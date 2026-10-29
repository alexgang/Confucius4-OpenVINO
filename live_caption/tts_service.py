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


# 🔴🔴🔴 APP-023 根因 1（后半段）：拉 worker 要用**真实解释器**。
#   旧实现：`cmd = [sys.executable, _WORKER, ...]`。
#   ⇒ 用户的启动路径是**桌面快捷方式 → `.venv\Scripts\pythonw.exe`**
#     （**venv 重定向器** + GUI 子系统、无控制台）
#   ⇒ `sys.executable` 拿到的是**那个 pythonw** ⇒ worker 自己**也没有控制台**
#     ⇒ worker 内部任何「`stderr=None` 走 `GetStdHandle(STD_ERROR_HANDLE)`」
#     的 spawn 都会在 `DuplicateHandle` 处炸 **WinError 50**
#     （实测 08:56 会话日志：CUDA 边车就是这么起不来的）。
#   ⇒ 修法：优先用 `sys._base_executable`（**真实的基础解释器**，
#     绕过 venv 的重定向器）；取不到就退回 `sys.executable`。
#   ⚠️ **必须仍是同一个解释器体系**：`_base_executable` 与 `sys.executable`
#     指向同一个 base 安装 ⇒ venv 的 site-packages 仍会生效（靠
#     `pyvenv.cfg` + `sys.path` 的 `''`/venv 前缀），**不会**跑成裸解释器。
#   ⚠️ 若 base 解释器是 `pythonw.exe`（无控制台）⇒ worker 自己也会缺 std 句柄
#     ⇒ 下面再配 `CREATE_NO_WINDOW`（**不创建**控制台，但**不继承**伪句柄）。
def _worker_python() -> str:
    """拉 TTS worker 用的解释器路径（APP-023）。

    🔴🔴 **为什么不能直接用 `sys._base_executable`**（本机实测）：
      `sys._base_executable` 指向**基础安装**的 python.exe
      （venv 下 = `AppData\\...\\Python312\\python.exe`）
      ⇒ 直接跑它 ⇒ `sys.prefix` 变成**基础安装** ⇒ **venv 的 site-packages
      整个失效**（实测 numpy 由 venv 的 **2.4.6** 变成 base 的 **2.5.4**）
      ⇒ worker 会 import 不到本项目的包 ⇒ **比原来更糟**。

    ⇒ 正确做法：**同一个环境，但换成带控制台的解释器**
      （只把 `pythonw.exe` 换成同目录的 `python.exe`）：
      - 仍是同一个 venv / 同一个客户包 ⇒ site-packages 不变；
      - 控制台子系统 ⇒ `GetStdHandle` 拿到**真实** std 句柄
        （pythonw 是 GUI 子系统、无控制台 ⇒ 三条 std 都是伪句柄/NULL）。

    候选顺序：
      ① `LIVECAP_TTS_PY`（显式指定，最高优先）；
      ② 当前解释器同目录的 `python.exe`（当前是 pythonw 时）；
      ③ 客户包 `<包根>/python/python.exe`；
      ④ 退回 `sys.executable`。
    """
    env_py = os.environ.get('LIVECAP_TTS_PY')
    if env_py and os.path.isfile(env_py):
        return env_py
    exe = sys.executable or ''
    if os.path.basename(exe).lower() in ('pythonw.exe', 'pythonw'):
        # ② 同目录的控制台解释器（保住 venv / 客户包的 site-packages）
        alt = os.path.join(os.path.dirname(exe), 'python.exe')
        if os.path.isfile(alt):
            return alt
        # ③ 客户包内解释器（`<包根>/python/python.exe`）
        pkg_py = os.path.join(os.path.dirname(_HERE), 'python', 'python.exe')
        if os.path.isfile(pkg_py):
            return pkg_py
    return exe


def _no_window_flag() -> dict:
    """🔴 APP-023：worker **不弹黑框**（用户走 pythonw 快捷方式启动）。"""
    if os.name != 'nt':
        return {}
    return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)}

