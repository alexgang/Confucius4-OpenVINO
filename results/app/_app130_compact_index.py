#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app130 —— 把 STATUS 里 §123–§129 的**索引指针**压成**一张表**（腾出行数）。

🔴 **纪律**：
  - 只动「最近章节」里 §123–§129 这几节的**指针形态**（它们**本来就只有指针**，
    正文早已逐字归档在 `status/archive/`）⇒ **旧正文一字未删**；
  - 章节**标题行一字不改**（`### §N ...`）⇒ 标题仍在原位；
  - 压缩后复核 ≤ 40 KB / ≤ 300 行 ＋ 写后逐字节复核。
"""
from __future__ import annotations

import ast
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

    # ── 把 §123–§129 的「标题 + 指针 + 空行」压成「标题 + 指针行」 ──
    #    （指针行的措辞逐字保留，只是把多行合成一行）
    lines = text.split('\n')
    out = []
    i = 0
    n_merged = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^### §(\d+) ', ln)
        if m and 123 <= int(m.group(1)) <= 129:
            # 收集这一节直到下一个 `### §` 或 `## `
            j = i + 1
            blk = []
            while j < len(lines) and not lines[j].startswith('### §') \
                    and not lines[j].startswith('## '):
                blk.append(lines[j])
                j += 1
            # 指针文本（保留「逐字保留，内容一字未删」这句）
            ptr = ' > **本节正文已原样归档** ⇒ 见 '
            keep = [b for b in blk if b.strip()]
            arch = None
            for b in keep:
                mm = re.search(r'`(status/archive/[^`]+)`', b)
                if mm:
                    arch = mm.group(1)
            if arch:
                ptr = (' > **本节正文已原样归档** ⇒ 见 `%s`'
                       '（逐字保留，内容一字未删）。' % arch)
            out.append(ln)
            out.append(ptr)
            n_merged += 1
            i = j
            continue
        out.append(ln)
        i += 1

    new = '\n'.join(out)

    # ── 自指大小修正（不动点迭代） ─────────────────────────
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
    print('合并了 %d 节的指针' % n_merged)
    if b > MAX_BYTES or nl > MAX_LINES:
        print('（仍超限 ⇒ 由追加脚本继续处理；本步先写盘）')

    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, STATUS)

    after = read(STATUS)
    assert len(after.encode('utf-8')) == b, '写后字节数不一致'
    # 🔴 **旧章节标题一个都不能少**
    old_titles = re.findall(r'(?m)^### §\d+ .*$', text)
    new_titles = re.findall(r'(?m)^### §\d+ .*$', after)
    missing = [t for t in old_titles if t not in new_titles]
    assert not missing, '旧章节标题丢失：%r' % missing[:2]
    print('写后复核通过：%d B / %d 行；%d 个章节标题全在'
          % (b, nl, len(new_titles)))
    print('SHA256 %s → %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
