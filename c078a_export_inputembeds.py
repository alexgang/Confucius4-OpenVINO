"""C-078#3 / C-075#5#1: export lastlogit IRs that also accept `inputs_embeds`.

Why this shape of change:
  * The ASR thinker merges audio into the text embeddings with
        inputs_embeds = inputs_embeds.masked_scatter(audio_mask, audio_features)
    where audio_mask selects the positions of `audio_token_id`
    (modeling_qwen3_asr.py:1202-1203). So the decoder never sees token ids for
    the audio span -- it sees encoder features at those slots.
  * NPUW itself looks for an `inputs_embeds` port
    (DLL string: `find_port_by_name(..., layer_names::inputs_embeds)`), and
    separately needs `input_ids` for `text_mask` ("input_ids port not
    initialized for text_mask").
  => The export must expose BOTH: `input_ids` (still fed with the real ids, so
     NPUW can build its mask) and `inputs_embeds` (which overrides the embedding
     lookup, carrying the scattered audio features).

So we patch the forward to prefer inputs_embeds when given, keep input_ids as a
real port, and -- crucially -- still apply last-position-only lm_head.

AOV-style two-input export: optimum needs both ports declared, so we save a
model whose forward signature has `input_ids` and `inputs_embeds`.
"""
import json
import os
import sys
import time

import torch
from transformers.modeling_outputs import CausalLMOutputWithPast

WORK = os.path.dirname(os.path.abspath(__file__))
LM = os.path.join(WORK, "models", "hf-qwen3-lm")


def log(*a):
    print(*a, flush=True)


def patched_forward(self, input_ids=None, attention_mask=None, position_ids=None,
                    inputs_embeds=None, past_key_values=None, use_cache=None, **kw):
    """last-position lm_head + inputs_embeds support, input_ids kept as a port."""
    # embed_tokens is still traced so that `input_ids` remains a graph input and
    # NPUW can use it for text_mask; when inputs_embeds is supplied it wins.
    if inputs_embeds is None:
        inputs_embeds = self.model.embed_tokens(input_ids)
    out = self.model(input_ids=None,
                     attention_mask=attention_mask,
                     position_ids=position_ids,
                     inputs_embeds=inputs_embeds,
                     past_key_values=past_key_values,
                     use_cache=use_cache, **kw)
    return CausalLMOutputWithPast(
        logits=self.lm_head(out.last_hidden_state[:, -1:, :]),
        past_key_values=out.past_key_values,
        hidden_states=out.hidden_states,
        attentions=out.attentions)


def main():
    from transformers import AutoTokenizer, Qwen3ForCausalLM
    orig = Qwen3ForCausalLM.forward
    Qwen3ForCausalLM.forward = patched_forward
    log("patched forward: last-position lm_head + inputs_embeds override")

    m = Qwen3ForCausalLM.from_pretrained(LM, dtype=torch.float32)
    tok = AutoTokenizer.from_pretrained(LM)
    ids = tok("system\n转写音频。\nassistant\n今天天气怎么样？",
              return_tensors="pt").input_ids
    with torch.no_grad():
        Qwen3ForCausalLM.forward = orig
        ref = m(input_ids=ids).logits[0, -1, :]
        Qwen3ForCausalLM.forward = patched_forward
        a = m(input_ids=ids).logits[0, -1, :]
        # feeding the same thing via inputs_embeds must give the same answer
        emb = m.model.embed_tokens(ids)
        b = m(input_ids=ids, inputs_embeds=emb).logits[0, -1, :]
    ok = int(ref.argmax()) == int(a.argmax()) == int(b.argmax())
    log("sanity: ref=%d patched=%d via_embeds=%d -> %s"
        % (ref.argmax(), a.argmax(), b.argmax(), ok))
    if not ok:
        log("sanity FAILED")
        return 1
    del m

    patched_dir = os.path.join(WORK, "models", "hf-qwen3-lm-inputembeds")
    os.makedirs(patched_dir, exist_ok=True)
    m2 = Qwen3ForCausalLM.from_pretrained(LM, dtype=torch.float32)
    m2.forward = patched_forward.__get__(m2, Qwen3ForCausalLM)
    if hasattr(m2, "generation_config"):
        for k in ("temperature", "top_p", "top_k"):
            if getattr(m2.generation_config, k, None) is not None:
                setattr(m2.generation_config, k, None)
    m2.save_pretrained(patched_dir, safe_serialization=True)
    tok.save_pretrained(patched_dir)
    log("saved patched model -> %s" % patched_dir)
    Qwen3ForCausalLM.forward = orig
    with open(os.path.join(WORK, "reports", "c078a_inputembeds_patch.json"), "w",
              encoding="utf-8") as f:
        json.dump(dict(dir=patched_dir, sanity_argmax_all_equal=bool(ok)), f, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
