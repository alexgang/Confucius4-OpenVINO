"""c080c_torch_reference.py — C-080 判定：cleanie IR 垃圾输出的责任归属。

c080a/b 的实测链条：
    音频嵌入确实进入计算（置零后 logits 变化 1324）
    但 INT4 cleanie 的转写是 "yay"；**INT4 在 CPU 上也是**
    "language English\\nHuman 1\\n\\n"
→ 与 NPU 无关。C-079 只验证过「两组不同 embedding 给不同输出」，
   **从未验证这个 IR 在真实 ASR prompt 上能否说人话**。

三种可能，本脚本一次性判定：
  A. prompt 拼错          → 连 torch 未量化参照都是垃圾
  B. 量化/导出把 LM 打坏  → torch 是人话，cleanie（CPU/NPU）都是垃圾
  C. NPUW 在真实序列上错  → cleanie@CPU 是人话，cleanie@NPU 是垃圾

做法：直接加载 `models/hf` 的 `Qwen3ASRForConditionalGeneration`，
用**它自己的** `get_audio_features` + `masked_scatter` 生成 inputs_embeds，
再分别喂给 torch FP32 LM 与 cleanie IR（CPU / NPU）。
torch 的 inputs_embeds 是权威参照 —— 它就是生产模型自己的计算结果。

输出：reports/c080c_torch_reference.json
"""
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
START_SEC = 12 * 60
SEG_SEC = 13
OUT = 'reports/c080c_torch_reference.json'
N_STEPS = 16


def log(*a, **kw):
    print(*a, flush=kw.get('flush', True))


def load_slice():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    return a[SR * START_SEC:SR * (START_SEC + SEG_SEC)]


