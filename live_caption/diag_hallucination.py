r"""diag_hallucination.py — 定位「切段阈值 → ASR 重复退化幻觉」的因果

现象（180s 会议音频，锁 English）：
    cut=1.0 的第 10 段出现 "youonoronoronoronor…" 重复退化，
    而 cut=0.8 / 1.2 的同一位置都正常。
    → 不是「阈值越低越差」，而是**非单调**，某个切点触发了退化。

要验证的两件事：
  A. 退化发生在哪条路径上 —— 流式主循环 streaming_transcribe，
     还是切段时的收尾解码 _finalize()？
     线索：live_caption_app.feed() 显式传 enable_hallucination_reset=False，
     所以流式主循环**没有** loop 保护；_finalize() 走的 generate_with_prefix
     也完全不经过 loop 检测 → 两条路都没有保护。
  B. 打开 loop 保护能不能消掉它。

做法：同一段音频，cut=1.0，跑 N 遍（不同随机性/不同 chunk 边界），
统计退化是否稳定复现；再打开幻觉重置跑同样次数对比。

用法：
  python diag_hallucination.py <wav> [--cut 1.0] [--repeats 2] [--guard]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600


def loop_stats(text):
    """统计文本里的重复退化：3-gram 连续 ≥3 次，或长 phrase 重复。"""
    import re
    words = re.findall(r'\S+', text.lower())
    # 单词级重复
    for i in range(len(words) - 2):
        tri = tuple(words[i:i + 3])
        cnt = 0
        for j in range(i, len(words) - 2, 3):
            if tuple(words[j:j + 3]) == tri:
                cnt += 1
            else:
                break
        if cnt >= 2:
            return f'3gram@{i}({tri})x{cnt+1}'
    # 字符级重复（"ononon"）
    for m in re.finditer(r'(.{2,12}?)\1{2,}', text.lower()):
        return f'charrep({m.group(1)})x{len(m.group(0))//max(1,len(m.group(1)))}'
    return None


def run(cut, audio, guard=False, max_seconds=180.0, force_language=None):
    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut)
    import importlib
    import live_caption_app as L
    importlib.reload(L)

    if guard:
        # 打开幻觉重置：把 feed() 里的 enable_hallucination_reset=False 改掉
        src = open(L.__file__, encoding='utf-8').read()
        patched = src.replace('enable_hallucination_reset=False',
                               'enable_hallucination_reset=True')
        if patched == src:
            print('  ⚠️ 没找到 enable_hallucination_reset=False，未改动')
        else:
            tmp = os.path.join(os.path.dirname(L.__file__), '_hc_patch.py')
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(patched)
            import importlib.util
            spec = importlib.util.spec_from_file_location('hc_patch', tmp)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            L = mod

    # 语种必须在建 state 时注入（与 diag_cut_quality.py 完全一致的口径）——
    # 用 set_force_language() 事后改会重建 state，行为与建 state 时注入不同，
    # 两次实验就不可比了。
    eng = L.make_engine('gpu_int8', on_log=lambda m: None,
                        force_language=force_language)
    finals = []
    t0 = time.perf_counter()
    fed = 0
    for i in range(0, len(audio), STEP):
        r = eng.feed(audio[i:i + STEP], time.perf_counter())
        fed += len(audio[i:i + STEP])
        if r:
            finals.append(r)
        if max_seconds and fed / SR >= max_seconds:
            break
    tail = eng.flush()
    if tail:
        finals.append(tail)
    wall = time.perf_counter() - t0
    eng.close()
    return finals, wall


def main():
    args = sys.argv[1:]
    wav = args[0]
    cut = 1.0
    repeats = 2
    max_seconds = 180.0
    guard = '--guard' in args
    force_language = None
    if '--cut' in args:
        cut = float(args[args.index('--cut') + 1])
    if '--repeats' in args:
        repeats = int(args[args.index('--repeats') + 1])
    if '--max-seconds' in args:
        max_seconds = float(args[args.index('--max-seconds') + 1])
    if '--lang' in args:
        force_language = args[args.index('--lang') + 1]

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(max_seconds * sr)]
    print(f'音频 {os.path.basename(wav)} {len(d)/SR:.1f}s  cut={cut}  '
          f'lang={force_language or "自动"}  guard={guard}  repeats={repeats}\n',
          flush=True)

    for rep in range(repeats):
        finals, wall = run(cut, d, guard=guard, max_seconds=max_seconds,
                           force_language=force_language)
        bad = []
        for i, f in enumerate(finals):
            st = loop_stats(f)
            if st:
                bad.append((i, st, f[:110]))
        print(f'--- 第 {rep+1} 次：{len(finals)} 段，墙钟 {wall:.1f}s，'
              f'退化段 {len(bad)} 个', flush=True)
        for i, st, snip in bad:
            print(f'    段[{i}] {st}', flush=True)
            print(f'       {snip!r}', flush=True)
        if not bad:
            print('    ✓ 无重复退化', flush=True)


if __name__ == '__main__':
    main()
