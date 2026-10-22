r"""diag_rule2_trace.py — 逐次 feed 追踪「规则2（静音超时）为什么没触发」

背景
----
C-104 结论：30 分钟样本里 146 段只有 5 段（3%）走规则2，141 段走规则1
（12s 下限），说明「静音超时切段」这条规则几乎没起作用。

但离线能量分析（diag_guard_energy.py）测出：静音起点前 0.35s 的 probe
能量中位 **-24.6dB**，远高于保护期的 -40dB 阈值 → 保护期**不应该**拦截。
两者矛盾。

本脚本不推断，直接在**真实引擎路径**上逐次记录：
  * 每次 feed() 后，段尾连续静音的实际长度（find_trailing_silence 的真实返回值）
  * 保护期 probe 的真实 dB
  * 规则2 的三个前置条件分别是否满足
  * 最终是规则1 还是规则2 触发切段

这样能定位「到底卡在哪一环」。

用法：
  python diag_rule2_trace.py <wav> [--minutes 10] [--cut 1.2] [--lang English]
                              [--dump out.json]
"""

from __future__ import annotations

import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600          # 100 ms 喂入粒度


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 10.0
    cut = 1.2
    lang = 'English'
    dump = None
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--lang' in args:
        lang = args[args.index('--lang') + 1]
    if '--dump' in args:
        dump = args[args.index('--dump') + 1]

    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import importlib
    import live_caption_app as L
    importlib.reload(L)
    from seg_stream import find_trailing_silence

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    total_s = min(minutes * 60.0, len(d) / sr)
    d = d[:int(total_s * sr)]

    print(f'音频 {os.path.basename(wav)}  {total_s/60:.1f} 分钟  cut={cut}s  lang={lang}',
          flush=True)

    eng = L.make_engine('gpu_int8', on_log=lambda m: None, force_language=lang)
    seg = eng.seg
    guard_s = L.SILENCE_TAIL_GUARD_SEC
    sil_db = L.SILENCE_DB
    min_seg = L.MIN_SEG_SEC
    max_seg = L.MAX_SEG_SEC

    # ── 记录每次 feed 后的尾静音与保护期状态 ──
    traces = []          # 每个 feed 一次
    cuts = []            # 每次切段一条
    pending = []         # 等待归因的 feed 轨迹（自上次切段起）

    def probe_state(acc):
        """复现 _silence_tail 的内部计算，返回诊断字典。"""
        n = acc.shape[0]
        out = dict(n=n, dur=n / SR, span=None, tail_sil=0.0,
                   probe_db=None, guard_ok=False, too_short=False)
        if n < int(SR * 0.5):
            out['too_short'] = True
            return out
        win = int(SR * (cut + guard_s + 0.5))
        start = max(0, n - win)
        span = find_trailing_silence(acc, start_sample=start, end_sample=n,
                                     silence_db=sil_db,
                                     min_silence_ms=int(cut * 1000))
        out['span'] = span is not None
        if span is None:
            return out
        sil_start, _ = span
        out['tail_sil'] = (n - sil_start) / SR
        g = int(SR * guard_s)
        ps = max(0, sil_start - g)
        probe = acc[ps:sil_start]
        if probe.size == 0:
            return out
        rms = float(np.sqrt(np.mean(probe.astype(np.float64) ** 2) + 1e-12))
        db = 20.0 * np.log10(rms + 1e-7)
        out['probe_db'] = db
        out['guard_ok'] = db > sil_db
        return out

    # 包裹 due()，记录触发规则
    orig_due = seg.due

    def traced_due(acc):
        st = probe_state(acc)
        # 复现规则1判定
        rule1 = False
        if st['dur'] >= min_seg and not st['too_short']:
            s = max(0, int((st['dur'] - L.SIL_LOOKBACK_SEC) * SR))
            rule1 = seg._find(acc, start_sample=s, end_sample=acc.shape[0],
                              silence_db=-40.0, min_silence_ms=300) is not None
        r2 = orig_due(acc)
        st['rule1'] = rule1
        st['rule2'] = bool(r2)
        st['dur_before'] = st['dur']
        traces.append(st)
        pending.append(st)
        return r2

    seg.due = traced_due

    # 包裹 _close_segment，归因
    orig_close = eng._close_segment

    def traced_close():
        # 归因：看是规则2 还是规则1 触发的（取最后一次 feed 的状态）
        last = pending[-1] if pending else {}
        info = dict(
            seg_len=last.get('dur', 0.0),
            tail_sil=last.get('tail_sil', 0.0),
            probe_db=last.get('probe_db'),
            guard_ok=last.get('guard_ok'),
            span=last.get('span'),
            rule1=last.get('rule1'),
            rule2=last.get('rule2'),
            n_feeds=len(pending),
        )
        # 找到「最后一次满足 tail_sil>=cut」的 feed 及其后第一次不满足
        first_ok = None
        for t in pending:
            if t.get('tail_sil', 0.0) >= cut:
                first_ok = t
                break
        info['first_tail_ok_dur'] = first_ok['dur'] if first_ok else None
        info['first_tail_ok_probe'] = first_ok.get('probe_db') if first_ok else None
        # 首次满足尾静音时，规则2 为什么没触发？
        if first_ok is not None:
            info['block_reason'] = (
                '保护期拦截' if not first_ok.get('guard_ok')
                else ('规则1已先触发' if first_ok.get('rule1') else '?')
            )
        t0 = time.perf_counter()
        out = orig_close()
        info['finalize_ms'] = (time.perf_counter() - t0) * 1000
        info['text'] = (out or '')[:70]
        cuts.append(info)
        pending.clear()
        return out

    eng._close_segment = traced_close

    t_start = time.perf_counter()
    for i in range(0, len(d), STEP):
        eng.feed(d[i:i + STEP], time.perf_counter())
        frac = (i + STEP) / SR / total_s
        if int(frac * 100) % 10 == 0 and frac * 100 % 10 < 1:
            print(f'  进度 {frac*100:4.0f}%  已切 {len(cuts)} 段  '
                  f'墙钟 {(time.perf_counter()-t_start)/60:.1f} 分钟', flush=True)
    eng.flush()
    wall = time.perf_counter() - t_start
    eng.close()

    print(f'\n{"="*74}')
    print(f'切段 {len(cuts)} 段，墙钟 {wall/60:.1f} 分钟（RTF {wall/total_s:.2f}）')
    print(f'喂入次数 {len(traces)}\n')

    # ── 统计：每个 feed 时，尾静音是否已达到 cut ──
    tail_ok = [t for t in traces if t.get('tail_sil', 0.0) >= cut]
    guard_block = [t for t in tail_ok if not t.get('guard_ok')]
    span_missing = [t for t in traces
                    if not t.get('span') and not t.get('too_short')
                    and t.get('dur', 0) > 1.0]

    print('── 逐次 feed 的规则2 可行性 ──')
    print(f'  尾静音 ≥ {cut}s 的 feed 次数：        {len(tail_ok)}')
    print(f'    其中保护期拦截（probe ≤ {sil_db}dB）：{len(guard_block)}')
    print(f'  有语音但找不到尾静音段的 feed：        {len(span_missing)}')
    print(f'  规则2 实际触发次数（due 返回 True）：  '
          f'{sum(1 for t in traces if t.get("rule2"))}')

    if tail_ok:
        pd = np.array([t['probe_db'] for t in tail_ok
                       if t.get('probe_db') is not None])
        ts = np.array([t['tail_sil'] for t in tail_ok])
        if pd.size:
            print(f'\n  尾静音达标时的 probe dB：中位 {np.median(pd):.1f}  '
                  f'p10 {np.percentile(pd,10):.1f}  p90 {np.percentile(pd,90):.1f}  '
                  f'min {pd.min():.1f}')
        print(f'  尾静音时长：中位 {np.median(ts):.2f}s  max {ts.max():.2f}s')

    # ── 切段归因 ──
    print(f'\n── 切段归因（{len(cuts)} 段）──')
    reasons = {}
    for c in cuts:
        r = c.get('block_reason') or '规则2 直接触发'
        reasons[r] = reasons.get(r, 0) + 1
    for k, v in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f'  {k:22s} {v:4d} 段')

    # 展示前若干段的详细轨迹
    print(f'\n── 前 12 段的详细轨迹 ──')
    for i, c in enumerate(cuts[:12], 1):
        pd = c['probe_db']
        pds = '—' if pd is None else f'{pd:.1f}dB'
        gok = '通' if c['guard_ok'] else '拦'
        ftd = c['first_tail_ok_dur']
        fts = '—' if ftd is None else f'{ftd:.1f}s'
        print(f'[{i:2d}] 段长 {c["seg_len"]:5.1f}s  尾静音 {c["tail_sil"]:5.2f}s  '
              f'probe {pds:>8}  保护期{gok}  '
              f'rule1={c["rule1"]} rule2={c["rule2"]}  首达尾静音于段长 {fts}')

    if dump:
        with open(dump, 'w', encoding='utf-8') as f:
            json.dump(dict(cuts=cuts, n_traces=len(traces)), f,
                      ensure_ascii=False, indent=1)
        print(f'\n已落盘 {dump}')


if __name__ == '__main__':
    main()
