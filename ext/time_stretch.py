"""time_stretch.py — 保持音高的变速（WSOLA）

EXT-001 B 节要求：TTS 语音超长时，在服务端做**保持音高**的变速，
上限 1.25×；**不能用 playbackRate**，那会变调。

本文件实现 WSOLA（Waveform Similarity Overlap-Add），
纯 numpy，无外部依赖；只做小幅度（≤1.25×）变速。

参考实现思路与 librosa 的 phase_vocoder 不同，这里用时域 WSOLA：
  * 以固定帧长 Hann 窗合成；
  * 合成时在容忍窗内搜索与上一帧最相似的位置（互相关最大），
    叠加对齐 ⇒ 波形连续 ⇒ 音高不变。

复用边界：本文件为 EXT 自有实现，不修改任何其他模块的文件。
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .config import SAMPLE_RATE


def _hann(n: int) -> np.ndarray:
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)


def _normalized_xcorr_best(seg: np.ndarray, ref: np.ndarray) -> int:
    """在 `seg` 里找与 `ref` 最相似的位置的**偏移**（WSOLA 的相似度搜索）。

    ★★★ 缺陷 21（本轮实测抓到）：旧实现是这样写的 ——

        clen = min(ref.shape[0], cand.shape[0] - (lo - ana_pos))
        seg = cand[:clen]
        num = np.correlate(seg - seg.mean(), ref[:clen] - ref[:clen].mean(),
                           mode="valid")
        best = lo + int(np.argmax(num))

    `cand` 的长度是 `(hi - lo) + frame`，而 `clen` 被算成
    `min(len(ref), len(cand) - (lo - ana_pos))` ⇒ 在 `lo == ana_pos` 时
    `clen = min(len(ref), len(cand))`；而 `len(ref)` 通常**恰好等于**
    `len(cand)` 附近的量级 ⇒ `np.correlate(..., mode="valid")` 在两个
    **等长**数组上返回**长度 1** 的数组（`|n-m|+1 = 1`）
    ⇒ `argmax` 恒为 0 ⇒ `best` **恒等于 `lo`**
    ⇒ **搜索窗口从未真正被搜索过**（实测：连续 8 帧 `best - lo` 恒为 0），
    WSOLA 退化成「固定偏移的重叠相加」⇒ 在有基频漂移/静音边界的语音上
    会有可听的相位不连续（拼接痕迹）。

    ⇒ 修法：**按候选偏移逐个算归一化互相关**，取最大值。
      候选数 = 容忍窗内的整数采样点数（默认 ±10 ms @16 kHz ⇒ 321 个）
      ⇒ 计算量 = 321 × 320 次乘加/帧，纯 numpy 仍够快，
      而且**真的在搜索**（可被自测区分：见 `tests/test_ext_selfcheck.py`）。

    Returns
    -------
    int
        最佳候选的**下标**（相对 `seg` 的起点，0 = 用 `seg` 自身）。
        无有效候选时返回 0。
    """
    n_ref = ref.shape[0]
    n_seg = seg.shape[0]
    if n_ref < 8 or n_seg < 8:
        return 0
    # 参考信号用**较短**的一侧 ⇒ 互相关长度 = n_ref
    r = np.asarray(ref[:n_ref], dtype=np.float64)
    r = r - r.mean()
    r_energy = float(np.dot(r, r))
    if r_energy < 1e-12:
        return 0
    # 候选起点：从 0 到 n_seg - n_ref
    n_cand = n_seg - n_ref + 1
    if n_cand <= 1:
        return 0
    # ★ 向量化：一次算出所有候选窗口的归一化互相关
    #   （用 sliding_window_view，避免 Python 层逐候选循环 ⇒ 性能可接受）
    windows = np.lib.stride_tricks.sliding_window_view(
        np.asarray(seg, dtype=np.float64), n_ref)[:n_cand]      # (n_cand, n_ref)
    w = windows - windows.mean(axis=1, keepdims=True)
    energies = np.einsum("ij,ij->i", w, w)
    # 能量为 0 的候选（静音窗口）得分记 -inf
    safe = energies > 1e-12
    if not safe.any():
        return 0
    num = w @ r
    scores = np.full(n_cand, -np.inf, dtype=np.float64)
    scores[safe] = num[safe] / np.sqrt(energies[safe] * r_energy)
    return int(np.argmax(scores))


def wsola(x: np.ndarray, rate: float, *, frame_ms: int = 60,
          tol_ms: int = 10, sample_rate: Optional[int] = None) -> np.ndarray:
    """保持音高的变速（WSOLA）。

    Parameters
    ----------
    x : np.ndarray
        输入波形（float32，单声道）。
    rate : float
        变速倍率；>1 变短（加速），<1 变长（减速），1.0 原样返回。
    frame_ms, tol_ms : int
        合成帧长与相似度搜索容忍窗（**毫秒**，与采样率无关）。
    sample_rate : int or None
        输入波形的采样率；缺省用 `config.SAMPLE_RATE`（16 kHz）。
        ★ 必须传对：TTS 的输出是 **24 kHz**，若沿用 16 kHz 的帧长，
          帧/容忍窗的实际时长会缩掉 1/3（60 ms 变成 40 ms）
          ⇒ 拼接粒度变粗、容忍窗变窄 ⇒ 音质变差。

    Returns
    -------
    np.ndarray
        变速后波形，长度约为 len(x) / rate。
    """
    x = np.asarray(x, dtype=np.float32)
    if abs(rate - 1.0) < 1e-6 or x.shape[0] == 0:
        return x

    sr = int(sample_rate or SAMPLE_RATE)
    frame = int(sr * frame_ms / 1000)
    tol = int(sr * tol_ms / 1000)
    if frame <= 0:
        return x

    win = _hann(frame)
    # 合成步长 = 分析步长 / rate
    ana_step = frame // 2
    syn_step = int(round(ana_step / rate))
    if syn_step <= 0:
        return x

    n_out = int(x.shape[0] / rate) + frame
    out = np.zeros(n_out, dtype=np.float32)
    win_sum = np.zeros(n_out, dtype=np.float32)

    # 第一个帧直接放在 0
    out[:frame] += x[:frame] * win
    win_sum[:frame] += win

    ana_pos = frame
    syn_pos = frame
    prev_tail = x[:frame]
    # ★ 上一帧的**尾部**（长度 tol*2）作为相似度参考
    ref_len = max(1, tol * 2)

    while ana_pos + frame < x.shape[0]:
        # 在 [ana_pos - tol, ana_pos + tol] 里找与 prev_tail 最相似的偏移
        lo = max(0, ana_pos - tol)
        hi = min(x.shape[0] - frame, ana_pos + tol)
        if hi <= lo:
            best = ana_pos
        else:
            cand = x[lo:hi + frame]
            ref = prev_tail[:ref_len] if prev_tail.shape[0] >= ref_len else prev_tail
            if ref.shape[0] < 8 or cand.shape[0] < 8:
                best = ana_pos
            else:
                # ★ 缺陷 21 修法：真正在候选窗口里搜索（见 _normalized_xcorr_best）
                off = _normalized_xcorr_best(cand, ref)
                best = lo + off
        seg = x[best:best + frame]
        if seg.shape[0] < frame:
            break
        if syn_pos + frame > n_out:
            break
        out[syn_pos:syn_pos + frame] += seg * win
        win_sum[syn_pos:syn_pos + frame] += win
        prev_tail = seg
        ana_pos = best + ana_step
        syn_pos += syn_step

    nz = win_sum > 1e-6
    out[nz] /= win_sum[nz]
    return out
