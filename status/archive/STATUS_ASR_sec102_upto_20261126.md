# STATUS_ASR §102 归档（§101 全文逐字）

> 归档时间 2026-11-26 14:55；来源 `status/asr/STATUS_ASR.md.bak_asr102`（§102 写入前的基线，39 997 B / 156 行）。
> 格式与 `status/archive/STATUS_ASR_sec100_upto_20261124.md` / `sec101_upto_20261124.md` 一致（全文逐字，不改一字）。

### §101 巡检（无新 ASR 纠偏）＋ EXT v0.4.21 已提交 `b2a4978` ＋ e2e_v26_r2 三臂复算（旁路全开）＋ 撤回 §100「`spk_reason_hist` 零缺口」结论（2026-11-24 18:37–19:05）

> 🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime 2026-11-23 16:55:15，与 §96–§100 逐字相同；最大编号 **ASR-068**；`ASR-069`/`070`/`071` **0 命中**）。邮件新增 **5 封全部非 ASR 编号**（APP-132、APP-133、QQ邮箱通知、NPU 性能报告、H-028）⇒ 不进 `last_ack`；spam **0**、trash **1**（非纠偏）。🔴 **本轮不是纯巡检**（EXT 状态变化 ＋ 一条撤回）⇒ 写 §101 ＋ 发 STATUS 邮件。明细 ⇒ `status/asr/notes/asr_s101.md`。

#### §101.1 🟢 EXT v0.4.21 **已提交**（§100 的「未提交」已过时 ⇒ 撤回该句）

HEAD = **`b2a4978e2f671836c2e464db528e02d138884df9`**（**2026-11-24 13:54:52**），**5 文件 / +102 −2**：`ext/bridge.py` +34、`ext/clone_voice.py` +55、`ext/version.py` +2/−1、`extension/manifest.json` +2/−1、`tests/test_ext0420_clone_gender.py` +11），工作区**干净**。⇒ §100 的「v0.4.21 未提交、HEAD 仍 `4740b06`」**已过时** ⇒ 按纪律**在 §101 撤回该句**（不改旧章节正文）⇒ §100 遗留 reviewer 事项 **①（提交 v0.4.21）已闭**。

#### §101.2 🟢 新三臂 `e2e_v26_r2`（旁路全开）⇒ §100 遗留 reviewer 事项 **②（开旁路臂）已闭**

产出方 = **App 模块** `results/app/_app133_chain_v26.py`（`OUT_ROOT = shared/bgkeep/e2e_v26_r2`，L74）；本模块**只读复算**；产物 **28 文件**；素材 `test_audio/clip_10min_0_600.wav`（600 s）、`delay=20`；三臂 `bridge.log` 首行均为「实时配音桥接 **v0.4.21**」⇒ EXT = `b2a4978`（§100 的 e2e_v26 是 v0.4.20 `4740b06`）。三臂 `bgkeep_e2e.json`：**27 752 B** / 17:56:26、**27 427 B** / 18:07:49、**31 911 B** / 18:19:10（off/on/clone）。

| 指标 | bgkeep_off | bgkeep_on | bgkeep_clone |
|---|---|---|---|
| `client_voice` / `bg_state` / `bg_blocks` / `bg_covered_s` | A / `off` / 0 / 0.0 | A / `ok` / 600 / 600.0 | **clone** / `ok` / 600 / 600.0 |
| `bg_late_blocks` / `bg_clone_from_vocals` / `bg_onset_no_vocals` / `bg_onset_shifted` | 0 / 0 / 0 / 0 | 0 / 0 / 86 / 2 | 0 / **167** / 108 / 3 |
| `asr`/`mt`/`tts` 段数；`dubs` / `dub_dropped`；`n_dropped` / `spk_queue_drop` / `n_frames` | 94/94/94；95 / 0；0 / 0 / 5951 | 89/89/89；90 / 0；0 / 0 / 5951 | 111/111/111；114 / 0；0 / 0 / 5951 |
| `spk_bypass.enabled` / `n_label` / `n_no_label` / `n_pending` / `n_final_req` | true / 118 / 3 / 0 / 121 | true / 116 / 2 / 0 / 121 | true / **139** / **27** / 0 / **168** |
| `spk_reason_hist`（合计）；`clone_reasons`（键数 / 事件数）；`n_gender_splits`；`dub_late_vs_play_s` max / p90 / n_late | `{none:1, label:118}`（119）；{} / 0；0；115.42 / 105.56 / 90 | `{none:4, label:114}`（118）；{} / 0；0；139.22 / 122.58 / 87 | `{none:3, label:156}`（159）；**12** / 348；**4**；**182.62** / 161.25 / 110 |

