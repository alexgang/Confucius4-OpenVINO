"""c058o_tail_by_alignment.py — 按「块数」而非「时间」配对，做尾延迟稳健分析

动机：`int4lmhead_dec` 那次运行（10:43–11:18）没有配 GPU guard，reviewer 认为
P95/max 不可信。但事后发现 `summary_int4lmhead_dec.json` **其实存了 226 条逐段
RTF**（`seg_rtfs`），所以可以先做稳健性分析，再决定是否值得花 35 分钟重跑。

**关键点**：段 RTF 应当随段长（块数）变化 —— 12 s 的段和 20 s 的段不能直接比。
所以本脚本：
  1. 用 `n_chunks`（块数）作为协变量，比较**同等块数**下的 RTF；
  2. 按块数分箱（20 / 24 / 28 / 31 块）看分布是否重叠；
  3. 只在**同块数**的段上做配对 bootstrap，隔离「段长差异」这个混淆因素；
  4. 报告长段（≥28 块）的 P95 —— 尾延迟通常出现在最长的段。

用法：.venv python c058o_tail_by_alignment.py
"""
import os
import sys
import json
import random
from collections import defaultdict

S_BASE = 'reports/c048_61min_adaptive/segments_adaptive.json'  # INT8 交付基线（list）
S_CAND = 'reports/c058_61min/summary_int4lmhead_dec.json'    # 全量 INT4 decoder
S_FP16 = 'reports/c058_tail/summary_seg_rtf.json'             # FP16/INT4 encoder 重跑
BOXES = [20, 24, 28, 31]


def load(path, segs_path=None):
    """读一份结果，返回带 `seg_rtfs` 键的 dict。

    C-048 的基线把逐段数据单独放在 `segments_adaptive.json`（字段名是
    `start_s`/`n_chunks`/`rtf`），而 C-058 的 `summary_*.json` 直接内嵌
    `seg_rtfs`（字段名 `start`）。这里统一成 `seg_rtfs` 结构。
    """
    d = json.load(open(path, encoding='utf-8'))
    if isinstance(d, list):
        d = d[0] if 'seg_idx' not in d[0] else {'seg_rtfs': d}
    if segs_path:
        segs = json.load(open(segs_path, encoding='utf-8'))
        d = dict(d)
        d['seg_rtfs'] = [{'label': s.get('seg_idx', i), 'start': s['start_s'],
                          'end': s['end_s'], 'rtf': s['rtf'],
                          'n_chunks': s.get('n_chunks', 0)}
                         for i, s in enumerate(segs)]
    return d


def by_chunks(entry, key='seg_rtfs'):
    g = defaultdict(list)
    for s in entry.get(key, []):
        g[s.get('n_chunks', 0)].append(s['rtf'])
    return g


