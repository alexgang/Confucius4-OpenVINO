"""bgkeep_e2e.py — v0.4.19「保留背景音」end-to-end check against a running real bridge (no browser).

Acts like the player over the real wire protocol, in real time:
  * hello {role:'uplink', bg_keep, bg_sample_rate:48000, bg_channels:2, target_lang, voice}
  * `pcm`    16 kHz mono PCM16 frames (100 ms)   — same as the player's ASR uplink
  * `pcm_bg` 48 kHz stereo PCM16 frames (100 ms) — same time origin
Collects `tts`, `bg`, `bg_status`, then reports:
  * background blocks: count, contiguity, and arrival margin vs. play time (t0 + t_start + D); late blocks
  * separator device / RTF / lead (from bg_status + stats), dubs delivered
  * an offline render of what the player plays: background (−4 dB under each dub) + dubs at t_start,
    falling back to the original ducked −15 dB wherever no background block arrived in time.

Usage (on A, bridge already running with real engines):
  python tools/bgkeep_e2e.py --media clip.mp4 --port 8765 --out .tmp/bgkeep --target-lang zh [--toggle-off-at 60 --toggle-on-at 90]
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".runtime_deps"))
import websockets  # noqa: E402


def load_media(path: str, ffmpeg: str) -> np.ndarray:
    """-> float32 [2, n] at 48 kHz. WAV is read directly (no ffmpeg needed); other media via ffmpeg."""
    if path.lower().endswith(".wav"):
        with wave.open(path, "rb") as w:
            ch, sr, sw = w.getnchannels(), w.getframerate(), w.getsampwidth()
            assert sw == 2, "16-bit wav expected"
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, ch).T.astype(np.float32) / 32768.0
        if ch == 1:
            x = np.vstack([x, x])
        x = x[:2]
        if sr != 48000:
            from scipy.signal import resample_poly
            x = resample_poly(x, 48000, sr, axis=1).astype(np.float32)
        return x
    raw = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "2", "-ar", "48000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return (np.frombuffer(raw, "<i2").reshape(-1, 2).T.astype(np.float32) / 32768.0)


def to16k(x48: np.ndarray) -> np.ndarray:
    from scipy.signal import resample_poly
    return resample_poly(x48.mean(0), 1, 3).astype(np.float32)


def wav_write(path, x, sr):
    x = np.clip(np.atleast_2d(x), -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(x.shape[0]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x.T * 32767).astype("<i2").tobytes())


async def run(a):
    x48 = load_media(a.media, a.ffmpeg)
    if a.max_sec:
        x48 = x48[:, :int(a.max_sec * 48000)]
    x16 = to16k(x48)
    dur = x48.shape[1] / 48000.0
    token = open(a.token_file, encoding="utf-8").read().strip() if os.path.exists(a.token_file) else ""
    got = {"tts": [], "bg": [], "bg_status": [], "stats": None, "shift": {}}
    url = f"ws://127.0.0.1:{a.port}/"
    sys.path.insert(0, ROOT)
    from ext.extension_id import resolve_extension_id
    origin = "chrome-extension://" + str(resolve_extension_id())     # the bridge only accepts the extension origin
    async with websockets.connect(url, max_size=None, open_timeout=30, origin=origin) as ws:
        await ws.send(json.dumps({"type": "hello", "token": token, "role": "uplink", "source": "player",
                                  "sample_rate": 16000, "delay_sec": a.delay, "target_lang": a.target_lang,
                                  "voice": a.voice, "bg_keep": not a.bg_off, "bg_sample_rate": 48000,
                                  "bg_channels": 2, "capture_mode": "tabCapture"}))
        t0 = None

        async def reader():
            async for raw in ws:
                try:
                    m = json.loads(raw)
                except Exception:
                    continue
                now = time.perf_counter()
                k = m.get("type")
                if k == "hello_ack":
                    got["hello_ack"] = {x: m.get(x) for x in ("delay_sec", "bg_supported", "bg_model", "bg", "mode")}
                elif k == "tts":
                    got["tts"].append({"id": str(m.get("id")), "t_start": m.get("t_start"), "t_end": m.get("t_end"), "sr": m.get("sample_rate", 24000),
                                       "pcm": m.get("pcm24k"), "tgt": m.get("tgt"), "src": m.get("src"),
                                       "arr": now - t0 if t0 else None})
                elif k == "bg":
                    got["bg"].append({"t_start": m["t_start"], "n": m["n_frames"], "sr": m["sample_rate"],
                                      "pcm": m["pcm"], "arr": now - t0 if t0 else None})
                elif k == "dub_shift":
                    got["shift"][str(m.get("id"))] = (float(m["t_start"]), now - t0 if t0 else None)
                elif k == "bg_status":
                    got["bg_status"].append({**{x: m.get(x) for x in ("state", "device", "reason", "rtf", "lead_sec")},
                                             "at": round(now - t0, 2) if t0 else None})
                elif k == "stats":
                    got["stats"] = m

        rd = asyncio.create_task(reader())
        await asyncio.sleep(1.0)
        t0 = time.perf_counter()
        n_frames = int(np.ceil(dur * 10))
        bg_on = not a.bg_off
        toggled_off = toggled_on = False
        for k in range(n_frames):
            target = t0 + k * 0.1
            d = target - time.perf_counter()
            if d > 0:
                await asyncio.sleep(d)
            ts = k * 0.1
            if a.toggle_off_at is not None and bg_on and not toggled_off and ts >= a.toggle_off_at:
                bg_on, toggled_off = False, True
                await ws.send(json.dumps({"type": "bg_keep", "on": False}))
            if a.toggle_on_at is not None and not bg_on and not toggled_on and not a.bg_off and ts >= a.toggle_on_at:
                bg_on, toggled_on = True, True
                await ws.send(json.dumps({"type": "bg_keep", "on": True}))
            p16 = (np.clip(x16[k * 1600:(k + 1) * 1600], -1, 1) * 32767).astype("<i2")
            await ws.send(json.dumps({"type": "pcm", "seq": k, "sample_index": k * 1600,
                                      "pcm": base64.b64encode(p16.tobytes()).decode()}))
            if bg_on:
                p48 = (np.clip(x48[:, k * 4800:(k + 1) * 4800], -1, 1).T * 32767).astype("<i2")
                await ws.send(json.dumps({"type": "pcm_bg", "seq": k, "sample_index_bg": k * 4800, "rate": 48000,
                                          "ch": 2, "pcm": base64.b64encode(p48.tobytes()).decode()}))
            if k % 50 == 0:
                await ws.send(json.dumps({"type": "stats"}))
        await ws.send(json.dumps({"type": "flush"}))
        t_end = time.perf_counter()
        while time.perf_counter() - t_end < a.tail_wait:
            await ws.send(json.dumps({"type": "stats"}))
            await asyncio.sleep(2.0)
        rd.cancel()
    return x48, dur, got


def report(a, x48, dur, got):
    os.makedirs(a.out, exist_ok=True)
    D = a.delay
    bg = sorted(got["bg"], key=lambda b: b["t_start"])
    contig = all(abs(bg[i + 1]["t_start"] - (bg[i]["t_start"] + bg[i]["n"] / 48000)) < 1e-4 for i in range(len(bg) - 1))
    margins = [b["t_start"] + D - b["arr"] for b in bg if b["arr"] is not None]
    late = [round(b["t_start"], 1) for b, mg in zip(bg, margins) if mg < 0.03]
    st = got.get("stats") or {}
    out = {
        "media": a.media, "duration_s": round(dur, 1), "delay_sec": D, "hello_ack": got.get("hello_ack"),
        "bg_blocks": len(bg), "bg_contiguous": contig,
        "bg_covered_s": round(sum(b["n"] for b in bg) / 48000, 1),
        "bg_margin_min_s": round(min(margins), 2) if margins else None,
        "bg_margin_p10_s": round(float(np.percentile(margins, 10)), 2) if margins else None,
        "bg_margin_median_s": round(float(np.median(margins)), 2) if margins else None,
        "bg_late_blocks": len(late), "bg_late_at": late[:20],
        "bg_status_seq": [(s["state"], s["device"], s["at"]) for s in got["bg_status"]][:12],
        "bg_status_last": got["bg_status"][-1] if got["bg_status"] else None,
        "dubs": len(got["tts"]),
        "dub_late_vs_play_s": (lambda L: {"max": round(max(L), 2), "p90": round(float(np.percentile(L, 90)), 2),
                                           "n_late": sum(1 for v in L if v > 0)} if L else None)(
            [t["arr"] - (float(t["t_start"]) + D) for t in got["tts"] if t["arr"] is not None and t["t_start"] is not None]),
        "stats_bg": {k: v for k, v in st.items() if k.startswith(("bg_", "sep_"))},
        "stats_misc": {k: st.get(k) for k in ("n_frames", "n_dropped", "proc_cpu_pct", "igpu_pct", "npu_pct", "rss_mb")},
        "stats_full": st,
    }
    # offline render of the player output (bg/orig switching + duck + dubs)
    n = x48.shape[1] + 48000 * 5
    y = np.zeros((2, n), np.float32)
    cover = np.zeros(n, bool)
    for b, mg in zip(bg, margins):
        if mg < 0.03:
            continue
        s0 = int(round(b["t_start"] * 48000))
        pcm = np.frombuffer(base64.b64decode(b["pcm"]), "<i2").reshape(-1, 2).T.astype(np.float32) / 32768
        e = min(n, s0 + pcm.shape[1])
        y[:, s0:e] += pcm[:, :e - s0]
        cover[s0:e] = True
    duck = np.ones(n, np.float32)
    dub = np.zeros(n, np.float32)
    from scipy.signal import resample_poly
    # dub placement like the player: sequential (no overlap), then `dub_shift` moves a dub later (only if the
    #   shift arrived before its play time, and never into the next dub)
    tts = sorted([t for t in got["tts"] if t["pcm"]], key=lambda t: float(t["t_start"]))
    vs, starts = [], []
    prev_end = 0.0
    for t in tts:
        v = np.frombuffer(base64.b64decode(t["pcm"]), "<i2").astype(np.float32) / 32768
        v = resample_poly(v, 48000, int(t["sr"] or 24000)).astype(np.float32)
        st = max(float(t["t_start"]), prev_end)
        vs.append(v); starts.append(st); prev_end = st + v.size / 48000
    n_shift = 0
    for i, t in enumerate(tts):
        sh = got["shift"].get(t["id"])
        if not sh or sh[1] is None or sh[1] > starts[i] + D - 0.15:
            continue
        limit = starts[i + 1] if i + 1 < len(tts) else 1e9
        new = min(sh[0], limit - vs[i].size / 48000 - 0.02)
        if new > starts[i] + 0.02:
            starts[i] = new; n_shift += 1
    for t, v, st in zip(tts, vs, starts):
        s0 = int(round(st * 48000))
        e = min(n, s0 + v.size)
        dub[s0:e] += v[:e - s0]
        duck[max(0, s0 - 3840):min(n, e + 2400)] = 10 ** (-4 / 20)
    orig = np.zeros((2, n), np.float32)
    orig[:, :x48.shape[1]] = x48 * (10 ** (-15 / 20))
    mix = np.where(cover[None], y * duck[None], orig) + dub[None]
    wav_write(os.path.join(a.out, "player_mix.wav"), mix[:, :x48.shape[1]], 48000)
    wav_write(os.path.join(a.out, "bg_only.wav"), y[:, :x48.shape[1]], 48000)
    out["dub_shift_msgs"] = len(got["shift"])
    out["dub_shift_applied"] = n_shift
    out["fallback_to_orig_s"] = round(float((~cover[:x48.shape[1]]).sum()) / 48000, 1)
    out["dub_items"] = [{"t": round(float(t["t_start"]), 2), "shift_to": (round(got["shift"][t["id"]][0], 2) if t["id"] in got["shift"] else None), "src": (t["src"] or "")[:40], "tgt": (t["tgt"] or "")[:40]}
                        for t in got["tts"][:8]]
    try:   # per-dub audio for offline checks (e.g. dub gender vs. source gender)
        np.savez_compressed(os.path.join(a.out, "dubs.npz"),
                            t_start=np.array([float(t["t_start"]) for t in tts]), t_end=np.array([float(t["t_end"] or 0) for t in tts]),
                            sr=np.array([int(t["sr"] or 24000) for t in tts]),
                            **{f"pcm_{i}": np.frombuffer(base64.b64decode(t["pcm"]), "<i2") for i, t in enumerate(tts)})
    except Exception as e:
        out["dubs_npz_error"] = repr(e)[:200]
    json.dump(out, open(os.path.join(a.out, "bgkeep_e2e.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "dub_items"}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--delay", type=float, default=20.0)
    ap.add_argument("--target-lang", default="zh")
    ap.add_argument("--voice", default="A")
    ap.add_argument("--token-file", default=os.path.join(ROOT, "bridge_token.txt"))
    ap.add_argument("--ffmpeg", default="ffmpeg")
    ap.add_argument("--out", default=os.path.join(ROOT, ".tmp", "bgkeep"))
    ap.add_argument("--max-sec", type=float, default=None)
    ap.add_argument("--tail-wait", type=float, default=30.0)
    ap.add_argument("--bg-off", action="store_true", help="run with 保留背景音 off (regression arm)")
    ap.add_argument("--toggle-off-at", type=float, default=None)
    ap.add_argument("--toggle-on-at", type=float, default=None)
    a = ap.parse_args()
    x48, dur, got = asyncio.run(run(a))
    report(a, x48, dur, got)


if __name__ == "__main__":
    main()
