#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §20 验收：验证 `tts_service.TTSService` 真的把 worker 的 stderr 读出来。

🔴 **不在 CPU 上跑推理** —— 本脚本**不起真的 TTS worker**，
   而是用一个**假的 worker**（纯 stdio 回声）替换 `tts_service._WORKER`，
   只验证**进程管道与线程模型**的正确性。

测 4 件事：
  [1] worker 往 stderr 写的行 ⇒ 必须出现在 `on_log` 里（前缀 `[TTS][stderr]`）
  [2] worker 往 stdout 写的状态行 ⇒ 必须仍然走原有的 JSON / log 分支
  [3] **管道写满不死锁**：worker 往 stderr 写 **> 512 KB**
      （远超 Windows 管道缓冲区）⇒ 主进程必须**照样读到**、
      worker 必须**不被 write 堵死**（能继续发 ready 事件）
  [4] worker 崩溃（stderr 打印 traceback 后退出）⇒ traceback **不得静默丢失**

用法
----
    python results/app/test_tts_stderr.py
"""
from __future__ import annotations

import os
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, 'live_caption')
sys.path.insert(0, SRC)

import tts_service  # noqa: E402

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_fake_worker.py')

FAKE_WORKER = r'''
import json, sys, time
mode = sys.argv[1] if len(sys.argv) > 1 else 'ok'
if mode == 'crash':
    import traceback
    sys.stderr.write('FAKE_TRACEBACK_MARKER line1\n')
    sys.stderr.write('FAKE_TRACEBACK_MARKER line2\n')
    sys.stderr.flush()
    sys.exit(3)
if mode == 'flood':
    # 写远超管道缓冲区（Windows 默认约 64 KB）的 stderr
    blob = 'FLOODMARKER-' + 'x' * 200 + '\n'
    for i in range(3000):
        sys.stderr.write(blob)
    sys.stderr.flush()
    sys.stdout.write(json.dumps({'kind': 'ready', 'device': 'GPU.0', 'voice': 'A'}) + '\n')
    sys.stdout.flush()
    for line in sys.stdin:
        obj = json.loads(line)
        if obj.get('cmd') == 'quit':
            break
    sys.exit(0)
# ok
sys.stderr.write('HELLO_STDERR_MARKER\n')
sys.stderr.flush()
sys.stdout.write(json.dumps({'kind': 'ready', 'device': 'GPU.0', 'voice': 'A'}) + '\n')
sys.stdout.flush()
for line in sys.stdin:
    obj = json.loads(line)
    if obj.get('cmd') == 'quit':
        break
sys.exit(0)
'''


def make_service(mode):
    logs = []
    lock = threading.Lock()

    def on_log(m):
        with lock:
            logs.append(m)

    with open(TMP, 'w', encoding='utf-8') as f:
        f.write(FAKE_WORKER)

    svc = tts_service.TTSService(device='GPU.0', voice='A', on_log=on_log, auto=False)
    # 替换 worker 脚本为假 worker，并把 mode 传进去
    svc._WORKER = TMP
    orig_start = svc.start

    def patched_start():
        import subprocess
        with svc.lock:
            svc.state = 'loading'
            svc.err = None
            env = dict(os.environ)
            cmd = [sys.executable, TMP, mode]
            svc.proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        svc._start_reader()

    svc.start = patched_start
    return svc, logs, lock


def wait_for(logs, lock, needle, timeout=30.0):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        with lock:
            if any(needle in m for m in logs):
                return True
        time.sleep(0.05)
    return False


def main():
    results = []

    def ok(name, cond, extra=''):
        results.append((name, bool(cond), extra))
        print(f'  [ {"OK" if cond else "FAIL"} ] {name}' + (f'  -- {extra}' if extra else ''))

    # ── [1][2] stderr 与 stdout 两条通道 ──────────────────────────────
    print('[1] stderr 行被读出 + stdout 状态行仍正常')
    svc, logs, lock = make_service('ok')
    svc.start()
    ok('stderr 行出现在 on_log', wait_for(logs, lock, 'HELLO_STDERR_MARKER'),
       repr([m for m in logs if 'stderr' in m][:2]))
    ok('stderr 行带 [TTS][stderr] 前缀',
       any('[TTS][stderr]' in m and 'HELLO_STDERR_MARKER' in m for m in logs))
    ok('worker 进入 ready 状态', wait_for(logs, lock, '就绪'))
    ok('stdout 分支未受影响（无 stderr 前缀污染 ready 行）',
       not any('就绪' in m and '[stderr]' in m for m in logs))
    svc.close()

    # ── [3] 管道写满不死锁 ────────────────────────────────────────────
    print('[3] stderr 写 >512 KB：worker 不被堵死，ready 仍能到达')
    svc2, logs2, lock2 = make_service('flood')
    svc2.start()
    got_ready = wait_for(logs2, lock2, '就绪', timeout=60.0)
    ok('flood 模式下 worker 仍能 emit ready（未被 stderr 写满堵死）', got_ready)
    with lock2:
        n_err = sum(1 for m in logs2 if 'FLOODMARKER' in m)
    ok('读到了大量 stderr 行（>1000 行）', n_err > 1000, f'n={n_err}')
    ok('worker 进程还活着（poll() is None）', svc2.proc.poll() is None)
    svc2.close()

    # ── [4] 崩溃 traceback 不静默丢失 ────────────────────────────────
    print('[4] worker 崩溃：traceback 不被静默吞掉')
    svc3, logs3, lock3 = make_service('crash')
    svc3.start()
    ok('崩溃 traceback 出现在 on_log', wait_for(logs3, lock3, 'FAKE_TRACEBACK_MARKER'))
    ok('崩溃被记为 error 状态', wait_for(logs3, lock3, 'worker 退出', timeout=20.0))
    try:
        svc3.close()
    except Exception:
        pass

    # 清理
    try:
        os.remove(TMP)
    except OSError:
        pass

    n_pass = sum(1 for _, c, _ in results if c)
    print('=' * 60)
    print(f'结果：{n_pass}/{len(results)} PASS')
    print('=' * 60)
    return 0 if n_pass == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
