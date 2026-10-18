"""c052_ov_vs_cuda.py — C-053: OV INT4 vs INT8 流式基准（OV 侧 4-bit 对照）

背景
----
CUDA 版报告（`C:\\Users\\Trekker-PTL\\confucius4-r2t2\\stream_report.html`）是在
**6.74 s / 320 ms 块 / RTX 5050 Laptop** 上测的。此前 OV 侧只有 61-min / 640 ms 块的
数据，两边音频、块长、硬件全不一样，直接比 RTF 没有意义。

本脚本把 OV 侧拉到同一条起跑线上：
  - 同一段音频 `test.wav`（6.74 s，16 kHz mono 16-bit）
  - 同一块长 320 ms
  - 同一台机器；并且本机 `GPU.1` 就是 **NVIDIA RTX 5050 Laptop**，
    OpenVINO 也能在上面跑 —— 于是可以在**同一块卡**上做「CUDA 运行时 vs OV 运行时」对照，
    把「运行时/量化差异」和「硬件差异」分开。

跑三组（GPU.1 那条腿跑不通，见下）：
  | key      | 设备   | 含义                                    | 状态 |
  |----------|--------|-----------------------------------------|------|
  | ov_igpu  | GPU.0  | 交付默认：Intel Xe3 iGPU + OV INT8-past | ✅   |
  | ov_dgpu  | GPU.1  | 同卡对照：RTX 5050 + OV INT8-past       | ❌   |
  | ov_cpu   | CPU    | 参考：纯 CPU 延迟量级                    | ✅   |

  ❌ **GPU.1 为什么跑不了**：本机 GPU.1 是 NVIDIA RTX 5050，OV 2026.4 的
  intel_gpu 插件确实能枚举到它（报 FP32/BIN/INT8，无 FP16），但 encoder IR
  是 FP16 常量，编译到 `convert:Convert_23531` 这个 F16→F32 reorder 节点时
  kernel_selector 找不到可用实现，`compile_model` 直接抛 RuntimeError。
  f32 / f16 / 默认 / HETERO 四种配置都试过，全部失败。
  所以「OV 跑在 NVIDIA 卡上」在本机不成立，只能做到 iGPU vs CUDA-dGPU 的对比。

CUDA 侧的 65 ms/块、RTF 0.544 直接引用那份报告，不在此处重跑（audio.cpp 是
独立二进制，不在本仓库构建链路内）。

采集内容
--------
1. **逐块延迟**：包裹 `backend.encode_audio` / `backend.generate_with_prefix` 计时，
   与 CUDA 报告的「Encoder / Decoder Prefill」两栏口径对齐。
2. **进程资源**：后台线程 250 ms 采样 RSS(≈WorkingSet) / USS(≈Private) / CPU%，
   与 CUDA 报告 `stream_metrics.csv` 的 ws_mb / private_mb / cpu_pct 同名同单位。
3. **GPU**：`typeperf` 抓 Windows 性能计数器
   `\\GPU Engine(*)\\Utilization Percentage` 与 `\\GPU Adapter Memory(*)\\{Dedicated,Shared} Usage`，
   按 **LUID** 把实例映射回 GPU.0/GPU.1（OV 的 `DEVICE_LUID` 可直接比对）。

用法
----
    .venv/Scripts/python.exe c052_ov_vs_cuda.py
    .venv/Scripts/python.exe c052_ov_vs_cuda.py --devices GPU.1,GPU.0,CPU
    .venv/Scripts/python.exe c052_ov_vs_cuda.py --chunk-ms 640     # 对齐 61-min 口径

产物
----
    reports/c052_ov_vs_cuda/
        summary.json            三组汇总
        chunks_<key>.csv        逐块延迟
        proc_<key>.csv          进程资源时间线
        gpu_<key>.csv / gpumem_<key>.csv   GPU 计数器原始值
"""
import os
import sys
import csv
import json
import time
import argparse
import threading
from typing import List, Dict

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.abspath(__file__))
ENC = 'models/ov-encoder-segment-reviewer'
DEC = 'models/ov-int4-lmfp16-past'
OUT_DIR = 'reports/c053_int4'

