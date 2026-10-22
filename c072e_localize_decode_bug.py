"""C-072#2 follow-up: attribute the OV decode-IR mismatch.

c072d showed the decode IR is wrong even on OV CPU (cos 0.436), which kills the
"NPU numeric issue" explanation. But that test injected state read from the
prefill IR, so the failure could be either:
  (A) the prefill IR's state is bad, or
  (B) the decode IR's own math is bad.

Decisive check: pull layer-0 key slot 383 (the LAST written slot) out of the
prefill IR and compare against the source model's layer-0 key at position 383.
If they agree, (A) is exonerated and the bug is inside the decode graph.
Also compares the UNUSED tail slots: if the prefill graph left stale non-zero
garbage past position 384, decode would attend to it and be wrong even though
the used slots are perfect -- the causal mask should prevent that, so this is
exactly where a hand-written graph typically breaks.
"""
import json
import os
import sys

import numpy as np
import torch

WORK = os.path.dirname(os.path.abspath(__file__))
PRE = os.path.join(WORK, "models", "ov-dec-stateful-prefill", "openvino_decoder_model.xml")
DEC0 = os.path.join(WORK, "models", "ov-dec-stateful-decode0", "openvino_decoder_model.xml")
OUT = os.path.join(WORK, "reports", "c072e_decode_bug_localisation.json")

T_PREFILL = 384
SEED = 7


def log(*a):
    print(*a, flush=True)


def cosine(a, b):
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))


def main():
    import openvino as ov
    from transformers import DynamicCache
    from qwen_asr.core.transformers_backend.modeling_qwen3_asr import (
        Qwen3ASRForConditionalGeneration,
    )
    core = ov.Core()

    full = Qwen3ASRForConditionalGeneration.from_pretrained(
        os.path.join(WORK, "models", "hf"), dtype=torch.float32)
    full.eval()
    thinker = full.thinker

    ids = np.random.default_rng(SEED).integers(
        100, 140000, size=(1, T_PREFILL)).astype(np.int64)
    with torch.no_grad():
        emb_t = thinker.model.embed_tokens(torch.from_numpy(ids))
        am = torch.ones(1, T_PREFILL, dtype=torch.long)
        pos, _ = thinker.get_rope_index(am)
        o = thinker.model(inputs_embeds=emb_t, attention_mask=am, position_ids=pos,
                          past_key_values=DynamicCache(), use_cache=True)
        ref_cache = o.past_key_values

    def src_kv(layer):
        k = ref_cache.layers[layer].keys if hasattr(ref_cache, "layers") else ref_cache.key_cache[layer]
        v = ref_cache.layers[layer].values if hasattr(ref_cache, "layers") else ref_cache.value_cache[layer]
        return k, v

    emb = emb_t.detach().numpy().astype(np.float32)
    beam = np.array([0], dtype=np.int32)

    cm_pre = core.compile_model(core.read_model(PRE), "CPU")
    req = cm_pre.create_infer_request()
    req.reset_state()
    req.infer({"inputs_embeds": emb, "beam_idx": beam})
    states = {s.name: np.array(s.state.data, copy=True) for s in req.query_state()}
    log("prefill IR states: %d (e.g. %s shape=%s)"
        % (len(states), list(states)[0], list(states.values())[0].shape))

    report = {"checks": [], "n_states": len(states)}
    keys_by_layer = {}
    for name, arr in states.items():
        # names look like past_key.13present_key.13
        if "present_key" in name:
            layer = int(name.split("present_key.")[-1])
            keys_by_layer[layer] = arr
    log("parsed %d present_key states" % len(keys_by_layer))

    worst_used, worst_tail = 1.0, 0.0
    for layer in sorted(keys_by_layer)[:4]:
        kv_ov = keys_by_layer[layer]            # [1, n_kv, 512, hd]
        k_src, _ = src_kv(layer)
        k_src = k_src[0].detach().numpy()       # [n_kv, T, hd]
        n_kv = k_src.shape[0]
        # last WRITTEN slot
        used = kv_ov[:, :, T_PREFILL - 1, :]   # [1,n_kv,hd]
        c_used = cosine(used[0], k_src[:, T_PREFILL - 1, :])
        # first UNWRITTEN slot (should be zero in a clean graph)
        tail = kv_ov[:, :, T_PREFILL, :]
        tail_absmax = float(np.abs(tail).max())
        # mean abs over all written slots vs source, per kv head
        c_first = cosine(kv_ov[0, :, 0, :], k_src[:, 0, :])
        c_mid = cosine(kv_ov[0, :, T_PREFILL // 2, :], k_src[:, T_PREFILL // 2, :])
        worst_used = min(worst_used, c_used, c_first, c_mid)
        worst_tail = max(worst_tail, tail_absmax)
        log("layer %2d  cos(slot0)=%.6f cos(slot192)=%.6f cos(slot383)=%.6f  "
            "tail_slot384_absmax=%.4g"
            % (layer, c_first, c_mid, c_used, tail_absmax))
        report["checks"].append(dict(
            layer=layer, cos_slot0=c_first, cos_slot_mid=c_mid, cos_slot_last=c_used,
            tail_slot_absmax=tail_absmax,
            written_slots_absmax=float(np.abs(kv_ov[:, :, :T_PREFILL, :]).max())))

    report["verdict_prefill_state"] = (
        "CLEAN -- prefill IR writes correct KV and zeroes the tail"
        if worst_used >= 0.999 and worst_tail < 1e-3
        else "SUSPECT -- prefill IR state itself is wrong")
    log("=" * 70)
    log("prefill-state verdict: %s  (worst used cos=%.6f, tail absmax=%.4g)"
        % (report["verdict_prefill_state"], worst_used, worst_tail))
    log("=" * 70)


    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log("wrote %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
