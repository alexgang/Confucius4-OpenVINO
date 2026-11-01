#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app199_run_with_lock.py —— 【APP-054 ③】持共享机器锁跑 A/B 两臂。

🔴 **纪律**：
  * 计时/测速作业**必须**持 `shared/MACHINE_LOCK`（模块名 `app`）；
  * 锁已存在 ⇒ **等待**（`machine_lock_app.acquire` 内建 fail-closed 逻辑）；
  * 结束后**释放**锁；
  * **两臂在同一次持锁会话内连续跑** ⇒ 比值不受 solo 跨会话漂移（±5%）影响。

用法：
    python results/app/_app199_run_with_lock.py
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

import machine_lock_app as MLA  # noqa: E402


def main():
    script = os.path.join(HERE, 'app199_app054_ab_run.py')
    ok, payload = MLA.acquire(module='app', timeout=3600, poll=20.0,
                              verbose=True)
    if not ok:
        print('[ab] 未取得机器锁 ⇒ 放弃本轮（不抢锁）')
        return 2
    print('[ab] 已取得机器锁：%s' % payload)
    try:
        proc = subprocess.run([sys.executable, script],
                              cwd=REPO)
        rc = proc.returncode
    finally:
        MLA.release(payload, verbose=True)
    print('[ab] A/B 完成 rc=%s，锁已释放' % rc)
    return rc


if __name__ == '__main__':
    sys.exit(main())
