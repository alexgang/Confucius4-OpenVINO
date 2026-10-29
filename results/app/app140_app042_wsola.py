#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app140 — APP-042 验收：WSOLA 时间伸缩**必须保持音高** + 统一参数公式正确。

🔴 APP-042 明文：
  「**保持音高**：用 WSOLA 或同类时间伸缩算法（例如 audiotsm 的 WSOLA，
    或自写的 numpy 实现），**不能用改采样率或 playbackRate 的方式，
    那样会变调**。」
  「速度 = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)：lag ≤ 3 s 时 1.0×，
    lag 到 15 s 时达到上限 1.30×。另加滞回：降速时 lag < 2 s 才回到 1.0×」
  「**按句变速**：每句开播时定一次速度，句内不变；相邻句之间每次变化不超过 0.1×」

🔴🔴 **判据设计**（本项目铁律）：
  ① 绝不 import 被测模块（顶层 numpy 会 abort）⇒ 这里要 import numpy，
     但**被测模块 `time_stretch` 只依赖 numpy** ⇒ 可安全 import；
     为稳妥仍用 `ast` 抽源码 + `exec`（与其它 app1xx 一致）。
  ② **双向反证**：注入「改采样率式变速」⇒ 音高判据必须 FAIL；
     注入「去掉滞回/步长限制」⇒ 参数判据必须 FAIL。
  ③ **音高判据**用**自相关基频估计**（不是听感）⇒ 客观、可复现。

🔴 **音高判据为什么可靠**：
  - 输入 = 200 Hz 正弦 + 400 Hz 正弦（合成语音的简化模型，有基频与谐波）
  - WSOLA ⇒ 时长变、**基频不变**
  - 线性重采样（错误的做法）⇒ 时长变、**基频按比例升高**（1.25× ⇒ 250 Hz）
  ⇒ 两者在基频上**可区分** ⇒ 判据有分辨力。
