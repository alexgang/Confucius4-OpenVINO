#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s51_to_pkg.py —— 把 §51（**离线朗读**：文件 / 对话框文本 → TTS 播报）
的改动**定点同步**到客户包。

## 本轮同步的文件

| 文件 | 改动 |
|---|---|
| `live_caption/offline_reader.py` | **新增**：解析（txt/md/srt/vtt/docx/pdf）+ 分段 + 节流喂句控制器 |
| `live_caption/offline_reader_gui.py` | **新增**：离线朗读对话框（Tk Toplevel） |
| `live_caption/live_caption_app.py` | ① 语音输出分区加「📖 离线朗读…」按钮 ② `_offline_get_tts/_offline_ensure_tts/_open_offline_reader` ③ `quit()` 收尾先停朗读 |

⚠️ `results/app/app069_*.py` / `app070_*.py` 是**仓库侧自检** ⇒ **不进包**。

## 同步机制（沿用 §49 纪律，不手抄代码）

- **已有文件**：`difflib` 从「包内 vs 仓库工作区」派生替换块，OLD 必须**唯一命中**，
  重建后与仓库版**逐字一致**才写入（失败回滚备份）。
- **新增文件**：直接 copy2 + sha256 记录（包内没有基线，无从派生）。

## 用法

    python live_caption/sync_s51_to_pkg.py            # 同步
    python live_caption/sync_s51_to_pkg.py --check    # 只查差异
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s51')

EDIT_FILES = [
    'live_caption/live_caption_app.py',
]
NEW_FILES = [
    'live_caption/offline_reader.py',
    'live_caption/offline_reader_gui.py',
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
        if not os.path.isdir(os.path.join(HOME, name, PKG_REL)):
            continue
        try:
            ver = float(name.rsplit('_v', 1)[1])
        except Exception:
            continue
        cands.append((ver, os.path.join(HOME, name)))
    if not cands:
        raise SystemExit('[sync] 找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def write_text(path: str, text: str):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def norm(text: str) -> str:
    return text.replace('\r\n', '\n')


def derive_blocks(base_text: str, new_text: str):
    b_lines = norm(base_text).split('\n')
    n_lines = norm(new_text).split('\n')
    sm = difflib.SequenceMatcher(None, b_lines, n_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        blocks.append(('\n'.join(b_lines[i1:i2]), '\n'.join(n_lines[j1:j2]),
                       i1, i2, j1, j2))
    return blocks, b_lines, n_lines


def apply_blocks(base_text: str, blocks, b_lines, n_lines) -> str:
    out = []
    pos = 0
    for (_o, _n, i1, i2, j1, j2) in blocks:
        out.extend(b_lines[pos:i1])
        out.extend(n_lines[j1:j2])
        pos = i2
    out.extend(b_lines[pos:])
    return '\n'.join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='只查差异，不写入')
    ap.add_argument('--pkg', default=None)
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('[sync] 客户包：%s' % pkg)
    print('[sync] 模式：%s' % ('只查差异' if args.check else '写入'))
    fail = False

    # ── 新增文件：直接 copy ─────────────────────────────────────────────
    for rel in NEW_FILES:
        repo_path = os.path.join(REPO, rel)
        pkg_path = os.path.join(pkg, PKG_REL, os.path.basename(rel))
        src = open(repo_path, 'rb').read()
        if os.path.isfile(pkg_path):
            dst = open(pkg_path, 'rb').read()
            if norm(dst.decode('utf-8', 'replace')) == \
                    norm(src.decode('utf-8', 'replace')):
                print('[sync] ✅ %s 已是最新' % rel)
                continue
        if args.check:
            print('[sync] （将新增/覆盖）%s' % rel)
            continue
        os.makedirs(BACKUP_DIR, exist_ok=True)
        if os.path.isfile(pkg_path):
            bak = os.path.join(BACKUP_DIR, '%s.bak_s51_%s' % (
                os.path.basename(rel), time.strftime('%H%M%S')))
            shutil.copy2(pkg_path, bak)
            print('   备份 → %s' % bak)
        shutil.copy2(repo_path, pkg_path)
        chk = open(pkg_path, 'rb').read()
        same = sha256_bytes(chk) == sha256_bytes(src)
        print('   ✅ 新增 %s（sha256 %s，一致=%s）'
              % (rel, sha256_bytes(chk)[:16], same))
        fail |= not same

    # ── 已有文件：difflib 派生替换块 ────────────────────────────────────
    for rel in EDIT_FILES:
        repo_path = os.path.join(REPO, rel)
        pkg_path = os.path.join(pkg, PKG_REL, os.path.basename(rel))
        if not os.path.isfile(pkg_path):
            print('[sync] 🔴 包内没有 %s（预期应已存在）' % rel)
            fail = True
            continue
        base_text = read_text(pkg_path)
        new_text = read_text(repo_path)
        if norm(base_text) == norm(new_text):
            print('[sync] ✅ %s 已是最新（无需改）' % rel)
            continue

        blocks, b_lines, n_lines = derive_blocks(base_text, new_text)
        real = [(o, n, i1, i2, j1, j2) for (o, n, i1, i2, j1, j2) in blocks
                if o != n]
        print('[sync] %s：%d 个变更块' % (rel, len(real)))
        for o, n, i1, i2, j1, j2 in real:
            print('   · 基线行 %d-%d → 目标行 %d-%d（OLD %d 行 / NEW %d 行）'
                  % (i1, i2, j1, j2, len(o.split('\n')), len(n.split('\n'))))

        for o, n, i1, i2, j1, j2 in real:
            if o == '':
                continue
            cnt = norm(base_text).count(o)
            if cnt != 1:
                print('   🔴 OLD 块命中 %d 次（应恰好 1 次）⇒ 拒绝写入' % cnt)
                fail = True
        if fail:
            print('[sync] 🔴 断言失败 ⇒ 未写入')
            return 2

        rebuilt = apply_blocks(base_text, blocks, b_lines, n_lines)
        if norm(rebuilt) != norm(new_text):
            print('   🔴 重建结果与仓库版不一致 ⇒ 拒绝写入')
            return 3
        if args.check:
            print('   （--check：不写入）')
            continue

        os.makedirs(BACKUP_DIR, exist_ok=True)
        bak = os.path.join(BACKUP_DIR, '%s.bak_s51_%s' % (
            os.path.basename(rel), time.strftime('%H%M%S')))
        shutil.copy2(pkg_path, bak)
        print('   备份 → %s' % bak)

        write_text(pkg_path, rebuilt)
        chk = read_text(pkg_path)
        if norm(chk) != norm(new_text):
            print('   🔴 写入后校验不一致 ⇒ 回滚')
            shutil.copy2(bak, pkg_path)
            return 4
        print('   ✅ 已同步并逐字校验通过（sha256 %s）'
              % sha256_bytes(chk.encode('utf-8'))[:16])

    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
