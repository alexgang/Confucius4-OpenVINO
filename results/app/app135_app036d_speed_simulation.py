# -*- coding: utf-8 -*-
"""app135 —— APP-036 D：**离线**模拟「播放 1.1×/1.2×/1.3× 时的滞后曲线」。

## reviewer APP-036 D 原文

> D. 不要自己做（等用户决定，reviewer 已上报）：追赶策略，例如滞后超过 X s 时
>    把播放速度提高到 1.15–1.25×、TTS 语速参数、MT 简洁模式。用户已决定不丢句，
>    **不得恢复任何丢句或跳句的做法**。
>    可以先做的零风险准备：用现有 soak 的 jsonl **离线模拟**「播放 1.1×/1.2×/1.3×
>    时的滞后曲线」，**只给数字，不改产品**。

## 🔴 本脚本**只给数字**

- **零推理、零 GPU、零 NPU、零声卡**；
- **不改任何产品代码**（只读 jsonl，只写自己的 csv/json）；
- **不碰追赶策略**（不设阈值、不改播放速度、不改 MT、不恢复任何丢句做法）。

## 模型（写清楚，供 reviewer 复核）

### 三条轴

| 轴 | 来源 | 用途 |
|---|---|---|
| **内容轴** `c_i` | `t_submit[i]` 线性重映射到 `[0, 300 s]` | 第 i 句对应的**原声位置**（reviewer 口径：原声 300 s） |
| **产出时刻** `p_i` | `c_i + D + synth_i` | 第 i 句音频**全部可播**的时刻（`synth_i` = jsonl 的 `t_last_chunk − t_submit`；`D` = 起步延迟常量，默认 0） |
| **长度轴** `dur_i` | jsonl `dur_s` | 第 i 句音频时长 |

### 滞后定义（= APP-028 的 `lag_s` 口径）

    A_prod(t) = Σ dur_i   （条件：p_i ≤ t）      ← 已合成完、待播的音频
    A_cons(t) = v × max(0, t − t_start)          ← 已播掉的音频（速率 v，受 A_prod 限制）
    lag(t)    = A_prod(t) − A_cons(t)            ← **队列里还没播的音频时长（秒）**

### 交叉校验（reviewer 的简单速率模型）

    R = 中文音频总时长 / 原声时长 = 338.8 / 300 = 1.1293
    ⇒ 播放速度 ≤ R ⇒ 滞后以 (R − v) 的斜率单调累积
    ⇒ v=1.0 时 lag(300s) ≈ (R − 1) × 300 = **38.8 s**
       （reviewer 原文「5 分钟下来至少 35–40 s」⇒ 同量级 ✓）

## 用法

    <py> results/app/app135_app036d_speed_simulation.py
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

SOAK_DIR = os.environ.get('APP135_SOAK_DIR') or r'C:\Users\Trekker-PTL\app028_soak'
JSONL = os.path.join(SOAK_DIR, 'app028_soak.wav.tts.jsonl')
SPE_SECONDS = 300.0          # SPE 前 5 分钟 = 原声 300 s（reviewer 口径）

EVID_PATH = os.environ.get('APP135_EVID') or os.path.join(
    HERE, 'app135_app036d_speed_simulation_evidence.json')
CSV_PATH = os.path.join(HERE, 'app135_app036d_lag_curves.csv')

SPEEDS = (1.0, 1.1, 1.2, 1.3)
SAMPLE_DT = 0.5              # 曲线采样步长（秒）
START_DELAY_S = 0.0         # D：起步延迟常量（reviewer 的「约 11 s 含 TTS 加载」是额外偏移，不影响斜率）


def load_segments():
    rows = []
    with open(JSONL, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    rows.sort(key=lambda r: r.get('id', 0))
    segs = []
    for r in rows:
        t_submit = r.get('t_submit')
        t_ready = r.get('t_last_chunk')
        if t_ready is None:
            t_ready = r.get('t_done')
        dur = float(r.get('dur_s') or 0.0)
        if t_submit is None or t_ready is None or dur <= 0:
            continue
        segs.append({
            'id': r.get('id'),
            't_submit': float(t_submit),
            't_ready': float(t_ready),
            'synth_s': float(t_ready) - float(t_submit),
            'dur_s': dur,
            'n_chars': r.get('n_chars') or 0,
            'synth_rtf': r.get('synth_rtf'),
        })
    return segs


def build_timeline(segs):
    """内容轴重映射到 [0, SPE_SECONDS]；产出时刻 = c_i + D + synth_i。"""
    t0 = segs[0]['t_submit']
    tN = segs[-1]['t_submit']
    span = max(tN - t0, 1e-9)
    for sg in segs:
        sg['c_s'] = (sg['t_submit'] - t0) / span * SPE_SECONDS
        sg['p_s'] = sg['c_s'] + START_DELAY_S + sg['synth_s']
    segs.sort(key=lambda s: s['p_s'])
    return segs


def simulate(segs, v):
    """按播放速度 v 模拟滞后曲线。"""
    total_audio = sum(sg['dur_s'] for sg in segs)
    # 产出事件：(可播时刻, 该句时长)
    events = [(sg['p_s'], sg['dur_s']) for sg in segs]
    events.sort()
    t_start = events[0][0] if events else 0.0

    pts = []
    p = 0.0            # 已播音频（秒）
    produced = 0.0     # 已产出音频（秒）
    ev_i = 0
    n_stall = 0
    t = 0.0
    while t <= SPE_SECONDS + 1e-9:
        while ev_i < len(events) and events[ev_i][0] <= t:
            produced += events[ev_i][1]
            ev_i += 1
        # 消费：速率 v，但不超过已产出
        want = v * SAMPLE_DT
        can = max(0.0, produced - p)
        got = min(want, can)
        if got < want - 1e-9:
            n_stall += 1
        p += got
        lag = produced - p
        pts.append((round(t, 2), round(produced, 3), round(p, 3),
                    round(lag, 3)))
        t += SAMPLE_DT

    def at(sec):
        i = min(int(sec / SAMPLE_DT), len(pts) - 1)
        return pts[i][3]

    return pts, {
        'end_lag_s': pts[-1][3],
        'max_lag_s': max(x[3] for x in pts),
        'lag_at_60s': at(60), 'lag_at_120s': at(120),
        'lag_at_180s': at(180), 'lag_at_240s': at(240),
        'lag_at_300s': at(300),
        'n_stall_steps': n_stall,
        'audio_played_s': round(p, 3),
        't_start_s': round(t_start, 3),
    }


def main():
    if not os.path.exists(JSONL):
        print('❌ 找不到 soak jsonl：%s' % JSONL)
        return 2

    segs = load_segments()
    if not segs:
        print('❌ jsonl 无可用句子')
        return 2
    segs = build_timeline(segs)

    total_audio = sum(sg['dur_s'] for sg in segs)
    R = total_audio / SPE_SECONDS          # 中文音频 / 原声（reviewer 口径）
    synth_total = sum(sg['synth_s'] for sg in segs)

    results = {}
    for v in SPEEDS:
        pts, summ = simulate(segs, v)
        results[v] = {'points': pts, 'summary': summ}

    # ── csv ──
    with open(CSV_PATH, 'w', encoding='utf-8', newline='\n') as f:
        cols = ['t_s', 'produced_s', 'audio_played_s'] + \
               ['lag_v%.1f' % v for v in SPEEDS]
        f.write(','.join(cols) + '\n')
        n = len(results[SPEEDS[0]]['points'])
        for i in range(n):
            base = results[SPEEDS[0]]['points'][i]
            row = [base[0], base[1], base[2]]
            for v in SPEEDS:
                pts = results[v]['points']
                row.append(pts[i][3] if i < len(pts) else '')
            f.write(','.join(str(x) for x in row) + '\n')

    out = {
        'source_jsonl': JSONL,
        'n_segments': len(segs),
        'total_audio_s': round(total_audio, 3),
        'spe_seconds': SPE_SECONDS,
        'start_delay_s': START_DELAY_S,
        'ratio_audio_per_source_speech_R': round(R, 4),
        'cross_check_reviewer_rate_model': {
            'formula': 'lag(t) ≈ (R − v)·t',
            'R': round(R, 4),
            'at_300s_v1.0': round((R - 1.0) * 300, 2),
            'note': ('reviewer 原文「5 分钟下来至少 35–40 s」'
                     '⇒ 与 (R−1)×300 = %.1f s 同量级' % ((R - 1.0) * 300)),
        },
        'speeds': {},
        'csv': CSV_PATH,
        'model_note': ('内容轴 = t_submit 线性重映射到 [0,300s]；'
                       '产出时刻 = 内容时刻 + 合成耗时；'
                       'lag(t) = 已产出音频 − 已播音频（= APP-028 的 lag_s 口径）；'
                       '播放速率 = v，受「已产出」限制 ⇒ 欠载会停顿'),
        'synth_total_s': round(synth_total, 3),
    }
    for v in SPEEDS:
        out['speeds']['%.1f' % v] = results[v]['summary']

    with open(EVID_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('=' * 92)
    print('app135 —— APP-036 D：离线模拟播放速度对滞后曲线的影响（**只给数字**）')
    print('=' * 92)
    print('语料 = %s（%d 句）' % (JSONL, len(segs)))
    print('中文音频总时长 = %.1f s ｜ 原声 = %.1f s' % (total_audio, SPE_SECONDS))
    print('**比值 R = %.4f（中文比原声长 %.1f%%）**' % (R, (R - 1) * 100))
    print('reviewer 速率模型交叉校验：lag(300s, v=1.0) ≈ (R−1)×300 = **%.1f s**'
          % ((R - 1) * 300))
    print()
    print('%-7s %9s %9s %9s %9s %11s %11s %9s'
          % ('速度', 'lag@60s', 'lag@120s', 'lag@180s', 'lag@240s',
             'lag@300s', 'max_lag_s', '欠载步'))
    for v in SPEEDS:
        s = results[v]['summary']
        print('%-7s %9.1f %9.1f %9.1f %9.1f %11.1f %11.1f %9d'
              % ('%.1fx' % v, s['lag_at_60s'], s['lag_at_120s'],
                 s['lag_at_180s'], s['lag_at_240s'], s['lag_at_300s'],
                 s['max_lag_s'], s['n_stall_steps']))
    print()
    print('曲线 csv = %s' % CSV_PATH)
    print('证据     = %s' % EVID_PATH)
    print()
    print('⚠️ **只给数字**：不改产品、不设阈值、不碰追赶策略（reviewer D 明文）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
