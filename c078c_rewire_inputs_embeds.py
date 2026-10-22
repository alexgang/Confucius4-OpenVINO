"""C-078#3 / C-075#5#1: put a real `inputs_embeds` port on the lastlogit IRs.

The ASR thinker merges audio into the text embeddings with

    inputs_embeds = inputs_embeds.masked_scatter(audio_mask, audio_features)

where `audio_mask` selects the positions of `audio_token_id`
(qwen_asr .../modeling_qwen3_asr.py:1202-1203).  So the decoder never consumes
token ids for the audio span -- it consumes encoder features sitting in those
embedding slots.  The exported LM has no way to accept that: it only has
`input_ids`.

NPUW itself looks for an `inputs_embeds` port (DLL string
`find_port_by_name(..., layer_names::inputs_embeds)`) and *separately* needs
`input_ids` to build `text_mask` (DLL string `input_ids port not initialized
for text_mask`).  => the IR must expose BOTH ports, and `inputs_embeds` must
WIN over the embedding lookup.

So on the exported IR:

    embed_tokens Gather  -->  cut
    consumers            -->  new Parameter `inputs_embeds` [?, 2048] f32

`input_ids` stays a graph input (it keeps its own consumers: position-id
arithmetic / mask machinery), which is exactly what NPUW needs.

Both the prefill and the generate path of the stateful model share this one
Gather, so a single cut covers both.

This script also re-verifies the two claims that the stale c075b report made
but the XML does not support:
  * logits really are last-position-only  -> decided by a CPU runtime run,
    not by the reported partial shape.
  * the weight format really is int4/int8 -> decided by counting
    `element_type="i4"` / `"i8"` in the saved XML.
"""
import json
import os
import re
import shutil
import sys

import numpy as np
import openvino as ov
from openvino import opset15 as ops

WORK = os.path.dirname(os.path.abspath(__file__))
PAIRS = [
    ("qwen3-lm-int8sym-lastlogit-ov", "qwen3-lm-int8sym-ie-ov"),
    ("qwen3-lm-int4sym-lastlogit-ov", "qwen3-lm-int4sym-ie-ov"),
]
VOCAB = 151936
HIDDEN = 2048
SKIP_SUFFIXES = (".bin",)


def log(*a):
    print(*a, flush=True)


def find_embedding_gather(model):
    """Return the Gather whose data input is the [vocab, hidden] embedding table."""
    cands = []
    for n in model.get_ordered_ops():
        if n.get_type_name() != "Gather":
            continue
        name = n.get_friendly_name()
        src = n.input(0).get_source_output()
        if src is None:
            continue
        try:
            shp = src.get_partial_shape()
        except Exception:
            continue
        if not (shp.rank.is_static and shp.rank.get_length() == 2):
            continue
        d0, d1 = shp[0], shp[1]
        if d0.is_static and d0.get_length() == VOCAB and \
                d1.is_static and d1.get_length() == HIDDEN:
            cands.append((n, name))
    if not cands:
        return None, []
    # prefer the friendly name that mentions embed_tokens / the weight
    for n, name in cands:
        if "embed_tokens" in name or "embed" in name.lower():
            return n, [name for _, name in cands]
    return cands[0][0], [name for _, name in cands]


def copy_aux(src_dir, dst_dir):
    """Copy everything except the IR itself (tokenizer / detokenizer / config)."""
    s = os.path.join(WORK, "models", src_dir)
    d = os.path.join(WORK, "models", dst_dir)
    os.makedirs(d, exist_ok=True)
    for fn in os.listdir(s):
        if fn.startswith("openvino_model."):
            continue
        sp = os.path.join(s, fn)
        if os.path.isfile(sp):
            shutil.copy2(sp, os.path.join(d, fn))


