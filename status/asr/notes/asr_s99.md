# ASR §99 — 巡检（无新 ASR 纠偏）＋ EXT v0.4.20 只读复核 ＋ 新发现「克隆计数未进 stats_full」（2026-11-24 11:20–11:45）

## 0. 本轮性质

- 🔴 **纠偏通道（文件 ＋ 邮件双复核）**：`CORRECTIONS_ASR.md` md5 `3d25680748cf7934fe172f3bb372ec1a`（**109 822 B**），
  与 §96 / §97 / §98 逐字相同；全文编号最大 = **ASR-068**；搜 `ASR-069` / `ASR-070` / `ASR-071` ⇒ **0 命中**
  ⇒ **`last_ack` 保持 `ASR-068`**。
- 🔴 **邮件通道有 3 封新 mail，但都不是 ASR 编号**（收件箱 after 2026-11-23T12:52:08Z）：
  | 时间(UTC) | 主题 | 与本模块的关系 |
  |---|---|---|
  | 2026-11-24 00:58:16Z | APP-129（bgkeep 交接：EXT `3573b2d` + Demucs 模型进完整版 v2.6、默认分离设备 GPU.0、同版带 APP-123 c13） | App 编号 ⇒ 不进本模块 `last_ack`；**无 ASR 模块动作项** |
  | 2026-11-24 00:58:20Z | APP-130（NPU 配音杂音根因：`cp_prefill`/`cp_decode` 在部分机型 NPU 上输出 NaN ⇒ talker 到不了 EOS；修法 = 搬 NPU 后自检、不合格留 CPU） | App/TTS 编号 ⇒ 不进本模块 `last_ack`；**无 ASR 模块动作项** |
  | 2026-11-24 02:47:12Z | APP-131（APP-129 补充：v2.6 的 EXT 改用 v0.4.20 `4740b06`，克隆音色跟随男女切换；验收第 2 项要**报 `stats_full` 里克隆相关计数 `tts_nearest_voice` / `gender_switch` / `gender_selfref`**） | App 编号 ⇒ 不进本模块 `last_ack`；🔴 **但它的验收项直接暴露本模块 §97/§98 开口项的同型缺口 ⇒ 见 §2.2** |
- spam **0** 封、trash **1** 封（MiniMVP rc9 性能报告，非纠偏）；sent 侧最新是 App/TTS 模块的 STATUS，非本模块纠偏。
- 🔴 **状态有实质变化 ⇒ 不是「纯巡检状态完全一致」** ⇒ 本轮**写 §99 章节 + 发 STATUS 邮件**（T-MAIL-003 第 ① 条：做完一轮且状态有变化 ⇒ 必须发）。

## 1. 机器与并发状况（本轮未取锁的理由）

- `shared/MACHINE_LOCK` **存在**，内容 = `app 10516 2026-11-24 10:57:53 app bgkeep v2.6 chain`
  ⇒ **App 模块正在跑 bgkeep v2.6 整链**（`shared/bgkeep/e2e_v26/bgkeep_on/bridge.log` mtime 持续增长到 11:19）。
- ⇒ 本模块**本轮不跑任何计时/测速/推理/分离器**，**不取 MACHINE_LOCK**、**不碰 App 的在跑作业**；全部为只读复算。

## 2. 只读复核：EXT 已推进到 v0.4.20

### 2.1 仓库状态（`C:/Users/Trekker-PTL/live_dub_ext`，只读）

- HEAD = **`4740b06`**（EXT v0.4.20，提交时间 2026-11-24 10:34:48）
  ⇒ 比 §96/§98 记录的 `3573b2d`（v0.4.19）**前进了 1 个版本**。
- ⚠️ **工作区有未提交的 v0.4.21 草稿**（`git status` 5 个文件 `M`）：
  `ext/bridge.py`（+10）、`ext/clone_voice.py`（+55，新增 `split_by_gender()`：按音高性别翻转切段）、
  `ext/version.py`（0.4.20 → 0.4.21）、`extension/manifest.json`（同）、`tests/test_ext0420_clone_gender.py`（+11）。
  ⇒ **非本模块产物 ⇒ 本模块不读改、不提交、不评论**（EXT 代码由 reviewer 写）。
- v0.4.20 提交内容（`git show 4740b06 --stat`）：`ext/bridge.py` +10、`ext/clone_voice.py` +152、
  `ext/config.py` +2、`ext/version.py`、`extension/manifest.json`、`tests/test_ext0420_clone_gender.py` +105、
  `tools/bgkeep_e2e.py` +7。

