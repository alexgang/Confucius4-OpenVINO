# -*- coding: utf-8 -*-
r"""asr052_speaker_tracker_api.py — ASR-029：**给 App 可 import 的说话人旁路接口**。

## ASR-029 原文（2026-10-29 14:38）
> 要做的：在 ASR-028（Q&A 段测试）跑通的同一套代码上，封装一个给 App 用的接口，例如
> `SpeakerTracker.feed(pcm16k, t)`，再加上定稿段回调
> `on_final(seg_id, t_start, t_end) -> {spk, spk_conf, is_new_spk, clean_ranges}`。
> 其中 clean_ranges 是这个说话人可以拿来取样的**干净单人区间**，App 用它来提 TTS x-vector。
> 另外要有 `on_spk_update(seg_id, spk)` 用于**延迟到达的标签**。
> 设备放 GPU.0，限制线程（ASR-026 的结论），不能占用很多 CPU。
> 写一页接口说明，放在 `shared/NOTICE_asr_to_app_speaker_api.md`，由主会话通知 App。

## 🔴🔴 ASR-033（2026-10-30 10:47）：**交付集合与内部素材隔离**
reviewer 指出：交给 App 的说话人接口代码里含有**内部音频素材标识与本机绝对路径**，
被 App 的打包闸门拦下。App 只在**包副本**里做等长字面量替换，
因为本模块在运行时会 import 那几个文件。

⇒ 本模块**已按 ASR-033 重构**：
* **交付集合 = 4 个文件**（互相之间只用普通模块名 import，**无本机绝对路径**）：
  - `asr052_speaker_tracker_api.py`（本文件，入口）
  - `asr052_spk_runtime.py`（运行时内核：fbank / 嵌入 / 聚类 / 旁路分段）
  - `asr_thread_defaults.py`（限线程，ASR-031 §1 的交付默认）
  - `asr_spk_window.py`（**窗口长度的唯一事实来源**；🔴 **ASR-045 新增**）
* **评估/测试代码一律不交付**（`asr050` 等评估脚本留在 ASR 侧的 `scripts/`，
  **不进交付集合**，运行时 import 链也不碰它们）。
* **默认 IR 路径改为「按包内相对布局探测」**，不再硬编码研发机绝对路径；
  调用方（App）仍可用 `seg_ir=` / `wes_ir=` 显式传入（**契约不变**）。
* 🔴 **ASR-045（2026-11-04 09:55）**：交付集合由 **3 个扩到 4 个文件**
  （新增 `asr_spk_window.py`）。理由：原内核把窗口写死 10 s，
  而 App 喂 5 s ⇒ 内核补零成 10 s 跑 ⇒ 标签质量无保证、客户包实际仍跑 10 s。
  ⇒ 现在内核**从 `asr_spk_window` 读**窗口常量 ⇒ 「窗口长度」只有一处定义。

### 交付集合自检（ASR-033 明文要求）
> 在交付文件列表上 grep 内部关键字（音频素材代号 / 素材编号 / 内部场合字样 /
> 机器用户名 / 本机绝对路径前缀），结果应为 0。

⚠️ **本文件（连同同交付集合的另两个文件）**也**不得**在注释里复述这些关键字
⇒ 否则**自检会被自己的文档字符串判失败** ⇒ 关键词表只存在于**闸门脚本**里，
不在交付集合里。

⇒ 由 `asr079_delivery_set_gate.py` 落成机读产物 + 反证。

## 🔴🔴 设计要点（对应 App 侧的问题）
App 现在的克隆是「滑动窗口 + 持续采样 + 平滑」⇒ **音色渐变 + 切换滞后**（APP-039）。
改正后的设计：**音色按句绑定到 spk，只在出现新 spk 时取样一次** ⇒ 本接口的职责是
1. `feed()` 持续收音频（不产生副作用，只缓冲）；
2. `on_final(seg_id, t_start, t_end)` 在**定稿段**产生时调用 ⇒ 返回该段的
   `{spk, spk_conf, is_new_spk, clean_ranges}`；
3. `on_spk_update(seg_id, spk)` 在**标签延迟到达**时补发（此时 `spk` 可能与
   `on_final` 时返回的不同 ⇒ App 需要能改绑）。

## 🔴 口径纪律（与 ASR-028 同一套代码，参数同源）
* 定稿段 = App 路径已验证的 `Recorder`（`pya_app_path_seg.py`）断句口径
  ⇒ 本接口**不自己造断句**，`on_final` 由调用方（App）在自己的定稿时刻调用。
* 旁路分段模型 = segmentation-3.0（GPU.0）⇒ 只出帧级 `p_speech`/`p_dom`，
  **不产生断点**（ASR-021）。
* 嵌入 = wespeaker（**方案 A 的 OV IR，GPU.0**；前端 fbank 用 numpy 复刻 kaldi）
  ⇒ **运行时不依赖 torch**。
* 聚类 = 在线聚类（余弦阈值 + 均值逐步更新 + 人数上限），与 ASR-013 ③ 同源。
* 克隆向量 = **TTS 自己的 x-vector**（ASR-026 铁律）⇒ 本接口只提供
  `clean_ranges`（干净的**单人区间**），供 App 取样，**不返回克隆向量**。

## 🔴 CPU 纪律（ASR-026 的结论：限制线程）
模块导入即设线程上限（OMP/MKL/OpenBLAS/NUMEXPR/VECLIB），
避免 ASR 在 GPU.0 上吃掉 6–7 个核把 NPU 上的 TTS 拖慢（ASR-026）。

## 用法（App 侧）
```python
from asr052_speaker_tracker_api import SpeakerTracker

tracker = SpeakerTracker(device='GPU.0', thr=0.35)

# ① 持续喂音频（App 的音频回调里）
tracker.feed(pcm16k_bytes_or_float_array, t_end_sec)

# ② App 自己定稿时调用
res = tracker.on_final(seg_id=12, t_start=10.5, t_end=13.2)
# res = {'spk': 'S2', 'spk_conf': 0.71, 'is_new_spk': True,
#        'clean_ranges': [(10.8, 12.9)], 'lag_s': 0.012, ...}

# ③ 标签延迟到达时（可选）
tracker.on_spk_update(seg_id=12, spk='S3')
```
"""
from __future__ import annotations

