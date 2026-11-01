#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app129 —— 把 §127/§128 正文**逐字**归档，并把 §129 写进 STATUS_APP.md。

🔴 纪律（APP-052 ④）：
  - 只**追加**章节，不回头改旧章节；
  - 旧正文**一字不删**（移到 `status/archive/`，逐字保留）；
  - 归档件必须**逐字命中**（写后复核）；
  - 压缩后复核 ≤ 40 KB / ≤ 300 行；
  - 压缩用 `.tmp` → `os.replace` **原子替换**；
  - 自指大小（头部「已压缩」行里的字节数）必须与磁盘**实测一致**（差 2 B 也要改）。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_sec127_128_upto_20261102.md')

MAX_BYTES = 40000
MAX_LINES = 300


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def split_sections(text):
    """返回 (头部, [(标题, 正文), ...])。标题以 `### §` 开头。"""
    ms = list(re.finditer(r'(?m)^(### §\d+ .*)$', text))
    if not ms:
        return text, []
    head = text[:ms[0].start()]
    secs = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        secs.append((m.group(1), text[m.end():end]))
    return head, secs


def main() -> int:
    text = read(STATUS)
    head, secs = split_sections(text)

    # ── 1. 归档 §127/§128 的正文（逐字） ────────────────────────
    keep_idx = []
    archived = []
    for i, (title, body) in enumerate(secs):
        m = re.match(r'### §(\d+)', title)
        n = int(m.group(1)) if m else 0
        if n in (127, 128):
            archived.append((title, body))
        else:
            keep_idx.append(i)
    if not archived:
        print('!! 没找到 §127/§128 ⇒ 中止（不猜）')
        return 2

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(ARCHIVE, 'w', encoding='utf-8', newline='') as f:
        f.write('# STATUS_APP 归档（§127 / §128 正文逐字留存）\n\n'
                '> 本文件由 `results/app/_app129_archive_sec127_128.py` 于 '
                '2026-11-02 生成。\n'
                '> **§127 / §128 的正文逐字保留，内容一字未删**；'
                '原位留有指针行（见 `status/app/STATUS_APP.md`）。\n\n')
        for title, body in archived:
            f.write(title + '\n')
            f.write(body if body.endswith('\n') else body + '\n')
            f.write('\n')

    # 🔴 复核：归档件必须**逐字**包含两节正文
    arc = read(ARCHIVE)
    for title, body in archived:
        if body.strip() and body.strip() not in arc:
            print('!! 归档件未逐字命中 %s ⇒ 中止' % title[:30])
            return 3
        print('归档逐字命中：%s' % title[:46])

    # ── 2. 重建 STATUS：头部 + 保留的旧节 + §127/§128 指针 + §129 ──
    out = head
    for i, (title, body) in enumerate(secs):
        if i in keep_idx:
            out += title + '\n' + body
        else:
            out += title + '\n'
            out += ('\n> **本节正文已原样归档** ⇒ 见 '
                    '`status/archive/STATUS_APP_sec127_128_upto_20261102.md`'
                    '（逐字保留，内容一字未删）。\n')

    # ── 3. 追加 §129（正文由调用方传入，避免在脚本里塞长文本） ──
    sec129 = read(os.path.join(HERE, '_app129_sec129_body.md'))
    out += '\n' + sec129

    # ── 4. 更新头部（last_ack 不变；更新时间实测） ──────────────
    out = re.sub(r'(?m)^更新时间: .*$',
                 '更新时间: 2026-11-02 04:47', out, count=1)

    # ── 5. 自指大小修正：头部「已压缩」行里的字节数 = 实测 ──────
    #    （必须先算「改完之后」的大小 ⇒ 迭代到不动点）
    for _ in range(6):
        b = len(out.encode('utf-8'))
        lines = out.count('\n') + 1
        new_out = re.sub(
            r'(?m)^已压缩: 本文件 \d+ B / \d+ 行',
            '已压缩: 本文件 %d B / %d 行' % (b, lines), out, count=1)
        if new_out == out:
            break
        out = new_out
    b = len(out.encode('utf-8'))
    lines = out.count('\n') + 1
    print('压缩后：%d B / %d 行（限额 %d B / %d 行）' % (b, lines,
                                                       MAX_BYTES, MAX_LINES))
    if b > MAX_BYTES or lines > MAX_LINES:
        print('!! 仍超限 ⇒ 中止（不写盘）')
        return 4

    # ── 6. 原子替换（.tmp → os.replace） ──────────────────────
    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)

    # ── 7. 写后复核 ───────────────────────────────────────────
    after = read(STATUS)
    assert len(after.encode('utf-8')) == b, '写后字节数不一致'
    assert after.count('\n') + 1 == lines, '写后行数不一致'
    for title, body in archived:
        if title not in after:
            print('!! 旧章节标题丢失 ⇒ 中止')
            return 5
    if '§129' not in after:
        print('!! §129 未写入 ⇒ 中止')
        return 6
    print('写后复核通过：%d B / %d 行；§127/§128 标题仍在；§129 已追加'
          % (b, lines))
    print('归档 SHA256 = %s' % hashlib.sha256(
        open(ARCHIVE, 'rb').read()).hexdigest())
    print('STATUS SHA256 = %s' % hashlib.sha256(
        open(STATUS, 'rb').read()).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
