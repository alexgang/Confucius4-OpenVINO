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

# 🔴🔴🔴 APP-047 / ASR-031 §11.3：**「本段没有说话人标签」的降级原因集合**。
#   ASR 侧新增 `reason='embed_shape_out_of_range'`（嵌入输入 T 维超出编译期
#   形状范围 ⇒ 编码器抛 `ValueError` ⇒ API 层降级为该 reason，并带
#   `embed_error` 字段）。**不截断**（截断会改变向量 ⇒ 聚类失真）。
#
#   ⇒ App 侧必须把它**与既有的 'not_clean_speech' / 'overlap' 同类处理**：
#   **该段没有标签 ⇒ 沿用上一句音色 / 预设音色**（方案 A：TTS 不等标签）。
#
#   ⚠️ 正常情况下**不会触发**：生产段长上限 20 s ⇒ 1998 帧 < 2048（ASR 侧
#   `EMBED_RANGE_HI=2048`）⇒ 只有部署方把分段上限调到 > 20.48 s 才会出现。
NO_LABEL_REASONS = frozenset((
    'not_clean_speech',        # 段内干净语音占比不足
    'overlap',                 # 重叠语音占比过高
    'too_short',               # 段太短（< ASR 的 min_dur_s）
    'audio_not_buffered',      # 音频还没 buffer 够
    'seg_pending',             # 旁路分段尚未覆盖到这一段
    'embed_shape_out_of_range',  # 🆕 APP-047：嵌入形状超界 ⇒ 该段无标签
    'models_not_ready',        # 模型缺失（旁路整体关闭）
    'unavailable',             # 桥接层不可用
))


