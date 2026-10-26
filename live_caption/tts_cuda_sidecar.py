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

        rid = req.get('id')
        text = (req.get('text') or '').strip()
        if not text:
            send({'id': rid, 'done': True})
            continue
        ref = req.get('ref_audio') or DEFAULT_REF
        try:
            # 🔴 只缓存**一块**：收到新块才发旧块（这样才能给最后一块打 last=True，
            #    且**绝不重复发送**同一块）。流式语义不受影响（滞后 1 块）。
            n = 0
            pending = None
            for chunk, sr, _timing in model.generate_voice_clone_streaming(
                    text=text, language=_lang(req.get('language')),
                    ref_audio=ref, xvec_only=True,
                    chunk_size=int(req.get('chunk_size') or 8)):
                if pending is not None:
                    send_chunk(pending[0], pending[1], False, rid)
                    n += 1
                pending = (chunk, sr)
            if pending is not None:
                send_chunk(pending[0], pending[1], True, rid)
                n += 1
            send({'id': rid, 'done': True, 'chunks': n})
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            send({'id': rid, 'error': '%s: %s' % (type(e).__name__, e)})


if __name__ == '__main__':
    sys.exit(main())
