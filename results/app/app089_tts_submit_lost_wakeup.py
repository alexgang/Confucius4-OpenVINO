#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app089 — §59 的**验收 + 反证**脚本。

## 本轮修的缺陷类别：**`submit()` 的「丢唤醒竞态」⇒ 命令永久滞留 `_queue`**

### 缺陷 A（主）：`submit()` 读状态与入队之间有窗口 ⇒ 命令**永远发不出去**

`submit()` 旧实现分成了**两个临界区**：

```python
with self.lock:                       # ① 临界区
    jid = self._next_id
    self.pending[jid] = ...
    self.n_submitted += 1
    ready = (self.state == 'ready')   # ← 读状态
    dead  = (self.state == 'error')
...
else:
    with self.lock:                   # ② 临界区
        self._queue.append(cmd)       # ← 入队
```

而 `ready` 事件的处理是：

```python
if kind == 'ready':
    self.state = 'ready'              # ← **锁外**
    self._flush_queue()               # ← 快照 `_queue`（当时可能为空）
```

⇒ **丢唤醒（lost wakeup）**：

| 时刻 | 线程 | 动作 |
|---|---|---|
| t1 | App | ① 锁内读到 `state == 'loading'` ⇒ `action='queue'` |
| t2 | 事件 | `state = 'ready'` ⇒ `_flush_queue()` ⇒ 快照 `_queue`（**空的**）⇒ 无事可做 |
| t3 | App | ② 入队 ⇒ 命令**留在 `_queue` 里** |

⇒ worker **已经 ready** ⇒ **再也不会有第二个 `ready` 事件**
⇒ `_flush_queue()` **永远不会再跑**
⇒ 这条命令**永远发不出去**
⇒ `pending[jid]` **永久悬挂** ⇒ `drain()` **必超时**（GUI 白等 30 s / CLI 白等 120 s）
⇒ 🔴 **用户可见后果：这一句译文永远不会被朗读**。

### 缺陷 B（同源）：`_inflight` 登记与「孤儿清理」之间有窗口 ⇒ **幽灵在途句**

`submit()` 的 ① 与「`_inflight.add(jid)`」也分在两个临界区：

```python
if ready:
    with self.lock:                   # ← 另一个临界区
        self._inflight.add(jid)
```

⇒ ① 与它之间，worker 级 error 的**孤儿清理**可能整段跑完
（`pending.clear()` + `_inflight.clear()` + 计丢句）
⇒ 随后再 `add(jid)` ⇒ `_inflight` 里多了一个**从未真正在途**的 jid（**幽灵**）
⇒ worker 崩溃时 `lost = sorted(self._inflight)` 把它算成「在途丢失」
⇒ `n_dropped` **双记** ⇒ 不变式破坏。

### 与 §58 的区别（为什么这是**另一个**破口）

- §58：`cancel()` **漏清 `_queue`** ⇒ **从未在途的句**被当成「在途丢失」（命令**被下发**了）；
- §59（本条）：`submit()` **丢唤醒** ⇒ 命令**根本没被下发**就永久滞留。

两者都会破坏不变式，但**根因不同、修的位置不同** ⇒ 必须分别修。

### 修法

1. **读状态 + 登记在途 / 决定「直接下发 vs 入队」合并到**同一个临界区**；
2. **入队前在同一把锁内复查 `state`** ⇒ 若已 ready 则**自己下发**（不入队）；
3. `ready` 事件的 `self.state = 'ready'` **移进锁内** ⇒ 与 ② 的复查互斥
   ⇒ 「入队」与「补发」**不可能两边都错过**。

### 怎么**确定性**复现（不靠概率）

真实世界里那个窗口只有几微秒宽 ⇒ 靠「多跑几次」抓不到。
⇒ 本脚本用**可注入的锁包装器**：在 `submit()` 的**第一个临界区释放之后**
   （= 窗口的精确位置）**同步**触发 `ready` 事件
   ⇒ 每次都必现 ⇒ 证据可复现。

⚠️ 触发点必须在**释放锁之后**：修复后 `_handle_event('ready')` 自己要取锁
   ⇒ 若在持锁时调用 ⇒ 直接自死锁（那正是修复后的**正确**行为）。

### 判定口径

