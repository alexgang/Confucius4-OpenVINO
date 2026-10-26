#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s48b_to_pkg.py —— §48 的**第二组**定点同步：把 HEAD 的 4 个文件同步进客户包。

## 为什么还要第二组

`live_caption/sync_s48_to_pkg.py`（第一组）只同步了 `tts_worker.py` +
`tts_engine.py`（流式化 + 内置音色探测）。
⇒ 但 HEAD 上还有 **3 个文件**与包内不一致，且**包内缺一个模块**：

| 文件 | 包内 | HEAD | 说明 |
|---|---|---|---|
| `app/live_caption_app.py` | 186 282 B | 193 226 B | APP-015 方案 C 渲染层（`import caption_render`）|
| `app/tts_cuda.py` | 9 519 B | 13 698 B | §48 的「不写死包版本号」 |
| `app/tts_cuda_sidecar.py` | 5 892 B | 8 035 B | 同上 |
| `app/caption_render.py` | **缺失** | 20 438 B | 方案 C 的渲染层模块 |

🔴 **`caption_render.py` 缺失是「已经真实发生过的事故」**
（`pkg_exclude.py` L281-290 的注释原文记录）：
`live_caption_app.py` 新增了 `import caption_render`，但同步脚本只替换了
`live_caption_app.py`、**漏了复制新的 `caption_render.py`**
⇒ 客户包启动即 `ModuleNotFoundError`。
⇒ 这正是 `pkg_exclude.find_missing_local_modules()` 这道闸门要防的形态
⇒ 本脚本**必须同时**做「替换 3 个文件」+「补 1 个新文件」。

## 同步机制（沿用 §30 / §47 / §48 的做法：**不手抄代码**）

替换块**从 git 自动派生**：
1. `git show <基线commit>:<file>` 取**改前**的基线（= 包内当前状态）；
2. 读**改后**的 HEAD 版本；
3. `difflib.SequenceMatcher` 按行对齐 ⇒ 切成若干**连续变更块**；
4. 🔴 **两条定位路径**（与 `sync_s48_to_pkg.py` 完全一致）：
   - **包内 == 基线**（`pkg_is_base=True`）⇒ 走**行号路径**：按 opcode 顺序
     替换、边走边累加偏移 ⇒ **纯插入块也无损**（纯插入块的 OLD 是空串，
     字符串路径根本定位不了）；
   - **包内 != 基线** ⇒ 走**字符串路径**：每个块的 OLD 必须在包内
     **恰好命中 1 次**；出现纯插入块 ⇒ 明确报错（不猜、不硬写）。
5. 全部替换完后，包内文件（归一化换行）必须与 HEAD 版**逐字一致**。

⚠️ **基线 commit 的选择**：这里用 **`ccb8b22`**（= §41 的「CUDA（PyTorch）本机可选后端」提交）。
实测（`git show <commit>:<file>` 逐个比对 40 个 commit）**包内那 3 个文件的内容
与 `ccb8b22` 逐字一致** ⇒ 它就是包内的真实基线。
⇒ 脚本会**先断言**「包内 == 基线」；不成立就报错（不猜、不硬写）。

⚠️ **为什么第一版会卡在「纯插入块」**：`live_caption_app.py` 的方案 C 渲染层
（`import caption_render`、`_render_lines()` 等）全是**新增** ⇒ 文本形式下
OLD 为空串 ⇒ 字符串路径**无解**。
⇒ 但「包内 == 基线」这个前提已实测成立 ⇒ 行号路径 100% 可靠。

## 新增文件（`caption_render.py`）

纯新增 ⇒ **没有 OLD 可替换** ⇒ 直接从 HEAD 复制。
但必须：
- 先断言包内**不存在**（已存在 ⇒ 走幂等分支）；
- 写完后断言与 HEAD **逐字一致**（归一化换行）。

## 备份

包外备份目录 `C:/Users/Trekker-PTL/pkg_backup_app_s48b/`
（**包外**，不污染客户包本身）。

