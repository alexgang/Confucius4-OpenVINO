r"""diag_guard_regress.py — C-105 相对阈值保护期的边界条件回归

覆盖 `_silence_tail()` 的关键分支：

  1. 段太短（<0.5s）→ 不切
  2. 段尾没有静音 → 不切
  3. 尾静音不足 1.2s → 不切
  4. 尾静音够 + probe 高于 -40dB（绝对判据）→ 切（**旧行为必须保持**）
  5. 尾静音够 + probe 低于 -40dB 但高于「段内语音电平 - 18dB」→ 切（**新行为**）
  6. 尾静音够 + probe 低于两者 → 不切（保护期仍有效）
  7. 段内是纯噪声（语音电平 < -45dB）→ 退回绝对判据
  8. `LIVECAP_GUARD_REL=0` → 行为与旧版完全一致（回退开关）

用法：python diag_guard_regress.py
"""

from __future__ import annotations

import os
import sys
import importlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

SR = 16000


def make_case(voice_db=-25.0, sil_db=-70.0, tail_sil=1.5, voice_s=3.0,
              noise_db=None, rng=None):
    """合成一段音频：voice_s 秒语音 + tail_sil 秒静音。

    voice_db : 语音电平（30ms 帧 RMS）
    sil_db   : 静音/底噪电平
    noise_db : 若给定，在语音段里也铺这个电平的底噪（模拟真实录音底噪）
    """
    rng = rng or np.random.default_rng(7)
    n_voice = int(voice_s * SR)
    n_sil = int(tail_sil * SR)
    amp = 10 ** (voice_db / 20.0)
    noise_amp = 10 ** ((noise_db if noise_db is not None else sil_db) / 20.0)
    # 语音：调幅正弦 + 轻微渐弱（模拟收尾能量下降）
    t = np.arange(n_voice) / SR
    fade = np.linspace(1.0, 0.55, n_voice)
    voice = amp * fade * np.sin(2 * np.pi * 220 * t)
    # 底噪
    base = noise_amp * rng.standard_normal(n_voice)
    voice = voice + base
    sil = noise_amp * rng.standard_normal(n_sil)
    return np.concatenate([voice, sil]).astype(np.float32)


def rms_db(x):
    if x.size == 0:
        return -120.0
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2) + 1e-12))
    return 20.0 * np.log10(r + 1e-7)


