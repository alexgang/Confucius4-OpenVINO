"""C-078#3: prove the `inputs_embeds` rewire is lossless, and check NPUW accepts it.

Two independent things are established here.

1. Losslessness. The rewire cut the embedding Gather, so if we feed
   `inputs_embeds = embed_tokens(input_ids)` -- i.e. exactly what the original
   graph computed internally -- then IE-IR and stock IR must agree. This needs
   the embedding table, taken from the HF safetensors (the IR keeps it only as
   the tied lm_head MatMul weight). Any mismatch means the rewire changed
   semantics, not just plumbing.

2. NPUW acceptance. NPUW_LLM is picky about the port set: it wants input_ids
   (for text_mask), inputs_embeds, attention_mask, position_ids, beam_idx.
   So compile the 5-port IR for real and run it -- compiling is not evidence,
   only an actual infer() is.

Latency is reported as in-session multi-step median (the delivery-relevant
number; per-fresh-InferRequest timing roughly doubles it).
"""
import json
import os
import sys
import time

import numpy as np
import openvino as ov

WORK = os.path.dirname(os.path.abspath(__file__))
VOCAB, HIDDEN = 151936, 2048
NPUW_PROPS = {
    "NPU_USE_NPUW": "YES",
    "NPUW_LLM": "YES",
    "NPUW_LLM_MAX_PROMPT_LEN": "512",
    "NPUW_LLM_MIN_RESPONSE_LEN": "64",
}


def log(*a):
    print(*a, flush=True)


def embedding_table():
    """embed_tokens.weight from the HF snapshot, as float32 numpy."""
    from safetensors import safe_open
    import glob
    idx = os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit",
                        "model.safetensors.index.json")
    if os.path.exists(idx):
        wm = json.load(open(idx))["weight_map"]
        shard = wm["model.embed_tokens.weight"]
    else:
        shard = os.path.basename(glob.glob(
            os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit",
                         "model.safetensors"))[0])
    with safe_open(os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit", shard),
                   framework="pt") as f:
        t = f.get_tensor("model.embed_tokens.weight")
    return t.detach().to(torch_f32()).numpy()


def torch_f32():
    import torch
    return torch.float32


def build_feed(ids, emb, past=0):
    """ids: [1,T] int64.  Returns the 5-port feed dict."""
    T = ids.shape[1]
    am = np.ones((1, T + past), dtype=np.int64)
    pos = np.arange(past, past + T, dtype=np.int64)[None, :]
    return {
        "input_ids": ids,
        "attention_mask": am,
        "position_ids": pos,
        "beam_idx": np.zeros(1, dtype=np.int32),
        "inputs_embeds": emb,
    }


def run_greedy(cm, ids, emb, W, n_new, label):
    """prefill + n_new decode steps in one session; returns tokens + latencies.

    Each decode step must feed the embedding of the token that was just
    sampled, not the last prompt embedding -- that is the whole point of
    routing audio through inputs_embeds.
    """
    req = cm.create_infer_request()
    req.reset_state()
    f = build_feed(ids, emb)
    t0 = time.perf_counter()
    out = req.infer(f)
    t_prefill = (time.perf_counter() - t0) * 1000
    logits = np.array(list(out.values())[0].data)
    toks, dec = [], []
    for _ in range(n_new):
        nxt = int(np.argmax(logits[0, -1]))
        toks.append(nxt)
        past = ids.shape[1] + len(toks) - 1
        # embedding of the sampled token
        step_emb = W[nxt][None, None, :].astype(np.float32)
        f = {
            "input_ids": np.array([[nxt]], dtype=np.int64),
            "attention_mask": np.ones((1, past + 1), dtype=np.int64),
            "position_ids": np.array([[past]], dtype=np.int64),
            "beam_idx": np.zeros(1, dtype=np.int32),
            "inputs_embeds": step_emb,
        }
        t0 = time.perf_counter()
        out = req.infer(f)
        dec.append((time.perf_counter() - t0) * 1000)
        logits = np.array(list(out.values())[0].data)
    return toks, t_prefill, dec


