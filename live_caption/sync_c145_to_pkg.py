#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c145_to_pkg.py — 把「§30 TTS 退出/双记修复」同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- **替换后必须与仓库版逐字一致（归一化换行）才写盘**。

## 与前几版同步脚本的差别（**本版改进**）

`sync_c140/c141/c142/c144` 的替换块是**手抄**的 ⇒ 抄错一个字符就会
「命中 0 次」而失败，或**命中多处**而误替换。

本版改为**从 git 自动派生替换块**：
1. `git show HEAD:<file>` 取**改前**的基线（= 本轮修复前的仓库版）；
2. 读**改后**的仓库工作区版本；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零；且「唯一命中」断言仍然成立。

## 要同步的变更（§30）

### `app/tts_service.py`

① **新增 `_dropped_ids` 集合** —— 登记「已被主进程丢弃、但 worker 可能仍会播出来」
   的 jid。
② **`_on_worker_exit()` 的「已重启过一次仍崩溃」分支必须清理在途句子**
   ⇒ 修掉 `pending` 永久悬挂 + `drain()` 必超时 + 少算。
③ **`cancel()` 登记 `_dropped_ids`**。
④ **句子级 `error` 不得重复计丢句**（这句可能早先已按积压被丢弃）。
⑤ **worker 级 `error` 清空 `_dropped_ids`**。
⑥ **`played` 事件：若该句已被丢弃 ⇒ 改记为「已播」**（`n_dropped -= 1`）
   ⇒ 修掉「丢了又播」的**双记**。
⑦ **`_update_backlog()` 丢句登记 `_dropped_ids`**。

### `app/tts_worker.py`

⑧ **播放前再查一次取消** —— 收窄「synth 线程已越过取消检查」的竞态窗口
   （权威判据仍在主进程 ①~⑦）。

## 实测证据（见 `results/app/`）

- `test_tts_exit_played.py` ⇒ 修复前 **4 项反证全部命中**
  （A4 pending 悬挂=[3,4] / A7 不变式被破坏 sum=3≠5 / A9 `drain()` 超时 8.0 s /
  B3 双记 sum=2>1）；修复后 **REAL 全 PASS + BUG 全落空 ⇒ PASS**；
- §20/§21/§22/§29 的 7 个既有套件 **全部未回归**。

## 用法
    python live_caption/sync_c145_to_pkg.py            # 执行
    python live_caption/sync_c145_to_pkg.py --check    # 只校验不写
    python live_caption/sync_c145_to_pkg.py --report <报告输出路径>
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, 'live_caption')

# 包外备份目录（绝不能放包内）
BACKUP_DIR = r'C:\Users\Trekker-PTL\pkg_backup_app016'

# ── 要同步的文件 ──────────────────────────────────────────────────────
FILES = ['tts_service.py', 'tts_worker.py']


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def norm(txt: str) -> str:
    """归一化换行（仓库 ⇄ 包的 .py 常有 CRLF/LF 差异）。"""
    return txt.replace('\r\n', '\n')


def git_head(rel_path: str) -> str:
    """取 `git show HEAD:<rel_path>` 的内容（LF 归一化）。"""
    out = subprocess.run(
        ['git', '-C', REPO, 'show', 'HEAD:' + rel_path],
        capture_output=True, check=True)
    return norm(out.stdout.decode('utf-8'))


def derive_patches(old: str, new: str):
    """从「改前 / 改后」两份文本派生**连续变更块**。

    返回 [(old_block, new_block), ...]，每个 block 都带**上下文**，
    保证在目标文件里**唯一命中**。
    """
    a = old.splitlines(keepends=True)
    b = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    patches = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        # 上下文：前后各 3 行（文件首尾则不越界）
        ctx = 3
        s1 = max(0, i1 - ctx)
        s2 = min(len(a), i2 + ctx)
        t1 = max(0, j1 - ctx)
        t2 = min(len(b), j2 + ctx)
        old_block = ''.join(a[s1:s2])
        new_block = ''.join(b[t1:t2])
        # 变更部分必须**真的**不同（否则无需替换）
        if old_block == new_block:
            continue
        patches.append((old_block, new_block))
    return patches


