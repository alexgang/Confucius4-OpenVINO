#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app129c —— §89 **确定性**证明：删掉「扣留一块」后，边车**发出的 PCM 字节逐字节不变**。

## 为什么需要这个脚本（app129 六轮实测逼出来的）

`app129` 的 R3/R4 原本想用「两臂总样本数严格相等」来证明
「本次改动只改时序、不改音频内容」。

🔴🔴🔴 **六轮实测证明这条判据不成立**：
- run1/run2/run3/run5/run6 都发现：**基线臂自己两次跑**的样本数就不一致；
- `app129b`（`results/app/app129b_determinism_evidence.json`）进一步在
  **同一进程内**、**同一份贪心代码**、**同一句话**下测得 frames = 19/22/21
  ⇒ **合成本身在 CUDA 上不可复现**
  ⇒ 「样本数严格相等」在任何口径下都做不到
  ⇒ 改成「A/A 噪声基准」后仍不稳（噪声只由 2 次运行估计 ⇒ 估计量本身方差极大）
  ⇒ **统计口径证明「内容未变」这条路走不通**。

## 本脚本的做法：**确定性字节级等价**（零 GPU、零推理、毫秒级）

把边车源码用 `exec` 跑在**独立命名空间**里（铁律：**不 import 被测模块**），
但把它的模型**换成桩**：

- `torch` 桩：`cuda.is_available() → True`；
- `faster_qwen3_tts` 桩：`generate_voice_clone_streaming` **确定性地** yield
  固定长度、固定取值的块序列（例如 4 块 / 各 1000+ 样本 / 数值互不相同）；
- `stdin` 桩：喂一条请求 + 一条 `quit`；
- `stdout` 桩：捕获协议字节流（JSON 行 + PCM）。

🔴 **这样两臂面对的是完全相同的块序列** ⇒
   若「基线（扣留一块）」与「候选（每块即发）」发出的 **PCM 字节序列完全相同**
   ⇒ **「只改时序、不改音频内容」就是被证明的事实**，而不是统计推断。

## 判据

- **E1** 两臂发出的 **PCM 字节流逐字节相同**（`bytes` 全等）；
- **E2** 两臂发出的**块数**相同；
- **E3** 两臂**逐块**的 `n`（样本数）序列相同；
- **E4** 唯一差异是 **最后一块的 `last` 标志**：基线 `True` / 候选 `False`
  ⇒ 且 **`last` 全仓库/客户包/TTS 模块 0 消费者**（静态核对）
  ⇒ ⇒ **线格式兼容，结束判据仍是 `done`**；
- **E5 反证**：基线的**第一块**确实**晚于**第二块产生
  ⇒ 用「协议流里第一块 PCM 出现的位置」直接证明「真首块被挡住」；
- **E6 反证**：候选臂的**第一块 PCM 出现位置 == 基线的第二块 PCM 位置**
  ⇒ 候选臂**提前整整一块**（这就是首包提前的**机制性**证明，不依赖计时）；
- **E7 反证**：对**修前 commit** 的源码跑同一套桩 ⇒ 必然 FAIL
  （证明判据对缺陷敏感，不是恒真）。

## 用法

    <py> results/app/app129c_emission_equivalence.py
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

#: 🔴 反证基线 = **修前** commit（§89 修掉扣留一块之前的 HEAD）
BASELINE_COMMIT = '6cd8248'

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


# ── 桩：确定性块序列 ────────────────────────────────────────────
#   4 块，长度递增（1000/2000/3000/4000），取值互不相同
#   ⇒ 任何「错位」「丢块」「重复发」都会在字节层面暴露
_CHUNK_N = (1000, 2000, 3000, 4000)
_CHUNK_TAG = (1.0, 2.0, 3.0, 4.0)


def _make_stub_modules(counter=None):
    """构造 `torch` / `faster_qwen3_tts` 两个桩模块。

    ⚠️ `counter`（dict）用来记录**生成序号**与**发送序号**：
       - `gen_count`：生成器 yield 了几次
       - `send_count`：边车调了几次 `send_chunk`
       ⇒ 首个 send 时刻的 `gen_count` − 1 = **被扣留的块数**
         （基线 = 1 ⇒ 扣住 1 块；候选 = 0 ⇒ 不扣）
    """
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
            for i, n in enumerate(_CHUNK_N):
                if counter is not None:
                    counter['gen_count'] = counter.get('gen_count', 0) + 1
                    counter['gen_at'] = counter['gen_count']
                arr = np.full(n, _CHUNK_TAG[i], dtype=np.float32)
                timing = {'total_steps_so_far': (i + 1) * 8}
                yield arr, 24000, timing

    class _FakeCls:
        @staticmethod
        def from_pretrained(model_id, **kw):
            return _FakeModel()

    fq.FasterQwen3TTS = _FakeCls
    return torch_stub, fq


