# -*- coding: utf-8 -*-
"""§250 关键判定（只读诊断，不改任何文件）。

D1. GT 源文件（39 个，含原始会议句）现在是否仍在仓库里被跟踪？
    ⇒ 若在 ⇒ 推 GitHub 会把会议原句带走（APP-155/156 §3 的真实风险面）
D2. §249 的 apply 到底改了哪些 .tts.jsonl / .mt.txt？
D3. 死会话那 54 个命中的**原样片段形状**（字母→x，不泄露内容）
D4. results/app/_app330_write_status167.py 的命中是什么（基线短语命中）
D5. .gitignore 是否覆盖这些
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
HITS = os.path.join(REPO, ".tmp_recover_app", "_app250_hits.json")


def git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm_map(t):
    out, idx = [], []
    for i, ch in enumerate(t):
        c = ch.lower()
        if c.isspace():
            c = " "
        if re.match(r"[^\w\s\u4e00-\u9fff]", c):
            continue
        if c == " ":
            if out and out[-1] == " ":
                continue
        out.append(c)
        idx.append(i)
    return "".join(out), idx


def shape(s):
    """只留结构：字母/汉字→x，数字→d，其余保留。"""
    o = []
    for ch in s:
        if ch.isalpha() or "\u4e00" <= ch <= "\u9fff":
            o.append("x")
        elif ch.isdigit():
            o.append("d")
        else:
            o.append(ch)
    return "".join(o)


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    gtset = set(gt["gt_files"])
    tracked = set(x for x in git("ls-files").splitlines() if x.strip())

    print("=== D1. GT 源文件是否被 git 跟踪 ===")
    n_tracked = sum(1 for g in gtset if g in tracked)
    print("GT 源文件 %d 个，其中被跟踪 %d 个" % (len(gtset), n_tracked))
    for g in sorted(gtset):
        if g in tracked:
            print("   TRACKED  ", g)
    untracked = sorted(g for g in gtset if g not in tracked)
    print("未跟踪 %d 个:" % len(untracked))
    for g in untracked:
        print("   untracked", g)

    print()
    print("=== D1b. GT json 本身是否被跟踪（它含 85 条原句全文！）===")
    print("   app155_desens_ground_truth.json tracked =",
          "results/app/app155_desens_ground_truth.json" in tracked)
    print("   app249_desen_*.json tracked:",
          {f: (f in tracked) for f in [
              "results/app/app249_desen_scan_full.json",
              "results/app/app249_desen_apply_full.json",
              "results/app/app249_desen_final_verify.json",
              "results/app/app249_desen_skeleton_verify.json"]})

    print()
    print("=== D2. §249 apply 改动的 .tts.jsonl / .mt.txt / .transcript.txt ===")
    ap = json.load(open(os.path.join(REPO, "results", "app",
                                     "app249_desen_apply_full.json"), encoding="utf-8"))
    suf = [c["file"] for c in ap["changed"]
           if c["file"].endswith((".tts.jsonl", ".mt.txt", ".transcript.txt"))]
    print("共 %d 个:" % len(suf))
    for f in suf:
        print("   ", f, "  (GT源=%s)" % (f in gtset))

    print()
    print("=== D3. 死会话 54 个命中的片段形状（字母→x）===")
    dead = json.load(open(HITS, encoding="utf-8"))
    seen = {}
    for rel in sorted(dead):
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        txt = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        for a, b, s8 in dead[rel]:
            raw = txt[a:b]
            sh = shape(raw)
            seen.setdefault(sh, []).append(rel)
    print("不同形状数:", len(seen))
    for sh, files in sorted(seen.items(), key=lambda x: -len(x[1]))[:14]:
        print("   %-40s  n_files=%-3d eg=%s" % (sh[:40], len(files), files[0][:52]))

    print()
    print("=== D4. results/app/_app330_write_status167.py 的基线命中 ===")
    p = os.path.join(REPO, "results", "app", "_app330_write_status167.py")
    txt = io.open(p, encoding="utf-8", errors="replace", newline="").read()
    base_texts = set()
    for rel, lst in gt["hits"].items():
        for h in lst:
            t = (h.get("text") or "").strip()
            if t:
                base_texts.add(t)
    for t in sorted(base_texts, key=len, reverse=True):
        c = re.sub(r"[\s\u3000]+", " ", t.strip()).casefold()
        if c and c in re.sub(r"[\s\u3000]+", " ", txt).casefold():
            print("   命中基线短语 len=%d sha8=%s  文件行数=%d"
                  % (len(t), sha8(c), txt.count("\n") + 1))
            for i, line in enumerate(txt.split("\n"), 1):
                if c in re.sub(r"[\s\u3000]+", " ", line).casefold():
                    print("      L%d: %s" % (i, shape(line)[:120]))
            break

    print()
    print("=== D5. .gitignore 覆盖 ===")
    for probe in ["results/app/app415_rc6_langs/ja/tts.jsonl",
                  "results/app/app155_desens_ground_truth.json",
                  "results/app/app155_desens_ground_truth.json",
                  "results/app/app249_desen_scan_full.json"]:
        r = subprocess.run(["git", "-C", REPO, "check-ignore", "-v", probe],
                           capture_output=True, text=True, errors="replace").stdout.strip()
        print("   %-52s -> %s" % (probe, r if r else "NOT-IGNORED"))

    # 统计：仓库里当前还有多少 tracked 文件含**基线短语**（权威口径）
    print()
    print("=== D6. 权威口径全库扫描（基线 85 条原句，2892 个 tracked 文件）===")
    ph = [re.sub(r"[\s\u3000]+", " ", t.strip()).casefold() for t in base_texts]
    ph = [x for x in ph if len(x) >= 6]
    hit_files = {}
    for rel in tracked:
        if rel in set(gt.get("reviewer_owned", [])):
            continue
        f = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(f):
            continue
        try:
            t = io.open(f, encoding="utf-8", errors="replace", newline="").read()
        except Exception:
            continue
        if not t:
            continue
        flat = re.sub(r"[\s\u3000]+", " ", t).casefold()
        n = sum(1 for c in ph if c in flat)
        if n:
            hit_files[rel] = n
    print("命中 tracked 文件: %d" % len(hit_files))
    for rel in sorted(hit_files):
        tag = "GT-SOURCE" if rel in gtset else ("OTHER" )
        print("   %-8s %-64s %d" % (tag, rel[:64], hit_files[rel]))


if __name__ == "__main__":
    main()
