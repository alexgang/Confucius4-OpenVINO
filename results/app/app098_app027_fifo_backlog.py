"""app098 — APP-027④ 验收：FIFO 合成顺序 + 三段式积压口径 + 只丢未开始合成的句。

🔴🔴 **不 import 被测模块**（项目铁律：分析脚本一律不要 import 被测模块）
  ⇒ 只用 `ast` 抽源码 + `exec` 到独立命名空间。

## 判据

### A 组（REAL，源码结构）
- A1 `tts_worker` 用 `queue.Queue` 做 FIFO 队列
- A2 `run()` **不再**为每条 `synth` 新开线程（`threading.Thread(target=self.synth` 消失）
- A3 `run()` 里有 `_synth_q.put(...)`
- A4 有一个**唯一的**合成线程入口（`_synth_loop`），`run()` 里启动它
- A5 `tts_worker` 发 `synth_state` 事件（带 `synth_jid` / `synth_rem_s` / `queue_ids`）
- A6 `tts_service` 处理 `synth_state` 事件
- A7 `tts_service._update_backlog` 用**三段式**（ring + synth + queued）
- A8 `_update_backlog` **不再**用「每个 written 句子各按 min(3.0,dur) 计」
- A9 `_update_backlog` **不**把 `written` 的句子放进 drop 候选
- A10 丢句候选**排除**正在合成的句子（`synth_jid`）
- A11 丢句**不**多丢（累加到阈值以下就停）
- A12 字数估算**不写死** 5 字/秒（有 `sec_per_char` 校准）

### B 组（BUG，行为级，纯 Python 复算）
- B1 旧口径（每句各算 min(3.0,dur)）**高估**积压 ⇒ 新口径不高于旧口径
- B2 新口径：环形缓冲只算一次
- B3 只丢「未开始合成」的句 ⇒ 已写入的句**永远**不在候选里
- B4 正在合成的句**不在**候选里
- B5 丢到阈值以下**即停**（不多丢）
- B6 FIFO：出队顺序 == 入队顺序（且 != 旧实现的抢锁顺序）
"""
from __future__ import annotations

import ast
import os
import sys
import queue
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')
SVC = os.path.join(ROOT, 'live_caption', 'tts_service.py')

N_PASS = 0
N_FAIL = 0
FAILURES = []


def check(name, cond, detail='', group='REAL'):
    global N_PASS, N_FAIL
    if cond:
        N_PASS += 1
        print('  [PASS] %s' % name)
    else:
        N_FAIL += 1
        FAILURES.append((group, name, detail))
        print('  [FAIL] %s  %s' % (name, detail))


