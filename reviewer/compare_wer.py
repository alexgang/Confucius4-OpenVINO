"""Compare target transcript vs MiniMax baseline.
Usage: compare_wer.py <baseline_dir> <target_transcript.txt> [window_sec]
Both sides are lines "[start-end] text". Baseline words carry MiniMax segment timestamps;
target words are spread linearly over their segment. Words are bucketed into fixed time
windows (default 120 s) so differing segmentations don't distort the per-window WER.
"""
import glob, json, re, sys
import jiwer

NUM = {'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6', 'seven': '7',
       'eight': '8', 'nine': '9', 'ten': '10'}


def norm(t):
    """Tokenize for mixed Chinese/English scoring (MER): CJK per character,
    English per word. Scoring whole Chinese runs as single tokens would make
    the error rate meaningless, so split them."""
    t = t.lower().replace('’', "'")
    t = re.sub(r"[^a-z0-9'一-鿿 ]+", ' ', t)
    # separate CJK characters so each becomes its own token
    t = re.sub(r'([一-鿿])', r' \1 ', t)
    return [NUM.get(w, w) for w in t.split()]


def spread(start, end, text):
    ws = norm(text)
    if not ws:
        return []
    step = (end - start) / len(ws)
    return [(start + (i + 0.5) * step, w) for i, w in enumerate(ws)]


def load_baseline(d):
    out = []
    for p in sorted(glob.glob(f'{d}/seg*.json')):
        s = json.load(open(p, encoding='utf-8'))
        subs = s['raw'].get('segments') or [{'start': 0, 'end': s['end'] - s['start'], 'text': s['text']}]
        for g in subs:
            out += spread(s['start'] + g['start'], s['start'] + g['end'], g['text'])
    return out


def load_target(p):
    out = []
    for line in open(p, encoding='utf-8'):
        m = re.match(r'\s*\[\s*([\d.]+)\s*-\s*([\d.]+)\s*\]\s*(.*)', line)
        if m:
            out += spread(float(m[1]), float(m[2]), m[3])
    return out


def main():
    base, tgt = load_baseline(sys.argv[1]), load_target(sys.argv[2])
    win = float(sys.argv[3]) if len(sys.argv) > 3 else 120
    end = max(t for t, _ in base + tgt)
    rows = []
    for k in range(int(end // win) + 1):
        b = ' '.join(w for t, w in base if k * win <= t < (k + 1) * win)
        h = ' '.join(w for t, w in tgt if k * win <= t < (k + 1) * win)
        if b:
            o = jiwer.process_words(b, h)
            rows.append((k * win, len(b.split()), o.wer, o.substitutions, o.deletions, o.insertions))
    o = jiwer.process_words(' '.join(w for _, w in base), ' '.join(w for _, w in tgt))
    print(f'OVERALL  ref_words={len(base)} hyp_words={len(tgt)}  WER={o.wer:.2%}  '
          f'S={o.substitutions} D={o.deletions} I={o.insertions}')
    print(f'{"t(min)":>7} {"words":>6} {"WER":>7} {"S":>4} {"D":>4} {"I":>4}')
    for t, n, w, s, d, i in rows:
        print(f'{t / 60:7.1f} {n:6d} {w:7.1%} {s:4d} {d:4d} {i:4d}' + ('   <<' if w > 0.15 else ''))
    ws = sorted(r[2] for r in rows)
    print(f'window WER  P50={ws[len(ws) // 2]:.1%}  P90={ws[int(len(ws) * 0.9)]:.1%}  max={ws[-1]:.1%}')


if __name__ == '__main__':
    main()
