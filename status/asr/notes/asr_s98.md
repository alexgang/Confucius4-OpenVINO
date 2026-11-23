# ASR §98 — 巡检 ＋ reviewer 对 §97「clone_s2 零标签」的裁定的独立复核（2026-11-23 22:05–22:35）

## 0. 本轮性质

- 🔴 **纠偏通道（文件 ＋ 邮件双复核）**：`CORRECTIONS_ASR.md` **109 822 B** / md5
  `3d25680748cf7934fe172f3bb372ec1a` / mtime **2026-11-23 16:55:15** ⇒ 与 §96、§97 **逐字相同**；
  全文搜 `ASR-069` / `ASR-070` / `ASR-071` ⇒ **0 命中**，最大编号 **ASR-068**
  ⇒ **`last_ack` 保持 `ASR-068`**。
- 🔴 **邮件通道本轮多出 2 封与 §97 的关键裁定**（收件箱 after 2026-11-23T08:55:00Z 共 **9** 封）：
  | 时间(UTC) | 主题 | 与本模块的关系 |
  |---|---|---|
  | 08:55:11Z | APP-126 | App 编号，不进本模块 `last_ack` |
  | 08:55:15Z | **ASR-068** | 已读已落地（§94 核实） |
  | 08:55:39Z | APP-127 | App 编号 |
  | 11:40:19Z | APP-128 | §97 已核实并闭环 |
  | 11:40:34Z | APP-128 补充（附件改名） | §97 已记录 |
  | 12:00:14Z | NAS T-003 关闭 | 别的模块 |
  | 12:06:18Z | NAS T-004 看门狗 | 别的模块 |
  | **12:52:07Z** | **APP-128 补充（e2e7 三臂表）** | 🔴 **正文含对 §97「clone_s2 零标签」的裁定** |
  | 12:52:08Z | NAS T-004 复核 PASS | 别的模块 |
- 🔴 **§97 漏看了这封**：§97 的收件箱清点发生在裁定到达前数秒（§97 的回信发出于 **12:55:17Z**，
  已晚于 12:52:07Z 的裁定）⇒ **§97 未回应 reviewer 对 clone_s2 的裁定** ⇒ 本轮补上。
- spam **0** 封、trash **1** 封（MiniMVP rc9 性能报告，**非纠偏**）。

## 1. reviewer 的裁定原文（APP-128 补充，12:52:07Z）

> 「clone_s2 n_speakers=0 判为正常（前 15 s 是配乐，台词每句约 1 s，到不了单人 3 s 干净语音的
> 登记门槛），不用处理。」

同封邮件另要求 App 线程单独补发 **e2e7 三臂表**（纯文本表格）⇒ 该表**已由 App 线程于 13:53:36Z
单独发出**（主题「[C4][A][STATUS][APP] APP-128 e2e7 三臂表」）⇒ **不是本模块的欠账**，本模块不重复发。

## 2. 🔴 本轮独立复核的核心发现：裁定的**结论方向可成立**，但**所引机制与代码路径不符**

### 2.1 裁定引用的机制 —— 与 `ext/speaker.py` 不符

裁定说「到不了单人 **3 s 干净语音的登记门槛**」⇒ 该门槛对应 `SpeakerTracker.clean_sec_required = 3.0`
（`ext/bridge.py` L1370–1374 传入 `C.SPK_CLEAN_SEC_REQUIRED`；`stats_full.speaker.clean_sec_required` = **3.0**）。
但读 `ext/speaker.py` 实测：

- `update_from_diarization()` L119–122：**只要有一条带 `spk_id` 的标签到达，就
  `self._profiles[spk_id] = prof` —— 无条件建 profile**；
- L125–134：`prof.clean_sec += (t_end - t_start)` 累加；`ready_for_clone(3.0)` **只**决定
  `prof.voice_id` 取**克隆音色**还是**预设 A**（`voice_for()` L171–181），**不影响 profile 是否存在**；
- L185：`"n_speakers": len(self._profiles)` ⇒ **profile 计数**。

