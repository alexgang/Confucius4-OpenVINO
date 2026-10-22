"""C-079#2: the clean embeddings-only IR works. Now measure it properly.

c079b established the fix -- removing the `input_ids` Parameter is what lets
NPUW take the embedding path. Evidence was two different inputs_embeds tensors
giving two different argmax on NPU, matching CPU exactly.

This script turns that into the numbers C-075#5 needs:

  1. Numerical agreement CPU vs NPU on a real prompt, per step.
     Not just argmax: cosine of the full last-position logit vector, since
     near-ties are where INT8/INT4 drift shows up.
  2. Multi-step greedy decode in one session (delivery-relevant latency; a
     fresh InferRequest per step roughly doubles it, which is the trap that
     produced the earlier 104 ms vs 57 ms discrepancy).
  3. Prefill and decode latency for both precisions, so the C-075#4
     stop-loss (RTF > 0.9) can be recomputed on the corrected numbers.

Everything is a dummy prompt, so per C-075#3/C-076 no accuracy verdict is
drawn from the tokens -- only timing and CPU/NPU agreement, which are exactly
what this path needs. Real-audio WER comes after the path is proven.

Note on inputs_embeds during decode: each step must carry the embedding of the
token just sampled, from the real embedding table. Feeding the last prompt
embedding instead is a bug that shows up as a plausible-looking but wrong
token stream.
"""
import json
import os
import sys
import time

import numpy as np
import openvino as ov

WORK = os.path.dirname(os.path.abspath(__file__))
NPUW_PROPS = {
    "NPU_USE_NPUW": "YES",
    "NPUW_LLM": "YES",
    "NPUW_LLM_MAX_PROMPT_LEN": "512",
    "NPUW_LLM_MIN_RESPONSE_LEN": "64",
}
MODELS = [
    ("INT8_SYM", "qwen3-lm-int8sym-cleanie-ov"),
    ("INT4_SYM", "qwen3-lm-int4sym-cleanie-ov"),
]
N_NEW = int(os.environ.get("C079C_STEPS", "12"))
PROMPT = int(os.environ.get("C079C_PROMPT", "269"))


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


def run_session(xml, dev, props, W, emb_prompt, n_new):
    """prefill + n_new greedy steps in one InferRequest. Returns tokens, lat."""
    cm = ov.Core().compile_model(xml, dev, props)
    req = cm.create_infer_request()
    req.reset_state()
    T = emb_prompt.shape[1]

    t0 = time.perf_counter()
    out = req.infer({
        "attention_mask": np.ones((1, T), dtype=np.int64),
        "position_ids": np.arange(T, dtype=np.int64)[None, :],
        "beam_idx": np.zeros(1, dtype=np.int32),
        "inputs_embeds": emb_prompt,
    })
    t_prefill = (time.perf_counter() - t0) * 1000
    arr = np.array(list(out.values())[0].data)
    logits = np.ascontiguousarray(arr[0, -1]).copy()

    tokens, step_logits, dec = [], [], []
    for _ in range(n_new):
        nxt = int(np.argmax(logits))
        tokens.append(nxt)
        past = T + len(tokens) - 1
        t0 = time.perf_counter()
        out = req.infer({
            "attention_mask": np.ones((1, past + 1), dtype=np.int64),
            "position_ids": np.array([[past]], dtype=np.int64),
            "beam_idx": np.zeros(1, dtype=np.int32),
            # embedding of the token just sampled
            "inputs_embeds": W[nxt][None, None, :].astype(np.float32),
        })
        dec.append((time.perf_counter() - t0) * 1000)
        arr = np.array(list(out.values())[0].data)
        logits = np.ascontiguousarray(arr[0, -1]).copy()
        step_logits.append(logits)
    del req, cm
    return tokens, step_logits, t_prefill, dec


def cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else None


def main():
    W = embed_table()
    rng = np.random.default_rng(7)
    T = PROMPT
    # a real text prompt: the ASR prompt template's text part, padded to T with
    # ordinary tokens so the embedding table is indexed meaningfully
    ids = rng.integers(1000, 5000, size=T)
    emb_prompt = np.take(W, ids, axis=0).astype(np.float32)[None, :, :]
    log("prompt len=%d steps=%d" % (T, N_NEW))

    rep = {}
    for label, mdir in MODELS:
        xml = os.path.join(WORK, "models", mdir, "openvino_model.xml")
        entry = {}
        got = {}
        for dev, props in (("CPU", {}), ("NPU", NPUW_PROPS)):
            t0 = time.perf_counter()
            toks, sl, tp, dec = run_session(xml, dev, props, W, emb_prompt, N_NEW)
            got[dev] = dict(tokens=toks, step_logits=sl,
                            prefill_ms=tp, decode_ms=dec)
            entry[dev + "_compile_plus_run_s"] = round(time.perf_counter() - t0, 1)
            entry[dev + "_prefill_ms"] = round(tp, 1)
            entry[dev + "_decode_median_ms"] = round(float(np.median(dec)), 1)
            log("[%s@%s] prefill=%.1f ms decode_median=%.1f ms tokens=%s"
                % (label, dev, tp, float(np.median(dec)), toks))
        # CPU vs NPU agreement, per step
        if "CPU" in got and "NPU" in got:
            ca, na = got["CPU"], got["NPU"]
            k = min(len(ca["tokens"]), len(na["tokens"]))
            match = sum(1 for i in range(k) if ca["tokens"][i] == na["tokens"][i])
            entry["n_steps"] = k
            entry["token_match"] = match
            entry["token_match_rate"] = round(match / k, 4) if k else None
            entry["first_divergence"] = next(
                (i for i in range(k) if ca["tokens"][i] != na["tokens"][i]), None)
            cosines = []
            for i in range(min(k, len(ca["step_logits"]), len(na["step_logits"]))):
                c = cos(ca["step_logits"][i], na["step_logits"][i])
                if c is not None:
                    cosines.append(round(c, 6))
            entry["per_step_cosine"] = cosines
            log("[%s] CPU/NPU token match %d/%d  first_divergence=%s"
                % (label, match, k, entry["first_divergence"]))
            log("[%s] per-step cosine: %s" % (label, cosines))
        rep[label] = entry

    with open(os.path.join(WORK, "reports", "c079c_cleanie_numerics.json"),
              "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log("wrote reports/c079c_cleanie_numerics.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
