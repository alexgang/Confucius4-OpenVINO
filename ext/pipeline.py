"""pipeline.py — ★ EXT-010：**桥接服务改成流水线**（句级并行）

## 为什么有这个模块（依据 = EXT-010 明文 + EXT-008 的 interference 实测）

EXT-010（RESUME，2026-10-29 15:38）末句：
> 之后**根据数据**改流水线。

EXT-009（2026-10-29 15:30）末句：
> 桥接服务改成流水线（ASR、MT、TTS 各自一个线程，句级并行），
> **等 EXT-008 的 interference 数据确认后再做**。

EXT-008 (c) 的 interference 实测（`.tmp/ext008_bench/interference.json`，
2026-10-29 16:56:51）给出了放行依据：

```
serial    : ASR 211.384 s + TTS 61.919 s = 273.303 s
concurrent: ASR 200.770 s ∥ TTS 60.917 s，墙钟 200.770 s
asr_slowdown_x     = 0.9498   （并发时 ASR 没有变慢）
tts_slowdown_x     = 0.9838   （并发时 TTS 没有变慢）
parallel_speedup_x = 1.3613   （真并行成立，但加速比只有 1.36×，不是 2×）
```

⇒ **ASR@GPU.0 与 TTS@NPU 并发时互不拖慢** ⇒ 流水线化在设备层面**可行**。
⇒ 但 1.36× ≠ 2× ⇒ 流水线的**吞吐上限由最慢的那一阶段决定**
（这里 ASR 是长杆：并发墙钟 200.77 s ≈ ASR 单独耗时）。

## 设计（4 个线程，句级并行）

```
        ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
PCM ──▶ │ ASR 线程   │──▶│ MT 线程    │──▶│ TTS 线程   │──▶│ 主机侧线程 │
        │ (GPU.0)    │   │ (GPU.0)    │   │ (NPU)      │   │ (顺序收口)  │
        └────────────┘   └────────────┘   └────────────┘   └────────────┘
              ▲                ▲                                    │
              └──── GPU 设备互斥锁（ASR 与 MT 串行）─────┘            ▼
                                                       按 index **有序**产出
```

* **ASR / MT / TTS 各自一个线程**（EXT-009 明文）⇒ 段 N 在做 TTS 时，
  段 N+1 已经在做 ASR ⇒ 流水线化。
* **第四个线程 = 主机侧收口线程**：EXT-009 要求「时间伸缩在主机侧做，
  **不能占满 CPU（单线程）**」⇒ WSOLA 变速必须**串行**；
  且**顺序下发**要求收口阶段**按段序**执行 ⇒ 单独一个线程最干净。
* **GPU 设备互斥**：ASR 与 MT **都在 GPU.0**（EXT-001 设备摆放不变），
  而 EXT-008 (c) **只验证过 ASR ∥ TTS**，**没有**验证 ASR ∥ MT
  ⇒ 保守起见二者**互斥串行**（`device_lock`）。
  ⇒ **代价为零**：GPU 侧总工作量 = ASR 204.581 s + MT 47.038 s = 251.619 s
  ⇒ 折算 RTF 0.8387；而 TTS 侧 374.366 s 折算 1.2479 ⇒ **GPU 侧不是长杆**
  ⇒ 串行它**不损失任何吞吐**。
* **顺序下发**：收口线程按 `index` 严格有序地产出任务
  ⇒ 客户端与插件看到的任务顺序与串行版**一致**
  ⇒ 指标口径、插件排程逻辑**都不用改**。

## 铁律

* **不改任何引擎文件**（ASR R2T2 / MT Hy-MT2 / TTS Qwen3-TTS 全部只 import）。
* **不在 CPU 上跑推理**（设备摆放不变）。
* 线程只做**调用引擎**与**顺序收口**；WSOLA 只在收口线程里跑（单线程）。
* 任一段**异常也不丢**（标 `error` 并照常下发，`has_tts=False`），
  符合 EXT-009「不丢句」的要求。
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

STAGE_ASR = "asr"
STAGE_MT = "mt"
STAGE_TTS = "tts"

#: 需要**设备互斥**的阶段（都在 GPU.0 ⇒ 互斥串行）。
#: TTS 在 NPU ⇒ 不参与互斥（interference 实测已验证 ASR ∥ TTS 不互相拖慢）。
GPU_SERIAL_STAGES = frozenset({STAGE_ASR, STAGE_MT})

#: 队列深度（够用即可；避免无限堆积吃掉内存）。
QUEUE_MAXSIZE = 64


class _FairLock:
    """**公平（FIFO）**互斥锁。

    ★ 为什么不用 `threading.Lock`：`threading.Lock` **不保证公平** ⇒
      ASR 线程连续拿锁、MT 线程一直饿着 ⇒ 管线**根本没有并行**
      （实测：ASR 3 段连跑 0.0~0.9 s，MT 3 段连跑 0.9~1.8 s，
      TTS 再连跑 1.2~2.1 s ⇒ 三个阶段**完全串行**，
      墙钟反而比串行版**更长** —— 流水线反而更慢！）。
    ⇒ 改成**严格 FIFO**（谁先排队谁先拿）⇒
      ASR(段0) → MT(段0) → TTS(段0) → ASR(段1) → …
      ⇒ 三个阶段真正**交错**并行。
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._owner = None
        self._next_ticket = 0
        self._serving = 0
        self._waiters: List[int] = []

    def acquire(self) -> None:
        with self._cv:
            ticket = self._next_ticket
            self._next_ticket += 1
            self._waiters.append(ticket)
            while self._owner is not None or self._waiters[0] != ticket:
                self._cv.wait()
            self._waiters.pop(0)

    def release(self) -> None:
        with self._cv:
            self._owner = None
            self._cv.notify_all()

    def __enter__(self) -> "_FairLock":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


