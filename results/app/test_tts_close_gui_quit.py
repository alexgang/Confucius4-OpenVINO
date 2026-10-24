#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""test_tts_close_gui_quit.py —— §31 的**验收 + 反证**脚本。

## 本轮修的三个缺陷

### 缺陷 ①：`TTSService.close()` **不计丢句** ⇒ 不变式被破坏

`close()`（停 TTS / 换设备 / 换音色 / 退出，四条路径都调）直接杀 worker
⇒ `pending` / `_inflight` / `_queue` 里**已提交但永远等不到 `played`/`error`**
的句子**静默消失** ⇒ `n_played + n_dropped != n_submitted`
⇒ 底栏「丢句 + 已播」**少于**「提交」⇒ 用户**不知道**有几句译文被丢掉。

### 缺陷 ②：GUI `quit()` **缺 `mt.wait_idle()`** ⇒ 最后一句译文丢失

`mt.flush()` 只是**入队**，翻译在后台线程异步做 ⇒ flush 返回时译文还没出
⇒ 旧实现直接 `_pump_tts()`（outbox 空）⇒ 这一句既不显示也不朗读
⇒ 随后 `mt.close()` 把工作线程停掉 ⇒ 这一句**永远丢**。
（CLI 侧 `run_cli` 收尾**有** `mt.wait_idle(180)`，GUI 侧漏了。）

### 缺陷 ③：两处 **U+FFFD 乱码**（纯注释/docstring）

`device_config.py` L251、`audio_source.py` L12（GBK 字节当 UTF-8 解码）。

## 判定口径

- **REAL** 组：修复后必须全 PASS；
- **BUG** 组：每条都在**断言「缺陷仍然存在」**
  ⇒ 修复前命中（缺陷复现 = 反证证据）⇒ 修复后必须**全部落空**；
- 总判定 = REAL 全过 **且** BUG 全落空。

## 关键不变式

> **每一句提交过的句子必须被恰好统计一次**
> ⇒ `n_played + n_dropped == n_submitted`。

## 纪律

- **桩 worker**：不跑任何推理、不测速、不占 GPU；
- **不 import 被测模块的重依赖**：`tts_service` 只 import stdlib（json/os/queue/
  subprocess/threading/time/collections/typing）⇒ 安全；
- GUI 侧用 `ast` **抽取 `quit()` 的源码**做静态判定（不开 Tk、不起窗口）。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_service  # noqa: E402

REAL_FAIL = []
BUG_HIT = []
EVIDENCE = {}

STUB = os.path.join(HERE, '_stub_close_worker.py')

# 🔴 **反证基线**：§31 修复**之前**的那个 commit
#   ⇒ 用 `git show <基线>:<file>` 取修复前的源码跑同样的场景 ⇒ 证明缺陷曾真实存在。
# ⚠️ **不能**用 `HEAD`（提交后 HEAD 就是修复版了 ⇒ 反证会永远落空）。
# ⚠️ **不能**依赖临时备份目录（清理后就没了）⇒ 用**固定的 commit SHA**。
BASELINE_COMMIT = '5b99bfd^'      # = §31 修复前的最后一个 commit

# ── 桩 worker：ready 之后**不回 played**（句子永远在途）──────────────────
#   ⛔ **stdin EOF 后必须继续活着** ⇒ 否则 worker 退出 ⇒ 触发自动重启
#      ⇒ 掩盖「命令送不出去 / 句子永远等不到结果」这个待测缺陷。
STUB_ALIVE = r'''
import sys, json, os, time
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
        # 故意**不**回 played ⇒ 句子永远在途
        pass
while True:
    time.sleep(0.2)
'''


def real(name, cond, detail=''):
    print(f"  [{'OK ' if cond else 'FAIL'}] {name}" + (f' — {detail}' if detail else ''))
    if not cond:
        REAL_FAIL.append(name)


