"""tts_worker.py — TTS 独立子进程（C-101 / P4）。

## 为什么独立进程

1. **不抢 GIL**：TTS 的重活是 numpy 特征提取 + numpy 采样 + S2A 的 25 步 Euler
   循环 + BigVGAN。这些都在主进程的话，会把 ASR / MT 饿死，字幕会卡。
2. **崩溃隔离**：worker 挂了只影响语音输出，字幕翻译照常（C-101 的硬要求）。

## 进程内协议

主进程 → worker（stdin，每行一个 JSON）：
    {"cmd": "synth", "id": 3, "text": "..."}
    {"cmd": "clone", "pcm": "<base64 float32 16k>"}     # 克隆说话人（可选）
    {"cmd": "quit"}

worker → 主进程（stdout，每行一个 JSON）：
    {"kind": "ready", "device": "GPU.0", "voice": "A"}
    {"kind": "first_packet", "latency_s": 0.83}
    {"kind": "played", "id": 3}
    {"kind": "error", "message": "..."}
    {"kind": "log", "message": "..."}

非 JSON 的行当作普通日志转发。

## 播放

🔴🔴🔴 **APP-028②：生产者 / 消费者架构**（2026-10-27）。

`sounddevice.OutputStream`（24000 Hz 或 22050 Hz、单声道、float32）
+ **无界内存音频队列**（`AudioQueue`）：

    合成线程（唯一，FIFO）──写──▶ AudioQueue（无界、保序）──取──▶ 播放回调

- **合成线程拿到 final 译文就连续合成**，不等上一句播完；
- 音频块写进内存里的**无界队列**（按句保持顺序、句内按块）⇒ **不设丢句上限**；
- **播放回调只从队列取数据**；队列空了 ⇒ **输出静音 + 计一次欠载**（**不丢句**）；
- **等播完 + 发 `played`** 由**独立的看门狗线程**（`_played_loop`）负责
  ⇒ 合成线程**不被播放速度卡住**；
- **用户手动停止 / 切换会话**时才清空队列（`clear_queue` 指令）。

⚠️ 旧实现（**已删除**）：`RingBuffer` = 3 s 有界环形缓冲 + 写满**反压阻塞**
⇒ 合成被播放速度卡住 ⇒ 谈不上「连续推理」；
主进程侧还叠了一层 `BACKLOG_MAX_S = 8` 的**丢句**逻辑 ⇒ 一律删除。

⚠️ **代价**：队列无界 ⇒ 若 RTF > 1，**语音滞后会持续累积**
⇒ 底栏实时显示「**语音滞后 X 秒**」⇒ 让用户看得见，但**不丢句**。

合成用**流式**路径（`native_stream.synth_stream`）：首块 25 token，之后每 50 token，
overlap 10，交叉淡化。这样第一包能早出来。
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import queue
import sys
import threading
import time
from collections import deque
from typing import Optional

SR = 22050
CHUNK_SAMPLES = 1024          # 音频回调每次取多少采样

# 🔴 Qwen3-TTS（BabelVox）的输出采样率 —— **24000 Hz**（babelvox 原生）。
# 旧引擎（OVSynth + BigVGAN）是 22050 Hz。
# ⇒ 走 BabelVox 路线时播放流必须用 24000，否则**变调/加速**。
TTS_SR = 24000

# ⚠️ 2026-10-22 修：`_HERE` 之前**从未定义**，但被用了 2 处
#    （`_load_conds` 的 `voices/` 目录、`_update_clone` 的 `clone_C.npz`）
#    ⇒ `NameError: name '_HERE' is not defined` ⇒ 音色加载必崩 ⇒ `ready=False`。
_HERE = os.path.dirname(os.path.abspath(__file__))

# 🔴🔴🔴 APP-028②：**stdout 写锁**（模块级）。
#   多个线程同时 `emit()` / `log()` ⇒ 行会**交错** ⇒ 主进程 JSON 解析失败。
#   ⚠️ 必须在 `import threading` 之后定义。
_OUT_WLOCK = threading.Lock()

# 🔴🔴🔴 APP-027②：**写进 `x.tts.jsonl` 的逐句遥测字段**
#   ⇒ V1/V2 验收要的是**机器可算的逐句指标**，不是会话日志里的散文。
#   ⇒ 只挑 APP-027 明文点名的字段 ⇒ 行不膨胀。
_APP027_JSONL_KEYS = (
    't_dequeue', 't_first_chunk', 't_last_chunk',
    'synth_rtf', 'prebuffer_s', 'prebuffer_short', 'rtf_ewma',
    'underflow_in_sentence', 'underflow_in_sentence_ms',
    'underflow_pre_sentence', 'underflow_pre_sentence_ms',
    'n_samples', 'n_parts', 'peak', 'rms', 'consumed',
    # 🔴🔴🔴 **本轮（APP-027 V2 修正）补的三个「出声硬证据」字段**
    #   ⇒ **实测缺口**：`read_delta` / `cb_delta` 只存在于**人可读遥测行**
    #     （`_fmt_telemetry`，L194-202），**没进逐句 jsonl**
    #   ⇒ 而「这句的音频**真的被声卡取走了多少样本**」的**唯一逐句可算证据**
    #     就是 `read_delta` ⇒ 缺它 ⇒ 「真出声」只能在事后翻散文日志
    #     ⇒ **验收脚本无法机器判定**「这句到底播没播」。
    #   ⇒ `consumed` 只是 **bool**（等 `ring.n_read` 追平的**结果**），
    #     **不含数量** ⇒ 「播了 24960 个样本」这种事实**无法核对**。
    #   ⇒ 两个字段一起补齐（`rms` 本来就在列表里）：
    #     `read_delta`  ：本句期间**被播放回调取走的样本数**（≥ n_samples ⇒ 整句交到声卡）
    #     `cb_delta`    ：本句期间的**音频回调次数**（>0 ⇒ 回调真的在跑）
    'read_delta', 'cb_delta',
)

# 🔴🔴🔴 APP-028②：**队列水位 / 语音滞后 / 队列峰值**（逐句 jsonl）。
#   APP-028 验收明文要求：「报告 5 分钟测试里队列的**峰值（秒和 MB）**」
#   ⇒ 必须**逐句落盘** ⇒ 否则验收只能翻会话日志（散文）。
#   - `queue_lag_s`   ：本句写入完成时，队列里还没播的音频时长（秒）
#   - `queue_peak_s`  ：到本句为止的**队列峰值**（秒）
#   - `queue_peak_mb` ：到本句为止的**队列峰值**（MB）
_APP028_JSONL_KEYS = (
    'queue_lag_s', 'queue_peak_s', 'queue_peak_mb',
)

# 🔴🔴🔴 APP-030⑤：**逐句语言 / 失控遥测**（`x.tts.jsonl`）。
#   APP-030⑤ 明文要求「会话日志每句记
#   `id / lang 实际下传值 / 字数 / 估计帧 / 实际帧 / 结束原因
#   （eos|cap|runaway|cancel）`，切换翻译目标时记一行」
#   ⇒ 必须**逐句落盘**（机器可算）⇒ 验收脚本可直接聚合。
_APP030_JSONL_KEYS = (
    'lang', 'lang_src', 'n_chars', 'est_frames', 'frames',
    'end_reason', 'max_new_tokens',
    # 🔴🔴🔴 APP-027 V3：**逐句的音色来源**（可观测性的第四项）
    #   ⇒ **为什么必须有**：APP-027 V3 要 reviewer 对「克隆 wav」做
    #     MiniMax 回转写 CER + CAMPPlus 余弦相似度对比。
    #   ⇒ 但 **jsonl 里原本没有「这句用的是克隆还是预设 A」** ⇒
    #     reviewer 拿到 wav **无法判断某句是不是克隆音色的产物**
    #     ⇒ 只能靠「目录名」猜 ⇒ **结论不可核**。
    #   ⇒ 本字段记录**本句合成时**的克隆状态：
    #     `clone_active` = 当时克隆是否已生效
    #     `clone_mode`    = xvector（BabelVox）/ ref_audio（CUDA 边车）
    #     `clone_audio_s` = 克隆源语音秒数
    #   ⚠️ **记录的是「合成那一刻」的状态**，不是会话结束时的状态
    #     ⇒ 前几句必然是 `clone_active=False`（还没攒够语音）⇒ 正确。
    'clone_active', 'clone_mode', 'clone_audio_s',
)


def _out_write(text: str):
    """往 stdout 写一行（**兼容二进制管道**）。

    🔴🔴 APP-021§54.10：主进程为了正确解码 stderr 的 GBK 字节，
    把管道改成了**二进制**模式（`Popen` 去掉 `text=True`）
    ⇒ worker 的 `sys.stdout` 变成二进制流
    ⇒ 旧写法 `sys.stdout.write(str)` 会抛
      `TypeError: a bytes-like object is required`。
    ⇒ 现在：**优先写 bytes**；拿不到 buffer 时才退回文本流。
    ⚠️ 两种情况都**必须 flush** —— 主进程靠行到达来实时拿状态。

    🔴🔴🔴 APP-027⑥：**本函数**必须**永不抛异常**。
    起因（用户 10:36:18 / 10:36:32 实测，APP-025）：
      GUI 是 **pythonw.exe**（GUI 子系统、**无控制台**）⇒
      `sys.stdout` 与 `sys.stderr` **都是 None**。
      旧实现在拿不到 `sys.stdout.buffer` 时**直接 `sys.stdout.write(...)`**
      ⇒ `AttributeError: 'NoneType' object has no attribute 'write'`
      ⇒ 连带把**播放设备打开失败**也吞掉（`Player.__init__` 里那句
        `log('播放流已启动…')` 就在 try 块内 ⇒ 一行日志把整条路径打断）
      ⇒ 用户看到的是「打开输出设备失败：AttributeError: …」
      ⇒ **与设备、精度、CUDA/NPU 全都无关**（实测复现：
        `play_test_tone_direct(None)` 在 pythonw 条件下
        返回 `(False, "打开输出设备失败：AttributeError: 'NoneType' object
        has no attribute 'write'")`，而同一段代码在控制台 python 下正常）。
    ⇒ 修法：**没有可用的 stdout 就把消息丢掉**（不是报错）
      ⇒ 日志写不出去**绝不能**影响功能。
    ⚠️ 判据用 `getattr(sys.stdout, 'write', None)` —— **不要**用
      `sys.stdout is None`（Git Bash 启动的 pythonw 会**继承 bash 管道句柄**
      ⇒ `sys.stdout` 不为 None 但 `buffer` 可能为 None ⇒ 两种情况都要覆盖）。
    """
    data = text + '\n'
    # 🔴🔴🔴 APP-028②：**多线程写 stdout 必须加锁**。
    #   起因：APP-028② 把「等播完」挪到**独立的播放看门狗线程**
    #   ⇒ 现在有「合成线程」+「看门狗线程」+「主循环线程」**同时**写 stdout
    #   ⇒ 无锁时两行的字节会**交错** ⇒ 主进程 JSON 解析失败
    #     （实测形态：`{"kind": "played"...}{"kind": "log"...` 拼成一行）
    #   ⇒ **独立**写锁（不能复用 `self.lock` 之类 ⇒ 那是实例级、
    #     且非可重入 ⇒ 会自死锁）。
    with _OUT_WLOCK:
        try:
            buf = getattr(sys.stdout, 'buffer', None)
        except Exception:
            buf = None
        if buf is not None:
            try:
                buf.write(data.encode('utf-8', 'replace'))
                buf.flush()
                return
            except Exception:
                pass
        # 🔴 文本流（或**根本没有** stdout ⇒ pythonw）
        w = getattr(sys.stdout, 'write', None)
        if w is None:
            return                       # 🔴 pythonw：**静默丢掉**，不抛异常
        try:
            w(data)
            fl = getattr(sys.stdout, 'flush', None)
            if fl is not None:
                fl()
        except Exception:
            pass                       # 🔴 任何 stdout 故障都**不能**影响功能


def emit(obj: dict):
    """往 stdout 发一行 JSON（立刻 flush，主进程要实时看到状态）。"""
    _out_write(json.dumps(obj, ensure_ascii=False))


def log(msg: str):
    _out_write(str(msg))

# ── APP-021②：每句一行播放遥测 ────────────────────────────────────────
def _fmt_telemetry(tel: dict) -> str:
    """把遥测 dict 格式化成**一行人可读**的文本（写进 worker 日志）。

    ⚠️ 字段名与数值必须**逐项**出现在这一行里 ⇒ reviewer 只看日志就能
    复核「峰值 / RMS(dBFS) / NaN / 回调数 / 已读增量 / 欠载次数」。
    """
    return ('out=%s sr=%s samples=%s parts=%s peak=%.4f rms_dbfs=%.1f '
            'nan_inf=%s cb_delta=%s read_delta=%s underflow_delta=%s '
            'ring=%s/%s consumed=%s%s'
            % (tel.get('out_desc', '?'), tel.get('sr', '?'),
               tel.get('n_samples', 0), tel.get('n_parts', 0),
               float(tel.get('peak', 0.0)), float(tel.get('rms_dbfs', -99.0)),
               tel.get('n_nan_inf', 0), tel.get('cb_delta', 0),
               tel.get('read_delta', 0), tel.get('underflow_delta', 0),
               tel.get('ring_level', 0), tel.get('ring_cap', 0),
               tel.get('consumed', '-'),
               (' [静音合成]' if tel.get('silent_synth') else '')))


class AudioQueue:
    """🔴🔴🔴 APP-028②：**无界内存音频队列**（生产者 / 消费者）。

    ## 为什么必须换成无界队列（用户 13:22 原话）

    > 「语音播放的时候，直接连续推理 TTS 音频流，不要等待播放完成，
    >   还没有播放的部分存内存缓存，这样提高系统利用率，
    >   **不要使用丢句这个方式**。」

    旧实现（`RingBuffer`）是**有界**环形缓冲（3 s）+ **写满阻塞（反压）**：
    - 合成线程写满 ⇒ 被 `write()` **阻塞** ⇒ 合成被迫降速到播放速度
      ⇒ **完全没有「连续推理」**，也拿不到「提高系统利用率」的好处；
    - 主进程侧再叠一层 `BACKLOG_MAX_S = 8` 的**丢句**逻辑
      ⇒ RTF 稍大于 1 就开始丢用户要听的句子（用户实测「越拖越久、最后全丢」）。

    ⇒ 本类实现 **APP-028② 的明文要求**：
      1. **合成线程拿到 final 译文就连续合成**，不等上一句播完；
      2. 音频块写进**内存里的无界队列**（按句保持顺序、句内按块）；
      3. **播放回调只从队列取数据**；队列空了 ⇒ 输出静音 + 计一次欠载
         （**不丢句**）；
      4. **不设丢句上限**。

    ## 保序（句间不交叉）

    队列是**块级 FIFO**：合成线程按句→块顺序 `put`，播放回调按同一顺序 `get`
    ⇒ 句内块顺序、句与句顺序都严格保持 ⇒ 不会交叉。

    ## 🔴 内存与「语音滞后」

    队列**无界** ⇒ 若 RTF > 1（合成比播放慢），队列会**持续增长**
    ⇒ 这正是 APP-028 要求 GUI 底栏显示「**语音滞后 X 秒**」的原因：
      **不丢句**的代价就是滞后会累积，必须让用户看得见。
    ⇒ 本类同时维护：
      - `n_written` / `n_read`（样本数，与旧环形缓冲同口径 ⇒ 遥测字段兼容）
      - `lag_s`（队列里尚未播放的样本时长 ⇒ **语音滞后秒数**）
      - `peak_lag_s` / `peak_bytes`（峰值，供验收报告）

    ## ⚠️ 与旧 `RingBuffer` 的兼容

    保留了旧类**同名方法**（`write` / `read` / `level` / `close`）与
    **同名计数器**（`n_written` / `n_read` / `n_blocks` / `_cap`）
    ⇒ 遥测字段（`read_delta` / `ring_level` / `ring_cap`）与
    `results/app/tts_audible_criterion.py` 的**出声判据**全部不受影响。

    🔴 `n_blocks` 语义**变了**：旧版 = 「因写满而阻塞的次数」；
       新版 = 「**队空**导致播放回调补静音的次数」（= 欠载次数）
       ⇒ 这正是 APP-028② 要的「队列空了就输出静音，同时计一次欠载」。
    """

    def __init__(self, capacity: int = SR * 30, timeout_s: float = 30.0):
        # 🔴 兼容旧字段：`_cap` 仍存在（遥测里报 `ring_cap`）
        #   ⚠️ 新实现**没有容量上限** ⇒ `_cap` 只是一个**名义值**，
        #      不再参与任何截断逻辑（不丢样本 ⇒ 绝不截断）。
        self._cap = capacity
        self.timeout_s = timeout_s
        self._cv = threading.Condition()
        self._closed = False
        # 🔴 队列元素 = `[numpy float32 块, 句子 jid, 该块在本句内的起始样本偏移]`
        #   ⇒ 播放回调可据此判断「这句播完了没有」（供 `played` 语义）。
        self._chunks: list = []
        self._cur_off = 0                # 队首块已取走的样本数（分片取用）
        self._queued_samples = 0         # 队列里尚未被取走的样本数
        self.n_written = 0               # 累计写入的样本数（与旧环形缓冲同口径）
        self.n_read = 0                  # 累计被播放回调取走的样本数
        self.n_blocks = 0                # 🔴 新语义：**队空次数**（= 欠载次数）
        self.n_underflow = 0             # 欠载次数（与 Player.n_underflow 对齐）
        self.n_silence_fill = 0          # 补了多少个静音样本
        self._sr = SR
        # 🔴 峰值（验收报告要「队列峰值（秒和 MB）」）
        self.peak_lag_s = 0.0
        self.peak_bytes = 0

    # -- 生产者 -------------------------------------------------------
    def write(self, data, should_stop=None, jid=None, offset=0):
        """把一块音频**追加**到队尾（**永不阻塞、永不丢弃**）。

        🔴 与旧 `write()` 的**根本区别**：
          旧：有界环形缓冲，写满 ⇒ **阻塞**（反压）⇒ 合成被迫降速；
          新：**无界** ⇒ 写进去就走 ⇒ 合成线程可以**连续推理**。

        `should_stop`：可选无参可调用对象；返回 True 时**中止本句**
        （返回 False），已入队的部分留在队列里自然播完（不制造爆音）。

        返回 True = 整块已入队；False = 被中止。
        """
        n = len(data)
        if n == 0:
            return True
        if should_stop is not None and should_stop():
            return False
        try:
            import numpy as _np
            arr = _np.asarray(data, dtype=_np.float32)
            if arr.ndim > 1:
                arr = arr.reshape(-1)
        except Exception:
            arr = data
        with self._cv:
            if self._closed:
                raise RuntimeError('音频队列已关闭')
            self._chunks.append((arr, jid, int(offset)))
            self._queued_samples += int(arr.size)
            self.n_written += int(arr.size)
            # 🔴 峰值（验收报告要「队列峰值（秒 / MB）」）
            lag = self._queued_samples / float(self._sr or SR or 1)
            if lag > self.peak_lag_s:
                self.peak_lag_s = lag
            nbytes = sum(int(a.nbytes) for a, _j, _o in self._chunks)
            if nbytes > self.peak_bytes:
                self.peak_bytes = nbytes
            self._cv.notify_all()
        return True

    # -- 消费者 -------------------------------------------------------
    def read(self, n):
        """取**至多 n** 个样本（不足就少给 ⇒ 调用方补静音）。

        🔴 与旧 `read()` 的区别：**不等待**。
          旧：环形缓冲空 ⇒ `read()` 立刻返回空（播放回调补静音）—— 一样；
          新：队列空 ⇒ 立刻返回空（**播放回调补静音 + 计欠载**）—— 一样。
        ⇒ **播放语义没变**，只是「空」的含义从「缓冲瞬时为空」
          变成「队列已排空（合成跟不上播放）」。
        """
        with self._cv:
            if not self._chunks:
                return []
            need = int(n)
            out_parts = []
            got = 0
            while self._chunks and got < need:
                arr, _jid, _off = self._chunks[0]
                remain = int(arr.size) - self._cur_off
                take = min(need - got, remain)
                if take <= 0:
                    # 上一块的尾巴已经取完 ⇒ 弹出这一块
                    self._chunks.pop(0)
                    self._cur_off = 0
                    continue
                out_parts.append(arr[self._cur_off:self._cur_off + take])
                self._cur_off += take
                got += take
                if self._cur_off >= int(arr.size):
                    self._chunks.pop(0)
                    self._cur_off = 0
            self._queued_samples = max(0, self._queued_samples - got)
            self.n_read += got
            if not out_parts:
                return []
            try:
                import numpy as _np
                if len(out_parts) == 1:
                    return out_parts[0].copy()
                return _np.concatenate(out_parts)
            except Exception:
                flat = []
                for p in out_parts:
                    try:
                        flat.extend(p.tolist())
                    except Exception:
                        flat.extend(list(p))
                return flat

    def level(self) -> int:
        """队列里**尚未播放**的样本数。"""
        with self._cv:
            return self._queued_samples

    def lag_s(self, sr: int = 0) -> float:
        """🔴🔴 APP-028②：**语音滞后秒数**（队列里还没播的音频时长）。

        ⇒ GUI 底栏显示「语音滞后 X 秒」用的就是它。
        """
        with self._cv:
            n = self._queued_samples
        s = float(sr or self._sr or SR)
        return (n / s) if s > 0 else 0.0

    def drop_jid(self, jid) -> int:
        """🔴🔴 APP-028②：**把某一句已入队的音频整句摘掉**。

        用途：**用户主动停止 / 切换会话**时，把这一句**还没播完**的音频
        从队列里去掉 ⇒ 避免「半句话突然被切断」（爆音 + 语义残缺）。

        🔴 **为什么以前会出现「半句被切断」**：
          旧实现里 `cancel` 只是给句子打一个标记 ⇒ `synth()` 在**块之间**
          检查到标记就 `break` ⇒ 但**已经写进缓冲的那部分音频还在**
          ⇒ 播放回调照样把它播出来 ⇒ 用户听到的是「一句话说到一半没了」。
          ⇒ 这就是 APP-028 明文要删的「**中止已写入句子**」的路径。

        返回被摘掉的样本数（0 = 这一句不在队列里）。
        """
        if jid is None:
            return 0
        with self._cv:
            keep = []
            removed = 0
            for arr, j, off in self._chunks:
                if j == jid:
                    removed += int(arr.size)
                else:
                    keep.append((arr, j, off))
            if not removed:
                return 0
            self._chunks = keep
            self._cur_off = 0
            self._queued_samples = max(0, self._queued_samples - removed)
            return removed

    def clear(self) -> int:
        """🔴🔴 APP-028②：**清空整个队列**（用户手动停止 / 切换会话时）。

        返回被清掉的样本数。
        """
        with self._cv:
            removed = int(self._queued_samples)
            self._chunks = []
            self._cur_off = 0
            self._queued_samples = 0
            return removed

    def close(self):
        with self._cv:
            self._closed = True
            self._cv.notify_all()


# ── 输出设备解析缓存（§52：同一 id 必须始终解析成同一设备）──────────────
# key = GUI 传来的原始字符串（WASAPI 端点 id / 设备名）
# value = (sd_device, note)
_OUT_DEV_CACHE = {}
_OUT_DEV_LOCK = threading.Lock()
_CO_DONE = threading.local()


def _co_init():
    """尽力在当前线程初始化 COM（`soundcard` 在子线程里取扬声器列表需要它）。

    ⚠️ 不能 `import comtypes`（包内没有）⇒ 直接调 ole32。
    ⚠️ 已初始化过就**不要重复调**（同线程第二次 CoInitializeEx 会返回
       RPC_E_CHANGED_MODE / S_FALSE，虽然无害但会刷日志）⇒ 用 thread-local 标记。
    ⚠️ 任何失败都**吞掉**：这里只是「尽力」，真正的兜底是 ① 缓存 ② 系统默认。
    """
    if getattr(_CO_DONE, 'ok', False):
        return
    try:
        import ctypes
        # 0x2 = COINIT_APARTMENTTHREADED；返回 S_OK/S_FALSE/E_INVALIDARG 都无所谓
        ctypes.windll.ole32.CoInitializeEx(None, 0x2)
        _CO_DONE.ok = True
    except Exception:
        pass


def _match_output_index(sd, name: str):
    """在 sounddevice 的输出设备里按名字找索引（精确 → 前后缀 → 子串，忽略大小写）。"""
    try:
        devs = [(i, d) for i, d in enumerate(sd.query_devices())
                if d['max_output_channels'] > 0]
    except Exception:
        return None
    low = (name or '').strip().lower()
    if not low:
        return None
    for i, d in devs:                                  # ① 精确同名
        if d['name'].strip().lower() == low:
            return i
    for i, d in devs:                                  # ② 前缀（sounddevice 常带后缀）
        n = d['name'].strip().lower()
        if n.startswith(low) or low.startswith(n):
            return i
    for i, d in devs:                                  # ③ 子串
        n = d['name'].strip().lower()
        if low in n or n in low:
            return i
    return None


# ── APP-023③：把「BabelVox 加载失败」翻译成人话 ──────────────────────────
def _babelvox_import_error() -> str:
    """探测 babelvox（Qwen3-TTS 运行时）是否可导入。返回错误串，'' 表示可用。

    🔴 为什么单独探测：异常链里 `e` 可能是**任何**环节
      （缺运行时 / 模型编译失败 / 设备不支持）⇒ 界面必须能区分。
    """
    try:
        import babelvox  # noqa: F401
        return ''
    except Exception as e:
        return '%s: %s' % (type(e).__name__, e)


def _babelvox_failure_reason(e, device='', precision='') -> str:
    """把 BabelVox 加载失败翻译成**一句用户能看懂、能处理**的话。

    🔴🔴 APP-023③ / APP-025：旧实现只在日志里写「BabelVox 引擎不可用 ⇒
       回落旧引擎」，而界面最终显示的是 `rc=3221226505`（进程级 abort）
       ⇒ **用户完全无从下手**（这正是用户 09:06 反馈的原话）。

    两种情形必须分开说：
      ① **缺运行时**（`import babelvox` 都不行）⇒ 明确报「缺少 Qwen3-TTS
         运行时（babelvox）」+ 指引（要用随包的 python）；
      ② **运行时在、但引擎起不来**（模型/设备/编译）⇒ 报「Qwen3-TTS 引擎
         加载失败」+ 原始异常，并说明**不会**回落旧引擎。
    """
    miss = _babelvox_import_error()
    if miss:
        return ('缺少 Qwen3-TTS 运行时（babelvox）：%s。'
                '请用随客户包分发的 python（<包根>\\python\\python.exe）启动，'
                '该运行时随包提供、无需联网安装。' % miss)
    where = ''
    if device or precision:
        where = '（设备 %s / 精度 %s）' % (device or '-', precision or '-')
    return ('Qwen3-TTS 引擎加载失败%s：%s。'
            '已不再回落旧的 Confucius4-TTS 引擎 —— 它的动态形状 IR 在 '
            'NPU/GPU 上必然编译失败并导致进程崩溃。' % (where, e))


# ── APP-023④ / APP-025：**不依赖 worker** 的测试音 ─────────────────────
def play_test_tone_direct(out_device=None, freq=440.0, dur_s=1.0, amp=0.3,
                          sr=None):
    """**直接在当前进程**用所选输出设备播一段 440 Hz（不经过 TTS worker）。

    🔴🔴🔴 为什么必须独立（用户 09:06 原话 + APP-023 第 4 条 / APP-025）：
      旧实现是「发一条 `test_tone` 指令给 worker」⇒ worker 没起来 / 起不来 /
      已经崩了 ⇒ 按钮直接报「语音输出还没启动」
      ⇒ 用户**没法先单独验证播放链路**（而排查顺序恰恰应该是：
        先确认声卡通，再怀疑合成）。
      ⇒ 现在：**测试音与 worker、与模型完全解耦** —— worker 有没有启动、
        是不是坏了都能用。

    🔴 判据复用：返回的 `tel` 与 `results/app/tts_audible_criterion.py` 的
      `evaluate_audible()` **同形**（`read_delta` / `n_samples` / `peak`）
      ⇒ 测试音也可以用同一套「真的出声」硬判据复核，不另立标准。

    返回 `(ok: bool, diag: str, tel: dict)`。
    """
    use_sr = int(sr or TTS_SR)
    try:
        p = Player(device=out_device, sr=use_sr)
    except Exception as e:
        return False, ('打开输出设备失败：%s: %s' % (type(e).__name__, e)), {}
    try:
        if getattr(p, '_stream', None) is None:
            return False, ('播放流未打开（所选输出设备不可用：%s）'
                           % (getattr(p, 'out_desc', None) or out_device)), {}
        before = p.telemetry()
        ok, diag = p.test_tone(freq=freq, dur_s=dur_s, amp=amp)
        after = p.telemetry()
        n_samples = int(use_sr * dur_s)
        tel = dict(after or {})
        tel['sr'] = use_sr
        tel['n_samples'] = n_samples
        tel['peak'] = amp
        tel['read_delta'] = max(0, int(after.get('n_read', 0))
                                - int(before.get('n_read', 0)))
        tel['cb_delta'] = max(0, int(after.get('n_cb', 0))
                              - int(before.get('n_cb', 0)))
        return bool(ok), diag, tel
    except Exception as e:
        return False, '测试音播放异常：%s: %s' % (type(e).__name__, e), {}
    finally:
        try:
            p.close()
        except Exception:
            pass


def resolve_out_device(device):
    """把「WASAPI 端点 id / 设备名 / 索引」统一解析成 sounddevice 认的输出设备。

    🔴🔴 **为什么必须做这一步**（用户反馈「GUI 里无论 CUDA 还是 NPU 都听不到声音」）：
      GUI 的「语音输出 → 输出设备」下拉值来自 `audio_source.list_output_devices()`，
      它是 **soundcard 的 WASAPI 端点 id**（形如 `{0.0.0.00000000}.{guid}`）。
      而 `sounddevice` 的 `device=` 只接受 **int 索引**或**设备名子串**
      （`sounddevice.py::_get_device_id` 把设备名+hostapi 拼起来做 `find()`）
      ⇒ GUID **永远匹配不到** ⇒ `ValueError: No output device matching '…'`
      ⇒ 播放流**打不开** ⇒ 一句都播不出来（**与精度/CUDA/NPU 全无关**）。
      ⚠️ 同一个 id 用在「系统声音」来源（`make_source('system', system_device=…)`）
        上是**正确**的（soundcard 要的就是它）⇒ 不能改上游，只能在这里转。

    🔴🔴🔴 **同一个 id 必须始终解析成同一个设备**（2026-10-26 §52 修）：
      `app071` 实测日志里同一个端点 id **第一次**解析成功（→ 播放索引 3），
      24 s 后 `_reopen_player()` **再解析就失败**（`无法识别 ⇒ 改用系统默认`）。
      原因：`_reopen_player()` 是在 **`_safe_load` 线程**里调的，而 `soundcard`
      取扬声器列表要 **COM**，那个线程没初始化过 COM ⇒ `all_speakers()`
      抛异常、被 `except` 吃掉 ⇒ 静默回落「系统默认」。
      ⇒ 用户在下拉里选的设备被**悄悄换掉**；若默认设备也不可用，
        就直接走到 `播放设备打开失败` ⇒ **worker 级 error** ⇒ 整场朗读中止。
      修法两层：
        ① **按 id 缓存**解析结果（第一次在主线程算的才是权威）；
        ② 调用前**尽力 CoInitializeEx**（非主线程也能拿到 COM）；
      两者都失败才回落默认，并且**日志里会写清楚**是缓存还是现算。
    """
    if device is None:
        return None, '系统默认设备'
    if isinstance(device, int):
        return device, '索引 %d' % device
    s = str(device).strip()
    if not s:
        return None, '系统默认设备'
    # ① 缓存命中 ⇒ 直接复用（保证「同一 id ⇒ 同一设备」，且不再依赖 COM）
    with _OUT_DEV_LOCK:
        hit = _OUT_DEV_CACHE.get(s)
    if hit is not None:
        d, note = hit
        return d, note + '（缓存）'
    import sounddevice as sd
    try:                       # ② 本身就是设备名（或名字子串）⇒ 原样交给 sounddevice
        sd.query_devices(s, 'output')
        res = (s, '设备名「%s」' % s)
        with _OUT_DEV_LOCK:
            _OUT_DEV_CACHE[s] = res
        return res
    except Exception:
        pass
    _co_init()                 # ③ 尽力初始化 COM（soundcard 在子线程里需要）
    name = None                # ④ WASAPI 端点 id ⇒ 反查端点名，再按名字找播放索引
    try:
        import soundcard as sc
        for spk in sc.all_speakers():
            if spk.id == s:
                name = spk.name
                break
    except Exception:
        pass
    if name:
        idx = _match_output_index(sd, name)
        if idx is not None:
            res = (idx, '端点 id → 「%s」→ 播放索引 %d' % (name, idx))
        else:
            res = (None, ('端点 id → 「%s」，但 sounddevice 里没有同名播放设备 '
                          '⇒ 改用系统默认' % name))
    else:
        res = (None, '无法识别「%s」⇒ 改用系统默认' % s)
    # ⑤ 成功的结果**缓存**；失败的结果**也缓存**（否则每次调用都可能给出
    #    不同设备 —— 「有时用你选的、有时用默认」比一直用默认更难查）
    with _OUT_DEV_LOCK:
        _OUT_DEV_CACHE[s] = res
    return res


def _describe_out(sd, dev):
    """人话描述「声音到底去了哪个设备」（写进日志，便于用户自查）。"""
    try:
        info = sd.query_devices(dev if dev is not None else sd.default.device[1],
                                'output')
        host = sd.query_hostapis(info['hostapi'])['name']
        return ('%s（hostapi=%s, ch=%d, 设备默认 sr=%d）'
                % (info['name'], host, info['max_output_channels'],
                   int(info['default_samplerate'])))
    except Exception as e:
        return '（无法解析设备名：%s）' % e


class Player:
    """sounddevice 输出流 + **无界内存音频队列**（APP-028②）。

    音频回调在独立线程里跑（sounddevice 自己开线程），从队列取数据。
    队列欠载时补静音（不补静音会爆音）**并计一次欠载**（**不丢句**）。

    🔴🔴 APP-028② 的架构变更：
      旧：合成线程 → **有界 3 s 环形缓冲**（写满阻塞）→ 播放回调
          ⇒ 合成被反压卡住，无法连续推理；
      新：合成线程 → **无界内存队列**（写入即走）→ 播放回调
          ⇒ 合成**连续推理**，未播放部分留在内存缓存里
          ⇒ 代价 = 语音滞后会累积 ⇒ 底栏显示「语音滞后 X 秒」。
    """

    def __init__(self, device=None, sr: int = SR):
        import sounddevice as sd
        self.sr = sr
        # 🔴🔴 APP-028②：**无界**内存队列（`AudioQueue`）。
        #   `capacity` 只作为**名义容量**（遥测字段 `ring_cap` 保留同名），
        #   **不再有任何截断 / 反压 / 丢样本逻辑**。
        self.ring = AudioQueue(capacity=sr * 3, timeout_s=30.0)
        self._sd = sd
        self._stream = None
        self._lock = threading.Lock()
        self.n_cb = 0                # 音频回调次数（诊断：0 = 回调根本没跑）
        # 🔴🔴 APP-021②：回调**欠载**次数（环形缓冲里取不满一帧 ⇒ 补了静音）。
        #   大量欠载 = 合成比播放快（或播放端在欠载）⇒ 听感上是「断断续续」。
        self.n_underflow = 0         # 欠载次数
        self.n_silence_fill = 0      # 补了多少个静音样本（欠载填充总量）
        # 🔴🔴🔴 APP-027②：**按句**统计「句内欠载」（首块播出之后的欠载）。
        #   起因（APP-027 问题②）：旧的 `underflow_delta` 从**拿到锁**就开始数
        #   ⇒ 把「首块前的空等」也算成卡顿 ⇒ 分不清「句前等一次」与
        #     「句内断断续续」⇒ 卡顿归因一直错。
        #   ⇒ 现在每次欠载都记一条 `(n_read 位置, 静音样本数, 时刻)`；
        #     句内欠载 = 发生在「本句首块已播完」之后的那些条数。
        #   ⚠️ 保留最近 2000 条（长会话不无界增长）。
        self._uf_events = deque(maxlen=2000)
        # 🔴🔴 **把 GUI 的端点 id 转成 sounddevice 认的设备**（见 resolve_out_device）：
        #   GUI 传的是 WASAPI GUID，直接塞给 `sd.OutputStream` 必然 ValueError
        #   ⇒ 旧实现「播放设备打开失败」⇒ **一句都不出声**（用户反馈的真因之一）。
        sd_dev, how = resolve_out_device(device)
        self.out_how = how
        self.out_sd_device = sd_dev
        self.out_desc = _describe_out(sd, sd_dev)
        self.out_is_default = sd_dev is None
        if str(device).strip() and device is not None and sd_dev != device:
            log(f'[tts_worker] 输出设备解析：{device!r} ⇒ {how}')
        # ① 先用解析出的设备开流；② 失败 ⇒ **回退系统默认再试一次**
        #   （「一句都不出声」远比「播到默认设备」严重 ⇒ 宁可回退也不静音）
        err = None
        for dev_try in ([sd_dev] if sd_dev is None else [sd_dev, None]):
            try:
                self._stream = sd.OutputStream(
                    samplerate=sr, channels=1, dtype='float32',
                    device=dev_try, blocksize=CHUNK_SAMPLES,
                    callback=self._cb)
                self._stream.start()
                if dev_try is None and sd_dev is not None:
                    self.out_desc = _describe_out(sd, None)
                    self.out_is_default = True
                    log('[tts_worker] ⚠️ 指定的输出设备打不开 ⇒ **已回退到系统默认**'
                        f'（实际输出: {self.out_desc}）')
                log(f'[tts_worker] 播放流已启动：sr={sr} '
                    f'device={"默认设备" if self.out_is_default else dev_try} '
                    f'⇒ **实际输出: {self.out_desc}** '
                    f'blocksize={CHUNK_SAMPLES} '
                    f'latency={getattr(self._stream, "latency", None)}')
                err = None
                break
            except Exception as e:
                err = e
                log(f'[tts_worker] 播放设备打开失败（device={dev_try!r}，'
                    f'{how}）：{e}')
                self._stream = None
        if self._stream is None:
            log('[tts_worker] 🔴 默认设备也打不开 ⇒ 本次会话无法出声'
                '（请检查系统是否有可用输出端点）')
            emit({'kind': 'error', 'message': f'播放设备打开失败：{err}'})

    def _cb(self, outdata, frames, time_info, status):
        self.n_cb += 1
        if status and self.n_cb <= 5:
            # ⚠️ 只报前 5 次，避免刷屏（欠载时每块都会带 status）
            log(f'[tts_worker] 播放状态：{status}')
        # 🔴🔴 APP-027②：欠载事件的**位置**用「读之前的 n_read」
        #   ⇒ 它就是「播放头当时停在哪」⇒ 可与「首块写入位置」比较。
        pos_before = self.ring.n_read
        data = self.ring.read(frames)
        n = len(data)
        if n < frames:
            # 🔴 APP-021②：欠载计数（诊断用；不影响播放语义）
            # 🔴🔴 APP-028②：队空 = 欠载 ⇒ 补静音 + 计一次欠载，**绝不丢句**。
            self.n_underflow += 1
            miss = frames - n
            self.n_silence_fill += miss
            # 同步到队列（`n_blocks` 新语义 = 队空次数）
            try:
                self.ring.n_underflow = self.n_underflow
                self.ring.n_silence_fill = self.n_silence_fill
                self.ring.n_blocks += 1
            except Exception:
                pass
            # 🔴🔴 APP-027②：登记**欠载事件**（位置 + 静音样本数 + 时刻）
            #   ⇒ 之后能区分「句内欠载」与「首块前空等」。
            self._uf_events.append((pos_before, miss, time.monotonic()))
            # 🔴 APP-027①：`read()` 现在返回 **numpy 数组** ⇒ 补静音也要用
            #   numpy（`list + list` 会退化成逐样本 Python 循环）。
            import numpy as _np
            data = _np.concatenate((data, _np.zeros(miss, dtype=_np.float32)))
        outdata[:, 0] = data

    # ── APP-027②：按句切分欠载事件（首块前 / 句内）────────────────────
    def underflow_split(self, first_chunk_start: int, last_chunk_end: int):
        """把欠载事件切成「首块前空等」与「句内欠载」两段。

        参数
        ----
        first_chunk_start : 本句**第一块写进环形缓冲之前**的 `n_written` 位置
                            （播放头到这里之前都还没开始播本句 ⇒ 空等）
        last_chunk_end    : 本句**最后一块写完之后**的 `n_written` 位置

        返回 `(pre_n, pre_ms, in_n, in_ms)`：
        - `pre_n` / `pre_ms`：**首块播出之前**的欠载次数与静音总时长
        - `in_n`  / `in_ms` ：**首块播出之后**（句内）的欠载次数与静音总时长

        🔴🔴 **APP-027② 的核心**：「卡顿」只该由 `in_*` 衡量。
        「首块前空等」是**正常的一等待**（预缓冲）⇒ 不能算卡顿。
        """
        pre_n = pre_ms = in_n = in_ms = 0
        if first_chunk_start is None:
            first_chunk_start = 1 << 60          # 还没有首块 ⇒ 全算「首块前」
        for pos, miss, _ts in list(self._uf_events):
            if pos < first_chunk_start:
                pre_n += 1
                pre_ms += miss
            elif last_chunk_end is not None and pos <= last_chunk_end:
                in_n += 1
                in_ms += miss
        return pre_n, pre_ms, in_n, in_ms

    def write(self, wav, should_stop=None, jid=None, offset=0):
        """把一块音频写进**无界队列**（不阻塞、不丢弃）。

        🔴 APP-028②：`jid` / `offset` 会随块一起入队（供后续按句判定
        「这句播完没有」），旧调用方不传也不受影响。
        """
        if self._stream is None:
            raise RuntimeError('播放流未打开（无法播出声音）')
        return self.ring.write(wav, should_stop=should_stop, jid=jid,
                               offset=offset)

    # 🔴🔴 APP-021①：**等音频真的被播放回调取走**（而不是"写进缓冲"）。
    #
    #   旧语义：synth() 把最后一块写进环形缓冲就发 `played`
    #   ⇒ `played` 只代表"进了缓冲"，**不代表声卡播完**
    #   ⇒ 缓冲容量 3 s ⇒ 发 played 时最多还有 3 s 音频没出声
    #   ⇒ 用户据此判断"能出声"是**无效判据**（APP-021 证据 1）。
    #
    #   新语义：`wait_consumed(target)` 等 `ring.n_read` 追上
    #   **本句最后样本的写入位置**（`n_written` 的绝对值）⇒
    #   此时这一句的音频**已经全部交给声卡**。
    def wait_consumed(self, target: int, timeout_s: float = 30.0,
                      should_stop=None):
        """等 `ring.n_read >= target`。

        返回 `(ok, diag)`：
        - `ok=True`  ⇒ 音频已被播放回调**全部取走**；
        - `ok=False` ⇒ 超时/被中止 ⇒ `diag` 里带诊断（已读/目标/n_cb）。
        """
        t0 = time.monotonic()
        while True:
            try:
                n_read = self.ring.n_read
            except Exception:
                n_read = 0
            if n_read >= target:
                return True, ''
            if should_stop is not None and should_stop():
                return False, ('已被中止（已读 %d / 目标 %d）' % (n_read, target))
            if time.monotonic() - t0 > timeout_s:
                return False, ('等待播放消费超时 %.1f s（已读 %d / 目标 %d，'
                               '回调 %d 次）'
                               % (timeout_s, n_read, target, self.n_cb))
            time.sleep(0.02)

    def telemetry(self) -> dict:
        """播放器当前的诊断快照（供每句遥测 / 「测试声音」用）。"""
        try:
            ring = self.ring
            return dict(
                out_desc=self.out_desc,
                sr=self.sr,
                n_cb=self.n_cb,
                n_underflow=self.n_underflow,
                n_silence_fill=self.n_silence_fill,
                n_written=ring.n_written,
                n_read=ring.n_read,
                n_blocks=ring.n_blocks,
                ring_level=ring.level(),
                ring_cap=ring._cap,
                # 🔴🔴 APP-028②：**语音滞后秒数**（队列里还没播的音频时长）
                lag_s=(ring.lag_s(self.sr) if hasattr(ring, 'lag_s') else 0.0),
                peak_lag_s=getattr(ring, 'peak_lag_s', 0.0),
                peak_bytes=getattr(ring, 'peak_bytes', 0),
                stream_open=(self._stream is not None),
            )
        except Exception as e:
            return {'error': '%s: %s' % (type(e).__name__, e)}

    # 🔴 APP-021④：**测试声音** —— 1 s 的 440 Hz 正弦波（幅度 0.3）。
    #   走**同一个** Player（同一个 sounddevice 输出流）⇒
    #   「能听到 440 Hz」就把「播放链路」与「TTS 合成」彻底拆开了：
    #   440 Hz 听不到 ⇒ 设备/音量/系统问题；听得到但 TTS 听不到 ⇒ 合成侧问题。
    def test_tone(self, freq: float = 440.0, dur_s: float = 1.0,
                  amp: float = 0.3):
        """播一段测试音。返回 (ok, diag)。"""
        if self._stream is None:
            return False, '播放流未打开（没有输出设备）'
        try:
            import math
        except Exception:
            pass
        n = int(self.sr * dur_s)
        if n <= 0:
            return False, '时长非法'
        wave = [amp * math.sin(2.0 * math.pi * freq * i / float(self.sr))
                for i in range(n)]
        try:
            ok = self.write(wave)
        except Exception as e:
            return False, '写入失败：%s: %s' % (type(e).__name__, e)
        if not ok:
            return False, '写入被中止'
        target = self.ring.n_written
        ok2, diag = self.wait_consumed(target, timeout_s=dur_s + 5.0)
        peak = amp
        return ok2, ('已播放 %.2f s %d Hz 正弦波（幅度 %.2f）；%s'
                     % (dur_s, freq, peak, diag if diag else '全部消费完毕'))

    def close(self):
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None


class TTSWorker:
    def __init__(self, device='GPU.0', voice='A', out_device=None, model_dir=None,
                 clone=False, bigvgan_ir=None, precision='f32',
                 out_wav=None, seed=1234, steps=25, cfg_rate=0.7):
        self.device = device
        self.voice = voice
        self.out_device = out_device
        self.model_dir = model_dir
        self.clone_mode = clone
        self.precision = precision   # OV 推理精度（f32 / f16）
        self.out_wav = out_wav       # 落盘模式：按真实时间轴混成一个 wav
        self.seed = seed
        self.steps = steps
        self.cfg_rate = cfg_rate
        self.model = None
        self.ov_rt = None            # OV 合成器（OVSynth 实例；非 torch 路径）
        self.ov_runtime = None       # OVRuntime 实例（供克隆音色/编码器链路用）
        self.bigvgan_ir = bigvgan_ir  # 指定 BigVGAN IR（多相分解版）
        self.conds = {}
        self.player = None
        self._clone_pcm = None       # 克隆说话人的 16 kHz PCM
        self._synth_lock = threading.Lock()
        self._stop = threading.Event()
        self._cancel_lock = threading.Lock()
        self._cancelled: set = set()  # 被主进程丢弃的句子 id
        # ── 🔴🔴🔴 APP-027④：**单一合成线程 + FIFO 队列** ──
        #   旧实现：主循环每收到一条 `synth` 就**新开一个线程**，
        #   线程们去抢 `threading.Lock` ⇒ **不保证先来先得**
        #   ⇒ 句子的**播出顺序**与提交顺序不一致（APP-027 问题③⑤）。
        #   ⇒ 现在：**一个**合成线程 + `queue.Queue`（FIFO）⇒ 顺序有保证。
        self._synth_q: 'queue.Queue' = queue.Queue()
        self._synth_thread = None
        # ── 🔴🔴🔴 APP-028②：**独立的「等播完」看门狗线程** ──
        #   起因（APP-028② 明文）：「语音播放的时候，**直接连续推理** TTS
        #   音频流，**不要等待播放完成**，还没有播放的部分存内存缓存」。
        #   ⇒ 旧实现里 `synth()` 结尾要 `wait_consumed()` 等本句音频
        #     **真的被声卡取走**才发 `played` ⇒ **合成线程被播放速度卡住**
        #     ⇒ 根本谈不上「连续推理」。
        #   ⇒ 现在：合成线程写完音频**立刻返回**（继续下一句），
        #     由**独立的看门狗线程**按 FIFO 顺序等「播完」并发 `played`。
        #   🔴 FIFO 保序：看门狗用一个 `queue.Queue` ⇒ `played` 的顺序
        #      == 合成的顺序（APP-027④ 的顺序保证**不能破**）。
        self._played_q: 'queue.Queue' = queue.Queue()
        self._played_thread = None
        # ── 🔴🔴🔴 APP-027②：**RTF 的 EWMA**（用于逐句自适应预缓冲）──
        #   `rtf` = 合成耗时 / 音频时长 ⇒ >1 表示「追不上播放」。
        #   预缓冲量 = `est_dur × (1 − 1/RTF_ewma)`（RTF ≤ 1 ⇒ 只留 0.3 s 底线）。
        self._rtf_ewma = None         # None = 还没有实测值
        self._rtf_win: deque = deque(maxlen=8)   # 最近 N 句的 RTF
        # ── 🔴🔴 APP-027④：**「音频秒/字」的 EWMA**（用于积压估算）──
        #   旧实现把「5 字/秒」写死 ⇒ 与实测偏差很大 ⇒ 积压估算偏高/偏低。
        #   ⇒ 现在用**本会话实测值**校准。
        self._sec_per_char = None     # None = 还没有实测值
        self._sec_per_char_win: deque = deque(maxlen=16)
        # ── 🔴🔴 APP-027④：**当前合成状态**（供主进程算积压）──
        self._synth_state_lock = threading.Lock()
        self._synth_jid = None        # 正在合成的句子 id
        self._synth_rem_s = 0.0       # 正在合成的句子的**剩余**预计时长
        self._synth_queue_ids: deque = deque()   # 排队中（尚未开始）的句子 id
        self._synth_queue_est = {}     # 排队句子的**预计时长**（秒）
        self._synth_text = {}          # 排队句子的原文（估时用）
        # ── BabelVox 路线（APP-004 第 2 条）──
        self.engine = None           # BabelVox 实例
        self.speaker_embed = None    # spkonly：预计算的 (1, 1024) 向量
        self.speaker_name = None     # 内置 speaker 名（用内置时有效）
        self.tts_cache_dir = None    # NPU 编译缓存目录
        self.sr = SR                # 当前引擎的采样率
        self._cur_jid = -1          # 当前正在合成的句子 id（供取消检查）
        # ── 🔴🔴 APP-027⑤：**克隆当前说话人**（本轮真正接入）──
        #   ⚠️ 隐私纪律（APP-022「共用约定」）：x-vector **只在内存里**，
        #   会话结束就丢弃、**不落盘、不进客户包**。
        self._clone_embed = None     # 当前克隆音色向量 (1, 1024)
        self._clone_updated_at = 0.0 # 克隆更新时刻（perf_counter）
        self._clone_audio_s = 0.0    # 克隆源音频时长（秒）
        self._clone_active = False   # 克隆是否**已生效**（失败时回落预设 A）
        # 🔴🔴🔴 APP-027 V3：**克隆音色向量/参考音频的「路线」**
        #   （`xvector` = BabelVox 的 spkonly 路线 / `ref_audio` = CUDA 边车）
        #   ⚠️ **必须单独记**：`_clone_active=True` 只说明「克隆已生效」，
        #   没说「走的是哪条路」⇒ 两条路的**音色来源证据完全不同**
        #   （x-vector 是 1024 维向量 / ref_audio 是参考 wav）
        #   ⇒ reviewer 做 CAMPPlus 对比时**需要知道这个**。
        self._clone_mode = None
        # 🔴🔴🔴 APP-027 V3：**本句合成时的音色快照**（逐句遥测用）
        #   ⚠️ 必须是「**合成那一刻**」的状态 ⇒ 不能用会话结束时的状态
        #   （会话结束时克隆可能已生效，但**前 20 句**用的是预设 A）。
        self._last_clone_active = False
        self._last_clone_mode = None
        self._last_clone_audio_s = 0.0
        # 🔴🔴 APP-027⑤：**克隆临时文件**（wav）
        #   ⚠️ 只在 `tempfile.gettempdir()` 下 ⇒ **不在客户包目录**
        #   ⚠️ **会话结束即删除**（`_cleanup_clone_files`）
        self._clone_tmp_paths: list = []
        self._clone_ref_path = None  # 当前给 CUDA 边车用的参考 wav
        # 🔴🔴 APP-027⑤：**预设 A 的缓存**（克隆失败时回落用）
        #   ⚠️ 回落**不能**重新算 embedding（要跑编码器 ⇒ 又慢又可能失败）
        #   ⇒ 在 `_setup_babelvox_voice()` 里把预设 A 的向量/路径**存一份**。
        self._preset_embed = None      # 预设 A 的 x-vector (1, 1024)
        self._preset_name = None       # 预设 A 的 speaker 名（None = 用向量）
        self._preset_ref_path = None   # 预设 A 的参考 wav 路径（CUDA 后端）
        # ── 落盘模式（--tts-out 回放测试）──
        self._timeline = []          # [(t_start_s, wav)]
        self._t0 = None
        self._jsonl_path = None      # 逐句记录文件（x.tts.jsonl）
        self._jsonl_rows = []
        # 🔴🔴 APP-024①：**worker 取到命令的时刻**（主循环写入、`synth()` 消费）
        #   ⇒ 用来把「首包」拆成「排队等待」与「合成首包」两段。
        self._dequeue_at = {}
        # 🔴 APP-021⑥：逐句 wav 落盘目录（None = 不落盘）
        self.dump_dir = None
        self._dump_seq = 0
        self._dump_paths = []
        # 🔴🔴 APP-022：当前句的说话人（**接口预留，本轮不集成**）
        #   ⚠️ 隐私纪律（APP-022「共用约定」）：x-vector **只在内存里**，
        #   会话结束就丢弃、**不落盘、不进客户包**。
        #   ⇒ 这里只存**标签**（S1/S2…）与置信度，**不是**向量本身。
        self._last_spk = None
        self._last_spk_conf = None
        # ── 🔴🔴🔴 APP-030⑤：逐句语言/失控可观测性 ────────────────────
        #   `self._last_lang`           本句**实际下传**的语言代号
        #   `self._last_lang_src`       'explicit'（主进程下传）/ 'guess'（兜底）
        #   `self._last_max_new_tokens` 本句传给引擎的**生成帧数上限**
        #   `self._last_end_reason`     结束原因：eos|cap|runaway|cancel|error
        self._last_lang = None
        self._last_lang_src = None
        self._last_max_new_tokens = None
        self._last_end_reason = None
        self._last_est_frames = None
        # 🔴 APP-030⑤：异常句落盘目录（`%LOCALAPPDATA%\Confucius4LiveCaption\tts_anomaly`）
        #   ⚠️ **只在本机**，**不进客户包**（隐私 + 包体积纪律）。
        self._anomaly_dir = None
        self._anomaly_count = 0
        # 🔴 APP-030⑤：异常句**最多保留 20 个**（FIFO 淘汰）
        self.ANOMALY_KEEP = 20

    # -- 模型加载 --------------------------------------------------------
    def load(self):
        t0 = time.perf_counter()

        # 🔴🔴 **只有 Qwen3-TTS（BabelVox）一条路**（APP-004 第 2 条：
        #   TTS 模型文件随客户包分发 ⇒ 客户机离线也能跑）。
        #
        # 🔴🔴🔴 APP-023③：**旧的 Confucius4-TTS 引擎回落已整段删除**。
        #   旧代码（`engine is None` 分支）会回落 `_try_load_ov()` / torch 参考实现，
        #   而旧引擎的**动态形状 IR 在 NPU 上必然编译失败**：
        #     ① `NPU_VCL ... Can't compute total shape size on dynamic shape`
        #     ② 第三个 IR 把 vpux 编译器打崩：`LLVM ERROR: Failed to infer
        #        result type(s)` ⇒ **进程级 abort**（`rc=3221226505` =
        #        0xC0000409，Python 的 try/except **接不住**）
        #   ⇒ 表现是「TTS worker 退出（rc=3221226505），已重启过一次仍失败」，
        #     而**真实原因（缺 babelvox 运行时）被完全掩盖**（用户 09:06 原话）。
        #   ⇒ 删除后：缺运行时就是缺运行时，界面会说人话（见
        #     `_babelvox_failure_reason`），不再是进程崩溃。
        #   ⚠️ 连带影响：`self.conds` / `self.ov_rt` / `self.tts_model` /
        #      `self.NS` 这些**旧引擎专属字段**不再被设置 ⇒ 合成路径
        #      （`_synth` 按 `self.engine is not None` 分派）只会走 BabelVox
        #      分支 ⇒ 旧分支代码成为死代码（暂留，不动它们以免引入新风险）。
        engine = self._try_load_babelvox()   # 🔴 失败即抛（不再返回 None）

        # ── BabelVox 路线（spkonly）──
        self.engine = engine
        self.model = engine
        self._setup_babelvox_voice()
        # 🔴 BabelVox 输出 24000 Hz（旧的 22050 播放流会变调/加速）
        #    ⇒ 播放流必须按新采样率**重建**。
        self.sr = TTS_SR
        self._reopen_player(TTS_SR)

        log(f'[tts_worker] 模型加载完成 {time.perf_counter() - t0:.1f}s')
        emit({'kind': 'ready', 'device': self.device, 'voice': self.voice})

    def _reopen_player(self, sr: int):
        """按新的采样率**重建**播放流。

        🔴 为什么要重建：`Player` 在构造时用 `samplerate=sr` 建了
        `sounddevice.OutputStream`，采样率是**流级属性**，之后改不了。
        BabelVox 输出 24000 Hz，而旧引擎是 22050 Hz
        ⇒ 播放流必须跟着引擎走，否则**变调/加速**。
        """
        if self.player is None:
            return
        try:
            self.player.close()
        except Exception:
            pass
        try:
            self.player = Player(device=self.out_device, sr=sr)
            log(f'[tts_worker] 播放流已按 {sr} Hz 重建')
        except Exception as e:
            log(f'[tts_worker] 播放流重建失败（{e}）⇒ 语音输出不可用')
            self.player = None

    def _try_load_babelvox(self):
        """加载 Qwen3-TTS 的 BabelVox 引擎。

        🔴🔴🔴 APP-023③：**不再返回 None、不再回落旧引擎**。
        旧行为（实测 2026-10-27 08:56 会话日志）：
          babelvox 缺失 ⇒ `return None` ⇒ `load()` 回落 `_try_load_ov()`
          ⇒ 编译 **Confucius4-TTS 旧引擎**的动态形状 IR ⇒ 在 NPU 上
          ① `Can't compute total shape size on dynamic shape`
          ② 第三个 IR 直接把 vpux 编译器打崩
             `LLVM ERROR: Failed to infer result type(s)`
             ⇒ **进程级 abort**（`rc=3221226505` = 0xC0000409，try/except **接不住**）
          ⇒ 用户看到的是「TTS worker 退出（rc=3221226505）」，
             **真实原因（缺运行时）被彻底掩盖**。
        ⇒ TTS 后端 10-22 起已换成 Qwen3-TTS ⇒ **旧引擎回落在 NPU/GPU 上
          没有任何成功的可能，只会把「缺运行时」变成「进程崩溃」**。
        ⇒ 现在：一律带真实原因抛出（不分设备），由上层翻译成人话。

        ⚠️ 这条路径**不 import torch**（babelvox 只用 transformers 的 tokenizer）。
        """
        try:
            import tts_engine
            # 🔴🆕 **`device='CUDA'` 走独立后端**（STATUS §40）：
            #   不是 OV 的 CUDA plugin（官方发行版根本不带），而是
            #   **PyTorch + faster-qwen3-tts**，跑在独立 venv（+5.7 GB，不进客户包）
            #   ⇒ 由 `tts_cuda` 以**子进程边车**调用，模型只加载一次。
            #   ⚠️ 客户机没这个 venv 时 `available()` 为 False ⇒ GUI 不列该项。
            if str(self.device).upper().startswith('CUDA'):
                import tts_cuda
                if not tts_cuda.available():
                    raise RuntimeError('CUDA 后端不可用：找不到 %s'
                                       % tts_cuda.python_exe())
                log('[tts_worker] 使用 PyTorch+CUDA 后端（faster-qwen3-tts 边车）')
                eng = tts_cuda.CudaTTSEngine(on_log=log)
                eng.start()
                return eng
            # 🔴🔴 **必须传 precision**（2026-10-25 修）：
            #   之前**没传** ⇒ GUI 的「精度 f32/f16」下拉**完全无效**
            #   （BabelVox 内部自建 ov.Core，不传任何 property）。
            #   ⇒ 用户在 GUI 里选 f16 也毫无作用（摆设）。
            eng = tts_engine.make_engine(device=self.device,
                                         cache_dir=self.tts_cache_dir,
                                         on_log=log,
                                         precision=self.precision)
            return eng
        except Exception as e:
            import traceback
            tb = traceback.format_exc()[-1000:]
            # 🔴🔴 §52：**CUDA 后端失败不能静默回落**。
            #   旧行为：CUDA 边车起不来 ⇒ 这里只打一行「BabelVox 引擎不可用」
            #   ⇒ 回落 `_try_load_ov`（CUDA 设备必然也失败）⇒ 回落 torch 参考
            #   实现 `import tts_model`（包内没有）⇒ 最终报出去的是
            #   「**模型加载失败：No module named 'tts_model'**」
            #   ⇒ **与真实原因（边车）毫无关系**，用户和我都被误导过。
            #   ⇒ 现在：CUDA 直接带着真实原因抛上去（反正回落也必然失败）。
            if str(self.device).upper().startswith('CUDA'):
                log(f'[tts_worker] 🔴 CUDA 后端启动失败（不回落旧引擎）：{e}')
                log(tb)
                raise RuntimeError(f'CUDA 后端启动失败：{e}') from e
            # 🔴🔴 APP-023③：**缺运行时** 与 **运行时有但加载失败** 要说不同的话
            #   ⇒ 否则用户看到的都是同一句「BabelVox 引擎不可用」，无从下手。
            log(f'[tts_worker] 🔴 Qwen3-TTS 引擎不可用（{e}）'
                f'（不回落旧引擎 —— 见 _try_load_babelvox 的 docstring）')
            log(tb)
            raise RuntimeError(_babelvox_failure_reason(
                e, getattr(self, 'device', ''),
                getattr(self, 'precision', ''))) from e

    def _setup_babelvox_voice(self):
        """准备音色（spkonly 路线）。

        🔴🔴 **只传 `speaker_embed`，禁止传 `ref_text` / `ref_audio`**
        （交接单 §5.1 / TTS-005：babelvox 的 ref_text 路径不是官方 ICL，
        codec 轨道没有 ref_code ⇒ 分布外 prompt ⇒ EOS 不稳）。

        优先级：
        1. 用户指定的内置 speaker（`--voice cindy`）⇒ 零体积；
        2. 预设音色 A 的参考 wav ⇒ 预计算 speaker embedding（只算一次）。
        """
        import tts_engine

        key = (self.voice or 'A').strip()
        # 🔴🔴 **2026-10-26 §48（APP-018 第 2 条）**：客户包里**没有**内置音色
        #   （`babelvox/data/speakers/` 已作为第三方素材排除）⇒ 必须先探测。
        #   旧实现只看「名字在 BUILTIN_SPEAKERS 里」就直接用 ⇒ 客户机上
        #   会在 babelvox 内部才炸（`speaker library not set` / 文件不存在）
        #   ⇒ 表现为「语音输出没有声音」，很难定位。
        avail = tts_engine.builtin_speakers_available()
        if key.lower() in tts_engine.BUILTIN_SPEAKERS:
            if key.lower() in avail:
                self.speaker_embed = None
                self.speaker_name = key.lower()
                # 🔴🔴 APP-027⑤：**缓存预设音色**（克隆失败时回落用）
                self._preset_embed = None
                self._preset_name = self.speaker_name
                log(f'[tts_worker] 使用内置 speaker：{self.speaker_name}')
                return
            log(f'[tts_worker] ⚠️ 内置 speaker「{key}」在当前环境不可用'
                f'（客户包不分发第三方音色文件，可用：{avail or "无"}）'
                f' ⇒ 改用参考 wav（音色 A）')
            # ↓ 继续走参考 wav 路线（音色 A）

        wav = tts_engine.preset_voice_path()
        if getattr(self.engine, 'USES_REF_AUDIO', False):
            # 🔴 CUDA 后端自己用参考音频做 x-vector（`ref_audio=` + `xvec_only=True`）
            #   ⇒ 不要在这里算 embedding（边车在另一个进程，没有 babelvox 编码器）
            self.speaker_embed = None
            self.speaker_name = 'A'
            # 🔴🔴 APP-027⑤：**缓存预设 A 的参考 wav**（克隆失败时回落用）
            self._preset_ref_path = wav
            log(f'[tts_worker] CUDA 后端自行使用参考音频做音色：{wav}')
            return
        self.speaker_embed = tts_engine.speaker_embedding(self.engine, wav, on_log=log)
        self.speaker_name = 'A'
        # 🔴🔴 APP-027⑤：**缓存预设 A 的向量**（克隆失败时回落用）
        self._preset_embed = self.speaker_embed
        self._preset_name = self.speaker_name
        if self.speaker_embed is None:
            # 🔴 内置音色也不可用（客户机）⇒ 只能报「没有音色」
            #   ⇒ 旧实现在这里硬回落 'cindy' ⇒ 客户机上必然失败
            #   ⇒ 改成：有可用内置音色才回落，否则让 `synth()` 走
            #      「没有可用的音色」句子级错误路径（带 id ⇒ 不影响后续句子）。
            fallback = next((s for s in avail), None)
            if fallback:
                log(f'[tts_worker] ⚠️ 没有可用音色 ⇒ 退回内置 speaker {fallback}')
                self.speaker_name = fallback
            else:
                log('[tts_worker] 🔴 没有可用音色（参考 wav 算不出 embedding，'
                    '且无内置音色文件）⇒ 语音输出将逐句报错')

    def _try_load_ov(self):
        """尝试加载 OpenVINO 版运行时包（tts_ov）。失败则回落到 torch。

        ⚠️ **OV 路径下绝不 import torch**（C-101 铁律）。

        ⚠️ **本函数返回的是 `OVSynth` 实例**（不是 `OVRuntime`）：
        `OVSynth` 才有整句合成入口 `synth()`。
        （旧实现返回 `OVRuntime` 且调用不存在的 `synth_ov.synth_whole(...)`
          ⇒ OV 路径一跑就崩，会静默回落到 torch，违反「运行时不能依赖 torch」的铁律。）

        ⚠️ **IR 路径必须显式给对**（2026-10-22 修）：
        - `OVRuntime` 默认找 `ir/` 下的 `bigvgan_dynamic.xml`，那份**在 GPU 上算错**
          （SNR ≈ -8 dB，见 runtime.py 注释）⇒ 改用 `ir_dyn/bigvgan_poly.xml`（多相版）；
        - `s2a_estimator` 在 `ir_dyn/` 里叫 `s2a_estimator_f32.xml` / `_f16.xml`；
        - `ir_dir` 指向 `ir_dyn`，`OVRuntime.load()` 再按候选列表兜底。
        """
        try:
            tts_dir = os.environ.get('LIVECAP_TTS_DIR', '').strip()
            candidates = [p for p in [tts_dir, r'C:\Users\Trekker-PTL\confucius4-tts'] if p]
            for d in candidates:
                if os.path.isdir(os.path.join(d, 'tts_ov')):
                    if d not in sys.path:
                        sys.path.insert(0, d)
                    from tts_ov.runtime import OVRuntime, IR_DYN_DIR
                    from tts_ov.synth_ov import OVSynth

                    ptag = 'f16' if self.precision in ('f16', 'fp16') else 'f32'
                    # ── BigVGAN IR（多相版优先）──
                    bg = self.bigvgan_ir
                    if not bg:
                        for cand in ('bigvgan_poly.xml', 'bigvgan_poly_dyn.xml'):
                            p = os.path.join(IR_DYN_DIR, cand)
                            if os.path.exists(p):
                                bg = p
                                break
                    # ── S2A estimator IR（按精度）──
                    s2a = os.path.join(IR_DYN_DIR, f's2a_estimator_{ptag}.xml')
                    if not os.path.exists(s2a):
                        s2a = None

                    rt = OVRuntime(device=self.device, precision=self.precision,
                                   ir_dir=IR_DYN_DIR, verbose=True,
                                   bigvgan_ir=bg, s2a_estimator_ir=s2a)
                    rt.load()
                    synth = OVSynth(rt, device=self.device,
                                    precision=self.precision,
                                    use_torch_rng=True,
                                    bigvgan_ir=bg, s2a_estimator_ir=s2a)
                    # 保留 OVRuntime 引用（克隆音色 / 编码器链路要用）
                    self.ov_runtime = rt
                    log(f'[tts_worker] BigVGAN IR = {os.path.basename(bg) if bg else "（自动）"}'
                        f' / S2A = {os.path.basename(s2a) if s2a else "（自动）"}')
                    return synth
        except Exception as e:
            log(f'[tts_worker] OpenVINO 运行时不可用（{e}），用 torch 回落')
            import traceback
            log(traceback.format_exc()[-1200:])
        return None

    def _load_conds(self):
        """加载音色条件。

        **优先从 npz 加载**（C-101 P4 第 3 条：预设音色的 conditioning 预先算好，
        存为 `live_caption\\voices\\*.npz`，运行时直接加载）。
        这样 App 运行时**完全不需要 torch**（C-101 铁律），也省掉 w2v-BERT +
        CAMPPlus 的前向（w2v-BERT 是 17 层 transformer，CPU 上要几秒）。

        npz 的键（与 `tts_model.py::extract_cond` 对齐）：
            semantic_features  (1, T_feat, 1024)  float32
            style_embedding    (1, 192)          float32
            reference_mel      (1, T_mel, 80)    float32

        没有 npz 时才回落到「用 torch 从 wav 现场算」。
        """
        import numpy as np

        out = {}
        base = os.environ.get('LIVECAP_TTS_DIR', '').strip() or \
            r'C:\Users\Trekker-PTL\confucius4-tts'
        vdir = os.path.join(_HERE, 'voices')

        # ① npz 优先（无需 torch）
        for key, fn in (('A', 'preset_A.npz'), ('B', 'preset_B.npz'),
                        ('clone', 'clone_C.npz')):
            p = os.path.join(vdir, fn)
            if not os.path.exists(p):
                continue
            try:
                z = np.load(p)
                out[key] = {
                    'semantic_features': z['semantic_features'].astype(np.float32),
                    'style_embedding': z['style_embedding'].astype(np.float32),
                    'reference_mel': z['reference_mel'].astype(np.float32),
                }
                log(f'[tts_worker] 音色 {key} 条件就绪（npz，'
                    f'semantic{out[key]["semantic_features"].shape}）')
            except Exception as e:
                log(f'[tts_worker] 音色 {key} npz 加载失败：{e}')

        if out:
            return out

        # ② 回落：现场从 wav 算（需要 torch）
        log('[tts_worker] 没有找到 voices/*.npz，回落到现场计算（需要 torch）')
        vdir_wav = os.path.join(base, 'golden', 'voices')
        presets = {
            'A': os.path.join(vdir_wav, 'preset_A.wav'),
            'B': os.path.join(vdir_wav, 'preset_B_new.wav'),
        }
        for k, p in presets.items():
            if not os.path.exists(p):
                log(f'[tts_worker] 缺少音色文件：{p}')
                continue
            try:
                out[k] = self.tts_model.extract_cond(self.model, p)
                log(f'[tts_worker] 音色 {k} 条件就绪')
            except Exception as e:
                log(f'[tts_worker] 音色 {k} 条件提取失败：{e}')
        # 克隆 C：会议录音里截的干净人声
        clone_wav = os.path.join(vdir_wav, 'clone_C.wav')
        if os.path.exists(clone_wav):
            try:
                out['clone'] = self.tts_model.extract_cond(self.model, clone_wav)
                log('[tts_worker] 克隆音色 C 条件就绪')
            except Exception as e:
                log(f'[tts_worker] 克隆音色 C 条件提取失败：{e}')
        return out

    # -- 合成 ------------------------------------------------------------
    def synth(self, jid: int, text: str, spk=None, spk_conf=None, lang=None):
        """合成一句并播放。

        三条路径：
        - **BabelVox**（`self.engine` 存在）—— Qwen3-TTS，**不碰 torch**；
        - OV 路径（`self.ov_rt` 存在）—— 旧 OVSynth，**不碰 torch**；
        - 否则回落到 torch 的 `native_stream.synth_stream`。

        ⚠️ **落盘模式**（`--out-wav`）：不实时播放，而是按**真实时间轴**
        把每句记到时间轴上，最后混成一个 wav（C-101 P4 第 6 条）。

        🔴🔴 APP-022：`spk` / `spk_conf` **接口预留**（说话人标签）。
        🔴🔴🔴 APP-029（2026-10-27 15:48 用户决定）：
          **pyannote/segmentation-3.0 只用来识别说话人，不再用来断句**
          ⇒ 断句继续用 R2T2 原有的方式；
          ⇒ pyannote 走**旁路**、**不阻塞定稿**（定稿段先发出去）；
          ⇒ spk 晚到（可晚 1~2 s）时用 `spk_update(id, spk, spk_conf)` 补发
            ⇒ 更新字幕标签 + **还没开始合成**的那几句的音色；
            **已经开始合成的句子不改**。
        ⚠️ **本轮不集成**（APP-029 明文「现在不要集成」）：
          等 TTS-019 交付「按句子取对应说话人的音色向量」
        ⇒ 这里**只把字段接住并记进遥测**，**不改变任何合成行为**。
        ⇒ 隐私纪律（APP-022「共用约定」）：x-vector 只在内存里，
        会话结束就丢弃、**不落盘、不进客户包**。

        🔴🔴🔴 APP-030①：`lang` = **主进程显式下传的目标语言**。
          - 有 `lang` ⇒ **直接用**（不再猜）；
          - 无 `lang`（旧命令）⇒ 退回 `_guess_lang()`（兜底）。
        """
        import numpy as np

        t_submit = time.perf_counter()
        # 🔴🔴 APP-024①：合成段的起点 = **worker 取到命令**的时刻
        #   （主循环已把它记在 `self._dequeue_at[jid]`）。
        #   ⚠️ 兜底：若缺（异常路径）⇒ 退回 `t_submit`
        #   ⇒ 此时 `synth_s` 会含一点线程启动延迟，但**不会崩**、不会缺字段。
        t_dequeue = self._dequeue_at.pop(jid, None)
        if t_dequeue is None:
            t_dequeue = t_submit
        # 🔴🔴🔴 APP-030①：**显式语言优先**
        #   旧实现无条件 `lang = self._guess_lang(text)` ⇒ **永远收不到 Japanese**
        #   （reviewer 实测 8 条日文样句 5 条判 en / 3 条判 zh）。
        #   ⇒ 现在：有 `lang` 就用它；没有才猜（兜底）。
        lang_src = 'explicit' if lang else 'guess'
        if not lang:
            lang = self._guess_lang(text)
        lang = (lang or 'en').strip().lower()
        # 🔴🔴🔴 APP-030⑤：**记录本句的语言口径**（可观测性的第一项）
        self._last_lang = lang
        self._last_lang_src = lang_src
        self._last_end_reason = None
        # 🔴🔴🔴 APP-027 V3：**本句合成时的「音色来源」快照**
        #   ⇒ **必须在合成之前取**（不是会话结束时）⇒
        #     前若干句（还没攒够语音）天然是 `clone_active=False`
        #     ⇒ 这正是事实（那几句确实用的是预设 A）。
        #   ⚠️ **不能**用会话结束时的 `_clone_active` ⇒
        #     那会把**前 20 句**也标成克隆 ⇒ reviewer 的 CER/CAMPPlus 对比
        #     会把「预设 A 的音」算进「克隆组」⇒ **结论失真**。
        self._last_clone_active = bool(self._clone_active)
        self._last_clone_mode = self._clone_mode
        self._last_clone_audio_s = float(self._clone_audio_s or 0.0)
        is_babelvox = self.engine is not None
        # 🔴 APP-022：记住本句的说话人（**只在本进程内存里**）
        self._last_spk, self._last_spk_conf = spk, spk_conf

        if is_babelvox:
            # BabelVox 路线：音色由 speaker_embed / 内置 speaker 提供
            if self.speaker_embed is None and not self.speaker_name:
                # 🔴 2026-10-24 §22：**句子级**错误必须带 `id`
                #   （主进程据此判定「这一句失败」而不是「worker 整体挂了」）
                emit({'kind': 'error', 'message': '没有可用的音色', 'id': jid})
                return
            cond = None
        else:
            key = self.voice
            if key not in self.conds:
                # 🔴 2026-10-24 §22：**句子级**错误必须带 `id`（同上一处）
                emit({'kind': 'error', 'message': f'没有可用的音色：{key}', 'id': jid})
                return
            cond = self.conds[key]

        # 主进程可能已经因为积压超限丢弃了这一句（C-101 P4 第 2 条）
        if self._is_cancelled(jid):
            log(f'[tts_worker] 句子 id={jid} 已被丢弃，跳过合成')
            self._record_jsonl(jid, text, t_submit, dropped=True)
            return

        # 🔴🔴 2026-10-26 §48（APP-018 第 1 条）：**流式合成 + 边合成边播**。
        #   旧实现：`_synth_babelvox()` 把**所有块收完**才 `return list`
        #   ⇒ `first_packet` 只能在**整句合成完成之后**才发
        #   ⇒ App 报的「首包」= **整句合成耗时**（实测 8.36 s），
        #     而**真实流式首包只要 1.16 s** ⇒ **流式能力被完全浪费**（差 7.2×）
        #     ⇒ 听感上也是「整句合成完才出声」。
        #   新实现：三条路径统一成**迭代器**，在 `_synth_lock` 内**边收边写**
        #      环形缓冲 ⇒ 第一块到达即发声、即报首包。
        #   ⚠️ 附带修掉一个旧隐患：旧实现的 `player.write()` 在**锁外**
        #      ⇒ 两句的音频可能**交错**进同一个环形缓冲；现在写入也在锁内
        #      ⇒ 句子之间**严格有序**。
        #   ⚠️ 中途失败（如缓冲 stall）：已写入的**部分音频会播出去**，
        #      但**不发 `played`** ⇒ 主进程记为「这一句失败」
        #      ⇒ 不变式 `n_played + n_dropped == n_submitted` 仍成立。
        chunks = None
        t_first = None
        latency = None
        n_samples = 0
        n_parts = 0
        aborted = False
        # 🔴🔴🔴 APP-030②：**RUNAWAY 标记**（worker 侧第三道闸触发时置 True）
        runaway = False
        # 🔴🔴🔴 APP-030②：**RUNAWAY 阈值（秒）**
        #   公式（APP-030② 明文）：`max(3×估计, 估计+8 s)`
        #   估计 = 按语言估的音频秒数（`tts_engine.estimate_sec`）
        #   ⚠️ 估不出来 ⇒ 不做这道闸（宁可漏判也不误杀）。
        try:
            import tts_engine as _te
            _runaway_s = _te.runaway_threshold_s(
                _te.estimate_sec(text, lang))
        except Exception:
            _runaway_s = None
        # 🔴🔴🔴 APP-030⑤：**本句的估计帧数**（遥测字段）
        try:
            self._last_est_frames = _te.estimate_frames(text, lang)
        except Exception:
            self._last_est_frames = None
        wav_parts = []
        # 🔴🔴🔴 APP-030⑤：**异常句落盘的滚动缓冲**（**有界**）
        #   `maxlen=48` 块 ≈ 48 s 音频（12 fps × 4 s/块）
        #   ⇒ 失控句的「出事段」一定在里面 ⇒ reviewer 能拿到音频。
        _anom_buf = deque(maxlen=48)
        # 🔴🔴 APP-021②：本句的**幅度/数值**统计（用于判定「合成出来是不是静音」）。
        #   ⚠️ 必须逐块累计，不能只在最后算一次（分块流式），
        #   也不能 import numpy 到模块顶层（numpy 预导入见 main()）。
        peak = 0.0
        sum_sq = 0.0
        n_nan = 0
        n_inf = 0
        # 播放侧计数器基线（用于算「本句期间」的增量）
        base_cb = 0
        base_read = 0
        base_underflow = 0
        # 🔴🔴🔴 APP-027②：本句的**时间戳**（遥测拆字段的核心）
        #   `t_dequeue`  = 从 FIFO 队列**取出**这句的时刻
        #   `t_first`    = **第一块**音频合成出来的时刻
        #   `t_last`     = **最后一块**合成出来的时刻
        #   ⇒ `synth_rtf` = (t_last − t_dequeue) / 音频时长
        # ⇒ 旧的 `latency_s`（submit → 首块）**保留**（旧消费方不受影响）。
        t_last = None
        # 🔴🔴🔴 APP-027①：**逐句自适应预缓冲** —— 攒够多少才允许出声。
        #   目标：把「句内多次欠载」变成「句前等一次」。
        #   公式：`max(0.3 s, est_dur × (1 − 1/RTF_ewma))`
        #   - `est_dur` = 本句预计音频时长（按「音频秒/字」EWMA 估）
        #   - `RTF_ewma` = 本会话最近 N 句实测 RTF 的 EWMA
        #   - RTF ≤ 1（追得上）⇒ 只保留 0.3 s 底线（不要无谓地等）
        #   - RTF > 1（追不上）⇒ 预缓冲 = 句长 × (1 − 1/RTF)
        #     （正好补上「合成比播放慢的那部分」⇒ 播放时不再欠载）
        #   ⚠️ **句间不插静音**：预缓冲只是「**延后开始出声**」，
        #      上一句播完时下一句若已攒够 ⇒ 直接接上（不补零）。
        prebuffer_s = self._compute_prebuffer_s(text)
        # 本句**首块写入前**的环形缓冲位置（用于切分欠载事件）
        first_chunk_start = None
        # 🔴 APP-027①：**本句已写进环形缓冲的样本数**（预缓冲判定用）
        buffered_samples = 0
        synth_started = False
        # 🔴 APP-027①：预缓冲**没攒够**就播了（宁可句内欠载也不能不出声）
        prebuffer_short = False
        try:
            with self._synth_lock:
                if self._is_cancelled(jid):
                    return
                self._cur_jid = jid
                if is_babelvox:
                    chunks = self._synth_babelvox(text, lang)      # 生成器
                elif self.ov_rt is not None:
                    chunks = iter(self._synth_ov(text, lang, cond))
                else:
                    chunks = iter(self._synth_torch(text, lang, cond))

                if self.player is not None:
                    base_cb = self.player.n_cb
                    base_read = self.player.ring.n_read
                    base_underflow = self.player.n_underflow

                # ── 流式主循环：收到一块 ⇒ **攒够预缓冲**才发声 ────────
                #
                # 🔴🔴🔴 APP-027①：**逐句自适应预缓冲**（本轮新增的核心机制）
                #
                #   起因（APP-027 问题②，用户实测「NPU 明显卡顿」）：
                #     RTF 从 0.80 升到约 1.5（资源争用）⇒ 合成**追不上**播放
                #     ⇒ 句内**来不及合成** ⇒ 环形缓冲欠载 ⇒ 听感「断断续续」。
                #     实测 NPU 实时 13 句：墙钟/音频比均值 **1.61**、
                #     underflow 合计 **389**。
                #
                #   旧做法（无效）：「边合成边播」⇒ 第一块一到就出声
                #     ⇒ 只要 RTF>1，**句内必然欠载** ⇒ 卡顿不可避免。
                #
                #   新做法：**先攒够再出声**
                #     预缓冲量 = `max(0.3 s, est_dur × (1 − 1/RTF_ewma))`
                #     - RTF ≤ 1（追得上）⇒ 只留 **0.3 s 底线**（不无谓地等）
                #     - RTF > 1（追不上）⇒ 预缓冲 = 句长 × (1 − 1/RTF)
                #       ⇒ 正好补上「合成比播放慢的那部分」
                #       ⇒ 播放开始时缓冲里已有足够音频 ⇒ **句内不再欠载**
                #     ⇒ 卡顿从「句内多次」变成「**句前等一次**」。
                #
                #   ⚠️ **句间不插静音**：预缓冲只是「延后开始出声」，
                #      **不补零**。上一句播完时下一句若已攒够 ⇒ 直接接上。
                #   ⚠️ 攒不够怎么办：合成结束还没攒够 ⇒ **照样播出**
                #      （宁可句内欠载，也不能不出声）⇒ 记 `prebuffer_short=True`。
                need_samples = int(prebuffer_s * (self.sr or SR))
                # 🔴🔴 APP-027①：**预缓冲的累加区**（先攒在本地，攒够再写进环形缓冲）
                #   ⚠️ **不能**一开始就写进环形缓冲 ⇒ 播放回调会立刻取走
                #      ⇒ 本句从第一毫秒就开始播 ⇒ 缓冲永远攒不够
                #      ⇒ 预缓冲形同虚设。
                #   ⇒ 攒够（或合成结束）时**一次性**写进环形缓冲。
                pending_chunks = []
                pending_samples = 0

                def _flush_prebuffer():
                    """把攒下的块写进环形缓冲（**只在预缓冲达成时调用**）。"""
                    nonlocal synth_started, first_chunk_start
                    if not pending_chunks:
                        return True
                    try:
                        if first_chunk_start is None:
                            first_chunk_start = self.player.ring.n_written
                    except Exception:
                        first_chunk_start = 0
                    for pc in pending_chunks:
                        self.player.write(
                            pc,
                            should_stop=lambda: (
                                self._is_cancelled(jid)
                                or self._stop.is_set()))
                    pending_chunks.clear()
                    synth_started = True
                    return True

                for w in chunks:
                    if self._stop.is_set() or self._is_cancelled(jid):
                        aborted = True
                        break
                    # 🔴🔴🔴 APP-030⑤：**滚动保留最近若干块**（异常句落盘用）
                    #   ⚠️ **有界**（deque maxlen）⇒ 不会无界增长
                    #   ⚠️ 只在本句**还没结束**时累计 ⇒ 正常句也会留最近 48 块
                    #     （≈48 s 音频）⇒ 足够覆盖失控句的「出事段」。
                    _anom_buf.append(w)
                    # 🔴🔴🔴 APP-030②：**worker 侧第三道闸（兜底的 RUNAWAY）**
                    #   判据：本句**已收音频秒数** > `max(3×估计, 估计+8 s)`
                    #   ⇒ 判 RUNAWAY ⇒ **停止播放该句剩余部分**
                    #   ⚠️ 这是**引擎无关**的兜底（babelvox / 边车都适用）
                    #      ⇒ 即使引擎侧上限没生效（老引擎 / 参数被忽略），
                    #        这一道**仍然能挡住**「一句拖 100 秒」。
                    #   ⚠️ 阈值**故意宽松** ⇒ 宁可漏判也不误杀正常句。
                    try:
                        _got_s = n_samples / float(self.sr or SR)
                        if _runaway_s is not None and _got_s > _runaway_s:
                            runaway = True
                            self._last_end_reason = 'runaway'
                            log('[tts_worker] 🔴 RUNAWAY id=%d lang=%s len=%d '
                                '已收 %.1f s > 阈值 %.1f s ⇒ 中止本句'
                                % (jid, lang, len(text), _got_s, _runaway_s))
                            break
                    except Exception:
                        pass
                    if t_first is None:
                        t_first = time.perf_counter()
                        latency = t_first - t_submit
                        # 🔴🔴 APP-024①：**首包拆成两段上报**。
                        #   旧实现只有 `latency_s` = 「submit → 首块到达」一个总值
                        #   ⇒ 里面**混着**两件完全不同的事：
                        #     ① **排队等待**（主进程提交 ⇒ worker 还没取到命令）
                        #     ② **合成首包**（worker 内部真正在算的那一段）
                        #   ⇒ §49.7 实测「首包 P50 17.29 s」量到的是
                        #     **加载期攒下的队一次性倒出来**（批量提交 ⇒ 排队段巨大）
                        #     ⇒ 混在一个数里**根本分不开** ⇒ 永远查不清。
                        #   ⇒ 现在 worker 侧先报**自己口径**的合成段：
                        #       `synth_s` = t_first − t_dequeue（worker 内部时钟）
                        #     排队段由**主进程**算（跨进程时钟不可比）：
                        #       `queued_s` = t_sent − t_submit
                        #   ⇒ `latency_s` 保留（= queued_s + synth_s 的旧口径）
                        #     **不删** ⇒ 旧消费方（ABBA 报告）不受影响。
                        emit({'kind': 'first_packet',
                              'latency_s': round(latency, 3), 'id': jid,
                              'synth_s': round(t_first - t_dequeue, 3),
                              't_dequeue': round(t_dequeue, 4)})
                    t_last = time.perf_counter()
                    n_samples += len(w)
                    n_parts += 1
                    # ── APP-021②：本块幅度统计 ──────────────────────
                    try:
                        if len(w):
                            wf = np.asarray(w, dtype=np.float64)
                            p = float(max(abs(float(wf.min())),
                                           abs(float(wf.max()))))
                            if p > peak:
                                peak = p
                            sum_sq += float((wf ** 2).sum())
                            n_nan += int(np.count_nonzero(np.isnan(wf)))
                            n_inf += int(np.count_nonzero(np.isinf(wf)))
                    except Exception:
                        pass
                    if self.out_wav or self.dump_dir:
                        # ⚠️ 落盘模式**不逐块入时间轴**：块的到达间隔
                        #   （= 合成耗时）通常 **> 音频时长**（RTF>1）
                        #   ⇒ 逐块入轴会把一句话**拉散成断续的碎片**。
                        #   ⇒ 这里只**整句累加**，收尾时一次性入轴
                        #   （与旧实现语义一致：一句话 = 一个时间点）。
                        # 🔴 APP-021⑥：需要逐句 wav 时也整句累加（供落盘）。
                        wav_parts.append(w)
                    if self.out_wav:
                        # 🔴 APP-021⑥：落盘模式下**不实时播放**
                        #   （与旧语义一致：只混时间轴，不出声）。
                        continue
                    if self.player is None:
                        continue
                    # 🔴🔴 APP-027①：**先攒进预缓冲区**，攒够才写进环形缓冲。
                    pending_chunks.append(w)
                    pending_samples += len(w)
                    if pending_samples >= need_samples:
                        # 🔴 预缓冲**达成** ⇒ 一次性写进去 ⇒ 本句开始出声
                        #   ⇒ 之后的欠载才算「**句内欠载**」（卡顿）。
                        try:
                            _flush_prebuffer()
                        except TimeoutError as e:
                            log(f'[tts_worker] 播放缓冲写满，阻塞超时：{e}')
                            emit({'kind': 'error',
                                  'message': f'播放缓冲写满：{e}',
                                  'id': jid, 'dropped': True})
                            self._record_jsonl(jid, text, t_submit,
                                               dropped=True, t_first=t_first,
                                               tel=self._app027_partial_tel(
                                                   t_dequeue, t_first, t_last,
                                                   prebuffer_s, prebuffer_short))
                            return
                        except Exception as e:
                            diag = ''
                            try:
                                diag = (' [诊断: 回调 %d 次, 已写 %d, 已读 %d, 缓冲 %d/%d]'
                                        % (self.player.n_cb,
                                           self.player.ring.n_written,
                                           self.player.ring.n_read,
                                           self.player.ring.level(),
                                           self.player.ring._cap))
                            except Exception:
                                pass
                            log(f'[tts_worker] 播放写入失败：{e}{diag}')
                            emit({'kind': 'error',
                                  'message': f'播放写入失败：{e}{diag}',
                                  'id': jid})
                            self._record_jsonl(jid, text, t_submit,
                                               error=(str(e) + diag)[:300],
                                               tel=self._app027_partial_tel(
                                                   t_dequeue, t_first, t_last,
                                                   prebuffer_s, prebuffer_short))
                            return
                # 🔴🔴 APP-027①：合成**结束**时，若预缓冲**还没攒够**
                #   ⇒ **照样写进去**（宁可句内欠载，也不能不出声）
                #   ⇒ 记 `prebuffer_short=True`（遥测里能看到）。
                if pending_chunks and not aborted:
                    prebuffer_short = True
                    try:
                        _flush_prebuffer()
                    except TimeoutError as e:
                        log(f'[tts_worker] 播放缓冲写满，阻塞超时：{e}')
                        emit({'kind': 'error',
                              'message': f'播放缓冲写满：{e}',
                              'id': jid, 'dropped': True})
                        self._record_jsonl(jid, text, t_submit,
                                           dropped=True, t_first=t_first,
                                           tel=self._app027_partial_tel(
                                               t_dequeue, t_first, t_last,
                                               prebuffer_s, prebuffer_short))
                        return
                    except Exception as e:
                        log(f'[tts_worker] 播放写入失败：{e}')
                        emit({'kind': 'error',
                              'message': f'播放写入失败：{e}', 'id': jid})
                        self._record_jsonl(jid, text, t_submit,
                                           error=str(e)[:300],
                                           tel=self._app027_partial_tel(
                                               t_dequeue, t_first, t_last,
                                               prebuffer_s, prebuffer_short))
                        return
                # 🔴🔴 APP-021①：**在锁内**记下「本句最后样本的写入位置」。
                #   ⚠️ 必须在 `_synth_lock` **内**取 ⇒ 否则下一句的 `synth()`
                #      可能已经往缓冲里写了别的样本 ⇒ target 被放大
                #      ⇒ `played` 会**晚**发（不算错，但语义不准）。
                target_written = (self.player.ring.n_written
                                  if self.player is not None else 0)
                # 🔴🔴 APP-027②：本句**最后一块**写入后的缓冲位置
                #   （用于把欠载事件切到「句内」）
                last_chunk_end = target_written
        except Exception as e:
            import traceback
            log('[tts_worker] 合成失败：' + traceback.format_exc())
            emit({'kind': 'error', 'message': f'合成失败：{e}', 'id': jid})
            self._record_jsonl(jid, text, t_submit, error=str(e)[:200])
            return

        # ── 收尾 ──────────────────────────────────────────────────
        # 🔴🔴 2026-10-25 §30 的取消语义在流式下依然成立：
        #   `cancel` 由**主线程**的 `for line in sys.stdin` 收到，
        #   `synth()` 跑在**独立线程** ⇒ 二者并发 ⇒ 取消可能在**任意块之间**
        #   到达 ⇒ 每块写入前都要查一次（上面循环里已经查了）。
        #   ⚠️ 权威判据在**主进程**（`tts_service.py` 的 `_dropped_ids`）
        #      ⇒ 收到迟到的 `played` 时改记为「已播」⇒ 不双记。
        if aborted or self._is_cancelled(jid) or self._stop.is_set():
            log(f'[tts_worker] 句子 id={jid} 合成中途被丢弃，不播放')
            self._record_jsonl(jid, text, t_submit, dropped=True,
                               t_first=t_first)
            return

        if n_parts == 0:
            # 一块都没拿到（空句 / 引擎没吐块）
            # 🔴🔴 APP-021①：**没有音频 ⇒ 不能算「已播」**。
            #   旧行为：这里发 `played` ⇒ 主进程 `n_played += 1`
            #   ⇒ 界面显示「已播 1」，但**声卡上一声都没有**。
            #   ⇒ 现在：发**句子级 error**（带 id）⇒ 计入「失败」，
            #   界面能显示「失败 1 句：引擎没有产出音频」。
            emit({'kind': 'error', 'id': jid,
                  'message': '引擎没有产出任何音频（本句无内容可播）'})
            self._record_jsonl(jid, text, t_submit,
                               error='引擎没有产出任何音频')
            return

        # ── APP-021①：无播放器 ⇒ **显式失败**，绝不发 played ──────────
        #   旧行为：`player is None` 时循环里 `elif self.player is not None`
        #   整段跳过 ⇒ **音频被直接扔掉**，却照样发 `played`
        #   ⇒ 主进程记「已播」⇒ 用户界面显示正常 ⇒ **实际一声没出**。
        #   ⇒ 现在：发**句子级 error**（带 id + 诊断）。
        if not self.out_wav and self.player is None:
            msg = '播放器不可用，音频未输出（没有可用的输出设备）'
            log(f'[tts_worker] 🔴 句子 id={jid}：{msg}')
            emit({'kind': 'error', 'id': jid, 'message': msg,
                  'telemetry': self._telemetry_snapshot(0, 0, 0.0, 0.0, 0,
                                                        base_cb, base_read,
                                                        base_underflow)})
            self._record_jsonl(jid, text, t_submit, error=msg)
            return

        if self.out_wav and wav_parts:
            # ── 落盘模式：整句一次性入时间轴（见循环内的说明）──
            now = time.perf_counter()
            if self._t0 is None:
                self._t0 = now
            wav = np.concatenate(wav_parts) if len(wav_parts) > 1 else wav_parts[0]
            self._timeline.append((now - self._t0, wav.copy()))

        # 🔴 APP-021⑥：逐句 wav 落盘（`--dump-dir`）——
        #   ⚠️ 与 `--out-wav`（时间轴混音）**独立**：两者可同时开。
        if self.dump_dir and wav_parts:
            wav = np.concatenate(wav_parts) if len(wav_parts) > 1 else wav_parts[0]
            self._dump_segment_wav(jid, wav)

        # 🔴🔴 APP-021②：本句的**一行遥测**（写进 worker 日志 + 事件带回主进程）。
        rms = 0.0
        if n_samples > 0 and sum_sq > 0:
            rms = (sum_sq / float(n_samples)) ** 0.5
        elif n_samples > 0:
            rms = 0.0
        rms_dbfs = -99.0
        if rms > 0:
            rms_dbfs = 20.0 * math.log10(rms)
        # 🔴🔴 APP-027②：`dur` 必须在遥测**之前**算好
        #   （`synth_rtf` 的分母就是它）。
        dur = n_samples / float(self.sr if self.sr else SR)
        tel = self._telemetry_snapshot(n_samples, n_parts, peak, rms_dbfs,
                                       n_nan + n_inf, base_cb, base_read,
                                       base_underflow)
        tel['rms'] = round(rms, 6)
        tel['n_inf'] = n_inf
        silent = (peak < 1e-3) or (n_nan + n_inf) > 0
        if silent:
            tel['silent_synth'] = True
        # 🔴🔴🔴 APP-027②：**遥测拆开**（每句报这几个字段）
        #   `t_dequeue` / `t_first_chunk` / `t_last_chunk` —— 三个时刻
        #   `synth_rtf`   = (t_last_chunk − t_dequeue) / 音频时长
        #   `prebuffer_s` = 本句用的预缓冲量（秒）
        #   `underflow_in_sentence` = **首块播出之后**的欠载次数与静音时长
        #   `underflow_pre_sentence` = 首块**之前**的空等（**单列，不算卡顿**）
        # ⚠️ 旧的 `underflow_delta` **保留**（兼容旧消费方）
        self._fill_app027_telemetry(tel, t_dequeue, t_first, t_last,
                                    dur, prebuffer_s, prebuffer_short,
                                    first_chunk_start, last_chunk_end)
        # 🔴🔴🔴 APP-030⑤：**逐句语言/失控遥测**（reviewer 明文要的 5 项）
        #   `lang`            实际下传值（'ja'/'zh'/'en'/'ko'）
        #   `lang_src`        'explicit'（主进程下传）/ 'guess'（兜底）
        #   `n_chars`         字数（非空白字符数）
        #   `est_frames`      估计帧数（12 fps）
        #   `frames`          实际帧数（引擎回报；CUDA 边车有，babelvox 无）
        #   `end_reason`      结束原因（eos|cap|runaway|cancel|error）
        tel['lang'] = self._last_lang
        tel['lang_src'] = self._last_lang_src
        tel['n_chars'] = len([c for c in (text or '') if not c.isspace()])
        tel['est_frames'] = self._last_est_frames
        try:
            tel['frames'] = getattr(self.engine, '_last_frames', None)
        except Exception:
            tel['frames'] = None
        # 🔴 APP-030②：**默认结束原因 = eos**（引擎正常收尾）
        #   ⇒ `cap`（撞上限）/ `runaway`（中止）由引擎或守卫覆盖。
        tel['end_reason'] = self._last_end_reason or 'eos'
        tel['max_new_tokens'] = self._last_max_new_tokens
        # 🔴🔴🔴 APP-027 V3：**逐句的「音色来源」**（可观测性的第四项）
        #   ⚠️ 取的是 `self._last_clone_*`（**合成那一刻**的快照）
        #   ⇒ 前几句天然是 `False`（还没攒够语音）⇒ 这正是事实。
        tel['clone_active'] = bool(self._last_clone_active)
        tel['clone_mode'] = self._last_clone_mode
        tel['clone_audio_s'] = round(float(self._last_clone_audio_s or 0.0), 2)
        if runaway:
            tel['runaway'] = True
        # ⚠️ 这一行是「**写完缓冲那一刻**」的快照 ⇒ `read_delta` 只到此刻
        #   ⇒ 它回答的是「**合成侧**产出了什么」（峰值/RMS/NaN/样本数），
        #   **不是**「播出去多少」⇒ 播完后的那一行才是权威的播放口径。
        log('[tts_worker] 合成遥测 id=%d %s'
            % (jid, _fmt_telemetry(tel)))

        # 🔴 APP-021③：告知主进程「本句音频已**全部写进**环形缓冲」
        #   （**还没播完**）⇒ 主进程用它算**真实积压**
        #   （音频在缓冲里 ⇒ 剩下的待播时间只有几秒，不是整句时长）
        #   ⚠️ 没有这个事件的话，`played` 推迟到「播完」后，
        #      主进程的 `pending` 会多挂一句的时长 ⇒ 积压被高估
        #      ⇒ 在连续会议里会**多丢句**。
        if not self.out_wav and self.player is not None:
            emit({'kind': 'written', 'id': jid, 'dur_s': round(dur, 3)})

        # 🔴🔴🔴 APP-030⑤：**异常句落盘**（cap / runaway / 超时）
        #   判据（APP-030⑤ 明文）：「异常句（cap/runaway/超时）自动把
        #   wav 和文本落到 tts_anomaly\」
        #   ⚠️ **正常句不落盘**（零副作用）⇒ 只在异常时才有文件。
        #   ⚠️ 落盘失败**绝不影响**语音链路（整段包在 try 里）。
        try:
            _reason = tel.get('end_reason')
            _is_abnormal = (runaway
                            or _reason in ('cap', 'runaway', 'cancel')
                            or silent)
            if _is_abnormal:
                self._anomaly_wav_parts = list(_anom_buf)
                self._dump_anomaly(jid, text, str(_reason), tel)
        except Exception:
            pass

        # 🔴🔴 APP-021①：**等音频真的被播放回调取走**再发 `played`。
        #   旧行为：写进环形缓冲就发 ⇒ `played` ≠ 出声（缓冲还有 3 s 没播）。
        #
        # 🔴🔴🔴 APP-028②：**这里不再等**！
        #   APP-028② 明文：「语音播放的时候，**直接连续推理** TTS 音频流，
        #   **不要等待播放完成**，还没有播放的部分存内存缓存」
        #   ⇒ 合成线程**必须**在写完音频后**立刻返回**（继续下一句）；
        #   否则合成被播放速度卡住 ⇒ 谈不上「连续推理」。
        #   ⇒ 「等播完 + 发 `played`」挪到**独立的看门狗线程**（`_played_loop`）。
        #   🔴 **保序**：看门狗只从 `queue.Queue` 取 ⇒ `played` 的顺序
        #      == 合成的顺序（APP-027④ 的顺序保证**不能破**）。
        wait_play = (not self.out_wav) and (self.player is not None)
        if wait_play:
            # 🔴🔴 **超时口径必须跟着滞后走**：
            #   队列无界 ⇒ 一句可能在队列里排很久（滞后累积）
            #   ⇒ 固定 30 s 会把「只是还没轮到它播」误判成「音频没播完」
            #   ⇒ 用户看到「失败 N 句」，而实际声音正常。
            #   ⇒ 超时 = 「按当前队列剩余时长」+ 30 s 余量。
            try:
                _sr = float(self.sr or SR)
                _ring = self.player.ring
                pending_s = max(0.0, (target_written - _ring.n_read) / _sr)
            except Exception:
                pending_s = 0.0
            self._played_q.put(dict(
                jid=jid, text=text, t_submit=t_submit, dur=dur,
                t_first=t_first, t_dequeue=t_dequeue, t_last=t_last,
                latency=latency, silent=silent, target=target_written,
                timeout_s=pending_s + 30.0,
                n_samples=n_samples, n_parts=n_parts, peak=peak,
                rms=rms, rms_dbfs=rms_dbfs, nan_inf=n_nan + n_inf,
                base_cb=base_cb, base_read=base_read,
                base_underflow=base_underflow,
                prebuffer_s=prebuffer_s, prebuffer_short=prebuffer_short,
                first_chunk_start=first_chunk_start,
                last_chunk_end=last_chunk_end,
                # 🔴🔴🔴 APP-027 V3（§84）：**本句的「元信息」随 job 传递**
                #   ⚠️ **为什么必须传**：真实播放路径下 jsonl 行是**看门狗线程**
                #     （`_finish_played`）用**重算出来的 tel** 写的
                #     ⇒ 而 APP-030⑤ 的 `lang`/`lang_src`/`n_chars`/`est_frames`/
                #       `frames`/`end_reason`/`max_new_tokens`
                #       与 APP-027 V3 的 `clone_active`/`clone_mode`/`clone_audio_s`
                #       **只在合成线程的 tel 里**填过
                #     ⇒ **播放路径整组字段全丢**（实测：76 行 jsonl 里
                #       `lang`/`end_reason`/`clone_*` **一个都没有**）
                #     ⇒ reviewer 无法按语言/音色来源分组 ⇒ **结论不可核**。
                #   ⇒ 这里把**合成那一刻**的这些字段**快照**带进 job
                #     ⇒ 看门狗重算完 tel 后再覆盖回去 ⇒ **逐句字段齐全**。
                #   🔴 **必须在合成时快照**（不是看门狗执行时读 `self._last_*`）
                #     ⇒ 否则并发合成下一句会把上一句的值冲掉。
                meta={k: tel.get(k) for k in _APP030_JSONL_KEYS}))

        # 🔴🔴 APP-027②：把本句实测 RTF / 秒每字记进 EWMA
        #   ⇒ 下一句的预缓冲与积压估算都用**本会话实测**校准。
        if t_last is not None and t_dequeue is not None and dur > 0:
            self._update_rtf((t_last - t_dequeue) / dur)
        self._update_sec_per_char(text, dur)
        # 🔴🔴 APP-027④：清掉「正在合成」的状态（给主进程算积压用）
        with self._synth_state_lock:
            if self._synth_jid == jid:
                self._synth_jid = None
                self._synth_rem_s = 0.0

        if not wait_play:
            # 🔴 落盘模式 / 无播放器 ⇒ 不等播放，直接定案（保持旧语义）
            self._record_jsonl(jid, text, t_submit, dur_s=dur, t_first=t_first,
                               tel=tel)
            emit({'kind': 'played', 'id': jid,
                  'dur_s': round(dur, 3),
                  'latency_s': round(latency, 3),
                  'telemetry': tel})

    # -- 🔴🔴🔴 APP-028②：**播放看门狗线程**（等播完 ⇒ 发 played）────
    def _played_loop(self):
        """🔴🔴🔴 APP-028②：独立的「等播完」看门狗线程。

        职责：等「本句音频真的被声卡取走」⇒ 再发 `played` + 落 jsonl。

        🔴 **为什么不能放在合成线程里**（APP-028② 明文）：
          「语音播放的时候，直接连续推理 TTS 音频流，不要等待播放完成」
          ⇒ 合成线程一旦等播放，就被**播放速度**卡住
          ⇒ 合成只能以播放速率进行 ⇒ 完全没有「提高系统利用率」。

        🔴 **FIFO 保序**：本线程只从 `queue.Queue` 取
          ⇒ `played` 的顺序 == 合成的顺序（APP-027④ 的顺序保证不能破）。
        """
        while True:
            try:
                job = self._played_q.get(timeout=0.2)
            except queue.Empty:
                if self._stop.is_set():
                    return
                continue
            if job is None:
                return
            try:
                self._finish_played(job)
            except Exception:
                import traceback
                log('[tts_worker] 🔴 播放看门狗异常：'
                    + traceback.format_exc())

    def _finish_played(self, job: dict):
        """等本句播完 ⇒ 发 `played`（APP-021① 的出声语义，APP-028② 挪到看门狗）。"""
        jid = job['jid']
        text = job['text']
        t_submit = job['t_submit']
        dur = job['dur']
        t_first = job['t_first']
        ok, diag = self.player.wait_consumed(
            job['target'], timeout_s=job['timeout_s'],
            should_stop=lambda: (self._is_cancelled(jid)
                                 or self._stop.is_set()))
        if not ok:
            msg = ('音频未被播放完（%s）' % diag)
            log(f'[tts_worker] 🔴 句子 id={jid}：{msg}')
            emit({'kind': 'error', 'id': jid, 'message': msg})
            self._record_jsonl(jid, text, t_submit, dur_s=dur, t_first=t_first,
                               error=msg)
            return
        # 🔴🔴 **必须在这里重算遥测**（APP-021①）：
        #   合成线程那边的快照是「写完队列那一刻」⇒ `read_delta` 只统计到
        #   「此刻已被取走」的部分 ⇒ 判据「n_read 增量 ≥ 本句样本数」
        #   会被误判成失败。
        #   ⇒ 等播完之后重算 ⇒ `read_delta` 才是「本句期间真正被取走的量」。
        tel = self._telemetry_snapshot(
            job['n_samples'], job['n_parts'], job['peak'], job['rms_dbfs'],
            job['nan_inf'], job['base_cb'], job['base_read'],
            job['base_underflow'])
        tel['rms'] = round(job['rms'], 6)
        tel['n_inf'] = job['nan_inf']
        tel['consumed'] = ok
        if job['silent']:
            tel['silent_synth'] = True
        # 🔴🔴 APP-027②：**播完之后重算**欠载切分
        #   （此刻 `last_chunk_end` 才是终值 ⇒ 「句内」的切分才准）
        self._fill_app027_telemetry(
            tel, job['t_dequeue'], job['t_first'], job['t_last'],
            job['dur'], job['prebuffer_s'], job['prebuffer_short'],
            job['first_chunk_start'], job['last_chunk_end'])
        # 🔴🔴🔴 APP-027 V3（§84）：**把合成那一刻的元信息覆盖回 tel**
        #   ⇒ 播放路径的 jsonl 行才有 `lang` / `end_reason` / `clone_*`。
        #   ⚠️ **只覆盖「合成线程算出来的」那些**（APP-030⑤ + clone）
        #     ⇒ 播放侧的遥测（`consumed`/`read_delta`/`cb_delta`/欠载）
        #     **保持看门狗重算的值**（那才是播完后的权威口径）。
        _meta = job.get('meta') or {}
        for k, v in _meta.items():
            if v is not None:
                tel[k] = v
        log('[tts_worker] 遥测 id=%d %s' % (jid, _fmt_telemetry(tel)))
        self._record_jsonl(jid, text, t_submit, dur_s=dur, t_first=t_first,
                           tel=tel)
        emit({'kind': 'played', 'id': jid,
              'dur_s': round(job['dur'], 3),
              'latency_s': round(job['latency'], 3),
              'telemetry': tel})

    # -- 🔴🔴🔴 APP-027②：遥测拆字段 ---------------------------------
    @staticmethod
    def _app027_partial_tel(t_dequeue, t_first, t_last, prebuffer_s,
                            prebuffer_short):
        """🔴 APP-027②：**失败/丢句路径**的**部分遥测**。

        🔴 **为什么需要**：合成途中的失败（缓冲写满 / 播放写入失败 /
          引擎异常）发生在**完整遥测算出来之前** ⇒ 那几条 jsonl 行
          若不带任何 APP-027 字段 ⇒ **V1/V2 验收会漏掉它们**
          ⇒ 「RTF > 1 导致的丢句只记录不判失败但必须如实写」
          这条要求就**无法从数据上核对**。

        ⚠️ 这里只给**已经知道**的字段（时刻、预缓冲量）⇒ 欠载等
          需要播放器状态的字段留空（**不编造**）。
        """
        tel = {}
        if t_dequeue is not None:
            tel['t_dequeue'] = round(float(t_dequeue), 4)
        if t_first is not None:
            tel['t_first_chunk'] = round(float(t_first), 4)
        if t_last is not None:
            tel['t_last_chunk'] = round(float(t_last), 4)
        if prebuffer_s is not None:
            tel['prebuffer_s'] = round(float(prebuffer_s), 3)
        if prebuffer_short:
            tel['prebuffer_short'] = True
        return tel

    def _fill_app027_telemetry(self, tel: dict, t_dequeue, t_first, t_last,
                               dur: float, prebuffer_s: float,
                               prebuffer_short: bool,
                               first_chunk_start, last_chunk_end):
        """把 APP-027② 要求的字段填进 `tel`（**就地修改**）。

        字段（APP-027 明文）：
        - `t_dequeue`      : 从 FIFO 队列取出这句的时刻
        - `t_first_chunk`  : 第一块合成出来的时刻
        - `t_last_chunk`   : 最后一块合成出来的时刻
        - `synth_rtf`      : (t_last_chunk − t_dequeue) / 音频时长
        - `prebuffer_s`    : 本句用的预缓冲量（秒）
        - `underflow_in_sentence`    : **首块播出之后**的欠载次数
        - `underflow_in_sentence_ms` : **首块播出之后**的静音总时长（毫秒）
        - `underflow_pre_sentence`   : 首块**之前**的空等次数（**单列**）

        🔴 **为什么必须拆开**（APP-027 问题② 的根因）：
          旧的 `underflow_delta` 从**拿到锁**就开始数 ⇒ 把「首块前的空等」
          也算成卡顿 ⇒ 分不清「句前等一次」（正常）与「句内断断续续」（真卡顿）
          ⇒ 卡顿归因一直错 ⇒ 预缓冲的收益无法度量。
        """
        tel['t_dequeue'] = round(t_dequeue, 4) if t_dequeue is not None else None
        tel['t_first_chunk'] = round(t_first, 4) if t_first is not None else None
        tel['t_last_chunk'] = round(t_last, 4) if t_last is not None else None
        tel['prebuffer_s'] = round(float(prebuffer_s), 3)
        tel['prebuffer_short'] = bool(prebuffer_short)
        if t_last is not None and t_dequeue is not None and dur > 0:
            tel['synth_rtf'] = round((t_last - t_dequeue) / dur, 4)
        else:
            tel['synth_rtf'] = None
        tel['rtf_ewma'] = (round(self._rtf_ewma, 4)
                           if self._rtf_ewma is not None else None)
        # 欠载切分
        try:
            p = self.player
            if p is None:
                pre_n = pre_ms = in_n = in_ms = 0
            else:
                pre_n, pre_ms, in_n, in_ms = p.underflow_split(
                    first_chunk_start, last_chunk_end)
        except Exception:
            pre_n = pre_ms = in_n = in_ms = 0
        tel['underflow_in_sentence'] = int(in_n)
        tel['underflow_in_sentence_ms'] = int(round(
            in_ms * 1000.0 / float(self.sr or SR)))
        tel['underflow_pre_sentence'] = int(pre_n)
        tel['underflow_pre_sentence_ms'] = int(round(
            pre_ms * 1000.0 / float(self.sr or SR)))
        return tel

    # -- 逐句记录（C-101 P4 第 6 条：`x.tts.jsonl`）----------------------
    def _telemetry_snapshot(self, n_samples, n_parts, peak, rms_dbfs,
                            n_nan_inf, base_cb, base_read, base_underflow):
        """汇总「本句」的播放遥测（APP-021②）。

        ⚠️ 增量口径：`cb_delta` = 本句期间音频回调次数增量，
        `read_delta` = 本句期间被播放回调**取走的样本数**增量
        （⇒ 这个数 ≥ 本句样本数 ⇒ 音频**真的**交给了声卡），
        `underflow_delta` = 本句期间缓冲欠载次数增量。
        """
        tel = dict(n_samples=int(n_samples), n_parts=int(n_parts),
                   peak=round(float(peak), 6),
                   rms_dbfs=round(float(rms_dbfs), 2),
                   n_nan_inf=int(n_nan_inf),
                   cb_delta=0, read_delta=0, underflow_delta=0,
                   ring_level=0, ring_cap=0, out_desc='（未初始化）',
                   sr=self.sr)
        p = self.player
        if p is None:
            return tel
        try:
            tel['cb_delta'] = max(0, p.n_cb - base_cb)
            tel['read_delta'] = max(0, p.ring.n_read - base_read)
            tel['underflow_delta'] = max(0, p.n_underflow - base_underflow)
            tel['ring_level'] = p.ring.level()
            tel['ring_cap'] = p.ring._cap
            tel['out_desc'] = p.out_desc
            tel['n_cb_total'] = p.n_cb
            tel['n_read_total'] = p.ring.n_read
        except Exception:
            pass
        return tel

    def _dump_segment_wav(self, jid: int, wav):
        """🔴 APP-021⑥：逐句落盘 wav（供 reviewer 算 RMS / 回转写）。

        目录：`--dump-dir` 指定；未指定 ⇒ **不落盘**（默认零副作用）。
        文件名：`seg_<jid>_<序号>.wav`。
        """
        if not self.dump_dir:
            return None
        try:
            import soundfile as sf
            os.makedirs(self.dump_dir, exist_ok=True)
            self._dump_seq += 1
            path = os.path.join(self.dump_dir,
                                'seg_%d_%04d.wav' % (jid, self._dump_seq))
            sf.write(path, wav, self.sr)
            self._dump_paths.append(path)
            log(f'[tts_worker] 已落盘分段 wav：{path}')
            return path
        except Exception as e:
            log(f'[tts_worker] 分段 wav 落盘失败：{e}')
            return None

    # -- 🔴🔴🔴 APP-030⑤：**异常句落盘** ---------------------------------
    def _anomaly_dir_path(self) -> str:
        """异常句目录：`%LOCALAPPDATA%\\Confucius4LiveCaption\\tts_anomaly`。

        🔴 APP-030⑤ 明文：「异常句（cap/runaway/超时）自动把 wav 和文本
          落到 `%LOCALAPPDATA%\\Confucius4LiveCaption\\tts_anomaly\\`
          （**最多保留 20 个**，只留本机，**不进包**）」。
        ⚠️ **只在本机** ⇒ 绝不写进客户包目录。
        """
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        return os.path.join(base, 'Confucius4LiveCaption', 'tts_anomaly')

    def _dump_anomaly(self, jid: int, text: str, reason: str,
                      tel: Optional[dict] = None):
        """把**异常句**（cap / runaway / 超时）的 wav + 文本落盘。

        🔴 APP-030⑤：reviewer 要「拿到出事的句子的音频和文本」才能复核
          （reviewer 原话：「会话日志不记目标语言、不记译文、不落 wav
          ⇒ 拿不到出事句音频」）。
        ⚠️ **隐私**：
          - 目录在 `%LOCALAPPDATA%` ⇒ **只留本机，不进客户包**；
          - **最多保留 20 个**（FIFO 淘汰最旧的）；
          - wav 用**合成侧**的音频（本句已收到的部分）⇒ 失控句就是那段
            低电平长拖（reviewer 实测 `rms_dbfs=-37.9`）。
        """
        try:
            d = self._anomaly_dir_path()
            os.makedirs(d, exist_ok=True)
            self._anomaly_count += 1
            stamp = time.strftime('%Y%m%d_%H%M%S')
            base = os.path.join(d, 'anom_%s_id%d_%s' % (stamp, int(jid),
                                                        reason))
            # ① 文本
            try:
                with open(base + '.txt', 'w', encoding='utf-8') as f:
                    f.write(text or '')
            except Exception:
                pass
            # ② 元数据（**机器可读** ⇒ reviewer 可直接聚合）
            try:
                meta = dict(id=int(jid), reason=reason, text=text or '',
                            ts=time.strftime('%Y-%m-%d %H:%M:%S'))
                if tel:
                    for k in ('lang', 'lang_src', 'n_chars', 'est_frames',
                              'frames', 'end_reason', 'max_new_tokens',
                              'dur_s', 'n_samples', 'n_parts', 'peak',
                              'rms_dbfs', 'synth_rtf'):
                        if k in tel:
                            meta[k] = tel[k]
                with open(base + '.json', 'w', encoding='utf-8') as f:
                    f.write(json.dumps(meta, ensure_ascii=False, indent=2))
            except Exception:
                pass
            # ③ wav（本句已收到的音频）
            try:
                if self.out_wav or self.dump_dir:
                    parts = getattr(self, '_anomaly_wav_parts', None)
                    if parts:
                        import numpy as np
                        wav = (np.concatenate(parts) if len(parts) > 1
                               else parts[0])
                        try:
                            import soundfile as sf
                            sf.write(base + '.wav', wav, self.sr or SR)
                        except Exception:
                            pass
            except Exception:
                pass
            # ④ **FIFO 淘汰**：最多保留 20 个
            try:
                files = sorted(
                    [f for f in os.listdir(d) if f.startswith('anom_')])
                # 每个异常句是 3 个文件（txt/json/wav）⇒ 按「组」淘汰
                groups = {}
                for f in files:
                    key = f.rsplit('.', 1)[0]
                    groups.setdefault(key, []).append(f)
                keys = sorted(groups)
                over = len(keys) - self.ANOMALY_KEEP
                for k in keys[:max(0, over)]:
                    for f in groups[k]:
                        try:
                            os.remove(os.path.join(d, f))
                        except Exception:
                            pass
            except Exception:
                pass
            log('[tts_worker] 异常句已落盘：%s（reason=%s）' % (base, reason))
            return base
        except Exception as e:
            log('[tts_worker] 异常句落盘失败：%s' % e)
            return None

    def _record_jsonl(self, jid, text, t_submit, dur_s=None, t_first=None,
                      dropped=False, error=None, tel=None):
        """记录一句的时间线（供 `x.tts.jsonl` 落盘）。

        每条字段：译文、入队时间、首包时间、播完时间、是否被丢弃。

        🔴🔴🔴 APP-027②：**把 APP-027 的遥测字段一并写进 jsonl**
          ⇒ 否则 V1/V2 验收只能去翻会话日志（散文），
          ⇒ 而验收要的是**逐句的机器可算指标**：
          `synth_rtf` / `prebuffer_s` / `underflow_in_sentence` /
          `underflow_in_sentence_ms` / `underflow_pre_sentence` /
          `t_dequeue` / `t_first_chunk` / `t_last_chunk`。
        ⚠️ `tel` 是**可选**的 ⇒ 失败/丢句的行照样写（字段为空）。
        """
        row = dict(id=jid, text=text,
                   t_submit=round(t_submit, 4),
                   t_first_packet=(round(t_first - t_submit, 4)
                                   if t_first is not None else None),
                   t_done=round(time.perf_counter(), 4),
                   dur_s=round(dur_s, 3) if dur_s is not None else None,
                   dropped=bool(dropped),
                   error=error)
        # 🔴 APP-027②：逐句遥测（**只挑 APP-027 关心的字段** ⇒ 行不膨胀）
        if tel:
            for k in _APP027_JSONL_KEYS:
                if k in tel:
                    row[k] = tel[k]
            # 🔴🔴🔴 APP-030⑤：**逐句语言 / 失控遥测**
            for k in _APP030_JSONL_KEYS:
                if k in tel:
                    row[k] = tel[k]
        else:
            # 🔴 APP-030⑤：即使 `tel` 为空（失败/丢句的行），
            #   **语言信息也必须留下** ⇒ 失败句也能查「是什么语言的句子失败」。
            row['lang'] = self._last_lang
            row['lang_src'] = self._last_lang_src
            # 🔴🔴🔴 APP-027 V3：**失败/丢句的行也要带音色来源**
            #   ⇒ 否则 reviewer 统计「克隆组句子数」时会漏掉这些行
            #   ⇒ 分母变小 ⇒ **对比失真**。
            row['clone_active'] = bool(self._last_clone_active)
            row['clone_mode'] = self._last_clone_mode
            row['clone_audio_s'] = round(
                float(self._last_clone_audio_s or 0.0), 2)
            row['end_reason'] = self._last_end_reason or 'error'
        # 🔴🔴🔴 APP-028②：队列水位 / 峰值（**验收要「队列峰值（秒和 MB）」**）
        #   ⚠️ 不依赖 `tel` ⇒ 失败/丢句的行也能带上水位（诊断用）。
        try:
            p = self.player
            if p is not None and p.ring is not None:
                _sr = float(self.sr or SR)
                row['queue_lag_s'] = round(p.ring.lag_s(_sr), 3)
                row['queue_peak_s'] = round(
                    float(getattr(p.ring, 'peak_lag_s', 0.0)), 3)
                row['queue_peak_mb'] = round(
                    float(getattr(p.ring, 'peak_bytes', 0)) / (1024.0 * 1024.0),
                    3)
        except Exception:
            pass
        self._jsonl_rows.append(row)
        # 实时追加到文件（崩溃也能留下已完成的行）
        if self._jsonl_path:
            try:
                with open(self._jsonl_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(row, ensure_ascii=False) + '\n')
            except Exception:
                pass

    def _flush_timeline(self):
        """落盘模式收尾：把时间轴上的句子混成一个 wav。"""
        if not self.out_wav or not self._timeline:
            return
        import numpy as np
        sr = self.sr                     # 🔴 采样率随引擎走（BabelVox=24000）
        items = list(self._timeline)
        end = max(t + len(w) / sr for t, w in items)
        total = int(end * sr)
        out = np.zeros(total, dtype=np.float32)
        for t, w in items:
            i = int(t * sr)
            j = min(i + len(w), total)
            out[i:j] += w[:j - i]
        try:
            import soundfile as sf
            sf.write(self.out_wav, out, sr)
            log(f'[tts_worker] 已落盘 {self.out_wav}'
                f'（{len(out)/sr:.2f}s，{len(items)} 句，{sr} Hz）')
        except Exception as e:
            log(f'[tts_worker] 落盘失败：{e}')

    def _synth_babelvox(self, text: str, lang: str):
        """BabelVox（Qwen3-TTS）**流式**合成。**生成器**：逐块 yield np.ndarray（24000 Hz）。

        🔴🔴 **音色路线：spkonly** —— 只传 `speaker_embed`，
        **不传 `ref_text` / `ref_audio`**（交接单 §5.1 / TTS-005）。

        ⚠️ **长句要按句切分**（交接单 §6.2）：帧数上限 =
        `max_talker_seq − prefill_len`，逐条不同 ⇒ 超限会被**静默砍断**。
        ⇒ 这里对超长句先切分，逐段合成后拼起来。

        🔴🔴 **2026-10-26 改为生成器（APP-018 第 1 条）**：
          旧实现是「**先收完所有块，再 return 整个 list**」⇒ 调用方
          (`synth()`) 只能在**整句合成完成之后**才发 `first_packet`、才写播放缓冲
          ⇒ **App 报出来的「首包」其实是整句合成耗时**（实测 8.36 s），
          而**真实流式首包只要 1.16 s** ⇒ **流式能力被完全浪费**（差 7.2×），
          听感上也要等整句合成完才出声。
          ⇒ 现在**逐块 yield**：调用方拿到第一块就能发声 ⇒ 首包回到真实值。
          ⚠️ 兼容性：旧调用方仍可用 `list(_synth_babelvox(...))` 收全量。
        """
        import numpy as np
        import tts_engine

        # 🔴🔴🔴 APP-030①：**显式语言 → 引擎全称**（不再二分 zh/en）
        #   旧实现：`blang = 'Chinese' if zh else 'English'`
        #   ⇒ **Japanese / Korean 永远拿不到**（reviewer 实测 8 条日文样句
        #     5 条判 en / 3 条判 zh ⇒ 8/8 全错）
        #   ⇒ 现在走 `tts_engine.map_language()`（唯一映射表）。
        #   ⚠️ 未知语言兜底 English（与历史行为一致），**不静默回落**的是
        #      「已知但不支持的语言」⇒ 那由 `language_supported()` 显式告警。
        blang = tts_engine.map_language(lang)
        if not tts_engine.language_supported(blang):
            # 🔴 APP-030① 明文：「不得静默回落 English」
            #   ⇒ 至少**大声告警**，让会话日志里能看见。
            log('[tts_worker] 🔴 目标语言 %r → %r 不在引擎支持列表 %s'
                '（会走 language-agnostic 模式）'
                % (lang, blang, list(tts_engine.SUPPORTED_LANGS)))

        # 🔴🔴 TTS-006：**中文数字正则化要在分句之前**
        #   （分句按字数估帧数 ⇒ 若先分句再正则化，估的是「数字」的字数，
        #    而实际读的是「五十二」的 3 个字 ⇒ 帧数上限会被低估）
        #   ⇒ 这里先正则化，再 split_long_text。
        #   ⚠️ `tts_engine.stream()` 里也有一层（幂等 ⇒ 不重复转换），
        #   那层负责覆盖**其它 stream 调用方**。
        # 🔴🔴🔴 APP-030① 明文：**只在 Chinese 时执行**
        #   ⇒ 旧实现 `if lang.startswith('zh')` 在 `lang='ja'` 时不触发，
        #     但旧实现**根本没有 ja** ⇒ 一旦判 zh（reviewer 实测 3/8 判 zh）
        #     就会把「2026年」读成「二零二六年」（中文读法）⇒ **错读**。
        #   ⇒ 日文数字规则交 TTS 模块定，App 侧**保持原样不转**。
        if blang == 'Chinese':
            text = tts_engine.normalize_zh_numbers(text)

        # 长句切分（保守上限 478 帧 ≈ 39.8 s）
        parts = tts_engine.split_long_text(text)
        for p in parts:
            if self._stop.is_set():
                break
            if self._is_cancelled(self._cur_jid):
                break
            # 🔴🔴🔴 APP-030②：**按句/按段传生成帧数上限**（第一道闸）
            #   公式：`clamp(3×估计帧数 + 36, 48, 2048)`
            #   ⚠️ **按切分段**算（不是整句）⇒ 段越短上限越紧 ⇒ 更早截断。
            #   ⚠️ `tts_engine.stream()` 内部**只收紧不放宽**引擎默认值。
            _mnt = tts_engine.clamp_max_new_tokens(p, lang)
            self._last_max_new_tokens = _mnt
            # 🔴🔴🔴 APP-030②：**第二道闸（客户端 RUNAWAY）**的输入
            #   `est_sec` = 本段的预计音频秒数（按语言估）
            _est = tts_engine.estimate_sec(p, lang)
            for wav_chunk, sr in tts_engine.stream(
                    self.engine, p, language=blang,
                    speaker_embed=self.speaker_embed,
                    speaker=self.speaker_name if self.speaker_embed is None else None,
                    cancel_event=self._stop,
                    max_new_tokens=_mnt,
                    est_sec=_est):
                w = np.asarray(wav_chunk, dtype=np.float32).reshape(-1)
                self.sr = int(sr)
                yield w
            # 🔴🔴🔴 APP-030⑤：**取引擎回报的结束原因**
            #   CUDA 边车回报 `eos`（正常）/ `cap`（撞上限被截断）/
            #   `runaway`（客户端中止）⇒ 供本句遥测与异常句落盘。
            try:
                _er = getattr(self.engine, '_last_end_reason', None)
                if _er:
                    self._last_end_reason = _er
            except Exception:
                pass

    def _synth_ov(self, text: str, lang: str, cond: dict):
        """OV 整句合成（**不依赖 torch**）。返回 list[np.ndarray]（22050 Hz）。

        ⚠️ 入口是 `OVSynth.synth()`（**实例方法**）。
        旧实现调用的 `synth_ov.synth_whole(rt, ...)` **不存在** ⇒ 必崩。
        """
        import numpy as np

        synth = self.ov_rt
        res = synth.synth(
            text, lang, cond,
            seed=self.seed, n_timesteps=self.steps, cfg_rate=self.cfg_rate,
        )
        wav = np.asarray(res['wav'], dtype=np.float32).reshape(-1)
        return [wav]

    def _synth_torch(self, text: str, lang: str, cond: dict):
        """torch 回落路径（流式）。"""
        import numpy as np

        gen = self.NS.make_generator(seed=1234, device='cuda')
        chunks = []
        for c in self.NS.synth_stream(
                self.model, text, lang, cond,
                first_chunk_size=25, chunk_size=50, overlap_tokens=10,
                n_timesteps=25, inference_cfg_rate=0.7, gen=gen):
            chunks.append(c)
            if self._stop.is_set():
                break
        return chunks

    @staticmethod
    def _guess_lang(text: str) -> str:
        """粗判语言（**兜底**，APP-030①：主进程应显式下传 `lang`）。

        🔴🔴🔴 APP-030①：**旧实现是个真缺陷**
          旧：`cjk = 汉字数`；`return 'zh' if cjk * 4 >= len(text) else 'en'`
          ⇒ 只分 zh/en ⇒ **Japanese / Korean 永远判不出来**
          ⇒ reviewer 本机实测 8 条日文样句：**5 条判 en、3 条判 zh**
            （`ありがとうございます。` / `はい、そうです。` / `これはテストです。`
              / `2026年の売上は52%増えました。`
              / `プロセッサーのパフォーマンスが向上しました。` / `今日は会議があります。` 等）
          ⇒ 判 en ⇒ 用 English 语言 token 读假名（**分布外** ⇒ EOS 不稳
            ⇒ 偶发撞 2048 帧上限 ⇒ 一句拖 106 s ⇒ 后续句全堵）
          ⇒ 判 zh ⇒ 用 Chinese token 读日文 + `normalize_zh_numbers` 误作用
        ⇒ 现在：复用 `tts_engine.guess_language_by_script()`
          - **假名**（U+3040–30FF）⇒ `ja`（最强信号）
          - **谚文**（U+AC00–D7AF）⇒ `ko`
          - 汉字占比 ≥ 25% ⇒ `zh`（**只数非空白字符**）
          - 否则 ⇒ `en`
        ⚠️ **这仍是兜底**：主进程显式下传时**根本不调用**本函数。
        """
        try:
            import tts_engine
            return tts_engine.guess_language_by_script(text)
        except Exception:
            # 🔴 兜底也不能退回「只看汉字」的旧逻辑（那是 APP-030 的真缺陷）
            cjk = sum(1 for ch in (text or '') if '\u4e00' <= ch <= '\u9fff')
            kana = sum(1 for ch in (text or '') if '\u3040' <= ch <= '\u30ff')
            hang = sum(1 for ch in (text or '') if '\uac00' <= ch <= '\ud7af')
            if kana:
                return 'ja'
            if hang:
                return 'ko'
            vis = len([c for c in (text or '') if not c.isspace()])
            return 'zh' if (vis and cjk * 4 >= vis) else 'en'

    def _is_cancelled(self, jid) -> bool:
        with self._cancel_lock:
            return jid in self._cancelled

    # -- 🔴🔴🔴 APP-027①/②/④：RTF / 预缓冲 / 时长校准 ---------------
    def _update_rtf(self, rtf: float):
        """把本句实测 RTF 记进 EWMA（用于下一句的预缓冲计算）。

        🔴 **`RTF_ewma` 用本会话最近 N 句的实测值**（APP-027 明文要求）
        ⇒ 不是常数、不是配置项 ⇒ **跑久了会自动适应**负载变化。
        """
        try:
            rtf = float(rtf)
        except Exception:
            return
        if not (0.01 <= rtf <= 20.0):
            return                        # 明显异常的样本不污染 EWMA
        self._rtf_win.append(rtf)
        self._rtf_ewma = sum(self._rtf_win) / float(len(self._rtf_win))

    def _update_sec_per_char(self, text: str, dur_s: float):
        """用本句实测更新「音频秒/字」的 EWMA（APP-027④）。

        🔴 **旧实现把「5 字/秒」写死** ⇒ 积压估算与实测偏差大
        ⇒ 积压被高估 ⇒ **多丢句**（用户实测「CUDA 连续播放越拖越久、
        最后全部被丢」）。
        ⇒ 现在用实测校准。
        """
        try:
            n = len([c for c in (text or '') if c.strip()])
            if n <= 0 or dur_s <= 0:
                return
            self._sec_per_char_win.append(float(dur_s) / n)
            self._sec_per_char = (sum(self._sec_per_char_win)
                                  / float(len(self._sec_per_char_win)))
        except Exception:
            pass

    def _estimate_dur_s(self, text: str) -> float:
        """估计一句的音频时长（秒）。

        🔴 **优先用本会话实测的「音频秒/字」**；没有实测值时
        用保守兜底（中文 0.12 s/字 ≈ 8.3 字/秒）。
        """
        try:
            n = len([c for c in (text or '') if c.strip()])
        except Exception:
            n = 0
        if n <= 0:
            return 0.0
        if self._sec_per_char:
            return float(n) * self._sec_per_char
        return float(n) * 0.12

    def _compute_prebuffer_s(self, text: str) -> float:
        """🔴🔴🔴 APP-027①：**逐句自适应预缓冲**（秒）。

        公式（APP-027 明文）：
            `prebuffer_s = max(0.3, est_dur × (1 − 1/RTF_ewma))`

        - `RTF_ewma ≤ 1`（追得上播放）⇒ 只保留 **0.3 s 底线**
          （不要无谓地让用户等）
        - `RTF_ewma > 1`（追不上）⇒ 预缓冲 = 句长 × (1 − 1/RTF)
          ⇒ 正好补上「合成比播放慢的那部分」
        - **还没有实测 RTF** ⇒ 用 0.3 s 底线（第一句不猜）

        🔴 **上限保护**：预缓冲不能无限大
        ⇒ 最多 `est_dur`（再多也没有意义，句内还是追不上）
        ⇒ 且不超过 3 s（超过 3 s 的等待用户会以为程序死了）。
        """
        try:
            est_dur = self._estimate_dur_s(text)
            if est_dur <= 0:
                return 0.3
            rtf = self._rtf_ewma
            if not rtf or rtf <= 1.0:
                return 0.3
            pre = est_dur * (1.0 - 1.0 / rtf)
            pre = max(0.3, min(pre, est_dur, 3.0))
            return float(pre)
        except Exception:
            return 0.3

    # -- 🔴🔴🔴 APP-027④：**唯一合成线程**（FIFO 消费）-------------------
    def _synth_loop(self):
        """🔴🔴🔴 APP-027④：**唯一的合成线程**，按 **FIFO** 消费队列。

        🔴 **为什么要改**（APP-027 问题③⑤，用户实测「CUDA 连续播放越拖越久、
        最后全部被丢」）：

        - 旧实现：主循环每收到一条 `synth` 就**新开一个线程**，
          线程们去抢 `threading.Lock`（`_synth_lock`）
          ⇒ **不保证先来先得**（谁先拿到锁谁先播）
          ⇒ **播出顺序 ≠ 提交顺序**
          ⇒ 主进程按「提交顺序」记账、用户按「播出顺序」听到
          ⇒ **字幕与声音错位**。
        - 现在：**一个**线程 + `queue.Queue` ⇒ **严格 FIFO**
          ⇒ 播出顺序 == 提交顺序 ⇒ 不再错位。

        ⚠️ **cancel 只把队列条目标记为丢弃**（不抢占正在合成的句子）：
          正在合成的那句由 `synth()` 内部的逐块检查处理。
        """
        while True:
            try:
                item = self._synth_q.get(timeout=0.5)
            except queue.Empty:
                if self._stop.is_set():
                    return
                continue
            if item is None:            # 关闭哨兵
                return
            jid, text, spk, spk_conf, lang = item
            # ── 出队时刻（APP-027② 的 `t_dequeue` 真正的口径）──
            t_dequeue = time.perf_counter()
            with self._synth_state_lock:
                self._dequeue_at[jid] = t_dequeue
                # 从排队队列里摘掉（**保持顺序**）
                try:
                    self._synth_queue_ids.remove(jid)
                except ValueError:
                    pass
                self._synth_queue_est.pop(jid, None)
                self._synth_text.pop(jid, None)
                # 登记「正在合成」
                self._synth_jid = jid
                self._synth_rem_s = self._estimate_dur_s(text)
            self._emit_synth_state()
            try:
                self.synth(jid, text, spk, spk_conf, lang)
            except Exception as e:
                import traceback
                log('[tts_worker] 🔴 合成线程异常：' + traceback.format_exc())
                emit({'kind': 'error', 'id': jid,
                      'message': f'合成线程异常：{e}'})
            finally:
                with self._synth_state_lock:
                    if self._synth_jid == jid:
                        self._synth_jid = None
                        self._synth_rem_s = 0.0
                self._emit_synth_state()
            self._synth_q.task_done()

    def _emit_synth_state(self):
        """🔴🔴🔴 APP-027④：把「合成队列状态」报给主进程。

        主进程据此算**积压**（APP-027④ 的三段式口径）：
            积压 = 环形缓冲里实际剩下的样本时长（只算一次，最多 3 s）
                 + **正在合成的句子剩余预计时长**
                 + **排队句子的预计时长**

        ⚠️ 为什么必须由 **worker** 报：
          「正在合成哪一句」「还剩多少」「后面排了几句」这些信息**只有
          worker 知道**（主进程的 `pending` 里只有原文，没有引擎进度）。
        """
        try:
            with self._synth_state_lock:
                jid = self._synth_jid
                rem = float(self._synth_rem_s or 0.0)
                qids = list(self._synth_queue_ids)
                qest = {k: float(v or 0.0)
                        for k, v in self._synth_queue_est.items()}
                spc = self._sec_per_char
            # 🔴🔴🔴 APP-028②：**无界队列里实际剩下的样本时长**（只算一次）。
            #   ⚠️ 旧口径是「每个已写入的句子按 min(3.0, dur) 各算一次」
            #      ⇒ 两句同时已写入就按最多 6 s 计 ⇒ **高估积压** ⇒ 多丢句
            #      （APP-027 问题③① 的根因之一）。
            #   ⇒ 现在：直接读**队列实际水位**。
            #   🔴🔴 APP-028②：队列**无界** ⇒ **不再截断到 3 s**
            #      （截断会让主进程低估滞后 ⇒ 用户看不到真实的「越拖越久」）。
            ring_s = 0.0
            lag_s = 0.0
            try:
                p = self.player
                if p is not None and p.ring is not None:
                    sr = float(self.sr or p.sr or SR)
                    ring_s = p.ring.level() / sr
                    # 🔴 APP-028②：**语音滞后秒数**（= 队列里还没播的音频时长）
                    lag_s = p.ring.lag_s(sr) if hasattr(p.ring, 'lag_s') else ring_s
            except Exception:
                ring_s = 0.0
                lag_s = 0.0
            emit({'kind': 'synth_state',
                  'synth_jid': jid,
                  'synth_rem_s': round(rem, 3),
                  'queue_ids': qids,
                  'queue_est_s': qest,
                  'ring_backlog_s': round(ring_s, 3),
                  # 🔴🔴 APP-028②：**语音滞后**（底栏显示「语音滞后 X 秒」）
                  'lag_s': round(lag_s, 3),
                  # 🔴 APP-027④：实测「音频秒/字」⇒ 主进程估时用同一口径
                  #   （**不写死 5 字/秒**）
                  'sec_per_char': (round(float(spc), 5)
                                   if spc else None)})
        except Exception:
            pass

    # -- 主循环 ----------------------------------------------------------
    def run(self):
        # 先起播放流，再加载模型（模型加载要几秒，播放流要先开好）
        try:
            self.player = Player(device=self.out_device, sr=self.sr)
        except Exception as e:
            log(f'[tts_worker] 播放流创建失败：{e}')
            self.player = None

        # 模型加载放到后台线程，主线程立刻开始收指令（避免主进程等太久）
        th = threading.Thread(target=self._safe_load, daemon=True)
        th.start()

        # 🔴🔴🔴 APP-027④：**唯一的合成线程**（FIFO 消费）
        #   ⇒ 顺序有保证（不再每句开线程抢锁）⇒ 字幕与声音不错位。
        self._synth_thread = threading.Thread(target=self._synth_loop,
                                              daemon=True)
        self._synth_thread.start()

        # 🔴🔴🔴 APP-028②：**播放看门狗线程**（等播完 ⇒ 发 `played`）
        #   ⇒ 合成线程**不等播放** ⇒ 可以连续推理。
        self._played_thread = threading.Thread(target=self._played_loop,
                                               daemon=True)
        self._played_thread.start()

        # 🔴🔴 APP-021§54.10：**按字节读 stdin**。
        #   起因：主进程为了正确解码 stderr（GBK/utf-8 混编码），
        #   把整条管道改成**二进制**模式（`Popen` 去掉 `text=True`）
        #   ⇒ worker 的 `sys.stdin` 也变成二进制流
        #   ⇒ 旧写法 `for line in sys.stdin` 拿到的是 **bytes**
        #   ⇒ `line.strip()` 能用，但 `json.loads(bytes)` 在部分版本上行为不稳，
        #      且**中文文本可能被按 locale 解码坏**。
        #   ⇒ 现在显式按 utf-8 解码（主进程写的就是 utf-8）。
        #   ⚠️ 用 `sys.stdin.buffer` 取二进制流；若拿不到就退回 `sys.stdin`。
        try:
            _stdin = sys.stdin.buffer
        except Exception:
            _stdin = sys.stdin
        for _raw in _stdin:
            if isinstance(_raw, (bytes, bytearray)):
                line = bytes(_raw).decode('utf-8', 'replace').strip()
            else:
                line = str(_raw).strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            cmd = msg.get('cmd')
            if cmd == 'quit':
                break
            elif cmd == 'synth':
                jid = msg.get('id')
                text = msg.get('text', '')
                # 🔴🔴 APP-022：`spk` / `spk_conf` **接口预留**
                #   （当前 ASR 侧还没交付 ⇒ 恒为 None ⇒ **行为不变**）。
                #   等 TTS-019 交付「按说话人取音色向量」时在这里接上。
                spk = msg.get('spk')
                spk_conf = msg.get('spk_conf')
                # 🔴🔴🔴 APP-030①：**目标语言显式下传**。
                #   旧实现命令体只有 `id/text` ⇒ worker 只能靠
                #   `_guess_lang()`（汉字占比二分 zh/en）**猜**
                #   ⇒ **TTS 永远收不到 Japanese**
                #   ⇒ reviewer 本机实测 8 条日文样句：**5 条判 en、3 条判 zh**
                #   ⇒ 判 en ⇒ 用 English 语言 token 读假名（分布外 ⇒ EOS 不稳
                #     ⇒ 偶发撞 2048 帧上限）
                #   ⇒ 判 zh ⇒ `normalize_zh_numbers` 误作用（2026年 → 二零二六年）
                # ⚠️ **缺 `lang` 的旧命令仍要能跑** ⇒ 兜底走 `_guess_lang`。
                lang = msg.get('lang')
                if not lang:
                    lang = self._guess_lang(text)
                # 🔴🔴 APP-024①：**dequeue 时刻** = worker 主循环从 stdin
                #   真正取到这条命令的瞬间。
                #   ⚠️ 为什么不直接在 `synth()` 入口取：`synth()` 是**独立线程**
                #   ⇒ 线程启动延迟会把「排队」混进「合成」⇒ 又分不开了。
                #   ⚠️ 为什么不用跨进程时钟：主进程与 worker 的
                #   `time.perf_counter()` **基准不同**（Windows 上是 QPC，
                #   起点是进程启动时刻）⇒ 不能直接相减
                #   ⇒ 跨进程的那一段（排队）**由主进程算**
                #     （`t_sent − t_submit`，同一个进程 ⇒ 时钟可比）。
                #   ⇒ worker 只报**自己口径**的 `t_dequeue`（供诊断）
                #     与**合成段** `synth_s = t_first − t_dequeue`。
                # 🔴🔴🔴 APP-027④：**入队**（不再每句开线程）。
                #   旧实现：每条 `synth` **新开一个线程**，线程们抢 `_synth_lock`
                #   ⇒ **不保证先来先得** ⇒ 播出顺序与提交顺序不一致
                #   ⇒ APP-027 问题③⑤（越拖越久 ⇒ 错位 ⇒ 全丢）。
                #   ⇒ 现在：**唯一**的合成线程 + `queue.Queue`（FIFO）。
                #   ⚠️ **顺序很重要**：先写 `_dequeue_at`（兜底 = 入队时刻），
                #      **再** `put` ⇒ 合成线程不可能「先 pop 后写」
                #      ⇒ 不会把 `t_dequeue` 弄丢（`synth()` 里 pop 不到就兜底）。
                t_enqueue = time.perf_counter()
                self._dequeue_at[jid] = t_enqueue
                est = self._estimate_dur_s(text)
                with self._synth_state_lock:
                    self._synth_queue_ids.append(jid)
                    self._synth_queue_est[jid] = est
                # 🔴🔴🔴 APP-030①：**`lang` 随命令进合成队列**
                #   ⇒ 合成线程拿得到**显式**语言 ⇒ 不再靠猜。
                self._synth_q.put((jid, text, spk, spk_conf, lang))
                self._emit_synth_state()
            elif cmd == 'cancel':
                # 🔴🔴🔴 APP-028②：**cancel 的语义已变**。
                #   旧语义：主进程因**积压超限**丢句 ⇒ 通知 worker 别播这句。
                #   ⇒ **该路径已整段删除**（见 `tts_service._update_backlog`）
                #      ⇒ 主进程**不再**因积压下发 cancel。
                #   新语义：**用户主动停止 / 切换会话** ⇒ 整句摘除。
                #   🔴 **关键**：「中止已写入句子」的路径（APP-028 明文要删）
                #      在这里被**替换**为「**把整句从队列里摘掉**」
                #      ⇒ 不是「播到一半切断」，而是「这一句**根本没播**」。
                jid = msg.get('id')
                with self._cancel_lock:
                    self._cancelled.add(jid)
                # 🔴 APP-028②：**整句摘除**（已入队的那部分也不播了）
                removed = 0
                try:
                    if self.player is not None and self.player.ring is not None:
                        removed = self.player.ring.drop_jid(jid)
                except Exception:
                    removed = 0
                # 🔴🔴🔴 APP-027④：cancel 把句子标记为丢弃。
                #   ⇒ 若是**还在 FIFO 里排队**（还没开始合成）的句子
                #      ⇒ 直接把它从队列状态里摘掉（否则主进程一直以为
                #      它还在排队 ⇒ 积压高估）。
                #   ⇒ 若是**正在合成**的 ⇒ 由 `synth()` 内部的逐块检查处理。
                with self._synth_state_lock:
                    try:
                        self._synth_queue_ids.remove(jid)
                    except ValueError:
                        pass
                    self._synth_queue_est.pop(jid, None)
                    self._synth_text.pop(jid, None)
                self._emit_synth_state()
                log(f'[tts_worker] 收到丢弃指令 id={jid}'
                    f'（已从队列摘除 {removed} 样本）')
                emit({'kind': 'dropped', 'id': jid, 'count': 1})
            elif cmd == 'spk_update':
                # 🔴🔴🔴 APP-029：**说话人晚到 ⇒ 补发更新**（接口预留）
                #   APP-029 明文：「定稿事件先按原样发出；另外增加
                #   spk_update(id, spk, spk_conf) 事件，用来更新字幕标签，
                #   以及**还没开始合成**的那几句的音色。
                #   **已经开始合成的句子不改。**」
                #   ⚠️ **本轮不集成**（APP-029 明文「现在不要集成」）
                #   ⇒ 这里只把命令**接住并记进日志**（不改变任何合成行为）
                #   ⇒ 真正的「更新还没开始合成的那几句的音色」要等
                #      TTS-019 交付「按句子取对应说话人的音色向量」。
                _jid = msg.get('id')
                _spk = msg.get('spk')
                _spk_conf = msg.get('spk_conf')
                log('[tts_worker] 收到 spk_update id=%s spk=%s conf=%s'
                    '（APP-029 预留接口，本轮不改变合成行为）'
                    % (_jid, _spk, _spk_conf))
            elif cmd == 'clear_queue':
                # 🔴🔴🔴 APP-028②：**用户手动停止 / 切换会话时清空队列**。
                #   APP-028 明文：「用户手动停止或切换会话时才清空队列」
                #   ⇒ 这是**唯一**允许清空队列的入口。
                #   🔴 顺带把「已取消」的标记清掉（下一轮会话是新的一句）
                #      ⇒ 否则新一轮的 jid 撞上旧标记会被误丢。
                n = 0
                try:
                    if self.player is not None and self.player.ring is not None:
                        n = self.player.ring.clear()
                except Exception:
                    n = 0
                with self._cancel_lock:
                    self._cancelled.clear()
                self._emit_synth_state()
                log(f'[tts_worker] 队列已清空（{n} 样本）')
                emit({'kind': 'queue_cleared', 'removed_samples': int(n)})
            elif cmd == 'clone':
                # 克隆说话人：更新最近 ≥3 s 的 16 kHz PCM 的条件
                try:
                    import base64
                    import numpy as np
                    pcm = np.frombuffer(base64.b64decode(msg.get('pcm', '')),
                                        dtype=np.float32)
                    self._update_clone(pcm)
                except Exception as e:
                    log(f'[tts_worker] 克隆更新失败：{e}')
            elif cmd == 'test_tone':
                # 🔴 APP-021④：**测试声音**（1 s 440 Hz 正弦波，走同一个 Player）
                #   ⇒ 把「播放链路」与「TTS 合成」彻底拆开：
                #     听得到 ⇒ 播放链路 OK；听不到 ⇒ 设备/音量/系统问题。
                th = threading.Thread(target=self._do_test_tone, daemon=True)
                th.start()
            elif cmd == 'telemetry':
                # 🔴 APP-021②：拉一次播放器遥测（不含模型）
                try:
                    tel = (self.player.telemetry() if self.player is not None
                           else {'error': '播放器不可用'})
                except Exception as e:
                    tel = {'error': '%s: %s' % (type(e).__name__, e)}
                emit({'kind': 'telemetry', 'telemetry': tel,
                      'id': msg.get('id')})
            elif cmd == 'set_dump_dir':
                # 🔴 APP-021⑥：**运行时**开关逐句 wav 落盘
                #   （worker 已经在跑，不能只靠启动参数 ⇒ 对话框勾选框要用）
                d = msg.get('dir') or None
                self.dump_dir = d
                log(f'[tts_worker] 逐句 wav 落盘目录：{d or "（关闭）"}')
                emit({'kind': 'dump_dir', 'dir': d})

        self._stop.set()
        # 🔴🔴🔴 APP-028②：**叫停播放看门狗线程**（否则它会一直阻塞在
        #   `wait_consumed` 里 ⇒ 进程退不干净）。
        try:
            self._played_q.put_nowait(None)
        except Exception:
            pass
        if self.player is not None:
            self.player.close()
        # 🔴🔴 APP-027⑤：**删除克隆临时文件**（隐私：会话结束即清）
        self._cleanup_clone_files()
        # 落盘模式：把时间轴混成 wav（C-101 P4 第 6 条）
        self._flush_timeline()
        # 逐句记录收尾（补写完整文件，崩溃也能靠增量行保留已完成部分）
        if self._jsonl_path and self._jsonl_rows:
            try:
                with open(self._jsonl_path, 'w', encoding='utf-8') as f:
                    for r in self._jsonl_rows:
                        f.write(json.dumps(r, ensure_ascii=False) + '\n')
            except Exception as e:
                log(f'[tts_worker] jsonl 收尾失败：{e}')

    def _safe_load(self):
        try:
            self.load()
        except Exception as e:
            import traceback
            log('[tts_worker] 加载失败：' + traceback.format_exc())
            emit({'kind': 'error', 'message': f'模型加载失败：{e}'})

    def _do_test_tone(self):
        """执行「测试声音」（APP-021④）。

        ⚠️ **必须在模型 ready 之后才有意义**（播放流是模型加载时按采样率
        重建的）⇒ 没 ready 时也要能测（用当前 player）。
        """
        try:
            if self.player is None:
                emit({'kind': 'test_tone', 'ok': False,
                      'message': '播放器不可用（没有可用的输出设备）'})
                return
            before = self.player.telemetry()
            ok, diag = self.player.test_tone()
            after = self.player.telemetry()
            tel = dict(after)
            tel['cb_delta'] = after.get('n_cb', 0) - before.get('n_cb', 0)
            tel['read_delta'] = (after.get('n_read', 0)
                                 - before.get('n_read', 0))
            log('[tts_worker] 测试声音：%s' % diag)
            emit({'kind': 'test_tone', 'ok': bool(ok),
                  'message': diag, 'telemetry': tel})
        except Exception as e:
            import traceback
            log('[tts_worker] 测试声音失败：' + traceback.format_exc())
            emit({'kind': 'test_tone', 'ok': False,
                  'message': f'{type(e).__name__}: {e}'})

    # -- 🔴🔴🔴 APP-027⑤：**克隆当前说话人**（真正接入）----------------
    def _update_clone(self, pcm):
        """🔴🔴🔴 APP-027⑤：用最近的 16 kHz PCM 更新**克隆音色**。

        🔴🔴 **三条硬约束**（APP-027 明文）：

        ① **不落盘**：x-vector / 参考音频 **只在内存里**
           ⇒ **绝不**写 `voices/clone_C.npz`
           ⇒ **绝不**写 `tts_speakers/`
           （隐私：APP-022「共用约定」；打包闸门也会拦这两个）
        ② **更新失败要显式写日志 + 回落预设 A**
           ⇒ 绝不静默（§42 的教训：静默回落 ⇒ 用户以为在用克隆音色）
        ③ **下一句起生效**（不改已排队的句子）

        🔴 **两条路线**（按后端分）：
        - **BabelVox（NPU / GPU.0）**：用 `tts_engine.speaker_embedding()`
          把 PCM 写成 x-vector `(1, 1024)` ⇒ 换 `self.speaker_embed`
          ⇒ 下一句走 `speaker_embed` 路线。
        - **CUDA 边车**：把 PCM 存成**内存里的临时 wav**
          ⇒ 用 `set_ref` 命令把路径告诉边车 ⇒ 边车用
          `generate_voice_clone_streaming(ref_audio=...)` 合成。
          ⇒ ⚠️ 库只接受**路径** ⇒ 必须落一个临时文件
          ⇒ **会话结束即删除**（本模块 `close()` 里删）。
        """
        import numpy as np

        pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if len(pcm) < 16000 * 3:      # 至少 3 s
            log('[tts_worker] 🔴 克隆源语音不足 3 s ⇒ 仍用预设 A')
            return False
        pcm = pcm[-16000 * 10:]        # 最多留 10 s
        dur_s = len(pcm) / 16000.0

        # ── 路线 1：BabelVox（NPU / GPU.0）—— x-vector ──────────────
        eng = self.engine
        if eng is not None and not getattr(eng, 'USES_REF_AUDIO', False):
            try:
                import tts_engine
                # ⚠️ babelvox 的 `extract_speaker_embedding` 只接受**路径**
                #   ⇒ 必须先落一个临时 wav（**用完即删**）。
                tmp = self._clone_tmp_wav(pcm)
                try:
                    spk = tts_engine.speaker_embedding(eng, tmp,
                                                       on_log=log)
                finally:
                    self._safe_unlink(tmp)
                if spk is None:
                    raise RuntimeError('speaker_embedding 返回 None')
                self.speaker_embed = spk
                self.speaker_name = None
                self._clone_embed = spk
                self._clone_audio_s = dur_s
                self._clone_updated_at = time.time()
                self._clone_active = True
                # 🔴🔴🔴 APP-027 V3：**记下路线**（逐句遥测要能区分）
                self._clone_mode = 'xvector'
                log('[tts_worker] ✅ 克隆音色已更新（BabelVox x-vector，%.1f s）'
                    % dur_s)
                emit({'kind': 'clone', 'ok': True, 'dur_s': round(dur_s, 2),
                      'updated_at': self._clone_updated_at,
                      'mode': 'xvector'})
                return True
            except Exception as e:
                log(f'[tts_worker] 🔴 克隆音色更新失败（BabelVox）：{e}')
                self._fallback_to_preset('BabelVox')
                emit({'kind': 'clone', 'ok': False,
                      'message': '克隆更新失败：%s' % e,
                      'updated_at': self._clone_updated_at})
                return False

        # ── 路线 2：CUDA 边车 —— 换参考音频 ────────────────────────
        if eng is not None and getattr(eng, 'USES_REF_AUDIO', False):
            try:
                tmp = self._clone_tmp_wav(pcm)
                ok = eng.set_ref_audio(tmp)
                if not ok:
                    raise RuntimeError('边车拒绝 set_ref')
                # 🔴🔴 APP-027⑤：**切换参考音频后删掉旧的临时 wav**
                #   ⇒ 旧的边车已不再引用它 ⇒ 可以安全删
                #   （⚠️ 只在 set_ref 成功后才删 ⇒ 失败时旧 ref 仍在用）
                old_ref = self._clone_ref_path
                self._clone_ref_path = tmp
                if old_ref and old_ref != tmp:
                    self._safe_unlink(old_ref)
                    try:
                        self._clone_tmp_paths.remove(old_ref)
                    except ValueError:
                        pass
                self._clone_audio_s = dur_s
                self._clone_updated_at = time.time()
                self._clone_active = True
                # 🔴🔴🔴 APP-027 V3：**记下路线**（逐句遥测要能区分）
                self._clone_mode = 'ref_audio'
                log('[tts_worker] ✅ 克隆音色已更新（CUDA 边车 ref_audio，%.1f s）'
                    % dur_s)
                emit({'kind': 'clone', 'ok': True, 'dur_s': round(dur_s, 2),
                      'updated_at': self._clone_updated_at,
                      'mode': 'ref_audio'})
                return True
            except Exception as e:
                log(f'[tts_worker] 🔴 克隆音色更新失败（CUDA 边车）：{e}')
                self._fallback_to_preset('CUDA 边车')
                emit({'kind': 'clone', 'ok': False,
                      'message': '克隆更新失败：%s' % e,
                      'updated_at': self._clone_updated_at})
                return False

        log('[tts_worker] ⚠️ 没有可用引擎 ⇒ 克隆无法生效（仍用预设 A）')
        return False

    def _fallback_to_preset(self, why: str = ''):
        """🔴🔴🔴 APP-027⑤：**显式回落预设 A**（克隆失败时）。

        🔴 **为什么必须有这个函数**：
          APP-027 明文「更新失败要显式写日志、回落预设 A」。
          而旧实现只写了 `self._clone_active = False`
          ⇒ **音色向量仍是上一次克隆的**（或 None）
          ⇒ 回落只是「嘴上说说」⇒ 实际仍在用克隆音色
          ⇒ 用户以为在用预设 A，其实一直在克隆。

        ⇒ 这里真正把 `speaker_embed` / `speaker_name` 换回**预设 A 的缓存**。
        ⚠️ 预设 A 的缓存来自 `_setup_babelvox_voice()`（加载时算一次）。
        """
        self._clone_active = False
        # 🔴🔴🔴 APP-027 V3：回落时**路线也要清**
        #   ⇒ 否则逐句遥测会写 `clone_mode='xvector'` 而 `clone_active=False`
        #   ⇒ reviewer 看到「路线是 xvector」会误判「这句是克隆音色的」
        #   ⇒ **矛盾字段** ⇒ 结论不可核。
        self._clone_mode = None
        try:
            self.speaker_embed = self._preset_embed
            self.speaker_name = self._preset_name
        except Exception:
            self.speaker_embed = None
            self.speaker_name = 'A'
        # 🔴 CUDA 边车：把参考音频换回预设 A 的 wav
        eng = self.engine
        if eng is not None and getattr(eng, 'USES_REF_AUDIO', False):
            ref = self._preset_ref_path
            if ref:
                try:
                    eng.set_ref_audio(ref)
                except Exception as e:
                    log('[tts_worker] 🔴 回落预设 A 时换参考音频失败：%s' % e)
        log('[tts_worker] 🔴 ⇒ 已回落到预设 A（不静默）'
            + (f'（原因：{why}）' if why else ''))

    def _clone_tmp_wav(self, pcm):
        """把克隆源 PCM 落成**临时 wav**（**用完即删**）。

        🔴 **为什么必须落文件**：babelvox 的 `extract_speaker_embedding(audio_path)`
        与 `generate_voice_clone_streaming(ref_audio=...)` **都只接受路径**。
        🔴 **隐私**：这是**临时文件** ⇒
        - 目录用 `tempfile.gettempdir()`（**不在客户包目录里**）
        - 文件名带进程 id ⇒ 不会互相覆盖
        - **会话结束即删除**（见 `close()` / `__del__`）
        - ⇒ **绝不会**进客户包（打包闸门另有一道）
        """
        import tempfile
        import soundfile as sf
        d = os.path.join(tempfile.gettempdir(), 'confucius4_clone')
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, 'clone_%d_%d.wav' % (os.getpid(),
                                                    int(time.time() * 1000)))
        sf.write(path, pcm, 16000)
        self._clone_tmp_paths.append(path)
        return path

    @staticmethod
    def _safe_unlink(path):
        try:
            if path and os.path.isfile(path):
                os.unlink(path)
        except Exception:
            pass

    def _cleanup_clone_files(self):
        """🔴 APP-027⑤：**删除所有克隆临时文件**（会话结束 / 关闭时）。"""
        for p in list(self._clone_tmp_paths):
            self._safe_unlink(p)
        try:
            self._clone_tmp_paths.clear()
        except Exception:
            pass

    # 🔴🔴🔴 APP-027⑤：**删除旧引擎的死代码**。
    #   旧 `_update_clone` 有两条路线都依赖**旧 Confucius4-TTS 引擎**
    #   （`ov_runtime` 的 w2vbert / CAMPPlus / `clone_C.npz` 落盘、
    #    `self.tts_model.extract_cond` 的 torch 路线）
    #   ⇒ 而 `load()` 自 APP-023③ 起**只走 BabelVox**
    #   ⇒ `self.ov_runtime` / `self.tts_model` **永远是 None**
    #   ⇒ 这两条路线是**死代码**，而且 `_extract_cond_ov` 会
    #      **把克隆音色写盘到 `voices/clone_C.npz`**
    #   ⇒ 违反 APP-022 隐私约定（用户音色不该落盘、更不该进客户包）。
    #   ⇒ 本轮**整段删除**（`load()` 的 docstring 已注明旧分支成死代码）。
    #   ⚠️ `self.conds` / `self.ov_rt` 的**引用**仍保留（非 BabelVox 分支
    #      的 `synth()` 会读它们）⇒ 但那些分支现在**永远走不到**
    #      （`self.engine` 恒非 None ⇒ `is_babelvox` 恒 True）。
    #   ⇒ 保留字段只为**不引入新风险**。


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--device', default='GPU.0')
    # 🔴 bf16 只对 **PyTorch+CUDA 后端**有意义（该后端恒 bf16，忽略该参数）；
    #   OV 后端仍只认 f32/f16（bf16 传进来会被归一成 f32）。
    ap.add_argument('--precision', default='f32',
                    choices=['f32', 'f16', 'bf16'])
    ap.add_argument('--voice', default='A',
                    help='音色：A / B / clone，或 babelvox 内置 speaker'
                         '（cindy / lou / phil / steve）')
    ap.add_argument('--out-device', default=None)
    ap.add_argument('--model-dir', default=None)
    ap.add_argument('--clone', action='store_true')
    ap.add_argument('--bigvgan-ir', default=None,
                    help='指定 BigVGAN IR 路径（多相分解版）')
    ap.add_argument('--tts-cache-dir', default=None,
                    help='NPU 编译缓存目录（默认 %%LOCALAPPDATA%%'
                         '\\Confucius4LiveCaption\\tts_npu_cache）')
    ap.add_argument('--out-wav', default=None,
                    help='落盘模式：把语音按**真实时间轴**混成一个 wav'
                         '（C-101 P4 第 6 条的 CLI 回放测试）')
    ap.add_argument('--jsonl', default=None,
                    help='逐句记录文件（默认 <out-wav>.tts.jsonl）')
    ap.add_argument('--dump-dir', default=None,
                    help='🔴 APP-021⑥：逐句 wav 落盘目录（每段一个 wav，'
                         '供 reviewer 算 RMS / 回转写）；不给 = 不落盘')
    ap.add_argument('--seed', type=int, default=1234)
    ap.add_argument('--steps', type=int, default=25)
    ap.add_argument('--cfg-rate', type=float, default=0.7)
    args = ap.parse_args()

    # 🔴🔴 [APP-FIX-20261023] 主线程**预导入**重依赖（numpy / scipy.linalg）
    #
    # 症状：worker 经 `tts_service.TTSService`（`Popen(stdout=PIPE)`）起时
    #      **stdout 一行都不输出**，主进程永远停在 `state=loading`，
    #      drain 超时、0 句播完（见 status/app/STATUS_APP.md §15）。
    #
    # 根因：模型加载跑在**后台线程**（`threading.Thread(target=self._safe_load)`），
    #      而它要 import 的 numpy / scipy 是 **C 扩展** ⇒ import 期间持有
    #      importlib 的**模块级锁**；与此同时主线程正阻塞在
    #      `for line in sys.stdin`（首次迭代会触发 io/textiobuffer 的加载），
    #      同样需要这把锁 ⇒ **互相等待的 import 死锁**。
    #      faulthandler 实测栈：后台线程停在
    #      `numpy/_core/multiarray.py:11 in create_module`。
    #
    # 为什么之前没暴露：`import tts_engine`（纯 python）不触发 C 扩展加载，
    #      单独测 worker 一切正常 ⇒ 只有「Popen + 后台加载 + stdin 阻塞」
    #      三者同时成立才复现。
    #
    # 修法：把重依赖的 import 提到**主线程**、且在**任何后台线程启动之前**。
    #      实测预导入耗时 0.3 s，修复后 worker 9.4 s 正常 emit `ready`。
    try:
        import numpy  # noqa: F401
        import scipy.linalg  # noqa: F401
    except Exception:
        # 预导入失败不致命：退回旧行为（下游仍会在 import 处报错，但有 traceback）
        pass

    w = TTSWorker(device=args.device, voice=args.voice, out_device=args.out_device,
                  model_dir=args.model_dir, clone=args.clone,
                  bigvgan_ir=args.bigvgan_ir, precision=args.precision,
                  out_wav=args.out_wav, seed=args.seed, steps=args.steps,
                  cfg_rate=args.cfg_rate)
    w.dump_dir = args.dump_dir
    w.tts_cache_dir = args.tts_cache_dir
    # jsonl 路径：`--out-wav` 存在时默认 `<out-wav>.tts.jsonl`
    if args.jsonl:
        w._jsonl_path = args.jsonl
    elif args.out_wav:
        w._jsonl_path = args.out_wav + '.tts.jsonl'
    try:
        w.run()
    except Exception:
        import traceback
        log('[tts_worker] 异常退出：' + traceback.format_exc())
        w._flush_timeline()
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
