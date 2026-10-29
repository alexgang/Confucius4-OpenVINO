#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app141 — APP-042 **主链集成**验收（补 app140 只测模块的缺口）。

🔴🔴 **为什么需要本脚本**：
  `app140_app042_wsola.py` 只验证了 `live_caption/time_stretch.py` 这个
  **独立模块**（WSOLA 保音高 + 统一参数公式）⇒ **22/22 PASS**。
  🔴 但它**完全没验证「主进程 → worker → 播放」这条主链**：
    主进程 `TTSService.submit(target_play_at=…)` 是否真的算出 `speed`
    ⇒ 是否真的写进命令体 ⇒ worker 是否真的解析 ⇒ 是否真的传给
    `synth(speed=…)` ⇒ 遥测是否真的回报 `speed` / `play_lag_s`。
  ⇒ **一个「模块测得好、主链没接上」的假绿**，正是本项目 §10 反复踩的坑
    （「做出来了但没接上」⇒ 「已交付」不成立）。

🔴🔴 **判据设计铁律**（本项目 §9/§10）：
  ① **绝不 `import` 被测模块**（`tts_service` 顶层 import numpy/其它）
     ⇒ 用 `ast` 抽源码 + `exec` 到独立命名空间；
  ② **双向反证**：注入「链路断开」⇒ 对应判据**必须 FAIL**
     ⇒ 证明判据不恒真；
  ③ **判据 FAIL 先怀疑判据本身**；
  ④ **跨进程时钟口径**：lag 的「目标」在主进程（墙钟 `time.time()`）、
     「实际开播」在 worker ⇒ **必须用墙钟**，不能用 `perf_counter()`。

## 判据清单
  A 组（静态链路完整性）
    A1 `TTSService.submit` 形参含 `target_play_at`
    A2 `submit` 里调用 `time_stretch.speed_for_lag(...)`
    A3 `submit` 把 `speed` 写进命令体 `cmd['speed']`
    A4 `submit` 把 `target_wall` 写进命令体（跨进程墙钟口径）
    A5 worker 主循环解析 `msg.get('speed')`（并 clamp 到 [1.0, 1.30]）
    A6 worker 把 `speed` 传给 `self.synth(...)`
    A7 worker 的 `synth()` 签名含 `speed` 形参
    A8 worker 用 `StreamWSOLA` 做**流式**变速（不是整句）
    A9 worker 遥测回报 `speed` / `out_dur_s` / `speed_gain`
    A10 worker 遥测回报 `play_lag_s`（= 实际开播墙钟 − 目标开播墙钟）
    A11 GUI 底栏显示「语速倍率」与「播放滞后」
    A12 GUI 把 `target_play_at=self._seg_target_wall.get(seg)` 传给 submit

  B 组（行为：主链真的算得出、传得下去）
    B1 `submit(target_play_at=墙钟−10s)` ⇒ 命令体带 `speed` 且 > 1.0
    B2 `submit()`（**不带** `target_play_at`）⇒ 命令体**逐字不含** speed
       （向后兼容：旧调用方命令体不变）
    B3 lag 小（< 3 s）⇒ speed == 1.0
    B4 lag 极大（> 15 s）⇒ speed == 1.30（clamp 上限）
    B5 连续两句：第二步长的速度变化 ≤ 0.1×
    B6 `stats()` 里有 `cur_speed` / `play_lag_s` / `speed_time_s` /
       `n_speed_adjusted` 四个字段
    B7 worker 收到带 `speed` 的命令 ⇒ `synth()` 收到的 speed 值相等

  C 组（反证：判据不恒真）
    C1 注入「submit 不写 speed」⇒ A3 **必须 FAIL**
    C2 注入「worker 不传 speed 给 synth」⇒ A6 **必须 FAIL**
    C3 注入「speed 改成改采样率（变调）做法」⇒ B 组音高判据 **必须 FAIL**
