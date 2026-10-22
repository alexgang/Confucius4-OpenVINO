"""C-079#1: is the all-zero `inputs_embeds` result caused by NPUW's host-side
embedding gather?

Two properties discovered in the NPU plugin DLL (they are absent from
SUPPORTED_PROPERTIES, which is why they never showed up before):

    NPUW_HOST_GATHER   default on -- NPUW hoists the vocab embedding Gather to
                        the host, computes it from input_ids, and feeds the
                        result straight into the NPU subgraph entry.  If the
                        in-graph Gather is cut or zeroed, the hoist still runs
                        and still writes to that entry, so the NPU never sees
                        the caller's inputs_embeds.

    NPUW_TEXT_EMBED    purpose unknown from the key name alone; tested here
                        because it is the only other embedding-related key.

Both are tried on all three rewire variants:
    A  qwen3-lm-int8sym-ie-ov      Gather removed
    B  qwen3-lm-int8sym-ie2-ov     Select(true, ie, gather)
    C  qwen3-lm-int4sym-ie2-ov     same, int4

Criterion for success is not merely "non-zero": the whole point is that the
audio embeddings REACH the model.  So each variant is run twice with two
completely different inputs_embeds tensors (real text embeddings vs random
noise).  If they agree, inputs_embeds is still being ignored and the fix
failed; if they disagree, the value is genuinely in the computation path.

Reference: the stock 4-port IR with ids only, which is known to work.
"""
import json
import os
import sys

import numpy as np
import openvino as ov

WORK = os.path.dirname(os.path.abspath(__file__))
BASE = {
    "NPU_USE_NPUW": "YES",
    "NPUW_LLM": "YES",
    "NPUW_LLM_MAX_PROMPT_LEN": "512",
    "NPUW_LLM_MIN_RESPONSE_LEN": "64",
}
VARIANTS = [
    ("A_cut_int8", "qwen3-lm-int8sym-ie-ov"),
    ("B_select_int8", "qwen3-lm-int8sym-ie2-ov"),
    ("B_select_int4", "qwen3-lm-int4sym-ie2-ov"),
]
STOCK = "qwen3-lm-int8sym-lastlogit-ov"


def log(*a):
    print(*a, flush=True)


def embed_table():
    from safetensors import safe_open
    import torch
    idx = os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit",
                       "model.safetensors.index.json")
    shard = json.load(open(idx))["weight_map"]["model.embed_tokens.weight"]
    with safe_open(os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit", shard),
                   framework="pt") as f:
        t = f.get_tensor("model.embed_tokens.weight")
    return t.detach().to(torch.float32).numpy()


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return None
    return float(a @ b / (na * nb))


def run(xml, props, feed):
    core = ov.Core()
    cm = core.compile_model(xml, "NPU", props)
    req = cm.create_infer_request()
    req.reset_state()
    lg = np.array(list(req.infer(feed).values())[0].data)[0, -1].copy()
    del req, cm
    return lg


def main():
    W = embed_table()
    rng = np.random.default_rng(7)
    T = 269
    ids = rng.integers(1000, 5000, size=(1, T)).astype(np.int64)
    emb_text = np.take(W, ids, axis=0).astype(np.float32)
    emb_rand = rng.standard_normal((1, T, 2048)).astype(np.float32)
    common = {
        "input_ids": ids,
        "attention_mask": np.ones((1, T), dtype=np.int64),
        "position_ids": np.arange(T, dtype=np.int64)[None, :],
        "beam_idx": np.zeros(1, dtype=np.int32),
    }

    prop_sets = [
        ("default", dict(BASE)),
        ("host_gather_NO", dict(BASE, NPUW_HOST_GATHER="NO")),
        ("text_embed_NO", dict(BASE, NPUW_TEXT_EMBED="NO")),
        ("both_NO", dict(BASE, NPUW_HOST_GATHER="NO", NPUW_TEXT_EMBED="NO")),
    ]

    rep = {}
    # stock reference first, so every later number has a known-good anchor
    xml = os.path.join(WORK, "models", STOCK, "openvino_model.xml")
    ref = {}
    for pname, props in prop_sets:
        try:
            lg = run(xml, props, dict(common))
            ref[pname] = dict(argmax=int(np.argmax(lg)),
                              allzero=bool(np.all(lg == 0)),
                              absmax=round(float(np.abs(lg).max()), 4))
            log("STOCK(4port) %-16s -> %s" % (pname, ref[pname]))
        except Exception as e:
            ref[pname] = dict(error=f"{type(e).__name__}: {str(e)[:160]}")
            log("STOCK(4port) %-16s FAILED %s" % (pname, ref[pname]["error"]))
    rep["stock_4port_reference"] = ref

    for vname, vdir in VARIANTS:
        xml = os.path.join(WORK, "models", vdir, "openvino_model.xml")
        if not os.path.exists(xml):
            log("[%s] missing, skipped" % vdir)
            continue
        entry = {}
        for pname, props in prop_sets:
            try:
                la = run(xml, props, dict(common, inputs_embeds=emb_text))
                lb = run(xml, props, dict(common, inputs_embeds=emb_rand))
                c = cos(la, lb)
                entry[pname] = dict(
                    text_argmax=int(np.argmax(la)),
                    rand_argmax=int(np.argmax(lb)),
                    text_allzero=bool(np.all(la == 0)),
                    cos_text_vs_rand=(round(c, 6) if c is not None else None),
                    ie_reaches_model=bool(c is not None and c < 0.999),
                )
                log("%-16s %-16s text_argmax=%d rand_argmax=%d cos=%s "
                    "allzero=%s IE_USED=%s"
                    % (vname, pname, entry[pname]["text_argmax"],
                       entry[pname]["rand_argmax"], entry[pname]["cos_text_vs_rand"],
                       entry[pname]["text_allzero"],
                       entry[pname]["ie_reaches_model"]))
            except Exception as e:
                entry[pname] = dict(error=f"{type(e).__name__}: {str(e)[:220]}")
                log("%-16s %-16s FAILED %s" % (vname, pname, entry[pname]["error"]))
        rep[vname] = entry

    with open(os.path.join(WORK, "reports", "c079a_host_gather_probe.json"),
              "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log("wrote reports/c079a_host_gather_probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
