"""thread_limits.py — ★ EXT-011：把 BLAS/OpenMP 的线程数限制为 1

## 为什么需要（EXT-011 明文，ASR §60.2 持锁实测）

> 设置 OMP/MKL/OPENBLAS/NUMEXPR_NUM_THREADS=1 后，ASR 的 CPU 从 7.81 核降到约 1 核
> （libiomp5md 原来占 6.85 核），RTF 也改善了。
> TTS 模块的根因分析也指向**主机 CPU 争用**，会让 NPU 上的 TTS 变慢约 30 %。

⇒ 本模块**只做一件事**：把下面四个环境变量设为 `1`：

    OMP_NUM_THREADS
    MKL_NUM_THREADS
    OPENBLAS_NUM_THREADS
    NUMEXPR_NUM_THREADS

## ★ 铁律：必须早于 import

OpenMP / MKL 运行时在**库被加载**（= `import numpy` 那一刻）读取这些变量，
之后再设**无效**（这不是本模块的推测，是 OpenMP 运行时的既定行为）。
⇒ 调用点必须落在**模块顶部、任何 numpy / OpenVINO import 之前**。

因此本模块**自身绝不 import numpy / openvino**（否则这个调用点本身就晚了一步），
只依赖 `os`（标准库，无 BLAS）。

## 逃生阀（A/B 对照用）

环境变量 `EXT_THREAD_LIMIT=0` ⇒ **不设**这四个变量
⇒ 用于跑「不限制线程」的对照组，量化线程限制到底值多少。

## 返回值

`apply_thread_limits()` 返回一个**可直接落盘**的字典：
`enabled` / `value` / `applied` / `previous` / `note`。
⇒ reviewer 可从 `p1_report.json` / `margin.json` 里直接核对，
   不必去猜这个进程到底有没有限过线程。
"""
from __future__ import annotations

import os
from typing import Dict, Optional

# ★ 四个变量缺一不可（EXT-011 明文列出）
THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)

#: 目标线程数（EXT-011：设为 1）
DEFAULT_THREADS = "1"

#: `EXT_THREAD_LIMIT` 取这些值时视为「关闭」（用于 A/B 对照）
OFF_VALUES = {"0", "off", "false", "no", "none", "disabled"}


def is_enabled(default: bool = True) -> bool:
    """读 `EXT_THREAD_LIMIT` 判断是否启用线程限制。

    * 未设置 ⇒ 用 `default`；
    * 设为 `0/off/false/no/none/disabled` ⇒ **关闭**（不改任何环境变量）。
    """
    raw = os.environ.get("EXT_THREAD_LIMIT")
    if raw is None:
        return default
    return raw.strip().lower() not in OFF_VALUES


def _fmt_line(rec: Dict) -> str:
    if not rec.get("enabled"):
        return ("[ext-thread-limits] 已跳过（EXT_THREAD_LIMIT 关闭）"
                " ⇒ 不改 %s" % ", ".join(THREAD_ENV_VARS))
    applied = rec.get("applied") or {}
    prev = rec.get("previous") or {}
    parts = []
    for name in THREAD_ENV_VARS:
        old = prev.get(name)
        old_s = "unset" if old in (None, "") else old
        parts.append("%s=%s (was %s)" % (name, applied.get(name), old_s))
    return ("[ext-thread-limits] 已限制线程数（EXT-011）：%s"
            " ⇒ 必须早于 numpy/openvino import 生效" % "; ".join(parts))


def apply_thread_limits(*, value: str = DEFAULT_THREADS,
                        enabled: Optional[bool] = None,
                        log=None) -> Dict:
    """把四个线程数环境变量设为 `value`（默认 ``"1"``）。

    Parameters
    ----------
    value : str
        目标线程数（EXT-011 要求 ``"1"``）。
    enabled : bool | None
        显式开关；``None`` ⇒ 读 `EXT_THREAD_LIMIT` 环境变量决定。
    log : callable | None
        日志回调（形如 ``print(msg)``）；``None`` ⇒ 不打日志。

    Returns
    -------
    dict
        ``{"enabled", "value", "applied", "previous", "note"}`` —— 可直接落盘。

    ⚠️ `enabled=False` 时**不动**已有环境变量
       （外层环境里若已由用户设了 OMP_NUM_THREADS，就尊重用户设置）。
    """
    previous: Dict[str, Optional[str]] = {}
    applied: Dict[str, str] = {}

    if enabled is None:
        enabled = is_enabled()
    enabled = bool(enabled)

    if enabled:
        for name in THREAD_ENV_VARS:
            previous[name] = os.environ.get(name)
            os.environ[name] = str(value)
            applied[name] = str(value)
        note = ("已生效：%s = %s（必须在 numpy/openvino import 之前调用）"
                % (", ".join(THREAD_ENV_VARS), value))
    else:
        for name in THREAD_ENV_VARS:
            previous[name] = os.environ.get(name)
        note = ("未生效：EXT_THREAD_LIMIT 关闭 ⇒ 保留外层环境原有的线程数设置"
                "（用于 A/B 对照）")

    rec = {
        "enabled": enabled,
        "value": str(value),
        "applied": applied,
        "previous": previous,
        "note": note,
    }
    if log is not None:
        try:
            log(_fmt_line(rec))
        except Exception:
            pass
    return rec
