"""诊断：新 stitch 的**停用词安全阀**把多少真缺陷挡掉了。

🔴 **背景**：`app024_seam_diag.py` 实测 A 组 n=1 命中 **36**、B 组 **42**
   （与工作区注释一致 ✅）；但 `app024_stitch_offline.py` 里新 stitch
   只消掉 **3** / **6** 次 ⇒ 差额来自「**n=1 停用词安全阀**」。

🔴 **要查清**：
   ① 被安全阀挡掉的 33 / 36 个重复词**分别是什么**；
   ② 它们是**功能词**（真内容，挡对了）还是**内容词**（真缺陷，挡错了）；
   ③ 安全阀的**正确边界**应该在哪 —— 按「词是否在停用词表」判，
      还是按「是否跨标点边界」判。
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


def load_stopwords():
    """从源码里抽 ``_STITCH_STOPWORDS``（ast，不 import 被测模块）。"""
    import ast
    src = open(os.path.join(REPO, 'live_caption', 'live_caption_app.py'),
               encoding='utf-8').read()
    tree = ast.parse(src)
    ns = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == '_STITCH_STOPWORDS':
                    exec(compile(ast.Module(body=[node], type_ignores=[]),
                                 '<sw>', 'exec'), ns)
    return ns['_STITCH_STOPWORDS']


def main():
    sw = load_stopwords()
    print('停用词表大小：%d' % len(sw))
    print()

    out = {}
    for name in ('A', 'B'):
        p = os.path.join(AB_DIR, 'segments_%s.json' % name)
        if not os.path.exists(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        segs = [s for s in d['segments'] if (s.get('text') or '').strip()]

        blocked = []       # 被安全阀挡掉的（停用词）
        allowed = []       # 真内容词 ⇒ 会删
        for i in range(1, len(segs)):
            prev, cur = segs[i - 1], segs[i]
            pt = prev.get('text') or ''
            ct = cur.get('text') or ''
            pw = [norm_word(x) for x in pt.split()[-3:]]
            cw_words = ct.split()
            cw = [norm_word(x) for x in cw_words]
            if not pw or not cw:
                continue
            if pw[-1] == cw[0]:
                w = cw_words[0]
                nw = norm_word(w)
                rec = dict(rule=prev.get('rule'), word=w, norm=nw,
                           prev=pt[-70:], cur=ct[:70])
                if nw in sw:
                    blocked.append(rec)
                else:
                    allowed.append(rec)

        print('═══ %s 组 ═══' % name)
        print('  n=1 重复共 %d 处 ⇒ 停用词（被安全阀挡）**%d** / 内容词（会删）**%d**'
              % (len(blocked) + len(allowed), len(blocked), len(allowed)))
        print()
        print('  ▸ 被挡掉的（判为「功能词重复 = 真内容」）—— 词频：')
        freq = {}
        for r in blocked:
            freq[r['norm']] = freq.get(r['norm'], 0) + 1
        for w, c in sorted(freq.items(), key=lambda x: -x[1]):
            print('       %-14s × %d' % (w, c))
        print()
        print('  ▸ 会删掉的（内容词 = 真缺陷）：')
        for r in allowed:
            print('       [%-9s] %-14s ...%s | %s...'
                  % (r['rule'], r['word'], r['prev'][-45:], r['cur'][:45]))
        print()
        out[name] = dict(blocked=blocked, allowed=allowed)

    op = os.path.join(HERE, 'app024_stopword_audit.json')
    with open(op, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('证据落盘：%s' % op)
    return 0


if __name__ == '__main__':
    sys.exit(main())
