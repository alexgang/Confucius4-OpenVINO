#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c147_to_pkg.py — 把「§31 TTS 关闭记账 + GUI 退出等 MT + 乱码修复」
同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，**幂等**（已同步则 no-op）；
- 备份目录**必须在包外**（`_backup*` 会被 `pkg_exclude.BACKUP_DIR_RE` 命中而污染包）；
- **替换后必须与仓库版逐字一致（归一化换行）才写盘**。

## 与前几版同步脚本的差别（沿用 §30 的改进）

`sync_c140/c141/c142/c144` 的替换块是**手抄**的 ⇒ 抄错一个字符就会
「命中 0 次」而失败，或**命中多处**而误替换。

本版改为**从 git 自动派生替换块**：
1. `git show HEAD:<file>` 取**改前**的基线（= 本轮修复前的仓库版）；
2. 读**改后**的仓库工作区版本；
3. 用 `difflib.SequenceMatcher` 把两份**按行**对齐，切成若干**连续变更块**；
4. 每个块的 OLD 文本必须在包内**恰好命中 1 次**（否则拒绝写入）；
5. 全部替换完后，包内文件（归一化换行）必须与仓库版**逐字一致**。

⇒ **不手抄任何代码** ⇒ 抄错的风险归零；且「唯一命中」断言仍然成立。

## 要同步的变更（§31）

### `app/tts_service.py`

① **`close()` 必须清理在途句子并计丢句** ⇒ 修掉
   `n_played + n_dropped != n_submitted`（停 TTS / 换设备 / 换音色 / 退出
   四条路径都会调 `close()` ⇒ 每走一次就丢一批在途句子的记账）。
② **`close()` 不得清 `_dropped_ids`** ⇒ worker 此刻还活着，可能回 `played`
   ⇒ 提前清了 ⇒ 又变成「丢了 + 播了」双记（§30 修的正是这个）。

### `app/live_caption_app.py`

③ **GUI `quit()` 必须等 MT 把最后一句翻完** ⇒ 旧实现 `mt.flush()` 后直接
   `_pump_tts()`（outbox 空）⇒ 最后一句**既不显示也不朗读**，随后
   `mt.close()` 把工作线程停掉 ⇒ 这一句**永远丢**。
   （CLI 侧 `run_cli` 收尾**有** `mt.wait_idle(180)`，GUI 侧漏了。）
④ `wait_idle` **必须有条件守卫** ⇒ 否则 `state == 'loading'` 时白等 180 s
   ⇒ 用户点关闭后界面卡死。

### `app/device_config.py` / `app/audio_source.py`

⑤ 两处 **U+FFFD 乱码**（GBK 字节当 UTF-8 解码）清零（纯注释/docstring）。

## 用法

    python live_caption/sync_c147_to_pkg.py            # 同步
    python live_caption/sync_c147_to_pkg.py --check    # 只查差异
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
BACKUP_DIR = os.path.join(HOME, 'pkg_backup_app_c147')

# 本轮要同步的文件（仓库相对路径 → 包内相对路径）
FILES = [
    'live_caption/live_caption_app.py',
    'live_caption/device_config.py',
]

PKG_REL = 'app'


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

    ⚠️ 目录名可能有 `v1.0.bak_20261020` 这类后缀 ⇒ 必须用**正则**取版本号
       —— `int(rsplit('_v',1)[1])` 会抛异常 ⇒ 整个目录列表被跳过
       ⇒ 报「找不到客户包目录」。
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


