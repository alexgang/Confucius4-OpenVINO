#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app336_compress_status2.py —— 第二批压缩：把「关键数字」表整表归档。

## 为什么
写 §167 需 12 338 B；压缩 §135–§140 后仍超限额 **777 B**。

## 压哪里
`### 关键数字` 表（约 5 321 B）= **APP-045/047/048/050/053/054 等历史结论**，
每行都注明了「来源产物 / 字段」⇒ **内容可完整追回**，逐字归档零损失。

⇒ 整表移入 `status/archive/STATUS_APP_key_numbers_20261110.md`，
   正文留**短指针 + 表头 + 一行速查**（本轮 §167 的关键数字在 §167 里）。

## 校验（同 `_app335`）
`every_old_line_preserved` / `header_lines_unchanged` / 限额 / 原子替换。

## 用法
```
.venv/Scripts/python.exe results/app/_app336_compress_status2.py [--apply]
```
"""
from __future__ import annotations

import argparse
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_key_numbers_20261110.md')
MAX_BYTES = 40000
MAX_LINES = 300

HEAD_KEYS = ['last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:',
             '已压缩:']


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_atomic(p, data):
    tmp = p + '.tmp_%d' % os.getpid()
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    with open(STATUS, 'rb') as f:
        raw = f.read()
    txt = raw.decode('utf-8')
    lines = txt.split('\n')
    before_bytes = len(raw)
    before_lines = len(lines)

    # ── 定位「### 关键数字」表 ──
    start = None
    for i, l in enumerate(lines):
        if l.startswith('### 关键数字'):
            start = i
            break
    if start is None:
        raise SystemExit('❌ 找不到「### 关键数字」')
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith('### ') or lines[j].startswith('## '):
            end = j
            break
    # 表体 = 标题行之后的全部行（到下一节前）
    table = lines[start:end]
    # 末尾空行不归档
    while table and not table[-1].strip():
        table = table[:-1]
    body = table[1:]          # 去掉「### 关键数字」标题行

    arc_body = ('# STATUS_APP 「关键数字」表归档\n\n'
                '> 🔴 2026-11-10 16:0x ｜ 为写 §167 腾字节限额（APP-052④ ≤40000 B）\n'
                '> ⇒ 本表（历史结论，逐行注明「来源产物 / 字段」）**整表逐字归档**于此。\n\n'
                '---\n\n')
    arc_body += '\n'.join(body).rstrip('\n') + '\n'
    arc_bytes = arc_body.encode('utf-8')

    pointer = [
        '### 关键数字',
        '',
        '> 🔴 本表已**整表逐字归档** ⇒ `status/archive/'
        'STATUS_APP_key_numbers_20261110.md`（块 SHA256 `%s`）。'
        % sha_bytes(arc_bytes),
        '> 🔴 表内每行均注明「来源产物 / 字段」⇒ 可按文件名完整追回；'
        '**本轮（APP-093 §3 / APP-097 §2）的关键数字见 §167**。',
        '',
    ]

    new_lines = lines[:start] + pointer + lines[end:]
    new_txt = '\n'.join(new_lines)
    new_raw = new_txt.encode('utf-8')

    checks = {}
    new_all = new_txt
    checks['every_old_line_preserved'] = all(
        (l.strip() and (l in new_all or l in arc_body))
        for l in lines if l.strip())
    head_ok = True
    for k in HEAD_KEYS:
        a = [l for l in lines if l.startswith(k)]
        b = [l for l in new_lines if l.startswith(k)]
        if a != b:
            head_ok = False
    checks['header_lines_unchanged'] = head_ok
    checks['bytes_decreased'] = len(new_raw) < before_bytes
    checks['under_byte_limit'] = len(new_raw) <= MAX_BYTES
    checks['under_line_limit'] = len(new_lines) <= MAX_LINES

    print('[check] bytes %d → %d (limit %d)'
          % (before_bytes, len(new_raw), MAX_BYTES))
    print('[check] lines %d → %d (limit %d)'
          % (before_lines, len(new_lines), MAX_LINES))
    for k, v in checks.items():
        print('  %-34s %s' % (k, v))

    if not all(checks.values()):
        print('❌ 校验未全过 ⇒ 不落盘')
        return 3
    if args.apply:
        os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
        write_atomic(ARCHIVE, arc_bytes)
        write_atomic(STATUS, new_raw)
        print('[ok] archived -> %s' % ARCHIVE)
        print('[ok] status rewritten: %d B, %d lines' % (len(new_raw),
                                                         len(new_lines)))
    else:
        print('[dry-run] 未落盘')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
