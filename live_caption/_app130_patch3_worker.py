#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130 补丁③：`tts_worker.py` 的**行级**定点补丁（🔴 避免 emoji 锚点）。

## 为什么用行级补丁

补丁②用「整行文本」做锚点时踩了 **emoji 码位不一致**的坑：
文件里是 `🔴🔴🔴`（三个 U+1F534），我写的是 `🔴🔴🔳` ⇒ 命中 0 次。
⇒ 改用**行级补丁**：行内用**纯文本唯一锚点**定位，行号由脚本算出来
（不用记忆里的行号）⇒ 不受 emoji 影响。

## 两处改动

1. worker 侧第三道闸（RUNAWAY）触发处 ⇒ 调 `_te._mark_runaway(self.engine, 'threshold')`。
2. 逐句遥测处 ⇒ 引擎侧运行时保险触发时把 `runaway` 标记补上。

## 纪律

备份 → 写前真不变量 ＋ 还原式复核 → 临时文件 → `os.replace`
⇒ 写后另起脚本复核 ＋ `git diff --numstat`。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'tts_worker.py')


def crlf(s: str) -> str:
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


# ── 改动①：第三道闸触发处 ────────────────────────────────────────────
ANCHOR1 = "if _runaway_s is not None and _got_s > _runaway_s:"
INS1 = [
    "                            # 🔴🔴🔳 APP-130②：记 `tts_runaway`",
    "                            #   （与 `tts_engine` 的运行时保险**同一句只记一次**",
    "                            #     ⇒ 由 `engine._runaway_counted` 守卫去重）",
    "                            try:",
    "                                _te._mark_runaway(self.engine, 'threshold')",
    "                            except Exception:",
    "                                pass",
]

# ── 改动②：逐句遥测补 runaway 标记 ───────────────────────────────────
# 🔴 锚点必须**纯文本且全文唯一**：「APP-042：」在文件里出现 13 次；
#   而这一行的真实文本是「APP-042：变速器的**收尾块**（最后一帧的尾巴）」
#   （`**` 只包住「收尾块」）⇒ 用整段纯文本定位。
ANCHOR2 = "变速器的**收尾块**（最后一帧的尾巴）"
INS2 = [
    "                # 🔴🔴🔳 APP-130②：**引擎侧运行时保险触发的 RUNAWAY**",
    "                #   （`tts_engine._guarded_stream` 在「超失控阈值」或",
    "                #     「code predictor 出 NaN」时会停句并把",
    "                #     `engine._last_end_reason` 置成 `runaway`",
    "                #     ⇒ 这里把它反映到逐句遥测的 `runaway` 标记上）",
    "                try:",
    "                    if getattr(self.engine, '_runaway_counted', False):",
    "                        runaway = True",
    "                        self._last_end_reason = 'runaway'",
    "                except Exception:",
    "                    pass",
]


def _find(lines, anchor, start=0):
    hits = [i for i in range(start, len(lines))
            if anchor in lines[i]]
    return hits


def main() -> int:
    raw = open(TARGET, 'rb').read()
    orig = raw.decode('utf-8')
    if '\r\n' not in orig:
        print('FAIL: 目标不是 CRLF ⇒ 停手')
        return 2
    backup = os.path.join(tempfile.gettempdir(), 'tts_worker.py.app130c.bak')
    shutil.copy2(TARGET, backup)
    print('备份: %s (%d B)' % (backup, len(raw)))

    lines = orig.split('\r\n')          # 末尾有一个空串（文件以 CRLF 结尾）
    n_before = len(lines)

    # ── 定位①：第三道闸 ────────────────────────────────────────────
    h1 = _find(lines, ANCHOR1)
    if len(h1) != 1:
        print('FAIL: 锚点①命中 %d 次（要求 1 次）⇒ 零改动' % len(h1))
        return 3
    i1 = h1[0]
    # 插到该 `if` 语句的**函数体首行之后**（下一行）
    lines[i1 + 1:i1 + 1] = INS1

    # ── 定位②：逐句遥测（APP-042 收尾块注释行）────────────────────
    h2 = _find(lines, ANCHOR2, start=i1)
    if len(h2) != 1:
        print('FAIL: 锚点②命中 %d 次（要求 1 次）⇒ 零改动' % len(h2))
        return 3
    i2 = h2[0]
    lines[i2:i2] = INS2

    text = '\r\n'.join(lines)

    # ── 真不变量（写前）────────────────────────────────────────────
    errs = []
    if text.count('\n') != text.count('\r\n'):
        errs.append('行尾风格被改')
    if len(lines) != n_before + len(INS1) + len(INS2):
        errs.append('行数增量不符')
    # 还原式复核：把插入的两段删掉 ⇒ 必须逐字节还原原文件
    #   ⚠️ 下标换算：`i2` 是**插完 INS1 之后**的下标 ⇒ 终局列表里
    #      INS2 占 [i2, i2+len(INS2)-1]；INS1 占 [i1+1, i1+len(INS1)]。
    back = (lines[:i1 + 1]
            + lines[i1 + 1 + len(INS1):i2]
            + lines[i2 + len(INS2):])
    if '\r\n'.join(back) != orig:
        errs.append('还原式复核失败：删掉插入段后与原文不逐字节相同')
    for sym in ('_mark_runaway', '_runaway_counted'):
        if sym not in text:
            errs.append('缺关键符号：%s' % sym)
    try:
        compile(text, TARGET, 'exec')
    except SyntaxError as e:
        errs.append('语法错误：%s' % e)
    if errs:
        print('自检 FAIL ⇒ 零改动：')
        for e in errs:
            print('  - %s' % e)
        return 4

    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TARGET), suffix='.app130c.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(text.encode('utf-8'))
        os.replace(tmp, TARGET)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print('已打补丁：改动①（第三道闸计数）＋ 改动②（遥测补 runaway 标记）')
    print('字节：%d → %d（%+d）／行数：%d → %d（%+d）'
          % (len(raw), len(text.encode('utf-8')),
             len(text.encode('utf-8')) - len(raw),
             orig.count('\n'), text.count('\n'),
             text.count('\n') - orig.count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
