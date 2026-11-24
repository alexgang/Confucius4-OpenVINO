# -*- coding: utf-8 -*-
"""ASR §100 STATUS 写入器（v16 门禁）：更新头部 4 行 + 最近更新 + 追加 §100 章节。
纪律：载荷里不要出现英文单引号（§98 踩过 SyntaxError）；Windows 路径写正斜杠。
自指大小迭代到不动点；末尾 CRLF；≤40000 B、≤160 行。
"""
import io, os, re, shutil, sys

BASE = r"C:\Users\Trekker-PTL\confucius4-openvino\status\asr"
STATUS = os.path.join(BASE, "STATUS_ASR.md")
BAK = os.path.join(BASE, "STATUS_ASR.md.bak_asr100")

# --- 载荷（无 % 号、无英文单引号） ---
HEAD = [
    ("last_ack", "ASR-068"),
    ("更新时间", "2026-11-24 13:50"),
    ("自指大小", None),      # 占位，迭代填
    ("当前任务", None),      # 占位
]
# 当前任务（单行）
CURRENT_TASK = (
    "\U0001F7E2 **巡检（无新 ASR 纠偏）＋ ASR-099 归因缺口已闭（reviewer 落地 v0.4.21 导出）＋ e2e_v26 三臂独立复算（§100）**："
    "纠偏通道**无新 ASR 条目**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，"
    "与 §96–§99 逐字相同；最大编号 **ASR-068**；搜 `ASR-069`/`ASR-070`/`ASR-071` **0 命中**）⇒ **`last_ack` 保持 `ASR-068`**。"
    "邮件通道：收件箱 after 2026-11-24T02:47:13Z **0 封**（最新仍是 APP-131 02:47:12Z，已在 §99 处理）；主题含 `ASR-` 的最大编号 = ASR-068；spam 0、trash 1（rc9 报告，非纠偏）。"
    "🟢 **§97/§98/§99 的归因缺口已闭**：§99 邮件（11:38:55Z）建议的「把旁路 `reason` 分布 ＋ 克隆 `_reasons` 计数合并进 `stats_full`」已由 reviewer 在 **v0.4.21** 落地"
    "（证据 `shared/bgkeep/v0421_stage/ext/bridge.py` **290 855 B** / mtime **11:48:43**，**晚于 §99 邮件**；代码注释直书「v0.4.21 (ASR-099)」）"
    "⇒ 新增 `clone_reasons` / `spk_reason_hist` / `n_gender_splits` 三字段 ＋ `EXT_BG_DUMP_VOCALS` 分离人声 raw 落地。"
    "🟢 **独立复算验证**（reviewer 自己的 A/B `shared/bgkeep/gender_ab2`，v0.4.20 vs v0.4.21，7 分钟 `bili_420.wav`，`voice=clone`）："
    "`stats_full` 顶层 key 数 **42 → 45**；v0421 的 `clone_reasons` **18 键全在**，APP-131 验收第 2 项要的三个字段**现在都能取到数**"
    "（`tts_nearest_voice`=**9**、`gender_switch`=**3**、`gender_selfref`=**1**；v0420 臂这三个**字段不存在**）；"
    "`spk_reason_hist`={`none`:10,`label`:79} 合计 **89** = v0421 的 `asr_segments`=**89** ⇒ **100% 覆盖、零缺口** ⇒ 「旁路零标签不可归因」不再是死结。"
    "🟡 **git 现状**：reviewer 曾在工作区放 v0.4.21 草稿（5 文件 `M`，+102/−2）后**撤回** ⇒ 本轮复核时 `live_dub_ext` HEAD 仍 = **`4740b06`**（v0.4.20）、工作区**干净** ⇒ **v0.4.21 尚未提交** ⇒ 本模块**只读**、不评论、不代改、不提交。"
    "🟡 **e2e_v26 三臂独立复算**（`shared/bgkeep/e2e_v26`，600 s 全集，EXT v0.4.20）：三臂 `spk_bypass.enabled` **全 true**、`n_dropped`=0 全、`spk_queue_drop`=0 全、`bg_late_blocks`=0（两开臂）；"
    "`bg_clone_from_vocals` 只在 clone 臂 = **163**（on 臂 0）⇒ 克隆臂确走分离人声；"
    "🔴 **`dub_late_vs_play_s.max` 三臂都很大**（149.92 / 230.82 / 235.0 s）⇒ 配音严重迟到，但**属 App/TTS 排队时延口径**（APP-130 已指出 NPU `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS）⇒ 本模块**只记录不归因**。"
    "🔴 **本轮状态有实质变化 ⇒ 写 §100 章节 ＋ 发 STATUS 邮件**（不是纯巡检）。"
)

