#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴 **fail-closed** 的孤儿 MACHINE_LOCK 回收（APP-064 纪律）。

## 铁律（MEMORY + APP-064）
* 锁**只**在**持有者 PID 确认已死**时才可回收；
* 死判据 = `ctypes OpenProcess` **err == 87**（ERROR_INVALID_PARAMETER
  ⇒ 该 PID 不存在）；
* **探测失败（err != 87 且拿不到 handle）⇒ 一律视为存活 ⇒ 拒绝回收**；
* 🔴 **绝不手写 `tasklist /FI`**（Git Bash 下会被当路径，曾误回收他人活锁）；
* 回收前还要核对：**锁内 `started` 与进程 StartTime 一致 ⇒ 活锁 ⇒ 不回收**。

## 用法
```
python _app239_reclaim_orphan_lock.py            # 只探测，不删
python _app239_reclaim_orphan_lock.py --reclaim  # 探测通过才删
```
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import datetime
import os
import re
import sys

LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE,
                                    ctypes.POINTER(wintypes.DWORD))
k32.GetProcessTimes.argtypes = (wintypes.HANDLE,
                                 ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME))


def probe(pid: int):
    """返回 ('ALIVE'|'DEAD'|'UNKNOWN', detail)。

    🔴 **fail-closed**：只有明确拿到 err==87 才判 DEAD。
    """
    h = k32.OpenProcess(0x1000, False, pid)      # PROCESS_QUERY_LIMITED_INFO
    if h:
        code = wintypes.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            k32.CloseHandle(h)
            return 'UNKNOWN', 'GetExitCodeProcess 失败'
        alive = (code.value == 259)               # STILL_ACTIVE
        # 进程创建时间（用于核对锁内 started）
        created = None
        ct = wintypes.FILETIME()
        et = wintypes.FILETIME()
        kt = wintypes.FILETIME()
        ut = wintypes.FILETIME()
        if k32.GetProcessTimes(h, ctypes.byref(ct), ctypes.byref(et),
                               ctypes.byref(kt), ctypes.byref(ut)):
            created = datetime.datetime.fromtimestamp(
                (ct.dwHighDateTime << 32 | ct.dwLowDateTime) / 1e7 - 11644473600)
        k32.CloseHandle(h)
        return ('ALIVE' if alive else 'DEAD'), (
            'exitcode=%d created=%s' % (code.value, created))
    err = ctypes.get_last_error()
    if err == 87:                                  # ERROR_INVALID_PARAMETER
        return 'DEAD', 'OpenProcess err=87（PID 不存在）'
    return 'UNKNOWN', 'OpenProcess err=%d（**探测失败 ⇒ 视为存活**）' % err


def main():
    reclaim = '--reclaim' in sys.argv
    if not os.path.isfile(LOCK):
        print('NO_LOCK ⇒ 无需回收')
        return 0
    with open(LOCK, 'rb') as f:
        raw = f.read().decode('utf-8', errors='replace')
    m = re.search(r'pid:\s*(\d+)', raw)
    if not m:
        print('锁文件里没有 pid ⇒ **无法判定** ⇒ 不动')
        return 2
    pid = int(m.group(1))
    ms = re.search(r'started:\s*([0-9\- :]+)', raw)
    lock_started = ms.group(1).strip() if ms else ''
    print('锁内容：')
    for line in raw.strip().splitlines():
        print('    %s' % line)
    print('持有者 PID = %d，锁内 started = %r' % (pid, lock_started))

    state, detail = probe(pid)
    print('探测：%s —— %s' % (state, detail))

    if state != 'DEAD':
        print('⇒ **不回收**（fail-closed：只有确认已死才可回收）')
        return 1

    # 🔴 二次核对：锁内 started 与进程创建时间一致 ⇒ 是同一进程 ⇒ 不该回收
    if 'created=' in detail:
        cm = re.search(r'created=(\S+ \S+)', detail)
        if cm and lock_started:
            try:
                lock_dt = datetime.datetime.strptime(
                    lock_started, '%Y-%m-%d %H:%M:%S')
                cre_dt = datetime.datetime.strptime(cm.group(1),
                                                   '%Y-%m-%d %H:%M:%S')
                if abs((lock_dt - cre_dt).total_seconds()) < 120:
                    print('⇒ 锁内 started 与进程创建时间一致（%s ≈ %s）'
                          ' ⇒ 疑似活锁 ⇒ **不回收**' % (lock_dt, cre_dt))
                    return 1
            except Exception as e:
                print('（时间比对跳过：%r）' % (e,))

    print('⇒ 持有者已死（err=87）且时间不匹配 ⇒ **孤儿锁**')
    if not reclaim:
        print('（dry-run：加 --reclaim 才真删）')
        return 0
    os.remove(LOCK)
    print('已删除孤儿锁：%s' % LOCK)
    return 0


if __name__ == '__main__':
    sys.exit(main())
