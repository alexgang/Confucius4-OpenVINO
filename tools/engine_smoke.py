"""engine_smoke.py — **真实引擎冒烟测试**（EXT-006 P1 的第一步）

目的：在跑完整 5 分钟验收前，先用**一小段**音频确认
ASR(R2T2 INT8@GPU.0) → MT(Hy-MT2 INT8@GPU.0) → TTS(Qwen3-TTS@NPU)
这条链路**真的能跑通**，并把每一段的原始输出与耗时落盘。

⚠️ **必须用 App 自带的 Python 解释器**跑（依赖 openvino / openvino_genai /
babelvox / transformers 只在那里）：
    C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v<版本>\\python\\python.exe

用法：
    <app-python> tools\\engine_smoke.py --wav <16k单声道wav> --target-lang en \\
        --out .tmp\\p1\\smoke.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ★★ EXT-011：线程限制必须在任何 numpy / openvino import 之前
#   （本工具**直接**跑引擎，不经过 ext.bridge ⇒ 这里要自己设一次）
from ext.thread_limits import apply_thread_limits as _apply_thread_limits

THREAD_LIMIT_RECORD = _apply_thread_limits(log=print)


def read_wav_16k_mono(path: str):
    """读 16 kHz 单声道 PCM16 wav → (float32 numpy, sample_rate)。"""
    import numpy as np
    with wave.open(path, "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("只支持 PCM16（sampwidth=%d）" % sw)
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if nch > 1:
        a = a.reshape(-1, nch).mean(axis=1)
    return a, sr


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EXT 真实引擎冒烟测试")
    ap.add_argument("--wav", required=True, help="16 kHz 单声道 PCM16 wav")
    ap.add_argument("--target-lang", default="en")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-sec", type=float, default=20.0,
                    help="只用音频前 N 秒（控制测试时长）")
    ap.add_argument("--skip-asr", action="store_true")
    ap.add_argument("--skip-mt", action="store_true")
    ap.add_argument("--skip-tts", action="store_true")
    ap.add_argument("--dump-wav", default=None,
                    help="把 TTS 产出的 24 kHz PCM 存成 wav")
    args = ap.parse_args(argv)

    import numpy as np
    from ext.engines import try_load_runtime_engine

    out: dict = {"ok": False, "wav": args.wav,
                 "target_lang": args.target_lang,
                 "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "stages": {}}

    eng, err = try_load_runtime_engine(target_lang=args.target_lang)
    if eng is None:
        out["error"] = "引擎接线失败: %s" % err
        _dump(args.out, out)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1
    out["available"] = eng.available()
    print("[smoke] available =", json.dumps(out["available"], ensure_ascii=False))

    audio, sr = read_wav_16k_mono(args.wav)
    if sr != 16000:
        raise ValueError("期望 16 kHz，实际 %d" % sr)
    n = int(min(audio.shape[0], args.max_sec * 16000))
    audio = audio[:n]
    out["audio_sec"] = round(n / 16000.0, 3)
    print("[smoke] 音频 %.2f s（%d 样本 @16k）" % (n / 16000.0, n))

    # ── ASR ────────────────────────────────────────────────────
    text = ""
    if not args.skip_asr:
        t0 = time.perf_counter()
        try:
            text = eng.asr(audio, 0.0, n / 16000.0) or ""
        except Exception as e:
            out["stages"]["asr"] = {"error": "%s: %s" % (type(e).__name__, e)}
        dt = time.perf_counter() - t0
        out["stages"]["asr"] = out["stages"].get("asr", {})
        out["stages"]["asr"].update({
            "text": text, "sec": round(dt, 3),
            "rtf": round(dt / max(1e-6, n / 16000.0), 4)})
        print("[smoke] ASR %.3f s  RTF=%.3f  => %r" % (dt, dt / (n / 16000.0), text))

    # ── MT ─────────────────────────────────────────────────────
    tgt = ""
    if not args.skip_mt and text:
        t0 = time.perf_counter()
        try:
            tgt = eng.mt(text) or ""
        except Exception as e:
            out["stages"]["mt"] = {"error": "%s: %s" % (type(e).__name__, e)}
        dt = time.perf_counter() - t0
        out["stages"]["mt"] = out["stages"].get("mt", {})
        out["stages"]["mt"].update({
            "src": text, "text": tgt, "sec": round(dt, 3)})
        print("[smoke] MT  %.3f s => %r" % (dt, tgt))

    # ── TTS ────────────────────────────────────────────────────
    tts_text = tgt or text
    if not args.skip_tts and tts_text:
        t0 = time.perf_counter()
        pcm, speech = (None, 0.0)
        try:
            pcm, speech = eng.tts(tts_text, voice="A")
        except Exception as e:
            out["stages"]["tts"] = {"error": "%s: %s" % (type(e).__name__, e)}
        dt = time.perf_counter() - t0
        st = out["stages"].setdefault("tts", {})
        st.update({
            "text": tts_text, "sec": round(dt, 3),
            "speech_sec": round(speech, 3),
            "rtf": round(dt / max(1e-6, speech), 4) if speech else None,
            "pcm_bytes": len(pcm) if pcm else 0,
            "ok": pcm is not None})
        print("[smoke] TTS %.3f s  音频 %.3f s  RTF=%.3f  bytes=%d"
              % (dt, speech, (dt / speech) if speech else -1,
                 len(pcm) if pcm else 0))
        if pcm and args.dump_wav:
            _write_wav(args.dump_wav, pcm, 24000)
            out["stages"]["tts"]["wav"] = args.dump_wav
            print("[smoke] TTS wav 已落盘：%s" % args.dump_wav)

    out["engine_stats"] = eng.stats()
    # ★★ EXT-011：线程限制的**实际生效记录**（reviewer 可直接核对）
    out["thread_limits"] = dict(THREAD_LIMIT_RECORD)
    out["ok"] = True
    out["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _dump(args.out, out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _write_wav(path: str, pcm: bytes, sr: int) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def _dump(path, data) -> None:
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("[smoke] 结果已落盘：%s" % path)
    except Exception as e:
        print("[smoke] 落盘失败：%s" % e)


if __name__ == "__main__":
    raise SystemExit(main())
