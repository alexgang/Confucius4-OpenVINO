#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s60_drop_atomic_to_pkg.py —— 把 §60 的「丢句记账原子化」同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换块**从 git 自动派生**（不手抄任何代码）⇒ 抄错的风险归零；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- 写盘时**保留包内原有的换行风格**（本包是 CRLF ⇒ 写回 CRLF）。

## 本轮要同步的变更（§60）

`app/tts_service.py`：

① **新增** `_drop_one(jid, register_dropped=False)`：
   丢句的**判定**（这句还在不在途）与**计数**（`n_dropped += 1`）
   **在同一把锁内**完成 ⇒ 只有「这句此刻确实还在 `pending` 里」才计丢句
   ⇒ 杜绝「worker 级 error 的孤儿清理」与 `submit()` / `_flush_queue()`
   交错时的**双记**。

② `submit()` 的三条丢句路径改用 `_drop_one()`：
   - `action == 'send'` 且 `_send()` 失败；
   - `action == 'dead'`（worker 已故障）；
   - 第二临界区的 `direct`（发送失败）与 `dead`（worker 已故障）分支。

③ `_flush_queue()` 的补发失败路径改为**按句**调用 `_drop_one()`
   （旧实现是循环外 `n_dropped += n_failed` ⇒ 无法按句判定）。

## 基线 commit

🔴 **不能用 `HEAD`** —— §60 提交后 HEAD 就是修复版 ⇒ 无法派生替换块。
⇒ 用**修复前的固定 commit** `b3c5ebb`（= §59 的 docs 提交，
   `tts_service.py` 内容与 §59 的 `36e3d1e` 一致 ⇒ **本缺陷类别尚未修**）。

## 用法

    python live_caption/sync_s60_drop_atomic_to_pkg.py --check   # 只查差异
    python live_caption/sync_s60_drop_atomic_to_pkg.py            # 同步
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s60')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
FILES = [
    'live_caption/tts_service.py',
]

# 🔴 **替换块基线**（修复前的固定 commit —— 不能用 HEAD）
BASELINE_COMMIT = 'b3c5ebb'

PKG_REL = 'app'


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def discover_pkg() -> str:
    """自动发现**版本号最大**的客户包目录（**不写死版本号**）。

    ⚠️ 目录名可能有 `v1.0.bak_20261020` 这类后缀 ⇒ 必须用**正则**取版本号
       —— `int(rsplit('_v',1)[1])` 会抛异常 ⇒ 整个目录列表被跳过
       ⇒ 报「找不到客户包目录」。
    """
    cands = []
    for name in os.listdir(HOME):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        m = re.search(r'_v(\d+(?:\.\d+)+)', name)
        if not m:
            continue
        if not os.path.isdir(os.path.join(HOME, name)):
            continue
        key = tuple(int(x) for x in m.group(1).split('.'))
        cands.append((key, os.path.join(HOME, name)))
    if not cands:
        raise SystemExit('!! 找不到客户包目录（%s 下没有 '
                         'Confucius4_LiveCaption_vX.Y/）' % HOME)
    cands.sort()
    return cands[-1][1]


def git_show(rel: str, commit: str) -> str:
    r = subprocess.run(['git', 'show', '%s:%s' % (commit, rel)], cwd=REPO,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120)
    if r.returncode != 0:
        raise SystemExit('!! git show 失败：%s@%s\n%s' % (rel, commit, r.stderr))
    return r.stdout


def norm(s: str) -> str:
    """归一化换行（仓库 ⇄ 包目录的 .py 常有 CRLF/LF 差异）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def derive_blocks(old: str, new: str):
    """用 difflib 把 old→new 切成若干**连续变更块**。

    每块 = (old_text, new_text, anchors)：
    - `old_text` 为空 ⇒ **纯新增** ⇒ 用 `anchors` 里的上下文定位插入点；
    - `old_text` 非空 ⇒ 用「唯一命中替换」。

    ⚠️ **纯新增块必须带上下文锚点** ⇒ 只看块内的新行是没用的
       （那些行在包内**根本不存在**）⇒ 必须取块**前后**的公共上下文。
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        blocks.append((''.join(old_lines[i1:i2]), ''.join(new_lines[j1:j2]),
                       _anchor_candidates(old_lines, i1, i2)))
    return blocks


