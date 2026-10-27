#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CUDA-TTS 边车（sidecar）—— **用独立 venv 的 python 跑 PyTorch+CUDA 合成**。

为什么要有它（而不是直接 import）：
  - 客户包的 python **没有 torch**（也不该塞进去：+4.2 GB 且与包内 transformers 冲突）；
  - CUDA 后端需要 `torch>=2.5.1(cu128)` + **`transformers==5.15.1`**（钉版，见 STATUS §40）；
  - ⇒ 只能放在**独立 venv**（默认 `C:\\Users\\Trekker-PTL\\_fq3tts_env`），
    由 App 以**子进程**方式调用，模型只加载一次、常驻服务。

协议（**长度前缀 + 二进制 PCM**，不用 base64 免得翻倍）：
  ① 启动：`{"ready": true, "load_s": .., "warmup_s": .., "device": ..}`
  ② 请求（一行 UTF-8 JSON）：`{"id": 1, "text": "...", "language": "Chinese",
     "ref_audio": "C:\\...\\preset_A.wav", "chunk_size": 8}`
  ③ 响应块：`{"id": 1, "sr": 24000, "n": 12000, "last": false}` + **n*4 字节 float32 LE**
  ④ 结束：`{"id": 1, "done": true}`
  ⑤ 出错：`{"id": 1, "error": "..."}`（不崩进程，下一句还能用）

🔴 **stdout 只能走协议**：第三方库（transformers / tqdm）会往 stdout 打印
   ⇒ 启动时立刻 `sys.stdout = sys.stderr`，真正的协议出口留在 `out = sys.stdout.buffer`。
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

# ── 0. 先把 stdout 保护起来（第三方 print 一律改道 stderr）────────────────
_out = sys.stdout.buffer
sys.stdout = sys.stderr

# 🔴🔴 APP-021§54.10：**stderr 改成「字节透传」**，绕开 Python 文本编码。
#   起因（实测 16:36 会话日志）：stderr 里出现
#     一行以 `'sox' ` 开头、后面跟一串 U+FFFD 替换字符的乱码
#   ⇒ 那不是「解码方式不对」，而是**字节在上游就被破坏了**。
#   完整链路（实测）：
#     ① `sox` 包初始化时执行 `os.popen('sox -h')`（**文本模式**）
#        ⇒ cmd.exe 找不到 sox ⇒ 用**系统 locale（cp936）**写中文报错
#           `'sox' 不是内部或外部命令，也不是可运行的程序`（**GBK 字节**）
#     ② `os.popen` 文本模式按 `locale.getpreferredencoding(False)` 解码
#        ⇒ 本 venv 是 **utf-8** ⇒ GBK 字节解成 **U+FFFD（不可恢复！）**
#     ③ `logger.warning(...)` 再用 UTF-8 编码输出 ⇒ 已是替换符 ⇒ 永久乱码
#   ⇒ **在 service 侧怎么改都救不回来**（U+FFFD 不可逆）
#   ⇒ 修法：把 `sys.stderr` 换成「直接写字节」的代理
#     ⇒ 第三方 `print(..., file=sys.stderr)` 的文本按 **utf-8** 编码成字节，
#       **不经过文本解码** ⇒ 不会产生 U+FFFD；
#     ⇒ 而 cmd.exe 的**原始 GBK 字节**（os.popen 内部直写 fd 2）**原样透传**
#       ⇒ 由主进程侧按「utf-8 严格 → gb18030 严格」逐行判定（见
#         `tts_service._decode_worker_line`）⇒ **两边都正确**。
#   ⚠️ 必须**在 import 任何第三方库之前**做（`sox` 包在 import 时就会触发）。
class _RawStderr:
    """把文本按 UTF-8 写成**字节**的 stderr 代理（不经过文本层）。"""

    def __init__(self, raw):
        self._raw = raw

    def write(self, s):
        try:
            if isinstance(s, str):
                s = s.encode('utf-8', 'replace')
            self._raw.write(s)
        except Exception:
            pass
        return len(s) if isinstance(s, (bytes, bytearray)) else 0

    def flush(self):
        try:
            self._raw.flush()
        except Exception:
            pass

    def isatty(self):
        return False

    def fileno(self):
        return self._raw.fileno()


