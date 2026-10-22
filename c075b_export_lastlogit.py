"""C-075#2: export IR variants whose lm_head runs on the LAST position only.

optimum's text-generation-with-past export emits `logits [?,?,151936]`, i.e. it
runs lm_head over ALL T positions. At T=256 that is ~80 GFLOP plus a large output
tensor; that is why the same IR costs 194/282/403 ms on GPU for T=256/384/512
while the production GPU prefill is a flat 94 ms (production only uses the last
position). So the "same IR on GPU" comparison must be made FAIR before drawing
any NPU-vs-GPU conclusion.

In-graph surgery is not possible here: lm_head's input is a DescriptorTensor
(a state variable) and OpenVINO's opset builders cannot attach to it
("Unidentified data type dtype('O')"). So we re-export with a patched forward.

Method: monkeypatch `Qwen3ForCausalLM.forward` to slice the last position before
lm_head, then call optimum's own `main_export` (the code path optimum-cli uses),
so the result is still a STANDARD stateful LLM that NPUW_LLM can consume.
"""
import json
import os
import sys
import time

import torch

WORK = os.path.dirname(os.path.abspath(__file__))
LM = os.path.join(WORK, "models", "hf-qwen3-lm")

# output filename produced by optimum (OpenVINOConverter default)
OV_NAME = "openvino_model"


def log(*a):
    print(*a, flush=True)


def patched_forward(self, input_ids=None, attention_mask=None, position_ids=None,
                    inputs_embeds=None, past_key_values=None, use_cache=None, **kw):
    from transformers.modeling_outputs import CausalLMOutputWithPast
    out = self.model(input_ids=input_ids,
                     attention_mask=attention_mask,
                     position_ids=position_ids,
                     inputs_embeds=inputs_embeds,
                     past_key_values=past_key_values,
                     use_cache=use_cache, **kw)
    h = out.last_hidden_state[:, -1:, :]
    return CausalLMOutputWithPast(
        logits=self.lm_head(h),
        past_key_values=out.past_key_values,
        hidden_states=out.hidden_states,
        attentions=out.attentions,
    )


def main():
    from transformers import Qwen3ForCausalLM
    orig = Qwen3ForCausalLM.forward
    Qwen3ForCausalLM.forward = patched_forward
    log("patched Qwen3ForCausalLM.forward -> last-position lm_head")

    # torch-level sanity before exporting
    from transformers import AutoTokenizer
    m = Qwen3ForCausalLM.from_pretrained(LM, dtype=torch.float32)
    m.eval()
    tok = AutoTokenizer.from_pretrained(LM)
    ids = tok("system\n转写音频。\nassistant\n今天天气怎么样？",
              return_tensors="pt").input_ids
    with torch.no_grad():
        Qwen3ForCausalLM.forward = orig
        full = m(input_ids=ids).logits[0, -1, :]
        Qwen3ForCausalLM.forward = patched_forward
        cut = m(input_ids=ids).logits[0, -1, :]
    ok = int(full.argmax()) == int(cut.argmax())
    log("sanity: full argmax=%d cut argmax=%d match=%s"
        % (full.argmax(), cut.argmax(), ok))
    if not ok:
        log("sanity FAILED -> abort")
        return 1
    del m

    # Persist the patched model so optimum-cli (which correctly applies the
    # int4 per-channel args) can export it from disk. main_export() silently
    # ignored our weight_format, producing two identical int8 models.
    import shutil
    patched_dir = os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit")
    os.makedirs(patched_dir, exist_ok=True)
    m2 = Qwen3ForCausalLM.from_pretrained(LM, dtype=torch.float32)
    m2.forward = patched_forward.__get__(m2, Qwen3ForCausalLM)
    # transformers refuses to save a generation_config with do_sample=False +
    # temperature set; drop it so save_pretrained succeeds (greedy is the target).
    if hasattr(m2, "generation_config"):
        gc = m2.generation_config
        for k in ("temperature", "top_p", "top_k"):
            if getattr(gc, k, None) is not None:
                setattr(gc, k, None)
    m2.save_pretrained(patched_dir, safe_serialization=True)
    tok.save_pretrained(patched_dir)
    log("saved patched model -> %s" % patched_dir)
    del m2

    from optimum.exporters.openvino.__main__ import main_export

    variants = [
        ("int8sym-lastlogit", "int8", ["--sym"]),
        ("int4sym-lastlogit", "int4", ["--sym", "--ratio", "1.0",
                                       "--group-size", "-1",
                                       "--group-size-fallback", "ignore"]),
    ]
    results = {}
    for name, fmt, extra in variants:
        dst = os.path.join(WORK, "models", f"qwen3-lm-{name}-ov")
        log("=" * 70)
        log("exporting %s -> %s   args=%s" % (fmt, os.path.basename(dst), extra))
        t0 = time.time()
        main_export(patched_dir, dst,
                    task="text-generation-with-past",
                    weight_format=fmt,
                    do_convert_tokenizer=False,
                    sym=True,
                    ratio=1.0,
                    group_size=-1,
                    group_size_fallback="ignore")
        log("  done in %.1fs" % (time.time() - t0))

        import openvino as ov
        core = ov.Core()
        xml = os.path.join(dst, "openvino_model.xml")
        if not os.path.exists(xml):
            log("  !! no IR produced")
            results[name] = dict(ok=False, dir=dst)
            continue
        mm = core.read_model(xml)
        outs = [(o.get_any_name(), str(o.get_partial_shape())) for o in mm.outputs]
        ins = [(i.get_any_name(), str(i.get_partial_shape())) for i in mm.inputs]
        log("  inputs : %s" % ins)
        log("  outputs: %s" % outs)
        results[name] = dict(
            ok=True, dir=dst, inputs=ins, outputs=outs,
            size_mib=round(os.path.getsize(
                os.path.join(dst, "openvino_model.bin")) / 1048576, 1))

    Qwen3ForCausalLM.forward = orig
    with open(os.path.join(WORK, "reports", "c075b_lastlogit_export.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log("wrote reports/c075b_lastlogit_export.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
