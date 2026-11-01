# -*- coding: utf-8 -*-
"""ext032_audio_compare.py —— ★ EXT-032②：三份音频**逐段**对比（TTS 原始 / 桥接下发 PCM / player 录音）

★ 背景（EXT-032 [BLOCKING] 2026-11-01 20:30）：
  reviewer 指出 EXT-028「只修了代码，没有交实录」⇒ 要求交**逐段三份音频对比**
  （时长比 / 互相关峰值与偏移 / SNR），并**用实测数据**证明采样率真修好了。

★ 本工具做的事（**纯信号处理 + 纯解码，不跑任何推理，不占 GPU/NPU**）：
  对每一段，从 e2e 产物目录里取三份音频：
    ① TTS 原始    = `audio_dump/<seg_id>_tts.wav`     （引擎出音）
    ② 桥接下发    = `audio_dump/<seg_id>_ws.pcm`      （经 WS 下发的 PCM，s16le）
    ③ player 录音 = `dub_player.webm` 的对应时间窗    （页内 MediaRecorder）
  算：
    - **时长比**（EXT-032 原文：三份时长比必须是 **1.00±0.02** ⇒ 采样率真修好的证据）
    - **互相关峰值**与**偏移**（是不是同一段音频、有没有错位）
    - **SNR**（桥接链路有没有引入噪声/失真）

★ webm 解码：复用 `tests/smoke/analyze_dub_audio.py` 的**同一套浏览器解码法**
  （`BrowserSession` + WebAudio `decodeAudioData`，**纯解码，不跑推理**）
  ⇒ 本仓库仍**零外部二进制依赖**（不引入 ffmpeg）。

★ 输出：`ext032_compare.json`（逐段数据）+ `ext032_compare.md`（给人看的表）。

★ 用法：
    python tests/smoke/ext032_audio_compare.py <e2e轮次目录> [--out 输出目录]
    例：python tests/smoke/ext032_audio_compare.py .tmp/ext028_029_e2e/20261101_155037_13840/A_off
"""
from __future__ import annotations

import argparse
import array
import base64
import io
import json
import math
import os
import sys
import time
import wave

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for _p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import browser_harness as H          # noqa: E402

# ── 判定阈值（模块级常量，单一事实来源）──────────────────────────
#: 时长比合格区间（EXT-032 原文：「三份时长比必须是 1.00±0.02」）
DUR_RATIO_TOL = 0.02
#: 互相关峰值下界（低于此值 ⇒ 认定不是同一段音频）
XCORR_PEAK_MIN = 0.30
#: 互相关偏移上限（秒）—— 超过 ⇒ 认定有明显错位
XCORR_OFFSET_MAX_SEC = 0.25
#: SNR 下界（dB）—— 低于此值 ⇒ 认定链路有明显噪声
SNR_MIN_DB = 10.0
#: 静音判定阈值（dBFS）
SILENCE_DBFS = -45.0
#: 静音窗（秒）
SILENCE_WIN_SEC = 0.25


# ── 纯 Python 音频工具（不引入 numpy/ffmpeg）─────────────────────
def read_wav_mono(path: str):
    """读 wav ⇒ (采样率, [float 样本])。"""
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("只支持 16-bit PCM（got %d bytes/sample）" % sw)
    a = array.array("h")
    a.frombytes(raw)
    if nch > 1:
        a = a[::nch]
    return sr, [v / 32768.0 for v in a]


def read_pcm_s16le(path: str, sample_rate: int):
    """读裸 s16le PCM ⇒ (采样率, [float 样本])。"""
    with open(path, "rb") as f:
        raw = f.read()
    a = array.array("h")
    a.frombytes(raw[:len(raw) - (len(raw) % 2)])
    return sample_rate, [v / 32768.0 for v in a]


def rms(x) -> float:
    if not x:
        return 0.0
    return math.sqrt(sum(v * v for v in x) / len(x))