- 🟢 **三臂 `spk_bypass.enabled` 全 true** ⇒ §100 手上只有旁路**关**着的 v0421 臂 ⇒ 遗留事项 **② 已闭**；`bg_clone_from_vocals` 只在 clone 臂 = **167** ⇒ clone 臂确实走「分离人声」；两开臂 `bg_late_blocks`=0、`n_dropped`=0、`spk_queue_drop`=0 ⇒ 无丢块、无背景迟到。🔴 **配音仍严重迟到**（max 115.42 / 139.22 / **182.62** s）⇒ 属 App/TTS 排队时延口径（APP-130：NPU `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS）⇒ **本模块只记录不归因**。🟡 **段数不可与 §100 的 e2e_v26 对比**（87/73/95 → 94/89/111）：v0.4.21 改了切段逻辑且本批由 App 链路跑 ⇒ **不是受控 A/B**。

#### §101.3 🔴🔴 撤回 §100.1「`spk_reason_hist` 零缺口 / 100% 覆盖」⇒ §97/§98 原始诉求**仍开口**

- 🔴 **事实**：r2 三臂 `spk_reason_hist` 合计 = **119 / 118 / 159**，而 `asr_segments` = **94 / 89 / 111** ⇒ 对不上 ⇒ §100 的「合计 = `asr_segments` ⇒ 100% 覆盖」**在 r2 上不成立**。
- **机理（读 HEAD `b2a4978`）**：`ext/bridge.py` L2145–2153 `_spk_reason_hist()` 统计 **`self._spk_rows`（段级说话人表）行数**；该表**两个写入点** —— ① L2533 `_on_spk_label()`（只有旁路**产出标签**时才写，带 `spk_reason`）；② L2915 `_finalize_segment()`（每段收口都写，**不带** `spk_reason`）。L2151 的 `spk_reason or ("label" if spk else "none")` 把**收口路径的行也并进直方图** ⇒ **'label' 桶混了两种来源**、分母随两条路径到达情况浮动 ⇒ 与 `asr_segments`（L2864，**只统计有文本的段**）**无结构性相等关系**。
- 🔴 **更关键：旁路「失败原因」结构上进不了该直方图**（§97/§98 要的）：`spk_reason` 全仓**只有一个写入点**（L2538）；`_on_spk_label` 只作为 `on_label` 回调（L3377）被调用，调用方 `ext/speaker_bypass.py` 的 `_emit_label()` **只在 `if spk:` 分支触发**（L420–422）；**失败分支只做 `n_no_label += 1`（L431）、不写任何行** ⇒ 段级表里没有这一段 ⇒ 直方图里没有它的 reason。而 `ext/spk_engine.py` `on_final()` 的 **7 个否定 reason**（`models_not_ready`/`audio_not_buffered`/`too_short`/`seg_pending`/`not_clean_speech`/`overlap`/`embed_shape_out_of_range`）**全部只在失败路径** ⇒ **结构上不可达**。🟢 **实测**：`shared/bgkeep/` 下**全部 7 个**带该字段的臂取值域**只有 `{label, none}`**。
- 🔴 **量化缺口（r2 clone 臂）**：`n_no_label` = **27**，但直方图 `'none'` 只有 **3** ⇒ **24 段「为什么没标签」被丢掉**；`'label'` = **156** > 旁路 `n_label` = **139**（多 **17**）⇒ 再证「收口路径的行被并进 label 桶」。🟡 **§100 那次 89 = 89 是巧合**：那个 `gender_ab2/v0421` 臂 **`spk_bypass.enabled = false`** ⇒ 没有一行来自 `_on_spk_label` ⇒ 直方图全由收口路径构成 ⇒ 恰等于 `asr_segments`（89）；r2 **三臂旁路全开** ⇒ 两种来源混在一起 ⇒ 对不上。⇒ **§100.1 的「零缺口 ⇒『旁路零标签不可归因』不再是死结」结论撤回**；**§97/§98 原始诉求仍开口**。**给 reviewer 的最小修法**：让失败路径也写进段级表 —— `ext/speaker_bypass.py` 失败分支（L429–431）也回调一次 `on_label`（带 `spk=None` ＋ `reason`），或让 `spk_bypass.stats()` 直接导出**否定 reason 计数**（旁路侧本来就有 `res["reason"]`）。**只调 `_spk_reason_hist()` 聚合口径解决不了**（数据压根没进表）。

#### §101.4 🟡 r2 clone 臂 `clone_reasons` 只有 **12 键**（v0421 臂 18 键）＋ APP-131 三字段在 10 分钟臂上的取值

- 🔴 **APP-131 验收第 2 项要的三个字段在 10 分钟臂上**：`tts_nearest_voice` = **1**（有值）；`gender_switch` = **键不存在**（不是值为 0）；`gender_selfref` = **键不存在** ⇒ **10 分钟臂上性别守门一次都没触发**。🟡 与 §100 的 v0421 臂（7 分钟 `bili_420.wav`：`tts_nearest_voice`=9、`gender_switch`=3、`gender_selfref`=1）**媒体不同 ⇒ 不可直接对比**。
- 🟡 12 键全量与 v0421 臂 18 键的差集（**事件数**合计 **348**）见 notes；🟡 `clone_reasons` 是**事件计数**、`spk_reason_hist` 是**行数** ⇒ **两口径不同、不能相加**；🟡 `bridge.log` L345「标签来源统计」是**跑中快照** ⇒ **以 `bgkeep_e2e.json` 为准**。
#### §101.5 🔴 仍未闭的旧开口项 ＋ 🟡 新增待拍板项 ＋ 纪律

- 🔴 **修前（v0.4.18 / `5121d99`）对照臂仍缺**（`shared/bgkeep/` 下**无** `v0418*` 目录）⇒ §96 ① 未闭。🔴 **分离人声 dump 仍 0 产出**：`EXT_BG_DUMP_VOCALS`（L1933）已实现**且已提交**，但 `shared/bgkeep/vocals/` **仍不存在**、全盘搜 `*vocal*` **0 命中** ⇒ 「原声 vs 分离人声」WER 对比仍做不了（🔴 两侧须同一 ASR 臂：`pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自行调 MiniMax**）。
- 🟡 **新待 reviewer 拍板：对外《NPU 性能测试与精度报告》（07:46:40Z）的 ASR 数字口径** —— 报告写 **RTF 0.067、英文 WER 0 / 中文 CER 0**；🔴 **与本模块 §83 / ASR-060～061 实测不是同一计分器**（本模块 NPU 流式 RTF 0.3094/0.2912/0.3165、离线 0.0496/0.0448/0.0665；SPE 全局 WER 9.74%/6.30%）⇒ 0.067 落在**离线**量级、而「WER 0 / CER 0」显然不是 SPE 10 分钟全局 WER ⇒ **本模块不自行改对外口径**，请 reviewer 说明 0.067 的口径（详见头部「阻塞」栏）；🟡 完整表在 `results/npu_benchmark/`，**本机未找到该路径** ⇒ 若需复核请提供位置。
- **纪律**：本轮**全部只读复算既有产物**（未跑推理 / 计时 / WER / 分离器）⇒ **不需 MACHINE_LOCK**（复核前后各查 `shared/MACHINE_LOCK`，**均不存在**）⇒ 始终未取锁、未干扰 App/reviewer。未改 4 个 ASR 交付文件；未动 `live_caption/`；未改 EXT 源码（**只读**）；未改纠偏文件；未打包；未提交 EXT。产物：`status/asr/notes/asr_s101.md` ＋ `status/archive/STATUS_ASR_sec101_upto_20261124.md`（§100 全文逐字）＋ `_asr101_email_body_sent.txt`。
