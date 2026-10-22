r"""diag_seg_qwen3_v3.py — Qwen3 方案 v3：修正 skip_tail 记账 + 连续语音检测

v2 的 bug
---------
v2 里 `skip_tail` 只改写了 `base`（段起点的绝对秒），但没同步 `cursor`
（已喂入音频的绝对采样下标）→ 段起点与实际音频内容错位，
「切点安全率」从 19.9% 骤降到 5.2%（假象）。
正确做法：**同时丢弃**前导静音的整块 chunk（chunk 边界与段起点天然对齐），
使 base 与 cursor 同步 —— 这也正是真实系统里 reset 后能做的事。

v3 新增：连续语音检测
----------------------
v1/v2 的 `next_speech` 用「单帧 > -40dB」找语音起点，但素材里有
**噪声突发**（9 帧连续 −36dB），会被误判成语音起点 → skip_tail 失效。
v3 改成：**连续 N 帧（≥120ms）** 都超过阈值才算语音起点。

本脚本回答三个问题
------------------
Q1：修正记账后，`skip_tail`（Qwen3 服务端 VAD 的 speech_start 语义）
    到底带来什么？切点质量、空段、段长、白字提前量。
Q2：`hangover` 取多少最优？（Qwen3 默认 800 / 推荐 400 / 我们已验证安全区间）
Q3：空段的真正判别特征是什么？如何在不误伤的前提下消掉它？

用法：
  python diag_seg_qwen3_v3.py <wav> [--minutes 61]
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


def find_speech_start(d, t, thr_db=-40.0, min_run_ms=120, max_look=6.0):
    """从绝对时刻 t 起找「连续语音」的起点（Qwen3 的 speech_start 语义）。

    要求连续 min_run_ms 的帧都超过 thr_db —— 避免把噪声突发当成语音。
    返回绝对秒，或 None。
    """
    s = int(t * SR)
    if s >= len(d):
        return None
    seg = d[s:s + int(max_look * SR)]
    if seg.size == 0:
        return None
    f = frame_db(seg)
    if f.size == 0:
        return None
    hot = f > thr_db
    need = max(1, int(min_run_ms / 10))
    run = 0
    for i, h in enumerate(hot):
        if h:
            run += 1
            if run >= need:
                first = i - run + 1
                # 回退 60ms 余量，避免切掉爆破音头
                first = max(0, first - 6)
                return (s + first * 160) / SR
        else:
            run = 0
    return None


def simulate(d, cfg, L):
    """按配置仿真切段。

    cfg = dict(silence_cut, min_seg, max_seg, rule1, skip_tail, min_run_ms)

    ★ 记账（严格）：
        base   = 当前段起点的绝对秒
        cursor = 已喂入音频的绝对采样下标
        chunk  = 0.64s = decoder 的输入粒度
      切点 = base + len(accum)/SR
      skip_tail 时，**整块丢弃**前导静音 chunk，base 与 cursor 同步前移。
    """
    from seg_stream import find_silence_in_range, find_trailing_silence

    sc = cfg['silence_cut']
    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    base = 0.0
    cursor = 0
    dropped = 0.0          # 因 skip_tail 丢弃的静音总时长

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

    def do_skip(cut_t):
        """丢弃前导静音 chunk（speech_start 语义），返回新的 base。"""
        if not cfg['skip_tail']:
            return cut_t
        ns = find_speech_start(d, cut_t, min_run_ms=cfg.get('min_run_ms', 120))
        if ns is None or ns <= cut_t:
            return cut_t
        # 丢弃整块 chunk
        k = int(np.ceil((ns - cut_t) / CHUNK_SEC - 1e-6))
        if k <= 0:
            return cut_t
        new_base = cut_t + k * CHUNK_SEC
        # 丢弃的音频必须确实是静音（否则会丢内容）
        seg = d[int(cut_t * SR):int(new_base * SR)]
        if seg.size:
            f = frame_db(seg)
            if f.size and f.max() > L.SILENCE_DB:
                return cut_t          # 有语音，不能丢
        nonlocal cursor, dropped
        cursor += k * chunk_n
        dropped += new_base - cut_t
        return new_base

    while True:
        n = accum.shape[0]
        dur = n / SR
        # 规则2：静音超时
        r2 = False
        if n >= int(SR * 0.5):
            win = int(SR * (sc + L.SILENCE_TAIL_GUARD_SEC + 0.5))
            span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                         end_sample=n, silence_db=L.SILENCE_DB,
                                         min_silence_ms=int(sc * 1000))
            if span is not None and guard_pass(accum, span[0]):
                r2 = True
        if r2:
            cut_t = base + dur
            cuts.append((cut_t, dur, 'rule2'))
            base = do_skip(cut_t)
            accum = np.zeros(0, dtype=np.float32)
            continue
        if dur >= cfg['max_seg']:
            cut_t = base + dur
            cuts.append((cut_t, dur, 'max'))
            base = do_skip(cut_t)
            accum = np.zeros(0, dtype=np.float32)
            continue
        if cfg['rule1'] and dur >= cfg['min_seg']:
            start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
            c = find_silence_in_range(accum, start_sample=start, end_sample=n,
                                      silence_db=L.SILENCE_DB, min_silence_ms=300)
            if c is not None:
                cut_t = base + dur
                cuts.append((cut_t, dur, 'rule1'))
                base = do_skip(cut_t)
                accum = np.zeros(0, dtype=np.float32)
                continue
        if cursor >= len(d):
            break
        chunk = d[cursor:cursor + chunk_n]
        cursor += chunk_n
        if chunk.size == 0:
            break
        accum = np.concatenate([accum, chunk]) if accum.size else chunk.copy()
    return cuts, dropped


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
        dict(key='B 0.8s', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=False),
        dict(key='B 0.8s+skip', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='B 0.8s+skip200', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True, min_run_ms=200),
        dict(key='C 0.6s+skip', silence_cut=0.6, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='D 0.4s+skip', silence_cut=0.4, min_seg=12.0, max_seg=20.0,
             rule1=True, skip_tail=True),
        dict(key='E 纯VAD0.8+skip', silence_cut=0.8, min_seg=12.0, max_seg=20.0,
             rule1=False, skip_tail=True),
        dict(key='F 0.8s+skip+min6s', silence_cut=0.8, min_seg=6.0, max_seg=20.0,
             rule1=True, skip_tail=True),
    ]

    print('=' * 112)
    print(f'Qwen3 方案 v3（修正记账 + 连续语音检测）  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 112)
    print(f'{"配置":<20} {"段数":>5} {"rule2":>6} {"rule1":>6} {"max":>4} '
          f'{"r2安全":>8} {"空段":>5} {"<2s":>4} {"中位段长":>9} '
          f'{"提前中位":>9} {"提前最大":>9} {"丢弃静音":>9} {"末段":>8}')

    results = []
    base_f = None
    for cfg in configs:
        cuts, dropped = simulate(d, cfg, L)
        c = Counter(x[2] for x in cuts)
        n = len(cuts)
        durs = np.array([x[1] for x in cuts])
        r2cuts = [x for x in cuts if x[2] == 'rule2']
        r2safe = sum(1 for x in r2cuts if safe_at(d, x[0]))
        prev = 0.0
        empties = []
        for x in cuts:
            if speech_ratio(d, prev, x[0]) < 0.10:
                empties.append((prev, x[0] - prev))
            prev = x[0]
        grid, f = frontier(cuts, total)
        if base_f is None:
            base_f = f
        adv = base_f - f
        pos = adv[adv > 0]
        adv_med = float(np.median(pos)) if pos.size else 0.0
        adv_max = float(pos.max()) if pos.size else 0.0
        last = cuts[-1][0] if cuts else 0.0
        results.append(dict(cfg=cfg, cuts=cuts, n=n, cnt=dict(c), r2safe=r2safe,
                            n_empty=len(empties), dropped=dropped,
                            adv_med=adv_med, adv_max=adv_max, last=last,
                            durs=durs.tolist(), empties=empties))
        rs = f'{r2safe}/{len(r2cuts)}' if r2cuts else '-'
        print(f'{cfg["key"]:<20} {n:>5} {c.get("rule2",0):>6} {c.get("rule1",0):>6} '
              f'{c.get("max",0):>4} {rs:>8} {len(empties):>5} {int((durs<2).sum()):>4} '
              f'{np.median(durs):>8.1f}s {adv_med:>8.2f}s {adv_max:>8.1f}s '
              f'{dropped:>8.1f}s {last:>7.1f}s')

    print()
    print('=' * 112)
    print('【Q1】skip_tail（Qwen3 speech_start 语义）到底带来什么')
    print('=' * 112)
    for r in results:
        if 'skip' not in r['cfg']['key'] and r['cfg']['key'] not in ('A 现状基线', 'B 0.8s'):
            continue
        print(f'\n▶ {r["cfg"]["key"]}')
        print(f'   段数 {r["n"]}  规则 {r["cnt"]}  '
              f'规则2 安全 {r["r2safe"]}  空段 {r["n_empty"]}  '
              f'丢弃静音 {r["dropped"]:.1f}s')
        ds = np.array(r['durs'])
        print(f'   段长 p5={np.percentile(ds,5):.2f} p25={np.percentile(ds,25):.2f} '
              f'p50={np.percentile(ds,50):.2f} p75={np.percentile(ds,75):.2f} '
              f'p95={np.percentile(ds,95):.2f}  max={ds.max():.2f}s')
        print(f'   白字提前 中位 {r["adv_med"]:.2f}s  最大 {r["adv_max"]:.1f}s  '
              f'末段定稿 {r["last"]:.1f}s')
        if r['empties']:
            print(f'   空段: {[(round(a,2), round(b,2)) for a,b in r["empties"][:6]]}')

    print()
    print('=' * 112)
    print('【Q3】空段判别特征（用 B 0.8s+skip 的空段）')
    print('=' * 112)
    for r in results:
        if r['cfg']['key'] != 'B 0.8s+skip':
            continue
        for a, b in r['empties'][:8]:
            seg = d[int(a * SR):int(b * SR)]
            f = frame_db(seg)
            hot = f > -35.0
            # 最长连续热帧
            run = best = 0
            for h in hot:
                run = run + 1 if h else 0
                best = max(best, run)
            print(f'   [{a:.2f},{b:.2f}] 长{b-a:.2f}s  max={f.max():.1f}dB '
                  f'p90={np.percentile(f,90):.1f}dB  '
                  f'语音帧占比={hot.mean()*100:.1f}%  最长连续语音={best*10}ms')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'diag_seg_qwen3_v3_result.json')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump([dict(key=r['cfg']['key'], cfg=r['cfg'], n=r['n'], cnt=r['cnt'],
                        r2safe=r['r2safe'], n_empty=r['n_empty'], dropped=r['dropped'],
                        adv_med=r['adv_med'], adv_max=r['adv_max'], last=r['last'],
                        durs=r['durs'],
                        empties=r['empties'],
                        cuts=[[round(x[0], 3), round(x[1], 3), x[2]] for x in r['cuts']])
                   for r in results], fp, ensure_ascii=False, indent=1)
    print(f'\n→ {out}')


if __name__ == '__main__':
    main()
