#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c157_to_pkg.py — 把「APP-041 + APP-042」同步到客户包（**定点替换 + 新增文件**）。

🔴 **纪律**（与 c151–c156 完全一致，仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 只做**精确字符串替换 + 唯一命中断言**；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘。

## 要同步的变更

### 🆕 `app/time_stretch.py`（**新增文件**）
APP-042 的 WSOLA 时间伸缩模块（**纯 numpy** ⇒ 客户包零新增依赖）。
⇒ 客户包**没有**这个文件 ⇒ **整文件新增**（复制 + 逐字节校验）。

### `app/tts_worker.py`（APP-041 无改动 + APP-042）
① **`synth()` 接受 `speed` / `target_wall`** ⇒ 逐句变速（WSOLA，**流式**）。
② **流式变速**（`_stretcher.process(w)` / `.flush()`）⇒ 首块即可出声。
③ **命令解析读 `speed` / `target_wall`** ⇒ 合成队列元组多带 2 个字段。
④ **遥测**新增 `speed` / `in_dur_s` / `out_dur_s` / `speed_gain` /
   `play_wall` / `target_wall` / `play_lag_s`。
⑤ **`_dump_segment_wav` 支持 `suffix`** ⇒ 加速版 wav 落盘（供抽听）。

### `app/tts_service.py`（APP-042）
⑥ **`submit(..., target_play_at=)`** ⇒ 用 `speed_for_lag` 算倍率并随命令下发。
⑦ **`stats()` 暴露** `cur_speed` / `play_lag_s` / `peak_play_lag_s` /
   `n_speed_adjusted` / `speed_time_s`。
⑧ **`played` 事件回收** worker 回报的倍率与实际播放滞后。

### `app/live_caption_app.py`（APP-041 + APP-042）
⑨ **APP-041 启动流程**：`_arm_startup_tts` / `_maybe_startup_tts` /
   `_tts_startup_failed` + `_asr_ready` / `_asr_failed`
   ⇒ 默认「开启」**真的初始化**（不再需要「取消再勾一次」）。
⑩ **APP-042**：`_seg_target_wall` 登记 + `_target_play_wall()` +
   `submit(..., target_play_at=)` + 底栏显示「语速 / 播放滞后」。

## 基线

🔴 本轮改动**全部在工作区（未提交）** ⇒ 基线 = `HEAD`（动态取）。
⚠️ 提交后基线会变，但那时包内已同步 ⇒ 走 `ALREADY` 分支（幂等）。

## 用法

    python live_caption/sync_c157_to_pkg.py            # 同步
    python live_caption/sync_c157_to_pkg.py --check    # 只查差异
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c157')

FILES = [
    'live_caption/tts_worker.py',
    'live_caption/tts_service.py',
    'live_caption/live_caption_app.py',
]

#: 🆕 **新增文件**（包内原本没有 ⇒ 整文件复制）
NEW_FILES = [
    'live_caption/time_stretch.py',
]

PKG_REL = 'app'


def head_commit() -> str:
    r = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=60)
    return r.stdout.strip()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def discover_pkg() -> str:
    """自动发现**版本号最大**的客户包目录（不写死版本号）。"""
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
    r = subprocess.run(['git', 'show', commit + ':' + rel], cwd=REPO,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120)
    if r.returncode != 0:
        raise SystemExit('!! git show 失败：%s@%s\n%s' % (rel, commit, r.stderr))
    return r.stdout


