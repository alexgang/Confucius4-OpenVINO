r"""c089b_build_recipe.py — C-089 步骤 2：构建 INT4 配方矩阵（R0–R4）

Reviewer 原文：
> 「统一从 models/qwen3-lm-fp16-cleanie-ov（已删 input_ids，只留 inputs_embeds）出发，
>   用 NNCF 的 nncf.compress_weights 直接压缩，不用重新导出、不用再做端口手术。
>   用 ov.save_model 保存，**保存后先数一遍 i4 / i8 常量个数**确认真的压成 INT4。」
> 「回退精度一律用 backup_mode=INT8_SYM。」
> 「配方：
>   R0 = INT4_SYM 按通道（group_size=-1, ratio=1.0, 无校准）；
>   R1 = INT4_SYM group_size=128 无校准；
>   R2 = 按通道 + awq=True + scale_estimation=True（subset_size=128）；
>   R3 = g128 + AWQ + scale_estimation；
>   R4（可选）= R2/R3 中较好者 + ratio=0.8 + HESSIAN_INPUT_ACTIVATION。」

## 为什么从 fp16-cleanie-ov 出发而不是 int8sym-cleanie-ov

INT4 是在 FP16 权重上做的**一次性**权重量化。若从已 INT8 的 IR 出发，
等于「INT8 → INT4」二次量化，误差会叠加，且无法与 GPU 上验证过的 g128 配方
对照。Reviewer 指定的起点就是 fp16-cleanie-ov。

## 为什么必须数 i4/i8 常量

`compress_weights` 在 OpenVINO 上产出的是 `Convert`/`Multiply` 组合，
常量张量的 dtype 才是唯一可信的证据。只看 IR 大小不够 —— 某些配置会
静默地把大部分层留在 FP16/INT8 而只有少数层被压成 INT4，体积几乎不变、
精度却没改善。所以每次保存后都扫全图常量，按 dtype 计数。

用法：
    python c089b_build_recipe.py R0
    python c089b_build_recipe.py R2 --calib models/c089_int4/calib_0_12min.npz
"""
import argparse
import json
import os
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import openvino as ov

WORK = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORK, 'models', 'qwen3-lm-fp16-cleanie-ov')
# ⚠️ C-090#2 / C-095#4：IR 每个约 1 GiB，**不能**放 reports/（.gitignore 只忽略
# npu_cache）。放 models/c089_int4/，models/ 已被忽略。
# 报告 JSON 仍写 reports/c089_int4/。
OUT_ROOT = os.path.join(WORK, 'models', 'c089_int4')
OUT_REPORTS = os.path.join(WORK, 'reports', 'c089_int4')

# ── 配方定义（严格照 Reviewer 的 R0–R4）────────────────────────────
RECIPES = {
    'R0': dict(desc='INT4_SYM 按通道（group_size=-1, ratio=1.0, 无校准）',
               kw=dict(group_size=-1, ratio=1.0, need_calib=False)),
    'R1': dict(desc='INT4_SYM group_size=128，无校准',
               kw=dict(group_size=128, ratio=1.0, need_calib=False)),
    'R2': dict(desc='按通道 + AWQ + scale_estimation（subset_size=128）',
               kw=dict(group_size=-1, ratio=1.0, awq=True,
                       scale_estimation=True, subset_size=128, need_calib=True)),
    'R3': dict(desc='g128 + AWQ + scale_estimation',
               kw=dict(group_size=128, ratio=1.0, awq=True,
                       scale_estimation=True, subset_size=128, need_calib=True)),
    'R4': dict(desc='R2/R3 中较好者 + ratio=0.8 + HESSIAN_INPUT_ACTIVATION',
               kw=dict(group_size=None, ratio=0.8, awq=True,
                       scale_estimation=True, subset_size=128,
                       sensitivity_metric='HESSIAN_INPUT_ACTIVATION',
                       need_calib=True, inherits_from=('R2', 'R3'))),
}

MODE_NAME = 'INT4_SYM'

# OV 的 str(Type) 是 "<Type: 'float16'>"，要抽出裸名
# OV 打印常量 dtype 用的是 C 风格名：'int4_t' / 'int8_t' / 'float16' / 'int64_t'
_DTYPE_BYTES = {'float64': 8, 'float32': 4, 'int64_t': 8, 'int32_t': 4,
                'int16_t': 2, 'int8_t': 1, 'uint8_t': 1, 'int4_t': 1,
                'uint4_t': 1, 'float16': 2, 'bfloat16': 2, 'boolean': 1,
                'char': 1, 'string': 1,
                # 兼容 numpy 风格名
                'f64': 8, 'f32': 4, 'i64': 8, 'i32': 4, 'i16': 2, 'i8': 1,
                'u8': 1, 'i4': 1, 'u4': 1, 'f16': 2, 'bf16': 2}

