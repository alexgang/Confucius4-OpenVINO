r"""diag_cut_quality.py — 「缩短定稿时间是否损准确率」的大样本对照

做法：同一段真实音频，用不同 SILENCE_CUT_SEC 跑完整端到端，比对：
  · 定稿文本的段数与内容（是否逐字一致）
  · 拼接后的全文（去掉切段接缝重复）
  · 定稿总延迟（说话结束 → 最后一段定稿）
  · WER 相对参考 baseline 的变化（若有 baseline）

用法：
  python diag_cut_quality.py <wav> [--ref baseline.txt] [--cuts 0.6,0.8,1.2] [--max-seconds N]

注意：音频最好长于 MIN_SEG_SEC（12 s）；太短的片段在所有阈值下都只出
一段，对照就没有意义。脚本用 importlib.reload 重载 live_caption_app，
改 SILENCE_CUT_SEC 后重新取模块级常量才生效。
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


def run_cut(cut_sec, audio, engine_key='gpu_int8', max_seconds=0.0):
    """用指定静音阈值跑一遍，返回 (全文, 段数, 定稿时间戳列表, 墙钟)。"""
    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut_sec)
    # Segmenter 读的是模块级常量，改 env 后必须重新 import 才生效
    import importlib
    importlib.reload(L)

    eng = L.make_engine(engine_key, on_log=lambda m: None)
    finals, t_stamps = [], []
    t0 = time.perf_counter()
    fed = 0
    for i in range(0, len(audio), STEP):
        r = eng.feed(audio[i:i + STEP], time.perf_counter())
        fed += len(audio[i:i + STEP])
        if r:
            finals.append(r)
            t_stamps.append(time.perf_counter() - t0)
        if max_seconds and fed / SR >= max_seconds:
            break
    tail = eng.flush()
    if tail:
        finals.append(tail)
        t_stamps.append(time.perf_counter() - t0)
    wall = time.perf_counter() - t0
    eng.close()
    return finals, t_stamps, wall


def norm_words(text):
    """归一化：只留字母数字小写，避免标点差异干扰比对。"""
    import re
    return re.sub(r'[^a-z0-9 ]', '', text.lower()).split()


def main():
    args = sys.argv[1:]
    wav = args[0]
    cuts = [0.6, 0.8, 1.2]
    max_seconds = 0.0
    if '--cuts' in args:
        cuts = [float(x) for x in args[args.index('--cuts') + 1].split(',')]
    if '--max-seconds' in args:
        max_seconds = float(args[args.index('--max-seconds') + 1])

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    if max_seconds:
        d = d[:int(max_seconds * sr)]
    print(f'音频 {os.path.basename(wav)}  {len(d)/sr:.1f}s', flush=True)

    results = {}
    for cut in cuts:
        finals, stamps, wall = run_cut(cut, d, max_seconds=max_seconds)
        full = ' '.join(finals)
        results[cut] = dict(finals=finals, stamps=stamps, wall=wall, full=full)
        print(f'\n=== SILENCE_CUT_SEC={cut} ===', flush=True)
        print(f'  段数={len(finals)}  墙钟={wall:.1f}s  '
              f'最后定稿 @{stamps[-1] if stamps else 0:.1f}s', flush=True)
        for i, (f, t) in enumerate(zip(finals, stamps)):
            print(f'   [{i}] @{t:5.1f}s  {f[:90]!r}', flush=True)

    # ── 比对 ──
    print('\n=== 两两比对（全文逐字一致性）===')
    base = cuts[-1]
    for cut in cuts[:-1]:
        a = results[cut]['full']
        b = results[base]['full']
        wa, wb = norm_words(a), norm_words(b)
        same_text = a.strip() == b.strip()
        same_words = wa == wb
        # 差异明细
        import difflib
        diff = [d for d in difflib.unified_diff(wa, wb, lineterm='', n=0)
                if d.startswith(('+', '-')) and not d.startswith(('+++', '---'))]
        print(f'  cut={cut} vs cut={base}: 逐字相同={same_text}  词序列相同={same_words}  '
              f'差异行数={len(diff)}', flush=True)
        if diff and not same_words:
            for d in diff[:20]:
                print(f'     {d[:100]}', flush=True)
        print(f'     定稿时刻: cut={cut} 末段@{results[cut]["stamps"][-1]:.1f}s  '
              f'cut={base} 末段@{results[base]["stamps"][-1]:.1f}s  '
              f'提前 {results[base]["stamps"][-1]-results[cut]["stamps"][-1]:.1f}s', flush=True)

    # ── 与参考 baseline 比 WER ──
    if '--ref' in args:
        ref_path = args[args.index('--ref') + 1]
        ref = open(ref_path, encoding='utf-8').read()
        rw = norm_words(ref)
        print(f'\n=== 相对参考 baseline 的 WER（参考 {os.path.basename(ref_path)}）===')
        import difflib
        for cut in cuts:
            ww = norm_words(results[cut]['full'])
            sm = difflib.SequenceMatcher(None, rw, ww)
            # 编辑距离（Levenshtein）用 difflib 的 opcodes 近似
            dist = sum(max(i2 - i1, j2 - j1)
                        for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal')
            print(f'  cut={cut}: 词数={len(ww)} (参考 {len(rw)})  编辑距离={dist}  '
                  f'WER={dist/max(1,len(rw)):.4f}', flush=True)


if __name__ == '__main__':
    main()
