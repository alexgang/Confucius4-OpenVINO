r"""diag_finalize_cost.py — 拆解 _finalize() 收尾解码的耗时构成

_finalize() 做三件事，本脚本分别计时：
  1. encode_audio()            整段 audio_accum 重新编码（补零到 MAX_FRAMES=2400 帧）
  2. prefill                   把 [prompt + audio_pad*N + prefix] 灌进 decoder
  3. 逐 token 解码              最多 64 步（遇 EOS 提前停）

要回答的问题：
  · 这 64 token 的预算实际用掉了多少？如果每次都跑满 64，说明预算给大了。
  · 编码 vs 解码各占多少？如果编码是大头，那「减少编码量」比「减 token」更有效。
  · 收尾解码在整段耗时里的占比（对照 feed() 的总时间）。

用法：
  python diag_finalize_cost.py <wav> [--cut 1.2] [--max-seconds N] [--lang English]
"""
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

    # ── 给 backend 的两个关键方法装计时器 ──
    # 注意：generate_with_prefix 同时被「流式解码」和「_finalize 收尾解码」
    # 调 用，必须分开统计 —— 否则算出来的"收尾开销"里混进了流式开销。
    # 判别方法：_finalize 传的 max_new_tokens 是 64，流式传的是自适应预算(1~32)。
    stats = dict(encode=[], prefill=[], n_tokens=[], decode=[])
    fin_stats = dict(encode=[], prefill=[], n_tokens=[], decode=[])
    orig_encode = be.encode_audio
    orig_greedy = be.greedy_decode_with_prefix
    in_finalize = {'v': False}
    cur = {'bucket': stats}

    def timed_encode(wav_arr):
        t = time.perf_counter()
        r = orig_encode(wav_arr)
        cur['bucket']['encode'].append((time.perf_counter() - t, len(wav_arr) / SR))
        return r

    def timed_greedy(ehs, prefix_ids, max_new_tokens, force_language=None):
        b = cur['bucket']
        # 复刻 greedy_decode_with_prefix，但要分段计时
        t_pre_start = time.perf_counter()
        be.dec_infer.reset_state()
        if force_language:
            ids_left, ids_right = be._build_prompt_template_ids_for(force_language)
        else:
            ids_left, ids_right = be._prompt_template_ids
        N_audio = ehs.shape[1]
        full_ids = ids_left + [be._audio_pad_id] * N_audio + ids_right + list(prefix_ids)
        input_ids = np.array([full_ids], dtype=np.int64)
        out = be.dec_infer.infer({
            "input_ids": input_ids,
            "encoder_hidden_states": ehs,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        next_id = int(np.argmax(logits[0, -1, :]))
        b['prefill'].append(time.perf_counter() - t_pre_start)

        generated = [next_id]
        eos_ids = {151643, 151645, be.tokenizer.eos_token_id}
        tok_t = []
        for _ in range(max_new_tokens - 1):
            if next_id in eos_ids:
                break
            t1 = time.perf_counter()
            out = be.dec_infer.infer({
                "input_ids": np.array([[next_id]], dtype=np.int64),
                "beam_idx": np.array([0], dtype=np.int32),
            }, share_inputs=True)
            logits = out["logits"] if isinstance(out, dict) else out[0]
            next_id = int(np.argmax(logits[0, -1, :]))
            tok_t.append(time.perf_counter() - t1)
            generated.append(next_id)
        if tok_t:
            b['decode'].append(sum(tok_t) / len(tok_t))
        b['n_tokens'].append(len(generated))
        return generated

    be.encode_audio = timed_encode
    be.greedy_decode_with_prefix = timed_greedy

    # 包住 _finalize，把这段期间的计时归到 fin_stats
    orig_finalize = eng._finalize

    def timed_finalize():
        cur['bucket'] = fin_stats
        try:
            return orig_finalize()
        finally:
            cur['bucket'] = stats
    eng._finalize = timed_finalize

    # ── 跑音频，同时记录每次 feed 的耗时 ──
    feed_times = []
    n_seg = 0
    t0 = time.perf_counter()
    fed = 0
    for i in range(0, len(d), STEP):
        t = time.perf_counter()
        r = eng.feed(d[i:i + STEP], time.perf_counter())
        feed_times.append((time.perf_counter() - t, 1 if r else 0))
        if r:
            n_seg += 1
        fed += len(d[i:i + STEP])
        if max_seconds and fed / SR >= max_seconds:
            break
    eng.flush()
    wall = time.perf_counter() - t0
    eng.close()

    print(f'\n=== _finalize() 耗时拆解（cut={cut}s，音频 {fed/SR:.1f}s，墙钟 {wall:.1f}s）===')
    print(f'切段 {n_seg} 次；流式解码调用 {len(stats["encode"])} 次，'
          f'收尾解码调用 {len(fin_stats["encode"])} 次\n', flush=True)

    if not fin_stats['encode']:
        print('没有切段，无法统计收尾开销')
        return

    def report(tag, st):
        if not st['encode']:
            return None
        enc = np.array([t for t, _ in st['encode']])
        enc_len = np.array([l for _, l in st['encode']])
        pre = np.array(st['prefill'])
        ntok = np.array(st['n_tokens'])
        dectok = np.array(st['decode']) if st['decode'] else np.array([0.0])
        n = min(len(dectok), len(ntok))
        dec_tot = float(np.sum(dectok[:n] * ntok[:n]))
        tot = enc.sum() + pre.sum() + dec_tot
        print(f'── {tag}（{len(enc)} 次）──')
        print(f'  ① 编码  {enc.sum():6.2f}s  平均 {enc.mean()*1000:5.0f}ms  '
              f'（音频均值 {enc_len.mean():.1f}s，补零到 2400 帧）')
        print(f'  ② prefill {pre.sum():6.2f}s  平均 {pre.mean()*1000:5.0f}ms')
        print(f'  ③ 解码  {dec_tot:6.2f}s  平均 {dectok.mean()*1000:5.1f}ms/token，'
              f'生成 {ntok.mean():.1f} token（预算 64，利用率 {ntok.mean()/64*100:.0f}%）')
        print(f'  合计   {tot:6.2f}s  平均 {tot/len(enc)*1000:.0f}ms 每次')
        print(f'  占比：编码 {enc.sum()/tot*100:.0f}% / '
              f'prefill {pre.sum()/tot*100:.0f}% / 解码 {dec_tot/tot*100:.0f}%\n')
        return tot

    tot_s = report('流式解码（对照）', stats)
    tot_f = report('★ 收尾解码 _finalize', fin_stats)

    if tot_s and tot_f:
        print(f'★ 收尾解码累计 {tot_f:.2f}s，占墙钟 {tot_f/wall*100:.1f}%')
        print(f'★ 平均每次收尾解码 {tot_f/len(fin_stats["encode"])*1000:.0f}ms'
              f'  ← 白字出现前要多等这段')
        print(f'★ 相对流式单次（{tot_s/len(stats["encode"])*1000:.0f}ms）'
              f'贵 {tot_f/len(fin_stats["encode"])/(tot_s/len(stats["encode"])):.2f} 倍')


if __name__ == '__main__':
    main()
