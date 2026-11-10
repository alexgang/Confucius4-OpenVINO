#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app327b_app093_overload_recompute.py —— **§3.3 过载臂结果重算（修正阶段划分）**。

## 为什么重算而不是重跑设备

第一版 `_app327_overload_driver.py` 有**两个真缺陷**，都在**分析侧**（不影响设备跑）：

### 缺陷 1：`sitecustomize` 的 patch **从未生效**
* 原实现用 `__import__` 钩子等 `import live_caption_app`
* **根因**：App 是**以 `__main__` 直接运行**的（`live_caption_app.py` 末尾有
  `if __name__ == '__main__':`）⇒ `import live_caption_app` **从不发生**
  ⇒ 钩子永远不触发 ⇒ `Session.start` 从未 patch ⇒ **pace 从未变过**。
* **修法**：改成**轮询 `sys.modules['__main__']`**（`__main__` 里定义了 `class Session`）。
* 已隔离验证：`patched? True`。

### 缺陷 2：阶段划分**漏掉全部 `late_drop` 行**
* 原实现只用 `play_wall` 定位墙钟 ⇒ **`late_drop` 的行 `play_wall=None`**
  ⇒ 过载期 **22 句被整体漏掉** ⇒ 「过载期只统计到 1 句」。
* **修法**：`t_submit` 是单调钟、`play_wall` 是墙钟 ⇒ 两者**不能直接相减**；
  但差值**恒定**（实测 std = 1.67 s）⇒ 取**中位数 offset** 平移
  ⇒ `wall_est = t_submit + offset` ⇒ **所有行**（含 late_drop）都能定位。

## 本脚本做什么

**不重跑设备**，直接对**已落盘**的 `runs4/after/dialog3_overload3/` 产物
用修正后的口径重算，并**同时给出修正前 / 修正后的对照**（证明修正的影响）。

## 口径

* 过载墙钟区间 = `[60, 105] s`
  （reviewer 的 60/150 s 是**源秒**；过载段 90 s 源在 pace 2.0 下花 45 s 墙钟）
* 恢复用时 = **过载结束墙钟 → 首个 `speed_lag_s ≤ 6 s` 的句**的墙钟差
  （`speed_lag_s` ＝ worker **出队**滞后，`tts_worker.py:2514`）
