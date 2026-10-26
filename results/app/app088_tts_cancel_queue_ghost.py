#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app088 — §58 的**验收 + 反证**脚本。

## 本轮修的缺陷类别：**「cancel() 没清待发队列 ⇒ 幽灵在途句 ⇒ 崩溃时双记」**

### 缺陷：`TTSService.cancel()` 只清 `pending` / `_inflight`，**漏了 `_queue`**

`submit()` 在 **worker 还没 ready** 时（模型加载中，实测 4~24 s）会把命令
放进**待发队列 `_queue`**（`tts_service.py` 的 `else: self._queue.append(cmd)`），
等 `ready` 事件后由 `_flush_queue()` 补发。

而 `cancel()` 原来只清两处：

```python
with self.lock:
    was_pending = self.pending.pop(jid, None) is not None
    self._inflight.discard(jid)
    # ⚠️ 没有从 self._queue 里摘掉！
```

⇒ 由此产生**两个真缺陷**：

#### ① 🔴 幽灵在途句（Ghost in-flight）

`cancel(jid)` 之后，这条命令**仍然留在 `_queue` 里** ⇒ worker ready 后
`_flush_queue()` **把它重新下发** ⇒ worker 按 `synth` 正常合成并**真的播出来**。

但主进程这边：`pending` 里已经没有它、`_inflight` 里也没有它 ⇒
可 `_flush_queue()` 又把它 `add` 进 `_inflight` ⇒ 于是 `_inflight` 里
多了一个**从未真正在途**的 jid（**幽灵**）。

🔴 **用户可见后果**：用户点了「⏹ 停止朗读」，**这句还是会被念出来**。

#### ② 🔴 崩溃时双记（不变式被破坏）

worker 崩溃时 `_on_worker_exit()` 取：

```python
lost = sorted(self._inflight)
self._inflight.clear()
for jid in lost:
    self.pending.pop(jid, None)
...
self.n_dropped += len(lost)
```

⇒ **幽灵 jid 被当成「在途丢失」** ⇒ `n_dropped` **再 +1**
⇒ 同一句被丢了**两次**（一次是 `cancel()`，一次是「崩溃在途丢失」）
⇒ 不变式 `n_played + n_dropped + len(pending) == n_submitted` 被破坏。

**实测（修复前）**：3 句提交 → cancel 第 0 句 → ready 后 `_inflight=[0]`（幽灵）
→ worker 崩溃 ⇒ `n_dropped=2 / n_played=2 / submitted=3`
⇒ **sum(4) ≠ submitted(3)** ⇒ 不变式破坏。

### 与 §57 的区别（为什么这是**另一个**破口）

- §57：`cancel()` **无条件** `n_dropped += 1` ⇒ **同一句被 cancel 两次**就双记；
- §58（本条）：`cancel()` **漏清 `_queue`** ⇒ **从未在途的句**被当成「在途丢失」。

两者都会让 `n_dropped` 虚高，但**根因不同、修的位置不同** ⇒ 必须分别修。

### 修法

1. `cancel()` 在**同一把锁内**把 jid 从 `_queue` 里摘掉
   （用 `_queued_ids` 这个 set 做 O(1) 成员判断；`_queue` 是 list 要保顺序）；
2. `_flush_queue()` 加**第二道保险**：**跳过已不在 `pending` 里的 jid**
   ⇒ 绝不下发一句「已经被定案（已丢）」的译文。

### 判定口径

- **REAL** 组：修复后必须全 PASS；
- **反证**组：用**修复前的固定 commit** 在**子进程**里跑同样的场景
  ⇒ 必须**复现**不变式被破坏 ⇒ 证明缺陷**曾真实存在**（不是嘴说）；
- 总判定 = REAL 全过 **且** 反证全命中。

⚠️ 反证基线**不能用 `HEAD`**（提交后 HEAD 就是修复版 ⇒ 反证永远落空）
⇒ 用固定 commit SHA `e06f8ee`（= §57 的提交，**本缺陷仍未修**）。

## 纪律