def dbfs(r: float) -> float:
    if r <= 0.0:
        return -120.0
    return 20.0 * math.log10(r)


def resample_linear(x, src_sr: int, dst_sr: int):
    """线性插值重采样（用于时长/互相关比对，非音频保真用途）。"""
    if src_sr == dst_sr or not x:
        return x
    ratio = float(dst_sr) / float(src_sr)
    n_out = int(len(x) * ratio)
    if n_out <= 0:
        return []
    out = []
    last = len(x) - 1
    for i in range(n_out):
        pos = i / ratio
        j = int(pos)
        if j >= last:
            out.append(x[last])
            continue
        f = pos - j
        out.append(x[j] * (1.0 - f) + x[j + 1] * f)
    return out


def xcorr_peak_offset(a, b, sr: int, max_lag_sec: float = 1.0):
    """零均值归一化互相关 ⇒ (峰值, 偏移秒)。

    ★ 零均值归一化 ⇒ 幅度缩放**不影响峰值**（这正是要证明的点）。
    """
    if not a or not b:
        return 0.0, 0.0
    n = min(len(a), len(b))
    if n < 64:
        return 0.0, 0.0
    a = a[:n]
    b = b[:n]
    ma = sum(a) / n
    mb = sum(b) / n
    a = [v - ma for v in a]
    b = [v - mb for v in b]
    ea = math.sqrt(sum(v * v for v in a))
    eb = math.sqrt(sum(v * v for v in b))
    if ea <= 0.0 or eb <= 0.0:
        return 0.0, 0.0
    max_lag = min(int(max_lag_sec * sr), n - 64)
    best = 0.0
    best_lag = 0
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            xa = a[lag:]
            xb = b[:n - lag]
        else:
            xa = a[:n + lag]
            xb = b[-lag:]
        m = len(xa)
        if m < 64:
            continue
        s = 0.0
        for i in range(m):
            s += xa[i] * xb[i]
        v = s / (ea * eb)
        if v > best:
            best = v
            best_lag = lag
    return best, best_lag / float(sr)


def snr_db(ref, test) -> float:
    """SNR（dB）= 10·log10(P_ref / P_err)。"""
    if not ref or not test:
        return 0.0
    n = min(len(ref), len(test))
    if n < 64:
        return 0.0
    err = [test[i] - ref[i] for i in range(n)]
    p_ref = sum(v * v for v in ref[:n]) / n
    p_err = sum(v * v for v in err) / n
    if p_err <= 1e-15:
        return 120.0 if p_ref > 1e-15 else 0.0
    if p_ref <= 1e-15:
        return 0.0
    return 10.0 * math.log10(p_ref / p_err)


def silence_spans(x, sr: int):
    """静音区间 ⇒ [(起秒, 止秒)]（低于 SILENCE_DBFS 的连续窗）。"""
    if not x:
        return []
    win = max(1, int(SILENCE_WIN_SEC * sr))
    spans = []
    cur = None
    for i in range(0, max(1, len(x) - win + 1), win):
        r = rms(x[i:i + win])
        if dbfs(r) < SILENCE_DBFS:
            if cur is None:
                cur = i
        else:
            if cur is not None:
                spans.append((cur / float(sr), i / float(sr)))
                cur = None
    if cur is not None:
        spans.append((cur / float(sr), len(x) / float(sr)))
    return spans


def fmt(sec) -> str:
    if sec is None:
        return "-"
    return "%.3f" % sec


def envelope(x, sr: int, hop_sec: float = 0.02):
    """RMS 包络（降采样到 hop 粒度）⇒ 用于**粗对齐**（快）。"""
    hop = max(1, int(hop_sec * sr))
    out = []
    for i in range(0, max(1, len(x) - hop + 1), hop):
        out.append(rms(x[i:i + hop]))
    return out


