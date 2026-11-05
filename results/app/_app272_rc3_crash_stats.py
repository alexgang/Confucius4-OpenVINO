#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **APP-069②：启动崩溃 0xC0000409 的统计与根因**（20 次启动）。

## reviewer 的要求

> `app263` 150% 臂第一次：rc=3221226505，wall 5.19 s；`app264` 第一次也是同一个
> rc，都是重试后才成功。客户看到的现象就是程序直接消失。§135 只写了「重试后成功」，
> 这是产品缺陷，不能当成测试噪声。
>
> 要做：用 rc2 包连续**冷启动和热启动各 10 次**（`--check` 加 GUI 启动到
> 「模型加载完成」），统计崩溃率；崩溃时用 `faulthandler` 和 Windows 事件日志
> （Application，0xc0000409 对应的**故障模块名**）定位是哪个 DLL（npu/gpu plugin、
> tk、sounddevice）。验收：**根因写清楚**，修复后 20 次启动 0 次崩溃；
> 修不了就加一个启动器，崩溃后自动重启一次并提示用户，同时报给主会话。

## 本脚本做什么

1. **20 次启动**（10 次 `--check` + 10 次 GUI 冷启动到「模型加载完成」）
   ⇒ 每次记 `rc` / `wall_s` / 是否崩溃
2. **崩溃判定**：`rc == 3221226505`（0xC0000409）⇒ 崩溃
3. **根因取证**：
   ① `faulthandler`（`PYTHONFAULTHANDLER=1`）⇒ 崩溃时的 Python 栈
   ② **Windows 事件日志**（Application，EventID 1000）⇒ **故障模块名**（哪个 DLL）
4. 输出崩溃率 + 根因结论

## 🔴 设备纪律

* 跑 GUI/NPU ⇒ **占设备** ⇒ 必须持机器锁（`machine_lock_app`）
* 崩溃率测量**要冷启动**（清 NPU 编译缓存）⇒ **每次冷启动 ≈ 20 min**
  ⇒ **20 次 × 20 min ≈ 6.7 h** ⇒ 本脚本**分阶段**跑、可续跑
  （`--phase check` / `--phase gui`），并把进度落盘

## 用法
```
# 阶段 1：10 次 --check（快，不编译 NPU）
.venv/Scripts/python.exe results/app/_app272_rc3_crash_stats.py --phase check --n 10
# 阶段 2：GUI 冷启动（每次清缓存）
.venv/Scripts/python.exe results/app/_app272_rc3_crash_stats.py --phase gui --n 10 --cold
```
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
sys.path.insert(0, REPO)
WORK = os.path.join(HERE, 'app272_crash_out')
PROGRESS = os.path.join(WORK, 'progress.json')
REPORT = os.path.join(WORK, 'app272_crash_stats_evidence.json')
DEFAULT_PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3')

CRASH_RC = 3221226505          # 0xC0000409（STATUS_STACK_BUFFER_OVERRUN / fail-fast）
NPU_CACHE = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                          'Confucius4LiveCaption', 'tts_npu_cache')
OV_CACHE = os.path.join(os.environ.get('LOCALAPPDATA', ''),
                         'Confucius4LiveCaption', 'ov_cache')


def clear_caches():
    """清 NPU / OV 编译缓存 ⇒ 制造**真冷启动**。"""
    n = 0
    for d in (NPU_CACHE, OV_CACHE):
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            n += 1
    return n


def event_log_crashes(limit=40):
    """Windows 事件日志（Application，EventID 1000 = Application Error）里的崩溃。"""
    ps = (
        "$ErrorActionPreference='SilentlyContinue;"
        "Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000} "
        "-MaxEvents %d | ForEach-Object {"
        "$x=$_.ToXml();"
        "$m=[regex]::Match($x,'<Data Name=\"(?<k>[^\"]+)\">(?<v>[^<]*)</Data>');"
        "$p=@{};"
        "[regex]::Matches($x,'<Data Name=\"(?<k>[^\"]+)\">(?<v>[^<]*)</Data>') | "
        "ForEach-Object { $p[$_.Groups['k'].Value]=$_.Groups['v'].Value };"
        "[pscustomobject]@{Time=$_.TimeCreated;App=$p['AppName'];"
        "Mod=$p['ModuleName'];Code=$p['ExceptionCode']} } | ConvertTo-Json -Compress"
    ) % limit
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', ps],
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout or '').strip()
        if not out:
            return []
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except Exception as e:
        return [{'error': repr(e)}]


def _wait_gui_loaded(proc, log_path, timeout_s=420):
    """等 GUI 的「模型加载完成」出现 ⇒ 然后**关掉主窗口**让它正常退出。

    🔴 用 **Windows 消息**关窗（`WM_CLOSE`）而不是杀进程 ⇒
    退出码才有意义（被杀会得到 -9，掩盖了真实退出码）。
    """
    import ctypes
    import time as _t
    u32 = ctypes.WinDLL('user32', use_last_error=True)
    deadline = _t.time() + timeout_s
    while _t.time() < deadline:
        if proc.poll() is not None:
            return False                      # 自己退了（可能崩了）
        try:
            txt = open(log_path, 'r', encoding='utf-8', errors='replace').read()
        except Exception:
            txt = ''
        if '模型加载完成' in txt:
            # 🔴 关窗：枚举顶层窗口 ⇒ 找本进程 PID 的 ⇒ 发 WM_CLOSE
            HWND = ctypes.wintypes.HWND if hasattr(ctypes, 'wintypes') else None
            try:
                import ctypes.wintypes as w
                EnumProc = ctypes.WINFUNCTYPE(
                    w.BOOL, w.HWND, w.LPARAM)
                found = []

                def _cb(hwnd, _l):
                    pid = w.DWORD()
                    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if pid.value == proc.pid:
                        found.append(hwnd)
                    return True

                u32.EnumWindows(EnumProc(_cb), 0)
                for h in found:
                    u32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
                if found:
                    return True
            except Exception:
                pass
            # 关窗失败 ⇒ 兜底：结束进程（退出码会失真，但能继续）
            try:
                proc.terminate()
            except Exception:
                pass
            return True
        _t.sleep(2.0)
    # 超时 ⇒ 结束
    try:
        proc.terminate()
    except Exception:
        pass
    return False


