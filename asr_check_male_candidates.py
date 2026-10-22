"""asr_check_male_candidates.py — 用本项目现成的 OV ASR 复核候选男声段。

目的：C-104 [BLOCKING] 要求预设 B 是「非名人的男声朗读」样例。
我们从自己的会议录音里挑了 6 段候选男声（golden/voices/male_candidates/*.wav），
用 ASR 转写确认：
  1. 内容是清晰可辨的朗读（不是音乐/噪声/多人重叠）；
  2. 段落里是**单一**说话人（转写内容连贯、不跳话题）；
  3. 语言是英文（会议录音 <redacted> 是英文会议）。

同时对 3 个 Amphion 候选做同样复核，作为对照。
"""
import json
import os
import sys
import time

import numpy as np
import soundfile as sf

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.path.insert(0, '.')

from backends import OVBackend, SAMPLE_RATE  # noqa: E402

TTS_ROOT = r"C:\Users\Trekker-PTL\confucius4-tts"
CAND_DIR = os.path.join(TTS_ROOT, "golden", "voices", "male_candidates")
AMPHION = os.path.join(TTS_ROOT, "external", "Confucius4-TTS", "external", "Amphion")

EXTRA = [
    os.path.join(AMPHION, "models", "vc", "vevo", "wav", "arabic_male.wav"),
    os.path.join(AMPHION, "models", "tts", "maskgct", "wav", "prompt.wav"),
]


def main():
    print(f"[asr] loading OVBackend models/ov-int8-past ...", flush=True)
    t0 = time.perf_counter()
    b = OVBackend(model_dir="models/ov-int8-past", device="GPU.0")
    print(f"[asr] loaded in {time.perf_counter()-t0:.1f}s", flush=True)

    files = sorted([os.path.join(CAND_DIR, f) for f in os.listdir(CAND_DIR) if f.endswith(".wav")])
    files += [f for f in EXTRA if os.path.exists(f)]

    rows = []
    for p in files:
        audio, sr = sf.read(p, dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if sr != SAMPLE_RATE:
            n = int(len(audio) * SAMPLE_RATE / sr)
            audio = np.interp(np.linspace(0, len(audio), n), np.arange(len(audio)), audio).astype(np.float32)
        t1 = time.perf_counter()
        try:
            ehs, n_real, N_audio = b.encode_audio(audio)
            out_ids = b.greedy_decode_with_prefix(ehs, prefix_ids=[], max_new_tokens=256)
            text = b.tokenizer.decode(out_ids, skip_special_tokens=True)
            from streaming_asr import parse_asr_output
            lang, txt = parse_asr_output(text, user_language=None)
            if not txt:
                txt = text
        except Exception as e:
            txt = f"<ERROR {e}>"
        r = dict(file=os.path.relpath(p, TTS_ROOT).replace("\\", "/"),
                 dur=round(len(audio) / SAMPLE_RATE, 2),
                 asr_s=round(time.perf_counter() - t1, 2), text=txt)
        rows.append(r)
        print(json.dumps(r, ensure_ascii=False), flush=True)

    out = os.path.join(TTS_ROOT, "results", "male_candidates_asr.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n[done] {out}")


if __name__ == "__main__":
    main()
