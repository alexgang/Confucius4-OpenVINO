"""§226 写 STATUS_APP.md（三件套定点写入：备份 → 内存真不变量 + 还原式复核 → os.replace → 写后独立复核）。

纪律（MEMORY §一）：
  * 备份先落 %TEMP%/*.bak
  * 写前在**内存新文本**上跑真不变量（行尾风格不变／章节数 +1／旧正文逐字未变／字节等长只针对被替换行）
    ＋ **还原式复核**（把本轮改动按「编辑区间替换后的长度」反向还原 ⇒ 必须逐字节等于写前备份）
  * 临时文件 → os.replace（避免 open(p,'w') 先截断）
  * 写后**另起脚本**独立复核 + numstat
"""
import hashlib
import os
import re
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, "status", "app", "STATUS_APP.md")
TS = "2026-11-24 00:41"

HEADER_OLD = "更新时间: 2026-11-23 21:56:37"
HEADER_NEW = "更新时间: " + TS

# 新增的「最近更新」条目（放在「## 最近更新」之后、作为最新一条）
RECENT_NEW = (
    "> 🔴 " + TS + " ｜ **巡检（无新 reviewer 纠偏，`last_ack` 仍 **APP-128**）＋ 接续上一会话（TAKEOVER）"
    "闭合其遗留的「入库字节不一致」缺陷**：🟢 **§0 六通道复核无新 App 纠偏**（局域网 125 条/max APP-127；"
    "QQ 最新 App 封仍是 APP-128 补充＝已执行；spam 0）｜🔴 **§1 上一会话心跳断了 63 min ⇒ TAKEOVER**"
    "（note=`step4: found autocrlf byte-divergence in committed reviewer source jsons`）｜🟢 **§2 根因**"
    "（`core.autocrlf=true` ＋ 无 `.gitattributes` ⇒ CRLF 被规整成 LF 入库 ⇒ **入库 blob ≠ reviewer 原件**）｜"
    "🟢 **§4 修法**（目录局部 `.gitattributes` 的 `*.json -text` ＋ `git add --renormalize`）｜🟢 **§5 四路复核 PASS**"
    "（工作区＝原件＝index blob＝公布 SHA256，3/3）＋ **真跑 `git -c core.autocrlf=false clone` 复现公布 SHA256，3/3**｜"
    "🟢 **反证组 PASS**（修前提交同口径 **3/3 对不上** ⇒ 修法承重）｜🔴 **§6 更大面如实报告**"
    "（全仓 854 个 divergent 文件，活文档命中 5 份 ⇒ 本轮只修 reviewer 源文件 3 份；**其余不动、留待 reviewer 裁定**）｜"
    "🔴 **§7 提交 `73a2e22`**｜**未打包／未改客户包／未跑推理·计时／未调 MiniMax／未连 B 机／未改纠偏文件**｜"
    "**本条需等 reviewer 复核**"
)

# 追加到文末的 §226 标题行 + 指针行
SECTION = (
    "## §226 巡检（**无新 reviewer 纠偏**，`last_ack` 仍 **APP-128**）｜🔴 **接续上一会话（TAKEOVER）并闭合其遗留的"
    "「入库字节不一致」缺陷**｜🟢 **已修：reviewer 复算底本逐字节入库，clone 可复现公布的 SHA256**｜🟢 **反证组证明修法承重**｜"
    "**本条需等 reviewer 复核**\n"
    "> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec226_detail_20261124.md`**"
    "（含 §0 六通道复核、§1 TAKEOVER 交接、§2 根因实测、§3 影响面、§4 修法、§5 四路复核＋反证组、"
    "§6 更大面范围如实报告、§7 提交、§8 纪律、§9 待裁定）\n"
)

