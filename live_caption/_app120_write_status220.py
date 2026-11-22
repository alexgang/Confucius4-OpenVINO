#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-120：**写 STATUS_APP.md 的 §220**（归档老节 + 追加新节 + 头部更新）。

## 纪律（§185 / §九）
🔴 **只追加**：不回头改旧章节；旧结论错了就在新章节里写「撤回 §x」；
🔴 **逼近 40 000 B ⇒ 先归档老的整节**（逐字）＋ 活文档换**指针行**；
🔴 **写前算字节**：超 40 000 B ⇒ fail-closed（**不落盘**）；
🔴 **写前还原式复核**：把新文本反推回原件应**逐字节相同** ⇒ 通过才落盘；
🔴 **临时文件 → `os.replace`**（绝不 `open(p,'w')` 截断）；
🔴 **写后独立复核**（另起脚本、UTF-8 **文本**比对）。

## 本脚本的三步
1. 归档 `## §215` 的正文（逐字）⇒ `status/app/STATUS_APP_sec215_20261122.md`
   （**write-once**：已存在 ⇒ 报错，不覆盖）；
2. 活文档：§215 正文 → 1 行指针；**追加** `## §220 …`；
3. 头部 `last_ack` → APP-120；`更新时间` → 实测值（`Get-Date`）。

## 用法
```
python live_caption/_app120_write_status220.py --body <§220 正文文件> --apply
```
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'app')
LIMIT_BYTES = 40000
LIMIT_LINES = 300


def log(*a):
    print(*a, flush=True)


def now_str():
    """实测当前时间（PowerShell Get-Date，避免推算）。"""
    try:
        cp = subprocess.run(['powershell', '-NoProfile', '-Command',
                             'Get-Date -Format "yyyy-MM-dd HH:mm:ss"'],
                            capture_output=True, text=True, timeout=30)
        s = (cp.stdout or '').strip()
        if s:
            return s
    except Exception as e:
        log('[warn] Get-Date 失败 %r ⇒ 用本地时间' % e)
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def read_bytes(p):
    with open(p, 'rb') as f:
        return f.read()


