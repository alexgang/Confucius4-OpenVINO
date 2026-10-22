r"""diag_seg_cut_quality.py — 规则1 切点是否切在词中间（真正的算法缺陷指标）

核心发现（待本脚本证实）
-------------------------
`Segmenter.due()` 的规则1：

    start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
    return self._find(acc, start_sample=start, end_sample=n,
                      silence_db=-40.0, min_silence_ms=300) is not None

`find_silence_in_range()` 返回的是**范围内最长静音段的中点**，
但 `due()` **只拿它做布尔判断**，切点仍然落在 `audio_accum` 的末尾
（chunk 边界）。

→ 也就是说：**「找到词间隙再切」的设计意图从未实现**，
   实际行为是「只要最近 3 秒里有任何 ≥300ms 静音，就在段尾切」。

后果：
  * 静音门槛极低（300ms）+ 回看窗口只有 3s（该素材 17.1 处/分钟 ≈ 每 3.5s 一处）
    → 规则1 几乎在「刚满 12s」的第一个 chunk 就满足条件
    → 94% 的段是 12 秒兜底，且切点**落在词中间**的概率很高

本脚本测量：
  1. 规则1 切点前 0.5s 是否安静（独立判据：安静=切在词间隙=安全）
  2. 规则1 里有多少切点其实**错过了**一个更好的切点
     （即：段内存在 ≥300ms 静音，但引擎切在了它后面）
  3. 若按「静音中点切」重放，切点质量会变成什么样（对照）

用法：
  python diag_seg_cut_quality.py <wav> [--minutes 61]
"""

from __future__ import annotations

import os
import sys
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000


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
    """切点前 win_ms 是否整体安静 → 安全（在词间隙）/ 危险（切碎词）"""
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True, -120.0
    db = frame_db(seg)
    return float(db.max()) < -40.0, float(db.max())


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
    import diag_seg_sim_real as SIM

    os.environ['LIVECAP_GUARD_REL'] = '1'
    importlib.reload(L)
    cuts = SIM.simulate(L.Segmenter(), d)

    print('=' * 80)
    print(f'规则1 切点质量分析  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 80)
    print(f'总段数 {len(cuts)}')

    r1 = [c for c in cuts if c[2] == 'rule1']
    r2 = [c for c in cuts if c[2] == 'rule2']
    mx = [c for c in cuts if c[2] == 'max']

    for tag, group in (('规则1(常规/12s兜底)', r1), ('规则2(静音超时)', r2),
                       ('硬切(20s)', mx)):
        if not group:
            continue
        safe = 0
        unsafe = 0
        worst = []
        for c in group:
            ok, mx_db = safe_at(d, c[0])
            if ok:
                safe += 1
            else:
                unsafe += 1
                worst.append((c[0], mx_db))
        print(f'\n【{tag}】{len(group)} 段')
        print(f'   切在词间隙（安全，前0.5s安静）: {safe} ({100*safe/len(group):.1f}%)')
        print(f'   切在词中间（危险）            : {unsafe} ({100*unsafe/len(group):.1f}%)')
        if worst:
            print(f'   危险切点前0.5s峰值能量（前 8 个）: '
                  f'{[f"{p:.1f}s/{m:.0f}dB" for p, m in worst[:8]]}')

    # ── 关键：规则1 段内是否「本来有更好的切点」 ──
    print('\n' + '=' * 80)
    print('【根因验证】规则1 里有多少段「段内明明有 ≥300ms 静音，却切在段尾」')
    print('=' * 80)
    from seg_stream import find_silence_in_range

    missed = 0
    checked = 0
    examples = []
    for c in r1[:80]:
        end_t = c[0]
        seg_len = c[1]
        start_t = end_t - seg_len
        s = int(start_t * SR)
        e = int(end_t * SR)
        seg = d[s:e]
        if seg.size == 0:
            continue
        # 在**段内**（不含末尾 0.64s chunk）找 ≥300ms 静音
        cut = find_silence_in_range(seg, start_sample=0, end_sample=seg.size,
                                    silence_db=-40.0, min_silence_ms=300)
        checked += 1
        if cut is not None:
            mid_t = start_t + cut / SR
            if mid_t < end_t - 0.3:      # 确实比段尾早
                missed += 1
                if len(examples) < 6:
                    ok_now, _ = safe_at(d, end_t)
                    ok_mid, _ = safe_at(d, mid_t)
                    examples.append((end_t, mid_t, ok_now, ok_mid))

    print(f'   抽检 {checked} 个规则1 段：')
    print(f'   → 段内存在更早的 ≥300ms 静音（本可以切在词间隙）：'
          f'**{missed}/{checked} ({100*missed/max(1,checked):.0f}%)**')
    if examples:
        print('\n   样例（当前切点 vs 应有切点 → 是否切在词中间）：')
        for end_t, mid_t, ok_now, ok_mid in examples:
            print(f'     当前 @{end_t:8.2f}s 安全={ok_now}   '
                  f'应有 @{mid_t:8.2f}s 安全={ok_mid}   '
                  f'差 {end_t-mid_t:.2f}s')

    # ── 对照：如果真的按静音中点切，质量会怎样 ──
    print('\n' + '=' * 80)
    print('【对照】假设真的按「段内静音中点」切（设计意图），切点质量')
    print('=' * 80)
    alt_safe = 0
    alt_unsafe = 0
    for c in r1:
        end_t = c[0]
        start_t = end_t - c[1]
        seg = d[int(start_t * SR):int(end_t * SR)]
        if seg.size == 0:
            continue
        cut = find_silence_in_range(seg, start_sample=0, end_sample=seg.size,
                                    silence_db=-40.0, min_silence_ms=300)
        t = start_t + cut / SR if cut is not None else end_t
        ok, _ = safe_at(d, t)
        if ok:
            alt_safe += 1
        else:
            alt_unsafe += 1
    n = len(r1)
    print(f'   规则1 段数 {n}')
    print(f'   现状（切在段尾）      : 安全 {n-alt_unsafe} / 危险 {alt_unsafe}'
          f'  ({100*alt_unsafe/n:.1f}% 危险)')
    print(f'   按静音中点切（设计意图）: 安全 {alt_safe} / 危险 {alt_unsafe}'
          f'  ({100*alt_unsafe/n:.1f}% 危险)')
    print(f'   → 安全率 {100*(n-alt_unsafe)/n:.1f}% → {100*alt_safe/n:.1f}%')


if __name__ == '__main__':
    main()
