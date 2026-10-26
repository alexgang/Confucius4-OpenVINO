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

# ── APP-021③：会话日志落盘 ────────────────────────────────────────────
# 🔴🔴 起因（APP-021 证据 2）：用户那次「听不到声音」的会话**没留下任何证据**
#   —— `_ui_log()` 只写状态栏（后一条覆盖前一条），`live_caption.log` 最后
#   mtime 是 10-21，`tts_worker_error.log` 只在 worker 级 error 时才写
#   （而目标机上根本没有那个文件）⇒ **事后无法复盘**。
# ⇒ 现在：本次会话的**所有**日志（GUI + TTS worker）一律**追加**写到
#   `%LOCALAPPDATA%\Confucius4LiveCaption\session_YYYYMMDD_HHMMSS.log`
#   （**不只在 error 时写**）⇒ 用户报障时只要给这个文件即可复盘。
_SESSION_LOG_PATH = None
# 🔴 必须是 **RLock**：`append_session_log()` 持锁后会调 `session_log_path()`
#   （它内部也取这把锁）⇒ 普通 Lock 会**自死锁**。
_SESSION_LOG_LOCK = threading.RLock()

# 🔴🔴 APP-021§54.10：**会话日志去重**。
#   起因（实测 16:22 的会话日志）：同一条 worker 日志被落盘 **2~3 遍** ——
#     ① service 的 `_log_and_forward` 写一遍（tag='[TTS]'）；
#     ② GUI 的 `_ui_log` 又写一遍；
#     ③ GUI 的 TTS on_log 回调还加了 `tts: ` 前缀再写一遍。
#   ⇒ 用户报障时在 8 KB 日志里翻「真正的错误行」成本极高，
#     且**重复行会让人误判成「错误发生了 3 次」**。
#   ⇒ 现在按「剥掉包装前缀后的正文」在**短窗口**内去重。
#   ⚠️ 只影响**落盘**，界面显示与 `log_tail` 都不变。
_SESSION_DEDUP_WINDOW_S = 3.0
_SESSION_DEDUP = []          # [(monotonic, core_key)]
_SESSION_DEDUP_HITS = [0]    # 被去重掉的行数（诊断用）


def _session_log_core(msg) -> str:
    """剥掉重复包装前缀，取「正文」作为去重键。

    包装前缀有：`[TTS] ` / `[tts] ` / `tts: ` / `[TTS][stderr] ` 之类。
    ⚠️ 只用于**去重键**，**写进文件的原文不受影响**。
    """
    s = str(msg)
    prefixes = ('[TTS]', '[tts]', 'tts:', 'TTS:', '[stderr]')
    for _ in range(6):
        before = s
        t = s.lstrip()
        for p in prefixes:
            if t.startswith(p):
                t = t[len(p):].lstrip()
                break
        s = t
        if s == before:
            break
    return s


def session_log_dup_suppressed() -> int:
    """本次会话被去重掉的重复行数（诊断用）。"""
    return _SESSION_DEDUP_HITS[0]


def session_log_path() -> str:
    """本次会话的日志文件路径（进程内第一次调用时确定）。"""
    global _SESSION_LOG_PATH
    with _SESSION_LOG_LOCK:
        if _SESSION_LOG_PATH is None:
            base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
            d = os.path.join(base, 'Confucius4LiveCaption')
            try:
                os.makedirs(d, exist_ok=True)
            except Exception:
                pass
            _SESSION_LOG_PATH = os.path.join(
                d, 'session_%s.log' % time.strftime('%Y%m%d_%H%M%S'))
        return _SESSION_LOG_PATH


def append_session_log(msg: str, tag: str = ''):
    """往会话日志追加一行（**永不抛异常** ⇒ 诊断不能把功能带崩）。

    🔴 APP-021§54.10：**短窗口内去重**（同一条 worker 日志会被 service
    与 GUI 各写一遍 ⇒ 落盘出现 2~3 份重复 ⇒ 用户报障时极难定位真错误行）。
    """
    try:
        core = _session_log_core(msg)
        now = time.monotonic()
        with _SESSION_LOG_LOCK:
            # 清理窗口外的记录
            while _SESSION_DEDUP and now - _SESSION_DEDUP[0][0] > \
                    _SESSION_DEDUP_WINDOW_S:
                _SESSION_DEDUP.pop(0)
            if any(k == core for _, k in _SESSION_DEDUP):
                _SESSION_DEDUP_HITS[0] += 1
                return                      # 重复行 ⇒ 不落盘
            _SESSION_DEDUP.append((now, core))
            path = session_log_path()
            with open(path, 'a', encoding='utf-8', newline='\n') as f:
                f.write('%s %s%s\n' % (time.strftime('%H:%M:%S'),
                                      (tag + ' ') if tag else '', msg))
    except Exception:
        pass


