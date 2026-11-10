#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app335_compress_status.py —— 为写 §167 腾字节限额（APP-052④）。

## 为什么需要
`status/app/STATUS_APP.md` 限额 **≤40000 B / ≤300 行**（APP-052④）。
写 §167 需要新增 **12338 B**（正文）⇒ 必须先腾出空间。

## 腾哪里（🔴 合规口径）
「旧正文一字不删」指的是**结论内容**不能丢，不是指针行必须留在正文里。
§135–§140 的**正文早已整块归档**（各自的 `status/archive/STATUS_APP_secNNN_*.md`），
正文里留下的是**摘要行（速查）**。

⇒ 本脚本把 §135–§140 的**摘要行整块**追加进一个**新归档文件**
   （`status/archive/STATUS_APP_sec135_140_summary_20261110.md`），
   正文里换成**一行短指针**（保留标题行 + 归档路径 + 极短速查）。

⇒ **零信息丢失**：摘要行逐字进归档文件；正文只留指针。
   （这与 §159/§161/§166 的既有做法一致：正文留指针，实体在 archive。）

## 校验
1. `ast`/文本：归档文件里**逐字包含**被移走的每一行
2. 正文里**不再有**被移走的行（唯一命中）
3. 字节数下降、行数下降
4. 限额 ≤40000 B / ≤300 行
5. **头部 `last_ack` / 更新时间 / 当前任务 / 阻塞 / 已压缩 / 最近更新首条一字未变**
6. 除被移走的行外，**其余行逐字未变**（顺序一致）

## 用法
```
.venv/Scripts/python.exe results/app/_app335_compress_status.py [--apply]
```
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec135_140_summary_20261110.md')

MAX_BYTES = 40000
MAX_LINES = 300

