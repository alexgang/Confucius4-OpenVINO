"""c066_npu_find_dynamic.py — 定位编码器里到底哪些 Reshape 是动态的

阶段 0 的实测结果推翻了 reviewer 的静态预筛：

    encoder_FP16 (1955 ops) compile_model(..., 'NPU') FAILED
      → "IE.Reshape doesn't support dynamic shapes"

reviewer 读 XML 后判断「编码器全部静态，最有希望直接上 NPU」。
但实测报 Reshape 动态。本脚本找出**具体是哪些 Reshape** 的 target_const
或输入是部分选择的动态形状。

对动态算子，OpenVINO 的 `Reshape` 有两个输入：
  - `input`（部分动态）
  - `target_const`（可能是 ShapeOf → Range → Concat 算出来的**动态** shape）
关键在于 `target_const` 的**来源算子**：如果它来自 ShapeOf/Range，
那这个 Reshape 的目标形状就是运行期算出来的，NPU 必然不支持。

用法：.venv python c066_npu_find_dynamic.py [model.xml]
输出：reports/c066_encoder_dynamic.json
"""
import json
import os
import sys

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import openvino as ov
from openvino import properties as p

MODEL = (sys.argv[1] if len(sys.argv) > 1 else
         'models/ov-encoder-segment-reviewer/openvino_encoder_model.xml')
OUT = 'reports/c066_encoder_dynamic.json'


def shape_str(sd):
    try:
        return str(sd)
    except Exception:
        return '?'


def main():
    core = ov.Core()
    try:
        core.set_property({'LOG_LEVEL': p.log.Level.ERROR})
    except Exception:
        pass

    model = core.read_model(MODEL)
    nodes = model.get_ordered_ops()

    by_type = {}
    for op in nodes:
        by_type.setdefault(op.get_type_name(), []).append(op)

    out = {'model': MODEL, 'n_ops': len(nodes),
           'op_type_hist': {k: len(v) for k, v in sorted(
               by_type.items(), key=lambda kv: -len(kv[1]))},
           'shapes': {}}

    # 1) 模型输入的形状（reviewer 说 [1,128,2400] + n_valid 是静态的）
    out['inputs'] = []
    for i in model.inputs:
        try:
            ps = i.get_partial_shape()
            out['inputs'].append({
                'name': i.get_any_name(),
                'shape': str(ps),
                'is_static': ps.is_static,
                # Dimension 不可 JSON 序列化，统一转字符串
                'dynamic_dims': [str(d) for d in ps if not d.is_static],
            })
        except Exception as e:
            out['inputs'].append({'name': i.get_any_name(),
                                  'err': str(e)[:200]})

    # 2) 所有 Reshape：哪些动态、target_const 来自哪里
    reshapes = []
    for r in by_type.get('Reshape', []):
        info = {'name': r.get_friendly_name(),
                'output_names': [r.output(i).get_any_name()
                                 for i in range(r.get_output_size())]}
        try:
            src = r.input(0).get_source_output()
            info['input_shape'] = shape_str(src.get_partial_shape())
            info['input_is_static'] = src.get_partial_shape().is_static
        except Exception as e:
            info['input_shape'] = f'ERR {str(e)[:80]}'
            info['input_is_static'] = None
        try:
            tc_src = r.input(1).get_source_output()
            tp = tc_src.get_partial_shape()
            tc_node = tc_src.get_node()
            info['target_const_shape'] = shape_str(tp)
            info['target_const_is_static'] = tp.is_static
            info['target_const_src_op'] = tc_node.get_type_name()
            info['target_const_src_name'] = tc_node.get_friendly_name()
            # 关键：target_const 是不是由 ShapeOf/Range 算出来的
            info['target_const_dynamic_src'] = (
                tc_node.get_type_name() in
                ('ShapeOf', 'Range', 'Constant', 'Concat', 'Add', 'Mul',
                 'Sub', 'Div', 'Gather', 'GatherElements', 'Reshape',
                 'Unsqueeze', 'Squeeze', 'Split', 'Slice', 'ReduceMean',
                 'Cast', 'Convert', 'ConstantDivide'))
        except Exception as e:
            info['target_const_shape'] = f'ERR {str(e)[:80]}'
            info['target_const_is_static'] = None
        reshapes.append(info)

    out['shapes']['Reshape_total'] = len(reshapes)
    out['shapes']['Reshape_input_dynamic'] = sum(
        1 for r in reshapes if r.get('input_is_static') is False)
    out['shapes']['Reshape_target_dynamic'] = sum(
        1 for r in reshapes if r.get('target_const_is_static') is False)
    out['shapes']['Reshape_target_from_shapeof'] = sum(
        1 for r in reshapes
        if r.get('target_const_src_op') in ('ShapeOf', 'Range'))
    bad = [r for r in reshapes
           if r.get('input_is_static') is False
           or r.get('target_const_is_static') is False]
    out['Reshape_dynamic_list'] = bad[:60]
    out['Reshape_static_samples'] = [r for r in reshapes if r not in bad][:5]

    # 3) 其它可能产生动态形状的算子
    shape_ops = {}
    for t in ('ShapeOf', 'Range', 'Gather', 'GatherElements', 'ScatterNDUpdate',
              'ReadValue', 'Assign', 'Less', 'Select', 'NonZero', 'Unique',
              'CumSum', 'ScatterElements'):
        if t in by_type:
            shape_ops[t] = len(by_type[t])
    out['shape_related_ops'] = shape_ops

    # 4) n_valid 的用途：Less/Select 生成掩码
    out['Less_nodes'] = [n.get_friendly_name() for n in by_type.get('Less', [])][:20]
    out['Select_nodes'] = [n.get_friendly_name() for n in by_type.get('Select', [])][:20]

    os.makedirs('reports', exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f'model: {MODEL}')
    print(f'n_ops = {out["n_ops"]}')
    print('\n--- 输入 ---')
    for i in out['inputs']:
        print(f"  {i['name']}: {i.get('shape')}  static={i.get('is_static')}"
              f"  dyn_dims={i.get('dynamic_dims')}")
    print('\n--- 算子类型 TOP12 ---')
    for k, v in list(out['op_type_hist'].items())[:12]:
        print(f'  {k:<28}{v}')
    print('\n--- Reshape 分析 ---')
    s = out['shapes']
    print(f"  Reshape 总数           = {s['Reshape_total']}")
    print(f"  其中 input 动态        = {s['Reshape_input_dynamic']}")
    print(f"  其中 target_const 动态 = {s['Reshape_target_dynamic']}")
    print(f"  target 来自 ShapeOf/Range = {s['Reshape_target_from_shapeof']}")
    print('\n--- 形状相关算子 ---')
    print(f'  {out["shape_related_ops"]}')
    print('\n--- 动态 Reshape 样例（前 5）---')
    for r in out['Reshape_dynamic_list'][:5]:
        print(f"  {r['name']}")
        print(f"     input       = {r['input_shape']} (static={r['input_is_static']})")
        print(f"     target_const= {r['target_const_shape']} "
              f"(static={r['target_const_is_static']}, "
              f"src={r['target_const_src_op']})")
    print(f"\nsaved -> {OUT}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
