#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""等共享机器锁释放后，自动跑 C-111 端到端（真实翻译模型）。

为什么需要它：ASR-001 规定「计时或测速作业开始前先创建共享机器锁，
锁已经存在就等待」；TTS 模块长时间持锁 ⇒ 本脚本**排队等待**，
不抢锁、不干扰别的模块。

判定「锁可用了」的条件（与 diag_c111_e2e.acquire_lock 一致）：
  * 锁文件不存在；或
  * 锁里的 PID 已不在（孤儿锁）⇒ 交由 e2e 脚本自己回收
（锁早于开机时间的孤儿锁同样由 e2e 处理）

用法：python wait_and_run_e2e.py [最长等待秒数]
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
E2E = os.path.join(HERE, 'diag_c111_e2e.py')
LOG = r'C:\Users\Trekker-PTL\hy_bench\runs\c111_half\e2e.log'
MAX_WAIT = int(sys.argv[1]) if len(sys.argv) > 1 else 7200


def lock_state():
    """返回 (status, info)：'free' / 'held' / 'orphan'"""
    if not os.path.exists(LOCK):
        return 'free', ''
    info = {}
    try:
        with open(LOCK, encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    k, v = line.split(':', 1)
                    info[k.strip()] = v.strip()
    except Exception:
        pass
    pid = int(info.get('pid', '0') or 0)
    alive = False
    if pid:
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.windll.kernel32
            h = k32.OpenProcess(0x1000, False, pid)
            if h:
                code = wintypes.DWORD()
                k32.GetExitCodeProcess(h, ctypes.byref(code))
                k32.CloseHandle(h)
                alive = (code.value == 259)
        except Exception:
            alive = True          # 判不出来就当活着（保守，不抢）
    return ('held' if alive else 'orphan'), info


def main():
    t0 = time.time()
    print(f'[wait] 开始等待共享机器锁（最长 {MAX_WAIT}s）', flush=True)
    while time.time() - t0 < MAX_WAIT:
        st, info = lock_state()
        if st == 'free':
            print(f'[wait] 锁已释放 ⇒ 启动 e2e', flush=True)
            break
        if st == 'orphan':
            print(f'[wait] 孤儿锁（PID {info.get("pid")} 已不在）⇒ 启动 e2e '
                  f'（e2e 脚本会自行回收）', flush=True)
            break
        print(f'[wait] 锁被 {info.get("module", "?")} '
              f'(PID {info.get("pid")}) 持有 ⇒ 继续等待 '
              f'({int(time.time() - t0)}s)', flush=True)
        time.sleep(30)
    else:
        print('[wait] 等待超时，未运行 e2e', flush=True)
        return 2

    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    print(f'[wait] 运行: {E2E}  日志 → {LOG}', flush=True)
    with open(LOG, 'w', encoding='utf-8') as lf:
        p = subprocess.Popen([sys.executable, E2E], stdout=lf,
                             stderr=subprocess.STDOUT, cwd=HERE)
        rc = p.wait()
    print(f'[wait] e2e 结束，returncode={rc}', flush=True)
    return rc


if __name__ == '__main__':
    sys.exit(main())
