r"""diag_cut_multiset.py — 判断不同切段阈值下是否**真的丢了内容**

序列对齐会把「同一批词换了段落归属」误报成大段差异。真正要回答的是：
  · 有哪些词**只在一边出现**（真丢失 / 真幻觉）
  · 词频差异有多大

做法：词 → 计数 的多重集比较，逐词列出差异。
  · 只在基准档出现的词 = 基准有、实验档丢了（内容缺失）
  · 只在实验档出现的词 = 实验档多出来的（幻觉/改写）

用法：
  python diag_cut_multiset.py <segs_cut*.json 的目录>
"""
import collections
import glob
import json
import os
import re
import sys


def norm_words(text):
    """英文按词、中文按字。与 diag_cut_quality.py 保持一致。

    ⚠️ 只用 ``[^a-z0-9 ]`` 过滤会把中文译文整段滤掉（空列表），
    「基准有而这档缺」会永远算 0 词，结论失真。
    """
    return re.findall(r'[a-z0-9]+|[一-鿿]', text.lower())


def main():
    d = sys.argv[1]
    files = sorted(glob.glob(os.path.join(d, 'segs_cut*.json')))
    if not files:
        print('没找到 segs_cut*.json')
        return

    data = {}
    for f in files:
        j = json.load(open(f, encoding='utf-8'))
        data[float(j['cut'])] = j

    cuts = sorted(data)
    base = cuts[-1]
    print(f'基准档 cut={base}\n')
    bc = collections.Counter(norm_words(' '.join(data[base]['finals'])))

    for cut in cuts[:-1]:
        a = collections.Counter(norm_words(' '.join(data[cut]['finals'])))
        only_base = bc - a          # 基准里有、这档没有的
        only_a = a - bc             # 这档多出来的
        n_base, n_a = sum(bc.values()), sum(a.values())
        print(f'===== cut={cut} vs cut={base} =====')
        print(f'  段数 {len(data[cut]["finals"])} vs {len(data[base]["finals"])}   '
              f'总词数 {n_a} vs {n_base} ({n_a-n_base:+d})')
        print(f'  基准有而这档缺：{sum(only_base.values())} 词')
        if only_base:
            print('     ' + ', '.join(f'{w}×{c}' for w, c in only_base.most_common(25)))
        print(f'  这档多出：{sum(only_a.values())} 词')
        if only_a:
            print('     ' + ', '.join(f'{w}×{c}' for w, c in only_a.most_common(25)))
        print()


if __name__ == '__main__':
    main()
