#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-023 / APP-025 —— 仓库 live_caption/ → 客户包 app/ 的**定点同步**。

🔴🔴 纪律（`MEMORY.md` 一.1）：
  - 仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
    ⇒ **禁止整目录覆盖**；
  - 同步必须用「`git show <基线>` + `difflib` **自动派生**替换块」，
    **不手抄代码**；
  - 每个替换块在目标文件里必须**唯一命中**，否则 FAIL（不猜、不 fuzzy）。

用法：
    python sync_app023_to_pkg.py --base <基线SHA> [--dry-run]

基线默认 `6d7ef24^`（即本轮提交的前一个 commit）⇒ 派生出的就是**本轮改动**。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import os
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'

FILES = [
    'tts_cuda.py',
    'tts_service.py',
    'tts_worker.py',
    'live_caption_app.py',
    'offline_reader_gui.py',
]


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


def derive_blocks(old: str, new: str):
    """从 old→new 派生「精确替换块」(old_block, new_block)。

    🔴🔴 必须用 `get_grouped_opcodes(n=3)`（**带上下文**）：
      裸 `get_opcodes()` / `n=0` 会让「**纯新增块**」的 old 变成**空串**
      ⇒ `str.count('')` == len(s)+1 ⇒ 报「命中 161478 次」这种**误导性报错**，
      而且会把真正的替换块**静默跳过**（`MEMORY.md` 一.1 记的铁律，本轮又踩到）。
      ⇒ `n=3` 让每个块都带上 3 行上下文 ⇒ old 恒非空、且仍唯一命中。
    """
    a, b = old.splitlines(keepends=True), new.splitlines(keepends=True)
    blocks = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for group in sm.get_grouped_opcodes(n=3):
        o, n = [], []
        for tag, i1, i2, j1, j2 in group:
            if tag in ('equal',):
                o.append(''.join(a[i1:i2]))
                n.append(''.join(a[i1:i2]))
            else:
                o.append(''.join(a[i1:i2]))
                n.append(''.join(b[j1:j2]))
        ob, nb = ''.join(o), ''.join(n)
        if ob != nb:
            blocks.append((ob, nb))
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='6d7ef24^')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=PKG)
    args = ap.parse_args()

    print('=' * 74)
    print('APP-023 / APP-025 定点同步：仓库 live_caption/ → 客户包 app/')
    print('基线(旧) = %s' % args.base)
    print('客户包   = %s' % args.pkg)
    print('模式     = %s' % ('DRY-RUN（只读，不写）' if args.dry_run else '写入'))
    print('=' * 74)

    fail = 0
    for rel in FILES:
        rel_old = 'live_caption/' + rel
        old = git_show(args.base, rel_old)
        new = io.open(os.path.join(REPO, 'live_caption', rel),
                      encoding='utf-8').read()
        dst = os.path.join(args.pkg, 'app', rel)
        cur = io.open(dst, encoding='utf-8').read()
        blocks = derive_blocks(old, new)
        print('\n── %s ──' % rel)
        print('  派生替换块 = %d' % len(blocks))
        if not blocks:
            print('  （无改动）')
            continue
        out = cur
        for i, (ob, nb) in enumerate(blocks, 1):
            cnt = out.count(ob)
            if cnt != 1:
                print('  ❌ 块 %d: 在包文件里命中 %d 次（要求恰好 1 次）⇒ 跳过'
                      % (i, cnt))
                print('     旧块首行: %r' % (ob.splitlines()[:1],))
                fail += 1
                continue
            out = out.replace(ob, nb, 1)
            print('  ✅ 块 %d: 唯一命中并替换（-%d/+%d 行）'
                  % (i, ob.count('\n'), nb.count('\n')))
        if fail:
            print('  ⚠️ 该文件有块未应用 ⇒ **不写盘**')
            continue
        if out == cur:
            print('  （替换后无变化）')
            continue
        if args.dry_run:
            print('  [DRY-RUN] 将写入 %d → %d 字节' % (len(cur), len(out)))
            continue
        io.open(dst, 'w', encoding='utf-8', newline='').write(out)
        print('  💾 已写入: %s' % dst)
        print('     sha256 = %s' % sha256(dst))

    print('\n' + '=' * 74)
    print('FAIL 计数 = %d' % fail)
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
