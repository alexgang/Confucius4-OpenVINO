#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app101_app027_v1v2_metrics.py —— APP-027 的 V1/V2 验收：**离线指标计算器**

🔴🔴 **本脚本不跑推理、不占 GPU、不取机器锁** ⇒ **可以在锁被占用时安全运行**。
   它只做一件事：**从 `x.tts.jsonl` + 会话日志里算出 APP-027 明文要求的指标**，
   并按明文判据给出 PASS / FAIL。

⇒ 拿到锁后：`app102_app027_v1v2_run.py` 负责**跑**，
   本脚本负责**算**（两者分离 ⇒ 判据可以独立回归、可反证）。

## 指标（APP-027 明文）

### V1（CUDA 连续实时）
- 逐句：`queued_s` / `synth_first_s` / `synth_rtf` / `prebuffer_s` /
  `underflow_in_sentence`（次数/毫秒）
- 丢句分两类：**未合成就丢** vs **已写入被丢** ⇒ **后者必须为 0**
- 「没有产出音频」次数 ⇒ **必须为 0**
- 看门狗触发次数 ⇒ **必须为 0**（或写明原因）
- 积压随时间曲线（每 5 s 一点）⇒ csv
- **5 分钟全程不能出现超过 30 s 没有合成的空窗**

### V2（NPU 连续实时）
- 同素材同条件 + **四种配置 ABBA**
  （TTS 单独 / +ASR(GPU.0) / +ASR+MT(NPU) / +ASR+MT(GPU.0)）
- 每种报 `synth_rtf` 的 **P50 / P95**
- 验收：**句内 `underflow_in_sentence` P95 = 0**（只允许句前等待）
- 丢句率与 RTF 一起报告
- **RTF > 1 导致的丢句只记录不判失败，但必须如实写**

## 用法

```
python app101_app027_v1v2_metrics.py --jsonl <x.tts.jsonl> \
        [--session-log <session_*.log>] [--label V1-CUDA] \
        [--out-dir results/app/v1v2]
```

⚠️ **不 import 被测模块**（项目铁律）⇒ 只读 jsonl / log 文本。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import sys

# ══════════════════════════════════════════════════════════════════
# 判据常量（reviewer 明文）
# ══════════════════════════════════════════════════════════════════
MAX_SILENCE_GAP_S = 30.0      # 「不能出现超过 30 s 没有合成的空窗」
BACKLOG_SAMPLE_S = 5.0        # 积压曲线每 5 s 一点
UNDERFLOW_P95_MAX = 0         # 「句内 underflow_in_sentence P95 = 0」

# 「已写入被丢」必须为 0
_DROPPED_AFTER_WRITE_RE = re.compile(
    r'音频未被播放完|播放缓冲写满|播放写入失败|wait_consumed', re.I)
# 「没有产出音频」必须为 0
_NO_AUDIO_RE = re.compile(r'没有产出任何音频|引擎没有产出', re.I)
# 看门狗触发（必须为 0 或写明原因）
_WATCHDOG_RE = re.compile(r'看门狗触发|WATCHDOG restart', re.I)


def pct(vals, q):
    """百分位（**线性插值**，与 numpy 默认一致）。"""
    if not vals:
        return None
    vs = sorted(vals)
    if len(vs) == 1:
        return float(vs[0])
    pos = (len(vs) - 1) * (q / 100.0)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(vs[lo])
    return float(vs[lo] + (vs[hi] - vs[lo]) * (pos - lo))


def load_jsonl(path):
    rows = []
    with open(path, 'r', encoding='utf-8') as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    return rows


def classify_drop(row):
    """把一行分成三类之一。

    ⇒ **「已写入被丢」必须为 0**（APP-027 明文）：
      已写进环形缓冲的句子**一律不丢**（只丢**还没开始合成的整句**）。
    """
    if not row.get('dropped'):
        return None
    err = row.get('error') or ''
    if _DROPPED_AFTER_WRITE_RE.search(err):
        return 'dropped_after_write'
    return 'dropped_before_synth'


