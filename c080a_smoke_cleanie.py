"""c080a_smoke_cleanie.py — C-080 第 0 步：单段冒烟，确认接线正确。

在花 1–2 分钟编译 NPU + 15 分钟端到端之前，先用**一段**真实音频跑通：

  1. cleanie IR 在 NPU 上编译 + 实跑（compile 成功是假阳性，必须实跑）；
  2. prompt 拼接的 token 数落在 [模板 13 + 音频 ~N + 前缀] 的预期区间；
  3. `inputs_embeds` 真的进了计算（把音频段置零 → 输出必须变）；
  4. 产出的转写是不是**人话** —— 这是唯一能立刻暴露接线错误的信号：
     若 left/right 顺序错了、或音频没进去，输出必然是数字串或乱码。

第 4 条比任何 cosine 都有说服力，所以本脚本把转写全文打出来。

输出：reports/c080a_smoke.json
"""
import json
import os
import sys
import time

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from npu_embeds_backend import NPUEmbedsDecoderBackend
from seg_stream import SegmentedStreamer, _make_segment_state

AUDIO = 'test_audio/<redacted>.wav'
SR = 16000
START_SEC = 12 * 60          # 与 ABBA 同一切片起点
SEG_SEC = float(os.environ.get('C080A_SEG_SEC', '13'))
DEC = os.environ.get('C080A_DEC', 'models/qwen3-lm-int4sym-cleanie-ov')
OUT = 'reports/c080a_smoke.json'


def main():
    audio, sr = sf.read(AUDIO, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR
    a = audio[SR * START_SEC:SR * (START_SEC + int(SEG_SEC))]

    rep = {'decoder_dir': DEC, 'seg_start_sec': START_SEC,
           'seg_dur_s': SEG_SEC}

    t0 = time.perf_counter()
    be = NPUEmbedsDecoderBackend(decoder_dir=DEC)
    rep['npu_compile_s'] = be.npu_compile_s
    print(f'[c080a] {DEC} NPU 编译 {be.npu_compile_s}s '
          f'(总耗时 {time.perf_counter()-t0:.1f}s)', flush=True)
    rep['ports'] = sorted(be._port_names)

    # ── 接线检查 1：prompt 长度与音频段位置 ───────────────────────
    ehs, n_real, N_audio = be.encode_audio(a)
    emb = be.build_inputs_embeds(ehs, [])
    T = int(emb.shape[1])
    rep['n_audio'] = int(N_audio)
    rep['prompt_len_no_prefix'] = T
    rep['template_tokens'] = (len(be._prompt_template_ids[0])
                              + len(be._prompt_template_ids[1]))
    rep['prompt_budget'] = 512
    rep['headroom'] = 512 - T
    print(f'[c080a] N_audio={N_audio} T={T} '
          f'(模板 {rep["template_tokens"]} + 音频 {N_audio}) '
          f'512 上界余量 {512-T}', flush=True)

    # ── 接线检查 2：音频嵌入真的进了计算吗 ────────────────────────
    # 把音频段置零，logits 必须变。不变就说明音频段被忽略（或被模板覆盖）。
    lo, hi = len(be._emb_left), len(be._emb_left) + int(N_audio)

    def last_logits(e):
        req = be.dec.create_infer_request()
        out = req.infer({
            "attention_mask": np.ones((1, e.shape[1]), dtype=np.int64),
            "position_ids": np.arange(e.shape[1], dtype=np.int64)[None, :],
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": e,
        })
        lg = np.ascontiguousarray(
            np.array(out[be._logits_port()].data)[0, -1]).copy()
        del req
        return lg

    lg_real = last_logits(emb)
    emb_zero = emb.copy()
    emb_zero[0, lo:hi, :] = 0.0
    lg_zero = last_logits(emb_zero)
    nz = float(np.linalg.norm(lg_real - lg_zero))
    cos = float(lg_real @ lg_zero /
                (np.linalg.norm(lg_real) * np.linalg.norm(lg_zero)))
    rep['audio_enters_compute'] = bool(nz > 1e-6)
    rep['logits_diff_norm'] = round(nz, 4)
    rep['cos_real_vs_audiozero'] = round(cos, 6)
    print(f'[c080a] 音频置零后 logits 变化量={nz:.4f} cos={cos:.6f}', flush=True)

    # ── 接线检查 3：产出的转写是不是人话 ──────────────────────────
    state = _make_segment_state(be, unfixed_chunk_num=0, unfixed_token_num=5,
                                chunk_size_sec=0.64, force_language=None,
                                context='')
    streamer = SegmentedStreamer(
        be, strategy='off', chunk_size_sec=0.64, unfixed_chunk_num=0,
        unfixed_token_num=5, max_new_tokens=32, adaptive_budget=True,
        finish_budget='max64', enable_hallucination_reset=False)
    t0 = time.perf_counter()
    text, segs = streamer.run(a)
    wall = time.perf_counter() - t0
    rep['text'] = text
    rep['wall_s'] = round(wall, 2)
    rep['rtf'] = round(wall / (len(a) / SR), 4)
    rep['n_chunks'] = int(segs[0]['n_chunks']) if segs else 0
    rep['looks_like_speech'] = bool(
        any(c.isalpha() for c in text) and len(text) > 20)
    for k in ('enc_ms', 'prefill_ms', 'decode_ms'):
        v = be.probe[k]
        if v:
            rep[k + '_median'] = round(float(np.median(v)), 1)
            rep[k + '_n'] = len(v)
    rep['prompt_len_max'] = int(max(be.probe['prompt_len'])) if be.probe['prompt_len'] else 0
    rep['out_tokens_mean'] = round(
        float(np.mean(be.probe['out_tokens'])), 2) if be.probe['out_tokens'] else 0

    print('\n' + '=' * 70)
    print(f'TRANSCRIPT ({rep["wall_s"]}s, RTF {rep["rtf"]}):')
    print(text[:900])
    print('=' * 70, flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('saved ->', OUT)
    if not rep['looks_like_speech']:
        print('[c080a] !! 输出不像人话 —— 接线有问题，不要继续端到端')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
