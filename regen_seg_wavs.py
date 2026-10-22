"""regen_seg_wavs.py — 按 reports/spe_61min_segments.json 重新切出 226 段 wav

seg_wavs/ 已被清理，但切段定义还在。切法与原 cuda_stream_full.py 消费的
seg_%03d.wav 命名一致，直接从 61-min 母带按 start_s/end_s 切。
"""
import os
import json
import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.abspath(__file__))
SEG_JSON = os.path.join(ROOT, 'reports', 'spe_61min_segments.json')
SRC = os.path.join(ROOT, 'test_audio', '<redacted>.wav')
OUT = os.path.join(ROOT, 'reports', 'seg_wavs')

segs = json.load(open(SEG_JSON, encoding='utf-8'))
audio, sr = sf.read(SRC, dtype='float32')
assert sr == 16000, sr
os.makedirs(OUT, exist_ok=True)
n = 0
for s in segs:
    a = max(0, int(round(s['start_s'] * sr)))
    b = min(len(audio), int(round(s['end_s'] * sr)))
    sf.write(os.path.join(OUT, f"seg_{s['seg_idx']:03d}.wav"),
             audio[a:b], sr, subtype='PCM_16')
    n += 1
print(f'wrote {n} segments -> {OUT}')
