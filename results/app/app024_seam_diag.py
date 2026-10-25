"""诊断「段接缝重复词」的真实分布 —— 核实工作区注释声称的数字（n=1: 36/42）。

🔴 **为什么要单独诊断**：`app024_stitch_offline.py` 实测新 stitch 只命中
   A 组 3 次 / B 组 6 次，而工作区注释声称「A 组 n=1: **36**、B 组 n=1: **42**」
   ⇒ **差一个数量级** ⇒ 必须查清是「注释口径不同」还是「实现有 bug」。

本脚本统计**更宽**的口径：
  ① 相邻段「前段末尾 k 词」vs「后段开头 k 词」的**最长公共 n-gram** 分布；
  ② 相邻两段之间**任意位置**的重复词数（更宽，包含切在词中间的情况）；
  ③ 字符级「切在词中间」的重叠长度分布。
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
AB_DIR = os.path.join(REPO, 'reports', 'asr004_ab')


def norm_word(w):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', (w or '').lower())


def longest_common_ngram(prev_words, cur_words, max_n=6):
    """前段末尾 n 词 == 后段开头 n 词 的最大 n（0=无）。"""
    p = [norm_word(x) for x in prev_words]
    c = [norm_word(x) for x in cur_words]
    for n in range(min(max_n, len(p), len(c)), 0, -1):
        if p[-n:] == c[:n]:
            return n
    return 0


def char_overlap(a, b, max_k=30):
    a = (a or '').rstrip()
    b = (b or '').lstrip()
    al, bl = a.lower(), b.lower()
    for k in range(min(len(a), len(b), max_k), 0, -1):
        if al[-k:] == bl[:k]:
            return k
    return 0


def main():
    out = {}
    for name in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % name)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        segs = [s for s in d['segments'] if (s.get('text') or '').strip()]

        ngram_hist = {}          # 最长公共 n-gram 的分布
        rule_hist = {}           # 按 rule 拆分
        char_hist = {}           # 字符级重叠长度分布
        dup_anywhere = 0         # 相邻两段有**任意位置**重复词的段对数
        dup_anywhere_by_rule = {}
        examples = []

        for i in range(1, len(segs)):
            prev = segs[i - 1]
            cur = segs[i]
            pt = prev.get('text') or ''
            ct = cur.get('text') or ''
            pw = pt.split()
            cw = ct.split()

            n = longest_common_ngram(pw, cw)
            ngram_hist[n] = ngram_hist.get(n, 0) + 1
            r = prev.get('rule') or cur.get('rule') or '?'
            rule_hist.setdefault(r, {}).setdefault(n, 0)
            rule_hist[r][n] = rule_hist[r].get(n, 0) + 1

            k = char_overlap(pt, ct)
            if k:
                char_hist[k] = char_hist.get(k, 0) + 1

            # 任意位置重复：前段出现过的词在后段开头 6 词里出现过
            pw_set = set(norm_word(x) for x in pw[-8:] if norm_word(x))
            cur_head = [norm_word(x) for x in cw[:6]]
            hits = [w for w in cur_head if w and w in pw_set]
            if hits:
                dup_anywhere += 1
                dup_anywhere_by_rule[r] = dup_anywhere_by_rule.get(r, 0) + 1
                if len(examples) < 10:
                    examples.append(dict(
                        rule=r, n=n, char=k, hits=hits[:3],
                        prev=pt[-80:], cur=ct[:80]))

        print('═══ %s 组（%d 段，%d 对相邻段）═══'
              % (name, len(segs), len(segs) - 1))
        print('  ① 前段末尾 vs 后段开头 —— 最长公共 n-gram 分布：')
        for k in sorted(ngram_hist):
            print('       n=%d : %d 对' % (k, ngram_hist[k]))
        print('  ② 字符级重叠（切在词中间）长度分布：')
        if char_hist:
            for k in sorted(char_hist):
                print('       k=%d : %d 对' % (k, char_hist[k]))
        else:
            print('       （无）')
        print('  ③ 前段末尾 8 词 ∩ 后段开头 6 词（有重复即计）：%d 对' % dup_anywhere)
        print('       按 rule：%s' % dup_anywhere_by_rule)
        print('  ④ 按 rule 拆的最长公共 n-gram：')
        for r in sorted(rule_hist):
            print('       %s: %s' % (r, rule_hist[r]))
        print('  ⑤ 样例：')
        for e in examples[:6]:
            print('       [rule=%s n=%d char=%d hits=%s]' % (e['rule'], e['n'],
                                                           e['char'], e['hits']))
            print('         ...%s | %s...' % (e['prev'], e['cur']))
        print()

        out[name] = dict(ngram_hist=ngram_hist, char_hist=char_hist,
                          dup_anywhere=dup_anywhere,
                          dup_anywhere_by_rule=dup_anywhere_by_rule,
                          rule_hist=rule_hist)

    op = os.path.join(HERE, 'app024_seam_diag.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
