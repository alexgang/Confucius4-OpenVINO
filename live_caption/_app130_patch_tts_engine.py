#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-130：给 `tts_engine.py` 打**自检兜底 + 运行时保险**的定点补丁。

## 背景（reviewer 在 B 机 Meteor Lake 一代 NPU 上的对照实验）

| 臂 | 结果 |
|---|---|
| 产品 NPU 引擎原样 | 每句生成到 492 帧 = 39.36 s（GPU.0 引擎同句 5.84 s） |
| 声码器同一组码 NPU / GPU.0 / CPU 解码 | 精度差正常 ⇒ **不是声码器** |
| talker 全改 CPU / NPU 显式 f16 | 仍 492 帧 ⇒ **不是 talker** |
| 说话人向量换 GPU.0 算的 | 仍 492 帧 ⇒ **不是 speaker encoder** |
| **cp_prefill / cp_decode 改到 CPU** | **5.44 s / 68 帧，正常收尾** |
| 同一个 cp_prefill 输入在 NPU vs CPU | **比较结果为 NaN（输出含 NaN）** |

⇒ 根因：`_move_cp_prefill_to_npu` / `_move_cp_decode_to_npu` 把 code predictor
  编到 NPU 后，在**这类机型/驱动上输出 NaN** ⇒ talker 每步拿到的 15 组码被污染
  ⇒ **永远走不到 EOS** ⇒ 一句拖到帧上限（39 s 乱说）。
  A 机（Panther Lake）NPU 正常 ⇒ 这是**机型/驱动相关**的数值问题。

## 本补丁做的四件事（与 APP-130 §要做的 1–2 一一对应）

1. **自检兜底**：NPU 版编译成功后、替换 `eng.cp_*` **之前**，用固定种子造
   2–3 组输入在 NPU 版与现有 CPU 版上各跑一遍；任一输出含 NaN/Inf、
   或与 CPU 的余弦 < 0.99 ⇒ **不替换、保留 CPU** ＋ 记日志。
2. **运行时保险**：给 code predictor 套 `_CPNaNGuard` ⇒ 输出 NaN/Inf 时
   **立刻抛 `CPNaNError`** ⇒ 生成循环当场停止本句 ＋ 记 `tts_runaway` 计数。
3. **失控阈值保险**：`stream()` 外层加 `_guarded_stream` ⇒
   已收音频秒数 > `runaway_threshold_s(estimate_sec(text, lang))` ⇒ 停句。
4. **计数与自检报告**：`tts_runaway_count()` / `tts_runaway_stats()` /
   `cp_selfcheck_report()`（供 STATUS / 邮件报数字）。

## 纪律（定点写入三件套）

- 备份 → **写前**在内存新文本上跑真不变量 ＋ **还原式复核**（改回须逐字节同）
- 临时文件 → `os.replace` ⇒ **写后另起脚本复核** ＋ `git diff --numstat`
- 只改 `live_caption/tts_engine.py`（开发树）⇒ **客户包本轮不动**
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, 'tts_engine.py')


def crlf(s: str) -> str:
    """把 LF 文本转成 CRLF（目标文件是 CRLF ⇒ 补丁串必须同风格）。"""
    return s.replace('\r\n', '\n').replace('\n', '\r\n')


