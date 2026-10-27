"""duration.py — EXT-001 B 节：TTS 时长适配（保持音高变速 + 顺延）

规则（来自 EXT-001 架构 B 节）：
  * 目标时长 = t_end − t_start；可以占用到下一段开始前的静音；
  * 超长时在**服务端**做**保持音高**的变速（WSOLA 等，**不能用 playbackRate**，那会变调）；
  * 变速上限 1.25×；超出上限就允许**顺延**，并记录顺延量。

纯函数实现，便于自测；实际变速算法由 `time_stretch.py` 接入。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DurationFit:
    """一段配音的时长适配结果。"""

    seg_id: str
    target_sec: float          # 目标时长（t_end - t_start）
    speech_sec: float          # TTS 原始语音时长
    rate: float                # 实际变速倍率（1.0 = 不变速）
    extend_sec: float          # 向下一段借用的静音时长
    defer_sec: float           # 顺延量（>0 表示排不进原窗口）
    feasible: bool             # 是否能在窗口内放下

    def to_dict(self) -> dict:
        return {
            "seg_id": self.seg_id,
            "target_sec": round(self.target_sec, 3),
            "speech_sec": round(self.speech_sec, 3),
            "rate": round(self.rate, 4),
            "extend_sec": round(self.extend_sec, 3),
            "defer_sec": round(self.defer_sec, 3),
            "feasible": self.feasible,
        }


def fit_duration(seg_id: str, *, t_start: float, t_end: float, speech_sec: float,
                 next_start: Optional[float] = None,
                 max_rate: float = 1.25) -> DurationFit:
    """计算一段配音的时长适配方案。

    Parameters
    ----------
    t_start, t_end : float
        原声定稿段的起止（秒）。
    speech_sec : float
        TTS 合成出来的语音时长（秒）。
    next_start : float or None
        下一段的起始时刻；用于计算可以借用的静音。
    max_rate : float
        变速上限（默认 1.25，来自 EXT-001）。
    """
    target = max(0.0, t_end - t_start)
    # 可以占用到下一段开始前的静音
    extend = 0.0
    if next_start is not None:
        extend = max(0.0, next_start - t_end)
    budget = target + extend

    if speech_sec <= 0:
        return DurationFit(seg_id, target, speech_sec, 1.0, extend, 0.0, True)

    if speech_sec <= budget:
        # 放得下，不用变速
        return DurationFit(seg_id, target, speech_sec, 1.0, extend, 0.0, True)

    # 需要变速：保持音高，最多 max_rate 倍
    needed_rate = speech_sec / budget if budget > 0 else float("inf")
    if needed_rate <= max_rate:
        return DurationFit(seg_id, target, speech_sec, needed_rate, extend, 0.0, True)

    # 超出变速上限 → 允许顺延，记录顺延量
    rate = max_rate
    fitted = budget * rate
    defer = max(0.0, speech_sec - fitted)
    return DurationFit(seg_id, target, speech_sec, rate, extend, defer, False)