def rewire(src_dir, dst_dir):
    core = ov.Core()
    src_xml = os.path.join(WORK, "models", src_dir, "openvino_model.xml")
    model = core.read_model(src_xml)
    log("[%s] read: %d ops, %d inputs, %d outputs"
        % (src_dir, len(model.get_ordered_ops()), len(model.inputs),
           len(model.outputs)))

    target, all_names = find_embedding_gather(model)
    if target is None:
        return None, {"error": "embedding Gather [151936,2048] not found",
                      "gather_candidates": all_names}
    log("[%s] target Gather: %r  out=%s"
        % (src_dir, target.get_friendly_name(),
           target.output(0).get_partial_shape()))
    log("[%s] all [vocab,hidden] Gathers: %d" % (src_dir, len(all_names)))
    for nm in all_names:
        log("      %s" % nm)

    out = target.output(0)
    users = list(out.get_target_inputs())
    log("[%s] consumers of Gather output: %d" % (src_dir, len(users)))
    if not users:
        return None, {"error": "embedding Gather has no consumers"}

    # reuse the exact partial shape the Gather produced ([?,?,2048]) so the
    # consumers keep validating unchanged
    param = ops.parameter(out.get_partial_shape(), ov.Type.f32)
    param.set_friendly_name("inputs_embeds")
    param.output(0).get_tensor().set_names({"inputs_embeds"})
    # a Parameter is only a graph input once it is registered on the model;
    # save_model rejects undeclared parameters
    model.add_parameters([param])
    log("[%s] registered inputs_embeds parameter" % src_dir)
    for u in users:
        u.replace_source_output(param.output(0))

    # The gather is now dangling. There is no Model.remove_node() in this OV
    # build; a dangling node is simply not serialized, so leave it in place.
    log("[%s] gather left dangling (not serialized); ops still %d"
        % (src_dir, len(model.get_ordered_ops())))

    copy_aux(src_dir, dst_dir)
    dst = os.path.join(WORK, "models", dst_dir)
    dst_xml = os.path.join(dst, "openvino_model.xml")
    # no Model.validate() in this OV build; save_model round-trips and the
    # re-read below is the real check
    # this OV build exposes save_model on the module, not on Core
    ov.save_model(model, dst_xml)

    # ---- verify what actually landed on disk ----
    xml = open(dst_xml, encoding="utf-8", errors="ignore").read()
    i4 = xml.count('element_type="i4"')
    i8 = xml.count('element_type="i8"')
    size = os.path.getsize(os.path.join(dst, "openvino_model.bin")) / 1048576
    reread = core.read_model(dst_xml)
    ins = [(i.get_any_name(), str(i.get_partial_shape())) for i in reread.inputs]
    outs = [(o.get_any_name(), str(o.get_partial_shape())) for o in reread.outputs]
    log("[%s] -> %s" % (src_dir, dst_dir))
    for n, s in ins:
        log("   IN  %-16s %s" % (n, s))
    for n, s in outs:
        log("   OUT %-16s %s" % (n, s))
    log("   consts i4=%d i8=%d   size=%.1f MiB" % (i4, i8, size))
    has_ie = any(n == "inputs_embeds" for n, _ in ins)
    has_iids = any(n == "input_ids" for n, _ in ins)
    if not has_ie or not has_iids:
        log("   !! port check FAILED inputs_embeds=%s input_ids=%s"
            % (has_ie, has_iids))
    return dst, dict(inputs=ins, outputs=outs, i4=i4, i8=i8,
                     size_mib=round(size, 1),
                     port_inputs_embeds=has_ie, port_input_ids=has_iids)


def runtime_shape_probe(dst_dir, prompt_len=269):
    """Decide last-position-only from an actual CPU run, not from rt_info."""
    core = ov.Core()
    xml = os.path.join(WORK, "models", dst_dir, "openvino_model.xml")
    cm = core.compile_model(xml, "CPU")
    req = cm.create_infer_request()
    req.reset_state()
    rng = np.random.default_rng(0)
    ids = rng.integers(1000, 5000, size=(1, prompt_len)).astype(np.int64)
    am = np.ones((1, prompt_len), dtype=np.int64)
    pos = np.arange(prompt_len, dtype=np.int64)[None, :]
    beam = np.zeros(1, dtype=np.int32)
    feed = {"input_ids": ids, "attention_mask": am,
            "position_ids": pos, "beam_idx": beam}
    if "inputs_embeds" in [i.get_any_name() for i in cm.inputs]:
        feed["inputs_embeds"] = rng.standard_normal(
            (1, prompt_len, HIDDEN)).astype(np.float32)
    t = req.infer(feed)
    out = {k: list(v.shape) for k, v in t.items()}
    log("[%s] CPU runtime prompt=%d -> output shapes %s"
        % (dst_dir, prompt_len, out))
    del req, cm
    return out


def main():
    report = {}
    for src, dst in PAIRS:
        log("=" * 72)
        try:
            d, info = rewire(src, dst)
            report[src] = dict(out=os.path.relpath(d, WORK) if d else None,
                               **(info or {}))
            if d and info and info.get("port_inputs_embeds"):
                report[src]["runtime_shapes"] = runtime_shape_probe(dst)
        except Exception as e:
            import traceback
            traceback.print_exc()
            log("[%s] FAILED %s: %s" % (src, type(e).__name__, e))
            report[src] = dict(error=f"{type(e).__name__}: {e}")
    with open(os.path.join(WORK, "reports", "c078c_rewire_inputs_embeds.json"),
              "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log("wrote reports/c078c_rewire_inputs_embeds.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
