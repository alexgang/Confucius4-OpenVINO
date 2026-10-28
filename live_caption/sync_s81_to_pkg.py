# -*- coding: utf-8 -*-
"""sync_s81_to_pkg — 把 §81 的两处改动**定点同步**到客户包 v1.6。

🔴🔴🔴 **仓库 ⇄ 客户包是两份独立副本** ⇒ **禁止整目录覆盖** ⇒
本脚本沿用 §30/§31 建立的「`git show HEAD:` + `difflib` 自动派生替换块」法：

1. 基线 = **HEAD**（不是工作区！⇒ 避免把本轮未提交的在制品带进包）
   —— §80.9 已确认「包内 == HEAD」。
2. 候选 = **工作区**（本轮改动）。
3. 用 `difflib` 派生 OLD/NEW 替换块（带上下文 ⇒ 唯一命中）⇒ **不手抄代码**。
4. 每块在包内**唯一命中**（`count == 1`）⇒ 否则 FAIL。
5. **幂等**：NEW 已在包里 ⇒ 报 `ALREADY`，不改。
6. 备份写在**包外**（`pkg_backup_app_s81/`）⇒ 不污染客户包。

⚠️ **纯新增块**（如新增 `if self.jsonl_path:` 两行）不能用新块**内部**的行当锚点
（那些行在包内**根本不存在**）⇒ 必须用块**前后各一行**的公共上下文定位。
⇒ 本脚本用 `difflib.SequenceMatcher.get_grouped_opcodes(n=3)` 取上下文。

## 用法

    <pkg>/python/python.exe live_caption/sync_s81_to_pkg.py
"""
from __future__ import annotations

import difflib
import hashlib
import os
import shutil
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..'))
PKG_ROOT = os.path.join(HOME, 'Confucius4_LiveCaption_v1.6')
PKG_APP = os.path.join(PKG_ROOT, 'app')
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_s81')

# (包内相对路径, 仓库内相对路径)
TARGETS = [
    (os.path.join('app', 'tts_service.py'), 'live_caption/tts_service.py'),
    (os.path.join('app', 'live_caption_app.py'),
     'live_caption/live_caption_app.py'),
    # 🔴🔴🔴 **本轮新增**：`tts_worker.py` 的逐句 jsonl 字段表
    #   （补 `read_delta` / `cb_delta` ⇒ 「出声硬证据」可机器判定）
    (os.path.join('app', 'tts_worker.py'), 'live_caption/tts_worker.py'),
]


def _norm(s: str) -> str:
    """归一化换行（LF）—— 仓库是 LF，包内可能是 CRLF。"""
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
    """🔴 **包内私有行** = 包里有、**HEAD 与候选都没有**的行。

    ⇒ 这些行是**客户包独有**的内容（或本轮已同步、HEAD 里没有的内容），
    ⇒ 同步**绝不能**把它们删掉 ⇒ 用作护栏。
    ⚠️ **判据用「行」而不是「块」**：块级判据会误报
    （`--tts-jsonl` 那段在 HEAD 里没有、候选里有 ⇒ 不会真被删）。
    """
    cl = set(cur.splitlines())
    bl = set(base.splitlines())
    kl = set(cand.splitlines())
    return sorted(ln for ln in (cl - bl - kl) if ln.strip())


def derive_blocks(base: str, cand: str, context: int = 3):
    """从 base → cand 派生替换块列表 [(old, new, anchor_before, anchor_after, tag)]。

    🔴🔴🔴 **踩过的坑（必须保留这个写法）**：
    `get_grouped_opcodes()` 返回的是**一组 opcode**，其中夹着 `equal` 部分。
    若只把**非 equal** 的行拼起来 ⇒ 得到的 `old` 是**不连续**的片段
    ⇒ 在包里**根本不是连续出现** ⇒ `text.count(old) == 0`
    ⇒ 表现为「同步后与候选不一致（拒绝写盘）」。
    ⇒ **正确做法**：取**整组的跨度**（第一个 opcode 的 `i1` 到最后一个的 `i2`）
    ⇒ `old = b[i1:i2]`（含中间的 equal 行）、`new = c[j1:j2]`
    ⇒ 两者都是**连续**的 ⇒ 在包里能逐字命中。
    """
    b = _norm(base).splitlines(keepends=True)
    c = _norm(cand).splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, b, c, autojunk=False)
    out = []
    for grp in sm.get_grouped_opcodes(context):
        # 🔴 **整组跨度**（含中间的 equal 行 ⇒ old/new 都连续）
        i1 = grp[0][1]
        i2 = grp[-1][2]
        j1 = grp[0][3]
        j2 = grp[-1][4]
        old = ''.join(b[i1:i2])
        new = ''.join(c[j1:j2])
        if old == new:
            continue
        # 🔴 **锚点**：块前后各一行的公共上下文（对纯新增块尤其重要）
        anchor_before = b[i1 - 1] if i1 > 0 else ''
        anchor_after = b[i2] if i2 < len(b) else ''
        out.append((old, new, anchor_before, anchor_after, (i1, i2, j1, j2)))
    return out


