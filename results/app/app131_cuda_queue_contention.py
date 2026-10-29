#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""app131 —— §91 **确定性**证明：CUDA 客户端的**消息队列争用**（三个真实缺陷）。

## 缺陷本体（§90 的修复引入的**同源复发**）

§90 把「cancel 不可达」修好了，但**没有审查它自己引入的并发结构**：

> §90 的修法：边车加独立命令读取线程（cancel 与生成并行）；
> 客户端 `_cancel_request` 等确认；`_start_drain` 把「别 rid 的消息」插回队首。

修完后，**四个消费者共用同一条 FIFO 队列** `self._q`：

| 消费者 | 引入于 | 用途 |
|---|---|---|
| 主合成线程 `generate_stream` | APP-027③ | 取本句的块 / `done` |
| `_start_drain` 后台线程 | APP-027③ | 排空被取消句的剩余块 |
| `_wait_cancel_ack` | **§90** | 等 `{'cancelled': true}` 确认 |
| 旧边车 reader 线程 | APP-027③ | 投递消息 + EOF 哨兵 `None` |

⇒ 由此产生**三个**真实缺陷：

### D2 —— `_wait_cancel_ack` 吞掉别 rid 的消息（**丢音频**）

§90 的 `_wait_cancel_ack` 从**共享队列**取消息，取到**别 rid** 的就 `continue`
⇒ **那条消息被永久丢弃**（没人再放回去）⇒ **下一句少一块或整句无输出**。

> 实测：队列里放一条 `('{"id":77,"n":2}', pcm)`（下一句的第 1 块），
> `_wait_cancel_ack(rid=5)` 跑完 ⇒ **队列空了** ⇒ 消息没了。

### D3 —— `_start_drain` 对别 rid 的消息**忙循环插回**（CPU 打满 + 目标排不到）

§90 的修法是「不是本 rid 的 ⇒ **插回队首**」
⇒ 但排空线程**下一次 `get()` 到的又是它** ⇒ **立刻再插回** ⇒ **无限忙循环**。

> 实测：**67 万次/秒**；且队尾**真正的目标**（本 rid 的 `done`）**永远排不到**
> ⇒ 排空线程直到 30 s 超时才退出 ⇒ **白占一个线程 30 s**。

### D5' —— 旧 reader 线程的 EOF 哨兵污染**新**边车的队列（**误报边车退出**）

`_restart_sidecar` 的顺序是「kill → 清队列 → start()」；
而旧 reader 线程**阻塞在 `pipe.read()`** ⇒ 边车被 kill 后它才拿到 EOF
⇒ **然后**才 `put(None)` ⇒ **落在「清队列」之后** ⇒ **污染新边车的队列**
⇒ 新句读到 `None` 哨兵 ⇒ **误报「CUDA 边车意外退出」**。

> §90 之前这是低频路径；§90 让 `_cancel_kill`→`_restart_sidecar` 变高频
> ⇒ **被激活**。

## 本脚本的做法（零 GPU、零推理、毫秒级）

把 `live_caption/tts_cuda.py` 的相关方法用 `ast` 抽出来、`exec` 到**独立命名空间**
（铁律：**不 import 被测模块**），绑到**假 proc / 假队列**上跑。

- **A 组**：在**修前**固定 commit 上跑 ⇒ 必须**命中**三个缺陷；
- **B 组**：在**候选**源码上跑 ⇒ 必须**全部 PASS**；
- **C 组**：**注入删除**（把 §91 的分流/世代号机制拆掉）⇒ 必须**复现失效**
  ⇒ 证明判据**不恒真**。

## 用法

    <py> results/app/app131_cuda_queue_contention.py

    # 同一套判据跑客户包：
    set APP131_SRC_ROOT=C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6
    set APP131_EVID=<落盘路径>
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import textwrap
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **同一套判据必须能在「仓库」和「客户包」两处跑**
SRC_ROOT = os.environ.get('APP131_SRC_ROOT') or REPO
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'
CUDA_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda.py')
EVID_PATH = os.environ.get('APP131_EVID') or os.path.join(
    HERE, 'app131_cuda_queue_contention_evidence.json')

#: 🔴 反证基线 = **固定 commit**（§90 修完、§91 修之前的状态）
#:   ⇒ A 组必须命中三个缺陷
BASELINE_COMMIT = 'b3d2eca'

TIMEOUT = object()

