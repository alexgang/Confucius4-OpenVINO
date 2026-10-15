"""seg_stream.py — C-014 #2 修订：VAD 切句 + 修复 finish 丢字（C-015/C-018）

按 C-018 修正：
  - 不按固定时长盲切。改为：在 [min_segment_sec, max_segment_sec] 范围内找静音点切。
  - 默认 min_segment_sec=12s, max_segment_sec=20s。
  - 切点必须走 finish_streaming_transcribe flush 尾巴（C-015 #3 丢字 bug 修复）。
  - 新段 unfixed_chunk_num=0（per 官方 ws_server.py）。

策略：
  - rolling:    按 max_segment_sec 硬切（保留旧行为作 fallback；C-014 #1 用过）
  - vad:        累积到 min_segment_sec 后，在 [min, max] 找静音点切；超 max 强制切
  - vad_roll:   vad 但任何段不超过 max
  - off:        单段（短音频用）
"""
from __future__ import annotations
import os
import time
import numpy as np

from backends import ASRBackend, ASRStreamingState, SAMPLE_RATE


def _make_segment_state(backend: ASRBackend, *, unfixed_chunk_num: int,
                        unfixed_token_num: int, chunk_size_sec: float,
                        force_language=None, context: str = "") -> ASRStreamingState:
    return backend.init_streaming_state(
        context=context,
        language=force_language,
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=chunk_size_sec,
    )


