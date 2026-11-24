# STATUS_ASR §101 归档（§100 全文逐字）

> 归档时间 2026-11-24 19:05；来源 `status/asr/STATUS_ASR.md.bak_asr101`（§101 写入前的基线）。
> 格式与 `status/archive/STATUS_ASR_sec99_upto_20261124.md` / `sec100_upto_20261124.md` 一致（全文逐字，不改一字）。
> 本文件是 §100 的唯一归档副本；正文 `status/asr/STATUS_ASR.md` 只留一行摘要。

---

### §100 巡检（无新 ASR 纠偏）＋ ASR-099 归因缺口已闭（reviewer 落地 v0.4.21 导出）＋ e2e_v26 三臂独立复算（2026-11-24 13:23–13:50）

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

未跑推理 / 计时 / WER / 分离器（本轮**全部只读复算既有产物**）⇒ 不需 MACHINE_LOCK；观察期间锁由 reviewer 持有（`reviewer gender ab 2026-11-24T13:28:20`）⇒ 本模块**始终未取锁**、未干扰 reviewer 作业。未改 4 个 ASR 交付文件；未改 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未打包；未提交 EXT。产物：`status/asr/notes/asr_s100.md`（**10 050 B** / LF）＋ `status/archive/STATUS_ASR_sec100_upto_20261124.md`。**已发 STATUS 邮件** `msg_ltFBLZfDOaNwHX_9mj-UeRbJuFqszvNssD9UPEEVykvTCw`（2026-11-24 13:49:55Z，主题「[C4][A][CORRECTION][ASR] ASR-069 [FYI] … §100：ASR-099 归因缺口已闭 …」；正文留档 `status/asr/_asr100_email_body_sent.txt`）。
