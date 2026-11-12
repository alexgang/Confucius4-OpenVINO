#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app509_polish_app157_gate_format.py —— 整理 app157 判据脚本的**空白/空行**（**纯格式，零语义**）。

## 为什么需要

上一轮补丁（`_app508_fix_app157_stale_gate.py`）把新方法插进类里时，
空行数不对（类方法前 3 行空行、顶层 `def` 前 0 行空行、EOF 多一行空行）
⇒ 虽然 `ast.parse` 通过、可执行，但**可读性/一致性**与文件其余部分不一致
⇒ reviewer 一眼看 diff 会以为混进了别的改动。

## 本脚本做什么（**只动空白**）

- 类方法（`    def `）前 ⇒ **恰好 1** 个空行；
- 顶层 `def `/`class ` 前 ⇒ **恰好 2** 个空行；
- 文件末尾 ⇒ **恰好 1** 个换行（无尾部空行）。

## 🔴 自检（写后必查）

1. **`ast.dump` 前后逐字相同** ⇒ 证明**只动了空白，零语义改动**；
2. 行尾保持 **CRLF**（原文件是 CRLF ⇒ 读入 `newline=''` 原样保留、写出原样保留）；
3. 「无裸 LF」不变量（CRLF 文件里不得出现单独 LF）。

🔴 幂等：重复跑 ⇒ `NO-OP`（空行已合规）⇒ 源文件零改动。
🔴 只改 `results/app/app157_follow_speaker_regression_test.py`；
   不碰 `live_caption/`（产品代码）、不碰任何客户包、不碰 `CORRECTIONS_*.md`。
"""

from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'app157_follow_speaker_regression_test.py')


def main() -> int:
    if not os.path.isfile(TARGET):
        print('target not found: %s' % TARGET)
        return 2
    with open(TARGET, 'r', encoding='utf-8', newline='') as f:
        src = f.read()

    eol = '\r\n' if '\r\n' in src else '\n'
    had_final_eol = src.endswith(eol)
    lines = src.split(eol)

    # 去掉尾部空行（EOF 只留一个换行）
    while lines and lines[-1].strip() == '':
        lines.pop()

    out = []
    for ln in lines:
        stripped = ln.strip()
        is_def = (stripped.startswith('def ') or stripped.startswith('class '))
        is_meth = stripped.startswith('def ') and ln.startswith('    def ')
        if is_def and out:
            want = 1 if (ln.startswith('    def ') or ln.startswith('        def ')) else 2
            # 统计 out 尾部连续空行
            n = 0
            while n < len(out) and out[len(out) - 1 - n].strip() == '':
                n += 1
            # 🔴 横幅注释**直接贴在** def 上（`# ==== ...`）⇒ **不插空行**
            #   （插了会把注释和 def 拆开 ⇒ 与文件其余部分不一致 ⇒ 无谓 diff）
            j = len(out) - n - 1
            attached_comment = (j >= 0 and out[j].lstrip().startswith('#'))
            if attached_comment:
                want = n
            if n != want:
                for _ in range(n):
                    out.pop()
                out.extend([''] * want)
        out.append(ln)

    new = eol.join(out) + (eol if had_final_eol else '')

    # ── 自检 1：ast.dump 前后相同 ⇒ 只动了空白 ──
    try:
        a1 = ast.dump(ast.parse(src))
        a2 = ast.dump(ast.parse(new))
    except SyntaxError as e:
        print('ABORT: 语法错误 ⇒ 源文件零改动（%s）' % e)
        return 3
    if a1 != a2:
        print('ABORT: ast.dump 前后不同 ⇒ 疑似改了语义 ⇒ 源文件零改动')
        return 3

    # ── 自检 2：无裸 LF ──
    body = new[:-len(eol)] if new.endswith(eol) else new
    if '\n' in body.replace('\r\n', ''):
        print('ABORT: 出现裸 LF ⇒ 源文件零改动')
        return 3

    if new == src:
        print('NO-OP：空行已合规')
        return 0

    with open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    print('POLISHED: %s' % TARGET)
    print('bytes %d -> %d ; eol=%r ; ast.dump identical' % (len(src), len(new), eol))
    return 0


if __name__ == '__main__':
    sys.exit(main())
