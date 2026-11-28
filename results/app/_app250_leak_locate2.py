# -*- coding: utf-8 -*-
"""定位 companion 里的泄漏行（只打印行号 + sha8 + 上下文形态，不打印原句）。"""
import importlib.util
import io
import json

spec = importlib.util.spec_from_file_location(
    "v3", "results/app/app250_verify_indep3.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
gt = json.load(open("results/app/app155_desens_ground_truth.json", encoding="utf-8"))
base = m.baseline_sents(gt)
p = "status/app/STATUS_APP_sec250_detail_20261128.md"
for ln, line in enumerate(io.open(p, encoding="utf-8").read().splitlines(), 1):
    nl, _ = m.norm_with_map(line)
    if not nl:
        continue
    for s in base:
        if s in nl:
            print("line %-4d len=%-3d sha8=%s" % (ln, len(s), m.sha8(s)))
            print("   ", line[:170])
            break
