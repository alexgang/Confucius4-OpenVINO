"""c046_seg60_probe.py — 定位 seg60 离线全量重解异常(hyp=18 vs ref=63)

疑点: 流式 base_k5 得62 词(接近 ref 63), 但无前缀全量重解只得 18 词。
可能原因:
  (a) 段边界来自 mix12 的 VAD 分段, 与本段实际语音不匹配
  (b) max_new_tokens 不足导致截断
  (c) EOS 过早触发
  (d) 编码器 2400 帧上限被触发
"""
import os, sys, json, re
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import parse_asr_output, _normalize_punct_by_context

SR = 16000
ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/ov-int8-past'


def norm_words(s):
    s = s.lower()
    s = re.sub(r"[^\w' ]", ' ', s).replace("'", '')
    return [w for w in s.split() if w]


def main():
    with open('reports/spe_61min_segments_ov-mix12-past.json', encoding='utf-8') as f:
        allsegs = json.load(f)
    seg = allsegs[60]
    s, e = float(seg['start_s']), float(seg['end_s'])
    print(f'[probe] seg60 meta: {seg}')
    print(f'[probe] span {s:.2f}-{e:.2f}  dur={e-s:.2f}s', flush=True)

    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR

    backend = SegmentEncoderOVBackend(encoder_dir=ENC_DIR, decoder_dir=DEC_DIR,
                                      device='GPU.0', precision='f16')
    tok = backend.tokenizer
    st = backend.init_streaming_state(unfixed_chunk_num=0, unfixed_token_num=5,
                                     chunk_size_sec=0.64)
    raw_ids = tok.encode(st.prompt_raw, add_special_tokens=False)

    wav = audio[int(s * SR):int(e * SR)]
    print(f'[probe] samples={len(wav)} ({len(wav)/SR:.2f}s)', flush=True)

    # 预热
    ehs, _, N = backend.encode_audio(wav[:5 * SR])
    backend.greedy_decode_with_prefix(ehs, [], 16)
    print('[probe] warmup done', flush=True)

    for budget in (32, 64, 128, 256, 400):
        ehs, n_real, N = backend.encode_audio(wav)
        ids = backend.greedy_decode_with_prefix(ehs, [], budget)
        eos = bool(ids) and ids[-1] in (151643, 151645, tok.eos_token_id)
        txt = _normalize_punct_by_context(tok.decode(ids, skip_special_tokens=True)).replace('\ufffd', '')
        _lang, clean = parse_asr_output(txt)
        print(f'  budget={budget:4d} N_audio={N:5d} n_real={n_real:5d} '
              f'gen_ids={len(ids):4d} eos={eos} words={len(norm_words(clean)):3d}', flush=True)
        print(f'      raw[:100]={txt[:100]!r}', flush=True)
        print(f'      clean     ={clean[:100]!r}', flush=True)

    # 检查音频本身是否真有语音: 算 RMS 分布
    rms = float(np.sqrt(np.mean(wav.astype(np.float64) ** 2)))
    print(f'\n[probe] seg60 RMS={rms:.5f}  peak={float(np.max(np.abs(wav))):.4f}', flush=True)

    # ── 关键复现: 先顺序解码 seg118/161/163/seg5, 再解 seg60 ──
    # 检验是否因解码器/编码器状态残留导致 seg60 退化
    print('\n[probe] === 顺序解码 5 段后再解 seg60 (复现 fix 循环的顺序) ===', flush=True)
    order = [(1925.4, 1939.5, 'seg118'), (2622.2, 2640.4, 'seg161'),
             (2656.8, 2675.9, 'seg163'), (76.7, 93.0, 'seg5')]
    for ss, ee, nm in order:
        w2 = audio[int(ss * SR):int(ee * SR)]
        e2, _, _ = backend.encode_audio(w2)
        g2 = backend.greedy_decode_with_prefix(e2, [], 32)
        t2 = _normalize_punct_by_context(tok.decode(g2, skip_special_tokens=True)).replace('\ufffd', '')
        _l2, c2 = parse_asr_output(t2)
        print(f'  {nm:8s} ids={len(g2):3d} words={len(norm_words(c2)):3d}', flush=True)

    ehs5, _, N5 = backend.encode_audio(wav)
    ids5 = backend.greedy_decode_with_prefix(ehs5, [], 128)
    eos5 = bool(ids5) and ids5[-1] in (151643, 151645, tok.eos_token_id)
    t5 = _normalize_punct_by_context(tok.decode(ids5, skip_special_tokens=True)).replace('\ufffd', '')
    _l5, c5 = parse_asr_output(t5)
    print(f'  >> seg60 AFTER 4segs: ids={len(ids5)} eos={eos5} words={len(norm_words(c5))}', flush=True)
    print(f'     text={c5[:110]!r}', flush=True)

    # 对比: 相邻段
    for idx in (5, 59, 60, 61, 62):
        if idx < len(allsegs):
            g = allsegs[idx]
            d = float(g['end_s']) - float(g['start_s'])
            w = audio[int(float(g['start_s']) * SR):int(float(g['end_s']) * SR)]
            r = float(np.sqrt(np.mean(w.astype(np.float64) ** 2))) if len(w) else 0.0
            print(f'  seg{idx}: {g["start_s"]:.1f}-{g["end_s"]:.1f} dur={d:.1f}s rms={r:.5f}', flush=True)


if __name__ == '__main__':
    main()