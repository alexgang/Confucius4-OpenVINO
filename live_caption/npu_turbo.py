"""npu_turbo.py —— **NPU turbo 编译属性的统一判定与注入**（APP-139）

## 为什么要有这个模块（APP-139，2026-11-26）

`NPU_TURBO` 这个 OpenVINO NPU 编译属性此前**全库没有任何实现**（grep 命中 0）。
本模块把它做成**一处判定、处处复用**的统一函数，避免 App 与 EXT 各写一份
⇒ 不会出现「App 开了、EXT 没开」或「两边口径不一致」。

## 🔴🔴 关键事实（**必须走编译期 config**，不是 `set_property`）

来自 TTS 模块 2026-11-02 的实测（`hy_bench` 记忆日志 §130）：

| 写法 | 结果 |
|---|---|
| `core.set_property({'NPU_TURBO': 'YES'})`（全局） | ❌ 被 **CPU 插件**拒：`Unsupported property NPU_TURBO by CPU plugin.` |
| `core.set_property(props, "NPU")`（设备级） | ❌ 之后 `build()` 的全局 `INFERENCE_PRECISION_HINT` 被 **AUTO 插件**拒 |
| `core.compile_model(model, "NPU", {**config, **props})` | ✅ **唯一可行解** |

⇒ 本模块的 `turbo_props()` 返回的 dict **只能**作为 `compile_model` 的
**第三参数（编译期 config）** 使用 ⇒ 本模块**不提供** `set_property` 包装。

## 🔴 属性是否存在的探测方式

OV 的 NPU 插件属性表用 `core.get_property("NPU", "SUPPORTED_PROPERTIES")` 查询。
本模块**先探测再注入** ⇒ 设备/驱动不支持该属性时**退回不带 turbo**，
并在日志里**打出实际值**（`NPU_TURBO=True` / `NPU_TURBO=False`），
⇒ 绝不「以为开了其实没开」。

## 三种情况（APP-139 要求单测覆盖）

1. **默认开**：没设 `LIVECAP_NPU_TURBO` ⇒ 尝试开；
2. **环境变量关闭**：`LIVECAP_NPU_TURBO=0` ⇒ 明确关（且日志打实际值 False）；
3. **设备不支持时退回**：NPU 不在可用设备里、或 `SUPPORTED_PROPERTIES` 里
   没有 `NPU_TURBO` ⇒ 退回**不带** turbo，并说明原因。

## ⚠️ 关于「turbo 到底有没有用」的既有结论（**不在本模块的职责内**）

TTS 模块 2026-11-02 的 ABBA 实测结论是「**turbo 与 latency 两个 NPU 编译开关
都没带来 ≥10% 的 RTF 收益**」⇒ **默认开**是用户/APP-139 决定的**产品口径**，
**不是**本模块测出来的性能结论 ⇒ 本模块只负责「按口径注入并如实打日志」。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

#: NPU turbo 属性的名字（OpenVINO NPU 插件的编译属性）。
NPU_TURBO_PROP = 'NPU_TURBO'

#: 打开时注入的值（OV 文档的写法是字符串 'YES'）。
NPU_TURBO_ON = 'YES'

#: 环境变量名（`0` / `false` / `no` / `off` ⇒ 关闭；其它 ⇒ 默认开）。
ENV_NPU_TURBO = 'LIVECAP_NPU_TURBO'

_FALSE_VALUES = {'0', 'false', 'no', 'off', 'disable', 'disabled'}


def turbo_requested() -> bool:
    """用户/环境是否**要求**开 turbo（只看环境变量，不看设备）。

    * 未设置 ⇒ **True**（APP-139：默认开）；
    * 值为 `0`/`false`/`no`/`off`/`disable` ⇒ **False**（明确关）；
    * 其它值 ⇒ **True**（不认识的取值按"默认"处理，并记在日志里）。
    """
    raw = os.environ.get(ENV_NPU_TURBO, '').strip().lower()
    if raw == '':
        return True
    return raw not in _FALSE_VALUES


def _npu_supported_props(core: Any) -> Optional[List[str]]:
    """取 NPU 插件支持的属性表；拿不到 ⇒ 返回 None（⇒ 视为"探测失败"）。"""
    try:
        props = core.get_property('NPU', 'SUPPORTED_PROPERTIES')
    except Exception:
        return None
    try:
        return [str(p) for p in props]
    except Exception:
        return None


def _available_devices(core: Any) -> List[str]:
    """取可用设备列表。

    🔴 **OV 的 `core.available_devices` 是「属性」，不是方法** ⇒
    直接 `core.available_devices()` 会抛 `TypeError: 'list' object is not callable`
    （本模块第一版就踩了这个坑，单测当场抓到）⇒ 这里**属性/方法两种形态都兼容**。
    """
    devs = getattr(core, 'available_devices', None)
    if callable(devs):
        devs = devs()
    if devs is None:
        raise RuntimeError('core 没有 available_devices')
    return [str(d) for d in devs]


def resolve_npu_turbo(core: Any = None,
                      device: str = 'NPU',
                      enabled: Optional[bool] = None,
                      ) -> Tuple[Dict[str, str], bool, str]:
    """判定 turbo 是否可用，并返回**应当注入的编译期属性**。

    Returns
    -------
    (props, actual, reason)
        * ``props`` —— 要并进 `compile_model` 第三参数（编译期 config）的属性；
          **不可用时是空 dict**（⇒ 调用方照常编译，只是不带 turbo）。
        * ``actual`` —— **实际**是否开了 turbo（打进日志的那个值）。
        * ``reason`` —— 判定理由（中文，可直接进日志）。
    """
    want = turbo_requested() if enabled is None else bool(enabled)

    if not want:
        return {}, False, '环境变量 %s 明确关闭' % ENV_NPU_TURBO

    # 设备级探测：先问 NPU 在不在，再问它支持不支持这个属性
    if core is None:
        return {}, False, '未提供 ov.Core（无法探测）'

    try:
        devs = _available_devices(core)
    except Exception as e:
        return {}, False, '读取 available_devices 失败（%s）' % type(e).__name__

    npu_names = [d for d in devs if str(d).upper().startswith('NPU')]
    if not npu_names:
        return {}, False, '本机无 NPU 设备（可用设备：%s）' % ', '.join(devs)

    supported = _npu_supported_props(core)
    if supported is None:
        # 探测失败 ⇒ **fail-closed**：不注入（避免"以为开了其实没开"）
        return {}, False, '读不到 NPU 的 SUPPORTED_PROPERTIES（探测失败 ⇒ 不注入）'
    if NPU_TURBO_PROP not in supported:
        return {}, False, ('本机 NPU 插件不支持 %s（%d 个属性里没有）'
                           % (NPU_TURBO_PROP, len(supported)))

    return {NPU_TURBO_PROP: NPU_TURBO_ON}, True, '已开启（%s=%s）' % (NPU_TURBO_PROP, NPU_TURBO_ON)


def turbo_props(core: Any = None,
                device: str = 'NPU',
                base: Optional[Dict[str, str]] = None,
                enabled: Optional[bool] = None,
                on_log=None) -> Dict[str, str]:
    """拿「基础编译属性 + turbo」的**合并**结果，并把**实际值**打进日志。

    ⚠️ **只能**用作 `core.compile_model(model, device, props)` 的第三参数
    ⇒ **不要**拿去 `core.set_property()`（会被 CPU/AUTO 插件拒，见模块头）。

    Parameters
    ----------
    base : dict | None
        调用方原有的编译期属性（如 `CACHE_DIR` / `INFERENCE_PRECISION_HINT`）。
    core : ov.Core | None
        用于探测设备与属性表；None ⇒ 不注入 turbo。
    on_log : callable | None
        日志回调（单参数 str）；没给就不打日志。
    """
    props: Dict[str, str] = dict(base or {})
    turbo, actual, reason = resolve_npu_turbo(core=core, device=device, enabled=enabled)
    props.update(turbo)
    if on_log is not None:
        on_log('[npu_turbo] NPU_TURBO=%s（%s）' % (actual, reason))
    return props


def turbo_state(core: Any = None, device: str = 'NPU',
                enabled: Optional[bool] = None) -> Dict[str, Any]:
    """只判定、不改任何东西 —— 给状态报告 / 单测用。"""
    turbo, actual, reason = resolve_npu_turbo(core=core, device=device, enabled=enabled)
    return {
        'requested': turbo_requested() if enabled is None else bool(enabled),
        'actual': actual,
        'reason': reason,
        'props': turbo,
    }
