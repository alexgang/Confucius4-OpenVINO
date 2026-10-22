r"""diag_early_cut.py — 验证「静音超时提前切段」会不会损失识别质量。

做法：喂一段语音，然后在第 N 秒静音处**手动**切段，看 final 文本质量。
对比「等满 12 秒自然切段」的结果。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

import live_caption_app as L

SR = 16000
STEP = 1600          # 100 ms


def feed_until_silence(eng, speech, silence_s, cut_at_s=None):
    """喂语音 + 静音。cut_at_s 给定时，在静音累计到该秒数处强制切段。"""
    step = STEP
    for i in range(0, len(speech), step):
        eng.feed(speech[i:i + step], time.perf_counter())
    speech_done = time.perf_counter()

    sil = np.zeros(int(silence_s * SR), dtype=np.float32)
    forced = None
    for i in range(0, len(sil), step):
        r = eng.feed(sil[i:i + step], time.perf_counter())
        if r:
            return r, time.perf_counter() - speech_done, 'natural', speech_done
        if cut_at_s is not None and forced is None and \
                (time.perf_counter() - speech_done) >= cut_at_s:
            # 模拟「静音超时强制切段」
            forced = eng._close_segment()
            return forced, time.perf_counter() - speech_done, 'forced', speech_done
    return None, silence_s, 'timeout', speech_done


def main():
    engine_key = sys.argv[1] if len(sys.argv) > 1 else 'gpu_int8'
    speech_s = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    wav = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_en_60s.wav')
    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    speech = d[:int(speech_s * sr)]

    print(f'=== 语音 {speech_s}s，参考全量文本 ===', flush=True)
    for cut in [None, 1.0, 1.5, 2.0, 3.0]:
        eng = L.make_engine(engine_key, on_log=lambda m: None)
        # 先喂一段静音让引擎进入稳态（模拟真实使用：先有环境音）
        r, delay, how, _ = feed_until_silence(
            eng, speech, silence_s=20.0, cut_at_s=cut)
        if r is None:
            print(f'  cut={cut if cut else "自然"}  → 超时未定稿', flush=True)
            eng.close()
            continue
        print(f'  cut={str(cut) + "s" if cut else "自然(等满12s)":16s} '
              f'延迟 {delay:5.1f}s  [{how:7s}]  {r!r}', flush=True)
        eng.close()


if __name__ == '__main__':
    main()
