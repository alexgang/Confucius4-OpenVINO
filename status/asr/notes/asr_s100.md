# ASR §100 — 巡检（无新 ASR 纠偏）＋ **ASR-099 归因缺口已闭（reviewer 落地 v0.4.21 导出）** ＋ e2e_v26 三臂独立复算（2026-11-24 13:23–13:50）

## 0. 本轮性质

- 🔴 **纠偏通道（文件 ＋ 邮件双复核）**：`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime **2026-11-23 16:55:15**，
  与 §96 / §97 / §98 / §99 **逐字相同**；全文编号最大 = **ASR-068**；搜 `ASR-069` / `ASR-070` / `ASR-071` ⇒ **0 命中**
  ⇒ **`last_ack` 保持 `ASR-068`**。
- 🔴 **邮件通道无新 reviewer ASR 邮件**：收件箱 after **2026-11-24T02:47:13Z** ⇒ **0 封**；
  最新一封仍是 **APP-131**（02:47:12Z，已在 §99 处理）；主题含 `ASR-` 的邮件最大编号 = **ASR-068**（2026-11-23 08:55:15Z）。
  spam **0** 封；trash **1** 封（rc9 性能报告，非纠偏）。
- 🔴 **本轮不是纯巡检 ⇒ 有实质状态变化 ⇒ 写 §100 章节 ＋ 发 STATUS 邮件**。

## 1. 🔴 核心结论：§97/§98/§99 的「reason 归因缺口」已闭

### 1.1 §99 提出的两个开口项，reviewer 已在 v0.4.21 落地

§99（11:38 邮件）向 reviewer 建议把「旁路 `reason` 分布」＋「克隆 `_reasons` 计数」**合并**进 `stats_full`。
**reviewer 已实现**（证据 = `shared/bgkeep/v0421_stage/ext/bridge.py`，**290 855 B** / mtime **2026-11-24 11:48:43**，
**晚于 §99 邮件 11:38:55Z** ⇒ 确系对本模块建议的响应）：

| 位置 | 新增内容 |
|---|---|
| `ext/bridge.py` L2139–2142（`bg_stats()`） | `"clone_reasons"`（读 `self._clone._reasons`）、`"spk_reason_hist"`、`"n_gender_splits"` |
| `ext/bridge.py` L2145–2153（新增 `_spk_reason_hist()`） | 从 `self._spk_rows` 聚合 `spk_reason` ⇒ 计数直方图 |
| `ext/bridge.py` L1933–1938（`_on_bg_vocals`） | `EXT_BG_DUMP_VOCALS` 环境变量 ⇒ 落地分离人声 16 kHz s16 raw（**供离线 WER**） |

- 🔴 **代码注释直接写「v0.4.21 (ASR-099)」** ⇒ reviewer 明确把本模块 §99 编号写进了实现注释 ⇒ 归因请求已被正式接收。
- 🟡 **git 状态**：观察期间 reviewer 曾在工作区放 v0.4.21 草稿（5 文件 `M`，+102/−2），
  **后撤回** ⇒ 本轮复核时 `live_dub_ext` HEAD 仍 = **`4740b06`**（v0.4.20）、工作区**干净**（`git status --porcelain` 空）。
  ⇒ **v0.4.21 尚未提交**；本模块**只读**、**不评论、不代改、不提交**（EXT 代码归 reviewer）。

### 1.2 🟢 实测验证：导出字段**真的进了 `stats_full`**

证据 = reviewer 自己跑的 A/B（`shared/bgkeep/run_gender_ab2.ps1`，v0.4.20 vs v0.4.21 两臂，7 分钟 B 站片 `bili_420.wav`，`voice=clone`）：

| 臂 | `stats_full` 顶层 key 数 | `clone_reasons` | `spk_reason_hist` | `n_gender_splits` |
|---|---|---|---|---|
| `gender_ab2/v0420` | **42** | **不存在** | **不存在** | **不存在** |
| `gender_ab2/v0421` | **45** | ✅ **存在（18 个键）** | ✅ **存在** | ✅ **3** |

- 产物：`shared/bgkeep/gender_ab2/v0420/bgkeep_e2e.json`（**25 852 B** / 13:37:06）、
  `shared/bgkeep/gender_ab2/v0421/bgkeep_e2e.json`（**26 543 B** / 13:45:39）、`v0421/bridge.log`（**45 011 B** / 13:45:36）。
- 🔴 **APP-131 验收第 2 项要的三个字段，现在都能取到数**（不再「字段不存在」）：

| 字段 | v0421 实测值 | v0420 |
|---|---|---|
| `tts_nearest_voice` | **9** | 字段不存在 |
| `gender_switch` | **3** | 字段不存在 |
| `gender_selfref` | **1** | 字段不存在 |

- 🟢 **完整 `clone_reasons`（18 键，v0421）**：`label`=82、`provisional`=76、`guard_keep`=70、`guard_short`=11、
  `self_ref`=9、`tts_nearest_voice`=9、`timeout`=5、`guard_pending`=4、`spk_split`=4、`fallback`=3、`gender_switch`=3、
  `guard_no_emb`=2、`self_ref_unvoiced`=2、`tts_nearest`=2、`gender_keep`=1、`gender_selfref`=1、`guard_new`=1、`guard_match`=1。
  ⇒ 🔴 **v0.4.20 §99 的「只写日志、不进 `stats_full`」缺口已实锤闭合**（18 类原因全部可机器读）。

### 1.3 🟢 旁路 `reason` 分布现在**可对账**，且**无缺口**

- `spk_reason_hist` = `{'none': 10, 'label': 79}` ⇒ 合计 **89**。
- v0421 臂 `asr_segments` = `mt_segments` = `tts_segments` = **89** ⇒ **合计 89 = 段数 89 ⇒ 100% 覆盖、零缺口**。
- 🟢 **取值域已核对**（`ext/spk_engine.py` L459/462/467/479/482）：`audio_not_buffered`（pending）/`too_short`/`not_clean_speech`/`overlap`，
  加上有标签时的 `label`、无标签时的 `none` ⇒ **与实现一致，不是臆造字段**。
- 🟢 **结论：§97 的「旁路零标签永远不可归因」不再是死结** —— 现在可分三类（pending / 明确无标签 / 有标签）。
- 🟡 **本轮 v0421 臂旁路是关的**（`spk_bypass.enabled=false`）⇒ `spk_reason_hist` 反映的是**克隆模式**的段级标签来源，
  **不是**开旁路的取值分布；开旁路臂的分布仍需 reviewer 另跑一臂（**不代做，等 reviewer**）。

## 2. 🟡 e2e_v26 三臂独立复算（§99 未记录这批产物）

产物：`shared/bgkeep/e2e_v26/{bgkeep_off,bgkeep_on,bgkeep_clone}/bgkeep_e2e.json`
（**26 399 B** / 12:44:55、**24 483 B** / 12:56:13、**28 663 B** / 13:07:36），素材 = `clip_10min_0_600.wav`（600 s），`delay=20`，EXT = **v0.4.20 `4740b06`**（三臂 bridge.log 首行版本一致）。

| 指标 | bgkeep_off | bgkeep_on | bgkeep_clone |
|---|---|---|---|
| `bg_state` | `off` | `ok` | `ok` |
| `bg_blocks` / `bg_covered_s` | 0 / 0.0 | 600 / 600.0 | 600 / 600.0 |
| `bg_late_blocks` | 0 | **0** | **0** |
| `bg_margin_min_s` / `median` | — / — | 8.96 / 12.03 | 8.97 / 12.14 |
| `sep_rtf_p50` / `p90` | — / — | 0.255 / 0.278 | 0.241 / 0.281 |
| `sep_device` / `sep_compile_s` | — / — | GPU.0 / 3.67 | GPU.0 / 3.91 |
| `bg_clone_from_vocals` | 0 | **0** | **163** |
| `bg_onset_no_vocals` / `onset_shifted` | 0 / 0 | 72 / 1 | 93 / 2 |
| `asr`/`mt`/`tts` 段数 | 87/87/87 | 73/73/73 | 95/95/95 |
| `dubs` | 88 | 73 | **97** |
| `dub_late_vs_play_s` max / p90 / n_late | 149.92 / 129.61 / 85 | 230.82 / 192.23 / 71 | **235.0 / 212.37 / 93** |
| `spk_bypass.enabled` | **true** | **true** | **true** |
| `n_label` / `n_no_label` / `n_pending` / `n_final_req` | 118 / 3 / 0 / 121 | 116 / 2 / 0 / 121 | 139 / 24 / **1** / 164 |
| `spk_queue_drop` | 0 | 0 | 0 |
| `speaker.n_speakers` | 1 | 1 | 1 |
| `n_dropped` / `n_frames` | 0 / 5951 | 0 / 5951 | 0 / 5951 |

- 🟢 **三臂旁路全开且全有效**（`enabled=true` 三臂）⇒ §96 的 A 项「e2e9 三臂首次真开旁路」在 **10 分钟全集**上**再次复现**。
- 🟢 **`n_dropped`=0 三臂**、`spk_queue_drop`=0 三臂、`bg_late_blocks`=0 两开臂 ⇒ 无丢块、无背景迟到。
- 🟡 **`bg_clone_from_vocals` 只在 clone 臂 = 163**（on 臂 = 0）⇒ 克隆臂确实走「分离人声」路径，on 臂走原声。
- 🔴 **本模块关注的一个口径**：`speaker.n_speakers` 三臂都 = **1**，而 `spk_bypass.n_label` = 118/116/139 ⇒
  **再次印证 §99 的澄清**：克隆/旁路模式下 `speaker.n_speakers` **不能**当「旁路有没有标签」的判据（旁路看 `spk_bypass.n_label`）。
- 🟡 **`dub_late_vs_play_s.max` 三臂都很大**（149.9 / 230.8 / 235.0 s）⇒ 🔴 **配音严重迟到**；
  但 🔴 **本模块不代做判定**：这属 App/TTS 链路的排队时延（`bg_onset_no_vocals` 72/93 也高），
  且 APP-130 已指出 NPU 上 `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS ⇒ **属 App 线程口径**，本模块**只记录不归因**。

