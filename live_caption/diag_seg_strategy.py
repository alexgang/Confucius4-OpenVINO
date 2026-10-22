r"""diag_seg_strategy.py — 切分策略对照：切点质量 vs 段数 vs 白字延迟

前面诊断出的两个硬事实
----------------------
1. **94.2% 的段由「12 秒超时」兜底切出**（规则1 只在段长 ≥12s 后才去看静音，
   而该素材 17.1 处 ≥300ms 静音/分钟 ≈ 每 3.5s 一处 → 刚满 12s 立刻满足）
2. **规则1 的 89.2% 切点落在词中间**（切点前 0.5s 有明显语音能量）
   —— `find_silence_in_range` 返回静音中点，但 `due()` **只拿它做布尔判断**，
     实际切点仍在段尾 → 「切在词间隙」的设计意图**从未实现**
3. **规则2（1.2s 静音超时）切点 100% 安全**

本脚本做策略对照，量化每种策略的：
  * 段数 / 段长分布
  * 切点安全性（前 0.5s 是否安静）
  * 白字提前量（相对现状能提前多少）

策略：
  S0 现状            规则1(12s门槛+300ms静音) ∪ 规则2(1.2s静音超时)
  S1 提高规则1静音门槛   规则1 的 min_silence_ms 从 300 → 1200（与规则2一致）
  S2 只用规则2        去掉规则1，纯静音驱动（MIN_SEG 门槛降到 2s）
  S3 规则1+真按静音中点切  额外实现设计意图（切点落在静音中点）

用法：
  python diag_seg_strategy.py <wav> [--minutes 61]
"""

from __future__ import annotations

import os
import sys
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
CHUNK_SEC = 0.64


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


def simulate(d, min_seg=12.0, max_seg=20.0, r1_min_ms=300,
             use_rule1=True, cut_at_silence_mid=False,
             silence_cut=1.2, guard_db=-40.0, rel_enabled=True):
    """通用切段模拟。参数化各策略。"""
    import live_caption_app as L
    from seg_stream import find_silence_in_range, find_trailing_silence

    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    pos = 0.0

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
        db = 20.0 * np.log10(rms + 1e-7)
        if db > guard_db:
            return True
        if not rel_enabled:
            return False
        seg_db = L._frame_db_series(acc[:sil_start])
        if seg_db.size == 0:
            return False
        speech = float(np.percentile(seg_db, 90))
        if speech < L.GUARD_REL_MIN_SPEECH_DB:
            return False
        return db > speech - L.GUARD_REL_DROP_DB

    while True:
        # 找尾静音
        r2 = False
        n = accum.shape[0]
        if n >= int(SR * 0.5):
            win = int(SR * (silence_cut + L.SILENCE_TAIL_GUARD_SEC + 0.5))
            span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                         end_sample=n, silence_db=guard_db,
                                         min_silence_ms=int(silence_cut * 1000))
            if span is not None and guard_pass(accum, span[0]):
                r2 = True
        if r2:
            dur = n / SR
            cuts.append((pos + dur, dur, 'rule2'))
            pos += dur
            accum = np.zeros(0, dtype=np.float32)
            continue

        dur = n / SR
        if dur >= max_seg:
            cuts.append((pos + dur, dur, 'max'))
            pos += dur
            accum = np.zeros(0, dtype=np.float32)
            continue

        cut_at = None
        if use_rule1 and dur >= min_seg:
            start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
            c = find_silence_in_range(accum, start_sample=start, end_sample=n,
                                      silence_db=-40.0, min_silence_ms=r1_min_ms)
            if c is not None:
                cut_at = (c / SR) if cut_at_silence_mid else None

        if cut_at is not None:
            # 切在静音中点：剩余音频 carry 到下一段
            cuts.append((pos + cut_at, cut_at, 'rule1mid'))
            pos += cut_at
            keep = int((dur - cut_at) * SR)
            accum = accum[-keep:] if keep > 0 else np.zeros(0, dtype=np.float32)
            continue

        if use_rule1 and dur >= min_seg:
            start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
            c = find_silence_in_range(accum, start_sample=start, end_sample=n,
                                      silence_db=-40.0, min_silence_ms=r1_min_ms)
            if c is not None:
                dur = n / SR
                cuts.append((pos + dur, dur, 'rule1'))
                pos += dur
                accum = np.zeros(0, dtype=np.float32)
                continue

        # 喂下一个 chunk
        if pos + dur >= len(d) / SR:
            break
        # （简化：直接按 chunk 推进）
        chunk = d[int((pos + dur) * SR):int((pos + dur + CHUNK_SEC) * SR)]
        if chunk.size == 0:
            break
        accum = np.concatenate([accum, chunk]) if accum.size else chunk.copy()
    return cuts


