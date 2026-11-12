#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app516_verify_status_sec186.py —— §186 落盘后的**独立**复核（读盘 + git HEAD 逐字节对照）。

不 import 被测脚本、不复用它的中间变量：一切从「磁盘现状」与「git HEAD 原文」重新推导。

判据：
 1. 活文档 ≤40 000 B、≤300 行、无 CR；
 2. **归档件 == HEAD 版 STATUS 里 §184 整节**（逐字节）⇒ 归档是逐字归档，不是改写；
 3. 活文档里 §184 正文**只剩指针行**（旧正文一字不留在活文档）；
 4. **还原式复核**：把指针行换回 HEAD 的 §184 原文 ⇒ 与 HEAD 版的差异**逐条**只落在
    {头部 3 行、最近更新 +1 行、末尾追加 §186} ⇒ 旧正文一字未改；
 5. §185 整节在活文档里**逐字节 == HEAD 版**；
 6. 头部 `last_ack` == APP-105；「更新时间」为实测值形态（`Get-Date` 格式）；
 7. 纠偏文件 **SHA 仍为开工基线**（`321be59c…`）⇒ 本轮未改 reviewer 文件。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec184_20261113.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
BASE_CORR_SHA = '321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1'

R = []


def ck(name, ok, info=''):
    R.append((name, bool(ok), info))


def main():
    head = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:status/app/STATUS_APP.md'],
                          cwd=REPO, capture_output=True).stdout.decode('utf-8')
    with open(STATUS, encoding='utf-8', newline='') as f:
        cur = f.read()
    with open(ARCH, 'rb') as f:
        arch = f.read()

    # 1
    ck('size<=40000', len(cur.encode('utf-8')) <= 40000, '%d B' % len(cur.encode('utf-8')))
    ck('lines<=300', cur.count('\n') <= 300, '%d lines' % cur.count('\n'))
    ck('no CR', '\r' not in cur, 'CR=%d' % cur.count('\r'))

    # 2
    hi = head.index('## §184 ')
    hj = head.index('## §185 ')
    head_sec184 = head[hi:hj]
    ck('archive == HEAD sec184 verbatim', arch == head_sec184.encode('utf-8'),
       'arch %d B vs head %d B sha %s' % (len(arch), len(head_sec184.encode('utf-8')),
                                          hashlib.sha256(arch).hexdigest()[:16]))

    # 3
    ci = cur.index('## §184 ')
    cj = cur.index('## §185 ')
    cur_sec184 = cur[ci:cj]
    ck('live sec184 body = pointer only',
       cur_sec184.count('\n') == 2 and '本节正文已整块逐字归档' in cur_sec184
       and '## §184 执行 APP-105' in cur_sec184,
       '%d chars' % len(cur_sec184))

    # 4 还原式复核
    pointer_line = [l for l in cur_sec184.split('\n') if '本节正文已整块逐字归档' in l][0]
    restored = cur.replace(cur_sec184, head_sec184)
    import difflib
    ol, rl = head.split('\n'), restored.split('\n')
    sm = difflib.SequenceMatcher(None, ol, rl, autojunk=False)
    kinds = []
    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        r_all = '\n'.join(rl[b1:b2])
        if tag == 'replace' and a2 <= 8 and b2 <= 8 and a1 >= 3 and b1 >= 3:
            kinds.append('HEADER')
        elif (tag == 'insert' and (b2 - b1) == 1 and rl[b1].startswith('> ')
              and '巡检无新 reviewer 纠偏' in rl[b1]):
            kinds.append('RECENT_UPDATES')
        elif tag == 'insert' and '## §186' in r_all and b2 >= len(rl) - 1:
            kinds.append('APPEND_SEC186')
        else:
            kinds.append('UNEXPECTED:%s@%d:%d' % (tag, a1, a2))
    ck('restored diff only-allowed', all(k in ('HEADER', 'RECENT_UPDATES', 'APPEND_SEC186')
                                         for k in kinds) and len(kinds) == 3, str(kinds))

    # 5
    h185 = head[hj:]
    c185 = cur[cur.index('## §185 '):]
    c185 = c185[:c185.index('## §186 ')] if '## §186 ' in c185 else c185
    ck('sec185 byte-identical', c185.rstrip('\n') == h185.rstrip('\n'),
       '%d vs %d chars (rstrip\\n)' % (len(c185.rstrip('\n')), len(h185.rstrip('\n'))))

    # 6
    ck('last_ack == APP-105', cur.split('\n')[2].strip() == 'last_ack: APP-105', cur.split('\n')[2])
    m = re.match(r'^更新时间: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})$', cur.split('\n')[3])
    ck('更新时间 = Get-Date 形态', bool(m), cur.split('\n')[3])

    # 7
    corr = open(CORR, 'rb').read()
    sha = hashlib.sha256(corr).hexdigest()
    ids = re.findall(r'^##\s*(APP-\d+)', corr.decode('utf-8', errors='replace'), flags=re.M)
    ck('CORRECTIONS_APP.md SHA unchanged', sha == BASE_CORR_SHA, sha[:20])
    ck('CORRECTIONS 105 条 / max APP-105', len(ids) == 105 and max(ids) == 'APP-105',
       '%d 条 / %s' % (len(ids), max(ids)))

    print('=== 写后独立复核 ===')
    bad = 0
    for n, ok, i in R:
        print('%-32s %s  %s' % (n, 'PASS' if ok else 'FAIL', i))
        bad += 0 if ok else 1
    print('SUMMARY: %d checks, %d FAIL' % (len(R), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
