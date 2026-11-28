# -*- coding: utf-8 -*-
"""§250：在 .gitignore 追加「基线快照目录」规则（**不删任何文件**，只挡新增入库）。

🔴 为什么：§250 的基线目录 ``.tmp_recover_app/_app250_base/`` 里存着
   **脱敏前**的源文件副本（与 HEAD 逐字节相同 ⇒ 含会议原句）⇒
   若被 `git add` 就会把原句带进仓库。.gitignore 只挡新增、不动存量 ⇒
   这是**预防**措施，不改变任何已跟踪文件。

🔴 写前不变量：
 ① 只**追加**到文件末尾（原内容逐字节不变）
 ② 追加行数 == 预期
 ③ 追加内容不含会议原句
"""
from __future__ import annotations

import io
import json
import os

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
P = os.path.join(REPO, ".gitignore")

ADD = (
    "\n"
    "# 🔴 §250（2026-11-28）**基线快照目录**——里面存着**脱敏前**的源文件副本\n"
    "#   （与 HEAD 逐字节相同 ⇒ 含会议原句）⇒ 一律**不入库**。\n"
    "#   ⚠️ .gitignore 只挡新增、不动存量 ⇒ 若已入库须单独 `git rm --cached`。\n"
    "#   🔴 末尾的 `/` ⇒ **只匹配目录**（不误伤 `_app250_baseline.py` 这类脚本）。\n"
    ".tmp_recover_app/_app250_base/\n"
)


def main():
    b0 = open(P, "rb").read()
    print("写前: bytes=%d lines=%d" % (len(b0), b0.count(b"\n")))
    # 🔴 幂等：已存在同一规则 ⇒ 直接退出（不重复追加）
    # 🔴 幂等判据：检查**规则行本身**（目录形态，末尾带 `/`）
    marker = b".tmp_recover_app/_app250_base/\n"
    if marker in b0:
        print("已存在 §250 基线目录规则 ⇒ 幂等退出（未改动）")
        return
    body = ADD.encode("utf-8")
    b1 = b0 + body
    assert b1.startswith(b0), "① 违反：原文件被改动"
    assert b1.count(b"\n") == b0.count(b"\n") + body.count(b"\n"), "① 违反：行数异常"
    # ③ 内容不得含会议原句（用 GT 基线句做归一化子串判定，**不把原句写进本文件**）
    import importlib.util
    _sp = importlib.util.spec_from_file_location(
        "v3", os.path.join(REPO, "results", "app", "app250_verify_indep3.py"))
    _v3 = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(_v3)
    _gt = json.load(open(os.path.join(REPO, "results", "app",
                                      "app155_desens_ground_truth.json"),
                         encoding="utf-8"))
    _nl, _ = _v3.norm_with_map(body.decode("utf-8"))
    _hit = [s for s in _v3.baseline_sents(_gt) if s in _nl]
    assert not _hit, "③ 违反：追加内容含会议原句（命中 %d 句）" % len(_hit)
    with io.open(P, "wb") as fh:
        fh.write(b1)
    print("写出: bytes=%d (Δ=%d)" % (len(b1), len(b1) - len(b0)))


if __name__ == "__main__":
    main()
