r"""diag_seg_sim.py — 离线切段模拟器（A/B 保护期判据，秒级出结果）

为什么需要它
------------
`Segmenter.due()` 是**纯音频逻辑**（只看 `audio_accum`），不需要 ASR 模型。
而 `audio_accum` 只在每凑满一个 chunk（CHUNK_SEC=0.64s）时才增长。
所以可以在**离线**精确复现引擎的切段行为：

    accum = []
    for chunk in 音频按 0.64s 切:
        accum += chunk
        while due(accum):
            记录切点(accum 末尾对应的时间)
            accum = []            # 段 reset

这让我们能在 61 分钟真实演讲上**秒级**跑 A/B，对比不同保护期判据的
切点差异，而不用每次都跑 20 分钟的真实推理。

它回答什么
----------
  Q1 新判据会不会让切点变多 / 变早？（变早 = 白字更快）
  Q2 新判据会不会把切点推到「词中间」——即切完之后 200ms 内就有语音
     重新起来（这是误切，会丢字/切碎词）
  Q3 各参数（DROP_DB）怎么选

用法：
  python diag_seg_sim.py <wav> [--minutes 61] [--cut 1.2]
                             [--mode abs|rel|both] [--drop 18] [--dump out.json]
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
MIN_SEG_SEC = 12.0
MAX_SEG_SEC = 20.0
SIL_LOOKBACK_SEC = 3.0
SILENCE_CUT_SEC = 1.2
SILENCE_TAIL_GUARD_SEC = 0.35
SILENCE_DB = -40.0


# ── 能量工具（与 seg_stream._frame_rms 同参数）─────────────────────
def frame_db(x: np.ndarray, frame_ms: int = 30, hop_ms: int = 10):
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if x.size < n:
        return np.zeros(0, dtype=np.float64), h
    nf = (x.size - n) // h + 1
    out = np.empty(nf, dtype=np.float64)
    sq = x.astype(np.float64) ** 2
    csum = np.concatenate(([0.0], np.cumsum(sq)))
    for i in range(nf):
        s = i * h
        e = s + n
        out[i] = 20.0 * np.log10(np.sqrt((csum[e] - csum[s]) / n + 1e-12) + 1e-7)
    return out, h


def trailing_silence(acc, silence_db, min_silence_ms):
    """复现 seg_stream.find_trailing_silence。"""
    n = acc.shape[0]
    if n <= 0:
        return None
    db, hop = frame_db(acc)
    if db.size == 0:
        return None
    is_sil = db < silence_db
    min_frames = max(1, int(min_silence_ms / 10))
    i = is_sil.shape[0] - 1
    while i >= 0 and is_sil[i]:
        i -= 1
    run = is_sil.shape[0] - 1 - i
    if run < min_frames:
        return None
    return (i + 1) * hop, n


def rms_db(x):
    if x.size == 0:
        return -120.0
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2) + 1e-12))
    return 20.0 * np.log10(r + 1e-7)


def guard_pass(acc, sil_start, mode, drop_db, rel_min_speech_db):
    """保护期判定。返回 (passed, probe_db, speech_db, noise_db)。"""
    guard = int(SR * SILENCE_TAIL_GUARD_SEC)
    ps = max(0, sil_start - guard)
    probe = acc[ps:sil_start]
    if probe.size == 0:
        return False, None, None, None
    probe_db = rms_db(probe)

    # 段内语音电平：静音起点之前那一段（排除末尾静音）的 90 分位
    seg_db, hop = frame_db(acc[:sil_start])
    if seg_db.size == 0:
        return False, probe_db, None, None
    speech_db = float(np.percentile(seg_db, 90))
    # 噪声底：段内被判为静音的帧的能量中位
    sil_frames = seg_db[seg_db < SILENCE_DB]
    noise_db = float(np.median(sil_frames)) if sil_frames.size else -120.0

    if mode == 'abs':
        return probe_db > SILENCE_DB, probe_db, speech_db, noise_db
    if mode == 'rel':
        if speech_db is None or speech_db < rel_min_speech_db:
            # 段内基本没有语音 → 退回绝对判据
            return probe_db > SILENCE_DB, probe_db, speech_db, noise_db
        return probe_db > speech_db - drop_db, probe_db, speech_db, noise_db
    if mode == 'both':
        # 相对判据为主，同时要求 probe 明显高于本段噪声底
        if speech_db is None or speech_db < rel_min_speech_db:
            return probe_db > SILENCE_DB, probe_db, speech_db, noise_db
        ok = probe_db > speech_db - drop_db
        ok = ok and (probe_db > noise_db + 4.0)
        return ok, probe_db, speech_db, noise_db
    raise ValueError(mode)


def due(acc, mode, drop_db, rel_min_speech_db):
    n = acc.shape[0]
    dur = n / SR
    if dur >= MAX_SEG_SEC:
        return True, 'max'
    # 规则 2
    if n >= int(SR * 0.5):
        span = trailing_silence(acc, SILENCE_DB, int(SILENCE_CUT_SEC * 1000))
        if span is not None:
            sil_start = span[0]
            ok, *_ = guard_pass(acc, sil_start, mode, drop_db, rel_min_speech_db)
            if ok:
                return True, 'rule2'
    # 规则 1
    if dur < MIN_SEG_SEC:
        return False, ''
    start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
    db, hop = frame_db(acc[start:])
    if db.size:
        is_sil = db < SILENCE_DB
        # find_silence_in_range: 找范围内最长静音段（≥300ms）
        best = None
        i = 0
        while i < is_sil.shape[0]:
            if is_sil[i]:
                j = i
                while j + 1 < is_sil.shape[0] and is_sil[j + 1]:
                    j += 1
                if (j - i + 1) * 10 >= 300:
                    if best is None or (j - i) > (best[1] - best[0]):
                        best = (i, j)
                i = j + 1
            else:
                i += 1
        if best is not None:
            return True, 'rule1'
    return False, ''


def simulate(d, mode, drop_db, rel_min_speech_db=-45.0):
    """离线模拟切段。返回 [(绝对切点秒, 规则, 段长, probe_db, speech_db, noise_db)]。"""
    chunk_n = int(CHUNK_SEC * SR)
    total = len(d) // chunk_n
    accum = np.zeros((0,), dtype=np.float32)
    abs_pos = 0            # 当前段在原始音频中的起点
    cuts = []
    for i in range(total):
        chunk = d[i * chunk_n:(i + 1) * chunk_n]
        accum = np.concatenate([accum, chunk]) if accum.size else chunk.copy()
        while True:
            ok, why = due(accum, mode, drop_db, rel_min_speech_db)
            if not ok:
                break
            n = accum.shape[0]
            # 切点绝对时间 = 段起点 + 段长
            cut_at = (abs_pos + n) / SR
            info = dict(cut_at=cut_at, why=why, seg_len=n / SR,
                        probe_db=None, speech_db=None, noise_db=None)
            # 记录诊断量（仅最后一次判定）
            if n >= int(SR * 0.5):
                span = trailing_silence(accum, SILENCE_DB, int(SILENCE_CUT_SEC * 1000))
                if span is not None:
                    _, p, s, nz = guard_pass(accum, span[0], mode, drop_db,
                                             rel_min_speech_db)
                    info['probe_db'] = p
                    info['speech_db'] = s
                    info['noise_db'] = nz
            cuts.append(info)
            abs_pos += n
            accum = np.zeros((0,), dtype=np.float32)
            break        # 段已 reset，accum 空
    return cuts


def resume_after(d, t, win_ms=300):
    """切点之后 win_ms 内是否又有语音（误切/切碎词的信号）。"""
    s = int(t * SR)
    e = int((t + win_ms / 1000.0) * SR)
    seg = d[s:min(e, len(d))]
    if seg.size == 0:
        return False, -120.0
    db, _ = frame_db(seg)
    if db.size == 0:
        return False, -120.0
    mx = float(db.max())
    return mx >= SILENCE_DB, mx


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    wav = args[0]
    minutes = 61.0
    cut = SILENCE_CUT_SEC
    mode = 'abs'
    drop = 18.0
    dump = None
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--mode' in args:
        mode = args[args.index('--mode') + 1]
    if '--drop' in args:
        drop = float(args[args.index('--drop') + 1])
    if '--dump' in args:
        dump = args[args.index('--dump') + 1]

    globals()['SILENCE_CUT_SEC'] = cut

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    total_s = min(minutes * 60.0, len(d) / sr)
    d = d[:int(total_s * sr)]

    print(f'文件 {os.path.basename(wav)}  {total_s/60:.1f} 分钟  '
          f'mode={mode} drop={drop} cut={cut}s')
    cuts = simulate(d, mode, drop)

    rules = {}
    for c in cuts:
        rules[c['why']] = rules.get(c['why'], 0) + 1
    print(f'切段 {len(cuts)} 段  {rules}')

    # 误切检测：切点后 300ms 内又有语音。
    # 只对「规则2（静音超时）切点」有意义 —— 规则2 的切点语义是
    # 「这里安静了 ≥1.2s，说话真的停了」，切完就该是下一句开口。
    # 规则1（12s 下限）的切点本来就在说话中间，它后面必然有语音，
    # 拿这个指标去衡量它没有意义。
    bad = 0
    bad_list = []
    r2 = [c for c in cuts if c['why'] == 'rule2']
    for c in r2:
        ok, mx = resume_after(d, c['cut_at'])
        if ok:
            bad += 1
            bad_list.append((c['cut_at'], c['why'], mx))
    print(f'规则2 切点后 300ms 内复有语音（切碎词信号）：{bad} / {len(r2)} '
          f'({bad/max(1,len(r2))*100:.1f}%)')
    for t, why, mx in bad_list[:10]:
        print(f'    {t:8.1f}s  {why}  复起 {mx:.1f}dB')

    # 延迟视角：切点相对「最后一次语音」的滞后
    lats = []
    for c in cuts:
        # 找切点前最后一个语音帧
        s = max(0, int((c['cut_at'] - 3.0) * SR))
        db, hop = frame_db(d[s:int(c['cut_at'] * SR)])
        if db.size == 0:
            continue
        i = db.shape[0] - 1
        while i >= 0 and db[i] < SILENCE_DB:
            i -= 1
        if i < 0:
            continue
        last_voice = (s + (i + 1) * hop) / SR
        lats.append(c['cut_at'] - last_voice)
    if lats:
        la = np.array(lats)
        print(f'\n切点滞后「最后一次语音」：中位 {np.median(la):.2f}s  '
              f'p90 {np.percentile(la,90):.2f}s  max {la.max():.2f}s')

    # 切点间隔分布（切得太密=碎段）
    if len(cuts) > 1:
        gaps = np.array([cuts[i + 1]['cut_at'] - cuts[i]['cut_at']
                         for i in range(len(cuts) - 1)])
        print(f'切点间隔：中位 {np.median(gaps):.2f}s  '
              f'p10 {np.percentile(gaps,10):.2f}s  min {gaps.min():.2f}s')

    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            json.dump(cuts, f, ensure_ascii=False, indent=1)
        print(f'已落盘 {dump}')


if __name__ == '__main__':
    main()
