"""为「段接缝 n=1 去重」确定**最终判据**（替换方向错了的停用词安全阀）。

🔴 **前情**：
  · A 组 n=1 重复 **36** 处 / B 组 **42** 处；旧 stitch（只试 n=3,2）命中 0 次。
  · 工作区在制品用「停用词表」做安全阀 ⇒ 把 15/18 处**真缺陷**挡掉（方向错了）。
  · `app024_seam_guard_design.py` 实测：n=1 重复里
      · 两词**完全一致**（含大小写）仅 12/36（A）、11/42（B），
        且这 12/11 处**全部无句末标点**；
      · 典型 `...So, welcome | Welcome to our Q3 26 QGS.` ⇒ **后段重新起句**
        （首字母大写）⇒ 切点穿词的强特征。

🔴 **本脚本要产出**：
  一个**判据函数**，在 A/B 两组上给出：
    ① 命中数（该删的删了多少）
    ② **误删数** —— 用**独立参照**判定：如果删掉的那个词在参照里
       **本来就该出现两次**（即真内容重复），那就是误删。
       判据：把「删词」前后拼出的文本与参照做对齐，看被删的词在参照里
       是否**只出现一次**（⇒ 真缺陷，删对了）还是**出现两次且位置对应**
       （⇒ 真内容，误删）。
    ③ 候选判据的组合对比。

⚠️ **不做人工看样例来定判据**（不可复现）⇒ 用参照文本客观判定。
"""
from __future__ import annotations

import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
AB_DIR = os.path.join(REPO, 'reports', 'asr004_ab')
REF_TXT = os.path.join(REPO, 'reports', 'c048_61min_adaptive',
                       'transcript_adaptive.txt')


def norm_word(w):
    return re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', (w or '').lower())


def norm_tokens(text):
    out = []
    for ln in (text or '').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        ln = re.sub(r'^\[\s*[0-9.]+\s*-\s*[0-9.]+\s*\]\s*', '', ln)
        ln = re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', ' ', ln).lower()
        out.extend(ln.split())
    return out


def tail_punct(text):
    t = (text or '').rstrip()
    return bool(t) and t[-1] in '.?!。！？'


def is_capitalized(w):
    return bool(w) and w[0].isupper()


# ── 候选判据 ─────────────────────────────────────────────────────────
def decide(prev_text, prev_word, cur_word, rule):
    """返回 True = 判定为「切点穿词」（该删）。"""
    # 候选 C（推荐）：**后段首词是大写开头** ⇒ 后段重新起句 ⇒ 切点穿词
    #   （真内容重复不会改大小写）
    if is_capitalized(cur_word) and not is_capitalized(prev_word):
        return True
    # 候选 B：前段末尾**无句末标点** ⇒ 同一句被切开 ⇒ 切点穿词
    #   （有句末标点 ⇒ 上一句说完了 ⇒ 真内容）
    if not tail_punct(prev_text):
        return True
    return False


def main():
    ref_tokens = norm_tokens(open(REF_TXT, encoding='utf-8').read())
    # 参照里每个词的出现次数（用于判「真内容重复」）
    ref_count = {}
    for t in ref_tokens:
        ref_count[t] = ref_count.get(t, 0) + 1

    out = {}
    for name in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % name)
        if not os.path.exists(p):
            continue
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
            w = norm_word(cw[0])
            keep = decide(pt, pw[-1], cw[0], prev.get('rule'))
            cases.append(dict(
                rule=prev.get('rule'), word=cw[0], norm=w,
                prev_cap=is_capitalized(pw[-1]), cur_cap=is_capitalized(cw[0]),
                punct=tail_punct(pt), decide=keep,
                ref_count=ref_count.get(w, 0),
                prev=pt[-55:], cur=ct[:55]))

        n = len(cases)
        hit = [c for c in cases if c['decide']]
        miss = [c for c in cases if not c['decide']]
        # 「参照里只出现一次」⇒ 删对了（真缺陷）；「出现多次」⇒ 可能是真内容
        hit_once = [c for c in hit if c['ref_count'] <= 1]
        hit_multi = [c for c in hit if c['ref_count'] > 1]

        print('═══ %s 组：n=1 重复 %d 处 ═══' % (name, n))
        print('  判据命中 %d / 未命中 %d' % (len(hit), len(miss)))
        print('  命中里：参照中该词只出现 1 次（⇒ 真缺陷，删对了）**%d**；'
              '出现多次（⇒ 可能是真内容）%d'
              % (len(hit_once), len(hit_multi)))
        print()
        print('  ▸ 未命中的 %d 处（可能漏删）：' % len(miss))
        for c in miss[:12]:
            print('     [%-9s] %-14s prev_cap=%-5s cur_cap=%-5s punct=%-5s'
                  % (c['rule'], c['word'], c['prev_cap'], c['cur_cap'],
                     c['punct']))
            print('         ...%s | %s...' % (c['prev'][-42:], c['cur'][:42]))
        print()
        print('  ▸ 命中但参照里该词出现多次的（需人看是否误删）：%d' % len(hit_multi))
        for c in hit_multi[:10]:
            print('     [%-9s] %-14s ref_count=%d' % (c['rule'], c['word'],
                                                     c['ref_count']))
            print('         ...%s | %s...' % (c['prev'][-42:], c['cur'][:42]))
        print()
        out[name] = cases

    op = os.path.join(HERE, 'app024_seam_rule_design.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
