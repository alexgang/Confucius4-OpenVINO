# -*- coding: utf-8 -*-
"""app134 持锁运行器 —— 取共享机器锁 ⇒ 跑验收 ⇒ 释放锁。

🔴 纪律（§「机器锁与计时」）：
  - 计时/测速作业**必须**持锁；
  - 锁已存在 ⇒ **等**（不抢不删）；
  - 回收锁前必须 **ctypes `OpenProcess` + `GetExitCodeProcess`** 确认 PID 真死，
    探测失败 ⇒ 视为存活；
  - 等锁期间**不得**反复「创建 tmp + 删除 tmp」（会触发批量删除保护）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, REPO)

import machine_lock_app as ml  # noqa: E402

PY312 = r'C:\Users\Trekker-PTL\AppData\Local\Programs\Python\Python312\python.exe'
SCRIPT = os.path.join(HERE, 'app134_app036c_telemetry.py')


def main():
    print('取锁中……')
    # 🔴 `acquire()` 返回 **(ok, payload)** —— payload 是释放锁时**必须**的
    #   （`release()` 只删「内容与自己那份完全一致」的文件 ⇒ 漏了 payload
    #   ⇒ 锁删不掉 ⇒ 残留成孤儿锁）。
    ok, payload = ml.acquire(module='app-app134', timeout=1800, poll=20.0,
                             verbose=True)
    if not ok:
        print('❌ 未取到锁 ⇒ 退出（不抢不删）')
        return 2
    print('✅ 已持锁，开始跑验收……')
    t0 = time.perf_counter()
    rc = 1
    try:
        r = subprocess.run([PY312, SCRIPT], cwd=REPO)
        rc = r.returncode
    finally:
        print('用时 %.1f s ⇒ 释放锁' % (time.perf_counter() - t0))
        try:
            done = ml.release(payload)
            print('释放锁：%s' % ('成功' if done else '**失败**（需人工确认）'))
        except Exception as e:
            print('释放锁异常：%s（**必须人工确认**）' % e)
    return rc


if __name__ == '__main__':
    sys.exit(main())
