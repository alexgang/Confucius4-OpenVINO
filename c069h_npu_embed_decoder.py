# C-066 阶段 3 · 方案 B：inputs_embeds 解码器上 NPU（编译 + **实跑**）
#
# ⚠️ C-069e/f 的教训：compile_model 返回成功是**假阳性**，必须实跑一次。
# 本脚本对每个设备都做「编译 → 真实推理 → 与 GPU 对比 cosine」。
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

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, 'reports/npu_cache')
OUT = os.path.join(ROOT, 'reports/c069h_npu_embed_decoder.json')
IR = os.path.join(ROOT, 'models/ov-dec-embed-fp16/openvino_decoder_model.xml')

L = 512
H = 2048
VOCAB = 151936

NPUW = {
    'NPU_USE_NPUW': 'YES',
    'NPUW_LLM': 'YES',
    'NPUW_LLM_MAX_PROMPT_LEN': str(L),
    'NPUW_LLM_MIN_RESPONSE_LEN': '1',
    'CACHE_DIR': CACHE,
}


def main():
    core = ov.Core()
    core.set_property({'CACHE_DIR': CACHE})
    rng = np.random.default_rng(0)
    x = (rng.standard_normal((1, L, H)) * 0.02).astype(np.float32)

    res = {'note': ('阶段 3 方案 B 实跑验证。compile 成功不等于可用，'
                    '每个设备都实跑一次并与 GPU 对比 cosine。'),
           'ir': IR, 'input_shape': [1, L, H], 'output_shape': [1, 1, VOCAB],
           'devices': {}}

    ref = None
    for tag, dev, props in (
        ('gpu_fp16', 'GPU', {'PERFORMANCE_HINT': 'LATENCY',
                             'INFERENCE_PRECISION_HINT': 'f16'}),
        ('npu_plain', 'NPU', {'CACHE_DIR': CACHE}),
        ('npu_npuw', 'NPU', NPUW),
        ('hetero', 'HETERO:NPU,GPU', {'CACHE_DIR': CACHE}),
    ):
        rec = {}
        cm = None
        t0 = time.time()
        try:
            cm = core.compile_model(IR, dev, props)
            rec['compile_ok'] = True
            rec['compile_seconds'] = round(time.time() - t0, 1)
            rec['inputs'] = [(i.get_any_name(), str(i.get_partial_shape()))
                             for i in cm.inputs]
        except Exception as e:
            rec['compile_ok'] = False
            rec['compile_seconds'] = round(time.time() - t0, 1)
            rec['compile_error'] = str(e)[:3000]
            tail = ' | '.join(l.strip() for l in str(e).strip().splitlines()
                              if l.strip())[-260:]
            print(f'[{tag}] compile FAILED — {tail}', flush=True)
            res['devices'][tag] = rec
            continue

        # 实跑（关键）
        try:
            for _ in range(2):
                cm([x])
            t0 = time.time()
            out = cm([x])[0]
            arr = np.asarray(out).reshape(-1)
            rec['infer_ok'] = True
            rec['infer_seconds'] = round((time.time() - t0) * 1000, 1)
            rec['output_len'] = int(arr.size)
            rec['argmax'] = int(np.argmax(arr))
            if ref is None:
                ref = arr
                rec['role'] = 'reference'
            else:
                cos = float(np.dot(ref, arr) /
                            (np.linalg.norm(ref) * np.linalg.norm(arr)))
                rec['cosine_vs_gpu'] = round(cos, 6)
                rec['argmax_match'] = bool(np.argmax(ref) == np.argmax(arr))
            print(f"[{tag}] OK  {rec['infer_seconds']}ms  "
                  f"len={rec['output_len']} "
                  f"cos={rec.get('cosine_vs_gpu', 'ref')} "
                  f"argmax_match={rec.get('argmax_match')}", flush=True)
        except Exception as e:
            rec['infer_ok'] = False
            msg = str(e)
            rec['infer_error'] = msg[:4000]
            rec['infer_error_tail'] = ' | '.join(
                l.strip() for l in msg.strip().splitlines()
                if l.strip())[-400:]
            print(f"[{tag}] INFER FAILED — {rec['infer_error_tail']}",
                  flush=True)
        res['devices'][tag] = rec

    # GPU 延迟基准
    try:
        cm = core.compile_model(IR, 'GPU', {'PERFORMANCE_HINT': 'LATENCY',
                                            'INFERENCE_PRECISION_HINT': 'f16'})
        for _ in range(5):
            cm([x])
        ts = []
        for _ in range(20):
            t0 = time.perf_counter()
            cm([x])
            ts.append((time.perf_counter() - t0) * 1000)
        ts.sort()
        res['gpu_median_ms'] = round(ts[len(ts) // 2], 2)
        print('GPU median:', res['gpu_median_ms'], 'ms')
    except Exception as e:
        res['gpu_latency_error'] = str(e)[:1500]

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)
    ok = [k for k, v in res['devices'].items() if v.get('infer_ok')]
    print('NPU-capable devices that ACTUALLY RAN:', ok)


if __name__ == '__main__':
    main()
