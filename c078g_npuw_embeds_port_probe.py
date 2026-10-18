"""C-078#3: can NPUW bind an `inputs_embeds` input at all? Systematic probe.

Closed attempts so far (all measured, see reports/c078g_*):

  c078c  cut embed_tokens Gather, feed consumers from a new `inputs_embeds`
         Parameter [?,?,2048].
         CPU  lossless (cosine 0.9999880791 vs stock, same argmax)
         NPU  all-zero logits, invariant to inputs_embeds x100, to input_ids,
              and to attention_mask. Same NPUW props + feed on the 4-port IR
              gives a normal argmax.

  c078f  kept the Gather, merged via Select(const true, ie, gather).
         CPU  identical to c078c (cosine 1.00000000)
         NPU  all-zero logits.

  probe  added a DUMMY f32 [?,?,2048] parameter to the untouched 4-port IR,
         consumed as `gather + (dummy - dummy)` so it cannot be pruned.
         CPU  works
         NPU  RuntimeError: broadcast_merge_into(output_shape,
              input_shapes[1]) failed

So a DYNAMIC rank-3 f32 input is not bindable. The open question this script
answers is whether STATIC rank-3 works, because NPUW's prefill subgraph is
static anyway (NPUW_LLM_MAX_PROMPT_LEN=512) and its decode step is a single
token -- i.e. [1,1,2048].

If a static-shaped inputs_embeds binds, the design survives: export the LM
with a fixed prompt length, feed the scattered audio embeddings at [1,L,2048]
for prefill and [1,1,2048] for decode. If neither dynamic nor static binds,
audio cannot enter the decoder as embeddings and the decoder must take the
audio span some other way.

Probe matrix: {dynamic rank3, static rank3} x {CPU, NPU}, using the dummy
`gather + (p - p)` construction so the parameter is provably live and cannot
be pruned, and confirming on CPU that the dummy construction is numerically
the identity (it must be, being +0).
"""
import json
import os

import numpy as np
import openvino as ov
from openvino import opset15 as ops

WORK = os.path.dirname(os.path.abspath(__file__))
STOCK = os.path.join(WORK, "models", "qwen3-lm-int8sym-lastlogit-ov",
                     "openvino_model.xml")
NPUW_PROPS = {
    "NPU_USE_NPUW": "YES",
    "NPUW_LLM": "YES",
    "NPUW_LLM_MAX_PROMPT_LEN": "512",
    "NPUW_LLM_MIN_RESPONSE_LEN": "64",
}
DYN = "dynamic"
ST512 = "static_1x512"
ST1 = "static_1x1"


def log(*a):
    print(*a, flush=True)


def build_variant(kind, path):
    core = ov.Core()
    m = core.read_model(STOCK)
    g = None
    for n in m.get_ordered_ops():
        if n.get_type_name() == "Gather" and \
                "embed_tokens" in n.get_friendly_name():
            g = n
            break
    hidden = g.output(0).get_partial_shape()[2].get_length()
    cons = list(g.output(0).get_target_inputs())
    if kind == DYN:
        big = 2 ** 62
        pshp = ov.PartialShape([ov.Dimension(1, big), ov.Dimension(1, big),
                                hidden])
        T = 269
    elif kind == ST512:
        pshp = ov.PartialShape([1, 512, hidden])
        T = 512
    else:
        pshp = ov.PartialShape([1, 1, hidden])
        T = 1
    p = ops.parameter(pshp, ov.Type.f32)
    p.set_friendly_name("inputs_embeds")
    p.output(0).get_tensor().set_names({"inputs_embeds"})
    m.add_parameters([p])
    zero = ops.subtract(p.output(0), p.output(0))   # exact 0, keeps p live
    merged = ops.add(g.output(0), zero)
    for u in cons:
        u.replace_source_output(merged.output(0))
    ov.save_model(m, path)
    mv = core.read_model(path)
    log("built %s -> inputs %s" % (kind, [i.get_any_name() for i in mv.inputs]))
    return hidden, T


def probe(kind):
    path = "/tmp/probe_%s.xml" % kind
    hidden, T = build_variant(kind, path)
    core = ov.Core()
    rng = np.random.default_rng(0)
    ids = rng.integers(1000, 5000, size=(1, T)).astype(np.int64)
    feed = {"input_ids": ids,
            "attention_mask": np.ones((1, T), dtype=np.int64),
            "position_ids": np.arange(T, dtype=np.int64)[None, :],
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": rng.standard_normal((1, T, hidden)).astype(np.float32)}
    out = {}
    for dev, props in (("CPU", {}), ("NPU", NPUW_PROPS)):
        try:
            cm = core.compile_model(path, dev, props)
            r = cm.create_infer_request()
            r.reset_state()
            lg = np.array(list(r.infer(feed).values())[0].data)[0, -1]
            out[dev] = dict(allzero=bool(np.all(lg == 0)),
                            argmax=int(np.argmax(lg)),
                            absmax=round(float(np.abs(lg).max()), 4))
            log("  %-16s %-4s -> %s" % (kind, dev, out[dev]))
            del r, cm
        except Exception as e:
            out[dev] = dict(error=f"{type(e).__name__}: {str(e)[:200]}")
            log("  %-16s %-4s FAILED %s" % (kind, dev, out[dev]["error"]))
    return out


def main():
    rep = {
        "closed_attempts": {
            "c078c_cut_gather": {
                "cpu": "lossless, cosine 0.9999880791 vs stock, same argmax",
                "npu": "all-zero logits, invariant to inputs_embeds/input_ids/"
                       "attention_mask",
            },
            "c078f_select_merge": {
                "cpu": "identical to c078c, cosine 1.00000000",
                "npu": "all-zero logits",
            },
            "probe_dummy_dynamic_rank3": {
                "cpu": "works",
                "npu": "RuntimeError broadcast_merge_into(output_shape, "
                       "input_shapes[1]) failed",
            },
        },
        "note": "dummy construction is gather + (p - p), i.e. numerically the "
                "identity, so any difference from stock is a binding failure "
                "and not an arithmetic one",
    }
    for kind in (DYN, ST512, ST1):
        log("probing %s" % kind)
        rep[kind] = probe(kind)
    with open(os.path.join(WORK, "reports", "c078g_npuw_embeds_port_probe.json"),
              "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log("wrote reports/c078g_npuw_embeds_port_probe.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
