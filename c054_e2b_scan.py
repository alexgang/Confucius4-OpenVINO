"""c054_e2b_scan.py — C-054 E2b: decoder IR 双维扫描（Tt 文本前缀 × Ta 音频帧）

在 c054_e2_seqlen.py 基础上补 Ta 维扫描并落盘 JSON，供 QUANT 报告引用。
回答：INT4 相对 INT8 的开销随 GEMM 尺寸怎么变？「INT4 更慢」在受控条件下成立吗？

用法：.venv python c054_e2b_scan.py
输出：reports/c054_e2_scan.json
"""
import os
import sys
import json
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
OUT = 'reports/c054_e2_scan.json'


def bench(core, path, tt, ta, bsz=1):
    m = core.read_model(path)
    m.reshape({
        'encoder_hidden_states': [bsz, ta, 2048],
        'input_ids': [bsz, tt],
        'beam_idx': [bsz],
    })
    c = core.compile_model(m, DEVICE)
    req = c.create_infer_request()
    ehs = (np.random.randn(bsz, ta, 2048) * 0.1).astype(np.float32)
    ids = np.zeros((bsz, tt), dtype=np.int64)
    bi = np.zeros((bsz,), dtype=np.int32)
    feeds = {'encoder_hidden_states': ehs, 'input_ids': ids, 'beam_idx': bi}
    for inp in m.inputs:          # 必须传 port 对象（本版不接受字符串名）
        req.set_tensor(inp, ov.Tensor(feeds[inp.get_any_name()]))
    ts = []
    for i in range(WARM + RUN):
        t0 = time.perf_counter()
        req.infer()
        ts.append((time.perf_counter() - t0) * 1000)
    return sorted(ts[WARM:])[len(ts[WARM:]) // 2]


def scan(core, tt_list, ta):
    rows = []
    for tt in tt_list:
        row = {'Tt': tt, 'Ta': ta}
        for tag, path in MODELS:
            row[tag] = round(bench(core, path, tt, ta), 3)
        row['ratio'] = round(row['INT4'] / row['INT8'], 3)
        rows.append(row)
        print(f'  Tt={tt:>4} Ta={ta:>4}  INT8 {row["INT8"]:8.2f}  '
              f'INT4 {row["INT4"]:8.2f}  {row["ratio"]:.3f}x', flush=True)
    return rows


def main():
    core = ov.Core()
    out = {'device': DEVICE, 'warm': WARM, 'run': RUN, 'scans': {}}

    print('=== 扫描 A：Tt 1..256（Ta=50，对应 decode / 短前缀）===', flush=True)
    out['scans']['tt'] = scan(core, [1, 2, 4, 8, 16, 32, 64, 128, 256], 50)

    print('=== 扫描 B：Ta 50..1500（Tt=32，对应长前缀 prefill）===', flush=True)
    rows = []
    for ta in [50, 150, 400, 800, 1500]:
        row = {'Tt': 32, 'Ta': ta}
        for tag, path in MODELS:
            row[tag] = round(bench(core, path, 32, ta), 3)
        row['ratio'] = round(row['INT4'] / row['INT8'], 3)
        rows.append(row)
        print(f'  Tt=  32 Ta={ta:>4}  INT8 {row["INT8"]:8.2f}  '
              f'INT4 {row["INT4"]:8.2f}  {row["ratio"]:.3f}x', flush=True)
    out['scans']['ta'] = rows

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'saved -> {OUT}', flush=True)


if __name__ == '__main__':
    main()
