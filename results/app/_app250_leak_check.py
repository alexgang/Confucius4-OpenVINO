# -*- coding: utf-8 -*-
"""§250 **入库前/入库后泄漏自查**（判据确定 ⇒ 结果可复算）。

🔴 v1 的缺陷：候选集＝「git status 的已改 ＋ untracked 的 app249/app250」⇒
   **随 git 状态漂移**（实测同一轮里 62 → 51 → 12）⇒ 报出的数字不可复算。
🔴 v2：候选集改为**确定性集合**＝
   ① **§250 那次提交实际入库的文件清单**（`git show --name-only HEAD`）
   ② 仓内**全部** `.py`/`.json` 里文件名含 app249/app250 的（不论 tracked 与否）
   ⇒ 同一 commit ⇒ 同一候选集 ⇒ 数字可复算。

🔴 判据：reviewer 权威基线句（归一化后**子串粒度**）⇒ 命中即 FAIL。
🔴 RULES §0：证据只写 len + sha256 前 8 位，**不写原句**。
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
OUT = os.path.join(REPO, "results", "app", "app250_leak_check.json")

_sp = importlib.util.spec_from_file_location(
    "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
v3 = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(v3)


def git_lines(args):
    return [l for l in subprocess.run(args, cwd=REPO, capture_output=True,
                                       text=True, encoding="utf-8",
                                       errors="replace").stdout.splitlines()
            if l.strip()]


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    base = v3.baseline_sents(gt)

    cands = set()
    # ① 本次提交实际入库的文件（HEAD 的变更集）
    for rel in git_lines(["git", "show", "--name-only", "--pretty=format:", "HEAD"]):
        cands.add(rel.strip())
    # ② 仓内所有 app249/app250 相关 .py/.json（tracked + untracked）
    all_files = set(git_lines(["git", "ls-files"])) | set(
        git_lines(["git", "ls-files", "--others", "--exclude-standard"]))
    for rel in all_files:
        if ("app250" in rel or "app249" in rel) and rel.endswith((".py", ".json")):
            cands.add(rel)
    # ③ 本轮新写的状态/证据文件
    for rel in ("status/app/STATUS_APP.md",
                "status/app/STATUS_APP_sec250_detail_20261128.md"):
        cands.add(rel)
    cands = sorted(c for c in cands if c)

    print("候选入库文件 %d 个（确定性：HEAD 变更集 ∪ app249/app250 相关 ∪ STATUS）"
          % len(cands))
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
            bad.append({"file": rel, "n_sents": len(hits)})
            print("  🔴 LEAK %-60s 命中 %d 句" % (rel[-60:], len(hits)))
    print("  （其余 %d 个文件 clean）" % (len(cands) - len(bad)))
    res = {"script": "_app250_leak_check.py",
           "criterion": "确定性候选集（HEAD 变更集 ∪ app249/app250 相关 .py/.json ∪ STATUS）× reviewer 权威基线句（子串粒度）",
           "n_candidates": len(cands),
           "n_leak": len(bad),
           "leak_files": bad,
           "pass": len(bad) == 0}
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    print("\n泄漏文件数：", len(bad))
    print("总判定：", "PASS（无泄漏）" if res["pass"] else "FAIL")
    print("写出:", OUT)


if __name__ == "__main__":
    main()
