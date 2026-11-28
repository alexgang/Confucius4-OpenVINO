# -*- coding: utf-8 -*-
"""§250 命中来源溯源：reviewer 权威基线是否**亲自点名**过这些文件/行。

判据（§250 decide.py 的口径，独立复算）：
  * ``in_base_text`` —— 命中的**句** ∈ reviewer 85 条基线原句
  * ``in_base_line`` —— 命中的 **(文件, 行)** 被 reviewer 亲自记过
  ⇒ 只有「reviewer 点名过 (文件,行)」的才是**必须脱敏**的硬要求；
    仅仅「句在基线里」而「位置 reviewer 没记过」的 ⇒ 属**扩散**，
    要按上下文性质（docstring/comment/功能字面量）逐处判定。

🔴 RULES §0：不输出原句，只输出 len + sha8 + 文件 + 行。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
FULLSCAN = os.path.join(REPO, "results", "app", "app250_fullscan.json")
OUT = os.path.join(REPO, "results", "app", "app250_provenance.json")


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def canon(s: str) -> str:
    """大小写折叠 + 空白折叠（§250 verify_baseline 口径）。"""
    return re.sub(r"[\s　]+", " ", s.strip()).casefold()


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    fs = json.load(open(FULLSCAN, encoding="utf-8"))
    hits = gt["hits"]

    # reviewer 基线：句 → [(file,line,kind)]
    base_by_sha = {}
    base_lines = set()
    for rel, lst in hits.items():
        for e in lst:
            t = (e.get("text") or "").strip()
            if not t:
                continue
            c = canon(t)
            base_by_sha.setdefault(sha8(c), []).append(
                (rel, e.get("line"), len(t), e.get("kind")))
            base_lines.add((rel, e.get("line")))

    rows = []
    for r in sorted(fs["rows"], key=lambda x: x["file"]):
        if r["kind"] == "gt_source":
            continue
        rel = r["file"]
        for h in r["hits"]:
            s8 = h["sha8"]
            recs = base_by_sha.get(s8, [])
            rows.append({
                "file": rel,
                "line": h["line"],
                "kind": r["kind"],
                "ctx": h["ctx"],
                "len": h["len"],
                "sha8": s8,
                "reviewer_pointed_file": any(x[0] == rel for x in recs),
                "reviewer_pointed_line": (rel, h["line"]) in base_lines,
                "reviewer_records_n": len(recs),
                "reviewer_record_sites": [
                    {"file": x[0], "line": x[1], "len": x[2], "kind": x[3]}
                    for x in recs[:4]],
            })

    print("=== 逐处溯源 ===")
    n_pointed = sum(1 for r in rows if r["reviewer_pointed_line"])
    n_pointed_file = sum(1 for r in rows if r["reviewer_pointed_file"])
    print("命中总数 %d ／ reviewer 点名(文件,行) %d ／ reviewer 点名文件 %d"
          % (len(rows), n_pointed, n_pointed_file))
    print()
    for r in rows:
        flag = ("🔴点名(文件,行)" if r["reviewer_pointed_line"]
                else ("🟡点名文件,未点名行" if r["reviewer_pointed_file"]
                      else "⚪ reviewer 未点名该位置"))
        print("  %-58s L%-5s ctx=%-14s len=%-3d sha8=%-10s %s"
              % (r["file"][:58], r["line"], r["ctx"], r["len"], r["sha8"], flag))
        for s in r["reviewer_record_sites"][:3]:
            print("        reviewer 记: %s L%s len=%s kind=%s"
                  % (s["file"][:56], s["line"], s["len"], s["kind"]))

    out = {"script": "app250_provenance.py",
           "n_hits": len(rows),
           "n_reviewer_pointed_line": n_pointed,
           "n_reviewer_pointed_file": n_pointed_file,
           "rows": rows}
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print("\n写出:", OUT)


if __name__ == "__main__":
    main()
