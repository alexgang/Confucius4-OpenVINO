# -*- coding: utf-8 -*-
"""🔴🔴🔴 APP-039 / APP-040：**ASR 说话人旁路**的接入适配层（App 侧）。

## 为什么需要这一层

ASR-029 交付了可 import 的接口（`shared/NOTICE_asr_to_app_speaker_api.md`）：

```python
from asr052_speaker_tracker_api import SpeakerTracker
tracker.feed(pcm16k, t_end_sec)            # ① 持续喂音频
res = tracker.on_final(seg_id, t_start, t_end)   # ② 定稿段 ⇒ spk
tracker.on_spk_update(seg_id, spk)          # ③ 标签晚到时补发
```

但 App 侧要接上它，还缺三件事：

1. 🔴 **ASR 侧的实现不在 git 仓库里**（在 `qwen3asr_06b/scripts/`，是 ASR
   模块的实验目录）⇒ **App 不能直接 import 它** ⇒ 本层负责**探测 + 加载**
   （找不到就**安静降级**，不崩、不拖慢）。
2. 🔴 **ASR 不给段级时间戳** ⇒ App 侧要自己维护「每段的时间区间」
   ⇒ 本层负责维护 `seg → (t_start, t_end)` 的映射。
3. 🔴 **App 的定稿口径与 ASR 的旁路要解耦** ⇒ 段区间由 App 在
   **切段那一刻**记录（App 自己的口径）⇒ 交给 tracker 做说话人判定。

## 🔴🔴🔴 三条纪律（ASR-029 通知 §4 明文）

1. **音色按句绑定到 spk，只在 `is_new_spk=True` 时取样一次**
   ⇒ 本层**不做**任何声纹计算，只**转交** `spk` 与 `clean_ranges`。
2. **克隆向量必须用 TTS 自己的 x-vector**
   ⇒ 本层**绝不**把 ASR 的嵌入向量传给 TTS ⇒ 只传 `clean_ranges`
   （**时间区间**）⇒ App 自己取 PCM、自己提向量。
3. **`spk=None` / `pending=True` 时不要等**
   ⇒ 按方案 A（ASR-024）：**TTS 不等说话人标签** ⇒ 立即返回，
   标签晚到时用 `on_spk_update` 补。

## 🔴 设备与线程纪律（ASR-026）

- 旁路模型设备 = **GPU.0**（`device='GPU.0'`、`seg_device='GPU.0'`）。
- **模块导入即限线程**（`OMP_NUM_THREADS` 等置 1）⇒ 不与 NPU 上的 TTS 抢核。
  ⚠️ 这条纪律**必须在 import ASR 那个模块之前**生效 ⇒ 本层在 import 前
  先设好环境变量。
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Optional, Tuple

# 🔴🔴🔴 ASR-026：**import ASR 模块之前**先限线程
#   （ASR 在 GPU.0 上跑时 torch 的 OpenMP 会吃掉 6.85 个核 ⇒ 把 NPU 上的
#     TTS 拖慢：TTS 的 CPU 时间 ×2.24、RTF 0.77 → 1.07）
for _v in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
           'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ.setdefault(_v, '1')

# ASR 模块的实验目录（**不在 git 仓库内**）
_ASR_SCRIPTS = r'C:\Users\Trekker-PTL\qwen3asr_06b\scripts'

_SR = 16000

# 🔴🔴🔴 §99（断链 A）：**ASR 侧判「段太短」的硬门槛**。
#   ASR-029 的 `SpeakerTracker.on_final` 里：
#     `if dur < self.min_dur_s:` ⇒ 返 `reason='too_short'`（或 `audio_not_buffered`）
#   而 `min_dur_s` 的**默认值 = 2.0 s**（ASR 侧构造参数，App 侧无法覆盖）。
#   ⇒ **App 传给旁路的段区间，长度必须 ≥ 2.0 s**，否则**永远拿不到 spk**
#      ⇒ 说话人旁路 100% 失效 ⇒ 每句都是预设 A。
# 🔴 借一点余量（2.5 s）⇒ 避免浮点边界把「刚好 2.0」判成太短。
SPAN_MIN_S = 2.5


def span_for_final(t_end: float, min_s: float = SPAN_MIN_S):
    """🔴🔴🔴 §99（断链 A）：**给出「这段」的区间**，长度不足就**往前借**。

    ## 为什么必须往前借

    ASR 侧 `on_final(t_start, t_end)` 会取 `t_start..t_end` 这段音频算嵌入，
    而 `dur < min_dur_s(=2.0)` ⇒ 直接返 `too_short` ⇒ **没有 spk**。
    ⇒ 而**定稿段常常只有几百毫秒到 1~2 s**（说话人是在句中换的）
    ⇒ 必须**向前借用**前面的音频，把区间补到 ≥ `min_s`。

    🔴 **借用是安全的**：借的是**同一个人在说话**的那一段之前的内容
       ⇒ 只用于**判断「这段是谁说的」**，不用于取 x-vector
       （取样用的是 ASR 自己给的 `clean_ranges`，**天然只含本人**）。

    ## 语义

    - `(t_end, t_end)`（旧口径）⇒ 区间长度 0 ⇒ **旁路必然失效**。
    - 返回 `(t0, t_end)`，其中 `t0 = max(0, t_end - min_s)`。
      ⚠️ `t_end` **保持不变**（不能往后借 ⇒ 往后是**未来**的音频，
      ASR 侧还没 buffer ⇒ 会变成 `audio_not_buffered` ⇒ 同样拿不到 spk）。
    - `t_end - t0 >= min_s` ⇒ 恒成立（除非 `t_end < min_s`，
      此时从 0 开始，长度 = `t_end`）。

    返回：`(t0, t_end)`。
    """
    try:
        te = float(t_end)
    except Exception:
        te = 0.0
    try:
        need = float(min_s)
    except Exception:
        need = SPAN_MIN_S
    if need <= 0:
        return (0.0, te)
    t0 = te - need
    if t0 < 0.0:
        t0 = 0.0
    return (t0, te)


class SpeakerBridge:
    """🔴🔴🔴 App 侧的**说话人旁路桥接器**（降级友好）。

    ## 生命周期

    1. `__init__`：只探测 ASR 模块在不在 ⇒ **不加载模型**（构造不阻塞启动）。
    2. `feed(pcm, t_end)`：持续喂音频（**失败就安静降级**）。
    3. `on_final(seg, t_start, t_end)`：App 定稿一段时调用
       ⇒ 返回 `{spk, spk_conf, clean_ranges, pending, reason}`。
    4. `on_spk_update(seg, spk)`：标签晚到时补发。

    ## 降级语义（**关键**）

    | 情况 | 行为 |
    |---|---|
    | ASR 模块不存在 | `available=False` ⇒ `on_final` 恒返 `spk=None` ⇒ **App 行为与改造前逐字一致** |
    | 模型加载失败 | 同上（`reason='models_not_ready'`） |
    | 该段不够干净 | `spk=None` + `reason='not_clean_speech'` ⇒ **不阻塞**（方案 A） |
    | 标签晚到 | `pending=True` ⇒ App 记下 seg ⇒ 之后用 `on_spk_update` 补 |

    🔴 **任何异常都不许打断音频循环** ⇒ 全部吞掉并降级。
    """

    def __init__(self, device: str = 'GPU.0', seg_device: str = 'GPU.0',
                 scripts_dir: str = _ASR_SCRIPTS,
                 thr: float = 0.35,
                 on_log=None):
        self._on_log = on_log or (lambda m: None)
        self.device = device
        self.seg_device = seg_device
        self._tracker = None
        self.available = False
        self.load_error = ''
        self.n_feed = 0
        self.n_final = 0
        self.n_pending = 0
        self.n_update = 0
        self._lock = threading.Lock()
        # seg -> (t_start, t_end)（**App 自己的口径**）
        self._seg_span = {}
        # seg -> 等待补标签的段（`pending=True`）
        self._pending = set()
        self._scripts_dir = scripts_dir
        self._thr = thr

    # ── ① 加载（惰性）──────────────────────────────────────────
    def _load(self) -> bool:
        """尝试加载 ASR 的 `SpeakerTracker`（**只加载一次**）。

        🔴 **不在 git 仓库内** ⇒ 用 `sys.path` 注入 + `importlib` 加载。
        🔴 失败 ⇒ **安静降级**（`available=False`）⇒ App 行为不变。
        """
        if self._tracker is not None:
            return True
        with self._lock:
            if self._tracker is not None:
                return True
            try:
                if self._scripts_dir not in sys.path:
                    sys.path.insert(0, self._scripts_dir)
                from asr052_speaker_tracker_api import SpeakerTracker
                self._tracker = SpeakerTracker(device=self.device,
                                               seg_device=self.seg_device,
                                               thr=self._thr)
                self.available = True
                self._log('说话人旁路已加载（ASR-029 接口）')
                return True
            except Exception as e:
                self.load_error = f'{type(e).__name__}: {e}'
                self.available = False
                self._log('说话人旁路不可用（降级：字幕无说话人标签）：%s'
                          % self.load_error)
                return False

    def _log(self, msg: str) -> None:
        try:
            self._on_log(msg)
        except Exception:
            pass

    # ── ② 喂音频 ───────────────────────────────────────────────
    def feed(self, pcm, t_end: Optional[float] = None) -> bool:
        """喂一段 16 kHz PCM（**失败就安静降级**）。

        ⚠️ `t_end` = 这段音频**结束**的时刻（全局时间轴，秒）
        ⇒ tracker 才能把缓冲对齐到全局时间轴 ⇒ `on_final` 的
        `t_start/t_end` 才对得上。
        """
        tr = self._tracker
        if tr is None:
            if not self._load():
                return False
            tr = self._tracker
        try:
            tr.feed(pcm, t_end)
            self.n_feed += 1
            return True
        except Exception as e:
            self._log('说话人旁路 feed 失败（忽略）：%s' % e)
            return False

    # ── ③ 定稿段 ───────────────────────────────────────────────
    def on_final(self, seg: int, t_start: float,
                 t_end: float) -> dict:
        """App 定稿一段 ⇒ 问 ASR「这句是谁说的」。

        返回 `{spk, spk_conf, clean_ranges, pending, reason, is_new_spk}`。

        🔴 **不等**（方案 A）：`pending=True` 时 `spk=None` ⇒ App 继续走
        「预设 A」⇒ 标签晚到时用 `on_spk_update` 补。
        """
        empty = dict(spk=None, spk_conf=None, clean_ranges=[], pending=False,
                     reason='unavailable', is_new_spk=False)
        with self._lock:
            self._seg_span[seg] = (float(t_start), float(t_end))
        tr = self._tracker
        if tr is None:
            if not self._load():
                return empty
            tr = self._tracker
        try:
            res = tr.on_final(seg_id=seg, t_start=float(t_start),
                              t_end=float(t_end))
        except Exception as e:
            self._log('说话人旁路 on_final 失败（忽略）：%s' % e)
            return empty
        self.n_final += 1
        out = dict(
            spk=res.get('spk'),
            spk_conf=res.get('spk_conf'),
            clean_ranges=list(res.get('clean_ranges') or []),
            pending=bool(res.get('pending')),
            reason=res.get('reason'),
            is_new_spk=bool(res.get('is_new_spk')))
        if out['pending']:
            with self._lock:
                self._pending.add(seg)
            self.n_pending += 1
        return out

    # ── ④ 标签晚到 ─────────────────────────────────────────────
    def on_spk_update(self, seg: int, spk: str) -> dict:
        """🔴 APP-040④：标签晚到时补标签。

        ⇒ 该句**先显示**（无标签），标签随后补上。
        """
        if not spk:
            return dict(known=False)
        tr = self._tracker
        if tr is None:
            return dict(known=False)
        try:
            res = tr.on_spk_update(seg_id=seg, spk=str(spk))
        except Exception as e:
            self._log('说话人标签补发失败（忽略）：%s' % e)
            return dict(known=False)
        self.n_update += 1
        with self._lock:
            self._pending.discard(seg)
        return dict(known=bool(res.get('known')),
                    spk=res.get('spk'),
                    spk_conf=res.get('spk_conf'))

    # ── ⑤ 取样区间 → PCM ───────────────────────────────────────
    def pcm_for_ranges(self, ranges, keep: Optional['np.ndarray'] = None,
                        max_s: float = 10.0, keep_t0: Optional[float] = None):
        """🔴 APP-039/040：**按 `clean_ranges` 取 PCM**（给 TTS 提 x-vector）。

        🔴 **取样区间只含该 spk 自己的干净语音** ⇒ **天然不会混入别人**
        ⇒ 这是「不渐变」的**结构性**保证（不是靠事后平滑）。

        ⚠️ `keep` = 主进程持有的**原始 PCM 环形缓冲**（16 kHz float32）
        ⇒ 本方法**不自己存音频**（避免第二份内存）。

        🔴🔴🔴 **§99 修真实缺陷（断链 E）**：**时间轴必须换算**。
          - `ranges`（= ASR 给的 `clean_ranges`）是**全局时间轴**的秒；
          - 而 `keep` 是**环形缓冲**，其下标 0 对应的是**缓冲起点**的时刻，
            **不是** t=0。
          - ⇒ 旧实现直接 `int(a * _SR)` 当下标 ⇒ **整体错位**
            ⇒ 取到的根本不是这个人的语音（长会话越错得离谱）。
          - ⇒ 修法：**新增 `keep_t0`**（缓冲起点在全局时间轴上的时刻）
            ⇒ 下标 = `(t - keep_t0) * _SR`。
          - ⚠️ `keep_t0` **不传** ⇒ 退化到旧口径（t=0）
            ⇒ **保持向后兼容**（老调用方行为逐字不变）。
        """
        if keep is None or not ranges:
            return None
        try:
            import numpy as np
            buf = np.asarray(keep, dtype=np.float32).reshape(-1)
            if buf.size == 0:
                return None
            base = 0.0 if keep_t0 is None else float(keep_t0)
            parts = []
            for a, b in ranges:
                # 🔴 **相对缓冲起点**的下标（§99 修：原为 `a * _SR`）
                i = max(0, int(round((float(a) - base) * _SR)))
                j = min(buf.size, int(round((float(b) - base) * _SR)))
                if j > i:
                    parts.append(buf[i:j])
            if not parts:
                return None
            out = np.concatenate(parts, axis=0).reshape(-1)
            max_n = int(max_s * _SR)
            if out.size > max_n:
                out = out[-max_n:]
            return out
        except Exception:
            return None

    # ── ⑥ 会话结束 ─────────────────────────────────────────────
    def reset(self) -> None:
        with self._lock:
            self._seg_span.clear()
            self._pending.clear()
        self.n_feed = 0
        self.n_final = 0
        self.n_pending = 0
        self.n_update = 0

    def stats(self) -> dict:
        with self._lock:
            n_span = len(self._seg_span)
            n_pend = len(self._pending)
        return dict(available=bool(self.available),
                    load_error=self.load_error,
                    device=self.device,
                    n_feed=int(self.n_feed),
                    n_final=int(self.n_final),
                    n_pending=int(n_pend),
                    n_update=int(self.n_update),
                    n_seg_span=int(n_span))


__all__ = ['SpeakerBridge']