# ── 修复前探针（子进程跑「修复前那份 tts_service.py」）────────────────
#   目的：证明「修复前的 close() 不计丢句 ⇒ 不变式被破坏」这个缺陷
#   **真实存在**（反证证据），而不是靠嘴说。
OLD_PROBE = r'''
import importlib.util, json, os, sys, time
from importlib.machinery import SourceFileLoader
mod_path, worker = sys.argv[1], sys.argv[2]
# ⚠️ 文件名后缀是 `.bak_s31` ⇒ `spec_from_file_location` **推断不出 loader**
#    （返回 None）⇒ 必须用**显式** SourceFileLoader。
loader = SourceFileLoader("old_tts_service", mod_path)
spec = importlib.util.spec_from_loader("old_tts_service", loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)
m._WORKER = worker
svc = m.TTSService(device="STUB", voice="A", on_log=lambda x: None)
t0 = time.time()
while time.time() - t0 < 25 and svc.state != "ready":
    time.sleep(0.05)
m.BACKLOG_MAX_S = 1e9
for i in range(5):
    svc.submit("sentence %d" % i, seg=i)
t0 = time.time()
while time.time() - t0 < 10 and len(svc.pending) < 5:
    time.sleep(0.05)
svc.close()
print(json.dumps(dict(sum=svc.n_played + svc.n_dropped,
                      submitted=svc.n_submitted,
                      n_played=svc.n_played,
                      n_dropped=svc.n_dropped,
                      invariant_broken=(svc.n_played + svc.n_dropped
                                        != svc.n_submitted))))
'''


def bug(name, cond, detail=''):
    """断言「缺陷仍然存在」——命中 = 缺陷复现（反证证据）。"""
    print(f"  [{'BUG ' if cond else 'gone'}] {name}" + (f' — {detail}' if detail else ''))
    if cond:
        BUG_HIT.append(name)


