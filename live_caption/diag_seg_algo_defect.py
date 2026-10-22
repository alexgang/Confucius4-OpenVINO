r"""diag_seg_algo_defect.py — 判定「94% 靠 12 秒超时切分」是素材属性还是算法缺陷

用户提出的质疑
--------------
> 「如果 61 分钟的音频有超过 90% 是 12 秒超时切分定稿，说明我们的分句算法一定有问题」

这个质疑要拆成两问：
  A. **素材本身**是不是几乎没有自然停顿？（→ 12 秒切分是合理的）
  B. **算法**是不是漏掉了素材里明明存在的停顿？（→ 12 秒切分是兜底滥用）

判定方法
--------
统计音频里**所有** ≥1.2s 的静音（不限段边界），这代表「演讲者真实停顿分布」：
  * 若音频里大量存在 ≥1.2s 停顿，但引擎几乎不用规则2 → **算法漏判**（缺陷）
  * 若音频里本来就几乎没有 ≥1.2s 停顿 → 素材是连续演讲，12 秒切分是**合理**的

再加一条更硬的检验：**把 MIN_SEG_SEC 调小**（如 2s / 4s / 6s / 8s），
看引擎会不会在真实的停顿处切出更多段、且段长分布不再堆在 12s。
若调小后段数显著增加且切点仍落在词间隙 → 说明引擎**有能力**做自然切分，
只是被 MIN_SEG_SEC=12 的门槛挡住了 → **算法确实有问题**。

用法：
  python diag_seg_algo_defect.py <wav> [--minutes 61]
"""

from __future__ import annotations

import os
import sys
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000


def all_silences(d, thr_db=-40.0, min_ms=300):
    """扫描全片所有静音区间，返回 [(起点秒, 长度秒), ...]"""
    n = int(30 * SR / 1000)
    h = int(10 * SR / 1000)
    if d.size < n:
        return []
    nf = (d.size - n) // h + 1
    sq = d.astype(np.float64) ** 2
    cs = np.concatenate(([0.0], np.cumsum(sq)))
    db = np.empty(nf)
    for i in range(nf):
        s = i * h
        db[i] = 20.0 * np.log10(np.sqrt((cs[s + n] - cs[s]) / n + 1e-12) + 1e-7)
    quiet = db <= thr_db
    out = []
    i = 0
    while i < nf:
        if quiet[i]:
            j = i
            while j < nf and quiet[j]:
                j += 1
            length = (j - i) * h / SR
            if length * 1000 >= min_ms:
                out.append((i * h / SR, length))
            i = j
        else:
            i += 1
    return out


def sim_cuts(d, min_seg, rel='1'):
    """用真实 Segmenter 跑切段，可临时改 MIN_SEG_SEC。"""
    import live_caption_app as L
    import diag_seg_sim_real as SIM
    os.environ['LIVECAP_GUARD_REL'] = rel
    importlib.reload(L)
    L.MIN_SEG_SEC = min_seg          # 直接改模块常量（模拟「门槛调小」）
    seg = L.Segmenter()
    cuts = SIM.simulate(seg, d)
    return cuts


def cut_is_safe(d, t, win_ms=500):
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True
    n = int(30 * SR / 1000)
    if seg.size < n:
        seg = np.concatenate([seg, np.zeros(n - seg.size, dtype=seg.dtype)])
    rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2) + 1e-12))
    return 20.0 * np.log10(rms + 1e-7) < -40.0


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

    print('=' * 80)
    print(f'「12 秒超时主导」是素材属性还是算法缺陷？  '
          f'{os.path.basename(wav)}  {total/60:.1f} 分钟')
    print('=' * 80)

    # ── A. 素材自身的停顿分布 ──
    print('\n【A】素材自身的静音分布（扫全片所有静音，阈值 -40dB）')
    for min_ms in (300, 500, 800, 1000, 1200, 1500, 2000):
        sil = all_silences(d, -40.0, min_ms)
        # 合并相邻（间隔 < 0.3s 视为同一处停顿）
        merged = []
        for s, L in sil:
            if merged and s - (merged[-1][0] + merged[-1][1]) < 0.3:
                merged[-1] = (merged[-1][0], s + L - merged[-1][0])
            else:
                merged.append((s, L))
        if merged:
            per_min = len(merged) / (total / 60)
            avg = float(np.mean([x[1] for x in merged]))
            print(f'   ≥{min_ms:>4}ms 静音: {len(merged):>5} 处  '
                  f'（{per_min:5.1f} 处/分钟）  平均长度 {avg:.2f}s  '
                  f'最长 {max(x[1] for x in merged):.1f}s')
        else:
            print(f'   ≥{min_ms:>4}ms 静音: 0 处')

    sil12 = all_silences(d, -40.0, 1200)
    print(f'\n   → 素材里 ≥1.2s 的停顿共 {len(sil12)} 处 '
          f'（{len(sil12)/(total/60):.1f} 处/分钟）')

    # ── B. 引擎实际用了多少规则2 ──
    print('\n【B】引擎实际用规则2（静音超时）切了多少段')
    from collections import Counter
    for min_seg in (12.0,):
        cuts = sim_cuts(d, min_seg)
        c = Counter(x[2] for x in cuts)
        n = len(cuts)
        print(f'   MIN_SEG_SEC={min_seg}: 段数 {n}  '
              f'规则1 {c.get("rule1",0)} ({100*c.get("rule1",0)/n:.1f}%)  '
              f'规则2 {c.get("rule2",0)} ({100*c.get("rule2",0)/n:.1f}%)  '
              f'硬切 {c.get("max",0)}')

    # ── C. 把 MIN_SEG_SEC 调小，看引擎是否「有能力」做自然切分 ──
    print('\n【C】把 MIN_SEG_SEC 调小后，引擎能否在真实停顿处切出更多段？')
    print('   （若能 → 说明引擎有能力自然切分，被 12s 门槛挡住了 → 算法问题）')
    print(f'\n   {"MIN_SEG":>8} {"段数":>6} {"规则2":>6} {"安全":>6} {"危险":>6} '
          f'{"段长中位":>9} {"堆在12s":>9}')
    print('   ' + '-' * 66)
    for min_seg in (12.0, 10.0, 8.0, 6.0, 4.0, 3.0, 2.0):
        cuts = sim_cuts(d, min_seg)
        c = Counter(x[2] for x in cuts)
        n = len(cuts)
        durs = [x[1] for x in cuts]
        # 安全性只对新增的自然切点评估（rule2）
        r2 = [x[0] for x in cuts if x[2] == 'rule2']
        safe = sum(1 for p in r2 if cut_is_safe(d, p))
        unsafe = len(r2) - safe
        at12 = sum(1 for x in durs if 11.9 <= x <= 12.5)
        print(f'   {min_seg:>7.1f}s {n:>6} {len(r2):>6} {safe:>6} {unsafe:>6} '
              f'{np.median(durs):>8.1f}s {at12:>8}')

    # ── D. 结论数据：段数上界 ──
    print('\n【D】理论上「按停顿切」最多能切多少段？')
    sil12m = sil12
    print(f'   素材里 ≥1.2s 停顿：{len(sil12m)} 处')
    print(f'   引擎实际切：{len(sim_cuts(d, 12.0))} 段')
    print(f'   → 12 秒兜底切出的段数中，'
          f'{len(sim_cuts(d,12.0)) - len(sil12m)} 段是「没有对应停顿」的硬凑段')


if __name__ == '__main__':
    main()
