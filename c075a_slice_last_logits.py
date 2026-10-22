"""C-075#2: make the same IR compute logits for the LAST position only.

optimum's text-generation-with-past export computes logits for ALL T positions:
`logits [?,?,151936]`. At T=256 that is ~80 GFLOP in lm_head alone plus a huge
output tensor. The production IR only ever uses the last position. This is the
suspected cause of the GPU prefill being 194->282->403 ms (linear in T) while the
production GPU prefill is a flat 94 ms.

NPUW internally only computes the last position, so this change must not make
the NPU slower -- it is a GPU-side fairness fix, which is exactly what C-075#2
asks for ("same IR on GPU" must be a fair comparison).

We do it by inserting a Slice/Gather before the final Matmul, i.e. the graph is
changed to consume hidden states [B,T,H] -> [B,1,H] -> matmul -> [B,1,V].
The stateful inputs_embeds path is untouched, so NPUW still works.
"""
import json
import os
import sys

import numpy as np
import openvino as ov
from openvino import opset15 as ops

WORK = os.path.dirname(os.path.abspath(__file__))
OUT_DIRS = {
    "qwen3-lm-int8sym-ov": "qwen3-lm-int8sym-lastlogit-ov",
    "qwen3-lm-int4sym-ov": "qwen3-lm-int4sym-lastlogit-ov",
    "qwen3-lm-fp16-ov":    "qwen3-lm-fp16-lastlogit-ov",
}


def log(*a):
    print(*a, flush=True)


def patch(src_dir, dst_dir):
    core = ov.Core()
    src = os.path.join(WORK, "models", src_dir, "openvino_model.xml")
    dst = os.path.join(WORK, "models", dst_dir)
    os.makedirs(dst, exist_ok=True)
    model = core.read_model(src)

    logits = model.outputs[0]
    log("[%s] output %s shape=%s" % (src_dir, logits.get_any_name(), logits.get_partial_shape()))

    # the last MatMul in the graph is lm_head; its input is [B,T,H]
    mats = [n for n in model.get_ordered_ops() if n.get_type_name() == "MatMul"]
    log("[%s] MatMul count = %d" % (src_dir, len(mats)))
    lm = mats[-1] if mats else None
    if lm is None:
        return None, "no MatMul found"
    log("[%s] lm_head MatMul in-dims: %s -> out %s"
        % (src_dir, lm.get_input_tensor(0).get_partial_shape(),
           lm.get_output_tensor(0).get_partial_shape()))

    hidden = lm.get_input_tensor(0)
    try:
        rank = hidden.get_partial_shape().get_max_rank()
    except Exception:
        rank = 3
    if rank != 3:
        return None, "hidden states rank %r, expected 3" % (rank,)

    # Slice -> take the last position along axis 1
    last = ops.slice(hidden,
                     ops.constant([0], ov.Type.i32),
                     ops.constant([-1], ov.Type.i32),
                     ops.constant([-1], ov.Type.i32))
    last.set_friendly_name("last_position_slice")
    lm.get_input_tensor(0).replace_source_output(last.output(0))
    model.validate()

    core.save_model(model, os.path.join(dst, "openvino_model.xml"), compress_to_fp16=False)
    new = core.read_model(os.path.join(dst, "openvino_model.xml"))
    log("[%s] -> %s  new output shape=%s  size=%.1f MiB"
        % (src_dir, dst_dir, new.outputs[0].get_partial_shape(),
           os.path.getsize(os.path.join(dst, "openvino_model.bin")) / 1048576))
    return dst, None


def main():
    core = ov.Core()
    report = {}
    for src, dst in OUT_DIRS.items():
        if not os.path.exists(os.path.join(WORK, "models", src, "openvino_model.xml")):
            log("skip %s (missing)" % src)
            continue
        try:
            d, err = patch(src, dst)
            report[src] = dict(out=d, error=err)
        except Exception as e:
            log("[%s] patch FAILED: %s: %s" % (src, type(e).__name__, e))
            report[src] = dict(error=f"{type(e).__name__}: {e}")

    # numeric check: last-position logits must be identical to slicing the full output
    for src in OUT_DIRS:
        d = report.get(src, {}).get("out")
        if not d:
            continue
        log("-" * 60)
        log("numeric check %s" % src)
        full = core.compile_model(core.read_model(
            os.path.join(WORK, "models", src, "openvino_model.xml")), "CPU")
        cut = core.compile_model(core.read_model(
            os.path.join(WORK, "models", d, "openvino_model.xml")), "CPU")
        for L in (12, 256):
            rng = np.random.default_rng(1234 + L)
            feed = {"input_ids": rng.integers(100, 140000, size=(1, L)).astype(np.int64),
                    "attention_mask": np.ones((1, L), dtype=np.int64),
                    "position_ids": np.arange(L, dtype=np.int64).reshape(1, L),
                    "beam_idx": np.array([0], dtype=np.int32)}
            rf = full.create_infer_request(); rf.reset_state()
            rc = cut.create_infer_request(); rc.reset_state()
            a = np.array(rf.get_tensor(full.outputs[0]).data, copy=True)[0, -1, :]
            b = np.array(rc.get_tensor(cut.outputs[0]).data, copy=True)[0, -1, :]
            c = float(a.astype(np.float64) @ b.astype(np.float64) /
                      (np.linalg.norm(a) * np.linalg.norm(b) + 1e-30))
            log("  len%-4d cos=%.8f argmax full=%d cut=%d match=%s"
                % (L, c, a.argmax(), b.argmax(), a.argmax() == b.argmax()))
            report[src].setdefault("numeric", {})["len%d" % L] = dict(
                cosine=c, argmax_match=bool(a.argmax() == b.argmax()))
    with open(os.path.join(WORK, "reports", "c075a_last_logits_slice.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log("wrote reports/c075a_last_logits_slice.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