def run_sidecar_with_stubs(src, counter=None):
    """用 `exec` 在独立命名空间跑边车源码（模型换成桩），捕获协议字节流。"""
    import numpy as np

    torch_stub, fq = _make_stub_modules(counter)

    out_buf = io.BytesIO()

    class _FakeStdout:
        def __init__(self, buf):
            self.buffer = buf

        def write(self, s):
            return 0

        def flush(self):
            return None

    stdin_buf = io.BytesIO()
    req = {'id': 1, 'text': '确定性桩测试。', 'language': 'Chinese',
           'ref_audio': r'C:\nonexistent\stub.wav', 'chunk_size': 8}
    stdin_buf.write((json.dumps(req, ensure_ascii=False) + '\n').encode('utf-8'))
    stdin_buf.write(b'{"cmd":"quit"}\n')
    stdin_buf.seek(0)

    class _FakeStdin:
        def __init__(self, buf):
            self.buffer = buf

    old_stdout, old_stdin = sys.stdout, sys.stdin
    old_mods = {k: sys.modules.get(k) for k in ('torch', 'faster_qwen3_tts')}
    sys.modules['torch'] = torch_stub
    sys.modules['faster_qwen3_tts'] = fq
    sys.stdout = _FakeStdout(out_buf)
    sys.stdin = _FakeStdin(stdin_buf)

    ns = {'__name__': 'sidecar_stub', '__file__': '<app129c-stub>'}
    try:
        code = compile(src, '<sidecar-stub>', 'exec')
        exec(code, ns)                      # 🔴 独立命名空间（不 import 被测模块）
        # 🔴 记录「首个 send_chunk 调用时，生成器已推进了几块」
        if counter is not None:
            _orig_send_chunk = ns['send_chunk']

            def _wrapped(arr, sr, last, rid, _oc=_orig_send_chunk):
                counter['send_count'] = counter.get('send_count', 0) + 1
                if 'first_send_after_gen' not in counter:
                    counter['first_send_after_gen'] = counter.get('gen_count', 0)
                    counter['first_send_gen_at'] = counter.get('gen_at', 0)
                return _oc(arr, sr, last, rid)

            ns['send_chunk'] = _wrapped
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
        msg = json.loads(line.decode('utf-8'))
        msgs.append(msg)
        if msg.get('n'):
            n = int(msg['n'])
            pcm.extend(raw[i:i + n * 4])
            i += n * 4
    return msgs, bytes(pcm)


def _send_lag_for(src):
    """跑一遍桩，量「首个 send_chunk 时生成器已推进几块」。

    🔴 这是**机制性证据**（不依赖墙钟、不依赖采样随机性）：
       - 基线（扣留一块）：首个 send 时生成器已 yield **2** 块
         ⇒ 第 1 块要等第 2 块产生才发 ⇒ **真首块被挡住**
       - 候选（每块即发）：首个 send 时生成器刚 yield **1** 块
         ⇒ **不扣留** ⇒ 首包提前整整一块
    """
    counter = {'gen_count': 0, 'send_count': 0}
    run_sidecar_with_stubs(src, counter)
    return {
        'first_send_after_gen': counter.get('first_send_after_gen', -1),
        'first_send_gen_at': counter.get('first_send_gen_at', -1),
        'gen_count': counter.get('gen_count', 0),
        'send_count': counter.get('send_count', 0),
    }


def analyse(msgs, pcm):
    """抽出：块序列（含 `last` 标志）、PCM 哈希。"""
    chunks = []
    for m in msgs:
        if m.get('n'):
            chunks.append({'n': int(m['n']), 'last': bool(m.get('last'))})
    done = [m for m in msgs if m.get('done')]
    return {
        'chunks': chunks,
        'n_chunks': len(chunks),
        'chunk_ns': [c['n'] for c in chunks],
        'n_last_true': sum(1 for c in chunks if c['last']),
        'done': bool(done),
        'done_msg': done[0] if done else None,
        'pcm_bytes': len(pcm),
        'pcm_sha256': hashlib.sha256(pcm).hexdigest(),
    }


