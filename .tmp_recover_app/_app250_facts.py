# -*- coding: utf-8 -*-
"""§250 facts: (1) sent-body vs archived-body delta; (2) GT hits in tracked files;
(3) tracked-status of pending producers; (4) .gitignore coverage."""
import hashlib, io, json, os, re, subprocess, sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
os.chdir(REPO)

def sha(b): return hashlib.sha256(b).hexdigest()

def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True).stdout.decode("utf-8", "replace")

print("=== 1. email body: sent-record vs on-disk ===")
sent = json.load(open("results/app/app249_status_email_sent.json", encoding="utf-8"))
print("record body_sha256:", sent.get("body_sha256"), "bytes:", sent.get("body_bytes"))
on_disk = open("results/app/_app249_status_email_body.txt", "rb").read()
print("on-disk sha:", sha(on_disk), "bytes:", len(on_disk))
# committed blob
blob = subprocess.run(["git", "show", "f44c878:results/app/_app249_status_email_body.txt"],
                      capture_output=True).stdout
print("blob f44c878 sha:", sha(blob), "bytes:", len(blob))
# diff: find placeholder insertions (sent -> on-disk)
s_txt = blob.decode("utf-8"); o_txt = on_disk.decode("utf-8")
ph = re.compile(r"\[会议句 idx \d+\]|<会议原句 len=\d+ sha256=[0-9a-f]{8}>")
import difflib
sm = difflib.SequenceMatcher(None, s_txt, o_txt, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag != "equal":
        seg_s = s_txt[i1:i2]; seg_o = o_txt[j1:j2]
        print("  %-8s sent_len=%d sha8=%s | disk_len=%d sha8=%s" % (
            tag, len(seg_s), sha(seg_s.encode())[:8], len(seg_o), sha(seg_o.encode())[:8]))

print()
print("=== 2. GT hits in tracked files (current reviewer baseline GT) ===")
gt = json.load(open("results/app/app155_desens_ground_truth.json", encoding="utf-8"))

def norm(s):
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s\u4e00-\u9fff]", "", s)
    return s.strip()

def build_gt(gt):
    sents = set()
    for rel in gt["gt_files"]:
        p = rel.replace("/", os.sep)
        if not os.path.exists(p): continue
        try: data = json.load(open(p, encoding="utf-8"))
        except Exception:
            data = None
        if data is None: continue
        items = data if isinstance(data, list) else [data]
        for o in items:
            if not isinstance(o, dict): continue
            for k in ("text", "tgt", "src", "zh", "en"):
                if isinstance(o.get(k), str): sents.add(norm(o[k]))
    return {s for s in sents if len(s) >= gt["min_len"]}

sents = build_gt(gt)
print("GT sentence count:", len(sents))
tracked = git("ls-files").splitlines()
hits = {}
for rel in tracked:
    p = rel.replace("/", os.sep)
    if not os.path.exists(p): continue
    try: txt = open(p, encoding="utf-8").read()
    except Exception: continue
    low = norm(txt)
    n = sum(1 for s in sents if s and s in low)
    if n: hits[rel] = n
print("files with GT hits:", len(hits))
for k in sorted(hits): print("   %-72s %d" % (k, hits[k]))

print()
print("=== 3. tracked-status of §249 producers ===")
for f in ["_app249_desen_apply_full.py", "_app249_desen_scan_full.py", "_app249_desen_analyze.py",
          "_app249_replay_desen.py", "_app249_verify_desen_final.py", "_app249_redact_selfquotes.py",
          "_app249_sync_pkg_to_dev.py", "_app249_append_status.py", "_app249_verify_desen_skeleton.py"]:
    loc = None
    for d in [".tmp_recover_app", "live_caption", "results/app", "."]:
        if os.path.exists(os.path.join(d, f)): loc = os.path.join(d, f).replace("\\", "/"); break
    st = "?" if loc is None else ("TRACKED" if git("ls-files", "--error-unmatch", loc) else "untracked")
    print("   %-40s %-10s %s" % (f, st, loc))

print()
print("=== 4. .gitignore coverage ===")
for probe in ["results/app/app415_rc6_langs/ja/tts.jsonl", "results/app/app155_desens_ground_truth.json",
              "results/app/app326_app097_lang_out/tts.jsonl"]:
    r = subprocess.run(["git", "check-ignore", "-v", probe], capture_output=True).stdout.decode().strip()
    print("   %-52s -> %s" % (probe, r if r else "NOT-IGNORED"))

print()
print("=== 5. dirty state summary ===")
st = git("status", "--porcelain").splitlines()
print("   dirty entries:", len(st))
mods = [l for l in st if l[:2].strip() in ("M", "A", "D", "R") or l[:2] in ("??",)]
from collections import Counter
print("   by code:", dict(Counter(l[:2] for l in st)))
for l in st[:40]: print("   ", l)
