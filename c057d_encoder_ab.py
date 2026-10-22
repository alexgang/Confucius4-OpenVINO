"""c057d_encoder_ab.py — C-057d: encoder FP16 vs INT4 的性能/内存 A/B

decoder 固定 INT8，只换 encoder_dir，640 ms 块跑同一段音频。
交替 4 轮取中位数，消除时间漂移与 iGPU 共享抖动。

用法：.venv python c057d_encoder_ab.py
输出：reports/c057_encoder_ab.json
"""
import os
import sys
import time
import json
import threading
import statistics as st

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

import numpy as np
import soundfile as sf
import psutil

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import streaming_transcribe, finish_streaming_transcribe
from win_gpu_perf import GpuQuery

GPU_PATHS = [r'\GPU Engine(*)\Utilization Percentage',
             r'\GPU Adapter Memory(*)\Dedicated Usage',
             r'\GPU Adapter Memory(*)\Shared Usage']
IGPU_LUID = '0x00012EAE'

ENCS = [('ENC-FP16', 'models/ov-encoder-segment-reviewer'),
        ('ENC-INT4', 'models/ov-encoder-segment-reviewer-int4')]
DEC = 'models/ov-int8-past'
WAV = r'C:\Users\Trekker-PTL\confucius4-r2t2\test.wav'
CHUNK_MS = 640.0
REPS = 4


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._halt = threading.Event()
        self.rows = []
        try:
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
            time.sleep(0.25)

    def stop(self):
        self._halt.set()
        self.join(timeout=2)

    def steady(self):
        """稳态 = 后 60% 采样中位数（避开编译期峰值）。"""
        if not self.rows:
            return {}
        tail = self.rows[int(len(self.rows) * 0.4):]
        ws = st.median([r['ws'] for r in tail])
        us = st.median([r['uss'] for r in tail])
        gp = 0.0
        if self.q is not None:
            try:
                for p, v in self.q.sample().items():
                    if 'Dedicated Usage' in p or 'Shared Usage' in p:
                        # PDH 计数器是字节，统一归一化到 MiB（与 c054 同口径）
                        gp = max(gp, v / 1024 ** 2)
            except Exception:
                pass
        return {'ws': ws, 'uss': us, 'gpumem': gp}


class Timed:
    def __init__(self, backend):
        self.enc_t = 0.0
        self.pre_t = 0.0
        self.dec_t = 0.0
        self.n = 0
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
                dt = (time.perf_counter() - t0) * 1000
                if kind == 'enc':
                    outer.enc_t = dt
                else:
                    try:
                        ids = a[0].get('input_ids') if a else kw.get('inputs')
                    except Exception:
                        ids = None
                    if ids is not None and getattr(ids, 'ndim', 0) == 2 \
                            and ids.shape[1] > 4:
                        outer.pre_t = dt
                    else:
                        outer.dec_t += dt
                        outer.n += 1
                return r

            def __getattr__(self, name):
                return getattr(self.o, name)
        return P(obj)

    def reset(self):
        self.pre_t = self.dec_t = self.n = 0.0


def run_once(enc_dir, audio):
    backend = SegmentEncoderOVBackend(
        encoder_dir=enc_dir, decoder_dir=DEC, device='GPU.0',
        precision='f16', strict_intel=True)
    cs = int(round(CHUNK_MS * 16000 / 1000))
    ws0 = backend.init_streaming_state(context='', language=None,
                                       unfixed_chunk_num=0, unfixed_token_num=5,
                                       chunk_size_sec=CHUNK_MS / 1000.0)
    streaming_transcribe(backend, audio[:cs * 2], ws0,
                         max_new_tokens=32, adaptive_budget=True)
    finish_streaming_transcribe(backend, ws0, max_new_tokens=32)

    tb = Timed(backend)
    ps = Sampler()
    state = backend.init_streaming_state(context='', language=None,
                                         unfixed_chunk_num=0, unfixed_token_num=5,
                                         chunk_size_sec=CHUNK_MS / 1000.0)
    chunks = []
    ps.start()
    for s in range(0, len(audio), cs):
        tb.reset()
        t0 = time.perf_counter()
        streaming_transcribe(backend, audio[s:s + cs], state,
                             max_new_tokens=32, adaptive_budget=True)
        dt = (time.perf_counter() - t0) * 1000
        chunks.append({'total': dt, 'enc': tb.enc_t, 'pre': tb.pre_t,
                       'dec': tb.dec_t, 'n': tb.n})
    t0 = time.perf_counter()
    finish_streaming_transcribe(backend, state, max_new_tokens=32)
    flush = (time.perf_counter() - t0) * 1000
    ps.stop()
    texts = [c['total'] for c in chunks]
    return {'chunks': chunks, 'flush': flush, 'mem': ps.steady(),
            'n_blocks': len(chunks), 'text': _last_text(state)}