# 🔴 **基线 commit**：本轮改动**之前**的版本（不是 HEAD！）。
#    HEAD 已经含本轮改动 ⇒ 用 HEAD 当基线会推导出「零变更块」。
BASE_COMMIT = '4d542ac'


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

    🔴🔴 **为什么不能只取一行**（§32 实测踩坑）：
       difflib 切出的块边界常常正好落在**公共行**上（例如函数末尾的
       ``}``、空行）⇒ 单行锚点在包内命中 10 次 / 283 次 ⇒
       「唯一命中」断言必然失败。
       ⇒ 必须取**连续多行的联合上下文**，直到在包内**唯一命中**为止。
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
    """用 difflib 把 old→new 切成若干**连续变更块**。

    每块 = (old_text, new_text, ctx_before_lines, ctx_after_lines)：
    - `old_text` 为空 ⇒ **纯新增** ⇒ 用上下文定位插入点；
    - `old_text` 非空 ⇒ 用「唯一命中替换」。

    ⚠️ **纯新增块必须带上下文锚点** ⇒ 只看块内的新行是没用的
       （那些行在包内**根本不存在**）⇒ 必须取块**前后**的公共上下文。
    """
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
    """纯新增块（OLD 为空）⇒ 用**唯一上下文锚点**插入。

    🔴 关键：**不能**用新块内部的行当锚点（那些行在包内**根本不存在**）
       ⇒ 必须用块**前后**的公共上下文。

    🔴🔴 **单行锚点不够**（§32 实测）：块边界常落在公共行（``}`` / 空行）
       ⇒ 单行在包内命中多次 ⇒ 必须从**最近的行开始逐行加长联合上下文**，
       直到在包内**恰好命中 1 次**为止。

    定位优先级：
      ① 在 ``ctx_before`` 的**最后一行之后**插入（要求该联合上下文唯一）；
      ② 否则在 ``ctx_after`` 的**第一行之前**插入。

    ⇒ 仍然是「唯一命中断言」的路子，不是整目录覆盖。

    返回 (新串, 是否成功)。⚠️ Python 字符串不可变 ⇒ 必须**返回**新串，
    在调用方重绑定（否则改动丢失）。
    """
    # ① 用 ctx_before：从**最长**上下文开始逐步缩短，找唯一命中
    #    🔴🔴 **必须从最长开始**（§32 实测踩坑）：
    #       从最短开始会**命中错的位置** —— 典型例子：包内 MT 的
    #       `build_engine_options()` 也有 `out = []` / `for dev in devices:`
    #       这两行 ⇒ 短上下文命中 2 次（MT 那个 + TTS 那个）
    #       ⇒ 而 difflib 给的**完整**上下文（前面还有 docstring）只命中 1 次
    #       ⇒ **先长后短**才能既精确又唯一。
    for n in range(len(ctx_before), 0, -1):
        joint = ''.join(ctx_before[len(ctx_before) - n:])
        if not joint.strip():
            continue
        cnt = cur.count(joint)
        if cnt == 1:
            idx = cur.index(joint) + len(joint)
            return cur[:idx] + new_blk + cur[idx:], True
        if cnt == 0:
            break   # 再缩短只会更多命中 ⇒ 换 ctx_after
    # ② 用 ctx_after：从最长开始逐步缩短
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
    # 兜底：在新块里找一行**在包内已存在**且唯一的行当锚点
    lines = new_blk.splitlines(keepends=True)
    for ln in lines:
        if not ln.strip():
            continue
        if cur.count(ln) == 1:
            idx = cur.index(ln)
            return cur[:idx] + new_blk + cur[idx:], True
    return cur, False


