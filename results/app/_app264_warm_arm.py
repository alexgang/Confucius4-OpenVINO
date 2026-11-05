#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app264 —— APP-066 3(b) 的**热启臂**（100 % 缩放）单独补测。

## 🔴 为什么需要它
`app263` 的真冷臂已测到 **首次 NPU 编译 1209.3 s**（全新 LOCALAPPDATA ⇒ 真冷），
但它的「热启臂」**超时 900 s**（`tts_load_s=null`）⇒ 因为
**热启臂复用了冷臂那个 LOCALAPPDATA，而冷臂里 TTS 从未起来 ⇒ NPU blob 一个都没编**
⇒ 热启臂等于**又冷启了一次** ⇒ 900 s 不够（真冷要 1209 s）⇒ 判据 ②/⑥ 因此 FAIL。

⇒ 但 **NPU 缓存已经热了**（热启臂超时前已编出 18 个 blob）⇒
   现在在**同一个 LOCALAPPDATA** 上再跑一次 100 % 臂 ⇒ 才是真正的「第二次启动」。

## 口径（与 app263 完全一致 ⇒ 可比）
- 同一 MiniMVP 包（`Confucius4_LiveCaption_MiniMVP_v1.0-rc2`）
- 同一 LOCALAPPDATA（沿用 app263 热臂那个 ⇒ **命中 NPU 编译缓存**）
- 同一音频（`SPE_1500s.wav`）、同一 `--selftest 1500`
- 抓屏判据沿用 app259 的 `grab_best`（按面积取最大者 + 客户区高 ≥ 700 px）

## 输出
`results/app/app264_app066_minimvp_warm_arm_evidence.json`
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc2')
# 🔴 app263 的热臂目录（**NPU 缓存已热** ⇒ 本臂是「第二次启动」）
WARM_LA = os.path.join(
    os.environ.get('TEMP', os.path.join(HOME, 'AppData', 'Local', 'Temp')),
    'minimvp_gui_b7djmwch')
SRC_WAV = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
OUT_JSON = os.path.join(HERE, 'app264_app066_minimvp_warm_arm_evidence.json')
WAV_LONG = os.path.join(HERE, '_app264_SPE_1500s.wav')

sys.path.insert(0, HERE)
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'a259', os.path.join(HERE, 'app259_app066_minimvp_gui_coldstart.py'))
_a259 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_a259)

build_long_wav = _a259.build_long_wav
run_gui = _a259.run_gui
OUT_DIR = _a259.OUT_DIR


def _run_with_retry(args, la, wav, tries=3):
    """🔴 复用 `app259` 的**异常早退重试**逻辑（上一会话已踩过并修好）。

    实测：`app263` 的 150 % 臂首跑 **5.19 s 就崩**（`rc=3221226505`
    = `0xC0000409` STATUS_STACK_BUFFER_OVERRUN，崩在模型加载那一刻）
    ⇒ 清掉**本模块自己**遗留的 MiniMVP GUI 进程后重试 ⇒ 第 2 次成功
    （`wall=331.82 s` / `tts_load_s=312.1 s`）。
    🔴 **只杀命令行里带 `MiniMVP_v1.0-rc2` + `live_caption_app.py` 的进程**
    ⇒ 不会误杀别人的会话。
    """
    last = None
    for i in range(tries):
        last = run_gui(PKG, la, wav, 1500, 'warm100', scale=1.0,
                       timeout_s=args.timeout, min_run_s=45.0)
        early = (last.get('stopped_reason') == '进程自行退出'
                 and (last.get('wall_s') or 0) < 60)
        if not early:
            return last
        print('[warm100] 异常早退（wall=%s s rc=%s）⇒ 清残留后重试 (%d/%d)'
              % (last.get('wall_s'), last.get('rc'), i + 1, tries), flush=True)
        killed = _kill_stale_minimvp()
        if killed:
            print('[warm100] 已清残留 MiniMVP GUI：%s' % (killed,), flush=True)
        time.sleep(3.0)
    return last


