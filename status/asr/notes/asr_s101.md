# ASR §101 — 巡检（无新 ASR 纠偏）＋ **EXT v0.4.21 已提交 `b2a4978`** ＋ **e2e_v26_r2 三臂复算（旁路全开）** ＋ 🔴 **撤回 §100「`spk_reason_hist` 零缺口」结论**（2026-11-24 18:37–19:05）

## 0. 本轮性质

- 🔴 **纠偏通道（文件 ＋ 邮件双复核）**：`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime **2026-11-23 16:55:15**，
  与 §96 / §97 / §98 / §99 / §100 **逐字相同**；全文编号最大 = **ASR-068**；搜 `ASR-069` / `ASR-070` / `ASR-071` ⇒ **0 命中**
  ⇒ **`last_ack` 保持 `ASR-068`**。
- 🔴 **邮件通道新增 5 封，全部不是 ASR 编号 ⇒ 不进本模块 `last_ack`、无 ASR 纠偏动作项**：
  | 时间(Z) | 邮件 | 归属 |
  |---|---|---|
  | 05:26:34 | **APP-132**（机器锁：写锁非原子创建 ⇒ 臂间没持住） | App |
  | 05:56:40 | **APP-133**（v2.6 的 EXT 升到 v0.4.21 `b2a4978`） | App |
  | 07:13:42 | QQ邮箱团队「WorkBuddy 已获得访问权限」通知 | 非纠偏 |
  | 07:46:40 | **NPU 性能测试与精度报告（中文版）**（自发自收，含 ASR 对外数字） | 非纠偏 |
  | 10:11:12 | **H-028**（Hy-MT2 → Hy-MT3-1.8B） | MT |
  spam **0** 封、trash **1** 封（MiniMVP rc9 性能报告，非纠偏）。
- 🔴 **本轮不是纯巡检 ⇒ 有实质状态变化 ＋ 一条撤回 ⇒ 写 §101 章节 ＋ 发 STATUS 邮件**。

## 1. 🟢 状态变化 1：EXT v0.4.21 **已提交**（§100 的「未提交」已过时）

- `live_dub_ext` HEAD = **`b2a4978e2f671836c2e464db528e02d138884df9`**（commit 时间 **2026-11-24 13:54:52**），提交信息直书
  「EXT v0.4.21: split segments where the speaker gender flips … clone label-source / gender-gate counters, bypass reason histogram and gender-split count in stats_full; optional separated-vocals dump (EXT_BG_DUMP_VOCALS)」。
- 提交范围 **5 文件 / +102 −2**：`ext/bridge.py` (+34)、`ext/clone_voice.py` (+55)、`ext/version.py` (+2/−1)、`extension/manifest.json` (+2/−1)、`tests/test_ext0420_clone_gender.py` (+11)。
- 工作区**干净**（`git status --short` 空）。⇒ §100 记录的「v0.4.21 未提交、HEAD 仍 `4740b06`」**已过时**，按纪律**在 §101 撤回该句**（不改旧章节正文）。
- ⇒ §100 遗留的 reviewer 事项 **①（提交 v0.4.21）已闭**（reviewer 已自行提交）。

## 2. 🟢 状态变化 2：新三臂 `e2e_v26_r2`（**旁路全开**）⇒ §100 遗留 reviewer 事项 **②（开旁路臂）已闭**

- 产出方 = **App 模块**的 `confucius4-openvino/results/app/_app133_chain_v26.py`（`OUT_ROOT = shared/bgkeep/e2e_v26_r2`，L74）；本模块**只读复算**。
- 产物：`shared/bgkeep/e2e_v26_r2/` 共 **28 个文件**；素材 `confucius4-openvino/test_audio/clip_10min_0_600.wav`（600 s）、`delay=20`；
  三臂 `bridge.log` 首行均为「实时配音桥接 **v0.4.21**（2026-11-24）」⇒ **EXT = v0.4.21 `b2a4978`**（§100 的 e2e_v26 是 v0.4.20 `4740b06`）。

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

文件级证据：`bgkeep_off/bgkeep_e2e.json` **27 752 B** / 17:56:26（md5 `77bcc17e9895…`）、`bridge.log` **29 899 B** / 17:56:31；
`bgkeep_on/bgkeep_e2e.json` **27 427 B** / 18:07:49（md5 `5b06be8943ab…`）、`bridge.log` **28 699 B** / 18:07:53；
`bgkeep_clone/bgkeep_e2e.json` **31 911 B** / 18:19:10（md5 `bc62ee4f6ba6…`）、`bridge.log` **54 849 B** / 18:19:17。

- 🟢 **三臂 `spk_bypass.enabled` 全 true** ⇒ **§100 遗留的「开旁路臂的 `spk_reason_hist` 分布」现在有了**（§100 手上只有旁路关着的 v0421 臂）。
- 🟢 `bg_clone_from_vocals` 只在 clone 臂 = **167**（on 臂 0）⇒ clone 臂确实走「分离人声」；两开臂 `bg_late_blocks` = 0、`n_dropped` = 0、`spk_queue_drop` = 0。
- 🔴 **配音仍严重迟到**（max 115.42 / 139.22 / **182.62** s）⇒ 属 App/TTS 排队时延口径（APP-130 已指出 NPU `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS）⇒ **本模块只记录不归因**。
- 🟡 **段数不可与 §100 的 e2e_v26 直接对比**（87/73/95 → 94/89/111）：v0.4.21 改了切段逻辑（性别切分）且本批由 App 链路跑 ⇒ **不是受控 A/B**。

