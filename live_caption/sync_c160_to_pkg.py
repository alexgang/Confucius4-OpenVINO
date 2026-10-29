#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c160_to_pkg.py — 把「§97」的三处修复同步到客户包。

## 要同步的变更

### ① `app/tts_worker.py`：APP-042 **定速时点**修复（真实缺陷）

reviewer APP-042 明文：「滞后 lag 定义为『这句的**实际开播时刻** −
这句的目标开播时刻』」。

🔴 **旧实现（错）**：主进程在 `submit()`（**提交时刻**）算
`lag = now − target_play_at` ⇒ 那只含「翻译延迟」
⇒ 实测 SPE 前 5 分钟 76 句**全部** `speed = 1.0`
（`app042_speed_distribution.csv` 只有 `1.0` 一行）
⇒ **加速链路从未真正生效** ⇒ B13（3 段 1.2–1.3×）FAIL。

🔴 **新实现（对）**：**worker 出队时**算 lag
（`time.time() − target_wall`，墙钟 ⇒ 跨进程可比）
⇒ 这才是「实际开播时刻」的**上界**（开播必在出队之后）
⇒ 用 run3 真实数据离线重放：**75/76 句**落在 1.2–1.3×。

⚠️ **向后兼容**：主进程仍下发 `speed`（老逻辑照旧），
但 worker **自己重算** ⇒ **以 worker 为准**
⇒ 老 worker（没这段代码）⇒ 行为不变。

### ② `app/tts_service.py`：新增 `register_spk_voice()` / `clear_spk_voices()`

⇒ APP-039/040「音色按句绑定」的**传输通道**（PCM base64 走 worker stdin）
⇒ **不落盘**（PCM 只在进程间传输）。

### ③ `app/live_caption_app.py`：APP-039/040 **接线**（GUI + CLI）

- `Session` 新增 `on_audio_span` ⇒ 喂 ASR 说话人旁路（含 `t_end` 时间轴）
- `_on_final` ⇒ 问旁路「这句是谁说的」⇒ **按句绑定**到音色表
- `_pump_spk_voices` / `_cli_pump_spk_voices` ⇒ **新 spk 才取样**并登记音色
- `tts.submit(..., spk=...)` ⇒ **按句**传音色给 worker
- 会话结束 ⇒ `reset()` + `clear_spk_voices()`（隐私：声纹只在内存里）

### ④ 新增两个文件（整体新增）

- `app/speaker_voice.py` —— 说话人音色表（只放内存，绝不落盘）
- `app/speaker_tracker.py` —— ASR-029 说话人旁路桥接（降级友好）

## 纪律

- **禁止整目录覆盖同步**；
- **OLD 取自包内实际内容**（不是基线 commit）⇒ difflib 派生替换块；
- **唯一命中断言**（`cur.count(old_blk) == 1`）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步 ⇒ `ALREADY`）；
- 备份目录**在包外**；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- **新增文件** ⇒ 逐字复制（并在写盘后校验 SHA256）。

## 用法

    python live_caption/sync_c160_to_pkg.py            # 同步
    python live_caption/sync_c160_to_pkg.py --check    # 只查差异
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import re
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_REL = 'app'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c160')

# 🔴 **定点同步**（OLD 取自包内实际内容 ⇒ difflib 派生替换块）
SYNC_FILES = [
    'live_caption/tts_worker.py',
    'live_caption/tts_service.py',
    'live_caption/live_caption_app.py',
]