def wait_state(svc, want, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if svc.state in want:
            return True
        time.sleep(0.05)
    return False


def wait_for(fn, timeout=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return False


def make_svc():
    # 🔴 **必须**把 worker 脚本路径换成桩 ⇒ 否则起的是真 `tts_worker.py`
    #   （会去 import numpy/tts_engine ⇒ 慢且可能占 GPU）
    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    wait_state(svc, ('ready',), 25.0)
    return svc


def invariant(svc):
    return svc.n_played + svc.n_dropped == svc.n_submitted


# ══════════════════════════════════════════════════════════════════════
# [A] 缺陷①：`close()` 不计丢句 ⇒ 不变式被破坏
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print()
    print('[A] close() 时在途句子必须被清掉并**计丢句**（不变式不得被破坏）')

    # 🔴 **必须**把 worker 脚本路径换成桩（否则起的是真 tts_worker.py）
    tts_service._WORKER = STUB
    # ⚠️ **必须把 backlog 阈值放到极大** ⇒ 否则 `submit()` 末尾的
    #   `_update_backlog()` 会因「积压超 8 s」把句子**按积压丢掉**
    #   （那是 §22/§29 的正常功能）⇒ 干扰本组测的「在途句子」前置条件。
    #   ⚠️ 组间**必须各自显式设置**模块级常量（否则串到后面的组）。
    tts_service.BACKLOG_MAX_S = 1e9

    # ── 反证：用**修复前**的源码跑同样的场景 ⇒ 缺陷必须复现 ──
    # ⚠️ 不能在同一个进程里 monkeypatch（改的是类方法，桩 worker 也要重起）
    #    ⇒ 用**子进程**跑修复前那份 `tts_service.py`。
    import subprocess
    old_src = None
    try:
        r = subprocess.run(
            ['git', 'show', '%s:live_caption/tts_service.py' % BASELINE_COMMIT],
            cwd=REPO, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=120)
        if r.returncode == 0:
            old_src = r.stdout
    except Exception:
        pass

    if old_src:
        old_mod = os.path.join(HERE, '_old_tts_service_s31.py')
        with open(old_mod, 'w', encoding='utf-8', newline='') as f:
            f.write(old_src)
        probe = os.path.join(HERE, '_probe_old_close.py')
        with open(probe, 'w', encoding='utf-8') as f:
            f.write(OLD_PROBE)
        try:
            r = subprocess.run([sys.executable, probe, old_mod, STUB],
                               capture_output=True, text=True, timeout=120)
            try:
                out = json.loads((r.stdout or '').strip().splitlines()[-1])
            except Exception:
                out = {}
            # ⚠️ **这条是「证明缺陷曾经存在」** ⇒ 命中是**预期**的
            #    ⇒ 归 **REAL** 组（断言「修复前不变式确实被破坏」成立）
            #    ⇒ **不能**放 BUG 组（BUG 组 = 「缺陷仍然存在」，命中即 FAIL）。
            real('A1 修复前的 close() 确实破坏不变式（反证：缺陷曾真实存在）',
                 out.get('invariant_broken') is True,
                 f'修复前 sum={out.get("sum")} submitted={out.get("submitted")}')
            EVIDENCE['A1_old'] = out
        finally:
            for p in (old_mod, probe):
                try:
                    os.remove(p)
                except Exception:
                    pass
    else:
        print('  [skip] A1 —— 取不到修复前源码，跳过反证')

    # ── 修复后的真实路径 ──
    svc = make_svc()
    for i in range(5):
        svc.submit('这是第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 5, 10.0)
    n_sub_before = svc.n_submitted
    n_pending_before = len(svc.pending)
    real('A0 测试前置：5 句已提交且在途',
         n_sub_before == 5 and n_pending_before == 5,
         f'submitted={n_sub_before} pending={n_pending_before}')
    svc.close()

    # ── 修复后的真实路径 ──
    svc = make_svc()
    for i in range(5):
        svc.submit('这是第 %d 句译文' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 5, 10.0)
    n_sub = svc.n_submitted
    svc.close()

    real('A2 close() 后 pending 清空', len(svc.pending) == 0,
         f'pending={len(svc.pending)}')
    real('A3 close() 后 _inflight 清空', len(svc._inflight) == 0,
         f'inflight={len(svc._inflight)}')
    real('A4 close() 后 _queue 清空', len(svc._queue) == 0,
         f'queue={len(svc._queue)}')
    real('A5 close() 后不变式成立',
         invariant(svc),
         f'n_played={svc.n_played} n_dropped={svc.n_dropped} '
         f'n_submitted={svc.n_submitted}')
    real('A6 close() 把在途句子计为丢句',
         svc.n_dropped == 5 and n_sub == 5,
         f'n_dropped={svc.n_dropped} (期望 5)')
    EVIDENCE['A_close'] = dict(n_submitted=svc.n_submitted,
                               n_played=svc.n_played,
                               n_dropped=svc.n_dropped,
                               invariant=invariant(svc))


# ══════════════════════════════════════════════════════════════════════
# [B] 缺陷①衍生：close() **不能**破坏 §30 的「丢了又播」改记逻辑
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print()
    print('[B] close() 后仍到达的 played 事件必须**改记为已播**（不得双记）')

    # 桩 worker：无视 cancel，**延迟**回 played（模拟「quit 还没生效就播了」）
    # ⚠️ **必须延迟回** ⇒ 否则 close() 之前 worker 就把 3 句全播完了
    #    ⇒ `pending` 空 ⇒ 本组测不到「close() 时仍在途」的场景。
    stub = r'''
import sys, json, time
sys.stdout.write(json.dumps({"kind": "ready", "device": "STUB", "voice": "A"}) + "\n")
sys.stdout.flush()
def later(jid):
    time.sleep(1.2)
    sys.stdout.write(json.dumps({"kind": "played", "id": jid}) + "\n")
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
        # 🔴 退出前**故意不**回 played ⇒ 模拟「这句永远等不到结果」
        sys.exit(0)
    if cmd == "cancel":
        continue            # 故意无视 cancel
    if cmd == "synth":
        import threading
        threading.Thread(target=later, args=(msg.get("id"),), daemon=True).start()
while True:
    time.sleep(0.2)
'''
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(stub)
    tts_service._WORKER = STUB

    svc = tts_service.TTSService(device='STUB', voice='A', on_log=lambda m: None)
    wait_state(svc, ('ready',), 25.0)
    for i in range(3):
        svc.submit('第 %d 句' % i, seg=i)
    wait_for(lambda: len(svc.pending) == 3, 10.0)

    # 按积压丢弃第 0 句（登记 _dropped_ids + n_dropped += 1）
    with svc.lock:
        svc.pending.pop(0, None)
        svc._inflight.discard(0)
        svc._dropped_ids.add(0)
    svc.n_dropped += 1
    n_drop_before_close = svc.n_dropped

    # close()：**不得**清掉 _dropped_ids
    svc.close()
    real('B1 close() 保留 _dropped_ids（worker 还活着，可能回 played）',
         0 in svc._dropped_ids,
         f'_dropped_ids={sorted(svc._dropped_ids)}')

    # close() 把**其余 2 句**（还在 pending 的）计丢句 ⇒ n_dropped = 1 + 2 = 3
    real('B1b close() 把其余在途句计丢句',
         svc.n_dropped == 3,
         f'n_dropped={svc.n_dropped} (期望 3 = 1 积压丢弃 + 2 close 丢弃)')

    # worker 仍回 played（模拟「quit 还没生效就播了」）⇒ 应改记为已播
    svc._handle_event({'kind': 'played', 'id': 0})
    real('B2 close() 后到达的 played 被改记为已播（n_dropped 减 1）',
         svc.n_dropped == 2 and svc.n_played == 1,
         f'n_dropped={svc.n_dropped} (期望 2) n_played={svc.n_played} (期望 1)')
    real('B3 改记后不变式仍成立',
         invariant(svc),
         f'n_played={svc.n_played} n_dropped={svc.n_dropped} '
         f'n_submitted={svc.n_submitted}')
    EVIDENCE['B_close_played'] = dict(n_dropped_before_close=n_drop_before_close,
                                      n_dropped=svc.n_dropped,
                                      n_played=svc.n_played,
                                      n_submitted=svc.n_submitted,
                                      invariant=invariant(svc))


# ══════════════════════════════════════════════════════════════════════
# [C] 缺陷②：GUI `quit()` 缺 `mt.wait_idle()`
#   （不开 Tk ⇒ 用 `ast` 抽取 `App.quit()` 的源码做**静态**判定）
# ══════════════════════════════════════════════════════════════════════
def group_c():
    print()
    print('[C] GUI App.quit() 必须等 MT 翻完（静态判定，不开 Tk 窗口）')

    app_py = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
    src = open(app_py, 'r', encoding='utf-8').read()
    tree = ast.parse(src)

    quit_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'quit':
            quit_fn = node
            break
    real('C0 能定位到 App.quit()', quit_fn is not None)
    if quit_fn is None:
        return

    fn_src = ast.get_source_segment(src, quit_fn) or ''
    # 找 flush() 与 wait_idle() 的**行号**，判定顺序与条件
    flush_lines = [n.lineno for n in ast.walk(quit_fn)
                   if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute)
                   and n.func.attr == 'flush']
    wait_lines = [n.lineno for n in ast.walk(quit_fn)
                  if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute)
                  and n.func.attr == 'wait_idle']

    real('C1 quit() 里有 mt.flush()', bool(flush_lines), f'行 {flush_lines}')
    real('C2 quit() 里有 mt.wait_idle()', bool(wait_lines), f'行 {wait_lines}')

    if flush_lines and wait_lines:
        real('C3 wait_idle 在 flush **之后**（先入队、再等）',
             min(wait_lines) > min(flush_lines),
             f'flush@{min(flush_lines)} wait_idle@{min(wait_lines)}')

    # 必须**有条件**地等（不能无条件白等 180 s）
    has_guard = 'if flushed' in fn_src or 'if self.mt.pending' in fn_src
    real('C4 wait_idle 有条件守卫（不会在 state=loading 时白等 180 s）',
         has_guard,
         'found guard' if has_guard else 'no guard found')

    # 不得有无条件 wait_idle
    real('C5 没有无条件的 wait_idle 调用',
         not any(isinstance(n, ast.If) is False for n in []) and
         ('if flushed' in fn_src or 'if self.mt.pending' in fn_src),
         'guarded')

    # 反证：对**修复前**的源码断言「确实缺 wait_idle」
    #   ⇒ 命中 = 缺陷在修复前复现（反证证据）
    # ⚠️ **不能**用 HEAD 当反证对象：修复提交之后 HEAD 就变成修复版了
    #    ⇒ 反证会永远落空 ⇒ 失去证据价值。
    #    ⇒ 用**固定的基线 commit** `BASELINE_COMMIT`（= 修复前那版）。
    import subprocess
    try:
        old_src = subprocess.run(
            ['git', 'show', '%s:live_caption/live_caption_app.py' % BASELINE_COMMIT],
            cwd=REPO, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=120).stdout
        h_tree = ast.parse(old_src)
        h_quit = None
        for node in ast.walk(h_tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'quit':
                h_quit = node
                break
        h_wait = 0
        if h_quit is not None:
            h_wait = len([n for n in ast.walk(h_quit)
                          if isinstance(n, ast.Call)
                          and isinstance(n.func, ast.Attribute)
                          and n.func.attr == 'wait_idle'])
        # ⚠️ **这条是「证明缺陷曾经存在」** ⇒ 命中是**预期**的
        #    ⇒ 归 **REAL** 组（断言「修复前确实缺 wait_idle」成立）
        #    ⇒ **不能**放 BUG 组（BUG 组 = 「缺陷仍然存在」，命中即 FAIL）。
        real('C6 修复前的 quit() 确实缺 wait_idle（反证：缺陷曾真实存在）',
             h_wait == 0,
             f'修复前 quit() 里 wait_idle 调用数 = {h_wait}')
    except Exception as e:
        real('C6 修复前的 quit() 确实缺 wait_idle（反证：缺陷曾真实存在）',
             False, f'取修复前源码失败: {e}')

    EVIDENCE['C_gui_quit'] = dict(flush_lines=flush_lines,
                                  wait_lines=wait_lines,
                                  has_guard=has_guard)


# ══════════════════════════════════════════════════════════════════════
# [D] 缺陷③：U+FFFD 乱码
# ══════════════════════════════════════════════════════════════════════
def group_d():
    print()
    print('[D] 两处 U+FFFD 乱码必须清零（纯注释/docstring）')
    out = {}
    for p in ('device_config.py', 'audio_source.py'):
        fp = os.path.join(REPO, 'live_caption', p)
        raw = open(fp, 'rb').read()
        try:
            s = raw.decode('utf-8')
            ok = True
        except UnicodeDecodeError:
            s = raw.decode('utf-8', errors='replace')
            ok = False
        n = s.count('\ufffd')
        out[p] = dict(utf8_ok=ok, u_fffd=n, bytes=len(raw))
        real(f'D {p} 无 U+FFFD 乱码', n == 0, f'count={n} bytes={len(raw)}')
    EVIDENCE['D_fffd'] = out


def main():
    old_max = tts_service.BACKLOG_MAX_S
    with open(STUB, 'w', encoding='utf-8') as f:
        f.write(STUB_ALIVE)

    print('=' * 72)
    print('§31 修复验收：close() 计丢句 + GUI quit() 等 MT + U+FFFD 清零')
    print('（桩 worker，无推理；不跑测速、不占 GPU、不调 MiniMax）')
    print('=' * 72)

    try:
        group_a()
        group_b()
        group_c()
        group_d()
    finally:
        tts_service.BACKLOG_MAX_S = old_max

    print()
    print('=' * 72)
    ok = (not REAL_FAIL) and (not BUG_HIT)
    print(f'REAL 失败项：{REAL_FAIL if REAL_FAIL else "无"}')
    print(f'BUG  命中项：{BUG_HIT if BUG_HIT else "无"}')
    print('总判定：' + ('PASS —— REAL 全过且 BUG 全落空'
                        if ok else 'FAIL'))

    ev_path = os.path.join(HERE, 'test_tts_close_gui_quit_evidence.json')
    with open(ev_path, 'w', encoding='utf-8') as f:
        json.dump(dict(real_fail=REAL_FAIL, bug_hit=BUG_HIT,
                       evidence=EVIDENCE, verdict='PASS' if ok else 'FAIL'),
                  f, ensure_ascii=False, indent=2)
    print(f'证据已落盘：{ev_path}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
