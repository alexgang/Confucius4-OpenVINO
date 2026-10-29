#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""sync_c154_to_pkg.py —— §91：**定点**把仓库的 `tts_cuda.py` 同步到客户包 v1.6。

## 为什么必须「定点」而不能整目录覆盖（铁律）

仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
⇒ 整目录覆盖会**吞掉客户包侧的独立改动**（客户包里有仓库没有的东西）。

## 本脚本的做法（沿用 §59/§90 的成熟法）

1. **基线 = 固定 commit**（`1782253` = §90 那次提交）
   ⇒ 用 `git show <基线>:<rel>` 拿到「包当前内容对应的仓库版本」；
2. 用 `difflib.SequenceMatcher.get_grouped_opcodes(n=3)` **自动派生**替换块
   ⇒ **不手抄代码**（手抄 = 引入笔误的通道）；
3. 每个替换块的 OLD 文本必须在包内**恰好命中 1 次**
   ⇒ 否则**中止**（不猜、不多命中就替换）；
4. 替换后**归一化 LF** 与仓库工作区**逐字一致**（逐字校验，不是「看起来一样」）；
5. 备份目录在**包外**（`C:\Users\Trekker-PTL\pkg_backup_app_c154`）；
6. **幂等**：已同步则报 `ALREADY`（可反复跑）。

## 用法

    <py> live_caption/sync_c154_to_pkg.py          # 执行同步
    <py> live_caption/sync_c154_to_pkg.py --check  # 只查差异，不写
