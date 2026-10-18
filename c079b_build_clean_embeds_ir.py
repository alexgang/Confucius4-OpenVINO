"""C-079#2: build a clean embeddings-only decoder IR, with no `input_ids` port.

Why this is the right shape
---------------------------
Strings extracted from openvino_genai.dll (multimodal_embedding_pipeline_impl.cpp)
spell out the contract of the embeddings-based path:

    "Language model must expose 'inputs_embeds' input for EmbeddingPipeline"
    has_lm_input("inputs_embeds")
    "inputs_embeds must be float32 for EmbeddingPipeline batching"
    item.inputs_embeds.get_element_type() == ov::element::f32
    "Expected position_ids to have rank 3"
    first_pos_shape.size() == 3

Note what is absent from that contract: `input_ids`. genai's language-model
half for VLM has inputs_embeds + attention_mask + position_ids (+ beam_idx)
and no token ids at all.

That matters because every variant tried so far KEPT `input_ids`
("4 ports + ie"). If NPUW_LLM selects its execution path by inspecting which
ports exist -- token path when input_ids is present, embedding path when only
inputs_embeds is -- then keeping input_ids is exactly what forced the token
path and made the caller's inputs_embeds invisible.

So this script builds the shape genai expects:
  * cut the embed_tokens Gather, feed its consumers from the new Parameter
  * REMOVE the input_ids Parameter entirely (`model.remove_parameter`)
  * name the embedding port `inputs_embeds`, shape [1, 1..512, 2048]
    (512 was measured to work on both CPU and NPU; unbounded and 2**62 do not)
  * keep attention_mask / position_ids / beam_idx

Caveat to check afterwards: `position_ids` is rank 2 here while genai expects
rank 3. That is a genuine difference from the genai contract, and it is
reported rather than assumed fine.

Verification performed on the result:
  * CPU runtime with two different inputs_embeds tensors -> must differ,
    otherwise the port is decorative
  * the same test on NPU
"""
import json
import os
import shutil
import sys

import numpy as np
import openvino as ov
from openvino import opset15 as ops

WORK = os.path.dirname(os.path.abspath(__file__))
PAIRS = [
    ("qwen3-lm-int8sym-lastlogit-ov", "qwen3-lm-int8sym-cleanie-ov"),
    ("qwen3-lm-int4sym-lastlogit-ov", "qwen3-lm-int4sym-cleanie-ov"),
]
MAX_TOK = 512
HIDDEN = 2048
NPUW_PROPS = {
    "NPU_USE_NPUW": "YES",
    "NPUW_LLM": "YES",
    "NPUW_LLM_MAX_PROMPT_LEN": "512",
    "NPUW_LLM_MIN_RESPONSE_LEN": "64",
}


def log(*a):
    print(*a, flush=True)


def copy_aux(src_dir, dst_dir):
    s = os.path.join(WORK, "models", src_dir)
    d = os.path.join(WORK, "models", dst_dir)
    os.makedirs(d, exist_ok=True)
    for fn in os.listdir(s):
        if fn.startswith("openvino_model."):
            continue
        sp = os.path.join(s, fn)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(d, fn))


def build(src_dir, dst_dir):
    core = ov.Core()
    model = core.read_model(
        os.path.join(WORK, "models", src_dir, "openvino_model.xml"))
    g = None
    for n in model.get_ordered_ops():
        if n.get_type_name() == "Gather" and \
                "embed_tokens" in n.get_friendly_name():
            g = n
            break
    if g is None:
        return None, {"error": "embedding gather not found"}
    consumers = list(g.output(0).get_target_inputs())
    log("[%s] gather consumers=%d" % (src_dir, len(consumers)))

    param = ops.parameter(
        ov.PartialShape([1, ov.Dimension(1, MAX_TOK), HIDDEN]), ov.Type.f32)
    param.set_friendly_name("inputs_embeds")
    param.output(0).get_tensor().set_names({"inputs_embeds"})
    model.add_parameters([param])
    for u in consumers:
        u.replace_source_output(param.output(0))

    # input_ids may still be used by the position-id / mask arithmetic that
    # optimum baked in. Those must go too, otherwise NPUW still sees a token
    # port. Report exactly what we remove.
    ids_users = []
    for p in list(model.inputs):
        if p.get_any_name() != "input_ids":
            continue
        users = [(u.get_node().get_type_name(),
                  u.get_node().get_friendly_name())
                 for u in p.get_target_inputs()]
        log("[%s] input_ids consumers before removal: %s" % (src_dir, users))
        # cut every consumer first: leftover nodes would either keep the port
        # alive (ShapeOf) or form a cycle through the detached Gather (Convert)
        for u in list(p.get_target_inputs()):
            u.replace_source_output(ops.constant(
                np.zeros(1, dtype=np.int64)).output(0))
        model.remove_parameter(p.get_node())
        break
    log("[%s] after cut: inputs = %s"
        % (src_dir, [i.get_any_name() for i in model.inputs]))

    copy_aux(src_dir, dst_dir)
    dst = os.path.join(WORK, "models", dst_dir)
    dst_xml = os.path.join(dst, "openvino_model.xml")
    ov.save_model(model, dst_xml)

    reread = core.read_model(dst_xml)
    ins = [(i.get_any_name(), str(i.get_partial_shape()),
            str(i.get_element_type())) for i in reread.inputs]
    outs = [(o.get_any_name(), str(o.get_partial_shape())) for o in reread.outputs]
    xml = open(dst_xml, encoding="utf-8", errors="ignore").read()
    i4 = xml.count('element_type="i4"')
    i8 = xml.count('element_type="i8"')
    size = os.path.getsize(os.path.join(dst, "openvino_model.bin")) / 1048576
    log("[%s] -> %s" % (src_dir, dst_dir))
    for n, s, t in ins:
        log("   IN  %-16s %-28s %s" % (n, s, t))
    for n, s in outs:
        log("   OUT %-16s %s" % (n, s))
    log("   consts i4=%d i8=%d size=%.1f MiB" % (i4, i8, size))
    names = [n for n, _, _ in ins]
    return dst, dict(inputs=ins, outputs=outs, i4=i4, i8=i8,
                     size_mib=round(size, 1),
                     has_inputs_embeds="inputs_embeds" in names,
                     has_input_ids="input_ids" in names,
                     input_ids_consumers=ids_users)


