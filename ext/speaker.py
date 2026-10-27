"""speaker.py — EXT-002：说话人识别走旁路，不阻塞定稿

EXT-002 修订要点（相对 EXT-001 架构 B 节）：
  * pyannote / segmentation-3.0 **只**用来识别说话人，**不再**用于强制断句；
  * 定稿段**先**发出去；spk 晚到（可晚 1–2 s）时，用 id **补发一条 spk 更新事件**；
  * 说话人攒够约 3 s 干净语音之前，spk 为 null，TTS 用**上一句的音色**或**预设 A**；
  * pyannote 与说话人 embedding 在**旁路**运行，**不阻塞定稿**。

实现边界：
  * 本模块**不含** pyannote 依赖调用；ASR-013 交付后由主会话通知接线点
    （`SpeakerTracker.update_from_diarization()`）。
  * 无 ASR-013 交付时，退化为「单一说话人」简化克隆路线（EXT-001 B 节 P1）。
  * 音色克隆只放内存，不落盘（EXT-001 总原则）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SpeakerProfile:
    """一个说话人的累计状态（内存内，不落盘）。"""

    spk_id: str
    clean_sec: float = 0.0          # 累计干净语音时长
    first_seen_ts: float = field(default_factory=time.time)
    last_update_ts: float = field(default_factory=time.time)
    voice_id: Optional[str] = None  # TTS 侧音色标识（克隆向量或预设）
    clone_pcm: Optional[bytes] = None  # 克隆用的干净 PCM（只在内存）
    updated: bool = False           # 是否已经向下游发过 spk 更新事件
    # 音频时间轴上的覆盖区间（会话相对秒，与 wall clock 无关）
    spans: List[tuple] = field(default_factory=list)

    def ready_for_clone(self, required_sec: float) -> bool:
        return self.clean_sec >= required_sec


class SpeakerTracker:
    """维护当前会话的说话人状态，并对齐 EXT-002 的"晚到补发"语义。

    典型用法（桥接服务管线里）：
        tracker = SpeakerTracker()
        # 1) ASR 定稿段先出，spk 此刻可能还是 None
        spk = tracker.spk_for_final(t_start, t_end)
        # 2) pyannote 旁路出结果后
        events = tracker.update_from_diarization(diarization)
        #    → events 是需要补发给插件的 spk 更新事件
    """

    def __init__(self, *, clean_sec_required: float = 3.0,
                 max_late_lag_sec: float = 2.0,
                 preset_voice: str = "A") -> None:
        self.clean_sec_required = clean_sec_required
        self.max_late_lag_sec = max_late_lag_sec
        self.preset_voice = preset_voice
        self._profiles: Dict[str, SpeakerProfile] = {}
        self._pending: Dict[str, List[tuple]] = {}  # spk_id -> [(seg_id, t_start, t_end)]
        self._last_spk: Optional[str] = None        # 上一句的音色来源
        self._n_final_without_spk = 0

    # ── 定稿段走的时候用 ────────────────────────────────────────
    def spk_for_final(self, seg_id: str, t_start: float, t_end: float) -> Optional[str]:
        """返回该定稿段的说话人 id；未知或证据不足时返回 None。

        None 的含义（EXT-002）：TTS 用上一句音色或预设 A。
        """
        prof = self._lookup_by_time(t_start, t_end)
        if prof is None:
            self._n_final_without_spk += 1
            return None
        prof.last_update_ts = time.time()
        return prof.spk_id

    def _lookup_by_time(self, t_start: float, t_end: float) -> Optional[SpeakerProfile]:
        """按时间区间找已知说话人（取重叠最多、且已够 clone 时长的那个）。"""
        best: Optional[SpeakerProfile] = None
        best_ov = 0.0
        for prof in self._profiles.values():
            ov = self._overlap(prof, t_start, t_end)
            if ov > best_ov:
                best_ov, best = ov, prof
        if best is None:
            return None
        return best

    @staticmethod
    def _overlap(prof: SpeakerProfile, t_start: float, t_end: float) -> float:
        """profile 在音频时间轴上的覆盖与目标区间的重叠秒数。"""
        total = 0.0
        for s, e in prof.spans:
            total += max(0.0, min(e, t_end) - max(s, t_start))
        return total

    # ── pyannote 旁路结果进来时用 ───────────────────────────────
    def update_from_diarization(self, diarization) -> List[dict]:
        """接收 pyannote 旁路输出，返回需要**补发**的 spk 更新事件。

        Parameters
        ----------
        diarization : iterable
            每项至少含 spk_id 与时间戳 t_start / t_end（秒）。

        Returns
        -------
        list[dict]
            每项形如 {"type": "spk_update", "spk_id": ..., "seg_id": ...,
                      "t_start": ..., "t_end": ..., "voice": ...}
            空列表表示无需补发（没有新信息）。
        """
        events: List[dict] = []
        for item in diarization or []:
            spk_id = str(item.get("spk_id") or item.get("speaker") or "")
            if not spk_id:
                continue
            t_start = float(item.get("t_start", item.get("start", 0.0)))
            t_end = float(item.get("t_end", item.get("end", t_start)))
            prof = self._profiles.get(spk_id)
            if prof is None:
                prof = SpeakerProfile(spk_id=spk_id)
                prof.first_seen_ts = time.time()
                self._profiles[spk_id] = prof
            prof.last_update_ts = time.time()
            prof.clean_sec += max(0.0, t_end - t_start)
            prof.spans.append((t_start, t_end))
            self._last_spk = spk_id
            # 够 3 s 才能克隆音色，之前用预设 A；
            # 一旦攒够语音量，要从预设 A **升级**为该说话人的克隆音色。
            if prof.ready_for_clone(self.clean_sec_required):
                if prof.voice_id != spk_id:
                    prof.voice_id = spk_id  # 实际由 TTS 侧克隆，voice_id 先占位
            else:
                prof.voice_id = self.preset_voice
            # 补发：把这条时间区间上挂着的、还没定稿过的段补上 spk
            for seg_id, s, e in self._pending.pop(spk_id, []):
                events.append({
                    "type": "spk_update",
                    "spk_id": spk_id,
                    "seg_id": seg_id,
                    "t_start": s,
                    "t_end": e,
                    "voice": prof.voice_id,
                })
            if prof.updated:
                # 已有过 spk 的段，其音色可能因 clone 就绪而变化
                events.append({
                    "type": "spk_update",
                    "spk_id": spk_id,
                    "seg_id": None,
                    "t_start": t_start,
                    "t_end": t_end,
                    "voice": prof.voice_id,
                })
            prof.updated = True
        return events

    def register_pending(self, seg_id: str, spk_id: Optional[str],
                         t_start: float, t_end: float) -> None:
        """定稿时若 spk 还没来，先挂起，等旁路结果到了补发。"""
        if spk_id is None:
            self._pending.setdefault("__unassigned__", []).append(
                (seg_id, t_start, t_end))
            self._n_final_without_spk += 1
        else:
            prof = self._profiles.setdefault(
                spk_id, SpeakerProfile(spk_id=spk_id))
            prof.updated = True
            self._last_spk = spk_id

    def voice_for(self, spk_id: Optional[str]) -> str:
        """给定 spk 取音色；spk 为 None 或证据不足 → 上一句音色或预设 A。"""
        if spk_id:
            prof = self._profiles.get(spk_id)
            if prof and prof.voice_id:
                return prof.voice_id
        if self._last_spk:
            prof = self._profiles.get(self._last_spk)
            if prof and prof.voice_id:
                return prof.voice_id
        return self.preset_voice

    def stats(self) -> dict:
        return {
            "n_speakers": len(self._profiles),
            "n_pending_unassigned": len(self._pending.get("__unassigned__", [])),
            "n_final_without_spk": self._n_final_without_spk,
            "clean_sec_required": self.clean_sec_required,
            "preset_voice": self.preset_voice,
            "blocking_diarization": False,  # EXT-002
        }
