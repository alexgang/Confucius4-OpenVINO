# -*- coding: utf-8 -*-
"""app134 —— APP-036 C1–C4：**遥测口径修正** 的验收（零推理、零硬件）。

## reviewer APP-036 C 原文（只做 C，D 不做）

> C. 要修的遥测口径（App 职责）：
>   1. worker jsonl 的 `t_submit` 是在 `_synth_babelvox` 开头取的 `perf_counter()`，
>      所以 `t_dequeue==t_submit`、`queue_lag_s` 恒为 0；
>      ⇒ 改法：worker 读到 stdin 命令时记 `t_recv`，
>      jsonl 里加 `worker_fifo_wait_s = t_dequeue − t_recv`，报告给出 P50/P95/max。
>   2. `app028_backlog_curve.csv` 只有收尾时的 1 行，不算曲线。
>      改成每 1–2 s 采样一次 `backlog_s / backlog_parts / lag_s`
>      （**在落盘模式下也要采**），并按 1 s 粒度用 `source_t` 对齐。
>   3. `end_lag_s=0.0` 是 drain 之后取的值，没有意义。
>      新增 `end_lag_s = 最后一句播完（或写完）的时刻 − 源音频结束时刻`，
>      播放模式和落盘模式各自给出。
>   4. CLI 收尾的统计行在 `close()` 之前打印 ⇒ 改成 close() 之后再打印一次
>      最终统计，或者把 drain 超时设为 max(120, 1.5×当前积压)，
>      并在报告里列出 `n_discard_on_close`。

## 本脚本验什么

| 组 | 对应 | 判据 |
|---|---|---|
| **C1** | C1 | worker jsonl **必须**有 `t_recv` / `t_enqueue` / `worker_fifo_wait_s` / `worker_fifo_wait_total_s`；且 `worker_fifo_wait_total_s` **能算出非 0 的排队**（老口径恒 0） |
| **C2** | C2 | 曲线 csv **≥100 个采样点**（老实现 1 行）；列含 `backlog_s` / `lag_s` / 三段式；**落盘模式也采**（`out_wav` 非空时仍有曲线） |
| **C3** | C3 | `end_lag_s` = 「最后一句播完」−「源音频结束」（**主进程时钟**）；跨进程不可相减 ⇒ 断言两个点同在主进程 |
| **C4** | C4 | `n_discard_on_close` **单独计数**（不混 `n_dropped`）；`close()` 后统计里能看到；CLI **close 后**再打印一次最终统计；drain 超时 = `max(120, 1.5×积压)` |
| **反证** | — | 4 条源码级注入 ⇒ 对应判据必须 FAIL（证明判据不是恒真） |

## 🔴 纪律

- **零推理 / 零 GPU / 零 NPU / 零声卡** ⇒ 只测「口径与账本」，不碰引擎。
- **不 import 被测模块** ⇒ `ast` 抽源码 + `exec` 独立命名空间。
- **固定解释器**：system **3.12**（managed 3.13 无 numpy ⇒ `synth()` 会 `ModuleNotFoundError`
  ⇒ 那是**解释器差异**不是产品缺陷）。

## 用法

    <py312> results/app/app134_app036c_telemetry.py
"""
from __future__ import annotations

import ast
import json
import os
import sys
import tempfile
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC_ROOT = os.environ.get('APP134_SRC_ROOT') or REPO
_SUBDIR = 'app' if os.path.isdir(os.path.join(SRC_ROOT, 'app')) else 'live_caption'

WORKER_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_worker.py')
SERVICE_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'tts_service.py')
APP_PATH = os.path.join(SRC_ROOT, _SUBDIR, 'live_caption_app.py')

EVID_PATH = os.environ.get('APP134_EVID') or os.path.join(
    HERE, 'app134_app036c_telemetry_evidence.json')

EVID = {'script': 'app134_app036c_telemetry.py',
        'src_root': SRC_ROOT, 'subdir': _SUBDIR,
        'python': sys.executable,
        'groups': {}, 'checks': []}


