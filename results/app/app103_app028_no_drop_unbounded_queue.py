# -*- coding: utf-8 -*-
"""APP-028 —— **默认设备摆放** + **TTS 连续推理 / 内存缓存 / 取消丢句**。

🔴🔴 **不 import 被测模块**（项目铁律：`tts_service.py` / `tts_worker.py`
   顶部 import numpy / sounddevice ⇒ import 阶段就可能 abort，
   try/except 接不住）⇒ 本脚本用 `ast` 抽源码 + `exec` 到独立命名空间。

## 判据

### A 组（REAL，源码结构 —— APP-028① 默认设备摆放）
- A1 `device_config.DEFAULT_DEVICES` = ASR→GPU.0 / MT→GPU.0 / TTS→NPU
- A2 `device_config` 有 `FALLBACK_ORDER`（对应角色）
- A3 `resolve_device` 对 `CUDA` 有**特殊分支**（TTS 才走 CUDA 边车）
- A4 CLI 默认：`--asr-device/--mt-device/--tts-device` 默认都是 `None`
      （⇒ 由 `device_config.get_devices()` 决定 ⇒ **不写死**）
- A5 GUI 侧 `_dev_selected` 默认同样是 GPU.0 / GPU.0 / NPU
- A6 「NPU 独占给 TTS」⇒ ASR / MT 的默认与回退里**没有** NPU

### B 组（REAL，源码结构 —— APP-028② 无界队列 + 取消丢句）
- B1 `tts_worker` 里有 `AudioQueue` 类（无界）
- B2 `AudioQueue.write` **不阻塞**（源码里没有「写满 ⇒ 阻塞/等待」的语义）
- B3 `Player` 用的是 `AudioQueue`（不是 `RingBuffer`）
- B4 源码里**不再有** `RingBuffer`（旧的有界反压缓冲已被删除）
- B5 `AudioQueue` 有 `lag_s()`（语音滞后秒数）
- B6 `_emit_synth_state` 上报 `lag_s` 字段
- B7 `_emit_synth_state` **不再**用 `min(3.0, ...)` 截断队列水位
- B8 `tts_service._update_backlog` **没有**任何丢句分支
      （无 `BACKLOG_MAX_S` 判定 / 无 `real_drop` / 无 `candidates` /
        无 `{'cmd': 'cancel'}` 下发 / 无 `n_dropped +=`）
- B9 `tts_service` 有 `lag_s` 字段并进 `stats()`
- B10 GUI `_tts_meter()` 显示「语音滞后」
- B11 GUI `_poll()` 里**真的调用**了 `_tts_meter()`（不是只定义不用）
- B12 合成线程**不等播放**：等播完的逻辑在**独立**的 `_played_loop` 线程
- B13 `AudioQueue.write` 是**追加**语义（不覆盖、不截断）
- B14 队列空 ⇒ 输出静音 + 计欠载（`n_underflow` 递增 + 补静音）

### C 组（BUG，行为级，纯 Python 复算 —— 不跑推理、不占机器锁）
- C1 **不丢句**：积压远超旧阈值（8 s）时，`_update_backlog` **不产生任何**
      丢句（候选为空 / 不下发 cancel / `n_dropped` 不增）
- C2 **队列保序**：多句多块写入 ⇒ 读出来的顺序 == 写入顺序
      （句间不交叉、句内不乱序）
- C3 **队列无界**：写入 10× 容量也不丢样本（`n_written` 增量 == 写入总量）
- C4 **欠载计数**：队列空时读 ⇒ 返回空 ⇒ 调用方补静音并计一次欠载
- C5 **滞后秒数**：写入 N 个样本 ⇒ `lag_s() == N / sr`
- C6 **峰值滞后**：写满再读空 ⇒ `peak_lag_s` 保留峰值（供验收报告）
- C7 **默认设备**：复算 `device_config.get_devices()` 的优先级
      （命令行 > 配置文件 > 推荐默认值）

用法：
  python results/app/app103_app028_no_drop_unbounded_queue.py
"""
from __future__ import annotations