def find_pkg_dir() -> str:
    """自动发现最大版本的客户包目录。

    ⚠️ 目录名里可能带后缀（`v1.0.bak_20261020`）⇒ 版本号必须用**正则**
    只取 `v<数字>` 部分，否则 `int()` 抛异常 ⇒ 整个目录列表被跳过。
    """
    base = r'C:\Users\Trekker-PTL'
    cands = []
    for name in os.listdir(base):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        if not os.path.isdir(os.path.join(base, name, 'app')):
            continue
        m = re.search(r'_v(\d+)(?:\D|$)', name)
        if not m:
            continue
        cands.append((int(m.group(1)), os.path.join(base, name)))
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只校验不写')
    ap.add_argument('--report', default=None, help='报告输出路径')
    args = ap.parse_args()

    pkg = args.pkg or find_pkg_dir()
    pkg_app = os.path.join(pkg, 'app')

    report = {
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': pkg,
        'check_only': bool(args.check),
        'method': 'git-HEAD 派生替换块 + 唯一命中断言（不手抄代码）',
        'files': {},
        'patches': [],
    }

    if not args.check:
        os.makedirs(BACKUP_DIR, exist_ok=True)

    for fn in FILES:
        rel = 'live_caption/' + fn
        src = os.path.join(SRC, fn)
        dst = os.path.join(pkg_app, fn)
        if not os.path.exists(dst):
            print(f'  [SKIP] 包内没有 {fn}')
            continue

        with open(dst, 'r', encoding='utf-8', newline='') as f:
            pkg_txt = f.read()
        with open(src, 'r', encoding='utf-8', newline='') as f:
            src_txt = f.read()

        orig_sha = hashlib.sha256(pkg_txt.encode('utf-8')).hexdigest()
        orig_bytes = len(pkg_txt.encode('utf-8'))

        try:
            old_txt = git_head(rel)
        except subprocess.CalledProcessError:
            print(f'  [SKIP] 取不到 git HEAD 版 {rel}')
            continue

        patches = derive_patches(old_txt, src_txt)
        cur = pkg_txt
        applied, skipped = [], []

        for idx, (old, new) in enumerate(patches, 1):
            tag = f'{fn}#{idx}'
            n_old = cur.count(old)
            n_new = cur.count(new)
            if n_new == 1 and n_old == 0:
                skipped.append(tag)          # 已同步（幂等）
                continue
            if n_old != 1:
                raise SystemExit(
                    f'✗ {tag}: OLD 在 {fn} 命中 {n_old} 次（要求恰好 1 次）'
                    f' / NEW 命中 {n_new} 次 ⇒ 拒绝写入')
            cur = cur.replace(old, new, 1)
            applied.append(tag)

        # 归一化换行后必须与仓库版**逐字一致**
        if norm(cur) != norm(src_txt):
            import difflib as _dl
            d = list(_dl.unified_diff(norm(pkg_txt).splitlines(),
                                      norm(cur).splitlines(), lineterm='', n=0))
            raise SystemExit('✗ 替换后与仓库版不一致，拒绝写盘：\n' +
                             '\n'.join(d[:40]))

        if not args.check:
            bak = os.path.join(BACKUP_DIR, fn + '.bak_' +
                               time.strftime('%Y%m%d_%H%M%S'))
            shutil.copy2(dst, bak)
            with open(dst, 'w', encoding='utf-8', newline='') as f:
                f.write(cur)

        new_bytes = len(cur.encode('utf-8'))
        new_sha = hashlib.sha256(cur.encode('utf-8')).hexdigest()
        report['files'][fn] = {
            'path': dst,
            'orig_sha256': orig_sha,
            'orig_bytes': orig_bytes,
            'new_sha256': new_sha,
            'new_bytes': new_bytes,
            'n_patches_derived': len(patches),
            'applied': applied,
            'already_synced': skipped,
            'repo_sha256': hashlib.sha256(src_txt.encode('utf-8')).hexdigest(),
            'repo_bytes': len(src_txt.encode('utf-8')),
        }
        report['patches'].extend(applied)
        print(f'  [OK] {fn}: 派生 {len(patches)} 块 → 应用 {len(applied)}'
              f' / 幂等跳过 {len(skipped)}')

    # 落盘后复核
    if not args.check:
        for fn in FILES:
            dst = os.path.join(pkg_app, fn)
            src = os.path.join(SRC, fn)
            with open(dst, 'r', encoding='utf-8', newline='') as f:
                a = norm(f.read())
            with open(src, 'r', encoding='utf-8', newline='') as f:
                b = norm(f.read())
            same = (a == b)
            st = os.stat(dst)
            report['files'][fn]['verify_equal_to_repo'] = same
            report['files'][fn]['mtime'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))
            report['files'][fn]['actual_sha256'] = sha256_file(dst)
            report['files'][fn]['actual_bytes'] = st.st_size
            print(f'  [复核] {fn}: 与仓库一致={same} '
                  f'实际 {st.st_size} B sha256={sha256_file(dst)[:16]}…')

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f'  报告：{args.report}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
