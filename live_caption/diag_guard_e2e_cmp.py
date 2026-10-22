r"""diag_guard_e2e_cmp.py — C-105 端到端 A/B 结果比对

对比两份 `diag_cut_quality.py` 的产物（`segs_cut1.2.json`）：
  * 段数变化
  * 定稿时间戳（= 白字出现时刻）逐段对比 → **白字提前了多少**
  * 定稿文本逐段对比 → **准确率有没有损失**
  * 拼接全文的词级多重集比较 → **有没有真的丢内容**

用法：
  python diag_guard_e2e_cmp.py <base.json> <new.json> [--label 基线,新判据]
"""

from __future__ import annotations

import os
import re
import sys
import json
from collections import Counter


def norm_words(text):
    """归一化：去标点、小写、非 ASCII 保留（中文要能处理）。"""
    t = text.lower()
    t = re.sub(r'[^\w\s]', ' ', t, flags=re.UNICODE)
    return [w for w in t.split() if w]


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return
    base_p, new_p = args[0], args[1]
    label = ('基线(绝对阈值)', '新判据(绝对∪相对)')
    if '--label' in args:
        a, b = args[args.index('--label') + 1].split(',')
        label = (a, b)

    base = json.load(open(base_p, encoding='utf-8'))
    new = json.load(open(new_p, encoding='utf-8'))

    bf, nf = base['finals'], new['finals']
    bs, ns = base['stamps'], new['stamps']

    print('=' * 74)
    print(f'{label[0]:22s}  段数 {len(bf):3d}  墙钟 {base["wall"]:7.1f}s')
    print(f'{label[1]:22s}  段数 {len(nf):3d}  墙钟 {new["wall"]:7.1f}s')
    print('=' * 74)

    # ── 1. 白字提前量（逐段按顺序配对）──
    n = min(len(bs), len(ns))
    diffs = [ns[i] - bs[i] for i in range(n)]
    earlier = sum(1 for d in diffs if d < -0.05)
    later = sum(1 for d in diffs if d > 0.05)
    same = n - earlier - later
    print(f'\n【1】白字出现时刻（按段序配对，前 {n} 段）')
    print(f'  提前 >50ms：{earlier} 段   推迟 >50ms：{later} 段   '
          f'基本持平：{same} 段')
    if earlier:
        e = [-d for d in diffs if d < -0.05]
        print(f'  提前量：中位 {sorted(e)[len(e)//2]:.2f}s  最大 {max(e):.2f}s  '
              f'合计 {sum(e):.1f}s')

    # ── 2. 逐段文本比对 ──
    print(f'\n【2】定稿文本逐段比对')
    exact = 0
    diff_list = []
    for i in range(n):
        a, b = norm_words(bf[i]), norm_words(nf[i])
        if a == b:
            exact += 1
        else:
            diff_list.append((i, bs[i], ns[i], bf[i], nf[i]))
    print(f'  逐字相同：{exact}/{n} 段 ({exact/max(1,n)*100:.0f}%)')
    print(f'  有差异：{len(diff_list)} 段')
    for i, t0, t1, a, b in diff_list[:6]:
        print(f'\n  --- 第 {i+1} 段（基线 @{t0:.1f}s → 新 @{t1:.1f}s）---')
        print(f'    基线: {a[:150]}')
        print(f'    新  : {b[:150]}')

    # ── 3. 全文词级多重集（有没有真的丢内容）──
    print(f'\n【3】全文词级多重集比较（判断是否真的丢了内容）')
    ba = Counter()
    for t in bf:
        ba.update(norm_words(t))
    na = Counter()
    for t in nf:
        na.update(norm_words(t))
    only_b = ba - na
    only_n = na - ba
    lost = sum(only_b.values())
    added = sum(only_n.values())
    total_b = sum(ba.values())
    print(f'  基线总词数 {total_b}   新判据总词数 {sum(na.values())}')
    print(f'  仅基线有（疑似丢失）：{lost} 词   仅新有（疑似多出）：{added} 词')
    if only_b:
        print(f'  丢失词 top20：{only_b.most_common(20)}')
    if only_n:
        print(f'  多出词 top20：{only_n.most_common(20)}')

    # ── 4. 结论 ──
    print('\n' + '=' * 74)
    print('结论')
    print('-' * 74)
    if earlier and not later:
        print(f'  ✅ 新判据让白字提前 {earlier} 段，无推迟')
    elif earlier and later:
        print(f'  ⚠️ 新判据提前 {earlier} 段，但也有 {later} 段推迟（需查原因）')
    else:
        print('  ℹ️ 未观察到白字提前')
    if exact == n and not later:
        print('  ✅ 全部定稿文本逐字相同')
    elif lost == 0:
        print(f'  ✅ 未丢失任何词（{len(diff_list)} 段有差异但内容无缺失）')
    else:
        print(f'  ⚠️ 疑似丢失 {lost} 个词，需人工核对')


if __name__ == '__main__':
    main()