"""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: 🔴 同步基线（客户包当前内容对应的仓库版本）
#:   ⚠️ **基线只是 diff 的起点**，同步的**目标**是「包内 == 仓库工作区」。
#:   本脚本**可重复执行**：每轮同步后包内已含上一轮的改动 ⇒ 再跑时
#:   基线不再是精确对应版本 ⇒ 因此下面用 **`(基线, 包内实际内容)` 取交集**
#:   的方式派生替换块：**以包内实际内容为 OLD** ⇒ 永远能唯一命中。
BASE_COMMIT = '1782253'

#: 本轮要同步的文件（相对仓库根）
FILES = ['live_caption/tts_cuda.py']

#: 🔴 备份目录（**必须在包外** ⇒ 万一要回滚）
BACKUP_DIR = r'C:\Users\Trekker-PTL\pkg_backup_app_c154'

#: 客户包候选目录名前缀
PKG_PREFIX = 'Confucius4_LiveCaption_v'


def log(msg):
    print('[sync-c154] %s' % msg, flush=True)


def git_show(commit, rel):
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True, timeout=120)
    if p.returncode != 0:
        raise SystemExit('git show 失败：%s:%s ⇒ %s'
                         % (commit, rel, p.stderr.decode('utf-8', 'replace')))
    return p.stdout.decode('utf-8', 'replace')


def find_pkg_dir():
    """挑**版本号最大**的客户包目录。"""
    home = os.path.expanduser('~')
    best, best_key = '', None
    for name in os.listdir(home):
        if not name.startswith(PKG_PREFIX):
            continue
        ver = name[len(PKG_PREFIX):]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        cand = os.path.join(home, name)
        if not os.path.isdir(os.path.join(cand, 'app')):
            continue
        if best_key is None or key > best_key:
            best_key, best = key, cand
    if not best:
        raise SystemExit('找不到客户包目录（%s*）' % PKG_PREFIX)
    return best


def norm(text):
    """归一化行尾（LF）⇒ 比对时忽略 CRLF/LF 差异。"""
    return text.replace('\r\n', '\n')


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def diff_blocks(base_text, pkg_text, new_text):
    """用 `get_grouped_opcodes` **自动派生**替换块。

    🔴🔴🔴 **OLD 必须取自「包内实际内容」**（不是基线！）
      否则：同步一轮后包内已变 ⇒ 再跑时基线的 OLD **在包内命中 0 次**
      ⇒ 脚本中止（§91 实际踩到过：第二轮同步直接失败）。
      ⇒ 正确做法：**以包内实际内容为 a、仓库工作区为 b** 做 diff
      ⇒ OLD 必然来自包内 ⇒ **唯一命中**天然成立。

    ⚠️ `get_grouped_opcodes` 返回的是**分组列表**（每组含多个 opcode）
      ⇒ 必须**两级遍历**（先取组，再取组内的 5 元组）
      ⇒ 直接当 5 元组解包 ⇒ `ValueError`。
    """
    a = norm(pkg_text).splitlines(keepends=True)
    b = norm(new_text).splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = []
    for group in sm.get_grouped_opcodes(3):
        i1 = min(x[1] for x in group)
        i2 = max(x[2] for x in group)
        j1 = min(x[3] for x in group)
        j2 = max(x[4] for x in group)
        old = ''.join(a[i1:i2])
        new = ''.join(b[j1:j2])
        if old == new:
            continue
        blocks.append((old, new, (i1 + 1, i2, j1 + 1, j2)))
    return blocks


def main():
    check_only = '--check' in sys.argv
    pkg = find_pkg_dir()
    log('客户包 = %s' % pkg)
    log('基线 commit = %s' % BASE_COMMIT)

    total_changed = 0
    for rel in FILES:
        base = git_show(BASE_COMMIT, rel)
        cur = open(os.path.join(REPO, rel), 'r', encoding='utf-8',
                   newline='').read()
        pkg_path = os.path.join(pkg, rel.replace('live_caption/', 'app/', 1))
        if not os.path.isfile(pkg_path):
            raise SystemExit('包内缺文件：%s' % pkg_path)
        pkg_text = open(pkg_path, 'r', encoding='utf-8', newline='').read()

        if norm(pkg_text) == norm(cur):
            log('%-32s ALREADY（包内已是仓库最新）' % rel)
            continue

        blocks = diff_blocks(base, pkg_text, cur)
        log('%-32s 派生 %d 个替换块' % (rel, len(blocks)))
        if not blocks:
            log('  ⚠️ 无替换块 ⇒ 基线与当前差异无法用块表达 ⇒ 需人工核对')
            continue

        # 🔴 备份（包外）
        os.makedirs(BACKUP_DIR, exist_ok=True)
        bak = os.path.join(BACKUP_DIR, '%s.%d.bak'
                           % (os.path.basename(pkg_path), int(time.time())))
        shutil.copy2(pkg_path, bak)
        log('  备份 → %s' % bak)

        work = norm(pkg_text)
        for idx, (old, new, pos) in enumerate(blocks, 1):
            cnt = work.count(old)
            if cnt != 1:
                raise SystemExit(
                    '🔴 块 %d 在包内命中 %d 次（要求恰好 1 次）⇒ 中止\n'
                    '   OLD 前 120 字：%r' % (idx, cnt, old[:120]))
            work = work.replace(old, new, 1)
            log('  块 %d/%d 唯一命中并替换（%d 行 → %d 行）'
                % (idx, len(blocks), pos[1] - pos[0] + 1,
                   pos[3] - pos[2] + 1))

        # 🔴 归一化后必须与仓库**逐字一致**
        if work != norm(cur):
            raise SystemExit('🔴 替换后与仓库工作区不一致 ⇒ 中止（不写盘）')
        log('  ✅ 替换后归一化内容与仓库逐字一致（sha=%s）'
            % sha(norm(cur))[:16])

        if check_only:
            log('  --check：只查不写')
            continue

        with open(pkg_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(work)
        log('  已写入 %s（%d B）' % (pkg_path, os.path.getsize(pkg_path)))
        total_changed += 1

    # 🔴 最终一致性复核
    log('--- 最终复核 ---')
    ok = True
    for rel in FILES:
        cur = open(os.path.join(REPO, rel), 'r', encoding='utf-8',
                   newline='').read()
        pkg_path = os.path.join(pkg, rel.replace('live_caption/', 'app/', 1))
        pkg_text = open(pkg_path, 'r', encoding='utf-8', newline='').read()
        same = norm(pkg_text) == norm(cur)
        log('  %-32s %s' % (rel, 'MATCH' if same else 'DIFF'))
        ok = ok and same
    log('全部一致 = %s' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