### 2.2 🔴 本轮新发现：**§97/§98 的「`reason` 进 `stats_full`」开口项仍然开口，而且同型缺口还多一处**

- 🔴 **§97/§98 提的开口项（`spk_engine.on_final()` 的 `reason` 分布进 `stats_full`）**：
  v0.4.20（`4740b06`）的 `ext/bridge.py` **L2514 仍是 `"spk_reason": info.get("reason")`**
  ⇒ **只进段级表 `_spk_rows`**，**没有任何路径把它汇总进 `stats_full`**。
  ⇒ **归因缺口仍然开口**（§97/§98 的结论本轮**继续成立**，未被 v0.4.20 替代）。
- 🔴 **新发现（同型，级别更高）**：`ext/clone_voice.py` 的标签来源/性别守门计数器
  （`_reasons["label"]` / `["provisional"]` / `["tts_nearest"]` / `["tts_nearest_voice"]` /
  `["gender_switch"]` / `["gender_selfref"]` / `["guard_match"]` / `["guard_new"]` / `["self_ref"]` …）
  **只写日志**（`_fallback()` 里每满 20 次打一行「[spk] 标签来源统计：%s」）
  ⇒ **没有任何 `stats()` / 导出方法把它们送进 `stats_full`**。
  ⇒ 🔴 **直接后果：APP-131 第 2 项要求「报 `stats_full` 里克隆相关计数（`tts_nearest_voice` /
  `gender_switch` / `gender_selfref`）」在当前 EXT 代码下**取不到数**（不是「数为 0」，是**字段根本不存在**）。
  ⇒ 🟡 这与 §97 提的 `reason` 是**同一个设计缺口**（诊断计数只进日志、不进机器可读导出）
  ⇒ **建议 reviewer 把两者一起改**：旁路 `reason` 分布 **＋** 克隆 `_reasons` 计数，**一起进 `stats_full`**。
- 🟢 **佐证**（只读复算 `shared/bgkeep/gender_ab/v0420/bgkeep_e2e.json` 的 `stats_full` 顶层 key，**38 个**）：
  `type, n_frames, n_dropped, buffered_sec, bg_keep, bg_state, bg_blocks_sent, bg_up_frames, bg_up_gaps,
  sep_device, sep_rtf_p50, sep_rtf_p90, sep_compile_s, bg_lead_sec, bg_clone_from_vocals,
  bg_clone_fallback_orig, bg_onset_shifted, bg_onset_shift_sum_sec, bg_onset_no_vocals, capture_mode,
  client_source, source_rate, client_target_lang, client_voice, applied_target_lang, asr_segments,
  mt_segments, tts_segments, speaker, spk_bypass, margin, adaptive_speed, lag_decomposition,
  feed_arrival_delay, pipeline, thread_limits, proc_cpu_pct, proc_mem_mb, igpu_pct, npu_pct,
  dub_dropped, seg_skipped`
  ⇒ **无 `spk_reason`、无任何 clone/tts_nearest/gender 字段**。

### 2.3 🟢 性别守门**确实生效**（唯一可得的证据在日志里，不在 `stats_full`）

只读复算 `shared/bgkeep/gender_ab/v0420/bridge.log`：
- 「性别守门」共 **4** 行（v0.4.19 对照臂 `gender_ab/v0419/bridge.log` = **0** 行 ⇒ 该功能是 v0.4.20 新增）：
  | 行号 | 内容 |
  |---|---|
  | 47 | 段 512000 性别守门：句子=f、音色 S1_1.wav=m、**没有同性别已登记音色 ⇒ 用本句自己克隆** |
  | 90 | 段 1545440 性别守门：句子=f、音色 S1_1.wav=m ⇒ 改用同性别最像的 `guard_512000.wav`（0.19） |
  | 284 | 段 6112480 性别守门：句子=f、音色 S1_1.wav=m ⇒ 改用同性别最像的 `S5_3.wav`（0.21） |
  | 296 | 段 6297120 性别守门：句子=f、音色 S1_1.wav=m ⇒ 改用同性别最像的 `S5_3.wav`（0.24） |
- 🔴 但「[spk] 标签来源统计」行 = **0** 行（`clone_voice.py` L311 的打印条件是 `n % 20 == 0`，本臂 `_reasons` 总数未凑到 20 的整数倍
  ⇒ **连日志口径本身也不可靠**，不能拿它当计数）⇒ **计数必须走 `stats_full` 导出**（§2.2）。

