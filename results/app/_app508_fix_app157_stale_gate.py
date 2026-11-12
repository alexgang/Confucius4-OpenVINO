#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app508_fix_app157_stale_gate.py —— 修掉 app157 判据**过期**（stale）导致的假 FAIL。

## 背景（本轮巡检发现的真缺陷）

`results/app/app157_follow_speaker_regression_test.py` 在 **HEAD（37b146a）** 上
直接跑 ⇒ **6 PASS / 4 FAIL**，且 4 条 FAIL 全是**异常**（不是判据判 FAIL）：

    FAIL  B3 …            异常：'_FakeWorker' object has no attribute '_apply_self_ref_voice'
    FAIL  D-B3 反证        异常：'_FakeWorker' object has no attribute '_apply_self_ref_voice'
    FAIL  D-B4 反证        异常：'_FakeWorker' object has no attribute '_apply_self_ref_voice'

⇒ **不是产品缺陷，是判据过期**：`synth()` 的决策分支在 APP-061⑤c / APP-086②
之后**多了一条**「沿用上一句克隆音色」的路径（`elif self._has_clone_voice() …`），
而判据里的桩 `_FakeWorker` 没跟上 ⇒ **判据跑的是一条已经不存在的代码路径**
⇒ 恒报 FAIL ⇒ **假 FAIL**（记忆铁律：FAIL 先怀疑判据/环境）。

工作区里已有一份**半成品**修补（15:05 落盘，未入库）⇒ 补齐它还差的最后两处：

### ① 桩缺 `_log_keep_last_clone`
`mutate_always_fallback`（D-B3 反证）把 `self.clone_mode and (not _bound)`
换成 `False` ⇒ 真实代码会落进 **`elif self._has_clone_voice() and (not _bound)`**
⇒ 调用 `self._log_keep_last_clone()` ⇒ 桩没有这个方法 ⇒ **异常**（不是判 FAIL）。

### ② D-B3 的变异**只废了一条**「保留克隆」条件 ⇒ 变异**没生效**
`synth()` 的 else 分支现在有**两条**「保留克隆」路径：
  ① `if self.clone_mode and (not _bound):`      → 保留全局克隆
  ② `elif self._has_clone_voice() and (not _bound):` → 沿用上一句克隆
⇒ 只废 ① 会落进 ② ⇒ 克隆音色**照样保留** ⇒ D-B3 的断言「B1 必须 FAIL」变成
**假反证**（记忆铁律：反证恒 PASS = 判据没有鉴别力）⇒ 必须**两条一起废**。

## 本脚本做什么（只改**判据脚本**本身 ⇒ **产品代码零改动**）

- ① 给 `_FakeWorker` 补 `_log_keep_last_clone`（**委托给真实实现**，与同文件其它
  两个桩同口径 ⇒ 判据验的仍是**真实代码**）；
- ② 让 `mutate_always_fallback` **同时废掉两条**「保留克隆」条件
  （并断言两处替换都**命中**⇒ 不会静默变成假反证）。

🔴 **本脚本只改 `results/app/app157_follow_speaker_regression_test.py`**；
   不碰 `live_caption/`（产品代码）、不碰任何客户包、不碰 `CORRECTIONS_*.md`。
🔴 幂等：两处替换都用「唯一命中」断言 ⇒ 重复跑要么成功要么**原样退出**。
🔴 行尾：原文件是 **CRLF** ⇒ 读入按 `newline=''` 原样保留、写出同样原样保留。
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'app157_follow_speaker_regression_test.py')

# ── ① 桩：补 `_log_keep_last_clone`（插在 `_has_clone_voice` 桩之后）────────
ADD_1 = [
    "",
    "    def _log_keep_last_clone(self):",
    "        \"\"\"APP-061⑤c：**沿用上一句的克隆音色**（标签晚到、未登记按句）。",
    "",
    "        ⚠️ **委托给真实实现**（AST 抽出的源码）",
    "        ⇒ 判据验的仍是**真实代码**，不是手抄的桩。",
    "        \"\"\"",
    "        fn = self._ns.get('_log_keep_last_clone')",
    "        if fn is None:",
    "            self._last_voice_spk = None",
    "            self._last_voice_kind = 'clone'",
    "            return None",
    "        return fn(self)",
]

