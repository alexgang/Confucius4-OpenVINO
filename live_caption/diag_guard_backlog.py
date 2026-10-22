r"""diag_guard_backlog.py — 判定「末段定稿晚 56.8s」是真实退化还是机器噪声

背景
----
端到端日志里的 `@ 时刻` 是**墙钟**（`time.perf_counter`），不是音频时刻。
音频按 100ms 步长喂入，ASR 若算不完就会**积压**：

    积压(t) = 墙钟时刻 - 该段对应的音频时刻

基线末段 @716.0s ≈ 音频 720s（积压 ≈ 0），
新判据末段 @772.8s（积压 ≈ 52.8s）。
两种可能：
  A. 新判据产生的段更长 → ASR 解码更慢 → 吞吐下降（真实退化，必须修）
  B. 两次跑机器负载不同 → 纯噪声（与判据无关）

判定方法
--------
用**离线切段模拟**（真实 Segmenter，无 GPU，确定性）拿到两跑的
**音频侧切点时间轴**，再与端到端的**墙钟时间戳**配对：

    积压_i = 墙钟_i - 音频切点_i

看积压随段号的**增长斜率**：斜率越大 = 吞吐越慢。
斜率基本一致 → 墙钟差来自机器噪声，与判据无关。

同时输出段长分布、段数、规则触发统计 —— 判断新判据是否让段变长。

用法：
  python diag_guard_backlog.py <wav> --stamps <base.json> <new.json> [--minutes 12]
"""

from __future__ import annotations

import os
import sys
import json
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

import diag_seg_sim_real as SIM


def load_stamps(path):
    d = json.load(open(path, encoding='utf-8'))
    return d['stamps'], d.get('finals', []), d.get('wall', 0.0)


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 12.0
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    si = args.index('--stamps')
    base_json, new_json = args[si + 1], args[si + 2]

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    total_s = min(minutes * 60.0, len(d) / sr)
    d = d[:int(total_s * sr)]

    import live_caption_app as L

    def run(rel):
        os.environ['LIVECAP_GUARD_REL'] = rel
        importlib.reload(L)
        seg = L.Segmenter()
        return SIM.simulate(seg, d)

    cutsA = run('0')
    cutsB = run('1')

    print('=' * 74)
    print(f'音频 {os.path.basename(wav)}  {total_s/60:.1f} 分钟')
    print('=' * 74)

    for tag, cuts in (('基线 rel=0', cutsA), ('新判据 rel=1', cutsB)):
        durs = [c[1] for c in cuts]
        r2 = sum(1 for c in cuts if c[2] == 'rule2')
        mx = sum(1 for c in cuts if c[2] == 'max')
        print(f'\n【{tag}】段数={len(cuts)}  规则2={r2}  硬切={mx}')
        print(f'  段长: 中位={np.median(durs):.1f}s  均值={np.mean(durs):.1f}s '
              f' p90={np.percentile(durs,90):.1f}s  max={max(durs):.1f}s  合计={sum(durs):.1f}s')
        # 长段（>18s）个数——长段是解码变慢的主因
        long18 = sum(1 for x in durs if x > 18.0)
        long15 = sum(1 for x in durs if x > 15.0)
        print(f'  >15s 段数={long15}   >18s 段数={long18}')

    # ── 配对：离线音频切点 vs 端到端墙钟 ──
    print('\n' + '=' * 74)
    print('【积压分析】积压 = 端到端墙钟 − 离线模拟的音频切点')
    print('=' * 74)

    sa, fa, wa = load_stamps(base_json)
    sb, fb, wb = load_stamps(new_json)

    for tag, cuts, stamps, wall in (('基线 rel=0', cutsA, sa, wa),
                                    ('新判据 rel=1', cutsB, sb, wb)):
        n = min(len(cuts), len(stamps))
        print(f'\n【{tag}】配对段数={n}  端到端墙钟={wall:.1f}s')
        print('   段号  音频切点   墙钟      积压')
        rows = []
        for i in range(n):
            at = cuts[i][0]
            w = stamps[i]
            rows.append((i, at, w, w - at))
        for i, at, w, bl in rows[:3] + rows[len(rows) // 2 - 1:len(rows) // 2 + 1] + rows[-3:]:
            print(f'   {i:3d}  {at:8.2f}  {w:8.2f}  {bl:+8.2f}')
        # 斜率：积压随段号的线性增长率（每段平均增加多少积压）
        xs = np.array([r[0] for r in rows], dtype=np.float64)
        ys = np.array([r[3] for r in rows], dtype=np.float64)
        k, b = np.polyfit(xs, ys, 1)
        print(f'   积压斜率 = {k:+.3f} s/段   起始积压 = {ys[0]:+.2f}s   末积压 = {ys[-1]:+.2f}s')
        print(f'   末段：音频切点 {cuts[n-1][0]:.1f}s  墙钟 {stamps[n-1]:.1f}s')


if __name__ == '__main__':
    main()
