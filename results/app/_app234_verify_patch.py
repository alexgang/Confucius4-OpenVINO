#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-234 轮 · **另起脚本**独立复核 `_app129_build_v26.py` 的改动。

🔴 为什么不与补丁脚本同进程复核：补丁脚本自己说 PASS 不算证据
（本项目的「判据能识破有缺陷的旧产物」纪律）⇒ 写盘后**另起进程**再核。

复核项：
  1. 文件可 `ast.parse`；
  2. `stage_identity` 存在且**唯一**；
  3. `identity` 已在 argparse 的 choices 里；
  4. `main()` 里 `identity` 分支存在且**唯一**；
  5. **旧正文逐字未变**（与写前备份逐行 diff：除新增块外零差异）；
  6. 行尾风格不变（纯 CRLF）；
  7. `git diff --numstat` 恰为「新增 N 行 / 删除 0 行」；
  8. **反证组**：把改动**还原**成旧版（去掉新增块）⇒ 新判据必须 FAIL
     ⇒ 证明判据确实绑在「改动是否存在」上，不是恒 PASS。
"""
from __future__ import annotations

import ast
import difflib
import io
import os
import subprocess
import sys


def find_repo():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        if os.path.isdir(os.path.join(d, 'live_caption')):
            return d
        d = os.path.dirname(d)
    raise SystemExit('[FAIL] 找不到仓库根')


REPO = find_repo()
TARGET = os.path.join(REPO, 'live_caption', '_app129_build_v26.py')
BACKUP = os.path.join(os.environ.get('TEMP', '/tmp'),
                      '_app129_build_v26.py.bak_app234')

FAILS = []
N = [0]


def chk(name, ok, detail=''):
    N[0] += 1
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('   ' + detail) if detail else ''))
    if not ok:
        FAILS.append((name, detail))


def read_lines(path):
    with open(path, 'rb') as f:
        return f.read().decode('utf-8').splitlines()


def main() -> int:
    print('=== APP-234 独立复核：_app129_build_v26.py 改动 ===')
    print('目标：%s' % TARGET)

    raw = open(TARGET, 'rb').read()
    text = raw.decode('utf-8')
    old = open(BACKUP, 'rb').read().decode('utf-8')

    # 1) AST
    try:
        ast.parse(text)
        chk('ast.parse 通过', True)
    except SyntaxError as e:
        chk('ast.parse 通过', False, repr(e))
        return 1

    # 2) stage_identity 唯一
    chk('stage_identity 定义存在且唯一',
        text.count('def stage_identity():') == 1,
        'count=%d' % text.count('def stage_identity():'))

    # 3) choices 含 identity
    chk('argparse choices 含 identity',
        "choices=['copy', 'sync', 'identity', 'pack', 'cleanup', 'all'])"
        in text)

    # 4) main() 中 identity 分支唯一
    chk('main() 中 identity 分支唯一',
        text.count("if args.stage in ('identity', 'all'):") == 1,
        'count=%d' % text.count("if args.stage in ('identity', 'all'):"))

    # 5) 旧正文逐字未变：**正向重建**校验 —— 新文件 == 对旧文件施加
    #    「已知 3 处编辑」后的结果（比「零删除零改写」更强：它同时证明
    #    「该改的都改了」＋「没多改一个字节」）。
    #    ⚠️ `choices=` 那行**必须**被改（加 'identity'）⇒ 「零改写」是
    #    错判据（假 FAIL 源）；正解是「恰好 1 行改写，且改写前后逐字等于预期」。
    old_lines = read_lines(BACKUP)
    new_lines = read_lines(TARGET)
    sm = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    removed = 0
    changed = 0
    added = 0
    changed_pairs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'delete':
            removed += (i2 - i1)
        elif tag == 'replace':
            changed += (i2 - i1)
            changed_pairs.append((old_lines[i1], new_lines[j1]))
        elif tag == 'insert':
            added += (j2 - j1)
    expect_old_choices = (
        "                    choices=['copy', 'sync', 'pack', 'cleanup', 'all'])")
    expect_new_choices = (
        "                    choices=['copy', 'sync', 'identity', 'pack', "
        "'cleanup', 'all'])")
    chk('旧正文无删除（零 removed）', removed == 0, 'removed=%d' % removed)
    chk('恰好 1 行改写，且就是 argparse choices 行',
        changed == 1 and changed_pairs
        and changed_pairs[0][0] == expect_old_choices
        and changed_pairs[0][1] == expect_new_choices,
        'changed=%d pair=%r' % (changed, changed_pairs[:1]))

    # 5b) 🔴 **正向重建**：把「已知 3 处编辑」施加到写前备份 ⇒ 必须
    #     **逐行等于**现在的文件 ⇒ 同时证明「该改的都改了」＋「没多改」。
    #     ⚠️ 不写死「新增 N 行」这种常量（判据里的常量 = 假 FAIL 源）；
    #     改为从**备份**重建，判据自带鉴别力。
    expect_lines = list(old_lines)
    # 编辑 ①：插入 stage_identity 块（在 stage_cleanup 之前）
    idx = expect_lines.index('def stage_cleanup():')
    block = new_lines[idx:idx + 33]        # 从**新文件**里取实际插入块
    expect_lines[idx:idx] = block
    # 编辑 ②：改写 choices 行
    ci = expect_lines.index(expect_old_choices)
    expect_lines[ci] = expect_new_choices
    # 编辑 ③：main() 里插入 identity 分支
    si = expect_lines.index(
        "    if args.stage in ('sync', 'all'):")
    expect_lines[si + 3:si + 3] = [
        "    if args.stage in ('identity', 'all'):",
        '        if not stage_identity():',
        '            return 6']
    chk('正向重建：备份 + 3 处已知编辑 ⇒ 逐行等于现文件',
        expect_lines == new_lines,
        'expected %d 行 / actual %d 行' % (len(expect_lines), len(new_lines)))
    chk('新增行数与重建结果一致',
        added == len(new_lines) - len(old_lines),
        'added=%d delta=%d' % (added, len(new_lines) - len(old_lines)))

    # 6) 行尾风格不变（纯 CRLF）
    crlf = raw.count(b'\r\n')
    lf = raw.count(b'\n')
    chk('行尾风格不变（纯 CRLF，无孤立 LF）', crlf == lf,
        'CRLF=%d LF=%d' % (crlf, lf))

    # 7) git diff --numstat：新增 39 行 / 删除 1 行（删的是被改写的
    #    choices 行 ⇒ git 记成 1 删 1 增）⇒ 断言「删除恰好 1 行」。
    p = subprocess.run(['git', '-C', REPO, 'diff', '--numstat', '--',
                        'live_caption/_app129_build_v26.py'],
                       capture_output=True, text=True)
    ns = (p.stdout or '').strip()
    parts = ns.split('\t')
    ok_ns = False
    detail = ns or '(空)'
    if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
        # 删除行数必须恰好 1（= 被改写的 choices 行），且新增行数 > 1
        ok_ns = (parts[1] == '1' and int(parts[0]) > 1)
    chk('git diff --numstat：删除恰好 1 行（choices 行改写）', ok_ns, detail)

    # 8) 反证组：还原成旧版 ⇒ 判据必须 FAIL
    print('\n[反证组] 把改动还原成旧版 ⇒ 同一批判据必须 FAIL：')
    reverted = text
    # 去掉新增的 stage_identity 块
    i = reverted.find('def stage_identity():')
    j = reverted.find('def stage_cleanup():')
    if i >= 0 and j > i:
        reverted = reverted[:i] + reverted[j:]
    reverted = reverted.replace(
        "choices=['copy', 'sync', 'identity', 'pack', 'cleanup', 'all'])",
        "choices=['copy', 'sync', 'pack', 'cleanup', 'all'])")
    reverted = reverted.replace(
        "    if args.stage in ('identity', 'all'):\r\n"
        "        if not stage_identity():\r\n"
        "            return 6\r\n", '')
    anti_fail = 0
    if reverted.count('def stage_identity():') != 1:
        anti_fail += 1
    if "choices=['copy', 'sync', 'identity', 'pack', 'cleanup', 'all'])" \
            not in reverted:
        anti_fail += 1
    if reverted.count("if args.stage in ('identity', 'all'):") != 1:
        anti_fail += 1
    chk('反证组：旧版命中判据失败项 > 0（判据有鉴别力）',
        anti_fail > 0, 'fail=%d' % anti_fail)

    print()
    print('PASS=%d / FAIL=%d' % (N[0] - len(FAILS), len(FAILS)))
    if FAILS:
        for n, d in FAILS:
            print('  [FAIL] %s  %s' % (n, d))
        return 1
    print('结论：PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
