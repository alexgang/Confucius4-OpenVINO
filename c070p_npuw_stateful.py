# C-070#2/#3：stateful+beam_idx 解码器在 NPUW 上编译 + **实跑**验收
#
# 铁律（reviewer C-070）：
#   - **编译成功不作判据，必须实跑**。这是方案 A 留下的教训：
#     方案 A 编译通过但真实推理时炸 `state descriptor is missing`。
#   - 分别报 **prefill(256/384/512)** 与 **decode 单步**，对照 GPU stateful 的
#     94 ms / 28.8 ms（C-069m 实测）。
#   - 3 小时止损：任一项比 GPU 慢 >30% 或无法实跑 → 停止并记录原因。
#
# 输出：reports/c070p_npuw_stateful.json
import os
os.environ.setdefault('USE_TORCH', '0')      # 计时子进程禁 torch
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

import json
import statistics
import time
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, 'reports/c070p_npuw_stateful.json')

HIDDEN = 2048
N_KV_HEADS = 8
HEAD_DIM = 128
MAX_LEN = 512
N_LAYERS = 28
EOS_IDS = {151643, 151645}

# GPU stateful 对照基线（C-069m 实测）
GPU_PREFILL_MS = 94.0
GPU_DECODE_MS = 28.8

info = {
    'note': 'C-070#2/#3：stateful+beam_idx 解码器在 NPUW 上编译+实跑。'
            '编译成功不作判据；必须真实 infer。分别测 prefill/decode 单步。',
    'baseline_gpu_stateful_ms': {'prefill': GPU_PREFILL_MS,
                                 'decode_1tok': GPU_DECODE_MS},
    'attempts': [],
}


def rec(name, **kw):
    info['attempts'].append({'name': name, **kw})
    print(f'--- {name}: ' + json.dumps(kw, ensure_ascii=False)[:400],
          flush=True)


def median_ms(fn, warmup=3, reps=20):
    """C-070#2 要求：≥20 次中位数。"""
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(ts), 2), [round(t, 2) for t in ts]


def make_inputs(seq_len, rng):
    """stateful 模型的**真实输入**只有 `inputs_embeds` + `beam_idx`。

    KV cache 在 `make_stateful` 之后已经变成**内部状态变量**
    （56 个 ReadValue/Assign），不再是模型输入端口。
    传 `past_key.*` 会报 `Port for tensor name past_key.0 was not found`
    —— v1 踩过这个坑。初始 cache 由图内的 ReadValue 初始化器填零。
    """
    emb = rng.standard_normal((1, seq_len, HIDDEN)).astype(np.float32) * 0.02
    return {'inputs_embeds': emb,
            'beam_idx': np.array([0], dtype=np.int32)}


def run_graph(tag, device, props, n_reps=20):
    """编译 + 实跑一张图，返回延迟与首 token。"""
    import openvino as ov
    path = os.path.join(ROOT, f'models/ov-dec-stateful-{tag}',
                        'openvino_decoder_model.xml')
    core = ov.Core()
    t0 = time.time()
    cm = core.compile_model(path, device, props)
    compile_s = round(time.time() - t0, 1)
    ir = core.compile_model(path, 'CPU')
    req = cm.create_infer_request()
    rng = np.random.default_rng(1234)

    T = 384 if tag == 'prefill' else 1
    feed = make_inputs(T, rng)

    def one():
        # 每次都从干净 cache 开始，测的是**单步成本**，
        # 否则第二次起 cache 里已写过 token，mask/写入位置语义会变。
        req.reset_state()
        return req.infer(feed)

    # ── 必须实跑：第一次 infer 若失败即为不可用 ──
    try:
        t0 = time.perf_counter()
        req.reset_state()
        req.infer(feed)
        first = round((time.perf_counter() - t0) * 1000, 2)
        real = True
        err = None
    except Exception as e:
        real = False
        err = f'{type(e).__name__}: {e}'[:2500]
        print(f'  [{tag}/{device}] REAL RUN FAILED: {err[:300]}', flush=True)

    out = {'tag': tag, 'device': device, 'compile_s': compile_s,
           'real_run': real, 'first_call_ms': first, 'error': err,
           'props': props}
    if not real:
        return out, None

    req.reset_state()
    logits = np.asarray(req.infer(feed)[0])
    out['logits_shape'] = list(logits.shape)
    out['argmax'] = int(np.argmax(logits[0, -1]))
    # 与 CPU 参考比余弦（同一份输入、同样 reset 状态）
    req_cpu = ir.create_infer_request()
    req_cpu.reset_state()
    ref = np.asarray(req_cpu.infer(feed)[0])
    a, b = logits[0, -1].reshape(-1), ref[0, -1].reshape(-1)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    out['cosine_vs_cpu'] = round(cos, 6)
    out['argmax_match_vs_cpu'] = bool(np.argmax(a) == np.argmax(b))

    med, ts = median_ms(one, reps=n_reps)
    out['median_ms'] = med
    out['n_reps'] = n_reps
    out['ms_min'], out['ms_max'] = min(ts), max(ts)
    print(f"  [{tag}/{device}] median={med} ms  cos={cos:.6f}  "
          f"argmax_match={out['argmax_match_vs_cpu']}", flush=True)
    return out, cm