# ── 能量 VAD（无外部依赖，16 kHz mono） ─────────────────────
def _frame_rms(x: np.ndarray, frame_ms: int = 30, hop_ms: int = 10) -> np.ndarray:
    """返回每帧 RMS。"""
    n = int(frame_ms * SAMPLE_RATE / 1000)
    h = int(hop_ms * SAMPLE_RATE / 1000)
    if n <= 0 or h <= 0:
        return np.zeros((0,), dtype=np.float32)
    if x.shape[0] < n:
        pad = np.zeros(n - x.shape[0], dtype=np.float32)
        x = np.concatenate([x, pad])
    n_frames = max(0, (x.shape[0] - n) // h + 1)
    out = np.zeros(n_frames, dtype=np.float32)
    for i in range(n_frames):
        s = i * h
        seg = x[s:s + n]
        out[i] = float(np.sqrt(np.mean(seg * seg) + 1e-12))
    return out


def find_silence_in_range(audio: np.ndarray, *, start_sample: int, end_sample: int,
                          silence_db: float = -40.0,
                          min_silence_ms: int = 300,
                          frame_ms: int = 30, hop_ms: int = 10) -> int | None:
    """在 [start_sample, end_sample] 范围内找最长静音段中点。

    Returns
    -------
    int | None
        切点 sample 位置（在该静音段中点），或 None（找不到）。
    """
    if end_sample <= start_sample:
        return None
    seg = audio[start_sample:end_sample]
    rms = _frame_rms(seg, frame_ms=frame_ms, hop_ms=hop_ms)
    if rms.shape[0] == 0:
        return None
    db = 20.0 * np.log10(rms + 1e-7)
    n = int(hop_ms * SAMPLE_RATE / 1000)
    is_sil = db < silence_db
    min_sil_frames = max(1, int(min_silence_ms / hop_ms))
    # 找最长连续 silence run
    best_start, best_len = -1, 0
    cur_start, cur_len = -1, 0
    for i in range(is_sil.shape[0]):
        if is_sil[i]:
            if cur_start < 0:
                cur_start = i
                cur_len = 1
            else:
                cur_len += 1
        else:
            if cur_len > best_len:
                best_start, best_len = cur_start, cur_len
            cur_start, cur_len = -1, 0
    if cur_len > best_len:
        best_start, best_len = cur_start, cur_len
    if best_start < 0 or best_len < min_sil_frames:
        return None
    # 切点 = 静音段中点（对齐到 sample）
    mid_frame = best_start + best_len // 2
    cut_sample_in_seg = mid_frame * n
    return start_sample + cut_sample_in_seg


# ── 主入口：分段的流式 ─────────────────────────────────────────
class SegmentedStreamer:
    """按策略把长音频切段喂给 backend 的 LSP 流式。

    Parameters
    ----------
    backend : ASRBackend
    strategy : 'rolling' | 'vad' | 'vad_roll' | 'off'
        off → 单段（与原来 streaming_asr 行为一致）
    min_segment_sec : float
        最小段长（VAD 模式下：在累积到该时长后才开始找静音点切）
    max_segment_sec : float
        段最大时长（VAD 模式：超此硬切；rolling 模式：等分）
    """

    def __init__(self, backend: ASRBackend, *,
                 strategy: str = 'vad',
                 min_segment_sec: float = 12.0,
                 max_segment_sec: float = 20.0,
                 force_language=None, context: str = "",
                 unfixed_chunk_num: int = 0,  # C-018：新段 unfixed_chunk_num=0
                 unfixed_token_num: int = 5,
                 chunk_size_sec: float = 0.32,
                 max_new_tokens: int = 32,
                 adaptive_budget: bool = False,
                 vad_silence_db: float = -40.0,
                 vad_min_silence_ms: int = 300,
                 enable_hallucination_reset: bool = True):
        self.backend = backend
        self.strategy = strategy
        self.min_segment_sec = min_segment_sec
        self.max_segment_sec = max_segment_sec
        self.force_language = force_language
        self.context = context
        self.unfixed_chunk_num = unfixed_chunk_num  # 默认 0（C-018 修正）
        self.unfixed_token_num = unfixed_token_num
        self.chunk_size_sec = chunk_size_sec
        self.max_new_tokens = max_new_tokens
        # C-047: True 时按官方负反馈动态决定每 chunk 生成长度（1..floor），
        # 避免固定 32 让单次自回归失控写满冻结前缀。
        self.adaptive_budget = adaptive_budget
        self.vad_silence_db = vad_silence_db
        self.vad_min_silence_ms = vad_min_silence_ms
        self.enable_hallucination_reset = enable_hallucination_reset

    # ── 切段策略 ─────────────────────────────────────────
    def _plan_segments(self, audio: np.ndarray) -> list[tuple[int, int]]:
        """返回 [(start_sample, end_sample), ...]"""
        if self.strategy == 'off' or audio.shape[0] == 0:
            return [(0, audio.shape[0])]

        if self.strategy == 'rolling':
            seg_samples = int(self.max_segment_sec * SAMPLE_RATE)
            segs = []
            i = 0
            while i < audio.shape[0]:
                j = min(i + seg_samples, audio.shape[0])
                segs.append((i, j))
                i = j
            return segs

        if self.strategy in ('vad', 'vad_roll'):
            min_samp = int(self.min_segment_sec * SAMPLE_RATE)
            max_samp = int(self.max_segment_sec * SAMPLE_RATE)
            segs = []
            i = 0
            while i < audio.shape[0]:
                # 至少跑到 min_segment_sec
                j = min(i + min_samp, audio.shape[0])
                if j >= audio.shape[0]:
                    segs.append((i, audio.shape[0]))
                    break
                # 在 [i+min, i+max] 找静音点
                upper = min(i + max_samp, audio.shape[0])
                cut = find_silence_in_range(
                    audio, start_sample=j, end_sample=upper,
                    silence_db=self.vad_silence_db,
                    min_silence_ms=self.vad_min_silence_ms,
                )
                if cut is None:
                    # 无静音，强制切
                    segs.append((i, upper))
                    i = upper
                else:
                    segs.append((i, cut))
                    i = cut
            return segs
        raise ValueError(f"unknown strategy: {self.strategy}")

    # ── 单段流式（重置 state；返回 final_text） ─────────
    def _run_one_segment(self, audio_seg: np.ndarray, state: ASRStreamingState) -> str:
        from streaming_asr import streaming_transcribe, finish_streaming_transcribe
        feed_chunk = int(SAMPLE_RATE * 0.04)
        feed_pos = 0
        n_hallucination_resets = 0
        while feed_pos < audio_seg.shape[0]:
            end = min(feed_pos + feed_chunk, audio_seg.shape[0])
            streaming_transcribe(
                self.backend, audio_seg[feed_pos:end], state,
                max_new_tokens=self.max_new_tokens,
                rollback_punctuation=False,
                enable_hallucination_reset=self.enable_hallucination_reset,
                adaptive_budget=self.adaptive_budget,
            )
            # C-031#5 / user 10:26 fallback: hallucination reset 触发后 finish 当前段
            if getattr(state, '_force_finish', False):
                n_hallucination_resets += 1
                state._force_finish = False  # 重置以便后续段不受影响
                break
            feed_pos = end
        # C-018：切点必须走 finish_streaming_transcribe 把尾巴 flush 出来
        # 如果是 hallucination reset 触发的提前 finish, 仍要 flush (max_new_tokens 减小避免再次循环)
        flush_max = max(16, self.max_new_tokens // 2) if n_hallucination_resets > 0 else max(64, self.max_new_tokens)
        final = finish_streaming_transcribe(
            self.backend, state,
            max_new_tokens=flush_max,
        )
        # 记录 reset 次数到 state
        state._n_resets_in_seg = n_hallucination_resets
        return final

    # ── 整段主循环 ──────────────────────────────────────
    def run(self, audio: np.ndarray, *, progress: bool = False):
        """返回 (full_text, segment_results)。

        segment_results: list[dict], 每段 {seg_idx, start_s, end_s, duration_s,
                                            n_chunks, wall_s, rtf, text}
        """
        segs = self._plan_segments(audio)
        results = []
        full_text = ""
        wall_start = time.perf_counter()
        for idx, (s, e) in enumerate(segs):
            seg_audio = audio[s:e]
            if seg_audio.shape[0] == 0:
                continue
            state = _make_segment_state(
                self.backend,
                unfixed_chunk_num=self.unfixed_chunk_num,
                unfixed_token_num=self.unfixed_token_num,
                chunk_size_sec=self.chunk_size_sec,
                force_language=self.force_language,
                context=self.context,
            )
            t0 = time.perf_counter()
            final_text = self._run_one_segment(seg_audio, state)
            wall = time.perf_counter() - t0
            seg_dur = (e - s) / SAMPLE_RATE
            results.append({
                'seg_idx': idx,
                'start_s': s / SAMPLE_RATE,
                'end_s': e / SAMPLE_RATE,
                'duration_s': seg_dur,
                'n_chunks': state.chunk_id,
                'wall_s': wall,
                'rtf': wall / seg_dur if seg_dur > 0 else 0.0,
                'text': final_text,
                'n_resets': getattr(state, '_n_resets_in_seg', 0),
            })
            full_text += final_text
            if progress and (idx % 5 == 0 or idx == len(segs) - 1):
                elapsed = time.perf_counter() - wall_start
                print(f'[seg] {idx:3d}/{len(segs)} start={s/SAMPLE_RATE:7.2f}s '
                      f'dur={seg_dur:6.2f}s chunks={state.chunk_id:3d} '
                      f'wall={wall:6.2f}s RTF={wall/seg_dur:.3f} '
                      f'elapsed={elapsed:6.1f}s text={final_text[:40]!r}', flush=True)
        return full_text, results
