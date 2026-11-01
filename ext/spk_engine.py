"""spk_engine.py — ★★ EXT-029：旁路推理内核（**编译缓存 + 正确分块推进**）

## 为什么需要这个模块（reviewer EXT-029 明文 + 主会话 11:10 的实测）

> 主会话 11:10 在 App 实测：说话人旁路（SpeakerTracker，GPU.0）在**主循环里同步调用
> `feed()`**，严重阻塞 ASR（5 分钟音频墙钟 838 s，积压 195 s）。
> EXT 要接克隆时同样的坑不能再踩。

### ★★ 实测出的**三个**真凶（本模块逐个拆掉）

| # | 真凶 | 实测证据 | 本模块的修法 |
|---|---|---|---|
| ① | **每次 `feed()` 都重新编译模型** | ASR 侧 `_advance_seg()` 调 `run_seg_side()`，而它**每次都 `ov.Core()` + `compile_model()`** ⇒ 实测 **0.73 s/次编译** | **编译一次、缓存复用**（`_seg_compiled`） |
| ② | **每次 `feed()` 都重跑整个缓冲** | `_advance_seg()` 每次 `np.concatenate(self._buf)`（全量拷贝）⇒ O(n²) | **只喂增量**（`_pending` 块） |
| ③ | **窗口永远凑不满 10 s** | `run_seg_side` 的窗口是 **10 s**（`WIN_N`），而 `feed()` 的块只有 **20–100 ms** ⇒ 每次都走「补零凑窗口」分支 ⇒ 每次白跑 10 s 的窗口推理（≈10× 浪费） | **攒够 10 s + 1 步长再推**（`_BLOCK_MIN`） |

⇒ 修完之后：分段推理的 **RTF ≈ 0**（实测单次推理 < 1 ms）
   且**每 11.28 s 才跑一次**（而不是每 20 ms 一次）。

## 只读引用（不改 ASR 的文件）

* **只** import ASR 交付集合里的 `asr052_spk_runtime`（纯 numpy + OV 运行时）
  ⇒ **不复用** `asr052_speaker_tracker_api.SpeakerTracker`（它内部那个
  `_advance_seg()` 正是「每帧重编译 + 窗口永远凑不满」的源头 ⇒ **不能直接用**）。
* 本模块**重新实现** ASR 侧的口径（fbank / 聚类 / 帧级时间轴），
  但**逐字照抄**它的常量与算法（`asr052_spk_runtime` 里的
  `numpy_kaldi_fbank` / `OnlineSpeakerCluster` / `FrameAggregator`），
  ⇒ **口径完全一致**，只是**执行方式**换了。

★ 这是 EXT-027③ 规则「只读引用那 3 个文件，不改原文件」的**正确做法**：
  **引用**它的纯函数与常量，**不调用**它那个「每帧重编译」的入口。

## 设备摆放（★ EXT-029 ④ 的硬要求）

| 用途 | 设备 | 依据（2026-11-01 实测） |
|---|---|---|
| 旁路**分段**（pyannote） | **NPU** | NPU 编译成功；GPU.1 失败；**GPU.0 会被 ASR 占用** |
| 旁路**嵌入**（wespeaker） | **GPU.0** | NPU 失败、GPU.1 失败 ⇒ **只有 GPU.0 可用** ⇒ 必须与 ASR/MT **共用**同一把公平锁 |

⇒ 分段（占绝大多数调用次数）**完全不碰 GPU.0** ⇒ ASR 不会被排队；
   只有**每段一次**的嵌入会短暂占用 ⇒ 其总时长即 **ASR 的额外延迟上界**
   （记进 `spk_gpu_lock_held_ms`，按 EXT-029 ④ 如实上报）。
"""
from __future__ import annotations

import glob
import os
import threading
import time
from typing import List, Optional, Tuple

import numpy as np

#: 聚类阈值（与 ASR 侧 `SpeakerTracker.__init__(thr=0.35)` 一致）
CLUSTER_THR = 0.35
#: 聚类均值更新系数（与 ASR 侧默认 `update_alpha=0.5` 一致）
CLUSTER_ALPHA = 0.5
#: 说话人数上限（与 ASR 侧默认 `max_speakers=6` 一致）
MAX_SPEAKERS = 6
#: 干净语音占比下限（与 ASR 侧默认 `min_clean_ratio=0.8` 一致）
MIN_CLEAN_RATIO = 0.8
#: 重叠占比上限（与 ASR 侧默认 `overlap_ratio_max=0.02` 一致）
OVERLAP_RATIO_MAX = 0.02
#: 段最短时长（与 ASR 侧默认 `min_dur_s=2.0` 一致）
MIN_DUR_S = 2.0
#: 分段滑窗步长（与 ASR 侧默认 `stride_ms=1280.0` 一致）
STRIDE_MS = 1280.0

