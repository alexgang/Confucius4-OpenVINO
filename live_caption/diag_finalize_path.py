r"""diag_finalize_path.py — 检查「切段收尾解码」这条路径的幻觉风险

背景：
  · C-036（用户决策）：hallucination reset 治标不治本，交付配置必须
    `enable_hallucination_reset=False`（流式主循环无 loop 保护）。
  · 但 10-21 引入的「静音超时切段」规则会让 `_finalize()` 走
    `generate_with_prefix(st, audio_accum, prefix, 64)` 收尾解码 ——
    **这条路径完全不经过 streaming_asr 的 loop 检测**，
    且历史上从未被评审覆盖。

本脚本专门量化这条路径的风险：
  对同一段音频，比较两种取文本的方式：
    A. 自然流式（cur_text，随 chunk 推进）
    B. 收尾解码（_finalize，触发切段时才跑）
  看 B 相比 A 是否有内容丢失 / 重复退化。

做法：跑一遍音频，在**每个切段点**记录 _finalize 的输出；同时记录
      切段前最后一刻的 cur_text（=流式已识别的内容）。
      两者应基本一致（finalize 只是把尾部补完）。

用法：
  python diag_finalize_path.py <wav> [--cut 1.2] [--max-seconds N] [--lang English]
"""
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600


def loop_kind(text):
    """检测重复退化。返回 (类型, 描述) 或 None。"""
    words = re.findall(r'\S+', text.lower())
    for i in range(len(words) - 2):
        tri = tuple(words[i:i + 3])
        cnt = 0
        for j in range(i, len(words) - 2, 3):
            if tuple(words[j:j + 3]) == tri:
                cnt += 1
            else:
                break
        if cnt >= 2:
            return ('3gram', f'{tri} 重复 {cnt+1} 次')
    for m in re.finditer(r'(.{2,12}?)\1{2,}', text.lower()):
        g = m.group(1)
        return ('charrep', f'"{g}" 重复 {len(m.group(0))//max(1,len(g))} 次')
    return None


def norm_words(text):
    return re.findall(r'[a-z0-9]+|[一-鿿]', text.lower())


def main():
    args = sys.argv[1:]
    wav = args[0]
    cut = 1.2
    max_seconds = 180.0
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
    print(f'音频 {os.path.basename(wav)} {len(d)/SR:.1f}s  cut={cut}  lang={lang or "自动"}\n',
          flush=True)

    eng = L.make_engine('gpu_int8', on_log=lambda m: None, force_language=lang)

    # 记录每次切段时的「流式已识别内容」与「收尾解码内容」
    records = []
    orig_close = eng._close_segment
    orig_finalize = eng._finalize

    def traced_finalize():
        pre_stream = eng.cur_text          # 收尾解码前的流式文本
        out = orig_finalize()
        records.append((pre_stream, out))
        return out

    eng._finalize = traced_finalize

    t0 = time.perf_counter()
    fed = 0
    n_seg = 0
    for i in range(0, len(d), STEP):
        eng.feed(d[i:i + STEP], time.perf_counter())
        fed += len(d[i:i + STEP])
        if max_seconds and fed / SR >= max_seconds:
            break
    eng.flush()
    wall = time.perf_counter() - t0
    eng.close()

    print(f'切段 {len(records)} 次，墙钟 {wall:.1f}s\n', flush=True)
    bad = 0
    for i, (pre, fin) in enumerate(records):
        k = loop_kind(fin)
        # finalize 文本应当「包含」流式文本的全部内容
        wf, wp = norm_words(fin), norm_words(pre)
        missing = [w for w in set(wp) if w not in set(wf)]
        flag = ''
        if k:
            flag = f'  ★ 退化({k[0]}): {k[1]}'
            bad += 1
        elif missing:
            flag = f'  ⚠ 流式有而 finalize 缺: {missing[:6]}'
        print(f'  段[{i}] 流式{len(wp):4d}词 → finalize{len(wf):4d}词{flag}', flush=True)
        if flag:
            print(f'        流式: {pre[:110]}', flush=True)
            print(f'        定稿: {fin[:110]}', flush=True)
    print(f'\n★ {len(records)} 段中 {bad} 段出现重复退化', flush=True)


if __name__ == '__main__':
    main()
