# -*- coding: utf-8 -*-
"""§250 判定：把 §250 死会话扫描出的 54 个命中逐个分类，回答三个问题：

Q1 命中是否落在 **reviewer 权威基线**（GT['hits'] 的 text 集合）里？
   ⇒ 是 ⇒ 真残留，必须脱敏
Q2 命中是否只是基线句的 **子串/变体**？
   ⇒ 是 ⇒ 真残留（片段）
Q3 命中是否来自 **重建 GT**（从 gt_files 抽出的全部句），而不在基线里？
   ⇒ 需要逐个看：可能是 (a) 基线没记到的真会议句 (b) 重建过程造出来的假句
   （例如把 JSON 字段值 / 译文 / 占位符当成了句子）

🔴 RULES §0：只输出 len + sha256 前 8 位 + 分类，不打印原句。
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
OUT = os.path.join(REPO, "results", "app", "app250_classify.json")


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


def norm(s):
    return norm_map(s)[0]


def build_rebuilt_gt(gt):
    """死会话口径：jsonl 取 text/tgt/src/zh/en；其余按整行。"""
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
        for line in t.splitlines():
            if line.strip():
                sents.add(norm(line.strip()))
    return {s for s in sents if len(s) >= gt["min_len"]}


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    base_texts = set()
    for rel, lst in gt["hits"].items():
        for h in lst:
            t = (h.get("text") or "").strip()
            if t:
                base_texts.add(t)
    base_norm = {norm(t) for t in base_texts}
    rebuilt = build_rebuilt_gt(gt)
    print("基线原句（去重）:", len(base_texts), " 归一化后:", len(base_norm))
    print("重建 GT 句:", len(rebuilt))
    only_rebuilt = rebuilt - base_norm
    print("仅在重建 GT 里（不在基线）:", len(only_rebuilt))

    dead = json.load(open(HITS, encoding="utf-8"))
    print("死会话命中文件:", len(dead))

    # 分类每个命中：命中句本身属于哪一类
    cls = {}
    detail = {}
    for rel, spans in dead.items():
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            cls[rel] = "FILE_MISSING"
            continue
        txt = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        n, idx = norm_map(txt)
        cats = []
        for a, b, s8 in spans:
            # 反查该 span 对应的归一化句（重建时存的是 sha8[:8]）
            cands = [x for x in rebuilt if sha8(x) == s8]
            if not cands:
                cats.append("unknown")
                continue
            s = cands[0]
            if s in base_norm:
                cats.append("Q1_基线整句")
            elif any(s in b2 or b2 in s for b2 in base_norm):
                cats.append("Q2_基线子串或变体")
            else:
                cats.append("Q3_仅重建GT")
        cats = sorted(set(cats))
        cls[rel] = "|".join(cats)
        detail[rel] = cats

    from collections import Counter
    print()
    print("=== 按文件分类统计 ===")
    for k, v in sorted(Counter(cls.values()).items(), key=lambda x: -x[1]):
        print("  %-30s %d" % (k, v))
    print()
    q3only = [r for r, c in cls.items() if c == "Q3_仅重建GT"]
    q12 = [r for r, c in cls.items() if "Q1" in c or "Q2" in c]
    print("Q1/Q2（真残留候选）%d 个文件:" % len(q12))
    for r in sorted(q12):
        print("   ", r)
    print()
    print("Q3 only（仅重建 GT，需人工判定）%d 个文件:" % len(q3only))
    for r in sorted(q3only):
        print("   ", r)

    # Q3 的句子到底是什么形状？（只写 len/sha8/字符类别，不写原文）
    print()
    print("=== Q3 命中句的形状（不写原文）===")
    shapes = {}
    for rel in q3only:
        for s in only_rebuilt:
            pass
    # 逐文件列出 Q3 句子的属性
    q3_info = {}
    for rel in q3only:
        spans = dead[rel]
        p = os.path.join(REPO, rel.replace("/", os.sep))
        txt = io.open(p, encoding="utf-8", errors="replace", newline="").read()
        n, idx = norm_map(txt)
        info = []
        for a, b, s8 in spans:
            cands = [x for x in rebuilt if sha8(x) == s8]
            s = cands[0] if cands else ""
            info.append({
                "sha8": s8, "len": len(s),
                "has_cjk": bool(re.search(r"[\u4e00-\u9fff]", s)),
                "has_ascii": bool(re.search(r"[a-zA-Z]", s)),
                "n_words": len(s.split()),
                "is_placeholder": bool(re.match(r"^会议句 idx \d+$", s)),
                "has_bracket": ("[" in s or "]" in s),
            })
        q3_info[rel] = info

    out = {"script": "_app250_classify.py",
           "n_base_texts": len(base_texts), "n_base_norm": len(base_norm),
           "n_rebuilt": len(rebuilt), "n_only_rebuilt": len(only_rebuilt),
           "classify": cls, "q3_info": q3_info,
           "n_q1q2_files": len(q12), "n_q3only_files": len(q3only)}
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print("\n写出:", OUT)


if __name__ == "__main__":
    main()
