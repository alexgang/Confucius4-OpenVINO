#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app468_fix_h1b.py —— 定点修 §173 判据 H1（第二次）：头部须引最新章节 §180。

🔴 同时修掉头部里 §180 已撤回的措辞：「**稳态 185 行**」⇒ 改为**只引用不变量**
   （`FAIL=0`／反据 3/3）——§180 的结论：行数是观察量、不是定值。

纪律：唯一命中断言 ＋ 只改这一行 ＋ 旧章节正文一字不动 ＋ CORR 只读。
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

OLD = ('＋ **新增「git 半交付」判据**（**稳态 185 行／0 FAIL／反证 3/3**）｜'
       '**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未占设备**｜'
       '结果见 §179 归档件（§179 是对 §178「判据 177 行」这一**自指快照数字**的勘误；'
       '§178 的结论与 6 处修复本身全部成立）')

NEW = ('＋ **新增「git 半交付」判据**（**不变量：`FAIL=0`／`MISSING=0`／反证 3/3**；'
       '审计行数是**观察量、非定值** ⇒ §180 已撤回「行数＝稳态真值」的措辞）｜'
       '**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax／未占设备**｜'
       '结果见 §180 归档件（§179／§180 两节是把「自指数字」这一**概念错误**连根拔除：'
       '**只引用不变量**；§178 的结论与 6 处修复本身全部成立）')


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main():
    corr_before = open(CORR, 'rb').read()
    text = open(STATUS, 'rb').read().decode('utf-8')

    n = text.count(OLD)
    if n != 1:
        print('ABORT: 目标串出现 %d 次（要求恰好 1 次）⇒ 源文件零改动' % n)
        return 1
    new_text = text.replace(OLD, NEW, 1)

    ct = re.search(r'(?m)^当前任务: (.*)$', new_text).group(1)
    if '§180' not in ct:
        print('ABORT: 新的「当前任务」行未引用 §180 ⇒ 源文件零改动')
        return 1
    if '稳态' in ct:
        print('ABORT: 头部仍含 §180 已撤回的「稳态」措辞 ⇒ 源文件零改动')
        return 1

    nb = new_text.encode('utf-8')
    checks = [
        ('bytes<=40000', len(nb) <= 40000, str(len(nb))),
        ('lines<=300', nb.count(b'\n') + 1 <= 300, str(nb.count(b'\n') + 1)),
        ('no CRLF', nb.count(b'\r\n') == 0, str(nb.count(b'\r\n'))),
        ('CORR untouched', sha(open(CORR, 'rb').read()) == sha(corr_before), ''),
        ('sections kept', len(re.findall(r'(?m)^## §', new_text)) == 25,
         str(len(re.findall(r'(?m)^## §', new_text)))),
        ('only header changed', new_text.count('当前任务:') == 1, ''),
        ('§180 block intact', '## §180 ' in new_text, ''),
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
