#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s48_to_pkg.py —— 把 §48（APP-018）的生产代码改动**定点同步**到客户包。

## 本轮同步的文件（APP-018）

| 文件 | 改动 |
|---|---|
| `live_caption/tts_worker.py` | **流式合成 + 边合成边播**（首包从整句耗时降到真实首包）|
| `live_caption/tts_engine.py` | 新增 `builtin_speakers_available()`（内置音色探测）|
| `live_caption/tts_service.py` | （本轮**不改**——service 层逻辑无需变）|

⚠️ `pkg_exclude.py` / `pack_v13.py` **不进包**（它们是仓库侧的打包工具）
⇒ **不需要**同步。

## 同步机制（沿用 §30 / §47 / §48 的改进）

替换块**不手抄** ⇒ 从 git 自动派生：
1. `git show <基线commit>:<file>` 取**改前**的基线；
2. 读**改后**的仓库工作区版本；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零；且「唯一命中」断言仍然成立。

## 用法

    python live_caption/sync_s48_to_pkg.py            # 同步
    python live_caption/sync_s48_to_pkg.py --check    # 只查差异
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s48')

FILES = [
    'live_caption/tts_worker.py',
    'live_caption/tts_engine.py',
]

PKG_REL = 'app'

# 🔴 **基线 commit**：§48 改动**之前**的版本（不是 HEAD！）。
#    HEAD 若已含本轮改动 ⇒ 推导出「零变更块」。
BASE_COMMIT = '8ea36e2'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def discover_pkg() -> str:
    """自动发现**版本号最大**的客户包目录（**不写死版本号**）。"""
    cands = []
    for name in os.listdir(HOME):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        m = re.search(r'_v(\d+(?:\.\d+)+)', name)
        if not m:
            continue
        if not os.path.isdir(os.path.join(HOME, name, 'app')):
            continue
        key = tuple(int(x) for x in m.group(1).split('.'))
        cands.append((key, os.path.join(HOME, name)))
    if not cands:
        raise SystemExit('!! 找不到客户包目录（%s 下没有 '
                         'Confucius4_LiveCaption_vX.Y/app）' % HOME)
    cands.sort()
    return cands[-1][1]


def git_show(rel: str, commit: str = BASE_COMMIT) -> str:
    r = subprocess.run(['git', 'show', commit + ':' + rel], cwd=REPO,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120)
    if r.returncode != 0:
        raise SystemExit('!! git show 失败：%s@%s\n%s'
                         % (rel, commit, r.stderr))
    return r.stdout


