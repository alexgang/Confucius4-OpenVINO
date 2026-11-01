#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""打包 v2.2 的后台启动包装器：先把自己的 PID 落盘（供 session_lease addpid 用）。

🔴 `--no-shortcut`：APP-061 明确「用户抽听以后才能改桌面快捷方式」
   ⇒ 打完包**不动**桌面 .lnk。
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
with open(os.path.join(HERE, '_pack_v22.pid'), 'w', encoding='ascii') as f:
    f.write(str(os.getpid()))
sys.argv = [
    os.path.join(REPO, 'pack_v13.py'),
    '--version', '2.2',
    '--pkg', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.2',
    '--no-shortcut',
    # 🔴 APP-061 轮：安静窗口的阻塞源 = **用户自己正在测试的 v2.1 会话**
    #   （PID 14712 = v2.1 的 app GUI；它不是别的模块的**计时作业**）
    #   ⇒ 本打包**全程持共享机器锁** ⇒ 别的模块的计时作业会**排队**而非并发
    #     ⇒ 不会污染任何计时；且打包只吃 CPU/磁盘，**不占 NPU/GPU**
    #     ⇒ 不可能干扰别处的**设备级**测量。
    '--skip-quiet',
]
runpy.run_path(sys.argv[0], run_name='__main__')
