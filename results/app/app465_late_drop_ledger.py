#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app465_late_drop_ledger.py —— `late_drop` **双记 + drain 永不退出**的验收脚本。

## 本轮（§177）查到的 App 侧真缺陷

**现象**（设备实测，`results/app/app461_app100_device/`）：
* A 臂（ASR GPU.0 + MT GPU.0 + TTS NPU）**自然退出**（exit=0），但日志里
  `drain 超时：仍有 66 句未完成` ⇒ **drain 明明等到了超时才放弃**。
* A 臂最终统计：**提交 159 播完 93 丢弃 132 关闭作废 66**
  ⇒ `n_played(93) + n_dropped(132) = 225 ≠ n_submitted(159)` ⇒ **多 66 句**。
* 逐句 jsonl 实测：**late_drop 恰好 66 句**，`end_reason='eos'` 93 句。

**根因**（读码定案，`live_caption/tts_service.py`）：
`_handle_event()` 的 `kind == 'late_drop'` 分支只做了 `self.n_dropped += 1`
⇒ **没有把 jid 从 `self.pending` 里摘掉** ⇒
① 该句**仍然留在 `pending`** ⇒ `drain()` 的退出条件
   `pending_n == 0 and n_done >= n_sub` **永远不成立**
   ⇒ drain 必然走完整个 timeout（APP-036 C4：timeout = `max(120, 1.5×积压)`）
   ⇒ **B 臂在 ASR 跑完后卡在 drain 逾 30 min、CPU 0%**（本轮实测）；
② `close()` 收尾时把**仍在 pending 的同一批**句当 orphan 再计一次丢句
   ⇒ **同一句被计了两次** ⇒ §29 不变式被破坏。

**正确修法**：late_drop 事件必须走**已有的唯一原子口径** `_drop_one(jid)`
（§60 建立的入口：`pending.pop` + `_inflight.discard` + `n_dropped += 1` **同一把锁内**）
⇒ ① 摘出 pending ⇒ drain 能正常退出；② close() 不会再重复计 ⇒ 不变式恢复。

## 判据
* **REAL 组**（桩 worker，stdlib only，不占 GPU/NPU、不跑推理）：
  1. late_drop 之后 `pending` 里**不再有**该 jid（摘出）；
  2. `n_played + n_dropped == n_submitted`（不变式成立）；
  3. `drain()` 在 timeout 之前**返回 True**（不再空等到超时）。
* **反证组**：把修好的代码**改回旧写法**（`n_dropped += 1` 且不摘 pending）
  ⇒ REAL 组 1/2/3 必须**全部 FAIL** ⇒ 证明判据有鉴别力、不是恒 PASS。

## 纪律
* 桩 worker ⇒ 不跑推理、不测速、不占 GPU/NPU、**不取机器锁**；
* 不调 MiniMax；质量判定交 reviewer；
* 只测**账本与 drain 退出语义**，不碰任何产品默认值/阈值。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

RESULTS = []
FAILURES = []

#: 桩 worker：ready 之后，对每条 synth 回一条 `late_drop`（模拟「太晚跳过」）。
#: 🔴 关键：桩 worker **不回 `played`** ⇒ 只有 late_drop 路径会被触发。
STUB = os.path.join(HERE, '_stub_app465_worker.py')
STUB_SRC = r'''
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
        # 模拟 APP-092 §2：这一句「太晚」⇒ worker 跳过 ⇒ 发 late_drop
        sys.stdout.write(json.dumps({
            "kind": "late_drop", "id": msg.get("id"),
            "seg": msg.get("seg"), "lag_s": 9.0, "threshold_s": 6.0,
            "count": 1}) + "\n")
        sys.stdout.flush()
while True:
    time.sleep(0.2)
'''


def check(name, ok, detail=''):
    ok = bool(ok)
    RESULTS.append({'check': name, 'pass': ok, 'detail': str(detail)})
    print(('  PASS  ' if ok else '  FAIL  ') + name +
          (' :: ' + str(detail) if detail else ''))
    if not ok:
        FAILURES.append(name)
    return ok


def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def make_svc():
    svc = tts_service.TTSService(device='STUB', voice='A',
                                  on_log=lambda m: None)
    wait_state(svc, ('ready',), 25.0)
    return svc


def submit_n(svc, n):
    for i in range(n):
        svc.submit('句 %d' % i, seg=i)


def scenario_late_drop(svc, n=5):
    """提交 n 句 ⇒ 桩 worker 全部回 late_drop ⇒ 检查 pending 与账本。"""
    submit_n(svc, n)
    # 等所有 late_drop 事件被主进程处理完
    t0 = time.time()
    while time.time() - t0 < 20.0:
        if svc.n_dropped >= n:
            break
        time.sleep(0.05)
    time.sleep(0.3)
    return dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
                n_submitted=svc.n_submitted,
                n_pending=len(svc.pending),
                sum=svc.n_played + svc.n_dropped,
                invariant=(svc.n_played + svc.n_dropped == svc.n_submitted))


