"""APP-086(2)：克隆说话人音色编排层（a–f）＋ **APP-089** 的 EXT v0.3.2 三项行为。

移植口径（来自 `live_dub_ext` claude-dev:ext/clone_voice.py，**只读参考**，未改 EXT）：
  a 无标签不沿用上一句音色 / b 临时标签 / c 先出临时音色 /
  d **整句 clean + ASR 文本（ICL 参考）** ← **APP-089 已删除**（见下）/ e 参考冻结 / f 克隆工作移出 ASR 线程。

🔴🔴🔴 **APP-089（2026-11-09）：本层改为「只用 x-vector」**
──────────────────────────────────────────────────────────────
reviewer 结论（`status/app/CORRECTIONS_APP.md` §2a）：
> 真实音频上 ICL 克隆（参考音频 + ASR 文本）不稳定：用户实跑 60 次 TTS 里有 22 次
> 撞上帧上限；140 段里 68 段只剩字幕；Dave's Take 6 分钟回放 ICL 的 CER 20.1 %
> 而 x-vector 是 8.4 %，撞上限 2 比 0。参考 ≥8.7 s 或拼接参考还会让模型说英语腔。

⇒ **本层不再产出任何 `.txt`（ICL 文本）**：
  · 旧的 `collect_reference()` / `_write_reference()`（ICL 参考 + 文本）**已删除**；
  · 「说话人参考」改为 **x-vector 专用**（EXT v0.3.2 的 `XV_*` 口径，见下）；
  · `tts_cuda_sidecar.py` 侧**不再读 `.txt`** ⇒ 固定 `xvec_only=True`（不再传 `ref_text`）。
🔴 **不移植 EXT 的 `EXT_CLONE_ICL` 开关**（reviewer 明文：App 只用 x-vector）。
🔴 **「说话人参考」的落点**：由 App 侧的 `speaker_voice.xv_reference_ticket()`
  承担（干净 + 有标签的句子拼成一段区间）⇒ **本层不做登记**（见类 docstring）。

🔴🔴 **APP-089 §2c：新增三项 EXT v0.3.2 行为**
  1. **self_ref**：句子所属说话人**还没有登记音色**时，用**这句自己的音频**
     （≥ `SELF_REF_MIN_S` = 1.5 s）做 x-vector 克隆 ⇒ **从第一句就开始克隆**。
     🔴 **取代** APP-086 的「无标签 ⇒ 预设 A」规则；
     🔴 **但** worker 侧「不许沿用**上一个说话人**的克隆音色」这条兜底**保留**。
  2. **说话人参考**（EXT `XV_*`）：把这个人**干净、有标签**的句子拼起来
     ⇒ ≥ `XV_FIRST_S`(3.0 s) 首次写入、≥ `XV_UPGRADE_S`(8.0 s) 升级**一次**、
     最长 `XV_MAX_S`(10.0 s)、之后**冻结**（只产 x-vector，**不写 .txt**）。
  3. **换人切段**：克隆模式下对已经 ready 的段落做 `split_by_speaker`
     （窗口 1.6/2.0/2.5 s、min_sim 0.30、margin 0.10、最短段 3.2 s）
     ⇒ **用自己的编码器**、**在克隆线程上编译**，**绝不放接收线程 / ASR 线程**。

🔴🔴🔴 **接线口径（APP-086②，本轮裁定）**：**复用 App 既有的那一份旁路与音色表**
──────────────────────────────────────────────────────────────
上一版（§159 落盘的那份）`CloneVoices` **自带** `SpeakerBridge` +
`SpeakerVoiceTable` ⇒ 与 App GUI/CLI 各自已有的 `_spk_voices` **并存**
⇒ **双旁路**（两份 wespeaker + 两份 pyannote 同时跑 ⇒ 抢 NPU/集显
⇒ 两套标签互相打架 ⇒ 必然串音）。
⇒ 现在：**旁路（`bridge`）与音色表（`table`）都由 App 注入**
⇒ 全程**只有一份**旁路 + 一份音色表 ⇒ **不可能双旁路**。
⇒ 独立运行（不注入）时仍可自建旁路 ⇒ 保持「可单测」的形态。

**a（无标签不许沿用上一句音色）** 的落点分两层，缺一不可：
  ① **App 侧**（`live_caption_app.py`）：合成前用本模块算出「最近已登记说话人」
     （cos ≥ `MIN_SIM_NEAREST`）⇒ 把**那个 spk** 交给 worker；
  ② **worker 侧**（`tts_worker.py`）：按句绑定模式下 `spk=None` ⇒ **回落预设 A**
     ⇒ **绝不**沿用上一句的克隆音色（结构性保证）。
⇒ 只做 ① 不做 ②：最近说话人算不出来时仍会串音；只做 ② 不做 ①：
  无标签句全是预设 A（音色对，但**不是**本人音色 ⇒ 切换慢）。

**b（临时标签）**：定稿即给一个临时标签（最近质心，cos ≥ `MIN_SIM_PROVISIONAL`）
⇒ 旁路之后的正式标签覆盖它。

**d/e（ICL 参考 + 冻结）**：🔴🔴 **APP-089 已删除 ICL**（reviewer §2a：真实音频上 ICL 不稳定）
⇒ 本层**不再写任何 `.txt`**；「参考」只剩 **x-vector** 口径（EXT v0.3.2 的 `XV_*`，见文件头）。
⇒ NPU 闸门不依赖它（APP-088③：以 NPU 数字为闸门，CUDA 数字可选）。

**f（克隆工作移出 ASR/音频线程）**：最近质心要在 wespeaker 上做嵌入
⇒ 放在本模块自己的 `clone-policy` 线程里算 ⇒ ASR/音频线程只做「入队」。
"""
from __future__ import annotations