def _anchor_candidates(old_lines, i1: int, i2: int):
    """给出插入点的**上下文锚点候选**（按「越长越具体」排序）。

    🔴 **为什么不能只用一行**：常见行（如 `            return False`）
       在文件里会出现**多次** ⇒ 单行锚点不唯一 ⇒ 定位失败。
    ⇒ 逐步加长上下文（1~6 行）⇒ 直到某一段在目标文件里**恰好出现 1 次**。

    每个候选 = (锚点文本, 插入位置)：`before` 表示插在锚点**之后**，
    `after` 表示插在锚点**之前**。
    """
    cands = []
    # ── 前置上下文：old_lines[i1-k : i1] ⇒ 插在它**之后** ──
    for k in range(1, 7):
        if i1 - k < 0:
            break
        chunk = ''.join(old_lines[i1 - k:i1])
        if chunk.strip():
            cands.append((chunk, 'after'))
    # ── 后置上下文：old_lines[i2 : i2+k] ⇒ 插在它**之前** ──
    for k in range(1, 7):
        if i2 + k > len(old_lines):
            break
        chunk = ''.join(old_lines[i2:i2 + k])
        if chunk.strip():
            cands.append((chunk, 'before'))
    return cands


def _anchor_insert(cur: str, new_blk: str, cands):
    """纯新增块（OLD 为空）⇒ 用**唯一锚点**插入。

    🔴 关键：**不能**用新块内部的行当锚点（那些行在包内**根本不存在**）
       ⇒ 必须用块**前后**的公共上下文。

    定位：逐个试锚点候选 ⇒ 要求该候选在包内**恰好出现 1 次**
       ⇒ 否则跳过 ⇒ 找到第一个唯一候选即插入。

    ⇒ 仍然是「唯一命中断言」的路子，不是整目录覆盖。
    """
    for anchor, mode in cands:
        if not anchor.strip():
            continue
        cnt = cur.count(anchor)
        if cnt != 1:
            continue
        idx = cur.index(anchor)
        if mode == 'after':
            idx += len(anchor)
        return cur[:idx] + new_blk + cur[idx:], True
    # 兜底：在新块里找一行**在包内已存在**且唯一的行当锚点
    lines = new_blk.splitlines(keepends=True)
    for ln in lines:
        if not ln.strip():
            continue
        if cur.count(ln) == 1:
            idx = cur.index(ln)
            return cur[:idx] + new_blk + cur[idx:], True
    return cur, False


