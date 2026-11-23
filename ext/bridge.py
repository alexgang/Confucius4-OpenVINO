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
import collections
import contextlib
import json
import os
import secrets
import struct
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

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
from .config import normalize_lang_code
from .adaptive_speed import combine_rates, decide_speed
from .duration import fit_duration
from .pipeline import EnginePipeline, SegmentJob, _FairLock
from .segmenter import (plan_segments, describe as describe_segmenter,
                       split_first_segment,
                       split_first_segment_streaming)
from .speaker import SpeakerTracker
from . import bg_separator as _bgsep
from .time_stretch import wsola
# ★★ EXT-029：说话人旁路（**独立线程 + 有界队列** ⇒ 不反压 ASR）。
#   注意：这里**不 import 引擎/模型**，只 import 纯 Python 的旁路壳子
#   ⇒ 加载失败也不影响 bridge 启动（旁路自己安静降级）。
from .speaker_bypass import SpeakerBypass

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


# v0.4.7：桥接进程自身的 CPU / 内存（播放界面底栏显示；不依赖 psutil）
_PROC_USAGE = {"t": None, "cpu": None, "pct": None}


_ACCEL = None


def _dub_drops(sess) -> dict:
    """v0.4.9: dubs not played (late) - shown in the player HUD."""
    try:
        n = sum(int(getattr(sess, k, 0) or 0) for k in ("_n_skip_tts", "_n_late_drop"))
        return {"dub_dropped": n, "seg_skipped": int(getattr(sess, "_n_catchup", 0) or 0)}
    except Exception:
        return {}


def _proc_usage() -> dict:
    out = {"proc_cpu_pct": None, "proc_mem_mb": None, "igpu_pct": None, "npu_pct": None}
    # v0.4.8：iGPU / NPU 占用（整机，PDH 计数器；后台线程每秒采一次）
    global _ACCEL
    try:
        if _ACCEL is None:
            from .accel_usage import AccelUsage
            _ACCEL = AccelUsage(1.0).start()
        out.update(_ACCEL.latest)
    except Exception:
        pass
    try:
        t = time.perf_counter()
        _ot = os.times()
        c = float(_ot[0]) + float(_ot[1])
        if _PROC_USAGE["t"] is None:
            _PROC_USAGE["t"], _PROC_USAGE["cpu"] = t, c
        elif t - _PROC_USAGE["t"] >= 0.5:
            _PROC_USAGE["pct"] = max(0.0, 100.0 * (c - _PROC_USAGE["cpu"])
                                     / ((t - _PROC_USAGE["t"]) * float(os.cpu_count() or 1)))
            _PROC_USAGE["t"], _PROC_USAGE["cpu"] = t, c
        if _PROC_USAGE["pct"] is not None:
            out["proc_cpu_pct"] = round(_PROC_USAGE["pct"], 1)
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        class _PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
        pmc = _PMC(); pmc.cb = ctypes.sizeof(_PMC)
        if k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
            out["proc_mem_mb"] = round(pmc.WorkingSetSize / 1048576.0, 1)
    except Exception:
        pass
    return out


# v0.4.2：当前正在使用桥接的对端 IP（局域网模式同一时间只服务一个人）
ACTIVE_PEER = {"ip": None, "n": 0}


# v0.4.0：取消 token 配对后，所有连接共用的会话键（只用于把 player / uplink 连接归到同一会话）
NO_PAIR_TOKEN = "nopair"


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
    # ★★★★★★ EXT-036 ③：**斜率只拟合「有 TTS 的段」**。
    #   ## 病根（reviewer EXT-036 ③ 的原话）
    #     「`margin_summary` 里的 `lag_growth_slope=0.248 (r²=0.375)`
    #       **混进了 60 s 之后 18 个没有 TTS 的段**（它们的 lag 是按
    #       直线外推出来的）⇒ **这个口径作废**，改成只用有 TTS 的段来拟合。」
    #   ## 为什么必须改
    #     * 有 TTS 的段 = 真正占用引擎、真正产生积压的段；
    #     * 没有 TTS 的段（`ASR='—'` 的空段）**没有 TTS 排队**，
    #       它们的 `deadline_margin` 只是「按同一斜率外推」的产物
    #       ⇒ 拿它们拟合 ⇒ **自证循环**（用外推值验证外推值）
    #       ⇒ 斜率被**稀释**（实测 0.248 vs 真实 ~0.46）。
    #   ⇒ 顶层 `lag_growth_slope_sec_per_sec` 改为 **TTS-only** 口径；
    #     旧的全段口径**保留**为 `lag_growth_slope_all_sec_per_sec`（附注作废）。
    tts_pairs = [(float(m.get("t_start") or 0.0),
                  float(m.get("deadline_margin_sec") or 0.0))
                 for m in margins
                 if m.get("deadline_margin_sec") is not None
                 and _seg_has_tts(m)]

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
        # ★★★★ EXT-036 ③：**顶层斜率改用 TTS-only 拟合**。
        #   有 TTS 的段才真正占用引擎、才产生积压 ⇒ 斜率必须只拟合它们。
        #   ⚠️ 旧口径（全段）保留为 `lag_growth_slope_all_sec_per_sec`
        #     ⇒ 可对照，但**不再**是验收量（reviewer 已判定其作废）。
        slope_tts, intercept_tts, r2_tts = (None, None, None)
        if len(tts_pairs) >= 2:
            slope_tts, intercept_tts, r2_tts = _linfit(
                [p[0] for p in tts_pairs], [p[1] for p in tts_pairs])
        out["lag_growth_slope_sec_per_sec"] = (
            round(slope_tts, 6) if slope_tts is not None else None)
        out["lag_growth_intercept_sec"] = (
            round(intercept_tts, 4) if intercept_tts is not None else None)
        out["lag_growth_r2"] = (
            round(r2_tts, 6) if r2_tts is not None else None)
        out["lag_n_fit_points"] = len(tts_pairs)
        # ── 旧口径（**作废**，仅供对照）──────────────────────────
        out["lag_growth_slope_all_sec_per_sec"] = round(slope, 6)
        out["lag_growth_intercept_all_sec"] = round(intercept, 4)
        out["lag_growth_r2_all"] = round(r2, 6)
        out["lag_n_fit_points_all"] = len(pairs)
        out["lag_growth_slope_note"] = (
            "★ EXT-036 ③：顶层 `lag_growth_slope_sec_per_sec` = "
            "**只用「有 TTS 的段」**拟合 (t_start, 排程余量)。"
            "旧的全段口径（含没有 TTS 的空段，其 lag 是直线外推值）"
            "保留在 `lag_growth_slope_all_sec_per_sec`，**已作废**，"
            "不得用于归因。")
    else:
        out["last_segment_lag_sec"] = None
        out["max_lag_sec"] = None
        out["lag_growth_slope_sec_per_sec"] = None
        out["lag_growth_intercept_sec"] = None
        out["lag_growth_r2"] = None
        out["lag_n_fit_points"] = 0
        out["lag_growth_slope_all_sec_per_sec"] = None
        out["lag_growth_intercept_all_sec"] = None
        out["lag_growth_r2_all"] = None
        out["lag_n_fit_points_all"] = 0
    out["lag_definition"] = (
        "last_segment_lag_sec = 末句 max(0, −排程余量)；"
        "lag_growth_slope_sec_per_sec = 对 (t_start, 排程余量) 线性拟合的斜率"
        "（负数 = 滞后随时间累积）；max_lag_sec = 各句滞后的最大值。"
        "⚠️ 不再有「余量求和」量（EXT-008 判定它没有物理含义，已删除）。"
        "★ EXT-036 ③：斜率**只用有 TTS 的段**拟合（见 lag_growth_slope_note）。")

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


def _seg_has_tts(m: dict) -> bool:
    """★ EXT-036 ③：这一段**是否真的产出了 TTS 音频**。

    ## 为什么需要这个判据
      没有 TTS 的段（`ASR='—'` 的空段）**没有 TTS 排队**
      ⇒ 它们的 `deadline_margin` 只是「按同一斜率外推」的产物
      ⇒ 拿它们拟合斜率 = **用外推值验证外推值**（自证循环）
      ⇒ 斜率被严重**稀释**（实测 0.248 vs 真实 ~0.46）。

    ## 判据（按可靠性排序）
      1. `has_tts` 字段（服务端收口时直接落的布尔值）—— 权威；
      2. `tts_sec > 0`（TTS 引擎耗时 > 0）—— 回退；
      3. `speech_sec > 0`（有输出语音时长）—— 再回退。

    ## ★ 「字段缺失」= **未知**，**不等于**「没有 TTS」
      ⚠️ 旧实现把「三个字段都没有」当作 `False`（= 没有 TTS ⇒ 排除）
        ⇒ 任何**字段不全**的逐段数据（例如自测里造的
          `{"t_start":…, "deadline_margin_sec":…}`）会**整组被排除**
        ⇒ 斜率变成 `None` ⇒ **回归**（`test_ext_selfcheck` 变红）。
      ⇒ 现在：**只有明确判定为「没有 TTS」才排除**；
        字段缺失 ⇒ 视为「未知」⇒ **计入**（宁可多算一个点，
        也不能把整组数据悄悄清空）。
      ⇒ 真实产物里 `has_tts` 恒有值（服务端收口时必落）⇒
        真实口径**不受**这个放宽影响。
    """
    if m.get("has_tts") is not None:
        return bool(m.get("has_tts"))
    if m.get("tts_sec") is not None:
        return float(m.get("tts_sec") or 0.0) > 0.0
    if m.get("speech_sec") is not None:
        return float(m.get("speech_sec") or 0.0) > 0.0
    # ★ 字段全缺 ⇒ **未知** ⇒ 计入（不是「没有 TTS」）
    return True


def _seg_proc_sec(m: dict) -> Optional[float]:
    """这一句的管线耗时（ASR+MT+TTS）。缺字段时用逐段耗时求和。"""
    if m.get("proc_sec") is not None:
        return float(m["proc_sec"])
    parts = [m.get("asr_sec"), m.get("mt_sec"), m.get("tts_sec")]
    if any(p is None for p in parts):
        return None
    return sum(float(p) for p in parts)


def compute_rtf_breakdown(margins: List[dict]) -> dict:
    """★ EXT-034 ②：**三个 RTF 口径分列**（不再混成一个数）。

    ## 为什么必须拆（reviewer EXT-034 ② 的批评）
      旧结论写「TTS RTF = 1.231 > 1 ⇒ 结构上不可能实时」。
      但 **1.231 不是 TTS 自身的 RTF**：
        `1.231 = TTS 耗时 73.84 s ÷ 源音频时长 59.98 s`
      其中**混进了「中文译文比英文原声长」这个因素**（1.196 倍）。
      ⇒ 用它去判「TTS 引擎慢」是**口径错** ⇒ 归因会错。

    ## 三个口径（各自有明确含义）
      | 口径 | 定义 | 说明 |
      |---|---|---|
      | `RTF_out` | `Σ tts_sec ÷ Σ speech_sec` | **TTS 自身的 RTF**（输出语音 vs 耗时）⇒ 这才是「TTS 引擎快不快」 |
      | `speech_over_src` | `Σ speech_sec ÷ Σ 源音频秒` | **译文比原声长多少**（中文 vs 英文）⇒ 与 TTS 快慢**无关** |
      | `tts_over_src` | `Σ tts_sec ÷ Σ 源音频秒` | **端到端占用率**（旧口径 1.231 就是它）⇒ 受上面两个**同时**影响 |

    ## 为什么这三个必须分开看
      * `RTF_out > 1` ⇒ **TTS 引擎**自己就来不及（⇒ TTS 模块提速）
      * `RTF_out ≤ 1` 但 `tts_over_src > 1` ⇒ TTS 没问题，
        是**译文变长 + 段太碎**把总占用推过了 1
        ⇒ **EXT 侧**可改（缩短切段 / 减少段数）
      * `speech_over_src` 大 ⇒ 译文变长（语言属性）⇒ 只能靠**变速**吸收

    ## 源音频秒的口径
      `t_end − t_start` = 这一段**原声**的时长（上行采样时间轴）。
      ⚠️ 只统计**有 TTS 的段**（`tts_sec > 0`）⇒ 与「TTS 实际处理了多少」
      口径一致 ⇒ 三个数**自洽**（分子分母同源）。

    Returns
    -------
    dict
        含三个口径 + 各自的分子分母 + **逐段**明细 + 每段口径。
        ⚠️ 分母为 0 时给 `None`（**不臆造 0 或 1**）。
    """
    src_total = 0.0        # 源音频秒（原声）
    speech_total = 0.0     # 输出语音秒（TTS 产出）
    tts_total = 0.0        # TTS 耗时秒
    asr_total = 0.0
    mt_total = 0.0
    per_seg = []
    n = 0
    for m in margins:
        tts_s = m.get("tts_sec")
        if tts_s is None or float(tts_s) <= 0.0:
            continue                      # 只算**真有 TTS** 的段
        tts_s = float(tts_s)
        sp = m.get("speech_sec")
        sp = float(sp) if sp is not None else 0.0
        t0 = m.get("t_start")
        t1 = m.get("t_end")
        src_s = 0.0
        if t0 is not None and t1 is not None:
            src_s = max(0.0, float(t1) - float(t0))
        src_total += src_s
        speech_total += sp
        tts_total += tts_s
        asr_total += float(m.get("asr_sec") or 0.0)
        mt_total += float(m.get("mt_sec") or 0.0)
        n += 1
        per_seg.append({
            "id": m.get("id"),
            "t_start": t0,
            "src_sec": round(src_s, 4),
            "speech_sec": round(sp, 4),
            "tts_sec": round(tts_s, 4),
            # ★ 逐段三个口径（reviewer 实测：前 7 段 1.09~1.23、后 6 段 0.82~0.89）
            "rtf_out": (round(tts_s / sp, 4) if sp > 0 else None),
            "speech_over_src": (round(sp / src_s, 4) if src_s > 0 else None),
            "tts_over_src": (round(tts_s / src_s, 4) if src_s > 0 else None),
        })

    def _r(num: float, den: float) -> Optional[float]:
        return round(num / den, 4) if den > 0 else None

    return {
        "n_segments_with_tts": n,
        # ★ 三个口径（**分列**）
        "RTF_out": _r(tts_total, speech_total),
        "speech_over_src": _r(speech_total, src_total),
        "tts_over_src": _r(tts_total, src_total),
        # ★ 分子分母（可自证）
        "totals": {
            "tts_sec": round(tts_total, 4),
            "speech_sec": round(speech_total, 4),
            "src_sec": round(src_total, 4),
            "asr_sec": round(asr_total, 4),
            "mt_sec": round(mt_total, 4),
        },
        # ★ 口径说明（reviewer 明文要求「三个数分开写」）
        "definitions": {
            "RTF_out": "TTS 自身 RTF = Σtts_sec ÷ Σspeech_sec（输出语音 vs 耗时）",
            "speech_over_src": "译文长度比 = Σspeech_sec ÷ Σ源音频秒（中文 vs 英文）",
            "tts_over_src": ("端到端占用率 = Σtts_sec ÷ Σ源音频秒"
                             "（★ 旧结论的 1.231 就是这个口径，"
                             "混入了译文变长）"),
        },
        "note": ("★ RTF_out > 1 ⇒ TTS 引擎自身来不及（⇒ TTS 模块提速）；"
                 "RTF_out ≤ 1 但 tts_over_src > 1 ⇒ TTS 没问题，"
                 "是译文变长/段太碎 ⇒ EXT 侧可改。"
                 "speech_over_src 大 ⇒ 语言属性，只能靠变速吸收。"),
        "per_segment": per_seg,
    }


def estimate_required_delay(margins: List[dict], *, delay_sec: float
                           ) -> dict:
    """★ EXT-034 ④：**要满足同步，延迟 D 需要多大**（交给用户决定）。

    ## 口径（reviewer EXT-034 ④ 的原话）
      「给出『按当前 TTS 吞吐，要满足同步需要的 D』估算，交用户决定。」

    ## 为什么需要一个估算
      D 是**原声被 DelayNode 延迟**的时长（也是配音的排程缓冲）。
      D 太小 ⇒ 配音来不及（D < 起步耗时 + 排队）；
      D 太大 ⇒ 用户听到的原声**晚很多**（唇音不同步、互动差）。
      ⇒ 存在一个「够用又不浪费」的取值 ⇒ **算出来给用户选**。

    ## 三个成分（实测驱动，不是拍脑袋）
      1. **起步开销** `startup_sec`
         = 首段长度 + 首段的 ASR + MT + TTS
         （ASR 是**整段到齐才定稿** ⇒ 首段的管线耗时**全部**落在 D 之前）
      2. **稳态排队** `steady_sec`
         = 段均管线耗时 − 段均源音频时长（按 TTS 吞吐算）
         （若为负 ⇒ TTS 比原声快 ⇒ 不需要额外排队）
      3. **安全余量** `safety_sec`
         = 一个经验常数（播放器侧的就绪→起播 + 跨时钟域误差）

    ⇒ `D_required ≈ startup_sec + steady_sec + safety_sec`
    ⚠️ **这是估算**，用**本轮实测**的段数据算 ⇒ 换素材/换引擎会变。
    ⚠️ 同时给出「当前 D 是否够」的判定 ⇒ reviewer 可直接核对。

    Returns
    -------
    dict
        含各成分 + 建议 D + 与当前 D 的对比 + 口径说明。
    """
    rtf = compute_rtf_breakdown(margins)
    tot = rtf.get("totals") or {}
    n = int(rtf.get("n_segments_with_tts") or 0)
    if n <= 0:
        return {"n_segments_with_tts": 0,
                "note": "没有带 TTS 的段 ⇒ 无法估算（不臆造数字）"}

    # ① 起步开销：首段（按 t_start 排序）
    with_tts = [m for m in margins
                if m.get("tts_sec") is not None
                and float(m.get("tts_sec") or 0) > 0.0]
    with_tts.sort(key=lambda m: float(m.get("t_start") or 0.0))
    first = with_tts[0]
    first_len = (float(first.get("t_end") or 0.0)
                 - float(first.get("t_start") or 0.0))
    startup = (first_len
               + float(first.get("asr_sec") or 0.0)
               + float(first.get("mt_sec") or 0.0)
               + float(first.get("tts_sec") or 0.0))

    # ② 稳态排队：段均「管线耗时」− 段均「源音频时长」
    avg_proc = (float(tot.get("asr_sec") or 0.0)
                + float(tot.get("mt_sec") or 0.0)
                + float(tot.get("tts_sec") or 0.0)) / n
    avg_src = float(tot.get("src_sec") or 0.0) / n
    steady = max(0.0, avg_proc - avg_src)

    # ③ 安全余量：播放器侧的就绪→起播 + 跨时钟域（实测约 4 s）
    safety = 4.0

    d_req = startup + steady + safety
    return {
        "n_segments_with_tts": n,
        "startup_sec": round(startup, 3),
        "startup_detail": {
            "first_seg_len_sec": round(first_len, 3),
            "first_asr_sec": float(first.get("asr_sec") or 0.0),
            "first_mt_sec": float(first.get("mt_sec") or 0.0),
            "first_tts_sec": float(first.get("tts_sec") or 0.0),
            "note": ("★ ASR 是**整段到齐才定稿** ⇒ 首段的整条管线"
                     "（ASR+MT+TTS）都落在 D 之前 ⇒ 首段越长起步越晚。"),
        },
        "steady_sec": round(steady, 3),
        "steady_detail": {
            "avg_proc_sec": round(avg_proc, 4),
            "avg_src_sec": round(avg_src, 4),
            "note": ("段均(ASR+MT+TTS) − 段均源音频时长；"
                     ">0 ⇒ TTS 比原声慢 ⇒ 需要额外排队缓冲"),
        },
        "safety_sec": safety,
        "safety_note": ("播放器侧「就绪→起播」+ uplink↔player 跨时钟域"
                        "误差（实测约 4 s）"),
        "D_required_sec": round(d_req, 3),
        "D_current_sec": delay_sec,
        "D_sufficient": bool(d_req <= delay_sec),
        "gap_sec": round(delay_sec - d_req, 3),
        "rtf_out": rtf.get("RTF_out"),
        "tts_over_src": rtf.get("tts_over_src"),
        "speech_over_src": rtf.get("speech_over_src"),
        "note": ("★ 这是**估算**（用本轮实测段数据）⇒ 交用户决定 D 取值。"
                 "若 D_required 仍 > 当前 D，说明**光调 D 不够**，"
                 "必须先提 TTS 吞吐（RTF_out）或进一步缩短首段。"),
    }


