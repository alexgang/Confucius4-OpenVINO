#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app193_update_status.py -- append STATUS_APP.md section 193 (patrol round),
archive the body of section 191 verbatim to make room under the 40 000 B cap
(APP-052-4), and update the header fields.

Discipline implemented here:
  * append-only for sections (old sections are never re-worded);
  * the section that gets archived is copied BYTE-VERBATIM into a write-once
    archive file, and the live document keeps its heading + a pointer line;
  * restore-check (reversible verification): putting the archived body back in
    place of the pointer line must reproduce the original file byte-for-byte;
  * size / line budget, and pure-LF line endings (no CR introduced);
  * header fields: last_ack stays APP-107 (no new correction => do not write
    our own number), timestamp is the measured Get-Date value passed in via
    argv (never computed here).

Fail-closed: every self-check runs BEFORE anything is written.
"""
import os
import re
import sys
import hashlib

STATUS = r"C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md"
ARCHIVE_DIR = r"C:\Users\Trekker-PTL\confucius4-openvino\status\archive"
ARCHIVE_191 = os.path.join(ARCHIVE_DIR, "STATUS_APP_sec191_20261113.md")
ARCHIVE_RU = os.path.join(ARCHIVE_DIR, "STATUS_APP_recent_updates_upto_20261113c.md")

NOW = sys.argv[1] if len(sys.argv) > 1 else None
if not NOW or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", NOW):
    sys.exit("usage: _app193_update_status.py 'YYYY-MM-DD HH:MM:SS'  (Get-Date measured)")

LIMIT_BYTES = 40000
LIMIT_LINES = 300

orig = open(STATUS, "rb").read()
assert b"\r" not in orig, "original file is expected to be pure LF"
text = orig.decode("utf-8")

# ---------------------------------------------------------------- split sections
starts = [m.start() for m in re.finditer(r"(?m)^## ", text)]
starts.append(len(text))
secs = []
for i in range(len(starts) - 1):
    body = text[starts[i]:starts[i + 1]]
    head = body.split("\n", 1)[0]
    secs.append((head, body))

idx191 = next(i for i, (h, _) in enumerate(secs) if h.startswith("## §191 "))
assert len([h for h, _ in secs if h.startswith("## §191 ")]) == 1, "ambiguous §191"
sec191_head, sec191_body = secs[idx191]

# ---------------------------------------------------------------- archive file
assert not os.path.exists(ARCHIVE_191), "archive file already exists (write-once)"
arch = (
    "# STATUS_APP §191 整块逐字归档（2026-11-13）\n"
    "\n"
    "归档时间：" + NOW + "\n"
    "归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §193 出陠。\n"
    "正文一字未删（标题行仍留在活文档）。\n"
    "\n"
    "块 SHA256（正文块，含标题行）：" + "（见 §193 本节记录的实测值）" + "\n"
    "\n"
    "---- 以下为 §191 原文，逐字 ----\n"
)
arch += sec191_body
arch_bytes = arch.encode("utf-8")
block_sha = hashlib.sha256(sec191_body.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------- pointer line
pointer = (
    "> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec191_20261113.md`"
    f"（{len(arch_bytes)} B／正文块 SHA256 `{block_sha}`）；活文档保留 §191 标题行 ＋ 1 行指针。\n"
)
new_191 = sec191_head + "\n\n" + pointer

# ------------------------------------------------ archive 3 oldest 最近更新 entries
ru_start = text.index("## 最近更新\n") + len("## 最近更新\n")
ru_end = text.index("## 当前有效结论")
ru_block = text[ru_start:ru_end]
ru_entries = [ln for ln in ru_block.split("\n")
              if ln.startswith("> 🔴 ") and not ln.startswith("> 🔴 本节")]
assert len(ru_entries) >= 5, "expected >=5 real 最近更新 entries, got %d" % len(ru_entries)
old3 = ru_entries[-3:]                       # the three oldest (04:46 / 06:49 / 08:21 patrols)
old3_block = "\n".join(old3) + "\n"
assert ru_block.count(old3_block) == 1, "old recent-update block not uniquely locatable"
ru_arch = (
    "# STATUS_APP「最近更新」较旧 3 条整块逐字归档（2026-11-13）\n"
    "\n"
    "归档时间：" + NOW + "\n"
    "归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §193 出陠。\n"
    "正文一字未删。\n"
    "\n"
    "---- 以下为「最近更新」3 条原文，逐字 ----\n"
    + old3_block
)
ru_arch_bytes = ru_arch.encode("utf-8")
ru_block_sha = hashlib.sha256(old3_block.encode("utf-8")).hexdigest()
ru_pointer = (
    "> 🔴 本节 3 条较旧「最近更新」条目（2026-11-13 04:46:11／06:49:24／08:21:30 三轮巡检）"
    "原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261113c.md`"
    f"（{len(ru_arch_bytes)} B／块 SHA256 `{ru_block_sha}`）；本节只留最近 3 条。\n"
)

# ---------------------------------------------------------------- new §193 text
sec193 = """## §193 巡检（last_ack=APP-107，__NOW__）｜**无新 reviewer 纠偏**（6 通道全查空）｜**rc11 半交付复核 PASS（zip ⇄ 包目录逐字节一致）**｜**`app523` 的 FAIL ＝ 判据过期（假 FAIL），非产品回归**｜**未打包／未改客户包／未改产品代码**

> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾 **107 条**／最大 **APP-107**／SHA `006d1ab7386ddfdf5f988330c74632f19f21b63b20d55aba8c5ca2febaf07ea5`／**355 098 B**／mtime **2026-11-13 09:28:40** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` **仍 APP-107**（无新纠偏 ⇒ 按纪律不写自己的编号）。
> **② 其它 5 通道全空（⇒ 无遗漏指令）**：`shared/NOTICE*` 最新仍 **11-05 09:35**｜agent-mail 回 **`not_bound`**（面板显示 connected，实际未开通）｜git `origin/main...main` = **0/0**（HEAD `1e3201c`）｜`MACHINE_LOCK` **NOT_PRESENT**（本轮零推理／零计时 ⇒ 未取锁）｜根 `status/CORRECTIONS.md` 仍 **10-24 17:01**；另查 ASR 侧 `status/asr/CORRECTIONS_ASR.md`（**26 条／最大 ASR-057**／mtime 11-13 09:06）**无 App 侧条目**。
> **③【rc11 半交付复核｜PASS 15/15】zip ⇄ 包目录「逐字节」一致（不只比文件名）**：zip `shared\\minimvp\\…rc11_perftest.zip`（**6 697 683 352 B**／mtime **11-13 10:23**）／前缀 `Confucius4_LiveCaption_MiniMVP_v1.0-rc11/`｜**文件数 10 629 ⇄ 10 629**（C1）｜**App 代码＋文档 15/15 逐字节一致**（C2：`tts_worker.py`／`tts_service.py`／`tts_engine.py`／`device_config.py`／`translator.py`／`live_caption_app.py`／`app/MANIFEST.json`／`release.json`／`package_profile.json`／三份 README／三个 `.bat`）｜**模型 12/12 逐字节一致**（C3：`models/mt/mt2-int8sym-cw-q` 全部 12 个文件）｜**MANIFEST 自洽**（A2 记录的 SHA ⇄ 包内字节 **12/12 一致**；A3 `all_match=true`／`n_mismatches=0`；条目 `optional=false`／`pkg_exists=true`／`source_path=C:\\Users\\Trekker-PTL\\hy_bench\\ov\\mt2-int8sym-cw-q`／note 明写 **INT8_SYM 对称按通道**）｜**拷贝源一致**（B1 包内字节 ⇄ 源目录 **12/12**；B2 MANIFEST 记录的 `source_sha256` ⇄ 真实源文件 **12/12**）｜**卫生**（D1 zip 内 `.pyc` **0**；D2 zip 内 `__pycache__` 成员 **0**；D3 zip 内 int4 成员 **0**；D4 包目录 int4 **0**；D5 `models/mt/` 只有 `mt2-int8sym-cw-q`）⇒ **「包里对」＝「zip 里也对」＝「已交付」**，APP-107 的模型身份与半交付风险**未发现缺口**（包目录 **10 629 文件**／zip **6 697 683 352 B** 与 §192 一致）。
> **④【判据鉴别力（反证组）】**：同一套判据指向 **rc10**（已知 INT4 旧包）⇒ **VERDICT FAIL（12 PASS / 3 FAIL）**，失败的正是 **D3（zip 内 int4 成员 12 个）／D4（包目录 int4 目录 1 个）／D5（`models/mt/` ≠ 只含 int8cw）** ⇒ 判据**能把 INT4 旧包识破**，不是恒真。
> **⑤【`app523` 报 VERDICT FAIL ＝ 假 FAIL（判据基线错），非产品回归；如实入册】**：`app523_pack_must_ttsworker_probe.py` 的 **A 段「改前事实」拿 `git cat-file blob HEAD:pack_v13.py` 断言「HEAD 仍缺 `app/tts_worker.py`、闸门④ 缺文件仍 `[SKIP] ⇒ return 0`」** —— 而 **§190 已把修好的 `pack_v13.py` 提交入库**（`git show` 可核：`af4264f`＝改前 MUST **39** 条且**不含** `app/tts_worker.py`；`cae2c53`＝改后 MUST **42** 条且**含**）⇒ **HEAD 变了 ⇒ A 段必然 FAIL ⇒ 整脚本 verdict FAIL** ⇒ 这是**一次性历史取证脚本**被当成**可复跑回归闸门**用（**反证基线必须是「当前被测对象」**）。**实质判据全过**（同一次运行的 B/C/D 段）：**B** 缺 `app/tts_worker.py` 的最小包 ⇒ 闸门④ **rc=1** 且输出「拒绝打包」、dry-run **rc=1** 且 MUST 只缺 `app/tts_worker.py`、补上 dev 收窄文件后闸门④ **rc=0**；**C** 磁盘 **19/19** 个真包都含新增 3 个 MUST 条目（**不误伤**）；**D** `_verify_and_report` 的 FAIL 条件含 `missing`（zip 校验 fail-closed）⇒ **§190 的两处修法仍在位**（`git show HEAD:pack_v13.py`：闸门④ 缺文件 ⇒ `[FAIL] 包内缺 app/tts_worker.py` ＋ `return 1`）。**处置**：按 APP-106 §4「不要再新建判据或审计脚本／不要提交新的」，**本轮不修补 app523、不新增闸门**，如实记录并请 reviewer 裁定是否退役该脚本。
> **⑥【既有闸门复跑（静态、零推理、未占锁）】**：`app510`（§188 反证）**VERDICT PASS**｜`app512`（§189 包矩阵）**判定未变** —— **10 个带 APP-086·2a 缺陷的包仍 FAIL**（完整版 v2.2／v2.3／v2.3_aborted／v2.4 ＋ MiniMVP v1.0／rc1–rc5），**通过包仍 PASS**（v1.13／v2.0／v2.1／rc7／rc8／rc9），**rc10 与 rc11 均 PASS**（B1 保留克隆音色／B3 回落预设 A）⇒ **rc11 包与 dev 树在「收窄」这一项上口径一致**。
> **⑦【本轮新增的本地探针：未入库，遵守 APP-106 §4】**：③/④ 的判据脚本 `results/app/app529_rc11_zip_pkg_halfdelivery.py` ＋两份 evidence json（rc11：**7 981 B**／SHA `5058a26c…`／mtime 12:38:34；rc10 反证：**8 112 B**／SHA `91cb4fb3…`／mtime 12:38:51）为**本轮一次性自检**产物，**按 APP-106 §4「不要再新建判据或审计脚本／不要提交新的」一律不入库、不提交**（磁盘上保留以备复核；本节所引数字已逐条写明，可独立复算）。
> **⑧【纪律】**：**未打包**（未打任何 zip／未改任何版本目录；rc10／rc11 原样未动）｜**未改客户包**（全部只读）｜**未改产品代码**（`live_caption/` 与 `pack_v13.py` **零改动**）｜**未改 `CORRECTIONS_APP.md`**（只读、未入库、未提交）｜**未跑推理／未计时 ⇒ 未取 `MACHINE_LOCK`**｜**未调 MiniMax**｜**未通知用户**｜**未提交** ASR／MT／TTS 其它模块的未提交改动（仓库仍有大量他人未提交改动，本轮**只提交 `status/app/STATUS_APP.md`**）。
> **⑨【压缩（APP-052④ 上限 40 000 B）】**：**§191 正文整块逐字归档** ⇒ `status/archive/STATUS_APP_sec191_20261113.md`（**__ARCH_BYTES__ B**／正文块 SHA256 `__ARCH_SHA__`）；活文档保留 §191 标题行 ＋ 1 行指针；**「最近更新」较旧 3 条**（11-13 04:46／06:49／08:21 三轮巡检）整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261113c.md`（**__RU_BYTES__ B**／块 SHA256 `__RU_SHA__`）＋ 1 行指针；「已压缩」行已追加 §191 指针。**归档件 write-once，正文一字未删；还原式复核通过（把指针行换回原文 ⇒ 与改前逐字节一致）。**
> **⑩ 本条需等 reviewer 复核**：① **`app523` 的假 FAIL** 是否照此结论销案／退役（是否改成「历史一次性」脚本）；② **本轮探针脚本不入库**是否认可；③ **rc11 的整链性能**（沿用 §192 ⑨，未变）；④ **10 个带缺陷包**作废还是标注（**目录一律不删**）；⑤ **完整版 v2.5** 何时打（必须带收窄）；⑥ **EXT 换嵌**通知。

