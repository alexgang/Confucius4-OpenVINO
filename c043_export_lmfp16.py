"""c043_export_lmfp16.py — C-043#1: 导出 INT8 + FP16 lm_head 的 decoder IR

Per C-043 (10-13 10:45):
- lm_head (tied with embed_tokens) 量化误差是第二个根因
- 解决方案: 保留 lm_head 为 FP16, 其余 INT8
- tie_word_embeddings=true, lm_head 和 embed_tokens 共享同一个 Constant
- 必须先把共享常量复制一份, 分别给 MatMul 和 Gather
- 输出: models/ov-int8-lmfp16-past/
"""
import os, sys, time, shutil
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, '.')

import numpy as np
import openvino as ov
import openvino.opset14 as ops
import nncf


SRC_DIR = 'models/ov-fp16-past'
DST_DIR = 'models/ov-int8-lmfp16-past'
LMHEAD_NAME = '__module.model.thinker.lm_head/aten::linear/MatMul'
EMBED_CONVERT_NAME = 'self.model.thinker.model.embed_tokens.weight'
EMBED_CONST_NAME = 'self.model.thinker.model.embed_tokens.weight_compressed'
EMBED_GATHER_NAME = '__module.model.thinker.model.embed_tokens/aten::embedding/Gather'


def find_node(model, friendly_name):
    for node in model.get_ops():
        if node.get_friendly_name() == friendly_name:
            return node
    return None


def clone_tied_weight(model):
    """Clone the shared embed_tokens Constant so lm_head and embedding each have their own copy."""
    print('[clone] finding shared Constant + Convert + MatMul + Gather...', flush=True)
    src_const = find_node(model, EMBED_CONST_NAME)
    src_convert = find_node(model, EMBED_CONVERT_NAME)
    lm_head_matmul = find_node(model, LMHEAD_NAME)
    assert src_const is not None, f'Constant {EMBED_CONST_NAME} not found'
    assert src_convert is not None, f'Convert {EMBED_CONVERT_NAME} not found'
    assert lm_head_matmul is not None, f'MatMul {LMHEAD_NAME} not found'

    # Get constant data
    data = src_const.data
    print(f'[clone] src const: shape={data.shape} dtype={data.dtype}', flush=True)

    # Create a new Constant (clone)
    new_const = ops.constant(data.copy(), name='self.model.thinker.lm_head.weight_compressed')

    # Create a new Convert (for lm_head, will be kept as FP16 in target)
    new_convert = ops.convert(new_const, destination_type=ov.Type.f16, name='self.model.thinker.lm_head.weight')

    # Re-wire: lm_head MatMul's weight input (input 1) should come from new_convert
    # We need to find which input index is the weight
    # Convention: MatMul has [activations, weight]
    print(f'[clone] lm_head MatMul has {len(lm_head_matmul.inputs())} inputs', flush=True)
    # Identify weight input by tracing back to Convert
    weight_input_idx = None
    for i, inp in enumerate(lm_head_matmul.inputs()):
        src = inp.get_source_output()
        if src.get_node() is src_convert:
            weight_input_idx = i
            break
    assert weight_input_idx is not None, 'Could not find weight input in lm_head MatMul'
    print(f'[clone] lm_head weight input idx = {weight_input_idx}', flush=True)

    # Replace
    lm_head_matmul.input(weight_input_idx).replace_source_output(new_convert.output(0))
    print(f'[clone] rewired lm_head MatMul to use cloned Convert', flush=True)

    # Also: insert a Convert on the activation side to match f16 type
    # (after NNCF, the body of the graph may have f32 activations, but
    # the original lm_head expects f16. We need to convert the activation to f16.)
    activation_input_idx = 1 - weight_input_idx
    activation_src = lm_head_matmul.input(activation_input_idx).get_source_output()
    act_node = activation_src.get_node()
    act_dtype = act_node.get_output_element_type(0)
    print(f'[clone] lm_head activation input idx = {activation_input_idx}, dtype = {act_dtype}', flush=True)
    if act_dtype != ov.Type.f16:
        new_act_convert = ops.convert(activation_src, destination_type=ov.Type.f16, name='self.model.thinker.lm_head.act_convert')
        lm_head_matmul.input(activation_input_idx).replace_source_output(new_act_convert.output(0))
        print(f'[clone] inserted f16 Convert on activation path', flush=True)

    # Verify: Convert still feeds Gather, but MatMul now uses new_convert
    consumers = []
    for inp in src_convert.output(0).get_target_inputs():
        consumers.append(inp.get_node().get_friendly_name())
    print(f'[clone] src Convert still feeds: {consumers}', flush=True)
    consumers2 = []
    for inp in new_convert.output(0).get_target_inputs():
        consumers2.append(inp.get_node().get_friendly_name())
    print(f'[clone] new Convert feeds: {consumers2}', flush=True)
    return model


