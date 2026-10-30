#!/usr/bin/env python
"""🔴 APP-048 定点同步脚本：仓库 `live_caption/` ⇒ 客户包 `app/`。

## 为什么用「派生替换块」而不是整文件覆盖

MEMORY 铁律：
- 仓库与客户包是**两份独立副本**（包内有 APP-023 之后历次打包时追加的改动）。
- ⇒ **禁止整目录覆盖 / 整文件覆盖**。
- ⇒ 只能「**精确字符串替换 + 唯一命中断言**」或「代码骨架等价校验后升级基底」。

本脚本的做法：
1. `difflib.SequenceMatcher` 在**归一化 LF** 的两份文本上求差异
   ⇒ 派生出「包内 OLD 段 → 仓库 NEW 段」的替换块。
2. 🔴 **OLD 必须取自「包内实际内容」**（不是基线 commit）
   ⇒ 否则包内若被别的会话改过，替换会落到错误位置。
3. 每个替换块在包内**必须唯一命中**（`count == 1`）⇒ 否则中止。
4. 替换块**倒序应用**（后面的先改 ⇒ 前面的偏移不受影响）。
5. 写盘前用 `ast.parse` 校验 ⇒ 不通过则**中止、不落盘**。
6. 写盘时**按包内原行尾还原**（LF / CRLF 都要能处理）。

## 新增文件

`gui_status.py` 是 APP-048 **新增**的模块（纯逻辑，不依赖 tkinter）
⇒ 直接复制过去（复制后逐字节比对 + SHA256 记录）。

## 跑法

    .venv\\Scripts\\python.exe live_caption\\sync_c170_app048_to_pkg.py --dry-run
    .venv\\Scripts\\python.exe live_caption\\sync_c170_app048_to_pkg.py
"""

import argparse
import ast
import difflib
import hashlib
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12\app'

# 需要同步的既有文件（仓库 → 包内）
TARGETS = ('live_caption_app.py',)

# 新增文件（直接复制）
NEW_FILES = ('gui_status.py',)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with open(path, 'rb') as f:
        raw = f.read()
    return raw


def split_keep_eol(raw):
    """返回 (归一化 LF 的文本, 原行尾类型)。"""
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n') - crlf
    eol = '\r\n' if crlf > lf else '\n'
    text = raw.decode('utf-8').replace('\r\n', '\n')
    return text, eol


def restore_eol(text, eol):
    if eol == '\r\n':
        return text.replace('\n', '\r\n')
    return text


def derive_blocks(old_text, new_text):
    """派生出 [(tag, i1, i2, old_lines, new_lines), ...]（**带位置**）。

    🔴 **为什么必须带位置**：纯插入块（old 为空）没有可匹配的文本
      ⇒ 只能按**行号**插入。
      ⇒ 行号基准是**包内原文**（old_text），因为 difflib 是拿两份全文求差异的。
      ⇒ 应用时必须**按 i1 倒序**（见 `apply_blocks` 的说明）。
    """
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
    """把替换块应用到 text。

    🔴 **为什么用「占位符两阶段 + 倒序」**：
      `difflib` 给的块里既有**替换**（old 非空）也有**纯插入**（old 为空）。
      - 纯插入没有可匹配的文本 ⇒ 只能按行号；
      - 但前面的块会**改变行数** ⇒ 后面的行号全部偏移。
      ⇒ 做法：**第一阶段**把每个块替换成一行**唯一占位符**；
        **第二阶段**再把占位符行**展开**成实际的多行内容。
      🔴 **第一阶段必须「按 i1 倒序」**：正序时前面的块改行数 ⇒ 后面块行号偏移。
        倒序时每次只改动**更靠后**的位置 ⇒ 前面块的行号始终有效。
      ⇒ 另外 `lines[i1:i2] = [marker]` 会把 N 行压成 1 行（行数变），
        所以第一阶段的行号有效性**完全依赖倒序**。
    """
    lines = text.split('\n')
    orig = list(lines)
    ph = []
    # ── 第一阶段：按行号倒序替换成占位符 ──
    for idx, (tag, i1, i2, old, new) in sorted(
            enumerate(blocks), key=lambda x: -x[1][1]):
        marker = '@@APP048_BLOCK_%d@@' % idx
        # 🔴 唯一命中断言：old 非空时，它在**包内原文**里必须唯一
        #    （对原文而非当前文本求值 ⇒ 不受已占位区块影响）
        if old:
            n = _count_occurrences(orig, old)
            if n != 1:
                raise SystemExit(
                    '❌ 块 #%d 在 %s 命中 %d 次（要求唯一命中 1 次）⇒ 中止'
                    % (idx, fname, n))
            # 位置一致性复核：difflib 给的行号必须与原文严格对齐
            if lines[i1:i2] != old:
                raise SystemExit(
                    '❌ 块 #%d 位置复核失败（行号 %d:%d 与包内原文不符）⇒ 中止'
                    % (idx, i1, i2))
        lines[i1:i2] = [marker]
        ph.append((marker, new))
    # ── 第二阶段：展开占位符 ──
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
        print('  = %s：包内已是仓库版本（逐字节一致）' % name)
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
    # 写后复核：逐字节 == 仓库（归一化行尾后）
    check, _ = split_keep_eol(read_text(pkg_path))
    want, _ = split_keep_eol(raw_repo)
    if check != want:
        raise SystemExit('❌ %s 写后复核不一致 ⇒ 中止' % name)
    print('    ✔ 写入 %d 字节 / SHA256 %s' % (len(out), sha256(pkg_path)[:16]))
    return len(blocks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=PKG)
    args = ap.parse_args()
    pkg = args.pkg
    if not os.path.isdir(pkg):
        raise SystemExit('❌ 客户包目录不存在：%s' % pkg)

    print('仓库 → 客户包 定点同步（APP-048）')
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

    for name in NEW_FILES:
        rp = os.path.join(REPO, 'live_caption', name)
        pp = os.path.join(pkg, name)
        if not os.path.exists(rp):
            print('  ! 仓库缺 %s，跳过' % name)
            continue
        if os.path.exists(pp):
            same = (read_text(rp) == read_text(pp))
            print('  = %s：包内已存在（逐字节一致=%s）' % (name, same))
            if not same:
                raise SystemExit('❌ %s 包内已存在但内容不同 ⇒ 需人工确认' % name)
            continue
        raw = read_text(rp)
        try:
            ast.parse(raw.decode('utf-8'))
        except SyntaxError as e:
            raise SystemExit('❌ %s AST 校验失败 ⇒ 中止：%s' % (name, e))
        if args.dry_run:
            print('  ~ %s：新增文件（将复制 %d 字节）' % (name, len(raw)))
            continue
        shutil.copyfile(rp, pp)
        print('  + %s：新增 %d 字节 / SHA256 %s'
              % (name, os.path.getsize(pp), sha256(pp)[:16]))

    print('\n合计替换块：%d' % total)
    if args.dry_run:
        print('（dry-run：未写入任何文件）')
    else:
        print('完成。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