- **REAL** 组：修复后必须全 PASS；
- **反证**组：用**修复前的固定 commit** 在**子进程**里跑同样的场景
  ⇒ 必须**复现**命令永久滞留 ⇒ 证明缺陷**曾真实存在**（不是嘴说）；
- 总判定 = REAL 全过 **且** 反证全命中。

⚠️ 反证基线**不能用 `HEAD`**（提交后 HEAD 就是修复版 ⇒ 反证永远落空）
⇒ 用固定 commit SHA `421d2d0`（= §58 的提交，**本缺陷仍未修**）。

## 纪律

- **桩 worker**：不跑推理、不测速、不占 GPU、不取机器锁；
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

# 🔴 **包内模式**：用 `--pkg <客户包目录>` ⇒ 直接 import **包内那份**
#   `tts_service.py`（而不是仓库那份）⇒ 验证「包里的那份也是修好的」。
#   ⚠️ 必须**在 import 之前**改 `sys.path` ⇒ 否则 import 到的是仓库那份。
_PKG = None
for _i, _a in enumerate(sys.argv):
    if _a == '--pkg' and _i + 1 < len(sys.argv):
        _PKG = sys.argv[_i + 1]
    elif _a.startswith('--pkg='):
        _PKG = _a.split('=', 1)[1]
if _PKG:
    sys.path.insert(0, os.path.join(_PKG, 'app'))
    print('🔴 包内模式：%s' % os.path.join(_PKG, 'app', 'tts_service.py'))
else:
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

REAL_FAIL = []
EVIDENCE = {}
STUB = os.path.join(HERE, '_stub_app089_worker.py')

# 🔴 **反证基线**：§58 的提交（本缺陷类别**尚未**修）
BASELINE_COMMIT = '421d2d0'