def check(group, name, ok, detail=''):
    ok = bool(ok)
    EVID['checks'].append({'group': group, 'name': name, 'pass': ok,
                           'detail': str(detail)})
    EVID.setdefault('groups', {}).setdefault(group, []).append(bool(ok))
    print('  [%s] %-4s %s — %s' % ('PASS' if ok else 'FAIL', group, name,
                                   detail))
    return ok


def load_ns(path, name):
    src = open(path, 'r', encoding='utf-8').read()
    tree = ast.parse(src, filename=path)
    body = [n for n in tree.body
            if not (isinstance(n, ast.If)
                    and isinstance(n.test, ast.Compare)
                    and getattr(n.test.left, 'id', None) == '__name__')]
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {'__name__': name, '__file__': path}
    exec(compile(mod, path, 'exec'), ns)
    return ns, src


def load_ns_src(src_text, name, path):
    tree = ast.parse(src_text, filename=path)
    body = [n for n in tree.body
            if not (isinstance(n, ast.If)
                    and isinstance(n.test, ast.Compare)
                    and getattr(n.test.left, 'id', None) == '__name__')]
    mod = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(mod)
    ns = {'__name__': name, '__file__': path}
    exec(compile(mod, path, 'exec'), ns)
    return ns


# ══════════════════════════════════════════════════════════════════
# C1 —— worker 侧排队口径
# ══════════════════════════════════════════════════════════════════
def group_c1(ns_w, tmpd):
    g = 'C1'
    W = ns_w['TTSWorker']

    # ── C1-a：`_APP036_JSONL_KEYS` 必须含 4 个新字段 ──
    keys = ns_w['_APP036_JSONL_KEYS']
    for k in ('t_recv', 't_enqueue', 'worker_fifo_wait_s',
              'worker_fifo_wait_total_s'):
        check(g, 'jsonl 键集含 %s' % k, k in keys,
              '_APP036_JSONL_KEYS = %s' % (list(keys),))

    # ── C1-b：主循环必须记 `t_recv`（读到 stdin 的时刻）──
    src = open(WORKER_PATH, 'r', encoding='utf-8').read()
    check(g, '主循环记 t_recv（读到 stdin 的时刻）',
          't_recv = time.perf_counter()' in src,
          '源码含 `t_recv = time.perf_counter()`')
    check(g, '入队时记 t_enqueue',
          't_enqueue = time.perf_counter()' in src,
          '源码含 `t_enqueue = time.perf_counter()`')

    # ── C1-c：**真的**跑一遍主循环，验证排队能算出来（非 0）──
    #   做法：造一个 worker 实例，**手工**模拟主循环的三步
    #   （t_recv → t_enqueue → t_dequeue），然后调 `synth()` 的**空句分支**
    #   （不进引擎）⇒ 从 jsonl 行里读 `worker_fifo_wait_total_s`。
    jsonl = os.path.join(tmpd, 'c1.tts.jsonl')
    w = object.__new__(W)
    w._dequeue_at = {}
    w._recv_at = {}
    w._enqueue_at = {}
    w._last_lang = None
    w._last_lang_src = None
    w._last_end_reason = None
    w._last_lead_punct = ''
    w._last_lead_punct_n = 0
    w._last_clone_active = False
    w._last_clone_mode = None
    w._last_clone_audio_s = 0.0
    w._last_spk = None
    w._last_spk_conf = None
    w._last_est_frames = None
    w._last_max_new_tokens = None
    w.player = None
    w.out_wav = None
    w.dump_dir = None
    w.sr = 24000
    w.voice = 'A'
    w.conds = {}
    w.engine = None
    w.ov_rt = None
    w._clone_active = False
    w._clone_mode = None
    w._clone_audio_s = 0.0
    w._stop = type('S', (), {'is_set': staticmethod(lambda: False)})()
    w._jsonl_rows = []
    w._jsonl_path = jsonl
    w._timeline = []
    w._t0 = None
    w._synth_lock = threading.Lock()
    w._is_cancelled = lambda jid: False

    ns_w['emit'] = lambda obj: None
    ns_w['log'] = lambda m: None

    # 模拟：读到命令 → 等 1.2 s（排队）→ 入队 → 再等 0.3 s → 出队
    t0 = time.perf_counter()
    t_recv = t0
    time.sleep(1.2)
    t_enqueue = time.perf_counter()
    time.sleep(0.3)
    t_dequeue = time.perf_counter()

    w._recv_at[5] = t_recv
    w._enqueue_at[5] = t_enqueue
    w._dequeue_at[5] = t_dequeue
    w.synth(5, '，', None, None, 'zh', t_recv)

    rows = []
    if os.path.exists(jsonl):
        with open(jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    check(g, 'jsonl 有 1 行', len(rows) == 1, '实际 = %d' % len(rows))
    if not rows:
        return
    r = rows[0]
    check(g, '行含 t_recv', r.get('t_recv') is not None,
          't_recv = %r' % r.get('t_recv'))
    check(g, '行含 t_enqueue', r.get('t_enqueue') is not None,
          't_enqueue = %r' % r.get('t_enqueue'))
    wfw = r.get('worker_fifo_wait_s')
    wfwt = r.get('worker_fifo_wait_total_s')
    check(g, 'worker_fifo_wait_s ≈ 1.2（入队前等待）',
          wfw is not None and 1.0 <= wfw <= 1.6,
          '实际 = %r' % wfw)
    check(g, 'worker_fifo_wait_total_s ≈ 1.5（**排队真的被量到**）',
          wfwt is not None and 1.3 <= wfwt <= 1.9,
          '实际 = %r' % wfwt)
    check(g, '**老口径量不到排队**（t_submit−t_dequeue ≈ 0）',
          abs((r.get('t_submit') or 0) - (r.get('t_dequeue') or 0)) < 0.5,
          't_submit=%r vs t_dequeue=%r ⇒ 差 %r s'
          % (r.get('t_submit'), r.get('t_dequeue'),
             (r.get('t_submit') or 0) - (r.get('t_dequeue') or 0)))
    check(g, '**新口径量得到排队**（t_dequeue−t_recv ≈ 1.5）',
          abs((r.get('t_dequeue') or 0) - (r.get('t_recv') or 0)) > 1.0,
          't_dequeue=%r vs t_recv=%r ⇒ 差 %r s'
          % (r.get('t_dequeue'), r.get('t_recv'),
             (r.get('t_dequeue') or 0) - (r.get('t_recv') or 0)))


# ══════════════════════════════════════════════════════════════════
# C2 —— 积压曲线采样
# ══════════════════════════════════════════════════════════════════
def group_c2(ns_s, tmpd):
    g = 'C2'
    S = ns_s['TTSService']

    def new_svc(**kw):
        return S(device='GPU.0', on_log=lambda m: None, auto=False, **kw)

    # ── C2-a：落盘模式（out_wav 非空）**也要有曲线** ──
    #   🔴 **只用采样线程**（不手工插点）⇒ 行序天然单调 ⇒ 可断言 t_s 递增。
    #   之前混用手工插点 + 线程 ⇒ 两者交错 ⇒ t_s 非单调（**是判据构造缺陷**，
    #   不是产品缺陷）。
    #   ⚠️ 采样间隔被产品代码钳到 **0.2 s 下限**（`max(0.2, interval_s)`）
    #     ⇒ 要凑够 100 点 ⇒ 至少要 20 s ⇒ 这里跑 21 s。
    svc = new_svc(out_wav=os.path.join(tmpd, 'o.wav'))
    svc.start_curve_sampler(interval_s=0.2)
    t_end = time.perf_counter() + 21.0
    while time.perf_counter() < t_end:
        svc.backlog_s = float(int(time.perf_counter() * 10) % 100)
        svc.lag_s = svc.backlog_s * 0.9
        svc.backlog_parts = dict(ring_s=1.0, synth_s=2.0, queued_s=3.0)
        svc.n_played = 1
        time.sleep(0.05)
    svc.stop_curve_sampler()
    rows = svc.curve_rows()
    check(g, '**落盘模式**也有曲线（老实现只有 1 行）', len(rows) >= 100,
          '采样点 = %d' % len(rows))
    check(g, '曲线行含 backlog_s / lag_s',
          all(('backlog_s' in r and 'lag_s' in r) for r in rows),
          '首行键 = %s' % sorted(rows[0].keys()) if rows else '无行')
    check(g, '曲线行含三段式 ring/synth/queued',
          all(('ring_s' in r and 'synth_s' in r and 'queued_s' in r)
              for r in rows),
          '首行键 = %s' % sorted(rows[0].keys()) if rows else '无行')
    check(g, '曲线行含 n_empty（APP-037 C 三段式）',
          all('n_empty' in r for r in rows),
          '首行键 = %s' % sorted(rows[0].keys()) if rows else '无行')

    # ── C2-b：采样间隔默认 1–2 s（reviewer 明文）──
    svc2 = new_svc()
    check(g, '默认采样间隔在 1–2 s 之间',
          1.0 <= svc2._curve_interval_s <= 2.0,
          '实际 = %r' % svc2._curve_interval_s)

    # ── C2-c：csv 落盘 ──
    csv_path = os.path.join(tmpd, 'curve.csv')
    ok = svc.write_curve_csv(csv_path)
    check(g, 'write_curve_csv 成功', ok, '路径 = %s' % csv_path)
    if ok and os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = [x for x in f.read().splitlines() if x.strip()]
        check(g, 'csv 有 ≥101 行（表头 + ≥100 采样点）', len(lines) >= 101,
              '实际 = %d 行' % len(lines))
        check(g, 'csv 表头含 backlog_s/lag_s/ring_s/synth_s/queued_s',
              all(c in lines[0] for c in ('backlog_s', 'lag_s', 'ring_s',
                                         'synth_s', 'queued_s')),
              '表头 = %s' % lines[0])
        # t_s **非递减**（采样点可能落在同一毫秒 ⇒ 允许相等）
        ts = [float(x.split(',')[0]) for x in lines[1:]]
        check(g, 't_s 非递减', all(ts[i] <= ts[i + 1]
                                  for i in range(len(ts) - 1)),
              '首/尾 = %r / %r' % (ts[0] if ts else None,
                                  ts[-1] if ts else None))
        check(g, 't_s 严格递增（毫秒级）',
              len(set(ts)) == len(ts),
              '唯一值 %d / 总数 %d（相等说明同一毫秒内采样 ⇒ 允许）'
              % (len(set(ts)), len(ts)))


# ══════════════════════════════════════════════════════════════════
# C3 —— end_lag_s 真实定义
# ══════════════════════════════════════════════════════════════════
def group_c3(ns_s):
    g = 'C3'
    S = ns_s['TTSService']
    svc = S(device='GPU.0', on_log=lambda m: None, auto=False)

    # ── C3-a：未打点时 end_lag_s 必须是 None（不是 0.0）──
    check(g, '未打点时 end_lag_s = None（老口径是 0.0，没意义）',
          svc.end_lag_s is None, '实际 = %r' % svc.end_lag_s)

    # ── C3-b：先打「源结束」再打「最后一句播完」⇒ 应为正数 ──
    svc.set_source_end(time.perf_counter())
    time.sleep(0.05)
    svc._last_out_t = time.perf_counter()
    svc._recompute_end_lag()
    check(g, 'end_lag_s > 0（= 播完时刻 − 源结束时刻）',
          svc.end_lag_s is not None and svc.end_lag_s > 0.04,
          '实际 = %r' % svc.end_lag_s)

    # ── C3-c：源结束**晚于**最后播完 ⇒ 应为**负数** ──
    #   ⇒ 证明它真的是「相减」而不是「取绝对值/取 max」
    svc2 = S(device='GPU.0', on_log=lambda m: None, auto=False)
    svc2._last_out_t = time.perf_counter()
    svc2.set_source_end(time.perf_counter() + 1.0)   # 源结束在 1 s 之后
    check(g, '源结束晚于播完 ⇒ end_lag_s < 0（是相减不是取绝对值）',
          svc2.end_lag_s is not None and svc2.end_lag_s < 0,
          '实际 = %r' % svc2.end_lag_s)

    # ── C3-d：两个点必须同在主进程时钟域 ──
    #   ⇒ worker 侧**不得**出现 `end_lag_s` 的计算
    src_w = open(WORKER_PATH, 'r', encoding='utf-8').read()
    # `end_lag_s` 在 worker 的 jsonl 键集里是**允许**的（作为字段透传位），
    # 但**不允许**在 worker 里做「减法」⇒ 查 `end_lag_s` 与 `-` 的共现。
    has_sub = ('end_lag_s' in src_w
               and ('end_lag_s -' in src_w or 'end_lag_s-' in src_w
                    or '- end_lag_s' in src_w))
    check(g, '**worker 侧不计算** end_lag_s（跨进程时钟不可相减）',
          not has_sub,
          'worker 源码含 end_lag_s 减法 = %s' % has_sub)

    # ── C3-e：`played` 事件会更新 `_last_out_t` ──
    svc3 = S(device='GPU.0', on_log=lambda m: None, auto=False)
    svc3.set_source_end(time.perf_counter())
    svc3._handle_event({'kind': 'played', 'id': 1})
    check(g, 'played 事件 ⇒ _last_out_t 被更新', svc3._last_out_t is not None,
          '实际 = %r' % svc3._last_out_t)
    check(g, 'played 后 end_lag_s 有值',
          svc3.end_lag_s is not None,
          '实际 = %r' % svc3.end_lag_s)


# ══════════════════════════════════════════════════════════════════
# C4 —— close() 作废计数 + close 后最终统计
# ══════════════════════════════════════════════════════════════════
def group_c4(ns_s, ns_app):
    g = 'C4'
    S = ns_s['TTSService']
    svc = S(device='GPU.0', on_log=lambda m: None, auto=False)

    # ── C4-a：3 句在途 ⇒ close() 后 n_discard_on_close = 3 ──
    for i in range(3):
        svc.pending[i] = dict(seg=i, text='x%d' % i, t=0.0)
        svc._inflight.add(i)
    svc.n_submitted = 3
    svc.close()
    check(g, 'n_discard_on_close = 3（close 主动作废的句子）',
          svc.n_discard_on_close == 3,
          '实际 = %r' % svc.n_discard_on_close)
    check(g, 'n_dropped 也 +3（**同时**计丢句，账本仍自洽）',
          svc.n_dropped == 3, '实际 = %r' % svc.n_dropped)
    check(g, '不变式 n_played+n_dropped+n_empty == n_submitted 仍成立',
          svc.n_played + svc.n_dropped + svc.n_empty == svc.n_submitted,
          '%d + %d + %d == %d' % (svc.n_played, svc.n_dropped, svc.n_empty,
                                 svc.n_submitted))
    st = svc.stats()
    check(g, 'stats() 含 n_discard_on_close',
          'n_discard_on_close' in st, '实际 = %r' % st.get('n_discard_on_close'))
    check(g, 'stats() 含 end_lag_s', 'end_lag_s' in st,
          '实际 = %r' % st.get('end_lag_s'))
    check(g, 'stats() 含 n_empty', 'n_empty' in st,
          '实际 = %r' % st.get('n_empty'))

    # ── C4-b：CLI 必须 **close 后**再打印一次最终统计 ──
    src_app = open(APP_PATH, 'r', encoding='utf-8').read()
    i_close = src_app.find('tts.close()')
    i_final = src_app.find('最终统计（close 后）')
    check(g, 'CLI 有「最终统计（close 后）」行', i_final >= 0,
          '位置 = %d' % i_final)
    check(g, '**最终统计行在 close() 之后**',
          i_final >= 0 and i_close >= 0 and i_final > i_close,
          'close()=%d  最终统计=%d' % (i_close, i_final))
    check(g, '最终统计行含 n_discard_on_close',
          'n_discard_on_close' in src_app[max(0, i_final - 800):i_final + 800],
          '在最终统计行附近 800 字符内')
    check(g, '最终统计行含 end_lag_s',
          'end_lag_s' in src_app[max(0, i_final - 800):i_final + 800],
          '在最终统计行附近 800 字符内')

    # ── C4-c：drain 超时 = max(120, 1.5×当前积压) ──
    check(g, 'drain 超时用 max(120, 1.5×积压)',
          'max(120.0, 1.5 * _bl)' in src_app,
          '源码含 `max(120.0, 1.5 * _bl)`')

    # ── C4-d：CLI 必须打「源结束」的点（否则 end_lag_s 恒 None）──
    check(g, 'CLI 调 set_source_end',
          'tts.set_source_end(' in src_app,
          '源码含 `tts.set_source_end(`')
    check(g, 'Session 记 source_end_t',
          'self.source_end_t' in src_app,
          '源码含 `self.source_end_t`')


# ══════════════════════════════════════════════════════════════════
# 反证组
# ══════════════════════════════════════════════════════════════════
def group_x(ns_w, src_w, ns_s, src_s, src_app):
    g = 'X'

    # ① C1：把 `t_recv` 恒置空（还原老口径 ⇒ 排队恒 0）
    broken = src_w.replace(
        "        _t_recv = self._recv_at.pop(jid, None) if t_recv is None else t_recv",
        "        _t_recv = None  # <<反证注入>> 还原老口径", 1)
    check(g, '① C1 反证：注入点命中', broken != src_w,
          '替换 t_recv 赋值行')
    if broken != src_w:
        ns_b = load_ns_src(broken, 'app134_x_worker', WORKER_PATH)
        import tempfile as _tf
        td = _tf.mkdtemp(prefix='app134_x1_')
        jsonl = os.path.join(td, 'x.tts.jsonl')
        w = object.__new__(ns_b['TTSWorker'])
        for k, v in (('_dequeue_at', {}), ('_recv_at', {}), ('_enqueue_at', {}),
                     ('_last_lang', None), ('_last_lang_src', None),
                     ('_last_end_reason', None), ('_last_lead_punct', ''),
                     ('_last_lead_punct_n', 0), ('_last_clone_active', False),
                     ('_last_clone_mode', None), ('_last_clone_audio_s', 0.0),
                     ('_last_spk', None), ('_last_spk_conf', None),
                     ('_last_est_frames', None), ('_last_max_new_tokens', None),
                     ('player', None), ('out_wav', None), ('dump_dir', None),
                     ('sr', 24000), ('voice', 'A'), ('conds', {}),
                     ('engine', None), ('ov_rt', None), ('_clone_active', False),
                     ('_clone_mode', None), ('_clone_audio_s', 0.0),
                     ('_jsonl_rows', []), ('_jsonl_path', jsonl),
                     ('_timeline', []), ('_t0', None)):
            setattr(w, k, v)
        w._stop = type('S', (), {'is_set': staticmethod(lambda: False)})()
        w._synth_lock = threading.Lock()
        w._is_cancelled = lambda jid: False
        ns_b['emit'] = lambda o: None
        ns_b['log'] = lambda m: None
        t_recv = time.perf_counter()
        time.sleep(1.0)
        w._recv_at[5] = t_recv
        w._enqueue_at[5] = time.perf_counter()
        w._dequeue_at[5] = time.perf_counter()
        w.synth(5, '，', None, None, 'zh', t_recv)
        rows = []
        with open(jsonl, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        r = rows[0] if rows else {}
        check(g, '① C1 反证：排队量不到 ⇒ C1 判据必 FAIL',
              r.get('worker_fifo_wait_total_s') is None,
              '注入后 worker_fifo_wait_total_s = %r（应为 None ⇒ 判 FAIL）'
              % r.get('worker_fifo_wait_total_s'))

    # ② C2：把采样间隔改成 10 s（点数不够 ⇒ C2 判据必 FAIL）
    broken2 = src_s.replace(
        "        self._curve_interval_s = 1.5",
        "        self._curve_interval_s = 10.0  # <<反证注入>>", 1)
    check(g, '② C2 反证：注入点命中', broken2 != src_s,
          '替换 _curve_interval_s = 1.5')
    if broken2 != src_s:
        ns_b2 = load_ns_src(broken2, 'app134_x_service', SERVICE_PATH)
        s2 = ns_b2['TTSService'](device='GPU.0', on_log=lambda m: None,
                                 auto=False)
        check(g, '② C2 反证：默认间隔越界 ⇒ C2 判据必 FAIL',
              not (1.0 <= s2._curve_interval_s <= 2.0),
              '注入后 _curve_interval_s = %r' % s2._curve_interval_s)

    # ③ C3：把 `_recompute_end_lag` 改成取绝对值（负数变正 ⇒ 判据必 FAIL）
    broken3 = src_s.replace(
        "            self.end_lag_s = round(self._last_out_t - self._source_end_t, 3)",
        "            self.end_lag_s = round(abs(self._last_out_t - self._source_end_t), 3)  # <<反证注入>>",
        1)
    check(g, '③ C3 反证：注入点命中', broken3 != src_s,
          '替换 end_lag_s 计算')
    if broken3 != src_s:
        ns_b3 = load_ns_src(broken3, 'app134_x_service3', SERVICE_PATH)
        s3 = ns_b3['TTSService'](device='GPU.0', on_log=lambda m: None,
                                 auto=False)
        s3._last_out_t = time.perf_counter()
        s3.set_source_end(time.perf_counter() + 1.0)
        check(g, '③ C3 反证：负值被吞 ⇒ C3 判据必 FAIL',
              not (s3.end_lag_s is not None and s3.end_lag_s < 0),
              '注入后 end_lag_s = %r（应为正 ⇒ 判 FAIL）' % s3.end_lag_s)

    # ④ C4：把 `n_discard_on_close` 的累加删掉（判据必 FAIL）
    broken4 = src_s.replace(
        "            self.n_discard_on_close += len(orphan)",
        "            pass  # <<反证注入>> 不记关闭作废", 1)
    check(g, '④ C4 反证：注入点命中', broken4 != src_s,
          '替换 n_discard_on_close 累加')
    if broken4 != src_s:
        ns_b4 = load_ns_src(broken4, 'app134_x_service4', SERVICE_PATH)
        s4 = ns_b4['TTSService'](device='GPU.0', on_log=lambda m: None,
                                 auto=False)
        for i in range(3):
            s4.pending[i] = dict(seg=i, text='x', t=0.0)
            s4._inflight.add(i)
        s4.n_submitted = 3
        s4.close()
        check(g, '④ C4 反证：不记作废 ⇒ C4 判据必 FAIL',
              s4.n_discard_on_close != 3,
              '注入后 n_discard_on_close = %r（应为 0 ⇒ 判 FAIL）'
              % s4.n_discard_on_close)


def main():
    print('=' * 78)
    print('app134 —— APP-036 C1–C4：遥测口径修正（零推理、零硬件）')
    print('=' * 78)
    print('解释器 = %s' % sys.executable)

    ns_w, src_w = load_ns(WORKER_PATH, 'app134_worker')
    ns_s, src_s = load_ns(SERVICE_PATH, 'app134_service')
    src_app = open(APP_PATH, 'r', encoding='utf-8').read()

    tmpd = tempfile.mkdtemp(prefix='app134_')
    try:
        group_c1(ns_w, tmpd)
        group_c2(ns_s, tmpd)
        group_c3(ns_s)
        group_c4(ns_s, src_app)
        group_x(ns_w, src_w, ns_s, src_s, src_app)
    except Exception:
        traceback.print_exc()
        EVID['fatal'] = traceback.format_exc()
        _dump()
        return 1

    _dump()
    return 0


def _dump():
    tot = len(EVID['checks'])
    ok = sum(1 for c in EVID['checks'] if c['pass'])
    EVID['summary'] = {'total': tot, 'pass': ok, 'fail': tot - ok}
    with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(EVID, f, ensure_ascii=False, indent=2)
    print('-' * 78)
    print('合计 %d 项：PASS %d / FAIL %d' % (tot, ok, tot - ok))
    print('证据 = %s' % EVID_PATH)


if __name__ == '__main__':
    sys.exit(main())
