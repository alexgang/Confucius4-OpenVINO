# -*- coding: utf-8 -*-
"""App §199：巡检（无新 reviewer 纠偏）+ 把 §197/§198 正文整块逐字归档后追加 §199。

纪律（APP-052④ / §185 归档纪律）：
  * 活文档上限 ≤40000 B / ≤300 行；先归档旧正文再追加。
  * 归档件 write-once：正文逐字写入，不改一字。
  * 写前自检（纯 LF / 无 BOM / 体积 / 行数 / **还原式复核** / **旧正文一行不丢**）
    全部通过才落盘；任一 FAIL ⇒ 源文件零改动。
  * 标题行必须保留（§194 教训：归档替换必须显式保留标题行）。
"""
import hashlib
import io
import os
import shutil
import sys
from collections import Counter

ROOT = r"C:\Users\Trekker-PTL\confucius4-openvino"
STATUS = os.path.join(ROOT, "status", "app", "STATUS_APP.md")
ARCHIVE = os.path.join(ROOT, "status", "archive", "STATUS_APP_sec197_198_20261113.md")

TS = "2026-11-13 23:59:06"          # Get-Date 实测值
MAX_BYTES = 40000
MAX_LINES = 300

# ---------------------------------------------------------------- 读取
with open(STATUS, "rb") as f:
    old_bytes = f.read()
old = old_bytes.decode("utf-8")
lines = old.split("\n")

# 定位 §197 / §198 标题行（唯一命中断言）
i197 = [i for i, l in enumerate(lines) if l.startswith("## §197 ")]
i198 = [i for i, l in enumerate(lines) if l.startswith("## §198 ")]
assert len(i197) == 1, "§197 title count=%d" % len(i197)
assert len(i198) == 1, "§198 title count=%d" % len(i198)
i197, i198 = i197[0], i198[0]
assert i197 < i198, "order"

title197 = lines[i197]
title198 = lines[i198]
body197 = lines[i197 + 1:i198]        # §197 标题行之后、§198 标题行之前
body198 = lines[i198 + 1:]           # §198 标题行之后到 EOF

# 字符偏移（比行号更可靠）
off_t197 = old.index(title197)
off_b197 = off_t197 + len(title197)
off_t198 = old.index(title198)
off_b198 = off_t198 + len(title198)
body197_block = old[off_b197:off_t198]     # §197 正文块（含其后的换行）
body198_block = old[off_b198:]             # §198 正文块（到 EOF）
assert body197_block and body198_block, "empty body"

# 归档块 = 两节标题行 + 两节正文，逐字
chunk = "\n".join([title197] + body197 + [title198] + body198)
chunk_bytes = chunk.encode("utf-8")
chunk_sha = hashlib.sha256(chunk_bytes).hexdigest()
chunk_len = len(chunk_bytes)

# ---------------------------------------------------------------- 新增文本
pointer = (
    "> **§197+§198 压缩**（2026-11-13）：**两节正文整块逐字归档** ⇒ "
    "`status/archive/STATUS_APP_sec197_198_20261113.md`（%d B／块 SHA256 `%s`）；"
    "本行同时覆盖 §197 与 §198 两节正文；两节**标题行仍逐字保留在活文档**。"
    % (chunk_len, chunk_sha)
)

index_entry = (
    "｜**§197+§198 压缩**（2026-11-13）：两节正文整块逐字归档 ⇒ "
    "`status/archive/STATUS_APP_sec197_198_20261113.md`（%d B／块 SHA256 `%s`）；"
    "活文档保留 §197／§198 标题行 ＋ 1 行指针" % (chunk_len, chunk_sha)
)

recent_entry = (
    "> 🔴 2026-11-13 23:59:06 ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）**："
    "6 通道全查空（`CORRECTIONS_APP.md` 107 条/APP-107 未变、NOTICE 最新 11-05、"
    "agent-mail 仍 `not_bound` 查不了、conversation_search 0 命中、git 0/0、`MACHINE_LOCK` 无）｜"
    "🔴 **本轮唯一实质发现（交付通道层）：目标机的无人值守进入通道已失效** —— "
    "口令当时只放在临时环境变量 `WB_SSH_PASS`（**未落盘未入库**）⇒ 本轮及后续会话都登不上；"
    "公钥路实测也未通（**已排除探法错误**：显式 `-i github_backup_ed25519 -o IdentitiesOnly=yes` 仍 Permission denied）"
    "⇒ §197⑤/§198② 的**两端 SHA256 对账任何无人值守轮次都无法闭环**，需用户给一次密码或装公钥｜"
    "未打包/未改客户包/未改产品代码/未跑推理/未调 MiniMax"
)

