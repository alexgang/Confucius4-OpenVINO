"""c054_e2_seqlen.py — C-054 E2: 真实 decoder IR 的序列长度扫描

decoder 输入：encoder_hidden_states [B,Ta,2048] f32 / input_ids [B,Tt] i64 / beam_idx [B] i32
通过 reshape 控制 Tt（文本前缀长度）与 Ta（音频帧数），测不同负载下的单次 infer 耗时，
回答：INT4 相对 INT8 的额外开销是「固定成本」还是「随 GEMM 尺寸增长」？

用法：
    .venv python c054_e2_seqlen.py
"""
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import openvino as ov

MODELS = [
    ('INT8', 'models/ov-int8-past/openvino_decoder_model.xml'),
    ('INT4', 'models/ov-int4-lmfp16-past/openvino_decoder_model.xml'),
]
DEVICE = 'GPU.0'
WARM, RUN = 3, 8


def bench(core, path, tt, ta=50, bsz=1):
    m = core.read_model(path)
    m.reshape({  # 固定动态维
        'encoder_hidden_states': [bsz, ta, 2048],
        'input_ids': [bsz, tt],
        'beam_idx': [bsz],
    })
    c = core.compile_model(m, DEVICE)
    req = c.create_infer_request()
    ehs = (np.random.randn(bsz, ta, 2048) * 0.1).astype(np.float32)
    ids = np.zeros((bsz, tt), dtype=np.int64)
    bi = np.zeros((bsz,), dtype=np.int32)
    req.set_tensor('encoder_hidden_states', ehs)
    req.set_tensor('input_ids', ids)
    req.set_tensor('beam_idx', bi)
    ts = []
    for i in range(WARM + RUN):
        t0 = time.perf_counter()
        req.infer()
        ts.append((time.perf_counter() - t0) * 1000)
    return sorted(ts[WARM:])[len(ts[WARM:]) // 2]


def main():
    core = ov.Core()
    print('序列长度扫描（Ta=50 音频帧，中位耗时 ms）')
    print(f'{"Tt":>6}{"INT8":>10}{"INT4":>10}{"INT4/INT8":>11}')
    for tt in [1, 2, 4, 8, 16, 32, 64, 128, 256]:
        row = {}
        for tag, path in MODELS:
            row[tag] = bench(core, path, tt)
        r = row['INT4'] / row['INT8']
        print(f'{tt:>6}{row["INT8"]:>10.2f}{row["INT4"]:>10.2f}{r:>10.2f}x')


if __name__ == '__main__':
    main()