BLOCK_LINE = (
    "阻塞 / 待用户决定: 🟢 **无阻塞**（`last_ack` = **ASR-068**，本轮无新 ASR 纠偏）。"
    "🟢 **§97/§98/§99 的归因缺口已闭**（reviewer 落地 v0.4.21 导出 ＋ 本模块独立复算验证）。"
    "🔴 **待 reviewer**：**v0.4.21 提交**（当前 HEAD 仍 `4740b06`、工作区干净）；**开旁路臂**的 `spk_reason_hist` 分布（v0421 臂旁路是关的）；"
    "**修前（v0.4.18 / `5121d99`）对照臂**（§96 ① 仍未闭）。"
    "🔴 **待 App/reviewer 提供**：10 分钟片段**分离人声 16 kHz wav** ⇒ `EXT_BG_DUMP_VOCALS` 已实现（v0.4.21），但**本轮无任何 dump 产出**"
    "（`shared/bgkeep/vocals/` 仍不存在、全盘搜 `EXT_BG_DUMP_VOCALS` 产物 = 0 命中）⇒ 拿到后本模块做「原声 vs 分离人声」WER 对比"
    "（🔴 两侧须同一 ASR 臂：`pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。"
    "🟡 **待 App 线程决定**：NPU 档前缀截断处置（建议 ① `MAX_SEG_SEC` 20.0 → 19.0 s）；🔴 **§100 新增**：配音迟到（max 235 s）由 App/TTS 排队时延口径处置。"
    "🟡 **待用户/reviewer 决定**：README 是否加「NPU 档 20 s 长段会触发前缀截断」；「md5 逐字节相同」是否改标注；整段离线转写是否加成交付路径；"
    "「RTF≈0.05」对外口径；encoder 静态上限 2400 mel 帧 ⇒ 30 s 上下文得重导出；新说话人首次登记用哪段音频。"
    "⚠️ **待 App 侧落地**：README `--asr-device NPU` 示例能否给客户（🔴 发客户前必须确认发的是 `v1.1.1.zip`）。"
    "🟡 **丢块计数上报 ASR 侧**（§95 单开，§96 沿用）：EXT 只在自家 `stats()` 计 `spk_queue_drop`；另请明确「旁路 64 项」与 `ext/bg_separator.py` L242 `maxsize=4000` 两层丢块语义。"
)

RECENT_NEW = (
    "- 2026-11-24 13:50 **§100（巡检（无新 ASR 纠偏）＋ ASR-099 归因缺口已闭（reviewer 落地 v0.4.21 导出）＋ e2e_v26 三臂独立复算）："
    "纠偏通道无新 ASR 条目 ⇒ `last_ack` 保持 **ASR-068**；邮件通道 after 02:47:13Z **0 封**（最新 APP-131 已在 §99 处理）⇒ 本轮无 reviewer ASR 动作项。"
    "🟢 **§97/§98/§99 归因缺口已闭**：reviewer 在 v0.4.21 落地 `clone_reasons` / `spk_reason_hist` / `n_gender_splits`（`shared/bgkeep/v0421_stage/ext/bridge.py` **290 855 B** / 11:48:43，"
    "注释直书「ASR-099」）＋ `EXT_BG_DUMP_VOCALS`；独立复算 `shared/bgkeep/gender_ab2/v0421/bgkeep_e2e.json`（**26 543 B** / 13:45:39）：`stats_full` 顶层 **42 → 45** key，"
    "`clone_reasons` **18 键全在**，APP-131 要的 `tts_nearest_voice`=**9** / `gender_switch`=**3** / `gender_selfref`=**1**（v0420 臂**字段不存在**），"
    "`spk_reason_hist` 合计 **89** = `asr_segments` **89** ⇒ 零缺口。🟡 **v0.4.21 未提交**（HEAD 仍 `4740b06`、工作区干净）⇒ 本模块只读。"
    "🟡 **e2e_v26 三臂复算**（`shared/bgkeep/e2e_v26/*/bgkeep_e2e.json`，600 s，EXT v0.4.20）：三臂 `spk_bypass.enabled` 全 true、`n_dropped`=0、`spk_queue_drop`=0；"
    "`bg_clone_from_vocals` 只在 clone 臂 = **163**；🔴 `dub_late_vs_play_s.max` 三臂 = 149.92 / 230.82 / **235.0** s ⇒ 配音严重迟到（属 App/TTS 排队时延口径，本模块只记录不归因）。"
    "产物：`status/asr/notes/asr_s100.md` ＋ `status/archive/STATUS_ASR_sec100_upto_20261124.md`。**待 reviewer**：v0.4.21 提交 ＋ 开旁路臂 ＋ 修前对照臂；"
    "**待 App/reviewer**：分离人声 16 kHz wav（`EXT_BG_DUMP_VOCALS` 已实现但本轮 0 产出）。**纪律**：本轮全为只读复算、未取 MACHINE_LOCK（锁由 reviewer 持有）、未改交付文件、未动 `live_caption/`、未改 EXT 源码、未打包。**未提交**。"
)