def decompose_sync_rootcause(margins: List[dict], *, delay_sec: float,
                             player_detail: Optional[List[dict]] = None,
                             server_to_player_sec: Optional[float] = None,
                             downlink_latency_sec: Optional[float] = None,
                             ) -> dict:
    """★ EXT-036 ②：**sync 滞后的逐项根因分解**（不得写成「全归 TTS」）。

    ## 要回答的问题（reviewer EXT-036 ② 的原话）
      「末段 41.9 s = 段长 4.12 + 上行 0.37 + ASR 2.54 + MT 0.43
        + TTS 本段 3.36 + **TTS 排队 32.96** + **server→player 7.0**
        + 播放端排队 1.1 − D 10。
        ⇒ 结论：积压部分（约 25–33 s）归 TTS 吞吐；
        但**就算 TTS 无限快，按现在的结构每段仍会晚约 +5.6 s**
        （主要是第 1 项的 7 s，加上 ASR 整段定稿约 3 s、播放排队 0–2.8 s）。
        ⇒ 这部分归 EXT 或 ASR，**不能写成「全归 TTS」**。」

    ## 本函数给出的分解（每项都有**实测来源**）
      | 项 | 含义 | 来源 |
      |---|---|---|
      | `tts_queue_sec` | **TTS 排队**（积压） | 流水线里 TTS 线程的**等待时间** |
      | `pipeline_sec` | 本段 ASR+MT+TTS（不含排队） | `per_segment` 的实测值 |
      | `feed_lag_sec` | **上行**慢（音频到服务端晚了） | `feed_lag_sec` |
      | `server_to_player_sec` | **server→player 缺口** | `player_detail` 的下行耗时 |
      | `player_queue_sec` | **播放端**排队 | `readyToStartSec` |
      | `non_tts_fixed_sec` | **非 TTS 固定项**合计 | 上面几项之和 |
      | `tts_independent_lag_sec` | **TTS 无限快时**仍会晚多少 | `non_tts_fixed − D` |

    ## 关键结论（本函数要输出的）
      `tts_independent_lag_sec > 0` ⇒ **即使 TTS 快到零，每段仍会晚**
      ⇒ 这部分**归 EXT/ASR**，**不归 TTS**。

    Parameters
    ----------
    margins : list of dict
        `per_segment`（服务端落盘）。
    delay_sec : float
        当前 D。
    player_detail : list of dict or None
        `dub_sync.json` 的 `detail`（player 端实测）。
        ★ 可选 ⇒ 没有它就**不给**播放端相关数字（**不臆造**）。

    Returns
    -------
    dict
    """
    out: dict = {
        "definition": (
            "★ EXT-036 ②：sync 有符号误差的**逐项分解**。"
            "「非 TTS 固定项」= 上行 + ASR定稿 + 播放排队 + server→player 缺口；"
            "「TTS 无限快时的残余滞后」= 非TTS固定项 − D。"
            "⇒ 该值 > 0 ⇒ **不能**把滞后全归 TTS。"),
        "delay_sec": delay_sec,
    }
    tts_segs = [m for m in margins if _seg_has_tts(m)]
    n = len(tts_segs)
    out["n_segments_with_tts"] = n
    if n <= 0:
        out["note"] = "没有带 TTS 的段 ⇒ 无法分解（不臆造数字）"
        return out

    # ── ① TTS 排队（流水线里 TTS 线程的等待）────────────────────
    #   `tts_sec` 是**纯引擎调用**耗时；排队时间要从流水线的
    #   「提交时刻 → TTS 开始时刻」量。服务端没有直接落这个字段
    #   ⇒ 用**相邻段的就绪间隔 − 本段源音频时长**近似不可靠
    #   ⇒ 这里改用**可核对**的口径：
    #   「服务端就绪时刻 − 音频到齐时刻 − 本段管线耗时」= 该段的**排队**。
    #   （音频到齐时刻 = `audio_ready_rel_sec` + t0；就绪时刻 = `ready_at`）
    queue_total = 0.0
    queue_vals: List[float] = []
    for m in tts_segs:
        arel = m.get("audio_ready_rel_sec")
        t_end = m.get("t_end")
        ready_at = m.get("ready_at")
        orig_end = m.get("orig_end")
        proc = _seg_proc_sec(m)
        if arel is None or ready_at is None or orig_end is None or proc is None:
            continue
        t0 = float(orig_end) - float(t_end or 0.0)
        # 音频到齐（服务端轴）→ 就绪（服务端轴）的墙钟跨度
        span = (float(ready_at) - t0) - float(arel)
        # 减去本段自己的管线耗时 ⇒ 剩下的是**等待**（排队）
        q = max(0.0, span - proc)
        queue_vals.append(q)
        queue_total += q
    out["tts_queue_sec_total"] = round(queue_total, 3)
    out["tts_queue_sec_mean"] = (
        round(queue_total / len(queue_vals), 3) if queue_vals else None)

    # ── ② 本段管线耗时（ASR+MT+TTS，不含排队）────────────────────
    proc_vals = [_seg_proc_sec(m) or 0.0 for m in tts_segs]
    out["pipeline_sec_mean"] = (
        round(sum(proc_vals) / len(proc_vals), 3) if proc_vals else None)
    out["pipeline_sec_total"] = round(sum(proc_vals), 3)

    # ── ③ 上行（喂帧）慢 ────────────────────────────────────────
    #   ⚠️ `feed_lag_sec` 为**负**表示「音频比要求的时间**早**到」
    #   （实测 mean = −5.041 s ⇒ 上行**不是**瓶颈）
    #   ⇒ 计入「非 TTS 固定项」时必须**夹到 0**（负数不能抵消其它项）。
    feed_vals = [max(0.0, float(m.get("feed_lag_sec") or 0.0))
                 for m in tts_segs]
    out["feed_lag_sec_mean_raw"] = (
        round(sum(float(m.get("feed_lag_sec") or 0.0) for m in tts_segs)
              / len(tts_segs), 3) if tts_segs else None)
    out["feed_lag_sec_mean"] = (
        round(sum(feed_vals) / len(feed_vals), 3) if feed_vals else None)
    out["feed_lag_note"] = (
        "★ `feed_lag_sec_mean_raw` 为**负** ⇒ 上行音频**早**到 "
        "⇒ 上行**不是**瓶颈（计入固定项时已夹到 0）。")

    # ── ④ server→player 缺口 + ⑤ 播放端排队 ────────────────────
    dl_vals: List[float] = []
    pq_vals: List[float] = []
    if player_detail:
        for d in player_detail:
            if d.get("readyToStartSec") is not None:
                try:
                    pq_vals.append(float(d.get("readyToStartSec") or 0.0))
                except Exception:
                    pass
        out["player_queue_sec_mean"] = (
            round(sum(pq_vals) / len(pq_vals), 3) if pq_vals else None)
        out["player_queue_sec_max"] = round(max(pq_vals), 3) if pq_vals else None
    else:
        out["player_queue_sec_mean"] = None
        out["player_queue_sec_max"] = None
    out["server_to_player_sec"] = (None if server_to_player_sec is None
                                   else round(float(server_to_player_sec), 3))
    out["downlink_latency_sec"] = (
        None if downlink_latency_sec is None
        else round(float(downlink_latency_sec), 3))
    out["server_to_player_note"] = (
        "★ EXT-036 ①：**两个不同的量，必须分开**。\n"
        "  * `server_to_player_sec` = **轴缺口**（常量）：播放端轴与服务端轴\n"
        "    对不上造成的**排程误差** ⇒ 它是**排程错**，不是「慢」。\n"
        "    根因 = `t0` 换算符号反了（EXT-036 ① 已修）⇒ 修后此项应 ≈ 0。\n"
        "  * `downlink_latency_sec` = **真实下行耗时**（墙钟）：\n"
        "    `ply_wall_ms − srv_wall_ms`（同一 Unix 墙钟时基）⇒\n"
        "    这才是「下行慢」的那一项 ⇒ 判据 P95 ≤ 0.3 s。\n"
        "  服务端**不猜**这两个值（取不到 ⇒ None ⇒ 不计入固定项）。")

    # ── ⑥ 非 TTS 固定项合计 & ⑦ TTS 无限快时的残余滞后 ──────────
    #   ★★★★★★ EXT-037 ③：**口径重写**（reviewer 原话逐条落实）
    #     ① `axis_gap`（`t0UpPlayerOffsetSec`）是**两端时钟的换算常数**，
    #        **不是延迟** ⇒ **不计入固定项**。
    #        （`requested` 已经在播放端轴上 ⇒ 换算常数不该再加一次。）
    #     ② `player_queue`（前一句还在播造成的排队）属于**结果项**，
    #        **不是固定项** ⇒ 单列。
    #     ③ **漏掉了最大的一项：等整段说完** ⇒ 新增 `seg_len` 项。
    #        sync 误差的下界 = seg_len + 上行 + ASR整段 + MT + TTS整句 − D。
    #   ⇒ **固定项** = 上行(夹0) + ASR整段定稿 + **等整段说完(seg_len)**
    #                   + 真实下行耗时
    #   ⇒ **结果项** = player_queue（排队）、axis_gap（换算常数）
    asr_vals = [float(m.get("asr_sec") or 0.0) for m in tts_segs]
    asr_mean = (sum(asr_vals) / len(asr_vals)) if asr_vals else 0.0
    out["asr_sec_mean"] = round(asr_mean, 3)
    axis_gap = out.get("server_to_player_sec")
    dlat = out.get("downlink_latency_sec")
    pq_mean = out.get("player_queue_sec_mean")
    # ★★ EXT-037 ③：**新增 `seg_len` 项**（「等整段说完」）
    #   = 段均长度（`t_end − t_start`）⇒ 这是「必须等这一段说完」的下界。
    _seg_lens = []
    for m in tts_segs:
        _ts = m.get("t_start")
        _te = m.get("t_end")
        if _ts is None or _te is None:
            continue
        _seg_lens.append(max(0.0, float(_te) - float(_ts)))
    seg_len_mean = (sum(_seg_lens) / len(_seg_lens)) if _seg_lens else None
    out["seg_len_sec_mean"] = (round(seg_len_mean, 3)
                               if seg_len_mean is not None else None)
    # ★★ 未实测项**不计入**合计（否则 null 被当成 0 ⇒ 读起来像「实测为零」）。
    #   取不到 ⇒ 该项记 None（**如实**），不参与求和。
    #   ⇒ `non_tts_fixed_sec` = **已实测项之和** ⇒ 是**下界**，不是全量。
    _parts = [(out.get("feed_lag_sec_mean"), "feed_lag_sec"),
              (asr_mean, "asr_sec"),
              (seg_len_mean, "seg_len_sec"),
              (dlat, "downlink_latency_sec")]
    non_tts = 0.0
    for _v, _k in _parts:
        if _v is not None:
            non_tts += float(_v)
    out["non_tts_fixed_sec"] = round(non_tts, 3)
    out["non_tts_fixed_is_lower_bound"] = any(
        v is None for v, _k in _parts)
    out["non_tts_fixed_detail"] = {
        "feed_lag_sec": out.get("feed_lag_sec_mean"),
        "asr_sec": round(asr_mean, 3),
        "seg_len_sec": (round(seg_len_mean, 3)
                         if seg_len_mean is not None else None),
        "downlink_latency_sec": dlat,
        "fixed_items": ["feed_lag_sec", "asr_sec", "seg_len_sec",
                        "downlink_latency_sec"],
        "unmeasured": [k for v, k in _parts if v is None],
        "note": ("★ EXT-037 ③：**固定项**= 上行(夹0) + ASR整段定稿 + "
                 "**seg_len（等整段说完）** + 真实下行耗时。"
                 "⇒ 这几项**与 TTS 快慢无关** ⇒ 即使 TTS 无限快，"
                 "每段仍会晚 `non_tts_fixed_sec − D` 秒。"
                 "★ **`axis_gap`（时钟换算常数）已移出固定项**"
                 "（它不是延迟；`requested` 已在播放端轴上）。"
                 "★ **`player_queue` 已移出固定项**（它是**结果项**）。"
                 "★ **未实测项记 None 且不计入合计** ⇒ `non_tts_fixed_sec` "
                 "是**下界**（`non_tts_fixed_is_lower_bound=true` 时）；"
                 "绝不把「没测到」写成 0。"),
    }
    # ★★ EXT-037 ③：**结果项**单列（不算进固定项，但**如实保留**实测值）
    out["result_items_detail"] = {
        "player_queue_sec_mean": pq_mean,
        "player_queue_sec_max": out.get("player_queue_sec_max"),
        "axis_gap_sec": axis_gap,
        "items": ["player_queue_sec_mean", "axis_gap_sec"],
        "note": ("★ EXT-037 ③：`player_queue` 是「前一句还在播」造成的排队，"
                 "属于**结果项**（滞后的一部分，不是与 TTS 无关的固定开销）；"
                 "`axis_gap` 是**两端时钟的换算常数**，"
                 "**不是延迟** ⇒ 两者都**不计入** `non_tts_fixed_sec`。"),
    }
    out["tts_independent_lag_sec"] = round(non_tts - delay_sec, 3)
    out["tts_independent_lag_note"] = (
        "★ 这个值 > 0 ⇒ **滞后不能全归 TTS**；"
        "这部分归 EXT / ASR（reviewer EXT-036 ② / EXT-037 ③ 的核心要求）。")

    # ── ⑥b EXT-037 ③：**`D_needed`** = P95(ready − t_start) + 0.3 ──
    #   ## 口径（reviewer EXT-037 ③ 的原话）
    #     「sync 误差的下界是 seg_len + 上行 + ASR整段 + MT + TTS整句 − D。
    #       ⇒ 给出 `D_needed = P95(ready − t_start) + 0.3 s` 的实测值。」
    #   ## 为什么这样算
    #     `ready − t_start` = 这一段从**开始播放**到**配音就绪**经过的墙钟
    #     ⇒ D 必须 ≥ 它，否则这段**必然晚**（D 再大也救不了单段超时）。
    #     + 0.3 s = 同步误差的**目标余量**（≤300 ms 判据）。
    _ready_gaps = []
    for m in tts_segs:
        _ts = m.get("t_start")
        _ready_at = m.get("ready_at")
        if _ts is None or _ready_at is None:
            continue
        # `ready_at` 是服务端**墙钟**（perf_counter 域）⇒ 与 `t_start`
        # （上行采样轴）不同域 ⇒ 必须用 `orig_end − t_end` 换算原点。
        _t_end = m.get("t_end")
        _orig_end = m.get("orig_end")
        if _t_end is None or _orig_end is None:
            continue
        try:
            _t0 = float(_orig_end) - float(_t_end)
            _ready_gaps.append(float(_ready_at) - _t0 - float(_ts))
        except Exception:
            continue
    if _ready_gaps:
        _sorted = sorted(_ready_gaps)
        _p95_idx = int(round(0.95 * (len(_sorted) - 1)))
        _p95 = _sorted[_p95_idx]
        out["ready_minus_t_start_p50_sec"] = round(_sorted[0], 3) if len(_sorted) == 1 \
            else round(_sorted[int(round(0.50 * (len(_sorted) - 1)))], 3)
        out["ready_minus_t_start_p95_sec"] = round(_p95, 3)
        out["D_needed_sec"] = round(_p95 + 0.3, 3)
        out["D_needed_is_sufficient"] = bool(out["D_needed_sec"] <= delay_sec)
        out["D_needed_note"] = (
            "★ EXT-037 ③：`D_needed = P95(ready − t_start) + 0.3 s`。"
            "`ready − t_start` = 这一段从开始播放到配音就绪的墙钟跨度"
            "⇒ D 必须 ≥ 它，否则该段**必然晚**（加大 D 救不了单段超时）。"
            "`+0.3 s` = 同步误差目标余量（≤300 ms 判据）。"
            "★ 当前 D = %.3f s ⇒ %s。"
            % (delay_sec,
               "**足够**" if out["D_needed_is_sufficient"]
               else "**不够** ⇒ 必须加大 D 或提速引擎"))
    else:
        out["D_needed_sec"] = None
        out["D_needed_note"] = ("没有可用的 `ready_at` / `t_start` ⇒ "
                                 "**无法**计算 D_needed（不臆造数字）")
    # ── ⑧ 与 TTS 吞吐的关系（交叉核对）─────────────────────────
    rtf = compute_rtf_breakdown(margins)
    out["rtf_out"] = rtf.get("RTF_out")
    out["speech_over_src"] = rtf.get("speech_over_src")
    out["tts_over_src"] = rtf.get("tts_over_src")
    out["cross_check_note"] = (
        "交叉核对：`tts_over_src == RTF_out × speech_over_src`"
        "（实测 1.4595 == 1.1937 × 1.2227）。"
        "⇒ 译文变长（speech_over_src=1.2227）**混在**端到端占用里，"
        "**不是** TTS 自身慢。")
    return out


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