def analyze_jsonl(path):
    rows = load_jsonl(path)
    out = {
        'n_rows': len(rows),
        'n_dropped_before_synth': 0,
        'n_dropped_after_write': 0,
        'n_no_audio': 0,
        'n_failed': 0,
        'rtf': [],
        'prebuffer_s': [],
        'underflow_in_sentence': [],
        'underflow_in_sentence_ms': [],
        'underflow_pre_sentence': [],
        'queued_s': [],
        'synth_first_s': [],
        'dur_s': [],
        'idle_gaps': [],
        'max_idle_gap_s': 0.0,
        'n_prebuffer_short': 0,
        # 🔴🔴🔴 APP-028②：队列水位 / 峰值 / 结尾滞后
        'queue_lag_s': [],
        'queue_peak_s': [],
        'queue_peak_mb': [],
        'final_lag_s': None,
    }
    for r in rows:
        if r.get('dropped'):
            k = classify_drop(r)
            if k == 'dropped_after_write':
                out['n_dropped_after_write'] += 1
            else:
                out['n_dropped_before_synth'] += 1
        err = r.get('error') or ''
        if _NO_AUDIO_RE.search(err):
            out['n_no_audio'] += 1
        elif err:
            out['n_failed'] += 1

        v = r.get('synth_rtf')
        if isinstance(v, (int, float)):
            out['rtf'].append(float(v))
        v = r.get('prebuffer_s')
        if isinstance(v, (int, float)):
            out['prebuffer_s'].append(float(v))
        if r.get('prebuffer_short'):
            out['n_prebuffer_short'] += 1
        v = r.get('underflow_in_sentence')
        if isinstance(v, (int, float)):
            out['underflow_in_sentence'].append(int(v))
        v = r.get('underflow_in_sentence_ms')
        if isinstance(v, (int, float)):
            out['underflow_in_sentence_ms'].append(float(v))
        v = r.get('underflow_pre_sentence')
        if isinstance(v, (int, float)):
            out['underflow_pre_sentence'].append(int(v))
        v = r.get('t_first_packet')
        if isinstance(v, (int, float)):
            out['synth_first_s'].append(float(v))
        v = r.get('dur_s')
        if isinstance(v, (int, float)):
            out['dur_s'].append(float(v))
        # 🔴🔴🔴 APP-028②：队列水位 / 峰值
        v = r.get('queue_lag_s')
        if isinstance(v, (int, float)):
            out['queue_lag_s'].append(float(v))
        v = r.get('queue_peak_s')
        if isinstance(v, (int, float)):
            out['queue_peak_s'].append(float(v))
        v = r.get('queue_peak_mb')
        if isinstance(v, (int, float)):
            out['queue_peak_mb'].append(float(v))

    # 🔴 「没有合成的空窗」：按 `t_submit` 排序 ⇒ 相邻两句的间隔
    ts = sorted(float(r['t_submit']) for r in rows
                 if isinstance(r.get('t_submit'), (int, float)))
    for i in range(1, len(ts)):
        gap = ts[i] - ts[i - 1]
        out['idle_gaps'].append(gap)
        if gap > out['max_idle_gap_s']:
            out['max_idle_gap_s'] = gap
    # 🔴🔴🔴 APP-028②：**结尾时的滞后**（最后一句写入完成时的队列水位）。
    #   ⇒ 按 `t_submit` 取**最后一行**（最接近会话末尾）的 `queue_lag_s`。
    _lag_rows = [r for r in sorted(
        (r for r in rows if isinstance(r.get('t_submit'), (int, float))),
        key=lambda r: float(r['t_submit']))
        if isinstance(r.get('queue_lag_s'), (int, float))]
    if _lag_rows:
        out['final_lag_s'] = float(_lag_rows[-1]['queue_lag_s'])
    return out


