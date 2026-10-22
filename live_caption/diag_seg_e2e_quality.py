r"""diag_seg_e2e_quality.py — 静音门槛的**端到端 ASR 质量**对照

背景
----
C-107 的离线结论（61 分钟真实演讲）：
  * 现状 `SILENCE_CUT_SEC=1.2` → 规则2 只有 17 段，94.2% 靠 12s 超时兜底
  * 降到 0.8s → 规则2 37 段（新增 29 个切点，**100% 安全**）

离线安全 ≠ 端到端无损。切段变多 → ASR 段数变多 → 每次解码的上下文变短、
段与段之间的接缝变多，可能带来：
  * 识别内容丢失/重复
  * 切分粒度变化导致的用词差异（真实内容相同）

本脚本跑**同一段真实音频**的不同静音门槛，做**词级内容对齐**比对，
判据与 C-105 一致（`diag_guard_e2e_align.py` 的口径）：
  * 真丢失 / 真多出（多重集差）→ 内容完整性
  * 词级对齐率 → 识别一致性
  * 各段的定稿时刻（墙钟）→ 白字时机

用法：
  python diag_seg_e2e_quality.py <wav> --cuts 1.2,0.8 --minutes 12 --lang English
"""

from __future__ import annotations

import os
import sys
import json
import time
import importlib
import re
import difflib
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import soundfile as sf

SR = 16000
STEP = 1600          # 100 ms


def run_once(L, audio, cut_sec, force_language, rel='1', guard_ms=None):
    os.environ['LIVECAP_SILENCE_CUT_SEC'] = str(cut_sec)
    os.environ['LIVECAP_GUARD_REL'] = rel
    if guard_ms is not None:
        os.environ['LIVECAP_MIN_SPEECH_RUN_MS'] = str(guard_ms)
    importlib.reload(L)
    eng = L.make_engine('gpu_int8', on_log=lambda m: None,
                        force_language=force_language)
    finals, stamps, apos = [], [], []
    t0 = time.perf_counter()
    for i in range(0, len(audio), STEP):
        r = eng.feed(audio[i:i + STEP], time.perf_counter())
        if r:
            finals.append(r)
            stamps.append(time.perf_counter() - t0)
            # 该段覆盖的**音频**结束时刻（秒）—— 与墙钟无关，
            # 用来算「音频 t 的内容在音频 t+Δ 才定稿」的白字延迟。
            apos.append((i + STEP) / 16000.0)
    tail = eng.flush()
    if tail:
        finals.append(tail)
        stamps.append(time.perf_counter() - t0)
        apos.append(len(audio) / 16000.0)
    wall = time.perf_counter() - t0
    eng.close()
    return finals, stamps, apos, wall


def norm_words(text):
    t = text.lower()
    t = re.sub(r'[^\w\s]', ' ', t, flags=re.UNICODE)
    return [w for w in t.split() if w]


def align(a_words, b_words):
    """词级对齐，返回 (相同, 替换, 仅A, 仅B, 对齐率)"""
    sm = difflib.SequenceMatcher(None, a_words, b_words, autojunk=False)
    same = sub = only_a = only_b = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            same += (i2 - i1)
        elif tag == 'replace':
            sub += min(i2 - i1, j2 - j1)
            only_a += max(0, (i2 - i1) - (j2 - j1))
            only_b += max(0, (j2 - j1) - (i2 - i1))
        elif tag == 'delete':
            only_a += (i2 - i1)
        elif tag == 'insert':
            only_b += (j2 - j1)
    return same, sub, only_a, only_b, same / max(1, len(a_words))


