"""speaker_bypass.py — ★★ EXT-029：**说话人旁路必须独立线程，不得反压 ASR**

## 为什么有这个模块（reviewer EXT-029 明文 + 主会话 11:10 的实测）

> 主会话 11:10 在 App 实测：说话人旁路（SpeakerTracker，GPU.0）在**主循环里同步调用
> `feed()`**，严重阻塞 ASR（5 分钟音频墙钟 838 s，积压 195 s）。
> EXT 要接克隆时同样的坑不能再踩。

⇒ 本模块把旁路做成**有界队列 + 独立 worker 线程**：

```
   音频入口（ASR 主路径）                旁路 worker 线程（独立）
   ─────────────────────                ────────────────────────
   feed()  ── put_nowait ──▶ [队列(有界)] ── get() ──▶ tracker.feed()
        （**永不阻塞**）         │  满了 ⇒          tracker.on_final()
                                │  丢**旧**块              │
                                └─ n_drop++                 └─▶ 异步回填 spk
```

## 三条铁律（对应 EXT-029 ①②④）

1. **音频入口只做 `put_nowait`** ⇒ 队列满时**丢最旧的块**并计数
   （`spk_queue_drop`），**绝不阻塞** ASR 主路径 / 定稿 / MT / TTS。
2. **spk 结果异步回填** ⇒ 未到就用**上一句音色或预设 A**（方案 A），
   **不等**（EXT-027③ 规则 7）。
3. **不得与 ASR 抢同一把 GPU 推理锁导致 ASR 排队** ⇒
   * 旁路**分段**（pyannote）跑在 `seg_device`（默认 **NPU**，实测可用）
     ⇒ **完全不碰 GPU.0**；
   * 旁路**嵌入**（wespeaker）实测**只有 GPU.0 能编译**
     ⇒ 它与 ASR/MT **共用同一把** `_FairLock`（FIFO 公平锁）
     ⇒ 不会饿死 ASR（公平 FIFO ⇒ ASR 最多多等一次 embed），
       并把「旁路持锁总时长」记下来 ⇒ 就是 **ASR 的额外延迟上界**，
       按 EXT-029 ④ 如实报进 STATUS / summary.json。

## 只读引用（不改 ASR 的文件，也不复制它的研发目录）

按 EXT-027③ 规则：只读引用 App 包内 `app/asr_spk/` 的**那 3 个交付文件**：

    asr052_speaker_tracker_api.py   ← 入口（SpeakerTracker）
    asr052_spk_runtime.py            ← 运行时内核（fbank / 嵌入 / 聚类 / 分段）
    asr_thread_defaults.py           ← 限线程

⇒ 只把 `app/asr_spk` 加进 `sys.path`，**不复制、不改写**。

## 铁律

* **只落内存**：克隆向量（x-vector）只在内存里，不落盘、不进包
  （EXT-027③ 规则 6）。
* **不阻塞**：本模块**任何**对外方法都不会等待 GPU 推理完成。
* **安静降级**：旁路加载失败 / 模型缺失 ⇒ `available=False`，
  整体行为与「没接旁路」**逐字一致**（绝不打断音频链路）。
"""
from __future__ import annotations

import os
import queue
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

#: 旁路队列深度（**有界** ⇒ 内存不会随会话时长增长）。
#: 60 s @ 20 ms/帧 = 3000 块 ⇒ 64 块 ≈ 1.3 s 的缓冲，足够旁路追平。
DEFAULT_QUEUE_MAXSIZE = 64

#: 单个待定稿段的最大重试次数（音频一直没到就放弃 ⇒ 走方案 A）。
DEFAULT_MAX_PENDING_TRIES = 60

#: 旁路**分段**（pyannote）的默认设备。
#: ★ 实测（2026-11-01）：pyannote 在 **NPU** 上编译成功、在 GPU.1 上失败；
#:   而 ASR/MT 都在 **GPU.0** ⇒ 分段放 NPU ⇒ **完全不与 ASR 抢 GPU.0**。
DEFAULT_SEG_DEVICE = "NPU"