def find_section(lines, prefix):
    """返回 (start_idx, end_idx)：prefix 起始行 → 下一个 '## ' 之前。"""
    s = None
    for i, l in enumerate(lines):
        if l.startswith(prefix):
            s = i
            break
    if s is None:
        return None, None
    e = len(lines)
    for j in range(s + 1, len(lines)):
        if lines[j].startswith('## '):
            e = j
            break
    return s, e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--body', required=True, help='§220 正文（含标题行）的文本文件')
    ap.add_argument('--archive-sec', default='## §215')
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    orig = read_bytes(STATUS)
    orig_text = orig.decode('utf-8')
    lines = orig_text.splitlines(keepends=True)
    log('原文件：%d B / %d 行' % (len(orig), len(lines)))

    # ── ① 归档老节 ─────────────────────────────────────────────────
    s, e = find_section(lines, args.archive_sec)
    if s is None:
        log('FAIL: 找不到归档目标节 %s' % args.archive_sec)
        return 2
    title = lines[s]
    body_lines = lines[s + 1:e]
    arch_path = os.path.join(ARCH_DIR, 'STATUS_APP_sec215_20261122.md')
    if os.path.exists(arch_path):
        log('FAIL: 归档件已存在（write-once）%s' % arch_path)
        return 2
    arch_text = (title + ''.join(body_lines))
    log('归档 %s：正文 %d 行 / %d B → %s'
        % (args.archive_sec.strip(), len(body_lines),
           len(arch_text.encode('utf-8')), arch_path))

    # ── ② 拼新文本 ─────────────────────────────────────────────────
    pointer = ('> 🔴 本节正文已**整块逐字归档** ⇒ `status/app/'
               'STATUS_APP_sec215_20261122.md`（%d B）；**原文一字未删、未改**。'
               '活文档本节只留本行。\n'
               % len(arch_text.encode('utf-8')))
    new_lines = list(lines)
    new_lines[s + 1:e] = [pointer]

    with open(args.body, 'r', encoding='utf-8') as f:
        sec220 = f.read()
    if not sec220.endswith('\n'):
        sec220 += '\n'
    # 追加在文件末尾（**只追加**）
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines[-1] += '\n'
    new_lines.append(sec220)

    # 头部：last_ack + 更新时间
    out_lines = []
    for l in new_lines:
        if l.startswith('last_ack:'):
            l = 'last_ack: APP-120\n'
        elif l.startswith('更新时间:'):
            l = '更新时间: %s\n' % NOW
        out_lines.append(l)
    new_text = ''.join(out_lines)
    new_bytes = new_text.encode('utf-8')

    # ── ③ 写前复核（还原式 + 真不变量）─────────────────────────────
    checks = []

    def chk(name, cond, detail=''):
        checks.append((name, bool(cond), str(detail)[:300]))
        return cond

    # 还原式：把新文本反推回原件
    undo = new_text
    undo = undo.replace(sec220, '', 1) if sec220 in undo else undo
    undo = undo.replace(pointer, ''.join(body_lines), 1)
    undo = undo.replace('last_ack: APP-120\n', 'last_ack: APP-119\n', 1)
    undo = undo.replace('更新时间: %s\n' % NOW,
                        [l for l in lines if l.startswith('更新时间:')][0], 1)
    chk('还原式：反推回原件逐字节相同',
        undo.encode('utf-8') == orig,
        'undo %d B vs orig %d B' % (len(undo.encode('utf-8')), len(orig)))
    chk('字节 ≤ %d' % LIMIT_BYTES, len(new_bytes) <= LIMIT_BYTES,
        '%d B' % len(new_bytes))
    chk('行数 ≤ %d' % LIMIT_LINES, len(out_lines) <= LIMIT_LINES,
        '%d 行' % len(out_lines))
    chk('CRLF 数不变（LF-only）',
        orig.count(b'\r\n') == new_bytes.count(b'\r\n'),
        '%d vs %d' % (orig.count(b'\r\n'), new_bytes.count(b'\r\n')))
    chk('UTF-8 往返一致',
        new_bytes.decode('utf-8').encode('utf-8') == new_bytes, '')
    chk('last_ack 唯一且 = APP-120',
        new_text.count('last_ack: APP-120') == 1
        and 'last_ack: APP-119' not in new_text, '')
    chk('§220 标题存在', '## §220' in new_text, '')
    chk('归档指针行存在', 'STATUS_APP_sec215_20261122.md' in new_text, '')
    chk('旧节标题保留', title.strip() in new_text, '')

    for n, ok, d in checks:
        log('  [%s] %s%s' % ('PASS' if ok else 'FAIL', n,
                             '' if ok else ' :: ' + d))
    if not all(ok for _n, ok, _d in checks):
        log('!! 写前复核 FAIL ⇒ **不落盘**（源文件零改动）')
        return 1

    if not args.apply:
        log('（dry-run：未写任何文件）')
        return 0

    # ── ④ 落盘（归档件 write-once ＋ STATUS 原子替换）─────────────
    tmp_arch = arch_path + '.tmp'
    with open(tmp_arch, 'wb') as f:
        f.write(arch_text.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_arch, arch_path)
    log('归档件已写：%s（%d B）' % (arch_path, os.path.getsize(arch_path)))

    tmp = STATUS + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new_bytes)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    # ── ⑤ 写后独立复核 ────────────────────────────────────────────
    after = read_bytes(STATUS)
    after_text = after.decode('utf-8')
    post = [
        ('字节 = 预期', len(after) == len(new_bytes), '%d' % len(after)),
        ('last_ack = APP-120', after_text.count('last_ack: APP-120') == 1, ''),
        ('§220 存在', '## §220' in after_text, ''),
        ('归档指针存在', 'STATUS_APP_sec215_20261122.md' in after_text, ''),
        ('字节 ≤ %d' % LIMIT_BYTES, len(after) <= LIMIT_BYTES, '%d' % len(after)),
        ('行数 ≤ %d' % LIMIT_LINES,
         len(after_text.splitlines()) <= LIMIT_LINES, ''),
        ('归档件可读且非空',
         os.path.getsize(arch_path) > 0, ''),
    ]
    all_ok = True
    for n, ok, d in post:
        log('  [%s] %s%s' % ('PASS' if ok else 'FAIL', n,
                             '' if ok else ' :: ' + d))
        all_ok = all_ok and ok
    log('写后复核：%s' % ('ALL PASS' if all_ok else 'FAIL'))
    return 0 if all_ok else 1


NOW = ''

if __name__ == '__main__':
    # NOW 必须在模块级先赋值（main 里用到）
    NOW = now_str()
    sys.exit(main())
