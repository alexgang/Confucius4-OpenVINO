#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_error_isolation.py —— §22 修复的**验收 + 反证**脚本。

## 缺陷（§22 修）

`tts_service.TTSService._handle_event()` 把 **worker 发来的** `kind=='error'`
事件**一律**当成「worker 整体挂了」：

    elif kind == 'error':
        self.state = 'error'          # ← 整个服务被判死
        self.err = msg.get('message', 'unknown')

但 worker 的 `error` 事件有**两类**（见 `tts_worker.py`）：

| 类别 | 载荷 | 语义 |
|---|---|---|
| **句子级** | 带 `'id': jid` | 这一句合成失败（播放缓冲写满 / 合成异常 / 写入失败 / 没有音色） |
| **worker 级** | **不带** `'id'` | 模型加载失败 / 播放设备打开失败 |

⇒ 句子级错误被误判成 worker 级 ⇒ **一句话失败 ⇒ 整个会话的语音输出永久死掉**：

1. `self.state = 'error'` ⇒ `active` 变 False ⇒
   - CLI `run_cli`：`if tts is not None and tts.active: tts.submit(...)`
     ⇒ **后续所有定稿译文都不再提交** ⇒ 语音输出静默消失；
   - GUI `_pump_tts`：`self.tts.submit(...)` 仍会调，但 `submit()` 里
     `ready = (self.state == 'ready')` 为 False ⇒ 命令进 `_queue`
     ⇒ **再也不会被 `_flush_queue()` 发出**（它只在 `ready` 事件时调用）⇒ 静默堆积。
2. `pending[jid]` **永不清除**（worker 在这条路径上不会发 `played`）
   ⇒ `drain()` 的 `pending_n == 0` 永远为假 ⇒
   **收尾必超时**（GUI 30 s / CLI 120 s 白等）。
3. `self._queue` **无上限** ⇒ worker 真死时每次提交都往里堆 ⇒ 内存无界增长。

## 修法

- worker：两处**句子级** error 事件补上 `'id': jid`（此前丢失了句子身份）。
- service：**按有没有 `id` 区分**两类 error
  - 带 `id` ⇒ 句子级 ⇒ 清 `pending[jid]` + 计丢句 + **保持 state='ready'**（服务继续）；
  - 不带 `id` ⇒ worker 级 ⇒ 维持原语义（`state='error'`）。
- `submit()`：`state == 'error'` ⇒ 直接计丢句（**不排队**）⇒ `_queue` 不再无界增长。

## 本脚本测什么（**桩 worker，不在 CPU 上跑推理**）

- [A] 句子级 error ⇒ ① state 仍 'ready' ② pending 清空 ③ 后续句子照常播
  ④ `drain()` **返回 True**（不再超时）⑤ 丢句计数 +1
- [B] worker 级 error（无 id）⇒ state 变 'error'（**原语义不被削弱**）
- [C] state=='error' 后 submit ⇒ `_queue` **不增长** + 计丢句

用法
----
    python results/app/test_tts_error_isolation.py