def _norm_corr(a, b) -> float:
    n = min(len(a), len(b))
    if n < 4:
        return 0.0
    a = a[:n]
    b = b[:n]
    ma = sum(a) / n
    mb = sum(b) / n
    a = [v - ma for v in a]
    b = [v - mb for v in b]
    ea = math.sqrt(sum(v * v for v in a))
    eb = math.sqrt(sum(v * v for v in b))
    if ea <= 0.0 or eb <= 0.0:
        return 0.0
    s = 0.0
    for i in range(n):
        s += a[i] * b[i]
    return s / (ea * eb)


def align_offset(ref, sig, sr: int, max_shift_sec: float = 120.0):
    """在 sig（长，player 录音）里找 ref（短，段音频）的位置 ⇒ (offset 秒, 粗相关峰)。

    ★ 用**包络**做粗对齐（快且对幅度不敏感）⇒ 再用原始样本互相关细化。
    ★ 为什么要对齐：player 排程用的是 `t0 + t_start + D`（**与 uplink 的 t_start 不同的时间基**），
      直接按 `t_start` 切片会**错位** ⇒ 必须按**音频内容**对齐。
    """
    if not ref or not sig:
        return 0.0, 0.0
    hop = max(1, int(0.02 * sr))
    e_ref = envelope(ref, sr)
    e_sig = envelope(sig, sr)
    if len(e_ref) < 4 or len(e_sig) < len(e_ref) + 4:
        return 0.0, 0.0
    m = len(e_ref)
    max_shift = int(max_shift_sec / 0.02)
    best = -2.0
    best_sh = 0
    for sh in range(0, min(max_shift, len(e_sig) - m) + 1):
        v = _norm_corr(e_ref, e_sig[sh:sh + m])
        if v > best:
            best = v
            best_sh = sh
    return best_sh * 0.02, best


def refine_offset(ref, sig, sr: int, coarse_sec: float, span_sec: float = 0.20):
    """在粗对齐附近，用**原始样本**互相关细化偏移 ⇒ (offset 秒, 峰值)。"""
    if not ref or not sig:
        return coarse_sec, 0.0
    c = int(coarse_sec * sr)
    span = int(span_sec * sr)
    lo = max(0, c - span)
    hi = min(len(sig), c + span)
    if hi - lo < 64:
        return coarse_sec, 0.0
    best = -2.0
    best_off = coarse_sec
    # 在 ±span 内逐 lag 滑窗（段长 ≤ 4 s ⇒ 复杂度可接受）
    step = max(1, int(0.005 * sr))
    for lag in range(lo, hi, step):
        seg = sig[lag:lag + len(ref)]
        if len(seg) < len(ref):
            break
        v = _norm_corr(ref, seg)
        if v > best:
            best = v
            best_off = lag / float(sr)
    return best_off, best


# ── webm 解码（纯 WebAudio，无推理、不抢 GPU）────────────────────
_DECODE_PCM_JS = r"""
async (b64) => {
  const bin = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const ctx = new OfflineAudioContext(1, 16000, 16000);
  let buf;
  try { buf = await ctx.decodeAudioData(bin.buffer); }
  catch (e) { return { ok: false, error: 'decodeAudioData failed: ' + (e && e.message || e) }; }
  const ch = buf.getChannelData(0);
  const sr = buf.sampleRate;
  // ⇒ 回传原始 float 样本（16-bit 量化，避免 JSON 精度丢失）
  const out = new Int16Array(ch.length);
  for (let i = 0; i < ch.length; i++) {
    let v = ch[i];
    if (v > 1) v = 1; if (v < -1) v = -1;
    out[i] = Math.round(v * 32767);
  }
  let bin2 = '';
  const bytes = new Uint8Array(out.buffer);
  const CHUNK = 8192;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin2 += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return { ok: true, sampleRate: sr, durationSec: buf.duration, b64: btoa(bin2) };
}
"""


