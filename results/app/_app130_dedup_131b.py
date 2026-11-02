#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 收尾：去掉**相邻重复**的 `### §131` 标题 + 它后面那份**旧正文**。

🔴 **事实**：上一轮脚本把新正文插在**第一个** `### §131` 之后，
  而**第二个** `### §131`（及其旧正文）仍留在后面 ⇒ 出现「两个相邻的 §131」。
⇒ 本脚本：把**第一个**标题之后的**第二个标题 + 旧正文**整块删掉
  ⇒ 只留**一个** §131（标题 ＋ 最新正文）。

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

    # 🔴 §130 标题 ＋ 正文（必须逐字不变）
    m130 = re.search(r'(?m)^(### §130 [^\n]*)$', text)
    assert m130, '找不到 §130'
    i = m130.end()
    nx = re.search(r'(?m)^### ', text[i:])
    e130 = i + (nx.start() if nx else len(text) - i)
    sec130 = text[m130.start():e130]

    ms = list(re.finditer(r'(?m)^### §131 [^\n]*$', text))
    print('找到 %d 个 §131 标题' % len(ms))
    if len(ms) < 2:
        print('没有重复 ⇒ 无需处理')
        return 0
    # 🔴 删掉**第二个**标题及其后**到下一个 `### §` 或文件尾**的全部内容
    #   （第二段是**旧正文**，要整块删）
    s2 = ms[1].start()
    nx2 = re.search(r'(?m)^### ', text[ms[1].end():])
    e2 = ms[1].end() + (nx2.start() if nx2 else len(text) - ms[1].end())
    out = text[:s2] + text[e2:]

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
    assert 'asr_spk_window' in after, '§131 未含 ASR-041 对齐说明 ⇒ 中止'
    print('写后复核通过：%d B / %d 行；§131 **有且只有一个**；§130 逐字未变'
          % (b, nl))
    print('SHA256 %s → %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
