# -*- coding: utf-8 -*-
"""定位泄漏文件的**命中位置**（行号 + sha8 + 上下文类别），不打印原句。"""
from __future__ import annotations

import importlib.util
import json
import os
import re

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
_spec = importlib.util.spec_from_file_location(
    "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v3)

GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
FILES = [
    ".tmp_recover_app/_app250_redact.py",
    "results/app/app250_redact.json",
    "results/app/app250_verify_indep3.json",
    "results/app/app250_verify_indep3.py",
    "status/app/_app250_append_status.py",
]

gt = json.load(open(GTJSON, encoding="utf-8"))
base = v3.baseline_sents(gt)
for rel in FILES:
    p = os.path.join(REPO, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        continue
    print("=== %s" % rel)
    for ln, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
        nl, _ = v3.norm_with_map(line)
        if not nl:
            continue
        for s in base:
            if s in nl:
                # 判断所在形态：字符串字面量 / docstring / comment / json 值
                kind = "?"
                st = line.strip()
                if st.startswith("#"):
                    kind = "comment"
                elif st.startswith(('"""', "'''", '"', "'")):
                    kind = "string-literal"
                elif '"' in st:
                    kind = "json-value/str"
                print("   line %-5d len=%-3d sha8=%s  kind=%-16s | %s"
                      % (ln, len(s), v3.sha8(s), kind,
                         re.sub(r"[^\x20-\x7e]", ".", st)[:96]))
                break
