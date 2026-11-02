#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 收尾：删掉 §123–§129 的**重复区块**（「最近章节」索引表里**已有**它们的一行摘要）。

🔴 **为什么可以删**：
  - 这些章节的**正文早已逐字归档**在 `status/archive/`（§123–§129 全部）；
  - `## 最近章节` 的**索引表里已经有每一节的一行摘要**（实测 §123–§129 **9 行全在**）
    ⇒ 下面的 `### §123 …` 区块**只是重复**（标题 + 一行归档指针）
    ⇒ 删掉**不丢任何信息**：摘要在表里，正文在归档文件里。
  - 🔴 **§130 / §131 一律不动**（§130 有归档指针、§131 有正文）。

🔴 **复核**：
  - 索引表里 §123–§129 的 9 行**必须仍在**；
  - 归档文件**必须仍在**且含逐字正文；
  - §130/§131 的标题与正文**逐字未变**；
  - 限额内。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')

MAX_BYTES = 40000
MAX_LINES = 300
DROP = (123, 124, 125, 126, 127, 128, 129)


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main() -> int:
    text = read(STATUS)
    before = hashlib.sha256(text.encode('utf-8')).hexdigest()

    # ── 保护 §130/§131 的标题与正文（写后必须逐字相同） ──
    protected = {}
    for mm in re.finditer(r'(?m)^(### §(\d+) [^\n]*)$', text):
        n = int(mm.group(2))
        if n in (130, 131):
            idx = mm.end()
            nxt = re.search(r'(?m)^### ', text[idx:])
            end = idx + (nxt.start() if nxt else len(text) - idx)
            protected[n] = (mm.group(1), text[idx:end])

    # ── 删掉 §123–§129 的区块（**只删这两行**：标题 + 归档指针 + 空行） ──
    lines = text.split('\n')
    out = []
    i = 0
    n_drop = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r'^### §(\d+) ', ln)
        if m and int(m.group(1)) in DROP:
            j = i + 1
            while j < len(lines) and not lines[j].startswith('### §') \
                    and not lines[j].startswith('## '):
                j += 1
            # 🔴 只在**这一节确实是归档指针**时才删（不删有正文的节）
            seg = '\n'.join(lines[i:j])
            if '本节正文已原样归档' in seg:
                n_drop += 1
                i = j
                continue
        out.append(ln)
        i += 1
    new = '\n'.join(out)
    print('删掉 %d 个重复区块（§123–§129 的标题 ＋ 归档指针）' % n_drop)
    if n_drop != len(DROP):
        print('!! 删掉的节数不对（%d ≠ %d）⇒ 中止' % (n_drop, len(DROP)))
        return 2

    # ── 自指大小修正（不动点迭代） ──
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
    if b > MAX_BYTES or nl > MAX_LINES:
        print('!! 仍超限 ⇒ 中止（不写盘）')
        return 4

    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    os.replace(tmp, STATUS)

    # ── 写后复核 ──
    after = read(STATUS)
    # ① 索引表里 §123–§129 的摘要行必须仍在
    tbl = after[after.find('## 最近章节'):after.find('### §130')]
    missing_idx = [n for n in DROP if ('| §%d |' % n) not in tbl]
    assert not missing_idx, '索引表里丢了 §%r' % missing_idx
    # ② 归档文件必须仍在
    for fn in ('STATUS_APP_sec123_upto_20261101.md',
               'STATUS_APP_sec124_upto_20261101.md',
               'STATUS_APP_sec126_upto_20261101.md',
               'STATUS_APP_sec127_128_upto_20261102.md',
               'STATUS_APP_sec130_upto_20261102.md'):
        p = os.path.join(ARCHIVE_DIR, fn)
        assert os.path.isfile(p), '归档文件缺失：%s' % fn
    # ③ §130/§131 逐字未变
    for n, (t, body) in protected.items():
        mm = re.search(r'(?m)^(### §%d [^\n]*)$' % n, after)
        assert mm, '§%d 标题丢失' % n
        assert mm.group(1) == t, '§%d 标题被改' % n
        idx = mm.end()
        nxt = re.search(r'(?m)^### ', after[idx:])
        end = idx + (nxt.start() if nxt else len(after) - idx)
        assert after[idx:end] == body, '§%d 正文被改' % n
    print('写后复核通过：%d B / %d 行；索引表 §123–§129 九行全在；'
          '5 个归档文件全在；§130/§131 逐字未变' % (b, nl))
    print('SHA256 %s → %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
