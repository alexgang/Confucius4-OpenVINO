"""C-088#3-1：把 embed_tokens 导出成独立 f16 .npy，让交付形态不再依赖 hf-qwen3-lm-lastlogit。

动机：C-083 tier4 的「可删清单」把 models/hf-qwen3-lm-lastlogit（约 X GiB）列为可删，
但 npu_embeds_backend._load_embed_table() 还在读它 —— 删了会直接弄坏全 NPU 路径。
本脚本把 embed_tokens 单独导出成 f16 .npy（约 0.6 GB），放在 qwen3-lm-int8sym-cleanie-ov/
旁边，然后 _load_embed_table() 改为从那里读。

只用 safetensors + numpy，不 import torch。
"""
import json
import os
import sys

import numpy as np

WORK = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(WORK, "models", "hf-qwen3-lm-lastlogit")
DST_DIR = os.path.join(WORK, "models", "qwen3-lm-int8sym-cleanie-ov")
DST = os.path.join(DST_DIR, "embed_tokens_f16.npy")
REPORT = os.path.join(WORK, "reports", "c088a_embed_npy.json")

os.makedirs(os.path.dirname(REPORT), exist_ok=True)

rep = {"task": "C-088#3-1", "src": SRC, "dst": DST}


def read_embed_tokens_f32():
    from safetensors import safe_open
    idx = os.path.join(SRC, "model.safetensors.index.json")
    if os.path.exists(idx):
        shard = json.load(open(idx))["weight_map"]["model.embed_tokens.weight"]
        path = os.path.join(SRC, shard)
    else:
        path = os.path.join(SRC, "model.safetensors")
    rep["shard_used"] = os.path.basename(path)
    with safe_open(path, framework="numpy") as f:
        return np.asarray(f.get_tensor("model.embed_tokens.weight"),
                          dtype=np.float32)


def main():
    w = read_embed_tokens_f32()
    rep["shape"] = list(w.shape)
    rep["dtype_src"] = "float32"
    assert w.ndim == 2 and w.shape[0] > 100000, f"unexpected embed shape {w.shape}"

    w16 = w.astype(np.float16)
    np.save(DST, w16)

    # 校验：读回来比对，确认转换没改坏
    back = np.load(DST)
    assert back.shape == w.shape and back.dtype == np.float16
    d = np.abs(back.astype(np.float32) - w)
    rel = d.max() / max(float(np.abs(w).max()), 1e-9)
    rep["npy_shape"] = list(back.shape)
    rep["npy_dtype"] = str(back.dtype)
    rep["npy_bytes"] = os.path.getsize(DST)
    rep["npy_gib"] = round(os.path.getsize(DST) / 2 ** 30, 4)
    rep["f32_vs_f16_max_abs_diff"] = float(d.max())
    rep["f32_vs_f16_max_rel_diff"] = float(rel)
    rep["note"] = ("f16 vs f32 的最大相对差来自 f16 尾数位截断（f16 eps≈9.8e-4），"
                   "属预期；embedding 表只用于把 token id 映射成 inputs_embeds，"
                   "实测 C-085 全 NPU WER 判据用 f32 表已成立，f16 需重跑一次确认。")

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
