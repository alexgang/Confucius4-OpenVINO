"""test_ext0419_bgkeep.py — v0.4.19「保留背景音」 bridge-side unit checks (no models, no browser).

  1. _spk_feed keeps ONE continuous 16 kHz axis when the speaker source switches (gap ⇒ silence, overlap ⇒ trim)
  2. the speaker bypass is fed the ORIGINAL until the separator is running (no missing stretch while starting)
  3. onset alignment: sustained voicing only (a short burst does not count); no speech ⇒ unchanged
  4. dub_shift is emitted only after the segment's vocals have arrived, never blocks, drops when too late
  5. spk_engine frame axis: block overlap is not double-counted (frames == round(samples·FPS/SR))
Run: python tests/test_ext0419_bgkeep.py   (prints RESULT: PASS / FAIL, exit code 0 / 1)
"""
import os
import sys
import time
import types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ext import bridge as Bm  # noqa: E402

RES = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok or not detail else f" — {detail}"))


class FakeBypass:
    def __init__(self):
        self.n = 0
        self.calls = []

    def feed(self, a, t_end):
        self.n += len(a)
        self.calls.append((len(a), round(t_end, 4)))


class FakeSep:
    def __init__(self, state="ok"):
        self.state = state

    def status(self):
        return {"state": self.state, "device": "CPU", "reason": "", "rtf": None, "lead_sec": 0.0}


def session(state="ok"):
    s = Bm.PipelineSession("t", engine=None, delay_sec=20.0)
    s.bg_keep = True
    s._bg_sep = FakeSep(state)
    return s


print("1. continuous speaker axis")
s = session()
s.spk_bypass = FakeBypass()
s._spk_feed(np.ones(1600), 0)
s._spk_feed(np.ones(1600), 1600)
s._spk_feed(np.ones(1600), 4800)          # 0.1 s gap -> 1600 zeros inserted
s._spk_feed(np.ones(3200), 4800)          # overlaps 1600 already fed -> trimmed
check("samples fed == timeline length", s.spk_bypass.n == 8000, s.spk_bypass.n)
check("t_end of last feed == 0.5 s", s.spk_bypass.calls[-1][1] == 0.5, s.spk_bypass.calls[-1])

print("2. original keeps feeding while the separator starts")
s = session("starting")
check("starting: speaker path uses the original", not s._spk_use_vocals())
s._bg_sep.state = "ok"
check("running: speaker path uses vocals", s._spk_use_vocals())
s._bg_sep.state = "unavailable"
check("unavailable: back to the original", not s._spk_use_vocals())

print("3. onset alignment")
s = session()
sr = 16000
v = np.zeros(sr * 16, np.float32)
rng = np.random.default_rng(0)
v[int(11.0 * sr):int(11.1 * sr)] = 0.01 * rng.standard_normal(int(0.1 * sr))      # short -40 dB burst
v[int(14.75 * sr):int(16 * sr)] = 0.3 * rng.standard_normal(int(1.25 * sr))       # speech
s._on_bg_vocals(0.0, v)
o = s._speech_onset(8.0, 16.0, wait=0.0)
check("onset = speech (14.75 s), not the burst (11.0 s)", 14.5 < o < 14.8, o)
check("no speech in the segment ⇒ unchanged", s._speech_onset(0.0, 8.0, wait=0.0) == 0.0)

print("4. dub_shift is non-blocking")
s = session()
s.t0 = time.perf_counter()
s._onset_pending.append(("d1", 8.0, 16.0, s.t0 + 8.0 + 20.0))
t0 = time.perf_counter()
out = s._check_onsets()
check("no vocals yet ⇒ nothing sent, kept pending, returns at once",
      out == [] and len(s._onset_pending) == 1 and time.perf_counter() - t0 < 0.5)
s._on_bg_vocals(0.0, v)
out = s._check_onsets()
check("vocals arrived ⇒ dub_shift with the onset", len(out) == 1 and out[0]["type"] == "dub_shift"
      and out[0]["id"] == "d1" and 14.5 < out[0]["t_start"] < 14.8, out)
s._onset_pending.append(("d2", 8.0, 16.0, time.perf_counter() - 1.0))       # play time already passed
check("too late ⇒ dropped, no message", s._check_onsets() == [] and len(s._onset_pending) == 0)

print("5. spk_engine frame axis")
rt = types.ModuleType("asr052_spk_runtime")
rt.FPS, rt.WIN_N = 58.6, 80000
sys.modules.setdefault("asr052_spk_runtime", rt)
rt = sys.modules["asr052_spk_runtime"]
from ext import spk_engine as SE  # noqa: E402
eng = SE.SpkEngine.__new__(SE.SpkEngine)
eng._pending, eng._pending_len, eng._seg_frames, eng._seg_block_start = [], 0, [], 0
eng._seg_stride_samples = int(round(SE.STRIDE_MS / 1000.0 * SE.SR))
eng._block_min = rt.WIN_N + eng._seg_stride_samples
eng.seg_infer_sec, eng.n_seg_infer = 0.0, 0
eng._ensure_seg = lambda: True
eng._infer_seg = lambda a: [(np.zeros(1), np.zeros(1))] * int(np.ceil(len(a) / SE.SR * rt.FPS))
total = 0
for _ in range(600 * 10):                  # 600 s in 100 ms pieces
    a = np.zeros(1600, np.float32)
    eng._pending.append(a)
    eng._pending_len += a.size
    total += a.size
    eng._advance_seg()
consumed = eng._seg_block_start
check("frames == round(consumed·FPS/SR) (no overlap double-count)",
      len(eng._seg_frames) == int(round(consumed / SE.SR * rt.FPS)),
      (len(eng._seg_frames), int(round(consumed / SE.SR * rt.FPS))))
check("consumed covers the session minus one window", total - consumed <= eng._block_min, (total, consumed))

print("6. segmentation IR variant follows the window, with app/asr_spk importable (ASR-096 B)")
import shutil  # noqa: E402
import tempfile  # noqa: E402
from ext import speaker_bypass as SB  # noqa: E402
tmp = tempfile.mkdtemp()
prev = os.environ.pop("EXT_SPK_SEG_IR", None)
try:
    spk = os.path.join(tmp, "app", "asr_spk")
    os.makedirs(spk)
    for sub in ("fp16", "fp16-w5"):
        os.makedirs(os.path.join(tmp, "models", "spk", "pyannote_seg_3_0", sub))
    with open(os.path.join(spk, "asr_spk_window.py"), "w") as f:
        f.write("def seg_ir_subdir_for(w):\n    return 'fp16-w5' if abs(w - 5.0) < 1e-6 else 'fp16'\n")
    sys.modules.pop("asr_spk_window", None)
    rt.WIN_S = 5.0
    sys.path.insert(0, spk)
    got = SB._find_seg_for_window(tmp)
    check("window 5 s ⇒ pyannote fp16-w5", got.replace("\\", "/").endswith("pyannote_seg_3_0/fp16-w5"), got)
    src = open(SB.__file__, encoding="utf-8").read()
    i_ins = src.find("os.sys.path.insert(0, d)\n        seg_ir, wes_ir = self._asset_paths()")
    check("_load() puts app/asr_spk on sys.path before _asset_paths()", i_ins > 0)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    if prev is not None:
        os.environ["EXT_SPK_SEG_IR"] = prev

ok = all(RES)
print("RESULT:", "PASS" if ok else "FAIL", f"({sum(RES)}/{len(RES)})")
sys.exit(0 if ok else 1)
