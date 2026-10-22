"""c054_ab.py — C-054: INT8 vs INT4 严格 A/B（多次重复 + 中位数）

c052/c053 单次测量的「INT4 prefill +51%」在逐调用打点中出现巨大抖动
（INT4 有 578 ms 离群值，INT8 也有 257 ms）。本脚本用多次重复 + 中位数
消除机器噪声，给出可下结论的数字。

每轮：640 ms 块跑同一段 6.74 s 音频，记录每块 enc/prefill/decode/total。
两个配置交替跑（INT8, INT4, INT8, INT4, ...）以抵消时间漂移。
"""
import os
import sys
import time
import threading
import statistics as st

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import streaming_transcribe, finish_streaming_transcribe

try:
    import psutil
except ImportError:
    psutil = None

from win_gpu_perf import GpuQuery

GPU_PATHS = [r'\GPU Engine(*)\Utilization Percentage',
             r'\GPU Adapter Memory(*)\Dedicated Usage',
             r'\GPU Adapter Memory(*)\Shared Usage']
IGPU_LUID = '0x00012EAE'   # GPU.0 (Intel Xe3 iGPU)

ENC = 'models/ov-encoder-segment-reviewer'
DECS = [('INT8', 'models/ov-int8-past'),
        ('INT4', 'models/ov-int4-lmfp16-past')]
WAV = r'C:\Users\Trekker-PTL\confucius4-r2t2\test.wav'
CHUNK_MS = 640.0
REPS = 5


class Sampler(threading.Thread):
    """250 ms 采样进程内存 + iGPU 计数器（与 c052 同口径）。"""

    def __init__(self):
        super().__init__(daemon=True)
        self._halt = threading.Event()
        self.rows = []
        self.q = None
        try:
            self.q = GpuQuery(GPU_PATHS, luid_filter=IGPU_LUID)
        except Exception:
            self.q = None

    def run(self):
        proc = psutil.Process(os.getpid()) if psutil else None
        while not self._halt.is_set():
            if proc is not None:
                try:
                    mi = proc.memory_info()
                    self.rows.append({'ws_mb': mi.rss / 1e6,
                                      'priv_mb': getattr(mi, 'private', 0) / 1e6})
                except Exception:
                    pass
            if self.q is not None:
                try:
                    self.q.sample()
                except Exception:
                    pass
            time.sleep(0.25)

    def stop(self):
        self._halt.set()
        self.join(timeout=2)

    def peaks(self):
        ws = max((r['ws_mb'] for r in self.rows), default=0)
        pv = max((r['priv_mb'] for r in self.rows), default=0)
        gm = gu = 0.0
        if self.q is not None:
            try:
                for p, v in self.q.sample().items():
                    if 'Utilization' in p:
                        gu = max(gu, v)
                    elif 'Shared Usage' in p or 'Dedicated Usage' in p:
                        gm = max(gm, v)
            except Exception:
                pass
        return {'ws_mb': ws, 'private_mb': pv,
                'gpu_mem_mb': gm, 'gpu_util_pct': gu}


class Timed:
    def __init__(self, backend):
        self.enc_t = 0.0
        self.pre_t = 0.0
        self.dec_t = 0.0
        self.n = 0
        self._backend = backend
        backend.enc_infer = self._wrap(backend.enc_infer, 'enc')
        backend.dec_infer = self._wrap(backend.dec_infer, 'dec')

    def _wrap(self, obj, kind):
        outer = self

        class P:
            def __init__(self, o):
                self.o = o

            def infer(self, *a, **kw):
                t0 = time.perf_counter()
                r = self.o.infer(*a, **kw)
                dt = time.perf_counter() - t0
                if kind == 'enc':
                    outer.enc_t = dt * 1000
                else:
                    # prefill：input_ids 长度 > 4；decode：1 token
                    try:
                        ids = a[0].get('input_ids') if a else kw.get('inputs')
                    except Exception:
                        ids = None
                    if ids is not None and getattr(ids, 'ndim', 0) == 2 \
                            and ids.shape[1] > 4:
                        outer.pre_t = dt * 1000
                    else:
                        outer.dec_t += dt * 1000
                        outer.n += 1
                return r

            def __getattr__(self, name):
                return getattr(self.o, name)

        return P(obj)

    def reset(self):
        self.pre_t = 0.0
        self.dec_t = 0.0
        self.n = 0


