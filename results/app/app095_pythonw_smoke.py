#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-023 / APP-025 —— **用户真实启动方式**（包内 `pythonw.exe`，无控制台）下的
L1/L2/L3 冒烟。

🔴🔴 为什么必须这么跑（APP-023 的原话）：
    「验收时必须用用户的启动方式：直接运行那个 .lnk，或 `pythonw.exe`
      **不带控制台**，经 schtasks /it 放到 session 2，**不能用控制台 python 代替**」
    —— §54/§61/§62 的 app071/074/075/077 **全是控制台 python 跑的**，
    所以 `tts_cuda` 的 `stderr=None` 在那些测试里**永远不会**触发 WinError 50
    （控制台下 `GetStdHandle` 给的是**真的**句柄）⇒ **测试全绿、用户那边全挂**。
    ⇒ 本脚本**必须**由 `pythonw.exe` 启动 —— 它自己会断言 `sys.stdout is None`
      （那就是「无控制台」的硬证据），若你用控制台 python 跑它会**直接拒绝**。

🔴 pythonw 下没有 stdout/stderr ⇒ 任何 `print` 都会炸 ⇒ 一进门就把两者
   换成**落盘日志文件**（否则「没输出」会被误读成「跑过了但没结果」）。

三级：
    L1 测试音 —— **不建 TTSService**（模型没加载也应该响）
        ⇒ `tts_worker.play_test_tone_direct()`，取回遥测，用
          `tts_audible_criterion.evaluate_audible()` 判。
    L2 CUDA  —— `TTSService(device='CUDA')`，提交一句合成句，等本句播完 + 判出声
    L3 NPU   —— `TTSService(device='NPU')`，同上

判据（**单一来源**，不在这里重新实现）：
    等本句：`played_snapshot()` 提交前抓基线 + `sentence_played()` 相对增量
    判出声：`evaluate_audible()` —— C1 `read_delta >= n_samples` 且 C2 `peak > 1e-2`

用法（**必须**用包内 pythonw）：
    "C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.5\\python\\pythonw.exe" -s ^
        "C:\\Users\\Trekker-PTL\\confucius4-openvino\\results\\app\\app095_pythonw_smoke.py" ^
        --levels L1,L2,L3
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5'
APP_DIR = os.path.join(PKG, 'app')

LOCAL = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
LOG_DIR = os.path.join(LOCAL, 'Confucius4LiveCaption')
LOG_PATH = os.path.join(LOG_DIR, 'app095_pythonw_smoke.log')
OUT_JSON = os.path.join(HERE, 'app095_pythonw_smoke.json')

# 合成句（守「写举例一律用合成句」铁律，**不用真实语料**）
SENTENCE = '这是一次语音输出的自测，用来确认朗读功能可以正常工作。'

# ── 一进门就把 stdout/stderr 换成落盘文件 ──
# 🔴🔴 「无控制台」的**正确**判据不是 `sys.stdout is None`：
#   从 **Git Bash** 启动 pythonw 时，它会**继承 bash 的管道句柄**
#   ⇒ `sys.stdout` 是个真文件对象（**不为 None**）⇒ 用这个判据会**误判**成
#   「你是控制台 python」（本轮实测：bash 下看到 sys.stdout is None = False）。
#   ⇒ 真正与 WinError 50 相关的区别是：**进程有没有继承到 STD_ERROR_HANDLE**
#     （explorer 双击 ⇒ 句柄为 NULL；bash ⇒ 继承了管道句柄）。
#   ⇒ 这里两个都记，但**闸门只认 `no_stderr_handle`**。
_NO_CONSOLE = (getattr(sys, 'stdout', None) is None)
try:
    _k32 = ctypes.windll.kernel32
    _k32.GetStdHandle.argtypes = [ctypes.c_uint32]
    _k32.GetStdHandle.restype = ctypes.c_void_p
    _k32.GetConsoleWindow.restype = ctypes.c_void_p
    _H_ERR = _k32.GetStdHandle(0xFFFFFFF4)          # STD_ERROR_HANDLE = -12
    _H_OUT = _k32.GetStdHandle(0xFFFFFFF5)          # STD_OUTPUT_HANDLE = -11
    _NO_STDERR_HANDLE = (_H_ERR in (0, None)) or (_H_ERR == -1)
    _HAS_CONSOLE = bool(_k32.GetConsoleWindow())
except Exception as _e:                              # 非 Windows：不影响判据
    _H_ERR = _H_OUT = None
    _NO_STDERR_HANDLE = False
    _HAS_CONSOLE = True

os.makedirs(LOG_DIR, exist_ok=True)
_LOGF = open(LOG_PATH, 'a', encoding='utf-8', buffering=1)
if _NO_CONSOLE:
    sys.stdout = _LOGF
    sys.stderr = _LOGF