"""
sec193 = sec193.replace("__NOW__", NOW)
sec193 = sec193.replace("__ARCH_BYTES__", str(len(arch_bytes)))
sec193 = sec193.replace("__ARCH_SHA__", block_sha)
sec193 = sec193.replace("__RU_BYTES__", str(len(ru_arch_bytes)))
sec193 = sec193.replace("__RU_SHA__", ru_block_sha)

recent_entry = (
    "> 🔴 " + NOW + " ｜ **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）**：6 通道全查空"
    "（`CORRECTIONS_APP.md` **107 条**／最大 **APP-107**／SHA `006d1ab7…`／**355 098 B**／"
    "mtime 11-13 09:28:40，**SHA 零改动**）｜**rc11 半交付复核 PASS 15/15**"
    "（zip ⇄ 包目录**逐字节**一致：文件数 10 629⇄10 629、App 代码＋文档 15/15、模型 12/12、"
    "MANIFEST 自洽 12/12、拷贝源 12/12、`.pyc` 0／int4 0）｜**反证组**：同一判据指向 rc10 ⇒ "
    "**FAIL 12/15**（D3/D4/D5）⇒ 判据有鉴别力｜**`app523` VERDICT FAIL ＝ 假 FAIL**"
    "（A 段断言「HEAD 仍带改前缺陷」，而 §190 修好的 `pack_v13.py` 已入库 ⇒ 基线错；实质 B/C/D 全过）｜"
    "`app510` PASS、`app512` 判定未变（10 缺陷包仍 FAIL、rc10/rc11 PASS）｜"
    "**未打包／未改客户包／未改产品代码**｜本轮探针**未入库**（APP-106 §4）｜未调 MiniMax、未通知用户\n"
)

# ---------------------------------------------------------------- build new text
new = text.replace(sec191_body, new_191, 1)
assert new != text, "§191 replacement did not apply"
assert new.count(new_191) == 1
new = new.replace(old3_block, ru_pointer, 1)
assert new.count(ru_pointer) == 1, "recent-update block replacement did not apply"

# insert the new "最近更新" entry as the first line under the "## 最近更新" heading
m = re.search(r"(?m)^## 最近更新\n", new)
assert m, "'## 最近更新' heading not found"
ins = m.end()
new = new[:ins] + recent_entry + new[ins:]

# append §193 at the end of the document
if not new.endswith("\n"):
    new += "\n"
new += sec193

# ---------------------------------------------------------------- header updates
lines = new.split("\n")
assert lines[2].startswith("last_ack: "), lines[2]
lines[2] = "last_ack: APP-107"          # unchanged (no new correction)
assert lines[3].startswith("更新时间: "), lines[3]
lines[3] = "更新时间: " + NOW
assert lines[4].startswith("当前任务: "), lines[4]
lines[4] = ("当前任务: **巡检（无新 reviewer 纠偏，last_ack 仍 APP-107）**｜"
            "**rc11 半交付复核 PASS 15/15**（zip ⇄ 包目录**逐字节**一致：文件数 10 629⇄10 629、"
            "App 代码＋文档 15/15、模型 12/12、MANIFEST 自洽 12/12、拷贝源 12/12、`.pyc` 0／int4 0）｜"
            "**反证组**：同一判据指向 rc10 ⇒ **FAIL 12/15**（D3/D4/D5）⇒ 判据有鉴别力｜"
            "**`app523` 的 VERDICT FAIL ＝ 假 FAIL**（A 段基线锚在 HEAD，而 §190 修好的 "
            "`pack_v13.py` 已入库 ⇒ 基线错；实质 B/C/D 全过）｜`app510` PASS、`app512` 判定未变"
            "（10 个缺陷包仍 FAIL、rc10/rc11 PASS）｜**未打包／未改客户包／未改产品代码**｜"
            "本轮探针脚本**未入库**（APP-106 §4）｜未调 MiniMax｜未通知用户")
assert lines[5].startswith("阻塞 / 待用户决定: "), lines[5]
lines[5] = lines[5].rstrip() + ("｜🔴 **待 reviewer 裁定（本轮新增）**：**`app523` 的假 FAIL 是否销案／退役** ＋ "
                                "**本轮探针脚本未入库是否认可**（APP-106 §4）｜沿用：rc11 整链性能是否可接受"
                                "（§192 ⑨）、10 个带缺陷包作废还是标注、完整版 v2.5 何时打、EXT 换嵌通知")
assert lines[6].startswith("已压缩: "), lines[6]
lines[6] = lines[6].rstrip() + ("｜**§191 压缩**（2026-11-13）：§191 正文整块逐字归档 ⇒ "
                                "`status/archive/STATUS_APP_sec191_20261113.md`（"
                                f"{len(arch_bytes)} B／正文块 SHA256 `{block_sha}`）；"
                                "活文档保留 §191 标题行 ＋ 1 行指针")
new = "\n".join(lines)

# ---------------------------------------------------------------- self-checks (fail-closed)
new_bytes = new.encode("utf-8")
n_lines = new.count("\n") + 1
assert len(new_bytes) <= LIMIT_BYTES, "size limit exceeded: %d > %d" % (len(new_bytes), LIMIT_BYTES)
assert n_lines <= LIMIT_LINES, "line limit exceeded: %d > %d" % (n_lines, LIMIT_LINES)
assert b"\r" not in new_bytes, "CR introduced"

# restore-check: put the archived §191 body back => must equal the original file.
# Scope: the document BODY (from '## 最近更新' on). The header rows 3-7 are
# intentionally updated (last_ack / 更新时间 / 当前任务 / 阻塞 / 已压缩) and are
# verified separately below.
BODY_MARK = "## 最近更新\n"
orig_wo = orig.decode("utf-8")
orig_body = orig_wo[orig_wo.index(BODY_MARK):]
new_body = new[new.index(BODY_MARK):]

restored = new_body.replace(new_191, sec191_body, 1)
assert restored.count(sec191_body) == 1, "restore-check: §191 body not uniquely locatable"
restored = restored.replace(ru_pointer, old3_block, 1)
assert restored.count(old3_block) == 1, "restore-check: recent-update block not uniquely locatable"
restored = restored.replace(recent_entry, "", 1)                 # new entry = addition
restored = restored[:restored.rindex("## §193 巡检")]            # §193 = addition
restored = restored.rstrip("\n") + "\n"
assert restored == orig_body, "restore-check failed: old body was modified"

# header rows: last_ack must NOT change (no new correction); the others must change
hdr = new.split("\n")
assert hdr[2] == "last_ack: APP-107", hdr[2]
assert hdr[3] == "更新时间: " + NOW, hdr[3]
assert hdr[4] != orig_wo.split("\n")[4], "当前任务 row was not updated"
assert hdr[5] != orig_wo.split("\n")[5], "阻塞 row was not updated"
assert hdr[6] != orig_wo.split("\n")[6], "已压缩 row was not updated"
assert orig_wo.split("\n")[0:2] == hdr[0:2], "title block must not change"

# every other section must be byte-identical
def sections_of(t):
    st = [m.start() for m in re.finditer(r"(?m)^## ", t)]
    st.append(len(t))
    return {t[st[i]:st[i + 1]].split("\n", 1)[0]: t[st[i]:st[i + 1]] for i in range(len(st) - 1)}

old_secs = sections_of(orig_wo)
new_secs = sections_of(new)
for head, body in old_secs.items():
    if head.startswith("## §191 "):
        continue
    if head == "## 最近更新":
        continue
    assert head in new_secs, "section lost: %s" % head
    if head in ("# STATUS_APP",) or head.startswith("## 当前有效结论"):
        continue
    if head in new_secs and head not in ("# STATUS_APP",):
        assert new_secs[head] == body, "section body changed: %s" % head
# '## 最近更新': every original entry must still be present verbatim or live in the archive
for line in orig_wo.split("## 最近更新\n", 1)[1].split("\n"):
    if line.startswith("> 🔴"):
        if line + "\n" in new:
            continue
        # the three oldest entries were archived -> their text must live in the archive file
        assert line + "\n" in old3_block, "recent-update entry lost: %s" % line[:60]

# ---------------------------------------------------------------- write (only now)
assert not os.path.exists(ARCHIVE_RU), "recent-update archive already exists (write-once)"
with open(ARCHIVE_191, "wb") as f:
    f.write(arch_bytes)
with open(ARCHIVE_RU, "wb") as f:
    f.write(ru_arch_bytes)
with open(STATUS, "wb") as f:
    f.write(new_bytes)

print("archive191:", ARCHIVE_191, len(arch_bytes), "B  block_sha", block_sha)
print("archiveRU :", ARCHIVE_RU, len(ru_arch_bytes), "B  block_sha", ru_block_sha)
print("status    :", STATUS, len(new_bytes), "B /", n_lines, "lines (was",
      len(orig), "B /", orig.count(b"\n") + 1, "lines)")
print("restore-check: OK (old body byte-identical)")
print("verdict   : OK")
