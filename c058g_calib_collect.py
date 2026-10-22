"""c058g_calib_collect.py — C-058⑤(d): 采集**真实** 0–12 分钟校准激活

reviewer 硬性要求（CORRECTIONS.md ⑤）：
  「校准**只用 0–12 分钟**，评测**只用 ≥12 分钟**」

c058d 的 build_calib_dataset() 此前是随机张量占位，撑不起 AWQ /
scale_estimation —— AWQ 的本质是按**激活幅度**挑显著通道，喂随机数等于没校准。

本脚本：
  1. 用 **FP16 encoder**（= 交付基线）编码 0–12 分钟的真实 VAD 段；
  2. 用 **FP16 decoder** 做真实 greedy 解码，边解边把送进 decoder 的
     三路输入 (encoder_hidden_states, input_ids, beam_idx) 采样出来；
  3. 只取前 12 分钟，**绝不触碰 ≥12 分钟**，落盘 npz 供 NNCF dataset 迭代。

采样的是**真实推理输入**（与线上一致），不是随机张量。

⚠️ GPU 独占：本脚本会跑 encoder+decoder 推理，**必须与其它 GPU 任务串行**。

用法：python c058g_calib_collect.py [out.npz] [--n 32]
输出：reports/c058_calib_0_12min.npz
"""
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from seg_stream import SegmentedStreamer

AUDIO = 'test_audio/<redacted>.wav'
ENC_DIR = 'models/ov-encoder-segment-reviewer'      # FP16, = 交付基线
DEC_DIR = 'models/ov-fp16-past'                     # FP16, 未量化
CALIB_MAX_SEC = 12 * 60                             # reviewer 硬性上限
OUT_NPZ = 'reports/c058_calib_0_12min.npz'


def collect_inputs(backend, ehs, prefix_ids, max_new_tokens):
    """复刻 greedy_decode_with_prefix，但返回**送进 decoder 的真实输入**。

    只截第一张 prefill 输入（整段 12–20 s 音频 + 完整 prompt，长度可达
    2000+ token，NNCF 逐样本前向代价高但仍可行），外加若干 decode step
    的单 token 输入，兼顾 prefill / decode 两种激活分布。
    """
    ids_left, ids_right = backend._prompt_template_ids
    N_audio = ehs.shape[1]
    audio_pad_ids = [backend._audio_pad_id] * N_audio
    full_ids = ids_left + audio_pad_ids + ids_right + list(prefix_ids)
    input_ids = np.array([full_ids], dtype=np.int64)

    samples = [(ehs, input_ids, np.array([0], dtype=np.int32))]

    backend.dec_infer.reset_state()
    out = backend.dec_infer.infer({
        "input_ids": input_ids,
        "encoder_hidden_states": ehs,
        "beam_idx": np.array([0], dtype=np.int32),
    }, share_inputs=True)
    logits = out["logits"] if isinstance(out, dict) else out[0]
    next_id = int(np.argmax(logits[0, -1, :]))
    eos_ids = {151643, 151645, backend.tokenizer.eos_token_id}
    for _ in range(max_new_tokens - 1):
        if next_id in eos_ids:
            break
        step_ids = np.array([[next_id]], dtype=np.int64)
        samples.append((None, step_ids, np.array([0], dtype=np.int32)))
        out = backend.dec_infer.infer({
            "input_ids": step_ids,
            "beam_idx": np.array([0], dtype=np.int32),
        }, share_inputs=True)
        logits = out["logits"] if isinstance(out, dict) else out[0]
        next_id = int(np.argmax(logits[0, -1, :]))
    return samples


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = args[0] if args else OUT_NPZ
    n_target = 24
    if '--n' in sys.argv:
        n_target = int(sys.argv[sys.argv.index('--n') + 1])

    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    audio = audio[:sr * CALIB_MAX_SEC]              # 硬性只取前 12 分钟
    print(f'[c058g] 校准音频 = 前 {len(audio)/sr:.1f}s ({len(audio)/sr/60:.2f} min)'
          f'  ← 上限 {CALIB_MAX_SEC}s', flush=True)
    assert len(audio) / sr <= CALIB_MAX_SEC + 1e-6, '校准音频超出 12 分钟！'

    backend = SegmentEncoderOVBackend(encoder_dir=ENC_DIR, decoder_dir=DEC_DIR,
                                      device='GPU.0', precision='f16')
    print('[c058g] warmup ...', flush=True)
    SegmentedStreamer(
        backend, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        enable_hallucination_reset=False).run(audio[:16000 * 5])

    # 用 streamer 拿真实 VAD 段边界，再逐段编码 + 采样
    print('[c058g] 采集中（真实 FP16 推理）...', flush=True)
    streamer = SegmentedStreamer(
        backend, strategy='vad', min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64, unfixed_chunk_num=0, unfixed_token_num=5,
        max_new_tokens=32, adaptive_budget=True, finish_budget='max64',
        enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    print(f'[c058g] 参考解码完成 {time.perf_counter()-t0:.1f}s / {len(segs)} 段',
          flush=True)

    # segs 是 dict 列表：{'start_s','end_s','text',...}
    samples, n_seg = [], 0
    for s in segs:
        st, en = float(s['start_s']), float(s['end_s'])
        if st >= CALIB_MAX_SEC:
            continue
        i0, i1 = int(st * sr), int(min(en, CALIB_MAX_SEC) * sr)
        wav = audio[i0:i1]
        if wav.size < sr:          # 丢掉 <1s 的碎片
            continue
        try:
            ehs, _, _ = backend.encode_audio(wav)
        except AssertionError:
            continue
        if ehs.shape[1] == 0:
            continue
        n_seg += 1
        got = collect_inputs(backend, ehs, [], max_new_tokens=6)
        for e, ids, bidx in got:
            if len(samples) < n_target:
                samples.append((e, ids, bidx))
        if len(samples) >= n_target:
            break

    if not samples:
        print('[c058g] ⚠️ 未采到样本', flush=True)
        return 1

    # NNCF 的 compress_weights(dataset=...) 要求每样本是一整份 dict，
    # 预填 full input（decode step 只有 input_ids 不完整）→ 只保留 prefill
    prefill = [s for s in samples if s[0] is not None]
    use = prefill if prefill else samples
    os.makedirs('reports', exist_ok=True)
    payload = {}
    for k, i in (('encoder_hidden_states', 0), ('input_ids', 1),
                 ('beam_idx', 2)):
        arrs = [s[i] for s in use]
        payload[k] = np.concatenate(arrs, axis=0) if k != 'beam_idx' \
            else np.concatenate(arrs, axis=0)
    np.savez_compressed(out, split_sec=CALIB_MAX_SEC, n_samples=len(use), **payload)
    print(f'[c058g] saved {len(use)} 真实样本 -> {out}', flush=True)
    for k, v in payload.items():
        print(f'   {k:<24} {v.shape} {v.dtype}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
