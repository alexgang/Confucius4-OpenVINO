#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 压缩后的**独立**写后复核（另起脚本，不 import 被检脚本）。

## 判据（全部对**磁盘现状**跑，不信任压缩脚本的自检）
1. 活文档 ≤ 40 000 B 且 ≤ 300 行（APP-052④／APP-049 硬限额）
2. 归档件**逐字**含原 §211–§227 字节区间（用写前备份的字节比）
3. 归档件头部声明的 SHA256／字节数与**实际归档块**一致
4. **还原式复核**：把活文档的指针行换回原区间 ⇒ 逐字节等于写前备份
5. §135–§232 每个节号都仍被「交代」（活文档标题行 或 归档件标题行）
6. `last_ack` 唯一且仍 = APP-133
7. 归档件内所有 `status/...` 指针目标存在（14/14）
8. 头部「已压缩」索引含新归档件路径（reviewer 可追溯）
9. **反证组**：把「归档块」换成**被改动过**的字节 ⇒ 判据必须 FAIL
   （证明判据有鉴别力，不是恒 PASS）
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(
    REPO, 'status', 'archive', 'STATUS_APP_sec211_227_headers_20261125.md')
BAK = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app233')

SEC_RE = re.compile(rb'^## \xc2\xa7(\d+)', re.M)

n_ok = 0
n_bad = 0


def chk(name, cond, detail=''):
    global n_ok, n_bad
    if cond:
        n_ok += 1
        print('  [PASS] %s%s' % (name, ('｜' + detail) if detail else ''))
    else:
        n_bad += 1
        print('  [FAIL] %s%s' % (name, ('｜' + detail) if detail else ''))


def main() -> int:
    raw = open(STATUS, 'rb').read()
    bak = open(BAK, 'rb').read()
    arch = open(ARCHIVE, 'rb').read()

    print('[post-write] 活文档 %d B / 40000 B｜%d 行 / 300 行'
          % (len(raw), raw.count(b'\n')))
    print('[post-write] 归档件 %d B' % len(arch))

    # 1) 硬限额
    chk('活文档 ≤ 40000 B', len(raw) <= 40000, '%d B' % len(raw))
    chk('活文档 ≤ 300 行', raw.count(b'\n') <= 300, '%d 行' % raw.count(b'\n'))

    # 2) 归档块逐字：从写前备份里重新切出区间
    hits = [(m.start(), int(m.group(1))) for m in SEC_RE.finditer(bak)]
    start = end = None
    for i, (off, num) in enumerate(hits):
        if num == 211:
            start = off
        if num == 228:
            end = hits[i][0]
    chk('写前备份里能定位 §211..§227 区间', start is not None and end is not None,
        '[%s, %s)' % (start, end))
    block = bak[start:end]
    chk('归档件逐字含原区间字节', block in arch, '%d B' % len(block))
    chk('归档件 = 头部 + 原区间（无多余改动）',
        arch.endswith(block), '尾部 %d B' % len(block))

    # 3) 归档件头部声明 vs 实际
    m = re.search(rb'SHA256 `([0-9a-f]{64})`\xe2\x80\x94?/\xe2\x80\x94?(\d+) B', arch)
    if not m:
        m = re.search(rb'SHA256 `([0-9a-f]{64})`[^0-9]{0,12}(\d+) B', arch)
    if m:
        decl_sha = m.group(1).decode()
        decl_n = int(m.group(2))
        chk('头部声明 SHA256 与实际块一致',
            decl_sha == hashlib.sha256(block).hexdigest(), decl_sha[:16])
        chk('头部声明字节数与实际块一致', decl_n == len(block),
            '%d vs %d' % (decl_n, len(block)))
    else:
        chk('归档件头部可解析（SHA256＋字节数）', False, '正则未命中')

    # 4) 还原式复核
    PTR_MARK = '> 🔴 **§211–§227 标题行＋指针行已整块逐字归档**'.encode('utf-8')
    ptr = re.search(re.escape(PTR_MARK) + rb'[^\n]*\n', raw)
    chk('活文档有唯一指针行', bool(ptr) and len(re.findall(
        re.escape(PTR_MARK), raw)) == 1)
    if ptr:
        restored = raw[:ptr.start()] + block + raw[ptr.end():]
        chk('还原式复核＝逐字节等于写前备份', restored == bak,
            '%d B vs %d B' % (len(restored), len(bak)))

    # 5) 无节丢失
    old_secs = set(int(m.group(1)) for m in SEC_RE.finditer(bak))
    new_secs = set(int(m.group(1)) for m in SEC_RE.finditer(raw))
    arc_secs = set(int(m.group(1)) for m in SEC_RE.finditer(arch))
    chk('每个旧节号都被交代（活文档∪归档件）', not (old_secs - new_secs - arc_secs),
        'lost=%s' % sorted(old_secs - new_secs - arc_secs) or '无')
    chk('§228–§232 仍在活文档', {228, 229, 230, 231, 232} <= new_secs)

    # 6) last_ack
    la = re.findall(rb'last_ack:\s*APP-(\d+)', raw)
    chk('last_ack 唯一且仍 = APP-133', la == [b'133'], str(la))

    # 7) 指针目标全在
    ptrs = sorted(set(re.findall(r'`(status/[^`]+)`', arch.decode('utf-8'))))
    missing = [p for p in ptrs
               if not os.path.exists(os.path.join(REPO, p.replace('/', os.sep)))]
    chk('归档件内指针目标全存在', not missing, '%d 个，缺 %s'
        % (len(ptrs), missing or '无'))

    # 8) 头部索引可追溯
    chk('头部「已压缩」索引含新归档件路径',
        b'status/archive/STATUS_APP_sec211_227_headers_20261125.md' in raw)

    # 9) 反证组：篡改归档块 1 字节 ⇒ 判据 2/3/4 必须 FAIL
    print('[counter-evidence] 把归档块篡改 1 字节 ⇒ 相关判据必须 FAIL：')
    tampered = block[:10] + (b'X' if block[10:11] != b'X' else b'Y') + block[11:]
    c1 = tampered in arch
    c2 = hashlib.sha256(tampered).hexdigest() == re.search(
        rb'SHA256 `([0-9a-f]{64})`', arch).group(1).decode()
    if ptr:
        c3 = (raw[:ptr.start()] + tampered + raw[ptr.end():]) == bak
    else:
        c3 = False
    chk('反证组：篡改后「逐字含原区间」FAIL', not c1)
    chk('反证组：篡改后「头部 SHA256 一致」FAIL', not c2)
    chk('反证组：篡改后「还原式复核」FAIL', not c3)

    print('\n[summary] PASS=%d FAIL=%d' % (n_ok, n_bad))
    return 0 if n_bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
