r"""diag_seg_c108_verify.py — 验证 C-108 落地后的真实 Segmenter 行为

用**真实**的 `live_caption_app.Segmenter`（不是仿真）跑 61 分钟真实演讲，
核对：
  * 切点数、规则分布
  * 规则2 切点安全性（切点前 0.5s 是否安静）
  * 空段数（段内语音帧占比 < 10%）
  * 段长分布
  * 与离线仿真（diag_seg_qwen3_v4.py 的 C 配置）是否**逐点一致**

记账（严格）：
    base   = 当前段起点的绝对秒
    cursor = 已喂入音频的绝对采样下标
    切点   = base + len(accum)/SR
    base  += len(accum)/SR      ← 秒，不是采样数

用法：
  python diag_seg_c108_verify.py <wav> [--minutes 61]
"""

from __future__ import annotations

import os
import sys
import importlib
from collections import Counter

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


def speech_ratio(d, t0, t1, thr=-35.0):
    s = int(t0 * SR)
    e = int(t1 * SR)
    seg = d[s:e]
    if seg.size == 0:
        return 0.0
    f = frame_db(seg)
    return float(np.mean(f > thr)) if f.size else 0.0


def run_real(L, d):
    """用真实 Segmenter 跑一遍，返回切点列表。"""
    from seg_stream import find_silence_in_range

    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    base = 0.0
    cursor = 0
    seg = L.Segmenter()

    def kind_of(acc, dur):
        """判断这一刀是规则2/规则1/硬切 —— 用与 due() 相同的顺序。"""
        if dur >= L.MAX_SEG_SEC:
            return 'max'
        if not seg._has_speech(acc):
            return None
        if seg._silence_tail(acc):
            return 'rule2'
        if dur < L.MIN_SEG_SEC:
            return None
        start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
        if find_silence_in_range(acc, start_sample=start, end_sample=accum.shape[0],
                                 silence_db=-40.0, min_silence_ms=300) is not None:
            return 'rule1'
        return None

    while True:
        n = accum.shape[0]
        dur = n / SR
        k = kind_of(accum, dur)
        if k is not None:
            cuts.append((base + dur, dur, k))
            base += dur
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

    os.environ['LIVECAP_GUARD_REL'] = '1'
    import live_caption_app as L
    importlib.reload(L)

    print('=' * 84)
    print(f'C-108 落地验证（真实 Segmenter）  {os.path.basename(wav)}  {minutes} 分钟')
    print('=' * 84)
    print(f'  SILENCE_CUT_SEC      = {L.SILENCE_CUT_SEC}')
    print(f'  MIN_SEG_SEC          = {L.MIN_SEG_SEC}')
    print(f'  MAX_SEG_SEC          = {L.MAX_SEG_SEC}')
    print(f'  SEG_MIN_SPEECH_RUN_MS= {L.SEG_MIN_SPEECH_RUN_MS}')
    print(f'  GUARD_REL_MIN_SPEECH = {L.GUARD_REL_MIN_SPEECH_DB}')

    cuts = run_real(L, d)
    c = Counter(x[2] for x in cuts)
    n = len(cuts)
    durs = np.array([x[1] for x in cuts])
    r2 = [x for x in cuts if x[2] == 'rule2']
    r2safe = sum(1 for x in r2 if safe_at(d, x[0]))
    prev = 0.0
    empties = []
    for x in cuts:
        r = speech_ratio(d, prev, x[0])
        if r < 0.10:
            empties.append((round(prev, 2), round(x[0] - prev, 2), round(r * 100, 1)))
        prev = x[0]

    print()
    print(f'  切点数        {n}')
    print(f'  规则分布      {dict(c)}')
    print(f'  规则2 切点    {len(r2)} 个，安全 {r2safe} 个，危险 {len(r2)-r2safe} 个')
    print(f'  空段          {len(empties)} 个 {empties[:8]}')
    print(f'  段长  p5={np.percentile(durs,5):.2f} p25={np.percentile(durs,25):.2f} '
          f'p50={np.percentile(durs,50):.2f} p75={np.percentile(durs,75):.2f} '
          f'p95={np.percentile(durs,95):.2f} max={durs.max():.2f}s')
    print(f'  短段 <2s      {int((durs < 2).sum())}   <1s {int((durs < 1).sum())}')
    print(f'  末段定稿      {cuts[-1][0]:.1f}s / 音频总长 {len(d)/SR:.1f}s')

    # 与离线仿真 v4 的 C 配置对照
    v4p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'diag_seg_qwen3_v4_result.json')
    if os.path.exists(v4p):
        import json
        with open(v4p, encoding='utf-8') as f:
            v4 = json.load(f)
        ref = next((r for r in v4 if r['key'] == 'C hang0.8s+守卫'), None)
        if ref:
            rc = [(round(x[0], 3), x[2]) for x in ref['cuts']]
            mc = [(round(x[0], 3), x[2]) for x in cuts]
            same = rc == mc
            print()
            print(f'  与离线仿真 v4「C hang0.8s+守卫」对照：')
            print(f'    仿真段数 {len(rc)}  真实段数 {len(mc)}  逐点一致 = {same}')
            if not same:
                for i, (a, b) in enumerate(zip(rc, mc)):
                    if a != b:
                        print(f'      首个差异 @#{i}: 仿真 {a} vs 真实 {b}')
                        break

    # 关闭守卫的对照（证明守卫在做事）
    os.environ['LIVECAP_MIN_SPEECH_RUN_MS'] = '0'
    importlib.reload(L)
    cuts0 = run_real(L, d)
    prev = 0.0
    emp0 = 0
    for x in cuts0:
        if speech_ratio(d, prev, x[0]) < 0.10:
            emp0 += 1
        prev = x[0]
    r20 = [x for x in cuts0 if x[2] == 'rule2']
    print()
    print(f'  【守卫关闭对照】段数 {len(cuts0)}  规则 {dict(Counter(x[2] for x in cuts0))}  '
          f'规则2安全 {sum(1 for x in r20 if safe_at(d, x[0]))}/{len(r20)}  '
          f'空段 {emp0}')


if __name__ == '__main__':
    main()
