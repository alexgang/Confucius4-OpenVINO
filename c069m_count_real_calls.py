"""c069m_count_real_calls.py — C-069：实测流式循环里 decoder 的真实调用画像

## 为什么必须先做这一步

`c069l` 的 RTF 外推用了 `AVG_OUT_TOK = 65`，但实际 ABBA 显示每段 wall 约 9524 ms，
与该估计差约 4.4 倍。原因有两个，都必须先量出来才能谈"方案 B 能否端到端"：

1. **每 chunk 都会重新 prefill 整条 prompt**，不是只喂 1 个 token。
   `seg_stream._run_one_segment` 以 40 ms 步长喂音频，`streaming_asr` 每凑满一个
   `chunk_size_sec`（640 ms）就调一次 `generate_with_prefix`，而
   `segment_encoder_backend.greedy_decode_with_prefix` 每次都 `reset_state()` +
   全量 prefill。→ 每段的 prefill 次数 = `n_chunks`，不是 1。

2. **生成预算上限 64**，中间 chunk 还用自适应预算。实际生成 token 数决定 decode 步数。

所以方案 B（无 KV cache）的成本不是 `n_chunks × 30 ms`，而是
`n_chunks × (整条 prompt 的全序列 forward)` —— 这才是当前方案 B 慢的本质，
也是 c069i / c069l 外推错得离谱的根因。

## 本脚本只做计数 + 分项计时，不做方案 B 端到端

用**生产**路径（`models/ov-fp16-past`：stateful FP16 encoder + INT8 decoder），
跑 12–27 分钟切片的前 N 段，用 wrapper 分项计时并输出真实画像。

输出：`reports/c069m_real_call_profile.json`
"""
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
# C-069 铁律：计时子进程禁止 import torch（transformers 会顺带加载 torch）
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer, _make_segment_state

AUDIO = 'test_audio/<redacted>.wav'
SR = 16000
SLICE_START_SEC = 12 * 60
SLICE_END_SEC = 27 * 60
CHUNK_SEC = 0.64

N_SEGS = 8
# 与 C-062 ABBA 的配置 A 完全一致（交付基线），这样本报告的分项耗时可直接
# 与 reports/c062_abba/summary.json 的 RTF 对齐。
# 注意：不能用 models/ov-fp16-past —— 那是**单输入** Encoder IR
#（input_features），而 SegmentEncoderOVBackend.encode_audio 传的是
# [enc_in, n_valid] 双输入列表，会报 `invalid vector subscript`。
ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/ov-int8-past'

OUT = 'reports/c069m_real_call_profile.json'


def load_slice():
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR, sr
    return audio[SR * SLICE_START_SEC:SR * SLICE_END_SEC]


