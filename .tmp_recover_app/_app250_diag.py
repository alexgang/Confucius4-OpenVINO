# -*- coding: utf-8 -*-
"""§250 诊断：搞清「54 个命中」到底是什么。

关键问题：§249 的 §1 扫描只扫 .md/.json/.txt/.tsv/.csv/.jsonl（**不含 .py**），
且用「整句相等/包含」判据 ⇒ **句子的残片**（只删了一半的会议句）判不出来。

本脚本：
 1. 重建 GT（口径同 §249：jsonl 取字段，其余按句切）
 2. 对每个命中文件，列出**匹配的归一化句**及其在文件里的**原样片段**（掩码后打印）
 3. 判定：命中的是「完整会议句」还是「会议句的残片」
 4. 检查 GT 源文件本身是否被 §249 改坏（GT 被污染 ⇒ 后面所有判据都不可信）

🔴 RULES §0：只打印掩码 + len + sha8，不打印原句。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
HITS = os.path.join(REPO, ".tmp_recover_app", "_app250_hits.json")

PUNCT_RE = re.compile(r'[,.!?;:"\'`()\[\]{}<>—–…·、，。！？；：「」『』（）]')
WS_RE = re.compile(r"[\s　]+")
PLACEHOLDER = re.compile(r"\[会议句 idx (\d+)\]")


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def norm(s):
    s = s.strip().lower()
    s = WS_RE.sub(" ", s)
    return PUNCT_RE.sub("", s)


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


def mask(s):
    """把疑似会议内容替换成 <HIT>，只留结构。"""
    s = re.sub(r"[A-Za-z一-鿿][A-Za-z0-9 一-鿿,.!?;:'\"\-–—…]{5,}", "<HIT>", s)
    return s


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    sents = build_gt(gt)
    print("GT 句（§249 口径）:", len(sents))
    dead = json.load(open(HITS, encoding="utf-8"))

    # ---------- 1. GT 源文件是否被 §249 改坏 ----------
    print()
    print("=== 1. GT 源文件健康检查（§249 的 apply 动过其中 2 个 .tts.jsonl）===")
    gtset = set(gt["gt_files"])
    apply_rec = json.load(open(os.path.join(REPO, "results", "app",
                                           "app249_desen_apply_full.json"), encoding="utf-8"))
    touched = [c["file"] for c in apply_rec["changed"] if c["file"] in gtset]
    print("§249 改动过的 GT 源文件:", len(touched))
    for f in touched:
        print("   ", f)
    # GT 源文件里现在还有多少「占位符」⇒ 被脱敏过的程度
    for rel in sorted(gtset):
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        nph = len(PLACEHOLDER.findall(t))
        if nph:
            print("   含占位符 %-4d 处: %s" % (nph, rel))

    # ---------- 2. 命中性质：整句 vs 残片 ----------
    print()
    print("=== 2. 命中性质（逐文件取第一个命中）===")
    rows = []
    for rel in sorted(dead):
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        txt = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        n, idx = norm_map(txt)
        spans = dead[rel]
        if not spans:
            continue
        a, b, s8 = spans[0]
        raw = txt[a:b]
        # 该 span 的归一化句是 GT 里的哪一条？
        cand = [s for s in sents if sha8(s) == s8]
        # 判断 raw 是否是 GT 句的「前缀/后缀/中间片段」
        gt_full = None
        for s in sents:
            if s and s in n:
                # 找覆盖该 span 的 GT 句
                pass
        # 直接算：raw 归一化后与哪条 GT 句最接近
        nraw = norm(raw)
        best = None
        for s in sents:
            if nraw and (nraw in s):
                if best is None or len(s) < len(best):
                    best = s
        kind = "UNKNOWN"
        if cand:
            s = cand[0]
            if nraw == s:
                kind = "整句命中"
            elif nraw in s:
                kind = "GT句残片(%d/%d)" % (len(nraw), len(s))
            elif s in nraw:
                kind = "包含整句"
            else:
                kind = "变体"
        rows.append((rel, kind, len(raw), sha8(raw), mask(raw)[:110]))

    from collections import Counter
    print("命中性质分布:")
    for k, v in Counter(r[1].split("(")[0] for r in rows).most_common():
        print("   %-16s %d" % (k, v))
    print()
    print("=== 3. 逐文件明细（掩码）===")
    for rel, kind, ln, s8, mk in rows:
        ext = os.path.splitext(rel)[1]
        print("%-64s %-6s %-14s len=%-4d %s" % (rel[:64], ext, kind, ln, mk))


if __name__ == "__main__":
    main()
