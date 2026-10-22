r"""diag_seg_qwen3.py — 按 Qwen3-ASR-Flash-Realtime 的 turn_detection 方案仿真切段

背景
----
`Qwen3-ASR-Flash-Realtime` 的官方切句语义（`session.turn_detection`）：

======================  ====================  ==========================
Qwen3 参数              官方取值              本项目对应量
======================  ====================  ==========================
`silence_duration_ms`  默认 800，范围[200,6000]  `SILENCE_CUT_SEC`
`threshold`            默认 0.5，范围[-1,1]    `SILENCE_DB`（能量dB，量纲不同）
`type`                 server_vad / semantic_vad  能量 VAD（无 semantic 能力）
`turn_detection=null`  Manual 模式，客户端 commit  （可选开关）
======================  ====================  ==========================

Qwen3 语义与本项目现状的**结构性**差异：

1. **没有最短段门槛**。Qwen3 完全靠 VAD（hangover）决定何时切，
   不存在「等满 N 秒」的计时器兜底。而本项目 `MIN_SEG_SEC=12s` 的
   规则1 正是这种计时器兜底，实测 94.2% 的段由它切出。
2. **规则1 的落点是段尾**（chunk 边界），不是静音中点 →
   89.2% 的切点切在词中间。
3. 行业最长单段 30–60s（模型上下文上限决定），本项目 `MAX_SEG_SEC=20s`。

所以「按 Qwen3 方案改」在本项目里等价于：
  * `SILENCE_CUT_SEC`：1.2s → **0.8s**（Qwen3 默认）/ 0.4s（Qwen3 推荐快速断句）
  * **关掉规则1 的 12s 计时器兜底**（改为纯 VAD 驱动）
  * `MAX_SEG_SEC`：评估是否放宽到 30s

本脚本做多配置离线仿真，指标：
  * 段数、规则分布（rule1/rule2/max）
  * 切点安全率（切点前 0.5s 是否安静 → 是否切碎词）
  * 空段率（段内语音帧占比极低的段 → C-106 那类「切出纯静音」）
  * 段长分布、末段定稿时刻
  * **白字提前量**：定稿前沿 F(t) 的提前量（中位/最大/累计）
  * **finalize 开销**：段数 × 单次收尾解码成本（段数变多会多花收尾时间）

用法：
  python diag_seg_qwen3.py <wav> [--minutes 61]
"""

from __future__ import annotations

import os
import sys
import json
import importlib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
CHUNK_SEC = 0.64
# 单次 finalize（收尾解码）实测成本：编码 68ms + prefill 108ms + 解码 252ms
FINALIZE_MS = 428.0


def frame_db(x, frame_ms=30, hop_ms=10):
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if x.size < n:
        x = np.concatenate([x, np.zeros(n - x.size, dtype=x.dtype)])
    nf = (x.size - n) // h + 1
    sq = x.astype(np.float64) ** 2
    cs = np.concatenate(([0.0], np.cumsum(sq)))
    out = np.empty(nf)
    for i in range(nf):
        s = i * h
        out[i] = 20.0 * np.log10(np.sqrt((cs[s + n] - cs[s]) / n + 1e-12) + 1e-7)
    return out


def safe_at(d, t, win_ms=500):
    """切点前 win_ms 是否安静（安静 = 没切碎词）。"""
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True
    return float(frame_db(seg).max()) < -40.0


def speech_ratio(d, t0, t1, thr_db=-35.0):
    """段内「语音帧」占比（帧 RMS > thr_db）。用于识别空段。"""
    s = int(t0 * SR)
    e = int(t1 * SR)
    seg = d[s:e]
    if seg.size == 0:
        return 0.0
    f = frame_db(seg)
    if f.size == 0:
        return 0.0
    return float(np.mean(f > thr_db))


