#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c159_to_pkg.py — 把「APP-042 CLI 路径不传 target_play_at」修复同步到客户包。

🔴🔴🔴 **为什么不用 `sync_c157_to_pkg.py`**（本轮实测踩到）：
  `sync_c157` 的基线 = **HEAD**（`head_commit()`）
  ⇒ 本轮修复**已经提交进 HEAD** ⇒ `derive_blocks(HEAD版, 仓库版)` = **空**
  ⇒ 报 `[NO-BLOCKS]` ⇒ **「看似同步成功、实际包里没改」**。
  ⇒ 🔴 **纪律**：定点同步的 OLD **必须取自「包内实际内容」**，
    基线 commit **只用于取参考** ⇒ 否则同步一轮后再跑会命中 0 次而中止。

## 要同步的变更（`app/live_caption_app.py`）

APP-042 的「自适应加速」依赖 `tts.submit(..., target_play_at=...)`。
**真机 CLI 回放实测证据**（`results/app/app042_soak_report.json` /
`app042_soak.wav.tts.jsonl`）：逐句 jsonl 里 `speed` 有值，
但 `target_wall` **恒为 None** ⇒ 加速参数**从未下发**
⇒ **CLI 下自适应加速链路永不触发**。

**根因**：目标墙钟机制**只做在 GUI `App` 类**
（`_session_wall0` 只在 `App.start()` 赋值；`App._on_final()` 里登记
`_seg_target_wall`）⇒ CLI 的三处 `tts.submit(...)` 全都不传 `target_play_at`。

**修法**：CLI 侧补齐**同一口径**（墙钟 `time.time()`，跨进程可比）：
- `_cli_wall0 = time.time()`（`s.start()` 之前 ⇒ 首句目标时刻不是 None）；
- `_cli_target_wall(seg)`（与 GUI `App._target_play_wall()` 同口径）；
- `on_final` 里**先登记**段号→目标墙钟，**再** submit；
- 三处 `tts.submit(...)` 全传 `target_play_at=`。

## 纪律

- **禁止整目录覆盖同步**；
- **OLD 取自包内实际内容**（不是基线 commit）⇒ difflib 派生替换块；
- **唯一命中断言**（`cur.count(old_blk) == 1`）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步 ⇒ `ALREADY`）；
- 备份目录**在包外**；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘。

## 用法

    python live_caption/sync_c159_to_pkg.py            # 同步
    python live_caption/sync_c159_to_pkg.py --check    # 只查差异
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

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_REL = 'app'
FILES = ['live_caption/live_caption_app.py']
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c159')


