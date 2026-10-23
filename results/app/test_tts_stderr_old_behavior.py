#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §20 验收（反证）：**旧行为**（stderr 用 PIPE 但从不读）会死锁。

做法：复制 `tts_service.py` 的**旧版** `_start_reader`（只起 stdout 线程），
     其余完全一样 ⇒ 与修复前行为等价。

预期：worker 往 stderr 写 >512 KB ⇒ **卡在 write(stderr)** ⇒
      永远发不出 `ready` 事件 ⇒ 主进程 `state` 永远停在 `loading`。

🔴 本脚本**不跑真 TTS 推理**（假 worker，纯 stdio）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_fake_worker_old.py')
FAKE = r'''
import json, sys
blob = 'FLOODMARKER-' + 'x' * 200 + '\n'
for i in range(3000):
    sys.stderr.write(blob)
sys.stderr.flush()
sys.stdout.write(json.dumps({'kind': 'ready', 'device': 'GPU.0', 'voice': 'A'}) + '\n')
sys.stdout.flush()
for line in sys.stdin:
    if json.loads(line).get('cmd') == 'quit':
        break
'''


def main():
    with open(TMP, 'w', encoding='utf-8') as f:
        f.write(FAKE)

    logs = []
    svc = tts_service.TTSService(device='GPU.0', voice='A',
                                 on_log=lambda m: logs.append(m), auto=False)

    # ── 旧行为：只起 stdout 线程，stderr 管道**没人读** ──
    def old_start_reader():
        proc = svc.proc
        t = threading.Thread(target=svc._read_loop, args=(proc,), daemon=True)
        t.start()
        # 旧版没有 stderr 线程

    svc._start_reader = old_start_reader

    with svc.lock:
        svc.state = 'loading'
        svc.proc = subprocess.Popen(
            [sys.executable, TMP], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)

    svc._start_reader()

    # 等 60 s 看 worker 能不能 emit ready
    t0 = time.perf_counter()
    got_ready = False
    while time.perf_counter() - t0 < 60.0:
        if any('就绪' in m for m in logs):
            got_ready = True
            break
        if svc.proc.poll() is not None:
            break
        time.sleep(0.1)
    elapsed = time.perf_counter() - t0

    alive = svc.proc.poll() is None
    print(f'旧行为（stderr 无人读）：')
    print(f'  worker 是否 emit ready : {got_ready}')
    print(f'  worker 进程是否还活着   : {alive}   (poll={svc.proc.poll()})')
    print(f'  观察时长                 : {elapsed:.1f}s')
    print(f'  日志条数                 : {len(logs)}')

    try:
        svc.proc.kill()
    except Exception:
        pass
    try:
        os.remove(TMP)
    except OSError:
        pass

    if not got_ready:
        print()
        print('⇒ 结论：旧行为**死锁确认**（worker 卡在 write(stderr)，永不发 ready）。')
        print('        修复后同一场景 9/9 PASS（见 test_tts_stderr.txt）。')
        return 0
    print()
    print('⇒ 结论：旧行为**未**复现死锁（可能机器管道缓冲更大）—— 需重估。')
    return 1


if __name__ == '__main__':
    sys.exit(main())