sec199 = """## §199 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-107**）｜🔴 **目标机进入通道已结构性失效** ⇒ §197 ⑤／§198 ② 的 SHA256 对账**任何无人值守轮次都无法闭环**

> **① 巡检（6 通道全查空，附开工实测值）**：`status/app/CORRECTIONS_APP.md` 开工＝**107 条／最大 APP-107**（SHA `006d1ab7386ddfdf5f988330c74632f19f21b63b20d55aba8c5ca2febaf07ea5`／**355 098 B**／mtime **11-13 09:28:40**）⇒ **无编号 > last_ack 的新条目** ⇒ `last_ack` **保持 APP-107**（无新纠偏 ⇒ 不写自己的编号）。其余通道：`shared/NOTICE*` 最新仍 **11-05 09:35**｜agent-mail 面板 connected 但工具仍返 **`not_bound`**（**该通道本轮查不了**，如实记录，不声称查过）｜`conversation_search`（11-13 全天）**0 命中**｜git `origin/main...main`＝**0/0**（HEAD `7703c78`）｜`claude-clone --not main`＝**0**（该分支只落后于 main）｜`MACHINE_LOCK` **NOT_PRESENT**｜根 `status/CORRECTIONS.md` 最大 **C-135**（10-24 17:01）｜ASR 侧最大 **ASR-057**（11-13 09:06，无 App 条目）｜`clone_dev` 等旧克隆仍是 **10 929 B／最大 APP-004** 的陈旧快照。
> **② 🔴 本轮唯一实质发现（交付通道层，非产品缺陷）**：§197 ② 的口令**当时只放进临时环境变量 `WB_SSH_PASS`**（脚本从环境读取、**未落盘、未入库、未硬编码**，做法本身正确）⇒ **但该口令本轮已不可得**（四处实测：`printenv` 空；HKCU/HKLM 持久环境变量**无** `WB_SSH_PASS`；PSReadLine 历史（**4 318 B／mtime 10-30 13:18**）**无**该串；`results/app/_app542_ssh_try.py` 与 `_app545_transfer_to_target.py` **只读环境变量**）⇒ **后续任何会话都登不上目标机**（不是「暂时连不上」，是**没有可用凭据**）。
> **③ 公钥这条路也没通（已排除「探法错误」）**：目标机**可达**（ping **1 ms**／0% 丢包；**22/445 OPEN**，3389 超时）；`ssh -o BatchMode=yes -o PreferredAuthentications=publickey test@192.168.2.194` → **Permission denied**；🔴 **首测有探法陷阱**：本机私钥文件名是 `github_backup_ed25519`，**不属 ssh 默认私钥名**（默认 `id_rsa`/`id_ed25519` 等）且 `~/.ssh/config` 只给 `github.com`/`win-pc` 配了 IdentityFile ⇒ **首测根本没把这把钥匙递上去** ⇒ 改用**显式** `-i ~/.ssh/github_backup_ed25519 -o IdentitiesOnly=yes` 复测，**仍** Permission denied ⇒ **公钥确实没装进目标机 `test` 的 authorized_keys**（**真缺，不是探法问题**）。
> **④ ⇒ 直接后果（须如实入册，不掩盖）**：本轮**未能复核**目标机侧的 AV 独占锁与磁盘（登不上 ⇒ 既不报「已闭环」也不报「锁仍在」）；§198 ① 的**目标机磁盘（82.3 MB 可用）**、§197 ⑦ 的**目标机实机 `--check`（sm_89 vs sm_120）**、§197 ⑨① 的**是否授权删 zip** —— 这三项**全部**只能由**有认证的人**在做。SMB 匿名读也确认不通（`\\192.168.2.194\\Users` → **WinError 3**，共享未匿名暴露；`C$` 仍是 error 5，`test` 非管理员）。
> **⑤ 最小解锁动作（任选其一，均不需我改任何客户包）**：① **重给一次目标机 `test` 密码**（我用完即弃、**不落盘**）；② **在目标机把本机公钥装上**（推荐，一劳永逸）：把 `C:\\Users\\Trekker-PTL\\.ssh\\github_backup_ed25519.pub` 的**一行内容**追加到目标机 `C:\\Users\\63446\\.ssh\\authorized_keys` ⇒ 之后我即可**免密**复核 SHA256／磁盘／实机 `--check`；③ **用户在目标机自己跑一次**并把输出贴回：`certutil -hashfile "C:\\Users\\63446\\Desktop\\Confucius4_LiveCaption_SpecialMVP_v1.0-sp1.zip" SHA256` 与 `fsutil volume diskfree c:`。
> **⑥ 零漂移复核（本轮只读）**：本机 Special MVP 源 zip **14 244 490 059 B／mtime 11-13 21:24:59**（＝§197 ④ 值，**未漂移**）｜MiniMVP rc11 zip **6 697 683 352 B／mtime 11-13 10:23:53**｜**各客户包目录未改**（MiniMVP/完整版/SpecialMVP 一律只读）｜`live_caption/` **产品代码零改动**｜上一轮 helper **全灭且 8899 端口已闭**（本轮 `Get-NetTCPConnection 8899` 无监听）⇒ **本机无遗留后台作业、不占租约**。
> **⑦ 沿用未变（等用户/reviewer）**：① **10 个带 APP-086·2a 缺陷包**作废还是标注（**目录一律保留不删**）；② **完整版 v2.5** 何时打（**必须带收窄**；**用户不通知不打包**）；③ **EXT 换嵌**通知；④ `app523` 假 FAIL 是否退役；⑤ rc11 **B 机**运行；⑥ **OPEN-1** 退出码 3221226505 定位；⑦ **CUDA TTS 音质/音色**待 reviewer 回转写、**TTS 首启 58.7 s** 是否可接受。
> **⑧ 纪律**：本节**只追加**，不改 §197／§198 正文（已整块逐字归档，正文一字未删）｜**未打包**（v2.5 仍未打；rc9/rc10/rc11 未动）｜**未改任何客户包**｜**未改产品代码**｜**未改 `CORRECTIONS_APP.md`**（收尾仍 **SHA `006d1ab7…`／355 098 B／mtime 11-13 09:28:40／107 条／APP-107 ＝ 开工值 ⇒ 本轮可写「SHA 零改动」）｜**未跑推理**（本机与目标机都没跑）⇒ 未取 `MACHINE_LOCK`｜**未调 MiniMax**｜**未提交其它模块**的未提交改动｜**明文口令未写入任何入库文件**｜`results/app/app512_pkg_follow_speaker_matrix.json`（+18/-0）与 `results/app/app523_pack_must_ttsworker_evidence.json`（+16/-7）**仍保持未提交**（等 reviewer 对 app523 裁定，**不预判**）。"""

