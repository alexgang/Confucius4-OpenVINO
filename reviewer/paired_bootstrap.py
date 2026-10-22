"""Paired bootstrap over VAD segments: is system B's WER really different from system A's?

Errors come from ONE global alignment of the whole reference against each system's concatenated
output, and every error is then attributed to the hypothesis segment it falls in. Per-segment
error counts therefore sum exactly to the global S+D+I, which assigning reference words to
segments by time does not (words near a boundary land in the wrong segment).
Usage: paired_bootstrap.py <baseline_dir> <A.txt> <B.txt> [n_boot]
"""
import glob
import json
import re
import sys

import jiwer
import numpy as np

try:  # run from the same folder as compare_wer.py (e.g. copied to the target machine)
    from compare_wer import norm, spread  # noqa: E402
except ImportError:  # run from ~/asr_baseline where it lives under scripts/
    sys.path.insert(0, __file__.rsplit('scripts', 1)[0])
    from scripts.compare_wer import norm, spread  # noqa: E402

LINE = re.compile(r'\s*\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)')


def load_segments(path):
    out = []
    for line in open(path, encoding='utf-8'):
        m = LINE.match(line)
        if m:
            out.append((float(m[1]), float(m[2]), m[3]))
    return out


def baseline_words(d):
    words = []
    for p in sorted(glob.glob(f'{d}/seg*.json')):
        s = json.load(open(p, encoding='utf-8'))
        for g in s['raw']['segments']:
            words += spread(s['start'] + g['start'], s['start'] + g['end'], g['text'])
    return [w for _, w in sorted(words)]


def per_segment_errors(segs, ref):
    hyp, owner = [], []
    for i, (_, _, text) in enumerate(segs):
        ws = norm(text)
        hyp += ws
        owner += [i] * len(ws)
    out = jiwer.process_words(' '.join(ref), ' '.join(hyp))
    errs = np.zeros(len(segs))
    for ch in out.alignments[0]:
        if ch.type == 'equal':
            continue
        if ch.type == 'delete':   # no hyp word: charge the segment the gap falls into
            pos = min(ch.hyp_start_idx, len(owner) - 1)
            errs[owner[pos]] += ch.ref_end_idx - ch.ref_start_idx
        else:                      # substitute / insert: charge the segments of the hyp words
            n_ref = ch.ref_end_idx - ch.ref_start_idx
            hyp_idx = range(ch.hyp_start_idx, ch.hyp_end_idx)
            for k in hyp_idx:
                errs[owner[k]] += 1
            if n_ref > len(hyp_idx):   # substitution that also deletes extra ref words
                errs[owner[min(ch.hyp_start_idx, len(owner) - 1)]] += n_ref - len(hyp_idx)
    return errs, out.substitutions + out.deletions + out.insertions


def main():
    base, fa, fb = sys.argv[1], sys.argv[2], sys.argv[3]
    n_boot = int(sys.argv[4]) if len(sys.argv) > 4 else 5000
    ref = baseline_words(base)
    sa, sb = load_segments(fa), load_segments(fb)
    assert len(sa) == len(sb), 'segmentations differ'
    ea, tot_a = per_segment_errors(sa, ref)
    eb, tot_b = per_segment_errors(sb, ref)
    assert abs(ea.sum() - tot_a) < 1e-6 and abs(eb.sum() - tot_b) < 1e-6, 'attribution lost errors'
    n = len(ref)
    # each segment's weight is its share of reference words, taken from system A's hypothesis span
    ref_per_seg = np.array([max(1, len(norm(t))) for _, _, t in sa], dtype=float)
    ref_per_seg *= n / ref_per_seg.sum()
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(sa), size=(n_boot, len(sa)))
    delta = (eb[idx].sum(1) - ea[idx].sum(1)) / ref_per_seg[idx].sum(1)
    lo, hi = np.percentile(delta, [2.5, 97.5])
    print(f'A  WER {tot_a / n:.2%} ({int(tot_a)} errors)   B  WER {tot_b / n:.2%} ({int(tot_b)} errors)   '
          f'delta(B-A) = {(tot_b - tot_a) / n:+.2%}')
    print(f'95% CI of delta (paired bootstrap, {n_boot}x over {len(sa)} segments): [{lo:+.2%}, {hi:+.2%}]')
    print(f'segments where B has fewer/equal/more errors than A: '
          f'{(eb < ea).sum()}/{(eb == ea).sum()}/{(eb > ea).sum()}')
    print('=> ' + ('statistically distinguishable' if lo > 0 or hi < 0 else 'NOT distinguishable from zero'))


if __name__ == '__main__':
    main()