import os
import queue as _queue
import threading
import time as _time
from typing import Optional

import numpy as np

SR = 16000
KEEP_S = 90.0

# ── APP-086② a/b 的两个门槛 ──────────────────────────────────────────
MIN_SIM_NEAREST = 0.25     # a：无标签句 ⇒ 最近已登记说话人的最小余弦
MIN_SIM_PROVISIONAL = 0.40  # b：定稿时的临时标签最小余弦
MIN_SIM_DEFAULT = 0.20      # 内部默认（与移植版一致）

# ── APP-089 §2c-2：EXT v0.3.2 的「说话人参考」门槛（**x-vector 专用**）────────
# 🔴 **只产 x-vector，不写 .txt**（reviewer §2a：ICL 在真实音频上不稳定）。
XV_FIRST_S = 3.0      # 首次写入门槛：攒够 3.0 s「干净、有标签」的句子
XV_UPGRADE_S = 8.0    # 升级门槛：到 8.0 s 允许**升级一次**，之后冻结
XV_MAX_S = 10.0       # 单个参考最长 10.0 s
# 🔴🔴🔳 **APP-094①**：默认 = **keep first**（保留第一份 x-vector 参考，不再 8 s 升级）
# ⚠️ 这是 `speaker_voice.py` 里同名常量的**副本** ⇒ 两处必须同口径，
#    否则行为分叉（`speaker_voice.XV_UPGRADE` 才是**真正生效**的那一份：
#    状态机在 `speaker_voice.xv_reference_ticket` 里）。
XV_UPGRADE = os.environ.get('LIVECAP_XV_UPGRADE', '0').strip() == '1'

# ── APP-089 §2c-1：self_ref（用**这句自己的音频**做 x-vector）──────────────
SELF_REF_MIN_S = 1.5  # 这句自己的音频 ≥ 1.5 s 才够提 x-vector

# ── APP-089 §2c-3：换人切段（split_by_speaker）参数 ──────────────────────────
# 🔴 口径来自 EXT v0.3.2 `ext/clone_voice.py`（**只读移植**，未改 EXT）。
SPLIT_MIN_SEG_S = 3.2      # 最短段 3.2 s（太短的段不切）
SPLIT_WIN_S = (1.6, 2.0, 2.5)   # 三个切分窗口（秒）
SPLIT_MIN_SIM = 0.30       # 质心识别的最小余弦
SPLIT_MIN_MARGIN = 0.10    # 第一名与第二名的最小差距

_CACHE_MAX = 256       # 最近质心缓存上限（段数）


def _seg_int(seg_id) -> int:
    return int(str(seg_id).rsplit("_", 1)[-1])


