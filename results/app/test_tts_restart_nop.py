#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_restart_nop.py —— 验证「worker 崩溃后**真的重启了吗**」。

根因假设：
  `_read_loop` 结束 ⇒ `rc = proc.poll()` 返回 **None**（进程刚死，Windows 上
  poll 还没更新）⇒ `_on_worker_exit()` ⇒ `self.start()`
  ⇒ 但 `start()` 开头有 `if self.proc is not None and self.proc.poll() is None: return`
  ⇒ **旧 proc 还"活着"（poll 仍是 None）⇒ 直接 return ⇒ 重启被静默跳过！**

后果：
- C-101 要求的「worker 崩溃自动重启一次」**从未真正生效**；
- 更糟：`state` 还停在 'ready' ⇒ App 以为 TTS 正常
  ⇒ 之后所有 `submit()` 都写进**死进程的 stdin** ⇒ **语音输出静默消失**，
  既不报错也不掉状态（与 §15/§20 的现象高度吻合）。

桩 worker（stub，无推理）。
"""
import os, sys, time, json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))
import tts_service  # noqa: E402

D = os.path.join(HERE, '_nop')
os.makedirs(D, exist_ok=True)
CNT = os.path.join(D, 'count.txt')
STUB = r'''
import sys, json, os
here = os.path.dirname(os.path.abspath(__file__))
cntf = os.path.join(here, "count.txt")
n = 0
if os.path.exists(cntf):
    try: n = int(open(cntf).read().strip() or "0")
    except Exception: n = 0
n += 1
open(cntf, "w").write(str(n))
print(json.dumps({"kind":"ready","device":"STUB","voice":"A"}), flush=True)
os._exit(7)          # 立刻崩溃
'''
STUB_PATH = os.path.join(D, 'stub.py')
open(STUB_PATH, 'w', encoding='utf-8').write(STUB)
tts_service._WORKER = STUB_PATH
if os.path.exists(CNT):
    os.remove(CNT)

logs = []
svc = tts_service.TTSService(device='STUB', voice='A', auto=False, on_log=logs.append)
svc.start()
time.sleep(3.0)

cnt = open(CNT).read().strip()
print('=' * 72)
print('worker 崩溃后「自动重启」是否真的发生？')
print('=' * 72)
print(f'worker 实例启动次数 = {cnt}   (期望 >= 2 表示真的重启了)')
print(f'state  = {svc.state}      (期望 error 或 ready-with-new-worker)')
print(f'n_restart = {svc.n_restart}')
print(f'self.proc.poll() = {svc.proc.poll() if svc.proc else None}')
print(f'logs = {logs}')
print()

real_restart = int(cnt) >= 2
print(f'「自动重启」真的发生了吗：{"YES" if real_restart else "NO —— 重启被静默跳过"}')

# 后果验证：state 还是 ready，但 worker 已死 ⇒ submit 写进死 stdin
print()
print('后果验证：worker 已死，但 state 仍为 ready')
print(f'  state = {svc.state}   (死 worker 却报 ready ⇒ App 以为 TTS 正常)')
try:
    svc.submit('测试提交一句话')
    time.sleep(0.5)
    print('  submit() 未抛异常 ⇒ 句子被写进死进程的 stdin ⇒ 语音静默丢失')
except Exception as e:
    print(f'  submit() 抛异常: {type(e).__name__}: {e}')

print()
print('结论：' + ('PASS（重启确实发生）' if real_restart else 'FAIL —— C-101「自动重启一次」从未真正生效，且 state 停在 ready 造成静默丢语音'))
try:
    svc.close()
except Exception:
    pass
import shutil
shutil.rmtree(D, ignore_errors=True)
sys.exit(0 if real_restart else 1)