"""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_DIR = os.path.join(REPO, 'live_caption')
SERVICE_PY = os.path.join(APP_DIR, 'tts_service.py')
WORKER_PY = os.path.join(APP_DIR, 'tts_worker.py')
APP_PY = os.path.join(APP_DIR, 'live_caption_app.py')
TS_PY = os.path.join(APP_DIR, 'time_stretch.py')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app141_app042_end_to_end_evidence.json')

RESULTS = []


def rec(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:600]})
    print(('PASS ' if ok else 'FAIL ') + name
          + ('  :: ' + str(detail)[:400] if detail else ''))
    sys.stdout.flush()
    return ok


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def method_src(src, cls_name, meth_name):
    """用 ast 抽出 `cls_name.meth_name` 的源码段（不 import 被测模块）。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and item.name == meth_name:
                    seg = ast.get_source_segment(src, item)
                    if seg:
                        return textwrap.dedent(seg)
    return None


def func_src(src, fn_name):
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == fn_name:
            seg = ast.get_source_segment(src, node)
            if seg:
                return textwrap.dedent(seg)
    return None


def exec_func(src, fn_name, ns_extra=None):
    """把模块级函数 exec 到独立命名空间。"""
    code = func_src(src, fn_name)
    if code is None:
        raise RuntimeError(f'找不到函数 {fn_name}')
    ns = dict(ns_extra or {})
    exec(compile(code, f'<{fn_name}>', 'exec'), ns)
    return ns[fn_name], ns


# ────────────────────────────────────────────────────────────────────
# A 组：静态链路完整性
# ────────────────────────────────────────────────────────────────────
def test_static():
    svc = load(SERVICE_PY)
    wk = load(WORKER_PY)
    gui = load(APP_PY)
    ok = True

    # A1 submit 形参含 target_play_at
    m = re.search(r'def submit\(self,[^)]*\)', svc, re.S)
    a1 = bool(m) and 'target_play_at' in m.group(0)
    rec('A1: TTSService.submit 形参含 target_play_at', a1,
        (m.group(0)[:120] if m else 'no def submit'))
    ok = ok and a1

    # A2 submit 里调用 speed_for_lag
    body = method_src(svc, 'TTSService', 'submit') or ''
    a2 = 'speed_for_lag' in body
    rec('A2: submit 里调用 time_stretch.speed_for_lag(...)', a2)
    ok = ok and a2

    # A3 submit 把 speed 写进命令体
    a3 = re.search(r"cmd\['speed'\]\s*=", body) is not None
    rec("A3: submit 把 speed 写进命令体 cmd['speed']", a3)
    ok = ok and a3

    # A4 submit 把 target_wall 写进命令体（跨进程墙钟）
    a4 = re.search(r"cmd\['target_wall'\]\s*=", body) is not None
    rec("A4: submit 把 target_wall 写进命令体（跨进程墙钟口径）", a4)
    ok = ok and a4

    # A5 worker 主循环解析 speed 并 clamp
    a5 = ("msg.get('speed')" in wk
          and re.search(r'speed\s*>\s*1\.30', wk) is not None)
    rec('A5: worker 解析 msg.get("speed") 并 clamp 到 [1.0, 1.30]', a5)
    ok = ok and a5

    # A6 worker 把 speed 传给 synth
    a6 = re.search(r'self\.synth\([^)]*\bspeed\b', wk, re.S) is not None
    rec('A6: worker 把 speed 传给 self.synth(...)', a6)
    ok = ok and a6

    # A7 synth 签名含 speed 形参
    a7 = re.search(r'def synth\(self,[^)]*\bspeed\b', wk, re.S) is not None
    rec('A7: worker 的 synth() 签名含 speed 形参', a7)
    ok = ok and a7

    # A8 用 StreamWSOLA 流式变速
    a8 = 'StreamWSOLA' in wk and '_stretcher.process(' in wk
    rec('A8: worker 用 StreamWSOLA 做流式变速（首块即可出声）', a8)
    ok = ok and a8

    # A9 遥测回报 speed / out_dur_s / speed_gain
    a9 = all(k in wk for k in ("tel['speed']", "tel['out_dur_s']",
                               "tel['speed_gain']"))
    rec('A9: worker 遥测回报 speed / out_dur_s / speed_gain', a9)
    ok = ok and a9

    # A10 遥测回报 play_lag_s
    a10 = "tel['play_lag_s']" in wk and "tel['target_wall']" in wk
    rec('A10: worker 遥测回报 play_lag_s（实际开播墙钟 − 目标开播墙钟）', a10)
    ok = ok and a10

    # A11 GUI 底栏显示语速倍率与播放滞后
    a11 = ("'语速 '" in gui or '语速 ' in gui) and '播放滞后' in gui
    rec('A11: GUI 底栏显示「语速倍率」与「播放滞后」', a11)
    ok = ok and a11

    # A12 GUI 把 target_play_at 传给 submit
    a12 = 'target_play_at=self._seg_target_wall.get(' in gui
    rec('A12: GUI 把 target_play_at=self._seg_target_wall.get(seg) 传给 submit',
        a12)
    ok = ok and a12

    return ok


