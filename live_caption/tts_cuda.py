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
import time

ENV_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')
SIDECAR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'tts_cuda_sidecar.py')
READY_TIMEOUT_S = float(os.environ.get('LIVECAP_CUDA_READY_S', '180'))


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
        pkg = pkg_dir or os.environ.get(
            'LIVECAP_PKG', r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5')
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
        env['LIVECAP_PKG'] = os.environ.get('LIVECAP_PKG', '') or os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))

        t0 = time.monotonic()
        self.on_log('[tts_cuda] 启动 CUDA 边车：%s' % self._py)
        self.proc = subprocess.Popen(
            [self._py, SIDECAR], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL if os.environ.get('LIVECAP_CUDA_QUIET') else None,
            env=env, bufsize=0)

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
