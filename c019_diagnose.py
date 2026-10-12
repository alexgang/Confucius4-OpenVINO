"""c019_diagnose.py — C-019 诊断矩阵

5 配置 × 2 段（A=600-660s 循环严重, B=1200-1260s 相对好），输出每段前 80 词 + WER。
"""
import os, sys, time, json, csv
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

import numpy as np
import soundfile as sf
import torch

sys.path.insert(0, '.')
from backends import OVBackend, TorchBackend, SAMPLE_RATE
from streaming_asr import streaming_transcribe, finish_streaming_transcribe

AUDIO_A = 'reports/c019_A.wav'
AUDIO_B = 'reports/c019_B.wav'
OUT_DIR = 'reports/c019_diag'

# WER 工具
def normalize(s):
    s = s.lower()
    # 去标点
    import re
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def first_n_words(s, n=80):
    return ' '.join(s.split()[:n])

def calc_wer(ref, hyp):
    import jiwer
    ref_n = normalize(ref)
    hyp_n = normalize(hyp)
    out = jiwer.process_words([ref_n], [hyp_n])
    return {
        'wer': out.wer,
        'substitutions': out.substitutions,
        'deletions': out.deletions,
        'insertions': out.insertions,
        'hits': out.hits,
        'ref_words': len(ref_n.split()),
        'hyp_words': len(hyp_n.split()),
    }


# ── #1: TorchBackend CPU FP32 离线 (qwen_asr.transcribe) ──
def cfg1_torch_offline(wav_path, name):
    from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
    print(f'[{name}] loading TorchBackend (CPU FP32) ...', flush=True)
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager',
    )
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    t0 = time.perf_counter()
    res = wrapper.transcribe(
        [(audio, sr)], language=None, return_time_stamps=False,
    )
    wall = time.perf_counter() - t0
    text = res[0].text
    raw = res[0]
    # 打印原始输出（包括 language tag）
    print(f'[{name}] raw (前 200 字符): {repr(str(raw))[:200]}', flush=True)
    print(f'[{name}] text (前 80 词): {first_n_words(text, 80)!r}', flush=True)
    print(f'[{name}] wall={wall:.2f}s', flush=True)
    return text, wall


# ── #2: OV FP16-past 离线 greedy ──
def cfg2_ov_fp16_offline(wav_path, name):
    print(f'[{name}] loading OVBackend (FP16) ...', flush=True)
    b = OVBackend(model_dir='models/ov-fp16-past', device='GPU.0')
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    state = b.init_streaming_state(
        unfixed_chunk_num=0, unfixed_token_num=0, chunk_size_sec=10.0,
    )
    state.force_language = None
    # 离线 greedy：把整段一次性塞进 audio_accum，prefill 整条 prompt + audio
    ehs, n_real, N_audio = b.encode_audio(audio)
    print(f'[{name}] encoder: n_real_mel={n_real} N_audio={N_audio}', flush=True)
    t0 = time.perf_counter()
    out_ids = b.greedy_decode_with_prefix(ehs, prefix_ids=[], max_new_tokens=512)
    wall = time.perf_counter() - t0
    text = b.tokenizer.decode(out_ids, skip_special_tokens=True)
    # 把 <asr_text> tag 等也算上 → 找 tag 后内容
    from streaming_asr import _ASR_TEXT_TAG, parse_asr_output
    lang, txt = parse_asr_output(text, user_language=None)
    if not txt:
        # 重新尝试：text 可能是 raw 不带 tag；使用 text 整体
        txt = text
    print(f'[{name}] lang={lang!r} txt (前 80 词): {first_n_words(txt, 80)!r}', flush=True)
    print(f'[{name}] wall={wall:.2f}s', flush=True)
    return txt, wall


# ── #3: OV INT8-past 离线 greedy ──
def cfg3_ov_int8_offline(wav_path, name):
    print(f'[{name}] loading OVBackend (INT8) ...', flush=True)
    b = OVBackend(model_dir='models/ov-int8-past', device='GPU.0')
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    ehs, n_real, N_audio = b.encode_audio(audio)
    print(f'[{name}] encoder: n_real_mel={n_real} N_audio={N_audio}', flush=True)
    t0 = time.perf_counter()
    out_ids = b.greedy_decode_with_prefix(ehs, prefix_ids=[], max_new_tokens=512)
    wall = time.perf_counter() - t0
    text = b.tokenizer.decode(out_ids, skip_special_tokens=True)
    from streaming_asr import parse_asr_output
    lang, txt = parse_asr_output(text, user_language=None)
    if not txt:
        txt = text
    print(f'[{name}] lang={lang!r} txt (前 80 词): {first_n_words(txt, 80)!r}', flush=True)
    print(f'[{name}] wall={wall:.2f}s', flush=True)
    return txt, wall


