#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_archive_sec246.py —— §251：STATUS 触顶处置（APP-052④ 口径）⇒ 把 §246 **正文**逐字归档。

🔴 **为什么必须处置**
   `status/app/STATUS_APP.md` 本体已 **39 773 B**，限额 **≤40 000 B**（§9 触顶处置口径）。
   追加 §251 指针行后会变成 **40 619 B** ⇒ **超限** ⇒ 必须先归档腾出空间。

🔴 **处置口径（沿用 §245 的既有做法 —— 标题行**留在**活文档）**
   ① 把 §246 的**正文 4 行**（`> 🟢 安装` / `> 🟢 行为验证` / `> 🔴 未做` / `> 🟢 STATUS 邮件`）
      **整块逐字**写进 **write-once** 归档件
      `status/archive/STATUS_APP_sec246_block_20261128.md` ⇒ **原文一字未删、未改**；
   ② 活文档里**保留 §246 标题行**，正文换成 **1 行指针**（指向归档件）；
   ③ 归档件**只新建、不覆写**（write-once）；已存在 ⇒ **中止**（防覆盖）。

🔴 **安全约束**
   * **纯字节操作**（`newline=''`）⇒ **不动**既有行尾（STATUS 是混合行尾，§236 坑⑥）。
   * 只动 **§246 的正文 4 行**；**标题行保留** ⇒ 章节数**不变**；其余**逐字节不变**。
   * 归档件写入后**逐字节复核**（与切下来的原文**完全相等**）。
"""
from __future__ import annotations

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
ARCH = os.path.join(ARCH_DIR, 'STATUS_APP_sec246_block_20261128.md')

TITLE = '## §246 **LOCK-001**'
POINTER = ('> 🔴 **§246 正文（4 行）已整块逐字归档** ⇒ '
           '`status/archive/STATUS_APP_sec246_block_20261128.md`（**原文一字未删、未改**）；'
           '要点：`machine_lock.py`（LOCK-001）已装并 **5/5 行为验证**（含整树被杀 ⇒ 系统锁自释放）'
           '｜🔴 **未做**：既有取锁代码（`write_lock_atomic` / CreateNew+finally 删锁）**尚未改成套 '
           '`machine_lock.py run`** ⇒ 下次计时作业起法改为 `run --module app --note … -- <命令>`'
           '｜🟢 STATUS 邮件 **2 封**已发并已发箱回读核对。\r\n')


def main() -> int:
    with io.open(P, 'rb') as f:
        raw = f.read()

    # ── 定位 §246 的**标题行**与**正文段** ──
    s = raw.find(TITLE.encode('utf-8'))
    if s < 0:
        print('!! 找不到 §246 标题 ⇒ 中止')
        return 2
    title_line_start = raw.rfind(b'\n', 0, s) + 1
    title_line_end = raw.find(b'\n', s) + 1          # 标题行（含换行）
    # 正文：从标题行之后，到下一个 `## §` 行之前
    body_start = title_line_end
    nxt = raw.find(b'\n## \xc2\xa7', body_start)
    if nxt < 0:
        print('!! 找不到 §246 之后的下一个章节 ⇒ 中止')
        return 2
    body_end = nxt + 1
    body = raw[body_start:body_end]
    title_line = raw[title_line_start:title_line_end]
    print('§246 标题行 %d B；正文 %d B（%d 行）'
          % (len(title_line), len(body), body.count(b'\n')))

    # ── write-once ──
    if os.path.exists(ARCH):
        print('!! 归档件已存在 ⇒ 中止（write-once）')
        return 2
    if not os.path.isdir(ARCH_DIR):
        os.makedirs(ARCH_DIR)

    header = ('# STATUS_APP §246 正文归档（write-once）\r\n\r\n'
              '> 本文件是 `status/app/STATUS_APP.md` 中 **§246 一节的正文 4 行**的**逐字归档**'
              '（**原文一字未删、未改**；标题行仍留在活文档）。\r\n'
              '> 归档时间：2026-11-28（§251 轮，STATUS 触顶处置：≤40 000 B 限额）。\r\n\r\n'
              '---\r\n\r\n').encode('utf-8')
    with io.open(ARCH, 'wb') as f:
        f.write(header + title_line + body)
        f.flush()
        os.fsync(f.fileno())

    with io.open(ARCH, 'rb') as f:
        wrote = f.read()
    assert body in wrote, '归档件未逐字节含正文'
    assert title_line + body in wrote, '归档件未逐字节含标题+正文'
    print('归档件已写入：%s（%d B）' % (ARCH, len(wrote)))

    # ── 活文档：标题行保留，正文换成 1 行指针 ──
    new = raw[:body_start] + POINTER.encode('utf-8') + raw[body_end:]

    # ── 写前不变量 ──
    assert new[:body_start] == raw[:body_start], '前缀变了'
    assert new[len(new) - (len(raw) - body_end):] == raw[body_end:], '后缀变了'
    assert new.count(b'\n## \xc2\xa7') == raw.count(b'\n## \xc2\xa7'), '章节数变了'
    assert new.count(b'\n') <= 300, '超 300 行：%d' % new.count(b'\n')
    assert len(new) <= 40000, '仍超 40 000 B：%d' % len(new)
    print('写前不变量 PASS：仅正文被替换 / 章节数不变 / bytes=%d / lines=%d'
          % (len(new), new.count(b'\n')))

    tmp = P + '.tmp_app251'
    with io.open(tmp, 'wb') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, P)
    print('STATUS_APP.md：%d B → %d B（−%d）' % (len(raw), len(new), len(raw) - len(new)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
