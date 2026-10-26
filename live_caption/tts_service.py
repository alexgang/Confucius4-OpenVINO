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
from collections import OrderedDict, deque
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

        # 🔴🔴 §52：**故障必须自带原因**。
        #   用户报「TTS worker 故障（error）⇒ 朗读中止」时，界面只有这一句，
        #   拿不到 worker 到底为什么错（模型加载 / 播放设备 / 边车启动），
        #   而 worker 级 error 的 message 其实**已经发过来了**，只是被丢了。
        #   ⇒ `last_error` 存最近一次**worker 级**错误原文；
        #      `log_tail` 存最近 200 行 worker 日志（含 stderr 转发）。
        self.last_error: Optional[str] = None
        self.log_tail: deque = deque(maxlen=200)
        # `on_log` 外面套一层：**先记账再转发**（调用方仍只看到自己的 on_log）
        self._on_log_user = on_log
        self.on_log = self._log_and_forward

        # 主进程侧的待播队列（只做积压统计与丢句决策，音频全在 worker 里）
        self.pending: 'OrderedDict[int, dict]' = OrderedDict()
        # 🔴 2026-10-24 §22 修：**已下发 worker、等待结果**的句子 id。
        #   用途：worker 崩溃时，这些句子永远等不到 `played`/`error`
        #   ⇒ 挂在 `pending` 上**永不消失** ⇒ `drain()` 必定超时
        #   （GUI 白等 30 s / CLI 白等 120 s）。
        #   worker 重启后，未下发的（`_queue` 里的）会补发，
        #   但**已下发的那批**是真的丢了 ⇒ 必须在崩溃时清掉并计丢句。
        self._inflight: set = set()
        # 🔴 2026-10-25 §30 修：**已被主进程丢弃、但 worker 可能仍会播出来**的 jid。
        #   起因：worker 的 `synth()` 线程**可能已经越过自己的取消检查**
        #   （`tts_worker.py` L537）⇒ 主进程已按积压丢弃（`n_dropped += 1`
        #   并发了 `cancel`），worker 却仍把这句话合成并播了出来 ⇒ 主进程收到
        #   `played` ⇒ 旧实现**无条件** `n_played += 1`
        #   ⇒ 同一句被「丢了」又「播了」⇒ **双记**
        #   ⇒ `n_played + n_dropped` 比 `n_submitted` **多 1**
        #   （实测见 `results/app/test_tts_exit_played.py` 的 B 组反证）。
        #   语义：本句**其实被播出来了**（用户听到了）⇒ 收到 `played` 时
        #   **改记为「已播」**（`n_dropped -= 1` + `n_played += 1`）
        #   ⇒ 不变式 `n_played + n_dropped == n_submitted` 成立。
        #   ⚠️ 集合只在「丢句」时增长；worker 退出时会清空（见 `_on_worker_exit`）。
        self._dropped_ids: set = set()
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

    # -- 日志与故障落盘（§52）--------------------------------------------
    def _log_and_forward(self, msg):
        """先记进 `log_tail`，再转给调用方的 `on_log`。

        🔴 为什么要在 service 里留尾巴：worker 级错误的**真实原因**往往在
        错误**之前**的那几十行里（例如 CUDA 后端会先打「边车启动…」再打
        「BabelVox 引擎不可用」再打「模型加载失败」）⇒ 只保存最后一句
        等于什么都没保存。`log_tail` 让界面/日志能一起交出来。
        """
        try:
            self.log_tail.append('%s %s' % (time.strftime('%H:%M:%S'), msg))
        except Exception:
            pass
        try:
            if self._on_log_user:
                self._on_log_user(msg)
        except Exception:
            pass

    def _dump_error(self, message: str, n_tail: int = 60):
        """把 worker 级故障（含前因日志）追加到 `tts_worker_error.log`。

        ⚠️ 只在**worker 级**故障时写（句子级错误太频繁，会刷盘）。
        ⚠️ 写失败一律吞掉：诊断信息不能把语音链路带崩。
        """
        try:
            base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
            path = os.path.join(base, 'Confucius4LiveCaption',
                                'tts_worker_error.log')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tail = list(self.log_tail)[-n_tail:]
            with open(path, 'a', encoding='utf-8', newline='\n') as f:
                f.write('\n' + '=' * 78 + '\n')
                f.write('%s  worker 级故障\n' % time.strftime(
                    '%Y-%m-%d %H:%M:%S'))
                f.write('device=%s precision=%s voice=%s out_device=%s\n'
                        % (self.device, self.precision, self.voice,
                           self.out_device))
                f.write('message: %s\n' % message)
                f.write('--- 最近 %d 行日志 ---\n' % len(tail))
                f.write('\n'.join(tail) + '\n')
            self.last_error_path = path
        except Exception:
            pass

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
            # 🔴 2026-10-26 §47 修：**新 worker 起来 ⇒ 旧 jid 的标记可以清空**。
            #   `_dropped_ids` 里是「旧 worker 的 jid」⇒ 新 worker 用的是
            #   **全新的、单调递增的** jid（`_next_id`）⇒ 两边不会撞
            #   ⇒ 旧标记对新 worker **毫无意义** ⇒ 必须清，否则
            #   「关 TTS / 换设备 / 换音色」每走一次就攒一批 ⇒ 集合无界增长。
            #   ⚠️ 走到这里说明「没有活着的 proc」（上面的守卫已 return）
            #      ⇒ 旧 worker **不可能**再回事件 ⇒ 清掉是安全的。
            #   ⚠️ `close()` 路径**不走这里**（`_closing` 守卫在上面就 return）
            #      ⇒ close() 里的孤儿标记会被保留到下一次 start() 才清
            #      ⇒ 迟到 `played` 仍能正确改记（这正是 §47 要的行为）。
            self._dropped_ids.clear()
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
            # 🔴🔴 2026-10-25 §30 修：**必须清理在途句子**。
            #   旧实现在这个分支**直接 return** ⇒ `pending` / `_inflight` / `_queue`
            #   全都没清 ⇒ worker 已判死、**不会再重启**
            #   ⇒ 所有「已下发未回结果」的句子**永远等不到 `played`/`error`**
            #   ⇒ `pending` 永久悬挂 ⇒ `drain()` **必定超时**
            #   （GUI 白等 30 s / CLI 白等 120 s）
            #   ⇒ 同时 `n_played + n_dropped != n_submitted`（少算，统计失真）。
            #   实测（`results/app/test_tts_exit_played.py` A 组反证）：
            #     第 2 次崩溃后 pending=[3,4] 悬挂、`drain()` 超时 8.0 s 返 False、
            #     sum=3 != submitted=5。
            #   ⚠️ §21/§22/§29 只修了「**第一次**崩溃」路径，**第二次**崩溃漏了。
            #   ⇒ 这里与第一次崩溃路径做**同样的清理 + 计丢句**（诚实记账）。
            with self.lock:
                orphan = sorted(self.pending.keys())
                self.pending.clear()
                self._inflight.clear()
                self._dropped_ids.clear()
                n_queued = len(self._queue)
                self._queue.clear()
            if orphan or n_queued:
                self.n_dropped += len(orphan)
                self.on_log(f'[TTS] worker 判死，{len(orphan)} 句未完成'
                            f'（已计丢句），{n_queued} 句待发作废')
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
            # 🔴 2026-10-24 §22 修：**已下发给（已死）worker 的句子永远等不到
            #   `played`/`error`** ⇒ 它们会一直挂在 `pending` 上
            #   ⇒ `drain()` 必定超时（GUI 白等 30 s / CLI 白等 120 s）。
            #   ⇒ 崩溃时把这些句子清掉并**计丢句**（诚实记账）。
            lost = sorted(self._inflight)
            self._inflight.clear()
            for jid in lost:
                self.pending.pop(jid, None)
        if lost:
            self.n_dropped += len(lost)
            self.on_log(f'[TTS] worker 崩溃，{len(lost)} 句在途译文丢失（已计丢句）')
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

        🔴🔴 2026-10-25 §31 修：**关闭时必须清理在途句子并计丢句**。
          旧实现直接杀进程 ⇒ `pending` / `_inflight` / `_queue` 里
          **已提交但永远等不到 `played`/`error`** 的句子**静默消失**
          ⇒ 违反 §29 建立的**不变式** `n_played + n_dropped == n_submitted`
          （实测提交 5 / 播 2 / 丢 0 ⇒ sum=2 ≠ 5）
          ⇒ GUI/CLI 底栏「丢句 + 已播」**少于**「提交」⇒ 统计自相矛盾，
             且用户**不知道**有几句译文被丢掉了。
          ⚠️ GUI 的**三条**路径都会调 `close()`（停 TTS / 换设备 / 换音色）
             ⇒ 每走一次就丢一批在途句子的记账。
          ⇒ 现在与「崩溃清理」路径（`_on_worker_exit`）做**同样的**清理：
             清 `pending` / `_inflight` / `_queue` + **计丢句**（诚实记账）。
          ⚠️ `_queue` 里的 jid **是 `pending` 的子集**（`submit()` 先写
             `pending[jid]` 再入队）⇒ 只按 `pending` 计一次，**不重复计**。
        """
        with self.lock:
            self._closing = True
            p = self.proc
            self.proc = None
            self.state = 'idle'
            # 🔴 §31：在途句子的**唯一放弃点** ⇒ 清干净 + 计丢句
            orphan = sorted(self.pending.keys())
            self.pending.clear()
            self._inflight.clear()
            # ⚠️ **不要清 `_dropped_ids`**：worker 此刻**还活着**（quit 在后面才发）
            #    ⇒ 它可能在这段时间里回一条 `played`（积压丢弃过、但它仍播了）
            #    ⇒ `_handle_event` 要靠 `_dropped_ids` 把它**改记为「已播」**
            #    ⇒ 提前清了 ⇒ 又变成「丢了 + 播了」双记（§30 修的正是这个）。
            # 🔴🔴 2026-10-26 §47 修：**孤儿句必须登记进 `_dropped_ids`**。
            #   旧实现只清 `pending` + 计丢句，**没有登记** ⇒
            #   迟到的 `played` 到达时 `was_dropped = False`
            #   ⇒ 只 `n_played += 1`（**不减** `n_dropped`）
            #   ⇒ 同一句「丢了」又「播了」⇒ **sum 比 submitted 多 1**
            #   ⇒ 不变式 `n_played + n_dropped == n_submitted` 被破坏。
            #   实测（`results/app/app057_tts_dropped_id_registration.py` A 组）：
            #     修复前 close() 后迟到 played ⇒ sum=4 / submitted=3 ⇒ 破坏。
            #   ⇒ 这里**登记**（与 `_update_backlog` / `cancel` 同一口径）：
            #     「已计丢句」+「worker 可能仍会产出事件」。
            self._dropped_ids.update(orphan)
            n_queued = len(self._queue)
            self._queue.clear()
        if orphan:
            # ⚠️ `_queue` 的 jid ⊆ `pending` ⇒ 只按 `pending` 计一次
            self.n_dropped += len(orphan)
            self.on_log(f'[TTS] 关闭语音输出，{len(orphan)} 句未播译文作废'
                        f'（已计丢句），{n_queued} 句待发作废')
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
            dead = (self.state == 'error')
        cmd = {'cmd': 'synth', 'id': jid, 'text': text}
        if ready:
            with self.lock:
                self._inflight.add(jid)
            # 🔴🔴 2026-10-25 §29 修：**命令送不出去时必须撤账**。
            #   `_send()` 旧实现只记日志、不返回成败 ⇒ 调用方以为已下发
            #   ⇒ `_inflight` 里留下这个 jid ⇒ 但 worker 永远收不到
            #   ⇒ `pending[jid]` 永久悬挂 ⇒ `drain()` 必超时
            #   （GUI 白等 30 s / CLI 白等 120 s）。
            #   现在：`_send()` 返回成败 ⇒ 失败即撤账（清 pending + 注销
            #   `_inflight`）+ **计丢句**（诚实记账，不让这句凭空消失）。
            if not self._send(cmd):
                with self.lock:
                    self.pending.pop(jid, None)
                    self._inflight.discard(jid)
                self.n_dropped += 1
        elif dead:
            # 🔴 2026-10-24 §22 修：worker 级故障后 `state == 'error'`，
            #   此时 `_flush_queue()` **永远不会被调用**（它只在 `ready` 事件时跑）
            #   ⇒ 旧实现把命令无限堆进 `_queue` ⇒ **内存无界增长**。
            #   现在：直接计丢句并清掉 pending，**不排队**。
            with self.lock:
                self.pending.pop(jid, None)
            self.n_dropped += 1
            self.on_log('[TTS] worker 已故障（error），该句不提交（已计丢句）')
        else:
            with self.lock:
                self._queue.append(cmd)
        self._update_backlog()

    def _flush_queue(self):
        """worker 就绪后补发待发队列。"""
        with self.lock:
            q = list(self._queue)
            self._queue.clear()
        n_failed = 0
        for cmd in q:
            jid = cmd.get('id')
            if jid is not None:
                with self.lock:
                    self._inflight.add(jid)
            # 🔴 2026-10-25 §29 修：同上 —— 送不出去必须撤账 + 计丢句
            if not self._send(cmd):
                n_failed += 1
                if jid is not None:
                    with self.lock:
                        self.pending.pop(jid, None)
                        self._inflight.discard(jid)
        if n_failed:
            self.n_dropped += n_failed
            self.on_log(f'[TTS] 补发时 {n_failed} 句未能下发（已计丢句）')
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

    def _send(self, obj: dict) -> bool:
        """把一条命令写给 worker。

        🔴 2026-10-25 §29 修：**必须返回成败**。
        旧实现只记日志、不返回 ⇒ 调用方无法知道命令有没有真的送出去
        ⇒ 「已下发」的记账（`_inflight`）与事实脱节 ⇒ 句子永久悬挂
        ⇒ `drain()` 必超时。返回 False 的调用方必须**撤账**。
        """
        with self.lock:
            p = self.proc
        if p is None or p.stdin is None:
            return False
        try:
            p.stdin.write(json.dumps(obj, ensure_ascii=False) + '\n')
            p.stdin.flush()
            return True
        except Exception as e:
            self.on_log(f'[TTS] 发送失败：{e}')
            return False

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
            # 🔴 2026-10-25 §29 修：**必须同时注销 `_inflight`**。
            #   旧实现只清 `pending` ⇒ 这个 jid 永远留在 `_inflight` 里
            #   ⇒ ① 集合无界增长；② worker 崩溃时 `_on_worker_exit()`
            #   会把它**再算一次**丢句（`n_dropped` 双记）。
            self._inflight.discard(jid)
            # 🔴 2026-10-25 §30 修：登记「这句已被丢弃」。
            #   worker 可能**无视 cancel 照样播出来**（它已越过自己的取消检查）
            #   ⇒ 收到 `played` 时要**改记为已播**而不是双记。
            self._dropped_ids.add(jid)
        self.n_dropped += 1

    # -- 事件 ------------------------------------------------------------
    def _handle_event(self, msg: dict):
        kind = msg.get('kind')
        if kind == 'ready':
            self.state = 'ready'
            self.on_log(f'[TTS] 就绪：{msg.get("device")} · 音色 {msg.get("voice")}')
            self._flush_queue()
        elif kind == 'error':
            # 🔴🔴 2026-10-24 §22 修：**必须区分「句子级」与「worker 级」错误**。
            #
            # worker 的 `error` 事件有两类（见 `tts_worker.py`）：
            #   - **句子级**：带 `'id': jid`（合成失败 / 播放缓冲写满 / 播放写入失败）
            #   - **worker 级**：**不带** `'id'`（模型加载失败 / 播放设备打开失败）
            #
            # 旧实现**一律**当成 worker 级 ⇒ `self.state = 'error'`，后果有三条：
            #   ① **整个会话的语音输出永久死掉**：
            #      `active` 变 False ⇒ CLI 的 `if tts.active: tts.submit(...)`
            #      从此不再提交；GUI 的 `submit()` 里 `ready = (state=='ready')`
            #      为 False ⇒ 命令进 `_queue` ⇒ `_flush_queue()` **只在 ready
            #      事件时调用** ⇒ 永远不发出去 ⇒ 静默堆积、**一声不响**。
            #   ② `pending[jid]` **永不清除**（这条路径上 worker 不发 `played`）
            #      ⇒ `drain()` 的 `pending_n == 0` 永远为假 ⇒ **收尾必超时**
            #      （GUI 白等 30 s / CLI 白等 120 s）。
            #   ③ `_queue` **无上限** ⇒ 内存无界增长。
            #
            # 修法：带 `id` ⇒ 句子级 ⇒ 只清这一句 + 计丢句 + **服务继续**
            #       不带 `id` ⇒ worker 级 ⇒ 维持原语义（判死 + 重启由 `_read_loop` 管）。
            msg_id = msg.get('id')
            message = msg.get('message', 'unknown')
            if msg_id is not None:
                # ── 句子级：这一句失败，**不影响后面的句子** ──────────────
                with self.lock:
                    self.pending.pop(msg_id, None)
                    self._inflight.discard(msg_id)
                    # 🔴 2026-10-25 §30 修：这一句**可能早先已按积压被丢弃**
                    #   （`n_dropped` 已 +1）⇒ 这里再 +1 就**双记**。
                    #   ⇒ 已在 `_dropped_ids` 里 ⇒ 本次**不再重复计丢句**。
                    already = msg_id in self._dropped_ids
                    self._dropped_ids.discard(msg_id)
                if not already:
                    self.n_dropped += 1
                self.on_log(f'[TTS] 第 {msg_id} 句合成失败（已丢弃，语音输出继续）：'
                            f'{message}')
            else:
                # ── worker 级：模型/播放设备等整体故障 ────────────────────
                self.state = 'error'
                self.err = message
                # 🔴 §52：**留住原因**（界面/q 日志要用）+ 落盘一份，
                #   这样下次用户报「worker 故障」时能直接看到为什么
                #   （旧行为：只把 message 塞进 `self.err`，界面从不显示）。
                self.last_error = str(message)
                self._dump_error(str(message))
                # 🔴🔴 2026-10-26 §47 修：**前提事实错误** ⇒ 行为随之出错。
                #   旧注释写「worker 已死 ⇒ 在途与待发的句子都不会再有结果」
                #   ⇒ 据此做了 `self._dropped_ids.clear()`。
                #   🔴 **但 worker 级 error 的两个产地都不会让 worker 进程退出**：
                #     `tts_worker.py` L339 `播放设备打开失败`（Player 打不开）
                #     `tts_worker.py` L1004 `模型加载失败`（`_safe_load` 异常）
                #   ⇒ 主循环 `for line in sys.stdin` **继续跑**
                #   ⇒ 它仍会为在途句子回**句子级** `error`（带 id）
                #      （模型没加载 ⇒ `synth()` emit `没有可用的音色` + id）
                #      或回 `played`（设备没开 ⇒ `synth()` 仍 emit `played`）
                #   ⇒ 后果有两条：
                #     ① `_dropped_ids.clear()` **毁掉 §30 的积压丢弃标记**
                #        ⇒ 迟到的 `played` 不再被识别为「已丢弃」⇒ 双记；
                #     ② 孤儿句**只计丢句、不登记** ⇒ 迟到句子级 error 又 +1
                #        ⇒ **同一句被计两次** ⇒ sum 比 submitted 多 N。
                #   实测（`results/app/app057_tts_dropped_id_registration.py`
                #   B/C 组）：修复前 worker 级 error 后跟 3 条迟到句子级 error
                #   ⇒ sum=6 / submitted=3 ⇒ 不变式破坏。
                # ⇒ 修法（两处）：
                #   ① **不清** `_dropped_ids`（保留 §30 的标记）；
                #   ② 孤儿句**登记**进 `_dropped_ids`（与 `close()` 同一口径）
                #      ⇒ 迟到的句子级 error 命中 `already` ⇒ 不重复计丢句。
                with self.lock:
                    orphan = sorted(self.pending.keys())
                    self.pending.clear()
                    self._inflight.clear()
                    self._dropped_ids.update(orphan)
                    n_queued = len(self._queue)
                    self._queue.clear()
                if orphan or n_queued:
                    self.n_dropped += len(orphan)
                    self.on_log(f'[TTS] worker 故障，{len(orphan)} 句未完成'
                                f'（已计丢句），{n_queued} 句待发作废')
                self.on_log(f'[TTS] 错误：{self.err}')
        elif kind == 'first_packet':
            # 首包延迟：从 submit 到 worker 开始播这段
            self.first_packet_s = msg.get('latency_s')
        elif kind == 'played':
            jid = msg.get('id')
            # 🔴🔴 2026-10-25 §30 修：**这一句可能早先已被按积压丢弃**。
            #   worker 的 `synth()` 线程**可能已经越过自己的取消检查**
            #   （`tts_worker.py` L537）⇒ 主进程已 `n_dropped += 1` 并发了
            #   `cancel`，worker 却仍把这句话合成并播了出来。
            #   旧实现**无条件** `n_played += 1` ⇒ 同一句被「丢了」又「播了」
            #   ⇒ **双记** ⇒ `n_played + n_dropped` 比 `n_submitted` **多 1**
            #   ⇒ GUI/CLI 底栏「丢句 + 已播」超过「提交」⇒ 统计自相矛盾。
            #   语义修正：这一句**确实被播出来了**（用户听到了）
            #   ⇒ 改记为「已播」（`n_dropped -= 1` + `n_played += 1`）
            #   ⇒ 不变式 `n_played + n_dropped == n_submitted` 成立。
            with self.lock:
                self.pending.pop(jid, None)
                self._inflight.discard(jid)
                was_dropped = jid in self._dropped_ids
                if was_dropped:
                    self._dropped_ids.discard(jid)
            if was_dropped:
                self.n_dropped -= 1
                self.on_log(f'[TTS] 第 {jid} 句已按积压丢弃，但 worker 仍播了出来'
                            f'（改记为已播）')
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
                    # 🔴🔴 2026-10-25 §29 修：**必须同时注销 `_inflight`**。
                    #   旧实现只清 `pending` ⇒ 这些 jid 永远留在 `_inflight` 里
                    #   ⇒ ① `_inflight` 集合无界增长（长会议内存单调上升）；
                    #   ② 🔴 worker 崩溃时 `_on_worker_exit()` 会
                    #      `lost = sorted(self._inflight)` ⇒ 把**早已丢弃**的
                    #      句子**再算一次**丢句 ⇒ `n_dropped` 双记、统计虚高
                    #      （实测：真实丢 8 句 ⇒ 统计成 9）。
                    self._inflight.discard(jid)
                    # 🔴 2026-10-25 §30 修：登记「这句已被丢弃」。
                    #   worker 可能无视 cancel 照样播出来 ⇒ 收到 `played` 时
                    #   **改记为已播**（`n_dropped -= 1`），避免双记。
                    self._dropped_ids.add(jid)
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
            # 🔴 §52：worker 级故障的**原文**（None = 没有故障）
            last_error=self.last_error,
        )
