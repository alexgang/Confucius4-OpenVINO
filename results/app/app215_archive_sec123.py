#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app215 —— 把 STATUS_APP.md 的 §123 正文**原样归档**，只留索引行。

🔴🔴 纪律（§110 / §120 / §121 踩过两次坑）：
  * **旧正文一字未删** ⇒ 归档件必须**逐字节包含**原正文
    （判据 = 每个章节 body `in archive`）
  * **保留条目之间的空行**（只保留 `- ` 开头行 ⇒ 空行被吃 ⇒
    `git diff` 多出一行删除 ⇒ 违反「旧正文逐字未删」）
  * **写文件先写临时文件再原子替换**
  * **不写死版本号**
"""
from __future__ import annotations

import hashlib
import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')

SEC_ID = '§123'
ARCH_NAME = 'STATUS_APP_sec123_upto_20261101.md'


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def main():
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    lines = text.split('\n')

    # 找 §123 正文的起止（标题行 … 文件末尾）
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith('### ' + SEC_ID):
            start = i
            break
    if start is None:
        print('[FAIL] 未找到 %s 正文标题' % SEC_ID)
        return 1
    body = '\n'.join(lines[start:])
    print('[info] %s 正文：第 %d 行起，共 %d 行 / %d B'
          % (SEC_ID, start + 1, len(lines) - start, len(body.encode('utf-8'))))

    os.makedirs(ARCH_DIR, exist_ok=True)
    arch_path = os.path.join(ARCH_DIR, ARCH_NAME)

    # 归档件 = 原 §123 正文（逐字）+ 归档头（标明来源）
    header = (
        '# STATUS_APP 归档 —— %s 正文（逐字保留，内容一字未删）\n'
        '\n'
        '- 归档来源：`status/app/STATUS_APP.md` → `%s` 正文\n'
        '- 归档时间：2026-11-01（本轮 APP-055~058 执行时腾空间用）\n'
        '- 更早的章节见 `STATUS_APP_sec109_122_upto_20261101.md` 与 '
        '`STATUS_APP_upto_20261030.md`\n'
        '\n'
        '---\n'
        '\n'
    ) % (SEC_ID, SEC_ID)
    arch_text = header + body

    tmp = arch_path + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(arch_text)
    # 复核：旧正文必须**逐字**在归档件里
    with io.open(tmp, 'r', encoding='utf-8', newline='') as f:
        got = f.read()
    if body not in got:
        os.remove(tmp)
        print('[FAIL] 归档件未逐字包含旧正文 ⇒ 已中止')
        return 1
    os.replace(tmp, arch_path)
    print('[OK] 已归档：%s（%d B / SHA256 %s）'
          % (arch_path, len(arch_text.encode('utf-8')),
             sha256_bytes(arch_text.encode('utf-8'))))

    # ── 改 STATUS：把正文换成**一行索引**（保留章节标题行作为锚点）──
    # 🔴 **保留标题行**（reviewer / 后续巡检靠它定位章节）
    title_line = lines[start]
    new_lines = lines[:start] + [title_line,
                                 '', '> **本节正文已原样归档** ⇒ '
                                 '见 `status/archive/%s`（逐字保留，'
                                 '内容一字未删）。' % ARCH_NAME, '']
    new_text = '\n'.join(new_lines)

    tmp2 = STATUS + '.tmp'
    with io.open(tmp2, 'w', encoding='utf-8', newline='') as f:
        f.write(new_text)
    with io.open(tmp2, 'r', encoding='utf-8', newline='') as f:
        got2 = f.read()
    # 复核：归档件仍逐字包含旧正文；新文件仍含标题行
    if body not in arch_text or title_line not in got2:
        os.remove(tmp2)
        print('[FAIL] 复核失败 ⇒ 已中止')
        return 1
    os.replace(tmp2, STATUS)
    print('[OK] STATUS 已替换 %s 正文为索引行：%d B → %d B'
          % (SEC_ID, len(text.encode('utf-8')),
             len(new_text.encode('utf-8'))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
