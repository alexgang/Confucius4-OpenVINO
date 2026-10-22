"""c057c_export_encoder_int4.py — C-057c: 导出 encoder 的 INT4_SYM(g128) 变体

对共享的 `models/ov-encoder-segment-reviewer` encoder IR 跑 NNCF compress_weights，
得到 what-if 变体 `models/ov-encoder-segment-reviewer-int4`。
同时导出 INT8 变体作为精度/体积对照（可选，RUN_INT8=True 时执行）。

用法：.venv python c057c_export_encoder_int4.py
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

sys.modules['torch'] = None   # 绕过 WinError 4551，见 c056_export_int4_lmhead.py

import openvino as ov
import nncf

SRC = 'models/ov-encoder-segment-reviewer'
RUN_INT8 = False


def quantize(src_dir, dst_dir, mode, group_size):
    model = ov.Core().read_model(f'{src_dir}/openvino_encoder_model.xml')
    t0 = time.perf_counter()
    kw = dict(ratio=1.0, all_layers=True,
              backup_mode=nncf.BackupMode.NONE,
              advanced_parameters=nncf.AdvancedCompressionParameters(
                  group_size_fallback_mode=nncf.GroupSizeFallbackMode.IGNORE))
    if group_size:
        kw['group_size'] = group_size
    compressed = nncf.compress_weights(model, mode=mode, **kw)
    print(f'  compress took {time.perf_counter()-t0:.1f}s', flush=True)

    os.makedirs(dst_dir, exist_ok=True)
    # 先复制 tokenizer/config 等辅助文件，跳过 IR 本体，避免覆盖刚 save 的结果
    for f in os.listdir(src_dir):
        if f.startswith('openvino_encoder_model.'):
            continue
        src = os.path.join(src_dir, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, f))
    ov.save_model(compressed, f'{dst_dir}/openvino_encoder_model.xml')
    p = f'{dst_dir}/openvino_encoder_model.bin'
    print(f'  -> {p}: {os.path.getsize(p) / 1024 ** 2:.1f} MiB', flush=True)
    return compressed


def main():
    for tag, dst, mode, gs in [
        ('INT4_SYM g128', f'{SRC}-int4', nncf.CompressWeightsMode.INT4_SYM, 128),
        ('INT8_SYM', f'{SRC}-int8', nncf.CompressWeightsMode.INT8_SYM, None),
    ]:
        if mode == nncf.CompressWeightsMode.INT8_SYM and not RUN_INT8:
            print(f'[c057c] 跳过 {tag}')
            continue
        print(f'[c057c] === {tag} ===', flush=True)
        t = time.perf_counter()
        quantize(SRC, dst, mode, gs)
        print(f'  total {time.perf_counter()-t:.1f}s', flush=True)


if __name__ == '__main__':
    main()