def analyze_session_log(path):
    """从会话日志里数**看门狗触发次数**与**丢弃原因分类**。"""
    if not path or not os.path.isfile(path):
        return {'n_watchdog': None, 'n_log_lines': 0,
                'note': '会话日志未提供 ⇒ 看门狗次数无法核对'}
    n_wd = 0
    n_lines = 0
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for ln in f:
            n_lines += 1
            if _WATCHDOG_RE.search(ln):
                n_wd += 1
    return {'n_watchdog': n_wd, 'n_log_lines': n_lines}


def write_backlog_csv(rows, path, every_s=BACKLOG_SAMPLE_S):
    """🔴 积压随时间曲线（每 5 s 一点）⇒ csv。

    ⚠️ **口径**：主进程的积压 = 环形缓冲剩余 + 正在合成剩余 + 排队估时
       ⇒ worker 的 jsonl **没有**这个总量 ⇒ 这里用**代理量**：
       「已提交但还没播完的句子数 × 该句 dur」的滚动和。
       ⇒ 列名里标 `proxy_backlog_s`（**不是**主进程口径，别混用）。
    """
    rs = [r for r in rows if isinstance(r.get('t_submit'), (int, float))]
    rs.sort(key=lambda r: r['t_submit'])
    if not rs:
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write('t_rel_s,proxy_backlog_s,n_pending\n')
        return 0
    t0 = float(rs[0]['t_submit'])
    # 每句的「结束时刻」= t_submit + dur + 首包
    ends = []
    for r in rs:
        d = float(r.get('dur_s') or 0.0)
        fp = float(r.get('t_first_packet') or 0.0)
        ends.append((float(r['t_submit']) + fp + d, d))
    n = 0
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t_rel_s', 'proxy_backlog_s', 'n_pending'])
        t = t0
        last = float(rs[-1]['t_submit']) + 5.0
        while t <= last:
            pend = [(e, d) for (e, d) in ends if e > t]
            bl = sum(d for _e, d in pend)
            w.writerow([round(t - t0, 2), round(bl, 3), len(pend)])
            t += every_s
            n += 1
    return n


