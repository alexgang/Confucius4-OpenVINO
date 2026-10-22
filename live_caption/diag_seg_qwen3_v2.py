r"""diag_seg_qwen3_v2.py — Qwen3 方案 v2：加入「切段后跳过尾静音」（speech_start 语义）

v1 仿真（diag_seg_qwen3.py）发现的两个现象
----------------------------------------
**现象 1：纯 VAD 模式（关掉 12s 计时器兜底）反而更慢。**
  61 分钟真实演讲：纯 VAD-800ms 共 198 段，其中 **159 段是 20s 硬切**，
  段长中位 20.5s，比现状（12.2s）还长。
  根因（diag_seg_qwen3_why.py 逐 chunk 追踪）：
    未切段的原因分布里 **5504/5508 次是 `no_trailing_silence`** ——
    即「根本没有 ≥800ms 的尾静音」，不是被保护期/准入门槛拦住的。
    素材是**连续演讲**：≥800ms 的停顿 61 分钟只有 113 处（1.9 处/分钟）。
    → 说话人几乎不停顿，VAD 没有可切的点，只能等 20s 硬切。
    → **照搬 Qwen3 的纯 VAD 模式在我们这类素材上是负收益。**

**现象 2： hangover 降到 400ms 后空段从 1 个涨到 11 个。**
  根因：切完一刀后，下一段仍从同一片静音的**中间**开始累积，
  于是又立刻检出「尾静音」→ 切出一个纯静音段。
  例：[41.60, 42.88] 长 1.28s，语音帧占比 **0.0%**，max 帧电平 −36.3dB。

**→ Qwen3 服务端 VAD 是怎么解决现象 2 的？**
  服务端 VAD 有 `speech_start` / `speech_stop` **两个**事件：
  语音起点**之前**的静音被服务端直接丢弃，不参与该 turn 的编码。
  我们的架构缺少这一步 —— 上一段的尾静音会漏进下一段。

v2 的改动
---------
新增一个语义：**切段后，下一段从「语音真正开始处」起算**（跳过尾静音），
即模拟 Qwen3 服务端 VAD 的 `speech_start` 处理。

同时对比「保留 12s 计时器兜底」与「纯 VAD」，给出可落地的组合。

用法：
  python diag_seg_qwen3_v2.py <wav> [--minutes 61]
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
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True
    return float(frame_db(seg).max()) < -40.0


def speech_ratio(d, t0, t1, thr_db=-35.0):
    s = int(t0 * SR)
    e = int(t1 * SR)
    seg = d[s:e]
    if seg.size == 0:
        return 0.0
    f = frame_db(seg)
    return float(np.mean(f > thr_db)) if f.size else 0.0


def next_speech(d, t, thr_db=-40.0):
    """从 t 起找第一处「语音」帧的起点（跳过尾静音）。

    这是 Qwen3 服务端 VAD 的 `speech_start` 语义：
    语音起点之前的静音直接丢弃，不参与该 turn 的编码。
    找不到就返回 None（后面全是静音）。
    """
    s = int(t * SR)
    if s >= len(d):
        return None
    # 粗查：从 s 起最多找 5 秒
    seg = d[s:s + SR * 5]
    if seg.size == 0:
        return None
    f = frame_db(seg)
    if f.size == 0:
        return None
    hit = np.where(f > thr_db)[0]
    if hit.size == 0:
        return None
    # 回退到第一个语音帧，再往前留 60ms 余量（避免切掉爆破音头）
    idx = max(0, int(hit[0]) - 6)
    return (s + idx * 160) / SR


def simulate(d, cfg, L):
    """按配置仿真切段（支持跳过尾静音）。

    cfg = dict(silence_cut, min_seg, max_seg, rule1, skip_tail)
    """
    from seg_stream import find_silence_in_range, find_trailing_silence

    sc = cfg['silence_cut']
    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    base = 0.0          # 当前段起点的**绝对**秒
    cursor = 0          # 已喂入音频的绝对采样下标
    pending_skip = None  # 已算出但尚未应用的「跳过尾静音」起点（秒）

    def guard_pass(acc, sil_start):
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
        # 规则2：静音超时
        r2 = False
        sil_abs = None
        if n >= int(SR * 0.5):
            win = int(SR * (sc + L.SILENCE_TAIL_GUARD_SEC + 0.5))
            span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                         end_sample=n, silence_db=L.SILENCE_DB,
                                         min_silence_ms=int(sc * 1000))
            if span is not None and guard_pass(accum, span[0]):
                r2 = True
                sil_abs = base + span[0] / SR
        if r2:
            cut_t = base + dur
            cuts.append((cut_t, dur, 'rule2'))
            base = cut_t
            if cfg['skip_tail']:
                ns = next_speech(d, cut_t)
                if ns is not None and ns > base:
                    base = ns          # 跳过尾静音（speech_start 语义）
            accum = np.zeros(0, dtype=np.float32)
            continue
        if dur >= cfg['max_seg']:
            cuts.append((base + dur, dur, 'max'))
            base += dur
            if cfg['skip_tail']:
                ns = next_speech(d, base)
                if ns is not None and ns > base:
                    base = ns
            accum = np.zeros(0, dtype=np.float32)
            continue
        if cfg['rule1'] and dur >= cfg['min_seg']:
            start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
            c = find_silence_in_range(accum, start_sample=start, end_sample=n,
                                      silence_db=L.SILENCE_DB, min_silence_ms=300)
            if c is not None:
                cut_t = base + dur
                cuts.append((cut_t, dur, 'rule1'))
                base = cut_t
                if cfg['skip_tail']:
                    ns = next_speech(d, cut_t)
                    if ns is not None and ns > base:
                        base = ns
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
    grid = np.arange(0, total_sec, step)
    ends = np.array([c[0] for c in cuts]) if cuts else np.array([total_sec])
    idx = np.clip(np.searchsorted(ends, grid, side='left'), 0, len(ends) - 1)
    return grid, ends[idx]


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
        dict(key='A 现状基线', silence_cut=1.2, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=False),
        dict(key='B 1.2→0.8s', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=False),
        dict(key='B+ 跳过尾静音', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='B+ +0.6s', silence_cut=0.6, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='B+ +0.4s', silence_cut=0.4, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='纯VAD0.8', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=False, skip_tail=True),
        dict(key='纯VAD0.4', silence_cut=0.4, min_seg=12.0, max_seg=20.0,
             rule1=False, skip_tail=True),
        dict(key='B+ +min6s', silence_cut=0.8, min_seg=6.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='B+ +min4s', silence_cut=0.8, min_seg=4.0, max_seg=20.0,
             rule1=True, skip_tail=True),
    ]

    print('=' * 108)
    print(f'Qwen3 方案 v2（含 speech_start 跳过尾静音）  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 108)
    print(f'{"配置":<18} {"段数":>5} {"rule2":>6} {"rule1":>6} {"max":>4} '
          f'{"安全率":>7} {"空段":>5} {"短段<2s":>8} {"中位段长":>9} '
          f'{"提前中位":>9} {"提前最大":>9} {"末段":>8} {"收尾开销":>9}')

    results = []
    base_f = None
    for cfg in configs:
        cuts = simulate(d, cfg, L)
        c = Counter(x[2] for x in cuts)
        n = len(cuts)
        durs = np.array([x[1] for x in cuts])
        safe = sum(1 for x in cuts if safe_at(d, x[0]))
        prev = 0.0
        empties = 0
        for x in cuts:
            if speech_ratio(d, prev, x[0]) < 0.10:
                empties += 1
            prev = x[0]
        grid, f = frontier(cuts, total)
        if base_f is None:
            base_f = f
        adv = base_f - f
        pos = adv[adv > 0]
        adv_med = float(np.median(pos)) if pos.size else 0.0
        adv_max = float(pos.max()) if pos.size else 0.0
        last = cuts[-1][0] if cuts else 0.0
        results.append(dict(cfg=cfg, cuts=cuts, n=n, cnt=dict(c), safe=safe,
                            n_empty=empties, adv_med=adv_med, adv_max=adv_max,
                            last=last, durs=durs.tolist()))
        print(f'{cfg["key"]:<18} {n:>5} {c.get("rule2",0):>6} {c.get("rule1",0):>6} '
              f'{c.get("max",0):>4} {100*safe/max(1,n):>6.1f}% {empties:>5} '
              f'{int((durs<2).sum()):>8} {np.median(durs):>8.1f}s '
              f'{adv_med:>8.2f}s {adv_max:>8.1f}s {last:>7.1f}s '
              f'{n*FINALIZE_MS/1000:>8.1f}s')

    print()
    print('=' * 108)
    print('【切点质量对比】规则2 的切点里有多少落在词间隙（安全）')
    print('=' * 108)
    for r in results:
        r2 = [x for x in r['cuts'] if x[2] == 'rule2']
        if not r2:
            print(f'   {r["cfg"]["key"]:<18} 规则2 0 段')
            continue
        ns = sum(1 for x in r2 if safe_at(d, x[0]))
        print(f'   {r["cfg"]["key"]:<18} 规则2 {len(r2):>4} 段，'
              f'安全 {ns:>4} ({100*ns/len(r2):>5.1f}%)，危险 {len(r2)-ns:>3}')

    print()
    print('=' * 108)
    print('【段长分位】')
    print('=' * 108)
    for r in results:
        ds = np.array(r['durs'])
        q = [np.percentile(ds, p) for p in (5, 25, 50, 75, 95)]
        print(f'   {r["cfg"]["key"]:<18} p5={q[0]:>6.2f} p25={q[1]:>6.2f} '
              f'p50={q[2]:>6.2f} p75={q[3]:>6.2f} p95={q[4]:>6.2f}  '
              f'max={ds.max():>6.2f}s')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'diag_seg_qwen3_v2_result.json')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump([dict(key=r['cfg']['key'], cfg=r['cfg'], n=r['n'], cnt=r['cnt'],
                        safe=r['safe'], n_empty=r['n_empty'],
                        adv_med=r['adv_med'], adv_max=r['adv_max'], last=r['last'],
                        durs=r['durs'],
                        cuts=[[round(x[0], 3), round(x[1], 3), x[2]] for x in r['cuts']])
                   for r in results], fp, ensure_ascii=False, indent=1)
    print(f'\n→ {out}')


if __name__ == '__main__':
    main()