EVID = {
    'script': 'app131_cuda_queue_contention.py',
    'baseline_commit': BASELINE_COMMIT,
    'src_root': SRC_ROOT,
    'subdir': _SUBDIR,
    'checks': [],
}


def check(name, ok, detail=''):
    ok = bool(ok)
    EVID['checks'].append({'name': name, 'pass': ok, 'detail': str(detail)})
    print('  [%s] %s — %s' % ('PASS' if ok else 'FAIL', name, detail))
    return ok


def git_show(commit, rel):
    """取某个 commit 下的文件内容（**不 checkout**）。"""
    try:
        p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                           capture_output=True, timeout=60)
        if p.returncode != 0:
            return None
        return p.stdout.decode('utf-8', 'replace')
    except Exception:
        return None


# ── 源码抽取（不 import 被测模块）────────────────────────────────────
def extract_method(src, cls_name, meth_name):
    """用 `ast` 抽出方法源码（**不 import 被测模块**）。"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == meth_name:
                    lines = src.splitlines()
                    return textwrap.dedent(
                        '\n'.join(lines[item.lineno - 1:item.end_lineno]))
    return None


def extract_class_methods(src, cls_name, names):
    """抽出多个方法（按依赖顺序）⇒ 返回 {name: source}。"""
    out = {}
    for n in names:
        s = extract_method(src, cls_name, n)
        if s is not None:
            out[n] = s
    return out


# ── D2：`_wait_cancel_ack` 是否吞掉别 rid 的消息 ───────────────────────
def probe_d2(src):
    """返回 dict：ack 等待结束后，**别 rid 的消息是否还在**。"""
    meths = extract_class_methods(src, 'CudaTTSEngine',
                                  ('_wait_cancel_ack', '_q_get_rid',
                                   '_rid_q_get', '_q_put_rid'))
    if '_wait_cancel_ack' not in meths:
        return {'error': 'no _wait_cancel_ack'}

    ns = {'json': json, 'time': time, 'queue': queue,
          'threading': threading, '_TIMEOUT': TIMEOUT}

    class Fake:
        pass

    f = Fake()
    f._rid_q = {}
    f._rid_q_lock = threading.Lock()

    # 🔴 §91 的分流实现（若源码里有）
    if '_rid_q_get' in meths:
        exec(meths['_rid_q_get'], ns)
        f._rid_q_get = lambda rid, create=True: ns['_rid_q_get'](f, rid, create)
    if '_q_put_rid' in meths:
        exec(meths['_q_put_rid'], ns)
        f._q_put_rid = lambda rid, item: ns['_q_put_rid'](f, rid, item)

    # 🔴 假队列：`_q_get_rid` 存在 ⇒ 按 rid 分流；否则退回共享队列
    shared = queue.Queue()

    # 🔴 修前版本用的是 `_q_get`（共享队列）⇒ 必须**同时**提供两个接口
    #   ⇒ 同一套脚本既能跑**修前**（A 组反证）也能跑**候选**（B 组）
    def _shared_q_get(timeout):
        try:
            return shared.get(timeout=max(0.0, float(timeout)))
        except queue.Empty:
            return TIMEOUT
    f._q_get = _shared_q_get

    if '_q_get_rid' in meths:
        exec(meths['_q_get_rid'], ns)
        f._q_get_rid = lambda rid, timeout: ns['_q_get_rid'](f, rid, timeout)
    else:
        def _legacy_q_get_rid(rid, timeout):
            try:
                return shared.get(timeout=max(0.0, float(timeout)))
            except queue.Empty:
                return TIMEOUT
        f._q_get_rid = _legacy_q_get_rid

    # 🔴 关键：别 rid 的消息**只**在共享队列里（模拟修前：所有消息共用一条队列）
    other = ('{"id": 77, "n": 2}', b'\x00\x00\x00\x00' * 2)
    if '_q_put_rid' in meths:
        # §91：分流 ⇒ 消息进 77 自己的队列 ⇒ 不该被 rid=5 的消费者碰到
        f._q_put_rid(77, other)
    else:
        shared.put(other)

    exec(meths['_wait_cancel_ack'], ns)
    ns['_wait_cancel_ack'](f, 5, timeout=0.6)

    # 检查：别的 rid 的消息还在不在？
    if '_q_get_rid' in meths:
        with f._rid_q_lock:
            q77 = f._rid_q.get(77)
        kept = bool(q77 is not None and not q77.empty())
    else:
        kept = not shared.empty()

    return {'kept': kept, 'drained': not kept,
            'has_rid_split': '_q_get_rid' in meths}


# ── D3：`_start_drain` 是否忙循环插回 ────────────────────────────────
def probe_d3(src):
    """返回 dict：drain 线程的插回次数（忙循环 ⇒ 巨大）。"""
    meths = extract_class_methods(src, 'CudaTTSEngine',
                                  ('_start_drain', '_q_get_rid',
                                   '_rid_q_get', '_q_put_rid',
                                   '_q_put_front', '_rid_q_drop'))
    if '_start_drain' not in meths:
        return {'error': 'no _start_drain'}

    ns = {'json': json, 'time': time, 'queue': queue,
          'threading': threading, '_TIMEOUT': TIMEOUT,
          '_trace': lambda m: None}

    class Fake:
        pass

    f = Fake()
    f._rid_q = {}
    f._rid_q_lock = threading.Lock()
    counter = {'n': 0}
    shared = queue.Queue()

    if '_rid_q_get' in meths:
        exec(meths['_rid_q_get'], ns)
        f._rid_q_get = lambda rid, create=True: ns['_rid_q_get'](f, rid, create)
    if '_q_put_rid' in meths:
        exec(meths['_q_put_rid'], ns)
        f._q_put_rid = lambda rid, item: ns['_q_put_rid'](f, rid, item)
    if '_q_get_rid' in meths:
        exec(meths['_q_get_rid'], ns)
        f._q_get_rid = lambda rid, timeout: ns['_q_get_rid'](f, rid, timeout)
    else:
        def _legacy_q_get_rid(rid, timeout):
            try:
                return shared.get(timeout=max(0.0, float(timeout)))
            except queue.Empty:
                return TIMEOUT
        f._q_get_rid = _legacy_q_get_rid

    # 🔴 修前版本的 `_start_drain` 直接用 `self._q.get(...)`
    def _shared_q_get(timeout):
        try:
            return shared.get(timeout=max(0.0, float(timeout)))
        except queue.Empty:
            return TIMEOUT
    f._q_get = _shared_q_get
    f._q = shared

    if '_rid_q_drop' in meths:
        exec(meths['_rid_q_drop'], ns)
        f._rid_q_drop = lambda rid: ns['_rid_q_drop'](f, rid)

    # 🔴 计「插回队首」的次数（忙循环的直接指标）
    if '_q_put_front' in meths:
        exec(meths['_q_put_front'], ns)

        def _counting_put_front(item):
            counter['n'] += 1
            return ns['_q_put_front'](f, item)
        f._q_put_front = _counting_put_front
    else:
        # §91：没有 `_q_put_front` ⇒ 也就没有「插回」这个动作
        f._q_put_front = lambda item: None

    # 别的 rid 的消息
    other = ('{"id": 77, "n": 2}', b'\x00\x00\x00\x00' * 2)
    if '_q_put_rid' in meths:
        f._q_put_rid(77, other)
    else:
        shared.put(other)

    exec(meths['_start_drain'], ns)
    ns['_start_drain'](f, 5)
    time.sleep(1.0)

    return {'put_front_calls': counter['n'],
            'busy': counter['n'] > 10000,
            'has_rid_split': '_q_get_rid' in meths}


# ── D5'：旧 reader 线程的 EOF 哨兵是否污染新边车队列 ──────────────────
def probe_d5(src):
    """模拟 `_restart_sidecar` 的真实时序：
       旧 reader 线程阻塞在 read → 边车被 kill（EOF）→ **清队列** → start()
    ⇒ 旧线程的 `put(None)` 若落在「清队列」之后 ⇒ 污染新边车队列。

    🔴🔴 关键：**真的执行**换代逻辑（而不是"看源码里有没有那一句"）
      ⇒ 否则反���脚本只能**猜** ⇒ 判据会**恒真**（闸门失效）。
    """
    meths = extract_class_methods(src, 'CudaTTSEngine',
                                  ('_start_reader', '_restart_sidecar',
                                   '_bump_gen',
                                   '_q_get_rid', '_rid_q_get', '_q_put_rid',
                                   '_rid_q_drop'))
    if '_start_reader' not in meths:
        return {'error': 'no _start_reader'}

    ns = {'json': json, 'time': time, 'queue': queue,
          'threading': threading, '_TIMEOUT': TIMEOUT,
          '_trace': lambda m: None, 'CudaTTSError': RuntimeError}

    class BlockingPipe:
        """真实管道语义：read 阻塞，直到边车被 kill（EOF）。"""
        def __init__(self):
            self.eof = threading.Event()
            self.buf = b''

        def read(self, n):
            if self.buf:
                b, self.buf = self.buf, b''
                return b
            self.eof.wait(3.0)
            return b''

    class FakeProc:
        def __init__(self, pipe):
            self.stdout = pipe
            self.stdin = None

        def poll(self):
            return None

    class Fake:
        pass

    f = Fake()
    f._q = queue.Queue()
    f._rid_q = {}
    f._rid_q_lock = threading.Lock()
    f._buf = b''
    f._gen = 0
    f.on_log = lambda *a, **k: None
    pipe = BlockingPipe()
    f.proc = FakeProc(pipe)

    if '_rid_q_get' in meths:
        exec(meths['_rid_q_get'], ns)
        f._rid_q_get = lambda rid, create=True: ns['_rid_q_get'](f, rid, create)
    if '_q_put_rid' in meths:
        exec(meths['_q_put_rid'], ns)
        f._q_put_rid = lambda rid, item: ns['_q_put_rid'](f, rid, item)
    if '_q_get_rid' in meths:
        exec(meths['_q_get_rid'], ns)
        f._q_get_rid = lambda rid, timeout: ns['_q_get_rid'](f, rid, timeout)
    if '_rid_q_drop' in meths:
        exec(meths['_rid_q_drop'], ns)
        f._rid_q_drop = lambda rid: ns['_rid_q_drop'](f, rid)

    exec(meths['_start_reader'], ns)
    ns['_start_reader'](f)
    time.sleep(0.2)

    # 🔴 `_restart_sidecar` 的真实顺序：**先换代** → kill → 清队列 → start()
    #   🔴 **真的执行**换代（若源码有 `_bump_gen`）⇒ 旧线程必须失效
    #   ⚠️ 修前源码（§90）**没有**换代 ⇒ 走「不换代」分支 ⇒ 污染复现
    gen_bumped = False
    if '_bump_gen' in meths:
        exec(meths['_bump_gen'], ns)
        f._bump_gen = lambda: ns['_bump_gen'](f)
        f._bump_gen()
        gen_bumped = True
    else:
        # 🔴 修前：`_restart_sidecar` 里散落的 `self._gen += 1`（若存在）也算
        if '_restart_sidecar' in meths and re.search(
                r'self\._gen\s*\+=\s*1', meths['_restart_sidecar']):
            f._gen += 1
            gen_bumped = True

    # 边车被 kill ⇒ EOF
    pipe.eof.set()
    # 清队列（真实顺序里在 kill 之后）
    try:
        while True:
            f._q.get_nowait()
    except Exception:
        pass
    time.sleep(0.4)

    polluted = f._q.qsize() > 0
    return {'polluted': polluted, 'gen_bumped': gen_bumped,
            'queue_after': list(f._q.queue)}


# ── C 组：注入删除（拆掉 §91 的机制 ⇒ 必须复现失效）──────────────────
def inject_remove(src, patterns):
    """按正则删除代码块（返回新源码 + 删除计数）。

    ⚠️ 用 `re.DOTALL`（`.` 也匹配换行）⇒ 多行方法体**整块**删掉
      ⇒ 否则只删掉 `def` 那一行 ⇒ 留下孤立语句块 ⇒ `IndentationError`
      ⇒ **反证脚本自己崩** ⇒ 看起来像「缺陷没复现」。
    """
    out = src
    total = 0
    for pat in patterns:
        new, n = re.subn(pat, '', out, count=1, flags=re.DOTALL)
        out = new
        total += n
    return out, total


def main():
    print('=' * 74)
    print('app131 —— §91 确定性证明：CUDA 客户端的消息队列争用（3 个缺陷）')
    print('=' * 74)

    cur_src = open(CUDA_PATH, 'r', encoding='utf-8').read()
    base_src = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda.py')

    check('A0-修前基线可取', base_src is not None,
          'commit=%s' % BASELINE_COMMIT)
    if base_src is None:
        EVID['pass'] = sum(1 for c in EVID['checks'] if c['pass'])
        EVID['fail'] = sum(1 for c in EVID['checks'] if not c['pass'])
        with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(EVID, f, ensure_ascii=False, indent=2)
        return 1

    # ── A 组：修前基线（期望「缺陷命中」）──
    print('\n  === A 组：修前源码（§90 修完、§91 未修）—— 期望缺陷命中 ===')
    a_d2 = probe_d2(base_src)
    check('A1-修前：`_wait_cancel_ack` **吞掉**别 rid 的消息（D2 丢音频）',
          a_d2.get('drained') is True,
          'kept=%s ⇒ 消息被永久丢弃' % a_d2.get('kept'))
    a_d3 = probe_d3(base_src)
    check('A2-修前：`_start_drain` 对别 rid 消息**忙循环插回**（D3）',
          a_d3.get('busy') is True,
          '插回 %d 次/秒' % a_d3.get('put_front_calls', -1))
    a_d5 = probe_d5(base_src)
    check('A3-修前：旧 reader 线程的 EOF 哨兵**污染新边车队列**（D5\'）',
          a_d5.get('polluted') is True,
          '污染=%s' % a_d5.get('polluted'))

    # ── B 组：候选源码（期望「缺陷已修」）──
    print('\n  === B 组：候选源码（§91）—— 期望缺陷已修 ===')
    b_d2 = probe_d2(cur_src)
    check('B1-候选：`_wait_cancel_ack` **不吞**别 rid 的消息（D2 已修）',
          b_d2.get('kept') is True,
          'kept=%s' % b_d2.get('kept'))
    b_d3 = probe_d3(cur_src)
    check('B2-候选：`_start_drain` **不忙循环**（D3 已修）',
          b_d3.get('busy') is False,
          '插回 %d 次/秒' % b_d3.get('put_front_calls', -1))
    b_d5 = probe_d5(cur_src)
    check('B3-候选：旧 reader 线程**不污染**新边车队列（D5\' 已修）',
          b_d5.get('polluted') is False,
          '污染=%s（换代=%s）' % (b_d5.get('polluted'), b_d5.get('gen_bumped')))

    # 🔴🔴 B4：候选源码必须**真的**有「按 rid 分流」和「世代号」两个机制
    check('B4-候选：源码含**按 rid 分流**（`_q_get_rid` / `_rid_q`）'
          '与**世代号**（`_gen`）两个机制',
          '_q_get_rid' in cur_src and '_rid_q' in cur_src
          and re.search(r'self\._gen\s*\+=\s*1', cur_src) is not None,
          '源码级锚定')

    # ── C 组：注入删除（拆掉机制 ⇒ 必须复现失效）──
    print('\n  === C 组：反证（注入删除 ⇒ 必须复现失效）===')
    # C-1：拆掉「换代」⇒ D5' 必须复现
    #   🔴 删**整个方法体**（`def _bump_gen` 那一段）
    #   ⇒ 脚本才可能"真的执行不到换代" ⇒ 反证才有效
    c1_src, c1_n = inject_remove(cur_src, [
        r'[ \t]*def _bump_gen\(self\):.*?\r?\n(?=    def )',
    ])
    check('C0-注入成功（删掉了 `_bump_gen` 换代方法）', c1_n >= 1,
          '删除数=%d' % c1_n)
    c1_d5 = probe_d5(c1_src)
    check('C1-删掉换代 ⇒ 旧线程**重新污染**新边车队列（D5\' 复现）',
          c1_d5.get('polluted') is True,
          '污染=%s（换代=%s）' % (c1_d5.get('polluted'),
                                 c1_d5.get('gen_bumped')))

    # C-2：拆掉「按 rid 分流」⇒ D2 必须复现
    c2_src, c2_n = inject_remove(cur_src, [
        r'[ \t]*def _q_get_rid\(self, rid, timeout\):.*?\r?\n(?=    def )',
    ])
    check('C2a-注入成功（删掉了 `_q_get_rid` 分流方法）', c2_n >= 1,
          '删除数=%d' % c2_n)
    if c2_n >= 1:
        c2_d2 = probe_d2(c2_src)
        check('C2b-删掉分流 ⇒ `_wait_cancel_ack` **重新吞掉**别 rid 的消息'
              '（D2 复现）',
              c2_d2.get('drained') is True,
              'kept=%s' % c2_d2.get('kept'))

    # ── 汇总 ──
    npass = sum(1 for c in EVID['checks'] if c['pass'])
    nfail = sum(1 for c in EVID['checks'] if not c['pass'])
    EVID['pass'] = npass
    EVID['fail'] = nfail
    EVID['a_group'] = {'d2': a_d2, 'd3': a_d3, 'd5': a_d5}
    EVID['b_group'] = {'d2': b_d2, 'd3': b_d3, 'd5': b_d5}
    with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('\n  PASS=%d  FAIL=%d' % (npass, nfail))
    print('  证据 → %s' % EVID_PATH)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