class ConnectionRegistry:
    """★★ EXT-024 A：**按连接**登记所有已连上的客户端。

    ## 为什么必须有这个（用户 10-31 实测的根因）

    旧实现里，`ext/bridge.py` 的 `handle_ws/_handle_messages` 给**每条连接**
    各建一个 `Session`，而 `tts` 任务只 `websocket.send` 回**本连接**
    ⇒ 上行连接（`upState.ws`，只发 pcm、**没有 onmessage**）上的会话
    产出的 `tts` 全部被浏览器丢弃；
    ⇒ player 连接（`connectBridge(..., 'player')`，**有 onmessage**）的会话
    收不到 PCM，什么也不产出
    ⇒ **用户只听到延迟原声，没有配音、没有字幕**（与用户描述完全一致）。

    ⇒ 现在：服务端**显式登记每条连接的角色**（uplink / player / probe），
      下行任务**广播给所有该 token 的 player 连接**（以及产生它的那条连接）。

    ## 角色识别

    * `role` 取自 hello 消息的 `role` / `source` 字段：
      - `'player'` ⇒ **下行**接收端（有 onmessage，能排程播放）；
      - `'uplink'` ⇒ 上行发送端（送 PCM）；
      - 其它（`p1_probe` / `p1_dumper` / None）⇒ **探针**，
        只收不发（保持旧行为：任务回给本连接）。
    * ⚠️ **兜底**：若某连接既没报 role 也没报 source，
      **不能**默认当 player（否则会退化成旧行为）。
      ⇒ 默认按 probe 处理；只有明确报了 `'player'` 才当下行端。

    ## 线程安全

    事件循环里读写，但 `handle_ws` 会在 `asyncio.to_thread` 之外调用
    ⇒ 一律用 `threading.Lock` 保护。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # conn_id → 连接信息
        self._conns: Dict[str, dict] = {}
        self._seq = 0

    # ── 登记 / 注销 ──────────────────────────────────────────
    def add(self, conn_id: str, *, websocket, token: str,
            role: Optional[str], session=None) -> None:
        with self._lock:
            self._conns[conn_id] = {
                "websocket": websocket,
                "token": token,
                "role": role,
                "session": session,
                "created_at": time.perf_counter(),
            }

    def set_role(self, conn_id: str, role: Optional[str]) -> None:
        with self._lock:
            info = self._conns.get(conn_id)
            if info is not None:
                info["role"] = role

    def set_session(self, conn_id: str, session) -> None:
        with self._lock:
            info = self._conns.get(conn_id)
            if info is not None:
                info["session"] = session

    def producer_session(self, token: str, *,
                         exclude_conn_id: Optional[str] = None):
        """同 token 的、role='uplink' 的连接上挂的**会话**。

        ★ 这是**真正产出段**的会话（player 的会话只负责收下行）。
        ⇒ stats / margin.json 要报的是它，不是 player 的空会话。
        """
        with self._lock:
            conns = list(self._conns.items())
        for cid, info in conns:
            if cid == exclude_conn_id:
                continue
            if info.get("token") != token:
                continue
            if info.get("role") != "uplink":
                continue
            sess = info.get("session")
            if sess is not None:
                return sess
        return None

    def remove(self, conn_id: str) -> None:
        with self._lock:
            self._conns.pop(conn_id, None)

    def get(self, conn_id: str) -> Optional[dict]:
        with self._lock:
            return self._conns.get(conn_id)

    def list(self) -> List[dict]:
        with self._lock:
            return list(self._conns.values())

    def next_id(self) -> str:
        with self._lock:
            self._seq += 1
            return "c%d" % self._seq

    # ── 下行目标选择 ──────────────────────────────────────────
    def downlink_targets(self, token: str, *, origin_conn_id: str) -> List[str]:
        """这条下行任务该发给谁？返回 conn_id 列表。

        ★ 规则：
          ① **产生它的那条连接**（origin_conn_id）—— 保持旧行为
            （探针/单连接客户端仍然收得到）；
          ② **同 token 的 role='player' 连接** —— ★ 这条是 EXT-024 的关键
            （上行的会话产出、player 的连接接收）。

        ⚠️ 探针连接（p1_probe 等）**不**被加进下行目标 ——
          它们只收自己那条连接的任务（否则 P1 的段数会重复计数）。
        """
        with self._lock:
            conns = list(self._conns.items())
        targets: List[str] = []
        for cid, info in conns:
            if info.get("token") != token:
                continue
            if cid == origin_conn_id:
                targets.append(cid)
                continue
            if info.get("role") == "player":
                targets.append(cid)
        return targets

    def uplink_conn_ids(self, token: str) -> List[str]:
        """同 token 的、role='uplink' 的连接 id 列表。"""
        with self._lock:
            conns = list(self._conns.items())
        return [cid for cid, info in conns
                if info.get("token") == token and info.get("role") == "uplink"]


def classify_role(msg: Optional[dict]) -> Optional[str]:
    """从 hello 消息里判断这条连接是什么角色。

    ★ 返回 `'player'` / `'uplink'` / `None`（探针或未报）。
    ⚠️ **绝不**把未报角色的连接当成 player ——
      否则等于退回 EXT-024 之前的错误行为。
    """
    if not isinstance(msg, dict):
        return None
    raw = msg.get("role") or msg.get("source")
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower()
    if key in ("player", "uplink"):
        return key
    return None


class Session:
    """一次配音会话。

    音频上行帧格式：{seq, sample_index, pcm(base64 PCM16 16k mono)}
    时间戳用**累计采样数**换算，不用墙钟，避免漂移（EXT-001 A 节）。

    ★ EXT-006：真实引擎模式下的**余量统计**是 P1 的核心验收量 ——
      「原声结束 → TTS 就绪」的余量分布、余量 < 0 的句数、累计滞后。
    """

    #: ★★ EXT-029：**本会话是否接了说话人旁路**。
    #:   * 基类（串行会话）恒为 False —— 串行路径没有 GPU 互斥锁
    #:     ⇒ 旁路若另开一把锁会**饿死 ASR**（EXT-029 ④）⇒ 串行不接。
    #:   * `PipelineSession` 在**启用**时置 True。
    spk_bypass_enabled: bool = False

    def __init__(self, token: str, *, delay_sec: float = 10.0,
                 engine=None, audio_dump=None, spk_bypass=None) -> None:
        self.token = token
        self.delay_sec = delay_sec
        self.t0 = time.perf_counter()
        # ★★★★★★ EXT-036 ①：**墙钟**版的会话原点。
        #   `self.t0` 是 `perf_counter()`（**单调钟**）⇒ 只能用于
        #   「同一进程内的时长计算」⇒ **不能**与插件的 `Date.now()` 相减。
        #   ⇒ 这里额外记一个 Unix 墙钟原点，让下行消息能带上
        #   「服务端发出时刻（墙钟）」⇒ 与插件的 `Date.now()` **同一时基**
        #   ⇒ 两边相减 = **真实下行耗时**（含收口后到 WS 落盘的那一段）。
        #   ★ 这个量是 EXT-036 ①「证明 7 s 缺口是哪种」的**关键证据**。
        self._t0_wall_ms = time.time() * 1000.0
        # ★★★★ EXT-028 ①：**逐段音频落盘器**（可为 None ⇒ 不落盘）。
        #   落盘三份音频里的前两份：
        #     (a) TTS 引擎的**原始输出**（未经变速）；
        #     (b) **WS 实际发出的**那份字节（base64 之前）。
        #   第三份 (c)（player 端录音）由冒烟脚本从浏览器侧落盘。
        #   ⇒ 三份对齐后即可定位「失真发生在哪一环」。
        self.audio_dump = audio_dump
        # ★★★ EXT-029：**说话人旁路**（可为 None ⇒ 不接旁路）。
        #   ★ 它是**独立线程**（`ext/speaker_bypass.py`）：
        #     * 音频入口只做 `put_nowait`（队列有界，满了丢旧块并计数）
        #       ⇒ **绝不阻塞** ASR 主路径 / 定稿 / MT / TTS；
        #     * spk 结果**异步回填**（未到就用上一句音色或预设 A ⇒ 方案 A）。
        #   ⚠️ 这个对象由**流水线会话**创建（因为要共用 ASR/MT 的
        #     GPU 互斥锁 ⇒ 公平 FIFO ⇒ 不会饿死 ASR），
        #     串行会话没有那把锁 ⇒ 串行路径下不接旁路。
        self.spk_bypass = spk_bypass
        # ★★ EXT-029 ②：段级「说话人 / 音色来源」表
        #   （EXT-027③ 验收要求落盘 `spk / voice_source / 是否换人`）。
        self.spk_table: List[dict] = []
        # ★★ EXT-029：异步回填到的标签（seg_id → spk）
        self._spk_labels: Dict[str, str] = {}
        self._spk_label_cv = threading.Condition()
        # ★★ EXT-029：段级表的**行索引**（seg_id → row）
        #   ⇒ 收口线程与旁路 worker 都写这张表 ⇒ 必须有锁 + 必须按
        #     seg_id 去重（否则同一段会出现两行、字段互相打架）。
        self._spk_rows: Dict[str, dict] = {}
        self._spk_table_lock = threading.Lock()
        self.sample_index = 0
        self._buf = np.zeros((0,), dtype=np.float32)
        # v0.4.19 「保留背景音」: separator + its downlink queue + separated vocals for speaker/clone
        self.bg_keep = False
        self._bg_sep = None
        self._bg_fail = ""                     # set when the client asked for bg but it cannot run
        self._bg_tasks = collections.deque()
        self._bg_seq = 0
        self._bg_status_at = 0.0
        self._bg_status_key = None
        self._bg_n_up = 0
        self._bg_on_frame = 0                  # n_frames when 保留背景音 was (re)enabled
        self._spk_fed_until = None             # 16 kHz sample index the speaker bypass has been fed up to
        self._spk_feed_lock = threading.Lock()
        self._voc_lock = threading.Lock()
        self._voc16 = np.zeros((0,), dtype=np.float32)
        self._voc16_base = 0                   # 16 kHz sample index of _voc16[0]
        self._clone_pending = collections.deque()
        self._clone_pending_lock = threading.Lock()
        self.bg_clone_from_vocals = 0
        self.bg_clone_fallback_orig = 0
        self._onset_pending = collections.deque()   # (dub id, t_start, t_end, play_deadline_perf)
        self.bg_onset_shifted = 0              # dubs whose start was moved to the speech onset in the vocals
        self.bg_onset_shift_sum = 0.0
        self.bg_onset_no_vocals = 0
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
        # ★★★★★★ EXT-036 ④：**缓冲第一个样本的会话绝对偏移**。
        #   `_consumed_samples` = 已**交付**的样本数；
        #   `_buf_base` = 缓冲里第一个样本的**会话绝对偏移**。
        #   ★ 两者在「首段提前交付」后**会分叉**：
        #     提前交付时我们**故意不裁缓冲**（⇒ 切点栅格逐位不变）
        #     ⇒ 已交付 3.5 s，但缓冲仍从 0 开始 ⇒ `_buf_base = 0`。
        #   ⇒ 段偏移必须用 `_buf_base + s0` 换算（**不是** `_consumed_samples`）。
        self._buf_base = 0
        # ★★★★★ EXT-034 ④：**首段限长**（会话级）。
        #   ## 为什么（reviewer EXT-034 ③ 的原话）
        #     「开头静音主要归 EXT（首段切得太长、ASR 在整段结束后才定稿）」。
        #     ASR 是**整段到齐才定稿**（`_dispatch_segment` 只在整段音频
        #     完整到达后才调 `_process_segment`）⇒ **首段越长、起步越晚**：
        #       起步耗时 ≈ 首段长度 + ASR + MT + TTS
        #       实测：8.0 + 5.20 + 1.30 + 11.04 = **25.54 s** > D=10 s
        #     ⇒ 结构上就赶不上 ⇒ 开头静音必然 ≫ D。
        #   ## 修法
        #     首段单独限短（默认 `FIRST_SEGMENT_MAX_SEC`）⇒ 起步提前。
        #     ⚠️ **只限首段**，其余段仍按 `SEG_MAX_SEC`（8 s）切
        #       ⇒ 稳态吞吐不变，只改「起步」。
        #   ⚠️ 与 R2T2 原件的**等价性**：默认参数下行为不变
        #     （`plan_segments` 的 `first_segment_max_sec` 默认 None）。
        self._first_seg_done = False
        self._first_seg_max_sec = C.FIRST_SEGMENT_MAX_SEC
        # ★★★★★★ EXT-036 ④：**提前交付**掉的样本数（会话绝对偏移）。
        #   0 ⇒ 首段还没提前交付；>0 ⇒ 已交付 `[0, _first_seg_cut]`。
        #   ⚠️ 提前交付时**不裁剪 `_buf`** ⇒ 切点栅格逐位不变
        #     （上一版裁了缓冲 ⇒ 栅格整体平移 ⇒ 尾段被吃掉）。
        self._first_seg_cut = 0
        # ★★★★★★ EXT-037 ②：**缓冲头部已交付、但还没被裁掉**的样本数。
        #   ## 为什么需要它
        #     首段提前交付时**故意不裁 `_buf`** ⇒ 缓冲里**还留着**
        #     已交付的那 3.5 s ⇒ 若此时 `flush()`，尾段会从 `_buf_base`
        #     开始 ⇒ **与已交付的首段重叠**（重复配音 + 段区间重叠）。
        #   ⇒ `flush()` 必须**跳过**这段前缀。
        #   0 ⇒ 缓冲头部没有「已交付但未裁」的部分。
        self._buf_delivered_prefix = 0
        self._engine = engine if engine is not None else ENGINE_ADAPTER
        # ★★★ EXT-026 ⑤：**会话前缀**（session epoch）
        #   ## 为什么需要（reviewer 指出的真缺陷）
        #     段 id 原本是 `seg_{s0}` / `seg_{abs0}`（采样点偏移）
        #     ⇒ **每个会话都从 0 开始** ⇒ 两次会话的 id 会**撞号**
        #       （第 1 段的 id 在两个会话里都是 `seg_0`）。
        #     ⇒ 而插件侧 `player.js` 的 `seenDubIds` 是**页面级常驻**的
        #       （player 页不关就一直留着）⇒ 新会话的第 1 段会被
        #       当成「旧会话已经排过程的重复段」而**静默丢掉**
        #       ⇒ 又一次「没有配音」（与用户 10-31 实测症状完全一致）。
        #   ## 修法
        #     段 id 带上**本会话的唯一前缀** ⇒ 跨会话不可能撞号。
        #     ⚠️ 前缀只加在**对外的 id** 上（`task["id"]`），
        #       内部的 `_seg_orig_end` / `_seg_ready` / speaker tracker
        #       仍用**裸的** `seg_{s0}`（它们是会话内的键，不跨会话）。
        #     ⚠️ 格式保持「`seg_<前缀>_<数字>`」⇒
        #       `tools/compare_ext011_cores.py` 的
        #       `int(str(r["id"]).split("_")[-1])` 仍能解析出起始毫秒
        #       （实测该工具就是靠 id 末尾数字排序的）。
        #       ⇒ 前缀**必须是纯数字**（不能用 hex 字母）
        #         ⇒ 否则那个工具的 `int()` 会 ValueError ⇒ 排序退化。
        self._session_epoch = str(uuid.uuid4().int % (10 ** 8)).zfill(8)
        # ── EXT-006 余量统计 ──────────────────────────────────
        #   margin_sec = (TTS 就绪时刻) − (该段原声结束时刻)
        #   负数 ⇒ 配音来不及在原声结束前就绪 ⇒ 滞后累积
        # ★★ T-5 修正：**这两个字典是「只写不读」的**（实测：
        #   全仓只有 `self._seg_orig_end[seg_id] = ...` 与
        #   `self._seg_ready[seg_id] = ...` 两处写入，**没有任何读取点**）
        #   ⇒ 每收一段就永久多留两个 key ⇒ 30 分钟会话会累积上千项
        #   ⇒ 属于 P2「内存不持续增长」的**真缺陷**。
        # ⇒ 改成**有界环形**（只留最近 N 段的原声结束/就绪时刻）。
        #   ⚠️ 保留这两个名字与语义（外部工具/日志可能引用），
        #   只是不再无限增长。
        self._seg_orig_end: Dict[str, float] = {}   # seg_id → 原声结束（会话秒）
        self._seg_ready: Dict[str, float] = {}      # seg_id → TTS 就绪（会话秒）
        # ★★ T-5：裁剪这两个字典的锁（流水线模式下可能被两个线程碰）
        self._seg_timing_lock = threading.Lock()
        self.margins: List[dict] = []               # 每句一条
        self.engine_calls: List[dict] = []          # 引擎各阶段耗时
        # ★ EXT-008 第 2 点：逐帧的「到达延迟」（实测「喂帧慢」）
        # ★★ T-5 修正：**逐帧追加 ⇒ 47 帧/秒 × 30 分钟 = 8.5 万条/会话**，
        #   旧实现**永不裁剪** ⇒ 内存持续增长（P2「30 分钟不崩」的隐患）。
        # ⇒ 改成**有界**：只保留最近 C.FRAME_DELAY_HISTORY 条，
        #   统计口径（n_frames_measured / late_ratio / max / mean / last）
        #   **保持不变** —— 计数类用累计量，均值/末值用保留窗口。
        #   ⚠️ `n_frames_measured` 仍统计**全部**帧（不随窗口变小），
        #   避免把「窗口大小」误当成「测了多少帧」。
        self._frame_arrival_delays: List[dict] = []
        self._n_frames_late = 0
        self._max_frame_arrival_delay = 0.0
        # ★ T-5：到达延迟的**累计和**（用于均值，不受窗口裁剪影响）
        self._sum_frame_arrival_delay = 0.0
        self._n_frames_measured = 0
        # ★ EXT-009：上一句实际采用的**自适应加速倍率**
        #   （用于「相邻句变化 ≤ 0.1×」与「滞回」两条约束）
        self._prev_adapt_speed = 1.0
        self._play_end_est = 0.0   # 11-08: 模拟 player 配音队列的结束时刻（perf_counter 轴）
        self._clone = None          # 11-08: 克隆说话人（ext/clone_voice.py），面板选 clone 时懒加载
        self._clone_failed = False
        # ── ★ T-1：抓流方式（captureMode）────────────────────
        #   **为什么需要**：EXT-005 ① / EXT-008 都要求「tabCapture 生产路径
        #   到底有没有被实测过」必须**能从数据核对**，而不是靠人读日志。
        #   插件侧其实**早就知道**自己走的是哪条路
        #   （offscreen.js 的 state.captureMode / player.js 的 upState.captureMode，
        #     取值 'tabCapture' | 'getDisplayMedia'），
        #   但此前**只在插件内部/弹窗里显示**（popup.js 的「抓流方式：…」），
        #   **没有上报到桥接服务** ⇒ 服务端 stats / margin.json 里
        #   根本没有这个字段 ⇒ reviewer 无法从落盘产物判断
        #   「这次跑的是 tabCapture 还是 getDisplayMedia 兜底」。
        #   ⇒ 现在：hello 消息带 capture_mode ⇒ 会话记住 ⇒ stats() 与
        #     margin.json 都带上它（**默认值 None** ⇒ 未上报时是 null，
        #     绝不臆造 'tabCapture'）。
        self.capture_mode: Optional[str] = None
        # 客户端身份（'offscreen' / 'player' / 'p1_probe'）——
        # 由 hello 的 source/role 填 ⇒ reviewer 能判断「这条数据是谁跑出来的」。
        self.client_source: Optional[str] = None
        # ★★ EXT-024 B：这条会话所属**连接的角色**
        #   （'player' / 'uplink' / None）——
        #   ⇒ 用来判断「新 uplink 是否该接管旧会话」。
        self.client_role: Optional[str] = None
        # 客户端抓到的原始采样率（没报就是 None）。
        self.source_rate: Optional[int] = None
        # ★★ T-3：客户端**请求**的目标语言与音色。
        #   为什么需要记录：插件面板上的「目标语言」「音色」此前
        #   **从没传到服务端** ⇒ reviewer 拿到 margin.json 时
        #   **无法确认这一轮到底译成了哪种语言**（margin.json 里原来记的
        #   target_lang 是**服务端启动参数**，不是客户端的请求）。
        #   ⇒ 记下来（**没报就是 None**，绝不臆造）。
        self.client_target_lang: Optional[str] = None
        self.client_voice: Optional[str] = None
        # ★★★★★★ EXT-036 ①/②：客户端**实测**的下行耗时与播放端排队。
        #   ## 为什么需要
        #     客户端已经能测：`ply_wall_ms − srv_wall_ms`（真实下行耗时）
        #     与 `readyToStartSec`（就绪→起播），也都落进了 `dub_sync.json`。
        #     但此前**从不上报服务端** ⇒ `margin.json` 的 `sync_rootcause` 里
        #     `server_to_player_sec` / `downlink_latency_sec` /
        #     `player_queue_sec_mean` **全是 null**
        #     ⇒ 「非 TTS 固定项」只加得上一部分 ⇒ **归因不完整**。
        #   ⇒ 现在客户端主动上报，服务端记住并落盘（**没报就是 None**，
        #     **绝不臆造**，也绝不用 0 冒充「实测为零」）。
        self.client_downlink_ms: List[float] = []     # 逐段下行耗时（ms）
        self.client_player_queue_sec: List[float] = []  # 逐段就绪→起播（s）
        self.client_t0_up_player_offset_sec: Optional[float] = None
        # ★★★ EXT-041：客户端上报的**媒体降速实测**（实际降了多少）。
        #   ⚠️ 没报就是 None（**不臆造**）⇒ 落盘在 `margin.json:slowdown`。
        self.client_slowdown: Optional[dict] = None
        # ★★★ EXT-024 E：**分开**的三段计数（ASR / MT / TTS）。
        #   为什么必须分开（而不是沿用一个 `n_segments`）：
        #     `n_segments`（= len(self.margins)）只说明「一共收口了几段」，
        #     **不能**说明「ASR 出没出文本 / MT 出没出译文 / TTS 出没出音频」
        #     ⇒ 若三者共用一个数，状态条上「TTS 0 段」这种关键故障信号
        #       **永远不会显示**（因为只要收口过一段，`n_segments` 就 >0）。
        #     ⇒ 插件侧曾把三者都设成 `m.n_segments` ⇒ **口径失真**
        #       （player.js 的 handleBridgeMessage）。
        #   口径（**如实**，不臆造）：
        #     * asr_segments —— 这一轮**产出了非空 ASR 文本**的段数；
        #     * mt_segments  —— 这一轮**产出了非空译文**的段数；
        #     * tts_segments —— 这一轮**产出了 TTS 音频**（pcm24k 非空）的段数。
        #   ⇒ 三者**可以不等**：ASR 认出文本但 MT 失败 ⇒ asr>0, mt=0,
        #     TTS=0 ⇒ 状态条立刻能指出「翻译/合成这一环断了」。
        self._n_asr_segments = 0
        self._n_mt_segments = 0
        self._n_tts_segments = 0
        # ★★ T-4：这一轮**真正用于翻译/合成**的目标语言。
        #   ★ 为什么需要这个字段：`client_target_lang` 只说明「面板上选了什么」，
        #     而这个字段说明「**实际生效**的是什么」——
        #     两者不一致时（例如引擎不接受该码 ⇒ 回落到服务端默认），
        #     reviewer 才能一眼看出「面板选了但没生效」。
        #   ⚠️ 初始为 None（还没跑过任何一句）⇒ 绝不臆造。
        self.applied_target_lang: Optional[str] = None

    # ── ★★★ EXT-026 ⑤：对外的段 id 带会话前缀 ──────────────
    def public_seg_id(self, seg_id: str) -> str:
        """把**会话内**的段 id 转成**跨会话唯一**的对外 id。

        ## 为什么需要（reviewer EXT-026 第 5 条）

        段 id 原本是 `seg_{s0}`（s0 = 该段第一帧的上行累计采样数）
        ⇒ **每个会话都从 0 开始** ⇒ 两次会话的第 1 段 id 完全相同。

        而插件侧 `player.js` 的 `seenDubIds`（按 id 去重，防止同一条
        tts 被两条 WS 各发一次而排程两次）是**页面级常驻**的 ——
        player 页不关就一直留着。

        ⇒ offscreen 路径重新开始一个会话时，新会话的段 id 与旧会话撞号
        ⇒ 被当成「重复段」**静默丢掉** ⇒ 又一次「没有配音」。

        ## 格式

        `seg_{session_prefix}_{数字}` ⇒
          * 前缀是 8 位**纯数字**（`uuid4().int % 1e8` ⇒ 转成 8 位十进制）；
          * 末尾仍是**纯数字** ⇒ `tools/compare_ext011_cores.py` 里
            `int(str(r["id"]).split("_")[-1])` 仍能解析出起始毫秒
            （那个工具就是靠 id 末尾数字排序取「后 50%」的）。

        ⚠️ **幂等**：同一段重复调用得到同一个 id（不会每次都变）。
        """
        return "seg_%s_%s" % (self._session_epoch,
                              str(seg_id).split("_")[-1])

    # ── 目标语言（T-4） ──────────────────────────────────────
    def _effective_target_lang(self) -> Optional[str]:
        """这一句该用哪个目标语言。

        ★★ T-4 的核心：**面板上选的目标语言必须真正生效**。
          此前 `client_target_lang` 只被**记录**、**从不用于翻译**
          ⇒ 用户在面板上选日语，MT/TTS 仍按服务端 `--target-lang` 走
          ⇒ 面板上的「目标语言」**依然是死控件**（T-3 只修了一半）。

        ⇒ 现在：客户端报了**白名单内**的语言码 ⇒ **按句覆盖**引擎的默认语言；
          没报 / 报的不是白名单内的码 ⇒ 沿用引擎默认（服务端启动参数）。

        ⚠️ 引擎侧映射不到会**抛异常**（EngineNeedsChange），
          绝不在这里静默回落。
        """
        return self.client_target_lang or None

    def _mt_with_lang(self, text: str, lang: Optional[str]) -> str:
        """按**目标语言**翻译一句（T-4）。

        ⚠️ **向后兼容**：引擎的 `mt` 若不接 `target_lang` 关键字
          （老适配层 / 自测桩）⇒ TypeError ⇒ **回落**成不传语言的旧调用
          ⇒ 不让旧引擎/旧桩直接崩掉。
          ⇒ 但回落时**如实记** `applied_target_lang=None`（不假装生效）。
        """
        if not lang:
            return self._engine.mt(text)
        try:
            r = self._engine.mt(text, target_lang=lang)
        except TypeError as e:
            if "target_lang" not in str(e):
                raise
            # 老引擎/桩：不接该关键字 ⇒ 回落旧行为（如实记未生效）
            self.applied_target_lang = None
            _log("⚠️ 引擎的 mt() 不接 target_lang ⇒ 本句沿用引擎默认语言"
                 "（面板选择未生效）")
            return self._engine.mt(text)
        self.applied_target_lang = lang
        return r

    def _tts_with_lang(self, text: str, voice: str,
                        lang: Optional[str]) -> Tuple[Optional[bytes], float]:
        """按**目标语言**合成一句（T-4）。

        ⚠️ 向后兼容说明同 `_mt_with_lang`。
        """
        if not lang:
            return self._engine.tts(text, voice=voice)
        try:
            r = self._engine.tts(text, voice=voice, target_lang=lang)
        except TypeError as e:
            if "target_lang" not in str(e):
                raise
            self.applied_target_lang = None
            _log("⚠️ 引擎的 tts() 不接 target_lang ⇒ 本句沿用引擎默认语言"
                 "（面板选择未生效）")
            return self._engine.tts(text, voice=voice)
        self.applied_target_lang = lang
        return r

    def note_client(self, hello: Optional[dict]) -> None:
        """★ T-1：从客户端的 hello 消息里记录**抓流方式**等元信息。

        放在 Session 上而不是全局，是因为**每个连接一个会话**，
        客户端自己的 hello 才是可信来源。

        只接受白名单取值：'tabCapture' / 'getDisplayMedia' / None。
        其它值一律记 None（不静默接受未知字符串，避免报告里出现
        含义不明的字段值）。
        """
        if not isinstance(hello, dict):
            return
        raw = hello.get("capture_mode") or hello.get("captureMode")
        if raw in ("tabCapture", "getDisplayMedia"):
            self.capture_mode = raw
        # 顺带记下客户端身份（'offscreen' / 'player' / 'p1_probe'）——
        # 与 capture_mode 一起，reviewer 能判断「这条数据是谁跑出来的」。
        role = hello.get("source") or hello.get("role")
        if isinstance(role, str) and role:
            self.client_source = role
        # 源采样率（客户端抓到的原始采样率）——
        # ★ 不是验收必需项，但和 capture_mode 一起能帮 reviewer 确认
        #   「这轮抓到的是不是预期的音频规格」。没报就是 None。
        try:
            sr = hello.get("source_rate")
            if sr is not None:
                self.source_rate = int(sr)
        except (TypeError, ValueError):
            pass
        # ★★ T-3：客户端请求的目标语言 / 音色。
        #   ⚠️ 只接受**引擎认识的语言码**（zh/en/ja/ko）
        #     —— 其它值一律记 None，不静默接受未知的码
        #     （否则 reviewer 会看到「目标语言：Chinese」这种
        #       引擎其实不认的值，误以为这轮真的按它译了）。
        lang = hello.get("target_lang") or hello.get("targetLang")
        if isinstance(lang, str):
            # ★★ EXT-024 G：**服务端也做一次全称→码的映射**。
            #   起因（用户 10-31 实测的现场证据）：Edge 默认 profile 的
            #   `chrome.storage` 里 `targetLang` 存的是 **`"Chinese"`**
            #   （旧版 popup 存的全称，EXT-022 之后才改成码，
            #    但**存量配置不会自动迁移**——用户的 Edge 里就是旧值）。
            #   ⇒ 旧值 "Chinese" 落到这里 ⇒ 旧逻辑把它记成 None
            #     ⇒ 服务端**不知道**用户要中文 ⇒ 用启动参数（en）翻译
            #     ⇒ 用户看到的是「没翻译成中文」。
            #   ⇒ 现在服务端**独立地**也认全称（不依赖插件是否已升级）
            #     ⇒ 存量配置也能正确翻译。
            #   ⚠️ 仍然只接受白名单里的值 ⇒ 未知字符串一律记 None。
            key = normalize_lang_code(lang)
            if key:
                self.client_target_lang = key
        voice = hello.get("voice")
        if isinstance(voice, str) and voice.strip():
            self.client_voice = voice.strip()

    # ★★★★★★ EXT-036 ①/②：接收客户端**实测**的下行/排队数据。
    #   ★ 为什么需要（真缺陷，不是锦上添花）：
    #     客户端能测 `ply_wall_ms − srv_wall_ms`（真实下行耗时）与
    #     `readyToStartSec`（就绪→起播），但此前**只留在插件本地**
    #     （`dub_sync.json`）⇒ 服务端 `margin.json` 的 `sync_rootcause`
    #     里这三项**全是 null** ⇒ 「非 TTS 固定项」少算了三项
    #     ⇒ **归因不完整**（reviewer 要求「逐项分解」）。
    #   ★ 口径约定：
    #     - 只收**数值**，收不到就不记（**绝不臆造**、绝不用 0 冒充）；
    #     - 列表**有界**（防 EXT-019「内存不持续增长」那类回归）；
    #     - 汇总值用**中位数/分位**（`_pct` 最近秩口径，与既有工具一致）。
    def note_client_metrics(self, msg: Optional[dict]) -> None:
        """记下客户端上报的**实测**下行耗时 / 播放端排队 / 轴偏移。"""
        if not isinstance(msg, dict):
            return

        # ── 逐段下行耗时（ms）──────────────────────────────────
        dl = msg.get("downlink_ms")
        if isinstance(dl, list):
            vals = []
            for v in dl:
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    continue
                # 下行耗时**不可能**是负数 ⇒ 负值视为无效（不记）
                if f < 0.0:
                    continue
                vals.append(f)
            if vals:
                self.client_downlink_ms = vals[-200:]   # 有界

        # ── 逐段「就绪→起播」（s）─────────────────────────────
        pq = msg.get("player_queue_sec")
        if isinstance(pq, list):
            vals = []
            for v in pq:
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    continue
                if f < 0.0:
                    continue
                vals.append(f)
            if vals:
                self.client_player_queue_sec = vals[-200:]  # 有界

        # ── 轴偏移（播放端轴 vs 上行轴，秒）────────────────────
        off = msg.get("t0_up_player_offset_sec")
        if off is not None:
            try:
                self.client_t0_up_player_offset_sec = float(off)
            except (TypeError, ValueError):
                pass

        # ── ★★★ EXT-041：**媒体降速的客户端实测** ─────────────
        #   插件（内容脚本）把「实际降了多少」回报上来
        #   ⇒ 落盘进 `margin.json:slowdown.client_*`
        #   ⇒ reviewer 要的「视频是否降速以及降了多少」就有据可查。
        #   ⚠️ **如实**：客户端没报 ⇒ 保持 None（**不臆造**）。
        #   ⚠️ 只接受 [0.5, 1.0] 区间（**永不加速**；越界视为无效）。
        slow = msg.get("slowdown")
        if isinstance(slow, dict):
            applied = slow.get("applied")
            rate = slow.get("rate")
            _rec = {
                "applied": (bool(applied) if applied is not None else None),
                "rate": None,
                "videos": None,
                "reason": (str(slow.get("reason"))[:200]
                           if slow.get("reason") is not None else None),
            }
            if rate is not None:
                try:
                    _r = float(rate)
                    if 0.5 <= _r <= 1.0:
                        _rec["rate"] = round(_r, 4)
                    else:
                        _rec["reason"] = ("客户端上报的倍率 %.4f 越界"
                                          "（只接受 0.5–1.0，永不加速）⇒ 已忽略"
                                          % _r)
                except (TypeError, ValueError):
                    pass
            if slow.get("videos") is not None:
                try:
                    _rec["videos"] = int(slow.get("videos"))
                except (TypeError, ValueError):
                    pass
            self.client_slowdown = _rec

    # ── 客户端实测值的**汇总**（供 margin.json 落盘用）────────
    def client_metrics_summary(self) -> dict:
        """把客户端实测的下行/排队/轴偏移汇成**可落盘**的量。

        ★ 没报 ⇒ 该项为 None（**如实**），绝不用 0 冒充「实测为零」。
        ★ 分位用 `round(q*(n-1))` 口径（`_pct`），与 Python 侧分析工具
        （`ext032_deliver._pct` / `p1_pipeline._pct` / `ext033_analyze._pct`）
        及 `extension/player.js` 的 `pct()` **四方一致**（EXT-039 收口修正）。
        """
        def _pct(vals: List[float], q: float) -> Optional[float]:
            if not vals:
                return None
            s = sorted(vals)
            # ★ 2026-11-05 EXT-039 收口：**分位口径统一** = `round(q*(n-1))`。
            #   原实现用 `ceil(q*n)-1` ⇒ 与 Python 侧
            #   （`ext032_deliver._pct` / `p1_pipeline._pct` /
            #     `ext033_analyze._pct`）与 `extension/player.js` 的 `pct()`
            #   **不一致** ⇒ 同一批数据在两端给出**两个不同的 P95**。
            #   ⇒ 统一为 `round(q*(n-1))`（**也是 reviewer 手算用的口径**：
            #     EXT-039 ② 报的 P50/P95 = 5.98 / 16.13 正是该口径）。
            i = int(round(q * (len(s) - 1)))
            i = max(0, min(i, len(s) - 1))
            return s[i]

        dl = list(self.client_downlink_ms or [])
        pq = list(self.client_player_queue_sec or [])
        out = {
            "n_downlink_samples": len(dl),
            "downlink_p50_ms": (round(_pct(dl, 0.50), 1) if dl else None),
            "downlink_p95_ms": (round(_pct(dl, 0.95), 1) if dl else None),
            "downlink_max_ms": (round(max(dl), 1) if dl else None),
            "n_player_queue_samples": len(pq),
            "player_queue_p50_sec": (round(_pct(pq, 0.50), 3) if pq else None),
            "player_queue_p95_sec": (round(_pct(pq, 0.95), 3) if pq else None),
            "player_queue_max_sec": (round(max(pq), 3) if pq else None),
            "t0_up_player_offset_sec": self.client_t0_up_player_offset_sec,
            "note": ("★ 客户端**实测**值（`ply_wall_ms − srv_wall_ms` 与 "
                     "`readyToStartSec`）⇒ 没报就是 None（**不臆造**）。"
                     "分位用**最近秩**口径（与 `_pct` 一致）。"),
        }
        return out

    def _clone_mgr(self):
        """11-08: 面板选 clone 且接了真实引擎 ⇒ 懒加载 CloneVoices；否则 None。"""
        if (self.client_voice or "A").strip().lower() != "clone" or self._engine is None:
            return None
        if self._clone is None and not self._clone_failed:
            try:
                from .clone_voice import CloneVoices
                self._clone = CloneVoices(on_log=_log)
                _log("克隆说话人已启用（说话人旁路 + 按句绑定音色）")
            except Exception as e:
                self._clone_failed = True
                _log(f"克隆说话人启用失败（回落预设 A）：{e}")
        return self._clone

    # ── 音色选择（T-3） ──────────────────────────────────────
    def _pick_voice(self, spk) -> str:
        """★ T-3：按**面板上的音色选择**决定这一句用哪个音色。

        面板有两个选项：
          * `A`（预设 A）—— 固定音色，走 speaker embedding（x-vector）。
          * `clone`（克隆说话人）—— 按说话人克隆音色。

        ⚠️ 旧实现（`self.tracker.voice_for(spk)`）**完全忽略面板选择**：
           只要 speaker tracker 里某个说话人攒够 3 s 干净语音，
           就会自动切到克隆音色 ⇒ 用户在面板上选「预设 A」也不管用。

        ⇒ 现在：面板选 `A` ⇒ **一律用预设 A**（不管 tracker 说什么）；
                面板选 `clone` ⇒ 沿用 tracker 的判断（攒够才克隆）。

        ★ 诚实性：clone 需要 pyannote 旁路提供 spk，而旁路**尚未接线**
          （见 STATUS §「pyannote 旁路未接线」）⇒ 选了 clone 但没有 spk 时，
          仍会回落到预设 A（`voice_for` 的默认行为）。
          ⇒ 这一点由 `client_voice` 字段如实记录，不假装克隆已生效。
        """
        pref = (self.client_voice or "A").strip().lower()
        if pref != "clone":
            # 预设 A：直接用配置里的预设音色，**不看 tracker**
            return C.PRESET_VOICE
        # clone：交给 tracker（攒够 3 s 才克隆，否则回落到预设 A）
        return self.tracker.voice_for(spk)

    # ── 接收一帧 ────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════
    # v0.4.19「保留背景音」(user 11-23): Demucs separation of the 48 kHz stereo uplink.
    #   background -> player (`bg`); vocals -> speaker bypass / voice clone (ASR keeps the original).
    # ══════════════════════════════════════════════════════════
    def set_bg_keep(self, on) -> None:
        on = bool(on)
        if on == self.bg_keep:
            return
        self.bg_keep = on
        self._bg_on_frame = self.n_frames
        self._bg_fail = "" if on else self._bg_fail
        if not on and self._bg_sep is not None:
            try:
                self._bg_sep.stop()
            except Exception:
                pass
            self._bg_sep = None
        _log("保留背景音：%s" % ("开" if on else "关"))
        self._bg_status_key = None             # push a fresh bg_status

    def _bg_wants_vocals(self) -> bool:
        """Speaker/clone paths should wait for separated vocals (instead of the original audio)."""
        if not self.bg_keep or self._bg_fail:
            return False
        sep = self._bg_sep
        return sep is None or sep.state in ("starting", "ok")

    def _spk_use_vocals(self) -> bool:
        """Speaker bypass takes separated vocals only once the separator is actually running (ASR-094 ③):
        while it is still starting the original keeps feeding, so the bypass never misses a stretch."""
        sep = self._bg_sep
        return bool(self.bg_keep and not self._bg_fail and sep is not None and sep.state == "ok")

    def _ensure_bg_sep(self):
        if self._bg_sep is None and self.bg_keep and not self._bg_fail:
            self._bg_sep = _bgsep.StreamingSeparator(self._on_bg_block, self._on_bg_vocals).start()
            _log("背景分离器启动（模型 %s，设备 %s）" % (self._bg_sep.model_path, self._bg_sep.device))
        return self._bg_sep

    def on_pcm_bg(self, msg: dict) -> None:
        if not self.bg_keep:
            return
        sep = self._ensure_bg_sep()
        if sep is None:
            return
        try:
            raw = base64.b64decode(msg.get("pcm") or "")
            sep.push(int(msg.get("sample_index_bg", 0)), raw,
                     channels=int(msg.get("ch", 2)), rate=int(msg.get("rate", _bgsep.SR_IN)))
            self._bg_n_up += 1
        except Exception as e:
            _log("pcm_bg 处理失败（忽略）：%s" % e)

    def bg_flush(self) -> None:
        if self._bg_sep is not None:
            self._bg_sep.flush()

    def _on_bg_block(self, t_start: float, pcm: bytes, n_frames: int) -> None:   # separator thread
        self._bg_seq += 1
        self._bg_tasks.append({
            "type": "bg", "seq": self._bg_seq, "t_start": round(float(t_start), 6),
            "sample_rate": _bgsep.SR_IN, "channels": 2, "n_frames": int(n_frames),
            "pcm": base64.b64encode(pcm).decode("ascii"),
        })

    def _on_bg_vocals(self, t_start: float, v16) -> None:                       # separator thread
        v16 = np.asarray(v16, dtype=np.float32)
        with self._voc_lock:
            i0 = int(round(t_start * C.SAMPLE_RATE))
            if self._voc16.size == 0:
                self._voc16_base = i0
            self._voc16 = np.concatenate([self._voc16, v16])
            keep = int(120 * C.SAMPLE_RATE)
            if self._voc16.size > keep:
                cut = self._voc16.size - keep
                self._voc16 = self._voc16[cut:]
                self._voc16_base += cut
        if self.spk_bypass is not None and self._spk_use_vocals():
            try:
                self._spk_feed(v16, int(round(t_start * C.SAMPLE_RATE)))
            except Exception as e:
                _log("说话人旁路喂人声失败（忽略）：%s" % e)
        self._pump_clone_pending()

    def _spk_feed(self, arr, start_idx: int) -> None:
        """Feed the speaker bypass on ONE continuous 16 kHz time axis (ASR-093 risk 1/3): the tracker
        slices audio by cumulative sample count, so when the source switches between the original and
        the separated vocals (toggle, separator failure) gaps are filled with silence and overlaps trimmed."""
        if self.spk_bypass is None:
            return
        arr = np.asarray(arr, dtype=np.float32)
        with self._spk_feed_lock:
            if self._spk_fed_until is None:
                self._spk_fed_until = int(start_idx)
            gap = int(start_idx) - self._spk_fed_until
            if gap > 0:
                z = np.zeros(gap, dtype=np.float32)
                self.spk_bypass.feed(z, (self._spk_fed_until + gap) / float(C.SAMPLE_RATE))
                self._spk_fed_until += gap
            elif gap < 0:
                arr = arr[-gap:]
                if arr.size == 0:
                    return
            self._spk_fed_until += arr.size
            self.spk_bypass.feed(arr, self._spk_fed_until / float(C.SAMPLE_RATE))

    def vocals_slice(self, t0: float, t1: float):
        """Separated vocals (16 kHz mono) for [t0, t1), or None if not (yet) available."""
        with self._voc_lock:
            a = int(round(t0 * C.SAMPLE_RATE)) - self._voc16_base
            b = int(round(t1 * C.SAMPLE_RATE)) - self._voc16_base
            if a < 0 or b > self._voc16.size or b <= a:
                return None
            return self._voc16[a:b].copy()

    def _speech_onset(self, t_start: float, t_end: float, wait: Optional[float] = None) -> float:
        """v0.4.19 (user 11-23: clip_s2 dub came before the actor spoke): segmentation runs on the
        original mix, and with background music it often has no silence to cut at ⇒ fixed-length cuts
        whose start is well before the speech. When separated vocals are available, start the dub at
        the first voiced frame of this segment's vocals. ASR cut points and text are unchanged.
        Waits for the vocals only while the dub still has slack; otherwise keeps t_start."""
        if wait is None:
            wait = float(os.environ.get("EXT_BG_ONSET_WAIT_SEC", "0"))
        deadline = time.perf_counter() + max(0.0, min(
            wait, (self.t0 + t_start + self.delay_sec) - time.perf_counter() - 4.0))
        voc = self.vocals_slice(t_start, t_end)
        while voc is None and time.perf_counter() < deadline and self._bg_wants_vocals():
            time.sleep(0.1)
            voc = self.vocals_slice(t_start, t_end)
        if voc is None or voc.size < int(0.3 * C.SAMPLE_RATE):
            self.bg_onset_no_vocals += 1
            return t_start
        hop = int(0.03 * C.SAMPLE_RATE)
        n = voc.size // hop
        rms = np.sqrt(np.mean(voc[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
        db = 20 * np.log10(rms + 1e-9)
        p95 = float(np.percentile(db, 95))
        if p95 < -45.0:                        # no speech in this segment's vocals: leave it alone
            return t_start
        # sustained voicing (≥ 0.15 s within 0.3 s) at most 20 dB under this segment's speech level:
        #   short breaths / music bleed in the vocals stem must not count as the onset (clip_s2: a 0.1 s
        #   -41 dB burst at 11.0 s vs. speech at -11 dB from 15.0 s)
        voiced = (db > max(p95 - 20.0, -45.0)).astype(np.int32)
        win = np.convolve(voiced, np.ones(10, dtype=np.int32), mode="full")[9:9 + voiced.size]
        on = np.where(win >= 5)[0]
        if on.size == 0:
            return t_start
        first = int(on[0])
        first = first + int(np.argmax(voiced[first:first + 10]))      # first voiced frame of that window
        shift = max(0.0, first * 0.03 - 0.1)
        new = min(t_start + shift, t_end - 0.5)
        if new > t_start + 0.05:
            self.bg_onset_shifted += 1
            self.bg_onset_shift_sum += new - t_start
            return round(new, 3)
        return t_start

    def _check_onsets(self) -> list:
        """`dub_shift` for emitted dubs whose vocals have arrived (event-loop thread, never blocks)."""
        out = []
        if not self._onset_pending:
            return out
        now = time.perf_counter()
        keep = collections.deque()
        with self._clone_pending_lock:
            items = list(self._onset_pending)
            self._onset_pending.clear()
        for did, t0, t1, deadline in items:
            if now > deadline - 0.3 or not self._bg_wants_vocals():
                self.bg_onset_no_vocals += 1          # too late to move it / separation off: stays put
                continue
            if self.vocals_slice(t0, t1) is None:
                keep.append((did, t0, t1, deadline))
                continue
            new = self._speech_onset(t0, t1, wait=0.0)
            if new > t0 + 0.05:
                out.append({"type": "dub_shift", "id": did, "t_start": new, "orig_t_start": t0})
        with self._clone_pending_lock:
            self._onset_pending.extendleft(reversed(keep))
        return out

    def _pump_clone_pending(self) -> None:
        """Hand queued sentences to the clone manager in order, with separated vocals once they have
        arrived; fall back to the original audio if separation is off/failed or later than the wait."""
        if not self._clone_pending:
            return
        cv = self._clone_mgr()
        if cv is None:
            return
        wait = float(os.environ.get("EXT_BG_CLONE_WAIT_SEC", "15"))
        with self._clone_pending_lock:
            while self._clone_pending:
                seg_id, audio, t0, t1, text, queued = self._clone_pending[0]
                voc = self.vocals_slice(t0, t1)
                if voc is not None:
                    use = voc
                    self.bg_clone_from_vocals += 1
                elif (not self._bg_wants_vocals()) or (time.monotonic() - queued > wait):
                    use = audio
                    self.bg_clone_fallback_orig += 1
                else:
                    break
                self._clone_pending.popleft()
                try:
                    cv.on_segment(seg_id, use, t0, t1, text=text)
                except Exception as e:
                    _log("克隆旁路失败（段 %s）: %s" % (seg_id, e))

    def pop_bg_tasks(self) -> list:
        """Downlink `bg` blocks + a `bg_status` on change / every 10 s (event-loop thread)."""
        out = []
        while self._bg_tasks:
            try:
                out.append(self._bg_tasks.popleft())
            except IndexError:
                break
        self._pump_clone_pending()
        out.extend(self._check_onsets())
        if not self.bg_keep and self._bg_status_key == "off":
            return out
        st = self.bg_status()
        key = (st["state"], st["device"], st["reason"])
        now = time.monotonic()
        if key != self._bg_status_key or now - self._bg_status_at >= 10.0:
            self._bg_status_key = key if self.bg_keep else "off"
            self._bg_status_at = now
            out.append({"type": "bg_status", **st})
        return out

    def bg_status(self) -> dict:
        if not self.bg_keep:
            return {"state": "off", "device": None, "reason": "", "rtf": None, "lead_sec": None}
        if self._bg_fail:
            return {"state": "unavailable", "device": None, "reason": self._bg_fail,
                    "rtf": None, "lead_sec": None}
        if self._bg_sep is None:
            ok = _bgsep.default_model_path() is not None
            return {"state": "starting" if ok else "unavailable", "device": None,
                    "reason": "" if ok else "背景分离模型缺失（models/bgsep/htdemucs_core.xml）",
                    "rtf": None, "lead_sec": None}
        st = self._bg_sep.status()
        state = st["state"] if st["state"] in ("starting", "ok", "unavailable") else "ok"
        if state == "ok" and st.get("lead_sec") is not None and st["lead_sec"] < -(self.delay_sec - 2.0):
            state = "degraded"                  # background would miss its play time
        return {"state": state, "device": st["device"], "reason": st["reason"],
                "rtf": st["rtf"], "lead_sec": st["lead_sec"]}

    def bg_stats(self) -> dict:
        st = self._bg_sep.status() if self._bg_sep is not None else {}
        return {
            "bg_keep": bool(self.bg_keep),
            "bg_state": self.bg_status()["state"],
            "bg_blocks_sent": st.get("bg_blocks_sent", 0),
            "bg_up_frames": self._bg_n_up,
            "bg_up_gaps": st.get("bg_up_gaps", 0),
            "sep_device": st.get("device"),
            "sep_rtf_p50": st.get("rtf"),
            "sep_rtf_p90": st.get("rtf_p90"),
            "sep_compile_s": st.get("compile_s"),
            "bg_lead_sec": st.get("lead_sec"),
            "bg_clone_from_vocals": self.bg_clone_from_vocals,
            "bg_clone_fallback_orig": self.bg_clone_fallback_orig,
            "bg_onset_shifted": self.bg_onset_shifted,
            "bg_onset_shift_sum_sec": round(float(self.bg_onset_shift_sum), 2),
            "bg_onset_no_vocals": self.bg_onset_no_vocals,
        }

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
        # ★★★ EXT-029 ①：把这一帧**投喂给说话人旁路**。
        #   ## 铁律：本调用**只做 put_nowait**（队列有界）
        #     ⇒ 队列满了就**丢旧块并计数**（`spk_queue_drop`）
        #     ⇒ **绝不阻塞** ASR 主路径 / 定稿 / MT / TTS。
        #   ⚠️ 必须喂**喂帧时刻的原始音频**（`arr`），而不是切段后的
        #     段音频 ⇒ 旁路才能拿到**连续**的时间轴（它自己按 10 s 窗口
        #     增量推进分段）。
        #   ⚠️ `t_end` 用**采样点**换算 ⇒ 与 `t_start` 同一时间轴。
        if (self.bg_keep and self._bg_sep is None and not self._bg_fail
                and self.n_frames - self._bg_on_frame > 100):
            # client asked for 保留背景音 but sent no stereo uplink for ~5-10 s => run without it
            self._bg_fail = "插件没有上传立体声原声（pcm_bg）"
            _log("保留背景音不可用：%s" % self._bg_fail)
        if self.spk_bypass is not None and not self._spk_use_vocals():
            try:
                self._spk_feed(arr, sidx)          # same continuous axis as the vocals path
            except Exception as e:
                _log(f"说话人旁路喂帧失败（忽略）：{e}")
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
        # ★★ T-5 修正：**有界化** —— 旧实现每帧追加、永不裁剪
        #   （47 帧/秒 × 30 分钟 ⇒ 8.5 万条/会话 ⇒ 内存持续增长）。
        #   ⇒ 只保留最近 C.FRAME_DELAY_HISTORY 条；
        #   统计口径由**累计量**（_n_frames_measured / _sum_frame_arrival_delay
        #   / _n_frames_late / _max_frame_arrival_delay）承担，
        #   **不随窗口裁剪而改变** ⇒ 与旧实现读出的数字口径一致。
        if len(self._frame_arrival_delays) > C.FRAME_DELAY_HISTORY:
            del self._frame_arrival_delays[:-C.FRAME_DELAY_HISTORY]
        # 汇总（滚动统计，不必每次都遍历全表）
        self._n_frames_measured += 1
        # ⚠️ 累加的是**四舍五入后**的值（round(_delay, 4)）
        #   ⇒ 与旧实现「对列表里 round 过的 delay_sec 求和」**完全等价**
        #   ⇒ 裁剪历史后均值口径**一字不变**。
        self._sum_frame_arrival_delay += round(_delay, 4)
        self._n_frames_late += 1 if _delay > 1.0 else 0
        if _delay > self._max_frame_arrival_delay:
            self._max_frame_arrival_delay = _delay

        # 分段：以 R2T2 原有断句为准（EXT-002）
        # ★★★★★★ EXT-036 ④：**首段一到 cap 就交出**（不等原段到齐）。
        #   ## 病根（reviewer EXT-036 ④ 的实测）
        #     旧流程：`plan_segments()` 只能在**原段（最多 8 s）音频到齐**后
        #     才给出网格 ⇒ 之后才谈得上「拆成 3.5 + 4.5」⇒
        #     ⇒ `seg_0` 与 `seg_56000` 的 `audio_ready_rel` **都是 8.216 s**
        #     ⇒ 首段**并没有**被真正「提前」。
        #   ## 修法
        #     首段**还没被切走**、且缓冲区里的音频已够 `cap` 秒时，
        #     **立刻**交出 `[0, cap]` ⇒ 不必等原段。
        #     ⚠️ 最终网格必须与
        #       `ext/segmenter.plan_segments_first_capped()` **一致**
        #       ⇒ 客户端预期段数才不会漂。
        # 11-08 self-test: clone mode cuts at silences from SEG_MIN_SEC_CLONE (short turns such as
        #   "Can you give us an example?" were merged with the next speaker => wrong voice)
        _clone_on = (self.client_voice or "").strip().lower() == "clone"
        # 11-09: with a small panel delay long segments can never be dubbed in time => cap by D
        _smax = min(C.SEG_MAX_SEC, max(C.SEG_MAX_FLOOR_SEC, float(self.delay_sec) - C.SEG_MAX_RESERVE_SEC))
        if getattr(self, "_smax_logged", None) != _smax:
            self._smax_logged = _smax
            _log("分段上限 %.1f s（D=%.1f s）" % (_smax, float(self.delay_sec)))
        segs = plan_segments(self._buf, min_segment_sec=(C.SEG_MIN_SEC_CLONE if _clone_on
                                                         else C.SEG_MIN_SEC),
                             max_segment_sec=_smax)
        # ★★★★★★ EXT-036 ④：**首段提前交付 + 切点栅格锚定**。
        #   ## 病根（reviewer EXT-036 ④ 的实测）
        #     旧流程：`plan_segments()` 只能在**原段（最多 8 s）音频到齐**后
        #     才给出网格 ⇒ 之后才谈得上「拆成 3.5 + 4.5」⇒
        #     ⇒ `seg_0` 与 `seg_56000` 的 `audio_ready_rel` **都是 8.216 s**
        #     ⇒ 首段**并没有**被真正「提前」。
        #   ## 修法
        #     首段**还没被切走**、且缓冲区里的音频已够 `cap` 秒时，
        #     **立刻**交出 `[0, cap]` ⇒ 不必等原段。
        #
        #   ## ★★★ 关键：**交出后不裁剪 `_buf`**（只记 `_first_seg_cut`）
        #     ⇒ `plan_segments(self._buf)` 始终是**从会话起点**算的
        #     ⇒ **VAD 切点栅格逐位不变** ⇒ 尾段**不会**被吃掉。
        #     ⚠️ 上一版实现把缓冲裁掉了 ⇒ 下一轮从 cap 处**重新起算**
        #       ⇒ 栅格整体平移 3.5 s ⇒ 后续切点全变
        #       （8.0→11.5、16.0→19.5 …）⇒ 尾段丢失。
        if not self._first_seg_done:
            # 首段还没交付 ⇒ 优先试「提前交付」
            first = self._first_segment_early()
            if first is not None:
                tasks = self._dispatch_segment(seq, 0, first, self._buf[:first],
                                               audio_complete_at=recv_at)
                # ★★★ **不裁剪 `_buf`** ⇒ 栅格逐位不变
                self._first_seg_cut = first
                # ★★ EXT-037 ②：记录「已交付但仍在缓冲里」的前缀
                #   ⇒ `flush()` 必须跳过它（否则尾段与首段**重叠**）
                self._buf_delivered_prefix = first
                self._first_seg_done = True
                return tasks or None
            # 原段已到齐但还没提前交付（cap 比原段长）⇒ 走**限长拆分**
            segs = self._split_first_segment(segs)
        else:
            # ★★★★★★ EXT-037 ②：**首段已交付 ⇒ 网格对齐**（**只切一次**）。
            #   ## 病根（reviewer EXT-037 ② 的实测，B 轮 `20261104_195911`）
            #     旧实现**每次**调用都执行 `split_first_segment_streaming(...)`
            #     ⇒ 但下面把 `_buf` 裁掉之后，网格已经是**相对新缓冲**的
            #     ⇒ 函数仍把新缓冲开头的 `[0, 3.5 s)` 当作「已交付首段」去掉
            #     ⇒ **每段之后都丢掉 3.5 s**。
            #     实测：段区间 0–3.5、3.5–8.0、**11.5**–15.89、
            #       **19.39**–26.44、**29.94**–36.91 ……
            #       ⇒ 每个缺口都**正好 3.5 s** ⇒ 60 s 素材丢了约 24 s（40%）。
            #   ## 修法（最小、范围可控）
            #     守卫 = **`_buf_base == 0`**（缓冲起点仍是会话起点
            #     ⇒ 缓冲里**还留着**已交付的首段 ⇒ 需要对齐）；
            #     一旦处理过网格里的段 ⇒ `_buf` 被裁 ⇒ `_buf_base > 0`
            #     ⇒ 此后**绝不再切**（新缓冲开头的 3.5 s 是**真实音频**，
            #     **不是**「已交付的首段」⇒ 切掉就是丢内容）。
            #   ⚠️ 为什么不能在这里就把 `_first_seg_cut` 清零：
            #     对齐后的网格**可能还没有可派发的段**（末段留在缓冲里）
            #     ⇒ 此时缓冲**没被裁** ⇒ `_buf_base` 仍为 0
            #     ⇒ 若已清零，下一轮就**不再对齐** ⇒ 原始网格的第一段
            #       会被**重复派发**（与已交付的首段重叠）。
            #     ⇒ 只在**真正裁掉缓冲之后**（`_buf_base` 推进）才清零。
            if self._buf_base == 0 and self._first_seg_cut:
                _segs = split_first_segment_streaming(
                    segs, cap_sec=self._first_seg_cut / float(C.SAMPLE_RATE),
                    min_sec=C.SEG_MIN_SEC)
                if not _segs:
                    # 网格还没成形（缓冲还不够）⇒ **保留** `_first_seg_cut`
                    # ⇒ 下一轮音频更多时**重试**（既不重复切，也不丢首段）
                    return None
                segs = _segs
        # 只处理已完整落在 [min, max] 内的段，最后一段留在缓冲区里等后续音频
        ready = list(segs[:-1])
        if not ready:
            return None
        # 11-09 user: "different speakers must be cut into different segments" - clone mode splits
        #   ready segments at speaker changes (outer bounds unchanged => grid/trim logic untouched)
        if _clone_on:
            _cvs = self._clone_mgr()
            if _cvs is not None:
                try:
                    ready = _cvs.split_by_speaker(self._buf, ready)
                except Exception as e:
                    _log(f"说话人切分失败（按停顿切）: {e}")
        tasks = []
        # ★ 段索引是相对**当前缓冲区**的 ⇒ 换算成会话绝对样本偏移。
        #   旧实现每处理一段就把 self._buf 裁掉前段，却继续用旧的 (s0, s1)
        #   去切下一个段 ⇒ 索引错位（第二段起音频被切错），且 t_start 归零
        #   ⇒ 全部段的时间基点漂移。EXT-006 P1 要按时间表落盘配音，
        #   这个错位会直接污染「同步误差」指标。
        # ★★★★★★ EXT-036 ④：**首段提前交付后，缓冲起点不再等于「已消费起点」**。
        #   `abs0 = self._consumed_samples + s0` 这个换算**只在缓冲没被裁过时**成立。
        #   提前交付时我们**故意不裁缓冲** ⇒ 缓冲里还留着已交付的首段
        #   ⇒ 必须用**缓冲的绝对起点**来换算，而不是 `_consumed_samples`。
        #   ⇒ `_buf_base` = 缓冲第一个样本的**会话绝对偏移**。
        #   ⇒ `_consumed_samples` = 已交付的样本数（用于尾段判定与统计）。
        for (s0, s1) in ready:
            seg_audio = self._buf[s0:s1]
            abs0 = self._buf_base + s0
            abs1 = self._buf_base + s1
            tasks.extend(self._dispatch_segment(seq, abs0, abs1, seg_audio,
                                                audio_complete_at=recv_at))
        # ★★★★★★ EXT-039：**首段只能交付一次**（真缺陷修复）。
        #   ## 病根（reviewer EXT-039 ⑤ 要求「raw 日志齐全可复现」⇒ 本轮
        #     用 ≥150 s 素材复现出来的）
        #     上面那条「**限长拆分**」路径（`self._split_first_segment(segs)`）
        #     **交付了首段**，但**没有**置 `_first_seg_done` ⇒
        #     下一轮 `if not self._first_seg_done:` **仍然成立**
        #     ⇒ 「**首段提前交付**」路径**又**跑一次
        #     ⇒ 而它**硬编码 `abs0 = 0`** ⇒ **把首段再交付一遍**。
        #   ## 实测证据（run `20261105_164316`，180 s 素材，D=20）
        #     `margin.json:per_segment` 里出现**两条 `seg_0`**：
        #       `seg_0 [0.00, 3.16]`（拆分路径交付）
        #       `seg_0 [0.00, 3.50]`（提前交付路径**重复**交付）
        #     ⇒ 两段**重叠 3.16 s** ⇒ 段区间不再连续
        #     ⇒ `bridge.log` 两条「段 seg_…_0 | t_start=0.000」
        #     ⇒ `metrics.json: dubDup = 1`（插件侧去重挡下了第二条）
        #   ## 修法（最小改动）
        #     一旦**真的派发**了段（`ready` 非空）⇒ 首段已交付 ⇒ 置位。
        #     ⚠️ **不能**在 `ready` 为空时置位 —— 那会废掉
        #       「首段提前交付」这条优化（首段还没到 3.5 s 时必须继续等）。
        self._first_seg_done = True
        # 一次性裁掉所有已处理的段，并把基准点推进
        # ★★★★★★ EXT-036 ④：**只在「栅格切点」上裁剪** ⇒ 栅格逐位不变。
        #   提前交付的首段（`[0, cap)`）**不被单独裁掉** ⇒ 下一轮
        #   `plan_segments(self._buf)` 仍从会话起点起算 ⇒ 切点不变。
        #   ⚠️ 上一版实现提前交付时裁了缓冲 ⇒ 栅格整体平移 3.5 s
        #     ⇒ 后续切点全变 ⇒ **尾段被吃掉**（实测 flush 产出 0 段）。
        cut = ready[-1][1]
        self._buf = self._buf[cut:]
        self._buf_base += cut
        self._consumed_samples = max(self._consumed_samples, self._buf_base)
        # ★★★★★★ EXT-037 ②：缓冲被裁 ⇒ **网格对齐已完成**
        #   ⇒ 此后 `_buf_base > 0` ⇒ 守卫 `self._buf_base == 0` 天然不再成立
        #   ⇒ **绝不再重复切首段**（旧实现每段都切 ⇒ 每段丢 3.5 s）。
        #   ⇒ 同时把「已交付但未裁」的前缀清零：它已被这次裁剪**吸收**。
        self._first_seg_cut = 0
        self._buf_delivered_prefix = 0
        return tasks or None

    # ── 段派发（串行 vs 流水线） ────────────────────────────────
    def _first_segment_early(self) -> Optional[int]:
        """★ EXT-036 ④：**首段提前交付** ⇒ 返回应切走的样本数（绝对）。

        ## 判据
          缓冲区里已有 **≥ cap 秒**（`FIRST_SEGMENT_MAX_SEC`）音频
          ⇒ 立刻交出 `[0, cap]`（**不等原段到齐**）。

        ## 为什么必须提前
          reviewer EXT-036 ④ 实测：`seg_0` 与 `seg_56000` 的
          `audio_ready_rel` **都是 8.216 s** ⇒ 首段要等原来那段
          **8 s** 的音频全部到齐才被交出 ⇒ **完全没提前** ⇒
          开头静音 ≈ D + 8 s + ASR + MT + TTS。

        ## 一致性保证
          最终网格与 `ext/segmenter.plan_segments_first_capped()` 一致
          ⇒ 客户端 `expected_segment_count()` 不会漂。

        Returns
        -------
        int or None
            该切的样本数；**不该提前切**时返回 None。
        """
        cap = int(self._first_seg_max_sec * C.SAMPLE_RATE)
        if cap <= 0:
            return None
        if self._buf.shape[0] < cap:
            return None
        # ⚠️ 余段若是**碎片**（原段尾巴不足 min）⇒ 提前切会多出一个碎片段
        #   ⇒ 与 `plan_segments_first_capped()` 的「碎片并进下一段」一致
        #   ⇒ 这里**照切**（碎片会在下一轮与后续音频合并时处理）。
        return cap

    def _split_first_segment(self, segs: List[Tuple[int, int]]
                             ) -> List[Tuple[int, int]]:
        """★ EXT-034 ④：**把会话的第一段拆成两段**（缩短「起步」）。

        ## 本方法只是 `ext/segmenter.split_first_segment()` 的**薄包装**
          服务端（这里）与客户端（`tools/p1_pipeline.py` 的
          `expected_segment_count()`）**必须**用**同一份**拆分逻辑
          ⇒ 否则两边各写一份 ⇒ 口径漂移 ⇒ 客户端预期与服务端实际不符。

        ## 为什么拆而不截短（EXT-034 ④ 的关键取舍）
          ASR 是**整段到齐才定稿**（`_dispatch_segment` 只在整段音频
          完整到达后才调 `_process_segment` ⇒ ASR/MT/TTS 都在那一刻
          才开始跑）⇒ **首段越长、起步越晚**：
            起步耗时 ≈ 首段长度 + ASR + MT + TTS
            实测：8.0 + 5.20 + 1.30 + 11.04 = **25.54 s** > D=10 s
          ⇒ 必须把首段**切短**。

        ## ⚠️ 只在**会话级**调用一次
          缓冲区每处理一段就被裁掉 ⇒ 「缓冲区第一段」每轮都不同
          ⇒ 必须按 `self._first_seg_done` 判定，只拆**会话真正的第一段**。
        """
        return split_first_segment(
            segs, cap_sec=self._first_seg_max_sec,
            min_sec=C.SEG_MIN_SEC, sample_rate=C.SAMPLE_RATE)

    def _dispatch_segment(self, seq: int, abs0: int, abs1: int,
                          seg_audio: np.ndarray, *,
                          audio_complete_at: float) -> list:
        """把一段交给处理路径。

        * **串行**（基类）⇒ 同步跑完 ASR→MT→TTS，返回这一段的配音任务；
        * **流水线**（`PipelineSession`）⇒ 提交到流水线线程，
          返回「**已经就绪**」的任务（未就绪的稍后由 drain 取回）。

        ★ 保持第一个钩子是为了**不改动**基类的串行行为
          （旧自测全部针对串行路径，行为必须完全一致）。
        """
        # ★★★ EXT-029 ②：**定稿段一被切出来**就向旁路要标签。
        #   ## 为什么在这里（而不是收口时）
        #     旁路要标签需要「音频已进缓冲 + 分段已推进到该段」
        #     ⇒ 越早问越好 ⇒ 现在问，标签能在 ASR+MT+TTS 这段时间里
        #     **异步**算好 ⇒ 到收口时多半已经就绪（**不等待**）。
        #   ⚠️ 本调用**只 append**（零阻塞）⇒ 不影响主路径。
        self._request_spk_label(abs0, abs1)
        return self._process_segment(seq, abs0, abs1, seg_audio,
                                     audio_complete_at=audio_complete_at)

    # ── ★★★ EXT-029：旁路标签的请求与回填 ─────────────────
    def _request_spk_label(self, abs0: int, abs1: int) -> None:
        """向旁路登记「这段定稿了」（**零阻塞**）。"""
        bp = self.spk_bypass
        if bp is None:
            return
        seg_id = "seg_%d" % abs0
        t_start = abs0 / C.SAMPLE_RATE
        t_end = abs1 / C.SAMPLE_RATE
        try:
            bp.request_final(seg_id, t_start, t_end)
        except Exception as e:
            _log(f"说话人旁路请求标签失败（忽略）：{e}")

    def _on_spk_label(self, seg_id: str, t_start: float, t_end: float,
                      spk: str, info: dict) -> None:
        """旁路 worker **异步回填**标签时的回调（EXT-029 ②）。

        ★ 只做：① 记进 `_spk_labels`；② 唤醒等标签的人；
          ③ 更新段级 `spk_table`。
        ⚠️ **绝不阻塞**旁路 worker。
        """
        try:
            with self._spk_label_cv:
                self._spk_labels[seg_id] = spk
                self._spk_label_cv.notify_all()
            # ★★ 把标签喂给**主 tracker**（`ext/speaker.py` 的记账类）
            #   ⇒ ① 该说话人进入 tracker 的 profile（攒够 3 s 才给克隆音色）
            #   ⇒ ② 下一句的音色选择能用「上一句音色」（EXT-027③ 规则 7）
            #   ⇒ ③ 未定稿的段能拿到补发事件（EXT-002 语义）
            #   ⚠️ 这是**记账**（纯 Python，微秒级）⇒ 不阻塞旁路 worker。
            try:
                self.tracker.update_from_diarization([{
                    "spk_id": spk, "t_start": float(t_start),
                    "t_end": float(t_end)}])
            except Exception as e:
                _log(f"说话人标签入 tracker 失败（忽略）：{e}")
            # ★ 段级表：EXT-027③ 验收要落盘
            #   `spk / voice_source（preset/clone_1.5s/clone_3s/cache）/ 是否换人`
            #   ⚠️ 按 seg_id **去重更新**（不是追加）⇒ 同一段只有一行，
            #     且标签晚到时能补上（否则会出现两行同段、字段互相打架）。
            self._upsert_spk_row(seg_id, {
                "spk": spk,
                "spk_conf": info.get("spk_conf"),
                "spk_is_new": bool(info.get("is_new_spk")),
                "clean_ranges": info.get("clean_ranges") or [],
                "spk_reason": info.get("reason"),
                "spk_lag_s": info.get("lag_s"),
            })
        except Exception as e:
            _log(f"说话人标签回填失败（忽略）：{e}")

    def _upsert_spk_row(self, seg_id: str, fields: dict) -> None:
        """按 seg_id **更新或追加**段级说话人行（线程安全）。

        ⚠️ 收口线程（`_finalize_segment`）与旁路 worker（`_on_spk_label`）
          都会写这张表 ⇒ 必须加锁。
        """
        with self._spk_table_lock:
            row = self._spk_rows.get(seg_id)
            if row is None:
                row = {"seg_id": seg_id}
                self._spk_rows[seg_id] = row
                self.spk_table.append(row)
            row.update(fields)

    def spk_for_seg(self, seg_id: str) -> Optional[str]:
        """查某段的说话人标签（**不等待** ⇒ 没有就是 None ⇒ 方案 A）。"""
        with self._spk_label_cv:
            return self._spk_labels.get(seg_id)

    def _resolve_spk(self, seg_id: str, t_start: float,
                     t_end: float) -> Optional[str]:
        """★★ EXT-029 ②：解析这一段的说话人（**绝不等待**）。

        口径（按优先级）：
          1. **旁路标签**（`_spk_labels`，异步回填）—— 精确命中该段；
          2. **tracker**（`spk_for_final`）—— 按时间区间找已知说话人
             （旁路标签也会经 `_on_spk_label` 进 tracker ⇒ 二者一致）；
          3. **None** ⇒ 未到 ⇒ **不等** ⇒ 走**方案 A**
             （上一句音色 / 预设 A，见 `_pick_voice`）。

        ⚠️ 本方法**只查表**（微秒级）⇒ 不阻塞 ASR / 定稿 / MT / TTS。
        """
        s = self.spk_for_seg(seg_id)
        if s:
            return s
        try:
            return self.tracker.spk_for_final(seg_id, t_start, t_end)
        except Exception:
            return None

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
        # ★★★★★★ EXT-037 ②：跳过「**已交付但仍在缓冲里**」的前缀。
        #   首段提前交付时**故意不裁 `_buf`** ⇒ 缓冲头部还留着那 3.5 s
        #   ⇒ 若直接 flush，尾段会从 `_buf_base` 开始 ⇒ 与已交付的首段
        #     **重叠**（重复配音 + 段区间重叠 ⇒ 覆盖率算不准）。
        #   ⇒ 先把这段前缀从缓冲里去掉（**不推进 `_buf_base`**，
        #     因为它**已经被交付过了**）。
        _prefix = int(self._buf_delivered_prefix or 0)
        if _prefix > 0:
            _prefix = min(_prefix, int(self._buf.shape[0]))
            self._buf = self._buf[_prefix:]
            self._buf_delivered_prefix = 0
        if self._buf.shape[0] < int(1.0 * C.SAMPLE_RATE):
            # 尾部不足 1 s ⇒ 没有有意义的语音段，丢弃（不计为段）
            self._buf = np.zeros((0,), dtype=np.float32)
            return []
        # ★ 绝对偏移：尾段同样要相对**会话起点**，不能归零
        #   （否则会重现「段起始时间基点归零」那个缺陷）。
        # ★★★★★★ EXT-036 ④：用 `_buf_base`（缓冲起点的会话绝对偏移）
        #   ⇒ 首段提前交付后（缓冲未裁）尾段偏移仍然**正确**。
        abs0 = self._buf_base
        abs1 = self._buf_base + self._buf.shape[0]
        seg_audio = self._buf
        tasks = self._process_segment(0, abs0, abs1, seg_audio)
        self._buf = np.zeros((0,), dtype=np.float32)
        self._buf_base += seg_audio.shape[0]
        self._consumed_samples = self._buf_base
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
        # ★★ T-5 修正：这两个字典**只写不读** ⇒ 原本每段永久留两个 key
        #   ⇒ 30 分钟会话累积上千项（P2「内存不持续增长」的真缺陷）。
        #   ⇒ 改成**有界**：只留最近 C.SEG_TIMING_HISTORY 段。
        self._trim_seg_timing_history()
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
        #   ★ EXT-029 ②：走 `_resolve_spk`（旁路标签优先）⇒ **不等**。
        spk = self._resolve_spk(seg_id, t_start, t_end)
        self.tracker.register_pending(seg_id, spk, t_start, t_end)
        voice = self._pick_voice(spk)

        # 译文
        # ★★ T-4：把**面板上选的目标语言**真正用起来
        #   （此前只被记录成 client_target_lang，从不参与翻译
        #     ⇒ 面板上的「目标语言」仍是死控件）。
        _tgt_lang = self._effective_target_lang()
        tgt = ""
        t_mt = time.perf_counter()
        if self._engine is not None and text:
            try:
                tgt = self._mt_with_lang(text, _tgt_lang) or ""
            except Exception as e:
                _log(f"MT 失败（段 {seg_id}）: {e}")
        mt_s = time.perf_counter() - t_mt

        # TTS
        pcm24k = None
        speech_sec = 0.0
        t_tts = time.perf_counter()
        if self._engine is not None:
            try:
                pcm24k, speech_sec = self._tts_with_lang(tgt or text, voice,
                                                          _tgt_lang)
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
        # ★★ T-5 修正：同上 ⇒ 有界（只留最近 N 段）
        self._trim_seg_timing_history()
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
        # 11-08 reviewer: player 按 max(目标时刻, 上一句播完, 到达) 排程 ⇒ 服务端照此模拟队列，
        #   否则 TTS 一快 lag_est 就≈0，看不到排队造成的累积滞后（用户实测 6 分钟涨到 10+ s）。
        start_est = max(deadline, ready_at, self._play_end_est)
        # 11-08 测试2：只按**排队**滞后变速（前一句没播完而被推后的部分）。
        #   到达晚（ASR/克隆旁路慢）变速追不回，旧口径会一直卡在 1.5×。
        lag_est = max(0.0, start_est - max(deadline, ready_at))
        dec = decide_speed(lag_est, prev_speed=self._prev_adapt_speed)

        # 时长适配（单句超长时压缩）—— EXT-009 明文「保留」
        fit = fit_duration(seg_id, t_start=t_start, t_end=t_end,
                           speech_sec=speech_sec, max_rate=C.TTS_RATE_MAX)
        # ★ EXT-009 EXT 侧：时长适配（1.0~1.25×）与自适应加速（1.0~1.30×）
        #   **相乘**，总倍率封顶 1.30×，超出的部分顺延。
        rates = combine_rates(fit.rate, dec.speed)
        total_rate = rates["total_rate"]
        # 11-08 用户：倍率只由滞后严重程度决定，1.0×→1.5× 渐进（不再用时长适配的固定倍率）
        # v0.4.9: drive = max(queue lag, lateness vs the picture slot). A late sentence also gets
        #   the rate that ends it by its own slot end, so the next one is not pushed back further.
        _late0 = max(0.0, start_est - deadline)
        _drive = max(lag_est, _late0)
        _raw = 1.0 + max(0.0, _drive - C.ADAPT_LAG_FREE_SEC) * C.ADAPT_GAIN_PER_SEC
        if _late0 > C.ADAPT_LAG_FREE_SEC and speech_sec > 0:
            _avail = deadline + max(0.5, t_end - t_start) - start_est
            _raw = max(_raw, speech_sec / max(0.5, _avail))
        # 11-09 user: Chinese dubs are ~17 % longer than the English source => speed floor for zh
        try:
            _tl = str(self._effective_target_lang() or "").strip().lower()
        except Exception:
            _tl = ""
        _base = C.ZH_BASE_SPEED if (_tl.startswith("zh") or "chinese" in _tl or "中文" in _tl) else 1.0
        _raw = min(C.ADAPT_TOTAL_RATE_MAX, max(_base, _raw))
        _prev = getattr(self, "_queue_rate", _base)
        # v0.4.9: jump up at once when late; only slow down gradually
        total_rate = _raw if _raw >= _prev else max(_prev - C.ADAPT_MAX_STEP, _raw)
        total_rate = round(max(_base, min(C.ADAPT_TOTAL_RATE_MAX, total_rate)), 4)
        self._queue_rate = total_rate
        rates["total_rate"] = total_rate
        # 11-08 test 3: a dub that can only start > LATE_DROP_SEC after its picture slot is
        #   not played (subtitle only) - keeps the voice on the right picture instead of drifting.
        _late = start_est - deadline
        if pcm24k is not None and C.LATE_DROP_SEC > 0 and _late > C.LATE_DROP_SEC:
            self._n_late_drop = getattr(self, "_n_late_drop", 0) + 1
            _log("[sync] 段 %s 已晚 %.1f s（>%.0f s）=> 不播配音、只出字幕（累计 %d 句）"
                 % (seg_id, _late, C.LATE_DROP_SEC, self._n_late_drop))
            pcm24k = None
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

        if pcm_out is not None and speech_out > 0:
            self._play_end_est = start_est + speech_out
        # 顺延量：按**实际采用的**总倍率算（封顶掉的部分排不进窗口 ⇒ 顺延）
        budget = fit.target_sec + fit.extend_sec
        defer_total = fit.defer_sec
        if budget > 0 and speech_out > budget:
            defer_total = max(defer_total, speech_out - budget)

        # ★★★★ EXT-028 ①：**逐段落盘两份音频**。
        #   (a) `pcm24k`  = TTS 引擎的**原始输出**（未经变速）
        #   (b) `pcm_out` = **WS 实际发出的**那份字节（base64 之前）
        #   (c) player 端录到的 —— 由冒烟脚本从浏览器侧落盘
        #   ⇒ 三份对齐后即可定位「失真发生在哪一环」。
        #   ⚠️ 在这里落盘是因为此处**同时**持有 (a) 与 (b) ——
        #     原始输出一旦被 WSOLA 覆盖就再也拿不到了。
        if self.audio_dump is not None and pcm_out is not None:
            try:
                self.audio_dump.dump_segment(
                    self.public_seg_id(seg_id),
                    tts_pcm=pcm24k, ws_pcm=pcm_out,
                    sample_rate=TTS_SAMPLE_RATE, channels=1,
                    extra={"t_start": round(t_start, 3),
                           "t_end": round(t_end, 3),
                           "src": (text or "")[:80],
                           "tgt": (tgt or "")[:80],
                           "speed": round(total_rate, 4),
                           "speech_sec": round(speech_out, 4)})
            except Exception as e:
                _log(f"音频落盘失败（段 {seg_id}）：{e}")

        # ★★★ EXT-024 E：累加**分开**的三段计数。
        #   口径见 `Session.__init__` 的注释（asr=有文本 / mt=有译文 /
        #   tts=有音频）。⚠️ 只在这里累加 ⇒ 串行与流水线路径
        #   **共用同一口径**（都走 `_finalize_segment`）。
        if text:
            self._n_asr_segments += 1
        if tgt:
            self._n_mt_segments += 1
        if pcm24k is not None:
            self._n_tts_segments += 1

        # ★★★ EXT-029 ② / EXT-027③：段级「说话人 / 音色来源」表。
        #   ## 口径（必须与 EXT-027③ 规则一致）
        #     * `voice_source`：
        #       - 'preset'      —— 用预设 A（面板选 A，或无克隆可用）；
        #       - 'clone_1.5s'  —— 新说话人的**首段**取样（≥1.5 s）；
        #       - 'clone_3s'    —— 攒够 3 s 后**重算一次**（之后冻结）；
        #       - 'cache'       —— 换回老说话人 ⇒ 用**缓存**的音色。
        #     * `spk` 未到 ⇒ **不等**（方案 A）⇒ `voice_source='preset'`，
        #       并在 `spk_pending=True` 里如实标注。
        #   ⚠️ 本表**只是记录**：真正的克隆音色接线在 EXT-027③ 的
        #     「音色克隆」阶段（要 TTS 侧的 speaker embedding 管线）。
        #     本轮（EXT-029）只保证**旁路不反压 ASR** + 标签可用。
        #   ★ seg_id 口径：`seg_<绝对起始采样点>`（与 `_dispatch_segment`、
        #     `_request_spk_label` 完全一致）⇒ 旁路回填能对上同一行。
        _spk_now = self.spk_for_seg(seg_id)
        # ★ `voice_source` 的口径（EXT-027③ 规则 5 的枚举）：
        #   'preset'      —— 用预设 A；
        #   'clone_1.5s'  —— 新说话人的**首段**取样（≥1.5 s）；
        #   'clone_3s'    —— 攒够 3 s 后**重算一次**（之后冻结）；
        #   'cache'       —— 换回老说话人 ⇒ 用**缓存**的音色。
        #   ⚠️ **诚实性（本轮只能写 'preset'）**：
        #     真正的克隆音色要把 x-vector **注入 TTS**，
        #     而 EXT 的引擎层目前**只支持预设 A**
        #     （`ext/engine_runtime.py` 的 `_prepare_preset_voice()` 只装
        #       `voices/preset_A.wav` 的 embedding，`tts()` 的 `voice`
        #       参数**没有**接进 `tts_engine.stream()`）。
        #     ⇒ 即便面板选了 clone、tracker 也给出了 spk，
        #       **实际发声仍是预设 A** ⇒ 这里如实写 'preset'，
        #       另用 `voice_requested` 记录「面板/追踪器**想要**什么」。
        #     ⇒ **绝不**写 'clone_1.5s'/'clone_3s'/'cache'（那是假的）。
        _row = {
            "id": seg_id,
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            "spk": spk if spk else None,
            "spk_label": _spk_now,
            "spk_pending": bool(_spk_now is None and self.spk_bypass is not None),
            "voice": voice,
            "voice_source": "preset",
            "voice_requested": voice,
            "clone_wired": False,
            "is_new_spk": None,
            "text": (text or "")[:120],
            "tgt": (tgt or "")[:120],
        }
        self._upsert_spk_row(seg_id, _row)

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
            # 11-07 (reviewer): per-stage compute seconds, for the segment log line
            "asr_sec": round(asr_s, 4), "mt_sec": round(mt_s, 4), "tts_sec": round(tts_s, 4),
            "total_rate": round(total_rate, 4),
            # ★★★ EXT-026 ⑤：**对外**的段 id 带会话前缀
            #   ⇒ 跨会话不可能撞号 ⇒ 插件侧常驻的 `seenDubIds`
            #     不会把新会话的段误判成「旧会话的重复段」而静默丢掉。
            #   ⚠️ 内部键（_seg_orig_end / _seg_ready / speaker tracker）
            #     仍用**裸的** seg_id（会话内键，不跨会话）。
            "id": self.public_seg_id(seg_id),
            # ★★ EXT-024 A（reviewer 明文）：**t_start 用的是哪个时间轴？**
            #   ⇒ 这里**如实写清楚**，并落进日志与 margin.json，
            #     免得 reviewer 只能靠猜。
            #
            #   ## t_start 的时间轴 = **上行链路的采样时间轴**
            #     * `t_start = s0 / 16000`（见 `_process_segment`），
            #       `s0` 是该段第一帧在**上行 PCM 里的累计采样数**
            #       ⇒ 采样点 0 = **上行链路收到的第一帧音频**；
            #     * 这个轴**与墙钟无关**（EXT-001 A 节：不用墙钟，避免漂移），
            #       也**与服务端 t0 无关**。
            #
            #   ## 插件侧怎么用
            #     插件把这段排在 **`t0_player + t_start + D`**：
            #       * `t0_player` = 插件 AudioContext 的启动基准
            #         （`upState.t0`，由**首帧的 inSamples 反推**真实基准点，
            #          见 `extension/player.js` 的 `onUplinkFrame`）；
            #       * `D` = `delay_sec`（原声被 DelayNode 延迟的时长）。
            #     ⇒ **上行采样点 0 与原声起点在同一条音频时间轴上**
            #       （两者都从同一路抓流来）⇒ 二者**天然对齐**，
            #       配音与原声按同一口径错开 D 秒。
            #
            #   ## ⚠️ 诚实的已知偏差（不宣称「精确对齐」）
            #     * 插件的 `t0_player` 与服务端的 `t0`（会话建立时刻）
            #       **不同源**（§6.4.1 已记录）⇒ 两者的**常量偏差**会平移
            #       服务端的 lag 估计（`lag_est_sec`）；
            #     * 但**排程本身**（`t0_player + t_start + D`）用的是
            #       **插件自己的同一个 t0_player** ⇒ 配音与原声的相对关系
            #       **不受这个跨时钟偏差影响**（偏差在两边同时抵消）。
            #     * 滞后的主导项是**管线 backlog**（占 83.18%，§6.4.3）
            #       ⇒ 该常量偏差是二阶效应。
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            # ★★ EXT-024 A：把时间轴口径**显式**带给客户端
            #   （插件可据此核对，不必猜；reviewer 也可从 margin.json 核对）。
            "t_start_axis": "uplink_sample_index",
            "src": text,
            "tgt": tgt,
            "spk": spk,
            "voice": voice,
            "pcm24k": (base64.b64encode(pcm_out).decode("ascii")
                       if pcm_out is not None else None),
            # ★★★★ EXT-028 ①：**必须显式带上 PCM 的采样率**。
            #   ## 为什么这是 EXT-028「基本听不清」的**头号根因**
            #     服务端下发的 TTS 是 **24 kHz** PCM16（`TTS_SAMPLE_RATE`），
            #     而插件侧 `scheduleDub()` 原来写的是
            #       `b64ToAudioBuffer(msg.pcm24k, msg.sample_rate || 16000)`
            #     ⇒ 服务端**没带** `sample_rate` 字段 ⇒ 插件按 **16 kHz** 重建
            #       AudioBuffer ⇒ 24 kHz 的波形被当成 16 kHz 播放
            #       ⇒ **语速快 1.5×、音调整体升高**（≈7 个半音）
            #       ⇒ 用户听到的是「完全听不出在说什么」。
            #   ⇒ 现在服务端**显式**声明采样率，插件按它重建。
            #   ⚠️ 仍然保留插件侧的兜底（老服务端没有这个字段时按 16 kHz），
            #     但**新服务端必须带**（见 `test_ext028_dub_audio_chain.py`）。
            "sample_rate": TTS_SAMPLE_RATE,
            # ★★ EXT-028 ①：PCM 的**格式**也显式声明（别让插件猜）。
            "pcm_format": "s16le",
            "pcm_channels": 1,
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
            # ★★★★★★ EXT-036 ①：**墙钟**（跨进程可比）时刻。
            #   ## 为什么必须加
            #     reviewer 的原话：「这 7 s 要么是下行或收口真的慢了 7 s，
            #     要么是两边 t0 对不上……**要做的**：每段在同一个时钟上记下
            #     服务端发出时刻和插件收到时刻……**先证明这 7 s 是哪一种**」。
            #   ⇒ 服务端这一侧必须给出**可与插件墙钟直接相减**的时刻。
            #     `time.time()` = Unix 墙钟（毫秒级）⇒ 与浏览器 `Date.now()`
            #     **同一时基** ⇒ 两边相减即真实的下行耗时。
            #   ⚠️ `tts_ready_at` 是 `perf_counter()`（**单调钟**）
            #     ⇒ **不能**与插件的 `Date.now()` 相减 ⇒ 必须另给墙钟。
            #   ★ `srv_wall_ms` = 服务端**产出这个任务**（收口完成）的墙钟。
            "srv_wall_ms": int(time.time() * 1000.0),
            # ★ 服务端自己的音频轴原点（会话建立时刻，墙钟）
            #   ⇒ 插件可核对「服务端轴」与「播放端轴」的差。
            "srv_t0_wall_ms": int(self._t0_wall_ms),
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
            **self.bg_stats(),
            # ★★ T-1：抓流方式（'tabCapture' | 'getDisplayMedia' | None）
            #   ⇒ EXT-005 ①「tabCapture 生产路径有没有被实测过」
            #     **终于可以从数据核对**，不用人读日志猜。
            #   ⚠️ 没上报就是 None（null）—— 绝不臆造 'tabCapture'。
            "capture_mode": self.capture_mode,
            "client_source": self.client_source,
            "source_rate": self.source_rate,
            # ★★ T-3：客户端请求的目标语言 / 音色
            #   ⇒ reviewer 能从 stats 直接确认「这轮面板上选的是什么」。
            #   ⚠️ 没上报就是 None（null）—— 绝不臆造。
            "client_target_lang": self.client_target_lang,
            "client_voice": self.client_voice,
            # ★★ T-4：这一轮**实际生效**的目标语言。
            #   ⚠️ 与 `client_target_lang` 区分开：
            #     前者 = 面板上选了什么；后者 = 真正用来翻译/合成的是什么。
            #   ⚠️ 没跑过任何一句 = None（null）⇒ 绝不臆造。
            "applied_target_lang": self.applied_target_lang,
            # ★★★ EXT-024 E：**分开**的三段计数（插件状态条直接用）。
            #   ⚠️ **为什么不能沿用一个 `n_segments`**：
            #     `n_segments`（在 `margin` 里）只说明「收口了几段」，
            #     **不能**区分「ASR 出文本 / MT 出译文 / TTS 出音频」
            #     ⇒ 若三者共用一个数，「TTS 0 段」这种关键故障信号
            #       永远不会出现（只要收口过一段它就 >0）。
            #   口径：asr=有非空文本 / mt=有非空译文 / tts=有音频。
            "asr_segments": self._n_asr_segments,
            "mt_segments": self._n_mt_segments,
            "tts_segments": self._n_tts_segments,
            "speaker": self.tracker.stats(),
            # ★★★ EXT-029 ③：**说话人旁路**的指标。
            #   ⚠️ 没接旁路 ⇒ `spk_bypass` = None ⇒ 这组是
            #     `{"enabled": false, ...}`，**不臆造**任何数字。
            "spk_bypass": (self.spk_bypass.stats()
                           if self.spk_bypass is not None else
                           {"enabled": False,
                            "spk_queue_drop": 0,
                            "spk_worker_busy_ms": 0.0,
                            "note": "本会话未接说话人旁路"
                            "（EXT-029：串行会话无 GPU 互斥锁 ⇒ 不接）"}),
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
            # ★★ T-5 修正：统计量改由**累计量**给出，
            #   不再依赖「保留窗口的大小」⇒ 裁剪历史后口径不变。
            #   ⚠️ 均值按**与旧实现相同的四舍五入值**求和
            #     （旧实现是对 round(delay,4) 求平均）⇒ 数字口径一致。
            "feed_arrival_delay": {
                "n_frames_measured": self._n_frames_measured,
                "n_frames_late_gt_1s": self._n_frames_late,
                "late_ratio": (round(self._n_frames_late
                                     / self._n_frames_measured, 4)
                               if self._n_frames_measured else None),
                "max_delay_sec": round(self._max_frame_arrival_delay, 4),
                "mean_delay_sec": (
                    round(self._sum_frame_arrival_delay
                          / self._n_frames_measured, 4)
                    if self._n_frames_measured else None),
                "last_delay_sec": (self._frame_arrival_delays[-1]["delay_sec"]
                                   if self._frame_arrival_delays else None),
                # ★ T-5：如实暴露「保留窗口」大小（便于核对内存口径）
                "history_window": C.FRAME_DELAY_HISTORY,
                "history_kept": len(self._frame_arrival_delays),
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

    # ── ★★ T-5：段级时刻表的**有界化** ──────────────────────────
    def _trim_seg_timing_history(self) -> None:
        """把 `_seg_orig_end` / `_seg_ready` 裁剪到最近 N 段。

        ## 为什么需要（P2「30 分钟不崩、内存不持续增长」）

        实测（读源码 + 全仓 grep）：这两个字典**只写不读** ——
        唯一的写入点是 `_process_segment` / `_finalize_segment` 里的
        `self._seg_orig_end[seg_id] = orig_end` 与
        `self._seg_ready[seg_id] = ready_at`，
        **没有任何读取点**（`tools/`、`tests/` 也都搜不到引用）。
        ⇒ 每收一段就**永久**多留两个 key ⇒
          30 分钟会话（≈100 段）会累积数百项，虽不大但**单调增长**。

        ⇒ 裁剪成「最近 C.SEG_TIMING_HISTORY 段」⇒ 内存**恒定**。
        ⚠️ 因为**无读取点**，裁剪**不影响任何统计口径**。

        ⚠️ **线程安全**：`_process_segment` 与 `_finalize_segment`
        可能被不同线程调用（EXT-010 流水线：收口线程串行调用，
        但 `_process_segment` 也在上行线程跑）⇒ 用一把锁保护，
        避免「裁剪时字典被改」导致 RuntimeError。
        """
        cap = C.SEG_TIMING_HISTORY
        with self._seg_timing_lock:
            if len(self._seg_orig_end) > cap:
                # dict 保持插入序 ⇒ 前面的就是最旧的
                for k in list(self._seg_orig_end.keys())[:len(self._seg_orig_end) - cap]:
                    self._seg_orig_end.pop(k, None)
            if len(self._seg_ready) > cap:
                for k in list(self._seg_ready.keys())[:len(self._seg_ready) - cap]:
                    self._seg_ready.pop(k, None)

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
            # ★★ 2026-11-05 EXT-039 ①：**修正「丢句」口径**。
            #   原式 `sum(1 for m in rows if not m.get("has_tts"))`
            #   把「**源语音区间之外的静音填充段**」（`src_len == 0` ⇒ ASR 空）
            #   也算成丢句 ⇒ 实测 180 s 素材下 **n_dropped_dub = 19**
            #   （实际丢句 = 0，19 段全是素材尾部静音填充段）。
            #   ⇒ 与 EXT-009「丢句 = 0」**直接冲突**，也会让 reviewer
            #     误判为「丢了 19 句」。
            #   ⇒ 修正：**只有「有源文本（src_len > 0）却没产出 TTS 音频」
            #     的段**才算丢句；静音填充段**单列**，不计入丢句。
            "n_dropped_dub": sum(1 for m in rows
                                  if not m.get("has_tts")
                                  and (m.get("src_len") or 0) > 0),
            # ★ 单列：素材尾部静音填充段（**不是**丢句）
            "n_silent_fill_segments": sum(1 for m in rows
                                         if not m.get("has_tts")
                                         and (m.get("src_len") or 0) == 0),
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
                 engine=None, audio_dump=None,
                 spk_bypass_enabled: bool = False) -> None:
        super().__init__(token, delay_sec=delay_sec, engine=engine,
                         audio_dump=audio_dump)
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
            # 11-08: MT on NPU => not serialized with ASR on GPU.0
            mt_lock=(contextlib.nullcontext()
                     if str(getattr(engine, "mt_device", "")).upper() == "NPU" else None),
        )
        self._seg_index = 0
        # ★★★ EXT-029 ①/④：**说话人旁路**（独立线程 + 有界队列）。
        #   ## 为什么放在这里（而不是基类）
        #     旁路的**嵌入**（wespeaker）实测**只有 GPU.0 能编译**
        #     ⇒ 必须与 ASR/MT **共用同一把** `self._device_lock`
        #       （公平 FIFO ⇒ ASR 最多多等一次 embed ⇒ 不会饿死）。
        #     ⇒ 只有**持有那把锁**的流水线会话才能正确接旁路。
        #   ## 设备摆放（实测 2026-11-01）
        #     * 旁路**分段**（pyannote）→ **NPU**（实测可编译）
        #       ⇒ **完全不碰 GPU.0** ⇒ 不与 ASR 抢 GPU。
        #     * 旁路**嵌入**（wespeaker）→ **GPU.0**（实测唯一可编译）
        #       ⇒ 共用 `_device_lock`，持锁总时长即 **ASR 额外延迟上界**
        #         （记 `spk_gpu_lock_held_ms`，按 EXT-029 ④ 上报）。
        #   ⚠️ 旁路加载失败 ⇒ **安静降级**（字幕没有说话人标签，
        #     其余行为逐字不变）⇒ 绝不打断音频链路。
        self.spk_bypass_enabled = bool(spk_bypass_enabled)
        if self.spk_bypass_enabled:
            try:
                from .speaker_bypass import SpeakerBypass
                self.spk_bypass = SpeakerBypass(
                    device_lock=self._device_lock,
                    on_label=self._on_spk_label,
                    on_log=lambda m: _log("旁路：%s" % m))
                self.spk_bypass.start()
                _log("★ EXT-029①：说话人旁路已启动"
                     "（独立线程 + 有界队列 + 异步回填）")
            except Exception as e:
                self.spk_bypass = None
                self.spk_bypass_enabled = False
                _log("⚠️ EXT-029：说话人旁路创建失败（降级：字幕无说话人标签）："
                     "%s: %s" % (type(e).__name__, e))

    # ── 阶段函数（各自在流水线线程里跑） ────────────────────────
    def _catch_up_skip(self, job, stage: str) -> bool:
        """11-09: segment already hopelessly late when this stage picks it up => skip (drain backlog)."""
        if self._engine is None:
            return False
        late = time.perf_counter() - (self.t0 + job.t_start + self.delay_sec)
        if C.LATE_DROP_SEC <= 0 or late <= C.LATE_DROP_SEC:   # v0.4.15: 0 = never skip
            return False
        self._n_catchup = getattr(self, "_n_catchup", 0) + 1
        if self._n_catchup <= 3 or self._n_catchup % 10 == 0:
            _log("[sync] 段 %s 进入%s时已晚 %.1f s（>%.0f s）=> 跳过（追赶实时，累计 %d 段）"
                 % (job.seg_id, stage, late, C.LATE_DROP_SEC, self._n_catchup))
        return True

    def _stage_asr(self, job) -> None:
        """ASR 阶段（在 ASR 线程里跑）。"""
        t0 = time.perf_counter()
        text = ""
        if self._catch_up_skip(job, "识别"):
            job.asr_sec = 0.0
            job.text = ""
            return
        if self._engine is not None:
            try:
                text = self._engine.asr(job.audio, job.t_start, job.t_end) or ""
            except Exception as e:
                _log(f"ASR 失败（段 {job.seg_id}）: {e}")
                # ★ EXT-010：如实标记（**不丢段**）⇒ 收口时进 `error` 字段
                job.mark_error("asr", e)
        job.asr_sec = time.perf_counter() - t0
        job.text = text
        # 11-08 reviewer: 克隆说话人——把定稿段喂给说话人旁路（不阻塞，失败只记日志）
        _cv = self._clone_mgr()
        if _cv is not None:
            if self._bg_wants_vocals():
                # v0.4.19: clone / voice guard use the separated vocals of this sentence (they arrive a
                #   few seconds later); queued in order, never blocks ASR; falls back to the original.
                with self._clone_pending_lock:
                    self._clone_pending.append((job.seg_id, job.audio, job.t_start, job.t_end,
                                                job.text, time.monotonic()))
                self._pump_clone_pending()
            else:
                try:
                    _cv.on_segment(job.seg_id, job.audio, job.t_start, job.t_end, text=job.text)
                except Exception as e:
                    _log(f"克隆旁路失败（段 {job.seg_id}）: {e}")

    def _stage_mt(self, job) -> None:
        """MT 阶段（在 MT 线程里跑）。"""
        t0 = time.perf_counter()
        tgt = ""
        # ★★ T-4：流水线路径同样要真正用上**面板上选的目标语言**
        #   （与串行路径 `_process_segment` 同一口径）。
        _tgt_lang = self._effective_target_lang()
        if job.text and self._catch_up_skip(job, "翻译"):
            job.mt_sec = 0.0
            job.tgt = ""
            job.text = ""          # else the TTS stage would read the English text
            return
        if self._engine is not None and job.text:
            try:
                tgt = self._mt_with_lang(job.text, _tgt_lang) or ""
            except Exception as e:
                _log(f"MT 失败（段 {job.seg_id}）: {e}")
                job.mark_error("mt", e)
        job.mt_sec = time.perf_counter() - t0
        job.tgt = tgt

    def _stage_tts(self, job) -> None:
        """TTS 阶段（在 TTS 线程里跑）。"""
        # spk / voice：EXT-002 —— 定稿先出，spk 可能为 None
        #   ⇒ 这段在**提交时**就已确定（spk 旁路不阻塞定稿）。
        #   ★ EXT-029 ②：`_resolve_spk` 只查表 ⇒ 标签未到就是 None
        #     ⇒ **不等** ⇒ 走方案 A（上一句音色 / 预设 A）。
        job.spk = self._resolve_spk(job.seg_id, job.t_start, job.t_end)
        self.tracker.register_pending(job.seg_id, job.spk,
                                       job.t_start, job.t_end)
        job.voice = self._pick_voice(job.spk)
        # 11-08 reviewer: 面板选 clone ⇒ 用该句说话人的已登记参考（wav 路径）；未到 ⇒ 预设 A
        _cv = self._clone_mgr()
        if _cv is not None:
            try:
                # 11-08 测试3：有余量时短等这一句的说话人标签（旁路窗口 5 s，标签常晚到）
                _slack = (self.t0 + job.t_start + self.delay_sec) - time.perf_counter()
                _wait = min(C.CLONE_LABEL_WAIT_SEC, max(0.0, _slack - C.CLONE_LABEL_RESERVE_SEC))
                _v = _cv.voice_for(job.seg_id, wait=_wait)
                # 11-09 user: "first clone > 10 s" => no registered voice for this sentence yet
                #   => clone it from its own audio (x-vector) right away
                # v0.4.11 (user 11-12: voice switched between sentences of one speaker): a
                #   sentence without a label no longer gets its own self_ref clone; it keeps the
                #   current voice. A new labeled speaker gets ONE self_ref until anchored.
                _lab = _cv.spk_of(job.seg_id) or ""
                _last = getattr(self, '_last_clone_voice', None)
                if _v:
                    job.voice = _v
                elif _lab:
                    _pv = self.__dict__.setdefault('_pending_voice', {})
                    if not (_pv.get(_lab) and os.path.exists(_pv[_lab])):
                        _pv[_lab] = _cv.self_ref(job.seg_id)
                    job.voice = _pv[_lab] or _last or C.PRESET_VOICE
                elif (_last and os.path.exists(_last)
                      and not (os.path.basename(_last).startswith('self_') and _cv.latest_path())):
                    job.voice = _last
                elif _last and os.path.exists(_last):
                    # v0.4.17: the current voice is a one-sentence clone (self_) but a real
                    #   speaker voice is registered now => move to it (user 11-17: S1 was registered
                    #   2 min in, yet every sentence stayed on the bad self_0); the guard below still
                    #   checks the sentence against it. v0.4.18: NOT for guard_ voices - those are the
                    #   guard's verified voice for a speaker the diarizer merged into another label; moving
                    #   back to the label's voice made unguardable short sentences flip (user 11-17)
                    job.voice = _cv.latest_path()
                else:
                    job.voice = _cv.self_ref(job.seg_id) or _cv.latest_path() or C.PRESET_VOICE
                # v0.4.15: voice guard - never dub a sentence with a voice it clearly does not match
                if job.voice and job.voice != C.PRESET_VOICE:
                    job.voice, _g = _cv.guard_voice(job.seg_id, job.voice)
                if job.voice and job.voice != C.PRESET_VOICE:
                    self._last_clone_voice = job.voice
                job.spk = job.spk or (_cv.spk_of(job.seg_id) or None)
                _log("[spk] 段 %s 标签=%s 音色=%s（等标签 %.1f s）" % (
                    job.seg_id, _cv.spk_of(job.seg_id) or "-",
                    os.path.basename(job.voice) if job.voice else "-", _wait))
            except Exception as e:
                _log(f"克隆选音色失败（段 {job.seg_id}）: {e}")
                job.voice = C.PRESET_VOICE

        # 11-08 test 4: decide the late drop BEFORE synthesis. Synthesizing a sentence that is
        #   dropped afterwards costs the full TTS time, so the backlog never drained and every
        #   later dub was dropped too (user: "translation and voice stopped").
        _txt = job.tgt or job.text or ""
        _cjk = sum(1 for ch in _txt if "\u3000" <= ch <= "\u9fff")
        _est = C.TTS_EST_RTF * (_cjk / 4.5 + (len(_txt) - _cjk) / 14.0)
        _deadline = self.t0 + job.t_start + self.delay_sec
        _start = max(_deadline, time.perf_counter() + _est, getattr(self, "_play_end_est", 0.0))
        if self._engine is not None and _txt and C.LATE_DROP_SEC > 0 and _start - _deadline > C.LATE_DROP_SEC:
            self._n_skip_tts = getattr(self, "_n_skip_tts", 0) + 1
            _log("[sync] 段 %s 预计晚 %.1f s（>%.0f s）=> 跳过合成、只出字幕（累计 %d 句）"
                 % (job.seg_id, _start - _deadline, C.LATE_DROP_SEC, self._n_skip_tts))
            job.tts_sec = 0.0
            job.pcm24k = None
            job.speech_sec = 0.0
            job.ready_at = time.perf_counter()
            return

        t0 = time.perf_counter()
        pcm24k = None
        speech_sec = 0.0
        # ★★ T-4：与串行路径同一口径 —— 真正用上面板选的目标语言。
        _tgt_lang = self._effective_target_lang()
        if self._engine is not None:
            try:
                pcm24k, speech_sec = self._tts_with_lang(job.tgt or job.text,
                                                          job.voice, _tgt_lang)
            except Exception as e:
                _log(f"TTS 失败（段 {job.seg_id}）: {e}")
                job.mark_error("tts", e)
        job.tts_sec = time.perf_counter() - t0
        job.pcm24k = pcm24k
        job.speech_sec = speech_sec
        job.ready_at = time.perf_counter()
        # 11-09 user: timbre drift => offer the dub as the speaker's anchor reference
        if pcm24k and self._clone is not None:
            try:
                self._clone.offer_dub(job.spk or self._clone.spk_of(job.seg_id), job.voice,
                                      job.tgt or "", pcm24k)
            except Exception as e:
                _log(f"音色锚定失败（忽略）: {e}")

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
        _task = (result[0] if result else None) if isinstance(result, list) else result
        if (isinstance(_task, dict) and _task.get("type") == "tts" and _task.get("pcm24k")
                and self._bg_wants_vocals()):
            # v0.4.19 onset alignment, NON-blocking: the dub goes out now; when this segment's separated
            #   vocals arrive (before its play time) pop_bg_tasks sends a `dub_shift` with the real onset.
            with self._clone_pending_lock:
                self._onset_pending.append((str(_task.get("id")), float(job.t_start), float(job.t_end),
                                            self.t0 + float(job.t_start) + float(self.delay_sec)))
        return _task

    # ── 派发钩子：提交到流水线 ──────────────────────────────────
    def _dispatch_segment(self, seq: int, abs0: int, abs1: int,
                          seg_audio: np.ndarray, *,
                          audio_complete_at: float) -> list:
        """提交一段到流水线；返回**已就绪**的任务（通常为空）。"""
        t_start = abs0 / C.SAMPLE_RATE
        t_end = abs1 / C.SAMPLE_RATE
        seg_id = f"seg_{abs0}"
        # ★★★ EXT-029 ②：**流水线也必须向旁路要标签**。
        #   ## 真实缺陷（2026-11-01 实测抓到的）
        #     基类 `_dispatch_segment()` 里有 `_request_spk_label(abs0, abs1)`，
        #     但 `PipelineSession` **覆盖**了这个方法（原实现不调基类）
        #     ⇒ 流水线会话**从不**向旁路登记定稿段
        #     ⇒ 实测 `n_final_req=0` / `n_label=0`（旁路只喂音频、从不产出标签）
        #     ⇒ 段级表里 `spk` 全是 `null`、`spk_pending=true`（永远等不到）。
        #   ## 修法
        #     在这里补上同样的调用（**零阻塞**，只 append）
        #     ⇒ 流水线（= 生产路径）也能拿到说话人标签。
        self._request_spk_label(abs0, abs1)
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
        # ★★★★★★ EXT-037 ②：跳过「已交付但仍在缓冲里」的前缀
        #   （与基类 `flush()` 同一口径 ⇒ 不重叠、不重复配音）
        _prefix = int(self._buf_delivered_prefix or 0)
        if _prefix > 0:
            _prefix = min(_prefix, int(self._buf.shape[0]))
            self._buf = self._buf[_prefix:]
            self._buf_delivered_prefix = 0
        if self._buf.shape[0] < int(1.0 * C.SAMPLE_RATE):
            # 尾部不足 1 s ⇒ 没有有意义的语音段，丢弃（不计为段）
            self._buf = np.zeros((0,), dtype=np.float32)
            return []
        abs0 = self._buf_base
        abs1 = self._buf_base + self._buf.shape[0]
        seg_audio = self._buf
        self._buf = np.zeros((0,), dtype=np.float32)
        self._buf_base += seg_audio.shape[0]
        self._consumed_samples = self._buf_base
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
        try:
            if self._bg_sep is not None:
                self._bg_sep.stop()
        except Exception:
            pass
        # ★ EXT-029：停掉旁路 worker（**优雅**：先放哨兵再 join）。
        try:
            if self.spk_bypass is not None:
                self.spk_bypass.stop()
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
                  use_pipeline: bool = False, audio_dump=None,
                  spk_bypass: bool = False) -> "Session":
    """建会话（★ EXT-010：可选**流水线**模式）。

    * `use_pipeline=False` ⇒ 串行 `Session`（**原有行为完全不变**，
      旧自测全部针对这条路径）；
    * `use_pipeline=True`  ⇒ `PipelineSession`（句级并行）。

    ⚠️ **回声模式不用流水线**（echo 是逐帧原样返回，没有分段/推理）。
    ★ EXT-028 ①：`audio_dump` 传给会话 ⇒ 逐段落盘 TTS 原始输出与 WS 字节。
    ★ EXT-029 ①：`spk_bypass=True` ⇒ 流水线会话**接说话人旁路**
      （独立线程 + 有界队列 + 异步回填）。
      ⚠️ 串行会话**不接**（没有 GPU 互斥锁 ⇒ 旁路会饿死 ASR）。
    """
    if use_pipeline and engine is not None:
        _log("★ 使用流水线会话（EXT-010：ASR/MT/TTS/收口 各一线程）")
        return PipelineSession(token, delay_sec=delay_sec, engine=engine,
                               audio_dump=audio_dump,
                               spk_bypass_enabled=bool(spk_bypass))
    if spk_bypass:
        _log("⚠️ EXT-029：串行会话不接说话人旁路"
             "（无 GPU 互斥锁 ⇒ 旁路会饿死 ASR）")
    return Session(token, delay_sec=delay_sec, engine=engine,
                   audio_dump=audio_dump)


async def handle_ws(websocket, *, tokens: TokenStore, delay_sec: float,
                    echo_mode: bool, engine=None,
                    session_holder: Optional[dict] = None,
                    margin_out: Optional[str] = None,
                    use_pipeline: bool = False,
                    registry: Optional["ConnectionRegistry"] = None,
                    mode: str = "echo",
                    audio_dump=None,
                    spk_bypass: bool = False) -> None:
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

    ★★ EXT-024 A：现在**多了一条连接**（player 的下行连接）
       ⇒ 光「不顶替」还不够：会话的**归属**必须能被找到。
       ⇒ 每条连接都登记进 `registry`（带 role），下行任务按
         `registry.downlink_targets(token, origin_conn_id=...)` 广播
         给「产生它的连接 + 同 token 的 player 连接」。
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
        # v0.4.0：用户取消 token 配对 ⇒ 不再校验 token；所有连接共用一个会话键
        token = NO_PAIR_TOKEN
        _log(f"已连接（无配对，role={first.get('role')}）")
        session = _make_session(token, delay_sec=delay_sec, engine=engine,
                                 use_pipeline=use_pipeline,
                                 audio_dump=audio_dump,
                                 spk_bypass=spk_bypass)
        conn_id = (registry.next_id() if registry is not None else None)
        _role0 = classify_role(first)
        if registry is not None:
            registry.add(conn_id, websocket=websocket, token=token,
                         role=_role0, session=session)
        session.client_role = _role0
        _register_session(session_holder, session, role=_role0)
        try:
            await _handle_messages(websocket, session=session,
                                   first=first, echo_mode=echo_mode,
                                   delay_sec=delay_sec,
                                   engine=engine,
                                   margin_out=margin_out,
                                   session_holder=session_holder,
                                   registry=registry, conn_id=conn_id,
                                   mode=mode, audio_dump=audio_dump)
        finally:
            _release_session(session_holder, session)
            if registry is not None and conn_id is not None:
                registry.remove(conn_id)
        return
    token = NO_PAIR_TOKEN  # v0.4.0：不再校验 token

    _log(f"已连接（origin={origin}）")
    session = _make_session(token, delay_sec=delay_sec, engine=engine,
                             use_pipeline=use_pipeline, audio_dump=audio_dump,
                             spk_bypass=spk_bypass)
    conn_id = (registry.next_id() if registry is not None else None)
    if registry is not None:
        # ★ 角色未知的连接**不当 player**（见 classify_role 的说明）。
        registry.add(conn_id, websocket=websocket, token=token, role=None,
                     session=session)
    session.client_role = None
    _register_session(session_holder, session, role=None)
    try:
        await _handle_messages(websocket, session=session, first=None,
                               echo_mode=echo_mode, delay_sec=delay_sec,
                               engine=engine,
                               margin_out=margin_out,
                               session_holder=session_holder,
                               registry=registry, conn_id=conn_id,
                               mode=mode, audio_dump=audio_dump)
    finally:
        _release_session(session_holder, session)
        if registry is not None and conn_id is not None:
            registry.remove(conn_id)


def _register_session(session_holder: Optional[dict], session,
                      *, role: Optional[str] = None) -> None:
    """把会话登记进 holder —— **但绝不顶替已有的活跃会话**（缺陷 15）。

    为什么要这样：见 `handle_ws` 的缺陷 15 说明。
    编排器的「双保险」会另开一条连接来请求落盘；若那条连接顶替了
    真会话，`dump_margin` 落的就是**空统计**，把真数据覆盖掉。

    ★★ EXT-024 B：**uplink 接管**。
      现在一条 token 可以同时有「uplink 连接」和「player 连接」两条
      ⇒ 后建的那条会话**不能**顶替先建的那条（否则 player 的会话
      会被 uplink 的空会话顶掉 ⇒ 统计/HUD 读到的都是错的）。
      ⇒ 但**新的 uplink 连接**必须能接管旧的 uplink 会话
      （EXT-024 B 明文：「同一时刻只允许一个 uplink 会话，
      新 uplink 接管时旧会话要停掉流水线线程」）。
      ⇒ 靠 `role` 区分：
        * `role == 'uplink'` 且 holder 里的旧会话**也是 uplink**
          ⇒ **接管**：停掉旧会话的流水线线程，holder 指向新会话；
        * 其它情况（player 连接 / 探针）⇒ **不顶替**（保持缺陷 15 的语义）。
    """
    if session_holder is None:
        return
    # ★★ EXT-024 A：uplink 的会话是「**产出会话**」——
    #   真正跑 ASR/MT/TTS、产出段的就是它
    #   ⇒ popup 的 /status、margin.json 都要读它
    #   （否则读 player 的空会话 ⇒ 段数/滞后恒为 0）。
    if role == "uplink":
        old_prod = session_holder.get("producer_session")
        if old_prod is not None and old_prod is not session:
            # ★★ uplink 接管：旧的 uplink 会话要**停掉流水线线程**
            #   （EXT-024 B 明文：「同一时刻只允许一个 uplink 会话，
            #     新 uplink 接管时旧会话要停掉流水线线程」）。
            _log("★ 新的 uplink 连接接管旧 uplink 会话（EXT-024 B）")
            closer = getattr(old_prod, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass
            try:
                session_holder["last_session"] = old_prod
            except Exception:
                pass
        session_holder["producer_session"] = session

    existing = session_holder.get("session")
    if existing is session:
        # ★ 同一会话重复登记 ⇒ 不做任何顶替。
        return
    if existing is not None:
        old_role = getattr(existing, "client_role", None)
        if role == "uplink" and old_role == "uplink":
            # ★★ uplink 接管（旧的 uplink 会话正好挂在 holder 上）。
            _log("★ uplink 接管旧会话（EXT-024 B）")
            closer = getattr(existing, "close", None)
            if callable(closer):
                try:
                    closer()
                except Exception:
                    pass
            try:
                session_holder["last_session"] = existing
            except Exception:
                pass
            session_holder["session"] = session
            return
        _log("已有活跃会话 ⇒ 本连接不顶替（缺陷 15 修复：避免落盘空统计）")
        return
    session_holder["session"] = session


def _propagate_client_settings(holder: Optional[dict],
                               registry: Optional["ConnectionRegistry"],
                               token: Optional[str], session) -> None:
    """★★ EXT-024 A/G：把**面板设置**（语言 / 音色）在同 token 的会话间**互相同步**。

    ## 为什么需要

    面板在 popup 里设置，而**产出段的是 uplink 会话**。
    但**上报 hello 的可能是 player 连接**（EXT-024 修复后，浏览器端
    player 与 uplink 是两条连接）。
    ⇒ 若不传播：uplink 会话的 `client_target_lang` 是 None
    ⇒ 翻译按服务端启动参数（默认 en）走
    ⇒ **用户在面板上选的中文不生效**。

    ⇒ 现在：同 token 的所有会话**双向同步**「非 None」的语言/音色。

    ⚠️ **只同步「非 None」的** ⇒ 不覆盖对方已经报过的值
      （不臆造、不清空）。
    ⚠️ player 与 uplink 谁先连上都一样（互为补充）。
    """
    if holder is None:
        return
    sessions = []
    prod = holder.get("producer_session")
    if prod is not None:
        sessions.append(prod)
    cur = holder.get("session")
    if cur is not None and cur not in sessions:
        sessions.append(cur)
    if registry is not None and token:
        try:
            for info in registry.list():
                if info.get("token") != token:
                    continue
                s = info.get("session")
                if s is not None and s not in sessions:
                    sessions.append(s)
        except Exception:
            pass
    if session is not None and session not in sessions:
        sessions.append(session)
    if len(sessions) < 2:
        return
    # 收集「非 None」的值（先到先得）
    lang = None
    voice = None
    dly = None
    for s in sessions:
        v = getattr(s, "client_target_lang", None)
        if v and not lang:
            lang = v
        v = getattr(s, "client_voice", None)
        if v and not voice:
            voice = v
        v = getattr(s, "client_delay_sec", None)
        if v and not dly:
            dly = v
    # 11-09: panel delay is a user setting too (the uplink session produces the segments)
    if dly:
        for s in sessions:
            try:
                if not getattr(s, "client_delay_sec", None):
                    s.client_delay_sec = dly
                    s.delay_sec = dly
            except Exception:
                pass
    if not lang and not voice:
        return
    for s in sessions:
        try:
            if lang and not getattr(s, "client_target_lang", None):
                s.client_target_lang = lang
            if voice and not getattr(s, "client_voice", None):
                s.client_voice = voice
        except Exception:
            pass


def _is_empty_producer(sess) -> bool:
    """这个会话是不是「**没产出过段**」的空会话？

    ★ 用来区分「player 的接收会话」（永远空）与
      「uplink 的产出会话」（有段）。
    ⚠️ 判据只看**段数**，不猜别的。
    """
    try:
        return len(getattr(sess, "margins", []) or []) == 0
    except Exception:
        return True


def _producer_session(holder: Optional[dict], registry: Optional["ConnectionRegistry"],
                      token: Optional[str]) -> Any:
    """★★ EXT-024 A：取「**真正产出段**」的那个会话。

    ## 为什么需要

    修复 EXT-024 后，**同一条 token 上会有两个会话**：
      * **uplink 会话** —— 收 PCM、跑 ASR/MT/TTS，**真正产出段**；
      * **player 会话** —— 只负责接收下行，**永远是空的**。

    ⇒ 若 `stats()` / `margin.json` 读的是 player 的会话
      ⇒ **段数恒为 0** ⇒ reviewer 看到的是「没出过段」的假象
      （这正是用户 10-31 实测时的症状：popup/HUD 的段数全是 0）。

    ⇒ 现在：优先取 uplink 会话；没有 uplink 才回落到 holder 里的会话
      （单连接的老用法仍然正确）。
    """
    if registry is not None and token:
        try:
            sess = registry.producer_session(token)
            if sess is not None:
                return sess
        except Exception:
            pass
    if holder is None:
        return None
    return holder.get("session")


def _release_session(session_holder: Optional[dict], session) -> None:
    """★★ EXT-024 B：连接关闭时**清掉 holder**。

    ## 为什么要清（用户 10-31 实测抓到的真缺陷）

    旧实现里 `_register_session` 只在 holder 为空时登记，
    而连接关闭的 `finally` 里**从不清 holder**
    ⇒ 第一个会话（22:34:14）之后，所有新会话永远是「不顶替」
    ⇒ stats / HUD / popup 读到的**都是旧会话的数据**
    （用户日志里 22:34:22–22:37:14 每条新连接都打「已有活跃会话」）。

    ⇒ 现在：连接关闭 ⇒ 若 holder 里的 session **就是本会话**
      ⇒ 置空（并把它的统计归档到 `last_session`，供 reviewer 事后核对）
      ⇒ 并**停掉流水线线程**（否则旧会话的线程会一直跑）。
    """
    if session_holder is None:
        return
    try:
        # ★★ EXT-024 A/B：uplink 的产出会话也要清
        #   （否则 uplink 断了，popup 还在显示上一轮的段数）。
        prod = session_holder.get("producer_session")
        if prod is session:
            session_holder["producer_session"] = None
            try:
                session_holder["last_session"] = session
            except Exception:
                pass
        cur = session_holder.get("session")
        if cur is not session:
            return
        session_holder["session"] = None
        # ★ 归档：关掉之后 stats 还是能报「上一轮跑出了什么」
        try:
            session_holder["last_session"] = session
        except Exception:
            pass
        # ★ 停掉流水线线程（EXT-024 B：旧会话的流水线不能继续跑）
        closer = getattr(session, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass
        _log("连接关闭 ⇒ 已清空 holder['session']（EXT-024 B）")
    except Exception as e:
        _log(f"释放会话时出错（忽略）：{e}")


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


def _engines_ready(engine, mode: str) -> bool:
    """★★ EXT-024 F：三个引擎（ASR/MT/TTS）都就绪了吗？

    ⚠️ **诚实性**：绝不能因为 mode='real' 就报 True ——
      真实模式但模型还没加载完（用户点「开始」时正在预热）⇒ 必须报 False
      ⇒ popup 才能禁用「开始」按钮并写明「引擎未就绪」。
    ★ 回声模式不需要引擎 ⇒ 恒为 True（回声能正常工作）。
    ★ 引擎对象没有 `stats()`（自测桩）⇒ 保守判 False（真实模式）。
    """
    if mode == "echo":
        return True
    if engine is None:
        return False
    try:
        st = engine.stats()
        loaded = st.get("loaded") or {}
        return bool(loaded.get("asr") and loaded.get("mt")
                    and loaded.get("tts"))
    except Exception:
        return False


def _log_segment(task: dict, roles: List[str]) -> None:
    """★★ EXT-024 D：写**一行段级日志**。

    ## 为什么必须有（用户 10-31 实测抓到的真缺陷）

    用户日志里整个会话**没有一行段级日志**（ASR 段 / MT / TTS 下发）
    ⇒ reviewer **无法从日志判断有没有出过段**、更无法判断
      「配音到底下发给了谁」。

    ⇒ 现在每段一行，含：
      * 段 id、t_start / t_end（会话秒）；
      * ASR 原文前 30 字、MT 译文前 30 字；
      * TTS 时长（speech_sec）；
      * **下发到了哪些连接**（角色名）—— ★ 这是 EXT-024 的关键证据：
        下发到 player 连接 ⇒ 用户能听到配音。

    ⚠️ **不臆造**：字段缺失就写 `—`，绝不编。
    """
    def _cut(v, n=30):
        if v is None:
            return "—"
        s = str(v).replace("\n", " ").strip()
        return (s[:n] + "…") if len(s) > n else (s or "—")

    # 11-06 (reviewer): per-stage compute seconds added, to find which stage
    #   cannot keep up in real time (user: dub lag keeps growing).
    _log("段 %s | t_start=%.3f t_end=%.3f | ASR=%r | MT=%r | TTS=%.2fs"
         " | 耗时 asr=%.2f mt=%.2f tts=%.2f | 倍率=%s | 下发到=%s"
         % (task.get("id", "?"),
            float(task.get("t_start") or 0.0),
            float(task.get("t_end") or 0.0),
            _cut(task.get("src")),
            _cut(task.get("tgt")),
            float(task.get("speech_sec") or 0.0),
            float(task.get("asr_sec") or 0.0),
            float(task.get("mt_sec") or 0.0),
            float(task.get("tts_sec") or 0.0),
            task.get("total_rate", task.get("speed", "—")),
            ",".join(roles) if roles else "无"))


async def _handle_messages(websocket, *, session: "Session", first: Optional[dict],
                           echo_mode: bool, delay_sec: float,
                           engine=None,
                           margin_out: Optional[str] = None,
                           session_holder: Optional[dict] = None,
                           registry: Optional["ConnectionRegistry"] = None,
                           conn_id: Optional[str] = None,
                           mode: str = "echo",
                           audio_dump=None) -> None:
    """消息循环。`first` 若已读过则先处理它。

    ★★ EXT-024 A：**下行任务按连接广播**。
      旧实现只 `websocket.send` 回本连接 ⇒ 上行连接（无 onmessage）
      产出的 `tts` 被丢弃 ⇒ 用户只听到延迟原声、没有配音也没有字幕。
      ⇒ 现在用 `_broadcast_task()` 发给「产生它的连接 + 同 token 的
        role='player' 连接」。
    """

    async def _broadcast_task(task: dict) -> int:
        """把一个下行任务发给该发的连接。返回**实际送达的连接数**。

        ★ 没有 registry（老调用方 / 单连接自测）⇒ 退回旧行为：
          只发本连接。
        ★★ EXT-024 D：每个 `tts` 任务都写**一行段级日志**
          （id / t_start / t_end / ASR 前 30 字 / MT 前 30 字 /
          TTS 秒数 / 下发到哪个连接）
          ⇒ 之前整个过程**没有一行段级日志** ⇒ reviewer 无法判断
            「有没有出过段」「下发到了谁」。
        """
        if registry is None or conn_id is None:
            await websocket.send(json.dumps(task))
            if task.get("type") == "tts":
                _log_segment(task, ["本连接"])
            return 1
        targets = registry.downlink_targets(session.token,
                                             origin_conn_id=conn_id)
        if not targets:
            # ★ 没有别的目标 ⇒ 至少发回本连接（保持旧行为，
            #   探针/单连接客户端不能收不到任务）。
            targets = [conn_id]
        sent = 0
        sent_roles: List[str] = []
        for cid in targets:
            info = registry.get(cid)
            if info is None:
                continue
            try:
                await info["websocket"].send(json.dumps(task))
                sent += 1
                sent_roles.append(str(info.get("role") or "probe"))
            except Exception as e:
                _log(f"下发到连接 {cid} 失败（忽略）：{e}")
        if task.get("type") == "tts":
            _log_segment(task, sent_roles)
        return sent

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
                # ★★ T-1：hello 里带 **capture_mode**（抓流方式）⇒
                #   记进会话 ⇒ 后面 stats / margin.json 都能报出来。
                #   （旧的客户端不带这个字段 ⇒ 记成 None ⇒ 输出 null，
                #     **向后兼容**：不改 hello_ack 的结构，旧客户端不受影响。）
                session.note_client(msg)
                if not echo_mode and "bg_keep" in msg:
                    session.set_bg_keep(bool(msg.get("bg_keep")))
                # ★★ EXT-024 A：hello 里的 role 才是**权威**的角色来源
                #   （浏览器端不能自定义请求头 ⇒ token 走首个 hello；
                #    而用请求头带 token 的客户端（Python 探针）首个消息
                #    未必是 hello ⇒ 角色要等这条 hello 才确定）。
                #   ⇒ 收到 hello 就**更新**登记表里的角色。
                _role = classify_role(msg)
                if registry is not None and conn_id is not None:
                    if _role:
                        registry.set_role(conn_id, _role)
                    registry.set_session(conn_id, session)
                if _role:
                    session.client_role = _role
                    # ★ 角色变了 ⇒ 可能需要重新登记（uplink 接管）
                    _register_session(session_holder, session, role=_role)
                # ★★ EXT-024 A/G：面板上的语言/音色是**用户设置**，
                #   不是「某条连接的属性」⇒ 谁报了都生效。
                #   典型场景：player 连接（面板所在）报了 targetLang='Chinese'，
                #   而**产出段的是 uplink 会话** ⇒ 若不传播，
                #   uplink 会话就不知道要译成中文（用的是服务端启动参数）。
                # 11-09 user: "panel delay 6-20 s is always 20 s" => the panel value wins
                _dreq = msg.get("delay_sec")
                try:
                    _dreq = float(_dreq) if _dreq is not None else None
                except (TypeError, ValueError):
                    _dreq = None
                if _dreq is not None and _dreq > 0:
                    _dreq = min(C.CLIENT_DELAY_MAX, max(C.CLIENT_DELAY_MIN, _dreq))
                    if abs(_dreq - float(session.delay_sec)) > 1e-6:
                        _log(f"延迟 D：面板设置 {_dreq:.1f} s（原 {session.delay_sec:.1f} s）")
                    session.delay_sec = _dreq
                    session.client_delay_sec = _dreq
                _propagate_client_settings(session_holder, registry,
                                           session.token, session)
                # ★★ EXT-024 A/F：hello_ack 里补三个字段 ——
                #   `mode`（真实引擎 / 回声）、`engines_ready`、`pipeline`。
                #   ⚠️ **向后兼容**：只是**新增**字段，不动老字段
                #     （老客户端忽略未知字段）。
                await websocket.send(json.dumps({
                    "type": "hello_ack",
                    "delay_sec": session.delay_sec,
                    "sample_rate": C.SAMPLE_RATE,
                    "segmentation": describe_segmenter(),
                    # ★ T-1：回显服务端**实际记到的**抓流方式，
                    #   让客户端能立刻确认「服务端认出我这条路径了」。
                    "capture_mode": getattr(session, "capture_mode", None),
                    # ★★ EXT-024 F：当前连接的模式（真实引擎 / 回声）。
                    "mode": mode,
                    # ★★ EXT-024 F：引擎是否就绪。
                    #   ⚠️ **必须查引擎的真实 loaded 状态**，不能只看 mode
                    #     （mode='real' 但模型还没加载完 ⇒ 一律报 False
                    #      ⇒ popup 会禁用「开始」按钮并写明原因）。
                    #   回声模式不需要引擎 ⇒ 恒为 True。
                    "engines_ready": _engines_ready(engine, mode),
                    "pipeline": bool(isinstance(session, PipelineSession)),
                    # ★★★ EXT-026 ⑤：**会话标识** ⇒ 插件能识别「新会话」。
                    #   段 id 已带会话前缀（跨会话不撞号），
                    #   但插件侧仍可据此**清空**常驻的 seenDubIds
                    #   ⇒ 双保险（旧服务端没有前缀时也能自愈）。
                    #   ⚠️ 向后兼容：只是**新增**字段。
                    "session_id": getattr(session, "_session_epoch", None),
                    # v0.4.19 保留背景音: supported by this server? model present? current state
                    "bg_supported": (not echo_mode),
                    "bg_model": bool(_bgsep.default_model_path()),
                    "bg": session.bg_status(),
                }))
                continue
            if mtype == "pcm_bg":
                if not echo_mode:
                    session.on_pcm_bg(msg)
                    for task in session.pop_bg_tasks():
                        await _broadcast_task(task)
                continue
            if mtype == "bg_keep":
                if not echo_mode:
                    session.set_bg_keep(bool(msg.get("on")))
                    for task in session.pop_bg_tasks():
                        await _broadcast_task(task)
                continue
            if mtype == "capture_info":
                # ★★ T-1：客户端补报**实际抓流方式**。
                #   （offscreen 的 hello 早于抓流 ⇒ hello 里拿不到；
                #     player 的 hello 在抓流之后 ⇒ 直接带在 hello 里。）
                #   两条路径都汇到 `note_client`，字段口径一致。
                session.note_client(msg)
                continue
            if mtype == "player_log":
                # 11-08 reviewer: player-side state (video slow-down) into bridge.log
                _log("[player] " + str(msg.get("text", ""))[:400])
                continue
            if mtype == "client_metrics":
                # ★★★★★★ EXT-036 ①/②：客户端上报**实测**的下行耗时 /
                #   播放端排队 / 轴偏移 ⇒ 服务端据此把 `sync_rootcause`
                #   的三项空缺补上（此前**从不**上报 ⇒ 归因不完整）。
                #   ★ 记到**生产者会话**（uplink）⇒ 与 `per_segment` 同源。
                _cms = _producer_session(session_holder, registry,
                                        session.token) or session
                try:
                    _cms.note_client_metrics(msg)
                except Exception as e:      # pragma: no cover
                    _log("client_metrics 处理失败：%s" % e)
                continue
            if mtype == "stats":
                # ★★ EXT-010：流水线模式下，先把**已就绪**的任务下发，
                #   再回 stats（否则 stats 会比任务先到，客户端会误判段数）。
                if isinstance(session, PipelineSession):
                    for task in session._pipeline.pop_ready(block=False):
                        await _broadcast_task(task)
                # ★★ EXT-024 A：stats 要报**真正产出段的那个会话**
                #   （uplink 会话）⇒ 否则 player 连接查到的段数恒为 0。
                _sess = _producer_session(session_holder, registry,
                                          session.token)
                await websocket.send(json.dumps(
                    {"type": "stats", **(_sess.stats() if _sess is not None
                                         else session.stats()), **_proc_usage(),
                     **_dub_drops(_sess if _sess is not None else session)}))
                if not echo_mode:                  # v0.4.19: background blocks also flow when no audio arrives
                    for task in session.pop_bg_tasks():
                        await _broadcast_task(task)
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
                        await _broadcast_task(task)
                # ★★ EXT-010：流水线模式下，段是**异步**跑完的 ⇒
                #   每次收到帧后**顺手把已就绪的任务取走**下发。
                #   （未就绪的继续在流水线里跑，稍后由下一帧/flush/stats 取走。）
                if isinstance(session, PipelineSession):
                    for task in session._pipeline.pop_ready(block=False):
                        await _broadcast_task(task)
                if not echo_mode:
                    for task in session.pop_bg_tasks():
                        await _broadcast_task(task)
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
                    # ★★ EXT-024 A：落盘要写**真正产出段的会话**（uplink）
                    #   ⇒ 否则落盘的是 player 的空会话（段数 0）。
                    _sess = _producer_session(session_holder, registry,
                                              session.token)
                    _dump_margin(session_holder or {}, margin_out,
                                 engine, session=_sess)
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
                    session.bg_flush()
                    # ★ 同上：尾段也要走线程，避免尾段推理阻塞心跳
                    out = await asyncio.to_thread(session.flush)
                    for task in session.pop_bg_tasks():     # v0.4.19: don't hold background behind the drain
                        await _broadcast_task(task)
                    if out:
                        for task in out:
                            await _broadcast_task(task)
                    # ★★ EXT-010：流水线模式下，尾段也**异步**跑
                    #   ⇒ flush 之后必须**等流水线把剩下的段都跑完**，
                    #   否则尾段的配音任务来不及下发（客户端会等不到段数达标）。
                    if isinstance(session, PipelineSession):
                        _dr = asyncio.ensure_future(asyncio.to_thread(session.drain))
                        while not _dr.done():                  # keep delivering background while dubs drain
                            await asyncio.sleep(0.5)
                            for task in session.pop_bg_tasks():
                                await _broadcast_task(task)
                        for task in _dr.result():
                            await _broadcast_task(task)
                    for task in session.pop_bg_tasks():
                        await _broadcast_task(task)
                continue
    except Exception as e:
        _log(f"连接异常: {e}")
    finally:
        _log("连接关闭")


def _probe_port_free(host: str, port: int) -> tuple[bool, str]:
    """★ T-1：这个端口现在**能不能绑**？返回 (ok, 原因)。

    **为什么要在预热模型之前查**（2026-10-30 22:41 用户实测报错的根因）：
    旧流程是「先加载 24 秒模型 → 再 `serve()` 去 bind 端口」⇒
    端口被占用时，用户**白等 24 秒**才看到一整屏
    `OSError: [Errno 10048] 端口只允许使用一次` 的 Python traceback。

    ⇒ 现在：**预热之前**先 bind 一下试试 ⇒ 不行就**立刻**退出，
    给出人话提示（哪个端口、被谁占了、怎么办），退出码 6。

    实现：用 `socket.socket` + `bind` + `listen` 真试一次 ⇒ 绑完立刻关掉。
    ⚠️ 试完就释放 ⇒ 与真正的 bind 之间有个极小的竞态窗口；
      真 bind 那一层另有 `OSError` 兜底（见 `main()`），两道防线都在。
    """
    import socket as _socket
    s = None
    try:
        s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        # ★ Windows 上必须显式 SO_EXCLUSIVEADDRUSE：
        #   否则本机探测用的 bind 可能与后面真正的 bind「共存」，
        #   探测就会**假报空闲**。
        try:
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_EXCLUSIVEADDRUSE, 1)
        except (AttributeError, OSError):
            pass
        s.bind((host, port))
        s.listen(1)
        return True, ""
    except OSError as e:
        winerr = getattr(e, "winerror", None)
        if winerr == 10048 or e.errno in (10048, 48, 98):
            return False, ("端口 %d 已被占用（%s）"
                           % (port, getattr(e, "strerror", None) or e))
        return False, ("端口 %d 无法绑定：%s" % (port, e))
    except Exception as e:
        # 探测本身出错 ⇒ **放行**（不因为探测失败而拒绝启动）。
        return True, ""
    finally:
        try:
            if s is not None:
                s.close()
        except Exception:
            pass


def _describe_port_owner(port: int) -> str:
    """尽力查一下端口被谁占着（只作提示，不作判定）。"""
    try:
        import subprocess as _sp
        r = _sp.run(["netstat", "-ano"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=10)
    except Exception:
        return ""
    needle = ":%d" % port
    for line in (r.stdout or "").splitlines():
        # ⚠️ netstat 的行**前面有空格**（"  TCP    127.0.0.1:8765 ..."）
        #   ⇒ 不能用 startswith("TCP")（实测会漏掉所有行）⇒ 先 strip。
        parts = line.strip().split()
        if not parts or parts[0].upper() != "TCP":
            continue
        if needle not in line:
            continue
        if "LISTENING" not in line:
            continue
        if parts and parts[-1].isdigit():
            return "占用者 PID=%s" % parts[-1]
    return ""


async def serve(host: str, port: int, *, delay_sec: float, echo_mode: bool,
                token_path: str, engine=None, margin_out: Optional[str] = None,
                session_holder: Optional[dict] = None,
                use_pipeline: bool = False, audio_dump=None,
                spk_bypass: bool = False) -> None:
    import websockets

    tokens = TokenStore(token_path)
    _log(f"token 文件：{token_path}")
    _log(f"监听 ws://{host}:{port}（echo={echo_mode}, D={delay_sec}s，"
         f"pipeline={use_pipeline}）")
    # ★★ EXT-024 A：**连接登记表** —— 服务端据此把下行任务广播给
    #   「产生它的连接 + 同 token 的 role='player' 连接」。
    registry = ConnectionRegistry()
    # ★★ EXT-024 F：连接模式（真实引擎 / 回声）—— 放进 hello_ack。
    mode = "echo" if echo_mode else "real"
    def _handle_ws_inner(ws):
        return handle_ws(ws, tokens=tokens, delay_sec=delay_sec, echo_mode=echo_mode, engine=engine,
                              session_holder=session_holder,
                              margin_out=margin_out,
                              use_pipeline=use_pipeline,
                              registry=registry,
                              mode=mode, audio_dump=audio_dump,
                              spk_bypass=spk_bypass)

    # v0.3.8：对端网段闸门 + 单用户（按对端 IP 计）；v0.4.2：放到模块级，/status 也能报「谁在用」
    _active = ACTIVE_PEER

    async def _gated(ws):
        try:
            peer = (ws.remote_address or ("?",))[0]
        except Exception:
            peer = "?"
        if not C.peer_allowed(peer):
            _log(f"拒绝连接：对端 {peer} 不在允许的网段（LAN_MODE={C.LAN_MODE}）")
            await ws.close(code=1008, reason="peer not allowed")
            return
        if _active["n"] > 0 and _active["ip"] != peer:
            _log(f"拒绝连接：桥接正在服务 {_active['ip']}，{peer} 需等待（同一时间只服务一个用户）")
            await ws.close(code=1013, reason="busy: bridge in use by another user")
            return
        _active["ip"] = peer; _active["n"] += 1
        try:
            await _handle_ws_inner(ws)
        finally:
            _active["n"] -= 1
            if _active["n"] <= 0:
                _active["n"] = 0; _active["ip"] = None

    async with websockets.serve(
        _gated,
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
    ap.add_argument("--delay", type=float, default=20.0, help="延迟 D（秒）")
    ap.add_argument("--echo", action="store_true", help="P0 ③ 回声自测模式")
    ap.add_argument("--token-file", default=C.BRIDGE_TOKEN_FILE)
    # ── EXT-006：真实引擎（P1） ──────────────────────────────
    ap.add_argument("--real", action="store_true",
                    help="接入真实引擎（ASR→MT→TTS），EXT-006 P1")
    ap.add_argument("--target-lang", default="en",
                    help="目标语言（en/zh/ja/...），TTS 会显式传给它")
    ap.add_argument("--margin-out", default=None,
                    help="把余量统计与时间表落盘到这个 JSON")
    # ★★★★ EXT-028 ①：逐段音频落盘目录。
    #   落了 (a) TTS 原始输出 wav + (b) WS 下发字节（裸 PCM + 元信息 json）。
    #   ★ 不配这个参数 ⇒ **完全不落盘**（不改变默认行为）。
    # ★★★ EXT-029 ①：说话人旁路开关（**默认关**）。
    #   开 ⇒ 流水线会话接旁路（独立线程 + 有界队列 + 异步回填）。
    #   关 ⇒ 完全不接（= EXT-029 ③ 验收里的「关闭旁路」那一轮）。
    ap.add_argument("--spk-bypass", dest="spk_bypass", action="store_true",
                    help="启用说话人旁路（EXT-029：独立线程 + 有界队列）")
    ap.add_argument("--no-spk-bypass", dest="spk_bypass", action="store_false",
                    help="禁用说话人旁路（默认）")
    ap.set_defaults(spk_bypass=False)
    ap.add_argument("--audio-dump-out", default=None,
                    help="★ EXT-028①：逐段落盘 TTS 原始输出(wav)与 "
                         "WS 下发字节(pcm)到这个目录")
    # ── ★ EXT-010：句级流水线 ────────────────────────────────
    # ★★ EXT-022 已定①：**流水线默认开启**（主会话 2026-10-30 已定，
    #   用户已知情）。
    #   ⇒ 旧写法 `--pipeline` 是 `store_true` ⇒ **默认关闭**
    #     ⇒ 与「已定」冲突（CLI 入口与启动器 GUI 口径还不一致）。
    #   ⇒ 现在：**默认开启**，另给 `--no-pipeline` 作逃生口
    #     （串行路径仍在，需要对照/排障时可退回）。
    # ⚠️ **诚实性**：`--no-pipeline` 仍然只是「串行会话」，
    #   不是「关掉引擎」—— 回声模式本来就不用流水线。
    ap.add_argument("--pipeline", dest="pipeline", action="store_true",
                    help="（**默认已开启**）显式要求流水线会话 —— "
                         "保留此参数只为兼容旧启动脚本")
    ap.add_argument("--no-pipeline", dest="pipeline", action="store_false",
                    help="**不用**流水线会话（退回串行 ASR→MT→TTS；"
                         "默认是**开启**流水线）")
    ap.set_defaults(pipeline=True)
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
            try:
                from .version import version_label as _vl
                _log("实时配音桥接 " + _vl())
            except Exception:
                pass
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

    # ★★ T-1：**预热模型之前**先探端口（2026-10-30 22:41 用户实测报错根因）。
    #   旧流程：先加载 24 秒模型 → 再 serve() 去 bind ⇒ 端口被占用时
    #   用户**白等 24 秒**才看到一整屏 `OSError 10048` 的 Python traceback。
    #   ⇒ 现在：**先探** ⇒ 占用则**立刻**退出（退出码 6）并给人话提示。
    #
    #   ★ 查**两个**端口：8765（WS，致命）与 8766（配对 HTTP）。
    #     实测事实：配对端点在**预热之前**就 bind 了 ⇒ 端口被占时它只会
    #     「⚠️ 配对端点不可用」告警后继续 ⇒ 用户**看不到任何异常**，
    #     然后白等 24 秒，最后崩在 8765 上 ⇒ 现象就是「启动报错但看不懂」。
    for _p in (args.port, args.pair_port):
        if not _p:
            continue
        _port_ok, _port_why = _probe_port_free(args.host, _p)
        if not _port_ok:
            _owner = _describe_port_owner(_p)
            _log(f"❌ {_port_why}{('（' + _owner + '）') if _owner else ''}")
            _log("   这通常意味着**桥接服务已经在运行**（重复启动）。")
            _log(f"   解决办法：① 在启动器窗口点「停止」后再启动；"
                 f"② 或结束占用该端口的进程；③ 或换一个端口。")
            _log(f"   （本轮**没有**加载模型 —— 端口检查在预热之前，"
                 f"所以不用白等 20–40 秒）")
            return 6
    # ★★ EXT-017②：预热期间 `/status` 就要能报「正在加载」。
    #   ⇒ 配对端点必须**在预热之前**起来（否则预热那 20–40 秒里
    #     /status 根本不在线 ⇒ 启动器/popup 轮询一直失败
    #     ⇒ 状态灯永远停在「正在加载模型…」，不会翻成「TTS 就绪」）。
    holder["engine_state"] = "loading" if (args.real and engine is not None) \
        else "unknown"
    # ★★ EXT-024 F：把**连接模式**放进 holder ⇒ /status 能报出来
    #   ⇒ popup 能显示「真实引擎 / 回声」。
    #   ⚠️ 诚实性：echo ⇒ "echo"；real ⇒ "real"（**不代表引擎已就绪**，
    #     就绪与否看 engine_state / warmup，popup 两者都要看）。
    holder["mode"] = "echo" if (args.echo or engine is None) else "real"
    if C.LAN_MODE and args.host == C.BRIDGE_HOST:
        args.host = "0.0.0.0"
        _log(f"局域网模式：监听 0.0.0.0，允许网段 {[str(n) for n in C.lan_allowed_nets()]}，同一时间只服务一个用户")

    # ★★ EXT-012：配对 HTTP 端点（**用户不需要手动复制 token**）
    #   插件从 http://127.0.0.1:<pair_port>/pair 自动取 token
    #   ⇒ 安全口径不变：仅接受 Origin: chrome-extension:// 的请求。
    pair_server = None
    try:
        from .pair_server import PairServer
        pair_server = PairServer(
            port=args.pair_port,
            host=args.host,
            peer_check=C.peer_allowed,
            token_provider=lambda: (_tokens.token if _tokens else ""),
            status_provider=lambda: dict(_pair_status(holder) or {},
                                         active_peer=(ACTIVE_PEER["ip"] if ACTIVE_PEER["n"] > 0 else None)),
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

    # ★★★★ EXT-028 ①：逐段音频落盘器（不配 --audio-dump-out ⇒ 不落盘）。
    # ★★ EXT-031③：**发行版默认关闭**（调试落盘不进发行包）。
    #   发行版即使显式传了 `--audio-dump-out` 也**不生效** ⇒ 如实警告但不创建落盘器。
    _audio_dump = None
    if args.audio_dump_out:
        if getattr(C, "RELEASE_MODE", False):
            _log("⚠️ EXT-031③：发行版已禁用逐段音频落盘"
                 "（--audio-dump-out 被忽略）")
        else:
            try:
                from .audio_dump import AudioDump
                _audio_dump = AudioDump(args.audio_dump_out)
                _log(f"★ EXT-028①：逐段音频落盘目录 = {args.audio_dump_out}")
            except Exception as e:
                _log(f"⚠️ 音频落盘器创建失败（不影响主功能）：{e}")
                _audio_dump = None

    try:
        asyncio.run(serve(args.host, args.port, delay_sec=args.delay,
                          echo_mode=args.echo, token_path=token_path,
                          engine=engine, margin_out=args.margin_out,
                          session_holder=holder,
                          use_pipeline=args.pipeline,
                          audio_dump=_audio_dump,
                          spk_bypass=args.spk_bypass))
    except KeyboardInterrupt:
        _log("已停止")
    except OSError as e:
        # ★★ T-1：bind 失败的**兜底**（端口检查与真正的 bind 之间有个
        #   极小的竞态窗口；也可能被别的程序抢占）。
        #   ⇒ **不要**抛一整屏 traceback 给用户 ⇒ 给人话提示 + 退出码 6。
        _win = getattr(e, "winerror", None)
        if _win == 10048 or e.errno in (10048, 48, 98):
            _owner = _describe_port_owner(args.port)
            _log(f"❌ 端口 {args.port} 已被占用{('（' + _owner + '）') if _owner else ''}"
                 f" ⇒ 无法启动监听。")
            _log("   这通常意味着**桥接服务已经在运行**（重复启动）。")
            _log(f"   解决办法：① 在启动器窗口点「停止」后再启动；"
                 f"② 或结束占用该端口的进程；③ 或换一个端口。")
            return 6
        _log(f"❌ 监听 {args.host}:{args.port} 失败：{e}")
        raise
    finally:
        if pair_server is not None:
            try:
                pair_server.stop()
            except Exception:
                pass
        # ★★ EXT-031③：发行版**禁用**诊断落盘（margin / audio_dump）——
        #   诊断产物是**验收/调试**用的，不该出现在用户机器上。
        if not getattr(C, "RELEASE_MODE", False):
            _dump_margin(holder, args.margin_out, engine)
        # ★ EXT-028 ①：退出前把落盘清单写出来（供 reviewer 核对文件数/字节数）。
        if _audio_dump is not None:
            try:
                _mp = _audio_dump.write_manifest()
                if _mp:
                    _log(f"★ EXT-028①：音频落盘清单 = {_mp}")
            except Exception as e:
                _log(f"⚠️ 音频落盘清单写入失败：{e}")
    return 0


def _client_rootcause_kwargs(sess) -> dict:
    """把客户端**实测**的数据整理成 `decompose_sync_rootcause` 的入参。

    ★ 没有的项一律**不传**（⇒ 分解里就是 None ⇒ 不计入合计）
      ⇒ 绝不把「没测到」写成 0。
    ★ `downlink_latency_sec` 取客户端实测下行耗时的 **P95**（秒）
      —— 判据就是「P95 ≤ 0.3 s」⇒ 必须用 P95 而不是均值。
    ★ `server_to_player_sec`（**轴缺口**）用客户端实测的
      `t0UpPlayerOffsetSec` ⇒ 它是**有符号**的（实测约 −3.18 s）⇒
      取**绝对值**才是「缺口的大小」。
    """
    kw: dict = {}
    if sess is None:
        return kw
    if not hasattr(sess, "client_metrics_summary"):
        return kw
    try:
        cm = sess.client_metrics_summary()
    except Exception:
        return kw

    # ── 真实下行耗时（P95，秒）────────────────────────────────
    p95_ms = cm.get("downlink_p95_ms")
    if p95_ms is not None:
        kw["downlink_latency_sec"] = float(p95_ms) / 1000.0

    # ── 轴缺口（取绝对值）───────────────────────────────────
    off = cm.get("t0_up_player_offset_sec")
    if off is not None:
        kw["server_to_player_sec"] = abs(float(off))

    # ── 播放端排队（逐段「就绪→起播」）──────────────────────
    pq = list(getattr(sess, "client_player_queue_sec", []) or [])
    if pq:
        kw["player_detail"] = [{"readyToStartSec": v} for v in pq]
    return kw


def _slowdown_record(sess) -> dict:
    """★ EXT-041：媒体降速的**建议** + **客户端实测是否生效**。

    两部分必须**分列**（不能混成一个数）：

    * `recommended_rate` —— **服务端**按实测 `tts_over_src` 算出的建议倍率
      （`ext/media_slowdown.py`）⇒ 这是"应该降多少"；
    * `client_applied_rate` / `client_applied` —— **客户端实测**
      （插件把内容脚本的执行结果回报上来）⇒ 这是"**实际降了多少**"
      ⇒ reviewer EXT-041 要的「视频是否降速以及降了多少」就看这两个。

    ⚠️ 客户端没回报 ⇒ 就是 `None`（**不臆造 0 / 不臆造 1.0**）。
    """
    out: dict = {
        "recommended_rate": None,
        "tts_over_src": None,
        "speech_over_src": None,
        "r_critical": None,
        "reason": None,
        "needs_slowdown": None,
        "est_slope_sec_per_sec": None,
        "slope_target": 0.01,
        "rate_floor": 0.90,
        "rate_ceil": 1.00,
        "client_applied": None,
        "client_applied_rate": None,
        "client_videos": None,
        "client_reason": None,
    }
    if sess is None:
        return out
    try:
        from .media_slowdown import rate_for as _ms_rate_for
        _rtf = compute_rtf_breakdown(getattr(sess, "margins", []) or [])
        _tor = _rtf.get("tts_over_src")
        _sos = _rtf.get("speech_over_src")
        _dec = _ms_rate_for(_tor, speech_over_src=_sos)
        out["tts_over_src"] = _tor
        out["speech_over_src"] = _sos
        out["recommended_rate"] = _dec.rate
        out["r_critical"] = _dec.r_critical
        out["reason"] = _dec.reason
        out["needs_slowdown"] = _dec.needs_slowdown
        out["est_slope_sec_per_sec"] = _dec.est_slope
        out["slope_target"] = _dec.to_dict()["slope_target"]
    except Exception as e:
        out["reason"] = "计算建议倍率失败：%s" % str(e)[:160]
    # ── 客户端实测（插件回报）──
    try:
        _cm = getattr(sess, "client_slowdown", None)
        if isinstance(_cm, dict):
            out["client_applied"] = _cm.get("applied")
            out["client_applied_rate"] = _cm.get("rate")
            out["client_videos"] = _cm.get("videos")
            out["client_reason"] = _cm.get("reason")
    except Exception:
        pass
    return out


def _dump_margin(holder: dict, out_path: Optional[str], engine,
                 session=None) -> None:
    """把余量统计与逐句时间表落盘（EXT-006 P1 验收要求）。

    ★★ 缺陷 15 的第二道防线：**绝不用空统计覆盖已有的真数据**。
    若本次要写的 `n_segments` 为 0，而磁盘上已有文件含更多段
    ⇒ 判定为「拿错了会话 / 会话还没数据」⇒ **跳过写盘**并记日志。
    （宁可少写一份，也不能把 EXT-006 的核心验收量清空。）

    ★★ EXT-024 A：新增 `session` 参数 ——
      显式指定要落盘哪个会话（**真正产出段的那个**，即 uplink 会话）。
      不给则沿用旧行为（读 `holder["session"]`）。
    """
    if not out_path:
        return
    sess = session if session is not None else holder.get("session")
    # ★ EXT-008：滞后分解落盘（喂帧慢 vs 引擎慢）
    #   ⚠️ 用 getattr 取 delay_sec ⇒ 桩 session（自测用的假对象）也不会崩。
    _dl = float(getattr(sess, "delay_sec", 10.0) or 10.0) if sess else 10.0
    data = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "target_lang": getattr(engine, "target_lang", None),
        # ★★ T-1：抓流方式落盘 ⇒ reviewer 直接看 margin.json 就能知道
        #   这一轮到底跑的是 tabCapture（生产路径）还是 getDisplayMedia（兜底）。
        #   ⚠️ 用 getattr 取 ⇒ 桩 session（自测用的假对象）也不会崩。
        "capture_mode": (getattr(sess, "capture_mode", None) if sess else None),
        "client_source": (getattr(sess, "client_source", None) if sess else None),
        "source_rate": (getattr(sess, "source_rate", None) if sess else None),
        # ★★ T-3：客户端请求的目标语言 / 音色（**与上面的 target_lang
        #   区分**：上面那个是**服务端启动参数**，这两个是**面板上的选择**）。
        "client_target_lang": (getattr(sess, "client_target_lang", None)
                               if sess else None),
        "client_voice": (getattr(sess, "client_voice", None) if sess else None),
        # ★★ T-4：这一轮**实际生效**的目标语言（没跑过句子 = None）。
        #   ⇒ reviewer 可直接比对 client_target_lang（面板选的）
        #     与 applied_target_lang（真正用的）⇒ 一眼看出「选了没生效」。
        "applied_target_lang": (getattr(sess, "applied_target_lang", None)
                                if sess else None),
        "margin_summary": (sess.margin_summary() if sess else {}),
        # ★★ EXT-024 A：把 `t_start` 的**时间轴口径**落盘
        #   （reviewer 明文要求「写清楚 t_start 用的是哪个时间轴」）
        #   ⇒ 从落盘文件即可核对，不必翻代码或猜。
        # ⚠️ 口径：t_start = **上行链路的采样时间轴**
        #   （s0/16000，s0 = 该段第一帧的上行累计采样数；
        #     采样点 0 = 上行收到的第一帧音频）。
        #   插件按 `t0_player + t_start + D` 排程 ⇒ 与原声**同轴**。
        "t_start_axis": "uplink_sample_index",
        "t_start_axis_note": (
            "t_start = 上行采样时间轴（s0/16000，采样点0=上行首帧）；"
            "插件按 t0_player + t_start + delay_sec 排程，与原声同轴。"
        ),
        "per_segment": (sess.margins if sess else []),
        "engine_calls": (sess.engine_calls if sess else []),
        "engine_stats": (engine.stats() if engine is not None else {}),
        "lag_decomposition": (decompose_lag(sess.margins, delay_sec=_dl)
                              if sess else {}),
        # ★★ EXT-034 ②：**三个 RTF 口径分列**（RTF_out / speech_over_src /
        #   tts_over_src）—— 旧结论的「1.231」是 `tts_over_src`，
        #   混进了「中文译文比英文原声长 1.196 倍」⇒ 归因会错。
        "rtf_breakdown": (compute_rtf_breakdown(sess.margins)
                          if sess else {}),
        # ★★★ EXT-041：**媒体降速**的建议与**实际是否生效**。
        #   * `recommended_rate` —— 按实测 `tts_over_src` 算出的 `playbackRate`
        #     （`ext/media_slowdown.py`；下限 0.90、**永不加速**）；
        #   * `client_applied_rate` / `client_applied` —— **客户端实测**
        #     （插件把降速结果回报给服务端）⇒ 没有就是 None（**不臆造**）。
        #   ⚠️ reviewer 要的「视频是否降速以及降了多少」就在这两个字段里。
        "slowdown": _slowdown_record(sess),
        # ★★ EXT-034 ④：**要满足同步需要的 D 估算**（交用户决定）
        "delay_requirement": (estimate_required_delay(sess.margins,
                                                       delay_sec=_dl)
                              if sess else {}),
        # ★★★★★★ EXT-036 ①/②：**sync 滞后的逐项根因分解**。
        #   ⇒ 明确区分「TTS 积压」与「**非 TTS 固定项**」
        #   ⇒ 后者 = 上行 + ASR 整段定稿 + 播放排队 + server→player 缺口
        #   ⇒ `tts_independent_lag_sec` > 0 ⇒ **不能**写成「全归 TTS」。
        #   ★★★ EXT-036 补测：把**客户端实测**的下行耗时/播放端排队/
        #   轴偏移喂进去（此前三项恒为 null ⇒ 归因少算三项）。
        #     - `downlink_latency_sec` = 客户端实测下行耗时 **P95**（秒）
        #     - `player_detail` = 客户端上报的逐段「就绪→起播」
        #     - `server_to_player_sec` = 客户端实测的**轴缺口**
        #       （`t0UpPlayerOffsetSec` ⇒ **有符号** ⇒ 实测约 −3.18 s）
        "sync_rootcause": (
            decompose_sync_rootcause(
                sess.margins, delay_sec=_dl,
                **_client_rootcause_kwargs(sess))
            if sess else {}),
        # ★ 客户端实测汇总（独立落盘 ⇒ reviewer 可直接核对原始分位）
        "client_metrics": (sess.client_metrics_summary()
                           if sess is not None
                           and hasattr(sess, "client_metrics_summary") else {}),
        # ★ EXT-009：自适应加速统计（滞后曲线 + 各倍率时间占比 + 丢句数）
        #   ⚠️ 用 getattr 取 ⇒ 桩 session（自测用的假对象）也不会崩。
        "adaptive_speed": (sess.adaptive_speed_stats()
                           if sess is not None
                           and hasattr(sess, "adaptive_speed_stats") else {}),
        # ★★ EXT-011：线程限制记录（4 个环境变量的实际值 + 开关状态）
        "thread_limits": dict(THREAD_LIMIT_RECORD),
        # ★★★ EXT-029 ③：**说话人旁路**的指标
        #   （`spk_queue_drop` / `spk_worker_busy_ms` 必须落盘 ⇒ reviewer
        #     可直接核对「旁路有没有反压 ASR」）。
        "spk_bypass": (sess.spk_bypass.stats()
                       if (sess is not None
                           and getattr(sess, "spk_bypass", None) is not None)
                       else {"enabled": False, "spk_queue_drop": 0,
                             "spk_worker_busy_ms": 0.0}),
        # ★★ EXT-027③：段级「说话人 / 音色来源」表
        "spk_table": (list(getattr(sess, "spk_table", []) or [])
                      if sess is not None else []),
        # ★★★ EXT-029 ③：**流水线各阶段的**墙钟**（含等 GPU 互斥锁的时间）。
        #   ## 为什么必须单独落盘
        #     `per_segment[].asr_sec` 是**纯引擎调用**耗时（**不含**等锁）
        #     ⇒ 旁路与 ASR 抢 GPU 锁造成的排队**不会**体现在 `asr_sec` 里
        #     ⇒ 只比 `asr_sec` 会**低估**旁路对 ASR 的影响（假通过）。
        #   ★ `stage_wall_sec.asr` 才是**真实墙钟**（`ext/pipeline.py` 里
        #     `dt = perf_counter() - t0` 覆盖 `with self._device_lock:` 整段）
        #     ⇒ 这才是 EXT-029③「ASR 墙钟」的正确口径。
        "pipeline": (sess.pipeline_stats()
                     if sess is not None
                     and hasattr(sess, "pipeline_stats") else None),
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

    ★★ EXT-024 A/F：popup 也要看到**真正产出段的会话**的数据
      （uplink 会话）⇒ 否则「当前滞后 / 段数」恒为空。
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
        # ★ 2026-11-05 EXT-039 ①：静音填充段单列（**不是**丢句）
        "n_silent_fill_segments": 0,
        # ★ EXT-017②：引擎加载状态（popup 显示「正在加载模型…」/「TTS 就绪」）
        "engine_state": "unknown",
        "engine_loaded": [],
        "engine_failed": {},
        # ★★ EXT-024 F：popup 显示「真实引擎 / 回声」
        "mode": "unknown",
    }
    holder = holder if isinstance(holder, dict) else {}
    # ★★ EXT-024 F：连接模式（真实引擎 / 回声）
    _mode = holder.get("mode")
    if isinstance(_mode, str) and _mode in ("real", "echo"):
        out["mode"] = _mode
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
    # ★★ EXT-024 A：优先用**真正产出段的会话**（uplink 会话）。
    if sess is None or _is_empty_producer(sess):
        _prod = holder.get("producer_session") if isinstance(holder, dict) else None
        if _prod is not None:
            sess = _prod
    if sess is None:
        return out
    out["has_session"] = True
    try:
        out["delay_sec"] = float(getattr(sess, "delay_sec", 0) or 0) or None
    except Exception:
        pass
    try:
        out["bg"] = sess.bg_status()          # v0.4.19 保留背景音 (popup shows state / reason)
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
        # ★ 2026-11-05 EXT-039 ①：静音填充段单列（**不是**丢句）
        out["n_silent_fill_segments"] = a.get("n_silent_fill_segments") or 0
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
    # ★★★ EXT-041：**媒体降速建议**（给插件按实测占用率算 `playbackRate`）。
    #   插件（内容脚本）拿这个倍率去降速宿主页面的 `<video>`/`<audio>`
    #   ⇒ 源到达速率下降 ⇒ 配音不再无限堆积（见 `ext/media_slowdown.py`）。
    #   ⚠️ 这里只给**建议**，**不代插件执行**（插件才有宿主页面的控制权）。
    #   ⚠️ 实测值来自**已产出段**的会话 ⇒ 没有段时是 None（插件用默认值 0.92）。
    try:
        from .media_slowdown import rate_for as _ms_rate_for
        _rtf = compute_rtf_breakdown(sess.margins) if sess else {}
        _tor = _rtf.get("tts_over_src")
        _sos = _rtf.get("speech_over_src")
        _dec = _ms_rate_for(_tor, speech_over_src=_sos)
        out["slowdown"] = {
            "tts_over_src": _tor,
            "speech_over_src": _sos,
            "recommended_rate": _dec.rate,
            "reason": _dec.reason,
            "r_critical": _dec.r_critical,
            "needs_slowdown": _dec.needs_slowdown,
            "est_slope_sec_per_sec": _dec.est_slope,
            "slope_target": _dec.to_dict()["slope_target"],
            "rate_floor": 0.90,
            "rate_ceil": 1.00,
        }
    except Exception as e:
        out["slowdown"] = {"error": str(e)[:200]}
    return out


def _caption_app_running() -> bool:
    """检测实时字幕 App 是否在运行（互斥铁律）。

    ★★★ EXT-033 实测抓到的**两个真实缺陷**（都让互斥形同虚设）：
    ① **匹配串漏了大小写变体**：
       旧实现只匹配字面量 ``"live_caption"``（**带下划线**），
       而本机运行的是 ``Confucius4_LiveCaption_v2.1`` 下的
       ``pythonw.exe ... ext/bridge/bridge_launcher.py``
       ⇒ 路径里是 **``LiveCaption``（无下划线）** ⇒ 匹配不到。
    ② **psutil 在实际运行的解释器里不存在**：
       bridge 由 **App 自带的 python** 启动（openvino/babelvox 只在那里），
       而那个解释器**没有装 psutil**（EXT-017② 注释里已记过此事）
       ⇒ 旧实现 ``import psutil`` 直接抛异常 ⇒ **恒返回 False**
       ⇒ 互斥**从来没生效过** ⇒ 两个进程同时抢 GPU.0 + NPU
       ⇒ 管线吞吐被拖垮（EXT-033 实测滞后以 0.31 s/s 累积）。
    ⇒ 现在：**不依赖 psutil**，用 Windows 自带的
      `tasklist /FO CSV /NH`（拿映像名）+ `wmic`/`Get-CimInstance` 拿命令行；
      都拿不到时**按「可能在跑」处理**（保守：宁可误拦，不可放行抢设备）。
    """
    me = os.getpid()
    cmds = _list_process_cmdlines()
    for pid, cmd in cmds:
        if pid == me:
            continue
        low = cmd.lower()
        # ★ 归一化：去掉 `_` / `-` / 空格 ⇒ `LiveCaption` ≡ `live_caption`
        norm = low.replace("_", "").replace("-", "").replace(" ", "")
        # 排除本模块自己的进程（`ext.bridge` / `ext_bridge` / `bridge_launcher`
        # 跑在 live_dub_ext 下时也算自己）
        if "extbridge" in norm or "ext.bridge" in low:
            continue
        # ★★ 必须命中**App 的真实入口**，不能只凭路径里出现 `LiveCaption`：
        #   否则任何**命令行里提到该路径**的进程（测试脚本、编辑器、
        #   本模块自己的诊断命令）都会被误判成「App 在跑」⇒ 永远起不来。
        #   App 的入口 = `bridge_launcher.py`（App 自带的 ext/bridge/）
        #   或 `live_caption_app.py`。
        if "bridgelauncher.py" in norm or "livecaptionapp.py" in norm:
            return True
    # ⚠️ 探测**彻底失败**（拿不到任何进程列表）⇒ 保守按「可能在跑」处理
    if not cmds:
        return _caption_app_probe_failed()
    return False


def _list_process_cmdlines() -> list:
    """列出 (pid, cmdline) —— **不依赖 psutil**。

    返回 [] 表示「探测失败」（不是「没有 App」）。
    """
    out = []
    # ── 路径 1：Windows `wmic process get ProcessId,CommandLine /FORMAT:CSV`
    #   ⚠️ 新版 Windows 已移除 wmic ⇒ 失败就换下一条。
    try:
        import subprocess  # local import：避免顶层依赖
        r = subprocess.run(
            ["wmic", "process", "get", "ProcessId,CommandLine", "/FORMAT:CSV"],
            capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                line = line.strip()
                if not line or line.startswith("Node,"):
                    continue
                # CSV 形如 "Node","PID","命令行"
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 3:
                    try:
                        pid = int(parts[1])
                    except ValueError:
                        continue
                    out.append((pid, parts[2]))
            if out:
                return out
    except Exception:
        pass
    # ── 路径 2：PowerShell `Get-CimInstance Win32_Process`
    try:
        import subprocess
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-CimInstance Win32_Process | ForEach-Object { "
             "\"$($_.ProcessId)`t$($_.CommandLine)\" }"],
            capture_output=True, text=True, timeout=40, errors="replace")
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                if "\t" not in line:
                    continue
                pid_s, _, cmd = line.partition("\t")
                try:
                    pid = int(pid_s.strip())
                except ValueError:
                    continue
                out.append((pid, cmd))
            if out:
                return out
    except Exception:
        pass
    # ── 路径 3：只拿映像名（`tasklist`）—— 没有命令行就退化成按 exe 名判
    try:
        import subprocess
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and r.stdout:
            for line in r.stdout.splitlines():
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                    except ValueError:
                        continue
                    # 没有命令行 ⇒ 用 exe 名兜底（App 的 exe 是 pythonw.exe，
                    # 匹配不到 App ⇒ 只能算「探测不完整」）
                    out.append((pid, parts[0]))
            if out:
                return out
    except Exception:
        pass
    return out


def _caption_app_probe_failed() -> bool:
    """进程列表**完全拿不到**时的保守判定。

    ⚠️ 铁律：**探测失败 ⇒ 按「可能在跑」处理**（宁可误拦，不可放行抢设备）。
    但不能永远返回 True（那会让模块永远起不来）⇒ 用共享机器锁做兜底：
    若锁存在且归属别的模块 ⇒ 视为「有人在用设备」。
    """
    try:
        lock = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "..", "..", "shared", "MACHINE_LOCK")
        lock = os.path.abspath(lock)
        if os.path.isfile(lock):
            with open(lock, "r", encoding="utf-8", errors="replace") as f:
                txt = (f.read() or "").lower()
            if "ext" not in txt:
                return True
    except Exception:
        pass
    return False


if __name__ == "__main__":
    raise SystemExit(main())
