# -*- coding: utf-8 -*-
"""§250 提交前**泄漏自查**：候选入库文件里是否含**会议原句**（RULES §0）。

🔴 纪律：证据文件里也不写会议原句（APP-155／RULES §0）⇒ 入库前必须逐个自查。
🔴 判据：reviewer 权威基线句（归一化后子串粒度）⇒ 命中即 FAIL。
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
_spec = importlib.util.spec_from_file_location(
    "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v3)

GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    base = v3.baseline_sents(gt)
    # 候选入库清单（§250 的脚本 + 证据 + 本轮独立复核 + §250 的 11 个脱敏文件）
    cands = []
    for rel in subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                              capture_output=True, text=True,
                              encoding="utf-8").stdout.splitlines():
        st = rel[:2].strip()
        path = rel[3:].strip().strip('"')
        if st == "M" and not path.endswith("CORRECTIONS_APP.md"):
            cands.append(path)
    # §250 相关的 untracked（**已尊重 .gitignore**：git ls-files --others
    # --exclude-standard 本身就会排除被 ignore 的路径 ⇒ 基线快照目录不入选）
    for rel in subprocess.run(["git", "ls-files", "--others",
                                "--exclude-standard"], cwd=REPO,
                               capture_output=True, text=True,
                               encoding="utf-8").stdout.splitlines():
        if ("app250" in rel or "app249" in rel) and rel.endswith((".py", ".json")):
            cands.append(rel)
    cands = sorted(set(cands))

    print("候选入库文件 %d 个" % len(cands))
    bad = []
    for rel in cands:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            continue
        try:
            t = open(p, "rb").read().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        nl, _ = v3.norm_with_map(t)
        hits = [s for s in base if s in nl]
        if hits:
            bad.append((rel, len(hits)))
            print("  🔴 LEAK %-60s 命中 %d 句" % (rel[-60:], len(hits)))
        else:
            print("  🟢 clean %-59s" % rel[-59:])
    print("\n泄漏文件数：", len(bad))
    out = {"script": "_app250_leak_check.py",
           "n_candidates": len(cands), "n_leak": len(bad),
           "leak_files": [{"file": f, "n_sents": n} for f, n in bad],
           "pass": len(bad) == 0}
    with io.open(os.path.join(REPO, "results", "app",
                              "app250_leak_check.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("总判定：", "PASS（无泄漏）" if out["pass"] else "FAIL")


if __name__ == "__main__":
    main()
