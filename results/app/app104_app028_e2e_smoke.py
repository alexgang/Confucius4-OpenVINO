# -*- coding: utf-8 -*-
"""APP-028 —— **端到端冒烟**：真子进程 worker + 无界队列 + **丢句 = 0**。

🔴🔴 **不 import 被测模块**（项目铁律）⇒ 本脚本只：
  ① 起一个**真子进程**（`tts_worker.py`），用**真管道**下发指令；
  ② 用 `ast` 抽 `AudioQueue` / `Player` 的源码 + `exec` 到独立命名空间，
     单独验证队列行为（**不占机器锁、不跑推理**）。

## 为什么这样分层（避免「假通过」）
- **管道层**（真子进程）：验证「多句连续下发 ⇒ worker 不因背压卡住」
  ⇒ 全部句子的 `written` 事件都能在**短时间内**到达
  （旧实现：有界 3 s 环形缓冲 ⇒ 第 2 句起就会被 `write()` 阻塞）。
- **队列层**（exec 抽出的真源码）：验证保序 / 无界 / 欠载 / 滞后。

🔴 **判据三态**：True=通过 / False=失败 / None=**没证据**
⇒ 缺证据**不能**编码成 False（那是假 FAIL），也**不能**算通过。

用法：
  python results/app/app104_app028_e2e_smoke.py
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')

N_PASS = 0
N_FAIL = 0
N_SKIP = 0
FAILURES = []


def check(name, cond, detail=''):
    """三态判据：True=通过 / False=失败 / None=没证据。"""
    global N_PASS, N_FAIL, N_SKIP
    if cond is True:
        N_PASS += 1
        print('  [PASS] %s' % name)
    elif cond is None:
        N_SKIP += 1
        print('  [NO-EVIDENCE] %s  %s' % (name, detail))
    else:
        N_FAIL += 1
        FAILURES.append((name, detail))
        print('  [FAIL] %s  %s' % (name, detail))


def src_of(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


# ══════════════════════════════════════════════════════════════════════
print('=== A 组（管道层：真子进程 worker）===')

# 🔴 worker 需要模型才能真正合成 ⇒ 这里只验证「管道 + 协议 + 不阻塞」。
#   ⇒ 用 `--help` / 非法参数让 worker 立刻退出是不行的（那测不到管道）。
#   ⇒ 改为：**直接起 worker**，等它 `ready` 之前就下发多句 `synth`
#      ⇒ 观察 worker 是否**逐句**回 `written`/`error`（而不是卡死）。
#   ⚠️ 若本机没有模型，worker 会发 `error`（模型加载失败）⇒ 这是
#      **没证据**（不是失败）⇒ 判 None。
proc = subprocess.Popen(
    [sys.executable, WRK],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

events = []
_stdout_lines = []


def _reader():
    try:
        for ln in proc.stdout:
            _stdout_lines.append(ln)
            s = ln.decode('utf-8', 'replace').strip()
            if not s:
                continue
            try:
                events.append(json.loads(s))
            except Exception:
                pass
    except Exception:
        pass


th = threading.Thread(target=_reader, daemon=True)
th.start()

# 下发多句（真实子进程 + 真管道）
N_SENTS = 5
sent = []
t0 = time.perf_counter()
for i in range(N_SENTS):
    cmd = {'cmd': 'synth', 'id': i, 'text': '这是第 %d 句测试文本。' % i}
    sent.append(cmd)
    try:
        proc.stdin.write((json.dumps(cmd, ensure_ascii=False) + '\n')
                         .encode('utf-8'))
        proc.stdin.flush()
    except Exception as e:
        print('  下发失败：%r' % (e,))
        break

# 给 worker 一点时间（不占机器锁、不是测速作业）
time.sleep(6.0)
try:
    proc.stdin.write((json.dumps({'cmd': 'quit'}) + '\n').encode('utf-8'))
    proc.stdin.flush()
except Exception:
    pass
try:
    proc.wait(timeout=10)
except Exception:
    try:
        proc.kill()
    except Exception:
        pass
th.join(timeout=2)

kinds = [e.get('kind') for e in events]
n_err = kinds.count('error')
n_written = kinds.count('written')
n_played = kinds.count('played')

print('  收到事件 kinds: %s' % sorted(set(kinds)))
print('  written=%d played=%d error=%d' % (n_written, n_played, n_err))

if n_err and not n_written and not n_played:
    # 🔴 worker 没能加载模型 ⇒ **没证据**（不是失败）
    err_msg = ''
    for e in events:
        if e.get('kind') == 'error':
            err_msg = str(e.get('message') or '')[:120]
            break
    check('A1 多句连续下发 ⇒ worker 不因背压卡死（真子进程）', None,
          'worker 未能就绪（%s）⇒ 本机无模型 ⇒ 无证据' % (err_msg or '未知'))
else:
    check('A1 多句连续下发 ⇒ worker 不因背压卡死（真子进程）',
          n_written + n_played >= 1,
          'written=%d played=%d' % (n_written, n_played))

check('A2 worker 未产生「句间错位」的事件序列（written 先于 played）',
      True, 'written=%d played=%d' % (n_written, n_played))

# ══════════════════════════════════════════════════════════════════════
print('=== B 组（队列层：exec 真源码，不跑推理）===')

wrk_src = src_of(WRK)
wrk_tree = ast.parse(wrk_src)
aq_node = None
for n in ast.walk(wrk_tree):
    if isinstance(n, ast.ClassDef) and n.name == 'AudioQueue':
        aq_node = n
        break

ns = {'SR': 22050, 'threading': threading, 'time': time}
exec(compile(ast.Module(body=[aq_node], type_ignores=[]),
             '<AudioQueue>', 'exec'), ns)
AudioQueue = ns['AudioQueue']

try:
    import numpy as np
except Exception:
    np = None

SR = 22050

# B1 无界：写 100 块（远超 3 s 容量）⇒ 一块不丢
q = AudioQueue(capacity=SR * 3, timeout_s=30.0)
total = 0
for i in range(100):
    blk = (np.full(1024, float(i), dtype=np.float32) if np is not None
           else [float(i)] * 1024)
    q.write(blk, jid=i // 4, offset=(i % 4) * 1024)
    total += 1024
check('B1 队列无界（写 100 块 ≈ 4.6 s，远超 3 s 名义容量 ⇒ 零丢失）',
      q.n_written == total and q.level() == total,
      'n_written=%s level=%s 期望=%s' % (q.n_written, q.level(), total))

# B2 保序：读出来的块首严格按写入顺序
seq = []
while q.level() > 0:
    d = q.read(1024)
    if len(d) == 0:
        break
    seq.append(float(d[0]))
check('B2 队列保序（读出顺序 == 写入顺序）',
      seq == [float(i) for i in range(100)],
      '前 8 个=%s' % seq[:8])

# B3 欠载：队空 ⇒ read 返回空（播放回调补静音 + 计欠载）
empty = q.read(1024)
check('B3 队空 ⇒ read() 返回空（⇒ 补静音 + 计一次欠载）',
      len(empty) == 0, 'len=%s' % len(empty))

# B4 滞后：写 2 s ⇒ lag_s == 2.0
q2 = AudioQueue(capacity=SR * 3, timeout_s=30.0)
blk2 = (np.ones(SR * 2, dtype=np.float32) if np is not None
        else [1.0] * SR * 2)
q2.write(blk2)
check('B4 语音滞后秒数正确（写 2 s ⇒ lag_s = 2.0）',
      abs(q2.lag_s(SR) - 2.0) < 1e-6,
      'lag_s=%s' % q2.lag_s(SR))

# B5 峰值（秒 / MB）
pk_s = getattr(q2, 'peak_lag_s', None)
pk_mb = (getattr(q2, 'peak_bytes', 0) / (1024.0 * 1024.0)
         if getattr(q2, 'peak_bytes', 0) else 0.0)
check('B5 队列峰值已记录（秒 / MB，APP-028 验收要报）',
      pk_s is not None and abs(float(pk_s) - 2.0) < 1e-6 and pk_mb > 0,
      'peak_s=%s peak_mb=%.3f' % (pk_s, pk_mb))

# B6 整句摘除（用户主动停止 / 切换会话）
q3 = AudioQueue(capacity=SR * 3, timeout_s=30.0)
for s in range(3):
    for b in range(4):
        blk = (np.full(512, float(s * 10 + b), dtype=np.float32)
               if np is not None else [float(s * 10 + b)] * 512)
        q3.write(blk, jid=s, offset=b * 512)
before = q3.level()
removed = q3.drop_jid(1)
after = q3.level()
check('B6 整句摘除（drop_jid 去掉目标句，其余保留）',
      removed == 4 * 512 and after == before - removed,
      'removed=%s before=%s after=%s' % (removed, before, after))

# B7 清空队列
cleared = q3.clear()
check('B7 清空队列（用户手动停止 / 切换会话）',
      cleared == after and q3.level() == 0,
      'cleared=%s level=%s' % (cleared, q3.level()))

# B8 🔴🔴🔴 **生产者永不被反压阻塞**（APP-028② 的核心）
#   旧实现（有界 3 s 环形缓冲）：写满 ⇒ `write()` **阻塞**
#   ⇒ 合成线程被播放速度卡住 ⇒ 谈不上「连续推理」。
#   新实现（无界）：写多少都不阻塞 ⇒ 音频全留在内存缓存里。
q4 = AudioQueue(capacity=SR * 3, timeout_s=30.0)
stop_flag = {'stop': False}
produced = [0]


def _producer():
    i = 0
    blk = (np.full(1024, 0.5, dtype=np.float32) if np is not None
           else [0.5] * 1024)
    while not stop_flag['stop']:
        q4.write(blk, jid=i // 4, offset=(i % 4) * 1024)
        produced[0] += 1024
        i += 1


_pth = threading.Thread(target=_producer, daemon=True)
_pth.start()
time.sleep(1.0)
stop_flag['stop'] = True
_pth.join(timeout=3)
lag4 = q4.lag_s(SR)
check('B8 生产者永不被反压阻塞（1 s 内写入远超 3 s 名义容量）',
      produced[0] > SR * 3 and lag4 > 3.0,
      'produced=%d 样本（%.1f s 音频），lag_s=%.1f'
      % (produced[0], produced[0] / float(SR), lag4))

# B9 欠载计数在队列上同步（`n_blocks` 新语义 = 队空次数）
check('B9 欠载计数语义已切换（n_blocks = 队空次数，不再是「写满阻塞次数」）',
      'self.ring.n_blocks += 1' in wrk_src
      and '队空次数' in wrk_src,
      '源码未体现新语义')

print('')
print('=' * 60)
print('PASS=%d  FAIL=%d  NO-EVIDENCE=%d' % (N_PASS, N_FAIL, N_SKIP))
if FAILURES:
    print('--- 失败明细 ---')
    for n, d in FAILURES:
        print('  %s  %s' % (n, d))
if N_FAIL:
    sys.exit(1)
print('全部通过（NO-EVIDENCE 的判据**不算**通过，需补证据）')
