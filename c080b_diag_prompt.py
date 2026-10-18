"""c080b_diag_prompt.py — C-080 接线排查：为什么真实音频 prompt 出 "yay"。

c080a 的结论：机制上通了（音频嵌入确实进入计算，置零后 logits 变化量 1324），
但转写是 "yay"，不是人话。C-079 之前只验证过 **随机 token embedding** 的
CPU/NPU 一致性，**从未验证过这个 IR 在真实 ASR prompt 上能否说出人话**。
所以这里要区分三种可能：

  A. prompt 拼接错了（left/right/prefix 顺序、模板 token、audio_pad 数量）
     → 与设备、量化无关，CPU 上也该是垃圾
  B. NPUW 在真实长序列上算错了
     → CPU 上是人话，NPU 上是垃圾
  C. 量化（INT8/INT4）本身把 LM 打坏了
     → CPU 上也是垃圾；但 FP16 cleanie 应该是人话

三个实验一次跑完：
  1. 同一份 inputs_embeds，cleanie IR 在 CPU 与 NPU 上各解码 12 步 → 比 token
  2. HF `Qwen3ForCausalLM`（torch，未量化）喂同一份 inputs_embeds → 参照
  3. 打印 prompt 的 token 分解，人工核对 left/right 是否与生产一致

判定：
  CPU 也垃圾 + torch 是人话 → A 或 C（prompt 拼错，或量化坏了）
  CPU 是人话 + NPU 垃圾     → B（NPUW 真实序列有问题，必须撤回 cleanie 结论）

输出：reports/c080b_diag_prompt.json
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
OUT = 'reports/c080b_diag_prompt.json'
N_STEPS = 12


def log(*a):
    print(*a, flush=True)


def load_slice():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    return a[SR * START_SEC:SR * (START_SEC + SEG_SEC)]


def decode_ov(xml, dev, props, emb, W, n_steps):
    """在一个 InferRequest 内 prefill + n_steps 贪心解码。"""
    import openvino as ov
    cm = ov.Core().compile_model(xml, dev, props)
    req = cm.create_infer_request()
    T = int(emb.shape[1])
    out = req.infer({
        "attention_mask": np.ones((1, T), dtype=np.int64),
        "position_ids": np.arange(T, dtype=np.int64)[None, :],
        "beam_idx": np.zeros(1, dtype=np.int32),
        "inputs_embeds": emb,
    })
    port = cm.outputs[0].get_any_name()
    logits = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()
    toks, lgs = [], []
    nxt = int(np.argmax(logits))
    toks.append(nxt)
    for _ in range(n_steps - 1):
        past = T + len(toks) - 1
        out = req.infer({
            "attention_mask": np.ones((1, past + 1), dtype=np.int64),
            "position_ids": np.array([[past]], dtype=np.int64),
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": np.ascontiguousarray(
                W[nxt][None, None, :], dtype=np.float32),
        })
        logits = np.ascontiguousarray(np.array(out[port].data)[0, -1]).copy()
        lgs.append(logits.copy())
        nxt = int(np.argmax(logits))
        toks.append(nxt)
    del req, cm
    return toks, lgs


def main():
    a = load_slice()
    rep = {'seg_start_sec': START_SEC, 'seg_dur_s': SEG_SEC}

    from npu_embeds_backend import (NPUEmbedsDecoderBackend, _load_embed_table,
                                    MAX_PROMPT_TOK)
    W = _load_embed_table()

    # ── 实验 0：prompt 分解，人工核对 ─────────────────────────────
    be = NPUEmbedsDecoderBackend(
        decoder_dir='models/qwen3-lm-int4sym-cleanie-ov')
    ehs, n_real, N_audio = be.encode_audio(a)
    emb = be.build_inputs_embeds(ehs, [])
    T = int(emb.shape[1])
    ids_left, ids_right = be._prompt_template_ids
    rep['prompt'] = {
        'n_audio': int(N_audio),
        'ids_left': ids_left, 'ids_right': ids_right,
        'left_text': be.tokenizer.decode(ids_left),
        'right_text': be.tokenizer.decode(ids_right),
        'T_no_prefix': T,
        'expected_T': len(ids_left) + int(N_audio) + len(ids_right),
        'audio_pad_id': be._audio_pad_id,
        'audio_token_id_config': 151676,
        'ehs_stats': {'mean': round(float(ehs.mean()), 5),
                      'std': round(float(ehs.std()), 5),
                      'absmax': round(float(np.abs(ehs).max()), 4)},
        'emb_stats': {'mean': round(float(emb.mean()), 5),
                      'std': round(float(emb.std()), 5)},
    }
    log('[0] prompt: N_audio=%d T=%d expected=%d' % (
        N_audio, T, rep['prompt']['expected_T']))
    log('[0] left  = %r' % rep['prompt']['left_text'])
    log('[0] right = %r' % rep['prompt']['right_text'])
    log('[0] ehs  mean=%.5f std=%.5f absmax=%.4f' % (
        ehs.mean(), ehs.std(), np.abs(ehs).max()))
    log('[0] emb  mean=%.5f std=%.5f' % (emb.mean(), emb.std()))

    # ── 实验 1：cleanie IR 的 CPU vs NPU ──────────────────────────
    xml = 'models/qwen3-lm-int4sym-cleanie-ov/openvino_model.xml'
    npuw = {"NPU_USE_NPUW": "YES", "NPUW_LLM": "YES",
            "NPUW_LLM_MAX_PROMPT_LEN": str(MAX_PROMPT_TOK),
            "NPUW_LLM_MIN_RESPONSE_LEN": "64",
            "CACHE_DIR": "reports/npu_cache"}
    for dev, props in (("CPU", {}), ("NPU", npuw)):
        try:
            t0 = time.perf_counter()
            toks, lgs = decode_ov(xml, dev, props, emb, W, N_STEPS)
            txt = be.tokenizer.decode(toks, skip_special_tokens=True)
            rep[f'int4_{dev}'] = {'tokens': toks, 'text': txt,
                                  'seconds': round(time.perf_counter() - t0, 1)}
            log('[1] INT4@%s tokens=%s' % (dev, toks))
            log('[1] INT4@%s text=%r' % (dev, txt[:200]))
        except Exception as e:
            rep[f'int4_{dev}'] = {'error': f'{type(e).__name__}: {str(e)[:300]}'}
            log('[1] INT4@%s FAILED %s' % (dev, rep[f'int4_{dev}']['error']))
    del be

    # ── 实验 2：torch 未量化参照（需要临时放开 torch） ─────────────
    try:
        os.environ.pop('USE_TORCH', None)
        import importlib
        import transformers.utils as tu
        importlib.reload(tu)
        import torch
        from transformers import Qwen3ForCausalLM
        m = Qwen3ForCausalLM.from_pretrained('models/hf-qwen3-lm',
                                             dtype=torch.float32).eval()
        ids = torch.from_numpy(emb[0].astype(np.float32))[None]
        pos = torch.arange(T)[None]
        with torch.no_grad():
            lg = m(input_ids=None, inputs_embeds=ids,
                   attention_mask=torch.ones(1, T, dtype=torch.long),
                   position_ids=pos).logits[0, -1]
        nxt = int(lg.argmax())
        toks = [nxt]
        cur_ids = ids
        for _ in range(N_STEPS - 1):
            e = torch.from_numpy(W[nxt][None, None, :].astype(np.float32))
            cur_ids = torch.cat([cur_ids, e], dim=1)
            p = T + len(toks) - 1
            with torch.no_grad():
                lg = m(input_ids=None, inputs_embeds=cur_ids,
                       attention_mask=torch.ones(1, cur_ids.shape[1],
                                                 dtype=torch.long),
                       position_ids=torch.arange(cur_ids.shape[1])[None]
                       ).logits[0, -1]
            nxt = int(lg.argmax())
            toks.append(nxt)
        rep['torch_fp32'] = {
            'tokens': toks,
            'text': be.tokenizer.decode(toks, skip_special_tokens=True)
            if False else None,
        }
        log('[2] torch FP32 tokens=%s' % toks)
        del m
    except Exception as e:
        rep['torch_fp32'] = {'error': f'{type(e).__name__}: {str(e)[:400]}'}
        log('[2] torch FAILED %s' % rep['torch_fp32']['error'])

    if rep.get('torch_fp32', {}).get('tokens'):
        rep['torch_fp32']['text'] = None  # tokenizer 已在上面的 be 里释放

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log('saved -> %s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
