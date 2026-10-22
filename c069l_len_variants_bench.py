# C-069l：测量多序列长度变体在 NPU/GPU 上的真实延迟，判断「缩短重算」能否救回
#
# 背景链：
#   C-069i  无 cache 方案 RTF≈3.5 不可交付
#   C-069j  发现 reshape 改不了序列长度（RoPE position_ids 图内固化）
#   C-069k  改为导出期参数化，256/320/384/512 四个变体已导出
#   本脚本  实测四者的延迟曲线 + 与 stateful 基线对比，给出可行性判定
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
OUT = os.path.join(ROOT, 'reports/c069l_len_variants_bench.json')

H = 2048
LENS = (256, 320, 384, 512)
STATEFUL_PER_TOKEN = 30.25     # C-069i 实测
STATEFUL_RTF = 0.582           # C-062 ABBA 基线
AVG_SEG_SEC = 16.36
AVG_OUT_TOK = 65


def median_ms(fn, warmup=3, reps=10):
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
    rng = np.random.default_rng(0)

    res = {
        'note': ('序列长度变体的真实延迟曲线。变体在导出期参数化（图内 RoPE '
                 'position_ids 正确固化），因此每个长度都是独立静态图。'),
        'baseline': {'stateful_per_token_ms': STATEFUL_PER_TOKEN,
                     'stateful_rtf': STATEFUL_RTF,
                     'avg_out_tokens': AVG_OUT_TOK,
                     'avg_seg_sec': AVG_SEG_SEC},
        'variants': {},
    }

    for L in LENS:
        ir = os.path.join(ROOT, f'models/ov-dec-embed-L{L}'
                                 '/openvino_decoder_model.xml')
        rec = {'len': L}
        for tag, dev, props in (
            ('gpu', 'GPU', {'PERFORMANCE_HINT': 'LATENCY',
                            'INFERENCE_PRECISION_HINT': 'f16'}),
            ('npu', 'NPU', {'CACHE_DIR': CACHE}),
        ):
            try:
                cm = core.compile_model(ir, dev, props)
                x = (rng.standard_normal((1, L, H)) * 0.02).astype(np.float32)
                # 实跑（不只看编译）
                for _ in range(3):
                    cm([x])
                ms = median_ms(lambda: cm([x]))
                rec[tag] = ms
                print(f'  L={L:4d} {tag}: {ms:7.2f} ms  '
                      f'({ms/STATEFUL_PER_TOKEN:.2f}x stateful)', flush=True)
            except Exception as e:
                rec[tag] = None
                rec[f'{tag}_error'] = str(e)[:400]
                print(f'  L={L:4d} {tag}: FAIL {str(e)[:120]}', flush=True)

        # 与 GPU 的 cosine（验证短序列版数值仍正确）
        if rec.get('gpu') and rec.get('npu'):
            try:
                cg = core.compile_model(ir, 'GPU',
                                        {'INFERENCE_PRECISION_HINT': 'f16'})
                cn = core.compile_model(ir, 'NPU', {'CACHE_DIR': CACHE})
                x = (rng.standard_normal((1, L, H)) * 0.02).astype(np.float32)
                a = np.asarray(cg([x])[0]).reshape(-1)
                b = np.asarray(cn([x])[0]).reshape(-1)
                rec['cosine_npu_vs_gpu'] = round(float(
                    np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))), 6)
                rec['argmax_match'] = bool(np.argmax(a) == np.argmax(b))
            except Exception as e:
                rec['cosine_error'] = str(e)[:300]
        res['variants'][str(L)] = rec

    # 线性拟合：ms = a + b*L
    fits = {}
    for tag in ('gpu', 'npu'):
        pts = [(int(k), v[tag]) for k, v in res['variants'].items()
               if v.get(tag)]
        if len(pts) >= 2:
            pts.sort()
            xs = np.array([p[0] for p in pts], float)
            ys = np.array([p[1] for p in pts], float)
            b, a = np.polyfit(xs, ys, 1)
            fits[tag] = {'intercept_ms': round(float(a), 2),
                         'us_per_token': round(float(b) * 1000, 2),
                         'points': [[int(x), float(y)] for x, y in pts]}
    res['linear_fit'] = fits
    print('\n线性拟合:')
    for tag, f in fits.items():
        print(f"  {tag}: {f['intercept_ms']:.1f} ms + "
              f"{f['us_per_token']:.2f} us/token")

    # 端到端外推：无 cache，每步序列 = base + 已生成 token
    # base = 模板13 + 音频(段长相关) + 前缀
    proj = {}
    for tag, f in fits.items():
        a, b = f['intercept_ms'], f['us_per_token'] / 1000.0
        for L_cap in LENS:
            for audio_tok in (208, 312):     # 典型 16.4s / 最长 24s
                base = 13 + audio_tok + 100
                # 超过 L_cap 的部分用填充（静态图只能填到 L_cap）
                total = 0
                for t in range(AVG_OUT_TOK):
                    seq = min(base + t, L_cap)
                    total += a + b * seq
                rtf = (total / 1000) / AVG_SEG_SEC
                key = f'{tag}_L{L_cap}_audio{audio_tok}'
                proj[key] = {'per_seg_ms': round(total, 1),
                             'rtf': round(rtf, 3),
                             'ok': bool(rtf <= 1)}
    res['projection'] = proj

    print('\n端到端预估（每段 16.36 s，65 输出 token）:')
    for k in sorted(proj, key=lambda x: proj[x]['rtf']):
        d = proj[k]
        flag = '✅' if d['ok'] else '❌'
        print(f"  {k:28s} RTF {d['rtf']:6.2f} {flag}")

    feasible = [k for k, v in proj.items() if v['ok']]
    res['verdict'] = {
        'any_feasible': bool(feasible),
        'feasible_keys': feasible[:10],
        'best_rtf': min(v['rtf'] for v in proj.values()),
        'conclusion': (
            '存在 RTF<=1 的组合，可继续端到端验收' if feasible else
            '所有长度变体的无 cache 方案 RTF 均 >1，'
            '「缩短序列」无法救回，NPU 交付路径判定为不可行'),
    }
    print('\nverdict:', json.dumps(res['verdict'], ensure_ascii=False))

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
