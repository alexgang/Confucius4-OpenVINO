# -*- coding: utf-8 -*-
"""§250 前置核验：确认「我重算的 idx_map」与 §249 已经写进仓库的占位编号**完全一致**。

方法（与 §249 apply 逐字同口径）：
  sents = build_gt(gt)          # 与 _app249_desen_apply_full.py 一致
  idx_map = {s: i+1 for i,s in enumerate(sorted(sents))}

验证：
  1. 现有已脱敏文件里的占位编号（如 app024 的 idx 54 / app121 的 idx 55/54）
     ⇒ 还原后应等于对应 GT 句（**不改文件**，只在内存里核）。
  2. 本轮要处理的 6 个 sha8 ⇒ 各自的 idx 编号。

🔴 RULES §0：只输出 idx 编号、len、sha8；不输出原句。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")
PLACEHOLDER = re.compile(r"\[会议句 idx (\d+)\]")


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s):
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def build_gt(gt):
    """与 §249 apply 的 build_gt 逐字同口径（_app249_desen_apply_full.py L110-130）。"""
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
        for s in re.split(r"[。！？\n]+|(?<=[.!?])\s+", t):
            if s and s.strip():
                sents.add(norm(s.strip()))
    return {s for s in sents if len(s) >= gt["min_len"]}


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    sents = build_gt(gt)
    idx_map = {s: i + 1 for i, s in enumerate(sorted(sents))}
    inv = {i: s for s, i in idx_map.items()}
    print("GT 句 %d 条 / idx_map %d 条（与 §249 同口径）" % (len(sents), len(idx_map)))

    # ── 验证 1：仓库里已有的占位编号能否对上 GT 句 ───────────────
    print()
    print("=== 验证：已入库文件的占位编号 → GT 句（sha8 核对）===")
    checks = [
        ("results/app/app024_seam_guard_design.json", 54),
        ("results/app/app024_seam_rule_design.json", 54),
        ("results/app/app024_stopword_audit.json", 54),
        ("results/app/app121_asr_app_3mat_GPU0.json", 55),
        ("results/app/app121_asr_app_3mat_GPU0.json", 54),
        ("README.md", 55),
    ]
    for rel, want in checks:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            print("  [跳过] %s" % rel)
            continue
        t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        n = len(PLACEHOLDER.findall(t))
        s = inv.get(want)
        print("  %-52s idx=%-4d 出现 %d 次  → GT 句 len=%-3d sha8=%s"
              % (rel[:52], want, n, len(s) if s else -1, sha8(s) if s else "-"))

    # ── 验证 2：本轮 6 个 sha8 的 idx 编号 ────────────────────────
    print()
    print("=== 本轮 6 个 sha8 → idx 编号 ===")
    want_sha = ["fd8e8b5c", "301202c0", "5e708d46", "cdf71dea",
                "9e9eab7d", "9726b63b"]
    by_sha = {}
    for s, i in idx_map.items():
        by_sha.setdefault(sha8(s), []).append((i, len(s)))
    for w in want_sha:
        got = by_sha.get(w)
        print("  sha8=%s → %s" % (w, got if got else "NOT-IN-GT"))

    out = {"script": "_app250_idxmap.py", "n_gt": len(sents),
           "n_idx": len(idx_map),
           "sha8_to_idx": {w: by_sha.get(w) for w in want_sha}}
    dst = os.path.join(REPO, "results", "app", "app250_idxmap.json")
    tmp = dst + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    print("\n写出:", dst)


if __name__ == "__main__":
    main()