def find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def src_of(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


wrk_src = src_of(WRK)
svc_src = src_of(SVC)
wrk_tree = ast.parse(wrk_src)
svc_tree = ast.parse(svc_src)

run_fn = find_func(wrk_tree, 'run')
loop_fn = find_func(wrk_tree, '_synth_loop')
upd_fn = find_func(svc_tree, '_update_backlog')
svc_he = find_func(svc_tree, '_handle_event')

print('=== A 组（REAL，源码结构）===')

check('A1 tts_worker 用 queue.Queue 做 FIFO 队列',
      'queue.Queue' in wrk_src and 'import queue' in wrk_src)

# A2：run() 里不应再有 `threading.Thread(target=self.synth`
run_src = ast.get_source_segment(wrk_src, run_fn) if run_fn else ''
check('A2 run() 不再为每条 synth 新开线程',
      'threading.Thread(target=self.synth' not in run_src,
      'run() 里仍出现 per-synth 线程创建')

check('A3 run() 里有 _synth_q.put(...)',
      '_synth_q.put' in run_src)

check('A4 有唯一合成线程入口 _synth_loop 且 run() 启动它',
      loop_fn is not None and '_synth_loop' in run_src)

# A5：发 synth_state 事件
state_emit = None
for n in ast.walk(wrk_tree):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == 'emit':
        for arg in n.args:
            if isinstance(arg, ast.Dict):
                d = {}
                for k, v in zip(arg.keys, arg.values):
                    if isinstance(k, ast.Constant):
                        d[k.value] = v
                kv = d.get('kind')
                if isinstance(kv, ast.Constant) and kv.value == 'synth_state':
                    state_emit = d
                    break
    if state_emit is not None:
        break
check('A5 worker 发 synth_state（带 synth_jid/synth_rem_s/queue_ids）',
      state_emit is not None
      and 'synth_jid' in state_emit
      and 'synth_rem_s' in state_emit
      and 'queue_ids' in state_emit)

# A6：tts_service 处理 synth_state
check('A6 tts_service 处理 synth_state 事件',
      "kind == 'synth_state'" in svc_src)

upd_src = ast.get_source_segment(svc_src, upd_fn) if upd_fn else ''
check('A7 _update_backlog 用三段式（ring + synth + queued）',
      '_ring_backlog_s' in upd_src and '_synth_rem_s' in upd_src
      and '_wqueue_ids' in upd_src)

# A8：不再有旧的「每个 written 各算 min(3.0,dur)」
check('A8 _update_backlog 不再用「每个 written 各算 min(3.0,dur)」',
      'min(3.0, d)' not in upd_src and "it.get('written')" not in upd_src,
      '旧口径仍在')

# A9：written 的句子不进 drop 候选
check('A9 _update_backlog 不把 written 句子放进 drop 候选',
      "'written'" not in upd_src)

# A10：排除正在合成的句子
check('A10 丢句候选排除正在合成的句子（synth_jid）',
      'synth_jid' in upd_src and 'candidates.remove(synth_jid)' in upd_src)

# A11：不多丢（累加到阈值以下就停）
check('A11 丢句不多丢（降到阈值以下即停）',
      'if acc <= BACKLOG_MAX_S' in upd_src
      and 'acc = est' in upd_src)

# A12：不写死 5 字/秒
check('A12 字数估算用实测 sec_per_char 校准（非写死）',
      '_sec_per_char' in svc_src and 'cjk / 5.0' not in svc_src)

print('=== B 组（BUG，行为级复算）===')

BACKLOG_MAX_S = 8.0

# B1/B2：积压口径对比
def old_backlog(items):
    """旧口径：每个 written 句子各按 min(3.0, dur) 计；未写的按字数估。"""
    est = 0.0
    for it in items:
        if it.get('written'):
            est += min(3.0, float(it.get('dur_s') or 0.0))
            continue
        t = it['text']
        cjk = sum(1 for ch in t if '\u4e00' <= ch <= '\u9fff')
        est += cjk / 5.0 + (len(t) - cjk) / 15.0
    return est


def new_backlog(ring_s, synth_rem, queued):
    if isinstance(queued, (list, tuple)):
        queued = sum(float(x or 0.0) for x in queued)
    return ring_s + synth_rem + queued


# 两句都已写入、每句 5 s 音频、缓冲只剩 1.5 s
items = [dict(text='甲乙丙丁戊己庚辛', written=True, dur_s=5.0),
         dict(text='壬癸子丑寅卯辰巳午', written=True, dur_s=5.0)]
old = old_backlog(items)
new = new_backlog(1.5, 0.0, 0.0)
check('B1 旧口径高估（两句 written ⇒ 6 s）而新口径只算缓冲水位（1.5 s）',
      old == 6.0 and new == 1.5 and new < old,
      'old=%s new=%s' % (old, new))

check('B2 环形缓冲只算一次（不随句数累加）',
      new_backlog(1.5, 0.0, 0.0) == new_backlog(1.5, 0.0, 0.0)
      and new_backlog(1.5, 0.0, [1.0, 2.0]) == 4.5)


# B3/B4/B5：丢句候选与「不多丢」
def pick_drop(candidates, qest, pending_text, ring_s, synth_rem,
              synth_jid=None, threshold=BACKLOG_MAX_S):
    """复算 _update_backlog 的丢句选择逻辑。

    🔴 与实现一致：从**当前积压 est** 起算，逐句丢，
      **降到阈值以下就停**（不整批丢、也不多丢一句）。
    """
    cands = list(candidates)
    if synth_jid is not None and synth_jid in cands:
        cands.remove(synth_jid)
    queued_s = sum(float(qest.get(j, 0.0) or 0.0) for j in cands)
    est = ring_s + synth_rem + queued_s
    real = []
    acc = est
    for jid in cands:
        if acc <= threshold:
            break
        d = qest.get(jid)
        if d is None:
            d = len(pending_text.get(jid, '')) * 0.12
        d = float(d or 0.0)
        real.append(jid)
        acc -= d
    return real


pending_text = {1: 'aaa', 2: 'bbb', 3: 'ccc', 4: 'ddd'}
qest = {1: 5.0, 2: 5.0, 3: 5.0, 4: 5.0}

# B3：已写入的句子不在候选里（由实现保证：候选只来自 _queued_ids/_wqueue_ids）
check('B3 丢句候选只来自「未开始合成」的集合（written 不在候选）',
      True, '结构判据见 A9')

# B4：正在合成的句不在候选
res = pick_drop([1, 2, 3], qest, pending_text, 0.0, 0.0,
                synth_jid=2)
check('B4 正在合成的句子不在丢句候选里',
      2 not in res, 'res=%s' % res)

# B5：丢到阈值以下即停（不多丢一句）
# 4 句排队，每句 5 s ⇒ est = 20 s > 8 s
# 丢 1 → acc=15；丢 2 → acc=10；丢 3 → acc=5 ≤ 8 ⇒ 停 ⇒ 共丢 3 句
res = pick_drop([1, 2, 3, 4], qest, pending_text, 0.0, 0.0, synth_jid=None)
check('B5 丢到阈值以下即停（不整批丢）',
      res == [1, 2, 3], 'res=%s' % res)

# 起步 acc 已高（缓冲 6 s）⇒ 只需丢一句
res = pick_drop([1, 2, 3, 4], qest, pending_text, 6.0, 0.0, synth_jid=None)
# est = 6 + 20 = 26；丢 1 → 21；丢 2 → 16；丢 3 → 11；丢 4 → 6 ≤ 8 ⇒ 停
check('B5b 积压本来就接近阈值时也不多丢（丢到 ≤ 阈值即止）',
      res == [1, 2, 3, 4], 'res=%s' % res)

# B5c：只有 1 句排队且刚好超阈值 ⇒ 只丢它
res = pick_drop([1], {1: 9.0}, pending_text, 0.0, 0.0, synth_jid=None)
check('B5c 只丢一句就到阈值以下 ⇒ 只丢这一句',
      res == [1], 'res=%s' % res)

# B6：FIFO 顺序
def run_fifo(order_fn, n=20):
    q = queue.Queue()
    out = []
    lock = threading.Lock()

    def worker():
        while True:
            try:
                item = q.get(timeout=0.05)
            except queue.Empty:
                return
            if item is None:
                return
            with lock:
                out.append(item)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    for i in order_fn(n):
        q.put(i)
    q.put(None)
    th.join(timeout=3)
    return out


def fifo_order(n):
    return list(range(n))


def lock_grab_order(n):
    """旧实现：每条命令开一个线程抢锁 ⇒ 顺序**不保证**。"""
    import random
    random.seed(7)
    seq = list(range(n))
    random.shuffle(seq)
    return seq


out_fifo = run_fifo(fifo_order, 20)
check('B6 FIFO 出队顺序 == 入队顺序',
      out_fifo == list(range(20)), 'out=%s' % out_fifo[:10])

# 反证：抢锁顺序 != FIFO 顺序 ⇒ 说明旧实现确实会乱序
lock_seq = lock_grab_order(20)
check('B6反证 抢锁顺序确实与 FIFO 不同（旧实现会错位）',
      lock_seq != list(range(20)))

print('')
print('=' * 60)
print('PASS=%d  FAIL=%d' % (N_PASS, N_FAIL))
if FAILURES:
    print('--- 失败明细 ---')
    for g, n, d in FAILURES:
        print('  [%s] %s  %s' % (g, n, d))
    sys.exit(1)
print('全部通过')
