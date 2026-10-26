#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s58_cancel_queue_to_pkg —— §58 修复的**定点同步**脚本。

## 为什么要单独的同步脚本（双副本纪律）

仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
⇒ **禁止整目录覆盖**，只能用「精确字符串替换 + 唯一命中断言」。

## 本次同步的内容（**只有 `cancel()` 的待发队列闸门 + `_queue` 成员跟踪**）

§58 修了一个真实缺陷：`TTSService.cancel()` 只清 `pending` / `_inflight`，
**漏了「待发队列 `_queue`」** ⇒

① **幽灵在途句**：worker 还没 ready 时（模型加载中）`submit()` 把命令放进
   `_queue` ⇒ `cancel()` 没摘掉 ⇒ ready 后 `_flush_queue()` **重新下发**
   ⇒ worker **真的播出来**（用户点了「停止」这句还是被念了）
   ⇒ 主进程这边 `_inflight` 里多了一个**从未在途**的 jid；
② **崩溃时双记**：worker 崩溃时 `_on_worker_exit()` 取 `lost = _inflight`
   ⇒ 幽灵 jid 被当成「在途丢失」⇒ `n_dropped` **再 +1**
   ⇒ 不变式 `n_played + n_dropped + len(pending) == n_submitted` 被破坏
   （实测 sum **4** vs submitted **3**）。

## 同步方式（沿用 §30/§57 的改进，**不手抄代码**）

- 旧块 / 新块都从 **git 自动派生**：
  1. `git show <基线commit>:live_caption/tts_service.py` 取**改前**的基线；
  2. 读**改后**的仓库工作区版本；
  3. `difflib.SequenceMatcher` 把两份**按行**对齐 ⇒ 切成若干**连续变更块**；
  4. 每个块的 OLD 文本必须在客户包里**恰好命中 1 次**（否则拒绝写入）；
  5. 全部替换完后，客户包文件（**归一化换行**）必须与仓库工作区**逐字节一致**；
- 行尾：替换**统一在「归一化为 LF」的文本域**完成
  ⇒ 最后按**客户包原本的行尾风格**写回
  （🔴 §57 踩过的坑：先取原文再 `\n→\r\n` 会把本就是 CRLF 的块变成 `\r\r\n`）。

## 纪律

- 不跑推理、不测速、不占 GPU、不取机器锁；
- 不调 MiniMax（质量判定交 reviewer）。
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REPO_FILE = os.path.join(REPO, 'live_caption', 'tts_service.py')
PKG_DIRS = [
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4',
]

# 修复前的基线（§57 的提交）⇒ 用它派生旧块，避免手抄
BASELINE_COMMIT = 'e06f8ee'


