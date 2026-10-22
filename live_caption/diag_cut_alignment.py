r"""diag_cut_alignment.py — 把不同 SILENCE_CUT_SEC 的分段结果做对齐分析

diag_cut_quality.py 给出了「全文词序列不同」，但没回答**差异在哪**：
是某一段丢了整块内容（严重），还是边界上多了/少了一两个词（可接受）？

做法：按**词级**做序列对齐（difflib.SequenceMatcher），
把差异归类成三类：
  · 整块缺失（连续 ≥3 个词只在一边出现）—— 严重，必须避免
  · 边界增删（≤2 个词的连续差异）—— 可接受
  · 替换（等长不同词）—— 通常是同音误识

用法：
  python diag_cut_alignment.py <results.txt>
  （results.txt 是 diag_cut_quality.py 的输出文件）
"""
import difflib
import os
import re
import sys


def norm_words(text):
    """英文按词、中文按字。与 diag_cut_quality.py 保持一致。

    ⚠️ 只用 ``[^a-z0-9 ]`` 过滤会把中文译文整段滤掉（空列表），
    比对结论会失真。
    """
    return re.findall(r'[a-z0-9]+|[一-鿿]', text.lower())


def parse(path):
    """从 diag_cut_quality.py 的输出里解析出 {cut: [段文本]}。"""
    out = {}
    cur = None
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        m = re.match(r'^=== SILENCE_CUT_SEC=([\d.]+) ===', line)
        if m:
            cur = float(m.group(1))
            out[cur] = []
            continue
        if cur is None:
            continue
        # 段行格式：  [0] @  14.0s  "...."
        m2 = re.match(r"^\s+\[\d+\]\s*@\s*([\d.]+)s\s+(.*)$", line)
        if m2:
            body = m2.group(2).strip()
            if body.startswith(("'", '"')):
                body = body[1:-1]
            out[cur].append((float(m2.group(1)), body))
    return out


def diff_class(wa, wb, label_a, label_b):
    """把两段词序列的差异分类统计。"""
    sm = difflib.SequenceMatcher(None, wa, wb)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        da = wa[i1:i2]
        db = wb[j1:j2]
        if not da and not db:
            continue
        if len(da) >= 3 or len(db) >= 3:
            kind = '整块缺失/新增'
        elif len(da) == len(db):
            kind = '替换'
        else:
            kind = '边界增删'
        blocks.append((kind, da, db))
    return blocks


def main():
    path = sys.argv[1]
    data = parse(path)
    if not data:
        print('没解析出任何分段结果')
        return
    cuts = sorted(data)
    base = cuts[-1]
    print(f'基准档 cut={base}\n')

    for cut in cuts[:-1]:
        a_segs, b_segs = data[cut], data[base]
        a_full = norm_words(' '.join(s for _, s in a_segs))
        b_full = norm_words(' '.join(s for _, s in b_segs))
        print(f'===== cut={cut}  vs  cut={base} =====')
        print(f'  词数：cut={cut} {len(a_full)} 词 | cut={base} {len(b_full)} 词  '
              f'(差 {len(a_full)-len(b_full):+d})')
        blocks = diff_class(a_full, b_full, cut, base)
        if not blocks:
            print('  ★ 词序列完全一致')
        else:
            n_hard = sum(1 for k, _, _ in blocks if k == '整块缺失/新增')
            print(f'  差异块 {len(blocks)} 个：'
                  f'整块 {n_hard} / 替换 {sum(1 for k,_,_ in blocks if k=="替换")} / '
                  f'边界增删 {sum(1 for k,_,_ in blocks if k=="边界增删")}')
            for kind, da, db in blocks:
                a_s = ' '.join(da) if da else '(无)'
                b_s = ' '.join(db) if db else '(无)'
                print(f'    [{kind}]')
                print(f'       cut={cut}: {a_s[:120]}')
                print(f'       cut={base}: {b_s[:120]}')
        print()


if __name__ == '__main__':
    main()
