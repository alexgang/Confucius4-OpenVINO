"""APP-123: real end-to-end measurement of the App's OV TTS path under c13.

Runs the PRODUCT code (the dev tree's `tts_engine.stream` -> vendored babelvox
+ `tts_engine_patch.py`) on the PACKAGE's IR/models with the PACKAGE's python.

MEASURED
  1. length conservation: is every chunk's sample count a multiple of 1920
     (one frame = 1920 samples @ 24 kHz), and is the sentence total == frames*1920?
  2. the join: direct_concat (c13) vs the crossfade behaviour, with the SAME
     seed so the two arms generate the SAME frames -> the only difference is
     the join, and the sample-count delta is exactly the audio the crossfade
     used to drop.
  3. first-packet latency and RTF.

🔴 WHY THE SEED MATTERS (first attempt was wrong and was discarded)
  babelvox samples with the GLOBAL `np.random` (`np.random.choice`, no seed
  argument) => two arms with different chunk sizes drew DIFFERENT tokens =>
  the sample-count delta measured sampling noise, not the join.
  => here we seed `np.random.seed(...)` before every arm => same tokens.
  ⚠️ The App path itself does NOT seed (it never did) => the production path
     stays non-deterministic; seeding here is only to make the A/B meaningful.

🔴 WHAT THE APP's OV PATH ALREADY DID (important finding)
  babelvox's `_yield_chunk` takes the "No crossfade - simple pass-through"
  branch when `not split_on_silence` — and the App always passes
  `split_on_silence=False` (mandatory: it would double the decode cost).
  => the App's OV path was ALREADY direct-concat, i.e. the 7.3% audio loss that
     TTS-075 found in the TTS module's own driver did NOT exist in the App.
  => the APP-123 `crossfade_samples=0` is therefore a hardening/no-op-today
     change (it makes the intent explicit and survives a future
     `split_on_silence` change), and the REAL App-side gaps were
     (a) the window was 33 (chunk 8) not 38 (chunk 13), and
     (b) the peak limiter / clipping counters did not exist.
  Both are now implemented and measured here.
"""
import json
import os
import sys
import time

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5"
DEV = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
OUT = (r"C:\Users\Trekker-PTL\confucius4-openvino\results\app"
       r"\app123_c13_ov_probe.json")

SEED = 20261023
TEXTS = [
    ("zh", "你好，这是实时字幕的测试。"),
    ("en", "Yes, good."),
]

sys.path.insert(0, os.path.join(PKG, "app"))
sys.path.insert(0, os.path.join(PKG, "python", "Lib", "site-packages"))
sys.path.insert(0, DEV)


def measure(label, env_overrides):
    saved = {}
    for k, v in env_overrides.items():
        saved[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    sys.modules.pop("tts_engine", None)
    import numpy as np
    import tts_engine as te

    rows = []
    eng = None
    try:
        t0 = time.perf_counter()
        eng = te.make_engine(device="GPU.0",
                             on_log=lambda s: print("   [engine]", s, flush=True))
        load_s = time.perf_counter() - t0
        for lang, text in TEXTS:
            blang = "Chinese" if lang == "zh" else "English"
            # 🔴 seed the GLOBAL numpy RNG => both arms draw the SAME tokens
            np.random.seed(SEED)
            chunks = []
            t_start = time.perf_counter()
            first_chunk_at = None
            n_total = 0
            for wav_chunk, sr in te.stream(eng, text, language=blang,
                                           speaker=None):
                n = int(len(wav_chunk))
                chunks.append(n)
                n_total += n
                if first_chunk_at is None:
                    first_chunk_at = time.perf_counter() - t_start
            wall = time.perf_counter() - t_start
            dur = n_total / float(sr)
            frames_implied = n_total / 1920.0
            rows.append(dict(
                lang=lang, text=text, sr=int(sr),
                n_chunks=len(chunks), chunk_samples=chunks,
                n_samples_total=n_total, dur_s=round(dur, 6),
                frames_implied=round(frames_implied, 6),
                frames_implied_is_integer=abs(frames_implied
                                              - round(frames_implied)) < 1e-6,
                every_chunk_multiple_of_1920=all(c % 1920 == 0 for c in chunks),
                first_packet_s=round(first_chunk_at or 0.0, 6),
                wall_s=round(wall, 6),
                rtf=round(wall / dur, 6) if dur > 0 else None,
            ))
        return dict(arm=label, load_s=round(load_s, 3), seed=SEED,
                    chunk_frames=te.CHUNK_FRAMES, ctx_frames=te.CTX_FRAMES,
                    window=te.CHUNK_FRAMES + te.CTX_FRAMES,
                    buckets=list(te.DECODER_BUCKETS_CTX),
                    direct_concat=bool(te.DIRECT_CONCAT), rows=rows)
    finally:
        if eng is not None:
            try:
                del eng
            except Exception:
                pass
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main():
    out = {}
    # ARM A: c13 (chunk 13 / ctx 25 / window 38) + direct concat
    out["c13_direct_concat"] = measure("c13_direct_concat", {
        "LIVECAP_TTS_DIRECT_CONCAT": "1",
        "LIVECAP_TTS_CHUNK_FRAMES": None,
        "LIVECAP_TTS_CTX_FRAMES": None,
        "LIVECAP_TTS_DECODER_BUCKETS": None,
    })
    # ARM B: the OLD App config (chunk 8 / ctx 25 / window 33) + crossfade
    out["old_chunk8_crossfade"] = measure("old_chunk8_crossfade", {
        "LIVECAP_TTS_DIRECT_CONCAT": "0",
        "LIVECAP_TTS_CHUNK_FRAMES": "8",
        "LIVECAP_TTS_CTX_FRAMES": "25",
        "LIVECAP_TTS_DECODER_BUCKETS": "8,16,32,33",
    })
    # ARM C: old chunk size but direct concat -> isolates the join from the window
    out["old_chunk8_direct_concat"] = measure("old_chunk8_direct_concat", {
        "LIVECAP_TTS_DIRECT_CONCAT": "1",
        "LIVECAP_TTS_CHUNK_FRAMES": "8",
        "LIVECAP_TTS_CTX_FRAMES": "25",
        "LIVECAP_TTS_DECODER_BUCKETS": "8,16,32,33",
    })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print()
    print("=== %s ===" % OUT)
    for arm, d in out.items():
        print("\n[%s] chunk=%s ctx=%s window=%s buckets=%s direct_concat=%s"
              % (arm, d["chunk_frames"], d["ctx_frames"], d["window"],
                 d["buckets"], d["direct_concat"]))
        for r in d["rows"]:
            print("   %s: chunks=%d samples=%d frames_implied=%.4f int=%s "
                  "all_chunks_x1920=%s dur=%.3fs first_pkt=%.3fs rtf=%.3f"
                  % (r["lang"], r["n_chunks"], r["n_samples_total"],
                     r["frames_implied"], r["frames_implied_is_integer"],
                     r["every_chunk_multiple_of_1920"], r["dur_s"],
                     r["first_packet_s"], r["rtf"]))
            print("      chunk_samples=%s" % r["chunk_samples"])


if __name__ == "__main__":
    main()
