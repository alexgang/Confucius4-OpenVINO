# -*- coding: utf-8 -*-
"""修 `_app402d_final_check.py` 里被 heredoc 弄坏的 `\\n` 转义。"""
import os

P = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app402d_final_check.py'
s = open(P, encoding='utf-8').read()

BAD = ("        heads = [l for l in body.split('\n') if l.startswith('## §')]")
GOOD = ("        heads = [l for l in body.splitlines() if l.startswith('## §')]")

if BAD in s:
    s = s.replace(BAD, GOOD, 1)
    print('fixed escaped-newline literal')
else:
    # 已被写成真正的换行 ⇒ 改回去
    BROKEN = ("        heads = [l for l in body.split('\n') if l.startswith('## §')]")
    assert BROKEN in s, '未找到待修复片段'
    s = s.replace(BROKEN, GOOD, 1)
    print('fixed broken literal')

open(P, 'w', encoding='utf-8', newline='\n').write(s)
import ast
ast.parse(s)
print('AST OK')
