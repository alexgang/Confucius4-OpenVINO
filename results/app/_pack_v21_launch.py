#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包 v2.1 的后台启动包装器：先把自己的 PID 落盘（供 session_lease addpid 用）。"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
with open(os.path.join(HERE, '_pack_v21.pid'), 'w', encoding='ascii') as f:
    f.write(str(os.getpid()))
sys.argv = [
    os.path.join(REPO, 'pack_v13.py'),
    '--version', '2.1',
    '--pkg', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1',
]
runpy.run_path(sys.argv[0], run_name='__main__')
