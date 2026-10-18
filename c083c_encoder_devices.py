"""c083c_encoder_devices.py — 「无GPU 机器」的最后一格：编码器在 CPU 上的延迟。

c083b 已证明纯 CPU 跑不动 LM（prefill 1029.6 ms vs NPU 177.1 ms）。无独显机器上
编码器只能落 CPU（落 NPU 慢 1.504×，c069d 实测）。编码器占 stream wall 15.2%
（c080h），它的 CPU 延迟直接决定这类机器的整体可行性。

## 前两版踩的坑（勿重复）

1. **不能手工 compile encoder IR 再 `infer({'input_features': feats})`**：
   动态时间维下 CPU 插件报
   `Reshape 'aten::reshape/Reshape' Check 'minusOneCount <= 1 && inputProduct == outputProduct' failed`，
   GPU 报 `broadcast_merge_into ... op::Add`。正确做法是走
   `SegEncoderOVBackend.encode_audio`（c080h 用的同一条路）——
   它先跑 WhisperFeatureExtractor 拿到真实帧，再按IR 端口构造。
2. 该 IR 含**匿名张量**，取输出必须 `model.output(0)`，`get_any_name()` 会抛
   `Attempt to get a name for a Tensor without names`。
3. 该 encoder 是**单输入版**，无 `n_valid` 端口（那是双输入变体）。

## 测法

同一份真实音频段，`OVBackend` 只换 `device`（CPU / GPU.0），跑 `encode_audio`
3 次取中位。warmup 与 c080h 同口径（5/12/18 s 三段）。

输出：reports/c083c_encoder_devices.json
"""
import json
import os
import statistics
import sys
import time

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

SR = 16000
START, END = 12 * 60, 27 * 60
SEGS = [(13.0, 0), (17.6, 1), (13.3, 2)]      # 与 c080h 的前 3 段同长
REPS = 3
OUT = 'reports/c083c_encoder_devices.json'


def main():
    a, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if a.ndim > 1:
        a = a[:, 0]
    assert sr == SR
    clip = a[SR * START:SR * END]

    from backends import OVBackend

    rep = {'note': '无 GPU 机器可行性：生产 encoder 在 CPU / GPU.0 上的单段延迟。'
                   'NPU 侧已有 c069d ABBA 实测（47.68 vs 31.70 ms，慢 1.504×）。',
           'encoder_ir': 'models/ov-encoder-segment-reviewer',
           'slice_sec': [START, END],
           'segs_sec': [s[0] for s in SEGS],
           'reps_per_seg': REPS,
           'npu_reference': {'source': 'reports/c069d_npu_latency_abba.json',
                             'gpu_ms_median': 31.70, 'npu_ms_median': 47.68,
                             'npu_over_gpu': 1.504},
           'runs': {}}

    for dev in ('GPU.0', 'CPU'):
        print(f'\n===== encoder @ {dev} =====', flush=True)
        try:
            be = OVBackend(model_dir='models/ov-int8-past', device=dev,
                           precision='f16')
            for s in (5, 12, 18):# warmup，与 c080h 同口径
                be.encode_audio(clip[:SR * s])
            rows = []
            for dur, idx in SEGS:
                w = clip[:SR * int(dur)]
                ts = []
                for _ in range(REPS):
                    t0 = time.perf_counter()
                    ehs, _, N = be.encode_audio(w)
                    ts.append((time.perf_counter() - t0) * 1000)
                ts.sort()
                rows.append({'dur_s': dur, 'n_audio': int(N),
                             'enc_ms_median': round(ts[REPS // 2], 1),
                             'enc_ms_all': [round(x, 1) for x in ts]})
                print(f'  dur={dur:.1f}s N_audio={N} enc={ts[REPS//2]:.1f} ms',
                      flush=True)
            med = round(statistics.median(
                [r['enc_ms_median'] for r in rows]), 1)
            rep['runs'][dev] = {'device': dev, 'status': 'ok',
                                'rows': rows, 'median_ms': med}
            print(f'  -> 中位 {med} ms', flush=True)
        except Exception as e:
            rep['runs'][dev] = {'device': dev, 'status': 'failed',
                                'error': str(e)[:400]}
            print(f'  失败: {str(e)[:250]}', flush=True)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)

    # ── 汇总 + 与已知值对照 ───────────────────────────────────────
    print('\n===== 汇总（encoder 单段中位）=====', flush=True)
    tab = {}
    for k in ('GPU.0', 'CPU'):
        v = rep['runs'].get(k, {})
        if v.get('status') == 'ok':
            tab[k] = v['median_ms']
            print(f'  {k:8s} {v["median_ms"]:>7} ms', flush=True)
    tab['NPU (c069d)'] = rep['npu_reference']['npu_ms_median']
    print(f'  {"NPU(ref)":8s} {rep["npu_reference"]["npu_ms_median"]:>7} ms',
          flush=True)
    if 'CPU' in tab and 'GPU.0' in tab and tab['CPU'] > 0:
        rep['cpu_over_gpu_encoder'] = round(tab['CPU'] / tab['GPU.0'], 2)
        print(f"\n  CPU/GPU encoder = {rep['cpu_over_gpu_encoder']}×", flush=True)

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print('\nsaved ->', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
