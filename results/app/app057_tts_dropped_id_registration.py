#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app057_tts_dropped_id_registration.py —— §47 的**验收 + 反证**脚本。

## 本轮修的缺陷类别：**「已计丢句」必须登记进 `_dropped_ids`**

§30 建立了不变式 `n_played + n_dropped == n_submitted`，
并引入 `_dropped_ids`（=「已计丢句、但 worker 可能仍会产出事件」的 jid 集合）
来**唯一**处理「丢了又播」的竞态。

🔴🔴 但 `_dropped_ids` 的**登记**只发生在**积压丢弃**（`_update_backlog`）
和**显式 cancel** 两处 ⇒ **另外两条「放弃该句」的路径漏了登记**：

### 缺陷 ①：`close()` 的孤儿句**没登记**

`close()`（停 TTS / 换设备 / 换音色 / 退出，四条路径都调）把在途句子
`pending` 清掉 + `n_dropped += len(orphan)` ⇒ 但**没有** `orphan` 进 `_dropped_ids`。

🔴 而 §31 自己的注释就写明「worker 此刻**还活着**（quit 在后面才发）
⇒ 它可能在这段时间里回一条 `played`」⇒
迟到 `played` 到达时 `was_dropped = False` ⇒ 只 `n_played += 1`（**不减** `n_dropped`）
⇒ 同一句「丢了」又「播了」⇒ **sum 比 submitted 多 1** ⇒ 不变式破坏。

### 缺陷 ②：worker 级 `error` **既清空 `_dropped_ids`、又不登记孤儿**

`tts_service.py::_handle_event` 的 worker 级 error 分支：
① `self._dropped_ids.clear()` ⇒ **毁掉 §30 的积压丢弃标记**
   ⇒ 迟到的 `played` 不再被识别为「已丢弃」⇒ 双记；
② 孤儿句**只计丢句、不登记** ⇒ 同缺陷①；
③ 🔴 **前提事实错误**：注释写「worker 已死 ⇒ 在途与待发的句子都不会再有结果」，
   但 worker 级 error 的两个产地
   （`tts_worker.py` L339 `播放设备打开失败` / L1004 `模型加载失败`）
   **都不会让 worker 进程退出** ⇒ 主循环 `for line in sys.stdin` 继续跑
   ⇒ 它仍会为在途句子回 `played`（设备没开时 `synth()` 仍 emit `played`）
      或句子级 `error`（模型没加载时 `synth()` emit 带 id 的 error）
   ⇒ **每个孤儿句都会被重复计数**。

## 判定口径

- **REAL** 组：修复后必须全 PASS；
- **反证**组：用**修复前的固定 commit** 在**子进程**里跑同样的场景
  ⇒ 必须**复现**不变式被破坏 ⇒ 证明缺陷**曾真实存在**（不是嘴说）；
- 总判定 = REAL 全过 **且** 反证全命中。

⚠️ 反证基线**不能用 `HEAD`**（提交后 HEAD 就是修复版 ⇒ 反证永远落空）
⇒ 用固定 commit SHA `5b99bfd`（= §31 的提交，**本缺陷仍未修**）。

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
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

REAL_FAIL = []
EVIDENCE = {}
STUB = os.path.join(HERE, '_stub_app057_worker.py')

# 🔴 **反证基线**：§31 的提交（本缺陷类别**尚未**修）
BASELINE_COMMIT = '5b99bfd'