def _last_text(state):
    for attr in ('last_text', 'text', 'stable_text', 'fixed_text'):
        v = getattr(state, attr, None)
        if isinstance(v, str) and v:
            return v
    return ''


def main():
    audio, sr = sf.read(WAV, dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    dur = len(audio) / sr
    print(f'audio {dur:.2f}s  chunk={CHUNK_MS}ms  reps={REPS}  decoder=INT8 固定')

    runs = {t: [] for t, _ in ENCS}
    for rep in range(REPS):
        for tag, enc in ENCS:
            r = run_once(enc, audio)
            runs[tag].append(r)
            c = r['chunks']
            print(f'  rep{rep} {tag}: 每块均值 {st.mean([x["total"] for x in c]):7.1f} ms  '
                  f'enc {st.mean([x["enc"] for x in c]):5.1f}  '
                  f'pre {st.mean([x["pre"] for x in c]):6.1f}  '
                  f'dec {st.mean([x["dec"] for x in c]):6.1f}  '
                  f'flush {r["flush"]:6.1f}  '
                  f'WS {r["mem"].get("ws", 0):.0f}  USS {r["mem"].get("uss", 0):.0f}  '
                  f'iGPU {r["mem"].get("gpumem", 0):.0f} MB', flush=True)

    print('\n=== 中位数汇总 ===')
    print(f'{"配置":<10}{"total":>9}{"enc":>8}{"prefill":>9}{"decode":>9}'
          f'{"RTF":>7}{"flush":>9}{"WS":>8}{"USS":>8}{"iGPU":>8}')
    med = {}
    for tag, _ in ENCS:
        g = lambda k: st.median([st.mean([x[k] for x in r['chunks']])
                                 for r in runs[tag]])
        tot, enc = g('total'), g('enc')
        mem = runs[tag][-1]['mem']
        med[tag] = {
            'total': tot, 'enc': enc, 'pre': g('pre'), 'dec': g('dec'),
            'rtf': tot / CHUNK_MS,
            'flush': st.median([r['flush'] for r in runs[tag]]),
            'ws': st.median([r['mem'].get('ws', 0) for r in runs[tag]]),
            'uss': st.median([r['mem'].get('uss', 0) for r in runs[tag]]),
            'gpumem': st.median([r['mem'].get('gpumem', 0) for r in runs[tag]]),
        }
        m = med[tag]
        print(f'{tag:<10}{m["total"]:>9.1f}{m["enc"]:>8.1f}{m["pre"]:>9.1f}'
              f'{m["dec"]:>9.1f}{m["rtf"]:>7.3f}{m["flush"]:>9.1f}'
              f'{m["ws"]:>8.0f}{m["uss"]:>8.0f}{m["gpumem"]:>8.0f}')

    a, b = med['ENC-FP16'], med['ENC-INT4']
    delta = {'enc_pct': 100 * (b['enc'] / a['enc'] - 1),
             'total_pct': 100 * (b['total'] / a['total'] - 1),
             'flush_pct': 100 * (b['flush'] / a['flush'] - 1),
             'ws_pct': 100 * (b['ws'] / a['ws'] - 1),
             'uss_pct': 100 * (b['uss'] / a['uss'] - 1),
             'gpumem_pct': 100 * (b['gpumem'] / a['gpumem'] - 1)}
    print('\nINT4 enc 相对 FP16 enc：encoder {:+.1f}% | total {:+.1f}% | '
          'flush {:+.1f}% | WS {:+.1f}% | USS {:+.1f}% | iGPU {:+.1f}%'.format(
              delta['enc_pct'], delta['total_pct'], delta['flush_pct'],
              delta['ws_pct'], delta['uss_pct'], delta['gpumem_pct']))

    out = {'medians': med, 'delta': delta,
           'runs': [{'tag': t, 'flush': r['flush'], 'mem': r['mem'],
                     'per_block': [round(x['total'], 2) for x in r['chunks']],
                     'text': r.get('text', '')}
                    for t, _ in ENCS for r in runs[t]]}
    os.makedirs('reports', exist_ok=True)
    with open('reports/c057_encoder_ab.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('saved -> reports/c057_encoder_ab.json')


if __name__ == '__main__':
    main()
