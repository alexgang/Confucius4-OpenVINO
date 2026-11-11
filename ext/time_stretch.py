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

import math

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


def wsola(x: np.ndarray, rate: float, *, frame_ms: int = 40,
          tol_ms: int = 10, sample_rate: Optional[int] = None) -> np.ndarray:
    """保持音高的变速（WSOLA）。

    ★ v0.4.5（用户 11-11 抽听 A/B 后选定）：算法换成 App `live_caption/time_stretch.time_stretch`
      的同一套实现。旧实现拿**上一帧的开头**做相似度参考（应该是刚放下那一帧的重叠尾部）
      ⇒ 每次拼接相位对不齐 ⇒ 音色/音高被拉偏（30 句实测：说话人相似度 1.1× 0.79、1.5× 0.68，
      音高偏差约 350 音分）。换算法后 1.1× 0.98、1.5× 0.86，音高偏差 14–25 音分，速度快约 40 倍。
      数据：reviewer `ext/tsm_ab/results2.json`（A0 = 旧实现，A4 = 本实现）。

    Parameters
    ----------
    x : 输入波形（float32，单声道）。
    rate : 变速倍率；>1 变短（加速），<1 变长（减速），1.0 原样返回。
    frame_ms : 分析帧长（毫秒）；tol_ms : 相似度搜索窗（毫秒）。
    sample_rate : 输入采样率；缺省 `config.SAMPLE_RATE`。TTS 输出是 24 kHz，必须传对。

    Returns
    -------
    长度约为 len(x) / rate 的波形（float32）。
    """
    arr = np.asarray(x, dtype=np.float32).reshape(-1)
    n = arr.size
    sp = float(rate) if rate is not None else 1.0
    if n == 0 or sp != sp or sp <= 0 or abs(sp - 1.0) < 1e-9:
        return arr.copy()
    sr = int(sample_rate or SAMPLE_RATE)
    if n < 64:
        out_len = max(1, int(round(n / sp)))
        idx = np.linspace(0, n - 1, out_len)
        return np.interp(idx, np.arange(n), arr).astype(np.float32)

    ha = max(64, int(round(sr * frame_ms / 1000.0)))     # 分析帧长
    ov = max(16, ha // 4)                                 # 重叠长度
    hs_out = max(16, ha - ov)                             # 合成 hop
    ha_in = max(16, int(round(hs_out * sp)))              # 分析 advance = 合成 hop × 倍率
    search = max(4, int(round(sr * tol_ms / 1000.0)))

    win = np.hanning(ha).astype(np.float32)
    n_frames = max(1, int(math.ceil(max(0, n - ha) / float(ha_in))) + 1)
    out_len = max(1, int(round(n / sp)))   # 也支持 <1（放慢）；bridge 只用 >1
    total = n_frames * hs_out + ha + 4
    out = np.zeros(total, dtype=np.float32)
    norm = np.zeros(total, dtype=np.float32)

    template = None   # 上一帧的重叠尾部（下一帧要和它对齐）
    pos = 0
    out_pos = 0
    while pos + ha + search < n:
        best = pos
        if template is not None:
            lo = max(0, pos - search)
            hi = min(n - ha, pos + search)
            if hi > lo:
                t = template
                tt = float(np.dot(t, t))
                if tt > 1e-9:
                    seg = arr[lo:hi + ha]
                    c = np.correlate(seg, t, mode='valid')
                    energy = np.convolve(seg ** 2, np.ones(t.size, dtype=np.float32), mode='valid')
                    ncc = c / np.sqrt(np.maximum(energy, 1e-9) * tt)
                    best = lo + int(np.argmax(ncc))
        frame = arr[best:best + ha]
        if frame.size < ha:
            frame = np.pad(frame, (0, ha - frame.size))
        out[out_pos:out_pos + ha] += frame * win
        norm[out_pos:out_pos + ha] += win
        template = arr[best + ha - ov: best + ha].copy()
        pos += ha_in
        out_pos += hs_out

    nz = norm > 1e-6
    out[nz] /= norm[nz]
    return out[:out_len].astype(np.float32)
