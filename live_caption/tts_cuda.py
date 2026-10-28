#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CUDA-TTS 后端（PyTorch + faster-qwen3-tts）—— App 侧客户端。

设计要点（STATUS §40）：
  - 本机 **CUDA 可用**（RTX 5050 / sm_120 / torch cu128），但与 **OpenVINO 的 CUDA plugin** 无关；
  - 该后端需要 `torch + transformers==5.15.1 + HF 权重`，**不进客户包**（+5.7 GB 且与包内
    transformers 4.57.6 冲突）⇒ 放在**独立 venv**，以**子进程边车**方式调用；
  - ⇒ 客户机没有这个 venv 时，`available()` 返回 False，GUI **自动不列该项**（不静默隐藏：note 说明）。

对外接口与 `babelvox` 对齐（这样 `tts_engine.stream()` / `tts_worker` 无需改）：
    eng.generate_stream(text=..., language=..., speaker_embed=..., speaker=...,
                        split_on_silence=..., cancel_event=..., chunk_frames=...)
        → 迭代产出 `(chunk_waveform, sample_rate)`，`sample_rate` 恒 24000。
"""
from __future__ import annotations

import atexit
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

ENV_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')
SIDECAR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'tts_cuda_sidecar.py')
READY_TIMEOUT_S = float(os.environ.get('LIVECAP_CUDA_READY_S', '180'))

# 🔴🔴🔴 APP-027③：**看门狗阈值**（秒）。
#   含义：已发出请求，但超过这么久**没有任何音频块**到达
#   ⇒ 判定边车卡死 ⇒ 记日志 + **杀并重启边车** + 本句记失败。
#   ⚠️ 默认 15 s（APP-027 明文「如 15 s 或 3×预计时长」）。
#   ⚠️ 首块要等模型预热（首次可能更久）⇒ 首块用**更宽松**的阈值
#      （`WATCHDOG_FIRST_S`），后续块用常规阈值。
WATCHDOG_S = float(os.environ.get('LIVECAP_CUDA_WATCHDOG_S', '15'))
WATCHDOG_FIRST_S = float(os.environ.get('LIVECAP_CUDA_WATCHDOG_FIRST_S', '60'))

# 🔴🔴🔴 §90：**cancel 确认等待上限**（秒）。
#:   边车回 `{'cancelled': true}` 表示「已收到取消指令」。
#:   ⚠️ **确认只代表「边车知道要取消」**，不代表「已停止」——
#:      边车会在**下一块**边界检查 ⇒ 最多再多生成一块。
#:   ⚠️ 等不到就**杀并重启**（APP-030② 明文要求的兜底）。
CANCEL_ACK_TIMEOUT_S = float(os.environ.get('LIVECAP_CUDA_CANCEL_ACK_S', '3'))

# 🔴🔴 APP-027③：**逐请求 trace 日志**（独立文件，便于复盘）。
#   记录：rid、收到请求时刻、第一块、done、块数、异常。
TRACE_PATH = os.path.join(
    os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'),
    'Confucius4LiveCaption', 'tts_cuda_trace.log')


def _trace(msg: str):
    """追加一行到 `tts_cuda_trace.log`（**永不抛异常**）。"""
    try:
        d = os.path.dirname(TRACE_PATH)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(TRACE_PATH, 'a', encoding='utf-8', newline='\n') as f:
            f.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
    except Exception:
        pass


#: 🔴🔴🔴 APP-030②：**RUNAWAY 判据阈值系数**
#:   判据（APP-030② 明文）：本句已收音频 > `max(3×估计, 估计+8 s)` ⇒ RUNAWAY
RUNAWAY_FACTOR = 3.0
RUNAWAY_EXTRA_S = 8.0


def runaway_threshold_s(est_sec) -> float:
    """RUNAWAY 判据阈值（秒）。

    ⚠️ **故意宽松** ⇒ 宁可漏判也不误杀正常句（误杀会把好句截断）。
    ⚠️ 与 `tts_engine.runaway_threshold_s` **同一公式**（两侧口径一致）。
    """
    try:
        e = float(est_sec)
    except Exception:
        e = 0.0
    if e <= 0:
        e = 0.0
    return max(RUNAWAY_FACTOR * e, e + RUNAWAY_EXTRA_S)


def _NO_WINDOW_FLAG():
    """🔴🔴 APP-023：子进程**不弹黑框**（Windows）。

    🔴 为什么必须加：本程序的用户启动路径是**桌面快捷方式 → pythonw.exe**
      （GUI 子系统、无控制台）⇒ 任何 `subprocess.Popen` 若不带这个 flag，
      Windows 会**给它分配一个新控制台** ⇒ 在用户桌面上**闪一个黑框**。
    ⇒ `CREATE_NO_WINDOW`（0x08000000）= 不创建控制台窗口。
    ⚠️ **Windows 专属** ⇒ 非 Windows 返回空 dict（`Popen` 不认这个 kwarg）。
    """
    if os.name != 'nt':
        return {}
    # 🔴 与 `tts_service.py` 用**同一个常量值**（两处独立 ⇒ 各自定义，
    #   但注释互相指认，避免以后有人只改一处）。
    return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)}


def _looks_like_pkg(d: str) -> bool:
    """目录像不像**客户包根**。

    🔴 判据 = **同时**有 `app/` 和 `models/`（实测教训）：
    - 仓库根 `confucius4-openvino/` **有** `models/`（放模型）但**没有** `app/`
      ⇒ 只判 `models/` 会把**仓库根**误判成包根（实测 `ref_audio` 指到
      `confucius4-openvino\\models\\...`，该文件不存在）；
    - **客户包根两个都有**（`app/` 是代码、`models/` 是模型与音色）。
    ⇒ 必须两个都判。
    """
    return (bool(d)
            and os.path.isdir(os.path.join(d, 'app'))
            and os.path.isdir(os.path.join(d, 'models')))


def _scan_for_pkg(start: str) -> str:
    """从 `start` 向上逐级查找「含 `models/` 且名字像包的目录」。

    🔴 **为什么是「逐级向上」而不是「固定上 N 级」**：
    - 客户机：`<包根>/app/tts_cuda.py` ⇒ 包根是**上上级**；
    - 开发机：`<repo>/live_caption/tts_cuda.py` ⇒ 上上级是 `C:\\Users\\Trekker-PTL`
      ⇒ **深度不同** ⇒ 写死层数必错（实测：写成上上级时开发机找不到包，
      `ref_audio` 退化成**相对路径** `models\\qwen3tts\\voices\\preset_A.wav`）。
    ⇒ 逐级向上 ⇒ 两种布局都对。
    """
    d = os.path.abspath(start)
    for _ in range(6):                 # 最多向上 6 级，够用且不会跑飞
        parent = os.path.dirname(d)
        if parent == d:                # 到根了
            break
        d = parent
        if _looks_like_pkg(d):
            return d
    return ''


def default_pkg_dir() -> str:
    """🔴🔴 **推导**客户包根目录（**绝不写死版本号**，STATUS §48）。

    事故（2026-10-26 实测）：原代码写死了**某个具体版本**的绝对包路径
    ⇒ ① 客户机上的包是**别的版本**（或装在别的路径）⇒ 音色文件找不到；
    ⇒ ② 仓库里升级版本号后，这行**不会跟着变** ⇒ 又一次指向旧包。

    推导顺序：
    1. 环境变量 `LIVECAP_PKG`（显式指定，最高优先）；
    2. 从本文件所在目录**逐级向上**找含 `models/` 的目录
       （客户机命中 `<包根>`；开发机命中 `C:\\Users\\Trekker-PTL` 本身——
        它下面有 `models/` 吗？没有 ⇒ 继续向上 ⇒ 也找不到 ⇒ 落第 3 步）；
    3. 在**扫描根**里挑**版本号最大**且含 `models/` 的 `Confucius4_LiveCaption_v*`。

    ⚠️ 本模块**在客户包里**⇒ **不能 import 仓库根的 `pkg_paths.py`**
    （包里没有它）⇒ 这里只做**纯 stdlib 的路径推导**。
    ⚠️ 找不到 ⇒ 返回空串（由调用方报错，**不静默指向某个旧版本**）。
    """
    env = os.environ.get('LIVECAP_PKG', '').strip()
    if env:
        return os.path.abspath(env)

    here = os.path.dirname(os.path.abspath(__file__))
    hit = _scan_for_pkg(here)
    if hit:
        return hit

    # 开发机：在**用户主目录**里挑版本号最大的包
    scan_root = os.path.expanduser('~')
    best, best_key = '', None
    try:
        names = os.listdir(scan_root)
    except OSError:
        names = []
    for name in names:
        if not name.startswith('Confucius4_LiveCaption_v'):
            continue
        ver = name[len('Confucius4_LiveCaption_v'):]
        try:
            key = tuple(int(x) for x in ver.split('.'))
        except ValueError:
            continue
        cand = os.path.join(scan_root, name)
        if not _looks_like_pkg(cand):
            continue
        if best_key is None or key > best_key:
            best_key, best = key, cand
    return os.path.abspath(best) if best else ''


class CudaTTSError(RuntimeError):
    pass


#: 🔴🔴🔴 APP-030③：**「队列超时」哨兵**
#:   必须与「边车已退出」（队列里的 `None`）**区分开**：
#:     - `None`      = 读者线程读到 EOF ⇒ 边车真的退出了；
#:     - `_TIMEOUT`  = 队列在超时窗口内**没有消息**（边车还活着，只是没产出）。
#:   ⇒ 旧实现把两者混为一谈（都 `raise`）⇒ 2 s 无块就判失败。
_TIMEOUT = object()


def python_exe() -> str:
    return ENV_PY


def available() -> bool:
    """**快速**可用性判断（不加载模型）：venv 的 python 在不在。

    ⚠️ 不做深度探测（`import torch` 要 3~5 s）⇒ 别在 GUI 启动路径上跑。
    深度探测用 `probe()`，在后台线程里做。
    """
    return os.path.isfile(ENV_PY) and os.path.isfile(SIDECAR)


def probe(timeout=90):
    """深度探测：真的能 import torch 且 `cuda.is_available()`。返回 (ok, detail)。"""
    if not os.path.isfile(ENV_PY):
        return False, '找不到 CUDA 环境：%s' % ENV_PY
    try:
        p = subprocess.run(
            [ENV_PY, '-c',
             'import torch,sys;'
             'sys.stdout.write("%s|%s|%s" % (torch.__version__, torch.version.cuda,'
             ' torch.cuda.is_available()))'],
            capture_output=True, timeout=timeout)
        out = (p.stdout or b'').decode('utf-8', 'replace').strip()
        if p.returncode != 0:
            return False, (p.stderr or b'').decode('utf-8', 'replace')[-300:]
        ver, cuda, ok = (out.split('|') + ['', '', ''])[:3]
        return ok == 'True', 'torch %s / CUDA %s / available=%s' % (ver, cuda, ok)
    except Exception as e:
        return False, '%s: %s' % (type(e).__name__, e)


class CudaTTSEngine:
    """常驻边车的客户端。`generate_stream` 与 babelvox 同形。"""

    #: 🔴 标记：该引擎**自己**用参考音频做 x-vector，不需要外部 speaker_embed
    USES_REF_AUDIO = True

    def __init__(self, pkg_dir=None, ref_audio=None, chunk_size=8,
                 python=None, on_log=print):
        self.on_log = on_log
        self.proc = None
        self.load_s = None
        self.warmup_s = None
        self.device_name = None
        self._rid = 0
        self._py = python or ENV_PY
        self._chunk_size = int(chunk_size)
        # 🔴 APP-023：stderr 泵线程（daemon）；close() 时不 join（不等它退出）。
        self._stderr_thread = None
        # 🔴🔴🔴 APP-027③：**读者线程 + 消息队列**
        #   `_q`  = 协议消息（JSON 行，或 `(JSON 行, PCM 字节)` 的**配对**）
        #   ⚠️ **PCM 必须与它的 JSON 行成对入队** ⇒ 否则 rid 过滤丢掉旧句的
        #      JSON 时，它的 PCM 还留在队列里 ⇒ 下一句读到旧 PCM ⇒ 错位。
        self._q: 'queue.Queue' = queue.Queue()
        self._reader_thread = None
        self._buf = b''
        # 🔴🔴🔴 APP-030⑤：**本句的结束原因与实际帧数**（供 worker 遥测）
        #   `end_reason` = eos | cap | runaway | error
        self._last_end_reason = None
        self._last_frames = None
        # 🔴🔴🔴 APP-027⑤：**stdin 写锁**
        #   `set_ref_audio()` 由 **worker 的命令处理线程**调用，
        #   而 `generate_stream()` 由 **合成线程**调用
        #   ⇒ 两个线程**并发 write(同一 pipe)** ⇒ 命令行**交错**
        #   ⇒ 边车收到半行 JSON ⇒ **解析失败 / 命令丢失**。
        #   ⇒ 必须串行化。
        self._stdin_wlock = threading.Lock()
        # 🔴🔴 §48：**不写死版本号** ⇒ 由 `default_pkg_dir()` 推导
        # （§48 前这里写死 `...\Confucius4_LiveCaption_v1.5`
        #   ⇒ 客户机换版本/换路径 ⇒ 音色文件找不到）。
        pkg = pkg_dir or default_pkg_dir()
        self.ref_audio = ref_audio or os.path.join(
            pkg, 'models', 'qwen3tts', 'voices', 'preset_A.wav')
        atexit.register(self.close)

    # ── 生命周期 ───────────────────────────────────────────────
    def start(self):
        if self.proc is not None and self.proc.poll() is None:
            return self
        if not os.path.isfile(self._py):
            raise CudaTTSError('CUDA 环境不存在：%s（见 README 的 CUDA 后端说明）' % self._py)
        if not os.path.isfile(SIDECAR):
            raise CudaTTSError('找不到边车脚本：%s' % SIDECAR)

        env = dict(os.environ)
        env.setdefault('HF_HUB_OFFLINE', '1')
        env.setdefault('PYTHONIOENCODING', 'utf-8')
        # 🔴🔴 §48：**统一**推导 —— 原代码这里用「上上级」，
        # 而 `__init__` 里算 `ref_audio` 用的是**写死的绝对路径**
        # ⇒ 两处不一致 ⇒ 边车与客户端可能指向**不同的包**。
        # ⇒ 现在两处都走 `default_pkg_dir()`（同一函数、同一规则）。
        env['LIVECAP_PKG'] = default_pkg_dir() or os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))

        t0 = time.monotonic()
        self.on_log('[tts_cuda] 启动 CUDA 边车：%s' % self._py)
        # 🔴🔴🔴 APP-023 根因 1：三个 std 句柄**必须全部显式给**。
        #   旧实现 `stderr=... else None` ⇒ 走 CPython 的
        #   `GetStdHandle(STD_ERROR_HANDLE)` 分支 ⇒ 在 **pythonw.exe**
        #   （GUI 子系统、**无控制台**）下拿到的是 **-1 伪句柄**
        #   ⇒ 随后的 `DuplicateHandle(-1)` 直接抛
        #   **`OSError: [WinError 50] 不支持该请求`**（实测 08:56 会话日志）。
        #   ⇒ 控制台 python 下句柄是真的 ⇒ **测试全绿、用户全挂**
        #     （APP-023 的核心教训：验收必须走用户真实启动路径）。
        #   ⇒ 修法：stderr 恒为 `PIPE`（绝不 None），另开一个 daemon 线程
        #     把它排空并转进 on_log ⇒ 既不丢错误信息，也不会写满管道缓冲区
        #     （Windows 管道约 64 KB 写满会**阻塞** worker 进程）。
        #   ⚠️ `stderr=PIPE` 时**必须有人读**，否则边车会卡在 write(stderr)。
        stderr_target = subprocess.DEVNULL if os.environ.get(
            'LIVECAP_CUDA_QUIET') else subprocess.PIPE
        self.proc = subprocess.Popen(
            [self._py, SIDECAR], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=stderr_target, env=env, bufsize=0,
            **(_NO_WINDOW_FLAG()))
        if stderr_target == subprocess.PIPE:
            self._start_stderr_pump()

        # 🔴🔴🔴 APP-027③：**先起读者线程**，再等 ready
        #   （否则 ready 那一行没人读 ⇒ 卡死）。
        self._start_reader()

        line = self._q_get(timeout=READY_TIMEOUT_S)
        # 🔴🔴🔴 APP-030③：**超时哨兵要在调用点区分**
        #   `_q_get` 现在超时返回 `_TIMEOUT`（**不抛**）⇒ 这里是**唯一**
        #   **必须**把它当失败的地方（等 ready 就是等一条消息）
        #   ⚠️ 旧写法 `if not line:` ⇒ `_TIMEOUT`（object()）是**真值**
        #   ⇒ 会走进 `json.loads(_TIMEOUT)` ⇒ TypeError ⇒ 启动路径崩。
        if line is _TIMEOUT:
            self.close()
            raise CudaTTSError('CUDA 边车启动失败（%.0f s 内没有 ready）'
                               % READY_TIMEOUT_S)
        if not line:
            self.close()
            raise CudaTTSError('CUDA 边车启动失败（%.0f s 内没有 ready）' % READY_TIMEOUT_S)
        msg = json.loads(line)
        if 'fatal' in msg:
            self.close()
            raise CudaTTSError('CUDA 边车致命错误：%s' % msg['fatal'])
        self.load_s = msg.get('load_s')
        self.warmup_s = msg.get('warmup_s')
        self.device_name = msg.get('device')
        self.on_log('[tts_cuda] 就绪：%s / torch %s / 加载 %.1fs / 预热 %.1fs'
                    % (self.device_name, msg.get('torch'),
                       self.load_s or -1, self.warmup_s or -1))
        self.on_log('[tts_cuda] 端到端启动耗时 %.1f s' % (time.monotonic() - t0))
        return self

    # ── stderr 泵（APP-023 根因 1）─────────────────────────────────────
    def _start_stderr_pump(self):
        """把边车的 stderr **排空**并转进 `on_log`。

        🔴🔴 **为什么必须有这个线程**（APP-023 根因 1）：
          - `stderr=PIPE` 而**没人读** ⇒ Windows 管道缓冲（约 64 KB）写满后
            边车会**阻塞在 write(stderr)** ⇒ 表现为「边车卡住 / 永不 ready」
            （与 §15 的 import 死锁症状一样，极难定位）；
          - ⇒ 必须有**独立的读者线程**，与读 stdout 的 `_readline` 分开
            （stdout 是稀疏的 JSON 行；stderr 是连续的告警/traceback）。
        ⚠️ **二进制读 + 逐行解码**：边车的 stderr 是**混编码**
          （torch/库自己的 UTF-8 + 外部 exe 的 GBK）⇒ 统一按 utf-8 解、
          失败用 'replace'（这里只是日志，丢一两个字节不影响判断）。
        """
        proc = self.proc
        if proc is None or proc.stderr is None:
            return
        pipe = proc.stderr

        def _pump():
            try:
                while True:
                    # 🔴 `readline()` 在二进制管道上返回 bytes（bufsize=0）
                    raw = pipe.readline()
                    if not raw:
                        break
                    line = raw.decode('utf-8', 'replace').rstrip('\r\n')
                    if line:
                        try:
                            self.on_log('[tts_cuda/stderr] %s' % line)
                        except Exception:
                            pass
            except Exception:
                pass

        t = threading.Thread(target=_pump, daemon=True)
        t.start()
        self._stderr_thread = t

    def close(self):
        p, self.proc = self.proc, None
        # 🔴🔴🔴 APP-027③：**清空消息队列**
        #   ⇒ 否则 close→start 之后，队列里还留着旧边车的消息
        #   ⇒ 新句会先读到旧句的块 ⇒ **错位**（APP-027③ 要消灭的缺陷）
        try:
            while True:
                self._q.get_nowait()
        except Exception:
            pass
        self._buf = b''
        if p is None:
            return
        try:
            if p.poll() is None:
                try:
                    with self._stdin_wlock:
                        p.stdin.write(b'{"cmd":"quit"}\n')
                        p.stdin.flush()
                except Exception:
                    pass
                try:
                    p.wait(timeout=5)
                except Exception:
                    p.kill()
        except Exception:
            pass

    # ── 协议：读者线程 + 队列（APP-027③）────────────────────────
    #
    # 🔴🔴🔴 **旧实现的三个致命缺陷**（APP-027③ 的根因）：
    #
    # ① **阻塞读永不超时**
    #    旧 `_readline(timeout=300)` 只在**两次 read 之间**检查超时
    #    ⇒ 一旦卡在 `proc.stdout.read(4096)`（等边车产出）⇒ **永不返回**
    #    ⇒ 持有 `_synth_lock` 的线程永久挂起 ⇒ **最后卡死**（用户实测
    #      10:51:37 之后 worker 再无任何合成遥测，但 cancel 仍在来）。
    #
    # ② **不核对 `rid`** ⇒ 中途 break 后边车仍在写旧句剩余块 + 旧 `done`
    #    ⇒ 下一句先读到**旧内容** ⇒ 10:51:25 id67 丢弃后 id69 只合成出
    #      3840 样本 ⇒ **从此播出内容与字幕错位**。
    #
    # ③ **没有 trace** ⇒ 无法复盘「哪一句卡在哪」。
    #
    # ⇒ 现在：**专门读者线程**读 stdout → `queue.Queue`
    #   ⇒ `generate_stream` 用 `queue.get(timeout=…)`（**真能超时**）
    #   ⇒ **严格按 `rid` 过滤**（不符的消息直接丢弃，含旧 `done`）
    #   ⇒ **看门狗**：N 秒无块 ⇒ 记日志 + 杀并重启边车 + 本句记失败
    def _start_reader(self):
        """启动**唯一的** stdout 读者线程。

        🔴🔴🔴 **必须按「字节」处理，不能按「行」处理**：
          边车的协议是「**JSON 行 + 紧跟其后的 n×4 字节 PCM**」
          ⇒ PCM 本身**没有换行符**
          ⇒ 若用 `readline()` 读，PCM 会被**下一行**的读取顺带吃掉
          ⇒ **数据错乱**（实测旧实现的 `_read_exact` 与 `_readline`
             争抢同一个 `self._buf` ⇒ 块边界随机错位）。
          ⇒ 现在：读者线程按**字节**缓冲，先切出完整 JSON 行，
            解析出 `n` 后再从缓冲里取走 `n*4` 字节的 PCM
            ⇒ **行与 PCM 各自进各自的队列**。
        """
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        pipe = proc.stdout
        q = self._q
        buf = bytearray()

        def _fill(n):
            """保证 `buf` 里至少有 n 字节；返回是否成功。"""
            while len(buf) < n:
                chunk = pipe.read(65536)
                if not chunk:
                    return False
                buf.extend(chunk)
            return True

        def _read():
            try:
                while True:
                    # ① 找完整的一行 JSON
                    while True:
                        idx = buf.find(b'\n')
                        if idx >= 0:
                            break
                        chunk = pipe.read(65536)
                        if not chunk:
                            q.put(None)
                            return
                        buf.extend(chunk)
                    line = bytes(buf[:idx])
                    del buf[:idx + 1]
                    s = line.decode('utf-8', 'replace').strip()
                    if not s:
                        continue
                    # ② 这行里若声明了 PCM 长度 ⇒ 紧接着取 PCM
                    try:
                        msg = json.loads(s)
                    except Exception:
                        q.put(s)
                        continue
                    n = 0
                    if isinstance(msg, dict):
                        try:
                            n = int(msg.get('n') or 0)
                        except Exception:
                            n = 0
                    if n > 0:
                        need = n * 4
                        if not _fill(need):
                            q.put(None)
                            return
                        pcm = bytes(buf[:need])
                        del buf[:need]
                        # 🔴🔴 **PCM 与它的 JSON 行必须成对入队**
                        #   ⇒ 否则 rid 过滤把旧句的 JSON 丢掉时，
                        #      它的 PCM 还留在队列里 ⇒ **下一句读到旧 PCM**
                        #      ⇒ 又变成「错位」⇒ APP-027③ 要消灭的那个缺陷。
                        q.put((s, pcm))
                    else:
                        q.put(s)
            except Exception as e:
                try:
                    self.on_log('[tts_cuda] stdout 读者线程退出：%s' % e)
                except Exception:
                    pass
                q.put(None)

        t = threading.Thread(target=_read, daemon=True)
        t.start()
        self._reader_thread = t

    def _q_get(self, timeout):
        """从队列取一行（**带真超时**）。

        🔴🔴🔴 APP-030③：**超时不再抛异常，而是返回哨兵**。
          - 旧实现：`queue.Empty` ⇒ **直接 `raise CudaTTSError`**
            ⇒ `generate_stream()` 用 `timeout=min(2.0, wl)` 调它
            ⇒ **任何 2 s 无块都直接判失败**
            ⇒ `WATCHDOG_FIRST_S=60` / `WATCHDOG_S=15` **从来没生效**
              （reviewer 实测：每次 CUDA 会话的**第 0 句都被丢**，
                16:31:22 / 16:47:10 `边车响应超时（2 s）`，
                而边车 3.09 s 后其实 DONE）
          - 现在：超时返回 `None`（=「暂时没消息」）
            ⇒ 调用方**回到循环** ⇒ 看门狗的时间比较分支**才真正生效**
            ⇒ 第 0 句不再丢。
        ⚠️ **「边车已退出」与「暂时没消息」要能区分**：
          读者线程在 EOF 时 `q.put(None)` ⇒ 队列里的 `None` 是**真退出**；
          而本函数的**超时**返回的是另一个哨兵 `_TIMEOUT`。
        """
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            # 🔴 APP-030③：返回哨兵，**不抛**（让看门狗按设计生效）
            return _TIMEOUT

    def _restart_sidecar(self, why: str):
        """杀掉卡死的边车并重启（**看门狗触发时调用**）。

        🔴 **必须真的杀掉**：旧边车持有 `_synth_lock` 的线程正卡在它的
        管道读上 ⇒ 不杀就永远卡住。
        """
        try:
            self.on_log('[tts_cuda] 🔴 看门狗触发（%s）⇒ 杀并重启边车' % why)
        except Exception:
            pass
        _trace('WATCHDOG restart: %s' % why)
        p, self.proc = self.proc, None
        try:
            if p is not None and p.poll() is None:
                p.kill()
                try:
                    p.wait(timeout=5)
                except Exception:
                    pass
        except Exception:
            pass
        # 清空队列里残留的旧消息（避免新句读到旧句的内容）
        try:
            while True:
                self._q.get_nowait()
        except Exception:
            pass
        self._buf = b''
        try:
            self.start()
        except Exception as e:
            raise CudaTTSError('边车重启失败：%s' % e)

    # ── 与 babelvox 同形的接口 ────────────────────────────────
    def extract_speaker_embedding(self, wav):      # 兼容旧调用路径
        return None

    def set_ref_audio(self, path: str):
        """🔴🔴🔴 APP-027⑤：切换**克隆参考音频**（CUDA 边车）。

        ⚠️ 边车**不支持取消**，但**支持换参考** ⇒ 下一句起生效。
        ⚠️ 参考音频路径可以是**临时文件**（用完即删）—— 本函数只传路径，
          **不负责**创建/删除文件。
        """
        if not path:
            return False
        self.ref_audio = path
        # 🔴 通知边车（边车侧也有 `current_ref` ⇒ 客户端重启后仍一致）
        try:
            if self.proc is not None and self.proc.poll() is None:
                # 🔴🔴🔴 APP-027⑤：**持写锁**（与 `generate_stream` 串行）
                with self._stdin_wlock:
                    self.proc.stdin.write(
                        (json.dumps({'cmd': 'set_ref', 'id': 0,
                                     'ref_audio': path},
                                    ensure_ascii=False) + '\n').encode('utf-8'))
                    self.proc.stdin.flush()
        except Exception as e:
            _trace('set_ref_audio failed: %s' % e)
            return False
        _trace('set_ref_audio: %s' % path)
        return True

    def generate_stream(self, text, language='English', speaker_embed=None,
                        speaker=None, split_on_silence=False,
                        cancel_event=None, chunk_frames=None,
                        max_new_tokens=None, est_sec=None, **_kw):
        """产出 `(list[float], 24000)`。

        🔴🔴🔴 APP-027③ 的三个改动：
        - **严格按 `rid` 过滤**（旧句的块 / 旧 `done` 一律丢弃）；
        - **队列取消息**（真能超时 ⇒ 看门狗能触发）；
        - **看门狗**：N 秒无块 ⇒ 杀并重启边车 ⇒ 本句记失败。

        🔴🔴🔴 APP-030②：**失控守卫**（两道闸）
          - **第一道闸（引擎侧）**：把 `max_new_tokens` 下发给边车
            ⇒ 库默认 2048（= 163.8 s 音频）⇒ 失控句拖 106 s
            ⇒ 客户端按句估算一个**更严**的上限下发。
          - **第二道闸（客户端侧）**：本句已收音频秒数
            > `max(3×估计, 估计+8 s)` ⇒ 判 **RUNAWAY**
            ⇒ 停止播放该句剩余部分 + 通知边车停止。
        ⚠️ `est_sec` 是**估计秒数**（由 `tts_engine.estimate_sec` 算）
          ⇒ 没传 ⇒ **不做第二道闸**（宁可漏判也不误杀）。
        """
        import array

        if not text or not text.strip():
            return
        if self.proc is None or self.proc.poll() is not None:
            self.start()

        self._rid += 1
        rid = self._rid
        req = {'id': rid, 'text': text, 'language': language,
               'ref_audio': self.ref_audio, 'chunk_size': self._chunk_size}
        # 🔴🔴🔴 APP-030②：**下发生成帧数上限**（第一道闸）
        try:
            if max_new_tokens is not None:
                mnt = int(max_new_tokens)
                if mnt > 0:
                    req['max_new_tokens'] = mnt
        except Exception:
            pass
        t_req = time.monotonic()
        _trace('REQ rid=%d len=%d mnt=%s lang=%s'
               % (rid, len(text), req.get('max_new_tokens'), language))
        try:
            # 🔴🔴🔴 APP-027⑤：**持写锁**（与 `set_ref_audio` 串行）
            with self._stdin_wlock:
                self.proc.stdin.write(
                    (json.dumps(req, ensure_ascii=False) + '\n').encode('utf-8'))
                self.proc.stdin.flush()
        except Exception as e:
            _trace('ERR rid=%d send failed: %s' % (rid, e))
            raise CudaTTSError('向 CUDA 边车发送请求失败：%s' % e)
        n_chunks = 0
        t_first = None
        last_seen = time.monotonic()
        # 🔴 APP-030②：**本句已收音频秒数**（RUNAWAY 判据的输入）
        got_sec = 0.0
        # 🔴 APP-030②：RUNAWAY 阈值（秒）；`None` ⇒ 不做第二道闸
        runaway_s = None
        if est_sec is not None:
            try:
                runaway_s = runaway_threshold_s(est_sec)
            except Exception:
                runaway_s = None
        while True:
            # 🔴 取消检查：**每条消息之前**都查一次
            if cancel_event is not None and getattr(
                    cancel_event, 'is_set', lambda: False)():
                # 取消：本句剩余块直接丢弃（不出声），记账由 worker 负责
                try:
                    self.on_log('[tts_cuda] 收到取消 ⇒ 丢弃本句剩余音频')
                except Exception:
                    pass
                _trace('CANCEL rid=%d chunks=%d' % (rid, n_chunks))
                # 🔴🔴 APP-027③：取消后**必须把本请求的剩余部分读完并丢掉**
                #   （否则边车还在写旧句的块 ⇒ 下一句会读到 ⇒ 错位）。
                #   ⇒ 交给**后台排空线程**（不占合成锁、不阻塞下一句）。
                self._start_drain(rid)
                return
            # 🔴🔴 看门狗：首块用宽松阈值，后续用常规阈值
            wl = WATCHDOG_FIRST_S if t_first is None else WATCHDOG_S
            now = time.monotonic()
            if now - last_seen > wl:
                # 🔴🔴 APP-027③：**不是直接抛异常**，而是**杀并重启边车**
                #   ⇒ 本句记失败（由调用方处理）⇒ **后续句子还能用**。
                try:
                    self.on_log('[tts_cuda] 🔴 边车 %.0f s 无任何输出（rid=%d）'
                                % (now - last_seen, rid))
                except Exception:
                    pass
                _trace('WATCHDOG rid=%d waited=%.1fs chunks=%d'
                       % (rid, now - last_seen, n_chunks))
                try:
                    self._restart_sidecar('rid=%d 无输出 %.1f s'
                                          % (rid, now - last_seen))
                except Exception as e:
                    _trace('WATCHDOG restart failed: %s' % e)
                    raise CudaTTSError('边车看门狗触发且重启失败：%s' % e)
                raise CudaTTSError('边车看门狗触发（%.0f s 无输出，已重启边车）'
                                   % (now - last_seen))
            line = self._q_get(timeout=min(2.0, wl))
            # 🔴🔴🔴 APP-030③：**超时 = 回到循环**（不是失败）
            #   ⇒ 看门狗的 `now - last_seen > wl` 分支**才真正生效**
            #   ⇒ 第 0 句不再因为「2 s 内没块」被丢
            #   （reviewer 实测每次 CUDA 会话第 0 句都被丢）。
            if line is _TIMEOUT:
                continue
            if line is None:
                raise CudaTTSError('CUDA 边车意外退出（无响应）')
            last_seen = time.monotonic()
            # 🔴 队列里可能是「(JSON 行, PCM 字节)」的**配对**（带 PCM 的块）
            pcm = None
            if isinstance(line, tuple):
                line, pcm = line
            try:
                msg = json.loads(line)
            except Exception:
                continue
            # 🔴🔴🔴 **严格按 rid 过滤**（APP-027③ 的第 2 条硬要求）。
            #   边车的协议**本来就带 `id`**（`send_chunk` 发 `{'id': rid, ...}`，
            #   `done` / `error` 也带 rid）⇒ 旧实现**不核对**是客户端的 bug。
            msg_rid = msg.get('id')
            if msg_rid is not None and msg_rid != rid:
                # 不属于本句 ⇒ **丢掉**（含旧句的 `done` 与旧句的 PCM）
                _trace('DROP rid=%d got_rid=%s' % (rid, msg_rid))
                continue
            if 'error' in msg:
                _trace('ERR rid=%d %s' % (rid, msg['error']))
                raise CudaTTSError('CUDA 合成失败：%s' % msg['error'])
            if msg.get('done'):
                # 🔴🔴🔴 APP-030⑤：**结束原因**（eos | cap）
                #   边车回报 `frames`（实际帧数）与 `end_reason`
                #   ⇒ `cap` = 撞上限被截断 ⇒ **异常句** ⇒ 落盘
                end_reason = msg.get('end_reason') or 'eos'
                frames = msg.get('frames')
                try:
                    frames = int(frames) if frames is not None else None
                except Exception:
                    frames = None
                self._last_end_reason = end_reason
                self._last_frames = frames
                _trace('DONE rid=%d chunks=%d frames=%s reason=%s first_s=%.2f'
                       % (rid, n_chunks, frames, end_reason,
                          (t_first - t_req) if t_first else -1))
                return
            n = int(msg.get('n') or 0)
            sr = int(msg.get('sr') or 24000)
            if not n:
                continue
            if pcm is None:
                raise CudaTTSError('边车块缺少 PCM 数据（rid=%d）' % rid)
            arr = array.array('f')
            arr.frombytes(pcm)
            if sys.byteorder != 'little':
                arr.byteswap()
            if t_first is None:
                t_first = time.monotonic()
            n_chunks += 1
            # 🔴🔴🔴 APP-030②：**第二道闸（RUNAWAY）**
            #   判据（APP-030② 明文）：本句已收音频
            #   > max(3×估计, 估计+8 s) ⇒ 判 RUNAWAY
            #   ⇒ **停止播放该句剩余部分**，并让边车停止（cancel）
            got_sec += len(arr) / float(sr or 24000)
            if runaway_s is not None and got_sec > runaway_s:
                _trace('RUNAWAY rid=%d len=%d frames=%d got_s=%.1f thr=%.1f'
                       % (rid, len(text),
                          int(got_sec * 12), got_sec, runaway_s))
                try:
                    self.on_log('[tts_cuda] 🔴 RUNAWAY rid=%d len=%d 音频 %.1f s '
                                '> 阈值 %.1f s ⇒ 中止本句'
                                % (rid, len(text), got_sec, runaway_s))
                except Exception:
                    pass
                # 让边车停止（**做不到就杀掉重启**）⇒ 见 `_cancel_request`
                self._cancel_request(rid)
                self._last_end_reason = 'runaway'
                return
            yield (list(arr), sr)

    def _cancel_request(self, rid):
        """🔴🔴🔴 APP-030② + §90：**让边车停止当前请求**。

        APP-030② 明文：「**加 cancel 命令，边车每块检查一次；做不到就杀掉重启**」
        ⇒ 这两句**都必须实现**。

        🔴🔴🔴 §90：**修掉「写命令成功就直接 return」的空壳兜底**
          旧实现：写命令**成功** ⇒ `return` ⇒ **永远不会**触发「杀掉重启」
          ⇒ 即使边车**根本不处理** `cancel`（修前的真实状态：
             边车主循环阻塞在生成器里 ⇒ 命令在生成结束前根本读不到），
             客户端也**以为**取消已生效 ⇒ 失控句照跑 106 s，
             后续句继续被堵 1~2 分钟。
          现在：**发命令 ⇒ 等边车回 `{'cancelled': true}` 确认 ⇒ 确认了才算数**；
          **等不到确认 ⇒ 杀掉并重启边车**（兜底兑现）。
        """
        if self.proc is None or self.proc.poll() is not None:
            # 边车已经没了 ⇒ 无需取消（但也不该静默返回 ⇒ 走兜底）
            self._cancel_kill(rid, '边车已退出')
            return
        try:
            with self._stdin_wlock:
                self.proc.stdin.write(
                    (json.dumps({'cmd': 'cancel', 'id': rid},
                                ensure_ascii=False) + '\n').encode('utf-8'))
                self.proc.stdin.flush()
            _trace('CANCEL_SENT rid=%d' % rid)
        except Exception as e:
            _trace('CANCEL_SENT failed rid=%d: %s' % (rid, e))
            self._cancel_kill(rid, '写 cancel 命令失败')
            return
        # 🔴🔴🔴 §90：**等确认**（不确认就当没取消成功 ⇒ 走兜底）
        ack = self._wait_cancel_ack(rid, timeout=CANCEL_ACK_TIMEOUT_S)
        if ack:
            _trace('CANCEL_ACK rid=%d' % rid)
            return
        _trace('CANCEL_NO_ACK rid=%d ⇒ 杀并重启边车' % rid)
        self._cancel_kill(rid, '等不到 cancel 确认')

    def _wait_cancel_ack(self, rid, timeout):
        """等待边车回 `{'id': rid, 'cancelled': true}` 确认。

        🔴 §90：**必须有真超时**（不能白等）⇒ 返回 True/False。
        ⚠️ 排空期间**只认本 rid 的确认**（其它 rid 的消息**不能丢**
           ⇒ 见 `_start_drain` 的同类缺陷）。
        """
        deadline = time.monotonic() + max(0.1, float(timeout))
        while time.monotonic() < deadline:
            remain = deadline - time.monotonic()
            line = self._q_get(timeout=min(0.5, max(0.05, remain)))
            if line is _TIMEOUT:
                continue
            if line is None:
                return False            # 边车退出 ⇒ 视为没确认
            if isinstance(line, tuple):
                line = line[0]
            try:
                msg = json.loads(line)
            except Exception:
                continue
            if not isinstance(msg, dict):
                continue
            if msg.get('cancelled') and msg.get('id') == rid:
                return True
        return False

    def _cancel_kill(self, rid, why):
        """兜底：**杀掉并重启边车**（必须真的杀，否则边车还在算这一句）。"""
        try:
            self.on_log('[tts_cuda] 🔴 cancel 未生效（%s）⇒ 杀并重启边车' % why)
        except Exception:
            pass
        try:
            self._restart_sidecar('RUNAWAY rid=%d（%s）' % (rid, why))
            _trace('CANCEL_KILL rid=%d' % rid)
        except Exception as e:
            _trace('CANCEL_KILL failed rid=%d: %s' % (rid, e))

    def _q_put_front(self, item):
        """🔴🔴🔴 §90：把消息**插回队首**（保序 + 立刻唤醒等待者）。

        ⚠️ 为什么不能简单 `put()`（插队尾）：
          插队尾会把**旧消息排到新消息之后** ⇒ 下一句的音频块**乱序**
          ⇒ 播出来的音频顺序错乱。
        ⚠️ 为什么不能直接丢弃：
          丢的是**别的 rid 的消息** ⇒ 下一句**少块或整句无输出**（静默丢音频）。
        ⇒ 队首插回 = **顺序正确 + 不丢 + 立刻唤醒**。
        """
        try:
            with self._q.mutex:
                self._q.queue.appendleft(item)
                self._q.not_empty.notify()
            return True
        except Exception:
            try:
                self._q.put(item)
                return True
            except Exception:
                return False

    def _start_drain(self, rid):
        """🔴🔴 APP-027③：取消后**后台排空**本请求的剩余消息。

        ⚠️ 边车**不支持取消** ⇒ 本请求的剩余块与 `done` 仍会到达
        ⇒ 必须读完并丢掉 ⇒ 否则**下一句会读到旧句的内容** ⇒ 错位。
        ⇒ 用**后台线程**排空 ⇒ 不占合成锁、不阻塞下一句。

        🔴🔴🔴 §90：**修掉「排空线程偷走并丢弃下一句的消息」**
          旧实现：拿到消息后判 `mr != rid` ⇒ **`continue`（直接丢弃）**
          ⇒ 排空线程与主合成线程**共用** `self._q`
          ⇒ 排空线程会把**下一句刚到的块 / cancel 确认**当成「别人的」丢掉
          ⇒ 下一句**少块或整句无输出**（静默丢音频）。
          修法：**不是本 rid 的消息 ⇒ 插回队首**（保序 + 不丢 + 唤醒等待者）。
        """
        def _drain():
            deadline = time.monotonic() + 30.0
            while time.monotonic() < deadline:
                try:
                    item = self._q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if item is None:
                    return
                line = item[0] if isinstance(item, tuple) else item
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                mr = msg.get('id')
                if mr is not None and mr != rid:
                    # 🔴 §90：**不是本句的 ⇒ 插回队首**（不能丢！）
                    self._q_put_front(item)
                    continue
                if msg.get('done'):
                    _trace('DRAIN done rid=%d' % rid)
                    return
            _trace('DRAIN timeout rid=%d' % rid)

        t = threading.Thread(target=_drain, daemon=True)
        t.start()
