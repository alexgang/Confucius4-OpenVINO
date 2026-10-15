"""c046_stream_fix.py — C-046 修复: 流式前缀过早冻结

根因（c046_diag_stream.py 实测锁定）:
  每个 chunk 用「已提交前缀(除最后k个token) + 全量音频」贪心重生成全文,
  前 k 之外永久冻结。k=5 时, 音频不足导致的猜错 token 会被永久锁死,
  成为自回归陷阱起点, 放大成重复循环 (seg161: n3=52, I=55, WER 100%)。
  k=5→30 使重复 106→2, WER 39.60%→20.24%, 证明根因在提交策略不在模型精度。

修复思路（自适应提交, 替代固定 k）:
  1. 共识提交: 只有连续 N 次 chunk 都给出相同 token 才冻结它。
     一次性的猜测天然不稳定, 会被自动留��回滚窗口, 不再被永久锁死。
  2. 重复守卫: 新提交部分若检出 n-gram 循环, 截断到循环起点。
     作为兜底, 防止个别段的错误前缀仍触发复读。
  3. 标点锚定: 遇到句读即立刻冻结(标点后不需要再改写), 避免尾部长期悬空。
     这同时能显著缩小平均前缀长度, 抵消共识提交带来的额外生成量。

用法:
  .venv python c046_stream_fix.py --n-extra 2 --variants fix
  .venv python c046_stream_fix.py --n-extra 2 --variants base,fix,fix_noguard
"""
import os, sys, time, json, re, argparse
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('PYTHONUTF8', '1')
os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('USE_TF', '0')
os.environ.setdefault('USE_FLAX', '0')

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

import numpy as np
import soundfile as sf
from collections import Counter
from difflib import SequenceMatcher

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import parse_asr_output, _normalize_punct_by_context
from c046_loop_guard import strict_loop_guard, strict_loop_guard_lenient


def loop_guard_pos(text):
    """组合守卫: strict(抓紧邻整段复读) + lenient(抓单词级复读)。

    不能直接用 streaming_asr._detect_any_loop —— 它在正常转写上系统性误报
    (seg60 正确离线输出被截断在第 103 字符, 60 词 -> 18 词)。
    """
    p1 = strict_loop_guard(text)
    if p1 >= 0:
        return p1
    return strict_loop_guard_lenient(text)

ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/ov-int8-past'
SR = 16000
EOS_IDS = {151643, 151645}
CHUNK_SEC = 0.64
PUNCT = '，。！？、；：.!?;:'

TEST_SEGMENTS = [
    (1925.4, 1939.5, 'seg118_c040flip'),
    (2622.2, 2640.4, 'seg161_c040flip'),
    (2656.8, 2675.9, 'seg163_c040flip'),
]

OUT_DIR = 'reports/c046_stream_gap'


def norm_words(s):
    s = s.lower()
    s = re.sub(r"[^\w' ]", ' ', s).replace("'", '')
    return [w for w in s.split() if w]


def load_ref():
    out = []
    for line in open('reports/c026_minimax_transcript.txt', encoding='utf-8'):
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\]\s*(.*)$', line.strip())
        if not m:
            continue
        st, en, txt = float(m.group(1)), float(m.group(2)), m.group(3)
        for w in norm_words(txt):
            out.append(((st + en) / 2.0, w))
    return out


def ref_slice(ref, s, e):
    return [w for t, w in ref if s - 0.5 <= t <= e + 0.5]


def sdi(ref, hyp):
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
    return S, D, I


def n_repeats(ws, n=3):
    c = Counter(tuple(ws[i:i + n]) for i in range(len(ws) - n + 1))
    return sum(v - 1 for v in c.values() if v > 1)