import os
import sys
import threading
import time

# 🔴🔴 CPU 纪律：**限线程是 ASR 的交付默认**（ASR-031 §1） ──
#   ASR-026/027 实测：不限线程时 torch 的 OpenMP（`libiomp5md.dll`）
#   吃掉 6.85 个核，把 NPU 上的 TTS 拖慢（TTS 的 CPU 时间 ×2.24）。
#   ⇒ 限线程（`OMP/MKL/OPENBLAS/NUMEXPR/VECLIB_MAXIMUM_THREADS=1`）
#     **是交付默认，不是「建议」**。
#   🔴🔴 **顺序是关键**：`OMP_NUM_THREADS` 等是 BLAS/OpenMP 运行时在
#     **import 时**读取的 ⇒ **必须在 import numpy/torch 之前设好**
#     ⇒ 本 import 放在**模块最顶**、早于任何重依赖 import。
#   🔴 §41：限线程代码**只有一份**（`asr_thread_defaults.py`）⇒ 不再各抄一份。
import asr_thread_defaults  # noqa: E402

THREAD_ENV = asr_thread_defaults.limit_threads(asr_thread_defaults.
                                                DEFAULT_THREADS)

# 🔴 ASR-033：**运行时内核**（fbank / 嵌入 / 聚类 / 旁路分段）
#   ⇒ 与本文件同属**交付集合**（**ASR-045 起 4 个文件**），
#     不含任何内部素材 / 本机绝对路径。
import asr052_spk_runtime as _rt  # noqa: E402

SR = 16000
DEFAULT_MAX_SPK = 6

# ══════════════════════════════════════════════════════════════════
# 🔴🔴🔴 **ASR-050（2026-11-06）用户决定：`min_clean_ratio` 默认 0.8 → 0.6**
#
# 依据（asr118，900 s 评测集 3 段 / 26 换人点）：
#   原基线（门槛 0.8）⇒ 召回 19/26、误报 3、无标签段 12；
#   候选值（门槛 0.6）⇒ 召回 22/26、误报 3、**无标签段 5**。
#   ⇒ **召回 ↑3、误报不变、无标签段 ↓7** ⇒ 用户决定采用 0.6。
#
# 🔴🔴 **措辞纪律（ASR-050 落地时实测到的跨模块陷阱）**：
#   App 侧 `results/app/app193_app053_spk_frame_audit.py` 的 `read_asr_gates()`
#   用**正则从本文件源码现读门槛默认值**（`re.search` 取**第一个**匹配）
#   ⇒ **本注释块里不能出现「`min_clean_ratio` 后面跟数字」的写法**
#     （会被当成默认值读走 ⇒ App 侧读成旧值 0.8 ⇒ 静默漂移）。
#   ⇒ 本文件里 `min_clean_ratio` + 数字的**第一个**出现必须是
#     `__init__` 签名里的真实默认值。**改本文件默认值时必须重跑该正则自检**。
#
# 🔴 **「三处一致」（ASR-050 第 1 条）**：
#   ① 本文件 `SpeakerTracker.__init__` 的**代码默认值**（下面 `DEFAULT_MIN_CLEAN_RATIO`）；
#   ② **环境变量开关**的默认值（`ASR_SPK_MIN_CLEAN_RATIO`，
#      与 `asr_spk_window.ASR_SPK_WINDOW_S` **完全同款** ⇒ 不写第二份默认值）；
#   ③ **配置说明**（本文件的 `min_clean_ratio` 参数文档 + `asr_spk_window` 的
#      交付常量 + `NOTICE_asr_to_app_speaker_api.md` 的参数表）。
#
# 🔴 **其它参数一律不动**：步长 0.64 s、VAD 关闭、5 s 窗、`thr=0.35`、
#   `overlap_ratio_max=0.02`（**惰性参数**，见 §76）、`min_dur_s=2.0`。
#
# 🔴 **产品后果（ASR-050 第 4 条）**：0.6 会让更多**短的、不太干净的**片段带上标签
#   ⇒ **标签多了 ≠ 这段可以拿来登记克隆音色**
#   ⇒ 登记仍然按 App 的 `REG_CONF_MIN` / 干净连续 ≥2.5 s 规则。
# ══════════════════════════════════════════════════════════════════