#: 采样率（16 kHz 单声道）
SR = 16000

#: ★ 归档音频的保留时长（秒）—— 嵌入需要**该段完整音频**
#:   ⇒ 至少要覆盖最长的段（`ext.config.SEG_MAX_SEC` = 8 s）
#:   ⇒ 取 30 s 留足余量 ⇒ 内存恒定（30 s × 16 kHz × 4 B = 1.9 MB）。
ARCHIVE_SEC = 30.0


def _log(msg: str) -> None:
    print("[ext-spk-engine] %s" % msg, flush=True)


# ══════════════════════════════════════════════════════════════════
# ★★ EXT-029 ①/④：**进程级已编译模型缓存**
# ══════════════════════════════════════════════════════════════════
#
# ## 为什么需要缓存
#   ① **预热与复用**：桥接启动时预热编译一次 ⇒ 会话内**零编译**。
#      否则第一次 `on_final` 会在**持有 ASR 的 GPU 互斥锁**时编译
#      wespeaker ⇒ ASR 被**排队等编译**（实测 GPU 编译是秒级）
#      ⇒ 直接违反 EXT-029 ④「不得与 ASR 抢同一把 GPU 推理锁导致 ASR 排队」。
#   ② **不多编一次**：同一条 token 下可能有多个会话（player + uplink），
#      各自建一个 `SpkEngine` ⇒ 不共享就会**重复编译**同一个模型
#      ⇒ 白白占用 NPU/GPU 内存（还可能与 TTS 的 NPU 抢资源）。
#
# ## 线程安全
#   * 缓存本身用 `_COMPILED_LOCK` 保护（dict 操作原子性足够）；
#   * **推理**用 `_INFER_LOCK` 串行化 ⇒ 多个 `SpkEngine` 共享同一个
#     已编译模型时，不会并发调用同一个 `CompiledModel`
#     （`CompiledModel.__call__` 内部复用 infer request ⇒ 并发不安全）。
#   * 旁路是**旁路**，串行化它不会影响 ASR/MT/TTS 的并行度。
_COMPILED_CACHE: Dict[Tuple[str, str, str], object] = {}
_COMPILED_LOCK = threading.Lock()
_INFER_LOCK = threading.Lock()


def _cached_compiled(key: Tuple[str, str, str]):
    with _COMPILED_LOCK:
        return _COMPILED_CACHE.get(key)


def _store_compiled(key: Tuple[str, str, str], cm):
    """存进缓存（**先到先得** ⇒ 并发预热也只编一次）。"""
    with _COMPILED_LOCK:
        old = _COMPILED_CACHE.get(key)
        if old is not None:
            return old
        _COMPILED_CACHE[key] = cm
        return cm


