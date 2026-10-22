r"""diag_seg_sim_real.py — 用 **App 里真实的 Segmenter** 做保护期判据 A/B

为什么不用重写的模拟器
----------------------
`diag_seg_sim.py` / `diag_guard_benefit.py` 里我自己重写了一遍 `due()`，
存在与 `live_caption_app.Segmenter` 实现漂移的风险（实测就发现过：
`sil_start` 的算法细节不同会差 1.5dB，导致放行/拦截结论相反）。

本脚本**直接 import App 的 Segmenter**，只切换环境变量
`LIVECAP_GUARD_REL`（0/1）来 A/B。这样测出来的就是线上真实行为。

模拟的前提
----------
`audio_accum` 只在每凑满一个 chunk（CHUNK_SEC=0.64s）时增长，所以
切段判定发生在 0.64s 的格点上。离线复现就是：

    accum = []
    for chunk in 音频按 0.64s 切:
        accum += chunk
        while seg.due(accum):
            记录切点; accum = []

用法：
  python diag_seg_sim_real.py <wav> [--minutes 61] [--dump out.json]
"""

from __future__ import annotations

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
CHUNK_SEC = 0.64
SILENCE_DB = -40.0


def frame_db(x, frame_ms=30, hop_ms=10):
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if x.size < n:
        return np.zeros(0, dtype=np.float64), h
    nf = (x.size - n) // h + 1
    out = np.empty(nf, dtype=np.float64)
    sq = x.astype(np.float64) ** 2
    cs = np.concatenate(([0.0], np.cumsum(sq)))
    for i in range(nf):
        s = i * h
        out[i] = 20.0 * np.log10(np.sqrt((cs[s + n] - cs[s]) / n + 1e-12) + 1e-7)
    return out, h


def simulate(seg, d, detail=False):
    """用真实 Segmenter 模拟切段。

    返回 [(切点绝对秒, 段长秒, 触发规则)]，规则取值 'rule2'/'rule1'/'max'。

    为什么要标规则：A/B 对比切点集合时有个陷阱 —— 一旦 B 在某处提前切了，
    后面**所有**切点都会整体偏移一个 chunk（0.64s），于是「只在 B 出现」
    的切点里混进了大量与判据无关的规则1 切点。必须按规则分开看。

    detail=True 时额外返回每个切点的保护期判据明细
    (probe_db / 段内语音电平 / 绝对是否通过 / 相对是否通过)。
    """
    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    dets = []
    abs_pos = 0.0
    # 记录本次 due() 判定时，规则2 是否成立
    last = {'r2': False, 'info': None}

    orig_st = seg._silence_tail

    def wrapped(acc):
        r = orig_st(acc)
        last['r2'] = bool(r)
        if detail:
            last['info'] = guard_detail(acc)
        return r

    seg._silence_tail = wrapped
    try:
        i = 0
        while i < len(d):
            chunk = d[i:i + chunk_n]
            i += chunk_n
            if chunk.size == 0:
                break
            accum = np.concatenate([accum, chunk]) if accum.size else chunk.copy()
            if seg.due(accum):
                n = accum.shape[0]
                dur = n / SR
                if last['r2']:
                    why = 'rule2'
                elif dur >= 20.0:
                    why = 'max'
                else:
                    why = 'rule1'
                cuts.append((abs_pos + n / SR, dur, why))
                if detail:
                    dets.append((abs_pos + n / SR, dur, why, last['info']))
                abs_pos += n / SR
                accum = np.zeros(0, dtype=np.float32)
    finally:
        seg._silence_tail = orig_st
    return (cuts, dets) if detail else cuts


def guard_detail(acc):
    """复现保护期判据的内部量，返回明细字典（用于人工核对）。"""
    import live_caption_app as L
    from seg_stream import find_trailing_silence
    n = acc.shape[0]
    if n < int(SR * 0.5):
        return None
    win = int(SR * (L.SILENCE_CUT_SEC + L.SILENCE_TAIL_GUARD_SEC + 0.5))
    span = find_trailing_silence(acc, start_sample=max(0, n - win), end_sample=n,
                                 silence_db=L.SILENCE_DB,
                                 min_silence_ms=int(L.SILENCE_CUT_SEC * 1000))
    if span is None:
        return None
    sil_start = span[0]
    g = int(SR * L.SILENCE_TAIL_GUARD_SEC)
    ps = max(0, sil_start - g)
    probe = acc[ps:sil_start]
    if probe.size == 0:
        return None
    rms = float(np.sqrt(np.mean(probe.astype(np.float64) ** 2) + 1e-12))
    db = 20.0 * np.log10(rms + 1e-7)
    seg_db = L._frame_db_series(acc[:sil_start])
    speech = float(np.percentile(seg_db, 90)) if seg_db.size else -120.0
    return dict(
        probe_db=float(db), speech_db=float(speech),
        tail_sil=float((n - sil_start) / SR),
        abs_ok=bool(db > L.SILENCE_DB),
        rel_ok=bool(speech >= L.GUARD_REL_MIN_SPEECH_DB
                    and db > speech - L.GUARD_REL_DROP_DB),
    )


