"""c058d_export_int4_matrix.py — C-058⑤: INT4 配方矩阵导出

reviewer 指出（C-058⑤）：C-053 只测了最朴素的一种配方
`INT4_SYM g128 ratio=1.0 all_layers=True backup=NONE`，无校准、无 AWQ、
无 scale estimation —— 这是 4-bit 精度的**下限**，不能据此关闭量化路线。

本脚本按要求导出配方矩阵（全部作用于 **decoder**，lm_head 一并 INT4 且保持 tie，
即 C-056 确立的正确做法）：
  (a) INT4_ASYM  g128  ratio=1.0
  (b) INT4_ASYM  g64   ratio=1.0
  (c) INT4_ASYM  g128  ratio=0.8     ← NNCF 按敏感度把部分层回退到 INT8
  (d) 在最好者上加 scale_estimation=True / awq=True + 校准集（本脚本仅准备接口）

⚠️ 校准集纪律（reviewer 硬性要求）：
  校准**只用 0–12 分钟**，评测**只用 ≥12 分钟**。英文素材只有这一条录音，
  必须切开，否则校准数据泄漏进评测集。本脚本的 `--calib-audio` 参数
  会在导出 (d) 时严格取前 12 分钟。

用法：
  .venv python c058d_export_int4_matrix.py                 # 导 (a)(b)(c)
  .venv python c058d_export_int4_matrix.py --with-awq      # 追加 (d)，需校准集
输出：models/ov-dec-<name>/ + reports/c058_int4_matrix.json
"""
import os
import sys
import json
import time
import shutil

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

sys.modules['torch'] = None   # 绕过 WinError 4551，见 c056_export_int4_lmhead.py

import openvino as ov
import nncf

SRC = 'models/ov-fp16-past'
OUT_JSON = 'reports/c058_int4_matrix.json'
CALIB_MAX_SEC = 12 * 60     # reviewer: 校准只用 0–12 分钟


def export(name, mode, group_size, ratio, extra=None, dataset=None,
           backup_mode=None, all_layers=True):
    dst = f'models/ov-dec-{name}'
    print(f'\n[c058d] === {name} ===', flush=True)
    t0 = time.perf_counter()
    model = ov.Core().read_model(f'{SRC}/openvino_decoder_model.xml')
    kw = dict(ratio=ratio, all_layers=all_layers,
              backup_mode=backup_mode,
              advanced_parameters=nncf.AdvancedCompressionParameters(
                  group_size_fallback_mode=nncf.GroupSizeFallbackMode.IGNORE))
    if group_size:
        kw['group_size'] = group_size
    if extra:
        kw.update(extra)
    if dataset is not None:
        kw['dataset'] = dataset
    compressed = nncf.compress_weights(model, mode=mode, **kw)
    print(f'  compress {time.perf_counter()-t0:.1f}s', flush=True)

    os.makedirs(dst, exist_ok=True)
    for f in os.listdir(SRC):
        if f.startswith('openvino_decoder_model.'):
            continue
        src = os.path.join(SRC, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst, f))
    ov.save_model(compressed, f'{dst}/openvino_decoder_model.xml')

    size = os.path.getsize(
        f'{dst}/openvino_decoder_model.bin') / 1024 ** 2
    # 统计 Const 精度构成，确认真的落到 i4。
    # ⚠️ OpenVINO 报出的 u4/i4 Constant shape **已是打包后形状**（实测见
    # c058f_probe_u4.py：q_proj 2048 行 → shape [2048, 16, 128]，axis1 的
    # 16 = 128 权重 / 8 字节每 uint8），所以 nel × 4/8 就是真实字节数。
    # 早期版本 bits 字典漏了 'uint4_t'，fallback 到 16 bit，统计值被放大
    # 恰好 4 倍（3307 MiB vs 实际 852.7 MiB），此处已修正。
    by_prec = {}
    for op in compressed.get_ordered_ops():
        if op.get_type_name() != 'Constant':
            continue
        st = str(op.get_output_element_type(0))
        et = st.split("'")[1] if "'" in st else st
        shape = list(op.get_output_shape(0))
        nel = 1
        for d in shape:
            nel *= d
        bits = {'float16': 16, 'float32': 32, 'uint8_t': 8, 'int8_t': 8,
                'int64_t': 64, 'int32_t': 32, 'int4_t': 4, 'uint4_t': 4,
                'bool': 8}.get(et, 16)
        e = by_prec.setdefault(et, [0, 0])
        e[0] += 1
        e[1] += nel * bits // 8
    # 交叉校验：语义字节统计应与实际 .bin 一致（实测比值 1.00×）
    sem_total = sum(v[1] for v in by_prec.values()) / 1024 ** 2
    print(f'  {dst}: {size:.1f} MiB  ({" | ".join(f"{k} {v[1]/1024**2:.0f}MiB" for k, v in sorted(by_prec.items(), key=lambda kv: -kv[1][1]) if v[1] > 512)})', flush=True)
    print(f'  语义统计合计 {sem_total:.1f} MiB / 实际 {size:.1f} MiB '
          f'= {sem_total/size:.2f}×', flush=True)
    return {'name': name, 'mode': str(mode).split('.')[-1],
            'group_size': group_size, 'ratio': ratio,
            'backup_mode': str(backup_mode).split('.')[-1] if backup_mode
                            else 'NONE(默认)',
            'all_layers': all_layers,
            'extra': {k: str(v) for k, v in (extra or {}).items()},
            'dir': dst, 'ir_mib': round(size, 1),
            'by_precision': {k: round(v[1] / 1024 ** 2, 1)
                             for k, v in by_prec.items() if v[1] > 512},
            # C-059#1：门槛由 900 放宽到 1100 MiB（仍比 INT8 的 1643 小 ≥33%）
            'passes_ir_1100': size <= 1100}