## 3. 🔴🔴 本轮新发现：**撤回 §100.1「`spk_reason_hist` 零缺口 / 100% 覆盖」结论**（§97/§98 的原始诉求**仍未闭**）

### 3.1 事实：r2 三臂的 `spk_reason_hist` 合计 **不等于** `asr_segments`

| 臂 | `spk_reason_hist` 合计 | `asr_segments` | `margin.n_segments` | `spk_bypass.n_final_req` | `n_label` / `n_no_label` |
|---|---|---|---|---|---|
| bgkeep_off | **119** | 94 | 94 | 121 | 118 / 3 |
| bgkeep_on | **118** | 89 | 89 | 121 | 116 / 2 |
| bgkeep_clone | **159** | 111 | 113 | 168 | 139 / 27 |

⇒ §100 写的「合计 = `asr_segments` ⇒ 100% 覆盖、零缺口」**在 r2 上不成立**。

### 3.2 机理（读 HEAD `b2a4978` 源码）：分母既不是 ASR 段数、也不是旁路请求数

- `ext/bridge.py` L2145–2153 `_spk_reason_hist()` 统计的是 **`self._spk_rows`（段级说话人表）**的行数。
- 该表有**两个写入点**：
  1. `ext/bridge.py` L2533–2543 `_on_spk_label()` ⇒ **只有旁路产出标签时才写**，并带 `spk_reason`；
  2. `ext/bridge.py` L2915 `_finalize_segment()` ⇒ **每个 ASR 段收口都写**，**不带** `spk_reason`。
- 于是 L2151 的取值规则 `k = spk_reason or ("label" if spk else "none")` 会把**收口路径的行**按「有 spk ⇒ label / 无 spk ⇒ none」并入直方图
  ⇒ **直方图的 'label' 桶混了两种来源**（旁路标签 ＋ 收口时已解析到的 spk），**分母随两条路径的到达情况浮动** ⇒ 与 `asr_segments`（只统计**有文本**的段，L2864）没有结构性相等关系。

### 3.3 🔴 更关键：**旁路「失败原因」在结构上进不了这个直方图**（这正是 §97/§98 要的东西）

- `spk_reason` 全仓**只有一个写入点**：`ext/bridge.py` L2538（`_on_spk_label` 内）。
- `_on_spk_label` 只作为 `on_label` 回调（`ext/bridge.py` L3377）被调用，调用方是 `ext/speaker_bypass.py` 的 `_emit_label()`；
  而 `_emit_label()` **只在 `if spk:` 分支触发**（`ext/speaker_bypass.py` L420–422）。
