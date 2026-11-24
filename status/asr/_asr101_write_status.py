# -*- coding: utf-8 -*-
"""ASR §101 STATUS 写入器（v16 门禁）：更新头部 4 行 + 最近更新 + 追加 §101 章节。
纪律：载荷里不要出现英文单引号（§98 踩过 SyntaxError）；Windows 路径写正斜杠。
自指大小迭代到不动点；末尾 CRLF；≤40000 B、≤160 行。
"""
import os, shutil

BASE = r"C:\Users\Trekker-PTL\confucius4-openvino\status\asr"
STATUS = os.path.join(BASE, "STATUS_ASR.md")
BAK = os.path.join(BASE, "STATUS_ASR.md.bak_asr101")

CURRENT_TASK = (
    "🟢 **巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 b2a4978 ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「spk_reason_hist 零缺口」结论（§101）**："
    "纠偏通道**无新 ASR 条目**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，"
    "与 §96–§100 逐字相同；最大编号 **ASR-068**；搜 `ASR-069`/`ASR-070`/`ASR-071` **0 命中**）⇒ **`last_ack` 保持 `ASR-068`**。"
    "邮件新增 **5 封、全部非 ASR 编号**（APP-132、APP-133、QQ邮箱通知、NPU 性能报告、H-028）⇒ 不进本模块 `last_ack`；spam 0、trash 1（非纠偏）。"
    "🟢 **EXT v0.4.21 已提交** ⇒ HEAD **`b2a4978`**（13:54:52，5 文件 +102/−2，工作区干净）⇒ §100「未提交、HEAD 仍 4740b06」**已过时、撤回该句**。"
    "🟢 **新三臂 `shared/bgkeep/e2e_v26_r2`**（App 模块产出、本模块只读复算；EXT v0.4.21；600 s）：三臂 `spk_bypass.enabled` **全 true** ⇒ **§100 遗留「开旁路臂」已闭**；"
    "`bg_clone_from_vocals` 只在 clone 臂 = **167**；两开臂 `bg_late_blocks`=0、`n_dropped`=0、`spk_queue_drop`=0；段数 94/89/111、`dubs` 95/90/114、`dub_dropped` 全 0；"
    "🔴 `dub_late_vs_play_s.max` = 115.42 / 139.22 / **182.62** s ⇒ 配音仍严重迟到（App/TTS 口径，只记录不归因）；🟡 段数不可与 §100 的 e2e_v26（87/73/95，v0.4.20）直接对比（非受控 A/B）。"
    "🔴🔴 **撤回 §100.1「`spk_reason_hist` 零缺口 / 100% 覆盖」**：r2 三臂直方图合计 = **119/118/159** 而 `asr_segments` = **94/89/111** ⇒ 对不上；"
    "机理 = `_spk_reason_hist()` 统计**段级表 `_spk_rows` 行数**，该表两个写入点（L2533 带 `spk_reason` ＋ L2915 不带）⇒ **收口路径的行被并进 label 桶**、分母浮动；"
    "🔴 **旁路失败原因结构上进不了该表**（失败分支只 `n_no_label += 1`、不写行 ⇒ `spk_engine.on_final()` 的 7 个否定 reason 不可达）；🟢 全部 7 个带该字段的臂取值域**只有 `{label, none}`**；"
    "🔴 clone 臂 **24 段「为什么没标签」被丢掉**（`n_no_label`=27 vs `none`=3）、`label`=156 > 旁路 `n_label`=139；🟡 §100 的 89=89 **是巧合**（那个 v0421 臂旁路是关的）⇒ **§97/§98 原始诉求仍开口**。"
    "🟡 r2 clone 臂 `clone_reasons` **12 键**（v0421 臂 18 键）：APP-131 三字段 = `tts_nearest_voice`=**1**、`gender_switch`/`gender_selfref` **键不存在**。"
    "🟢 **本轮有实质变化 ＋ 一条撤回 ⇒ 写 §101 章节 ＋ 发 STATUS 邮件**。"
)

