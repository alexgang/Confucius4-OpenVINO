#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c173_app050_to_pkg.py —— APP-050 定点同步：仓库 `live_caption/` ⇒ 客户包 `app/`。

## 同步什么

| 文件 | 改动 |
|---|---|
| `tts_engine.py` | ① 新增 `_norm_exec_devices()`（**字符串不再逐字符拆**）② `execution_devices()` 探测 talker 桶（**int 键**）与解码器桶 ③ `absent` / `unknown` 分开 ④ 新增 **`key4_line`**（APP-050 要的那一行） |

## 为什么用「派生替换块」而不是整文件覆盖

MEMORY 铁律：
- 仓库与客户包是**两份独立副本**。
- ⇒ **禁止整目录覆盖 / 整文件覆盖**。
- ⇒ 只能「**精确字符串替换 + 唯一命中断言**」或「代码骨架等价校验后升级基底」。

本脚本的做法（沿用 `sync_c170_app048_to_pkg.py` 的**已验证**骨架）：
1. `difflib.SequenceMatcher` 在**归一化 LF** 的两份文本上求差异
   ⇒ 派生出「包内 OLD 段 → 仓库 NEW 段」的替换块。
2. 🔴 **OLD 取自「包内实际内容」**（不是基线 commit）。
3. 每个替换块在包内**必须唯一命中**（`count == 1`）⇒ 否则中止。
4. **占位符两阶段 + 倒序应用**（纯插入块没有可匹配文本 ⇒ 只能按行号）。
5. 写盘前用 `ast.parse` 校验 ⇒ 不通过则**中止、不落盘**。
6. 写盘时**按包内原行尾还原**（LF / CRLF 都要能处理）。
7. 写后**逐字节复核**（归一化行尾后）⇒ 不一致即中止。

## 跑法

    "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.13/python/python.exe" \
        live_caption/sync_c173_app050_to_pkg.py --dry-run
    "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.13/python/python.exe" \
        live_caption/sync_c173_app050_to_pkg.py
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13\app'

#: 需要同步的既有文件（仓库 → 包内）
TARGETS = ('tts_engine.py',)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def read_text(path):
    with open(path, 'rb') as f:
        return f.read()


def split_keep_eol(raw):
    """拆成 (归一化 LF 文本, 行尾类型)。"""
    if b'\r\n' in raw:
        return raw.replace(b'\r\n', b'\n').decode('utf-8'), 'crlf'
    return raw.decode('utf-8'), 'lf'


def restore_eol(text, eol):
    if eol == 'crlf':
        return text.replace('\n', '\r\n')
    return text


def derive_blocks(old_text, new_text):
    """派生出 [(tag, i1, i2, old_lines, new_lines), ...]（**带位置**）。"""
    a = old_text.split('\n')
    b = new_text.split('\n')
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        blocks.append((tag, i1, i2, a[i1:i2], b[j1:j2]))
    return blocks


def _count_occurrences(lines, seq):
    if not seq:
        return len(lines) + 1
    n = 0
    for i in range(len(lines) - len(seq) + 1):
        if lines[i:i + len(seq)] == seq:
            n += 1
    return n


def apply_blocks(text, blocks, fname):
    """把替换块应用到 text（占位符两阶段 + **按 i1 倒序**）。"""
    lines = text.split('\n')
    orig = list(lines)
    ph = []
    for idx, (tag, i1, i2, old, new) in sorted(
            enumerate(blocks), key=lambda x: -x[1][1]):
        marker = '@@APP050_BLOCK_%d@@' % idx
        if old:
            n = _count_occurrences(orig, old)
            if n != 1:
                raise SystemExit(
                    '❌ 块 #%d 在 %s 命中 %d 次（要求唯一命中 1 次）⇒ 中止'
                    % (idx, fname, n))
            if lines[i1:i2] != old:
                raise SystemExit(
                    '❌ 块 #%d 位置复核失败（行号 %d:%d 与包内原文不符）⇒ 中止'
                    % (idx, i1, i2))
        lines[i1:i2] = [marker]
        ph.append((marker, new))
    for marker, new in ph:
        pos = lines.index(marker)
        lines[pos:pos + 1] = new
    return '\n'.join(lines)


def sync_one(repo_path, pkg_path, dry):
    name = os.path.basename(repo_path)
    raw_pkg = read_text(pkg_path)
    pkg_text, eol = split_keep_eol(raw_pkg)
    raw_repo = read_text(repo_path)
    repo_text, _ = split_keep_eol(raw_repo)

    if pkg_text == repo_text:
        print('  = %s：包内已是仓库版本（归一化行尾后逐字节一致）' % name)
        return 0

    blocks = derive_blocks(pkg_text, repo_text)
    print('  ~ %s：派生替换块 %d 个（包内 %d 行 → 仓库 %d 行）'
          % (name, len(blocks), len(pkg_text.split('\n')),
             len(repo_text.split('\n'))))

    new_text = apply_blocks(pkg_text, blocks, name)

    # 🔴 写盘前 ast 校验（不通过 ⇒ 中止、不落盘）
    try:
        ast.parse(new_text)
    except SyntaxError as e:
        raise SystemExit('❌ %s 替换后 AST 校验失败 ⇒ 中止、不落盘：%s'
                         % (name, e))

    out = restore_eol(new_text, eol).encode('utf-8')
    if dry:
        print('    [dry-run] 将写入 %d 字节（原 %d）' % (len(out), len(raw_pkg)))
        return len(blocks)

    with open(pkg_path, 'wb') as f:
        f.write(out)
    # 写后复核
    check, _ = split_keep_eol(read_text(pkg_path))
    want, _ = split_keep_eol(raw_repo)
    if check != want:
        raise SystemExit('❌ %s 写后复核不一致 ⇒ 中止' % name)
    print('    ✔ 写入 %d 字节 / SHA256 %s'
          % (len(out), sha256(pkg_path)))
    return len(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=PKG)
    args = ap.parse_args()
    pkg = args.pkg
    if not os.path.isdir(pkg):
        raise SystemExit('❌ 客户包目录不存在：%s' % pkg)

    print('仓库 → 客户包 定点同步（APP-050）')
    print('  仓库：%s' % REPO)
    print('  客户包：%s' % pkg)
    print('  模式：%s' % ('DRY-RUN' if args.dry_run else '实际写入'))

    total = 0
    for name in TARGETS:
        rp = os.path.join(REPO, 'live_caption', name)
        pp = os.path.join(pkg, name)
        if not os.path.exists(rp):
            print('  ! 仓库缺 %s，跳过' % name)
            continue
        if not os.path.exists(pp):
            print('  ! 包内缺 %s，跳过' % name)
            continue
        total += sync_one(rp, pp, args.dry_run)

    print('\n合计替换块：%d' % total)
    if args.dry_run:
        print('（dry-run：未写入任何文件）')
    else:
        print('完成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
