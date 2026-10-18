"""c058j_tail_latency.py — C-058 尾延迟系统性分析

reviewer 追问（C-058 第五节）：
  「注意 encoder INT4 这次的 seg_rtf_max = 0.805（FP16 是 0.676），P95 也从
    0.638 升到 0.689；请确认是**单点离群**还是**系统性**（看逐段 RTF 分布，
    必要时重跑该段）」

方法：
  1. 把 FP16 与 INT4 的逐段 RTF 按**同一段标签**配对；
  2. 看差值分布（中位数 / 四分位 / 尾部），而不是只看单点最大值；
  3. 配对 bootstrap 给出「P95 / max 是否真的升高」的 95% CI；
  4. 定位最差的几段，看是否集中在特定音频（可用重跑验证）。

只读 JSON，不占 GPU。
用法：.venv python c058j_tail_latency.py
"""
import os
import sys
import json
import random

FP16_SEG = 'reports/c058_tail/summary_seg_rtf.json'   # c058k 重跑，存了逐段 RTF
CAND_SEG = {
    'FP16 enc + INT8 dec (基线)': 'reports/c048_61min_adaptive/summary.json',
    'INT4 enc + INT8 dec (C-057)': 'reports/c057_61min_encoder/summary.json',
    'FP16 enc + INT4全量 dec (C-058④)': 'reports/c058_61min/summary_int4lmhead_dec.json',
}


def pct(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    k = min(int(len(s) * q), len(s) - 1)
    return s[k]


def stats(d, key='seg_rtfs'):
    rtfs = [s['rtf'] for s in d.get(key, []) if s.get('rtf', 0) > 0]
    return rtfs


def paired_bootstrap_p95(a, b, iters=5000, seed=1234):
    """统计量 = P95(b) − P95(a)，正 = b 的 P95 更高（更慢）。"""
    rng = random.Random(seed)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]

    def p95(sample, idx):
        return pct([sample[i] for i in idx], 0.95)

    allidx = list(range(n))
    obs = p95(b, allidx) - p95(a, allidx)
    d = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        d.append(p95(b, idx) - p95(a, idx))
    d.sort()
    lo = d[int(len(d) * 0.025)]
    hi = d[int(len(d) * 0.975)]
    return {'delta_p95': round(obs, 4),
            'ci95': [round(lo, 4), round(hi, 4)],
            'significant': not (lo <= 0 <= hi)}


