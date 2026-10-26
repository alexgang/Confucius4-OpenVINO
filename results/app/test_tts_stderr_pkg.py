#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §20 验收（客户包版）：对**客户包内**的 `tts_service.py` 跑同一套 stderr 自测。

为什么单独跑一遍：
  仓库 ⇄ 客户包是两份独立副本 ⇒ 「仓库里测过」**不等于**「包里的那份是对的」。
  ⇒ 必须对包内那份**单独**跑同一套断言。

🔴 不跑真 TTS 推理（假 worker，纯 stdio）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

import sys as _sys
_sys.path.insert(0, r'C:\Users\Trekker-PTL\confucius4-openvino')
import pkg_paths as _pkg_paths

# 🔴🔴 §48：**不写死包版本** ⇒ 自动发现最大版本（`pkg_paths` 单一数据源）
PKG_APP = _pkg_paths.pkg_app_dir()
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_fake_worker_pkg.py')

FAKE = r'''
import json, sys
mode = sys.argv[1]
if mode == 'crash':
    sys.stderr.write('PKG_CRASH_MARKER line1\n')
    sys.stderr.write('PKG_CRASH_MARKER line2\n')
    sys.stderr.flush()
    sys.exit(3)
if mode == 'flood':
    blob = 'PKGFLOOD-' + 'x' * 200 + '\n'
    for i in range(3000):
        sys.stderr.write(blob)
    sys.stderr.flush()
    sys.stdout.write(json.dumps({'kind': 'ready', 'device': 'GPU.0', 'voice': 'A'}) + '\n')
    sys.stdout.flush()
    for line in sys.stdin:
        if json.loads(line).get('cmd') == 'quit':
            break
    sys.exit(0)
sys.stderr.write('PKG_HELLO_MARKER\n')
sys.stderr.flush()
sys.stdout.write(json.dumps({'kind': 'ready', 'device': 'GPU.0', 'voice': 'A'}) + '\n')
sys.stdout.flush()
for line in sys.stdin:
    if json.loads(line).get('cmd') == 'quit':
        break
'''


def main():
    if not os.path.isfile(os.path.join(PKG_APP, 'tts_service.py')):
        print(f'!! 客户包不存在: {PKG_APP}')
        return 1
    sys.path.insert(0, PKG_APP)
    import tts_service
    print(f'导入的 tts_service 来自: {tts_service.__file__}')
    assert os.path.normcase(os.path.abspath(tts_service.__file__)) == \
        os.path.normcase(os.path.join(PKG_APP, 'tts_service.py')), '导入的不是包内那份！'

    results = []

    def ok(name, cond, extra=''):
        results.append((name, bool(cond)))
        print(f'  [ {"OK" if cond else "FAIL"} ] {name}' + (f'  -- {extra}' if extra else ''))

    with open(TMP, 'w', encoding='utf-8') as f:
        f.write(FAKE)

    def make(mode):
        logs = []
        lock = threading.Lock()
        svc = tts_service.TTSService(device='GPU.0', voice='A',
                                     on_log=lambda m: (lock.acquire(), logs.append(m), lock.release()),
                                     auto=False)
        def patched_start():
            with svc.lock:
                svc.state = 'loading'
                svc.proc = subprocess.Popen(
                    [sys.executable, TMP, mode], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, bufsize=1)
            svc._start_reader()
        svc.start = patched_start
        return svc, logs, lock

    def wait(logs, lock, needle, timeout=60.0):
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < timeout:
            with lock:
                if any(needle in m for m in logs):
                    return True
            time.sleep(0.05)
        return False

    print('[1] 包内版本：stderr 被读出')
    svc, logs, lock = make('ok')
    svc.start()
    ok('stderr 行出现在 on_log', wait(logs, lock, 'PKG_HELLO_MARKER'))
    ok('带 [TTS][stderr] 前缀',
       any('[TTS][stderr]' in m and 'PKG_HELLO_MARKER' in m for m in logs))
    ok('worker 进入 ready', wait(logs, lock, '就绪'))
    svc.close()

    print('[2] 包内版本：stderr 写满 512 KB 不死锁')
    svc2, logs2, lock2 = make('flood')
    svc2.start()
    ok('worker 仍能 emit ready', wait(logs2, lock2, '就绪', timeout=60.0))
    with lock2:
        n = sum(1 for m in logs2 if 'PKGFLOOD' in m)
    ok('读满 3000 行 stderr', n == 3000, f'n={n}')
    svc2.close()

    print('[3] 包内版本：崩溃 traceback 不静默')
    svc3, logs3, lock3 = make('crash')
    svc3.start()
    ok('traceback 出现在 on_log', wait(logs3, lock3, 'PKG_CRASH_MARKER'))
    try:
        svc3.close()
    except Exception:
        pass

    try:
        os.remove(TMP)
    except OSError:
        pass

    n_pass = sum(1 for _, c in results if c)
    print('=' * 60)
    print(f'结果：{n_pass}/{len(results)} PASS')
    print('=' * 60)
    return 0 if n_pass == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
