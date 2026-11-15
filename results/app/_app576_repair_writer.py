#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app576 —— 修 `_app573_write_status_sec208.py` 被 `_app575` 压紧时弄坏的一行。

🔴 **事故**：`SEC208_BODY` 的**第一行与赋值语句同一行**（`SEC208_BODY = r'''> 🔴 ...`）
   ⇒ `_app575` 按「整行替换」把它**连同 `SEC208_BODY = r'''` 一起替换掉**了
   ⇒ 该文件 `SyntaxError`（`r'''` 开引号丢失）。

🔴 **修法**：把那一行的前缀补回来（**只加前缀，不动正文**）⇒ 再 `ast.parse` 验证。
   同时**修 `_app575`**：以后遇到「赋值语句与正文首行同行」的行，
   **只替换引号之后的部分**（不整行替换）⇒ 同一个坑不再踩第二次。
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, '_app573_write_status_sec208.py')
COMPACTOR = os.path.join(HERE, '_app575_compact_sec208_body.py')


def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    os.close(fd)
    with open(tmp, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def repair():
    with open(TARGET, 'rb') as f:
        text = f.read().decode('utf-8')
    lines = text.split('\n')
    fixed = 0
    for i, line in enumerate(lines):
        if '完整正文' in line and 'SEC208_BODY' not in line:
            # 找到紧邻的上一行是否已有赋值（防止重复修）
            lines[i] = "SEC208_BODY = r'''" + line
            fixed += 1
            break
    if fixed != 1:
        print('!! 未能定位待修行（命中 %d）⇒ 零写入' % fixed)
        return 1
    new = '\n'.join(lines).encode('utf-8')
    try:
        ast.parse(new.decode('utf-8'))
    except SyntaxError as e:
        print('!! 修复后仍 SyntaxError：%s ⇒ 零写入' % e)
        return 1
    m = re.search(r"SEC208_BODY = r'''(.*?)'''", new.decode('utf-8'), re.S)
    if not m:
        print('!! 修复后仍找不到 SEC208_BODY ⇒ 零写入')
        return 1
    atomic_write(TARGET, new)
    print('[repair] 已补回 `SEC208_BODY = r\'\'\'`｜body %d B｜文件 %d B'
          % (len(m.group(1).encode('utf-8')), len(new)))
    return 0


def fix_compactor():
    """把「整行替换」改成「引号之后替换」（首行与赋值同行时不再被弄坏）。"""
    with open(COMPACTOR, 'rb') as f:
        text = f.read().decode('utf-8')
    old = """            if mark in line:
                if line.strip() != NEW[key].strip():
                    lines[i] = NEW[key]
                hits += 1
                break"""
    new = """            if mark in line:
                pre = ''
                rest = line
                # 🔴 首行可能与赋值语句同行（`SEC208_BODY = r'''> ...`）
                #    ⇒ **只替换引号之后的部分**，否则会把开引号一起弄掉
                mq = re.match(r"^(\\s*SEC208_BODY\\s*=\\s*r''')(.*)$", line)
                if mq:
                    pre, rest = mq.group(1), mq.group(2)
                if rest.strip() != NEW[key].strip():
                    lines[i] = pre + NEW[key]
                hits += 1
                break"""
    if old not in text:
        print('[fix-compactor] 锚点未命中（跳过）')
        return 0
    atomic_write(COMPACTOR, text.replace(old, new, 1).encode('utf-8'))
    print('[fix-compactor] 已改成「引号之后替换」')
    return 0


def main():
    rc = repair()
    if rc:
        return rc
    return fix_compactor()


if __name__ == '__main__':
    sys.exit(main())
