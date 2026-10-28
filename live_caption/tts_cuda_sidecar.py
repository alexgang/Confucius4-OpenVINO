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

🔴🔴🔴 §89：**结束判据是 ④ 的 `done`，不是 ③ 的 `last`**。
   `last` 是旧实现留下的字段（旧边车为了给最后一块打标记而**扣住一块**），
   但**全仓库 / 客户包 / TTS 模块都没有任何代码读它**
   ⇒ 旧实现为它付出的代价（**首块被挡一块**）是**纯浪费**
   ⇒ 现已**删掉扣留**（每块产出来就下发），`last` 恒为 `false`（线格式兼容）。

🔴 **stdout 只能走协议**：第三方库（transformers / tqdm）会往 stdout 打印
   ⇒ 启动时立刻 `sys.stdout = sys.stderr`，真正的协议出口留在 `out = sys.stdout.buffer`。
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
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
#:
#: 🔴🔴🔴 §90：**修掉「cancel 永远不可达」**
#:   旧实现的致命点：边车主循环**只在两次请求之间**读 stdin
#:   ⇒ 生成期间（`generate_voice_clone_streaming`）主循环**被阻塞**
#:   ⇒ `{'cmd':'cancel'}` 这行 JSON **在生成结束前根本不会被读到**
#:   ⇒ `_CANCEL_RIDS` 在本次生成期间**恒为空**
#:   ⇒ 「边车每块检查一次」= **永远为 False** = **从未生效**
#:   ⇒ APP-030② 的「做不到就杀掉重启」在客户端侧也没实现（写命令成功就 return）
#:   ⇒ **合起来：失控守卫在 CUDA 路径上从未成立**
#:   （reviewer 实测：一句 7 字日文跑 106.61 s / 255 块，把后续句全堵住）
#:
#:   修法：**独立命令读取线程**（daemon）持续读 stdin ⇒ 命令在生成期间
#:   也能到达；生成循环**每块检查一次** `_CANCEL_RIDS`。
#:   ⚠️ 线程安全：`_CANCEL_RIDS` 的读写都用**同一把锁**保护
#:   （读线程写、主循环读 ⇒ 否则 CPython 的 set 操作虽原子，
#:      但「读-判断-删」三步之间可能被插入 ⇒ 取消标志被吞）。
#:   ⚠️ **命令处理与生成是两条路径**：`cancel` / `set_ref` 由读线程直接处理；
#:      **合成请求**仍必须由主循环串行处理（边车一次只做一句）。
#:      ⇒ 读线程**只处理控制类命令**，遇到合成请求就**放回队列**给主循环。
_CANCEL_RIDS = set()
_CANCEL_LOCK = threading.Lock()

#: 🔴 §90：**待主循环处理的合成请求**（由命令读取线程投递）
_REQ_Q: 'queue.Queue' = queue.Queue()

#: 🔴 §90：**协议写锁**
#:   §90 起有**两条线程**会写 stdout（主循环发块 / 读线程回 ack）
#:   ⇒ 不加锁 ⇒ JSON 行与 PCM 字节**交错** ⇒ 客户端协议解析错乱。
_OUT_LOCK = threading.Lock()

#: 🔴 §90：**当前克隆参考音频**（读线程可改 ⇒ 用锁保护）
_REF_LOCK = threading.Lock()
_CURRENT_REF = None

#: 🔴 §90：**退出标志**（读线程收到 `quit` 时置位）
_EXIT = threading.Event()


def _get_ref():
    with _REF_LOCK:
        return _CURRENT_REF or DEFAULT_REF


