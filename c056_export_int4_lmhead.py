"""c056_export_int4_lmhead.py — C-056: INT4 全量变体（lm_head 也进 INT4，tie 保留）

背景（C-055 发现）：交付的 `ov-int4-lmfp16-past` 只把 28 层 transformer + embed_tokens
量化到 INT4，lm_head 刻意保留 FP16（`c043_export_int4.py` 的 ignored_scope +
clone_tied_weight），代价是词表矩阵被复制成两份（148 MiB i4 + 594 MiB f16 = 746 MiB），
「INT4 省内存」的卖点基本落空。

本脚本导出 what-if 变体 `ov-int4-lmhead-past`：
  - 不 clone、不 ignored_scope → embed_tokens 与 lm_head 共用同一份 i4 常量（tie 保留）
  - INT4_SYM per-group g128, ratio=1.0, all_layers=True, backup_mode=NONE
  - 预期 decoder IR ≈ 995 MiB（1440 - 594 + 148），比 INT8 小 ~39%

用法：.venv python c056_export_int4_lmhead.py
"""
import os
import sys
import time
import shutil

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

# 本机 Windows 应用控制策略阻止了 torch_python.dll（WinError 4551），NNCF 的
# backend 自动探测只 suppress(ImportError)，OSError 会漏出去。置
# sys.modules['torch'] = None 可把 import torch 变成 ImportError 被吞掉，
# NNCF 退化为纯 numpy backend（compress_weights 不需要 torch）。
sys.modules['torch'] = None

import openvino as ov
import nncf

SRC_DIR = 'models/ov-fp16-past'
DST_DIR = 'models/ov-int4-lmhead-past'
LMHEAD_NAME = '__module.model.thinker.lm_head/aten::linear/MatMul'
EMBED_CONVERT_NAME = 'self.model.thinker.model.embed_tokens.weight'


def main():
    print('[c056-int4lm] === INT4 全量（lm_head 也 INT4，tie 保留）===', flush=True)
    print(f'[c056-int4lm] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print(f'[c056-int4lm] loading FP16 decoder from {SRC_DIR}...', flush=True)
    t0 = time.perf_counter()
    model = ov.Core().read_model(f'{SRC_DIR}/openvino_decoder_model.xml')
    print(f'[c056-int4lm] load took {time.perf_counter()-t0:.1f}s', flush=True)

    print('[c056-int4lm] compressing: INT4_SYM g128, ratio=1.0, all_layers=True, '
          'backup=NONE, 无 ignored_scope（lm_head 一起量化）...', flush=True)
    t1 = time.perf_counter()
    compressed = nncf.compress_weights(
        model,
        mode=nncf.CompressWeightsMode.INT4_SYM,
        ratio=1.0,
        group_size=128,
        all_layers=True,
        backup_mode=nncf.BackupMode.NONE,   # NONE = 保持 FP16（不备份 INT8）
        advanced_parameters=nncf.AdvancedCompressionParameters(
            group_size_fallback_mode=nncf.GroupSizeFallbackMode.IGNORE,
        ),
    )
    print(f'[c056-int4lm] compression took {time.perf_counter()-t1:.1f}s',
          flush=True)

    # 验证 lm_head MatMul 的权重确实来自 i4 常量（tie 保留 = 与 embed 同一份）
    for op in compressed.get_ordered_ops():
        if op.get_friendly_name() == LMHEAD_NAME:
            w = op.input_values()[1].get_node()
            src = w
            if w.get_type_name() == 'Convert':
                src = w.input_values()[0].get_node()
            print(f'[c056-int4lm] lm_head 权重来源: {src.get_type_name()} '
                  f'{src.get_friendly_name()[:60]} '
                  f'et={src.get_output_element_type(0)} '
                  f'shape={list(src.get_output_shape(0))}', flush=True)
            break

    os.makedirs(DST_DIR, exist_ok=True)
    print(f'[c056-int4lm] writing to {DST_DIR}/...', flush=True)
    t2 = time.perf_counter()
    ov.save_model(compressed, f'{DST_DIR}/openvino_decoder_model.xml')
    print(f'[c056-int4lm] save took {time.perf_counter()-t2:.1f}s', flush=True)

    for f in os.listdir(SRC_DIR):
        if f.startswith('openvino_decoder_model.'):
            continue
        src = os.path.join(SRC_DIR, f)
        if os.path.isfile(src) and not os.path.exists(os.path.join(DST_DIR, f)):
            shutil.copy2(src, os.path.join(DST_DIR, f))

    for f in ['openvino_decoder_model.xml', 'openvino_decoder_model.bin']:
        p = os.path.join(DST_DIR, f)
        if os.path.exists(p):
            print(f'  {p}: {os.path.getsize(p) / 1024 / 1024:.1f} MB', flush=True)
    print('[c056-int4lm] DONE.', flush=True)


if __name__ == '__main__':
    main()