SEC100_BODY = """### §100 巡检（无新 ASR 纠偏）＋ ASR-099 归因缺口已闭（reviewer 落地 v0.4.21 导出）＋ e2e_v26 三臂独立复算（2026-11-24 13:23–13:50）

> 🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，与 §96–§99 逐字相同；最大编号 **ASR-068**；搜 `ASR-069`/`ASR-070`/`ASR-071` **0 命中**）。
> 🟢 **邮件通道无新 reviewer ASR 邮件**（收件箱 after 2026-11-24T02:47:13Z ⇒ **0 封**；最新仍是 **APP-131** 02:47:12Z，已在 §99 处理）；spam **0**、trash **1**（rc9 报告，非纠偏）。
> 🔴 **本轮不是纯巡检**（有实质状态变化）⇒ 写 §100 章节 ＋ 发 STATUS 邮件。

#### §100.1 🟢 §97/§98/§99 的「reason 归因缺口」已闭（reviewer 落地 v0.4.21 导出 ＋ 本模块独立复算）

- **§99 提的开口项，reviewer 已实现**：§99 邮件（11:38:55Z）建议把「旁路 `reason` 分布」＋「克隆 `_reasons` 计数」**合并**进 `stats_full`。证据 = `shared/bgkeep/v0421_stage/ext/bridge.py`（**290 855 B** / mtime **11:48:43**，**晚于 §99 邮件**）：`ext/bridge.py` L2139–2142（`bg_stats()`）新增 `clone_reasons`（读 `self._clone._reasons`）/ `spk_reason_hist` / `n_gender_splits`；L2145–2153（新增 `_spk_reason_hist()`）从 `self._spk_rows` 聚合 `spk_reason`；L1933–1938（`_on_bg_vocals`）新增 `EXT_BG_DUMP_VOCALS`（分离人声 16 kHz s16 raw 落地，供离线 WER）。
- 🔴 代码注释**直书「v0.4.21 (ASR-099)」** ⇒ 本模块 §99 编号被正式接收。🟡 **git 现状**：reviewer 曾在工作区放 v0.4.21 草稿（5 文件 `M`，+102/−2）后**撤回** ⇒ 复核时 HEAD 仍 = **`4740b06`**（v0.4.20）、工作区**干净** ⇒ **v0.4.21 尚未提交**；本模块**只读**、不评论、不代改、不提交。
- **🟢 实测验证（reviewer 自己的 A/B `shared/bgkeep/run_gender_ab2.ps1`；7 分钟 `bili_420.wav`，`voice=clone`）**：`stats_full` 顶层 key 数 **v0420 = 42 → v0421 = 45**；v0420 臂三个新字段**不存在**，v0421 臂 `clone_reasons` **18 键全在**、`spk_reason_hist` 在、`n_gender_splits`=**3**。产物：`shared/bgkeep/gender_ab2/v0420/bgkeep_e2e.json`（**25 852 B** / 13:37:06）、`gender_ab2/v0421/bgkeep_e2e.json`（**26 543 B** / 13:45:39）、`v0421/bridge.log`（**45 011 B** / 13:45:36）。
- **🔴 APP-131 验收第 2 项要的三个字段，现在都能取到数**（v0420 臂是**字段不存在**，不是值为 0）：`tts_nearest_voice`=**9**、`gender_switch`=**3**、`gender_selfref`=**1**。完整 18 键：`label`=82、`provisional`=76、`guard_keep`=70、`guard_short`=11、`self_ref`=9、`tts_nearest_voice`=9、`timeout`=5、`guard_pending`=4、`spk_split`=4、`fallback`=3、`gender_switch`=3、`guard_no_emb`=2、`self_ref_unvoiced`=2、`tts_nearest`=2、`gender_keep`=1、`gender_selfref`=1、`guard_new`=1、`guard_match`=1。
- **🟢 旁路 `reason` 分布可对账、零缺口**：`spk_reason_hist`={`none`:10,`label`:79} ⇒ 合计 **89** = v0421 的 `asr_segments`=`mt_segments`=`tts_segments`=**89** ⇒ **100% 覆盖**；取值域已核对 `ext/spk_engine.py` L459/462/467/479/482（`audio_not_buffered`/`too_short`/`not_clean_speech`/`overlap` ＋ `label`/`none`）⇒ **不是臆造字段** ⇒ **§97 的「旁路零标签永远不可归因」不再是死结**。🟡 但 **v0421 臂旁路是关的**（`spk_bypass.enabled=false`）⇒ 该分布反映**克隆模式**段级标签来源；**开旁路臂的分布仍需 reviewer 另跑一臂**（本模块**不代做**）。

#### §100.2 🟡 e2e_v26 三臂独立复算（§99 未记录这批产物）

产物：`shared/bgkeep/e2e_v26/{bgkeep_off,bgkeep_on,bgkeep_clone}/bgkeep_e2e.json`（**26 399 B** / 12:44:55、**24 483 B** / 12:56:13、**28 663 B** / 13:07:36）；素材 `clip_10min_0_600.wav`（600 s）、`delay=20`、EXT = **v0.4.20 `4740b06`**（三臂 bridge.log 首行版本一致）。

| 指标 | bgkeep_off | bgkeep_on | bgkeep_clone |
|---|---|---|---|
| `bg_state` / `bg_blocks` / `bg_covered_s` | `off` / 0 / 0.0 | `ok` / 600 / 600.0 | `ok` / 600 / 600.0 |
| `bg_late_blocks` | 0 | **0** | **0** |
| `bg_margin_min_s` / `median_s` | — / — | 8.96 / 12.03 | 8.97 / 12.14 |
| `sep_rtf_p50` / `p90` | — / — | 0.255 / 0.278 | 0.241 / 0.281 |
| `sep_device` / `sep_compile_s` | — / — | GPU.0 / 3.67 | GPU.0 / 3.91 |
| `bg_clone_from_vocals` | 0 | **0** | **163** |
| `bg_onset_no_vocals` / `bg_onset_shifted` | 0 / 0 | 72 / 1 | 93 / 2 |
| `asr`/`mt`/`tts` 段数 | 87/87/87 | 73/73/73 | 95/95/95 |
| `dubs` | 88 | 73 | **97** |
| `dub_late_vs_play_s` max / p90 / n_late | 149.92 / 129.61 / 85 | 230.82 / 192.23 / 71 | **235.0** / 212.37 / 93 |
| `spk_bypass.enabled` / `n_label` / `n_no_label` / `n_pending` / `n_final_req` | true / 118 / 3 / 0 / 121 | true / 116 / 2 / 0 / 121 | true / 139 / 24 / **1** / 164 |
| `spk_queue_drop` / `speaker.n_speakers` / `n_dropped` / `n_frames` | 0 / 1 / 0 / 5951 | 0 / 1 / 0 / 5951 | 0 / 1 / 0 / 5951 |

- 🟢 **三臂旁路全开且全有效** ⇒ §96 的 A 项在 **10 分钟全集**上再次复现；`n_dropped`=0 全、`spk_queue_drop`=0 全、`bg_late_blocks`=0（两开臂）⇒ 无丢块、无背景迟到。🟢 `bg_clone_from_vocals` 只在 clone 臂 = **163**（on 臂 0）⇒ 克隆臂确实走「分离人声」路径。
- 🔴 **口径提醒**：`speaker.n_speakers` 三臂都 = **1**，而 `spk_bypass.n_label` = 118/116/139 ⇒ **再次印证 §99 澄清**：克隆/旁路模式下 `speaker.n_speakers` **不能**当「旁路有没有标签」的判据（旁路看 `spk_bypass.n_label`）。
- 🔴 **`dub_late_vs_play_s.max` 三臂都很大**（149.92 / 230.82 / 235.0 s）⇒ **配音严重迟到**；但 🔴 **本模块不代做判定**：属 App/TTS 链路的排队时延（`bg_onset_no_vocals` 72/93 也高），且 APP-130 已指出 NPU 上 `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS ⇒ **属 App 线程口径**，本模块**只记录不归因**。

#### §100.3 纪律

未跑推理 / 计时 / WER / 分离器（本轮**全部只读复算既有产物**）⇒ 不需 MACHINE_LOCK；观察期间锁由 reviewer 持有（`reviewer gender ab 2026-11-24T13:28:20`）⇒ 本模块**始终未取锁**、未干扰 reviewer 作业。未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未打包；未提交 EXT。产物：`status/asr/notes/asr_s100.md`（**10 050 B** / LF）＋ `status/archive/STATUS_ASR_sec100_upto_20261124.md`。
"""

