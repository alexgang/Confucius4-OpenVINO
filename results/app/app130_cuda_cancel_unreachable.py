#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app130 —— §90 **确定性**证明：CUDA 边车的 `cancel` 命令在**生成期间根本不可达**。

## 缺陷本体（APP-030② 明文要求被实现成了空壳）

reviewer 在 APP-030②「### 3. 要做」② 里写明：

> 客户端再加一道：本句已收音频 > max(3×估计, 估计+8 s) ⇒ 判 RUNAWAY ⇒
> 停止播放本句剩余部分，并让边车停止（**加 cancel 命令，边车每块检查一次；做不到就杀掉重启**）

修前现状（`live_caption/tts_cuda_sidecar.py`）：

- 边车主循环只在 **两次请求之间** 执行 `stdin.readline()`；
- 生成期间（`model.generate_voice_clone_streaming(...)`）**主循环被阻塞**；
- ⇒ `{'cmd':'cancel','id':rid}` 这行 JSON **在生成结束前根本不会被读到**；
- ⇒ `_CANCEL_RIDS` 在本次生成期间**恒为空**；
- ⇒ 「**边车每块检查一次**」这个守卫 = **永远为 False** = **从未生效**。

而客户端的兜底也没实现（`live_caption/tts_cuda.py::_cancel_request`）：
写命令**成功**就 `return`，**不会**触发「杀掉重启」
⇒ 「**做不到就杀掉重启**」这半句也是空壳。

⇒ 合起来：**APP-030② 想要的「失控句立刻中止、不再把后续句堵住 1~2 分钟」
在 CUDA 路径上从未成立**（reviewer 实测：一句 7 字日文跑 106.61 s / 255 块）。

## 本脚本的做法（零 GPU、零推理、毫秒级）

- **边车侧**：把边车源码用 `exec` 跑在**独立命名空间**里
  （铁律：**不 import 被测模块**），模型换成**桩**，`torch` / `faster_qwen3_tts`
  也换成桩；stdin 换成**可动态注入**的桩 ⇒ 可以在「生成进行到第 N 块之前」把
  `cancel` 命令**塞进管道**（这正是真实 RUNAWAY 发生的时刻）。
- **客户端侧**：用 `ast` 抽出 `CudaTTSEngine._cancel_request` 的源码，
  `exec` 到独立命名空间，绑到**假 proc / 假队列**上 ⇒ 验证
  「写命令成功但边车不回确认 ⇒ 必须杀并重启」这条兜底**确实存在**。

## 判据

| 组 | 语义 | 期望 |
|---|---|---|
| **A** | 在**修前**源码（固定 commit `ef830d6`）上的观察 | **全部命中**（缺陷真实存在） |
| **B** | 在**候选**源码（工作区）上的观察 | **全部 PASS**（缺陷已修） |
| **C** | **判据敏感性反证**：把候选源码里的命令读取线程启动**注入删除** | **必须重新变回「不可达」** |

C 组是防「闸门恒真」的必需项。

## 用法

    <py> results/app/app130_cuda_cancel_unreachable.py
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **同一套判据必须能在「仓库」和「客户包」两处跑**
#:   （客户包里的模块在 `app/` 子目录下，不是 `live_caption/`）
#:   ⇒ 用环境变量覆盖源码根目录，不复制脚本、不改判据。
#:   APP130_SRC_ROOT = 客户包根目录（其下有 app/）
#:   APP130_EVID     = 证据 JSON 落盘路径
SRC_ROOT = os.environ.get('APP130_SRC_ROOT') or REPO
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'
SIDECAR_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda_sidecar.py')
CUDA_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda.py')
EVID_PATH = os.environ.get('APP130_EVID') or os.path.join(
    HERE, 'app130_cuda_cancel_unreachable_evidence.json')

#: 🔴 反证基线 = **固定 commit**（修前状态）
#:   （记忆铁律：反证基线不能用 HEAD ⇒ 修完之后 HEAD 就是修版 ⇒ 反证永远落空）
BASELINE_COMMIT = 'ef830d6'

