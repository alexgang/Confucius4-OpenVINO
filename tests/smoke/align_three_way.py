"""align_three_way.py — ★★★ EXT-028 ①：**三份音频逐段对齐**（定位失真发生在哪一环）

## 为什么需要这个工具（reviewer EXT-028 明文）

> 每段落盘三份音频，逐段对比：
> - (a) 桥接侧 TTS 原始输出 wav；
> - (b) 桥接下发前的 PCM（也就是 WS 发出的那份，按发出的格式原样存）；
> - (c) player 端 MediaRecorder 录到的同一段。
> 三份要对齐时长和采样率，算互相关/SNR，找出是哪一环开始失真：
> 采样率或声道错配、int16/float32 解释错、字节序、chunk 拼接、增益、叠播。

## 三份音频的**确切含义**（不要混淆）

| 编号 | 是什么 | 落盘名 | 采样率 | 回答什么问题 |
|---|---|---|---|---|
| (a) | **TTS 引擎的原始输出**（未经变速） | `*_tts.wav` | 24 kHz | 模型本身对不对 |
| (b) | **WS 实际发出的那份**（WSOLA 变速后、base64 之前） | `*_ws.pcm` | 24 kHz | 服务端下发环节有没有改坏 |
| (c) | **player 录到的**（MediaRecorder ⇒ opus/webm） | `dub_player.webm` | 48 kHz(opus) | 浏览器这一环有没有改坏 |

★ **(a) → (b) 的差异 = 服务端变速（WSOLA）的影响**
★ **(b) → (c) 的差异 = 浏览器解码/重采样/混音/录音的影响**
★ **失真起点 = 第一个出现异常的那一步**

## 判定口径（全部**可复现**，落进 JSON）

| 指标 | 定义 | 阈值（可调） |
|---|---|---|
| `duration_ratio` | 两份的时长比 | 偏离 1 超过 5% ⇒ 报 `dur_mismatch` |
| `xcorr_peak` | 归一化互相关的峰值（−1..1） | < 0.5 ⇒ 报 `content_mismatch` |
| `xcorr_lag_sec` | 互相关峰值对应的时移 | 绝对值 > 0.25 s ⇒ 报 `time_shift` |
| `snr_db` | 10·log10(信号功率/噪声功率) | < 15 dB ⇒ 报 `low_snr` |
| `gain_db` | RMS 比（dB） | 绝对值 > 6 dB ⇒ 报 `gain_mismatch` |
| `sample_rate` | 采样率 | 不一致 ⇒ 报 `sr_mismatch`（**这是 EXT-028 的头号根因**） |

## ★ 铁律

* **只做纯数学**（numpy）⇒ 不跑任何推理 ⇒ 不抢 GPU/NPU；
* (c) 是 opus ⇒ 解码交给浏览器（WebAudio `decodeAudioData`），
  与 `analyze_dub_audio.py` 同一套办法（仓库零外部二进制依赖）；
* **没对齐上的段如实标 `unaligned`** ⇒ 绝不臆造互相关值。

跑法：
    python tests/smoke/align_three_way.py --a-dump <目录> --c-webm <录音.webm> \
        --out <输出.json>
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import struct
import sys
import time
from typing import List, Optional, Tuple

SMOKE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(SMOKE_DIR))
for p in (SMOKE_DIR, os.path.join(ROOT, "tools"), ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import numpy as np

import browser_harness as H          # noqa: E402

# ── 判定阈值（单一事实来源，可 CLI 覆盖）─────────────────────────
TH_SR = 1.05          # 采样率一致（1.0 = 完全相同）
TH_DUR = 0.05         # 时长相对偏差 5%
TH_XCORR = 0.50       # 互相关峰值下限
TH_LAG_SEC = 0.25     # 时移上限
TH_SNR_DB = 15.0      # SNR 下限
TH_GAIN_DB = 6.0      # 增益差上限

# ★ 浏览器端解码脚本（与 analyze_dub_audio.py 同一套办法）
_DECODE_JS = r"""
async (b64) => {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const ctx = new Ctx();
  const ab = await ctx.decodeAudioData(buf.buffer);
  const n = ab.length;
  const chs = ab.numberOfChannels;
  const sr = ab.sampleRate;
  // 混成单声道 float32
  const out = new Float32Array(n);
  for (let c = 0; c < chs; c++) {
    const d = ab.getChannelData(c);
    for (let i = 0; i < n; i++) out[i] += d[i] / chs;
  }
  // 返回 base64 的 float32 原始数据（小端）
  const u8 = new Uint8Array(out.buffer);
  let s = '';
  const CH = 0x8000;
  for (let i = 0; i < u8.length; i += CH) {
    s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
  }
  return { sampleRate: sr, channels: chs, length: n, float32B64: btoa(s) };
}
"""


def _log(msg: str) -> None:
    print("[align] %s" % msg, flush=True)


def read_wav_pcm16(path: str) -> Tuple[np.ndarray, int, int]:
    """读 44 字节头的 WAV ⇒ (float32 样本, 采样率, 声道数)。"""
    with open(path, "rb") as f:
        data = f.read()
    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("不是 RIFF/WAVE：%s" % path)
    pos = 12
    fmt = None
    pcm = None
    while pos + 8 <= len(data):
        cid = data[pos:pos + 4]
        csize = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + csize]
        if cid == b"fmt ":
            fmt = struct.unpack("<HHIIHH", body[:16])
        elif cid == b"data":
            pcm = body
        pos += 8 + csize + (csize & 1)
    if fmt is None or pcm is None:
        raise ValueError("WAV 缺 fmt/data：%s" % path)
    channels, sr = fmt[1], fmt[2]
    arr = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    return arr, sr, channels


def read_raw_pcm16(path: str, sr: int, channels: int = 1) -> np.ndarray:
    """读裸 PCM16LE ⇒ float32 单声道。"""
    with open(path, "rb") as f:
        raw = f.read()
    arr = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        arr = arr.reshape(-1, channels).mean(axis=1)
    return arr


def decode_webm_mono(path: str) -> Tuple[np.ndarray, int, int]:
    """用浏览器 WebAudio 解码 webm/opus ⇒ (float32, 采样率, 声道数)。"""
    import base64
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    profile = os.path.join(ROOT, ".tmp", "_align_profile")
    with H.BrowserSession(profile, headless=True) as br:
        page = br.new_page()
        res = page.evaluate(_DECODE_JS, b64)
    arr = np.frombuffer(base64.b64decode(res["float32B64"]),
                        dtype="<f4").astype(np.float32)
    return arr, int(res["sampleRate"]), int(res["channels"])


def resample_linear(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """线性重采样（**只用于对齐分析**，不是产品路径）。"""
    if sr_in == sr_out or x.size == 0:
        return x
    n_out = int(round(x.size * sr_out / float(sr_in)))
    if n_out <= 0:
        return np.zeros(0, dtype=np.float32)
    idx = np.linspace(0, x.size - 1, n_out)
    return np.interp(idx, np.arange(x.size), x).astype(np.float32)


def best_xcorr(a: np.ndarray, b: np.ndarray, max_lag_sec: float,
               sr: int) -> Tuple[float, float]:
    """求 (峰值互相关, 对应时移秒)。

    ★ 用**归一化互相关**（除以各自能量）⇒ 与音量无关。
      只在 ±`max_lag_sec` 的范围内搜（避免长段错位时耗时爆炸）。
    """
    if a.size == 0 or b.size == 0:
        return 0.0, 0.0
    n = min(a.size, b.size)
    a = a[:n]
    b = b[:n]
    ea = float(np.dot(a, a))
    eb = float(np.dot(b, b))
    if ea <= 1e-12 or eb <= 1e-12:
        return 0.0, 0.0
    max_lag = int(max_lag_sec * sr)
    max_lag = max(1, min(max_lag, n - 1))
    best = -1.0
    best_lag = 0
    # 逐时移算相关（用 FFT 太重，这里用滑窗点积，段长不大）
    step = max(1, n // 4000)      # ★ 粗搜步长（保证耗时可控）
    lags = list(range(-max_lag, max_lag + 1, step))
    if 0 not in lags:
        lags.append(0)
    for lag in lags:
        if lag >= 0:
            x = a[lag:lag + (n - lag)]
            y = b[:n - lag]
        else:
            x = a[:n + lag]
            y = b[-lag:-lag + (n + lag)]
        if x.size < sr // 10:      # ★ 重叠太短 ⇒ 不可信
            continue
        c = float(np.dot(x, y)) / (ea ** 0.5 * eb ** 0.5)
        if c > best:
            best = c
            best_lag = lag
    return best, best_lag / float(sr)


def snr_db(ref: np.ndarray, test: np.ndarray) -> float:
    """SNR：把 `test` 当作 `ref` 的带噪版本 ⇒ 10·log10(P_ref / P_err)。"""
    n = min(ref.size, test.size)
    if n == 0:
        return -999.0
    r = ref[:n]
    t = test[:n]
    # ★ 先做一次最优标量增益对齐（把增益差异从残差里剥掉）
    denom = float(np.dot(t, t))
    g = (float(np.dot(r, t)) / denom) if denom > 1e-12 else 0.0
    err = r - g * t
    p_ref = float(np.dot(r, r))
    p_err = float(np.dot(err, err))
    if p_err <= 1e-15:
        return 99.0
    if p_ref <= 1e-15:
        return -999.0
    return round(10.0 * np.log10(p_ref / p_err), 3)


def rms_db(x: np.ndarray) -> float:
    if x.size == 0:
        return -999.0
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    return round(20.0 * np.log10(max(r, 1e-12)), 3)


def analyze_pair(a: np.ndarray, a_sr: int, b: np.ndarray, b_sr: int,
                 tag_a: str, tag_b: str) -> dict:
    """对齐两份音频 ⇒ 返回指标 + 问题清单。"""
    out: dict = {"a": tag_a, "b": tag_b,
                 "a_sample_rate": a_sr, "b_sample_rate": b_sr,
                 "a_duration_sec": round(a.size / float(a_sr), 4) if a_sr else 0,
                 "b_duration_sec": round(b.size / float(b_sr), 4) if b_sr else 0,
                 "a_rms_dbfs": rms_db(a), "b_rms_dbfs": rms_db(b),
                 "issues": []}
    if a.size == 0 or b.size == 0:
        out["issues"].append("empty_audio")
        out["aligned"] = False
        return out

    # ① 采样率一致？
    if a_sr != b_sr:
        out["issues"].append("sr_mismatch")

    # ② 时长比
    ratio = (a.size / float(a_sr)) / max(b.size / float(b_sr), 1e-9)
    out["duration_ratio"] = round(ratio, 4)
    if abs(ratio - 1.0) > TH_DUR:
        out["issues"].append("dur_mismatch")

    # ③ 增益差
    g_db = out["a_rms_dbfs"] - out["b_rms_dbfs"]
    out["gain_db"] = round(g_db, 3)
    if abs(g_db) > TH_GAIN_DB:
        out["issues"].append("gain_mismatch")

    # ④ 重采样到同一率 ⇒ 互相关 + SNR
    b2 = resample_linear(b, b_sr, a_sr)
    a2 = a
    n = min(a2.size, b2.size)
    if n < a_sr // 10:
        out["issues"].append("too_short_to_align")
        out["aligned"] = False
        return out
    xc, lag = best_xcorr(a2[:n], b2[:n], TH_LAG_SEC, a_sr)
    out["xcorr_peak"] = round(xc, 4)
    out["xcorr_lag_sec"] = round(lag, 4)
    if xc < TH_XCORR:
        out["issues"].append("content_mismatch")
    if abs(lag) > TH_LAG_SEC:
        out["issues"].append("time_shift")
    out["snr_db"] = snr_db(a2[:n], b2[:n])
    if out["snr_db"] < TH_SNR_DB:
        out["issues"].append("low_snr")
    out["aligned"] = True
    return out


def analyze(a_dump_dir: str, c_webm: str, out_path: Optional[str] = None,
            th: Optional[dict] = None) -> dict:
    """主分析：(a) vs (b) 逐段 + (b) 拼接 vs (c) 整段。"""
    global TH_SR, TH_DUR, TH_XCORR, TH_LAG_SEC, TH_SNR_DB, TH_GAIN_DB
    if th:
        TH_SR = th.get("sr", TH_SR)
        TH_DUR = th.get("dur", TH_DUR)
        TH_XCORR = th.get("xcorr", TH_XCORR)
        TH_LAG_SEC = th.get("lag", TH_LAG_SEC)
        TH_SNR_DB = th.get("snr", TH_SNR_DB)
        TH_GAIN_DB = th.get("gain", TH_GAIN_DB)

    res: dict = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "a_dump_dir": a_dump_dir, "c_webm": c_webm,
                 "thresholds": {"sr": TH_SR, "dur": TH_DUR, "xcorr": TH_XCORR,
                                "lag_sec": TH_LAG_SEC, "snr_db": TH_SNR_DB,
                                "gain_db": TH_GAIN_DB},
                 "segments": [], "summary": {}}

    wavs = sorted(glob.glob(os.path.join(a_dump_dir, "*_tts.wav")))
    pcms = sorted(glob.glob(os.path.join(a_dump_dir, "*_ws.pcm")))
    _log("(a) TTS wav：%d 个；(b) WS pcm：%d 个" % (len(wavs), len(pcms)))

    # ── 逐段 (a) vs (b) ────────────────────────────────────
    seg_issues: dict = {}
    for w in wavs:
        base = w[:-len("_tts.wav")]
        p = base + "_ws.pcm"
        if not os.path.isfile(p):
            res["segments"].append({"seg": os.path.basename(base),
                                    "aligned": False,
                                    "issues": ["ws_pcm_missing"]})
            seg_issues.setdefault("ws_pcm_missing", []).append(
                os.path.basename(base))
            continue
        meta = {}
        mp = base + "_ws.json"
        if os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
        try:
            a, a_sr, _ch = read_wav_pcm16(w)
            b = read_raw_pcm16(p, int(meta.get("sample_rate") or 24000),
                               int(meta.get("channels") or 1))
        except Exception as e:
            res["segments"].append({"seg": os.path.basename(base),
                                    "aligned": False,
                                    "issues": ["read_error: %s" % e]})
            continue
        r = analyze_pair(a, a_sr, b, b_sr, "tts_raw", "ws_sent")
        r["seg"] = os.path.basename(base)
        r["a_bytes"] = os.path.getsize(w)
        r["b_bytes"] = os.path.getsize(p)
        res["segments"].append(r)
        for iss in r.get("issues", []):
            seg_issues.setdefault(iss, []).append(r["seg"])

    # ── (b) 拼接 vs (c) 整段（player 录到的）───────────────
    b_all = None
    b_sr = 24000
    for p in pcms:
        base = p[:-len("_ws.pcm")]
        mp = base + "_ws.json"
        sr = 24000
        if os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    sr = int(json.load(f).get("sample_rate") or 24000)
            except Exception:
                pass
        b_sr = sr
        try:
            x = read_raw_pcm16(p, sr)
        except Exception:
            continue
        b_all = x if b_all is None else np.concatenate([b_all, x])
    if b_all is not None and os.path.isfile(c_webm):
        try:
            c, c_sr, c_ch = decode_webm_mono(c_webm)
            res["b_to_c"] = analyze_pair(b_all, b_sr, c, c_sr,
                                         "ws_sent_concat", "player_recorded")
            res["b_to_c"]["c_bytes"] = os.path.getsize(c_webm)
            res["b_to_c"]["c_sample_rate"] = c_sr
            res["b_to_c"]["c_channels"] = c_ch
        except Exception as e:
            res["b_to_c"] = {"error": "%s: %s" % (type(e).__name__, e)}
    else:
        res["b_to_c"] = {"error": "没有 (b) 或 (c) 无法对比"}

    # ── 汇总 ────────────────────────────────────────────────
    aligned = [s for s in res["segments"] if s.get("aligned")]
    res["summary"] = {
        "n_segments": len(res["segments"]),
        "n_aligned": len(aligned),
        "n_unaligned": len(res["segments"]) - len(aligned),
        "issue_histogram": {k: len(v) for k, v in sorted(seg_issues.items())},
        "issue_segments": {k: v for k, v in sorted(seg_issues.items())},
        "mean_xcorr": (round(float(np.mean([s["xcorr_peak"] for s in aligned])), 4)
                       if aligned else None),
        "mean_snr_db": (round(float(np.mean([s["snr_db"] for s in aligned])), 3)
                        if aligned else None),
        "mean_gain_db": (round(float(np.mean([s["gain_db"] for s in aligned])), 3)
                         if aligned else None),
        "duration_ratio_mean": (
            round(float(np.mean([s["duration_ratio"] for s in aligned])), 4)
            if aligned else None),
    }
    # ★ 判定：失真从哪一环开始
    a2b = res["summary"]["issue_histogram"]
    b2c = ((res.get("b_to_c") or {}).get("issues") or [])
    if not a2b and not b2c:
        verdict = "no_distortion_found"
    elif not a2b:
        verdict = "distortion_in_browser_stage"       # 服务端 OK ⇒ 浏览器这一环坏
    else:
        verdict = "distortion_in_server_stage"         # 服务端这一环就坏了
    res["verdict"] = verdict
    res["verdict_note"] = (
        "(a)→(b) 的问题 = 服务端变速/下发环节；"
        "(b)→(c) 的问题 = 浏览器解码/重采样/混音/录音环节。")

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        _log("对齐结果已落盘：%s" % out_path)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description="EXT-028 三份音频逐段对齐")
    ap.add_argument("--a-dump", required=True, help="audio_dump 目录")
    ap.add_argument("--c-webm", required=True, help="player 录音 webm")
    ap.add_argument("--out", default=None, help="输出 json")
    args = ap.parse_args()
    res = analyze(args.a_dump, args.c_webm, args.out)
    print("\n" + "=" * 68)
    print("对齐判定：%s" % res["verdict"])
    print("段数 %d / 对齐 %d / 未对齐 %d"
          % (res["summary"]["n_segments"], res["summary"]["n_aligned"],
             res["summary"]["n_unaligned"]))
    print("平均互相关 %s / 平均 SNR %s dB / 平均增益差 %s dB"
          % (res["summary"]["mean_xcorr"], res["summary"]["mean_snr_db"],
             res["summary"]["mean_gain_db"]))
    print("问题分布：%s" % res["summary"]["issue_histogram"])
    bc = res.get("b_to_c") or {}
    if bc.get("issues"):
        print("(b)→(c) 问题：%s" % bc["issues"])
    print("=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main())
