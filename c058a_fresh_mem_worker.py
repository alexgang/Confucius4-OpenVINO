"""c058a_fresh_mem_worker.py — C-058②: 单配置的 fresh-process 内存测量（子进程）

reviewer 指出 c054/c057d 的 A/B 在同一进程内反复加载模型，前一个的残留污染后一个，
配置内单调漂移（+20%）大于配置间差（−10.6%）。本脚本是**子进程 worker**：
一个进程只测一个配置，走完 加载 → warmup → 稳态采样 → 打印 JSON → 退出，
彻底避免跨配置污染。

不要直接跑本脚本，由 c058a_fresh_mem.py 以子进程方式调用。

用法：python c058a_fresh_mem_worker.py <encoder_dir> <decoder_dir> <tag>
"""
import os
import sys
import json
import time
import threading

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import psutil

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import streaming_transcribe, finish_streaming_transcribe

GPU_PATHS = [r'\GPU Engine(*)\Utilization Percentage',
             r'\GPU Adapter Memory(*)\Dedicated Usage',
             r'\GPU Adapter Memory(*)\Shared Usage']
IGPU_LUID = '0x00012EAE'
CHUNK_SEC = 0.64
CHUNK_SAMPLES = int(CHUNK_SEC * 16000)     # 10240
STEADY_S = 20.0


def feed(backend, state, seconds):
    """逐块喂静音音频。注意：累积音频不得超过 encoder 的 2400 帧上限
    （≈20 s，segment_encoder_backend 的 assert），所以每 6 s 重置一次状态。
    """
    n_chunk = int(seconds * 16000) // CHUNK_SAMPLES
    chunk = np.zeros(CHUNK_SAMPLES, dtype=np.float32)
    done = 0
    while done < n_chunk:
        batch = min(n_chunk - done, 6)     # 6 * 0.64s ≈ 3.8s，安全
        for _ in range(batch):
            streaming_transcribe(backend, chunk, state, max_new_tokens=32,
                                 adaptive_budget=True)
        done += batch
        finish_streaming_transcribe(backend, state, max_new_tokens=32)
        state = backend.init_streaming_state(
            context='', language=None, unfixed_chunk_num=0,
            unfixed_token_num=5, chunk_size_sec=CHUNK_SEC)
    return state


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._halt = threading.Event()
        self.rows = []
        try:
            from win_gpu_perf import GpuQuery
            self.q = GpuQuery(GPU_PATHS, luid_filter=IGPU_LUID)
        except Exception:
            self.q = None

    def run(self):
        proc = psutil.Process(os.getpid())
        while not self._halt.is_set():
            try:
                fi = proc.memory_full_info()
                self.rows.append({'ws': fi.rss / 1024 ** 2,
                                  'uss': fi.uss / 1024 ** 2})
            except Exception:
                pass
            if self.q is not None:
                try:
                    self.q.sample()
                except Exception:
                    pass
            time.sleep(0.2)

    def stop(self):
        self._halt.set()
        self.join(timeout=2)

    def igpu_mib(self):
        """iGPU 显存（主指标）：取采样期内 Dedicated+Shared 的最大值。"""
        if self.q is None:
            return None
        peak = 0.0
        try:
            for p, v in self.q.sample().items():
                if 'Dedicated Usage' in p or 'Shared Usage' in p:
                    peak = max(peak, v / 1024 ** 2)   # PDH 是字节
        except Exception:
            pass
        return peak


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    return xs[n // 2] if n else 0.0


def main():
    enc_dir, dec_dir, tag = sys.argv[1], sys.argv[2], sys.argv[3]

    # 1) 加载（编译）—— 这是显存/内存的主要来源
    t0 = time.perf_counter()
    backend = SegmentEncoderOVBackend(
        encoder_dir=enc_dir, decoder_dir=dec_dir,
        device='GPU.0', precision='f16', strict_intel=True)
    load_s = time.perf_counter() - t0

    # 2) warmup：跑几秒音频，让 KV cache / 临时缓冲稳定下来
    st = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_SEC)
    feed(backend, st, 4.0)

    # 3) 稳态采样：继续跑 20 s，只采后半段（剔除编译/预热瞬态）
    ps = Sampler()
    ps.start()
    st2 = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_SEC)
    t1 = time.perf_counter()
    feed(backend, st2, STEADY_S)
    ps.stop()

    tail = ps.rows[int(len(ps.rows) * 0.5):] or ps.rows
    result = {
        'tag': tag,
        'encoder_dir': enc_dir,
        'decoder_dir': dec_dir,
        'load_s': round(load_s, 1),
        'ws_steady_mib': round(median([r['ws'] for r in tail]), 1),
        'uss_steady_mib': round(median([r['uss'] for r in tail]), 1),
        'igpu_mib': round(ps.igpu_mib() or 0, 1),
        'n_samples': len(ps.rows),
        # IR 体积，用于与显存对账
        'enc_ir_mib': round(os.path.getsize(
            os.path.join(enc_dir, 'openvino_encoder_model.bin'))
            / 1024 ** 2, 1),
        'dec_ir_mib': round(os.path.getsize(
            os.path.join(dec_dir, 'openvino_decoder_model.bin'))
            / 1024 ** 2, 1),
    }
    result['ir_total_mib'] = round(result['enc_ir_mib'] + result['dec_ir_mib'], 1)
    print('###JSON###' + json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