#: 桩生成器的块序列（长度递增、取值互不相同 ⇒ 任何错位都能在字节层暴露）
_CHUNK_N = (1000, 2000, 3000, 4000)
_CHUNK_TAG = (1.0, 2.0, 3.0, 4.0)

PASS: list = []
FAIL: list = []
EVID: dict = {}


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)
    EVID.setdefault('checks', {})[name] = dict(
        ok=bool(cond), detail=str(detail)[:400])
    return bool(cond)


def git_show(commit, rel):
    r = subprocess.run(['git', '-C', REPO, 'show', f'{commit}:{rel}'],
                       capture_output=True)
    return r.stdout.decode('utf-8', 'replace') if r.returncode == 0 else None


# ── 桩：可动态注入的 stdin ───────────────────────────────────────
class _DynStdin:
    """可**动态注入**内容的 stdin 桩（模拟「生成进行中才到达的命令」）。

    ⚠️ `priority=True` ⇒ 插到**队首**（真实现里 cancel 是**新到**的数据，
       而主循环在生成期间根本没读 ⇒ 生成结束后第一个读到它）。
    """

    def __init__(self):
        self._buf = bytearray()
        self._cond = threading.Condition()
        self.eof = False
        self.read_calls = 0

    def inject(self, data: bytes, priority=False):
        with self._cond:
            if priority:
                self._buf = bytearray(data) + self._buf
            else:
                self._buf.extend(data)
            self._cond.notify_all()

    def readline(self):
        with self._cond:
            deadline = time.monotonic() + 15.0
            while not self._buf and not self.eof:
                remain = deadline - time.monotonic()
                if remain <= 0:
                    self.eof = True
                    break
                self._cond.wait(timeout=min(0.25, remain))
            self.read_calls += 1
            if not self._buf:
                return b''
            idx = self._buf.find(b'\n')
            if idx < 0:
                return b''
            line = bytes(self._buf[:idx + 1])
            del self._buf[:idx + 1]
            return line


def _make_stub_modules(state):
    """构造 `torch` / `faster_qwen3_tts` 两个桩模块。"""
    import types

    torch_stub = types.ModuleType('torch')
    torch_stub.__version__ = 'stub-0.0.0'
    _cuda = types.SimpleNamespace()
    _cuda.is_available = lambda: True
    _cuda.get_device_name = lambda idx: 'STUB-GPU'
    torch_stub.cuda = _cuda

    fq = types.ModuleType('faster_qwen3_tts')

    class _FakeModel:
        def warmup(self, **kw):
            return None

        def generate_voice_clone_streaming(self, text=None, language=None,
                                           ref_audio=None, xvec_only=False,
                                           max_new_tokens=None, chunk_size=None,
                                           **kw):
            import numpy as np
            inject_at = state.get('inject_at_gen')
            for i, n in enumerate(_CHUNK_N):
                if inject_at is not None and i == inject_at:
                    # 🔴 真实 RUNAWAY 的时刻：生成进行中，cancel 才到达
                    state['inject_cancel']()
                # 让出 GIL ⇒ 命令读取线程有机会把 cancel 取走
                time.sleep(0.10)
                ns = state.get('ns')
                if ns is not None:
                    try:
                        seen = bool(ns.get('_CANCEL_RIDS'))
                    except Exception:
                        seen = False
                    state['cancel_seen'].append(seen)
                    if seen:
                        state['cancel_observed'] = True
                arr = np.full(n, _CHUNK_TAG[i], dtype=np.float32)
                timing = {'total_steps_so_far': (i + 1) * 8}
                yield arr, 24000, timing

    class _FakeCls:
        @staticmethod
        def from_pretrained(model_id, **kw):
            return _FakeModel()

    fq.FasterQwen3TTS = _FakeCls
    return torch_stub, fq