def simulate(d, cfg, L):
    """按配置仿真切段。

    cfg = dict(silence_cut, min_seg, max_seg, rule1)
      silence_cut : rule2 的 hangover（秒）
      min_seg     : rule1 的最短段门槛（秒）；rule1=False 时忽略
      max_seg     : 硬切上限（秒）
      rule1       : 是否启用「计时器兜底」规则1

    位置记账（严格）：
      base   = 当前段起点的**绝对**采样下标
      cursor = 已喂入音频的绝对采样下标
      切点绝对位置 = base + len(accum)/SR
    """
    from seg_stream import find_silence_in_range, find_trailing_silence

    sc = cfg['silence_cut']
    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    base = 0
    cursor = 0

    def guard_pass(acc, sil_start):
        """保护期判据（C-105/C-106：绝对 ∪ 相对）。"""
        n = acc.shape[0]
        g = int(SR * L.SILENCE_TAIL_GUARD_SEC)
        ps = max(0, sil_start - g)
        if ps >= sil_start:
            return False
        probe = acc[ps:sil_start]
        if probe.size == 0:
            return False
        rms = float(np.sqrt(np.mean(probe.astype(np.float64) ** 2) + 1e-12))
        db = 20.0 * float(np.log10(rms + 1e-7))
        if db > L.SILENCE_DB:
            return True
        if not L.GUARD_REL_ENABLED:
            return False
        seg_db = L._frame_db_series(acc[:sil_start])
        if seg_db.size == 0:
            return False
        speech = float(np.percentile(seg_db, 90))
        if speech < L.GUARD_REL_MIN_SPEECH_DB:
            return False
        return db > speech - L.GUARD_REL_DROP_DB

    while True:
        n = accum.shape[0]
        dur = n / SR
        # 规则2：静音超时（Qwen3 的 hangover 语义）
        r2 = False
        if n >= int(SR * 0.5):
            win = int(SR * (sc + L.SILENCE_TAIL_GUARD_SEC + 0.5))
            span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                         end_sample=n, silence_db=L.SILENCE_DB,
                                         min_silence_ms=int(sc * 1000))
            if span is not None and guard_pass(accum, span[0]):
                r2 = True
        if r2:
            cuts.append((base / SR + dur, dur, 'rule2'))
            base += n
            accum = np.zeros(0, dtype=np.float32)
            continue
        if dur >= cfg['max_seg']:
            cuts.append((base / SR + dur, dur, 'max'))
            base += n
            accum = np.zeros(0, dtype=np.float32)
            continue
        if cfg['rule1'] and dur >= cfg['min_seg']:
            start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
            c = find_silence_in_range(accum, start_sample=start, end_sample=n,
                                      silence_db=L.SILENCE_DB, min_silence_ms=300)
            if c is not None:
                cuts.append((base / SR + dur, dur, 'rule1'))
                base += n
                accum = np.zeros(0, dtype=np.float32)
                continue
        if cursor >= len(d):
            break
        chunk = d[cursor:cursor + chunk_n]
        cursor += chunk_n
        if chunk.size == 0:
            break
        accum = np.concatenate([accum, chunk]) if accum.size else chunk.copy()
    return cuts