def _decode_worker_line(b) -> str:
    """把 worker 的一行**原始字节**解成文本（**混编码**管道专用）。

    🔴🔴 APP-021§54.10：stderr 是**混编码**管道：
      ① worker 自己写的是 utf-8（env 已钉 `PYTHONIOENCODING=utf-8`）；
      ② 但 worker **spawn 的外部 exe**（cmd.exe / sox / ffmpeg）在 Windows 上
         吐的是 **GBK** 字节 ⇒ 按 utf-8 解会变成一段乱码（U+FFFD 替换字符）。
    ⇒ 判定顺序：**utf-8 严格 → gb18030 严格 → utf-8 替换**
      （utf-8 严格通过 ⇒ 一定是 utf-8；否则 gb18030 能解 ⇒ 按 GBK；
        都不行 ⇒ 最后兜底替换，**绝不抛异常**）。
    ⚠️ 必须在**字节层**判定 —— 一旦按错误编码解出 U+FFFD 就**不可恢复**。
    """
    if isinstance(b, str):
        return b
    try:
        b = bytes(b)
    except Exception:
        return ''
    b = b.rstrip(b'\r\n')
    if not b:
        return ''
    for enc in ('utf-8', 'gb18030'):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode('utf-8', 'replace')


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
                 bigvgan_ir: Optional[str] = None,
                 dump_dir: Optional[str] = None):
        self.on_log = on_log
        self.device = device
        self.voice = voice            # 'A' | 'B' | 'clone'
        self.out_device = out_device  # 输出设备名（None = 系统默认）
        self.model_dir = model_dir
        self.clone = clone            # 克隆当前说话人
        self.precision = precision    # OV 推理精度（f32 / f16）
        self.out_wav = out_wav        # 落盘模式（CLI 回放测试）
        self.bigvgan_ir = bigvgan_ir  # BigVGAN IR 覆盖（多相分解版 / NPU 窗口版）
        # 🔴 APP-021⑥：逐句 wav 落盘目录（None = 不落盘）
        self.dump_dir = dump_dir

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
        # 🔴🔴 APP-021③：「失败」是**第三个**计数（与已播/丢弃并列）。
        #   旧实现只有 已播/丢弃 ⇒ 「句子级失败」（合成失败 / 播放器不可用 /
        #   音频没播完）被**混进 n_dropped** ⇒ 界面分不清「被丢弃」和「失败」。
        self.n_failed = 0                             # 句子级失败数
        # 🔴 APP-021③：最近一条**句子级**错误原文（对话框要显示）
        self.last_sentence_error: Optional[str] = None
        # 🔴 APP-021②：最近一行的播放遥测（供界面显示 / 日志核对）
        self.last_telemetry: Optional[dict] = None

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
        # 🔴🔴 2026-10-27 §58 修：`_queue` 里**有哪些 jid**（辅助集合）。
        #   为什么要它：worker 还没 ready 时 `submit()` 把命令放进 `_queue`
        #   （**还没下发**）⇒ 此时 `cancel(jid)` 必须能把这条命令**摘掉**
        #   ⇒ 否则 ready 后 `_flush_queue()` 会把它**重新下发**
        #   ⇒ worker 真的播它 ⇒ 而主进程这边成了「幽灵在途」
        #   ⇒ worker 一崩溃 ⇒ `_inflight` 里的幽灵被当成「在途丢失」
        #   ⇒ `n_dropped` 双记 ⇒ 不变式破坏（实测 sum 4 vs submitted 3）。
        #   ⚠️ `_queue` 是 `list`（要保顺序）⇒ 摘除是 O(n) ⇒ 另用 set 记成员
        #      以便 O(1) 判断「这个 jid 在不在待发队列里」。
        self._queued_ids: set = set()

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

        🔴🔴 APP-021③：**同时追加写到会话日志文件**（不只在 error 时写）
        ⇒ 用户报障时给一个文件就能复盘整个会话。
        """
        try:
            self.log_tail.append('%s %s' % (time.strftime('%H:%M:%S'), msg))
        except Exception:
            pass
        # 🔴 APP-021§54.10：消息本身**已经带** `[TTS]` 前缀
        #   （来自 stdout 读取循环的 `self.on_log(f'[TTS] {line}')`）
        #   ⇒ 再加 tag 会写成 `[TTS] [TTS] [tts_worker] …`（双重标签）。
        #   ⇒ 只有**消息里没有** `[TTS]` 时才补 tag。
        _m = str(msg)
        _tag = '' if _m.lstrip().startswith('[TTS]') else '[TTS]'
        append_session_log(_m, tag=_tag)
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
            # 🔴🔴🔴 §53：**worker 的 stdout 编码必须钉死为 UTF-8**。
            #   起因（2026-10-26 用户实测「TTS worker 退出（rc=None），已重启过一次仍失败」）：
            #   `live_caption_app.py` L57-58 在**运行时**做
            #       os.environ.setdefault('PYTHONUTF8', '1')
            #       os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
            #   ⇒ ① 它只影响**后续新建**的子进程的 stdout 编码（worker 写 UTF-8）；
            #     ② **但它改不了本进程**的 `locale.getpreferredencoding()`
            #        （实测仍是 cp936 —— 环境变量在解释器启动**前**才生效）；
            #     ③ 而 `Popen(..., text=True)` **不带 encoding** 时，
            #        用的正是 `locale.getpreferredencoding(False)` 来解码管道
            #        ⇒ **父进程用 cp936 解码 worker 写的 UTF-8 字节**。
            #   ⇒ worker 第一条带中文/符号（`⇒` `🔴` `·`）的日志行
            #      ⇒ `UnicodeDecodeError` ⇒ 被 `_read_loop` 的 `except: pass` 吞掉
            #      ⇒ 读循环提前结束 ⇒ 走进「stdout 关闭 = worker 退出」分支
            #      ⇒ `proc.wait(timeout=2)` 超时、`poll()` 返回 **None**
            #        （**进程其实还活着**！）⇒ 报「worker 退出（rc=None）」
            #      ⇒ 重启一次后同样立刻崩 ⇒ 「已重启过一次仍失败」。
            #   ⚠️ **用户从 `Start_LiveCaption.bat` 启动时 `PYTHONUTF8=1`**
            #      （脚本里 `set PYTHONUTF8=1`）⇒ 父进程就是 UTF-8 ⇒ 不会犯。
            #      ⇒ 所以这条 bug 只在「**不经 bat、直接 python app/live_caption_app.py**」
            #      或 bat 被改过时出现 ⇒ 极难复现、极难联想。
            #   ⇒ 修法（**不依赖任何环境变量**）：`Popen` 显式 `encoding='utf-8'`
            #      + 给 worker 的 env 也钉 `PYTHONIOENCODING=utf-8`（双向锁死）。
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUTF8'] = '1'
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
            # 🔴 APP-021⑥：逐句 wav 落盘目录
            if self.dump_dir:
                cmd += ['--dump-dir', self.dump_dir]
            try:
                # 🔴 §53：`encoding='utf-8'` **必须显式写** ⇒ 不依赖 locale/环境变量
                #   （详见上面 env 那段注释里的完整根因）。
                #   `errors='replace'` 是**第二道保险**：万一还有非法字节，
                #   也不能让整个读循环崩掉（那会被误判成「worker 退出」）。
                # 🔴🔴 APP-021§54.10：**改用二进制模式**，自己逐行解码。
                #   起因（实测 16:22 会话日志）：stderr 里出现
                #     一行以 `'sox' ` 开头、后面跟一串 U+FFFD 替换字符的乱码
                #   ⇒ 那是 **cmd.exe / sox 吐的 GBK 字节**被按 utf-8 解码。
                #   ⚠️ **一旦按 utf-8 解出 U+FFFD 就不可恢复** ⇒ 必须留在字节层。
                #   ⇒ stdout（JSON 协议 + worker 自己写的日志，env 已钉 utf-8）
                #      按 utf-8 解；stderr（**混编码**：worker 的 utf-8 +
                #      外部 exe 的 GBK）按「utf-8 严格 → gb18030 严格 → utf-8 替换」
                #      三级判定逐行选编码。
                self.proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, bufsize=0, env=env)
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
        """把 worker 的 stderr 逐行转给 `on_log`（不再静默丢弃）。

        🔴🔴 APP-021§54.10：**逐行判定编码**（stderr 是**混编码**管道）：
          ① worker 自己写的是 utf-8（env 已钉 `PYTHONIOENCODING=utf-8`）；
          ② 但 worker **spawn 的外部 exe**（cmd.exe / sox / ffmpeg）在 Windows 上
             吐的是 **GBK** 字节 ⇒ 按 utf-8 解会变成一段乱码（U+FFFD 替换字符）。
          ⇒ 判定顺序：**utf-8 严格 → gb18030 严格 → utf-8 替换**
            （utf-8 严格通过 ⇒ 一定是 utf-8；否则 gb18030 能解 ⇒ 按 GBK；
              都不行 ⇒ 最后兜底替换，绝不抛异常）。
        ⚠️ 必须在**字节层**判定 —— 一旦按错误编码解出 U+FFFD 就**不可恢复**。
        """
        if proc is None or proc.stderr is None:
            return
        try:
            for raw in proc.stderr:
                line = _decode_worker_line(raw)
                if not line:
                    continue
                self.on_log(f'[TTS][stderr] {line}')
        except Exception:
            # stderr 在进程退出时关闭 → readline 抛 ValueError/IOError 属正常
            pass

    def _read_loop(self, proc):
        if proc is None:
            return
        read_error = None
        try:
            # 🔴 APP-021§54.10：stdout 现在是**二进制**流（见 start() 的 Popen）
            #   ⇒ 自己解码。worker 的 env 已钉 utf-8 ⇒ 按 utf-8 解即可；
            #   仍用 'replace' 兜底，**绝不让解码异常把读循环打断**
            #   （那会被误判成「worker 退出」，见下面 except 里的完整根因）。
            for raw in proc.stdout:
                line = (raw.decode('utf-8', 'replace')
                        if isinstance(raw, (bytes, bytearray))
                        else str(raw)).strip()
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
        except Exception as e:
            # 🔴🔴🔴 §53：**读循环异常不许被当成「worker 退出」**。
            #   旧实现是 `except: pass` ⇒ 解码异常（UnicodeDecodeError）
            #   被**静默吞掉** ⇒ 循环提前结束 ⇒ 直接落到下面
            #   「stdout 关闭 = worker 退出」的收尾逻辑
            #   ⇒ `proc.wait(timeout=2)` 超时 + `poll()` 返回 None
            #   ⇒ 报「worker 退出（rc=None）」——**而进程其实还活着**。
            #   ⇒ 这就是 §53 用户实测那条错误的真身：
            #      「TTS worker 退出（rc=None），已重启过一次仍失败」。
            # ⇒ 修法：**区分两类退出** ——
            #   ① 读循环**异常**结束 ⇒ **不是进程退出** ⇒ 不判死、不重启，
            #      而是记下原因 + 继续用**另一个线程**接管（或直接判 error 并带原因）。
            #      既然协议已经坏掉，最诚实的做法是：判 error + **带原因**，
            #      这样界面能显示「解码失败」而不是含混的「worker 退出」。
            #   ② 正常 EOF（`for line in stdout` 正常结束）⇒ 才是进程退出。
            read_error = e
            self.on_log(f'[TTS] 🔴 读取 worker 输出失败：'
                        f'{type(e).__name__}: {e}')
        # stdout 关闭 = worker 退出
        # 🔴 §21：`poll()` 在进程刚死时可能仍返回 None（Windows 上退出码还没回填）
        #   ⇒ 旧代码把 `rc=None` 记进日志，且**判断不到「真的死了」**。
        #   这里显式 `wait()` 拿到真实退出码。
        try:
            rc = proc.wait(timeout=2)
        except Exception:
            rc = proc.poll()
        # 🔴🔴 §53：**读循环异常 ⇒ 进程不一定死了** ⇒ 先确认它到底死没死。
        #   `poll()` 返回 None ⇒ **还活着** ⇒ 绝不判死（否则会误杀一个健康 worker），
        #   直接标 error 并**带上真实原因**（解码错误），让界面/日志说人话。
        if read_error is not None and rc is None:
            self.state = 'error'
            self.err = RuntimeError(
                f'读取 TTS worker 输出失败：{type(read_error).__name__}: '
                f'{read_error}')
            self.last_error = str(self.err)
            self._dump_error(str(self.err))
            return
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
                # 🔴 2026-10-27 §58：待发队列作废 ⇒ 成员集合也要清
                self._queued_ids.clear()
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
            # 🔴 2026-10-27 §58：待发队列作废 ⇒ 成员集合也要清
            self._queued_ids.clear()
        if orphan:
            # ⚠️ `_queue` 的 jid ⊆ `pending` ⇒ 只按 `pending` 计一次
            self.n_dropped += len(orphan)
            self.on_log(f'[TTS] 关闭语音输出，{len(orphan)} 句未播译文作废'
                        f'（已计丢句），{n_queued} 句待发作废')
        try:
            if p is not None:
                try:
                    # 🔴 APP-021§54.10：二进制管道 ⇒ 写 bytes（兼容旧文本管道）
                    _q = (json.dumps({'cmd': 'quit'}) + '\n').encode('utf-8')
                    try:
                        p.stdin.write(_q)
                    except TypeError:
                        p.stdin.write(_q.decode('utf-8'))
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
    def submit(self, text: str, seg: Optional[int] = None,
               spk=None, spk_conf=None):
        """提交一条**定稿译文**。

        ⚠️ worker 还没 `ready` 时**不能直接下发** —— worker 的 stdin
        在模型加载完成前也在收命令，但那时音色条件还没加载好，
        合成会失败。所以这里**先入待发队列**，等 `ready` 事件后补发。

        🔴🔴 APP-022：`spk` / `spk_conf` **接口预留**（当前恒为 None）。
        ⇒ 透传给 worker 的 `synth` 命令（worker 侧**同样只预留不使用**）。
        ⇒ **不改变现有行为**：spk 为 None 时命令体与改造前逐字一致。
        """
        text = (text or '').strip()
        if not text:
            return
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]
        # 🔴🔴🔴 2026-10-27 §59 修：**「读状态」与「登记在途」必须在同一把锁内**。
        #
        #   旧实现（§29~§58 一直如此）分成了**两个临界区**：
        #       ① 锁内读 `state` → `ready` / `dead`
        #       ② 出锁后再 `with self.lock: self._inflight.add(jid)`
        #   ⇒ ①与②之间，worker 级 error 的「孤儿清理」可能整段跑掉
        #      （`pending.clear()` + `_inflight.clear()` + 计丢句）
        #      ⇒ ②再把 jid 加回 `_inflight` ⇒ **幽灵在途句**
        #      ⇒ worker 崩溃时 `lost = sorted(self._inflight)` 把它算成
        #         「在途丢失」⇒ `n_dropped` 双记 ⇒ 不变式破坏。
        #
        #   ⇒ 现在：读状态 + 登记在途 / 决定「直接下发 vs 入队」**一次做完**。
        with self.lock:
            jid = self._next_id
            self._next_id += 1
            self.pending[jid] = dict(seg=seg, text=text, t=time.perf_counter())
            self.n_submitted += 1
            st = self.state
            if st == 'ready':
                # worker 已 ready ⇒ 立刻下发 ⇒ **同时**登记在途
                # （与 `pending[jid]` 的写入在同一临界区 ⇒ 孤儿清理看不到半状态）
                self._inflight.add(jid)
                action = 'send'
            elif st == 'error':
                action = 'dead'
            else:
                action = 'queue'
        cmd = {'cmd': 'synth', 'id': jid, 'text': text}
        # 🔴🔴 APP-022：说话人字段**只在有值时加** ⇒ 无 spk 时命令体不变
        if spk is not None:
            cmd['spk'] = spk
            cmd['spk_conf'] = spk_conf
        if action == 'send':
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
        elif action == 'dead':
            # 🔴 2026-10-24 §22 修：worker 级故障后 `state == 'error'`，
            #   此时 `_flush_queue()` **永远不会被调用**（它只在 `ready` 事件时跑）
            #   ⇒ 旧实现把命令无限堆进 `_queue` ⇒ **内存无界增长**。
            #   现在：直接计丢句并清掉 pending，**不排队**。
            with self.lock:
                self.pending.pop(jid, None)
            self.n_dropped += 1
            self.on_log('[TTS] worker 已故障（error），该句不提交（已计丢句）')
        else:
            # ── worker 还没 ready ⇒ 入待发队列 ──────────────────────────
            was_pending = False
            with self.lock:
                # 🔴🔴🔴 2026-10-27 §59 修：**丢唤醒竞态（lost wakeup）**。
                #   `ready` 事件可能在上面那次读 `state` 与这里之间到达：
                #       T_app : 锁内读到 state='loading' ⇒ action='queue'
                #       T_evt : `self.state = 'ready'` ⇒ `_flush_queue()`
                #               ⇒ 快照 `_queue`（**当时还是空的**）⇒ 无事可做
                #       T_app : 入队 ⇒ 命令**留在队列里**
                #   ⇒ worker **已经 ready** ⇒ **再也不会有第二个 `ready` 事件**
                #      ⇒ `_flush_queue()` 永远不会再跑
                #      ⇒ 这条命令**永远发不出去**
                #      ⇒ `pending[jid]` **永久悬挂** ⇒ `drain()` 必超时
                #      ⇒ 这句译文**永远不会被朗读**。
                #   ⚠️ 这与 §58 的「幽灵在途句」是**两个不同的洞**：
                #      §58 = 命令**被下发**了但主进程记错；
                #      §59 = 命令**根本没被下发**就永久滞留。
                #   ⇒ 修法：**入队前在同一把锁内复查 `state`**。
                #      复查与入队在同一临界区 ⇒ 与 `_flush_queue()` 的快照互斥
                #      ⇒ **不可能两边都错过**：
                #        · 复查看到 'ready'  ⇒ `_flush_queue()` 的快照要么还没取
                #          （那就一定取得到我们的命令），要么已经取完
                #          （那它看到的是空队列 ⇒ 我们必须**自己**下发）；
                #        · 复查看到非 'ready' ⇒ `_flush_queue()` 必定在我们之后跑
                #          （它读 `state` 之前我们已入队）⇒ 一定取得到我们的命令。
                if self.state == 'ready':
                    # 已经 ready ⇒ **不能**再入队（会永远滞留）
                    # ⇒ 改为直接下发（与 `action == 'send'` 同一条路径）
                    self._inflight.add(jid)
                    direct = True
                    dead = False
                elif self.state == 'error':
                    # 🔴🔴 2026-10-27 §59 修：**worker 级故障时也不能入队**。
                    #   §22 的原意是「`state == 'error'` 时不排队」
                    #   （否则 `_queue` 无上限增长 ⇒ 内存无界）。
                    #   ⚠️ 但旧实现只在**第一次**临界区读状态 ⇒ 若故障恰好
                    #      落在「读状态」与「入队」之间 ⇒ 这句**照样入队**
                    #      ⇒ 而 `_flush_queue()` 只在 `ready` 时跑
                    #      ⇒ worker 判死后**永远不会再 ready**（除非重启）
                    #      ⇒ 这句**永远滞留** ⇒ `_queue` 无上限增长。
                    #   ⇒ 现在在同一把锁内复查 ⇒ 故障期间**直接定案**。
                    #   ⚠️ 计数口径：`pending.pop` 返回 None ⇒ 这句**已被别处
                    #      定案**（多半是 worker 级 error 的「孤儿清理」
                    #      已经把它计过丢句）⇒ 本次**不再重复计**。
                    in_pending = self.pending.pop(jid, None) is not None
                    direct = False
                    dead = True
                    was_pending = in_pending
                else:
                    self._queue.append(cmd)
                    # 🔴🔴 2026-10-27 §58 修：登记「这句在待发队列里」
                    #   ⇒ `cancel()` 才能把它摘掉（见 cancel() 里的说明）。
                    self._queued_ids.add(jid)
                    direct = False
                    dead = False
            if direct:
                if not self._send(cmd):
                    with self.lock:
                        self.pending.pop(jid, None)
                        self._inflight.discard(jid)
                    self.n_dropped += 1
            elif dead:
                # ⚠️ 只有「这句此刻确实还在 `pending` 里」才计丢句
                #   （否则会与「孤儿清理」的计数重复 ⇒ 双记）。
                if was_pending:
                    self.n_dropped += 1
                self.on_log('[TTS] worker 已故障（error），该句不提交（已计丢句）')
        self._update_backlog()

    def _flush_queue(self):
        """worker 就绪后补发待发队列。"""
        with self.lock:
            q = list(self._queue)
            self._queue.clear()
            self._queued_ids.clear()
        n_failed = 0
        n_skipped = 0
        for cmd in q:
            jid = cmd.get('id')
            # 🔴🔴 2026-10-27 §58 修：**跳过已被 cancel 的句子**。
            #   worker 还没 ready 期间 `cancel(jid)` 会把这条命令从 `_queue`
            #   摘掉（见 cancel()）⇒ 正常情况下这里遇不到；
            #   但**两道保险**：即使 `_queue` 与 `pending` 之间出现任何
            #   不一致（其它路径清过 `pending`），也**绝不能**把一句
            #   已经「定了案（已丢）」的译文**重新下发** ⇒
            #   worker 会真的播它 ⇒ 主进程这边变成「幽灵在途」
            #   ⇒ worker 一崩溃 ⇒ `n_dropped` 双记 ⇒ 不变式破坏。
            #   ⇒ 判据 = 「这句已不在 `pending` 里」⇒ 它已被别处定案。
            if jid is not None:
                with self.lock:
                    if jid not in self.pending:
                        n_skipped += 1
                        continue
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
        if n_skipped:
            self.on_log(f'[TTS] 补发时跳过 {n_skipped} 句（已被丢弃，不重新下发）')
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
            # 🔴 APP-021§54.10：worker 现在跑在**二进制**管道模式
            #   （见 start() 的 Popen）⇒ 写 stdin 也必须写 **bytes**。
            #   ⚠️ 写 str 会抛 TypeError ⇒ 之前会表现为「发送失败」。
            line = (json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8')
            try:
                p.stdin.write(line)
            except TypeError:
                # 兼容旧的文本模式管道（例如外部注入的假 proc）
                p.stdin.write(line.decode('utf-8'))
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

        🔴🔴 2026-10-26 §57 修：**同一个 jid 的丢弃计数只能加一次**。
        旧实现**无条件** `n_dropped += 1` ⇒ 只要同一句被 cancel 两次就双记。
        真实触发路径（不是理论构造）：
        `live_caption/offline_reader.py` 的 `OfflineReader.stop()` 与 `_loop()`
        的 `finally` **各调一次** `_cancel_pending()`；
        而 `_cancel_pending()` 是「**锁内快照 victims → 锁外逐个 `svc.cancel()`**」
        ⇒ 两个线程的快照可重叠 ⇒ 同一 jid 被 `cancel()` 两次
        ⇒ 实测 3 句提交却报 `n_dropped=6` ⇒ 不变式
          `n_played + n_dropped + len(pending) == n_submitted` 被破坏。
        🔴 且**双记无法被 §30 的「改记」自愈**：迟到 `played` 只能 `n_dropped -= 1`
        ⇒ 减回 1 仍与 `submitted` 不符 ⇒ 必须在本方法内杜绝双记。

        ⇒ 修法：**只有「这一句此刻确实还在途（仍在 `pending` 里）」的那一次
        cancel 才计丢句**。判定与摘除放在**同一个锁内临界区**（原子）。
        第二次 cancel 时该句已不在 `pending` ⇒ 已由第一次 cancel 定案
        ⇒ 本次**不再重复计丢句**、也**不再重复登记** `_dropped_ids`。

        🔴🔴 2026-10-27 §58 修：**还必须把这一句从「待发队列 `_queue`」里摘掉**。
        旧实现只清 `pending` / `_inflight` ⇒ **漏了 `_queue`** ⇒ 于是有两条真缺陷：
        ① 🔴 **幽灵在途句**：worker **还没 ready** 时（模型加载中，实测 4~24 s）
           `submit()` 把命令**放进 `_queue`**（`tts_service.py` L762）⇒
           此时 `cancel(jid)` 只清了 `pending` ⇒ **命令仍留在 `_queue` 里**
           ⇒ worker ready 后 `_flush_queue()` **把它重新下发**
           ⇒ worker 按 `synth` 正常合成并**真的播出来**
           ⇒ 但主进程这边 `_inflight` 里多了一个**从未真正在途**的 jid
           ⇒ ② 🔴 **崩溃时双记**：worker 崩溃时 `_on_worker_exit()` 取
           `lost = sorted(self._inflight)` ⇒ **把幽灵 jid 也算成「在途丢失」**
           ⇒ `n_dropped += len(lost)` ⇒ **同一句被丢了两次**
           ⇒ 不变式 `n_played + n_dropped + len(pending) == n_submitted` 被破坏。
        实测（`results/app/app088_tts_cancel_queue_ghost.py` A 组）：
          3 句提交 → cancel 第 0 句 → ready 后 `_inflight=[0]`（幽灵）
          → worker 崩溃 ⇒ `n_dropped=2 / n_played=2 / submitted=3`
          ⇒ **sum(4) ≠ submitted(3)** ⇒ 不变式破坏。
        ⚠️ 这与 §57 的「同一 jid 被 cancel 两次」是**两个不同的破口**：
          §57 修的是「同一句被计两次」，本条修的是「**从未在途的句被当成在途丢失**」。
        ⇒ 修法：**在同一把锁内**把 jid 从 `_queue` 里摘掉（§58）。
        """
        self._send({'cmd': 'cancel', 'id': jid})
        with self.lock:
            # 🔴 §57：**原子地**判定「这句是否还在途」并摘出 `pending`。
            #   `pop` 返回被摘下的值 ⇒ `None` ⇒ 这句**已不在途**。
            was_pending = self.pending.pop(jid, None) is not None
            # 🔴 2026-10-25 §29 修：**必须同时注销 `_inflight`**。
            #   旧实现只清 `pending` ⇒ 这个 jid 永远留在 `_inflight` 里
            #   ⇒ ① 集合无界增长；② worker 崩溃时 `_on_worker_exit()`
            #   会把它**再算一次**丢句（`n_dropped` 双记）。
            self._inflight.discard(jid)
            # 🔴🔴 2026-10-27 §58 修：**必须同时从「待发队列」里摘掉**。
            #   worker 还没 ready 时命令在 `_queue` 里（还没下发）
            #   ⇒ 不摘 ⇒ ready 后会被 `_flush_queue()` 重新下发
            #   ⇒ worker 真的会播它 ⇒ 而主进程这边是「幽灵在途」
            #   ⇒ worker 一崩溃 ⇒ 它被当成「在途丢失」⇒ `n_dropped` 双记。
            #   ⚠️ 与 `pending`/`_inflight` 在**同一把锁内**完成 ⇒ 原子。
            if jid in self._queued_ids:
                self._queued_ids.discard(jid)
                self._queue = [c for c in self._queue if c.get('id') != jid]
            if was_pending:
                # 🔴 2026-10-25 §30 修：登记「这句已被丢弃」。
                #   worker 可能**无视 cancel 照样播出来**（它已越过自己的取消检查）
                #   ⇒ 收到 `played` 时要**改记为已播**而不是双记。
                self._dropped_ids.add(jid)
        # 🔴🔴 §57：**只有真正在途的那一次才计丢句**。
        #   ⚠️ 不在途 ⇒ 这句已被别的路径定案（已播 / 已丢 / 已失败）
        #   ⇒ 这里再 +1 就是**双记**（不变式 sum > submitted）。
        #   ⚠️ 且**不得**再登记 `_dropped_ids`：若这句其实**已被播**
        #   （`n_played` 已 +1），登记后迟到的重复 `played` 会被误判为
        #   「已丢弃」⇒ `n_dropped -= 1` ⇒ `n_dropped` 变负 ⇒ 账本更糟。
        if was_pending:
            self.n_dropped += 1

    # -- 事件 ------------------------------------------------------------
    def _handle_event(self, msg: dict):
        kind = msg.get('kind')
        if kind == 'ready':
            # 🔴🔴 2026-10-27 §59 修：**状态转换必须在锁内完成**。
            #   旧实现 `self.state = 'ready'` 在锁外 ⇒ 与 `submit()` 的
            #   「入队临界区」之间存在窗口 ⇒ `submit()` 可能读到 'loading'
            #   ⇒ 入队 ⇒ 而 `_flush_queue()` 的快照**已经取过**（当时为空）
            #   ⇒ 命令**永久滞留**在 `_queue` 里（worker 已 ready，不会再有
            #     第二个 ready 事件 ⇒ 永远不会被下发）⇒ 丢唤醒竞态。
            #   ⇒ 现在：锁内置为 'ready' ⇒ 与 `submit()` 的复查互斥
            #      ⇒ 「入队」与「补发」**不可能两边都错过**。
            with self.lock:
                self.state = 'ready'
            self.on_log(f'[TTS] 就绪：{msg.get("device")} · 音色 {msg.get("voice")}')
            # ⚠️ `_flush_queue()` 自己会取锁 ⇒ **必须在上面那个 with 块之外**调用
            #   （`self.lock` 是**非**可重入的 `threading.Lock` ⇒ 嵌套会自死锁）。
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
                # 🔴🔴 APP-021③：**句子级失败单独计数**（`n_failed`）。
                #   旧行为：句子级 error 被混进 `n_dropped` ⇒ 界面分不清
                #   「这句被丢弃（积压超限）」和「这句失败了（合成/播放问题）」。
                #   ⇒ 现在分开：已播 / 丢句 / 失败 三个数（对话框要显示）。
                #   ⚠️ **口径**：不变式仍然是
                #     `n_played + n_dropped == n_submitted`（**不动**，
                #     §29/§30/§47 建立的账本口径不能被这次改动破坏）
                #     ⇒ `n_failed` 是 `n_dropped` 的**子集**
                #     （只有「既没被积压丢、又失败」的那句才 +1）
                #     ⇒ 界面上的三个数是「已播 / 丢句(含失败) / 失败(其中)」。
                if not already:
                    self.n_failed += 1
                self.last_sentence_error = ('第 %s 句：%s' % (msg_id, message))
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
                    # 🔴 2026-10-27 §58：待发队列作废 ⇒ 成员集合也要清
                    self._queued_ids.clear()
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
            # 🔴🔴 APP-021②：`played` 现在带**每句遥测** ⇒ 存下来供界面显示，
            #   并**追加进会话日志**（复盘时能看到「这一句到底播了没有」）。
            #   ⚠️ 语义（APP-021①）：`played` 现在**只在音频已被播放回调
            #   全部取走之后**才发 ⇒ 它**才真的代表「出声了」**。
            tel = msg.get('telemetry')
            if tel:
                self.last_telemetry = tel
                self.on_log('[TTS] 遥测 id=%s peak=%s rms_dbfs=%s '
                            'read_delta=%s consumed=%s%s'
                            % (jid, tel.get('peak'), tel.get('rms_dbfs'),
                               tel.get('read_delta'), tel.get('consumed'),
                               (' [静音合成]' if tel.get('silent_synth') else '')))
        elif kind == 'written':
            # 🔴 APP-021③：本句音频已**全部写进**环形缓冲（**还没播完**）。
            #   ⇒ 主进程用它更新**真实积压**（缓冲里的音频只剩几秒待播，
            #      不是整句时长）⇒ 避免因 `played` 推迟而**高估积压**
            #      ⇒ 避免连续会议里多丢句。
            #   ⚠️ **不动记账**：这句仍然算「在途」（还没出声），
            #      `n_played` 只有真的 `played` 才 +1。
            jid = msg.get('id')
            with self.lock:
                it = self.pending.get(jid)
                if it is not None:
                    it['written'] = True
                    it['dur_s'] = msg.get('dur_s')
            self._update_backlog()
        elif kind == 'test_tone':
            # 🔴 APP-021④：「测试声音」的结果回传
            ok = bool(msg.get('ok'))
            tel = msg.get('telemetry') or {}
            self.last_telemetry = tel
            self.on_log('[TTS] 测试声音：%s（%s，回调 +%s / 已读 +%s）'
                        % ('成功' if ok else '失败',
                           msg.get('message', ''),
                           tel.get('cb_delta', '-'), tel.get('read_delta', '-')))
        elif kind == 'telemetry':
            # 🔴 APP-021②：拉取到的遥测快照
            tel = msg.get('telemetry') or {}
            self.last_telemetry = tel
            self.on_log('[TTS] 遥测快照：%s' % tel)
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

    # 🔴 APP-021④：让 GUI 能触发「测试声音」（走**同一个 worker 的 Player**）。
    def test_tone(self, freq: float = 440.0, dur_s: float = 1.0,
                  amp: float = 0.3) -> bool:
        """发一条 `test_tone` 指令给 worker。

        返回 True = 指令**已下发**（不代表已播完 —— 结果在 `test_tone` 事件里）。
        """
        return self._send({'cmd': 'test_tone', 'freq': freq,
                           'dur_s': dur_s, 'amp': amp})

    # 🔴 APP-021②：拉一次播放器遥测（不含模型）。
    def request_telemetry(self) -> bool:
        return self._send({'cmd': 'telemetry'})

    # 🔴 APP-021⑥：**运行时**开关逐句 wav 落盘（worker 已经在跑也能改）。
    def set_dump_dir(self, path: Optional[str]) -> bool:
        return self._send({'cmd': 'set_dump_dir', 'dir': path or ''})

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
            # 🔴 APP-021③：**音频已写进环形缓冲**的句子 ⇒ 用**真实时长**
            #   且**只算还没播的那部分**（环形缓冲容量 3 s ⇒ 最多 3 s 待播）
            #   ⇒ 否则会把这句的**整段时长**都算进积压 ⇒ 高估 ⇒ 多丢句。
            if it.get('written'):
                try:
                    d = float(it.get('dur_s') or 0.0)
                except Exception:
                    d = 0.0
                est += min(3.0, d)
                continue
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
                    # 🔴 APP-021③：已写进缓冲的句子 ⇒ 剩余待播 ≤ 3 s
                    if it.get('written'):
                        try:
                            d = float(it.get('dur_s') or 0.0)
                        except Exception:
                            d = 0.0
                        acc += min(3.0, d)
                        drop_ids.append(jid)
                        continue
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
            # 🔴 APP-021③：三个数（已播 / 丢句 / 失败）+ 最近一条句子级错误
            n_failed=self.n_failed,
            last_sentence_error=self.last_sentence_error,
            # 🔴 APP-021②：最近一行的播放遥测
            last_telemetry=self.last_telemetry,
            # 🔴 APP-021③：会话日志路径（用户报障时给这一个文件即可复盘）
            session_log=session_log_path(),
        )