def norm(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_show(rel: str, commit: str) -> str:
    r = subprocess.run(['git', 'show', '%s:%s' % (commit, rel)],
                       cwd=REPO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=120)
    if r.returncode != 0:
        raise RuntimeError('git show %s:%s 失败：%s'
                           % (commit, rel, r.stderr[-400:]))
    return r.stdout


def discover_pkg():
    """自动发现最大版本的客户包目录（不写死版本号）。

    🔴 §29 的教训：版本目录名**可能带后缀**
    （如 `v1.0.bak_20261020`）⇒ 版本号必须用**正则**取，不能用
    `int(rsplit('_v',1)[1])`（会抛异常 ⇒ **整个目录列表被跳过**
    ⇒ 报「找不到客户包目录」）。
    🔴 而且版本号可能是 `v1.5`（**带小数点**）⇒ 正则要允许 `1.5`。
    ⇒ 统一扫主目录，取 `Confucius4_LiveCaption_v*` 里**版本号最大**的。
    """
    home = os.path.dirname(os.path.dirname(PKG_DIRS[0])) if PKG_DIRS else None
    scan_roots = []
    if PKG_DIRS:
        scan_roots.append(os.path.dirname(PKG_DIRS[0]))
    if home:
        scan_roots.append(home)

    cands = []
    for root in set(scan_roots):
        if not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except Exception:
            continue
        for nm in names:
            p = os.path.join(root, nm)
            if not os.path.isdir(p) or not nm.startswith('Confucius4_LiveCaption_v'):
                continue
            m = re.search(r'_v(\d+(?:\.\d+)*)', nm)
            if not m:
                continue
            ver = tuple(int(x) for x in m.group(1).split('.'))
            cands.append((ver, p))
    if not cands:
        return None
    cands.sort(key=lambda t: (t[0], t[1]))
    return cands[-1][1]


def derive_blocks(old_src: str, new_src: str):
    """从基线→工作区派生若干「连续变更块」。

    🔴 §31 的教训：**纯新增块**不能用新块**内部**的行当锚点
    （那些行在客户包里根本不存在）⇒ 必须用块**前后各一行**的公共上下文。
    ⇒ 本函数对每个变更块都取「前 1 行上下文 + 变更行 + 后 1 行上下文」，
      并在 **LF 域**上做替换。
    """
    old_lines = old_src.splitlines(keepends=True)
    new_lines = new_src.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        # 公共上下文：块前 1 行 + 块后 1 行（若存在）
        pre = old_lines[i1 - 1] if i1 > 0 else ''
        post = old_lines[i2] if i2 < len(old_lines) else ''
        old_blk = ''.join(old_lines[i1:i2])
        new_blk = ''.join(new_lines[j1:j2])
        blocks.append(dict(
            old=pre + old_blk + post,
            new=pre + new_blk + post,
            tag=tag, i1=i1, i2=i2,
        ))
    return blocks


def main() -> int:
    pkg_dir = discover_pkg()
    if pkg_dir is None:
        print('[FAIL] 找不到客户包目录')
        return 2
    pkg_file = os.path.join(pkg_dir, 'app', 'tts_service.py')
    if not os.path.isfile(pkg_file):
        print('[FAIL] 客户包里没有 app/tts_service.py：%s' % pkg_file)
        return 2

    old_src = git_show('live_caption/tts_service.py', BASELINE_COMMIT)
    new_src = open(REPO_FILE, 'r', encoding='utf-8', newline='').read()

    pkg_before = open(pkg_file, 'rb').read()
    pkg_norm = pkg_before.decode('utf-8').replace('\r\n', '\n')

    blocks = derive_blocks(old_src, new_src)
    print('派生变更块：%d 个' % len(blocks))

    cur = pkg_norm
    applied = 0
    for i, b in enumerate(blocks):
        old_lf = b['old'].replace('\r\n', '\n')
        new_lf = b['new'].replace('\r\n', '\n')
        if not old_lf.strip():
            # 纯插入且**没有前文上下文**⇒ 无法唯一定位 ⇒ 拒绝（保守）
            print('  [skip] 块 %d 无公共上下文 ⇒ 跳过' % i)
            continue
        cnt = cur.count(old_lf)
        if cnt != 1:
            print('  [FAIL] 块 %d 命中次数 = %d（必须 == 1）⇒ 拒绝写入' % (i, cnt))
            print('         OLD 首行：%r' % old_lf.splitlines()[0][:100])
            return 3
        cur = cur.replace(old_lf, new_lf)
        applied += 1
    print('已应用块：%d / %d' % (applied, len(blocks)))

    # ── 写回（**恢复客户包原本的行尾风格**） ─────────────────────
    pkg_crlf = pkg_before.count(b'\r\n') > 0
    out_text = cur.replace('\n', '\r\n') if pkg_crlf else cur
    with open(pkg_file, 'wb') as f:
        f.write(out_text.encode('utf-8'))

    # ── 验证：归一化换行后与仓库工作区**逐字节一致** ─────────────
    repo_b = open(REPO_FILE, 'rb').read()
    pkg_after = open(pkg_file, 'rb').read()
    same = norm(repo_b) == norm(pkg_after)
    print('仓库工作区 bytes=%d sha256=%s' % (len(repo_b), sha(norm(repo_b))[:16]))
    print('客户包   bytes=%d sha256=%s' % (len(pkg_after), sha(norm(pkg_after))[:16]))
    print('归一化换行后逐字节一致：%s' % ('YES' if same else 'NO'))
    if not same:
        print('[FAIL] 同步后不一致 ⇒ 已写回但需人工核对')
        return 3

    # ── 差异摘要（确认改动范围） ────────────────────────────────
    d = list(difflib.unified_diff(
        norm(pkg_before).decode('utf-8').splitlines(),
        norm(pkg_after).decode('utf-8').splitlines(),
        fromfile='pkg(before)', tofile='pkg(after)', lineterm='', n=1))
    changed = [ln for ln in d if ln.startswith('@@') or
               (ln[:1] in '+-' and ln[:3] not in ('+++', '---'))]
    print('客户包差异行数：%d' % len(changed))
    for ln in changed[:20]:
        print('   ' + ln)
    return 0


if __name__ == '__main__':
    sys.exit(main())