def main():
    base = json.load(open(FP16_SEG, encoding='utf-8'))
    # C-061#3 起 c058k 的输出格式从 list 改为 dict（含 order / warmup 等元信息）
    if isinstance(base, dict):
        base = base.get('results', base.get('data', []))
    fp16 = next(d for d in base if d['tag'] == 'enc_fp16')
    int4 = next(d for d in base if d['tag'] == 'enc_int4')
    a = stats(fp16)
    b = stats(int4)
    print('=== C-057 尾延迟：encoder INT4 vs FP16（同一份 FP16 decoder，仅换 encoder）===')
    print(f'{"配置":<10}{"P50":>8}{"P90":>8}{"P95":>8}{"P99":>8}{"max":>8}{"n>0.75":>8}')
    for nm, r in (('FP16', a), ('INT4', b)):
        print(f'{nm:<10}{pct(r,.5):>8.3f}{pct(r,.9):>8.3f}{pct(r,.95):>8.3f}'
              f'{pct(r,.99):>8.3f}{max(r):>8.3f}{sum(1 for x in r if x>0.75):>8d}')

    # 逐段配对差值
    n = min(len(a), len(b))
    diff = [b[i] - a[i] for i in range(n)]
    pos = sum(1 for d_ in diff if d_ > 0)
    print(f'\n逐段配对 n={n}：INT4 更慢的段数 = {pos} ({100*pos/n:.1f}%)')
    print(f'  差值 中位数 = {pct(diff,.5):+.4f}   均值 = {sum(diff)/n:+.4f}')
    print(f'  差值 P10/P90 = {pct(diff,.1):+.4f} / {pct(diff,.9):+.4f}')

    ci = paired_bootstrap_p95(a, b)
    # C-061#2 修正：原判据是「CI 不含 0 就下系统性结论」，这是错的。
    # 两个原因：
    #   1) 逐段 RTF 有 lag-1 自相关（FP16 0.77 / INT4 0.37），段间独立假设不成立，
    #      真实 CI 比这里算的宽；
    #   2) 更关键 —— **运行间**波动（c057f 与 c058k 方向相反，约 0.1）比任何
    #      运行**内**的 CI 都大。单个 CI 再「显著」也压不住跨运行的随机性。
    # 所以这里只报告数字，不再输出「系统性更高/更低」的结论。
    print(f'\nP95 差值（INT4 − FP16，本次运行内）= {ci["delta_p95"]:+.4f}  '
          f'朴素 CI [{ci["ci95"][0]:+.4f}, {ci["ci95"][1]:+.4f}]  '
          f'（{"不含" if ci["significant"] else "含"} 0）')
    print('  ⚠️ C-061：该 CI 假设段间独立，但 FP16 的 lag-1 自相关达 0.77；')
    print('     且 c057f/c058k 两次运行方向相反（−0.051 / +0.083），')
    print('     运行间波动 ~0.1 > 运行内 CI 宽度 → **不能据此下系统性结论**。')

    worst = sorted(range(n), key=lambda i: diff[i], reverse=True)[:5]
    print('\nINT4 相对 FP16 最慢的 5 段（label / FP16 RTF → INT4 RTF）:')
    for i in worst:
        print(f'  seg{i:<4d} {a[i]:.3f} → {b[i]:.3f}  ({diff[i]:+.3f})')

    # C-058④ 全量 INT4 的尾延迟
    print('\n=== C-058④ 全量 INT4 decoder 的尾延迟 ===')
    d4 = json.load(open(CAND_SEG['FP16 enc + INT4全量 dec (C-058④)'],
                        encoding='utf-8'))
    r4 = stats(d4)
    print(f'{"配置":<26}{"P50":>8}{"P95":>8}{"P99":>8}{"max":>8}')
    print(f'{"FP16 enc+INT8 dec":<26}{pct(a,.5):>8.3f}{pct(a,.95):>8.3f}'
          f'{pct(a,.99):>8.3f}{max(a):>8.3f}')
    print(f'{"FP16 enc+INT4全量 dec":<26}{pct(r4,.5):>8.3f}{pct(r4,.95):>8.3f}'
          f'{pct(r4,.99):>8.3f}{max(r4):>8.3f}')
    ci4 = paired_bootstrap_p95(a, r4)
    print(f'P95 差值 = {ci4["delta_p95"]:+.4f}  朴素 CI '
          f'[{ci4["ci95"][0]:+.4f}, {ci4["ci95"][1]:+.4f}]  '
          f'（{"不含" if ci4["significant"] else "含"} 0）')
    print('  ⚠️ C-061：同上，跨运行波动更大，不下系统性结论。'
          '带 guard 重跑见 c058p_rerun_tail.py。')

    out = {'note': 'delta = P95(候选) − P95(FP16)；负 = 候选尾延迟更低。'
                  '⚠️ C-061#2：以下 CI 均为「运行内」朴素 CI（假设段间独立，'
                  '但逐段 RTF 有 lag-1 自相关 FP16=0.77），且运行间波动约 0.1 '
                  '大于任何运行内 CI，**不得据此下系统性结论**。',
           'encoder_int4_vs_fp16': {
               'p50_fp16': round(pct(a, .5), 4), 'p95_fp16': round(pct(a, .95), 4),
               'p99_fp16': round(pct(a, .99), 4), 'max_fp16': round(max(a), 4),
               'p50_int4': round(pct(b, .5), 4), 'p95_int4': round(pct(b, .95), 4),
               'p99_int4': round(pct(b, .99), 4), 'max_int4': round(max(b), 4),
               'n_slower_segments': pos, 'n': n,
               'n_gt_075_fp16': sum(1 for x in a if x > 0.75),
               'n_gt_075_int4': sum(1 for x in b if x > 0.75),
               **ci},
           'int4_full_decoder_vs_int8': {
               'p50': round(pct(r4, .5), 4), 'p95': round(pct(r4, .95), 4),
               'p99': round(pct(r4, .99), 4), 'max': round(max(r4), 4),
               **ci4}}
    with open('reports/c058_tail_latency.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\nsaved -> reports/c058_tail_latency.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