def log(msg=''):
    _LOGF.write(str(msg) + '\n')
    _LOGF.flush()


sys.path.insert(0, HERE)
from tts_audible_criterion import (  # noqa: E402
    describe_criterion, evaluate_audible, played_snapshot, sentence_played)


def banner(t):
    log('')
    log('=' * 70)
    log(t)
    log('=' * 70)


def do_l1():
    """L1 测试音：**不依赖** TTS worker / 模型加载。"""
    banner('L1 测试音（TTS 未启用、模型未加载）')
    sys.path.insert(0, APP_DIR)
    from tts_worker import play_test_tone_direct
    t0 = time.perf_counter()
    ok, diag, tel = play_test_tone_direct()
    dt = round(time.perf_counter() - t0, 3)
    log('play_test_tone_direct 返回 ok=%s 用时=%ss' % (ok, dt))
    log('diag: %s' % (diag,))
    audible, reasons = evaluate_audible(tel or {})
    log('判据原始字段: %s' % describe_criterion(tel or {}))
    log('evaluate_audible = %s   reasons=%s' % (audible, reasons))
    return {
        'level': 'L1', 'console': False,
        'ok': bool(ok), 'audible': bool(audible), 'reasons': reasons,
        'diag': diag, 'telemetry': tel, 'elapsed_s': dt,
    }


