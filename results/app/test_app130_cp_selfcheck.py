#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130 单测：**code predictor 的 NPU 自检兜底 + 运行时保险**（不需要 NPU）。

## 覆盖的判据（reviewer APP-130 §要做的 3）

1. 自检走「**替换**」路径：NPU 版输出与 CPU 版一致 ⇒ `_cp_selfcheck` ok=True
   ⇒ `_move_cp_prefill_to_npu` **真的替换** `eng.cp_prefill`。
2. 自检走「**保留 CPU**」路径：
   - NPU 版输出含 NaN ⇒ ok=False ⇒ `eng.cp_prefill` **原样不动**；
   - NPU 版输出方向不同（余弦 < 0.99）⇒ ok=False ⇒ 原样不动。
3. 运行时保险在**假 NaN 输出**下 **1 步内停** ＋ 记 `tts_runaway`。

## 判据纪律

- 🔴 **PASS ≠ 正确**：每个「应当拦住」的用例都必须**真的被拦住**（断言状态），
  而不是「函数没抛异常」。
- 🔴 反证组：把 fake 换成「好」的 ⇒ 必须走**另一条**路（替换 / 不计数）。
- 🔴 不用 pytest（本仓无 pytest）⇒ 自带断言 + 退出码。

运行：`.venv/Scripts/python.exe results/app/test_app130_cp_selfcheck.py`
"""
from __future__ import annotations

import os
import sys
import tempfile
import collections.abc

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

import tts_engine  # noqa: E402

_RESULTS = []


def check(name, cond, detail=''):
    _RESULTS.append((name, bool(cond), detail))
    print('%s %s%s' % ('PASS' if cond else 'FAIL', name,
                       ('  — ' + detail) if detail else ''))
    return bool(cond)


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴 复现 **OV 2026.4.1 的真实返回形态**（补丁④⑤ 的根因，必须有回归用例）
#
# `CompiledModel.__call__` 返回的是 `openvino.utils.data_helpers.wrappers.OVDict`：
#   · **不是 dict**（是 `collections.abc.Mapping`）⇒ `isinstance(out, dict)` 为 False；
#   · `.items()` 的**键是 ConstOutput 对象**（不是字符串名）；
#   · 值是 `ConstOutput`（取 `.data` 才是 numpy 数组）；
#   · `ConstOutput.get_names()` ⇒ **set**（`{'hidden_states'}`）；
#   · `ConstOutput.node.get_names()` 在**动态形状**上抛 RuntimeError。
#
# ⇒ 判据若用 `isinstance(out, dict)` / `str(key)` / `np.asarray(out)`，
#   就会拿到 **object 数组** ⇒ 余弦恒 0 ⇒ **恒判失败（假 FAIL）**，
#   且 NaN 守卫**永远不触发**。
# ══════════════════════════════════════════════════════════════════════
class FakeConstOutput:
    """模拟 `ConstOutput`（有 `.data` 与 `.get_names()`）。"""

    def __init__(self, arr, names):
        self.data = np.asarray(arr)
        self._names = set(names)

    def get_names(self):
        return self._names


class FakeOVDict(collections.abc.Mapping):
    """模拟 `OVDict`：**不是 dict**，键是 ConstOutput，值是 ConstOutput。"""

    def __init__(self, d):
        self._d = dict(d)

    def __getitem__(self, k):
        return self._d[k]

    def __iter__(self):
        return iter(self._d)

    def __len__(self):
        return len(self._d)

    def items(self):
        return self._d.items()

    def keys(self):
        return self._d.keys()

    def values(self):
        return self._d.values()


def as_ovdict(d):
    """把 {名字: ndarray} 变成 OV 的返回形态（键/值都包一层 ConstOutput）。"""
    return FakeOVDict({FakeConstOutput(v, {k}): v for k, v in d.items()})


# ══════════════════════════════════════════════════════════════════════
# 假的 compiled model
# ══════════════════════════════════════════════════════════════════════
class FakeCM:
    """假的 compiled model。

    mode:
      - `'good'`    正常：输出 = 输入的确定性映射（CPU / NPU 一致 ⇒ 余弦 1.0）
      - `'nan'`     输出含 NaN
      - `'negate'`  输出方向相反（余弦 = −1 ⇒ < 0.99）
    """

    def __init__(self, mode='good'):
        self.mode = mode
        self.calls = 0

    def __call__(self, inputs):
        self.calls += 1
        x = np.asarray(inputs['inputs_embeds'], dtype=np.float64)
        base = x * 3.0 + 0.5
        if self.mode == 'negate':
            base = -base
        hidden = base.astype(np.float32)
        pk = np.repeat(hidden[:, :, None, None, :], 8, axis=3)
        pv = pk + 0.25
        out = {'hidden_states': hidden, 'present_keys': pk, 'present_values': pv}
        if self.mode == 'nan':
            out['hidden_states'] = hidden.copy()
            out['hidden_states'].reshape(-1)[0] = np.nan
        return out

    def get_property(self, key):
        return ['CPU']


class FakeOVModel:
    def __init__(self):
        self.shape = None

    def reshape(self, shape):
        self.shape = dict(shape)
        return self


class FakeCore:
    def __init__(self, npu_mode='good'):
        self.npu_mode = npu_mode
        self.compiled = []

    def set_property(self, props):
        pass

    def read_model(self, path):
        return FakeOVModel()

    def compile_model(self, model, device):
        self.compiled.append((device, self.npu_mode))
        return FakeCM(self.npu_mode)


class FakeOVModule:
    """假 `openvino` 模块（临时塞进 `sys.modules`）。"""

    def __init__(self, npu_mode):
        self.core = FakeCore(npu_mode)

    def Core(self):
        return self.core


class FakeEngine:
    """假的引擎（只有 `_move_cp_*` 与 `stream()` 需要的部分）。"""

    def __init__(self, model_dir, cp_mode='good'):
        self._model_dir = model_dir
        self.is_npu = True
        self.device = 'NPU'
        self.cp_prefill = FakeCM(cp_mode)
        self.cp_decode = FakeCM(cp_mode)

    def reset_ctx(self):
        pass


class NanEngine:
    """假引擎：`generate_stream` 的**第一步**就触发 code predictor 的 NaN。"""

    def __init__(self, chunk_samples=24000, n_chunks=50, sr=24000):
        self.chunk_samples = chunk_samples
        self.n_chunks = n_chunks
        self.sr = sr
        self.yielded = 0
        self.cp_prefill = tts_engine._CPNaNGuard(FakeCM('nan'), 'cp_prefill')

    def reset_ctx(self):
        pass

    def generate_stream(self, **kwargs):
        for i in range(self.n_chunks):
            if i == 0:
                # 第一步就调 code predictor ⇒ NaN ⇒ CPNaNError
                self.cp_prefill({'inputs_embeds': np.zeros((1, 2, 1024),
                                                           dtype=np.float32)})
            self.yielded += 1
            yield (np.zeros(self.chunk_samples, dtype=np.float32), self.sr)


class LongEngine:
    """假引擎：一路产出很长的音频 ⇒ 应触发阈值保险。"""

    def __init__(self, chunk_samples=24000, n_chunks=50, sr=24000):
        self.chunk_samples = chunk_samples
        self.n_chunks = n_chunks
        self.sr = sr

    def reset_ctx(self):
        pass

    def generate_stream(self, **kwargs):
        for _ in range(self.n_chunks):
            yield (np.zeros(self.chunk_samples, dtype=np.float32), self.sr)


# ══════════════════════════════════════════════════════════════════════
# 用例
# ══════════════════════════════════════════════════════════════════════
def test_selfcheck_pass_path():
    """① 自检「替换」路径：CPU / NPU 输出一致 ⇒ ok=True。"""
    ok, reason, el, detail = tts_engine._cp_selfcheck(
        'cp_prefill', FakeCM('good'), FakeCM('good'))
    check('自检-一致 ⇒ ok=True', ok, 'reason=%r elapsed=%.4f detail=%s'
          % (reason, el, detail))
    check('自检-一致 ⇒ 3 组用例', len(detail) == 3, 'detail=%s' % (detail,))
    check('自检-一致 ⇒ 余弦全为 1.0',
          all(abs(c - 1.0) < 1e-6 for _a, c in detail), 'detail=%s' % (detail,))
    # cp_decode 也要能自检（零 KV + 合法 mask 的输入构造）
    ok2, reason2, el2, d2 = tts_engine._cp_selfcheck(
        'cp_decode', FakeCM('good'), FakeCM('good'))
    check('自检-cp_decode ⇒ ok=True', ok2, 'reason=%r detail=%s' % (reason2, d2))


def test_selfcheck_fail_paths():
    """② 自检「保留 CPU」路径：NaN / 余弦不足 ⇒ ok=False。"""
    ok, reason, el, detail = tts_engine._cp_selfcheck(
        'cp_prefill', FakeCM('good'), FakeCM('nan'))
    check('自检-NaN ⇒ ok=False', not ok, 'reason=%r' % reason)
    check('自检-NaN ⇒ 原因含 NaN', 'NaN' in reason, 'reason=%r' % reason)

    ok2, reason2, _el2, _d2 = tts_engine._cp_selfcheck(
        'cp_prefill', FakeCM('good'), FakeCM('negate'))
    check('自检-余弦不足 ⇒ ok=False', not ok2, 'reason=%r' % reason2)
    check('自检-余弦不足 ⇒ 原因含余弦', '余弦' in reason2, 'reason=%r' % reason2)


def test_move_keeps_cpu_on_fail():
    """③ `_move_cp_prefill_to_npu` 自检失败 ⇒ `eng.cp_prefill` 原样不动。"""
    tmp = tempfile.mkdtemp(prefix='app130_')
    for nm in ('cp_prefill.xml', 'cp_decode.xml'):
        with open(os.path.join(tmp, nm), 'wb') as f:
            f.write(b'<net/>')

    orig_ov = sys.modules.get('openvino')
    orig_cache = tts_engine._cache_dir
    try:
        tts_engine._cache_dir = lambda *a, **k: tmp
        # ---- 反证组①：NPU 版正常 ⇒ 走「替换」路径 ----
        sys.modules['openvino'] = FakeOVModule('good')
        eng = FakeEngine(tmp)
        before = eng.cp_prefill
        r = tts_engine._move_cp_prefill_to_npu(eng, on_log=lambda *a, **k: None)
        check('搬运-自检通过 ⇒ 返回 True', r is True, 'ret=%r' % (r,))
        check('搬运-自检通过 ⇒ eng.cp_prefill 被替换',
              eng.cp_prefill is not before, 'type=%s' % type(eng.cp_prefill).__name__)

        # ---- 反证组②：NPU 版出 NaN ⇒ 走「保留 CPU」路径 ----
        sys.modules['openvino'] = FakeOVModule('nan')
        eng2 = FakeEngine(tmp)
        before2 = eng2.cp_prefill
        r2 = tts_engine._move_cp_prefill_to_npu(eng2, on_log=lambda *a, **k: None)
        check('搬运-自检失败 ⇒ 返回 False', r2 is False, 'ret=%r' % (r2,))
        check('搬运-自检失败 ⇒ eng.cp_prefill 原样不动（保留 CPU）',
              eng2.cp_prefill is before2,
              'type=%s' % type(eng2.cp_prefill).__name__)
        # cp_decode 同理
        sys.modules['openvino'] = FakeOVModule('nan')
        eng3 = FakeEngine(tmp)
        before3 = eng3.cp_decode
        r3 = tts_engine._move_cp_decode_to_npu(eng3, on_log=lambda *a, **k: None)
        check('搬运-cp_decode 自检失败 ⇒ 返回 False', r3 is False, 'ret=%r' % (r3,))
        check('搬运-cp_decode 自检失败 ⇒ eng.cp_decode 原样不动',
              eng3.cp_decode is before3,
              'type=%s' % type(eng3.cp_decode).__name__)
        # 自检报告已记录
        rep = tts_engine.cp_selfcheck_report()
        check('自检报告已记录 cp_prefill',
              'cp_prefill' in rep and rep['cp_prefill']['ok'] is False,
              'report=%s' % rep)
    finally:
        tts_engine._cache_dir = orig_cache
        if orig_ov is None:
            sys.modules.pop('openvino', None)
        else:
            sys.modules['openvino'] = orig_ov


def test_runtime_insurance_nan():
    """④ 运行时保险：假 NaN 输出 ⇒ 1 步内停 ＋ 记 `tts_runaway`。"""
    tts_engine._RUNAWAY_STATS['tts_runaway'] = 0
    tts_engine._RUNAWAY_STATS['tts_runaway_cp_nan'] = 0
    tts_engine._RUNAWAY_STATS['tts_runaway_threshold'] = 0
    eng = NanEngine()
    got = []
    for item in tts_engine.stream(eng, '测试句子', language='Chinese'):
        got.append(item)
    check('运行时保险-NaN ⇒ 1 步内停（产出 ≤1 块）', len(got) <= 1,
          '产出 %d 块' % len(got))
    check('运行时保险-NaN ⇒ tts_runaway 计数 = 1',
          tts_engine.tts_runaway_count() == 1,
          'count=%r' % tts_engine.tts_runaway_count())
    check('运行时保险-NaN ⇒ 归类为 cp_nan',
          tts_engine.tts_runaway_stats().get('tts_runaway_cp_nan') == 1,
          'stats=%s' % tts_engine.tts_runaway_stats())
    check('运行时保险-NaN ⇒ 引擎打了 _cp_nan_hit 标记',
          getattr(eng, '_cp_nan_hit', False) is True)


def test_runtime_insurance_threshold():
    """⑤ 运行时保险：超失控阈值 ⇒ 停 ＋ 记 `tts_runaway`（threshold 类）。"""
    tts_engine._RUNAWAY_STATS['tts_runaway'] = 0
    tts_engine._RUNAWAY_STATS['tts_runaway_cp_nan'] = 0
    tts_engine._RUNAWAY_STATS['tts_runaway_threshold'] = 0
    eng = LongEngine(chunk_samples=24000, n_chunks=50)   # 每块 1 s ⇒ 共 50 s
    got = list(tts_engine.stream(eng, '短句', language='Chinese',
                                  est_sec=1.0))
    thr = tts_engine.runaway_threshold_s(1.0)     # = max(3, 9) = 9 s
    check('运行时保险-阈值 ⇒ 在阈值处停（< 50 块）', len(got) < 50,
          '产出 %d 块，阈值 %.1f s' % (len(got), thr))
    check('运行时保险-阈值 ⇒ tts_runaway 计数 = 1',
          tts_engine.tts_runaway_count() == 1,
          'count=%r' % tts_engine.tts_runaway_count())
    check('运行时保险-阈值 ⇒ 归类为 threshold',
          tts_engine.tts_runaway_stats().get('tts_runaway_threshold') == 1,
          'stats=%s' % tts_engine.tts_runaway_stats())
    # 反证组：没超阈值 ⇒ 不该计数
    tts_engine._RUNAWAY_STATS['tts_runaway'] = 0
    tts_engine._RUNAWAY_STATS['tts_runaway_threshold'] = 0
    eng2 = LongEngine(chunk_samples=24000, n_chunks=3)   # 共 3 s < 9 s
    got2 = list(tts_engine.stream(eng2, '短句', language='Chinese',
                                  est_sec=1.0))
    check('反证-未超阈值 ⇒ 不计数', tts_engine.tts_runaway_count() == 0,
          'count=%r 产出 %d 块' % (tts_engine.tts_runaway_count(), len(got2)))


def test_nan_guard_basics():
    """⑥ `_CPNaNGuard`：NaN ⇒ 抛 `CPNaNError`；正常 ⇒ 透传 ＋ 转发属性。"""
    g = tts_engine._CPNaNGuard(FakeCM('good'), 'cp_prefill')
    out = g({'inputs_embeds': np.zeros((1, 2, 1024), dtype=np.float32)})
    check('守卫-正常输出透传', isinstance(out, dict) and 'hidden_states' in out)
    check('守卫-正常不抛异常', g.n_bad == 0 and g.n_calls == 1)
    check('守卫-转发 get_property', g.get_property('EXECUTION_DEVICES') == ['CPU'])
    g2 = tts_engine._CPNaNGuard(FakeCM('nan'), 'cp_prefill')
    raised = False
    try:
        g2({'inputs_embeds': np.zeros((1, 2, 1024), dtype=np.float32)})
    except tts_engine.CPNaNError:
        raised = True
    check('守卫-NaN ⇒ 抛 CPNaNError', raised, 'n_bad=%r' % g2.n_bad)


def test_ovdict_shape():
    """⑦ 🔴 **OV 返回形态**（OVDict，不是 dict）下的判据正确性。

    回归背景：11-24 10:36 A 机上自检报「余弦 0.0000」⇒ 根因是判据把
    `OVDict` 当 dict ⇒ `np.asarray(OVDict)` 得到 object 数组 ⇒ 恒不相等。
    ⇒ 这组用例必须保证：**OVDict 形态下自检能通过、NaN 能被抓到**。
    """
    good = {'hidden_states': np.ones((1, 2, 4), dtype=np.float32),
            'present_keys': np.full((2, 1, 1, 2, 4), 0.5, dtype=np.float32)}
    ok, reason, _el, detail = tts_engine._cp_selfcheck(
        'cp_prefill', FakeCM('good'), FakeCM('good'))
    check('OVDict-自检（dict 形态）⇒ ok=True', ok, 'reason=%r' % reason)

    # 直接比两个 OVDict
    cos, desc = tts_engine._cp_compare_outputs(as_ovdict(good),
                                                as_ovdict(good))
    check('OVDict-逐键比较 ⇒ 余弦 ≈ 1.0', abs(cos - 1.0) < 1e-6,
          'cos=%r desc=%r' % (cos, desc))
    check('OVDict-逐键比较 ⇒ 无报错', desc == '', 'desc=%r' % desc)

    # NaN 在 OVDict 里必须被抓到
    bad = {'hidden_states': np.array([[[np.nan, 1.0, 2.0, 3.0]]],
                                     dtype=np.float32)}
    r = tts_engine._find_nonfinite(as_ovdict(bad))
    check('OVDict-NaN ⇒ _find_nonfinite 抓得到', bool(r) and 'NaN' in r,
          'r=%r' % r)
    r2 = tts_engine._find_nonfinite(as_ovdict(good))
    check('OVDict-正常 ⇒ _find_nonfinite 返回 None', r2 is None, 'r=%r' % r2)

    # 守卫：模型返回 OVDict 且含 NaN ⇒ 必须抛 CPNaNError
    class OvNaNModel:
        def __call__(self, inputs):
            return as_ovdict(bad)

    g = tts_engine._CPNaNGuard(OvNaNModel(), 'cp_prefill')
    raised = False
    try:
        g({'inputs_embeds': np.zeros((1, 2, 4), dtype=np.float32)})
    except tts_engine.CPNaNError:
        raised = True
    check('OVDict-守卫抓到 NaN ⇒ 抛 CPNaNError', raised)

    # 反证：OVDict 但**没有 NaN** ⇒ 守卫不得误报
    class OvGoodModel:
        def __call__(self, inputs):
            return as_ovdict(good)

    g2 = tts_engine._CPNaNGuard(OvGoodModel(), 'cp_prefill')
    out2 = g2({'inputs_embeds': np.zeros((1, 2, 4), dtype=np.float32)})
    check('OVDict-反证：无 NaN ⇒ 不抛异常', g2.n_bad == 0 and out2 is not None)


def main():
    test_selfcheck_pass_path()
    test_selfcheck_fail_paths()
    test_move_keeps_cpu_on_fail()
    test_runtime_insurance_nan()
    test_runtime_insurance_threshold()
    test_nan_guard_basics()
    test_ovdict_shape()
    n_ok = sum(1 for _n, ok, _d in _RESULTS if ok)
    n_all = len(_RESULTS)
    print('\n==== %d/%d PASS ====' % (n_ok, n_all))
    if n_ok != n_all:
        print('FAILED:')
        for n, ok, d in _RESULTS:
            if not ok:
                print('  - %s  %s' % (n, d))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