DEFAULT_WAV = r'C:\Users\Trekker-PTL\confucius4-r2t2\test.wav'
SAMPLE_INTERVAL = 0.25  # 与 CUDA 报告的 250 ms 采样间隔一致

# CUDA 侧引用值（来自 confucius4-r2t2/stream_report.html + stream_metrics.csv）
CUDA_REF = {
    'label': 'CUDA (audio.cpp v0.9.1, GGUF Q8_0)',
    'device': 'NVIDIA RTX 5050 Laptop 8GB / CUDA 13.3',
    'audio_s': 6.74,
    'chunk_ms': 320,
    'n_chunks': 22,
    'wall_s': 3.67,
    'rtf': 0.544,
    'per_chunk_ms_mean': 65.0,
    'per_chunk_ms_steady': 55.5,
    'per_chunk_ms_first': 264.5,
    'throughput_chunks_per_s': 6.0,
    'ws_mb_peak': 2515,
    'private_gb_peak': 4.8,
    'gpu_mem_mb_peak': 3355,
    'gpu_util_pct_peak': 96,
    'text': '之前有顾客自己带酒水也没加收钱或者不让喝。',
}


# ───────────────────────── 资源采样 ─────────────────────────
class ResourceSampler(threading.Thread):
    """250 ms 采样一次进程内存 / CPU%，同时（可选）读 GPU 计数器。

    字段与 CUDA 报告的 `stream_metrics.csv` 对齐：
        ws_mb      ≈ WorkingSet（psutil 取 RSS）
        private_mb ≈ Private（psutil 取 USS，即进程独占）
        cpu_pct    CPU 占用率（多核可 >100）
        gpu_util_pct / gpu_mem_mb  来自 Windows PDH 计数器
    """

    GPU_PATHS = [r'\GPU Engine(*)\Utilization Percentage',
                 r'\GPU Adapter Memory(*)\Dedicated Usage',
                 r'\GPU Adapter Memory(*)\Shared Usage']

    def __init__(self, luid: str = None, interval: float = SAMPLE_INTERVAL):
        super().__init__(daemon=True)
        self.interval = interval
        self.luid = luid
        self.rows: List[Dict] = []
        self._gq = None
        # 不能叫 _stop —— threading.Thread 内部已有同名方法，会覆盖掉
        self._halt = threading.Event()

    def run(self):
        import psutil
        import os
        from win_gpu_perf import GpuQuery

        p = psutil.Process()
        pid_tag = f'pid_{os.getpid()}_'
        if self.luid:
            try:
                self._gq = GpuQuery(self.GPU_PATHS, luid_filter=self.luid)
            except Exception as e:
                print(f'[c053] GPU 计数器不可用: {e}', flush=True)
                self._gq = None

        t0 = time.perf_counter()
        while not self._halt.is_set():
            try:
                mi = p.memory_info()
                try:
                    uss = p.memory_full_info().uss
                except Exception:
                    uss = mi.rss
                cpu = p.cpu_percent(interval=None)
            except Exception:
                break
            row = {
                't_s': round(time.perf_counter() - t0, 3),
                'ws_mb': round(mi.rss / 1024 ** 2, 1),
                'private_mb': round(uss / 1024 ** 2, 1),
                'cpu_pct': round(cpu, 2),
            }
            if self._gq is not None:
                vals = self._gq.sample()
                util = [v for k, v in vals.items()
                        if 'utilization percentage' in k.lower()
                        and pid_tag.lower() in k.lower()]
                mem = [v for k, v in vals.items()
                       if ('dedicated usage' in k.lower()
                           or 'shared usage' in k.lower())]
                row['gpu_util_pct'] = round(max(util), 1) if util else 0.0
                row['gpu_mem_mb'] = round(sum(mem) / 1024 ** 2, 1) if mem else 0.0
            self.rows.append(row)
            self._halt.wait(self.interval)

        if self._gq is not None:
            self._gq.close()
            self._gq = None

    def stop(self):
        self._halt.set()
        self.join(timeout=3.0)

    def peaks(self):
        keys = self.rows[0].keys() if self.rows else []
        return {f'{k}_peak': max((r.get(k, 0) for r in self.rows), default=0)
                for k in keys if k != 't_s'}