⇒ 🔴 **推论：`n_speakers = 0` 只可能由「一条标签都没到」造成**（旁路 `n_label`=0 ⇒ 必然 0 个 profile）；
**3 s 登记门槛无法解释 `n_speakers = 0`** —— 若标签到了，哪怕 `clean_sec` < 3 s，
`n_speakers` 也会 ≥ 1，且 bridge.log 会打出「标签=Sx」。
⇒ 对照实测正好印证：clone_s1 `n_label`=**3** ⇒ `n_speakers`=**2**；clone_cs2 `n_label`=**17** ⇒
`n_speakers`=**1**（`n_speakers` 与 `n_label` 强相关，与 3 s 门槛无关）。

### 2.2 裁定的**结论方向**与代码一致（素材/阈值侧）

- `ext/spk_engine.py` `on_final()` L436–493 的前置门只有这些：
  | 门 | 判据 | clone_s2 是否命中 |
  |---|---|---|
  | `models_not_ready` | L453–455 | ❌ 排除（`seg_ready`=true、`enc_ready`=true） |
  | `audio_not_buffered` | L458–460 | ❌ 排除（见 2.3） |
  | `too_short` | L456/L462（`dur` < `MIN_DUR_S`=2.0 s，L69） | ⚠️ 只能命中前 2 段 |
  | `not_clean_speech` | L478–480（`clean_ratio` < `MIN_CLEAN_RATIO`=0.6，L63/65） | 🟡 **最可能** |
  | `overlap` | L481–483（`overlap_ratio` > `OVERLAP_RATIO_MAX`=0.02，L67） | 🟡 可能 |
  | `embed_shape_out_of_range` | L490–492 | ❌ 排除（见 2.3） |
- clone_s2 段长（`bridge.log` 原始行，ASR 侧段 id）：
  `seg_44875241_0` 0.000–**3.500**（ASR='—'）／`seg_44875241_56000` 3.500–**8.000**（ASR='—'）／
  `seg_44875241_128000` 8.000–**16.000**（'皇上，这不可能！'）／
  `seg_44875241_256000` 16.000–**24.000**（'这绝对不可能，皇上，大胆真魂还不跪下，臣妾无错，为何要跪下？'）／
  `seg_44875241_384000` 24.000–**30.743**（'血相融者即为亲，你还有什么可辩驳？'）
  ⇒ 段长 **3.5 / 4.5 / 8.0 / 8.0 / 6.743 s** ⇒ **5 段全部 ≥ 2.0 s** ⇒ `too_short` 只能命中前 2 段。
- 🟡 **推断（非结论）**：后 3 段的台词分别约 8 / 28 / 13 个字，落在 **8.0 / 8.0 / 6.7 s** 的窗里
  ⇒ **段内干净语音占比很可能 < 0.6** ⇒ `not_clean_speech` 最可能 ⇒ **「不用处理」的方向与代码一致**。
- 🟢 **独立佐证「前 15 s 是配乐」**：clone_s2 的分离器**全程正常** ——
  `bg_status_last` = {'state':'ok','device':'GPU.0','rtf':0.216}、
  `stats_bg.sep_rtf_p50`=**0.216** / `sep_rtf_p90`=**0.232**、
  `bg_clone_from_vocals`=**4**、`bg_clone_fallback_orig`=**0**、`fallback_to_orig_s`=**0.0**
  ⇒ 分离器在 GPU.0 正常工作、**旁路喂的是分离人声**（`_spk_use_vocals()`：state=='ok' ⇒ 喂人声）
  ⇒ 若前 15 s 是纯配乐，其人声轨近乎为空 ⇒ `clean_ratio`≈0 ⇒ `not_clean_speech`。
  ⚠️ 这是**从分离器状态反推**，**不是对分离人声的直接测量**（`shared/bgkeep/vocals/` 本轮实测**仍不存在** ⇒ 无分离人声 wav 可核）。

### 2.3 🔴 归因缺口**依然存在**（§97 提出的 `reason` 需求**未被满足**）

