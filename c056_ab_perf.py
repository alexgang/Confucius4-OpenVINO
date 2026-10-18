"""c056_ab_perf.py — C-056: int4lmfp16 vs int4lmhead 性能 A/B（3 轮交替取中位）

C-056 的 what-if 变体 `ov-int4-lmhead-past`（lm_head 也 INT4、tie 保留，846 MiB）
与交付的 `ov-int4-lmfp16-past`（1440 MiB）op 数几乎一样，只差权重体积。
按 C-054 的方法学教训，用交替重复 + 中位数比较，不用单发。

用法：.venv python c056_ab_perf.py
输出：reports/c056_ab_perf.json
"""
import os
import sys
import time
import json
import statistics as st

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import streaming_transcribe, finish_streaming_transcribe

ENC = 'models/ov-encoder-segment-reviewer'
DECS = [('int4lmfp16', 'models/ov-int4-lmfp16-past'),
        ('int4lmhead', 'models/ov-int4-lmhead-past')]
WAV = r'C:\Users\Trekker-PTL\confucius4-r2t2\test.wav'
CHUNK_MS = 640.0
REPS = 3


def run_once(dec_dir, audio):
    backend = SegmentEncoderOVBackend(
        encoder_dir=ENC, decoder_dir=dec_dir, device='GPU.0',
        precision='f16', strict_intel=True)
    chunk_samples = int(round(CHUNK_MS * 16000 / 1000))
    ws = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_MS / 1000.0)
    streaming_transcribe(backend, audio[:chunk_samples * 2], ws,
                         max_new_tokens=32, adaptive_budget=True)
    finish_streaming_transcribe(backend, ws, max_new_tokens=32)

    state = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_MS / 1000.0)
    tots = []
    for s in range(0, len(audio), chunk_samples):
        t0 = time.perf_counter()
        streaming_transcribe(backend, audio[s:s + chunk_samples], state,
                             max_new_tokens=32, adaptive_budget=True)
        tots.append((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    finish_streaming_transcribe(backend, state, max_new_tokens=32)
    flush = (time.perf_counter() - t0) * 1000
    del backend
    return tots, flush


def main():
    audio, sr = sf.read(WAV, dtype='float32')
    assert sr == 16000
    if audio.ndim > 1:
        audio = audio[:, 0]
    print(f'[c056-ab] audio {len(audio)/sr:.2f}s  chunk={CHUNK_MS}ms  reps={REPS}',
          flush=True)

    runs = {tag: [] for tag, _ in DECS}
    flushs = {tag: [] for tag, _ in DECS}
    for rep in range(REPS):
        for tag, dec in DECS:   # 交替跑
            tots, flush = run_once(dec, audio)
            runs[tag].append(tots)
            flushs[tag].append(flush)
            print(f'  rep{rep} {tag:12s}: 每块均值 {st.mean(tots):7.1f} ms  '
                  f'flush {flush:6.1f}', flush=True)

    med = {}
    for tag, _ in DECS:
        per_chunk_means = [st.mean(t) for t in runs[tag]]
        med[tag] = {
            'per_chunk_median': st.median(per_chunk_means),
            'per_chunk_all': [st.mean(t) for t in runs[tag]],
            'flush_median': st.median(flushs[tag]),
        }
    a, b = med['int4lmfp16'], med['int4lmhead']
    print('\n=== 汇总（每块中位，跨 %d 次交替）===' % REPS)
    for tag, _ in DECS:
        m = med[tag]
        print(f'{tag:12s} 每块中位 {m["per_chunk_median"]:7.1f} ms  '
              f'flush 中位 {m["flush_median"]:7.1f} ms  '
              f'（各轮 {[f"{v:.0f}" for v in m["per_chunk_all"]]}）')
    d = 100 * (b['per_chunk_median'] / a['per_chunk_median'] - 1)
    print(f'\nint4lmhead 相对 int4lmfp16：每块 {d:+.1f}%')

    out = {'reps': REPS, 'chunk_ms': CHUNK_MS, 'medians': med,
           'delta_pct': round(d, 2)}
    os.makedirs('reports', exist_ok=True)
    with open('reports/c056_ab_perf.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('saved -> reports/c056_ab_perf.json')


if __name__ == '__main__':
    main()
