# -*- coding: utf-8 -*-
"""§250 **重跑生产脚本**（可复现性证明 + 证据再生成）。

🔴 目的：
 ① 死会话的 ``_app250_redact.py`` 的 DECISIONS **理由文本里写了会议原句**
    ⇒ 违反 RULES §0（证据/脚本里也不写原句）⇒ 已修（改为 len+sha8 指代）。
 ② 本脚本：把 11 个文件**还原成备份（= HEAD）态** ⇒ 重跑 ``_app250_redact.py``
    ⇒ 产出**新的** ``app250_redact.json``（无泄漏）⇒ 再与**重跑前的快照**逐字节比对
    ⇒ **证明脚本可复现**（同输入 ⇒ 同输出，逐字节相等）。

🔴 写前不变量：
 ① 备份目录 11 个文件**必须**与 HEAD 逐字节相等（否则还原会丢内容）
 ② 重跑后 11 个文件**必须**与快照逐字节相等（否则不可复现 ⇒ 中止）
 ③ 重跑**只**改这 11 个文件（其余 tracked 文件 SHA 前后一致）
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
BACKUP = r"C:\Users\Trekker-PTL\shared\app250_desen_backup"
REDACT_JSON = os.path.join(REPO, "results", "app", "app250_redact.json")
SNAP = os.path.join(REPO, "results", "app", "app250_snapshot_pre_rerun.json")
SCRIPT = os.path.join(REPO, ".tmp_recover_app", "_app250_redact.py")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def tracked_hashes():
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8").stdout.splitlines()
    h = {}
    for rel in out:
        p = os.path.join(REPO, rel.replace("/", os.sep))
        if os.path.isfile(p):
            h[rel] = sha(p)
    return h


def main():
    snap = json.load(open(SNAP, encoding="utf-8"))["rows"]
    files = sorted(snap.keys())

    # ── ① 备份必须 == HEAD ────────────────────────────────────
    for rel in files:
        bp = os.path.join(BACKUP, rel.replace("/", os.sep))
        r = subprocess.run(["git", "show", "HEAD:" + rel], cwd=REPO,
                           capture_output=True)
        assert r.returncode == 0, "① 违反：HEAD 无此文件 %s" % rel
        assert open(bp, "rb").read() == r.stdout, \
            "① 违反：备份 != HEAD ⇒ %s" % rel
    print("① 备份 11 文件 == HEAD 逐字节相等：PASS")

    # ── 还原成备份态 ─────────────────────────────────────────
    for rel in files:
        bp = os.path.join(BACKUP, rel.replace("/", os.sep))
        cp = os.path.join(REPO, rel.replace("/", os.sep))
        shutil.copy2(bp, cp)
    print("已还原 11 个文件到备份（= HEAD）态")

    before_all = tracked_hashes()
    red_before = sha(REDACT_JSON)

    # ── 重跑生产脚本 ─────────────────────────────────────────
    r = subprocess.run([sys.executable, SCRIPT], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    print("--- 生产脚本输出（末 12 行）---")
    for ln in (r.stdout or "").splitlines()[-12:]:
        print("   ", ln)
    if r.returncode != 0:
        print("!! 生产脚本 rc=%d" % r.returncode)
        print((r.stderr or "")[-2000:])
        sys.exit(1)

    # ── ② 重跑后必须与快照逐字节相等 ─────────────────────────
    diffs = []
    for rel in files:
        cp = os.path.join(REPO, rel.replace("/", os.sep))
        now = sha(cp)
        if now != snap[rel]["sha256"]:
            diffs.append(rel)
    if diffs:
        print("② 违反：重跑结果与快照不等 ⇒ %d 个文件" % len(diffs))
        for d in diffs:
            print("     ", d)
        sys.exit(1)
    print("② 重跑后 11 文件与快照逐字节相等（可复现）：PASS")

    # ── ③ 只改了这 11 个文件 ─────────────────────────────────
    after_all = tracked_hashes()
    changed = [k for k in before_all
               if k in after_all and before_all[k] != after_all[k]]
    changed += [k for k in after_all if k not in before_all]
    unexpected = [c for c in changed
                  if c not in files and c != "results/app/app250_redact.json"]
    if unexpected:
        print("③ 违反：额外改了 %d 个文件 ⇒ %s" % (len(unexpected), unexpected[:10]))
        sys.exit(1)
    print("③ 只改了这 11 个文件（+ 证据 json）：PASS（changed=%d）" % len(changed))

    print("\n证据 json：sha 前 %s → 前 %s（已重新生成）"
          % (red_before[:16], sha(REDACT_JSON)[:16]))


if __name__ == "__main__":
    main()