def run_sidecar(src, inject_at_gen=None, inject_cancel=True):
    """用 `exec` 在独立命名空间跑边车源码（模型换桩），返回观测结果。"""
    state = {'ns': None, 'cancel_seen': [], 'inject_at_gen': inject_at_gen,
             'cancel_observed': False}

    stdin_stub = _DynStdin()
    out_buf = io.BytesIO()

    class _FakeStdout:
        def __init__(self, buf):
            self.buffer = buf

        def write(self, s):
            return 0

        def flush(self):
            return None

    class _FakeStdin:
        def __init__(self, buf):
            self.buffer = buf

    req = {'id': 1, 'text': '失控句测试。', 'language': 'Chinese',
           'ref_audio': r'C:\nonexistent\stub.wav', 'chunk_size': 8}
    stdin_stub.inject((json.dumps(req, ensure_ascii=False) + '\n').encode('utf-8'))
    # 末尾放 quit ⇒ 主循环读完 cancel 后再读到 quit ⇒ 干净退出（不挂起）
    stdin_stub.inject(b'{"cmd":"quit"}\n')

    def _inject_cancel():
        state['cancel_injected'] = True
        stdin_stub.inject(
            (json.dumps({'cmd': 'cancel', 'id': 1},
                        ensure_ascii=False) + '\n').encode('utf-8'),
            priority=True)

    state['inject_cancel'] = _inject_cancel

    torch_stub, fq = _make_stub_modules(state)

    old_stdout, old_stdin = sys.stdout, sys.stdin
    old_mods = {k: sys.modules.get(k) for k in ('torch', 'faster_qwen3_tts')}
    sys.modules['torch'] = torch_stub
    sys.modules['faster_qwen3_tts'] = fq
    sys.stdout = _FakeStdout(out_buf)
    sys.stdin = _FakeStdin(stdin_stub)

    ns = {'__name__': 'sidecar_stub', '__file__': '<app130-stub>'}
    try:
        code = compile(src, '<sidecar-stub>', 'exec')
        exec(code, ns)
        state['ns'] = ns
        state['inject_at_gen'] = inject_at_gen if inject_cancel else None
        ns['main']()
    finally:
        sys.stdout, sys.stdin = old_stdout, old_stdin
        for k, v in old_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    raw = out_buf.getvalue()

    # ── 解析协议：JSON 行 + n*4 字节 PCM ──
    msgs, pcm = [], bytearray()
    i = 0
    while i < len(raw):
        nl = raw.find(b'\n', i)
        if nl < 0:
            break
        line = raw[i:nl]
        i = nl + 1
        try:
            msg = json.loads(line.decode('utf-8'))
        except Exception:
            continue
        msgs.append(msg)
        if msg.get('n'):
            n = int(msg['n'])
            pcm.extend(raw[i:i + n * 4])
            i += n * 4

    done = [m for m in msgs if m.get('done')]
    chunks = [m for m in msgs if m.get('n')]
    return {
        'msgs': msgs,
        'n_chunks': len(chunks),
        'chunk_ns': [int(c['n']) for c in chunks],
        'done_msg': done[0] if done else None,
        'end_reason': (done[0].get('end_reason') if done else None),
        'pcm_bytes': len(pcm),
        'pcm_sha256': hashlib.sha256(bytes(pcm)).hexdigest(),
        'cancel_seen': list(state.get('cancel_seen') or []),
        'cancel_injected': bool(state.get('cancel_injected')),
        'stdin_read_calls': stdin_stub.read_calls,
    }


# ── 客户端侧：抽出 `_cancel_request` 做行为级测试 ─────────────────
def extract_method(src, cls_name, meth_name):
    """用 `ast` 抽出方法源码（**不 import 被测模块**）。

    ⚠️ 抽出来的是**带缩进**的片段 ⇒ 顶层 `exec` 会 IndentationError
    ⇒ 必须 `textwrap.dedent`。
    """
    import textwrap
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == meth_name:
                    lines = src.splitlines()
                    start = item.lineno - 1
                    end = item.end_lineno
                    return textwrap.dedent('\n'.join(lines[start:end]))
    return None


