"""test_ext0420_clone_gender.py — v0.4.20 clone voice selection (no models, no browser).

  1. f0_median / gender_of on synthetic voices (male 98/125 Hz, female 232/235 Hz incl. a strong 2nd harmonic),
     noise ⇒ None, ambiguous 170 Hz ⇒ None
  2. gender_gate: female sentence + male voice ⇒ the registered female voice; same gender ⇒ unchanged;
     ambiguous sentence ⇒ unchanged; no registered voice of that gender ⇒ clone from this sentence (self_ref)
  3. _nearest_voice: picks the registered voice with the highest embedding similarity, respects min_sim
Run: python tests/test_ext0420_clone_gender.py   (RESULT: PASS / FAIL)
"""
import os
import sys
import tempfile
import threading
import wave

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ext import clone_voice as CV  # noqa: E402

SR = 16000
RES = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok or not detail else f" — {detail}"))


def voice(f0, amps, sec=2.0, seed=0):
    t = np.arange(int(sec * SR)) / SR
    vib = 1 + 0.02 * np.sin(2 * np.pi * 5 * t)
    ph = 2 * np.pi * np.cumsum(f0 * vib) / SR
    x = sum(a * np.sin((k + 1) * ph) for k, a in enumerate(amps)) * 0.2
    return (x + 0.003 * np.random.default_rng(seed).standard_normal(x.size)).astype(np.float32)


def write_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


print("1. pitch / gender")
for name, f0, amps, want in [("male 98", 95, [1, .8, .6, .5], "m"), ("male 125", 120, [1, .6, .4, .3], "m"),
                             ("female 232", 220, [1, .5, .3], "f"), ("female 235, strong 2nd harmonic", 230, [.4, 1, .5], "f"),
                             ("ambiguous 170", 168, [1, .5, .3], None)]:
    f = CV.f0_median(voice(f0, amps))
    check(f"{name}: f0={f and round(f)} ⇒ {CV.gender_of(f)}", CV.gender_of(f) == want)
check("noise ⇒ no pitch", CV.f0_median(np.random.default_rng(1).standard_normal(SR).astype(np.float32) * 0.1) is None)

print("2. gender gate")
tmp = tempfile.mkdtemp()
male_ref, female_ref = os.path.join(tmp, "S1_1.wav"), os.path.join(tmp, "S2_2.wav")
write_wav(male_ref, voice(120, [1, .6, .4, .3], 3.0, 2))
write_wav(female_ref, voice(230, [1, .5, .3], 3.0, 3))


def manager(paths):
    m = CV.CloneVoices.__new__(CV.CloneVoices)
    m._lock = threading.Lock()
    m._buf, m._buf_t0 = np.zeros(0, np.float32), 0.0
    m._span, m._seg_pcm, m._reasons = {}, {}, {}
    m.paths = dict(paths)
    m.dir = tmp
    m._log = lambda *_: None
    # deterministic stand-in for the WeSpeaker embedding: pitch-band energy profile (unit vector)
    def emb(pcm):
        if pcm is None or len(pcm) < SR:
            return None
        X = np.abs(np.fft.rfft(pcm[:SR]))
        v = np.array([X[i * 25:(i + 1) * 25].sum() for i in range(40)], np.float64)
        return v / (np.linalg.norm(v) + 1e-9)
    m._embed = emb
    return m


def sentence(m, seg, x):
    m.note_audio(seg, x, 0.0, len(x) / SR)


m = manager({"S1": male_ref, "S2": female_ref})
sentence(m, 1, voice(228, [1, .5, .3], 2.5, 4))
v, r = m.gender_gate(1, male_ref)
check("female sentence + male voice ⇒ registered female voice", v == female_ref and r == "gender_switch", (v, r))
v, r = m.gender_gate(1, female_ref)
check("female sentence + female voice ⇒ unchanged", v == female_ref and r is None, (v, r))
sentence(m, 2, voice(168, [1, .5, .3], 2.5, 5))
v, r = m.gender_gate(2, male_ref)
check("ambiguous sentence ⇒ unchanged", v == male_ref and r is None, (v, r))
m2 = manager({"S1": male_ref})
sentence(m2, 3, voice(232, [1, .5, .3], 2.5, 6))
v, r = m2.gender_gate(3, male_ref)
check("no female voice registered ⇒ clone from this sentence", r == "gender_selfref" and v and os.path.basename(v).startswith("self_"), (v, r))

print("3. nearest registered voice")
p, sim = m._nearest_voice(1)
check("nearest = the female reference for a female sentence", p == female_ref, (p, sim))
p, sim = m._nearest_voice(1, min_sim=1.01)
check("min_sim respected", p is None)

ok = all(RES)
print("RESULT:", "PASS" if ok else "FAIL", f"({sum(RES)}/{len(RES)})")
sys.exit(0 if ok else 1)
