r"""diag_guard_benefit.py — 量化「换保护期判据」的收益与代价

决策问题
--------
保护期从绝对阈值（probe > -40dB）换成相对阈值（probe > 段内语音电平 - X dB），
值不值？需要两个数字：

  收益：白字能提前多少秒出现？
  代价：新增的切点里，有多少切在了「词中间」（会切碎词、丢字）？

质量判据（独立于被测判据）
--------------------------
「切点安全性」：**切点前 0.5s 的窗口必须整体安静**（所有帧 < -40dB）。
  * 安静 → 切点落在词间隙 → 安全，不会切碎词；
  * 不安静 → 切点落在词中间 → 危险。
这个判据只看切点**之前**、用 0.5s 窗口，与被测判据（静音起点**之前**、
0.35s 窗口）参数不同、位置不同，互相独立。

注意：第一版曾用「切点后 1.5s 内有没有说话」判断真停/误切，这是错的 ——
用户停顿 1.2s 后继续说是完全正常的，那仍是**真停顿**（值得提前定稿），
却被误判成「没停」。已废弃。

口径
----
所有切点都以「段末绝对音频位置」为准。两种判据各跑一遍同一份音频，
对比切点集合。

用法：
  python diag_guard_benefit.py <wav> [--minutes 61] [--drops 6,9,12,15,18,24]
                               [--dump out.json]
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


def trailing_silence(acc, silence_db, min_silence_ms):
    db, hop = frame_db(acc)
    if db.size == 0:
        return None
    is_sil = db < silence_db
    minf = max(1, int(min_silence_ms / 10))
    i = is_sil.shape[0] - 1
    while i >= 0 and is_sil[i]:
        i -= 1
    if is_sil.shape[0] - 1 - i < minf:
        return None
    return (i + 1) * hop, acc.shape[0]


def rms_db(x):
    if x.size == 0:
        return -120.0
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2) + 1e-12))
    return 20.0 * np.log10(r + 1e-7)


def guard_ok(acc, sil_start, mode, drop):
    """保护期判定。返回 (passed, probe_db, speech_db)。"""
    guard = int(SR * SILENCE_TAIL_GUARD_SEC)
    ps = max(0, sil_start - guard)
    probe = acc[ps:sil_start]
    if probe.size == 0:
        return False, -120.0, -120.0
    pdb = rms_db(probe)
    if mode == 'abs':
        return pdb > SILENCE_DB, pdb, -120.0
    # 相对判据：段内语音电平（静音起点之前的 90 分位）
    seg_db, _ = frame_db(acc[:sil_start])
    if seg_db.size == 0:
        return False, pdb, -120.0
    speech = float(np.percentile(seg_db, 90))
    if speech < -45.0:
        # 段内几乎没有语音（纯噪声段）→ 退回绝对判据
        return pdb > SILENCE_DB, pdb, speech
    return pdb > speech - drop, pdb, speech


def due(acc, mode, drop):
    n = acc.shape[0]
    dur = n / SR
    if dur >= MAX_SEG_SEC:
        return True, 'max'
    if n >= int(SR * 0.5):
        span = trailing_silence(acc, SILENCE_DB, int(SILENCE_CUT_SEC * 1000))
        if span is not None:
            ok, _, _ = guard_ok(acc, span[0], mode, drop)
            if ok:
                return True, 'rule2'
    if dur < MIN_SEG_SEC:
        return False, ''
    start = max(0, int((dur - SIL_LOOKBACK_SEC) * SR))
    db, _ = frame_db(acc[start:])
    if db.size:
        is_sil = db < SILENCE_DB
        i = 0
        found = False
        while i < is_sil.shape[0]:
            if is_sil[i]:
                j = i
                while j + 1 < is_sil.shape[0] and is_sil[j + 1]:
                    j += 1
                if (j - i + 1) * 10 >= 300:
                    found = True
                    break
                i = j + 1
            else:
                i += 1
        if found:
            return True, 'rule1'
    return False, ''


def simulate(d, mode, drop):
    chunk_n = int(SR * CHUNK_SEC)
    accum = np.zeros(0, dtype=np.float32)
    cuts = []
    abs_pos = 0.0
    i = 0
    while i < len(d):
        chunk = d[i:i + chunk_n]
        i += chunk_n
        if chunk.size == 0:
            break
        accum = np.concatenate([accum, chunk])
        while True:
            ok, why = due(accum, mode, drop)
            if not ok:
                break
            cuts.append(dict(at=abs_pos + accum.shape[0] / SR, why=why))
            abs_pos += accum.shape[0] / SR
            accum = np.zeros(0, dtype=np.float32)
    return cuts


def cut_is_safe(d, t, win_ms=500):
    """切点安全性：切点前 win_ms 是否整体安静。

    安静 → 切在词间隙（安全）；有语音 → 切在词中间（切碎词）。
    """
    s = int(t * SR)
    seg = d[max(0, s - int(win_ms / 1000.0 * SR)):s]
    if seg.size == 0:
        return True, -120.0
    db, _ = frame_db(seg)
    if db.size == 0:
        return True, -120.0
    mx = float(db.max())
    return mx < SILENCE_DB, mx


def wait_gain(d, new_cut, base_cuts):
    """白字提前量：新切点比基线里下一个切点早多少秒。

    基线在真停顿处会因为保护期拦不住而拖到 12s 下限，
    所以「下一个基线切点」通常就是那条延迟的定稿时刻。
    """
    later = [b['at'] for b in base_cuts if b['at'] > new_cut['at'] + 0.01]
    if not later:
        return None
    return min(later) - new_cut['at']


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    wav = args[0]
    minutes = 61.0
    drops = [6, 9, 12, 15, 18, 24]
    dump = None
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--drops' in args:
        drops = [float(x) for x in args[args.index('--drops') + 1].split(',')]
    if '--dump' in args:
        dump = args[args.index('--dump') + 1]

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    total_s = min(minutes * 60.0, len(d) / sr)
    d = d[:int(total_s * sr)]

    print(f'文件 {os.path.basename(wav)}  {total_s/60:.1f} 分钟  '
          f'cut={SILENCE_CUT_SEC}s  保护期={SILENCE_TAIL_GUARD_SEC}s\n')

    base = simulate(d, 'abs', 0)
    base_r2 = [c for c in base if c['why'] == 'rule2']
    base_safe = sum(1 for c in base_r2 if cut_is_safe(d, c['at'])[0])
    print(f'基线（绝对阈值 probe > -40dB）')
    print(f'  切段 {len(base)}  规则2 {len(base_r2)}  规则1 {len(base)-len(base_r2)}')
    print(f'  规则2 切点中「切在词间隙（安全）」{base_safe}/{len(base_r2)}\n')

    summary = []
    for dr in drops:
        alt = simulate(d, 'rel', dr)
        alt_r2 = [c for c in alt if c['why'] == 'rule2']
        base_times = set(round(c['at'], 2) for c in base_r2)
        alt_times = set(round(c['at'], 2) for c in alt_r2)
        new_r2 = [c for c in alt_r2 if round(c['at'], 2) not in base_times]
        lost = [c for c in base_r2 if round(c['at'], 2) not in alt_times]

        safe_new = [c for c in new_r2 if cut_is_safe(d, c['at'])[0]]
        unsafe_new = [c for c in new_r2 if not cut_is_safe(d, c['at'])[0]]
        gains = [g for g in (wait_gain(d, c, base) for c in safe_new) if g is not None]

        print(f'── drop={dr:.0f}dB ──')
        print(f'  规则2 触发 {len(alt_r2)}（基线 {len(base_r2)}）'
              f'  新增 {len(new_r2)}  丢失 {len(lost)}')
        print(f'  新增切点安全性：安全（词间隙）{len(safe_new)}  '
              f'危险（词中间）{len(unsafe_new)}')
        if gains:
            g = np.array(gains)
            print(f'  白字提前量（仅安全切点）：中位 {np.median(g):.2f}s  '
                  f'p90 {np.percentile(g,90):.2f}s  max {g.max():.2f}s  '
                  f'合计 {g.sum():.1f}s')
        else:
            print('  白字提前量：—')
        if unsafe_new:
            det = ', '.join(f'{c["at"]:.1f}s' for c in unsafe_new[:8])
            print(f'  危险切点位置：{det}')
        print()

        summary.append(dict(drop=dr, n_r2=len(alt_r2), n_new=len(new_r2),
                            n_lost=len(lost), n_safe=len(safe_new),
                            n_unsafe=len(unsafe_new),
                            gains=gains,
                            unsafe_at=[c['at'] for c in unsafe_new]))

    print('=' * 74)
    print('汇总：drop  规则2  新增  丢失  安全  危险  提前量中位  提前量合计')
    print('-' * 74)
    for s in summary:
        g = s['gains']
        gm = f'{np.median(g):.2f}s' if g else '—'
        gs = f'{sum(g):.1f}s' if g else '—'
        print(f'  {s["drop"]:4.0f}  {s["n_r2"]:5d}  {s["n_new"]:4d}  '
              f'{s["n_lost"]:4d}  {s["n_safe"]:4d}  {s["n_unsafe"]:4d}  '
              f'{gm:>9}  {gs:>10}')
    print(f'  基线  {len(base_r2):5d}     -     -  {base_safe:4d}  '
          f'{len(base_r2)-base_safe:4d}      -        -')

    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            json.dump(dict(base=base, summary=summary), f,
                      ensure_ascii=False, indent=1)
        print(f'\n已落盘 {dump}')


if __name__ == '__main__':
    main()