# 🔴 **新增文件**（包内原本没有 ⇒ 逐字复制 + SHA256 校验）
NEW_FILES = [
    'live_caption/speaker_voice.py',
    'live_caption/speaker_tracker.py',
]


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
    """派生替换块。

    🔴🔴🔴 **带行号**（`i1/i2`）：短块在大文件里可能重复出现
    ⇒ 只靠 `str.count` 无法消歧 ⇒ **必须带行号**，用行号切片替换
    ⇒ 天然唯一（不再需要「命中 N 次就放弃」）。
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        blocks.append((''.join(old_lines[i1:i2]), ''.join(new_lines[j1:j2]),
                       _ctx_before(old_lines, i1), _ctx_after(old_lines, i2),
                       i1, i2, j1, j2))
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
    # 🔴🔴🔴 **按行号顺序替换**（difflib 已给出块在 old 中的行号）
    #   ⇒ 天然唯一（不依赖 `str.count`）⇒ 短块也能安全替换。
    #   ⚠️ 必须**从后往前**替换（否则前面的替换会挪动后面的行号）。
    blocks_rev = list(reversed(blocks))
    for old_blk, new_blk, anc_b, anc_a, i1, i2, j1, j2 in blocks_rev:
        cur_lines = cur.splitlines(keepends=True)
        # 🔴 **唯一命中断言**（行号切片的内容必须与 old_blk 逐字相同）
        actual = ''.join(cur_lines[i1:i2])
        if actual != old_blk:
            return dict(file=name, status='FAIL-block-drift', pkg=pkg_path,
                        detail='第 %d–%d 行内容与派生的 OLD 不一致'
                               % (i1, i2))
        new_lines = cur_lines[:i1] + new_blk.splitlines(keepends=True) \
            + cur_lines[i2:]
        cur = ''.join(new_lines)
        applied += 1

    # 写盘前校验：结果必须与仓库逐字一致
    if norm(cur) != new_txt:
        return dict(file=name, status='FAIL-mismatch-after', pkg=pkg_path,
                    detail='替换后与仓库不一致')

    # 🔴🔴🔴 **唯一命中断言**：每个块的 OLD 内容在**原包内**必须唯一。
    #   ⚠️ **短块例外**（如 `        _stretcher = None` 在 20 万行文件里
    #     出现 3 次）⇒ 这类块靠**行号定位 + 内容逐字校验**保证正确
    #     （见上面的 `FAIL-block-drift`）⇒ 对它们改用
    #     「**块 + 紧邻上下文**在包内唯一」来验证。
    for old_blk, new_blk, anc_b, anc_a, i1, i2, j1, j2 in blocks:
        if not old_blk.strip():
            continue
        n_hit = pkg_txt.count(old_blk)
        if n_hit == 1:
            continue
        # 🔴 用「块 + 后 5 行 + 前 5 行」的上下文窗口来消歧
        ctx = ''.join(anc_b[-5:]) + old_blk + ''.join(anc_a[:5])
        n_ctx = pkg_txt.count(ctx)
        if n_ctx != 1:
            return dict(file=name, status='FAIL-block-not-unique',
                        pkg=pkg_path,
                        detail='OLD 块命中 %d 次，且 ±5 行上下文窗口命中 '
                               '%d 次（要求恰好 1 次）' % (n_hit, n_ctx))

    before_sha = sha256_bytes(pkg_bytes)
    after_bytes = cur.encode('utf-8')
    after_sha = sha256_bytes(after_bytes)
    repo_sha = sha256_bytes(repo_bytes)
    after_norm_sha = sha256_bytes(norm(cur).encode('utf-8'))
    repo_norm_sha = sha256_bytes(norm(repo_txt).encode('utf-8'))

    if check_only:
        return dict(file=name, status='WOULD-SYNC', pkg=pkg_path,
                    blocks=len(blocks), applied=applied,
                    bytes_before=len(pkg_bytes), sha_before=before_sha,
                    bytes_after=len(after_bytes), sha_after=after_sha,
                    sha_after_norm=after_norm_sha, repo_sha=repo_sha,
                    repo_sha_norm=repo_norm_sha)

    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, '%s.%s.bak' % (name, before_sha[:12]))
    if not os.path.exists(bak):
        shutil.copy2(pkg_path, bak)

    with open(pkg_path, 'wb') as f:
        f.write(after_bytes)

    written = open(pkg_path, 'rb').read()
    if sha256_bytes(norm(written.decode('utf-8')).encode('utf-8')) != repo_norm_sha:
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


def add_new_file(rel: str, pkg: str, check_only: bool) -> dict:
    """🔴 **新增文件**：包内没有 ⇒ 逐字复制 + SHA256 校验。"""
    repo_path = os.path.join(REPO, rel.replace('/', os.sep))
    name = os.path.basename(rel)
    pkg_path = os.path.join(pkg, PKG_REL, name)
    repo_bytes = open(repo_path, 'rb').read()
    repo_sha = sha256_bytes(repo_bytes)
    if os.path.exists(pkg_path):
        pkg_bytes = open(pkg_path, 'rb').read()
        if sha256_bytes(pkg_bytes) == repo_sha:
            return dict(file=name, status='ALREADY', pkg=pkg_path,
                        bytes=len(pkg_bytes), sha=repo_sha)
        return dict(file=name, status='FAIL-exists-but-different',
                    pkg=pkg_path,
                    detail='包内已存在同名文件但内容不同（需人工确认）',
                    sha_pkg=sha256_bytes(pkg_bytes), sha_repo=repo_sha)
    if check_only:
        return dict(file=name, status='WOULD-ADD', pkg=pkg_path,
                    bytes_after=len(repo_bytes), sha_after=repo_sha)
    os.makedirs(os.path.dirname(pkg_path), exist_ok=True)
    with open(pkg_path, 'wb') as f:
        f.write(repo_bytes)
    written = open(pkg_path, 'rb').read()
    if sha256_bytes(written) != repo_sha:
        try:
            os.remove(pkg_path)
        except Exception:
            pass
        return dict(file=name, status='FAIL-sha-mismatch', pkg=pkg_path,
                    detail='写盘后 SHA 不一致（已删除）')
    return dict(file=name, status='ADDED', pkg=pkg_path,
                bytes_after=os.path.getsize(pkg_path),
                sha_after=sha256_bytes(written), repo_sha=repo_sha)


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
    for rel in SYNC_FILES:
        r = sync_file(rel, pkg, args.check)
        print('  [%s] %s' % (r.get('status'), r.get('file')))
        for k in ('blocks', 'applied', 'bytes_before', 'sha_before',
                  'bytes_after', 'sha_after', 'sha_after_norm',
                  'repo_sha_norm', 'backup', 'detail'):
            if r.get(k) is not None:
                print('        %-14s %s' % (k, r[k]))
        if r.get('status', '').startswith('FAIL'):
            ok = False
    for rel in NEW_FILES:
        r = add_new_file(rel, pkg, args.check)
        print('  [%s] %s（新文件）' % (r.get('status'), r.get('file')))
        for k in ('bytes_after', 'sha_after', 'repo_sha', 'detail'):
            if r.get(k) is not None:
                print('        %-14s %s' % (k, r[k]))
        if r.get('status', '').startswith('FAIL'):
            ok = False
    print()
    print('结果：%s' % ('OK' if ok else '存在 FAIL（未继续）'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