#: 🔴 **交付默认 `min_clean_ratio`**（ASR-050 用户决定 0.8 → 0.6）
DEFAULT_MIN_CLEAN_RATIO = 0.6
# reviewer 11-07: clustering algorithm switch.  v1 = legacy (thr 0.35 + EMA 0.5);
#   v2 = diart-style (asr_spk_cluster_v2.py), DEFAULT since v2.4 (user-approved 2026-11-07).  Env ASR_SPK_CLUSTER=v1 reverts.
CLUSTER_MODE = os.environ.get('ASR_SPK_CLUSTER', 'v2').strip().lower()
HOMOG_MIN_DUR_S = 3.0
HOMOG_MIN_SIM = float(os.environ.get('ASR_SPK_HOMOG_MIN', '0.45'))

#: 🔴 ASR 侧环境变量名；App 侧用 `LIVECAP_SPK_MIN_CLEAN_RATIO`（同义）
MIN_CLEAN_RATIO_ENV = 'ASR_SPK_MIN_CLEAN_RATIO'


def _min_clean_ratio_from_env(default: float = DEFAULT_MIN_CLEAN_RATIO
                               ) -> float:
    """从环境变量读 `min_clean_ratio`；非法 ⇒ 退回 `default`。

    🔴 **同源纪律**（与 `asr_spk_window._win_s_from_env` **完全同款**）：
      * ASR 侧读 `ASR_SPK_MIN_CLEAN_RATIO`；
      * App 侧读 `LIVECAP_SPK_MIN_CLEAN_RATIO`（**由 App 自己实现**，
        但**默认值必须来自本文件的 `DEFAULT_MIN_CLEAN_RATIO`**）
        ⇒ 两边**各写一份环境变量名**是为了不互相 import，
          但**默认值只有一份** ⇒ 不可能漂移。
    ⚠️ 非法值（非数字 / ≤ 0 / > 1）⇒ **退回默认**（不静默改语义）。
    """
    raw = os.environ.get(MIN_CLEAN_RATIO_ENV, '')
    if raw in (None, ''):
        return float(default)
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return float(default)
    if not (0.0 < v <= 1.0):
        return float(default)
    return v

# ── IR 默认位置：🔴 **不再硬编码研发机绝对路径**（ASR-033）────────────
#   交付形态：IR 在包内 `models/spk/` 下（App 的 `speaker_assets.resolve()`
#   会**显式**把路径传进来 ⇒ 这里只是「兜底默认值」）。
#   ⇒ 探测顺序：
#     ① 环境变量 `ASR_SPK_WES_IR` / `ASR_SPK_SEG_IR`（部署方显式指定）；
#     ② 包内相对布局：`<包根>/models/spk/wespeaker-resnet34-<精度>`、
#        `<包根>/models/spk/pyannote_seg_3_0/<精度>`（精度 fp32 → fp16）；
#     ③ 都没有 ⇒ 返回 None ⇒ `_ensure_models()` 失败 ⇒ 旁路**安静降级**
#        （App 的语义：模型文件缺失时旁路自动关闭）。
#
# 🔴🔴🔴 **ASR-045：seg IR 的目录必须按「当前窗口」选**
#   seg IR 的输入长度必须 == `WIN_N`（5 s 窗 ⇒ 80000；10 s 窗 ⇒ 160000）
#   ⇒ 喂错 ⇒ OpenVINO 抛 shape 不兼容 ⇒ 旁路**整个失效**（零标签）。
#   ⇒ 兜底探测时按 `asr_spk_window.seg_ir_subdir_for(WIN_S)` 选目录
#     （5.0 s ⇒ `fp16-w5`；10.0 s ⇒ `fp16`）。
_WES_DIR_TMPL = 'wespeaker-resnet34-%s'
_SEG_DIR_TMPL = os.path.join('pyannote_seg_3_0', '%s')
_PRECISIONS = ('fp32', 'fp16')


