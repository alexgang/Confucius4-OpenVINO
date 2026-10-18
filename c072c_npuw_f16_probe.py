"""C-072#4a: NPUW speed feasibility on the STANDARD Qwen3ForCausalLM IR.

Why a standard LM (C-072#3): NPUW_LLM reshapes the model itself into
prefill(MAX_PROMPT_LEN) and generate(1 token) variants, with KV length =
MAX_PROMPT_LEN + MIN_RESPONSE_LEN. It requires input_ids [?,?],
attention_mask [?,?], position_ids [?,?], beam_idx [?] with a DYNAMIC sequence
dim, and KV as state with a dynamic seq axis. optimum's
text-generation-with-past export produces exactly that (verified: the IR has
those four ports with partial shape [?,?] / [?]).

Discipline (C-072#1/#2):
  - numerics are verified BEFORE any latency is reported; a config with wrong
    numerics reports NO latency at all;
  - both comparisons are reported:
      * same-IR NPU vs GPU  -> device difference
      * NPU vs PRODUCTION GPU (94 ms prefill / 28.8 ms decode) -> delivery criterion
  - >= 20 reps, median only, serial, GPU guard wraps timing jobs.

OpenVINO 2026.4 note: CompiledModel has no .infer(); must create an
InferRequest. For stateful LMs we must reuse ONE request and call reset_state()
between independent measurements, otherwise the KV cache keeps growing and the
timing stops meaning "one prefill".
"""
import json
import os
import statistics
import subprocess
import sys
import time

import numpy as np
import openvino as ov

WORK = os.path.dirname(os.path.abspath(__file__))
IR = os.path.join(WORK, "models", os.environ.get("C072_IR", "qwen3-lm-fp16-ov"),
                  "openvino_model.xml")

MAX_PROMPT = int(os.environ.get("C072_MAXPROMPT", "512"))
MIN_RESP = int(os.environ.get("C072_MINRESP", "64"))
CHUNK = os.environ.get("C072_CHUNK", "")
DEVICE = os.environ.get("C072_DEVICE", "NPU")
GUARD_SECONDS = float(os.environ.get("C072_GUARD", "0"))
PREFILL_LENS = [int(x) for x in os.environ.get("C072_PREFILL_LENS", "256,384,512").split(",")]
WARMUP = int(os.environ.get("C072_WARMUP", "3"))
REPS = int(os.environ.get("C072_REPS", "20"))
SKIP_STEP4 = os.environ.get("C072_SKIP_LATENCY", "0") == "1"
# C-074: for the quantized variants a strict argmax match against the torch FP32
# model is NOT the right gate -- quantisation legitimately changes argmax. We
# therefore still measure latency but label it "numerics-flagged", and the
# quality question is settled separately by WER, not by a single-step argmax.
NUMERICS_ADVISORY = os.environ.get("C072_NUMERICS_ADVISORY", "0") == "1"

GPU_PREFILL_MS = 94.0
GPU_DECODE_MS = 28.8
CUSTOM_GPU_PREFILL_MS = 167.3
CUSTOM_GPU_DECODE_MS = 93.1

RESULTS = {"device": DEVICE, "ir": os.path.relpath(IR, WORK),
           "max_prompt_len": MAX_PROMPT, "min_response_len": MIN_RESP,
           "prefill_chunk_size": CHUNK or None,
           "reps": REPS, "warmup": WARMUP}


def log(*a):
    print(*a, flush=True)


def make_inputs(seq, seed=None):
    rng = np.random.default_rng(1234 + (seed or seq))
    return {
        "input_ids": rng.integers(100, 140000, size=(1, seq)).astype(np.int64),
        "attention_mask": np.ones((1, seq), dtype=np.int64),
        "position_ids": np.arange(seq, dtype=np.int64).reshape(1, seq),
        "beam_idx": np.array([0], dtype=np.int32),
    }


def cosine(a, b):
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))


