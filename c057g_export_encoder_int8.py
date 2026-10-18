"""c057g_export_encoder_int8.py — C-057g: 导出 encoder 的 INT8 变体（三方对比用）

背景（C-057）：encoder 目前纯 FP16（605.6 MiB）。
  - INT4_SYM g128  → 162.5 MiB（-73%），但 teacher-forcing top-1 掉 1.80 pp
  - INT8 很可能是「省内存」诉求下的甜点：预计约 310 MiB，精度损失应显著小于 INT4

本脚本导出两个 INT8 变体做口径对照：
  - INT8_ASYM（per-channel，与 ov-int8-past decoder 同一口径）
  - INT8_SYM （per-channel，对称）

用法：.venv python c057g_export_encoder_int8.py
产物：models/ov-encoder-segment-reviewer-int8asym、...-int8sym
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


def quantize(dst_dir, mode):
    model = ov.Core().read_model(f'{SRC}/openvino_encoder_model.xml')
    t0 = time.perf_counter()
    # INT8 模式不支持 all_layers / backup_mode（必须为 None）；
    # INT4 才需要 all_layers=True + BackupMode.NONE
    if mode in (nncf.CompressWeightsMode.INT8_ASYM,
                nncf.CompressWeightsMode.INT8_SYM):
        compressed = nncf.compress_weights(model, mode=mode, ratio=1.0)
    else:
        compressed = nncf.compress_weights(
            model, mode=mode, ratio=1.0, all_layers=True,
            backup_mode=nncf.BackupMode.NONE)
    print(f'  compress took {time.perf_counter() - t0:.1f}s', flush=True)

    # 统计压缩后的 Const 构成，确认真的落到 u8/i8
    by_prec = {}
    for op in compressed.get_ordered_ops():
        if op.get_type_name() != 'Constant':
            continue
        s = str(op.get_output_element_type(0))
        et = s.split("'")[1] if "'" in s else s
        shape = list(op.get_output_shape(0))
        nel = 1
        for d in shape:
            nel *= d
        bits = {'float16': 16, 'float32': 32, 'uint8_t': 8, 'int8_t': 8,
                'int64_t': 64, 'int32_t': 32, 'int4_t': 4, 'bool': 8}.get(et, 16)
        e = by_prec.setdefault(et, [0, 0])
        e[0] += 1
        e[1] += nel * bits // 8
    for k, v in sorted(by_prec.items(), key=lambda kv: -kv[1][1]):
        if v[1] > 1024:
            print(f'    {k:<10} {v[0]:>5} 个  {v[1] / 1024 ** 2:>9.2f} MiB', flush=True)

    os.makedirs(dst_dir, exist_ok=True)
    # 先复制辅助文件、跳过 IR 本体，避免覆盖刚 save 的结果
    for f in os.listdir(SRC):
        if f.startswith('openvino_encoder_model.'):
            continue
        src = os.path.join(SRC, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, f))
    ov.save_model(compressed, f'{dst_dir}/openvino_encoder_model.xml')
    p = f'{dst_dir}/openvino_encoder_model.bin'
    print(f'  -> {p}: {os.path.getsize(p) / 1024 ** 2:.1f} MiB', flush=True)


def main():
    base = os.path.getsize(f'{SRC}/openvino_encoder_model.bin') / 1024 ** 2
    print(f'[c057g] 源 encoder: {base:.1f} MiB', flush=True)
    for tag, dst, mode in [
        ('INT8_ASYM (per-channel)', f'{SRC}-int8asym',
         nncf.CompressWeightsMode.INT8_ASYM),
        ('INT8_SYM (per-channel)', f'{SRC}-int8sym',
         nncf.CompressWeightsMode.INT8_SYM),
    ]:
        print(f'\n[c057g] === {tag} ===', flush=True)
        t = time.perf_counter()
        quantize(dst, mode)
        sz = os.path.getsize(f'{dst}/openvino_encoder_model.bin') / 1024 ** 2
        print(f'  {base:.1f} → {sz:.1f} MiB '
              f'({100 * (sz / base - 1):+.1f}%)  '
              f'total {time.perf_counter() - t:.1f}s', flush=True)


if __name__ == '__main__':
    main()