# ---------------------------------------------------------------- 组装新活文档
new = (old[:off_b197]                      # …至 §197 标题行（不含换行）
       + "\n" + pointer + "\n\n"           # 指针行
       + old[off_t198:off_b198]            # §198 标题行
       + "\n\n"                            # 空行
       + sec199 + "\n")

# 头部：更新时间（Get-Date 实测值）
old_ts_line = [l for l in lines if l.startswith("更新时间: ")]
assert len(old_ts_line) == 1, "ts line count"
new_ts_line = "更新时间: " + TS
assert old_ts_line[0] in new, "ts line lost"
new = new.replace(old_ts_line[0], new_ts_line, 1)

# 头部「已压缩」索引追加
idx_line = [l for l in new.split("\n") if l.startswith("已压缩: ")]
assert len(idx_line) == 1, "index line count"
new = new.replace(idx_line[0], idx_line[0] + index_entry, 1)

# 「最近更新」新增一条（插在「## 最近更新」标题行之后）
anchor = "## 最近更新"
assert new.count(anchor) == 1, "recent anchor"
new = new.replace(anchor + "\n", anchor + "\n" + recent_entry + "\n", 1)

# ---------------------------------------------------------------- 自检（先跑完再落盘）
errs = []
nb = new.encode("utf-8")
if b"\r" in nb:
    errs.append("CR present (must be pure LF)")