# ══════════════════════════════════════════════════════════════════════
# ① 新增块：插在 `_cp_decode_ir_path` 之后
# ══════════════════════════════════════════════════════════════════════
BLOCK_APP130 = '''
# ══════════════════════════════════════════════════════════════════════
# 🔴🔴🔳 APP-130：**code predictor 的 NPU 自检兜底 + 运行时保险**
# ══════════════════════════════════════════════════════════════════════
#
# ## 背景（reviewer 在 B 机 Meteor Lake 一代 NPU 上做的 4 组对照实验）
#
# | 臂 | 结果 |
# |---|---|
# | 产品 NPU 引擎原样 | 每句生成到 492 帧 = 39.36 s（GPU.0 引擎同句 5.84 s） |
# | 声码器同一组码 NPU / GPU.0 / CPU 解码 | 精度差正常 ⇒ **不是声码器** |
# | talker 全改 CPU / NPU 显式 f16 | 仍 492 帧 ⇒ **不是 talker** |
# | 说话人向量换 GPU.0 算的 | 仍 492 帧 ⇒ **不是 speaker encoder** |
# | **cp_prefill / cp_decode 改到 CPU** | **5.44 s / 68 帧，正常收尾** |
# | 同一个 cp_prefill 输入在 NPU vs CPU | **比较结果为 NaN（输出含 NaN）** |
#
# ⇒ 根因：`_move_cp_prefill_to_npu` / `_move_cp_decode_to_npu` 把 code predictor
#   编到 NPU 后，在**这类机型/驱动上输出 NaN** ⇒ talker 每步拿到的 15 组码
#   被污染 ⇒ **永远走不到 EOS** ⇒ 一句拖到帧上限（39 s 乱说）。
#   A 机（Panther Lake）NPU 正常 ⇒ 这是**机型/驱动相关**的数值问题，
#   代码里**原本没有任何兜底**。
#
# ## 本模块的两道保险
#
# 1. **自检兜底**（启动时）：NPU 版编译成功后、替换 `eng.cp_*` **之前**，
#    用固定种子造 2–3 组输入，在 NPU 版与**现有 CPU 版**上各跑一遍；
#    任一输出含 NaN/Inf、或与 CPU 的余弦 < 0.99 ⇒ **不替换、保留 CPU**。
# 2. **运行时保险**（生成时）：code predictor 输出 NaN/Inf ⇒ **本句立刻停**
#    并记 `tts_runaway` 计数（不再一路生成到帧上限）。
#
# 🔴 **口径写清楚**（reviewer 要求「阈值沿用 tts_engine 现有的估计函数，
#    写清口径」）：
#   - 失控阈值 = `runaway_threshold_s(estimate_sec(text, lang))`
#     = `max(3×估计秒数, 估计秒数 + 8 s)`（`RUNAWAY_FACTOR=3.0` /
#     `RUNAWAY_EXTRA_S=8.0`，见本模块 `runaway_threshold_s`）。
#   - 估计秒数 = `estimate_sec(text, lang)` = **非空白字符数 × 每字秒数
#     + 尾部常数**（`_SEC_PER_CHAR` / `_LANG_TAIL_S`）。
#   - **NaN 判据与阈值无关**：只要 code predictor 输出含 NaN/Inf ⇒ 立刻停。

#: 自检随机种子（固定 ⇒ 可复现；reviewer 要求「用固定种子构造输入」）
CP_SELFCHECK_SEED = 20261124

#: 自检的三组输入幅度（reviewer 明文：0.02 / 0.1 / 1.0）
CP_SELFCHECK_AMPS = (0.02, 0.1, 1.0)

#: 自检判据：与 CPU 的余弦下限（reviewer 明文：< 0.99 ⇒ 不替换）
CP_SELFCHECK_COS_MIN = 0.99

#: code predictor 的形状常量（与 babelvox `pipeline.py` L110-113 一致：
#: CP_NUM_LAYERS=5 / CP_NUM_KV_HEADS=8 / CP_HEAD_DIM=128 / CP_MAX_KV_LEN=20）
CP_NUM_LAYERS = 5
CP_NUM_KV_HEADS = 8
CP_MAX_KV_LEN = 20
CP_HEAD_DIM = 128


class CPNaNError(RuntimeError):
    """🔴🔴🔳 APP-130：code predictor 输出 NaN/Inf ⇒ 本句立刻停。"""


def _find_nonfinite(out):
    """在 OV 输出（dict / ndarray）里找 NaN / Inf。返回描述串或 None。"""
    try:
        import numpy as np
    except Exception:
        return None

    def _one(arr):
        try:
            a = np.asarray(arr)
        except Exception:
            return None
        if a.dtype.kind not in 'fc':
            return None
        if not bool(np.all(np.isfinite(a))):
            return 'NaN' if bool(np.isnan(a).any()) else 'Inf'
        return None

    if isinstance(out, dict):
        for k in sorted(out.keys(), key=str):
            r = _one(out[k])
            if r:
                return '%s 含 %s' % (k, r)
        return None
    r = _one(out)
    return ('含 %s' % r) if r else None


def _cosine(a, b) -> float:
    """两组数组的余弦（展平）。任一方范数≈0 ⇒ 1.0（两者都≈0）/ 0.0（只有一方）。"""
    try:
        import numpy as np
    except Exception:
        return 0.0
    try:
        x = np.asarray(a, dtype=np.float64).reshape(-1)
        y = np.asarray(b, dtype=np.float64).reshape(-1)
    except Exception:
        return 0.0
    if x.size != y.size or x.size == 0:
        return 0.0
    nx = float(np.linalg.norm(x))
    ny = float(np.linalg.norm(y))
    if nx < 1e-12 and ny < 1e-12:
        return 1.0
    if nx < 1e-12 or ny < 1e-12:
        return 0.0
    return float(np.dot(x, y) / (nx * ny))


def _cp_selfcheck_inputs(which: str):
    """构造 code predictor 自检输入（**固定种子** ⇒ 可复现）。

    - `cp_prefill`：运行时输入**恒为** `(1, 2, 1024)`
      （babelvox `pipeline.py`：`cp_input = np.concatenate([hidden, code_0_embed], axis=1)`
      ⇒ `hidden`(1,1,1024) + `code_0_embed`(1,1,1024)）⇒ 按此造。
    - `cp_decode`：按 `CP_DECODE_NPU_SHAPE` 造**零 KV + 合法 attention_mask**
      （mask 前 `pos+1` 位为 0、其余为 float32 min ⇒ 与 babelvox
      `_run_cp_decode` L570-572 同语义）。

    返回 `[(amp, inputs_dict), ...]`。
    """
    import numpy as np
    rng = np.random.default_rng(CP_SELFCHECK_SEED)
    cases = []
    if which == 'cp_prefill':
        for amp in CP_SELFCHECK_AMPS:
            x = (rng.standard_normal((1, 2, 1024)) * float(amp)).astype(np.float32)
            cases.append((amp, {'inputs_embeds': x}))
    else:
        for amp in CP_SELFCHECK_AMPS:
            x = (rng.standard_normal((1, 1, 1024)) * float(amp)).astype(np.float32)
            mask = np.full((1, 1, 1, CP_MAX_KV_LEN),
                           np.finfo(np.float32).min, dtype=np.float32)
            mask[:, :, :, :1] = 0.0
            kv_k = np.zeros((CP_NUM_LAYERS, 1, CP_NUM_KV_HEADS,
                             CP_MAX_KV_LEN, CP_HEAD_DIM), dtype=np.float32)
            cases.append((amp, {
                'inputs_embeds': x,
                'cache_position': np.array([0], dtype=np.int64),
                'attention_mask': mask,
                'past_keys': kv_k,
                'past_values': kv_k.copy(),
            }))
    return cases


def _cp_compare_outputs(cpu_out, npu_out):
    """逐键比较 CPU / NPU 输出。返回 `(min_cos, bad_desc)`。"""
    if isinstance(cpu_out, dict) and isinstance(npu_out, dict):
        keys = [k for k in cpu_out.keys() if k in npu_out]
        if not keys:
            return 0.0, '输出键不匹配（CPU %s / NPU %s）' % (
                sorted(map(str, cpu_out.keys())),
                sorted(map(str, npu_out.keys())))
        min_cos = 1.0
        desc = ''
        for k in sorted(keys, key=str):
            c = _cosine(cpu_out[k], npu_out[k])
            if c < min_cos:
                min_cos = c
            if c < CP_SELFCHECK_COS_MIN and not desc:
                desc = '%s 与 CPU 余弦 %.4f < %.2f' % (
                    k, c, CP_SELFCHECK_COS_MIN)
        return min_cos, desc
    c = _cosine(cpu_out, npu_out)
    if c < CP_SELFCHECK_COS_MIN:
        return c, '与 CPU 余弦 %.4f < %.2f' % (c, CP_SELFCHECK_COS_MIN)
    return c, ''


def _cp_selfcheck(which: str, cpu_cm, npu_cm, on_log=print):
    """🔴🔴🔳 APP-130①：**NPU 自检**（编译成功后、替换 `eng.cp_*` 之前）。

    返回 `(ok, reason, elapsed_s, detail)`：
    - `ok=False` ⇒ **不替换 `eng.cp_*`，保留 CPU**（机型/驱动相关 NaN 不进生产）。
    - `detail` = 逐用例的 `(amp, min_cos)` 列表（供 STATUS / 邮件报数字）。
    """
    import time as _t
    t0 = _t.perf_counter()
    detail = []
    if cpu_cm is None:
        return False, '没有可比的 CPU 版（cpu_cm is None）', 0.0, detail
    try:
        cases = _cp_selfcheck_inputs(which)
    except Exception as e:
        return (False, '自检输入构造失败：%s: %s' % (type(e).__name__, e),
                0.0, detail)
    for amp, inp in cases:
        try:
            npu_out = npu_cm(inp)
        except Exception as e:
            return (False, '用例 amp=%s NPU 推理异常：%s: %s'
                    % (amp, type(e).__name__, e),
                    _t.perf_counter() - t0, detail)
        bad = _find_nonfinite(npu_out)
        if bad:
            return (False, '用例 amp=%s NPU 输出 %s' % (amp, bad),
                    _t.perf_counter() - t0, detail)
        try:
            cpu_out = cpu_cm(inp)
        except Exception as e:
            return (False, '用例 amp=%s CPU 推理异常：%s: %s'
                    % (amp, type(e).__name__, e),
                    _t.perf_counter() - t0, detail)
        badc = _find_nonfinite(cpu_out)
        if badc:
            return (False, '用例 amp=%s **CPU** 输出 %s（基线自身异常）'
                    % (amp, badc), _t.perf_counter() - t0, detail)
        min_cos, desc = _cp_compare_outputs(cpu_out, npu_out)
        detail.append((amp, round(min_cos, 6)))
        if desc:
            return (False, '用例 amp=%s %s' % (amp, desc),
                    _t.perf_counter() - t0, detail)
    return True, '', _t.perf_counter() - t0, detail


#: 🔴🔴🔳 APP-130②：**自检报告**（最近一次结果；供 STATUS / 遥测取）
_CP_SELFCHECK_REPORT: dict = {}


def cp_selfcheck_report() -> dict:
    """取 code predictor 自检报告（dict 的副本）。

    每项形如：`{'which': 'cp_prefill', 'ok': bool, 'reason': str,
    'elapsed_s': float, 'detail': [(amp, cos), ...]}`。
    """
    return {k: (dict(v) if isinstance(v, dict) else v)
            for k, v in _CP_SELFCHECK_REPORT.items()}


def _record_selfcheck(which: str, ok: bool, reason: str,
                      elapsed_s: float, detail) -> None:
    _CP_SELFCHECK_REPORT[which] = {
        'which': which, 'ok': bool(ok), 'reason': str(reason or ''),
        'elapsed_s': round(float(elapsed_s), 4),
        'detail': [(float(a), float(c)) for a, c in (detail or [])],
    }


class _CPNaNGuard:
    """🔴🔴🔳 APP-130②：包裹 code predictor 的 compiled model。

    输出含 NaN/Inf ⇒ **立刻抛 `CPNaNError`** ⇒ 生成循环当场停止本句
    （不再一路生成到帧上限 ⇒ 不再出现 39 s 乱说）。

    ⚠️ **必须转发 `get_property`** ⇒ `execution_devices()` 靠它取
    `EXECUTION_DEVICES` ⇒ 守卫不能把设备落点搞成「取不到」。
    """

    def __init__(self, inner, name: str):
        self._inner = inner
        self._name = name
        self.n_calls = 0
        self.n_bad = 0
        self.last_reason = None

    def __call__(self, *a, **k):
        out = self._inner(*a, **k)
        self.n_calls += 1
        bad = _find_nonfinite(out)
        if bad:
            self.n_bad += 1
            self.last_reason = bad
            raise CPNaNError('%s 输出 %s（APP-130 运行时保险）'
                             % (self._name, bad))
        return out

    def get_property(self, key):
        return self._inner.get_property(key)

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        inner = self.__dict__.get('_inner')
        if inner is None:
            raise AttributeError(name)
        return getattr(inner, name)


def _install_cp_nan_guard(eng, on_log=print) -> int:
    """给 `eng.cp_prefill` / `eng.cp_decode` 套 NaN/Inf 守卫。返回套上的个数。"""
    n = 0
    for name in ('cp_prefill', 'cp_decode'):
        cur = getattr(eng, name, None)
        if cur is None or isinstance(cur, _CPNaNGuard):
            continue
        try:
            setattr(eng, name, _CPNaNGuard(cur, name))
            n += 1
        except Exception as e:
            on_log('[tts_engine] ⚠️ APP-130：%s 守卫安装失败（%s）'
                   % (name, e))
    return n


#: 🔴🔴🔳 APP-130②：**`tts_runaway` 计数**（模块级；进程内有效）
_RUNAWAY_LOCK = threading.Lock()
_RUNAWAY_STATS = {
    'tts_runaway': 0,
    'tts_runaway_cp_nan': 0,
    'tts_runaway_threshold': 0,
}


def bump_tts_runaway(reason: str = 'threshold') -> int:
    """🔴🔴🔳 APP-130②：记一次 `tts_runaway`（本句因失控被中止）。

    `reason`：`'cp_nan'`（code predictor 出 NaN/Inf）/ `'threshold'`（超失控阈值）。
    返回累计次数。
    """
    with _RUNAWAY_LOCK:
        _RUNAWAY_STATS['tts_runaway'] = int(
            _RUNAWAY_STATS.get('tts_runaway', 0)) + 1
        if reason == 'cp_nan':
            _RUNAWAY_STATS['tts_runaway_cp_nan'] = int(
                _RUNAWAY_STATS.get('tts_runaway_cp_nan', 0)) + 1
        else:
            _RUNAWAY_STATS['tts_runaway_threshold'] = int(
                _RUNAWAY_STATS.get('tts_runaway_threshold', 0)) + 1
        return int(_RUNAWAY_STATS['tts_runaway'])


def tts_runaway_count() -> int:
    """🔴 APP-130②：取 `tts_runaway` 累计次数。"""
    return int(_RUNAWAY_STATS.get('tts_runaway', 0))


def tts_runaway_stats() -> dict:
    """🔴 APP-130②：取 `tts_runaway` 明细（给状态/遥测用）。"""
    return dict(_RUNAWAY_STATS)


def _guarded_stream(gen, eng, text, language, est_sec, on_log=print):
    """🔴🔴🔳 APP-130②：**运行时保险**（生成循环级）。

    两道判据：
    1. **code predictor 输出 NaN/Inf**（`_CPNaNGuard` 抛 `CPNaNError`）
       ⇒ **本句立刻停** ＋ 记 `tts_runaway`（`reason='cp_nan'`）。
    2. **已收音频秒数 > `runaway_threshold_s(estimate_sec(text, lang))`**
       ⇒ 本句立刻停（`reason='threshold'`）。
       口径：`max(3×估计秒数, 估计秒数 + 8 s)`；估计秒数按**非空白字符数**
       × 每字秒数 + 尾部常数（`estimate_sec`）。

    ⚠️ **计数只在这里加一次**：`tts_worker.py` 的 worker 侧第三道闸
    （同阈值）**不再重复计数** ⇒ 一句只记 1 次。
    """
    try:
        thr = runaway_threshold_s(
            est_sec if est_sec is not None else estimate_sec(text, language))
    except Exception:
        thr = None
    got_s = 0.0
    sr = 24000
    try:
        for item in gen:
            try:
                wav, s = item
            except Exception:
                wav, s = item, sr
            try:
                sr = int(s) or sr
            except Exception:
                pass
            try:
                import numpy as np
                n = int(np.asarray(wav).size)
            except Exception:
                n = 0
            got_s += n / float(sr or 24000)
            yield item
            if thr is not None and got_s > thr:
                on_log('[tts_engine] 🔴 APP-130 运行时保险：本句已收 %.1f s > '
                       '阈值 %.1f s ⇒ 停止本句（记 tts_runaway）'
                       % (got_s, thr))
                bump_tts_runaway('threshold')
                break
    except CPNaNError as e:
        on_log('[tts_engine] 🔴 APP-130 运行时保险：%s ⇒ 停止本句（记 tts_runaway）'
               % e)
        bump_tts_runaway('cp_nan')
        try:
            eng._cp_nan_hit = True
            eng._last_end_reason = 'runaway'
        except Exception:
            pass
        return
'''

