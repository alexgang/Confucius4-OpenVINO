#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""app131b —— §91 的**端到端协议级**验证：真实 `CudaTTSEngine` + 桩边车（子进程）。

## 为什么要有这一条（app131 之外的补充）

`app131` 用**假 proc / 假队列**验证三个缺陷的**逻辑**；
但它**没有验证「真实进程 + 真实管道 + 真实 JSON/PCM 协议」下分流机制是通的**。

⇒ 本脚本：
- **真的** `subprocess.Popen` 起一个**桩边车**（纯 stdlib，零 GPU、零推理）；
- **真的**跑 `CudaTTSEngine.start()` / `generate_stream()` / `close()`；
- 验证：① 正常句能拿到**全部**块（PCM 逐字节正确）；
  ② 句结束后**本 rid 的队列被回收**（不留内存泄漏）；
  ③ 连续多句**互不干扰**（rid 分流 ⇒ 不错位）。

## 用法

    <py> results/app/app131b_cuda_rid_split_e2e.py
"""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SRC_ROOT = os.environ.get('APP131B_SRC_ROOT') or REPO
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'
CUDA_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda.py')
EVID_PATH = os.environ.get('APP131B_EVID') or os.path.join(
    HERE, 'app131b_cuda_rid_split_e2e_evidence.json')

EVID = {'script': 'app131b_cuda_rid_split_e2e.py',
        'src_root': SRC_ROOT, 'subdir': _SUBDIR, 'checks': []}

#: 🔴 桩边车：纯 stdlib。协议 = JSON 行 + n*4 字节 float32 LE PCM
STUB_SIDECAR = r'''
import sys, json, struct
# ① ready（客户端 start() 等的就是这条）
sys.stdout.buffer.write((json.dumps(
    {'ready': True, 'load_s': 0.0, 'warmup_s': 0.0,
     'device': 'STUB', 'torch': 'stub', 'model': 'stub'}) + '\n').encode())
sys.stdout.buffer.flush()
CHUNKS = 3
N = 100
for line in sys.stdin.buffer:
    line = line.strip()
    if not line:
        continue
    try:
        req = json.loads(line)
    except Exception:
        continue
    cmd = req.get('cmd')
    if cmd == 'quit':
        break
    if cmd == 'cancel':
        sys.stdout.buffer.write((json.dumps(
            {'id': req.get('id'), 'cancelled': True}) + '\n').encode())
        sys.stdout.buffer.flush()
        continue
    rid = req.get('id')
    for _k in range(CHUNKS):
        hdr = json.dumps({'id': rid, 'sr': 24000, 'n': N,
                          'last': False}).encode() + b'\n'
        pcm = struct.pack('<%df' % N, *([0.25] * N))
        sys.stdout.buffer.write(hdr)
        sys.stdout.buffer.write(pcm)
        sys.stdout.buffer.flush()
    sys.stdout.buffer.write((json.dumps(
        {'id': rid, 'done': True, 'chunks': CHUNKS,
         'frames': 10, 'max_new_tokens': 48,
         'end_reason': 'eos'}) + '\n').encode())
    sys.stdout.buffer.flush()
'''


def check(name, ok, detail=''):
    ok = bool(ok)
    EVID['checks'].append({'name': name, 'pass': ok, 'detail': str(detail)})
    print('  [%s] %s — %s' % ('PASS' if ok else 'FAIL', name, detail))
    return ok


def load_engine():
    """exec 源码得到 `CudaTTSEngine`（**不 import 被测模块** ⇒ 顶层 numpy 不会 abort）。"""
    src = open(CUDA_PATH, 'r', encoding='utf-8').read()
    ns = {'__name__': 'app131b_notmain',
          '__file__': os.path.join(SRC_ROOT, _SUBDIR, 'tts_cuda.py')}
    exec(compile(src, 'tts_cuda', 'exec'), ns)
    return ns


def main():
    print('=' * 74)
    print('app131b —— §91 端到端协议级验证：真实 CudaTTSEngine + 桩边车')
    print('=' * 74)

    ns = load_engine()
    CudaTTSEngine = ns['CudaTTSEngine']

    tmpd = tempfile.mkdtemp(prefix='app131b_')
    sp = os.path.join(tmpd, 'stub_sidecar.py')
    with open(sp, 'w', encoding='utf-8') as f:
        f.write(STUB_SIDECAR)

    # 🔴 把模块级 SIDECAR 指向桩（真实 start() 会用它）
    ns['SIDECAR'] = sp

    eng = CudaTTSEngine(pkg_dir=tmpd, python=sys.executable)
    ok_start = False
    try:
        eng.start()
        ok_start = True
    except Exception as e:
        check('E0-桩边车能 ready（客户端 start() 成功）', False,
              '%s: %s' % (type(e).__name__, e))
    if not ok_start:
        EVID['pass'] = sum(1 for c in EVID['checks'] if c['pass'])
        EVID['fail'] = sum(1 for c in EVID['checks'] if not c['pass'])
        with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(EVID, f, ensure_ascii=False, indent=2)
        return 1
    check('E0-桩边车能 ready（客户端 start() 成功）', True,
          'device=%s' % eng.device_name)

    # ── E1：正常句拿到全部块 + PCM 正确 ──
    try:
        outs = list(eng.generate_stream('hello world', language='English',
                                        est_sec=1.0))
    except Exception as e:
        outs = []
        check('E1-正常句能合成（不抛异常）', False,
              '%s: %s' % (type(e).__name__, e))
    else:
        check('E1-正常句能合成（不抛异常）', True, 'chunks=%d' % len(outs))
    check('E2-正常句拿到**全部 3 块**（PCM 未被吞）',
          len(outs) == 3 and all(len(a) == 100 for a, _ in outs),
          'chunks=%d lens=%s' % (len(outs), [len(a) for a, _ in outs]))
    check('E3-PCM 采样值正确（0.25 float32 LE）',
          all(abs(a[0] - 0.25) < 1e-6 for a, _ in outs if a),
          'first=%s' % (outs[0][0][0] if outs and outs[0][0] else None))

    # ── E4：句结束后 rid 队列被回收（不留内存泄漏）──
    with eng._rid_q_lock:
        left = list(eng._rid_q.keys())
    check('E4-句结束后**本 rid 的队列被回收**（无内存泄漏）',
          not left, '残留 rid 队列=%s' % left)

    # ── E5：连续多句互不干扰（rid 分流 ⇒ 不错位）──
    lens = []
    try:
        for i in range(5):
            o = list(eng.generate_stream('sentence %d' % i, language='English',
                                         est_sec=1.0))
            lens.append(len(o))
    except Exception as e:
        check('E5-连续 5 句互不干扰（每句都拿满 3 块）', False,
              '%s: %s' % (type(e).__name__, e))
    else:
        check('E5-连续 5 句互不干扰（每句都拿满 3 块）',
              lens == [3, 3, 3, 3, 3], '各句块数=%s' % lens)

    # ── E6：全部结束后 rid 队列仍为空 ──
    with eng._rid_q_lock:
        left2 = list(eng._rid_q.keys())
    check('E6-连续多句后 rid 队列仍为空', not left2,
          '残留=%s' % left2)

    try:
        eng.close()
    except Exception:
        pass

    npass = sum(1 for c in EVID['checks'] if c['pass'])
    nfail = sum(1 for c in EVID['checks'] if not c['pass'])
    EVID['pass'] = npass
    EVID['fail'] = nfail
    with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('\n  PASS=%d  FAIL=%d' % (npass, nfail))
    print('  证据 → %s' % EVID_PATH)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