- clone_s2 `engine` 原始字段：`embed_count`=**0**、`embed_sec`=**0.0**、`enc_ready`=**true**、
  `enc_error`=**None**、`seg_ready`=**true**、`seg_error`=**None**、`seg_compile_count`=**1**、
  `seg_infer_count`=**4**、`seg_infer_sec`=**0.251** ⇒ **嵌入一次都没跑过** ⇒ 标签在 `on_final`
  的**前置门**就被拒（`embed_count`=0 ⇒ 不可能是 `embed_shape_out_of_range` 之后的分支）。
- `spk_bypass` 原始字段：`n_final_req`=**5**、`n_no_label`=**5**、`n_label`=**0**、`n_pending`=**0**
  ⇒ 5 段**全部**走「明确无标签」分支（`ext/speaker_bypass.py` L427–429），
  **没有一段**走「音频还没进缓冲」的 pending 分支（L423–426）⇒ 排除 `audio_not_buffered`。
- 🔴 **要区分 `too_short` / `not_clean_speech` / `overlap`，唯一字段是 `reason`**；
  而 `reason` **只**进段级表（`ext/bridge.py` L2504 `spk_reason` → `_spk_rows`），
  `bgkeep_e2e.json` **只导出 `stats_full`**、bridge.log **不打 reason**
  ⇒ **从现有产物仍无法判定 clone_s2 属于哪一类** ⇒ **§97 的「把 `reason` 分布进 `stats_full`」这一项
  仍然是必要的，且本轮裁定**没有替代**它**。

## 3. §96 三条待办的最终状态（本轮无变化）

- **① 补跑「开了旁路」的实时 e2e ⇒ 部分闭环**：e2e9 三臂已带 `--spk-bypass` 且已有标签证据
  （clone_s1 `n_label`=3／`n_speakers`=2；clone_cs2 `n_label`=17／`n_speakers`=1）；
  🔴 **仍缺「修前（v0.4.18 / `5121d99`）」对照臂** ⇒ 「修前为零标签 ⇒ 修后有标签」的对账**尚不完整**。
  ⚠️ reviewer 的 12:52:07Z 补充**未涉及此项** ⇒ 仍开口。
- **② 修 seg IR 变体解析顺序 ⇒ ✅ 闭环**（§97 已核）。
- **③ 修 note 措辞 ＋ 补真实路径回归用例 ⇒ ✅ 闭环**（§97 已核，14/14 PASS）。

## 4. 其余待办现状（本轮只读确认，无变化）

- 🔴 **分离人声素材仍缺** —— `shared/bgkeep/vocals/` 本轮实测**仍不存在**
  ⇒ 「原声 vs 分离人声」WER 对比**继续等 reviewer 提供**（工具已齐备；
  🔴 两侧须同一 ASR 臂 `pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。
- 🟡 **丢块计数上报 ASR 侧**仍未闭环（沿用 §95）：本轮实测三臂 `spk_queue_drop` 全 **0**，
  仅证明本次无丢块，**不等于机制已闭环**。
- 🟡 NPU 档前缀截断处置、README 口径、「md5 逐字节相同」口径、整段离线转写是否成交付路径、
  「RTF≈0.05」对外口径、encoder 2400 mel 帧上限与 30 s 上下文重导出、新说话人首次登记用哪段音频、
  旧 `v1.1.zip` 仍在磁盘不自证（发客户前必须确认发的是 `v1.1.1.zip`）—— **全部沿用，未变**。

## 5. 本轮纪律

- 🔴 **未跑 ASR 推理 / NPU·GPU 计时 / WER / Demucs 分离器、未取 MACHINE_LOCK**（实测本机无锁）、
  **未改 4 个 ASR 交付文件、未改 `live_caption/`、未改 EXT 源码（只读）、未改纠偏文件内容、未打包**。
- 唯一「执行」＝ **只读复算已有 e2e9 产物 ＋ 读 EXT 源码 ＋ 对 `clips/s2.wav` 做无模型的 RMS 统计**。
- 产物：`status/asr/STATUS_ASR.md` §98 ＋ 本 note ＋ `status/archive/STATUS_ASR_sec97_upto_20261123.md`。
