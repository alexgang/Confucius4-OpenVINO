#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_fix_h1.py —— 定点修 §173 判据 H1：头部「当前任务」只引 §178，而活文档最新章节是 §179。

🔴 纪律：**唯一命中断言**（目标串必须出现且仅出现 1 次）＋ 只改这一行 ＋
   旧章节正文一字不动 ＋ CORR 只读 ＋ 写前自检不过 ⇒ 源文件零改动。
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

OLD = ('当前任务: **巡检无新纠偏**（`last_ack=APP-100`；纠偏文件 **100 条 / 最大 APP-100**'
       '（SHA `219ef841…`／308 340 B）⇒ 无编号更大的新条目）｜**本轮修掉 6 处 git 半交付**'
       '（STATUS 引用的归档件／证据产物在磁盘上却从没进过 git ⇒ 换 clone 即断链）'
       '＋ **新增「git 半交付」判据**（177 行／0 FAIL／反证 3/3）｜**未打包 v2.5／未打 rc8／'
       '未通知用户／未调 MiniMax／未占设备**｜结果见 §178 归档件')

NEW = ('当前任务: **巡检无新纠偏**（`last_ack=APP-100`；纠偏文件 **100 条 / 最大 APP-100**'
       '（SHA `219ef841…`／308 340 B）⇒ 无编号更大的新条目）｜**本轮修掉 6 处 git 半交付**'
       '（STATUS 引用的归档件／证据产物在磁盘上却从没进过 git ⇒ 换 clone 即断链）'
       '＋ **新增「git 半交付」判据**（**稳态 185 行／0 FAIL／反证 3/3**）｜'
       '**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未占设备**｜'
       '结果见 §179 归档件（§179 是对 §178「判据 177 行」这一**自指快照数字**的勘误；'
       '§178 的结论与 6 处修复本身全部成立）')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    corr_before = open(CORR, 'rb').read()
    text = open(STATUS, 'rb').read().decode('utf-8')

    # ── 唯一命中断言 ───────────────────────────────────────────────────
    n = text.count(OLD)
    if n != 1:
        print('ABORT: 目标串出现 %d 次（要求恰好 1 次）⇒ 源文件零改动' % n)
        return 1
    new_text = text.replace(OLD, NEW, 1)

    # ── 头部必须同时引用最新章节 §179（§173 判据 H1 的口径）─────────────
    ct = re.search(r'(?m)^当前任务: (.*)$', new_text).group(1)
    if '§179' not in ct:
        print('ABORT: 新的「当前任务」行未引用 §179 ⇒ 源文件零改动')
        return 1

    nb = new_text.encode('utf-8')
    checks = [
        ('bytes<=40000', len(nb) <= 40000, str(len(nb))),
        ('lines<=300', nb.count(b'\n') + 1 <= 300, str(nb.count(b'\n') + 1)),
        ('no CRLF', nb.count(b'\r\n') == 0, str(nb.count(b'\r\n'))),
        ('CORR untouched', sha(open(CORR, 'rb').read()) == sha(corr_before), ''),
        ('sections kept', len(re.findall(r'(?m)^## §', new_text)) == 24,
         str(len(re.findall(r'(?m)^## §', new_text)))),
        ('only header changed', new_text.count('当前任务:') == 1, ''),
        ('§178/§179 blocks intact',
         '## §178 ' in new_text and '## §179 ' in new_text, ''),
    ]
    bad = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print('  %-22s %s %s' % (name, 'OK' if ok else 'FAIL', detail))
    if bad:
        print('ABORT: 写前自检未过 ⇒ 源文件零改动')
        return 1

    with io.open(STATUS, 'wb') as f:
        f.write(nb)
    print('WROTE %s (%d B)' % (STATUS, len(nb)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