class CloneVoices:
    """APP-086② 的**策略层**：无标签句的最近说话人 / 临时标签 / ICL 参考收集。

    ⚠️ **本类不做音色登记**：登记仍由 App 既有的 `_pump_spk_voices()`
    （`register_spk_voice` ⇒ worker 侧算 x-vector）负责
    ⇒ **不产生第二条登记路径** ⇒ 不会双登记、不会互相覆盖。
    """

    def __init__(self, on_log=print, bridge=None, table=None,
                 pcm_getter=None, span_getter=None,
                 manage_reference=True, on_nearest=None):
        import sys as _sys
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in _sys.path:
            _sys.path.insert(0, _here)

        self._log = on_log
        self.sv = table
        self.br = bridge
        self._own_bridge = False
        self._own_table = False

        if self.br is None:
            # 独立运行（单测 / 脚本）⇒ 自建旁路（App 侧**不会**走这条分支）
            import speaker_tracker
            self.br = speaker_tracker.SpeakerBridge(
                on_log=lambda m: on_log("[spk] %s" % m), enabled=True)
            self._own_bridge = True
        if self.sv is None:
            import speaker_voice
            self.sv = speaker_voice.SpeakerVoiceTable(
                on_event=lambda k, p: on_log("[spk] %s %s" % (k, p)))
            self._own_table = True

        self._pcm_getter = pcm_getter or (lambda: (np.zeros(0, dtype=np.float32), 0.0))
        self._span_getter = span_getter or (lambda seg: None)

        self._lock = threading.Lock()
        self._span = {}          # seg -> (t_start, t_end)
        self._text = {}          # seg -> ASR 文本（ICL 参考用）
        self._nearest = {}       # seg -> (spk, cos)（最近质心缓存；**带余弦**⇒ a/b 两个门槛都能用）
        self._emb = {}           # seg -> 嵌入向量（**缓存**⇒ 质心长出来后可零成本重算）
        self._pushed = {}        # seg -> (spk, cos)（已推给 worker 的最近说话人）
        self._on_nearest = on_nearest
        self._q = _queue.Queue()
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._worker, name="clone-policy",
                                     daemon=True)
        self._th.start()

        # d/e：整句 clean 参考（CUDA 路线）
        # 🔴🔴🔴 APP-089 §2a：**ICL 已删除** ⇒ 不再收集候选句、不再写参考 wav。
        #   ⇒ 保留 `paths` 字段只为**兼容旧调用方**（恒为空字典）。
        self._manage_reference = bool(manage_reference)
        self._cands = {}         # spk -> [(seg, dur, pcm, text)]（ICL 已删 ⇒ 恒空）
        self._ref_dur = {}       # spk -> 已写入参考的秒数（ICL 已删 ⇒ 恒空）
        self._upgraded = {}      # spk -> 是否已升级过（冻结）
        self.paths = {}          # spk -> 参考 wav 路径（ICL 已删 ⇒ 恒空）
        self.n_ref = 0
        # 🔴🔴🔳 **APP-089 §2b 修**：`LIVECAP_CLONE_VOICES_DIR` 的语义
        #   reviewer 原文：「**会话开始时清空克隆目录**
        #   （`%LOCALAPPDATA%\Confucius4LiveCaption\clone_voices`
        #     **或** `LIVECAP_CLONE_VOICES_DIR`）」
        #   ⇒ 这**两个是同一个目录的两种写法**（二选一），
        #     **不是**「基目录」关系。
        #   ⚠️ 旧实现把它当**基目录** ⇒ 又拼了
        #     `Confucius4LiveCaption/clone_voices`
        #     ⇒ 实际落在 `<env>/Confucius4LiveCaption/clone_voices`
        #     ⇒ 与 reviewer 口径**不一致**（验收要检查的就是这个目录）。
        #   ⇒ 修法：**给了环境变量就直接用它当克隆目录**；
        #     没给才用默认的 `%LOCALAPPDATA%\Confucius4LiveCaption\clone_voices`。
        _env_dir = (os.environ.get("LIVECAP_CLONE_VOICES_DIR") or '').strip()
        if _env_dir:
            self.dir = _env_dir
        else:
            self.dir = os.path.join(
                os.environ.get("LOCALAPPDATA", "."),
                "Confucius4LiveCaption", "clone_voices")
        try:
            os.makedirs(self.dir, exist_ok=True)
        except Exception:
            pass

        self.n_nearest = 0
        self.n_hit = 0
        # 🔴🔴🔴 APP-089 §2c-1 / §2c-3 的计数器
        self.n_self_ref = 0      # self_ref 取到的 PCM 段数
        self.n_split = 0         # 切点总数
        self.n_split_calls = 0   # split_by_speaker 调用次数
        self.n_split_ready = 0   # App 侧入口：确实切出多块的段数
        self._split_enc = None   # 自己的 WeSpeaker 编码器（克隆线程上编译）
        self._split_enc_failed = False
        self._cents = []         # 质心快照（归一化）
        # 🔴🔴🔳 APP-089 §2c-3：**切段请求队列 + 结果表**
        #   reviewer 明文：「用**自己的编码器**，在**克隆线程上编译**，
        #   **绝不能放在接收线程或 ASR 线程上**」
        #   ⇒ 旧实现（CLI 侧）**直接在接收线程**调 `split_ready_segments`
        #     ⇒ **违反线程纪律**（编码器首次编译会卡住接收线程）。
        #   ⇒ 现在改成**异步**：接收线程只 `request_split()`（入队即返回）
        #     ⇒ 真正的切分 + 编码器编译都在**切段线程**上做。
        self._split_q = _queue.Queue()
        self._split_res = {}     # seg -> {'n_parts': int, 'n_split': int}
        self._split_th = threading.Thread(
            target=self._split_worker, name="clone-split", daemon=True)
        self._split_th.start()

    # ── APP-089 §2c-3：**换人切段（异步，克隆侧线程）**────────────────
    def request_split(self, seg, buf, segs):
        """🔴🔴🔳 APP-089 §2c-3：**请求**切段（**只入队，立即返回**）。

        ## 线程纪律（reviewer 明文）
        > 用**自己的编码器**，在**克隆线程上编译**，
        > **绝不能放在接收线程或 ASR 线程上**。

        ⇒ 本方法**只做入队**（微秒级）⇒ 接收线程 / ASR 线程**零阻塞**。
        ⇒ 真正的切分与编码器编译在 `_split_worker` 线程上完成。

        参数
        ----
        seg : int
            段号（用于取回结果）。
        buf : np.ndarray
            PCM（16 kHz mono，**调用方须保证在切分完成前不被回收**
            ⇒ 本方法**立即复制**所需片段）。
        segs : list[(int, int)]
            段边界（**样本下标**，指向 `buf`）。
        """
        try:
            arr = np.asarray(buf, dtype=np.float32).reshape(-1)
            if arr.size == 0 or not segs:
                return False
            # 🔴 **立即复制**要用的片段（避免调用方的环形缓冲被挤掉）
            a = max(0, int(segs[0][0]))
            b = min(arr.size, int(segs[0][1]))
            if b <= a:
                return False
            piece = np.ascontiguousarray(arr[a:b], dtype=np.float32)
            self._split_q.put((int(seg), piece, [(0, piece.size)]))
            return True
        except Exception as e:
            self._log("[spk] 切段请求失败（忽略）：%s" % e)
            return False

    def poll_split(self, seg):
        """🔴🔴🔳 取回某段的切分结果（**没有就是 None**）。

        返回 `{'n_parts': int, 'n_split': int}`：
        - `n_parts` = 切出的块数（**1** = 没换人）
        - `n_split` = 切点数（`n_parts - 1`）
        """
        with self._lock:
            return self._split_res.get(int(seg))

    def _split_worker(self) -> None:
        """🔴🔴🔳 **切段线程**（`clone-split`）：真正的切分都在这里做。

        🔴 **这是 reviewer 要求的线程纪律的落点**：
        * 编码器（`_split_encoder`）**在这里懒加载 + 编译**；
        * 切分（`split_by_speaker`）**在这里算**；
        * ⇒ 接收线程 / ASR 线程**完全不受影响**。
        """
        while not self._stop.is_set():
            try:
                item = self._split_q.get(timeout=0.25)
            except _queue.Empty:
                continue
            if item is None:
                continue
            try:
                seg, piece, rngs = item
                parts = self.split_by_speaker(piece, rngs)
                n_parts = len(parts)
                with self._lock:
                    self._split_res[int(seg)] = {
                        'n_parts': n_parts,
                        'n_split': max(0, n_parts - 1),
                    }
            except Exception as e:
                self._log("[spk] 切段失败（忽略）：%s" % e)

    # ── APP-089 §2b：**会话开始清空**（克隆目录 + 策略层缓存）────────
    def reset_session(self) -> None:
        """🔴🔴🔳 APP-089 §2b：**会话开始时清空克隆目录与本层缓存**。

        reviewer 原话（`CORRECTIONS_APP.md` APP-089 §2b）：
        > **每个会话用自己的克隆参考**：会话开始时清空克隆目录
        > （`%LOCALAPPDATA%\\Confucius4LiveCaption\\clone_voices` 或
        > `LIVECAP_CLONE_VOICES_DIR`），同时清空 `_spk_bind`/`_spk_voices`/
        > 策略层的缓存。
        > 原因：EXT 的实际情况是，文件名被复用时，旁边旧的 `<ref>.txt`
        > 悄悄把克隆切成了 ICL，用的还是错的文本。

        🔴 **本方法只清本层**（目录 + 缓存）；
        `_spk_bind`/`_spk_voices` 在 **worker 侧** ⇒ 由 App 调
        `tts.clear_spk_voices()` + 新增的 `tts.clear_spk_bind()` 清。
        """
        # ① 清克隆目录（**只删本目录下的文件**，不删目录本身）
        try:
            import shutil
            if os.path.isdir(self.dir):
                for _n in os.listdir(self.dir):
                    _p = os.path.join(self.dir, _n)
                    try:
                        if os.path.isfile(_p):
                            os.remove(_p)
                        elif os.path.isdir(_p):
                            shutil.rmtree(_p, ignore_errors=True)
                    except Exception:
                        pass
        except Exception as e:
            self._log("[spk] 清空克隆目录失败（忽略）：%s" % e)
        # ② 清策略层缓存
        with self._lock:
            self._span.clear()
            self._text.clear()
            self._nearest.clear()
            self._emb.clear()
            self._pushed.clear()
            self._cands.clear()
            self._ref_dur.clear()
            self._upgraded.clear()
            self.paths.clear()
            self.n_ref = 0
            self.n_self_ref = 0
            self.n_split = 0
            self.n_split_calls = 0
            self.n_split_ready = 0
            # 🔴🔴🔳 APP-089 §2b：**切段结果也要清**（跨会话残留 ⇒ 串段）
            self._split_res.clear()
        # 🔴🔴🔳 切段队列里的**旧请求**也要清（避免上一会话的段被切）
        try:
            while True:
                try:
                    self._split_q.get_nowait()
                except _queue.Empty:
                    break
        except Exception:
            pass
        self._log("[spk] 会话开始：克隆目录与策略层缓存已清空")

    # ── ASR 线程：定稿时登记（**只入队，不算**）──────────────────
    def on_segment(self, seg_id, t_start: float, t_end: float,
                   text: str = "") -> None:
        """定稿一段 ⇒ 记下区间/文本 ⇒ 请求算「最近质心」。

        🔴 **不在这里做嵌入**（f）⇒ ASR/音频线程零阻塞。
        """
        seg = _seg_int(seg_id)
        with self._lock:
            self._span[seg] = (float(t_start), float(t_end))
            if text:
                self._text[seg] = str(text)
        self._q.put(seg)

    # ── 策略线程：算最近质心 ──────────────────────────────────────
    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                seg = self._q.get(timeout=0.25)
            except _queue.Empty:
                continue
            try:
                v = self._embed(seg)
                if v is None:
                    continue
                with self._lock:
                    self._emb[seg] = v
                    if len(self._emb) > _CACHE_MAX:
                        for k in list(self._emb.keys())[:len(self._emb) // 2]:
                            self._emb.pop(k, None)
                spk, sim = self._nearest_from_vec(v)
                with self._lock:
                    self._nearest[seg] = (spk, sim)
                if spk:
                    self.n_hit += 1
                self._try_push(seg)
            except Exception as e:
                self._log("[spk] 最近说话人计算失败（忽略）：%s" % e)

    def _embed(self, seg):
        """对这一句做嵌入（**只做一次**⇒ 缓存；质心长出来后可零成本重算）。

        🔴 与移植版一致：编码器有编译上限 ⇒ 超过 6 s 取中间 6 s。
        """
        tr = getattr(self.br, "_tracker", None)
        if tr is None:
            return None
        enc = getattr(tr, "_enc", None)
        clu = getattr(tr, "_clu", None)
        if enc is None or clu is None:
            return None
        span = self._span_getter(seg) or self._span.get(seg)
        if not span:
            return None
        try:
            buf, t0 = self._pcm_getter()
        except Exception:
            return None
        buf = np.asarray(buf, dtype=np.float32).reshape(-1)
        i0 = int((float(span[0]) - float(t0)) * SR)
        i1 = int((float(span[1]) - float(t0)) * SR)
        if i0 < 0 or i1 > buf.size or (i1 - i0) < int(1.0 * SR):
            return None
        pcm = buf[i0:i1]
        if pcm.size > int(6.0 * SR):
            m = (pcm.size - int(6.0 * SR)) // 2
            pcm = pcm[m:m + int(6.0 * SR)]
        try:
            with tr._lock:
                v = np.asarray(enc.embed(pcm, SR), dtype=np.float64).reshape(-1)
        except Exception as e:
            self._log("[spk] 最近说话人嵌入失败：%s" % e)
            return None
        n = float(np.linalg.norm(v))
        if n <= 0:
            return None
        return v / n

    def _nearest_from_vec(self, v):
        """拿**缓存的嵌入** ⇒ 与**当前**质心比 ⇒ `(spk, cos)`。

        🔴 质心是随会话增长的（旁路每识别出一个新说话人就加一个）
        ⇒ 同一个嵌入在不同时间点的「最近说话人」可能不同 ⇒ 允许重算。
        """
        tr = getattr(self.br, "_tracker", None)
        if tr is None:
            return None, 0.0
        clu = getattr(tr, "_clu", None)
        if clu is None:
            return None, 0.0
        try:
            with tr._lock:
                cents = list(clu.centroids)
                labels = [clu._label(k) for k in range(len(cents))]
        except Exception:
            return None, 0.0
        if not cents:
            return None, 0.0
        best, best_s = None, -1.0
        for k, c in enumerate(cents):
            s = float(np.dot(v, np.asarray(c).reshape(-1)))
            if s > best_s:
                best, best_s = labels[k], s
        if best is None:
            return None, 0.0
        self.n_nearest += 1
        return best, best_s

    def pump(self) -> None:
        """质心长出来之后**零成本重算**最近说话人（嵌入已缓存）⇒ 推给 worker。

        🔴 由 App 的**周期性泵**调用（GUI `_pump_spk_voices` / CLI `_cli_pump_spk_voices`）
        ⇒ 嵌入算在策略线程里（f）⇒ 这里只做**余弦比较**（微秒级）。
        """
        with self._lock:
            segs = list(self._emb.keys())
        for seg in segs:
            try:
                v = self._emb.get(seg)
                if v is None:
                    continue
                spk, sim = self._nearest_from_vec(v)
                with self._lock:
                    self._nearest[seg] = (spk, sim)
                self._try_push(seg)
            except Exception:
                continue

    def _try_push(self, seg) -> None:
        """把「最近**已登记**说话人」推给 worker（**走既有 `spk_update` 通道**）。

        🔴🔴🔳 **为什么不在提交时直接把 spk 塞进命令**：
          worker 的晚到标签通道（`_spk_bind`）**只在命令里 spk 为空时**才生效
          ⇒ 一旦提前塞了「最近说话人」，旁路后来的**官方标签就被挡住**
          ⇒ 可能用**错的**说话人 ⇒ 比回落预设 A 更糟。
        ⇒ 现在：**官方标签**仍走 `_spk_push_update`；**最近说话人**走同一条
          `spk_update` 通道（后写覆盖先写）⇒ 官方标签**后到**时自动胜出。
        🔴 **已有确认标签 ⇒ 一律不推**（官方优先）。
        """
        if self._on_nearest is None:
            return
        try:
            if self.sv.spk_of(seg):
                return                       # 已有官方标签 ⇒ 不动
        except Exception:
            return
        spk, sim = self._cached(seg) or (None, 0.0)
        if not spk or sim < MIN_SIM_NEAREST:
            return
        if not self._has_voice(spk):
            return                           # 该说话人还没登记音色 ⇒ 不推
        key = (spk, round(float(sim), 3))
        with self._lock:
            if self._pushed.get(seg) == key:
                return
            self._pushed[seg] = key
        try:
            self._on_nearest(seg, spk, float(sim))
        except Exception as e:
            self._log("[spk] 推最近说话人失败（忽略）：%s" % e)

    def _cached(self, seg_id):
        with self._lock:
            return self._nearest.get(_seg_int(seg_id))

    # ── 对外：合成前解析音色（**只读缓存，不阻塞**）──────────────
    def nearest_registered(self, seg_id, min_sim: float = MIN_SIM_NEAREST
                           ) -> Optional[str]:
        """a：**无标签**句 ⇒ 最近**已登记**（有音色）的说话人。

        🔴 **只认「已登记音色」的说话人** ⇒ 找不到就返回 `None`
        ⇒ 调用方回落**预设 A**（绝不用别人的音色）。
        🔴 **b 优先**：先取 cos ≥ `MIN_SIM_PROVISIONAL` 的**临时标签**
        （更可靠）⇒ 没有才放宽到 `min_sim`（a）。
        """
        seg = _seg_int(seg_id)
        spk, sim = self._cached(seg) or (None, 0.0)
        if not spk:
            return None
        if sim >= MIN_SIM_PROVISIONAL and self._has_voice(spk):
            return spk
        if sim >= float(min_sim) and self._has_voice(spk):
            return spk
        return None

    def provisional_spk(self, seg_id, min_sim: float = MIN_SIM_PROVISIONAL
                        ) -> Optional[str]:
        """b：定稿时的**临时标签**（最近质心，cos ≥ `min_sim`）。

        ⚠️ 临时标签**只是标签** ⇒ 不参与登记门槛的 conf 判定
        ⇒ 旁路正式标签到达后覆盖它。
        """
        spk, sim = self._cached(seg_id) or (None, 0.0)
        if not spk:
            return None
        return spk if sim >= float(min_sim) else None

    def _has_voice(self, spk) -> bool:
        try:
            return bool(self.sv.has_voice(spk))
        except Exception:
            return False

    def has_label(self, seg_id) -> bool:
        """这一句**已经有**（正式或临时）标签吗？"""
        seg = _seg_int(seg_id)
        try:
            if self.sv.spk_of(seg):
                return True
        except Exception:
            pass
        with self._lock:
            return bool(self._nearest.get(seg, (None, 0.0))[0])

    # ── APP-089 §2a：**ICL 已删除**（原 d/e：写 `<spk>_<n>.wav` + 同名 `.txt`）──
    # 🔴🔴 **本层不再产出任何 `.txt`** ⇒ 见文件头「只用 x-vector」。
    #
    # 替代物（EXT v0.3.2 的 `XV_*` 口径）由 **App 侧的 `speaker_voice`**
    # 承担（`xv_reference_ticket()` ⇒ 干净有标签句子的拼接区间）
    # ⇒ **本层不做音色登记**（不变，见类 docstring）。

    # ── APP-089 §2c-1：**self_ref**（用**这句自己的音频**做 x-vector）────
    def self_ref_pcm(self, seg_id):
        """🔴🔴🔴 APP-089 §2c-1：**这句自己的音频**（≥ `SELF_REF_MIN_S`）⇒ PCM。

        ## 为什么需要（EXT v0.3.2 的行为，reviewer 要求移植）
        句子所属说话人**还没有登记音色**时，EXT 不用预设 A、也不用别人的音色，
        而是**直接用这句自己的音频**提 x-vector ⇒ **从第一句就开始克隆**。

        🔴 **本层只给 PCM**（不落盘、不算向量）：
        向量必须由 **worker 自己的 speaker encoder** 算（ASR-026/§50 铁律）
        ⇒ App 侧把这段 PCM 交给 worker（`spk_voice_seg` 命令）⇒ worker 算。

        🔴 **返回 None 的两种情形**：
        ① 这句的音频还没进环形缓冲（或已被挤掉）⇒ 拿不到；
        ② 长度 < `SELF_REF_MIN_S`（1.5 s）⇒ 提不出可靠的 x-vector。
        """
        seg = _seg_int(seg_id)
        span = self._span_getter(seg) or self._span.get(seg)
        if not span:
            return None
        try:
            buf, t0 = self._pcm_getter()
            buf = np.asarray(buf, dtype=np.float32).reshape(-1)
            i0 = int((float(span[0]) - float(t0)) * SR)
            i1 = int((float(span[1]) - float(t0)) * SR)
            if i0 < 0 or i1 > buf.size or (i1 - i0) < int(SELF_REF_MIN_S * SR):
                return None
            pcm = buf[i0:i1]
            if pcm.size > int(8.0 * SR):
                m = (pcm.size - int(8.0 * SR)) // 2
                pcm = pcm[m:m + int(8.0 * SR)]
            with self._lock:
                self.n_self_ref += 1
            return np.ascontiguousarray(pcm, dtype=np.float32)
        except Exception as e:
            self._log("[spk] self_ref 取音频失败（忽略）：%s" % e)
            return None

    # ── APP-089 §2c-3：**换人切段**（自己的编码器，克隆线程上编译）────
    def _split_encoder(self):
        """🔴🔴🔴 APP-089 §2c-3：**自己的** WeSpeaker 编码器实例。

        🔴 **为什么要自己一份**：旁路那份在 tracker 的锁后面
        ⇒ 借它算切点会**卡住旁路**（旁路是 ASR 线程的旁路 ⇒ 影响 ASR）。
        ⇒ 本方法在**克隆策略线程**上懒加载 + 编译
        （EXT v0.3.2 `ext/clone_voice.py:_split_encoder` 同思路）。

        ⚠️ **失败不抛异常**：返回 None ⇒ 调用方按「不切段」处理。
        """
        if self._split_enc is not None:
            return self._split_enc
        if self._split_enc_failed:
            return None
        tr = getattr(self.br, "_tracker", None)
        src = getattr(tr, "_enc", None) if tr is not None else None
        ir = getattr(tr, "wes_ir", None) if tr is not None else None
        if src is None or not ir:
            return None
        try:
            enc = type(src)(ir, getattr(src, "device", "GPU.0"), range_lo=60)
            z = np.zeros(int(max(SPLIT_WIN_S) * SR), np.float32) + 1e-3
            for w in SPLIT_WIN_S:                 # 每个窗口长度各编译一次
                enc.embed(z[:int(w * SR)], SR)
            self._split_enc = enc
            self._log("[spk] 说话人切分编码器已就绪（克隆线程编译）")
        except Exception as e:
            self._split_enc_failed = True
            self._log("[spk] 说话人切分不可用：%s" % e)
            return None
        return self._split_enc

    def _split_centroids(self):
        """🔴 **质心快照**（归一化）—— 切点判定的依据。"""
        tr = getattr(self.br, "_tracker", None)
        clu = getattr(tr, "_clu", None) if tr is not None else None
        if clu is not None and tr._lock.acquire(timeout=0.05):
            try:
                cs = [np.asarray(c, np.float64).reshape(-1)
                      for c in clu.centroids]
                self._cents = [c / (np.linalg.norm(c) + 1e-9) for c in cs]
            finally:
                tr._lock.release()
        return self._cents or []

    def _split_ident(self, enc, cents, x):
        """🔴 窗口 ⇒ 质心识别（`SPLIT_MIN_SIM` / `SPLIT_MIN_MARGIN`）。"""
        v = np.asarray(enc.embed(x, SR), np.float64).reshape(-1)
        v = v / (np.linalg.norm(v) + 1e-9)
        sims = sorted(((float(v @ c), k) for k, c in enumerate(cents)), reverse=True)
        if sims[0][0] >= SPLIT_MIN_SIM and sims[0][0] - sims[1][0] >= SPLIT_MIN_MARGIN:
            return sims[0][1], sims[0][0] - sims[1][0]
        return None, 0.0

    def _split_best_cut(self, enc, cents, x):
        """🔴 **最佳切点**（粗扫 0.5 s → 精修 ±0.25 s → 吸附最安静 20 ms）。"""
        L = x.size / float(SR)
        lo, hi = SPLIT_WIN_S[0], L - SPLIT_WIN_S[0]
        if hi < lo:
            return None

        def score(t):
            m = int(t * SR)
            wl = max(w for w in SPLIT_WIN_S if w <= t + 1e-6)
            wr = max(w for w in SPLIT_WIN_S if w <= L - t + 1e-6)
            kl, ml = self._split_ident(enc, cents, x[m - int(wl * SR):m])
            kr, mr = self._split_ident(enc, cents, x[m:m + int(wr * SR)])
            return min(ml, mr) if (kl is not None and kr is not None
                                   and kl != kr) else None

        best = None
        for t in np.arange(lo, hi + 1e-6, 0.5):
            sc = score(t)
            if sc is not None and (best is None or sc > best[0]):
                best = (sc, t)
        if best is None:
            return None
        for t in (best[1] - 0.25, best[1] + 0.25):
            if lo <= t <= hi:
                sc = score(t)
                if sc is not None and sc > best[0]:
                    best = (sc, t)
        # 吸附到最安静的 20 ms 帧（EXT 同款）
        c = int(best[1] * SR)
        fr = int(0.02 * SR)
        a0 = max(int(lo * SR), c - int(0.25 * SR))
        a1 = min(int(hi * SR), c + int(0.25 * SR))
        if a1 - a0 > fr:
            e = [float(np.mean(x[i:i + fr] ** 2))
                 for i in range(a0, a1 - fr, fr // 2)]
            c = a0 + int(np.argmin(e)) * (fr // 2) + fr // 2
        return c

    def split_by_speaker(self, buf, segs):
        """🔴🔴🔴 APP-089 §2c-3：**按说话人变化切段**（EXT v0.3.2 移植）。

        参数
        ----
        buf : np.ndarray
            整段 PCM（16 kHz mono）。
        segs : list[(int, int)]
            段边界（**样本下标**，指向 `buf`）。

        返回
        ----
        切分后的段边界列表（外边界不变 ⇒ 只在段**内部**多切点）。

        ⚠️ **不改 ASR**：本方法只提供「段内说话人变化点」的判定；
        段的**文本**由 ASR 一次性解码 ⇒ **无词级时间戳 ⇒ 文本无法再切**
        （证据：`live_caption_app.py:1547` `OVEngine._finalize` 对整段
        `audio_accum` 做**一次** `generate_with_prefix`；
        `streaming_asr.py` / `seg_stream.py` / `backends.py` /
        `segment_encoder_backend.py` 里 **零** 处 `timestamp`/`align`）。
        ⇒ App 侧用它做**「混合说话人段」识别 + 音色归属**（见 STATUS §161）。
        """
        if not segs or not any((b - a) >= int(SPLIT_MIN_SEG_S * SR)
                               for a, b in segs):
            return segs
        cents = self._split_centroids()
        if len(cents) < 2:
            return segs
        # 🔴🔴🔴 **修真实缺陷**：本方法**从不调用** `_split_encoder()`
        #   ⇒ `self._split_enc` **恒为 None** ⇒ `split_by_speaker` **恒直接返回**
        #   ⇒ **APP-089 §2c-3「换人切段」完全死了**
        #   ⇒ 现在补上（懒加载 ⇒ 首次调用时编译）。
        #   🔴 线程纪律（reviewer 明文）：编码器**自己一份**，
        #   在**克隆线程上编译** ⇒ 不卡旁路（不影响 ASR）。
        enc = self._split_encoder()
        if enc is None:
            return segs
        out = []
        for a, b in segs:
            parts = [(a, b)]
            for _round in range(2):
                nxt = []
                for p0, p1 in parts:
                    c = None
                    if p1 - p0 >= int(SPLIT_MIN_SEG_S * SR):
                        try:
                            c = self._split_best_cut(
                                enc, cents, np.asarray(buf[p0:p1], np.float32))
                        except Exception as e:
                            self._log("[spk] 说话人切分失败：%s" % e)
                    if c:
                        nxt += [(p0, p0 + c), (p0 + c, p1)]
                        with self._lock:
                            self.n_split += 1
                    else:
                        nxt.append((p0, p1))
                if len(nxt) == len(parts):
                    break
                parts = nxt
            out += parts
        with self._lock:
            self.n_split_calls += 1
        return out

    def split_ready_segments(self, segs) -> list:
        """🔴🔴🔳 APP-089 §2c-3：**对「已 ready」的段落做换人切段**（App 侧入口）。

        ## 为什么要有这个入口（reviewer 原文）
        > **换人切段**：克隆模式下，对已经 ready 的段落做 `split_by_speaker`。
        > 按质心识别，窗口 1.6/2.0/2.5 s，min_sim 0.30，margin 0.10，
        > 最短段 3.2 s。用**自己的编码器**，在**克隆线程上编译**，
        > **绝不能放在接收线程或 ASR 线程上**。

        ## 与 EXT 的对应
        EXT `ext/bridge.py:1953`：
            `ready = _cvs.split_by_speaker(self._buf, ready)`
        ⇒ EXT 在**派发段之前**切 ⇒ 切点会变成**新的段**。
        ⚠️ **App 侧不能照抄**：App 的 ASR **一次解码整段**（无词级时间戳）
        ⇒ 切出来的子段**没有文本** ⇒ 不能变成新的待合成句
        （`clone_voice.split_by_speaker` 的 docstring 已写明这一点）。

        ## App 侧的实际用法（**不改变合成行为**）
        ⇒ 用它做**「混合说话人段」的识别与统计**：
          段被切成 >1 块 ⇒ 说明**这一段里换了人**
          ⇒ 记 `n_split`（切点总数）＋ 段号 ⇒ 供验收报告
          （APP-089 §4「换人切段：切段次数」）。

        ## 🔴 线程纪律（reviewer 明文）
        * **绝不在接收线程 / ASR 线程上跑** ⇒ 本方法**只登记**，
          真正的切分在**克隆策略线程**上做（见 `poll_split`）。
        * 编码器**自己一份**（`_split_encoder`）⇒ 不卡旁路。

        参数
        ----
        segs : list[(int, int)]
            段边界（**样本下标**，指向 PCM 缓冲）。

        返回
        ----
        切分后的段边界列表（外边界不变）。
        """
        try:
            buf, t0 = self._pcm_getter()
            buf = np.asarray(buf, dtype=np.float32).reshape(-1)
            if buf.size < int(SPLIT_WIN_S[0] * SR):
                return segs
            out = self.split_by_speaker(buf, segs)
            if len(out) > len(segs):
                with self._lock:
                    self.n_split_ready += 1
            return out
        except Exception as e:
            self._log("[spk] 换人切段失败（忽略）：%s" % e)
            return segs

    def reference_path(self, spk: str) -> Optional[str]:
        """🔴 APP-089 §2a：**不再有参考 wav 文件** ⇒ 恒返回 None。

        （原实现返回 ICL 参考 wav 的路径；ICL 已删除。）
        """
        return None

    def stats(self) -> dict:
        with self._lock:
            return {
                'n_nearest': self.n_nearest,
                'n_hit': self.n_hit,
                'n_ref': self.n_ref,
                'cached': len(self._nearest),
                'paths': dict(self.paths),
                'n_self_ref': self.n_self_ref,
                'n_split': self.n_split,
                'n_split_calls': self.n_split_calls,
                'n_split_ready': self.n_split_ready,
                'split_enc_ready': self._split_enc is not None,
            }

    def close(self) -> None:
        self._stop.set()
        if self._own_bridge:
            try:
                self.br.stop()
            except Exception:
                pass


__all__ = ['CloneVoices', 'SR', 'KEEP_S',
           'MIN_SIM_NEAREST', 'MIN_SIM_PROVISIONAL', 'MIN_SIM_DEFAULT',
           'XV_FIRST_S', 'XV_UPGRADE_S', 'XV_MAX_S', 'XV_UPGRADE',
           'SELF_REF_MIN_S',
           'SPLIT_MIN_SEG_S', 'SPLIT_WIN_S', 'SPLIT_MIN_SIM',
           'SPLIT_MIN_MARGIN']
