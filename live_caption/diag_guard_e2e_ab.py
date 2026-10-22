r"""diag_guard_e2e_ab.py — 端到端 A/B 的**可复现性**对照（排除机器噪声）

为什么需要这个
--------------
`diag_cut_quality.py` 跑出来的 `@ 时刻` 是**墙钟**（`time.perf_counter`），
不是音频时刻。音频按 100ms 步长喂入，ASR 算不完就会**积压**。

C-105 首轮 A/B（两次独立进程，先后串行）：
    基线 rel=0：59 段，墙钟 716.0s（≈ 音频 720s，积压 ≈ 0）
    新判据 rel=1：59 段，墙钟 772.8s（积压 ≈ 52.8s）
看着像「新判据让 ASR 变慢 7.8%」。

但离线切段模拟（`diag_guard_backlog.py`）证明**两跑段完全同构**：
段数相同、段长中位 12.2s 相同、max 15.4s 相同，规则2 触发仅差 1 次
→ 每段的 ASR 计算量几乎一致，**判据解释不了 52.8s 的积压差**。

剩下的最大嫌疑是**机器状态漂移**：
  * GPU 存在后台负载（OMEN / HpAppStore 常驻，SM 时钟仅 855~900MHz 低功耗态）
  * 首轮两跑是**先后串行**的，若存在热降频/降频，就是**时段效应**
    而非判据效应。

所以本脚本做 **ABBA 复现实验**：同一音频、同一参数，
交替跑 rel=0 / rel=1 / rel=1 / rel=0，各跑**独立进程**
（与首轮条件完全一致，避免进程内 OpenVINO 状态残留造成混淆）。

判读：
  * 若 A 组两次都 ≈716s、B 组两次都 ≈772s 且不重叠
    → 差异稳定，需进一步排查判据的真实影响
  * 若同一组两次差异 > 20s
    → 机器噪声占主导，端到端墙钟差**不能用于评价判据**
  * 若 A 组第二次也变慢（如 ≈770s）
    → 时段效应（机器热起来/降频），与判据无关

用法（单跑模式，由外层脚本按 ABBA 顺序调用）：
  python diag_guard_e2e_ab.py <wav> --minutes 12 --lang English \
      --rel 0|1 --out <输出目录> --tag A|B
"""

from __future__ import annotations

import os
import sys
import json
import time
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600          # 100 ms


def run_once(L, audio, force_language, rel, drop='18'):
    """跑一遍完整端到端，返回 (finals, stamps, wall)。"""
    os.environ['LIVECAP_GUARD_REL'] = rel
    os.environ['LIVECAP_GUARD_REL_DROP'] = drop
    importlib.reload(L)

    eng = L.make_engine('gpu_int8', on_log=lambda m: None,
                        force_language=force_language)
    finals, t_stamps = [], []
    t0 = time.perf_counter()
    for i in range(0, len(audio), STEP):
        r = eng.feed(audio[i:i + STEP], time.perf_counter())
        if r:
            finals.append(r)
            t_stamps.append(time.perf_counter() - t0)
    tail = eng.flush()
    if tail:
        finals.append(tail)
        t_stamps.append(time.perf_counter() - t0)
    wall = time.perf_counter() - t0
    eng.close()
    return finals, t_stamps, wall


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 12.0
    force_language = 'English'
    outdir = None
    rel = '1'
    tag = 'B'
    drop = '18'
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--lang' in args:
        force_language = args[args.index('--lang') + 1]
    if '--out' in args:
        outdir = os.path.abspath(args[args.index('--out') + 1])
    if '--rel' in args:
        rel = args[args.index('--rel') + 1]
    if '--tag' in args:
        tag = args[args.index('--tag') + 1]
    if '--drop' in args:
        drop = args[args.index('--drop') + 1]
    if outdir is None:
        outdir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', 'hy_bench', 'runs', 'c105_rule2', 'abba'))
    os.makedirs(outdir, exist_ok=True)

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(minutes * 60 * sr)]

    import live_caption_app as L

    print('=' * 74)
    print(f'run tag={tag}  判据=LIVECAP_GUARD_REL={rel} (drop={drop})  '
          f'音频={os.path.basename(wav)}  {minutes} 分钟  语种={force_language}')
    print('=' * 74, flush=True)

    finals, stamps, wall = run_once(L, d, force_language, rel, drop)
    end = stamps[-1] if stamps else 0.0
    print(f'   段数={len(finals)}  墙钟={wall:.1f}s  末段定稿 @{end:.1f}s  '
          f'（音频 {len(d)/SR:.0f}s，积压 {end - len(d)/SR:+.1f}s）', flush=True)

    fn = os.path.join(outdir, f'{tag}_rel{rel}_drop{drop}.json')
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(dict(cut=1.2, wall=wall, stamps=stamps, finals=finals,
                       tag=tag, rel=rel, drop=drop), f, ensure_ascii=False, indent=1)
    print(f'   → {fn}', flush=True)


if __name__ == '__main__':
    main()