# 桩 worker：ready 之后**不回 played**（句子永远在途）
# 🔴 stdin EOF 后必须继续活着 ⇒ 否则 worker 退出 ⇒ 触发自动重启
STUB_ALIVE = r'''
import sys, json, time
sys.stdout.write(json.dumps({"kind": "ready", "device": "STUB", "voice": "A"}) + "\n")
sys.stdout.flush()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if msg.get("cmd") == "quit":
        sys.exit(0)
    if msg.get("cmd") == "synth":
        pass          # 故意**不**回 played ⇒ 句子永远在途
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
    wait_state(svc, ('ready',), 25.0)
    return svc


def invariant(svc):
    return svc.n_played + svc.n_dropped == svc.n_submitted


def sums(svc):
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted,
                sum=svc.n_played + svc.n_dropped,
                invariant=invariant(svc))


# ══════════════════════════════════════════════════════════════════════
# [A] 缺陷①：`close()` 的孤儿句未登记 ⇒ 迟到 `played` 双记
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print()
    print('[A] close() 之后到达的迟到 played 必须**改记为已播**（不得双记）')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = make_svc()
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)
    real('A0 前置：3 句已提交且在途',
         svc.n_submitted == 3 and len(svc.pending) == 3,
         f'submitted={svc.n_submitted} pending={len(svc.pending)}')

    svc.close()
    real('A1 close() 后不变式成立（清场即计丢句）', invariant(svc), str(sums(svc)))
    real('A2 close() 把 3 句孤儿计为丢句',
         svc.n_dropped == 3 and svc.n_played == 0, str(sums(svc)))
    real('A3 close() 后孤儿句**已登记**进 _dropped_ids（迟到 played 才能改记）',
         set(svc.pending.keys()) == set() and 1 in svc._dropped_ids and 2 in svc._dropped_ids,
         f'_dropped_ids={sorted(svc._dropped_ids)}')

    # 🔴 worker 此刻**还活着**（quit 在 close() 清理**之后**才发）
    #   ⇒ 它可能在这段时间里回一条 `played`（模拟真实竞态）
    svc._handle_event({'kind': 'played', 'id': 1})
    real('A4 迟到 played 后不变式仍成立', invariant(svc), str(sums(svc)))
    real('A5 迟到 played 被**改记为已播**（n_dropped 减 1 / n_played 加 1）',
         svc.n_played == 1 and svc.n_dropped == 2, str(sums(svc)))
    EVIDENCE['A_close_late_played'] = sums(svc)


# ══════════════════════════════════════════════════════════════════════
# [B] 缺陷②：worker 级 error **清空 `_dropped_ids`** ⇒ 毁掉 §30 的标记
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print()
    print('[B] worker 级 error **不得清空** `_dropped_ids`（§30 的积压丢弃标记要保留）')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = make_svc()
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)

    # 模拟「积压丢弃」：§30 的登记路径
    with svc.lock:
        svc.pending.pop(0, None)
        svc._inflight.discard(0)
        svc._dropped_ids.add(0)
    svc.n_dropped += 1
    real('B0 前置：jid 0 已按积压丢弃并登记',
         0 in svc._dropped_ids and svc.n_dropped == 1, str(sums(svc)))

    # worker 级 error（**不带 id**）—— 与 `tts_worker.py` L339 / L1004 同形
    svc._handle_event({'kind': 'error', 'message': '播放设备打开失败：boom'})
    real('B1 worker 级 error 后不变式成立', invariant(svc), str(sums(svc)))
    real('B2 worker 级 error **未清空** `_dropped_ids`（jid 0 的标记还在）',
         0 in svc._dropped_ids,
         f'_dropped_ids={sorted(svc._dropped_ids)}')
    real('B3 worker 级 error 的孤儿句**已登记**（迟到事件不会重复计数）',
         1 in svc._dropped_ids and 2 in svc._dropped_ids,
         f'_dropped_ids={sorted(svc._dropped_ids)}')
    EVIDENCE['B_worker_error'] = sums(svc)


# ══════════════════════════════════════════════════════════════════════
# [C] 缺陷②续：worker 级 error 之后到达的**句子级** error 不得重复计丢句
#   （worker 没死 ⇒ 模型加载失败时 `synth()` 会 emit 带 id 的 error）
# ══════════════════════════════════════════════════════════════════════
def group_c():
    print()
    print('[C] worker 级 error 之后的迟到句子级 error 不得**重复**计丢句')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = make_svc()
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)

    svc._handle_event({'kind': 'error', 'message': '模型加载失败：boom'})
    real('C1 worker 级 error 后不变式成立', invariant(svc), str(sums(svc)))

    # 🔴 worker **仍然活着** ⇒ 它会对在途句子逐句回句子级 error（带 id）
    for i in range(3):
        svc._handle_event({'kind': 'error', 'message': '没有可用的音色', 'id': i})
    real('C2 迟到句子级 error 后不变式仍成立', invariant(svc), str(sums(svc)))
    real('C3 迟到句子级 error **未重复**计丢句（n_dropped 仍为 3）',
         svc.n_dropped == 3 and svc.n_played == 0, str(sums(svc)))
    EVIDENCE['C_late_sentence_error'] = sums(svc)


# ══════════════════════════════════════════════════════════════════════
# [D] 正常路径**不得回归**（无丢弃时 played 正常计数）
# ══════════════════════════════════════════════════════════════════════
def group_d():
    print()
    print('[D] 正常路径：played 正常计数，不变式成立（不得回归）')

    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9

    svc = make_svc()
    for i in range(3):
        svc.submit('第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)
    for i in range(3):
        svc._handle_event({'kind': 'played', 'id': i})
    real('D1 正常 3 句全播 ⇒ n_played=3 / n_dropped=0',
         svc.n_played == 3 and svc.n_dropped == 0, str(sums(svc)))
    real('D2 不变式成立', invariant(svc), str(sums(svc)))
    svc.close()
    EVIDENCE['D_normal'] = sums(svc)


# ══════════════════════════════════════════════════════════════════════
# [E] 反证：修复前的固定 commit **确实**破坏不变式（缺陷曾真实存在）
# ══════════════════════════════════════════════════════════════════════
PROBE = r'''
import importlib.util, json, os, sys, time
from importlib.machinery import SourceFileLoader
mod_path, worker = sys.argv[1], sys.argv[2]
loader = SourceFileLoader("old_tts_service", mod_path)
spec = importlib.util.spec_from_loader("old_tts_service", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
m._WORKER = worker
m.BACKLOG_MAX_S = 1e9

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

out = {}

# ── 场景 1：close() 之后迟到 played ──────────────────────────────
svc = m.TTSService(device="STUB", voice="A", on_log=lambda x: None)
wait_state(svc, ("ready",))
for i in range(3):
    svc.submit("s%d" % i, seg=i)
wait_for(lambda: len(svc.pending) == 3)
svc.close()
before = svc.n_played + svc.n_dropped
svc._handle_event({"kind": "played", "id": 1})
out["close_late_played"] = dict(
    n_played=svc.n_played, n_dropped=svc.n_dropped,
    n_submitted=svc.n_submitted,
    sum=svc.n_played + svc.n_dropped,
    broken_after_late_played=(svc.n_played + svc.n_dropped != svc.n_submitted),
    sum_before_late=before)

# ── 场景 2：worker 级 error 之后迟到句子级 error ──────────────────
svc2 = m.TTSService(device="STUB", voice="A", on_log=lambda x: None)
wait_state(svc2, ("ready",))
for i in range(3):
    svc2.submit("t%d" % i, seg=i)
wait_for(lambda: len(svc2.pending) == 3)
svc2._handle_event({"kind": "error", "message": "模型加载失败：boom"})
for i in range(3):
    svc2._handle_event({"kind": "error", "message": "没有可用的音色", "id": i})
out["worker_error_late_sentence_error"] = dict(
    n_played=svc2.n_played, n_dropped=svc2.n_dropped,
    n_submitted=svc2.n_submitted,
    sum=svc2.n_played + svc2.n_dropped,
    broken=(svc2.n_played + svc2.n_dropped != svc2.n_submitted))
svc2.close()
svc.close()
print(json.dumps(out, ensure_ascii=False))
'''


def group_e():
    print()
    print('[E] 反证：修复前的固定 commit **确实**破坏不变式（缺陷曾真实存在）')

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
        real('E0 反证：修复前源码可取', False, '取不到 %s' % BASELINE_COMMIT)
        return

    old_mod = os.path.join(HERE, '_old_tts_service_s47.py')
    probe = os.path.join(HERE, '_probe_old_s47.py')
    with open(old_mod, 'w', encoding='utf-8', newline='') as f:
        f.write(old_src)
    with open(probe, 'w', encoding='utf-8') as f:
        f.write(PROBE)
    try:
        r = subprocess.run([sys.executable, probe, old_mod, STUB],
                           capture_output=True, text=True, timeout=180)
        try:
            out = json.loads((r.stdout or '').strip().splitlines()[-1])
        except Exception:
            out = {}
            print('  [warn] 反证探针无输出：', (r.stdout or '')[-500:],
                  (r.stderr or '')[-500:])
        a = out.get('close_late_played') or {}
        b = out.get('worker_error_late_sentence_error') or {}
        # ⚠️ 这两条是「证明缺陷曾经存在」⇒ 命中是**预期**的
        real('E1 修复前：close() 后迟到 played **确实**破坏不变式（反证）',
             a.get('broken_after_late_played') is True,
             f'修复前 sum={a.get("sum")} submitted={a.get("n_submitted")}')
        real('E2 修复前：worker 级 error 后迟到句子级 error **确实**破坏不变式（反证）',
             b.get('broken') is True,
             f'修复前 sum={b.get("sum")} submitted={b.get("n_submitted")}')
        EVIDENCE['E_baseline'] = dict(commit=BASELINE_COMMIT,
                                      close_late_played=a,
                                      worker_error=b)
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
    print('§47 验收：「已计丢句」必须登记进 _dropped_ids（不变式不得被破坏）')
    print('（桩 worker，无推理；不跑测速、不占 GPU、不调 MiniMax）')
    print('=' * 74)

    try:
        group_a()
        group_b()
        group_c()
        group_d()
        group_e()
    finally:
        tts_service.BACKLOG_MAX_S = old_max

    print()
    print('=' * 74)
    ok = not REAL_FAIL
    print(f'REAL 失败项：{REAL_FAIL if REAL_FAIL else "无"}')
    print('总判定：' + ('PASS —— REAL 全过' if ok else 'FAIL'))

    ev_path = os.path.join(HERE, 'app057_tts_dropped_id_registration_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, evidence=EVIDENCE,
                       baseline_commit=BASELINE_COMMIT,
                       verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