# ───────────────────────── GPU LUID ─────────────────────────
def device_luids(devices: List[str]) -> Dict[str, str]:
    """取每个 OV 设备的 LUID（低 8 位），用于匹配 Windows 计数器实例名。

    计数器实例长这样：
        \\GPU Engine(pid_1234_luid_0x00000000_0x00012EAE_phys_0_eng_0_engtype_3D)\\...
        \\GPU Adapter Memory(luid_0x00000000_0x00012EAE_phys_0)\\Dedicated Usage
    把 OV 的 DEVICE_LUID 取低 4 字节按 little-endian 拼成 0x%08X 即可对上。
    """
    out = {}
    try:
        from win_gpu_perf import luid_low
    except Exception:
        return out
    for d in devices:
        try:
            v = luid_low(d)
        except Exception:
            v = None
        if v:
            out[d] = v
    return out


# ───────────────────────── 计时包裹 ─────────────────────────
class TimedInfer:
    """包裹 ov.InferRequest，逐次记录 infer() 耗时（毫秒）。

    注意：不能只在 Python 层包 `backend.encode_audio` / `generate_with_prefix`
    —— `generate_with_prefix` 内部走的是 `self.encode_audio`（真 backend），
    会绕过外层代理，导致 enc_ms 恒为 0。
    直接替换 `backend.enc_infer` / `backend.dec_infer` 实例属性才拦得到。
    """

    def __init__(self, inner):
        self._inner = inner
        self.calls: List[float] = []

    def reset(self):
        self.calls = []

    def infer(self, *a, **kw):
        t = time.perf_counter()
        out = self._inner.infer(*a, **kw)
        self.calls.append((time.perf_counter() - t) * 1000.0)
        return out

    def reset_state(self):
        return self._inner.reset_state()

    @property
    def total_ms(self):
        return sum(self.calls)

    @property
    def first_ms(self):
        return self.calls[0] if self.calls else 0.0

    @property
    def rest_ms(self):
        return sum(self.calls[1:])

    @property
    def n(self):
        return len(self.calls)

    def __getattr__(self, k):
        return getattr(self._inner, k)


class TimedBackend:
    """薄代理：把 enc_infer / dec_infer 换成 TimedInfer，其余属性透传。"""

    def __init__(self, backend):
        self._b = backend
        self.enc_t = TimedInfer(backend.enc_infer)
        self.dec_t = TimedInfer(backend.dec_infer)
        backend.enc_infer = self.enc_t
        backend.dec_infer = self.dec_t

    def __getattr__(self, k):
        return getattr(self._b, k)

    def reset_chunk(self):
        self.enc_t.reset()
        self.dec_t.reset()

    @property
    def enc_ms(self):
        return self.enc_t.total_ms

    @property
    def prefill_ms(self):
        return self.dec_t.first_ms

    @property
    def decode_ms(self):
        return self.dec_t.rest_ms

    @property
    def n_dec(self):
        return self.dec_t.n


