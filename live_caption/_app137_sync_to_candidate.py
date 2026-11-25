#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_sync_to_candidate.py — **把 dev 树的 APP-137 改动定点同步进 v1.2 候选目录**。

## 为什么需要这一步

候选目录是从 **v2.6 客户包**裁出来的 ⇒ 它的 `app/package_profile.py` 是
**v2.6 的旧版**（`allow_clone_voice` 对 minimvp 硬编码 False）。
而 APP-137 §1 的改造在 **dev 树**里 ⇒ 候选目录必须拿到新版，
否则「MiniMVP 里克隆可用」在候选目录里**不成立**。

## 🔴 纪律（与 `_app120_sync_v25.py` 同一套）
* 仓库 `live_caption/` 与客户包是**两份独立副本** ⇒ **禁止整目录覆盖**；
* 只做「**精确字符串替换 + 唯一命中断言**」：
  ① 断言目标文件 == 写前备份（前提唯一）；
  ② 用 `difflib` **自动导出**改写块（**不手抄字符串**）；
  ③ 每块在目标文本里**唯一命中**才替换（0 次或 >1 次 ⇒ fail-closed）；
  ④ 写盘后断言**目标文件与 dev 树文件逐字节相同**；
  ⑤ 写前**还原式复核**（把目标文本反推回原件应逐字相同）⇒ 通过才落盘；
* 落盘用**临时文件 + `os.replace`**（原子）。

## 用法
```
python live_caption/_app137_sync_to_candidate.py --dry-run
python live_caption/_app137_sync_to_candidate.py --apply
```
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)

DEV = HERE
CAND = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.candidate', 'app')
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app137_sync_to_candidate.json')

#: 本轮要同步的文件（dev 树文件名 == 包内 app/ 文件名）
FILES = [
    'package_profile.py',
]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def hunks(old: str, new: str, context: int = 3):
    """用 `difflib` 从 (原件 → 新 dev 文件) **自动导出**改写块。

    🔴 **纯插入块（old 为空串）必须带上上下文**才能唯一命中
       （空串在文本里「命中 N 次」⇒ 永远不是唯一）⇒
       每块都带上**前 context 行**做锚点 ⇒ 锚点整块**唯一命中**才替换。
    """
    o_lines = old.splitlines(True)
    n_lines = new.splitlines(True)
    out = []
    sm = difflib.SequenceMatcher(a=o_lines, b=n_lines)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        # 前置锚点（原文侧）—— 只用**锚点**做唯一性判定，
        # 替换时用「锚点 + 改写部分」整体替换（保证位置正确）。
        a1 = max(0, i1 - context)
        anchor = ''.join(o_lines[a1:i1])
        changed_old = ''.join(o_lines[i1:i2])
        changed_new = ''.join(n_lines[j1:j2])
        out.append({
            'tag': tag,
            'anchor': anchor,
            'old': changed_old,
            'new': changed_new,
            # 实际替换用的整块（锚点 + 改写）
            'old_block': anchor + changed_old,
            'new_block': anchor + changed_new,
            # 🔴 **位置信息**：还原式复核用**行号**定位（不靠字符串搜索
            #    ⇒ 锚点重叠也不会误替换）
            'i1': i1, 'i2': i2, 'j1': j1, 'j2': j2,
        })
    return out


def reverse_by_position(new_text: str, old_text: str, hs) -> str:
    """🔴 **按行号**把新文本反推回旧文本（不靠字符串搜索 ⇒ 锚点重叠也安全）。

    做法：对每个改写块，新文本的 `[j1:j2]` 行**就是**旧文本的 `[i1:i2]` 行
    ⇒ 把它们换回去即可；**equal** 段原样保留。
    """
    n_lines = new_text.splitlines(True)
    o_lines = old_text.splitlines(True)
    segs = sorted([(h['j1'], h['j2'], h['i1'], h['i2']) for h in hs],
                   key=lambda x: x[0])
    out = []
    prev = 0
    for j1, j2, i1, i2 in segs:
        out.extend(n_lines[prev:j1])
        out.extend(o_lines[i1:i2])
        prev = j2
    out.extend(n_lines[prev:])
    return ''.join(out)