def norm(s: str) -> str:
    """归一化换行（仓库 CRLF / 包 LF ⇒ 原始字节必 DIFF = 假报警）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


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


def _anchor_insert(cur: str, new_blk: str, ctx_before, ctx_after):
    for n in range(len(ctx_before), 0, -1):
        joint = ''.join(ctx_before[len(ctx_before) - n:])
        if not joint.strip():
            continue
        cnt = cur.count(joint)
        if cnt == 1:
            idx = cur.index(joint) + len(joint)
            return cur[:idx] + new_blk + cur[idx:], True
        if cnt == 0:
            break
    for n in range(len(ctx_after), 0, -1):
        joint = ''.join(ctx_after[:n])
        if not joint.strip():
            continue
        cnt = cur.count(joint)
        if cnt == 1:
            idx = cur.index(joint)
            return cur[:idx] + new_blk + cur[idx:], True
        if cnt == 0:
            break
    for ln in new_blk.splitlines(keepends=True):
        if not ln.strip():
            continue
        if cur.count(ln) == 1:
            idx = cur.index(ln)
            return cur[:idx] + new_blk + cur[idx:], True
    return cur, False


def sync_new_file(rel: str, pkg: str, check_only: bool) -> dict:
    """🆕 **新增文件** ⇒ 整文件复制（包内原本没有）。

    🔴 与「定点替换」不同：新增文件**没有旧内容**可替换
      ⇒ 唯一命中断言不适用 ⇒ 改为「复制后逐字节校验」。
    ⚠️ 包内**已存在同名文件**时：
      逐字节相同 ⇒ ALREADY；内容不同 ⇒ **FAIL**（绝不覆盖 ⇒ 需人工确认）。
    """
    repo_path = os.path.join(REPO, rel)
    name = os.path.basename(rel)
    pkg_path = os.path.join(pkg, PKG_REL, name)
    with open(repo_path, 'rb') as f:
        repo_bytes = f.read()
    repo_sha = sha256_bytes(repo_bytes)

    if os.path.exists(pkg_path):
        with open(pkg_path, 'rb') as f:
            pkg_bytes = f.read()
        if sha256_bytes(pkg_bytes) == repo_sha:
            return dict(file=name, status='ALREADY', pkg=pkg_path,
                        bytes=len(pkg_bytes), sha=repo_sha)
        if norm(pkg_bytes.decode('utf-8')) == norm(repo_bytes.decode('utf-8')):
            return dict(file=name, status='ALREADY', pkg=pkg_path,
                        bytes=len(pkg_bytes), sha=repo_sha,
                        detail='换行不同但内容一致')
        return dict(file=name, status='FAIL-new-file-exists-differs',
                    pkg=pkg_path,
                    detail='包内已有同名文件且内容不同 ⇒ **不覆盖**（需人工确认）')

    if check_only:
        return dict(file=name, status='WOULD-ADD', pkg=pkg_path,
                    bytes=len(repo_bytes), sha=repo_sha)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, name + '.bak_' + time.strftime('%Y%m%d_%H%M%S'))
    # ⚠️ 包内原本没有 ⇒ 无需备份内容；但为审计仍记一条说明
    with open(bak, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# 备份占位：同步前包内**不存在**该文件（新增文件）\n')

    tmp = pkg_path + '.tmp_c157'
    with open(tmp, 'wb') as f:
        f.write(repo_bytes)
    os.replace(tmp, pkg_path)
    after = sha256_file(pkg_path)
    if after != repo_sha:
        return dict(file=name, status='FAIL-sha-mismatch', pkg=pkg_path,
                    detail='写盘后 SHA 不一致')
    return dict(file=name, status='ADDED', pkg=pkg_path,
                bytes_after=os.path.getsize(pkg_path), sha_after=after,
                repo_sha=repo_sha, backup=bak)


def sync_file(rel: str, pkg: str, check_only: bool, base: str) -> dict:
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

    if norm(pkg_txt) == norm(repo_txt):
        return dict(file=name, status='ALREADY', pkg=pkg_path,
                    bytes=len(pkg_bytes), sha=sha256_bytes(pkg_bytes))

    old_txt = norm(git_show(rel, base))
    blocks = derive_blocks(old_txt, norm(repo_txt))
    if not blocks:
        return dict(file=name, status='NO-BLOCKS', pkg=pkg_path)

    cur = pkg_txt
    applied = 0
    for old_blk, new_blk, anc_b, anc_a in blocks:
        if not old_blk.strip():
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
            if new_blk.strip() and cur.count(new_blk) == 1:
                continue
            return dict(file=name, status='FAIL-block-not-found',
                        pkg=pkg_path, detail='块未命中（包内与基线差异过大）')
        if cnt > 1:
            return dict(file=name, status='FAIL-block-not-unique',
                        pkg=pkg_path, detail='块命中 %d 次（要求恰好 1 次）' % cnt)
        cur = cur.replace(old_blk, new_blk, 1)
        applied += 1

    if norm(cur) != norm(repo_txt):
        return dict(file=name, status='FAIL-mismatch-after',
                    pkg=pkg_path, applied=applied,
                    detail='替换后仍与仓库不一致')

    if check_only:
        return dict(file=name, status='WOULD-SYNC', pkg=pkg_path,
                    applied=applied, blocks=len(blocks))

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, name + '.bak_' + time.strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(pkg_path, bak)

    raw = cur.encode('utf-8')
    tmp = pkg_path + '.tmp_c157'
    with open(tmp, 'wb') as f:
        f.write(raw)
    os.replace(tmp, pkg_path)

    after = sha256_file(pkg_path)
    return dict(file=name, status='SYNCED', pkg=pkg_path,
                applied=applied, blocks=len(blocks),
                bytes_before=len(pkg_bytes),
                sha_before=sha256_bytes(pkg_bytes),
                bytes_after=os.path.getsize(pkg_path),
                sha_after=after, backup=bak,
                repo_sha=sha256_bytes(repo_bytes))


def main():
    ap = argparse.ArgumentParser(
        description='把 APP-041 + APP-042 同步到客户包（定点替换 + 新增文件）')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    base = head_commit()
    print('客户包目录：%s' % pkg)
    print('基线 commit：%s（HEAD）' % base)
    print()
    ok = True
    print('── 新增文件 ──')
    for rel in NEW_FILES:
        r = sync_new_file(rel, pkg, args.check)
        print('  [%s] %s' % (r.get('status'), r.get('file')))
        for k in ('bytes', 'bytes_after', 'sha', 'sha_after', 'repo_sha',
                  'backup', 'detail'):
            if r.get(k) is not None:
                print('        %-12s %s' % (k, r[k]))
        if r.get('status', '').startswith('FAIL'):
            ok = False
    print('── 定点替换 ──')
    for rel in FILES:
        r = sync_file(rel, pkg, args.check, base)
        print('  [%s] %s' % (r.get('status'), r.get('file')))
        for k in ('blocks', 'applied', 'bytes_before', 'sha_before',
                  'bytes_after', 'sha_after', 'backup', 'detail'):
            if r.get(k) is not None:
                print('        %-12s %s' % (k, r[k]))
        if r.get('status', '').startswith('FAIL'):
            ok = False
    print()
    print('结论：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
