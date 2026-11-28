# -*- coding: utf-8 -*-
"""§250 full-scope scan: all tracked files incl. .py ; locate hits without echoing raw text."""
import hashlib, io, json, os, re, subprocess

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
os.chdir(REPO)
GTJSON = r"results/app/app155_desens_ground_truth.json"

def norm(s):
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\u4e00-\u9fff]", "", s)
    return s.strip()

def sentences(t):
    out = []
    for line in t.splitlines():
        line = line.strip()
        if line:
            out.append(line)
    return out

def build_gt(gt):
    sents = set()
    for rel in gt["gt_files"]:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        if rel.endswith(".jsonl"):
            for line in t.splitlines():
                try: o = json.loads(line)
                except Exception: continue
                for k in ("text", "tgt", "src", "zh", "en"):
                    if isinstance(o.get(k), str): sents.add(norm(o[k]))
            continue
        for s in sentences(t): sents.add(norm(s))
    return {s for s in sents if len(s) >= gt["min_len"]}

def norm_map(t):
    """normalized char stream + index map back to original offsets"""
    out = []; idx = []
    for i, ch in enumerate(t):
        c = ch.lower()
        if c.isspace():
            c = " "
        if re.match(r"[^\w\s\u4e00-\u9fff]", c):
            continue
        if c == " ":
            if out and out[-1] == " ": continue
        out.append(c); idx.append(i)
    return "".join(out), idx

def find_spans(text, sents):
    """return list of (orig_start, orig_end, sent) for each GT sentence found"""
    n, idx = norm_map(text)
    spans = []
    for s in sorted(sents, key=len, reverse=True):
        if not s: continue
        pos = n.find(s)
        while pos != -1:
            a, b = idx[pos], idx[pos + len(s) - 1] + 1
            spans.append((a, b, s))
            pos = n.find(s, pos + 1)
    # merge overlapping
    spans.sort(key=lambda x: (x[0], -x[1]))
    merged = []
    for a, b, s in spans:
        if merged and a < merged[-1][1]:
            if b > merged[-1][1]:
                merged[-1] = (merged[-1][0], b, merged[-1][2])
            continue
        merged.append((a, b, s))
    return merged

def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    sents = build_gt(gt)
    print("GT sentences (len>=%d): %d" % (gt["min_len"], len(sents)))
    tracked = [x for x in subprocess.run(["git","-C",REPO,"ls-files"],capture_output=True,
                text=True,encoding="utf-8",errors="replace").stdout.splitlines() if x.strip()]
    gtset = {r.replace("/", os.sep) for r in gt["gt_files"]}
    reviewer_owned = {r.replace("/", os.sep) for r in gt.get("reviewer_owned", [])}
    SKIP_SUFFIX = (".transcript.txt", ".mt.txt", ".tts.jsonl")
    hits = {}
    for rel in tracked:
        p = rel.replace("/", os.sep)
        if p in gtset or p in reviewer_owned: continue
        if rel.endswith(SKIP_SUFFIX): continue
        if not os.path.isfile(p): continue
        try: txt = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        except Exception: continue
        if not txt.strip(): continue
        sp = find_spans(txt, sents)
        if sp: hits[rel] = sp
    print("tracked files with GT hits (ALL ext, .py included): %d" % len(hits))
    for rel in sorted(hits):
        sp = hits[rel]
        ext = os.path.splitext(rel)[1].lower()
        print("  %-72s %-6s n_spans=%d" % (rel, ext, len(sp)))
    json.dump({k: [[a, b, hashlib.sha256(s.encode()).hexdigest()[:8]] for a, b, s in v]
               for k, v in hits.items()}, open(".tmp_recover_app/_app250_hits.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print()
    print("=== .py hits: locate line numbers + context shape (raw replaced by <HIT>) ===")
    for rel in sorted(hits):
        if not rel.endswith(".py"): continue
        txt = io.open(rel.replace("/", os.sep), encoding="utf-8", errors="replace", newline="").read()
        lines = txt.split("\n")
        offs = []; pos = 0
        for i, ln in enumerate(lines):
            offs.append((pos, pos + len(ln))); pos += len(ln) + 1
        for a, b, s in hits[rel]:
            ln_i = None
            for i, (lo, hi) in enumerate(offs):
                if lo <= a < hi + 1: ln_i = i; break
            shown = lines[ln_i]
            for x in re.finditer(r"[A-Za-z_]{3,}", shown):
                pass
            # replace the matched sentence region with <HIT> marker (approx: replace longest CJK/latin run)
            masked = re.sub(r"[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z ,.!?;:'\"\-–—…]{6,}", "<HIT>", shown)
            print("  %s:%d  spans=%d  %s" % (rel, (ln_i or 0) + 1, len(hits[rel]), masked.strip()[:150]))

    print()
    print("=== sent-body segments vs GT (are the redacted segments meeting sentences?) ===")
    blob = subprocess.run(["git","show","f44c878:results/app/_app249_status_email_body.txt"],
                          capture_output=True).stdout.decode("utf-8")
    disk = open("results/app/_app249_status_email_body.txt", encoding="utf-8").read()
    import difflib
    sm = difflib.SequenceMatcher(None, blob, disk, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal": continue
        seg = blob[i1:i2]
        print("  %-8s sent_len=%3d sent_sha8=%s  in_GT=%s  disk_repl=%r" % (
            tag, len(seg), hashlib.sha256(seg.encode()).hexdigest()[:8],
            bool(seg.strip()) and norm(seg) in sents, disk[j1:j2][:24]))

if __name__ == "__main__":
    main()