# 🔴🔴🔴 APP-028②：**积压上限已取消**（不再丢句）。
#   保留这个名字（外部脚本 / 文档可能引用）⇒ 但**只作为「滞后告警阈值」**：
#   超过它 ⇒ 只在日志里提示「语音滞后 X 秒」⇒ **绝不丢句**。
#   ⚠️ APP-027④ 的丢句实现已**整段删除**（见 `_update_backlog`）。
BACKLOG_MAX_S = float(os.environ.get('LIVECAP_TTS_BACKLOG_MAX', '8'))
# 🔴 APP-028②：语音滞后的**告警阈值**（秒）—— 只提示、不丢句。
LAG_WARN_S = float(os.environ.get('LIVECAP_TTS_LAG_WARN', '8'))
# 🔴 APP-028②：滞后告警的**冷却**（秒）—— 防止刷屏
LAG_WARN_COOLDOWN_S = float(os.environ.get('LIVECAP_TTS_LAG_WARN_CD', '30'))
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
                 dump_dir: Optional[str] = None,
                 jsonl_path: Optional[str] = None):
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
        # 🔴🔴🔴 **逐句遥测 JSONL 路径**（APP-027 V1/V2 验收用）。
        #   ⚠️ **为什么必须显式传**：worker 侧 `_jsonl_path` **只在有 `--out-wav` 时**
        #   才被自动设成 `<out-wav>.tts.jsonl`（`tts_worker.py` L3179-3182）
        #   ⇒ **真实播放路径（不带 `--out-wav`）本来拿不到逐句 JSONL**
        #   ⇒ 而 APP-027 的验收字段（`synth_rtf` / `prebuffer_s` /
        #     `underflow_in_sentence` / `queue_peak_s` …）**只在 JSONL 里**
        #   ⇒ 不传这个 ⇒ 真实播放路径的验收**字段全缺**。
        self.jsonl_path = jsonl_path

        self.proc: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        # 🔴🔴🔴 APP-027⑤：**stdin 写锁**（命令**串行化**）
        #   起因：`set_clone_pcm()` 由**会话线程**（`Session._loop` → `on_audio`）
        #   调用，而 `submit()` / `cancel()` 由 **GUI 主线程**调用
        #   ⇒ 两个线程**并发 write(同一 pipe)** ⇒ 命令行**交错**
        #   ⇒ worker 收到的 JSON 变成半行拼接 ⇒ **解析失败 / 丢命令**。
        #   ⚠️ `self.lock` **不能**复用（它保护的是 `pending` 等状态，
        #      且 `_send()` 里已经 `with self.lock` 取过 proc ⇒ 非可重入会自死锁）。
        self._stdin_wlock = threading.Lock()
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
        # 🔁§99（断链 C）：**worker 的说话人音色登记结果**
        #   主进程不能「发命令就算成功」，必须等 worker 确认。
        #   而之前 **没有任何分派分支** ⇒ 已经发出去的命令也标成「成功」。
        self._spk_voice_status = {}

        # 统计
        self.first_packet_s: Optional[float] = None   # 首包延迟
        # 🔴🔴 APP-024①：**首包的两段拆分**（最近一句）
        #   `queued_s` = 命令写进 worker stdin − submit（**主进程**时钟，同源可比）
        #   `synth_s`  = worker 内部「取到命令 → 第一块音频到达」（worker 时钟）
        #   ⚠️ 两个数来自**两个进程** ⇒ 只能**各自解释**，不能跨进程相减。
        self.first_packet_parts: Optional[dict] = None
        self.backlog_s = 0.0                          # 当前积压
        self.max_backlog_s = 0.0                     # 最大积压
        self.n_dropped = 0                            # 丢句数
        self.n_played = 0                             # 已播句数
        self.n_submitted = 0
        # 🔴🔴 APP-021③：「失败」是**第三个**计数（与已播/丢弃并列）。
        #   旧实现只有 已播/丢弃 ⇒ 「句子级失败」（合成失败 / 播放器不可用 /
        #   音频没播完）被**混进 n_dropped** ⇒ 界面分不清「被丢弃」和「失败」。
        self.n_failed = 0                             # 句子级失败数
        # 🔴🔴🔴 APP-036 C4：**关闭时作废的句子数**（`n_discard_on_close`）
        #   reviewer APP-036 C4 原话：
        #     「CLI 收尾的统计行在 `close()` 之前打印（L4205 drain(120) → stats
        #       → close），所以 §82 那次『丢弃 0』实际作废了 51 句。
        #       改成 close() 之后再打印一次最终统计，或者把 drain 超时设为
        #       max(120, 1.5×当前积压)，并在报告里列出 `n_discard_on_close`。」
        #   ⇒ 这里**单独计数**（不混进 `n_dropped`）⇒ 验收脚本可独立核对。
        self.n_discard_on_close = 0
        # 🔴🔴🔴 APP-037 C：**空句数**（句首标点剥离后为空 ⇒ 未合成）
        #   ⇒ **既不播也不丢**（reviewer 明文「不计丢句」）
        #   ⇒ 不变式变成三段式：
        #     `n_played + n_dropped + n_empty == n_submitted`
        self.n_empty = 0
        # 🔴🔴🔴 APP-036 C3：**结尾滞后**（真实定义）
        #   reviewer 原话：「`end_lag_s=0.0` 是 drain 之后取的值，没有意义。
        #     新增 `end_lag_s = 最后一句播完（或写完）的时刻 − 源音频结束时刻`」
        #   ⚠️ **跨进程时钟不可比** ⇒ 只能由**主进程**在收到最后一条
        #     `played` / `written` 时，用**主进程自己的时钟**与
        #     「源音频结束时刻」相减 ⇒ 由 App 侧在 `set_source_end()` 里打点。
        self._source_end_t: Optional[float] = None
        self._last_out_t: Optional[float] = None
        self.end_lag_s: Optional[float] = None
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
        # ── 🔴🔴🔴 APP-027④：**三段式积压**需要的、由 worker 报上来的状态 ──
        #   ① `_ring_backlog_s`：环形缓冲里**实际剩下**的样本时长（只算一次）
        #   ② `_synth_jid` / `_synth_rem_s`：正在合成的句子及其剩余预计时长
        #   ③ `_wqueue_ids` / `_queue_est_s`：worker FIFO 里排队的句子及估时
        #   ④ `_sec_per_char`：worker 实测的「音频秒/字」（估时校准）
        self._ring_backlog_s = 0.0
        self._synth_jid = None
        self._synth_rem_s = 0.0
        self._wqueue_ids: List = []
        self._queue_est_s: dict = {}
        self._sec_per_char = None
        # 🔴🔴 APP-028②：**语音滞后秒数**（队列里还没播的音频时长）。
        #   ⇒ 这是「用户实际听到的延迟」；`backlog_s` 是「系统内部总积压」。
        #   ⇒ GUI 底栏显示「语音滞后 X 秒」用的就是它。
        self._lag_s = 0.0
        self.lag_s = 0.0
        # 🔴🔴🔴 APP-042：**上一句用的加速倍率**（滞回 + 步长限制的基准）
        self._last_speed = 1.0
        # 🔴🔴🔴 APP-042：**当前正在播放的倍率 / 滞后**（GUI 底栏显示）
        self.cur_speed = 1.0
        self.play_lag_s = 0.0
        self.peak_play_lag_s = 0.0
        # 🔴🔴 APP-042：**各倍率的时间占比**（验收报告要）
        #   key = 倍率×100（整数），value = 该倍率下的**音频秒数**
        self.speed_time_s: dict = {}
        self.n_speed_adjusted = 0
        # 🔴 APP-028②：滞后告警的边沿触发 + 冷却（避免刷屏）
        self._lag_warned = False
        self._lag_warn_last = 0.0
        # 🔴 APP-027④：积压的三段明细（诊断用）
        self.backlog_parts: dict = dict(ring_s=0.0, synth_s=0.0,
                                        queued_s=0.0)
        # 🔴🔴🔴 APP-027⑤：克隆音色状态（GUI 要显示「实际使用的音色」）
        self.clone_active = False
        self.clone_updated_at = None
        self.clone_dur_s = None
        self.clone_mode = None
        # ── 🔴🔴🔴 APP-036 C2：**积压随时间的曲线**（每 1–2 s 采一点）──
        #   reviewer APP-036 C2 原话：
        #     「`app028_backlog_curve.csv` 只有收尾时的 1 行，不算曲线。
        #       改成每 1–2 s 采样一次 `backlog_s / backlog_parts / lag_s`
        #       （在落盘模式下也要采），并按 1 s 粒度用 `source_t` 对齐。」
        #   ⇒ 旧实现是**从 CLI 日志里 grep 统计行**⇒ 那些行只在收尾时打印
        #     ⇒ 1 个采样点 ⇒ **不是曲线**。
        #   ⇒ 现在：**service 内部**起一个采样线程 ⇒ 与播放/落盘模式无关
        #     ⇒ 两个模式都有曲线。
        self._curve_rows: List = []
        self._curve_t0 = time.perf_counter()
        self._curve_stop = threading.Event()
        self._curve_thread: Optional[threading.Thread] = None
        self._curve_interval_s = 1.5

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
            # 🔴🔴🔴 APP-036 C2：**起积压曲线采样线程**
            #   ⇒ worker 起来之后曲线才有内容 ⇒ 放在这里（不是 `__init__`）
            self.start_curve_sampler()
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
            # 🔴🔴 APP-023 根因 1（后半段）：用**真实解释器**，别用 venv 的
            #   pythonw 重定向器（旧代码是 `sys.executable`）。
            #   ⇒ worker 自己**不带控制台** ⇒ 它内部再 spawn 时，
            #     `stderr=None` 会踩同一个 `GetStdHandle(-1)` ⇒ WinError 50。
            #   ⇒ `CREATE_NO_WINDOW`：**不创建**新控制台（不弹黑框），
            #     同时 worker 的 std 句柄由 `PIPE` 显式给（见下）。
            self._worker_python_used = _worker_python()
            cmd = [self._worker_python_used, _WORKER,
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
            # 🔴🔴🔴 **逐句遥测 JSONL**（APP-027 V1/V2 验收字段的**唯一来源**）
            #   ⚠️ worker 侧只在有 `--out-wav` 时才自动设 JSONL 路径
            #   ⇒ 真实播放路径**必须显式传**，否则逐句遥测**无处可落盘**。
            if self.jsonl_path:
                cmd += ['--jsonl', self.jsonl_path]
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
                # 🔴 APP-023：**不弹黑框**。worker 换成了控制台解释器
                #   （`python.exe`，为了拿到真实 std 句柄）⇒ 不加这个 flag
                #   就会在用户桌面上**闪一个 cmd 黑窗口**（用户是 pythonw 启动的）。
                self.proc = subprocess.Popen(
                    cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, bufsize=0, env=env,
                    **_no_window_flag())
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
            # 🔴🔴🔴 APP-036 C2：**停曲线采样线程**（在清 pending 之前
            #   ⇒ 最后再采一个收尾点 ⇒ 曲线包含收尾时刻）
            try:
                self._sample_curve()
            except Exception:
                pass
            self.stop_curve_sampler()
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
            # 🔴🔴🔴 APP-036 C4：**单独记「关闭时作废」**
            #   reviewer 原话：「§82 那次『丢弃 0』实际作废了 51 句
            #     ⇒ ……并在报告里列出 `n_discard_on_close`。」
            #   ⇒ 这一类是 `close()` **主动**作废的 ⇒ 与「积压丢句」性质不同
            #   ⇒ 单独计数，验收脚本可独立核对「收尾前统计行」与
            #     「close() 之后真实作废数」是否一致。
            self.n_discard_on_close += len(orphan)
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
               spk=None, spk_conf=None, lang: Optional[str] = None,
               target_play_at: Optional[float] = None):
        """提交一条**定稿译文**。

        ⚠️ worker 还没 `ready` 时**不能直接下发** —— worker 的 stdin
        在模型加载完成前也在收命令，但那时音色条件还没加载好，
        合成会失败。所以这里**先入待发队列**，等 `ready` 事件后补发。

        🔴🔴 APP-022：`spk` / `spk_conf` **接口预留**（当前恒为 None）。
        ⇒ 透传给 worker 的 `synth` 命令（worker 侧**同样只预留不使用**）。
        ⇒ **不改变现有行为**：spk 为 None 时命令体与改造前逐字一致。

        🔴🔴🔴 APP-030①：`lang` = **MT 当前目标语言**（显式下传）。
          - 旧实现命令体只有 `{'cmd','id','text'}` ⇒ **不带语言**
            ⇒ worker 只能靠 `_guess_lang()` **猜**（只分 zh/en）
            ⇒ **TTS 永远收不到 Japanese**
            ⇒ reviewer 实测 8 条日文样句：**5 条判 en、3 条判 zh**（8/8 全错）
            ⇒ 判 en ⇒ 用 English 语言 token 读假名（分布外 ⇒ EOS 不稳
              ⇒ 偶发撞 2048 帧上限 ⇒ 一句拖 106 s ⇒ 后续句全堵）
            ⇒ 判 zh ⇒ 用 Chinese token 读日文 + `normalize_zh_numbers` 误作用
          - 现在：`lang` 随命令下发 ⇒ worker **不再猜**。
          ⚠️ **只有 `lang` 为真值时才加进命令体** ⇒ 旧调用方
            （不传 lang）**命令体逐字不变** ⇒ 向后兼容。

        🔴🔴🔴 APP-042：**自适应加速播放**（按句变速，追赶语音滞后）。
          - `target_play_at` = **这句的目标开播时刻**（主进程时钟，
            `time.perf_counter()` 口径）⇒ App 侧 = 「源音频中这句的结束
            时刻」对应的墙钟；插件侧 = `t0 + t_start + D`。
          - `lag` = 「这句的**实际**开播时刻 − 目标开播时刻」。
            ⚠️ **提交时刻**不是开播时刻 ⇒ 这里用**提交时刻**算 lag 是
            **下界**（真正开播还要排队 + 合成 + 预缓冲）。
            ⇒ 真正的 lag 由 worker 在**播出时**回报（`played` 事件里的
              `play_lag_s`）⇒ **主进程用回报值**做闭环修正。
          - `speed` = `time_stretch.speed_for_lag(lag, prev_speed)`
            （**统一参数**，与插件一致）⇒ 随命令下发。
          - ⚠️ **只有 `target_play_at` 为真值时才加进命令体**
            ⇒ 旧调用方**命令体逐字不变** ⇒ 向后兼容。
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
        # 🔴🔴🔴 APP-030①：**目标语言显式下传**（同样「只在有值时加」）
        if lang:
            cmd['lang'] = str(lang)
        # 🔴🔴🔴 APP-042：**自适应加速**（按句变速）
        #   ⚠️ **只在有 `target_play_at` 时才加** ⇒ 旧调用方命令体逐字不变。
        #   ⚠️ **时钟口径**：APP-042 的 lag 是「实际开播 − 目标开播」，
        #     这两个时刻分别发生在 **worker 进程**（开播）和 **主进程**
        #     （目标）⇒ **跨进程** ⇒ `time.perf_counter()` **基准不同**
        #     （Windows 上是 QPC，起点是各进程启动时刻）⇒ **不可比**。
        #     ⇒ 统一改用 **墙钟 `time.time()`**（同一台机器的系统时钟
        #       ⇒ 跨进程可比）。⚠️ 目标时刻由调用方按同一口径给出。
        #   ⚠️ `speed_for_lag` 是纯函数 ⇒ 无副作用 ⇒ 锁外算安全；
        #      但 `prev_speed` 的更新要**加锁**（并发提交时不能丢更新）。
        #
        # 🔴🔴🔴 **§97 实测修正（重要）**：这里的 `lag` **不是** APP-042
        #   定义的 lag（那是「实际开播 − 目标」⇒ **只有 worker 知道**）。
        #   本处算的是「**提交时刻** − 目标」⇒ 只含**翻译延迟**
        #   （实测 2–3 s ⇒ 恒在 3 s 死区内 ⇒ speed 恒 1.0）。
        #   ⇒ **权威定速已移到 worker 出队时**（见 `tts_worker.synth()`）。
        #   ⇒ 本处**保留**下发，仅为**向后兼容老 worker**（无新代码时行为不变）。
        #   ⇒ `cmd['lag_s']` 保留旧值语义（提交时刻滞后）⇒ 不改旧字段口径。
        if target_play_at is not None:
            try:
                import time_stretch as _ts
                now_wall = time.time()
                _lag_target = now_wall - float(target_play_at)
                # 🔴 滞后取**两个来源的较大者**：
                #   ① 目标滞后 = 「现在 − 目标开播时刻」（翻译+排队的延迟）
                #   ② 队列积压 = `lag_s`（用户实际听到的延迟，APP-028②）
                #   ⇒ 加速是为了**追赶用户听到的落后**⇒ ② 才是关键量。
                try:
                    _lag_queue = float(self.lag_s or 0.0)
                except Exception:
                    _lag_queue = 0.0
                _lag = max(_lag_target, _lag_queue)
                with self.lock:
                    _prev = float(self._last_speed or 1.0)
                _sp = float(_ts.speed_for_lag(_lag, _prev))
                with self.lock:
                    self._last_speed = _sp
                cmd['speed'] = round(_sp, 4)
                cmd['target_wall'] = round(float(target_play_at), 4)
                cmd['lag_s'] = round(_lag, 3)
            except Exception as e:
                # 🔴 变速参数算不出来 ⇒ **不加速**（宁可不变调，也不崩）
                self.on_log('[TTS] APP-042 速度计算失败 ⇒ 本句按 1.0× 播放：%s'
                            % e)
        if action == 'send':
            # 🔴🔴 2026-10-25 §29 修：**命令送不出去时必须撤账**。
            #   `_send()` 旧实现只记日志、不返回成败 ⇒ 调用方以为已下发
            #   ⇒ `_inflight` 里留下这个 jid ⇒ 但 worker 永远收不到
            #   ⇒ `pending[jid]` 永久悬挂 ⇒ `drain()` 必超时
            #   （GUI 白等 30 s / CLI 白等 120 s）。
            #   现在：`_send()` 返回成败 ⇒ 失败即撤账（清 pending + 注销
            #   `_inflight`）+ **计丢句**（诚实记账，不让这句凭空消失）。
            if not self._send(cmd):
                # 🔴🔴 2026-10-27 §60 修：**不得无条件 `n_dropped += 1`**。
                #   旧实现无条件 +1 ⇒ 若 worker 级 error 的「孤儿清理」
                #   已先把这句清掉并计过丢句 ⇒ 这里**再 +1** ⇒ **双记**。
                #   ⇒ 改用统一原子口径（见 `_drop_one`）。
                #   ⚠️ `register_dropped=False`：命令**从未到达 worker**
                #     ⇒ worker 不会回 `played` ⇒ 不必登记 `_dropped_ids`。
                self._drop_one(jid, register_dropped=False)
        elif action == 'dead':
            # 🔴 2026-10-24 §22 修：worker 级故障后 `state == 'error'`，
            #   此时 `_flush_queue()` **永远不会被调用**（它只在 `ready` 事件时跑）
            #   ⇒ 旧实现把命令无限堆进 `_queue` ⇒ **内存无界增长**。
            #   现在：直接计丢句并清掉 pending，**不排队**。
            # 🔴🔴 2026-10-27 §60 修：**不得无条件 `n_dropped += 1`**。
            #   旧实现无条件 +1 ⇒ 若 worker 级 error 的「孤儿清理」
            #   已先把这句清掉并计过丢句 ⇒ 这里**再 +1** ⇒ **双记**。
            #   ⇒ 改用统一原子口径（见 `_drop_one`）。
            #   ⚠️ `register_dropped=False`：worker 已故障 ⇒ 不会再有 `played`。
            self._drop_one(jid, register_dropped=False)
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
                    #   🔴🔴 2026-10-27 §60 修：**这里不得再 `pending.pop`**。
                    #   旧实现在本临界区内 pop、到锁外才计数 ⇒
                    #   「摘除」与「计数」**不原子** ⇒ 与别的路径交错时
                    #   会出现「已被别处定案却仍被计数」⇒ **双记**。
                    #   ⇒ 现在**不在这里摘除** ⇒ 交给 `_drop_one()` 在
                    #      **同一个锁内**完成「摘除 + 计数」⇒ 原子。
                    direct = False
                    dead = True
                else:
                    self._queue.append(cmd)
                    # 🔴🔴 2026-10-27 §58 修：登记「这句在待发队列里」
                    #   ⇒ `cancel()` 才能把它摘掉（见 cancel() 里的说明）。
                    self._queued_ids.add(jid)
                    direct = False
                    dead = False
            if direct:
                if not self._send(cmd):
                    # 🔴🔴 2026-10-27 §60 修：统一原子口径（见 `_drop_one`）。
                    #   ⚠️ `register_dropped=False`：命令**从未到达 worker**。
                    self._drop_one(jid, register_dropped=False)
            elif dead:
                # 🔴🔴 2026-10-27 §60 修：**只有「这句此刻确实还在 `pending` 里」
                #   才计丢句**（否则会与「孤儿清理」的计数重复 ⇒ 双记）。
                #   ⇒ `_drop_one()` 在**同一把锁内**完成「摘除 + 计数」。
                #   ⚠️ `register_dropped=False`：worker 已故障 ⇒ 不会再有 `played`。
                self._drop_one(jid, register_dropped=False)
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
                    # 🔴🔴 2026-10-27 §60 修：**不得无条件 `n_dropped += 1`**。
                    #   旧实现先 `pending.pop` 再在循环外 `n_dropped += n_failed`
                    #   ⇒ 若这句已被 worker 级 error 的「孤儿清理」定案
                    #   ⇒ 仍然**双记** ⇒ 不变式破坏。
                    #   ⇒ 改用统一原子口径（见 `_drop_one`）⇒ **按句**判定。
                    #   ⚠️ `register_dropped=False`：命令**从未到达 worker**。
                    self._drop_one(jid, register_dropped=False)
        if n_failed:
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
            # 🔴🔴🔴 APP-027⑤：**必须持写锁** ⇒ 命令行不交错
            #   （`submit`/`cancel` 来自 GUI 主线程，`clone` 来自会话线程）
            with self._stdin_wlock:
                try:
                    p.stdin.write(line)
                except TypeError:
                    # 兼容旧的文本模式管道（例如外部注入的假 proc）
                    p.stdin.write(line.decode('utf-8'))
                p.stdin.flush()
            # 🔴🔴 APP-024①：**命令真正写进 worker stdin 的时刻**。
            #   ⇒ 主进程侧「排队等待」= `t_sent − t_submit`
            #     （同一个进程 ⇒ `time.perf_counter()` 时钟可比；
            #      跨进程时钟**不可比** ⇒ 排队段必须由主进程算）。
            #   ⚠️ `submit()` 已把 `t_submit` 写进 `pending[jid]['t']` ⇒
            #   这里只补 `t_sent` ⇒ 两条路径（直接下发 / `_flush_queue` 补发）
            #   **都**能拿到完整的排队段。
            jid = obj.get('id')
            if jid is not None:
                with self.lock:
                    p = self.pending.get(jid)
                    if p is not None:
                        p['t_sent'] = time.perf_counter()
            return True
        except Exception as e:
            self.on_log(f'[TTS] 发送失败：{e}')
            return False

    # 🔴🔴🔴 2026-10-27 §60 新增：**丢句记账的唯一原子口径**。
    def _drop_one(self, jid: int, register_dropped: bool = False) -> bool:
        """原子地「把这一句定案为丢句」。

        🔴🔴 **为什么需要这个统一入口（§60 修的缺陷类别）**：
          丢句的**判定**（这句还在不在途）与**计数**（`n_dropped += 1`）
          必须**在同一把锁内**完成，否则会出现「双记」：
            · 路径 A 先把这句话从 `pending` 里清掉并计了丢句；
            · 路径 B 随后又对**同一句**执行 `n_dropped += 1`
              （因为它只看 `state` / 发送成败，**没看这句是否还在途**）
            ⇒ 同一句被计了两次 ⇒ `n_played + n_dropped > n_submitted`
              ⇒ 不变式破坏 ⇒ 底栏「丢句 + 已播」超过「提交」。

        🔴 **真实触发路径（不是理论构造）**：
          「worker 级 error 的孤儿清理」会做
              `orphan = sorted(self.pending.keys())` → `pending.clear()`
              → `n_dropped += len(orphan)`
          而 `submit()` 的三条丢句路径（发送失败 / worker 已故障 / 补发失败）
          都在**这个清理之外**各自执行了一次**无条件**的 `n_dropped += 1`
          ⇒ 只要 worker 级 error 与 `submit()` / `_flush_queue()` **交错**，
            就会双记（实测见 `results/app/app090_tts_drop_double_count.py`）。

        ⇒ **统一口径**：**只有「这一句此刻确实还在 `pending` 里」才计丢句**。
          摘除（`pending.pop`）+ 注销 `_inflight` + 计数
          **全部在同一把锁内**完成 ⇒ 原子。

        参数 `register_dropped`：
          `True`  ⇒ 同时登记进 `_dropped_ids`
                    （含义：worker **仍可能**回 `played` ⇒ 收到时要「改记为已播」）
                    —— 用于「命令**已下发**、worker 可能无视 cancel 照样播」的场景；
          `False` ⇒ **不**登记（含义：命令**从未下发**或 worker 已死 ⇒ 不会再有事件）
                    —— 用于「发送失败 / worker 已故障」的场景。

        返回 True  = 本次**确实计了**丢句；
        返回 False = 这句**已被别的路径定案**（已播 / 已丢 / 已失败）⇒ **不再重复计**。
        """
        with self.lock:
            # 🔴 `pop` 返回 None ⇒ 这句**已不在途** ⇒ 已被别人定案 ⇒ 不得重复计。
            was_pending = self.pending.pop(jid, None) is not None
            # 🔴 §29：**必须同时注销 `_inflight`**，否则 worker 崩溃时
            #   `lost = sorted(self._inflight)` 会把它**再算一次**丢句。
            self._inflight.discard(jid)
            if not was_pending:
                return False
            if register_dropped:
                # 🔴 §30：登记「已丢弃但 worker 可能仍会播」
                #   ⇒ 迟到的 `played` 会被改记为已播（`n_dropped -= 1`）。
                self._dropped_ids.add(jid)
            # 🔴 计数**在锁内**完成 ⇒ 与「摘除」原子 ⇒ 不会与别的路径并发叠加。
            self.n_dropped += 1
        return True

    # -- 🔴🔴🔴 APP-029：**说话人晚到 ⇒ 补发更新**（接口预留）-----------
    def spk_update(self, jid: int, spk, spk_conf=None) -> bool:
        """🔴🔴🔴 APP-029：`spk_update(id, spk, spk_conf)`（**接口预留**）。

        ## APP-029 的新口径（2026-10-27 15:48 用户决定）

        **pyannote/segmentation-3.0 只用来识别说话人，不再用来给 ASR 断句。**

        依据（ASR-020 的 Opus 复算，SPE 前 5 分钟）：
          - WER 是 baseline 7.39% 对 forced 7.52% ⇒ **没有实际差异**；
          - 词内切点都是 3 处 ⇒ **也没有差异**；
          - 而实时断句至少还要多等约 9.4 s 的右侧上下文
            ⇒ 对实时字幕和 10 s 缓冲的配音插件**都不可接受**。

        ⇒ **断句继续用 R2T2 原有的方式**；
        ⇒ pyannote 和说话人 embedding 在**旁路**运行、**不阻塞定稿**：
          定稿段先发出去，spk 晚到（可以晚 1~2 s）时，
          用 id 补发一条 spk 更新；
        ⇒ 这个更新用来**更新字幕标签**，以及**还没开始合成**的那几句的音色；
        ⇒ **已经开始合成的句子不改。**

        ⚠️ **本轮不集成**（APP-029 明文「现在不要集成」）
        ⇒ 本方法**只把命令下发出去**（worker 侧只记日志）
        ⇒ **不改变任何合成行为**、**不影响 `n_played`/`n_dropped` 账本**。
        """
        cmd = {'cmd': 'spk_update', 'id': jid,
               'spk': spk, 'spk_conf': spk_conf}
        return self._send(cmd)

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
            # 🔴🔴🔴 APP-027④：worker FIFO 队列里的句子也要摘掉
            #   （否则主进程以为它还在排队 ⇒ 积压高估 ⇒ 又多丢几句）
            self._queue_est_s.pop(jid, None)
            try:
                self._wqueue_ids.remove(jid)
            except ValueError:
                pass
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
            # 🔴🔴 APP-024①：**首包拆成两段上报**（reviewer 验收标准：
            #   「排队等待 `t_dequeue − t_submit`，合成首包 `t_first_packet − t_dequeue`」）。
            #   ⚠️ **跨进程时钟不可比** ⇒ 排队段必须用**主进程自己的**两个时刻相减：
            #     `t_sent`（命令写进 stdin）− `t_submit`（submit 时）
            #     ⇒ worker 回传的 `t_dequeue` 只作**诊断参考**，不参与计算。
            #   ⚠️ `pending[jid]` 可能已被清（句子已定案）⇒ 取不到就**不填**
            #     （⇒ 该句的排队段为 None，**不编造数字**）。
            jid = msg.get('id')
            if jid is not None:
                with self.lock:
                    p = self.pending.get(jid)
                    t_submit = p.get('t') if p else None
                    t_sent = p.get('t_sent') if p else None
                if t_submit is not None and t_sent is not None:
                    queued = max(0.0, t_sent - t_submit)
                    synth_s = msg.get('synth_s')
                    self.first_packet_parts = dict(
                        id=jid,
                        queued_s=round(queued, 3),
                        synth_s=(round(float(synth_s), 3)
                                 if synth_s is not None else None),
                        latency_s=msg.get('latency_s'),
                    )
                    self.on_log(
                        '[TTS] 首包分段 id=%s：排队 %.3f s + 合成 %s s'
                        % (jid, queued,
                           ('%.3f' % float(synth_s)) if synth_s is not None
                           else '?'))
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
            # 🔴🔴🔴 APP-036 C3：**记录「最后一句播完」的时刻**（主进程时钟）
            #   ⇒ 与「源音频结束时刻」相减 = `end_lag_s`。
            self._last_out_t = time.perf_counter()
            self._recompute_end_lag()
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
            # 🔴🔴🔴 APP-042：**回收 worker 回报的实际倍率 / 播放滞后**
            #   ⇒ 底栏显示「当前语速倍率 + 滞后秒数」（APP-042 明文）。
            #   ⇒ 同时累计「各倍率的时间占比」（验收报告要）。
            try:
                _sp = float(tel.get('speed') or 1.0) if tel else 1.0
            except Exception:
                _sp = 1.0
            self.cur_speed = _sp
            if _sp > 1.0000001:
                self.n_speed_adjusted += 1
            try:
                _plag = float(tel.get('play_lag_s')) if tel else None
            except Exception:
                _plag = None
            if _plag is not None:
                self.play_lag_s = _plag
                if _plag > self.peak_play_lag_s:
                    self.peak_play_lag_s = _plag
            # 各倍率的**音频秒数**占比
            try:
                _od = float(tel.get('out_dur_s') or 0.0) if tel else 0.0
            except Exception:
                _od = 0.0
            if _od > 0:
                _k = int(round(_sp * 100))
                self.speed_time_s[_k] = (self.speed_time_s.get(_k, 0.0)
                                         + _od)
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
            # 🔴🔴🔴 APP-036 C3：落盘模式（`--tts-out`）下**没有 `played`**
            #   ⇒ 「写完」就是终点 ⇒ 这里也记一次「最后输出时刻」。
            if self.out_wav:
                self._last_out_t = time.perf_counter()
                self._recompute_end_lag()
            self._update_backlog()
        elif kind == 'empty':
            # 🔴🔴🔴 APP-037 C（reviewer 裁定）：**空句**（剥掉句首标点后为空）
            #   ⇒ worker **没有合成**（没有音频、也没有失败）
            #   ⇒ **既不播也不丢** ⇒ **不能** `n_played += 1`（没出声）
            #   ⇒ **也不能** `n_dropped += 1`（reviewer 明文「不计丢句」）
            #   ⇒ 但这一句**必须从 `pending` 里摘掉** ⇒ 否则
            #     `drain()` 永远等不到它 ⇒ **必超时**。
            #   ⚠️ `n_submitted` 已经把它算进去了 ⇒ 不变式变成
            #     `n_played + n_dropped + n_empty == n_submitted`
            #     ⇒ 单独用 `n_empty` 记这一类（不混进 dropped）。
            jid = msg.get('id')
            with self.lock:
                was_pending = self.pending.pop(jid, None) is not None
                self._inflight.discard(jid)
            if was_pending:
                self.n_empty += 1
            self.on_log('[TTS] 第 %s 句句首标点剥离后为空，未合成'
                        '（不计丢句）' % jid)
        elif kind == 'synth_state':
            # 🔴🔴🔴 APP-027④：worker 报「合成队列状态」。
            #   ⇒ 主进程据此算**三段式积压**（环形缓冲水位 + 正在合成的剩余
            #     + 排队句子的预计时长）。
            #   ⚠️ **旧口径为什么错**：每个「已写入」的句子各按
            #      `min(3.0, dur_s)` 各算一次 ⇒ 两句同时已写入按 6 s 计
            #      ⇒ **高估积压** ⇒ **多丢句**（用户实测「越拖越久、全丢」）。
            #   ⇒ 现在这一项**只算一次**（来自 worker 的实际水位）。
            with self.lock:
                self._synth_jid = msg.get('synth_jid')
                try:
                    self._synth_rem_s = float(msg.get('synth_rem_s') or 0.0)
                except Exception:
                    self._synth_rem_s = 0.0
                try:
                    self._ring_backlog_s = float(
                        msg.get('ring_backlog_s') or 0.0)
                except Exception:
                    self._ring_backlog_s = 0.0
                # 🔴🔴 APP-028②：**语音滞后秒数**（队列里还没播的音频时长）
                #   ⇒ 底栏显示「语音滞后 X 秒」。
                #   ⚠️ worker 是旧版（没这个字段）时回落成队列水位。
                try:
                    _lag = msg.get('lag_s')
                    self._lag_s = (float(_lag) if _lag is not None
                                   else float(self._ring_backlog_s or 0.0))
                except Exception:
                    self._lag_s = float(self._ring_backlog_s or 0.0)
                self._wqueue_ids = list(msg.get('queue_ids') or [])
                qe = msg.get('queue_est_s') or {}
                self._queue_est_s = {int(k): float(v)
                                     for k, v in qe.items()}
                spc = msg.get('sec_per_char')
                if spc:
                    try:
                        self._sec_per_char = float(spc)
                    except Exception:
                        pass
            self._update_backlog()
        elif kind == 'clone':
            # 🔴🔴🔴 APP-027⑤：克隆音色更新结果。
            #   ⇒ GUI 要能看见「**当前实际使用的音色**」
            #     （「预设 A」/「克隆（更新于 hh:mm:ss，x s 语音）」）
            #   ⇒ **绝不静默**（失败必须显式回落预设 A 并写日志）。
            ok = bool(msg.get('ok'))
            self.clone_active = ok
            self.clone_updated_at = msg.get('updated_at')
            self.clone_dur_s = msg.get('dur_s')
            self.clone_mode = msg.get('mode')
            if ok:
                self.on_log('[TTS] 克隆音色已更新（%.1f s 语音，模式 %s）'
                            % (float(self.clone_dur_s or 0.0),
                               self.clone_mode or '?'))
            else:
                self.on_log('[TTS] 🔴 克隆音色更新失败：%s ⇒ 回落到预设 A'
                            % (msg.get('message') or '未知原因'))
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
        elif kind == 'spk_voice':
            # 🔁§99（断链 C）：worker 登记结果回执
            #   → 主进程必须**等这个确认**才能标「已有音色」。
            #   ok=True → 已成功；ok=False → 登记失败（回落预设 A）。
            _spk = str(msg.get('spk') or '').strip()
            if _spk:
                self._spk_voice_status[_spk] = dict(
                    ok=bool(msg.get('ok')),
                    dur_s=msg.get('dur_s'),
                    message=msg.get('message') or '')
            self.on_log('[TTS] 说话人音色登记 %s：%s'
                        % (_spk, '成功' if msg.get('ok')
                           else '失败（%s）'
                           % (msg.get('message') or '')))
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

    # 🔴🔴🔴 APP-028②：**用户手动停止 / 切换会话** ⇒ 清空队列。
    def clear_audio_queue(self) -> bool:
        """🔴🔴🔴 APP-028②：让 worker **清空音频队列**。

        APP-028 明文：「**用户手动停止或切换会话时才清空队列**」
        ⇒ 这是**唯一**允许清空的入口（正常播放期间**绝不**清空）。

        🔴 为什么需要清空：APP-028② 取消了丢句 ⇒ 队列会保留所有已合成
          但还没播的音频 ⇒ 用户手动停止后，若不清空 ⇒ 停止之后**声音还在继续**
          ⇒ 用户以为「停了」但耳机里还在说话。
        ⇒ 同时也把「已取消」标记清掉（下一轮会话是新的一句）。
        """
        return self._send({'cmd': 'clear_queue'})

    # 🔴 APP-021②：拉一次播放器遥测（不含模型）。
    def request_telemetry(self) -> bool:
        return self._send({'cmd': 'telemetry'})

    # 🔴 APP-021⑥：**运行时**开关逐句 wav 落盘（worker 已经在跑也能改）。
    def set_dump_dir(self, path: Optional[str]) -> bool:
        return self._send({'cmd': 'set_dump_dir', 'dir': path or ''})

    # 🔴🔴🔴 APP-027⑤：**更新克隆音色**（把 16 kHz PCM 发给 worker）。
    def set_clone_pcm(self, pcm) -> bool:
        """把一段 **16 kHz float32 PCM** 发给 worker ⇒ 更新克隆音色。

        🔴 **隐私**：PCM **只在进程间传输**（base64）⇒
        **不落盘到客户包**（worker 侧的临时 wav 在 `tempfile.gettempdir()`
        下，会话结束即删）。
        🔴 **失败不抛异常**：返回 False ⇒ 调用方显式回落预设 A。
        """
        try:
            import base64
            import numpy as np
            a = np.asarray(pcm, dtype=np.float32).reshape(-1)
            if a.size < 16000 * 3:
                return False
            b64 = base64.b64encode(a.tobytes()).decode('ascii')
            return self._send({'cmd': 'clone', 'pcm': b64})
        except Exception as e:
            self.on_log(f'[TTS] 克隆音色更新失败：{e}')
            return False

    # 🔴🔴🔴 APP-039/040：**登记某个 spk 的音色**（按句绑定用）。
    def register_spk_voice(self, spk: str, pcm) -> bool:
        """把「某个 spk 的干净语音」发给 worker ⇒ 登记该 spk 的音色。

        🔴🔴🔴 **与 `set_clone_pcm()` 的区别**（这是 APP-039 的核心）：
        - `set_clone_pcm()` 改的是「**当前全局**音色」⇒ 旧的滑动窗口路线
          ⇒ 每 30 s 重算 ⇒ **渐变 + 滞后 + 一直采样**（用户报的三宗罪）。
        - 本方法**只往「spk → 音色」表里加一条** ⇒ **不改全局音色**
          ⇒ 后续**按句**选用 ⇒ **切换是一次性的、不渐变**。

        🔴 **隐私**：PCM 只在进程间传输（base64）⇒ **不落盘**；
        worker 侧算出的向量只在**进程内存**里 ⇒ 会话结束清空。
        🔴 **失败不抛异常**：返回 False ⇒ 调用方回落预设 A。
        """
        if not spk:
            return False
        try:
            import base64
            import numpy as np
            a = np.asarray(pcm, dtype=np.float32).reshape(-1)
            if a.size < 16000 * 1:      # 至少 0.1 s
                return False
            b64 = base64.b64encode(a.tobytes()).decode('ascii')
            return self._send({'cmd': 'spk_voice', 'spk': str(spk),
                               'pcm': b64})
        except Exception as e:
            self.on_log(f'[TTS] 说话人音色登记失败：{e}')
            return False

    def spk_voice_status(self, spk: str):
        """🔁§99（断链 C）：**取用**已收到的说话人音色登记结果。

        → 返回 `None` 表示「worker 还没回」；
        → 返回 `dict(ok=..., dur_s=..., message=...)` 表示「已回」。
        → **取出即消费**（一个 spk 只能被结算一次）。
        """
        if not spk:
            return None
        with self.lock:
            return self._spk_voice_status.pop(str(spk), None)

    def clear_spk_voices(self) -> bool:
        """🔴 APP-039：**会话结束清空**说话人音色表（隐私纪律）。"""
        try:
            return self._send({'cmd': 'spk_voice_drop'})
        except Exception as e:
            self.on_log(f'[TTS] 清空说话人音色表失败：{e}')
            return False

    def _emit(self, kind, payload):
        with self._outbox_lock:
            self._outbox.append((kind, payload))

    # -- 积压与丢句 ------------------------------------------------------
    def _estimate_dur_s(self, text: str) -> float:
        """估计一句译文的音频时长（秒）。

        🔴🔴🔴 APP-027④：**用 worker 实测的「音频秒/字」校准，不写死 5 字/秒**。
        - 旧实现写死「中文 5 字/秒、英文 15 字符/秒」
          ⇒ 与实测偏差很大 ⇒ 积压估算失真 ⇒ **多丢句**。
        - 现在：优先用 worker 报上来的 `sec_per_char`（实测 EWMA）
          ⇒ 没有实测值时才用保守兜底（中文 0.12 s/字 ≈ 8.3 字/秒）。
        """
        try:
            n = len([c for c in (text or '') if c.strip()])
        except Exception:
            n = 0
        if n <= 0:
            return 0.0
        spc = self._sec_per_char
        if spc:
            return float(n) * float(spc)
        return float(n) * 0.12

    def set_source_end(self, t: Optional[float] = None):
        """🔴🔴🔴 APP-036 C3：**打「源音频结束」的点**（主进程时钟）。

        reviewer APP-036 C3 原话：
          「新增 `end_lag_s = 最后一句播完（或写完）的时刻 − 源音频结束时刻`，
            播放模式和落盘模式各自给出。」

        ⚠️ **必须用主进程自己的时钟** ⇒ worker 的 `perf_counter()` 与主进程
          **基准不同**（Windows 上是 QPC，起点是进程启动时刻）⇒ 跨进程不能相减。
        ⇒ 由 **App 侧**在源音频播完时调用本方法打点。
        """
        self._source_end_t = (time.perf_counter() if t is None else float(t))
        self._recompute_end_lag()

    def _recompute_end_lag(self):
        """🔴🔴🔴 APP-036 C3：算 `end_lag_s`（两个点都在主进程 ⇒ 时钟可比）。"""
        if self._source_end_t is None or self._last_out_t is None:
            return
        try:
            self.end_lag_s = round(self._last_out_t - self._source_end_t, 3)
        except Exception:
            self.end_lag_s = None

    def _update_backlog(self):
        """🔴🔴🔴 APP-028②：**只统计积压，不再丢句**。

        🔴🔴🔴 **APP-028② 的明文要求**（用户 2026-10-27 13:22 原话）：

        > 「语音播放的时候，直接连续推理 TTS 音频流，不要等待播放完成，
        >   还没有播放的部分存内存缓存，这样提高系统利用率，
        >   **不要使用丢句这个方式**。」

        ⇒ 本方法**不再有任何丢句分支**：
          - 不再选候选（`_queued_ids` / `_wqueue_ids`）；
          - 不再下发 `{'cmd':'cancel'}`；
          - 不再 `n_dropped += ...`。
        ⇒ 代价 = **语音滞后会累积**（RTF > 1 时）⇒ 必须让用户看得见：
          `backlog_s` / `backlog_parts` / `lag_s` 全部照常上报，
          GUI 底栏显示「语音滞后 X 秒」。

        🔴 **口径不变**（APP-027④ 的三段式仍保留，只是不再用于丢句）：
            积压 = ① 音频队列里**实际剩下**的样本时长（只算一次，**不截断**）
                 + ② **正在合成的句子**的剩余预计时长
                 + ③ **排队中**（还没开始合成）的句子的预计时长

        ⚠️ **不丢句 ≠ 不记账**：`n_dropped` 只在**真正失败**的路径
        （命令送不出去 / worker 故障 / 显式 cancel）里增加。
        """
        with self.lock:
            pending_map = dict(self.pending)
        if not pending_map:
            self.backlog_s = 0.0
            return

        # ── ① 音频队列实际水位（worker 报）──
        ring_s = float(self._ring_backlog_s or 0.0)

        # ── ② 正在合成的句子：剩余预计时长 ──
        with self.lock:
            synth_jid = self._synth_jid
            synth_rem = float(self._synth_rem_s or 0.0)
            qest = dict(self._queue_est_s or {})
            qids = list(self._wqueue_ids or [])

        # ── ③ 排队中的句子（还没开始合成）──
        queued_s = 0.0
        for jid in qids:
            d = qest.get(jid)
            if d is None:
                d = self._estimate_dur_s((pending_map.get(jid) or {}).get(
                    'text', ''))
            queued_s += float(d or 0.0)

        est = ring_s + synth_rem + queued_s
        self.backlog_s = est
        self.max_backlog_s = max(self.max_backlog_s, est)
        self.backlog_parts = dict(ring_s=round(ring_s, 3),
                                  synth_s=round(synth_rem, 3),
                                  queued_s=round(queued_s, 3))
        # 🔴🔴 APP-028②：**语音滞后**（队列里还没播的音频时长）
        #   ⇒ 与 `backlog_s`（含排队句）**分开报**：
        #     前者是「用户实际听到的延迟」，后者是「系统内部的总积压」。
        self.lag_s = float(self._lag_s or 0.0)

        # 🔴🔴🔴 APP-028②：**到此为止 —— 不丢句**。
        #   只在日志里**低频**提示滞后（不刷屏、不改任何账本）。
        #   🔴 边沿触发 + 冷却 ⇒ 只有「跨过阈值」或「每 30 s」才记一条
        #      （否则 synth_state 每次事件都记 ⇒ 刷屏）。
        now = time.monotonic()
        over = self.lag_s > LAG_WARN_S
        if over and (not self._lag_warned
                     or now - self._lag_warn_last > LAG_WARN_COOLDOWN_S):
            self._lag_warned = True
            self._lag_warn_last = now
            self.on_log(
                f'[TTS] 语音滞后 {self.lag_s:.1f}s'
                f'（队列 {ring_s:.1f}s + 正在合成 {synth_rem:.1f}s'
                f' + 排队 {queued_s:.1f}s）'
                f'⇒ **按 APP-028 不丢句**，音频继续连续合成')
        elif not over:
            self._lag_warned = False

    # -- 🔴🔴🔴 APP-036 C2：**积压曲线采样** --------------------------
    def start_curve_sampler(self, interval_s: Optional[float] = None):
        """🔴🔴🔴 APP-036 C2：**起一个采样线程**，每 1–2 s 记一行曲线。

        reviewer 原话：「改成每 1–2 s 采样一次 `backlog_s / backlog_parts /
          `lag_s`（**在落盘模式下也要采**），并按 1 s 粒度用 `source_t` 对齐。」

        ⚠️ **为什么必须在 service 内部采**：
          旧实现是从 **CLI 日志**里 grep `[TTS] …积压…` 行
          ⇒ 那些行**只在收尾时打印一次** ⇒ csv 只有 1 行 ⇒ **不是曲线**。
          ⇒ 现在与日志无关 ⇒ 播放模式 / 落盘模式**都有曲线**。
        ⚠️ **采样线程不碰音频、不跑推理** ⇒ 只是读几个数值 ⇒ 开销可忽略。
        """
        if self._curve_thread is not None:
            return
        if interval_s is not None:
            self._curve_interval_s = max(0.2, float(interval_s))
        self._curve_t0 = time.perf_counter()
        self._curve_stop.clear()

        def _run():
            while not self._curve_stop.is_set():
                try:
                    self._sample_curve()
                except Exception:
                    pass
                if self._curve_stop.wait(self._curve_interval_s):
                    return

        self._curve_thread = threading.Thread(target=_run, daemon=True,
                                              name='tts-curve')
        self._curve_thread.start()

    def _sample_curve(self):
        """采一个曲线点。"""
        try:
            parts = dict(self.backlog_parts or {})
        except Exception:
            parts = {}
        row = {
            't_s': round(time.perf_counter() - self._curve_t0, 3),
            'backlog_s': round(float(self.backlog_s or 0.0), 3),
            'lag_s': round(float(self.lag_s or 0.0), 3),
            'ring_s': round(float(parts.get('ring_s') or 0.0), 3),
            'synth_s': round(float(parts.get('synth_s') or 0.0), 3),
            'queued_s': round(float(parts.get('queued_s') or 0.0), 3),
            'n_played': int(self.n_played),
            'n_dropped': int(self.n_dropped),
            'n_empty': int(self.n_empty),
            'n_submitted': int(self.n_submitted),
        }
        self._curve_rows.append(row)
        return row

    def stop_curve_sampler(self):
        """停采样线程（并再采一个收尾点）。"""
        self._curve_stop.set()
        th = self._curve_thread
        if th is not None:
            try:
                th.join(timeout=2.0)
            except Exception:
                pass
        self._curve_thread = None

    def curve_rows(self) -> List:
        """返回曲线采样点（副本）。"""
        try:
            return list(self._curve_rows)
        except Exception:
            return []

    def write_curve_csv(self, path: str) -> bool:
        """🔴🔴🔴 APP-036 C2：**把曲线写成 csv**（供 reviewer 直接画）。

        列：`t_s,backlog_s,lag_s,ring_s,synth_s,queued_s,n_played,n_dropped,
             n_empty,n_submitted`
        ⇒ **1 s 粒度**（默认 1.5 s ⇒ reviewer 可按 `source_t` 对齐）。
        """
        try:
            rows = self.curve_rows()
            d = os.path.dirname(os.path.abspath(path))
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write('t_s,backlog_s,lag_s,ring_s,synth_s,queued_s,'
                        'n_played,n_dropped,n_empty,n_submitted\n')
                for r in rows:
                    f.write('%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n' % (
                        r['t_s'], r['backlog_s'], r['lag_s'], r['ring_s'],
                        r['synth_s'], r['queued_s'], r['n_played'],
                        r['n_dropped'], r['n_empty'], r['n_submitted']))
            return True
        except Exception as e:
            try:
                self.on_log(f'[TTS] 曲线 csv 写入失败：{e}')
            except Exception:
                pass
            return False

    def stats(self) -> dict:
        return dict(
            state=self.state,
            first_packet_s=self.first_packet_s,
            first_packet_parts=self.first_packet_parts,
            backlog_s=round(self.backlog_s, 2),
            max_backlog_s=round(self.max_backlog_s, 2),
            # 🔴🔴 APP-028②：**语音滞后秒数**（队列里还没播的音频时长）
            #   ⇒ GUI 底栏显示「语音滞后 X 秒」。
            lag_s=round(self.lag_s, 2),
            # 🔴🔴🔴 APP-027④：积压的**三段明细**（诊断用）
            backlog_parts=dict(self.backlog_parts),
            # 🔴 APP-027④：worker 实测的「音频秒/字」（估时校准）
            sec_per_char=self._sec_per_char,
            n_dropped=self.n_dropped,
            n_played=self.n_played,
            n_submitted=self.n_submitted,
            # 🔴🔴🔴 APP-036 C3：**结尾滞后**（真实定义）
            end_lag_s=self.end_lag_s,
            # 🔴🔴🔴 APP-036 C4：**关闭时作废的句子数**
            n_discard_on_close=self.n_discard_on_close,
            # 🔴🔴🔴 APP-037 C：**空句数**（句首标点剥离后为空 ⇒ 未合成）
            n_empty=self.n_empty,
            n_restart=self.n_restart,
            voice=self.voice,
            device=self.device,
            out_device=self.out_device,
            clone=self.clone,
            # 🔴🔴🔴 APP-027⑤：**当前实际使用的音色**（GUI 显示用）
            clone_active=self.clone_active,
            clone_updated_at=self.clone_updated_at,
            clone_dur_s=self.clone_dur_s,
            clone_mode=self.clone_mode,
            # 🔴 §52：worker 级故障的**原文**（None = 没有故障）
            last_error=self.last_error,
            # 🔴 APP-021③：三个数（已播 / 丢句 / 失败）+ 最近一条句子级错误
            n_failed=self.n_failed,
            last_sentence_error=self.last_sentence_error,
            # 🔴 APP-021②：最近一行的播放遥测
            last_telemetry=self.last_telemetry,
            # 🔴🔴🔴 APP-042：**自适应加速**的状态（GUI 底栏显示）
            #   `cur_speed`        上一句用的倍率
            #   `play_lag_s`       上一句的**实际开播滞后**（worker 回报）
            #   `peak_play_lag_s`  峰值滞后
            #   `n_speed_adjusted` 被加速的句数
            #   `speed_time_s`     各倍率下的**音频秒数**（占比统计）
            cur_speed=round(float(self.cur_speed or 1.0), 3),
            play_lag_s=(round(float(self.play_lag_s), 3)
                        if self.play_lag_s is not None else None),
            peak_play_lag_s=round(float(self.peak_play_lag_s or 0.0), 3),
            n_speed_adjusted=int(self.n_speed_adjusted or 0),
            speed_time_s={int(k): round(float(v), 3)
                          for k, v in (self.speed_time_s or {}).items()},
            # 🔴 APP-021③：会话日志路径（用户报障时给这一个文件即可复盘）
            session_log=session_log_path(),
        )