## 用法

    python live_caption/sync_s48b_to_pkg.py            # 同步
    python live_caption/sync_s48b_to_pkg.py --check    # 只查差异，不写包
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s48b')

# 🔴 **基线 commit**：实测包内那 3 个文件与它**逐字一致**（§41 的 CUDA 后端提交）。
BASE_COMMIT = 'ccb8b22'

# ── 要「替换」的文件（包内已有 ⇒ 走精确字符串替换路径）─────────────
REPLACE_FILES = [
    'live_caption/live_caption_app.py',
    'live_caption/tts_cuda.py',
    'live_caption/tts_cuda_sidecar.py',
]

# ── 要「新增」的文件（包内缺失 ⇒ 从 HEAD 复制）──────────────────────
ADD_FILES = [
    'live_caption/caption_render.py',
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


def apply_blocks(cur: str, blocks, label: str, pkg_is_base: bool) -> str:
    """把变更块应用到 `cur`（包内内容，归一化换行）⇒ 返回**新内容**。

    🔴 **两条路径**（与 `sync_s48_to_pkg.py` 一致）：
    - `pkg_is_base=True`（包内与基线**逐字一致**）⇒ 用**基线行号 + 行列表**
      定位（纯插入块也无损）⇒ 100% 可靠；
    - `pkg_is_base=False` ⇒ 只能用**唯一命中的字符串**替换
      ⇒ 若 OLD 为空则**无解** ⇒ 明确报错（不猜）。
    """
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
        return '\n'.join(out_lines)

    # ── 字符串路径：每个块的 OLD 必须在包内**恰好命中 1 次** ────────
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
    return cur


def backup_pkg_file(pkg_file: str, tag: str):
    """包外备份（**不污染客户包本身**）。"""
    if not os.path.isfile(pkg_file):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dst = os.path.join(BACKUP_DIR, '%s__%s' % (os.path.basename(pkg_file), tag))
    shutil.copy2(pkg_file, dst)
    return dst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写包')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现）')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg) if args.pkg else discover_pkg()
    print('客户包目录:', pkg)
    print('基线 commit:', BASE_COMMIT)
    print()

    n_changed = 0
    n_already = 0
    n_blocks_total = 0

    # ── ① 替换类 ──────────────────────────────────────────────────
    for rel in REPLACE_FILES:
        name = os.path.basename(rel)
        pkg_file = os.path.join(pkg, PKG_REL, name)
        if not os.path.isfile(pkg_file):
            raise SystemExit('!! 包内缺文件：%s' % pkg_file)

        old_src = norm(git_show(rel))
        new_src = norm(git_show(rel, 'HEAD'))
        pkg_now = norm(open(pkg_file, 'r', encoding='utf-8',
                            newline='').read())

        if pkg_now == new_src:
            print('[ALREADY] %-24s 包内已与 HEAD 一致' % name)
            n_already += 1
            continue

        # 🔴 **先断言包内 == 基线**（否则只能走字符串路径）
        pkg_is_base = (pkg_now == old_src)
        if not pkg_is_base:
            print('[SKIP] %-24s 包内既不等于基线(%s)也不等于 HEAD ⇒ '
                  '**拒绝盲改**' % (name, BASE_COMMIT))
            print('       包内 %d B / 基线 %d B / HEAD %d B'
                  % (len(pkg_now), len(old_src), len(new_src)))
            continue

        blocks = derive_blocks(old_src, new_src)
        # 🔴 **先在内存里算一遍并复核**，确认结果与 HEAD 一致，
        #    再决定是否落盘（--check 时不写包）。
        out = apply_blocks(pkg_now, blocks, name, pkg_is_base)
        if norm(out) != new_src:
            raise SystemExit('!! %s：替换后与 HEAD 不一致 ⇒ 中止' % name)

        print('[CHANGED] %-22s %d 个变更块（%s路径）'
              % (name, len(blocks),
                 '行号' if pkg_is_base else '字符串'))
        n_blocks_total += len(blocks)
        n_changed += 1

        if args.check:
            continue

        bk = backup_pkg_file(pkg_file, time.strftime('%Y%m%d%H%M%S'))
        if bk:
            print('           备份：%s' % bk)
        # 保持包内原有的换行风格
        raw = open(pkg_file, 'rb').read()
        nl = '\r\n' if b'\r\n' in raw else '\n'
        with open(pkg_file, 'w', encoding='utf-8', newline='') as f:
            f.write(out.replace('\n', nl))

    # ── ② 新增类（纯复制）────────────────────────────────────────
    for rel in ADD_FILES:
        name = os.path.basename(rel)
        pkg_file = os.path.join(pkg, PKG_REL, name)
        new_src = norm(git_show(rel, 'HEAD'))

        if os.path.isfile(pkg_file):
            cur = norm(open(pkg_file, 'r', encoding='utf-8',
                            newline='').read())
            if cur == new_src:
                print('[ALREADY] %-24s 包内已存在且与 HEAD 一致' % name)
                n_already += 1
                continue
            raise SystemExit('!! %s：包内已存在但内容与 HEAD 不同 ⇒ '
                             '拒绝覆盖（请人工确认）' % name)

        print('[ADDED]  %-22s %d B（从 HEAD 复制）' % (name, len(new_src)))
        n_changed += 1
        if args.check:
            continue

        src_file = os.path.join(REPO, rel.replace('/', os.sep))
        shutil.copy2(src_file, pkg_file)
        cur = norm(open(pkg_file, 'r', encoding='utf-8',
                        newline='').read())
        if cur != new_src:
            raise SystemExit('!! %s：复制后与 HEAD 不一致 ⇒ 中止' % name)

    # ── ③ 复核：全部文件（替换类 + 新增类）都必须与 HEAD 逐字一致 ──
    print()
    print('=== 复核（归一化换行后与 HEAD 比对）===')
    ok = True
    for rel in REPLACE_FILES + ADD_FILES:
        name = os.path.basename(rel)
        pkg_file = os.path.join(pkg, PKG_REL, name)
        head = norm(git_show(rel, 'HEAD'))
        if not os.path.isfile(pkg_file):
            if args.check and rel in ADD_FILES:
                # --check 时新增文件还没落盘 ⇒ 用 HEAD 的内容做等价复核
                same = True
                print('  [PEND ] %-24s %d B  sha256=%s（--check：计划新增）'
                      % (name, len(head),
                         sha256_bytes(head.encode('utf-8'))[:16]))
            else:
                same = False
                print('  [MISS ] %-24s 包内缺失' % name)
            ok &= same
            continue
        cur = norm(open(pkg_file, 'r', encoding='utf-8', newline='').read())
        same = (cur == head)
        if args.check and not same:
            # --check 时替换类文件还没落盘 ⇒ 用**内存里算出的结果**做等价复核
            old_src = norm(git_show(rel))
            if cur == old_src:
                planned = apply_blocks(cur, derive_blocks(old_src, head),
                                       name, True)
                same = (planned == head)
                print('  [%s] %-24s %d B  sha256=%s（--check：计划替换后一致）'
                      % ('PLAN ' if same else 'FAIL ', name, len(planned),
                         sha256_bytes(planned.encode('utf-8'))[:16]))
            else:
                print('  [DIFF ] %-24s %d B  sha256=%s'
                      % (name, len(cur),
                         sha256_bytes(cur.encode('utf-8'))[:16]))
        else:
            print('  [%s] %-24s %d B  sha256=%s'
                  % ('MATCH' if same else 'DIFF ', name, len(cur),
                     sha256_bytes(cur.encode('utf-8'))[:16]))
        ok &= same

    print()
    if args.check:
        print('结论：%s（--check，未写包）'
              % ('一致' if ok else '存在差异'))
    else:
        print('结论：%s（改动 %d 个文件 / %d 个变更块 / 已同步 %d 个）'
              % ('PASS' if ok else 'FAIL', n_changed, n_blocks_total, n_changed))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
