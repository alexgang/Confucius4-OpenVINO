"""c057b_encoder_quant_probe.py — C-057b: 探查 encoder IR 里哪些层可被 NNCF 权重量化

关注 MatMul / Conv / Gather 及其输入权重来源，统计「可被 compress_weights 覆盖的
MatMul 权重字节数 vs 总权重字节数」，同时列出每个 MatMul 的权重 shape。
输出：控制台 + reports/c057_quant_probe.json
"""
import os
import sys
import json
import collections

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.path.insert(0, '.')
import openvino as ov

SRC = 'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml'
OUT = 'reports/c057_quant_probe.json'
BITS = {'float32': 32, 'f32': 32, 'float16': 16, 'f16': 16, 'bf16': 16,
        'int8_t': 8, 'uint8_t': 8, 'int4_t': 4, 'uint4_t': 4,
        'int64_t': 64, 'int32_t': 32}


def tn(t):
    s = str(t)
    return s.split("'")[1] if "'" in s else s


def trace_const(node, depth=0):
    """回溯到产生权重的 Const。"""
    seen = set()
    while depth < 8:
        if node is None:
            return None, None
        k = id(node)
        if k in seen:
            return None, None
        seen.add(k)
        if node.get_type_name() == 'Constant':
            return tn(node.get_output_element_type(0)), list(node.get_output_shape(0))
        srcs = [i.get_node() for i in node.input_values() if i.get_node() is not None]
        cands = [s for s in srcs if s.get_type_name() == 'Constant']
        if cands:
            n = cands[-1]
            return tn(n.get_output_element_type(0)), list(n.get_output_shape(0))
        # Convert/Reshape 只包一个输入时继续往里走
        single = [s for s in srcs if s.get_type_name() in ('Convert', 'Reshape', 'Squeeze')]
        if len(single) == 1 and len(srcs) == 1:
            node = single[0]
            depth += 1
            continue
        return None, None
    return None, None


def main():
    core = ov.Core()
    m = core.read_model(SRC)

    opcount = collections.Counter()
    mm = []
    const_bytes = 0
    quant_bytes = 0
    skipped = []

    for op in m.get_ordered_ops():
        opcount[op.get_type_name()] += 1
        if op.get_type_name() != 'MatMul':
            continue
        ins = [i for i in op.input_values()]
        if len(ins) < 2:
            continue
        # 权重通常是第 2 个输入（decoder 是 [1]）
        for wi in (1, 0):
            et, sh = trace_const(ins[wi].get_node())
            if et is None:
                continue
            nel = 1
            for d in (sh or []):
                nel *= d
            nb = nel * BITS.get(et, 16) // 8
            if nb < 1024 * 64:      # <64 KiB 视为非权重（激活/索引）
                continue
            mm.append((op.get_friendly_name()[:56], et, sh, round(nb / 1024 ** 2, 3)))
            if BITS.get(et, 16) >= 8:
                quant_bytes += nb
            break
        else:
            skipped.append(op.get_friendly_name()[:56])

    for op in m.get_ordered_ops():
        if op.get_type_name() == 'Constant':
            sh = list(op.get_output_shape(0))
            nel = 1
            for d in sh:
                nel *= d
            const_bytes += nel * BITS.get(tn(op.get_output_element_type(0)), 16) // 8

    print('=== encoder IR op 类型 top15 ===')
    for k, v in opcount.most_common(15):
        print(f'  {k:<22} {v}')
    print(f'\n总 Const 字节：{const_bytes / 1024 ** 2:.1f} MiB')
    print(f'MatMul(权重>=64KiB) 数量：{len(mm)}')
    print(f'  其中常量权重（可量化）：{quant_bytes / 1024 ** 2:.1f} MiB '
          f'({100 * quant_bytes / const_bytes:.1f}% of Const)')
    print(f'  动态权重 MatMul：{len(skipped)}')
    print('\n=== MatMul 权重明细（按字节降序，前 15）===')
    for nm, et, sh, mb in sorted(mm, key=lambda x: -x[3])[:15]:
        print(f'  {mb:>8.3f} MiB  {et:<9} {sh!s:<18} {nm}')

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({
            'opcount': dict(opcount),
            'const_mib': round(const_bytes / 1024 ** 2, 2),
            'n_matmul_weight': len(mm),
            'quantizable_mib': round(quant_bytes / 1024 ** 2, 2),
            'cover_pct': round(100 * quant_bytes / const_bytes, 1),
            'n_dynamic_matmul': len(skipped),
            'matmuls': mm,
        }, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT}')


if __name__ == '__main__':
    main()
