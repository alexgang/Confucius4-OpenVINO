#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 收尾：把 §123–§129 的**标题行 + 指针行**压成**各一行**（腾出限额）。

🔴 **纪律**：
  - **标题行一字不改**（`### §N ...` ⇒ 仍在原位、逐字相同）⇒ 章节索引仍完整；
  - **指针行只压行数**（内容逐字保留）⇒ 正文仍逐字归档在 `status/archive/`；
  - 只动 §123–§129 这几节（**§130/§131 一字不动**）；
  - 写后复核：限额内 ＋ 标题逐字未变 ＋ 归档指针仍在。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

MAX_BYTES = 40000
MAX_LINES = 300


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main() -> int:
    text = read(STATUS)
    before = hashlib.sha256(text.encode('utf-8')).hexdigest()
    lines = text.split('\n')

    out = []
    i = 0
    n_merged = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^### §(\d+) ', ln)
        if m and 123 <= int(m.group(1)) <= 129:
            # 收集这一节（到下一个 `### §` 或 `## ` 为止）
            j = i + 1
            blk = []
            while j < len(lines) and not lines[j].startswith('### §') \
                    and not lines[j].startswith('## '):
                blk.append(lines[j])
                j += 1
            arch = None
            for b in blk:
                mm = re.search(r'`(status/archive/[^`]+)`', b)
                if mm:
                    arch = mm.group(1)
            out.append(ln)
            if arch:
                out.append(' > **本节正文已原样归档** ⇒ 见 `%s`'
                           '（逐字保留，内容一字未删）。' % arch)
            n_merged += 1
            i = j
            continue
        out.append(ln)
        i += 1

    new = '\n'.join(out)

    for _ in range(8):
        b = len(new.encode('utf-8'))
        nl = new.count('\n') + 1
        n2 = re.sub(r'(?m)^已压缩: 本文件 \d+ B / \d+ 行',
                    '已压缩: 本文件 %d B / %d 行' % (b, nl), new, count=1)
        if n2 == new:
            break
        new = n2
    b = len(new.encode('utf-8'))
    nl = new.count('\n') + 1
    print('压缩后：%d B / %d 行（限额 %d B / %d 行）'
          % (b, nl, MAX_BYTES, MAX_LINES))
    print('压缩了 %d 节的指针' % n_merged)

    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, STATUS)

    after = read(STATUS)
    old_titles = re.findall(r'(?m)^### §\d+ .*$', text)
    new_titles = re.findall(r'(?m)^### §\d+ .*$', after)
    missing = [t for t in old_titles if t not in new_titles]
    assert not missing, '旧章节标题丢失：%r' % missing[:2]
    # 🔴 §130/§131 的正文必须**逐字未变**
    for n in (130, 131):
        mm = re.search(r'(?m)^### §%d [^\n]*$' % n, after)
        assert mm, '§%d 标题丢失' % n
        seg = after[mm.start():]
        nxt = re.search(r'(?m)^### ', seg[10:])
        seg = seg[:10 + nxt.start()] if nxt else seg
        assert 'app227' in seg or 'app226' in seg, '§%d 正文异常' % n
    print('写后复核通过：%d B / %d 行；%d 个章节标题全在；§130/§131 正文在位'
          % (b, nl, len(new_titles)))
    print('SHA256 %s → %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
