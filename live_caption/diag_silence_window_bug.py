r"""diag_silence_window_bug.py — 复现「长时间静音后规则2 永久失效」

怀疑的缺陷链条：
  `_silence_tail()` 只在末尾 `win = cut + guard + 0.5 ≈ 2.05s` 的窗口里找静音。
  `find_trailing_silence()` 返回的「静音起点」在该静音长于窗口时会被
  **窗口左边界截住**，于是 sil_start = 窗口起点。
  保护期再取 sil_start 往前 0.35s 作为 probe —— 这段也已经是静音了，
  probe_dB ≈ -119 → `db > SILENCE_DB(-40)` 为 False → 判「不是说完」→ 不切。

  而窗口是跟着音频末尾滑动的，所以静音一旦超过 (窗口 + 保护期) ≈ 2.40s，
  probe 永远落在静音里 → **规则2 从此再也无法触发**，
  只能等规则1（段长满 12s）或 MAX_SEG（20s）来切。

本脚本用「增量喂入」逐步复现：说 5 秒，然后一直静音，看多久才切。
对照不同静音长度，观察是否出现「永远不切」的平台。

用法：
  python diag_silence_window_bug.py [--cut 1.2] [--speech 5] [--silence 25]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

SR = 16000
STEP = 1600          # 100 ms


def main():
    args = sys.argv[1:]
    cut = 1.2
    speech_s = 5.0
    silence_s = 25.0
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--speech' in args:
        speech_s = float(args[args.index('--speech') + 1])
    if '--silence' in args:
        silence_s = float(args[args.index('--silence') + 1])

    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import live_caption_app as L
    import importlib
    importlib.reload(L)

    seg = L.Segmenter()
    guard = L.SILENCE_TAIL_GUARD_SEC
    win = cut + guard + 0.5
    print(f'cut={cut}s  guard={guard}s  窗口={win:.2f}s  '
          f'（静音超过 {win+guard:.2f}s 后 probe 会落进静音）\n', flush=True)

    rng = np.random.default_rng(0)
    amp = 10 ** (-25 / 20)
    voice = rng.normal(0, 1, int(speech_s * SR)).astype(np.float32)
    voice *= amp / max(1e-9, float(np.sqrt(np.mean(voice ** 2))))

    acc = np.zeros((0,), dtype=np.float32)
    acc = np.concatenate([acc, voice])
    # 先喂完语音，确认还没到 12s、不该切
    print(f'语音 {speech_s:.1f}s 喂完：due={seg.due(acc)}  '
          f'(段长 {acc.shape[0]/SR:.1f}s < 12s，规则1 不满足)', flush=True)

    cut_at = None
    for k in range(1, int(silence_s / 0.1) + 1):
        sil = np.zeros(STEP, dtype=np.float32)
        acc = np.concatenate([acc, sil])
        dur = acc.shape[0] / SR
        tail = dur - speech_s
        ok = seg.due(acc)
        if ok and cut_at is None:
            cut_at = dur
            print(f'  ★ 切段于：语音结束后 {tail:5.2f}s（段长 {dur:5.2f}s）', flush=True)
            # 继续观察后续，看是不是靠 12s 才切
        if k % 10 == 0 and cut_at is None:
            print(f'    已等 {tail:5.2f}s  段长 {dur:5.2f}s  due=False', flush=True)

    if cut_at is None:
        print(f'\n★ 静音 {silence_s:.0f}s 内始终没切段', flush=True)
    else:
        tail = cut_at - speech_s
        if tail > win + guard + 0.3:
            print(f'\n★ 判定：切段发生在静音 {tail:.2f}s 之后，'
                  f'远晚于阈值 {cut}s。', flush=True)
            print(f'  说明规则2 在静音超过约 {win+guard:.2f}s 后已失效，', flush=True)
            print(f'  本次是靠「段长 ≥ 12s 的规则1」才切出来的。', flush=True)
        else:
            print(f'\n✓ 判定：切段在静音 {tail:.2f}s 处发生，符合阈值 + 余量预期。', flush=True)


if __name__ == '__main__':
    main()