ARCHIVE_LINK = (
    "- ✅ **§100（巡检（无新 ASR 纠偏）＋ ASR-099 归因缺口已闭（reviewer 落地 v0.4.21 导出）＋ e2e_v26 三臂独立复算（2026-11-24 13:23–13:50））**："
    "**全文已归档** ⇒ `status/archive/STATUS_ASR_sec100_upto_20261124.md` ＋ `status/asr/notes/asr_s100.md`"
)


def build(size_field, current_task, block_line, recent_new, sec_body):
    raw = open(STATUS, "rb").read().decode("utf-8")
    lines = raw.split("\r\n")
    # 头部 4 行
    lines[0] = "last_ack: ASR-068"
    lines[1] = "更新时间: 2026-11-24 13:50"
    lines[2] = "自指大小: %s" % size_field
    lines[3] = "当前任务: %s" % current_task
    lines[4] = block_line
    # 最近更新：新的写在最上面
    idx = lines.index("## 最近更新")
    # 找到该节第一行 bullet
    j = idx + 1
    while j < len(lines) and not lines[j].startswith("- "):
        j += 1
    lines.insert(j, recent_new)
    # 章节：先处理「最近章节」区的归档行，再替换正文 §99 章节
    arch_idx = None
    for i, l in enumerate(lines):
        if l.startswith("- ✅ **§99"):
            arch_idx = i
            break
    if arch_idx is None:
        raise SystemExit("FAIL: §99 archive link not found")
    lines[arch_idx] = ARCHIVE_LINK
    # 归档链接总数保持 5 ⇒ 删掉最老的 §94 行
    for i in range(arch_idx - 1, -1, -1):
        if lines[i].startswith("- ✅ **§94"):
            del lines[i]
            break

    # 移除 §99 正文章节（从 k 到文件末尾的非空尾部）
    k = None
    for i, l in enumerate(lines):
        if l.startswith("### §99 "):
            k = i
            break
    if k is None:
        raise SystemExit("FAIL: §99 section not found")
    tail = lines[k:]
    while tail and tail[-1].strip() == "":
        tail.pop()
    lines = lines[:k]
    lines.append("")
    lines.append(sec_body.replace("\r\n", "\n").rstrip("\n").replace("\n", "\r\n"))
    lines.append("")
    out = "\r\n".join(lines)
    return out


