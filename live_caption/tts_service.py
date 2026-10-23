"""tts_service.py — 实时字幕 App 的译文语音输出服务（C-101 / P4）。

## 定位

实时同传链路：**说话 → 字幕 → 译文 → 译文语音**。
本模块负责最后一段：把**定稿译文**变成 22050 Hz 的语音并播放出来。

## 关键设计

1. **TTS 跑在独立子进程**（`tts_worker.py`）。
   理由：TTS 是 CPU 密集（numpy 特征 + 采样 + S2A 25 步 Euler），
   放在主进程会跟 ASR / MT 抢 GIL，把字幕识别拖垮。
   独立进程还有第二个好处：worker 崩溃**不会**带崩字幕翻译。

2. **只取定稿译文**，不取草稿。草稿会被后续定稿推翻，播出去就是错的。

3. **积压超 8 s 丢最旧未播句并计数**。
   实时同传里，播一句过时的译文比不播更糟（听到的内容和屏幕上对不上）。
   丢句数显示在底栏，让用户知道语音输出跟不上。

4. **播放也在 worker 进程内**（`sounddevice.OutputStream` + 环形缓冲）。
   跨进程传音频再播会引入额外的拷贝延迟，而且播放状态和合成状态分散在两个进程
   不好协调。放在 worker 里，合成完立刻进环形缓冲。

## 接口

    svc = TTSService(device='GPU.0', voice='A', out_device=None, on_log=print)
    svc.start()                       # 起 worker 进程
    svc.submit(text, seg=0)           # 提交一条定稿译文
    svc.pop_outbox()                  # 取事件 [(kind, payload), ...]
    svc.stats()                       # 首包延迟 / 积压 / 丢句数
    svc.close()
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from collections import OrderedDict
from typing import List, Optional

# 与 App 同目录，worker 脚本
_HERE = os.path.dirname(os.path.abspath(__file__))
_WORKER = os.path.join(_HERE, "tts_worker.py")

# 积压上限（秒）：超过就丢最旧的未播句
BACKLOG_MAX_S = float(os.environ.get('LIVECAP_TTS_BACKLOG_MAX', '8'))
# 单句最长（秒）：防止异常长句卡住
MAX_TEXT_CHARS = int(os.environ.get('LIVECAP_TTS_MAX_CHARS', '200'))


class TTSService:
    """译文语音输出服务（主进程侧）。

    状态机：idle → loading → ready → error
    与 TranslationService 的线程模型一致：主进程只管收发队列，
    重活全在 worker 进程。
    """

    def __init__(self, device: str = 'GPU.0', voice: str = 'A',
                 out_device: Optional[str] = None, model_dir: Optional[str] = None,
                 on_log=print, auto: bool = True, clone: bool = False,
                 precision: str = 'f32', out_wav: Optional[str] = None,
                 bigvgan_ir: Optional[str] = None):
        self.on_log = on_log
        self.device = device
        self.voice = voice            # 'A' | 'B' | 'clone'
        self.out_device = out_device  # 输出设备名（None = 系统默认）
        self.model_dir = model_dir
        self.clone = clone            # 克隆当前说话人
        self.precision = precision    # OV 推理精度（f32 / f16）
        self.out_wav = out_wav        # 落盘模式（CLI 回放测试）
        self.bigvgan_ir = bigvgan_ir  # BigVGAN IR 覆盖（多相分解版 / NPU 窗口版）

        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self.state = 'idle'
        self.err = None
        self.n_restart = 0             # worker 崩溃重启次数（C-101：最多 1 次）
        self._restarted = False
        # 🔴 2026-10-24 §21 修：`_closing` 闸门 —— `close()` 期间**禁止重启 worker**。
        #   起因：旧 `close()` 把 `self.state = 'idle'` 放在 `p.wait()` **之后**，
        #   而 `p.wait()` 一返回，stdout 就已关闭 ⇒ `_read_loop` 线程醒来时
        #   `self.state` 仍是 'ready' ⇒ 走 `_on_worker_exit()` ⇒ **自动重启一次**
        #   ⇒ `close()` 返回后 `self.proc` 指向**新进程**，它永远收不到 quit
        #   ⇒ **孤儿 worker 进程泄漏**（占着 GPU/NPU + 音频输出流）。
        #   实测（`results/app/test_tts_close_orphan.py`）：close() 后多起 1 个
        #   worker 且**仍存活**。GUI 的 quit / 停 TTS / 换设备 / 换音色 4 条路径
        #   都会调 `close()` ⇒ 每次都漏一个孤儿。
        self._closing = False
        self._reader_threads: List = []

        # 统计
        self.first_packet_s: Optional[float] = None   # 首包延迟
        self.backlog_s = 0.0                          # 当前积压
        self.max_backlog_s = 0.0                     # 最大积压
        self.n_dropped = 0                            # 丢句数
        self.n_played = 0                             # 已播句数
        self.n_submitted = 0

        # 主进程侧的待播队列（只做积压统计与丢句决策，音频全在 worker 里）
        self.pending: 'OrderedDict[int, dict]' = OrderedDict()
        self._next_id = 0
        self._outbox: List = []
        self._outbox_lock = threading.Lock()
        # worker 未 ready 时暂存的下发命令（ready 后补发）
        self._queue: List = []

        if auto:
            self.start()

    # -- 生命周期 --------------------------------------------------------
    @property
    def active(self) -> bool:
        return self.state in ('loading', 'ready')

    def start(self):
        """起 worker 进程。"""
        with self.lock:
            # 🔴 §21：`close()` 期间（`_closing=True`）**不允许起 worker**。
            #   否则 close() 与退出竞态时会把刚起的 worker 立刻丢掉 ⇒ 又一个孤儿。
            if self._closing:
                self.on_log('[TTS] 正在关闭，跳过 worker 启动')
                return
            if self.proc is not None and self.proc.poll() is None:
                return
            # 🔴 §21：旧 proc 已死（poll 有退出码）⇒ 必须先回收它的管道，
            #   否则它的 reader 线程还挂着（daemon 线程会一直占着 fd）。
            if self.proc is not None:
                try:
                    self.proc.kill()
                except Exception:
                    pass
                self.proc = None
            self.state = 'loading'
            self.err = None
            env = dict(os.environ)
            # 让 worker 里的 tts_ov 能被 import 到
            env['LIVECAP_TTS_DIR'] = env.get('LIVECAP_TTS_DIR', '')
            cmd = [sys.executable, _WORKER,
                   '--device', self.device,
                   '--precision', self.precision,
                   '--voice', self.voice]
            if self.out_device:
                cmd += ['--out-device', self.out_device]
            if self.model_dir:
                cmd += ['--model-dir', self.model_dir]
            if self.clone:
                cmd += ['--clone']
            if self.out_wav:
                cmd += ['--out-wav', self.out_wav]
            if self.bigvgan_ir:
                cmd += ['--bigvgan-ir', self.bigvgan_ir]
            try:
                self.proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
            except Exception as e:
                self.state = 'error'
                self.err = e
                self.on_log(f'[TTS] worker 启动失败：{e}')
                return
        self._start_reader()

    def _start_reader(self):
        """后台线程读 worker 的 stdout（状态行）与 stderr（日志）。"""
        proc = self.proc
        if proc is None:
            return
        t = threading.Thread(target=self._read_loop, args=(proc,), daemon=True)
        t.start()
        # 🔴 stderr **必须**有独立读者（2026-10-24 §20 修）。
        #   原因：worker 的 traceback / 库的告警都走 stderr ⇒
        #   ① 不读 ⇒ **静默吞掉崩溃原因**（排查时完全看不到东西）；
        #   ② 不读 ⇒ 管道缓冲区（Windows 约 64 KB）写满后 worker 会
        #      **阻塞在 write(stderr)** ⇒ 表现为「worker 永不 ready」
        #      的假死（和 §15 的 import 死锁症状一样，极难定位）。
        #   ⚠️ 不能合并进 _read_loop —— 那个循环在 stdout 关闭才结束，
        #      而 stdout 的行是稀疏的 ⇒ stderr 会一直堵着没人读。
        t2 = threading.Thread(target=self._read_stderr_loop, args=(proc,), daemon=True)
        t2.start()
        self._reader_threads = [t, t2]

    def _read_stderr_loop(self, proc):
        """把 worker 的 stderr 逐行转给 `on_log`（不再静默丢弃）。"""
        if proc is None or proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                line = line.rstrip('\r\n')
                if not line:
                    continue
                self.on_log(f'[TTS][stderr] {line}')
        except Exception:
            # stderr 在进程退出时关闭 → readline 抛 ValueError/IOError 属正常
            pass

    def _read_loop(self, proc):
        if proc is None:
            return
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('{'):
                    try:
                        msg = json.loads(line)
                    except Exception:
                        continue
                    self._handle_event(msg)
                else:
                    self.on_log(f'[TTS] {line}')
        except Exception:
            pass
        # stdout 关闭 = worker 退出
        # 🔴 §21：`poll()` 在进程刚死时可能仍返回 None（Windows 上退出码还没回填）
        #   ⇒ 旧代码把 `rc=None` 记进日志，且**判断不到「真的死了」**。
        #   这里显式 `wait()` 拿到真实退出码。
        try:
            rc = proc.wait(timeout=2)
        except Exception:
            rc = proc.poll()
        # 🔴 §21：只有「**不是**主动 close 导致的退出」才走重启路径。
        #   主动 close 时 `_closing=True` ⇒ 不重启（否则就是孤儿泄漏）。
        if self.state != 'idle' and not self._closing:
            self._on_worker_exit(rc, proc)

    def _on_worker_exit(self, rc, dead_proc=None):
        """worker 崩溃：C-101 要求自动重启一次；再崩就报错（不影响字幕翻译）。"""
        if self._restarted:
            self.state = 'error'
            self.err = RuntimeError(f'TTS worker 退出（rc={rc}），已重启过一次仍失败')
            self.on_log(f'[TTS] worker 再次退出（rc={rc}），不再重启；语音输出已停用')
            return
        # 🔴🔴 §21：**必须先把死掉的 proc 从 `self.proc` 上摘掉**，否则
        #   `start()` 开头那句
        #       if self.proc is not None and self.proc.poll() is None: return
        #   会看到「旧 proc 还活着」（Windows 上 poll 还没更新）⇒ **直接 return**
        #   ⇒ C-101 要求的「崩溃自动重启一次」**从未真正生效**（实测：
        #   `results/app/test_tts_restart_nop.py` ⇒ worker 实例启动次数 = 1）。
        #   后果更糟：`state` 停在 'ready' ⇒ App 以为 TTS 正常
        #   ⇒ 之后每句 `submit()` 都写进**死进程的 stdin** ⇒ **语音输出静默消失**，
        #   不报错、不掉状态（与 §15/§20 的现象高度吻合）。
        with self.lock:
            if dead_proc is not None and self.proc is dead_proc:
                self.proc = None
        self._restarted = True
        self.n_restart += 1
        self.on_log(f'[TTS] worker 退出（rc={rc}），自动重启一次')
        self.start()

    def close(self):
        """关闭 TTS worker（**必须真正关掉，不留孤儿进程**）。

        🔴 2026-10-24 §21 修（**孤儿 worker 进程泄漏**）：
        旧实现的顺序错了 —— `self.state = 'idle'` 放在 `p.wait()` **之后**，
        而 `p.wait()` 一返回，stdout 已关闭 ⇒ `_read_loop` 线程醒来时
        `self.state` 仍是 'ready' ⇒ 判定为「worker 崩溃」⇒ `_on_worker_exit()`
        ⇒ **自动重启一次** ⇒ `close()` 返回后 `self.proc` 指向**新进程**，
        它永远收不到 quit ⇒ **孤儿进程**（占 GPU/NPU + 音频输出流）。
        实测：`results/app/test_tts_close_orphan.py` ⇒ close() 后多起 1 个
        worker 且**仍存活**。GUI 有 4 条路径会调 `close()`（quit / 停 TTS /
        换设备 / 换音色）⇒ 每走一次漏一个孤儿。

        新顺序：
          ① `_closing = True`（闸门：禁止 `start()` 重启）；
          ② `state = 'idle'`（让 `_read_loop` 的 `state != 'idle'` 判断为假）；
          ③ 发 quit → 等 → kill；
          ④ **再等 reader 线程收尾**（避免它们还持有旧 proc 的管道）。
        """
        with self.lock:
            self._closing = True
            p = self.proc
            self.proc = None
            self.state = 'idle'
        try:
            if p is not None:
                try:
                    p.stdin.write(json.dumps({'cmd': 'quit'}) + '\n')
                    p.stdin.flush()
                except Exception:
                    pass
                try:
                    p.wait(timeout=3)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
                    try:
                        p.wait(timeout=2)
                    except Exception:
                        pass
            # 等 reader 线程收尾（它们读的是旧 proc 的管道）
            for th in list(self._reader_threads):
                try:
                    th.join(timeout=1.0)
                except Exception:
                    pass
            self._reader_threads = []
        finally:
            with self.lock:
                self._closing = False

    # -- 提交 ------------------------------------------------------------
    def submit(self, text: str, seg: Optional[int] = None):
        """提交一条**定稿译文**。

        ⚠️ worker 还没 `ready` 时**不能直接下发** —— worker 的 stdin
        在模型加载完成前也在收命令，但那时音色条件还没加载好，
        合成会失败。所以这里**先入待发队列**，等 `ready` 事件后补发。
        """
        text = (text or '').strip()
        if not text:
            return
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]
        with self.lock:
            jid = self._next_id
            self._next_id += 1
            self.pending[jid] = dict(seg=seg, text=text, t=time.perf_counter())
            self.n_submitted += 1
            ready = (self.state == 'ready')
        cmd = {'cmd': 'synth', 'id': jid, 'text': text}
        if ready:
            self._send(cmd)
        else:
            with self.lock:
                self._queue.append(cmd)
        self._update_backlog()

    def _flush_queue(self):
        """worker 就绪后补发待发队列。"""
        with self.lock:
            q = list(self._queue)
            self._queue.clear()
        for cmd in q:
            self._send(cmd)
        if q:
            self.on_log(f'[TTS] 就绪后补发 {len(q)} 句')

    def drain(self, timeout: float = 30.0) -> bool:
        """等所有已提交的句子都播完（或超时）。

        用于**收尾**：App 退出前要把队列里的话念完，不能半路掐断。
        返回 True 表示已排空。

        ⚠️ 判定依据是「已提交数 == 已播数 + 已丢数」——
        worker 侧的 `played` / `dropped` 事件都会更新这两个计数。

        ⚠️ **worker 还没 ready 时**，先给它一段加载时间（`timeout` 的
        一半，最多 60 s）——模型加载要几十秒（实测 CPU 37 s），
        不等就退出会把待发队列里的句子全丢掉。
        """
        t0 = time.perf_counter()
        # ── 阶段 1：等 worker ready ──
        ready_wait = min(60.0, max(5.0, timeout * 0.5))
        while time.perf_counter() - t0 < ready_wait:
            if self.state in ('ready', 'error'):
                break
            time.sleep(0.2)

        # ── 阶段 2：等排空 ──
        t_end = t0 + timeout
        while time.perf_counter() < t_end:
            with self.lock:
                pending_n = len(self.pending)
                n_sub = self.n_submitted
                n_done = self.n_played + self.n_dropped
            if pending_n == 0 and n_done >= n_sub:
                return True
            time.sleep(0.2)
        with self.lock:
            pending_n = len(self.pending)
        self.on_log(f'[TTS] drain 超时：仍有 {pending_n} 句未完成')
        return False

    def _send(self, obj: dict):
        with self.lock:
            p = self.proc
        if p is None or p.stdin is None:
            return
        try:
            p.stdin.write(json.dumps(obj, ensure_ascii=False) + '\n')
            p.stdin.flush()
        except Exception as e:
            self.on_log(f'[TTS] 发送失败：{e}')

    def cancel(self, jid: int):
        """通知 worker 丢弃某一句（还没开始播的整句）。

        C-101 P4 第 2 条：「积压超 N 秒就丢掉最旧的**未开始的句子**」。
        丢掉必须**整句为单位**，所以主进程在丢弃时也要让 worker 别播这一句
        —— 否则 worker 照样合成并播出来，丢弃就白做了。

        ⚠️ **计数只在这里加一次**（2026-10-22 修）：
        worker 收到 `cancel` 后会回一条 `{'kind':'dropped','id':jid}` 事件，
        而 `_handle_event` 也会 `n_dropped += count`
        ⇒ 同一句被**计了两次**（实测「提交 9」却报「丢弃 16」）。
        现在 worker 侧的 `dropped` 事件**不再计数**（只记日志），
        因为所有丢弃都是主进程发起的（积压超限 / 显式 cancel）。
        """
        self._send({'cmd': 'cancel', 'id': jid})
        with self.lock:
            self.pending.pop(jid, None)
        self.n_dropped += 1

    # -- 事件 ------------------------------------------------------------
    def _handle_event(self, msg: dict):
        kind = msg.get('kind')
        if kind == 'ready':
            self.state = 'ready'
            self.on_log(f'[TTS] 就绪：{msg.get("device")} · 音色 {msg.get("voice")}')
            self._flush_queue()
        elif kind == 'error':
            self.state = 'error'
            self.err = msg.get('message', 'unknown')
            self.on_log(f'[TTS] 错误：{self.err}')
        elif kind == 'first_packet':
            # 首包延迟：从 submit 到 worker 开始播这段
            self.first_packet_s = msg.get('latency_s')
        elif kind == 'played':
            jid = msg.get('id')
            with self.lock:
                self.pending.pop(jid, None)
            self.n_played += 1
        elif kind == 'dropped':
            # ⚠️ **不再计数**（2026-10-22 修）：
            # worker 的 `dropped` 事件是对主进程 `cancel` 指令的**回执**，
            # 丢弃数已经在 `cancel()` / `_update_backlog()` 里加过了。
            # 这里再加一次会导致同一句被计两遍
            # （实测「提交 9 / 丢弃 16」）。
            self.on_log(f'[TTS] 已丢弃 id={msg.get("id")}')
        elif kind == 'log':
            self.on_log(f'[TTS] {msg.get("message", "")}')

    def pop_outbox(self) -> List:
        with self._outbox_lock:
            out, self._outbox = self._outbox, []
        return out

    def _emit(self, kind, payload):
        with self._outbox_lock:
            self._outbox.append((kind, payload))

    # -- 积压与丢句 ------------------------------------------------------
    def _update_backlog(self):
        """按**音频时长**估算积压（不是字数），超 8 s 就丢最旧的未播句。

        ⚠️ **worker 还没 ready 时不丢句**（2026-10-22 修）：
        worker 加载模型要几十秒（实测 CPU 37 s），这段时间里所有提交的句子
        都堆在待发队列上，积压估算会瞬间超过阈值
        ⇒ 实测 30 s 回放里 **8 句全被丢掉**，一句都没念。
        但这段积压**不是播放跟不上造成的**，是模型还没加载完
        ⇒ 此时丢句是误伤。改成：ready 之前只**记录**积压，不丢。
        """
        with self.lock:
            pending = list(self.pending.values())
        if not pending:
            self.backlog_s = 0.0
            return
        # 粗略估算：中文 ~5 字/秒，英文 ~2.5 词/秒
        est = 0.0
        for it in pending:
            t = it['text']
            cjk = sum(1 for ch in t if '\u4e00' <= ch <= '\u9fff')
            other = len(t) - cjk
            est += cjk / 5.0 + other / 15.0
        self.backlog_s = est
        self.max_backlog_s = max(self.max_backlog_s, est)

        if est > BACKLOG_MAX_S:
            # ⚠️ **worker 还没 ready ⇒ 只记录，不丢**（见本方法 docstring）
            if self.state != 'ready':
                self.on_log(f'[TTS] 积压 {est:.1f}s（模型尚未就绪，暂不丢弃）')
                return
            # 丢最旧的未播句（**整句为单位**，C-101 P4 第 2 条）
            with self.lock:
                drop_ids = []
                acc = 0.0
                for jid, it in self.pending.items():
                    t = it['text']
                    cjk = sum(1 for ch in t if '\u4e00' <= ch <= '\u9fff')
                    d = cjk / 5.0 + (len(t) - cjk) / 15.0
                    acc += d
                    drop_ids.append(jid)
                    if acc > BACKLOG_MAX_S * 0.5:
                        break
                for jid in drop_ids:
                    self.pending.pop(jid, None)
            # 通知 worker 别播这些句子（否则丢弃白做了）
            for jid in drop_ids:
                self._send({'cmd': 'cancel', 'id': jid})
            self.n_dropped += len(drop_ids)
            self.on_log(f'[TTS] 积压 {est:.1f}s > {BACKLOG_MAX_S}s，丢弃 {len(drop_ids)} 句未播译文')

    def stats(self) -> dict:
        return dict(
            state=self.state,
            first_packet_s=self.first_packet_s,
            backlog_s=round(self.backlog_s, 2),
            max_backlog_s=round(self.max_backlog_s, 2),
            n_dropped=self.n_dropped,
            n_played=self.n_played,
            n_submitted=self.n_submitted,
            n_restart=self.n_restart,
            voice=self.voice,
            device=self.device,
            out_device=self.out_device,
            clone=self.clone,
        )
