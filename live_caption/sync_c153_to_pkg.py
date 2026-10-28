#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c153_to_pkg.py — 把「§90 CUDA 边车 cancel 不可达修复」同步到客户包（**定点替换**）。

🔴 **纪律**（与 c146/c149/c151/c152 完全一致，仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 只做**精确字符串替换 + 唯一命中断言**；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘。

## 要同步的变更（§90）

### `app/tts_cuda_sidecar.py`

① **独立命令读取线程**（`_start_command_reader`）
   根因：旧实现的边车主循环**只在两次请求之间**读 stdin
   ⇒ 生成期间（`generate_voice_clone_streaming`）主循环**被阻塞**
   ⇒ `{'cmd':'cancel'}` **在生成结束前根本不会被读到**
   ⇒ `_CANCEL_RIDS` 在本次生成期间**恒为空**
   ⇒ 「边车每块检查一次」= **永远为 False** = **从未生效**
   ⇒ APP-030② 的失控守卫在 CUDA 路径上**从未成立**。
   修法：daemon 线程持续读 stdin ⇒ 控制命令（`ping`/`quit`/`set_ref`/`cancel`）
   **在生成期间也能到达**；合成请求**投递到 `_REQ_Q`** 仍由主循环**串行**处理。

② **`_CANCEL_RIDS` 改为锁保护**（`_CANCEL_LOCK` / `_cancel_pending` / `_take_cancel`）
   ⇒ 读线程写、主循环读 ⇒ 「读-判断-删」三步之间可能被插入 ⇒ 取消标志被吞。

③ **协议写锁**（`_OUT_LOCK`）
   ⇒ §90 起有**两条线程**会写 stdout（主循环发块 / 读线程回 ack）
   ⇒ 不加锁 ⇒ JSON 行与 PCM 字节**交错** ⇒ 客户端协议解析错乱。

④ **排队期间即被取消 ⇒ 立即放弃**（不白烧 GPU）。

### `app/tts_cuda.py`

⑤ **`_cancel_request` 必须等确认，否则杀并重启**
   APP-030② 明文：「**加 cancel 命令，边车每块检查一次；做不到就杀掉重启**」
   ⇒ 旧实现写命令**成功**就 `return` ⇒ **永远不会**触发「杀掉重启」
   ⇒ 即使边车根本不处理 cancel，客户端也**以为**取消已生效。
   修法：发命令 ⇒ 等 `{'cancelled': true}` 确认 ⇒ 确认了才算数；
   **等不到确认 ⇒ 杀掉并重启边车**（兜底兑现）。

⑥ **`_start_drain` 不得丢弃别的 rid 的消息**
   ⇒ 旧实现 `mr != rid` ⇒ `continue`（**直接丢**）
   ⇒ 排空线程与主合成线程**共用** `self._q`
   ⇒ 排空线程会把**下一句刚到的块 / cancel 确认**当成「别人的」丢掉
   ⇒ 下一句**少块或整句无输出**（静默丢音频）。
   修法：`_q_put_front()` 插回**队首**（保序 + 不丢 + 唤醒等待者）。

## 与前几版同步脚本的差别（沿用 §59 的改进）

替换块**不手抄** ⇒ 从 git 自动派生：
1. `git show <基线commit>:<file>` 取**改前**的基线；
2. 读**改后**的仓库工作区版本；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零；且「唯一命中」断言仍然成立。

## 用法

    python live_caption/sync_c153_to_pkg.py            # 同步
    python live_caption/sync_c153_to_pkg.py --check    # 只查差异
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c153')

FILES = [
    'live_caption/tts_cuda.py',
    'live_caption/tts_cuda_sidecar.py',
]

PKG_REL = 'app'

# 🔴 **基线 commit**：§90 改动**之前**的版本（不是 HEAD！）。
#    HEAD 若已含本轮改动 ⇒ 推导出「零变更块」。
BASE_COMMIT = 'ef830d6'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm(s: str) -> str:
    """归一化换行（仓库 LF ⇄ 包内 CRLF ⇒ 不能直接比）。"""
    return s.replace('\r\n', '\n')