def main():
    args = sys.argv[1:]
    wav = args[0]
    minutes = 12.0
    force_language = 'English'
    cuts = [1.2, 0.8]
    outdir = None
    if '--minutes' in args:
        minutes = float(args[args.index('--minutes') + 1])
    if '--lang' in args:
        force_language = args[args.index('--lang') + 1]
    if '--cuts' in args:
        cuts = [float(x) for x in args[args.index('--cuts') + 1].split(',')]
    guard_ms = None
    if '--guard' in args:
        guard_ms = int(args[args.index('--guard') + 1])
    if '--out' in args:
        outdir = os.path.abspath(args[args.index('--out') + 1])
    if outdir is None:
        outdir = os.path.abspath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', '..', 'hy_bench', 'runs', 'c105_rule2', 'seg_quality'))
    os.makedirs(outdir, exist_ok=True)

    d, sr = sf.read(wav, dtype='float32')
    if d.ndim > 1:
        d = d[:, 0]
    d = d[:int(minutes * 60 * sr)]

    import live_caption_app as L

    print('=' * 78)
    print(f'静音门槛端到端质量对照  {os.path.basename(wav)}  {minutes} 分钟  '
          f'语种={force_language}')
    print('=' * 78, flush=True)

    runs = {}
    for cut in cuts:
        print(f'\n── SILENCE_CUT_SEC={cut} ──', flush=True)
        finals, stamps, apos, wall = run_once(L, d, cut, force_language,
                                              guard_ms=guard_ms)
        fn = os.path.join(outdir, f'cut{cut}.json')
        with open(fn, 'w', encoding='utf-8') as f:
            json.dump(dict(cut=cut, guard_ms=guard_ms, wall=wall,
                           stamps=stamps, apos=apos, finals=finals),
                      f, ensure_ascii=False, indent=1)
        words = [w for x in finals for w in norm_words(x)]
        print(f'   段数={len(finals)}  词数={len(words)}  墙钟={wall:.1f}s  '
              f'末段定稿 @{stamps[-1] if stamps else 0:.1f}s', flush=True)
        print(f'   → {fn}', flush=True)
        runs[cut] = dict(finals=finals, stamps=stamps, apos=apos,
                         wall=wall, words=words)

    # ── 逐对比对（以第一个门槛为基准） ──
    base_cut = cuts[0]
    base = runs[base_cut]
    print('\n' + '=' * 78)
    print(f'【质量比对】基准 = SILENCE_CUT_SEC {base_cut}')
    print('=' * 78)
    for cut in cuts[1:]:
        o = runs[cut]
        same, sub, only_b, only_a, rate = align(base['words'], o['words'])
        print(f'\n── {base_cut} vs {cut} ──')
        print(f'   词数 {len(base["words"])} vs {len(o["words"])}')
        print(f'   完全相同词: {same}')
        print(f'   替换(同音等): {sub}')
        print(f'   ★ 仅基准有（真丢失）: {only_a}  '
              f'{[w for w,_ in Counter(base["words"]).most_common() if False] or ""}')
        print(f'   ★ 仅新有（真多出）  : {only_b}')
        print(f'   对齐率: {rate*100:.2f}%')
        ca, cb = Counter(base['words']), Counter(o['words'])
        lost = [(w, ca[w]-cb[w]) for w in ca if ca[w] > cb[w]]
        gain = [(w, cb[w]-ca[w]) for w in cb if cb[w] > ca[w]]
        if lost:
            print(f'   丢失词明细: {lost[:15]}')
        if gain:
            print(f'   多出词明细: {gain[:15]}')

        # 白字时机（★ 用音频时间轴 apos，不用墙钟 stamps）
        def curve(r):
            ap, fin = r['apos'], r['finals']
            out = []
            cw = 0
            for i in range(len(ap)):
                cw += len(norm_words(fin[i]))
                out.append((ap[i], cw))
            return out
        cA, cB = curve(base), curve(o)
        print(f'   累计可见字数对比（★ 按**音频时间轴**，不受机器漂移影响）:')
        for T in (60, 120, 240, 360, 480, 600, 720):
            def at(c):
                v = 0
                for t, w in c:
                    if t <= T:
                        v = w
                return v
            va, vb = at(cA), at(cB)
            print(f'      音频@{T:>4}s  基准 {va:>5} 字   新 {vb:>5} 字   '
                  f'差 {vb-va:+5}')

        # ── 音频时间轴口径的「白字延迟」──
        # 定义：音频时刻 t 的内容，在音频时刻 t+lag 才定稿（转白）。
        # 用每个段的「覆盖到的音频末尾」→ 定稿时点来算，与墙钟无关。
        def lag_curve(r):
            out = []
            for a_end in r['apos']:
                out.append(a_end)
            return out

        def visible_at_audio(r, T):
            """音频时刻 T 时，已经定稿的内容覆盖到音频时刻多少。"""
            ap = r['apos']
            best = 0.0
            for a_end in ap:
                if a_end <= T:
                    best = max(best, a_end)
            return best

        print(f'   ★ 白字延迟（音频时间轴口径：音频 t 的内容在音频 t+lag 定稿）:')
        for T in (60, 120, 240, 360, 480, 600):
            la = T - visible_at_audio(base, T)
            lb = T - visible_at_audio(o, T)
            print(f'      音频@{T:>4}s  基准延迟 {la:>5.2f}s   '
                  f'新延迟 {lb:>5.2f}s   改善 {la-lb:+.2f}s')


if __name__ == '__main__':
    main()
