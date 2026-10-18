# C-066 阶段 1/2 延迟复核：NPU vs GPU 必须统一基准重测
#
# 为什么重测：两轮独立测量给出**相反**结论 ——
#   阶段 1 (reviewer 双输入 encoder, 12 s 段): NPU 35.8 ms  vs GPU 49.4 ms  → NPU 快 1.38×
#   生产前置 (单输入 encoder,      12 s 段): NPU 47.6 ms  vs GPU 35.2 ms  → NPU 慢 0.74×
# 两者模型规模几乎相同（1938 vs 2075 ops），差异很可能来自测量口径
# （GPU 精度提示 / 是否复用 CACHE / 首次调用残留），不是设备能力差异。
# 本脚本：同一进程内、同一输入、ABBA 顺序、GPU 用生产精度设置，多轮。
import os
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
os.environ['USE_FLAX'] = '0'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import time
import statistics
import numpy as np
import openvino as ov
import soundfile as sf
from transformers import WhisperFeatureExtractor

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, 'reports/npu_cache')
OUT = os.path.join(ROOT, 'reports/c069d_npu_latency_abba.json')

IR = {
    'prod': 'models/ov-fp16-past/openvino_encoder_model.xml',
    'reviewer': 'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml',
}
GPU_PROP = {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f16'}
SECS = (12.0, 20.0)


def freeze(m, n_in):
    smap = {m.input(0): ov.PartialShape([1, 128, 2400])}
    if n_in > 1:
        smap[m.input(1)] = ov.PartialShape([1])
    ret = m.reshape(smap)
    return ret if ret is not None else m


def main():
    core = ov.Core()
    core.set_property({'CACHE_DIR': CACHE})
    fe = WhisperFeatureExtractor.from_pretrained(os.path.join(ROOT, 'models/hf'))
    audio, sr = sf.read(os.path.join(ROOT, 'test_audio/<redacted>.wav'),
                        dtype='float32')
    seg = audio[2812 * sr: 2812 * sr + int(24.0 * sr)]

    def build(sec):
        o = fe([seg[: int(sec * sr)]], sampling_rate=16000, return_tensors='np',
               padding='do_not_pad', truncation=False, return_attention_mask=True)
        mel = o['input_features'][0]
        mel = mel[:, : int(o['attention_mask'][0].sum())]
        x = np.zeros((1, 128, 2400), dtype=np.float32)
        x[0, :, : mel.shape[1]] = mel
        return [x]

    def aftercnn_len(n):
        leave = n % 100
        feat = (leave - 1) // 2 + 1
        return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // 100) * 13

    def total_aftercnn_len(frames):
        if frames <= 0:
            return 0
        n_full = frames // 100
        leave = frames - n_full * 100
        return n_full * 13 if leave == 0 else n_full * 13 + aftercnn_len(frames)

    res = {'note': ('统一基准重测：同进程、同输入、ABBA 顺序、GPU 用生产精度设置 '
                    '(PERFORMANCE_HINT=LATENCY, INFERENCE_PRECISION_HINT=f16)。'
                    '用于裁定前两轮互相矛盾的延迟结论。'),
           'gpu_prop': GPU_PROP, 'warmup': 5, 'reps': 20, 'rounds': 3,
           'results': {}}

    for tag, rel in IR.items():
        mdl = freeze(core.read_model(os.path.join(ROOT, rel)),
                     2 if tag == 'reviewer' else 1)
        n_in = 1 if tag == 'prod' else 2
        gpu = core.compile_model(mdl, 'GPU', GPU_PROP)
        npu = core.compile_model(mdl, 'NPU', {'CACHE_DIR': CACHE})

        for sec in SECS:
            feeds = build(sec)
            if n_in > 1:
                # 双输入版需要 n_valid：按 c069 阶段 1 的同一口径从 mel 帧数推
                nz = int(np.abs(feeds[0][0]).sum(axis=0).nonzero()[0].max()) + 1 \
                    if feeds[0][0].any() else 2400
                feeds = feeds + [np.array([total_aftercnn_len(nz)],
                                          dtype=np.int32)]

            # ABBA 顺序：G N N G G N N G ... 消除热启动偏差
            samples = {'gpu': [], 'npu': []}
            for cm_key, cm in (('gpu', gpu), ('npu', npu)):
                for _ in range(5):
                    cm(feeds)
            for r in range(3):
                order = ['gpu', 'npu', 'npu', 'gpu'] if r % 2 == 0 else \
                        ['npu', 'gpu', 'gpu', 'npu']
                for key in order:
                    ts = []
                    for _ in range(20):
                        t0 = time.perf_counter()
                        cm = gpu if key == 'gpu' else npu
                        cm(feeds)
                        ts.append((time.perf_counter() - t0) * 1000)
                    samples[key].append(statistics.median(ts))

            def agg(v):
                v = sorted(v)
                return {'rounds': [round(x, 2) for x in v],
                        'median': round(statistics.median(v), 2),
                        'min': round(v[0], 2), 'max': round(v[-1], 2),
                        'spread_pct': round((v[-1] - v[0]) /
                                           statistics.median(v) * 100, 1)}

            g, n = agg(samples['gpu']), agg(samples['npu'])
            key = f'{tag}@{sec:g}s'
            res['results'][key] = {
                'gpu': g, 'npu': n,
                'npu_over_gpu': round(n['median'] / max(g['median'], 1e-9), 3),
                'npu_faster': bool(n['median'] < g['median']),
            }
            print(f"{key:16s} GPU {g['median']:6.2f}ms  NPU {n['median']:6.2f}ms  "
                  f"ratio {n['median']/g['median']:.3f}  "
                  f"spread G{g['spread_pct']}%/N{n['spread_pct']}%")

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