# ══════════════════════════════════════════════════════════════════════
# ② `_move_cp_prefill_to_npu`：编译成功后、替换 `eng.cp_prefill` 之前自检
# ══════════════════════════════════════════════════════════════════════
OLD_PREFILL = '''
    eng.cp_prefill = cm
    # `cp_on_cpu` 在 babelvox 里**只被写、从不被读**（pipeline L181/L356）
'''

NEW_PREFILL = '''
    # 🔴🔴🔳 APP-130①：**NPU 自检兜底**
    #   编译成功后、**替换 `eng.cp_prefill` 之前** ⇒ 自检不过就**保留 CPU**
    #   （B 机那类 NPU 上 cp_prefill 输出 NaN ⇒ 保留 CPU 即恢复 5.44 s / 68 帧）。
    _cpu_cm = getattr(eng, 'cp_prefill', None)
    _ok, _reason, _elapsed, _detail = _cp_selfcheck(
        'cp_prefill', _cpu_cm, cm, on_log=on_log)
    _record_selfcheck('cp_prefill', _ok, _reason, _elapsed, _detail)
    if not _ok:
        on_log('[tts_engine] cp_prefill: NPU 自检失败（%s）⇒ 留在 CPU'
               % _reason)
        return False
    on_log('[tts_engine] cp_prefill: NPU 自检通过（耗时 %.3f s，用例 %s）'
           % (_elapsed, _detail))

    eng.cp_prefill = cm
    # `cp_on_cpu` 在 babelvox 里**只被写、从不被读**（pipeline L181/L356）
'''

