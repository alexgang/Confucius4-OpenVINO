"""C-072#4a: multi-step stability of the NPUW LLM path (the thing that actually matters).

c072c measured SINGLE inferences. For delivery we need a full generate loop:
prefill once, then N decode steps, all on one NPUW CompiledModel with its own
internal KV cache. If the state handling is broken the error compounds step by
step, which a single-step test cannot reveal.

For each IR (fp16 / int8_sym) and device (NPU / GPU / CPU) we run the same
greedy loop and compare the produced token sequence with the CPU reference of the
SAME IR, plus the torch model.
"""
import json
import os
import sys
import time

import numpy as np
import openvino as ov

WORK = os.path.dirname(os.path.abspath(__file__))
PROMPT_LEN = 269          # c069m measured mean prompt length 268.75
N_NEW = 12                # c069m measured 7.6 tokens per call -> use 12 to see drift
SEED = 21

RESULTS = {}


def log(*a):
    print(*a, flush=True)


def make(seq):
    rng = np.random.default_rng(SEED)
    return {
        "input_ids": rng.integers(100, 140000, size=(1, seq)).astype(np.int64),
        "attention_mask": np.ones((1, seq), dtype=np.int64),
        "position_ids": np.arange(seq, dtype=np.int64).reshape(1, seq),
        "beam_idx": np.array([0], dtype=np.int32),
    }


def props_for(device):
    if device != "NPU":
        return {}
    return {"NPU_USE_NPUW": "YES", "NPUW_LLM": "YES",
            "NPUW_LLM_MAX_PROMPT_LEN": "512", "NPUW_LLM_MIN_RESPONSE_LEN": "64"}


def greedy_loop(cm, prompt_len, n_new):
    """One stateful session: prefill + n_new decode steps on the SAME request."""
    req = cm.create_infer_request()
    req.reset_state()
    rng = np.random.default_rng(SEED)
    ids = rng.integers(100, 140000, size=(1, prompt_len)).astype(np.int64)
    feed = {"input_ids": ids,
            "attention_mask": np.ones((1, prompt_len), dtype=np.int64),
            "position_ids": np.arange(prompt_len, dtype=np.int64).reshape(1, prompt_len),
            "beam_idx": np.array([0], dtype=np.int32)}
    t0 = time.perf_counter()
    req.infer(feed)
    prefill_ms = (time.perf_counter() - t0) * 1000.0
    toks = []
    step_ms = []
    for step in range(n_new):
        nxt = int(np.array(req.get_tensor(cm.outputs[0]).data).reshape(-1)[-0]
                  if False else int(np.argmax(np.array(
                      req.get_tensor(cm.outputs[0]).data)[0, -1, :])))
        toks.append(nxt)
        L = prompt_len + step + 1
        t0 = time.perf_counter()
        req.infer({"input_ids": np.array([[nxt]], dtype=np.int64),
                   "attention_mask": np.ones((1, L), dtype=np.int64),
                   "position_ids": np.array([[L - 1]], dtype=np.int64),
                   "beam_idx": np.array([0], dtype=np.int32)})
        step_ms.append((time.perf_counter() - t0) * 1000.0)
    return toks, prefill_ms, step_ms


def main():
    irs = os.environ.get("C072_IR_LIST", "qwen3-lm-fp16-ov,qwen3-lm-int8sym-ov").split(",")
    devices = os.environ.get("C072_DEV_LIST", "CPU,GPU,NPU").split(",")
    core = ov.Core()
    out = {}

    for irname in irs:
        ir = os.path.join(WORK, "models", irname, "openvino_model.xml")
        if not os.path.exists(ir):
            log("skip missing %s" % irname)
            continue
        model = core.read_model(ir)
        out[irname] = {}
        # CPU reference tokens
        cpu = core.compile_model(core.read_model(ir), "CPU")
        ref_toks, ref_pre, ref_step = greedy_loop(cpu, PROMPT_LEN, N_NEW)
        log("[%s] CPU ref tokens : %s" % (irname, ref_toks))
        out[irname]["cpu"] = dict(tokens=ref_toks,
                                  prefill_ms=round(ref_pre, 2),
                                  decode_ms=[round(x, 2) for x in ref_step])

        for dev in devices:
            if dev == "CPU":
                continue
            log("-" * 70)
            try:
                cm = core.compile_model(core.read_model(ir), dev, props_for(dev))
            except Exception as e:
                log("[%s] %s compile FAILED: %s" % (irname, dev, str(e)[:160]))
                out[irname][dev.lower()] = dict(compile_ok=False, error=str(e)[:400])
                continue
            try:
                toks, pre, step = greedy_loop(cm, PROMPT_LEN, N_NEW)
            except Exception as e:
                log("[%s] %s run FAILED: %s" % (irname, dev, str(e)[:160]))
                out[irname][dev.lower()] = dict(compile_ok=True, run_ok=False,
                                               error=str(e)[:400])
                continue
            match = [int(a == b) for a, b in zip(toks, ref_toks)]
            first_div = next((i for i, m in enumerate(match) if not m), None)
            out[irname][dev.lower()] = dict(
                compile_ok=True, run_ok=True, tokens=toks,
                step_match=match, n_steps=N_NEW,
                first_divergence_step=first_div,
                exact_match=bool(all(match)),
                prefill_ms=round(pre, 2),
                decode_ms=[round(x, 2) for x in step],
                decode_ms_median=round(float(np.median(step)), 2))
            log("[%s] %-3s tokens   : %s" % (irname, dev, toks))
            log("[%s] %-3s step match: %s  first_divergence=%s  prefill=%.1fms decode_med=%.1fms"
                % (irname, dev, match, first_div, pre, float(np.median(step))))

    with open(os.path.join(WORK, "reports", "c072f_npuw_multistep.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log("wrote reports/c072f_npuw_multistep.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