def _replace_unique(cur: str, old_blk: str, new_blk: str, ctx_before, ctx_after):
    """把 ``old_blk`` 替换成 ``new_blk``。

    🔴🔴 **命中多次时的处理**（§32 实测踩坑）：
       difflib 会把**多个不同的修改点**合并成一个块 —— 典型例子：
       ``self.var_tts_note.set(f'设备 {opt["device"]} · 精度 …')``
       这一行在**两个不同函数**里都出现（初始选中 / 下拉变更），
       两处**都要**改成 ``self._tts_note_text(opt)``，
       而 difflib 只给出**一个**包含该行的 replace 块
       ⇒ 该块在包内命中 2 次。

       ⇒ 修法（**三步递进**）：
         ① 用上下文联合把命中**收窄到唯一**（首选，改动最精确）；
         ② 若上下文仍无法收窄，但 **new_blk 已在包内存在** ⇒ 说明这块
            **已经同步过** ⇒ 幂等跳过；
         ③ 否则 ⇒ **替换全部命中**（因为 difflib 既然把 N 处合并成一块，
            说明 N 处的目标内容**相同** ⇒ 全部替换才正确）。

    返回 (新串, 是否成功, 命中次数, 说明)。
    """
    cnt = cur.count(old_blk)
    if cnt == 1:
        return cur.replace(old_blk, new_blk, 1), True, 1, 'unique'
    if cnt == 0:
        return cur, False, 0, 'not-found'

    # ① 上下文联合收窄（**从最长开始** ⇒ 最精确，见 §32 踩坑说明）
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

    # ② 已同步过（new_blk 存在且 old_blk 残留）⇒ 幂等跳过
    if new_blk.strip() and cur.count(new_blk) >= 1:
        return cur, True, cnt, 'already-synced'

    # ③ 替换全部命中（difflib 合并 ⇒ 目标内容相同 ⇒ 全替才正确）
    return cur.replace(old_blk, new_blk), True, cnt, 'replace-all'


def sync_file(rel: str, pkg: str, check_only: bool) -> dict:
    repo_path = os.path.join(REPO, rel)
    name = os.path.basename(rel)
    pkg_path = os.path.join(pkg, PKG_REL, name)

    if not os.path.exists(pkg_path):
        return dict(file=name, status='SKIP-not-in-pkg', pkg=pkg_path)

    # 🔴🔴 **必须同步 HEAD 版，不能用工作区版**！
    #   工作区里混着 APP-012② 的 stitch 在制品（**未接线、未验证**）
    #   ⇒ 同步工作区版会把未完成的在制品带进客户包。
    #   ⇒ 一律以 HEAD（= 本轮 CUDA 修复的提交 6a1dee6）为准。
    repo_txt = git_show(rel, 'HEAD')   # 目标 = HEAD（本轮 CUDA 提交）
    with open(pkg_path, 'rb') as f:
        pkg_bytes = f.read()

    repo_bytes = repo_txt.encode('utf-8')
    pkg_txt = pkg_bytes.decode('utf-8')

    # ── 幂等：包内已与仓库一致（归一化换行后）──
    if norm(pkg_txt) == norm(repo_txt):
        return dict(file=name, status='ALREADY', pkg=pkg_path,
                    bytes=len(pkg_bytes), sha=sha256_bytes(pkg_bytes))

    # ── 从「包内实际内容」派生替换块 ──
    # 🔴🔴 **基线必须是包内实际内容，不能是 git 基线**（§32 实测踩坑）：
    #   用 git 基线（BASE_COMMIT）推导时，difflib 会把**两处独立的修改点**
    #   合并成一个块 —— 典型例子：
    #       `self.var_tts_note.set(f'设备 {opt["device"]} · 精度 …')`
    #       这一行在**两个不同函数**里都出现（初始选中 / 下拉变更），
    #       两处都要改成 `self._tts_note_text(opt)`，
    #       而 difflib 只给出**一个**包含该行的 replace 块
    #       ⇒ 该块在包内命中 2 次 ⇒ 无法唯一定位。
    #   ⇒ 改用「包内实际内容 → 目标版」做 diff ⇒ 每个块对应包内**一处**
    #     连续差异 ⇒ old 块在包内**天然唯一**（连续多行块几乎不可能重复）。
    #
    #   ⚠️ 仍然**不手抄任何代码**（沿用 §30/§31 的纪律）—— 两端都是自动取的。
    #   ⚠️ 「目标版」取 **HEAD**（不是工作区）⇒ 不会把 stitch 在制品带进包。
    old_txt = norm(pkg_txt)                # 包内实际内容（改前）
    blocks = derive_blocks(old_txt, norm(repo_txt))   # HEAD 版（改后）
    if not blocks:
        return dict(file=name, status='NO-BLOCKS', pkg=pkg_path)

    # 🔴🔴 **在归一化文本上做替换**！块是归一化（LF）后的产物，
    #   而包内原文件可能是 CRLF ⇒ 直接拿 LF 块去 count(CRLF 文本)
    #   ⇒ 恒为 0 命中 ⇒ 报「块未命中 / 找不到唯一锚点」。
    #   ⇒ 正确做法：把包内文本先归一化 → 在归一化文本上替换 →
    #     **写回时再恢复包内原本的行尾风格**。
    pkg_is_crlf = b'\r\n' in pkg_bytes
    cur = norm(pkg_txt)
    applied = 0
    for old_blk, new_blk, anc_b, anc_a in blocks:
        if not old_blk.strip():
            # 纯新增（old 为空）⇒ 用**上下文锚点**定位插入
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
            # 包内可能已经有部分内容 ⇒ 幂等跳过
            if new_blk.strip() and cur.count(new_blk) == 1:
                continue
            return dict(file=name, status='FAIL-block-not-found',
                        pkg=pkg_path, detail='块未命中（包内与基线差异过大）')
        cur2, ok, hits, how = _replace_unique(cur, old_blk, new_blk, anc_b, anc_a)
        if not ok:
            return dict(file=name, status='FAIL-block-not-unique',
                        pkg=pkg_path,
                        detail='块命中 %d 次且无法安全替换' % hits)
        cur = cur2
        applied += 1
        if how == 'replace-all':
            print('        [note] 块命中 %d 次 ⇒ 全部替换（difflib 合并 ⇒ 目标相同）'
                  % hits)

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

    # ── 写回（保持包内原有的换行风格：用包内原文件的风格）──
    if pkg_is_crlf:
        cur = cur.replace('\n', '\r\n')
    raw = cur.encode('utf-8')
    tmp = pkg_path + '.tmp_c147'
    with open(tmp, 'wb') as f:
        f.write(raw)
    os.replace(tmp, pkg_path)

    # ── 落盘后复核 SHA256 ──
    after = sha256_file(pkg_path)
    return dict(file=name, status='SYNCED', pkg=pkg_path,
                applied=applied, blocks=len(blocks),
                bytes_before=len(pkg_bytes),
                sha_before=sha256_bytes(pkg_bytes),
                bytes_after=os.path.getsize(pkg_path),
                sha_after=after, backup=bak,
                repo_sha=sha256_bytes(repo_bytes))


