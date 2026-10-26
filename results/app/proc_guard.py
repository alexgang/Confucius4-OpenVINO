#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""proc_guard.py — 计时作业的**安静窗口闸门**（纯 ctypes，无第三方依赖）。

## 为什么需要它

🔴🔴 **实测教训（2026-10-26，APP-062）**：
同一脚本、同一配置、连续两跑，A 臂单句 RTF 中位 **2.284 → 3.256**
（差 **1.43×**）⇒ 原因：**ASR 模块的 `p3_ov_app.py --device NPU` 在并发跑**，
而且**它不持机器锁** ⇒ 共享锁**挡不住**不持锁的模块作业。

⇒ 铁律（与「共享锁 fail-closed」互补）：
- **共享锁**管的是「**持锁方之间**的互斥」；
- **安静窗口闸门**管的是「**不持锁的作业**」的污染。

## 为什么不用现成工具

| 工具 | 实测结果 | 判定 |
|---|---|---|
| `wmic process get CommandLine` | **返回空** | ❌ **假阴性**（最危险） |
| `tasklist` | 只有镜像名，无命令行 | ❌ 判据不够 |
| `psutil` | 好用 | ⚠️ **客户包 python 里没有**（不能进产品路径） |

⇒ 这里用 **ctypes 走 Windows API**（PEB → RTL_USER_PROCESS_PARAMETERS
→ CommandLine），**零第三方依赖** ⇒ 客户包 python 可直接用。

## 🔴🔴 三个必须踩对的坑（本次实测踩了两次）

| # | 坑 | 后果 |
|---|---|---|
| ① | `PROCESS_BASIC_INFORMATION` **漏了 4 字节 padding**（`ExitStatus` 是 LONG(4)，后面要 4 字节对齐） | `PebBaseAddress` 读成 `None` ⇒ 全体假阴性 |
| ② | `OpenProcess` 权限掩码只给 `PROCESS_QUERY_LIMITED_INFORMATION`(0x1000) | `ReadProcessMemory` 失败（读 PEB 需要 `PROCESS_VM_READ`=0x10） |
| ③ | ctypes 函数**不显式设 `argtypes`/`restype`** | `HANDLE` 被截断成 32 位 ⇒ 静默失败 ⇒ 假阴性 |

⇒ **判据必须自检**：读不到命令行 ≠ 进程不存在。
⇒ 本模块提供 `self_test()`，**闸门启动时必须先跑一次自检**。

## 🔴「等锁进程」不算作业

安静窗口的判据要排除「**正在等锁**的进程」：它 CPU 增量 ≈ 0，只是排队。
⇒ 判据 = **两次采样相隔 `poll_s`，CPU 增量 ≥ 阈值** ⇒ 视为真在干活。
（否则「等锁的进程」会把闸门和自己变成死锁。）

## 用法

```python
from proc_guard import QuietGate
g = QuietGate()
if g.wait_quiet(max_wait_s=1800, poll_s=12):
    ...  # 安静窗口达成，可以开始计时
else:
    ...  # 没等到 ⇒ 数据可能受污染，必须在报告里写明
```
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes

# ── Win32 常量 ──────────────────────────────────────────────────────────
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = -1

# 🔴 这些命令行片段 = 「会跟本实验抢 NPU/GPU/CPU」的作业。
# ⚠️ **按命令行判据，不按进程名**（所有推理作业都是 python.exe）。
JOB_MARKERS = (
    'p3_ov_app.py',            # ASR NPU 推理（实测污染源）
    'p3_run_with_lock.py',
    'wait_and_build',          # ASR 的等待包装器（本身不算作业，但它的子进程算）
    'own20_step_probe.py',     # TTS 模块探针
    'run_matrix',
    'bench_',
    'eval_',
    'diag_',
)

# 🔴 CPU 增量阈值（秒）：低于它 = 等锁/空转 ⇒ 不算作业
CPU_DELTA_ACTIVE = 0.5