def derive_fine_blocks(base: str, cand: str, context: int = 3):
    """🔴 **细粒度重试**：把每个 opcode 单独做成一个块（带上下文扩展）。

    🔴🔴🔴 **为什么需要（实测踩到）**：
    「分组跨度」会把**相邻的几处改动合并成一大块**（例如先加 `--tts-jsonl`、
    后加 `--tts-source`，两次改动**挨着** ⇒ 合成一个大块）。
    ⇒ 若包里**已经**应用了其中一处（上一轮同步过）⇒
    **整块**的 `old` 在包里**找不到** ⇒ 直接 FAIL。
    ⇒ **修法**：大块命中失败时 ⇒ **退到 opcode 粒度**逐个替换
    （每个 opcode 的 old/new 本身就是**连续**的 ⇒ 可逐字命中），
    命中不了的再跳过 ⇒ **不覆盖**已应用的部分。

    ⇒ 上下文扩展：opcode 前后各取 `context` 行 base 内容并入 old/new
      ⇒ **保证唯一命中**（比裸 opcode 更不容易撞多处）。
    """
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
        # 🔴 上下文扩展（前后各 context 行）
        pre = b[max(0, i1 - context):i1]
        post = b[i2:i2 + context]
        out.append((''.join(pre) + old + ''.join(post),
                    ''.join(pre) + new + ''.join(post),
                    b[i1 - 1] if i1 > 0 else '',
                    b[i2] if i2 < len(b) else '',
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
                    sha_pkg=_sha(_norm(cur))[:12],
                    sha_cand=_sha(_norm(cand))[:12], n_blocks=0)

    blocks = derive_blocks(base, cand)
    if not blocks:
        return dict(file=pkg_rel, ok=False, why='未能派生替换块')

    text = _norm(cur)
    applied = []
    failed_block = None
    for old, new, ab, aa, tag in blocks:
        # 🔴 幂等：NEW 已在包里 ⇒ 这块已同步
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
        # 🔴 纯新增块：OLD 为空 ⇒ 用「块前一行 + 块后一行」定位
        if not old:
            if ab and text.count(ab) == 1:
                pos = text.index(ab) + len(ab)
                text = text[:pos] + new + text[pos:]
                applied.append(dict(tag=str(tag), status='APPENDED',
                                    new_len=len(new)))
                continue
            return dict(file=pkg_rel, ok=False,
                        why='纯新增块无法唯一定位：%r' % (tag,))
        # 🔴🔴🔴 **大块命中失败** ⇒ 不直接 FAIL ⇒ **退到 opcode 粒度**
        #   （包里可能**已经**应用了其中一部分 ⇒ 整块 old 找不到）
        failed_block = (old, new, tag)
        break

    if failed_block is not None:
        old, new, tag = failed_block
        fine = derive_fine_blocks(base, cand)
        n_applied = 0
        n_skipped = 0
        for fold, fnew, fab, faa, ftag in fine:
            if fnew and fnew in text:
                n_skipped += 1
                continue
            if fold and text.count(fold) == 1:
                text = text.replace(fold, fnew, 1)
                n_applied += 1
                continue
            # 🔴 opcode 粒度也命中不了 ⇒ 说明**包里这段与 base 不同**
            #   （已被别的改动动过）⇒ 记下来，最后靠「与候选逐字节一致」把关
            n_skipped += 1
        applied.append(dict(tag='fine-granularity', status='FINE',
                            applied=n_applied, skipped=n_skipped,
                            orig=str(tag)))

    # 🔴🔴🔴 **兜底：HEAD 基线不适用时 ⇒ 改用「包内现状 → 候选」派生**
    #   **真实踩坑（2026-10-28 08:02）**：同一文件**连续两轮**各加一个
    #   相邻的 CLI 开关（`--tts-jsonl` 已同步、`--tts-source` 未同步）
    #   ⇒ HEAD→候选的**分组跨度**把两处改动**合成一个大块**
    #   ⇒ 该大块的 `old`（含**已应用**的那段）在包里**不存在** ⇒ 命中失败。
    #   ⇒ **改用「包内现状」作基线**派生替换块（这才是"还差什么"的真实定义）。
    #
    #   🔴🔴🔴 **护栏（文件级，替换块级会误报）**：
    #     「包里独有的行」= 包里有、**HEAD 与候选都没有**的行
    #     ⇒ 同步后这些行**必须还在** ⇒ 否则说明同步把客户包私有内容删了
    #     ⇒ **拒绝写盘**。
    #   ⚠️ **不能用「要删的行必须在 HEAD 里」当护栏**（实测误报）：
    #     `--tts-jsonl` 那段在 HEAD 里没有（是本轮新增、已同步进包），
    #     但它在**候选里也有** ⇒ 同步不会删它 ⇒ 不该拦。
    #     ⇒ 护栏的判据必须是「**HEAD 与候选都没有**」⇒ 才是真会被误删的。
    _pkg_only = _pkg_private_lines(_norm(cur), _norm(base), _norm(cand))
    if _norm(text) != _norm(cand):
        cur_blocks = derive_blocks(_norm(cur), _norm(cand))
        ok2 = True
        why2 = None
        n_applied2 = 0
        for old2, new2, ab2, aa2, tag2 in cur_blocks:
            if new2 and new2 in text:
                continue                       # 已同步
            if old2:
                cnt2 = text.count(old2)
                if cnt2 != 1:
                    ok2 = False
                    why2 = '（包内基线）替换块命中 %d 次：%r' % (cnt2, tag2)
                    break
                text = text.replace(old2, new2, 1)
                n_applied2 += 1
                continue
            # 纯新增
            if ab2 and text.count(ab2) == 1:
                pos = text.index(ab2) + len(ab2)
                text = text[:pos] + new2 + text[pos:]
                n_applied2 += 1
                continue
            ok2 = False
            why2 = '（包内基线）纯新增块无法唯一定位：%r' % (tag2,)
            break
        if ok2 and _norm(text) == _norm(cand):
            # 🔴 护栏复核：包内私有行必须**全部还在**
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

    # 🔴 写盘前再核对一遍：结果必须与候选逐字节一致
    if _norm(text) != _norm(cand):
        return dict(file=pkg_rel, ok=False,
                    why='同步后与候选不一致（拒绝写盘）')

    # 备份（包外）
    os.makedirs(BACKUP_DIR, exist_ok=True)
    shutil.copy2(pkg_path, os.path.join(
        BACKUP_DIR, os.path.basename(pkg_path) + '.before_s81'))

    with open(pkg_path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)

    return dict(file=pkg_rel, ok=True, status='SYNCED',
                sha_pkg=_sha(text)[:12], sha_cand=_sha(_norm(cand))[:12],
                n_blocks=len(blocks), applied=applied)


def main():
    print('=' * 72)
    print('sync_s81_to_pkg — §81 定点同步（仓库 ⇄ 客户包 v1.6）')
    print('基线 = HEAD（不是工作区）；方式 = difflib 派生 + 唯一命中')
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
        if r.get('applied'):
            for a in r['applied']:
                print('        - %s %s' % (a['status'], a['tag']))
        if r.get('sha_pkg'):
            print('        sha pkg=%s cand=%s' % (r['sha_pkg'], r['sha_cand']))
    print('\nSUMMARY: %s' % ('全部 OK' if allok else '存在 FAIL'))
    print('备份目录（包外）：%s' % BACKUP_DIR)
    print('ts=%s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
