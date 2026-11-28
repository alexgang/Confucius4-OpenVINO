# -*- coding: utf-8 -*-
"""§250 **反证组（anti-control）**：证明独立复核的判据**有鉴别力**。

🔴 纪律（项目铁律）：「PASS ≠ 正确」——判据必须**被有缺陷的旧产物识破**；
   反证组必须**有鉴别力**（「去掉被检对象仍成立」⇒ 不能进）。

🔴 本反证组的设计必须**真的**破坏被检对象，否则是**反证组自身的缺陷**：
 - **AC-1（§1 鉴别力）**：把一条 GT 原句注入到一个**已被 git 跟踪**的文件
   ⇒ §1 残留扫描**必须**命中。
   🔴 v1 缺陷：探针文件若是 **untracked** ⇒ `git ls-files` 扫不到 ⇒ §1 必然
      「NO HIT」⇒ 那是反证组设计缺陷，**不是**判据没鉴别力。
 - **AC-2（§2 鉴别力）**：**改动**一行**不含** GT 句的既有内容（让该行进入
   diff 的 **minus 侧**）⇒ §2 diff 法**必须**判 FAIL。
   🔴 v1 缺陷：只**插入**一行中性内容 ⇒ minus 侧没有非 GT 行 ⇒
      `minus_all_have_gt` 仍为 True ⇒ 假 FAIL。
 - **AC-3（§4 鉴别力）**：在被改脚本里**注入真行为变化**（让某条断言的 ok 翻转）
   ⇒ §4 的「断言判定相同」判据**必须**识破。

🔴 每个 AC 都在**工作树副本**上做，跑完**逐字节复原**原文件与 evidence ⇒ 工作树零污染。
🔴 RULES §0：证据只写 len + sha256 前 8 位，**不写原句**。
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
GTJSON = os.path.join(REPO, "results", "app", "app155_desens_ground_truth.json")
OUT = os.path.join(REPO, "results", "app", "app250_anticontrol.json")

_spec = importlib.util.spec_from_file_location(
    "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
v3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v3)


def sha8(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def tracked_set():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8").stdout
    return set(out.splitlines())


def main():
    gt = json.load(open(GTJSON, encoding="utf-8"))
    base = v3.baseline_sents(gt)
    # 取一条**较长的**基线原句做反证注入（长度 ≥ 20 ⇒ 子串粒度能判出）
    orig_text = None
    for rel, hs in gt["hits"].items():
        for h in hs:
            t = h.get("text")
            if isinstance(t, str) and len(t) >= 20 and v3.norm(t) in base:
                orig_text = t
                break
        if orig_text:
            break

    rows = []
    tracked = tracked_set()
    tgt = "results/app/test_app015_caption_render.py"
    tgt_p = os.path.join(REPO, tgt.replace("/", os.sep))
    assert tgt in tracked, "AC 目标文件未被跟踪"

    # ── AC-1：§1 鉴别力 ────────────────────────────────────────
    bak1 = tgt_p + ".ac1bak"
    shutil.copy2(tgt_p, bak1)
    try:
        t = io.open(tgt_p, encoding="utf-8").read()
        t2 = t + "\n# AC1_PROBE = %r\n" % orig_text
        with io.open(tgt_p, "w", encoding="utf-8", newline="") as fh:
            fh.write(t2)
        n_scanned, residual = v3.scan_residual(base, skip=set(gt["gt_files"]))
        hit = residual.get(tgt)
        rows.append({"id": "AC-1", "target": "sec1_residual",
                     "expect": "FAIL（§1 必须命中注入进 tracked 文件的真原句）",
                     "observed": ("HIT n=%d" % len(hit)) if hit else "NO HIT",
                     "pass": bool(hit)})
    finally:
        shutil.copy2(bak1, tgt_p)
        os.remove(bak1)

    # ── AC-2：§2 鉴别力（改动一行**不含** GT 句的既有内容）──────────
    bak2 = tgt_p + ".ac2bak"
    shutil.copy2(tgt_p, bak2)
    try:
        t = io.open(tgt_p, encoding="utf-8").read()
        marker = "BLOCKS = ["
        assert marker in t, "AC-2 锚点丢失"
        # 该行**不含** GT 句 ⇒ 改动它 ⇒ 它进入 diff 的 minus 侧
        t2 = t.replace(marker, "BLOCKS = list([", 1)
        with io.open(tgt_p, "w", encoding="utf-8", newline="") as fh:
            fh.write(t2)
        d = v3.diff_check(tgt, base)
        ok = bool(d.get("changed") and not d.get("minus_all_have_gt"))
        rows.append({"id": "AC-2", "target": "sec2_diff",
                     "expect": "FAIL（minus 侧出现非 GT 行 ⇒ diff 法必须识破）",
                     "observed": "minus_all_have_gt=%s plus_no_gt=%s"
                                 % (d.get("minus_all_have_gt"), d.get("plus_no_gt")),
                     "pass": ok})
    finally:
        shutil.copy2(bak2, tgt_p)
        os.remove(bak2)

    # ── AC-3：§4 鉴别力（注入真行为变化）────────────────────────
    ev_rel = "results/app/app015_caption_render_evidence.json"
    ev_p = os.path.join(REPO, ev_rel.replace("/", os.sep))
    bak3 = tgt_p + ".ac3bak"
    bak3ev = ev_p + ".ac3evbak"
    shutil.copy2(tgt_p, bak3)
    shutil.copy2(ev_p, bak3ev)
    try:
        t = io.open(tgt_p, encoding="utf-8").read()
        old = "check('REAL', 'R5 原文守恒（渲染层不丢字/不加字）',"
        assert old in t, "AC-3 锚点丢失"
        t2 = t.replace(old, "check('REAL', 'R5 原文守恒（渲染层不丢字/不加字）', False and", 1)
        with io.open(tgt_p, "w", encoding="utf-8", newline="") as fh:
            fh.write(t2)
        # after = 被改坏（判定翻转）的当前版
        cap = v3.run_capture(tgt, "py", ev_rel)
        shutil.copy2(bak3ev, ev_p)          # 复原 evidence（跑脚本写过的）
        # before = 备份版（脱敏前、判定完好）
        bakp = os.path.join(v3.BACKUP, tgt.replace("/", os.sep))
        keep = tgt_p + ".ac3keep"
        shutil.copy2(tgt_p, keep)
        shutil.copy2(bakp, tgt_p)
        try:
            before = v3.run_capture(tgt, "py", ev_rel)
        finally:
            shutil.copy2(keep, tgt_p)
            os.remove(keep)
        shutil.copy2(bak3ev, ev_p)          # 再复原 evidence
        vb = v3.verdicts_of(before["evidence"])
        va = v3.verdicts_of(cap["evidence"])
        same = (vb == va)
        n_ok_b = sum(1 for x in vb["oks"] if x) if vb else None
        n_ok_a = sum(1 for x in va["oks"] if x) if va else None
        rows.append({"id": "AC-3", "target": "sec4_behavior",
                     "expect": "FAIL（断言判定被改坏 ⇒ 必须识破）",
                     "observed": "verdicts_same=%s ok_true %s->%s"
                                 % (same, n_ok_b, n_ok_a),
                     "pass": (not same)})
    finally:
        shutil.copy2(bak3, tgt_p)
        os.remove(bak3)
        shutil.copy2(bak3ev, ev_p)
        os.remove(bak3ev)

    n_pass = sum(1 for r in rows if r["pass"])
    result = {
        "script": "app250_anticontrol.py",
        "note": "反证组：故意改坏被检部分，验证判据有鉴别力（去掉被检对象仍成立⇒不能进）",
        "n_cases": len(rows),
        "n_pass": n_pass,
        "all_pass": n_pass == len(rows),
        "rows": rows,
        "injected_len": len(orig_text),
        "injected_sha8": sha8(orig_text),
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, ensure_ascii=False, indent=1)
    for r in rows:
        print("  %-6s %-16s observed=%-34s %s"
              % (r["id"], r["target"], r["observed"],
                 "PASS" if r["pass"] else "FAIL"))
    print("\n反证组判定：", "ALL PASS（判据有鉴别力）" if result["all_pass"]
          else "HAS FAIL")
    print("写出:", OUT)


if __name__ == "__main__":
    main()
