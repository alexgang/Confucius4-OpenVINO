#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 收尾：**去掉重复的 §131 区块**（上一次「中止前已写盘」留下的）。

🔴 **事实**：`_app130_update_sec131_asr041.py` 在**上一轮**里，
  `§131` 正文**已经被替换过一次** ⇒ 随后又追加了一次 ⇒ 出现**两个 `### §131`**。
  ⇒ 本脚本：**保留第一个**（较旧、正文是 ASR-041 对齐前的版本）
  ⇒ 用**最新的** `_app130_sec131_body.md` **替换**它 ⇒ 删掉第二个。

🔴 **复核**：写后 `### §131` **有且只有一个** ＋ §130 逐字未变 ＋ 限额内。
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

    # 🔴 §130 的标题与正文（**必须逐字不变**）
    m130 = re.search(r'(?m)^(### §130 [^\n]*)$', text)
    assert m130, '找不到 §130'
    idx = m130.end()
    nxt = re.search(r'(?m)^### ', text[idx:])
    end130 = idx + (nxt.start() if nxt else len(text) - idx)
    sec130 = text[m130.start():end130]

    # ── 找全部 `### §131` 的位置 ──
    ms = list(re.finditer(r'(?m)^### §131 [^\n]*$', text))
    print('找到 %d 个 §131 区块' % len(ms))
    if len(ms) < 2:
        print('没有重复 ⇒ 无需处理')
        return 0
    # 保留**第一个**的标题，删掉**其余**的整块
    first = ms[0]
    spans = []
    for i, m in enumerate(ms):
        s = m.start()
        e = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        spans.append((s, e))
    # 🔴 从**后往前**删（避免下标错位）
    for s, e in reversed(spans[1:]):
        text = text[:s] + text[e:]
    # ── 用最新的 §131 正文替换**第一个**的正文 ──
    m = re.search(r'(?m)^(### §131 [^\n]*)$', text)
    tail_start = m.end()
    nxt = re.search(r'(?m)^### ', text[tail_start:])
    tail_end = tail_start + (nxt.start() if nxt else len(text) - tail_start)
    new_body = read(os.path.join(HERE, '_app130_sec131_body.md'))
    new_body = '\n' + new_body.lstrip('\n')
    out = text[:tail_start] + new_body + text[tail_end:]

    for _ in range(8):
        b = len(out.encode('utf-8'))
        nl = out.count('\n') + 1
        n2 = re.sub(r'(?m)^已压缩: 本文件 \d+ B / \d+ 行',
                    '已压缩: 本文件 %d B / %d 行' % (b, nl), out, count=1)
        if n2 == out:
            break
        out = n2
    b = len(out.encode('utf-8'))
    nl = out.count('\n') + 1
    print('去重后：%d B / %d 行（限额 %d B / %d 行）'
          % (b, nl, MAX_BYTES, MAX_LINES))
    if b > MAX_BYTES or nl > MAX_LINES:
        print('!! 仍超限 ⇒ 中止（不写盘）')
        return 4

    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)

    after = read(STATUS)
    n131 = len(re.findall(r'(?m)^### §131 ', after))
    assert n131 == 1, '§131 仍有 %d 个' % n131
    m2 = re.search(r'(?m)^(### §130 [^\n]*)$', after)
    i2 = m2.end()
    nx = re.search(r'(?m)^### ', after[i2:])
    e2 = i2 + (nx.start() if nx else len(after) - i2)
    assert after[m2.start():e2] == sec130, '§130 被改 ⇒ 中止'
    assert 'asr_spk_window' in after, '§131 未更新 ⇒ 中止'
    print('写后复核通过：%d B / %d 行；§131 **有且只有一个**；§130 逐字未变'
          % (b, nl))
    print('SHA256 %s → %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
