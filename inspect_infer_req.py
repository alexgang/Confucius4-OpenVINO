"""inspect_infer_req.py — 检查 with-past decoder 的 infer request 实际输入名"""
import os
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
import numpy as np
import openvino as ov

core = ov.Core()
core.set_property({"CACHE_DIR": "./ov_cache"})
dec = core.compile_model(
    "models/ov-fp16-past/openvino_decoder_model.xml",
    "GPU.0",
    {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_PRECISION_HINT": "f16"},
)
req = dec.create_infer_request()
print("=== Model inputs (from compiled) ===")
for i, inp in enumerate(dec.inputs):
    print(f"  [{i}] {inp.any_name}  shape={inp.partial_shape}  type={inp.element_type}")
print("=== Model outputs ===")
for i, out in enumerate(dec.outputs):
    print(f"  [{i}] {out.any_name}  shape={out.partial_shape}  type={out.element_type}")

print("\n=== Infer request input ports ===")
try:
    for i, p in enumerate(req.get_input_tensor(0).port, 0):
        print(f"  port {i}")
except Exception as e:
    print(f"  iter error: {e}")
# Direct inspect via list
print("\n=== Try list_inputs (might be attribute) ===")
for attr in ("input_tensors", "inputs", "get_input_tensors", "get_inputs"):
    if hasattr(req, attr):
        v = getattr(req, attr)
        print(f"  has {attr}: {type(v).__name__}")
    else:
        print(f"  no {attr}")

# Try the dict-style infer and see what the first call accepts
print("\n=== Try one infer call with 1 token ===")
try:
    ehs = np.zeros((1, 5, 2048), dtype=np.float32)
    ids = np.array([[1]], dtype=np.int64)
    beam = np.array([0], dtype=np.int32)
    out = req.infer({"encoder_hidden_states": ehs, "decoder_input_ids": ids, "beam_idx": beam})
    print("  OK, output keys:", list(out.keys()))
    for k, v in out.items():
        print(f"    {k}: shape={v.shape}")
except Exception as e:
    print(f"  ERR: {e}")

print("\n=== After infer: re-list inputs ===")
# After infer, the ports should be the same but let's see
try:
    print(f"  inputs: {req.get_input_tensor(0).port}, ...")
except Exception as e:
    print(f"  err: {e}")

# Try get_input_tensor by index
print("\n=== get_input_tensor by index ===")
for i in range(5):
    try:
        t = req.get_input_tensor(i)
        print(f"  [{i}] shape={t.partial_shape} name={t.node.get_name() if hasattr(t, 'node') and t.node else '?'}")
    except Exception as e:
        print(f"  [{i}] err: {e}")
        break
