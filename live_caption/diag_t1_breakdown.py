r"""diag_t1_breakdown.py — 拆开「说话结束 → 定稿」的每一段耗时

要回答的问题：T1 定稿延迟里，除了「静音阈值」之外还有多少是**固定开销**？
固定开销决定了「把静音阈值降到 0」能省多少，省不动的那部分才是真瓶颈。

时间轴（采样点）：
  t_speech_end   语音结束的判定（用能量粗判，仅作参考）
  t_due          Segmenter.due() 首次返回 True 的时刻
  t_finalize_end _finalize() 返回（= 定稿文本产出）

差值：
  Δ1 = t_due - t_speech_end   → 静音阈值 + 判定余量（阈值可压缩）
  Δ2 = t_finalize_end - t_due  → 收尾解码固定开销（阈值降不了）

用法：
  python diag_t1_breakdown.py <wav> [--cut 1.2] [--max-seconds N]

注意：音频必须**长于 MIN_SEG_SEC（12 s）**且段尾有 ≥ cut 秒静音，否则
Segmenter.due() 始终返回 False、时间线会是空的（flush() 走的是另一条
路径，不经过 _close_segment）。AISHELL 单句最长约 8 s，直接喂会看到
「零时间线」——那是前提不满足，不是脚本坏了。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600          # 100 ms


def main():
    args = sys.argv[1:]
    wav = args[0]
    cut = 1.2
    max_seconds = 0.0
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--max-seconds' in args:
        max_seconds = float(args[args.index('--max-seconds') + 1])

    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import live_caption_app as L
    import importlib
    importlib.reload(L)

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    if max_seconds:
        d = d[:int(max_seconds * sr)]

    eng = L.make_engine('gpu_int8', on_log=lambda m: None)

    # 记录每一段的「due 判定时刻」与「finalize 完成时刻」
    timeline = []
    orig_due = eng.seg.due
    orig_close = eng._close_segment

    def traced_due(acc):
        r = orig_due(acc)
        if r:
            timeline.append(dict(due_at=time.perf_counter()))
        return r

    def traced_close():
        t0 = time.perf_counter()
        out = orig_close()
        if timeline:
            timeline[-1]['close_start'] = t0
            timeline[-1]['close_end'] = time.perf_counter()
            timeline[-1]['text'] = out
        return out

    eng.seg.due = traced_due
    eng._close_segment = traced_close

    t0 = time.perf_counter()
    fed = 0
    for i in range(0, len(d), STEP):
        chunk = d[i:i + STEP]
        eng.feed(chunk, time.perf_counter())
        fed += len(chunk)
        if max_seconds and fed / SR >= max_seconds:
            break
    eng.flush()
    wall = time.perf_counter() - t0

    print(f'\n=== T1 耗时分解（cut={cut}s，音频 {len(d)/SR:.1f}s，墙钟 {wall:.1f}s）===', flush=True)
    for i, tl in enumerate(timeline):
        close_dur = tl['close_end'] - tl['close_start']
        # 距上一段定稿的间隔 = 这一段里语音长度 + 静音等待
        print(f'  [{i}] 定稿@{tl["close_end"]-t0:6.1f}s  '
              f'收尾解码耗时={close_dur:5.2f}s  '
              f'文本={"..." if not tl.get("text") else tl["text"][:60]!r}', flush=True)

    if timeline:
        closes = [tl['close_end'] - t0 for tl in timeline]
        durs = [tl['close_end'] - tl['close_start'] for tl in timeline]
        print(f'\n  收尾解码平均 {np.mean(durs):.2f}s / 最大 {np.max(durs):.2f}s', flush=True)
        print(f'  段间隔（相邻定稿时刻之差）中位 {np.median(np.diff(closes)):.2f}s', flush=True)
        print(f'  → 收尾解码占总墙钟 {100*np.sum(durs)/wall:.1f}%', flush=True)
    eng.close()


if __name__ == '__main__':
    main()