def sync_file(rel: str, pkg: str, check_only: bool) -> dict:
    repo_path = os.path.join(REPO, rel)
    name = os.path.basename(rel)
    pkg_path = os.path.join(pkg, PKG_REL, name)

    if not os.path.exists(pkg_path):
        return dict(file=name, status='SKIP-not-in-pkg', pkg=pkg_path)

    with open(repo_path, 'rb') as f:
        repo_bytes = f.read()
    with open(pkg_path, 'rb') as f:
        pkg_bytes = f.read()

    repo_txt = repo_bytes.decode('utf-8')
    pkg_txt = pkg_bytes.decode('utf-8')

    # ── 幂等：包内已与仓库一致（归一化换行后）──
    if norm(pkg_txt) == norm(repo_txt):
        return dict(file=name, status='ALREADY', pkg=pkg_path,
                    bytes=len(pkg_bytes), sha=sha256_bytes(pkg_bytes))

    # ── 从 git 派生替换块（基线 = 修复前的固定 commit）──
    # 🔴 **必须先归一化换行再推导** ⇒ 否则 `git show` 的行尾（LF）与
    #   工作区/包目录（可能 CRLF）不同 ⇒ difflib 把**每一行**都判成变更
    #   ⇒ 推导出 N 个「纯新增」块（OLD 为空）⇒ 无法做「唯一命中替换」。
    old_txt = norm(git_show(rel, BASELINE_COMMIT))
    blocks = derive_blocks(old_txt, norm(repo_txt))
    if not blocks:
        return dict(file=name, status='NO-BLOCKS', pkg=pkg_path)

    # 🔴 **必须归一化换行后再替换**：替换块是从 `git show` 派生的（**LF**），
    #   而包内文件是 **CRLF** ⇒ 直接拿 LF 的块去 `count()` CRLF 的串
    #   ⇒ **恒命中 0 次** ⇒ 报「块未命中」。
    #   ⇒ 归一化后替换 ⇒ 写盘时再恢复包内原有的换行风格（见下方写盘段）。
    cur = norm(pkg_txt)
    applied = 0
    for old_blk, new_blk, cands in blocks:
        if not old_blk.strip():
            # 纯新增（old 为空）⇒ 用**上下文锚点**定位插入
            cur2, ok = _anchor_insert(cur, new_blk, cands)
            if not ok:
                return dict(file=name, status='FAIL-block-cannot-anchor',
                            pkg=pkg_path,
                            detail='纯新增块找不到唯一锚点')
            cur = cur2
            applied += 1
            continue
        cnt = cur.count(old_blk)
        if cnt == 0:
            # 包内可能已经有部分内容 ⇒ 幂等跳过
            if new_blk.strip() and cur.count(new_blk) == 1:
                continue
            return dict(file=name, status='FAIL-block-not-found',
                        pkg=pkg_path, detail='块未命中（包内与基线差异过大）')
        if cnt > 1:
            return dict(file=name, status='FAIL-block-not-unique',
                        pkg=pkg_path, detail='块命中 %d 次（要求恰好 1 次）' % cnt)
        cur = cur.replace(old_blk, new_blk, 1)
        applied += 1

    # ── 最终校验：必须与仓库版逐字一致（归一化换行）──
    if norm(cur) != norm(repo_txt):
        return dict(file=name, status='FAIL-mismatch-after',
                    pkg=pkg_path, applied=applied,
                    detail='替换后仍与仓库不一致')

    if check_only:
        return dict(file=name, status='WOULD-SYNC', pkg=pkg_path,
                    applied=applied, blocks=len(blocks))

    # ── 包外备份 ──
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, name + '.bak_' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(pkg_path, bak)

    # ── 写回（**保留包内原有的换行风格**）──
    #   本包是 CRLF ⇒ 若直接写仓库的 LF，diff 会把**每一行**都判成变更。
    crlf = '\r\n' in pkg_txt
    raw = cur.replace('\r\n', '\n').replace('\r', '\n')
    if crlf:
        raw = raw.replace('\n', '\r\n')
    raw = raw.encode('utf-8')
    tmp = pkg_path + '.tmp_s60'
    with open(tmp, 'wb') as f:
        f.write(raw)
    os.replace(tmp, pkg_path)

    # ── 落盘后复核 SHA256 ──
    after = sha256_file(pkg_path)
    return dict(file=name, status='SYNCED', pkg=pkg_path,
                applied=applied, blocks=len(blocks),
                bytes_before=len(pkg_bytes),
                sha_before=sha256_bytes(pkg_bytes),
                bytes_after=os.path.getsize(pkg_path),
                sha_after=after, backup=bak,
                repo_sha=sha256_bytes(repo_bytes),
                newline='CRLF' if crlf else 'LF')


def main():
    ap = argparse.ArgumentParser(
        description='把 §60 的「丢句记账原子化」同步到客户包（定点替换）')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('客户包：%s' % pkg)
    print('基线  ：%s（修复前的固定 commit）' % BASELINE_COMMIT)
    print('模式  ：%s' % ('check（不写盘）' if args.check else 'sync'))
    print()

    rows = []
    bad = False
    for rel in FILES:
        r = sync_file(rel, pkg, args.check)
        rows.append(r)
        st = r['status']
        if st.startswith('FAIL'):
            bad = True
        line = '  %-22s %s' % (r['file'], st)
        if 'sha_after' in r:
            line += '  %d → %d B  sha %s → %s' % (
                r.get('bytes_before', 0), r['bytes_after'],
                r['sha_before'][:12], r['sha_after'][:12])
        if 'blocks' in r:
            line += '  块 %d' % r['blocks']
        if 'newline' in r:
            line += '  行尾 %s' % r['newline']
        if 'detail' in r:
            line += '  ← ' + r['detail']
        if 'backup' in r and r['backup']:
            line += '\n        备份：%s' % r['backup']
        print(line)

    print()
    n_sync = sum(1 for r in rows if r['status'] == 'SYNCED')
    n_already = sum(1 for r in rows if r['status'] == 'ALREADY')
    print('同步 %d 个，已一致 %d 个，失败 %d 个' % (n_sync, n_already, bad))
    if bad:
        print('结论：FAIL —— 有文件未同步成功（**包内与仓库不一致**）')
        return 1
    print('结论：PASS —— 包内与仓库逐字一致（归一化换行）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