# ───────────────────────── 主流程 ─────────────────────────
def run_one(device: str, audio: np.ndarray, chunk_ms: float,
            adaptive: bool, out_dir: str) -> Dict:
    from segment_encoder_backend import SegmentEncoderOVBackend
    from streaming_asr import (streaming_transcribe,
                               finish_streaming_transcribe)

    key = {'GPU.0': 'ov_igpu', 'GPU.1': 'ov_dgpu', 'CPU': 'ov_cpu'}.get(
        device, device.replace('.', '').lower())
    print(f'\n[c053] === {key}  device={device} ===', flush=True)

    # GPU.1（NVIDIA）在本版 OV 里不报 FP16 能力，用 f32 才能编过；
    # GPU.0（Intel iGPU）与交付口径一致用 f16。
    precision = 'f32' if device == 'GPU.1' else 'f16'
    t_build = time.perf_counter()
    backend = SegmentEncoderOVBackend(
        encoder_dir=ENC, decoder_dir=DEC, device=device, precision=precision,
        strict_intel=not device.startswith('GPU.1'),
    )
    build_s = time.perf_counter() - t_build
    print(f'[c053] {key}: 模型编译 {build_s:.2f}s', flush=True)

    chunk_samples = int(round(chunk_ms * 16000 / 1000))

    # ── 预热：编译后第一次推理会直接吐 EOS，必须废弃 ──
    ws = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=chunk_ms / 1000.0)
    streaming_transcribe(backend, audio[:chunk_samples * 2], ws,
                         max_new_tokens=32, adaptive_budget=adaptive)
    finish_streaming_transcribe(backend, ws, max_new_tokens=32)
    print(f'[c053] {key}: 预热完成', flush=True)

    # ── 正式跑 ──
    tb = TimedBackend(backend)
    state = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=chunk_ms / 1000.0)

    luid = device_luids([device]).get(device)
    ps = ResourceSampler(luid=luid)

    chunks: List[Dict] = []
    wall_start = time.perf_counter()
    ps.start()
    n_chunks = 0
    prev_text = ''
    for s in range(0, len(audio), chunk_samples):
        blk = audio[s:s + chunk_samples]
        tb.reset_chunk()
        t0 = time.perf_counter()
        text, _fixed = streaming_transcribe(
            tb, blk, state, max_new_tokens=32, adaptive_budget=adaptive)
        dt = (time.perf_counter() - t0) * 1000.0
        n_chunks += 1
        try:
            delta = text[len(prev_text):].strip() if text.startswith(prev_text) \
                else text
        except Exception:
            delta = text
        prev_text = text
        chunks.append({
            'chunk': n_chunks,
            'enc_ms': round(tb.enc_ms, 1),
            'prefill_ms': round(tb.prefill_ms, 1),
            'decode_ms': round(tb.decode_ms, 1),
            'total_ms': round(dt, 1),
            'n_dec': tb.n_dec,
            'text': text,
            'delta': delta[:60],
        })
        print(f"[c053] {key} chunk {n_chunks:2d}: "
              f"enc={tb.enc_ms:6.1f} prefill={tb.prefill_ms:6.1f} "
              f"dec={tb.decode_ms:6.1f} tot={dt:6.1f}ms  {delta[:40]!r}",
              flush=True)

    t_flush = time.perf_counter()
    final_text = finish_streaming_transcribe(tb, state, max_new_tokens=32)
    flush_ms = (time.perf_counter() - t_flush) * 1000.0
    wall = time.perf_counter() - wall_start

    ps.stop()

    audio_dur = len(audio) / 16000.0
    tot_ms = [c['total_ms'] for c in chunks]
    steady = tot_ms[1:] or tot_ms
    # 稳态 RTF：去掉首块（含编译后首次推理的额外开销）后，逐块耗时之和 / 音频时长。
    # 与 CUDA 报告的「稳态每块延迟」口径一致，便于跨运行时比较。
    rtf_steady = (sum(steady) / 1000.0) / audio_dur if steady else 0.0

    # 写 CSV
    with open(os.path.join(out_dir, f'chunks_{key}.csv'), 'w',
              newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(chunks[0].keys()))
        w.writeheader()
        w.writerows(chunks)
    if ps.rows:
        with open(os.path.join(out_dir, f'proc_{key}.csv'), 'w',
                  newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list(ps.rows[0].keys()))
            w.writeheader()
            w.writerows(ps.rows)

    res = {
        'key': key,
        'device': device,
        'device_name': _dev_name(device),
        'adaptive_budget': adaptive,
        'audio_s': round(audio_dur, 2),
        'chunk_ms': chunk_ms,
        'n_chunks': n_chunks,
        'compile_s': round(build_s, 2),
        'wall_s': round(wall, 3),
        'rtf': round(wall / audio_dur, 3),
        'rtf_steady': round(rtf_steady, 3),
        'per_chunk_ms_mean': round(sum(tot_ms) / len(tot_ms), 1),
        'per_chunk_ms_median': round(sorted(tot_ms)[len(tot_ms) // 2], 1),
        'per_chunk_ms_max': round(max(tot_ms), 1),
        'per_chunk_ms_first': round(tot_ms[0], 1),
        'per_chunk_ms_steady': round(sum(steady) / len(steady), 1),
        'flush_ms': round(flush_ms, 1),
        'throughput_chunks_per_s': round(n_chunks / wall, 2),
        'enc_ms_mean': round(sum(c['enc_ms'] for c in chunks) / len(chunks), 1),
        'prefill_ms_mean': round(
            sum(c['prefill_ms'] for c in chunks) / len(chunks), 1),
        'decode_ms_mean': round(
            sum(c['decode_ms'] for c in chunks) / len(chunks), 1),
        'text': final_text,
    }
    res.update(ps.peaks())
    return res


def _dev_name(device: str) -> str:
    try:
        import openvino as ov
        return ov.Core().get_property(device, 'FULL_DEVICE_NAME')
    except Exception:
        return device


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--wav', default=DEFAULT_WAV)
    ap.add_argument('--chunk-ms', type=float, default=320.0)
    ap.add_argument('--devices', default='GPU.0,CPU')
    ap.add_argument('--no-adaptive-budget', action='store_true')
    ap.add_argument('--out', default=OUT_DIR)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    audio, sr = sf.read(args.wav, dtype='float32')
    assert sr == 16000, f'expect 16k, got {sr}'
    if audio.ndim > 1:
        audio = audio[:, 0]
    print(f'[c053] audio {len(audio)/sr:.2f}s  chunk={args.chunk_ms}ms  '
          f'adaptive={not args.no_adaptive_budget}', flush=True)

    results, errors = [], []
    for dev in [d.strip() for d in args.devices.split(',') if d.strip()]:
        try:
            results.append(run_one(dev, audio, args.chunk_ms,
                                   not args.no_adaptive_budget, args.out))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f'[c053] {dev} 失败: {type(e).__name__}: {e}', flush=True)
            errors.append({'device': dev, 'error': f'{type(e).__name__}: {e}'})

    payload = {'cuda_ref': CUDA_REF, 'ov': results, 'errors': errors,
               'generated': time.strftime('%Y-%m-%d %H:%M:%S')}
    sp = os.path.join(args.out, 'summary.json')
    with open(sp, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'\n[c053] saved -> {sp}', flush=True)

    print('\n=== 汇总 ===')
    print(f"{'配置':<12}{'RTF':>7}{'墙钟s':>8}{'均值ms':>9}"
          f"{'稳态ms':>9}{'峰值WS(MB)':>11}{'文本'}")
    for r in results:
        print(f"{r['key']:<12}{r['rtf']:>7.3f}{r['wall_s']:>8.2f}"
              f"{r['per_chunk_ms_mean']:>9.1f}{r['per_chunk_ms_steady']:>9.1f}"
              f"{r['ws_mb_peak']:>11.0f}  {r['text'][:30]!r}")
    print(f"{'CUDA(引用)':<12}{CUDA_REF['rtf']:>7.3f}{CUDA_REF['wall_s']:>8.2f}"
          f"{CUDA_REF['per_chunk_ms_mean']:>9.1f}"
          f"{CUDA_REF['per_chunk_ms_steady']:>9.1f}"
          f"{CUDA_REF['ws_mb_peak']:>11}  {CUDA_REF['text'][:30]!r}")


if __name__ == '__main__':
    main()
