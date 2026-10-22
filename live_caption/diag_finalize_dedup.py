r"""diag_finalize_dedup.py — 验证 _finalize() 是否在重复编码同一段音频

怀疑链条：
  feed() → streaming_transcribe() → generate_with_prefix(state.audio_accum)
         → 最后一个 chunk 处理完，audio_accum 已是**整段音频**
  随后 while seg.due(audio_accum) → _close_segment() → _finalize()
         → generate_with_prefix(st.audio_accum)   ← 同一个数组，再编一次

若成立，则 _finalize 的 encode_audio（实测 68ms，占收尾解码 16%）
是**纯重复计算**，可通过「缓存上一次编码结果」直接省掉。

本脚本做法：
  对比「流式最后一次调用」与「紧随其后的 _finalize」所编码的
  audio_accum 的 (长度, 内容哈希)。并实测缓存命中后能省多少毫秒。

用法：
  python diag_finalize_dedup.py <wav> [--cut 1.2] [--max-seconds N] [--lang English]
"""
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600


def main():
    args = sys.argv[1:]
    wav = args[0]
    cut = 1.2
    max_seconds = 120.0
    lang = 'English'
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--max-seconds' in args:
        max_seconds = float(args[args.index('--max-seconds') + 1])
    if '--lang' in args:
        lang = args[args.index('--lang') + 1]

    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import importlib
    import live_caption_app as L
    importlib.reload(L)

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(max_seconds * sr)]

    eng = L.make_engine('gpu_int8', on_log=lambda m: None, force_language=lang)
    be = eng.backend

    calls = []          # 每次 encode 的 (n_samples, md5)
    in_fin = {'v': False}
    orig_encode = be.encode_audio

    def timed_encode(wav_arr):
        t = time.perf_counter()
        r = orig_encode(wav_arr)
        dt = time.perf_counter() - t
        h = hashlib.md5(np.ascontiguousarray(wav_arr).tobytes()).hexdigest()[:16]
        calls.append(dict(n=int(len(wav_arr)), md5=h, dt=dt, fin=in_fin['v']))
        return r

    be.encode_audio = timed_encode

    orig_finalize = eng._finalize

    def wrapped_finalize():
        in_fin['v'] = True
        try:
            return orig_finalize()
        finally:
            in_fin['v'] = False
    eng._finalize = wrapped_finalize

    fed = 0
    t0 = time.perf_counter()
    for i in range(0, len(d), STEP):
        eng.feed(d[i:i + STEP], time.perf_counter())
        fed += len(d[i:i + STEP])
        if max_seconds and fed / SR >= max_seconds:
            break
    eng.flush()
    wall = time.perf_counter() - t0
    eng.close()

    fin_idx = [i for i, c in enumerate(calls) if c['fin']]
    print(f'\n=== 重复编码验证（cut={cut}s，音频 {fed/SR:.1f}s，墙钟 {wall:.1f}s）===')
    print(f'共 {len(calls)} 次 encode_audio，其中收尾解码 {len(fin_idx)} 次\n', flush=True)

    dup = 0
    save_ms = 0.0
    for i in fin_idx:
        c = calls[i]
        # 找它之前最近一次非 finalize 的调用
        prev = [calls[j] for j in range(max(0, i - 3), i) if not calls[j]['fin']]
        if not prev:
            print(f'  收尾#{i}: 前面没有流式调用可比')
            continue
        p = prev[-1]
        same = (p['md5'] == c['md5'] and p['n'] == c['n'])
        if same:
            dup += 1
            save_ms += c['dt'] * 1000
        print(f'  收尾#{i}: 音频 {c["n"]/SR:5.2f}s md5={c["md5"]} '
              f'编码 {c["dt"]*1000:5.1f}ms  ← 前次流式 {p["n"]/SR:5.2f}s '
              f'md5={p["md5"]}  {"★完全相同（重复！）" if same else "不同"}', flush=True)

    print(f'\n★ {len(fin_idx)} 次收尾中 {dup} 次与紧邻的流式调用编码同一段音频')
    if fin_idx:
        print(f'★ 若缓存复用，平均每次省 '
              f'{save_ms/max(1,len(fin_idx)):.0f}ms（占收尾解码 428ms 的 '
              f'{save_ms/max(1,len(fin_idx))/428*100:.0f}%）')


if __name__ == '__main__':
    main()