def main():
    print('[c043-export] === C-043#1: 导出 INT8 + FP16 lm_head ===', flush=True)
    print(f'[c043-export] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print(f'[c043-export] loading FP16 decoder from {SRC_DIR}...', flush=True)
    t0 = time.perf_counter()
    model = ov.Core().read_model(f'{SRC_DIR}/openvino_decoder_model.xml')
    print(f'[c043-export] load took {time.perf_counter()-t0:.1f}s', flush=True)

    # Step 1: Clone the tied weight
    model = clone_tied_weight(model)

    # Step 2: NNCF compress_weights with ignored_scope on lm_head
    print(flush=True)
    print('[nncf] compressing weights with INT8_ASYM, ignored_scope=lm_head MatMul...', flush=True)
    t1 = time.perf_counter()
    compressed = nncf.compress_weights(
        model,
        mode=nncf.CompressWeightsMode.INT8_ASYM,
        ignored_scope=nncf.IgnoredScope(names=[LMHEAD_NAME]),
    )
    print(f'[nncf] compression took {time.perf_counter()-t1:.1f}s', flush=True)

    # Step 3: Verify: lm_head MatMul weight should be f16, embedding can be INT8
    print(flush=True)
    print('[verify] checking resulting IR...', flush=True)
    lm_head_matmul = find_node(compressed, LMHEAD_NAME)
    assert lm_head_matmul is not None, 'lm_head MatMul not found after compress'
    # Find its weight input
    for i, inp in enumerate(lm_head_matmul.inputs()):
        src = inp.get_source_output()
        n = src.get_node()
        if n.get_type_name() in ('Convert', 'Constant'):
            try:
                data = n.data
                print(f'[verify] lm_head input {i}: {n.get_friendly_name()} ({n.get_type_name()}) dtype={data.dtype} shape={data.shape}', flush=True)
            except Exception:
                pass

    # Find embed Gather
    embed_gather = find_node(compressed, EMBED_GATHER_NAME)
    if embed_gather:
        print(f'[verify] embed Gather: {embed_gather.get_friendly_name()}', flush=True)
        for i, inp in enumerate(embed_gather.inputs()):
            src = inp.get_source_output()
            n = src.get_node()
            print(f'  input {i}: {n.get_friendly_name()} ({n.get_type_name()})', flush=True)

    # Step 4: Save to destination
    os.makedirs(DST_DIR, exist_ok=True)
    print(flush=True)
    print(f'[save] writing to {DST_DIR}/...', flush=True)
    t2 = time.perf_counter()
    ov.save_model(compressed, f'{DST_DIR}/openvino_decoder_model.xml')
    print(f'[save] save took {time.perf_counter()-t2:.1f}s', flush=True)

    # Copy non-IR files
    print('[save] copying tokenizer/config files from source...', flush=True)
    for f in os.listdir(SRC_DIR):
        if f == 'openvino_decoder_model.xml' or f == 'openvino_decoder_model.bin':
            continue
        src = os.path.join(SRC_DIR, f)
        dst = os.path.join(DST_DIR, f)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f'  copied: {f}', flush=True)

    print(flush=True)
    print(f'[c043-export] DONE. → {DST_DIR}/openvino_decoder_model.xml', flush=True)
    # Print final file size
    for f in ['openvino_decoder_model.xml', 'openvino_decoder_model.bin']:
        p = os.path.join(DST_DIR, f)
        if os.path.exists(p):
            print(f'  {p}: {os.path.getsize(p) / 1024 / 1024:.1f} MB', flush=True)


if __name__ == '__main__':
    main()
