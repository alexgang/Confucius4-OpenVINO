# -*- coding: utf-8 -*-
"""§250 独立复核：用 **reviewer 权威基线** 判定脱敏是否真有残留。

判据（与 §249 的 §1 不同，不依赖其内部信息）：
  A. 基线逐条核销：GT['hits'] 里每条 (file, line, text) —— 权威记录了
     「会议原句在哪个文件的哪一行」。⇒ 直接查当前磁盘该文件该行附近是否仍含该句。
     （大小写不敏感 + 空白折叠，标点保留 ⇒ 精确短语，不会误报）
  B. 全库子串扫描：用 GT['hits'] 里的 text 集合（**不重建 GT**）扫全部 tracked 文件。
  C. 与 §250 死会话扫描结果交叉核对。

🔴 RULES §0：证据只写 len + sha256 前 8 位，不落原句。
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
OUT = os.path.join(REPO, "results", "app", "app250_verify_baseline.json")
HITS = os.path.join(REPO, ".tmp_recover_app", "_app250_hits.json")

WS = re.compile(r"[\s\u3000]+")


def canon(s: str) -> str:
    """大小写折叠 + 空白折叠；标点保留（⇒ 精确短语匹配）。"""
    return WS.sub(" ", s.strip()).casefold()


def sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def tracked_files():
    r = subprocess.run(["git", "-C", REPO, "ls-files"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return [x for x in r.stdout.splitlines() if x.strip()]


def read(rel):
    p = os.path.join(REPO, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        return None
    return io.open(p, encoding="utf-8", errors="replace", newline="").read()


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    hits = gt["hits"]                       # reviewer 权威基线：file -> [{line,text,kind}]
    reviewer_owned = set(gt.get("reviewer_owned", []))
    gt_files = set(gt.get("gt_files", []))

    # ---- 建立基线短语集合（去重、去短句）--------------------------
    phrase_by_sha = {}
    for rel, lst in hits.items():
        for h in lst:
            t = h.get("text") or ""
            if len(t.strip()) < 6:
                continue
            phrase_by_sha.setdefault(sha8(canon(t)), []).append((rel, h.get("line"), t))
    phrases = [v[0][2] for v in phrase_by_sha.values()]
    print("基线短语数（去重）:", len(phrases))
    print("基线文件数:", len(hits))

    tracked = tracked_files()
    print("tracked 文件数:", len(tracked))

    # =================================================================
    # A. 基线逐条核销：原句所在文件当前是否仍含该句
    # =================================================================
    per_file = {}
    for rel, lst in hits.items():
        txt = read(rel)
        if txt is None:
            per_file[rel] = {"exists": False, "n_still": None, "n_base": len(lst)}
            continue
        flat = canon(txt)
        lines = txt.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        still = []
        for h in lst:
            t = h.get("text") or ""
            c = canon(t)
            if not c:
                continue
            if c in flat:
                still.append({"line": h.get("line"), "len": len(t), "sha8": sha8(c),
                              "kind": h.get("kind")})
        per_file[rel] = {"exists": True, "n_still": len(still), "n_base": len(lst),
                         "still": still}

    n_files_residual = sum(1 for v in per_file.values()
                            if v.get("n_still"))
    n_still_total = sum(v.get("n_still") or 0 for v in per_file.values())
    n_base_total = sum(v["n_base"] for v in per_file.values())
    print()
    print("A. 基线核销：%d 个基线文件里，仍含原句的文件 = %d（命中 %d 条 / 基线 %d 条）"
          % (len(hits), n_files_residual, n_still_total, n_base_total))
    for rel in sorted(per_file):
        v = per_file[rel]
        if v.get("n_still"):
            print("   RESID %-62s %d/%d" % (rel, v["n_still"], v["n_base"]))

    # =================================================================
    # B. 全库子串扫描（基线短语，非重建 GT）——查基线之外的扩散
    # =================================================================
    scan_hits = {}
    for rel in tracked:
        if rel in reviewer_owned:
            continue
        txt = read(rel)
        if not txt:
            continue
        flat = canon(txt)
        if len(flat) < 20:
            continue
        f = []
        for c in phrases:
            if c and c in flat:
                f.append({"len": len(c), "sha8": sha8(c)})
        if f:
            scan_hits[rel] = f
    print()
    print("B. 全库扫描（基线短语，扫 %d 个 tracked 文件，不含 reviewer 独占）："
          "命中文件 = %d" % (len(tracked), len(scan_hits)))
    for rel in sorted(scan_hits):
        print("   HIT %-62s %d" % (rel, len(scan_hits[rel])))

    # =================================================================
    # C. 与死会话扫描结果交叉核对
    # =================================================================
    cross = {}
    if os.path.isfile(HITS):
        dead = json.load(open(HITS, encoding="utf-8"))
        cross = {
            "dead_n_files": len(dead),
            "dead_only": sorted(set(dead) - set(scan_hits)),
            "mine_only": sorted(set(scan_hits) - set(dead)),
            "both": len(set(dead) & set(scan_hits)),
        }
        print()
        print("C. 交叉核对：死会话 %d 文件 / 本轮 %d 文件 / 交集 %d"
              % (cross["dead_n_files"], len(scan_hits), cross["both"]))
        print("   仅死会话有（需解释）:", len(cross["dead_only"]))
        for x in cross["dead_only"][:20]:
            print("      ", x)
        print("   仅本轮有:", len(cross["mine_only"]))
        for x in cross["mine_only"][:20]:
            print("      ", x)

    out = {
        "script": "_app250_verify_baseline.py",
        "method": "A reviewer 权威基线逐条核销 + B 基线短语全库子串扫描 + C 交叉核对",
        "n_base_files": len(hits),
        "n_base_phrases": len(phrases),
        "n_tracked": len(tracked),
        "A": {"n_files_residual": n_files_residual, "n_still": n_still_total,
              "n_base": n_base_total, "per_file": per_file},
        "B": {"n_files": len(scan_hits), "hits": scan_hits},
        "C": cross,
    }
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)
    print("\n写出:", OUT)


if __name__ == "__main__":
    main()
