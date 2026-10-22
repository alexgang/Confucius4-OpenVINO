"""c054_e1_rtinfo.py — C-054 E1: 从 runtime model 提取每类 primitive 的数量与 GPU 耗时

OpenVINO 2026.x 的 `CompiledModel.get_runtime_model()` 返回的 ExecutionNode 带 rt_info：
  layerType / primitiveType / runtimePrecision / execTimeMcs / execOrder
execTimeMcs 是插件实测的单 primitive 耗时（微秒），可直接定位 INT4 慢在哪类算子上。

用法：
    .venv python c054_e1_rtinfo.py
"""
import os
import sys
import collections

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import openvino as ov

MODELS = [
    ('INT8', 'models/ov-int8-past/openvino_decoder_model.xml'),
    ('INT4', 'models/ov-int4-lmfp16-past/openvino_decoder_model.xml'),
]
DEVICE = 'GPU.0'


def grab(ri, key):
    """安全地从 RTMap 取标量值。"""
    try:
        v = ri[key]
    except Exception:
        return None
    for attr in ('value',):
        try:
            return getattr(v, attr)
        except Exception:
            pass
    try:
        return ov.Any.cast(v)
    except Exception:
        pass
    try:
        return str(v)
    except Exception:
        return None


def collect(tag, path, core):
    import numpy as np
    m = core.read_model(path)
    c = core.compile_model(m, DEVICE)
    # 先跑一次推理，否则 execTimeMcs 全是 'not_executed'
    try:
        req = c.create_infer_request()
        for inp in m.inputs:
            shp = inp.get_partial_shape()
            if shp.is_dynamic():
                shp = ov.PartialShape([1 if d.is_dynamic() else d.get_length()
                                       for d in shp])
            et = inp.get_element_type()
            dt = {ov.Type.f16: np.float16, ov.Type.f32: np.float32,
                  ov.Type.i64: np.int64, ov.Type.i32: np.int32,
                  ov.Type.boolean: np.bool_}.get(et, np.float32)
            arr = np.zeros(shp.get_shape(), dtype=dt)
            req.set_tensor(inp, arr)
        req.infer()
    except Exception as e:
        print(f'[{tag}] 预热 infer 失败（execTimeMcs 可能为 not_executed）: '
              f'{type(e).__name__}: {str(e)[:150]}')
    rt = c.get_runtime_model()
    rows = []
    for op in rt.get_ops():
        if op.get_type_name() != 'ExecutionNode':
            continue
        ri = op.get_rt_info()
        pt = grab(ri, 'primitiveType')
        lt = grab(ri, 'layerType')
        rp = grab(ri, 'runtimePrecision')
        et = grab(ri, 'execTimeMcs')
        try:
            us = float(et)
        except (TypeError, ValueError):
            us = 0.0   # 'not_executed' 等非数值
        rows.append({'pt': str(pt), 'lt': str(lt), 'rp': str(rp), 'us': us})
    print(f'[{tag}] ExecutionNodes={len(rows)}')
    return rows


def summarize(rows):
    by = collections.defaultdict(lambda: [0, 0.0])
    for r in rows:
        k = (r['pt'], r['rp'])
        by[k][0] += 1
        by[k][1] += r['us']
    return by


def main():
    core = ov.Core()
    all_rows = {}
    for tag, path in MODELS:
        if not os.path.exists(path):
            print(f'[{tag}] 缺 {path}')
            continue
        all_rows[tag] = collect(tag, path, core)

    if len(all_rows) < 2:
        return
    a = summarize(all_rows['INT8'])
    b = summarize(all_rows['INT4'])

    print('\n=== primitive 类型 × runtimePrecision：数量 / 总耗时(us) ===')
    print(f'{"primitive":<26}{"prec":<8}{"INT8 n":>7}{"INT8 us":>10}'
          f'{"INT4 n":>7}{"INT4 us":>10}{"Δus":>9}')
    keys = sorted(set(a) | set(b),
                  key=lambda k: -(b.get(k, [0, 0])[1] - a.get(k, [0, 0])[1]))
    tot8 = sum(v[1] for v in a.values())
    tot4 = sum(v[1] for v in b.values())
    for k in keys:
        na, ta = a.get(k, [0, 0.0])
        nb, tb = b.get(k, [0, 0.0])
        if na == 0 and nb == 0:
            continue
        print(f'{k[0]:<26}{k[1]:<8}{na:>7}{ta:>10.0f}{nb:>7}{tb:>10.0f}'
              f'{tb - ta:>+9.0f}')
    print(f'{"TOTAL":<26}{"":<8}{"":>7}{tot8:>10.0f}{"":>7}{tot4:>10.0f}'
          f'{tot4 - tot8:>+9.0f}')

    # Convert / reorder 类 primitive 的明细（权重反量化路径）
    print('\n=== 权重反量化相关 primitive 明细 ===')
    for tag, rows in all_rows.items():
        sel = [r for r in rows
               if any(s in r['pt'].lower() for s in
                      ('convert', 'reorder', 'decompress'))]
        print(f'[{tag}] n={len(sel)}  us={sum(r["us"] for r in sel):.0f}')
        for r in sel[:8]:
            print(f'    {r["pt"]:<24} {r["rp"]:<6} {r["us"]:>8.0f} us')


if __name__ == '__main__':
    main()