class Runner:
    def __init__(self, backend):
        self.b = backend
        self.tok = backend.tokenizer
        st = backend.init_streaming_state(unfixed_chunk_num=0, unfixed_token_num=5,
                                        chunk_size_sec=CHUNK_SEC)
        self.prompt_raw = st.prompt_raw
        self.raw_ids = self.tok.encode(self.prompt_raw, add_special_tokens=False)

    def prefix_ids(self, prefix_text):
        if not prefix_text:
            return []
        ids = self.tok.encode(self.prompt_raw + prefix_text, add_special_tokens=False)
        return ids[len(self.raw_ids):] if len(ids) > len(self.raw_ids) else []

    def decode_once(self, audio_accum, prefix_text, max_new):
        ehs, _, _ = self.b.encode_audio(audio_accum)
        gen_ids = self.b.greedy_decode_with_prefix(ehs, self.prefix_ids(prefix_text), max_new)
        return gen_ids, bool(gen_ids) and gen_ids[-1] in EOS_IDS

    # ── 基线: 官方固定 k 语义 ──
    def run_fixed_k(self, seg_audio, k=5, max_new=32):
        raw = ''
        for ci in range((len(seg_audio) + int(CHUNK_SEC * SR) - 1) // int(CHUNK_SEC * SR)):
            acc = seg_audio[:min((ci + 1) * int(CHUNK_SEC * SR), len(seg_audio))]
            cur_ids = self.tok.encode(raw, add_special_tokens=False)
            end_idx = max(0, len(cur_ids) - k)
            prefix = self.tok.decode(cur_ids[:end_idx]) if end_idx > 0 else ''
            gen_ids, _ = self.decode_once(acc, prefix, max_new)
            gen_text = _normalize_punct_by_context(self.tok.decode(gen_ids, skip_special_tokens=True))
            gen_text = gen_text.replace('\ufffd', '')
            raw = (prefix + gen_text) if prefix else gen_text
            _lang, raw = parse_asr_output(raw)
        return raw

    # ── 修复: 自适应共识提交 + 重复守卫 + 标点锚定 ──
    def run_fix(self, seg_audio, max_new=32, agree=2, max_stable=30,
                guard=True, punct_anchor=True, tail_flush=True):
        """
        agree:        同一字符需连续出现几次才冻结
        max_stable:   单轮最多提交多少字符(防前缀一次增长过多)
        guard:        重复守卫(截断新提交部分的 n-gram 循环)
        punct_anchor: 标点锚定(遇标点立即冻结, 不等共识)
        tail_flush:   段尾用一次全量重解收尾(清空未冻结候选)

        实现: LocalAgreement 策略。维护 cand(未冻结候选) 与 cnt(每个候选字符的
        连续一致轮数)。每轮只提交 cnt>=agree 的前缀; 模型改口时该位置计数归 1,
        自然退回未冻结区 —— 一次性猜测因此无法被永久锁死。

        tail_flush 的必要性: 共识提交偏保守, 段尾总有文本滞留在未冻结区
        (实测 seg60 有 145 字符/ 40% 尾部滞留 -> 过删 D=22)。段尾以累积的
        完整音频做一次无前缀全量重解, 相当于离线收尾, 只增加约1 次解码。
        """
        frozen = ''          # 已永久提交的文本
        cand = ''# 未冻结候选
        cnt = []             # cand 各字符的连续一致轮数
        for ci in range((len(seg_audio) + int(CHUNK_SEC * SR) - 1) // int(CHUNK_SEC * SR)):
            acc = seg_audio[:min((ci + 1) * int(CHUNK_SEC * SR), len(seg_audio))]
            prefix = frozen
            gen_ids, _ = self.decode_once(acc, prefix, max_new)
            gen_text = _normalize_punct_by_context(self.tok.decode(gen_ids, skip_special_tokens=True))
            gen_text = gen_text.replace('\ufffd', '')
            raw = (prefix + gen_text) if prefix else gen_text
            _lang, full = parse_asr_output(raw)

            # 重复守卫: 检出循环则截断到循环起点
            if guard:
                pos = loop_guard_pos(full)
                if pos >= 0:
                    full = full[:pos]

            # 已提交部分不可回退; 输出未增长则本轮无新信息
            if len(full) <= len(frozen):
                continue
            new_cand = full[len(frozen):]

            # 逐字符更新连续一致计数(未变位置 +1, 新增/改动位置重置为 1)
            new_cnt = []
            for i, ch in enumerate(new_cand):
                if i < len(cand) and i < len(cnt) and cand[i] == ch:
                    new_cnt.append(cnt[i] + 1)
                else:
                    new_cnt.append(1)

            # 可提交长度 = 满足 agree 的最长前缀, 再受 max_stable 限制
            commit_len = 0
            for c in new_cnt:
                if c >= agree:
                    commit_len += 1
                else:
                    break
            commit_len = min(commit_len, max_stable)

            # 标点锚定: 提交区内遇标点立即提交(含标点), 标点后无需改写
            if punct_anchor and commit_len > 0:
                for i, ch in enumerate(new_cand[:commit_len]):
                    if ch in PUNCT:
                        commit_len = i + 1
                        break

            if commit_len > 0:
                frozen += new_cand[:commit_len]
            cand, cnt = new_cand[commit_len:], new_cnt[commit_len:]

        if tail_flush:
            # 段尾收尾: 用完整音频做一次**无前缀**全量重解(等价离线)。
            # 不能带 frozen 前缀: frozen 只覆盖段的前半, 以中途截断的前缀继续
            # 生成会产出语义不连贯的内容(实测 seg60 hyp 44->18, S=46)。
            gen_ids, _ = self.decode_once(seg_audio, '', max(max_new, 128))
            gen_text = _normalize_punct_by_context(
                self.tok.decode(gen_ids, skip_special_tokens=True)).replace('\ufffd', '')
            _lang, final = parse_asr_output(gen_text)
        else:
            final = frozen + cand

        if guard:
            pos = loop_guard_pos(final)
            if pos >= 0:
                final = final[:pos]
        return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-extra', type=int, default=2)
    ap.add_argument('--variants', default='base,fix')
    ap.add_argument('--agree', type=int, default=2)
    ap.add_argument('--max-stable', type=int, default=30)
    ap.add_argument('--agree3', type=int, default=0, help='额外跑 agree=3 对照')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ref = load_ref()
    audio, sr = sf.read('test_audio/260902_SPE_audio.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR

    segs = list(TEST_SEGMENTS)
    if args.n_extra > 0:
        with open('reports/spe_61min_segments_ov-mix12-past.json', encoding='utf-8') as f:
            allsegs = json.load(f)
        for p in [5, 60, 120, 180, 200][:args.n_extra]:
            if p < len(allsegs):
                s = allsegs[p]
                segs.append((float(s['start_s']), float(s['end_s']), f'seg{p}'))

    print(f'[c046fix] reference words: {len(ref)}', flush=True)
    print(f'[c046fix] segments: {[x[2] for x in segs]}', flush=True)

    backend = SegmentEncoderOVBackend(encoder_dir=ENC_DIR, decoder_dir=DEC_DIR,
                                     device='GPU.0', precision='f16')
    runner = Runner(backend)
    print('[c046fix] warmup ...', flush=True)
    runner.decode_once(audio[:5 * SR], '', 16)
    print('[c046fix] warmup done', flush=True)

    jobs = []
    for v in args.variants.split(','):
        v = v.strip()
        if v == 'base':
            jobs.append(('base_k5', lambda seg: runner.run_fixed_k(seg, 5, 32)))
        elif v == 'fix':
            jobs.append((f'fix_a{args.agree}_s{args.max_stable}',
                         lambda seg: runner.run_fix(seg, 32, args.agree, args.max_stable,
                                                    True, True, True)))
        elif v == 'fix_notail':
            jobs.append(('fix_notail', lambda seg: runner.run_fix(seg, 32, args.agree, args.max_stable,
                                                                  True, True, False)))
        elif v == 'fix_noguard':
            jobs.append(('fix_noguard', lambda seg: runner.run_fix(seg, 32, args.agree, args.max_stable,
                                                                    False, True, True)))
        elif v == 'fix_nopunct':
            jobs.append(('fix_nopunct', lambda seg: runner.run_fix(seg, 32, args.agree, args.max_stable,
                                                                    True, False, True)))
        elif v == 'fix3':
            jobs.append(('fix_a3', lambda seg: runner.run_fix(seg, 32, 3, args.max_stable,
                                                               True, True, True)))
        elif v == 'fix3_notail':
            jobs.append(('fix_a3_notail', lambda seg: runner.run_fix(seg, 32, 3, args.max_stable,
                                                                      True, True, False)))
        elif v == 'k30':
            jobs.append(('k30', lambda seg: runner.run_fixed_k(seg, 30, 32)))

    results = {}
    for name, fn in jobs:
        print(f'\n[c046fix] === {name} ===', flush=True)
        t0 = time.perf_counter()
        tot = {'ref': 0, 'hyp': 0, 'S': 0, 'D': 0, 'I': 0, 'n3': 0}
        per_seg = {}
        for s, e, label in segs:
            seg = audio[int(s * SR):int(e * SR)]
            txt = fn(seg)
            r = ref_slice(ref, s, e)
            hyp = norm_words(txt)
            S, D, I = sdi(r, hyp)
            per_seg[label] = {'ref': len(r), 'hyp': len(hyp), 'S': S, 'D': D, 'I': I,
                              'wer': round(100.0 * (S + D + I) / max(len(r), 1), 2),
                              'n3': n_repeats(hyp), 'text': txt}
            tot['ref'] += len(r); tot['hyp'] += len(hyp)
            tot['S'] += S; tot['D'] += D; tot['I'] += I; tot['n3'] += n_repeats(hyp)
            print(f'  {label:16s} ref={len(r):4d} hyp={len(hyp):4d} S={S:4d} D={D:3d} I={I:4d} '
                  f'WER={100.0*(S+D+I)/max(len(r),1):6.2f}% n3={n_repeats(hyp):3d}', flush=True)
        wall = time.perf_counter() - t0
        wer = 100.0 * (tot['S'] + tot['D'] + tot['I']) / max(tot['ref'], 1)
        print(f'  >> {name}: WER={wer:.2f}%  S={tot["S"]} D={tot["D"]} I={tot["I"]} '
              f'n3={tot["n3"]}  wall={wall:.0f}s', flush=True)
        results[name] = {'wer': round(wer, 2), 'totals': tot, 'per_seg': per_seg,
                         'wall_s': round(wall, 1)}

    out = os.path.join(OUT_DIR, 'fix_variants.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n[c046fix] saved -> {out}', flush=True)


if __name__ == '__main__':
    main()