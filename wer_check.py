"""Compute WER of OV transcripts vs MiniMax baseline (word-level, lowercase, strip punct)."""
import re, sys, json

REP = "reports"

def words_from_minimax(path):
    ws = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[[\d.\-]+\]\s*(.*)$", line)
        if not m:
            continue
        w = m.group(1).strip()
        if w:
            ws.append(w)
    return ws

def words_from_seg_transcript(path):
    ws = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^\[\s*[\d.\-]+\s*-\s*[\d.]+\]\s*(.*)$", line)
        if m:
            line = m.group(1)
        ws.extend(w for w in line.split() if w)
    return ws

def norm(ws):
    out = []
    for w in ws:
        w = w.lower()
        w = re.sub(r"[^\w']", "", w)  # strip punctuation except apostrophe
        w = w.replace("'", "")
        if w:
            out.append(w)
    return out

def wer(ref, hyp):
    n, m = len(ref), len(hyp)
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]

def report(name, path, ref):
    hyp = norm(words_from_seg_transcript(path))
    d = wer(ref, hyp)
    print(f"{name:42s} words={len(hyp):6d} edit={d:5d} WER={100.0*d/len(ref):6.2f}%")
    return hyp, d

if __name__ == "__main__":
    ref = norm(words_from_minimax(f"{REP}/c026_minimax_transcript.txt"))
    print(f"MiniMax baseline words={len(ref)}")
    print("-" * 80)
    for name, path in [
        ("OV streaming v1 (broken cache)", f"{REP}/spe_61min_transcript.txt"),
        ("OV streaming noreset (cache fixed)", f"{REP}/spe_61min_transcript_noreset.txt"),
        ("OV streaming reset-only", f"{REP}/spe_61min_transcript_v1_ov_streaming.txt"),
        ("Hybrid offline (torch enc + OV dec)", f"{REP}/spe_hybrid_offline.txt"),
        ("OV offline (window enc + OV dec)", f"{REP}/spe_ov_offline.txt"),
    ]:
        try:
            report(name, path, ref)
        except FileNotFoundError:
            print(f"{name:42s} FILE NOT FOUND")
