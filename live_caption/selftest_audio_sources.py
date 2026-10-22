r"""selftest_audio_sources.py — 三种音频源的独立烟测（不加载 ASR 引擎）

用法:
  python selftest_audio_sources.py            # 全部三种
  python selftest_audio_sources.py system     # 只测某一种

只验证「能不能稳定地产出 16 kHz 单声道 PCM」以及基本电平/时长，
不碰 OpenVINO / CUDA 引擎 —— 引擎自测走 live_caption_app.py --selftest。
"""
import os
import queue
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import audio_source
from audio_source import SR, make_source

APP_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_WAV = os.path.join(APP_DIR, 'test_en_60s.wav')


def _drain(q, want_s, timeout=30):
    """收 want_s 秒的 PCM，返回 (样本数, 峰值, RMS, 耗时)。"""
    got = 0
    peak = 0.0
    acc = 0.0
    t0 = time.perf_counter()
    while got < want_s * SR:
        try:
            item = q.get(timeout=timeout)
        except queue.Empty:
            break
        if item is None:
            break
        pcm, _t = item
        got += len(pcm)
        peak = max(peak, float(np.max(np.abs(pcm))) if pcm.size else 0.0)
        acc += float(np.sum(pcm.astype(np.float64) ** 2))
    rms = float(np.sqrt(acc / max(1, got)))
    return got, peak, rms, time.perf_counter() - t0


def test_mic(seconds=2.0):
    q = queue.Queue()
    src = make_source('mic', q)
    src.start()
    got, peak, rms, wall = _drain(q, seconds)
    src.stop()
    ok = got > 0
    print(f'[mic]   {"OK " if ok else "FAIL"} 样本 {got}（期望≈{int(seconds*SR)}）'
          f'  峰值 {peak:.4f}  RMS {rms:.5f}  耗时 {wall:.1f}s  设备={src.name_used!r}')
    return ok


def test_system(seconds=2.0):
    q = queue.Queue()
    src = make_source('system', q)
    src.start()
    got, peak, rms, wall = _drain(q, seconds)
    src.stop()
    # 系统此刻可能完全静音，峰值 0 也是正常的；只要有稳定的 PCM 流就算通过
    ok = got > 0 and not src.err
    print(f'[system] {"OK " if ok else "FAIL"} 样本 {got}（期望≈{int(seconds*SR)}）'
          f'  峰值 {peak:.4f}  RMS {rms:.5f}  耗时 {wall:.1f}s  设备={src.name_used!r}'
          f'{"" if not src.err else "  错误=" + repr(src.err)}')
    return ok


def test_file(seconds=2.0):
    if not os.path.isfile(TEST_WAV):
        print(f'[file]  SKIP 找不到测试文件 {TEST_WAV}')
        return True
    q = queue.Queue()
    src = make_source('file', q, file=TEST_WAV, speed=0.0)   # 全速
    src.start()
    got, peak, rms, wall = _drain(q, seconds)
    src.stop()
    ok = got > 0 and peak > 0.001
    print(f'[file]  {"OK " if ok else "FAIL"} 样本 {got}  峰值 {peak:.4f}'
          f'  RMS {rms:.5f}  耗时 {wall:.1f}s  解码={src.name_used!r}'
          f'{"" if not src.err else "  错误=" + repr(src.err)}')
    return ok


def test_file_pyav(seconds=2.0):
    """用 PyAV 路径解码同一个 wav（覆盖 soundfile 失败时的回退路径）。"""
    if not os.path.isfile(TEST_WAV):
        return True
    q = queue.Queue()
    src = make_source('file', q, file=TEST_WAV, speed=0.0)
    try:
        audio, sr, decoder = src.load()
        print(f'[decode] soundfile={decoder} sr={sr} 样本 {len(audio)}')
    except Exception as e:
        print(f'[decode] FAIL {e!r}')
        return False
    # 强制走 PyAV
    try:
        a2, sr2, dec2 = src._load_pyav()
        ok = len(a2) > 0
        print(f'[decode-pyav] {"OK " if ok else "FAIL"} sr={sr2} 样本 {len(a2)}')
    except Exception as e:
        print(f'[decode-pyav] FAIL {e!r}')
        return False
    return ok


TESTS = {'mic': test_mic, 'system': test_system, 'file': test_file}


def main():
    which = sys.argv[1:] or ['mic', 'system', 'file']
    results = []
    for name in which:
        if name not in TESTS:
            print(f'未知测试项：{name}')
            continue
        try:
            results.append((name, TESTS[name]()))
        except Exception as e:
            print(f'[{name}]   FAIL 异常 {type(e).__name__}: {e}')
            results.append((name, False))
    results.append(('decode-pyav', test_file_pyav()))
    print()
    bad = [n for n, ok in results if not ok]
    print('全部通过' if not bad else '失败项：' + ', '.join(bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
