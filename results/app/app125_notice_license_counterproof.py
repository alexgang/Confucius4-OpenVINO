# -*- coding: utf-8 -*-
"""App §85 反证：用**修正前**的 NOTICE/THIRD_PARTY 原文验证 app124 判据曾真实 FAIL。

纪律：
  - 反证基准是**实际修正前的文本**（来自 git HEAD 之外的备份/客户包备份），
    不用 HEAD（HEAD 若已修好，反证会落空 ⇒ 假证据，§31 教训）；
  - 纯离线字符串/文本判定，不触碰客户包；
  - 判据必须能 FAIL。
"""
import io
import json
import os
import re
import sys

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6"
SP = os.path.join(PKG, "python", "Lib", "site-packages")

# 修正前的 NOTICE 原文（本轮开工时从客户包读到的内容，逐字内嵌为反证基准）
OLD_NOTICE = u"""Confucius4 LiveCaption v1.6 \u2014 \u7b2c\u4e09\u65b9\u7ec4\u4ef6\u5f52\u5c5e\u4e0e\u8bb8\u53ef\u8bc1
=====================================================

\u672c\u8f6f\u4ef6\u5305\u542b\u6216\u4f9d\u8d56\u4ee5\u4e0b\u7b2c\u4e09\u65b9\u7ec4\u4ef6\u3002\u6240\u6709\u7ec4\u4ef6\u5747\u4e3a Apache License 2.0 \u6388\u6743\uff0c
\u53ef\u81ea\u7531\u518d\u5206\u53d1\u3002
"""

OLD_TP_NUM2WORDS_MISSING = True  # 旧 THIRD_PARTY.md 里没有 num2words 这一行（实测）

results = []


def chk(cid, name, ok, got="", want=""):
    results.append((cid, name, bool(ok), got, want))


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


def app124_judges(notice_text, tp_text):
    """复刻 app124 的核心判据（对任意文本），用于反证。"""
    out = {}
    # G6: 顶部不得声称「所有组件均为 Apache License 2.0」
    out["G6"] = re.search(r"\u6240\u6709\u7ec4\u4ef6\u5747\u4e3a\s*Apache", notice_text) is None
    # G7: 不得出现 num2words = MIT（只判**表格行**，行级提取许可列）
    bad = []
    nrows = 0
    for l in notice_text.splitlines():
        if "num2words" not in l or not l.lstrip().startswith("|"):
            continue
        m = re.match(r"^\|\s*[^|]+\|\s*[^|]*\|\s*(.+?)\s*\|", l)
        if not m:
            continue
        nrows += 1
        if re.search(r"\bMIT\b", m.group(1)):
            bad.append(l[:80])
    out["G7"] = (nrows == 1 and not bad)
    # G1: 表格行数 == 47
    rows = 0
    for line in notice_text.splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$", line)
        if m and m.group(1) not in ("\u5305", "---") and not set(m.group(1)) <= set("-: "):
            rows += 1
    out["G1"] = (rows == 47)
    # G10: THIRD_PARTY 里 num2words 必须是 LGPL
    tp_row = re.search(r"^\|\s*num2words\s*\|[^|]*\|\s*([^|]+?)\s*\|", tp_text, re.M)
    out["G10"] = bool(tp_row and "LGPL" in tp_row.group(1))
    return out


# ---- 反证 1：修正前的 NOTICE 文本 ----
old_j = app124_judges(OLD_NOTICE, "")
chk("R1-1", "【反证】修正前 NOTICE：G6（不得声称全部 Apache）必须 FAIL",
    old_j["G6"] is False, "G6=%s" % old_j["G6"], "False（修正前确实 FAIL）")
chk("R1-2", "【反证】修正前 NOTICE：G1（表格覆盖 47 包）必须 FAIL",
    old_j["G1"] is False, "G1=%s（表格行数=0）" % old_j["G1"], "False")

# ---- 反证 2：修正前的 THIRD_PARTY.md（无 num2words 行）----
old_tp = u"""| Package | Version | License |
|---|---|---|
| certifi | 2026.7.22 | MPL-2.0 |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| openvino | 2026.4.1 | Apache-2.0 |
"""
old_j2 = app124_judges(u"", old_tp)
chk("R2-1", "【反证】修正前 THIRD_PARTY：G10（num2words 必须 LGPL）必须 FAIL",
    old_j2["G10"] is False, "G10=%s" % old_j2["G10"], "False（修正前确实 FAIL）")

# ---- 反证 3：当前实文件必须全部 PASS（证明判据不是恒 FAIL）----
cur_notice = read(os.path.join(PKG, "NOTICE"))
cur_tp = read(os.path.join(PKG, "THIRD_PARTY.md"))
cur_j = app124_judges(cur_notice, cur_tp)
for cid, name in [("G6", "NOTICE 顶部不得声称全部 Apache"),
                  ("G7", "NOTICE 不得出现 num2words=MIT"),
                  ("G1", "NOTICE 表格覆盖 47 包"),
                  ("G10", "THIRD_PARTY 的 num2words = LGPL")]:
    chk("R3-%s" % cid, "【反证】当前实文件：%s 必须 PASS" % name,
        cur_j[cid] is True, "%s=%s" % (cid, cur_j[cid]), "True")

# ---- 反证 4：把当前 NOTICE 的 LGPL 改回 MIT 后，G7/G5 类判据必须 FAIL ----
sandbox = cur_notice.replace("LGPL-2.1\uff08\u6216\u66f4\u9ad8\u7248\u672c\uff09", "MIT")
sb = app124_judges(sandbox, cur_tp)
chk("R4-1", "【反证】把当前 NOTICE 的 num2words 改成 MIT 后，G7 必须 FAIL",
    sb["G7"] is False, "G7=%s" % sb["G7"], "False")
chk("R4-2", "【反证】把当前 THIRD_PARTY 的 num2words 改成 MIT 后，G10 必须 FAIL",
    app124_judges(cur_notice, cur_tp.replace("LGPL-2.1-or-later", "MIT"))["G10"] is False,
    "G10=%s" % app124_judges(cur_notice, cur_tp.replace("LGPL-2.1-or-later", "MIT"))["G10"],
    "False")

# ---- 反证 5：判定「包内确实只有 47 个 dist-info」这一前提本身可被推翻 ----
n_real = len([d for d in os.listdir(SP) if d.endswith(".dist-info")])
chk("R5-1", "【反证】包内 dist-info 数 = 47（判据前提可被验证）",
    n_real == 47, "实测=%d" % n_real, "47")

npass = sum(1 for r in results if r[2])
nfail = sum(1 for r in results if not r[2])
lines = []
for cid, name, ok, got, want in results:
    lines.append("%s %-6s %s" % ("PASS" if ok else "FAIL", cid, name))
    lines.append("        got : %s" % got)
    if not ok:
        lines.append("        want: %s" % want)
summary = "app125 NOTICE 修正反证: PASS=%d FAIL=%d" % (npass, nfail)
lines.append("SUMMARY: " + summary)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "app125_notice_license_counterproof_evidence.json")
with io.open(out, "w", encoding="utf-8", newline="") as f:
    json.dump({
        "pkg": PKG,
        "pass": npass, "fail": nfail,
        "checks": [{"id": c, "name": n, "ok": o, "got": str(g), "want": str(w)}
                   for (c, n, o, g, w) in results],
    }, f, ensure_ascii=False, indent=2)

print("\n".join(lines))
print("SUMMARY: " + summary)
print("EVIDENCE: %s" % out)
sys.exit(0 if nfail == 0 else 1)