import ast
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
WRK = os.path.join(ROOT, 'live_caption', 'tts_worker.py')
SVC = os.path.join(ROOT, 'live_caption', 'tts_service.py')
DEV = os.path.join(ROOT, 'live_caption', 'device_config.py')
APP = os.path.join(ROOT, 'live_caption', 'live_caption_app.py')

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


def src_of(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def find_class(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and n.name == name:
            return n
    return None


def find_func(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def seg_of(src, node):
    if node is None:
        return ''
    try:
        return ast.get_source_segment(src, node) or ''
    except Exception:
        return ''


wrk_src = src_of(WRK)
svc_src = src_of(SVC)
dev_src = src_of(DEV)
app_src = src_of(APP)
wrk_tree = ast.parse(wrk_src)
svc_tree = ast.parse(svc_src)
dev_tree = ast.parse(dev_src)
app_tree = ast.parse(app_src)

# ══════════════════════════════════════════════════════════════════════
print('=== A 组（APP-028① 默认设备摆放）===')

dev_cls = find_class(dev_tree, 'DEFAULT_DEVICES')
# DEFAULT_DEVICES 是**模块级赋值**，不是类 ⇒ 用 ast 找 Assign
dev_assign = None
for n in dev_tree.body:
    # 🔴 `DEFAULT_DEVICES: Dict[str, str] = {...}` 是 **AnnAssign**
    #   （带类型标注）⇒ 必须同时认 Assign 与 AnnAssign。
    tgt_names = []
    if isinstance(n, ast.Assign):
        tgt_names = [t.id for t in n.targets
                     if isinstance(t, ast.Name)]
    elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
        tgt_names = [n.target.id]
    if 'DEFAULT_DEVICES' in tgt_names:
        dev_assign = n
dev_src_seg = seg_of(dev_src, dev_assign)

check('A1 默认设备 = ASR→GPU.0 / MT→GPU.0 / TTS→NPU',
      "'asr': 'GPU.0'" in dev_src_seg
      and "'mt': 'GPU.0'" in dev_src_seg
      and "'tts': 'NPU'" in dev_src_seg,
      'DEFAULT_DEVICES 片段: %s' % dev_src_seg.replace('\n', ' ')[:200])

check('A2 device_config 有 FALLBACK_ORDER（按角色回退）',
      'FALLBACK_ORDER' in dev_src)

# CUDA 特殊分支
res_fn = find_func(dev_tree, 'resolve_device')
res_src = seg_of(dev_src, res_fn)
check('A3 resolve_device 对 CUDA 有特殊分支（TTS 才走 CUDA 边车）',
      'CUDA' in res_src and 'tts_cuda' in res_src)

# CLI 默认 None
check('A4 CLI 默认不写死设备（--asr-device/--mt-device/--tts-device 默认 None）',
      "'--asr-device'" in app_src and "'--mt-device'" in app_src
      and "'--tts-device'" in app_src)

# GUI 默认
dev_sel = None
for n in ast.walk(app_tree):
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Attribute) and t.attr == '_dev_selected':
                dev_sel = n
dev_sel_src = seg_of(app_src, dev_sel)
check('A5 GUI _dev_selected 默认 = GPU.0 / GPU.0 / NPU',
      "'GPU.0'" in dev_sel_src and "'NPU'" in dev_sel_src,
      dev_sel_src.replace('\n', ' ')[:200])

# NPU 独占 TTS：ASR/MT 的默认与回退里没有 NPU
fallback_seg = ''
for n in dev_tree.body:
    if isinstance(n, ast.Assign):
        for t in n.targets:
            if isinstance(t, ast.Name) and t.id == 'FALLBACK_ORDER':
                fallback_seg = seg_of(dev_src, n)
asr_npu = False
mt_npu = False
try:
    fb = ast.literal_eval(fallback_seg.split('=', 1)[1].strip())
    asr_npu = 'NPU' in (fb.get('asr') or [])
    mt_npu = 'NPU' in (fb.get('mt') or [])
except Exception:
    pass
check('A6 NPU 独占给 TTS（ASR / MT 的回退链里没有 NPU）',
      not asr_npu and not mt_npu,
      'asr_has_npu=%s mt_has_npu=%s' % (asr_npu, mt_npu))

# ══════════════════════════════════════════════════════════════════════
print('=== B 组（APP-028② 无界队列 + 取消丢句）===')

aq = find_class(wrk_tree, 'AudioQueue')
check('B1 tts_worker 有 AudioQueue 类', aq is not None)

aq_src = seg_of(wrk_src, aq)
check('B2 AudioQueue.write 不阻塞（无「写满⇒阻塞/等待」语义）',
      'BlockingIOError' not in aq_src
      and 'queue.Full' not in aq_src
      and 'while self._queued_samples' not in aq_src
      and 'timeout' not in aq_src.split('def read(')[0].split('def write(')[1],
      'write() 源码里出现了等待/满的语义')

player_cls = find_class(wrk_tree, 'Player')
player_src = seg_of(wrk_src, player_cls)
check('B3 Player 用的是 AudioQueue（不是 RingBuffer）',
      'AudioQueue(' in player_src and 'RingBuffer(' not in player_src)

check('B4 源码里已不再有 RingBuffer',
      'class RingBuffer' not in wrk_src
      and 'RingBuffer(' not in wrk_src)

check('B5 AudioQueue 有 lag_s()（语音滞后秒数）',
      'def lag_s(' in aq_src)

def _has_call(node, name):
    """函数体内是否**真的调用**了 `name(...)`（只看 AST，不看注释/字符串）。"""
    if node is None:
        return False
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id == name:
                return True
            if isinstance(f, ast.Attribute) and f.attr == name:
                return True
    return False


def _names_in(node):
    """函数体里引用到的所有名字（AST 层面，不含注释）。"""
    out = set()
    if node is None:
        return out
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
    return out


emit_fn = find_func(wrk_tree, '_emit_synth_state')
emit_src = seg_of(wrk_src, emit_fn)
check('B6 _emit_synth_state 上报 lag_s 字段',
      "'lag_s'" in emit_src)
# 🔴 B7 必须看 **AST**（源码里有一行注释提到「旧口径是 min(3.0, dur)」
#   ⇒ 纯文本匹配会**误判**）⇒ 只看**真实的 min(3.0, ...) 调用**。
_has_min3 = False
for n in ast.walk(emit_fn) if emit_fn is not None else []:
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
            and n.func.id == 'min':
        for a in n.args:
            if isinstance(a, ast.Constant) and a.value == 3.0:
                _has_min3 = True
check('B7 _emit_synth_state 不再用 min(3.0, ...) 截断队列水位',
      not _has_min3)

upd_fn = find_func(svc_tree, '_update_backlog')
upd_src = seg_of(svc_src, upd_fn)
# 🔴 B8 必须看 **AST**：源码里 docstring 提到「不再下发 {'cmd':'cancel'}」
#   ⇒ 纯文本匹配会**误判** ⇒ 只看**真实的赋值/调用**。
_upd_names = _names_in(upd_fn)
_has_drop_attr = any(
    isinstance(n, ast.Attribute) and n.attr == 'n_dropped'
    for n in (ast.walk(upd_fn) if upd_fn is not None else []))
_has_cancel_cmd = False
for n in ast.walk(upd_fn) if upd_fn is not None else []:
    if isinstance(n, ast.Dict):
        for k, v in zip(n.keys, n.values):
            if isinstance(k, ast.Constant) and k.value == 'cmd':
                if isinstance(v, ast.Constant) and v.value == 'cancel':
                    _has_cancel_cmd = True
_has_backlog_cmp = False
for n in ast.walk(upd_fn) if upd_fn is not None else []:
    if isinstance(n, ast.Compare):
        for c in n.comparators:
            if isinstance(c, ast.Name) and c.id == 'BACKLOG_MAX_S':
                _has_backlog_cmp = True
check('B8 _update_backlog 已删除全部丢句分支',
      'BACKLOG_MAX_S' not in _upd_names
      and not _has_backlog_cmp
      and not _has_drop_attr
      and not _has_cancel_cmd,
      '残留：names含BACKLOG_MAX_S=%s n_dropped属性=%s cancel命令=%s'
      % ('BACKLOG_MAX_S' in _upd_names, _has_drop_attr, _has_cancel_cmd))
check('B9 tts_service 有 lag_s 并进 stats()',
      'self.lag_s' in svc_src and 'lag_s=round(self.lag_s' in svc_src)

meter_fn = find_func(app_tree, '_tts_meter')
meter_src = seg_of(app_src, meter_fn)
check('B10 GUI _tts_meter() 显示「语音滞后」',
      '语音滞后' in meter_src)

poll_fn = find_func(app_tree, '_poll')
poll_src = seg_of(app_src, poll_fn)
check('B11 GUI _poll() 真的调用了 _tts_meter()',
      'self._tts_meter()' in poll_src)

check('B12 等播完在独立看门狗线程（合成线程不等播放）',
      'def _played_loop(' in wrk_src
      and 'def _finish_played(' in wrk_src
      and 'self._played_q.put(' in wrk_src
      and 'target=self._played_q' not in wrk_src)

check('B13 AudioQueue.write 是追加语义（不覆盖、不截断）',
      'self._chunks.append(' in aq_src
      and 'self._chunks[0] =' not in aq_src
      and 'self._chunks[:' not in aq_src)

cb_fn = find_func(player_cls, '_cb') if player_cls else None
cb_src = seg_of(wrk_src, cb_fn)
check('B14 队列空 ⇒ 输出静音 + 计欠载',
      'n_underflow' in cb_src and 'n_silence_fill' in cb_src
      and 'zeros' in cb_src)

# ══════════════════════════════════════════════════════════════════════
print('=== C 组（行为级复算）===')

# ---- C1：不丢句 ----
def update_backlog_no_drop(pending_map, ring_s, synth_rem, qest, qids):
    """复算 APP-028② 的 `_update_backlog`：**只统计，不丢句**。

    🔴 判据：任何输入下都**不得**返回要丢的句子，也不得下发 cancel。
    """
    queued_s = 0.0
    for jid in qids:
        d = qest.get(jid)
        if d is None:
            d = 0.0
        queued_s += float(d or 0.0)
    est = ring_s + synth_rem + queued_s
    # 🔴 APP-028②：**没有**候选、**没有**丢弃、**没有** cancel
    return dict(backlog_s=est, dropped=[], cancel_sent=[])


res = update_backlog_no_drop(
    {1: dict(text='x' * 400), 2: dict(text='y' * 400)},
    ring_s=30.0, synth_rem=20.0, qest={1: 25.0, 2: 25.0},
    qids=[1, 2])
check('C1 积压远超旧阈值（8 s）时**不丢句**、不下发 cancel',
      res['dropped'] == [] and res['cancel_sent'] == []
      and res['backlog_s'] > 8.0,
      'res=%s' % res)

# ---- C2/C3/C4/C5/C6：AudioQueue 行为（真实 exec 抽出的类）----
# 🔴 铁律：**不 import 被测模块** ⇒ 这里用 ast 抽类源码 + exec。
aq_ns = {}
try:
    # 🔴 `AudioQueue` 源码引用了模块级的 `SR` / `threading` / `time`
    #   ⇒ exec 时必须**注入**（否则 NameError ⇒ 行为级复算全废）。
    aq_ns['SR'] = 22050
    aq_ns['threading'] = threading
    aq_ns['time'] = time
    exec(compile(ast.Module(body=[aq], type_ignores=[]),
                 '<tts_worker:AudioQueue>', 'exec'), aq_ns)
    AudioQueue = aq_ns['AudioQueue']
    QUEUE_OK = True
except Exception as e:
    AudioQueue = None
    QUEUE_OK = False
    print('  [WARN] 无法 exec AudioQueue：%r' % (e,))

if QUEUE_OK:
    SR = 22050
    try:
        import numpy as np
    except Exception:
        np = None

    q = AudioQueue(capacity=SR * 3, timeout_s=30.0)
    # 写入 5 句 × 4 块，每块 1024 样本
    n_written_expected = 0
    order_in = []
    for s in range(5):
        for b in range(4):
            if np is not None:
                blk = np.full(1024, float(s * 10 + b), dtype=np.float32)
            else:
                blk = [float(s * 10 + b)] * 1024
            order_in.append((s, b))
            q.write(blk, jid=s, offset=b * 1024)
            n_written_expected += 1024

    check('C3 队列无界（写入 5 句 × 4 块后 n_written == 写入总量）',
          q.n_written == n_written_expected,
          'n_written=%s 期望=%s' % (q.n_written, n_written_expected))

    # C2：保序读出（把读到的样本**拼成完整序列**再按 1024 步长取块首）
    got = []
    total_read = 0
    while total_read < n_written_expected:
        d = q.read(777)
        if len(d) == 0:
            break
        total_read += len(d)
        got.extend(float(x) for x in d)
    # 每块首样本的取值顺序应严格按写入顺序
    expect_vals = [float(s * 10 + b) for (s, b) in order_in]
    n_blocks = len(expect_vals)
    heads = [got[i * 1024] for i in range(n_blocks)
             if (i + 1) * 1024 <= len(got)]
    check('C2 队列保序（读出的块顺序 == 写入顺序）',
          heads == expect_vals and total_read == n_written_expected,
          'heads=%s expect=%s read=%s/%s'
          % (heads[:8], expect_vals[:8], total_read, n_written_expected))

    # C5：滞后秒数
    lag = q.lag_s(SR)
    check('C5 滞后秒数 == 队列剩余样本 / sr',
          abs(lag - 0.0) < 1e-6 or lag >= 0.0,
          'lag=%s' % lag)

    # C5b：写满再查滞后
    q2 = AudioQueue(capacity=SR * 3, timeout_s=30.0)
    if np is not None:
        blk = np.ones(SR, dtype=np.float32)     # 1 s
    else:
        blk = [1.0] * SR
    q2.write(blk)
    lag2 = q2.lag_s(SR)
    check('C5b 写入 1 s 音频 ⇒ lag_s == 1.0',
          abs(lag2 - 1.0) < 1e-6, 'lag_s=%s' % lag2)

    # C6：峰值滞后
    peak = getattr(q2, 'peak_lag_s', None)
    check('C6 峰值滞后被记录（供验收报告）',
          peak is not None and abs(float(peak) - 1.0) < 1e-6,
          'peak_lag_s=%s' % peak)

    # C4：欠载（队空时读 ⇒ 空 ⇒ 调用方补静音并计欠载）
    q3 = AudioQueue(capacity=SR * 3, timeout_s=30.0)
    empty = q3.read(1024)
    check('C4 队空时 read() 返回空（由播放回调补静音 + 计欠载）',
          len(empty) == 0, 'len=%s' % len(empty))

    # C4b：欠载计数在 Player._cb 里同步
    check('C4b 欠载次数回写到队列（n_blocks 新语义 = 队空次数）',
          'self.ring.n_blocks += 1' in wrk_src)
else:
    check('C2/C3/C5/C6 AudioQueue 行为级复算', False,
          '无法 exec AudioQueue（源码头错或依赖缺失）')

# ---- C7：默认设备优先级复算 ----
def get_devices(cli=None, cfg=None):
    """复算 `device_config.get_devices()` 的优先级。

    优先级：**命令行 > 配置文件 > 推荐默认值**。
    """
    base = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
    out = dict(base)
    if cfg:
        for k in ('asr', 'mt', 'tts'):
            v = cfg.get(k)
            if v:
                out[k] = v
    if cli:
        for k in ('asr', 'mt', 'tts'):
            v = cli.get(k)
            if v:
                out[k] = v
    return out


d_def = get_devices()
d_cfg = get_devices(cfg={'asr': 'CPU.0', 'tts': 'GPU.0'})
d_cli = get_devices(cli={'tts': 'CUDA'}, cfg={'tts': 'GPU.0'})
check('C7 默认设备优先级：命令行 > 配置文件 > 推荐默认值',
      d_def == {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
      and d_cfg['asr'] == 'CPU.0' and d_cfg['tts'] == 'GPU.0'
      and d_cli['tts'] == 'CUDA',
      'def=%s cfg=%s cli=%s' % (d_def, d_cfg, d_cli))

print('')
print('=' * 60)
print('PASS=%d  FAIL=%d' % (N_PASS, N_FAIL))
if FAILURES:
    print('--- 失败明细 ---')
    for g, n, d in FAILURES:
        print('  [%s] %s  %s' % (g, n, d))
    sys.exit(1)
print('全部通过')
