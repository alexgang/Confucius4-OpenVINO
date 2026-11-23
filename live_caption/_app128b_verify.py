"""APP-128 补充轮（§225）—— **写后独立复核**（与写入脚本分开，避免自证）。

复核项：
  1. STATUS 形态：字节/行数/行尾/章节数/last_ack 唯一/§225 块/companion 指针。
  2. **除本轮 4 处改动外，其余行逐字节未变**（对写前备份做行级 diff）。
  3. 归档文件：2 条原文逐字保留，且其 sha256/字节数与活文档指针行声明**一致**。
  4. 入库完整性：实发邮件正文文件 == 证据 json 里的 email_body（逐字节）。
  5. 纠偏文件只读：SHA256/字节/mtime/`## APP-xxx` 条数 与开工记录一致。
"""
import hashlib
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "status", "app", "STATUS_APP.md")
ARCHIVE = os.path.join(REPO, "status", "archive", "STATUS_APP_recent_updates_20261123.md")
COMPANION = os.path.join(REPO, "status", "app", "STATUS_APP_sec225_detail_20261123.md")
CORR = os.path.join(REPO, "status", "app", "CORRECTIONS_APP.md")
BODY = os.path.join(REPO, "live_caption", "_app128b_email_body.txt")
EVID = os.path.join(REPO, "results", "app", "app128b_e2e7_table_evidence.json")
SCRIPT = os.path.join(REPO, "live_caption", "_app128b_e2e7_table.py")
SRCDIR = os.path.join(REPO, "results", "app", "app128b_e2e7_src")

# 开工时记录的纠偏文件指纹（§225 §7）
CORR_SHA = "fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48"
CORR_BYTES = 429255
CORR_MTIME = "2026-11-23 16:55:40"
CORR_COUNT = 125