# ══════════════════════════════════════════════════════════════════════
# ③ `_move_cp_decode_to_npu`：同上
# ══════════════════════════════════════════════════════════════════════
OLD_DECODE = '''
    eng.cp_decode = cm
    # `cp_on_cpu` 在 babelvox 里**只被写、从不被读**（pipeline L181/L356）
'''

NEW_DECODE = '''
    # 🔴🔴🔳 APP-130①：**NPU 自检兜底**
    #   编译成功后、**替换 `eng.cp_decode` 之前** ⇒ 自检不过就**保留 CPU**
    _cpu_cm = getattr(eng, 'cp_decode', None)
    _ok, _reason, _elapsed, _detail = _cp_selfcheck(
        'cp_decode', _cpu_cm, cm, on_log=on_log)
    _record_selfcheck('cp_decode', _ok, _reason, _elapsed, _detail)
    if not _ok:
        on_log('[tts_engine] cp_decode: NPU 自检失败（%s）⇒ 留在 CPU'
               % _reason)
        return False
    on_log('[tts_engine] cp_decode: NPU 自检通过（耗时 %.3f s，用例 %s）'
           % (_elapsed, _detail))

    eng.cp_decode = cm
    # `cp_on_cpu` 在 babelvox 里**只被写、从不被读**（pipeline L181/L356）
'''