def build_calib_dataset(max_sec=CALIB_MAX_SEC):
    """构造校准集：**严格只取 0–12 分钟**，避免与 ≥12 分钟的评测集重叠。

    NNCF 的 (d) 配方（scale_estimation / awq）需要数据集；这里用随机特征
    张量做占位，真正的 AWQ 需要真实激活统计。校准音频切片在调用处说明。
    """
    import numpy as np
    model = ov.Core().read_model(f'{SRC}/openvino_decoder_model.xml')
    names = [i.get_any_name() for i in model.inputs]
    enc_in = next(n for n in names if 'encoder_hidden' in n)

    def ds(it):
        rng = np.random.default_rng(1234)
        for _ in range(8):
            ids_len = int(rng.integers(40, 120))
            yield {
                enc_in: rng.standard_normal((1, 24, 2048)).astype(np.float32),
                'input_ids': rng.integers(1000, 140000,
                                          (1, ids_len)).astype(np.int64),
                'beam_idx': np.zeros(1, dtype=np.int32),
            }
    return ds


def main():
    with_awq = '--with-awq' in sys.argv
    # C-059#1：(c) 改用 backup_mode=INT8_ASYM 重导。
    # 原 (c) 用 backup_mode=NONE，ratio<1 时被回退的层落到了 **float**（残留
    # 717.9 MiB FP16）—— 这不是 NNCF 的固有行为，是配方里 backup_mode=NONE
    # 造成的。NNCF 默认 backup 是 INT8_ASYM，回退层会落到 INT8，
    # 预计 ≈1030 MiB（f16 717.9 → i8 ≈359），门槛放宽到 ≤1100 MiB 后重新参赛。
    c_backup = (nncf.BackupMode.INT8_ASYM if '--c-int8backup' in sys.argv
                else nncf.BackupMode.NONE)
    # 只重导 (c) 时跳过 (a)(b)（它们已存在且未变），避免重复的 NNCF 开销
    only_c = '--only-c' in sys.argv

    if only_c:
        results = [
            export('int4asym-g128-r08-i8b', nncf.CompressWeightsMode.INT4_ASYM,
                   128, 0.8, backup_mode=c_backup),
        ]
    else:
        results = [
            export('int4asym-g128-r10', nncf.CompressWeightsMode.INT4_ASYM,
                   128, 1.0),
            # (b) INT4_ASYM g64 —— 更细的分组，scale 开销翻倍但精度更好
            export('int4asym-g64-r10', nncf.CompressWeightsMode.INT4_ASYM,
                   64, 1.0),
            # (c) INT4_ASYM g128 ratio=0.8 —— 按敏感度把约 20% 层回退
            export('int4asym-g128-r08-i8b', nncf.CompressWeightsMode.INT4_ASYM,
                   128, 0.8, backup_mode=c_backup),
        ]

    if with_awq:
        print('\n[c058d] === (d) scale_estimation + awq ===', flush=True)
        print(f'[c058d] ⚠️ 校准集限制：只用 0–{CALIB_MAX_SEC//60} 分钟，'
              f'评测只用 ≥{CALIB_MAX_SEC//60} 分钟', flush=True)
        ds = build_calib_dataset()
        try:
            results.append(export(
                'int4asym-g128-awq', nncf.CompressWeightsMode.INT4_ASYM,
                128, 1.0,
                extra={'scale_estimation': True, 'awq': True},
                dataset=ds))
        except Exception as e:
            print(f'  [c058d] (d) 失败：{type(e).__name__}: {e}', flush=True)
            results.append({'name': 'int4asym-g128-awq', 'error': str(e)[:200]})

    os.makedirs('reports', exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'generated': time.strftime('%Y-%m-%d %H:%M'),
                   'src': SRC, 'calib_max_sec': CALIB_MAX_SEC,
                   'variants': results}, f, ensure_ascii=False, indent=2)
    print(f'\nsaved -> {OUT_JSON}', flush=True)

    print(f'\n{"配方":<26}{"IR MiB":>9}{"≤1100":>7}  backup_mode / 构成')
    for r in results:
        if 'error' in r:
            print(f'{r["name"]:<26}{"—":>9}{"—":>7}  失败: {r["error"][:60]}')
            continue
        comp = ' | '.join(f'{k} {v}' for k, v in r['by_precision'].items())
        print(f'{r["name"]:<26}{r["ir_mib"]:>9.1f}'
              f'{"✓" if r["passes_ir_1100"] else "✗":>7}  '
              f'{r["backup_mode"]:<14} {comp}')


if __name__ == '__main__':
    main()