## 3. 纪律

- 未跑推理 / 计时 / WER / 分离器（本轮**全部只读复算既有产物**）⇒ 不需 MACHINE_LOCK；
  观察期间锁由 reviewer 持有（`reviewer gender ab 2026-11-24T13:28:20`）⇒ 本模块**始终未取锁**、未干扰 reviewer 作业。
- 未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未打包；未提交 EXT。
- 只提交本模块文件（`status/asr/` ＋ 本模块归档）。

## 4. 状态

🟢 **ASR 线程待命**。`last_ack` = **ASR-068**（无新 ASR 纠偏）。

**§97/§98/§99 的归因缺口已闭**（reviewer 落地 v0.4.21 导出 ＋ 本模块独立复算验证）。

**剩余开口项**（均不属本模块可代做）：
- 🔴 **待 reviewer**：**v0.4.21 提交**（当前仍 HEAD `4740b06`，工作区干净 ⇒ 改动尚未入库）；
  **开旁路臂**的 `spk_reason_hist` 分布（v0421 臂旁路是关的）；
  **修前（v0.4.18 / `5121d99`）对照臂**（§96 ① 仍未闭 ⇒ 「修前为零标签 ⇒ 修后有标签」对账不完整）。
- 🔴 **待 App/reviewer 提供**：10 分钟片段**分离人声 16 kHz wav** ⇒ `EXT_BG_DUMP_VOCALS` 已实现（v0.4.21），
  但**本轮未产出任何 dump 文件**（`shared/bgkeep/vocals/` 仍不存在；全盘搜索 `EXT_BG_DUMP_VOCALS` 产物 = 0 命中）
  ⇒ 拿到 dump 后本模块做「原声 vs 分离人声」WER 对比（🔴 两侧同一 ASR 臂：`pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。
- 🟡 **待 App 线程决定**：NPU 档前缀截断处置（建议 ① `MAX_SEG_SEC` 20.0 → 19.0 s）；🔴 **§2 新增**：配音迟到（max 235 s）由 App/TTS 排队时延口径处置。
- 🟡 **待用户/reviewer 决定**：README 是否加「NPU 档 20 s 长段会触发前缀截断」；「md5 逐字节相同」是否改标注；整段离线转写是否加成交付路径；「RTF≈0.05」对外口径；encoder 静态上限 2400 mel 帧 ⇒ 30 s 上下文得重导出；新说话人首次登记用哪段音频。
- ⚠️ **待 App 侧落地**：README `--asr-device NPU` 示例能否给客户（🔴 发客户前必须确认发的是 `v1.1.1.zip`）。
- 🟡 **丢块计数上报 ASR 侧**（§95 单开，§96 沿用）：EXT 只在自家 `stats()` 计 `spk_queue_drop`；另请明确「旁路 64 项」与 `ext/bg_separator.py` L242 `maxsize=4000` 两层丢块语义。
