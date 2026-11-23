"""APP-123: decisive A/B for the c13 window口径 on the App's OV path.

Two arms, same seed, same text, same engine:
  A "multi_bucket"  : the App's PRODUCTION decoder buckets [8,16,32,33]
                      (smallest-fitting bucket, per call)
  B "c13_fixed_38"  : c13 semantics -> ONE fixed static window of 38 frames
                      (i.e. decoder_chunk_frames 13 + ctx 25), zero-padded

Measured per arm:
  * samples per chunk, total samples, frames implied (= samples/1920)
  * whether every chunk is a multiple of 1920  (length conservation)
  * first-packet latency, wall time, RTF
  * the WAVEFORM itself, so we can compute the SNR between the two arms
    (same seed => same tokens => any difference is the window, not sampling)

The SNR tells us whether the c13 fixed window is a *behaviour change* or just a
different way to express the same thing.
"""
import json
import os
import sys
import time

import numpy as np

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5"
DEV = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption"
OUT = (r"C:\Users\Trekker-PTL\confucius4-openvino\results\app"
       r"\app123_c13_window_ab.json")

SEED = 20261023
TEXTS = [("zh", "你好，这是实时字幕的测试。"),
         ("en", "Yes, good.")]

sys.path.insert(0, os.path.join(PKG, "app"))
sys.path.insert(0, os.path.join(PKG, "python", "Lib", "site-packages"))
sys.path.insert(0, DEV)


def run_arm(label, env_overrides, device="GPU.0"):
    saved = {}
    for k, v in env_overrides.items():
        saved[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    sys.modules.pop("tts_engine", None)
    import tts_engine as te

    rows = []
    eng = None
    try:
        eng = te.make_engine(device=device,
                             on_log=lambda s: print("   [engine]", s, flush=True))
        for lang, text in TEXTS:
            blang = "Chinese" if lang == "zh" else "English"
            np.random.seed(SEED)
            chunks, wavs = [], []
            t0 = time.perf_counter()
            first_at = None
            for wav_chunk, sr in te.stream(eng, text, language=blang, speaker=None):
                n = int(len(wav_chunk))
                chunks.append(n)
                wavs.append(np.asarray(wav_chunk, dtype=np.float32).reshape(-1))
                if first_at is None:
                    first_at = time.perf_counter() - t0
            wall = time.perf_counter() - t0
            full = np.concatenate(wavs) if wavs else np.zeros(0, np.float32)
            dur = len(full) / float(sr)
            frames = len(full) / 1920.0
            rows.append(dict(
                lang=lang, text=text, sr=int(sr),
                n_chunks=len(chunks), chunk_samples=chunks,
                n_samples_total=int(len(full)),
                dur_s=round(dur, 6),
                frames_implied=round(frames, 6),
                frames_is_integer=abs(frames - round(frames)) < 1e-6,
                every_chunk_x1920=all(c % 1920 == 0 for c in chunks),
                first_packet_s=round(first_at or 0.0, 6),
                wall_s=round(wall, 6),
                rtf=round(wall / dur, 6) if dur > 0 else None,
                peak=float(np.abs(full).max()) if full.size else 0.0,
                n_clipped=int(np.count_nonzero(np.abs(full) >= 1.0)),
                n_near_fs=int(np.count_nonzero(np.abs(full) >= 0.999)),
                _wav=full,
            ))
        return dict(arm=label, seed=SEED,
                    chunk_frames=te.CHUNK_FRAMES, ctx_frames=te.CTX_FRAMES,
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


def snr(a, b):
    n = min(len(a), len(b))
    if n == 0:
        return None
    a = a[:n].astype(np.float64)
    b = b[:n].astype(np.float64)
    noise = a - b
    ps = float(np.sum(a * a))
    pn = float(np.sum(noise * noise))
    if pn <= 0:
        return float("inf")
    if ps <= 0:
        return None
    return round(10.0 * np.log10(ps / pn), 4)


def main():
    out = {}
    DEV = os.environ.get("APP123_DEVICE", "GPU.0")
    print("### device = %s ###" % DEV)
    # A: production multi-bucket
    out["A_multi_bucket_prod"] = run_arm("A_multi_bucket_prod", {
        "LIVECAP_TTS_DECODER_BUCKETS": "8,16,32,33",
        "LIVECAP_TTS_CHUNK_FRAMES": "8",
        "LIVECAP_TTS_CTX_FRAMES": "25",
        "LIVECAP_TTS_DIRECT_CONCAT": "1",
    }, device=DEV)
    # B: c13 fixed 38-frame static window
    out["B_c13_fixed_38"] = run_arm("B_c13_fixed_38", {
        "LIVECAP_TTS_DECODER_BUCKETS": "38",
        "LIVECAP_TTS_CHUNK_FRAMES": "8",
        "LIVECAP_TTS_CTX_FRAMES": "25",
        "LIVECAP_TTS_DIRECT_CONCAT": "1",
    }, device=DEV)

    # SNR between the arms (same seed => same tokens)
    print("\n=== A/B 波形对比（同 seed ⇒ 同一批 token）===")
    cmp_rows = []
    for ra, rb in zip(out["A_multi_bucket_prod"]["rows"],
                       out["B_c13_fixed_38"]["rows"]):
        s = snr(ra["_wav"], rb["_wav"])
        same_len = len(ra["_wav"]) == len(rb["_wav"])
        print("   %s: A samples=%d  B samples=%d  same_len=%s  SNR(A,B)=%s dB"
              % (ra["lang"], len(ra["_wav"]), len(rb["_wav"]), same_len, s))
        cmp_rows.append(dict(lang=ra["lang"], a_samples=len(ra["_wav"]),
                             b_samples=len(rb["_wav"]),
                             same_len=bool(same_len), snr_db=s))
    out["ab_waveform_compare"] = cmp_rows

    for d in out.values():
        if isinstance(d, dict):
            for r in d.get("rows", []) if isinstance(d.get("rows"), list) else []:
                r.pop("_wav", None)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print("\n=== %s ===" % OUT)
    for arm, d in out.items():
        if arm == "ab_waveform_compare":
            continue
        print("\n[%s] chunk=%s ctx=%s buckets=%s direct_concat=%s"
              % (arm, d["chunk_frames"], d["ctx_frames"], d["buckets"],
                 d["direct_concat"]))
        for r in d["rows"]:
            print("   %s: chunks=%d samples=%d frames=%.4f int=%s "
                  "all_x1920=%s dur=%.3fs first_pkt=%.3fs rtf=%.3f "
                  "peak=%.4f clipped=%d near_fs=%d"
                  % (r["lang"], r["n_chunks"], r["n_samples_total"],
                     r["frames_implied"], r["frames_is_integer"],
                     r["every_chunk_x1920"], r["dur_s"], r["first_packet_s"],
                     r["rtf"], r["peak"], r["n_clipped"], r["n_near_fs"]))
            print("      chunk_samples=%s" % r["chunk_samples"])


if __name__ == "__main__":
    main()