# 本轮要归档的 2 条较旧「最近更新」条目（唯一锚点，命中才动）
ARCHIVE_OLD1 = "> 🔴 2026-11-23 18:5x ｜ **执行 APP-122…APP-127（last_ack=APP-121 → **APP-127**）**"
ARCHIVE_OLD2 = "> 🔴 2026-11-23 12:2x ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-121）＋ 接续上一会话（TAKEOVER）闭合 4 处半交付**"
ARCHIVE_REL = "status/archive/STATUS_APP_recent_updates_20261124.md"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    orig = open(P, "rb").read()
    text = orig.decode("utf-8")
    bak = os.path.join(tempfile.gettempdir(), "STATUS_APP.bak_app226_%s.md" % TS.replace(":", "").replace(" ", "_"))
    shutil.copyfile(P, bak)
    print("backup:", bak, os.path.getsize(bak), "B")

    # ---------- 在内存里构造新文本 ----------
    assert text.count(HEADER_OLD) == 1, "header 锚点不唯一"
    assert "## 最近更新\n" in text, "缺「## 最近更新」"
    # 尾部锚点：最后一节必须是 §225（§226 追加在它之后）
    tail_anchor = "## §225 执行 **APP-128 补充**"
    assert tail_anchor in text, "尾部锚点不符（未找到 §225 标题行）"
    assert text.rindex(tail_anchor) > text.rindex("## §224"), "§225 标题行位置异常"

    # 1) 改 header 更新时间（唯一命中）
    new = text.replace(HEADER_OLD, HEADER_NEW, 1)
    hdr_pos = new.index(HEADER_NEW)

    # 2) 插入「最近更新」新条目（紧跟 "## 最近更新\n" 之后）
    anchor = "## 最近更新\n"
    ai = new.index(anchor) + len(anchor)
    new = new[:ai] + RECENT_NEW + "\n" + new[ai:]

    # 2b) APP-052④ 压缩：把 2 条较旧「最近更新」条目**整块逐字**归档，活文档换成 1 行指针
    old_lines = new.split("\n")
    idx1 = [i for i, l in enumerate(old_lines) if l.startswith(ARCHIVE_OLD1)]
    idx2 = [i for i, l in enumerate(old_lines) if l.startswith(ARCHIVE_OLD2)]
    if len(idx1) != 1 or len(idx2) != 1:
        print("SELF-CHECK FAIL => 源文件零改动")
        print("  归档锚点不唯一：ARCHIVE_OLD1=%d ARCHIVE_OLD2=%d" % (len(idx1), len(idx2)))
        return 2
    i1, i2 = idx1[0], idx2[0]
    if i2 != i1 + 1:
        print("SELF-CHECK FAIL => 源文件零改动")
        print("  两条待归档条目不相邻：%d / %d" % (i1, i2))
        return 2
    archived_block = old_lines[i1] + "\n" + old_lines[i2] + "\n"
    # 归档件（write-once：已存在则拒绝覆盖）
    arch_path = os.path.join(REPO, "status", "archive", "STATUS_APP_recent_updates_20261124.md")
    if os.path.exists(arch_path):
        print("SELF-CHECK FAIL => 源文件零改动")
        print("  归档件已存在，拒绝覆盖：", arch_path)
        return 2
    with open(arch_path, "wb") as f:
        f.write(archived_block.encode("utf-8"))
    arch_sha = sha(open(arch_path, "rb").read())
    arch_bytes = os.path.getsize(arch_path)
    print("archive written:", arch_path, arch_bytes, "B sha256:", arch_sha)
    pointer = (
        "> 🔴 本节 2 条较旧「最近更新」条目（🔴 2026-11-23 18:5x「执行 APP-122…APP-127」／"
        "🔴 2026-11-23 12:2x「巡检＋接续上一会话闭合 4 处半交付」）原文已**整块逐字归档** ⇒ `%s`"
        "（%d B／块 SHA256 `%s`）；**原文一字未删、未改**。" % (ARCHIVE_REL, arch_bytes, arch_sha)
    )
    new_lines = new.split("\n")
    new_lines[i1:i2 + 1] = [pointer]
    new = "\n".join(new_lines)

    # 3) 文末追加 §226（保持文件以换行结尾）
    if not new.endswith("\n"):
        new += "\n"
    new = new + SECTION

    nb = new.encode("utf-8")

    # ---------- 真不变量（对内存新文本） ----------
    errs = []
    # a) 行尾风格不变（原文件全 LF ⇒ 新文件必须全 LF）
    if orig.count(b"\r\n") != 0 and nb.count(b"\r\n") != 0:
        errs.append("CRLF 风格被改动")
    if nb.count(b"\r\n") != 0:
        errs.append("新文本混入了 CRLF")
    # b) 章节数 +1
    n_old = len(re.findall(r"^##\s+§", text, re.M))
    n_new = len(re.findall(r"^##\s+§", new, re.M))
    if n_new != n_old + 1:
        errs.append("章节数不是 +1：%d -> %d" % (n_old, n_new))
    # c) last_ack 唯一且未变
    if text.count("last_ack: APP-128") != 1 or new.count("last_ack: APP-128") != 1:
        errs.append("last_ack 字段异常")
    # d) 旧正文逐字未变（除 header 那 1 行 + 新增块 + 归档指针替换）
    stripped = new.replace(RECENT_NEW + "\n", "", 1)
    stripped = stripped.replace(SECTION, "", 1)
    stripped = stripped.replace(HEADER_NEW, HEADER_OLD, 1)
    # 指针行还原成原来的 2 条归档条目
    stripped = stripped.replace(pointer, archived_block.rstrip("\n"), 1)
    if stripped != text:
        errs.append("旧正文被改动（还原后与原文不等）")
    # d2) 归档块必须逐字节等于原文件里那两行
    if archived_block != old_lines[i1] + "\n" + old_lines[i2] + "\n":
        errs.append("归档块与原文不等")
    # e) 限额
    if len(nb) > 40000:
        errs.append("超过 40000 B 限额：%d" % len(nb))
    if new.count("\n") > 300:
        errs.append("超过 300 行限额：%d" % new.count("\n"))

    # ---------- 还原式复核（独立实现：按长度反推区间还原） ----------
    # 从 new 里反向切掉三处新增/替换，必须逐字节等于 orig
    r = nb
    assert SECTION.encode("utf-8") in r
    r = r[:r.rindex(SECTION.encode("utf-8"))]           # 去掉文末 §226
    rec_b = (RECENT_NEW + "\n").encode("utf-8")
    assert rec_b in r
    r = r[:r.index(rec_b)] + r[r.index(rec_b) + len(rec_b):]   # 去掉最近更新新条目
    assert HEADER_NEW.encode("utf-8") in r
    r = r.replace(HEADER_NEW.encode("utf-8"), HEADER_OLD.encode("utf-8"), 1)  # 还原本行
    # 指针行 → 还原成 2 条原条目
    pb = pointer.encode("utf-8")
    assert pb in r
    r = r.replace(pb, archived_block.rstrip("\n").encode("utf-8"), 1)
    if r != orig:
        errs.append("还原式复核失败：还原后与写前备份不等")

    if errs:
        print("SELF-CHECK FAIL => 源文件零改动")
        for e in errs:
            print("  -", e)
        return 2

    print("self-check: PASS")
    print("  bytes %d -> %d | lines %d -> %d | sections %d -> %d"
          % (len(orig), len(nb), text.count("\n"), new.count("\n"), n_old, n_new))
    print("  header@%d  recent-updates inserted" % hdr_pos)

    # ---------- 落盘：临时文件 → os.replace ----------
    tmpf = P + ".tmp_app226"
    with open(tmpf, "wb") as f:
        f.write(nb)
    os.replace(tmpf, P)
    print("written:", P, os.path.getsize(P), "B  sha256:", sha(open(P, "rb").read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
