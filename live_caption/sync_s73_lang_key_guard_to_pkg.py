#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s73_lang_key_guard_to_pkg.py —— 把「失控守卫的语言口径统一」同步到客户包。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 替换块**从 git 自动派生**（`difflib` + `get_grouped_opcodes(n=3)`）
  ⇒ **不手抄任何代码** ⇒ 抄错的风险归零；
- 每块**唯一命中断言**（`count == 1`）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 写盘时**保留包内原有的换行风格**；
- **幂等**：已同步则 no-op。

## 本轮要同步的变更（§78 自查抓出的真实缺陷）

**根因**：`tts_engine.estimate_frames()` / `estimate_sec()` 原先用
`_SEC_PER_CHAR.get((lang or 'en').lower(), _SEC_PER_CHAR['en'])`
⇒ **只认小写代号**（`zh`/`ja`/`ko`/`en`）；
但同文件的 `map_language()` **认得**全称与带区域写法
（`'Japanese'` / `'zh-cn'` / `'zh-tw'` / `'jp'` …）
⇒ **两套表解析同一个语言标识 ⇒ 口径不一致**：

| `lang` 传入 | 修复前 sec/字 | 真实值 | 低估倍数 |
|---|---|---|---|
| `'Japanese'` | 0.07（英文） | 0.15（日） | **2.1×** |
| `'zh-cn'`     | 0.07（英文） | 0.25（中） | **3.6×** |

⇒ 后果 = **失控守卫阈值算得过低**：
  - `RUNAWAY` 阈值 `max(3×est, est+8)` 用小 est ⇒ **更容易误杀正常长句**；
  - `clamp_max_new_tokens` 用小 est ⇒ **帧数上限偏松**（失控上限被放行）。

⚠️ 当前生产路径**恰好**只传小写代号（`translator.TARGETS` = zh/en/ja/ko）
⇒ 缺陷**未暴露**；但这属于「同一个标识两套口径」的隐患。

**修复**：新增 `_lang_key()`，**统一走 `map_language()`**（唯一映射表）再反查小写代号。
  🔴 **生产路径（小写代号）的 sec/frames/mnt 逐字不变** ⇒ 零回归（`app109` B 组 12 条判据）。

## 基线 commit

🔴 **不能用 `HEAD`** —— 本轮提交后 HEAD 就是新版本 ⇒ 无法派生替换块。
⇒ 用**同步前的固定 commit** `83cac33`（= §77 的交付 commit）。
⚠️ 已实测：包内 `tts_engine.py` 与 `83cac33` **逐字节一致**（LF 归一化后 SHA256 相同）
   ⇒ 可直接作为派生基线。

## 用法

    python live_caption/sync_s73_lang_key_guard_to_pkg.py --check   # 只查差异
    python live_caption/sync_s73_lang_key_guard_to_pkg.py            # 同步
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s73')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
TARGETS = [
    ('live_caption/tts_engine.py', 'app/tts_engine.py'),
]

# 🔴 **同步前的固定 commit**（不是 HEAD！见模块 docstring）
BASE_COMMIT = '83cac33'


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
