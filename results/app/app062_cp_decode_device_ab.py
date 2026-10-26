#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""APP-062：**cp_decode 设备**的决定性 A/B（reviewer APP-018 第 1 条第 1 项）。

## 假设（来自代码事实，非猜测）

reviewer 的生产配置明写「**cp_decode 放 NPU**」，但 App 侧从来没实现过：

| 位置 | 代码 | cp_decode 设备 |
|---|---|---|
| `babelvox/pipeline.py` L347-350（原生 `BabelVox._load_npu_models`） | `core.compile_model(cp_decode.xml, "CPU")` | **CPU** |
| `live_caption/tts_engine_patch.py` L379-382（App vendored patch，md5 与 TTS 模块 `qwen3tts_patch.py` **完全一致**） | 同上 | **CPU** |
| `qwen3tts_eval/eval_cp_on_npu.py::_recompile_cp_on_npu()`（TTS 模块的「尺子」） | `m.reshape(CP_SHAPE)` 后 `compile_model(m, "NPU")` | **NPU** |

⇒ TTS 模块测出 RTF 0.8568 / 首包 0.5862 s 时，**cp_decode 在 NPU**；
   App 测出 RTF ~2.05 / 首块 1.07-1.29 s 时，**cp_decode 在 CPU**。
⇒ 差 ≈ **2.4×**，与观测到的 RTF 差距量级一致。

## 本脚本要做的

**同一个进程、同一个引擎实例、同一批句子**，只切 `cp_decode` 的编译设备：

- **A 臂（基线）**：`cp_decode` 留在 **CPU**（= 现在的 App 行为）
- **B 臂**：把 `cp_decode` 用**同样的 CP_SHAPE reshape** 后**重新编译到 NPU**

⇒ 只改一个变量 ⇒ 直接读出这个变量的效应。

⚠️ **必须 reshape**：动态维 IR 直接编到 NPU 会 **Segfault**（进程直接崩，
   try/except 接不住）—— 详见 `eval_cp_on_npu.py` 的 docstring。

## 纪律

- 🔴 **持共享机器锁**（计时作业）。
- 🔴 **不 import 被测模块**（`tts_worker` 顶部连带 numpy/openvino ⇒ import 阶段就 abort）。
  ⇒ 这里只调**引擎层** `tts_engine`（纯 python 入口，走客户包真实路径）。
- 🔴 **计时窗口内除本进程外不启动任何 `python.exe`**（连读 JSON 都不行）。
- 🔴 产物写**仓库外**。

用法（客户包 python）：
    python results/app/app062_cp_decode_device_ab.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
OUT_DIR = r'C:\Users\Trekker-PTL\abba_out'
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

# 🔴 cp_decode 的静态形状（取自 babelvox pipeline.py 的 CP_* 常量，
#    与 `qwen3tts_eval/eval_cp_on_npu.py` **完全一致** ⇒ 同一把尺子）
CP_SHAPE = {
    "inputs_embeds": [1, 1, 1024],
    "cache_position": [1],
    "attention_mask": [1, 1, 1, 20],
    "past_keys": [5, 1, 8, 20, 128],
    "past_values": [5, 1, 8, 20, 128],
}

# 与 `app061` 同一批句子（同源素材）⇒ 可与 app061 solo 直接对照
TEXTS = [
    '大家早上好，欢迎参加季度工程评审会。',
    '今天，我想与团队一起探讨三个主要主题。',
    '首先，我们将看看上次测量的推理延迟数据。',
    '其次，包装流程得到了大幅简化。',
    '第三，我们希望简化流程，讨论下一次发布的路线图。',
    '如果还有任何问题，请随时告诉我，我们继续吧。',
]


def _pid_alive(pid: int) -> bool:
    import ctypes
    k = ctypes.windll.kernel32
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        if k.GetExitCodeProcess(h, ctypes.byref(code)):
            return code.value == 259
        return False
    finally:
        k.CloseHandle(h)


def _read_lock_pid(raw: str):
    """🔴 锁格式兼容：README 单行（`asr PID=…`）+ key-value 两种都要认。"""
    for ln in raw.split('\n'):
        up = ln.upper()
        if 'PID=' in up:
            try:
                return int(up.split('PID=')[1].split()[0].strip())
            except Exception:
                return None
        if up.strip().startswith('PID:'):
            try:
                return int(up.split('PID:')[1].split()[0].strip())
            except Exception:
                return None
    return None