def content_matches(new_text: str, hs) -> tuple:
    """🔴 **内容级**校验：改写后文本的每个 `[j1:j2]` 段**必须逐字等于**该块的新内容。

    ## 为什么必须有这一条（不能只有「按行号反推」）

    「按行号反推」**恒为真**（它只是把 `[j1:j2]` 换回 `[i1:i2]` ⇒ 不管段内容
    被改成什么都能还原）⇒ **没有鉴别力**。

    ⇒ 这一条**逐字比内容** ⇒ 内容被篡改就 FAIL ⇒ 判据才真的承重。

    Returns
    -------
    (ok: bool, detail: str)
    """
    n_lines = new_text.splitlines(True)
    for h in hs:
        got = ''.join(n_lines[h['j1']:h['j2']])
        if got != h['new']:
            return False, ('块[%s] 内容不等：期望 %d B / 实测 %d B'
                           % (h['tag'], len(h['new']), len(got)))
    return True, '%d 块内容逐字相等' % len(hs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--candidate', default=CAND)
    args = ap.parse_args()
    cand = args.candidate

    if not os.path.isdir(cand):
        print('FAIL: 候选目录不存在 %s' % cand)
        return 2

    plan = []
    for fn in FILES:
        devp = os.path.join(DEV, fn)
        candp = os.path.join(cand, fn)
        if not os.path.isfile(devp):
            print('FAIL: dev 树缺文件 %s' % devp)
            return 2
        if not os.path.isfile(candp):
            print('FAIL: 候选目录缺文件 %s' % candp)
            return 2
        with open(devp, 'rb') as f:
            dev_b = f.read()
        with open(candp, 'rb') as f:
            cand_b = f.read()
        if dev_b == cand_b:
            print('  %-24s 已经一致 ⇒ 跳过' % fn)
            continue
        old_text = cand_b.decode('utf-8')
        new_text = dev_b.decode('utf-8')
        hs = hunks(old_text, new_text)
        print('  %-24s %d 个改写块' % (fn, len(hs)))
        plan.append((fn, devp, candp, cand_b, dev_b, old_text, new_text, hs))

    # ── 写前：在**内存**上跑真不变量 ────────────────────────────────
    checks = []
    prepared = []
    for fn, devp, candp, cand_b, dev_b, old_text, new_text, hs in plan:
        work = old_text
        applied = []
        ok = True
        # 🔴 **先验唯一性**（全部在**原件**上验）⇒ 顺序替换不会互相干扰；
        #    再按**从后往前**的顺序替换（前面的替换不会影响后面的锚点）。
        for h in hs:
            cnt = old_text.count(h['old_block'])
            if cnt != 1:
                checks.append({'name': 'unique_hit_%s[%s]' % (fn, h['tag']),
                               'ok': False,
                               'detail': '命中 %d 次（要求恰好 1 次）' % cnt})
                ok = False
                break
        if not ok:
            continue
        checks.append({'name': 'unique_hits_%s' % fn, 'ok': True,
                       'detail': '%d 块全部在原件上唯一命中' % len(hs)})
        for h in reversed(hs):
            work = work.replace(h['old_block'], h['new_block'], 1)
        applied = list(hs)
        # ① 目标文件与 dev 文件**逐字节相同**
        checks.append({'name': 'equals_dev_%s' % fn,
                       'ok': work.encode('utf-8') == dev_b,
                       'detail': '改写后 %d B vs dev %d B'
                                 % (len(work.encode('utf-8')), len(dev_b))})
        # ② 还原式复核：**按行号**把新文本反推回旧文本 ⇒ 必须逐字等于原件
        #    🔴 **不靠字符串搜索** ⇒ 锚点块重叠也不会误替换。
        back = reverse_by_position(work, old_text, applied)
        checks.append({'name': 'reverse_reconstruct_%s' % fn,
                       'ok': back == old_text,
                       'detail': '还原后 %d B vs 原 %d B' % (len(back), len(old_text))})
        # ②b 🔴 **内容级**校验（**这条才有鉴别力**）：改写段的**内容**必须逐字相等
        c_ok, c_detail = content_matches(work, applied)
        checks.append({'name': 'content_matches_%s' % fn, 'ok': c_ok,
                       'detail': c_detail})
        # ③ 行尾风格不变
        checks.append({'name': 'crlf_preserved_%s' % fn,
                       'ok': work.encode('utf-8').count(b'\r\n') == cand_b.count(b'\r\n'),
                       'detail': '%d -> %d' % (cand_b.count(b'\r\n'),
                                              work.encode('utf-8').count(b'\r\n'))})
        # ④ 语法可解析
        try:
            import ast
            ast.parse(work)
            checks.append({'name': 'ast_ok_%s' % fn, 'ok': True, 'detail': ''})
        except SyntaxError as e:
            checks.append({'name': 'ast_ok_%s' % fn, 'ok': False, 'detail': repr(e)})
        prepared.append((fn, candp, cand_b, work.encode('utf-8'), dev_b, len(applied)))

    # 反证：把其中一块改坏 ⇒ **内容级**判据必须 FAIL（这才是有鉴别力的那条）
    if prepared:
        fn, candp, cand_b, new_bytes, dev_b, n_applied = prepared[0]
        work = new_bytes.decode('utf-8')
        broken = work.replace('def allow_bgkeep', 'def allow_bgkeep_X', 1)
        old_text = cand_b.decode('utf-8')
        new_text = dev_b.decode('utf-8')
        hs = hunks(old_text, new_text)
        ce_ok, ce_detail = content_matches(broken, hs)
        checks.append({'name': 'counterexample_detected',
                       'ok': (not ce_ok),
                       'detail': '篡改内容后内容级校验 FAIL（符合预期）⇒ 判据有鉴别力；'
                                 '原判据说：%s' % ce_detail})
        # 另：按行号反推**本来就不该有鉴别力**（恒真）⇒ 如实记录，不假装它是判据
        checks.append({'name': 'note_positional_reverse_is_trivially_true',
                       'ok': True,
                       'detail': '「按行号反推」恒为真 ⇒ 鉴别力由 content_matches 承担'})

    print('--- 写前真不变量 ---')
    for c in checks:
        print('  %-46s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    if not all(c['ok'] for c in checks):
        print('FAIL: 真不变量未全 PASS ⇒ 零改动')
        return 3

    if not args.apply:
        print('（dry-run：未写任何文件）')
        return 0

    for fn, candp, cand_b, new_bytes, dev_b, n_applied in prepared:
        bak = candp + '.bak_app137'
        shutil.copy2(candp, bak)
        tmp = candp + '.tmp_app137'
        with open(tmp, 'wb') as f:
            f.write(new_bytes)
        os.replace(tmp, candp)

    # ── 写后复核 ────────────────────────────────────────────────────
    post = []
    for fn, candp, cand_b, new_bytes, dev_b, n_applied in prepared:
        with open(candp, 'rb') as f:
            now = f.read()
        with open(candp + '.bak_app137', 'rb') as f:
            bakb = f.read()
        post.append({'name': 'equals_dev_%s' % fn, 'ok': now == dev_b,
                     'detail': 'sha %s' % sha(now)[:16]})
        post.append({'name': 'bak_sha_matches_old_%s' % fn,
                     'ok': sha(bakb) == sha(cand_b),
                     'detail': sha(bakb)[:16]})
        post.append({'name': 'crlf_preserved_%s' % fn,
                     'ok': now.count(b'\r\n') == cand_b.count(b'\r\n'),
                     'detail': '%d -> %d' % (cand_b.count(b'\r\n'), now.count(b'\r\n'))})
        try:
            import ast
            ast.parse(now.decode('utf-8'))
            post.append({'name': 'ast_ok_%s' % fn, 'ok': True, 'detail': ''})
        except SyntaxError as e:
            post.append({'name': 'ast_ok_%s' % fn, 'ok': False, 'detail': repr(e)})

    ev = {
        'script': '_app137_sync_to_candidate.py',
        'task': 'APP-137：把 dev 树的 profile 改动定点同步进 v1.2 候选目录',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'candidate_app': cand,
        'files': [{'file': fn, 'n_hunks': n_applied,
                   'old_sha256': sha(cand_b), 'new_sha256': sha(new_bytes),
                   'dev_sha256': sha(dev_b),
                   'old_bytes': len(cand_b), 'new_bytes': len(new_bytes)}
                  for fn, candp, cand_b, new_bytes, dev_b, n_applied in prepared],
        'pre_write_invariants': checks,
        'post_write_selfcheck': post,
        'post_write_ok': all(p['ok'] for p in post),
    }
    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('--- 写后复核 ---')
    for p in post:
        print('  %-46s %s  %s' % (p['name'], 'PASS' if p['ok'] else 'FAIL',
                                  p['detail']))
    print('证据：%s' % EVIDENCE)
    return 0 if ev['post_write_ok'] else 3


if __name__ == '__main__':
    sys.exit(main())