def verify(dst_dir):
    """CPU + NPU: two different inputs_embeds must produce two different logits."""
    core = ov.Core()
    xml = os.path.join(WORK, "models", dst_dir, "openvino_model.xml")
    W = None
    idx = os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit",
                       "model.safetensors.index.json")
    if os.path.exists(idx):
        from safetensors import safe_open
        import torch
        shard = json.load(open(idx))["weight_map"]["model.embed_tokens.weight"]
        with safe_open(os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit",
                                    shard), framework="pt") as f:
            W = f.get_tensor("model.embed_tokens.weight").detach().to(
                torch.float32).numpy()
    rng = np.random.default_rng(7)
    T = 269
    out = {}
    for label, ie in (
            ("text", np.take(W, rng.integers(1000, 5000, size=(1, T)),
                             axis=0).astype(np.float32)
             if W is not None
             else rng.standard_normal((1, T, HIDDEN)).astype(np.float32)),
            ("rand", rng.standard_normal((1, T, HIDDEN)).astype(np.float32))):
        out[label] = ie
    feed_tmpl = {"attention_mask": np.ones((1, T), dtype=np.int64),
                 "position_ids": np.arange(T, dtype=np.int64)[None, :],
                 "beam_idx": np.zeros(1, dtype=np.int32)}
    res = {}
    for dev, props in (("CPU", {}), ("NPU", NPUW_PROPS)):
        try:
            cm = core.compile_model(xml, dev, props)
            lgs = {}
            for label, ie in out.items():
                # a fresh InferRequest per run: calling reset_state() twice on
                # one request trips "sub-views are not implemented" in this OV
                # build when the previous output tensor is still referenced
                r = cm.create_infer_request()
                r.reset_state()
                arr = np.array(list(r.infer(
                    dict(feed_tmpl, inputs_embeds=ie)).values())[0].data)
                lgs[label] = np.ascontiguousarray(arr[0, -1])
                del r
            del cm
            a, b = lgs["text"], lgs["rand"]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            c = float(a @ b / (na * nb)) if na and nb else None
            res[dev] = dict(text_argmax=int(np.argmax(a)),
                            rand_argmax=int(np.argmax(b)),
                            text_allzero=bool(np.all(a == 0)),
                            cos_text_vs_rand=(round(c, 6) if c is not None else None),
                            ie_reaches_model=bool(c is not None and c < 0.999))
            log("[%s@%s] %s" % (dst_dir, dev, res[dev]))
        except Exception as e:
            res[dev] = dict(error=f"{type(e).__name__}: {str(e)[:240]}")
            log("[%s@%s] FAILED %s" % (dst_dir, dev, res[dev]["error"]))
    return res


def main():
    rep = {}
    for src, dst in PAIRS:
        log("=" * 72)
        try:
            d, info = build(src, dst)
            rep[src] = dict(out=os.path.relpath(d, WORK) if d else None,
                            **(info or {}))
            if d and info and info.get("has_inputs_embeds"):
                rep[src]["runtime"] = verify(dst)
        except Exception as e:
            import traceback
            traceback.print_exc()
            rep[src] = dict(error=f"{type(e).__name__}: {e}")
    with open(os.path.join(WORK, "reports", "c079b_clean_embeds_ir.json"),
              "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log("wrote reports/c079b_clean_embeds_ir.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
