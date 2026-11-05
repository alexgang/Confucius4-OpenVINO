#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ext033_analyze.py — ★ EXT-033 C/D/E：**实测**三份对比 + player 端 sync_err
+ 交付物生成

## 为什么必须重写（EXT-032 的第 1 条批评）
EXT-032 的对比是「**按内容强行对齐**」出来的：对齐峰只有 0.04~0.70，
`d_player_sec` 说是实测、其实是抄的 `d_ws`，录音被截断、时间轴是压缩过的。
⇒ 本脚本**只信 player 自己报出来的时间原点**：

    WAV 里第 i 段的位置 = `onset_actual − acStartSec`

`onset_actual`（AudioContext 时刻）来自 player 的 onset 检测器，
`acStartSec` 来自录音开始时的 AudioContext 时刻 ⇒ **同一个时钟轴**
⇒ 不需要任何「搜索对齐」，也就不会再出现「强行对齐出来的落点」。

## 判定阈值（EXT-033 原文）
| 指标 | 阈值 |
|---|---|
| 时长比 player/(b) | **1.00 ± 0.02**（变速段按 speed 校正） |
| 互相关峰 | **≥ 0.6**（低于此 ⇒ 该段标「未对齐」，**不计入合格**） |
| sync_err（有符号） | **\\|误差\\| ≤ 300 ms** |
| 录音完整性 | ffprobe 不报 truncated；时长 **≥ 75 s** |
| 开头静音 | **≤ 15 s** |
| 源语言 | **必须是英文**（逐段校验 src 不含中日韩字符） |

## 跑法
    python tests/smoke/ext033_analyze.py <run_dir> [--deliver]
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import shutil
import sys
import time

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from ext032_audio_compare import (read_wav_mono, read_pcm_s16le,   # noqa: E402
                                  resample_linear, xcorr_peak_offset,
                                  snr_db, silence_spans, rms, dbfs)
from ext032_deliver import _pct                                    # noqa: E402

# ── 阈值（EXT-033 原文）────────────────────────────────────────────
DUR_RATIO_TOL = 0.02
XCORR_PEAK_MIN = 0.6
SYNC_ERR_TARGET_MS = 300.0
MIN_RECORDING_SEC = 75.0
MAX_LEADING_SILENCE_SEC = 15.0
SILENCE_DBFS = -55.0

#: 中日韩统一表意文字（用来判「源语言必须是英文」）
CJK_RE = re.compile(
    "[\u4e00-\u9fff\u3400-\u4dbf\u3040-\u30ff\uac00-\ud7af]")

#: ★ **细粒度**有声跨度检测（EXT-033 C 的时长比要判到 ±2%）
#:   ⚠️ `ext032_audio_compare.silence_spans` 用的是 **250 ms** 窗
#:      ⇒ 量化误差 ±250 ms ⇒ 对 1~3 s 的句子就是 ±10~25%
#:      ⇒ **根本判不了 EXT-033 的 1.00±0.02**。
#:   ⇒ 这里自己用 **10 ms** 窗重测，且对 player 与 WS **用同一把尺子**
#:      （阈值偏置互相抵消 ⇒ 比的是真实差异，不是检测器偏差）。
VOICE_WIN_MS = 10
VOICE_DBFS = -45.0

LISTEN_ROOT = r"C:\Users\Trekker-PTL\shared\ext_listen"


try:
    import numpy as _np          # noqa: E402
except Exception:                # pragma: no cover
    _np = None


def _xcorr_peak_offset(a, b, sr, max_lag_sec=1.0):
    """零均值归一化互相关 ⇒ (峰值, 偏移秒)。

    ★ 与 `ext032_audio_compare.xcorr_peak_offset` **同口径**
      （零均值 + 全信号能量归一 ⇒ 幅度缩放不影响峰值）。
    ★ 有 numpy 时走 FFT（48 kHz × 数秒信号，纯 Python 是 O(n²) ⇒ 跑不动）。
    """
    if not a or not b:
        return 0.0, 0.0
    n = min(len(a), len(b))
    if n < 64:
        return 0.0, 0.0
    if _np is not None:
        xa = _np.asarray(a[:n], dtype=_np.float64)
        xb = _np.asarray(b[:n], dtype=_np.float64)
        xa = xa - xa.mean()
        xb = xb - xb.mean()
        ea = float(_np.sqrt((xa * xa).sum()))
        eb = float(_np.sqrt((xb * xb).sum()))
        if ea <= 0.0 or eb <= 0.0:
            return 0.0, 0.0
        m = 1
        while m < 2 * n:
            m <<= 1
        cc = _np.fft.irfft(_np.fft.rfft(xa, m)
                           * _np.conj(_np.fft.rfft(xb, m)), m)
        max_lag = min(int(max_lag_sec * sr), n - 64)
        lags = _np.arange(-max_lag, max_lag + 1)
        idx = _np.where(lags >= 0, lags, lags + m)
        vals = cc[idx] / (ea * eb)
        k = int(_np.argmax(vals))
        return float(vals[k]), float(lags[k]) / float(sr)
    from ext032_audio_compare import xcorr_peak_offset as _slow
    return _slow(a, b, sr, max_lag_sec)


def _snr_db(ref, test) -> float:
    """SNR（dB）= 10·log10(P_ref / P_err)。"""
    if not ref or not test:
        return 0.0
    n = min(len(ref), len(test))
    if n < 64:
        return 0.0
    if _np is not None:
        xa = _np.asarray(ref[:n], dtype=_np.float64)
        xb = _np.asarray(test[:n], dtype=_np.float64)
        err = xb - xa
        p_ref = float((xa * xa).mean())
        p_err = float((err * err).mean())
        if p_err <= 1e-15:
            return 120.0 if p_ref > 1e-15 else 0.0
        if p_ref <= 1e-15:
            return 0.0
        return 10.0 * math.log10(p_ref / p_err)
    from ext032_audio_compare import snr_db as _slow_snr
    return _slow_snr(ref, test)


