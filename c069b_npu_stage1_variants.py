# C-066 阶段 1 可选项：INT8 对称权重 Encoder 变体上 NPU
# reviewer：「可选：INT8 对称权重变体（NPU 对它更友好）」
# 同时把 FP16 作为对照，判断 NPU 支持 FP16 是否有精度损失。
import os
os.environ['USE_TORCH'] = '0'
os.environ['USE_TF'] = '0'
os.environ['USE_FLAX'] = '0'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import time
import numpy as np
import openvino as ov
import soundfile as sf
from transformers import WhisperFeatureExtractor

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, 'reports/npu_cache')
OUT = os.path.join(ROOT, 'reports/c069b_npu_encoder_variants.json')

VARIANTS = {
    'fp16': 'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml',
    'int8sym': 'models/ov-encoder-segment-reviewer-int8sym/openvino_encoder_model.xml',
    'int4': 'models/ov-encoder-segment-reviewer-int4/openvino_encoder_model.xml',
}
LENS = (0.64, 4, 7.68, 8, 9.6, 12.8, 16, 20, 23.9)


def aftercnn_len(n):
    leave = n % 100
    feat = (leave - 1) // 2 + 1
    return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // 100) * 13


def total_aftercnn_len(frames):
    if frames <= 0:
        return 0
    n_full = frames // 100
    leave = frames - n_full * 100
    return n_full * 13 if leave == 0 else n_full * 13 + aftercnn_len(leave)


def freeze(m):
    """冻结全部动态输入（NPU 要求静态）。2026.4 reshape 原地修改返回 None。"""
    names = [i.get_any_name() for i in m.inputs]
    smap = {}
    for idx, nm in enumerate(names):
        smap[m.input(idx)] = (ov.PartialShape([1, 128, 2400])
                              if idx == 0 else ov.PartialShape([1]))
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
        clip = seg[: int(sec * sr)]
        o = fe([clip], sampling_rate=16000, return_tensors='np',
               padding='do_not_pad', truncation=False, return_attention_mask=True)
        mel = o['input_features'][0]
        mel = mel[:, : int(o['attention_mask'][0].sum())]
        assert mel.shape[1] <= 2400
        x = np.zeros((1, 128, 2400), dtype=np.float32)
        x[0, :, : mel.shape[1]] = mel
        return [x, np.array([total_aftercnn_len(mel.shape[1])], dtype=np.int32)]

    # GPU FP16 作为参考基准（reviewer 的判据是 NPU vs GPU）
    ref_cm = core.compile_model(
        freeze(core.read_model(os.path.join(ROOT, VARIANTS['fp16']))), 'GPU')

    res = {'note': ('C-066 阶段 1 可选项：三种权重精度上 NPU，参考基准是 '
                    'GPU FP16。判据 mean>=0.999 / min>=0.99。'),
           'lens_sec': list(LENS), 'variants': {}}

    for tag, rel in VARIANTS.items():
        rec = {'ir': rel}
        try:
            mdl = freeze(core.read_model(os.path.join(ROOT, rel)))
            rec['frozen_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                                   for i in mdl.inputs]
            t0 = time.time()
            cm = core.compile_model(mdl, 'NPU', {'CACHE_DIR': CACHE})
            rec['npu_compile_ok'] = True
            rec['npu_compile_seconds'] = round(time.time() - t0, 1)
        except Exception as e:
            rec['npu_compile_ok'] = False
            rec['error'] = f'{type(e).__name__}: {e}'[:3000]
            res['variants'][tag] = rec
            print(f'{tag}: NPU compile FAILED — {str(e)[:150]}')
            continue

        rows = []
        for sec in LENS:
            feeds = build(sec)
            a = ref_cm(feeds)[0].reshape(-1)
            b = cm(feeds)[0].reshape(-1)
            cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
            rel_err = float(np.abs(a - b).max() / (np.abs(a).max() + 1e-12))
            rows.append({'sec': sec, 'cosine': round(cos, 6),
                         'max_rel_diff': round(rel_err, 6)})
            print(f'  {tag} {sec:5.2f}s cos={cos:.6f} rel={rel_err:.2e}')
        cs = [r['cosine'] for r in rows]
        rec['rows'] = rows
        rec['cosine_mean'] = round(float(np.mean(cs)), 6)
        rec['cosine_min'] = round(float(np.min(cs)), 6)
        rec['pass'] = bool(np.mean(cs) >= 0.999 and np.min(cs) >= 0.99)

        # 延迟：预热后 >=20 次中位数
        feeds = build(12.0)
        for _ in range(5):
            cm(feeds)
        ts = []
        for _ in range(20):
            t0 = time.time()
            cm(feeds)
            ts.append((time.time() - t0) * 1000)
        ts.sort()
        rec['npu_median_ms'] = round(ts[len(ts) // 2], 2)
        res['variants'][tag] = rec
        print(f'{tag}: mean={rec["cosine_mean"]} min={rec["cosine_min"]} '
              f'pass={rec["pass"]} npu={rec["npu_median_ms"]}ms')

    # GPU FP16 参考延迟
    feeds = build(12.0)
    for _ in range(5):
        ref_cm(feeds)
    ts = []
    for _ in range(20):
        t0 = time.time()
        ref_cm(feeds)
        ts.append((time.time() - t0) * 1000)
    ts.sort()
    res['gpu_fp16_reference_median_ms'] = round(ts[len(ts) // 2], 2)
    print('GPU FP16 reference:', res['gpu_fp16_reference_median_ms'], 'ms')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