def _init_api():
    k = ctypes.windll.kernel32
    n = ctypes.windll.ntdll
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.ReadProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    k.ReadProcessMemory.restype = wintypes.BOOL
    k.GetProcessTimes.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p]
    k.GetProcessTimes.restype = wintypes.BOOL
    k.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    k.Process32FirstW.restype = wintypes.BOOL
    k.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    k.Process32NextW.restype = wintypes.BOOL
    n.NtQueryInformationProcess.argtypes = [
        wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p,
        ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    n.NtQueryInformationProcess.restype = ctypes.c_long
    return k, n


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD),
                ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', wintypes.DWORD),
                ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', wintypes.DWORD),
                ('szExeFile', wintypes.WCHAR * 260)]


class _PROCESS_BASIC_INFORMATION(ctypes.Structure):
    # 🔴🔴 **Pad 是必须的**：ExitStatus 是 LONG(4)，后面指针要 8 字节对齐
    #    ⇒ 少这 4 字节 ⇒ PebBaseAddress 读成 None ⇒ **全体假阴性**。
    _fields_ = [('ExitStatus', wintypes.LONG),
                ('Pad', ctypes.c_uint),
                ('PebBaseAddress', ctypes.c_void_p),
                ('AffinityMask', ctypes.c_void_p),
                ('BasePriority', ctypes.c_void_p),
                ('UniqueProcessId', ctypes.c_void_p),
                ('InheritedFromUniqueProcessId', ctypes.c_void_p)]


class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [('Length', wintypes.USHORT),
                ('MaximumLength', wintypes.USHORT),
                ('Buffer', ctypes.c_void_p)]


class _FILETIME(ctypes.Structure):
    _fields_ = [('dwLowDateTime', wintypes.DWORD),
                ('dwHighDateTime', wintypes.DWORD)]


def read_cmdline(pid: int) -> str:
    """读进程命令行（读不到就返回空串——**不要**当成「进程不存在」）。"""
    k, n = _init_api()
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ,
                      False, pid)
    if not h:
        return ''
    try:
        pbi = _PROCESS_BASIC_INFORMATION()
        ret = ctypes.c_ulong()
        status = n.NtQueryInformationProcess(
            h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(ret))
        if status != 0 or not pbi.PebBaseAddress:
            return ''
        # PEB.ProcessParameters（x64 0x20 / x86 0x10）
        # RTL_USER_PROCESS_PARAMETERS.CommandLine（x64 0x70 / x86 0x40）
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            pp_off, cmd_off = 0x20, 0x70
        else:
            pp_off, cmd_off = 0x10, 0x40
        n_read = ctypes.c_size_t(0)
        params = ctypes.c_void_p()
        if not k.ReadProcessMemory(
                h, ctypes.c_void_p(pbi.PebBaseAddress + pp_off),
                ctypes.byref(params), ctypes.sizeof(params),
                ctypes.byref(n_read)):
            return ''
        us = _UNICODE_STRING()
        if not k.ReadProcessMemory(
                h, ctypes.c_void_p(params.value + cmd_off), ctypes.byref(us),
                ctypes.sizeof(us), ctypes.byref(n_read)):
            return ''
        cnt = us.Length // 2
        if cnt <= 0 or cnt > 32768:
            return ''
        buf = ctypes.create_unicode_buffer(cnt)
        if not k.ReadProcessMemory(h, ctypes.c_void_p(us.Buffer), buf,
                                  us.Length, ctypes.byref(n_read)):
            return ''
        return buf.value
    except Exception:
        return ''
    finally:
        k.CloseHandle(h)


def cpu_time_s(pid: int) -> float:
    """进程**已用 CPU 时间**（秒）= kernel + user。

    🔴🔴 **参数顺序陷阱**：`GetProcessTimes(h, lpCreationTime, lpExitTime,
    lpKernelTime, lpUserTime)` ⇒ **第 1 个是「创建时间」，不是 CPU 时间**！
    ⇒ 误用会得到一个 ~1.3e10 秒的荒谬数（= 创建时间戳）。
    ⇒ CPU 时间只取 **kernel + user**。
    """
    k, _ = _init_api()
    h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return 0.0
    try:
        c, e, kk, u = (_FILETIME(), _FILETIME(), _FILETIME(), _FILETIME())
        if not k.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                 ctypes.byref(kk), ctypes.byref(u)):
            return 0.0

        def _t(ft):
            return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7
        return _t(kk) + _t(u)
    except Exception:
        return 0.0
    finally:
        k.CloseHandle(h)


