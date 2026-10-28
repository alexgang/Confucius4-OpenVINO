#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app129b —— 诊断「边车合成结果为何跨次不一致」（§89 R3/R4 判据口径的依据）。

## 要回答的问题

app129 连续三轮（run1/run2/run3/run4）都发现：
**基线臂自己两次跑**，同一句话的样本数就不同。

run4 已经把 `do_sample=False`（贪心解码）**同等注入两臂**，但基线臂自身**仍不一致**：
    base1=[40320, 59520, 65280]  vs  base2=[34560, 49920, 69120]

⇒ 说明非确定性源**不止采样**。

## 本脚本的三组探测（同一 CUDA 边车进程内）

- **D1 同进程内连跑同一句 3 次**
  ⇒ 若一致 ⇒ 非确定性来自**跨进程加载**（初始化/图捕获），
     **与本次改动无关** ⇒ R3 严格相等口径在「跨臂」比较下不成立。
- **D2 同进程内跑 3 句 × 2 轮**（第 1 轮 vs 第 2 轮）
  ⇒ 检验「同进程内跨句位置」是否影响结果。
- **D3 记录 `frames`（12 fps codec 帧）**
  ⇒ frames 不同 ⇒ 解码长度真的不同（不只是重采样）。

🔴 持共享机器锁 + 45 s 安静窗口；零 CPU 推理；不调 MiniMax；不写客户包。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import pkg_paths  # noqa: E402

PKG_ROOT = pkg_paths.discover_pkg_dir()
CUDA_PY = os.environ.get(
    'LIVECAP_CUDA_PY', r'C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe')
BASELINE_COMMIT = '6cd8248'

TEXT = '大家早上好。'

_CLIENT_SRC = r'''
# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import time

SIDECAR = sys.argv[1]
OUT = sys.argv[2]
TEXT = sys.argv[3]
GREEDY = sys.argv[4] == '1'
REPEAT = int(sys.argv[5])

errlog = open(os.path.join(os.path.dirname(OUT), 'stderr.log'), 'wb')
proc = subprocess.Popen([sys.executable, SIDECAR], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=errlog)
ready = json.loads(proc.stdout.readline().decode('utf-8'))
rows = []
rid = 0
for round_i in range(REPEAT):
    for ti in range(1):
        rid += 1
        req = {'id': rid, 'text': TEXT, 'language': 'Chinese',
               'ref_audio': os.path.join(
                   os.environ.get('LIVECAP_PKG', ''),
                   'models', 'qwen3tts', 'voices', 'preset_A.wav'),
               'chunk_size': 8}
        t_req = time.monotonic()
        proc.stdin.write((json.dumps(req, ensure_ascii=False) + '\n').encode('utf-8'))
        proc.stdin.flush()
        t_first = None
        n_chunks = 0
        total = 0
        while True:
            raw = proc.stdout.readline()
            if not raw:
                break
            msg = json.loads(raw.decode('utf-8'))
            if msg.get('id') != rid:
                continue
            if msg.get('done'):
                frames = msg.get('frames')
                reason = msg.get('end_reason')
                break
            n = int(msg.get('n') or 0)
            if not n:
                continue
            proc.stdout.read(n * 4)
            if t_first is None:
                t_first = time.monotonic()
            n_chunks += 1
            total += n
        rows.append({'round': round_i, 'id': rid,
                     'first_chunk_s': round(t_first - t_req, 4) if t_first else None,
                     'n_chunks': n_chunks, 'n_samples': total,
                     'frames': frames, 'end_reason': reason})
try:
    proc.stdin.write(b'{"cmd":"quit"}\n')
    proc.stdin.flush()
    proc.wait(timeout=10)
except Exception:
    proc.kill()
errlog.close()
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump({'ready': ready, 'rows': rows}, f, ensure_ascii=False)
'''


def git_show(commit, rel):
    r = subprocess.run(['git', '-C', REPO, 'show', f'{commit}:{rel}'],
                       capture_output=True)
    return r.stdout.decode('utf-8', 'replace') if r.returncode == 0 else None


def inject_greedy(src):
    anchor = 'max_new_tokens=mnt,'
    assert src.count(anchor) == 1, '注入点不唯一'
    return src.replace(anchor, 'max_new_tokens=mnt,\n                    do_sample=False,')