# ══════════════════════════════════════════════════════════════════════
# ④ `make_engine`：装 NaN 守卫（在 execution_devices 探测**之前**）
# ══════════════════════════════════════════════════════════════════════
OLD_MAKE = '''
    # 🔴🔴 **必须挂 SpeakerLibrary**，否则按名查内置音色会直接抛
'''

NEW_MAKE = '''
    # 🔴🔴🔳 APP-130②：**code predictor 的 NaN/Inf 守卫**
    #   ⚠️ 必须在 `execution_devices()` **之前**装 ⇒ 守卫转发 `get_property`
    #      ⇒ 设备落点仍能测到（cp_* 显示真实落点）。
    try:
        _ng = _install_cp_nan_guard(eng, on_log=on_log)
        if _ng:
            on_log('[tts_engine] 🔴 APP-130：code predictor NaN 守卫已装 %d 个'
                   % _ng)
    except Exception as e:
        on_log('[tts_engine] ⚠️ APP-130：NaN 守卫安装失败（%s）⇒ 不影响主链路'
               % e)

    # 🔴🔴 **必须挂 SpeakerLibrary**，否则按名查内置音色会直接抛
'''

# ══════════════════════════════════════════════════════════════════════
# ⑤ `stream()`：接运行时保险
# ══════════════════════════════════════════════════════════════════════
OLD_STREAM = '''    return eng.generate_stream(**kwargs)
'''