try:
    _raw_err = getattr(sys.stderr, 'buffer', None)
    if _raw_err is not None:
        sys.stderr = _RawStderr(_raw_err)
except Exception:
    pass

os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_VERBOSITY', 'error')
os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS', '1')
os.environ.setdefault('TQDM_DISABLE', '1')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')

MODEL_ID = os.environ.get('LIVECAP_CUDA_TTS_MODEL',
                          'Qwen/Qwen3-TTS-12Hz-0.6B-Base')

# 🔴🔴 §48：**不写死客户包版本号**。
# 原代码写死 `...\Confucius4_LiveCaption_v1.5`
# ⇒ ① 客户机上的包是别的版本/别的路径 ⇒ 音色文件找不到；
# ⇒ ② 仓库升版本后这行不跟着变 ⇒ 又一次指向旧包。
#
# 推导顺序（与 `tts_cuda.py::default_pkg_dir()` **同规则**）：
#   1. 环境变量 `LIVECAP_PKG`（客户端 `tts_cuda.py` 启动边车时**必设**
#      ⇒ 客户机上就是**包根**，最可靠）；
#   2. 从本文件所在目录**逐级向上**找含 `models/` 的目录
#      （客户机命中 `<包根>`；开发机深度不同 ⇒ 不能写死层数）；
#   3. 在**用户主目录**里挑**版本号最大**且含 `models/` 的包（开发机）。
#
# ⚠️ 本文件**在客户包里**⇒ 不能 import 仓库根的 `pkg_paths.py`（包里没有它）
# ⇒ 只做纯 stdlib 推导。
def _looks_like_pkg(d):
    # 🔴 判据 = **同时**有 `app/` 和 `models/`（仓库根只有 `models/` ⇒ 别误判）
    return (bool(d)
            and os.path.isdir(os.path.join(d, 'app'))
            and os.path.isdir(os.path.join(d, 'models')))


def _discover_pkg_dir() -> str:
    env = os.environ.get('LIVECAP_PKG', '').strip()
    if env:
        return os.path.abspath(env)

    here = os.path.dirname(os.path.abspath(__file__))
    d = os.path.abspath(here)
    for _ in range(6):
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
        if _looks_like_pkg(d):
            return d

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


PKG = _discover_pkg_dir()
DEFAULT_REF = os.path.join(PKG, 'models', 'qwen3tts', 'voices', 'preset_A.wav')

_LANG = {
    'zh': 'Chinese', 'chinese': 'Chinese',
    'en': 'English', 'english': 'English',
    'ja': 'Japanese', 'japanese': 'Japanese',
    'ko': 'Korean', 'korean': 'Korean',
}

#: 🔴🔴🔴 APP-030②：**兜底的生成帧数上限**
#:   客户端没传 `max_new_tokens` 时用它（**不是**库的默认 2048）。
#:   2048 帧 = 163.8 s 音频（12 fps）⇒ reviewer 实测一句 7 字日文
#:   跑了 106.61 s / 255 块 / 163.0 s 音频 ⇒ 后续句全被堵住。
#:   ⇒ 这里取 512（≈42.7 s）作为「没有估算可用时的保守上限」。
DEFAULT_MAX_NEW_TOKENS = int(
    os.environ.get('LIVECAP_CUDA_MAX_NEW_TOKENS', '512'))

#: 🔴🔴🔴 APP-030②：**待取消的请求 id 集合**
#:   边车**串行**处理（一次一句）⇒ 取消命令只能在**当前句的解码循环**
#:   里被检查 ⇒ 用模块级集合。
#:   ⚠️ 客户端会「先发 cancel ⇒ 不行就杀并重启边车」⇒ 两条路都堵死。
_CANCEL_RIDS = set()


def _lang(s):
    t = (s or 'auto').strip().lower()
    if t.startswith('zh') or t.startswith('chinese'):
        return 'Chinese'
    if t.startswith('en') or t.startswith('english'):
        return 'English'
    if t.startswith('ja') or t.startswith('japanese'):
        return 'Japanese'
    if t.startswith('ko') or t.startswith('korean'):
        return 'Korean'
    return _LANG.get(t, 'Auto')


