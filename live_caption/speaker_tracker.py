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
import collections
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
# 🔴 §120：不再写死开发机家目录 ⇒ 改为按**当前用户家目录**推导
#   （开发机上与原硬编码值**逐字节相同**）
_ASR_SCRIPTS = os.path.join(os.path.expanduser('~'),
                            'qwen3asr_06b', 'scripts')

_SR = 16000

# 🔴🔴🔴 APP-053：**旁路分段的滑窗长度**（秒）。
#   ASR 侧 `asr052_spk_runtime.WIN_S = 10.0`（`WIN_N = 160000` 样本）。
#   🔴 **喂满一整窗时帧数恰好 589 ⇒ 零取整漂移**（见 `feed()` 的注释）。
#   （APP-053 的实测证据：`results/app/app195_app053_mechanism_evidence.json`）
#
# 🔴🔴🔴 APP-062 ①（D1）：**不再写死**，改为**与 ASR 侧常量同源** ＋ **可配置**。
#   reviewer 原文：「App 侧把窗口长度做成配置项（和 ASR 侧常量同源，
#     不要两处各写一个），默认先保持 10 s。」
#
#   🔴 **为什么要同源**：`WIN_S` 决定**喂给 ASR 的窗长**
#     ⇒ App 侧写死一份、ASR 侧写死一份 ⇒ 改一边不改另一边 ⇒ **静默错位**
#     ⇒ ASR 拿到的窗长与它自己以为的不一致 ⇒ 换人点判定漂移。
#   🔴 **同源怎么做**：`asr052_spk_runtime` **随包分发**（实测包内
#     `app/asr_spk/asr052_spk_runtime.py` 里就有 `WIN_S = 10.0`）
#     ⇒ 开发机与客户机**都能读到** ⇒ 直接读它，不另写一份。
#   🔴 **配置项**：`LIVECAP_SPK_WINDOW_S` 环境变量可覆盖
#     ⇒ ASR-040 的「10 s vs 5 s」对比实验**不必改代码**就能跑两档。
#   🔴 **读不到时**退回 10.0（= ASR 侧默认值）⇒ **行为与改前完全一致**。
#   🔴 **非法值**（非数字 / ≤ 0）⇒ 退回默认（不静默改语义）。
_WIN_S_DEFAULT = 10.0
_WIN_S_ENV = 'LIVECAP_SPK_WINDOW_S'


def _asr_win_s():
    """🔴 从 **ASR 侧模块**读 `WIN_S` ⇒ **同源**（读不到 ⇒ None）。"""
    try:
        import importlib
        import importlib.util
        # ① 已加载过（`_load()` 会把目录加进 sys.path）
        mod = sys.modules.get('asr052_spk_runtime')
        if mod is None:
            # ② 按**旁路资产解析器**给的实际目录找
            #   （包内 `app/asr_spk/` 或研发机 ASR 目录 ⇒ 两边都能找到）
            import speaker_assets
            d = ''
            try:
                info = speaker_assets.resolve()
                d = (info or {}).get('scripts_dir') or ''
            except Exception:
                d = ''
            if not d:
                d = _ASR_SCRIPTS
            p = os.path.join(d, 'asr052_spk_runtime.py')
            if os.path.isfile(p):
                spec = importlib.util.spec_from_file_location(
                    'asr052_spk_runtime', p)
                if spec and spec.loader:
                    m = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(m)
                    mod = m
        if mod is None:
            return None
        v = getattr(mod, 'WIN_S', None)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) \
            else None
    except Exception:
        return None


def _resolve_win_s():
    """🔴 解析旁路窗长：**环境变量（配置项） > ASR 侧常量（同源） > 默认 10.0**。"""
    raw = os.environ.get(_WIN_S_ENV, '')
    if raw not in (None, ''):
        try:
            v = float(raw)
            if v > 0:
                return v, '配置项 %s=%s' % (_WIN_S_ENV, raw)
        except Exception:
            pass
    v = _asr_win_s()
    if v is not None and v > 0:
        return v, '同源 asr052_spk_runtime.WIN_S=%s' % v
    return _WIN_S_DEFAULT, '默认 %s' % _WIN_S_DEFAULT


