#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c168_to_pkg.py — 把 APP-045①④「克隆纯内存化 + 音色库不复制」同步到客户包。

🔴🔴🔴 **纪律（记忆 §一 / §九）**：
  - **禁止整目录覆盖同步**（仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**）；
  - 🔴 **OLD 必须取自「包内实际内容」**（不是基线 commit）
    ⇒ 用 `difflib` 从「包内现文件」与「仓库现文件」**派生**替换块；
  - 🔴 **唯一命中断言**（`cur.count(old_blk) == 1`）⇒ 命中 0 次 ⇒ **中止、不落盘**
    （§104 教训：命中 0 次 = **静默假同步**，比不同步更坏）；
  - 替换前后逐字节校验 SHA256；**幂等**（已同步 ⇒ 报 `ALREADY`）；
  - 备份目录**在包外**（`%TEMP%`）；
  - 🔴🔴 **行尾无关**（§一铁律）：仓库 CRLF / 包 LF ⇒ 用 bytes 读入、
    检测 `b'\r\n'` ⇒ 归一化 LF 匹配/替换 ⇒ 写回按**原行尾**还原
    ⇒ **断言「前后行尾不变」**；
  - 🔴🔴 **写盘前必须 `ast.parse` 校验**（§一铁律）：
    客户机 `ast.parse` 报 `unterminated string literal` ⇒ **客户机启动即崩**。

## 本轮同步的变更

**APP-045①（克隆纯内存化）**
  - `tts_engine.py`：新增 `speaker_embedding_from_pcm()` + `_mel_spectrogram_np_24000()`
    （**纯内存**复刻 babelvox 的 mel + speaker_enc ⇒ 不落盘）；
  - `tts_worker.py`：两处「落临时 wav 再提取 embedding」改为**直接送 numpy 数组**。

**APP-045④（内置音色不再复制到用户目录）**
  - `tts_engine.py`：`SpeakerLibrary(copy_builtins=True)` → `False`
    ＋ 新增 `_SpeakerLibraryWithBuiltinFallback`（内置音色走**只读回退**）。

## 用法

    python live_caption/sync_c168_app045_to_pkg.py            # 同步
    python live_caption/sync_c168_app045_to_pkg.py --check    # 只查差异
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
HOME = r'C:\Users\Trekker-PTL'
PKG_APP = os.path.join(HOME, 'Confucius4_LiveCaption_v1.13', 'app')

# 🔴 本轮要同步的文件（**只改这两个**；`shortcut_update.py` 是打包侧脚本，不进包）
# 🔴 APP-052：本次只有 `tts_engine.py` 有变更（新增 `_ov_out_to_array`）
#   ⇒ `tts_worker.py` 不在 TARGETS 里（内容未变 ⇒ 不动 ⇒ 遵守「只定点改」）
TARGETS = ('tts_engine.py',)

BACKUP = os.path.join(tempfile.gettempdir(),
                      'app045_backup_%s' % time.strftime('%Y%m%d_%H%M%S'))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_bytes(p: str) -> bytes:
    with open(p, 'rb') as f:
        return f.read()


def detect_eol(b: bytes) -> bytes:
    """🔴 **行尾无关**（§一）：检测原文件行尾风格。"""
    return b'\r\n' if b'\r\n' in b else b'\n'


