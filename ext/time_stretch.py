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

import numpy as np

from .config import SAMPLE_RATE


def _hann(n: int) -> np.ndarray:
    return 0.5 - 0.5 * np.cos(2.0 * np.pi * np.arange(n) / n)


def wsola(x: np.ndarray, rate: float, *, frame_ms: int = 60,
          tol_ms: int = 10) -> np.ndarray:
    """保持音高的变速。

    Parameters
    ----------
    x : np.ndarray
        输入波形（float32，16 kHz 单声道）。
    rate : float
        变速倍率；>1 变短（加速），<1 变长（减速），1.0 原样返回。
    frame_ms, tol_ms : int
        合成帧长与相似度搜索容忍窗。

    Returns
    -------
    np.ndarray
        变速后波形，长度约为 len(x) / rate。
    """
    x = np.asarray(x, dtype=np.float32)
    if abs(rate - 1.0) < 1e-6 or x.shape[0] == 0:
        return x

    frame = int(SAMPLE_RATE * frame_ms / 1000)
    tol = int(SAMPLE_RATE * tol_ms / 1000)
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

    while ana_pos + frame < x.shape[0]:
        # 在 [ana_pos - tol, ana_pos + tol] 里找与 prev_tail 最相似的偏移
        lo = max(0, ana_pos - tol)
        hi = min(x.shape[0] - frame, ana_pos + tol)
        if hi <= lo:
            best = ana_pos
        else:
            cand = x[lo:hi + frame]
            # 用前一段尾部做互相关，找最匹配位置
            ref = prev_tail[:tol * 2] if prev_tail.shape[0] >= tol * 2 else prev_tail
            clen = min(ref.shape[0], cand.shape[0] - (lo - ana_pos))
            if clen < 16:
                best = ana_pos
            else:
                seg = cand[:clen]
                # 归一化互相关
                num = np.correlate(seg - seg.mean(), ref[:clen] - ref[:clen].mean(),
                                    mode="valid")
                if num.shape[0] == 0:
                    best = ana_pos
                else:
                    best = lo + int(np.argmax(num))
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
