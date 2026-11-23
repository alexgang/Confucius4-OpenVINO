"""APP-123 §3: add the TTS-076 peak limiter (whole-utterance scaling) + clipping count.

TTS-076 (TTS module) replaced the hard `np.clip(-1, 1)` with WHOLE-SENTENCE
scaling:
    peak_before = max |raw|
    n_clipped   = count(|raw| > 1.0)        # would have been flattened
    n_near_fs   = count(|raw| >= 0.999)     # reviewer口径
    gain        = 0.98 / peak_before  if peak_before > 0.98 else 1.0
    wav         = raw * gain
=> no flattened (distorted) plateau, and |x| >= 0.999 count drops to 0.

WHERE TO APPLY IT IN THE APP
  The App's OV path is BabelVox-driven: `babelvox/pipeline.py` L637 already does
  `np.clip(wav, -1.0, 1.0)` on EVERY decoded chunk (the hard clip TTS-076
  removed). We cannot change the vendored library's behaviour, but we CAN apply
  the sentence-level limiter to the assembled sentence BEFORE it is played /
  dumped, which is exactly where TTS-076 applied it.

  Scope: the OV path only (the CUDA path is explicitly out of scope per
  APP-123, and the CUDA sidecar has its own audio chain).

  The limiter acts on the assembled per-sentence waveform:
      wav_parts  -> the raw per-chunk waveform of this sentence
      out_parts  -> the speed-adjusted waveform actually played
  We scale `out_parts` (what the user hears) and report the numbers in the
  per-sentence telemetry.

  IMPORTANT: the hard clip inside babelvox happens PER CHUNK, before we see the
  sentence. So a sample that exceeded 1.0 inside a chunk was already flattened
  there and cannot be recovered. What the sentence-level limiter CAN do is
  guarantee the ASSEMBLED sentence never sits above 0.98 (i.e. no additional
  hard-clip distortion at the sentence level) and it tells the reviewer exactly
  how many samples were at/over full scale (the observable proxy for "the
  signal was too hot").
  => This limitation is stated plainly in the STATUS so the reviewer is not
     misled into thinking the babelvox per-chunk clip was removed.

  It also adds the limiter to the OV path only, leaving the CUDA path byte-identical.
"""
import os

WORKER = r"C:\Users\Trekker-PTL\confucius4-openvino\live_caption\tts_worker.py"

PEAK_LIMIT = 0.98   # TTS-076 threshold (same constant as _tts076_worker.py)


def read_lines(p):
    with open(p, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    nl = "\r\n" if b"\r\n" in raw else "\n"
    if nl == "\r\n":
        text = text.replace("\r\n", "\n")
    return text, nl


def write_lines(p, text, nl):
    if nl == "\r\n":
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    data = text.replace("\n", nl).encode("utf-8")
    tmp = p + ".tmp_app123b"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, p)


def find_line(lines, needle, start=0):
    hits = [i for i, l in enumerate(lines) if needle in l and i >= start]
    if len(hits) != 1:
        raise SystemExit("ANCHOR %r: expected 1 line, found %d" % (needle, len(hits)))
    return hits[0]


text, nl = read_lines(WORKER)
lines = text.split("\n")

# IDEMPOTENCE: this script owns ONLY the limiter helper + the apply block +
# the telemetry fields. The clipping COUNTERS are inserted by
# `_app123_patch_tts_engine.py` (a different script) => do NOT guard on them
# here, or this script would refuse to run whenever the counters exist.
_MARKERS = [
    "def app123_peak_limit(wav, peak_limit=None):",
    "app123_peak_limit(_sent)",
]
_found = [m for m in _MARKERS if any(m in l for l in lines)]
if _found:
    raise SystemExit("REFUSING to re-apply: markers already present: %s" % _found)

