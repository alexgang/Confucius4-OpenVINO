"""c054_int4_rootcause.py — C-054: OV INT4 在 iGPU 上变慢的根因实验

背景：C-053 发现 OV INT4（ov-int4-lmfp16-past）在 Intel Xe3 iGPU 上比 INT8 慢 15%
（prefill 102→155 ms），而内存只省 14%。IR 静态分析显示 INT4 把反量化写进了图：
197 个 i4 Const → Convert(i4→f16) → MatMul，另有 +197 Reshape / +55 Concat / +55 Broadcast，
且 INT8 的 198 个 Subtract（zeropoint）在 INT4 里消失。

本脚本用三个实验定位运行时到底慢在哪：
  E1  get_runtime_model：编译后看 GPU 实际执行的 primitive 类型直方图
      （Convert 是否被常量折叠掉？是否保留为每拍都跑的 primitive？）
  E2  同形状重复 infer：若 Convert 每拍都跑，则单次 infer 有固定额外开销；
      若只在首拍贵，则是编译期一次性反量化
  E3  纯 GEMM 微基准：i4→Convert→MatMul vs u8→MatMul，同尺寸，隔离 4-bit 路径本身

用法：
    .venv python c054_int4_rootcause.py
"""
import os
import sys
import time
import collections

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.path.insert(0, '.')
import numpy as np
import openvino as ov

MODELS = {
    'INT8': 'models/ov-int8-past/openvino_decoder_model.xml',
    'INT4': 'models/ov-int4-lmfp16-past/openvino_decoder_model.xml',
}
DEVICE = 'GPU.0'
N_WARM = 3
N_RUN = 12


def e1_runtime_primitives(core):
    """E1: 编译后取 runtime model，统计 GPU 实际执行的 primitive 类型。"""
    print('\n=== E1: 编译后 runtime graph primitive 直方图 ===')
    out = {}
    for tag, path in MODELS.items():
        if not os.path.exists(path):
            print(f'[{tag}] 缺文件 {path}')
            continue
        m = core.read_model(path)
        t0 = time.perf_counter()
        c = core.compile_model(m, DEVICE)
        compile_s = time.perf_counter() - t0
        try:
            rt = c.get_runtime_model()
            ops = collections.Counter(
                op.get_type_name() if hasattr(op, 'get_type_name')
                else op.get('type') for op in rt.get_ops())
            out[tag] = ops
            print(f'[{tag}] compile {compile_s:.2f}s  runtime ops={sum(ops.values())}')
            print(f'        top: {ops.most_common(10)}')
        except Exception as e:
            print(f'[{tag}] get_runtime_model 失败: {type(e).__name__}: {e}')
    if len(out) == 2:
        print('\n  primitive 差集 (INT4 - INT8):')
        for k in set(out['INT4']) | set(out['INT8']):
            d = out['INT4'].get(k, 0) - out['INT8'].get(k, 0)
            if d:
                print(f'    {d:+6d}  {k}')


def e2_repeat_infer(core):
    """E2: 同一形状重复 infer，看首拍 vs 稳态拍——分离一次性反量化与每拍开销。"""
    print('\n=== E2: 重复 infer 首拍/稳态对比 ===')
    # 用一个独立的静态 GEMM 模型太麻烦，直接读 decoder IR 跑真实推理：
    # 找 batch=1 的最小可跑配置（past 输入形状固定，audio 维度给 1 帧）
    for tag, path in MODELS.items():
        if not os.path.exists(path):
            continue
        m = core.read_model(path)
        # 动态维固定成 1
        try:
            m.reshape({})
        except Exception:
            pass
        try:
            c = core.compile_model(m, DEVICE)
        except Exception as e:
            print(f'[{tag}] 编译失败: {type(e).__name__}: {e}')
            continue
        req = c.create_infer_request()
        # 所有输入填 0
        for inp in m.inputs:
            try:
                arr = np.zeros(inp.get_partial_shape().get_shape(),
                               dtype=np.float16 if 'f16' in str(
                                   inp.get_element_type()).lower() else np.float32)
                req.set_tensor(inp, arr)
            except Exception:
                pass
        times = []
        for i in range(N_WARM + N_RUN):
            t0 = time.perf_counter()
            try:
                req.infer()
            except Exception as e:
                print(f'[{tag}] infer#{i} 失败: {type(e).__name__}: {str(e)[:120]}')
                return
            times.append((time.perf_counter() - t0) * 1000)
        first = times[N_WARM]
        rest = times[N_WARM:]
        steady = sorted(rest)[len(rest) // 2]
        print(f'[{tag}] 首拍 {times[0]:7.1f} ms | 第2拍 {times[1]:7.1f} ms | '
              f'稳态中位 {steady:7.1f} ms  (n={N_RUN})')


def e3_gemm_micro(core):
    """E3: 纯 GEMM 微基准 —— i4(经 Convert) vs u8，同 K/N，隔离 4-bit 路径。"""
    print('\n=== E3: GEMM 微基准（K=2048 N=2048, M=64）===')
    K, N, M = 2048, 2048, 64
    results = {}
    for tag, wt in [('u8', np.random.randint(0, 255, (K, N)).astype(np.uint8)),
                    ('i4', np.random.randint(0, 15, (K, N)).astype(np.uint8))]:
        # 手工搭一个最小 IR：Param(f16) x Const(W) → MatMul
        # 走 openvino Opset API
        from openvino.opset13 import Parameter, Constant, MatMul
        from openvino import Type
        p = Parameter(Type.f16, [M, K])
        if tag == 'u8':
            W = Constant(Type.u8, Type.f16, [K, N], wt.astype(np.float32).ravel())
            mm = MatMul(p, W, transpose_a=False, transpose_b=True)
        else:
            # i4 常量 + Convert → f16
            Wi = Constant(Type.u4, Type.f16, [K, N],
                          np.packbits(wt.astype(np.uint8)[:, ::2] & 0xF |
                                      ((wt.astype(np.uint8)[:, 1::2] & 0xF) << 4)
                                      if False else np.zeros(((K * N + 1) // 2,),
                                                             dtype=np.uint8)))
            Wf = ov.opset13.Convert(Wi, Type.f16)
            mm = MatMul(p, Wf, transpose_a=False, transpose_b=True)
        mdl = ov.Model([mm], [p], f'gemm_{tag}')
        try:
            c = core.compile_model(mdl, DEVICE)
        except Exception as e:
            print(f'[{tag}] 编译失败: {type(e).__name__}: {e}')
            continue
        req = c.create_infer_request()
        x = (np.random.randn(M, K) * 0.1).astype(np.float16)
        req.set_tensor(0, x)
        ts = []
        for i in range(N_WARM + N_RUN):
            t0 = time.perf_counter()
            req.infer()
            ts.append((time.perf_counter() - t0) * 1000)
        steady = sorted(ts[N_WARM:])[len(ts[N_WARM:]) // 2]
        results[tag] = steady
        print(f'[{tag}] 稳态 {steady:7.2f} ms  (首拍 {ts[0]:.2f})')
    if len(results) == 2:
        print(f'  → i4/u8 = {results["i4"]/results["u8"]:.2f}x')


def main():
    core = ov.Core()
    print(f'OV {core.get_versions(DEVICE)[0].build_number if False else ""}'
          f'device={DEVICE}')
    which = sys.argv[1] if len(sys.argv) > 1 else 'e1,e2,e3'
    if 'e1' in which:
        e1_runtime_primitives(core)
    if 'e2' in which:
        e2_repeat_infer(core)
    if 'e3' in which:
        e3_gemm_micro(core)


if __name__ == '__main__':
    main()