def run_once(dec_dir, audio):
    backend = SegmentEncoderOVBackend(
        encoder_dir=ENC, decoder_dir=dec_dir, device='GPU.0',
        precision='f16', strict_intel=True)
    chunk_samples = int(round(CHUNK_MS * 16000 / 1000))
    # 预热
    ws = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_MS / 1000.0)
    streaming_transcribe(backend, audio[:chunk_samples * 2], ws,
                         max_new_tokens=32, adaptive_budget=True)
    finish_streaming_transcribe(backend, ws, max_new_tokens=32)

    tb = Timed(backend)
    ps = Sampler()
    state = backend.init_streaming_state(
        context='', language=None, unfixed_chunk_num=0,
        unfixed_token_num=5, chunk_size_sec=CHUNK_MS / 1000.0)
    chunks = []
    ps.start()
    for s in range(0, len(audio), chunk_samples):
        tb.reset()
        t0 = time.perf_counter()
        streaming_transcribe(backend, audio[s:s + chunk_samples], state,
                             max_new_tokens=32, adaptive_budget=True)
        dt = (time.perf_counter() - t0) * 1000
        chunks.append({'total': dt, 'enc': tb.enc_t, 'pre': tb.pre_t,
                       'dec': tb.dec_t, 'n': tb.n})
    t0 = time.perf_counter()
    finish_streaming_transcribe(backend, state, max_new_tokens=32)
    flush = (time.perf_counter() - t0) * 1000
    ps.stop()
    return chunks, flush, ps.peaks()


def main():
    audio, sr = sf.read(WAV, dtype='float32')
    assert sr == 16000
    if audio.ndim > 1:
        audio = audio[:, 0]
    print(f'audio {len(audio)/sr:.2f}s  chunk={CHUNK_MS}ms  reps={REPS}')

    runs = {tag: [] for tag, _ in DECS}
    flushs = {tag: [] for tag, _ in DECS}
    mems = {tag: [] for tag, _ in DECS}
    for rep in range(REPS):
        for tag, dec in DECS:   # 交替跑
            chunks, flush, mem = run_once(dec, audio)
            runs[tag].append(chunks)
            flushs[tag].append(flush)
            mems[tag].append(mem)
            tot = st.mean([c['total'] for c in chunks])
            print(f'  rep{rep} {tag}: 每块均值 {tot:7.1f} ms  '
                  f'enc {st.mean([c["enc"] for c in chunks]):5.1f}  '
                  f'pre {st.mean([c["pre"] for c in chunks]):6.1f}  '
                  f'dec {st.mean([c["dec"] for c in chunks]):6.1f}  '
                  f'flush {flush:6.1f}  WS {mem["ws_mb"]:.0f}MB', flush=True)

    print('\n=== 汇总（每块中位数，跨 %d 次重复）===' % REPS)
    print(f'{"配置":<8}{"total":>9}{"enc":>8}{"prefill":>9}{"decode":>9}{"flush":>9}'
          f'{"WS峰值":>9}{"Priv峰值":>9}{"GPU Mem":>9}')
    med = {}
    for tag, _ in DECS:
        tot = [st.mean([c['total'] for c in ch]) for ch in runs[tag]]
        enc = [st.mean([c['enc'] for c in ch]) for ch in runs[tag]]
        pre = [st.mean([c['pre'] for c in ch]) for ch in runs[tag]]
        dec = [st.mean([c['dec'] for c in ch]) for ch in runs[tag]]
        med[tag] = dict(
            total=st.median(tot), enc=st.median(enc), pre=st.median(pre),
            dec=st.median(dec), flush=st.median(flushs[tag]),
            ws=st.median([m['ws_mb'] for m in mems[tag]]),
            priv=st.median([m['private_mb'] for m in mems[tag]]),
            gpumem=st.median([m['gpu_mem_mb'] for m in mems[tag]]))
        m = med[tag]
        print(f'{tag:<8}{m["total"]:>9.1f}{m["enc"]:>8.1f}{m["pre"]:>9.1f}'
              f'{m["dec"]:>9.1f}{m["flush"]:>9.1f}'
              f'{m["ws"]:>9.0f}{m["priv"]:>9.0f}{m["gpumem"]:>9.0f}')
    a, b = med['INT8'], med['INT4']
    print('\nINT4 相对 INT8：total {:+.1f}% | enc {:+.1f}% | prefill {:+.1f}% | '
          'decode {:+.1f}% | WS {:+.1f}%'.format(
              100 * (b['total'] / a['total'] - 1),
              100 * (b['enc'] / a['enc'] - 1),
              100 * (b['pre'] / a['pre'] - 1),
              100 * (b['dec'] / a['dec'] - 1),
              100 * (b['ws'] / a['ws'] - 1)))
    import json
    with open('reports/c054_ab_medians.json', 'w', encoding='utf-8') as f:
        json.dump(med, f, ensure_ascii=False, indent=2)
    print('saved -> reports/c054_ab_medians.json')


if __name__ == '__main__':
    main()
