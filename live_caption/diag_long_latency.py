r"""diag_long_latency.py — 长音频（30 分钟）上的定稿延迟分布与尖峰归因

在 120s 短样本上，白字延迟中位 1.66s、最大 5.22s。但短样本切段太少，
尖峰样本量不足，无法判断「最慢的那几段到底为什么慢」。本脚本跑长音频，
把每一段都记下来，重点回答：

  1. 延迟分布长什么样（中位 / p90 / p99 / 最大）
  2. 最慢的那几段，慢在哪个环节：
     · 段尾静音远长于阈值 1.2s → 说明「该切却没切」，要查保护期/静音检测
     · 收尾解码特别慢        → 说明是编码/prefill 随段长增长
     · 段长顶到 20s 硬切     → 说明说话一直没停，属于规则本身
  3. 保护期 `SILENCE_TAIL_GUARD_SEC` 是否在拦切段

延迟口径 = 音频时间轴：
    延迟 = 定稿时的绝对音频位置 − 该段内「最后一次有声音」的绝对位置
（实时场景下音频 1:1 流入，所以这个口径≈用户感知的墙钟延迟）

用法：
  python diag_long_latency.py <wav> [--minutes 30] [--cut 1.2] [--lang English]
                              [--top 12]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600          # 100 ms


def last_voice_sample(x, db_thresh=-40.0, frame_ms=30, hop_ms=10):
    """返回 x 内「最后一段连续语音的结束位置」样本号；全静音返回 0。

    注意不能简单「从前往后扫、记住最后一个非静音帧」—— 段尾只要有一两个
    噪声帧（呼吸、椅子声）就会被当成"最后一句话"，tail_sil 直接变 0，
    看起来像"说完立刻就定稿"，把真实的静音等待全部掩盖掉。

    正确做法：**从末尾往前跳过尾部静音**，遇到第一个语音帧即为最后一句
    的收尾，返回它的结束位置。这样 tail_sil 才是「说完之后等了多久」。
    """
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if x.shape[0] < n:
        return 0
    nf = max(0, (x.shape[0] - n) // h + 1)
    if nf == 0:
        return 0
    db = np.empty(nf, dtype=np.float32)
    for i in range(nf):
        s = i * h
        seg = x[s:s + n]
        rms = float(np.sqrt(np.mean(seg.astype(np.float64) ** 2) + 1e-12))
        db[i] = 20.0 * np.log10(rms + 1e-7)
    i = nf - 1
    while i >= 0 and db[i] <= db_thresh:
        i -= 1
    if i < 0:
        return 0                     # 整段都是静音
    return min(x.shape[0], (i + 1) * h + n)


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 30.0
    cut = 1.2
    lang = 'English'
    top_n = 12
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--lang' in args:
        lang = args[args.index('--lang') + 1]
    if '--top' in args:
        top_n = int(args[args.index('--top') + 1])

    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import importlib
    import live_caption_app as L
    importlib.reload(L)

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    total_s = min(minutes * 60.0, len(d) / SR)
    d = d[:int(total_s * sr)]

    print(f'音频 {os.path.basename(wav)}  截取 {total_s/60:.1f} 分钟  '
          f'cut={cut}s  lang={lang}', flush=True)

    eng = L.make_engine('gpu_int8', on_log=lambda m: None, force_language=lang)
    guard_s = L.SILENCE_TAIL_GUARD_SEC
    min_seg, max_seg = L.MIN_SEG_SEC, L.MAX_SEG_SEC

    records = []
    fed = {'n': 0}
    orig_close = eng._close_segment

    def traced_close():
        st = eng.state
        accum = st.audio_accum
        seg_len = accum.shape[0] / SR
        lv = last_voice_sample(accum)
        tail_sil = (accum.shape[0] - lv) / SR
        # 未解码残余：state.buffer 里还没凑满一个 chunk 的音频。
        # 注意不能用 fed['n'] - accum.shape[0] —— 段 reset 后 accum 从 0 重新
        # 累积，那样算出来的是「之前所有段的总长」，会得到几十秒的假延迟。
        buffer_s = (st.buffer.shape[0] / SR) if st.buffer is not None else 0.0

        # 复现保护期判定（看它是不是在拦切段）
        guard_db = None
        try:
            from seg_stream import find_trailing_silence
            win = int(SR * (cut + guard_s + 0.5))
            start = max(0, accum.shape[0] - win)
            span = find_trailing_silence(
                accum, start_sample=start, end_sample=accum.shape[0],
                silence_db=-40.0, min_silence_ms=int(cut * 1000))
            if span:
                sil_start = span[0]
                ps = max(0, sil_start - int(SR * guard_s))
                probe = accum[ps:sil_start]
                if probe.size:
                    rms = float(np.sqrt(np.mean(probe.astype(np.float64) ** 2) + 1e-12))
                    guard_db = 20.0 * np.log10(rms + 1e-7)
        except Exception:
            pass

        t0 = time.perf_counter()
        out = orig_close()
        dur = time.perf_counter() - t0

        wait = (accum.shape[0] - lv) / SR + buffer_s
        records.append(dict(
            seg_len=seg_len, tail_sil=tail_sil, buffer_s=buffer_s,
            latency_cut=wait,                 # 切段判定前已等（尾部静音 + 残余）
            finalize_ms=dur * 1000,
            latency_user=wait + dur,          # 用户看到白字时已过
            abs_close=fed['n'] / SR,
            guard_db=guard_db, text=(out or '')[:70],
        ))
        return out

    eng._close_segment = traced_close

    t_start = time.perf_counter()
    n_step = len(d) // STEP
    next_report = 0.1
    for i in range(0, len(d), STEP):
        chunk = d[i:i + STEP]
        fed['n'] += len(chunk)
        eng.feed(chunk, time.perf_counter())
        frac = fed['n'] / SR / total_s
        if frac >= next_report:
            print(f'  进度 {frac*100:4.0f}%  音频 {fed["n"]/SR/60:5.1f} 分钟  '
                  f'已切 {len(records)} 段  墙钟 {(time.perf_counter()-t_start)/60:.1f} 分钟',
                  flush=True)
            next_report += 0.1
    fed_tail = eng.flush()
    wall = time.perf_counter() - t_start
    eng.close()

    if not records:
        print('没有切段')
        return

    lat = np.array([r['latency_user'] for r in records])
    latc = np.array([r['latency_cut'] for r in records])
    seg = np.array([r['seg_len'] for r in records])
    sil = np.array([r['tail_sil'] for r in records])
    fin = np.array([r['finalize_ms'] for r in records])
    buf = np.array([r['buffer_s'] for r in records])

    print(f'\n{"="*74}')
    print(f'共切段 {len(records)} 段，音频 {total_s/60:.1f} 分钟，墙钟 {wall/60:.1f} 分钟')
    print(f'（实时率 RTF = {wall/total_s:.2f}）')
    print(f'阈值 cut={cut}s，12s 下限={min_seg}s，20s 硬切={max_seg}s\n')

    # 关键区分：段尾静音 >= cut 才是「用户已经停下」的切段（有真实等待）；
    # 若段尾静音 < cut，说明是规则1（12s 下限）触发，用户其实还在说话 —— 不算等待。
    user_stop = sil >= cut
    print(f'静音超时切段（用户已停）：{int(user_stop.sum())} 段  '
          f'({user_stop.mean()*100:.0f}%)  ← 这些才产生「等白字」的体感')
    print(f'规则1/硬切（用户还在说）：{int((~user_stop).sum())} 段  '
          f'({(~user_stop).mean()*100:.0f}%)  ← 不构成等待，只是切段节奏\n')

    print('用户感知延迟（说完 → 白字出现 = 尾部静音 + 未解码残余 + 收尾解码）：')
    for name, q in [('中位', 50), ('p75', 75), ('p90', 90), ('p95', 95),
                    ('p99', 99), ('最大', 100), ('均值', 0)]:
        val = lat.mean() if q == 0 else np.percentile(lat, q)
        print(f'  {name:5s} {val:6.2f}s')

    if user_stop.any():
        us = lat[user_stop]
        print(f'\n只看「用户已停」的 {len(us)} 段：')
        for name, q in [('中位', 50), ('p90', 90), ('p99', 99), ('最大', 100)]:
            print(f'  {name:5s} {np.percentile(us, q):6.2f}s')

    print(f'\n延迟恒等式自检：尾部静音(中位 {np.median(sil):.2f}s) + '
          f'未解码残余(中位 {np.median(buf):.2f}s) + 收尾(中位 {np.median(fin)/1000:.2f}s) '
          f'= {np.median(sil)+np.median(buf)+np.median(fin)/1000:.2f}s')
    print(f'切段判定前等待（不含收尾）：中位 {np.median(latc):.2f}s  最大 {latc.max():.2f}s')
    print(f'段长：中位 {np.median(seg):.1f}s 最大 {seg.max():.1f}s  '
          f'≥{max_seg:.0f}s硬切 {int((seg>=max_seg-0.7).sum())} 段')
    print(f'收尾解码：中位 {np.median(fin):.0f}ms 最大 {fin.max():.0f}ms')

    # ── 最慢的 N 段 ──
    order = np.argsort(-lat)[:top_n]
    print(f'\n{"="*74}')
    print(f'最慢的 {len(order)} 段逐段归因')
    print(f'{"序":>3} {"总延迟":>7} {"尾静音":>7} {"残余":>6} {"收尾":>7} {"段长":>6} {"保护":>7}  判定')
    print('-' * 74)
    for rank, idx in enumerate(order, 1):
        r = records[idx]
        if r['seg_len'] >= max_seg - 0.7:
            cause = 'MAX_SEG 硬切（说话没停）'
        elif r['tail_sil'] >= cut * 2:
            cause = f'★★ 尾静音 {r["tail_sil"]:.1f}s 远超阈值 → 该切未切'
        elif r['tail_sil'] >= cut:
            cause = '正常（走静音超时）'
        elif r['finalize_ms'] > 800:
            cause = '收尾解码特别慢'
        else:
            cause = '规则1 切段（用户没停）'
        g = '—' if r['guard_db'] is None else f'{r["guard_db"]:.0f}dB'
        print(f'{rank:3d} {r["latency_user"]:6.2f}s {r["tail_sil"]:6.2f}s '
              f'{r["buffer_s"]:5.2f}s {r["finalize_ms"]:6.0f}ms {r["seg_len"]:5.1f}s '
              f'{g:>7}  {cause}')
        if r['text']:
            print(f'      文本: {r["text"]!r}')

    # ── 尖峰归因汇总 ──
    print(f'\n{"="*74}')
    thresh = 2.0
    slow = [r for r in records if r['latency_user'] > thresh]
    print(f'总延迟 > {thresh:.0f}s 的段：{len(slow)} / {len(records)} '
          f'（{len(slow)/len(records)*100:.0f}%）')
    buckets = {'硬切(用户没停)': 0, '该切未切': 0, '收尾慢': 0, '其他': 0}
    for r in slow:
        if r['seg_len'] >= max_seg - 0.7:
            buckets['硬切(用户没停)'] += 1
        elif r['tail_sil'] >= cut * 2:
            buckets['该切未切'] += 1
        elif r['finalize_ms'] > 800:
            buckets['收尾慢'] += 1
        else:
            buckets['其他'] += 1
    for k, v in buckets.items():
        print(f'    {k:14s} {v:4d} 段  ({v/max(1,len(slow))*100:3.0f}%)')

    blocked = [r for r in records if r['guard_db'] is not None and r['guard_db'] <= -40.0]
    print(f'\n保护期检查失败（probe ≤ -40dB，会拦住切段）：{len(blocked)} / {len(records)} 段')
    for r in blocked[:5]:
        print(f'    尾静音 {r["tail_sil"]:.2f}s  probe {r["guard_db"]:.1f}dB  '
              f'段长 {r["seg_len"]:.1f}s  总延迟 {r["latency_user"]:.2f}s')


if __name__ == '__main__':
    main()