if nb[:3] == b"\xef\xbb\xbf":
    errs.append("BOM present")
if len(nb) > MAX_BYTES:
    errs.append("size %d > %d" % (len(nb), MAX_BYTES))
nl = new.count("\n") + 1
if nl > MAX_LINES:
    errs.append("lines %d > %d" % (nl, MAX_LINES))

# 还原式复核：把本轮对 §197/§198 区域的改动反向还原，应逐字节等于原文
spliced = ("\n" + pointer + "\n\n" + old[off_t198:off_b198] + "\n\n" + sec199 + "\n")
restore = new.replace(spliced, body197_block + old[off_t198:off_b198] + body198_block, 1)
restore = restore.replace(recent_entry + "\n", "", 1)
restore = restore.replace(index_entry, "", 1)
restore = restore.replace(new_ts_line, old_ts_line[0], 1)
if restore != old:
    errs.append("restore-check mismatch (%d vs %d)" % (len(restore), len(old)))

# 旧正文一行不丢：除被归档的两块正文外，旧文件的每一行都必须仍在活文档中
old_counts = Counter(lines)
new_counts = Counter(new.split("\n"))
archived = Counter(body197 + body198)
# 头部两行是本轮**受权修改**的唯一两行（时间戳实测值 / 已压缩索引追加一条）
archived[old_ts_line[0]] = 1
archived[idx_line[0]] = 1
for ln, c in old_counts.items():
    allowed = archived.get(ln, 0)
    if new_counts.get(ln, 0) < c - allowed:
        errs.append("lost old line: %.80s" % ln)
        break

# 标题行必须仍逐字在活文档
if new.count(title197) != 1:
    errs.append("title197 not exactly once")
if new.count(title198) != 1:
    errs.append("title198 not exactly once")
if new.count("## §199 ") != 1:
    errs.append("sec199 missing")

print("OLD bytes=%d lines=%d" % (len(old_bytes), len(lines)))
print("NEW bytes=%d lines=%d  (cap %d/%d)" % (len(nb), nl, MAX_BYTES, MAX_LINES))
print("archived chunk bytes=%d sha256=%s" % (chunk_len, chunk_sha))

if errs:
    for e in errs:
        print("SELF-CHECK FAIL:", e)
    print("=> 源文件零改动")
    sys.exit(1)

# ---------------------------------------------------------------- 落盘
archive_text = (
    "# STATUS_APP §197+§198 整块逐字归档（2026-11-13）\n"
    "\n"
    "归档时间：%s\n"
    "归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §199 出重。\n"
    "正文一字未删（§197／§198 两节标题行＋正文逐字保留；活文档仍保留两个标题行 ＋ 1 行指针）。\n"
    "\n"
    "§197+§198 正文块 SHA256（含两节标题行）：%s（%d B）\n"
    "\n"
    "---- 以下为 §197+§198 原文，逐字 ----\n"
    "%s\n"
) % (TS, chunk_sha, chunk_len, chunk)

with io.open(ARCHIVE, "w", encoding="utf-8", newline="\n") as f:
    f.write(archive_text)

bak = STATUS + ".bak_sec199"
shutil.copy2(STATUS, bak)
with io.open(STATUS, "w", encoding="utf-8", newline="\n") as f:
    f.write(new)

# 落盘后复核
with open(STATUS, "rb") as f:
    now = f.read()
assert now == nb, "on-disk mismatch"
with open(ARCHIVE, "rb") as f:
    ab = f.read()
assert chunk.encode("utf-8") in ab, "archive does not contain verbatim chunk"
print("WROTE STATUS bytes=%d  ARCHIVE bytes=%d sha256=%s"
      % (len(now), len(ab), hashlib.sha256(ab).hexdigest()))
print("BACKUP:", bak)