def run_once(cm, feed):
    """One independent inference with a fresh state (OV 2026.4 API)."""
    req = cm.create_infer_request()
    req.reset_state()
    req.infer(feed)
    out = {o.get_any_name(): req.get_tensor(o).data.copy() for o in cm.outputs}
    return out


def last_logits(cm, feed):
    req = cm.create_infer_request()
    req.reset_state()
    req.infer(feed)
    t = req.get_tensor(cm.outputs[0])
    return np.array(t.data, dtype=np.float32).copy()


def timeit(cm, feed, warmup=WARMUP, reps=REPS):
    """Median of `reps` INDEPENDENT inferences (fresh state each time)."""
    for _ in range(warmup):
        run_once(cm, feed)
    lat = []
    for _ in range(reps):
        t0 = time.perf_counter()
        run_once(cm, feed)
        lat.append((time.perf_counter() - t0) * 1000.0)
    return dict(
        median_ms=round(statistics.median(lat), 3),
        mean_ms=round(statistics.mean(lat), 3),
        p10_ms=round(np.percentile(lat, 10), 3),
        p90_ms=round(np.percentile(lat, 90), 3),
        min_ms=round(min(lat), 3),
        max_ms=round(max(lat), 3),
        n=len(lat),
    )


# ----------------------------------------------------------------------------- numerics
def torch_reference(seq=12):
    import torch
    from transformers import Qwen3ForCausalLM
    key = "_m"
    if not hasattr(torch_reference, key):
        m = Qwen3ForCausalLM.from_pretrained(
            os.path.join(WORK, "models", "hf-qwen3-lm"), dtype=torch.float32)
        m.eval()
        setattr(torch_reference, key, m)
    m = getattr(torch_reference, key)
    f = make_inputs(seq)
    with torch.no_grad():
        o = m(input_ids=torch.from_numpy(f["input_ids"])).logits[0, -1, :].numpy()
    return o.astype(np.float64)


def step1_cpu_numerics(core):
    log("-" * 70)
    log("STEP 1: CPU IR numerics vs torch Qwen3ForCausalLM")
    log("-" * 70)
    cm = core.compile_model(core.read_model(IR), "CPU")
    t = torch_reference(12)
    cases = {}
    ok = True
    for L in (12, 256):
        f = make_inputs(L)
        ov_logits = last_logits(cm, f)[0, -1, :].astype(np.float64)
        if L == 12:
            c = cosine(ov_logits, t)
            cases["vs_torch_len12"] = dict(cosine=c,
                                           argmax_ov=int(ov_logits.argmax()),
                                           argmax_torch=int(t.argmax()),
                                           argmax_match=bool(ov_logits.argmax() == t.argmax()))
            ok = ok and cases["vs_torch_len12"]["cosine"] >= 0.99
            log("len12 vs torch : cos=%.6f argmax ov=%d torch=%d match=%s"
                % (c, ov_logits.argmax(), t.argmax(), ov_logits.argmax() == t.argmax()))
        else:
            ref256 = last_logits(cm, make_inputs(256, seed=256))[0, -1, :].astype(np.float64)
            cases["self_consistency_len256"] = dict(cosine=cosine(ov_logits, ref256))
            log("len256 self-ref : cos=%.6f" % cases["self_consistency_len256"]["cosine"])
    cases["pass_"] = bool(ok)
    RESULTS["cpu_numerics"] = cases
    return cases["pass_"]


def step3_device_numerics(core, cm):
    log("-" * 70)
    log("STEP 3: %s numerics vs CPU reference (same IR)" % DEVICE)
    log("-" * 70)
    cpu = core.compile_model(core.read_model(IR), "CPU")
    out = {}
    ok = True
    for L in (12, 256, 1):
        f = make_inputs(L)
        a = last_logits(cpu, f)[0, -1, :]
        b = last_logits(cm, f)[0, -1, :]
        c = cosine(a, b)
        am = int(a.argmax()) == int(b.argmax())
        out["len%d" % L] = dict(cosine=c, argmax_cpu=int(a.argmax()),
                                argmax_dev=int(b.argmax()), argmax_match=am,
                                absmax=float(np.abs(a - b).max()))
        log("len%-4d cpu-vs-%s: cos=%.6f argmax cpu=%d dev=%d match=%s absmax=%.4g"
            % (L, DEVICE, c, a.argmax(), b.argmax(), am, out["len%d" % L]["absmax"]))
        ok = ok and c >= 0.999 and am
    out["pass_"] = bool(ok)
    RESULTS["%s_numerics" % DEVICE.lower()] = out
    return out["pass_"]


