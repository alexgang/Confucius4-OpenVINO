r"""diag_seg_white_lead.py — 白字提前量的**无漂移**测量（音频坐标 + 词级对齐）

问题
----
端到端墙钟对比被**机器漂移**支配：C-108 的两次实验里，
同一组对比的墙钟方向是**相反的**（12 分钟跑：617.6s vs 485.0s；
8 分钟跑：298.5s vs 325.2s）。C-105 也已证明同条件两次基线相差 60.2s。
→ 墙钟不能作为白字提前量的判据。

方法
----
把所有坐标换到**音频时间轴**，机器漂移就自动被剔除：

  1. 每个方案记录：每段的「覆盖到的音频末尾位置」`apos[i]` 与「该段文本」。
  2. 词级对齐两个方案的词序列（difflib），得到词对应关系。
  3. 对每个匹配词对 (w_A, w_B)，它所属段的音频末尾位置分别是 e_A、e_B。
     → 该内容的「定稿覆盖位置」差 = e_A − e_B。
       正数 = 方案 B 在**更靠前的音频位置**就定稿了这段内容（白字更早）。
  4. 统计中位 / 最大 / 分位数。

为什么这个口径成立
------------------
「音频位置 e 处已定稿」是一个**纯内容坐标**，与机器快慢无关。
方案 B 的 e_B 小于 e_A，说明同样多的内容，B 在更早的音频时刻就已转白
→ 用户的白字等待时间更短。

用法：
  python diag_seg_white_lead.py <run_dir>
  （run_dir 里应有 cut1.2.json / cut0.8.json）
"""

from __future__ import annotations

import os
import re
import sys
import json
import difflib
from collections import Counter


def norm_words(text):
    t = text.lower()
    t = re.sub(r'[^\w\s]', ' ', t, flags=re.UNICODE)
    return [w for w in t.split() if w]


def build(r):
    """把一个 run 展开成「词 → 所属段的音频末尾位置」列表。"""
    words = []
    pos = []
    for i, fin in enumerate(r['finals']):
        e = r['apos'][i]
        for w in norm_words(fin):
            words.append(w)
            pos.append(e)
    return words, pos


def main():
    run_dir = sys.argv[1]
    a_path = os.path.join(run_dir, 'cut1.2.json')
    b_path = os.path.join(run_dir, 'cut0.8.json')
    with open(a_path, encoding='utf-8') as f:
        A = json.load(f)
    with open(b_path, encoding='utf-8') as f:
        B = json.load(f)

    wa, pa = build(A)
    wb, pb = build(B)

    print('=' * 88)
    print(f'白字提前量（音频坐标 + 词级对齐）  {os.path.basename(run_dir)}')
    print('=' * 88)
    print(f'  基线 1.2s：段数 {len(A["finals"])}  词数 {len(wa)}  '
          f'墙钟 {A["wall"]:.1f}s')
    print(f'  新  0.8s：段数 {len(B["finals"])}  词数 {len(wb)}  墙钟 {B["wall"]:.1f}s')
    print(f'  ⚠️ 墙钟受机器漂移支配，不作为判据；以下全部用音频坐标。')

    sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for i, j in zip(range(i1, i2), range(j1, j2)):
                diffs.append(pa[i] - pb[j])
        else:
            # 替换/插入/删除：把区间内按位置插值配对（仅用于统计，不计为内容差异）
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                diffs.append(pa[i1 + k] - pb[j1 + k])

    if not diffs:
        print('  无可比对词')
        return

    ds = sorted(diffs)
    import statistics
    pos = [x for x in diffs if x > 0]
    neg = [x for x in diffs if x < 0]

    print()
    print('  ★ 差值 = e_基线 − e_新（正数 = 新方案在同一内容的音频位置上更早定稿）')
    print(f'    比对词数        {len(diffs)}')
    print(f'    中位差值        {statistics.median(diffs):+.3f}s')
    print(f'    均值差值        {sum(diffs)/len(diffs):+.3f}s')
    print(f'    最大提前        {max(diffs):+.2f}s')
    print(f'    最大滞后        {min(diffs):+.2f}s')
    print(f'    p90 / p75 / p25  {ds[int(len(ds)*0.90)]:+.2f} / '
          f'{ds[int(len(ds)*0.75)]:+.2f} / {ds[int(len(ds)*0.25)]:+.2f}s')
    print(f'    新方案更早的词数  {len(pos)}  ({100*len(pos)/len(diffs):.1f}%)')
    print(f'    新方案更晚的词数  {len(neg)}  ({100*len(neg)/len(diffs):.1f}%)')
    print(f'    持平的词数        {len(diffs)-len(pos)-len(neg)}  '
          f'({100*(len(diffs)-len(pos)-len(neg))/len(diffs):.1f}%)')

    # 按「每 30 秒音频桶」统计累计提前量
    print()
    print('  ★ 分桶：每 30s 音频区间内，已定稿内容的覆盖位置差（累计提前）')
    total = max(A['apos'][-1], B['apos'][-1])
    step = 30.0
    print(f'    {"音频区间":>14} {"基线覆盖":>10} {"新覆盖":>10} {"提前":>8}')
    for lo in range(0, int(total), int(step)):
        hi = lo + step
        ca = _covered(A, lo)
        cb = _covered(B, lo)
        if ca is None and cb is None:
            continue
        ca = ca or 0.0
        cb = cb or 0.0
        print(f'    {lo:>6.0f}-{hi:<6.0f} {ca:>10.2f} {cb:>10.2f} {ca-cb:>+8.2f}')

    print()
    print('  说明：「覆盖位置」= 在该音频时刻，最新定稿的那一段覆盖到的音频末尾。')
    print('        新方案覆盖位置更靠后 = 同样时刻已经看到更多内容 = 白字更早。')


def _covered(r, T):
    """音频时刻 T 时，已定稿内容覆盖到的最远音频位置。"""
    best = None
    for e in r['apos']:
        if e <= T:
            best = e if best is None else max(best, e)
    return best


if __name__ == '__main__':
    main()
