r"""diag_guard_boundary.py — 验证保护期 `SILENCE_TAIL_GUARD_SEC` 在边界上会不会拦住切段

30 分钟实测里最慢的那段（2.56s）：
    段长 9.0s，尾静音 2.11s，保护期 probe = **-40dB**
而 `_silence_tail()` 的判定是 `db > SILENCE_DB`（SILENCE_DB = -40.0），
**-40 > -40 为 False** → 保护期判定失败 → 不切段 → 一直等到别的条件触发。

本脚本用合成音频把这个边界行为钉死：
  构造「低声语音 + 长静音」，让 probe 的 dB 落在 -40 附近，
  看 `Segmenter._silence_tail()` 返回 True/False，以及最终要等多久才切。

这能回答：最慢的那 2.56s，是不是**保护期卡在 dB 边界**造成的。

用法：
  python diag_guard_boundary.py [--cut 1.2]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

SR = 16000


def make_case(voice_db, silence_s=1.6, voice_s=2.0, seed=0):
    """构造：voice_s 秒的宽带噪声（能量=voice_db）+ silence_s 秒静音。

    静音长度必须**略大于 cut、明显小于窗口**（窗口 = cut+guard+0.5 ≈ 2.05s）。
    如果静音比窗口还长，`find_trailing_silence` 的起点会被窗口左边界截住，
    probe 取到的是静音本身（-119dB），测不出保护期的真实行为 ——
    这正是第一版脚本的错。
    """
    rng = np.random.default_rng(seed)
    amp = 10 ** (voice_db / 20.0)
    voice = rng.normal(0, 1, int(voice_s * SR)).astype(np.float32)
    voice *= amp / max(1e-9, float(np.sqrt(np.mean(voice ** 2))))
    sil = np.zeros(int(silence_s * SR), dtype=np.float32)
    return np.concatenate([voice, sil])


def main():
    args = sys.argv[1:]
    cut = 1.2
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)

    import live_caption_app as L
    import importlib
    importlib.reload(L)
    seg = L.Segmenter()
    guard = L.SILENCE_TAIL_GUARD_SEC
    sdb = L.SILENCE_DB
    print(f'cut={cut}s  guard={guard}s  SILENCE_DB={sdb}\n')
    print('语音能量(dB)   保护期probe(dB)   _silence_tail()   该切吗')
    print('-' * 62)

    for voice_db in [-25, -30, -35, -38, -39, -39.5, -40, -40.5, -45, -50]:
        audio = make_case(voice_db)
        ok = seg._silence_tail(audio)
        # 独立算 probe dB 供对照
        from seg_stream import find_trailing_silence
        win = int(SR * (cut + guard + 0.5))
        start = max(0, audio.shape[0] - win)
        span = find_trailing_silence(audio, start_sample=start,
                                     end_sample=audio.shape[0],
                                     silence_db=sdb,
                                     min_silence_ms=int(cut * 1000))
        probe_db = None
        if span:
            ps = max(0, span[0] - int(SR * guard))
            p = audio[ps:span[0]]
            if p.size:
                rms = float(np.sqrt(np.mean(p.astype(np.float64) ** 2) + 1e-12))
                probe_db = 20.0 * np.log10(rms + 1e-7)
        pd = '—' if probe_db is None else f'{probe_db:.2f}'
        print(f'  {voice_db:6.1f}      {pd:>12}        {str(ok):5}       '
              f'{"切" if ok else "★不切"}')

    print('\n判据：_silence_tail 要求 probe_db > SILENCE_DB(-40.0)，')
    print('      所以 probe 落在 -40.0 及以下时**一律判失败、不切段**。')
    print('      实测最慢段 probe=-40dB 正好踩在边界上。')


if __name__ == '__main__':
    main()