def main():
    a = load_slice()
    print(f'[c069m] 切片 {len(a)/SR:.1f}s', flush=True)

    # ── 阶段 1：纯切段，不加载模型 ──────────────────────────────
    print('[c069m] 阶段 1：VAD 切段（不加载模型）', flush=True)
    plan = SegmentedStreamer(
        None, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    segs = plan._plan_segments(a)
    seg_info = []
    for i, (s, e) in enumerate(segs[:N_SEGS]):
        dur = (e - s) / SR
        n_ch = int(np.ceil(dur / CHUNK_SEC))
        seg_info.append({'idx': i, 'dur_s': round(dur, 2),
                         'n_chunks_640ms': n_ch, 'n_generate_est': n_ch + 1})
        print(f"  seg{i:2d} dur={dur:6.2f}s chunks={n_ch:3d} gen≈{n_ch+1:3d}",
              flush=True)
    del plan

    # ── 阶段 2：生产模型 + 分项计时 ─────────────────────────────
    print('\n[c069m] 阶段 2：加载生产模型实测（encoder/prefill/decode 分项）',
          flush=True)
    backend = SegmentEncoderOVBackend(encoder_dir=ENC_DIR, decoder_dir=DEC_DIR,
                                      device='GPU.0', precision='f16')

    # warmup：覆盖到接近 VAD 段上限，避免首段吃冷启动
    for s in (5, 12, 18):
        st = _make_segment_state(backend, unfixed_chunk_num=0,
                                 unfixed_token_num=5,
                                 chunk_size_sec=CHUNK_SEC,
                                 force_language=None, context='')
        SegmentedStreamer(
            backend, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
            chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0, unfixed_token_num=5,
            max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
            enable_hallucination_reset=False)._run_one_segment(a[:SR * s], st)
    print('[c069m] warmup done', flush=True)

    # 打桩：统计 prompt 长度 / prefill 数 / decode 步数 / 分项耗时
    # 注意：所有 list 都必须**逐段清空**，计数一律用 len(probe[...]) 现算，
    # 不要维护跨段累加的计数器（v1 踩过这个坑，把 n_generate 报成累计值 144）。
    probe = {'enc_ms': [], 'prefill_ms': [], 'decode_ms': [], 'n_decode': [],
             'prompt_len': [], 'n_audio': [], 'budget': [],
             'out_tokens': []}

    orig_encode = backend.encode_audio
    orig_decode = backend.greedy_decode_with_prefix

    def traced_encode(wav):
        t0 = time.perf_counter()
        ehs, n_real, N_audio = orig_encode(wav)
        probe['enc_ms'].append((time.perf_counter() - t0) * 1000)
        probe['n_audio'].append(int(N_audio))
        return ehs, n_real, N_audio

    def traced_decode(ehs, prefix_ids, max_new_tokens):
        n_prompt = (len(backend._prompt_template_ids[0])
                    + ehs.shape[1]
                    + len(backend._prompt_template_ids[1])
                    + len(prefix_ids))
        probe['prompt_len'].append(n_prompt)
        probe['budget'].append(int(max_new_tokens))

        # 把内部 prefill / decode 拆开计时
        ids_left, ids_right = backend._prompt_template_ids
        N_audio = ehs.shape[1]
        audio_pad_ids = [backend._audio_pad_id] * N_audio
        full_ids = ids_left + audio_pad_ids + ids_right + list(prefix_ids)
        input_ids = np.array([full_ids], dtype=np.int64)

        t0 = time.perf_counter()
        backend.dec_infer.reset_state()
        out = backend.dec_infer.infer({
            "input_ids": input_ids,
            "encoder_hidden_states": ehs,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        probe['prefill_ms'].append((time.perf_counter() - t0) * 1000)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        next_id = int(np.argmax(logits[0, -1, :]))
        generated = [next_id]
        eos_ids = {151643, 151645, backend.tokenizer.eos_token_id}
        n_dec = 0
        td = time.perf_counter()
        for _ in range(max_new_tokens - 1):
            if next_id in eos_ids:
                break
            out = backend.dec_infer.infer({
                "input_ids": np.array([[next_id]], dtype=np.int64),
                "beam_idx": np.array([0], dtype=np.int32),
            }, share_inputs=True)
            logits = out["logits"] if isinstance(out, dict) else out[0]
            next_id = int(np.argmax(logits[0, -1, :]))
            generated.append(next_id)
            n_dec += 1
        probe['decode_ms'].append((time.perf_counter() - td) * 1000)
        probe['n_decode'].append(n_dec)
        probe['out_tokens'].append(len(generated))
        return generated

    backend.encode_audio = traced_encode
    backend.greedy_decode_with_prefix = traced_decode

    stats = []
    t_all0 = time.perf_counter()
    for (s, e) in segs[:N_SEGS]:
        seg_audio = a[s:e]
        dur = len(seg_audio) / SR
        for k in probe:
            if isinstance(probe[k], list):
                probe[k].clear()
        state = _make_segment_state(backend, unfixed_chunk_num=0,
                                    unfixed_token_num=5,
                                    chunk_size_sec=CHUNK_SEC,
                                    force_language=None, context='')
        t0 = time.perf_counter()
        txt = streamer_run = SegmentedStreamer(
            backend, strategy='vad', min_segment_sec=12.0,
            max_segment_sec=20.0, chunk_size_sec=CHUNK_SEC, unfixed_chunk_num=0,
            unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
            finish_budget='max64',
            enable_hallucination_reset=False)._run_one_segment(seg_audio, state)
        wall = time.perf_counter() - t0
        st = {
            'idx': len(stats), 'dur_s': round(dur, 2),
            'n_chunks': state.chunk_id,
            'n_generate': len(probe['prefill_ms']),
            'wall_s': round(wall, 2), 'rtf': round(wall / dur, 3),
            'enc_ms_mean': round(float(np.mean(probe['enc_ms'])), 2),
            'enc_ms_total': round(float(np.sum(probe['enc_ms'])), 1),
            'prefill_ms_mean': round(float(np.mean(probe['prefill_ms'])), 2),
            'prefill_ms_total': round(float(np.sum(probe['prefill_ms'])), 1),
            'decode_ms_total': round(float(np.sum(probe['decode_ms'])), 1),
            'prompt_len_last': probe['prompt_len'][-1] if probe['prompt_len'] else 0,
            'n_audio_last': probe['n_audio'][-1] if probe['n_audio'] else 0,
            'out_tok_mean': round(float(np.mean(probe['out_tokens'])), 1),
            'out_tok_max': int(np.max(probe['out_tokens'])) if probe['out_tokens'] else 0,
            'n_decode_total': int(np.sum(probe['n_decode'])),
            'text': txt[:100],
        }
        stats.append(st)
        print(f"  seg{st['idx']:2d} dur={dur:6.2f}s chunks={st['n_chunks']:3d} "
              f"gen={st['n_generate']:3d} wall={wall:6.2f}s RTF={st['rtf']:.3f} | "
              f"enc={st['enc_ms_mean']:.1f}ms prefill={st['prefill_ms_mean']:.1f}ms "
              f"prompt_len={st['prompt_len_last']} out_tok={st['out_tok_mean']}", flush=True)
    total_wall = time.perf_counter() - t_all0

    def agg(key):
        v = [s[key] for s in stats]
        return {'mean': round(float(np.mean(v)), 2),
                'median': round(float(np.median(v)), 2),
                'min': round(float(np.min(v))), 'max': round(float(np.max(v)))}

    grand_ms = float(np.sum([s['enc_ms_total'] + s['prefill_ms_total']
                             + s['decode_ms_total'] for s in stats]))
    result = {
        'note': 'C-069m：实测流式循环里 decoder 的真实调用画像。'
                '目的：用真实数据替换 c069l 的 AVG_OUT_TOK=65 猜测，'
                '并量化"每 chunk 重新 prefill 整条 prompt"这一结构性成本。',
        'method': f'生产路径 {ENC_DIR}（stateful FP16 enc）+ {DEC_DIR}（INT8 dec），'
                  f'{SLICE_START_SEC//60}–{SLICE_END_SEC//60} 分钟切片前 {N_SEGS} 段，'
                  f'chunk={CHUNK_SEC}s，warmup=[5,12,18]s，逐段 fresh state。',
        'seg_info': seg_info,
        'segments': stats,
        'summary': {
            'n_generate_total': int(np.sum([s['n_generate'] for s in stats])),
            'generate_calls_per_segment': agg('n_generate'),
            'chunks_per_segment': agg('n_chunks'),
            'prompt_len_last_segment': agg('prompt_len_last'),
            'n_audio_last_segment': agg('n_audio_last'),
            'out_tokens_per_call': agg('out_tok_mean'),
            'enc_ms_per_call': agg('enc_ms_mean'),
            'prefill_ms_per_call': agg('prefill_ms_mean'),
            'seg_rtf': agg('rtf'),
            'seg_wall_s': agg('wall_s'),
            'accounted_share_of_wall': round(grand_ms / (total_wall * 1000), 3),
        },
        'structural': {
            'prefill_calls_equal_chunks': all(
                s['n_generate'] >= s['n_chunks'] for s in stats),
            'n_generate_equals_chunks_plus_finish': all(
                s['n_generate'] == s['n_chunks'] + 1 for s in stats),
            'prefill_share_of_decoder': round(float(np.sum(
                [s['prefill_ms_total'] for s in stats]))
                / grand_ms, 3),
            'decode_share_of_decoder': round(float(np.sum(
                [s['decode_ms_total'] for s in stats])) / grand_ms, 3),
            'enc_share_of_decoder': round(float(np.sum(
                [s['enc_ms_total'] for s in stats])) / grand_ms, 3),
        },
        'total_wall_s': round(total_wall, 2),
    }

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    print(json.dumps(result['structural'], ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
