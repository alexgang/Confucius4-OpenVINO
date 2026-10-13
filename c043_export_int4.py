"""c043_export_int4.py — C-043#3 备选 2: INT4 主干 + FP16 lm_head

C-043 验证 lm_head FP16 (per-channel INT8) 没有帮助.
C-043#3 备选 2: 把 28 层 transformer 量化到 INT4, lm_head 保持 FP16.
NNCF 自动: INT4_SYM 时 embedding 和 last MatMul 保持 INT8_ASYM (backup), 但我们要 lm_head 是 FP16, 所以需要 ignored_scope.
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
DST_DIR = 'models/ov-int4-lmfp16-past'
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
    print('[clone] cloning tied embed weight for lm_head...', flush=True)
    src_const = find_node(model, EMBED_CONST_NAME)
    src_convert = find_node(model, EMBED_CONVERT_NAME)
    lm_head_matmul = find_node(model, LMHEAD_NAME)
    assert src_const is not None
    assert src_convert is not None
    assert lm_head_matmul is not None

    data = src_const.data
    new_const = ops.constant(data.copy(), name='self.model.thinker.lm_head.weight_compressed')
    new_convert = ops.convert(new_const, destination_type=ov.Type.f16, name='self.model.thinker.lm_head.weight')

    weight_input_idx = None
    for i, inp in enumerate(lm_head_matmul.inputs()):
        src = inp.get_source_output()
        if src.get_node() is src_convert:
            weight_input_idx = i
            break
    assert weight_input_idx is not None
    lm_head_matmul.input(weight_input_idx).replace_source_output(new_convert.output(0))

    # activation path Convert(f16) in case NNCF makes activations f32
    activation_input_idx = 1 - weight_input_idx
    activation_src = lm_head_matmul.input(activation_input_idx).get_source_output()
    act_node = activation_src.get_node()
    act_dtype = act_node.get_output_element_type(0)
    if act_dtype != ov.Type.f16:
        new_act_convert = ops.convert(activation_src, destination_type=ov.Type.f16, name='self.model.thinker.lm_head.act_convert')
        lm_head_matmul.input(activation_input_idx).replace_source_output(new_act_convert.output(0))
    print(f'[clone] done, weight_idx={weight_input_idx}, act_idx={activation_input_idx}, act_dtype={act_dtype}', flush=True)
    return model


def main():
    print('[c043-int4] === C-043#3 备选 2: INT4 主干 + FP16 lm_head ===', flush=True)
    print(f'[c043-int4] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print(f'[c043-int4] loading FP16 decoder from {SRC_DIR}...', flush=True)
    t0 = time.perf_counter()
    model = ov.Core().read_model(f'{SRC_DIR}/openvino_decoder_model.xml')
    print(f'[c043-int4] load took {time.perf_counter()-t0:.1f}s', flush=True)

    # Clone tied weight for lm_head
    model = clone_tied_weight(model)

    # NNCF: INT4_SYM, group_size=128 (C-043#3 spec), ratio=1 (all 28 layers to int4)
    # backup_mode=FP16 would make non-int4 layers FP16, but default backup is INT8_ASYM
    # We want lm_head FP16, so ignored_scope
    print('[c043-int4] compressing with INT4_SYM, group_size=128, ratio=1, all_layers=True...', flush=True)
    t1 = time.perf_counter()
    compressed = nncf.compress_weights(
        model,
        mode=nncf.CompressWeightsMode.INT4_SYM,
        ratio=1.0,  # 100% layers to int4 (others stay backup)
        group_size=128,
        all_layers=True,
        ignored_scope=nncf.IgnoredScope(names=[LMHEAD_NAME]),
        backup_mode=nncf.BackupMode.NONE,  # NONE means FP16 (not INT8_ASYM)
        advanced_parameters=nncf.AdvancedCompressionParameters(
            group_size_fallback_mode=nncf.GroupSizeFallbackMode.IGNORE,
        ),
    )
    print(f'[c043-int4] compression took {time.perf_counter()-t1:.1f}s', flush=True)

    # Save
    os.makedirs(DST_DIR, exist_ok=True)
    print(flush=True)
    print(f'[c043-int4] writing to {DST_DIR}/...', flush=True)
    t2 = time.perf_counter()
    ov.save_model(compressed, f'{DST_DIR}/openvino_decoder_model.xml')
    print(f'[c043-int4] save took {time.perf_counter()-t2:.1f}s', flush=True)

    # Copy non-IR files
    print('[c043-int4] copying tokenizer/config files from source...', flush=True)
    for f in os.listdir(SRC_DIR):
        if f == 'openvino_decoder_model.xml' or f == 'openvino_decoder_model.bin':
            continue
        src = os.path.join(SRC_DIR, f)
        dst = os.path.join(DST_DIR, f)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f'  copied: {f}', flush=True)

    print(flush=True)
    print(f'[c043-int4] DONE. → {DST_DIR}/openvino_decoder_model.xml', flush=True)
    for f in ['openvino_decoder_model.xml', 'openvino_decoder_model.bin']:
        p = os.path.join(DST_DIR, f)
        if os.path.exists(p):
            print(f'  {p}: {os.path.getsize(p) / 1024 / 1024:.1f} MB', flush=True)


if __name__ == '__main__':
    main()