def verdict(a, log_a, label):
    """按 APP-027 明文给判据。返回 (checks, overall)。"""
    checks = []

    def ck(name, ok, detail):
        # 🔴🔴 **三态**（本脚本自测 B7 抓出来的缺陷）：
        #   旧写法 `bool(ok)` 会把 **`None`（= 未能核对 / 没证据）变成 False**
        #   ⇒ 「缺会话日志」被当成「有缺陷」⇒ **误判 FAIL**
        #   ⇒ 「**没证据**比「结论错」更严重」⇒ 必须能表达「没证据」这一态。
        #   ⇒ True = 通过 / False = 失败 / None = **没证据**（不算通过，也不算失败）
        if ok is None:
            v = None
        else:
            v = bool(ok)
        checks.append({'name': name, 'pass': v, 'detail': detail})

    # ① 已写入被丢 = 0（硬性）
    ck('已写入被丢的句子数 = 0',
       a['n_dropped_after_write'] == 0,
       '实际 %d' % a['n_dropped_after_write'])
    # ② 没有产出音频 = 0（硬性）
    ck('「没有产出音频」次数 = 0',
       a['n_no_audio'] == 0,
       '实际 %d' % a['n_no_audio'])
    # ③ 看门狗触发 = 0
    nwd = log_a.get('n_watchdog')
    if nwd is None:
        ck('看门狗触发次数 = 0', None, '⚠️ 无会话日志 ⇒ 未能核对')
    else:
        ck('看门狗触发次数 = 0', nwd == 0, '实际 %d' % nwd)    # ④ 合成空窗 ≤ 30 s
    ck('合成空窗 ≤ %.0f s' % MAX_SILENCE_GAP_S,
       a['max_idle_gap_s'] <= MAX_SILENCE_GAP_S,
       '最大间隔 %.1f s' % a['max_idle_gap_s'])
    # ⑤ 句内 underflow P95 = 0
    p95 = pct(a['underflow_in_sentence'], 95)
    ck('句内 underflow_in_sentence P95 = 0',
       (p95 is not None and p95 <= UNDERFLOW_P95_MAX),
       'P95 = %s（样本 %d）'
       % ('—' if p95 is None else p95, len(a['underflow_in_sentence'])))
    # ⑥ 句前等待是**允许**的（只记录）
    pre = a['underflow_pre_sentence']
    ck('句前空等已单列（只记录，不判失败）', True,
       '句前空等次数 P50=%s P95=%s'
       % (pct(pre, 50), pct(pre, 95)))

    # ── 🔴🔴🔴 APP-028② 新增判据 ──────────────────────────────────
    # ⑦ **丢句数必须为 0**（APP-028 验收明文：「丢句数必须为 0」）
    #    ⚠️ 口径：jsonl 里的 `dropped` 行 = 「这一句被放弃」。
    #    APP-028② 取消了**积压丢句** ⇒ 正常会话应当**一句都不丢**。
    n_drop_total = (a['n_dropped_before_synth'] + a['n_dropped_after_write'])
    ck('APP-028② 丢句数 = 0（取消积压丢句）',
       n_drop_total == 0,
       '实际 %d（未合成 %d / 已写入 %d）'
       % (n_drop_total, a['n_dropped_before_synth'],
          a['n_dropped_after_write']))

    # ⑧ **队列峰值（秒）**（APP-028 验收明文要报）
    #    ⚠️ **只记录，不判失败**（峰值大不代表有缺陷；RTF>1 时会自然累积）
    pk_s = a['queue_peak_s']
    ck('APP-028② 队列峰值（秒）已记录', True,
       'peak_s=%s（句内水位 P50=%s / P95=%s / max=%s）'
       % (max(pk_s) if pk_s else None, pct(a['queue_lag_s'], 50),
          pct(a['queue_lag_s'], 95),
          max(a['queue_lag_s']) if a['queue_lag_s'] else None))

    # ⑨ **队列峰值（MB）**（APP-028 验收明文要报）
    pk_mb = a['queue_peak_mb']
    ck('APP-028② 队列峰值（MB）已记录', True,
       'peak_mb=%s' % (max(pk_mb) if pk_mb else None))

    # ⑩ **结尾时的滞后**（APP-028 验收明文要报）
    #    ⚠️ **只记录**（滞后大 ≠ 缺陷；RTF>1 时必然累积）
    ck('APP-028② 结尾时的语音滞后已记录', True,
       'final_lag_s=%s' % a['final_lag_s'])

    # overall：**硬性判据**（①②③④⑤）全过才算过
    #   🔴🔴 **判据自身的缺陷（本脚本自测 B7 抓出来的）**：
    #     旧写法 `all(c['pass'] for c in hard)` 会把 **`None`（= 未能核对）
    #     当成 False** ⇒ 「缺会话日志」被判成 FAIL
    #     ⇒ 而「**没证据**比「结论错」更严重」⇒ 正确做法是：
    #        - `False` ⇒ 判 FAIL
    #        - `None` ⇒ **不算通过，但也不算失败** ⇒ 必须在输出里显式标注
    #          ⇒ 并且**整体不算 PASS**（不能在没有证据时宣称通过）
    #   ⇒ 因此：overall = 「没有 False」且「没有 None」
    #     （None 会被单独报出来，提示需要补日志）
    soft = {'句前空等已单列（只记录，不判失败）'}
    hard = [c for c in checks if c['name'] not in soft]
    has_false = any(c['pass'] is False for c in hard)
    has_none = any(c['pass'] is None for c in hard)
    overall = (not has_false) and (not has_none)
    return checks, overall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jsonl', required=True)
    ap.add_argument('--session-log', default=None)
    ap.add_argument('--label', default='V1-CUDA')
    ap.add_argument('--out-dir', default=None)
    args = ap.parse_args()

    if not os.path.isfile(args.jsonl):
        print('!! jsonl 不存在：%s' % args.jsonl)
        sys.exit(2)

    rows = load_jsonl(args.jsonl)
    a = analyze_jsonl(args.jsonl)
    log_a = analyze_session_log(args.session_log)
    checks, overall = verdict(a, log_a, args.label)

    print('=' * 66)
    print('%s  ←  %s' % (args.label, args.jsonl))
    print('=' * 66)
    print('句子行数            : %d' % a['n_rows'])
    print('未合成就丢          : %d' % a['n_dropped_before_synth'])
    print('已写入被丢（须=0）  : %d' % a['n_dropped_after_write'])
    print('没有产出音频（须=0）: %d' % a['n_no_audio'])
    print('其它失败            : %d' % a['n_failed'])
    print('预缓冲不足的句子    : %d' % a['n_prebuffer_short'])
    rtf = a['rtf']
    print('synth_rtf           : P50=%.3f P95=%.3f max=%.3f (n=%d)'
          % (pct(rtf, 50) or -1, pct(rtf, 95) or -1,
             max(rtf) if rtf else -1, len(rtf)))
    print('prebuffer_s         : P50=%.3f P95=%.3f'
          % (pct(a['prebuffer_s'], 50) or -1,
             pct(a['prebuffer_s'], 95) or -1))
    uf = a['underflow_in_sentence']
    print('句内 underflow      : P50=%s P95=%s max=%s (n=%d)'
          % (pct(uf, 50), pct(uf, 95), max(uf) if uf else '-', len(uf)))
    up = a['underflow_pre_sentence']
    print('句前空等（单列）    : P50=%s P95=%s'
          % (pct(up, 50), pct(up, 95)))
    print('最大合成空窗        : %.1f s（上限 %.0f s）'
          % (a['max_idle_gap_s'], MAX_SILENCE_GAP_S))
    print('看门狗触发          : %s' % log_a.get('n_watchdog'))
    # 🔴🔴🔴 APP-028②：队列水位 / 峰值 / 结尾滞后
    pk_s = a['queue_peak_s']
    pk_mb = a['queue_peak_mb']
    print('队列水位 queue_lag_s: P50=%s P95=%s max=%s (n=%d)'
          % (pct(a['queue_lag_s'], 50), pct(a['queue_lag_s'], 95),
             max(a['queue_lag_s']) if a['queue_lag_s'] else None,
             len(a['queue_lag_s'])))
    print('队列峰值（秒）      : %s' % (max(pk_s) if pk_s else None))
    print('队列峰值（MB）      : %s' % (max(pk_mb) if pk_mb else None))
    print('结尾时语音滞后（秒）: %s' % a['final_lag_s'])
    print('-' * 66)
    for c in checks:
        if c['pass'] is True:
            mark = 'PASS'
        elif c['pass'] is False:
            mark = 'FAIL'
        else:
            mark = 'NO-EVIDENCE'
        print('  [%s] %s  —  %s' % (mark, c['name'], c['detail']))
    print('-' * 66)
    has_false = any(c['pass'] is False for c in checks)
    has_none = any(c['pass'] is None for c in checks)
    if has_false:
        print('总体：FAIL')
    elif has_none:
        print('总体：INCOMPLETE（有判据缺证据 ⇒ 不能宣称通过）')
    else:
        print('总体：PASS')

    out_dir = args.out_dir
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        summary = {
            'label': args.label, 'jsonl': args.jsonl,
            'session_log': args.session_log,
            'metrics': {k: v for k, v in a.items() if k != 'idle_gaps'},
            'log': log_a, 'checks': checks, 'overall': 'PASS' if overall else 'FAIL',
        }
        sp = os.path.join(out_dir, '%s_summary.json' % args.label)
        with open(sp, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        cp = os.path.join(out_dir, '%s_backlog.csv' % args.label)
        n = write_backlog_csv(rows, cp)
        print('已写 %s' % sp)
        print('已写 %s（%d 行积压曲线）' % (cp, n))

    sys.exit(0 if overall else 1)


if __name__ == '__main__':
    main()