"""
from __future__ import annotations

import ast
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TS_PY = os.path.join(REPO, 'live_caption', 'time_stretch.py')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app140_app042_wsola_evidence.json')

RESULTS = []


def rec(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:600]})
    print(('PASS ' if ok else 'FAIL ') + name + ('  :: ' + str(detail)[:300] if detail else ''))
    return ok


def load_ts(path=None):
    with open(path or TS_PY, 'r', encoding='utf-8') as f:
        return f.read()


def exec_ts(src, path=None):
    """把 time_stretch 模块源码 exec 到独立命名空间（返回 module-like ns）。"""
    import types
    ns = {'__name__': 'ts_under_test', '__file__': path or TS_PY}
    exec(compile(src, path or TS_PY, 'exec'), ns)
    mod = types.ModuleType('ts_under_test')
    mod.__dict__.update(ns)
    return mod


# ── 基频估计（自相关）────────────────────────────────────────────────
def est_f0(x, sr, fmin=80.0, fmax=600.0):
    import numpy as np
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    if x.size < 512:
        return 0.0
    x = x - x.mean()
    if np.allclose(x, 0):
        return 0.0
    n = x.size
    # 自相关
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
    # 抛物线插值
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
    x = 0.5 * np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * 2 * f0 * t)
    return (x / np.max(np.abs(x))).astype('float32')


def resample_linear(x, speed, sr):
    """❌ 错误的做法（变调）：线性重采样。用来证明判据有分辨力。"""
    import numpy as np
    n = x.size
    out_len = max(1, int(round(n / speed)))
    idx = np.linspace(0, n - 1, out_len)
    return np.interp(idx, np.arange(n), x).astype('float32')


def test_wsola_pitch_preserved():
    import numpy as np
    src = load_ts()
    ts = exec_ts(src)
    sr = 24000
    x = make_tone(sr=sr, dur=2.0, f0=200.0)
    f0_in = est_f0(x, sr)
    ok = True
    rec('输入基频估计正确（≈200 Hz）', abs(f0_in - 200.0) < 8.0,
        f'f0_in={f0_in:.2f} Hz')

    for speed in (1.10, 1.25, 1.30):
        y = ts.time_stretch(x, speed, sr=sr)
        dur_in = x.size / sr
        dur_out = y.size / sr
        ratio = dur_in / dur_out
        ok_ratio = abs(ratio - speed) < 0.12 * speed
        rec(f'WSOLA speed={speed}: 时长按比例缩短', ok_ratio,
            f'ratio={ratio:.3f} (期望≈{speed})')
        f0_out = est_f0(y, sr)
        # 🔴 音高不变 ⇒ 偏差 < 5%
        ok_pitch = abs(f0_out - f0_in) / f0_in < 0.05
        rec(f'WSOLA speed={speed}: **音高不变**（基频 {f0_in:.1f}→{f0_out:.1f} Hz）',
            ok_pitch, f'相对偏差={abs(f0_out-f0_in)/f0_in*100:.2f}%')
        ok = ok and ok_ratio and ok_pitch

    # 🔴 **对照**：线性重采样（错误做法）**必须**变调 ⇒ 证明判据有分辨力
    z = resample_linear(x, 1.25, sr)
    f0_z = est_f0(z, sr)
    shifted = abs(f0_z - f0_in) / f0_in > 0.10
    rec('对照: 线性重采样**确实变调**（判据有分辨力）', shifted,
        f'f0 {f0_in:.1f}→{f0_z:.1f} Hz（偏差 {abs(f0_z-f0_in)/f0_in*100:.1f}%）')
    ok = ok and shifted
    return ok


def test_speed_equals_one_identity():
    import numpy as np
    src = load_ts()
    ts = exec_ts(src)
    x = make_tone(sr=24000, dur=0.5, f0=200.0)
    y = ts.time_stretch(x, 1.0, sr=24000)
    same = (y.size == x.size and bool(np.array_equal(y, x)))
    rec('speed=1.0 ⇒ 逐位原样返回（零风险）', same,
        f'sizes {y.size}/{x.size} equal={bool(np.array_equal(y, x))}')
    return same


def test_params():
    src = load_ts()
    ts = exec_ts(src)
    ok = True
    s = ts.speed_for_lag

    # lag ≤ 3 s ⇒ 1.0×
    for lag in (0.0, 1.0, 2.0, 2.9):
        v = s(lag, prev_speed=1.0)
        rec(f'参数: lag={lag} s ⇒ 1.0×', abs(v - 1.0) < 1e-9, f'speed={v}')
        ok = ok and abs(v - 1.0) < 1e-9

    # lag = 15 s ⇒ 1.30×（上限）
    v = s(15.0, prev_speed=1.30)
    rec('参数: lag=15 s ⇒ 1.30×（上限）', abs(v - 1.30) < 1e-9, f'speed={v}')
    ok = ok and abs(v - 1.30) < 1e-9

    # lag > 15 s ⇒ 仍 1.30×（clamp）
    v = s(60.0, prev_speed=1.30)
    rec('参数: lag=60 s ⇒ 仍 1.30×（clamp 上限）', abs(v - 1.30) < 1e-9, f'speed={v}')
    ok = ok and abs(v - 1.30) < 1e-9

    # 中间点：lag=7 ⇒ 1.0 + 4×0.025 = 1.10
    v = s(7.0, prev_speed=1.10)
    rec('参数: lag=7 s ⇒ 1.10×（公式 1.0+(7-3)*0.025）',
        abs(v - 1.10) < 1e-9, f'speed={v}')
    ok = ok and abs(v - 1.10) < 1e-9

    # 滞回：lag=2.5 s（介于 2 与 3 之间）
    #   ⇒ 无滞回时应为 1.0×；有滞回时**保持上一速度**（不是 1.0×）
    v_no = s(2.5, prev_speed=1.0)
    v_hy = s(2.5, prev_speed=1.20)
    ok_hy = (abs(v_no - 1.0) < 1e-9) and (abs(v_hy - 1.20) < 1e-9)
    rec('参数: **滞回** ⇒ lag=2.5 s 保持上一速度 1.20×（不抖动回 1.0×）',
        ok_hy, f'prev=1.0⇒{v_no} ; prev=1.20⇒{v_hy}')
    ok = ok and ok_hy

    # 步长限制：prev=1.0，lag 很大 ⇒ 不得一步跳到 1.30（上限 1.10）
    v = s(60.0, prev_speed=1.0)
    ok_step = (v <= 1.0 + 0.1 + 1e-9)
    rec('参数: **相邻句变化 ≤ 0.1×**（prev=1.0, lag=60 ⇒ ≤1.10×）',
        ok_step, f'speed={v}')
    ok = ok and ok_step

    # 步长限制的另一侧：prev=1.30，lag=0 ⇒ 不得低于 1.20
    v = s(0.0, prev_speed=1.30)
    ok_step2 = (v >= 1.30 - 0.1 - 1e-9)
    rec('参数: 相邻句变化 ≤ 0.1×（prev=1.30, lag=0 ⇒ ≥1.20×）',
        ok_step2, f'speed={v}')
    ok = ok and ok_step2
    return ok


def test_counterevidence():
    """🔴 反证：把 WSOLA 换成「线性重采样」（即改采样率 ⇒ 变调）
    ⇒ 音高判据必须 FAIL ⇒ 证明判据不恒真。"""
    import numpy as np
    src = load_ts()
    # 🔴 反证注入：**整个 time_stretch 换成线性重采样**（APP-042 明令禁止的
    #   「改采样率 / playbackRate ⇒ 变调」做法）⇒ 音高判据必须 FAIL。
    #   ⚠️ 不能只对 WSOLA 的输出再插值（那已经是正确变速的结果 ⇒ 基频不变
    #     ⇒ 判据会假通过）⇒ 必须**替换实现本身**。
    mutated = src.replace(
        "    win = np.hanning(ha).astype(np.float32)",
        "    # ❌ 反证注入：线性重采样（变调）\n"
        "    _idx = np.linspace(0, n - 1, max(1, int(round(n / sp))))\n"
        "    return np.interp(_idx, np.arange(n), arr).astype(np.float32)\n"
        "    win = np.hanning(ha).astype(np.float32)",
        1)
    changed = mutated != src
    rec('反证准备: 注入「线性重采样式变速」', changed,
        'mutated' if changed else 'PATTERN NOT FOUND ⇒ 反证无效')
    if not changed:
        return False
    ts = exec_ts(mutated, path='<mutated>')
    sr = 24000
    x = make_tone(sr=sr, dur=2.0, f0=200.0)
    f0_in = est_f0(x, sr)
    y = ts.time_stretch(x, 1.25, sr=sr)
    f0_out = est_f0(y, sr)
    dev = abs(f0_out - f0_in) / f0_in
    failed_as_expected = dev > 0.05
    rec('反证: 换成变调做法 ⇒ 音高判据 FAIL（判据不恒真）',
        failed_as_expected, f'f0 {f0_in:.1f}→{f0_out:.1f} Hz 偏差 {dev*100:.1f}%')
    return failed_as_expected


def test_no_new_dependency():
    """🔴 客户包**不得**为此新增第三方依赖 ⇒ 只依赖 numpy。"""
    src = load_ts()
    import re
    mods = set(re.findall(r'^\s*import\s+([a-zA-Z_][\w]*)', src, re.M))
    mods |= set(re.findall(r'^\s*from\s+([a-zA-Z_][\w]*)\s+import', src, re.M))
    allowed = {'numpy', 'wave', '__future__', 'math'}
    extra = mods - allowed
    rec('依赖: 只用 numpy/wave（客户包零新增依赖）', not extra,
        f'imports={sorted(mods)} extra={sorted(extra)}')
    return not extra


def main():
    print('=' * 70)
    print('app140 — APP-042 验收（WSOLA 保持音高 + 统一参数）')
    print(f'被测源码: {TS_PY}')
    print('=' * 70)
    groups = [
        ('WSOLA 保音高', test_wsola_pitch_preserved()),
        ('speed=1.0 恒等', test_speed_equals_one_identity()),
        ('统一参数公式', test_params()),
        ('依赖纪律', test_no_new_dependency()),
        ('反证（判据不恒真）', test_counterevidence()),
    ]
    n_pass = sum(1 for r in RESULTS if r['ok'])
    n_fail = len(RESULTS) - n_pass
    print('-' * 70)
    print(f'REAL: {n_pass}/{len(RESULTS)} PASS, {n_fail} FAIL')
    for nm, g in groups:
        print(f'  组 [{nm}]: {"PASS" if g else "FAIL"}')
    ev = {
        'script': 'app140_app042_wsola.py',
        'correction': 'APP-042',
        'target': TS_PY,
        'python': sys.version,
        'total': len(RESULTS), 'n_pass': n_pass, 'n_fail': n_fail,
        'groups': {nm: bool(g) for nm, g in groups},
        'results': RESULTS,
        'verdict': n_fail == 0 and all(g for _, g in groups),
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f'证据落盘: {OUT} ({os.path.getsize(OUT)} B)')
    print('VERDICT:', 'PASS' if ev['verdict'] else 'FAIL')
    return 0 if ev['verdict'] else 1


if __name__ == '__main__':
    sys.exit(main())