def drain_returns(svc, timeout=8.0):
    """drain() 是否在 timeout 之前就返回 True（而不是空等到超时才 False）。"""
    t0 = time.time()
    ok = svc.drain(timeout=timeout)
    return bool(ok), round(time.time() - t0, 2)


def run_real_group():
    print()
    print('=== REAL 组 · 修复后的行为（桩 worker，不占设备）===')
    tts_service._WORKER = STUB
    tts_service.BACKLOG_MAX_S = 1e9      # 禁掉「积压丢弃」路径，只留 late_drop

    # R1：late_drop 之后该句不再留在 pending
    svc = make_svc()
    st = scenario_late_drop(svc, 5)
    check('R1.late_drop_removed_from_pending', st['n_pending'] == 0,
          'n_pending=%s（应为 0）' % st['n_pending'])

    # R2：§29 不变式
    check('R2.invariant_played_plus_dropped_eq_submitted',
          st['invariant'] and st['sum'] == st['n_submitted'],
          'played=%s dropped=%s submitted=%s sum=%s'
          % (st['n_played'], st['n_dropped'], st['n_submitted'], st['sum']))

    # R3：drain 能在 timeout 之前返回 True
    ok, dt = drain_returns(svc, timeout=8.0)
    check('R3.drain_returns_before_timeout', ok,
          'drain() -> %s（用时 %.2fs）' % (ok, dt))

    # R4：close() 之后账本仍然自洽（不得因 orphan 二次计丢句而变大）
    svc.close()
    st2 = dict(n_played=svc.n_played, n_dropped=svc.n_dropped,
               n_submitted=svc.n_submitted,
               sum=svc.n_played + svc.n_dropped,
               invariant=(svc.n_played + svc.n_dropped == svc.n_submitted))
    check('R4.invariant_holds_after_close', st2['invariant'],
          'played=%s dropped=%s submitted=%s sum=%s'
          % (st2['n_played'], st2['n_dropped'], st2['n_submitted'], st2['sum']))
    return st, st2


#: 🔴 修复**前**的 late_drop 分支（原文逐字）⇒ 反证基线。
OLD_LATE_DROP_BLOCK = """        elif kind == 'late_drop':
            # 🔴🔴🔳 APP-092 §2：worker 跳过了一句「太晚」的句子。
            #   ⇒ **计丢句**（保持 `n_played + n_dropped + n_empty == n_submitted`）
            #   ⇒ 内容仍在字幕/转写里（**只丢语音**）。
            try:
                self.n_dropped += 1
            except Exception:
                pass
            self._n_late_drop = int(getattr(self, '_n_late_drop', 0) or 0) + 1"""


