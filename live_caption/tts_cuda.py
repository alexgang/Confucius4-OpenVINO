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

        line = self._readline(timeout=READY_TIMEOUT_S)
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
        if p is None:
            return
        try:
            if p.poll() is None:
                try:
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

    # ── 协议 ──────────────────────────────────────────────────
    def _readline(self, timeout=None):
        """读一行 JSON（二进制读，避免文本层多读把 PCM 吃掉）。"""
        buf = getattr(self, '_buf', b'')
        t0 = time.monotonic()
        while b'\n' not in buf:
            if self.proc is None:
                return None
            if timeout is not None and time.monotonic() - t0 > timeout:
                raise CudaTTSError('边车响应超时（%.0f s）' % timeout)
            chunk = self.proc.stdout.read(4096)
            if not chunk:
                self._buf = b''
                return None
            buf += chunk
        line, buf = buf.split(b'\n', 1)
        self._buf = buf
        return line.decode('utf-8', 'replace')

    def _read_exact(self, n):
        buf = getattr(self, '_buf', b'')
        while len(buf) < n:
            chunk = self.proc.stdout.read(n - len(buf))
            if not chunk:
                self._buf = b''
                raise CudaTTSError('边车在传输 PCM 时断开')
            buf += chunk
        out, self._buf = buf[:n], buf[n:]
        return out

    # ── 与 babelvox 同形的接口 ────────────────────────────────
    def extract_speaker_embedding(self, wav):      # 兼容旧调用路径
        return None

    def generate_stream(self, text, language='English', speaker_embed=None,
                        speaker=None, split_on_silence=False,
                        cancel_event=None, chunk_frames=None, **_kw):
        """产出 `(list[float], 24000)`；`speaker_embed` / `speaker` 在本后端**不使用**
        （音色由 `ref_audio` 的 x-vector 决定，见 `USES_REF_AUDIO`）。"""
        import array

        if not text or not text.strip():
            return
        if self.proc is None or self.proc.poll() is not None:
            self.start()

        self._rid += 1
        rid = self._rid
        req = {'id': rid, 'text': text, 'language': language,
               'ref_audio': self.ref_audio, 'chunk_size': self._chunk_size}
        try:
            self.proc.stdin.write(
                (json.dumps(req, ensure_ascii=False) + '\n').encode('utf-8'))
            self.proc.stdin.flush()
        except Exception as e:
            raise CudaTTSError('向 CUDA 边车发送请求失败：%s' % e)

        while True:
            if cancel_event is not None and getattr(cancel_event, 'is_set', lambda: False)():
                # 取消：本句剩余块直接丢弃（不出声），记账由 worker 负责
                self.on_log('[tts_cuda] 收到取消 ⇒ 丢弃本句剩余音频')
                return
            line = self._readline(timeout=300)
            if line is None:
                raise CudaTTSError('CUDA 边车意外退出（无响应）')
            msg = json.loads(line)
            if 'error' in msg:
                raise CudaTTSError('CUDA 合成失败：%s' % msg['error'])
            if msg.get('done'):
                return
            n = int(msg.get('n') or 0)
            sr = int(msg.get('sr') or 24000)
            if not n:
                continue
            raw = self._read_exact(n * 4)
            arr = array.array('f')
            arr.frombytes(raw)
            if sys.byteorder != 'little':
                arr.byteswap()
            yield (list(arr), sr)
