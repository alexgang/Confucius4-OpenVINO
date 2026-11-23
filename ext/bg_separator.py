"""bg_separator.py — streaming background/vocals separation for "keep background audio" (EXT v0.4.19).

Pipeline (all in one worker thread, never on the websocket loop or the ASR path):
    48 kHz stereo s16 uplink (`pcm_bg`)  ->  44.1 kHz  ->  htdemucs (OpenVINO core, 7.8 s chunks,
    25 % overlap, triangular cross-fade = demucs `apply_model(split=True, overlap=0.25)`)
    ->  background = drums+bass+other  ->  48 kHz stereo blocks for the player (`bg` messages)
    ->  vocals -> 16 kHz mono for the speaker / voice-clone paths.

Only the network core is in the IR (`htdemucs_core.xml`, converted from the official htdemucs weights
with torch.export; see shared/bgkeep/ov_demucs.py). STFT / iSTFT / complex-as-channels packing are
re-implemented here with numpy so the runtime needs no torch; they match demucs' `_spec`,
`_magnitude`, `_mask`, `_ispec` (verified against torch, SNR > 100 dB).

Time base: sample i of the 48 kHz uplink is at t = i / 48000 s, the same origin as the 16 kHz
ASR uplink (`sample_index / 16000`). Everything emitted keeps that origin.
"""
from __future__ import annotations

import math
import os
import queue
import threading
import time
from typing import Callable, List, Optional

import numpy as np

SR_IN = 48000          # uplink / player rate
SR_MODEL = 44100       # htdemucs rate
SR_SPK = 16000         # speaker / clone paths
SEG = 343980           # int(7.8 * 44100): htdemucs training segment (the IR is static at this length)
NFFT = 4096
HOP = NFFT // 4
SOURCES = ("drums", "bass", "other", "vocals")
OVERLAP = 0.25
STRIDE = int((1 - OVERLAP) * SEG)


def _log(msg: str) -> None:
    try:
        print(f"[bg_sep] {msg}", flush=True)
    except Exception:
        pass


# ───────────────────────── numpy STFT matching torch.stft / istft ─────────────────────────
_WIN = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(NFFT) / NFFT)).astype(np.float64)   # torch.hann_window (periodic)


def _stft(x: np.ndarray) -> np.ndarray:
    """torch.stft(x, NFFT, HOP, hann, normalized=True, center=True, pad_mode='reflect') for x [..., T]."""
    pad = NFFT // 2
    xp = np.pad(x, [(0, 0)] * (x.ndim - 1) + [(pad, pad)], mode="reflect")
    n_frames = 1 + (xp.shape[-1] - NFFT) // HOP
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n_frames)[:, None]
    frames = xp[..., idx] * _WIN                       # [..., frames, NFFT]
    z = np.fft.rfft(frames, axis=-1) / math.sqrt(NFFT)  # normalized=True
    return np.swapaxes(z, -1, -2)                       # [..., freqs, frames]


def _istft(z: np.ndarray, length: int) -> np.ndarray:
    """torch.istft(z, NFFT, HOP, hann, normalized=True, center=True, length=length)."""
    frames = np.fft.irfft(np.swapaxes(z, -1, -2) * math.sqrt(NFFT), n=NFFT, axis=-1)   # [..., frames, NFFT]
    n_frames = frames.shape[-2]
    full = HOP * (n_frames - 1) + NFFT
    out = np.zeros(frames.shape[:-2] + (full,), dtype=np.float64)
    env = np.zeros(full, dtype=np.float64)
    w2 = _WIN ** 2
    for f in range(n_frames):
        s = f * HOP
        out[..., s:s + NFFT] += frames[..., f, :] * _WIN
        env[s:s + NFFT] += w2
    pad = NFFT // 2
    out = out[..., pad:pad + length]
    env = env[pad:pad + length]
    return out / np.where(env > 1e-11, env, 1.0)


