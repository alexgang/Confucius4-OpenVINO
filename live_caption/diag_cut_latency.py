r"""diag_cut_latency.py — 精确测「说话结束 → 定稿」的延迟随阈值的变化

上一版 diag_final_delay.py 用「喂语音再喂静音」的方式测，测的是
「语音后接静音」这种理想情况。真实会议音频里，句子之间只有几百毫秒
到 1 秒的自然停顿，且停顿长度各异 —— 阈值改一点点，
「等多久才判定为说完了」的差别会被放大。

本脚本用**真实会议音频**：
  1. 先用能量 VAD 找出所有「停顿 ≥ 0.4s」的位置（当说话结束点）
  2. 对每个停顿点，模拟「到这里停止喂音频」，测定稿延迟
     —— 但这是多次重跑，太慢。

改成更实际的方案：跑一遍完整音频，记录**每次定稿发生在音频的哪个
时刻**（音频时间轴，不是墙钟），再对照 VAD 检出的停顿点，
算出「最后一次说话 → 第一次定稿」的音频时间差。

用法：
  python diag_cut_latency.py <wav> [--cuts 0.8,1.0,1.2] [--max-seconds N]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600          # 100 ms


def frame_rms(x, frame_ms=30, hop_ms=10):
    n = int(frame_ms * SR / 1000)
    h = int(hop_ms * SR / 1000)
    if x.shape[0] < n:
        x = np.concatenate([x, np.zeros(n - x.shape[0], dtype=np.float32)])
    nf = max(0, (x.shape[0] - n) // h + 1)
    out = np.zeros(nf, dtype=np.float32)
    for i in range(nf):
        s = i * h
        out[i] = float(np.sqrt(np.mean(x[s:s + n] ** 2) + 1e-12))
    return out


def find_pauses(x, db_thresh=-40.0, min_pause_ms=400, frame_ms=30, hop_ms=10):
    """找所有「静音段」，返回 [(起, 止) 秒]。"""
    rms = frame_rms(x, frame_ms, hop_ms)
    db = 20 * np.log10(rms + 1e-7)
    is_sil = db < db_thresh
    hop_s = hop_ms / 1000.0
    out = []
    i = 0
    n = is_sil.shape[0]
    while i < n:
        if is_sil[i]:
            j = i
            while j < n and is_sil[j]:
                j += 1
            if (j - i) * hop_s * 1000 >= min_pause_ms:
                out.append((i * hop_s, j * hop_s))
            i = j
        else:
            i += 1
    return out


def main():
    args = sys.argv[1:]
    wav = args[0]
    cuts = [1.2]
    max_seconds = 0.0
    if '--cuts' in args:
        cuts = [float(x) for x in args[args.index('--cuts') + 1].split(',')]
    if '--max-seconds' in args:
        max_seconds = float(args[args.index('--max-seconds') + 1])

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    if max_seconds:
        d = d[:int(max_seconds * sr)]

    pauses = find_pauses(d)
    print(f'音频 {os.path.basename(wav)} {len(d)/SR:.1f}s  '
          f'检出 {len(pauses)} 处 ≥400ms 停顿', flush=True)
    for k, (a, b) in enumerate(pauses[:12]):
        print(f'   停顿{k}: {a:.2f}s ~ {b:.2f}s  (长 {b-a:.2f}s)', flush=True)

    import live_caption_app as L
    import importlib

    for cut in cuts:
        os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
        importlib.reload(L)
        eng = L.make_engine('gpu_int8', on_log=lambda m: None)

        # 记录每段定稿时，**已喂入的音频总长**是多少秒
        events = []      # (音频秒, 墙钟秒)
        fed_samples = 0
        t0 = time.perf_counter()
        for i in range(0, len(d), STEP):
            chunk = d[i:i + STEP]
            r = eng.feed(chunk, time.perf_counter())
            fed_samples += len(chunk)
            if r:
                events.append((fed_samples / SR, time.perf_counter() - t0))
        tail = eng.flush()
        if tail:
            events.append((fed_samples / SR, time.perf_counter() - t0))
        eng.close()

        print(f'\n=== cut={cut}s ===', flush=True)
        print(f'  定稿 {len(events)} 次', flush=True)
        # 每段定稿点离「最近一次停顿结束」有多远 —— 这就是实感延迟
        lags = []
        for k, (a_sec, w_sec) in enumerate(events):
            # 找最后一个结束的、且结束时刻 ≤ a_sec 的停顿
            prev = [p for p in pauses if p[1] <= a_sec + 0.01]
            if not prev:
                continue
            lag = a_sec - prev[-1][1]
            lags.append(lag)
            if k < 6:
                print(f'   定稿{k}: 音频{a_sec:6.2f}s  '
                      f'停顿结束于{prev[-1][1]:6.2f}s  延迟 {lag:.2f}s', flush=True)
        if lags:
            arr = np.array(lags)
            print(f'  ★ 停顿结束→定稿：均值 {arr.mean():.2f}s  '
                  f'中位 {np.median(arr):.2f}s  最大 {arr.max():.2f}s', flush=True)
        print(f'  墙钟总耗时 {time.perf_counter()-t0:.1f}s', flush=True)


if __name__ == '__main__':
    main()
