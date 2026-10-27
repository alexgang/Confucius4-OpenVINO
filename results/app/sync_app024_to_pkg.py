#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-024① —— 仓库 live_caption/ → 客户包 app/ 的**定点同步**。

🔴🔴 纪律（`MEMORY.md` 一.1 / 一.9）：
  - 仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
    ⇒ **禁止整目录覆盖**、**禁止手抄代码**；
  - 替换块由 `git show <基线>` + `difflib.get_grouped_opcodes(n=3)`
    **自动派生**（不手抄），每个块在目标文件里必须**唯一命中**；
  - 🔴 **换行归一化**：仓库 `tts_service.py` 是 **CRLF**、客户包是 **LF**
    ⇒ 裸 diff 会把**整个文件**当成一个大块（实测 `-1503/+1550 行`）
    ⇒ 派生前**必须**把 old/new 都归一化为 LF，替换块因此**精确且唯一命中**；
  - 🔴 `difflib` 裸 `get_opcodes()` 的「纯新增块」old 是**空串**
    ⇒ `count('')` == len+1 ⇒ 报「命中 161148 次」这种**误导性报错**
    ⇒ 必须用 `get_grouped_opcodes(n=3)`。

用法：
    python sync_app024_to_pkg.py [--base <基线SHA>] [--dry-run]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.dirname(HERE))

import pkg_paths  # noqa: E402

REPO = pkg_paths.repo_root()
PKG = pkg_paths.pkg_app_dir()

FILES = ['tts_service.py', 'tts_worker.py']


def sha256(p: str) -> str:
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def git_show(rev: str, rel: str) -> str:
    out = subprocess.run(['git', 'show', '%s:%s' % (rev, rel)],
                         cwd=REPO, capture_output=True)
    if out.returncode != 0:
        raise SystemExit('git show 失败: %s (%s)'
                         % (rel, out.stderr.decode('utf-8', 'replace')))
    return out.stdout.decode('utf-8')


def norm(s: str) -> str:
    """🔴 换行归一化（LF）—— 派生与命中都用同一口径。"""
    return s.replace('\r\n', '\n')


def derive_blocks(old: str, new: str):
    """从 old→new 派生「精确替换块」(old_block, new_block)。均已归一化为 LF。"""
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    blocks = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for group in sm.get_grouped_opcodes(n=3):
        o, n = [], []
        for tag, i1, i2, j1, j2 in group:
            o.append(''.join(a[i1:i2]))
            if tag == 'equal':
                n.append(''.join(a[i1:i2]))
            else:
                n.append(''.join(b[j1:j2]))
        ob, nb = ''.join(o), ''.join(n)
        if ob != nb:
            blocks.append((ob, nb))
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='0d1be9d',
                    help='派生基线（默认 = APP-023 已入库的 commit）')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    print('=' * 74)
    print('APP-024① 定点同步：仓库 live_caption/ → 客户包 app/')
    print('基线(旧) = %s' % args.base)
    print('仓库     = %s' % REPO)
    print('客户包   = %s' % PKG)
    print('模式     = %s' % ('DRY-RUN（只读，不写）' if args.dry_run else '写入'))
    print('=' * 74)

    fail = 0
    for rel in FILES:
        old = norm(git_show(args.base, 'live_caption/' + rel))
        new = norm(io.open(os.path.join(REPO, 'live_caption', rel),
                           encoding='utf-8', newline='').read())
        dst = os.path.join(PKG, rel)
        cur = io.open(dst, encoding='utf-8', newline='').read()
        blocks = derive_blocks(old, new)
        print('\n── %s ──' % rel)
        print('  派生替换块 = %d（换行已归一化 LF）' % len(blocks))
        if not blocks:
            print('  （无改动）')
            continue
        out = cur
        bad = 0
        for i, (ob, nb) in enumerate(blocks, 1):
            cnt = out.count(ob)
            if cnt != 1:
                print('  ❌ 块 %d: 在包文件里命中 %d 次（要求恰好 1 次）⇒ 跳过'
                      % (i, cnt))
                print('     旧块首行: %r' % (ob.splitlines()[:1],))
                bad += 1
                continue
            out = out.replace(ob, nb, 1)
            print('  ✅ 块 %d: 唯一命中并替换（-%d/+%d 行）'
                  % (i, ob.count('\n'), nb.count('\n')))
        if bad:
            print('  ⚠️ 该文件有 %d 个块未应用 ⇒ **不写盘**' % bad)
            fail += bad
            continue
        if out == cur:
            print('  （替换后无变化 ⇒ 包已是最新）')
            continue
        if args.dry_run:
            print('  [DRY-RUN] 将写入 %d → %d 字节' % (len(cur), len(out)))
            continue
        # 🔴 写入前再核对：归一化后应与仓库**逐字节**相同
        repo_norm = norm(io.open(os.path.join(REPO, 'live_caption', rel),
                                 encoding='utf-8', newline='').read())
        if norm(out) != repo_norm:
            print('  🔴🔴 替换结果与仓库不一致 ⇒ **不写盘**')
            fail += 1
            continue
        io.open(dst, 'w', encoding='utf-8', newline='').write(out)
        print('  💾 已写入: %s' % dst)
        print('     sha256 = %s' % sha256(dst))

    print('\n' + '=' * 74)
    print('FAIL 计数 = %d' % fail)
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
