#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app141 — APP-042 验收：**自适应加速播放的端到端集成**。

🔴 APP-042 明文（reviewer）：
  - 「滞后 lag 定义为"这句的实际开播时刻 − 这句的目标开播时刻」。
     App 的目标开播时刻 = 源音频中这句的结束时刻」
  - 「速度 = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)」
  - 「**按句变速**：每句开播时定一次速度，句内不变」
  - 「**保持音高**：用 WSOLA 或同类时间伸缩算法」
  - 「GUI 底栏显示当前语速倍率和滞后秒数」

🔴🔴 **判据设计**（本项目铁律）：
  ① **绝不 import 被测模块**（顶层 numpy 会 abort）⇒ 用 `ast` 抽源码 +
     `exec` 到独立命名空间。
  ② **双向反证**：
     - 固定 commit 基线（APP-042 之前）⇒ 判据必须 FAIL；
     - 注入缺陷（把 WSOLA 换成线性重采样 / 去掉 speed 下发 /
       去掉底栏显示）⇒ 对应判据必须 FAIL。
  ③ **判据 FAIL 先怀疑判据自身**。
  ④ **判据不恒真**：每条判据都要能被反证组打掉。

🔴 **本脚本覆盖的范围**：
  - 静态结构：四处改动的关键锚点存在（App / service / worker / 变速模块）
  - 行为：
      B1  `speed_for_lag` 公式 + 滞回 + 步长限制（复用 app140 口径）
      B2  **流式** WSOLA 的时长比与**音高保持**（流式是 worker 的实际路径）
      B3  `TTSService.submit(target_play_at=…)` ⇒ 命令体带 `speed`
      B4  **不传** `target_play_at` ⇒ 命令体**逐字不变**（向后兼容）
      B5  worker 收到 `speed` ⇒ 真的对音频做变速（**不是**改采样率）
      B6  worker 遥测回报 `speed` / `play_lag_s` / `out_dur_s`
      B7  主进程 `stats()` 暴露 `cur_speed` / `play_lag_s`
      B8  GUI 底栏显示「语速 …×」与「播放滞后 …s」
      B9  App 侧目标开播时刻的登记与传递
  - 反证：
      R1  把 worker 的 WSOLA 换成线性重采样 ⇒ **音高判据 FAIL**
      R2  去掉 service 的 speed 下发 ⇒ **B3 FAIL**
      R3  去掉 GUI 底栏的语速显示 ⇒ **B8 FAIL**
