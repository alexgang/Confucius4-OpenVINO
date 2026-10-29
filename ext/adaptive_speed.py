"""adaptive_speed.py — ★ EXT-009：**自适应加速播放**（App 与插件统一参数）

## 为什么有这个模块

EXT-009（用户决定 2026-10-29 15:30）：App 和插件都采用"自适应加速播放"
来追赶滞后（**不改译文，不丢句，不回退到丢句**）。

原 EXT-001 架构 B 节只规定了"单句超长时做**保持音高**变速，上限 1.25×，
超出就顺延"。实测（P1 run7）表明：**端到端 RTF 2.09 > 1**
（§6.5.2 独立实测）⇒ 顺延量会**持续累积**
（末句滞后 297.88 s、增长斜率 −0.892 sec/sec，§6.3）
⇒ 单靠"每句最多 1.25×"**追不上**累积滞后。

EXT-009 把"追赶滞后"这件事做成**统一参数**，App 与插件一致。

## 统一参数（EXT-009 明文，本模块是唯一实现处）

```
lag   = 实际开播时刻 − 目标开播时刻
        插件的目标开播时刻 = t0 + t_start + D
speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)
        · lag ≤ 3 s  ⇒ 1.0×
        · lag = 15 s ⇒ 1.30×（上限）
```

* **滞回**：降速时 `lag < 2 s` 才回到 `1.0×`（避免来回抖动）。
* **按句变速**：每句开播时定一次速度，句内不变。
* **相邻句之间每次变化不超过 0.1×**（听感更平滑）。
* **保持音高**：用 WSOLA（`ext/time_stretch.py`），**不能**用改采样率 /
  `playbackRate`（那会变调）。
* **GUI 底栏显示当前语速倍率和滞后秒数**（插件侧由 `extension/player.js` 实现）。

## 与「单句时长适配」的关系（EXT-009 EXT 侧明文）

> 原来按句做时长适配（单句超长时压缩）的逻辑保留，
> 在它的基础上叠加"按滞后自适应"的速度，**两者相乘后整体仍然不超过 1.30×**，
> 超出的部分就顺延。

⇒ 本模块只负责**自适应加速**这一层（1.0 ~ 1.30×）；
   与时长适配（1.0 ~ 1.25×）的**相乘与封顶**由 `combine_rates()` 负责。

## 纯函数设计

本模块是**纯计算**（不碰音频、不碰设备）⇒ 可直接单测。
音频侧的 WSOLA 变速由调用方在**主机侧单线程**完成
（EXT-009：「时间伸缩在主机侧做，不能占满 CPU（遵守 ASR-026 的线程限制，单线程）」）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import config as C


@dataclass
class SpeedDecision:
    """一句的加速决策结果。"""

    speed: float                # 本句实际采用的倍率（1.0 ~ 1.30）
    lag_sec: float              # 输入的滞后（实际开播 − 目标开播）
    raw_speed: float            # 未加约束的原始速度（公式直接算出的）
    reason: str                 # 决策原因（写进产物，便于复盘）
    clamped_max: bool = False   # 是否被 1.30× 上限截断
    clamped_step: bool = False  # 是否被「相邻句 0.1×」限制截断
    held_by_hysteresis: bool = False  # 是否因滞回保持原速度

    def to_dict(self) -> dict:
        return {
            "speed": round(self.speed, 4),
            "lag_sec": round(self.lag_sec, 4),
            "raw_speed": round(self.raw_speed, 4),
            "reason": self.reason,
            "clamped_max": self.clamped_max,
            "clamped_step": self.clamped_step,
            "held_by_hysteresis": self.held_by_hysteresis,
        }


def raw_speed_for_lag(lag_sec: float, *,
                      lag_free_sec: float = C.ADAPT_LAG_FREE_SEC,
                      gain: float = C.ADAPT_GAIN_PER_SEC,
                      speed_max: float = C.ADAPT_SPEED_MAX,
                      speed_min: float = C.ADAPT_SPEED_MIN) -> float:
    """EXT-009 的速度公式（**未加约束**的原始值）。

    ```
    speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)
    ```

    Parameters
    ----------
    lag_sec : float
        滞后秒数（实际开播时刻 − 目标开播时刻）；可为负（提前了）。

    Returns
    -------
    float
        原始速度（已在 [speed_min, speed_max] 内截断）。
    """
    v = 1.0 + (lag_sec - lag_free_sec) * gain
    return max(speed_min, min(speed_max, v))


def decide_speed(lag_sec: float, *, prev_speed: float = 1.0,
                 lag_free_sec: float = C.ADAPT_LAG_FREE_SEC,
                 lag_hyst_sec: float = C.ADAPT_LAG_HYST_SEC,
                 gain: float = C.ADAPT_GAIN_PER_SEC,
                 speed_max: float = C.ADAPT_SPEED_MAX,
                 speed_min: float = C.ADAPT_SPEED_MIN,
                 max_step: float = C.ADAPT_MAX_STEP) -> SpeedDecision:
    """算一句该用多少倍速（EXT-009 完整决策）。

    决策顺序（**顺序很重要**，逐条对应 EXT-009 的明文）：

    1. **公式**：`raw = clamp(1.0 + (lag − 3) × 0.025, 1.0, 1.30)`；
    2. **滞回**：若 `lag < 2 s`（滞回门槛）且 `raw < prev_speed`
       ⇒ **不降速**，保持 `prev_speed`（避免在门槛附近来回抖动）。
       ⚠️ 若 `raw >= prev_speed`（加速方向）⇒ 正常按公式升速，不受滞回限制。
    3. **相邻句步长限制**：`|speed − prev_speed| ≤ 0.1×`
       ⇒ 超出的部分被截断（听感更平滑）。
    4. **上限**：`speed ≤ 1.30×`。

    Parameters
    ----------
    lag_sec : float
        本句的滞后秒数。
    prev_speed : float
        上一句实际采用的倍率（用于滞回与步长限制）。

    Returns
    -------
    SpeedDecision
    """
    raw = raw_speed_for_lag(lag_sec, lag_free_sec=lag_free_sec, gain=gain,
                             speed_max=speed_max, speed_min=speed_min)
    clamped_max = raw >= speed_max - 1e-9 and \
        raw_speed_for_lag(lag_sec, lag_free_sec=lag_free_sec, gain=gain,
                          speed_max=1e9, speed_min=speed_min) > speed_max

    held = False
    speed = raw
    reason = "按公式"

    # ── 滞回：只有「想降速」时才受门槛约束 ──────────────────
    #   降速 ⇒ raw < prev_speed 且 lag < lag_hyst_sec ⇒ 保持 prev_speed。
    #   （加速方向不受滞回限制 ⇒ 滞后一大就立刻能升速）
    if raw < prev_speed and lag_sec < lag_hyst_sec:
        speed = prev_speed
        held = True
        reason = "滞回保持（lag %.2fs < %.1fs 且想降速）" % (
            lag_sec, lag_hyst_sec)

    # ── 相邻句步长限制（0.1×） ──────────────────────────────
    clamped_step = False
    delta = speed - prev_speed
    if delta > max_step:
        speed = prev_speed + max_step
        clamped_step = True
        reason = "步长上限（+0.1×）"
    elif delta < -max_step:
        speed = prev_speed - max_step
        clamped_step = True
        reason = "步长上限（−0.1×）"

    # ── 上限 ────────────────────────────────────────────────
    if speed > speed_max:
        speed = speed_max
        clamped_max = True
        reason = "上限 1.30×"
    if speed < speed_min:
        speed = speed_min

    return SpeedDecision(speed=speed, lag_sec=lag_sec, raw_speed=raw,
                          reason=reason, clamped_max=clamped_max,
                          clamped_step=clamped_step,
                          held_by_hysteresis=held)


def combine_rates(fit_rate: float, adapt_speed: float, *,
                  total_max: float = C.ADAPT_TOTAL_RATE_MAX) -> dict:
    """把「单句时长适配」与「自适应加速」**相乘**，并封顶总倍率。

    EXT-009 EXT 侧明文：
    > 两者相乘后整体仍然不超过 1.30×，超出的部分就顺延。

    Parameters
    ----------
    fit_rate : float
        时长适配的倍率（`ext.duration.fit_duration().rate`，1.0 ~ 1.25×）。
    adapt_speed : float
        自适应加速的倍率（本模块 `decide_speed().speed`，1.0 ~ 1.30×）。

    Returns
    -------
    dict
        ``total_rate``（封顶后的总倍率）、``raw_rate``（相乘未封顶）、
        ``capped``（是否被封顶）、``defer_extra_sec``（被封顶掉的那部分
        对应的时长差，需要顺延）。
    """
    fit_rate = max(1.0, float(fit_rate or 1.0))
    adapt_speed = max(1.0, float(adapt_speed or 1.0))
    raw = fit_rate * adapt_speed
    total = min(raw, total_max)
    return {
        "fit_rate": round(fit_rate, 4),
        "adapt_speed": round(adapt_speed, 4),
        "raw_rate": round(raw, 4),
        "total_rate": round(total, 4),
        "total_max": total_max,
        "capped": raw > total_max + 1e-9,
        # 被封顶掉的那部分倍率（>1 表示有内容排不进原窗口 ⇒ 顺延）
        "rate_loss_x": round((raw - total) / total, 6) if total > 0 else 0.0,
    }


def lag_from_schedule(*, actual_start: float, target_start: float) -> float:
    """算 lag（EXT-009 口径）。

    ```
    lag = 实际开播时刻 − 目标开播时刻
    ```

    插件侧：目标开播时刻 = `t0 + t_start + D`。

    Parameters
    ----------
    actual_start : float
        实际开播时刻（AudioContext 绝对秒）。
    target_start : float
        目标开播时刻。

    Returns
    -------
    float
        lag 秒数；正数 = 晚了（滞后），负数 = 早了。
    """
    return actual_start - target_start


def target_start_for(*, t0: float, t_start: float, delay_sec: float) -> float:
    """插件侧的目标开播时刻（EXT-009 明文）。

    目标开播时刻 = `t0 + t_start + D`。
    """
    return t0 + t_start + delay_sec