def acquire_lock(module='app', timeout_s=3600.0):
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    t0 = time.time()
    while True:
        if not os.path.exists(LOCK):
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, ('module: %s\npid: %d\nstarted: %s\n'
                              % (module, os.getpid(),
                                 time.strftime('%Y-%m-%d %H:%M:%S'))).encode('utf-8'))
                os.close(fd)
                print('[lock] 已取得 %s' % LOCK)
                return True
            except FileExistsError:
                pass
        try:
            raw = io.open(LOCK, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            raw = ''
        pid = _read_lock_pid(raw)
        if pid and not _pid_alive(pid):
            print('[lock] 陈旧锁（pid=%d 已死）→ 回收' % pid)
            try:
                os.remove(LOCK)
            except OSError:
                pass
            continue
        if time.time() - t0 > timeout_s:
            print('[lock] 等锁超时 ⇒ 放弃')
            return False
        print('[lock] 等待中…（已等 %.0fs）' % (time.time() - t0), flush=True)
        time.sleep(10.0)


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 🔴🔴 安静窗口闸门（防污染）
# ---------------------------------------------------------------------------
# 实测教训（2026-10-26）：同一脚本、同一配置，连续两跑 A 臂
#   RTF 中位 **2.284** → **3.256**（差 1.43×）
# ⇒ 原因：**ASR 模块的 `p3_ov_app.py --device NPU` 正在并发跑**，
#    而且**它没持机器锁** ⇒ 我的计时窗口被污染。
# ⇒ 计时前必须确认「没有别的推理作业在跑」。
#
# 🔴 判据**不能只看进程名**（要按命令行判断是不是推理作业）；
#    🔴 也不能只看「谁持锁」——**不持锁的模块作业照样会污染**。
#    🔴 取命令行**不用 wmic**（实测返回空 ⇒ 假阴性）⇒ 用 ctypes 走
#    Windows API（NtQueryInformationProcess + PEB）读命令行。
#
# 🔴🔴 **「正在等锁的进程」不算作业**（否则和自己是死锁）：
#    判据要排除 CPU 增量≈0 的等锁进程。

# 这些命令行片段 = 「会跟本实验抢 NPU/GPU/CPU」的作业
JOB_MARKERS = (
    'p3_ov_app.py',          # ASR NPU 推理
    'p3_run_with_lock.py',
    'own20_step_probe.py',   # TTS 模块探针
    'bench', 'run_matrix',   # TTS 模块矩阵
    'eval_', 'diag_',
)


def _read_cmdline(pid: int) -> str:
    """🔴 读进程命令行（ctypes 走 Windows API）。

    ⚠️ 不用 `wmic`（实测返回空 ⇒ 假阴性）。
    ⚠️ 不用 `tasklist`（只有镜像名，没有命令行）。

    🔴🔴 **必须显式设 argtypes/restype**：否则 `HANDLE` 被当成
    32 位 int 截断 ⇒ `ReadProcessMemory` 静默失败 ⇒ **假阴性**
    （本次实测踩过：所有进程都返回空字符串）。
    """
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll

    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                     wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.ReadProcessMemory.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    ntdll.NtQueryInformationProcess.argtypes = [
        wintypes.HANDLE, ctypes.c_ulong, ctypes.c_void_p,
        ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long

    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ''
    try:
        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [('ExitStatus', wintypes.LONG),
                        ('PebBaseAddress', ctypes.c_void_p),
                        ('AffinityMask', ctypes.c_void_p),
                        ('BasePriority', ctypes.c_void_p),
                        ('UniqueProcessId', ctypes.c_void_p),
                        ('InheritedFromUniqueProcessId', ctypes.c_void_p)]
        pbi = PROCESS_BASIC_INFORMATION()
        ret = ctypes.c_ulong()
        status = ntdll.NtQueryInformationProcess(
            h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(ret))
        if status != 0 or not pbi.PebBaseAddress:
            return ''
        peb = pbi.PebBaseAddress

        # PEB.ProcessParameters（x64 偏移 0x20）
        # RTL_USER_PROCESS_PARAMETERS.CommandLine（x64 偏移 0x70）
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            pp_off, cmd_off = 0x20, 0x70
        else:
            pp_off, cmd_off = 0x10, 0x40

        n_read = ctypes.c_size_t(0)
        params_ptr = ctypes.c_void_p()
        if not kernel32.ReadProcessMemory(
                h, ctypes.c_void_p(peb + pp_off), ctypes.byref(params_ptr),
                ctypes.sizeof(params_ptr), ctypes.byref(n_read)):
            return ''

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [('Length', wintypes.USHORT),
                        ('MaximumLength', wintypes.USHORT),
                        ('Buffer', ctypes.c_void_p)]
        us = UNICODE_STRING()
        if not kernel32.ReadProcessMemory(
                h, ctypes.c_void_p(params_ptr.value + cmd_off),
                ctypes.byref(us), ctypes.sizeof(us), ctypes.byref(n_read)):
            return ''
        n = us.Length // 2
        if n <= 0 or n > 32768:
            return ''
        buf = ctypes.create_unicode_buffer(n)
        if not kernel32.ReadProcessMemory(
                h, ctypes.c_void_p(us.Buffer), buf, us.Length,
                ctypes.byref(n_read)):
            return ''
        return buf.value
    except Exception:
        return ''
    finally:
        kernel32.CloseHandle(h)


def _cpu_time_s(pid: int) -> float:
    """进程已用 CPU 时间（秒）——用来区分「真在跑」与「在等锁」。"""
    import ctypes
    from ctypes import wintypes

    class FILETIME(ctypes.Structure):
        _fields_ = [('dwLowDateTime', wintypes.DWORD),
                    ('dwHighDateTime', wintypes.DWORD)]

    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                     wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME)]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return 0.0
    try:
        c, e = FILETIME(), FILETIME()
        k, u = FILETIME(), FILETIME()
        if not kernel32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                        ctypes.byref(k), ctypes.byref(u)):
            return 0.0
        def _t(ft):
            return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7
        return _t(c) + _t(e) + _t(k) + _t(u)
    except Exception:
        return 0.0
    finally:
        kernel32.CloseHandle(h)