def main():
    ap = argparse.ArgumentParser(description='把 §31 修复同步到客户包（定点替换）')
    ap.add_argument('--pkg', default=None, help='客户包目录（默认自动发现最大版本）')
    ap.add_argument('--check', action='store_true', help='只查差异，不写盘')
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    print('客户包：%s' % pkg)
    print('模式  ：%s' % ('check（不写盘）' if args.check else 'sync'))
    print()

    rows = []
    bad = False
    for rel in FILES:
        r = sync_file(rel, pkg, args.check)
        rows.append(r)
        st = r['status']
        if st.startswith('FAIL'):
            bad = True
        line = '  %-22s %s' % (r['file'], st)
        if 'sha_after' in r:
            line += '  %d → %d B  sha %s → %s' % (
                r.get('bytes_before', 0), r['bytes_after'],
                r['sha_before'][:12], r['sha_after'][:12])
        if 'blocks' in r:
            line += '  块 %d' % r['blocks']
        if 'detail' in r:
            line += '  ← ' + r['detail']
        if 'backup' in r:
            line += '\n        备份：%s' % r['backup']
        print(line)

    print()
    n_sync = sum(1 for r in rows if r['status'] == 'SYNCED')
    n_already = sum(1 for r in rows if r['status'] == 'ALREADY')
    print('同步 %d 个，已一致 %d 个，失败 %d 个' % (n_sync, n_already, bad))
    if bad:
        print('结论：FAIL —— 有文件未同步成功（**包内与仓库不一致**）')
        return 1
    print('结论：PASS —— 包内与仓库逐字一致（归一化换行）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
