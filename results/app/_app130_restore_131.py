#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 收尾：把 §131 的**正文**写回（标题已在）⇒ 用 `_app130_sec131_body.md`。

🔴 **为什么**：去重脚本把「第二个 §131 标题 + 它后面的旧正文」整块删掉了
  ⇒ 连**正文**一起没了（只剩标题）⇒ 本脚本把**最新正文**补回标题之后。
"""
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


def main():
    text = read(STATUS)
    before = hashlib.sha256(text.encode('utf-8')).hexdigest()
    heads = list(re.finditer(r'(?m)^### §131 [^\n]*$', text))
    print('找到 %d 个 §131 标题' % len(heads))
    if len(heads) != 1:
        print('!! §131 标题不唯一 ⇒ 先跑去重脚本')
        return 2
    m = heads[0]
    body = read(os.path.join(HERE, '_app130_sec131_body.md'))
    # 🔴 正文文件**自带 `### §131` 标题行** ⇒ 直接追加会造出**第二个**标题
    #   ⇒ 这里**剥掉标题行**（只留正文）。
    lines = body.split('\n')
    if lines and lines[0].startswith('### §131'):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines = lines[1:]
        body = '\n'.join(lines)
    body = '\n' + body.lstrip('\n')
    # 🔴 若标题后已经有正文 ⇒ 先删掉旧正文
    tail = text[m.end():]
    nxt = re.search(r'(?m)^### |^## ', tail)
    tail_end = m.end() + (nxt.start() if nxt else len(tail))
    out = text[:m.end()] + body + text[tail_end:]
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
    print('写入后：%d B / %d 行（限额 %d B / %d 行）' % (b, nl, MAX_BYTES, MAX_LINES))
    if b > MAX_BYTES or nl > MAX_LINES:
        print('!! 仍超限 ⇒ 中止（不写盘）')
        return 4
    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)
    after = read(STATUS)
    n131 = len(re.findall(r'(?m)^### §131 ', after))
    assert n131 == 1, '§131 标题不唯一（%d）' % n131
    for k in ('asr_spk_window', 'app227', 'app228', '_fq3tts_env',
              'MACHINE_LOCK', 'D1', 'D2', 'D3', 'D4'):
        assert k in after, '§131 正文缺 %r' % k
    print('写后复核通过：%d B / %d 行；§131 标题唯一；正文关键项全在' % (b, nl))
    print('SHA256 %s -> %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
