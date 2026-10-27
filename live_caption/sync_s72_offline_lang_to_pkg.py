#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s72_offline_lang_to_pkg.py —— 把「离线朗读显式下传目标语言」同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 替换块**从 git 自动派生**（`difflib` + `get_grouped_opcodes(n=3)`）
  ⇒ **不手抄任何代码** ⇒ 抄错的风险归零；
- 每块**唯一命中断言**（`count == 1`）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 写盘时**保留包内原有的换行风格**；
- **幂等**：已同步则 no-op。

## 本轮要同步的变更（APP-030① 的补漏）

**根因**：§75 实现了 APP-030①（目标语言显式下传），但只覆盖了
**实时路径**（`live_caption_app.py` 的 `_pump_tts()` / CLI 两处）与
**CLI 路径**。🔴 **离线朗读路径漏了**：

- `live_caption/offline_reader.py` 的 `_loop()` 调用
      `self.svc.submit(self.segs[i], seg=self.seg_base - i)`
  **不带 `lang`** ⇒ worker 侧 `msg.get('lang')` 为空
  ⇒ 回落到 `_guess_lang()` ⇒ **只分 zh/en** ⇒ **日文永远收不到 Japanese**
  ⇒ 正是 APP-030 的**原始根因路径**（「日文发音偶发卡住」）。
- 🔴 这条路径**恰好是用户复现卡住最常走的那条**（离线朗读对话框）。

**修复（3 个文件）**：
① `offline_reader.py`：`OfflineReader.__init__` 新增 `lang` 关键字参数；
   `_loop()` 在 `lang` 有值时把它传进 `svc.submit(..., lang=...)`
   ⇒ **不传时命令体与改造前逐字一致**（向后兼容，旧假 service 不炸）。
② `offline_reader_gui.py`：对话框新增 `get_lang` 回调；
   创建 `OfflineReader` 时传 `lang=self._cur_lang()`；
   `open_dialog()` 接受并转发 `get_lang`。
③ `live_caption_app.py`：新增 `_offline_get_lang()`
   （取「翻译目标」下拉的当前值；下拉为「关闭」⇒ 返回 `None` ⇒ 不下传）
   并在 `open_dialog(...)` 里传 `get_lang=self._offline_get_lang`。

## 基线 commit

🔴 **不能用 `HEAD`** —— 本轮提交后 HEAD 就是新版本 ⇒ 无法派生替换块。
⇒ 用**同步前的固定 commit** `a9ed250`（= §76 的交付 commit）。
⚠️ 已实测：包内这 3 个文件与 `a9ed250` **逐字节一致**（LF 归一化后 SHA256 相同）
   ⇒ 可直接作为派生基线。

## 用法

    python live_caption/sync_s72_offline_lang_to_pkg.py --check   # 只查差异
    python live_caption/sync_s72_offline_lang_to_pkg.py            # 同步
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

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s72')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
TARGETS = [
    ('live_caption/offline_reader.py', 'app/offline_reader.py'),
    ('live_caption/offline_reader_gui.py', 'app/offline_reader_gui.py'),
    ('live_caption/live_caption_app.py', 'app/live_caption_app.py'),
]

# 🔴 **同步前的固定 commit**（不是 HEAD！见模块 docstring）
BASE_COMMIT = 'a9ed250'


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(b: bytes) -> bytes:
    """归一化换行（CRLF/CR → LF）⇒ 比对与派生都用它。"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _detect_eol(b: bytes) -> bytes:
    """探测原文件的换行风格（\\r\\n 还是 \\n）。"""
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
    """用 difflib 从「同步前 → 同步后」派生替换块（含上下文 ⇒ 唯一命中）。

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


def sync_one(repo_rel: str, pkg_rel: str, pkg_root: str, check_only: bool,
             prev_commit: str = None, base_from_disk: bool = False):
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

    # 🔴🔴 **基线选择**（优先级从高到低）：
    #   ① `--base-from-disk`：以包内当前内容为基线（增量同步用）
    #   ② `--prev-commit`：上一轮同步后的 commit
    #   ③ `BASE_COMMIT`：首次同步用
    #   ⚠️ 基线必须**逐字等于包内当前内容**，否则派生块对不上
    #     ⇒ 不匹配就**拒绝派生**（不许盲改）。
    base = None
    base_desc = ''
    if base_from_disk:
        base = disk
        base_desc = '包内当前内容（--base-from-disk）'
    else:
        for cand in ([prev_commit] if prev_commit else []) + [BASE_COMMIT]:
            if not cand:
                continue
            b = _git_show(cand, repo_rel)
            if _norm(b) == _norm(disk):
                base = b
                base_desc = cand
                break
        if base is None:
            return ('FAIL', repo_rel,
                    '基线 %s / %s 均与包内当前内容不一致 ⇒ 拒绝派生'
                    '（包可能被手工改过；如确为增量同步请加 --base-from-disk）'
                    % (prev_commit or '-', BASE_COMMIT))

    blocks = _derive_blocks(base, cur)
    if not blocks:
        return ('FAIL', repo_rel, '无法从基线派生替换块')

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

    tmp = dst + '.s72tmp'
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
    ap.add_argument('--prev-commit', default=None,
                    help='上一轮同步后的 commit（增量同步用）')
    ap.add_argument('--base-from-disk', action='store_true',
                    help='以**包内当前内容**为基线做增量同步。'
                         '⚠️ 安全性不降级：仍走 difflib 自动派生 + 唯一命中断言 '
                         '+ 写盘前与仓库版逐字一致校验。')
    args = ap.parse_args()

    dirs = _pkg_dirs()
    if not dirs:
        print('!! 找不到客户包目录')
        return 1
    ver, name, root = dirs[-1]
    print('客户包目录: %s（v%d）' % (root, ver))
    if args.base_from_disk:
        print('基线: 包内当前内容（--base-from-disk）')
    else:
        print('基线 commit: %s' % BASE_COMMIT)
        if args.prev_commit:
            print('增量基线: %s' % args.prev_commit)
    print('备份目录（包外）: %s' % BACKUP_DIR)
    print('-' * 70)

    rc = 0
    for repo_rel, pkg_rel in TARGETS:
        st, rel, msg = sync_one(repo_rel, pkg_rel, root, args.check,
                                args.prev_commit,
                                base_from_disk=args.base_from_disk)
        print('[%s] %s — %s' % (st, rel, msg))
        if st == 'FAIL':
            rc = 1
    print('-' * 70)
    print('结论：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