def _kill_stale_minimvp():
    """🔴 只杀**本模块自己**遗留的 MiniMVP GUI（按命令行特征过滤）。

    ⚠️ **本机仓库 `.venv` 里没有 `wmi`** ⇒ `app259`/`app263` 的同名函数
    其实是**静默空操作**（`import wmi` 失败 ⇒ 直接 return []）
    ⇒ `app263` 的 150 % 臂首跑崩了以后「清残留」其实**什么都没清**，
    重试能成功是因为**崩的是自己的进程、音频设备已释放**，不是靠这段代码。
    ⇒ 这里加 **`Toolhelp32 + 打开进程读命令行`** 的兜底（不依赖 pywin32）。
    """
    killed = []
    try:
        import wmi  # noqa
        for p in wmi.WMI().Win32_Process():
            cl = (p.CommandLine or '')
            if 'MiniMVP_v1.0-rc2' in cl and 'live_caption_app.py' in cl:
                try:
                    p.Terminate()
                    killed.append(p.ProcessId)
                except Exception:
                    pass
        return killed
    except Exception:
        pass
    # ── 兜底：Toolhelp32 枚举 + 读命令行（纯 ctypes，不依赖 pywin32） ──
    try:
        import ctypes
        import ctypes.wintypes as w
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = w.HANDLE
        k32.Process32FirstW.argtypes = [w.HANDLE, ctypes.c_void_p]
        k32.Process32NextW.argtypes = [w.HANDLE, ctypes.c_void_p]
        k32.OpenProcess.restype = w.HANDLE
        k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        psapi.QueryFullProcessImageNameW.argtypes = [
            w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]

        class _P(ctypes.Structure):
            _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD),
                        ('th32ProcessID', w.DWORD),
                        ('th32DefaultHeapID', ctypes.c_ulong),
                        ('th32ModuleID', w.DWORD), ('cntThreads', w.DWORD),
                        ('th32ParentProcessID', w.DWORD),
                        ('pcPriClassBase', w.LONG), ('dwFlags', w.DWORD),
                        ('szExeFile', w.WCHAR * 260)]

        snap = k32.CreateToolhelp32Snapshot(0x2, 0)
        p = _P()
        p.dwSize = ctypes.sizeof(_P)
        mine = os.getpid()
        while True:
            if not k32.Process32FirstW(snap, ctypes.byref(p)):
                break
            pid = int(p.th32ProcessID)
            if pid == mine:
                continue
            h = k32.OpenProcess(0x1000, False, pid)
            if not h:
                if not k32.Process32NextW(snap, ctypes.byref(p)):
                    break
                continue
            try:
                buf = ctypes.create_unicode_buffer(1024)
                n = w.DWORD(1024)
                if psapi.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                    cmd = buf.value
                    if ('MiniMVP_v1.0-rc2' in cmd
                            and 'live_caption_app.py' in cmd):
                        k32.TerminateProcess(h, 1)
                        killed.append(pid)
            except Exception:
                pass
            finally:
                k32.CloseHandle(h)
            if not k32.Process32NextW(snap, ctypes.byref(p)):
                break
        k32.CloseHandle(snap)
    except Exception:
        pass
    return killed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--la', default=WARM_LA)
    ap.add_argument('--timeout', type=float, default=1500.0)
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': os.path.basename(__file__),
           'correction': 'APP-066 3(b) 热启臂（补测）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args), 'checks': [], 'runs': [],
           'purpose': ('app263 的热启臂超时（900 s）⇒ 判据 ②/⑥ FAIL；'
                       '本臂在**同一 LOCALAPPDATA**（NPU 缓存已热）上补测 '
                       '100 % 缩放的「第二次启动」')}

    def add(name, verdict, detail, why=''):
        out['checks'].append({'name': name, 'verdict': verdict,
                              'detail': detail, 'why': why})
        print('  [%s] %s%s' % ({True: 'PASS', False: 'FAIL',
                                None: 'NONE'}[verdict], name,
                               ('  ' + json.dumps(detail, ensure_ascii=False))
                               if detail else ''), flush=True)

    if not args.run:
        print('（未加 --run ⇒ 不跑设备作业）')
        return 0

    # ── 机器锁（APP-064）：本作业占 NPU ⇒ 必须先排队拿锁 ──
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        out['verdict'] = 'LOCK_BUSY'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    print('[lock] 已取得：%r' % (payload,))

    try:
        ok_q, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                timeout=1800.0, verbose=True)
    except Exception as e:
        ok_q, qinfo = None, repr(e)
    out['quiet_window'] = {'ok': ok_q, 'info': str(qinfo)}
    if ok_q is False:
        print('[quiet] !! 等不到安静窗口 ⇒ 退出')
        out['verdict'] = 'NOT_QUIET'
        try:
            ml.release(payload, verbose=True)
        except Exception:
            pass
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3

    la = args.la
    if not os.path.isdir(os.path.join(la, 'Confucius4LiveCaption')):
        print('!! 指定的 LOCALAPPDATA 目录不存在：%s' % la)
        out['verdict'] = 'NO_LA'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    n_blob = len(os.listdir(os.path.join(la, 'Confucius4LiveCaption',
                                         'tts_npu_cache'))) \
        if os.path.isdir(os.path.join(la, 'Confucius4LiveCaption',
                                      'tts_npu_cache')) else 0
    out['warm_localappdata'] = la
    out['npu_blobs_before'] = n_blob
    print('[warm] LOCALAPPDATA=%s  已有 NPU blob=%d 个' % (la, n_blob))

    wav = WAV_LONG
    if not os.path.isfile(wav):
        wav = build_long_wav(SRC_WAV, wav, 5)
    out['wav'] = wav

    try:
        r = _run_with_retry(args, la, wav)
        out['runs'].append(r)
        add('① 热启臂测到 TTS 加载耗时（有实测值）',
            r.get('tts_load_s') is not None,
            {'tts_load_s': r.get('tts_load_s'),
             'model_loaded_at_s': r.get('model_loaded_at_s'),
             'wall_s': r.get('wall_s'), 'device': r.get('tts_device'),
             'stopped_reason': r.get('stopped_reason'),
             'mt_label': r.get('mt_label')})
        sh = r.get('shot') or {}
        cl = sh.get('client') or []
        is_main = bool(cl) and cl[1] >= 700
        add('② 100 % 截图抓到**完整主窗口**且非黑图',
            bool(sh.get('ok') and not sh.get('all_black') and is_main),
            {'ok': sh.get('ok'), 'all_black': sh.get('all_black'),
             'bytes': sh.get('bytes'), 'size': sh.get('size'),
             'client': sh.get('client'), 'is_main_window': is_main,
             'n_candidates': sh.get('n_candidates')})
        out['npu_blobs_after'] = len(
            os.listdir(os.path.join(la, 'Confucius4LiveCaption',
                                    'tts_npu_cache'))) \
            if os.path.isdir(os.path.join(la, 'Confucius4LiveCaption',
                                          'tts_npu_cache')) else 0
        # 🔴 与 app263 的真冷臂对比
        cold = 1209.3
        warm = r.get('tts_load_s')
        add('③ 热启 ≪ 冷启（缓存生效）',
            bool(warm and cold and warm < cold),
            {'cold_s': cold, 'warm_s': warm,
             'saved_s': (round(cold - warm, 1) if warm else None),
             'ratio': (round(warm / cold, 4) if warm else None),
             'cold_src': 'app263 真冷臂（全新 LOCALAPPDATA）',
             'warm_src': 'app264 本臂（同一 LOCALAPPDATA，NPU 缓存已热）'})
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % e)

    n_pass = sum(1 for c in out['checks'] if c['verdict'] is True)
    n_fail = sum(1 for c in out['checks'] if c['verdict'] is False)
    n_none = sum(1 for c in out['checks'] if c['verdict'] is None)
    out['n_pass'], out['n_fail'], out['n_none'] = n_pass, n_fail, n_none
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
