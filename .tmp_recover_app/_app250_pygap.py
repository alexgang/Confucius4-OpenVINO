# -*- coding: utf-8 -*-
"""§250 定位：.py 缺口 + status/ 缺口（APP-155 要求 status/ 全模块在扫描范围）。

对每个命中给出：
  文件、行号、命中句 sha8/len、**所在上下文类型**（注释 / docstring / 字符串字面量 / 代码）、
  是否是「功能性字符串」（例如断言右侧、比较左值）——决定能不能安全脱敏。

🔴 RULES §0：只输出 sha8/len/上下文类型，不输出原句。
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

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s):
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def build_gt(gt):
    sents = set()
    for rel in gt["gt_files"]:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        if rel.endswith(".jsonl"):
            for line in t.splitlines():
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                for k in ("text", "tgt", "src", "zh", "en"):
                    if isinstance(o.get(k), str):
                        sents.add(norm(o[k]))
            continue
        for p2 in re.split(r"[。！？\n]+|(?<=[.!?])\s+", t):
            if p2 and p2.strip():
                sents.add(norm(p2.strip()))
    return {s for s in sents if len(s) >= gt["min_len"]}


def ctx_kind(lines, i):
    """粗判该行属于哪类上下文。"""
    line = lines[i]
    st = line.strip()
    if st.startswith("#"):
        return "comment"
    if st.startswith(('"""', "'''")):
        return "docstring"
    # 该行前面是否处于 docstring 内
    pre = "\n".join(lines[:i])
    if pre.count('"""') % 2 == 1 or pre.count("'''") % 2 == 1:
        return "docstring-inner"
    if re.search(r'["\']\s*[,)\]]?\s*(#.*)?$', st) and ("=" in st or ":" in st):
        return "string-literal"
    if st.startswith(('"', "'")) or re.search(r'==\s*["\']', st) or re.search(r'["\']\s*==', st):
        return "assert-compare"
    return "code/other"


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    sents = build_gt(gt)
    by_sha = {}
    for s in sents:
        by_sha.setdefault(sha8(s), s)
    gtset = set(gt["gt_files"])

    # 复现 §249 的 §1 扫描范围（6 个扩展）vs 全范围
    TEXT_EXT = (".md", ".json", ".txt", ".tsv", ".csv", ".jsonl")
    tracked = [x for x in subprocess.run(["git", "-C", REPO, "ls-files"],
                                         capture_output=True, text=True,
                                         encoding="utf-8", errors="replace"
                                         ).stdout.splitlines() if x.strip()]
    reviewer_owned = set(gt.get("reviewer_owned", []))

    results = {}
    for rel in tracked:
        if rel in reviewer_owned or rel in gtset:
            continue
        ext = os.path.splitext(rel)[1].lower()
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        except Exception:
            continue
        if not t.strip():
            continue
        lines = t.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        hits = []
        for i, line in enumerate(lines):
            n = norm(line)
            if len(n) < gt["min_len"]:
                continue
            matched = [s for s in sents if s and s in n]
            if not matched:
                continue
            longest = max(matched, key=len)
            hits.append({"line": i + 1, "n_gt": len(matched),
                         "gt_len": len(longest), "gt_sha8": sha8(longest),
                         "ctx": ctx_kind(lines, i),
                         "ext": ext,
                         "in_249_scope": ext in TEXT_EXT})
        if hits:
            results[rel] = hits

    print("=== 全范围（所有扩展，含 .py）命中文件:", len(results))
    n_in = sum(1 for r in results.values() if any(h["in_249_scope"] for h in r))
    print("其中 §249 的 §1 扫描范围能覆盖的:", n_in)
    n_out = len(results) - n_in
    print("⇒ §249 范围外（.py 等）漏掉的:", n_out)
    print()
    print("=== §249 范围外的命中文件明细 ===")
    for rel in sorted(results):
        out = [h for h in results[rel] if not h["in_249_scope"]]
        if not out:
            continue
        print("%-62s %s" % (rel[:62], os.path.splitext(rel)[1]))
        for h in out:
            print("      L%-5d ctx=%-16s gt_len=%-4d gt_sha8=%s n_gt=%d"
                  % (h["line"], h["ctx"], h["gt_len"], h["gt_sha8"], h["n_gt"]))

    print()
    print("=== 上下文类型汇总（范围外）===")
    from collections import Counter
    c = Counter()
    for rel, hs in results.items():
        for h in hs:
            if not h["in_249_scope"]:
                c[(os.path.splitext(rel)[1], h["ctx"])] += 1
    for k, v in sorted(c.items(), key=lambda x: -x[1]):
        print("   %-10s %-18s %d" % (k[0], k[1], v))

    out = {"script": "_app250_pygap.py",
           "n_files_all_ext": len(results),
           "n_files_in_249_scope": n_in,
           "n_files_outside_249_scope": n_out,
           "hits": results}
    dst = os.path.join(REPO, "results", "app", "app250_pygap.json")
    tmp = dst + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    print("\n写出:", dst)


if __name__ == "__main__":
    main()