def _set_ref(path):
    global _CURRENT_REF
    with _REF_LOCK:
        _CURRENT_REF = path
        return _CURRENT_REF


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
    with _OUT_LOCK:
        _out.write((json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8'))
        _out.flush()


def send_chunk(arr, sr, last, rid):
    import numpy as np
    a = np.ascontiguousarray(np.asarray(arr, dtype='<f4').reshape(-1))
    # 🔴 §90：**头与 PCM 必须原子写出**（否则与 ack 行交错 ⇒ 协议解析错乱）
    with _OUT_LOCK:
        _out.write((json.dumps({'id': rid, 'sr': int(sr), 'n': int(a.size),
                                'last': bool(last)},
                               ensure_ascii=False) + '\n').encode('utf-8'))
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


# 🔴🔴🔴 §90：**控制命令处理**（由**命令读取线程**调用）。
#:   ⚠️ 这些命令**必须能与生成并行** ⇒ cancel 才可能真的生效。
#:   ⚠️ 合成请求**不在这里处理**（边车一次只做一句 ⇒ 交给主循环串行）。
def _handle_control(req):
    """处理控制类命令。返回 True = 已处理；False = 这是合成请求（交给主循环）。"""
    cmd = req.get('cmd')
    if cmd == 'ping':
        send({'id': req.get('id'), 'pong': True})
        return True
    if cmd == 'quit':
        _EXIT.set()
        _REQ_Q.put(None)          # 唤醒主循环 ⇒ 退出
        return True
    # 🔴🔴🔴 APP-027⑤：**切换克隆参考音频**
    #   ⚠️ 路径可能是**临时文件**（客户端负责删除）⇒ 这里不校验存在性
    #      （失败会在合成时报出来，由客户端显式回落预设 A）。
    if cmd == 'set_ref':
        new_ref = req.get('ref_audio')
        if new_ref:
            _set_ref(new_ref)
            _trace('set_ref: %s' % new_ref)
        send({'id': req.get('id'), 'set_ref': True,
              'ref_audio': _get_ref()})
        return True
    # 🔴🔴🔴 APP-030② + §90：**取消当前请求**（失控守卫的第二道闸）
    #   🔴 **§90 的关键修复点**：本命令现在由**独立的读取线程**执行
    #      ⇒ 即使主循环正阻塞在生成器里，cancel **也能立刻到达**
    #      ⇒ `_CANCEL_RIDS` 在生成期间**真的会被置位**
    #      ⇒ 生成循环「每块检查一次」才**第一次真正生效**。
    #   ⇒ 客户端仍保留「等不到确认就杀掉重启」的兜底（见 `tts_cuda._cancel_request`）。
    if cmd == 'cancel':
        rid = req.get('id')
        with _CANCEL_LOCK:
            _CANCEL_RIDS.add(rid)
        _trace('cancel: %s' % rid)
        send({'id': rid, 'cancelled': True})
        return True
    return False


def _cancel_pending(rid):
    """本句是否已被请求取消（**线程安全**）。"""
    with _CANCEL_LOCK:
        return rid in _CANCEL_RIDS


def _take_cancel(rid):
    """取出并清除本句的取消标志（**线程安全**）。"""
    with _CANCEL_LOCK:
        if rid in _CANCEL_RIDS:
            _CANCEL_RIDS.discard(rid)
            return True
        return False


def _start_command_reader(stdin):
    """🔴🔴🔴 §90：**独立命令读取线程**。

    为什么必须有（这是本轮修掉的**根因**）：
      旧实现的边车主循环**只在两次请求之间**读 stdin
      ⇒ 生成期间（`generate_voice_clone_streaming`）主循环**被阻塞**
      ⇒ `{'cmd':'cancel'}` **在生成结束前根本不会被读到**
      ⇒ `_CANCEL_RIDS` 恒为空 ⇒ 「每块检查一次」= 永远 False
      ⇒ **APP-030② 的失控守卫在 CUDA 路径上从未成立**。

    职责边界（**关键**）：
      - **控制类命令**（`ping` / `quit` / `set_ref` / `cancel`）**在这里处理**
        ⇒ 才能与生成**并行** ⇒ cancel 才可能真的生效；
      - **合成请求**（带 `text` 的）**投递到 `_REQ_Q`**
        ⇒ 仍由**主循环串行**处理（边车一次只做一句 ⇒ 不得并发合成）。
    """
    def _read():
        while True:
            try:
                line = stdin.readline()
            except Exception:
                line = b''
            if not line:
                # 父进程关了 stdin ⇒ 退出
                _EXIT.set()
                _REQ_Q.put(None)
                return
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line.decode('utf-8'))
            except Exception as e:
                send({'error': 'bad request: %s' % e})
                continue
            try:
                if _handle_control(req):
                    continue
            except Exception as e:
                _trace('ERR cmd: %s' % e)
            # 合成请求 ⇒ 交给主循环串行处理
            _REQ_Q.put(req)

    t = threading.Thread(target=_read, daemon=True)
    t.start()
    return t


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
    #   🔴 §90：现在**跨线程**可见（读取线程可改）⇒ 用 `_REF_LOCK` 保护。
    _set_ref(DEFAULT_REF)

    stdin = sys.stdin.buffer
    # 🔴🔴🔴 §90：**先起命令读取线程**（否则 cancel 在生成期间不可达）
    _start_command_reader(stdin)

    while True:
        req = _REQ_Q.get()
        if req is None:
            return 0                        # stdin 关闭 / quit ⇒ 退出

        rid = req.get('id')
        text = (req.get('text') or '').strip()
        t_req = time.monotonic()
        if not text:
            send({'id': rid, 'done': True})
            continue
        ref = req.get('ref_audio') or _get_ref()
        # 🔴🔴🔴 §90：**这一句在排队期间就已被取消** ⇒ 立即放弃
        #   （否则「取消 ⇒ 仍合成一遍」⇒ 白烧 GPU）
        if _cancel_pending(rid):
            _take_cancel(rid)
            _trace('CANCELLED-BEFORE rid=%s' % rid)
            send({'id': rid, 'done': True, 'chunks': 0,
                  'frames': 0, 'max_new_tokens': 0,
                  'end_reason': 'cancel'})
            continue
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
            # 🔴🔴🔴 §89：**不再扣留一块**。
            #   旧实现用 `pending` 缓冲**扣住最新一块**（收到下一块才发上一块），
            #   唯一目的 = 给「最后一块」打 `last=True`。
            #   🔴 **但 `last` 没有任何消费者**：
            #     - 仓库 `live_caption/` 全量 grep（`get('last')` / `['last']`）= **0 命中**；
            #     - 客户包 `v1.6/app/` 全量 grep = **0 命中**；
            #     - TTS 模块 `qwen3tts_eval/` 全量 grep = **0 命中**。
            #   ⇒ 端到端判据**本来就是** `done` 消息（协议头 L16 写的也是 `done`）。
            #   ⇒ 扣留一块 = **纯粹白等「下一块的生成时间」**（chunk_size=8 帧
            #      ⇒ 12 fps 下每块 ≈ 0.667 s 音频，RTF≈0.6 时 ≈ 0.4 s 墙钟）
            #   ⇒ 🔴 **客户端量到的「首包」实际是第 2 块到达的时刻**
            #      （真首包被第 2 块挡住）⇒ **系统性偏晚**。
            #   ⇒ 现在**每块产出来就立刻下发**（真流式）⇒ 首包不再被挡。
            #   ⚠️ `last` 字段**保留**（线格式兼容）但恒为 `False`
            #      ⇒ 端到端的结束判据是 `done`（见客户端 `msg.get('done')`）。
            n = 0
            t_first = None
            t_end = None
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
                #   🔴 §90：改用**线程安全**的 `_take_cancel()`
                #      （读取线程正在并发写 `_CANCEL_RIDS`）
                if _take_cancel(rid):
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
                # 🔴🔴🔴 §89：**产出来就立刻下发**（不再扣留一块）
                send_chunk(chunk, sr, False, rid)
                n += 1
                if t_first is None:
                    t_first = time.monotonic()
            t_end = time.monotonic()
            if cancelled:
                send({'id': rid, 'done': True, 'chunks': n,
                      'frames': int(frames), 'max_new_tokens': int(mnt),
                      'end_reason': 'cancel'})
                continue
            # 🔴🔴🔴 APP-030⑤：**结束原因**（eos | cap）
            #   `frames >= max_new_tokens` ⇒ **撞上限被截断**（cap）
            #   ⇒ 客户端据此判「异常句」并落盘（APP-030⑤）
            reason = 'cap' if frames >= mnt else 'eos'
            send({'id': rid, 'done': True, 'chunks': n,
                  'frames': int(frames), 'max_new_tokens': int(mnt),
                  'end_reason': reason})
            # 🔴🔴🔴 §89：**同时报「首块时刻」与「整句结束时刻」**
            #   ⇒ 客户端/日志能区分「首包」与「整句合成完」
            #   ⇒ 旧字段 `elapsed` **保留**（语义 = 首块时刻）⇒ 旧消费方不受影响；
            #      新增 `total_s` = 整句合成耗时。
            _trace('DONE rid=%s chunks=%d frames=%d mnt=%d reason=%s '
                   'elapsed=%.2fs total_s=%.2fs'
                   % (rid, n, frames, mnt, reason,
                      (t_first - t_req) if t_first else -1,
                      (t_end - t_req) if t_end else -1))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            _trace('ERR rid=%s %s: %s' % (rid, type(e).__name__, e))
            send({'id': rid, 'error': '%s: %s' % (type(e).__name__, e)})


if __name__ == '__main__':
    sys.exit(main())