def norm(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\r', '\n')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def discover_pkg() -> str:
    cands = []
    for name in os.listdir(HOME):
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        m = re.search(r'_v(\d+(?:\.\d+)+)', name)
        if not m:
            continue
        if not os.path.isdir(os.path.join(HOME, name)):
            continue
        cands.append((tuple(int(x) for x in m.group(1).split('.')),
                      os.path.join(HOME, name)))
    if not cands:
        raise SystemExit('!! 找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def _ctx_before(old_lines, i1, max_ctx=12):
    out = []
    k = i1
    while k > 0 and len(out) < max_ctx:
        k -= 1
        out.append(old_lines[k])
    out.reverse()
    return out


def _ctx_after(old_lines, i2, max_ctx=12):
    out = []
    k = i2
    n = len(old_lines)
    while k < n and len(out) < max_ctx:
        out.append(old_lines[k])
        k += 1
    return out


def derive_blocks(old: str, new: str):
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        blocks.append((''.join(old_lines[i1:i2]), ''.join(new_lines[j1:j2]),
                       _ctx_before(old_lines, i1), _ctx_after(old_lines, i2)))
    return blocks


def sync_file(rel: str, pkg: str, check_only: bool) -> dict:
    repo_path = os.path.join(REPO, rel.replace('/', os.sep))
    name = os.path.basename(rel)
    pkg_path = os.path.join(pkg, PKG_REL, name)

    if not os.path.exists(pkg_path):
        return dict(file=name, status='SKIP-not-in-pkg', pkg=pkg_path)

    repo_bytes = open(repo_path, 'rb').read()
    pkg_bytes = open(pkg_path, 'rb').read()
    repo_txt = repo_bytes.decode('utf-8')
    pkg_txt = pkg_bytes.decode('utf-8')

    if norm(pkg_txt) == norm(repo_txt):
        return dict(file=name, status='ALREADY', pkg=pkg_path,
                    bytes=len(pkg_bytes), sha=sha256_bytes(pkg_bytes))

    # 🔴🔴 **OLD 取自「包内实际内容」**（不是基线 commit）
    old_txt = norm(pkg_txt)
    new_txt = norm(repo_txt)
    blocks = derive_blocks(old_txt, new_txt)
    if not blocks:
        return dict(file=name, status='NO-BLOCKS', pkg=pkg_path,
                    detail='包内与仓库差异无法派生出替换块')

    cur = pkg_txt
    applied = 0
    for old_blk, new_blk, anc_b, anc_a in blocks:
        if not old_blk.strip():
            # 纯新增块：用块前后公共上下文当锚点
            done = False
            for n in range(len(anc_b), 0, -1):
                joint = ''.join(anc_b[len(anc_b) - n:])
                if not joint.strip():
                    continue
                if cur.count(joint) == 1:
                    idx = cur.index(joint) + len(joint)
                    cur = cur[:idx] + new_blk + cur[idx:]
                    done = True
                    break
            if not done:
                for n in range(len(anc_a), 0, -1):
                    joint = ''.join(anc_a[:n])
                    if not joint.strip():
                        continue
                    if cur.count(joint) == 1:
                        idx = cur.index(joint)
                        cur = cur[:idx] + new_blk + cur[idx:]
                        done = True
                        break
            if not done:
                return dict(file=name, status='FAIL-block-cannot-anchor',
                            pkg=pkg_path, detail='纯新增块找不到唯一锚点')
            applied += 1
            continue

        cnt = cur.count(old_blk)
        if cnt == 0:
            if new_blk.strip() and cur.count(new_blk) == 1:
                applied += 1
                continue
            return dict(file=name, status='FAIL-block-not-found',
                        pkg=pkg_path, detail='块未命中')
        if cnt != 1:
            return dict(file=name, status='FAIL-block-not-unique',
                        pkg=pkg_path, detail='块命中 %d 次（要求恰好 1 次）' % cnt)
        cur = cur.replace(old_blk, new_blk, 1)
        applied += 1

    # 写盘前校验：结果必须与仓库逐字一致
    if norm(cur) != new_txt:
        return dict(file=name, status='FAIL-mismatch-after', pkg=pkg_path,
                    detail='替换后与仓库不一致')

    before_sha = sha256_bytes(pkg_bytes)
    after_bytes = cur.encode('utf-8')
    after_sha = sha256_bytes(after_bytes)
    repo_sha = sha256_bytes(repo_bytes)
    # 🔴 **仓库是 CRLF / 包内是 LF** ⇒ 原始字节 SHA 必然不同
    #   ⇒ **交付等价性必须按「归一化换行后」判定**
    #   ⇒ 同时报出两个 SHA（raw + norm），避免"看起来不一致"的假报警。
    after_norm_sha = sha256_bytes(norm(cur).encode('utf-8'))
    repo_norm_sha = sha256_bytes(norm(repo_txt).encode('utf-8'))

    if check_only:
        return dict(file=name, status='WOULD-SYNC', pkg=pkg_path,
                    blocks=len(blocks), applied=applied,
                    bytes_before=len(pkg_bytes), sha_before=before_sha,
                    bytes_after=len(after_bytes), sha_after=after_sha,
                    sha_after_norm=after_norm_sha, repo_sha=repo_sha,
                    repo_sha_norm=repo_norm_sha)

    # 备份（包外）
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, '%s.%s.bak' % (name, before_sha[:12]))
    if not os.path.exists(bak):
        shutil.copy2(pkg_path, bak)

    with open(pkg_path, 'wb') as f:
        f.write(after_bytes)

    # 写盘后校验（**归一化换行后**与仓库一致）
    written = open(pkg_path, 'rb').read()
    if sha256_bytes(norm(written.decode('utf-8')).encode('utf-8')) != repo_norm_sha:
        # 回滚
        shutil.copy2(bak, pkg_path)
        return dict(file=name, status='FAIL-sha-mismatch', pkg=pkg_path,
                    detail='写盘后与仓库不一致（已回滚）')
    return dict(file=name, status='SYNCED', pkg=pkg_path,
                blocks=len(blocks), applied=applied,
                bytes_before=len(pkg_bytes), sha_before=before_sha,
                bytes_after=os.path.getsize(pkg_path),
                sha_after=sha256_bytes(written),
                sha_after_norm=after_norm_sha,
                repo_sha=repo_sha, repo_sha_norm=repo_norm_sha, backup=bak)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('客户包目录：%s' % pkg)
    print('OLD 取自「包内实际内容」（不是基线 commit）')
    print()
    ok = True
    for rel in FILES:
        r = sync_file(rel, pkg, args.check)
        print('  [%s] %s' % (r.get('status'), r.get('file')))
        for k in ('blocks', 'applied', 'bytes_before', 'sha_before',
                  'bytes_after', 'sha_after', 'repo_sha', 'backup', 'detail'):
            if r.get(k) is not None:
                print('        %-12s %s' % (k, r[k]))
        if r.get('status', '').startswith('FAIL'):
            ok = False
    print()
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
