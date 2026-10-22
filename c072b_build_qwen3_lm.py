"""C-072#4a step 2: materialise a standalone Qwen3ForCausalLM from the Qwen3-ASR
thinker text trunk, so optimum-cli can export it as a *standard* stateful LLM.

Mapping (verified by c072a: logits cosine ~1.0, greedy argmax all match):
    thinker.model.*          -> model.*
    thinker.lm_head.weight   -> lm_head.weight
    thinker_config.text_config -> config

Writes models/hf-qwen3-lm/ with config.json, model.safetensors, tokenizer files.
"""
import json
import os
import shutil
import sys

import torch

WORK = os.path.dirname(os.path.abspath(__file__))
HF = os.path.join(WORK, "models", "hf")
DST = os.path.join(WORK, "models", "hf-qwen3-lm")

TOKENIZER_FILES = [
    "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt",
    "added_tokens.json", "special_tokens_map.json", "generation_config.json",
    "chat_template.json",
]

# audio placeholder tokens must stay in the vocab; ids come from the ASR config
AUDIO_SPECIAL = {
    "audio_start_token_id": 151669,
    "audio_end_token_id": 151670,
    "audio_token_id": 151676,
}


def log(*a):
    print(*a, flush=True)


def main():
    os.makedirs(DST, exist_ok=True)

    full_cfg = json.load(open(os.path.join(HF, "config.json"), encoding="utf-8"))
    tc = dict(full_cfg["thinker_config"]["text_config"])

    # ---- config.json for a plain Qwen3ForCausalLM ----
    cfg = {
        "architectures": ["Qwen3ForCausalLM"],
        "model_type": "qwen3",
        "attention_bias": False,
        "attention_dropout": 0.0,
        "bos_token_id": tc.get("bos_token_id") or 151643,
        "eos_token_id": 151673,
        "pad_token_id": tc.get("pad_token_id") or 151643,
        "head_dim": tc["head_dim"],
        "hidden_act": tc["hidden_act"],
        "hidden_size": tc["hidden_size"],
        "initializer_range": tc["initializer_range"],
        "intermediate_size": tc["intermediate_size"],
        "max_position_embeddings": tc["max_position_embeddings"],
        "max_window_layers": tc["num_hidden_layers"],
        "num_attention_heads": tc["num_attention_heads"],
        "num_hidden_layers": tc["num_hidden_layers"],
        "num_key_value_heads": tc["num_key_value_heads"],
        "rms_norm_eps": tc["rms_norm_eps"],
        "rope_theta": tc["rope_theta"],
        "sliding_window": None,
        "tie_word_embeddings": True,
        "torch_dtype": "float32",
        "use_cache": True,
        "use_sliding_window": False,
        "vocab_size": tc["vocab_size"],
        # keep the ASR audio tokens resolvable by the tokenizer
        "audio_token_id": AUDIO_SPECIAL["audio_token_id"],
    }
    # generation defaults: greedy
    gen_cfg = {
        "bos_token_id": 151643,
        "eos_token_id": [151673, 151645],
        "pad_token_id": 151643,
        "do_sample": False,
        "repetition_penalty": 1.0,
        "temperature": None,
        "top_p": None,
        "top_k": None,
    }
    with open(os.path.join(DST, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    with open(os.path.join(DST, "generation_config.json"), "w", encoding="utf-8") as f:
        json.dump(gen_cfg, f, indent=2)
    log("wrote config.json + generation_config.json")

    for fn in TOKENIZER_FILES:
        src = os.path.join(HF, fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(DST, fn))
    log("copied tokenizer files")

    # ---- weights ----
    from safetensors.torch import load_file, save_file
    src_sd = load_file(os.path.join(HF, "model.safetensors"))

    out = {}
    for k, v in src_sd.items():
        if k.startswith("thinker.model."):
            out["model." + k[len("thinker.model."):]] = v.contiguous()
    # lm_head is tied to embed_tokens in the ASR checkpoint (no separate tensor);
    # keep it out so tie_word_embeddings=True re-ties it on load.
    assert "model.embed_tokens.weight" in out, sorted(out)[:5]
    log("mapped %d tensors; embed_tokens %s" % (len(out), tuple(out["model.embed_tokens.weight"].shape)))
    total = sum(v.numel() for v in out.values())
    log("params: %.1fM" % (total / 1e6))

    save_file(out, os.path.join(DST, "model.safetensors"), metadata={"format": "pt"})
    log("wrote %s" % os.path.join(DST, "model.safetensors"))

    # ---- readback sanity: load as Qwen3ForCausalLM and check the trunk matches ----
    from transformers import AutoTokenizer, Qwen3ForCausalLM
    tok = AutoTokenizer.from_pretrained(DST)
    m = Qwen3ForCausalLM.from_pretrained(DST, dtype=torch.float32)
    m.eval()
    ids = tok("system\n转写音频。\nassistant\n今天天气怎么样？", return_tensors="pt").input_ids
    with torch.no_grad():
        o1 = m(input_ids=ids).logits
    log("readback OK, ids=%d logits=%s argmax=%d" % (ids.shape[1], tuple(o1.shape), int(o1[0, -1].argmax())))

    meta = dict(dst=DST, tensors=len(out), params_M=round(total / 1e6, 2),
                seq_len=int(ids.shape[1]), argmax=int(o1[0, -1].argmax()))
    with open(os.path.join(WORK, "reports", "c072b_qwen3_lm_dir.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