- **桩 worker**：不跑推理、不测速、不占 GPU、不取机器锁；
- 桩 worker **忠实复刻真实 worker 的 cancel 语义**
  （收到 `cancel` → 记入 `_cancelled`；收到 `synth` 时若已 cancelled
  → **跳过合成、不回 `played`**）⇒ 见 `tts_worker.py` L942 / L1463；
- `tts_service` 只 import stdlib ⇒ 安全；
- 不调 MiniMax；质量判定交 reviewer。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

REAL_FAIL = []
EVIDENCE = {}
STUB = os.path.join(HERE, '_stub_app088_worker.py')

# 🔴 **反证基线**：§57 的提交（本缺陷类别**尚未**修）
BASELINE_COMMIT = 'e06f8ee'

# 🔴 桩 worker：**忠实复刻真实 worker 的 cancel 语义**
#   - ready 之前有延迟（模拟模型加载中 ⇒ 命令会进 `_queue`）；
#   - 收到 `cancel` → 记入 `_cancelled`；
#   - 收到 `synth` 时若该 jid 已 cancelled → **跳过合成、不回 `played`**
#     （真实 worker：`tts_worker.py` L942 `if self._is_cancelled(jid): return`）
STUB_ALIVE = r'''
import sys, json, time, os
_cancelled = set()
def emit(d):
    sys.stdout.write(json.dumps(d) + "\n")
    sys.stdout.flush()
time.sleep(float(os.environ.get("STUB_READY_DELAY", "4")))
emit({"kind": "ready", "device": "STUB", "voice": "A"})
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    c = msg.get("cmd")
    if c == "quit":
        sys.exit(0)
    if c == "cancel":
        jid = msg.get("id")
        _cancelled.add(jid)
        emit({"kind": "dropped", "id": jid, "count": 1})
    elif c == "synth":
        jid = msg.get("id")
        if jid in _cancelled:
            continue          # ← 真实 worker 语义：跳过、**不回 played**
        emit({"kind": "played", "id": jid, "dur_s": 1.0, "latency_s": 0.1,
              "telemetry": {"peak": 0.5, "rms_dbfs": -18.0,
                            "read_delta": 24000}})
while True:
    time.sleep(0.2)
'''


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def wait_for(fn, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False


def make_svc():
    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    wait_state(svc, ('ready',), 30.0)
    return svc


def invariant(svc):
    """🔴 正确的「守恒」判据。

    ⚠️ **不能**只写 `n_played + n_dropped == n_submitted` ——
    句子还**在途**（`pending` 里）时两边都会少算 ⇒ 那是正常的，不是缺陷。
    ⇒ 正确判据：**每一句提交过的句子，恰好处于「在途 / 已播 / 已丢」三者之一**：

        n_played + n_dropped + len(pending) == n_submitted
    """
    with svc.lock:
        n_pending = len(svc.pending)
    return (svc.n_played + svc.n_dropped + n_pending) == svc.n_submitted


def sums(svc):
    with svc.lock:
        n_pending = len(svc.pending)
        n_queue = len(svc._queue)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                n_queue=n_queue,
                inflight=sorted(svc._inflight),
                sum=svc.n_played + svc.n_dropped,
                invariant=invariant(svc))