def _pkg_root() -> str:
    """推断包根（`<包根>/app/asr_spk/` ⇒ `<包根>`）。

    🔴 纯**相对**推断 ⇒ 不含任何本机绝对路径。
    研发机直接跑 `scripts/` 时 ⇒ 包根 = `scripts/` 的上一级 ⇒ 探测自然落空
    ⇒ 旁路降级（**这是正确行为**：研发机请显式传 `seg_ir`/`wes_ir`）。
    """
    here = os.path.dirname(os.path.abspath(__file__))
    # 交付形态：<pkg>/app/asr_spk/<file>.py ⇒ 上溯 2 级
    if os.path.basename(here).lower() == 'asr_spk':
        return os.path.dirname(os.path.dirname(here))
    return os.path.dirname(here)


def _find_ir(env_name: str, dir_tmpl: str) -> str | None:
    """按 ① 环境变量 → ② 包内相对布局 的顺序定位 IR 目录。"""
    v = os.environ.get(env_name)
    if v and os.path.isdir(v):
        return v
    root = _pkg_root()
    for prec in _PRECISIONS:
        cand = os.path.join(root, 'models', 'spk', dir_tmpl % prec)
        if os.path.isdir(cand):
            return cand
    return None


def _default_wes_ir() -> str | None:
    return _find_ir('ASR_SPK_WES_IR', _WES_DIR_TMPL)


def _default_seg_ir() -> str | None:
    """seg IR 的兜底定位（**按当前窗口选变体**）。

    🔴🔴🔴 **ASR-045**：seg IR 的输入长度必须 == `WIN_N`
      ⇒ 5 s 窗 ⇒ 80000 样本的 IR（`fp16-w5`）；10 s 窗 ⇒ 160000（`fp16`）
      ⇒ 喂错 ⇒ OpenVINO 抛 shape 不兼容 ⇒ 旁路**整个失效**。
    ⇒ 探测顺序：
      ① 环境变量 `ASR_SPK_SEG_IR`（部署方显式指定 ⇒ **最高优先**）
      ② 包内 `models/spk/pyannote_seg_3_0/<当前窗口的变体>`
      ③ 包内 `models/spk/pyannote_seg_3_0/fp16`（= 10 s 的现役 IR）
         —— ⚠️ 若当前窗口是 5 s 而只有 ③ 命中 ⇒ 那是**形状不匹配**的 IR
         ⇒ `run_seg_side` 的形状守卫会**明确抛错**（不静默错位）。
    """
    v = os.environ.get('ASR_SPK_SEG_IR')
    if v and os.path.isdir(v):
        return v
    root = _pkg_root()
    try:
        import asr_spk_window as _W  # 交付集合内（ASR-045 新增）
        sub = _W.seg_ir_subdir_for(_rt.WIN_S)
    except Exception:
        sub = 'fp16'
    cand = os.path.join(root, 'models', 'spk', _SEG_DIR_TMPL % sub)
    if os.path.isdir(cand):
        return cand
    for prec in _PRECISIONS:
        cand = os.path.join(root, 'models', 'spk', _SEG_DIR_TMPL % prec)
        if os.path.isdir(cand):
            return cand
    return None