def main():
    if not os.path.exists(BAK):
        shutil.copy2(STATUS, BAK)
    size_field = "0 B / 0 行"
    prev = None
    for _ in range(30):
        out = build(size_field, CURRENT_TASK, BLOCK_LINE, RECENT_NEW, SEC100_BODY)
        b = out.encode("utf-8")
        n_crlf = b.count(b"\r\n")
        n_lines = n_crlf + 1
        new_field = "%d B / %d 行" % (len(b), n_lines)
        if new_field == size_field and prev == len(b):
            break
        prev = len(b)
        size_field = new_field
    else:
        raise SystemExit("FAIL: no fixed point")

    # 最终构建（size_field 已收敛）
    out = build(size_field, CURRENT_TASK, BLOCK_LINE, RECENT_NEW, SEC100_BODY)
    b = out.encode("utf-8")
    n_crlf = b.count(b"\r\n")
    n_lines = n_crlf + 1
    # 门禁
    assert b.count(b"\n") - n_crlf == 0, "bare LF present"
    assert b.endswith(b"\r\n"), "must end with CRLF"
    assert len(b) <= 40000, "too big: %d" % len(b)
    assert n_lines <= 160, "too many lines: %d" % n_lines
    # 自指大小自洽
    field = "自指大小: %d B / %d 行" % (len(b), n_lines)
    assert lines_field_ok(out, field), "self size mismatch"
    open(STATUS, "wb").write(b)
    print("WROTE", len(b), "bytes", n_lines, "lines")
    print("field:", field)


def lines_field_ok(out, field):
    for l in out.split("\r\n"):
        if l.startswith("自指大小: "):
            return l == field
    return False


if __name__ == "__main__":
    main()