def reason_is_no_label(reason) -> bool:
    """🔴 APP-047：判断某个 `reason` 是否属于「**本段无标签**」。

    ⇒ 调用方据此**沿用上一句音色 / 预设音色**，**不重试、不等待**
    （方案 A：TTS 不等说话人标签）。
    """
    if not reason:
        return False
    return str(reason) in NO_LABEL_REASONS


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
                 scripts_dir: str = None,
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
        # 🔴 APP-047：因「本段无标签」而沿用上一句音色的次数（诊断用）
        self.n_no_label = 0
        self._lock = threading.Lock()
        # seg -> (t_start, t_end)（**App 自己的口径**）
        self._seg_span = {}
        # seg -> 等待补标签的段（`pending=True`）
        self._pending = set()
        self._thr = thr
        # 🔴🔴🔴 APP-044：**优先用包内资产**（客户机形态）
        #   ⇒ 包内 `app/asr_spk/`（ASR 接口代码）+ `models/spk/`（两个 OV IR）
        #   ⇒ 研发机（无包内资产）⇒ 回退到 ASR 的实验目录。
        #   ⚠️ 关键：**不改 ASR 源码一个字节** —— `SpeakerTracker.__init__`
        #     接受 `seg_ir` / `wes_ir` 参数 ⇒ 直接把包内 IR 路径传进去即可。
        #     （实测见 `results/app/app157_app044_portable_load_probe.py` 9/9 PASS）
        self._assets = None
        self._scripts_dir = scripts_dir or _ASR_SCRIPTS
        try:
            import speaker_assets
            self._assets = speaker_assets.resolve()
            if self._assets.get('ok'):
                self._scripts_dir = self._assets['scripts_dir']
                self._log('说话人资产（包内）：%s；%s'
                          % (self._assets['wes_note'],
                             self._assets['seg_note']))
            else:
                # 🔴🔴🔴 研发机回退**必须先探测目录是否真的存在**
                #   ⇒ 否则在**客户机**上（ASR 实验目录不存在）仍会走回退分支
                #      ⇒ `_load()` 因找不到模块而失败（虽然不会崩），
                #      但 `available` 的语义会含混。
                #   ⇒ 客户机形态：包内无资产 ⇒ **旁路关闭** + GUI 提示
                #      （APP-044 明文：「模型文件缺失时，旁路自动关闭，
                #        GUI 提示"说话人识别不可用"，其他功能不受影响」）。
                if os.path.isdir(self._scripts_dir) and os.path.isfile(
                        os.path.join(self._scripts_dir,
                                     'asr052_speaker_tracker_api.py')):
                    self._log('包内无说话人资产（%s）⇒ 回退到研发机 ASR 目录：%s'
                              % (self._assets.get('reason', ''),
                                 self._scripts_dir))
                else:
                    self._scripts_dir = ''
                    self._log('说话人识别不可用：%s'
                              % self._assets.get('reason', '缺少说话人资产'))
        except Exception as e:
            self._assets = None
            self._log('说话人资产探测异常（忽略）：%s' % e)

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
                # 🔴 APP-044：包内无资产且无研发机回退 ⇒ 直接降级
                #   （不 import、不探测，避免无谓的文件系统访问）
                if not self._scripts_dir:
                    self.load_error = 'no_speaker_assets'
                    self.available = False
                    self._log('说话人识别不可用（缺少说话人资产）')
                    return False
                if self._scripts_dir not in sys.path:
                    sys.path.insert(0, self._scripts_dir)
                from asr052_speaker_tracker_api import SpeakerTracker
                # 🔴🔴🔴 APP-044：**把包内 IR 路径传进去**
                #   （ASR 侧 `SpeakerTracker.__init__` 支持 `seg_ir`/`wes_ir`）
                #   ⇒ 不需要改 ASR 源码一个字。
                #   ⚠️ 研发机回退时**不传** ⇒ 用 ASR 自己的默认（硬编码本机路径）。
                kwargs = dict(device=self.device, seg_device=self.seg_device,
                              thr=self._thr)
                if self._assets and self._assets.get('ok'):
                    kwargs['seg_ir'] = self._assets['seg_ir']
                    kwargs['wes_ir'] = self._assets['wes_ir']
                self._tracker = SpeakerTracker(**kwargs)
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
        # 🔴🔴🔴 APP-047：ASR 侧新增 `embed_error` 字段（形状超界时）。
        #   ⇒ 透传给调用方（**可观测，不静默丢段**）。
        if res.get('embed_error'):
            out['embed_error'] = str(res.get('embed_error'))
        # 🔴 APP-047：`reason='embed_shape_out_of_range'` ⇒ 该段**没有标签**
        #   ⇒ 与 'not_clean_speech' 同类（沿用上一句音色），**不等待**。
        if out['pending']:
            with self._lock:
                self._pending.add(seg)
            self.n_pending += 1
        elif not out['spk'] and reason_is_no_label(out.get('reason')):
            self.n_no_label += 1
        return out

    # ── ④ 标签晚到 ─────────────────────────────────────────────
    def retry_pending(self, max_n: int = 8) -> list:
        """🔴🔴🔴 §100（断链 J）：**重新问一遍 ASR**（拿晚到的标签）。

        ## 断链 J 的根因（实测）

        ASR 侧 `SpeakerTracker.on_final()` 在旁路分段**还没覆盖到该段**时
        返回 `spk=None` + `pending=True`，并把该 seg 存进 `self._pending`。
        ⇒ 标签「稍后由 `on_spk_update` 补发」（ASR 侧文档原话）。

        🔴 **但实测**：`on_spk_update` **没有任何调用方** ——
        ASR 侧的 `_pending` 只在 `on_spk_update` 里被 `pop`，
        而 ASR 模块自己**从不调用它** ⇒
        ⇒ **`pending=True` 的段，标签**永远**不会到** ⇒
        ⇒ APP-040④「spk 晚到时用 spk_update 补标签」**客观做不了**。

        ## 修法（App 侧，**不代改 ASR**）

        ASR 侧 `on_final()` 的判定依赖 `_seg_frames`，而它**随 `feed()` 推进**
        ⇒ ⇒ **过一段时间再问一次同一个 seg**，就能拿到标签。
        ⇒ 所以 App 侧把「待补标签的 seg」记下来，**每轮轮询重试一次**。

        ⚠️ **不阻塞**（守 APP-034 方案 A：「TTS 不等说话人标签」）：
        重试在**后台轮询**里做 ⇒ 字幕/翻译/语音**不为**说话人识别增加延迟。

        ⚠️ **不覆盖已定稿的标签**：只有 `spk` 真的拿到了才返回。

        返回：`[(seg, spk, spk_conf), ...]`（本次**新拿到**标签的段）。
        """
        out = []
        with self._lock:
            pending = sorted(self._pending)
        if not pending:
            return out
        tr = self._tracker
        if tr is None:
            return out
        for seg in pending[:max(1, int(max_n))]:
            try:
                with self._lock:
                    span = self._seg_span.get(seg)
                if span is None:
                    continue
                t_start, t_end = span
                res = tr.on_final(seg_id=seg, t_start=float(t_start),
                                  t_end=float(t_end))
            except Exception as e:
                self._log('说话人标签重试失败（忽略）：%s' % e)
                continue
            spk = (res or {}).get('spk')
            if not spk:
                # 仍拿不到 ⇒ 继续挂着（下一轮再试）
                continue
            # ✅ 拿到了 ⇒ 出队（不再重试这个 seg）
            with self._lock:
                self._pending.discard(seg)
            self.n_update += 1
            out.append((seg, str(spk), (res or {}).get('spk_conf')))
        return out

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
        self.n_no_label = 0

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
                    n_no_label=int(self.n_no_label),
                    n_seg_span=int(n_span))


__all__ = ['SpeakerBridge']
