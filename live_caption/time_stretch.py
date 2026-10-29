#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""time_stretch — WSOLA 时间伸缩（**保持音高**）。

🔴🔴🔴 APP-042（2026-10-29 15:30，用户决定）：
  「滞后追赶采用**自适应加速播放**（App 和插件统一）」
  ⇒ App 侧按句变速（1.0×–1.30×）来追赶语音滞后，
    **不改译文、不丢句、不回退到丢句**。

🔴🔴 **为什么必须是 WSOLA 而不是改采样率**：
  APP-042 明文：「**保持音高**：用 WSOLA 或同类时间伸缩算法
  （例如 audiotsm 的 WSOLA，或自写的 numpy 实现），
  **不能用改采样率或 playbackRate 的方式，那样会变调**。」
  - 改采样率（resample）⇒ 音高随速度一起变（老人声变成快放）⇒ **违要求**；
  - `playbackRate`（Windows 媒体 API）⇒ 同样变调，且改变全局播放状态 ⇒ **违要求**；
  - WSOLA（Waveform Similarity Overlap-Add）⇒ **时长变、音高不变** ⇒ 正是要求。

🔴 **为什么自己写而不用 audiotsm**：
  客户包**不装** audiotsm（实测：本机与客户包 site-packages 里都没有），
  而客户包**只有 numpy**（+scipy，但 scipy 没有可靠的时间伸缩实现）⇒
  ⇒ 自己写一个**只依赖 numpy** 的 WSOLA ⇒ 客户包零新增依赖。
  ⚠️ 依赖纪律（§8）：**不得**为了这个功能给客户包新增第三方包。

🔴 **线程纪律**（ASR-026 / APP-042 明文「单线程」「不能占满 CPU」）：
  时间伸缩在**主机侧**做 ⇒ 但它是对音频块的**一次性**变换
  ⇒ 放在 worker 的合成线程里（本来就是后台线程）⇒ **不额外起线程**。
  ⚠️ WSOLA 的重叠相加是 O(N) ⇒ 一句音频通常几秒 ⇒ 开销可忽略。

## 算法（经典 WSOLA）
1. 分析步长 `Hs = round(Ha / speed)`，合成步长 `Ha`（帧长）；
2. 在输入里按 `Hs` 跳一步取一帧（**搜索窗**内找与上一帧最相似的位置）；
3. 相邻帧做 **overlap-add**（重叠长度 `Ha/4`）。

🔴 **质量要点**：
  - 相似度用**归一化互相关**（NCC）⇒ 找「波形最像」的位置 ⇒ 减少相位跳变 ⇒ 少金属味；
  - 搜索窗取 `±(Hs/4)`；
  - Hann 窗 ⇒ 重叠相加无咔哒声。

## 公开 API
  `time_stretch(x, speed, sr=None, frame_ms=40, search_ms=10) -> np.ndarray`
      - `speed` > 1 ⇒ **变短**（加速）；`speed` == 1 ⇒ **原样返回**（逐位不变）；
      - `speed` < 1 ⇒ 变长（本项目不用，但实现对称以便自测）。
  `speed_for_lag(lag_s, ...)` → APP-042 的**统一参数**（见下）。

## APP-042 的统一参数（**App 与插件必须一致**）
  - `lag` = 「这句的实际开播时刻 − 这句的目标开播时刻」
  - `speed = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)`
    ⇒ lag ≤ 3 s 时 1.0×；lag = 15 s 时达到上限 1.30×
  - **滞回**：降速时 lag < 2 s 才回到 1.0×（避免来回抖动）
  - **按句变速**：每句开播时定一次速度，句内不变
  - **相邻句之间每次变化不超过 0.1×**