def load_progress():
    if os.path.isfile(PROGRESS):
        try:
            return json.load(open(PROGRESS, encoding='utf-8'))
        except Exception:
            pass
    return {'runs': []}


def save_progress(p):
    with open(PROGRESS, 'w', encoding='utf-8') as f:
        json.dump(p, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=DEFAULT_PKG)
    ap.add_argument('--phase', choices=['check', 'gui'], default='check')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--cold', action='store_true',
                    help='每次启动前清 NPU/OV 缓存（真冷启动）')
    ap.add_argument('--gui-timeout', type=float, default=420.0,
                    help='GUI 臂：等「模型加载完成」的最长秒数')
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    py = os.path.join(a.pkg, 'python', 'python.exe')
    app = os.path.join(a.pkg, 'app', 'live_caption_app.py')

    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        return 3
    prog = load_progress()
    key = a.phase
    prog.setdefault(key, [])
    try:
        for i in range(len(prog[key]), a.n):
            if a.cold:
                clear_caches()
            log = os.path.join(WORK, '%s_%02d.log' % (key, i))
            if a.phase == 'check':
                cmd = [py, app, '--check']
                env = dict(os.environ)
                env.pop('PYTHONPATH', None)
                env.pop('PYTHONHOME', None)
                env['PYTHONFAULTHANDLER'] = '1'
                env['PYTHONUNBUFFERED'] = '1'   # 🔴 崩溃时打印 Python 栈
                env['PYTHONUTF8'] = '1'
                t0 = time.perf_counter()
                with open(log, 'wb') as lf:
                    rc = subprocess.call(cmd, env=env, stdout=lf,
                                         stderr=subprocess.STDOUT, timeout=3600)
                wall = time.perf_counter() - t0
                loaded = True
            else:
                # 🔴 GUI 臂：**自动关窗**（否则 GUI 常驻 ⇒ 脚本挂死）
                #   ⇒ 用一个「看门狗」线程：日志里出现「模型加载完成」
                #     （或超时）就 **关掉主窗口** ⇒ 进程正常退出。
                # SEC137: GUI arm needs an audio source (SEC135 app259 real cmd);
                # --autostart alone stalls before model loading (420s timeout).
                wav = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')
                cmd = [py, app, '--autostart', '--source', 'file', '--file', wav]
                env = dict(os.environ)
                env.pop('PYTHONPATH', None)
                env.pop('PYTHONHOME', None)
                env['PYTHONFAULTHANDLER'] = '1'
                env['PYTHONUNBUFFERED'] = '1'
                env['PYTHONUTF8'] = '1'
                t0 = time.perf_counter()
                with open(log, 'wb') as lf:
                    proc = subprocess.Popen(cmd, env=env, stdout=lf,
                                            stderr=subprocess.STDOUT)
                loaded = _wait_gui_loaded(proc, log, a.gui_timeout)
                try:
                    rc = proc.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    rc = proc.wait()
                wall = time.perf_counter() - t0
            rec = {'i': i, 'rc': rc, 'wall_s': round(wall, 2),
                   'crashed': (rc == CRASH_RC),
                   'loaded': loaded,
                   'cold': bool(a.cold), 'log': os.path.basename(log)}
            prog[key].append(rec)
            save_progress(prog)
            print('  [%s %d/%d] rc=%s wall=%.1fs crashed=%s'
                  % (key, i + 1, a.n, rc, wall, rec['crashed']))
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % (e,))

    # ── 汇总 ────────────────────────────────────────────────────────
    allruns = []
    for k, v in prog.items():
        allruns.extend(v)
    n = len(allruns)
    n_crash = sum(1 for r in allruns if r['crashed'])
    out = {
        'correction': 'APP-069②',
        'generated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'pkg': a.pkg,
        'n_runs': n,
        'n_crash_0xC0000409': n_crash,
        'crash_rate_pct': (round(100.0 * n_crash / n, 2) if n else None),
        'runs': allruns,
        'crash_rc_expected': CRASH_RC,
        'event_log': event_log_crashes(),
        'by_phase': {k: {'n': len(v),
                         'n_crash': sum(1 for r in v if r['crashed'])}
                      for k, v in prog.items()},
    }
    out['verdict'] = 'PASS' if (n >= 20 and n_crash == 0) else (
        'FAIL' if n_crash else 'INCOMPLETE')
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('\n崩溃率：%d / %d = %s%%（期望 0）'
          % (n_crash, n, out['crash_rate_pct']))
    print('按阶段：%s' % json.dumps(out['by_phase'], ensure_ascii=False))
    ev = out['event_log']
    if ev and isinstance(ev, list) and ev and 'Module' in (ev[0] or {}):
        print('事件日志里的故障模块：%s'
              % sorted({e.get('Mod') for e in ev if e.get('Mod')}))
    print('[evidence] %s' % REPORT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