def run_cancel_request(src, ack=True):
    """在**假 proc / 假队列**上跑 `_cancel_request`，返回是否调用了重启。

    ⚠️ 只抽 `_cancel_request` 一个方法 ⇒ 它调用的 `_wait_cancel_ack` /
       `_cancel_kill` 也必须一起抽（否则 `NameError`）⇒ 按调用图补齐。
    """
    meth = extract_method(src, 'CudaTTSEngine', '_cancel_request')
    if meth is None:
        return None
    meth_ack = extract_method(src, 'CudaTTSEngine', '_wait_cancel_ack')
    meth_kill = extract_method(src, 'CudaTTSEngine', '_cancel_kill')

    events = {'restart': False, 'written': [], 'ack_waited': False}

    class _FakeStdin:
        def write(self, b):
            events['written'].append(b)

        def flush(self):
            pass

    class _FakeProc:
        def __init__(self):
            self.stdin = _FakeStdin()

        def poll(self):
            return None

    class _FakeLock:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class _FakeSelf:
        def __init__(self):
            self.proc = _FakeProc()
            self._stdin_wlock = _FakeLock()
            self.on_log = lambda *a, **k: None

        def _restart_sidecar(self, why):
            events['restart'] = True

    ns = {'json': json, 'time': time,
          '_trace': lambda m: events.setdefault('trace', []).append(m),
          '_TIMEOUT': object(),
          'CANCEL_ACK_TIMEOUT_S': 0.2,
          'CudaTTSError': RuntimeError}
    exec(compile(meth, '<cancel_request>', 'exec'), ns)
    if meth_ack:
        exec(compile(meth_ack, '<wait_cancel_ack>', 'exec'), ns)
    if meth_kill:
        exec(compile(meth_kill, '<cancel_kill>', 'exec'), ns)

    fake = _FakeSelf()

    # 🔴 把抽出来的方法**绑到假实例**上
    #   （`exec` 出来的是**模块级函数**⇒ `self._wait_cancel_ack(...)` 找不到）
    if meth_ack:
        fake._wait_cancel_ack = lambda rid, timeout: ns['_wait_cancel_ack'](
            fake, rid, timeout)
    if meth_kill:
        fake._cancel_kill = lambda rid, why: ns['_cancel_kill'](fake, rid, why)

    if meth_ack:
        # 让「等确认」这一步**真的发生**（用假队列喂确认 / 不喂）
        def _fake_q_get(timeout):
            events['ack_waited'] = True
            if ack:
                return json.dumps({'id': 7, 'cancelled': True})
            return ns['_TIMEOUT']
        fake._q_get = _fake_q_get

    ns['_cancel_request'](fake, 7)
    return events


