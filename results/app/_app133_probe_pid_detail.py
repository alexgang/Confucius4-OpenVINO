# -*- coding: utf-8 -*-
"""app133 —— PID 38028 深度取证（ctypes 与进程表矛盾时的裁决）。

🔴 场景：`Get-Process` / `Get-CimInstance` 都说不存在，
   但 ctypes `OpenProcess` 成功 ⇒ **必须查清它到底是什么**，
   否则可能误回收**别人的活锁**（本项目历史上踩过）。

查：
   ① `QueryFullProcessImageNameW` ⇒ 可执行文件路径；
   ② `GetExitCodeProcess` ⇒ 退出码（259 = STILL_ACTIVE）；
   ③ `GetProcessTimes` ⇒ 创建/退出时间（与锁文件时间戳比对）；
   ④ `EnumProcesses` ⇒ 系统里到底有没有这个 PID。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, REPO)

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.OpenProcess.restype = wt.HANDLE
k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                           ctypes.POINTER(wt.DWORD)]
k32.GetProcessTimes.argtypes = [wt.HANDLE,
                                ctypes.POINTER(wt.FILETIME),
                                ctypes.POINTER(wt.FILETIME),
                                ctypes.POINTER(wt.FILETIME),
                                ctypes.POINTER(wt.FILETIME)]
k32.EnumProcesses = None
try:
    ps = ctypes.WinDLL('psapi', use_last_error=True)
    ps.EnumProcesses.argtypes = [ctypes.POINTER(wt.DWORD), wt.DWORD,
                                 ctypes.POINTER(wt.DWORD)]
    ps.EnumProcesses.restype = wt.BOOL
    _enum_proc = ps.EnumProcesses
except Exception:
    _enum_proc = None

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_QUERY_INFORMATION = 0x0400


def filetime_to_epoch(ft):
    return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7 - 11644473600.0


def enum_has_pid(pid):
    if _enum_proc is None:
        return None
    n = 4096
    arr = (wt.DWORD * n)()
    got = wt.DWORD(0)
    if not _enum_proc(arr, ctypes.sizeof(arr), ctypes.byref(got)):
        return None
    ids = [int(arr[i]) for i in range(got.value)]
    return pid in ids, len(ids)


def main():
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 38028
    out = {'pid': pid}

    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    out['openprocess_handle'] = bool(h)
    out['openprocess_err'] = ctypes.get_last_error()
    if h:
        code = wt.DWORD(0)
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        out['getexitcode_ok'] = bool(ok)
        out['exit_code'] = code.value
        out['still_active'] = (code.value == 259)

        buf = ctypes.create_unicode_buffer(1024)
        sz = wt.DWORD(1024)
        ok2 = k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
        out['image_ok'] = bool(ok2)
        out['image'] = buf.value if ok2 else None

        ct, et, kt, ut = (wt.FILETIME(), wt.FILETIME(), wt.FILETIME(),
                          wt.FILETIME())
        ok3 = k32.GetProcessTimes(h, ctypes.byref(ct), ctypes.byref(et),
                                  ctypes.byref(kt), ctypes.byref(ut))
        out['getprocesstimes_ok'] = bool(ok3)
        if ok3:
            out['create_epoch'] = filetime_to_epoch(ct)
            out['exit_epoch'] = filetime_to_epoch(et)
        k32.CloseHandle(h)

    in_enum, total = enum_has_pid(pid)
    out['enum_contains_pid'] = in_enum
    out['enum_total_pids'] = total

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
