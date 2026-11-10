#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app414_rc6_smoke.py —— **APP-098 三.3：rc6 冒烟测试**（每个 60 s）。

## reviewer 三.3 原文
> **冒烟测试，各跑 60 s，每项报 exit 码、EXECUTION_DEVICES、有没有输出**：
> - ASR 分别放 GPU、NPU；
> - MT 分别放 GPU、NPU，目标 zh；
> - TTS 分别放 GPU、NPU，音色 A。

## 🔴🔴🔳 纪律
* **设备作业 ⇒ 持 MACHINE_LOCK**（跑完必删；回收前必须用
  `OpenProcess` + `GetExitCodeProcess` 确认 PID 真死）。
* **不调用 MiniMax**（质量判定由 reviewer 做）。
* 每臂都记：**exit 码 / stdout 字节数 / 有没有输出 / EXECUTION_DEVICES 行**。

## 用法
```
.venv/Scripts/python.exe results/app/_app414_rc6_smoke.py --pkg <rc6 目录> --lock
```
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)

OUTROOT = os.path.join(HERE, 'app414_rc6_smoke')
REPORT = os.path.join(HERE, 'app414_rc6_smoke.json')
LOCK = r'C:\Users\Trekker-PTL\shared\MACHINE_LOCK'

#: 🔴 各臂（reviewer 三.3 的六臂）
ARMS = (
    ('asr_gpu', '--engine', 'gpu_int8', '--asr-device', 'GPU.0'),
    ('asr_npu', '--engine', 'npu_int8', '--asr-device', 'NPU'),
    ('mt_gpu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--translate', 'zh', '--mt-device', 'GPU.0'),
    ('mt_npu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--translate', 'zh', '--mt-device', 'NPU'),
    ('tts_gpu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--tts', 'on', '--tts-voice', 'A', '--tts-device', 'GPU.0'),
    ('tts_npu', '--engine', 'npu_int8', '--asr-device', 'NPU',
     '--tts', 'on', '--tts-voice', 'A', '--tts-device', 'NPU'),
)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def pid_alive(pid):
    """🔴 **用 OpenProcess + GetExitCodeProcess** 判活（不用 tasklist）。

    ⚠️ **259 = STILL_ACTIVE ⇒ 活着**（**只有 0 才是死**）
    ⇒ 把它当死会**误抢活锁**（本项目已踩过一次）。
    """
    import ctypes
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False        # err == 87（参数错）⇒ 进程不存在 ⇒ 死
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    if not ok:
        return True         # 探测失败 ⇒ **视为存活**（保守）
    return code.value == STILL_ACTIVE


def acquire_lock(tag):
    """🔴 创建 MACHINE_LOCK（已存在 ⇒ 失败，等人工/上一轮释放）。"""
    payload = 'app %d %s %s' % (os.getpid(), now(), tag)
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, payload.encode('utf-8'))
        os.close(fd)
        return payload
    except FileExistsError:
        return None


def release_lock():
    try:
        if os.path.exists(LOCK):
            with open(LOCK, encoding='utf-8', errors='replace') as f:
                info = f.read()
            m = re.match(r'\S+\s+(\d+)\s', info)
            if m:
                pid = int(m.group(1))
                if pid_alive(pid):
                    print('🔴 锁的 PID %d 还活着 ⇒ 不删锁' % pid)
                    return False
            os.remove(LOCK)
            print('[lock] 已释放')
            return True
    except Exception as e:
        print('[lock] 释放异常：%r' % e)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', required=True)
    ap.add_argument('--seconds', type=float, default=60.0)
    ap.add_argument('--lock', action='store_true')
    ap.add_argument('--arms', default='')
    ap.add_argument('--audio', default=r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest\smoke30.wav',
                    help='冒烟素材（30 s 英文）')
    args = ap.parse_args()
    PKG = args.pkg
    py = os.path.join(PKG, 'python', 'python.exe')
    app = os.path.join(PKG, 'app', 'live_caption_app.py')
    os.makedirs(OUTROOT, exist_ok=True)
    if not os.path.isfile(args.audio):
        print('!! 找不到冒烟素材：%s' % args.audio)
        return 2

    ev = {'created_at': now(), 'pkg': PKG, 'seconds': args.seconds,
          'arms': [], 'verdict': 'PENDING'}

    lock_payload = None
    if args.lock:
        lock_payload = acquire_lock('rc6_smoke')
        if not lock_payload:
            print('🔴 MACHINE_LOCK 已被占用 ⇒ 本轮不跑设备作业')
            ev['verdict'] = 'SKIPPED_LOCK_BUSY'
            with open(REPORT, 'w', encoding='utf-8') as f:
                json.dump(ev, f, ensure_ascii=False, indent=1)
            return 1
        ev['lock'] = lock_payload
        print('[lock] 已获取：%s' % lock_payload)

    want = set(a for a in args.arms.split(',') if a)
    try:
        for name, *opts in ARMS:
            if want and name not in want:
                continue
            outp = os.path.join(OUTROOT, '%s.log' % name)
            cmd = [py, '-s', app, '--cli',
                   '--file', args.audio,
                   '--max-seconds', str(args.seconds),
                   '--out', os.path.join(OUTROOT, '%s.txt' % name)] + list(opts)
            print('[arm] %s: %s' % (name, ' '.join(opts)))
            t0 = time.time()
            with open(outp, 'wb') as lf:
                p = subprocess.run(cmd, cwd=PKG, stdout=lf,
                                   stderr=subprocess.STDOUT, timeout=900)
            dt = round(time.time() - t0, 1)
            raw = open(outp, 'rb').read()
            txt = raw.decode('utf-8', errors='replace')
            # 🔴 **EXTRACT**：EXECUTION_DEVICES 行（APP-098 二.3 的新输出）
            exec_lines = [l.strip() for l in txt.splitlines()
                          if 'EXECUTION_DEVICES' in l]
            # 🔴 有没有输出：字幕/译文非空
            sub_path = os.path.join(OUTROOT, '%s.txt' % name)
            sub_text = ''
            if os.path.exists(sub_path):
                sub_text = open(sub_path, encoding='utf-8',
                                errors='replace').read().strip()
            rec = {
                'arm': name, 'opts': list(opts), 'exit_code': p.returncode,
                'seconds': dt, 'log_bytes': len(raw),
                'log_path': outp,
                'exec_devices_lines': exec_lines,
                'n_exec_devices_lines': len(exec_lines),
                'has_output': bool(sub_text),
                'output_chars': len(sub_text),
                'output_path': sub_path if os.path.exists(sub_path) else None,
                'output_head': sub_text[:400],
            }
            ev['arms'].append(rec)
            print('   exit=%s  %ss  输出=%s  EXEC_DEV=%d 行'
                  % (rec['exit_code'], dt, rec['has_output'],
                     rec['n_exec_devices_lines']))
    finally:
        if args.lock:
            release_lock()

    # ── 判定：每臂都要 exit==0 且有输出 ─────────────────────────
    n_ok = sum(1 for a in ev['arms']
               if a['exit_code'] == 0 and a['has_output'])
    ev['n_arms'] = len(ev['arms'])
    ev['n_arms_ok'] = n_ok
    ev['verdict'] = 'PASS' if (ev['n_arms'] and n_ok == ev['n_arms']) else 'PARTIAL'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[smoke] %d/%d 臂 OK ⇒ %s' % (n_ok, ev['n_arms'], ev['verdict']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