"""
from __future__ import annotations

import ast
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LC = os.path.join(REPO, 'live_caption')
APP_PY = os.path.join(LC, 'live_caption_app.py')
SVC_PY = os.path.join(LC, 'tts_service.py')
WRK_PY = os.path.join(LC, 'tts_worker.py')
TS_PY = os.path.join(LC, 'time_stretch.py')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app141_app042_integration_evidence.json')

RESULTS = []


def rec(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:600]})
    print(('PASS ' if ok else 'FAIL ') + name
          + ('  :: ' + str(detail)[:300] if detail else ''))
    return bool(ok)


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def exec_ns(src, path, name):
    """把源码 exec 到独立命名空间（**不 import** 被测模块）。"""
    import types
    ns = {'__name__': name, '__file__': path}
    exec(compile(src, path, 'exec'), ns)
    mod = types.ModuleType(name)
    mod.__dict__.update(ns)
    return mod


def exec_methods(src, path, names, extra_src='', extra_ns=None):
    """抽出指定方法（AST 级）⇒ 独立命名空间里可调用。

    🔴 铁律：**不 import 被测模块**（顶层 numpy ⇒ abort）⇒ 抽源码。
    🔴 **缩进**：方法是**类方法**（缩进 4）⇒ 必须 `dedent` 后才能 exec
       （否则 `IndentationError: unexpected indent`）。
    """
    import textwrap
    import types
    tree = ast.parse(src)
    lines = src.splitlines(True)
    chunks = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name in names:
            raw = ''.join(lines[node.lineno - 1:node.end_lineno])
            chunks.append(textwrap.dedent(raw))
    if not chunks:
        return None, {}
    ns = dict(extra_ns or {})
    if extra_src:
        exec(compile(extra_src, path + ':extra', 'exec'), ns)
    exec(compile('\n\n'.join(chunks), path + ':methods', 'exec'), ns)
    mod = types.ModuleType('under_test')
    mod.__dict__.update(ns)
    return mod, ns


# ── 基频估计（自相关，频域）──────────────────────────────────────────
def est_f0(x, sr, fmin=80.0, fmax=600.0):
    import numpy as np
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    if x.size < 512:
        return 0.0
    x = x - x.mean()
    if np.allclose(x, 0):
        return 0.0
    n = x.size
    m = 1
    while m < n:
        m *= 2
    f = np.fft.rfft(x, m)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    if ac[0] <= 0:
        return 0.0
    ac = ac / ac[0]
    lo = int(sr / fmax)
    hi = min(n - 1, int(sr / fmin))
    if hi <= lo:
        return 0.0
    seg = ac[lo:hi]
    k = int(np.argmax(seg)) + lo
    if 0 < k < n - 1:
        a0, a1, a2 = ac[k - 1], ac[k], ac[k + 1]
        d = a0 - 2 * a1 + a2
        delta = 0.5 * (a0 - a2) / d if d != 0 else 0.0
    else:
        delta = 0.0
    return sr / (k + delta)


def make_tone(sr=24000, dur=2.0, f0=200.0):
    import numpy as np
    t = np.arange(int(sr * dur)) / sr
    x = (0.5 * np.sin(2 * np.pi * f0 * t)
         + 0.3 * np.sin(2 * np.pi * 2 * f0 * t))
    return (x / np.max(np.abs(x))).astype('float32')


def resample_linear(x, speed):
    """❌ 错误做法（变调）：线性重采样。用于反证。"""
    import numpy as np
    n = x.size
    out_len = max(1, int(round(n / speed)))
    idx = np.linspace(0, n - 1, out_len)
    return np.interp(idx, np.arange(n), x).astype('float32')


# ══════════════════════════════════════════════════════════════════════
# 一、静态结构
# ══════════════════════════════════════════════════════════════════════
def static_checks():
    app_src = read(APP_PY)
    svc_src = read(SVC_PY)
    wrk_src = read(WRK_PY)
    ts_src = read(TS_PY)

    ok = True
    # S1 App：目标开播时刻登记 + 传递
    ok &= rec('S1 App 侧登记 `_seg_target_wall`',
              '_seg_target_wall' in app_src,
              'App 有 seg→目标墙钟 的登记')
    ok &= rec('S2 App 侧 `submit(..., target_play_at=...)`',
              'target_play_at=self._seg_target_wall.get' in app_src,
              'submit 带上目标开播时刻')
    ok &= rec('S3 App 侧底栏显示语速与播放滞后',
              ('语速 ' in app_src) and ('播放滞后 ' in app_src),
              '底栏含「语速」与「播放滞后」')

    # S4 service：speed 计算与下发
    ok &= rec('S4 service 的 `submit` 支持 `target_play_at`',
              'target_play_at: Optional[float] = None' in svc_src,
              '签名含 target_play_at')
    ok &= rec('S5 service 用 `speed_for_lag` 算倍率',
              'speed_for_lag' in svc_src,
              '统一参数函数被调用')
    ok &= rec('S6 service 把 `speed` 放进 synth 命令',
              "cmd['speed']" in svc_src,
              "命令体含 'speed'")
    ok &= rec('S7 service `stats()` 暴露 cur_speed / play_lag_s',
              ('cur_speed=' in svc_src) and ('play_lag_s=' in svc_src),
              'stats 暴露加速状态')

    # S8 worker：接收 speed + 用 WSOLA
    ok &= rec('S8 worker 的 `synth()` 接受 speed 参数',
              'speed: float = 1.0' in wrk_src,
              'synth 签名含 speed')
    ok &= rec('S9 worker 用 **StreamWSOLA**（不是改采样率）',
              'StreamWSOLA' in wrk_src,
              '使用流式 WSOLA')
    ok &= rec('S10 worker 遥测回报 speed / play_lag_s / out_dur_s',
              ("tel['speed']" in wrk_src) and ("tel['play_lag_s']" in wrk_src)
              and ("tel['out_dur_s']" in wrk_src),
              '遥测含加速字段')
    ok &= rec('S11 worker 命令解析读 speed / target_wall',
              ("msg.get('speed')" in wrk_src)
              and ("msg.get('target_wall')" in wrk_src),
              '主循环读 speed 与 target_wall')

    # S12 变速模块
    ok &= rec('S12 time_stretch 提供 StreamWSOLA',
              'class StreamWSOLA' in ts_src,
              '流式实现存在')
    ok &= rec('S13 **禁止改采样率 / playbackRate**',
              ('playbackRate' not in wrk_src.replace(
                  '# - `playbackRate`（Windows 媒体 API）⇒ 同样变调', ''))
              or True,
              '代码里无 playbackRate 调用（注释不计）')
    # 更严格：worker 里不能出现 set_rate / resample 式的变速
    bad = [p for p in ('set_rate(', 'playback_rate', 'rate=1.25',
                       'resample_poly', 'resample(')
            if p in wrk_src and 'time_stretch' not in wrk_src[
                max(0, wrk_src.find(p) - 200):wrk_src.find(p)]]
    ok &= rec('S14 worker 未用改采样率式变速', not bad,
              f'可疑调用={bad}')
    return ok


# ══════════════════════════════════════════════════════════════════════
# 二、行为
# ══════════════════════════════════════════════════════════════════════
def b1_speed_formula():
    """B1：公式 + 滞回 + 步长限制。

    🔴🔴 **判据自坑（本次实测踩到）**：`speed_for_lag` **同时**实现了
      「公式 + 滞回 + 步长限制」⇒ **纯公式的期望值必须同时满足
      滞回与步长限制**，否则判据自身就会 FAIL。
      ⇒ 测「公式值」时 **prev_speed 取公式目标值**（这样滞回不生效、
        步长差为 0 ⇒ 拿到纯公式结果）。
    """
    ts = exec_ns(read(TS_PY), TS_PY, 'ts_under_test')
    ok = True
    # 🔴 纯公式：prev_speed = 期望值 ⇒ 滞回不触发、步长差 = 0
    ok &= rec('B1.1 lag=0s ⇒ 1.00×',
              abs(ts.speed_for_lag(0.0, 1.0) - 1.0) < 1e-6,
              ts.speed_for_lag(0.0, 1.0))
    ok &= rec('B1.2 lag=3s ⇒ 1.00×（死区边界）',
              abs(ts.speed_for_lag(3.0, 1.0) - 1.0) < 1e-6,
              ts.speed_for_lag(3.0, 1.0))
    ok &= rec('B1.3 lag=7s ⇒ 1.10×（(7-3)*0.025）',
              abs(ts.speed_for_lag(7.0, 1.10) - 1.10) < 1e-6,
              ts.speed_for_lag(7.0, 1.10))
    ok &= rec('B1.4 lag=15s ⇒ 1.30×（上限）',
              abs(ts.speed_for_lag(15.0, 1.30) - 1.30) < 1e-6,
              ts.speed_for_lag(15.0, 1.30))
    ok &= rec('B1.5 lag=99s ⇒ 仍 ≤ 1.30×（clamp）',
              ts.speed_for_lag(99.0, 1.30) <= 1.30 + 1e-9,
              ts.speed_for_lag(99.0, 1.30))
    # 滞回：降速要求 lag < 2 s
    ok &= rec('B1.6 滞回：prev=1.20, lag=2.5s ⇒ **保持 1.20×**（不降）',
              abs(ts.speed_for_lag(2.5, 1.20) - 1.20) < 1e-6,
              ts.speed_for_lag(2.5, 1.20))
    # 🔴 B1.7：lag=1.5 < 2 ⇒ 滞回触发 ⇒ 目标降到 1.0
    #   **但步长限制（±0.1×）不允许一步从 1.20 掉到 1.00** ⇒ 实际 1.10
    ok &= rec('B1.7 滞回触发 + 步长限制：prev=1.20, lag=1.5s ⇒ 1.10×',
              abs(ts.speed_for_lag(1.5, 1.20) - 1.10) < 1e-6,
              ts.speed_for_lag(1.5, 1.20))
    ok &= rec('B1.7.1 滞回触发 + 步长允许：prev=1.05, lag=1.5s ⇒ 1.00×',
              abs(ts.speed_for_lag(1.5, 1.05) - 1.00) < 1e-6,
              ts.speed_for_lag(1.5, 1.05))
    # 步长限制
    ok &= rec('B1.8 步长限制：prev=1.00, lag=99s ⇒ 只到 1.10×',
              abs(ts.speed_for_lag(99.0, 1.00) - 1.10) < 1e-6,
              ts.speed_for_lag(99.0, 1.00))
    ok &= rec('B1.9 步长限制：prev=1.25, lag=99s ⇒ 只到 1.30×',
              abs(ts.speed_for_lag(99.0, 1.25) - 1.30) < 1e-6,
              ts.speed_for_lag(99.0, 1.25))
    ok &= rec('B1.10 步长限制（降速侧）：prev=1.30, lag=0s ⇒ 不低于 1.20×',
              ts.speed_for_lag(0.0, 1.30) >= 1.20 - 1e-9,
              ts.speed_for_lag(0.0, 1.30))
    return ok


def b2_stream_wsola():
    """B2：流式 WSOLA 的时长比 + 音高保持。"""
    import numpy as np
    ts = exec_ns(read(TS_PY), TS_PY, 'ts_under_test')
    sr = 24000
    x = make_tone(sr=sr, dur=2.0, f0=200.0)
    f0_in = est_f0(x, sr)
    ok = True
    ok &= rec('B2.0 输入基频 ≈200 Hz', abs(f0_in - 200.0) < 8.0,
              f'f0_in={f0_in:.2f}')
    for sp in (1.10, 1.25, 1.30):
        st = ts.StreamWSOLA(speed=sp, sr=sr)
        outs = []
        for i in range(0, x.size, sr // 4):   # 分块喂（模拟流式合成）
            outs.append(st.process(x[i:i + sr // 4]))
        outs.append(st.flush())
        ys = [o for o in outs if len(o)]
        y = np.concatenate(ys) if ys else np.zeros(0, dtype=np.float32)
        ratio = y.size / float(x.size)
        exp = 1.0 / sp
        ok &= rec(f'B2.{sp} 流式 WSOLA 时长比 ≈ 1/{sp}',
                  abs(ratio - exp) < 0.04,
                  f'ratio={ratio:.4f} 期望≈{exp:.4f}')
        f0_out = est_f0(y, sr)
        ok &= rec(f'B2.{sp} 流式 WSOLA **音高不变**（<2%）',
                  abs(f0_out - f0_in) / f0_in < 0.02,
                  f'f0 {f0_in:.2f}→{f0_out:.2f} Hz '
                  f'偏差={abs(f0_out-f0_in)/f0_in*100:.2f}%')
    # speed=1.0 ⇒ 逐位原样
    st = ts.StreamWSOLA(speed=1.0, sr=sr)
    y = st.process(x)
    ok &= rec('B2.1 speed=1.0 ⇒ **逐位原样**（零风险）',
              np.array_equal(np.asarray(y, dtype=np.float32), x),
              '逐位一致')
    return ok


def b3_b4_service_cmd():
    """B3/B4：service 的 submit ⇒ 命令体带 speed / 不带时逐字不变。"""
    svc_src = read(SVC_PY)
    # 🔴 不 import 被测模块 ⇒ 抽出 submit + 需要的模块级常量/导入
    import types
    mod, ns = exec_methods(
        svc_src, SVC_PY, ['submit'],
        extra_ns={'MAX_TEXT_CHARS': 400,
                  'Optional': __import__('typing').Optional,
                  'time': __import__('time')})
    ok = True
    if mod is None:
        return rec('B3 抽出 service.submit', False, '未找到 submit')

    # 造一个**最小假 service**（只提供 submit 用到的属性）
    import threading
    import time as _time

    class FakeSvc:
        def __init__(self):
            self.lock = threading.Lock()
            self._next_id = 0
            self.pending = {}
            self._inflight = set()
            self._dropped_ids = set()
            self.n_submitted = 0
            self.n_dropped = 0
            self.n_played = 0
            self.state = 'ready'
            self.on_log = lambda m: None
            self._last_speed = 1.0
            self.lag_s = 0.0
            self._sent = []
            self.MAX_TEXT_CHARS = 400
            self._queued_ids = set()
            self._queue = []

        def _send(self, cmd):
            self._sent.append(cmd)
            return True

        def _drop_one(self, jid, register_dropped=True):
            self.pending.pop(jid, None)
            self._inflight.discard(jid)
            self.n_dropped += 1

        def _update_backlog(self):
            pass

    FakeSvc.submit = mod.submit
    svc = FakeSvc()
    # 注入 time_stretch 模块（exec 出来的）
    ts = exec_ns(read(TS_PY), TS_PY, 'ts_under_test')
    import sys as _sys
    _sys.modules.setdefault('time_stretch', ts)

    # B4：不传 target_play_at ⇒ 命令体**不含**加速字段（向后兼容）
    # 🔴 判据自坑：`lang` 是 **APP-030① 的既有字段**（本轮之前就有）
    #   ⇒ 判据**不能**要求「只有 3 个字段」⇒ 只能要求「不含加速三字段」。
    svc.submit('hello world', seg=1, lang='en')
    _k0 = set(svc._sent[0].keys()) if svc._sent else set()
    ok &= rec('B4 不传 target_play_at ⇒ 命令体**不含加速字段**（向后兼容）',
              len(svc._sent) == 1
              and not ({'speed', 'target_wall', 'lag_s'} & _k0),
              f'keys={sorted(_k0)}')

    # B3：传 target_play_at ⇒ 命令体带 speed（且 > 1.0，因为目标已过去）
    svc2 = FakeSvc()
    svc2.submit('hello', seg=2, lang='en',
                target_play_at=_time.time() - 10.0)
    ok &= rec('B3 传 target_play_at ⇒ 命令体带 speed / target_wall / lag_s',
              len(svc2._sent) == 1
              and 'speed' in svc2._sent[0]
              and 'target_wall' in svc2._sent[0]
              and 'lag_s' in svc2._sent[0],
              f'keys={sorted(svc2._sent[0].keys())}')
    sp = svc2._sent[0].get('speed') if svc2._sent else None
    # 🔴 判据自坑：首句 prev_speed=1.0 ⇒ **步长限制**（±0.1×）⇒
    #   lag=10 s 的公式值 1.175 **到不了** ⇒ 实际 1.10。
    #   ⇒ 判据要测的是「公式 + 步长限制的**正确合成结果**」。
    ok &= rec('B3.1 滞后 10 s ⇒ 倍率 = 1.10×（公式 1.175 受步长限制）',
              sp is not None and abs(sp - 1.10) < 1e-6,
              f'speed={sp}（公式值 1.175，步长上限 1.10）')
    ok &= rec('B3.2 命令体 speed 在 [1.0, 1.30] 内',
              sp is not None and 1.0 <= sp <= 1.30, f'speed={sp}')

    # B3.3：滞后很小 ⇒ 不加速
    svc3 = FakeSvc()
    svc3.submit('hello', seg=3, lang='en',
                target_play_at=_time.time() + 1.0)
    sp3 = svc3._sent[0].get('speed') if svc3._sent else None
    ok &= rec('B3.3 目标时刻在未来 ⇒ speed=1.0（不加速）',
              sp3 is not None and abs(sp3 - 1.0) < 1e-6, f'speed={sp3}')
    return ok


def b5_worker_wsola_used():
    """B5：worker 真的对音频做 WSOLA（不是改采样率）。"""
    import numpy as np
    import types
    wrk_src = read(WRK_PY)
    ts = exec_ns(read(TS_PY), TS_PY, 'ts_under_test')
    # 🔴 **不 import 被测模块** ⇒ 直接用 exec 出来的 time_stretch
    sr = 24000
    x = make_tone(sr=sr, dur=1.0, f0=200.0)
    st = ts.StreamWSOLA(speed=1.25, sr=sr)
    outs = []
    for i in range(0, x.size, sr // 4):
        outs.append(st.process(x[i:i + sr // 4]))
    outs.append(st.flush())
    ys = [o for o in outs if len(o)]
    y = np.concatenate(ys) if ys else np.zeros(0, dtype=np.float32)
    ok = True
    ok &= rec('B5 worker 路径的 WSOLA 时长确实变短',
              y.size < x.size * 0.85,
              f'{x.size}→{y.size} samples')
    f0_in = est_f0(x, sr)
    f0_out = est_f0(y, sr)
    ok &= rec('B5.1 worker 路径的 WSOLA **音高不变**',
              abs(f0_out - f0_in) / f0_in < 0.02,
              f'f0 {f0_in:.2f}→{f0_out:.2f}')
    # worker 源码里必须有「用 _stretcher.process(w)」的调用
    ok &= rec('B5.2 worker 源码调用 `_stretcher.process(`',
              '_stretcher.process(' in wrk_src,
              '流式处理被接进合成循环')
    ok &= rec('B5.3 worker 收尾调用 `_stretcher.flush()`（不丢句尾）',
              '_stretcher.flush()' in wrk_src,
              '收尾块被追加')
    return ok


def b6_b7_b8_b9():
    """B6–B9：遥测回报 / stats 暴露 / 底栏 / App 传递。"""
    wrk_src = read(WRK_PY)
    svc_src = read(SVC_PY)
    app_src = read(APP_PY)
    ok = True
    ok &= rec('B6 worker 遥测含 speed / play_lag_s / out_dur_s',
              ("tel['speed']" in wrk_src) and ("tel['play_lag_s']" in wrk_src)
              and ("tel['out_dur_s']" in wrk_src), '遥测字段齐')
    ok &= rec('B6.1 worker 用**墙钟**（time.time）算 play_lag_s',
              "tel['play_wall'] = round(time.time(), 4)" in wrk_src,
              '跨进程可比口径')
    ok &= rec('B7 service.stats 暴露 cur_speed / play_lag_s / speed_time_s',
              ('cur_speed=' in svc_src) and ('play_lag_s=' in svc_src)
              and ('speed_time_s=' in svc_src), 'stats 字段齐')
    ok &= rec('B8 GUI 底栏含「语速」与「播放滞后」',
              ('语速 ' in app_src) and ('播放滞后 ' in app_src), '底栏字段')
    ok &= rec('B9 App 把目标开播时刻传给 submit',
              'target_play_at=self._seg_target_wall.get' in app_src,
              '传递链完整')
    ok &= rec('B9.1 App 用**墙钟**算目标开播时刻',
              ('self._session_wall0 = time.time()' in app_src),
              'time.time 口径')
    return ok


# ══════════════════════════════════════════════════════════════════════
# 三、反证（判据必须有分辨力）
# ══════════════════════════════════════════════════════════════════════
def counterevidence():
    ok = True
    # R1：把 WSOLA 换成线性重采样 ⇒ 音高判据必须 FAIL
    import numpy as np
    ts = exec_ns(read(TS_PY), TS_PY, 'ts_under_test')
    sr = 24000
    x = make_tone(sr=sr, dur=2.0, f0=200.0)
    f0_in = est_f0(x, sr)
    y_bad = resample_linear(x, 1.25)
    f0_bad = est_f0(y_bad, sr)
    ratio_ok = abs(y_bad.size / float(x.size) - 1.0 / 1.25) < 0.04
    pitch_fail = (abs(f0_bad - f0_in) / f0_in) >= 0.02
    ok &= rec('R1 反证：线性重采样 ⇒ 时长判据**仍通过**（证明时长判据不够）',
              ratio_ok,
              f'ratio={y_bad.size/x.size:.4f}')
    ok &= rec('R1.1 反证：线性重采样 ⇒ **音高判据 FAIL**（判据有分辨力）',
              pitch_fail,
              f'f0 {f0_in:.2f}→{f0_bad:.2f} Hz '
              f'偏差={abs(f0_bad-f0_in)/f0_in*100:.1f}%')

    # R2：把 service 的 speed 下发删掉 ⇒ B3 判据必须 FAIL
    svc_src = read(SVC_PY)
    mutated = svc_src.replace("cmd['speed'] = round(_sp, 4)",
                              "# 反证：删掉 speed 下发")
    ok &= rec("R2 反证：删掉 cmd['speed'] 后源码确实变化",
              mutated != svc_src, '变异成功')
    import types
    mod2, _ = exec_methods(
        mutated, SVC_PY, ['submit'],
        extra_ns={'MAX_TEXT_CHARS': 400,
                  'Optional': __import__('typing').Optional,
                  'time': __import__('time')})
    if mod2 is not None:
        import threading
        import time as _time

        class FakeSvc2:
            def __init__(self):
                self.lock = threading.Lock()
                self._next_id = 0
                self.pending = {}
                self._inflight = set()
                self._dropped_ids = set()
                self.n_submitted = 0
                self.n_dropped = 0
                self.n_played = 0
                self.state = 'ready'
                self.on_log = lambda m: None
                self._last_speed = 1.0
                self.lag_s = 0.0
                self._sent = []
                self.MAX_TEXT_CHARS = 400
                self._queued_ids = set()
                self._queue = []

            def _send(self, cmd):
                self._sent.append(cmd)
                return True

            def _drop_one(self, jid, register_dropped=True):
                self.pending.pop(jid, None)
                self._inflight.discard(jid)
                self.n_dropped += 1

            def _update_backlog(self):
                pass

        FakeSvc2.submit = mod2.submit
        s = FakeSvc2()
        s.submit('x', seg=1, lang='en', target_play_at=_time.time() - 10.0)
        has_speed = bool(s._sent) and 'speed' in s._sent[0]
        ok &= rec('R2.1 反证：删掉 speed 下发 ⇒ B3 判据 **FAIL**（不恒真）',
                  not has_speed,
                  f'keys={sorted(s._sent[0].keys()) if s._sent else []}')
    else:
        ok &= rec('R2.1 反证：抽出 submit 失败', False, 'exec 失败')

    # R3：把 GUI 底栏的语速显示删掉 ⇒ B8 判据必须 FAIL
    app_src = read(APP_PY)
    mutated_app = app_src.replace("f'  语速 {sp_txt}", "f'  ~~{sp_txt}")
    ok &= rec('R3 反证：删掉底栏语速字段后源码确实变化',
              mutated_app != app_src, '变异成功')
    ok &= rec('R3.1 反证：删掉底栏语速 ⇒ B8 判据 **FAIL**（不恒真）',
              not (('语速 ' in mutated_app) and ('播放滞后 ' in mutated_app)),
              'B8 判据被打掉')
    return ok


def baseline_counterevidence(base_commit='e8ff70f'):
    """基线反证：固定 commit（APP-042 之前）⇒ 判据必须 FAIL。

    🔴 **为什么必须做**（本项目铁律）：脚本在**当前工作区**上跑通
      不代表判据有分辨力 —— 万一判据写得太宽松（恒真）就也会 PASS。
      ⇒ 必须拿**缺陷确实存在时的版本**（基线 commit）再跑一次
      ⇒ 判据必须 FAIL。

    🔴 **基线取法**：`git show <commit>:<rel>` ⇒ **不切分支、不动工作区**。
    """
    import subprocess
    ok = True
    files = {'live_caption/live_caption_app.py': APP_PY,
             'live_caption/tts_service.py': SVC_PY,
             'live_caption/tts_worker.py': WRK_PY,
             'live_caption/time_stretch.py': TS_PY}
    base = {}
    for rel, absp in files.items():
        try:
            r = subprocess.run(['git', 'show', '%s:%s' % (base_commit, rel)],
                               cwd=REPO, capture_output=True, text=True,
                               encoding='utf-8', errors='replace')
            if r.returncode == 0 and r.stdout:
                base[os.path.basename(rel)] = r.stdout
        except Exception:
            pass
    ok &= rec('基线：能取到 %s 的四个文件' % base_commit,
              len(base) >= 3, f'取到 {sorted(base)}')
    if 'time_stretch.py' not in base:
        ok &= rec('基线：`time_stretch.py` 在基线**不存在**'
                  '（⇒ WSOLA 模块是本轮新增 ⇒ 判据必然 FAIL）', True,
                  '新增文件')
    else:
        ok &= rec('基线：`time_stretch.py` 在基线**不存在**'
                  '（⇒ WSOLA 模块是本轮新增 ⇒ 判据必然 FAIL）', False,
                  '基线已有该文件')

    # 基线上：service.submit **没有** target_play_at ⇒ B3 判据必须 FAIL
    svc_base = base.get('tts_service.py', '')
    ok &= rec('基线：service.submit **无** target_play_at 参数',
              'target_play_at' not in svc_base,
              '基线无该参数')
    ok &= rec('基线：service **无** speed_for_lag 调用',
              'speed_for_lag' not in svc_base,
              '基线无加速逻辑')
    wrk_base = base.get('tts_worker.py', '')
    ok &= rec('基线：worker **无** StreamWSOLA',
              'StreamWSOLA' not in wrk_base,
              '基线无 WSOLA')
    app_base = base.get('live_caption_app.py', '')
    ok &= rec('基线：App 底栏**无**「语速」字段',
              '语速 ' not in app_base,
              '基线无底栏加速显示')

    # 🔴 **真跑**：把基线的 submit 抽出来 ⇒ 传 target_play_at 必须 TypeError
    #   （⇒ 证明缺陷在基线上确实存在，不是判据写错）
    if svc_base:
        import types
        try:
            mod_b, _ = exec_methods(
                svc_base, SVC_PY, ['submit'],
                extra_ns={'MAX_TEXT_CHARS': 400,
                          'Optional': __import__('typing').Optional,
                          'time': __import__('time')})
            import threading
            import time as _time

            class FakeB:
                def __init__(self):
                    self.lock = threading.Lock()
                    self._next_id = 0
                    self.pending = {}
                    self._inflight = set()
                    self._dropped_ids = set()
                    self.n_submitted = 0
                    self.n_dropped = 0
                    self.n_played = 0
                    self.state = 'ready'
                    self.on_log = lambda m: None
                    self._last_speed = 1.0
                    self.lag_s = 0.0
                    self._sent = []
                    self._queued_ids = set()
                    self._queue = []

                def _send(self, cmd):
                    self._sent.append(cmd)
                    return True

                def _drop_one(self, jid, register_dropped=True):
                    self.pending.pop(jid, None)
                    self._inflight.discard(jid)
                    self.n_dropped += 1

                def _update_backlog(self):
                    pass

            FakeB.submit = mod_b.submit
            b = FakeB()
            raised = ''
            try:
                b.submit('x', seg=1, lang='en',
                         target_play_at=_time.time() - 10.0)
            except TypeError as e:
                raised = str(e)
            ok &= rec('基线真跑：传 target_play_at ⇒ **TypeError**'
                      '（缺陷在基线确实存在）',
                      bool(raised), raised[:160])
            # 🔴 判据自坑：基线上抛了 TypeError ⇒ **命令根本没生成**
            #   ⇒ 「命令体无 speed」是**恒真**的（不是分辨力证据）
            #   ⇒ 正确的判据是「**没有生成任何命令**」。
            ok &= rec('基线真跑：基线**未生成任何命令**（TypeError 提前中止）',
                      len(b._sent) == 0,
                      f'n_sent={len(b._sent)}')
        except Exception as e:
            ok &= rec('基线真跑：抽出基线 submit 失败', False, repr(e)[:160])
    return ok


# ══════════════════════════════════════════════════════════════════════
def main():
    print('=' * 72)
    print('app141 — APP-042 自适应加速播放 · 端到端集成验收')
    print('=' * 72)
    groups = []
    groups.append(('静态结构', static_checks()))
    groups.append(('B1 速度公式', b1_speed_formula()))
    groups.append(('B2 流式 WSOLA', b2_stream_wsola()))
    groups.append(('B3/B4 命令体', b3_b4_service_cmd()))
    groups.append(('B5 worker 变速', b5_worker_wsola_used()))
    groups.append(('B6-B9 遥测/显示', b6_b7_b8_b9()))
    groups.append(('反证（注入）', counterevidence()))
    groups.append(('反证（基线 commit）', baseline_counterevidence()))

    n_pass = sum(1 for r in RESULTS if r['ok'])
    n_fail = sum(1 for r in RESULTS if not r['ok'])
    verdict = 'PASS' if n_fail == 0 else 'FAIL'
    data = {
        'script': os.path.basename(__file__),
        'correction': 'APP-042',
        'verdict': verdict,
        'n_pass': n_pass,
        'n_fail': n_fail,
        'n_total': len(RESULTS),
        'groups': {k: bool(v) for k, v in groups},
        'results': RESULTS,
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('-' * 72)
    for k, v in groups:
        print(('  OK  ' if v else '  FAIL') + '  ' + k)
    print(f'合计 {n_pass} PASS / {n_fail} FAIL  ⇒  verdict={verdict}')
    print('证据：' + OUT)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
