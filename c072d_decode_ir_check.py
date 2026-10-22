"""C-072#2 / C-073#2: verify the OV decode IR itself on OV CPU.

c070q only validated the handwritten cache math on the TORCH side. It never
checked the exported OV decode IR. So the "NPU is numerically wrong" claim is
unproven -- the IR could be wrong on every device.

This script:
  1. runs ov-dec-stateful-prefill on OV CPU, captures its KV state
     (req.query_state()),
  2. WRITES that state into the decode IR via `s.state = ov.Tensor(arr)`
     (the Python binding of C++ VariableState::set_state),
  3. runs decode0 / decode1 and compares logits against the source torch model
     with use_cache=True doing the same steps.

Verdict matrix:
  CPU decode wrong            -> the export math is wrong (device-independent)
  CPU right, NPU wrong (c070p) -> genuinely an NPU numeric/state issue
"""
import json
import os
import sys

import numpy as np
import torch

WORK = os.path.dirname(os.path.abspath(__file__))
PRE = os.path.join(WORK, "models", "ov-dec-stateful-prefill", "openvino_decoder_model.xml")
DEC0 = os.path.join(WORK, "models", "ov-dec-stateful-decode0", "openvino_decoder_model.xml")
DEC1 = os.path.join(WORK, "models", "ov-dec-stateful-decode1", "openvino_decoder_model.xml")
OUT = os.path.join(WORK, "reports", "c072d_decode_ir_cpu_check.json")

T_PREFILL = 384          # c070o prefill graph was exported at T=384
N_DECODE_STEPS = 2
SEED = 7


def log(*a):
    print(*a, flush=True)


def cosine(a, b):
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))


