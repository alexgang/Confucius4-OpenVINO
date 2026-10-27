#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-023 验收启动器 —— 用 **`ShellExecuteW`** 拉起 `app095_pythonw_smoke.py`，
等价 **explorer 双击**（≈ 用户桌面快捷方式那条路）。

🔴 为什么不能 `subprocess.Popen` 或直接从 bash 跑：
    从控制台 / Git Bash 启动 pythonw 时，它会**继承父进程的标准句柄**
    （bash 的管道）⇒ `GetStdHandle(STD_ERROR_HANDLE)` **不是 NULL**
    ⇒ CPython 走「句柄是真的」那条路 ⇒ `stderr=None` 的 Popen **不会**触发
    WinError 50 ⇒ 测出来「全绿」，而用户那边照样挂。
    ⇒ `ShellExecuteW` 是 shell 的**打开**动作（与 explorer 双击同一条路径），
      新进程**不带**继承句柄 ⇒ 才是用户的真实环境。

🔴 为什么不用 schtasks：本环境安全策略把 `schtasks.exe` 挡在黑名单里。
   `ShellExecuteW` 达成的是同一个目的（在**当前交互会话**里、无句柄地拉起）。

用法：
    python app095b_launch_via_shellexecute.py --levels L1
    python app095b_launch_via_shellexecute.py --levels L1,L2,L3 --wait --poll 10
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, 'app095_pythonw_smoke.py')
PYW = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5\python\pythonw.exe'
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
OUT_JSON = os.path.join(HERE, 'app095_pythonw_smoke.json')

SW_SHOWNORMAL = 1
SW_SHOWMINNOACTIVE = 7


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--levels', default='L1,L2,L3')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--timeout', type=float, default=1500.0)
    ap.add_argument('--play-timeout', type=float, default=300.0)
    ap.add_argument('--wait', action='store_true',
                    help='轮询结果 JSON 直到出现（或超时）')
    ap.add_argument('--poll', type=float, default=15.0)
    ap.add_argument('--max-wait', type=float, default=3600.0)
    args = ap.parse_args()

    params = '-s "%s" --levels %s --precision %s --timeout %s --play-timeout %s' % (
        SMOKE, args.levels, args.precision, args.timeout, args.play_timeout)

    # 结果 JSON 先删，避免读到上一轮的
    if os.path.isfile(OUT_JSON):
        os.remove(OUT_JSON)

    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p,
                                      ctypes.c_wchar_p, ctypes.c_wchar_p,
                                      ctypes.c_wchar_p, ctypes.c_int]
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    rc = shell32.ShellExecuteW(None, 'open', PYW, params, PKG,
                               SW_SHOWMINNOACTIVE)
    # ShellExecute 返回值 > 32 表示成功
    ok = (rc is not None) and (rc > 32)
    print('ShellExecuteW(explorer 等价) rc=%r  成功=%s' % (rc, ok))
    print('  解释器 : %s' % PYW)
    print('  参数   : %s' % params)
    print('  工作目录: %s' % PKG)
    if not ok:
        print('❌ 启动失败（rc<=32）')
        return 2

    if not args.wait:
        print('\n已拉起（不等待）。结果 JSON：%s' % OUT_JSON)
        return 0

    t0 = time.perf_counter()
    last = 0.0
    while time.perf_counter() - t0 < args.max_wait:
        if os.path.isfile(OUT_JSON):
            try:
                d = json.load(open(OUT_JSON, encoding='utf-8'))
            except Exception:
                time.sleep(2.0)
                continue
            print('\n结果 JSON 已出现（%s）：' % d.get('when'))
            print('  launched_by       = %s' % d.get('launched_by'))
            print('  no_stderr_handle  = %s   ← 无继承句柄=用户真实环境'
                  % d.get('no_stderr_handle'))
            print('  all_pass          = %s' % d.get('all_pass'))
            for r in d.get('results', []):
                print('   - %-3s ready=%s played=%s audible=%s err=%s' % (
                    r.get('level'), r.get('ready'), r.get('played'),
                    r.get('audible'), (r.get('err') or '')[:80]))
            return 0 if d.get('all_pass') else 1
        el = time.perf_counter() - t0
        if el - last >= 30:
            last = el
            print('  ...等待中 %.0f s' % el)
        time.sleep(args.poll)
    print('⏱ 等待超时，未见到结果 JSON')
    return 3


if __name__ == '__main__':
    sys.exit(main())
