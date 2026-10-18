"""c058i_fix_matrix_json.py — 用修正后的 u4 语义重算 C-058⑤ 配方矩阵构成

背景：c058d 的 bits 字典漏了 'uint4_t'，fallback 到 16 bit，把 INT4 字节
统计放大恰好 4 倍（3307 MiB vs 实际 852.7 MiB）。c058f_probe_u4.py 已实测
确认：OpenVINO 报出的 u4/i4 Constant shape **已是打包后形状**
（q_proj 2048 行 → shape [2048, 16, 128]，axis1 的 16 = 128 权重 / 8 字节），
因此 nel × 4/8 就是真实字节，修正后与 .bin 比值 1.00×。

本脚本只重算构成、不重新导出（省 GPU/NNCF 时间），并把交叉校验比值写进 JSON。

用法：.venv python c058i_fix_matrix_json.py
"""
import os
import sys
import json

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.modules['torch'] = None

import openvino as ov

SRC_JSON = 'reports/c058_int4_matrix.json'
BITS = {'float16': 16, 'float32': 32, 'uint8_t': 8, 'int8_t': 8,
        'int64_t': 64, 'int32_t': 32, 'int4_t': 4, 'uint4_t': 4, 'bool': 8}


def breakdown(model_dir):
    model = ov.Core().read_model(f'{model_dir}/openvino_decoder_model.xml')
    agg = {}
    for op in model.get_ordered_ops():
        if op.get_type_name() != 'Constant':
            continue
        st = str(op.get_output_element_type(0))
        et = st.split("'")[1] if "'" in st else st
        nel = 1
        for d in op.get_output_shape(0):
            nel *= d
        e = agg.setdefault(et, [0, 0])
        e[0] += 1
        e[1] += nel * BITS.get(et, 16) // 8
    total = sum(v[1] for v in agg.values()) / 1024 ** 2
    binmib = os.path.getsize(f'{model_dir}/openvino_decoder_model.bin') / 1024 ** 2
    return ({k: round(v[1] / 1024 ** 2, 1) for k, v in agg.items() if v[1] > 512},
            round(total, 1), round(binmib, 1), round(total / binmib, 2))


def main():
    with open(SRC_JSON, encoding='utf-8') as f:
        data = json.load(f)
    print(f'{"配方":<24}{"IR MiB":>9}{"≤900":>6}{"校验":>7}  构成')
    for v in data['variants']:
        if 'error' in v or not os.path.isdir(v['dir']):
            print(f'{v["name"]:<24}{"—":>9}{"—":>6}{"—":>7}  (无模型)')
            continue
        comp, total, binmib, ratio = breakdown(v['dir'])
        v['by_precision'] = comp
        v['semantic_mib'] = total
        v['bin_mib'] = binmib
        v['semantic_over_bin'] = ratio
        v['ir_mib'] = binmib
        v['passes_ir_900'] = binmib <= 900
        s = ' | '.join(f'{k} {b}' for k, b in comp.items())
        print(f'{v["name"]:<24}{binmib:>9.1f}'
              f'{"✓" if v["passes_ir_900"] else "✗":>6}{ratio:>7.2f}×  {s}')

    with open(SRC_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'\nupdated -> {SRC_JSON}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
