"""Where do loops START within a segment? Correlate loop onset with window boundaries (8s)."""
import re
from collections import Counter

def norm(w):
    w = w.lower(); w = re.sub(r"[^\w']", "", w).replace("'", "")
    return w

segs = []
for line in open("reports/spe_61min_transcript_noreset.txt", encoding="utf-8"):
    m = re.match(r"^\[\s*([\d.]+)\s*-\s*([\d.]+)\]\s*(.*)$", line.strip())
    if m:
        ws = [norm(w) for w in m.group(3).split() if norm(w)]
        segs.append((float(m.group(1)), float(m.group(2)), ws))

def loop_onset(ws, L=6):
    """first index i where ws[i:i+L] occurs again later (>=2 occurrences)."""
    seen = {}
    for i in range(len(ws) - L + 1):
        ng = tuple(ws[i:i + L])
        if ng in seen:
            return seen[ng], i  # first occurrence index, second occurrence index
        seen[ng] = i
    return None, None

rows = []
for s, e, ws in segs:
    n4 = sum(v - 1 for v in Counter(tuple(ws[i:i+4]) for i in range(len(ws)-3)).values() if v >= 2)
    if n4 < 2:
        continue
    first, second = loop_onset(ws)
    if first is None:
        continue
    dur = e - s
    rows.append((s, e, dur, len(ws), n4, first, second, first / max(1, len(ws))))

rows.sort(key=lambda r: -r[4])
print(f"{'seg_start':>9} {'dur':>5} {'words':>5} {'n4':>3} {'loop1st':>7} {'@s':>6} {'frac':>5}  loop_text")
for r in rows[:25]:
    s, e, dur, nw, n4, first, second, frac = r
    ws = [x for x in segs if x[0] == s][0][2]
    print(f"{s:9.1f} {dur:5.1f} {nw:5d} {n4:3d} {first:7d} {s + first*0.2:6.1f} {frac:5.2f}  {' '.join(ws[first:first+8])}")

# stats: fraction of segments whose loop starts in first half vs after 60% of segment
fracs = [r[7] for r in rows]
import statistics
print(f"\nloop segments: {len(rows)}; median onset frac={statistics.median(fracs):.2f}; "
      f"onset frac>0.5: {sum(1 for f in fracs if f>0.5)}/{len(fracs)}; >0.6: {sum(1 for f in fracs if f>0.6)}")