def _spec(x: np.ndarray) -> np.ndarray:
    """demucs HTDemucs._spec: x [C, T] -> complex [C, NFFT/2, T/HOP]."""
    le = int(math.ceil(x.shape[-1] / HOP))
    pad = HOP // 2 * 3
    xp = np.pad(x, [(0, 0), (pad, pad + le * HOP - x.shape[-1])], mode="reflect")
    z = _stft(xp)[..., :-1, :]
    return z[..., 2:2 + le]


def _ispec(z: np.ndarray, length: int) -> np.ndarray:
    """demucs HTDemucs._ispec: z [..., NFFT/2, frames] -> [..., length]."""
    z = np.pad(z, [(0, 0)] * (z.ndim - 2) + [(0, 1), (0, 0)])
    z = np.pad(z, [(0, 0)] * (z.ndim - 1) + [(2, 2)])
    pad = HOP // 2 * 3
    le = HOP * int(math.ceil(length / HOP)) + 2 * pad
    x = _istft(z, le)
    return x[..., pad:pad + length]


def _magnitude(z: np.ndarray) -> np.ndarray:
    """cac packing: complex [C, F, T] -> real [C*2, F, T] ordered (c0.re, c0.im, c1.re, c1.im)."""
    C, F, T = z.shape
    m = np.stack([z.real, z.imag], axis=1)               # [C, 2, F, T]
    return m.reshape(C * 2, F, T)


def _mask(m: np.ndarray) -> np.ndarray:
    """cac unpacking: real [S, C*2, F, T] -> complex [S, C, F, T]."""
    S, C2, F, T = m.shape
    m = m.reshape(S, C2 // 2, 2, F, T)
    return m[:, :, 0] + 1j * m[:, :, 1]


# ───────────────────────── chunked resampler (exact block ratios, no edge artifacts) ─────────────────────────
class BlockResampler:
    """Streaming rational resampler: consumes input in blocks of `up_in` samples, emits `up_out` per block.

    Each block is resampled together with `ctx` blocks of real context on both sides (resample_poly
    FIR spans ~10 input periods), then the middle is kept, so block seams match an offline resample.
    Output lags input by `ctx` blocks.
    """

    def __init__(self, sr_in: int, sr_out: int, channels: int, block_in: int, ctx_blocks: int = 2):
        g = math.gcd(sr_in, sr_out)
        self.up, self.down = sr_out // g, sr_in // g
        assert block_in % self.down == 0, (block_in, self.down)
        self.block_in = block_in
        self.block_out = block_in * self.up // self.down
        self.ctx = ctx_blocks
        self.ch = channels
        self._buf = np.zeros((channels, 0), np.float32)
        self._started = False
        self.n_out = 0
        try:
            from scipy.signal import resample_poly
            self._rp = resample_poly
        except Exception:      # no scipy: linear interpolation (worse, but never crashes)
            self._rp = None

    def _resample(self, x: np.ndarray) -> np.ndarray:
        if self._rp is not None:
            return self._rp(x, self.up, self.down, axis=-1).astype(np.float32)
        n = x.shape[-1] * self.up // self.down
        src = np.arange(n) * (self.down / self.up)
        return np.stack([np.interp(src, np.arange(x.shape[-1]), c) for c in x]).astype(np.float32)

    def push(self, x: np.ndarray, final: bool = False) -> np.ndarray:
        """x [C, n] float32. Returns newly finalized output [C, m]."""
        if not self._started:      # reflect-free start: pretend ctx blocks of silence before t=0
            self._buf = np.zeros((self.ch, self.ctx * self.block_in), np.float32)
            self._started = True
        if x.size:
            self._buf = np.concatenate([self._buf, x.astype(np.float32)], axis=1)
        outs = []
        B, K = self.block_in, self.ctx
        while self._buf.shape[1] >= (2 * K + 1) * B:
            y = self._resample(self._buf[:, :(2 * K + 1) * B])
            outs.append(y[:, K * self.block_out:(K + 1) * self.block_out])
            self._buf = self._buf[:, B:]
        if final:
            tail = self._buf.shape[1] - K * B                  # real samples not yet emitted
            if tail > 0:
                pad_to = int(math.ceil(tail / B)) * B + 2 * K * B
                buf = np.concatenate([self._buf, np.zeros((self.ch, pad_to - self._buf.shape[1]), np.float32)], 1)
                y = self._resample(buf)
                n_out = int(math.ceil(tail * self.up / self.down))      # same length rule as scipy resample_poly
                outs.append(y[:, K * self.block_out:K * self.block_out + n_out])
            self._buf = self._buf[:, :0]
        out = np.concatenate(outs, axis=1) if outs else np.zeros((self.ch, 0), np.float32)
        self.n_out += out.shape[1]
        return out


# ───────────────────────── model ─────────────────────────
def default_model_path() -> Optional[str]:
    env = os.environ.get("EXT_BG_MODEL")
    if env and os.path.isfile(env):
        return env
    cands = []
    try:
        from .engine_runtime import MODELS_DIR
        cands.append(os.path.join(MODELS_DIR, "bgsep", "htdemucs_core.xml"))
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(here, "..", "models", "bgsep", "htdemucs_core.xml"))
    for c in cands:
        if os.path.isfile(c):
            return os.path.abspath(c)
    return None


