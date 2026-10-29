"""throughput_bench.py — ★ EXT-008 第 3 点：**分阶段测吞吐**（先测数据，再谈架构）

## 为什么需要这个工具

EXT-008 第 3 点：reviewer 指出「**并行化即根治**」尚无证据 ——
冒烟的单阶段 RTF 是 ASR 1.02（GPU）、MT 0.28、TTS 1.60（NPU），
即使三阶段完美流水，吞吐上限由**最慢阶段**决定，
而 TTS 1.60 > 1、ASR 1.02 也无余量 ⇒ 必须先测三组数再提方向：

  (a) 冒烟的 TTS/ASR 是否含**首次编译/预热**？⇒ 冷、热**各 3 次**分别报；
  (b) 三阶段**单独**连续跑 5 分钟素材的**稳态 RTF**；
  (c) ASR 与 TTS **同时**跑时的**互相干扰**（不同设备是否真并行）。

## 三个子命令

    # (a) 冷/热各 3 次
    python tools\\throughput_bench.py cold-hot --wav <wav> --target-lang ja --out <json>

    # (b) 三阶段单独跑 5 分钟素材的稳态 RTF
    python tools\\throughput_bench.py steady --wav <wav> --target-lang ja --out <json>

    # (c) ASR 与 TTS 同时跑（互相干扰）
    python tools\\throughput_bench.py interference --wav <wav> --target-lang ja --out <json>

⚠️ **必须用 App 自带解释器**跑（openvino / babelvox 只在那里）：
    C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.6\\python\\python.exe

⚠️ **必须持共享机器锁**（铁律）：本工具默认走 `machine_lock.hold()`，
   锁被别的模块持有时**排队等待**，绝不抢占。

## RTF 口径（**统一、且写明分母**）

| 阶段 | RTF 分母 | 说明 |
|---|---|---|
| ASR | **输入音频秒** | 识别 1 s 音频花几秒 |
| MT  | **输入源文秒**（按 ASR 产出估） | 译 1 s 源文花几秒 |
| TTS | **输出语音秒** | 生成 1 s 配音花几秒 |

⚠️ 三阶段的分母**不同** ⇒ 不可直接相加；端到端 RTF 必须用
   「各阶段总耗时 ÷ 总音频秒」来算（本工具 `end_to_end` 字段）。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import threading
import time
import wave
from typing import List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

APP_ROOT = os.environ.get("EXT_APP_ROOT",
                          r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6")
APP_PYTHON = os.path.join(APP_ROOT, "python", "python.exe")


# ── 输入 ────────────────────────────────────────────────────────────
def read_wav_16k_mono(path: str):
    """读 16 kHz 单声道 PCM16 wav → (float32, sample_rate)。"""
    import numpy as np
    with wave.open(path, "rb") as w:
        nch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("只支持 PCM16（sampwidth=%d）" % sw)
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if nch > 1:
        a = a.reshape(-1, nch).mean(axis=1)
    return a, sr


def _dump(path: Optional[str], data) -> None:
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("[bench] 结果已落盘：%s" % path)
    except Exception as e:
        print("[bench] 落盘失败：%s" % e)


def _stats(vals: List[float]) -> dict:
    if not vals:
        return {}
    s = sorted(vals)
    return {
        "n": len(vals),
        "min": round(s[0], 4),
        "p50": round(statistics.median(s), 4),
        "max": round(s[-1], 4),
        "mean": round(sum(vals) / len(vals), 4),
        "stdev": round(statistics.pstdev(s), 4) if len(vals) > 1 else 0.0,
        "all": [round(v, 4) for v in vals],
    }


# ── (a) 冷 / 热各 3 次 ──────────────────────────────────────────────
def cmd_cold_hot(args) -> int:
    """(a) 同一段音频，ASR/TTS **冷、热各 3 次**。

    * 「冷」= 该阶段的**第一次**调用（**含**模型加载 + 图编译 + 预热）；
    * 「热」= 之后的调用（模型已在内存、图已编译）。

    ⚠️ 关键：为了让 ASR 的「冷」真的是冷，TTS 的「冷」真的是冷，
      本子命令**分两段**跑：
        第 1 段：只跑 ASR 3 次（冷 + 热 + 热）
        第 2 段：**新起一个引擎实例**（重置 ASR 已热的状态），
                只跑 TTS 3 次（冷 + 热 + 热）
      ⇒ 两段的「冷」互不污染。
    """
    import numpy as np
    from ext.engines import try_load_runtime_engine

    out: dict = {
        "mode": "cold_hot",
        "wav": os.path.abspath(args.wav),
        "target_lang": args.target_lang,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rtf_definition": {
            "asr": "RTF = ASR 耗时 / 输入音频秒",
            "mt": "RTF = MT 耗时 / 源文估算秒",
            "tts": "RTF = TTS 耗时 / 输出语音秒",
            "note": "三阶段分母不同，不可直接相加；端到端见 steady.end_to_end",
        },
    }

    audio, sr = read_wav_16k_mono(args.wav)
    n = int(min(audio.shape[0], args.max_sec * 16000))
    audio = audio[:n]
    audio_sec = n / 16000.0
    out["audio_sec"] = round(audio_sec, 3)
    print("[bench] 音频 %.2f s" % audio_sec, flush=True)

    # ── 第 1 段：ASR 冷/热各 3 次 ────────────────────────────
    eng, err = try_load_runtime_engine(target_lang=args.target_lang)
    if eng is None:
        out["error"] = "引擎接线失败: %s" % err
        _dump(args.out, out)
        return 1
    asr_runs = []
    for i in range(args.reps):
        t0 = time.perf_counter()
        text = eng.asr(audio, 0.0, audio_sec) or ""
        dt = time.perf_counter() - t0
        asr_runs.append({
            "run": i + 1, "kind": ("cold" if i == 0 else "hot"),
            "sec": round(dt, 3), "rtf": round(dt / audio_sec, 4),
            "text_len": len(text), "text_head": text[:80]})
        print("[bench] ASR %s #%d: %.3f s  RTF=%.4f"
              % ("冷" if i == 0 else "热", i + 1, dt, dt / audio_sec), flush=True)
    out["asr"] = {
        "runs": asr_runs,
        "cold_rtf": asr_runs[0]["rtf"] if asr_runs else None,
        "hot_rtfs": [r["rtf"] for r in asr_runs[1:]],
        "hot_rtf_stats": _stats([r["rtf"] for r in asr_runs[1:]]),
        "cold_minus_hot_rtf": (
            round(asr_runs[0]["rtf"] - statistics.median(
                [r["rtf"] for r in asr_runs[1:]]), 4)
            if len(asr_runs) > 1 else None),
        "engine_load_s": eng.stats().get("load_s"),
    }

    # ── 第 2 段：**新实例**，TTS 冷/热各 3 次 ──────────────────
    #   ⇒ ASR 已经把 GPU 跑热了，但 TTS 是 NPU ⇒ 与 ASR 不同设备，
    #     「冷」的定义仍然成立（TTS 模型本进程第一次加载 + NPU 首次编译）。
    eng2, err2 = try_load_runtime_engine(target_lang=args.target_lang)
    if eng2 is None:
        out["tts_error"] = "第二段引擎接线失败: %s" % err2
        _dump(args.out, out)
        return 1
    # 先跑一次 ASR 拿到**源文**（TTS 需要文本）
    src_text = eng2.asr(audio, 0.0, audio_sec) or ""
    if not src_text:
        out["error"] = "ASR 没产出文本 ⇒ 无法测 TTS"
        _dump(args.out, out)
        return 1
    tgt_text = ""
    try:
        tgt_text = eng2.mt(src_text) or src_text
    except Exception as e:
        out["mt_error"] = str(e)
        tgt_text = src_text
    tts_runs = []
    for i in range(args.reps):
        t0 = time.perf_counter()
        pcm, speech = eng2.tts(tgt_text, voice="A")
        dt = time.perf_counter() - t0
        tts_runs.append({
            "run": i + 1, "kind": ("cold" if i == 0 else "hot"),
            "sec": round(dt, 3),
            "speech_sec": round(speech, 3),
            "rtf": round(dt / speech, 4) if speech else None,
            "pcm_bytes": len(pcm) if pcm else 0})
        print("[bench] TTS %s #%d: %.3f s  语音 %.3f s  RTF=%.4f"
              % ("冷" if i == 0 else "热", i + 1, dt, speech,
                 (dt / speech) if speech else -1), flush=True)
    out["tts"] = {
        "runs": tts_runs,
        "cold_rtf": tts_runs[0]["rtf"] if tts_runs else None,
        "hot_rtfs": [r["rtf"] for r in tts_runs[1:]],
        "hot_rtf_stats": _stats([r["rtf"] for r in tts_runs[1:]]),
        "cold_minus_hot_rtf": (
            round(tts_runs[0]["rtf"] - statistics.median(
                [r["rtf"] for r in tts_runs[1:]]), 4)
            if len(tts_runs) > 1 else None),
        "src_text_len": len(src_text),
        "tgt_text_len": len(tgt_text),
    }
    out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out["ok"] = True
    _dump(args.out, out)
    print(json.dumps({k: v for k, v in out.items()
                      if k in ("asr", "tts")}, ensure_ascii=False, indent=2))
    return 0


# ── (b) 三阶段单独跑 5 分钟素材的稳态 RTF ───────────────────────────
def cmd_steady(args) -> int:
    """(b) 三阶段**各自单独**、**连续**跑 5 分钟素材 ⇒ 稳态 RTF。

    * ASR：把 5 分钟音频按 EXT-001 的断句区间（12~20 s）切成 N 段，
      **逐段**跑（模拟真实定稿段粒度）⇒ 稳态 RTF；
    * MT：对每段的 ASR 文本逐条翻译 ⇒ 稳态 RTF；
    * TTS：对每段的译文逐条合成 ⇒ 稳态 RTF；
    * 端到端 = (ASR总 + MT总 + TTS总) / 音频总秒。

    ⚠️ **每个阶段单独计时**，但用**同一批**真实产出串起来
      （ASR 的真文本 → MT → TTS）⇒ 不是拿假数据凑。
    """
    import numpy as np
    from ext.engines import try_load_runtime_engine
    from ext.segmenter import plan_segments

    out: dict = {
        "mode": "steady",
        "wav": os.path.abspath(args.wav),
        "target_lang": args.target_lang,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rtf_definition": {
            "asr": "RTF = ΣASR耗时 / 音频总秒",
            "mt": "RTF = ΣMT耗时 / 音频总秒（同一分母，便于与 ASR 同尺度比）",
            "tts": "RTF = ΣTTS耗时 / **输出语音总秒**（TTS 的自然分母）",
            "end_to_end": "端到端 RTF = (ΣASR + ΣMT + ΣTTS) / 音频总秒",
        },
    }

    audio, sr = read_wav_16k_mono(args.wav)
    n = int(min(audio.shape[0], args.max_sec * 16000))
    audio = audio[:n]
    audio_sec = n / 16000.0
    out["audio_sec"] = round(audio_sec, 3)

    # 按断句切段（与服务端同一套）
    segs = plan_segments(audio)
    # 尾部不足 1 s 的丢弃（与服务端 flush 同规则）
    if segs:
        tail = (segs[-1][1] - segs[-1][0]) / float(sr)
        if tail < 1.0:
            segs = segs[:-1]
    out["n_segments"] = len(segs)
    print("[bench] 音频 %.2f s → %d 段" % (audio_sec, len(segs)), flush=True)

    eng, err = try_load_runtime_engine(target_lang=args.target_lang)
    if eng is None:
        out["error"] = "引擎接线失败: %s" % err
        _dump(args.out, out)
        return 1

    per_seg = []
    tot_asr = tot_mt = tot_tts = 0.0
    tot_speech = 0.0
    for (s0, s1) in segs:
        seg = audio[s0:s1]
        seg_sec = (s1 - s0) / float(sr)
        t0 = time.perf_counter()
        text = eng.asr(seg, s0 / sr, s1 / sr) or ""
        asr_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        tgt = eng.mt(text) if text else ""
        mt_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        pcm, speech = eng.tts(tgt or text, voice="A")
        tts_s = time.perf_counter() - t0
        tot_asr += asr_s
        tot_mt += mt_s
        tot_tts += tts_s
        tot_speech += (speech or 0.0)
        per_seg.append({
            "t_start": round(s0 / sr, 3), "t_end": round(s1 / sr, 3),
            "seg_sec": round(seg_sec, 3),
            "asr_sec": round(asr_s, 4),
            "asr_rtf": round(asr_s / seg_sec, 4),
            "mt_sec": round(mt_s, 4),
            "tts_sec": round(tts_s, 4),
            "tts_rtf": round(tts_s / speech, 4) if speech else None,
            "speech_sec": round(speech or 0.0, 3),
            "src_len": len(text), "tgt_len": len(tgt or ""),
        })
        print("[bench] seg %6.1f–%6.1f  asr %5.2f (%.3f×)  mt %5.2f  tts %6.2f (%.3f×)"
              % (s0 / sr, s1 / sr, asr_s, asr_s / seg_sec, mt_s, tts_s,
                 (tts_s / speech) if speech else -1), flush=True)

    # ★ 前 N 段是「冷启动」（首段含图编译）⇒ 稳态要看**去掉首段**的数
    warm = per_seg[1:] if len(per_seg) > 1 else per_seg
    warm_asr = sum(p["asr_sec"] for p in warm)
    warm_sec = sum(p["seg_sec"] for p in warm)
    warm_tts = sum(p["tts_sec"] for p in warm)
    warm_speech = sum(p["speech_sec"] for p in warm)
    warm_mt = sum(p["mt_sec"] for p in warm)

    out["all_segments"] = {
        "asr_total_sec": round(tot_asr, 3),
        "mt_total_sec": round(tot_mt, 3),
        "tts_total_sec": round(tot_tts, 3),
        "speech_total_sec": round(tot_speech, 3),
        "asr_rtf": round(tot_asr / audio_sec, 4),
        "mt_rtf": round(tot_mt / audio_sec, 4),
        "tts_rtf": round(tot_tts / tot_speech, 4) if tot_speech else None,
        "end_to_end_rtf": round((tot_asr + tot_mt + tot_tts) / audio_sec, 4),
    }
    out["steady_state_excl_first_segment"] = {
        "note": "去掉首段（首段含图编译/预热）⇒ 稳态",
        "n_segments": len(warm),
        "audio_sec": round(warm_sec, 3),
        "asr_rtf": round(warm_asr / warm_sec, 4) if warm_sec else None,
        "mt_rtf": round(warm_mt / warm_sec, 4) if warm_sec else None,
        "tts_rtf": round(warm_tts / warm_speech, 4) if warm_speech else None,
        "end_to_end_rtf": round(
            (warm_asr + warm_mt + warm_tts) / warm_sec, 4) if warm_sec else None,
    }
    out["per_segment"] = per_seg
    out["engine_stats"] = eng.stats()
    out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out["ok"] = True
    _dump(args.out, out)
    print(json.dumps({"all_segments": out["all_segments"],
                      "steady_state_excl_first_segment":
                          out["steady_state_excl_first_segment"]},
                     ensure_ascii=False, indent=2))
    return 0


# ── (c) ASR 与 TTS 同时跑 ⇒ 互相干扰 ────────────────────────────────
def cmd_interference(args) -> int:
    """(c) ASR 与 TTS **同时**跑 ⇒ 测互相干扰（不同设备是否真并行）。

    做法：
      * 先**串行**跑一轮同样的工作量（基线）；
      * 再**并发**跑一轮（ASR 在一个线程、TTS 在另一个线程）；
      * 对比 RTF：并发时明显变慢 ⇒ 两个阶段**抢同一资源**（不是真并行）。

    ⚠️ ASR 在 GPU.0、TTS 在 NPU ⇒ 理论上应该能并行；
      若并发时两者都变慢 ⇒ 说明瓶颈在**主机侧**（如 Python GIL / 内存带宽 /
      线程调度），不是设备。
    """
    import numpy as np
    from ext.engines import try_load_runtime_engine

    out: dict = {
        "mode": "interference",
        "wav": os.path.abspath(args.wav),
        "target_lang": args.target_lang,
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": ("串行基线 vs 并发；ASR@GPU.0 与 TTS@NPU 若并发时"
                 "两者都变慢 ⇒ 瓶颈在主机侧而非设备。"),
    }

    audio, sr = read_wav_16k_mono(args.wav)
    n = int(min(audio.shape[0], args.max_sec * 16000))
    audio = audio[:n]
    audio_sec = n / 16000.0
    out["audio_sec"] = round(audio_sec, 3)

    eng, err = try_load_runtime_engine(target_lang=args.target_lang)
    if eng is None:
        out["error"] = "引擎接线失败: %s" % err
        _dump(args.out, out)
        return 1

    # 先拿一批真实文本（TTS 需要）
    text = eng.asr(audio, 0.0, audio_sec) or ""
    if not text:
        out["error"] = "ASR 没产出文本"
        _dump(args.out, out)
        return 1
    try:
        tgt = eng.mt(text) or text
    except Exception:
        tgt = text

    # ── 串行基线 ────────────────────────────────────────────
    t0 = time.perf_counter()
    eng.asr(audio, 0.0, audio_sec)
    serial_asr = time.perf_counter() - t0
    t0 = time.perf_counter()
    pcm, speech = eng.tts(tgt, voice="A")
    serial_tts = time.perf_counter() - t0
    print("[bench] 串行：ASR %.2f s  TTS %.2f s" % (serial_asr, serial_tts),
          flush=True)

    # ── 并发 ────────────────────────────────────────────────
    res = {}

    def _worker_asr():
        t = time.perf_counter()
        eng.asr(audio, 0.0, audio_sec)
        res["asr"] = time.perf_counter() - t

    def _worker_tts():
        t = time.perf_counter()
        eng.tts(tgt, voice="A")
        res["tts"] = time.perf_counter() - t

    t_start = time.perf_counter()
    th_a = threading.Thread(target=_worker_asr)
    th_t = threading.Thread(target=_worker_tts)
    th_a.start()
    th_t.start()
    th_a.join()
    th_t.join()
    wall = time.perf_counter() - t_start
    print("[bench] 并发：ASR %.2f s  TTS %.2f s  墙钟 %.2f s"
          % (res.get("asr", 0), res.get("tts", 0), wall), flush=True)

    out["serial"] = {
        "asr_sec": round(serial_asr, 3),
        "asr_rtf": round(serial_asr / audio_sec, 4),
        "tts_sec": round(serial_tts, 3),
        "tts_rtf": round(serial_tts / speech, 4) if speech else None,
        "sum_sec": round(serial_asr + serial_tts, 3),
    }
    out["concurrent"] = {
        "asr_sec": round(res.get("asr", 0.0), 3),
        "asr_rtf": round(res.get("asr", 0.0) / audio_sec, 4),
        "tts_sec": round(res.get("tts", 0.0), 3),
        "tts_rtf": (round(res.get("tts", 0.0) / speech, 4)
                    if speech else None),
        "wall_sec": round(wall, 3),
    }
    out["interference"] = {
        "asr_slowdown_x": (round(res.get("asr", 0.0) / serial_asr, 4)
                           if serial_asr > 0 else None),
        "tts_slowdown_x": (round(res.get("tts", 0.0) / serial_tts, 4)
                           if serial_tts > 0 else None),
        "parallel_speedup_x": (round((serial_asr + serial_tts) / wall, 4)
                               if wall > 1e-9 else None),
        "interpretation": (
            "parallel_speedup_x ≈ 1 ⇒ 两阶段**没有**真正并行（合起来没省时间）"
            "⇒ 「并行化即根治」不成立；"
            "≈ 2 ⇒ 真并行，吞吐可翻倍。"),
    }
    out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out["ok"] = True
    _dump(args.out, out)
    print(json.dumps({"serial": out["serial"], "concurrent": out["concurrent"],
                      "interference": out["interference"]},
                     ensure_ascii=False, indent=2))
    return 0


# ── 主入口 ──────────────────────────────────────────────────────────
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT-008 分阶段吞吐基准")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _common(p):
        p.add_argument("--wav", required=True)
        p.add_argument("--target-lang", default="ja")
        p.add_argument("--out", default=None)
        p.add_argument("--max-sec", type=float, default=20.0)
        p.add_argument("--reps", type=int, default=3)
        p.add_argument("--no-lock", action="store_true")
        p.add_argument("--lock-wait", type=float, default=7200.0)
        return p

    _common(sub.add_parser("cold-hot", help="(a) 冷/热各 3 次"))
    _common(sub.add_parser("steady", help="(b) 三阶段单独跑 5 分钟素材"))
    _common(sub.add_parser("interference", help="(c) ASR 与 TTS 同时跑"))

    args = ap.parse_args(argv)
    handler = {"cold-hot": cmd_cold_hot, "steady": cmd_steady,
               "interference": cmd_interference}[args.cmd]

    if args.no_lock:
        return handler(args)
    # ★ 铁律：计时/测速作业必须持共享机器锁
    from machine_lock import hold
    with hold("EXT-throughput-%s" % args.cmd, wait_timeout=args.lock_wait):
        print("[bench] 已取得共享锁", flush=True)
        return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