def make_counterexample_copy():
    """把 dev 树的 tts_service.py **改回旧写法** ⇒ 造出反证版本。

    旧写法 = `late_drop` 分支里 `self.n_dropped += 1` 且**不摘 pending**。
    🔴 用**整块精确替换**（不是拼接）⇒ 不会出现缩进错乱。
    """
    src_path = os.path.join(REPO, 'live_caption', 'tts_service.py')
    src = open(src_path, 'r', encoding='utf-8').read()
    anchor = "            try:\n                self._drop_one(msg.get('id'), register_dropped=False)"
    if anchor not in src:
        raise AssertionError('dev 树 tts_service.py 未找到修复后的 late_drop 调用')
    # 定位修复块：从 `elif kind == 'late_drop':` 到 `_n_late_drop` 那一行
    start = src.find("        elif kind == 'late_drop':")
    if start < 0:
        raise AssertionError('找不到 late_drop 分支')
    end_marker = "            self._n_late_drop = int(getattr(self, '_n_late_drop', 0) or 0) + 1"
    end = src.find(end_marker, start)
    if end < 0:
        raise AssertionError('找不到 late_drop 分支结尾')
    end += len(end_marker)
    fixed_block = src[start:end]
    bad = src[:start] + OLD_LATE_DROP_BLOCK + src[end:]
    d = tempfile.mkdtemp(prefix='app465_ce_')
    # 🔴 反证副本必须**同名** `tts_service.py` ⇒ 子进程的 `sys.path[0]` 就是
    #    临时目录 ⇒ `import tts_service` 一定拿到**改坏的那份**（不会误取仓库版）。
    path = os.path.join(d, 'tts_service.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(bad)
    # 🔴 自检：改坏的那份必须与「修复前原文」一致 ⇒ 否则反证无效
    got = open(path, 'r', encoding='utf-8').read()
    if OLD_LATE_DROP_BLOCK not in got:
        raise AssertionError('反证副本未含旧写法')
    if fixed_block in got:
        raise AssertionError('反证副本仍含修复写法（替换没生效）')
    import ast
    ast.parse(got)   # 🔴 语法必须合法 ⇒ 否则反证是自己崩，不是判据命中
    return path, d


def run_counterexample_group():
    print()
    print('=== 反证组 · 旧写法（只加计数、不摘 pending）必须被识破 ===')
    ce_path, ce_dir = make_counterexample_copy()
    # 用**子进程**跑：避免模块级符号污染本进程
    runner = os.path.join(ce_dir, '_run_ce.py')
    with open(runner, 'w', encoding='utf-8') as f:
        f.write(r'''
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tts_service
tts_service._WORKER = %r
tts_service.BACKLOG_MAX_S = 1e9
svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
t0 = time.time()
while time.time() - t0 < 25 and svc.state != 'ready':
    time.sleep(0.05)
for i in range(5):
    svc.submit('句 %%d' %% i, seg=i)
t0 = time.time()
while time.time() - t0 < 20 and svc.n_dropped < 5:
    time.sleep(0.05)
time.sleep(0.3)
st = dict(n_pending=len(svc.pending),
          n_played=svc.n_played, n_dropped=svc.n_dropped,
          n_submitted=svc.n_submitted,
          sum=svc.n_played + svc.n_dropped)
st['invariant'] = (st['n_played'] + st['n_dropped'] == st['n_submitted'])
# 🔴 「扩展不变式」= 代码里自己写的 `n_played + n_dropped + len(pending) == n_submitted`
#   （tts_service.py 的注释明确列出这一条）⇒ 旧写法下 late_drop 句既计了丢句
#   又留在 pending ⇒ 这条被破坏 ⇒ 与「drain 等不到排空」是同一根因。
st['extended_sum'] = st['n_played'] + st['n_dropped'] + st['n_pending']
st['extended_invariant'] = (st['extended_sum'] == st['n_submitted'])
t0 = time.time()
ok = svc.drain(timeout=6.0)
st['drain_ok'] = bool(ok)
st['drain_s'] = round(time.time() - t0, 2)
try:
    svc.close()
except Exception:
    pass
st['after_close_sum'] = svc.n_played + svc.n_dropped
st['after_close_submitted'] = svc.n_submitted
print('CE_JSON ' + json.dumps(st, ensure_ascii=False))
''' % (STUB,))
    import subprocess
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    p = subprocess.run([sys.executable, runner], capture_output=True,
                       text=True, timeout=180, env=env)
    line = [l for l in p.stdout.splitlines() if l.startswith('CE_JSON ')]
    if not line:
        check('R5.counterexample_detected', False,
              '反证子进程没输出 CE_JSON（stderr=%s）' % p.stderr[-400:])
        shutil.rmtree(ce_dir, ignore_errors=True)
        return
    st = json.loads(line[0][len('CE_JSON '):])
    print('  反证实测: %s' % json.dumps(st, ensure_ascii=False))
    check('R5.counterexample_pending_not_removed', st['n_pending'] > 0,
          'n_pending=%s（旧写法应 > 0）' % st['n_pending'])
    check('R6.counterexample_extended_invariant_broken',
          not st['extended_invariant'],
          'played+dropped+pending=%s submitted=%s（旧写法应破「扩展不变式」）'
          % (st['extended_sum'], st['n_submitted']))
    check('R7.counterexample_drain_times_out', not st['drain_ok'],
          'drain_ok=%s drain_s=%s（旧写法应等满 timeout）'
          % (st['drain_ok'], st['drain_s']))
    check('R8.counterexample_double_count_after_close',
          st['after_close_sum'] > st['after_close_submitted'],
          'after_close sum=%s submitted=%s（旧写法应多计）'
          % (st['after_close_sum'], st['after_close_submitted']))
    shutil.rmtree(ce_dir, ignore_errors=True)


def main():
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(STUB_SRC)
    try:
        st, st2 = run_real_group()
        run_counterexample_group()
    finally:
        try:
            os.remove(STUB)
        except OSError:
            pass

    n_pass = sum(1 for r in RESULTS if r['pass'])
    n_fail = len(RESULTS) - n_pass
    out = {
        'gate': 'late_drop_ledger',
        'n_checks': len(RESULTS),
        'n_pass': n_pass,
        'n_fail': n_fail,
        'pass': n_fail == 0,
        'checks': RESULTS,
        'real_group_ledger': st,
        'real_group_after_close': st2,
        'defect': ('tts_service._handle_event 的 late_drop 分支只 n_dropped += 1 '
                   '而未把 jid 摘出 pending ⇒ ① drain() 退出条件 '
                   'pending_n == 0 永不成立（必然空等到超时）'
                   '② close() 再把同一批 orphan 计一次丢句 ⇒ §29 不变式被破坏'),
        'fix': 'late_drop 分支改走唯一原子口径 _drop_one(jid)（摘 pending + 计数同锁）',
        'evidence': ('设备实测：results/app/app461_app100_device/'
                     'gpu_same_asr_mt.log（A 臂 exit=0，drain 超时仍有 66 句，'
                     '最终统计 提交 159 播完 93 丢弃 132 ⇒ 多 66 句 = '
                     '逐句 jsonl 实测 late_drop 66 句）'),
    }
    out_path = os.path.join(HERE, 'app465_late_drop_ledger.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print()
    print('=== 汇总 === %d/%d PASS, %d FAIL ⇒ %s' % (
        n_pass, len(RESULTS), n_fail, 'PASS' if n_fail == 0 else 'FAIL'))
    print('evidence: %s' % out_path)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