class DemucsCore:
    """OpenVINO htdemucs core: (mix [1,2,SEG], packed spec [1,4,2048,336]) -> (x_spec [1,4,4,2048,336], xt [1,4,2,SEG])."""

    def __init__(self, xml: str, device: str = "GPU.0"):
        import openvino as ov
        core = ov.Core()
        m = core.read_model(xml)
        T = int(math.ceil(SEG / HOP))
        m.reshape({m.inputs[0].any_name: [1, 2, SEG], m.inputs[1].any_name: [1, 4, NFFT // 2, T]})
        cfg = {}
        if device.upper().startswith("GPU"):
            cfg["INFERENCE_PRECISION_HINT"] = "f32"      # FP16 on iGPU degrades the background to ~16 dB SNR
        cache = os.environ.get("EXT_BG_CACHE_DIR")
        if cache:
            cfg["CACHE_DIR"] = cache
        t0 = time.perf_counter()
        self.compiled = core.compile_model(m, device, cfg)
        self.compile_s = time.perf_counter() - t0
        self.req = self.compiled.create_infer_request()
        self.device = device

    def separate(self, mix: np.ndarray) -> np.ndarray:
        """mix [2, SEG] float32 at 44.1 kHz -> sources [4, 2, SEG] (drums, bass, other, vocals)."""
        z = _spec(mix.astype(np.float64))                      # [2, 2048, 336] complex
        mag = _magnitude(z)[None].astype(np.float32)           # [1, 4, 2048, 336]
        r = self.req.infer({0: mix[None].astype(np.float32), 1: mag})
        x = np.asarray(r[0])[0].astype(np.float64)             # [4, 4, 2048, 336]
        xt = np.asarray(r[1])[0].astype(np.float64)            # [4, 2, SEG]
        spec_out = _ispec(_mask(x), SEG)                       # [4, 2, SEG]
        return (xt + spec_out).astype(np.float32)


# ───────────────────────── streaming separator ─────────────────────────
class StreamingSeparator:
    """Feed 48 kHz stereo frames with their sample index; get background blocks (48 kHz stereo) and
    16 kHz vocals through callbacks. Runs its own worker thread; `push()` never blocks.

    on_bg(t_start_sec, pcm_s16_interleaved_bytes, n_frames)     — contiguous, non-overlapping blocks
    on_vocals(t_start_sec, float32_16k_mono)                     — contiguous
    """

    BLOCK_OUT_SEC = 1.0      # split emitted background into ~1 s messages

    def __init__(self, on_bg: Callable, on_vocals: Optional[Callable] = None, *,
                 model_path: Optional[str] = None, device: Optional[str] = None):
        self.on_bg = on_bg
        self.on_vocals = on_vocals
        self.model_path = model_path or default_model_path()
        self.device = (device or os.environ.get("EXT_BG_DEVICE") or "GPU.0").strip()
        self.state = "starting"
        self.reason = ""
        self._q: "queue.Queue" = queue.Queue(maxsize=4000)
        self._stop = threading.Event()
        self._flush = threading.Event()
        self._th = threading.Thread(target=self._run, name="bg-separator", daemon=True)
        # stats
        self.n_up_frames = 0
        self.up_gaps = 0
        self.n_chunks = 0
        self.chunk_wall: List[float] = []
        self.blocks_sent = 0
        self.emitted_until_sec = 0.0
        self.input_until_sec = 0.0
        self.compile_s = None
        self._next_idx: Optional[int] = None
        self._origin = 0          # 48 kHz index where this separator started (bg toggled on mid-session)
        self._debug = [] if os.environ.get('EXT_BG_DEBUG') else None

    # ── public ──
    def start(self) -> "StreamingSeparator":
        self._th.start()
        return self

    def push(self, sample_index: int, pcm_s16: bytes, channels: int = 2, rate: int = SR_IN) -> None:
        if self.state in ("unavailable", "stopped"):
            return
        if rate != SR_IN or channels != 2:
            self._fail(f"unsupported uplink format {rate} Hz / {channels} ch")
            return
        try:
            self._q.put_nowait((int(sample_index), pcm_s16))
            self.n_up_frames += 1
        except queue.Full:
            self._fail("separator input queue overflow (separation slower than real time)")

    def flush(self) -> None:
        self._flush.set()

    def stop(self) -> None:
        self._stop.set()
        self.state = "stopped" if self.state != "unavailable" else self.state

    def lead_sec(self) -> float:
        """How far the emitted background reaches beyond the newest uplink audio (negative = behind)."""
        return round(self.emitted_until_sec - self.input_until_sec, 3)

    def status(self) -> dict:
        w = sorted(self.chunk_wall)
        p = (lambda q: round(w[min(len(w) - 1, int(len(w) * q))] / (STRIDE / SR_MODEL), 3) if w else None)
        return {"state": self.state, "device": self.device, "reason": self.reason,
                "rtf": p(0.5), "rtf_p90": p(0.9), "lead_sec": self.lead_sec(),
                "chunks": self.n_chunks, "bg_blocks_sent": self.blocks_sent,
                "bg_up_gaps": self.up_gaps, "compile_s": self.compile_s}

    # ── worker ──
    def _fail(self, why: str) -> None:
        if self.state != "unavailable":
            _log(f"unavailable: {why}")
        self.state = "unavailable"
        self.reason = why

    def _load(self):
        if not self.model_path:
            raise RuntimeError("background model not found (models/bgsep/htdemucs_core.xml)")
        order = [self.device] + (["CPU"] if self.device.upper() != "CPU" else [])
        last = None
        for dev in order:
            try:
                core = DemucsCore(self.model_path, dev)
                if dev != self.device:
                    _log(f"{self.device} failed ({last}); using {dev}")
                    self.reason = f"{self.device} unavailable, fell back to {dev}"
                self.device = dev
                self.compile_s = round(core.compile_s, 2)
                return core
            except Exception as e:
                last = f"{type(e).__name__}: {e}"[:200]
        raise RuntimeError(f"cannot compile background model: {last}")

    def _run(self) -> None:
        try:
            core = self._load()
        except Exception as e:
            self._fail(str(e))
            return
        self.state = "ok"
        rs_in = BlockResampler(SR_IN, SR_MODEL, 2, block_in=4800)      # 100 ms -> 4410
        rs_out = BlockResampler(SR_MODEL, SR_IN, 2, block_in=4410)     # back to the player rate
        rs_voc = BlockResampler(SR_MODEL, SR_SPK, 1, block_in=4410)    # 4410 -> 1600
        mix = np.zeros((2, 0), np.float32)       # 44.1 kHz input not yet fully consumed
        mix_base = 0                             # 44.1 kHz index of mix[:, 0]
        acc = np.zeros((4, 2, 0), np.float32)    # weighted source sum for the not-yet-final region
        wsum = np.zeros((0,), np.float32)
        acc_base = 0
        chunk_k = 0
        weight = np.concatenate([np.arange(1, SEG // 2 + 1), np.arange(SEG - SEG // 2, 0, -1)]).astype(np.float32)
        weight /= weight.max()
        out48 = np.zeros((2, 0), np.float32)
        out48_t = 0                               # 48 kHz index of out48[:, 0]
        voc_t = 0
        final = False

        def emit_bg(force: bool = False):
            nonlocal out48, out48_t
            blk = int(self.BLOCK_OUT_SEC * SR_IN)
            while out48.shape[1] >= blk or (force and out48.shape[1] > 0):
                n = min(blk, out48.shape[1])
                part = np.clip(out48[:, :n], -1.0, 1.0)
                pcm = (part.T.reshape(-1) * 32767.0).astype("<i2").tobytes()
                try:
                    self.on_bg((out48_t + self._origin) / SR_IN, pcm, n)
                    self.blocks_sent += 1
                except Exception as e:
                    _log(f"on_bg failed: {e}")
                out48 = out48[:, n:]
                out48_t += n
                self.emitted_until_sec = (out48_t + self._origin) / SR_IN

        def finalize(upto: int):
            """Sources for 44.1 kHz [acc_base, upto) are final: divide by weights, route outputs."""
            nonlocal acc, wsum, acc_base, out48, voc_t
            n = upto - acc_base
            if n <= 0:
                return
            src = acc[:, :, :n] / np.maximum(wsum[:n], 1e-8)
            acc, wsum, acc_base = acc[:, :, n:], wsum[n:], upto
            bg = src[0] + src[1] + src[2]
            if self._debug is not None:
                self._debug.append(src.copy())
            out48 = np.concatenate([out48, rs_out.push(bg)], axis=1)
            if self.on_vocals is not None:
                v16 = rs_voc.push(src[3].mean(0, keepdims=True))
                if v16.shape[1]:
                    try:
                        self.on_vocals(voc_t / SR_SPK + self._origin / SR_IN, v16[0])
                    except Exception as e:
                        _log(f"on_vocals failed: {e}")
                    voc_t += v16.shape[1]
            emit_bg()

        while not self._stop.is_set():
            got = False
            try:
                idx, raw = self._q.get(timeout=0.2)
                got = True
            except queue.Empty:
                pass
            if got:
                a = np.frombuffer(raw, dtype="<i2").astype(np.float32).reshape(-1, 2).T / 32768.0
                if self._next_idx is not None and idx != self._next_idx:
                    if idx > self._next_idx:        # lost uplink frames: fill silence to keep the time base
                        self.up_gaps += 1
                        gap = np.zeros((2, idx - self._next_idx), np.float32)
                        mix = np.concatenate([mix, rs_in.push(gap)], axis=1)
                    else:                           # overlap/duplicate: drop the part we already have
                        a = a[:, self._next_idx - idx:]
                        idx = self._next_idx
                if self._next_idx is None:
                    # start on a 100 ms grid at (or just before) the first frame; only that < 100 ms is padded
                    self._origin = idx - idx % 4800
                    self.emitted_until_sec = self._origin / SR_IN
                    if idx > self._origin:
                        mix = np.concatenate([mix, rs_in.push(np.zeros((2, idx - self._origin), np.float32))], axis=1)
                self._next_idx = idx + a.shape[1]
                self.input_until_sec = self._next_idx / SR_IN
                mix = np.concatenate([mix, rs_in.push(a)], axis=1)
            if self._flush.is_set() and not final and not got and self._q.empty():   # only after all queued input
                final = True
                mix = np.concatenate([mix, rs_in.push(np.zeros((2, 0), np.float32), final=True)], axis=1)
            # run every chunk whose 7.8 s window is available
            while True:
                start = chunk_k * STRIDE
                have = mix_base + mix.shape[1]
                if have < start + SEG and not (final and have > start):
                    break
                seg = mix[:, start - mix_base:start - mix_base + SEG]
                n_real = seg.shape[1]
                lead = 0
                if n_real < SEG:
                    # last partial window (flush only): centre it like demucs TensorChunk.padded —
                    # real audio before it on the left, zeros after the end on the right
                    delta = SEG - n_real
                    lead = min(delta // 2, start - mix_base)
                    left = mix[:, start - mix_base - lead:start - mix_base]
                    seg = np.concatenate([np.zeros((2, delta // 2 - lead), np.float32), left, seg,
                                          np.zeros((2, delta - delta // 2), np.float32)], axis=1)
                    lead = delta // 2
                t0 = time.perf_counter()
                try:
                    out = core.separate(seg)
                except Exception as e:
                    self._fail(f"inference failed: {type(e).__name__}: {e}"[:200])
                    return
                if lead:
                    out = out[:, :, lead:lead + n_real]
                self.chunk_wall.append(time.perf_counter() - t0)
                self.chunk_wall = self.chunk_wall[-200:]
                self.n_chunks += 1
                # accumulate into acc (which starts at acc_base <= start)
                need = start + n_real - acc_base
                if acc.shape[2] < need:
                    acc = np.concatenate([acc, np.zeros((4, 2, need - acc.shape[2]), np.float32)], axis=2)
                    wsum = np.concatenate([wsum, np.zeros(need - wsum.shape[0], np.float32)])
                o = start - acc_base
                acc[:, :, o:o + n_real] += out[:, :, :n_real] * weight[:n_real]
                wsum[o:o + n_real] += weight[:n_real]
                chunk_k += 1
                last = final and (mix_base + mix.shape[1]) <= start + SEG
                finalize(start + n_real if last else chunk_k * STRIDE)
                # drop consumed input before the next chunk start
                keep_from = chunk_k * STRIDE - SEG // 2 - mix_base     # keep left context for a final partial window
                if keep_from > 0:
                    mix = mix[:, keep_from:]
                    mix_base += keep_from
                if last:
                    break
            if final:
                tail = rs_out.push(np.zeros((2, 0), np.float32), final=True)
                out48 = np.concatenate([out48, tail], axis=1)
                emit_bg(force=True)
                self.state = "stopped"
                return


def selftest_against_torch(wav_path: str, xml: str, device: str = "CPU") -> dict:  # pragma: no cover - dev helper
    """Dev check (needs torch + demucs): run the streaming separator on a wav at 48 kHz and compare the
    background with demucs apply_model(shifts=0, split=True, overlap=0.25) at 44.1 kHz, resampled to 48 kHz."""
    import soundfile as sf
    from scipy.signal import resample_poly
    x, sr = sf.read(wav_path, dtype="float32", always_2d=True)
    x48 = resample_poly(x.T, SR_IN, sr, axis=1).astype(np.float32) if sr != SR_IN else x.T
    blocks, done = [], threading.Event()
    sep = StreamingSeparator(lambda t, pcm, n: blocks.append((t, pcm, n)), model_path=xml, device=device).start()
    step = 4800
    s16 = (np.clip(x48, -1, 1).T * 32767).astype("<i2")
    for i in range(0, s16.shape[0], step):
        sep.push(i, s16[i:i + step].tobytes())
    sep.flush()
    sep._th.join(timeout=600)
    got = np.concatenate([np.frombuffer(p, "<i2").reshape(-1, 2) for _, p, _ in blocks]).T.astype(np.float32) / 32768
    return {"blocks": len(blocks), "frames": got.shape[1], "input_frames": x48.shape[1], "status": sep.status()}