- **失败分支只做 `self.n_no_label += 1`（L431），不写任何行** ⇒ 段级表里**没有**这一段 ⇒ 直方图里**没有**它的 reason。
- 而 `ext/spk_engine.py` `on_final()` 的 **7 个否定 reason**（`models_not_ready` / `audio_not_buffered` / `too_short` / `seg_pending` / `not_clean_speech` / `overlap` / `embed_shape_out_of_range`，L454/459/462/466/467/479/482/485/491）**全部只出现在失败路径上** ⇒ **结构上不可达**。
- 🟢 **实测佐证**：`shared/bgkeep/` 下**全部 7 个**带 `spk_reason_hist` 的臂（`e2e_v26/{clip_cs2,clip_s2,clip_tuffy}`、`e2e_v26_r2/{off,on,clone}`、`gender_ab2/v0421`）
  取值域**只有 `{label, none}`**，**0 个**臂出现任何否定 reason。
- 🔴 **量化缺口（r2 clone 臂）**：`spk_bypass.n_no_label` = **27**，但直方图 `'none'` 只有 **3** ⇒ **24 段「为什么没标签」被直方图丢掉**；
  同时 `'label'` = **156** > 旁路 `n_label` = **139**（多 **17**）⇒ 印证 §3.2 的「收口路径的行也被算进 label 桶」。

### 3.4 为什么 §100 那次能对上（89 = 89）？——**是巧合，不是结构保证**

§100 复算的 `gender_ab2/v0421` 臂 **`spk_bypass.enabled = false`** ⇒ **没有一行来自 `_on_spk_label`** ⇒ 直方图**全部**由 `_finalize_segment` 的行构成
⇒ 在那一个臂上恰好等于 `asr_segments`（89）。§101 的 r2 **三臂旁路全开** ⇒ 两种来源混在一起 ⇒ 对不上。
⇒ **§100.1 的「零缺口 ⇒『旁路零标签不可归因』不再是死结」结论撤回**；**§97/§98 的原始诉求（旁路零标签为什么 ⇒ 要能归因）仍然开口**。

### 3.5 给 reviewer 的最小修法建议（**本模块不代改**）

要真正闭合「旁路零标签可归因」，需要**把失败路径也写进段级表**，例如在 `ext/speaker_bypass.py` 的失败分支（L429–431）
也回调一次 `on_label`（带 `spk=None` + `reason`），或让 `spk_bypass.stats()` 直接导出**否定 reason 的计数**（旁路侧本来就有 `res["reason"]`）。
只做现有 `_spk_reason_hist()` 的聚合口径调整**解决不了**（数据压根没进表）。

## 4. 🟡 r2 clone 臂的 `clone_reasons` 只有 **12 键**（v0421 臂 18 键）⇒ APP-131 验收第 2 项三字段在 10 分钟臂上的取值

- r2 clone 臂 12 键全量：`label`=61、`provisional`=159、`guard_keep`=66、`guard_short`=45、`timeout`=6、`guard_no_emb`=2、`self_ref_unvoiced`=2、`self_ref`=1、`fallback`=2、`tts_nearest`=1、`tts_nearest_voice`=**1**、`gender_keep`=2（**事件数**合计 **348**）。
- 相对 v0421 臂（18 键）**缺 6 键**：`gender_selfref`、`gender_switch`、`guard_match`、`guard_new`、`guard_pending`、`spk_split`。
- 🔴 **APP-131 验收第 2 项要的三个字段在 10 分钟臂上**：`tts_nearest_voice` = **1**（有值）；
  `gender_switch` = **键不存在**（不是值为 0）；`gender_selfref` = **键不存在** ⇒ **10 分钟臂上性别守门一次都没触发**。