def main():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = (got == want)
        if not good:
            ok = False
        print(f'  [{"PASS" if good else "FAIL"}] {name}: got={got} want={want}')

    import live_caption_app as L

    print('=== 8. 回退开关：LIVECAP_GUARD_REL=0 时行为与旧版一致 ===')
    os.environ['LIVECAP_GUARD_REL'] = '0'
    importlib.reload(L)
    seg = L.Segmenter()
    check('rel=0 默认常量', L.GUARD_REL_ENABLED, False)

    print('\n=== 1~7：rel=1 时的各分支 ===')
    os.environ['LIVECAP_GUARD_REL'] = '1'
    importlib.reload(L)
    seg = L.Segmenter()
    check('rel=1 默认常量', L.GUARD_REL_ENABLED, True)
    check('默认 drop', L.GUARD_REL_DROP_DB, 18.0)
    check('默认 min_speech', L.GUARD_REL_MIN_SPEECH_DB, -40.0)

    rng = np.random.default_rng(11)

    # 1. 太短（**总段长** < 0.5s）
    a = make_case(voice_s=0.2, tail_sil=0.2, rng=rng)
    check('1 段太短(<0.5s) 不切', seg._silence_tail(a), False)

    # 2. 段尾没有静音（全程说话）
    a = make_case(voice_s=4.0, tail_sil=0.0, rng=rng)
    check('2 段尾无静音 不切', seg._silence_tail(a), False)

    # 3. 尾静音不足 1.2s
    a = make_case(voice_s=4.0, tail_sil=0.8, rng=rng)
    check('3 尾静音不足1.2s 不切', seg._silence_tail(a), False)

    # 4. 绝对判据放行（probe 明显高于 -40dB）
    a = make_case(voice_db=-20.0, sil_db=-70.0, tail_sil=1.5, rng=rng)
    check('4 绝对判据放行', seg._silence_tail(a), True)

    # 5. 新行为：probe 低于 -40dB，但高于「段内语音电平 - 18dB」
    #    构造：语音电平 -25dB，底噪 -55dB，尾音渐弱到 -50dB
    #    → probe ≈ -48dB（绝对不通过），相对阈值 = -25-18 = -43dB → 通过
    a = make_case(voice_db=-25.0, sil_db=-55.0, noise_db=-55.0,
                  tail_sil=1.5, rng=rng)
    segdb = L._frame_db_series(a[:int(len(a) - 1.5 * SR)])
    speech = float(np.percentile(segdb, 90))
    check('5 相对判据放行', seg._silence_tail(a), True)
    print(f'        （该用例段内语音电平 {speech:.1f}dB，'
          f'相对阈值 {speech - 18:.1f}dB）')

    # 6. 两者都不满足 → 不切（保护期仍拦住）
    #    构造：整段语音都很弱（-45dB 附近），probe 低于 -40dB，
    #    且段内语音电平（p90）也低 → 相对阈值不够低 → 拦住。
    #    注意：要压低的是**静音起点前 0.35s 那个窗口**，不是别处。
    a = make_case(voice_db=-45.0, sil_db=-58.0, noise_db=-58.0,
                  tail_sil=1.5, rng=rng)
    check('6 保护期拦截（相对也不通过）', seg._silence_tail(a), False)

    # 7. 纯噪声段（语音电平 < 门槛）→ 退回绝对判据
    a = make_case(voice_db=-60.0, sil_db=-70.0, tail_sil=1.5, rng=rng)
    segdb = L._frame_db_series(a[:int(len(a) - 1.5 * SR)])
    speech = float(np.percentile(segdb, 90))
    print(f'        （该用例段内语音电平 {speech:.1f}dB）')
    check('7 纯噪声段退回绝对判据(不切)', seg._silence_tail(a), False)

    # 7b. ★ C-106：低语音电平的「伪语音段」必须被语音准入门槛挡住
    #     真实缺陷：61 分钟演讲上 520.96s 处多切了一刀 1.92s 的纯静音段，
    #     该段段内语音电平 p90 = -40.4dB（就是噪声底），probe = -44.2dB。
    #     旧门槛 -45dB 会放行它 → 产生空段 + 后续切点整体漂移。
    #     这里构造 speech ≈ -41dB（< -40dB 门槛）→ 必须不切。
    a = make_case(voice_db=-41.0, sil_db=-52.0, noise_db=-52.0,
                  tail_sil=1.4, rng=rng)
    segdb = L._frame_db_series(a[:int(len(a) - 1.4 * SR)])
    speech = float(np.percentile(segdb, 90))
    check('7b 低语音电平段被准入门槛拦住', seg._silence_tail(a), False)
    print(f'        （该用例段内语音电平 {speech:.1f}dB，门槛 '
          f'{L.GUARD_REL_MIN_SPEECH_DB:.1f}dB）')

    print('\n=== 9. 「绝对 ∪ 相对」只放宽不收紧 ===')
    print('    对所有随机样本，rel=1 的放行集合必须包含 rel=0 的放行集合')
    os.environ['LIVECAP_GUARD_REL'] = '0'
    importlib.reload(L)
    seg0 = L.Segmenter()
    os.environ['LIVECAP_GUARD_REL'] = '1'
    importlib.reload(L)
    seg1 = L.Segmenter()

    rng2 = np.random.default_rng(2024)
    n_cases = 400
    lost = 0
    gained = 0
    for i in range(n_cases):
        # 覆盖「绝对判据刚好不通过」的区间：语音电平压到 -30~-48dB，
        # 底噪抬到 -38~-60dB（真实录音的典型组合）。
        vdb = float(rng2.uniform(-48, -26))
        sdb = float(rng2.uniform(-60, -38))
        tail = float(rng2.uniform(1.2, 2.5))
        vs = float(rng2.uniform(0.6, 6.0))
        a = make_case(voice_db=vdb, sil_db=sdb, noise_db=sdb,
                      tail_sil=tail, voice_s=vs, rng=rng2)
        r0 = seg0._silence_tail(a)
        r1 = seg1._silence_tail(a)
        if r0 and not r1:
            lost += 1
        elif r1 and not r0:
            gained += 1
    print(f'  合成随机样本 {n_cases} 个：rel=1 相对 rel=0 '
          f'新增放行 {gained}，丢失放行 {lost}')
    check('9 只放宽不收紧（丢失必须为 0）', lost, 0)

    # ── 9b：在**真实录音**上验证「只放宽不收紧」──
    # 合成信号难以复现「渐弱尾音 + 底噪」的真实组合，
    # 所以这里用真实演讲音频的完整切段模拟来验证。
    wav = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..', 'test_audio', '<redacted>.wav')
    if os.path.exists(wav):
        import soundfile as sf
        d, sr = sf.read(wav, dtype='float32')
        if d.ndim > 1:
            d = d[:, 0]
        d = d[:int(20 * 60 * sr)]        # 前 20 分钟，够覆盖数十个切点

        def sim(seg_obj):
            chunk_n = int(SR * 0.64)
            acc = np.zeros(0, dtype=np.float32)
            out = []
            i = 0
            while i < len(d):
                ch = d[i:i + chunk_n]
                i += chunk_n
                if ch.size == 0:
                    break
                acc = np.concatenate([acc, ch]) if acc.size else ch.copy()
                if seg_obj.due(acc):
                    out.append(acc.shape[0] / SR)
                    acc = np.zeros(0, dtype=np.float32)
            return out

        r0 = sim(seg0)
        r1 = sim(seg1)
        n0, n1 = len(r0), len(r1)
        # 逐段比：同一段起点下，rel=1 不得比 rel=0 更晚才切
        # （用段数与总切点位置做粗判据：rel=1 切段数应 ≥ rel=0）
        print(f'  真实录音 20 分钟：rel=0 切 {n0} 段，rel=1 切 {n1} 段')
        check('9b 真实录音上不减少切段数', n1 >= n0, True)
    else:
        print('  （跳过真实录音验证：找不到音频）')

    print()
    print('全部通过' if ok else '有失败项')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
