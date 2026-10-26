#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s61_dump_dir_to_pkg.py —— 把 §61 的「App CLI 暴露 --tts-dump-dir」同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换块**从 git 自动派生**（不手抄任何代码）⇒ 抄错的风险归零；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- 写盘时**保留包内原有的换行风格**（本包是 CRLF ⇒ 写回 CRLF）。

## 本轮要同步的变更（§61）

`app/live_caption_app.py`：

① **新增** CLI 参数 `--tts-dump-dir`
   （APP-021⑥ 要求「新增 `--tts-dump-dir`（或者在对话框里勾选『同时保存 wav』）」——
   离线朗读对话框的勾选框在 §54 已做，但 **App CLI 侧一直没有这个开关** ⇒
   只有 worker 有 `--dump-dir` ⇒ **从 App 命令行无法触发逐句 wav 落盘**）。

② CLI 模式的 `TTSService(...)` 构造**透传** `dump_dir=args.tts_dump_dir`
   （`TTSService.__init__` 早就有 `dump_dir` 参数，`start()` 也会拼 `--dump-dir`
   ⇒ 只差 App 这一层的接线）。

## 基线 commit

🔴 **不能用 `HEAD`** —— §61 提交后 HEAD 就是修复版 ⇒ 无法派生替换块。
⇒ 用**修复前的固定 commit** `3afaf7a`（= §60 的 fix 提交，
   `live_caption_app.py` 在 §61 之前的内容与之一致）。

## 用法

    python live_caption/sync_s61_dump_dir_to_pkg.py --check   # 只查差异
    python live_caption/sync_s61_dump_dir_to_pkg.py            # 同步
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s61')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
TARGETS = [
    ('live_caption/live_caption_app.py', 'app/live_caption_app.py'),
]

# 🔴 **修复前的固定 commit**（不是 HEAD！见模块 docstring）
BASE_COMMIT = '3afaf7a'


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(b: bytes) -> bytes:
    """归一化换行（CRLF/CR → LF）⇒ 比对与派生都用它。"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _detect_eol(b: bytes) -> bytes:
    """探测原文件的换行风格（\r\n 还是 \n）。"""
    return b'\r\n' if b'\r\n' in b else b'\n'


def _git_show(commit: str, rel: str) -> bytes:
    r = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git show %s:%s 失败: %s'
                           % (commit, rel, r.stderr.decode('utf-8', 'replace')))
    return r.stdout


def _pkg_dirs():
    """自动发现最大版本客户包目录（🔴 目录名可能有 `_bak_日期` 后缀
    ⇒ 必须用正则取版本号，不能用 `rsplit('_v',1)[1]`）。"""
    out = []
    for name in os.listdir(HOME):
        p = os.path.join(HOME, name)
        if not os.path.isdir(p):
            continue
        m = re.match(r'^Confucius4_LiveCaption_v(\d+)(?:\.\d+)*$', name)
        if m:
            out.append((int(m.group(1)), name, p))
    out.sort()
    return out


def _derive_blocks(old: bytes, new: bytes):
    """用 difflib 从「修复前 → 修复后」派生替换块（含上下文 ⇒ 唯一命中）。

    🔴🔴 **必须用 `get_grouped_opcodes(n=3)`**（带上下文），
    不能用裸 `get_opcodes()`：
      裸 opcodes 里「纯新增块」的 old 部分是**空串** ⇒
      `text.count('')` = len(text)+1 ⇒ 报「命中 161148 次」⇒ 误导性失败。
    ⇒ 带上下文后，每块都含**前后各若干行公共上下文** ⇒ 可唯一定位。
    """
    old_lines = _norm(old).decode('utf-8').splitlines(keepends=True)
    new_lines = _norm(new).decode('utf-8').splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for group in sm.get_grouped_opcodes(n=3):
        i1 = group[0][1]
        i2 = group[-1][2]
        j1 = group[0][3]
        j2 = group[-1][4]
        old_b = ''.join(old_lines[i1:i2])
        new_b = ''.join(new_lines[j1:j2])
        if old_b == new_b:
            continue
        blocks.append((old_b, new_b))
    return blocks


def _apply(text: str, old: str, new: str) -> str:
    n = text.count(old)
    if n != 1:
        raise AssertionError('期望恰好命中 1 次，实际 %d 次 ⇒ 块无法唯一定位' % n)
    return text.replace(old, new)


def sync_one(repo_rel: str, pkg_rel: str, pkg_root: str, check_only: bool):
    src = os.path.join(REPO, repo_rel.replace('/', os.sep))
    dst = os.path.join(pkg_root, pkg_rel.replace('/', os.sep))
    if not os.path.isfile(src):
        return ('SKIP', repo_rel, '仓库文件不存在')
    if not os.path.isfile(dst):
        return ('SKIP', repo_rel, '包内文件不存在: %s' % dst)

    with open(src, 'rb') as f:
        cur = f.read()
    with open(dst, 'rb') as f:
        disk = f.read()

    if _norm(disk) == _norm(cur):
        return ('ALREADY', repo_rel, '已与仓库一致，无需同步')

    base = _git_show(BASE_COMMIT, repo_rel)
    blocks = _derive_blocks(base, cur)
    if not blocks:
        return ('FAIL', repo_rel, '无法从 %s 派生替换块' % BASE_COMMIT)

    eol = _detect_eol(disk)
    text = _norm(disk).decode('utf-8')
    applied = 0
    for old_b, new_b in blocks:
        try:
            text = _apply(text, old_b, new_b)
            applied += 1
        except AssertionError as e:
            return ('FAIL', repo_rel, '块 %d 未唯一命中: %s' % (applied, e))
    out = text.replace('\n', eol.decode('utf-8')).encode('utf-8')

    # 🔴 写盘前必须与仓库版逐字一致（归一化换行）
    if _norm(out) != _norm(cur):
        return ('FAIL', repo_rel, '替换后与仓库版不一致 ⇒ 中止写盘')

    if check_only:
        return ('DIFF', repo_rel, '%d 块待同步（未写盘，--check）' % applied)

    # 备份（包外）
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(dst, os.path.join(BACKUP_DIR, os.path.basename(dst)))

    tmp = dst + '.s61tmp'
    with open(tmp, 'wb') as f:
        f.write(out)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, dst)
    return ('SYNCED', repo_rel,
            '%d 块；sha %s → %s（%d → %d B）'
            % (applied, _sha(disk)[:16], _sha(out)[:16], len(disk), len(out)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    dirs = _pkg_dirs()
    if not dirs:
        print('!! 找不到客户包目录')
        return 1
    ver, name, root = dirs[-1]
    print('客户包目录: %s（v%d）' % (root, ver))
    print('基线 commit: %s' % BASE_COMMIT)
    print('备份目录（包外）: %s' % BACKUP_DIR)
    print('-' * 70)

    rc = 0
    for repo_rel, pkg_rel in TARGETS:
        st, rel, msg = sync_one(repo_rel, pkg_rel, root, args.check)
        print('[%s] %s — %s' % (st, rel, msg))
        if st == 'FAIL':
            rc = 1
    print('-' * 70)
    print('结论：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
