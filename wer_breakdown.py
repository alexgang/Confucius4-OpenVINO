"""Break down remaining WER of noreset transcript: S/D/I + worst segments + repeat stats (difflib)."""
import re
from collections import Counter
from difflib import SequenceMatcher

REP = "reports"

def words_from_minimax(path):
    ws = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\[[\d.\-]+\]\s*(.*)$", line.strip())
        if m and m.group(1).strip():
            ws.append(m.group(1).strip())
    return ws

def norm(w):
    w = w.lower()
    w = re.sub(r"[^\w']", "", w).replace("'", "")
    return w

def segments_from_transcript(path):
    segs = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\[\s*([\d.]+)\s*-\s*([\d.]+)\]\s*(.*)$", line.strip())
        if m:
            segs.append((float(m.group(1)), float(m.group(2)), m.group(3)))
    return segs

def ngram_repeats(words, n):
    c = Counter(tuple(words[i:i + n]) for i in range(len(words) - n + 1))
    rep = sum(v - 1 for v in c.values() if v >= 2)
    mx = max(c.values()) if c else 0
    return rep, mx

if __name__ == "__main__":
    ref = [norm(w) for w in words_from_minimax(f"{REP}/c026_minimax_transcript.txt") if norm(w)]
    segs = segments_from_transcript(f"{REP}/spe_61min_transcript_noreset.txt")
    hyp = []
    seg_words = []
    for s, e, t in segs:
        ws = [norm(w) for w in t.split() if norm(w)]
        seg_words.append((s, e, ws))
        hyp.extend(ws)

    sm = SequenceMatcher(a=ref, b=hyp, autojunk=False)
    S = D = I = 0
    sub_examples, ins_examples, del_examples = [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            S += max(i2 - i1, j2 - j1)
            if len(sub_examples) < 12:
                sub_examples.append((" ".join(ref[i1:i2]), " ".join(hyp[j1:j2])))
        elif tag == "delete":
            D += i2 - i1
            if len(del_examples) < 8:
                del_examples.append(" ".join(ref[i1:i2]))
        elif tag == "insert":
            I += j2 - j1
            if len(ins_examples) < 12:
                ins_examples.append(" ".join(hyp[j1:j2]))
    print(f"noreset vs MiniMax: words={len(hyp)} ref={len(ref)}")
    print(f"  S={S} D={D} I={I}  WER={100.0*(S+D+I)/len(ref):.2f}%")
    print(f"  insertions {I} = {100.0*I/len(ref):.1f}pp | deletions {D} = {100.0*D/len(ref):.1f}pp | subs {S} = {100.0*S/len(ref):.1f}pp")

    rows = []
    for s, e, ws in seg_words:
        n3, m3 = ngram_repeats(ws, 3)
        n4, m4 = ngram_repeats(ws, 4)
        rows.append((s, e, len(ws), n3, m3, n4, m4, " ".join(ws)))
    rows.sort(key=lambda r: -r[4])
    print("\nTop 15 segments by n4_repeat (count of extra occurrences of any repeated 4-gram):")
    for r in rows[:15]:
        print(f"  [{r[0]:7.1f}-{r[1]:7.1f}] words={r[2]:3d} n3={r[3]:3d} n4={r[4]:3d} maxrun={r[5]}")
    print(f"\ntotal n3={sum(r[3] for r in rows)} n4={sum(r[4] for r in rows)}; segments with n4>0: {sum(1 for r in rows if r[4]>0)}/{len(rows)}")

    print("\n=== worst 3 segment texts ===")
    for r in rows[:3]:
        print(f"\n[{r[0]:.1f}-{r[1]:.1f}] n4={r[4]}:\n{r[7][:700]}")

    print("\n=== insertion examples (hyp-only) ===")
    for ex in ins_examples:
        print("  +", ex[:160])
    print("\n=== substitution examples (ref -> hyp) ===")
    for a, b in sub_examples:
        print("  ~", a[:80], "->", b[:80])
    print("\n=== deletion examples (ref-only) ===")
    for ex in del_examples:
        print("  -", ex[:160])