def pct(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    return s[min(int(len(s) * q), len(s) - 1)]


def paired_same_chunks(a_entry, b_entry, iters=5000, seed=1234):
    """只在块数相同的段上配对，比较 P95。统计量 = P95(B) − P95(A)。"""
    ga, gb = by_chunks(a_entry), by_chunks(b_entry)
    common = sorted(set(ga) & set(gb))
    if not common:
        return None
    # 每块数箱内各自重采样，再按段数加权合并
    rng = random.Random(seed)
    obs_a, obs_b, wts = [], [], []
    for c in common:
        A, B = sorted(ga[c]), sorted(gb[c])
        if not A or not B:
            continue
        obs_a.append(pct(A, .95))
        obs_b.append(pct(B, .95))
        wts.append(len(A) + len(B))
    if not wts:
        return None
    wsum = sum(wts)
    # 各块数箱等权平均（箱内段数已通过重采样反映在方差里）
    oa = sum(obs_a) / len(obs_a)
    ob = sum(obs_b) / len(obs_b)
    d = []
    for _ in range(iters):
        ra, rb = [], []
        for i, c in enumerate(common):
            A, B = sorted(ga[c]), sorted(gb[c])
            if not A or not B:
                continue
            ia = [rng.randrange(len(A)) for _ in A]
            ib = [rng.randrange(len(B)) for _ in B]
            ra.append(pct([A[k] for k in ia], .95))
            rb.append(pct([B[k] for k in ib], .95))
        if ra:
            d.append(sum(rb) / len(rb) - sum(ra) / len(ra))
    d.sort()
    lo, hi = d[int(len(d) * .025)], d[int(len(d) * .975)]
    return {'boxes': common, 'p95_a': round(oa, 4), 'p95_b': round(ob, 4),
            'delta_p95': round(ob - oa, 4),
            'ci95': [round(lo, 4), round(hi, 4)],
            'significant': not (lo <= 0 <= hi)}


def main():
    base = load(S_BASE, segs_path=S_BASE)
    cand = load(S_CAND)
    fp16 = next(d for d in json.load(open(S_FP16, encoding='utf-8'))
                if d['tag'] == 'enc_fp16')

    print('=== 段 RTF 按块数分箱（长段才是尾延迟的来源）===\n')
    print(f'{"块数":<6}{"基线 n":>7}{"基线P50":>9}{"基线P95":>9}'
          f'{"INT4 n":>7}{"INT4P50":>9}{"INT4P95":>9}{"P95差":>8}')
    gb_b, gb_c = by_chunks(base), by_chunks(cand)
    for c in sorted(set(gb_b) | set(gb_c)):
        A, B = gb_b.get(c, []), gb_c.get(c, [])
        if not A or not B:
            continue
        print(f'{c:<6}{len(A):>7}{pct(A,.5):>9.3f}{pct(A,.95):>9.3f}'
              f'{len(B):>7}{pct(B,.5):>9.3f}{pct(B,.95):>9.3f}'
              f'{pct(B,.95)-pct(A,.95):>+8.3f}')

    ci = paired_same_chunks(base, cand)
    print(f'\n=== 同块数配对 bootstrap（隔离段长混淆）===')
    if ci:
        print(f'  块数箱 = {ci["boxes"]}')
        print(f'  基线 P95 {ci["p95_a"]:.4f} → 全量 INT4 P95 {ci["p95_b"]:.4f}')
        print(f'  ΔP95 = {ci["delta_p95"]:+.4f}  95% CI '
              f'[{ci["ci95"][0]:+.4f}, {ci["ci95"][1]:+.4f}]  '
              f'{"显著" if ci["significant"] else "不显著（含 0）"}')
    # 长段尾部
    long_b = [s['rtf'] for s in base['seg_rtfs'] if s.get('n_chunks', 0) >= 28]
    long_c = [s['rtf'] for s in cand['seg_rtfs'] if s.get('n_chunks', 0) >= 28]
    print(f'\n=== 长段（≥28 块）尾部 ===')
    print(f'  基线   n={len(long_b):<4} P50={pct(long_b,.5):.3f} '
          f'P95={pct(long_b,.95):.3f} max={max(long_b):.3f}')
    print(f'  INT4   n={len(long_c):<4} P50={pct(long_c,.5):.3f} '
          f'P95={pct(long_c,.95):.3f} max={max(long_c):.3f}')

    # 同一次运行的 FP16 encoder 对照：看波动有多大
    long_f = [s['rtf'] for s in fp16['seg_rtfs'] if s.get('n_chunks', 0) >= 28]
    print(f'  FP16enc n={len(long_f):<4} P50={pct(long_f,.5):.3f} '
          f'P95={pct(long_f,.95):.3f} max={max(long_f):.3f}  '
          f'← 同日另一配置的参照，可见运行间波动幅度')

    print(f'\n验收线（P-060#1）：P95 ≤ 0.8')
    ok = '通过' if pct(cand['seg_rtfs'] and [s['rtf'] for s in cand['seg_rtfs']],
                       .95) <= 0.8 else '不通过'
    print(f'  全量 INT4 整体 P95 = {cand["seg_rtf_p95"]:.3f} → {ok}')

    out = {'note': 'same-n_chunks paired bootstrap isolates segment-length confound',
           'boxes': {str(c): {'n_base': len(gb_b.get(c, [])),
                              'n_cand': len(gb_c.get(c, [])),
                              'p95_base': round(pct(gb_b.get(c, []), .95), 4),
                              'p95_cand': round(pct(gb_c.get(c, []), .95), 4)}
                     for c in sorted(set(gb_b) & set(gb_c))},
           'paired_same_chunks': ci,
           'long_segs_ge28': {
               'base': {'n': len(long_b), 'p50': round(pct(long_b, .5), 4),
                        'p95': round(pct(long_b, .95), 4), 'max': round(max(long_b), 4)},
               'int4_full': {'n': len(long_c), 'p50': round(pct(long_c, .5), 4),
                             'p95': round(pct(long_c, .95), 4), 'max': round(max(long_c), 4)},
               'fp16_enc_ref': {'n': len(long_f), 'p50': round(pct(long_f, .5), 4),
                                'p95': round(pct(long_f, .95), 4),
                                'max': round(max(long_f), 4)}}}
    with open('reports/c058_tail_by_chunks.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\nsaved -> reports/c058_tail_by_chunks.json')
    return 0


if __name__ == '__main__':
    sys.exit(main())
