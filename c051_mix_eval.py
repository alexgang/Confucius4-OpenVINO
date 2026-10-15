"""c051_mix_eval.py — C-050/C-051: 中英混合 + 单语长音频流式评测

背景（C-050）:
  现有 61-min 测试集是纯英文。自适应生成长度的中文分支
  (_is_last_token_chinese / 预算翻倍) 从未在真实中文流式上验证过,
  中英混合的语码切换场景也完全没覆盖。

本脚本做三件事:
  1. 在测试集上跑 SegmentedStreamer, 产出 transcript / segments / 诊断
  2. 按 MER 口径评分: **中文按字、英文按词**(不用 ≤11% 那条英文线套用)
  3. 报告 C-050 要求的必查项:
       - 整体 MER / S / D / I
       - 中文为主的段 vs 英文为主的段 分别的 MER
       - 重复 4-gram 数
       - RTF (P50 / P95 / max)
       - lang 翻转次数、中文分支触发率、中英各自平均生成预算

force_language 必须保持 None（自动）:  混合音频里模型逐 chunk 判语言,
强制单一语言会破坏另一种语言的输出。

用法:
  .venv python c051_mix_eval.py --sets mix_60min --variants adaptive
  .venv python c051_mix_eval.py --sets zh_60min,mix_60min,en_60min --variants adaptive
  .venv python c051_mix_eval.py --sets mix_60min --variants adaptive,finish_first --max-min 5
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from difflib import SequenceMatcher

os.environ.setdefault('USE_TORCH', '0')
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SR = 16000
SETS = os.path.join(ROOT, 'test_data', 'sets')
OUT_ROOT = os.path.join(ROOT, 'reports', 'c051_mix')

# 每个变体 = (输出后缀, finish_budget)。adaptive 为必须与 C-047 交付一致的口径。
VARIANTS = {
    'adaptive': dict(adaptive=True, finish_budget='max64'),
    'finish_first': dict(adaptive=True, finish_budget='first'),
    'fixed32': dict(adaptive=False, finish_budget='max64'),
}

_CJK = re.compile(r'[\u4e00-\u9fff]')
_PUNCT = re.compile(r'[^0-9a-z\u4e00-\u9fff\s]')


# ── MER 归一化: 中文按字, 英文按词 ──────────────────────────────────────
def mer_tokens(text):
    """混合文本切分为评测单元: 连续汉字串按字切, 拉丁/数字串按 token 保留。"""
    t = str(text).lower()
    t = _PUNCT.sub(' ', t)
    out = []
    for tok in t.split():
        if _CJK.search(tok):
            # 混合 token (如 "gpu加速"): 拆成 "gpu" + "加" + "速"
            for m in re.finditer(r'[\u4e00-\u9fff]+|[a-z0-9]+', tok):
                w = m.group(0)
                out.extend(list(w) if _CJK.match(w) else [w])
        else:
            out.append(tok)
    return out


def score_tokens(ref, hyp):
    """S/D/I + MER。口径同 c045_wer.py (difflib, autojunk=False)。"""
    if not ref:
        return dict(S=0, D=0, I=len(hyp), mer=0.0 if not hyp else 1.0, n_ref=0)
    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    S = D = I = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            S += max(i2 - i1, j2 - j1)
        elif tag == 'delete':
            D += i2 - i1
        elif tag == 'insert':
            I += j2 - j1
    return dict(S=S, D=D, I=I, mer=(S + D + I) / len(ref) * 100, n_ref=len(ref))


def n_gram_repeat(hyp, n=4):
    """重复 n-gram 数: 出现 ≥2 次的 n-gram 的总冗余数 (同 C-045 口径)。"""
    if len(hyp) < n:
        return 0
    c = Counter(tuple(hyp[i:i + n]) for i in range(len(hyp) - n + 1))
    return sum(v - 1 for v in c.values() if v > 1)


# ── 参考文本读取 ────────────────────────────────────────────────────────
def load_ref_lines(path):
    """解析 '[start-end] text' 行, 返回 [(start, end, text), ...]"""
    out = []
    for line in open(path, encoding='utf-8'):
        # 注意: build() 用 [%8.1f-%8.1f] 固定宽度输出, 数字前后有空格填充
        m = re.match(r'^\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)$', line.strip())
        if m and m.group(3).strip():
            out.append((float(m.group(1)), float(m.group(2)), m.group(3).strip()))
    return out


def load_manifest(set_name):
    p = os.path.join(SETS, set_name, 'manifest.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def dominant_lang(start, end, segs):
    """按源 utterance 的时长占比判断该区间的主导语言。

    返回 ('zh'|'en'|'mixed', zh_sec, en_sec)
    """
    zh = en = 0.0
    for s in segs:
        ov = min(end, s['end']) - max(start, s['start'])
        if ov <= 0:
            continue
        if s['lang'] == 'zh':
            zh += ov
        else:
            en += ov
    if zh == 0 and en == 0:
        return 'unknown', 0.0, 0.0
    if zh > 2 * en:
        return 'zh', zh, en
    if en > 2 * zh:
        return 'en', zh, en
    return 'mixed', zh, en


# ── 评测 ────────────────────────────────────────────────────────────────
def evaluate(set_name, seg_results, out_dir):
    manifest = load_manifest(set_name)
    ref_items = load_ref_lines(os.path.join(SETS, set_name, 'ref_official.txt'))

    ref_all, hyp_all = [], []
    ref_zh, hyp_zh, ref_en, hyp_en = [], [], [], []
    dom_stats = Counter()
    per_dom = {}

    for sg in seg_results:
        # utterance 按**中点归属**到唯一的 VAD 段，否则被切点跨越的句子会
        # 在相邻两段各计一次，凭空放大参考长度。
        own = [(s, e, t) for s, e, t in ref_items
               if sg['start_s'] <= (s + e) / 2 < sg['end_s']]
        if not own:
            continue
        dom, zsec, esec = dominant_lang(sg['start_s'], sg['end_s'],
                                        manifest['segments'])
        dom_stats[dom] += 1
        rtok = []
        for _s, _e, t in own:
            rtok.extend(mer_tokens(t))
        htok = mer_tokens(sg['text'])
        ref_all.extend(rtok)
        hyp_all.extend(htok)
        if dom == 'zh':
            ref_zh.extend(rtok); hyp_zh.extend(htok)
        elif dom == 'en':
            ref_en.extend(rtok); hyp_en.extend(htok)

    res = {
        'set': set_name,
        'overall': score_tokens(ref_all, hyp_all),
        'n4_repeat': n_gram_repeat(hyp_all, 4),
        'n3_repeat': n_gram_repeat(hyp_all, 3),
        'total_units': len(ref_all),
        'dominant_counts': dict(dom_stats),
    }
    if ref_zh:
        res['zh_segments'] = score_tokens(ref_zh, hyp_zh)
    if ref_en:
        res['en_segments'] = score_tokens(ref_en, hyp_en)

    rtf = sorted(sg['rtf'] for sg in seg_results if sg['rtf'] > 0)
    if rtf:
        n = len(rtf)
        res['rtf'] = {
            'overall': sum(sg['wall_s'] for sg in seg_results) /
                       sum(sg['duration_s'] for sg in seg_results),
            'p50': rtf[min(n - 1, int(n * 0.50))],
            'p95': rtf[min(n - 1, int(n * 0.95))],
            'max': rtf[-1],
        }

    # C-050 必查项: lang 翻转 / 中文分支触发率 / 中英平均预算
    diag = [sg.get('diag') for sg in seg_results if sg.get('diag')]
    if diag:
        tot_chunks = sum(d['n_chunks_logged'] for d in diag)
        tot_flips = sum(d['lang_flips'] for d in diag)
        zc = sum(d['n_zh_chunks'] for d in diag)
        ec = sum(d['n_en_chunks'] for d in diag)
        bz = sum(d['budget_mean_zh'] * d['n_zh_chunks'] for d in diag)
        be = sum(d['budget_mean_en'] * d['n_en_chunks'] for d in diag)
        res['diag'] = {
            'segments_with_diag': len(diag),
            'total_chunks': tot_chunks,
            'lang_flips_total': tot_flips,
            'lang_flips_per_seg_max': max(d['lang_flips'] for d in diag),
            'zh_chunk_ratio': (zc / tot_chunks * 100) if tot_chunks else 0.0,
            'budget_mean_zh': (bz / zc) if zc else 0.0,
            'budget_mean_en': (be / ec) if ec else 0.0,
            'budget_max_seen': max(d['budget_max'] for d in diag),
            'multi_lang_segments': sum(
                1 for d in diag if len(d['lang_values']) > 1),
        }
    return res


# ── 跑批 ────────────────────────────────────────────────────────────────
def run_variant(backend, set_name, audio, variant, audio_dur):
    from seg_stream import SegmentedStreamer
    cfg = VARIANTS[variant]
    out_name = f'{set_name}__{variant}'
    print(f'\n[c051] === {out_name} ===', flush=True)
    streamer = SegmentedStreamer(
        backend, strategy='vad',
        min_segment_sec=12.0, max_segment_sec=20.0,
        chunk_size_sec=0.64,
        unfixed_chunk_num=0, unfixed_token_num=5, max_new_tokens=32,
        adaptive_budget=cfg['adaptive'],
        finish_budget=cfg['finish_budget'],
        enable_hallucination_reset=False,
        enable_diag=True,
    )
    # C-050 第 2 项: force_language 保持 None（自动）
    assert streamer.force_language is None, 'force_language 必须为 None'

    t0 = time.perf_counter()
    text, segs = streamer.run(audio, progress=True)
    wall = time.perf_counter() - t0

    out = os.path.join(OUT_ROOT, set_name)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, f'transcript_{variant}.txt'), 'w', encoding='utf-8') as f:
        for sg in segs:
            f.write(f"[{sg['start_s']:8.1f}-{sg['end_s']:8.1f}] {sg['text']}\n")
    with open(os.path.join(out, f'segments_{variant}.json'), 'w', encoding='utf-8') as f:
        json.dump({'set': set_name, 'variant': variant, 'wall_s': wall,
                   'segments': segs}, f, ensure_ascii=False, indent=1)

    res = evaluate(set_name, segs, out)
    res['variant'] = variant
    res['wall_s'] = wall
    res['n_segs'] = len(segs)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sets', default='mix_60min')
    ap.add_argument('--variants', default='adaptive')
    ap.add_argument('--max-min', type=float, default=0.0,
                    help='只跑前 N 分钟（冒烟用），0 = 全长')
    ap.add_argument('--decoder-dir', default='models/ov-int8-past')
    ap.add_argument('--device', default='GPU.0')
    args = ap.parse_args()

    from segment_encoder_backend import SegmentEncoderOVBackend
    backend = SegmentEncoderOVBackend(
        encoder_dir='models/ov-encoder-segment-reviewer',
        decoder_dir=args.decoder_dir,
        device=args.device, precision='f16')

    os.makedirs(OUT_ROOT, exist_ok=True)
    all_res = []
    for set_name in args.sets.split(','):
        set_name = set_name.strip()
        wav = os.path.join(SETS, set_name, 'audio.wav')
        if not os.path.exists(wav):
            print(f'[c051] 跳过 {set_name}: 无 {wav}', flush=True)
            continue
        audio, sr = sf.read(wav, dtype='float32')
        if audio.ndim > 1:
            audio = audio[:, 0]
        if args.max_min > 0:
            audio = audio[:int(SR * 60 * args.max_min)]
        print(f'[c051] {set_name}: {len(audio)/SR/60:.2f} min', flush=True)
        for v in args.variants.split(','):
            all_res.append(run_variant(backend, set_name, audio, v.strip(),
                                       len(audio) / SR))

    summary_path = os.path.join(OUT_ROOT, 'summary.json')
    old = json.load(open(summary_path, encoding='utf-8')) \
        if os.path.exists(summary_path) else []
    old_keys = {(r['set'], r['variant']) for r in old}
    for r in all_res:
        old = [x for x in old if (x['set'], x['variant']) != (r['set'], r['variant'])]
        old.append(r)
    json.dump(old, open(summary_path, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    print('\n=== C-051 汇总 ===', flush=True)
    for r in all_res:
        o = r['overall']
        line = (f"{r['set']:11s} {r['variant']:13s} MER={o['mer']:6.2f}% "
                f"S={o['S']:5d} D={o['D']:5d} I={o['I']:5d} n4={r['n4_repeat']:5d} "
                f"units={r['total_units']:6d}")
        if 'rtf' in r:
            line += f" RTF={r['rtf']['overall']:.3f} P95={r['rtf']['p95']:.3f} max={r['rtf']['max']:.3f}"
        print(line, flush=True)
        for dom in ('zh_segments', 'en_segments'):
            if dom in r:
                d = r[dom]
                print(f"    {dom:12s} MER={d['mer']:6.2f}%  S={d['S']:5d} "
                      f"D={d['D']:5d} I={d['I']:5d} n_ref={d['n_ref']:6d}", flush=True)
        if 'diag' in r:
            g = r['diag']
            print(f"    diag: flips={g['lang_flips_total']:4d} "
                  f"multi_lang_seg={g['multi_lang_segments']:3d} "
                  f"zh_chunk={g['zh_chunk_ratio']:5.1f}% "
                  f"budget_zh={g['budget_mean_zh']:5.2f} "
                  f"budget_en={g['budget_mean_en']:5.2f} max={g['budget_max_seen']}", flush=True)
    print(f'\n→ {summary_path}', flush=True)


if __name__ == '__main__':
    main()
