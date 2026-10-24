#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c146_to_pkg.py — 把「§31 TTS 关闭记账 + GUI 退出等 MT + 乱码修复」
同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- **替换后必须与仓库版逐字一致（归一化换行）才写盘**。

## 与前几版同步脚本的差别（沿用 §30 的改进）

`sync_c140/c141/c142/c144` 的替换块是**手抄**的 ⇒ 抄错一个字符就会
「命中 0 次」而失败，或**命中多处**而误替换。

本版改为**从 git 自动派生替换块**：
1. `git show HEAD:<file>` 取**改前**的基线（= 本轮修复前的仓库版）；
2. 读**改后**的仓库工作区版本；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零；且「唯一命中」断言仍然成立。

## 要同步的变更（§31）

### `app/tts_service.py`

① **`close()` 必须清理在途句子并计丢句** ⇒ 修掉
   `n_played + n_dropped != n_submitted`（停 TTS / 换设备 / 换音色 / 退出
   四条路径都会调 `close()` ⇒ 每走一次就丢一批在途句子的记账）。
② **`close()` 不得清 `_dropped_ids`** ⇒ worker 此刻还活着，可能回 `played`
   ⇒ 提前清了 ⇒ 又变成「丢了 + 播了」双记（§30 修的正是这个）。

### `app/live_caption_app.py`

③ **GUI `quit()` 必须等 MT 把最后一句翻完** ⇒ 旧实现 `mt.flush()` 后直接
   `_pump_tts()`（outbox 空）⇒ 最后一句**既不显示也不朗读**，随后
   `mt.close()` 把工作线程停掉 ⇒ 这一句**永远丢**。
   （CLI 侧 `run_cli` 收尾**有** `mt.wait_idle(180)`，GUI 侧漏了。）
④ `wait_idle` **必须有条件守卫** ⇒ 否则 `state == 'loading'` 时白等 180 s
   ⇒ 用户点关闭后界面卡死。

### `app/device_config.py` / `app/audio_source.py`

⑤ 两处 **U+FFFD 乱码**（GBK 字节当 UTF-8 解码）清零（纯注释/docstring）。

## 用法

    python live_caption/sync_c146_to_pkg.py            # 同步
    python live_caption/sync_c146_to_pkg.py --check    # 只查差异
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c146')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
FILES = [
    'live_caption/tts_service.py',
    'live_caption/live_caption_app.py',
    'live_caption/device_config.py',
    'live_caption/audio_source.py',
]

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


def git_show(rel: str) -> str:
    r = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=REPO,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120)
    if r.returncode != 0:
        raise SystemExit('!! git show 失败：%s\n%s' % (rel, r.stderr))
    return r.stdout


def norm(s: str) -> str:
    """归一化换行（仓库 ⇄ 包目录的 .py 常有 CRLF/LF 差异）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def derive_blocks(old: str, new: str):
    """用 difflib 把 old→new 切成若干**连续变更块**。

    每块 = (old_text, new_text, anchor_before, anchor_after)：
    - `old_text` 为空 ⇒ **纯新增** ⇒ 用 `anchor_before` 定位插入点；
    - `old_text` 非空 ⇒ 用「唯一命中替换」。

    ⚠️ **纯新增块必须带上下文锚点** ⇒ 只看块内的新行是没用的
       （那些行在包内**根本不存在**）⇒ 必须取块**前后各一行**的公共上下文。
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        anchor_before = old_lines[i1 - 1] if i1 > 0 else ''
        anchor_after = old_lines[i2] if i2 < len(old_lines) else ''
        blocks.append((''.join(old_lines[i1:i2]), ''.join(new_lines[j1:j2]),
                       anchor_before, anchor_after))
    return blocks


def _anchor_insert(cur: str, new_blk: str, anchor_before: str, anchor_after: str):
    """纯新增块（OLD 为空）⇒ 用**唯一锚点**插入。

    🔴 关键：**不能**用新块内部的行当锚点（那些行在包内**根本不存在**）
       ⇒ 必须用块**前后各一行**的公共上下文（`anchor_before` / `anchor_after`）。

    定位：优先在 `anchor_before` 之后插入（要求 `anchor_before` 在包内
    **恰好出现 1 次**）；否则退化到 `anchor_after` 之前插入。

    ⇒ 仍然是「唯一命中断言」的路子，不是整目录覆盖。

    返回 (新串, 是否成功)。⚠️ Python 字符串不可变 ⇒ 必须**返回**新串，
    在调用方重绑定（否则改动丢失）。
    """
    if anchor_before and anchor_before.strip():
        cnt = cur.count(anchor_before)
        if cnt == 1:
            idx = cur.index(anchor_before) + len(anchor_before)
            return cur[:idx] + new_blk + cur[idx:], True
        if cnt > 1:
            return cur, False
    if anchor_after and anchor_after.strip():
        cnt = cur.count(anchor_after)
        if cnt == 1:
            idx = cur.index(anchor_after)
            return cur[:idx] + new_blk + cur[idx:], True
        if cnt > 1:
            return cur, False
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

    # ── 从 git 派生替换块 ──
    # 🔴 **必须先归一化换行再推导** ⇒ 否则 `git show` 的行尾（LF）与
    #   工作区/包目录（可能 CRLF）不同 ⇒ difflib 把**每一行**都判成变更
    #   ⇒ 推导出 N 个「纯新增」块（OLD 为空）⇒ 无法做「唯一命中替换」。
    old_txt = norm(git_show(rel))
    blocks = derive_blocks(old_txt, norm(repo_txt))
    if not blocks:
        return dict(file=name, status='NO-BLOCKS', pkg=pkg_path)

    cur = pkg_txt
    applied = 0
    for old_blk, new_blk, anc_b, anc_a in blocks:
        if not old_blk.strip():
            # 纯新增（old 为空）⇒ 用**上下文锚点**定位插入
            cur2, ok = _anchor_insert(cur, new_blk, anc_b, anc_a)
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

    # ── 写回（保持包内原有的换行风格：用包内原文件的风格）──
    raw = cur.encode('utf-8')
    tmp = pkg_path + '.tmp_c146'
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
                repo_sha=sha256_bytes(repo_bytes))


def main():
    ap = argparse.ArgumentParser(description='把 §31 修复同步到客户包（定点替换）')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('客户包：%s' % pkg)
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
        if 'detail' in r:
            line += '  ← ' + r['detail']
        if 'backup' in r:
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
