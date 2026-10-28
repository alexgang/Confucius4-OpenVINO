# -*- coding: utf-8 -*-
"""sync_s89_to_pkg — §89 的 `tts_cuda_sidecar.py` 改动**定点同步**到客户包。

🔴🔴🔴 **仓库 ⇄ 客户包是两份独立副本** ⇒ **禁止整目录覆盖**（纪律铁律）。

## 本轮同步内容（只有一处，极其窄）

`live_caption/tts_cuda_sidecar.py`：**删掉「扣留一块」的 `pending` 缓冲**
⇒ 每块产出来就下发 ⇒ **客户端量到的首包不再被第 2 块挡住**；
同时 `elapsed` 语义修正为「首块时刻」并新增 `total_s`（整句耗时）。

🔴 **为什么必须同步**：`app/tts_cuda_sidecar.py` 是**生产模块**
⇒ 客户机上跑的也是「扣留一块」的旧版 ⇒ 客户实际体验到的首包延迟**依旧存在**。

## 方法（沿用 §30/§81/§86 定稿的「不手抄代码」法）

1. 基线 = **HEAD**（`git show HEAD:<rel>`）—— 不是工作区。
2. 候选 = 工作区。
3. `difflib.SequenceMatcher.get_grouped_opcodes(n=3)` **自动派生**替换块
   （整组跨度 ⇒ old/new 都连续 ⇒ 能在包里逐字命中）。
4. 每块在包内**唯一命中**（`count == 1`）⇒ 否则 FAIL。
5. **幂等**：候选已在包里 ⇒ 报 `ALREADY`（不重复写）。
6. 写盘后核对：结果必须与候选**逐字节一致**（LF 归一化后）。
7. **护栏**：包里独有的行（包里有、基线与候选都没有）同步后必须**全部还在**
   ⇒ 否则**拒绝写盘**。
8. 备份写在**包外**（`pkg_backup_app_s89/`）⇒ **不污染客户包**。
9. **版本号不写死** ⇒ 走 `pkg_paths.pkg_app_dir()`（单一数据源）。

## 用法

    <py> live_caption/sync_s89_to_pkg.py [--dry-run]
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

HOME = r'C:\Users\Trekker-PTL'
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s89')
REPORT = os.path.join(REPO, 'results', 'app', 'app129_sync_s89_report.json')

#: 🔴 客户包单一数据源（**不写死版本号**）
import pkg_paths  # noqa: E402

PKG_ROOT = pkg_paths.discover_pkg_dir()
PKG_APP = pkg_paths.pkg_app_dir()

# (包内相对路径, 仓库内相对路径)
TARGETS = [
    (os.path.join('app', 'tts_cuda_sidecar.py'),
     'live_caption/tts_cuda_sidecar.py'),
]


def _norm(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\r', '\n')


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def git_show(rel: str) -> str:
    p = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:' + rel],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('git show HEAD:%s 失败：%r'
                           % (rel, p.stderr[:200]))
    return p.stdout.decode('utf-8', 'replace')


def derive_blocks(base: str, cand: str, context: int = 3):
    """🔴 **整组跨度**（含中间 equal 行）⇒ old/new 都连续 ⇒ 能在包里逐字命中。"""
    b = _norm(base).splitlines(keepends=True)
    c = _norm(cand).splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, b, c, autojunk=False)
    out = []
    for grp in sm.get_grouped_opcodes(context):
        i1, i2 = grp[0][1], grp[-1][2]
        j1, j2 = grp[0][3], grp[-1][4]
        old = ''.join(b[i1:i2])
        new = ''.join(c[j1:j2])
        if old == new:
            continue
        out.append((old, new))
    return out


def sync_one(pkg_rel: str, repo_rel: str, dry_run: bool = False):
    pkg_abs = os.path.join(PKG_ROOT, pkg_rel.replace('/', os.sep))
    repo_abs = os.path.join(REPO, repo_rel.replace('/', os.sep))
    rec = dict(file=pkg_rel, repo_rel=repo_rel,
               pkg_abs=pkg_abs, repo_abs=repo_abs)
    if not os.path.isfile(pkg_abs):
        rec.update(status='FAIL', reason='包内文件不存在：%s' % pkg_abs)
        return rec
    if not os.path.isfile(repo_abs):
        rec.update(status='FAIL', reason='仓库文件不存在：%s' % repo_abs)
        return rec

    with open(pkg_abs, encoding='utf-8', errors='replace', newline='') as f:
        cur = f.read()
    base = git_show(repo_rel)
    with open(repo_abs, encoding='utf-8', errors='replace', newline='') as f:
        cand = f.read()

    cur_n, base_n, cand_n = _norm(cur), _norm(base), _norm(cand)
    rec['sha_pkg_before'] = _sha(cur_n)
    rec['sha_base_head'] = _sha(base_n)
    rec['sha_cand'] = _sha(cand_n)
    rec['bytes_pkg_before'] = len(cur.encode('utf-8'))
    rec['mtime_pkg_before'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                            time.localtime(os.path.getmtime(pkg_abs)))
    rec['pkg_equals_head'] = (cur_n == base_n)

    if cur_n == cand_n:
        rec.update(status='ALREADY', n_blocks=0,
                   note='包内已是候选 ⇒ 幂等，不重复写')
        return rec

    # 🔴 包内既不是 HEAD 也不是候选 ⇒ **基线不匹配** ⇒ 停下来人工看
    if cur_n != base_n:
        rec.update(status='FAIL',
                   reason='包内既不等于 HEAD 基线也不等于候选 ⇒ 基线不匹配，'
                          '拒绝自动同步（需人工核对）')
        return rec

    blocks = derive_blocks(base_n, cand_n)
    rec['n_blocks_derived'] = len(blocks)
    if not blocks:
        rec.update(status='FAIL', reason='派生不出替换块')
        return rec

    out = cur_n
    applied = 0
    for old, new in blocks:
        cnt = out.count(old)
        if cnt == 0:
            if new and out.count(new) >= 1:
                continue
            rec.update(status='FAIL',
                       reason='块在包内 0 命中（且 NEW 也不在）',
                       old_head=old[:120])
            return rec
        if cnt != 1:
            rec.update(status='FAIL',
                       reason='块在包内命中 %d 次（要求恰好 1 次）' % cnt,
                       old_head=old[:120])
            return rec
        out = out.replace(old, new, 1)
        applied += 1
    rec['n_blocks'] = applied

    if out == cur_n:
        rec.update(status='FAIL', reason='替换后无变化')
        return rec

    # ── 护栏：包内独有的行必须全部还在 ──
    cur_lines = {ln.strip() for ln in cur_n.splitlines() if ln.strip()}
    base_lines = {ln.strip() for ln in base_n.splitlines() if ln.strip()}
    cand_lines = {ln.strip() for ln in cand_n.splitlines() if ln.strip()}
    private = cur_lines - base_lines - cand_lines
    out_lines = {ln.strip() for ln in out.splitlines() if ln.strip()}
    lost = sorted(private - out_lines)
    if lost:
        rec.update(status='FAIL',
                   reason='包内私有行丢失 %d 行（拒绝写盘）' % len(lost),
                   lost_sample=lost[:5])
        return rec

    if out != cand_n:
        rec.update(status='FAIL',
                   reason='同步结果与候选不一致（拒绝写盘）')
        return rec

    if dry_run:
        rec.update(status='DRYRUN', note='dry-run：未写盘')
        return rec

    # ── 写盘（备份在包外）──
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(pkg_abs, os.path.join(
        BACKUP_DIR, os.path.basename(pkg_abs) + '.before_s89'))

    # 🔴 保持包内原有换行风格（探测原文件是 CRLF 还是 LF）
    use_crlf = '\r\n' in cur
    data = out.replace('\n', '\r\n') if use_crlf else out
    with open(pkg_abs, 'w', encoding='utf-8', newline='') as f:
        f.write(data)

    with open(pkg_abs, encoding='utf-8', errors='replace', newline='') as f:
        after = f.read()
    rec['bytes_after'] = len(data)
    rec['use_crlf'] = use_crlf
    rec['sha_pkg_after'] = _sha(_norm(after))
    rec['mtime_pkg_after'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                           time.localtime(os.path.getmtime(pkg_abs)))
    rec['verify_identical'] = (_norm(after) == cand_n)
    if not rec['verify_identical']:
        rec.update(status='FAIL',
                   reason='写盘后复核不一致（已写盘，需人工核对）')
        return rec

    rec.update(status='SYNCED')
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true',
                    help='只派生与校验，不写盘')
    args = ap.parse_args()

    print('=' * 74)
    print('§89 客户包定点同步（tts_cuda_sidecar.py：删「扣留一块」⇒ 首包不再被挡）')
    print('=' * 74)
    print('  客户包根 = %s' % PKG_ROOT)
    print('  客户包app= %s' % PKG_APP)
    print('  备份目录 = %s' % BACKUP_DIR)
    print('  dry_run  = %s' % args.dry_run)
    print('')

    results = []
    rc = 0
    for pkg_rel, repo_rel in TARGETS:
        r = sync_one(pkg_rel, repo_rel, dry_run=args.dry_run)
        results.append(r)
        print('  [%s] %s' % (r.get('status'), pkg_rel))
        print('      sha_before=%s' % str(r.get('sha_pkg_before'))[:16])
        print('      sha_base  =%s' % str(r.get('sha_base_head'))[:16])
        print('      sha_cand  =%s' % str(r.get('sha_cand'))[:16])
        if r.get('n_blocks') is not None:
            print('      blocks    =%s' % r.get('n_blocks'))
        if r.get('sha_pkg_after'):
            print('      sha_after =%s' % str(r['sha_pkg_after'])[:16])
        if r.get('status') == 'FAIL':
            rc = 1
            print('      原因：%s' % r.get('reason'))
            for k in ('old_head', 'lost_sample'):
                if r.get(k):
                    print('      %s: %s' % (k, r[k]))
    print('')
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(dict(results=results, rc=rc, pkg_root=PKG_ROOT,
                       pkg_app=PKG_APP, backup_dir=BACKUP_DIR,
                       dry_run=bool(args.dry_run),
                       ts=time.strftime('%Y-%m-%d %H:%M:%S')),
                  f, ensure_ascii=False, indent=2)
    print('报告已落盘：%s' % REPORT)
    return rc


if __name__ == '__main__':
    sys.exit(main())