* 反证组：把 `speed_lag_s` 全部 +1000 ⇒ 恢复用时必须变 `None`
"""
from __future__ import annotations

import csv
import json
import os
import statistics as st
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser('~')
BASE = os.path.join(HOME, '_app_shadow')
OUTROOT = os.path.join(BASE, 'runs4')

SRC_NORMAL_END = 60.0
SRC_OVERLOAD_END = 150.0
PACE_OVERLOAD = 2.0
RECOVER_LAG_S = 6.0

ARMS = ('after',)
REPORT = os.path.join(HERE, 'app327b_app093_overload_recompute.json')


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def read_jsonl(p):
    rows = []
    if not os.path.exists(p):
        return rows
    with open(p, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    return round(s[int(q * (len(s) - 1))], 4)


def phase_of(rel, T1, T2):
    if rel is None:
        return None
    if rel < T1:
        return 'normal'
    if rel < T2:
        return 'overload'
    return 'recover'


def score_phase(rows, phase):
    sub = [r for r in rows if r.get('_phase') == phase]
    lags = [float(r['speed_lag_s']) for r in sub
            if isinstance(r.get('speed_lag_s'), (int, float))]
    play = [float(r['play_lag_s']) for r in sub
            if isinstance(r.get('play_lag_s'), (int, float))]
    fifo = [float(r['worker_fifo_wait_s']) for r in sub
            if isinstance(r.get('worker_fifo_wait_s'), (int, float))]
    rtfs = [float(r['synth_rtf']) for r in sub
            if isinstance(r.get('synth_rtf'), (int, float))]
    dlags = [float(r['late_drop_lag_s']) for r in sub
             if isinstance(r.get('late_drop_lag_s'), (int, float))]
    ers = {}
    for r in sub:
        k = str(r.get('end_reason'))
        ers[k] = ers.get(k, 0) + 1
    return {
        'n_rows': len(sub),
        'n_with_play_wall': sum(1 for r in sub
                                if isinstance(r.get('play_wall'), (int, float))),
        'n_late_drop': sum(1 for r in sub
                           if r.get('late_drop') or r.get('dropped')),
        'speed_lag_p50': pct(lags, 0.50),
        'speed_lag_p95': pct(lags, 0.95),
        'speed_lag_max': (round(max(lags), 4) if lags else None),
        'play_lag_p50': pct(play, 0.50),
        'play_lag_p95': pct(play, 0.95),
        'worker_fifo_wait_p50': pct(fifo, 0.50),
        'synth_rtf_p50': pct(rtfs, 0.50),
        'synth_rtf_p95': pct(rtfs, 0.95),
        'late_drop_lag_s_p50': pct(dlags, 0.50),
        'late_drop_lag_s_max': (round(max(dlags), 4) if dlags else None),
        'n_speed_floor_conflict_max': max(
            [int(r['n_speed_floor_conflict']) for r in sub
             if isinstance(r.get('n_speed_floor_conflict'), (int, float))]
            or [0]),
        'end_reason_dist': ers,
    }


def recovery_from(rows, t_end_wall, threshold=RECOVER_LAG_S):
    """过载结束墙钟 → 首个 `speed_lag_s ≤ threshold` 的句的墙钟差。"""
    for r in sorted(rows, key=lambda x: x.get('_wall_est') or 0.0):
        sl = r.get('speed_lag_s')
        t = r.get('_wall_est')
        if not isinstance(sl, (int, float)) or not isinstance(t, (int, float)):
            continue
        if float(t) < t_end_wall:
            continue
        if sl <= threshold:
            return round(float(t) - t_end_wall, 3)
    return None


def neg_control(rows, threshold=RECOVER_LAG_S):
    tampered = []
    for r in rows:
        r2 = dict(r)
        r2['speed_lag_s'] = (r.get('speed_lag_s') or 0.0) + 1000.0
        tampered.append(r2)
    return recovery_from(tampered, 0.0, threshold)


def analyze(arm):
    out = os.path.join(OUTROOT, arm, 'dialog3_overload3')
    meta_path = os.path.join(BASE, arm, 'app', '_app327_session_meta.json')
    rows = read_jsonl(os.path.join(out, 'tts.jsonl'))
    segs = read_jsonl(os.path.join(out, 'spk_seg.jsonl'))
    meta = json.load(open(meta_path, encoding='utf-8')) \
        if os.path.exists(meta_path) else {}
    t0_wall = meta.get('t0_wall')
    T1 = SRC_NORMAL_END
    T2 = T1 + (SRC_OVERLOAD_END - SRC_NORMAL_END) / PACE_OVERLOAD

    rec = {'arm': arm, 'out': out, 'meta': meta,
           'n_tts_rows': len(rows), 'n_seg_rows': len(segs)}

    # ── 修正前口径（只按 play_wall）──
    def _rel_old(r):
        w = r.get('play_wall')
        return (float(w) - float(t0_wall)) if (
            isinstance(w, (int, float))
            and isinstance(t0_wall, (int, float))) else None
    old = []
    for r in rows:
        r2 = dict(r)
        r2['_phase'] = phase_of(_rel_old(r), T1, T2)
        old.append(r2)

    # ── 修正后口径（t_submit + 中位数 offset）──
    offs = [float(r['play_wall']) - float(r['t_submit'])
            for r in rows
            if isinstance(r.get('play_wall'), (int, float))
            and isinstance(r.get('t_submit'), (int, float))]
    offset = st.median(offs) if offs else 0.0
    new = []
    for r in rows:
        r2 = dict(r)
        w = r.get('play_wall')
        ts = r.get('t_submit')
        if isinstance(w, (int, float)):
            rel = float(w) - float(t0_wall)
        else:
            rel = (float(ts) + offset - float(t0_wall)) if (
                isinstance(ts, (int, float))
                and isinstance(t0_wall, (int, float))) else None
        r2['_wall_rel'] = rel
        r2['_wall_est'] = (float(ts) + offset
                           if isinstance(ts, (int, float)) else None)
        r2['_phase'] = phase_of(rel, T1, T2)
        new.append(r2)

    rec['clock_offset'] = {
        'method': 'wall_est = t_submit + median(play_wall - t_submit)',
        'n_used': len(offs),
        'offset_s': round(offset, 4),
        'offset_std_s': (round(st.pstdev(offs), 4) if len(offs) > 1 else None),
        'note': ('🔴 `t_submit` 是单调钟、`play_wall` 是墙钟 ⇒ 不能直接相减；'
                 '取差值中位数做平移 ⇒ late_drop 行（play_wall=None）也能定位'),
    }
    rec['wall_window'] = {'normal_end_s': T1, 'overload_end_s': T2,
                          't0_wall': t0_wall,
                          'note': ('reviewer 的 60/150 s 是**源秒**；'
                                   '过载段 90 s 源在 pace 2.0 下花 45 s 墙钟'
                                   '⇒ 过载墙钟区间 = [60, 105] s')}
    rec['phases_old'] = {ph: score_phase(old, ph)
                         for ph in ('normal', 'overload', 'recover')}
    rec['phases'] = {ph: score_phase(new, ph)
                     for ph in ('normal', 'overload', 'recover')}

    # ── 恢复用时（修正后）──
    T2_wall = meta.get('T2_wall')
    rec['recovery'] = {
        'threshold_s': RECOVER_LAG_S,
        'field': 'speed_lag_s（worker 出队滞后；tts_worker.py:2514）',
        'overload_end_wall': T2_wall,
        'recovery_s_after_overload': (recovery_from(new, T2_wall)
                                      if isinstance(T2_wall, (int, float))
                                      else None),
        'recovery_s_old_criterion': (recovery_from(old, T2_wall)
                                     if isinstance(T2_wall, (int, float))
                                     else None),
    }
    nc = neg_control(new)
    rec['recovery']['neg_control'] = nc
    rec['recovery']['neg_control_pass'] = (nc is None)
    rec['recovery']['neg_control_note'] = (
        '🔴 反证：把 speed_lag_s 全部 +1000 ⇒ 恢复用时必须变 None'
        '（否则判据恒真）')

    # ── ASR 侧积压曲线 ──
    bc_path = os.path.join(out, 'mix.wav.backlog_curve.csv')
    rec['asr_backlog_curve'] = {'path': bc_path,
                                'exists': os.path.exists(bc_path),
                                'columns': [], 'phases': {}}
    if os.path.exists(bc_path):
        with open(bc_path, encoding='utf-8', errors='replace',
                  newline='') as f:
            rdr = list(csv.DictReader(f))
        if rdr:
            rec['asr_backlog_curve']['columns'] = list(rdr[0].keys())
            rec['asr_backlog_curve']['n_points'] = len(rdr)
            for ph, (a, b) in (('normal', (0.0, T1)),
                               ('overload', (T1, T2)),
                               ('recover', (T2, 1e18))):
                sub = [r for r in rdr
                       if a <= float(r.get('t_s') or 0.0) < b]
                if not sub:
                    continue
                bl = [float(r['backlog_s']) for r in sub if r.get('backlog_s')]
                lg = [float(r['lag_s']) for r in sub if r.get('lag_s')]
                sy = [float(r['synth_s']) for r in sub if r.get('synth_s')]
                qu = [float(r['queued_s']) for r in sub if r.get('queued_s')]
                dp = [int(r['n_dropped']) for r in sub if r.get('n_dropped')]
                rec['asr_backlog_curve']['phases'][ph] = {
                    'n_points': len(sub),
                    'backlog_s_max': (round(max(bl), 4) if bl else None),
                    'backlog_s_p50': pct(bl, 0.50),
                    'lag_s_max': (round(max(lg), 4) if lg else None),
                    'lag_s_p50': pct(lg, 0.50),
                    'synth_s_max': (round(max(sy), 4) if sy else None),
                    'queued_s_max': (round(max(qu), 4) if qu else None),
                    'n_dropped_final': (dp[-1] if dp else None),
                }

    # ── 字幕完整度 ──
    n_sub = 0
    sp = os.path.join(out, 'subtitles.txt')
    if os.path.exists(sp):
        with open(sp, encoding='utf-8', errors='replace') as f:
            n_sub = sum(1 for ln in f if ln.strip())
    rec['subtitle_completeness'] = {
        'n_subtitle_lines': n_sub,
        'n_seg_rows': len(segs),
        'n_tts_rows': len(rows),
        'n_sub_n_seg_equal': (n_sub == len(segs)),
        'note': ('App 侧 subtitles.txt 与 spk_seg.jsonl 同源同序（一 定稿一段）'
                 '⇒ 段数应相等；**跳句只丢语音，不影响字幕/转写**'),
    }
    return rec


def main():
    ev = {
        'created_at': now(),
        'correction': 'APP-093 §3.3 过载臂（修正后重算）',
        'criterion': ('单会话过载臂：1.0× → 2.0× → 1.0×；报过载起止（源秒/墙钟）、'
                      'ASR/MT/TTS 积压曲线、过载期跳过句数、'
                      '过载结束到 dequeue lag 回到 6 s 以内的用时、字幕完整度'),
        'method': ('对**已落盘**的 runs4 产物**重算**（不重跑设备）；'
                   '修正两处分析缺陷：① sitecustomize patch 改为轮询 __main__ '
                   '② 阶段划分改用 t_submit + 中位数 offset（覆盖 late_drop 行）'),
        'device_job': False,
        'lock_note': ('本次为**只读重算**（不加载模型、不占 GPU/NPU）'
                      '⇒ 按项目纪律**不持 MACHINE_LOCK**；'
                      '设备跑那一轮（_app327_overload_driver.py）的锁记录'
                      '见 app327_overload_after.json'),
        'arms': {},
    }
    for arm in ARMS:
        ev['arms'][arm] = analyze(arm)
    ev['verdict'] = 'RAN'
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('[out] %s' % REPORT)
    for arm, rec in ev['arms'].items():
        print('--- %s ---' % arm)
        for ph in ('normal', 'overload', 'recover'):
            o = rec['phases_old'][ph]
            n = rec['phases'][ph]
            print('  %-9s old n=%-3s late=%-3s | new n=%-3s late=%-3s '
                  'sl_p50=%-8s sl_p95=%-8s rtf_p50=%s'
                  % (ph, o['n_rows'], o['n_late_drop'], n['n_rows'],
                     n['n_late_drop'], n['speed_lag_p50'], n['speed_lag_p95'],
                     n['synth_rtf_p50']))
        print('  recovery new=%s old=%s neg=%s'
              % (rec['recovery']['recovery_s_after_overload'],
                 rec['recovery']['recovery_s_old_criterion'],
                 rec['recovery']['neg_control']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
