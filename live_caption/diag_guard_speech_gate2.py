r"""diag_guard_speech_gate2.py — 语音准入门槛扫描（**修正口径**：只比 rule2 切点）

为什么要重写
------------
`diag_guard_speech_gate.py` 的「新增/丢失」用的是**全体切点集合差**，
一旦某处提前切，后面所有切点都整体偏移一个 chunk，这些偏移点会被
误判成「新增」和「丢失」—— 正是 C-105 里踩过的那个坑。

本脚本按**正确口径**：
  * 只比较 **规则2（静音超时）** 触发的切点 —— 那才是被测判据直接影响的
  * 新增切点按「切点前 0.5s 是否整体安静」判安全性（独立于被测判据）
  * 单独统计**空段**（段长 < 3s 且由规则2 触发）—— 这是真实的用户可见缺陷：
    ASR 会对一段纯静音产出一句无意义内容，且打乱后续切点节奏

用法：
  python diag_guard_speech_gate2.py <wav> [--minutes 61] [--dump out.json]
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

GATES = [-45, -40, -35, -32, -30, -28, -26]


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 61.0
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

    def run(rel, gate):
        os.environ['LIVECAP_GUARD_REL'] = rel
        os.environ['LIVECAP_GUARD_REL_MIN_SPEECH'] = str(gate)
        importlib.reload(L)
        cuts, dets = SIM.simulate(L.Segmenter(), d, detail=True)
        return cuts, dets

    cutsA, _ = run('0', -45)
    r2A = {round(c[0], 2) for c in cutsA if c[2] == 'rule2'}
    tinyA = [c for c in cutsA if c[2] == 'rule2' and c[1] < 3.0]

    print('=' * 84)
    print(f'相对判据「语音准入门槛」扫描（只比 rule2 切点）  '
          f'音频={os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 84)
    print(f'基线 rel=0：{len(cutsA)} 段，规则2 {len(r2A)} 次，'
          f'其中空段(<3s) {len(tinyA)} 个\n')

    print(f'{"门槛":>7} {"段数":>5} {"规则2":>6} {"rule2新增":>10} {"rule2丢失":>10} '
          f'{"新增安全":>9} {"新增危险":>9} {"空段":>5}')
    print('-' * 84)

    rows = []
    for gate in GATES:
        cutsB, detsB = run('1', gate)
        r2B = {round(c[0], 2) for c in cutsB if c[2] == 'rule2'}

        new2 = sorted(r2B - r2A)
        lost2 = sorted(r2A - r2B)

        det_by_pos = {}
        for c, dt in zip(cutsB, detsB):
            det_by_pos[round(c[0], 2)] = dt[3]

        safe, unsafe, details = 0, 0, []
        for p in new2:
            ok, mx = SIM.cut_is_safe(d, p)
            info = det_by_pos.get(p) or {}
            dur = next((c[1] for c in cutsB if round(c[0], 2) == p), 0.0)
            details.append(dict(pos=p, dur=dur, safe=bool(ok),
                                pre_max_db=float(mx),
                                probe_db=info.get('probe_db'),
                                speech_db=info.get('speech_db')))
            if ok:
                safe += 1
            else:
                unsafe += 1

        tinyB = [c for c in cutsB if c[2] == 'rule2' and c[1] < 3.0]
        nseg = len(cutsB)

        print(f'{gate:>6}dB {nseg:>6} {len(r2B):>6} {len(new2):>10} {len(lost2):>10} '
              f'{safe:>9} {unsafe:>9} {len(tinyB):>5}')

        rows.append(dict(gate=gate, nseg=nseg, n_r2=len(r2B),
                         n_new2=len(new2), n_lost2=len(lost2),
                         safe=safe, unsafe=unsafe, n_tiny=len(tinyB),
                         tiny=[dict(pos=round(c[0], 2), dur=c[1]) for c in tinyB],
                         new_details=details))

    # 空段明细（各门槛）
    print('\n' + '=' * 84)
    print('【空段明细】规则2 触发但段长 < 3s 的段')
    print('=' * 84)
    for r in rows:
        if r['tiny']:
            print(f'门槛={r["gate"]:>4}dB  ' +
                  '  '.join(f'@{t["pos"]}s({t["dur"]:.2f}s)' for t in r['tiny']))
        else:
            print(f'门槛={r["gate"]:>4}dB  （无）')

    # 推荐门槛：新增安全最多、危险为 0、空段最少
    print('\n' + '=' * 84)
    print('【推荐】按「新增危险 = 0 且 空段最少」排序')
    print('=' * 84)
    ok = [r for r in rows if r['unsafe'] == 0]
    for r in sorted(ok, key=lambda x: (x['n_tiny'], -x['n_new2'])):
        print(f'  门槛={r["gate"]:>4}dB  rule2新增={r["n_new2"]:>2} 安全={r["safe"]:>2} '
              f'危险={r["unsafe"]:>2} 空段={r["n_tiny"]:>2}  段数={r["nseg"]}')

    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=1)
        print(f'\n→ {dump}')


if __name__ == '__main__':
    main()
