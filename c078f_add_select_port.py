"""C-078#3: add `inputs_embeds` WITHOUT breaking NPUW's id-based embedding path.

What c078c did, and why it fails on NPU:
  it cut the embed_tokens Gather and fed the 3 consumers from a new
  `inputs_embeds` Parameter.  Lossless on CPU (cosine 0.99999 vs stock, same
  argmax), but NPUW returns all-zero logits for every input -- even after
  scaling inputs_embeds by 100 or changing input_ids.  Same NPUW properties,
  same feed: the 4-port IR returns a normal argmax.  So the 5-port graph is
  simply not executed the way CPU executes it.

The NPU plugin DLL explains why.  Around `inputs_embeds` it only contains
    ov::npuw::util::find_port_by_name(
        compiled_model->m_prefill_compiled->inputs(),
        layer_names::inputs_embeds)
inside the Kokoro (TTS) pipeline, plus
    "replacing text_mask generation with Parameter input"
i.e. NPUW *rewrites* the mask subgraph into its own Parameter and re-binds
ports by name.  Deleting the embedding Gather puts the graph in a shape that
pipeline cannot rebuild, and it silently produces zeros rather than erroring.

So: keep the Gather AND add the port, and make the choice explicit in-graph:

    inputs_embeds -> (IsFinite-free) Select  <- embed_tokens(input_ids)
                     ^ Boolean input `use_inputs_embeds`

Actually a cleaner form that avoids a boolean port (NPUW dislikes extra
conditionals): concatenate instead of replacing.  Take the Gather output and
build the new value as

    emb = Gather(embed_tokens, input_ids)          # unchanged, keeps ids path
    ie  = inputs_embeds                            # new Parameter

and then take  ie  if shapes allow, else emb.  Since both are [?, ?, 2048],
the simplest faithful merge is a `Where` on a constant-true condition, which
lets the liveness analysis keep both branches:

    emb_out = Where(Constant(true scalar), ie, emb)

Both inputs stay used, the id path stays intact, and feeding ie reproduces
the c078c semantics exactly.  We verify that on CPU (must match stock) and on
NPU (must stop being all-zero).

If `Where` is rejected by NPUW, fall back to reporting that the rewire shape
is unusable and the audio must instead enter through an encoder-side concat
(a separate graph), which is a bigger change and belongs to the caller.
"""
import json
import os
import shutil

import numpy as np
import openvino as ov
from openvino import opset15 as ops

WORK = os.path.dirname(os.path.abspath(__file__))
PAIRS = [
    ("qwen3-lm-int8sym-lastlogit-ov", "qwen3-lm-int8sym-ie2-ov"),
    ("qwen3-lm-int4sym-lastlogit-ov", "qwen3-lm-int4sym-ie2-ov"),
]
HIDDEN = 2048
GATHER_HINT = "embed_tokens"


def log(*a):
    print(*a, flush=True)


def find_embed_gather(model):
    for n in model.get_ordered_ops():
        if n.get_type_name() != "Gather":
            continue
        if GATHER_HINT not in n.get_friendly_name():
            continue
        src = n.input(0).get_source_output()
        shp = src.get_partial_shape()
        if shp.rank.is_static and shp.rank.get_length() == 2 and \
                shp[0].get_length() == 151936:
            return n
    return None


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
    g = find_embed_gather(model)
    if g is None:
        return None, {"error": "embedding gather not found"}
    log("[%s] gather=%s out=%s" % (src_dir, g.get_friendly_name(),
                                    g.output(0).get_partial_shape()))

    # The IR records [?,?,2048]. The dynamic dims need a finite, sane upper
    # bound: `ov.PartialShape([None,None,2048])` yields unbounded dims and
    # NPUW then binds the port to nothing and returns all-zero logits, while
    # 2**62 overflows the CPU memory-desc arithmetic
    # ("CpuBlockedMemoryDesc::getCurrentMemSizeImp overflow"). NPUW is capped at
    # NPUW_LLM_MAX_PROMPT_LEN=512 anyway, so 512 is the honest upper bound.
    MAX_TOK = int(os.environ.get("C078F_MAX_TOK", "512"))
    dims = list(g.output(0).get_partial_shape())
    pshp = ov.PartialShape([
        d.get_length() if d.is_static else ov.Dimension(1, MAX_TOK)
        for d in dims])
    log("[%s] inputs_embeds partial shape %s" % (src_dir, pshp))
    param = ops.parameter(pshp, ov.Type.f32)
    param.set_friendly_name("inputs_embeds")
    param.output(0).get_tensor().set_names({"inputs_embeds"})
    model.add_parameters([param])

    # ie wins, but the Gather branch stays live so NPUW's id-based path is
    # not left dangling
    cond = ops.constant(np.array(True, dtype=np.bool_))
    merged = ops.select(cond, param.output(0), g.output(0))
    merged.output(0).get_tensor().set_names({"embeds"})
    for u in list(g.output(0).get_target_inputs()):
        if u.get_node() is not merged:
            u.replace_source_output(merged.output(0))
    log("[%s] merged via Select; consumers rewired" % src_dir)

    copy_aux(src_dir, dst_dir)
    dst = os.path.join(WORK, "models", dst_dir)
    dst_xml = os.path.join(dst, "openvino_model.xml")
    ov.save_model(model, dst_xml)

    reread = core.read_model(dst_xml)
    ins = [(i.get_any_name(), str(i.get_partial_shape())) for i in reread.inputs]
    outs = [(o.get_any_name(), str(o.get_partial_shape())) for o in reread.outputs]
    xml = open(dst_xml, encoding="utf-8", errors="ignore").read()
    i4 = xml.count('element_type="i4"')
    i8 = xml.count('element_type="i8"')
    size = os.path.getsize(os.path.join(dst, "openvino_model.bin")) / 1048576
    # confirm the Gather is still in the saved graph
    g_alive = any("embed_tokens" in n.get_friendly_name()
                  for n in reread.get_ordered_ops())
    log("[%s] -> %s" % (src_dir, dst_dir))
    for n, s in ins:
        log("   IN  %-16s %s" % (n, s))
    for n, s in outs:
        log("   OUT %-16s %s" % (n, s))
    log("   gather_alive=%s consts i4=%d i8=%d size=%.1f MiB"
        % (g_alive, i4, i8, size))
    return dst, dict(inputs=ins, outputs=outs, gather_alive=g_alive,
                     i4=i4, i8=i8, size_mib=round(size, 1))


def main():
    rep = {}
    for src, dst in PAIRS:
        log("=" * 72)
        try:
            d, info = build(src, dst)
            rep[src] = dict(out=os.path.relpath(d, WORK) if d else None,
                            **(info or {}))
        except Exception as e:
            import traceback
            traceback.print_exc()
            log("[%s] FAILED %s: %s" % (src, type(e).__name__, e))
            rep[src] = dict(error=f"{type(e).__name__}: {e}")
    with open(os.path.join(WORK, "reports", "c078f_inputs_embeds_select.json"),
              "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log("wrote reports/c078f_inputs_embeds_select.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