BLOCK_LINE = (
    "阻塞 / 待用户决定: 🟢 **无阻塞**（`last_ack` = **ASR-068**，本轮无新 ASR 纠偏）。"
    "🟢 **§100 遗留 reviewer 2 项已闭 1 项**：「提交 v0.4.21」已闭（`b2a4978`）；「开旁路臂」已闭（r2 三臂旁路全开）。"
    "🔴🔴 **待 reviewer（新）**：**旁路失败原因的归因缺口仍未闭** ⇒ 需让旁路**失败路径也写进段级表**（或由 `spk_bypass.stats()` 导出否定 reason 计数）；"
    "只调 `_spk_reason_hist()` 聚合口径**解决不了**（`ext/speaker_bypass.py` L431 失败分支只 `n_no_label += 1`、**不写行** ⇒ 7 个否定 reason 结构上不可达）。"
    "🔴 **待 reviewer（沿用）**：**修前（v0.4.18 / `5121d99`）对照臂**（§96 ① 仍未闭；`shared/bgkeep/` 下无 `v0418*` 目录）。"
    "🔴 **待 App/reviewer 提供**：10 分钟片段**分离人声 16 kHz wav** ⇒ `EXT_BG_DUMP_VOCALS`（L1933）已实现**且已提交**，但 `shared/bgkeep/vocals/` **仍不存在**、全盘搜 `*vocal*` **0 命中** "
    "⇒ 「原声 vs 分离人声」WER 对比仍做不了（🔴 两侧须同一 ASR 臂：`pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。"
    "🟡 **待 reviewer 拍板（新）**：对外《NPU 性能测试与精度报告》（07:46:40Z）写的 **ASR RTF 0.067 / 英文 WER 0 / 中文 CER 0** 与本模块 §83 / ASR-060～061 实测"
    "**不是同一计分器**（本模块 NPU 流式 RTF 0.3094/0.2912/0.3165、离线 0.0496/0.0448/0.0665；SPE 全局 WER 9.74%/6.30%）⇒ 请说明 **0.067 的口径**；"
    "🟡 报告称完整表在 `results/npu_benchmark/`，**本机未找到该路径** ⇒ 若需本模块复核请提供位置。"
    "🟡 **待 App 线程决定**：NPU 档前缀截断处置（建议 ① `MAX_SEG_SEC` 20.0 → 19.0 s）；配音迟到（max 182.62 s）按 App/TTS 排队时延口径处置。"
    "🟡 **待用户/reviewer 决定**：README 是否加「NPU 档 20 s 长段会触发前缀截断」；「md5 逐字节相同」是否改标注；整段离线转写是否加成交付路径；「RTF≈0.05」对外口径；"
    "encoder 静态上限 2400 mel 帧 ⇒ 30 s 上下文得重导出；新说话人首次登记用哪段音频。"
    "⚠️ **待 App 侧落地**：README `--asr-device NPU` 示例能否给客户（🔴 发客户前必须确认发的是 `v1.1.1.zip`）。"
    "🟡 **丢块计数上报 ASR 侧**（§95 单开）：EXT 只在自家 `stats()` 计 `spk_queue_drop`；另请明确「旁路 64 项」与 `ext/bg_separator.py` L242 `maxsize=4000` 两层丢块语义。"
)

RECENT_NEW = (
    "- 2026-11-24 19:05 **§101（巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 b2a4978 ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「spk_reason_hist 零缺口」结论）："
    "纠偏通道无新 ASR 条目 ⇒ `last_ack` 保持 **ASR-068**；邮件新增 **5 封全部非 ASR 编号** ⇒ 无 ASR 动作项。"
    "🟢 **EXT v0.4.21 已提交**（HEAD **`b2a4978`**，13:54:52，5 文件 +102/−2，工作区干净）⇒ §100「未提交、HEAD 仍 4740b06」**已过时、撤回该句**。"
    "🟢 **新三臂 `shared/bgkeep/e2e_v26_r2`**（App 模块产出、本模块只读复算；EXT v0.4.21；600 s）：三臂 `spk_bypass.enabled` **全 true** ⇒ **§100 遗留「开旁路臂」已闭**；"
    "`bg_clone_from_vocals` 只在 clone 臂 = **167**；两开臂 `bg_late_blocks`=0、`n_dropped`=0、`spk_queue_drop`=0；段数 94/89/111、`dubs` 95/90/114；"
    "🔴 `dub_late_vs_play_s.max` = 115.42 / 139.22 / **182.62** s ⇒ 配音仍严重迟到（App/TTS 口径）；🟡 段数不可与 §100 的 e2e_v26 直接对比（非受控 A/B）。"
    "🔴🔴 **撤回 §100.1「零缺口 / 100% 覆盖」**：r2 直方图合计 = **119/118/159** 而 `asr_segments` = **94/89/111**；机理 = 段级表两个写入点（收口路径的行被并进 label 桶）"
    "＋ **旁路失败原因结构上进不了该表**；🟢 全部 7 个带该字段的臂取值域只有 `{label, none}`；🔴 clone 臂 **24 段「为什么没标签」被丢掉**、`label`=156 > 旁路 `n_label`=139；"
    "🟡 §100 的 89=89 **是巧合**（那个臂旁路是关的）⇒ **§97/§98 原始诉求仍开口**。"
    "🟡 r2 clone 臂 `clone_reasons` **12 键**：APP-131 三字段 = `tts_nearest_voice`=**1**、`gender_switch`/`gender_selfref` **键不存在**。"
    "产物：`status/asr/notes/asr_s101.md` ＋ `status/archive/STATUS_ASR_sec101_upto_20261124.md`（§100 全文逐字）。"
    "**待 reviewer**：旁路失败原因归因缺口（新）＋ 修前对照臂（沿用）；**待 App/reviewer**：分离人声 16 kHz wav；**待 reviewer 拍板**：对外 NPU 报告 ASR「RTF 0.067 / WER 0」口径。"
    "**纪律**：本轮全为只读复算、未取 MACHINE_LOCK（全程无锁）、未改交付文件、未动 `live_caption/`、未改 EXT 源码、未打包。**未提交**。"
)

