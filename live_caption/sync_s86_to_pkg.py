# -*- coding: utf-8 -*-
"""sync_s86_to_pkg — §86 的 `tts_engine.py` 改动**定点同步**到客户包 v1.6。

🔴🔴🔴 **仓库 ⇄ 客户包是两份独立副本** ⇒ **禁止整目录覆盖**（纪律铁律）。

## 本轮同步内容（只有一处，极其窄）

`live_caption/tts_engine.py` 的 **L336**：

    -    ⇒ ��审问「**是否真在 NPU 上跑**」⇒ **无法回答**。   ← 2 个 U+FFFD 乱码
    +    ⇒ **审问「是否真在 NPU 上跑」时无法回答**。

🔴 **为什么必须同步**：乱码是**交付质量事故**（§36 已把它进内部素材闸门），
且它**会进客户 zip**（`app/tts_engine.py` 是生产模块）⇒ 客户看到的是乱码文档字符串。

## 方法（沿用 §30/§81 定稿的「不手抄代码」法）

1. 基线 = **HEAD**（`git show HEAD:<rel>`）—— 不是工作区。
2. 候选 = 工作区。
3. `difflib.SequenceMatcher.get_grouped_opcodes(n=3)` **自动派生**替换块。
4. 每块在包内**唯一命中**（`count == 1`）⇒ 否则 FAIL。
5. **幂等**：NEW 已在包里 ⇒ 报 `ALREADY`（不重复写）。
6. 写盘后核对：结果必须与候选**逐字节一致**（LF 归一化后）。
7. **护栏**：包里独有的行（包里有、HEAD 与候选都没有）同步后必须**全部还在**
   ⇒ 否则**拒绝写盘**。
8. 备份写在**包外**（`pkg_backup_app_s86/`）⇒ **不污染客户包**。

## 用法

    <pkg>/python/python.exe live_caption/sync_s86_to_pkg.py
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import sys

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..'))
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s86')
REPORT = os.path.join(REPO, 'results', 'app', 'app126_sync_s86_report.json')

# (包内相对路径, 仓库内相对路径)
TARGETS = [
    (os.path.join('app', 'tts_engine.py'), 'live_caption/tts_engine.py'),
]


def _norm(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\r', '\n')


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def git_show(rel: str) -> str:
    import subprocess
    p = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:' + rel],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError('git show HEAD:%s 失败：%r' % (rel, p.stderr[:200]))
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


def sync_one(pkg_rel: str, repo_rel: str):
    pkg_abs = os.path.join(PKG_ROOT, pkg_rel.replace('/', os.sep))
    repo_abs = os.path.join(REPO, repo_rel.replace('/', os.sep))
    if not os.path.isfile(pkg_abs):
        return dict(file=pkg_rel, status='FAIL', reason='包内文件不存在：%s' % pkg_abs)
    if not os.path.isfile(repo_abs):
        return dict(file=pkg_rel, status='FAIL', reason='仓库文件不存在：%s' % repo_abs)

    with open(pkg_abs, encoding='utf-8', errors='replace', newline='') as f:
        cur = f.read()
    base = git_show(repo_rel)
    with open(repo_abs, encoding='utf-8', errors='replace', newline='') as f:
        cand = f.read()

    cur_n, base_n, cand_n = _norm(cur), _norm(base), _norm(cand)

    if cur_n == cand_n:
        return dict(file=pkg_rel, status='ALREADY',
                    sha_pkg=_sha(cur_n), sha_cand=_sha(cand_n), n_blocks=0)

    blocks = derive_blocks(base_n, cand_n)
    if not blocks:
        return dict(file=pkg_rel, status='FAIL', reason='派生不出替换块')

    out = cur_n
    applied = 0
    for old, new in blocks:
        cnt = out.count(old)
        if cnt == 0:
            # 幂等判定：**NEW 优先**（追加型替换块 OLD ⊂ NEW ⇒ 替换后 OLD 仍在）
            if new and out.count(new) >= 1:
                continue
            return dict(file=pkg_rel, status='FAIL',
                        reason='块在包内 0 命中（且 NEW 也不在）',
                        old_head=old[:80])
        if cnt != 1:
            return dict(file=pkg_rel, status='FAIL',
                        reason='块在包内命中 %d 次（要求恰好 1 次）' % cnt,
                        old_head=old[:80])
        out = out.replace(old, new, 1)
        applied += 1

    if out == cur_n:
        return dict(file=pkg_rel, status='FAIL', reason='替换后无变化')

    # ── 护栏：包内独有的行必须全部还在 ──
    cur_lines = {ln.strip() for ln in cur_n.splitlines() if ln.strip()}
    base_lines = {ln.strip() for ln in base_n.splitlines() if ln.strip()}
    cand_lines = {ln.strip() for ln in cand_n.splitlines() if ln.strip()}
    private = cur_lines - base_lines - cand_lines
    out_lines = {ln.strip() for ln in out.splitlines() if ln.strip()}
    lost = sorted(private - out_lines)
    if lost:
        return dict(file=pkg_rel, status='FAIL',
                    reason='包内私有行丢失 %d 行（拒绝写盘）' % len(lost),
                    lost_sample=lost[:5])

    if out != cand_n:
        return dict(file=pkg_rel, status='FAIL',
                    reason='同步结果与候选不一致（拒绝写盘）')

    # ── 写盘（备份在包外）──
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(pkg_abs, os.path.join(
        BACKUP_DIR, os.path.basename(pkg_abs) + '.before_s86'))

    # 🔴 保持包内原有换行风格（探测原文件是 CRLF 还是 LF）
    use_crlf = '\r\n' in cur
    data = out.replace('\n', '\r\n') if use_crlf else out
    with open(pkg_abs, 'w', encoding='utf-8', newline='') as f:
        f.write(data)

    with open(pkg_abs, encoding='utf-8', errors='replace', newline='') as f:
        after = f.read()
    if _norm(after) != cand_n:
        return dict(file=pkg_rel, status='FAIL',
                    reason='写盘后复核不一致（已写盘，需人工核对）')

    return dict(file=pkg_rel, status='SYNCED', n_blocks=applied,
                sha_pkg=_sha(_norm(after)), sha_cand=_sha(cand_n),
                bytes=len(data), use_crlf=use_crlf)


def main():
    print('=' * 70)
    print('§86 客户包定点同步（tts_engine.py 乱码修复）')
    print('=' * 70)
    results = []
    rc = 0
    for pkg_rel, repo_rel in TARGETS:
        r = sync_one(pkg_rel, repo_rel)
        results.append(r)
        tag = r.get('status')
        print('  [%s] %s' % (tag, pkg_rel))
        if tag == 'FAIL':
            rc = 1
            print('      原因：%s' % r.get('reason'))
            for k in ('old_head', 'lost_sample'):
                if r.get(k):
                    print('      %s: %s' % (k, r[k]))
        else:
            print('      sha_pkg =%s' % str(r.get('sha_pkg'))[:16])
            print('      sha_cand=%s' % str(r.get('sha_cand'))[:16])
            if r.get('bytes'):
                print('      bytes=%d  CRLF=%s' % (r['bytes'], r.get('use_crlf')))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(dict(results=results, rc=rc,
                       pkg_root=PKG_ROOT, backup_dir=BACKUP_DIR),
                  f, ensure_ascii=False, indent=2)
    print()
    print('报告已落盘：%s' % REPORT)
    return rc


if __name__ == '__main__':
    sys.exit(main())