def cut_is_safe(d, t, win_ms=500):
    """切点安全性：切点前 win_ms 是否整体安静（切在词间隙=安全）。"""
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True, -120.0
    db, _ = frame_db(seg)
    if db.size == 0:
        return True, -120.0
    mx = float(db.max())
    return mx < SILENCE_DB, mx


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
    total_s = min(minutes * 60.0, len(d) / sr)
    d = d[:int(total_s * sr)]

    import importlib
    import live_caption_app as L

    print(f'文件 {os.path.basename(wav)}  {total_s/60:.1f} 分钟\n')

    # ── A: 旧判据（相对阈值关闭）──
    os.environ['LIVECAP_GUARD_REL'] = '0'
    importlib.reload(L)
    segA = L.Segmenter()
    cutsA = simulate(segA, d)
    safeA = sum(1 for c in cutsA if cut_is_safe(d, c[0])[0])

    # ── B: 新判据（相对阈值开启，drop=18）──
    os.environ['LIVECAP_GUARD_REL'] = '1'
    os.environ['LIVECAP_GUARD_REL_DROP'] = '18'
    importlib.reload(L)
    segB = L.Segmenter()
    cutsB, detsB = simulate(segB, d, detail=True)

    print('── A 旧判据（绝对阈值 probe > -40dB）──')
    r2A = [c for c in cutsA if c[2] == 'rule2']
    r1A = [c for c in cutsA if c[2] != 'rule2']
    print(f'  切段 {len(cutsA)}（规则2 {len(r2A)}，规则1/硬切 {len(r1A)}）'
          f'  段长中位 {np.median([s for _, s, _ in cutsA]):.1f}s')

    print('\n── B 新判据（绝对 ∪ 相对，drop=18dB）──')
    r2B = [c for c in cutsB if c[2] == 'rule2']
    r1B = [c for c in cutsB if c[2] != 'rule2']
    print(f'  切段 {len(cutsB)}（规则2 {len(r2B)}，规则1/硬切 {len(r1B)}）'
          f'  段长中位 {np.median([s for _, s, _ in cutsB]):.1f}s')

    print('\n  ★ 规则2 切点对比（这才是保护期判据直接影响的）──')
    tA2 = set(round(t, 2) for t, _, _ in r2A)
    tB2 = set(round(t, 2) for t, _, _ in r2B)
    onlyB2 = sorted(tB2 - tA2)
    onlyA2 = sorted(tA2 - tB2)
    print(f'    A 有 {len(tA2)} 个，B 有 {len(tB2)} 个')
    print(f'    只在 B 出现：{len(onlyB2)}  {onlyB2[:20]}')
    print(f'    只在 A 出现：{len(onlyA2)}  {onlyA2[:20]}')

    if onlyB2:
        print('\n    新增的规则2 切点 —— 安全性 & 白字提前量：')
        gains = []
        n_unsafe = 0
        for t in onlyB2:
            safe, mx = cut_is_safe(d, t)
            later = [x for x, _, _ in cutsA if x > t + 0.01]
            gain = (min(later) - t) if later else None
            gs = '—' if gain is None else f'{gain:.2f}s'
            flag = '安全' if safe else f'危险(前0.5s有{mx:.1f}dB)'
            if not safe:
                n_unsafe += 1
            else:
                if gain is not None:
                    gains.append(gain)
            print(f'      {t:9.2f}s  {flag:24s} 提前 {gs}')
        if gains:
            g = np.array(gains)
            print(f'\n    新增且安全 {len(gains)} 个，危险 {n_unsafe} 个')
            print(f'    白字提前量：中位 {np.median(g):.2f}s  p90 {np.percentile(g,90):.2f}s  '
                  f'max {g.max():.2f}s  合计 {g.sum():.1f}s')

    if onlyA2:
        print('\n    ★ 丢失的规则2 切点（相对判据把基线能切的也拦了）：')
        for t in onlyA2[:15]:
            print(f'      {t:9.2f}s')

    # ── 判据明细：相对判据到底在哪些段起了作用 ──
    print('\n  判据明细（B 模式下每个规则2 切点的探针量）：')
    print(f'    {"时刻":>10} {"尾静音":>7} {"probe":>8} {"段内p90":>9} '
          f'{"相对阈值":>9} {"绝对":>5} {"相对":>5}')
    rel_only = 0
    for t, dur, why, info in detsB:
        if why != 'rule2' or not info:
            continue
        thr = info['speech_db'] - 18.0
        tag = ''
        if info['rel_ok'] and not info['abs_ok']:
            tag = '  ← 相对判据救回'
            rel_only += 1
        print(f'    {t:10.2f} {info["tail_sil"]:6.2f}s {info["probe_db"]:7.1f}dB '
              f'{info["speech_db"]:8.1f}dB {thr:8.1f}dB '
              f'{"通" if info["abs_ok"] else "拦":>4} '
              f'{"通" if info["rel_ok"] else "拦":>4}{tag}')
    print(f'  → 相对判据单独救回了 {rel_only} 个切点')

    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            json.dump(dict(A=cutsA, B=cutsB,
                           onlyB2=onlyB2, onlyA2=onlyA2,
                           detsB=[(t, dur, w, i) for t, dur, w, i in detsB]),
                      f, ensure_ascii=False, indent=1)
        print(f'\n已落盘 {dump}')


if __name__ == '__main__':
    main()
