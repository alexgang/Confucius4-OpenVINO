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
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import config as C
from .duration import fit_duration
from .segmenter import plan_segments, describe as describe_segmenter
from .speaker import SpeakerTracker

# ── 引擎接入点（复用现有交付版本；此处只做延迟 import，不改对方文件） ──
ENGINE_ADAPTER = None  # 由 main() 注入：见 ext/engines.py


def _log(msg: str) -> None:
    print(f"[bridge {time.strftime('%H:%M:%S')}] {msg}", flush=True)


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


def check_origin(origin: Optional[str]) -> bool:
    """校验 Origin 必须是 chrome-extension://<id>。"""
    if not origin:
        return False
    return origin.startswith(C.ALLOWED_ORIGIN_PREFIX)


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
            tasks.extend(self._process_segment(seq, abs0, abs1, seg_audio,
                                               audio_complete_at=recv_at))
        # 一次性裁掉所有已处理的段，并把基准点推进
        cut = ready[-1][1]
        self._buf = self._buf[cut:]
        self._consumed_samples += cut
        return tasks or None

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

        # ★ EXT-006：TTS 就绪时刻 + 余量
        ready_at = time.perf_counter()
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
        })
        self.engine_calls.append({
            "id": seg_id, "asr_sec": round(asr_s, 4),
            "mt_sec": round(mt_s, 4), "tts_sec": round(tts_s, 4)})

        fit = fit_duration(seg_id, t_start=t_start, t_end=t_end,
                           speech_sec=speech_sec, max_rate=C.TTS_RATE_MAX)

        return [{
            "type": "tts",
            "id": seg_id,
            "t_start": round(t_start, 3),
            "t_end": round(t_end, 3),
            "src": text,
            "tgt": tgt,
            "spk": spk,
            "voice": voice,
            "pcm24k": (base64.b64encode(pcm24k).decode("ascii")
                       if pcm24k is not None else None),
            "fit": fit.to_dict(),
            "delay_sec": self.delay_sec,
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
        return {
            "n_frames": self.n_frames,
            "n_dropped": self.n_dropped,
            "buffered_sec": round(self._buf.shape[0] / C.SAMPLE_RATE, 2),
            "speaker": self.tracker.stats(),
            "margin": self.margin_summary(),
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


async def handle_ws(websocket, *, tokens: TokenStore, delay_sec: float,
                    echo_mode: bool, engine=None,
                    session_holder: Optional[dict] = None,
                    margin_out: Optional[str] = None) -> None:
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
    if not check_origin(origin):
        _log(f"拒绝连接：Origin 非法 ({origin!r})")
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
        session = Session(token, delay_sec=delay_sec, engine=engine)
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
    session = Session(token, delay_sec=delay_sec, engine=engine)
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
                continue
    except Exception as e:
        _log(f"连接异常: {e}")
    finally:
        _log("连接关闭")


async def serve(host: str, port: int, *, delay_sec: float, echo_mode: bool,
                token_path: str, engine=None, margin_out: Optional[str] = None,
                session_holder: Optional[dict] = None) -> None:
    import websockets

    tokens = TokenStore(token_path)
    _log(f"token 文件：{token_path}")
    _log(f"监听 ws://{host}:{port}（echo={echo_mode}, D={delay_sec}s）")
    async with websockets.serve(
        lambda ws: handle_ws(ws, tokens=tokens, delay_sec=delay_sec,
                              echo_mode=echo_mode, engine=engine,
                              session_holder=session_holder,
                              margin_out=margin_out),
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

    holder: dict = {}
    try:
        asyncio.run(serve(args.host, args.port, delay_sec=args.delay,
                          echo_mode=args.echo, token_path=token_path,
                          engine=engine, margin_out=args.margin_out,
                          session_holder=holder))
    except KeyboardInterrupt:
        _log("已停止")
    finally:
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
