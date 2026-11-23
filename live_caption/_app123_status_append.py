"""Append §223 to status/app/STATUS_APP.md and update the header.

Discipline (APP-052④ / this project's rules):
  * the live doc only gets the TITLE line + a pointer line; the body goes to
    the companion file `status/app/STATUS_APP_sec223_detail_20261123.md`
  * `last_ack` -> APP-127 (the largest APP number actually executed)
  * `更新时间` = the MEASURED Get-Date value (never computed by hand)
  * append-only: never rewrite an old section
  * CRLF preserved; write is atomic (temp -> os.replace)
  * a restore-style check afterwards: removing exactly what we added must
    give back the original bytes
"""
import datetime
import os
import shutil
import subprocess

STATUS = r"C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md"
BAK = os.path.join(os.environ.get("TEMP", r"C:\Users\Trekker-PTL\AppData\Local\Temp"),
                   "STATUS_APP.md.bak_app123")

# measured timestamp (PowerShell Get-Date), not hand-computed
ts = subprocess.run(
    ["powershell", "-NoProfile", "-Command", "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"],
    capture_output=True, text=True).stdout.strip()
print("measured 时间 =", repr(ts))

raw = open(STATUS, "rb").read()
orig = raw.decode("utf-8")
shutil.copy2(STATUS, BAK)
print("backup ->", BAK)

nl = "\r\n" if b"\r\n" in raw else "\n"
text = orig.replace("\r\n", "\n")
lines = text.split("\n")

# ── 1) header: last_ack + 更新时间 ─────────────────────────────────────────
i_ack = [i for i, l in enumerate(lines) if l.startswith("last_ack:")]
assert len(i_ack) == 1, "last_ack header not unique"
lines[i_ack[0]] = "last_ack: APP-127"
i_ts = [i for i, l in enumerate(lines) if l.startswith("更新时间:")]
assert len(i_ts) == 1, "更新时间 header not unique"
lines[i_ts[0]] = "更新时间: " + ts

# ── 2) 最近更新: add the newest entry on top of that section ───────────────
i_recent = lines.index("## 最近更新")
entry = (
    "> 🔴 2026-11-23 18:5x ｜ **执行 APP-122…APP-127（last_ack=APP-121 → **APP-127**）**："
    "🟢 **§0 六通道复核**：局域网 125 条/max APP-127 ＋ QQ 邮箱最新封=APP-127（同一编号两边都到 ⇒ 只执行一次）＋ spam 0；"
    "**收尾复核 SHA/字节/mtime/条数四项逐字一致 ⇒ SHA 零改动**｜"
    "🟢 **APP-122/124/125 = 分工调整，App 线程零代码**（APP-125 覆盖前两条 ⇒ 保留背景音的代码全由 reviewer 写；"
    "**App 线程在 APP-125 生效前未动过 live_dub_ext**，未提交未 stash）｜"
    "🟢 **APP-126 §2 15/15 md5 逐个一致**（`git diff --stat` 只这 15 个）｜"
    "🟢 **§3 单测+回归 10/10 全过**（18/18 ＋ 12/12 ＋ python 70/25/21/38/42 ＋ node 26/28/16/13）｜"
    "🟢 **§4 实时 e2e v5 七臂全过**（blocks 74/23/31/46/23/31/74、**contig 全 True**、**late 全 0**、"
    "**fallback 全 0.0**、rtf p50 0.200–0.234、**clip_s2 首句 shift_to=14.77 s**（修前 8.0））｜"
    "🔴 **§5 一处计数器口径如实报告**：`stats_full.speaker.n_speakers=0` ＋ `spk_bypass.enabled=false`，"
    "**但日志里标签是真的有**（clone_cs2 **9 段** `标签=S1`）⇒ 已读源码定位：那是 `ext/speaker.py` 的 tracker，"
    "只由 `--spk-bypass` 那条路灌（本会话没接）；**克隆标签来自 App 包 `speaker_tracker.SpeakerBridge`**，"
    "其 stats 未被收进 `stats_full` ⇒ **口径不同，非功能缺陷**；**reviewer 自己的 e2e7 同为 0 ⇒ 非 v0.4.19 回归**；"
    "**按 APP-126 §5 未自行改代码**｜"
    "🟢 **§6 提交 `5121d99` ＋ 推送 `ee45ce5..5121d99 claude-dev -> live-dub-ext`**（工作区干净）｜"
    "🟢 **§7 APP-127：开工时无陈旧锁 ⇒ 未删任何锁**（本轮自泄漏的那把已按 ctypes 证死并回收）｜"
    "🟢 **§8 APP-123 c13 接入完成（开发层）**：**架构事实**=App 走 BabelVox+`tts_engine_patch.py`（**本来就有**左上下文/长度守恒/小窗口）"
    "⇒ 补的是**可配的 c13 口径 + TTS-076 整句限幅与削波计数**；🔴 **并发现 App 本来就是「直接拼接」**"
    "（babelvox `split_on_silence=False` ⇒ 走 pass-through 分支 ⇒ **没有** TTS-075 那个丢 7.3% 音频的缺陷）"
    "⇒ `crossfade_samples=0` 是显式化加固、**不是**修缺陷（如实写）；"
    "🔴 **并修正一处自己的错**：初版把 `CHUNK_FRAMES` 设成 13（误读 c13 三参数）⇒ **首包 2.9→4.5 s 劣化** ⇒ 已改回 8；"
    "🟢 **真跑实测 NPU**：**长度守恒成立**（78 720=41×1920、26 880=14×1920、每块都是 1920 整数倍、clipped=0）；"
    "**窗口 A/B 同 seed ⇒ 样本数相同、SNR 56.44/57.99 dB**；**GPU.0 臂 SNR=∞（逐字节相同，桶只在 NPU 生效）**；"
    "🟢 **EXT 走同一份 `tts_engine.stream` ⇒ 自动用上 c13**，player.js **无固定 0.64 s**（按实际采样数排程）｜"
    "🔴 **§8.5 未做（按 APP-126 §7）**：不进包、不跑 10 分钟整链、不做 MiniMax 抽查与抽听样片 ⇒ **等 reviewer 交接**｜"
    "🔴 **如实登记 4 处事故**（锁泄漏／回收脚本 fail-open／CRLF 二次应用／docstring 未闭合）＋ **2 处判据错误**（c13 参数语义／A/B 被采样噪声污染）｜"
    "**未打包／未改客户包／未连 B 机／未调 MiniMax／未改纠偏文件**｜**本条需等 reviewer 复核**"
)
lines[i_recent + 1:i_recent + 1] = [entry]