_INT4_NAMES = ('int4_t', 'uint4_t', 'i4', 'u4')
_INT8_NAMES = ('int8_t', 'uint8_t', 'i8', 'u8')
_F16_NAMES = ('float16', 'bfloat16', 'f16', 'bf16', 'int16_t', 'i16')


def _dtype_name(dt):
    s = str(dt)
    if "'" in s and s.endswith('>'):
        return s.split("'")[1]
    return s


def count_const_dtypes(model):
    """扫全图常量，按 dtype 计数 + 算总字节。这是「真的压成 INT4 了」的唯一证据。"""
    from collections import Counter
    cnt = Counter()
    bytes_by = Counter()
    for node in model.get_ordered_ops():
        if node.get_type_name() != 'Constant':
            continue
        # OV 2026.4.1 的 Node 只有 get_output_tensor(idx)，没有 get_output_tensors()
        try:
            t = node.get_output_tensor(0)
        except Exception:
            continue
        if t is None:
            continue
        name = _dtype_name(t.get_element_type())
        cnt[name] += 1
        n = 1
        try:
            for d in t.get_shape():
                n *= int(d)
        except Exception:
            pass
        bytes_by[name] += n * _DTYPE_BYTES.get(name, 1)
    return dict(cnt), dict(bytes_by)


