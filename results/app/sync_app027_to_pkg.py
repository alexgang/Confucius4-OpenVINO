#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-027 —— 仓库 live_caption/ → 客户包 app/ 的**定点同步**（LF 归一化 + 唯一命中断言）。

🔴🔴 纪律（`MEMORY.md` 一.1）：
  - 仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本** ⇒ **禁止整目录覆盖**；
  - 同步必须用「difflib **自动派生**替换块」，且每个块在目标文件里**唯一命中**
    （否则 FAIL，不猜、不 fuzzy）；
  - 🔴🔴 **换行归一化**（§65 铁律）：仓库 .py 是 CRLF、客户包是 LF（且现状是**混合**）
    ⇒ 派生前必须把**两端**都归一化为 LF，否则裸 diff 把整文件当一块
    ⇒ 这里：git show 出来的原始串**去 \\r**；包文件用通用换行读（自动去 \\r）。

🔴🔴 **本轮改用 `pkg → HEAD` 派生**（不是 `BASE → HEAD`）：
  - 客户包当前状态**不一致**（tts_worker.py 已含**部分** APP-025/APP-027⑥ 改动，
    其余 4 个文件停在 2d19402），没有单一干净的 BASE；
  - 直接「包当前 → 仓库 HEAD」派生，能保证**最终状态 == HEAD** 且只动差异处，
    不会误删任何包内非相关改动（真有也会在唯一命中校验里暴露）。

用法：
    python sync_app027_to_pkg.py [--dry-run] [--pkg <客户包根>]
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
PKG_DEFAULT = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'

FILES = [
    'tts_worker.py',
    'tts_service.py',
    'tts_cuda.py',
    'tts_cuda_sidecar.py',
    'live_caption_app.py',
]


def sha256_text(p: str) -> str:
    with io.open(p, 'rb') as f:
        b = f.read()
    return hashlib.sha256(b).hexdigest()


def git_show(rev: str, rel: str) -> str:
    out = subprocess.run(['git', 'show', '%s:%s' % (rev, rel)],
                         cwd=REPO, capture_output=True)
    if out.returncode != 0:
        raise SystemExit('git show 失败: %s (%s)'
                         % (rel, out.stderr.decode('utf-8', 'replace')))
    # 🔴 原始串含 CRLF ⇒ 归一化为 LF（§65）
    return out.stdout.decode('utf-8').replace('\r', '')


def derive_blocks(old: str, new: str):
    """old→new 派生「精确替换块」（带 n=3 上下文），每个块唯一命中。

    🔴🔴 必须用 `get_grouped_opcodes(n=3)`：裸 `get_opcodes()` 会让「纯新增块」
    的 old 变空串 ⇒ `str.count('') == len+1` ⇒ 误导性「命中 161478 次」+ 静默跳过真块。
    """
    a = old.splitlines(keepends=True)
    b = new.splitlines(keepends=True)
    blocks = []
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for group in sm.get_grouped_opcodes(n=3):
        o, n = [], []
        for tag, i1, i2, j1, j2 in group:
            o.append(''.join(a[i1:i2]))
            n.append(''.join(b[j1:j2]))
        ob, nb = ''.join(o), ''.join(n)
        if ob != nb:
            blocks.append((ob, nb))
    return blocks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pkg', default=PKG_DEFAULT)
    args = ap.parse_args()
    pkg_root = args.pkg
    print('=' * 74)
    print('APP-027 定点同步：仓库 live_caption/ → 客户包 app/（pkg→HEAD，LF 归一化）')
    print('客户包根 = %s' % pkg_root)
    print('模式     = %s' % ('DRY-RUN（只读）' if args.dry_run else '写入'))
    print('=' * 74)

    fail = 0
    written = []
    for rel in FILES:
        dst = os.path.join(pkg_root, 'app', rel)
        if not os.path.isfile(dst):
            print('\n── %s ──\n  ⚠️ 客户包没有此文件 ⇒ 跳过' % rel)
            continue
        new = git_show('HEAD', 'live_caption/' + rel)
        # 🔴 包文件用通用换行读（自动去 \\r）⇒ 已是 LF
        cur = io.open(dst, encoding='utf-8').read()
        blocks = derive_blocks(cur, new)
        print('\n── %s ──' % rel)
        print('  派生替换块 = %d' % len(blocks))
        if not blocks:
            print('  （无改动，已 == HEAD）')
            continue
        out = cur
        ok_file = True
        for i, (ob, nb) in enumerate(blocks, 1):
            cnt = out.count(ob)
            if cnt != 1:
                print('  ❌ 块 %d: 命中 %d 次（要求恰好 1，否则跳过）' % (i, cnt))
                fail += 1
                ok_file = False
                continue
            out = out.replace(ob, nb, 1)
            print('  ✅ 块 %d: 唯一命中并替换（-%d/+%d 行）'
                  % (i, ob.count('\n'), nb.count('\n')))
        if not ok_file:
            print('  ⚠️ 该文件有块未应用 ⇒ **不写盘**')
            continue
        # 🔴🔴 验证：替换后必须 == HEAD（LF 归一化）
        if out != new:
            print('  ❌ 替换后 != HEAD（差 %d 行）⇒ 不写盘'
                  % abs(out.count('\n') - new.count('\n')))
            fail += 1
            continue
        if args.dry_run:
            print('  [DRY-RUN] 将写入 %d → %d 字节（LF）' % (len(cur), len(out)))
            continue
        io.open(dst, 'w', encoding='utf-8', newline='').write(out)
        h = sha256_text(dst)
        print('  💾 已写入: %s' % dst)
        print('     sha256 = %s' % h)
        written.append((rel, h))

    print('\n' + '=' * 74)
    print('FAIL 计数 = %d' % fail)
    if written:
        print('已写文件数 = %d' % len(written))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