"""
from __future__ import annotations

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

STUB_PATH = os.path.join(HERE, '_stub_err_worker.py')

# 桩 worker：
#   - 启动即 emit ready
#   - 收到 synth：
#       id == 0  ⇒ emit **句子级** error（带 id）
#       id == 1  ⇒ emit played
#       id == 2  ⇒ emit **worker 级** error（不带 id）
STUB = r'''
import sys, json
mode = sys.argv[1] if len(sys.argv) > 1 else 'ok'
sys.stdout.write(json.dumps({"kind":"ready","device":"STUB","voice":"A"}) + "\n")
sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    cmd = msg.get("cmd")
    if cmd == "quit":
        sys.exit(0)
    if cmd == "synth":
        jid = msg.get("id")
        if jid == 0:
            # 句子级失败：合成抛异常 ⇒ worker 发 error（带 id，不发 played）
            sys.stdout.write(json.dumps({"kind":"error",
                "message":"合成失败：STUB_BOOM","id":jid}) + "\n")
            sys.stdout.flush()
        elif jid == 1:
            sys.stdout.write(json.dumps({"kind":"played","id":jid}) + "\n")
            sys.stdout.flush()
        elif jid == 2:
            # worker 级失败：模型加载失败（不带 id）
            sys.stdout.write(json.dumps({"kind":"error",
                "message":"模型加载失败：STUB_FATAL"}) + "\n")
            sys.stdout.flush()
'''

FAIL = []


def check(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        FAIL.append(name)


def wait_state(svc, want, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def new_service(logs):
    svc = tts_service.TTSService(device='STUB', voice='A', auto=False,
                                 on_log=logs.append)
    return svc


def main():
    with open(STUB_PATH, 'w', encoding='utf-8') as f:
        f.write(STUB)
    tts_service._WORKER = STUB_PATH

    print('=' * 72)
    print('§22 修复验收：句子级 error 不得杀死整个 TTS 服务（桩 worker，无推理）')
    print('=' * 72)

    # ── [A] 句子级 error ───────────────────────────────────────────────
    print()
    print('[A] 句子级 error（带 id）⇒ 服务必须存活 + pending 清空 + drain 不超时')
    logs_a = []
    svc = new_service(logs_a)
    svc.start()
    check('A0 worker 到 ready', wait_state(svc, ('ready',)), f'state={svc.state}')

    svc.submit('第一句：应当失败', seg=0)
    check('A1 失败句已入 pending', len(svc.pending) == 1, f'pending={len(svc.pending)}')

    # 等 worker 发回句子级 error
    t0 = time.time()
    while time.time() - t0 < 15 and svc.state != 'error' and 0 in svc.pending:
        time.sleep(0.05)
    time.sleep(0.3)

    check('A2 state 仍为 ready（句子级错误不得判死服务）',
          svc.state == 'ready', f'state={svc.state}')
    check('A3 pending 已清空（失败句不再悬挂）',
          len(svc.pending) == 0, f'pending={list(svc.pending)}')
    check('A4 丢句计数 +1',
          svc.n_dropped == 1, f'n_dropped={svc.n_dropped}')
    check('A5 错误信息被记录（日志可见）',
          any('STUB_BOOM' in m for m in logs_a),
          repr([m for m in logs_a if 'STUB_BOOM' in m][:2]))

    # 后续句子必须照常提交并播出
    svc.submit('第二句：应当正常', seg=1)
    t0 = time.time()
    while time.time() - t0 < 15 and svc.n_played < 1:
        time.sleep(0.05)
    check('A6 后续句子照常播出（n_played == 1）',
          svc.n_played == 1, f'n_played={svc.n_played}')

    # drain 必须能排空（关键回归点：修复前 pending 永不清 ⇒ 必超时）
    t_drain = time.time()
    drained = svc.drain(timeout=20.0)
    drain_s = time.time() - t_drain
    check('A7 drain() 返回 True（修复前必超时 False）',
          drained, f'drained={drained} 用时 {drain_s:.1f}s')
    check('A8 drain 未长时间空等（< 10 s）',
          drain_s < 10.0, f'{drain_s:.1f}s')
    svc.close()

    # ── [B] worker 级 error（无 id）⇒ 原语义保留 ───────────────────────
    print()
    print('[B] worker 级 error（不带 id）⇒ state 必须变 error（原语义不被削弱）')
    logs_b = []
    svc2 = new_service(logs_b)
    svc2.start()
    check('B0 worker 到 ready', wait_state(svc2, ('ready',)), f'state={svc2.state}')
    svc2.submit('第三句', seg=0)
    # 让 worker 发 worker 级 error（id == 2）
    svc2.submit('第四句', seg=1)
    t0 = time.time()
    while time.time() - t0 < 15 and svc2.state != 'error':
        # 直接推一条 id=2 的 synth
        if not getattr(svc2, '_fatal_sent', False):
            svc2._send({'cmd': 'synth', 'id': 2, 'text': 'fatal'})
            svc2._fatal_sent = True
        time.sleep(0.05)
    check('B1 state == error（worker 级失败仍判死）',
          svc2.state == 'error', f'state={svc2.state}')
    check('B2 err 有值',
          svc2.err is not None and 'STUB_FATAL' in str(svc2.err),
          f'err={svc2.err}')
    svc2.close()

    # ── [C] error 状态下的 submit 不得无界堆积 ────────────────────────
    print()
    print('[C] state==error 后 submit ⇒ _queue 不增长 + 计丢句')
    logs_c = []
    svc3 = new_service(logs_c)
    svc3.start()
    wait_state(svc3, ('ready',))
    svc3.submit('x', seg=0)
    svc3._send({'cmd': 'synth', 'id': 2, 'text': 'fatal'})
    t0 = time.time()
    while time.time() - t0 < 15 and svc3.state != 'error':
        time.sleep(0.05)
    q_before = len(svc3._queue)
    d_before = svc3.n_dropped
    for i in range(20):
        svc3.submit(f'error 状态下的第 {i} 句', seg=100 + i)
    check('C1 _queue 不增长（无界堆积已修）',
          len(svc3._queue) == q_before,
          f'q_before={q_before} q_after={len(svc3._queue)}')
    check('C2 提交被计为丢句（诚实记账）',
          svc3.n_dropped > d_before,
          f'n_dropped {d_before} -> {svc3.n_dropped}')
    svc3.close()

    # ── [D] worker 崩溃时在途句子不得悬挂 ─────────────────────────────
    print()
    print('[D] worker 崩溃 ⇒ 在途句子必须清掉（drain 不得超时）')
    logs_d = []
    svc4 = new_service(logs_d)
    svc4.start()
    check('D0 worker 到 ready', wait_state(svc4, ('ready',)), f'state={svc4.state}')
    # 让 worker 收到一条 synth 但**不回 played**（模拟在途），
    # 然后杀掉 worker ⇒ 在途句子永远等不到结果。
    svc4.submit('在途的句子', seg=0)
    t0 = time.time()
    while time.time() - t0 < 10 and 0 not in svc4._inflight:
        time.sleep(0.05)
    check('D1 句子已标记为在途', 0 in svc4._inflight,
          f'inflight={sorted(svc4._inflight)}')
    # 杀掉 worker（桩 worker 不回 played ⇒ 模拟崩溃）
    try:
        svc4.proc.kill()
    except Exception:
        pass
    t0 = time.time()
    while time.time() - t0 < 20 and svc4.n_played < 1 and svc4.state != 'error':
        time.sleep(0.05)
    time.sleep(1.0)
    t_drain = time.time()
    drained = svc4.drain(timeout=15.0)
    drain_s = time.time() - t_drain
    check('D2 drain() 能排空（修复前 pending 悬挂 ⇒ 必超时）',
          drained, f'drained={drained} 用时 {drain_s:.1f}s')
    check('D3 drain 未长时间空等（< 8 s）', drain_s < 8.0, f'{drain_s:.1f}s')
    try:
        svc4.close()
    except Exception:
        pass

    print()
    print('=' * 72)
    print(f'结论：{"PASS" if not FAIL else "FAIL " + str(FAIL)}')
    print('=' * 72)
    try:
        os.remove(STUB_PATH)
    except OSError:
        pass
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
