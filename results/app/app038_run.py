#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-038 运行器：**持共享机器锁**跑 `app038_tts_f16_probe.py`。

🔴 为什么单独一个运行器：
   探针本身要占 GPU 做编译（污染其它模块的计时）⇒ 必须持锁；
   而探针脚本是纯测量脚本（`import openvino`），不适合把锁逻辑塞进去。
   ⇒ 锁逻辑放这里，探针保持可单跑。

用法（必须用**客户包**的 python，才有 openvino）：
   `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.5\\python\\python.exe`
   `results/app/app038_run.py`
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"

sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from machine_lock_app import LockHeld          # noqa: E402

import app038_tts_f16_probe as probe           # noqa: E402


def main() -> int:
    with LockHeld(module='app', timeout=1800, poll=20.0,
                  verbose=True) as lk:
        print('[lock] 已持锁：%r' % (lk.payload,), flush=True)
        try:
            return probe.main()
        finally:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