def frontier(cuts, total_sec, step=0.5):
    """定稿前沿 F(t)：时间 t 之前的内容在什么时候定稿。

    F(t) = 包含 t 的那一段的切点时刻（该段结束时才定稿）。
    返回 (t_grid, F_array)。
    """
    grid = np.arange(0, total_sec, step)
    f = np.full(grid.shape, total_sec)
    # 每段的 (起, 止) 区间 → 切点时刻
    starts = np.concatenate([[0.0], [c[0] for c in cuts[:-1]]])
    ends = np.array([c[0] for c in cuts])
    idx = np.searchsorted(ends, grid, side='left')
    idx = np.clip(idx, 0, len(ends) - 1)
    f = ends[idx]
    return grid, f


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 61.0
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(minutes * 60 * sr)]
    total = len(d) / SR

    os.environ['LIVECAP_GUARD_REL'] = '1'
    import live_caption_app as L
    importlib.reload(L)

    configs = [
        dict(key='A 现状基线', silence_cut=1.2, min_seg=12.0, max_seg=20.0, rule1=True),
        dict(key='B 仅降hangover', silence_cut=0.8, min_seg=12.0, max_seg=20.0, rule1=True),
        dict(key='C 纯VAD-800ms', silence_cut=0.8, min_seg=12.0, max_seg=20.0, rule1=False),
        dict(key='D 纯VAD-400ms', silence_cut=0.4, min_seg=12.0, max_seg=20.0, rule1=False),
        dict(key='E 纯VAD-600ms', silence_cut=0.6, min_seg=12.0, max_seg=20.0, rule1=False),
        dict(key='F 纯VAD-800/30s', silence_cut=0.8, min_seg=12.0, max_seg=30.0, rule1=False),
        dict(key='G 纯VAD-400/30s', silence_cut=0.4, min_seg=12.0, max_seg=30.0, rule1=False),
        dict(key='H VAD800+min2s', silence_cut=0.8, min_seg=2.0, max_seg=20.0, rule1=True),
        dict(key='I VAD400+min2s', silence_cut=0.4, min_seg=2.0, max_seg=20.0, rule1=True),
    ]

    print('=' * 100)
    print(f'Qwen3 turn_detection 方案离线仿真  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 100)

    results = []
    base_frontier = None
    for cfg in configs:
        cuts = simulate(d, cfg, L)
        c = Counter(x[2] for x in cuts)
        n = len(cuts)
        durs = [x[1] for x in cuts]
        safe = sum(1 for x in cuts if safe_at(d, x[0]))
        # 空段：段内语音帧占比 < 10%
        empties = []
        prev_end = 0.0
        for x in cuts:
            r = speech_ratio(d, prev_end, x[0])
            if r < 0.10:
                empties.append((prev_end, x[0] - prev_end, r))
            prev_end = x[0]
        grid, f = frontier(cuts, total)
        if base_frontier is None:
            base_frontier = f
        advance = base_frontier - f
        adv_pos = advance[advance > 0]
        results.append(dict(cfg=cfg, cuts=cuts, n=n, cnt=dict(c), safe=safe,
                            durs=durs, empties=empties, frontier=f,
                            adv_med=float(np.median(adv_pos)) if adv_pos.size else 0.0,
                            adv_max=float(adv_pos.max()) if adv_pos.size else 0.0,
                            adv_sum=float(adv_pos.sum() * 0.5) if adv_pos.size else 0.0,
                            last=cuts[-1][0] if cuts else 0.0))
        r = results[-1]
        print(f'{r["cfg"]["key"]:<18} 段数={n:>4} rule2={c.get("rule2",0):>4} '
              f'rule1={c.get("rule1",0):>4} max={c.get("max",0):>3} '
              f'安全率={100*safe/max(1,n):>5.1f}% 空段={len(empties):>3} '
              f'段长中位={np.median(durs):>5.1f}s 提前中位={r["adv_med"]:>5.2f}s '
              f'提前最大={r["adv_max"]:>5.1f}s 累计={r["adv_sum"]:>6.1f}s '
              f'末段={r["last"]:>6.1f}s '
              f'finalize={n*FINALIZE_MS/1000:>5.1f}s')

    print()
    print('=' * 100)
    print('【配置明细】')
    print('=' * 100)
    for r in results:
        cfg = r['cfg']
        print(f'\n▶ {cfg["key"]}  (hangover={cfg["silence_cut"]}s, '
              f'min_seg={cfg["min_seg"]}s, max_seg={cfg["max_seg"]}s, '
              f'rule1={"on" if cfg["rule1"] else "off"})')
        print(f'   段数 {r["n"]}   规则分布 {r["cnt"]}   '
              f'切点安全 {r["safe"]}/{r["n"]} ({100*r["safe"]/max(1,r["n"]):.1f}%)')
        ds = np.array(r['durs'])
        for q in (5, 25, 50, 75, 95):
            print(f'   段长 p{q:<2} = {np.percentile(ds, q):>6.2f}s', end='')
        print()
        print(f'   短段(<2s) {int((ds < 2).sum())} 段   '
              f'<1s {int((ds < 1).sum())} 段   '
              f'>25s {int((ds > 25).sum())} 段')
        if r['empties']:
            print(f'   空段明细（前 5）: {r["empties"][:5]}')
        else:
            print('   空段: 无')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'diag_seg_qwen3_result.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump([dict(key=r['cfg']['key'], cfg=r['cfg'], n=r['n'], cnt=r['cnt'],
                        safe=r['safe'], n_empty=len(r['empties']),
                        durs=r['durs'], last=r['last'],
                        adv_med=r['adv_med'], adv_max=r['adv_max'],
                        adv_sum=r['adv_sum'],
                        cuts=[[round(x[0], 3), round(x[1], 3), x[2]] for x in r['cuts']])
                   for r in results], f, ensure_ascii=False, indent=1)
    print(f'\n→ {out}')


if __name__ == '__main__':
    main()
