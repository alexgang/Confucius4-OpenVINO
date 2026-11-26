#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app139_npu_turbo_test.py —— **APP-139**：NPU turbo 统一函数的单测。

## 覆盖三种情况（APP-139 明文要求）

1. **默认开**：没设 `LIVECAP_NPU_TURBO` ⇒ 判定为「要开」；
2. **环境变量关闭**：`LIVECAP_NPU_TURBO=0` ⇒ 明确关；
3. **设备不支持时退回**：NPU 不在可用设备里、或 `SUPPORTED_PROPERTIES` 里
   没有 `NPU_TURBO` ⇒ **退回不带 turbo**，并说明原因。

## 🔴 判据必须有鉴别力（否则是"恒真"）

反证组：**把被检对象 `resolve_npu_turbo` 换成一个"永远返回开"的假实现**
⇒ 相关断言**必须 FAIL** ⇒ 说明断言真的在检查行为。

跑法：
    python live_caption/_app139_npu_turbo_test.py
退出码 0 = 全通过。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import npu_turbo as NT

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


class FakeCore:
    """假的 ov.Core：只实现本模块用到的两个接口。

    ⚠️ `available_devices` 提供**两种形态**：
       * `as_property=True`（默认）⇒ **属性**（真实 OV 的形态：`core.available_devices`
         是 list，**不是**方法 ⇒ 第一版实现踩了 `TypeError: not callable`）；
       * `as_property=False` ⇒ 方法（兼容老写法）。
    """

    def __init__(self, devices, supported_props=None, raise_on_props=False,
                 as_property=True):
        self._devices = list(devices)
        self._supported = supported_props
        self._raise = raise_on_props
        self._as_property = as_property
        if as_property:
            self.available_devices = list(self._devices)
        else:
            self.available_devices = self._available_devices

    def _available_devices(self):
        return list(self._devices)

    def get_property(self, device, prop):
        if prop != 'SUPPORTED_PROPERTIES':
            raise RuntimeError('unexpected prop %r' % prop)
        if self._raise:
            raise RuntimeError('probe failed on purpose')
        if self._supported is None:
            raise RuntimeError('no SUPPORTED_PROPERTIES')
        return list(self._supported)


def _with_env(value, fn):
    """临时设置/清除环境变量，跑完恢复。"""
    old = os.environ.get(NT.ENV_NPU_TURBO)
    had = NT.ENV_NPU_TURBO in os.environ
    try:
        if value is None:
            os.environ.pop(NT.ENV_NPU_TURBO, None)
        else:
            os.environ[NT.ENV_NPU_TURBO] = value
        return fn()
    finally:
        if had:
            os.environ[NT.ENV_NPU_TURBO] = old
        else:
            os.environ.pop(NT.ENV_NPU_TURBO, None)


def test_requested_default_on():
    print("\n[1] 情况①：默认开")
    r = _with_env(None, NT.turbo_requested)
    check("未设 %s ⇒ 请求为开（默认开）" % NT.ENV_NPU_TURBO, r is True, f"{r}")
    r = _with_env('1', NT.turbo_requested)
    check("设 '1' ⇒ 请求为开", r is True, f"{r}")
    r = _with_env('YES', NT.turbo_requested)
    check("设 'YES' ⇒ 请求为开（不认识的取值按默认）", r is True, f"{r}")


def test_requested_off():
    print("\n[2] 情况②：环境变量关闭")
    for v in ('0', 'false', 'no', 'off', 'OFF', 'disable'):
        r = _with_env(v, NT.turbo_requested)
        check("设 '%s' ⇒ 请求为关" % v, r is False, f"{r}")