def list_python_jobs(markers=JOB_MARKERS, exclude_self=True):
    """列出「像推理作业」的 python 进程（按**命令行**判定）。"""
    k, _ = _init_api()
    me = os.getpid()
    out = []
    snap = k.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE or not snap:
        return out
    try:
        pe = _PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        if k.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                pid = pe.th32ProcessID
                name = pe.szExeFile or ''
                if name.lower() in ('python.exe', 'pythonw.exe') and \
                        not (exclude_self and pid == me):
                    cmd = read_cmdline(pid)
                    low = (cmd or '').lower()
                    if any(mk in low for mk in markers):
                        out.append({'pid': pid, 'cmd': cmd[:400],
                                    'cpu_s': round(cpu_time_s(pid), 2)})
                if not k.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        k.CloseHandle(snap)
    return out


class QuietGate:
    """安静窗口闸门：等到「没有别的活跃推理作业」为止。"""

    def __init__(self, markers=JOB_MARKERS, cpu_delta_active=CPU_DELTA_ACTIVE,
                 on_log=print):
        self.markers = tuple(markers)
        self.cpu_delta_active = cpu_delta_active
        self.on_log = on_log

    def self_test(self):
        """🔴 闸门**启动前必须自检**：确认「能读到命令行」。

        ⚠️ 读不到 ≠ 没有作业。必须先证明机制有效，才敢用它做判据。
        """
        me = os.getpid()
        cmd = read_cmdline(me)
        ok = bool(cmd)
        self.on_log('[gate] 自检：读自己(%d)的命令行 = %s'
                    % (me, 'OK' if ok else '**失败**'))
        if not ok:
            self.on_log('[gate] 🔴 闸门**不可用**（读不到命令行）'
                        '⇒ 本次测量**不能**声称「无污染」')
        return ok

    def _active_jobs(self, snap1, snap2):
        """snap1/snap2 都是 `{pid: job_dict}` ⇒ 这里要遍历 **values()**。

        🔴 踩过的坑：直接 `for j in snap2` 迭代出的是 **key（int）**
        ⇒ `j['pid']` 报「int object is not subscriptable」。
        """
        active = []
        for j in snap2.values():
            cpu0 = snap1.get(j['pid'], {}).get('cpu_s', j['cpu_s'])
            delta = round(j['cpu_s'] - cpu0, 2)
            j['cpu_delta'] = delta
            # 🔴 CPU 增量 ≈ 0 ⇒ 等锁/空转 ⇒ 不算作业
            if delta >= self.cpu_delta_active:
                active.append(j)
        return active

    def wait_quiet(self, max_wait_s=1800.0, poll_s=12.0,
                   require_two_rounds=True, skip=False):
        """等安静窗口。返回 True = 达成。"""
        if skip:
            self.on_log('[gate] ⚠️ **跳过安静窗口**（--skip-quiet）'
                        '⇒ 本次数据**可能受污染**，必须在报告里写明理由')
            return False
        t0 = time.time()
        clean = 0
        need = 2 if require_two_rounds else 1
        while time.time() - t0 < max_wait_s:
            snap1 = {j['pid']: j for j in
                     list_python_jobs(self.markers)}
            time.sleep(poll_s)
            snap2 = {j['pid']: j for j in
                     list_python_jobs(self.markers)}
            active = self._active_jobs(snap1, snap2)
            if not active:
                clean += 1
                if clean >= need:
                    self.on_log('[gate] ✅ 安静窗口达成'
                                '（连续 %d 轮无活跃推理作业）' % clean)
                    return True
            else:
                clean = 0
                for j in active:
                    self.on_log('[gate] 检测到活跃作业 pid=%d cpuΔ=%.2fs %s'
                                % (j['pid'], j['cpu_delta'], j['cmd'][:150]),
                                flush=True)
        self.on_log('[gate] ⚠️ 等不到安静窗口（已等 %.0fs）'
                    '⇒ 数据可能受污染' % (time.time() - t0))
        return False


if __name__ == '__main__':
    # 自检 + 列出当前作业
    g = QuietGate()
    ok = g.self_test()
    print('self_test =', ok)
    jobs = list_python_jobs()
    print('当前像作业的进程：%d 个' % len(jobs))
    for j in jobs:
        print('  pid=%s cpu=%.1fs %s' % (j['pid'], j['cpu_s'],
                                         j['cmd'][:160]))
