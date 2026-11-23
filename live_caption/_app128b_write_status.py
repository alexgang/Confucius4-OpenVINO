"""APP-128 补充轮（§225）—— 定点写 status/app/STATUS_APP.md。

做四件事（每件都可独立还原）：
  E1  第 4 行「更新时间」＝ PowerShell `Get-Date` 实测值（不推算）。
  E2  「最近更新」小节**最前面**插入本轮 1 条。
  E3  「最近更新」小节里 2 条较旧条目（APP-121 / APP-120）**整块逐字归档**
      ⇒ status/archive/STATUS_APP_recent_updates_20261123.md，活文档原位置换成 1 行指针。
  E4  末尾追加 `## §225` 标题行 ＋ 正文指针行。

纪律（照 MEMORY 一、）：
  * 开工先备份（%TEMP%/*.bak）。
  * 写前在**内存新文本**上跑真不变量 ＋ **还原式复核**（把本轮改动逐条还原后须逐字节等于原字节）。
  * 临时文件 → os.replace；写后再由**另一个脚本**独立复核。
  * 真不变量：行尾风格不变（LF-only）、`last_ack` 唯一且不变、旧正文逐字未变、章节数只 +1。

幂等：若 §225 标题行已存在 ⇒ 明确拒绝（不重复插入）。
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "status", "app", "STATUS_APP.md")
ARCHIVE = os.path.join(REPO, "status", "archive", "STATUS_APP_recent_updates_20261123.md")
COMPANION = "status/app/STATUS_APP_sec225_detail_20261123.md"

# 本轮「最近更新」条目（插入到小节最前）
NEW_UPDATE = (
    "> \U0001f534 2026-11-23 21:5x ｜ **APP-128 补充（reviewer 12:52:07Z 邮件）—— 已单独补发 e2e7 三臂表**"
    "（`last_ack` 仍 **APP-128**，本条**不是新编号**）："
    "\U0001f7e2 **§0 复核**：reviewer 判 APP-128「**通过**」（md5／14/14+18/18+回归／e2e9 三臂 seg IR=fp16-w5／"
    "提交 `3573b2d`／两个 ogg 附件均收到）；`clone_s2` 的 `n_speakers=0` **判为正常、不用处理**｜"
    "\U0001f7e2 **§1 唯一要求**＝上一封 STATUS 邮件正文中间被截断 ⇒ **单独补发 e2e7 三臂表**"
    "（reviewer 明写「不要做别的；v2.6 交接等这张表到了再发」）｜"
    "\U0001f7e2 **§2 表已发出**＝`msg_52Ta35TCkxRJS1CDLmdVZbCF5yDGbx4gPdFrKHNlMH7bJw`（13:53:36Z），"
    "主题 `[C4][A][STATUS][APP] APP-128 e2e7 三臂表`，正文 **462 B**（SHA256 `3fc385027894c62d…`），"
    "**已发箱回执逐行核对＝8 行齐全、未截断**（正针对上轮投诉点）｜"
    "\U0001f7e2 **§3 数字双路复核**＝脚本解析（并回原始 JSON 文本逐字命中）＋ 独立 raw 切片，两路逐字段一致｜"
    "\U0001f7e2 **§4 入库完整性**＝实发正文文件 `live_caption/_app128b_email_body.txt`（与实发**逐字节相同**）＋"
    "证据 json `results/app/app128b_e2e7_table_evidence.json` ＋ 产生脚本 `live_caption/_app128b_e2e7_table.py` ＋ "
    "**reviewer 复算底本** `results/app/app128b_e2e7_src/*.json`（3 份源 json 原样入库）｜"
    "\U0001f534 **§5 纪律**＝未打包／未改客户包／未跑推理·计时（未取 MACHINE_LOCK）／未调 MiniMax／未连 B 机／"
    "**未进 v2.6**（等这张表到达）／未改纠偏文件（收尾四项指纹逐字一致 ⇒ SHA 零改动）｜"
    "**本条需等 reviewer 复核**"
)

# 末尾追加的 §225 块
SEC225_TITLE = (
    "## §225 执行 **APP-128 补充**（`last_ack` 仍 **APP-128**，2026-11-23 21:5x）｜"
    "\U0001f7e2 **e2e7 三臂表已单独补发**（正文未截断）"
)
SEC225_PTR = (
    "> \U0001f534 **本节正文全文 ⇒ `" + COMPANION + "`**"
    "（含 §0–§8：纠偏邮件原文摘录与 message_id、六通道复核、三臂原始字段与源文件 SHA256/字节/mtime、"
    "双路复核结果、实发邮件 message_id 与正文 SHA256、入库清单、收尾四项指纹、纪律与下一轮）"
)

# 「最近更新」里要归档的 2 条（按出现顺序：APP-121、APP-120）
ARCHIVE_TAGS = ["2026-11-23 10:39", "2026-11-22 16:54"]


def get_date():
    out = subprocess.check_output(
        ["powershell", "-NoProfile", "-Command", "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"],
        text=True, stderr=subprocess.STDOUT)
    return out.strip().splitlines()[-1].strip()


def main():
    orig = open(STATUS, "rb").read()
    orig_text = orig.decode("utf-8")
    lines = orig_text.split("\n")

    # ---- 幂等守卫 ----
    if any(l.startswith("## §225") for l in lines):
        print("拒绝：§225 已存在（幂等守卫命中）")
        return 2

    # ---- 定位要归档的 2 条（**只在「最近更新」小节内**用时间戳标签精确定位，命中必须恰好 1 条）----
    upd_start = lines.index("## 最近更新")
    upd_end = len(lines)
    for i in range(upd_start + 1, len(lines)):
        if lines[i].startswith("## "):
            upd_end = i
            break
    idxs = []
    for tag in ARCHIVE_TAGS:
        hits = [i for i in range(upd_start + 1, upd_end) if l_tag(lines[i], tag)]
        if len(hits) != 1:
            print("拒绝：标签 %r 在「最近更新」小节内命中 %d 条（应为 1）" % (tag, len(hits)))
            return 3
        idxs.append(hits[0])
    if idxs[0] > idxs[1]:
        print("拒绝：归档条目顺序异常")
        return 3
    if idxs[1] - idxs[0] != 1:
        print("拒绝：两条待归档条目不相邻（%d,%d）" % (idxs[0], idxs[1]))
        return 3
    archived_lines = [lines[i] for i in idxs]

    # ---- 备份 ----
    stamp = time.strftime("%Y%m%d_%H%M%S")
    bak = os.path.join(tempfile.gettempdir(), "STATUS_APP.bak_app128b_%s.md" % stamp)
    shutil.copyfile(STATUS, bak)
    print("备份 →", bak, os.path.getsize(bak), "B")

    # ---- E3a：先写归档文件（正文 = 2 条逐字原文，不加任何头尾）----
    arch_bytes = ("\n".join(archived_lines) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(ARCHIVE), exist_ok=True)
    with open(ARCHIVE, "wb") as f:
        f.write(arch_bytes)
    arch_sha = hashlib.sha256(arch_bytes).hexdigest()
    print("归档 →", ARCHIVE, len(arch_bytes), "B  sha256", arch_sha)

    ptr = (
        "> \U0001f534 本节 2 条较旧「最近更新」条目（\U0001f534 2026-11-23 10:39「执行 APP-121」／"
        "\U0001f534 2026-11-22 16:54「执行 APP-120」）原文已**整块逐字归档** ⇒ "
        "`status/archive/STATUS_APP_recent_updates_20261123.md`（%d B／块 SHA256 `%s`）；"
        "**原文一字未删、未改**。" % (len(arch_bytes), arch_sha)
    )

    # ---- 构造新文本（内存）----
    now = get_date()
    new = list(lines)

    # E3：把**相邻的 2 条**换成**1 行**指针
    new[idxs[0]:idxs[1] + 1] = [ptr]
    # E2：插入新的「最近更新」条目（小节标题行之后）
    new.insert(upd_start + 1, NEW_UPDATE)
    # E1：更新时间
    ts_idx = [i for i, l in enumerate(new) if l.startswith("更新时间:")]
    if len(ts_idx) != 1:
        print("拒绝：「更新时间」行命中 %d 条" % len(ts_idx))
        return 3
    new[ts_idx[0]] = "更新时间: " + now
    # E4：末尾追加 §225（在文件末尾的空行之前）
    assert new[-1] == "", "文件末尾结构异常"
    new = new[:-1] + ["", SEC225_TITLE, SEC225_PTR, ""]
    new_text = "\n".join(new)
    new_bytes = new_text.encode("utf-8")

    # ---- 真不变量（内存态）----
    checks = []

    def ck(name, cond, extra=""):
        checks.append((name, bool(cond), extra))

    ck("行尾风格不变（LF-only）", b"\r\n" not in new_bytes and new_bytes.count(b"\n") == orig.count(b"\n") + 3)
    ck("last_ack 唯一且未变", new_text.count("last_ack: APP-128") == 1 and "last_ack: APP-128\n" in new_text)
    ck("`## §` 章节数只 +1", len(re.findall(r"(?m)^## §", new_text)) == len(re.findall(r"(?m)^## §", orig_text)) + 1)
    ck("总字节 < 40000（APP-052④）", len(new_bytes) < 40000, "%d B" % len(new_bytes))
    ck("行数 <= 300", len(new) <= 300, "%d" % len(new))
    ck("归档文件 2 条原文逐字保留", all(a in arch_bytes.decode("utf-8") for a in archived_lines))
    ck("活文档已不含这 2 条原文（已归档）", all(a not in new_text for a in archived_lines))
    ck("§225 标题行存在", any(l.startswith("## §225") for l in new))
    ck("§225 指针行含 companion 路径", COMPANION in new_text)

    # ---- 还原式复核：把本轮 4 处改动逐条还原 ⇒ 必须逐字节等于原字节 ----
    r = list(new)
    # 还原 E4
    k = [i for i, l in enumerate(r) if l == SEC225_TITLE][0]
    assert r[k - 1] == "" and r[k + 1] == SEC225_PTR and r[k + 2] == ""
    del r[k - 1:k + 2]
    # 还原 E2
    r.remove(NEW_UPDATE)
    # 还原 E3
    j = [i for i, l in enumerate(r) if l == ptr][0]
    r[j:j + 1] = archived_lines
    # 还原 E1
    ti = [i for i, l in enumerate(r) if l.startswith("更新时间:")][0]
    r[ti] = lines[ts_idx[0]]
    restored = "\n".join(r).encode("utf-8")
    ck("还原式复核：逐字节等于原文件", restored == orig,
       "restored %d B vs orig %d B" % (len(restored), len(orig)))

    bad = [c for c in checks if not c[1]]
    for n, ok, ex in checks:
        print(("  PASS  " if ok else "  FAIL  ") + n + (("  " + ex) if ex else ""))
    if bad:
        print("自检失败 ⇒ 源文件零改动")
        return 4

    # ---- 写盘：临时文件 → os.replace ----
    tmp = STATUS + ".tmp_app128b"
    with open(tmp, "wb") as f:
        f.write(new_bytes)
    os.replace(tmp, STATUS)
    print("写入完成：%s  %d → %d B" % (STATUS, len(orig), len(new_bytes)))
    print("更新时间 =", now)
    return 0


def l_tag(line, tag):
    return tag in line


if __name__ == "__main__":
    sys.exit(main())
