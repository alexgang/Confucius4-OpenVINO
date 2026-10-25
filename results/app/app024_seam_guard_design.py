"""为「段接缝 n=1 去重」找一个**更精确**的判据（替代过严的停用词安全阀）。

🔴 **问题**（`app024_stopword_audit.py` 实测）：
   A 组 n=1 重复 **36** 处 / B 组 **42** 处；
   旧 stitch（只试 n=3,2）命中 **0** 次；
   工作区在制品的「停用词安全阀」把其中 **15 / 18** 处挡掉了
   ⇒ 只剩 21 / 24 处会被删 ⇒ **漏掉一半以上的真缺陷**。

   而被挡掉的那些**全是真缺陷**（切点正好落在词中间）：
     ...our strategy will and has | has been to maximize...
     ...the scale is | is very important...
     ...So | So this was just a summary...
   ⇒ 停用词安全阀**方向错了**（把真缺陷当成了真内容）。

🔴 **那真内容误删的风险在哪**？
   「I want this | this is it」—— 前段末尾词 == 后段开头词 ⇒ 若是功能词，
   更可能是**真内容**（口语里功能词重复很常见），若是内容词，
   更可能是**切点穿词**。
   ⇒ **判据不该是「词表」，而该是「这个重复能否用切点穿词解释」**。

🔴 **本脚本的候选判据**（都基于**可观测特征**，不依赖外部模型）：
   ① **音节/词形一致性**：重复词的大小写形态是否一致（`will | will` vs
      `Will | will`）；ASR 同一词被切两半时，两边**通常完全一致**（含大小写）。
   ② **前后段的长上下文相似度**：切点穿词 ⇒ 前段末尾与后段开头的
      **非重复部分**应该高度相关（同一句话被切成两半）。
   ③ **标点边界**：重复词前面（前段末尾）若有句末标点（. ? !）⇒ 更可能是
      **真内容**（上一句说完了，新句又说了同一个词）；若无标点 ⇒ 更可能是
      切点穿词（同一句被切开）。

本脚本在 **A/B 两组真实产物**上，逐个候选判据算：
  - 命中（该删的）数
  - 漏删（真缺陷未删）数
  - 误删（真内容被删）数 —— 以「人工可判读的样例」列出
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


def tail_punct(text):
    """前段末尾的最后一个字符是不是句末标点。"""
    t = (text or '').rstrip()
    return bool(t) and t[-1] in '.?!。！？'


def case_shape(w):
    """词的大小写形态：'lower' / 'Capital' / 'ALLCAP' / 'other'。"""
    if not w:
        return 'empty'
    if w.isupper() and len(w) > 1:
        return 'ALLCAP'
    if w[0].isupper():
        return 'Capital'
    return 'lower'


def collect(name):
    p = os.path.join(AB_DIR, 'segments_%s.json' % name)
    d = json.load(open(p, encoding='utf-8'))
    segs = [s for s in d['segments'] if (s.get('text') or '').strip()]
    cases = []
    for i in range(1, len(segs)):
        prev, cur = segs[i - 1], segs[i]
        pt = prev.get('text') or ''
        ct = cur.get('text') or ''
        pw = pt.split()
        cw = ct.split()
        if not pw or not cw:
            continue
        if norm_word(pw[-1]) != norm_word(cw[0]):
            continue
        cases.append(dict(
            rule=prev.get('rule'),
            prev_word=pw[-1], cur_word=cw[0],
            same_case=(pw[-1] == cw[0]),
            shape_prev=case_shape(pw[-1]), shape_cur=case_shape(cw[0]),
            tail_punct=tail_punct(pt),
            prev_tail=pt[-60:], cur_head=ct[:60],
        ))
    return cases


def main():
    all_cases = {}
    for name in ('A', 'B'):
        cases = collect(name)
        all_cases[name] = cases
        print('═══ %s 组：n=1 重复共 %d 处 ═══' % (name, len(cases)))
        print()
        print('  ① 两词**完全一致**（含大小写）：%d / %d'
              % (sum(1 for c in cases if c['same_case']), len(cases)))
        print('  ② 前段末尾是句末标点（. ? !）：%d / %d'
              % (sum(1 for c in cases if c['tail_punct']), len(cases)))
        print()
        print('  交叉表：')
        tab = {}
        for c in cases:
            k = (c['same_case'], c['tail_punct'])
            tab[k] = tab.get(k, 0) + 1
        print('     same_case \\ tail_punct |  有标点  无标点')
        for sc in (True, False):
            a = tab.get((sc, True), 0)
            b = tab.get((sc, False), 0)
            print('     %-19s |  %5d  %5d' % (sc, a, b))
        print()
        # 无标点 + 完全一致 ⇒ 高置信「切点穿词」
        strong = [c for c in cases if (not c['tail_punct']) and c['same_case']]
        print('  ③ 强判据（**无标点** 且 **两词完全一致**）⇒ %d / %d'
              % (len(strong), len(cases)))
        print('     样例：')
        for c in strong[:8]:
            print('       [%-9s] %-12s ...%s | %s...'
                  % (c['rule'], c['prev_word'], c['prev_tail'][-42:],
                     c['cur_head'][:42]))
        print()
        weak = [c for c in cases if c not in strong]
        print('     弱判据未覆盖的 %d 处：' % len(weak))
        for c in weak[:12]:
            print('       [%-9s] %-12s same=%-5s punct=%-5s ...%s | %s...'
                  % (c['rule'], c['prev_word'], c['same_case'], c['tail_punct'],
                     c['prev_tail'][-38:], c['cur_head'][:38]))
        print()

    op = os.path.join(HERE, 'app024_seam_guard_design.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(all_cases, f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
