#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-233 轮 · 修压缩时写入的**指针行重复行尾**（1 字节）。

## 🔴 写后独立复核抓到的问题（不是脚本自检，是另起脚本复核抓到的）
压缩脚本里指针行写成了 `ptr_line`（**自带**结尾 `\\n`）**再补一个** `eol`
⇒ 落盘是 `ptr_text\\n\\n` ⇒ **多 1 字节**＋多出一个空行。
⇒ 写后复核的「还原式复核」判据**如实 FAIL**（39 805 B vs 39 804 B）⇒ 判据有鉴别力。

## 🔴 为什么正确行尾是**单个 LF**（不是 CRLF）
实测写前备份里 §211–§227 区间的**最后一行**（§227 指针行）本来就以**孤立 LF** 结束
（区间内 CRLF 37 / LF 总数 38 ⇒ 唯一那个孤立 LF 就在块尾），
而紧随其后的 `## §228` 也是 LF 段 ⇒
**指针行沿用单个 LF** 既与被替换处的边界一致，也与相邻的 §228 段一致。

## 修法
把 `ptr_text` 之后**连续两个** `\\n` 删掉**一个** ⇒ `ptr_text\\n`。
删 1 字节 ⇒ 还原式复核应逐字节等于写前备份。

## 写前真不变量（FAIL ⇒ 零改动）
- `ptr_text` 在全文**唯一命中**
- 其后紧跟**恰好两个** `\\n`（不是 CRLF）
- 删 1 字节后：孤立 LF 少 1、CRLF 数**不变**、字节数 -1
- 删 1 字节后：**还原式复核逐字节 == 写前备份**
- 归档块仍逐字在归档件中；`last_ack` 仍唯一且 = APP-133
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
import tempfile

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(
    REPO, 'status', 'archive', 'STATUS_APP_sec211_227_headers_20261125.md')
BAK = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app233')

SEC_RE = re.compile(rb'^## \xc2\xa7(\d+)', re.M)
PTR_MARK = '> 🔴 **§211–§227 标题行＋指针行已整块逐字归档**'.encode('utf-8')

n_ok = n_bad = 0


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

    # ── 定位指针行（只取文本，不含行尾）───────────────────────────
    m = re.search(re.escape(PTR_MARK) + rb'[^\n]*', raw)
    if not m:
        print('[FAIL] 找不到指针行')
        return 1
    txt_end = m.end()
    after = raw[txt_end:txt_end + 4]
    print('[inspect] 指针文本后紧跟：%r' % after)

    print('[pre-write] 真不变量：')
    chk('指针文本唯一命中',
        len(re.findall(re.escape(PTR_MARK), raw)) == 1)
    chk('其后紧跟恰好两个 \\n', after[:2] == b'\n\n',
        repr(after[:2]))
    chk('第三个字节不是 \\n（确认只有两个）',
        after[2:3] != b'\n', repr(after[2:3]))

    # ── 新文本：删掉重复的那个 \\n ─────────────────────────────────
    new_raw = raw[:txt_end + 1] + raw[txt_end + 2:]
    chk('新文本比原文少 1 字节', len(new_raw) == len(raw) - 1,
        '%d → %d' % (len(raw), len(new_raw)))
    chk('CRLF 数不变', new_raw.count(b'\r\n') == raw.count(b'\r\n'),
        '%d → %d' % (raw.count(b'\r\n'), new_raw.count(b'\r\n')))
    chk('孤立 LF 少 1',
        (new_raw.count(b'\n') - new_raw.count(b'\r\n'))
        == (raw.count(b'\n') - raw.count(b'\r\n')) - 1,
        '%d → %d' % (raw.count(b'\n') - raw.count(b'\r\n'),
                     new_raw.count(b'\n') - new_raw.count(b'\r\n')))
    chk('§228–§232 仍在', all(
        n in set(int(x.group(1)) for x in SEC_RE.finditer(new_raw))
        for n in (228, 229, 230, 231, 232)))
    chk('last_ack 仍唯一且 = APP-133',
        re.findall(rb'last_ack:\s*APP-(\d+)', new_raw) == [b'133'])
    chk('仍 ≤ 40000 B', len(new_raw) <= 40000, '%d B' % len(new_raw))

    # ── 还原式复核（用写前备份的真实区间）─────────────────────────
    hits = [(mm.start(), int(mm.group(1))) for mm in SEC_RE.finditer(bak)]
    start = end = None
    for i, (off, num) in enumerate(hits):
        if num == 211:
            start = off
        if num == 228:
            end = hits[i][0]
    block = bak[start:end]
    m2 = re.search(re.escape(PTR_MARK) + rb'[^\n]*\n', new_raw)
    restored = new_raw[:m2.start()] + block + new_raw[m2.end():]
    chk('还原式复核＝逐字节等于写前备份', restored == bak,
        '%d B vs %d B' % (len(restored), len(bak)))
    chk('归档块仍逐字在归档件中', block in arch, '%d B' % len(block))

    if n_bad:
        print('[ABORT] 真不变量有 FAIL ⇒ 零改动')
        return 1

    bak2 = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app233_pre_eol')
    shutil.copy2(STATUS, bak2)
    print('[backup] %s' % bak2)
    tmp = STATUS + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_raw)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)
    print('[write] 完成：%d B（余量 %d B）' % (len(new_raw), 40000 - len(new_raw)))
    print('SHA256 %s' % hashlib.sha256(new_raw).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
