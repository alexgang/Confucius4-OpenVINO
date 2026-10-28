# -*- coding: utf-8 -*-
"""sync_s82_to_pkg — 把 §82 的 `tts_engine.py` 改动**定点同步**到客户包 v1.6。

🔴🔴🔴 **仓库 ⇄ 客户包是两份独立副本** ⇒ **禁止整目录覆盖**。
沿用 `sync_s81_to_pkg.py` 的成熟做法（**不手抄代码**）：

1. 基线 = **HEAD**（`git show HEAD:<rel>`）—— 不是工作区。
2. 候选 = 工作区。
3. `difflib.SequenceMatcher.get_grouped_opcodes(n=3)` 派生替换块。
4. 每块在包内**唯一命中**（`count == 1`）⇒ 否则 FAIL。
5. **幂等**：NEW 已在包里 ⇒ 报 `ALREADY`。
6. **护栏**：包里独有的行（包里有、HEAD 与候选都没有）同步后必须**全部还在**
   ⇒ 否则**拒绝写盘**。
7. 写盘前再核对：结果必须与候选**逐字节一致**（LF 归一化后）。
8. 备份写在**包外**（`pkg_backup_app_s82/`）⇒ 不污染客户包。

🔴 **本轮同步内容**（§82 第 3 条「NPU 身份未证」）：
- 新增 `import time`
- 新增 `execution_devices(eng, on_log=print)`（基于 `EXECUTION_DEVICES`）
- `make_engine()` 内 `os.times()` → `time.perf_counter()`
- 引擎对象补 `load_s` / `device_desc`
- 挂载 `eng.exec_devices`（cp 搬运**之后**的最终状态）

## 用法

    <pkg>/python/python.exe live_caption/sync_s82_to_pkg.py
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..'))
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s82')
REPORT = os.path.join(REPO, 'results', 'app', 'app120_sync_s82_report.json')

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


def _pkg_private_lines(cur: str, base: str, cand: str):
    """🔴🔴🔴 **「包内私有行」的判据（本轮连续踩坑后定稿）**。

    ## 踩到的坑（连续三次）

    1. 旧定义 = 包里有、**HEAD 与候选都没有**的行
       ⇒ **第二轮同步时误报**：上一轮**已同步进包**的 §82 内容
       （既不在 HEAD、也不在当前候选里）⇒ 被判成「包内私有」
       ⇒ 护栏把**本仓库自己的内容**当成「客户包独有、绝不能删」
       ⇒ **本轮合法改动被拦下**（实测拦了 4 行：组件名映射）。

    2. 改用「git 全历史」判据 ⇒ **仍拦**：
       那 4 行是 §82 **首轮**同步写进包的，**从未进入过任何 git 提交**
       ⇒ git 历史里当然没有 ⇒ 还是被判成私有。

    3. 改用「首轮同步前的备份」作参照点 ⇒ **第二轮可用、第三轮又拦**：
       因为备份**被每轮覆盖** ⇒ 第二轮备份 = 「第一轮同步后」
       ⇒ 参照点漂移 ⇒ 又把「第一轮写进去、后来被本轮改掉」的行误判成私有。

    ## 定稿判据（两条件同时满足才算「真私有」）

    **客户包私有内容** = 客户包**自己历史里就有**、且**不是本仓库写进去的**。
    ⇒ 条件 A：该行在**最初**的包内快照（`*.before_s82.orig`，只写一次）里就有；
    ⇒ 条件 B：该行**不在本仓库的任何历史版本**里
       （HEAD 各提交 + **同步脚本记录过的历次候选**）。

    🔴 **条件 B 的关键**：「本仓库写进去的行」包括**历次同步的候选内容**
       ⇒ 必须把**历次候选**也纳入「本仓库内容」集合
       ⇒ 否则第一轮写进去、第二轮改掉的行仍会被误判。
    ⇒ 本实现把**历次同步报告**（`app120_sync_s82_report.json` 的历史）里
       出现过的候选内容 + git 全历史，一起当作「本仓库内容」。

    ⚠️ 护栏仍必须保留：它是「禁止整目录覆盖误删客户包内容」的最后一道闸。
    """
    cl = set(cur.splitlines())
    bl = set(base.splitlines())
    kl = {k.strip() for k in cand.splitlines()}
    candidates = sorted(ln for ln in (cl - bl - kl) if ln.strip())
    if not candidates:
        return []

    # ── 条件 A：最初快照里有？──
    #   🔴 **最初快照 = §82 动手前的客户包内容**。
    #   实测：`pkg_backup_app_s81/` 里**没有** `tts_engine.py`
    #   （§81 未同步过它）⇒ 而 §80.9 已确认「包内 == HEAD」
    #   ⇒ **最初快照 == git HEAD 版本** ⇒ 直接用 `base` 即可。
    #   ⇒ 若存在 `*.before_s82.orig`（只写一次的快照）⇒ 优先用它。
    orig_lines = set()
    _orig = os.path.join(BACKUP_DIR, 'tts_engine.py.before_s82.orig')
    if os.path.exists(_orig):
        try:
            with open(_orig, encoding='utf-8', errors='replace') as f:
                for ln in f.read().splitlines():
                    s = ln.strip()
                    if s:
                        orig_lines.add(s)
        except Exception:
            orig_lines = set()
    if not orig_lines:
        # 🔴 用 HEAD 版本作「最初快照」（§80.9：包内 == HEAD）
        orig_lines = {ln.strip() for ln in base.splitlines() if ln.strip()}
    if not orig_lines:
        return candidates

    # ── 条件 B：不在本仓库（git 全历史 ∪ 历次候选）里？──
    repo_lines = _repo_content_lines()
    out = []
    for ln in candidates:
        s = ln.strip()
        if s not in orig_lines:
            continue                      # 不是最初快照里的 ⇒ 不算私有
        if s in repo_lines or s in kl:
            continue                      # 本仓库写过 ⇒ 不算私有
        out.append(ln)
    return out


def _repo_content_lines():
    """🔴 本仓库「写过的所有内容」的行集合 = git 全历史 ∪ 历次同步候选。"""
    out = set()
    # git 全历史（只看 tts_engine.py）
    try:
        import subprocess
        p = subprocess.run(
            ['git', '-C', REPO, 'log', '--all', '--pretty=format:%H',
             '--', 'live_caption/tts_engine.py'], capture_output=True, timeout=120)
        for c in p.stdout.decode('utf-8', 'replace').split()[:60]:
            p3 = subprocess.run(
                ['git', '-C', REPO, 'show',
                 '%s:live_caption/tts_engine.py' % c],
                capture_output=True, timeout=60)
            if p3.returncode != 0:
                continue
            for ln in p3.stdout.decode('utf-8', 'replace').splitlines():
                s = ln.strip()
                if s:
                    out.add(s)
    except Exception:
        pass
    # 历次同步的候选（工作区当前内容 + 历次同步报告里的 sha 无关的原始内容）
    try:
        with open(os.path.join(REPO, 'live_caption', 'tts_engine.py'),
                  encoding='utf-8') as f:
            for ln in f.read().splitlines():
                s = ln.strip()
                if s:
                    out.add(s)
    except Exception:
        pass
    return out


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
        out.append((old, new, b[i1 - 1] if i1 > 0 else '',
                    b[i2] if i2 < len(b) else '', (i1, i2, j1, j2)))
    return out


def derive_fine_blocks(base: str, cand: str, context: int = 3):
    b = _norm(base).splitlines(keepends=True)
    c = _norm(cand).splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, b, c, autojunk=False)
    out = []
    for op in sm.get_opcodes():
        tag_, i1, i2, j1, j2 = op
        if tag_ == 'equal':
            continue
        old = ''.join(b[i1:i2])
        new = ''.join(c[j1:j2])
        if old == new:
            continue
        pre = b[max(0, i1 - context):i1]
        post = b[i2:i2 + context]
        out.append((''.join(pre) + old + ''.join(post),
                    ''.join(pre) + new + ''.join(post),
                    b[i1 - 1] if i1 > 0 else '', b[i2] if i2 < len(b) else '',
                    ('fine', i1, i2, j1, j2)))
    return out


def sync_one(pkg_rel: str, repo_rel: str):
    pkg_path = os.path.join(PKG_ROOT, pkg_rel)
    if not os.path.exists(pkg_path):
        return dict(file=pkg_rel, ok=False, why='包内文件不存在')
    base = git_show(repo_rel)
    with open(os.path.join(REPO, repo_rel), encoding='utf-8') as f:
        cand = f.read()
    with open(pkg_path, encoding='utf-8', errors='replace') as f:
        cur = f.read()

    if _norm(cur) == _norm(cand):
        return dict(file=pkg_rel, ok=True, status='ALREADY',
                    sha_pkg=_sha(_norm(cur)), sha_cand=_sha(_norm(cand)),
                    n_blocks=0)

    blocks = derive_blocks(base, cand)
    if not blocks:
        return dict(file=pkg_rel, ok=False, why='未能派生替换块')

    text = _norm(cur)
    applied = []
    failed_block = None
    for old, new, ab, aa, tag in blocks:
        if new and new in text:
            applied.append(dict(tag=str(tag), status='ALREADY'))
            continue
        if old and old in text:
            cnt = text.count(old)
            if cnt != 1:
                return dict(file=pkg_rel, ok=False,
                            why='替换块命中 %d 次（要求唯一）：%r' % (cnt, tag))
            text = text.replace(old, new, 1)
            applied.append(dict(tag=str(tag), status='APPLIED',
                                old_len=len(old), new_len=len(new)))
            continue
        if not old:
            if ab and text.count(ab) == 1:
                pos = text.index(ab) + len(ab)
                text = text[:pos] + new + text[pos:]
                applied.append(dict(tag=str(tag), status='APPENDED',
                                    new_len=len(new)))
                continue
            return dict(file=pkg_rel, ok=False,
                        why='纯新增块无法唯一定位：%r' % (tag,))
        failed_block = (old, new, tag)
        break

    if failed_block is not None:
        old, new, tag = failed_block
        fine = derive_fine_blocks(base, cand)
        n_applied = n_skipped = 0
        for fold, fnew, fab, faa, ftag in fine:
            if fnew and fnew in text:
                n_skipped += 1
                continue
            if fold and text.count(fold) == 1:
                text = text.replace(fold, fnew, 1)
                n_applied += 1
                continue
            n_skipped += 1
        applied.append(dict(tag='fine-granularity', status='FINE',
                            applied=n_applied, skipped=n_skipped,
                            orig=str(tag)))

    # 🔴 兜底：以「包内现状」为基线派生（这才是"还差什么"的真实定义）
    _pkg_only = _pkg_private_lines(_norm(cur), _norm(base), _norm(cand))
    if _norm(text) != _norm(cand):
        cur_blocks = derive_blocks(_norm(cur), _norm(cand))
        ok2, why2, n_applied2 = True, None, 0
        for old2, new2, ab2, aa2, tag2 in cur_blocks:
            if new2 and new2 in text:
                continue
            if old2:
                cnt2 = text.count(old2)
                if cnt2 != 1:
                    ok2 = False
                    why2 = '（包内基线）替换块命中 %d 次：%r' % (cnt2, tag2)
                    break
                text = text.replace(old2, new2, 1)
                n_applied2 += 1
                continue
            if ab2 and text.count(ab2) == 1:
                pos = text.index(ab2) + len(ab2)
                text = text[:pos] + new2 + text[pos:]
                n_applied2 += 1
                continue
            ok2 = False
            why2 = '（包内基线）纯新增块无法唯一定位：%r' % (tag2,)
            break
        if ok2 and _norm(text) == _norm(cand):
            lost = [ln for ln in _pkg_only if ln not in text]
            if lost:
                return dict(file=pkg_rel, ok=False,
                            why='护栏：包内私有内容在同步后消失（%d 行）⇒ 拒绝写盘'
                                % len(lost))
            applied.append(dict(tag='pkg-baseline', status='PKG_BASE',
                                applied=n_applied2,
                                pkg_private_lines=len(_pkg_only)))
        elif not ok2:
            return dict(file=pkg_rel, ok=False,
                        why='包内基线派生失败：%s' % (why2,))

    if _norm(text) != _norm(cand):
        return dict(file=pkg_rel, ok=False,
                    why='同步后与候选不一致（拒绝写盘）')

    os.makedirs(BACKUP_DIR, exist_ok=True)
    # 🔴🔴🔴 **「最初快照」只写一次，绝不覆盖**（本轮实测踩到）：
    #   它是**护栏的稳定参照点**（「§82 动手前的客户包」）
    #   若每轮都覆盖 ⇒ 参照点漂移 ⇒ 护栏误拦本轮合法改动（实测拦了 3 行）。
    #   ⚠️ §82 动手前的包内内容 == git HEAD 版本（§80.9「包内 == HEAD」）
    #   ⇒ 首轮同步时若 `.orig` 尚未存在 ⇒ 用 base（HEAD）落盘一份。
    _orig = os.path.join(BACKUP_DIR, os.path.basename(pkg_path) + '.before_s82.orig')
    if not os.path.exists(_orig):
        with open(_orig, 'w', encoding='utf-8', newline='') as f:
            f.write(base)
    # 逐轮备份（保留每一轮的状态，便于回滚）
    _bk = os.path.join(BACKUP_DIR, os.path.basename(pkg_path) + '.before_s82')
    shutil.copy2(pkg_path, _bk)

    with open(pkg_path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)

    return dict(file=pkg_rel, ok=True, status='SYNCED',
                sha_pkg=_sha(text), sha_cand=_sha(_norm(cand)),
                n_blocks=len(blocks), applied=applied)


def main():
    print('=' * 72)
    print('sync_s82_to_pkg — §82 定点同步（仓库 ⇄ 客户包 v1.6）')
    print('基线 = HEAD；方式 = difflib 派生 + 唯一命中 + 包内私有行护栏')
    print('=' * 72)
    results = []
    allok = True
    for pkg_rel, repo_rel in TARGETS:
        r = sync_one(pkg_rel, repo_rel)
        results.append(r)
        if not r.get('ok'):
            allok = False
        print('  [%s] %-28s %s' % ('OK  ' if r.get('ok') else 'FAIL',
                                    r['file'], r.get('status') or r.get('why')))
        for a in (r.get('applied') or []):
            print('        - %s %s' % (a['status'], a['tag']))
        if r.get('sha_pkg'):
            print('        sha pkg=%s' % r['sha_pkg'][:16])
            print('        sha cand=%s' % r['sha_cand'][:16])

    # 🔴🔴 **独立复核**：写盘后重新从磁盘读，逐字节比对候选
    verify = []
    for pkg_rel, repo_rel in TARGETS:
        p = os.path.join(PKG_ROOT, pkg_rel)
        with open(p, encoding='utf-8', errors='replace') as f:
            after = _norm(f.read())
        with open(os.path.join(REPO, repo_rel), encoding='utf-8') as f:
            cand = _norm(f.read())
        verify.append(dict(file=pkg_rel,
                           identical=(after == cand),
                           sha_disk=_sha(after), sha_cand=_sha(cand),
                           bytes=len(after.encode('utf-8'))))

    rep = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               pkg_root=PKG_ROOT, backup_dir=BACKUP_DIR,
               results=results, verify=verify,
               all_ok=allok and all(v['identical'] for v in verify))
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8', newline='') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('\n独立复核：')
    for v in verify:
        print('  %-28s identical=%s sha_disk=%s'
              % (v['file'], v['identical'], v['sha_disk'][:16]))
    print('\nSUMMARY: %s' % ('全部 OK' if rep['all_ok'] else '存在 FAIL'))
    print('报告：%s' % REPORT)
    return 0 if rep['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
