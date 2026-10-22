r"""diag_gui_latency.py — 实测 GUI 上「白字定稿」与「黄字实时」各自的刷新节奏

用户反馈的是「GUI 上看到白色句子出现的时间比较慢」。本脚本验证：
  · 白色行（overlay 第一行 / 主窗口无 tag 的定稿行）的数据源 = final_text
    只在 _on_final（定稿事件）时追加 —— 所以白字出现时间 == 定稿时间
  · 黄色行（partial）= engine.cur_text，随 chunk 推进实时更新 —— 很快

做法：跑一段真实音频，记录每 100ms 采一次：
    cur_text（partial/黄字内容）与 final_text（白字内容）的变化时刻
输出两条曲线的时间点，直观对比「实时文本多久更新一次」与「定稿文本多久才出现」。

用法：
  python diag_gui_latency.py <wav> [--cut 1.2] [--max-seconds N] [--lang English]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600


def main():
    args = sys.argv[1:]
    wav = args[0]
    cut = 1.2
    max_seconds = 120.0
    lang = None
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--max-seconds' in args:
        max_seconds = float(args[args.index('--max-seconds') + 1])
    if '--lang' in args:
        lang = args[args.index('--lang') + 1]

    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import importlib
    import live_caption_app as L
    importlib.reload(L)

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(max_seconds * sr)]

    eng = L.make_engine('gpu_int8', on_log=lambda m: None, force_language=lang)

    # 模拟 GUI 的状态
    final_text = ''          # 白字内容（只在定稿时追加）
    partial = ''             # 黄字内容（随 chunk 更新）

    t0 = time.perf_counter()
    fed = 0
    audio_t = 0.0
    partial_updates = []    # (音频秒, 墙钟秒, 词数)
    final_marks = []        # (音频秒, 墙钟秒, 文本)
    last_partial = ''
    last_len = 0

    for i in range(0, len(d), STEP):
        chunk = d[i:i + STEP]
        r = eng.feed(chunk, time.perf_counter())
        fed += len(chunk)
        audio_t = fed / SR

        # —— GUI 轮询（80ms 一次）会看到的状态 ——
        cur = eng.cur_text
        if cur != last_partial:
            partial_updates.append((audio_t, time.perf_counter() - t0,
                                    len(cur.split())))
            last_partial = cur

        if r:
            final_text += r + '\n'
            final_marks.append((audio_t, time.perf_counter() - t0, r))
        if max_seconds and audio_t >= max_seconds:
            break

    wall = time.perf_counter() - t0
    eng.close()

    print(f'\n=== GUI 两条文本的刷新节奏（cut={cut}s，音频 {audio_t:.1f}s，墙钟 {wall:.1f}s）===\n')
    print(f'黄字（partial / 正在识别）更新 {len(partial_updates)} 次：', flush=True)
    if partial_updates:
        # 前 12 次，看它多快就变一次
        for a, w, n in partial_updates[:12]:
            print(f'   音频{a:6.2f}s  墙钟{w:6.2f}s  {n:3d} 词', flush=True)
        gaps = np.diff([u[1] for u in partial_updates])
        print(f'   → 更新间隔：均值 {gaps.mean():.2f}s / 中位 {np.median(gaps):.2f}s',
              flush=True)

    print(f'\n白字（final / 定稿）更新 {len(final_marks)} 次：', flush=True)
    for a, w, txt in final_marks:
        print(f'   音频{a:6.2f}s  墙钟{w:6.2f}s  {txt[:70]!r}', flush=True)

    if final_marks and partial_updates:
        # 从「最后一次有实质语音」到「白字出现」
        print(f'\n★ 白字（定稿）首条出现于墙钟 {final_marks[0][1]:.2f}s', flush=True)
        print(f'★ 黄字在墙钟 {partial_updates[0][1]:.2f}s 就已经有内容了'
              f'（{partial_updates[0][2]} 词）', flush=True)
        print(f'→ 白字比黄字晚 {final_marks[0][1]-partial_updates[0][1]:.2f}s 出现',
              flush=True)


if __name__ == '__main__':
    main()