# ── ② 反证变异：两条「保留克隆」条件**一起废** ──────────────────────────────
REPL_2 = [
    "def mutate_always_fallback(decision_src: str) -> str:",
    "    \"\"\"反证 3：**永远回落** ⇒ 判据 B1（follow_speaker 下必须保留克隆）**必须 FAIL**。",
    "",
    "    🔴 **必须同时废掉两条「保留克隆」条件**：",
    "      ① `if self.clone_mode and (not _bound):`            → 保留全局克隆",
    "      ② `elif self._has_clone_voice() and (not _bound):`  → 沿用上一句克隆",
    "    ⇒ 只废 ① 会落进 ② ⇒ 克隆音色**照样保留** ⇒ 反证**永远 PASS = 假反证**。",
    "    \"\"\"",
    "    out = decision_src.replace('self.clone_mode and (not _bound)', 'False')",
    "    out = out.replace('self._has_clone_voice() and (not _bound)', 'False')",
    "    assert out != decision_src, 'mutate_always_fallback 没改到任何条件 '",
    "    assert out.count('False') >= 2, 'mutate_always_fallback 只废掉了一条'",
    "    return out",
]


def find_def(lines, name):
    """返回 `def <name>(` 所在行下标；找不到返回 -1。"""
    for i, ln in enumerate(lines):
        if ln.startswith('def %s(' % name):
            return i
    return -1


def main() -> int:
    if not os.path.isfile(TARGET):
        print('target not found: %s' % TARGET)
        return 2
    with open(TARGET, 'r', encoding='utf-8', newline='') as f:
        src = f.read()

    eol = '\r\n' if '\r\n' in src else '\n'
    lines = src.split(eol)
    trailing_nl = src.endswith(eol)

    changed = []

    # ── ① 桩补方法 ──
    if any('def _log_keep_last_clone(self)' in ln for ln in lines):
        print('SKIP ① 桩已有 _log_keep_last_clone')
    else:
        # 插在 `_has_clone_voice` 桩之后（桩是类内方法，缩进 4）
        anchor = None
        for i, ln in enumerate(lines):
            if ln.startswith('    def _has_clone_voice(self):'):
                anchor = i
                break
        if anchor is None:
            print('ABORT ① 找不到 `    def _has_clone_voice(self):` ⇒ 源文件零改动')
            return 3
        # 找到该方法的结束（下一个缩进 4 的 `def ` 或类结束）
        end = anchor + 1
        while end < len(lines):
            ln = lines[end]
            if ln.startswith('    def ') or (ln and not ln.startswith(' ')):
                break
            end += 1
        lines[end:end] = ADD_1
        changed.append('① _FakeWorker._log_keep_last_clone')

    # ── ② 反证变异 ──
    if any("out.count('False') >= 2" in ln for ln in lines):
        print('SKIP ② mutate_always_fallback 已是新版')
    else:
        start = find_def(lines, 'mutate_always_fallback')
        if start < 0:
            print('ABORT ② 找不到 def mutate_always_fallback ⇒ 源文件零改动')
            return 3
        # 该函数体到下一个顶层 def / 结尾
        end = start + 1
        while end < len(lines):
            ln = lines[end]
            if ln.startswith('def ') or (ln and not ln.startswith((' ', ')'))) and ln.startswith('def'):
                break
            if ln.startswith('def '):
                break
            end += 1
        lines[start:end] = REPL_2
        changed.append('② mutate_always_fallback 两条一起废')

    if not changed:
        print('NO-OP：两处都已就位')
        return 0

    out = eol.join(lines)
    if trailing_nl:
        out += eol
    with open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('PATCHED: %s' % '; '.join(changed))
    print('target: %s' % TARGET)
    return 0


if __name__ == '__main__':
    sys.exit(main())