def report(name, cuts, d, base_cuts=None):
    from collections import Counter
    c = Counter(x[2] for x in cuts)
    n = len(cuts)
    durs = [x[1] for x in cuts]
    safe = sum(1 for x in cuts if safe_at(d, x[0]))
    at12 = sum(1 for x in durs if 11.9 <= x <= 12.5)
    print(f'\n【{name}】')
    print(f'   段数 {n}   规则1 {c.get("rule1",0)}  规则2 {c.get("rule2",0)}  '
          f'硬切 {c.get("max",0)}  规则1mid {c.get("rule1mid",0)}')
    print(f'   ★ 12s超时占比 {100*(c.get("rule1",0)+c.get("max",0))/max(1,n):.1f}%   '
          f'堆在12s的段 {at12}')
    print(f'   ★ 切点安全率 {100*safe/max(1,n):.1f}%  (危险 {n-safe})')
    print(f'   段长 中位 {np.median(durs):.1f}s  min {min(durs):.1f}s  max {max(durs):.1f}s')
    return dict(name=name, n=n, safe=safe, at12=at12,
                r2=c.get('rule2', 0), durs=durs, cuts=cuts)


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

    import live_caption_app as L
    os.environ['LIVECAP_GUARD_REL'] = '1'
    importlib.reload(L)

    print('=' * 80)
    print(f'切分策略对照  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 80)

    rows = []
    rows.append(report('S0 现状（规则1 300ms + 规则2 1.2s）',
                       simulate(d, min_seg=12.0, r1_min_ms=300), d))
    rows.append(report('S1 规则1静音门槛 300→1200ms',
                       simulate(d, min_seg=12.0, r1_min_ms=1200), d))
    rows.append(report('S2 纯静音驱动（去掉规则1，门槛降到2s）',
                       simulate(d, min_seg=2.0, use_rule1=False), d))
    rows.append(report('S3 规则1按静音中点切 + 门槛1200ms',
                       simulate(d, min_seg=12.0, r1_min_ms=1200,
                                cut_at_silence_mid=True), d))

    print('\n' + '=' * 80)
    print('【汇总】')
    print('=' * 80)
    print(f'{"策略":<40}{"段数":>6}{"12s占比":>9}{"切点安全率":>12}{"规则2":>7}')
    print('-' * 80)
    for r in rows:
        from collections import Counter
        c = Counter(x[2] for x in r['cuts'])
        pct = 100 * (c.get('rule1', 0) + c.get('max', 0)) / max(1, r['n'])
        print(f'{r["name"]:<40}{r["n"]:>6}{pct:>8.1f}%'
              f'{100*r["safe"]/max(1,r["n"]):>11.1f}%{r["r2"]:>7}')

    # 白字提前量：以「当前段覆盖的音频内容」为准
    print('\n' + '=' * 80)
    print('【白字时机】各策略下，最后一段定稿对应的音频时刻')
    print('=' * 80)
    for r in rows:
        last = r['cuts'][-1][0] if r['cuts'] else 0
        print(f'   {r["name"]:<40} 末段覆盖到音频 {last:8.1f}s  '
              f'（音频总长 {len(d)/SR:.1f}s）')


if __name__ == '__main__':
    main()