def main():
    t_start = time.time()
    guard_proc = None
    if GUARD_SECONDS > 0:
        tag = f"c072_{DEVICE}_{MAX_PROMPT}"
        guard_proc = subprocess.Popen(
            ["C:/Users/Trekker-PTL/confucius4-openvino/.venv/Scripts/python.exe",
             "c058l_gpu_guard.py", str(os.getpid()), tag, str(int(GUARD_SECONDS))],
            cwd=WORK)
        log("GPU guard pid=%s tag=%s seconds=%s" % (guard_proc.pid, tag, GUARD_SECONDS))

    core = ov.Core()

    if not step1_cpu_numerics(core):
        log("CPU numerics FAILED -> stop, report no latency")
        return finish(guard_proc, t_start, 1)

    props = {}
    if DEVICE == "NPU":
        props = {
            "NPU_USE_NPUW": "YES",
            "NPUW_LLM": "YES",
            "NPUW_LLM_MAX_PROMPT_LEN": str(MAX_PROMPT),
            "NPUW_LLM_MIN_RESPONSE_LEN": str(MIN_RESP),
        }
        if CHUNK:
            props["NPUW_LLM_PREFILL_CHUNK_SIZE"] = str(CHUNK)
    # On GPU the NPUW_* keys are rejected outright ("Option not found: NPUW_LLM"),
    # so the same IR must be compiled plainly there for the device-difference
    # comparison required by C-072#1.
    RESULTS["npuw_props_used"] = props or None

    log("-" * 70)
    log("STEP 2: compile for %s  props=%s" % (DEVICE, props))
    log("-" * 70)
    t0 = time.time()
    cm = None
    try:
        cm = core.compile_model(core.read_model(IR), DEVICE, props)
        RESULTS["compile"] = dict(ok=True, props=props,
                                  seconds=round(time.time() - t0, 1))
        log("compile OK in %.1fs" % (time.time() - t0))
    except Exception as e:
        RESULTS["compile"] = dict(ok=False, props=props,
                                  error=f"{type(e).__name__}: {e}")
        log("compile FAILED:\n%s" % e)
        return finish(guard_proc, t_start, 2)

    dev_ok = step3_device_numerics(core, cm)
    if not dev_ok and not NUMERICS_ADVISORY:
        log("%s numerics WRONG -> latency VOID per C-072#2" % DEVICE)
        return finish(guard_proc, t_start, 3)
    if not dev_ok:
        log("%s numerics FLAGGED (advisory mode): latency is reported but the "
            "config is NOT precision-qualified." % DEVICE)
        RESULTS["latency_numerics_flagged"] = True

    if SKIP_STEP4:
        log("STEP 4 skipped by C072_SKIP_LATENCY=1")
        return finish(guard_proc, t_start, 0)

    log("-" * 70)
    log("STEP 4: latency  prefill %s + decode single step" % PREFILL_LENS)
    log("-" * 70)
    lat = {}
    for L in PREFILL_LENS:
        if L > MAX_PROMPT:
            log("skip prefill %d > MAX_PROMPT_LEN %d" % (L, MAX_PROMPT))
            continue
        st = timeit(cm, make_inputs(L))
        st["vs_prod_gpu"] = round(st["median_ms"] / GPU_PREFILL_MS, 3)
        st["vs_custom_gpu"] = round(st["median_ms"] / CUSTOM_GPU_PREFILL_MS, 3)
        lat["prefill_%d" % L] = st
        log("prefill %3d : %8.2f ms median  | vs prod GPU %.3fx | vs handwritten-GPU %.3fx"
            % (L, st["median_ms"], st["vs_prod_gpu"], st["vs_custom_gpu"]))

    st1 = timeit(cm, make_inputs(1))
    st1["vs_prod_gpu"] = round(st1["median_ms"] / GPU_DECODE_MS, 3)
    st1["vs_custom_gpu"] = round(st1["median_ms"] / CUSTOM_GPU_DECODE_MS, 3)
    lat["decode_step"] = st1
    log("decode  1 : %8.2f ms median  | vs prod GPU %.3fx | vs handwritten-GPU %.3fx"
        % (st1["median_ms"], st1["vs_prod_gpu"], st1["vs_custom_gpu"]))

    RESULTS["latency"] = lat
    # C-074#2: NPUW prefill is length-independent (~221 ms at 256/384/512) because
    # it computes the whole MAX_PROMPT_LEN static shape. Report the average
    # weighted by the REAL production prompt-length distribution from c069m
    # (min 215, median 263, mean 268.75, max 339).
    def real_weighted():
        dist = {215: 1, 263: 2, 269: 4, 339: 1}   # min / median(2x) / mean(4x) / max
        tot = sum(dist.values())
        acc = 0.0
        for L, w in dist.items():
            key = "prefill_%d" % L
            if key in lat:
                acc += w * lat[key]["median_ms"]
            elif "prefill_%d" % 256 in lat:
                acc += w * lat["prefill_256"]["median_ms"]
        return round(acc / tot, 3)
    RESULTS["real_prompt_weighted_prefill_ms"] = real_weighted()
    RESULTS["real_prompt_weighted_prefill_vs_prod"] = round(
        real_weighted() / GPU_PREFILL_MS, 3)
    log("real-prompt-weighted prefill = %.2f ms (vs prod GPU %.3fx)"
        % (real_weighted(), real_weighted() / GPU_PREFILL_MS))
    RESULTS["baselines"] = dict(
        prod_gpu_prefill_ms=GPU_PREFILL_MS, prod_gpu_decode_ms=GPU_DECODE_MS,
        handwritten_graph_gpu_prefill_ms=CUSTOM_GPU_PREFILL_MS,
        handwritten_graph_gpu_decode_ms=CUSTOM_GPU_DECODE_MS)
    pf = max(v["vs_prod_gpu"] for k, v in lat.items() if k.startswith("prefill"))
    dc = lat["decode_step"]["vs_prod_gpu"]
    RESULTS["stop_loss"] = dict(
        prefill_worst_vs_prod=pf,
        prefill_real_weighted_vs_prod=RESULTS["real_prompt_weighted_prefill_vs_prod"],
        decode_vs_prod=dc, threshold=1.30,
        verdict="STOP_LOSS_TRIGGERED" if (pf > 1.30 or dc > 1.30) else "WITHIN_30PCT")
    log("=" * 70)
    log("STOP-LOSS vs PRODUCTION GPU: prefill worst %.3fx, prefill(real-weighted) %.3fx,"
        " decode %.3fx -> %s"
        % (pf, RESULTS["real_prompt_weighted_prefill_vs_prod"], dc,
           RESULTS["stop_loss"]["verdict"]))
    log("=" * 70)
    return finish(guard_proc, t_start, 0)


def finish(guard_proc, t_start, code):
    RESULTS["seconds"] = round(time.time() - t_start, 1)
    out = os.path.join(WORK, "reports",
                       f"c072c_{DEVICE.lower()}_npuw_{MAX_PROMPT}"
                       f"{('_chunk' + CHUNK) if CHUNK else ''}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2)
    log("wrote %s" % out)
    if guard_proc is not None:
        guard_proc.wait()   # never kill: c058l only writes json on clean exit
        log("guard exited cleanly")
    return code


if __name__ == "__main__":
    sys.exit(main())
