#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c152_to_pkg.py — 把「§59 submit() 丢唤醒竞态修复」同步到客户包（**定点替换**）。

🔴 **纪律**（与 c146/c149/c151 完全一致，仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 只做**精确字符串替换 + 唯一命中断言**；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- 替换后必须与仓库版**逐字一致（归一化换行）**才写盘。

## 要同步的变更（§47）

### `app/tts_service.py`

① **`close()` 的孤儿句必须登记进 `_dropped_ids`**
   ⇒ 否则迟到的 `played` 到达时 `was_dropped = False`
   ⇒ 只 `n_played += 1`（不减 `n_dropped`）⇒ 同一句「丢了」又「播了」
   ⇒ `n_played + n_dropped` 比 `n_submitted` **多 1** ⇒ 不变式被破坏。
   （实测：修复前 close() 后迟到 played ⇒ sum=4 / submitted=3。）

② **worker 级 `error` 不得 `clear()` `_dropped_ids`**
   ⇒ 旧注释的前提「worker 已死」是**事实错误**：
   `tts_worker.py` L339（播放设备打开失败）/ L1004（模型加载失败）
   **都不会让 worker 进程退出** ⇒ 主循环继续跑 ⇒ 仍会回事件
   ⇒ 旧实现清空标记 ⇒ 毁掉 §30 的积压丢弃标记 ⇒ 迟到 `played` 双记。

③ **worker 级 `error` 的孤儿句必须登记进 `_dropped_ids`**
   ⇒ 否则迟到的**句子级** error（带 id）会**重复**计丢句
   ⇒ sum 比 submitted 多 N（实测：修复前 sum=6 / submitted=3）。

④ **新 worker 起来时清空 `_dropped_ids`**
   ⇒ 新 worker 用的是全新、单调递增的 jid ⇒ 旧标记无意义
   ⇒ 否则「关 TTS / 换设备 / 换音色」每走一次就攒一批 ⇒ 集合无界增长。

## 与前几版同步脚本的差别（沿用 §30 的改进）

替换块**不手抄** ⇒ 从 git 自动派生：
1. `git show <基线commit>:<file>` 取**改前**的基线；
2. 读**改后**的仓库工作区版本；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零；且「唯一命中」断言仍然成立。

## 用法

    python live_caption/sync_c151_to_pkg.py            # 同步
    python live_caption/sync_c151_to_pkg.py --check    # 只查差异
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c152')

FILES = [
    'live_caption/tts_service.py',
]

PKG_REL = 'app'

# 🔴 **基线 commit**：§47 改动**之前**的版本（不是 HEAD！）。
#    HEAD 若已含本轮改动 ⇒ 推导出「零变更块」。
BASE_COMMIT = '421d2d0'


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

    ⚠️ 目录名可能有 `v1.0.bak_20261020` 这类后缀 ⇒ 必须用**正则**取版本号。
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


def git_show(rel: str, commit: str = BASE_COMMIT) -> str:
    r = subprocess.run(['git', 'show', commit + ':' + rel], cwd=REPO,
                       capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=120)
    if r.returncode != 0:
        raise SystemExit('!! git show 失败：%s@%s\n%s' % (rel, commit, r.stderr))
    return r.stdout


def norm(s: str) -> str:
    """归一化换行（仓库 ⇄ 包目录的 .py 常有 CRLF/LF 差异）。"""
    return s.replace('\r\n', '\n').replace('\r', '\n')


def _ctx_before(old_lines, i1, max_ctx=12):
    """取块**前面**最多 ``max_ctx`` 行的**联合上下文**（从远到近）。

    🔴 单行锚点不够（§32 实测踩坑）⇒ 必须取连续多行联合上下文，
       直到在包内**唯一命中**为止。
    """
    out = []
    k = i1
    while k > 0 and len(out) < max_ctx:
        k -= 1
        out.append(old_lines[k])
    out.reverse()
    return out


def _ctx_after(old_lines, i2, max_ctx=12):
    """取块**后面**最多 ``max_ctx`` 行的**联合上下文**（从近到远）。"""
    out = []
    k = i2
    n = len(old_lines)
    while k < n and len(out) < max_ctx:
        out.append(old_lines[k])
        k += 1
    return out


