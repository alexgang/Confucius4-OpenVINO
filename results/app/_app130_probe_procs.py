#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130：列出**当前**所有 python 系进程（含命令行）⇒ 人工判断谁在干扰。"""
import ctypes
import ctypes.wintypes as w

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', w.DWORD), ('cntUsage', w.DWORD),
        ('th32ProcessID', w.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', w.DWORD), ('cntThreads', w.DWORD),
        ('th32ParentProcessID', w.DWORD), ('pcPriClassBase', ctypes.c_long),
        ('dwFlags', w.DWORD), ('szExeFile', w.WCHAR * 260),
    ]


def main():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateToolhelp32Snapshot.restype = w.HANDLE
    k.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR,
                                             ctypes.POINTER(w.DWORD)]

    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == w.HANDLE(-1):
        print('snapshot failed', ctypes.get_last_error())
        return 1
    pe = PROCESSENTRY32W()
    pe.dwSize = ctypes.sizeof(pe)
    rows = []
    ok = k.Process32FirstW(snap, ctypes.byref(pe))
    while ok:
        name = pe.szExeFile
        if name.lower() in ('python.exe', 'pythonw.exe', 'python3.exe'):
            h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False,
                              pe.th32ProcessID)
            path = ''
            if h:
                buf = ctypes.create_unicode_buffer(1024)
                sz = w.DWORD(1024)
                if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz)):
                    path = buf.value
                k.CloseHandle(h)
            rows.append((pe.th32ProcessID, name, path))
        ok = k.Process32NextW(snap, ctypes.byref(pe))
    k.CloseHandle(snap)
    print('python 系进程：%d 个' % len(rows))
    for pid, name, path in rows:
        print('  pid=%-7d %-12s %s' % (pid, name, path))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
