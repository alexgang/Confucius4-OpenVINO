# -*- coding: utf-8 -*-
"""§250 决定性判定：12 个「§249 范围外」命中，逐处分类。

判据（用 reviewer 自己的权威记录，不重建 GT）：
  * `base_texts` = GT['hits'] 里 reviewer 记下的 **原句全文**（85 条）
  * `base_lines` = reviewer 记下的 **(文件, 行号)** 对

对每一处命中回答：
  Q-a 该命中所在 **(文件, 行)** 是否被 reviewer 亲自记过？
  Q-b 命中的原句是否属于 reviewer 的 85 条基线原句？
  Q-c 命中句长度（短句 = §249 自己文档里点名的「会误伤」的通用短语）

分类：
  R1 = reviewer 点名过的 (文件,行) ⇒ **必须脱敏**
  R2 = 命中句 ∈ reviewer 85 条基线原句 ⇒ **必须脱敏**
  R3 = 仅「重建 GT」口径命中（不在基线原句里）⇒ **通用短语/散文 ⇒ 不动**
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
PYGAP = os.path.join(REPO, "results", "app", "app250_pygap.json")

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s):
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


def build_gt_249(gt):
    """§249 自己的 build_gt（与 _app249_verify_desen_final.py 逐字同口径）。"""
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
    gap = json.load(open(PYGAP, encoding="utf-8"))
    sents = build_gt_249(gt)

    base_texts = set()
    base_lines = set()
    for rel, lst in gt["hits"].items():
        for h in lst:
            t = (h.get("text") or "").strip()
            if t:
                base_texts.add(t)
            base_lines.add((rel, h.get("line")))
    base_norm = {norm(t) for t in base_texts}
    print("reviewer 基线：原句 %d 条 / (文件,行) 记录 %d 条"
          % (len(base_texts), len(base_lines)))

    print()
    print("=== 逐处分类（12 个 §249 范围外文件）===")
    rows = []
    for rel in sorted(gap["hits"]):
        for h in gap["hits"][rel]:
            gtsha = h["gt_sha8"]
            cand = [s for s in sents if sha8(s) == gtsha]
            s = cand[0] if cand else ""
            in_base_text = (s in base_norm) if s else False
            in_base_line = (rel, h["line"]) in base_lines
            short = h["gt_len"] < 25
            if in_base_line or in_base_text:
                cls = "R2_必须脱敏"
            else:
                cls = "R3_不动(通用短语)"
            rows.append((rel, h["line"], h["ctx"], h["gt_len"], gtsha,
                         in_base_text, in_base_line, cls, short))
            print("  %-58s L%-5d %-15s len=%-3d %s base_text=%-5s base_line=%-5s => %s"
                  % (rel[:58], h["line"], h["ctx"], h["gt_len"], gtsha,
                     in_base_text, in_base_line, cls))

    must = [r for r in rows if r[7].startswith("R2")]
    dont = [r for r in rows if r[7].startswith("R3")]
    print()
    print("必须脱敏 %d 处（%d 个文件）: %s"
          % (len(must), len({r[0] for r in must}),
             sorted({r[0] for r in must})))
    print("不脱敏 %d 处（%d 个文件）: %s"
          % (len(dont), len({r[0] for r in dont}),
             sorted({r[0] for r in dont})))

    # 每个「必须脱敏」文件里，是否**所有**命中都要脱敏？
    print()
    print("=== 逐文件：必须脱敏的文件里有没有 R3 混在同一文件 ===")
    for rel in sorted({r[0] for r in must}):
        sub = [r for r in rows if r[0] == rel]
        r3 = [r for r in sub if r[7].startswith("R3")]
        print("  %-58s  R2=%d R3=%d" % (rel[:58], len(sub) - len(r3), len(r3)))

    out = {"script": "_app250_decide.py",
           "n_base_texts": len(base_texts), "n_base_lines": len(base_lines),
           "rows": [{"file": r[0], "line": r[1], "ctx": r[2], "gt_len": r[3],
                     "gt_sha8": r[4], "in_base_text": r[5], "in_base_line": r[6],
                     "cls": r[7], "short": r[8]} for r in rows]}
    dst = os.path.join(REPO, "results", "app", "app250_decide.json")
    tmp = dst + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, dst)
    print("\n写出:", dst)


if __name__ == "__main__":
    main()