### 2.4 克隆模式 e2e 两臂只读复算（`gender_ab/v0419` vs `gender_ab/v0420`，同一素材同一口径）

| 字段 | v0.4.19 | v0.4.20 |
|---|---|---|
| `client_voice` | clone | clone |
| `asr_segments` / `tts_segments` | 87 / 87 | 87 / 87 |
| `dub_dropped` | 0 | 0 |
| `bg_state` / `sep_device` | ok / GPU.0 | ok / GPU.0 |
| `sep_rtf_p50` | 0.267 | 0.258 |
| `bg_clone_from_vocals` | 78 | 83 |
| `speaker.n_speakers` | 0 | 0 |
| `speaker.n_pending_unassigned` | 87 | 87 |
| `speaker.n_final_without_spk` | 174 | 174 |
| `spk_bypass.enabled` | false | false |

- 🟡 **`n_speakers`=0 在克隆模式属预期**，与 §98 结论一致：**克隆模式的说话人标签来自 `clone_voice` 的
  `SpeakerVoiceTable`（`clone_voice.py` L201 `self.tab`），不是 `bridge.tracker`** ⇒ `stats_full.speaker`
  这组计数在克隆模式下**不反映标签产出**（它反映 `bridge.tracker`，克隆模式下 tracker 不收标签）。
  ⇒ 🟢 **`speaker.n_speakers` 不能当「旁路有没有标签」的判据**（§98 的判据链成立：旁路看 `spk_bypass.n_label`）。
- 🟡 这两臂**都没开旁路**（`spk_bypass.enabled`=false）⇒ **对 §96 的「修前为零标签 ⇒ 修后有标签」对账没有新增证据**。

## 3. 其它开口项状态（本轮只读确认，均无变化）

- 🔴 **仍缺「修前（v0.4.18 / `ee45ce5` / `5121d99`）」对照臂**：`shared/bgkeep/` 下只有
  `e2e, e2e2, e2e5, e2e7, e2e8, e2e9, e2e_v26, gender_ab, gender_ab2`，**无 v0.4.18 臂产物**
  ⇒ 「修前为零标签 ⇒ 修后有标签」对账**仍不完整**。
- 🔴 **分离人声素材仍缺**：`shared/bgkeep/vocals/` **仍不存在**（`find` 全盘无 `*vocal*` 目录；
  `ov_demucs.py` 只落 `ov_*_bg.wav`，**不落人声 wav**）⇒ 「原声 vs 分离人声」WER 对比**继续等 reviewer 提供**。
  🟢 本轮新增素材：`shared/bgkeep/clips/bili_420.wav`、`clips/bili_600s.wav`（B 站素材，**不是**分离人声）。
- 🟡 **e2e9 三臂独立复算复现**（`shared/bgkeep/e2e9/*/bgkeep_e2e.json`）：
  clone_s1 `n_speakers`=**2**、clone_cs2 `n_speakers`=**1**、clone_s2 `n_speakers`=**0**
  （三臂 `spk_bypass.enabled`=true）⇒ 与 §98 完全一致。
- 🟡 **待 App 线程 1 项**：NPU 档前缀截断处置（建议 `MAX_SEG_SEC` 20.0 → 19.0 s）—— 不变。
- 🟡 **待用户/reviewer 5 项 ＋ 待 App 侧落地 1 项** —— 不变。

## 4. 本轮纪律（逐条自查）

- 未跑推理、未跑计时、未跑 WER、未跑分离器（**MACHINE_LOCK 被 App 模块持有**，本轮不取锁）。
- 未改 4 个 ASR 交付文件、未动 `live_caption/`、**未改 EXT 源码（只读）**、未改 `CORRECTIONS_ASR.md` 内容、未打包、未提交客户包。
- 本轮唯一「写」= `status/asr/notes/asr_s99.md` ＋ `status/asr/STATUS_ASR.md`（头部 + 最近更新 + §99 章节）＋
  `status/archive/STATUS_ASR_sec98_upto_20261124.md`（§98 全文逐字归档）。
- 租约：`acquire asr` ⇒ TOKEN=`826bafe3`（exit 0，无 BUSY/TAKEOVER）；beat 11:20:33 / 11:23:48 / 11:28:35 / 11:30:57 全 OK；末 release。
