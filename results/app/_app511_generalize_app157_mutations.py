#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app511_generalize_app157_mutations.py —— 把 app157 判据的两条**反证变异**改成**版本容忍**。

## 为什么需要（本轮实测发现的真问题）

`_app508` 修好的 `mutate_always_fallback` 写死了断言
`out.count('False') >= 2`（“必须废掉**两条**保留克隆条件”）⇒
🔴 **在老客户包上会直接抛 `AssertionError`**：

- `Confucius4_LiveCaption_v2.4/app/tts_worker.py`（11-07 打的完整版）
  ⇒ `synth()` 决策分支**只有 ①**（`if self.clone_mode and not _bound:`）、
  **没有 ②**（`elif self._has_clone_voice() and not _bound:`）
  ⇒ 源码里只存在 **1** 条「保留克隆」条件 ⇒ `count('False')` 只有 1
  ⇒ 断言炸 ⇒ 判据**跑不完**（看起来像假 FAIL，实际是判据写死了版本）。

## 改法（**判据层，产品代码零改动**）

两条变异统一改成：**对源码里**实际存在**的每一条「保留克隆」条件**逐条替换**，
并在替换后逐条断言「已不存在」：

- `mutate_always_fallback` ⇒ 存在的全换 `'False'`（永远回落）
- `mutate_never_fallback`  ⇒ 存在的全换 `'True'`（永不回落）

🔴 **fail-closed 保留**：
- 一条都没废掉 ⇒ 断言炸（变异无效 ⇒ 反证无意义）；
- 任一条存在却没被废掉 ⇒ 断言炸（⇒ 又变成假反证）。

🔴 **幂等**：已是新版就原样退出（源文件零改动）。
🔴 **行尾**：原文件是 CRLF ⇒ 读入 `newline=''` 原样保留、写出原样保留。
🔴 只改 `results/app/app157_follow_speaker_regression_test.py`；
   不碰 `live_caption/`、不碰任何客户包、不碰 `CORRECTIONS_*.md`。
"""

from __future__ import annotations

import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'app157_follow_speaker_regression_test.py')

NEW_ALWAYS = '''def mutate_always_fallback(decision_src: str) -> str:
    """反证 3：**永远回落** ⇒ 判据 B1（follow_speaker 下必须保留克隆）**必须 FAIL**。

    🔴 **必须废掉源码里**所有**「保留克隆」条件**（一条都不能漏）：
      ① `if self.clone_mode and (not _bound):`            → 保留全局克隆
      ② `elif self._has_clone_voice() and (not _bound):`  → 沿用上一句克隆
    ⇒ 只废 ① 会落进 ② ⇒ 克隆音色**照样保留** ⇒ 反证**永远 PASS = 假反证**。

    🔴 **版本容忍**（2026-11-13）：**老客户包**（如 `Confucius4_LiveCaption_v2.4`）
      的决策分支**只有 ①**、没有 ② ⇒ 断言按「源码里**实际存在**的条件」逐条核，
      而不是写死「必须有 2 条」⇒ 否则在老包上会抛 `AssertionError`
      （看起来像假 FAIL，实际是判据写死了版本）。
      但「**一条都没废掉**」仍然 fail-closed。
    """
    conds = ('self.clone_mode and (not _bound)',
             'self._has_clone_voice() and (not _bound)')
    out = decision_src
    n_hit = 0
    for c in conds:
        if c in out:
            assert out.count(c) == 1, \\
                'mutate_always_fallback: %r 命中不唯一' % c
            out = out.replace(c, 'False')
            n_hit += 1
    assert n_hit >= 1, 'mutate_always_fallback: 源码里没有任何「保留克隆」条件'
    for c in conds:
        assert c not in out, 'mutate_always_fallback: %r 没被废掉' % c
    return out
'''

NEW_NEVER = '''def mutate_never_fallback(decision_src: str) -> str:
    """反证 4：**永不回落** ⇒ 判据 B3（按句绑定模式必须回落）**必须 FAIL**。

    🔴 同 `mutate_always_fallback`：**源码里实际存在的**每一条「保留克隆」条件
      全换 `'True'`（一条都不能漏 ⇒ 否则落进另一条分支 ⇒ 变异没生效
      ⇒ 反证**永远 PASS = 假反证**）。
    🔴 **版本容忍**（2026-11-13）：老客户包只有 ① ⇒ 只换那一条。
    """
    conds = ('self.clone_mode and (not _bound)',
             'self._has_clone_voice() and (not _bound)')
    out = decision_src
    n_hit = 0
    for c in conds:
        if c in out:
            assert out.count(c) == 1, \\
                'mutate_never_fallback: %r 命中不唯一' % c
            out = out.replace(c, 'True')
            n_hit += 1
    assert n_hit >= 1, 'mutate_never_fallback: 源码里没有任何「保留克隆」条件'
    for c in conds:
        assert c not in out, 'mutate_never_fallback: %r 没被废掉' % c
    return out
'''


def replace_function(lines, name: str, new_block: str, eol: str):
    """把顶层 `def <name>(...)` 整块换成 `new_block`（唯一命中 ⇒ 找不到就中止）。"""
    start = -1
    for i, ln in enumerate(lines):
        if ln.startswith('def %s(' % name):
            start = i
            break
    if start < 0:
        raise AssertionError('找不到 def %s(' % name)
    end = start + 1
    while end < len(lines):
        ln = lines[end]
        if ln.startswith('def ') or (ln and not ln.startswith(' ')):
            break
        end += 1
    return lines[:start] + new_block.rstrip('\n').split('\n') + [''] + lines[end:]


def main() -> int:
    if not os.path.isfile(TARGET):
        print('target not found: %s' % TARGET)
        return 2
    with open(TARGET, 'r', encoding='utf-8', newline='') as f:
        src = f.read()
    eol = '\r\n' if '\r\n' in src else '\n'
    lines = src.split(eol)

    if '版本容忍' in src and 'mutate_never_fallback: 源码里没有任何' in src:
        print('NO-OP：两条变异已是版本容忍版')
        return 0

    try:
        lines = replace_function(lines, 'mutate_always_fallback', NEW_ALWAYS, eol)
        lines = replace_function(lines, 'mutate_never_fallback', NEW_NEVER, eol)
    except AssertionError as e:
        print('ABORT: %s ⇒ 源文件零改动' % e)
        return 3

    out = eol.join(lines)
    try:
        ast.parse(out)
    except SyntaxError as e:
        print('ABORT: 语法错误 ⇒ 源文件零改动（%s）' % e)
        return 3

    with open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('PATCHED: mutate_always_fallback / mutate_never_fallback 版本容忍')
    print('target: %s' % TARGET)
    return 0


if __name__ == '__main__':
    sys.exit(main())
