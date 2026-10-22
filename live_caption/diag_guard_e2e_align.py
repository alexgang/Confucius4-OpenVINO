r"""diag_guard_e2e_align.py — 端到端 A/B 的**内容对齐**比对（修正段序配对的缺陷）

为什么需要这个
--------------
`diag_guard_e2e_cmp.py` 用「第 i 段对第 i 段」来配对，这在新判据下是**错的**：
一旦某处提前切，后面所有段的时间戳都会整体漂移（实测漂移达 35s），
于是「逐段配对」看到的 ±28s 差异其实是**漂移**，不是真实的提前/推迟。

正确口径：**按文本内容对齐**。
  1. 把两边的定稿文本都切成「词序列」。
  2. 用**词级序列对齐**（类似 diff）把两边的词流对齐，
     找出「基线的第 k 个词」在「新判据」里对应第几个词。
  3. 对每个**对齐上的词**，比较它被定稿的时刻
     （= 所属段的定稿时间戳）→ 这才是「这段话的白字早/晚了多少」。

同时报告：
  * 全文词级多重集差异（是否真的丢了内容）
  * 未对齐的词（真实丢失/新增）

用法：
  python diag_guard_e2e_align.py <base.json> <new.json>
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


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return
    base = json.load(open(args[0], encoding='utf-8'))
    new = json.load(open(args[1], encoding='utf-8'))

    # 展开成「词 → 定稿时刻」
    def expand(d):
        words, times = [], []
        for txt, ts in zip(d['finals'], d['stamps']):
            ws = norm_words(txt)
            words.extend(ws)
            times.extend([ts] * len(ws))
        return words, times

    bw, bt = expand(base)
    nw, nt = expand(new)

    print('=' * 74)
    print(f'基线：{len(base["finals"])} 段 / {len(bw)} 词')
    print(f'新  ：{len(new["finals"])} 段 / {len(nw)} 词')
    print('=' * 74)

    # ── 词级序列对齐 ──
    sm = difflib.SequenceMatcher(a=bw, b=nw, autojunk=False)
    ops = sm.get_opcodes()

    time_diffs = []          # 对齐上的词：白字时刻差
    n_equal = 0
    n_sub = 0
    n_del = 0
    n_ins = 0
    del_words = []
    ins_words = []

    for tag, i1, i2, j1, j2 in ops:
        if tag == 'equal':
            for k in range(i2 - i1):
                time_diffs.append(nt[j1 + k] - bt[i1 + k])
                n_equal += 1
        elif tag == 'replace':
            # 可能有部分相等
            sub = difflib.SequenceMatcher(a=bw[i1:i2], b=nw[j1:j2], autojunk=False)
            for t2, a1, a2, b1, b2 in sub.get_opcodes():
                if t2 == 'equal':
                    for k in range(a2 - a1):
                        time_diffs.append(nt[j1 + b1 + k] - bt[i1 + a1 + k])
                        n_equal += 1
                elif t2 == 'replace':
                    n_sub += max(a2 - a1, b2 - b1)
                elif t2 == 'delete':
                    n_del += a2 - a1
                    del_words.extend(bw[i1 + a1:i1 + a2])
                elif t2 == 'insert':
                    n_ins += b2 - b1
                    ins_words.extend(nw[j1 + b1:j1 + b2])

    print(f'\n【1】词级对齐')
    print(f'  完全相同的词：{n_equal}')
    print(f'  替换（识别不同）：{n_sub}')
    print(f'  仅基线有（真丢失）：{n_del}  {del_words[:20]}')
    print(f'  仅新有（真多出）：{n_ins}  {ins_words[:20]}')
    print(f'  对齐率：{n_equal}/{len(bw)} = {n_equal/max(1,len(bw))*100:.1f}%')

    if time_diffs:
        td = time_diffs
        earlier = [d for d in td if d < -0.05]
        later = [d for d in td if d > 0.05]
        print(f'\n【2】同一批词的白字出现时刻差（新 - 基线）')
        print(f'  提前 >50ms：{len(earlier)} 词')
        print(f'  推迟 >50ms：{len(later)} 词')
        print(f'  基本持平：{len(td)-len(earlier)-len(later)} 词')
        if earlier:
            e = sorted(-d for d in earlier)
            print(f'  提前量：中位 {e[len(e)//2]:.2f}s  '
                  f'p90 {e[int(len(e)*0.9)]:.2f}s  max {max(e):.2f}s')
        if later:
            l = sorted(d for d in later)
            print(f'  推迟量：中位 {l[len(l)//2]:.2f}s  max {max(l):.2f}s')

    # ── 按段对齐：同一段文本在两边是否被定稿在同一时刻 ──
    print(f'\n【3】按「段落文本」匹配（同一句话在两边的白字时刻）')
    bmap = {}
    for txt, ts in zip(base['finals'], base['stamps']):
        bmap.setdefault(' '.join(norm_words(txt)), []).append(ts)
    nmap = {}
    for txt, ts in zip(new['finals'], new['stamps']):
        nmap.setdefault(' '.join(norm_words(txt)), []).append(ts)

    matched = 0
    diffs = []
    for k, bts in bmap.items():
        if k in nmap and bts and nmap[k]:
            matched += 1
            diffs.append(nmap[k][0] - bts[0])
    print(f'  两边都有完全相同文本的段：{matched} / {len(bmap)}')
    if diffs:
        earlier = [d for d in diffs if d < -0.05]
        later = [d for d in diffs if d > 0.05]
        print(f'  提前 >50ms：{len(earlier)}   推迟 >50ms：{len(later)}   '
              f'持平：{len(diffs)-len(earlier)-len(later)}')
        if earlier:
            e = sorted(-d for d in earlier)
            print(f'  提前量：中位 {e[len(e)//2]:.2f}s  max {max(e):.2f}s  '
                  f'合计 {sum(e):.1f}s')

    # ── 3b. 漂移校正：段边界变了会导致「段序配对」整体错位 ──
    # 做法：以「累计词数」为横轴，把两边的定稿时刻画成阶梯函数，
    # 再按累计词数对齐比较 —— 这样消除段边界差异，只看
    # 「同样的内容被定稿的时刻」。
    print(f'\n【3b】按累计词数对齐（消除段边界漂移后的真实时刻差）')
    bcum = []
    c = 0
    for ts in base['stamps']:
        c += len(norm_words(base['finals'][len(bcum)]))
        bcum.append((c, ts))
    ncum = []
    c = 0
    for i, ts in enumerate(new['stamps']):
        c += len(norm_words(new['finals'][i]))
        ncum.append((c, ts))

    def stamp_at(steps, k):
        """累计词数 k 处，字幕出现的时刻（阶梯函数）"""
        for cum, ts in steps:
            if cum > k:
                return ts
        return steps[-1][1] if steps else 0.0

    sample = [min(k, len(bw) - 1) for k in range(0, len(bw), max(1, len(bw) // 40))]
    ds = [stamp_at(ncum, k) - stamp_at(bcum, k) for k in sample]
    earlier = [d for d in ds if d < -0.05]
    later = [d for d in ds if d > 0.05]
    print(f'  采样 {len(ds)} 个累计词数点')
    print(f'  提前 >50ms：{len(earlier)}   推迟 >50ms：{len(later)}   '
          f'持平：{len(ds)-len(earlier)-len(later)}')
    if earlier:
        e = sorted(-d for d in earlier)
        print(f'  提前量：中位 {e[len(e)//2]:.2f}s  max {max(e):.2f}s')
    if later:
        l = sorted(d for d in later)
        print(f'  推迟量：中位 {l[len(l)//2]:.2f}s  max {max(l):.2f}s')

    # ── 多重集 ──
    ba, na = Counter(bw), Counter(nw)
    only_b = ba - na
    only_n = na - ba
    print(f'\n【4】词级多重集')
    print(f'  仅基线有：{sum(only_b.values())} 词 {only_b.most_common(12)}')
    print(f'  仅新有  ：{sum(only_n.values())} 词 {only_n.most_common(12)}')

    print('\n' + '=' * 74)
    if n_del == 0:
        print('✅ 未丢失任何词（识别内容完整）')
    else:
        print(f'⚠️ 丢失 {n_del} 个词，需核对')
    if diffs:
        earlier = [d for d in diffs if d < -0.05]
        later = [d for d in diffs if d > 0.05]
        if earlier and not later:
            print(f'✅ 相同内容的白字全部提前（{len(earlier)} 段，无推迟）')
        elif earlier and later:
            print(f'⚠️ {len(earlier)} 段提前、{len(later)} 段推迟')


if __name__ == '__main__':
    main()