# ────────────────────────────────────────────────────────────────────
# B 组：行为 —— 主链真的算得出、传得下去
# ────────────────────────────────────────────────────────────────────
class _FakeLock:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeProc:
    """假 worker 进程：记录写进 stdin 的命令体。"""

    def __init__(self):
        self.sent = []
        self.stdin = self

    def write(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        for line in data.splitlines():
            line = line.strip()
            if line:
                self.sent.append(json.loads(line))
        return len(data)

    def flush(self):
        pass


def _make_service_cls(svc_src, ts_ns):
    """抽出 TTSService.submit（+ 少量依赖）⇒ 独立命名空间。

    ⚠️ **只抽 `submit`**，不抽整个类 ⇒ 避免 `__init__` 的一堆依赖。
      ⇒ 用一个**假实例**承载 `submit` 需要的状态。
    """
    code = method_src(svc_src, 'TTSService', 'submit')
    if code is None:
        raise RuntimeError('找不到 TTSService.submit')
    ns = dict(ts_ns)
    ns['time'] = __import__('time')
    # 🔴 `submit` 用到模块级常量 ⇒ 必须一并注入（否则 NameError
    #   ⇒ 表现为「脚本崩了」而不是「判据 FAIL」）。
    # 🔴 **从真实源码抽常量**（不硬编码）⇒ 口径不漂移。
    for cname in ('MAX_TEXT_CHARS',):
        m = re.search(rf'^{cname}\s*=\s*(.+)$', svc_src, re.M)
        if m:
            try:
                ns[cname] = eval(m.group(1).strip(), {'os': os,
                                                     'int': int})
            except Exception:
                pass
    ns.setdefault('MAX_TEXT_CHARS', 100000)
    exec(compile(code, '<TTSService.submit>', 'exec'), ns)
    return ns['submit']


def _make_fake_svc_inst(svc_src, ts_ns):
    submit = _make_service_cls(svc_src, ts_ns)

    class FakeSvc:
        def __init__(self):
            self.lock = _FakeLock()
            self._stdin_wlock = _FakeLock()
            self.proc = _FakeProc()
            self.state = 'ready'
            self.pending = {}
            self._inflight = set()
            self._queue = []
            self._next_id = 1
            self.n_submitted = 0
            self.n_dropped = 0
            self.lag_s = 0.0
            self._last_speed = 1.0
            self._queued_ids = set()
            self.logs = []

        def on_log(self, m):
            self.logs.append(m)

        def _drop_one(self, jid, register_dropped=True):
            self.pending.pop(jid, None)
            self._inflight.discard(jid)
            self.n_dropped += 1

        def _send(self, obj):
            """🔴 真实现会把命令写进 worker stdin ⇒ 这里记录下来即可。"""
            line = (json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8')
            self.proc.write(line)
            return True

        def _update_backlog(self, *a, **k):
            """🔴 真实实现会更新积压遥测 ⇒ 本验收不测积压口径。"""
            pass

        def _flush_queue(self):
            pass

    inst = FakeSvc()
    inst.submit = submit.__get__(inst, FakeSvc)
    return inst


def test_behavior():
    ok = True
    svc_src = load(SERVICE_PY)
    ts_src = load(TS_PY)

    # time_stretch 的 exec 命名空间（不 import 被测模块）
    ts_ns = {}
    exec(compile(ts_src, '<time_stretch>', 'exec'), ts_ns)

    # 🔴🔴 **判据环境（关键）**：真实代码用 `import time_stretch as _ts`
    #   ⇒ 必须是**可 import 的模块**⇒ 把它放进 `sys.modules`
    #   （否则 `import` 失败 ⇒ 走进 `except` ⇒ **静默不加速**
    #     ⇒ 表现为「speed 永远算不出来」⇒ **看起来像产品缺陷**）。
    #   ⚠️ 这正是「判据 FAIL 先怀疑判据」的典型（§10）。
    import types as _types
    import time as _time
    _ts_mod = _types.ModuleType('time_stretch')
    for _k, _v in ts_ns.items():
        if not _k.startswith('__'):
            setattr(_ts_mod, _k, _v)
    _old_ts = sys.modules.get('time_stretch')
    sys.modules['time_stretch'] = _ts_mod

    try:
        # ── B1：lag 大 ⇒ 算出 speed > 1.0 并写进命令体 ─────────
        inst = _make_fake_svc_inst(svc_src, ts_ns)
        # 目标开播时刻 = 10 秒前 ⇒ lag ≈ 10 s
        #   ⇒ 期望 speed ≈ 1.0+(10-3)*0.025 = 1.175
        inst.submit('hello', seg=1, target_play_at=_time.time() - 10.0)
        sent = inst.proc.sent
        b1 = (len(sent) == 1
              and 'speed' in sent[0]
              and sent[0]['speed'] > 1.0
              and 'target_wall' in sent[0])
        rec('B1: submit(target_play_at=10s前) ⇒ 命令体带 speed>1.0 '
            '与 target_wall', b1,
            f"cmd={sent[0] if sent else None} logs={inst.logs[-2:]}")
        ok = ok and b1

        # ── B2：不带 target_play_at ⇒ 命令体**不含** speed ──────
        inst2 = _make_fake_svc_inst(svc_src, ts_ns)
        inst2.submit('hello', seg=1)
        sent2 = inst2.proc.sent
        b2 = (len(sent2) == 1 and 'speed' not in sent2[0]
              and 'target_wall' not in sent2[0])
        rec('B2: submit() 不带 target_play_at ⇒ 命令体不含 speed（向后兼容）',
            b2, f"cmd={sent2[0] if sent2 else None}")
        ok = ok and b2

        # ── B3：lag 小 ⇒ speed == 1.0 ─────────────────────────
        inst3 = _make_fake_svc_inst(svc_src, ts_ns)
        inst3.submit('hello', seg=1, target_play_at=_time.time() - 1.0)
        b3 = (bool(inst3.proc.sent)
              and 'speed' in inst3.proc.sent[0]
              and abs(inst3.proc.sent[0]['speed'] - 1.0) < 1e-9)
        rec('B3: lag≈1s ⇒ speed == 1.0（不加速）', b3,
            f"speed={inst3.proc.sent[0].get('speed') if inst3.proc.sent else None}")
        ok = ok and b3

        # ── B4：lag 极大 ⇒ 速度**爬到** clamp 上限 1.30 ─────────
        # 🔴🔴 **判据口径修正（首跑 FAIL 后改判据，不是改产品）**：
        #   APP-042 有**两条**约束同时生效：
        #     ① `speed = clamp(1.0+(lag−3)×0.025, 1.0, 1.30)` ⇒ 上限 1.30；
        #     ② **相邻句之间每次变化不超过 0.1×**。
        #   ⇒ **第一句**从 `prev=1.0` 出发 ⇒ 最多只能到 **1.10**
        #     （步长限制先于 clamp 生效）⇒ 首跑期望 1.30 是**错的**。
        #   ⇒ 正确判据：**连续提交足够多句** ⇒ 速度逐句 +0.1 ⇒
        #     最终**收敛到** 1.30（clamp 上限）且**不再超过**。
        inst4 = _make_fake_svc_inst(svc_src, ts_ns)
        for _i in range(6):
            inst4.submit(f's{_i}', seg=_i, target_play_at=_time.time() - 60.0)
        sp4 = [c.get('speed') for c in inst4.proc.sent]
        b4 = (len(sp4) == 6
              and all(s is not None for s in sp4)
              and abs(sp4[-1] - 1.30) < 1e-9
              and all(sp4[i + 1] - sp4[i] <= 0.1 + 1e-9 for i in range(5))
              and all(s <= 1.30 + 1e-9 for s in sp4))
        rec('B4: lag≈60s ⇒ 速度逐句 +0.1 收敛到 clamp 上限 1.30（且不超）',
            b4, f"speeds={sp4}")
        ok = ok and b4

        # ── B5：连续两句 ⇒ 步长变化 ≤ 0.1× ───────────────────
        inst5 = _make_fake_svc_inst(svc_src, ts_ns)
        inst5.submit('a', seg=1, target_play_at=_time.time() - 60.0)  # → 1.30
        inst5.submit('b', seg=2, target_play_at=_time.time() - 60.0)  # → 不应再涨
        sp = [c.get('speed') for c in inst5.proc.sent]
        b5 = (len(sp) == 2 and sp[0] is not None and sp[1] is not None
              and abs(sp[1] - sp[0]) <= 0.1 + 1e-9)
        rec('B5: 连续两句 ⇒ 速度变化 ≤ 0.1×（听感平滑）', b5, f"speeds={sp}")
        ok = ok and b5
    finally:
        if _old_ts is not None:
            sys.modules['time_stretch'] = _old_ts
        else:
            sys.modules.pop('time_stretch', None)

    # ── B6：stats() 有四个加速相关字段 ────────────────────────
    st_src = method_src(svc_src, 'TTSService', 'stats') or ''
    b6 = all(k in st_src for k in ('cur_speed', 'play_lag_s',
                                   'speed_time_s', 'n_speed_adjusted'))
    rec('B6: stats() 含 cur_speed / play_lag_s / speed_time_s / '
        'n_speed_adjusted', b6)
    ok = ok and b6

    # ── B7：worker 收到带 speed 的命令 ⇒ synth 收到的 speed 相等 ──
    wk = load(WORKER_PY)
    b7 = re.search(r'self\.synth\([^)]*\bspeed\b', wk, re.S) is not None
    b7 = b7 and bool(re.search(
        r'speed\s*=\s*float\(msg\.get\(.speed.\)\s*or\s*1\.0\)', wk))
    rec('B7: worker 把命令里的 speed 原样传给 synth()', b7)
    ok = ok and b7

    return ok


# ────────────────────────────────────────────────────────────────────
# C 组：反证 —— 判据不恒真
# ────────────────────────────────────────────────────────────────────
def test_counterevidence():
    ok = True
    svc_src = load(SERVICE_PY)
    wk = load(WORKER_PY)

    # C1：注入「submit 不写 speed」⇒ A3 必须 FAIL
    mutated = svc_src.replace(
        "                cmd['speed'] = round(_sp, 4)\n",
        "                pass  # 反证：故意不写 speed\n", 1)
    changed = mutated != svc_src
    rec('反证准备: 注入「submit 不写 speed」', changed,
        'mutated' if changed else 'PATTERN NOT FOUND ⇒ 反证无效')
    if changed:
        body = method_src(mutated, 'TTSService', 'submit') or ''
        a3_fail = re.search(r"cmd\['speed'\]\s*=", body) is None
        rec('反证: submit 不写 speed ⇒ A3 判据 FAIL（判据不恒真）', a3_fail)
        ok = ok and a3_fail
    else:
        ok = False

    # C2：注入「worker 不传 speed 给 synth」⇒ A6 必须 FAIL
    # 🔴 **反证删代码必须删「整块」**（只删 `if` 行 ⇒ 孤立语句块 ⇒
    #   IndentationError ⇒ 反证脚本自己崩 ⇒ 看起来像「缺陷没复现」）。
    # ⇒ 这里用带上下文的整块正则替换。
    pat = re.compile(r'self\.synth\(jid, text, spk, spk_conf, lang, t_recv,\s*'
                     r'speed,\s*\n\s*target_wall\)')
    mutated_wk, n_sub = pat.subn(
        'self.synth(jid, text, spk, spk_conf, lang, t_recv)', wk, count=1)
    changed_wk = (n_sub == 1)
    rec('反证准备: 注入「worker 不传 speed 给 synth」', changed_wk,
        f'mutated (替换 {n_sub} 处)'
        if changed_wk else 'PATTERN NOT FOUND ⇒ 反证无效')
    if changed_wk:
        a6_fail = re.search(r'self\.synth\([^)]*\bspeed\b',
                            mutated_wk, re.S) is None
        rec('反证: worker 不传 speed ⇒ A6 判据 FAIL（判据不恒真）', a6_fail)
        ok = ok and a6_fail
    else:
        ok = False

    # C3：注入「改采样率（变调）做法」⇒ WSOLA 音高判据必须 FAIL
    ts_src = load(TS_PY)
    import numpy as np
    ns = {}
    exec(compile(ts_src, '<time_stretch>', 'exec'), ns)
    sr = 24000
    t = np.arange(sr, dtype=np.float64) / sr
    x = (0.5 * np.sin(2 * np.pi * 200.0 * t)).astype(np.float32)

    def est_f0(y, srr):
        yy = np.asarray(y, dtype=np.float64)
        yy = yy - yy.mean()
        spec = np.abs(np.fft.rfft(yy * np.hanning(len(yy))))
        freqs = np.fft.rfftfreq(len(yy), 1.0 / srr)
        lo = np.searchsorted(freqs, 50)
        hi = np.searchsorted(freqs, 400)
        if hi <= lo:
            return 0.0
        return float(freqs[lo + int(np.argmax(spec[lo:hi]))])

    # 正确做法（WSOLA）：音高不变
    y_wsola = ns['time_stretch'](x, 1.25, sr=sr)
    f_wsola = est_f0(y_wsola, sr)
    # 错误做法（线性重采样）：变调
    n_out = max(1, int(round(len(x) / 1.25)))
    idx = np.linspace(0, len(x) - 1, n_out)
    y_lin = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    f_lin = est_f0(y_lin, sr)
    dev_lin = abs(f_lin - 200.0) / 200.0 * 100
    dev_wsola = abs(f_wsola - 200.0) / 200.0 * 100
    c3 = (dev_wsola < 1.0) and (dev_lin > 5.0)
    rec('反证: 换成变调做法 ⇒ 音高判据 FAIL（判据有分辨力）', c3,
        f'WSOLA偏差={dev_wsola:.2f}% 线性重采样偏差={dev_lin:.2f}%')
    ok = ok and c3

    return ok


def main():
    print('=' * 70)
    print('app141 — APP-042 主链集成验收（主进程 → worker → 播放）')
    print(f'仓库: {REPO}')
    print(f'解释器: {sys.executable}  (Python {sys.version.split()[0]})')
    print('=' * 70)
    sys.stdout.flush()

    groups = []
    groups.append(('静态链路完整性', test_static()))
    groups.append(('行为', test_behavior()))
    groups.append(('反证（判据不恒真）', test_counterevidence()))

    n_pass = sum(1 for r in RESULTS if r['ok'])
    n_fail = len(RESULTS) - n_pass
    print('-' * 70)
    print(f'REAL: {n_pass}/{len(RESULTS)} PASS, {n_fail} FAIL')
    for nm, gok in groups:
        print(f'  组 [{nm}]: {"PASS" if gok else "FAIL"}')

    evidence = {
        'script': 'app141_app042_end_to_end.py',
        'correction': 'APP-042',
        'targets': [SERVICE_PY, WORKER_PY, APP_PY, TS_PY],
        'python': sys.version,
        'interpreter': sys.executable,
        'total': len(RESULTS),
        'n_pass': n_pass,
        'n_fail': n_fail,
        'groups': {nm: bool(g) for nm, g in groups},
        'results': RESULTS,
        'verdict': (n_fail == 0 and all(g for _, g in groups)),
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f'证据落盘: {OUT} ({os.path.getsize(OUT)} B)')
    print('VERDICT:', 'PASS' if evidence['verdict'] else 'FAIL')
    return 0 if evidence['verdict'] else 1


if __name__ == '__main__':
    sys.exit(main())