def main():
    import openvino as ov
    core = ov.Core()
    devs = core.available_devices
    info['available_devices'] = devs
    print('devices:', devs, flush=True)

    NPU_PROPS_LIST = [
        ('plain_npu', {'CACHE_DIR': os.path.join(ROOT, 'ov_cache')}),
        ('npuw', {'CACHE_DIR': os.path.join(ROOT, 'ov_cache'),
                  'NPU_USE_NPUW': 'YES',
                  'NPUW_LLM': 'YES',
                  'NPUW_LLM_MAX_PROMPT_LEN': 512,
                  'NPUW_LLM_MIN_RESPONSE_LEN': 32}),
    ]

    results = {}
    for tag in ('prefill', 'decode0'):
        for pname, props in NPU_PROPS_LIST:
            key = f'{tag}@{pname}'
            try:
                out, _ = run_graph(tag, 'NPU', props)
                results[key] = out
                rec(key, **{k: v for k, v in out.items()
                            if k not in ('props',)})
            except Exception as e:
                results[key] = {'tag': tag, 'device': 'NPU',
                                'props_name': pname,
                                'error': f'{type(e).__name__}: {e}'[:1500],
                                'tb': traceback.format_exc()[-800:]}
                print(f'  [{key}] COMPILE FAILED: '
                      f'{type(e).__name__}: {str(e)[:300]}', flush=True)
                rec(key, **results[key])

    # ── GPU 对照（同一批图） ────────────────────────────────
    for tag in ('prefill', 'decode0'):
        try:
            out, _ = run_graph(tag, 'GPU',
                               {'PERFORMANCE_HINT': 'LATENCY',
                                'INFERENCE_PRECISION_HINT': 'f16'})
            results[f'{tag}@gpu'] = out
            rec(f'{tag}@gpu', median_ms=out.get('median_ms'),
                cosine_vs_cpu=out.get('cosine_vs_cpu'))
        except Exception as e:
            print(f'  [{tag}@gpu] FAILED: {e}', flush=True)

    # ── 止损判定（C-070#4） ────────────────────────────────
    def med_of(k):
        v = results.get(k, {}).get('median_ms')
        return v if isinstance(v, (int, float)) else None

    judge = {}
    for tag, base, label in (('prefill', GPU_PREFILL_MS, 'prefill'),
                             ('decode0', GPU_DECODE_MS, 'decode_1tok')):
        for pname, _ in NPU_PROPS_LIST:
            k = f'{tag}@{pname}'
            v = med_of(k)
            if v is None:
                judge[k] = {'verdict': 'FAIL_OR_UNRUN',
                            'note': '无法实跑'}
                continue
            ratio = v / base
            judge[k] = {
                'median_ms': v, 'gpu_baseline_ms': base,
                'ratio_vs_gpu': round(ratio, 3),
                'verdict': 'OK' if ratio <= 1.30 else 'SLOWER_THAN_30PCT',
            }
    info['judgement'] = judge
    info['results'] = results
    print('\n=== 止损判定 ===')
    print(json.dumps(judge, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
    finally:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print('\nwrote', LOG)
