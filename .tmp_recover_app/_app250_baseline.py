# -*- coding: utf-8 -*-
"""§250 基线采集：在**任何改动前**跑一遍会被改到的 4 个功能脚本，存下 stdout 与证据文件。

🔴 目的：改动后**逐字节比对这些输出** ⇒ 证明「脱敏没有改坏行为」。
🔴 跑完把被改写的证据文件恢复（git checkout），保证后续 diff 只含预期改动。

不跑推理/测速：4 个脚本都是**纯离线**（无模型、无 GPU、只读 hy_bench 产物 json）。
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
BASE = os.path.join(REPO, ".tmp_recover_app", "_app250_base")
os.makedirs(BASE, exist_ok=True)

# (脚本, 证据文件, 用的 python)
JOBS = [
    ("results/app/app053_draft_prefix_boundary_probe.py",
     "results/app/app053_draft_prefix_boundary_evidence.json", "py"),
    ("results/app/test_app015_caption_render.py",
     "results/app/app015_caption_render_evidence.json", "py"),
    ("results/app/app127_c111_real_timing_draft_lines.py",
     "results/app/app127_c111_real_timing_draft_lines_evidence.json", "py"),
    ("live_caption/diag_c111_half.py", None, "py312"),
]


def sh(cmd, cwd=REPO):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def main():
    for script, ev, pyk in JOBS:
        name = os.path.basename(script).replace(".py", "")
        out = os.path.join(BASE, name + ".stdout.txt")
        exe = "py" if pyk == "py" else "py"
        args = [exe] if pyk == "py" else [exe, "-3.12"]
        r = sh(args + [script])
        io.open(out, "w", encoding="utf-8", newline="\n").write(
            "rc=%d\n--- stdout ---\n%s\n--- stderr ---\n%s\n"
            % (r.returncode, r.stdout, r.stderr))
        print("%-52s rc=%d  stdout=%d B" % (script, r.returncode, len(r.stdout)))
        if ev:
            p = os.path.join(REPO, ev.replace("/", os.sep))
            if os.path.isfile(p):
                shutil.copy2(p, os.path.join(BASE, os.path.basename(ev)))
                print("    证据已存基线: %s" % os.path.basename(ev))
            # 恢复证据文件（避免基线运行污染后续 diff）
            g = sh(["git", "checkout", "--", ev])
            print("    恢复证据文件 rc=%d" % g.returncode)
    print("\n基线目录:", BASE)
    for f in sorted(os.listdir(BASE)):
        print("   ", f, os.path.getsize(os.path.join(BASE, f)), "B")


if __name__ == "__main__":
    main()