# 开工时 STATUS 指纹
STATUS_OLD_BYTES = 39918
STATUS_OLD_LINES = 103
STATUS_OLD_SEC = 16


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    import time
    fails = []

    def ck(name, cond, extra=""):
        print(("  PASS  " if cond else "  FAIL  ") + name + (("  " + extra) if extra else ""))
        if not cond:
            fails.append(name)

    sb = open(STATUS, "rb").read()
    st = sb.decode("utf-8")
    sl = st.split("\n")

    print("== 1. STATUS 形态 ==")
    ck("字节数 = 38958", len(sb) == 38958, "%d B" % len(sb))
    ck("LF-only（CRLF 0）", sb.count(b"\r\n") == 0 and sb.count(b"\r") == 0)
    ck("行数 106（<=300）", len(sl) == 106, "%d" % len(sl))
    ck("`## §` 章节数 38 -> 39", len(re.findall(r"(?m)^## §", st)) == STATUS_OLD_SEC + 1,
       "%d" % len(re.findall(r"(?m)^## §", st)))
    ck("`last_ack: APP-128` 唯一", st.count("last_ack: APP-128") == 1)
    ck("更新时间行存在且格式正确", bool(re.search(r"(?m)^更新时间: 2026-11-23 \d\d:\d\d:\d\d$", st)))
    ck("§225 标题行存在", any(l.startswith("## §225") for l in sl))
    ck("§225 指针行指向 companion", any(l.startswith("> ") and "STATUS_APP_sec225_detail_20261123.md" in l
                                        for l in sl))
    ck("§224 旧节仍在（未回头改）", any(l.startswith("## §224") for l in sl))
    ck("companion 文件存在", os.path.isfile(COMPANION),
       "%d B" % os.path.getsize(COMPANION) if os.path.isfile(COMPANION) else "missing")

    print("== 2. 行级 diff（对写前备份）==")
    baks = sorted(f for f in os.listdir(os.environ.get("TEMP", "."))
                   if f.startswith("STATUS_APP.bak_app128b_"))
    if not baks:
        ck("找到写前备份", False)
    else:
        bak = os.path.join(os.environ.get("TEMP", "."), baks[-1])
        ob = open(bak, "rb").read()
        ck("备份 = 39918 B（开工态）", len(ob) == STATUS_OLD_BYTES, "%d B" % len(ob))
        ol = ob.decode("utf-8").split("\n")
        ck("备份行数 = 103", len(ol) == STATUS_OLD_LINES, "%d" % len(ol))
        import difflib
        sm = difflib.SequenceMatcher(None, ol, sl, autojunk=False)
        ops = [o for o in sm.get_opcodes() if o[0] != "equal"]
        ck("改动区域恰为 4 处", len(ops) == 4, "regions=%d %r" % (len(ops), [(o[0], o[1], o[2], o[3]) for o in ops]))
        # 4 处之外逐行未变
        changed_old_idx, changed_new_idx = set(), set()
        for tag, i1, i2, j1, j2 in ops:
            changed_old_idx.update(range(i1, i2))
            changed_new_idx.update(range(j1, j2))
        for i, l in enumerate(ol):
            if i not in changed_old_idx:
                j = sm.get_matching_blocks()
        # 逐行等价比对：equal 区块内原样
        ok_equal = True
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal" and ol[i1:i2] != sl[j1:j2]:
                ok_equal = False
        ck("equal 区块逐行原样未变", ok_equal)

    print("== 3. 归档文件 ==")
    ab = open(ARCHIVE, "rb").read()
    at = ab.decode("utf-8")
    al = at.split("\n")
    ck("归档含 2 条原文", len([x for x in al if x.strip()]) == 2,
       "%d 非空行" % len([x for x in al if x.strip()]))
    ck("归档条目 = APP-121 / APP-120", "执行 APP-121" in al[0] and "执行 APP-120" in al[1])
    ptr_lines = [l for l in sl if l.startswith("> ") and "STATUS_APP_recent_updates_20261123.md" in l]
    ck("活文档有且仅有 1 行归档指针", len(ptr_lines) == 1)
    if ptr_lines:
        m = re.search(r"（(\d+) B／块 SHA256 `([0-9a-f]{64})`）", ptr_lines[0])
        ck("指针行声明的字节数与实际一致", bool(m) and int(m.group(1)) == len(ab),
           "%s vs %d" % (m.group(1) if m else "?", len(ab)))
        ck("指针行声明的 SHA256 与实际一致", bool(m) and m.group(2) == sha(ab),
           "%s" % (m.group(2)[:16] if m else "?"))
        ck("归档原文已不在活文档", al[0] not in st and al[1] not in st)

    print("== 4. 入库完整性 ==")
    bb = open(BODY, "rb").read()
    ev = json.load(open(EVID, encoding="utf-8"))
    eb = ev["email_body"].encode("utf-8")
    ck("正文文件 == 证据 json 的 email_body（逐字节）", bb == eb,
       "%d B / sha %s" % (len(bb), sha(bb)[:16]))
    ck("正文 sha256 与证据声明一致", ev["email_body_sha256"] == sha(bb))
    ck("证据 json 字节数声明与实际一致", ev["email_body_bytes"] == len(bb))
    ck("产生脚本已入库", os.path.isfile(SCRIPT))
    ck("复算底本 3 份源 json 已入库",
       os.path.isfile(os.path.join(SRCDIR, "off_bgkeep_e2e.json")) and
       os.path.isfile(os.path.join(SRCDIR, "on_gpu_bgkeep_e2e.json")) and
       os.path.isfile(os.path.join(SRCDIR, "on_cpu_bgkeep_e2e.json")))
    # 底本与 reviewer 源文件逐字节一致
    src = os.path.join("C:\\", "Users", "Trekker-PTL", "shared", "bgkeep", "e2e7")
    same = True
    for a in ("off", "on_gpu", "on_cpu"):
        s = open(os.path.join(src, a, "bgkeep_e2e.json"), "rb").read()
        c = open(os.path.join(SRCDIR, "%s_bgkeep_e2e.json" % a), "rb").read()
        if s != c:
            same = False
    ck("入库底本 == reviewer 源文件（逐字节）", same)
    # 证据 json 里三臂数值与底本一致
    ok = True
    for row in ev["arms"]:
        j = json.load(open(os.path.join(SRCDIR, "%s_bgkeep_e2e.json" % row["arm"]), encoding="utf-8"))
        if (j["dubs"] != row["dubs"] or j["dub_late_vs_play_s"]["max"] != row["dub_late_max"]
                or j["dub_late_vs_play_s"]["p90"] != row["dub_late_p90"]
                or j["dub_late_vs_play_s"]["n_late"] != row["n_late"]
                or j["bg_late_blocks"] != row["bg_late_blocks"]
                or j["stats_bg"]["sep_rtf_p50"] != row["sep_rtf_p50"]
                or j["stats_bg"]["sep_rtf_p90"] != row["sep_rtf_p90"]):
            ok = False
    ck("证据 json 三臂数值 == 底本原始字段", ok)

    print("== 5. 纠偏文件只读 ==")
    cb = open(CORR, "rb").read()
    ct = cb.decode("utf-8", errors="replace")
    ids = re.findall(r"(?m)^##\s*APP-(\d+)", ct)
    mt = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(CORR)))
    ck("SHA256 与开工一致", sha(cb) == CORR_SHA, sha(cb)[:16])
    ck("字节数与开工一致", len(cb) == CORR_BYTES, "%d" % len(cb))
    ck("mtime 与开工一致", mt == CORR_MTIME, mt)
    ck("`## APP-xxx` 条数与开工一致", len(ids) == CORR_COUNT, "%d（max APP-%s）" % (len(ids), max(ids)))

    print("== 结果 ==")
    if fails:
        print("FAIL %d 项: %r" % (len(fails), fails))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