"""
from __future__ import annotations

import math

import numpy as np

# ── APP-042 统一参数 ────────────────────────────────────────────────
#: 低于这个滞后（秒）⇒ 1.0×（不加速）
LAG_DEADZONE_S = 3.0
#: 超过这个滞后（秒）⇒ 1.30×（上限）
LAG_FULL_SPEED_S = 15.0
#: 滞后每多 1 秒，速度增加多少
SPEED_PER_LAG_S = 0.025
#: 速度下限 / 上限
SPEED_MIN = 1.0
SPEED_MAX = 1.30
#: 滞回：降速时 lag 必须低于这个值才回 1.0×
LAG_HYSTERESIS_S = 2.0
#: 相邻两句之间速度变化上限
MAX_STEP_CHANGE = 0.1


def speed_for_lag(lag_s: float,
                  prev_speed: float = 1.0,
                  lag_deadzone_s: float = LAG_DEADZONE_S,
                  lag_full_speed_s: float = LAG_FULL_SPEED_S,
                  speed_per_lag_s: float = SPEED_PER_LAG_S,
                  speed_min: float = SPEED_MIN,
                  speed_max: float = SPEED_MAX,
                  lag_hysteresis_s: float = LAG_HYSTERESIS_S,
                  max_step_change: float = MAX_STEP_CHANGE):
    """按 APP-042 的统一公式算「这句」的速度。

    🔴 **滞回**：只有在 `lag < lag_hysteresis_s` 时才回到 1.0×；
      否则保持上一个速度（哪怕新公式算出 1.0×）⇒ 避免在阈值附近抖动。

    🔴 **步长限制**：与上一句的速度差不超过 `max_step_change` ⇒ 听感平滑。

    参数
    ----
    lag_s : float
        「实际开播时刻 − 目标开播时刻」（秒）。**负值 = 提前**（不加速）。
    prev_speed : float
        上一句用的速度（用于滞回与步长限制）。第一句传 1.0。
    """
    try:
        lag = float(lag_s)
    except Exception:
        lag = 0.0
    if lag != lag:                       # NaN
        lag = 0.0

    if lag < lag_hysteresis_s:
        # 🛡️ 滞回：明确落后不多 ⇒ 回到 1.0×
        target = speed_min
    else:
        target = speed_min + (lag - lag_deadzone_s) * speed_per_lag_s
        if target < speed_min:
            target = speed_min
        if target > speed_max:
            target = speed_max

    # 🔴🔴 **滞回（降速方向）**：APP-042 明文「**降速时 lag < 2 s 才回到 1.0×**，
    #   避免来回抖动」。
    #   ⇒ 实现为「**任何降速动作都要求 lag < 2 s**」：
    #     - lag ≥ 2 s 时，公式算出的速度若**低于**上一句 ⇒ **保持上一句的速度**
    #       （这就是"没换人/没落后就一直保持"的语义 ⇒ 不抖动）；
    #     - 提速（lag 变大）**立即生效**（不然永远追不上）。
    try:
        p = float(prev_speed)
    except Exception:
        p = speed_min
    if p != p:
        p = speed_min
    if target < p and lag >= lag_hysteresis_s:
        target = p

    # 步长限制（相对上一句）
    lo = p - max_step_change
    hi = p + max_step_change
    if lo < speed_min:
        lo = speed_min
    if hi > speed_max:
        hi = speed_max
    if target < lo:
        target = lo
    if target > hi:
        target = hi
    return float(target)


def time_stretch(x, speed: float, sr=None,
                 frame_ms: float = 40.0,
                 search_ms: float = 10.0):
    """WSOLA 时间伸缩：**时长按 `speed` 变，音高不变**。

    参数
    ----
    x : 一维 np.ndarray（float32/float64，音频样本）
    speed : float
        > 1 ⇒ **变短**（加速播放）；== 1 ⇒ **原样返回**（逐位不变）。
    sr : int 或 None
        采样率（只用于把 ms 换算成样本数；不需要时传 None 也行）。
    frame_ms / search_ms : float
        分析帧长与搜索窗（毫秒）。

    返回
    ----
    np.ndarray（float32）—— 长度 ≈ `len(x) / speed`。
    """
    arr = np.asarray(x, dtype=np.float32).reshape(-1)
    n = arr.size
    if n == 0:
        return arr.copy()
    sp = float(speed) if speed is not None else 1.0
    if sp != sp or sp <= 0:
        return arr.copy()
    # 🔴 speed == 1 ⇒ **逐位原样返回**（不做任何变换 ⇒ 零风险）
    if abs(sp - 1.0) < 1e-9:
        return arr.copy()
    if n < 64:
        # 太短 ⇒ 直接线性重采样（听感上无所谓，且不会引入伪影）
        out_len = max(1, int(round(n / sp)))
        idx = np.linspace(0, n - 1, out_len)
        return np.interp(idx, np.arange(n), arr).astype(np.float32)

    ha = max(64, int(round((sr or 16000) * frame_ms / 1000.0)))   # 分析帧长
    ov = max(16, ha // 4)                                          # 重叠长度
    # 🔴🔴🔴 **步长关系（这里曾是一个真实缺陷）**：
    #   WSOLA 里**合成 hop**（输出侧相邻两帧的间距）与
    #   **分析 advance**（输入侧每次往后取多少）是**两个独立的量**：
    #     · 合成 hop `hs_out = ha − ov`（帧之间重叠 `ov` ⇒ OLA 连续）
    #     · 分析 advance `ha_in = hs_out × speed`
    #   ⇒ speed>1（加速）时，每输出 `hs_out` 个样本就**多消耗**输入
    #     ⇒ 输出变短 ⇒ 时长比 = 1/speed ✓
    #   ⚠️ 旧实现把两者混成一个 `hs = ha / speed`（且方向还是反的）
    #     ⇒ speed=1.25 时输出**没变短**（ratio=1.000）⇒「加速」根本没生效。
    hs_out = max(16, ha - ov)                                     # 合成 hop
    ha_in = max(16, int(round(hs_out * sp)))                       # 分析 advance
    search = max(4, int(round((sr or 16000) * search_ms / 1000.0)))

    win = np.hanning(ha).astype(np.float32)
    # 🔴 分配足够的输出缓冲：帧数 × 合成 hop + 一帧余量
    n_frames = max(1, int(math.ceil(max(0, n - ha) / float(ha_in))) + 1)
    out_len = max(1, min(n, int(round(n / sp))))
    total = n_frames * hs_out + ha + 4
    out = np.zeros(total, dtype=np.float32)
    norm = np.zeros(total, dtype=np.float32)

    # 归一化互相关用的「模板」（上一帧的重叠部分）
    template = None
    pos = 0                       # 当前分析帧起点
    out_pos = 0                   # 当前合成帧写入起点

    while pos + ha + search < n:
        # 🔴 在 [pos − search, pos + search] 里找与 template 最相似的位置
        best = pos
        if template is not None:
            lo = max(0, pos - search)
            hi = min(n - ha, pos + search)
            if hi > lo:
                t = template
                tt = float(np.dot(t, t))
                if tt > 1e-9:
                    seg = arr[lo:hi + ha]
                    # 用滑窗互相关（帧数不大 ⇒ 直接算）
                    c = np.correlate(seg, t, mode='valid')
                    # 归一化：用候选帧自身的能量做除数
                    energy = np.convolve(seg ** 2, np.ones(t.size, dtype=np.float32),
                                          mode='valid')
                    ncc = c / np.sqrt(np.maximum(energy, 1e-9) * tt)
                    k = int(np.argmax(ncc))
                    best = lo + k
        frame = arr[best:best + ha]
        if frame.size < ha:
            frame = np.pad(frame, (0, ha - frame.size))
        # overlap-add
        out[out_pos:out_pos + ha] += frame * win
        norm[out_pos:out_pos + ha] += win
        # 下一帧的模板 = 本帧的最后 ov 个样本
        template = arr[best + ha - ov: best + ha].copy()
        pos += ha_in
        out_pos += hs_out

    # 🔴 归一化（win^2 累加 ⇒ 补偿窗函数的功率损失）
    nz = norm > 1e-6
    out[nz] /= norm[nz]
    # 🔴🔴🔴 **不要把结果补齐到原长**（这里曾是一个真实缺陷）：
    #   旧实现末尾有 `if res.size < n: res = np.pad(res, (0, n - res.size))`
    #   ⇒ 输出被**拉回原始长度** ⇒ 「加速」在时长上**完全无效**
    #     （实测 ratio 恒为 1.000）。
    #   ⇒ 加速的定义就是「变短」⇒ 短就是对的 ⇒ 不补齐。
    res = out[:out_len]
    return res.astype(np.float32)


class StreamWSOLA:
    """🔴🔴🔴 APP-042：**流式** WSOLA（边合成边变速）。

    🔴 **为什么必须有流式版**（不能只用上面的整句 `time_stretch`）：
      worker 是**逐块流式合成**的（一块一块出音频）。
      若等**整句合成完**再做变速 ⇒ 首句出声延迟 = 整句合成时间
      （实测一句 4–8 s、RTF≈1 ⇒ 延迟 4–8 s）
      ⇒ **直接把滞后做大了** ⇒ 与 APP-042「追赶滞后」的目标**背道而驰**。
      ⇒ 必须：**边收块边变换边输出**（第一块到达即可开始出声）。

    🔴 **句内速度恒定**（APP-042「按句变速、句内不变」）：
      速度在**主进程提交时**就定好（随命令下发）⇒ 本类的 `speed`
      在构造后**不再改变** ⇒ 天然满足。

    🔴 **拼接不出现咔哒**：
      整句版 WSOLA 是「一帧接一帧 OLA」；流式版**沿用同一套帧结构**
      ⇒ 跨块边界时帧序列**连续**（块的边界不参与分段）
      ⇒ 不会出现「每块一个断点」的问题。

    用法：
      ```python
      st = StreamWSOLA(speed=1.2, sr=24000)
      for chunk in chunks:
          out = st.process(chunk)      # 可能为空（缓冲不足）
          ...播放 out...
      tail = st.flush()                # 收尾
      ```
    """

    def __init__(self, speed: float, sr: int = 16000,
                 frame_ms: float = 40.0, search_ms: float = 10.0):
        self.sp = float(speed) if speed else 1.0
        self.sr = int(sr or 16000)
        self.ha = max(64, int(round(self.sr * frame_ms / 1000.0)))
        self.ov = max(16, self.ha // 4)
        self.hs_out = max(16, self.ha - self.ov)
        self.ha_in = max(16, int(round(self.hs_out * self.sp)))
        self.search = max(4, int(round(self.sr * search_ms / 1000.0)))
        self.win = np.hanning(self.ha).astype(np.float32)
        # 输入缓冲（未处理的部分）及其**绝对**起始样本索引
        self._buf = np.zeros(0, dtype=np.float32)
        self._buf_start = 0
        self._pos = 0                 # 当前分析位置（绝对样本索引）
        # 输出累积（绝对索引从 0 开始）
        self._out = np.zeros(0, dtype=np.float32)
        self._norm = np.zeros(0, dtype=np.float32)
        self._out_pos = 0             # 下一帧写入位置（输出绝对索引）
        self._done = 0                # 已定稿（归一化并交付）的输出长度
        self._template = None         # 上一帧尾部 ov 个样本（模板）
        self._template_start = 0      # 模板在输入里的绝对起点
        self._n_frames = 0
        self._n_in = 0
        self._n_out = 0

    # -- 内部 -----------------------------------------------------------
    def _ensure_out(self, need):
        if self._out.size < need:
            pad = need - self._out.size
            self._out = np.concatenate(
                [self._out, np.zeros(pad, dtype=np.float32)])
            self._norm = np.concatenate(
                [self._norm, np.zeros(pad, dtype=np.float32)])

    def _drop_input(self):
        """丢弃已经用不到的输入（保留搜索窗需要的尾部）。"""
        keep_from = self._pos - self.search
        if self._template is not None and self._template.size:
            keep_from = min(keep_from, self._template_start)
        if keep_from <= self._buf_start:
            return
        cut = keep_from - self._buf_start
        self._buf = self._buf[cut:]
        self._buf_start = keep_from

    def _one_frame(self):
        """处理一帧；返回 True 表示成功处理了一帧。"""
        rel = self._pos - self._buf_start
        if self._buf.size - rel < self.ha + self.search:
            return False
        best = self._pos
        if self._template is not None and self._template.size:
            lo = max(self._buf_start, self._pos - self.search)
            hi = min(self._buf_start + self._buf.size - self.ha,
                     self._pos + self.search)
            if hi > lo:
                seg = self._buf[lo - self._buf_start:
                                hi - self._buf_start + self.ha]
                t = self._template
                tt = float(np.dot(t, t))
                if tt > 1e-9 and seg.size >= t.size:
                    c = np.correlate(seg, t, mode='valid')
                    energy = np.convolve(
                        seg.astype(np.float32) ** 2,
                        np.ones(t.size, dtype=np.float32), mode='valid')
                    ncc = c / np.sqrt(np.maximum(energy, 1e-9) * tt)
                    best = lo + int(np.argmax(ncc))
        frame = self._buf[best - self._buf_start:
                          best - self._buf_start + self.ha]
        if frame.size < self.ha:
            return False
        w = self._out_pos
        self._ensure_out(w + self.ha)
        self._out[w:w + self.ha] += frame * self.win
        self._norm[w:w + self.ha] += self.win
        # 下一帧的模板 = 本帧尾部 ov 个样本
        self._template_start = best + self.ha - self.ov
        self._template = self._buf[
            self._template_start - self._buf_start:
            self._template_start - self._buf_start + self.ov].copy()
        self._pos += self.ha_in
        self._out_pos += self.hs_out
        self._n_frames += 1
        return True

    def _take_done(self, upto):
        """把 [done, upto) 归一化并取出来。"""
        upto = min(int(upto), self._out.size)
        if upto <= self._done:
            return np.zeros(0, dtype=np.float32)
        seg = self._out[self._done:upto]
        nseg = self._norm[self._done:upto]
        good = nseg > 1e-6
        seg = seg.copy()
        seg[good] = seg[good] / nseg[good]
        seg[~good] = 0.0
        # 压缩已交付的部分
        self._out = self._out[upto:]
        self._norm = self._norm[upto:]
        self._done = 0
        self._out_pos -= upto
        self._n_out += int(seg.size)
        return seg.astype(np.float32)

    # -- 公开 -----------------------------------------------------------
    def process(self, chunk):
        """喂一块音频，返回**可以立刻输出**的音频（可能为空数组）。"""
        arr = np.asarray(chunk, dtype=np.float32).reshape(-1)
        self._n_in += int(arr.size)
        if self.sp <= 1.0:
            # 1.0× ⇒ **原样透传**（不缓冲、不变换 ⇒ 零风险）
            return arr.copy()
        if arr.size:
            self._buf = np.concatenate([self._buf, arr])
        # 帧序列在块边界**连续** ⇒ 逐帧处理
        while self._one_frame():
            pass
        # 交付「已经不会再被后续帧覆盖」的部分
        # （下一帧从 w+hs_out 开始 ⇒ 位置 < w 不会再被写）
        ready = self._out_pos - self.ha
        if ready < self._done:
            ready = self._done
        out = self._take_done(ready)
        self._drop_input()
        return out

    def flush(self):
        """收尾：把剩余输入补零处理成最后一帧，再交付尾部。"""
        if self.sp <= 1.0:
            return np.zeros(0, dtype=np.float32)
        if self._buf.size:
            pad = self.ha + self.search + 4
            self._buf = np.concatenate(
                [self._buf, np.zeros(pad, dtype=np.float32)])
        # 再处理若干帧，直到输入耗尽
        for _ in range(64):
            if not self._one_frame():
                break
        # 交付剩余全部（末尾不足一整帧的部分用窗衰减收尾）
        out = self._take_done(self._out_pos)
        return out.astype(np.float32)


def stretch_audio_file(in_path: str, out_path: str, speed: float, sr=None) -> bool:
    """把一个 wav 按 `speed` 变速落盘（验收脚本用；返回是否成功）。"""
    import wave
    try:
        with wave.open(in_path, 'rb') as w:
            nch = w.getnchannels()
            sw = w.getsampwidth()
            fs = w.getframerate()
            nframes = w.getnframes()
            raw = w.readframes(nframes)
        if sw != 2:
            return False
        a = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
        if nch > 1:
            a = a.reshape(-1, nch).mean(axis=1)
        out = time_stretch(a, speed, sr=fs)
        pcm = np.clip(out * 32768.0, -32768, 32767).astype('<i2')
        with wave.open(out_path, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(fs)
            w.writeframes(pcm.tobytes())
        return True
    except Exception:
        return False
