"""c054_cuda_mem.py — C-054: CUDA Q8/Q4 流式内存占用实测（子进程 + PDH）

c052 报告里 CUDA 侧的内存数字（ws 2515 / private 4.8 GB / gpu 3355 MB）来自
原始 stream_report.html 的 Q8 口径；Q4_K 没有对应测量。本脚本补上：
对 Q8_0 / Q4_K 两个 gguf 各跑一次 test.wav 流式（chunk 320 ms，与 c052
cuda_ref 同口径），在子进程存活期间按 200 ms 采样：
    - 子进程 WorkingSet(RSS) / Private(USS)
    - 全部 4 个 GPU adapter 的 Dedicated / Shared Usage（按 LUID 区分）

用法：venv python c054_cuda_mem.py
输出：reports/c054_cuda_mem.json
"""
import os
import re
import sys
import json
import time
import threading
import subprocess

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf
import psutil

from win_gpu_perf import GpuQuery

CUDA_DIR = 'C:/Users/Trekker-PTL/confucius4-r2t2'
CUDA_EXE = f'{CUDA_DIR}/audio.cpp/audiocpp_cli.exe'
WAV = f'{CUDA_DIR}/test.wav'
MODELS = [('CUDA_Q8', f'{CUDA_DIR}/models/r2t2-q8_0.gguf'),
          ('CUDA_Q4', f'{CUDA_DIR}/models/r2t2-q4_k.gguf')]
CHUNK_MS = 320
INTERVAL = 0.2
OUT = 'reports/c054_cuda_mem.json'

GPU_PATHS = [r'\GPU Adapter Memory(*)\Dedicated Usage',
             r'\GPU Adapter Memory(*)\Shared Usage']


class MemSampler(threading.Thread):
    def __init__(self, pid):
        super().__init__(daemon=True)
        self.pid = pid
        self._halt = threading.Event()
        self.rows = []
        self.q = None
        try:
            self.q = GpuQuery(GPU_PATHS)
        except Exception as e:
            print(f'[mem] GPU 计数器不可用: {e}', flush=True)
            self.q = None

    def run(self):
        try:
            p = psutil.Process(self.pid)
        except Exception:
            return
        while not self._halt.is_set():
            row = {'t': time.time()}
            try:
                mi = p.memory_info()
                row['ws_mb'] = mi.rss / 1024 ** 2
                try:
                    row['uss_mb'] = p.memory_full_info().uss / 1024 ** 2
                except Exception:
                    row['uss_mb'] = row['ws_mb']
            except Exception:
                break
            if self.q is not None:
                try:
                    vals = self.q.sample()
                    for k, v in vals.items():
                        m = re.search(r'luid_0x[0-9A-Fa-f]+_(0x[0-9A-Fa-f]+)', k)
                        kind = 'ded' if 'dedicated' in k.lower() else 'shr'
                        if m:
                            row[f'{m.group(1)}_{kind}_mb'] = v / 1024 ** 2
                except Exception:
                    pass
            self.rows.append(row)
            self._halt.wait(INTERVAL)

    def stop(self):
        self._halt.set()
        self.join(timeout=3)
        if self.q is not None:
            self.q.close()


def run_one(model_path):
    audio, sr = sf.read(WAV, dtype='float32')
    assert sr == 16000
    if audio.ndim > 1:
        audio = audio[:, 0]
    pcm = (audio * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
    cmd = [
        CUDA_EXE,
        '--task', 'asr', '--family', 'confucius4_r2t2',
        '--model', model_path, '--backend', 'cuda',
        '--mode', 'streaming',
        '--audio', '-', '--input-format', 's16le', '--input-rate', '16000',
        '--input-channels', '1',
        '--session-option', f'chunk_size_ms={CHUNK_MS}',
        '--session-option', 'unfixed_chunk_num=0',
        '--session-option', 'unfixed_token_num=5',
        '--session-option', 'max_tokens=32',
        '--log-file', 'NUL',
    ]
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = MemSampler(proc.pid)
    s.start()
    try:
        proc.stdin.write(pcm)
        proc.stdin.close()
    except Exception:
        pass
    rc = proc.wait(timeout=300)
    wall = time.perf_counter() - t0
    time.sleep(0.3)
    s.stop()
    return rc, wall, s.rows


def main():
    out = {}
    for tag, mp in MODELS:
        rc, wall, rows = run_one(mp)
        if not rows:
            print(f'[{tag}] 无采样数据 rc={rc}', flush=True)
            continue
        keys = set()
        for r in rows:
            keys |= set(r.keys())
        keys -= {'t'}
        peaks = {k: max((r.get(k, 0.0) for r in rows), default=0.0)
                 for k in sorted(keys)}
        # 稳态 = 最后 40% 采样点的中位数（避开模型加载段）
        tail = rows[int(len(rows) * 0.6):]
        steady = {}
        for k in sorted(keys):
            vals = [r.get(k, 0.0) for r in tail if r.get(k, 0.0) > 0]
            steady[k] = float(np.median(vals)) if vals else 0.0
        out[tag] = {'model': mp, 'rc': rc, 'wall_s': round(wall, 2),
                    'n_samples': len(rows), 'peaks_mb': peaks,
                    'steady_mb': steady}
        print(f'[{tag}] rc={rc} wall={wall:.1f}s samples={len(rows)}', flush=True)
        print(f'   peaks: ' + '  '.join(
            f'{k}={v:.0f}' for k, v in peaks.items()), flush=True)
        print(f'   steady: ' + '  '.join(
            f'{k}={v:.0f}' for k, v in steady.items()), flush=True)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'saved -> {OUT}', flush=True)


if __name__ == '__main__':
    main()
