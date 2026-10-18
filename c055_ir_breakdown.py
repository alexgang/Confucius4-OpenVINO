"""c055_ir_breakdown.py — C-055: 拆解 OV decoder IR 的权重构成（按精度 × 语义分组）

问题：OV INT4 的模型/内存只比 INT8 小 ~10%，而 CUDA Q4_K 比 Q8_0 小 35%。为什么？
本脚本把 decoder IR 的每个 Const 按 element_type 与名字语义分组累加字节数，
回答「哪些权重被量化了、哪些没有」，并给出「全量 4-bit 的理论下限」做对照。

用法：.venv python c055_ir_breakdown.py
输出：reports/c055_ir_breakdown.json + 控制台表格
"""
import os
import re
import sys
import json
import collections

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.path.insert(0, '.')

import openvino as ov

MODELS = [
    ('FP16', 'models/ov-fp16-past/openvino_decoder_model.xml'),
    ('INT8', 'models/ov-int8-past/openvino_decoder_model.xml'),
    ('INT4', 'models/ov-int4-lmfp16-past/openvino_decoder_model.xml'),
]
OUT = 'reports/c055_ir_breakdown.json'

# element_type -> 每元素位数（i4/u4 在 bin 里按 2 个/字节打包）
# 注意 OV Python 侧类型名是 int4_t / uint8_t / float16 这种形式
BITS = {'f32': 32, 'float32': 32, 'f16': 16, 'float16': 16, 'bf16': 16,
        'i8': 8, 'int8_t': 8, 'u8': 8, 'uint8_t': 8,
        'i4': 4, 'int4_t': 4, 'u4': 4, 'uint4_t': 4,
        'i16': 16, 'int16_t': 16, 'u16': 16, 'uint16_t': 16,
        'i32': 32, 'int32_t': 32, 'u32': 32, 'uint32_t': 32,
        'i64': 64, 'int64_t': 64, 'u64': 64, 'uint64_t': 64,
        'boolean': 8, 'bool': 8}


def semantic(name, shape):
    """按名字/形状把 Const 归到语义组。"""
    n = name.lower()
    nel = 1
    for d in shape:
        nel *= d
    if 'embed' in n or (shape and shape[0] >= 100000):
        return 'token embedding / lm_head（词表 151936）'
    if 'layernorm' in n or 'layer_norm' in n or 'norm' in n:
        return 'LayerNorm / RMSNorm'
    if nel <= 4096 and ('bias' in n or 'scale' in n or 'weight' in n):
        return '小张量（bias/scale/零头）'
    if nel <= 65536:
        return '其他小常量（mask/inv_freq 等）'
    return 'transformer 层权重（28 层）'


def type_name(t):
    """ov.Type -> 'f16' / 'int4_t' 这样的短名（str(t) 会带 <Type: '...'> 包装）。"""
    s = str(t)
    if "'" in s:
        return s.split("'")[1]
    return s


def analyze(path):
    m = ov.Core().read_model(path)
    by_prec = collections.defaultdict(lambda: [0, 0])       # prec -> [n, bytes]
    by_sem = collections.defaultdict(lambda: collections.defaultdict(
        lambda: [0, 0]))                                    # sem -> prec -> [n, bytes]
    biggest = []
    for op in m.get_ordered_ops():
        if op.get_type_name() != 'Constant':
            continue
        et = type_name(op.get_output_element_type(0))
        shape = list(op.get_output_shape(0))
        nel = 1
        for d in shape:
            nel *= d
        bits = BITS.get(et, 16)
        nbytes = nel * bits // 8
        name = op.get_friendly_name()
        by_prec[et][0] += 1
        by_prec[et][1] += nbytes
        sem = semantic(name, shape)
        by_sem[sem][et][0] += 1
        by_sem[sem][et][1] += nbytes
        biggest.append((nbytes, et, name, shape))
    total = sum(v[1] for v in by_prec.values())
    return {
        'n_const': sum(v[0] for v in by_prec.values()),
        'total_mib': total / 1024 ** 2,
        'by_precision': {k: {'n': v[0], 'mib': round(v[1] / 1024 ** 2, 1)}
                         for k, v in sorted(by_prec.items(),
                                            key=lambda kv: -kv[1][1])},
        'by_semantic': {s: {p: {'n': v[0], 'mib': round(v[1] / 1024 ** 2, 1)}
                            for p, v in d.items()}
                        for s, d in by_sem.items()},
        'top10': sorted(biggest, reverse=True)[:10],
    }


def main():
    core = ov.Core()
    out = {}
    for tag, path in MODELS:
        if not os.path.exists(path):
            print(f'[{tag}] 缺 {path}')
            continue
        r = analyze(path)
        out[tag] = r
        print(f'\n=== {tag} ===  Const {r["n_const"]} 个，'
              f'合计 {r["total_mib"]:.0f} MiB')
        print(f'{"精度":<8}{"个数":>6}{"MiB":>10}{"占比":>8}')
        for p, v in r['by_precision'].items():
            print(f'{p:<8}{v["n"]:>6}{v["mib"]:>10.1f}'
                  f'{100 * v["mib"] / r["total_mib"]:>7.1f}%')
        print('-- 按语义 --')
        for s, d in sorted(r['by_semantic'].items(),
                           key=lambda kv: -sum(v["mib"] for v in kv[1].values())):
            tot = sum(v['mib'] for v in d.values())
            detail = ' + '.join(f'{p} {v["mib"]:.0f}' for p, v in
                                sorted(d.items(), key=lambda kv: -kv[1]['mib']))
            print(f'  {s:<38} {tot:>8.1f} MiB   [{detail}]')
        print('-- 最大的 5 个 Const --')
        for b, et, name, shape in r['top10'][:5]:
            print(f'  {b / 1024 ** 2:>8.1f} MiB  {et:<5} {name[:44]:<44} {shape}')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}')

    # 理论下限：若 transformer 层权重也全部 4-bit
    if 'INT4' in out and 'FP16' in out:
        f16 = out['FP16']['total_mib']
        i4 = out['INT4']['total_mib']
        print(f'\nFP16 基线 {f16:.0f} MiB → INT4 实际 {i4:.0f} MiB '
              f'（{100 * (i4 / f16 - 1):+.1f}%）')


if __name__ == '__main__':
    main()