def main():
    a = load_slice()
    rep = {'seg_start_sec': START_SEC, 'seg_dur_s': SEG_SEC}

    import torch
    import qwen_asr  # noqa: F401  注册 qwen3_asr
    from qwen_asr.inference.qwen3_asr import Qwen3ASRModel
    from transformers import AutoTokenizer, WhisperFeatureExtractor

    log('[c080c] 加载 models/hf（torch 参照）...', flush=True)
    t0 = time.perf_counter()
    wrapper = Qwen3ASRModel.from_pretrained(
        'models/hf', dtype=torch.float32, attn_implementation='eager')
    model = wrapper.model.eval()          # Qwen3ASRForConditionalGeneration
    tok = AutoTokenizer.from_pretrained('models/hf', fix_mistral_regex=True)
    # 用**生产**的 chat_template（.jinja 纯文本，可直接读）。
    # models/hf 的 chat_template.json 没被 tokenizer 自动加载，而本实验要回答的
    # 正是「cleanie IR 的 prompt 与生产是否一致」，所以必须用生产模板，
    # 而不是 models/hf 里那份可能不同的。
    tok.chat_template = open('models/ov-int8-past/chat_template.jinja',
                             encoding='utf-8').read()
    log('[c080c] 加载 %.1fs' % (time.perf_counter() - t0), flush=True)

    fe = WhisperFeatureExtractor.from_pretrained('models/hf')

    # ── 用**生产**的特征提取路径（backends.extract_audio_features） ──
    # 这是 c069m / 交付链路在用的那一个；自己调 fe(...) 会得到不同的
    # 补零/分块口径，n_audio 就会对不上，结论会失真。
    from backends import extract_audio_features
    from segment_encoder_backend import total_aftercnn_len
    feats_real, _, n_real, n_audio = extract_audio_features(fe, a)
    feats = torch.from_numpy(np.asarray(feats_real, dtype=np.float32))
    fmask = None
    rep['feats_shape'] = list(feats.shape)

    # 文本部分按 audio 占位切开，和生产一致
    msgs = [{"role": "system", "content": ""},
            {"role": "user", "content": [{"type": "audio", "audio": ""}]}]
    text = tok.apply_chat_template(msgs, add_generation_prompt=True,
                                   tokenize=False)
    left_txt, right_txt = text.split('<|audio_start|><|audio_pad|><|audio_end|>')
    ids_left = tok.encode(left_txt, add_special_tokens=False)
    ids_right = tok.encode(right_txt, add_special_tokens=False)
    n_audio = int(n_audio)
    assert n_audio == total_aftercnn_len(feats.shape[-1]), (
        n_audio, total_aftercnn_len(feats.shape[-1]))
    full_ids = ids_left + [151676] * n_audio + ids_right
    rep['n_audio_model_side'] = n_audio
    rep['ids_left'] = ids_left
    rep['ids_right'] = ids_right
    rep['T_full'] = len(full_ids)
    log('[c080c] n_audio=%d T=%d' % (n_audio, len(full_ids)))

    with torch.no_grad():
        audio_features = model.thinker.get_audio_features(
            feats, audio_feature_lengths=torch.tensor([n_real]))
    log('[c080c] audio_features %s std=%.5f absmax=%.4f' % (
        tuple(audio_features.shape), audio_features.std(),
        audio_features.abs().max()))
    rep['audio_features'] = {
        'shape': list(audio_features.shape),
        'mean': round(float(audio_features.mean()), 6),
        'std': round(float(audio_features.std()), 6),
        'absmax': round(float(audio_features.abs().max()), 4),
    }

    # ── 交叉检查：torch audio_tower 输出 vs OV encoder 输出 ─────────
    # 我喂给 cleanie IR 的 ehs 来自 OV segment encoder。若两者不一致，
    # 那「cleanie 说不出人话」就可能是音频错了，而不是 LM 坏了。
    try:
        from npu_embeds_backend import NPUEmbedsDecoderBackend
        be = NPUEmbedsDecoderBackend(
            decoder_dir='models/qwen3-lm-int4sym-cleanie-ov')
        ehs_ov, _, N_ov = be.encode_audio(a)
        af = audio_features[0].numpy().astype(np.float32)[:N_ov]
        c = float((ehs_ov[0] * af).sum() /
                  (np.linalg.norm(ehs_ov[0]) * np.linalg.norm(af)))
        rep['ov_vs_torch_audio'] = {
            'N_audio': int(N_ov),
            'cosine': round(c, 6),
            'ov_std': round(float(ehs_ov.std()), 6),
            'torch_std': round(float(af.std()), 6),
            'ov_absmax': round(float(np.abs(ehs_ov).max()), 4),
            'torch_absmax': round(float(np.abs(af).max()), 4),
        }
        log('[c080c] OV encoder vs torch audio_tower: cos=%.6f '
            'ov_std=%.6f torch_std=%.6f' % (c, ehs_ov.std(), af.std()))
        del be
    except Exception as e:
        rep['ov_vs_torch_audio'] = {
            'error': f'{type(e).__name__}: {str(e)[:200]}'}
        log('[c080c] OV/torch 音频对比失败: %s' % rep['ov_vs_torch_audio']['error'])

    # ── 权威 inputs_embeds：模型自己的 masked_scatter 结果 ─────────
    emb_layer = model.thinker.get_input_embeddings()
    ids_t = torch.tensor([full_ids])
    with torch.no_grad():
        embeds = emb_layer(ids_t)
        mask = model.thinker.get_placeholder_mask(
            ids_t, inputs_embeds=embeds)
        rep['placeholder_tokens'] = int(mask.sum())
        embeds = embeds.masked_scatter(mask, audio_features.to(embeds.dtype))
    T = int(embeds.shape[1])
    emb_np = embeds[0].numpy().astype(np.float32)
    rep['T'] = T
    rep['embeds_stats'] = {'mean': round(float(emb_np.mean()), 6),
                           'std': round(float(emb_np.std()), 6)}
    log('[c080c] 权威 inputs_embeds %s std=%.6f（audio 段 std=%.6f）' % (
        tuple(embeds.shape), embeds.std(),
        audio_features.std()))

    # ── torch FP32 LM 贪心解码（参照） ────────────────────────────
    lm = model.thinker.model      # Qwen3ASRThinkerTextModel
    head = model.thinker.lm_head
    W = emb_layer.weight.detach().to(torch.float32).numpy()
    rep['embed_table_shape'] = list(W.shape)

    def torch_step(ids_so_far_embeds, n_past):
        with torch.no_grad():
            o = lm(inputs_embeds=ids_so_far_embeds,
                   attention_mask=torch.ones(1, ids_so_far_embeds.shape[1]),
                   position_ids=torch.arange(n_past,
                                             ids_so_far_embeds.shape[1])[None])
            return head(o[0][:, -1, :])[0]

    lg = torch_step(embeds, 0)
    toks = [int(lg.argmax())]
    cur = embeds
    for _ in range(N_STEPS - 1):
        e = torch.from_numpy(W[toks[-1]][None, None, :].astype(np.float32))
        cur = torch.cat([cur, e], dim=1)
        lg = torch_step(cur, 0)
        toks.append(int(lg.argmax()))
    txt = tok.decode(toks, skip_special_tokens=True)
    rep['torch_fp32'] = {'tokens': toks, 'text': txt}
    log('[c080c] torch FP32 tokens=%s' % toks)
    log('[c080c] torch FP32 TEXT  = %r' % txt[:300])
    log('[c080c] ★ 权威参照（这段音频的真实转写）★')

    # ── 同一份 embeds 喂 cleanie IR：CPU 与 NPU ───────────────────
    from npu_embeds_backend import MAX_PROMPT_TOK
    npuw = {"NPU_USE_NPUW": "YES", "NPUW_LLM": "YES",
            "NPUW_LLM_MAX_PROMPT_LEN": str(MAX_PROMPT_TOK),
            "NPUW_LLM_MIN_RESPONSE_LEN": "64",
            "CACHE_DIR": "reports/npu_cache"}
    import openvino as ov
    for tag, xml in (('int4', 'models/qwen3-lm-int4sym-cleanie-ov/openvino_model.xml'),
                     ('int8', 'models/qwen3-lm-int8sym-cleanie-ov/openvino_model.xml')):
        for dev, props in (("CPU", {}), ("NPU", npuw)):
            key = f'{tag}@{dev}'
            try:
                cm = ov.Core().compile_model(xml, dev, props)
                req = cm.create_infer_request()
                port = cm.outputs[0].get_any_name()
                out = req.infer({
                    "attention_mask": np.ones((1, T), dtype=np.int64),
                    "position_ids": np.arange(T, dtype=np.int64)[None, :],
                    "beam_idx": np.zeros(1, dtype=np.int32),
                    "inputs_embeds": emb_np[None],
                })
                lgv = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()
                ot = [int(np.argmax(lgv))]
                for _ in range(N_STEPS - 1):
                    past = T + len(ot) - 1
                    out = req.infer({
                        "attention_mask": np.ones((1, past + 1), dtype=np.int64),
                        "position_ids": np.array([[past]], dtype=np.int64),
                        "beam_idx": np.zeros(1, dtype=np.int32),
                        "inputs_embeds": np.ascontiguousarray(
                            W[ot[-1]][None, None, :], dtype=np.float32),
                    })
                    lgv = np.ascontiguousarray(
                        np.array(out[port].data)[0, -1]).copy()
                    ot.append(int(np.argmax(lgv)))
                del req, cm
                rep[key] = {'tokens': ot, 'text': tok.decode(ot, skip_special_tokens=True)}
                log('[c080c] %-9s tokens=%s' % (key, ot[:8]))
                log('[c080c] %-9s TEXT =%r' % (
                    key, rep[key]['text'][:200]))
            except Exception as e:
                rep[key] = {'error': f'{type(e).__name__}: {str(e)[:250]}'}
                log('[c080c] %-9s FAILED %s' % (key, rep[key]['error']))

    # ── 判定 ─────────────────────────────────────────────────────
    def looks_human(s):
        if not s:
            return False
        letters = sum(c.isalpha() for c in s)
        return letters >= 8 and len(s) >= 15

    v = {
        'torch_human': looks_human(rep.get('torch_fp32', {}).get('text', '')),
        'int4_cpu_human': looks_human(rep.get('int4@CPU', {}).get('text', '')),
        'int4_npu_human': looks_human(rep.get('int4@NPU', {}).get('text', '')),
        'int8_cpu_human': looks_human(rep.get('int8@CPU', {}).get('text', '')),
        'int8_npu_human': looks_human(rep.get('int8@NPU', {}).get('text', '')),
    }
    v['verdict'] = (
        'A/C: 量化或导出把 LM 打坏（torch 是人话，cleanie 全是垃圾）'
        if v['torch_human'] and not v['int4_cpu_human'] and not v['int8_cpu_human']
        else ('C: NPUW 在真实序列上错（CPU 是人话，NPU 是垃圾）'
              if v['int4_cpu_human'] and not v['int4_npu_human']
              else ('OK: cleanie 能说人话' if v['int4_cpu_human']
                    else 'A: prompt 拼接错误（连 torch 参照都不对）')))
    rep['verdict'] = v
    log('\n[c080c] VERDICT: %s' % v['verdict'])

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
