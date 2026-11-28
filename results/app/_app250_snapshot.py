# -*- coding: utf-8 -*-
"""§250 修复前快照：记录 11 个脱敏文件的 sha256（用于「重跑后逐字节相等」比对）。"""
from __future__ import annotations

import hashlib
import io
import json
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
REDACT = os.path.join(REPO, "results", "app", "app250_redact.json")
OUT = os.path.join(REPO, "results", "app", "app250_snapshot_pre_rerun.json")

red = json.load(open(REDACT, encoding="utf-8"))
rows = {}
for c in red["changed"]:
    rel = c["file"]
    p = os.path.join(REPO, rel.replace("/", os.sep))
    b = open(p, "rb").read()
    rows[rel] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    print("%-58s %s %d" % (rel[-58:], rows[rel]["sha256"][:16], rows[rel]["bytes"]))
with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump({"script": "_app250_snapshot.py", "rows": rows}, fh,
              ensure_ascii=False, indent=1)
print("写出:", OUT)
