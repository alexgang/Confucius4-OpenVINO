#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app214 后台启动包装器：先把自己的 PID 落盘（供 session_lease addpid 用），再跑正题。

用法：
    .venv\\Scripts\\python.exe results\\app\\_app214_launch.py
"""
from __future__ import annotations

import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
TARGET = os.path.join(HERE, 'app214_app057_v20_clean_test.py')
PID_FILE = os.path.join(HERE, '_app214.pid')

with open(PID_FILE, 'w', encoding='ascii') as f:
    f.write(str(os.getpid()))

sys.argv = [
    TARGET,
    '--zip', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1.zip',
    # 🔴 **用全新空目录**：上一轮残留的 `C:\v20_cleantest` 里有 10 382 个半解压文件，
    #    直接沿用会扫到「zip 里根本没有的文件」⇒ 口径失真。
    #    而 `shutil.rmtree` 那个旧目录会触发批量删除保护 ⇒ 干脆换新路径。
    '--clean', r'C:\v20_cleantest_v3',
    '--json', os.path.join(HERE, 'app214_app057_v20_clean_test_evidence.json'),
]
runpy.run_path(TARGET, run_name='__main__')
