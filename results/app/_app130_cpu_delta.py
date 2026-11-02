#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130：测指定 PID 的 **CPU 时间增量**（两次 `GetProcessTimes` 采样差）
⇒ 判断它**是否真的在算**（不是「常驻但不干活」）。
🔴 同时打印**命令行**（MEMORY：干扰进程要连命令行一起记录）。"""
import ctypes
import ctypes.wintypes as w
import sys
import time

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def cpu_times(pid):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.GetProcessTimes.argtypes = [w.HANDLE, ctypes.POINTER(w.FILETIME),
                                  ctypes.POINTER(w.FILETIME),
                                  ctypes.POINTER(w.FILETIME),
                                  ctypes.POINTER(w.FILETIME)]
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None, ctypes.get_last_error()
    c, e, kk, u = (w.FILETIME() for _ in range(4))
    if not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                             ctypes.byref(kk), ctypes.byref(u)):
        k.CloseHandle(h)
        return None, ctypes.get_last_error()
    k.CloseHandle(h)
    t = (c.dwHighDateTime << 32) | c.dwLowDateTime
    return t / 1e7, 0      # 100 ns → s


def cmdline(pid):
    import subprocess
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine"
             % pid], capture_output=True, text=True, errors='replace',
            timeout=30)
        return (out.stdout or '').strip()
    except Exception as e:
        return '<cmdline 读取失败: %s>' % e


def main():
    pids = [int(x) for x in sys.argv[1:]] or [4896]
    interval = 10.0
    for pid in pids:
        t0, err = cpu_times(pid)
        if t0 is None:
            print('pid=%-7d **进程不存在或不可读**（err=%d）' % (pid, err))
            continue
        cl = cmdline(pid)
        print('pid=%-7d cmdline=%s' % (pid, cl[:220]))
        time.sleep(interval)
        t1, err = cpu_times(pid)
        if t1 is None:
            print('pid=%-7d 第二次采样失败（err=%d）⇒ 进程已退出' % (pid, err))
            continue
        delta = t1 - t0
        print('           CPU 增量 = %.3f s / %.0f s ⇒ %s'
              % (delta, interval,
                 '🔴 **在算**' if delta > 0.5 else '✅ 常驻但不干活'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
