"""c087c_int4_npu_900s.py — C-087#3：在**已验证的 12–27 min 口径**上重跑
「NPU 能否跑 INT4」的三方对照。

## 为什么推翻 c087b 的 40 s 切片

c087b 在 720–760 s（40 s）上算出的参照 WER 离谱：**INT8@NPU 这个公认正常的配置
自己就报41.3%**。原因是 baseline 词表按 **500 s 大块线性插值**定位词时间
（`c026_minimax_raw.json` 只有 8 个 chunk，每块 500 s），在 40 s 窗口内
词级时间归属误差极大，method_b 全局对齐被这个误差带偏 → **短切片不能算 WER**。

12–27 min（900 s）口径是本项目反复验证过的：C-085 的 A=5.961% / cleanie=6.679%，
C-086 的全长A=7.798%，量级一致。改用它。

## 三方对照（唯一变量 = 精度 × 设备；encoder 固定 @NPU）

| 组 | decoder IR | 设备 |
|---|---|---|
| int8_npu | `qwen3-lm-int8sym-cleanie-ov` | NPU |
| int4_npu | `qwen3-lm-int4sym-cleanie-ov` | NPU |
| int4_cpu | 同上 | CPU（RTF≈1.54，最慢，放最后） |

预期耗时（900 s 音频）：int8_npu ~12 min + int4_npu ~7 min + int4_cpu ~23 min ≈ 42 min。

输出：reports/c087_int4_npu_900s/{summary.json, transcript_*.txt}
"""
import json
import os
import sys
import threading
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
START, END = 12 * 60, 27 * 60          # 与 C-085 相同的已验证切片
CHUNK_SEC = 0.64
ENC_DIR = 'models/ov-encoder-segment-reviewer'
AUX_DIR = 'models/ov-int8-past'
OUT_DIR = 'reports/c087_int4_npu_900s'
WARMUP = [5, 12, 18]
DIRS = {
    'int8_npu': ('models/qwen3-lm-int8sym-cleanie-ov', 'NPU'),
    'int4_npu': ('models/qwen3-lm-int4sym-cleanie-ov', 'NPU'),
    'int4_cpu': ('models/qwen3-lm-int4sym-cleanie-ov', 'CPU'),
}


def agg(v):
    if not v:
        return {}
    return {'median': round(float(np.median(v)), 1),
            'mean': round(float(np.mean(v)), 2), 'n': len(v),
            'sum': round(float(np.sum(v)), 1)}


def build_backend(dec_dir, dec_device):
    import openvino as ov
    from c085a_smoke_all_npu import make_all_npu_backend
    be = make_all_npu_backend(ENC_DIR, dec_dir, aux_dir=AUX_DIR)
    if dec_device == 'NPU':
        return be
    core = ov.Core()
    core.set_property({'CACHE_DIR': './reports/npu_cache'})
    t0 = time.perf_counter()
    be.dec = core.compile_model(os.path.join(dec_dir, 'openvino_model.xml'), 'CPU')
    be.npu_compile_s = round(time.perf_counter() - t0, 1)
    return be


def run_one(name, dec_dir, dev, a):
    from seg_stream import SegmentedStreamer
    from c058q_wordcount import save_transcript

    print(f'\n=== {name}（{dec_dir}@{dev}）', flush=True)
    t0 = time.perf_counter()
    be = build_backend(dec_dir, dev)
    print(f'  backend init {time.perf_counter()-t0:.1f}s', flush=True)

    for s in WARMUP:
        SegmentedStreamer(
            be, strategy='off', chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            enable_hallucination_reset=False).run(a[:SR * s])

    pr = be.probe                     # 使用前定义（C-085 白跑两小时的教训）
    for k in pr:
        pr[k].clear()
    streamer = SegmentedStreamer(
        be, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(a, progress=True)
    wall = time.perf_counter() - t0
    tp = save_transcript(segs, f'{OUT_DIR}/transcript_{name}.txt')
    print(f'  RTF={wall/(len(a)/SR):.4f}  segs={len(segs)}  words={len(text.split())}',
          flush=True)
    print('  HEAD:', text[:260], flush=True)
    return {
        'decoder_dir': dec_dir, 'decoder_device': dev,
        'wall_s': round(wall, 2), 'rtf': round(wall / (len(a) / SR), 4),
        'n_segs': len(segs), 'n_generate_calls': len(pr['prefill_ms']),
        'words': len(text.split()), 'chars': len(text),
        'breakdown': {k: agg(pr[k]) for k in ('prefill_ms', 'decode_ms')},
        'transcript_path': tp, 'text_head': text[:600],
    }


def main():
    audio, _ = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    a = audio[SR * START:SR * END]
    os.makedirs(OUT_DIR, exist_ok=True)
    print(f'[c087c] 切片 {len(a)/SR:.1f}s（{START}–{END} s，已验证口径）', flush=True)

    rep = {'note': 'C-087「NPU 能否跑 INT4」三方对照，12–27 min 已验证口径。'
                   'c087b 的 40 s 切片作废（参照自身 WER 41.3%，baseline 词按 500 s '
                   '块插值，短窗口对齐误差过大）。encoder 固定 @NPU。',
           'slice_sec': [START, END], 'audio_sec': round(len(a) / SR, 2),
           'enc_device': 'NPU（固定）', 'runs': {}}

    for name, (dec_dir, dev) in DIRS.items():
        rep['runs'][name] = run_one(name, dec_dir, dev, a)
        with open(f'{OUT_DIR}/summary_partial.json', 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)

    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', f'{OUT_DIR}/summary.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
