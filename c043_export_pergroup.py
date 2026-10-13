"""c043_export_pergroup.py — C-043#3 备选 1: INT8_ASYM per-group (group_size=128) for ALL layers

C-043 验证 lm_head FP16 没有帮助. C-043#3 备选 1: 把量化粒度从 per-channel 改为 per-group (group_size=128).
简化做法: 对整个模型用 INT8_ASYM per-group (group_size=128).
"""
import os, sys, time, shutil
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, '.')

import numpy as np
import openvino as ov
import nncf


SRC_DIR = 'models/ov-fp16-past'
DST_DIR = 'models/ov-int8-pergroup-past'


def main():
    print('[c043-pergroup] === C-043#3 备选 1: INT8_ASYM per-group (group_size=128) ===', flush=True)
    print(f'[c043-pergroup] updated: {time.strftime("%Y-%m-%d %H:%M")}', flush=True)

    print(f'[c043-pergroup] loading FP16 decoder from {SRC_DIR}...', flush=True)
    t0 = time.perf_counter()
    model = ov.Core().read_model(f'{SRC_DIR}/openvino_decoder_model.xml')
    print(f'[c043-pergroup] load took {time.perf_counter()-t0:.1f}s', flush=True)

    print('[c043-pergroup] compressing weights with INT8_ASYM, group_size=128, all_layers=True...', flush=True)
    t1 = time.perf_counter()
    compressed = nncf.compress_weights(
        model,
        mode=nncf.CompressWeightsMode.INT8_ASYM,
        group_size=128,
        all_layers=True,  # 也量化 lm_head 和 embedding (与 c039 plain INT8 一致)
    )
    print(f'[c043-pergroup] compression took {time.perf_counter()-t1:.1f}s', flush=True)

    # Save
    os.makedirs(DST_DIR, exist_ok=True)
    print(flush=True)
    print(f'[c043-pergroup] writing to {DST_DIR}/...', flush=True)
    t2 = time.perf_counter()
    ov.save_model(compressed, f'{DST_DIR}/openvino_decoder_model.xml')
    print(f'[c043-pergroup] save took {time.perf_counter()-t2:.1f}s', flush=True)

    # Copy non-IR files
    print('[c043-pergroup] copying tokenizer/config files from source...', flush=True)
    for f in os.listdir(SRC_DIR):
        if f == 'openvino_decoder_model.xml' or f == 'openvino_decoder_model.bin':
            continue
        src = os.path.join(SRC_DIR, f)
        dst = os.path.join(DST_DIR, f)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            print(f'  copied: {f}', flush=True)

    print(flush=True)
    print(f'[c043-pergroup] DONE. → {DST_DIR}/openvino_decoder_model.xml', flush=True)
    for f in ['openvino_decoder_model.xml', 'openvino_decoder_model.bin']:
        p = os.path.join(DST_DIR, f)
        if os.path.exists(p):
            print(f'  {p}: {os.path.getsize(p) / 1024 / 1024:.1f} MB', flush=True)


if __name__ == '__main__':
    main()