def test_resolve_supported():
    print("\n[3] 情况③：设备支持 ⇒ 注入编译期属性")
    core = FakeCore(['CPU', 'GPU.0', 'NPU'],
                     supported_props=['NPU_TURBO', 'CACHE_DIR', 'PERFORMANCE_HINT'])
    props, actual, reason = _with_env(None, lambda: NT.resolve_npu_turbo(core=core))
    check("实际值 = True", actual is True, f"{actual}")
    check("注入属性 = {NPU_TURBO: YES}",
          props.get(NT.NPU_TURBO_PROP) == NT.NPU_TURBO_ON, f"{props}")
    check("理由里带「已开启」", '已开启' in reason, reason)

    # ★ 真实 OV 的形态是**属性**（`core.available_devices` 是 list，不是方法）
    #   ⇒ 两种形态都必须能工作（第一版实现踩了 `TypeError: not callable`）。
    core_m = FakeCore(['CPU', 'NPU'], supported_props=['NPU_TURBO'], as_property=False)
    props_m, actual_m, reason_m = _with_env(
        None, lambda: NT.resolve_npu_turbo(core=core_m))
    check("★ available_devices 是**方法**形态也能工作（兼容）",
          actual_m is True and props_m.get(NT.NPU_TURBO_PROP) == NT.NPU_TURBO_ON,
          f"actual={actual_m} props={props_m}")


def test_resolve_no_npu_device():
    print("\n[4] 情况③：设备不支持 ⇒ 退回不带 turbo")
    core = FakeCore(['CPU', 'GPU.0'], supported_props=['NPU_TURBO'])
    props, actual, reason = _with_env(None, lambda: NT.resolve_npu_turbo(core=core))
    check("实际值 = False（没开）", actual is False, f"{actual}")
    check("**不注入**任何 turbo 属性", NT.NPU_TURBO_PROP not in props, f"{props}")
    check("理由里带「无 NPU 设备」", '无 NPU' in reason, reason)


def test_resolve_prop_not_supported():
    print("\n[5] 情况③：NPU 在，但属性表里没有 NPU_TURBO ⇒ 退回")
    core = FakeCore(['CPU', 'NPU'], supported_props=['CACHE_DIR', 'PERFORMANCE_HINT'])
    props, actual, reason = _with_env(None, lambda: NT.resolve_npu_turbo(core=core))
    check("实际值 = False（没开）", actual is False, f"{actual}")
    check("**不注入**任何 turbo 属性", NT.NPU_TURBO_PROP not in props, f"{props}")
    check("理由里带「不支持」", '不支持' in reason, reason)


def test_probe_failure_is_fail_closed():
    print("\n[6] 探测失败 ⇒ fail-closed（不注入）")
    core = FakeCore(['CPU', 'NPU'], raise_on_props=True)
    props, actual, reason = _with_env(None, lambda: NT.resolve_npu_turbo(core=core))
    check("实际值 = False（不冒险注入）", actual is False, f"{actual}")
    check("**不注入**任何 turbo 属性", NT.NPU_TURBO_PROP not in props, f"{props}")
    check("理由里带「探测失败」", '探测失败' in reason, reason)


def test_env_off_overrides_supported_device():
    print("\n[7] 环境变量关闭时，即便设备支持也不注入")
    core = FakeCore(['CPU', 'NPU'],
                     supported_props=['NPU_TURBO', 'CACHE_DIR'])
    props, actual, reason = _with_env('0', lambda: NT.resolve_npu_turbo(core=core))
    check("实际值 = False", actual is False, f"{actual}")
    check("**不注入**任何 turbo 属性", NT.NPU_TURBO_PROP not in props, f"{props}")
    check("理由里带「明确关闭」", '明确关闭' in reason, reason)