def norm(s: str) -> str:
    """归一化换行（仓库 ⇄ 包目录的 .py 常有 CRLF/LF 差异）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def derive_blocks(old: str, new: str):
    """把 old→new 的差异切成若干**连续变更块**（已归一化换行）。

    每个块是 `(old_b, new_b, old_lines, new_lines, i1, i2, j1, j2)`：
    - `old_b` / `new_b`：文本形式（用于字符串替换路径）；
    - `old_lines` / `new_lines`：**行列表**（用于行号路径 —— 纯插入块
      在文本形式下是空串，无法定位；行列表则无损）。
    """
    a = old.split('\n')
    b = new.split('\n')
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        blocks.append(('\n'.join(a[i1:i2]), '\n'.join(b[j1:j2]),
                       a[i1:i2], b[j1:j2], i1, i2, j1, j2))
    return blocks


def apply_blocks(pkg_file: str, blocks, label: str, pkg_is_base: bool):
    """把变更块写进包内文件。

    🔴 **两条路径**：
    - `pkg_is_base=True`（包内与基线**逐字一致**）⇒ 用**基线行号 + 行列表**
      定位（纯插入块也无损）⇒ 100% 可靠；
    - `pkg_is_base=False` ⇒ 只能用**唯一命中的字符串**替换
      ⇒ 若 OLD 为空则**无解** ⇒ 明确报错（不猜）。
    """
    src = open(pkg_file, 'r', encoding='utf-8', newline='').read()
    cur = norm(src)
    applied = 0

    if pkg_is_base:
        # ── 行号路径：按 opcode 顺序替换，边走边累加偏移 ───────────
        base_lines = cur.split('\n')
        out_lines = []
        cur_i = 0            # 基线里已消费到的行号
        for _o, _n, _ol, new_lines, i1, i2, _j1, _j2 in blocks:
            # 先把基线里 [cur_i, i1) 原样搬过去
            out_lines.extend(base_lines[cur_i:i1])
            out_lines.extend(new_lines)
            cur_i = i2
        out_lines.extend(base_lines[cur_i:])
        cur = '\n'.join(out_lines)
        applied = len(blocks)
    else:
        for blk in blocks:
            old_b, new_b = blk[0], blk[1]
            if old_b == new_b:
                continue
            if old_b.strip() == '':
                raise SystemExit(
                    '!! %s：包内与基线不一致，且存在**纯插入块** ⇒ '
                    '无法用字符串替换定位 ⇒ 请先把包内对齐到基线，'
                    '或改用行号路径' % label)
            cnt = cur.count(old_b)
            if cnt != 1:
                raise SystemExit('!! %s：变更块命中 %d 次（应恰好 1 次）\n'
                                 '---- OLD ----\n%s\n---- END ----'
                                 % (label, cnt, old_b[:600]))
            cur = cur.replace(old_b, new_b, 1)
            applied += 1
    if applied == 0:
        return 0
    # 写回时保持**包内原有的换行风格**
    nl = '\r\n' if '\r\n' in src else '\n'
    out = cur.replace('\n', nl)
    with open(pkg_file, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    return applied


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写包')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现）')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg) if args.pkg else discover_pkg()
    print('客户包目录:', pkg)
    print('基线 commit:', BASE_COMMIT)
    print()

    total_blocks = 0
    total_applied = 0

    for rel in FILES:
        repo_path = os.path.join(REPO, rel.replace('/', os.sep))
        name = os.path.basename(rel)
        pkg_file = os.path.join(pkg, PKG_REL, name)

        if not os.path.isfile(pkg_file):
            raise SystemExit('!! 包内缺文件：%s' % pkg_file)

        old_src = git_show(rel)
        new_src = open(repo_path, 'r', encoding='utf-8', newline='').read()
        old_n = norm(old_src)
        new_n = norm(new_src)

        pkg_now = open(pkg_file, 'r', encoding='utf-8', newline='').read()
        pkg_n = norm(pkg_now)

        print('=' * 70)
        print('文件：%s' % rel)
        print('  仓库版 %d B / SHA256 %s'
              % (len(new_src.encode('utf-8')),
                 sha256_bytes(new_n.encode('utf-8'))[:16]))
        print('  包内版 %d B / SHA256 %s'
              % (len(pkg_now.encode('utf-8')),
                 sha256_bytes(pkg_n.encode('utf-8'))[:16]))

        if pkg_n == new_n:
            print('  [ALREADY] 包内已是目标形态（幂等）')
            continue

        blocks = derive_blocks(old_n, new_n)
        real_blocks = [b for b in blocks if b[0] != b[1]]
        print('  派生变更块：%d 个（其中非空 %d）'
              % (len(blocks), len(real_blocks)))
        total_blocks += len(real_blocks)

        if args.check:
            for i, (o, n, _ol, _nl, _i1, _i2, _j1, _j2) in enumerate(real_blocks, 1):
                print('    块%d：OLD %d 行 / NEW %d 行'
                      % (i, o.count('\n') + 1, n.count('\n') + 1))
            print('  [CHECK] 未写入（--check）')
            continue

        # ── 包外备份（不能放在包内，否则会被打进 zip）──
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = time.strftime('%Y%m%d_%H%M%S')
        bak = os.path.join(BACKUP_DIR, '%s.bak_%s' % (name, stamp))
        shutil.copy2(pkg_file, bak)

        pkg_is_base = (pkg_n == old_n)
        print('  包内 == 基线？ %s ⇒ %s'
              % ('是' if pkg_is_base else '否',
                 '用行号路径（含纯插入块）' if pkg_is_base
                 else '只能用字符串替换（纯插入块会报错）'))
        # ⚠️ 行号路径必须用**全部** opcode（含 old_b == new_b 的）
        #    ⇒ 否则偏移链断裂 ⇒ 重建结果与仓库版不一致。
        applied = apply_blocks(pkg_file, blocks, rel, pkg_is_base)
        total_applied += applied

        # ── 校验：包内必须与仓库版**逐字一致**（归一化换行）──
        after = norm(open(pkg_file, 'r', encoding='utf-8', newline='').read())
        if after != new_n:
            raise SystemExit('!! %s：同步后包内与仓库版**不一致** ⇒ 拒绝继续'
                             % rel)
        print('  [SYNCED] %s（%d 块唯一命中）' % (name, applied))
        print('           包外备份：%s' % bak)

    print()
    print('=' * 70)
    print('合计：变更块 %d / 已应用 %d' % (total_blocks, total_applied))
    if args.check:
        print('结论：CHECK（未写入）')
        return 0
    print('结论：%s' % ('PASS' if total_applied == total_blocks
                        else 'PARTIAL'))
    return 0 if total_applied == total_blocks else 1


if __name__ == '__main__':
    sys.exit(main())