NEW_STREAM = '''    # 🔴🔴🔳 APP-130②：**运行时保险**（生成循环级）
    #   ⇒ code predictor 出 NaN/Inf ⇒ 本句立刻停；已收音频超失控阈值 ⇒ 本句停。
    return _guarded_stream(eng.generate_stream(**kwargs), eng, text,
                            language, est_sec, on_log=on_log)
'''

# ══════════════════════════════════════════════════════════════════════
# ⑥ `import threading`（`_RUNAWAY_LOCK` 需要）
# ══════════════════════════════════════════════════════════════════════
OLD_IMPORT = '''import contextlib
import os
import time
'''

NEW_IMPORT = '''import contextlib
import os
import threading
import time
'''

PATCHES = [
    ('import threading', OLD_IMPORT, NEW_IMPORT),
    ('APP-130 block', '''def _cp_decode_ir_path(eng) -> Optional[str]:
    """定位 cp_decode 的 IR 路径（兼容旧调用方）。"""
    return _cp_ir_path(eng, 'cp_decode')
''', '''def _cp_decode_ir_path(eng) -> Optional[str]:
    """定位 cp_decode 的 IR 路径（兼容旧调用方）。"""
    return _cp_ir_path(eng, 'cp_decode')
''' + BLOCK_APP130),
    ('cp_prefill selfcheck', OLD_PREFILL, NEW_PREFILL),
    ('cp_decode selfcheck', OLD_DECODE, NEW_DECODE),
    ('make_engine guard', OLD_MAKE, NEW_MAKE),
    ('stream guard', OLD_STREAM, NEW_STREAM),
]


