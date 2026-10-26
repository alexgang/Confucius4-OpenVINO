#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_error_isolation_pkg.py —— 对**客户包内那份** `tts_service.py`
单独跑 §22 的同一套断言。

🔴 铁律：「仓库里测过」≠「包里的那份是对的」
⇒ §22 的修复必须**对包内那份单独跑同一套断言**（本脚本）。

做法：把 `sys.path` 指向**客户包 app 目录**（而不是仓库 `live_caption/`），
再 import `tts_service` ⇒ 被测的就是包内那份文件。

用法
----
    python results/app/test_tts_error_isolation_pkg.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
import sys as _sys
_sys.path.insert(0, r'C:\Users\Trekker-PTL\confucius4-openvino')
import pkg_paths as _pkg_paths
# 🔴🔴 §48：**不写死包版本** ⇒ 自动发现最大版本（`pkg_paths` 单一数据源）
PKG = _pkg_paths.pkg_app_dir()

if not os.path.isdir(PKG):
    print(f'!! 找不到客户包 app 目录：{PKG}')
    sys.exit(2)

# 🔴 关键：**只**把客户包 app 目录放进 path，且**不放**仓库 live_caption
#    （否则会 import 到仓库那份，等于没测包）。
sys.path.insert(0, PKG)

import tts_service  # noqa: E402

imported = os.path.abspath(tts_service.__file__)
print('=' * 72)
print(f'§22 验收（**客户包内那份**）：{imported}')
print('=' * 72)
if os.path.abspath(PKG) not in os.path.abspath(imported):
    print('!! 导入的不是包内文件 ⇒ 测无效，中止')
    sys.exit(2)

# 复用主验收脚本的用例逻辑（同一套断言）
sys.path.insert(0, HERE)
import test_tts_error_isolation as t  # noqa: E402

# 主脚本的 main() 用的是它自己 import 的 tts_service；
# 这里把主脚本模块里的 tts_service 指向**包内那份**。
t.tts_service = tts_service

rc = t.main()
print()
print(f'被测文件 SHA256 相关：包内 tts_service.py = {imported}')
sys.exit(rc)
