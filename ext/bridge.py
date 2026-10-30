"""bridge.py — EXT-001 B 节：本地桥接服务（dub_server.py 的核心）

职责：
  * 只绑 127.0.0.1，WebSocket；
  * 安全：校验 Origin = chrome-extension://<本插件 id>，并用首次配对生成的 token 鉴权；
  * 管线：PCM（带 sample_index）→ 分段（R2T2 原有断句，EXT-002）→ ASR 定稿段
    → MT → TTS（按说话人选音色）→ 时长适配 → 下发 {id, t_start, t_end, src, tgt, spk, pcm24k}。

复用边界（EXT-001 总原则）：
  * ASR / MT / TTS 引擎**只 import 现有交付版本**，不改它们的文件；
  * 引擎未接入时，桥接服务仍可启动并完成**回声自测**（P0 ③）：
    服务端把收到的音频原样延迟 D 后发回，插件按 t_start + D 排程播放。

调用方式：
    python -m ext.bridge --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import secrets
import struct
import threading
import time
from typing import Dict, List, Optional, Tuple

# ★★ EXT-011：**必须早于任何 numpy / openvino import**。
#   OpenMP / MKL 运行时在**库被加载**（= `import numpy` 那一刻）读取
#   OMP_NUM_THREADS / MKL_NUM_THREADS / OPENBLAS_NUM_THREADS /
#   NUMEXPR_NUM_THREADS ⇒ 之后再设**无效**。
#   依据：ASR §60.2 持锁实测（OMP/MKL/OPENBLAS/NUMEXPR=1 ⇒ ASR CPU
#   7.81 核 → 约 1 核，libiomp5md 原本占 6.85 核，RTF 也改善）。
#   ⚠️ `ext.thread_limits` 自身**不 import numpy / openvino**，
#      所以这个调用点本身没有把「晚一步」的问题带进来。
from .thread_limits import apply_thread_limits as _apply_thread_limits

# ★★ EXT-017①：日志输出必须**绝不因编码问题抛异常**。
#   本机中文 Windows 控制台代码页实测 = gb2312（cp936 系），
#   而 `print("🔴 ...")` 在 GBK 编码下会抛 `UnicodeEncodeError`
#   ⇒ 一条日志写不出去 ⇒ 进程崩溃 / 日志中断在那一行（用户看到的「乱码」）。
#   ⇒ 所有对外日志一律走 `safe_print`（不可编码字符降级替换，绝不抛异常）。
#   （环境变量层的 PYTHONUTF8=1 由启动器负责，见 tools/ext_launcher.py。）
from .utf8_io import safe_print as _safe_print
# ★ EXT-017④：解析本插件的扩展 id（/pair 与 WS 握手都按**精确 id** 校验）。
from .extension_id import resolve_extension_id

THREAD_LIMIT_RECORD = _apply_thread_limits(log=lambda m: _safe_print(m))

import numpy as np

from . import config as C
from .adaptive_speed import combine_rates, decide_speed
from .duration import fit_duration
from .pipeline import EnginePipeline, SegmentJob, _FairLock
from .segmenter import plan_segments, describe as describe_segmenter
from .speaker import SpeakerTracker
from .time_stretch import wsola

# TTS 输出采样率（Qwen3-TTS 输出 24 kHz PCM16）
TTS_SAMPLE_RATE = 24000

# ── 引擎接入点（复用现有交付版本；此处只做延迟 import，不改对方文件） ──
ENGINE_ADAPTER = None  # 由 main() 注入：见 ext/engines.py


def _log(msg: str) -> None:
    """写一行桥接日志。

    ★ EXT-017①：**绝不抛异常**。
      中文 Windows 控制台代码页是 GBK，`🔴` / `⇒` / `⛔` 这些符号
      在 GBK 下**无法编码** ⇒ 直接 `print()` 会抛 `UnicodeEncodeError`
      ⇒ 进程崩溃或日志中断（用户报告的「乱码」）。
      ⇒ 统一走 `safe_print`：不可编码的字符降级替换，**日志继续往下走**。
    """
    _safe_print(f"[bridge {time.strftime('%H:%M:%S')}] {msg}")


class TokenStore:
    """首次配对生成的 token（落盘在项目目录，只读给插件）。"""

    def __init__(self, path: str) -> None:
        self.path = path
        self.token = self._load_or_create()

    def _load_or_create(self) -> str:
        if os.path.isfile(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                t = f.read().strip()
            if t:
                return t
        t = secrets.token_urlsafe(24)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(t)
        return t

    def verify(self, candidate: str) -> bool:
        return bool(candidate) and secrets.compare_digest(candidate, self.token)


def check_origin(origin: Optional[str], extension_id: Optional[str] = None) -> bool:
    """校验 Origin。

    Parameters
    ----------
    origin
        请求头里的 Origin。
    extension_id
        本插件的扩展 id。

        * ``None``（默认）⇒ 只校验**前缀** `chrome-extension://`
          （旧的宽松口径，保留给通用场景）；
        * 给了 id ⇒ **精确匹配** `chrome-extension://<本插件 id>`
          （★ EXT-017④ 的收紧口径）。
    """
    if not origin:
        return False
    if extension_id is None:
        return origin.startswith(C.ALLOWED_ORIGIN_PREFIX)
    return origin.strip() == "chrome-extension://%s" % extension_id


# ── EXT-006 P1：余量汇总（★ 缺陷 17：顶层口径修正） ──────────────
def _percentile(sorted_vals: List[float], p: float) -> float:
    """线性近似的分位数（与 `tools/p1_pipeline.py::_pct` 同口径）。"""
    if not sorted_vals:
        return 0.0
    k = min(len(sorted_vals) - 1,
            max(0, int(round(p * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def _linfit(xs: List[float], ys: List[float]) -> Tuple[float, float, float]:
    """最小二乘线性拟合 `y = a*x + b`。返回 `(a, b, r2)`。

    ★ EXT-008：用于「滞后随时间的斜率」。
      点数不足 2 ⇒ `(0.0, 0.0, 0.0)`（无斜率可言）。
      x 全同（退化）⇒ 斜率不可定义 ⇒ 返回 0。
    """
    n = len(xs)
    if n < 2:
        return (0.0, 0.0, 0.0)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return (0.0, my, 0.0)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    a = sxy / sxx
    b = my - a * mx
    # r²（判定拟合是否有意义）
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    r2 = (1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    return (a, b, r2)


def summarize_margins(margins: List[dict]) -> dict:
    """汇总逐句余量 ⇒ EXT-006 P1 的三项核心验收量。

    ★ 缺陷 17：**顶层必须是 deadline（排程）口径**。

    EXT-001 P1 原文要的是「每句『原声结束 → TTS 就绪』的**余量分布**、
    **余量 < 0 的句数**、**累计漂移**」。

    ⚠️ 这里的「余量」必须**先厘清基准**，否则会读出假结论：

    | 口径 | 定义 | 负数意味着 |
    |---|---|---|
    | **排程余量**（顶层，`basis="deadline"`） | `(t0 + t_start + D) − TTS就绪时刻` | **赶不上自己的播放时刻** ⇒ 这句会压后播 ⇒ **这才是「滞后」** |
    | 就绪延迟（`ready_after_orig_end`） | `TTS就绪时刻 − (t0 + t_end)` | 几乎恒为正 ⇒ 负数**没有**滞后含义 |

    实测（`.tmp/p1_run6/margin.json`）：就绪延迟口径下顶层读出
    `n_negative=0`、`cumulative_lag_sec=0.0`（**假结论：零滞后**），
    而排程口径的真值是 `n_negative=19`。

    ⇒ 顶层用排程口径；就绪延迟口径保留为子组（原始信息不丢）。

    ★★ EXT-008：**「累计滞后」口径再次修正 —— 删除「余量求和」量**。

    旧实现把 22 段余量**求和**当「累计滞后」（`cumulative_lag_sec`），
    实测读出 `-3969.5098`（run7）⇒ **这是 22 个独立量之和，不是累计滞后**，
    数值随段数线性放大，**没有物理含义**，reviewer 明确要求删除。

    ⇒ 改成两个**有物理含义**的量（EXT-008 原文口径）：
      1. `last_segment_lag_sec` = **末句滞后** = 末句 `max(0, −排程余量)`
         （= 末句「TTS 就绪时刻 − 它应播的时刻」）；
      2. `lag_growth_slope_sec_per_sec` = **滞后增长斜率**
         = 对 `(t_start, 排程余量)` 做**线性拟合**得到的斜率
         （负数 = 余量随时间越来越负 ⇒ 滞后在**累积**）。
      另保留 `max_lag_sec`（= 各句滞后的最大值，即「最坏的一句晚多少」）。

    Parameters
    ----------
    margins : list of dict
        每段一条，至少含 `deadline_margin_sec`（可缺）、`margin_sec`
        与 `t_start`（斜率拟合要用）。

    Returns
    -------
    dict
        顶层 = 排程口径验收量；`deadline` = 同值别名（向后兼容）；
        `ready_after_orig_end` = 就绪延迟口径。
    """
    dl = [float(m.get("deadline_margin_sec") or 0.0) for m in margins
          if m.get("deadline_margin_sec") is not None]
    rd = [float(m.get("margin_sec") or 0.0) for m in margins]
    # ★ EXT-008：斜率拟合需要 (t_start, 排程余量) 配对
    pairs = [(float(m.get("t_start") or 0.0),
              float(m.get("deadline_margin_sec") or 0.0))
             for m in margins if m.get("deadline_margin_sec") is not None]

    def _group(vals: List[float]) -> dict:
        """分布统计（**不含**求和量 —— EXT-008 要求删除）。"""
        g = {"n_negative": sum(1 for v in vals if v < 0)}
        if vals:
            s = sorted(vals)
            g.update({
                "min": round(s[0], 4),
                "p50": round(_percentile(s, 0.50), 4),
                "p95": round(_percentile(s, 0.95), 4),
                "max": round(s[-1], 4),
                "mean": round(sum(vals) / len(vals), 4),
            })
        return g

    out = {"n_segments": len(margins)}
    out.update(_group(dl))
    out["basis"] = "deadline"
    out["definition"] = ("排程余量 = (t0 + t_start + D) − TTS就绪时刻；"
                         "负数 = 该句赶不上自己的播放时刻（滞后）")

    # ── ★ EXT-008：滞后口径（替换旧的「求和」量） ──────────────
    if pairs:
        last_dm = pairs[-1][1]
        slope, intercept, r2 = _linfit([p[0] for p in pairs],
                                       [p[1] for p in pairs])
        out["last_segment_lag_sec"] = round(max(0.0, -last_dm), 4)
        out["max_lag_sec"] = round(max(0.0, -min(p[1] for p in pairs)), 4)
        out["lag_growth_slope_sec_per_sec"] = round(slope, 6)
        out["lag_growth_intercept_sec"] = round(intercept, 4)
        out["lag_growth_r2"] = round(r2, 6)
        out["lag_n_fit_points"] = len(pairs)
    else:
        out["last_segment_lag_sec"] = None
        out["max_lag_sec"] = None
        out["lag_growth_slope_sec_per_sec"] = None
        out["lag_growth_intercept_sec"] = None
        out["lag_growth_r2"] = None
        out["lag_n_fit_points"] = 0
    out["lag_definition"] = (
        "last_segment_lag_sec = 末句 max(0, −排程余量)；"
        "lag_growth_slope_sec_per_sec = 对 (t_start, 排程余量) 线性拟合的斜率"
        "（负数 = 滞后随时间累积）；max_lag_sec = 各句滞后的最大值。"
        "⚠️ 不再有「余量求和」量（EXT-008 判定它没有物理含义，已删除）。")

    # 向后兼容：旧读取方读 out["deadline"] 取排程口径
    out["deadline"] = {
        "n_negative": out["n_negative"],
        "last_segment_lag_sec": out["last_segment_lag_sec"],
        "max_lag_sec": out["max_lag_sec"],
        "lag_growth_slope_sec_per_sec": out["lag_growth_slope_sec_per_sec"],
        **({"min": out["min"], "p50": out["p50"], "p95": out["p95"],
            "max": out["max"], "mean": out["mean"]} if "min" in out else {}),
    }
    # 就绪延迟口径（原始信息保留，不作为验收量）
    out["ready_after_orig_end"] = {
        **_group(rd),
        "definition": ("就绪延迟 = TTS就绪时刻 − (t0 + t_end)；"
                       "正数 = 配音比原声结束晚多久可用（不是滞后）"),
    }
    return out


def _seg_proc_sec(m: dict) -> Optional[float]:
    """这一句的管线耗时（ASR+MT+TTS）。缺字段时用逐段耗时求和。"""
    if m.get("proc_sec") is not None:
        return float(m["proc_sec"])
    parts = [m.get("asr_sec"), m.get("mt_sec"), m.get("tts_sec")]
    if any(p is None for p in parts):
        return None
    return sum(float(p) for p in parts)


def _seg_audio_ready_rel(m: dict) -> Optional[float]:
    """这一句的**音频完整到达服务端**的时刻（相对会话起点 t0）。

    ★ 新版实测数据里服务端直接记了 `audio_ready_rel_sec`。
    ★ **旧版**实测数据（如 run7）没记这个字段 ⇒ **重建**：
      服务端的消息循环是**单线程串行**的 ⇒ 一句的推理**紧接着**
      「那一帧到达」开始 ⇒ 推理开始时刻 ≈ `ready_at − 管线耗时`；
      而 `t0` 可由 `orig_end − t_end` 反推 ⇒
          audio_ready_rel ≈ (ready_at − proc_sec) − t0
      ⇒ 这是**重建值**（不是直接实测），本函数返回 (值, 是否重建)。
    """
    if m.get("audio_ready_rel_sec") is not None:
        return float(m["audio_ready_rel_sec"])
    ready_at = m.get("ready_at")
    orig_end = m.get("orig_end")
    t_end = m.get("t_end")
    proc = _seg_proc_sec(m)
    if ready_at is None or orig_end is None or t_end is None or proc is None:
        return None
    t0 = float(orig_end) - float(t_end)
    return (float(ready_at) - proc) - t0


def decompose_lag(margins: List[dict], *, delay_sec: float) -> dict:
    """把「末句滞后」拆成**喂帧慢**与**引擎慢**两部分（EXT-008 第 2 点）。

    ★ 为什么必须拆：EXT-008 问「喂帧 570.96 s / 音频 300 s ⇒
      是谁阻塞？核对『滞后』里有多少是喂帧慢造成的」。

    对第 i 句（`t_start` = 该段在音频里的起点，会话秒）：

      * 该句的**应播时刻** = `t0 + t_start + D`
      * 该句的**音频完整到达服务端的时刻** = `t0 + audio_ready_rel_sec`
      * ⇒ `feed_lag_sec` = 音频到达时刻 − 应播时刻
        （>0 ⇒ **音频本身就送晚了** ⇒ 上行/反压造成的滞后）
      * ⇒ `intrinsic_lag_sec` = max(0, 管线耗时 − (D − 段长))
        （这段音频**即使准时送到**，光跑 ASR→MT→TTS 也赶不上 ⇒ 引擎慢）
      * 两者相加 ≈ 该句滞后（`max(0, −排程余量)`），差额是排程/分段误差。

    Returns
    -------
    dict
        含 `n_segments` / 末句各项 / 各分项的累计与均值。
    """
    if not margins:
        return {"n_segments": 0}
    feeds: List[float] = []
    intr: List[float] = []
    lags: List[float] = []
    n_reconstructed = 0
    for m in margins:
        dm = float(m.get("deadline_margin_sec") or 0.0)
        lag = max(0.0, -dm)
        proc = _seg_proc_sec(m)
        arel = _seg_audio_ready_rel(m)
        t_start = float(m.get("t_start") or 0.0)
        t_end = float(m.get("t_end") or 0.0)
        if arel is None:
            feed = 0.0
        else:
            if m.get("audio_ready_rel_sec") is None:
                n_reconstructed += 1
            feed = arel - (t_start + delay_sec)
        if proc is None:
            intrinsic = 0.0
        else:
            intrinsic = max(0.0, proc - max(0.0, delay_sec - (t_end - t_start)))
        feeds.append(feed)
        intr.append(intrinsic)
        lags.append(lag)
    last = margins[-1]
    return {
        "n_segments": len(margins),
        "definition": ("feed_lag_sec = 音频完整到达服务端的时刻 − 该句应播时刻"
                       "(t0+t_start+D)；>0 = 音频送晚了（上行/反压）。"
                       "intrinsic_lag_sec = max(0, 管线耗时 − (D − 段长))"
                       "= 即使准时送到也赶不上的部分（引擎慢）。"),
        "n_segments_audio_ready_reconstructed": n_reconstructed,
        "reconstruction_note": (
            "audio_ready_rel_sec 缺失时按 (ready_at − 管线耗时) − t0 重建"
            "（服务端消息循环单线程串行 ⇒ 推理紧接帧到达开始）。"
            "重建段数 >0 ⇒ 该值为推算而非直接实测。"),
        "last_segment": {
            "id": last.get("id"),
            "t_start": last.get("t_start"),
            "lag_sec": round(lags[-1], 4),
            "feed_lag_sec": round(feeds[-1], 4),
            "intrinsic_lag_sec": round(intr[-1], 4),
            "proc_sec": (round(_seg_proc_sec(last), 4)
                         if _seg_proc_sec(last) is not None else None),
            "audio_ready_rel_sec": (
                round(_seg_audio_ready_rel(last), 3)
                if _seg_audio_ready_rel(last) is not None else None),
        },
        "sum_feed_lag_sec": round(sum(feeds), 4),
        "sum_intrinsic_lag_sec": round(sum(intr), 4),
        "mean_feed_lag_sec": round(sum(feeds) / len(feeds), 4),
        "mean_intrinsic_lag_sec": round(sum(intr) / len(intr), 4),
        "sum_lag_sec": round(sum(lags), 4),
        "n_segments_feed_lagged": sum(1 for v in feeds if v > 0),
        "n_segments_intrinsic_lagged": sum(1 for v in intr if v > 0),
        "per_segment": [
            {"id": m.get("id"), "t_start": m.get("t_start"),
             "lag_sec": round(l, 4),
             "feed_lag_sec": round(f, 4),
             "intrinsic_lag_sec": round(i, 4)}
            for m, l, f, i in zip(margins, lags, feeds, intr)
        ],
    }


def decompose_lag_exact(margins: List[dict], *, delay_sec: float) -> dict:
    """★ EXT-008 第 2 点：把每句滞后**精确**拆成三个可归因的分量。

    恒等式（逐段精确闭合）::

        lag_sec = backlog_sec + struct_sec + proc_sec

    * `backlog_sec` = 该段音频**完整到达服务端**的时刻 − 该段**结束**时刻
      （>0 ⇒ **音频送晚了** ⇒ 上行/反压造成；这才是「喂帧慢」的量化）。
    * `struct_sec` = 该段**长度** − 缓冲窗 `D`
      （>0 ⇒ 这段内容本身就比缓冲窗长 ⇒ 结构性滞后，与引擎快慢无关）。
    * `proc_sec` = 该段的 **ASR + MT + TTS 管线耗时**
      （= 引擎本身的耗时）。

    ⚠️ `struct_sec` 可为负（该段比缓冲窗短 ⇒ 这部分是「提前量」）。
    ⚠️ `backlog_sec` 由 `audio_ready_rel_sec` 推得；该字段缺失时按
      `(ready_at − 管线耗时) − t0` **重建**（服务端消息循环单线程串行 ⇒
      推理紧接帧到达开始）⇒ `n_segments_backlog_reconstructed > 0`
      表示该项为**推算**而非直接实测。

    「喂帧慢占了多少滞后」= `sum_backlog_sec / sum_lag_sec`（见输出
    `backlog_share_of_lag_pct`）。
    """
    if not margins:
        return {"n_segments": 0}
    rows: List[dict] = []
    n_recon = 0
    for m in margins:
        dm = float(m.get("deadline_margin_sec") or 0.0)
        lag = max(0.0, -dm)
        proc = _seg_proc_sec(m)
        arel = _seg_audio_ready_rel(m)
        t_start = float(m.get("t_start") or 0.0)
        t_end = float(m.get("t_end") or 0.0)
        seg_len = max(0.0, t_end - t_start)
        if arel is None:
            backlog = 0.0
        else:
            if m.get("audio_ready_rel_sec") is None:
                n_recon += 1
            backlog = arel - t_end
        struct = seg_len - delay_sec
        p = proc or 0.0
        resid = lag - (backlog + struct + p)
        rows.append({
            "id": m.get("id"), "t_start": m.get("t_start"),
            "seg_len_sec": round(seg_len, 3),
            "lag_sec": round(lag, 4),
            "backlog_sec": round(backlog, 4),
            "struct_sec": round(struct, 4),
            "proc_sec": round(p, 4),
            "residual_sec": round(resid, 4),
        })
    sum_lag = sum(r["lag_sec"] for r in rows)
    sum_bk = sum(r["backlog_sec"] for r in rows)
    sum_st = sum(r["struct_sec"] for r in rows)
    sum_pr = sum(r["proc_sec"] for r in rows)
    max_resid = max((abs(r["residual_sec"]) for r in rows), default=0.0)
    return {
        "n_segments": len(rows),
        "identity": "lag_sec = backlog_sec + struct_sec + proc_sec（逐段精确闭合）",
        "definitions": {
            "backlog_sec": ("该段音频完整到达服务端的时刻 − 该段结束时刻；"
                            ">0 = 音频送晚了（上行/反压）⇒ 喂帧慢的量化"),
            "struct_sec": "该段长度 − 缓冲窗 D（>0 = 这段内容比缓冲窗还长）",
            "proc_sec": "该段 ASR + MT + TTS 管线耗时（引擎本身）",
        },
        "delay_sec": delay_sec,
        "n_segments_backlog_reconstructed": n_recon,
        "reconstruction_note": (
            "audio_ready_rel_sec 缺失时按 (ready_at − 管线耗时) − t0 重建 ⇒ "
            "该项为推算值（服务端消息循环单线程串行 ⇒ 推理紧接帧到达开始）。"),
        "sum_lag_sec": round(sum_lag, 4),
        "sum_backlog_sec": round(sum_bk, 4),
        "sum_struct_sec": round(sum_st, 4),
        "sum_proc_sec": round(sum_pr, 4),
        "mean_lag_sec": round(sum_lag / len(rows), 4),
        "mean_backlog_sec": round(sum_bk / len(rows), 4),
        "mean_struct_sec": round(sum_st / len(rows), 4),
        "mean_proc_sec": round(sum_pr / len(rows), 4),
        "backlog_share_of_lag_pct": (round(sum_bk / sum_lag * 100, 2)
                                     if abs(sum_lag) > 1e-9 else None),
        "struct_share_of_lag_pct": (round(sum_st / sum_lag * 100, 2)
                                    if abs(sum_lag) > 1e-9 else None),
        "proc_share_of_lag_pct": (round(sum_pr / sum_lag * 100, 2)
                                  if abs(sum_lag) > 1e-9 else None),
        "max_abs_residual_sec": round(max_resid, 6),
        "identity_closed": bool(max_resid < 0.01),
        "n_segments_backlog_positive": sum(1 for r in rows if r["backlog_sec"] > 0),
        "n_segments_struct_positive": sum(1 for r in rows if r["struct_sec"] > 0),
        "last_segment": rows[-1],
        "per_segment": rows,
    }


class Session:
    """一次配音会话。

    音频上行帧格式：{seq, sample_index, pcm(base64 PCM16 16k mono)}
    时间戳用**累计采样数**换算，不用墙钟，避免漂移（EXT-001 A 节）。

    ★ EXT-006：真实引擎模式下的**余量统计**是 P1 的核心验收量 ——
      「原声结束 → TTS 就绪」的余量分布、余量 < 0 的句数、累计滞后。
    """

    def __init__(self, token: str, *, delay_sec: float = 10.0,
                 engine=None) -> None:
        self.token = token
        self.delay_sec = delay_sec
        self.t0 = time.perf_counter()
        self.sample_index = 0
        self._buf = np.zeros((0,), dtype=np.float32)
        self.tracker = SpeakerTracker(
            clean_sec_required=C.SPK_CLEAN_SEC_REQUIRED,
            max_late_lag_sec=C.SPK_LATE_UPDATE_MAX_LAG_SEC,
            preset_voice=C.PRESET_VOICE,
        )
        self.n_frames = 0
        self.n_dropped = 0
        self._pending_sp: Optional[int] = None
        # ★ 已消耗（已切走）的样本数 —— 段的时间基点必须相对**会话起点**，
        #   不能相对「当前缓冲区」。见 _process_segment 的说明。
        self._consumed_samples = 0
        self._engine = engine if engine is not None else ENGINE_ADAPTER
        # ── EXT-006 余量统计 ──────────────────────────────────
        #   margin_sec = (TTS 就绪时刻) − (该段原声结束时刻)
        #   负数 ⇒ 配音来不及在原声结束前就绪 ⇒ 滞后累积
        self._seg_orig_end: Dict[str, float] = {}   # seg_id → 原声结束（会话秒）
        self._seg_ready: Dict[str, float] = {}      # seg_id → TTS 就绪（会话秒）
        self.margins: List[dict] = []               # 每句一条
        self.engine_calls: List[dict] = []          # 引擎各阶段耗时
        # ★ EXT-008 第 2 点：逐帧的「到达延迟」（实测「喂帧慢」）
        self._frame_arrival_delays: List[dict] = []
        self._n_frames_late = 0
        self._max_frame_arrival_delay = 0.0
        # ★ EXT-009：上一句实际采用的**自适应加速倍率**
        #   （用于「相邻句变化 ≤ 0.1×」与「滞回」两条约束）
        self._prev_adapt_speed = 1.0

    # ── 接收一帧 ────────────────────────────────────────────────
    def on_pcm_frame(self, msg: dict, *,
                     recv_at: Optional[float] = None) -> Optional[dict]:
        """处理一帧上行 PCM。

        Parameters
        ----------
        msg : dict
            一帧上行 PCM。
        recv_at : float or None
            ★ EXT-008：**这一帧到达服务端消息循环**的墙钟时刻
            （`time.perf_counter()`）。缺省则用进入本函数的时刻。
            ⇒ 用来把「喂帧慢」（服务端收到音频晚于实时）与
              「服务端排队慢」区分开（见 `decompose_lag()`）。

        Returns
        -------
        dict or None
            若该帧触发了「一段音频够长可分段」，返回待下发的配音任务列表；
            否则返回 None。
        """
        try:
            seq = int(msg.get("seq", 0))
            sidx = int(msg.get("sample_index", -1))
            pcm_b64 = msg.get("pcm") or ""
        except Exception:
            return None

        raw = base64.b64decode(pcm_b64) if pcm_b64 else b""
        if len(raw) < 2:
            return None
        # 连续性检查：sample_index 必须与上一帧接得上
        if self._pending_sp is not None and sidx != self._pending_sp:
            self.n_dropped += 1
            _log(f"帧不连续: 期望 {self._pending_sp} 实际 {sidx}（丢 {sidx - self._pending_sp} 样本）")
        arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        self._pending_sp = sidx + len(arr)

        self._buf = np.concatenate([self._buf, arr])
        self.n_frames += 1
        if recv_at is None:
            recv_at = time.perf_counter()
        # ★★ EXT-008 第 2 点：**这一帧到达服务端的延迟**（直接测「喂帧慢」）。
        #   帧的 `sample_index` 就是它的**音频时间**（EXT-001：用累计采样数换算，
        #   不用墙钟）⇒ 它「本该」在 `t0 + sidx/16000` 到达。
        #   ⇒ `arrival_delay_sec` = 实际到达时刻 − 本该到达时刻
        #     > 0 ⇒ **音频送晚了**（客户端被**服务端背压**卡住，或客户端自己慢）。
        #   ⇒ 这是**服务端侧的直接实测**，不受 TCP 缓冲大小影响
        #     （客户端侧的 `ws.send()` 阻塞时长可能被内核缓冲吸收 ⇒ 不可靠）。
        _should_arrive = self.t0 + (sidx / float(C.SAMPLE_RATE))
        _delay = recv_at - _should_arrive
        self._frame_arrival_delays.append({
            "seq": seq, "sidx": sidx,
            "delay_sec": round(_delay, 4),
            "recv_at": round(recv_at, 3)})
        # 汇总（滚动统计，不必每次都遍历全表）
        self._n_frames_late += 1 if _delay > 1.0 else 0
        if _delay > self._max_frame_arrival_delay:
            self._max_frame_arrival_delay = _delay

        # 分段：以 R2T2 原有断句为准（EXT-002）
        segs = plan_segments(self._buf)
        if len(segs) <= 1:
            return None
        # 只处理已完整落在 [min, max] 内的段，最后一段留在缓冲区里等后续音频
        ready = list(segs[:-1])
        if not ready:
            return None
        tasks = []
        # ★ 段索引是相对**当前缓冲区**的 ⇒ 换算成会话绝对样本偏移。
        #   旧实现每处理一段就把 self._buf 裁掉前段，却继续用旧的 (s0, s1)
        #   去切下一个段 ⇒ 索引错位（第二段起音频被切错），且 t_start 归零
        #   ⇒ 全部段的时间基点漂移。EXT-006 P1 要按时间表落盘配音，
        #   这个错位会直接污染「同步误差」指标。
        for (s0, s1) in ready:
            seg_audio = self._buf[s0:s1]
            abs0 = self._consumed_samples + s0
            abs1 = self._consumed_samples + s1
            tasks.extend(self._dispatch_segment(seq, abs0, abs1, seg_audio,
                                                audio_complete_at=recv_at))
        # 一次性裁掉所有已处理的段，并把基准点推进
        cut = ready[-1][1]
        self._buf = self._buf[cut:]
        self._consumed_samples += cut
        return tasks or None

    # ── 段派发（串行 vs 流水线） ────────────────────────────────
    def _dispatch_segment(self, seq: int, abs0: int, abs1: int,
                          seg_audio: np.ndarray, *,
                          audio_complete_at: float) -> list:
        """把一段交给处理路径。

        * **串行**（基类）⇒ 同步跑完 ASR→MT→TTS，返回这一段的配音任务；
        * **流水线**（`PipelineSession`）⇒ 提交到流水线线程，
          返回「**已经就绪**」的任务（未就绪的稍后由 drain 取回）。

        ★ 分开这个钩子是为了**不改动**基类的串行行为
          （旧自测全部针对串行路径，行为必须完全一致）。
        """
        return self._process_segment(seq, abs0, abs1, seg_audio,
                                     audio_complete_at=audio_complete_at)

    # ── 处理一段 → 配音任务 ──────────────────────────────────────
    def flush(self) -> list:
        """把缓冲区里的**尾段**也处理掉（EXT-006 P1：时间表要完整）。

        流式服务默认把最后一段留在缓冲区等后续音频（正常直播场景正确）。
        但 P1 验收要「配音 wav 和时间表落盘」⇒ 喂完最后一批音频后，
        客户端会发一条 `flush` ⇒ 这里把剩余缓冲切成一段并处理。

        Returns
        -------
        list
            配音任务列表（通常 0 或 1 条；缓冲区太短则 0 条）。
        """
        if self._buf.shape[0] < int(1.0 * C.SAMPLE_RATE):
            # 尾部不足 1 s ⇒ 没有有意义的语音段，丢弃（不计为段）
            self._buf = np.zeros((0,), dtype=np.float32)
            return []
        # ★ 绝对偏移：尾段同样要相对**会话起点**，不能归零
        #   （否则会重现「段起始时间基点归零」那个缺陷）。
        abs0 = self._consumed_samples
        abs1 = self._consumed_samples + self._buf.shape[0]
        seg_audio = self._buf
        tasks = self._process_segment(0, abs0, abs1, seg_audio)
        self._buf = np.zeros((0,), dtype=np.float32)
        self._consumed_samples += seg_audio.shape[0]
        return tasks

    def _process_segment(self, seq: int, s0: int, s1: int,
                         audio: np.ndarray, *,
                         audio_complete_at: Optional[float] = None) -> list:
        """**串行**处理一段（EXT-006 原有路径，保留作回退与自测基线）。

        ★ EXT-010：真实引擎模式下改走**流水线**（`ext/pipeline.py`），
          本方法只在 `pipeline=None` 时被调用（回声模式 / 桩引擎自测）。
        """
        t_start = s0 / C.SAMPLE_RATE
        t_end = s1 / C.SAMPLE_RATE
        seg_id = f"seg_{s0}"

        # ★ EXT-006：原声结束时刻（会话秒）—— 余量的基准
        orig_end = self.t0 + t_end
        self._seg_orig_end[seg_id] = orig_end
        # ★ EXT-008：这一段的**音频已经完整到达服务端**的时刻。
        #   缺省用「进入本函数」的时刻（等价于该帧到达后立刻开跑）。
        if audio_complete_at is None:
            audio_complete_at = time.perf_counter()

        # ASR 定稿：引擎未接入时留空（不猜内容）
        text = ""
        t_asr = time.perf_counter()
        if self._engine is not None:
            try:
                text = self._engine.asr(audio, t_start, t_end) or ""
            except Exception as e:
                _log(f"ASR 失败（段 {seg_id}）: {e}")
        asr_s = time.perf_counter() - t_asr

        # spk：EXT-002 —— 定稿先出，spk 可能为 None
        spk = self.tracker.spk_for_final(seg_id, t_start, t_end)
        self.tracker.register_pending(seg_id, spk, t_start, t_end)
        voice = self.tracker.voice_for(spk)

        # 译文
        tgt = ""
        t_mt = time.perf_counter()
        if self._engine is not None and text:
            try:
                tgt = self._engine.mt(text) or ""
            except Exception as e:
                _log(f"MT 失败（段 {seg_id}）: {e}")
        mt_s = time.perf_counter() - t_mt

        # TTS
        pcm24k = None
        speech_sec = 0.0
        t_tts = time.perf_counter()
        if self._engine is not None:
            try:
                pcm24k, speech_sec = self._engine.tts(tgt or text, voice=voice)
            except Exception as e:
                _log(f"TTS 失败（段 {seg_id}）: {e}")
        tts_s = time.perf_counter() - t_tts

        # ★ EXT-010：把「算指标 + 自适应加速 + 变速 + 产出任务」抽成
        #   `_finalize_segment()`，让**串行**与**流水线**共用同一份口径。
        return self._finalize_segment(
            seg_id=seg_id, t_start=t_start, t_end=t_end, orig_end=orig_end,
            audio_complete_at=audio_complete_at,
            text=text, tgt=tgt, spk=spk, voice=voice,
            pcm24k=pcm24k, speech_sec=speech_sec,
            asr_s=asr_s, mt_s=mt_s, tts_s=tts_s,
            ready_at=time.perf_counter(), error=None)

    def _finalize_segment(self, *, seg_id: str, t_start: float, t_end: float,
                          orig_end: float, audio_complete_at: float,
                          text: str, tgt: str, spk, voice: str,
                          pcm24k: Optional[bytes], speech_sec: float,
                          asr_s: float, mt_s: float, tts_s: float,
                          ready_at: float,
                          error: Optional[str] = None) -> list:
        """算指标 + 自适应加速 + 主机侧变速 + 产出配音任务。

        ★ EXT-010：**串行路径与流水线路径共用**这一段 ⇒
          两者的余量/滞后/倍率口径**逐字一致**（指标可比）。
        ★ 本方法**只允许一个线程同时调用**
          （串行路径天然满足；流水线里由**收口线程**串行调用）
          ⇒ `self._prev_adapt_speed` 的「相邻句 0.1×」约束在两条路径上都成立。
        """
        # ★ EXT-006：TTS 就绪时刻 + 余量
        self._seg_ready[seg_id] = ready_at
        # EXT-006 原文要的余量：「原声结束 → TTS 就绪」
        margin = ready_at - orig_end
        # ★ 另一个**决定能不能跟上**的口径：**排程截止余量**
        #   插件把这段配音排在 `t0 + t_start + D`（EXT-001 A 节）⇒
        #   配音必须在那一刻**之前**就绪，否则要么来不及、要么被钳位到「立刻播」。
        #   deadline_margin = (t0 + t_start + D) − ready_at
        #   ⇒ 负数 ⇒ 这句配音**赶不上**自己的播放时刻（真正的滞后）。
        deadline = self.t0 + t_start + self.delay_sec
        deadline_margin = deadline - ready_at
        # ★★ EXT-008：把这一段的**滞后拆成三项**，才能回答
        #   「有多少滞后是『喂帧慢』造成的、不是引擎慢造成的」。
        #   （定义见 `decompose_lag()`）
        proc_sec = asr_s + mt_s + tts_s
        # ① 音频完整到达服务端的时刻（相对会话起点）
        audio_ready_rel = audio_complete_at - self.t0
        # ② 「音频到达」相对「这段原声应播时刻（t_start + D）」的落后量
        #    —— 这就是**喂帧/上行慢**造成的部分（>0 = 音频到得太晚）
        feed_lag_sec = audio_ready_rel - (t_start + self.delay_sec)
        # ③ **引擎自身**的落后量：音频到齐后，光跑管线就花了 proc_sec
        #    ⇒ 这一句光靠引擎就已经赶不上了（与喂帧速度无关）
        intrinsic_lag_sec = max(0.0, proc_sec - max(0.0, self.delay_sec
                                                      - (t_end - t_start)))

        # ═══ ★ EXT-009：自适应加速播放（App 与插件统一参数） ═══
        #
        # 统一参数（EXT-009 明文）：
        #   lag   = 实际开播时刻 − 目标开播时刻
        #           （插件的目标开播时刻 = t0 + t_start + D）
        #   speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)
        #
        # ★ 本模块在**服务端**算 lag，理由与口径（务必如实理解）：
        #   服务端的 `deadline` = `t0 + t_start + D`（同一套 t0/D，
        #   与插件排程用的是**同一组参数**）⇒
        #   `lag_est = ready_at − deadline = −deadline_margin_sec`
        #   就是「这句配音**最早**能开播的时刻 − 它的目标开播时刻」
        #   ⇒ 插件若按时排程成功，这就是它的实际 lag；
        #     插件若被钳位到「立刻播」，实际 lag 还要再加钳位量（≤ 几十 ms）。
        #   ⚠️ **跨时钟的诚实说明**：插件自己的 t0（AudioContext 启动时刻）
        #   与服务端 t0（会话建立时刻）**不同源**（§6.4.1 已记录），
        #   两者的**常量偏差**会平移这个 lag 估计。
        #   但滞后的主导项是**管线 backlog**（占 83.18%，§6.4.3）
        #   ⇒ 偏差是二阶效应；且速度曲线在 lag=15 s 就饱和到 1.30×，
        #   小偏差在饱和区无影响。本轮如实记录该口径，不宣称「精确」。
        lag_est = max(0.0, -deadline_margin)
        dec = decide_speed(lag_est, prev_speed=self._prev_adapt_speed)

        # 时长适配（单句超长时压缩）—— EXT-009 明文「保留」
        fit = fit_duration(seg_id, t_start=t_start, t_end=t_end,
                           speech_sec=speech_sec, max_rate=C.TTS_RATE_MAX)
        # ★ EXT-009 EXT 侧：时长适配（1.0~1.25×）与自适应加速（1.0~1.30×）
        #   **相乘**，总倍率封顶 1.30×，超出的部分顺延。
        rates = combine_rates(fit.rate, dec.speed)
        total_rate = rates["total_rate"]
        self._prev_adapt_speed = dec.speed

        # ★ 保持音高变速在**主机侧单线程**做（EXT-009 明文：
        #   「时间伸缩在主机侧做，不能占满 CPU（单线程）」）。
        #   ★ 绝不用 playbackRate / 改采样率（会变调）⇒ 用 WSOLA。
        #   ★ 采样率必须传对：TTS 输出是 24 kHz。
        pcm_out = pcm24k
        speech_out = speech_sec
        stretch_sec = 0.0
        if pcm24k is not None and total_rate > 1.0 + 1e-6:
            try:
                t_stretch = time.perf_counter()
                arr = np.frombuffer(pcm24k, dtype="<i2").astype(np.float32) / 32768.0
                stretched = wsola(arr, total_rate, sample_rate=TTS_SAMPLE_RATE)
                pcm_out = (np.clip(stretched, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
                speech_out = len(pcm_out) / 2.0 / float(TTS_SAMPLE_RATE)
                stretch_sec = time.perf_counter() - t_stretch
            except Exception as e:
                _log(f"WSOLA 变速失败（段 {seg_id}）：{e} ⇒ 保持原速")
                pcm_out = pcm24k
                speech_out = speech_sec

        # 顺延量：按**实际采用的**总倍率算（封顶掉的部分排不进窗口 ⇒ 顺延）
        budget = fit.target_sec + fit.extend_sec
        defer_total = fit.defer_sec
        if budget > 0 and speech_out > budget:
            defer_total = max(defer_total, speech_out - budget)

        self.margins.append({
            "id": seg_id,
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            "orig_end": round(orig_end, 3),
            "ready_at": round(ready_at, 3),
            "margin_sec": round(margin, 4),
            "deadline": round(deadline, 3),
            "deadline_margin_sec": round(deadline_margin, 4),
            "asr_sec": round(asr_s, 4),
            "mt_sec": round(mt_s, 4),
            "tts_sec": round(tts_s, 4),
            "speech_sec": round(speech_sec, 4),
            "src_len": len(text or ""),
            "tgt_len": len(tgt or ""),
            "has_tts": pcm24k is not None,
            # ★ EXT-008：滞后分解（新增字段）
            "proc_sec": round(proc_sec, 4),
            "audio_ready_rel_sec": round(audio_ready_rel, 3),
            "feed_lag_sec": round(feed_lag_sec, 4),
            "intrinsic_lag_sec": round(intrinsic_lag_sec, 4),
            # ★ EXT-009：自适应加速（倍率 / lag 估计 / 顺延）
            "speed": round(total_rate, 4),
            "lag_est_sec": round(lag_est, 4),
            "adapt_speed": round(dec.speed, 4),
            "adapt_reason": dec.reason,
            "defer_total_sec": round(defer_total, 4),
            "stretch_sec": round(stretch_sec, 4),
            # ★ EXT-010：流水线化后某阶段失败时**如实记录**（不丢段）
            "error": error,
        })
        self.engine_calls.append({
            "id": seg_id, "asr_sec": round(asr_s, 4),
            "mt_sec": round(mt_s, 4), "tts_sec": round(tts_s, 4)})

        return [{
            "type": "tts",
            "id": seg_id,
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            "src": text,
            "tgt": tgt,
            "spk": spk,
            "voice": voice,
            "pcm24k": (base64.b64encode(pcm_out).decode("ascii")
                       if pcm_out is not None else None),
            "fit": fit.to_dict(),
            "delay_sec": self.delay_sec,
            # ★ EXT-009：自适应加速的决策与最终倍率
            #   （插件侧按 `speed` 播放，并把它显示在底栏）
            "speed": round(total_rate, 4),
            "adapt": dec.to_dict(),
            "rates": rates,
            "lag_est_sec": round(lag_est, 4),
            "speech_sec_out": round(speech_out, 4),
            "stretch_sec": round(stretch_sec, 4),
            "defer_total_sec": round(defer_total, 4),
            # ★ EXT-006 P1：把排程截止余量带给客户端 ⇒
            #   客户端可按 EXT-001 口径算「实际播放起点 − 原声起点 + D」，
            #   不必自己猜就绪时刻。
            "deadline_margin_sec": round(deadline_margin, 4),
            "margin_sec": round(margin, 4),
            "speech_sec": round(speech_sec, 4),
            "tts_ready_at": round(ready_at, 3),
        }]

    # ── P0 ③ 回声测试：原样延迟 D 发回 ────────────────────────────
    def echo(self, msg: dict) -> Optional[dict]:
        """回声模式：把收到的音频原样延迟 D 后发回。"""
        raw = base64.b64decode(msg.get("pcm") or "")
        if not raw:
            return None
        sidx = int(msg.get("sample_index", 0))
        t_start = sidx / C.SAMPLE_RATE
        return {
            "type": "echo",
            "id": f"echo_{sidx}",
            "seq": int(msg.get("seq", 0)),
            "t_start": round(t_start, 3),
            "t_end": round(t_start + len(raw) / 2 / C.SAMPLE_RATE, 3),
            # ★ 回声原样 16 kHz PCM16；插件按 t_start + D 排程播放
            "pcm24k": base64.b64encode(raw).decode("ascii"),
            "sample_rate": C.SAMPLE_RATE,
            "delay_sec": self.delay_sec,
        }

    def stats(self) -> dict:
        out = {
            "n_frames": self.n_frames,
            "n_dropped": self.n_dropped,
            "buffered_sec": round(self._buf.shape[0] / C.SAMPLE_RATE, 2),
            "speaker": self.tracker.stats(),
            "margin": self.margin_summary(),
            # ★ EXT-009：自适应加速的**各倍率时间占比**与滞后曲线
            #   （EXT-009 验收：「报告滞后随时间的曲线（起点、峰值、结尾）
            #   和各倍率的时间占比」）
            "adaptive_speed": self.adaptive_speed_stats(),
            # ★ EXT-008：滞后分解（喂帧慢 vs 引擎慢）
            "lag_decomposition": decompose_lag(self.margins,
                                              delay_sec=self.delay_sec),
            # ★★ EXT-008 第 2 点：**逐帧到达延迟**（服务端侧直接实测）
            #   ⇒ 直接回答「喂帧慢了多少、是不是被服务端背压卡住」
            "feed_arrival_delay": {
                "n_frames_measured": len(self._frame_arrival_delays),
                "n_frames_late_gt_1s": self._n_frames_late,
                "late_ratio": (round(self._n_frames_late
                                     / len(self._frame_arrival_delays), 4)
                               if self._frame_arrival_delays else None),
                "max_delay_sec": round(self._max_frame_arrival_delay, 4),
                "mean_delay_sec": (
                    round(sum(d["delay_sec"]
                              for d in self._frame_arrival_delays)
                          / len(self._frame_arrival_delays), 4)
                    if self._frame_arrival_delays else None),
                "last_delay_sec": (self._frame_arrival_delays[-1]["delay_sec"]
                                   if self._frame_arrival_delays else None),
                "definition": ("arrival_delay_sec = 帧到达服务端的墙钟时刻 − "
                               "(t0 + sample_index/16000)；"
                               ">0 ⇒ 这一帧的音频**送晚了**。"),
            },
        }
        # ★ EXT-010：流水线诊断（串行模式下为 None）
        out["pipeline"] = self.pipeline_stats() \
            if isinstance(self, PipelineSession) else None
        # ★★ EXT-011：线程限制的**实际生效记录**（reviewer 可直接核对，
        #   不必猜这个进程到底有没有限过线程）
        out["thread_limits"] = THREAD_LIMIT_RECORD
        return out

    def margin_summary(self) -> dict:
        """★ EXT-006 P1 核心验收量。

        ★★ 缺陷 17（本轮实测抓到的真缺陷）：**顶层的口径曾经是错的**。

        旧实现顶层用 `margin_sec`（= TTS就绪时刻 − (t0 + t_end)，
        即「原声结束后**多久**配音才可用」的**延迟**）来算
        `n_negative` / `cumulative_lag_sec` ⇒ 在**按墙钟实时喂帧**的
        P1 实测里，这个延迟**恒为正**（37~250 s）⇒
        顶层读出来是 **`n_negative=0`、`cumulative_lag_sec=0.0`**
        ⇒ 读的人会得出「**零句超时、零累计滞后**」的**假结论**，
        而同一份文件里的 `deadline` 组却是
        `n_negative=19`、`cumulative_lag_sec=-2841.3498`（实测真值）。

        ⇒ 根因：**EXT-001 的「余量 < 0 的句数」必须是「赶不上播放时刻」
          的口径**（负数 = 配音赶不上 `t0 + t_start + D`），
          而不是「比原声结束晚了多久」的延迟口径。
          延迟口径下「负数」几乎没有意义（配音比原声结束更早可用是好事）。

        ⇒ 修法：顶层**改用 deadline 口径**（EXT-001 排程口径），
          延迟口径降级为 `ready_after_orig_end` 子组（保留原始信息，不丢）。
          两组都带 `definition` 字符串 ⇒ reviewer 可自行核对口径。

        返回结构：
          * 顶层 = EXT-001 验收量（deadline 口径）：
            `n_segments` / `n_negative` / `cumulative_lag_sec` /
            `peak_lag_sec` / `min` / `p50` / `p95` / `max` / `mean`
            + `basis` / `definition`
          * `deadline` 子组 = 顶层同值的**别名**（向后兼容旧读取方）
          * `ready_after_orig_end` 子组 = 旧的延迟口径（保留原始信息）
        """
        return summarize_margins(self.margins)

    # ── ★ EXT-009：自适应加速的统计 ────────────────────────────
    def adaptive_speed_stats(self) -> dict:
        """EXT-009 验收要的「各倍率时间占比」与「滞后曲线」。

        EXT-009 明文：
        > 报告滞后随时间的曲线（起点、峰值、结尾）和**各倍率的时间占比**，
        > **丢句 = 0**。

        Returns
        -------
        dict
            * `n_segments` — 参与统计的句数；
            * `speed_time_share` — 按**句的音频时长**加权的倍率占比
              （比按句数更贴近「时间占比」的真实含义）；
            * `speed_count_share` — 按**句数**的倍率占比；
            * `lag_curve` — 滞后曲线（起点 / 峰值 / 结尾 / 逐段序列）；
            * `n_dropped_dub` — 丢句数（EXT-009 要求 **丢句 = 0**）。
        """
        rows = [m for m in self.margins if m.get("speed") is not None]
        if not rows:
            return {"n_segments": 0,
                    "speed_time_share": {}, "speed_count_share": {},
                    "lag_curve": {}, "n_dropped_dub": 0,
                    "note": "尚无带 speed 的段（自适应加速未启用或还没出句）"}

        def _bucket(v: float) -> str:
            if v <= 1.001:
                return "1.00"
            if v <= 1.10:
                return "1.00-1.10"
            if v <= 1.20:
                return "1.10-1.20"
            if v <= 1.30 + 1e-6:
                return "1.20-1.30"
            return ">1.30"

        buckets = ["1.00", "1.00-1.10", "1.10-1.20", "1.20-1.30", ">1.30"]
        time_share = {b: 0.0 for b in buckets}
        count_share = {b: 0 for b in buckets}
        total_sec = 0.0
        for m in rows:
            sp = float(m.get("speed") or 1.0)
            b = _bucket(sp)
            seg_sec = float(m.get("t_end", 0)) - float(m.get("t_start", 0))
            time_share[b] += max(0.0, seg_sec)
            count_share[b] += 1
            total_sec += max(0.0, seg_sec)
        for b in buckets:
            time_share[b] = (round(time_share[b] / total_sec, 4)
                             if total_sec > 0 else 0.0)

        lags = [(float(m.get("t_start", 0)),
                 max(0.0, float(m.get("lag_est_sec", 0.0) or 0.0)))
                for m in rows]
        peak_i = max(range(len(lags)), key=lambda i: lags[i][1]) \
            if lags else 0
        return {
            "n_segments": len(rows),
            "speed_time_share": time_share,
            "speed_count_share": count_share,
            "total_audio_sec": round(total_sec, 3),
            "lag_curve": {
                "start_sec": round(lags[0][1], 3) if lags else None,
                "peak_sec": round(lags[peak_i][1], 3) if lags else None,
                "peak_at_t_start": round(lags[peak_i][0], 3) if lags else None,
                "end_sec": round(lags[-1][1], 3) if lags else None,
                "series_t_start": [round(a, 3) for a, _ in lags],
                "series_lag_sec": [round(b, 3) for _, b in lags],
            },
            # ★ EXT-009：丢句必须为 0（不改译文、不丢句、不回退到丢句）
            "n_dropped_dub": sum(1 for m in rows if not m.get("has_tts")),
            "definition": ("lag_est_sec = −deadline_margin_sec = "
                           "(这句最早能开播的时刻) − (t0 + t_start + D)；"
                           "speed = 时长适配倍率 × 自适应加速倍率，"
                           "总倍率封顶 1.30×。"),
        }



class PipelineSession(Session):
    """★ EXT-010：**句级流水线**会话（ASR / MT / TTS / 主机侧收口 各一线程）。

    与基类 `Session` 的差别只有一个：**段的处理从"同步跑完"变成"提交给流水线"**。
    其它（分段、时间基点、余量统计、自适应加速、顺序下发）**完全复用**基类实现。

    ★ 为什么继承而不是复制：
      - EXT-009 的自适应加速（`decide_speed` / `combine_rates` / WSOLA）
        与 EXT-008 的滞后分解都在基类的 `_process_segment` 里；
      - 流水线化只改**执行方式**，不改**语义** ⇒ 继承复用是最小改动。
    """

    def __init__(self, token: str, *, delay_sec: float = 10.0,
                 engine=None) -> None:
        super().__init__(token, delay_sec=delay_sec, engine=engine)
        # ★ GPU 设备互斥：ASR 与 MT 都在 GPU.0 ⇒ 二者互斥串行。
        #   （TTS 在 NPU，不参与互斥 —— interference 实测已验证
        #     ASR ∥ TTS 并发时互不拖慢，见 ext/pipeline.py 顶部。）
        #   ★ 用**公平锁**（FIFO）：普通 `threading.Lock` 不保证公平
        #     ⇒ ASR 连续拿锁、MT 饿死 ⇒ 三个阶段退化成串行
        #     ⇒ 流水线反而比串行更慢（实测过，见 §8 的缺陷记录）。
        self._device_lock = _FairLock()
        self._pipeline = EnginePipeline(
            asr_fn=self._stage_asr,
            mt_fn=self._stage_mt,
            tts_fn=self._stage_tts,
            emit_fn=self._stage_emit,
            device_lock=self._device_lock,
            on_log=_log,
        )
        self._seg_index = 0

    # ── 阶段函数（各自在流水线线程里跑） ────────────────────────
    def _stage_asr(self, job) -> None:
        """ASR 阶段（在 ASR 线程里跑）。"""
        t0 = time.perf_counter()
        text = ""
        if self._engine is not None:
            try:
                text = self._engine.asr(job.audio, job.t_start, job.t_end) or ""
            except Exception as e:
                _log(f"ASR 失败（段 {job.seg_id}）: {e}")
                # ★ EXT-010：如实标记（**不丢段**）⇒ 收口时进 `error` 字段
                job.mark_error("asr", e)
        job.asr_sec = time.perf_counter() - t0
        job.text = text

    def _stage_mt(self, job) -> None:
        """MT 阶段（在 MT 线程里跑）。"""
        t0 = time.perf_counter()
        tgt = ""
        if self._engine is not None and job.text:
            try:
                tgt = self._engine.mt(job.text) or ""
            except Exception as e:
                _log(f"MT 失败（段 {job.seg_id}）: {e}")
                job.mark_error("mt", e)
        job.mt_sec = time.perf_counter() - t0
        job.tgt = tgt

    def _stage_tts(self, job) -> None:
        """TTS 阶段（在 TTS 线程里跑）。"""
        # spk / voice：EXT-002 —— 定稿先出，spk 可能为 None
        #   ⇒ 这段在**提交时**就已确定（spk 旁路不阻塞定稿）。
        job.spk = self.tracker.spk_for_final(job.seg_id, job.t_start, job.t_end)
        self.tracker.register_pending(job.seg_id, job.spk,
                                       job.t_start, job.t_end)
        job.voice = self.tracker.voice_for(job.spk)

        t0 = time.perf_counter()
        pcm24k = None
        speech_sec = 0.0
        if self._engine is not None:
            try:
                pcm24k, speech_sec = self._engine.tts(job.tgt or job.text,
                                                      voice=job.voice)
            except Exception as e:
                _log(f"TTS 失败（段 {job.seg_id}）: {e}")
                job.mark_error("tts", e)
        job.tts_sec = time.perf_counter() - t0
        job.pcm24k = pcm24k
        job.speech_sec = speech_sec
        job.ready_at = time.perf_counter()

    def _stage_emit(self, job) -> Optional[dict]:
        """主机侧收口阶段（**单线程** ⇒ WSOLA 变速不占满 CPU）。

        ★ 复用基类的全部 EXT-008/EXT-009 口径（`_finalize_segment`）。
        """
        result = self._finalize_segment(
            seg_id=job.seg_id, t_start=job.t_start, t_end=job.t_end,
            orig_end=job.orig_end, audio_complete_at=job.audio_complete_at,
            text=job.text, tgt=job.tgt, spk=job.spk, voice=job.voice,
            pcm24k=job.pcm24k, speech_sec=job.speech_sec,
            asr_s=job.asr_sec, mt_s=job.mt_sec, tts_s=job.tts_sec,
            ready_at=job.ready_at, error=job.error)
        # `_finalize_segment` 返回 **list**（串行路径直接 extend 用），
        # 而流水线的收口阶段要的是**单个**任务 dict ⇒ 这里拆开。
        if isinstance(result, list):
            return result[0] if result else None
        return result

    # ── 派发钩子：提交到流水线 ──────────────────────────────────
    def _dispatch_segment(self, seq: int, abs0: int, abs1: int,
                          seg_audio: np.ndarray, *,
                          audio_complete_at: float) -> list:
        """提交一段到流水线；返回**已就绪**的任务（通常为空）。"""
        t_start = abs0 / C.SAMPLE_RATE
        t_end = abs1 / C.SAMPLE_RATE
        seg_id = f"seg_{abs0}"
        job = SegmentJob(
            index=self._seg_index, seg_id=seg_id,
            t_start=t_start, t_end=t_end, audio=seg_audio,
            orig_end=self.t0 + t_end,
            audio_complete_at=audio_complete_at)
        self._seg_index += 1
        self._pipeline.submit(job)
        # 已就绪的（流水线跑得比提交快时）顺手取走
        return self._pipeline.pop_ready(block=False)

    # ── 收尾 ────────────────────────────────────────────────────
    def flush(self) -> list:
        """★ EXT-010：尾段也**走流水线**（不能走串行路径！）。

        ⚠️ **为什么必须重写**：基类的 `flush()` 调用 `_process_segment()`，
        那会**同步**跑完 ASR→MT→TTS 并调 `_finalize_segment()`；
        而流水线的**收口线程**也在调 `_finalize_segment()`
        ⇒ 两者**并发** ⇒ `_finalize_segment` 里读的
        `self._prev_adapt_speed`（EXT-009「相邻句 0.1×」约束）
        与 `self.margins.append(...)` 会被**两个线程同时改**
        ⇒ 口径可能错乱 ⇒ **必须让尾段也走流水线**（收口线程串行调用）。
        """
        if self._buf.shape[0] < int(1.0 * C.SAMPLE_RATE):
            # 尾部不足 1 s ⇒ 没有有意义的语音段，丢弃（不计为段）
            self._buf = np.zeros((0,), dtype=np.float32)
            return []
        abs0 = self._consumed_samples
        abs1 = self._consumed_samples + self._buf.shape[0]
        seg_audio = self._buf
        self._buf = np.zeros((0,), dtype=np.float32)
        self._consumed_samples += seg_audio.shape[0]
        # 走流水线（与 `_dispatch_segment` 同一路径）
        self._dispatch_segment(0, abs0, abs1, seg_audio,
                               audio_complete_at=time.perf_counter())
        # 返回「已就绪」的任务（尾段通常还没跑完 ⇒ 返回空列表）
        return self._pipeline.pop_ready(block=False)

    def drain(self, timeout: float = 300.0) -> list:
        """等流水线把**所有**段跑完，取回全部任务（按段序）。"""
        return self._pipeline.wait_all(timeout=timeout)

    def pipeline_stats(self) -> dict:
        return self._pipeline.snapshot()

    def close(self) -> None:
        try:
            self._pipeline.stop()
        except Exception:
            pass


def _get_header(websocket, name: str) -> Optional[str]:
    """跨 websockets 版本取请求头。

    websockets 10.x/11.x 旧 asyncio API：``websocket.request_headers``；
    websockets 12+ 新 asyncio API：``websocket.request.headers``。
    两种都兼容，缺 header 返回 None。
    """
    try:
        hdrs = getattr(websocket, "request_headers", None)
        if hdrs is None:
            req = getattr(websocket, "request", None)
            hdrs = getattr(req, "headers", None)
        if hdrs is None:
            return None
        return hdrs.get(name, None)
    except Exception:
        return None


def _make_session(token: str, *, delay_sec: float, engine,
                  use_pipeline: bool = False) -> "Session":
    """建会话（★ EXT-010：可选**流水线**模式）。

    * `use_pipeline=False` ⇒ 串行 `Session`（**原有行为完全不变**，
      旧自测全部针对这条路径）；
    * `use_pipeline=True`  ⇒ `PipelineSession`（句级并行）。

    ⚠️ **回声模式不用流水线**（echo 是逐帧原样返回，没有分段/推理）。
    """
    if use_pipeline and engine is not None:
        _log("★ 使用流水线会话（EXT-010：ASR/MT/TTS/收口 各一线程）")
        return PipelineSession(token, delay_sec=delay_sec, engine=engine)
    return Session(token, delay_sec=delay_sec, engine=engine)


async def handle_ws(websocket, *, tokens: TokenStore, delay_sec: float,
                    echo_mode: bool, engine=None,
                    session_holder: Optional[dict] = None,
                    margin_out: Optional[str] = None,
                    use_pipeline: bool = False) -> None:
    """单连接的握手与消息循环。

    ★★ 缺陷 15（EXT-006 P1 实测抓到的真缺陷）：**不能覆盖已有 session**。

    成因：每条 WebSocket 连接都会新建一个 `Session`，并把它写进
    `session_holder["session"]`。而编排器 `tools/run_p1_real.py` 的
    `_request_margin_dump()`（缺陷 14 的「双保险」）会**另开一条连接**来
    请求落盘 ⇒ 那条连接建了一个**全新的空 Session** ⇒
    把 `session_holder["session"]` 指向了空会话 ⇒
    随后 `dump_margin` 落盘的是**空统计**（`n_segments=0`、
    `per_segment=[]`）⇒ **把客户端刚写好的真余量数据覆盖掉了**。

    ⇒ 后果：EXT-006 要求的「余量分布 / 余量<0 句数 / 累计滞后」
       在**最后一步**被清空 —— 比「不落盘」更隐蔽（文件在、内容是空的）。

    修法：**已有活跃 session 时，本连接不再顶替它**（`session_holder`
       保持指向原会话）。这样：
       * 客户端那条连接写进去的真数据不会被第二条连接冲掉；
       * 第二条连接发的 `dump_margin` 依然能触发落盘 ——
         `_dump_margin` 读的是 `session_holder["session"]`（= **真会话**），
         不是这条连接自己的空会话。
    """
    origin = _get_header(websocket, "Origin") or ""
    # ★★ EXT-017④：Origin 必须是**本插件**（精确 id），不是任意扩展。
    #   解析不出本插件 id ⇒ 一律拒绝（不静默放宽）。
    _eid = resolve_extension_id()
    if not check_origin(origin, _eid):
        _log(f"拒绝连接：Origin 非法 ({origin!r})"
             + (f"，本插件 id={_eid}" if _eid else "（未能解析本插件 id）"))
        await websocket.close(code=1008, reason="bad origin")
        return

    # token 通过请求头或首个消息给出
    token = _get_header(websocket, "X-Bridge-Token")
    if not token:
        # ★ 浏览器端 WebSocket **不能自定义请求头** ⇒ 允许 token 放在
        #   首个 hello 消息里（EXT-003 P0①③ 的插件侧就是这么连的）。
        #   安全口径不变：token 必须正确，且 Origin 必须是 chrome-extension://。
        first = await _recv_first(websocket)
        if first is None:
            _log("拒绝连接：缺少 token")
            await websocket.close(code=1008, reason="no token")
            return
        token = str(first.get("token") or "")
        if not token:
            _log("拒绝连接：缺少 token")
            await websocket.close(code=1008, reason="no token")
            return
        if not tokens.verify(token):
            _log("拒绝连接：token 不匹配")
            await websocket.close(code=1008, reason="bad token")
            return
        _log(f"已通过首个 hello 消息鉴权（role={first.get('role')}）")
        session = _make_session(token, delay_sec=delay_sec, engine=engine,
                                 use_pipeline=use_pipeline)
        _register_session(session_holder, session)
        await _handle_messages(websocket, session=session,
                               first=first, echo_mode=echo_mode,
                               delay_sec=delay_sec,
                               engine=engine,
                               margin_out=margin_out,
                               session_holder=session_holder)
        return
    if not tokens.verify(token):
        _log("拒绝连接：token 不匹配")
        await websocket.close(code=1008, reason="bad token")
        return

    _log(f"已连接（origin={origin}）")
    session = _make_session(token, delay_sec=delay_sec, engine=engine,
                             use_pipeline=use_pipeline)
    _register_session(session_holder, session)
    await _handle_messages(websocket, session=session, first=None,
                           echo_mode=echo_mode, delay_sec=delay_sec,
                           engine=engine,
                           margin_out=margin_out,
                           session_holder=session_holder)


def _register_session(session_holder: Optional[dict], session) -> None:
    """把会话登记进 holder —— **但绝不顶替已有的活跃会话**（缺陷 15）。

    为什么要这样：见 `handle_ws` 的缺陷 15 说明。
    编排器的「双保险」会另开一条连接来请求落盘；若那条连接顶替了
    真会话，`dump_margin` 落的就是**空统计**，把真数据覆盖掉。
    """
    if session_holder is None:
        return
    existing = session_holder.get("session")
    if existing is not None:
        _log("已有活跃会话 ⇒ 本连接不顶替（缺陷 15 修复：避免落盘空统计）")
        return
    session_holder["session"] = session


async def _recv_first(websocket) -> Optional[dict]:
    """读第一条消息并解析成 dict（用于 hello 帧里的 token 鉴权）。"""
    try:
        raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
    except Exception:
        return None
    try:
        msg = json.loads(raw)
    except Exception:
        return None
    return msg if isinstance(msg, dict) else None


async def _handle_messages(websocket, *, session: "Session", first: Optional[dict],
                           echo_mode: bool, delay_sec: float,
                           engine=None,
                           margin_out: Optional[str] = None,
                           session_holder: Optional[dict] = None) -> None:
    """消息循环。`first` 若已读过则先处理它。"""
    try:
        pending = [first] if first else []
        it = pending.pop() if pending else None
        while True:
            if it is not None:
                msg = it
                it = None
            else:
                raw = await websocket.recv()
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            if mtype == "hello":
                await websocket.send(json.dumps({
                    "type": "hello_ack",
                    "delay_sec": delay_sec,
                    "sample_rate": C.SAMPLE_RATE,
                    "segmentation": describe_segmenter(),
                }))
                continue
            if mtype == "stats":
                # ★★ EXT-010：流水线模式下，先把**已就绪**的任务下发，
                #   再回 stats（否则 stats 会比任务先到，客户端会误判段数）。
                if isinstance(session, PipelineSession):
                    for task in session._pipeline.pop_ready(block=False):
                        await websocket.send(json.dumps(task))
                await websocket.send(json.dumps({"type": "stats", **session.stats()}))
                continue
            if mtype == "pcm":
                # ★ EXT-008：记下**这一帧到达消息循环**的墙钟时刻。
                #   客户端是按墙钟节拍喂帧的（真实时间）⇒
                #   `recv_at` 与「客户端本该发出的时刻」一比，
                #   就知道**是客户端送得晚，还是服务端排队晚**
                #   （区别于「引擎算得慢」）。
                _recv_at = time.perf_counter()
                if echo_mode:
                    out = session.echo(msg)
                else:
                    # ★★ 推理必须**离开事件循环**（EXT-006 P1 实测修掉的真缺陷）。
                    #   真实 TTS 单句要几十秒～几百秒（首次 NPU 编译更久），
                    #   若在事件循环里同步跑 ⇒ 事件循环被阻塞 ⇒ 服务端
                    #   无法及时处理客户端的 pong ⇒ websockets 的
                    #   keepalive ping timeout（ping_interval=20s /
                    #   ping_timeout=20s）触发 ⇒ 服务端以 **1011** 关闭连接
                    #   ⇒ 客户端在喂帧途中断连，本轮所有已算好的配音/时间表
                    #   **全部拿不到**（实测：pipeline.log 报
                    #   `received 1011 (internal error) keepalive ping timeout`）。
                    #   `asyncio.to_thread` 让推理在**工作线程**里跑，
                    #   事件循环始终能响应心跳。
                    out = await asyncio.to_thread(session.on_pcm_frame, msg,
                                                  recv_at=_recv_at)
                if out:
                    for task in (out if isinstance(out, list) else [out]):
                        await websocket.send(json.dumps(task))
                # ★★ EXT-010：流水线模式下，段是**异步**跑完的 ⇒
                #   每次收到帧后**顺手把已就绪的任务取走**下发。
                #   （未就绪的继续在流水线里跑，稍后由下一帧/flush/stats 取走。）
                if isinstance(session, PipelineSession):
                    for task in session._pipeline.pop_ready(block=False):
                        await websocket.send(json.dumps(task))
                continue
            if mtype == "dump_margin":
                # ★★ EXT-006 P1 实测修掉的缺陷 14：余量统计**主动落盘**。
                #   成因：编排器停服务时用 `bridge.terminate()`（SIGTERM），
                #     进程被直接终止 ⇒ Python 的 `finally` **不会执行**
                #     ⇒ `margin.json` 永远不落盘
                #     （实测：p1_run4 的 pipeline rc=0、19 个 wav 都在，
                #       但 margin.json 缺失、报告里 `bridge_stats: null`
                #       ⇒ EXT-006 要求的「余量分布 / 余量<0 句数 /
                #       累计滞后」**全部拿不到**）。
                #   修法：客户端在断开前发一条 `dump_margin` ⇒ 服务端
                #     **立刻**把余量统计写盘（不依赖进程退出路径）。
                if margin_out:
                    _log("收到 dump_margin 请求 ⇒ 落盘 %s" % margin_out)
                    _dump_margin(session_holder or {}, margin_out,
                                 engine)
                    await websocket.send(json.dumps({
                        "type": "margin_dumped", "path": margin_out,
                        "dumped": True}))
                else:
                    # ★★ 缺陷 18：即使**没配 --margin-out**，也**必须**回确认。
                    #   旧实现：不回确认 ⇒ 客户端只能干等 `dump_timeout`
                    #   （默认 60 s）才放弃 ⇒ 每个没配落盘的会话都要白等 60 s
                    #   （实测：桩引擎自测里「realtime 喂帧」耗时 76.55 s
                    #     而音频只有 16.00 s ⇒ **超时的不是喂帧，是收尾**）。
                    #   ⇒ 现在无论是否落盘都回 `margin_dumped`，
                    #     用 `dumped` 字段区分「真落盘了」与「没配落盘路径」。
                    _log("收到 dump_margin 请求，但未配置 --margin-out（不落盘）")
                    await websocket.send(json.dumps({
                        "type": "margin_dumped", "path": None,
                        "dumped": False}))
                continue
            if mtype == "flush":
                # ★ EXT-006 P1：客户端说「音频喂完了」⇒ 把**尾段**也处理掉。
                #   流式服务默认把最后一段留在缓冲区（等后续音频），
                #   但 P1 要求「配音 wav 和时间表落盘」⇒ 尾段必须出，
                #   否则时间表缺最后一段，reviewer 回转写时对不上。
                #   回声模式不适用（echo 是逐帧原样返回，无需切段）。
                if not echo_mode:
                    # ★ 同上：尾段也要走线程，避免尾段推理阻塞心跳
                    out = await asyncio.to_thread(session.flush)
                    if out:
                        for task in out:
                            await websocket.send(json.dumps(task))
                    # ★★ EXT-010：流水线模式下，尾段也**异步**跑
                    #   ⇒ flush 之后必须**等流水线把剩下的段都跑完**，
                    #   否则尾段的配音任务来不及下发（客户端会等不到段数达标）。
                    if isinstance(session, PipelineSession):
                        for task in await asyncio.to_thread(session.drain):
                            await websocket.send(json.dumps(task))
                continue
    except Exception as e:
        _log(f"连接异常: {e}")
    finally:
        _log("连接关闭")


async def serve(host: str, port: int, *, delay_sec: float, echo_mode: bool,
                token_path: str, engine=None, margin_out: Optional[str] = None,
                session_holder: Optional[dict] = None,
                use_pipeline: bool = False) -> None:
    import websockets

    tokens = TokenStore(token_path)
    _log(f"token 文件：{token_path}")
    _log(f"监听 ws://{host}:{port}（echo={echo_mode}, D={delay_sec}s，"
         f"pipeline={use_pipeline}）")
    async with websockets.serve(
        lambda ws: handle_ws(ws, tokens=tokens, delay_sec=delay_sec,
                              echo_mode=echo_mode, engine=engine,
                              session_holder=session_holder,
                              margin_out=margin_out,
                              use_pipeline=use_pipeline),
        host, port,
        origins=None,
        max_size=32 * 1024 * 1024,
        # ★ 心跳放宽（EXT-006 P1 实测）：默认 ping_interval=20s /
        #   ping_timeout=20s。真实推理单句可能耗时数十秒（首次 NPU 编译
        #   可达数百秒）⇒ 服务端若在事件循环里处理推理，就来不及回 pong
        #   ⇒ 触发 keepalive timeout ⇒ 以 1011 关闭连接。
        #   现在推理已挪到工作线程（见 _handle_messages），这里再放宽一次
        #   作为双保险：即便个别步骤仍慢，也不至于误杀长连接。
        ping_interval=60,
        ping_timeout=300,
    ):
        await asyncio.Future()   # 永久运行


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT 桥接服务")
    ap.add_argument("--host", default=C.BRIDGE_HOST)
    ap.add_argument("--port", type=int, default=C.BRIDGE_PORT)
    ap.add_argument("--delay", type=float, default=10.0, help="延迟 D（秒）")
    ap.add_argument("--echo", action="store_true", help="P0 ③ 回声自测模式")
    ap.add_argument("--token-file", default=C.BRIDGE_TOKEN_FILE)
    # ── EXT-006：真实引擎（P1） ──────────────────────────────
    ap.add_argument("--real", action="store_true",
                    help="接入真实引擎（ASR→MT→TTS），EXT-006 P1")
    ap.add_argument("--target-lang", default="en",
                    help="目标语言（en/zh/ja/...），TTS 会显式传给它")
    ap.add_argument("--margin-out", default=None,
                    help="把余量统计与时间表落盘到这个 JSON")
    # ── ★ EXT-010：句级流水线 ────────────────────────────────
    ap.add_argument("--pipeline", action="store_true",
                    help="用流水线会话（ASR/MT/TTS/收口 各一线程，句级并行）；"
                         "依据 EXT-008 (c) interference 实测（ASR ∥ TTS 互不拖慢）")
    # ── ★ EXT-012：配对 HTTP 端点（插件自动取 token） ──
    ap.add_argument("--pair-port", type=int, default=C.PAIR_PORT,
                    help="配对/状态 HTTP 端点端口（0 = 关闭）")
    # ── ★ EXT-017②：启动即预热引擎（让「正在加载模型…」可见） ──
    ap.add_argument("--no-warmup", action="store_true",
                    help="不预热引擎（启动后等第一句音频再懒加载；"
                         "默认是**启动即预热**）")
    ap.add_argument("--warmup-strict", action="store_true",
                    help="任一引擎加载失败就拒绝启动（默认：告警后继续）")
    args = ap.parse_args(argv)

    try:
        import websockets  # noqa: F401
    except Exception:
        _log("缺少依赖：websockets（pip install websockets）")
        return 2

    # 互斥检查（EXT-001 总原则）：实时字幕 App 在运行就拒绝启动
    if _caption_app_running():
        _log("检测到实时字幕 App 在运行，拒绝启动（设备互斥）")
        return 3

    token_path = args.token_file
    if not os.path.isabs(token_path):
        token_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), token_path)

    # ★★ EXT-012：配对端点要**复用同一个 TokenStore** ⇒ token 与 WebSocket
    #   鉴权用的是同一个值（不会各自生成不同的 token）。
    try:
        _tokens = TokenStore(token_path)
    except Exception:
        _tokens = None

    # ── EXT-006：注入真实引擎 ────────────────────────────────
    engine = None
    if args.real:
        try:
            from .engines import load_runtime_engine
            engine = load_runtime_engine(target_lang=args.target_lang)
            _log(f"真实引擎已接线：ASR(R2T2 INT8@{C.DEVICE_ASR}) → "
                 f"MT(Hy-MT2 INT8@{C.DEVICE_MT}) → "
                 f"TTS(Qwen3-TTS@{C.DEVICE_TTS})，目标语言={args.target_lang}")
        except Exception as e:
            # ★ 不静默回落到回声模式 —— 否则 P1 验收会拿到假数据
            _log(f"❌ 真实引擎接线失败：{type(e).__name__}: {e}")
            return 4
    else:
        _log("回声模式（未接引擎）—— 仅供 P0 ③ 自测")

    # ★★ EXT-017②：**启动即预热引擎**，让「正在加载模型…」可见。
    #   根因：三个引擎原先都是**懒加载**（第一句音频进来才 load）
    #         ⇒ start 之后屏幕上什么都没有（用户报的「无任何输出」）。
    #   ⇒ 现在启动阶段就把 ASR/MT/TTS 逐个加载好，每步都有进度提示。
    #   ⚠️ 预热会占 GPU/NPU ⇒ 与实时字幕 App 互斥（上面已检查）。
    #   ⚠️ 预热**失败**不静默：要么拒绝启动（--warmup-strict），
    #      要么明确告警后继续（默认，用户仍可用回声/部分能力）。
    holder: dict = {}
    # ★★ EXT-017②：预热期间 `/status` 就要能报「正在加载」。
    #   ⇒ 配对端点必须**在预热之前**起来（否则预热那 20–40 秒里
    #     /status 根本不在线 ⇒ 启动器/popup 轮询一直失败
    #     ⇒ 状态灯永远停在「正在加载模型…」，不会翻成「TTS 就绪」）。
    holder["engine_state"] = "loading" if (args.real and engine is not None) \
        else "unknown"

    # ★★ EXT-012：配对 HTTP 端点（**用户不需要手动复制 token**）
    #   插件从 http://127.0.0.1:<pair_port>/pair 自动取 token
    #   ⇒ 安全口径不变：仅接受 Origin: chrome-extension:// 的请求。
    pair_server = None
    try:
        from .pair_server import PairServer
        pair_server = PairServer(
            port=args.pair_port,
            host=args.host,
            token_provider=lambda: (_tokens.token if _tokens else ""),
            status_provider=lambda: _pair_status(holder),
        )
        ok, msg = pair_server.start()
        if ok:
            _log(f"配对端点：{msg}（EXT-012：插件自动取 token）")
        else:
            _log(f"⚠️ {msg}（插件将需要手动粘贴 token）")
            pair_server = None
    except Exception as e:
        _log(f"⚠️ 配对端点不可用：{e}（插件将需要手动粘贴 token）")
        pair_server = None

    warm_report: dict = {}
    if args.real and engine is not None and not args.no_warmup:
        _log("正在加载模型…（预计 20–40 秒，请稍候）")
        try:
            warm_report = engine.warmup(on_progress=_log)
        except Exception as e:
            warm_report = {"ok": False, "loaded": [], "failed": {"warmup": str(e)}}
            _log(f"❌ 引擎预热异常：{type(e).__name__}: {e}")
        if warm_report.get("ok"):
            _log(f"✅ 模型加载完成（ASR/MT/TTS 就绪，"
                 f"耗时 {warm_report.get('elapsed_sec')} 秒）")
        else:
            failed = warm_report.get("failed") or {}
            _log(f"❌ 部分引擎加载失败：{failed}")
            _log(f"   详细日志见本文件（%LOCALAPPDATA%\\LiveDubEXT\\bridge.log）")
            if args.warmup_strict:
                _log("已按 --warmup-strict 拒绝启动（引擎不完整 ⇒ 配音会有问题）")
                return 5

    # ★★ EXT-017②：预热结果放进 holder ⇒ /status 能报告引擎状态
    #   （popup 显示「正在加载模型…」/「TTS 就绪」/「某引擎失败」）。
    if warm_report:
        holder["warmup"] = warm_report
    holder["engine_ready"] = bool(warm_report.get("ok")) if warm_report else False
    if warm_report:
        holder["engine_state"] = "ready" if warm_report.get("ok") else "partial"

    try:
        asyncio.run(serve(args.host, args.port, delay_sec=args.delay,
                          echo_mode=args.echo, token_path=token_path,
                          engine=engine, margin_out=args.margin_out,
                          session_holder=holder,
                          use_pipeline=args.pipeline))
    except KeyboardInterrupt:
        _log("已停止")
    finally:
        if pair_server is not None:
            try:
                pair_server.stop()
            except Exception:
                pass
        _dump_margin(holder, args.margin_out, engine)
    return 0


def _dump_margin(holder: dict, out_path: Optional[str], engine) -> None:
    """把余量统计与逐句时间表落盘（EXT-006 P1 验收要求）。

    ★★ 缺陷 15 的第二道防线：**绝不用空统计覆盖已有的真数据**。
    若本次要写的 `n_segments` 为 0，而磁盘上已有文件含更多段
    ⇒ 判定为「拿错了会话 / 会话还没数据」⇒ **跳过写盘**并记日志。
    （宁可少写一份，也不能把 EXT-006 的核心验收量清空。）
    """
    if not out_path:
        return
    sess = holder.get("session")
    # ★ EXT-008：滞后分解落盘（喂帧慢 vs 引擎慢）
    #   ⚠️ 用 getattr 取 delay_sec ⇒ 桩 session（自测用的假对象）也不会崩。
    _dl = float(getattr(sess, "delay_sec", 10.0) or 10.0) if sess else 10.0
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_lang": getattr(engine, "target_lang", None),
        "margin_summary": (sess.margin_summary() if sess else {}),
        "per_segment": (sess.margins if sess else []),
        "engine_calls": (sess.engine_calls if sess else []),
        "engine_stats": (engine.stats() if engine is not None else {}),
        "lag_decomposition": (decompose_lag(sess.margins, delay_sec=_dl)
                              if sess else {}),
        # ★ EXT-009：自适应加速统计（滞后曲线 + 各倍率时间占比 + 丢句数）
        #   ⚠️ 用 getattr 取 ⇒ 桩 session（自测用的假对象）也不会崩。
        "adaptive_speed": (sess.adaptive_speed_stats()
                           if sess is not None
                           and hasattr(sess, "adaptive_speed_stats") else {}),
        # ★★ EXT-011：线程限制记录（4 个环境变量的实际值 + 开关状态）
        "thread_limits": dict(THREAD_LIMIT_RECORD),
    }
    n_new = len(data.get("per_segment") or [])

    # ★ 第二道防线：不用空统计覆盖真数据
    try:
        if n_new == 0 and os.path.isfile(out_path):
            with open(out_path, "r", encoding="utf-8") as f:
                old = json.load(f)
            n_old = len(old.get("per_segment") or [])
            if n_old > 0:
                _log(f"拒绝落盘空统计（本次 0 段，磁盘已有 {n_old} 段）"
                     f"⇒ 保留原文件：{out_path}")
                return
    except Exception as e:
        _log(f"覆盖保护检查失败（继续写盘）：{e}")

    try:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        _log(f"余量统计已落盘：{out_path}（{n_new} 段）")
    except Exception as e:
        _log(f"余量统计落盘失败：{e}")


def _pair_status(holder: dict) -> dict:
    """★ EXT-012：给插件 popup 用的**实时状态**摘要。

    popup 要显示（EXT-012 明文 ③）：
    * 桥接连接状态；
    * 当前延迟（D）；
    * 当前语速倍率；
    * ⇒ 滞后（lag）也一并给出（用户最关心的就是「落后多少秒」）。

    ⚠️ 只返回**只读**的标量摘要，不含 token、不含原始音频。
    """
    out: dict = {
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "has_session": False,
        "delay_sec": None,
        "lag_sec": None,
        "speed": None,
        "n_segments": 0,
        "speed_time_share": {},
        "n_dropped_dub": 0,
        # ★ EXT-017②：引擎加载状态（popup 显示「正在加载模型…」/「TTS 就绪」）
        "engine_state": "unknown",
        "engine_loaded": [],
        "engine_failed": {},
    }
    holder = holder if isinstance(holder, dict) else {}
    # 引擎加载状态（由 main() 在预热后写入 holder）
    warm = holder.get("warmup") or {}
    if isinstance(warm, dict) and warm:
        out["engine_loaded"] = list(warm.get("loaded") or [])
        out["engine_failed"] = dict(warm.get("failed") or {})
        out["engine_state"] = "ready" if warm.get("ok") else "partial"
    else:
        # ★★ EXT-017②：预热**还没结束**（或被 --no-warmup 关掉）时，
        #   holder 里的 engine_state 说明当前阶段
        #   （"loading" = 正在加载 / "unknown" = 未预热）。
        st = holder.get("engine_state")
        if isinstance(st, str) and st in ("loading", "unknown", "ready", "partial"):
            out["engine_state"] = st
    sess = holder.get("session") if isinstance(holder, dict) else None
    if sess is None:
        return out
    out["has_session"] = True
    try:
        out["delay_sec"] = float(getattr(sess, "delay_sec", 0) or 0) or None
    except Exception:
        pass
    try:
        m = sess.margin_summary()
        out["lag_sec"] = m.get("last_segment_lag_sec")
        out["n_segments"] = m.get("n_segments") or 0
    except Exception:
        pass
    try:
        a = sess.adaptive_speed_stats()
        out["speed_time_share"] = a.get("speed_time_share") or {}
        out["n_dropped_dub"] = a.get("n_dropped_dub") or 0
        curve = a.get("lag_curve") or {}
        # ★ 当前倍率 = 最近的倍率（lag_curve 末值 ≈ 当前倍率对应的滞后）
        #   ⇒ 用「各倍率占比里最大的那个」作为「当前大致倍率」的可读近似。
        shares = out["speed_time_share"]
        if shares:
            out["speed"] = max(shares, key=lambda k: shares[k] or 0)
        out["lag_curve"] = {k: curve.get(k) for k in
                            ("start_sec", "peak_sec", "peak_at_t_start", "end_sec")}
    except Exception:
        pass
    try:
        out["thread_limits"] = dict(THREAD_LIMIT_RECORD)
    except Exception:
        pass
    return out


def _caption_app_running() -> bool:
    """检测实时字幕 App 是否在运行（互斥铁律）。"""
    try:
        import psutil  # type: ignore
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmd = " ".join(p.info.get("cmdline") or [])
                if "live_caption" in cmd.lower() and "ext.bridge" not in cmd.lower():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


if __name__ == "__main__":
    raise SystemExit(main())