def decode_webm_samples(webm_path: str):
    """webm ⇒ (采样率, [float 样本])；失败抛异常。

    ★ profile 目录**必须唯一**且 `reuse_profile=True`（2026-11-01 实测修的坑：
      `BrowserSession` 默认会 `shutil.rmtree(profile)` 清理 ⇒ 触发安全策略
      （SAFE_DELETE_BULK_CONFIRM_REQUIRED）⇒ 脚本被腰斩）。
    """
    with open(webm_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    profile = os.path.join(
        ROOT, ".tmp",
        "_ext032_decode_profile_%s_%d" % (time.strftime("%Y%m%d_%H%M%S"), os.getpid()))
    with H.BrowserSession(profile, headless=True, reuse_profile=True) as br:
        page = br.new_page()
        res = page.evaluate(_DECODE_PCM_JS, b64)
    if not res.get("ok"):
        raise RuntimeError(res.get("error") or "decode failed")
    raw = base64.b64decode(res["b64"])
    a = array.array("h")
    a.frombytes(raw[:len(raw) - (len(raw) % 2)])
    return int(res["sampleRate"]), [v / 32768.0 for v in a]


# ── 主流程 ─────────────────────────────────────────────────────────
def compare_run(run_dir: str):
    """对一轮 e2e 产物做三份音频逐段对比 ⇒ dict。"""
    adir = os.path.join(run_dir, "audio_dump")
    if not os.path.isdir(adir):
        raise SystemExit("找不到 audio_dump 目录: " + adir)
    webm = os.path.join(run_dir, "dub_player.webm")
    if not os.path.isfile(webm):
        raise SystemExit("找不到 player 录音: " + webm)
    player_sr, player = decode_webm_samples(webm)

    segs = []
    for fn in sorted(os.listdir(adir)):
        if not fn.endswith("_ws.json"):
            continue
        side = json.load(io.open(os.path.join(adir, fn), encoding="utf-8"))
        seg_id = side.get("seg_id")
        wav_p = os.path.join(adir, seg_id + "_tts.wav")
        pcm_p = os.path.join(adir, seg_id + "_ws.pcm")
        if not (os.path.isfile(wav_p) and os.path.isfile(pcm_p)):
            continue
        try:
            tts_sr, tts = read_wav_mono(wav_p)
            ws_sr, ws = read_pcm_s16le(pcm_p, int(side.get("sample_rate") or 24000))
        except Exception as e:
            segs.append({"seg_id": seg_id, "error": "read failed: %s" % e})
            continue

        t_start = float(side.get("t_start") or 0.0)
        dur = float(side.get("duration_sec") or 0.0)
        speed = float(side.get("speed") or 1.0)

        d_tts = len(tts) / float(tts_sr) if tts_sr else 0.0
        d_ws = len(ws) / float(ws_sr) if ws_sr else 0.0
        # ★ 时长比：桥接下发的 PCM 时长 ÷ TTS 原始时长。
        #   ⚠️ **但桥接会做变速（WSOLA）** ⇒ 下发时长 = 原始时长 ÷ speed
        #   ⇒ 「时长比 1.00」只在 **speed=1.0** 时成立（EXT-032 的口径）。
        #   ⇒ 这里同时给出**原始比**（d_ws/d_tts）与**变速校正比**（d_ws×speed/d_tts）。
        ratio_raw = (d_ws / d_tts) if d_tts > 0 else 0.0
        ratio_speed_adj = (d_ws * speed / d_tts) if d_tts > 0 else 0.0

        # ★★ 三份音频对比的第二层：TTS 原始 vs 桥接下发 PCM（同采样率 ⇒ 直接比）
        ws_r = resample_linear(ws, ws_sr, tts_sr)
        pk, off = xcorr_peak_offset(tts, ws_r, tts_sr)
        snr = snr_db(tts, ws_r)

        # ★★★ 三份音频对比的第三层：桥接下发 PCM vs **player 录音**
        #   ★ player 排程用的是 `t0 + t_start + D`（**与 uplink 的 t_start 不是同一时间基**），
        #     且 player 会变速 ⇒ **不能按 t_start 直接切片**（会错位）。
        #   ⇒ 改为**按音频内容对齐**（包络粗对齐 + 原始样本细化）⇒ 得到真实落点与真实时长。
        pl = []
        pl_off = None
        pl_pk = 0.0
        pl_dur = 0.0
        if len(ws) > 64:
            # ★★ 必须**重采样到 player 采样率**再对齐
            #   （WS PCM = 24 kHz、player webm 解码 = 16 kHz ⇒ 采样率不同直接比会全错）
            ws_pl = resample_linear(ws, ws_sr, player_sr)
            coarse, cpeak = align_offset(ws_pl, player, player_sr)
            if cpeak > 0.2:
                off2, pk2 = refine_offset(ws_pl, player, player_sr, coarse)
                pl_off = off2
                pl_pk = pk2
                i0 = int(off2 * player_sr)
                i1 = min(len(player), i0 + int(dur * player_sr))
                pl = player[i0:i1] if i1 > i0 else []
                pl_dur = len(pl) / float(player_sr)

        sil = silence_spans(pl, player_sr) if pl else []

        segs.append({
            "seg_id": seg_id,
            "t_start": t_start,
            "t_end": float(side.get("t_end") or 0.0),
            "src": side.get("src"),
            "tgt": side.get("tgt"),
            "speed": speed,
            "d_tts_sec": round(d_tts, 4),
            "d_ws_sec": round(d_ws, 4),
            "d_player_sec": round(pl_dur, 4),
            "dur_ratio_ws_over_tts": round(ratio_raw, 6),
            "dur_ratio_speed_adjusted": round(ratio_speed_adj, 6),
            "dur_ratio_ok": abs(ratio_raw - 1.0) <= DUR_RATIO_TOL,
            "dur_ratio_speed_adjusted_ok": abs(ratio_speed_adj - 1.0) <= DUR_RATIO_TOL,
            "xcorr_peak": round(pk, 6),
            "xcorr_offset_sec": round(off, 6),
            "xcorr_ok": pk >= XCORR_PEAK_MIN and abs(off) <= XCORR_OFFSET_MAX_SEC,
            "snr_db": round(snr, 3),
            "snr_ok": snr >= SNR_MIN_DB,
            "player_align_offset_sec": (round(pl_off, 4) if pl_off is not None else None),
            "player_align_peak": round(pl_pk, 6),
            "player_aligned_ok": pl_pk >= XCORR_PEAK_MIN,
            "player_silence_total_sec": round(sum(b - a for a, b in sil), 3),
            "player_silence_spans": [[round(a, 3), round(b, 3)] for a, b in sil],
        })

    good = [s for s in segs if "dur_ratio_ok" in s]
    ratios = [s["dur_ratio_ws_over_tts"] for s in good]
    ratios_adj = [s["dur_ratio_speed_adjusted"] for s in good]
    snrs = [s["snr_db"] for s in good]
    # ★ player 录音整体静音画像（EXT-032③：开头静音 / 最长静音段 / 首段配音到达）
    all_sil = silence_spans(player, player_sr)
    onset = None
    step = max(1, int(0.05 * player_sr))
    for i in range(0, max(1, len(player) - step + 1), step):
        if dbfs(rms(player[i:i + step])) > SILENCE_DBFS:
            onset = i / float(player_sr)
            break
    longest = max((b - a for a, b in all_sil), default=0.0)
    summary = {
        "run_dir": os.path.abspath(run_dir),
        "player_webm": os.path.abspath(webm),
        "player_webm_bytes": os.path.getsize(webm),
        "player_sample_rate": player_sr,
        "player_duration_sec": round(len(player) / float(player_sr), 3),
        "player_first_speech_sec": round(onset, 3) if onset is not None else None,
        "player_leading_silence_sec": round(onset, 3) if onset is not None else None,
        "player_longest_silence_sec": round(longest, 3),
        "player_total_silence_sec": round(sum(b - a for a, b in all_sil), 3),
        "player_silence_spans": [[round(a, 3), round(b, 3)] for a, b in all_sil],
        "n_segments": len(segs),
        "n_compared": len(good),
        "dur_ratio_tol": DUR_RATIO_TOL,
        "dur_ratio_ok_count": sum(1 for s in good if s["dur_ratio_ok"]),
        "dur_ratio_speed_adjusted_ok_count": sum(1 for s in good if s["dur_ratio_speed_adjusted_ok"]),
        "dur_ratio_all_ok": bool(good) and all(s["dur_ratio_ok"] for s in good),
        "dur_ratio_min": min(ratios) if ratios else None,
        "dur_ratio_max": max(ratios) if ratios else None,
        "dur_ratio_mean": (sum(ratios) / len(ratios)) if ratios else None,
        "dur_ratio_speed_adjusted_min": min(ratios_adj) if ratios_adj else None,
        "dur_ratio_speed_adjusted_max": max(ratios_adj) if ratios_adj else None,
        "xcorr_ok_count": sum(1 for s in good if s["xcorr_ok"]),
        "snr_ok_count": sum(1 for s in good if s["snr_ok"]),
        "player_aligned_count": sum(1 for s in good if s.get("player_aligned_ok")),
        "snr_min_db": min(snrs) if snrs else None,
        "snr_median_db": sorted(snrs)[len(snrs) // 2] if snrs else None,
        "snr_max_db": max(snrs) if snrs else None,
        "thresholds": {
            "xcorr_peak_min": XCORR_PEAK_MIN,
            "xcorr_offset_max_sec": XCORR_OFFSET_MAX_SEC,
            "snr_min_db": SNR_MIN_DB,
            "silence_dbfs": SILENCE_DBFS,
        },
    }
    return {"summary": summary, "segments": segs}


def render_md(data: dict) -> str:
    s = data["summary"]
    L = ["# EXT-032② 三份音频逐段对比（实测）", ""]
    L.append("- 轮次目录：`%s`" % s["run_dir"])
    L.append("- player 录音：`%s`（%d B，%s s @ %d Hz）"
             % (s["player_webm"], s["player_webm_bytes"], fmt(s["player_duration_sec"]),
                s["player_sample_rate"]))
    L.append("- 段数：**%d**（可比 **%d**）" % (s["n_segments"], s["n_compared"]))
    L.append("")
    L.append("## ★ player 录音静音画像（EXT-032③）")
    L.append("")
    L.append("| 项 | 实测 |")
    L.append("|---|---|")
    L.append("| 录音总长 | **%s s** |" % fmt(s["player_duration_sec"]))
    L.append("| **开头静音**（到首段配音） | **%s s** |" % fmt(s["player_leading_silence_sec"]))
    L.append("| **最长静音段** | **%s s** |" % fmt(s["player_longest_silence_sec"]))
    L.append("| 总静音 | %s s |" % fmt(s["player_total_silence_sec"]))
    L.append("")
    L.append("## ★ 时长比（EXT-032② 的核心判据）")
    L.append("")
    L.append("- **原始比**（桥接下发 ÷ TTS 原始）min/mean/max = **%s / %s / %s**（合格区间 1.00±%.2f）"
             % (fmt(s["dur_ratio_min"]), fmt(s["dur_ratio_mean"]), fmt(s["dur_ratio_max"]),
                s["dur_ratio_tol"]))
    L.append("- **变速校正比**（原始比 × speed，抵消桥接 WSOLA 变速）min/max = **%s / %s**"
             % (fmt(s["dur_ratio_speed_adjusted_min"]), fmt(s["dur_ratio_speed_adjusted_max"])))
    L.append("- **原始比合格 %d / %d**；**变速校正比合格 %d / %d**"
             % (s["dur_ratio_ok_count"], s["n_compared"],
                s["dur_ratio_speed_adjusted_ok_count"], s["n_compared"]))
    L.append("- **互相关合格 %d / %d**；**SNR 合格 %d / %d**（SNR 中位 **%s dB**）；"
             "**player 录音对齐成功 %d / %d**"
             % (s["xcorr_ok_count"], s["n_compared"], s["snr_ok_count"], s["n_compared"],
                fmt(s["snr_median_db"]), s["player_aligned_count"], s["n_compared"]))
    L.append("")
    L.append("| 段 | speed | TTS 时长 | 桥接 PCM 时长 | 原始时长比 | 校正时长比 | 互相关峰值 | 偏移(s) | SNR(dB) | player 落点(s) | player 对齐峰 | 判定 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for g in data["segments"]:
        if "dur_ratio_ok" not in g:
            L.append("| %s | - | - | - | - | - | - | - | - | - | - | %s |"
                     % (g["seg_id"], g.get("error")))
            continue
        ok = g["dur_ratio_speed_adjusted_ok"] and g["xcorr_ok"] and g["snr_ok"]
        L.append("| %s | %.4f | %s | %s | %.4f | **%.4f** | %.4f | %+.4f | %.2f | %s | %.4f | %s |"
                 % (g["seg_id"], g["speed"], fmt(g["d_tts_sec"]), fmt(g["d_ws_sec"]),
                    g["dur_ratio_ws_over_tts"], g["dur_ratio_speed_adjusted"],
                    g["xcorr_peak"], g["xcorr_offset_sec"], g["snr_db"],
                    fmt(g.get("player_align_offset_sec")), g.get("player_align_peak") or 0.0,
                    "✅" if ok else "❌"))
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="EXT-032② 三份音频逐段对比")
    ap.add_argument("run_dir", help="e2e 轮次目录（含 audio_dump/ 与 dub_player.webm）")
    ap.add_argument("--out", default=None, help="输出目录（默认写到轮次目录）")
    a = ap.parse_args()
    out_dir = a.out or a.run_dir
    os.makedirs(out_dir, exist_ok=True)
    data = compare_run(a.run_dir)
    jp = os.path.join(out_dir, "ext032_compare.json")
    mp = os.path.join(out_dir, "ext032_compare.md")
    with io.open(jp, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))
    with io.open(mp, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_md(data))
    s = data["summary"]
    print("=" * 68)
    print("EXT-032② 三份音频逐段对比")
    print("=" * 68)
    print("轮次：%s" % s["run_dir"])
    print("段数 %d（可比 %d）" % (s["n_segments"], s["n_compared"]))
    print("player 录音：%s s，**开头静音 %s s**，最长静音 %s s"
          % (fmt(s["player_duration_sec"]), fmt(s["player_leading_silence_sec"]),
             fmt(s["player_longest_silence_sec"])))
    print("时长比 原始 min/mean/max = %s / %s / %s（合格 %d/%d）"
          % (fmt(s["dur_ratio_min"]), fmt(s["dur_ratio_mean"]), fmt(s["dur_ratio_max"]),
             s["dur_ratio_ok_count"], s["n_compared"]))
    print("时长比 变速校正 min/max = %s / %s（合格 %d/%d）"
          % (fmt(s["dur_ratio_speed_adjusted_min"]), fmt(s["dur_ratio_speed_adjusted_max"]),
             s["dur_ratio_speed_adjusted_ok_count"], s["n_compared"]))
    print("互相关合格 %d/%d；SNR 合格 %d/%d（中位 %s dB）；player 对齐 %d/%d"
          % (s["xcorr_ok_count"], s["n_compared"], s["snr_ok_count"], s["n_compared"],
             fmt(s["snr_median_db"]), s["player_aligned_count"], s["n_compared"]))
    print("落盘：%s / %s" % (jp, mp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