SEC101_BODY = """### §101 巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 `b2a4978` ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「`spk_reason_hist` 零缺口」结论（2026-11-24 18:37–19:05）

> 🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，与 §96–§100 逐字相同；最大编号 **ASR-068**；搜 `ASR-069`/`ASR-070`/`ASR-071` **0 命中**）。邮件新增 **5 封全部非 ASR 编号**（APP-132、APP-133、QQ邮箱通知、NPU 性能报告、H-028）⇒ 不进 `last_ack`；spam **0**、trash **1**（非纠偏）。🔴 **本轮不是纯巡检**（EXT 状态变化 ＋ 一条撤回）⇒ 写 §101 ＋ 发 STATUS 邮件。明细 ⇒ `status/asr/notes/asr_s101.md`。

#### §101.1 🟢 EXT v0.4.21 **已提交**（§100 的「未提交」已过时 ⇒ 撤回该句）

HEAD = **`b2a4978e2f671836c2e464db528e02d138884df9`**（commit **2026-11-24 13:54:52**），范围 **5 文件 / +102 −2**（`ext/bridge.py` +34、`ext/clone_voice.py` +55、`ext/version.py` +2/−1、`extension/manifest.json` +2/−1、`tests/test_ext0420_clone_gender.py` +11），工作区**干净**。⇒ §100 的「v0.4.21 未提交、HEAD 仍 `4740b06`」**已过时**，按纪律**在 §101 撤回该句**（不改旧章节正文）⇒ §100 遗留 reviewer 事项 **① 已闭**。

#### §101.2 🟢 新三臂 `e2e_v26_r2`（旁路全开）⇒ §100 遗留 reviewer 事项 **② 已闭**

产出方 = **App 模块** `results/app/_app133_chain_v26.py`（`OUT_ROOT = shared/bgkeep/e2e_v26_r2`，L74）；本模块**只读复算**。产物共 **28 个文件**；素材 `clip_10min_0_600.wav`（600 s）、`delay=20`；三臂 `bridge.log` 首行均为「实时配音桥接 **v0.4.21**」⇒ EXT = `b2a4978`（§100 的 e2e_v26 是 v0.4.20 `4740b06`）。

| 指标 | bgkeep_off | bgkeep_on | bgkeep_clone |
|---|---|---|---|
| `client_voice` | A | A | **clone** |
| `bg_state` / `bg_blocks` / `bg_covered_s` | `off` / 0 / 0.0 | `ok` / 600 / 600.0 | `ok` / 600 / 600.0 |
| `bg_late_blocks` | 0 | **0** | **0** |
| `bg_margin_min_s` / `median_s` | — / — | 9.28 / 12.43 | 9.06 / 12.35 |
| `sep_rtf_p50` / `p90` | — / — | 0.202 / 0.219 | 0.205 / 0.239 |
| `sep_device` / `sep_compile_s` | — / — | GPU.0 / 4.5 | GPU.0 / 3.05 |
| `bg_clone_from_vocals` | 0 | **0** | **167** |
| `bg_onset_no_vocals` / `bg_onset_shifted` | 0 / 0 | 86 / 2 | 108 / 3 |
| `asr`/`mt`/`tts` 段数 | 94/94/94 | 89/89/89 | 111/111/111 |
| `dubs` / `dub_dropped` | 95 / 0 | 90 / 0 | 114 / 0 |
| `dub_late_vs_play_s` max / p90 / n_late | 115.42 / 105.56 / 90 | 139.22 / 122.58 / 87 | **182.62** / 161.25 / 110 |
| `spk_bypass.enabled` / `n_label` / `n_no_label` / `n_pending` / `n_final_req` | true / 118 / 3 / 0 / 121 | true / 116 / 2 / 0 / 121 | true / **139** / **27** / 0 / **168** |
| `spk_reason_hist` | `{none:1, label:118}` | `{none:4, label:114}` | `{none:3, label:156}` |
| `clone_reasons`（键数 / 事件数合计） | {} / 0 | {} / 0 | **12** / 348 |
| `n_gender_splits` | 0 | 0 | **4** |
| `spk_queue_drop` / `n_dropped` / `n_frames` | 0 / 0 / 5951 | 0 / 0 / 5951 | 0 / 0 / 5951 |

文件级证据：`bgkeep_off/bgkeep_e2e.json` **27 752 B** / 17:56:26（md5 `77bcc17e9895…`）、`bridge.log` **29 899 B** / 17:56:31；`bgkeep_on/bgkeep_e2e.json` **27 427 B** / 18:07:49（md5 `5b06be8943ab…`）、`bridge.log` **28 699 B** / 18:07:53；`bgkeep_clone/bgkeep_e2e.json` **31 911 B** / 18:19:10（md5 `bc62ee4f6ba6…`）、`bridge.log` **54 849 B** / 18:19:17。

- 🟢 **三臂 `spk_bypass.enabled` 全 true** ⇒ §100 手上只有旁路**关**着的 v0421 臂 ⇒ 遗留事项 **② 已闭**；`bg_clone_from_vocals` 只在 clone 臂 = **167** ⇒ clone 臂确实走「分离人声」；两开臂 `bg_late_blocks`=0、`n_dropped`=0、`spk_queue_drop`=0。
- 🔴 **配音仍严重迟到**（max 115.42 / 139.22 / **182.62** s）⇒ 属 App/TTS 排队时延口径（APP-130：NPU `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS）⇒ **本模块只记录不归因**。
- 🟡 **段数不可与 §100 的 e2e_v26 直接对比**（87/73/95 → 94/89/111）：v0.4.21 改了切段逻辑且本批由 App 链路跑 ⇒ **不是受控 A/B**。

#### §101.3 🔴🔴 撤回 §100.1「`spk_reason_hist` 零缺口 / 100% 覆盖」⇒ §97/§98 原始诉求**仍开口**

| 臂 | `spk_reason_hist` 合计 | `asr_segments` | `margin.n_segments` | `n_final_req` | `n_label` / `n_no_label` |
|---|---|---|---|---|---|
| bgkeep_off | **119** | 94 | 94 | 121 | 118 / 3 |
| bgkeep_on | **118** | 89 | 89 | 121 | 116 / 2 |
| bgkeep_clone | **159** | 111 | 113 | 168 | 139 / 27 |

⇒ §100 的「合计 = `asr_segments` ⇒ 100% 覆盖、零缺口」**在 r2 上不成立**。

**机理（读 HEAD `b2a4978`）**：`ext/bridge.py` L2145–2153 `_spk_reason_hist()` 统计 **`self._spk_rows`（段级说话人表）行数**，该表**两个写入点** —— ① **L2533 `_on_spk_label()`**（只有旁路**产出标签**时才写，带 `spk_reason`）；② **L2915 `_finalize_segment()`**（每个 ASR 段收口都写，**不带** `spk_reason`）。于是 L2151 的 `spk_reason or ("label" if spk else "none")` 把**收口路径的行也并入直方图** ⇒ **'label' 桶混了两种来源**、分母随两条路径到达情况浮动 ⇒ 与 `asr_segments`（L2864，**只统计有文本的段**）**无结构性相等关系**。

**🔴 更关键：旁路「失败原因」在结构上进不了这个直方图**（这正是 §97/§98 要的东西）：`spk_reason` 全仓**只有一个写入点**（L2538）；`_on_spk_label` 只作为 `on_label` 回调（L3377）被调用，调用方 `ext/speaker_bypass.py` 的 `_emit_label()` **只在 `if spk:` 分支触发**（L420–422）；**失败分支只做 `n_no_label += 1`（L431）、不写任何行** ⇒ 段级表里**没有**这一段 ⇒ 直方图里**没有**它的 reason。而 `ext/spk_engine.py` `on_final()` 的 **7 个否定 reason**（`models_not_ready`/`audio_not_buffered`/`too_short`/`seg_pending`/`not_clean_speech`/`overlap`/`embed_shape_out_of_range`）**全部只在失败路径上** ⇒ **结构上不可达**。**实测佐证**：`shared/bgkeep/` 下**全部 7 个**带 `spk_reason_hist` 的臂取值域**只有 `{label, none}`**。**量化缺口（r2 clone 臂）**：`n_no_label` = **27** 但直方图 `'none'` 只有 **3** ⇒ **24 段「为什么没标签」被丢掉**；`'label'` = **156** > 旁路 `n_label` = **139**（多 **17**）⇒ 再证「收口路径的行被并进 label 桶」。

**§100 那次能对上（89 = 89）是巧合**：那个 `gender_ab2/v0421` 臂 **`spk_bypass.enabled = false`** ⇒ **没有一行来自 `_on_spk_label`** ⇒ 直方图全部由收口路径构成 ⇒ 恰等于 `asr_segments`（89）。§101 的 r2 **三臂旁路全开** ⇒ 两种来源混在一起 ⇒ 对不上。⇒ **§100.1 的「零缺口 ⇒『旁路零标签不可归因』不再是死结」结论撤回**；**§97/§98 原始诉求（旁路零标签为什么 ⇒ 要能归因）仍开口**。

**给 reviewer 的最小修法（本模块不代改）**：需**把失败路径也写进段级表** —— `ext/speaker_bypass.py` 失败分支（L429–431）也回调一次 `on_label`（带 `spk=None` ＋ `reason`），或让 `spk_bypass.stats()` 直接导出**否定 reason 计数**（旁路侧本来就有 `res["reason"]`）。**只调 `_spk_reason_hist()` 的聚合口径解决不了**（数据压根没进表）。

#### §101.4 🟡 r2 clone 臂 `clone_reasons` 只有 **12 键**（v0421 臂 18 键）

- 12 键全量：`label`=61、`provisional`=159、`guard_keep`=66、`guard_short`=45、`timeout`=6、`guard_no_emb`=2、`self_ref_unvoiced`=2、`self_ref`=1、`fallback`=2、`tts_nearest`=1、`tts_nearest_voice`=**1**、`gender_keep`=2（**事件数**合计 **348**）；缺 6 键：`gender_selfref`、`gender_switch`、`guard_match`、`guard_new`、`guard_pending`、`spk_split`。
- 🔴 **APP-131 验收第 2 项三字段在 10 分钟臂上**：`tts_nearest_voice` = **1**（有值）；`gender_switch` = **键不存在**（不是值为 0）；`gender_selfref` = **键不存在** ⇒ **10 分钟臂上性别守门一次都没触发**。
- 🟡 与 §100 的 v0421 臂（7 分钟 `bili_420.wav`：`tts_nearest_voice`=9、`gender_switch`=3、`gender_selfref`=1）**媒体不同 ⇒ 不可直接对比**；🟡 `clone_reasons` 是**事件计数**、`spk_reason_hist` 是**行数** ⇒ **两口径不同、不能相加**；🟡 `bgkeep_clone/bridge.log` L345 那行「标签来源统计」是**跑中快照** ⇒ **以 json 为准**。

#### §101.5 🟡 仍未闭的旧开口项 ＋ 新增待拍板项

- 🔴 **修前（v0.4.18 / `5121d99`）对照臂仍缺**：`shared/bgkeep/` 下**无** `v0418*` 目录 ⇒ §96 ① 仍未闭。
- 🔴 **分离人声 dump 仍 0 产出**：`EXT_BG_DUMP_VOCALS`（L1933）已实现**且已提交**，但 `shared/bgkeep/vocals/` **仍不存在**、全盘搜 `*vocal*` **0 命中** ⇒ 「原声 vs 分离人声」WER 对比仍做不了。
- 🟡 **新待 reviewer 拍板：对外《NPU 性能测试与精度报告》（07:46:40Z，用户自发到 intel.com）的 ASR 数字口径** —— 报告写 **RTF 0.067、英文 WER 0 / 中文 CER 0**（MiniMVP v1.1.1、OV 2026.4.1）；🔴 **与本模块 §83 / ASR-060～061 实测不是同一计分器**（本模块 NPU **流式** RTF 0.3094/0.2912/0.3165、**离线** 0.0496/0.0448/0.0665；SPE 全局 WER 9.74%/6.30%）⇒ 0.067 落在**离线**量级、而「WER 0 / CER 0」显然不是 SPE 10 分钟全局 WER ⇒ **本模块不自行改对外口径**，请 reviewer 说明 0.067 的口径；🟡 报告称完整表在 `results/npu_benchmark/`，**本机未找到该路径** ⇒ 若需本模块复核请提供位置。

#### §101.6 纪律

本轮**全部只读复算既有产物**（未跑推理 / 计时 / WER / 分离器）⇒ **不需 MACHINE_LOCK**；复核前后各查一次 `shared/MACHINE_LOCK`，**均不存在** ⇒ 本模块**始终未取锁**、未干扰 App/reviewer 作业。未改 4 个 ASR 交付文件；未动 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未打包；未提交 EXT。产物：`status/asr/notes/asr_s101.md` ＋ `status/archive/STATUS_ASR_sec101_upto_20261124.md`（§100 全文逐字）＋ `_asr101_write_status.py` ＋ `_asr101_email_body_sent.txt`。
"""

