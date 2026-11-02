#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""回收**孤儿锁**（APP-064 / MEMORY §二 的「让锁要彻底让」）。

🔴 **纪律**：
   - 回收前**必须**用 ctypes `OpenProcess` 确认锁里的 PID **真死**
     （`err == 87` ⇒ 进程不存在 ⇒ 确认死 ⇒ 可回收）
   - **探测失败一律视为存活** ⇒ 不回收
   - **绝不手写 `tasklist /FI`**（Git Bash 下会被当路径 ⇒ 曾误回收他人活锁）
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

LOCK = os.path.join(os.path.expanduser('~'), 'shared', 'MACHINE_LOCK')
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259


def proc_alive(pid: int):
    """🔴 返回 (alive: bool, detail: str)。

    🔴 **探测失败 ⇒ 视为存活**（fail-closed）。
    """
    if pid <= 0:
        return True, 'PID 非法 ⇒ 视为存活'
    PROCESS_ALL_ACCESS = 0x1F0FFF
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        err = ctypes.get_last_error()
        if err == 87:          # ERROR_INVALID_PARAMETER ⇒ 进程不存在
            return False, 'OpenProcess err=87 ⇒ 进程不存在（确认死）'
        # 🔴 其它错误（权限等）⇒ **探测失败** ⇒ 视为存活
        return True, 'OpenProcess 失败 err=%d ⇒ 探测失败 ⇒ 视为存活' % err
    try:
        code = wt.DWORD()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        if not ok:
            return True, 'GetExitCodeProcess 失败 ⇒ 探测失败 ⇒ 视为存活'
        val = code.value
        if val == STILL_ACTIVE:
            return True, '进程仍活动（exit code %d）' % val
        return False, '进程已退出（exit code %d）' % val
    finally:
        k32.CloseHandle(h)


def main():
    if not os.path.exists(LOCK):
        print('锁文件不存在 ⇒ 无需回收')
        return 0
    with open(LOCK, 'rb') as f:
        raw = f.read()
    txt = raw.decode('utf-8', 'replace')
    print('锁内容：%r' % txt)
    pid = None
    for line in txt.splitlines():
        line = line.strip()
        if line.lower().startswith('pid:'):
            try:
                pid = int(line.split(':', 1)[1].strip())
            except Exception:
                pass
    if pid is None:
        print('[ABORT] 锁里没有可解析的 PID ⇒ **不回收**（fail-closed）')
        return 2
    alive, detail = proc_alive(pid)
    print('PID %d 探测：%s' % (pid, detail))
    if alive:
        print('[ABORT] 进程**仍活着**（或探测失败）⇒ **不回收锁**')
        return 2
    # 🔴 再等一会儿，确认不是「刚好在启动」
    time.sleep(3)
    alive2, detail2 = proc_alive(pid)
    if alive2:
        print('[ABORT] 3 s 后仍活着（%s）⇒ 不回收' % detail2)
        return 2
    os.remove(LOCK)
    print('✅ 已回收孤儿锁（PID %d 确认已死：%s）' % (pid, detail))
    return 0


if __name__ == '__main__':
    sys.exit(main())