def send(obj):
    _out.write((json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8'))
    _out.flush()


def send_chunk(arr, sr, last, rid):
    import numpy as np
    a = np.ascontiguousarray(np.asarray(arr, dtype='<f4').reshape(-1))
    send({'id': rid, 'sr': int(sr), 'n': int(a.size), 'last': bool(last)})
    _out.write(a.tobytes())
    _out.flush()


# 🔴🔴🔴 APP-027③：**逐请求 trace**（边车侧）。
#   记录：rid、收到请求时刻、第一块、done、块数、异常。
#   ⚠️ **只写 stderr**（stdout 是协议出口 ⇒ 不能混）。
#   ⚠️ 落盘由**客户端**（`tts_cuda.py`）做 `tts_cuda_trace.log`；
#      这里只把**边车内部**的时序打进 stderr ⇒ 客户端的 stderr 泵会转进 on_log。
def _trace(msg):
    try:
        print('[sidecar] %s' % msg, file=sys.stderr, flush=True)
    except Exception:
        pass


def main() -> int:
    t0 = time.monotonic()
    import torch
    from faster_qwen3_tts import FasterQwen3TTS

    if not torch.cuda.is_available():
        send({'fatal': 'torch.cuda.is_available() = False（CUDA 不可用）'})
        return 2

    model = FasterQwen3TTS.from_pretrained(
        MODEL_ID, device='cuda', dtype='bfloat16', local_files_only=True)
    load_s = time.monotonic() - t0
    t1 = time.monotonic()
    try:
        model.warmup(prefill_len=100)      # 捕获 CUDA Graph（稳态才快）
    except Exception as e:                  # warmup 失败不致命，只是第一句慢
        print('[sidecar] warmup 失败（忽略）：%s' % e, file=sys.stderr)
    warmup_s = time.monotonic() - t1

    send({'ready': True, 'load_s': round(load_s, 2),
          'warmup_s': round(warmup_s, 2),
          'device': torch.cuda.get_device_name(0),
          'torch': torch.__version__, 'model': MODEL_ID})

    # 🔴🔴🔴 APP-027⑤：**当前克隆参考音频**（可在会话中切换）。
    #   默认是预设 A；客户端可用 `set_ref` 命令换掉 ⇒ 下一句起生效。
    #   ⚠️ **只存在内存里**，**不落盘**（隐私：APP-022「共用约定」）。
    current_ref = DEFAULT_REF

    stdin = sys.stdin.buffer
    while True:
        line = stdin.readline()
        if not line:
            return 0                        # 父进程关了 stdin ⇒ 退出
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line.decode('utf-8'))
        except Exception as e:
            send({'error': 'bad request: %s' % e})
            continue
        if req.get('cmd') == 'ping':
            send({'id': req.get('id'), 'pong': True})
            continue
        if req.get('cmd') == 'quit':
            return 0
        # 🔴🔴🔴 APP-027⑤：**切换克隆参考音频**
        #   ⚠️ 边车**不支持取消**，但**支持换参考** ⇒ 下一句起生效。
        #   ⚠️ 路径可能是**临时文件**（客户端负责删除）⇒ 这里不校验存在性
        #      （失败会在合成时报出来，由客户端显式回落预设 A）。
        if req.get('cmd') == 'set_ref':
            new_ref = req.get('ref_audio')
            if new_ref:
                current_ref = new_ref
                _trace('set_ref: %s' % current_ref)
            send({'id': req.get('id'), 'set_ref': True,
                  'ref_audio': current_ref})
            continue
        # 🔴🔴🔴 APP-030②：**取消当前请求**（失控守卫的第二道闸）
        #   ⚠️ 边车**是串行**的（一次只处理一句）⇒ 取消命令只能在
        #      **当前句的解码循环里**被检查 ⇒ 用一个模块级标志位。
        #   ⇒ 客户端「先发 cancel ⇒ 不行就杀并重启」（见 `tts_cuda._cancel_request`）
        if req.get('cmd') == 'cancel':
            _CANCEL_RIDS.add(req.get('id'))
            _trace('cancel: %s' % req.get('id'))
            send({'id': req.get('id'), 'cancelled': True})
            continue

        rid = req.get('id')
        text = (req.get('text') or '').strip()
        t_req = time.monotonic()
        if not text:
            send({'id': rid, 'done': True})
            continue
        ref = req.get('ref_audio') or current_ref
        # 🔴🔴🔴 APP-030②：**生成帧数上限**（失控守卫的第一道闸）
        #   旧实现**从不传** ⇒ 用库默认 `max_new_tokens=2048`
        #   ⇒ **2048 帧 = 163.8 s 音频**（12 fps）
        #   ⇒ reviewer 实测：一句 7 字日文跑了 **106.61 s**、255 块、163.0 s 音频
        #   ⇒ 且**边车串行** ⇒ 后续句全部排队堵住 1~2 分钟
        #   ⇒ 现在客户端按句估算上限并下发 ⇒ 失控句几秒内被截断。
        try:
            mnt = int(req.get('max_new_tokens') or 0)
        except Exception:
            mnt = 0
        if mnt <= 0:
            mnt = DEFAULT_MAX_NEW_TOKENS
        mnt = max(48, min(2048, mnt))
        _trace('REQ rid=%s len=%d mnt=%d ref=%s' % (rid, len(text), mnt, ref))
        try:
            # 🔴 只缓存**一块**：收到新块才发旧块（这样才能给最后一块打 last=True，
            #    且**绝不重复发送**同一块）。流式语义不受影响（滞后 1 块）。
            n = 0
            pending = None
            t_first = None
            # 🔴🔴🔴 APP-030⑤：**实际帧数**（12 fps codec 帧）
            #   `timing['total_steps_so_far']` 是库给的累计步数
            #   ⇒ 用来判「撞上限」：`frames >= max_new_tokens` ⇒ 截断（cap）
            #     否则 ⇒ 正常 EOS（eos）
            frames = 0
            cancelled = False
            for chunk, sr, timing in model.generate_voice_clone_streaming(
                    text=text, language=_lang(req.get('language')),
                    ref_audio=ref, xvec_only=True,
                    max_new_tokens=mnt,
                    chunk_size=int(req.get('chunk_size') or 8)):
                # 🔴🔴🔴 APP-030②：**每块检查一次取消**（失控守卫）
                if rid in _CANCEL_RIDS:
                    _CANCEL_RIDS.discard(rid)
                    cancelled = True
                    _trace('CANCELLED rid=%s chunks=%d frames=%d'
                           % (rid, n, frames))
                    break
                try:
                    ts = int((timing or {}).get('total_steps_so_far') or 0)
                    if ts > frames:
                        frames = ts
                except Exception:
                    pass
                if pending is not None:
                    send_chunk(pending[0], pending[1], False, rid)
                    n += 1
                pending = (chunk, sr)
            if cancelled:
                send({'id': rid, 'done': True, 'chunks': n,
                      'frames': int(frames), 'max_new_tokens': int(mnt),
                      'end_reason': 'cancel'})
                continue
            if pending is not None:
                send_chunk(pending[0], pending[1], True, rid)
                n += 1
                t_first = time.monotonic()
            # 🔴🔴🔴 APP-030⑤：**结束原因**（eos | cap）
            #   `frames >= max_new_tokens` ⇒ **撞上限被截断**（cap）
            #   ⇒ 客户端据此判「异常句」并落盘（APP-030⑤）
            reason = 'cap' if frames >= mnt else 'eos'
            send({'id': rid, 'done': True, 'chunks': n,
                  'frames': int(frames), 'max_new_tokens': int(mnt),
                  'end_reason': reason})
            _trace('DONE rid=%s chunks=%d frames=%d mnt=%d reason=%s elapsed=%.2fs'
                   % (rid, n, frames, mnt, reason,
                      (t_first - t_req) if t_first else -1))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            _trace('ERR rid=%s %s: %s' % (rid, type(e).__name__, e))
            send({'id': rid, 'error': '%s: %s' % (type(e).__name__, e)})


if __name__ == '__main__':
    sys.exit(main())