# ── 1) the limiter helper (module level, right after the APP-027 jsonl keys) ──
i_keys = find_line(lines, "_APP027_JSONL_KEYS = (")
helper = [
    "",
    "",
    "# 🔴🔴🔴 **APP-123 §3 / TTS-076：峰值限幅（整句缩放）+ 削波计数**",
    "#",
    "# TTS-076 的做法：旧版用 `np.clip(-1, 1)` **硬削** ⇒ 削平段失真；",
    "# 新版改成**整句缩放**（peak > 0.98 ⇒ gain = 0.98 / peak）",
    "# ⇒ wav 里 |x| >= 0.999 的采样数从 33 降到 **0**。",
    "#",
    "# ⚠️ **本 App 的诚实边界**（写清楚，别让 reviewer 误读）：",
    "#   OV 路径的**每块**硬削发生在 `babelvox/pipeline.py` L637"
    "（`np.clip(wav, -1.0, 1.0)`），",
    "#   那在**块级**、在我们看到整句之前 ⇒ 块内已越界的采样**无法恢复**。",
    "#   本函数做的是：**整句**层面保证成品不超过 0.98（不再叠加失真），",
    "#   并如实报出 `n_clipped` / `n_near_fs` / `peak_before` / `limiter_gain`，",
    "#   让 reviewer 能判断「信号是否过热」。",
    "APP123_PEAK_LIMIT = 0.98",
    "",
    "",
    "def app123_peak_limit(wav, peak_limit=None):",
    '    """整句峰值限幅（TTS-076 口径）。返回 (wav_limited, info)。',
    "",
    "    info 里有 peak_before / peak_after / limiter_gain / n_clipped /",
    "    n_near_full_scale / limited 六个字段。",
    '    """',
    "    info = dict(peak_before=0.0, peak_after=0.0, limiter_gain=1.0,",
    "                n_clipped=0, n_near_full_scale=0, limited=False)",
    "    if wav is None:",
    "        return wav, info",
    "    try:",
    "        import numpy as _np",
    "        arr = _np.asarray(wav, dtype=_np.float32).reshape(-1)",
    "    except Exception:",
    "        return wav, info",
    "    if arr.size == 0:",
    "        return wav, info",
    "    lim = APP123_PEAK_LIMIT if peak_limit is None else float(peak_limit)",
    "    absarr = _np.abs(arr)",
    "    peak_before = float(absarr.max())",
    "    info['peak_before'] = round(peak_before, 6)",
    "    info['n_clipped'] = int(_np.count_nonzero(absarr > 1.0))",
    "    info['n_near_full_scale'] = int(_np.count_nonzero(absarr >= 0.999))",
    "    if peak_before > lim and peak_before > 0:",
    "        gain = lim / peak_before",
    "        arr = (arr * gain).astype(_np.float32)",
    "        info['limiter_gain'] = round(float(gain), 6)",
    "        info['limited'] = True",
    "    info['peak_after'] = round(float(_np.abs(arr).max()) if arr.size else 0.0, 6)",
    "    return arr, info",
]
# insert AFTER the _APP027_JSONL_KEYS tuple closes -> find the next line that is
# not part of the tuple (a line that starts at column 0 after the tuple)
i_after = i_keys
depth = 0
started = False
while True:
    line = lines[i_after]
    depth += line.count("(") - line.count(")")
    if "(" in line:
        started = True
    if started and depth <= 0:
        break
    i_after += 1
    if i_after > i_keys + 60:
        raise SystemExit("could not find the end of _APP027_JSONL_KEYS")
lines[i_after + 1:i_after + 1] = helper

# ── 2) apply the limiter to the assembled sentence (OV path) ──
# The assembled sentence is built from `out_parts` (speed-adjusted, played).
# Apply the limit right before the telemetry is built, and stash the info in
# `_app123_limiter` so the telemetry can carry it.
i_tel = find_line(lines, "tel = self._telemetry_snapshot(n_samples, n_parts, peak, rms_dbfs,")
apply_block = [
    "        # 🔴🔴🔴 APP-123 §3 / TTS-076：整句峰值限幅",
    "        #   （OV 路径；CUDA 路径不经过这里 ⇒ CUDA 行为逐字不变）",
    "        _app123_limiter = None",
    "        try:",
    "            _sent = (np.concatenate(out_parts) if len(out_parts) > 1",
    "                     else (out_parts[0] if out_parts else None))",
    "            if _sent is not None and len(_sent):",
    "                _sent_lim, _app123_limiter = app123_peak_limit(_sent)",
    "                if _app123_limiter.get('limited'):",
    "                    # 整句缩放 ⇒ 回写到逐块列表（保持各块相对时长不变）",
    "                    _g = float(_app123_limiter['limiter_gain'])",
    "                    out_parts = [np.asarray(p, dtype=np.float32) * _g",
    "                                 for p in out_parts]",
    "        except Exception as e:",
    "            log('[tts_worker] APP-123 峰值限幅失败（忽略）：%s' % e)",
    "            _app123_limiter = None",
]
lines[i_tel:i_tel] = apply_block

# ── 3) carry the limiter numbers into the telemetry dict ──
i_peakfield = find_line(lines, "peak=round(float(peak), 6),")
extra_tel = [
    "                   # 🔴 APP-123 §3 / TTS-076：限幅与削波计数",
    "                   **({'n_clipped': int(_app123_limiter['n_clipped']),",
    "                       'n_near_full_scale': int(_app123_limiter['n_near_full_scale']),",
    "                       'peak_before_limit': float(_app123_limiter['peak_before']),",
    "                       'limiter_gain': float(_app123_limiter['limiter_gain'])}",
    "                      if _app123_limiter else {}),",
]
lines[i_peakfield + 1:i_peakfield + 1] = extra_tel

write_lines(WORKER, "\n".join(lines), nl)
print("tts_worker.py: APP-123 peak limiter applied")