def main():
    print('=' * 74)
    print('app130 —— §90 确定性证明：CUDA 边车 `cancel` 在生成期间不可达')
    print('=' * 74)

    # ⚠️ 用**通用换行**读取（默认 newline=None）⇒ 统一成 LF
    #   ⇒ 客户包那份是 CRLF 时也能正常 exec / 正则匹配
    cur_src = open(SIDECAR_PATH, 'r', encoding='utf-8').read()
    cuda_src = open(CUDA_PATH, 'r', encoding='utf-8').read()
    base_src = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda_sidecar.py')
    base_cuda = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda.py')
    check('A0-修前基线可取', base_src is not None and base_cuda is not None,
          'commit=%s' % BASELINE_COMMIT)
    EVID['_src_root'] = SRC_ROOT
    EVID['_subdir'] = _SUBDIR
    if base_src is None:
        return finish()

    # ── 场景 S1：cancel 预先在管道中（最宽松形态）──
    print('\n  ── 场景 S1：cancel 预先在管道中（生成开始前） ──')
    base_s1 = run_sidecar(base_src, inject_at_gen=0)
    cand_s1 = run_sidecar(cur_src, inject_at_gen=0)
    print('    修前: chunks=%d end_reason=%s cancel_seen=%s'
          % (base_s1['n_chunks'], base_s1['end_reason'],
             base_s1['cancel_seen']))
    print('    候选: chunks=%d end_reason=%s cancel_seen=%s'
          % (cand_s1['n_chunks'], cand_s1['end_reason'],
             cand_s1['cancel_seen']))
    for tag, r in (('baseline_S1', base_s1), ('candidate_S1', cand_s1)):
        EVID[tag] = {k: r[k] for k in ('n_chunks', 'chunk_ns', 'end_reason',
                                       'cancel_seen', 'stdin_read_calls')}

    # ── 场景 S2：cancel 在生成**中途**到达（真实 RUNAWAY 时刻）──
    print('\n  ── 场景 S2：cancel 在生成进行到第 2 块前到达 ──')
    base_s2 = run_sidecar(base_src, inject_at_gen=1)
    cand_s2 = run_sidecar(cur_src, inject_at_gen=1)
    print('    修前: chunks=%d end_reason=%s cancel_seen=%s'
          % (base_s2['n_chunks'], base_s2['end_reason'],
             base_s2['cancel_seen']))
    print('    候选: chunks=%d end_reason=%s cancel_seen=%s'
          % (cand_s2['n_chunks'], cand_s2['end_reason'],
             cand_s2['cancel_seen']))
    for tag, r in (('baseline_S2', base_s2), ('candidate_S2', cand_s2)):
        EVID[tag] = {k: r[k] for k in ('n_chunks', 'chunk_ns', 'end_reason',
                                       'cancel_seen', 'stdin_read_calls')}

    # ── 场景 S3：正常请求（无 cancel）—— 回归 ──
    print('\n  ── 场景 S3：正常请求（无 cancel）—— 回归 ──')
    cand_s3 = run_sidecar(cur_src, inject_at_gen=None, inject_cancel=False)
    base_s3 = run_sidecar(base_src, inject_at_gen=None, inject_cancel=False)
    print('    修前: chunks=%d end_reason=%s' % (base_s3['n_chunks'],
                                                  base_s3['end_reason']))
    print('    候选: chunks=%d end_reason=%s' % (cand_s3['n_chunks'],
                                                  cand_s3['end_reason']))
    EVID['candidate_S3'] = {k: cand_s3[k] for k in
                            ('n_chunks', 'chunk_ns', 'end_reason',
                             'pcm_sha256', 'pcm_bytes')}
    EVID['baseline_S3'] = {k: base_s3[k] for k in
                           ('n_chunks', 'chunk_ns', 'end_reason',
                            'pcm_sha256', 'pcm_bytes')}

    # ══ A 组：修前源码上的观察（期望**全部命中**＝缺陷真实存在）══
    print('\n  === A 组：修前源码（期望「缺陷命中」）===')
    check('A1-修前：生成期间 `_CANCEL_RIDS` 恒为空（cancel 从未被读到）',
          bool(base_s2['cancel_seen']) and not any(base_s2['cancel_seen']),
          'cancel_seen=%s' % (base_s2['cancel_seen'],))
    check('A2-修前：cancel 后**全部 4 块照发**且 end_reason=eos（守卫失效）',
          base_s2['n_chunks'] == 4 and base_s2['end_reason'] == 'eos',
          'chunks=%d end_reason=%s' % (base_s2['n_chunks'],
                                       base_s2['end_reason']))
    check('A3-修前：S1（cancel 预先在管道）同样完全失效',
          base_s1['n_chunks'] == 4 and base_s1['end_reason'] == 'eos',
          'chunks=%d end_reason=%s' % (base_s1['n_chunks'],
                                       base_s1['end_reason']))
    base_ce = run_cancel_request(base_cuda, ack=False)
    check('A4-修前：客户端写 cancel 命令成功 ⇒ **直接返回**（不杀重启）',
          bool(base_ce) and not base_ce['restart']
          and len(base_ce['written']) == 1,
          'restart=%s written=%d' % (base_ce and base_ce['restart'],
                                     len(base_ce['written']) if base_ce else -1))
    check('A5-修前：客户端**从不**等确认（ack_waited=False ⇒ 兜底是空壳）',
          bool(base_ce) and not base_ce['ack_waited'],
          'ack_waited=%s' % (base_ce and base_ce['ack_waited'],))

    # ══ B 组：候选源码上的观察（期望**全部 PASS**＝缺陷已修）══
    print('\n  === B 组：候选源码（期望「缺陷已修」）===')
    check('B1-候选：生成期间能读到 cancel（`_CANCEL_RIDS` 非空）',
          bool(cand_s2['cancel_seen']) and any(cand_s2['cancel_seen']),
          'cancel_seen=%s' % (cand_s2['cancel_seen'],))
    check('B2-候选：cancel 后**提前停止**（块数 < 4）且 end_reason=cancel',
          cand_s2['n_chunks'] < 4 and cand_s2['end_reason'] == 'cancel',
          'chunks=%d end_reason=%s' % (cand_s2['n_chunks'],
                                       cand_s2['end_reason']))
    check('B3-候选：S1（cancel 预先在管道）也能取消（块数 < 4）',
          cand_s1['n_chunks'] < 4 and cand_s1['end_reason'] == 'cancel',
          'chunks=%d end_reason=%s' % (cand_s1['n_chunks'],
                                       cand_s1['end_reason']))
    check('B4-回归：候选在**无 cancel**时行为不变（4 块 / eos）',
          cand_s3['n_chunks'] == 4 and cand_s3['end_reason'] == 'eos',
          'chunks=%d end_reason=%s' % (cand_s3['n_chunks'],
                                       cand_s3['end_reason']))
    check('B5-回归：候选无 cancel 时的 PCM 字节流与修前逐字节相同',
          cand_s3['pcm_sha256'] == base_s3['pcm_sha256']
          and cand_s3['pcm_bytes'] == base_s3['pcm_bytes'],
          'base sha=%s cand sha=%s（%d B）'
          % (base_s3['pcm_sha256'][:16], cand_s3['pcm_sha256'][:16],
             cand_s3['pcm_bytes']))
    check('B6-候选：边车源码含**命令读取线程**（cancel 得以在生成期间到达）',
          '_start_command_reader' in cur_src,
          '_start_command_reader in src = %s'
          % ('_start_command_reader' in cur_src))
    cand_ce = run_cancel_request(cuda_src, ack=False)
    check('B7-候选：客户端**会等确认**（ack_waited=True）',
          bool(cand_ce) and cand_ce['ack_waited'],
          'ack_waited=%s' % (cand_ce and cand_ce['ack_waited'],))
    check('B9-候选：**等不到确认 ⇒ 杀掉并重启边车**（APP-030② 的兜底兑现）',
          bool(cand_ce) and cand_ce['restart'] is True,
          'restart=%s' % (cand_ce and cand_ce['restart'],))
    cand_ce_ok = run_cancel_request(cuda_src, ack=True)
    check('B10-候选：**收到确认 ⇒ 不杀重启**（正常路径不误杀）',
          bool(cand_ce_ok) and cand_ce_ok['restart'] is False
          and len(cand_ce_ok['written']) == 1,
          'restart=%s written=%d' % (cand_ce_ok and cand_ce_ok['restart'],
                                     len(cand_ce_ok['written'])
                                     if cand_ce_ok else -1))
    check('B8-候选：客户端含「杀并重启」兜底分支（做不到就杀掉重启）',
          '_restart_sidecar' in cuda_src
          and re.search(r'_cancel_request[\s\S]{0,3000}_restart_sidecar',
                        cuda_src) is not None,
          '源码级锚定')
    # 🔴 §90 第二个缺陷：排空线程偷走并丢弃下一句的消息
    check('B11-候选：`_start_drain` 对**非本 rid** 的消息**插回队首**（不丢弃）',
          '_q_put_front' in cuda_src
          and re.search(r'_start_drain[\s\S]{0,3000}_q_put_front',
                        cuda_src) is not None,
          '_q_put_front in src = %s' % ('_q_put_front' in cuda_src))

    # ══ C 组：判据敏感性反证（注入删除 ⇒ 必须复现失效）══
    print('\n  === C 组：反证（注入删除 ⇒ 必须复现失效）===')

    # ── C-1：删掉**生成循环里的取消检查**（整块）──
    #   ⇒ cancel **能被读到**（`_CANCEL_RIDS` 非空）但**不会中止生成**
    #   ⇒ 必须重新出现「4 块照发 / end_reason=eos」⇒ B2 判据对此敏感
    broken1 = re.sub(
        r'(?m)^[ \t]*if _take_cancel\(rid\):\r?\n'
        r'(?:[ \t]+.*\r?\n|\r?\n)*?[ \t]*break\r?\n',
        '', cur_src)
    removed1 = len(re.findall(r'(?m)^[ \t]*if _take_cancel\(rid\):$',
                              cur_src)) - len(
        re.findall(r'(?m)^[ \t]*if _take_cancel\(rid\):$', broken1))
    check('C0-注入成功（删掉了生成循环里的取消检查）', removed1 >= 1,
          '删除数=%d' % removed1)
    if removed1 >= 1:
        brk1 = run_sidecar(broken1, inject_at_gen=1)
        print('    删检查后: chunks=%d end_reason=%s cancel_seen=%s'
              % (brk1['n_chunks'], brk1['end_reason'], brk1['cancel_seen']))
        EVID['broken_no_check_S2'] = {k: brk1[k] for k in
                                      ('n_chunks', 'end_reason', 'cancel_seen')}
        check('C1-删掉取消检查 ⇒ 守卫重新失效（4 块 / eos）',
              brk1['n_chunks'] == 4 and brk1['end_reason'] == 'eos',
              'chunks=%d end_reason=%s' % (brk1['n_chunks'],
                                           brk1['end_reason']))

    # ── C-2：删掉**命令读取线程的启动** ──
    #   ⇒ 合成请求**根本到不了主循环**（没人往 `_REQ_Q` 投递）
    #   ⇒ 必须出现「0 块 / 无 end_reason」⇒ 证明读取线程是请求到达的唯一通道
    broken2 = re.sub(r'(?m)^[ \t]*_start_command_reader\([^\n]*\n', '', cur_src)
    removed2 = len(re.findall(r'(?m)^[ \t]*_start_command_reader\([^\n]*$',
                              cur_src)) - len(
        re.findall(r'(?m)^[ \t]*_start_command_reader\([^\n]*$', broken2))
    check('C2a-注入成功（删掉了命令读取线程的启动）', removed2 >= 1,
          '删除数=%d' % removed2)
    if removed2 >= 1:
        # 🔴 删掉读取线程后**没有人**往 `_REQ_Q` 投递请求
        #   ⇒ 主循环的 `_REQ_Q.get()` 会**永久阻塞** ⇒ 测试挂死
        #   ⇒ 所以还要把 `get()` 改成**带超时**（超时即退出）
        broken2 = broken2.replace(
            '        req = _REQ_Q.get()\n',
            '        try:\n'
            '            req = _REQ_Q.get(timeout=6.0)\n'
            '        except queue.Empty:\n'
            '            return 0\n')
        brk2 = run_sidecar(broken2, inject_at_gen=1)
        print('    删线程后: chunks=%d end_reason=%s'
              % (brk2['n_chunks'], brk2['end_reason']))
        EVID['broken_no_reader_S2'] = {k: brk2[k] for k in
                                       ('n_chunks', 'end_reason')}
        check('C2b-删掉读取线程 ⇒ 请求**根本到不了**主循环（0 块 / 无 end_reason）',
              brk2['n_chunks'] == 0 and brk2['end_reason'] is None,
              'chunks=%d end_reason=%s' % (brk2['n_chunks'],
                                           brk2['end_reason']))

    return finish()


def finish():
    print('')
    print('  PASS=%d  FAIL=%d' % (len(PASS), len(FAIL)))
    out = EVID_PATH
    EVID['verdict'] = 'PASS' if not FAIL else 'FAIL'
    EVID['pass_count'] = len(PASS)
    EVID['fail_count'] = len(FAIL)
    EVID['real_fail'] = list(FAIL)
    EVID['baseline_commit'] = BASELINE_COMMIT
    EVID['stub_chunks'] = list(_CHUNK_N)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('  证据 → %s (%d B)' % (out, os.path.getsize(out)))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
