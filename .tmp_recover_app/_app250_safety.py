# -*- coding: utf-8 -*-
"""§250 安全分析：判定 .py 命中的**可脱敏性**。

对每个 .py 命中行输出（会议句已掩码，只留代码结构）：
  - 该行本身（掩码）
  - 上下各 3 行（掩码）
  - 该命中是「文档用途」还是「功能性比较」

功能性比较（assert / == 比较）：替换字面量会让断言失配 ⇒ 需特殊处理。
🔴 RULES §0：不输出原句。
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


def mask_line(line, sents):
    """把行内所有 GT 句（含其片段）替换成 <HIT>，保留代码结构。"""
    out = line
    for s in sorted(sents, key=len, reverse=True):
        # 用归一化后的原样大小写找（大小写不敏感）
        pat = re.compile(re.escape(s), re.IGNORECASE)
        out = pat.sub("<HIT>", out)
    return out


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    sents = build_gt(gt)
    pygap = json.load(open(os.path.join(REPO, "results", "app",
                                       "app250_pygap.json"), encoding="utf-8"))
    gtset = set(gt["gt_files"])
    files = [r for r in pygap["hits"]
             if r not in gtset and os.path.splitext(r)[1].lower() == ".py"]
    print("待分析 .py 文件:", len(files))
    for rel in files:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        lines = t.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        print("\n" + "=" * 100)
        print("FILE", rel)
        for h in pygap["hits"][rel]:
            i = h["line"] - 1
            print("  --- L%d  ctx=%s  gt_sha8=%s len=%d" % (h["line"], h["ctx"],
                                                           h["gt_sha8"], h["gt_len"]))
            lo, hi = max(0, i - 3), min(len(lines), i + 4)
            for j in range(lo, hi):
                mark = ">>" if j == i else "  "
                print("   %s L%-5d %s" % (mark, j + 1, mask_line(lines[j], sents)[:150]))


if __name__ == "__main__":
    main()