# ══════════════════════════════════════════════════════════════════════
# [A] 幽灵在途句：worker 未 ready 时 cancel ⇒ 命令必须从待发队列摘掉
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print()
    print('[A] worker 未 ready 时 cancel ⇒ 不得留下「幽灵在途句」')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9
    os.environ['STUB_READY_DELAY'] = '4'

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc._queue) == 3, 5.0)
    real('A0 前置：worker 未 ready ⇒ 3 条命令在待发队列里',
         len(svc._queue) == 3 and svc.n_submitted == 3, str(sums(svc)))

    svc.cancel(0)
    real('A1 cancel 后待发队列里**没有**这一句',
         all(c.get('id') != 0 for c in svc._queue), str(sums(svc)))
    real('A2 cancel 后待发队列剩 2 条',
         len(svc._queue) == 2, str(sums(svc)))
    real('A3 cancel 仍计 1 句丢句',
         svc.n_dropped == 1, str(sums(svc)))
    real('A4 不变式成立（取消后该句已定案）', invariant(svc), str(sums(svc)))
    EVIDENCE['A_after_cancel'] = sums(svc)

    # 等 ready ⇒ `_flush_queue()` 补发
    wait_state(svc, ('ready',), 25.0)
    time.sleep(1.0)
    real('A5 ready 后 `_inflight` 里**没有**幽灵 jid 0',
         0 not in svc._inflight, 'inflight=%s' % sorted(svc._inflight))
    real('A6 不变式仍成立', invariant(svc), str(sums(svc)))
    EVIDENCE['A_after_ready'] = sums(svc)
    svc.close()


# ══════════════════════════════════════════════════════════════════════
# [B] 崩溃时双记：幽灵 jid 不得被当成「在途丢失」
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print()
    print('[B] worker 崩溃 ⇒ 幽灵 jid 不得被当成「在途丢失」（不变式不得破坏）')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9
    os.environ['STUB_READY_DELAY'] = '4'

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc._queue) == 3, 5.0)
    svc.cancel(0)
    wait_state(svc, ('ready',), 25.0)
    time.sleep(1.0)
    real('B0 前置：其余 2 句已播',
         svc.n_played == 2 and svc.n_dropped == 1, str(sums(svc)))

    # worker 崩溃 ⇒ `_on_worker_exit()` 的 `lost = _inflight`
    svc._restarted = False
    svc._on_worker_exit(1, None)
    real('B1 崩溃后不变式成立', invariant(svc), str(sums(svc)))
    real('B2 丢句数仍为 1（幽灵未被重复计）',
         svc.n_dropped == 1, str(sums(svc)))
    real('B3 不变式：played+dropped+pending == submitted',
         svc.n_played + svc.n_dropped + len(svc.pending) == svc.n_submitted,
         str(sums(svc)))
    EVIDENCE['B_after_crash'] = sums(svc)
    try:
        svc.close()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# [C] 正常路径**不得回归**
# ══════════════════════════════════════════════════════════════════════
def group_c():
    print()
    print('[C] 正常路径：待发队列补发仍要正常下发并计数')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9
    os.environ['STUB_READY_DELAY'] = '4'

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc._queue) == 3, 5.0)
    real('C0 前置：3 条命令在待发队列', len(svc._queue) == 3, str(sums(svc)))
    wait_state(svc, ('ready',), 25.0)
    time.sleep(1.2)
    real('C1 ready 后 3 句都补发并播了',
         svc.n_played == 3, str(sums(svc)))
    real('C2 不变式成立', invariant(svc), str(sums(svc)))
    real('C3 待发队列已清空', len(svc._queue) == 0, str(sums(svc)))
    EVIDENCE['C_normal'] = sums(svc)
    try:
        svc.close()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════
# [D] 反证：修复前的固定 commit **确实**留下幽灵在途句并破坏不变式
# ══════════════════════════════════════════════════════════════════════
PROBE = r'''
import importlib.util, json, os, sys, time
from importlib.machinery import SourceFileLoader
mod_path, worker = sys.argv[1], sys.argv[2]
os.environ["STUB_READY_DELAY"] = "4"
loader = SourceFileLoader("old_tts_service", mod_path)
spec = importlib.util.spec_from_loader("old_tts_service", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
m._WORKER = worker
m.BACKLOG_MAX_S = 1e9

def wait_state(svc, want, timeout=30.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False

def wait_for(fn, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False

out = {}

def inv(svc):
    with svc.lock:
        n_pending = len(svc.pending)
    return (svc.n_played + svc.n_dropped + n_pending) == svc.n_submitted

def snap(svc):
    with svc.lock:
        n_pending = len(svc.pending)
        n_queue = len(svc._queue)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                n_queue=n_queue,
                inflight=sorted(svc._inflight),
                sum=svc.n_played + svc.n_dropped,
                broken=(not inv(svc)))

svc = m.TTSService(device="STUB", voice="A", on_log=lambda x: None)
for i in range(3):
    svc.submit("s%d" % i, seg=i)
wait_for(lambda: len(svc._queue) == 3)
svc.cancel(0)
out["after_cancel"] = snap(svc)
wait_state(svc, ("ready",))
time.sleep(1.2)
out["after_ready"] = snap(svc)
svc._restarted = False
svc._on_worker_exit(1, None)
out["after_crash"] = snap(svc)
try:
    svc.close()
except Exception:
    pass
print(json.dumps(out, ensure_ascii=False))
'''


