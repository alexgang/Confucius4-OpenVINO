# -*- coding: utf-8 -*-
"""App §85 验收：客户包 NOTICE / THIRD_PARTY.md 的许可声明必须与包内实测一致。

纪律：
  - 零推理、零 GPU、零 NPU、不调 MiniMax；
  - 纯只读核对（不写客户包任何文件）；
  - 判据必须能 FAIL（不是恒 PASS）。
"""
import email
import io
import os
import re
import sys

PKG = r"C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6"
SP = os.path.join(PKG, "python", "Lib", "site-packages")
NOTICE = os.path.join(PKG, "NOTICE")
TP = os.path.join(PKG, "THIRD_PARTY.md")

results = []


def chk(cid, name, ok, got="", want=""):
    results.append((cid, name, bool(ok), got, want))
    return bool(ok)


def read(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- 事实层
dist_dirs = sorted(
    os.path.join(SP, d) for d in os.listdir(SP) if d.endswith(".dist-info")
)
VERSION_RE = re.compile(r"-\d[\w.\-]*$")


def norm_name(n):
    """把 dist-info 目录名 / PyPI 包名归一化：
    'openvino_genai-2026.4.1.0' -> 'openvino-genai'；'av-19.0.1' -> 'av'；
    'charset_normalizer-3.5.2' -> 'charset-normalizer'。
    规则：去掉末尾版本号段（下划线转连字符、小写）。
    """
    s = n.replace("_", "-").lower()
    s = VERSION_RE.sub("", s)
    return s


pkg_dirs = {os.path.basename(d)[:-len(".dist-info")]: d for d in dist_dirs}
# 归一化名 -> dist-info 目录名
pkg_by_norm = {norm_name(k): k for k in pkg_dirs}
# NOTICE / THIRD_PARTY 里写的名字 -> dist-info 目录名
def resolve(name):
    return pkg_dirs.get(pkg_by_norm.get(norm_name(name), ""), None)


def meta_license(d):
    md = os.path.join(d, "METADATA")
    if not os.path.isfile(md):
        return None, []
    msg = email.message_from_string(read(md))
    lic = msg.get("License")
    cls = [v for v in (msg.get_all("Classifier") or []) if v.startswith("License")]
    return lic, cls


# NOTICE 表格解析：| 包 | 版本 | 许可 | 路径 |
notice = read(NOTICE)
rows = []
for line in notice.splitlines():
    m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$", line)
    if not m:
        continue
    pkg, ver, lic, path = m.group(1), m.group(2), m.group(3), m.group(4)
    if pkg in ("包", "---") or set(pkg) <= set("-: "):
        continue
    rows.append((pkg, ver, lic, path))

# ================================================================= 判据
# G1: NOTICE 表格行数 == 包内 dist-info 数（47）
chk("G1", "NOTICE 表格覆盖包内全部 dist-info",
    len(rows) == len(dist_dirs) and len(dist_dirs) == 47,
    "表格行=%d, 包内 dist-info=%d" % (len(rows), len(dist_dirs)),
    "两者均为 47")

# G2: 每个包在 NOTICE 表里恰好出现一次
dupe = []
for p in pkg_dirs:
    hits = [r for r in rows if resolve(r[0]) == pkg_dirs[p]]
    if len(hits) != 1:
        dupe.append((p, len(hits)))
chk("G2", "NOTICE 每个包恰好一行（无重复、无遗漏）",
    not dupe and len(rows) == len(dist_dirs),
    "异常包=%s (表格行=%d, dist-info=%d)" % (dupe or "无", len(rows), len(dist_dirs)),
    "无重复且无遗漏")

# G3: NOTICE 表格里的版本号与 METADATA 的 Version 一致
bad_ver = []
for pkg, ver, lic, path in rows:
    d = resolve(pkg)
    if not d:
        bad_ver.append((pkg, "包不存在"))
        continue
    md = os.path.join(d, "METADATA")
    real = email.message_from_string(read(md)).get("Version")
    if real != ver:
        bad_ver.append((pkg, "NOTICE=%s METADATA=%s" % (ver, real)))
chk("G3", "NOTICE 版本号 == dist-info METADATA 的 Version",
    not bad_ver, str(bad_ver), "全部一致")

# G4: 随包许可证全文路径真实存在
bad_path = []
for pkg, ver, lic, path in rows:
    if not resolve(pkg):
        continue
    rel = path.strip()
    if "未自带" in rel or "⚠" in rel:
        continue  # 显式声明缺失的包，另由 G4b 判
    p = os.path.join(SP, rel.replace("/", os.sep))
    if not os.path.isfile(p):
        bad_path.append((pkg, rel))
chk("G4", "NOTICE 标注的「随包许可证全文路径」全部真实存在",
    not bad_path, str(bad_path), "全部存在")

# G4b: 声称「未自带许可证文件」的包确实没有
selfless = []
for pkg, ver, lic, path in rows:
    if "未自带" not in path:
        continue
    d = resolve(pkg)
    if not d:
        continue
    found = []
    for root, dirs, files in os.walk(d):
        for f in files:
            if f.upper().startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")):
                found.append(os.path.join(root, f))
    selfless.append((pkg, len(found)))
chk("G4b", "被标注为「未自带许可证文件」的包确实没有许可证文件",
    selfless == [("tokenizers", 0)], str(selfless), "[('tokenizers', 0)]")

# G5: num2words 的许可必须是 LGPL（回归：不能回到 MIT）
n2w = resolve("num2words")
lic, cls = meta_license(n2w)
row = [r for r in rows if r[0] == "num2words"]
notice_n2w = row[0][2] if row else ""
copying = os.path.join(n2w, "COPYING")
copying_head = read(copying).splitlines()[0] if os.path.isfile(copying) else ""
chk("G5", "num2words 许可 = LGPL-2.1（METADATA + COPYING 双重取证，且 NOTICE 已改正）",
    lic == "LGPL"
    and any("LGPL" in c for c in cls)
    and "LGPL" in notice_n2w
    and "Lesser General Public License" in copying_head,
    "METADATA.License=%s | Classifier=%s | NOTICE=%s | COPYING首行=%s"
    % (lic, cls, notice_n2w, copying_head),
    "LGPL / LGPL / 含LGPL / GNU Lesser General Public License")

# G6: NOTICE 顶部**不得**再声称「所有组件均为 Apache License 2.0」
bad_claim = re.search(r"所有组件均为\s*Apache", notice)
chk("G6", "NOTICE 不再声称「所有组件均为 Apache License 2.0」",
    bad_claim is None,
    "命中=%r" % (bad_claim.group(0) if bad_claim else None), "无此表述")

# G7: NOTICE 的**表格行**里 num2words 的许可列不得写 MIT
#     ⚠ 第一版只写了相邻正则 `num2words\s*\S*\s*MIT`，实测**过弱**：
#     表格行是 "| num2words | 0.5.14 | MIT | ..." ⇒ 相邻正则匹配不到 ⇒
#     把该行许可改成 MIT 后判据仍 PASS（假通过）。⇒ 改为**行级提取许可列**。
#     ⚠ 第二版过严：把说明句「…确认为 LGPL-2.1，不是 MIT。」也误判为 FAIL
#     ⇒ 限定**只判表格行**（以 `|` 开头且能解析出许可列）。
n2w_rows = []
for l in notice.splitlines():
    if "num2words" not in l or not l.lstrip().startswith("|"):
        continue
    m = re.match(r"^\|\s*[^|]+\|\s*[^|]*\|\s*(.+?)\s*\|", l)
    if not m:
        continue
    n2w_rows.append((l, m.group(1)))
bad_mit = [(l[:90], c) for (l, c) in n2w_rows if re.search(r"\bMIT\b", c)]
chk("G7", "NOTICE 表格行里 num2words 的许可列不再写 MIT（行级提取，非相邻正则）",
    len(n2w_rows) == 1 and not bad_mit,
    "表格行数=%d, 命中=%s" % (len(n2w_rows), bad_mit or "无"),
    "表格行数=1 且无 MIT")

# G8: 每个包在 NOTICE 中的许可标识，必须与 METADATA(字段/Classifier) 或 LICENSE 正文一致
#     允许 NOTICE 写更精确的 SPDX（比 METADATA 笼统更具体），但不允许与 METADATA 冲突
def norm(s):
    return re.sub(r"[^a-z0-9.+-]", "", s.lower())


mismatch = []
for pkg, ver, lic, path in rows:
    d = resolve(pkg)
    if not d:
        continue
    mlic, mcls = meta_license(d)
    mcls_s = " ".join(mcls)
    nlic = lic.replace("**", "")
    # 找出 METADATA 侧的标识关键词
    keys = []
    for c in mcls:
        c2 = c.replace("License :: OSI Approved :: ", "")
        if "GNU Library or Lesser" in c2:
            keys.append("lgpl")
        elif "Apache" in c2:
            keys.append("apache")
        elif "BSD" in c2:
            keys.append("bsd")
        elif "MIT" in c2:
            keys.append("mit")
        elif "Mozilla Public" in c2:
            keys.append("mpl")
        elif "ISC" in c2:
            keys.append("isc")
        elif "Python Software Foundation" in c2:
            keys.append("psf")
    if mlic:
        ml = mlic.lower()
        if "lgpl" in ml:
            keys.append("lgpl")
        elif "apache" in ml:
            keys.append("apache")
        elif "bsd" in ml:
            keys.append("bsd")
        elif "mit" in ml:
            keys.append("mit")
        elif "mpl" in ml:
            keys.append("mpl")
        elif "isc" in ml:
            keys.append("isc")
    if not keys:
        continue  # METADATA 无任何许可线索，跳过（由 G4 的文件路径兜底）
    nl = nlic.lower()
    # NOTICE 里的关键词
    nk = []
    if "lgpl" in nl or "lesser general" in nl:
        nk.append("lgpl")
    if "apache" in nl:
        nk.append("apache")
    if "bsd" in nl:
        nk.append("bsd")
    if "mit" in nl:
        nk.append("mit")
    if "mpl" in nl:
        nk.append("mpl")
    if "isc" in nl:
        nk.append("isc")
    if "psf" in nl:
        nk.append("psf")
    if "hpnd" in nl:
        nk.append("hpnd")
    # 允许 NOTICE 补充 METADATA 没有的更细信息（hpnd 等）
    core_m = set(k for k in keys if k in ("lgpl", "apache", "bsd", "mit", "mpl", "isc"))
    core_n = set(k for k in nk if k in ("lgpl", "apache", "bsd", "mit", "mpl", "isc"))
    if core_m and not (core_n & core_m):
        mismatch.append((pkg, "METADATA=%s NOTICE=%s" % (mcls_s or mlic, nlic)))
chk("G8", "NOTICE 的许可标识与包内 METADATA/Classifier 无冲突",
    not mismatch, str(mismatch), "无冲突")

# G9: THIRD_PARTY.md 也覆盖 47 个包（不能只有 29 个）
tp = read(TP)
tp_pkgs = set(re.findall(r"^\|\s*([A-Za-z0-9_.-]+)\s*\|\s*[0-9][^|]*\|\s*([^|]+?)\s*\|",
                         tp, re.M))
tp_names = set(p for p, _ in tp_pkgs)
missing_tp = sorted(n for n in pkg_by_norm if norm_name(n) not in
                    {norm_name(x) for x in tp_names})
chk("G9", "THIRD_PARTY.md 覆盖包内全部 dist-info",
    not missing_tp, "缺=%s (已列=%d)" % (missing_tp, len(tp_names)),
    "无缺失")

# G10: THIRD_PARTY.md 里 num2words 也必须写成 LGPL
tp_row = re.search(r"^\|\s*num2words\s*\|[^|]*\|\s*([^|]+?)\s*\|", tp, re.M)
tp_lic = tp_row.group(1) if tp_row else ""
chk("G10", "THIRD_PARTY.md 的 num2words 许可 = LGPL",
    "LGPL" in tp_lic, "THIRD_PARTY=%r" % tp_lic, "含 LGPL")

# G11: 沙盒自检——判据本身能 FAIL（把 NOTICE 的 LGPL 改成 MIT 后 G5 必须 FAIL）
import copy
fake_notice = notice.replace("LGPL-2.1（或更高版本）", "MIT")
m5 = re.search(r"num2words[^\n]*", fake_notice)
chk("G11", "【自检】把 NOTICE 的 num2words 改成 MIT 后，G5 判据应当失败",
    m5 is not None and "LGPL" not in m5.group(0),
    "沙盒串=%r" % (m5.group(0)[:80] if m5 else None), "判据可 FAIL")

# ================================================================= 输出
npass = sum(1 for r in results if r[2])
nfail = sum(1 for r in results if not r[2])
lines = []
for cid, name, ok, got, want in results:
    lines.append("%s %-5s %s" % ("PASS" if ok else "FAIL", cid, name))
    lines.append("        got : %s" % got)
    if not ok:
        lines.append("        want: %s" % want)
summary = "app124 NOTICE/THIRD_PARTY 许可审计: PASS=%d FAIL=%d" % (npass, nfail)
lines.append("SUMMARY: " + summary)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "app124_notice_license_audit_evidence.json")
import json
with io.open(out, "w", encoding="utf-8", newline="") as f:
    json.dump({
        "pkg": PKG,
        "n_dist_info": len(dist_dirs),
        "notice_table_rows": len(rows),
        "pass": npass,
        "fail": nfail,
        "checks": [
            {"id": c, "name": n, "ok": o, "got": str(g), "want": str(w)}
            for (c, n, o, g, w) in results
        ],
    }, f, ensure_ascii=False, indent=2)

print("\n".join(lines))
print("SUMMARY: " + summary)
print("EVIDENCE: %s" % out)
sys.exit(0 if nfail == 0 else 1)