@dataclass
class SegmentJob:
    """流水线里流动的**一段**（从音频到可下发的配音任务）。"""

    index: int                       # 段序（0,1,2,...）⇒ 顺序收口用
    seg_id: str
    t_start: float
    t_end: float
    audio: object                    # np.ndarray（float32，16 kHz 单声道）
    orig_end: float                  # 原声结束时刻（会话绝对秒）
    audio_complete_at: float         # 这一段音频**完整到达服务端**的时刻
    # ── 阶段产出（由各阶段函数填） ──────────────────────────────
    text: str = ""
    tgt: str = ""
    spk: object = None
    voice: str = ""
    pcm24k: Optional[bytes] = None
    speech_sec: float = 0.0
    asr_sec: float = 0.0
    mt_sec: float = 0.0
    tts_sec: float = 0.0
    ready_at: float = 0.0            # TTS 就绪时刻
    error: Optional[str] = None

    def mark_error(self, stage: str, exc: BaseException) -> None:
        """记录某阶段的失败（**不丢段**）。

        ★ 只保留**第一个**错误：多阶段失败时，第一个才是根因
          （后面的多半是连锁反应）⇒ 便于复盘。
        """
        if self.error:
            return
        self.error = "%s:%s:%s" % (stage, type(exc).__name__, exc)


