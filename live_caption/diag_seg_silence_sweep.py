r"""diag_seg_silence_sweep.py — 静音阈值扫描：找到「既切在词间隙、又不等满 12 秒」的切法

前面诊断的结论
--------------
* 素材 `<redacted>.wav`（61 分钟连续演讲）：
    ≥300ms 停顿 1044 处（17.1 处/分钟）
    ≥500ms 停顿  546 处（ 9.0 处/分钟）
    ≥800ms 停顿  113 处（ 1.9 处/分钟）
    ≥1200ms 停顿   30 处（ 0.5 处/分钟）  ← 规则2 的门槛
* 引擎现状：94% 的段由「12 秒超时」兜底切出，
  且规则1 的 **89.2%** 切点落在词中间（切点前 0.5s 有 -21~-30dB 的语音能量）。
* 规则1 之所以「切在词中间」，是因为 `find_silence_in_range` 返回静音中点，
  但 `due()` 只拿它做**布尔判断**，实际切点仍在段尾（chunk 边界）。

为什么不能简单「切在静音中点」
-----------------------------
`mic_asr_app.py` 的历史注释已记录：若切在 chunk 内部，
那部分音频**已经参与过本段的 encoder**，再喂一次下一段就会被识别两遍。
所以切点必须对齐 chunk 边界（= audio_accum 末尾）。
→ **「切在词间隙」在当前架构下做不到**。

那正确的解法是什么？
------------------
既然切点只能在 chunk 边界，那么唯一能提高切点质量的办法是：
**让「切」的时机本身落在词间隙上** —— 也就是提高静音检测灵敏度，
让规则2 在更短的真实停顿处触发，而不是等满 12 秒兜底。

本脚本扫描 `SILENCE_CUT_SEC`（规则2 的静音门槛）：
  * 规则2 触发次数
  * 规则1（12s 兜底）占比
  * 切点安全率（切点前 0.5s 是否安静）
  * 段长分布 / 白字提前量

用法：
  python diag_seg_silence_sweep.py <wav> [--minutes 61]
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


def simulate(d, silence_cut, L):
    """用真实 Segmenter 的逻辑，但可调 SILENCE_CUT_SEC。

    ⚠️ 位置记账要严格：
       `base` = 当前段起始的**绝对**采样位置；
       `accum` = 当前段的音频；
       切点绝对位置 = base + len(accum)/SR。
       （早前版本把「累计位置」当「段内偏移」用来索引 d，导致双重计数、
        切点位置全错 —— 切点安全性统计因此完全失真。）
    """
    from seg_stream import find_silence_in_range, find_trailing_silence

    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    base = 0          # 当前段起点的绝对采样下标
    cursor = 0        # 已喂入音频的绝对采样下标

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
        # 规则2
        r2 = False
        if n >= int(SR * 0.5):
            win = int(SR * (silence_cut + L.SILENCE_TAIL_GUARD_SEC + 0.5))
            span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                         end_sample=n, silence_db=L.SILENCE_DB,
                                         min_silence_ms=int(silence_cut * 1000))
            if span is not None and guard_pass(accum, span[0]):
                r2 = True
        if r2:
            cuts.append((base / SR + dur, dur, 'rule2'))
            base += n
            accum = np.zeros(0, dtype=np.float32)
            continue
        if dur >= L.MAX_SEG_SEC:
            cuts.append((base / SR + dur, dur, 'max'))
            base += n
            accum = np.zeros(0, dtype=np.float32)
            continue
        if dur >= L.MIN_SEG_SEC:
            start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
            c = find_silence_in_range(accum, start_sample=start, end_sample=n,
                                      silence_db=-40.0, min_silence_ms=300)
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

    print('=' * 84)
    print(f'静音阈值扫描（规则2 门槛 SILENCE_CUT_SEC）  '
          f'{os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 84)
    print(f'{"门槛":>7} {"段数":>6} {"规则2":>6} {"规则1":>6} {"硬切":>6} '
          f'{"12s占比":>9} {"切点安全率":>11} {"段长中位":>9} {"末段音频":>9}')
    print('-' * 84)

    rows = []
    for sc in (1.2, 1.0, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3):
        cuts = simulate(d, sc, L)
        from collections import Counter
        c = Counter(x[2] for x in cuts)
        n = len(cuts)
        durs = [x[1] for x in cuts]
        safe = sum(1 for x in cuts if safe_at(d, x[0]))
        pct12 = 100 * (c.get('rule1', 0) + c.get('max', 0)) / max(1, n)
        print(f'{sc:>6.1f}s {n:>6} {c.get("rule2",0):>6} {c.get("rule1",0):>6} '
              f'{c.get("max",0):>6} {pct12:>8.1f}% {100*safe/max(1,n):>10.1f}% '
              f'{np.median(durs):>8.1f}s {cuts[-1][0]:>8.1f}s')
        rows.append(dict(sc=sc, n=n, c=dict(c), safe=safe,
                         durs=durs, cuts=cuts, pct12=pct12))

    print('\n' + '=' * 84)
    print('【切点安全性与静音时长关系】—— 门槛越短，误切风险越高')
    print('=' * 84)
    for r in rows:
        r2 = [x for x in r['cuts'] if x[2] == 'rule2']
        if not r2:
            continue
        nsafe = sum(1 for x in r2 if safe_at(d, x[0]))
        print(f'   门槛 {r["sc"]:.1f}s：规则2 {len(r2)} 段，'
              f'其中安全 {nsafe} ({100*nsafe/len(r2):.0f}%)，'
              f'危险 {len(r2)-nsafe}')

    print('\n' + '=' * 84)
    print('【推荐】在「切点安全率 ≥95%」前提下，取段数最多（白字最早）的门槛')
    print('=' * 84)
    ok = [r for r in rows if 100 * r['safe'] / max(1, r['n']) >= 95.0]
    for r in sorted(ok, key=lambda x: -x['n']):
        print(f'   门槛={r["sc"]:.1f}s  段数={r["n"]}  '
              f'安全率={100*r["safe"]/r["n"]:.1f}%  '
              f'12s占比={r["pct12"]:.1f}%  段长中位={np.median(r["durs"]):.1f}s')
    if not ok:
        print('   （没有门槛达到 95% 安全率）')


if __name__ == '__main__':
    main()
