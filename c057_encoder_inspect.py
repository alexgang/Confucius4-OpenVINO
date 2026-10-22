"""c057_encoder_inspect.py — C-057: 确认 encoder 端当前权重精度 + INT4 理论上限

问题：encoder 端目前用的量化精度是多少？如果也量化到 INT4 会有多大变化？

本脚本做两件事：
1. 读 encoder IR（共享的 ov-encoder-segment-reviewer，以及 decoder 目录内的副本），
   逐个 Constant 统计 element_type 与字节数，确认「磁盘存的到底是什么精度」。
2. 列出各语义组的字节数，给出「若全量 INT4_SYM(group_size=128)」的理论体积下限。

用法：.venv python c057_encoder_inspect.py
输出：reports/c057_encoder_ir.json + 控制台表格
"""
import os
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

# 流式 backend 实际加载的共享 encoder，以及 decoder 目录里未加载的副本
TARGETS = [
    ('SEG-REVIEWER(共享/实际加载)', 'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml'),
    ('INT8目录内encoder副本', 'models/ov-int8-past/openvino_encoder_model.xml'),
    ('INT4-LMFP16目录内副本', 'models/ov-int4-lmfp16-past/openvino_encoder_model.xml'),
    ('FP16目录内encoder副本', 'models/ov-fp16-past/openvino_encoder_model.xml'),
]
OUT = 'reports/c057_encoder_ir.json'

BITS = {'f32': 32, 'float32': 32, 'f16': 16, 'float16': 16, 'bf16': 16,
        'i8': 8, 'int8_t': 8, 'u8': 8, 'uint8_t': 8,
        'i4': 4, 'int4_t': 4, 'u4': 4, 'uint4_t': 4,
        'i16': 16, 'int16_t': 16, 'u16': 16, 'uint16_t': 16,
        'i32': 32, 'int32_t': 32, 'u32': 32, 'uint32_t': 32,
        'i64': 64, 'int64_t': 64, 'u64': 64, 'uint64_t': 64,
        'boolean': 8, 'bool': 8}

# INT4_SYM + group_size=128：每 128 个元素存 1 个 f16 scale + 1 个 i4 zero-point
#   → 5.5 bits/元素（含 scale/zp 摊薄后）。OV 的 int4_t 常量在 IR 里是
#   [C, group_size/2, 2] 的打包形式，按 4 bit 算字节。
INT4_BITS_PER_ELEM = 4 + 20 / 128.0  # 4 (data) + 16 (f16 scale) + 4 (i4 zp) per 128


def int4_bytes_for_shape(shape):
    """[out, in] 的 2D 权重按 INT4_SYM(g128) 打包后的字节数。"""
    nel = 1
    for d in shape:
        nel *= d
    return int(nel * INT4_BITS_PER_ELEM / 8)


def type_name(t):
    s = str(t)
    if "'" in s:
        return s.split("'")[1]
    return s


def semantic(name, shape, nel):
    n = name.lower()
    if 'conv' in n and 'patch' not in n and 'proj' in n:
        return '输入投影 conv / patch_embed'
    if nel <= 4096:
        return '小张量（bias/scale/位置/mask）'
    if nel <= 65536:
        return '其他小常量（inv_freq 等）'
    return 'encoder transformer 层权重'


def analyze(path):
    m = ov.Core().read_model(path)
    by_prec = collections.defaultdict(lambda: [0, 0])
    by_sem = collections.defaultdict(lambda: collections.defaultdict(
        lambda: [0, 0]))
    biggest = []
    conv_fc = collections.Counter()
    total_w = 0
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
        sem = semantic(name, shape, nel)
        by_sem[sem][et][0] += 1
        by_sem[sem][et][1] += nbytes
        conv_fc[op.get_type_name()] += 1
        biggest.append((nbytes, et, name, shape))
        if bits >= 8:
            total_w += nel  # 可量化的大权重元素数
    total = sum(v[1] for v in by_prec.values())
    # 理论下限：把「大权重 Const」（>=1 MiB，即真权重而非 bias/mask）
    # 全部按 INT4_SYM(group_size=128) 打包；小张量保持原精度
    theory = 0
    small_left = 0
    for b, et, nm, sh in biggest:
        if b >= 1024 ** 2 and BITS.get(et, 16) >= 8:
            theory += int4_bytes_for_shape(sh)
        else:
            small_left += b
    theory += small_left
    return {
        'n_const': sum(v[0] for v in by_prec.values()),
        'total_mib': round(total / 1024 ** 2, 2),
        'by_precision': {k: {'n': v[0], 'mib': round(v[1] / 1024 ** 2, 2)}
                         for k, v in sorted(by_prec.items(), key=lambda kv: -kv[1][1])},
        'by_semantic': {s: {p: {'n': v[0], 'mib': round(v[1] / 1024 ** 2, 2)}
                            for p, v in d.items()}
                        for s, d in by_sem.items()},
        'op_types': dict(conv_fc),
        'top8': [(round(b / 1024 ** 2, 2), et, nm[:50], sh)
                 for b, et, nm, sh in sorted(biggest, reverse=True)[:8]],
        'int4_theory_mib': round(theory / 1024 ** 2, 1),
        'int4_theory_big_weights': len([1 for b, e, n, s in biggest
                                        if b >= 1024 ** 2 and BITS.get(e, 16) >= 8]),
    }


def main():
    out = {}
    for tag, path in TARGETS:
        if not os.path.exists(path):
            print(f'[{tag}] 缺 {path}')
            continue
        r = analyze(path)
        out[tag] = r
        print(f'\n=== {tag} ===')
        print(f'  Const {r["n_const"]} 个，合计 {r["total_mib"]:.1f} MiB')
        print(f'  {"精度":<10}{"个数":>6}{"MiB":>10}{"占比":>8}')
        for p, v in r['by_precision'].items():
            print(f'  {p:<10}{v["n"]:>6}{v["mib"]:>10.2f}'
                  f'{100 * v["mib"] / r["total_mib"]:>7.1f}%')
        print('  -- 按语义 --')
        for s, d in sorted(r['by_semantic'].items(),
                           key=lambda kv: -sum(v["mib"] for v in kv[1].values())):
            tot = sum(v['mib'] for v in d.values())
            detail = ' + '.join(f'{p} {v["mib"]:.1f}' for p, v in
                                sorted(d.items(), key=lambda kv: -kv[1]['mib']))
            print(f'    {s:<36} {tot:>8.1f} MiB  [{detail}]')
        print('  -- 最大的 5 个 Const --')
        for mib, et, nm, sh in r['top8'][:5]:
            print(f'    {mib:>8.2f} MiB  {et:<6} {nm:<50} {sh}')
        print(f'  → 全量 INT4_SYM(g128) 理论体积：{r["int4_theory_mib"]:.0f} MiB'
              f'（-{100 * (1 - r["int4_theory_mib"] / r["total_mib"]):.0f}%）')
        print(f'  -- op 类型 top --  {dict(sorted(r["op_types"].items(), key=lambda kv: -kv[1])[:6])}')

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}')


if __name__ == '__main__':
    main()
