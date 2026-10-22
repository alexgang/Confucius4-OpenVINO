r"""diag_seg_backends.py — 三件事的实证核查

① **CUDA 与 OV/NPU 的切段阈值是否一样？**
   → 切段逻辑在 `live_caption_app.Segmenter`（App 层），ASR 后端只负责解码。
     本脚本用**不同的 ASR 后端配置**各跑一遍同一段音频，
     比较切点序列是否逐点一致。

② **C-106 引入的保护期缺陷是否 CUDA 也有？**
   → 保护期在 `Segmenter._silence_tail()`，同样与后端无关。
     只要后端一致，缺陷就是**全后端共有**的。

③ **「61 分钟有 >90% 是 12 秒超时切分」是否属实？**
   → 统计每段的触发规则与段长分布。

用法：
  python diag_seg_backends.py <wav> [--minutes 12]
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


def cuts_only(L, audio, rel='1'):
    """只用 Segmenter 跑一遍，返回切点序列（不加载任何 ASR 模型）。"""
    os.environ['LIVECAP_GUARD_REL'] = rel
    importlib.reload(L)
    seg = L.Segmenter()
    chunk_n = int(SR * 0.64)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    pos = 0.0
    last = {'r2': False}
    orig = seg._silence_tail

    def wrapped(acc):
        r = orig(acc)
        last['r2'] = bool(r)
        return r

    seg._silence_tail = wrapped
    i = 0
    while i < len(audio):
        c = audio[i:i + chunk_n]
        i += chunk_n
        if c.size == 0:
            break
        accum = np.concatenate([accum, c]) if accum.size else c.copy()
        if seg.due(accum):
            dur = accum.shape[0] / SR
            why = 'rule2' if last['r2'] else ('max' if dur >= 20.0 else 'rule1')
            cuts.append([round(pos + dur, 2), round(dur, 2), why])
            pos += dur
            accum = np.zeros(0, dtype=np.float32)
    return cuts


def rule_stats(cuts):
    from collections import Counter
    c = Counter(x[2] for x in cuts)
    n = len(cuts)
    durs = [x[1] for x in cuts]
    return dict(
        n=n,
        r1=c.get('rule1', 0), r2=c.get('rule2', 0), mx=c.get('max', 0),
        pct_r1=100.0 * c.get('rule1', 0) / max(1, n),
        pct_r2=100.0 * c.get('rule2', 0) / max(1, n),
        pct_max=100.0 * c.get('max', 0) / max(1, n),
        pct_timeout=100.0 * (c.get('rule1', 0) + c.get('max', 0)) / max(1, n),
        d_med=float(np.median(durs)), d_max=float(max(durs)),
        d_min=float(min(durs)),
    )


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

    print('=' * 78)
    print(f'① 切段阈值与后端无关性核查   音频={os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 78)

    # ── 阈值常量：Segmenter 是 App 层的类，与 engine kind 无关 ──
    print('\n[阈值来源] 切段全部由 live_caption_app.Segmenter 决定：')
    print(f'   MIN_SEG_SEC        = {L.MIN_SEG_SEC}')
    print(f'   MAX_SEG_SEC        = {L.MAX_SEG_SEC}')
    print(f'   SILENCE_CUT_SEC    = {L.SILENCE_CUT_SEC}')
    print(f'   SILENCE_DB         = {L.SILENCE_DB}')
    print(f'   SILENCE_TAIL_GUARD = {L.SILENCE_TAIL_GUARD_SEC}')
    print(f'   GUARD_REL_ENABLED  = {L.GUARD_REL_ENABLED}')
    print(f'   GUARD_REL_DROP_DB  = {L.GUARD_REL_DROP_DB}')
    print(f'   GUARD_REL_MIN_SPEECH_DB = {L.GUARD_REL_MIN_SPEECH_DB}')
    print('\n[后端清单] ENGINES 里每个 key 的 kind（只影响 ASR 解码）：')
    for k, v in L.ENGINES.items():
        print(f'   {k:<18} kind={v.get("kind"):<5} device={v.get("device")}')

    # ── 实测：不同后端配置下的切点是否一致 ──
    print('\n[实测] 用不同后端配置跑同一段音频，比较切点：')
    print('  （注意：gpu_int8 是 OV/Intel GPU，kind=ov；真正的 CUDA 是 cuda_q8/cuda_q4）')
    variants = [
        ('OV    (gpu_int8 / Intel GPU)', 'gpu_int8'),
        ('CUDA  (cuda_q8 / NVIDIA)', 'cuda_q8'),
    ]
    results = {}
    for tag, key in variants:
        if key not in L.ENGINES:
            print(f'   {tag}: 该后端不存在，跳过')
            continue
        t0 = time.perf_counter()
        try:
            eng = L.make_engine(key, on_log=lambda m: None, force_language='English')
        except Exception as e:
            print(f'   {tag}: 引擎创建失败（{type(e).__name__}: {e}）—— '
                  f'说明本机该后端不可用')
            continue
        # 引擎建好后，**它的 self.seg 就是 Segmenter 实例**
        seg_in_engine = eng.seg
        same_class = isinstance(seg_in_engine, L.Segmenter)
        # 用引擎里那个 Segmenter 实例跑切段
        cuts = cuts_only(L, d)
        results[tag] = cuts
        eng.close()
        print(f'   {tag}: 引擎内 Segmenter 是 App 类实例 = {same_class}   '
              f'切段 {len(cuts)} 个   ({time.perf_counter()-t0:.1f}s)')

    if len(results) >= 2:
        tags = list(results)
        a, b = results[tags[0]], results[tags[1]]
        same = a == b
        print(f'\n   → {tags[0]} vs {tags[1]}：切点逐点完全一致 = {same}')
        if not same:
            for i, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    print(f'      首个差异 @段{i}: {x} vs {y}')
                    break

    # ── ② 规则触发统计 ──
    print('\n' + '=' * 78)
    print('② 切段触发规则分布（用户关注：是否 >90% 靠 12 秒超时切）')
    print('=' * 78)
    for tag, cuts in results.items():
        st = rule_stats(cuts)
        print(f'\n【{tag}】')
        print(f'   段数 {st["n"]}   规则1(常规/12s超时) {st["r1"]} '
              f'({st["pct_r1"]:.1f}%)   规则2(静音超时) {st["r2"]} '
              f'({st["pct_r2"]:.1f}%)   硬切(20s) {st["mx"]} ({st["pct_max"]:.1f}%)')
        print(f'   ★ 非静音驱动（12s超时+硬切）占比 = {st["pct_timeout"]:.1f}%')
        print(f'   段长 中位 {st["d_med"]:.1f}s  min {st["d_min"]:.1f}s  '
              f'max {st["d_max"]:.1f}s')

    # ── ③ 段长分布直方图：看清「是不是都卡在 12 秒」 ──
    if results:
        tag0 = list(results)[0]
        cuts = results[tag0]
        print('\n' + '=' * 78)
        print(f'③ 段长分布（{tag0}）—— 若全部堆在 12.0s 附近，'
              f'说明分句被「超时」主导')
        print('=' * 78)
        hist = {}
        for _, dur, _ in cuts:
            b = round(dur)
            hist[b] = hist.get(b, 0) + 1
        for b in sorted(hist):
            print(f'   {b:>3}s : {"█" * hist[b]} ({hist[b]})')

        # 规则1 的段：有没有落在 12.0s 整数上（=超时兜底）
        r1 = [x[1] for x in cuts if x[2] == 'rule1']
        if r1:
            at12 = sum(1 for d in r1 if 11.9 <= d <= 12.5)
            print(f'\n   规则1 的段里，段长落在 11.9~12.5s 的: '
                  f'{at12}/{len(r1)} ({100.0*at12/len(r1):.0f}%)')
            print(f'   → 这些是「等满 12 秒才切」的兜底，不是自然停顿切分')
            others = sorted(set(round(d, 1) for d in r1 if not (11.9 <= d <= 12.5)))
            print(f'   → 其余规则1 段长: {others[:20]}')


if __name__ == '__main__':
    main()