def to_lf(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def from_lf(b: bytes, eol: bytes) -> bytes:
    return b.replace(b'\n', eol)


def derive_blocks(old_text: str, new_text: str):
    """🔴 从「包内实际内容」与「仓库现文件」派生替换块（difflib）。

    ⇒ OLD 取自**包内**（§104 教训：不能取基线 commit，否则第二轮命中 0 次）。

    🔴🔴 **纯插入块（old 为空）必须特殊处理**：
      `cur.count('')` = **字符串长度 + 1**（实测 49386 次）
      ⇒ 「唯一命中断言」会**永远失败** ⇒ 脚本根本跑不动。
      ⇒ 纯插入块改用**行位置插入**（`i1` 处的锚点行），
        锚点行**必须唯一命中**才落盘。
    """
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        old_blk = ''.join(old_lines[i1:i2])
        new_blk = ''.join(new_lines[j1:j2])
        # 🔴 纯插入 ⇒ 记录**唯一锚点**：
        #   用「插入点前一行 + 后一行」的**组合**（单行常常是空行 ⇒ 不唯一）
        #   ⇒ 组合必须唯一命中，否则中止。
        # 🔴 replace/delete 块也要记 `i1`（消歧时要用上下文窗口）
        anchor = ('ctx', i1)
        if not old_blk:
            if i1 == 0:
                anchor = ('head', old_lines[i2] if i2 < len(old_lines) else '')
            elif i2 >= len(old_lines):
                anchor = ('tail', old_lines[i1 - 1])
            else:
                anchor = ('mid', old_lines[i1 - 1], old_lines[i2], i1)
        blocks.append((tag, old_blk, new_blk, i1, anchor))
    return blocks


def sync_one(name: str, dry_run: bool = True):
    src = os.path.join(REPO, 'live_caption', name)
    dst = os.path.join(PKG_APP, name)
    if not os.path.isfile(src) or not os.path.isfile(dst):
        print('  [skip] %s：源或目标不存在' % name)
        return True, 'SKIP'

    src_b = read_bytes(src)
    dst_b = read_bytes(dst)
    src_eol = detect_eol(src_b)
    dst_eol = detect_eol(dst_b)

    src_lf = to_lf(src_b).decode('utf-8')
    dst_lf = to_lf(dst_b).decode('utf-8')

    if src_lf == dst_lf:
        print('  [ALREADY] %s：包内已与仓库一致（归一化行尾后）' % name)
        return True, 'ALREADY'

    blocks = derive_blocks(dst_lf, src_lf)
    if not blocks:
        print('  [NO-BLOCKS] %s：无法派生差异块' % name)
        return False, 'NO-BLOCKS'

    print('  [DIFF] %s：派生 %d 个替换块' % (name, len(blocks)))
    cur = dst_lf
    old_lines = dst_lf.splitlines(keepends=True)

    # 🔴🔴 **从后往前应用块**（倒序）：
    #   前面的替换会**改变**后面块所用的上下文/行号 ⇒ 正序会让锚点漂移
    #   ⇒ 命中 0 次（= 静默假同步的温床）⇒ 必须倒序。
    for idx, (tag, old_blk, new_blk, i1, anchor) in reversed(list(enumerate(blocks, 1))):
        if not old_blk:
            # 🔴 纯插入 ⇒ 用**唯一锚点组合**定位（基于**原始** old_lines）
            kind = anchor[0]
            if kind == 'head':
                a = anchor[1]
                cnt = cur.count(a)
                if cnt != 1:
                    print('    🔴 头锚点命中 %d 次 ⇒ **中止，不落盘**' % cnt)
                    return False, 'AMBIGUOUS-ANCHOR'
                cur = new_blk + cur
                print('    块%d [%s] 插到文件开头  new=%dB'
                      % (idx, tag, len(new_blk.encode('utf-8'))))
                continue
            if kind == 'tail':
                a = anchor[1]
                cnt = cur.count(a)
                if cnt != 1:
                    print('    🔴 尾锚点命中 %d 次 ⇒ **中止，不落盘**' % cnt)
                    return False, 'AMBIGUOUS-ANCHOR'
                cur = cur + new_blk
                print('    块%d [%s] 追加到文件末尾  new=%dB'
                      % (idx, tag, len(new_blk.encode('utf-8'))))
                continue
            # mid：插入点**前后**的原文窗口（逐步扩展直到唯一）
            ctx = 1
            pre = ''.join(old_lines[max(0, i1 - 1):i1])
            post = old_lines[i1] if i1 < len(old_lines) else ''
            combo = pre + post
            cnt = cur.count(combo)
            while cnt > 1 and ctx <= 12:
                ctx += 1
                lo = max(0, i1 - ctx)
                hi = min(len(old_lines), i1 + ctx)
                pre = ''.join(old_lines[lo:i1])
                post = ''.join(old_lines[i1:hi])
                combo = pre + post
                cnt = cur.count(combo)
            print('    块%d [%s] 组合锚点(上下文±%d行)命中 %d 次  new=%dB'
                  % (idx, tag, ctx, cnt, len(new_blk.encode('utf-8'))))
            if cnt != 1:
                print('    🔴 组合锚点命中 %d 次（应恰好 1 次）⇒ **中止，不落盘**' % cnt)
                return False, 'AMBIGUOUS-ANCHOR'
            cur = cur.replace(combo, pre + new_blk + post, 1)
            continue

        cnt = cur.count(old_blk)
        print('    块%d [%s] 命中 %d 次  old=%dB new=%dB'
              % (idx, tag, cnt, len(old_blk.encode('utf-8')),
                 len(new_blk.encode('utf-8'))))
        if cnt > 1:
            # 🔴 旧块不唯一 ⇒ **用上下文扩展消歧**（把块前后的行加进锚点）
            #    （块5 实测：old 72B 命中 2 次 ⇒ 必须消歧，否则改错地方）
            i1 = anchor[1] if anchor and anchor[0] == 'ctx' else None
            ctx = 1
            pre = ''.join(old_lines[max(0, i1 - 1):i1])
            post = ''.join(old_lines[i1 + old_blk.count('\n'):
                                       i1 + old_blk.count('\n') + 1])
            combo = pre + old_blk + post
            cnt2 = cur.count(combo)
            while cnt2 > 1 and ctx <= 12:
                ctx += 1
                lo = max(0, i1 - ctx)
                n_old = old_blk.count('\n')
                hi = min(len(old_lines), i1 + n_old + ctx)
                pre = ''.join(old_lines[lo:i1])
                post = ''.join(old_lines[i1 + n_old:hi])
                combo = pre + old_blk + post
                cnt2 = cur.count(combo)
            print('      ↳ 扩展上下文(±%d行)后命中 %d 次' % (ctx, cnt2))
            if cnt2 == 1:
                cur = cur.replace(combo, pre + new_blk + post, 1)
                continue
            print('    🔴 扩展后仍命中 %d 次 ⇒ **中止，不落盘**' % cnt2)
            return False, 'AMBIGUOUS'
        if cnt == 0:
            print('    🔴 命中 0 次（= 静默假同步）⇒ **中止，不落盘**')
            return False, 'AMBIGUOUS'
        cur = cur.replace(old_blk, new_blk, 1)

    if cur == dst_lf:
        print('  [NOOP] %s：替换后无变化' % name)
        return True, 'NOOP'

    # 🔴🔴 写盘前 **ast.parse 校验**（客户机启动即崩的防线）
    try:
        ast.parse(cur)
    except SyntaxError as e:
        print('    🔴 ast.parse 失败：%s ⇒ **中止，不落盘**' % e)
        return False, 'SYNTAX'

    if dry_run:
        print('  [CHECK] %s：%d 块待应用（未落盘）' % (name, len(blocks)))
        return True, 'CHECK'

    # ── 备份（包外）─────────────────────────────────────────────
    os.makedirs(BACKUP, exist_ok=True)
    shutil.copy2(dst, os.path.join(BACKUP, name))

    # ── 写回（**还原原行尾**）────────────────────────────────────
    out_b = from_lf(cur.encode('utf-8'), dst_eol)
    with open(dst, 'wb') as f:
        f.write(out_b)

    # ── 写后校验 ────────────────────────────────────────────────
    new_b = read_bytes(dst)
    if detect_eol(new_b) != dst_eol:
        print('    🔴 行尾风格被改变 ⇒ 回滚')
        shutil.copy2(os.path.join(BACKUP, name), dst)
        return False, 'EOL-CHANGED'
    if to_lf(new_b).decode('utf-8') != src_lf:
        print('    🔴 与仓库不一致 ⇒ 回滚')
        shutil.copy2(os.path.join(BACKUP, name), dst)
        return False, 'MISMATCH'
    try:
        ast.parse(to_lf(new_b).decode('utf-8'))
    except SyntaxError as e:
        print('    🔴 写后 ast.parse 失败 ⇒ 回滚：%s' % e)
        shutil.copy2(os.path.join(BACKUP, name), dst)
        return False, 'POST-SYNTAX'

    print('  [OK] %s：已同步  sha256 %s → %s'
          % (name, sha256_bytes(dst_b)[:16], sha256_bytes(new_b)[:16]))
    return True, 'OK'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='只查差异，不落盘')
    args = ap.parse_args()

    print('=' * 70)
    print('sync_c168 —— APP-045①④ 同步到客户包')
    print('  目标:', PKG_APP)
    print('  模式:', 'CHECK（不落盘）' if args.check else '同步')
    print('=' * 70)

    if not os.path.isdir(PKG_APP):
        print('!! 客户包 app/ 目录不存在:', PKG_APP)
        return 2

    all_ok = True
    for name in TARGETS:
        ok, status = sync_one(name, dry_run=args.check)
        all_ok = all_ok and ok
        if not ok:
            print('  ⇒ %s 失败 ⇒ **整体中止**（后续文件不处理）' % name)
            break

    print('-' * 70)
    if args.check:
        print('CHECK 完成（未落盘）')
    else:
        print('同步完成' if all_ok else '**同步失败**')
        if all_ok:
            print('备份目录:', BACKUP)
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