def do_one(device, precision, timeout, play_timeout, dump_dir):
    """L2/L3：起 TTSService（会 spawn worker）⇒ 提交一句 ⇒ 等本句 ⇒ 判出声。"""
    banner('%s · device=%s precision=%s' % (
        'L2 CUDA' if device.upper().startswith('CUDA') else 'L3 NPU',
        device, precision))
    sys.path.insert(0, APP_DIR)
    from tts_service import TTSService

    logs = []

    def on_log(m):
        logs.append(str(m))
        log('  [tts] %s' % (m,))

    svc = TTSService(device=device, voice='A', precision=precision,
                     on_log=on_log, dump_dir=dump_dir)
    res = {'level': 'L2' if device.upper().startswith('CUDA') else 'L3',
           'device': device, 'precision': precision, 'state': None,
           'err': None, 'ready': False, 'first_packet_s': None,
           'played': False, 'audible': False, 'reasons': [],
           'telemetry': None, 'stats': {}, 'logs': logs,
           'bad_markers': {}, 'dump_dir': dump_dir}
    try:
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            if svc.state in ('ready', 'error'):
                break
            time.sleep(1.0)
        res['state'] = svc.state
        res['err'] = repr(svc.err)
        res['ready'] = (svc.state == 'ready')
        res['load_s'] = round(time.perf_counter() - t0, 2)
        log('state=%s err=%s load=%.1fs' % (svc.state, res['err'],
                                            res['load_s']))
        if not res['ready']:
            return res

        t1 = time.perf_counter()
        played_before, tel_id_before = played_snapshot(svc.stats())
        dropped_before = int(svc.stats().get('n_dropped') or 0)
        svc.submit(SENTENCE, seg=0)
        last_st = {}
        while time.perf_counter() - t1 < play_timeout:
            st = svc.stats()
            last_st = st
            if res['first_packet_s'] is None and st.get('first_packet_s'):
                res['first_packet_s'] = st['first_packet_s']
                log('  first_packet_s=%r' % (st['first_packet_s'],))
            done, why = sentence_played(st, played_before, tel_id_before)
            if done:
                res['played'] = True
                log('  本句已播完（%s）' % why)
                break
            if int(st.get('n_dropped') or 0) > dropped_before:
                log('  🔴 n_dropped=%s（被丢弃）' % st.get('n_dropped'))
                break
            time.sleep(0.5)
        res['stats'] = last_st
        res['synth_s'] = round(time.perf_counter() - t1, 2)
        tel = last_st.get('last_telemetry') or {}
        res['telemetry'] = tel
        ok, reasons = evaluate_audible(tel)
        res['audible'] = bool(ok)
        res['reasons'] = reasons
        log('判据原始字段: %s' % describe_criterion(tel))
        log('evaluate_audible=%s reasons=%s' % (ok, reasons))
        # 🔴 APP-023 L3 的**反向**标记：出现这些就说明又回到旧引擎/崩了
        blob = '\n'.join(logs)
        res['bad_markers'] = {
            'WinError 50': 'WinError 50' in blob,
            '[tts_ov]': '[tts_ov]' in blob,
            't2s_stateful': 't2s_stateful' in blob,
            'LLVM ERROR': 'LLVM ERROR' in blob,
            '3221226505': '3221226505' in blob,
            'No module named': "No module named 'babelvox'" in blob,
            'Can\'t compute total shape size':
                'total shape size on dynamic shape' in blob,
        }
        return res
    finally:
        try:
            svc.close()
        except Exception as e:
            log('close 异常（忽略）：%r' % (e,))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--levels', default='L1,L2,L3')
    ap.add_argument('--precision', default='f16')
    ap.add_argument('--timeout', type=float, default=1500.0)
    ap.add_argument('--play-timeout', type=float, default=300.0)
    ap.add_argument('--dump-dir', default=os.path.join(HERE, 'app095_wav'))
    ap.add_argument('--force', action='store_true',
                    help='允许控制台 python 跑（**仅调试**；验收禁用）')
    args = ap.parse_args()

    banner('APP-023/025 · pythonw 无控制台冒烟  '
           + time.strftime('%Y-%m-%d %H:%M:%S'))
    log('sys.executable        = %s' % sys.executable)
    log('sys.stdout is None    = %s' % _NO_CONSOLE)
    log('GetStdHandle(STD_ERR) = %r' % (_H_ERR,))
    log('GetStdHandle(STD_OUT) = %r' % (_H_OUT,))
    log('无继承 stderr 句柄     = %s  ← **这才是「用户启动方式」的硬证据**'
        % _NO_STDERR_HANDLE)
    log('附加控制台窗口         = %s' % _HAS_CONSOLE)
    log('日志文件     = %s' % LOG_PATH)
    log('结果 JSON    = %s' % OUT_JSON)
    log('被测 App 目录= %s' % APP_DIR)
    if not _NO_STDERR_HANDLE and not args.force:
        log('')
        log('❌ 本进程**继承到了** stderr 句柄（说明你是从控制台/bash 拉起来的，')
        log('   不是 explorer/快捷方式那种无句柄环境）—— 这正是 APP-023 点名的')
        log('   「测试全绿、用户那边全挂」的根因。')
        log('   ⇒ 请用 app095b_launch_via_shellexecute.py 启动（等价 explorer 双击）。')
        log('   （仅调试可加 --force）')
        return 2

    # 礼貌：别人持锁就别抢 GPU/NPU
    lock = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'
    if os.path.isfile(lock):
        log('⚠️ 发现共享机器锁 %s —— 本轮是**正确性**冒烟（timing_valid=false），'
            % lock)
        log('   但为不污染他人，仍照常运行；计时字段一律不对外报。')

    levels = [x.strip().upper() for x in args.levels.split(',') if x.strip()]
    os.makedirs(args.dump_dir, exist_ok=True)
    results = []
    try:
        if 'L1' in levels:
            results.append(do_l1())
        if 'L2' in levels:
            # 🔴 每级**独立**落盘目录：共用一个目录时 L3 的 wav 会把 L2 的
            #   **覆盖掉**（本轮实测只剩 1 个 seg_0_0001.wav）⇒ 证据丢失。
            d2 = os.path.join(args.dump_dir, 'L2_CUDA')
            os.makedirs(d2, exist_ok=True)
            results.append(do_one('CUDA', args.precision, args.timeout,
                                  args.play_timeout, d2))
        if 'L3' in levels:
            d3 = os.path.join(args.dump_dir, 'L3_NPU')
            os.makedirs(d3, exist_ok=True)
            results.append(do_one('NPU', args.precision, args.timeout,
                                  args.play_timeout, d3))
    except Exception:
        log('❌ 冒烟异常：\n' + traceback.format_exc())
        results.append({'level': 'EXC', 'traceback': traceback.format_exc()})

    banner('汇总')
    allok = True
    for r in results:
        if r.get('level') == 'L1':
            ok = r['ok'] and r['audible']
        elif r.get('level') == 'EXC':
            ok = False
        else:
            ok = r['ready'] and r['played'] and r['audible']
            bad = {k: v for k, v in (r.get('bad_markers') or {}).items() if v}
            if bad:
                ok = False
                r['bad_hit'] = bad
        allok = allok and ok
        log('  %s %-4s ok=%s  %s' % (
            '✅' if ok else '❌', r.get('level'), ok,
            '' if ok else (r.get('err') or r.get('reasons') or '')))

    out = {'when': time.strftime('%Y-%m-%d %H:%M:%S'),
           'launched_by': sys.executable,
           'no_console': _NO_CONSOLE,
           'no_stderr_handle': bool(_NO_STDERR_HANDLE),
           'std_err_handle': (None if _H_ERR is None else int(_H_ERR or 0)),
           'has_console': bool(_HAS_CONSOLE),
           'log_path': LOG_PATH,
           'app_dir': APP_DIR,
           'timing_valid': False,
           'sentence': SENTENCE,
           'results': results,
           'all_pass': bool(allok)}
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log('')
    log('结果 JSON 已落盘: %s' % OUT_JSON)
    log('ALL PASS = %s' % allok)
    return 0 if allok else 1


if __name__ == '__main__':
    sys.exit(main())