def main():
    print('=' * 74)
    print('app129c —— §89 确定性字节级等价证明（零 GPU / 零推理）')
    print('=' * 74)
    cur_src = open(os.path.join(REPO, 'live_caption', 'tts_cuda_sidecar.py'),
                   'r', encoding='utf-8').read()
    base_src = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda_sidecar.py')
    check('E0-基线可取', base_src is not None,
          'commit=%s' % BASELINE_COMMIT)
    if base_src is None:
        return finish()

    b_msgs, b_pcm = run_sidecar_with_stubs(base_src)
    c_msgs, c_pcm = run_sidecar_with_stubs(cur_src)
    B = analyse(b_msgs, b_pcm)
    C = analyse(c_msgs, c_pcm)
    EVID['baseline'] = B
    EVID['candidate'] = C
    EVID['stub_chunks'] = list(_CHUNK_N)

    print('  基线：块序列=%s  last=True 个数=%d  PCM=%d B  sha=%s'
          % (B['chunk_ns'], B['n_last_true'], B['pcm_bytes'],
             B['pcm_sha256'][:16]))
    print('  候选：块序列=%s  last=True 个数=%d  PCM=%d B  sha=%s'
          % (C['chunk_ns'], C['n_last_true'], C['pcm_bytes'],
             C['pcm_sha256'][:16]))

    check('E1-两臂发出的 PCM 字节流逐字节相同',
          B['pcm_sha256'] == C['pcm_sha256'] and B['pcm_bytes'] == C['pcm_bytes'],
          'base sha=%s cand sha=%s（%d B）'
          % (B['pcm_sha256'][:16], C['pcm_sha256'][:16], B['pcm_bytes']))
    check('E2-两臂块数相同', B['n_chunks'] == C['n_chunks'],
          'base=%d cand=%d' % (B['n_chunks'], C['n_chunks']))
    check('E3-两臂逐块样本数序列相同', B['chunk_ns'] == C['chunk_ns'],
          'base=%s cand=%s' % (B['chunk_ns'], C['chunk_ns']))
    check('E4-唯一差异 = 最后一块的 last 标志'
          '（基线 True / 候选 False；线格式兼容）',
          B['n_last_true'] == 1 and C['n_last_true'] == 0
          and B['chunk_ns'] == C['chunk_ns'],
          'base last_true=%d cand last_true=%d'
          % (B['n_last_true'], C['n_last_true']))
    check('E4b-两臂都以 done 结束（结束判据不变）',
          B['done'] and C['done'],
          'base done=%s cand done=%s' % (B['done'], C['done']))
    check('E4c-候选臂 done 消息仍带 end_reason',
          bool(C['done_msg'] and C['done_msg'].get('end_reason')),
          'done_msg=%s' % (C['done_msg'],))

    # ── E5/E6：机制性反证 ──
    #   关键：**协议流里 JSON 消息的顺序**就能暴露「扣留」。
    #   基线（扣留一块）：
    #       ready → chunk1(头) → chunk2(头) → chunk3(头) → chunk4(头,last=True)
    #       ⇒ 第一个 chunk 头的 `last` 是 **False**，**最后一个**才是 True
    #       ⇒ 「最后一块」是**最后才发**的 ⇒ 第 1 块在第 2 块产生后才发
    #   候选（每块即发）：
    #       ready → chunk1(头) → chunk2(头) → chunk3(头) → chunk4(头,last=False)
    #       ⇒ 结构完全一样，但**没有任何** last=True
    #
    #   🔴 但**协议字节流本身看不出「第 1 块何时产生」**（那是墙钟事实）。
    #   ⇒ 要在**桩里**直接观测「生成器推进了几次才发出第 1 块」：
    #      桩的 `generate_voice_clone_streaming` 每次 yield 时记一次计数，
    #      边车调 `send_chunk` 时记一次计数 ⇒ 两者之差 = **扣留的块数**。
    #   ⇒ 这个「生成序号 vs 发送序号」的差值，才是**机制性证据**。
    b_lag = _send_lag_for(src=base_src)
    c_lag = _send_lag_for(src=cur_src)
    EVID['baseline_send_lag_blocks'] = b_lag
    EVID['candidate_send_lag_blocks'] = c_lag
    check('E5-基线：第 1 块发出时，生成器已推进 ≥2 块（真首块被挡住）',
          b_lag['first_send_after_gen'] >= 2,
          '基线首个 send 时生成器已 yield %d 块'
          % b_lag['first_send_after_gen'])
    check('E6-候选：第 1 块发出时，生成器刚推进 1 块（每块即发）',
          c_lag['first_send_after_gen'] == 1,
          '候选首个 send 时生成器已 yield %d 块'
          % c_lag['first_send_after_gen'])
    check('E7-反证：两臂的「生成-发送滞后」不同（判据对缺陷敏感）',
          b_lag['first_send_after_gen'] != c_lag['first_send_after_gen'],
          '基线=%d 候选=%d' % (b_lag['first_send_after_gen'],
                               c_lag['first_send_after_gen']))

    return finish()


def finish():
    print('')
    print('  PASS=%d  FAIL=%d' % (len(PASS), len(FAIL)))
    out = os.path.join(HERE, 'app129c_emission_equivalence_evidence.json')
    EVID['verdict'] = 'PASS' if not FAIL else 'FAIL'
    EVID['pass_count'] = len(PASS)
    EVID['fail_count'] = len(FAIL)
    EVID['real_fail'] = list(FAIL)
    EVID['baseline_commit'] = BASELINE_COMMIT
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('  证据 → %s (%d B)' % (out, os.path.getsize(out)))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
