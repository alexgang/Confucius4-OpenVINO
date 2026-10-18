# C-066 阶段 3 · 替代路径：缩短重算序列，救回无 cache 方案
#
# 前提修正：C-069 探测确认 **主线 2026.4.1 的 NPU 没有任何 NPUW 属性**
# （SUPPORTED_PROPERTIES 里 NPUW 过滤后 = 0 个），所以「NPUW 静态 KV 分块缓存」
# 这条路在目标机上**根本不可用** —— 与 C-068 阶段 0 的结论一致。
#
# 那还剩什么可做？无 cache 方案的成本 = O(序列长度)。
# 而序列长度 = 模板 + 音频 token + 已生成 token，而**音频 token 占大头**。
# 所以：能否减少「每步都要重算」的部分？
#
# 本脚本实测「序列长度 → 单次延迟」曲线，算出：
#   1) 缩到多短才可能追平 RTF 0.582
#   2) 真实音频段的音频 token 数是多少（决定可行性）
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
OUT = os.path.join(ROOT, 'reports/c069j_npu_seq_len_sweep.json')
H = 2048
VOCAB = 151936

# 探针序列长度：覆盖从极短到 1024
PROBE_LENS = (64, 128, 192, 256, 384, 512, 768, 1024)


def median_ms(fn, warmup=3, reps=8):
    for _ in range(warmup):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000)
    ts.sort()
    return round(ts[len(ts) // 2], 2)


def main():
    core = ov.Core()
    core.set_property({'CACHE_DIR': CACHE})
    res = {'note': ('NPUW 在主线 2026.4.1 不可用（无任何 NPUW 属性），'
                    '故改测「缩短重算序列」这条路：实测延迟-长度曲线并外推可行性。'),
           'npuw_available': False,
           'probe_lens': list(PROBE_LENS),
           'baseline': {
               'stateful_per_token_ms': 30.25,
               'stateful_rtf': 0.582,
               'planb_512_npu_ms': 181.58,
           }}

    rng = np.random.default_rng(0)
    for tag, dev, props in (
        ('gpu', 'GPU', {'PERFORMANCE_HINT': 'LATENCY',
                        'INFERENCE_PRECISION_HINT': 'f16'}),
        ('npu', 'NPU', {'CACHE_DIR': CACHE}),
    ):
        curve = []
        for L in PROBE_LENS:
            x = (rng.standard_normal((1, L, H)) * 0.02).astype(np.float32)
            try:
                # ⚠️ CompiledModel 没有 get_model()；必须重新 read_model 再 reshape。
                # 每个 L 都是一张独立静态图（NPU 要求静态形状）。
                m = core.read_model(os.path.join(
                    ROOT, 'models/ov-dec-embed-fp16/openvino_decoder_model.xml'))
                ret = m.reshape({m.input(0): ov.PartialShape([1, L, H])})
                m = ret if ret is not None else m
                cmL = core.compile_model(m, dev, props)
                ms = median_ms(lambda: cmL([x]))
                curve.append({'len': L, 'ms': ms})
                print(f'  {tag} L={L:5d}: {ms:7.2f} ms', flush=True)
            except Exception as e:
                curve.append({'len': L, 'error': str(e)[:200]})
                print(f'  {tag} L={L:5d}: FAIL {str(e)[:100]}', flush=True)
        res[f'curve_{tag}'] = curve

    # 线性拟合：ms ≈ a + b*L（只取成功点）
    import statistics
    fits = {}
    for tag in ('gpu', 'npu'):
        pts = [(p['len'], p['ms']) for p in res.get(f'curve_{tag}', [])
               if 'ms' in p]
        if len(pts) >= 2:
            xs = np.array([p[0] for p in pts], dtype=float)
            ys = np.array([p[1] for p in pts], dtype=float)
            b, a = np.polyfit(xs, ys, 1)
            fits[tag] = {'intercept_ms': round(float(a), 2),
                         'per_token_us': round(float(b) * 1000, 1),
                         'n_points': len(pts)}
            print(f'\n{tag} 线性拟合: {a:.1f} ms + {b*1000:.1f} us/token')
    res['linear_fit'] = fits

    # 反解：要多短才追平 stateful 的 30.25 ms/token
    for tag, f in fits.items():
        need_ms = res['baseline']['stateful_per_token_ms']
        L_needed = (need_ms - f['intercept_ms']) / (f['per_token_us'] / 1000)
        res.setdefault('length_needed_to_match', {})[tag] = {
            'target_ms_per_token': need_ms,
            'required_seq_len': round(L_needed, 1),
            'feasible': bool(0 < L_needed <= len(PROBE_LENS)),
        }
        print(f'{tag}: 要追平 30.25 ms/token 需要序列长 {L_needed:.0f}')

    # 真实音频段的 token 预算（来自 C069_STAGE3_INTERFACE_SPEC）
    res['token_budget'] = {
        'template': 13, 'audio_max_24s': 312, 'prefix_max': 100,
        'typical_seg_16s_audio_tok': 208,   # 312 * 16.36/24
        'note': ('音频 token 是大头（典型段约 208），模板+前缀只有约 113。'
                 '即使把生成部分砍掉，序列也降不到 150 以下。'),
    }

    # 端到端估算：若用 NPU、无 cache、序列 = 音频+模板+已生成
    for tag in ('gpu', 'npu'):
        f = fits.get(tag)
        if not f:
            continue
        a = f['intercept_ms']
        b = f['per_token_us'] / 1000
        # 每段：N 个输出 token，每步序列长 = base + 已生成
        base = 13 + 208 + 100   # 321
        for n_out in (65, 130, 195):
            total = sum(a + b * (base + t) for t in range(n_out))
            est_rtf = (total / 1000) / 16.36
            res.setdefault('projection', {}).setdefault(tag, {})[str(n_out)] = {
                'per_seg_ms': round(total, 1), 'rtf': round(est_rtf, 3)}

    for tag, v in res.get('projection', {}).items():
        print(f'\n{tag} 端到端预估（每段 16.36 s）:')
        for n_out, d in v.items():
            flag = '✅' if d['rtf'] <= 1 else '❌'
            print(f'  输出 {n_out} token: RTF {d["rtf"]:.2f} {flag}')

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