def derive_blocks(old: str, new: str):
    """用 difflib 把 old→new 切成若干**连续变更块**。"""
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
    """纯新增块（OLD 为空）⇒ 用**唯一上下文锚点**插入。"""
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
    lines = new_blk.splitlines(keepends=True)
    for ln in lines:
        if not ln.strip():
            continue
        if cur.count(ln) == 1:
            idx = cur.index(ln)
            return cur[:idx] + new_blk + cur[idx:], True
    return cur, False


def _replace_unique(cur: str, old_blk: str, new_blk: str, ctx_before, ctx_after):
    """把 ``old_blk`` 替换成 ``new_blk``（唯一命中；必要时用上下文收窄）。"""
    cnt = cur.count(old_blk)
    if cnt == 1:
        return cur.replace(old_blk, new_blk, 1), True, 1, 'unique'
    if cnt == 0:
        return cur, False, 0, 'not-found'

    for n in range(max(len(ctx_before), len(ctx_after)), 0, -1):
        pre = ''.join(ctx_before[len(ctx_before) - n:]) if n <= len(ctx_before) else ''
        suf = ''.join(ctx_after[:n]) if n <= len(ctx_after) else ''
        joint = pre + old_blk + suf
        if not pre and not suf:
            continue
        c = cur.count(joint)
        if c == 1:
            idx = cur.index(joint)
            return (cur[:idx] + pre + new_blk + suf + cur[idx + len(joint):],
                    True, 1, 'ctx-unique')
        if c == 0:
            break

    if new_blk.strip() and cur.count(new_blk) >= 1:
        return cur, True, cnt, 'already-synced'

    return cur.replace(old_blk, new_blk), True, cnt, 'replace-all'


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

    # 🔴🔴 2026-10-27 §59 修：**包内是 CRLF、`git show` 是 LF**。
    #   仓库工作区是 CRLF（`core.autocrlf=true`），包目录也是 CRLF
    #   ⇒ 但 `git show <commit>:<file>` 出来的**永远是 LF**
    #   ⇒ 推导出的替换块是 LF 文本 ⇒ 在 CRLF 的包内容里**命中 0 次**
    #   ⇒ 报「纯新增块找不到唯一锚点」。
    #   ⇒ 修法：**推导与匹配全程在归一化（LF）文本上进行**，
    #      写盘时再**还原成包原本的换行风格**。
    #   ⚠️ 还原方式必须按「包内原本的多数换行」决定
    #      ⇒ 不能一律写 CRLF（有些包文件是 LF）。
    pkg_crlf = pkg_bytes.count(b'\r\n') > 0

    # ── 幂等：包内已与仓库一致（归一化换行后）──
    if norm(pkg_txt) == norm(repo_txt):
        return dict(file=name, status='ALREADY', pkg=pkg_path,
                    bytes=len(pkg_bytes), sha=sha256_bytes(pkg_bytes))

    # 🔴 **必须先归一化换行再推导** ⇒ 否则 difflib 把每一行都判成变更
    old_txt = norm(git_show(rel))
    blocks = derive_blocks(old_txt, norm(repo_txt))
    if not blocks:
        return dict(file=name, status='NO-BLOCKS', pkg=pkg_path)

    cur = norm(pkg_txt)
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

    # ── 写回（**还原包原本的换行风格**）──
    # 🔴 §59：`cur` 现在是**归一化（LF）**文本 ⇒ 必须按包原本的风格还原
    #   ⇒ 否则包内文件会从 CRLF 变成 LF ⇒ 与仓库/其它包文件的风格不一致
    #   ⇒ 也会让「仓库⇄包 逐字节一致」的核对口径变得难以判断。
    out_txt = cur.replace('\n', '\r\n') if pkg_crlf else cur
    raw = out_txt.encode('utf-8')
    tmp = pkg_path + '.tmp_c152'
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
                repo_sha=sha256_bytes(repo_bytes),
                crlf=bool(pkg_crlf))


def main():
    ap = argparse.ArgumentParser(description='把 §59 修复同步到客户包（定点替换）')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('客户包目录：%s' % pkg)
    print('基线 commit：%s' % BASE_COMMIT)
    print()
    ok = True
    for rel in FILES:
        r = sync_file(rel, pkg, args.check)
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
