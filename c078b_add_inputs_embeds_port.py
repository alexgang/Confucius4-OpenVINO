"""C-078#3 / C-075#5#1: add a real `inputs_embeds` port to the lastlogit IRs.

optimum traces `inputs_embeds` away when it is not used as an alternative to
input_ids in the example input, so the ASR audio span (which arrives as encoder
features scattered into the embedding positions of `audio_token_id`, see
modeling_qwen3_asr.py:1202-1203) cannot be fed. So do the rewire on the exported
IR:

  find the embedding Gather  ->  cut it  ->  replace its consumers with a new
  Parameter named `inputs_embeds` of shape [?, 2048].

`input_ids` is KEPT as a graph input, because NPUW needs it for `text_mask`
(DLL strings: "input_ids port not initialized for text_mask"). The embedding
Gather is then dangling and gets pruned on save.

Both prefill and generate paths in the stateful model share this one Gather, so a
single cut covers both.
"""
import json
import os
import re
import sys

import numpy as np
import openvino as ov
from openvino import opset15 as ops

WORK = os.path.dirname(os.path.abspath(__file__))
PAIRS = [
    ("qwen3-lm-int4sym-lastlogit-ov", "qwen3-lm-int4sym-ie-ov"),
    ("qwen3-lm-int8sym-lastlogit-ov", "qwen3-lm-int8sym-ie-ov"),
]
HIDDEN = 2048
EMBED_GATHER_HINT = "embed_tokens/aten::embedding/Gather"


def log(*a):
    print(*a, flush=True)


def cut(src_dir, dst_dir):
    core = ov.Core()
    src = os.path.join(WORK, "models", src_dir, "openvino_model.xml")
    model = core.read_model(src)

    # locate the embedding gather: the one whose data input is the [vocab, 2048] table
    target = None
    for n in model.get_ordered_ops():
        if n.get_type_name() != "Gather":
            continue
        if EMBED_GATHER_HINT in n.get_friendly_name():
            target = n
            break
    if target is None:
        # fall back: data input with static rank-2 shape whose dim0 == vocab_size
        for n in model.get_ordered_ops():
            if n.get_type_name() != "Gather":
                continue
            d = n.input(0)
            try:
                shp = d.get_partial_shape()
                if shp.rank.is_static and shp.rank.get_length() == 2 and \
                        shp[0].get_length() == 151936:
                    target = n
                    break
            except Exception:
                continue
    if target is None:
        return None, "embedding Gather not found"
    log("[%s] embedding Gather: %s  out=%s"
        % (src_dir, target.get_friendly_name(), target.output(0).get_partial_shape()))

    out = target.output(0)
    users = list(out.get_target_inputs())
    log("[%s] consumers: %d" % (src_dir, len(users)))

    # new Parameter: [?, 2048], f32, same as the embeddings it replaces
    param = ops.parameter([None, HIDDEN], ov.Type.f32)
    param.output(0).get_tensor().set_names({"inputs_embeds"})
    param.set_friendly_name("inputs_embeds")

    for u in users:
        u.replace_source_output(param.output(0))
    # detach the now-dangling gather
    for src_in in target.input(0).get_source_outputs():
        pass

    dst = os.path.join(WORK, "models", dst_dir)
    os.makedirs(dst, exist_ok=True)
    model.validate()
    core.save_model(model, os.path.join(dst, "openvino_model.xml"))

    new = core.read_model(os.path.join(dst, "openvino_model.xml"))
    ins = [(i.get_any_name(), str(i.get_partial_shape())) for i in new.inputs]
    log("[%s] -> %s" % (src_dir, dst_dir))
    for n, s in ins:
        log("   IN  %-16s %s" % (n, s))
    for o in new.outputs:
        log("   OUT %-16s %s" % (o.get_any_name(), str(o.get_partial_shape())))
    xml = open(os.path.join(dst, "openvino_model.xml"), encoding="utf-8",
               errors="ignore").read()
    i4 = len(re.findall(r'type="i4"', xml))
    i8 = len(re.findall(r'type="i8"', xml))
    size = os.path.getsize(os.path.join(dst, "openvino_model.bin")) / 1048576
    log("   consts: i4=%d i8=%d  size=%.1f MiB" % (i4, i8, size))
    return dst, dict(inputs=ins, i4=i4, i8=i8, size_mib=round(size, 1))


def main():
    report = {}
    for src, dst in PAIRS:
        log("=" * 70)
        try:
            d, info = cut(src, dst)
            report[src] = dict(out=d, **(info or {}))
        except Exception as e:
            log("[%s] FAILED: %s: %s" % (src, type(e).__name__, e))
            report[src] = dict(error=f"{type(e).__name__}: {e}")
    with open(os.path.join(WORK, "reports", "c078b_inputs_embeds_port.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log("wrote reports/c078b_inputs_embeds_port.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
