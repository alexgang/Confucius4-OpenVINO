"""C-072#4a step 1: verify that thinker text trunk == standard Qwen3ForCausalLM.

C-072 says: for pure text/audio get_rope_index sets all three position rows to the
same value, so interleaved MRoPE == plain 1D RoPE. Therefore the text trunk can be
mapped onto a standard Qwen3ForCausalLM (thinker.model.* -> model.*,
thinker.lm_head -> lm_head, config = text_config).

This script:
  1. loads the full Qwen3ASR model,
  2. builds a Qwen3ForCausalLM from text_config,
  3. copies thinker.model.* weights into it,
  4. runs the SAME inputs_embeds through both and compares logits,
  5. does a multi-step greedy decode with use_cache on both to make sure
     position handling is right over time, not just for one prefill.
"""
import json
import os
import sys
import time

import numpy as np
import torch
from transformers import AutoConfig, AutoTokenizer, Qwen3ForCausalLM
from qwen_asr.core.transformers_backend.modeling_qwen3_asr import (
    Qwen3ASRForConditionalGeneration,
)

WORK = os.path.dirname(os.path.abspath(__file__))
HF = os.path.join(WORK, "models", "hf")
OUT = os.path.join(WORK, "reports", "c072a_text_trunk_equivalence.json")

PROMPT = "system\n你是语音识别助手，请忠实转写音频内容。\nuser\naudio: <|audio_bos|><|AUDIO|><|audio_eos|>\nassistant\n"
PROMPT2 = "system\n你是语音识别助手，请忠实转写音频内容。\nuser\naudio: <|audio_bos|><|AUDIO|><|audio_eos|>\nassistant\n今天天气怎么样？"


def log(*a):
    print(*a, flush=True)