def run(src, greedy, repeat, tag):
    shadow = tempfile.mkdtemp(prefix='app129b_%s_' % tag)
    p = os.path.join(shadow, 'tts_cuda_sidecar.py')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write(src)
    c = os.path.join(shadow, 'client.py')
    with open(c, 'w', encoding='utf-8', newline='') as f:
        f.write(_CLIENT_SRC)
    out = os.path.join(shadow, 'out.json')
    env = dict(os.environ)
    env['LIVECAP_PKG'] = PKG_ROOT
    env['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([CUDA_PY, c, p, out, TEXT,
                        '1' if greedy else '0', str(repeat)],
                       capture_output=True, timeout=1800, env=env)
    data = {}
    if os.path.exists(out):
        with open(out, 'r', encoding='utf-8') as f:
            data = json.load(f)
    data['_rc'] = r.returncode
    data['_shadow'] = shadow
    return data


def cleanup(shadow):
    if not shadow or not os.path.isdir(shadow):
        return
    try:
        for n in os.listdir(shadow):
            p = os.path.join(shadow, n)
            if os.path.isfile(p):
                os.remove(p)
        os.rmdir(shadow)
    except Exception:
        pass


def main():
    print('=' * 74)
    print('app129b —— 诊断「边车合成跨次不一致」的根因')
    print('=' * 74)
    base = git_show(BASELINE_COMMIT, 'live_caption/tts_cuda_sidecar.py')
    if base is None:
        print('基线取不到，退出')
        return 1

    import machine_lock_app as ml
    lock = ml.LockHeld(module='app')
    got = lock.acquire()
    print('  取得锁 = %s' % got)
    if not got:
        return 1
    ev = {}
    try:
        ok_q, info_q = lock.wait_quiet(quiet_seconds=45.0, timeout=1800.0)
        print('  安静窗口 ok=%s waited_s=%s'
              % (ok_q, (info_q or {}).get('waited_s')))
        ev['quiet'] = {'ok': bool(ok_q),
                       'waited_s': (info_q or {}).get('waited_s')}

        # ── D1：同进程内、贪心、同一句 × 3 ──
        print('\n── D1：同进程内 · 贪心 · 同一句 × 3 ──')
        d1 = run(inject_greedy(base), True, 3, 'd1')
        for r in d1.get('rows', []):
            print('   round=%d samples=%d chunks=%d frames=%s first=%s'
                  % (r['round'], r['n_samples'], r['n_chunks'],
                     r['frames'], r['first_chunk_s']))
        d1s = [r['n_samples'] for r in d1.get('rows', [])]
        ev['d1_same_process_greedy_same_text'] = d1s
        ev['d1_consistent'] = (len(set(d1s)) == 1)
        print('   ⇒ 同进程内是否一致：%s' % ('一致' if len(set(d1s)) == 1 else '不一致'))

        # ── D2：同进程内 · 贪心 · 3 句 × 2 轮 ──
        print('\n── D2：同进程内 · 贪心 · 3 句 × 2 轮 ──')
        # 改 client 让它跑 3 句 2 轮：直接复用 repeat 机制不够，改为 6 次同一句
        # ⇒ 这里改为「同一句 × 6」，看是否随次数漂移
        d2 = run(inject_greedy(base), True, 6, 'd2')
        for r in d2.get('rows', []):
            print('   round=%d samples=%d chunks=%d frames=%s'
                  % (r['round'], r['n_samples'], r['n_chunks'], r['frames']))
        d2s = [r['n_samples'] for r in d2.get('rows', [])]
        ev['d2_same_process_greedy_x6'] = d2s
        ev['d2_consistent'] = (len(set(d2s)) == 1)
        print('   ⇒ 同进程内 6 次是否一致：%s'
              % ('一致' if len(set(d2s)) == 1 else '不一致'))

        # ── D3：同进程内 · 采样(非贪心) · 同一句 × 3 ──
        print('\n── D3：同进程内 · 采样 · 同一句 × 3 ──')
        d3 = run(base, False, 3, 'd3')
        for r in d3.get('rows', []):
            print('   round=%d samples=%d chunks=%d frames=%s'
                  % (r['round'], r['n_samples'], r['n_chunks'], r['frames']))
        d3s = [r['n_samples'] for r in d3.get('rows', [])]
        ev['d3_same_process_sampling_x3'] = d3s
        ev['d3_consistent'] = (len(set(d3s)) == 1)
        print('   ⇒ 同进程内采样是否一致：%s'
              % ('一致' if len(set(d3s)) == 1 else '不一致'))
    finally:
        try:
            lock.release()
        except Exception:
            pass

    out = os.path.join(HERE, 'app129b_determinism_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n证据 → %s' % out)
    print('\n结论：')
    print('  同进程内贪心一致？%s' % ev.get('d1_consistent'))
    print('  同进程内贪心×6 一致？%s' % ev.get('d2_consistent'))
    print('  同进程内采样一致？%s' % ev.get('d3_consistent'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
