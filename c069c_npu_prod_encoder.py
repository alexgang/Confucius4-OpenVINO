# C-066 阶段 2 前置：生产交付基线的 encoder 能否上 NPU
#
# 重要发现：阶段 1 测的 `ov-encoder-segment-reviewer` 是**双输入**版本
#   (input_features [?,?,?] + n_valid [?])，而**实际生产路径**
#   `OVBackend.encode_audio` 只喂 input_features，模型目录是 `models/ov-fp16-past`，
#   它的 encoder 是**单输入**版本。
# 阶段 2 要替换的是**生产那个**，所以必须单独验证它。
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
OUT = os.path.join(ROOT, 'reports/c069c_npu_prod_encoder.json')
PROD = 'models/ov-fp16-past/openvino_encoder_model.xml'
LENS = (0.64, 4, 7.68, 8, 9.6, 12.8, 16, 20, 23.9)


def total_aftercnn_len(frames):
    if frames <= 0:
        return 0

    def tail(n):
        leave = n % 100
        feat = (leave - 1) // 2 + 1
        return ((feat - 1) // 2 + 1 - 1) // 2 + 1 + (n // 100) * 13
    n_full = frames // 100
    leave = frames - n_full * 100
    return n_full * 13 if leave == 0 else n_full * 13 + tail(frames)


def main():
    core = ov.Core()
    core.set_property({'CACHE_DIR': CACHE})
    res = {'note': ('生产基线 models/ov-fp16-past 的 encoder 是单输入版本，'
                    '与阶段 1 测的双输入版本不同。本脚本验证它能否上 NPU，'
                    '这是阶段 2 的前置。'),
           'ir': PROD, 'lens_sec': list(LENS)}

    model = core.read_model(os.path.join(ROOT, PROD))
    res['input_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                          for i in model.inputs]
    res['n_inputs'] = len(model.inputs)
    print('ports:', res['input_ports'])

    # GPU 参考（生产精度设置，与 OVBackend 一致）
    gp = {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_PRECISION_HINT': 'f16'}
    ref = core.compile_model(model, 'GPU', gp)
    print('GPU compile OK')

    # 1) 原始动态直接上 NPU（记录失败原因）
    try:
        core.compile_model(model, 'NPU', {'CACHE_DIR': CACHE})
        res['raw_npu_ok'] = True
    except Exception as e:
        res['raw_npu_ok'] = False
        res['raw_npu_error'] = str(e)[:3000]
        print('raw NPU FAILED:', str(e)[-160:].strip())

    # 2) 冻结输入签名（单输入只需冻一个）
    frozen = None
    try:
        smap = {model.input(0): ov.PartialShape([1, 128, 2400])}
        ret = model.reshape(smap)
        frozen = ret if ret is not None else model
        res['reshape_returned_none'] = (ret is None)
        res['frozen_ports'] = [(i.get_any_name(), str(i.get_partial_shape()))
                               for i in frozen.inputs]
        print('frozen ports:', res['frozen_ports'])
    except Exception as e:
        res['reshape_error'] = f'{type(e).__name__}: {e}'[:800]
        print('reshape FAILED:', e)

    if frozen is None:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        return

    npu = None
    try:
        t0 = time.time()
        npu = core.compile_model(frozen, 'NPU', {'CACHE_DIR': CACHE})
        res['npu_compile_ok'] = True
        res['npu_compile_seconds'] = round(time.time() - t0, 1)
        print(f'NPU compile OK {res["npu_compile_seconds"]}s')
    except Exception as e:
        res['npu_compile_ok'] = False
        res['npu_error'] = str(e)[:3000]
        print('NPU FAILED:', str(e)[-200:].strip())

    if npu is None:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print('\nwrote', OUT)
        return

    # 3) 精度：NPU vs GPU FP16，9 长度
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
        return x

    rows = []
    for sec in LENS:
        x = build(sec)
        a = ref([x])[0].reshape(-1)
        b = npu([x])[0].reshape(-1)
        cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        rel = float(np.abs(a - b).max() / (np.abs(a).max() + 1e-12))
        rows.append({'sec': sec, 'cosine': round(cos, 6),
                     'max_rel_diff': round(rel, 6)})
        print(f'  {sec:5.2f}s cos={cos:.6f} rel={rel:.2e}')
    cs = [r['cosine'] for r in rows]
    res['cosine'] = {'rows': rows,
                     'mean': round(float(np.mean(cs)), 6),
                     'min': round(float(np.min(cs)), 6),
                     'pass': bool(np.mean(cs) >= 0.999 and np.min(cs) >= 0.99)}

    # 4) 延迟
    x = build(12.0)
    for _ in range(5):
        ref([x]); npu([x])
    lat = {}
    for tag, cm in (('gpu_fp16', ref), ('npu', npu)):
        ts = []
        for _ in range(20):
            t0 = time.time()
            cm([x])
            ts.append((time.time() - t0) * 1000)
        ts.sort()
        lat[tag] = round(ts[len(ts) // 2], 2)
    lat['speedup_gpu_over_npu'] = round(
        lat['gpu_fp16'] / max(lat['npu'], 1e-9), 3)
    res['latency_ms'] = lat
    print('latency:', json.dumps(lat))

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
