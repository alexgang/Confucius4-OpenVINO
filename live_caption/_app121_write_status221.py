#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-121 §221：**把 §221 追加进 `status/app/STATUS_APP.md`**（并按 APP-052④ 归档腾空间）。

## 做什么（严格「只追加、不回头改旧章节」）
1. 🔴 **归档腾空间**：`§181 … §210` 这 30 行的**标题行＋指针行整块逐字**写进
   `status/archive/STATUS_APP_sec181_210_headers_20261123.md`
   ⇒ 活文档原处换成 1 行指针（**原文一字未删、未改**）；
2. 头部 `last_ack`：**APP-120 → APP-121**；「更新时间」用 `Get-Date` **实测值**；
3. 「最近更新」节**最前面**插入本轮条目（旧的条目**不删**，只不动）；
4. **追加** `## §221 …` 标题行 ＋ 1 行指针行（正文在 companion）；
5. **写后独立复核**：字节数 ≤ 40000、行数 ≤ 300、`last_ack` 正确、
   §221 标题在、归档块 SHA 与指针声明一致、旧正文逐字未变（对**写前备份**逐行 diff）。

## 纪律
- 临时文件 → `os.replace`（**不截断原文件**）；
- **不碰** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。

## 用法
```
python live_caption/_app121_write_status221.py --title-file <t.txt> --recent-file <r.txt> [--apply]
```
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE_FILE = os.path.join(ARCHIVE_DIR,
                             'STATUS_APP_sec181_210_headers_20261123.md')
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def sha_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--title-file', required=True,
                    help='§221 的标题行 + 指针行（两行文本）')
    ap.add_argument('--recent-file', required=True,
                    help='「最近更新」本轮条目（一行文本）')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out', default=os.path.join(
        REPO, 'results', 'app', 'app121_write_status221_evidence.json'))
    args = ap.parse_args()

    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        orig = f.read()
    if not args.apply:
        print('（dry-run）')
        print('  last_ack 行数 =', orig.count('last_ack: APP-120'))
        print('  §181 标题行存在 =', '\n## §181 ' in orig or orig.startswith('## §181 '))
        print('  §211 标题行存在 =', '## §211 ' in orig)
        return 0

    # ── 写前备份（还原式复核用）─────────────────────────────────
    bak = os.path.join(tempfile.gettempdir(), 'STATUS_APP.md.bak_app121')
    shutil.copy2(STATUS, bak)

    with io.open(args.title_file, 'r', encoding='utf-8') as f:
        title_block = f.read().rstrip('\n')
    with io.open(args.recent_file, 'r', encoding='utf-8') as f:
        recent_line = f.read().rstrip('\n')

    lines = orig.splitlines(True)

    # ── ① 归档 §181–§210（整块逐字）─────────────────────────────
    i_start = i_end = None
    for i, l in enumerate(lines):
        if l.startswith('## §181 ') and i_start is None:
            i_start = i
        if l.startswith('## §211 '):
            i_end = i
            break
    if i_start is None or i_end is None or i_end <= i_start:
        print('FAIL: 找不到 §181–§210 的行范围（start=%s end=%s）'
              % (i_start, i_end))
        return 2
    block = ''.join(lines[i_start:i_end])
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    if os.path.exists(ARCHIVE_FILE):
        with io.open(ARCHIVE_FILE, 'r', encoding='utf-8', newline='') as f:
            old = f.read()
        if old != block:
            print('FAIL: 归档件已存在且与本次取到的块**不一致** ⇒ 拒绝覆盖'
                  '（归档件 write-once）')
            return 2
        print('  归档件已存在且逐字相同 ⇒ 复用')
        arch_sha = sha_text(old)
        arch_bytes = len(old.encode('utf-8'))
    else:
        hdr = ('> 🔴 本块为 `status/app/STATUS_APP.md` 的 **§181–§210 标题行＋'
               '指针行**，原文**整块逐字归档**（写一次，不再改）。\n'
               '> 归档时间：2026-11-23；归档块 SHA256 `%s`／%d B。\n\n'
               % (sha_text(block), len(block.encode('utf-8'))))
        with io.open(ARCHIVE_FILE, 'w', encoding='utf-8', newline='') as f:
            f.write(hdr + block)
        arch_sha = sha_text(block)
        arch_bytes = len(block.encode('utf-8'))
        print('  归档件已写：%s（%d B）' % (ARCHIVE_FILE, arch_bytes))

    pointer = ('> 🔴 **§181–§210（本批 30 节）的标题行＋指针行已整块逐字归档** ⇒ '
               '`status/archive/STATUS_APP_sec181_210_headers_20261123.md`'
               '（%d B／块 SHA256 `%s`）；**原文一字未删、未改**。'
               '活文档本处只留本行。\n' % (arch_bytes, arch_sha))

    new_lines = (lines[:i_start] + [pointer] + lines[i_end:])

    # ── ② 头部 last_ack / 更新时间 ──────────────────────────────
    text = ''.join(new_lines)
    n_ack = text.count('last_ack: APP-120')
    if n_ack != 1:
        print('FAIL: `last_ack: APP-120` 命中 %d 次（应为 1）' % n_ack)
        return 2
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    text = text.replace('last_ack: APP-120', 'last_ack: APP-121', 1)
    # 「更新时间」用 Get-Date 实测值
    import re
    text, n_upd = re.subn(r'(?m)^更新时间: .*$', '更新时间: %s' % now, text, count=1)
    if n_upd != 1:
        print('FAIL: 「更新时间」行命中 %d 次（应为 1）' % n_upd)
        return 2

    # ── ③ 「最近更新」插入最新条目 ──────────────────────────────
    m = re.search(r'(?m)^## 最近更新\n', text)
    if not m:
        print('FAIL: 找不到「## 最近更新」')
        return 2
    ins = m.end()
    text = text[:ins] + recent_line + '\n' + text[ins:]

    # ── ④ 追加 §221（标题行 + 指针行）───────────────────────────
    if not text.endswith('\n'):
        text += '\n'
    text += '\n' + title_block + '\n'

    # ── ⑤ 写盘（临时文件 → os.replace）─────────────────────────
    tmp = STATUS + '.app121.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    # ── ⑥ 写后独立复核 ────────────────────────────────────────
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        after = f.read()
    checks = [
        ('last_ack = APP-121', 'last_ack: APP-121' in after),
        ('§221 标题行在', '\n## §221 ' in after),
        ('§181–§210 已换成指针行', pointer.strip() in after),
        ('旧 §211 标题行仍在', '## §211 ' in after),
        ('旧 §220 标题行仍在', '## §220 ' in after),
        ('「最近更新」本轮条目在', recent_line.strip()[:60] in after),
        ('字节数 ≤ %d' % LIMIT_BYTES, len(after.encode('utf-8')) <= LIMIT_BYTES),
        ('行数 ≤ %d' % LIMIT_LINES, len(after.splitlines()) <= LIMIT_LINES),
    ]
    # 🔴 **还原式复核**：把本轮新增**按行**去掉 ⇒ 应与写前原件**逐字节**相同
    #   ⚠️ **不能用 `rstrip()`/正则去吃换行**（会把「指针行换回归档块」处的
    #      空行吃掉 ⇒ 假 FAIL）。按**整行**替换，不碰其它任何字符。
    with io.open(ARCHIVE_FILE, 'r', encoding='utf-8', newline='') as f:
        arch_text = f.read()
    body = arch_text.split('\n\n', 1)[1] if '\n\n' in arch_text else arch_text
    undo = after.replace(recent_line + '\n', '', 1)
    undo = undo.replace('\n' + title_block + '\n', '', 1)
    pl = [l for l in undo.splitlines(True)
          if l.startswith('> 🔴 **§181–§210（本批 30 节）')]
    if len(pl) == 1:
        undo = undo.replace(pl[0], body, 1)
    undo = undo.replace('last_ack: APP-121', 'last_ack: APP-120', 1)
    with io.open(bak, 'r', encoding='utf-8', newline='') as f:
        orig_norm = f.read()
    m_upd = re.search(r'(?m)^更新时间: .*$', orig_norm)
    if m_upd:
        undo = re.sub(r'(?m)^更新时间: .*$', lambda _m: m_upd.group(0), undo,
                      count=1)
    checks.append(('还原式复核（去掉本轮新增后与写前原件逐字节一致）',
                   undo == orig_norm))

    ev = {'script': '_app121_write_status221.py',
          'ts': now,
          'status': STATUS,
          'bytes_after': len(after.encode('utf-8')),
          'lines_after': len(after.splitlines()),
          'bytes_before': len(orig.encode('utf-8')),
          'lines_before': len(orig.splitlines()),
          'archive_file': ARCHIVE_FILE,
          'archive_block_sha256': arch_sha,
          'archive_block_bytes': arch_bytes,
          'checks': {n: bool(o) for n, o in checks},
          'n_fail': sum(1 for _n, o in checks if not o),
          'backup': bak,
      }
    ev['verdict'] = 'PASS' if ev['n_fail'] == 0 else 'FAIL'
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    t2 = args.out + '.tmp'
    with io.open(t2, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(t2, args.out)
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))
    print('  字节 %d / 行 %d（限额 %d B / %d 行）'
          % (ev['bytes_after'], ev['lines_after'],
             LIMIT_BYTES, LIMIT_LINES))
    print('  判定：%s' % ev['verdict'])
    print('  证据 → %s' % args.out)
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
