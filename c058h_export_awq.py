"""c058h_export_awq.py — C-058⑤(d): 真实校准集驱动的 AWQ / scale_estimation

reviewer 指出（C-058⑤）：C-053 只测了最朴素的一种配方
`INT4_SYM g128 ratio=1.0`，无校准、无 AWQ、无 scale estimation —— 这是
4-bit 精度的**下限**，不能据此关闭量化路线。

本脚本是 (d) 的实现：
  - 校准集来自 **c058g_calib_collect.py** 采的**真实 0–12 分钟激活**；
  - 配方：INT4_ASYM g128 ratio=1.0 + `scale_estimation=True` + `awq=True`；
  - lm_head 一并 INT4 且保持 tie（同 C-056 确立的正确做法）。

⚠️ 校准集纪律（reviewer 硬性要求）：
  校准**只用 0–12 分钟**，评测**只用 ≥12 分钟**。英文素材只有这一条 61 分钟
  录音，必须切开，否则校准数据泄漏进评测集。本脚本在加载 npz 后会**硬性断言**
  `split_sec <= 720`，越界直接退出。

用法：
  .venv python c058g_calib_collect.py            # 先采真实校准集
  .venv python c058h_export_awq.py                # 再导出 (d)
输出：models/ov-dec-int4asym-g128-awq/ + reports/c058_awq_export.json
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
import numpy as np

SRC = 'models/ov-fp16-past'
CALIB_NPZ = 'reports/c058_calib_0_12min.npz'
OUT_DIR = 'models/ov-dec-int4asym-g128-awq'
OUT_JSON = 'reports/c058_awq_export.json'
CALIB_MAX_SEC = 12 * 60


def load_calib(path=CALIB_NPZ, n_max=16):
    """加载真实校准集，并硬性校验未越过 12 分钟。"""
    d = np.load(path, allow_pickle=False)
    split = int(d['split_sec'])
    assert split <= CALIB_MAX_SEC, (
        f'校准集 split_sec={split}s 越过 12 分钟上限，会泄漏进评测集！')
    ehs = d['encoder_hidden_states']
    ids = d['input_ids']
    n = min(n_max, ehs.shape[0], ids.shape[0])
    print(f'[c058h] 校准集 {path}: split={split}s '
          f'(<= {CALIB_MAX_SEC}s ✓)  ehs={ehs.shape} ids={ids.shape} '
          f'取前 {n} 条', flush=True)
    return ehs[:n], ids[:n]


def make_dataset(ehs, ids, repeat=4):
    """构造 NNCF 要求的 dataset 迭代器。

    每条样本 = 一份完整 dict（encoder_hidden_states / input_ids / beam_idx）。
    `repeat` 让 AWQ 的显著性统计有足够样本量（每条激活被看多次）。
    """
    def ds():
        for _ in range(repeat):
            for i in range(ehs.shape[0]):
                yield {
                    'encoder_hidden_states': ehs[i:i + 1].astype(np.float32),
                    'input_ids': ids[i:i + 1].astype(np.int64),
                    'beam_idx': np.array([0], dtype=np.int32),
                }
    return ds


def main():
    if not os.path.exists(CALIB_NPZ):
        print(f'[c058h] ✗ 缺少真实校准集 {CALIB_NPZ}\n'
              f'       请先运行：python c058g_calib_collect.py', flush=True)
        return 1

    ehs, ids = load_calib()
    ds = make_dataset(ehs, ids)

    print(f'[c058h] loading FP16 decoder from {SRC} ...', flush=True)
    model = ov.Core().read_model(f'{SRC}/openvino_decoder_model.xml')

    print('[c058h] compress_weights: INT4_ASYM g128 ratio=1.0 '
          'scale_estimation=True awq=True （真实校准集）...', flush=True)
    t0 = time.perf_counter()
    try:
        compressed = nncf.compress_weights(
            model,
            mode=nncf.CompressWeightsMode.INT4_ASYM,
            ratio=1.0,
            group_size=128,
            all_layers=True,
            backup_mode=nncf.BackupMode.NONE,
            scale_estimation=True,
            awq=True,
            dataset=ds,
            advanced_parameters=nncf.AdvancedCompressionParameters(
                group_size_fallback_mode=nncf.GroupSizeFallbackMode.IGNORE),
        )
    except Exception as e:
        print(f'[c058h] ✗ AWQ 失败：{type(e).__name__}: {e}', flush=True)
        os.makedirs('reports', exist_ok=True)
        with open(OUT_JSON, 'w', encoding='utf-8') as f:
            json.dump({'ok': False, 'error': f'{type(e).__name__}: {e}',
                       'calib': CALIB_NPZ, 'calib_split_sec': CALIB_MAX_SEC,
                       'n_calib': int(ehs.shape[0])}, f,
                      ensure_ascii=False, indent=2)
        print(f'[c058h] saved -> {OUT_JSON}', flush=True)
        return 2
    print(f'[c058h] compress took {time.perf_counter()-t0:.1f}s', flush=True)

    os.makedirs(OUT_DIR, exist_ok=True)
    for f in os.listdir(SRC):
        if f.startswith('openvino_decoder_model.'):
            continue
        s = os.path.join(SRC, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(OUT_DIR, f))
    ov.save_model(compressed, f'{OUT_DIR}/openvino_decoder_model.xml')

    size = os.path.getsize(f'{OUT_DIR}/openvino_decoder_model.bin') / 1024 ** 2
    print(f'[c058h] {OUT_DIR}: {size:.1f} MiB  '
          f'{"✓ 通过 ≤900 MiB" if size <= 900 else "✗ 超过 900 MiB"}', flush=True)

    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump({'ok': True, 'dir': OUT_DIR, 'ir_mib': round(size, 1),
                   'passes_ir_900': size <= 900,
                   'calib': CALIB_NPZ, 'calib_split_sec': CALIB_MAX_SEC,
                   'n_calib': int(ehs.shape[0]),
                   'mode': 'INT4_ASYM', 'group_size': 128, 'ratio': 1.0,
                   'awq': True, 'scale_estimation': True,
                   'compress_sec': round(time.perf_counter() - t0, 1)}, f,
                  ensure_ascii=False, indent=2)
    print(f'[c058h] saved -> {OUT_JSON}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