# ── #4: OV INT8-past 流式 ──
def cfg4_ov_int8_streaming(wav_path, name, *, max_new_tokens=32,
                           unfixed_chunk_num=2, unfixed_token_num=5):
    print(f'[{name}] loading OVBackend (INT8 streaming) ...', flush=True)
    b = OVBackend(model_dir='models/ov-int8-past', device='GPU.0')
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    state = b.init_streaming_state(
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=0.64,
    )
    t0 = time.perf_counter()
    feed_chunk = int(SAMPLE_RATE * 0.04)
    feed_pos = 0
    while feed_pos < len(audio):
        end = min(feed_pos + feed_chunk, len(audio))
        streaming_transcribe(b, audio[feed_pos:end], state,
                             max_new_tokens=max_new_tokens, rollback_punctuation=False)
        feed_pos = end
    final = finish_streaming_transcribe(b, state, max_new_tokens=max(64, max_new_tokens))
    wall = time.perf_counter() - t0
    print(f'[{name}] final (前 80 词): {first_n_words(final, 80)!r}', flush=True)
    print(f'[{name}] wall={wall:.2f}s', flush=True)
    return final, wall


# ── #5: TorchBackend 流式 ──
def cfg5_torch_streaming(wav_path, name, *, max_new_tokens=32,
                         unfixed_chunk_num=2, unfixed_token_num=5):
    print(f'[{name}] loading TorchBackend (streaming) ...', flush=True)
    b = TorchBackend(model_dir='models/hf')
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float32)
    state = b.init_streaming_state(
        unfixed_chunk_num=unfixed_chunk_num,
        unfixed_token_num=unfixed_token_num,
        chunk_size_sec=0.64,
    )
    t0 = time.perf_counter()
    feed_chunk = int(SAMPLE_RATE * 0.04)
    feed_pos = 0
    while feed_pos < len(audio):
        end = min(feed_pos + feed_chunk, len(audio))
        streaming_transcribe(b, audio[feed_pos:end], state,
                             max_new_tokens=max_new_tokens, rollback_punctuation=False)
        feed_pos = end
    final = finish_streaming_transcribe(b, state, max_new_tokens=max(64, max_new_tokens))
    wall = time.perf_counter() - t0
    print(f'[{name}] final (前 80 词): {first_n_words(final, 80)!r}', flush=True)
    print(f'[{name}] wall={wall:.2f}s', flush=True)
    return final, wall


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = []
    for seg_name, seg_path in [('A', AUDIO_A), ('B', AUDIO_B)]:
        print(f'\n========= segment {seg_name}: {seg_path} =========', flush=True)
        for cfg_id, cfg_fn, cfg_name in [
            (1, cfg1_torch_offline, 'cfg1_torch_offline'),
            (2, cfg2_ov_fp16_offline, 'cfg2_ov_fp16_offline'),
            (3, cfg3_ov_int8_offline, 'cfg3_ov_int8_offline'),
            (4, cfg4_ov_int8_streaming, 'cfg4_ov_int8_streaming'),
            (5, cfg5_torch_streaming, 'cfg5_torch_streaming'),
        ]:
            print(f'\n--- cfg {cfg_id} on {seg_name} ---', flush=True)
            try:
                text, wall = cfg_fn(seg_path, f'{seg_name}_{cfg_name}')
            except Exception as e:
                import traceback
                print(f'[{seg_name}_{cfg_name}] ERROR: {type(e).__name__}: {e}', flush=True)
                traceback.print_exc()
                text, wall = f'[ERROR: {e}]', 0.0
            summary.append({
                'seg': seg_name,
                'cfg': cfg_id,
                'cfg_name': cfg_name,
                'text': text,
                'text_first_80w': first_n_words(text, 80),
                'text_words': len(text.split()),
                'wall_s': wall,
            })
    # 写文件
    with open(f'{OUT_DIR}/summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    # 写人类可读对照
    with open(f'{OUT_DIR}/compare.txt', 'w', encoding='utf-8') as f:
        for s in summary:
            f.write(f"\n=== {s['seg']} | cfg {s['cfg']} ({s['cfg_name']}) | "
                    f"wall={s['wall_s']:.2f}s | words={s['text_words']} ===\n")
            f.write(s['text_first_80w'] + '\n')
    print(f'\n[diag] summary → {OUT_DIR}/summary.json', flush=True)
    print(f'[diag] compare → {OUT_DIR}/compare.txt', flush=True)


if __name__ == '__main__':
    main()