def main():
    from safetensors.torch import load_file

    os.makedirs(os.path.join(WORK, "reports"), exist_ok=True)
    t0 = time.time()

    full_cfg = AutoConfig.from_pretrained(HF)
    log("loading full model ...")
    full = Qwen3ASRForConditionalGeneration.from_pretrained(
        HF, dtype=torch.float32
    )
    full.eval()
    log("full model loaded %.1fs" % (time.time() - t0))

    thinker = full.thinker
    text_cfg = thinker.config.text_config

    log("text_config: hidden=%d layers=%d heads=%d kv=%d head_dim=%d vocab=%d rope_theta=%s tie=%s",
        text_cfg.hidden_size, text_cfg.num_hidden_layers, text_cfg.num_attention_heads,
        text_cfg.num_key_value_heads, text_cfg.head_dim, text_cfg.vocab_size,
        text_cfg.rope_theta, text_cfg.tie_word_embeddings)

    # ---- build the standard Qwen3ForCausalLM trunk ----
    from transformers.models.qwen3.configuration_qwen3 import Qwen3Config

    std_cfg = Qwen3Config(**{k: v for k, v in text_cfg.to_dict().items()
                             if k in Qwen3Config().to_dict()})
    std_cfg.architectures = ["Qwen3ForCausalLM"]
    std = Qwen3ForCausalLM(std_cfg)
    std.eval()

    src = dict(thinker.model.named_parameters())
    dst = dict(std.model.named_parameters())
    log("trunk params: src=%d dst=%d" % (len(src), len(dst)))
    missing = sorted(set(dst) - set(src))
    extra = sorted(set(src) - set(dst))
    log("missing in src: %s" % missing[:10])
    log("extra in src:   %s" % extra[:10])

    copied, mism = 0, []
    with torch.no_grad():
        for k in dst:
            if k in src and src[k].shape == dst[k].shape:
                dst[k].copy_(src[k])
                copied += 1
            else:
                mism.append((k, tuple(dst[k].shape)))
        # lm_head: tie_word_embeddings=True -> shared with embed_tokens
        if text_cfg.tie_word_embeddings:
            std.lm_head.weight.copy_(thinker.lm_head.weight)
            copied += 1
    log("copied %d tensors, mismatched %d" % (copied, len(mism)))
    if mism:
        for k, s in mism[:10]:
            log("  MISMATCH %s %s" % (k, s))

    tok = AutoTokenizer.from_pretrained(HF)
    results = {}

    def prep(text, n_pad=0):
        ids = tok(text, return_tensors="pt").input_ids
        if n_pad:
            ids = torch.cat([torch.zeros(1, n_pad, dtype=ids.dtype), ids], dim=1)
        return ids

    def run_trunk(ids, steps=1):
        """Run the ORIGINAL thinker trunk with inputs_embeds, greedy, use_cache."""
        emb = thinker.model.embed_tokens(ids)
        am = torch.ones(1, ids.shape[1], dtype=torch.long)
        from transformers import DynamicCache
        cache = DynamicCache()
        pos = None
        out_tokens = []
        logits = None
        cur = emb
        cur_ids = ids
        for s in range(steps):
            if s == 0:
                p, _ = thinker.get_rope_index(am)
            else:
                p = p[:, :, -1:] + 1
            o = thinker.model(
                inputs_embeds=cur,
                attention_mask=am,
                position_ids=p,
                past_key_values=cache,
                use_cache=True,
            )
            logits = thinker.lm_head(o.last_hidden_state)
            nxt = logits[:, -1, :].argmax(-1)
            out_tokens.append(int(nxt))
            cache = o.past_key_values
            am = torch.cat([am, torch.ones(1, 1, dtype=am.dtype)], dim=1)
            cur = thinker.model.embed_tokens(nxt.view(1, 1))
            cur_ids = cur
        return logits, out_tokens, emb

    def run_std(emb, steps=1):
        """Run the standard Qwen3ForCausalLM on the SAME inputs_embeds."""
        from transformers import DynamicCache
        cache = DynamicCache()
        am = torch.ones(1, emb.shape[1], dtype=torch.long)
        cur = emb
        out_tokens = []
        logits = None
        for s in range(steps):
            o = std(
                inputs_embeds=cur,
                attention_mask=am,
                past_key_values=cache,
                use_cache=True,
            )
            logits = o.logits
            nxt = logits[:, -1, :].argmax(-1)
            out_tokens.append(int(nxt))
            cache = o.past_key_values
            am = torch.cat([am, torch.ones(1, 1, dtype=am.dtype)], dim=1)
            cur = std.model.embed_tokens(nxt.view(1, 1))
        return logits, out_tokens

    cases = [
        ("prompt_plain", PROMPT, 0, 6),
        ("prompt_pad7", PROMPT, 7, 6),
        ("prompt2", PROMPT2, 0, 6),
    ]
    all_cases = []
    for name, text, pad, steps in cases:
        ids = prep(text, pad)
        with torch.no_grad():
            lt, tt, emb = run_trunk(ids, steps)
            ls, ts = run_std(emb, steps)
        cos = float(torch.nn.functional.cosine_similarity(
            lt[0, -1, :].double(), ls[0, -1, :].double(), dim=0))
        agree = tt == ts
        case = dict(case=name, seq_len=int(ids.shape[1]), steps=steps,
                    logits_cosine=cos,
                    argmax_match_per_step=[int(a == b) for a, b in zip(tt, ts)],
                    tokens_thinker=tt, tokens_std=ts,
                    logit_absmax=float((lt[0, -1, :] - ls[0, -1, :]).abs().max()),
                    logit_absmax_rel=float((lt[0, -1, :] - ls[0, -1, :]).abs().max()
                                           / lt[0, -1, :].abs().max()))
        all_cases.append(case)
        log("[%s] len=%d steps=%d cos=%.6f argmax_match=%s tokens=%s",
            name, case["seq_len"], steps, cos, all(case["argmax_match_per_step"]), tt)
        results[name] = case

    min_cos = min(c["logits_cosine"] for c in all_cases)
    all_match = all(all(c["argmax_match_per_step"]) for c in all_cases)
    verdict = dict(
        min_logits_cosine=min_cos,
        all_argmax_match=all_match,
        threshold=0.9999,
        pass_=(bool(min_cos >= 0.9999 and all_match)),
        weights_copied=copied,
        weight_mismatches=[(k, list(s)) for k, s in mism],
        cases=all_cases,
        seconds=round(time.time() - t0, 1),
    )
    log("=" * 60)
    log("VERDICT: min_cos=%.6f (need >=0.9999) all_argmax_match=%s -> %s",
        min_cos, all_match, "PASS" if verdict["pass_"] else "FAIL")
    log("=" * 60)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)
    log("wrote %s" % OUT)
    return 0 if verdict["pass_"] else 1


if __name__ == "__main__":
    sys.exit(main())