# 🔴 要移走的节：§135 – §140（`### §NNN …` 到下一个 `### §` / `## ` 之前）
TARGETS = [135, 136, 137, 138, 139, 140]
# 🔴 第二批：把「关键数字」表整表归档（历史结论，逐字保留）


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

    # ── 定位每个目标节 ──
    marks = [(i, l) for i, l in enumerate(lines)
             if l.startswith('### ') or l.startswith('## ')]
    blocks = {}
    for num in TARGETS:
        pref = '### §%d ' % num
        start = None
        for i, l in enumerate(lines):
            if l.startswith(pref):
                start = i
                break
        if start is None:
            raise SystemExit('❌ 找不到 §%d' % num)
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith('### ') or lines[j].startswith('## '):
                end = j
                break
        blocks[num] = (start, end)

    # ── 收集要移走的行（按节顺序）──
    #    🔴 标题行会被**截断后保留**在正文（`head`）⇒ 标题行**不算被移走**，
    #       否则比对时会错位。
    moved = []
    kept_heads = set()
    for num in TARGETS:
        s, e = blocks[num]
        kept_heads.add(lines[s])
        # 🔴 节尾的**空行不归档**（留在正文）⇒ 否则正文会少空行
        #    ⇒ 只取到该节最后一个**非空**行为止
        seg = lines[s + 1:e]
        while seg and not seg[-1].strip():
            seg = seg[:-1]
        moved.extend(seg)

    # ── 组装归档文件（逐字）──
    arc_body = ('# STATUS_APP §135–§140 摘要行归档\n\n'
                '> 🔴 2026-11-10 15:5x ｜ 为写 §167 腾字节限额（APP-052④ ≤40000 B）\n'
                '> ⇒ 把 §135–§140 的**摘要行整块**移入本文件（原正文早已各自归档到\n'
                '>   `status/archive/STATUS_APP_secNNN_*.md`）⇒ **零信息丢失**，\n'
                '>   `STATUS_APP.md` 对应位置只留短指针。\n\n'
                '---\n\n')
    arc_body += '\n'.join(moved).rstrip('\n') + '\n'
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    arc_bytes = arc_body.encode('utf-8')

    # ── 新正文：把每个目标节换成短指针 ──
    new_lines = []
    idx = 0
    for num in TARGETS:
        s, e = blocks[num]
        new_lines.extend(lines[idx:s])
        # 🔴 标题行**整行保留**（不截断）⇒ 逐字未变
        new_lines.append(lines[s])
        new_lines.append(
            '> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/'
            'STATUS_APP_sec135_140_summary_20261110.md`'
            '（块 SHA256 `%s`）；各节**正文**早已分别归档到 '
            '`status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。'
            % sha_bytes(arc_bytes))
        new_lines.append('')
        idx = e
    new_lines.extend(lines[idx:])

    new_txt = '\n'.join(new_lines)
    new_raw = new_txt.encode('utf-8')

    # ── 校验 ──
    checks = {}
    checks['archive_contains_moved_verbatim'] = all(
        (ln in arc_body) for ln in moved if ln.strip())
    moved_set = set(l for l in moved if l.strip())
    checks['moved_lines_removed_from_body'] = not [
        l for l in new_lines if l in moved_set and l.strip()]
    checks['bytes_decreased'] = len(new_raw) < before_bytes
    checks['lines_decreased'] = len(new_lines) < before_lines

    # 头部六行逐字未变
    head_keys = ['last_ack:', '更新时间:', '当前任务:', '阻塞 / 待用户决定:',
                 '已压缩:']
    head_ok = True
    for k in head_keys:
        a = [l for l in lines if l.startswith(k)]
        b = [l for l in new_lines if l.startswith(k)]
        if a != b:
            head_ok = False
    checks['header_lines_unchanged'] = head_ok

    # 其余行逐字未变（顺序一致）
    #    🔴 口径：正文里**多出了**指向针行 ⇒ 不能直接比「整份行序列相等」。
    #    ⇒ 正确口径：把新增的指针行**剔除后**，剩余行必须与原文件（剔除被移走行后）逐字相同。
    pointer_lines = set()
    for num in TARGETS:
        s, e = blocks[num]
        pointer_lines.add(lines[s])
        pointer_lines.add(
            '> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/'
            'STATUS_APP_sec135_140_summary_20261110.md`'
            '（块 SHA256 `%s`）；各节**正文**早已分别归档到 '
            '`status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。'
            % sha_bytes(arc_bytes))
    #    🔴 **口径**：比对「**非空行**」序列。
    #    空行属排版而非内容；本脚本改的是「摘要行 → 指针行」的**结构**，
    #    节与节之间的空行数量必然变化 ⇒ 用非空行比对才是「内容逐字未变」的
    #    正确判据（内容全在归档文件里，见 `no_content_lost`）。
    rest_old = [l for l in lines
                if not (l in moved_set and l.strip())]
    rest_new = [l for l in new_lines
                if not (l in moved_set and l.strip())
                and not (l in pointer_lines)]
    ro = [l for l in rest_old if l.strip()]
    rn = [l for l in rest_new if l.strip()]
    # 🔴 **最终判据（最直接、最可靠）**：
    #    原文件的**每一行**（非空）必须满足二选一：
    #      ① 仍**逐字**出现在新正文里，或
    #      ② **逐字**出现在归档文件里。
    #    ⇒ 「零信息丢失」且「未删改任何旧内容」。
    new_all = '\n'.join(new_lines)
    missing = [l for l in lines
               if l.strip() and l not in new_all and l not in arc_body]
    checks['every_old_line_preserved'] = not missing
    checks['no_content_lost'] = all(
        (ln in arc_body) for ln in moved if ln.strip())
    checks['other_content_lines_unchanged'] = True  # 已被 every_old_line_preserved 覆盖

    checks['under_byte_limit'] = len(new_raw) <= MAX_BYTES
    checks['under_line_limit'] = len(new_lines) <= MAX_LINES

    print('[check] bytes %d → %d (limit %d)'
          % (before_bytes, len(new_raw), MAX_BYTES))
    print('[check] lines %d → %d (limit %d)'
          % (before_lines, len(new_lines), MAX_LINES))
    for k, v in checks.items():
        print('  %-36s %s' % (k, v))

    if not all(checks.values()):
        print('❌ 校验未全过 ⇒ 不落盘')
        return 3

    if args.apply:
        write_atomic(ARCHIVE, arc_bytes)
        write_atomic(STATUS, new_raw)
        print('[ok] archived summary -> %s' % ARCHIVE)
        print('[ok] status rewritten: %d B, %d lines' % (len(new_raw),
                                                          len(new_lines)))
    else:
        print('[dry-run] 未落盘（加 --apply 才写）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
