r"""diag_final_delay.py — 量化「说话结束后定稿要等多久」

模拟：喂一段语音，然后喂静音，观察 feed() 多久之后返回定稿（final）。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

import live_caption_app as L

SR = 16000


def run(engine_key='gpu_int8', speech_s=5.0, silence_s=15.0, wav=None):
    wav = wav or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_en_60s.wav')
    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(speech_s * sr)]

    eng = L.make_engine(engine_key, on_log=lambda m: print('LOG:', m, flush=True))
    print(f'引擎已加载 {eng.load_s:.1f}s', flush=True)

    step = 1600          # 100 ms
    speech = d
    sil = np.zeros(int(silence_s * sr), dtype=np.float32)

    t0 = time.perf_counter()
    fed = 0
    final_at = None
    speech_done_at = None

    # 先喂语音
    for i in range(0, len(speech), step):
        eng.feed(speech[i:i + step], time.perf_counter())
        fed += len(speech[i:i + step])
    speech_done_at = time.perf_counter()
    print(f'语音喂完  t={speech_done_at - t0:.1f}s  cur_text={eng.cur_text[:60]!r}', flush=True)

    # 再喂静音
    for i in range(0, len(sil), step):
        r = eng.feed(sil[i:i + step], time.perf_counter())
        if r:
            final_at = time.perf_counter()
            print(f'★ 定稿返回  t={final_at - t0:.1f}s  '
                  f'（说话结束后 {final_at - speech_done_at:.1f}s）', flush=True)
            print(f'  final={r!r}', flush=True)
            break
        if (i // step) % 10 == 0:
            print(f'  静音 {i/sr:5.1f}s  已等 {time.perf_counter()-speech_done_at:5.1f}s  '
                  f'cur_text={eng.cur_text[:50]!r}', flush=True)

    if final_at is None:
        print(f'!! {silence_s}s 静音内没有定稿', flush=True)
        return
    print(f'\n结论：说话结束 → 定稿耗时 {final_at - speech_done_at:.1f}s', flush=True)


if __name__ == '__main__':
    eng = sys.argv[1] if len(sys.argv) > 1 else 'gpu_int8'
    sp = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    sil = float(sys.argv[3]) if len(sys.argv) > 3 else 15.0
    run(eng, sp, sil)
