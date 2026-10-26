#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s49_to_pkg.py —— 把 §49（APP-018 第 1 条：**cp_decode 放 NPU**）
的生产代码改动**定点同步**到客户包。

## 本轮同步的文件

| 文件 | 改动 |
|---|---|
| `live_caption/tts_engine.py` | ① 新增 `CP_DECODE_NPU_SHAPE` 常量 ② 新增 `_cp_decode_ir_path()` / `_move_cp_decode_to_npu()` ③ `make_engine()` 里调用 |

⚠️ `results/app/proc_guard.py` / `results/app/app062_*.py` **不进包**
（它们是仓库侧的测量工具）⇒ **不需要**同步。

## 同步机制（沿用 §30 / §47 / §48 的纪律）

替换块**不手抄** ⇒ 从「包内 vs 仓库工作区」自动派生：
1. 读**包内**当前文件（基线）；
2. 读**仓库工作区**版本（目标）；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零。

## ⚠️ 为什么不用 `git show <commit>:` 派生

本仓库有**并发会话**在改同一批文件 ⇒ `git show HEAD:<file>` 的基线
**不等于**包内的实际内容 ⇒ 派生的块对不上。
⇒ 这里直接用「**包内文件**」当基线 ⇒ 与包内真实状态一致 ⇒ 最安全。

## 用法

    python live_caption/sync_s49_to_pkg.py            # 同步
    python live_caption/sync_s49_to_pkg.py --check    # 只查差异
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s49')

FILES = [
    'live_caption/tts_engine.py',
]

PKG_REL = 'app'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def discover_pkg() -> str:
    """自动发现**版本号最大**的客户包目录（**不写死版本号**）。"""
    cands = []
    for name in os.listdir(HOME):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        if not os.path.isdir(os.path.join(HOME, name, PKG_REL)):
            continue
        try:
            # ⚠️ 版本号可能是 "1.5"（小数）⇒ 不能用 int()
            ver = float(name.rsplit('_v', 1)[1])
        except Exception:
            continue
        cands.append((ver, os.path.join(HOME, name)))
    if not cands:
        raise SystemExit('[sync] 找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_text(path: str, text: str):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def norm(text: str) -> str:
    return text.replace('\r\n', '\n')


def derive_blocks(base_text: str, new_text: str):
    """按行派生连续变更块。

    返回 [(old_block, new_block, base_start, base_end, new_start, new_end)]。
    🔴 **必须用全部 opcode**（含 `old_b == new_b` 的）才能保持偏移链。
    """
    b_lines = norm(base_text).split('\n')
    n_lines = norm(new_text).split('\n')
    sm = difflib.SequenceMatcher(None, b_lines, n_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        old_b = '\n'.join(b_lines[i1:i2])
        new_b = '\n'.join(n_lines[j1:j2])
        blocks.append((old_b, new_b, i1, i2, j1, j2))
    return blocks, b_lines, n_lines


def apply_blocks(base_text: str, blocks, b_lines, n_lines) -> str:
    """按**行号路径**重建目标文本。

    🔴 必须用 `new_lines` 行列表（用 `'\n'.join(...)` 会丢空行）。
    """
    out = []
    pos = 0          # 基线行游标
    for (old_b, new_b, i1, i2, j1, j2) in blocks:
        out.extend(b_lines[pos:i1])
        out.extend(n_lines[j1:j2])
        pos = i2
    out.extend(b_lines[pos:])
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写入')
    ap.add_argument('--pkg', default=None)
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('[sync] 客户包：%s' % pkg)
    ok = True
    for rel in FILES:
        repo_path = os.path.join(REPO, rel)
        pkg_path = os.path.join(pkg, PKG_REL,
                                os.path.basename(rel))
        if not os.path.isfile(pkg_path):
            print('[sync] ⚠️ 包内没有 %s ⇒ 跳过' % rel)
            continue
        base_text = read_text(pkg_path)
        new_text = read_text(repo_path)
        if norm(base_text) == norm(new_text):
            print('[sync] ✅ %s 已是最新（无需改）' % rel)
            continue

        blocks, b_lines, n_lines = derive_blocks(base_text, new_text)
        real = [(o, n, i1, i2, j1, j2) for (o, n, i1, i2, j1, j2) in blocks
                if o != n]
        print('[sync] %s：%d 个变更块' % (rel, len(real)))
        for o, n, i1, i2, j1, j2 in real:
            print('   · 基线行 %d-%d → 目标行 %d-%d（OLD %d 行 / NEW %d 行）'
                  % (i1, i2, j1, j2, len(o.split('\n')), len(n.split('\n'))))

        # 唯一命中断言（对**纯替换**块有效；纯插入块 OLD 为空 ⇒ 跳过）
        for o, n, i1, i2, j1, j2 in real:
            if o == '':
                continue
            cnt = norm(base_text).count(o)
            if cnt != 1:
                print('   🔴 OLD 块命中 %d 次（应恰好 1 次）⇒ 拒绝写入'
                      % cnt)
                ok = False

        if not ok:
            print('[sync] 🔴 断言失败 ⇒ 未写入任何文件')
            return 2

        rebuilt = apply_blocks(base_text, blocks, b_lines, n_lines)
        if norm(rebuilt) != norm(new_text):
            print('   🔴 重建结果与仓库版不一致 ⇒ 拒绝写入')
            return 3

        if args.check:
            print('   （--check：不写入）')
            continue

        # 备份（包外）
        os.makedirs(BACKUP_DIR, exist_ok=True)
        bak = os.path.join(BACKUP_DIR,
                           '%s.bak_s49_%s' % (os.path.basename(rel),
                                              time.strftime('%H%M%S')))
        shutil.copy2(pkg_path, bak)
        print('   备份 → %s' % bak)

        write_text(pkg_path, rebuilt)
        # 逐字校验
        chk = read_text(pkg_path)
        if norm(chk) != norm(new_text):
            print('   🔴 写入后校验不一致 ⇒ 回滚')
            shutil.copy2(bak, pkg_path)
            return 4
        print('   ✅ 已同步并逐字校验通过'
              '（sha256 %s）' % sha256_bytes(chk.encode('utf-8'))[:16])

    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