class SpeakerTracker:
    """说话人旁路：**给 App import 用的**在线跟踪器。

    ## 线程模型
    `feed()` 与 `on_final()` 可能被 App 的音频线程与定稿线程分别调用
    ⇒ 全部用一把 `threading.Lock` 保护（`feed` 持锁时间极短，只做追加）。

    ## 生命周期
    1. `__init__` 只做**轻量**初始化（不加载 IR）⇒ 构造不阻塞 App 启动。
    2. 第一次 `feed()` 时惰性加载旁路分段 IR 与 wespeaker IR（`_ensure_models`）。
    3. `on_final()` 需要**旁路分段结果**覆盖到该段 ⇒ 若分段尚未推进到该段，
       会返回 `spk=None` + `pending=True`（标签稍后由 `on_spk_update` 补发）。

    ## 🔴 不做强制断句（ASR-021）
    本类**不产生任何断点**；`on_final` 的调用时机完全由 App 决定。

    ## 🔴 IR 路径（ASR-033）
    `seg_ir` / `wes_ir` **可显式传入**（App 的 `speaker_assets.resolve()`
    就是这么做的）；不传时按「环境变量 → 包内相对布局」探测，
    **探测不到 ⇒ 旁路安静降级**（`reason='models_not_ready'`）。

    ## 🔴🔴 门槛参数（**配置说明**，ASR-050）
    | 参数 | 交付默认 | 环境变量（ASR 侧） | 说明 |
    |---|---|---|---|
    | `min_clean_ratio` | **0.6** | `ASR_SPK_MIN_CLEAN_RATIO` | 段内**干净语音占比**下限（低于则不出标签）|
    | `overlap_ratio_max` | 0.02 | —（**惰性参数**，见下）| 重叠语音占比上限 |
    | `min_dur_s` | 2.0 | — | 段的最小时长 |
    | `stride_ms` | 1280.0 | — | 旁路分段的滑窗步长 |
    | `thr` | 0.35 | — | 在线聚类的余弦阈值 |

    🔴 **`min_clean_ratio` 的取值优先级**（ASR-050 第 1 条「三处一致」）：
      ① 显式传**非默认值** ⇒ 用传入值（评测脚本的 A/B 口径覆盖）；
      ② 否则 ⇒ 环境变量 `ASR_SPK_MIN_CLEAN_RATIO`；
      ③ 再否则 ⇒ `DEFAULT_MIN_CLEAN_RATIO`（= **0.6**）。
      ⇒ **代码默认值 / 环境变量默认值 / 本配置说明三处同源**。

    🔴 **`overlap_ratio_max` 是惰性参数**（ASR-048/asr121 实测）：
      `p_dom` 只含 powerset 的**单人三类** ⇒ 行和 ≤ 1.0 ⇒ 判据 `>1.05` **恒 False**
      ⇒ `overlap_ratio` **恒 0.0** ⇒ 该分支**永不触发**
      ⇒ **不要把它当作「已排除重叠语音」的防护**（`clean_ranges` 不保证单人）。

    🔴 **标签变多 ≠ 这段可以登记克隆音色**（ASR-050 第 4 条）：
      门槛放宽到 0.6 ⇒ 更多**短的、不太干净的**片段会带上标签
      ⇒ 登记仍按 App 的 `REG_CONF_MIN` / 干净连续 ≥2.5 s 规则。
    """

    def __init__(self, device: str = 'GPU.0', seg_device: str = 'GPU.0',
                 thr: float = 0.35, update_alpha: float = 0.5,
                 max_speakers: int = DEFAULT_MAX_SPK,
                 seg_ir: str | None = None, wes_ir: str | None = None,
                 min_clean_ratio: float = 0.6,
                 overlap_ratio_max: float = 0.02,
                 min_dur_s: float = 2.0,
                 stride_ms: float = 1280.0):
        self.device = device
        self.seg_device = seg_device
        self.thr = thr
        self.update_alpha = update_alpha
        self.max_speakers = max_speakers
        self.seg_ir = seg_ir if seg_ir is not None else _default_seg_ir()
        self.wes_ir = wes_ir if wes_ir is not None else _default_wes_ir()
        # 🔴🔴 **ASR-050：`min_clean_ratio` 的取值优先级**（三处同源）
        #   ① **显式传值**（≠ 代码默认值 0.6）⇒ 用传入值
        #      ⇒ **评测脚本的口径覆盖仍有效**（`asr111`/`asr118` 就靠这个跑 A/B：
        #      基线臂显式传 0.8、候选臂显式传 0.4/0.6）。
        #   ② 其它情况（未传 / 传的就是 0.6）⇒ **环境变量**
        #      `ASR_SPK_MIN_CLEAN_RATIO` 优先；
        #      环境变量未设 / 非法 ⇒ **`DEFAULT_MIN_CLEAN_RATIO`（0.6）**。
        #   ⇒ **「代码默认值 / 环境变量默认值 / 配置说明」三处一致**（ASR-050 第 1 条）。
        #   ⚠️ 副作用（已写进交接清单）：若运维**显式设了环境变量**，
        #      则「显式传 0.6」也会被环境变量覆盖（0.6 == 代码默认值 ⇒ 视为未覆盖）。
        #      评测脚本**不设**该环境变量 ⇒ A/B 不受影响。
        if float(min_clean_ratio) != float(DEFAULT_MIN_CLEAN_RATIO):
            self.min_clean_ratio = float(min_clean_ratio)
        else:
            self.min_clean_ratio = _min_clean_ratio_from_env()
        self.overlap_ratio_max = overlap_ratio_max
        self.min_dur_s = min_dur_s
        self.stride_ms = stride_ms

        self._lock = threading.Lock()
        self._buf = []            # 未消费的 float32 音频（16 kHz 单声道）
        self._buf_len = 0         # 缓冲内样本数
        self._t0 = None            # 缓冲起点在全局时间轴上的位置（秒）
        self._seg_frames = None    # 帧级概率（由旁路分段填充）
        # 🔴🔴 **ASR-045**：旁路推理失败**不许静默** ⇒ 记下最后一次异常
        #   （此前 `except Exception: self._seg_frames = None` 会把
        #   「seg IR 形状不匹配」这类**致命**错误吞掉 ⇒ 表现为「零标签」，
        #   现场无法区分「没人说话」和「旁路已死」）
        self._seg_error = None
        self._models_ready = False
        self._enc = None
        self._clu = None
        self._prev_spk = None
        self._pending = {}         # seg_id -> row（等分段结果到达）
        self._finalized = {}       # seg_id -> 结果（供 on_spk_update 改绑）
        self._n_embed = 0
        self._embed_lag = []

    # ── ① 喂音频 ────────────────────────────────────────────────
    def feed(self, pcm16k, t: float = None) -> int:
        """喂一段 16 kHz 单声道 PCM。

        参数
        ----
        pcm16k : bytes | bytearray | numpy.ndarray | list
            16 kHz、单声道、PCM16（bytes/bytearray）或 float32（ndarray/list，值域 [-1,1]）。
        t : float, 可选
            这段音频**结束**时刻（秒，全局时间轴）。给了就把缓冲起点对齐到
            `t - len/sr`，从而让 `on_final` 的 `t_start/t_end` 与缓冲时间轴一致。

        返回
        ----
        缓冲中累计的样本数（int）。
        """
        import numpy as np
        if isinstance(pcm16k, (bytes, bytearray)):
            a = np.frombuffer(pcm16k, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            a = np.asarray(pcm16k, dtype=np.float32).reshape(-1)
        if a.size == 0:
            return self._buf_len
        with self._lock:
            if self._t0 is None:
                if t is None:
                    self._t0 = 0.0
                else:
                    self._t0 = max(0.0, float(t) - a.size / SR)
            self._buf.append(a)
            self._buf_len += int(a.size)
            self._ensure_models()
            self._advance_seg()
        return self._buf_len

    # ── ② 定稿段回调 ────────────────────────────────────────────
    def on_final(self, seg_id, t_start: float, t_end: float) -> dict:
        """App 定稿一段时调用 ⇒ 返回该段的说话人信息。

        返回
        ----
        dict：
          `spk`          : 'S1'/'S2'/... 或 None（还不够干净/模型未就绪）
          `spk_conf`     : float 或 None
          `is_new_spk`   : bool（该 spk 首次出现 ⇒ App 应当**取样一次**）
          `clean_ranges` : [(start_s, end_s), ...] 该 spk 可用于取 x-vector 的**干净单人区间**
          `lag_s`        : 该段嵌入耗时（秒）
          `pending`      : True 表示旁路分段还没覆盖到该段 ⇒ 稍后走 `on_spk_update`
          `reason`       : 未出标签的原因（None / 'not_clean_speech' / 'overlap' /
                          'embed_shape_out_of_range' / ...）
        """
        import numpy as np
        with self._lock:
            self._ensure_models()
            seg = self._seg_slice(t_start, t_end)
            pcm = self._pcm_slice(t_start, t_end)
            dur = len(pcm) / SR
            base = {'spk': None, 'spk_conf': None, 'is_new_spk': False,
                    'clean_ranges': [], 'lag_s': None, 'pending': False,
                    'reason': None, 'seg_id': seg_id,
                    't_start': float(t_start), 't_end': float(t_end),
                    'dur_s': round(dur, 3)}
            if not self._models_ready:
                base['reason'] = 'models_not_ready'
                return base
            # 🔴🔴 **2026-10-29 21:40 修（asr054 自检抓出）**：
            #   原来只判 `dur < min_dur_s` ⇒ **请求区间超出已缓冲音频时**，
            #   `dur` 会退化成「缓冲里实际有多少」⇒ 被**误报成 `too_short`**，
            #   而真实原因是「**这段音频还没 feed 进来**」。
            #   ⇒ 两个原因必须**分开**：音频没到 ⇒ `audio_not_buffered` + `pending=True`
            #     （App 侧应等 `on_spk_update` 补发），而不是当成「段太短」丢弃。
            if dur < self.min_dur_s:
                base['reason'] = ('audio_not_buffered'
                                  if dur < (t_end - t_start) - 1e-6
                                  else 'too_short')
                base['pending'] = (base['reason'] == 'audio_not_buffered')
                base['requested_dur_s'] = round(float(t_end - t_start), 3)
                base['buffered_dur_s'] = round(dur, 3)
                if base['pending']:
                    self._pending[seg_id] = base
                return dict(base)
            if seg is None:
                base['reason'] = 'seg_pending'
                base['pending'] = True
                self._pending[seg_id] = base
                return dict(base)

            p_speech, p_dom = seg
            clean_f = (p_speech >= 0.5)
            clean_ratio = float(clean_f.mean()) if clean_f.size else 0.0
            # 🔴 `p_dom` 真实形状 = (N, n_speakers+1)；但**调用方可能塞 1 维**
            #   ⇒ 这里做维度兜底（1 维 ⇒ 视为「只有主导说话人，无重叠信息」）。
            if getattr(p_dom, 'ndim', 1) >= 2 and p_dom.shape[1] > 1:
                overlap_ratio = float(
                    (p_dom[:, 1:].sum(axis=1) > 1.05).mean())
            else:
                overlap_ratio = 0.0
            overlap_ratio = overlap_ratio if p_dom.size else 0.0
            base['clean_ratio'] = round(clean_ratio, 4)
            base['overlap_ratio'] = round(overlap_ratio, 4)
            if clean_ratio < self.min_clean_ratio:
                base['reason'] = 'not_clean_speech'
                return base
            if overlap_ratio > self.overlap_ratio_max:
                base['reason'] = 'overlap'
                return base

            t0 = time.perf_counter()
            # 🔴 **超界不静默、不崩溃**（ASR-031 §3 改法 ① 落地）：
            #   编译期给 T 设了上界 ⇒ 超过上界的段**不能截断**（截断会改变向量
            #   ⇒ 聚类结论失真）⇒ 编码器抛异常 ⇒ 这里**降级为「跳过该段」**，
            #   并把原因写进 `reason`（App 可观测，不静默丢段）。
            try:
                v = self._enc.embed(pcm, SR)
            except ValueError as ex:
                base['reason'] = 'embed_shape_out_of_range'
                base['embed_error'] = str(ex)
                return dict(base)
            lag = time.perf_counter() - t0
            self._n_embed += 1
            self._embed_lag.append(lag)
            if CLUSTER_MODE == 'v2':
                # homogeneity check: embed the two halves; a speaker change inside the
                # segment shows up as dissimilar halves => label it, but never let it
                # move a centroid or seed a voice registration.
                homog, hsim = True, None
                if dur >= HOMOG_MIN_DUR_S:
                    try:
                        h = len(pcm) // 2
                        e1 = np.asarray(self._enc.embed(pcm[:h], SR)).reshape(-1)
                        e2 = np.asarray(self._enc.embed(pcm[h:], SR)).reshape(-1)
                        hsim = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-9))
                        homog = hsim >= HOMOG_MIN_SIM
                    except Exception:
                        homog, hsim = True, None
                spk, conf, _action = self._clu.assign(
                    v, homogeneous=homog, weight=clean_ratio * dur)
                base['cluster_action'] = _action
                base['homog_sim'] = None if hsim is None else round(hsim, 4)
                if not homog:
                    base['mixed'] = True
                    conf = min(float(conf), 0.3)   # below App's REG_CONF_MIN => never registers a voice
            else:
                spk, conf, _action = self._clu.assign(v)
            is_new = (self._prev_spk is None) or (spk != self._prev_spk)
            self._prev_spk = spk
            base['spk'] = spk
            base['spk_conf'] = round(float(conf), 4)
            base['is_new_spk'] = bool(is_new)
            base['lag_s'] = round(lag, 4)
            # clean_ranges = 该段内**连续干净**的区间（≥0.3 s 才算可用）
            ranges = self._clean_ranges(p_speech, t_start, t_end)
            base['clean_ranges'] = ranges
            self._finalized[seg_id] = base
            # 🔴🔴 **2026-10-29 21:45 修（asr054 自检抓出）**：
            #   原来 `return base` 直接返回**内部字典本体** ⇒ 调用方拿到的对象
            #   与 `self._finalized[seg_id]` **是同一个对象** ⇒
            #   后续 `on_spk_update()` 改绑 `spk` 时，会**就地改掉调用方手里的旧结果**
            #   （aliasing bug）⇒ App 侧可能看到「自己刚拿到的标签自己变了」。
            #   ⇒ 对外一律返回**副本**。
            return dict(base)

    # ── ③ 延迟标签补发 ──────────────────────────────────────────
    def on_spk_update(self, seg_id, spk: str) -> dict:
        """标签延迟到达时补发/改绑。

        * 该段**还没**定稿（还在 `_pending`）⇒ 直接填上，`pending=False`。
        * 该段**已**定稿 ⇒ 改绑 `spk`（App 侧需要能跟着改音色）。
        """
        with self._lock:
            row = self._pending.pop(seg_id, None)
            if row is not None:
                row['spk'] = spk
                row['spk_conf'] = row.get('spk_conf')
                row['pending'] = False
                row['reason'] = 'late_update'
                self._finalized[seg_id] = row
                return dict(row)
            row = self._finalized.get(seg_id)
            if row is None:
                return {'seg_id': seg_id, 'spk': spk, 'known': False,
                        'note': '未知 seg_id（未见过该段的 on_final）'}
            old = row.get('spk')
            row['spk'] = spk
            row['spk_rebound_from'] = old
            row['known'] = True
            return dict(row)

    # ── 工具 ────────────────────────────────────────────────────
    def stats(self) -> dict:
        with self._lock:
            lags = sorted(self._embed_lag)

            def pct(p):
                if not lags:
                    return None
                k = max(0, min(len(lags) - 1,
                               int(round(p / 100.0 * (len(lags) - 1)))))
                return round(lags[k], 4)
            return {
                'n_embed': self._n_embed,
                'n_finalized': len(self._finalized),
                'n_pending': len(self._pending),
                'buffered_samples': self._buf_len,
                'buffered_sec': round(self._buf_len / SR, 3),
                'embed_lag_p50_s': pct(50),
                'embed_lag_p95_s': pct(95),
                'backend': getattr(self._enc, 'backend', None),
                'device': self.device,
                'n_speakers': len(getattr(self._clu, 'centroids', []) or []),
                'thread_env': {k: os.environ.get(k) for k in (
                    'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                    'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')},
            }

    # ── 内部 ────────────────────────────────────────────────────
    def _ensure_models(self) -> None:
        if self._models_ready:
            return
        try:
            self._enc = _rt.WespeakerOVEncoder(self.wes_ir, self.device)
            if CLUSTER_MODE == 'v2':
                # reviewer 11-07: diart-style clustering (see asr_spk_cluster_v2.py)
                from asr_spk_cluster_v2 import DiartStyleCluster
                self._clu = DiartStyleCluster(max_speakers=self.max_speakers)
            else:
                self._clu = _rt.OnlineSpeakerCluster(thr=self.thr,
                                                     update_alpha=self.update_alpha,
                                                     max_speakers=self.max_speakers)
            self._models_ready = True
        except Exception:
            self._models_ready = False

    def _advance_seg(self) -> None:
        """把旁路分段推进到**当前缓冲末尾**（帧级 p_speech/p_dom）。"""
        if not self._models_ready:
            return
        try:
            import numpy as np
            if self._seg_frames is None:
                self._seg_frames = {'p_speech': [], 'p_dom': []}
            buf = np.concatenate(self._buf) if self._buf else None
            if buf is None or buf.size == 0:
                return
            # 🔴 增量推进：只对**新增**的部分跑（避免重复推理）
            done_samples = getattr(self, '_seg_done', 0)
            if buf.size <= done_samples:
                return
            new = buf[done_samples:]
            frames, _w = _rt.run_seg_side(new, self.seg_ir, self.seg_device,
                                           self.stride_ms)
            if self._seg_frames['p_speech']:
                self._seg_frames['p_speech'].extend(frames['p_speech'])
                self._seg_frames['p_dom'].extend(frames['p_dom'])
            else:
                self._seg_frames['p_speech'] = list(frames['p_speech'])
                self._seg_frames['p_dom'] = list(frames['p_dom'])
            self._seg_done = done_samples + new.size
            self._seg_error = None
        except Exception as _e:
            # 🔴🔴 ASR-045：**记录**异常（不再静默），但**保持**原有降级行为
            #   （旁路挂掉时 ASR 主链路仍要能跑）
            self._seg_error = '%s: %s' % (type(_e).__name__, _e)
            self._seg_frames = None

    def _seg_slice(self, t_start: float, t_end: float):
        if not self._seg_frames or not self._seg_frames['p_speech']:
            return None
        import numpy as np
        p = np.asarray(self._seg_frames['p_speech'], dtype=np.float64)
        d = np.asarray(self._seg_frames['p_dom'], dtype=np.float64)
        i0 = max(0, int(round(t_start * _rt.FPS)))
        i1 = min(len(p), int(round(t_end * _rt.FPS)))
        if i1 <= i0:
            return None
        return p[i0:i1], d[i0:i1]

    def _pcm_slice(self, t_start: float, t_end: float):
        import numpy as np
        if not self._buf:
            return np.zeros(0, dtype=np.float32)
        buf = np.concatenate(self._buf)
        base = self._t0 if self._t0 is not None else 0.0
        a = int(round((t_start - base) * SR))
        b = int(round((t_end - base) * SR))
        a = max(0, min(a, buf.size))
        b = max(a, min(b, buf.size))
        return np.ascontiguousarray(buf[a:b])

    def _clean_ranges(self, p_speech, t_start: float, t_end: float,
                      min_len_s: float = 0.3):
        """段内**连续干净**（p_speech ≥ 0.5）的区间 ⇒ App 取 x-vector 用。"""
        import numpy as np
        flags = np.asarray(p_speech) >= 0.5
        if flags.size == 0:
            return []
        ranges = []
        i = 0
        n = flags.size
        while i < n:
            if not flags[i]:
                i += 1
                continue
            j = i
            while j < n and flags[j]:
                j += 1
            s = t_start + i / _rt.FPS
            e = t_start + j / _rt.FPS
            if e - s >= min_len_s:
                ranges.append((round(s, 3), round(e, 3)))
            i = j
        return ranges


__all__ = ['SpeakerTracker', 'SR']
