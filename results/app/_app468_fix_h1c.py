#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_fix_h1c.py —— 定点修 §173 判据 H1（第三次）：头部须引最新章节 §180。

🔴🔴 **修掉 `_app468_fix_h1b.py` 的判据自身缺陷（伪不变量）**：
   b 版的写后校验是 `if '稳态' in ct: ABORT` ⇒ 而它自己要写入的 NEW 串里
   **含有「稳态真值」四个字**（用于说明「§180 已撤回该措辞」）
   ⇒ 写入后必然命中自己的禁用词 ⇒ **必然 ABORT** ⇒ **源文件零改动**
   ⇒ 这正是 MEMORY 里那条「**写前自检 FAIL ⇒ 源文件零改动**」保护生效，
   但也说明**禁用词不能是「会出现在新正文里的说明性引用」**。
   本版改为只禁**被撤回的那一个具体措辞**（`稳态 185 行`），
   并**额外断言**新串确实引用了 §180 且确实不含被撤回措辞。

纪律：唯一命中断言 ＋ 只改「当前任务」这一行 ＋ 旧章节正文一字不动
     ＋ CORRECTIONS_APP.md 只读（开工/收尾 SHA 复核）。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

OLD = ('＋ **新增「git 半交付」判据**（**稳态 185 行／0 FAIL／反证 3/3**）｜'
       '**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未占设备**｜'
       '结果见 §179 归档件（§179 是对 §178「判据 177 行」这一**自指快照数字**的勘误；'
       '§178 的结论与 6 处修复本身全部成立）')

NEW = ('＋ **新增「git 半交付」判据**（**不变量：`FAIL=0`／`MISSING=0`／反证 3/3**；'
       '审计行数是**观察量、非定值** ⇒ §180 已撤回「行数＝定值」的措辞）｜'
       '**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未占设备**｜'
       '结果见 §180 归档件（§179／§180 两节是把「自指数字」这一**概念错误**连根拔除：'
       '**只引用不变量**；§178 的结论与 6 处修复本身全部成立）')

# 🔴 被撤回的具体措辞（只禁它，不再禁「稳态」二字本身）
BANNED = '稳态 185 行'


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    corr_before = open(CORR, 'rb').read()
    text = open(STATUS, 'rb').read().decode('utf-8')

    n = text.count(OLD)
    if n != 1:
        print('ABORT: 目标串出现 %d 次（要求恰好 1 次）⇒ 源文件零改动' % n)
        return 1

    new_text = text.replace(OLD, NEW, 1)

    m = re.search(r'(?m)^当前任务: (.*)$', new_text)
    if not m:
        print('ABORT: 未找到「当前任务」行 ⇒ 源文件零改动')
        return 1
    ct = m.group(1)
    if '§180' not in ct:
        print('ABORT: 新的「当前任务」行未引用 §180 ⇒ 源文件零改动')
        return 1
    if BANNED in ct:
        print('ABORT: 头部仍含被撤回的措辞「%s」⇒ 源文件零改动' % BANNED)
        return 1

    nb = new_text.encode('utf-8')
    checks = [
        ('bytes<=40000', len(nb) <= 40000, str(len(nb))),
        ('lines<=300', nb.count(b'\n') + 1 <= 300, str(nb.count(b'\n') + 1)),
        ('no CRLF', nb.count(b'\r\n') == 0, str(nb.count(b'\r\n'))),
    ]
    for name, ok, val in checks:
        if not ok:
            print('ABORT: 自检 %s 失败（%s）⇒ 源文件零改动' % (name, val))
            return 1

    # 旧章节正文一字不动：除「当前任务」行外，原字节序列必须仍完整存在
    old_lines = text.split('\n')
    new_lines = new_text.split('\n')
    if len(old_lines) != len(new_lines):
        print('ABORT: 行数变化 ⇒ 源文件零改动')
        return 1
    diff_idx = [i for i in range(len(old_lines)) if old_lines[i] != new_lines[i]]
    if diff_idx != [4]:
        print('ABORT: 改动的行不是唯一的第 5 行（实际 %r）⇒ 源文件零改动' % (diff_idx,))
        return 1

    with open(STATUS, 'wb') as f:
        f.write(nb)

    corr_after = open(CORR, 'rb').read()
    if sha(corr_before) != sha(corr_after):
        print('ABORT: CORRECTIONS_APP.md 在写入期间发生变化 ⇒ 严重异常')
        return 1

    print('OK: 头部「当前任务」行已指向 §180；唯一改动行 = 第 5 行')
    print('    STATUS bytes=%d lines=%d  sha=%s'
          % (len(nb), nb.count(b'\n') + 1, sha(nb)[:16]))
    print('    CORR sha=%s bytes=%d  (零改动)' % (sha(corr_after)[:16], len(corr_after)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