# 🔴 桩 worker：
#   - `STUB_SUPPRESS_READY=1` ⇒ **不发** ready 事件（由测试脚本自己注入）
#   - `STUB_NO_REPLY=1`      ⇒ 收到 synth **不回 played**（模拟 worker 已死）
STUB_ALIVE = r'''
import sys, json, time, os
def emit(d):
    sys.stdout.write(json.dumps(d) + "\n")
    sys.stdout.flush()
if os.environ.get("STUB_SUPPRESS_READY") != "1":
    time.sleep(float(os.environ.get("STUB_READY_DELAY", "4")))
    emit({"kind": "ready", "device": "STUB", "voice": "A"})
no_reply = os.environ.get("STUB_NO_REPLY") == "1"
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
    elif c == "synth":
        if no_reply:
            continue
        jid = msg.get("id")
        emit({"kind": "played", "id": jid, "dur_s": 1.0, "latency_s": 0.1,
              "telemetry": {"peak": 0.5, "rms_dbfs": -18.0,
                            "read_delta": 24000}})
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


def sums(svc):
    with svc.lock:
        n_pending = len(svc.pending)
        n_queue = len(svc._queue)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                n_queue=n_queue,
                inflight=sorted(svc._inflight),
                sum=svc.n_played + svc.n_dropped,
                invariant=(svc.n_played + svc.n_dropped + n_pending)
                          == svc.n_submitted)


def make_gate(svc, fire):
    """返回一个锁包装器：在**第一个临界区释放之后**调用 `fire()`。

    🔴 **为什么在释放之后**：修复后 `_handle_event('ready')` 自己要取锁
       ⇒ 若在持锁时调用 ⇒ 自死锁（那是修复后的**正确**行为）。
       ⇒ 而「释放锁之后」正是真实世界里 `ready` 事件落进窗口的位置。

    ⚠️ 包装器**不改变**锁的语义（仍是同一个 `threading.Lock`）
       ⇒ 被测代码拿到的仍是**非可重入**锁 ⇒ 死锁检测依然有效。
    """

    class _Gate:
        def __init__(self, inner):
            self._inner = inner
            self._n = 0

        def __enter__(self):
            self._inner.acquire()
            self._n += 1
            return self

        def __exit__(self, *a):
            self._inner.release()
            if self._n == 1 and not getattr(self, '_fired', False):
                self._fired = True
                fire()
            return False

        def __getattr__(self, n):
            return getattr(self._inner, n)

    return _Gate(svc.lock)


# ══════════════════════════════════════════════════════════════════════
# [A] 丢唤醒：命令不得永久滞留 `_queue`
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print()
    print('[A] 丢唤醒竞态：ready 恰落在「读状态」与「入队」之间 ⇒ 不得滞留')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9
    os.environ['STUB_SUPPRESS_READY'] = '1'
    os.environ['STUB_NO_REPLY'] = '0'

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    try:
        wait_for(lambda: svc.state == 'loading', 10.0)
        real('A0 前置：worker 处于 loading（模型加载中）',
             svc.state == 'loading', svc.state)

        fired = []

        def fire():
            fired.append(1)
            # 🔴 真实世界里的 `ready` 事件
            svc._handle_event({'kind': 'ready', 'device': 'STUB', 'voice': 'A'})

        svc.lock = make_gate(svc, fire)
        svc.submit('竞态测试句', seg=0)
        svc.lock = svc.lock._inner

        real('A1 注入点确实命中（在第一个临界区之后触发了 ready）',
             len(fired) == 1, 'fired=%d' % len(fired))

        time.sleep(1.5)
        s = sums(svc)
        real('A2 命令**没有**滞留待发队列', s['n_queue'] == 0, str(s))
        real('A3 不变式成立（没有悬挂）', s['invariant'], str(s))
        EVIDENCE['A_after_submit'] = s

        wait_for(lambda: svc.n_played == 1, 15.0)
        s = sums(svc)
        real('A4 这句**真的被播出来了**（没有永远滞留）',
             svc.n_played == 1, str(s))
        real('A5 播完后不变式仍成立', s['invariant'], str(s))

        # 🔴 `drain()` 是用户最直接的感受（收尾时会不会白等）
        t0 = time.time()
        ok = svc.drain(timeout=10.0)
        EVIDENCE['A_drain'] = dict(ok=ok, elapsed=round(time.time() - t0, 2))
        real('A6 `drain()` 正常返回（不超时）', ok is True,
             'elapsed=%.2fs' % (time.time() - t0))
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [B] 幽灵在途句：孤儿清理与 submit() 交错 ⇒ 不得双记
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print()
    print('[B] 幽灵在途句：worker 级 error 的孤儿清理与 submit() 交错 ⇒ 不得双记')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9
    os.environ['STUB_SUPPRESS_READY'] = '1'
    os.environ['STUB_NO_REPLY'] = '1'      # worker 装了但不会回 played

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    try:
        wait_for(lambda: svc.state == 'loading', 10.0)
        real('B0 前置：worker 处于 loading', svc.state == 'loading', svc.state)

        fired = []

        def fire():
            fired.append(1)
            # 🔴 worker 级 error（不带 id）⇒ 触发「孤儿清理」
            svc._handle_event({'kind': 'error', 'message': '注入的 worker 级故障'})

        svc.lock = make_gate(svc, fire)
        svc.submit('幽灵测试句', seg=0)
        svc.lock = svc.lock._inner
        time.sleep(0.6)

        real('B1 注入点确实命中', len(fired) == 1, 'fired=%d' % len(fired))

        # 🔴 模拟 worker 崩溃 ⇒ `_on_worker_exit()` 取 `lost = _inflight`
        svc._restarted = False
        svc._on_worker_exit(1, None)
        time.sleep(0.3)

        s = sums(svc)
        real('B2 不变式成立（没有双记）', s['invariant'], str(s))
        real('B3 没有「幽灵在途句」残留（`_inflight` 为空）',
             s['inflight'] == [], 'inflight=%s' % s['inflight'])
        real('B4 丢句数恰好 1（只算一次）', svc.n_dropped == 1, str(s))
        EVIDENCE['B_after_crash'] = s
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [C] 正常路径**不得回归**
# ══════════════════════════════════════════════════════════════════════
def group_c():
    print()
    print('[C] 正常路径：worker 未 ready 时提交 ⇒ ready 后必须补发')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9
    os.environ.pop('STUB_SUPPRESS_READY', None)
    os.environ['STUB_NO_REPLY'] = '0'
    os.environ['STUB_READY_DELAY'] = '3'

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    try:
        for i in range(3):
            svc.submit('第 %d 句译文' % i, seg=i)
        wait_for(lambda: len(svc._queue) == 3, 5.0)
        s = sums(svc)
        real('C0 前置：3 条命令在待发队列',
             s['n_queue'] == 3 and s['n_submitted'] == 3, str(s))

        wait_state(svc, ('ready',), 25.0)
        wait_for(lambda: svc.n_played == 3, 15.0)
        s = sums(svc)
        real('C1 ready 后 3 句都补发并播了', svc.n_played == 3, str(s))
        real('C2 不变式成立', s['invariant'], str(s))
        real('C3 待发队列已清空', s['n_queue'] == 0, str(s))
        EVIDENCE['C_normal'] = s
    finally:
        try:
            svc.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
# [D] 反证：修复前的固定 commit **确实**丢唤醒（缺陷曾真实存在）
# ══════════════════════════════════════════════════════════════════════
PROBE = r'''
import importlib.util, json, os, sys, time
from importlib.machinery import SourceFileLoader
mod_path, worker = sys.argv[1], sys.argv[2]
os.environ["STUB_SUPPRESS_READY"] = "1"
os.environ["STUB_NO_REPLY"] = "0"
loader = SourceFileLoader("old_tts_service", mod_path)
spec = importlib.util.spec_from_loader("old_tts_service", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
m._WORKER = worker
m.BACKLOG_MAX_S = 1e9

def wait_for(fn, timeout=10.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False

def snap(svc):
    with svc.lock:
        n_pending = len(svc.pending)
        n_queue = len(svc._queue)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted, n_pending=n_pending,
                n_queue=n_queue,
                inflight=sorted(svc._inflight),
                sum=svc.n_played + svc.n_dropped,
                stuck=(n_pending > 0 and svc.n_played == 0),
                broken=((svc.n_played + svc.n_dropped + n_pending)
                        != svc.n_submitted))

svc = m.TTSService(device="STUB", voice="A", on_log=lambda x: None)
wait_for(lambda: svc.state == "loading")

orig_lock = svc.lock

class _Gate:
    def __init__(self, inner):
        self._inner = inner
        self._n = 0
        self._fired = False
    def __enter__(self):
        self._inner.acquire()
        self._n += 1
        return self
    def __exit__(self, *a):
        self._inner.release()
        if self._n == 1 and not self._fired:
            self._fired = True
            svc._handle_event({"kind": "ready", "device": "STUB", "voice": "A"})
        return False
    def __getattr__(self, n):
        return getattr(self._inner, n)

svc.lock = _Gate(orig_lock)
svc.submit("竞态测试句", seg=0)
svc.lock = orig_lock
time.sleep(1.5)
out = {"after_submit": snap(svc)}
# 🔴 收尾：drain() 会不会白等到超时（用户最直接的感受）
t0 = time.time()
out["drain_ok"] = svc.drain(timeout=6.0)
out["drain_elapsed"] = round(time.time() - t0, 2)
try:
    svc.close()
except Exception:
    pass
print(json.dumps(out, ensure_ascii=False))
'''


def group_d():
    print()
    print('[D] 反证：修复前的固定 commit **确实**丢唤醒（命令永久滞留）')

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

    old_mod = os.path.join(HERE, '_old_tts_service_s59.py')
    probe = os.path.join(HERE, '_probe_old_s59.py')
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
        a = out.get('after_submit') or {}
        # ⚠️ 这三条是「证明缺陷曾经存在」⇒ 命中是**预期**的
        real('D1 修复前：命令**永久滞留**待发队列（反证）',
             a.get('n_queue') == 1,
             f'修复前 n_queue={a.get("n_queue")}（应为 0）')
        real('D2 修复前：这句**永远悬挂**（没播出、也没离开 pending）（反证）',
             a.get('stuck') is True,
             f'修复前 played={a.get("n_played")} pending={a.get("n_pending")}')
        real('D3 修复前：`drain()` **超时**（反证）',
             out.get('drain_ok') is False,
             f'修复前 drain_ok={out.get("drain_ok")} '
             f'elapsed={out.get("drain_elapsed")}s')
        EVIDENCE['D_baseline'] = dict(commit=BASELINE_COMMIT,
                                      after_submit=a,
                                      drain_ok=out.get('drain_ok'),
                                      drain_elapsed=out.get('drain_elapsed'))
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
    print('§59 验收：submit() 不得丢唤醒（命令不得永久滞留 _queue）')
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

    ev_path = os.path.join(HERE, 'app089_tts_submit_lost_wakeup_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, evidence=EVIDENCE,
                       baseline_commit=BASELINE_COMMIT,
                       verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