def main():
    n_new = int(os.environ.get("C078D_STEPS", "12"))
    plen = int(os.environ.get("C078D_PROMPT", "269"))
    rng = np.random.default_rng(7)
    ids = rng.integers(1000, 5000, size=(1, plen)).astype(np.int64)
    W = embedding_table()
    log("embedding table %s %s" % (W.shape, W.dtype))
    emb = np.take(W, ids, axis=0).astype(np.float32)

    core = ov.Core()
    report = {}
    # ---- 1. losslessness: IE-IR fed with text embeddings == stock IR ----
    for name in ["qwen3-lm-int8sym-ie-ov", "qwen3-lm-int8sym-lastlogit-ov"]:
        cm = core.compile_model(
            os.path.join(WORK, "models", name, "openvino_model.xml"), "CPU")
        req = cm.create_infer_request()
        req.reset_state()
        if name.endswith("-ie-ov"):
            o = req.infer(build_feed(ids, emb))
        else:
            f = build_feed(ids, emb)
            del f["inputs_embeds"]
            o = req.infer(f)
        lg = np.array(list(o.values())[0].data)
        log("[%s] logits %s argmax_last=%d" % (name, lg.shape,
                                               int(np.argmax(lg[0, -1]))))
        report.setdefault(name, {})["last_argmax"] = int(np.argmax(lg[0, -1]))
        report[name]["cos_vs_int8sym_ie"] = None
        del req, cm

    # cosine between the two, on the last position
    lgs = {}
    for name in ["qwen3-lm-int8sym-ie-ov", "qwen3-lm-int8sym-lastlogit-ov"]:
        cm = core.compile_model(
            os.path.join(WORK, "models", name, "openvino_model.xml"), "CPU")
        req = cm.create_infer_request()
        req.reset_state()
        f = build_feed(ids, emb)
        if not name.endswith("-ie-ov"):
            del f["inputs_embeds"]
        lgs[name] = np.array(list(req.infer(f).values())[0].data)[0, -1].copy()
        del req, cm
    a, b = lgs["qwen3-lm-int8sym-ie-ov"], lgs["qwen3-lm-int8sym-lastlogit-ov"]
    cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    log("IE vs stock last-logit cosine = %.10f  argmax %d vs %d"
        % (cos, int(np.argmax(a)), int(np.argmax(b))))
    report["rewire_check"] = dict(cosine=cos,
                                  argmax_ie=int(np.argmax(a)),
                                  argmax_stock=int(np.argmax(b)),
                                  lossless=bool(cos > 0.9999
                                                and np.argmax(a) == np.argmax(b)))

    # ---- 2. CPU vs NPUW greedy on both IE IRs ----
    for name in ["qwen3-lm-int8sym-ie-ov", "qwen3-lm-int4sym-ie-ov"]:
        xml = os.path.join(WORK, "models", name, "openvino_model.xml")
        entry = {}
        for dev, props in (("CPU", {}), ("NPU", NPUW_PROPS)):
            try:
                t0 = time.perf_counter()
                cm = core.compile_model(xml, dev, props)
                entry[dev + "_compile_s"] = round(time.perf_counter() - t0, 1)
                toks, tp, dec = run_greedy(cm, ids, emb, W, n_new, dev)
                entry[dev + "_tokens"] = toks
                entry[dev + "_prefill_ms"] = round(tp, 1)
                entry[dev + "_decode_median_ms"] = round(float(np.median(dec)), 1)
                log("[%s@%s] prefill=%.1f ms decode_median=%.1f ms toks=%s"
                    % (name, dev, tp, float(np.median(dec)), toks))
                del cm
            except Exception as e:
                entry[dev + "_error"] = f"{type(e).__name__}: {e}"
                log("[%s@%s] FAILED %s: %s" % (name, dev, type(e).__name__, e))
        if "CPU_tokens" in entry and "NPU_tokens" in entry:
            k = min(len(entry["CPU_tokens"]), len(entry["NPU_tokens"]))
            entry["cpu_npu_prefix_match"] = sum(
                1 for i in range(k)
                if entry["CPU_tokens"][i] == entry["NPU_tokens"][i])
            entry["n_compared"] = k
        report[name] = entry

    with open(os.path.join(WORK, "reports", "c078d_ie_rewire_and_npuw.json"),
              "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log("wrote reports/c078d_ie_rewire_and_npuw.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