ARCHIVE_LINK = (
    "- ✅ **§101（巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 `b2a4978` ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「`spk_reason_hist` 零缺口」结论（2026-11-24 18:37–19:05））**："
    "**全文已归档** ⇒ `status/archive/STATUS_ASR_sec101_upto_20261124.md` ＋ `status/asr/notes/asr_s101.md`"
)


def build(size_field, current_task, block_line, recent_new, sec_body):
    raw = open(STATUS, "rb").read().decode("utf-8")
    lines = raw.split("\r\n")
    lines[0] = "last_ack: ASR-068"
    lines[1] = "更新时间: 2026-11-24 19:05"
    lines[2] = "自指大小: %s" % size_field
    lines[3] = "当前任务: %s" % current_task
    lines[4] = block_line
    idx = lines.index("## 最近更新")
    j = idx + 1
    while j < len(lines) and not lines[j].startswith("- "):
        j += 1
    lines.insert(j, recent_new)
    arch_idx = None
    for i, l in enumerate(lines):
        if l.startswith("- ✅ **§100"):
            arch_idx = i
            break
    if arch_idx is None:
        raise SystemExit("FAIL: §100 archive link not found")
    lines[arch_idx] = ARCHIVE_LINK
    for i in range(arch_idx - 1, -1, -1):
        if lines[i].startswith("- ✅ **§95"):
            del lines[i]
            break
    k = None
    for i, l in enumerate(lines):
        if l.startswith("### §100 "):
            k = i
            break
    if k is None:
        raise SystemExit("FAIL: §100 section not found")
    tail = lines[k:]
    while tail and tail[-1].strip() == "":
        tail.pop()
    lines = lines[:k]
    lines.append("")
    lines.append(sec_body.replace("\r\n", "\n").rstrip("\n").replace("\n", "\r\n"))
    lines.append("")
    return "\r\n".join(lines)


def lines_field_ok(out, field):
    for l in out.split("\r\n"):
        if l.startswith("自指大小: "):
            return l == field
    return False


def main():
    if not os.path.exists(BAK):
        shutil.copy2(STATUS, BAK)
    size_field = "0 B / 0 行"
    prev = None
    for _ in range(30):
        out = build(size_field, CURRENT_TASK, BLOCK_LINE, RECENT_NEW, SEC101_BODY)
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

    out = build(size_field, CURRENT_TASK, BLOCK_LINE, RECENT_NEW, SEC101_BODY)
    b = out.encode("utf-8")
    n_crlf = b.count(b"\r\n")
    n_lines = n_crlf + 1
    assert b.count(b"\n") - n_crlf == 0, "bare LF present"
    assert b.endswith(b"\r\n"), "must end with CRLF"
    assert len(b) <= 40000, "too big: %d" % len(b)
    assert n_lines <= 160, "too many lines: %d" % n_lines
    field = "自指大小: %d B / %d 行" % (len(b), n_lines)
    assert lines_field_ok(out, field), "self size mismatch"
    open(STATUS, "wb").write(b)
    print("WROTE", len(b), "bytes", n_lines, "lines")
    print("field:", field)


if __name__ == "__main__":
    main()
