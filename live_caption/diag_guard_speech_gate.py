r"""diag_guard_speech_gate.py — 相对判据的「语音准入门槛」扫描（修 1.92s 空段）

问题
----
C-105 实施「绝对 ∪ 相对」并集判据后，在 12 分钟真实演讲上发现一处
**反直觉的代价**：新判据在 520.96s 多切了一刀**只有 1.92s 的段**。

对比两个「相对判据放行」的切点：

    切点        段长    probe      speech(段内p90)  probe-speech   性质
    256.00s    8.32s   -40.03dB   -26.37dB       -13.66dB      真正的渐弱尾音 → 救回正确
    520.96s    1.92s   -44.16dB   -40.37dB        -3.79dB      整段几乎无语音 → 误切

差别不在 probe 与 speech 的**差值**，而在 **speech 本身**：
  -26dB = 真的在说话；-40dB = 噪声底。

所以判别特征应该是「这一段到底有没有语音」，而不是靠 drop 阈值。
现实现 `GUARD_REL_MIN_SPEECH_DB = -45dB` 门槛太低，把 -40.37dB 也放行了。

代价
----
520.96s 这刀之后，规则1 从 520.96s 起算，凑满 12s 要到 533.12s
（比原来 531.84s 晚 1.28s），并逐段累积 —— 这才是端到端
「末段推迟」的真正来源（与机器噪声无关）。

本脚本扫描 `GUARD_REL_MIN_SPEECH` 的取值，看：
  * 合法切点（真渐弱尾音）还能不能救回
  * 空段（误切）能不能被挡住
  * 切点整体有没有重新收敛

用法：
  python diag_guard_speech_gate.py <wav> [--minutes 12] [--dump out.json]
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


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 12.0
    dump = None
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--dump' in args:
        dump = args[args.index('--dump') + 1]

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(minutes * 60 * sr)]

    import live_caption_app as L

    # 门槛候选：越负越宽松
    GATES = [-99, -45, -40, -35, -32, -30, -28, -26]

    def run(rel, gate=None):
        os.environ['LIVECAP_GUARD_REL'] = rel
        if gate is not None:
            os.environ['LIVECAP_GUARD_REL_MIN_SPEECH'] = str(gate)
        importlib.reload(L)
        return SIM.simulate(L.Segmenter(), d)

    # 基线
    base = run('0', -45)
    base_pos = {round(c[0], 2): c for c in base}

    print('=' * 78)
    print(f'相对判据「语音准入门槛」扫描  音频={os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 78)
    print(f'基线(rel=0)：{len(base)} 段，规则2 {sum(1 for c in base if c[2]=="rule2")} 次\n')

    rows = []
    for gate in GATES:
        cuts = run('1', gate)
        r2 = [c for c in cuts if c[2] == 'rule2']
        pos = {round(c[0], 2) for c in cuts}
        base_pos_set = {round(c[0], 2) for c in base}

        new_only = sorted(pos - base_pos_set)
        lost_only = sorted(base_pos_set - pos)

        # 新增切点里，按「段内语音电平」分成两类：
        #   真渐弱尾音（speech 明显高于噪声底）vs 空段（speech 接近噪声底）
        cut_dets = {}
        os.environ['LIVECAP_GUARD_REL'] = '1'
        os.environ['LIVECAP_GUARD_REL_MIN_SPEECH'] = str(gate)
        importlib.reload(L)
        _, dets = SIM.simulate(L.Segmenter(), d, detail=True)
        for c, dt in zip(cuts, dets):
            cut_dets[round(c[0], 2)] = dt[3]

        # 空段数：段长 < 3s 且由规则2 触发
        tiny = [c for c in r2 if c[1] < 3.0]

        # 新增切点的安全性
        unsafe = 0
        safe = 0
        for p in new_only:
            ok, _ = SIM.cut_is_safe(d, p)
            if ok:
                safe += 1
            else:
                unsafe += 1

        rows.append(dict(gate=gate, n=len(cuts), n_r2=len(r2),
                         n_new=len(new_only), n_lost=len(lost_only),
                         safe=safe, unsafe=unsafe, n_tiny=len(tiny),
                         tiny_pos=[round(c[0], 2) for c in tiny],
                         new_pos=new_only, lost_pos=lost_only))

        print(f'门槛={gate:>4}dB  段数={len(cuts):3d}  规则2={len(r2):2d}  '
              f'新增={len(new_only):2d}  丢失={len(lost_only):2d}  '
              f'安全={safe:2d} 危险={unsafe:2d}  **空段(<3s)={len(tiny):2d}**')
        if tiny:
            print(f'          空段位置: {rows[-1]["tiny_pos"]}')

    print('\n' + '=' * 78)
    print('【各门槛下新增切点的判据明细】')
    print('=' * 78)
    for r in rows:
        if not r['new_pos']:
            continue
        print(f'\n门槛={r["gate"]}dB:')
        for p in r['new_pos']:
            info = None
            for c, dt in zip([], []):
                pass
            print(f'   新增切点 @{p:8.2f}s')

    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f'\n→ {dump}')


if __name__ == '__main__':
    main()