def test_turbo_props_merge_and_log():
    print("\n[8] turbo_props：与基础属性合并，且日志打实际值")
    core = FakeCore(['CPU', 'NPU'], supported_props=['NPU_TURBO', 'CACHE_DIR'])
    logs = []
    base = {'CACHE_DIR': r'C:\tmp\cache', 'INFERENCE_PRECISION_HINT': 'f16'}
    out = _with_env(None, lambda: NT.turbo_props(core=core, base=base,
                                                  on_log=logs.append))
    check("基础属性都还在", out.get('CACHE_DIR') == base['CACHE_DIR']
          and out.get('INFERENCE_PRECISION_HINT') == base['INFERENCE_PRECISION_HINT'],
          f"{out}")
    check("turbo 属性已并入", out.get(NT.NPU_TURBO_PROP) == NT.NPU_TURBO_ON, f"{out}")
    check("**日志打了实际值** True", len(logs) == 1 and 'NPU_TURBO=True' in logs[0],
          f"{logs}")
    check("**没有**改动调用方传入的 base 字典",
          NT.NPU_TURBO_PROP not in base, f"{base}")

    # 关的情况：日志必须打 False
    logs2 = []
    core2 = FakeCore(['CPU', 'NPU'], supported_props=['NPU_TURBO'])
    out2 = _with_env('0', lambda: NT.turbo_props(core=core2, base=base,
                                                  on_log=logs2.append))
    check("关闭时**不注入** turbo", NT.NPU_TURBO_PROP not in out2, f"{out2}")
    check("关闭时日志打实际值 False",
          len(logs2) == 1 and 'NPU_TURBO=False' in logs2[0], f"{logs2}")


def test_turbo_state():
    print("\n[9] turbo_state：只判定不改状态")
    core = FakeCore(['CPU', 'NPU'], supported_props=['NPU_TURBO'])
    st = _with_env(None, lambda: NT.turbo_state(core=core))
    check("字段齐全", set(['requested', 'actual', 'reason', 'props']) <= set(st.keys()),
          f"{list(st.keys())}")
    check("requested=True / actual=True",
          st['requested'] is True and st['actual'] is True, f"{st}")


# ══════════════════════════════════════════════════════════════
# 反证组：判据必须有鉴别力
# ══════════════════════════════════════════════════════════════
def test_counterexample():
    print("\n[10] ★ 反证组：把被检对象换成「永远返回开」的假实现 ⇒ 必须 FAIL")
    core = FakeCore(['CPU', 'GPU.0'], supported_props=['NPU_TURBO'])

    # 假实现：无脑返回「开」
    def fake_resolve(core=None, device='NPU', enabled=None):
        return {NT.NPU_TURBO_PROP: NT.NPU_TURBO_ON}, True, 'fake: 永远开'

    real = NT.resolve_npu_turbo
    try:
        NT.resolve_npu_turbo = fake_resolve
        props, actual, reason = NT.resolve_npu_turbo(core=core)
        # 断言（与上面 test_resolve_no_npu_device 同样的判据）
        must_fail = (actual is False) and (NT.NPU_TURBO_PROP not in props)
        check("★ 鉴别力：假实现让「无 NPU 设备 ⇒ 不注入」这条判据 FAIL",
              not must_fail,
              f"假实现返回 actual={actual} props={props} ⇒ 原判据被识破")
    finally:
        NT.resolve_npu_turbo = real

    # 反向：真实现必须通过同一条判据
    props, actual, reason = NT.resolve_npu_turbo(core=core)
    check("★ 对照：真实现通过同一条判据",
          (actual is False) and (NT.NPU_TURBO_PROP not in props),
          f"actual={actual} props={props}")


def main() -> int:
    for fn in (test_requested_default_on,
               test_requested_off,
               test_resolve_supported,
               test_resolve_no_npu_device,
               test_resolve_prop_not_supported,
               test_probe_failure_is_fail_closed,
               test_env_off_overrides_supported_device,
               test_turbo_props_merge_and_log,
               test_turbo_state,
               test_counterexample):
        fn()
    n_pass = sum(1 for _n, ok in RESULTS if ok)
    n_fail = len(RESULTS) - n_pass
    print("\n" + "=" * 68)
    print(f"结果：{n_pass} PASS / {n_fail} FAIL / 共 {len(RESULTS)}")
    print("=" * 68)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