def main() -> int:
    if not os.path.isfile(TARGET):
        print('FAIL: 目标文件不存在 %s' % TARGET)
        return 2
    raw = open(TARGET, 'rb').read()
    orig = raw.decode('utf-8')
    if '\r\n' not in orig:
        print('FAIL: 目标文件不是 CRLF ⇒ 停手（避免行尾风格被改）')
        return 2
    backup = os.path.join(tempfile.gettempdir(), 'tts_engine.py.app130.bak')
    shutil.copy2(TARGET, backup)
    print('备份: %s (%d B)' % (backup, len(raw)))

    text = orig
    applied = []
    for name, old, new in PATCHES:
        o = crlf(old)
        n = crlf(new)
        cnt = text.count(o)
        if cnt != 1:
            print('FAIL: 补丁 %r 命中 %d 次（要求恰好 1 次）⇒ 零改动' % (name, cnt))
            return 3
        text = text.replace(o, n, 1)
        applied.append(name)

    # ── 真不变量（写前，在内存新文本上跑）────────────────────────────
    errs = []

    # ① 还原式复核：把每条补丁反向替换回去 ⇒ 必须逐字节还原原文件
    back = text
    for name, old, new in reversed(PATCHES):
        o = crlf(old)
        n = crlf(new)
        if back.count(n) != 1:
            errs.append('还原式复核失败：%r 反向命中 %d 次' % (name, back.count(n)))
            break
        back = back.replace(n, o, 1)
    else:
        if back != orig:
            errs.append('还原式复核失败：反向替换后与原文不逐字节相同')

    # ② 行尾风格不变（全部 CRLF，无孤立 LF / CR）
    if text.count('\n') != text.count('\r\n'):
        errs.append('行尾风格被改：CRLF=%d / LF=%d'
                    % (text.count('\r\n'), text.count('\n')))

    # ③ 旧正文逐字未变：原文件去掉被替换的片段后，必须都是新文件的子串
    for name, old, _new in PATCHES:
        o = crlf(old)
        if o.strip() and o not in orig:
            errs.append('旧正文片段不在原文件里：%r' % name)

    # ④ 关键符号都在
    for sym in ('_cp_selfcheck(', '_CPNaNGuard', 'CPNaNError', 'bump_tts_runaway',
                '_guarded_stream(', 'cp_selfcheck_report(',
                '_install_cp_nan_guard('):
        if sym not in text:
            errs.append('缺关键符号：%s' % sym)

    # ⑤ 编译可解析
    try:
        compile(text, TARGET, 'exec')
    except SyntaxError as e:
        errs.append('语法错误：%s' % e)

    # ⑥ 行数只增不减
    if text.count('\n') < orig.count('\n'):
        errs.append('行数变少（异常）')

    if errs:
        print('自检 FAIL ⇒ 零改动：')
        for e in errs:
            print('  - %s' % e)
        return 4

    # ── 落盘：临时文件 → os.replace ─────────────────────────────────
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TARGET), suffix='.app130.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(text.encode('utf-8'))
        os.replace(tmp, TARGET)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

    print('已打补丁：%s' % '、'.join(applied))
    print('字节：%d → %d（+%d）' % (len(raw), len(text.encode('utf-8')),
                                len(text.encode('utf-8')) - len(raw)))
    print('行数：%d → %d（+%d）'
          % (orig.count('\n'), text.count('\n'),
             text.count('\n') - orig.count('\n')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
