#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-119 §3 臂 2 补测：all-NPU 组合的「进程内存」采样**。

reviewer 原文（APP-119 §3 臂 2）：
> 「另外记录 **NPU 编译时间**和**进程内存**。」

🔴 **为什么要单独再跑一次**：已有的 allnpu 臂（`run20261121-033422`）的验收脚本
**不采进程内存** ⇒ 这一项**没有数字** ⇒ 「没落盘的东西不能写『已交付』」
⇒ 本脚本**重跑同一条臂**（同一验收脚本、同一 600 s 片段、同一 ASR=NPU/MT=NPU/TTS=NPU），
**并发**采「包内 python 进程的工作集（Working Set）」⇒ 补上这一项。

## 采什么

  * **包内 python 进程** = 映像路径含 `Confucius4_LiveCaption_v2.5\\python\\python.exe`
    的全部进程（CLI 主进程 ＋ TTS worker ＋ 其子进程）；
  * 每次采样读 `PROCESS_MEMORY_COUNTERS.WorkingSetSize`（**工作集**，Windows 口径）
    ⇒ 取**各进程之和**与**单进程峰值**，全程记 **峰值**与**采样点数**。

## 纪律

  * **只读采样**（不写包、不改产品代码）；
  * 采样**不持有 MACHINE_LOCK**（只读进程计数器，不占设备）
    ⇒ 但**必须与验收臂串行**（同一台机，避免污染 RTF）；
  * 证据落盘 `results/app/app119_allnpu_memprobe.json`；
  * 结束后把内存数据**合并**进 `app119_allnpu_summary.json` 的 `mem_probe` 字段。
"""
import ctypes
import datetime
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
# 🔴 位置无关：脚本放在 live_caption/ 或 results/app/ 都能定位仓库根
REPO = HERE if os.path.isdir(os.path.join(HERE, 'results')) else     os.path.dirname(HERE)
RES = os.path.join(REPO, 'results', 'app')
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5'
PKG_PY_MARK = os.path.join(PKG, 'python', 'python.exe').lower()
LEASE = r'C:\Users\Trekker-PTL\shared\tools\session_lease.py'
TOKEN = '3579d2f8'

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

# 🔴 `EnumProcesses` 在 **psapi.dll**（kernel32 里没有）
psapi.EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD),
                                ctypes.POINTER(wintypes.DWORD),
                                wintypes.DWORD]
psapi.EnumProcesses.restype = wintypes.BOOL
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.OpenProcess.restype = wintypes.HANDLE
k32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
    ctypes.POINTER(wintypes.DWORD)]


class PMC(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD),
                ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE,
                                       ctypes.POINTER(PMC), wintypes.DWORD]


class PEE(ctypes.Structure):
    """🔴 `PROCESSENTRY32W`（Toolhelp32 快照用）。"""
    _fields_ = [('dwSize', wintypes.DWORD),
                ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD),
                ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', wintypes.LONG),
                ('dwFlags', wintypes.DWORD),
                ('szExeFile', wintypes.WCHAR * 260)]


k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PEE)]
k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PEE)]


def _all_pids():
    """🔴 枚举全部进程 PID。

    🔴 **`EnumProcesses` 在本机失败**（实测 `ok=0`／`err=998 ERROR_NOT_ENOUGH_MEMORY`
    ⇒ 返回 **0 个 PID** ⇒ 采样恒为 0 ⇒ 第一轮补测**采不到任何样本**）
    ⇒ **改用 `CreateToolhelp32Snapshot`**：实测可遍历 **335** 个进程 ⇒ 可靠。
    """
    TH32CS_SNAPPROCESS = 0x00000002
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return []
    out = []
    try:
        pe = PEE()
        pe.dwSize = ctypes.sizeof(PEE)
        if k32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                out.append((int(pe.th32ProcessID), pe.szExeFile))
                if not k32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        k32.CloseHandle(snap)
    return out


def pkg_python_pids():
    """返回**包内 python 进程**的 [(pid, 映像路径, 工作集字节)]。"""
    out = []
    for pid, _exe in _all_pids():
        if 'python' not in (_exe or '').lower():
            continue
        h = k32.OpenProcess(0x1000 | 0x0010, False, pid)   # QUERY_INFO|VM_READ
        if not h:
            continue
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                path = buf.value
                if path.lower() == PKG_PY_MARK:
                    c = PMC()
                    c.cb = ctypes.sizeof(PMC)
                    if psapi.GetProcessMemoryInfo(h, ctypes.byref(c),
                                                  ctypes.sizeof(PMC)):
                        out.append((pid, path, int(c.WorkingSetSize)))
        finally:
            k32.CloseHandle(h)
    return out


def main():
    arm = sys.argv[1] if len(sys.argv) > 1 else 'allnpu'
    run_id = sys.argv[2] if len(sys.argv) > 2 else time.strftime('%Y%m%d-%H%M%S')
    out = {'app': 'APP-119', 'arm': arm, 'run_id': run_id,
           'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'pkg_py_mark': PKG_PY_MARK, 'samples': []}

    cmd = [sys.executable, os.path.join(RES, '_app119_run_arm.py'),
           '--arm', arm, '--lang', 'zh', '--run-id', run_id,
           '--note', 'APP-119 臂2 补测进程内存（并行采样）']
    print('[mem] 起：%s' % ' '.join(cmd), flush=True)
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=RES)

    peak_sum = 0
    peak_single = 0
    n_samples = 0
    seen_pids = set()
    try:
        while p.poll() is None:
            procs = pkg_python_pids()
            if procs:
                s = sum(w for _pid, _path, w in procs)
                mx = max(w for _pid, _path, w in procs)
                peak_sum = max(peak_sum, s)
                peak_single = max(peak_single, mx)
                seen_pids.update(pid for pid, _p, _w in procs)
                out['samples'].append({
                    't': round(time.time() - t0, 1),
                    'n_proc': len(procs),
                    'sum_ws_mib': round(s / 1048576.0, 1),
                    'max_ws_mib': round(mx / 1048576.0, 1),
                })
                n_samples += 1
            time.sleep(5.0)
    finally:
        rc = p.wait()

    out['rc'] = rc
    out['n_samples'] = n_samples
    out['peak_sum_ws_mib'] = round(peak_sum / 1048576.0, 1)
    out['peak_single_proc_ws_mib'] = round(peak_single / 1048576.0, 1)
    out['pids_seen'] = sorted(seen_pids)
    out['elapsed_s'] = round(time.time() - t0, 1)
    out['note'] = ('工作集（Working Set）＝ Windows 口径；峰值取自 %d 次采样；'
                   '采样期间不持有 MACHINE_LOCK（只读计数器）。' % n_samples)
    with open(os.path.join(RES, 'app119_allnpu_memprobe.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in out.items() if k != 'samples'},
                     ensure_ascii=False, indent=1), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
