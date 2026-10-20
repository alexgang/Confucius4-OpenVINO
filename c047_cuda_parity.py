"""c047_cuda_parity.py — C-047: 与 CUDA(R2T2官方) 流式方案逐项对齐对比

问题: 为什么 CUDA 流式 WER 很低, OV 流式却17.87%? 错误引入点在哪?

已定位的 CUDA/OV 参数差异（源码级）:
  ┌────────────────────────┬──────────────────┬──────────────────┐
  │ 参数                    │ CUDA (example.py)│ OV (transcribe_  │
  │ │                        │stream.py)      │
  ├────────────────────────┼──────────────────┼──────────────────┤
  │ unfixed_chunk_num│ 0                  │ 0                │ 同
  │ unfixed_token_num       │ **1**            │ **5**            │ ★差异
  │ chunk_size_ms           │ **160**          │ **640**          │ ★差异
  │ max_new_tokens          │ **动态**         │ **固定 32**      │ ★★核心差异
  │ first chunk带lookahead  │ **是**           │ **否**           │ ★差异
  │ finish 预算             │ first_max_new_   │ max(64, 32)=64   │ ★差异
  │                         │ tokens (=1~2)    │                  │
  └────────────────────────┴──────────────────┴──────────────────┘

CUDA 核心机制 (example.py:118-155) —— 自适应生成长度:
    max_new_tokens = max(1, int((step+lookhead)/1280))   # 基准, 随音频长度
    floor = min(32, max(4, 2*int(step/1280)))
    loop:
        if len(text) > len(last_text_tmp):   # 有新内容 -> 预算降回基准(省算力)
            max_new_tokens =基准
        else:                                # 无新增 -> 逐步放宽, 让模型能改写
            max_new_tokens += 1              # (英语; 中文直接翻倍)
        if末token是中文: max_new_tokens *= 2
        max_new_tokens = min(floor, max_new_tokens)
  直觉: 输出增长说明前缀健康 -> 收紧预算; 输出停滞说明模型想改写/卡住 ->
       放宽预算给它空间。这正是 OV 固定 32 缺少的负反馈。

本脚本做受控对比, 逐项打开 CUDA 机制, 定位错误引入点。
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

ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/ov-int8-past'
SR = 16000
EOS_IDS = {151643, 151645}
PUNCT = '，。！？、；：.!?;:'

OUT_DIR = 'reports/c047_cuda_parity'


def loop_guard_pos(text):
    p1 = strict_loop_guard(text)
    return p1 if p1 >= 0 else strict_loop_guard_lenient(text)


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


def is_last_chinese(text):
    t = text.strip()
    if not t:
        return False
    for ch in t[-1]:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False


class Runner:
    def __init__(self, backend):
        self.b = backend
        self.tok = backend.tokenizer
        st = backend.init_streaming_state(unfixed_chunk_num=0, unfixed_token_num=5,
                                        chunk_size_sec=0.64)
        self.prompt_raw = st.prompt_raw
        self.raw_ids = self.tok.encode(self.prompt_raw, add_special_tokens=False)

    def prefix_ids(self, prefix_text):
        if not prefix_text:
            return []
        ids = self.tok.encode(self.prompt_raw + prefix_text, add_special_tokens=False)
        return ids[len(self.raw_ids):] if len(ids) > len(self.raw_ids) else []

    def decode_once(self, audio_accum, prefix_text, max_new):
        ehs, _, _ = self.b.encode_audio(audio_accum)
        gen = self.b.greedy_decode_with_prefix(ehs, self.prefix_ids(prefix_text), max_new)
        return gen, bool(gen) and gen[-1] in EOS_IDS

    # ── OV 生产语义: 固定 k回滚 + 固定 max_new ──
    def run_ov(self, seg_audio, chunk_ms=640, k=5, max_new=32, first_lookahead=False):
        step = int(round(chunk_ms / 1000.0 * SR))
        look = step if first_lookahead else 0
        raw = ''
        pos = 0
        first = True
        accum = np.zeros((0,), dtype=np.float32)   # 累积音频(等同 state.audio_accum)
        while pos < len(seg_audio):
            take = (step + look) if first else step
            piece = seg_audio[pos:pos + take]
            pos += piece.shape[0]
            accum = np.concatenate([accum, piece]) if accum.size else piece
            cur_ids = self.tok.encode(raw, add_special_tokens=False)
            end_idx = max(0, len(cur_ids) - k)
            prefix = self.tok.decode(cur_ids[:end_idx]) if end_idx > 0 else ''
            gen, _ = self.decode_once(accum, prefix, max_new)
            gt = _normalize_punct_by_context(self.tok.decode(gen, skip_special_tokens=True))
            raw = (prefix + gt) if prefix else gt
            _l, raw = parse_asr_output(raw)
            first = False
            if piece.shape[0] / SR < chunk_ms / 1000.0:
                break
        # finish
        cur_ids = self.tok.encode(raw, add_special_tokens=False)
        end_idx = max(1, len(cur_ids) - k)
        prefix = self.tok.decode(cur_ids[:end_idx])
        gen, _ = self.decode_once(seg_audio, prefix, max(max_new, 64))
        gt = _normalize_punct_by_context(self.tok.decode(gen, skip_special_tokens=True))
        _l, out = parse_asr_output((prefix + gt) if prefix else gt)
        return out

    # ── CUDA 语义: 自适应生成长度 + k=1 + 160ms chunk + first lookahead ──
    def run_cuda(self, seg_audio, chunk_ms=160, k=1, adaptive=True,
                 first_lookahead=True, guard=True, first_finish=False):
        step = int(round(chunk_ms / 1000.0 * SR))
        look = step if first_lookahead else 0
        raw = ''
        pos = 0
        first = True
        last_len = 0
        # CUDA: max_new = int((step+lookhead)/1280); floor = min(32, 2*int(step/1280))
        base = max(1, int((step + look) / 1280))
        floor = min(32, max(4, 2 * int(step / 1280)))
        first_max_new = base
        max_new = base
        gen_log = []
        accum = np.zeros((0,), dtype=np.float32)
        while pos < len(seg_audio):
            take = (step + look) if first else step
            piece = seg_audio[pos:pos + take]
            pos += piece.shape[0]
            accum = np.concatenate([accum, piece]) if accum.size else piece
            cur_ids = self.tok.encode(raw, add_special_tokens=False)
            end_idx = max(0, len(cur_ids) - k)
            prefix = self.tok.decode(cur_ids[:end_idx]) if end_idx > 0 else ''
            gen, eos = self.decode_once(accum, prefix, max_new)
            gt = _normalize_punct_by_context(self.tok.decode(gen, skip_special_tokens=True)).replace('\ufffd', '')
            raw = (prefix + gt) if prefix else gt
            _l, raw = parse_asr_output(raw)
            if guard:
                p = loop_guard_pos(raw)
                if p >= 0:
                    raw = raw[:p]
            gen_log.append({'budget': max_new, 'words': len(norm_words(raw)), 'eos': eos})

            # ── CUDA 自适应预算 (example.py:143-155) ──
            if adaptive:
                if len(raw) > last_len:
                    max_new = max(1, int(step / 1280))
                else:
                    if not is_last_chinese(raw):
                        max_new = max_new + 1
                    else:
                        max_new = max(1, int(step / 1280))
                if is_last_chinese(raw):
                    max_new = 2 * max_new
                max_new = min(floor, max_new)
            last_len = len(raw)
            first = False
            if piece.shape[0] / SR < chunk_ms / 1000.0:
                break
        # finish: 官方用 first_max_new_tokens(160ms 下仅 1 token)。但 1 token 收尾
        # 在 OV 上实测会截断尾巴(D=293), 因为 OV 的 gen 质量低于 vLLM,
        # 流式过程未必收敛。默认沿用 OV 的 max(64) 以隔离变量,
        # first_finish=True 时才复现 CUDA 原始行为。
        cur_ids = self.tok.encode(raw, add_special_tokens=False)
        end_idx = max(1, len(cur_ids) - k)
        prefix = self.tok.decode(cur_ids[:end_idx])
        fin_budget = first_max_new if first_finish else max(max_new, 64)
        gen, _ = self.decode_once(accum, prefix, max(1, fin_budget))
        gt = _normalize_punct_by_context(self.tok.decode(gen, skip_special_tokens=True)).replace('\ufffd', '')
        _l, out = parse_asr_output((prefix + gt) if prefix else gt)
        return out, gen_log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-extra', type=int, default=2)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ref = load_ref()
    audio, sr = sf.read('test_audio/<redacted>.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR

    segs = [
        (1925.4, 1939.5, 'seg118_c040flip'),
        (2622.2, 2640.4, 'seg161_c040flip'),
        (2656.8, 2675.9, 'seg163_c040flip'),
    ]
    if args.n_extra > 0:
        with open('reports/spe_61min_segments_ov-mix12-past.json', encoding='utf-8') as f:
            allsegs = json.load(f)
        for p in [5, 60][:args.n_extra]:
            if p < len(allsegs):
                sg = allsegs[p]
                segs.append((float(sg['start_s']), float(sg['end_s']), f'seg{p}'))

    print(f'[c047] segments: {[x[2] for x in segs]}', flush=True)
    backend = SegmentEncoderOVBackend(encoder_dir=ENC_DIR, decoder_dir=DEC_DIR,
                                      device='GPU.0', precision='f16')
    runner = Runner(backend)
    print('[c047] warmup ...', flush=True)
    runner.decode_once(audio[:5 * SR], '', 16)
    print('[c047] warmup done', flush=True)

    # (名称, fn, 说明)—— 逐项打开 CUDA 机制
    jobs = [
        ('A_ov_prod', lambda seg: (runner.run_ov(seg, 640, 5, 32, False), []),
         'OV 生产: 640ms/k=5/固定32'),
        ('B_k1', lambda seg: (runner.run_ov(seg, 640, 1, 32, False), []),
         '只改k: 5->1'),
        ('C_chunk160', lambda seg: (runner.run_ov(seg, 160, 5, 32, False), []),
         '只改 chunk: 640->160ms'),
        ('D_lookahead', lambda seg: (runner.run_ov(seg, 640, 5, 32, True), []),
         '只加 first-chunk lookahead'),
        ('E_adapt_only', lambda seg: runner.run_cuda(seg, 640, 5, True, False, True),
         '只开自适应预算(640ms/k=5/无lookahead)'),
        ('F_cuda_full', lambda seg: runner.run_cuda(seg, 160, 1, True, True, True),
         'CUDA 全套: 160ms/k=1/自适应/first-lookahead'),
        ('G_cuda_noadapt', lambda seg: runner.run_cuda(seg, 160, 1, False, True, True),
         'CUDA 但关自适应预算'),
        ('H_cuda_640', lambda seg: runner.run_cuda(seg, 640, 1, True, True, True),
         'CUDA 但 chunk=640ms'),
    ]

    results = {}
    for name, fn, desc in jobs:
        print(f'\n[c047] === {name}: {desc} ===', flush=True)
        t0 = time.perf_counter()
        tot = {'ref': 0, 'hyp': 0, 'S': 0, 'D': 0, 'I': 0, 'n3': 0}
        per_seg = {}
        budget_log = []
        for s, e, label in segs:
            seg = audio[int(s * SR):int(e * SR)]
            out = fn(seg)
            txt, glog = out if isinstance(out, tuple) else (out, [])
            r = ref_slice(ref, s, e)
            hyp = norm_words(txt)
            S, D, I = sdi(r, hyp)
            per_seg[label] = {'ref': len(r), 'hyp': len(hyp), 'S': S, 'D': D, 'I': I,
                              'wer': round(100.0 * (S + D + I) / max(len(r), 1), 2),
                              'n3': n_repeats(hyp), 'text': txt}
            tot['ref'] += len(r); tot['hyp'] += len(hyp)
            tot['S'] += S; tot['D'] += D; tot['I'] += I; tot['n3'] += n_repeats(hyp)
            if glog:
                budget_log.append({'seg': label, 'log': glog})
            print(f'  {label:16s} ref={len(r):4d} hyp={len(hyp):4d} S={S:4d} D={D:3d} I={I:4d} '
                  f'WER={100.0*(S+D+I)/max(len(r),1):6.2f}% n3={n_repeats(hyp):3d}', flush=True)
        wall = time.perf_counter() - t0
        wer = 100.0 * (tot['S'] + tot['D'] + tot['I']) / max(tot['ref'], 1)
        print(f'  >> {name}: WER={wer:.2f}%  S={tot["S"]} D={tot["D"]} I={tot["I"]} '
              f'n3={tot["n3"]}  wall={wall:.0f}s', flush=True)
        results[name] = {'desc': desc, 'wer': round(wer, 2), 'totals': tot,
                         'per_seg': per_seg, 'wall_s': round(wall, 1)}
        if budget_log:
            results[name]['budget_log'] = budget_log

    out = os.path.join(OUT_DIR, 'cuda_parity.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n[c047] saved -> {out}', flush=True)


if __name__ == '__main__':
    main()