#: 旁路**嵌入**（wespeaker）的默认设备。
#: ★ 实测（2026-11-01）：wespeaker 在 NPU 上编译失败、GPU.1 上失败
#:   （动态形状 + 编译期 PartialShape 改写）⇒ **只有 GPU.0 可用**
#:   ⇒ 它必须与 ASR/MT **共用同一把** device_lock（见 `device_lock` 参数）。
DEFAULT_EMBED_DEVICE = "GPU.0"


def _log(msg: str) -> None:
    print("[ext-spk] %s" % msg, flush=True)


class SpeakerBypass:
    """★ EXT-029：说话人旁路（**独立线程 + 有界队列 + 异步回填**）。

    Parameters
    ----------
    device
        嵌入（wespeaker）设备。默认 GPU.0（**实测唯一可用的设备**）。
    seg_device
        分段（pyannote）设备。默认 NPU（**实测可用 ⇒ 不与 ASR 抢 GPU.0**）。
    device_lock
        与 ASR/MT **共用**的那把 GPU 互斥锁（`ext.pipeline._FairLock`）。
        ⚠️ **必须**传同一把锁 ⇒ 旁路的嵌入不会**另开一把锁**把 ASR 饿死
        （EXT-029 ④）。为 None ⇒ 不加锁（**仅自测用**，真实路径禁止）。
    on_label
        回调 `(seg_id, t_start, t_end, spk, info) -> None`：
        旁路拿到标签时**异步回填**给上层（上层据此改绑音色 / 显示字幕标签）。
    """

    def __init__(self, *, device: str = DEFAULT_EMBED_DEVICE,
                 seg_device: str = DEFAULT_SEG_DEVICE,
                 device_lock=None,
                 queue_maxsize: int = DEFAULT_QUEUE_MAXSIZE,
                 max_pending_tries: int = DEFAULT_MAX_PENDING_TRIES,
                 on_label: Optional[Callable] = None,
                 on_log: Callable[[str], None] = _log) -> None:
        self.device = device
        self.seg_device = seg_device
        self.device_lock = device_lock
        self.queue_maxsize = max(1, int(queue_maxsize))
        self.max_pending_tries = max(1, int(max_pending_tries))
        self._on_label = on_label
        self._on_log = on_log

        # ── 状态 ──────────────────────────────────────────────
        self._engine = None
        self.available = False
        self.load_error = ""
        self._loaded = False

        # ── 有界队列（★ EXT-029 ① 的核心）──────────────────
        self._q: "queue.Queue[Optional[Tuple[object, float]]]" = \
            queue.Queue(maxsize=self.queue_maxsize)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # ── 待定稿段（**异步问**，不等）────────────────────
        self._pending: List[Tuple[str, float, float, int]] = []
        self._pending_lock = threading.Lock()

        # ── 指标（★ EXT-029 ③ 要求进 summary.json）─────────
        self.n_drop = 0            # spk_queue_drop：因队列满而丢掉的块数
        self.n_feed = 0            # 成功投递的块数
        self.n_worker_busy_ms = 0.0  # spk_worker_busy_ms：worker 的总忙时
        self.n_label = 0           # 拿到的标签数
        self.n_no_label = 0        # 明确「无标签」的段数（走方案 A）
        self.n_final_req = 0       # 请求定稿的段数
        self._lock_held_ms = 0.0   # 旁路持 device_lock 的总时长（ASR 额外延迟上界）
        self._max_lag_ms = 0.0     # 最长的「标签晚到」时长
        self._last_label: Optional[Tuple[str, str]] = None   # (seg_id, spk)

    # ══════════════════════════════════════════════════════════
    # ① 加载（惰性 + 安静降级）
    # ══════════════════════════════════════════════════════════
    def _app_spk_dir(self) -> str:
        """定位 App 包内的 `app/asr_spk/`（**只读引用**）。"""
        from .app_root import resolve_app_root
        root = resolve_app_root()
        if not root:
            return ""
        d = os.path.join(root, "app", "asr_spk")
        return d if os.path.isdir(d) else ""

    def _asset_paths(self) -> Tuple[str, str]:
        """定位两个 IR（pyannote 分段 / wespeaker 嵌入）。

        ★ 探测顺序（与 ASR 侧 `_find_ir` 同款）：
          ① 环境变量 `EXT_SPK_SEG_IR` / `EXT_SPK_WES_IR`；
          ② 包内相对布局 `<包根>/models/spk/<名字>/<精度>`。
        ⚠️ 找**不到**就返回空串 ⇒ 旁路安静降级（**绝不臆造路径**）。
        """
        from .app_root import resolve_app_root
        root = resolve_app_root() or ""

        def _find(env_name: str, sub: str) -> str:
            v = os.environ.get(env_name)
            if v and os.path.isdir(v):
                return v
            if not root:
                return ""
            for prec in ("fp32", "fp16"):
                cand = os.path.join(root, "models", "spk", sub % prec)
                if os.path.isdir(cand):
                    return cand
            return ""

        seg = _find("EXT_SPK_SEG_IR", os.path.join("pyannote_seg_3_0", "%s"))
        wes = _find("EXT_SPK_WES_IR", "wespeaker-resnet34-%s")
        return seg, wes

    def _load(self) -> bool:
        """加载旁路引擎（**只读引用** ASR 的交付文件 + 自研编译缓存内核）。"""
        if self._loaded:
            return self.available
        self._loaded = True
        d = self._app_spk_dir()
        if not d:
            self.load_error = "no_app_spk_dir"
            self.available = False
            self._on_log("旁路不可用：找不到 App 的 app/asr_spk/（降级）")
            return False
        seg_ir, wes_ir = self._asset_paths()
        if not seg_ir or not wes_ir:
            self.load_error = "no_spk_ir"
            self.available = False
            self._on_log("旁路不可用：找不到说话人 IR（seg=%r wes=%r）（降级）"
                         % (bool(seg_ir), bool(wes_ir)))
            return False
        try:
            if d not in os.sys.path:
                os.sys.path.insert(0, d)
            from .spk_engine import SpkEngine
            self._engine = SpkEngine(seg_ir=seg_ir, wes_ir=wes_ir,
                                     seg_device=self.seg_device,
                                     embed_device=self.device,
                                     on_log=self._on_log)
            self.available = True
            self._on_log("旁路已加载（只读引用 %s；分段@%s 嵌入@%s）"
                         % (os.path.basename(d), self.seg_device, self.device))
            # ★★ EXT-029 ④：**预热**（编译两个模型）**在这里做**
            #   ⇒ 之后的 `on_final` 里 `_ensure_enc()` 只是查表
            #   ⇒ **绝不会在持有 ASR 的 GPU 互斥锁时触发编译**
            #   ⇒ ASR 不会被「等编译」排队。
            try:
                wr = self._engine.warmup()
                self._on_log("旁路模型预热：%s" % wr)
            except Exception as e:
                self._on_log("旁路模型预热失败（降级）：%s" % e)
        except Exception as e:
            self.load_error = "%s: %s" % (type(e).__name__, e)
            self.available = False
            self._engine = None
            self._on_log("旁路不可用（降级：字幕无说话人标签）：%s"
                         % self.load_error)
        return self.available

    # ══════════════════════════════════════════════════════════
    # ② 音频入口（★ EXT-029 ①：**只做 put_nowait，永不阻塞**）
    # ══════════════════════════════════════════════════════════
    def feed(self, pcm, t_end: Optional[float] = None) -> bool:
        """投喂一段 16 kHz 单声道 PCM 到旁路队列。

        ★★ **本方法绝不阻塞**：队列满 ⇒ **丢最旧的块**并计数
          （`spk_queue_drop`）⇒ 立即返回。
          ⇒ ASR 主路径 / 定稿 / MT / TTS **绝不会被旁路拖住**。

        ★★ **本方法也绝不加载模型**（EXT-029 ①）：
          加载/编译**只发生在 worker 线程**（`_run` 的第一步）
          ⇒ 第一次 `feed()` 不会因为「import + 编译」卡住 ASR 主路径
          （旧实现在这里调 `_load()` ⇒ 首次 feed 阻塞数秒 ⇒ **违反 ①**）。

        ★★ **即使引擎还没就绪也照常入队**：
          worker 加载完会**接着处理队列里的旧块** ⇒
          分段引擎不会因为「加载慢」而**丢掉开头几秒音频**
          （否则分段窗口对不齐 ⇒ 标签全错）。

        Returns
        -------
        bool
            True = 已投递；False = 队列满（已丢旧块，**不影响主链路**）。
        """
        item = (pcm, t_end)
        try:
            self._q.put_nowait(item)
            self.n_feed += 1
            return True
        except queue.Full:
            # ★ 队列满 ⇒ **丢最旧的块**（保留最新的音频 ⇒ 旁路追得上来）
            try:
                self._q.get_nowait()
                self.n_drop += 1
            except queue.Empty:
                pass
            try:
                self._q.put_nowait(item)
                self.n_feed += 1
                return True
            except queue.Full:
                self.n_drop += 1
                return False

    # ══════════════════════════════════════════════════════════
    # ③ 定稿段（★ EXT-029 ②：**不等**）
    # ══════════════════════════════════════════════════════════
    def request_final(self, seg_id: str, t_start: float, t_end: float) -> None:
        """登记「这一段定稿了，请旁路给标签」。

        ★★ **立即返回**（只 append）⇒ 定稿路径**零阻塞**。
          真正的 `on_final()` 在 worker 线程里跑（EXT-029 ①）。

        ★★ **也不加载模型**（同 `feed()`）⇒ 定稿路径零阻塞。
          ⇒ 引擎还没就绪时**照样登记** ⇒ worker 加载完会补算
            （否则这段的标签就永远丢了）。
        """
        with self._pending_lock:
            self._pending.append((str(seg_id), float(t_start), float(t_end), 0))
            self.n_final_req += 1

    # ══════════════════════════════════════════════════════════
    # ④ worker 线程
    # ══════════════════════════════════════════════════════════
    def start(self) -> None:
        """启动 worker 线程（幂等）。"""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="ext-spk-bypass",
                                        daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """停止 worker（放完队列再 join）。"""
        self._stop.set()
        try:
            self._q.put_nowait(None)
        except Exception:
            pass
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _run(self) -> None:
        """worker 主循环：**加载 → 取块 → feed → 处理待定稿段**。

        ⚠️ 本循环**永远不抛异常**（旁路挂了也不能影响主链路）。

        ★★ EXT-029 ①：**模型加载/编译只在这里发生**（worker 线程）
          ⇒ ASR 主路径 / 定稿路径**永不**因为「import + 编译」被阻塞。
        """
        # ★★ 第一步就加载（在 **worker 线程**里 ⇒ 不阻塞 ASR 主路径）
        try:
            self._load()
        except Exception as e:
            self._on_log("旁路加载异常（降级）：%s" % e)
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.2)
            except queue.Empty:
                item = None
            if item is None and self._stop.is_set():
                break
            if item is not None:
                t0 = time.perf_counter()
                try:
                    self._feed_tracker(item[0], item[1])
                except Exception as e:
                    self._on_log("旁路 feed 失败（忽略）：%s" % e)
                self.n_worker_busy_ms += (time.perf_counter() - t0) * 1000.0
            # ★ 每次循环都**试一下**待定稿段（不等到有新音频）
            try:
                self._process_pending()
            except Exception as e:
                self._on_log("旁路定稿处理失败（忽略）：%s" % e)
        self._on_log("旁路 worker 已退出（忙时 %.0f ms，丢块 %d）"
                     % (self.n_worker_busy_ms, self.n_drop))

    def _feed_tracker(self, pcm, t_end: Optional[float]) -> None:
        """调旁路引擎的 `feed()`（在 worker 线程里 ⇒ 不阻塞主路径）。

        ⚠️ `feed()` 内部会推进**分段**（在 `seg_device` 上推理）
          ⇒ 默认 NPU ⇒ **不与 ASR 抢 GPU.0**。
        """
        eng = self._engine
        if eng is None:
            return
        eng.feed(pcm, t_end)

    def _process_pending(self) -> None:
        """对**待定稿段**问旁路要标签（异步回填）。

        ★ `engine.on_final()` 内部会做**嵌入**（GPU.0）
          ⇒ 必须与 ASR/MT **共用同一把 device_lock**
          ⇒ 公平 FIFO ⇒ 不会饿死 ASR（EXT-029 ④）。
        """
        eng = self._engine
        if eng is None:
            return
        with self._pending_lock:
            pend = list(self._pending)
            self._pending = []
        if not pend:
            return
        keep: List[Tuple[str, float, float, int]] = []
        for seg_id, t_start, t_end, tries in pend:
            t_call = time.perf_counter()
            try:
                if self.device_lock is not None:
                    with self.device_lock:
                        res = eng.on_final(seg_id=seg_id, t_start=t_start,
                                           t_end=t_end)
                else:
                    res = eng.on_final(seg_id=seg_id, t_start=t_start,
                                       t_end=t_end)
            except Exception as e:
                self._on_log("旁路 on_final 失败（忽略）：%s" % e)
                res = {}
            self._lock_held_ms += (time.perf_counter() - t_call) * 1000.0
            spk = (res or {}).get("spk")
            if spk:
                self.n_label += 1
                self._last_label = (seg_id, str(spk))
                self._emit_label(seg_id, t_start, t_end, str(spk), res or {})
            elif (res or {}).get("pending"):
                # 音频还没进旁路缓冲 ⇒ 等下一轮（**不等**，主路径不阻塞）
                if tries + 1 < self.max_pending_tries:
                    keep.append((seg_id, t_start, t_end, tries + 1))
            else:
                # 明确「无标签」（不干净 / 重叠 / 模型未就绪）⇒ 走方案 A
                self.n_no_label += 1
        if keep:
            with self._pending_lock:
                self._pending.extend(keep)

    def _emit_label(self, seg_id: str, t_start: float, t_end: float,
                    spk: str, info: dict) -> None:
        """把标签**异步回填**给上层（异常不许影响旁路）。"""
        if self._on_label is None:
            return
        try:
            self._on_label(seg_id, t_start, t_end, spk, info)
        except Exception as e:
            self._on_log("标签回填失败（忽略）：%s" % e)

    # ══════════════════════════════════════════════════════════
    # ⑤ 指标
    # ══════════════════════════════════════════════════════════
    def stats(self) -> dict:
        """旁路诊断（★ EXT-029 ③ 的字段名直接对应 summary.json）。"""
        return {
            # ★ EXT-029 ③ 明文要求的两个字段名
            "spk_queue_drop": self.n_drop,
            "spk_worker_busy_ms": round(self.n_worker_busy_ms, 1),
            # ── 其余诊断 ──────────────────────────────────
            "enabled": True,
            "available": self.available,
            "load_error": self.load_error or None,
            "device_embed": self.device,
            "device_seg": self.seg_device,
            "queue_maxsize": self.queue_maxsize,
            "n_feed": self.n_feed,
            "n_final_req": self.n_final_req,
            "n_label": self.n_label,
            "n_no_label": self.n_no_label,
            "n_pending": len(self._pending),
            "last_label": ({"seg_id": self._last_label[0],
                            "spk": self._last_label[1]}
                           if self._last_label else None),
            # ★ ASR 的**额外延迟上界**：旁路持 device_lock 的总时长
            #   （公平锁 ⇒ ASR 最多多等这段时间）。
            "spk_gpu_lock_held_ms": round(self._lock_held_ms, 1),
            "shares_device_lock_with_asr": self.device_lock is not None,
            # ★ 旁路引擎的诊断（编译次数 / 推理次数 ⇒ EXT-029 ① 的证据）
            "engine": (self._engine.stats() if self._engine is not None else {}),
            "definition": ("spk_queue_drop = 队列满时丢弃的音频块数；"
                           "spk_worker_busy_ms = 旁路 worker 的总忙时；"
                           "spk_gpu_lock_held_ms = 旁路持 GPU 互斥锁的"
                           "总时长（= ASR 的额外延迟上界）。"),
        }


__all__ = ["SpeakerBypass", "DEFAULT_QUEUE_MAXSIZE",
           "DEFAULT_SEG_DEVICE", "DEFAULT_EMBED_DEVICE"]
