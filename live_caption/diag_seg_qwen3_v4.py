r"""diag_seg_qwen3_v4.py — Qwen3 方案最终扫描：hangover × min_seg × 空段守卫

前三版仿真的结论汇总
----------------------
v1（diag_seg_qwen3.py）：
  * 照搬 Qwen3 的**纯 VAD 模式**（关掉 12s 计时器兜底）在我们素材上是
    **负收益**：198 段里 159 段是 20s 硬切，段长中位 20.5s > 现状 12.2s。
  * 归因（v2 的 diag_seg_qwen3_why.py 逐 chunk 追踪）：未切段的原因里
    **5504/5508 次是 `no_trailing_silence`** —— 素材是连续演讲，
    ≥800ms 的停顿 61 分钟只有 113 处（1.9 处/分钟），
    说话人几乎不停顿，VAD 没有可切的点。
  * hangover 降到 400ms 后空段从 1 涨到 11。

v2（diag_seg_qwen3_v2.py）：`skip_tail` 记账 bug（改 base 没同步 cursor），
  导致切点安全率假性暴跌。已在 v3 修正。

v3（diag_seg_qwen3_v3.py）：
  * 修正记账后，`skip_tail`（Qwen3 服务端 VAD 的 `speech_start` 语义）
    在本素材上**几乎无收益**：61 分钟只丢弃 3.8s 静音
    → 因为段间几乎没有静音可丢。
  * hangover 0.8s：规则2 17→37 段，切点 **37/37 全安全**，
    白字最大提前 15.4s。空段 2 个（基线 1 个）。
  * hangover 0.6s：规则2 103 段，**103/103 全安全**，白字提前中位 1.28s，
    但空段涨到 5 个。
  * hangover 0.4s：规则2 274 段里只有 181 安全（**93 个危险**），
    空段 11 个 → 不可用。

★ 空段的根因（v3 Q3 + 手工核实）
  典型空段 [41.60, 42.88]：帧 dB max=−36.3 / p90=−44.0，
  尾静音起点前 0.35s 的 probe = **−42.5dB**（绝对判据 −40dB 拦下），
  但段内 p90 = **−44.0dB**（≥ 准入门槛 −40dB？否 → 拦下）……
  等等，实际结果是**放行**了 —— 因为准入门槛判的是 `speech >= -40`，
  这里 p90=−44 应被拦。
  → 实际是「噪声突发」把 p90 拉高到 −40 以上时，准入门槛误放行。
  → **空段判别特征不是能量电平，而是「有没有成段的连续语音」。**

v4 的解法：加**空段守卫** —— 段内必须存在一段**足够长的连续语音**
  （连续 ≥ MIN_SPEECH_RUN_MS 的帧都高于 −35dB）才允许切段。
  这比「p90 电平」稳健得多：单个噪声突发不会构成连续语音。

本脚本扫描 hangover × min_seg × 守卫阈值，给出最终推荐配置。

用法：
  python diag_seg_qwen3_v4.py <wav> [--minutes 61]
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
SPEECH_FRAME_DB = -35.0     # 判定「有语音」的帧电平
MIN_SPEECH_RUN_MS = 200     # 连续语音最短时长


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


def max_speech_run(frames_db, thr=SPEECH_FRAME_DB):
    """最长的连续「语音帧」时长（ms）。"""
    hot = frames_db > thr
    run = best = 0
    for h in hot:
        run = run + 1 if h else 0
        if run > best:
            best = run
    return best * 10


def safe_at(d, t, win_ms=500):
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True
    return float(frame_db(seg).max()) < -40.0


def speech_ratio(d, t0, t1, thr=SPEECH_FRAME_DB):
    s = int(t0 * SR)
    e = int(t1 * SR)
    seg = d[s:e]
    if seg.size == 0:
        return 0.0
    f = frame_db(seg)
    return float(np.mean(f > thr)) if f.size else 0.0


def simulate(d, cfg, L):
    """按配置仿真切段。

    cfg = dict(silence_cut, min_seg, max_seg, rule1, skip_tail,
               guard_run_ms)
      guard_run_ms : 空段守卫 —— 段内最长连续语音须 ≥ 此值才允许切段
                     （0 = 不启用守卫）
    """
    from seg_stream import find_silence_in_range, find_trailing_silence

    sc = cfg['silence_cut']
    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    base = 0.0
    cursor = 0
    dropped = 0.0

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

    def speech_ok(acc):
        """空段守卫：段内必须有一段足够长的连续语音。"""
        need = cfg.get('guard_run_ms', 0)
        if need <= 0:
            return True
        f = L._frame_db_series(acc)
        if f.size == 0:
            return False
        return max_speech_run(f) >= need

    def find_speech_start(t):
        s = int(t * SR)
        if s >= len(d):
            return None
        seg = d[s:s + int(6.0 * SR)]
        if seg.size == 0:
            return None
        f = frame_db(seg)
        if f.size == 0:
            return None
        hot = f > L.SILENCE_DB
        need = 12          # 连续 120ms
        run = 0
        for i, h in enumerate(hot):
            if h:
                run += 1
                if run >= need:
                    first = max(0, i - run + 1 - 6)
                    return (s + first * 160) / SR
            else:
                run = 0
        return None

    def do_skip(cut_t):
        if not cfg.get('skip_tail'):
            return cut_t
        ns = find_speech_start(cut_t)
        if ns is None or ns <= cut_t:
            return cut_t
        k = int(np.ceil((ns - cut_t) / CHUNK_SEC - 1e-6))
        if k <= 0:
            return cut_t
        new_base = cut_t + k * CHUNK_SEC
        seg = d[int(cut_t * SR):int(new_base * SR)]
        if seg.size:
            f = frame_db(seg)
            if f.size and f.max() > L.SILENCE_DB:
                return cut_t
        nonlocal cursor, dropped
        cursor += k * chunk_n
        dropped += new_base - cut_t
        return new_base

    while True:
        n = accum.shape[0]
        dur = n / SR
        r2 = False
        if n >= int(SR * 0.5):
            win = int(SR * (sc + L.SILENCE_TAIL_GUARD_SEC + 0.5))
            span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                         end_sample=n, silence_db=L.SILENCE_DB,
                                         min_silence_ms=int(sc * 1000))
            if span is not None and guard_pass(accum, span[0]) and speech_ok(accum):
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
            if c is not None and speech_ok(accum):
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

    configs = []
    # 基线
    configs.append(dict(key='A 现状基线', silence_cut=1.2, min_seg=12.0, max_seg=20.0,
                        rule1=True, skip_tail=False, guard_run_ms=0))
    # hangover 扫描（保留 12s 计时器兜底）
    for sc in (0.8, 0.6, 0.5):
        configs.append(dict(key=f'B hang{sc}s', silence_cut=sc, min_seg=12.0,
                            max_seg=20.0, rule1=True, skip_tail=False, guard_run_ms=0))
        configs.append(dict(key=f'C hang{sc}s+守卫', silence_cut=sc, min_seg=12.0,
                            max_seg=20.0, rule1=True, skip_tail=False, guard_run_ms=200))
    # 降 min_seg（计时器门槛）
    for ms in (8.0, 6.0, 4.0):
        configs.append(dict(key=f'D hang0.8+min{ms}s+守卫', silence_cut=0.8,
                            min_seg=ms, max_seg=20.0, rule1=True,
                            skip_tail=False, guard_run_ms=200))
    # skip_tail 组合
    configs.append(dict(key='E hang0.8+守卫+skip', silence_cut=0.8, min_seg=12.0,
                        max_seg=20.0, rule1=True, skip_tail=True, guard_run_ms=200))
    # 纯 VAD（对照）
    configs.append(dict(key='F 纯VAD0.8+守卫', silence_cut=0.8, min_seg=12.0,
                        max_seg=20.0, rule1=False, skip_tail=False, guard_run_ms=200))
    configs.append(dict(key='G 纯VAD0.8+守卫+30s', silence_cut=0.8, min_seg=12.0,
                        max_seg=30.0, rule1=False, skip_tail=False, guard_run_ms=200))

    print('=' * 116)
    print(f'Qwen3 方案 v4 最终扫描  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 116)
    print(f'{"配置":<26} {"段数":>5} {"rule2":>6} {"rule1":>6} {"max":>4} '
          f'{"r2安全":>9} {"空段":>5} {"<2s":>4} {"<1s":>4} {"中位段长":>9} '
          f'{"提前中位":>9} {"提前最大":>9} {"末段":>8}')

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
        print(f'{cfg["key"]:<26} {n:>5} {c.get("rule2",0):>6} {c.get("rule1",0):>6} '
              f'{c.get("max",0):>4} {rs:>9} {len(empties):>5} {int((durs<2).sum()):>4} '
              f'{int((durs<1).sum()):>4} {np.median(durs):>8.1f}s '
              f'{adv_med:>8.2f}s {adv_max:>8.1f}s {last:>7.1f}s')

    print()
    print('=' * 116)
    print('【空段守卫的效果】')
    print('=' * 116)
    for r in results:
        if '守卫' not in r['cfg']['key']:
            continue
        base = next((b for b in results if b['cfg']['key'] == 'A 现状基线'), None)
        print(f'\n▶ {r["cfg"]["key"]}')
        print(f'   段数 {r["n"]}  规则 {r["cnt"]}  '
              f'规则2安全 {r["r2safe"]}  空段 {r["n_empty"]}  '
              f'丢弃静音 {r["dropped"]:.1f}s')
        ds = np.array(r['durs'])
        print(f'   段长 p5={np.percentile(ds,5):.2f} p25={np.percentile(ds,25):.2f} '
              f'p50={np.percentile(ds,50):.2f} p75={np.percentile(ds,75):.2f} '
              f'p95={np.percentile(ds,95):.2f}  max={ds.max():.2f}s')
        print(f'   白字提前 中位 {r["adv_med"]:.2f}s  最大 {r["adv_max"]:.1f}s  '
              f'末段定稿 {r["last"]:.1f}s')
        if r['empties']:
            print('   空段: ' + str([(round(a, 2), round(b - a, 2)) for a, b in r['empties'][:8]]))

    print()
    print('=' * 116)
    print('【推荐】安全率 100%（规则2 无危险切点）+ 空段 ≤ 基线 + 白字提前为正')
    print('=' * 116)
    base_empty = next((r['n_empty'] for r in results if r['cfg']['key'] == 'A 现状基线'), 1)
    cands = []
    for r in results:
        cfg = r['cfg']
        if cfg['key'] == 'A 现状基线':
            continue
        r2cuts = [x for x in r['cuts'] if x[2] == 'rule2']
        danger = len(r2cuts) - r['r2safe']
        if danger > 0:
            continue
        if r['n_empty'] > base_empty:
            continue
        if r['adv_med'] <= 0 and r['adv_max'] <= 0:
            continue
        cands.append(r)
    for r in sorted(cands, key=lambda x: (-x['adv_med'], x['n'])):
        cfg = r['cfg']
        print(f'   {cfg["key"]:<26} 段数={r["n"]:<5} 空段={r["n_empty"]}  '
              f'提前中位={r["adv_med"]:.2f}s 最大={r["adv_max"]:.1f}s  '
              f'中位段长={np.median(r["durs"]):.1f}s  '
              f'收尾开销={r["n"]*FINALIZE_MS/1000:.1f}s')
    if not cands:
        print('   （无满足条件的配置）')

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'diag_seg_qwen3_v4_result.json')
    with open(out, 'w', encoding='utf-8') as fp:
        json.dump([dict(key=r['cfg']['key'], cfg=r['cfg'], n=r['n'], cnt=r['cnt'],
                        r2safe=r['r2safe'], n_empty=r['n_empty'], dropped=r['dropped'],
                        adv_med=r['adv_med'], adv_max=r['adv_max'], last=r['last'],
                        durs=r['durs'], empties=r['empties'],
                        cuts=[[round(x[0], 3), round(x[1], 3), x[2]] for x in r['cuts']])
                   for r in results], fp, ensure_ascii=False, indent=1)
    print(f'\n→ {out}')


if __name__ == '__main__':
    main()