def build(name, calib_path=None, overwrite=False):
    import nncf
    from nncf import compress_weights, Dataset
    from nncf.quantization.algorithms.weight_compression.config import \
        CompressWeightsMode

    # ⚠️ NNCF 3.4.0 的 mode 必须是 CompressWeightsMode 枚举（或其小写值字符串
    # 'int4_sym'），传 'INT4_SYM' 这种大写串会在 num_bits 里 KeyError 成
    # "Unsupported compression mode for num_bits: INT4_SYM"。
    MODE = getattr(CompressWeightsMode, MODE_NAME)
    BACKUP = CompressWeightsMode.INT8_SYM
    # ⚠️ sensitivity_metric 也必须是枚举（SensitivityMetric），传大写字符串会在
    # MIXED_PRECISION_CRITERIA.get() 里 KeyError：
    # "HESSIAN_INPUT_ACTIVATION is unknown type of mixed_precision_criteria"。
    SM = nncf.SensitivityMetric

    rc = RECIPES[name]
    kw = dict(rc['kw'])
    inherits = kw.pop('inherits_from', None)
    need_calib = kw.pop('need_calib')
    if name == 'R4':
        base = inherits[0] if inherits else 'R2'
        kw['group_size'] = RECIPES[base]['kw']['group_size']
        print(f'[c089b] R4 继承 {base} 的 group_size='
              f'{kw["group_size"]}（Reviewer 要求取 R2/R3 中较好者）')

    out_dir = os.path.join(OUT_ROOT, name)
    xml = os.path.join(out_dir, 'openvino_model.xml')
    if os.path.exists(xml) and not overwrite:
        print(f'[c089b] {xml} 已存在，跳过构建（要重建加 --overwrite）')
        return out_dir

    print(f'[c089b] 读源模型 {SRC_DIR}')
    assert os.path.exists(os.path.join(SRC_DIR, 'openvino_model.xml')), \
        f'source IR missing: {SRC_DIR}'
    core = ov.Core()
    model = core.read_model(os.path.join(SRC_DIR, 'openvino_model.xml'))

    src_cnt, _ = count_const_dtypes(model)
    print(f'[c089b] 源常量 dtype 分布: {src_cnt}')

    dataset = None
    if need_calib:
        assert calib_path, f'{name} 需要校准数据，请给 --calib'
        z = np.load(calib_path)
        emb_keys = [k for k in z.files if k.startswith('emb_T')]
        assert emb_keys, f'{calib_path} 里没有 emb_T* 数组'

        # ⚠️ 冻结 inputs_embeds 的动态维。
        # 源 IR 的端口是 [1, 1..512, 2048]（T 动态），而 NNCF 的 CPU infer
        # engine 不做 reshape，直接 set_input_tensor 会报
        # "model input (shape=[1,1..512,2048]) and the tensor (shape=(5,121,2048))
        #  are incompatible"。所以必须把 T 冻成具体值，且批维固定为 1
        # —— 与生产路径一致（npu_embeds_backend 每次喂 (1,T,2048)）。
        emb_port = next(p for p in model.inputs
                        if p.get_any_name() == 'inputs_embeds')
        ps = emb_port.get_partial_shape()
        T_MAX = int(ps[1].get_max_length()) if ps[1].is_dynamic \
            else int(ps[1].get_length())

        # ⚠️ **不要 reshape 冻结 T**。源 IR 里 position embedding 是常量
        # `Constant[1,1,512]`，冻结 inputs_embeds 到 [1,512,2048] 会让它与
        # Multiply 的广播校验失败：
        #   "While validating node 'opset1::Multiply ... Constant[1,1,512]
        #    ... Multiply[1,1,512] -> f32[1,1..512,2048]': Argument shapes are inconsistent"
        # 正确做法：**保持动态维**，逐条按真实长度喂 (1, T, 2048)，
        # 批维恒为 1 —— 与生产路径（npu_embeds_backend 每次喂 (1,T,2048)）一致。
        # 之前那次 "tensor (shape=(5,1,21,2048)) incompatible" 的报错纯粹是
        # 因为我把 5 条样本 np.stack 成了批维 5，那才是错的。

        # 保持动态维：每条样本按**真实长度**单独喂一批（批维恒为 1）。
        # ⚠️ npz 里 emb_T{T} 的形状是 (k, 1, T, 2048) —— 每条本身已带一个
        # 批维（build_inputs_embeds 返回 (1,T,2048)，再 stack 就成 4 维）。
        # 必须先 squeeze 掉那一维，否则再套 [None] 会变成 5 维，报
        # "tensor (shape=(1,1,21,2048)) and the model input
        #  (shape=[1,1..512,2048]) are incompatible"。
        items = []
        for k in sorted(emb_keys, key=lambda s: int(s[5:])):
            arr = z[k]
            assert arr.ndim == 4 and arr.shape[1] == 1, \
                f'{k} 形状异常 {arr.shape}，期望 (k,1,T,2048)'
            for row in arr:
                e = np.squeeze(row, 0)            # (T, 2048)
                T = e.shape[0]
                assert T <= T_MAX, f'样本 T={T} > IR 上界 {T_MAX}'
                items.append({
                    'inputs_embeds': e.astype(np.float32)[None, ...],
                    'attention_mask': np.ones((1, T), dtype=np.int64),
                    'position_ids': np.arange(T, dtype=np.int64)[None, :],
                    'beam_idx': np.zeros(1, dtype=np.int32),
                })
        assert items, '校准集为空'
        # ⚠️ emb_T{T} 的形状是 (k, 1, T, 2048) —— T 在**第 2 维**（axis 2），
        # 不是 axis 1（那是批维，恒为 1）。取错会让日志打印成「真实 T ∈ [1,1]」，
        # 看起来像校准数据没长度分布，实际是我读错了轴。
        tmin = min(z[k].shape[2] for k in emb_keys)
        tmax = max(z[k].shape[2] for k in emb_keys)

        # 敏感性分析每条都要前向一次；subset_size=128 是 Reviewer 指定的语义
        # （128 条样本参与统计），这里尊重它。
        subset = int(kw.get('subset_size') or 128)
        use = items[:max(1, min(len(items), subset))]
        print(f'[c089b] 校准：{len(items)} 条候选，喂 {len(use)} 条；'
              f'保持动态维逐条喂（真实 T ∈ [{tmin}, {tmax}]，IR 上界 {T_MAX}）')
        dataset = Dataset(use)

    t0 = time.perf_counter()
    kwargs = dict(model=model, mode=MODE, backup_mode=BACKUP, dataset=dataset)
    kwargs.update(kw)
    # 字符串形态的 sensitivity_metric 换成枚举
    if 'sensitivity_metric' in kwargs and \
            isinstance(kwargs['sensitivity_metric'], str):
        kwargs['sensitivity_metric'] = getattr(
            SM, kwargs['sensitivity_metric'])
    print(f'[c089b] compress_weights(mode={MODE}, backup_mode=INT8_SYM, '
          f'{ {k: v for k, v in kw.items() if v is not None} })')
    compressed = compress_weights(**kwargs)
    build_s = time.perf_counter() - t0

    os.makedirs(out_dir, exist_ok=True)
    t1 = time.perf_counter()
    ov.save_model(compressed, xml, compress_to_fp16=False)
    save_s = time.perf_counter() - t1

    # 保存后重新读回，数 i4/i8 常量 —— 这一步不能省
    check = core.read_model(xml)
    cnt, by_bytes = count_const_dtypes(check)

    def mb(v):
        return round(v / 2 ** 20, 1)

    src_size = sum(os.path.getsize(os.path.join(SRC_DIR, f))
                   for f in os.listdir(SRC_DIR)
                   if f.endswith(('.xml', '.bin')))
    out_size = sum(os.path.getsize(os.path.join(out_dir, f))
                   for f in os.listdir(out_dir) if f.endswith(('.xml', '.bin')))

    i4 = sum(v for k, v in cnt.items() if k in _INT4_NAMES)
    i8 = sum(v for k, v in cnt.items() if k in _INT8_NAMES)
    i16 = sum(v for k, v in cnt.items() if k in _F16_NAMES)
    i4_w = sum(v for k, v in by_bytes.items() if k in _INT4_NAMES)
    i16_w = sum(v for k, v in by_bytes.items() if k in _F16_NAMES)
    i8_w = sum(v for k, v in by_bytes.items() if k in _INT8_NAMES)

    rep = {
        'recipe': name,
        'desc': rc['desc'],
        'params': {k: v for k, v in kw.items() if v is not None},
        'mode': str(MODE),
        'backup_mode': str(BACKUP),
        'calib': calib_path if need_calib else None,
        'src_dir': os.path.relpath(SRC_DIR, WORK),
        'out_dir': os.path.relpath(out_dir, WORK),
        'build_s': round(build_s, 1),
        'save_s': round(save_s, 1),
        'src_const_dtypes': src_cnt,
        'out_const_dtypes': cnt,
        'out_const_MiB': {k: mb(v) for k, v in by_bytes.items()},
        'n_i4_consts': i4,
        'n_i8_consts': i8,
        'n_f16_consts': i16,
        'weight_MiB': {'i4': mb(i4_w), 'i8': mb(i8_w), 'f16': mb(i16_w)},
        'i4_weight_MiB': mb(i4_w),
        'ir_size_MiB': {'src': mb(src_size), 'out': mb(out_size)},
        'verified_int4': bool(i4 > 0),
        'interpretation': (
            f'i4 常量 {i4} 个 / {mb(i4_w)} MiB，'
            f'i8 {i8} 个 / {mb(i8_w)} MiB（backup），'
            f'f16 残留 {i16} 个 / {mb(i16_w)} MiB'
            + ('（残留多为 norm/bias，非权重，可接受）' if i16 else '（无 FP16 残留）')),
        'nncf_bitwidth_note': '对照 NNCF 自报表：int4_sym 层数 / int8_sym backup 层数。'
                              'saved IR 的 int4_t 常量个数应与 int4_sym 层数一致。',
    }
    rep['report'] = os.path.join(OUT_REPORTS, f'{name}_build.json')
    json.dump(rep, open(rep['report'], 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    print('\n' + '=' * 72)
    print(f'{name}: {rc["desc"]}')
    print(f'  常量: i4={i4}  i8={i8}   i4 权重 {rep["i4_weight_MiB"]} MiB')
    print(f'  源常量分布: {src_cnt}')
    print(f'  产物常量分布: {cnt}')
    print(f'  IR 大小: {mb(src_size)} -> {mb(out_size)} MiB')
    print(f'  build {build_s:.1f}s / save {save_s:.1f}s')
    print(f'  **INT4 校验: {"PASS" if i4 > 0 else "FAIL（没有任何 i4 常量！）"}**')
    print('=' * 72)
    return out_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('recipe', choices=sorted(RECIPES))
    ap.add_argument('--calib', default=os.path.join(OUT_ROOT, 'calib_0_12min.npz'))
    ap.add_argument('--overwrite', action='store_true')
    a = ap.parse_args()
    try:
        build(a.recipe, a.calib, a.overwrite)
        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Reviewer 要求：编译失败按原样记录报错，不要绕过
        json.dump({'recipe': a.recipe, 'error': str(e),
                   'traceback': traceback.format_exc()},
                  open(os.path.join(OUT_REPORTS, f'{a.recipe}_build.json'),
                       'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        return 2


if __name__ == '__main__':
    sys.exit(main())