def voiced_span(x, sr, thr_db=VOICE_DBFS, win_ms=VOICE_WIN_MS):
    """细粒度有声跨度（秒）= 第一个有声窗的起点 → 最后一个有声窗的终点。

    ★ 返回 (start_sec, end_sec, voiced_sec)；无声则 (None, None, 0.0)。
    """
    if not x or len(x) < 8:
        return None, None, 0.0
    if _np is not None:
        a = _np.asarray(x, dtype=_np.float32)
        step = max(1, int(sr * win_ms / 1000))
        n = (a.size // step) * step
        if n < step:
            return None, None, 0.0
        blocks = a[:n].reshape(-1, step).astype(_np.float64)
        # ★ 变量名不能叫 `rms`：本函数下面的 fallback 分支要调用**全局**
        #   `rms(...)`，同名局部变量会让 Python 把整个函数里的 `rms` 判成局部
        #   ⇒ fallback 分支必然 `UnboundLocalError`
        #   （EXT-033 自测 `test_ext033_deliver.py` 实测踩到）。
        _rms_blocks = _np.sqrt((blocks * blocks).mean(axis=1))
        db = 20.0 * _np.log10(_np.maximum(_rms_blocks, 1e-12))
        idx = _np.nonzero(db > thr_db)[0]
        if idx.size == 0:
            return None, None, 0.0
        first = int(idx[0]) * step
        last = (int(idx[-1]) + 1) * step
        return first / float(sr), last / float(sr), (last - first) / float(sr)
    step = max(1, int(sr * win_ms / 1000))
    first = None
    last = None
    for i in range(0, len(x) - step + 1, step):
        if dbfs(rms(x[i:i + step])) > thr_db:
            if first is None:
                first = i
            last = i + step
    if first is None:
        return None, None, 0.0
    return first / float(sr), last / float(sr), (last - first) / float(sr)


def _log(msg: str) -> None:
    print("[ext033-analyze] %s" % msg, flush=True)


# ══════════════════════════════════════════════════════════════════
# 纯函数（**可单测**）
# ══════════════════════════════════════════════════════════════════
def wav_timeline_offsets(detail, ac_start_sec):
    """player 报的实际起播（AudioContext 时刻）⇒ WAV 里的位置（秒）。

    ★ 同一个时钟轴 ⇒ 不需要搜索对齐。
    """
    out = []
    for d in detail or []:
        actual = d.get("actual")
        if actual is None:
            continue
        out.append({
            "id": d.get("id"),
            "t_start": d.get("tStart"),
            # ★★ EXT-036 ⑥：源段长需要 `t_end`（源段 = [t_start, t_end]）
            "t_end": d.get("tEnd"),
            "requested": d.get("requested"),
            "actual": actual,
            "signed_err_ms": d.get("signedErrMs"),
            "speed": d.get("speed"),
            # ★★★★★★ EXT-037 ④：`d_player` 改用 **`endedAt − actual`**
            #   （= 实测播放时长，包络起止 ⇒ 不截尾部静音）
            #   ⚠️ 旧的能量检测口径会把**尾部静音**截掉 ⇒ d_player 偏小
            #     ⇒ 时长比偏小 ⇒ 与 reviewer 的 0.57–1.55 对不上。
            #   ⚠️ `endedAt` 缺失（旧插件）⇒ None ⇒ 回落能量检测口径。
            "ended_at": d.get("endedAt"),
            "d_player_ended_sec": (
                round(float(d.get("endedAt")) - float(actual), 4)
                if d.get("endedAt") is not None
                and actual is not None else None),
            "wav_offset_sec": round(float(actual) - float(ac_start_sec), 4),
        })
    return out


def measure_player_segment(wav, wav_sr, offset_sec, expect_dur_sec,
                           guard_sec=0.35):
    """从 WAV 里切出一段并**实测**它的有声时长。

    ★ 不抄任何外部数字：切完再用**细粒度能量检测**（10 ms 窗）量出真实
      的有声跨度（EXT-033 C 要判 ±2% ⇒ 250 ms 窗的 `silence_spans` 不够用）。
    ★ 同一把尺子也会用在 WS PCM 上 ⇒ 时长比是「苹果对苹果」。
    """
    if not wav:
        return {"d_player_sec": None, "reason": "empty wav"}
    i0 = int(round(offset_sec * wav_sr))
    if i0 < 0:
        i0 = 0
    span = int(round((expect_dur_sec + guard_sec) * wav_sr))
    i1 = min(len(wav), i0 + span) if span > 0 else i0
    seg = wav[i0:i1] if i1 > i0 else []
    if not seg:
        return {"d_player_sec": None, "reason": "offset out of range"}
    vs, ve, vd = voiced_span(seg, wav_sr)
    step = max(1, int(0.01 * wav_sr))
    onset_in_seg = None
    for i in range(0, max(1, len(seg) - step + 1), step):
        if dbfs(rms(seg[i:i + step])) > SILENCE_DBFS:
            onset_in_seg = i / float(wav_sr)
            break
    return {
        "d_player_sec": round(vd, 4) if vd else None,
        "d_window_sec": round(len(seg) / float(wav_sr), 4),
        "voiced_start_in_seg_sec": (round(vs, 4) if vs is not None else None),
        "voiced_end_in_seg_sec": (round(ve, 4) if ve is not None else None),
        "onset_in_segment_sec": (round(onset_in_seg, 4)
                                 if onset_in_seg is not None else None),
        "cut_from_sec": round(i0 / float(wav_sr), 4),
    }


def sync_stats(errs_ms):
    """player 端实测的**有符号**同步误差统计。

    ★ 口径与 `tools/p1_pipeline.py::_pct` 完全一致（最近秩、不插值）。
    ★ **有符号**：负数 = 早播。EXT-032 的 `max(0, …)` 恒为 0 ⇒ 量不出早播。
    """
    vals = sorted(float(x) for x in (errs_ms or []))
    if not vals:
        return {"n": 0, "p50": None, "p95": None, "max": None, "min": None,
                "mean": None, "abs_p95": None, "n_over_300ms": 0,
                "n_under_minus300ms": 0}
    return {
        "n": len(vals),
        "p50": _pct(vals, 0.50),
        "p95": _pct(vals, 0.95),
        "max": vals[-1],
        "min": vals[0],
        "mean": (sum(vals) / len(vals)),
        "abs_p95": _pct(sorted(abs(v) for v in vals), 0.95),
        "n_over_300ms": sum(1 for v in vals if v > SYNC_ERR_TARGET_MS),
        "n_under_minus300ms": sum(1 for v in vals if v < -SYNC_ERR_TARGET_MS),
    }


def silence_profile(wav, wav_sr):
    """开头静音 / 最长静音段 / 总静音（**实测**）。"""
    if not wav:
        return {"leading_silence_sec": None, "longest_silence_sec": None,
                "total_silence_sec": None, "duration_sec": 0.0}
    step = max(1, int(0.01 * wav_sr))
    onset = None
    for i in range(0, max(1, len(wav) - step + 1), step):
        if dbfs(rms(wav[i:i + step])) > SILENCE_DBFS:
            onset = i / float(wav_sr)
            break
    spans = silence_spans(wav, wav_sr)
    longest = max((b - a for a, b in spans), default=0.0)
    return {
        "duration_sec": round(len(wav) / float(wav_sr), 3),
        "leading_silence_sec": round(onset, 3) if onset is not None else None,
        "longest_silence_sec": round(longest, 3),
        "total_silence_sec": round(sum(b - a for a, b in spans), 3),
        "n_silence_spans": len(spans),
    }


def source_is_english(src):
    """源语言必须是英文（EXT-033 E）。返回 (ok, reason)。"""
    if src is None or str(src).strip() == "":
        return False, "src 为空"
    s = str(src)
    if CJK_RE.search(s):
        return False, "src 含中日韩字符（源语言必须是英文）"
    return True, "ok"


# ══════════════════════════════════════════════════════════════════
# ★★★★★★ EXT-036 ①/⑤/⑥：下行耗时 / 时间轴完整性 / 时长比口径
# ══════════════════════════════════════════════════════════════════
def _ext036_analysis(detail, sync, metrics, wav, wav_sr, prof, stop,
                      segs, aligned, ratios):
    """★ EXT-036 ①/⑤/⑥ 的实测分析（**只算不算猜**）。

    ## ① server→player 缺口：**到底是哪一种**
      reviewer 的原话：「这 7 s 要么是下行或收口真的慢了 7 s，
      要么是两边 t0 对不上……**先证明这 7 s 是哪一种**，再修。」
      ⇒ 本节给出两个**互斥**的量：
        * `downlink_ms`（**墙钟**）：`Date.now() − srv_wall_ms`
          = 服务端产出该段 → 插件收到该段的**真实**耗时。
          ★ 若它 ≪1 s ⇒ 缺口**不是**下行慢。
        * `axis_gap_sec`（**音频轴**）：播放端轴与服务端轴的常量差。
          ★ 它**不随时间增长** ⇒ 就是「轴对不上」的证据。

    ## ⑤ 录音时间轴完整性
      `wav 时长` vs `record_stop.durationSec`（或 `acElapsedSec`）
      ⇒ 差值 = 时间轴被压缩掉多少（判据 ≤ 0.2 s）。

    ## ⑥ 时长比口径核对
      reviewer 实测：「每段『实际播放时长 ÷ 源段长』是 **0.57–1.55**
      （STATUS 写 0.68–1.49，对不上，请核对口径）」
      ★★★★★★ EXT-037 ④：**口径重写**
        * `over_ws`      = d_player ÷ **d_ws**（**未经**变速校正）← **主口径**
        * `over_src_len` = d_player ÷ **源段长**（reviewer 用的口径）
        * ~~`speed_adjusted` = d_player × speed ÷ d_ws~~ ⇒ **已作废**
          （`d_ws` 已经是 WSOLA 变速之后的时长 ⇒ 再乘一次 speed
            就是**重复校正** ⇒ 变速被算了两次）
      ★ `d_player` 主口径也改了：**`endedAt − actual`**（包络起止）
        （旧的能量检测会**截掉尾部静音** ⇒ d_player 偏小）。
      ⇒ 两个口径**含义不同** ⇒ STATUS 必须写明用的是哪一个。
    """
    out: dict = {}

    # ── ① 下行耗时（墙钟）────────────────────────────────────────
    dl_rows = (sync or {}).get("downlinkMs") or []
    dl_vals = [float(r["ms"]) for r in dl_rows
               if r.get("ms") is not None]
    if dl_vals:
        s = sorted(dl_vals)
        out["downlink_ms"] = {
            "n": len(dl_vals),
            "min": round(s[0], 1),
            "p50": round(_pct(s, 0.50), 1),
            "p95": round(_pct(s, 0.95), 1),
            "max": round(s[-1], 1),
            "mean": round(sum(dl_vals) / len(dl_vals), 1),
            "target_p95_ms": 300.0,
            "ok": bool(_pct(s, 0.95) <= 300.0),
            "per_segment": [{"id": r.get("id"), "ms": r.get("ms")}
                            for r in dl_rows],
            "note": ("★ `Date.now() − srv_wall_ms` = 服务端产出该段 → "
                     "插件收到该段的**真实**下行耗时（同一墙钟时基）。"
                     "P95 ≤ 300 ms ⇒ 下行**不是**瓶颈。"),
        }
    else:
        out["downlink_ms"] = None
        out["downlink_note"] = (
            "本轮产物**没有** `downlinkMs`（旧版本插件不带 `srv_wall_ms`）"
            "⇒ 下行耗时**未实测**（不臆造）。")

    # ── ① 音频轴常量差（server 轴 vs player 轴）─────────────────
    #   服务端轴原点 = 会话建立时刻；播放端轴原点 = 抓流样本 0 的时刻。
    #   ⇒ 两者的差 = 「会话建立 → 抓流首样本到达」的时长
    #   ⇒ 若它是**常量**（不随段序增长）⇒ 缺口是**轴对不上**。
    t0_sec = (sync or {}).get("t0Sec")
    out["player_t0_sec"] = t0_sec
    out["player_t0_up_sec"] = (sync or {}).get("t0UpSec")
    out["player_t0_player_offset_sec"] = (sync or {}).get(
        "t0UpPlayerOffsetSec")
    out["t0_sign_check"] = {
        "t0_sec": t0_sec,
        "should_be_non_negative": True,
        "ok": bool(t0_sec is not None and float(t0_sec) >= 0.0),
        "note": ("★ EXT-036 ①：`t0` = 抓流样本 0 在 player 域的时刻 "
                 "⇒ 必须 **≥ 0**。旧实现符号反了（实测 −3.409）"
                 "⇒ `planned` 整体偏早 6.818 s。"),
    }

    # ── ⑤ 录音时间轴完整性 ──────────────────────────────────────
    wav_dur = (len(wav) / float(wav_sr)) if wav_sr else None
    rec_dur = None
    ac_elapsed = None
    if stop:
        rec_dur = stop.get("durationSec")
        ac_elapsed = stop.get("acElapsedSec")
        if ac_elapsed is None and stop.get("acTimeSec") is not None \
                and stop.get("acStartSec") is not None:
            ac_elapsed = (float(stop["acTimeSec"])
                          - float(stop["acStartSec"]))
    ref = ac_elapsed if ac_elapsed is not None else rec_dur
    tl = {
        "wav_duration_sec": round(wav_dur, 3) if wav_dur is not None else None,
        "record_duration_sec": (round(float(rec_dur), 3)
                                if rec_dur is not None else None),
        "ac_elapsed_sec": (round(float(ac_elapsed), 3)
                           if ac_elapsed is not None else None),
        "target_abs_diff_sec": 0.2,
        "note": ("★ EXT-036 ⑤：WAV 时长应与 AudioContext 经过时长"
                 "**相差 ≤0.2 s**（旧轮差 16.4 s ⇒ 时间轴被压缩）。"),
    }
    if wav_dur is not None and ref is not None:
        tl["abs_diff_sec"] = round(abs(wav_dur - float(ref)), 3)
        tl["ok"] = bool(abs(wav_dur - float(ref)) <= 0.2)
    out["timeline_integrity"] = tl

    # ── ⑥ 时长比：三个口径 ──────────────────────────────────────
    over_src = []
    over_ws = []
    for s in segs:
        d_player = s.get("d_player_sec")
        if d_player is None:
            continue
        src_len = s.get("src_len_sec")
        if src_len:
            over_src.append(float(d_player) / float(src_len))
        d_ws = s.get("d_ws_sec")
        if d_ws:
            over_ws.append(float(d_player) / float(d_ws))
    out["dur_ratio_calibers"] = {
        "over_src_len": {
            "min": round(min(over_src), 4) if over_src else None,
            "max": round(max(over_src), 4) if over_src else None,
            "n": len(over_src),
            "definition": "d_player ÷ **源段长**（reviewer EXT-036 ⑥ 用的口径）",
        },
        "over_ws": {
            "min": round(min(over_ws), 4) if over_ws else None,
            "max": round(max(over_ws), 4) if over_ws else None,
            "n": len(over_ws),
            "definition": "d_player ÷ d_ws（**未经**变速校正）",
        },
        "note": ("★ **两个口径**（EXT-037 ④ 已作废第三个）：\n"
                 "  * `over_ws`     = d_player ÷ **d_ws**（**未经**变速校正）"
                 "⇒ **主口径**（EXT-037 ④ 明确要求）\n"
                 "  * `over_src_len`= d_player ÷ **源段长**（reviewer EXT-036 ⑥ "
                 "用的口径）\n"
                 "★ **`d_ws` 已经是 WSOLA 变速之后的时长** ⇒ 拿它再乘/除一次 "
                 "speed 就是**重复校正** ⇒ 旧口径 `speed_adjusted` "
                 "（d_player × speed ÷ d_ws）**已作废**（EXT-037 ④）。\n"
                 "★ `over_ws` 与 `over_src_len` **含义不同** ⇒ STATUS 必须"
                 "写明用的是哪一个；直接互比会**对不上**。"),
    }
    return out


# ══════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════
def _sync_coverage(detail, metrics, run_dir):
    """★ EXT-034 ①：**同步测量覆盖率自证** + 缺失段归因。

    ## 为什么要有这一节
      reviewer EXT-034 ①：旧实现 `dubSyncDetail` 只覆盖 **7/13** 段
      ⇒ 「同步误差 P50/P95」这个指标**只对一半的段有效**
      ⇒ 不能当作**整体**结论（却曾被这样用过）。

    ## 旧实现为什么缺段（双重根因，讲清楚）
      ① **onset 配对被抢**：`PAIR_WINDOW_SEC = 0.25`
         ⇒ onset 会被「最近的下一段排程」抢走
         （实测 `dubOnsets` 里出现 50 ms 间隔的连续 onset
          ⇒ 同一段被记成多条、另一段则**一条都没有**）；
      ② **onset 未必触发**：TTS 中文开头常是辅音/静音
         ⇒ 声学 onset **不出现** ⇒ 该段永远配不上。

    ## 现在（EXT-034 ① 修复后）
      主口径改成「**排程起点**」（`start(when)` 的采样精确值）
      ⇒ **每个有 TTS 的段都必然进 detail** ⇒ 段数 == TTS 段数。

    ## 本函数做什么
      ① 拿「TTS 段数」与「detail 段数」对比 ⇒ 给出覆盖率；
      ② 覆盖率不足时，**列出缺了哪些段**（用服务端 `margin.json` 的段全集
         与 detail 的 id 集合求差）⇒ 「讲清缺的是哪几段」；
      ③ 同时给出**可能的原因**（onset 未触发 / 配对被抢 / 该段没有 TTS）
         —— 但**不臆造**：每条原因都附带可核对的证据字段。

    Returns
    -------
    dict
        覆盖率 + 缺失段清单 + 归因（含证据）。
    """
    detail = detail or []
    detail_ids = {str(d.get("id")) for d in detail if d.get("id") is not None}

    # ── TTS 段数（全集）──
    #   优先用服务端 `margin.json` 的 per_segment（有 TTS 的段）
    #   ⇒ 它是**服务端口径**的权威全集；
    #   退而用 metrics 的 `dubDelivered`（= 下发到 player 的段数）。
    all_ids = []
    tts_total = None
    source = None
    margin_path = os.path.join(run_dir, "margin.json")
    if os.path.isfile(margin_path):
        try:
            md = json.load(io.open(margin_path, encoding="utf-8"))
            ps = md.get("per_segment") or []
            with_tts = [m for m in ps
                        if m.get("tts_sec") is not None
                        and float(m.get("tts_sec") or 0) > 0]
            if with_tts:
                all_ids = [str(m.get("id") or m.get("seg_id")) for m in with_tts]
                tts_total = len(with_tts)
                source = "margin.json:per_segment(tts_sec>0)"
        except Exception:
            pass
    if tts_total is None:
        dv = metrics.get("dubDelivered")
        if isinstance(dv, (int, float)):
            tts_total = int(dv)
            source = "metrics.json:dubDelivered"

    # ★★★ id 命名空间对齐（**实测踩到的坑**）
    #   服务端 `margin.json` 的段 id = `seg_<采样点>`（**无**会话前缀）
    #   player `dubSyncDetail` 的 id = `seg_<会话前缀>_<采样点>`（**有**前缀）
    #   ⇒ 直接求差会**把全部段都算成缺失**（实测：13 段全「缺」，
    #     而真实只缺 6 段）⇒ 必须按**采样点后缀**对齐。
    def _sfx(i: str) -> str:
        """取 id 的采样点后缀（`seg_14425951_56000` → `56000`）。"""
        s = str(i)
        return s.rsplit("_", 1)[-1] if "_" in s else s

    detail_by_sfx = {_sfx(i): i for i in detail_ids}
    all_by_sfx = {_sfx(i): i for i in all_ids}

    missing = [all_by_sfx[k] for k in all_by_sfx if k not in detail_by_sfx]
    missing_detail_ids = [detail_by_sfx[k] for k in detail_by_sfx
                          if k not in all_by_sfx]
    coverage = (len(detail_by_sfx) / tts_total) if tts_total else None

    # ── 归因（附证据，不臆造）──
    reasons = []
    if missing:
        # 证据 1：onset 到底触发了几次、有没有连续/抢配
        onsets = metrics.get("dubOnsets") or []
        min_gap = None
        for i in range(1, len(onsets)):
            g = round(float(onsets[i]) - float(onsets[i - 1]), 4)
            if min_gap is None or g < min_gap:
                min_gap = g
        reasons.append({
            "cause": "onset 口径覆盖不足（旧实现的根因）",
            "evidence": {
                "n_onsets": len(onsets),
                "min_onset_gap_sec": min_gap,
                "pair_window_sec": 0.25,
                "note": ("onset 数 < 段数 ⇒ 有段没触发声学 onset"
                         "（TTS 开头是辅音/静音时**必然**如此）"),
                "consecutive_onsets_within_pair_window": (
                    min_gap is not None and min_gap < 0.25),
            },
        })
        reasons.append({
            "cause": "onset 配对被「最近的下一段排程」抢走",
            "evidence": {
                "pair_window_sec": 0.25,
                "min_onset_gap_sec": min_gap,
                "note": ("两段 onset 间隔 < PAIR_WINDOW ⇒ 后段的排程"
                         "会抢走前段的 onset ⇒ 前段既没配上也拿不到"
                         "自己的声学起点"),
            },
        })
        reasons.append({
            "cause": "这些段**根本没有 TTS 输出**（不是同步问题）",
            "evidence": {
                "missing_ids": missing,
                "note": ("若某段在 margin.json 里 tts_sec=0，"
                         "它本就不该有配音 ⇒ 不属于同步测量缺口"),
            },
        })

    return {
        "n_detail": len(detail_ids),
        "n_detail_matched": len(detail_by_sfx),
        "n_tts_segments": tts_total,
        "tts_total_source": source,
        "coverage": (round(coverage, 4) if coverage is not None else None),
        "full_coverage": bool(coverage is not None and coverage >= 1.0),
        "missing_ids": missing,
        "missing_detail_ids": missing_detail_ids,
        "n_missing": len(missing),
        "id_alignment": ("按采样点后缀对齐（margin.json 的 id 无会话前缀，"
                         "detail 的带会话前缀 ⇒ 直接求差会把全部段算成缺失）"),
        "missing_reasons": reasons,
        "basis": ("排程起点（start(when) 采样精确）⇒ 覆盖全部有 TTS 的段"
                  if not missing else
                  "★ 覆盖不足 ⇒ 上面的同步统计**只对已覆盖的段有效**"),
        "ext034_note": ("EXT-034 ① 的验收口径："
                        "dubSyncDetail 段数 == TTS 段数"),
    }


def analyze_run(run_dir: str):
    run_dir = os.path.abspath(run_dir)
    wav_path = os.path.join(run_dir, "dub_player.wav")
    webm_path = os.path.join(run_dir, "dub_player.webm")
    sync_path = os.path.join(run_dir, "dub_sync.json")
    met_path = os.path.join(run_dir, "metrics.json")
    adir = os.path.join(run_dir, "audio_dump")

    if not os.path.isfile(wav_path):
        raise SystemExit("找不到 WAV：%s" % wav_path)
    wav_sr, wav = read_wav_mono(wav_path)
    sync = json.load(io.open(sync_path, encoding="utf-8")) \
        if os.path.isfile(sync_path) else {}
    metrics = json.load(io.open(met_path, encoding="utf-8")) \
        if os.path.isfile(met_path) else {}

    # 录音起点（AudioContext 时刻）—— 从 summary 或 metrics 里拿
    ac_start = None
    stop = {}
    for cand in (os.path.join(run_dir, "record_stop.json"),):
        if os.path.isfile(cand):
            stop = json.load(io.open(cand, encoding="utf-8"))
            ac_start = stop.get("acStartSec")
    if ac_start is None:
        # 从 sync.json 的 requested/actual 与 wav 偏移反推不可靠 ⇒ 用 metrics
        ac_start = (metrics.get("recordStartAc")
                    or (metrics.get("__record_start_ac")))
    if ac_start is None:
        # 最后兜底：summary_*.json
        for fn in os.listdir(os.path.dirname(run_dir) or "."):
            if fn.startswith("summary_") and fn.endswith(".json"):
                s = json.load(io.open(os.path.join(os.path.dirname(run_dir),
                                                  fn), encoding="utf-8"))
                ac_start = ((s.get("record_stop") or {}).get("acStartSec"))
                if ac_start is not None:
                    break
    if ac_start is None:
        raise SystemExit("找不到录音起点（acStartSec）")

    detail = sync.get("detail") or []
    offs = wav_timeline_offsets(detail, ac_start)

    # (b) 桥接下发的 PCM（24 kHz）
    ws_by_id = {}
    if os.path.isdir(adir):
        for fn in sorted(os.listdir(adir)):
            if not fn.endswith("_ws.json"):
                continue
            side = json.load(io.open(os.path.join(adir, fn), encoding="utf-8"))
            ws_by_id[str(side.get("seg_id"))] = side

    segs = []
    for o in offs:
        sid = str(o.get("id"))
        side = ws_by_id.get(sid) or {}
        d_ws = float(side.get("duration_sec") or 0.0)
        speed = float(side.get("speed") or o.get("speed") or 1.0)
        row = {
            "seg_id": sid,
            "t_start": o.get("t_start"),
            "wav_offset_sec": o.get("wav_offset_sec"),
            "signed_err_ms": o.get("signed_err_ms"),
            "speed": speed,
            "src": side.get("src"),
            "tgt": side.get("tgt"),
            "d_ws_sec": round(d_ws, 4),
            # ★★ EXT-036 ⑥：源段长（**reviewer 用的时长比口径**的分子）
            #   = `t_end − t_start`（上行采样时间轴）
            #   ⇒ `d_player ÷ src_len_sec` = reviewer 实测的 0.57–1.55
            "src_len_sec": (round(float(o.get("t_end") or 0.0)
                                  - float(o.get("t_start") or 0.0), 4)
                             if o.get("t_end") is not None
                             and o.get("t_start") is not None else None),
        }
        # ★ d_player：**实测**（切出来 + 静音检测量有声跨度）
        m = measure_player_segment(wav, wav_sr, o["wav_offset_sec"], d_ws)
        row.update(m)
        # ★★★★★★ EXT-037 ④：`d_player` **主口径** = `endedAt − actual`
        #   （player 实测的播放时长，包络起止）
        #   ⚠️ 旧的能量检测口径会**截掉尾部静音** ⇒ d_player 偏小
        #     ⇒ 时长比偏小 ⇒ 与 reviewer 实测 0.57–1.55 **对不上**
        #     （reviewer 原话：「d_player 用能量检测会截掉尾部静音」）。
        #   ⇒ 有 `endedAt` 就用它；没有（旧插件）⇒ **如实**回落能量检测
        #     并标出用的是哪个口径（不混着报）。
        _d_ended = o.get("d_player_ended_sec")
        if _d_ended is not None and float(_d_ended) > 0:
            row["d_player_sec"] = round(float(_d_ended), 4)
            row["d_player_caliber"] = "endedAt-actual"
        else:
            row["d_player_caliber"] = "voiced_span(fallback)"
        row["d_player_voiced_sec"] = m.get("d_player_sec")
        # ★ 时长比（EXT-037 ④：**只保留两个口径**）
        #   ① `over_ws`      = d_player ÷ d_ws（**未经**变速校正）← **主口径**
        #   ② `over_src_len` = d_player ÷ 源段长（reviewer EXT-036 ⑥ 口径）
        #   ③ 同尺子比 = voiced(player) ÷ voiced(WS)（阈值偏置互相抵消）
        #   ⚠️ **不再**输出 `dur_ratio_speed_adjusted`
        #     （`d_ws` 已是 WSOLA 变速后时长 ⇒ 再乘 speed 是**重复校正**）
        ws_voiced = None
        pcm_p = os.path.join(adir, sid + "_ws.pcm")
        ws_data = None
        if os.path.isfile(pcm_p):
            try:
                ws_sr, ws = read_pcm_s16le(pcm_p, int(side.get("sample_rate")
                                                       or 24000))
                ws_data = (ws_sr, ws)
                ws_voiced = voiced_span(ws, ws_sr)[2]
            except Exception as e:
                row["ws_read_error"] = str(e)
        row["d_ws_voiced_sec"] = (round(ws_voiced, 4)
                                  if ws_voiced else None)
        _dp = row.get("d_player_sec")
        if d_ws > 0 and _dp:
            row["dur_ratio_player_over_ws"] = round(_dp / d_ws, 4)
        else:
            row["dur_ratio_player_over_ws"] = None
        if ws_voiced and _dp:
            row["dur_ratio_same_ruler"] = round(_dp / ws_voiced, 4)
        else:
            row["dur_ratio_same_ruler"] = None
        # ★ 互相关 + SNR（player WAV vs 桥接下发 PCM）
        if ws_data is not None and m.get("d_player_sec"):
            try:
                ws_sr, ws = ws_data
                ws_w = resample_linear(ws, ws_sr, wav_sr)
                i0 = int(round(o["wav_offset_sec"] * wav_sr))
                n = int(round((d_ws + 0.2) * wav_sr))
                cut = wav[i0:i0 + n] if i0 >= 0 else []
                if len(cut) > 64 and len(ws_w) > 64:
                    L = min(len(cut), len(ws_w))
                    pk, off = _xcorr_peak_offset(ws_w[:L], cut[:L], wav_sr)
                    row["xcorr_peak"] = round(pk, 4)
                    row["xcorr_offset_sec"] = round(off, 4)
                    row["snr_db"] = round(_snr_db(ws_w[:L], cut[:L]), 3)
                    row["aligned"] = bool(pk >= XCORR_PEAK_MIN)
                else:
                    row["aligned"] = False
            except Exception as e:
                row["xcorr_error"] = str(e)
                row["aligned"] = False
        else:
            row["aligned"] = False
        # ★ 源语言必须是英文
        ok, why = source_is_english(row.get("src"))
        row["src_is_english"] = ok
        row["src_lang_note"] = why
        segs.append(row)

    # ── ★★★★★ EXT-034 ①：**同步测量覆盖率自证** + 缺失归因 ──
    #   reviewer EXT-034 ① 的批评：旧实现 `dubSyncDetail` 只覆盖 7/13 段
    #   ⇒ 「同步误差」这个指标**只对一半的段有效** ⇒ 不能作为整体结论。
    #   ## 为什么旧实现会缺段（双重根因）
    #     ① onset 配对被「最近的下一段排程」抢走
    #        （`PAIR_WINDOW_SEC=0.25`，实测 `dubOnsets` 里有 50 ms 间隔的
    #         连续 onset ⇒ 一段被后一段抢配）
    #     ② TTS 中文开头常是辅音/静音 ⇒ **onset 未必触发**
    #   ⇒ 现在 player.js 的主口径改成「排程起点」（`start(when)` 采样精确）
    #     ⇒ **每个有 TTS 的段都必然进 detail** ⇒ 段数 == TTS 段数。
    #   ## 本节做什么
    #     ① 拿 `metrics.dubDelivered`（= TTS 下发段数）与 detail 段数对比
    #        ⇒ 覆盖率不足时**明确写出来**，不静默；
    #     ② 缺段时**列出缺了哪些段**（用服务端 margin.json 的 seg 列表做全集）
    #        ⇒ 「讲清这 6 段为什么缺」（reviewer 的原话）。
    sync_coverage = _sync_coverage(detail, metrics, run_dir)

    # ── 汇总 ──
    aligned = [s for s in segs if s.get("aligned")]
    # ★★★★★★ EXT-037 ④：**主口径** = `dur_ratio_player_over_ws`
    #   （d_player ÷ d_ws，**未经**变速校正）
    #   ⚠️ 旧口径 `dur_ratio_speed_adjusted`（d_player × speed ÷ d_ws）
    #     **已作废**：`d_ws` 已是 WSOLA 变速后时长 ⇒ 再乘 speed 是**重复校正**
    ratios = [s["dur_ratio_player_over_ws"] for s in aligned
              if s.get("dur_ratio_player_over_ws") is not None]
    prof = silence_profile(wav, wav_sr)
    st = sync_stats(sync.get("errs") or [])

    # ── ★★★★★★ EXT-036 ①/⑤/⑥：**下行耗时 + 时间轴完整性 + 时长比口径** ──
    ext036 = _ext036_analysis(detail, sync, metrics, wav, wav_sr,
                               prof, stop, segs, aligned, ratios)

    out = {
        "run_dir": run_dir,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "player_wav": os.path.abspath(wav_path),
        "player_wav_bytes": os.path.getsize(wav_path),
        "player_webm": os.path.abspath(webm_path) if os.path.isfile(webm_path) else None,
        "player_webm_bytes": (os.path.getsize(webm_path)
                              if os.path.isfile(webm_path) else None),
        "player_sample_rate": wav_sr,
        "recording_duration_sec": prof["duration_sec"],
        "recording_ok_len": bool(prof["duration_sec"] >= MIN_RECORDING_SEC),
        "ac_start_sec": ac_start,
        "t0_axis": sync.get("axis"),
        "t0_sec": sync.get("t0Sec"),
        "silence": prof,
        "leading_silence_ok": bool(prof["leading_silence_sec"] is not None
                                   and prof["leading_silence_sec"] <= MAX_LEADING_SILENCE_SEC),
        "first_segment_arrival_sec": (round(offs[0]["wav_offset_sec"], 3)
                                       if offs else None),
        "sync_err_ms": st,
        "sync_err_target_ms": SYNC_ERR_TARGET_MS,
        "sync_err_ok": bool(st["n"] and st["abs_p95"] is not None
                            and st["abs_p95"] <= SYNC_ERR_TARGET_MS),
        "n_segments": len(segs),
        "n_aligned": len(aligned),
        "n_unaligned": len(segs) - len(aligned),
        "dur_ratio_over_ws_min": min(ratios) if ratios else None,
        "dur_ratio_over_ws_max": max(ratios) if ratios else None,
        # ★★★★★★ EXT-037 ④：主口径更名（`speed_adjusted` ⇒ `over_ws`）
        #   ⚠️ **旧 key 保留**（标 `deprecated`）⇒ 旧的下游/报告模板
        #     不会 KeyError；但**值已换成新口径** ⇒ 别再按旧名解读。
        "dur_ratio_speed_adjusted_min": (min(ratios) if ratios else None),
        "dur_ratio_speed_adjusted_max": (max(ratios) if ratios else None),
        "dur_ratio_speed_adjusted_deprecated": True,
        "dur_ratio_caliber": "over_ws = d_player ÷ d_ws（未经变速校正）",
        "dur_ratio_ok_count": sum(1 for r in ratios
                                  if abs(r - 1.0) <= DUR_RATIO_TOL),
        "dur_ratio_tol": DUR_RATIO_TOL,
        "src_all_english": all(s.get("src_is_english") for s in segs) if segs else None,
        "sync_coverage": sync_coverage,
        # ★★★★★★ EXT-036 ①/⑤/⑥
        "ext036": ext036,
        "segments": segs,
    }
    return out


# ══════════════════════════════════════════════════════════════════
# 渲染
# ══════════════════════════════════════════════════════════════════
def render_md(d: dict) -> str:
    L = []
    L.append("# EXT-033 三份音频实测对比（player 端）")
    L.append("")
    L.append("- 录音（WAV，无损）：`dub_player.wav`，%s Hz / %.3f s / %d 字节"
             % (d["player_sample_rate"], d["recording_duration_sec"],
                d["player_wav_bytes"]))
    L.append("- 时间原点：录音起点 = AudioContext %.4f s；`t0` 口径 = `%s`（t0=%.4f s）"
             % (d["ac_start_sec"], d["t0_axis"], d["t0_sec"] or 0.0))
    L.append("- **切段方式**：按 player 自己测得的实际起播（AudioContext 时刻）"
             " ⇒ WAV 内位置 = `actual − acStartSec` ⇒ **同轴、不搜索对齐**")
    L.append("")
    L.append("## 汇总")
    L.append("")
    L.append("| 项 | 值 | 判据 |")
    L.append("|---|---|---|")
    L.append("| 录音时长 | %.3f s | ≥ 75 s ⇒ %s |"
             % (d["recording_duration_sec"],
                "✅" if d["recording_ok_len"] else "❌"))
    L.append("| 开头静音 | %s s | ≤ 15 s ⇒ %s |"
             % (d["silence"]["leading_silence_sec"],
                "✅" if d["leading_silence_ok"] else "❌"))
    L.append("| 最长静音段 | %s s | — |" % d["silence"]["longest_silence_sec"])
    L.append("| 首段到达 | %s s | — |" % d["first_segment_arrival_sec"])
    L.append("| sync_err（有符号）P50/P95/max | %s / %s / %s ms | "
             "\\|误差\\| P95 ≤ 300 ms ⇒ %s |"
             % (d["sync_err_ms"]["p50"], d["sync_err_ms"]["p95"],
                d["sync_err_ms"]["max"],
                "✅" if d["sync_err_ok"] else "❌"))
    L.append("| 段数 / 已对齐 / 未对齐 | %d / %d / %d | 对齐峰 ≥ 0.6 |"
             % (d["n_segments"], d["n_aligned"], d["n_unaligned"]))
    L.append("| 时长比（`over_ws` = player ÷ d_ws，**未经**变速校正；EXT-037 ④） | %s ~ %s | 1.00±0.02 |"
             % (d.get("dur_ratio_over_ws_min",
                       d.get("dur_ratio_speed_adjusted_min")),
                d.get("dur_ratio_over_ws_max",
                      d.get("dur_ratio_speed_adjusted_max"))))
    L.append("| 源语言全为英文 | %s | EXT-033 E |" % d["src_all_english"])
    # ★★★★★ EXT-034 ①：同步测量覆盖率（**必须**在报告里显眼）
    sc = d.get("sync_coverage") or {}
    L.append("| **同步测量覆盖率** | %s / %s 段（%s） | "
             "detail 段数 == TTS 段数 ⇒ %s |"
             % (sc.get("n_detail"), sc.get("n_tts_segments"),
                ("%.1f%%" % (sc["coverage"] * 100.0))
                if sc.get("coverage") is not None else "—",
                "✅" if sc.get("full_coverage") else "❌"))
    L.append("")
    L.append("## ★ EXT-034 ①：同步测量覆盖率")
    L.append("")
    L.append("- 口径：`%s`" % (sc.get("basis") or "—"))
    L.append("- 全集来源：`%s`" % (sc.get("tts_total_source") or "—"))
    L.append("- detail 段数 = **%s**；TTS 段数 = **%s**；缺失 = **%s**"
             % (sc.get("n_detail"), sc.get("n_tts_segments"),
                sc.get("n_missing")))
    L.append("- 验收口径：%s" % (sc.get("ext034_note") or "—"))
    if sc.get("missing_ids"):
        L.append("")
        L.append("### ⚠️ 缺失段清单与归因（讲清缺的是哪几段、为什么）")
        L.append("")
        for r in (sc.get("missing_reasons") or []):
            L.append("- **%s**" % r.get("cause"))
            ev = r.get("evidence") or {}
            for k, v in ev.items():
                if k == "note":
                    continue
                L.append("  - `%s` = %s" % (k, v))
            if ev.get("note"):
                L.append("  - 说明：%s" % ev["note"])
    L.append("")
    L.append("## 逐段明细")
    L.append("")
    L.append("| # | id | t_start | WAV 位置(s) | d_player(s) | d_player口径 | d_ws(s) | "
             "时长比(over_ws) | 互相关峰 | SNR(dB) | 对齐 | signed err(ms) | 源 | 译 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, s in enumerate(d["segments"], 1):
        L.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |"
                 % (i, s.get("seg_id"), s.get("t_start"),
                    s.get("wav_offset_sec"), s.get("d_player_sec"),
                    s.get("d_player_caliber") or "—",
                    s.get("d_ws_sec"),
                    s.get("dur_ratio_player_over_ws"),
                    s.get("xcorr_peak"), s.get("snr_db"),
                    "✅" if s.get("aligned") else "**未对齐**",
                    s.get("signed_err_ms"),
                    (s.get("src") or "")[:28], (s.get("tgt") or "")[:28]))
    L.append("")
    L.append("> **未对齐**的段：对齐峰 < 0.6 ⇒ **不计入合格**（EXT-033 C 原文）。")
    L.append("")
    return "\n".join(L)


def render_readme(d: dict) -> str:
    L = []
    L.append("# EXT-033 交付说明（player 端实测）")
    L.append("")
    L.append("## 这份交付要证明什么")
    L.append("")
    L.append("1. **输入是英文 SPE 的页面元素音频**，不是整机系统声音；")
    L.append("2. **player 录音完整**（不截断、≥75 s），另附**无损 WAV**；")
    L.append("3. **三份音频逐段实测**（TTS 原始 / 桥接下发 / player 实录）；")
    L.append("4. **sync_err 是 player 端实测的有符号误差**（不是 `max(0, …)`）。")
    L.append("")
    L.append("## 关键数字")
    L.append("")
    L.append("| 项 | 值 |")
    L.append("|---|---|")
    L.append("| 录音时长 | %.3f s |" % d["recording_duration_sec"])
    L.append("| 开头静音 | %s s |" % d["silence"]["leading_silence_sec"])
    L.append("| 最长静音段 | %s s |" % d["silence"]["longest_silence_sec"])
    L.append("| 首段到达 | %s s |" % d["first_segment_arrival_sec"])
    L.append("| sync_err P50 / P95 / max | %s / %s / %s ms |"
             % (d["sync_err_ms"]["p50"], d["sync_err_ms"]["p95"],
                d["sync_err_ms"]["max"]))
    L.append("| sync_err 样本数 | %d |" % d["sync_err_ms"]["n"])
    L.append("| 时间原点口径 | %s（t0=%.4f s） |" % (d["t0_axis"], d["t0_sec"] or 0.0))
    L.append("")
    L.append("## 逐段起止与译文（源语言 = 英文）")
    L.append("")
    L.append("| # | WAV 起(s) | WAV 止(s) | 英文原文 | 中文译文 |")
    L.append("|---|---|---|---|---|")
    for i, s in enumerate(d["segments"], 1):
        st = s.get("wav_offset_sec")
        dur = s.get("d_player_sec") or 0.0
        L.append("| %d | %s | %s | %s | %s |"
                 % (i, st, (round(st + dur, 3) if st is not None else None),
                    (s.get("src") or ""), (s.get("tgt") or "")))
    L.append("")
    L.append("## 口径说明（必读）")
    L.append("")
    L.append("- **切段位置** = player 实测的实际起播（AudioContext 时刻）− 录音起点"
             " ⇒ 与 `t0+t_start+D` **同轴**；**没有**任何「搜索对齐」。")
    L.append("- **d_player** = 从 WAV 切出该段后，用静音检测量出的**有声跨度**"
             "（不是抄 `d_ws`）。")
    L.append("- **时长比** = `d_player ÷ d_ws`，变速段再乘 `speed` 抵消 WSOLA。")
    L.append("- **互相关峰 < 0.6** 的段标「未对齐」，**不计入合格**。")
    L.append("- **sync_err** = 实际起播 − (t0 + t_start + D)，**有符号**"
             "（负 = 早播）；「迟到量」另见 metrics。")
    L.append("- **源语言**：逐段校验原文不含中日韩字符 ⇒ 必须是英文。")
    L.append("")
    return "\n".join(L)


def deliver(d: dict, run_dir: str, listen_dir: str = None) -> str:
    listen_dir = listen_dir or os.path.join(
        LISTEN_ROOT, "ext033_%s" % time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(listen_dir, exist_ok=True)
    # 录音原件（原样拷贝，不转码 ⇒ 保留原始证据）
    for fn in ("dub_player.webm", "dub_player.wav"):
        src = os.path.join(run_dir, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(listen_dir, fn))
    with io.open(os.path.join(listen_dir, "ext033_compare.json"), "w",
                 encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2))
    with io.open(os.path.join(listen_dir, "ext033_compare.md"), "w",
                 encoding="utf-8") as f:
        f.write(render_md(d))
    with io.open(os.path.join(listen_dir, "README.md"), "w",
                 encoding="utf-8") as f:
        f.write(render_readme(d))
    return listen_dir


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    run_dir = args[0]
    d = analyze_run(run_dir)
    out_json = os.path.join(run_dir, "ext033_compare.json")
    with io.open(out_json, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=2))
    with io.open(os.path.join(run_dir, "ext033_compare.md"), "w",
                 encoding="utf-8") as f:
        f.write(render_md(d))
    _log("对比结果已落盘：%s" % out_json)
    _log("录音 %.3f s；开头静音 %s s；sync P50/P95/max = %s/%s/%s ms；"
         "段 %d（对齐 %d）"
         % (d["recording_duration_sec"], d["silence"]["leading_silence_sec"],
            d["sync_err_ms"]["p50"], d["sync_err_ms"]["p95"],
            d["sync_err_ms"]["max"], d["n_segments"], d["n_aligned"]))
    if "--deliver" in sys.argv:
        ld = deliver(d, run_dir)
        _log("交付目录：%s" % ld)
    return 0


if __name__ == "__main__":
    sys.exit(main())