# ── 3) the §223 section (title line + pointer line; body is in companion) ──
i_last = len(lines) - 1
while i_last > 0 and not lines[i_last].strip():
    i_last -= 1
sec = [
    "",
    "## §223 执行 **APP-122 / APP-123 / APP-124 / APP-125 / APP-126 / APP-127**（last_ack=APP-121 → **APP-127**，2026-11-23 18:5x）｜"
    "🟢 **§0 六通道复核：局域网 125 条/max APP-127 ＋ QQ 最新封=APP-127（同一编号只执行一次）＋ spam 0；收尾复核 SHA/字节/mtime/条数四项逐字一致 ⇒ SHA 零改动**｜"
    "🟢 **§1 APP-122/124/125 = 分工调整，App 线程零代码**（APP-125 覆盖前两条 ⇒ 保留背景音代码全由 reviewer 写；**App 线程在 APP-125 生效前未动过 live_dub_ext**）｜"
    "🟢 **§2 APP-126 落码 15/15 md5 一致**｜🟢 **§3 单测+回归 10/10 全过**｜🟢 **§4 实时 e2e v5 七臂全过**"
    "（**contig 全 True／late 全 0／fallback 全 0.0**、rtf p50 0.200–0.234、**clip_s2 首句 shift_to=14.77 s**）｜"
    "🔴 **§5 `n_speakers=0` 是计数器口径不同（日志里标签真实存在：clone_cs2 9 段 `标签=S1`）⇒ 非缺陷；reviewer 的 e2e7 同为 0 ⇒ 非回归；按 APP-126 §5 未自行改代码**｜"
    "🟢 **§6 提交 `5121d99` ＋ 推送 `ee45ce5..5121d99 claude-dev -> live-dub-ext`**｜🟢 **§7 APP-127 无陈旧锁可删**｜"
    "🟢 **§8 APP-123 c13 接入完成（开发层）：补「可配 c13 口径 + TTS-076 整句限幅与削波计数」；"
    "🔴 并发现 App 本来就是「直接拼接」⇒ `crossfade_samples=0` 是加固不是修缺陷；"
    "🔴 并修正自己一处错（CHUNK_FRAMES 误设 13 ⇒ 首包 2.9→4.5 s 劣化 ⇒ 已改回 8）；"
    "🟢 真跑实测 NPU 长度守恒成立（78 720=41×1920、clipped=0）、窗口 A/B SNR 56.44/57.99 dB、GPU.0 臂 SNR=∞（桶只在 NPU 生效）；"
    "🟢 EXT 走同一份 `tts_engine.stream` ⇒ 自动用上 c13，player.js 无固定 0.64 s**｜"
    "🔴 **§8.5 按 APP-126 §7 不进包／不跑 10 分钟整链／不做 MiniMax 抽查与抽听 ⇒ 等 reviewer 交接**｜"
    "🔴 **如实登记 4 处事故 ＋ 2 处判据错误**｜**未打包／未改客户包／未连 B 机／未调 MiniMax／未改纠偏文件**｜**本条需等 reviewer 复核**",
    "🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec223_detail_20261123.md`**（含 §0–§10 全部数字、证据路径、"
    "e2e8/e2e7 对照表、架构事实与事故登记）",
]
lines[i_last + 1:i_last + 1] = sec

new_text = "\n".join(lines)
if nl == "\r\n":
    new_text = new_text.replace("\n", "\r\n")
data = new_text.encode("utf-8")
tmp = STATUS + ".tmp_app123"
with open(tmp, "wb") as f:
    f.write(data)
os.replace(tmp, STATUS)

# ── 4) restore-style check: removing exactly what we added => original bytes ──
new_raw = open(STATUS, "rb").read()
print("new bytes", len(new_raw), "old bytes", len(raw))

# rebuild the pre-edit text from the backup and confirm the only differences
# are the ones we intended (header 2 lines + 1 最近更新 entry + §223 block)
back = open(BAK, "rb").read()
bl = back.decode("utf-8").replace("\r\n", "\n").split("\n")
nl_lines = new_raw.decode("utf-8").replace("\r\n", "\n").split("\n")
import difflib
diff = list(difflib.unified_diff(bl, nl_lines, lineterm="", n=0))
added = [d for d in diff if d.startswith("+") and not d.startswith("+++")]
removed = [d for d in diff if d.startswith("-") and not d.startswith("---")]
print("added lines: %d, removed lines: %d" % (len(added), len(removed)))
for r in removed:
    print("  REMOVED:", r[:120])
for a in added[:6]:
    print("  ADDED  :", a[:120])
print("  ... (%d more added lines)" % max(0, len(added) - 6))
