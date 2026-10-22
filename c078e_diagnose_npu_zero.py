"""C-078#3: why does the NPUW run of the 5-port IE IR emit token 0 every step?

CPU on the same IR gives a normal token stream, NPU gives all zeros. NPUW is
a different graph decomposition, so it is likely doing one of:

  H1  it ignores `inputs_embeds` and still Gathers from `input_ids`
      -> the prompt path would be fine (both agree) but the decode step,
         where we feed the embedding of a token sampled from *our* logits,
         would silently use a different token. All-zero output is consistent
         with the text_mask/position machinery disagreeing.

  H2  it treats an unused-if-unfed port as default zeros and the masked_scatter
      position is empty, so the whole audio span is dropped.

  H3  it does not accept a 5-port graph and silently binds the wrong tensors.

Discriminate them by feeding controlled perturbations: change ONE thing at a
time (only inputs_embeds, only input_ids, only attention_mask) and see
whether the NPU logits move. If logits are invariant to inputs_embeds but
sensitive to input_ids, that is H1 -- NPUW is embedding by id.

Also compare against the 4-port IR (no inputs_embeds) on the same ids, which
is the ground truth for "what NPUW does with ids alone".
"""
import json
import os
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
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    W = embed_table()
    rng = np.random.default_rng(7)
    T = 269
    ids = rng.integers(1000, 5000, size=(1, T)).astype(np.int64)
    emb_text = np.take(W, ids, axis=0).astype(np.float32)
    emb_rand = rng.standard_normal((1, T, 2048)).astype(np.float32)
    core = ov.Core()
    rep = {}

    xml_ie = os.path.join(WORK, "models", "qwen3-lm-int8sym-ie-ov",
                          "openvino_model.xml")
    xml_4p = os.path.join(WORK, "models", "qwen3-lm-int8sym-lastlogit-ov",
                          "openvino_model.xml")

    def infer(xml, dev, feed, props=None):
        cm = core.compile_model(xml, dev, props or {})
        req = cm.create_infer_request()
        req.reset_state()
        lg = np.array(list(req.infer(feed).values())[0].data)[0, -1].copy()
        del req, cm
        return lg

    def feed5(ie):
        return {"input_ids": ids,
                "attention_mask": np.ones((1, T), dtype=np.int64),
                "position_ids": np.arange(T, dtype=np.int64)[None, :],
                "beam_idx": np.zeros(1, dtype=np.int32),
                "inputs_embeds": ie}

    # ---- baseline: 4-port stock IR on ids alone (ground truth for id path) ----
    f4 = {"input_ids": ids,
          "attention_mask": np.ones((1, T), dtype=np.int64),
          "position_ids": np.arange(T, dtype=np.int64)[None, :],
          "beam_idx": np.zeros(1, dtype=np.int32)}
    l4_npu = infer(xml_4p, "NPU", f4, NPUW_PROPS)
    l4_cpu = infer(xml_4p, "CPU", f4)
    rep["4port_stock"] = dict(
        npu_argmax=int(np.argmax(l4_npu)), cpu_argmax=int(np.argmax(l4_cpu)),
        cos_npu_cpu=cos(l4_npu, l4_cpu))
    log("4-port stock: NPU argmax=%d CPU argmax=%d cos=%.6f"
        % (rep["4port_stock"]["npu_argmax"], rep["4port_stock"]["cpu_argmax"],
           rep["4port_stock"]["cos_npu_cpu"]))

    # ---- 5-port: vary ONE input at a time ----
    l_text_npu = infer(xml_ie, "NPU", feed5(emb_text), NPUW_PROPS)
    l_rand_npu = infer(xml_ie, "NPU", feed5(emb_rand), NPUW_PROPS)
    l_text_cpu = infer(xml_ie, "CPU", feed5(emb_text))

    rep["5port_text"] = dict(npu_argmax=int(np.argmax(l_text_npu)),
                             cpu_argmax=int(np.argmax(l_text_cpu)),
                             cos_npu_cpu=cos(l_text_npu, l_text_cpu))
    rep["ie_sensitivity"] = dict(
        cos_text_vs_random_npu=cos(l_text_npu, l_rand_npu),
        cos_text_vs_stock4_npu=cos(l_text_npu, l4_npu))
    log("5-port text:  NPU argmax=%d CPU argmax=%d cos=%.6f"
        % (rep["5port_text"]["npu_argmax"], rep["5port_text"]["cpu_argmax"],
           rep["5port_text"]["cos_npu_cpu"]))
    log("NPU cos(text, random-embeds) = %.6f   <- ~0 would mean ie is ignored"
        % rep["ie_sensitivity"]["cos_text_vs_random_npu"])
    log("NPU cos(5port-text, 4port-stock) = %.6f"
        % rep["ie_sensitivity"]["cos_text_vs_stock4_npu"])

    # ---- does a garbage attention_mask matter? (tests text_mask wiring) ----
    am_bad = np.zeros((1, T), dtype=np.int64)
    am_bad[0, ::3] = 1
    f_bad = feed5(emb_text)
    f_bad["attention_mask"] = am_bad
    l_bad = infer(xml_ie, "NPU", f_bad, NPUW_PROPS)
    rep["am_sensitivity"] = dict(cos_full_vs_gappy_mask=cos(l_text_npu, l_bad))
    log("NPU cos(full mask, gappy mask) = %.6f"
        % rep["am_sensitivity"]["cos_full_vs_gappy_mask"])

    with open(os.path.join(WORK, "reports", "c078e_npu_zero_diagnosis.json"),
              "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    log("wrote reports/c078e_npu_zero_diagnosis.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
