r"""diag_seg_qwen3_why.py — 定位「纯 VAD 模式退化」「空段」两个现象的根因

两个待解释的现象（来自 diag_seg_qwen3.py，61 分钟真实演讲）：

  现象 1：纯 VAD（hangover=0.8s，关掉规则1）里 **159/198 段是 20s 硬切**，
          段长中位 20.5s —— 比现状（12.2s）**更慢**，而不是更快。
          若真能靠 VAD 切，段数应更多、段长应更短。

  现象 2：纯 VAD-400ms 的空段从 1 个涨到 11 个。
          推测：切完一刀后，下一段仍从同一片静音的**中间**开始累积，
          于是又立刻检出「尾静音」→ 切出一个纯静音段。
          这正是 Qwen3 服务端 VAD 用 `speech_start` 事件解决的
          （服务端把语音起点之前的静音直接丢弃）。

诊断方法
--------
对每个「本该切但没切」的位置，打印：
  * trailing silence 的实际长度
  * guard probe 的 dB（静音起点前 0.35s）
  * 段内语音电平 p90（30ms 帧）
  * 绝对判据 / 相对判据 / 语音准入门槛 各自的结果

→ 定位是「保护期把切点挡了」还是「语音准入门槛把切点挡了」。

用法：
  python diag_seg_qwen3_why.py <wav> [--minutes 61]
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
    from seg_stream import find_trailing_silence

    def db_series(x):
        return L._frame_db_series(x)

    # ── 现象 1 诊断 ──────────────────────────────────────────────
    # 模拟纯 VAD-800ms 的累积过程，记录每个 chunk 后「为什么没切」。
    print('=' * 100)
    print('【现象 1 诊断】纯 VAD-800ms：逐 chunk 记录「未切段」的原因')
    print('=' * 100)

    def trace(hangover, rule1, max_seg, label):
        chunk_n = int(SR * CHUNK_SEC)
        accum = np.zeros(0, dtype=np.float32)
        base = 0
        cursor = 0
        cuts = []
        reasons = Counter()
        block_samples = []
        while True:
            n = accum.shape[0]
            dur = n / SR
            # rule2
            r2 = False
            why = ''
            if n >= int(SR * 0.5):
                win = int(SR * (hangover + L.SILENCE_TAIL_GUARD_SEC + 0.5))
                span = find_trailing_silence(accum, start_sample=max(0, n - win),
                                             end_sample=n, silence_db=L.SILENCE_DB,
                                             min_silence_ms=int(hangover * 1000))
                if span is None:
                    why = 'no_trailing_silence'
                else:
                    sil_start = span[0]
                    g = int(SR * L.SILENCE_TAIL_GUARD_SEC)
                    ps = max(0, sil_start - g)
                    probe = accum[ps:sil_start]
                    if probe.size == 0:
                        why = 'guard_empty'
                    else:
                        rms = float(np.sqrt(np.mean(probe.astype(np.float64) ** 2) + 1e-12))
                        db = 20.0 * float(np.log10(rms + 1e-7))
                        abs_ok = db > L.SILENCE_DB
                        sdb = db_series(accum[:sil_start])
                        speech = float(np.percentile(sdb, 90)) if sdb.size else -999.0
                        gate_ok = speech >= L.GUARD_REL_MIN_SPEECH_DB
                        rel_ok = db > speech - L.GUARD_REL_DROP_DB if gate_ok else False
                        if abs_ok:
                            r2 = True
                            why = 'abs_ok'
                        elif gate_ok and rel_ok:
                            r2 = True
                            why = 'rel_ok'
                        elif not gate_ok:
                            why = f'gate_blocked(speech={speech:.1f})'
                        else:
                            why = f'rel_blocked(db={db:.1f},speech={speech:.1f})'
            if r2:
                cuts.append((base / SR + dur, dur, 'rule2'))
                base += n
                accum = np.zeros(0, dtype=np.float32)
                continue
            if dur >= max_seg:
                cuts.append((base / SR + dur, dur, 'max'))
                base += n
                accum = np.zeros(0, dtype=np.float32)
                continue
            if rule1 and dur >= 12.0:
                from seg_stream import find_silence_in_range
                start = max(0, int((dur - L.SIL_LOOKBACK_SEC) * SR))
                if find_silence_in_range(accum, start_sample=start, end_sample=n,
                                         silence_db=L.SILENCE_DB,
                                         min_silence_ms=300) is not None:
                    cuts.append((base / SR + dur, dur, 'rule1'))
                    base += n
                    accum = np.zeros(0, dtype=np.float32)
                    continue
            reasons[why] += 1
            if cursor >= len(d):
                break
            chunk = d[cursor:cursor + chunk_n]
            cursor += chunk_n
            if chunk.size == 0:
                break
            accum = np.concatenate([accum, chunk]) if accum.size else chunk.copy()
        print(f'\n▶ {label}：段数 {len(cuts)}  '
              f'分布 {dict(Counter(x[2] for x in cuts))}')
        print('   「未切段」原因分布（chunk 级计数）：')
        for k, v in reasons.most_common(8):
            print(f'      {k:<34} {v:>6} 次')
        return cuts

    c_base = trace(1.2, True, 20.0, 'A 现状基线（1.2s + rule1）')
    c_vad = trace(0.8, False, 20.0, 'C 纯VAD-800ms（0.8s，无 rule1）')

    # ── 现象 1 关键分析 ──────────────────────────────────────────
    print()
    print('=' * 100)
    print('【现象 1 归因】为什么纯 VAD 的段长反而更长')
    print('=' * 100)
    hard = [x for x in c_vad if x[2] == 'max']
    print(f'   纯 VAD 的硬切段 {len(hard)} 个 / 共 {len(c_vad)} 段')
    # 取一个硬切段，看它内部所有 ≥0.8s 静音为什么都没触发 rule2
    if hard:
        # 找第 2 个硬切段（跳过开头的）
        tgt = hard[1]
        t0 = tgt[0] - tgt[1]
        seg = d[int(t0 * SR):int(tgt[0] * SR)]
        sdb = db_series(seg)
        print(f'\n   样例硬切段 [{t0:.2f}, {tgt[0]:.2f}] 长 {tgt[1]:.2f}s')
        print(f'      段内 30ms 帧 dB：p10={np.percentile(sdb,10):.1f} '
              f'p50={np.percentile(sdb,50):.1f} p90={np.percentile(sdb,90):.1f} '
              f'max={sdb.max():.1f}')
        # 找出段内所有 ≥0.8s 的静音段
        is_sil = sdb < L.SILENCE_DB
        runs = []
        i = 0
        while i < len(is_sil):
            if is_sil[i]:
                j = i
                while j + 1 < len(is_sil) and is_sil[j + 1]:
                    j += 1
                runs.append((i, j))
                i = j + 1
            else:
                i += 1
        long_runs = [(a, b) for a, b in runs if (b - a + 1) * 10 >= 800]
        print(f'      段内 ≥800ms 的静音段共 {len(long_runs)} 处')
        for a, b in long_runs[:6]:
            # 该静音起点前的 probe
            sil_start_abs = int(t0 * SR) + a * 160
            g = int(SR * L.SILENCE_TAIL_GUARD_SEC)
            ps = max(0, sil_start_abs - g)
            probe = d[ps:sil_start_abs]
            if probe.size == 0:
                print(f'      静音 {a*10/1000:.2f}s~ 起点处 probe 为空')
                continue
            rms = float(np.sqrt(np.mean(probe.astype(np.float64) ** 2) + 1e-12))
            db = 20.0 * float(np.log10(rms + 1e-7))
            segdb = db_series(d[int(t0 * SR):sil_start_abs])
            speech = float(np.percentile(segdb, 90)) if segdb.size else -999.0
            abs_ok = db > L.SILENCE_DB
            gate_ok = speech >= L.GUARD_REL_MIN_SPEECH_DB
            rel_ok = (db > speech - L.GUARD_REL_DROP_DB) if gate_ok else False
            print(f'      静音 @段内{a*10/1000:>6.2f}s 长{(b-a+1)*10/1000:>5.2f}s | '
                  f'probe_db={db:>7.2f} 段内p90={speech:>7.2f} | '
                  f'绝对={"放行" if abs_ok else "拦"} '
                  f'准入={"过" if gate_ok else "拦"} '
                  f'相对={"放行" if rel_ok else "拦"}')

    # ── 现象 2 诊断：空段 ────────────────────────────────────────
    print()
    print('=' * 100)
    print('【现象 2 诊断】纯 VAD-400ms 的空段：从哪来的')
    print('=' * 100)

    def speech_ratio(a, b, thr=-35.0):
        s = int(a * SR)
        e = int(b * SR)
        seg = d[s:e]
        if seg.size == 0:
            return 0.0
        f = db_series(seg)
        return float(np.mean(f > thr)) if f.size else 0.0

    c400 = trace(0.4, False, 20.0, 'D 纯VAD-400ms')
    prev = 0.0
    empties = []
    for x in c400:
        r = speech_ratio(prev, x[0])
        if r < 0.10:
            empties.append((prev, x[0] - prev, r, x[2]))
        prev = x[0]
    print(f'\n   空段 {len(empties)} 个（前 6）：')
    for a, dur, r, kind in empties[:6]:
        # 前一段的结束时刻
        print(f'      [{a:.2f}, {a+dur:.2f}] 长{dur:.2f}s 语音占比{r*100:.1f}% ({kind})')
        # 该空段起始处的尾静音长度
        seg = d[int(a * SR):int((a + dur) * SR)]
        f = db_series(seg)
        is_sil = f < L.SILENCE_DB
        print(f'        段内帧dB: max={f.max():.1f} p90={np.percentile(f,90):.1f} '
              f'全静音={bool(is_sil.all())}')


if __name__ == '__main__':
    main()