def git_show(commit: str, rel: str):
    r = subprocess.run(['git', '-C', REPO, 'show', f'{commit}:{rel}'],
                       capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout.decode('utf-8', 'replace')


def find_pkg_dir():
    """自动发现**版本号最大**的客户包目录。"""
    best, best_key = '', None
    for name in os.listdir(HOME):
        m = re.match(r'^Confucius4_LiveCaption_v(\d+(?:\.\d+)*)$', name)
        if not m:
            continue
        d = os.path.join(HOME, name)
        if not os.path.isdir(os.path.join(d, PKG_REL)):
            continue
        key = tuple(int(x) for x in m.group(1).split('.'))
        if best_key is None or key > best_key:
            best_key, best = key, d
    return best


def diff_blocks(base: str, new: str):
    """把两份文本切成**连续变更块**（OLD/NEW 文本对）。

    🔴 用 `difflib.SequenceMatcher` 的 `get_grouped_opcodes(n=3)`
       ⇒ 每个块自带**上下文** ⇒ 在包内**唯一命中**。
    """
    b_lines = norm(base).splitlines(keepends=True)
    n_lines = norm(new).splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, b_lines, n_lines, autojunk=False)
    blocks = []
    # ⚠️ `get_grouped_opcodes(n)` 返回的是**分组列表**（每组含多个 opcode）
    #   ⇒ 必须**两级遍历**：先取组，再取组内的 (tag, i1, i2, j1, j2)
    for group in sm.get_grouped_opcodes(n=3):
        i1 = min(op[1] for op in group)
        i2 = max(op[2] for op in group)
        j1 = min(op[3] for op in group)
        j2 = max(op[4] for op in group)
        old = ''.join(b_lines[i1:i2])
        new = ''.join(n_lines[j1:j2])
        if old == new:
            continue
        blocks.append((old, new))
    return blocks


def apply_to_pkg(pkg_dir: str, check_only: bool):
    results = []
    for rel in FILES:
        pkg_path = os.path.join(pkg_dir, PKG_REL,
                                os.path.basename(rel))
        base = git_show(BASE_COMMIT, rel)
        if base is None:
            results.append((rel, 'FAIL-base-missing', ''))
            continue
        with open(os.path.join(REPO, rel), 'r', encoding='utf-8',
                  newline='') as f:
            new = f.read()
        if not os.path.isfile(pkg_path):
            results.append((rel, 'FAIL-pkg-missing', pkg_path))
            continue
        with open(pkg_path, 'r', encoding='utf-8', newline='') as f:
            pkg_text = f.read()

        # ── 幂等：包内已等于仓库版 ⇒ ALREADY ──
        if norm(pkg_text) == norm(new):
            results.append((rel, 'ALREADY', sha256_bytes(norm(pkg_text).encode())))
            continue

        blocks = diff_blocks(base, new)
        if not blocks:
            results.append((rel, 'FAIL-no-blocks', ''))
            continue

        text = pkg_text
        applied = 0
        for old, newblk in blocks:
            cnt = text.count(old)
            if cnt != 1:
                results.append((rel, 'FAIL-block-count-%d' % cnt,
                                old.strip().splitlines()[0][:70]
                                if old.strip() else ''))
                text = None
                break
            text = text.replace(old, newblk, 1)
            applied += 1
        if text is None:
            continue

        # 🔴 **必须与仓库版逐字一致（归一化换行）**才写盘
        if norm(text) != norm(new):
            results.append((rel, 'FAIL-mismatch-after', ''))
            continue

        if check_only:
            results.append((rel, 'WOULD-APPLY',
                            '%d 块' % applied))
            continue

        # 🔴 备份**必须在包外**
        os.makedirs(BACKUP_DIR, exist_ok=True)
        bpath = os.path.join(BACKUP_DIR, os.path.basename(rel))
        with open(bpath, 'wb') as f:
            f.write(pkg_text.encode('utf-8'))
        # 🔴 **不整目录覆盖** ⇒ 只写**这一个文件**
        with open(pkg_path, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        with open(pkg_path, 'r', encoding='utf-8', newline='') as f:
            after = f.read()
        ok = norm(after) == norm(new)
        results.append((rel, 'OK' if ok else 'FAIL-verify',
                        '%d 块 / SHA256=%s / 备份=%s'
                        % (applied, sha256_bytes(norm(after).encode())[:16],
                           os.path.basename(bpath))))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pkg', default='')
    args = ap.parse_args()

    pkg = args.pkg or find_pkg_dir()
    if not pkg or not os.path.isdir(pkg):
        print('找不到客户包目录')
        return 2
    print('客户包：%s' % pkg)
    print('基线 commit：%s' % BASE_COMMIT)
    res = apply_to_pkg(pkg, args.check)
    bad = 0
    for rel, status, detail in res:
        print('  %-34s %-18s %s' % (os.path.basename(rel), status, detail))
        if status.startswith('FAIL'):
            bad += 1
    print('  备份目录：%s' % BACKUP_DIR)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
