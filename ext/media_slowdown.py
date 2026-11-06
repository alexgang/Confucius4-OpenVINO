"""media_slowdown.py — ★ EXT-041：**媒体轻微降速**（让画面追配音）

## 为什么需要它（EXT-041 的背景）

用户 2026-11-06 决定**放宽**「signed P95 ≤ 0.3 s」⇒ 新口径要求：

1. signed P95 ≤ **1.5 s**、P50 ≤ 0.8 s；
2. **不能无限累积**：`signed_err` 对时间的斜率 ≤ **0.01 s/s**；
3. 不丢句、不重复、不异常静音；变速 ≤ 现有上限 1.3×。

reviewer 同时指出：**只放宽数值、不改机制，长视频照样越落越远**
⇒ 必须加一个**机制**。

## 机制选型（本轮做的取舍）

EXT-041 给了三个可选机制：

| 机制 | 本轮取舍 | 理由 |
|---|---|---|
| **① 媒体轻微降速**（`video.playbackRate`） | ✅ **选它** | 唯一**不动译文、不动引擎、不改 ASR/MT**的机制；EXT 侧可独立完成；reviewer 给了明确区间（下限 0.9） |
| ② 积压时收紧（缩短停顿 / 更短译文） | ❌ 不选 | 要改译文 ⇒ **必须与 MT 侧对齐**（EXT 不能单方面改）⇒ 超出 EXT 模块边界 ⇒ 需跨模块协调，本轮不做 |
| ③ 调 D | ❌ 不选 | D 只影响**起点**，不改变**每单位源时间的占用率** ⇒ 对**斜率**（累积速率）几乎无效；且调大 D 只是把耗尽点推后，**不解决无限累积** |

## ★★ 数学依据（为什么降速能治斜率）—— 口径必须写准

### 记号

* `S` = 源语音**内容**总长（秒）—— 即所有「有 TTS 的段」的 `t_end − t_start` 之和
  （**内容**秒，不是墙钟秒）；
* `P` = 配音**内容**总长（秒）= Σ`speech_sec`；
* `sos` = `speech_over_src` = `P / S`（译文比原声长多少）；
* `tor` = `tts_over_src` = `Σtts_sec / S`（端到端占用率）；
* `r` = 媒体降速倍率（`playbackRate`，1.0 = 不降速）。

### 关键前提：降速**只改墙钟，不改内容**

* 媒体以 `r` 倍速播放 ⇒ 同样的**内容**占用 `1/r` 倍的**墙钟**；
* 上行采集仍是**每秒 16000 个采样**（浏览器重采样输出）
  ⇒ **`t_start` 仍是墙钟轴**（这点是全部推导的基石）；
* `t_start`（墙钟轴）↔ 内容位置 的换算：`内容 = r × t_start`。

### 终值落后（= 素材播完时配音落后画面多少）

第 `s` 秒**内容**在墙钟 `s/r` 到达；这段内容对应的配音在墙钟 `s/r + (t0+D)` 播出。
配音内容总长 `P` ⇒ 配音播完的墙钟 = `t0 + P`；画面播完的墙钟 = `t0 + S/r`。
⇒ **终值落后**

```
lag_end = P − S/r = S·(sos − 1/r)
```

⇒ **不堆积（终值不落后）的条件**

```
P ≤ S/r    ⇔    r ≤ 1/sos    ⇔    r ≤ 1/tor（两者相差 <0.1%）
```

⇒ 临界倍率 `r* = 1/tor`。

### 斜率（signed_err 对 `t_start` 的斜率，单位 s/s）

总时长（墙钟）= `S/r` ⇒

```
slope = lag_end / (S/r) = r·sos − 1
```

⚠️ **注意**：斜率是 **`r·sos − 1`**，不是 `tor − 1/r`
（后者是「单位内容多占用多少墙钟」，**量纲不同**，本模块早期版本写错过）。

代入实测（run `20261105_174558`：`sos = 1.0942`、`tor = 1.0936`）：

| `r` | `r·sos − 1` | 终值落后 `S·(sos − 1/r)` | 判定 |
|---|---|---|---|
| 1.00 | **+0.0942** | +16.95 s | ❌（实测拟合 +0.135，量级一致） |
| 0.95 | +0.0395 | +7.93 s | ❌ |
| 0.92 | **+0.0067** | +1.31 s | ✅（≤0.01） |
| **1/tor = 0.9144** | **+0.0000** | ≈ +0.01 s | ✅✅（精确持平） |
| 0.90 | −0.0152 | −3.03 s | ⚠️ **反向漂移**（配音超前） |

⇒ reviewer 举例的区间 **0.92–0.95** 里，**只有 0.92 达标**；
⇒ 本模块取 **临界倍率 `r* = 1/tor`（并夹到 `[0.90, 1.00]`）**——
它比 0.92 **更精确**（残差 ≈ 0 s 而不是 1.31 s），
且仍满足 reviewer 给的**下限 0.9**。

### ★ 为什么不能简单取 `min(default, r*)`

旧实现 `rate = min(default_rate, r_crit)` 有个**真缺陷**：
当 `tor` 稍大于 1（如 1.02 ⇒ `r* = 0.980`）时，`min(0.92, 0.980) = 0.92`
⇒ 实际斜率 = `0.92×1.02 − 1 = −0.0616` ⇒ **反向漂移**（配音越来越超前画面）。
⇒ 正确规则是 **直接取临界倍率** `r = clamp(r*, 0.90, 1.00)`。

## 边界与安全

* 下限 **0.90**：再慢下去观感明显变差，且 reviewer 明确给了下限。
* 上限 **1.0**：**永不加速**（加速画面会改变语义时轴，属于另一件事）。
* `tor ≤ 1` ⇒ 端到端不超载 ⇒ **不降速**（`r = 1.0`）。
* `r* < 0.90` ⇒ 连下限都做不到 ⇒ 降速**救不了**（只能把耗尽点推后）
  ⇒ 取 0.90 并在 `reason` 里**如实说明**（**不假装能解决**）。

## ★ 时间轴的诚实说明

* `t_start` 的轴 = **上行链路的采样时间轴** = **墙钟轴**（降速不改变它）；
* 媒体降速**只改变墙钟**：源音频到达插件的墙钟变慢 ⇒
  配音的**目标时刻** `t0 + t_start + D` 随之变慢 ⇒
  **配音与画面一起慢下来** ⇒ 相对关系保持 ⇒ **斜率被压平**；
* ⚠️ **代价（必须如实说明）**：
  * 慢放会让语音**音高变低**（ASR 输入被降调）⇒ 识别率可能下降；
  * 画面变慢 ⇒ 用户看到的是「慢放画面」；
  * 这两个代价是**机制①的固有成本**，本模块不掩盖。

## 纯函数设计

本模块是**纯计算**（不碰音频、不碰设备、不碰 DOM）⇒ 可直接单测。
真正设置 `video.playbackRate` 的是插件侧（`extension/`），
本模块只负责**算倍率**。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

#: 降速下限（reviewer 明确：下限 0.9）
RATE_FLOOR = 0.90
#: 降速上限（**永不加速**：>1.0 会改变语义时轴）
RATE_CEIL = 1.00
#: 默认降速倍率（**没有实测值时**的保守取值）
#:   取 0.92（reviewer 举例区间内、且对本轮实测 tor=1.0936 恰好达标）
#:   ⇒ 有实测值时**一律用临界倍率**，不用这个。
RATE_DEFAULT = 0.92
#: 斜率目标（EXT-041 新口径：signed_err 斜率 ≤ 0.01 s/s）
SLOPE_TARGET = 0.01


@dataclass
class SlowdownDecision:
    """一次降速决策的结果。"""

    rate: float                  # 实际采用的 playbackRate（1.0 = 不降速）
    reason: str                 # 人类可读的理由（写进落盘产物）
    tts_over_src: Optional[float]  # 实测占用率（没有就是 None）
    r_critical: Optional[float]    # 临界倍率 = 1 / tts_over_src
    needs_slowdown: bool = False   # 是否真的降了速
    # 估算的净漂移斜率（s/s）；无实测数据时为 None
    est_slope: Optional[float] = None
    # 估算的终值落后（秒）；无实测数据时为 None
    est_lag_end: Optional[float] = None
    # 实测 speech_over_src（用于算斜率）；没有就是 None
    speech_over_src: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "rate": round(self.rate, 4),
            "reason": self.reason,
            "tts_over_src": self.tts_over_src,
            "r_critical": (round(self.r_critical, 4)
                           if self.r_critical is not None else None),
            "needs_slowdown": self.needs_slowdown,
            "est_slope": (round(self.est_slope, 5)
                          if self.est_slope is not None else None),
            "est_lag_end_sec": (round(self.est_lag_end, 4)
                                if self.est_lag_end is not None else None),
            "speech_over_src": self.speech_over_src,
            "slope_target": SLOPE_TARGET,
            "slope_ok": (self.est_slope is not None
                         and self.est_slope <= SLOPE_TARGET),
        }


def _est_slope(rate: float, sos: Optional[float]) -> Optional[float]:
    """估算斜率（s/s）= `r·sos − 1`。

    ⚠️ 口径：**斜率是「内容差」在墙钟上的体现**，不是 `tor − 1/r`
    （后者量纲不同 ⇒ 本模块早期版本写错过 ⇒ 见模块 docstring 的推导）。
    """
    if sos is None:
        return None
    return rate * float(sos) - 1.0


def rate_for(tts_over_src: Optional[float], *,
             enabled: bool = True,
             default_rate: float = RATE_DEFAULT,
             speech_over_src: Optional[float] = None) -> SlowdownDecision:
    """按实测 `tts_over_src` 算出该用的媒体降速倍率。

    * `tts_over_src` 为 `None`（还没有实测值）⇒ 用 `default_rate`（0.92）；
    * `tts_over_src ≤ 1` ⇒ **不需要降速** ⇒ `rate = 1.0`；
    * 否则 `r_critical = 1 / tts_over_src`：
      - 若 `r_critical ≤ RATE_FLOOR` ⇒ 连下限都做不到 ⇒ 降速**救不了**
        ⇒ 取 `RATE_FLOOR` 并在 reason 里**如实说明**（不要假装能解决）；
      - 否则取 **`r_critical`**（夹到 `[RATE_FLOOR, RATE_CEIL]`）。

    ★ 为什么取 `r_critical` 而不是 `min(default_rate, r_critical)`：
      `min()` 在 `tor` 接近 1 时会取到偏小的值 ⇒ 斜率变**负** ⇒
      配音**反向超前**画面（另一个方向的错位）⇒ 详见模块 docstring。
    """
    if not enabled:
        return SlowdownDecision(
            rate=1.0, reason="用户关闭了媒体降速开关",
            tts_over_src=tts_over_src, r_critical=None,
            needs_slowdown=False, est_slope=None, est_lag_end=None,
            speech_over_src=speech_over_src)

    if tts_over_src is None:
        return SlowdownDecision(
            rate=default_rate,
            reason=("没有实测 tts_over_src ⇒ 保守用默认 %.2f"
                    "（下限 %.2f）" % (default_rate, RATE_FLOOR)),
            tts_over_src=None, r_critical=None,
            needs_slowdown=True, est_slope=_est_slope(default_rate,
                                                      speech_over_src),
            est_lag_end=None, speech_over_src=speech_over_src)

    tor = float(tts_over_src)
    if tor <= 0:
        return SlowdownDecision(
            rate=1.0, reason="tts_over_src 非法（≤0）⇒ 不降速",
            tts_over_src=tor, r_critical=None,
            needs_slowdown=False, est_slope=None, est_lag_end=None,
            speech_over_src=speech_over_src)

    if tor <= 1.0:
        return SlowdownDecision(
            rate=1.0,
            reason="tts_over_src=%.4f ≤ 1 ⇒ 端到端不超载 ⇒ 不降速" % tor,
            tts_over_src=tor, r_critical=1.0 / tor,
            needs_slowdown=False,
            est_slope=_est_slope(1.0, speech_over_src), est_lag_end=None,
            speech_over_src=speech_over_src)

    r_crit = 1.0 / tor
    if r_crit <= RATE_FLOOR:
        return SlowdownDecision(
            rate=RATE_FLOOR,
            reason=("tts_over_src=%.4f ⇒ 临界倍率 %.4f **低于下限 %.2f** "
                    "⇒ 降速**救不了**（只能把耗尽点推后，不能压平斜率）"
                    % (tor, r_crit, RATE_FLOOR)),
            tts_over_src=tor, r_critical=r_crit,
            needs_slowdown=True,
            est_slope=_est_slope(RATE_FLOOR, speech_over_src),
            est_lag_end=None, speech_over_src=speech_over_src)

    rate = min(max(r_crit, RATE_FLOOR), RATE_CEIL)
    slope = _est_slope(rate, speech_over_src)
    reason = ("tts_over_src=%.4f ⇒ 临界倍率 %.4f ⇒ 取 %.4f"
              "（下限 %.2f）" % (tor, r_crit, rate, RATE_FLOOR))
    if slope is not None:
        reason += ("；估算斜率 %+.5f s/s（目标 ≤ %.2f）"
                   % (slope, SLOPE_TARGET))
    return SlowdownDecision(
        rate=rate,
        reason=reason,
        tts_over_src=tor, r_critical=r_crit,
        needs_slowdown=(rate < 1.0), est_slope=slope,
        est_lag_end=None, speech_over_src=speech_over_src)


def effective_rate_for_ratio(speech_over_src: float,
                              rtf_out: float,
                              **kwargs) -> SlowdownDecision:
    """由 `speech_over_src` 与 `RTF_out` 反推 `tts_over_src` 再决策。

    `tts_over_src = RTF_out × speech_over_src`（见 `ext/bridge.py` 的口径）⇒
    当**只有**这两个数时也能决策。
    """
    sor = float(speech_over_src)
    rtf = float(rtf_out)
    kwargs.setdefault("speech_over_src", sor)
    return rate_for(rtf * sor, **kwargs)