class EnginePipeline:
    """句级流水线（ASR / MT / TTS / 主机侧收口 各一个线程）。

    Parameters
    ----------
    asr_fn, mt_fn, tts_fn, emit_fn
        四个阶段的回调。签名统一为 ``fn(job) -> None``（``emit_fn`` 返回下发用的 dict）。
    device_lock
        GPU 设备互斥锁（ASR 与 MT 共用）。``None`` ⇒ 不互斥（仅自测用）。
    on_log
        日志回调（默认静默）。
    """

    def __init__(self, *,
                 asr_fn: Callable[[SegmentJob], None],
                 mt_fn: Callable[[SegmentJob], None],
                 tts_fn: Callable[[SegmentJob], None],
                 emit_fn: Callable[[SegmentJob], Optional[dict]],
                 device_lock: Optional[threading.Lock] = None,
                 on_log: Callable[[str], None] = lambda _m: None,
                 mt_lock=None) -> None:
        self._asr_fn = asr_fn
        self._mt_fn = mt_fn
        self._tts_fn = tts_fn
        self._emit_fn = emit_fn
        # ★ 用**公平锁**（FIFO）⇒ 见 `_FairLock` 的说明：
        #   `threading.Lock` 不保证公平 ⇒ ASR 会连续拿锁、MT 饿死
        #   ⇒ 三个阶段退化成串行 ⇒ 流水线反而比串行更慢。
        self._device_lock = device_lock if device_lock is not None else _FairLock()
        # 11-08: MT on NPU does not share GPU.0 with ASR => its own (no-op) lock
        self._mt_lock = mt_lock if mt_lock is not None else self._device_lock
        self._on_log = on_log

        self._q_asr: "queue.Queue[Optional[SegmentJob]]" = \
            queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._q_mt: "queue.Queue[Optional[SegmentJob]]" = \
            queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._q_tts: "queue.Queue[Optional[SegmentJob]]" = \
            queue.Queue(maxsize=QUEUE_MAXSIZE)
        self._q_out: "queue.Queue[Optional[SegmentJob]]" = \
            queue.Queue(maxsize=QUEUE_MAXSIZE)

        # 顺序收口的结果缓冲（**按 index 有序**）
        self._ready: Dict[int, dict] = {}
        self._next_index = 0
        self._ready_cv = threading.Condition()

        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []
        self._stats_lock = threading.Lock()
        self._n_submitted = 0
        self._n_emitted = 0
        self._n_error = 0
        self._stage_wall_sec = {STAGE_ASR: 0.0, STAGE_MT: 0.0, STAGE_TTS: 0.0}
        self._emit_sec = 0.0
        self._started = False

    # ── 生命周期 ────────────────────────────────────────────────
    def start(self) -> None:
        """启动 4 个工作线程（幂等）。"""
        if self._started:
            return
        self._started = True
        spec = [
            ("asr", self._run_asr),
            ("mt", self._run_mt),
            ("tts", self._run_tts),
            ("emit", self._run_emit),
        ]
        for name, fn in spec:
            th = threading.Thread(target=self._guard(name, fn),
                                  name="ext-pipeline-%s" % name, daemon=True)
            th.start()
            self._threads.append(th)

    def stop(self, timeout: float = 5.0) -> None:
        """停止流水线（放完队列再 join）。"""
        if not self._started:
            return
        self._stop.set()
        for q in (self._q_asr, self._q_mt, self._q_tts):
            try:
                q.put_nowait(None)
            except Exception:
                pass
        for th in self._threads:
            th.join(timeout=timeout)
        self._threads = []
        self._started = False

    def _guard(self, name: str, fn: Callable[[], None]):
        def _wrapped() -> None:
            try:
                fn()
            except BaseException as e:      # 线程绝不能静默死掉
                self._on_log("[pipeline] %s 线程异常：%s: %s"
                             % (name, type(e).__name__, e))
        return _wrapped

    # ── 提交 ────────────────────────────────────────────────────
    def submit(self, job: SegmentJob) -> int:
        """提交一段到流水线（**阻塞**在队列满时）。返回段序。"""
        self.start()
        with self._stats_lock:
            self._n_submitted += 1
        self._q_asr.put(job)
        return job.index

    @property
    def n_pending(self) -> int:
        """已提交但还没被收口线程产出的段数。"""
        with self._stats_lock:
            return self._n_submitted - self._n_emitted

    @property
    def n_all_emitted(self) -> bool:
        """所有已提交的段都已被收口线程产出。"""
        with self._stats_lock:
            return self._n_emitted >= self._n_submitted

    # ── 取结果 ──────────────────────────────────────────────────
    def pop_ready(self, *, block: bool = False,
                  timeout: float = 0.0) -> List[dict]:
        """取走**已经就绪**（且顺序正确）的任务。

        Parameters
        ----------
        block
            True ⇒ 一直等到「至少有一段就绪」或超时；
            False ⇒ 有就取，没有就返回空列表（不阻塞）。
        """
        out: List[dict] = []
        with self._ready_cv:
            if block:
                deadline = time.time() + max(0.0, timeout)
                while self._next_index not in self._ready:
                    left = deadline - time.time()
                    if left <= 0:
                        break
                    self._ready_cv.wait(timeout=min(left, 0.25))
            while self._next_index in self._ready:
                task = self._ready.pop(self._next_index)
                self._next_index += 1
                if task is not None:      # None = failed segment, skip it
                    out.append(task)
        return out

    def wait_all(self, timeout: float = 300.0) -> List[dict]:
        """等**所有**已提交的段都被收口线程产出，返回剩余任务。

        用法：客户端说「音频喂完了」时调用（``flush``）。
        """
        deadline = time.time() + timeout
        with self._ready_cv:
            while not self.n_all_emitted:
                left = deadline - time.time()
                if left <= 0:
                    self._on_log("[pipeline] wait_all 超时（还有 %d 段未产出）"
                                 % self.n_pending)
                    break
                self._ready_cv.wait(timeout=min(left, 0.25))
        return self.pop_ready(block=False)

    # ── 阶段线程 ────────────────────────────────────────────────
    def _run_asr(self) -> None:
        while not self._stop.is_set():
            job = self._q_asr.get()
            if job is None:
                break
            t0 = time.perf_counter()
            try:
                with self._device_lock:
                    self._asr_fn(job)
            except BaseException as e:
                job.mark_error(STAGE_ASR, e)
                self._on_log("[pipeline] ASR 失败（%s）：%s" % (job.seg_id, e))
            dt = time.perf_counter() - t0
            # ★ 阶段函数自己测**纯引擎调用**耗时（`job.asr_sec`）；
            #   这里记的是**墙钟**（含等 GPU 互斥锁的时间）⇒ 两者含义不同，
            #   分开记才能把「等锁」与「引擎慢」区分开。
            with self._stats_lock:
                self._stage_wall_sec[STAGE_ASR] += dt
            self._q_mt.put(job)

    def _run_mt(self) -> None:
        while not self._stop.is_set():
            job = self._q_mt.get()
            if job is None:
                break
            t0 = time.perf_counter()
            try:
                with self._mt_lock:
                    self._mt_fn(job)
            except BaseException as e:
                job.mark_error(STAGE_MT, e)
                self._on_log("[pipeline] MT 失败（%s）：%s" % (job.seg_id, e))
            dt = time.perf_counter() - t0
            with self._stats_lock:
                self._stage_wall_sec[STAGE_MT] += dt
            self._q_tts.put(job)

    def _run_tts(self) -> None:
        while not self._stop.is_set():
            job = self._q_tts.get()
            if job is None:
                break
            t0 = time.perf_counter()
            try:
                self._tts_fn(job)
            except BaseException as e:
                job.mark_error(STAGE_TTS, e)
                self._on_log("[pipeline] TTS 失败（%s）：%s" % (job.seg_id, e))
            dt = time.perf_counter() - t0
            with self._stats_lock:
                self._stage_wall_sec[STAGE_TTS] += dt
            self._push_ready(job)

    def _run_emit(self) -> None:
        """主机侧收口线程：**按段序**产出任务。

        （EXT-009 的单线程 WSOLA 变速也在此 ⇒ 主机侧 CPU 占用有界。）
        """
        pending: Dict[int, SegmentJob] = {}
        next_emit = 0
        while not self._stop.is_set() or pending:
            job = self._q_out.get()
            if job is None:
                break
            pending[job.index] = job
            while next_emit in pending:
                cur = pending.pop(next_emit)
                next_emit += 1
                t0 = time.perf_counter()
                try:
                    task = self._emit_fn(cur)
                except BaseException as e:
                    self._on_log("[pipeline] 收口失败（%s）：%s"
                                 % (cur.seg_id, e))
                    task = None
                dt = time.perf_counter() - t0
                with self._stats_lock:
                    self._emit_sec += dt
                    self._n_emitted += 1
                    if cur.error:
                        self._n_error += 1
                # 11-06 fix (EXT-043 B1): a failed emit used to leave a hole at
                #   cur.index, and pop_ready() releases strictly in order => every
                #   later segment of the session was blocked forever.  Put a None
                #   placeholder so pop_ready() skips this index and moves on.
                with self._ready_cv:
                    self._ready[cur.index] = task
                    self._ready_cv.notify_all()

    def _push_ready(self, job: SegmentJob) -> None:
        self._q_out.put(job)

    # ── 诊断 ────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        """给 stats / STATUS 用的诊断快照。"""
        with self._stats_lock:
            return {
                "n_submitted": self._n_submitted,
                "n_emitted": self._n_emitted,
                "n_error": self._n_error,
                "n_pending": self._n_submitted - self._n_emitted,
                "stage_wall_sec": {k: round(v, 3)
                                   for k, v in self._stage_wall_sec.items()},
                "emit_sec": round(self._emit_sec, 3),
                "gpu_serial_stages": sorted(GPU_SERIAL_STAGES),
                "definition": ("stage_wall_sec = 各阶段线程的墙钟（含等 GPU "
                               "互斥锁的时间）；emit_sec = 主机侧收口"
                               "（含 WSOLA 变速）的总耗时。"),
            }