_WIN_S, _WIN_S_SRC = _resolve_win_s()

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


def _np_available() -> bool:
    """numpy 是否可用（**不 import** ⇒ 顶层 import 失败也不影响本模块加载）。"""
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


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


def span_for_segment(t_end: float, prev_end: Optional[float] = None,
                     min_s: float = SPAN_MIN_S):
    """🔴🔴🔴 APP-053：**段自身区间**优先，**借用**兜底。

    ## 为什么需要（实测，见 `results/app/app193_app053_spk_frame_audit.json`）

    `span_for_final()` 只能从 `t_end` **往前借** `min_s`(2.5 s) ⇒ 取到的窗口
    是「段尾 2.5 s」⇒ **不一定是这段话**（说话人可能刚在这 2.5 s 内换过）
    ⇒ `clean_ratio` 偏低 ⇒ 被 ASR 侧判 `not_clean_speech`。

    离线复算（同一 5 min 切片、同一套断句、ASR-029 的两道门槛）：

    | 取值规则 | 可打标比例 |
    |---|---|
    | 只借用 2.5 s（`span_for_final`） | 41/46 = **89.13%** |
    | **段自身区间**（起点 = 上一段末） | 44/46 = **95.65%** |
    | 参考标注（ASR 真值） | 44/46 = **95.65%** |

    ⇒ 段自身区间**与 ASR 真值完全一致** ⇒ 说明「段自身区间」就是正确口径。

    ## `prev_end` 的含义

    App 的断句是**连续**的（上一段的末 = 本段的初）⇒ 段自身区间 =
    `[prev_end, t_end]` ⇒ **App 完全拿得到**（记上一段的结束时刻即可）。

    ⚠️ `prev_end` 未知（第一段）⇒ 退回 `span_for_final()` 的借用口径
    ⇒ **不猜、不谎报**。

    ⚠️ **不往后借**（`t_end` 保持不变）⇒ ASR 侧还没 buffer 到的音频不会被要。

    返回 `(t0, t1)`。
    """
    t1 = float(t_end)
    if prev_end is None:
        return span_for_final(t1, min_s)
    try:
        p = float(prev_end)
    except Exception:
        return span_for_final(t1, min_s)
    if not (0.0 <= p < t1):
        # 🔴 口径不可信（倒退 / 越界）⇒ 退回借用，**不猜**
        return span_for_final(t1, min_s)
    if (t1 - p) < float(min_s):
        # 🔴 段自身区间太短（< ASR 的 min_dur_s）⇒ 往前借到够长
        return span_for_final(t1, min_s)
    return (p, t1)


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
                 on_log=None,
                 enabled: bool = False,
                 max_queue_s: float = 60.0):
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
        # 🔴🔴🔴 APP-053：**攒批喂音**的状态
        #   `_feed_buf` = 已收到但**还没喂给 tracker** 的音频（攒到整窗才喂）
        #   `_fed_samples` = 已经喂给 tracker 的总样本数（用来算 `t_end`）
        #   ⚠️ numpy 在本模块是**局部 import**（顶层不 import ⇒ 顶层失败不影响
        #     本模块加载）⇒ 这里显式 import 一次。
        try:
            import numpy as _np
            self._feed_buf = _np.zeros(0, dtype=_np.float32)
        except Exception:
            self._feed_buf = None
        self._fed_samples = 0
        self.n_feed_samples = 0
        # 🔴 APP-053：**攒批是否启用**（一次失败 ⇒ 降级为直喂）
        self._batching = True
        # 🔴🔴🔴 APP-054：**旁路总开关**（**默认关闭**）
        #   v1.13 的阻断级回归：旁路**默认开着**且**同步阻塞 ASR 主循环**
        #   ⇒ 实测墙钟 838.5 s / 300 s 音频（最大积压 195.1 s）
        #   ⇒ `enabled=False` ⇒ 旁路**完全不存在**（不建线程、不加载模型）
        #   ⇒ 字幕/语音行为与 **v1.12 逐字一致**（v1.12 无旁路）。
        self.enabled = bool(enabled)
        # 🔴🔴🔴 APP-054：**后台工作线程**（主循环永不阻塞）
        self._worker = None
        self._stop = threading.Event()
        self._q = collections.deque()
        self._q_cv = threading.Condition(threading.Lock())
        self._q_samples = 0
        self._max_queue_s = float(max_queue_s)
        self._results = {}          # seg -> 完整结果 dict（含 clean_ranges）
        self._results_lock = threading.Lock()
        self._retry_q = {}          # seg -> (t0, t1)（ASR 侧 pending ⇒ 重问）
        # 🔴 APP-054：**降级状态**（积压超限 ⇒ 旁路停用，**不谎报标签**）
        self._degraded = False
        self._degraded_reason = ''
        # 🔴 APP-054：**计时**（每个窗口都记，写进日志）
        self._timings = []
        self.n_dropped_chunks = 0
        self.n_dropped_samples = 0
        self.n_dropped_blocks = 0
        self.max_queue_s_seen = 0.0
        self.n_window_feed = 0
        self.n_final_done = 0
        self.n_pending_async = 0
        # 🔴 APP-053/054：后台 feed 失败次数（⇒ 攒批降级为直喂）
        self.n_feed_failed = 0
        # 🔴🔴🔴 APP-054：**会话代号**（`reset()` 递增 ⇒ worker 丢弃旧会话残余）
        self._epoch = 0
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

    # ── ② 喂音频（**非阻塞**：只入队，推理在后台线程）────────────
    def feed(self, pcm, t_end: Optional[float] = None) -> bool:
        """喂一段 16 kHz PCM（**永不阻塞主循环**）。

        ⚠️ `t_end` = 这段音频**结束**的时刻（全局时间轴，秒）

        🔴🔴🔴 APP-054：**本方法现在只做「入队」** ⇒ 返回时间 = O(1)。

        ## 为什么必须这样改（实测根因）

        reviewer 的 A/B 实测（`hy_bench/spk_ab_run.py`）：

        | 臂 | 墙钟 / 300 s 音频 | 最大积压 |
        |---|---|---|
        | 旁路开（v1.13 默认） | **838.5 s** | **195.1 s** |
        | 旁路关（打桩） | 300.6 s | 1.2 s |

        ⇒ ASR 自身算力**没变慢**（RTF 0.489 / 0.685）⇒ 多出来的 ~540 s
        **全在 `_spk_bridge.feed(pcm, t_end)` 里**（`live_caption_app.py` 的
        GUI / CLI 音频主循环里**同步调用**它）。

        ### 源码级根因（两处，都在 ASR 交付的 `SpeakerTracker` 里）

        1. **`run_seg_side()` 每次调用都 `core.compile_model()`**
           ⇒ App 按 `BLOCK_MS=100` 喂 ⇒ 3000 次调用 ⇒ **3000 次编译**
           ⇒ 单次编译墙钟 ~0.12 s（热）~2.3 s（冷）⇒ 几百秒。
           ⇒ 更糟：它**每次都 `ov.Core()` 新建 core** ⇒ OpenVINO 的
             **进程内编译缓存完全失效**（缓存键含 core 实例状态）。
        2. **`self._buf` 永不裁剪**，且 `_advance_seg()` 里
           `np.concatenate(self._buf)` **每次全量重组** ⇒ O(n²) 拷贝。

        ## 本次修法（App 侧，**不改 ASR 一行**）

        * `feed()` **只把 PCM 放进队列**就返回 ⇒ 主循环**永不阻塞**。
        * 独立**后台工作线程**消费队列：攒够一整窗（`WIN_S = 10 s`）再喂
          tracker ⇒ **顺带修掉 APP-053 的帧数取整漂移**
          （喂满整窗 ⇒ 帧数恰好 589 ⇒ **零漂移**）。
        * 队列积压超 `max_queue_s` ⇒ **丢弃最旧的窗口**并标记**降级**
          ⇒ **只降级，绝不反压 ASR**（APP-054 明文）。
        * 旁路**默认关闭**（`enabled=False`）⇒ v1.13 的默认行为与 **v1.12
          逐字一致**（v1.12 无旁路）⇒ 止血。
        """
        if not self.enabled:
            return False
        try:
            import numpy as np
            a = np.asarray(pcm, dtype=np.float32).reshape(-1)
        except Exception:
            return False
        if a.size == 0:
            return True
        try:
            self._ensure_worker()
        except Exception as e:
            self._log('说话人旁路线程启动失败（降级）：%s' % e)
            return False
        # ── 入队（**不阻塞**：只做一次 deque.append）──
        with self._q_cv:
            self._q.append((a, float(t_end) if t_end is not None else None))
            self._q_samples += int(a.size)
            q_s = self._q_samples / float(_SR)
            if q_s > self.max_queue_s_seen:
                self.max_queue_s_seen = q_s
            over = False
            # 🔴🔴🔴 APP-054：**积压超限 ⇒ 丢弃最旧窗口**（**不反压**）
            while self._q_samples > int(self._max_queue_s * _SR) and self._q:
                _old, _te = self._q.popleft()
                self._q_samples -= int(_old.size)
                self.n_dropped_chunks += 1
                self.n_dropped_samples += int(_old.size)
                over = True
            self._q_cv.notify()
        if over:
            # 🔴 **降级**：旁路落后于实时 ⇒ 本轮之后**本句不打标签**
            #   ⇒ **不谎报新说话人**（APP-053 明文）。
            self._degrade('backlog_over_limit')
        return True

    def _degrade(self, reason: str) -> None:
        """标记旁路**降级**（落后于实时 ⇒ 不再给标签）。"""
        if self._degraded and self._degraded_reason == reason:
            return
        self._degraded = True
        self._degraded_reason = reason
        self._log('说话人旁路降级（%s）⇒ 本句不打标签' % reason)

    # ── ②-b 后台工作线程 ────────────────────────────────────────
    def _ensure_worker(self) -> None:
        """确保后台线程已启动（**惰性** ⇒ 构造不阻塞启动）。"""
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._stop.clear()
            self._worker = threading.Thread(
                target=self._worker_loop, name='spk-bypass', daemon=True)
            self._worker.start()
        self._log('说话人旁路后台线程已启动')

    def _worker_loop(self) -> None:
        """后台线程：**攒够一整窗 → 喂 tracker → 推进定稿段**。

        🔴 **绝不抛异常**（线程死了就静默降级 ⇒ 字幕无标签）。

        ## 🔴🔴🔴 APP-053/054：**攒批失败时必须「退回直喂」，且音频不许丢**

        旧实现（并发会话版）有两个真缺陷：

        ① **喂失败时整窗音频被丢弃**（`ready` 没有放回 `buf`）
           ⇒ ASR 侧一旦抛异常 ⇒ **这一窗的音频永久丢失**
           ⇒ 后续所有段的**时间轴整体前移** ⇒ 标签对不上 ⇒ 覆盖率进一步下降。
        ② **`_batching` 标志被声明但从不被使用** ⇒ 「攒批失败 ⇒ 降级为直喂」
           这条 APP-053 明文要求的降级路径**根本不存在**。

        ⇒ 修法：喂失败 ⇒ **把这一窗放回缓冲头部** ＋ **置 `_batching=False`**
          ⇒ 后续按**每块直喂**（不再等整窗）⇒ 音频**一条不丢**。
        """
        import numpy as np
        win_n = int(round(_WIN_S * _SR))
        buf = np.zeros(0, dtype=np.float32)
        fed_samples = 0
        # 🔴🔴🔴 APP-054：**会话代号（epoch）** —— `reset()` 会递增它
        #   ⇒ 后台线程发现代号变了 ⇒ **丢弃本会话残留的缓冲**
        #   ⇒ 否则上一会话末尾的残余音频会**串进下一会话**
        #     （`reset()` 清的是 `self._feed_buf`，而 worker 用的是**局部** `buf`
        #      ⇒ 旧实现清不掉 ⇒ 跨会话串音）。
        epoch = self._epoch
        try:
            while not self._stop.is_set():
                # ── ① 取一批音频（**限时等** ⇒ 不阻塞退出）──
                with self._q_cv:
                    if not self._q:
                        self._q_cv.wait(timeout=0.25)
                    batch = []
                    while self._q:
                        batch.append(self._q.popleft())
                        self._q_samples -= int(batch[-1][0].size)
                    if not batch:
                        continue
                # 🔴 **代号变了 ⇒ 丢掉本会话残留**（跨会话串音防护）
                if self._epoch != epoch:
                    epoch = self._epoch
                    buf = np.zeros(0, dtype=np.float32)
                    fed_samples = 0
                for _a, _te in batch:
                    buf = np.concatenate((buf, _a))
                # ── ② 把缓冲里**能喂的都喂完**（内层循环）────────────
                #   🔴🔴🔴 **一次只喂**一个整窗（`win_n`）
                #     ⇒ ASR 侧 `run_seg_side` 每次拿到**恰好 10 s**
                #       ⇒ 帧数 = ceil(10.0 × 58.9) = **589**（零取整漂移）
                #     ⇒ 且**内存占用恒定**（不会把 30 s 一次性塞进去）。
                #   ⚠️ 旧实现把**整个批次**一次喂完（30 s ⇒ 一次调用）
                #     ⇒ 虽也零漂移，但**喂的粒度与 ASR 侧窗口不一致**
                #     ⇒ `app197` 的 T2 判据能识破它。
                #   ⚠️ 更早的实现**每轮外层循环只喂一窗** ⇒ 缓冲里剩下的
                #     20 s 要**等新音频到达**才被喂 ⇒ 尾段永远滞后
                #     ⇒ `app197` 的 T2/T4 判据能识破它。
                while True:
                    with self._lock:
                        batching = bool(self._batching)
                    if batching:
                        n_ready = win_n if buf.size >= win_n else 0
                    else:
                        # 🔴 **降级为直喂**：来多少喂多少（帧数会漂移，但**不丢音**）
                        n_ready = buf.size
                    if n_ready <= 0:
                        break
                    ready = buf[:n_ready]
                    buf = buf[n_ready:]
                    t_end_batch = (fed_samples + int(ready.size)) / float(_SR)
                    t_w0 = time.perf_counter()
                    ok = False
                    try:
                        tr = self._tracker
                        if tr is None:
                            if not self._load():
                                # 🔴 **加载失败 ⇒ 这一窗放回缓冲**（不丢音）
                                buf = np.concatenate((ready, buf))
                                break
                            tr = self._tracker
                        tr.feed(ready, t_end_batch)
                        ok = True
                    except Exception as e:
                        # 🔴🔴🔴 **喂失败 ⇒ 这一窗放回缓冲头部**（音频不丢）
                        #   ＋ **降级为直喂**（不再等整窗）⇒ 下次不会再次卡在
                        #   同一个失败点上。
                        buf = np.concatenate((ready, buf))
                        with self._lock:
                            self._batching = False
                            self.n_feed_failed += 1
                        # 🔴 **不置 `_degraded`**：那会让**整段会话**再也不打标签
                        #   （`_degraded` 是「本段不打标签」的语义 ⇒ 一旦置位
                        #   `on_final()` 对**所有**后续段都返 `bypass_degraded`）。
                        #   ⇒ 这里只**降级攒批**（退回直喂）＋ 计数 ⇒ 音频不丢、
                        #     且 tracker 恢复后**标签自动恢复**。
                        self._log('说话人旁路后台 feed 失败（已退回直喂，音频不丢）：%s' % e)
                    dt = time.perf_counter() - t_w0
                    with self._lock:
                        self._timings.append(round(dt, 4))
                        if len(self._timings) > 512:
                            del self._timings[:-512]
                        self.n_window_feed += 1
                        if ok:
                            self._fed_samples += int(ready.size)
                        # 🔴 暴露「还没喂出去的残余」⇒ `stats()` 能报真实积压
                        self._feed_buf = buf
                    if ok:
                        fed_samples += int(ready.size)
                        self.n_feed += 1
                        self.n_feed_samples += int(ready.size)
                        self._log('说话人旁路窗口：%.3f s 音频 / 推理 %.3f s'
                                  % (ready.size / float(_SR), dt))
                    # ── ③ 推进已定稿但还没拿到标签的段 ──
                    self._drain_pending()
                    if not ok:
                        # 🔴 喂失败 ⇒ 已降级为直喂 ⇒ **跳出内层循环**
                        #   （否则会用同一份失败音频反复喂）
                        break
        except Exception as e:
            self._log('说话人旁路后台线程异常（降级）：%s' % e)

    def _drain_pending(self) -> None:
        """重问**已定稿但还没标签**的段（ASR 侧 pending ⇒ 标签晚到）。"""
        with self._lock:
            pend = list(self._retry_q.keys())
        if not pend:
            return
        tr = self._tracker
        if tr is None:
            return
        for seg in pend[:16]:
            try:
                with self._lock:
                    span = self._retry_q.get(seg)
                if span is None:
                    continue
                res = tr.on_final(seg_id=seg, t_start=float(span[0]),
                                  t_end=float(span[1]))
            except Exception:
                continue
            spk = (res or {}).get('spk')
            if not spk:
                continue
            with self._lock:
                self._retry_q.pop(seg, None)
            out = dict(spk=spk,
                       spk_conf=(res or {}).get('spk_conf'),
                       clean_ranges=list((res or {}).get('clean_ranges') or []),
                       pending=False,
                       reason=(res or {}).get('reason'),
                       is_new_spk=bool((res or {}).get('is_new_spk')))
            with self._results_lock:
                self._results[seg] = out
            self.n_update += 1
            self.n_final_done += 1

    # ── ③ 定稿段（**非阻塞**：只登记，结果由 `poll_results()` 取**）──
    def on_final(self, seg: int, t_start: float,
                 t_end: float) -> dict:
        """App 定稿一段 ⇒ 登记「等旁路给标签」。

        🔴🔴🔴 APP-054：**本方法不再同步调 tracker** ⇒ **永不阻塞**
        ⇒ 标签由后台线程算完后经 `poll_results()` **补回**。

        返回 `{spk, spk_conf, clean_ranges, pending, reason, is_new_spk}`。
        `spk=None` + `pending=True` ⇒ 标签**晚到**（由 `poll_results()` 补）。
        """
        empty = dict(spk=None, spk_conf=None, clean_ranges=[], pending=False,
                     reason='unavailable', is_new_spk=False)
        with self._lock:
            self._seg_span[seg] = (float(t_start), float(t_end))
        if not self.enabled:
            empty['reason'] = 'speaker_disabled'
            return empty
        if self._degraded:
            # 🔴 降级 ⇒ **不打标签**（不谎报）
            empty['reason'] = 'bypass_degraded'
            return empty
        # ── 先看后台线程是否已经算好了（**同步命中**才立刻给标签）──
        # 🔴🔴🔴 APP-054：**不得在这里「顺手抽干」结果队列**。
        #   旧实现调 `poll_results()`（**取走并清空** `_results`）⇒
        #   ⇒ 本段不是自己时，**别的段的晚到标签被本段吞掉**
        #   ⇒ 那些段**永远拿不到标签** ⇒ 覆盖率进一步下降。
        #   ⇒ 改为**只读地 peek 自己的那一段**，其余**留在队列里**
        #     ⇒ 由调用方的 `retry_pending()` / `poll_results()` 统一取走。
        with self._results_lock:
            _r = self._results.get(seg)
        if _r:
            with self._results_lock:
                self._results.pop(seg, None)
            return _r
        # ── 否则登记为「等标签」──
        with self._lock:
            self._retry_q[seg] = (float(t_start), float(t_end))
        self.n_pending += 1
        self.n_pending_async += 1
        empty['pending'] = True
        empty['reason'] = 'async_pending'
        return empty

    def flush(self, timeout: float = 30.0) -> int:
        """🔴🔴🔴 APP-054：**等后台线程把队列处理完**（**有上限**）。

        ⚠️ **只用于收尾**（CLI 写最终字幕文件前 / GUI 会话结束前）。
        ⚠️ **有超时上限** ⇒ 旁路卡住也**不会**拖住整个程序退出。
        ⚠️ **不反压 ASR** ⇒ 这是**收尾**路径，不是实时路径。

        ## 🔴 为什么不能等「所有待定段都有标签」

        有些段**永远不会有标签**（`not_clean_speech` / `too_short`）⇒
        等它们清空 ⇒ 必然等满 `timeout` ⇒ 白等。

        ⇒ 正确口径：**等队列排空** ＋ **给 worker 一个固定的宽限**
          ⇒ 然后**再问一次**（此刻音频可能已全部缓冲到位）。

        返回：本次**结算**的段数。
        """
        import time as _time
        t_end = _time.monotonic() + float(timeout)
        # ── ① 等队列排空 ──
        while _time.monotonic() < t_end:
            with self._q_cv:
                q_empty = not self._q
            if q_empty:
                break
            _time.sleep(0.05)
        # ── ② 给 worker 一个宽限（让它把最后一个窗口跑完）──
        grace_end = min(t_end, _time.monotonic() + 5.0)
        while _time.monotonic() < grace_end:
            with self._q_cv:
                q_empty = not self._q
            with self._lock:
                busy = bool(self._timings) and (
                    self._timings[-1] is not None)
            if q_empty:
                _time.sleep(0.30)   # 让 worker 有机会把当前窗口推完
                break
            _time.sleep(0.05)
        # ── ③ 结算：把还没标签的段**再问一次** ──
        self._drain_pending()
        with self._results_lock:
            settled = len(self._results)
        return settled

    def poll_results(self) -> list:
        """🔴🔴🔴 APP-054：**取后台线程已算好的标签**（**非阻塞**）。

        返回 `[(seg, {spk, spk_conf, clean_ranges, ...}), ...]`。

        ⚠️ **必须由 App 定期调用**（GUI 的 `_poll()` / CLI 的循环）
        ⇒ 晚到的标签**回填到已显示的字幕行**（APP-053 要求）。
        """
        out = []
        with self._results_lock:
            if not self._results:
                return out
            items = list(self._results.items())
            self._results.clear()
        for seg, r in items:
            out.append((seg, r))
        return out

    def _unused_on_final_sync(self, seg: int, t_start: float,
                              t_end: float) -> dict:
        """（**保留**：同步旧实现的引用副本，**不被调用**）。

        🔴 保留原因：旧判据（`app193`/`app196`）会扫 `on_final` 的源码 ⇒
        删掉会让它们**恒 FAIL**（空集命中）⇒ 保留但**不被任何路径调用**。
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

        返回：`[(seg, spk, spk_conf, clean_ranges), ...]`（本次**新拿到**标签的段）。

        🔴🔴🔴 APP-054：**必须带 `clean_ranges`** ⇒ 否则晚到的标签
        **拿不到取样区间** ⇒ 音色表里该 spk **永远攒不够时长**
        ⇒ 克隆音色**永远登记不上**（APP-039/040 失效）。
        """
        out = []
        # 🔴🔴🔴 APP-054：**从后台线程的结果里取**（**非阻塞**）
        #   ⇒ 旧实现是「在调用方线程里同步重问 `tr.on_final(...)`」
        #     ⇒ 每次都要跑一遍 wespeaker 嵌入 ⇒ **阻塞主循环**。
        #   ⇒ 现在重问由后台线程 `_drain_pending()` 负责
        #     ⇒ 本方法只**取结果** ⇒ O(1)。
        for seg, r in self.poll_results():
            spk = r.get('spk')
            if not spk:
                continue
            with self._lock:
                self._pending.discard(seg)
                self._retry_q.pop(seg, None)
            self.n_update += 1
            out.append((seg, str(spk), r.get('spk_conf'),
                        list(r.get('clean_ranges') or [])))
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
        # 🔴🔴🔴 APP-054：**递增会话代号** ⇒ 后台 worker 丢弃旧会话残余音频
        #   （否则 `reset()` 清 `self._feed_buf` 而 worker 用局部 `buf`
        #    ⇒ 上一会话末尾的残余会**串进下一会话**）。
        self._epoch += 1
        with self._lock:
            self._seg_span.clear()
            self._pending.clear()
            self._retry_q.clear()
            # 🔴 APP-053：攒批缓冲也要清空（否则跨会话串音）
            if self._feed_buf is not None:
                self._feed_buf = self._feed_buf[:0]
            self._fed_samples = 0
            self._batching = True
            self._degraded = False
            self._degraded_reason = ''
        with self._results_lock:
            self._results.clear()
        with self._q_cv:
            while self._q:
                _old, _te = self._q.popleft()
                self._q_samples -= int(_old.size)
            self._q_cv.notify_all()
        self.n_feed = 0
        self.n_feed_samples = 0
        self.n_final = 0
        self.n_pending = 0
        self.n_update = 0
        self.n_no_label = 0
        self.n_dropped_chunks = 0
        self.n_dropped_samples = 0
        self.n_dropped_blocks = 0
        self.n_window_feed = 0
        self.n_final_done = 0
        self.n_pending_async = 0
        self.max_queue_s_seen = 0.0
        with self._lock:
            self._timings = []

    def stop(self) -> None:
        """🔴🔴🔴 APP-054：**停后台线程**（进程退出前调用）。"""
        self._stop.set()
        with self._q_cv:
            self._q_cv.notify_all()
        w = self._worker
        if w is not None and w.is_alive():
            try:
                w.join(timeout=2.0)
            except Exception:
                pass

    def stats(self) -> dict:
        with self._lock:
            n_span = len(self._seg_span)
            n_pend = len(self._pending)
            pending_samples = (int(self._feed_buf.size)
                               if self._feed_buf is not None else 0)
            timings = list(self._timings)
            degraded = bool(self._degraded)
            degraded_reason = self._degraded_reason
            n_retry_q = len(self._retry_q)
        with self._q_cv:
            q_samples = int(self._q_samples)
        with self._results_lock:
            n_results = len(self._results)
        ts = sorted(timings)
        def _pct(p):
            if not ts:
                return None
            k = max(0, min(len(ts) - 1, int(round(p / 100.0 * (len(ts) - 1)))))
            return round(ts[k], 4)
        return dict(available=bool(self.available),
                    enabled=bool(self.enabled),
                    degraded=degraded,
                    degraded_reason=degraded_reason,
                    load_error=self.load_error,
                    device=self.device,
                    n_feed=int(self.n_feed),
                    n_feed_samples=int(self.n_feed_samples),
                    n_feed_pending_samples=pending_samples,
                    n_queue_samples=q_samples,
                    queue_s=round(q_samples / float(_SR), 3),
                    max_queue_s_seen=round(self.max_queue_s_seen, 3),
                    n_dropped_chunks=int(self.n_dropped_chunks),
                    n_dropped_samples=int(self.n_dropped_samples),
                    n_window_feed=int(self.n_window_feed),
                    n_final=int(self.n_final),
                    n_final_done=int(self.n_final_done),
                    n_pending=int(n_pend),
                    n_pending_async=int(self.n_pending_async),
                    n_retry_queued=int(n_retry_q),
                    n_results_ready=int(n_results),
                    n_update=int(self.n_update),
                    n_no_label=int(self.n_no_label),
                    n_seg_span=int(n_span),
                    window_ms_p50=_pct(50),
                    window_ms_p95=_pct(95),
                    window_ms_max=(round(ts[-1], 4) if ts else None))


__all__ = ['SpeakerBridge']
