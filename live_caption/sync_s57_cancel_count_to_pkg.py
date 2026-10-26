#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_s57_cancel_count_to_pkg —— §57 修复的**定点同步**脚本。

## 为什么要单独的同步脚本（双副本纪律）

仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
⇒ **禁止整目录覆盖**，只能用「精确字符串替换 + 唯一命中断言」。

## 本次同步的内容（**只有 `cancel()` 的丢句计数闸门**）

§57 修了一个真实缺陷：`TTSService.cancel()` **无条件** `n_dropped += 1`
⇒ 同一个 jid 被 cancel 两次就**双记**
⇒ 真实触发路径 = `OfflineReader.stop()` 与 `_loop()` 的 `finally`
  各调一次 `_cancel_pending()`（锁内快照 + 锁外逐个 cancel ⇒ 快照可重叠）
⇒ 实测 3 句提交却报 `n_dropped=6`。

## 同步方式

- 旧块 / 新块都从**仓库 HEAD 版本**（`git show 8d6bcc1:live_caption/tts_service.py`）
  派生 ⇒ 不手抄代码；
- 对客户包文件做**精确字符串替换** ⇒ 断言命中次数 **== 1**；
- 替换后**归一化换行**比对仓库工作区 ⇒ 必须**逐字节一致**（除行尾风格）；
- 客户包保持自己的行尾风格（不改动客户的换行约定）。

## 纪律

- 不跑推理、不测速、不占 GPU、不取机器锁；
- 不调 MiniMax（质量判定交 reviewer）。
"""
from __future__ import annotations

import difflib
import hashlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REPO_FILE = os.path.join(REPO, 'live_caption', 'tts_service.py')
PKG_FILE = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\app\tts_service.py'

# 修复前的基线（§56 的提交）⇒ 用它派生旧块，避免手抄
BASELINE_COMMIT = '8d6bcc1'


def norm(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_show(rel: str, commit: str) -> str:
    r = subprocess.run(['git', 'show', '%s:%s' % (commit, rel)],
                       cwd=REPO, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=120)
    if r.returncode != 0:
        raise RuntimeError('git show %s:%s 失败：%s' % (commit, rel, r.stderr[-400:]))
    return r.stdout


def main() -> int:
    # ── 1. 取基线（旧）与仓库工作区（新） ───────────────────────────
    old_src = git_show('live_caption/tts_service.py', BASELINE_COMMIT)
    new_src = open(REPO_FILE, 'r', encoding='utf-8', newline='').read()

    # 🔴 **只同步 `cancel()` 这一处** ⇒ 用 difflib 从基线→工作区派生替换块，
    #    并且**只取落在 cancel() 方法体内**的那些 hunk。
    old_lines = old_src.splitlines(keepends=True)
    new_lines = new_src.splitlines(keepends=True)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)

    # 定位基线里 cancel() 的行区间
    def method_span(lines):
        start = None
        for i, ln in enumerate(lines):
            if ln.startswith('    def cancel(self, jid'):
                start = i
                break
        if start is None:
            raise RuntimeError('基线里找不到 cancel()')
        end = len(lines)
        for j in range(start + 1, len(lines)):
            ln = lines[j]
            if ln.strip() and not ln.startswith('        '):
                end = j
                break
        return start, end

    o0, o1 = method_span(old_lines)
    n0, n1 = method_span(new_lines)

    # 提取两个方法的**完整文本**作为替换块
    old_block = ''.join(old_lines[o0:o1])
    new_block = ''.join(new_lines[n0:n1])

    if old_block == new_block:
        print('[skip] 基线与工作区的 cancel() 完全相同 ⇒ 无需同步')
        return 0

    # ── 2. 对客户包做精确字符串替换（唯一命中断言） ─────────────────
    pkg_b = open(PKG_FILE, 'rb').read()
    pkg_text = pkg_b.decode('utf-8')

    # 🔴🔴 行尾：**统一在「归一化为 LF」的文本上做替换**。
    #   旧写法（先取工作区原文再 `\n→\r\n`）会把本就是 CRLF 的块
    #   变成 `\r\r\n` ⇒ 客户包被写坏（本次已实测踩到，已还原）。
    #   ⇒ 现在：`old_block` / `new_block` 都先归一化成 LF，
    #     客户包文本也先归一化成 LF ⇒ 替换在 LF 域完成
    #     ⇒ 最后按**客户包原始行尾风格**写回。
    old_lf = old_block.replace('\r\n', '\n')
    new_lf = new_block.replace('\r\n', '\n')

    pkg_norm = pkg_text.replace('\r\n', '\n')
    cnt = pkg_norm.count(old_lf)
    if cnt != 1:
        print('[FAIL] 客户包旧块命中次数 = %d（必须 == 1）⇒ 拒绝同步' % cnt)
        print('      客户包文件：%s' % PKG_FILE)
        return 2

    pkg_norm_new = pkg_norm.replace(old_lf, new_lf)
    assert pkg_norm_new.count(new_lf) == 1, '替换后新块命中次数异常'

    # ── 3. 写回（**恢复客户包原本的行尾风格**） ─────────────────────
    pkg_crlf = pkg_b.count(b'\r\n') > 0
    out_text = pkg_norm_new.replace('\n', '\r\n') if pkg_crlf else pkg_norm_new
    out_bytes = out_text.encode('utf-8')
    with open(PKG_FILE, 'wb') as f:
        f.write(out_bytes)

    # ── 4. 验证：归一化换行后与仓库工作区**逐字节一致** ─────────────
    repo_b = open(REPO_FILE, 'rb').read()
    pkg_after = open(PKG_FILE, 'rb').read()
    same = norm(repo_b) == norm(pkg_after)
    print('仓库工作区 bytes=%d sha256=%s' % (len(repo_b), sha(norm(repo_b))[:16]))
    print('客户包   bytes=%d sha256=%s' % (len(pkg_after), sha(norm(pkg_after))[:16]))
    print('归一化换行后逐字节一致：%s' % ('YES' if same else 'NO'))
    if not same:
        print('[FAIL] 同步后不一致 ⇒ 已写回但需人工核对')
        return 3

    # ── 5. 差异摘要（确认只改了 cancel()） ──────────────────────────
    d = list(difflib.unified_diff(
        norm(pkg_before_bytes).decode('utf-8').splitlines(),
        norm(pkg_after).decode('utf-8').splitlines(),
        fromfile='pkg(before)', tofile='pkg(after)', lineterm='', n=1))
    changed = [ln for ln in d if ln.startswith('@@') or
               (ln[:1] in '+-' and ln[:3] not in ('+++', '---'))]
    print('客户包差异行数：%d（应只有 cancel() 一处）' % len(changed))
    for ln in changed[:12]:
        print('   ' + ln)
    return 0


if __name__ == '__main__':
    pkg_before_bytes = open(PKG_FILE, 'rb').read()
    sys.exit(main())