def _find_job_pids(exclude_self=True):
    """找「会抢设备」的作业进程（按命令行，不按进程名）。"""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    out = []
    # Toolhelp32 枚举进程
    class PROCESSENTRY32W(ctypes.Structure):
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

    me = os.getpid()
    snap = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if snap == -1:
        return out
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        if kernel32.Process32FirstW(snap, ctypes.byref(pe)):
            while True:
                pid = pe.th32ProcessID
                name = pe.szExeFile
                if (name.lower() in ('python.exe', 'pythonw.exe')
                        and not (exclude_self and pid == me)):
                    cmd = _read_cmdline(pid)
                    low = (cmd or '').lower()
                    if any(mk in low for mk in JOB_MARKERS):
                        out.append({'pid': pid, 'cmd': cmd[:300],
                                    'cpu_s': round(_cpu_time_s(pid), 2)})
                if not kernel32.Process32NextW(snap, ctypes.byref(pe)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return out


def wait_quiet_window(max_wait_s=1800.0, poll_s=12.0, require_two_rounds=True):
    """🔴 等到「没有别的推理作业在跑」为止。

    🔴🔴 **必须排除「正在等锁的进程」**：CPU 增量 ≈ 0 ⇒ 它只是排队，
         不是在干活 ⇒ 若把它算成作业 ⇒ 与自己是死锁。
    ⇒ 判据：两次采样相隔 ``poll_s``，CPU 增量 < 0.5 s ⇒ 视为「等锁/空转」。
    """
    t0 = time.time()
    clean_rounds = 0
    while time.time() - t0 < max_wait_s:
        snap1 = {j['pid']: j for j in _find_job_pids()}
        time.sleep(poll_s)
        snap2 = {j['pid']: j for j in _find_job_pids()}
        active = []
        for pid, j in snap2.items():
            cpu0 = snap1.get(pid, {}).get('cpu_s', j['cpu_s'])
            delta = round(j['cpu_s'] - cpu0, 2)
            j['cpu_delta'] = delta
            # 🔴 CPU 增量 ≈ 0 ⇒ 等锁/空转 ⇒ 不算作业
            if delta >= 0.5:
                active.append(j)
        if not active:
            clean_rounds += 1
            need = 2 if require_two_rounds else 1
            if clean_rounds >= need:
                print('[quiet] 安静窗口达成（连续 %d 轮无活跃推理作业）'
                      % clean_rounds)
                return True
        else:
            clean_rounds = 0
            for j in active:
                print('[quiet] 检测到活跃作业 pid=%d cpuΔ=%.2fs cmd=%s'
                      % (j['pid'], j['cpu_delta'], j['cmd'][:160]),
                      flush=True)
    print('[quiet] ⚠️ 等不到安静窗口（已等 %.0fs）⇒ 继续但数据可能受污染'
          % (time.time() - t0))
    return False


def _cp_decode_ir_path(eng, model_root):
    """定位 cp_decode 的 IR。

    🔴 `MultiDecoderBabelVox`（App 用的类）**没有** `_ir_path`
    （那是 `QuantEvalBabelVox` 才有的）⇒ 走原生路径：
    `model_dir = export_dir / precision` ⇒ `.../int8/cp_decode.xml`。
    """
    fn = getattr(eng, '_ir_path', None)
    if callable(fn):
        return fn('cp_decode')
    # 原生路径：export_dir/int8/cp_decode.xml
    root = getattr(eng, '_model_dir', None)
    if not root:
        root = os.path.join(model_root, 'int8')
    return os.path.join(root, 'cp_decode.xml')


def _recompile_cp_decode_npu(eng, core, model_root):
    """把 cp_decode 用**固定形状**重编译到 NPU（与 TTS 模块同一把尺子）。"""
    t0 = time.perf_counter()
    ir = _cp_decode_ir_path(eng, model_root)
    m = core.read_model(ir)
    # 🔴🔴 必须 reshape：动态维 IR 直接编到 NPU 会 Segfault
    m.reshape(CP_SHAPE)
    cm = core.compile_model(m, 'NPU')
    dt = time.perf_counter() - t0
    eng.cp_decode = cm
    eng.cp_on_cpu = False
    return dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='NPU')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--no-lock', action='store_true')
    ap.add_argument('--skip-quiet', action='store_true',
                    help='跳过安静窗口闸门（必须在日志里写明理由）')
    ap.add_argument('--quiet-max-wait', type=float, default=1800.0)
    args = ap.parse_args()

    sys.path.insert(0, os.path.join(PKG, 'app'))
    sys.path.insert(0, os.path.join(PKG, 'python', 'Lib', 'site-packages'))
    os.chdir(PKG)

    if not args.no_lock and not acquire_lock('app-062'):
        return 2

    # 🔴🔴 **安静窗口闸门**：计时前必须确认「没有别的推理作业在跑」。
    #   实测教训：ASR 的 `p3_ov_app.py --device NPU` 并发跑（且**不持锁**）
    #   ⇒ 同一脚本两跑 RTF 中位 2.284 → 3.256（差 1.43×）。
    quiet_ok = wait_quiet_window(
        max_wait_s=args.quiet_max_wait,
        require_two_rounds=not args.skip_quiet)
    print('[quiet] 安静窗口 = %s' % quiet_ok)

    rec = {'experiment': 'APP-062 cp_decode 设备 A/B（CPU vs NPU）',            'precision': args.precision,
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'quiet_ok': None,
           'skip_quiet': bool(args.skip_quiet),
           'texts': TEXTS}
    try:
        import numpy as np
        import openvino as ov
        import tts_engine

        print('\n=== 加载引擎（生产配置：NPU/int8/ctx25/chunk8/spkonly）===')
        t0 = time.perf_counter()
        eng = tts_engine.make_engine(device=args.device,
                                     precision=args.precision,
                                     on_log=lambda m: print('  ' + m))
        rec['load_s'] = round(time.perf_counter() - t0, 2)
        print('  加载 %.1f s' % rec['load_s'])

        # 记录 cp_decode 当前设备（基线应为 CPU）
        # 🔴 判据用 `eng.cp_on_cpu`（原生 pipeline.py L181/L356 设的标志位）：
        #    CompiledModel **没有** `get_property('DEVICE')` ⇒ 不能靠它。
        cp_dev = 'CPU' if getattr(eng, 'cp_on_cpu', False) else 'NPU(?)'
        rec['arm_A_cp_decode_device'] = cp_dev
        rec['arm_A_cp_on_cpu_flag'] = bool(getattr(eng, 'cp_on_cpu', False))
        print('  基线 cp_decode 设备 = %s（cp_on_cpu=%s）'
              % (cp_dev, rec['arm_A_cp_on_cpu_flag']))

        ref = tts_engine.preset_voice_path()
        spk = tts_engine.speaker_embedding(eng, ref,
                                           on_log=lambda m: print('  ' + m))
        rec['spk_ok'] = spk is not None

        # 预热（排除首次编译/首帧）
        t0 = time.perf_counter()
        _ = list(tts_engine.stream(eng, '预热。', language='Chinese',
                                   speaker_embed=spk))
        rec['warmup_s'] = round(time.perf_counter() - t0, 2)
        print('  预热 %.1f s' % rec['warmup_s'])

        def synth_one(text):
            t = time.perf_counter()
            t_first = None
            total = 0
            for w, sr in tts_engine.stream(eng, text, language='Chinese',
                                           speaker_embed=spk):
                if t_first is None:
                    t_first = time.perf_counter() - t
                total += len(w)
            t_all = time.perf_counter() - t
            return (t_first, t_all, total / 24000.0)

        def run_arm(name):
            print('\n=== 臂 %s ===' % name)
            rows = []
            for i, txt in enumerate(TEXTS):
                tf, ta, au = synth_one(txt)
                rtf = (ta / au) if au else None
                rows.append({'id': i, 't_first': round(tf, 3),
                             't_all': round(ta, 3),
                             'audio_s': round(au, 2),
                             'rtf': round(rtf, 3) if rtf else None})
                print('  句%d 首块 %.3f s  整句 %.3f s  音频 %.2f s  RTF %.3f'
                      % (i, tf, ta, au, rtf or 0))
            rtfs = [r['rtf'] for r in rows if r['rtf']]
            wall = sum(r['t_all'] for r in rows)
            audio = sum(r['audio_s'] for r in rows)
            out = {
                'rows': rows,
                'rtf_median': round(statistics.median(rtfs), 3) if rtfs else None,
                'first_block_median': round(
                    statistics.median([r['t_first'] for r in rows]), 3),
                'wall_s': round(wall, 2),
                'audio_total_s': round(audio, 2),
                'aggregate_rtf': round(wall / max(audio, 1e-9), 3),
            }
            print('  ⇒ 单句 RTF 中位 %.3f  首块中位 %.3f s  聚合 RTF %.3f'
                  % (out['rtf_median'], out['first_block_median'],
                     out['aggregate_rtf']))
            return out

        # ── A 臂：cp_decode 留在 CPU（= 现在的 App 行为）──
        rec['arm_A'] = run_arm('A：cp_decode=CPU（App 现状）')

        # ── 切设备（只改这一个变量）──
        print('\n=== 把 cp_decode 重编译到 NPU（reshape 定形状）===')
        core = ov.Core()
        try:
            cdir = tts_engine._cache_dir()
            core.set_property({'CACHE_DIR': cdir})
        except Exception:
            pass
        try:
            dt = _recompile_cp_decode_npu(eng, core, tts_engine.model_root())
            rec['arm_B_recompile_s'] = round(dt, 2)
            print('  ✅ cp_decode → NPU，编译 %.2f s' % dt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            rec['arm_B_error'] = '%s: %s' % (type(e).__name__, e)
            rec['verdict'] = False
            raise
        try:
            cp_dev_b = 'CPU' if getattr(eng, 'cp_on_cpu', False) else 'NPU'
        except Exception:
            cp_dev_b = 'unknown'
        rec['arm_B_cp_decode_device'] = cp_dev_b
        rec['arm_B_cp_on_cpu_flag'] = bool(getattr(eng, 'cp_on_cpu', False))
        print('  B 臂 cp_decode 设备 = %s（cp_on_cpu=%s）'
              % (cp_dev_b, rec['arm_B_cp_on_cpu_flag']))

        # ── B 臂：cp_decode 在 NPU ──
        rec['arm_B'] = run_arm('B：cp_decode=NPU')

        # ── 汇总 ──
        a, b = rec['arm_A'], rec['arm_B']
        rec['delta_rtf_median'] = round(b['rtf_median'] - a['rtf_median'], 3)
        rec['delta_first_block_median'] = round(
            b['first_block_median'] - a['first_block_median'], 3)
        rec['speedup_rtf_median'] = round(
            a['rtf_median'] / b['rtf_median'], 3) if b['rtf_median'] else None
        rec['speedup_first_block'] = round(
            a['first_block_median'] / b['first_block_median'], 3) \
            if b['first_block_median'] else None
        print('\n===== 结论 =====')
        print('  单句 RTF 中位：CPU %.3f → NPU %.3f  （提速 %.2f×）'
              % (a['rtf_median'], b['rtf_median'],
                 rec['speedup_rtf_median'] or 0))
        print('  首块中位：     CPU %.3f s → NPU %.3f s  （提速 %.2f×）'
              % (a['first_block_median'], b['first_block_median'],
                 rec['speedup_first_block'] or 0))
        print('  聚合 RTF：     CPU %.3f → NPU %.3f'
              % (a['aggregate_rtf'], b['aggregate_rtf']))
        rec['verdict'] = True
    except Exception as e:
        import traceback
        traceback.print_exc()
        rec.setdefault('error', '%s: %s' % (type(e).__name__, e))
        rec.setdefault('verdict', False)
    finally:
        if not args.no_lock:
            release_lock()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, 'app062_cp_decode_device_ab.json')
    io.open(out, 'w', encoding='utf-8').write(
        json.dumps(rec, ensure_ascii=False, indent=1))
    print('\n结果：%s' % out)
    return 0 if rec.get('verdict') else 1


if __name__ == '__main__':
    sys.exit(main())