- 🟡 与 §100 的 v0421 臂（7 分钟 `bili_420.wav`：`tts_nearest_voice`=9、`gender_switch`=3、`gender_selfref`=1）**媒体不同 ⇒ 不可直接对比**。
- 🟡 `clone_reasons` 是**事件计数**（一次标签尝试可多次自增，`ext/clone_voice.py` L276–867），而 `spk_reason_hist` 是**行数** ⇒ **两个口径不同、不能相加**。
- 🟡 `bgkeep_clone/bridge.log` 里那行「标签来源统计」（L345，18:17:08）是**跑中快照**（`provisional`=144/`guard_keep`=61/`guard_short`=39），
  **json 里的终值更大**（159/66/45）⇒ **以 `bgkeep_e2e.json` 为准**（§100 起即遵此口径）。

## 5. 🟡 仍未闭的旧开口项（与 §100 一致，无变化）

- 🔴 **修前（v0.4.18 / `5121d99`）对照臂仍缺**：`shared/bgkeep/` 下**无** `v0418*` 目录（只有 `v0419_stage` / `v0420_stage` / `v0421_stage`）⇒ §96 ① 仍未闭。
- 🔴 **分离人声 dump 仍 0 产出**：`EXT_BG_DUMP_VOCALS`（`ext/bridge.py` L1933）已实现且已提交，但 `shared/bgkeep/vocals/` **仍不存在**、
  全盘搜 `*vocal*` **0 命中** ⇒ 「原声 vs 分离人声」WER 对比仍**做不了**（等 App/reviewer 出一份 10 分钟分离人声 16 kHz wav）。
- 🔴 **v0.4.21 已提交 ⇒ 「待 reviewer 提交 v0.4.21」已闭**（见 §1）。

## 6. 🔴 新增待 reviewer 拍板项：**对外 NPU 报告里的 ASR 数字口径**（与本模块实测不是同一计分器）

- 用户自发到 `alex.g.chen@intel.com` 的《NPU 性能测试与精度报告（中文版）》（07:46:40Z）对外写：
  **Qwen3-ASR-0.6B INT8 有状态、延迟 p50 172 ms、RTF 0.067、英文 WER 0 / 中文 CER 0**（MiniMVP v1.1.1、OV 2026.4.1）。
- 🔴 **与本模块 §83 / ASR-060～061 的实测不是同一口径**：本模块 NPU **流式** RTF = **0.3094 / 0.2912 / 0.3165**（EN/ZH/SPE）、
  NPU **离线** RTF = **0.0496 / 0.0448 / 0.0665**；SPE 全局 WER = **9.74%**（流式）/ **6.30%**（离线）。
  ⇒ 报告里的 **0.067** 落在**离线**量级、而「WER 0 / CER 0」显然不是 SPE 10 分钟全局 WER ⇒ **属另一计分器 / 另一素材**。
- 🟡 **本模块不自行改对外口径**（§100 已列「RTF≈0.05 对外口径」待决）⇒ **请 reviewer 说明 0.067 的口径**（流式还是离线、素材集、WER 统计范围），
  以免与交付文档里的数字互相打架。
- 🟡 报告称完整表在本地 `results/npu_benchmark/NPU_Performance_Test_Report_CN.html/.md` ⇒ **本机未找到该路径**（4 个候选根目录均 0 命中）⇒
  若 reviewer 要本模块复核该报告，需提供文件位置。

## 7. 纪律

本轮**全部只读复算既有产物**（未跑推理 / 计时 / WER / 分离器）⇒ **不需 MACHINE_LOCK**；
观察期间 `shared/MACHINE_LOCK` **不存在**（复核前后各查一次，均无）⇒ 本模块**始终未取锁**、未干扰 App/reviewer 作业。
未改 4 个 ASR 交付文件；未动 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件内容；未打包；未提交 EXT。
产物：`status/asr/notes/asr_s101.md`（本文件）＋ `status/asr/STATUS_ASR.md` §101 ＋ `status/archive/STATUS_ASR_sec101_upto_20261124.md`（§100 全文逐字）＋ `_asr101_write_status.py` ＋ `_asr101_email_body_sent.txt`。
