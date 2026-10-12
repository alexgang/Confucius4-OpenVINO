"""cuda_slice_segments.py — C-020 准备：按 reports/spe_61min_segments.json 切 226 个 wav

使用同一套 VAD 切段，确保 OV 和 CUDA 用相同的切分（排除切段差异）。
"""
import os, json
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf

WAV_IN = 'test_audio/260902_SPE_audio.wav'
SEG_JSON = 'reports/spe_61min_segments.json'
OUT_DIR = 'reports/seg_wavs'

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    audio, sr = sf.read(WAV_IN)
    audio = audio.astype(np.float32)
    assert sr == 16000, f"sample rate {sr} != 16000"
    print(f'[slice] audio: {len(audio)/sr:.2f}s', flush=True)
    with open(SEG_JSON, 'r', encoding='utf-8') as f:
        segs = json.load(f)['segments']
    print(f'[slice] {len(segs)} segments', flush=True)
    for s in segs:
        idx = s['seg_idx']
        start = int(s['start_s'] * sr)
        end = int(s['end_s'] * sr)
        seg_audio = audio[start:end]
        if seg_audio.shape[0] == 0:
            continue
        out_path = f'{OUT_DIR}/seg_{idx:03d}.wav'
        sf.write(out_path, seg_audio, sr, subtype='PCM_16')
    print(f'[slice] done → {OUT_DIR}/seg_NNN.wav', flush=True)

if __name__ == '__main__':
    main()