def group_d():
    print()
    print('[D] 反证：修复前的固定 commit **确实**留下幽灵在途句（缺陷曾真实存在）')

    old_src = None
    try:
        r = subprocess.run(
            ['git', 'show', '%s:live_caption/tts_service.py' % BASELINE_COMMIT],
            cwd=REPO, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=180)
        if r.returncode == 0:
            old_src = r.stdout
    except Exception as e:
        print(f'  [skip] 取不到修复前源码: {e}')

    if not old_src:
        real('D0 反证：修复前源码可取', False, '取不到 %s' % BASELINE_COMMIT)
        return

    old_mod = os.path.join(HERE, '_old_tts_service_s58.py')
    probe = os.path.join(HERE, '_probe_old_s58.py')
    with open(old_mod, 'w', encoding='utf-8', newline='') as f:
        f.write(old_src)
    with open(probe, 'w', encoding='utf-8') as f:
        f.write(PROBE)
    try:
        r = subprocess.run([sys.executable, probe, old_mod, STUB],
                           capture_output=True, text=True, timeout=240)
        try:
            out = json.loads((r.stdout or '').strip().splitlines()[-1])
        except Exception:
            out = {}
            print('  [warn] 反证探针无输出：', (r.stdout or '')[-500:],
                  (r.stderr or '')[-500:])
        a = out.get('after_cancel') or {}
        b = out.get('after_ready') or {}
        c = out.get('after_crash') or {}
        # ⚠️ 这三条是「证明缺陷曾经存在」⇒ 命中是**预期**的
        real('D1 修复前：cancel 后待发队列里**仍留着**这一句（反证）',
             a.get('n_queue') == 3,
             f'修复前 n_queue={a.get("n_queue")}（应为 2）')
        real('D2 修复前：ready 后 `_inflight` 里有幽灵 jid 0（反证）',
             0 in (b.get('inflight') or []),
             f'修复前 inflight={b.get("inflight")}')
        real('D3 修复前：worker 崩溃后不变式**被破坏**（反证）',
             c.get('broken') is True,
             f'修复前 sum={c.get("sum")} submitted={c.get("n_submitted")}')
        EVIDENCE['D_baseline'] = dict(commit=BASELINE_COMMIT,
                                      after_cancel=a, after_ready=b,
                                      after_crash=c)
    finally:
        for p in (old_mod, probe):
            try:
                os.remove(p)
            except Exception:
                pass


def main():
    old_max = tts_service.BACKLOG_MAX_S
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(STUB_ALIVE)

    print('=' * 74)
    print('§58 验收：cancel() 必须清待发队列（不得留「幽灵在途句」）')
    print('（桩 worker，无推理；不跑测速、不占 GPU、不调 MiniMax）')
    print('=' * 74)

    try:
        group_a()
        group_b()
        group_c()
        group_d()
    finally:
        tts_service.BACKLOG_MAX_S = old_max

    print()
    print('=' * 74)
    ok = not REAL_FAIL
    print(f'REAL 失败项：{REAL_FAIL if REAL_FAIL else "无"}')
    print('总判定：' + ('PASS —— REAL 全过' if ok else 'FAIL'))

    ev_path = os.path.join(HERE, 'app088_tts_cancel_queue_ghost_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, evidence=EVIDENCE,
                       baseline_commit=BASELINE_COMMIT,
                       verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
