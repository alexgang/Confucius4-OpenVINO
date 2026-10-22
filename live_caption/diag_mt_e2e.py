r"""diag_mt_e2e.py — 量化「说话结束 → 译文出现」的全链路延迟

分解三段：
  T1 定稿延迟   说话结束 → ASR 给出 final
  T2 翻译延迟   final 提交 → 译文出结果
  T3 挂起延迟   final 里最后一句若是半句，要等下一段才翻（C-099①）

用法：
  python diag_mt_e2e.py [engine] [speech_s] [silence_s] [--draft on|off]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

import live_caption_app as L
from translator import TranslationService

SR = 16000
STEP = 1600          # 100 ms


def main():
    engine_key = sys.argv[1] if len(sys.argv) > 1 else 'gpu_int8'
    speech_s = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    silence_s = float(sys.argv[3]) if len(sys.argv) > 3 else 20.0

    wav = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_en_60s.wav')
    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    speech = d[:int(speech_s * sr)]

    eng = L.make_engine(engine_key, on_log=lambda m: print('LOG:', m, flush=True))
    print(f'引擎已加载 {eng.load_s:.1f}s', flush=True)

    mt = TranslationService(target='zh', device='GPU.0', engine_key='gpu_int4cw',
                            on_log=lambda m: print('MT:', m, flush=True))
    print(f'翻译模型已加载 {mt.load_s:.1f}s state={mt.state}', flush=True)

    t0 = time.perf_counter()
    # ── 喂语音 ──
    for i in range(0, len(speech), STEP):
        eng.feed(speech[i:i + STEP], time.perf_counter())
    speech_done = time.perf_counter()
    print(f'语音喂完 t={speech_done - t0:.1f}s cur={eng.cur_text[:60]!r}', flush=True)

    # ── 喂静音，等定稿 ──
    sil = np.zeros(int(silence_s * SR), dtype='float32')
    final_at = None
    final_text = None
    for i in range(0, len(sil), STEP):
        r = eng.feed(sil[i:i + STEP], time.perf_counter())
        if r:
            final_at = time.perf_counter()
            final_text = r
            break
    if final_at is None:
        print('!! 静音内没有定稿')
        return
    t1 = final_at - speech_done
    print(f'\n★ T1 定稿延迟 = {t1:.2f}s   final={final_text!r}', flush=True)

    # ── 提交翻译 ──
    mt.submit(final_text, seg=0)
    print(f'  已提交翻译，carry 挂起={mt._carry!r}', flush=True)
    print(f'  分句={__import__("translator").split_sentences(final_text)}', flush=True)

    # ── 等译文 ──
    got_at = None
    deadline = time.perf_counter() + 60
    while time.perf_counter() < deadline:
        for kind, key, txt in mt.pop_outbox():
            if kind == 'final' and txt.strip():
                got_at = time.perf_counter()
                print(f'★ T2 翻译延迟 = {got_at - final_at:.2f}s   译文={txt!r}', flush=True)
        if got_at:
            break
        time.sleep(0.02)
    if got_at is None:
        print('!! 60s 内没有译文')

    # ── 下一段：挂起的半句何时才翻出来 ──
    if mt._carry:
        print(f'\n★ 段尾半句被挂起：{mt._carry!r}', flush=True)
        print('  → 它的译文要等【下一段定稿】才出现', flush=True)
        t_next = time.perf_counter()
        for i in range(0, len(sil), STEP):
            r = eng.feed(sil[i:i + STEP], time.perf_counter())
            if r:
                break
        if r:
            mt.submit(r, seg=1)
            deadline = time.perf_counter() + 60
            while time.perf_counter() < deadline:
                for kind, key, txt in mt.pop_outbox():
                    if kind == 'final' and txt.strip():
                        t3 = time.perf_counter() - t_next
                        print(f'★ T3 挂起半句的译文延迟 = {t3:.2f}s（从下一段定稿算起）', flush=True)
                        print(f'  译文={txt!r}', flush=True)
                        break
                else:
                    time.sleep(0.02)
                    continue
                break

    sm = mt.summary()
    print(f'\n翻译统计: n={sm["n"]} lat_med={sm["lat_med"]:.0f}ms '
          f'P95={sm["lat_p95"]:.0f}ms TTFT={sm["ttft_med"]:.0f}ms '
          f'{sm["tok_s"]:.1f} tok/s', flush=True)
    mt.close()
    eng.close()


if __name__ == '__main__':
    main()