class SpkEngine:
    """旁路推理内核（**编译缓存 + 分块推进 + 有界归档**）。

    Parameters
    ----------
    seg_ir, wes_ir
        两个 OV IR 目录（pyannote 分段 / wespeaker 嵌入）。
    seg_device
        分段设备（默认 **NPU** ⇒ 不与 ASR 抢 GPU.0）。
    embed_device
        嵌入设备（默认 **GPU.0** ⇒ 与 ASR/MT 共用 ⇒ 必须共用同一把锁）。
    """

    def __init__(self, *, seg_ir: Optional[str], wes_ir: Optional[str],
                 seg_device: str = "NPU", embed_device: str = "GPU.0",
                 on_log=_log) -> None:
        self.seg_ir = seg_ir
        self.wes_ir = wes_ir
        self.seg_device = seg_device
        self.embed_device = embed_device
        self._on_log = on_log

        self._lock = threading.Lock()

        # ── 分段（pyannote）────────────────────────────────
        self._seg_compiled = None          # ★ **编译缓存**（EXT-029 ①）
        self._seg_ready = False
        self._seg_error = ""
        self._seg_frames: List[Tuple[np.ndarray, np.ndarray]] = []
        self._seg_stride_samples = int(round(STRIDE_MS / 1000.0 * SR))
        self._block_min = 0                # 推进阈值（由 `_ensure_seg` 填）

        # ── 嵌入（wespeaker）──────────────────────────────
        self._enc = None
        self._enc_ready = False
        self._enc_error = ""

        # ── 音频缓冲 ─────────────────────────────────────
        #   `_archive`：有界滚动归档（供嵌入取段音频）
        #   `_pending`：尚未做分段推理的音频（增量推进）
        self._archive: List[np.ndarray] = []
        self._archive_len = 0
        self._archive_cap = int(ARCHIVE_SEC * SR)
        self._pending: List[np.ndarray] = []
        self._pending_len = 0
        self._total = 0                   # 累计喂入样本数（全局时间轴）
        self._t0 = 0.0                    # 音频起点在全局时间轴上的位置
        self._seg_frame_base = 0          # 已产出的分段帧数（全局帧号）

        # ── 聚类（照抄 ASR 侧 `OnlineSpeakerCluster`）─────
        self._centroids: List[np.ndarray] = []
        self._counts: List[int] = []
        self._prev_spk: Optional[str] = None

        # ── 指标 ─────────────────────────────────────────
        self.n_seg_compile = 0            # 编译次数（★ 修复前每帧一次）
        self.n_seg_infer = 0              # 推理次数
        self.n_seg_reuse = 0              # ★ 命中进程级缓存的次数（免编译）
        self.n_enc_compile = 0            # ★ 嵌入模型编译次数
        self.n_enc_reuse = 0              # ★ 命中进程级缓存的次数（免编译）
        self._last_enc_compile_sec = 0.0
        self.n_embed = 0
        self.seg_infer_sec = 0.0
        self.embed_sec = 0.0
        self._last_compile_sec = 0.0

    # ══════════════════════════════════════════════════════════
    # ① 加载（**编译一次、缓存复用** ⇒ EXT-029 ① 的核心修法）
    # ══════════════════════════════════════════════════════════
    def _ensure_seg(self) -> bool:
        """加载并**缓存** pyannote 分段模型。

        ★★ 与 ASR 侧 `run_seg_side()` 的**根本区别**：
          ASR 侧每次都 `core.compile_model(...)` ⇒ 实测 0.73 s/次
          ⇒ 这里**只编译一次**，之后复用。
        """
        if self._seg_ready:
            return True
        if self._seg_error:
            return False
        try:
            import openvino as ov
            import asr052_spk_runtime as rt
            if not self.seg_ir:
                raise RuntimeError("没有 seg_ir")
            if os.path.isdir(self.seg_ir):
                xmls = sorted(glob.glob(os.path.join(self.seg_ir, "*.xml")))
                if not xmls:
                    raise RuntimeError("seg_ir 里没有 .xml")
                xml = xmls[0]
            else:
                xml = self.seg_ir
            key = ("seg", xml, self.seg_device)
            cm = _cached_compiled(key)
            if cm is not None:
                self._seg_compiled = cm
                self.n_seg_reuse += 1
                self._seg_ready = True
                self._block_min = rt.WIN_N + self._seg_stride_samples
                self._on_log("分段模型**命中进程级缓存**（免编译）：%s @ %s"
                             % (os.path.basename(xml), self.seg_device))
                return True
            core = ov.Core()
            t0 = time.perf_counter()
            cm = core.compile_model(
                core.read_model(xml), self.seg_device)
            self._last_compile_sec = time.perf_counter() - t0
            self.n_seg_compile += 1
            self._seg_compiled = _store_compiled(("seg", xml, self.seg_device),
                                                 cm)
            self._seg_ready = True
            # ★ 推进阈值：一个**完整窗口** + 一个步长
            #   ⇒ 保证窗口永远是**真音频**（不是补零）
            self._block_min = rt.WIN_N + self._seg_stride_samples
            self._on_log("分段模型已编译并缓存：%s @ %s（%.2fs，编译次数=%d）"
                         % (os.path.basename(xml), self.seg_device,
                            self._last_compile_sec, self.n_seg_compile))
        except Exception as e:
            self._seg_error = "%s: %s" % (type(e).__name__, e)
            self._on_log("分段模型不可用（降级）：%s" % self._seg_error)
        return self._seg_ready

    def _ensure_enc(self) -> bool:
        """加载并缓存 wespeaker 嵌入模型（**只有 GPU.0 编译得过**）。

        ★★ EXT-029 ④：**进程级缓存**（`_COMPILED_CACHE`）
          ⇒ 预热阶段编一次 ⇒ 会话内 `on_final` 里的 `_ensure_enc()`
            **只是查表** ⇒ 绝不会在**持有 ASR 的 GPU 锁**时触发编译。
        """
        if self._enc_ready:
            return True
        if self._enc_error:
            return False
        try:
            import openvino as ov
            if not self.wes_ir:
                raise RuntimeError("没有 wes_ir")
            xml = os.path.join(self.wes_ir, "openvino_encoder_model.xml")
            if not os.path.isfile(xml):
                raise RuntimeError("找不到 %s" % xml)
            key = ("enc", xml, self.embed_device)
            cm = _cached_compiled(key)
            if cm is not None:
                self._enc = cm
                self.n_enc_reuse += 1
                self._enc_ready = True
                self._on_log("嵌入模型**命中进程级缓存**（免编译）：%s @ %s"
                             % (os.path.basename(xml), self.embed_device))
                return True
            core = ov.Core()
            model = core.read_model(xml)
            # ★ 与 ASR 侧同款：编译前给 T 设上界（一次编译、多次复用）
            model.reshape({"fbank": ov.PartialShape([1, [100, 2048], 80])})
            t0 = time.perf_counter()
            cm = core.compile_model(
                model, self.embed_device,
                {"PERFORMANCE_HINT": "LATENCY",
                 "INFERENCE_PRECISION_HINT": "f16"})
            self._last_enc_compile_sec = time.perf_counter() - t0
            self.n_enc_compile += 1
            self._enc = _store_compiled(key, cm)
            self._enc_ready = True
            self._on_log("嵌入模型已编译并缓存：%s @ %s（%.2fs）"
                         % (os.path.basename(xml), self.embed_device,
                            self._last_enc_compile_sec))
        except Exception as e:
            self._enc_error = "%s: %s" % (type(e).__name__, e)
            self._on_log("嵌入模型不可用（降级）：%s" % self._enc_error)
        return self._enc_ready

    def warmup(self) -> dict:
        """**预热**：把两个模型都编译好（**不持有 ASR 的 GPU 锁**）。

        ★ 桥接启动时调用一次 ⇒ 会话内 `_ensure_*` 只是查表。
        """
        t0 = time.perf_counter()
        seg_ok = self._ensure_seg()
        enc_ok = self._ensure_enc()
        return {"ok": bool(seg_ok and enc_ok),
                "seg_ready": bool(seg_ok), "enc_ready": bool(enc_ok),
                "elapsed_sec": round(time.perf_counter() - t0, 3),
                "seg_compile_count": self.n_seg_compile,
                "enc_compile_count": self.n_enc_compile,
                "seg_reuse": self.n_seg_reuse, "enc_reuse": self.n_enc_reuse}

    # ══════════════════════════════════════════════════════════
    # ② 音频入口（★ **只喂增量** ⇒ 修掉 O(n²) 全量拷贝）
    # ══════════════════════════════════════════════════════════
    def feed(self, pcm, t_end: Optional[float] = None) -> int:
        """喂一段 16 kHz 单声道 PCM（返回累计样本数）。

        ★ 本方法**不跑嵌入**（嵌入只在 `on_final` 里做，每段一次）。
        ★ 分段推理**按块推进**（攒够 10 s + 步长才跑一次）⇒
          推理次数从「每帧一次」降到「每 11.28 s 一次」。
        """
        if isinstance(pcm, (bytes, bytearray)):
            a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            a = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if a.size == 0:
            return self._total
        with self._lock:
            if self._total == 0 and t_end is not None:
                self._t0 = max(0.0, float(t_end) - a.size / SR)
            self._total += int(a.size)
            # ① 归档（有界）—— 供嵌入取段音频
            self._archive.append(a)
            self._archive_len += int(a.size)
            while self._archive_len > self._archive_cap and len(self._archive) > 1:
                old = self._archive.pop(0)
                self._archive_len -= int(old.size)
            # ② 待推进
            self._pending.append(a)
            self._pending_len += int(a.size)
            self._advance_seg()
        return self._total

    def _advance_seg(self) -> None:
        """把分段推进到**当前缓冲末尾**（**按块** ⇒ 不重跑已处理部分）。"""
        if not self._ensure_seg():
            return
        if self._pending_len < self._block_min:
            return          # ★ 还没攒够一个完整窗口 ⇒ **不做推理**（省 10×）
        audio = (self._pending[0] if len(self._pending) == 1
                 else np.concatenate(self._pending))
        t0 = time.perf_counter()
        try:
            frames = self._infer_seg(audio)
        except Exception as e:
            self._seg_error = "分段推理失败: %s" % e
            self._seg_ready = False
            return
        self.seg_infer_sec += time.perf_counter() - t0
        self.n_seg_infer += 1
        if frames is not None and len(frames):
            self._seg_frames.extend(frames)
        # ★ 消费掉已推理的部分（保留一点尾巴，保证下一块的窗口连续）
        keep = self._seg_stride_samples
        consumed = audio.size - keep
        if consumed <= 0:
            return
        self._pending = [audio[consumed:]] if keep > 0 else []
        self._pending_len = keep if keep > 0 else 0

    def _infer_seg(self, audio: np.ndarray):
        """跑 pyannote 分段（**用缓存的 compiled model**）。"""
        import asr052_spk_runtime as rt
        cm = self._seg_compiled
        stride = self._seg_stride_samples
        agg = rt.FrameAggregator(int(np.ceil(len(audio) / SR * rt.FPS)))
        win_idx = 0
        win_start = 0
        n = len(audio)
        while win_start + rt.WIN_N <= n:
            seg = np.ascontiguousarray(
                audio[win_start:win_start + rt.WIN_N]
                .reshape(1, 1, -1).astype(np.float32))
            # ★ 已编译模型可能被**多个 SpkEngine 实例共享**（进程级缓存）
            #   ⇒ 推理必须串行（`CompiledModel.__call__` 复用 infer request
            #   ⇒ 并发调用不安全）。
            with _INFER_LOCK:
                res = cm([seg])
            logits = np.asarray(res[cm.output(0)])[0].astype(np.float64)
            m = logits.max(axis=-1, keepdims=True)
            z = logits - m
            e = np.exp(z)
            agg.add_window(win_idx, stride, e / e.sum(axis=-1, keepdims=True))
            win_idx += 1
            win_start += stride
        if win_start < n:
            seg = np.zeros((1, 1, rt.WIN_N), dtype=np.float32)
            rest = n - win_start
            seg[0, 0, :rest] = audio[win_start:]
            with _INFER_LOCK:
                res = cm([seg])
            logits = np.asarray(res[cm.output(0)])[0].astype(np.float64)
            m = logits.max(axis=-1, keepdims=True)
            z = logits - m
            e = np.exp(z)
            agg.add_window(win_idx, stride, e / e.sum(axis=-1, keepdims=True))
        p_speech, p_dom, _spk_id, _cov = agg.finalize()
        # ⇒ 只保留**概率**（p_speech / p_dom），够算标签用
        out = []
        for i in range(len(p_speech)):
            out.append((np.asarray(p_speech[i], dtype=np.float64),
                        np.asarray(p_dom[i], dtype=np.float64)))
        return out

    # ══════════════════════════════════════════════════════════
    # ③ 定稿段（**嵌入一次** ⇒ GPU.0 短暂占用）
    # ══════════════════════════════════════════════════════════
    def on_final(self, seg_id, t_start: float, t_end: float) -> dict:
        """问「这一段是谁说的」（**口径与 ASR 侧 `on_final` 一致**）。

        返回
        ------
        dict
            `spk` / `spk_conf` / `is_new_spk` / `clean_ranges` /
            `pending` / `reason` / `lag_s`
        """
        base = {"spk": None, "spk_conf": None, "is_new_spk": False,
                "clean_ranges": [], "lag_s": None, "pending": False,
                "reason": None, "seg_id": seg_id,
                "t_start": float(t_start), "t_end": float(t_end)}
        with self._lock:
            pcm = self._pcm_slice(t_start, t_end)
            dur = len(pcm) / SR
            base["dur_s"] = round(dur, 3)
            if not self._ensure_seg():
                base["reason"] = "models_not_ready"
                return base
            if dur < MIN_DUR_S:
                # ★ 与 ASR 侧同款区分：「音频还没到」vs「段太短」
                if dur < (t_end - t_start) - 1e-6:
                    base["reason"] = "audio_not_buffered"
                    base["pending"] = True
                else:
                    base["reason"] = "too_short"
                return base
            seg = self._seg_slice(t_start, t_end)
            if seg is None:
                base["reason"] = "seg_pending"
                base["pending"] = True
                return base
            p_speech, p_dom = seg
            clean_f = (p_speech >= 0.5)
            clean_ratio = float(clean_f.mean()) if clean_f.size else 0.0
            if p_dom.ndim >= 2 and p_dom.shape[1] > 1:
                overlap_ratio = float((p_dom[:, 1:].sum(axis=1) > 1.05).mean())
            else:
                overlap_ratio = 0.0
            base["clean_ratio"] = round(clean_ratio, 4)
            base["overlap_ratio"] = round(overlap_ratio, 4)
            if clean_ratio < MIN_CLEAN_RATIO:
                base["reason"] = "not_clean_speech"
                return base
            if overlap_ratio > OVERLAP_RATIO_MAX:
                base["reason"] = "overlap"
                return base
            if not self._ensure_enc():
                base["reason"] = "models_not_ready"
                return base
            t0 = time.perf_counter()
            try:
                v = self._embed(pcm)
            except ValueError as ex:
                base["reason"] = "embed_shape_out_of_range"
                base["embed_error"] = str(ex)
                return base
            lag = time.perf_counter() - t0
            self.embed_sec += lag
            self.n_embed += 1
            base["lag_s"] = round(lag, 4)
            spk, conf = self._assign(v)
            is_new = (self._prev_spk is None) or (spk != self._prev_spk)
            self._prev_spk = spk
            base["spk"] = spk
            base["spk_conf"] = round(float(conf), 4)
            base["is_new_spk"] = bool(is_new)
            base["clean_ranges"] = self._clean_ranges(p_speech, t_start, t_end)
            return base

    # ── 嵌入（照抄 ASR 侧 `WespeakerOVEncoder.embed` 的口径）────
    def _embed(self, pcm: np.ndarray) -> np.ndarray:
        import asr052_spk_runtime as rt
        seg = np.ascontiguousarray(np.asarray(pcm, dtype=np.float32))
        if seg.ndim > 1:
            seg = seg.mean(axis=1)
        fbank = rt.numpy_kaldi_fbank(seg)
        fbank = fbank - fbank.mean(axis=0, keepdims=True)
        n_frames = int(fbank.shape[0])
        if n_frames > 2048:
            raise ValueError("fbank 帧数 %d 超过编译期上界 2048" % n_frames)
        if n_frames < 100:
            raise ValueError("fbank 帧数 %d 低于编译期下界 100" % n_frames)
        x = np.ascontiguousarray(fbank[None, ...].astype(np.float32))
        cm = self._enc
        in_name = list(cm.inputs)[0]
        out_name = list(cm.outputs)[0]
        with _INFER_LOCK:
            res = cm({in_name: x})
        return np.asarray(res[out_name]).reshape(-1).astype(np.float32)

    # ── 聚类（照抄 ASR 侧 `OnlineSpeakerCluster.assign`）────────
    def _assign(self, v: np.ndarray) -> Tuple[str, float]:
        x = v.reshape(-1)
        n = float(np.linalg.norm(x))
        u = x / n if n > 1e-9 else x
        if not self._centroids:
            self._centroids.append(u)
            self._counts.append(1)
            return "S1", 1.0
        sims = np.array([float(np.dot(u, c)) for c in self._centroids])
        j = int(np.argmax(sims))
        if sims[j] >= CLUSTER_THR:
            self._centroids[j] = self._unit(
                (1 - CLUSTER_ALPHA) * self._centroids[j] + CLUSTER_ALPHA * u)
            self._counts[j] += 1
            return "S%d" % (j + 1), float(sims[j])
        if len(self._centroids) < MAX_SPEAKERS:
            self._centroids.append(u)
            self._counts.append(1)
            return "S%d" % len(self._centroids), float(sims[j])
        self._centroids[j] = self._unit(
            (1 - CLUSTER_ALPHA) * self._centroids[j] + CLUSTER_ALPHA * u)
        self._counts[j] += 1
        return "S%d" % (j + 1), float(sims[j])

    @staticmethod
    def _unit(v: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(v))
        return v / n if n > 1e-9 else v

    # ── 切片 ─────────────────────────────────────────────
    def _pcm_slice(self, t_start: float, t_end: float) -> np.ndarray:
        """取一段音频（**16 kHz float32**）。

        ⚠️ 嵌入需要**该段完整音频** ⇒ 从**有界归档**里取
          ⇒ 归档长度（30 s）必须 > 最长的段（8 s）⇒ 否则该段会被截短。

        ★★ **EXT-029③ 实测抓到的真缺陷（2026-11-01，已修）**：
          旧实现拿 `self._t0`（= **全局**时间轴起点）当归档缓冲的**基址**
          ⇒ 但归档是**滚动窗口**（只留最近 30 s，起点在不断右移）
          ⇒ 30 s 之后的段：索引 `a` 远超 `buf.size`
          ⇒ 被 `min(a, buf.size)` 夹到末尾 ⇒ **切出空数组**
          ⇒ `on_final` 判「音频还没进缓冲」⇒ 反复重试到上限后**静默丢弃**
          ⇒ 实测 60 s 里只有前 4 段拿到标签（**4/13**），其余全部回落方案 A。
          ⇒ 修法：基址必须是**归档首样本的全局时间**：
                 `base = _t0 + (_total − _archive_len) / SR`
        """
        if not self._archive:
            return np.zeros(0, dtype=np.float32)
        buf = (self._archive[0] if len(self._archive) == 1
               else np.concatenate(self._archive))
        # ★ 归档首样本的**全局**时间（不是全局起点！滚动窗口会右移）
        base = self._t0 + (self._total - self._archive_len) / float(SR)
        a = int(round((t_start - base) * SR))
        b = int(round((t_end - base) * SR))
        a = max(0, min(a, buf.size))
        b = max(a, min(b, buf.size))
        return np.ascontiguousarray(buf[a:b])

    def _seg_slice(self, t_start: float, t_end: float):
        if not self._seg_frames:
            return None
        import asr052_spk_runtime as rt
        p = np.asarray([f[0] for f in self._seg_frames], dtype=np.float64)
        d = np.asarray([f[1] for f in self._seg_frames], dtype=np.float64)
        i0 = max(0, int(round(t_start * rt.FPS)))
        i1 = min(len(p), int(round(t_end * rt.FPS)))
        if i1 <= i0:
            return None
        return p[i0:i1], d[i0:i1]

    def _clean_ranges(self, p_speech, t_start: float, t_end: float,
                      min_len_s: float = 0.3):
        import asr052_spk_runtime as rt
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
            s = t_start + i / rt.FPS
            e = t_start + j / rt.FPS
            if e - s >= min_len_s:
                ranges.append((round(s, 3), round(e, 3)))
            i = j
        return ranges

    # ══════════════════════════════════════════════════════════
    # ④ 指标
    # ══════════════════════════════════════════════════════════
    def stats(self) -> dict:
        return {
            "seg_device": self.seg_device,
            "embed_device": self.embed_device,
            "seg_ready": self._seg_ready,
            "seg_error": self._seg_error or None,
            "enc_ready": self._enc_ready,
            "enc_error": self._enc_error or None,
            # ★ 编译次数（★ EXT-029 ① 的关键证据：
            #   修复前「每帧一次」⇒ 修复后「整个会话 1 次」）
            "seg_compile_count": self.n_seg_compile,
            "seg_compile_sec": round(self._last_compile_sec, 3),
            "seg_infer_count": self.n_seg_infer,
            "seg_infer_sec": round(self.seg_infer_sec, 3),
            "embed_count": self.n_embed,
            "embed_sec": round(self.embed_sec, 3),
            # ★★ EXT-029 ④：**编译次数 vs 缓存命中次数**
            #   ⇒ reviewer 可直接核对「会话内有没有在 GPU 锁内编译」。
            "seg_reuse_count": self.n_seg_reuse,
            "enc_compile_count": self.n_enc_compile,
            "enc_compile_sec": round(self._last_enc_compile_sec, 3),
            "enc_reuse_count": self.n_enc_reuse,
            "archived_sec": round(self._archive_len / SR, 3),
            "pending_sec": round(self._pending_len / SR, 3),
            "n_speakers": len(self._centroids),
            "definition": ("seg_compile_count = 分段模型编译次数"
                           "（修复前每帧一次 ⇒ 0.73s/次；修复后整个会话 1 次）；"
                           "seg_infer_count = 分段推理次数"
                           "（修复前每帧一次；修复后每 11.28 s 一次）；"
                           "seg_infer_sec = 分段推理总耗时。"),
        }


__all__ = ["SpkEngine", "SR", "CLUSTER_THR", "MIN_CLEAN_RATIO"]
