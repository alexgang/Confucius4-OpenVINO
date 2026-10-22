"""c058f_probe_u4.py — 诊断 INT4(u4/i4) Constant 的 shape 语义

背景：c058d 的 by_precision 报 uint4_t 3307 MiB，而实际 .bin 只有 852.7 MiB。
需要确认 OpenVINO 对 u4 Constant 报告的 shape 到底是「逻辑形状」还是「打包形状」，
以及同一权重是否存在多个 Constant（原始 f16 残留 + 打包后 u4）。

只读模型，不编译，不占 GPU。
"""
import os
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.modules['torch'] = None

import openvino as ov

DST = sys.argv[1] if len(sys.argv) > 1 else 'models/ov-dec-int4asym-g128-r10'

model = ov.Core().read_model(f'{DST}/openvino_decoder_model.xml')

agg = {}
samples = []
for op in model.get_ordered_ops():
    if op.get_type_name() != 'Constant':
        continue
    st = str(op.get_output_element_type(0))
    et = st.split("'")[1] if "'" in st else st
    shape = list(op.get_output_shape(0))
    nel = 1
    for d in shape:
        nel *= d
    e = agg.setdefault(et, [0, 0, []])
    e[0] += 1
    e[1] += nel
    if len(e[2]) < 4 and nel > 1000:
        e[2].append((op.get_friendly_name(), shape))

print(f'=== {DST} ===')
for et, (n, nel, smp) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
    print(f'\n{et:<12} count={n:<5} sum(nel)={nel:,}  '
          f'naive4bit={nel*4/8/1024**2:.1f} MiB')
    for nm, sh in smp:
        print(f'    {nm[:48]:<50} shape={sh}')

# 关键校验：u4 的 nel 是否等于打包后真实存储
print('\n=== 交叉校验 ===')
tot_4bit_naive = sum(v[1] for k, v in agg.items() if k in ('uint4_t', 'int4_t')) * 4 / 8
tot_other = sum(v[1] for k, v in agg.items() if k not in ('uint4_t', 'int4_t')) * 16 / 8
bin_mib = os.path.getsize(f'{DST}/openvino_decoder_model.bin') / 1024 ** 2
print(f'naive 4bit 常量      : {tot_4bit_naive/1024**2:10.1f} MiB')
print(f'naive 其它常量(f16)  : {tot_other/1024**2:10.1f} MiB')
print(f'naive 合计           : {(tot_4bit_naive+tot_other)/1024**2:10.1f} MiB')
print(f'实际 .bin            : {bin_mib:10.1f} MiB')
print(f'比值                 : {(tot_4bit_naive+tot_other)/1024**2/bin_mib:10.2f}×')
