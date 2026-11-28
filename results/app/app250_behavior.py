# -*- coding: utf-8 -*-
"""§250 行为等价验证：脱敏**前后**逐字节比对「会执行的脚本」的 stdout/stderr。

🔴 为什么要做：脱敏改的是**文档/生成器**里的文本，但文件是 ``.py`` ⇒
必须证明「改了之后这些脚本跑出来的输出**一字不差**」，
否则就是「改了文本、悄悄改了行为」。

比对对象（**只挑真会被执行的脚本**，且都是纯离线、无模型、无 GPU）：
  1. ``results/app/app053_draft_prefix_boundary_probe.py``（读 hy_bench 产物 json）
  2. ``results/app/test_app015_caption_render.py``（纯 stdlib）
  3. ``results/app/app127_c111_real_timing_draft_lines.py``（需 numpy ⇒ 用系统 3.12）
  4. ``live_caption/diag_c111_half.py``（纯 stdlib 诊断脚本）

⚠️ 脚本会**写自己的 evidence 文件** ⇒ 运行前把该文件备份、运行后**复原**
    （避免污染工作树 ⇒ 避免把「跑脚本的副作用」当成「脱敏的副作用」）。

🔴 记录 rc + stdout + stderr + 被写文件的 sha256 ⇒ 前后逐项比。
🔴 RULES §0：证据只写 len + sha256 前 8 位。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
OUT = os.path.join(REPO, "results", "app", "app250_behavior.json")
BASE = r"C:\Users\Trekker-PTL\shared\app250_behavior_base"

# (脚本, 解释器, 该脚本会写的 evidence 文件)
JOBS = [
    ("results/app/app053_draft_prefix_boundary_probe.py", "py",
     "results/app/app053_draft_prefix_boundary_evidence.json"),
    ("results/app/test_app015_caption_render.py", "py",
     "results/app/app015_caption_render_evidence.json"),
    ("results/app/app127_c111_real_timing_draft_lines.py", "py312",
     "results/app/app127_c111_real_timing_draft_lines_evidence.json"),
    ("live_caption/diag_c111_half.py", "py",
     "results/app/diag_c111_half_evidence.json"),
]


def sha256_file(p):
    if not os.path.isfile(p):
        return None
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


# evidence 里**每次跑都会变**的字段 ⇒ 比对时必须剔除，否则判据恒 FAIL
VOLATILE_KEYS = ("generated_at",)


def stable_evidence_fingerprint(p):
    """evidence 的**稳定**指纹：剔除时间戳等易变字段后重算 sha256。

    🔴 实测：两次跑同一脚本，evidence 只有 ``generated_at`` 变
    （其余 0 差异）⇒ 不剔除它 ⇒ 「脱敏前后逐字节比对」会**恒 DIFF** ⇒ 假 FAIL。
    """
    if not os.path.isfile(p):
        return None
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        return sha256_file(p)

    def strip(o):
        if isinstance(o, dict):
            return {k: strip(v) for k, v in o.items()
                    if k not in VOLATILE_KEYS}
        if isinstance(o, list):
            return [strip(v) for v in o]
        return o

    blob = json.dumps(strip(d), ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def run_job(script, interp, evidence):
    """跑一个脚本 ⇒ 收集 rc/stdout/stderr/evidence 指纹。"""
    args = ["py"] if interp == "py" else ["py", "-3.12"]
    r = subprocess.run(args + [script], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    ev = os.path.join(REPO, evidence.replace("/", os.sep))
    return {
        "rc": r.returncode,
        "stdout_len": len(r.stdout),
        "stdout_sha256": hashlib.sha256(r.stdout.encode("utf-8")).hexdigest(),
        "stderr_len": len(r.stderr),
        "stderr_sha256": hashlib.sha256(r.stderr.encode("utf-8")).hexdigest(),
        "evidence_exists": os.path.isfile(ev),
        "evidence_sha256": sha256_file(ev),
        "evidence_stable_sha256": stable_evidence_fingerprint(ev),
    }


def main():
    phase = sys.argv[1] if len(sys.argv) > 1 else "before"
    os.makedirs(BASE, exist_ok=True)
    rows = []
    for script, interp, evidence in JOBS:
        # 运行前备份该脚本会写的 evidence（若有）
        ev = os.path.join(REPO, evidence.replace("/", os.sep))
        bak = os.path.join(BASE, phase + "__" + os.path.basename(evidence))
        if os.path.isfile(ev):
            shutil.copy2(ev, bak)
        rec = run_job(script, interp, evidence)
        # 运行后**复原** evidence ⇒ 工作树不被跑脚本的副作用污染
        if os.path.isfile(bak):
            shutil.copy2(bak, ev)
        rec.update({"script": script, "interp": interp, "evidence": evidence})
        rows.append(rec)
        print("  [%s] %-56s rc=%s stdout=%d B" % (phase, script[:56], rec["rc"],
                                                 rec["stdout_len"]))

    out_path = os.path.join(BASE, "behavior_%s.json" % phase)
    with io.open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"phase": phase, "rows": rows}, fh, ensure_ascii=False, indent=1)
    print("写出:", out_path)

    # 前后对比（当 after 阶段存在时）
    before_p = os.path.join(BASE, "behavior_before.json")
    if phase == "after" and os.path.isfile(before_p):
        before = json.load(open(before_p, encoding="utf-8"))["rows"]
        by = {r["script"]: r for r in before}
        print()
        print("=== 脱敏前后行为逐项比对 ===")
        all_same = True
        for r in rows:
            b = by.get(r["script"])
            if not b:
                continue
            keys = ["rc", "stdout_len", "stdout_sha256", "stderr_len",
                    "stderr_sha256", "evidence_stable_sha256"]
            same = all(b.get(k) == r.get(k) for k in keys)
            all_same = all_same and same
            print("  %-56s %s" % (r["script"][:56], "SAME" if same else "DIFF"))
            if not same:
                for k in keys:
                    if b.get(k) != r.get(k):
                        print("      %s: before=%r after=%r" % (k, b.get(k), r.get(k)))
        print()
        print("总判定：", "ALL SAME（脱敏未改任何可观察行为）" if all_same
              else "HAS DIFF（有行为差异 ⇒ 必须回退并查因）")
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            json.dump({"before": before, "after": rows,
                       "all_same": all_same}, fh, ensure_ascii=False, indent=1)
        print("写出:", OUT)


if __name__ == "__main__":
    main()