def main():
    import openvino as ov
    core = ov.Core()

    log("loading prefill/decode IRs on CPU ...")
    cm_pre = core.compile_model(core.read_model(PRE), "CPU")
    cm_d0 = core.compile_model(core.read_model(DEC0), "CPU")
    cm_d1 = core.compile_model(core.read_model(DEC1), "CPU")

    for name, cm in (("prefill", cm_pre), ("decode0", cm_d0), ("decode1", cm_d1)):
        log("%s inputs : %s" % (name, [(i.get_any_name(), str(i.get_partial_shape()))
                                       for i in cm.inputs]))
        log("%s outputs: %s" % (name, [(o.get_any_name(), str(o.get_partial_shape()))
                                       for o in cm.outputs]))

    # ---------- torch reference ----------
    log("loading torch source model ...")
    from transformers import AutoTokenizer
    from qwen_asr.core.transformers_backend.modeling_qwen3_asr import (
        Qwen3ASRForConditionalGeneration,
    )
    hf = os.path.join(WORK, "models", "hf")
    full = Qwen3ASRForConditionalGeneration.from_pretrained(hf, dtype=torch.float32)
    full.eval()
    thinker = full.thinker

    rng = np.random.default_rng(SEED)
    ids = rng.integers(100, 140000, size=(1, T_PREFILL)).astype(np.int64)

    # torch: prefill with use_cache=True, then 2 decode steps
    from transformers import DynamicCache
    with torch.no_grad():
        emb = thinker.model.embed_tokens(torch.from_numpy(ids))
        am = torch.ones(1, T_PREFILL, dtype=torch.long)
        pos, _ = thinker.get_rope_index(am)
        cache = DynamicCache()
        o = thinker.model(inputs_embeds=emb, attention_mask=am, position_ids=pos,
                          past_key_values=cache, use_cache=True)
        ref_logits = [thinker.lm_head(o.last_hidden_state)[0, -1, :].numpy().copy()]
        cache = o.past_key_values
        nxt = torch.from_numpy(ref_logits[0].argmax(0)[None, None].astype(np.int64))
        for step in range(N_DECODE_STEPS):
            am = torch.cat([am, torch.ones(1, 1, dtype=am.dtype)], dim=1)
            emb1 = thinker.model.embed_tokens(nxt)
            pos1 = pos[:, :, -1:] + 1 + step
            o = thinker.model(inputs_embeds=emb1, attention_mask=am, position_ids=pos1,
                              past_key_values=cache, use_cache=True)
            lg = thinker.lm_head(o.last_hidden_state)[0, -1, :].numpy().copy()
            ref_logits.append(lg)
            cache = o.past_key_values
            nxt = torch.from_numpy(lg.argmax(0)[None, None].astype(np.int64))
    log("torch reference tokens: %s" % [int(x.argmax()) for x in ref_logits])

    # ---------- OV: prefill then hand the state to decode ----------
    with torch.no_grad():
        emb = thinker.model.embed_tokens(torch.from_numpy(ids)).detach().numpy().astype(np.float32)
    beam = np.array([0], dtype=np.int32)

    req_pre = cm_pre.create_infer_request()
    req_pre.reset_state()
    req_pre.infer({"inputs_embeds": emb, "beam_idx": beam})
    t = req_pre.get_tensor(cm_pre.outputs[0])
    ov_pre_logits = np.array(t.data, dtype=np.float32).copy()
    ov_pre_logits = ov_pre_logits[0, -1, :]

    states = req_pre.query_state()
    log("prefill query_state -> %d states" % len(states))
    for s in list(states)[:3]:
        log("   state name=%s dtype=%s shape=%s"
            % (s.name, s.state.get_element_type(), s.state.get_shape()))

    cos_pre = cosine(ov_pre_logits, ref_logits[0])
    am_pre = int(ov_pre_logits.argmax()) == int(ref_logits[0].argmax())
    log("prefill  ov-vs-torch: cos=%.6f argmax ov=%d torch=%d match=%s"
        % (cos_pre, ov_pre_logits.argmax(), ref_logits[0].argmax(), am_pre))

    steps = []
    cur_tok = int(ref_logits[0].argmax())
    pre_by_name = {s.name: np.array(s.state.data, copy=True) for s in states}
    for step, cm in enumerate((cm_d0, cm_d1)):
        req = cm.create_infer_request()
        req.reset_state()
        # inject the prefill KV state into the decode graph (C++ VariableState::set_state)
        dec_states = req.query_state()
        if step == 0:
            log("decode0 query_state -> %d states (e.g. %s)"
                % (len(dec_states), dec_states[0].name))
        n_set = 0
        for s in dec_states:
            nm = s.name
            if nm in pre_by_name:
                s.state = ov.Tensor(np.ascontiguousarray(pre_by_name[nm]))
                n_set += 1
        if step == 0:
            log("injected %d/%d states by name" % (n_set, len(dec_states)))
        with torch.no_grad():
            e = thinker.model.embed_tokens(
                torch.from_numpy(np.array([[cur_tok]], dtype=np.int64))
            ).detach().numpy().astype(np.float32)
        req.infer({"inputs_embeds": e, "beam_idx": beam})
        t = req.get_tensor(cm.outputs[0])
        lg = np.array(t.data, dtype=np.float32).copy()[0, -1, :]
        ref = ref_logits[step + 1]
        c = cosine(lg, ref)
        am = int(lg.argmax()) == int(ref.argmax())
        steps.append(dict(step=step, graph=f"decode{step}", cosine=c,
                          argmax_ov=int(lg.argmax()), argmax_torch=int(ref.argmax()),
                          argmax_match=am, absmax=float(np.abs(lg - ref).max())))
        log("decode%d ov-vs-torch: cos=%.6f argmax ov=%d torch=%d match=%s absmax=%.4g"
            % (step, c, lg.argmax(), ref.argmax(), am, steps[-1]["absmax"]))
        cur_tok = int(lg.argmax())

    all_ok = am_pre and all(s["argmax_match"] and s["cosine"] >= 0.999 for s in steps)
    verdict = dict(
        prefill=dict(cosine=cos_pre, argmax_match=am_pre),
        decode_steps=steps,
        all_pass=bool(all_ok),
        interpretation=("decode IR is CORRECT on OV CPU -> the c070p NPU decode "
                        "mismatch is an NPU-side state/numeric issue"
                        if all_ok else
                        "decode IR is WRONG even on OV CPU -> the c070o export math "
                        "is wrong; c070q only proved the torch-side manual math"),
        seconds=None,
    )
    log("=" * 70)
    log("VERDICT: decode IR on OV CPU all_pass=%s" % all_ok)
    log("  -> %s" % verdict["interpretation"])
    log("=" * 70)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)
    log("wrote %s" % OUT)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
