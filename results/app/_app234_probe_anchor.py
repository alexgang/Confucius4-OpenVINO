#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · **探针**：定位「锚点命中 2 次」的精确机制。

🔴 为什么要探针：§233 的 e2e 复核 23/23 全 PASS，但它测的是
**「删掉 v2.6 段后的影子包」**（把整段 v2.6 内容切掉）
⇒ 锚点落在 `## v2.5 改动说明`；
而**真实的 v2.7 成包路径**是把 **v2.6 的 README 原样 robocopy 过去**
⇒ 锚点落在 `## v2.6 改动说明`（v2.6 包里有**两个**）
⇒ 两者路径**不同** ⇒ §233 的测法覆盖不到真实路径。

本探针只读真包，不写任何东西。
"""
from __future__ import annotations

import io
import os
import re
import sys

REAL = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.6'
REAL2 = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def main() -> int:
    zh = os.path.join(REAL, 'README_zh.md')
    t = read(zh)
    print('=== 真包 v2.6 README_zh.md ===')
    print('CRLF? %s  (bytes=%d)'
          % ('\r\n' in t, len(t.encode('utf-8'))))
    lines = t.split('\n')
    for i, l in enumerate(lines[:8]):
        print('  line %d: %r' % (i + 1, l))

    rx = re.compile(r'^##\s+v(\d+(?:\.\d+)+)\s+改动说明\s*$', re.M)
    ms = list(rx.finditer(t))
    print()
    print('=== 行锚定匹配（_ZH_SEC_RE，同步器用的口径）===')
    for m in ms[:6]:
        print('  %-24s @%d' % (repr(m.group(0)), m.start()))

    print()
    print('=== apply_file 的唯一性判据用的是 text.count(old)（**子串**计数）===')
    for a in ('## v2.6 改动说明', '## v2.5 改动说明', '## v2.4 改动说明'):
        line_n = sum(1 for m in ms if m.group(0) == a)
        print('  %-20s 行数=%d  子串数=%d  %s'
              % (a, line_n, t.count(a),
                 '⇒ >1 ⇒ apply_file FAIL' if t.count(a) > 1 else ''))

    # ── 复现 §233 的影子包做法，看它为什么没踩到 ────────────────
    m = re.search(r'^## v2\.6 改动说明\n', t, re.M)
    m2 = re.search(r'^## v2\.5 改动说明\n', t[m.end():], re.M)
    shadow = t[:m.start()] + t[m.end() + m2.start():]
    print()
    print('=== §233 影子包（删掉整段 v2.6）→ 锚点落在哪 ===')
    print('  shadow 子串 count("## v2.5 改动说明") = %d' % shadow.count('## v2.5 改动说明'))
    print('  shadow 子串 count("## v2.6 改动说明") = %d' % shadow.count('## v2.6 改动说明'))
    print('  ⇒ §233 测的是「v2.5 当锚点」的路径；')
    print('    真实 v2.7 路径是「v2.6 当锚点」（v2.6 包里有 2 个）⇒ 命中 2 次 ⇒ FAIL')

    # ── 真实 v2.7 路径：把 v2.6 的 README 原样复制（robocopy）────
    print()
    print('=== 真实 v2.7 路径（robocopy v2.6 ⇒ v2.7）===')
    print('  锚点 = ## v2.6 改动说明；子串 count = %d ⇒ apply_file 报「命中 2 次」'
          % t.count('## v2.6 改动说明'))

    # ── v2.5 的历史遗留：带后缀的标题让子串计数也为 2 ───────────
    zh5 = os.path.join(REAL2, 'README_zh.md')
    t5 = read(zh5)
    print()
    print('=== v2.5 包的 README_zh.md（看带后缀标题的历史形态）===')
    for i, l in enumerate(t5.split('\n')[:8]):
        if '改动说明' in l or i < 5:
            print('  line %d: %r' % (i + 1, l))
    print('  子串 count("## v2.5 改动说明") = %d'
          % t5.count('## v2.5 改动说明'))
    print('  行锚定命中数 = %d'
          % sum(1 for m in rx.finditer(t5) if m.group(0) == '## v2.5 改动说明'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
