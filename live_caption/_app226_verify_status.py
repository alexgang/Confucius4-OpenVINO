"""§226 写后**独立复核**（另起脚本，不复用写入脚本的内存对象）。

复核内容：
  ① 备份存在且其字节 == 写前原文件（写前备份与写后文件的差异必须恰好是本轮三处改动）
  ② 行尾风格不变（全 LF，无 CRLF 混入）
  ③ § 章节数 17 → 18（只 +1），且 §226 存在
  ④ `last_ack: APP-128` 仍唯一
  ⑤ 旧正文逐字未变：把本轮三处改动**反向还原**后必须逐字节等于写前备份
  ⑥ 归档件逐字节等于它所声称归档的那 2 条「最近更新」原文
  ⑦ 限额：≤40000 B / ≤300 行
  ⑧ §226 companion 存在、非空，且被 §226 指针行正确引用
"""
import hashlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, "status", "app", "STATUS_APP.md")
BAK = os.path.join(os.environ.get("TEMP", "/tmp"),
                   "STATUS_APP.bak_app226_2026-11-24_0041.md")
ARCH = os.path.join(REPO, "status", "archive", "STATUS_APP_recent_updates_20261124.md")
COMP = os.path.join(REPO, "status", "app", "STATUS_APP_sec226_detail_20261124.md")

fails = []


def ck(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ((" | " + extra) if extra else ""))
    if not cond:
        fails.append(name)


def main():
    new = open(P, "rb").read()
    old = open(BAK, "rb").read()
    nt = new.decode("utf-8")
    ot = old.decode("utf-8")

    print("§226 写后独立复核")
    ck("① 写前备份存在", os.path.exists(BAK), "%d B" % len(old))
    ck("① 备份大小 == 38958（写前原文件）", len(old) == 38958)

    ck("② 全 LF，无 CRLF 混入", new.count(b"\r\n") == 0 and old.count(b"\r\n") == 0)
    ck("② 裸 LF 数增加量 == 新增行数", new.count(b"\n") - old.count(b"\n") == 2,
       "%d -> %d" % (old.count(b"\n"), new.count(b"\n")))

    n_old = len(re.findall(r"^##\s+§", ot, re.M))
    n_new = len(re.findall(r"^##\s+§", nt, re.M))
    ck("③ § 章节数 17 -> 18", n_old == 17 and n_new == 18, "%d -> %d" % (n_old, n_new))
    ck("③ §226 标题行存在", "## §226 巡检" in nt)

    ck("④ last_ack: APP-128 唯一且未变", nt.count("last_ack: APP-128") == 1)

    # ⑤ 反向还原：去掉 §226 块 → 去掉新「最近更新」条目 → 指针行换回 2 条 → header 换回
    r = nt
    m = re.search(r"## §226 巡检.*\Z", r, re.S)
    ck("⑤ §226 块可定位", m is not None)
    r = r[:m.start()].rstrip("\n") + "\n" if m else r
    rec_new = [l for l in nt.split("\n") if l.startswith("> 🔴 2026-11-24 00:41 ｜ **巡检")]
    ck("⑤ 新「最近更新」条目可定位", len(rec_new) == 1)
    r = r.replace(rec_new[0] + "\n", "", 1) if rec_new else r
    pm = re.search(r"^> 🔴 本节 2 条较旧「最近更新」条目（🔴 2026-11-23 18:5x.*$", r, re.M)
    ck("⑤ 归档指针行可定位", pm is not None)
    if pm:
        arch_txt = open(ARCH, encoding="utf-8").read().rstrip("\n")
        r = r[:pm.start()] + arch_txt + r[pm.end():]
    r = r.replace("更新时间: 2026-11-24 00:41", "更新时间: 2026-11-23 21:56:37", 1)
    ck("⑤ 反向还原后与写前备份逐字节相同", r.encode("utf-8") == old)

    # ⑥ 归档件逐字节 == 它声称归档的 2 条原文
    arch_txt = open(ARCH, encoding="utf-8").read()
    old_lines = ot.split("\n")
    a1 = [l for l in old_lines if l.startswith("> 🔴 2026-11-23 18:5x ｜ **执行 APP-122…APP-127")]
    a2 = [l for l in old_lines if l.startswith("> 🔴 2026-11-23 12:2x ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-121）")]
    ck("⑥ 归档件含原文 2 条且逐字节相等",
       len(a1) == 1 and len(a2) == 1 and arch_txt == a1[0] + "\n" + a2[0] + "\n",
       "%d B" % len(arch_txt.encode("utf-8")))
    ck("⑥ 归档件 SHA256 与指针行声明一致",
       ("%s" % hashlib.sha256(arch_txt.encode("utf-8")).hexdigest()) in nt)

    ck("⑦ 限额 ≤40000 B / ≤300 行", len(new) <= 40000 and nt.count("\n") <= 300,
       "%d B / %d 行" % (len(new), nt.count("\n")))

    ck("⑧ §226 companion 存在且非空", os.path.exists(COMP) and os.path.getsize(COMP) > 100,
       "%d B" % (os.path.getsize(COMP) if os.path.exists(COMP) else 0))
    ck("⑧ 指针行正确引用 companion",
       "status/app/STATUS_APP_sec226_detail_20261124.md" in nt)

    print()
    print("RESULT:", "ALL PASS" if not fails else "FAIL: %r" % fails)
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
