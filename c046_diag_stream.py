"""c046_diag_stream.py — C-046: 流式 vs 离线 WER 差距的取证与根因定位

问题: int8 流式 17.87% vs 离线 7.84%（10pp差, 其中插入 1140 vs 362）。

流式循环（streaming_asr.py + segment_encoder_backend.py）每个 chunk 做:
    cur_ids   = encode(raw_decoded)                # 上一次的全文假设
    prefix    = decode(cur_ids[: len-k])           # k = unfixed_token_num = 5, **永久冻结**
    gen_ids   = greedy_decode(audio_accum, prefix) # 全量音频 + 前缀, 重新生成全文
    raw_decoded = prefix + gen_text
→ 每个 chunk 都重写全文, 但只有"除最后 k 个 token"以外的部分被永久提交。

本脚本做两件事:
  A. 取证: 逐 chunk 记录 (提交前缀长度 / 假设长度 / EOS / 重复插入量 /
     与"同音频离线解码"的首次分歧位置), 定位误差从哪一步进入。
  B. 判决实验: 扫 5 种 (回滚预算 k, max_new_tokens) 组合, 看 WER 如何变化,
     从而判断根因是"提交过早(前缀中毒)"还是"生成被max_new_tokens 截断"。

用法: .venv python c046_diag_stream.py
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
from difflib import SequenceMatcher

from segment_encoder_backend import SegmentEncoderOVBackend
from streaming_asr import parse_asr_output

ENC_DIR = 'models/ov-encoder-segment-reviewer'
DEC_DIR = 'models/ov-int8-past'
SR = 16000
EOS_IDS = {151643, 151645}
CHUNK_SEC = 0.64

# C-040 标记的 INT8 翻转段+ 3 个随机段（覆盖不同内容/时长）
TEST_SEGMENTS = [
    (1925.4, 1939.5, 'seg118_c040flip'),
    (2622.2, 2640.4, 'seg161_c040flip'),
    (2656.8, 2675.9, 'seg163_c040flip'),
]

# (变体名, unfixed_token_num, max_new_tokens)   k=None 表示"全量重解, 不带前缀"
VARIANTS = [
    ('V0_k5_m32',   5,    32),     # 当前生产配置
    ('V1_k5_m128',  5,    128),    # 只放开生成长度
    ('V2_k30_m32',  30,   32),     # 只放大回滚预算
    ('V3_kinf_m32', None, 32),     # 全量重解 + 短生成
    ('V4_kinf_m128', None, 128),   # 全量重解 + 足量生成  (= 离线)
]

OUT_DIR = 'reports/c046_stream_gap'


def norm_words(s):
    s = s.lower()
    s = re.sub(r"[^\w' ]", ' ', s).replace("'", '')
    return [w for w in s.split() if w]


def load_ref():
    """MiniMax 参考: [(start, word)]"""
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
    from collections import Counter
    c = Counter(tuple(ws[i:i + n]) for i in range(len(ws) - n + 1))
    return sum(v - 1 for v in c.values() if v > 1)


class Runner:
    """复刻官方流式循环, 但 token 级可观测。"""

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
        ehs, _, N = self.b.encode_audio(audio_accum)
        gen_ids = self.b.greedy_decode_with_prefix(ehs, self.prefix_ids(prefix_text), max_new)
        eos = bool(gen_ids) and gen_ids[-1] in EOS_IDS
        return gen_ids, eos

    def run_stream(self, seg_audio, k, max_new, collect_diag=False, offline_texts=None):
        raw_decoded = ''
        prev_committed = []
        rows = []
        n_chunks = (len(seg_audio) + int(CHUNK_SEC * SR) - 1) // int(CHUNK_SEC * SR)
        for ci in range(n_chunks):
            audio_accum = seg_audio[:min((ci + 1) * int(CHUNK_SEC * SR), len(seg_audio))]
            cur_ids = self.tok.encode(raw_decoded, add_special_tokens=False)
            end_idx = max(0, len(cur_ids) - k) if k is not None else 0
            prefix = self.tok.decode(cur_ids[:end_idx]) if end_idx > 0 else ''
            gen_ids, eos = self.decode_once(audio_accum, prefix, max_new)
            gen_text = self.tok.decode(gen_ids, skip_special_tokens=True)
            raw_decoded = (prefix + gen_text) if prefix else gen_text
            _lang, txt = parse_asr_output(raw_decoded)
            committed = norm_words(txt)

            if collect_diag:
                # 本 chunk 新提交的部分 = committed 去掉与上次提交重复的前缀
                sm = SequenceMatcher(a=prev_committed, b=committed, autojunk=False)
                new_words = 0
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag in ('insert', 'replace'):
                        new_words += (j2 - j1)
                # 与同音频离线解码的首次分歧
                first_diff = -1
                if offline_texts is not None:
                    off = norm_words(offline_texts.get(ci, ''))
                    n = min(len(off), len(committed))
                    d = next((i for i in range(n) if off[i] != committed[i]), -1)
                    if d == -1 and len(off) != len(committed):
                        d = n
                    first_diff = d
                rows.append({
                    'chunk': ci, 'audio_s': round(len(audio_accum) / SR, 2),
                    'prefix_tokens': end_idx, 'hyp_tokens': len(gen_ids),
                    'eos': eos, 'committed_words': len(committed),
                    'new_words': new_words, 'first_diff_vs_offline': first_diff,
                })
            prev_committed = committed
        return txt, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seg-start', type=int, default=0, help='追加从 61-min 分段里取 N 个随机段')
    ap.add_argument('--n-extra', type=int, default=0)
    ap.add_argument('--diag-only', default='V0_k5_m32')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    ref = load_ref()
    print(f'[c046] reference words: {len(ref)}', flush=True)

    audio, sr = sf.read('test_audio/260902_SPE_audio.wav', dtype='float32')
    if audio.ndim > 1:
        audio = audio[:, 0]
    assert sr == SR

    segs = list(TEST_SEGMENTS)
    if args.n_extra > 0:
        with open('reports/spe_61min_segments_ov-mix12-past.json', encoding='utf-8') as f:
            allsegs = json.load(f)
        picks = [5, 60, 120, 180, 200][:args.n_extra]
        for p in picks:
            if p < len(allsegs):
                s = allsegs[p]
                segs.append((float(s['start_s']), float(s['end_s']), f'seg{p}'))
    print(f'[c046] test segments: {[x[2] for x in segs]}', flush=True)

    print('[c046] loading backend (int8 + segment encoder) ...', flush=True)
    backend = SegmentEncoderOVBackend(encoder_dir=ENC_DIR, decoder_dir=DEC_DIR,
                                      device='GPU.0', precision='f16')
    runner = Runner(backend)

    # 预热: 编译后第一次推理会直接吐 EOS (实测), 必须先跑一次废弃推理
    print('[c046] warmup ...', flush=True)
    _ids, _ = runner.decode_once(audio[:5 * SR], '', 16)
    print(f'[c046] warmup done (first id={_ids[0] if _ids else None})', flush=True)

    results = {}
    # ── 每段的离线解码 (同decoder, 单次全量) 作为对照 ──
    offline = {}
    off_tot = {'ref': 0, 'S': 0, 'D': 0, 'I': 0}
    print('\n[c046] === 离线全量解码 (对照) ===', flush=True)
    for s, e, label in segs:
        seg = audio[int(s * SR):int(e * SR)]
        ids, _ = runner.decode_once(seg, '', 128)
        _lang, txt = parse_asr_output(backend.tokenizer.decode(ids, skip_special_tokens=True))
        offline[label] = txt
        r = ref_slice(ref, s, e)
        hyp = norm_words(txt)
        S, D, I = sdi(r, hyp)
        off_tot['ref'] += len(r); off_tot['S'] += S; off_tot['D'] += D; off_tot['I'] += I
        print(f'  {label:16s} [{s:.1f}-{e:.1f}] ref={len(r):4d} hyp={len(hyp):4d} '
              f'WER={100.0*(S+D+I)/max(len(r),1):6.2f}%  n3={n_repeats(hyp)}', flush=True)
    off_wer = 100.0 * (off_tot['S'] + off_tot['D'] + off_tot['I']) / max(off_tot['ref'], 1)
    print(f'  >> offline TOTAL WER={off_wer:.2f}% (ref={off_tot["ref"]} S={off_tot["S"]} '
          f'D={off_tot["D"]} I={off_tot["I"]})', flush=True)

    # ── 变体扫描 ──
    for vname, k, max_new in VARIANTS:
        print(f'\n[c046] === {vname} (unfixed_token_num={k}, max_new_tokens={max_new}) ===', flush=True)
        t0 = time.perf_counter()
        tot = {'ref': 0, 'S': 0, 'D': 0, 'I': 0, 'hyp': 0, 'n3': 0}
        per_seg = {}
        diag_rows = []
        for s, e, label in segs:
            seg = audio[int(s * SR):int(e * SR)]
            collect = (vname == args.diag_only)
            offline_texts = None
            if collect:
                n_chunks = (len(seg) + int(CHUNK_SEC * SR) - 1) // int(CHUNK_SEC * SR)
                offline_texts = {}
                for ci in range(n_chunks):
                    acc = seg[:min((ci + 1) * int(CHUNK_SEC * SR), len(seg))]
                    ids, _ = runner.decode_once(acc, '', 128)
                    _lang, t = parse_asr_output(backend.tokenizer.decode(ids, skip_special_tokens=True))
                    offline_texts[ci] = t
            txt, rows = runner.run_stream(seg, k, max_new, collect_diag=collect,
                                          offline_texts=offline_texts)
            r = ref_slice(ref, s, e)
            hyp = norm_words(txt)
            S, D, I = sdi(r, hyp)
            per_seg[label] = {'ref': len(r), 'hyp': len(hyp), 'S': S, 'D': D, 'I': I,
                              'wer': round(100.0 * (S + D + I) / max(len(r), 1), 2),
                              'n3': n_repeats(hyp), 'text': txt}
            tot['ref'] += len(r); tot['hyp'] += len(hyp)
            tot['S'] += S; tot['D'] += D; tot['I'] += I; tot['n3'] += n_repeats(hyp)
            if collect:
                for row in rows:
                    row['seg'] = label
                    diag_rows.append(row)
            print(f'  {label:16s} ref={len(r):4d} hyp={len(hyp):4d} S={S:4d} D={D:3d} I={I:4d} '
                  f'WER={100.0*(S+D+I)/max(len(r),1):6.2f}% n3={n_repeats(hyp):3d}', flush=True)
        wall = time.perf_counter() - t0
        agg_wer = 100.0 * (tot['S'] + tot['D'] + tot['I']) / max(tot['ref'], 1)
        print(f'  >> {vname}: TOTAL WER={agg_wer:.2f}%  S={tot["S"]} D={tot["D"]} I={tot["I"]} '
              f'n3={tot["n3"]}  wall={wall:.0f}s', flush=True)
        results[vname] = {'k': k, 'max_new': max_new, 'agg_wer': round(agg_wer, 2),
                          'totals': tot, 'per_seg': per_seg, 'wall_s': round(wall, 1)}
        if diag_rows:
            results[vname]['diag'] = diag_rows

    with open(os.path.join(OUT_DIR, 'variants.json'), 'w', encoding='utf-8') as f:
        json.dump({'offline': offline, 'offline_agg': {'wer': round(off_wer, 2), **off_tot},
                   'variants': results}, f, ensure_ascii=False, indent=2)
    print(f'\n[c046] → {OUT_DIR}/variants.json', flush=True)

    # ── 汇总表 ──
    print('\n=== C-046 汇总 (测试段合计) ===')
    print(f'{"variant":16s} {"k":>6s} {"maxnew":>7s} {"WER%":>7s} {"S":>5s} {"D":>4s} {"I":>5s} {"n3":>5s}')
    print('-' * 62)
    print(f'{"offline(对照)":16s} {"-":>6s} {128:>7d} {off_wer:7.2f} {off_tot["S"]:5d} '
          f'{off_tot["D"]:4d} {off_tot["I"]:5d} {"-":>5s}')
    for vname, k, max_new in VARIANTS:
        r = results[vname]
        t = r['totals']
        print(f'{vname:16s} {str(k):>6s} {max_new:>7d} {r["agg_wer"]:7.2f} {t["S"]:5d} {t["D"]:4d} {t["I"]:5d} {t["n3"]:5d}')

    # ── 取证摘要 ──
    if args.diag_only in results and 'diag' in results[args.diag_only]:
        rows = results[args.diag_only]['diag']
        print(f'\n=== 取证 ({args.diag_only}) ===')
        n_eos = sum(1 for r in rows if r['eos'])
        firsts = [r['first_diff_vs_offline'] for r in rows if r['first_diff_vs_offline'] >= 0]
        print(f'chunks={len(rows)}  EOS 触发={n_eos} ({100.0*n_eos/max(len(rows),1):.1f}%)')
        print(f'首次与离线分歧发生在 chunk: {sorted(set(r["chunk"] for r in rows if r["first_diff_vs_offline"] >= 0))[:12]}')
        print(f'{"seg":16s} {"chunk":>5s} {"audio_s":>7s} {"pfx_tok":>7s} {"hyp_tok":>7s} {"eos":>5s} {"new_w":>5s} {"diff@":>5s}')
        for r in rows[:40]:
            print(f'{r["seg"]:16s} {r["chunk"]:5d} {r["audio_s"]:7.2f} {r["prefix_tokens"]:7d} '
                  f'{r["hyp_tokens"]:7d} {str(r["eos"]):>5s} {r["new_words"]:5d} {r["first_diff_vs_offline"]:5d}')


if __name__ == '__main__':
    main()