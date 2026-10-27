# -*- coding: utf-8 -*-
"""tts_audible_criterion.py —— 「**真的出声了**」的**唯一判据来源**。

🔴🔴 **为什么需要这个模块（2026-10-27 §62）**：

APP-021（`status/app/CORRECTIONS_APP.md` L256）**明文**要求：

> 「app071 的判据改成：`n_read` 增量 ≥ 本句样本数，并且本句峰值 > 1e-2。」
> 「不要用 "played ≥ 1" 或者假 service 的冒烟结果来宣称"能出声"。」

⇒ **实测：该要求**从未被执行** —— `app071` / `app074` / `app075` / `app077` /
`app039` 至今仍用 `n_played >= 1` 当判据（`app077` 虽另加了 A4/A5 两条硬数字，
但它自己的 **A2** 仍是 `n_played >= 1`，且 `app071`/`app074`/`app075`/`app039`
**一条硬数字都没有**）⇒ ⇒ **这一类缺陷会复发**（§36 同源教训：
「修掉一处」≠「这一类不会再来」）⇒ **必须把它变成闸门**。

## 🔴 判据本身的依据（APP-021 证据 1 的三段）

`played` 事件在 APP-021 之前是「**最后一块写进环形缓冲**」时发的 ⇒
它**不代表声卡播完**（环形缓冲 3 s ⇒ 发 `played` 时最多还有 3 s 没播）。
§54 之后 `played` 已改为「播完才发」，但：

- 「`player is None` 时照样发 `played`」这条旧路径**仍在历史脚本的判据里**；
- 更关键：**旧脚本 `close()` 掉 worker 后**，`pending` 被清空 ⇒
  **根本看不到任何遥测** ⇒ 只能退回到 `n_played >= 1` 这个弱判据。

⇒ 所以**判据必须落到硬数字上**，而不是事件计数。

## ✅ 判据（两条**同时**成立才算「真的出声」）

| 编号 | 判据 | 含义 |
|---|---|---|
| **C1** | `read_delta >= n_samples` | 本句的**全部样本**都被播放回调**取走**了 ⇒ 音频真的交给了声卡 |
| **C2** | `peak > 1e-2` | 本句合成出来的音频**不是静音**（峰值低于 1e-2 ⇒ 判为静音合成） |

- **C1** 的样本数口径 = `telemetry['n_samples']`（**本句**的样本数），
  `read_delta` = 本句期间 `ring.n_read` 的**增量**。
- **C2** 的峰值口径 = `telemetry['peak']`（**本句**的绝对峰值）。

⚠️ **C1 的坑（§54.5 踩过）**：遥测快照**必须在播完之后重算** ⇒
`read_delta` 才是「本句期间真正被取走的量」。
若是「写完缓冲那一刻」的快照 ⇒ `read_delta` 只到此刻（实测 68 608 / 本句 120 960）
⇒ **C1 会被误判成失败**。§54 之后 worker 已在 `wait_consumed()` 之后重算 ⇒ 可用。

⚠️ **C2 的坑**：`peak` 是**合成侧**的幅度，与音量/静音无关 ⇒
**峰值够不代表用户听得见**（系统音量 0.25 + 笔记本外放仍可能听不见）
⇒ **本模块只判「链路真的出声了」，不判「用户听见了」**
⇒ 后者**必须由用户抽听**（APP-021 验收 C）。

## 🔴🔴 「等本句」与「判本句」必须**物理分离**（§62 新增）

APP-021⑦ 作废的是「**用事件计数宣称出声**」，但**事件计数本身仍有用**
（用来知道「本句播完了没」）。两者的正确写法完全不同：

| 用途 | 正确写法 | 错误写法 |
|---|---|---|
| **等**本句播完 | 和**提交前**的快照比**相对增量** ⇒ `n_played > played_before` | `n_played >= 1`（把「历史上任何一句」当本句） |
| **判**本句是否出声 | `evaluate_audible(telemetry)` | `n_played >= 1` |

🔴 **为什么必须用相对增量**：`n_played` 是**累计计数** ⇒ `>= 1` 只说明
「**从服务启动到现在**至少播过一句」⇒ 在下列场景会**假通过**：

- 句 ① 已播 ⇒ 提交句 ② 后 `n_played` 立刻 `>= 1` ⇒ **句 ② 其实还没出声**
  就被判成「出声了」；
- `app077` 先发「🔊 测试声音」⇒ `last_telemetry` 已被**测试音**覆盖 ⇒
  再提交正式句 ⇒ 只看 `last_telemetry` 会把**测试音的遥测**当成本句的证据。

⇒ 下面的 `sentence_played()` 把这两点**一次性**堵死：
它要求「**计数相对提交前增加了**」**且**「**遥测对象是新的**」。

## 🔴 用法

```python
from tts_audible_criterion import evaluate_audible, describe_criterion

ok, reasons = evaluate_audible(telemetry)
if ok:
    print('✅ 真的出声（链路级）：' + describe_criterion(telemetry))
else:
    print('🔴 不能宣称出声：' + '；'.join(reasons))
```

`evaluate_audible(telemetry)` 返回 `(bool, List[str])`：
- `telemetry` 为 `None` / 空 ⇒ **判失败**（**不是**「无法判断 ⇒ 放行」）
  ⇒ 这是本模块最要紧的一条：**缺证据 ⇒ 判失败**，不是判成功。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# 🔴 阈值（APP-021 原文）：峰值 > 1e-2 ⇒ 排除「静音合成」
PEAK_MIN = 1e-2

# 🔴 遥测里「本句样本数」的字段名（worker 的 `_telemetry_snapshot` 产出）
N_SAMPLES_KEY = 'n_samples'
READ_DELTA_KEY = 'read_delta'
PEAK_KEY = 'peak'


def _get(tel: Dict[str, Any], key: str) -> Optional[float]:
    v = tel.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def evaluate_audible(telemetry: Optional[Dict[str, Any]]
                     ) -> Tuple[bool, List[str]]:
    """按 APP-021 的硬判据判断「本句是否真的出声了（链路级）」。

    返回 `(ok, reasons)`：
      · `ok=True`  ⇒ C1 与 C2 **同时**成立；
      · `ok=False` ⇒ `reasons` 列出**具体**哪一条不成立、缺什么。
    ⚠️ **缺证据 ⇒ False**（`telemetry` 为 None / 缺字段 ⇒ 判失败）。
    """
    reasons: List[str] = []

    if not telemetry:
        return False, ['没有遥测数据 ⇒ 无法证明出声（缺证据 ⇒ 判失败）']

    n_samples = _get(telemetry, N_SAMPLES_KEY)
    read_delta = _get(telemetry, READ_DELTA_KEY)
    peak = _get(telemetry, PEAK_KEY)

    # ── C1：n_read 增量 ≥ 本句样本数 ──────────────────────────────
    if n_samples is None:
        reasons.append('遥测缺 %s（无法核对「样本数」）' % N_SAMPLES_KEY)
    elif read_delta is None:
        reasons.append('遥测缺 %s（无法核对「已读增量」）' % READ_DELTA_KEY)
    elif read_delta < n_samples:
        reasons.append('C1 不成立：read_delta=%.0f < n_samples=%.0f'
                       '（音频没被全部取走）' % (read_delta, n_samples))

    # ── C2：峰值 > 1e-2（不是静音合成）────────────────────────────
    if peak is None:
        reasons.append('遥测缺 %s（无法核对「峰值」）' % PEAK_KEY)
    elif peak <= PEAK_MIN:
        reasons.append('C2 不成立：peak=%.6f ≤ %g（静音合成）'
                       % (peak, PEAK_MIN))

    return (not reasons), reasons


def describe_criterion(telemetry: Optional[Dict[str, Any]]) -> str:
    """把判据的**原始字段**拼成一句可引用的话（供 STATUS / 日志引用）。"""
    if not telemetry:
        return '（无遥测）'
    return ('n_samples=%s / read_delta=%s / peak=%s（阈值 %g）'
            % (telemetry.get(N_SAMPLES_KEY),
               telemetry.get(READ_DELTA_KEY),
               telemetry.get(PEAK_KEY), PEAK_MIN))


def audible_verdict(telemetry: Optional[Dict[str, Any]]) -> str:
    """给「一句」的最终判定文本（**不**宣称用户听见了）。"""
    ok, reasons = evaluate_audible(telemetry)
    if ok:
        return ('OK 链路级真的出声（%s）'
                ' ⚠️ 不代表用户听得见 ⇒ 仍需抽听'
                % describe_criterion(telemetry))
    return 'FAIL 不能宣称出声：' + '；'.join(reasons)


# ══════════════════════════════════════════════════════════════════════
# 🔴🔴 §62 新增：「等本句」与「判本句」的物理分离
# ══════════════════════════════════════════════════════════════════════

# 🔴 遥测里的「本句 id」字段名（worker 的 `played` 事件带 `id`）
#   ⚠️ `tts_service` 目前把**整个 telemetry dict** 存进 `last_telemetry`
#   ⇒ telemetry 里**可能**带 `id`，也可能不带（取决于 worker 版本）
#   ⇒ 用 `get` 取，取不到就**退回计数判据**（但仍要求相对增量）。
TELEMETRY_ID_KEY = 'id'


def played_snapshot(stats: Optional[Dict[str, Any]]) -> Tuple[int, Optional[int]]:
    """抓一份「提交本句**之前**」的快照（用于算**相对增量**）。

    返回 `(n_played, telemetry_id)`：
    - `n_played` ⇒ 当前累计已播句数；
    - `telemetry_id` ⇒ 当前 `last_telemetry` 的 id（若遥测里没有 id ⇒ None）。

    ⚠️ **必须在 `submit()` 之前调用** ⇒ 否则拿到的就是「提交后」的值，
       相对增量恒为 0 ⇒ 永远等不到。
    """
    if not stats:
        return 0, None
    tel = stats.get('last_telemetry') or {}
    tid = tel.get(TELEMETRY_ID_KEY)
    try:
        tid_i = int(tid) if tid is not None else None
    except (TypeError, ValueError):
        tid_i = None
    try:
        np = int(stats.get('n_played') or 0)
    except (TypeError, ValueError):
        np = 0
    return np, tid_i


def sentence_played(stats: Optional[Dict[str, Any]],
                    played_before: int,
                    telemetry_id_before: Optional[int] = None
                    ) -> Tuple[bool, str]:
    """判断「**本句**是不是真的播完了」（**不是**判断「是否出声」）。

    ✅ 这是「等事件」的**唯一合法写法**：**相对增量**（不是常量阈值）。

    三条判据**同时**成立才算「本句播完」：
    1. `n_played > played_before` ⇒ **计数相对提交前增加了**
       （⇒ 不是「历史上播过别的句」）；
    2. `last_telemetry` 存在；
    3. 若**遥测带 id**（`telemetry_id_before` 已知）⇒ **本句 id 与提交前不同**
       ⇒ 不是「上一句 / 测试音」的旧遥测。

    ⚠️ **本函数只回答「播完了没」，不回答「出声了没」**
    ⇒ 「出声」的判据见 `evaluate_audible()`。
    """
    if not stats:
        return False, '没有 stats()'
    try:
        np_now = int(stats.get('n_played') or 0)
    except (TypeError, ValueError):
        np_now = 0
    if np_now <= played_before:
        return False, 'n_played 未增加（%d ≤ 提交前的 %d）' % (np_now,
                                                            played_before)
    tel = stats.get('last_telemetry') or {}
    if not tel:
        return False, '还没有 last_telemetry（遥测没落下来）'
    tid = tel.get(TELEMETRY_ID_KEY)
    if tid is not None and telemetry_id_before is not None:
        try:
            tid_i = int(tid)
        except (TypeError, ValueError):
            tid_i = None
        if tid_i is not None and tid_i == telemetry_id_before:
            return False, ('遥测 id 仍是提交前的 %d ⇒ 是旧遥测'
                           '（不是本句）' % tid_i)
    return True, ('n_played %d→%d（相对增量）'
                  % (played_before, np_now))


def sentence_failed(stats: Optional[Dict[str, Any]],
                    failed_before: int = 0) -> bool:
    """判断「**本句**是不是失败了」（相对增量 ⇒ 不受历史影响）。"""
    if not stats:
        return False
    try:
        nf = int(stats.get('n_failed') or 0)
    except (TypeError, ValueError):
        return False
    return nf > failed_before
