last_ack: ASR-068
更新时间: 2026-11-24 11:45
自指大小: 32263 B / 120 行
当前任务: 🟢 **巡检（无新 ASR 纠偏）＋ EXT v0.4.20 只读复核 ＋ 新发现「克隆计数未进 stats_full」（§99）**：纠偏通道**无新 ASR 条目**（`CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a`，与 §96/§97/§98 逐字相同；最大编号 **ASR-068**；搜 `ASR-069`/`ASR-070`/`ASR-071` **0 命中**）⇒ **`last_ack` 保持 `ASR-068`**。邮件（qq-mail，只读）：收件箱 after 2026-11-23T12:52:08Z 新增 **3** 封 —— **APP-129**（bgkeep 交接：EXT `3573b2d` + Demucs 进 v2.6、默认分离 GPU.0、同版带 APP-123 c13）、**APP-130**（NPU 上 `cp_prefill`/`cp_decode` 输出 NaN ⇒ talker 到不了 EOS；搬 NPU 后自检、不合格留 CPU）、**APP-131**（APP-129 补充：v2.6 的 EXT 改用 v0.4.20 `4740b06`，克隆音色跟随男女切换；验收第 2 项要报 `stats_full` 里克隆相关计数 `tts_nearest_voice`/`gender_switch`/`gender_selfref`）—— **三封都是 App 编号，不进本模块 `last_ack`**，且无 ASR 模块动作项；spam 0 封、trash 1 封（rc9 报告，非纠偏）。🔴 **本轮状态有实质变化 ⇒ 写 §99 章节 ＋ 发 STATUS 邮件**（不是纯巡检）。🟢 **EXT 已推进到 v0.4.20**：HEAD = **`4740b06`**（2026-11-24 10:34:48），比 §96/§98 的 `3573b2d`（v0.4.19）前进 1 版；工作区另有 **未提交的 v0.4.21 草稿**（`ext/bridge.py` +10、`ext/clone_voice.py` +55 新增 `split_by_gender()`、`ext/version.py`/`extension/manifest.json` 0.4.20→0.4.21、`tests/test_ext0420_clone_gender.py` +11）⇒ **非本模块产物 ⇒ 只读、不评论、不提交**。🔴 **§97/§98 提的开口项「`spk_engine.on_final()` 的 `reason` 进 `stats_full`」仍然开口**：v0.4.20 的 `ext/bridge.py` **L2514 仍是 `"spk_reason": info.get("reason")`** ⇒ 只进段级表 `_spk_rows`，**没有任何路径汇总进 `stats_full`**。🔴 **本轮新发现同型缺口（级别更高，直接影响 APP-131 验收）**：`ext/clone_voice.py` 的标签来源/性别守门计数器（`_reasons["label"]`/`["tts_nearest_voice"]`/`["gender_switch"]`/`["gender_selfref"]`/`["guard_match"]` 等）**只写日志**（`_fallback()` 每满 20 次打一行「[spk] 标签来源统计」）⇒ **没有任何 `stats()`/导出方法把它们送进 `stats_full`** ⇒ **APP-131 第 2 项要求的三个计数字段在当前 EXT 代码下取不到数（字段根本不存在，不是值为 0）**。🟢 **佐证**：只读复算 `shared/bgkeep/gender_ab/v0420/bgkeep_e2e.json` 的 `stats_full` 顶层 **38** 个 key，**无 `spk_reason`、无任何 clone/tts_nearest/gender 字段**。🟢 **性别守门确实生效（唯一证据在日志）**：`shared/bgkeep/gender_ab/v0420/bridge.log` 的「性别守门」**4** 行（v0.4.19 对照臂 `gender_ab/v0419/bridge.log` = **0** 行 ⇒ 该功能为 v0.4.20 新增）；但「[spk] 标签来源统计」= **0** 行（打印条件 `n % 20 == 0`，本臂未凑到 20 的整数倍 ⇒ **连日志口径本身也不可靠**）。🟡 **克隆模式 e2e 两臂只读复算**（v0.4.19 vs v0.4.20，同素材同口径）：`client_voice`=clone、`asr_segments`/`tts_segments`=**87/87**、`dub_dropped`=**0**、`bg_state`=ok、`sep_device`=GPU.0、`sep_rtf_p50`=**0.267**→**0.258**、`bg_clone_from_vocals`=**78**→**83**、`speaker.n_speakers`=**0**（两臂）、`spk_bypass.enabled`=false（两臂）。🟡 **新澄清（对 §98 判据链的补充）**：克隆模式的说话人标签来自 `clone_voice` 的 `SpeakerVoiceTable`（`ext/clone_voice.py` L201 `self.tab`），**不是 `bridge.tracker`** ⇒ `stats_full.speaker` 这组计数在克隆模式下**不反映标签产出** ⇒ 🟢 **`speaker.n_speakers` 不能当「旁路有没有标签」的判据**（旁路仍看 `spk_bypass.n_label`）。🟡 **其它开口项本轮只读确认，无变化**：🔴 仍缺「修前 v0.4.18 对照臂」（`shared/bgkeep/` 下只有 `e2e/e2e2/e2e5/e2e7/e2e8/e2e9/e2e_v26/gender_ab/gender_ab2`，**无 v0.4.18 臂产物**）；🔴 `shared/bgkeep/vocals/` **仍不存在**（`ov_demucs.py` 只落 `ov_*_bg.wav`，**不落人声 wav**）⇒ 分离人声素材仍缺；🟢 e2e9 三臂独立复算复现（clone_s1 `n_speakers`=**2**、clone_cs2=**1**、clone_s2=**0**，三臂 `spk_bypass.enabled`=true）。🔴 **本轮纪律**：未跑推理/计时/WER/分离器（**`shared/MACHINE_LOCK` 被 App 模块持有**：`app 10516 2026-11-24 10:57:53 app bgkeep v2.6 chain` ⇒ 本轮**不取锁**、不碰 App 在跑作业）、未改 4 个 ASR 交付文件、未改 `live_caption/`、未改 EXT 源码（只读）、未改 `CORRECTIONS_ASR.md` 内容、未打包。**产物** `status/asr/notes/asr_s99.md` ＋ `status/asr/STATUS_ASR.md` §99 ＋ `status/archive/STATUS_ASR_sec98_upto_20261124.md`（§98 全文逐字归档）
阻塞 / 待用户决定: 🟢 **无阻塞**（`last_ack` = **ASR-068**，本轮无新 ASR 纠偏）。🟡 **§97/§98 的归因缺口仍未闭**：EXT v0.4.20（`4740b06`）的 `ext/bridge.py` L2514 `spk_reason` 仍只进段级表、**未进 `stats_full`** ⇒ 「旁路零标签」仍不可归因。🔴 **本轮新发现同型缺口**：克隆侧 `_reasons`（`tts_nearest_voice`/`gender_switch`/`gender_selfref` 等）**只进日志、不进 `stats_full`** ⇒ **APP-131 第 2 项要的三个计数字段当前取不到数（字段不存在）** ⇒ 🟢 **建议 reviewer 把两者合并改**：旁路 `reason` 分布 **＋** 克隆 `_reasons` 计数，**一起进 `stats_full`**。🟡 **§96 的 ① 仍只「部分闭环」**：仍缺「修前（v0.4.18 / `ee45ce5` / `5121d99`）对照臂」（`shared/bgkeep/` 下**无 v0.4.18 臂产物**）⇒ 「修前为零标签 ⇒ 修后有标签」对账**仍不完整** ⇒ 请 reviewer 补该对照臂。🟡 **待 reviewer 提供**：10 分钟片段的**分离人声 16 kHz wav**（🔴 `shared/bgkeep/vocals/` 本轮实测**仍不存在**；`ov_demucs.py` 只落 `ov_*_bg.wav`、**不落人声**）⇒ 拿到后本模块做「原声 vs 分离人声」WER 对比（🔴 两侧须同一 ASR 臂 `pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。🟡 **待 App 线程决定 1 项（沿用）**：NPU 档前缀截断处置 —— 建议 **① `MAX_SEG_SEC` 20.0 → 19.0 s**（实际 19.20 s ⇒ `allowed_prefix=52`，覆盖实测最长前缀 43，余量 9）；备选 ② 丢段尾前缀而非左截断；🔴 ③ 上调 pml **会改变 §86 全部 RTF 数字 ⇒ 必须重测**。🟡 **待用户/reviewer 决定 1 项（沿用）**：README 是否加「NPU 档在 20 s 长段会触发前缀截断（实测 3 次；两侧转写一致、未见丢字，但机制上会丢句首）」。🟡 **待用户决定 4 项（沿用）**：**①** 「md5 逐字节相同」口径改写为「NPU 档 ＋ OV 2026.4.1」（未获批）；**②** 整段离线转写是否加成交付路径；**③** 「RTF≈0.05」对外口径；**④** 🔴 encoder 静态上限 2400 mel 帧 = 24.0 s ⇒ 30 s 上下文**得重导出 encoder**（放宽段长 ⇒ pml=320 必须重算）。⚠️ **待 App 侧落地 1 项（沿用）**：**只剩 README 的 `--asr-device NPU` 示例能否给客户**（🔴 旧 `v1.1.zip` 仍在磁盘且不自证 ⇒ **发客户前必须确认发的是 `v1.1.1.zip`**）。🟡 **待 App 线程决定 1 项（沿用）**：新说话人首次登记用哪段音频（推荐**方案 B**）。⚠️ 沿用不变：ASR-028 换人点抽听（用户侧）；**ASR-042 第 3 步仍暂停**（ASR-047）⇒ 本模块不跑 TTS；**B 机实测已关闭**（ASR-059）；`results/asr162`/`asr163`/`asr121_item1_check`/`asr090_zipcheck` 按纪律**未入库**；**OV 2026.4.1 口径纪律**；**不主动打包**。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。 §80 全文归档见 `status/archive/STATUS_ASR_sec80_upto_20261115.md`。

## 最近更新
- 2026-11-24 11:45 **§99（巡检（无新 ASR 纠偏）＋ EXT v0.4.20 只读复核 ＋ 新发现「克隆计数未进 stats_full」）：纠偏通道无新 ASR 条目 ⇒ `last_ack` 保持 **ASR-068**；邮件通道新增 3 封（APP-129/130/131）**均为 App 编号**，不进本模块 `last_ack`、无 ASR 动作项。**EXT 已推进到 v0.4.20**：HEAD = **`4740b06`**（10:34:48），另有未提交的 v0.4.21 草稿（非本模块产物 ⇒ 只读）。🔴 **§97/§98 的开口项仍开口**：v0.4.20 `ext/bridge.py` L2514 `spk_reason` 仍只进段级表 ⇒ 未进 `stats_full`。🔴 **新发现同型缺口（影响 APP-131 验收）**：`ext/clone_voice.py` 的 `_reasons`（`tts_nearest_voice`/`gender_switch`/`gender_selfref` 等）**只写日志、不进 `stats_full`** ⇒ **APP-131 第 2 项要的三个字段当前取不到数（字段不存在，不是值为 0）** ⇒ 建议 reviewer 两者合并改。🟢 **佐证**：`gender_ab/v0420/bgkeep_e2e.json` 的 `stats_full` 顶层 **38** key，无 `spk_reason`、无 clone/gender 字段；`gender_ab/v0420/bridge.log`「性别守门」**4** 行（v0.4.19 对照臂 **0** 行 ⇒ v0.4.20 新增），但「[spk] 标签来源统计」**0** 行 ⇒ **日志口径本身也不可靠**。🟡 **克隆模式 e2e 两臂复算**（v0.4.19 vs v0.4.20）：87/87 段、`dub_dropped`=0、`sep_rtf_p50` 0.267→0.258、`bg_clone_from_vocals` 78→83、两臂 `speaker.n_speakers`=0、两臂 `spk_bypass.enabled`=false。🟡 **新澄清**：克隆模式的标签来自 `clone_voice` 的 `SpeakerVoiceTable`、**不是 `bridge.tracker`** ⇒ `speaker.n_speakers` **不能**当「旁路有没有标签」的判据（旁路仍看 `spk_bypass.n_label`）。🟡 **其它开口项无变化**：仍缺 v0.4.18 对照臂（`shared/bgkeep/` 无该臂产物）；`shared/bgkeep/vocals/` **仍不存在**（`ov_demucs.py` 只落 bg、不落人声）。🔴 **纪律**：未跑推理/计时/WER/分离器（`shared/MACHINE_LOCK` 被 App 模块持有 ⇒ 本轮不取锁）、未改 4 个 ASR 交付文件、未改 `live_caption/`、未改 EXT 源码（只读）、未改纠偏文件内容、未打包。**产物** `status/asr/notes/asr_s99.md` ＋ `status/asr/STATUS_ASR.md` §99 ＋ `status/archive/STATUS_ASR_sec98_upto_20261124.md`（§98 全文逐字归档）
- 2026-11-23 22:20 **§98（巡检 ＋ reviewer 对 §97「clone_s2 零标签」裁定的独立复核）**：纠偏通道无新 ASR 条目 ⇒ `last_ack` 保持 **ASR-068**；🟡 裁定「判为正常不用处理」方向站得住，🔴 **但其所引 3 s 登记门槛机制与 `ext/speaker.py` 不符**（`n_speakers`=0 的真因是「一条标签都没到」），🔴 `reason` 归因缺口仍开口。**全文已归档** ⇒ `status/archive/STATUS_ASR_sec98_upto_20261124.md` ＋ `status/asr/notes/asr_s98.md`
- 2026-11-15 12:05 **ASR-059 已读（`last_ack` → **ASR-059**）⇒ B 机实测待办**已关闭**，ASR 线程**待命**（纯文档，未跑实验/未取锁）**：用户 **11-15 决定 B 机（192.168.2.206）不跑 ASR 套件** ⇒ 头部「B 机实测由 reviewer / 主会话安排」改为「**11-15 用户决定不做（ASR-059）**」；**ASR-028 换人点抽听**仍为**用户侧待办**（本线程**无动作**）。🔴 **本轮只改文档**：未跑计时/WER、未取 MACHINE_LOCK、未改套件文件、未打包、未动 `live_caption/`；🔴 **为腾出 ASR-036（≤40 KB / ≤160 行）余量**，**§80 全文归档** ⇒ `status/archive/STATUS_ASR_sec80_upto_20261115.md`（**逐字保留**）＋ 正文留一行摘要（结论/数字仍在「关键数字」表 ＋「已撤回的旧结论」清单，**未丢结论**）。
- 2026-11-14 16:25 **ASR-058 已读（`last_ack` → **ASR-058**）⇒ ASR-057 关闭，ASR 线程**待命**（按 §3 **不写新章节**）**：reviewer 验收**全通过** —— `run_bk.cmd` **3764 B / CRLF 134 / 裸 LF 0 / 纯 ASCII / SHA256 `3c9b387a…b3c1`**（与 SHA256SUMS 一致），三种用法 **12/1/1 组 rc=0**，假桩失败 ⇒ 打印 **failed 12/1/1 且 rc=1**，两参 ⇒ 用法 **rc=2**；套件 **65 文件 == `n_files` 65**（去 `MANIFEST.json`+`SHA256SUMS.txt` ⇒ **2 348 478 744 B** == §82），无 `.bak*`/`results_A_local`/`.pyc`；`ref_A/` **8 文件 = 最终版 4 组**；`sources` **14 条**（4 条派生 `identical=null`+`derived=true`）；10min 口径 SPE **0–600 s** 一致；本轮**只读复核**：`_asr057_verify_status.py` **32 PASS**、`_asr057_verify_kit.py` **26 PASS**（哈希 0 处不符）⇒ **未打包、未动 `live_caption/`、未上 B 机**。
- 2026-11-13 10:10 **ASR-057 已落地（`last_ack` ASR-056 → **ASR-057**）⇒ 停下等 reviewer 复核**：**①** 🔴 `run_bk.cmd` **CRLF + 纯 ASCII** ＋ **`all`(12 组) / `selftest` 分支** ＋ **失败非 0 退出** ⇒ **假桩实测 12 / 1 / 1**（`bk_check_cmd.py` **8 PASS / 0 FAIL**）；**②** `.bak_asr056/` ＋ `results_A_local/` **移出套件** ＋ `SKIP_DIRS` 收窄 ⇒ **文件数 65 == MANIFEST `n_files` 65**；**③** `ref_A/` 补**最终版 18 s 三组** ＋ 删旧脚本 3 组 ⇒ **最终版 4 组**；**④** `sources` 拆 **copy/derived** ⇒ **14 条**（copy 10 / derived 4）＋ **tokenizer + `prompt.json`** 补齐；**⑤** 遗留项「待用户决定 `overlap_ratio_max`」**已删**（用户 11-07 已决定不修）；**附带修掉 2 处真缺陷**（`n_files` 语义 ＋ **MANIFEST.json 在 PS 5.1 解析失败**）；**验收 26 PASS / 0 FAIL**、`--check` **0 处不符** ⇒ 详见 **§82**。
- 2026-11-11 15:40 **ASR-056 已落地（`last_ack` ASR-055 → **ASR-056**）⇒ 停下等 reviewer 复核**：**①** §79 正文 **4 处标撤回** ＋ 已撤回清单补 **3 条**；**②** 旧计时 json（**10 个**）标 `unverified` ＋ `bk_run.py` 无锁改 `"no_lock"`；**③** 跨脚本比较块清理（4 个 bench json → `cross_script_ref_1025` ＋ `"comparable": false`，**并修掉标签颠倒**）＋ `asr138*` 加 `superseded_by`；**④** 关键数字表**补 300 s / 18 s 并排行**（带出处）＋ GPU 提速写 **RTF 区间 1.6–2.1×**；**⑤** 套件**最终版脚本持锁补跑 4 组** ⇒ **31/31 PASS**；**⑥** 套件小修 a–f 全做 ⇒ **61 文件 / 2348476971 B**；**未打包、未动 App 树 / 客户包 / `live_caption/`** ⇒ 详见 **§81**。

## 当前有效结论

> 🔴 **每个数字都注明来源产物**；被推翻的旧结论**不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| ASR 主模型 | R2T2（Qwen3-ASR-Flash-Realtime 路线），**默认 GPU.0** | ASR-018 用户决定 |
| 语音输出模型 | TTS 走 NPU（**不属本模块**） | ASR-018 |
| 线程 | **限线程是交付默认**：`OMP/MKL/OPENBLAS/NUMEXPR/VECLIB_MAXIMUM_THREADS=1`，**必须在 import numpy/torch 之前** | `asr073_thread_limit_delivery_default.json`（AST 级守卫 + 6/6 反证）；单一事实来源 `scripts/asr_thread_defaults.py` |
| 说话人编码器 | **wespeaker resnet34 OV IR，FP16 交付**（ASR-025 已关闭） | `asr067_fp16_vs_fp32_cluster.json` |
| 说话人聚类阈值 | `thr = 0.35` | ASR-013 ③ |
| 切段 | 规则1（段长 ≥MIN_SEG 且近 3 s 内有 ≥300 ms 静音）+ 规则2（静音超时 0.8 s 优先）+ 空段守卫 | C-108 / C-109（MIN_SEG = 6 s） |
| 强制断句 | **已停用**（pyannote 只做说话人识别，不产生断点） | ASR-021 用户决定 |
| TTS 音色策略 | 方案 A：**TTS 不等说话人标签** | ASR-024 用户决定 |

### 关键数字

| 指标 | 值 | 来源产物 / 字段 |
|---|---|---|
| CPU 占用（不限线程 / 限线程） | 7.8074 核 / **0.9981 核** | `asr049_cpu_attribution_rerun_{base,ovthreads}.json` → `avg_cores` |
| RTF（不限线程 / 限线程） | 0.6444 / **0.5302** | 同上 → `rtf`（🔴 单次测量 ⇒ 只能写「**不变或略好**」，不得写提速 18%） |
| 定稿段数（两臂） | 45 / 45 | 同上 → `n_segs` |
| 锁自检次数（两臂） | 88 / 73 | 同上 → `lock_probe.lock_probe_checks`（stolen 均 0） |
| 说话人聚类：FP16 vs FP32 不一致段数 | **0 / 196**（diff_rate 0.0） | `asr067_fp16_vs_fp32_cluster.json` → `arm_consistency.n_diff_segments` |
| 说话人：段级纯度 vs 伪真值 | 0.9147（n=183 段） | 同上 → `per_arm_vs_pseudo_truth.A_fp16.purity_and_fragmentation.segment_purity_vs_pseudo_truth` |
| 说话人：换人点 F1（±0.5 s / ±3.2 s） | 0.2025 / 0.6582 | 同上 → `per_arm_vs_pseudo_truth.A_fp16.switch_points_vs_pseudo_truth.tol_0p5s.f1` / `per_arm_vs_pseudo_truth.A_fp16.switch_points_vs_pseudo_truth.tol_3p2s.f1` |
| 说话人：识别人数 | 5（伪真值 6 人） | `asr055_spk_qa_reference_eval.json` → `asr_side_report.n_speakers` / `ref_meta.n_speakers` |
| 嵌入 RTF 增量（改法① 落地前 / 后） | 0.0494 / **0.0315** | `asr081_range_hi_coverage.json` → `arms.embed_dynamic.rtf_increment_vs_asr_only` / `arms.embed_range_2048.rtf_increment_vs_asr_only` |
| 嵌入墙钟（落地前 / 后） | 5.921 s / **0.551 s** | 同上 → `arms.embed_dynamic.embed_wall_s` / `arms.embed_range_2048.embed_wall_s` |
| 嵌入向量一致性（落地后 vs 动态） | 43 段逐段，cos 最小 1.0、rel 最大 0.0 | 同上 → `consistency_vs_dynamic.embed_range_2048.n` / `.cos_min` / `per_segment[].rel_max_abs_diff` |
| 生产段帧数上界 | 1998 帧（= MAX_SEG_SEC 20.0 s）；落地取 EMBED_RANGE_HI **2048** | 同上 → `offline_segment_length.prod_frame_upper_bound` / `.app_MAX_SEG_SEC` / `.landed_EMBED_RANGE_HI` |
| FP16 嵌入保真（余弦 / rel） | 0.999998775537715 / 0.001432037985732332（**不过** 1e-3 门槛） | `asr060_wespeaker_precision_attrib.json` → `experiments.ov_fp16_vs_torch_fp32.cos` / `.rel_max_abs_diff` |
| FP32 对照 rel | 1.1163879303042469e-06（**过**门槛）⇒ 归因 = FP16 格式固有精度，非 IR 缺陷 | 同上 → `experiments.ov_fp32_vs_torch_fp32.rel_max_abs_diff` |
| `SpeakerTracker` 接口自检 | 19/19 全过 | `asr054_speaker_tracker_selftest.json` → `n_pass`/`n_checks` |
| 交付集合闸门（3 文件） | 关键字 0、运行时链越界 0、隔离自洽 True、反证 4/4 | `asr079_delivery_set_gate.json` |
| NOTICE 关键字闸门 | 命中 0、反证 4/4 | `asr085_notice_keyword_gate.json` |
| 说话人旁路窗口 10 s vs 5 s：召回（10 s / 5 s） | 10/12 / **10/12** | `asr105_spk_window_5s_vs_10s.json` → `arms[].evaluation.analysis_raw.n_hit`（`n_ref_switches` = 12） |
| 说话人旁路窗口 10 s vs 5 s：误报（10 s / 5 s） | **0 / 0** | 同上 → `arms[].evaluation.analysis_raw.n_false_positive` |
| 标签到达延迟 P50（10 s / 5 s） | 10.0003 s / **5.0002 s** | 同上 → `arms[].evaluation.label_lag.all_pending.p50_s` |
| 标签到达延迟 P95（10 s / 5 s） | 10.0013 s / **5.0008 s** | 同上 → `arms[].evaluation.label_lag.all_pending.p95_s` |
| 每窗口耗时：旁路分段 P50（10 s / 5 s，GPU.0） | 0.04159 s / **0.021128 s** | `asr105_window_bench.json` → `seg_bench[].infer_p50_s` |
| 每窗口耗时：旁路分段 P50（10 s / 5 s，CPU 对照） | 0.054432 s / **0.027677 s** | 同上 |
| 旁路分段 RTF（10 s / 5 s，GPU.0） | 0.004159 / **0.004226** | `asr105_window_bench.json` → `summary[].rtf_seg`（窗口数翻倍 ⇒ RTF 略升）|
| 旁路+嵌入 RTF（10 s / 5 s，GPU.0） | 0.004807 / **0.005521** | 同上 → `summary[].rtf_total` |
| 300 s 总成本（10 s / 5 s，GPU.0） | 1.248 s / **1.268 s** | 同上 → `summary[].projected_300s_cost_s`（基本持平）|
| stateful vs mask2（**同脚本同口径**，10 分钟）RTF：GPU.0 / NPU | **0.2479 / 0.3998**（1.6×）与 **0.384 / 0.5696**（1.5×） | `asr138_10min_{stateful,stateless}_{GPU0,NPU}/summary.json` → `rtf`（🔴 **不再用 10-25 旧 runner 的 0.6827/1.0684** ⇒ §79④ 已撤回）|
| stateful vs mask2 每 token 解码 p50：GPU.0 / NPU | **14.5565 / 56.7728 ms**（3.9×）与 **18.7421 / 91.6198 ms**（4.9×） | 同上 → `probe.decode_ms_p50` |
| stateful vs mask2 出字延迟 p50：GPU.0 / NPU | **0.0928 / 0.0949 s**（持平）与 **0.1518 / 0.1296 s**（NPU 反而慢 17%） | 同上 → `first_tok_latency_p50` |
| mask2 18 s 端到端（GPU.0 / NPU） | **3.7929 s / rtf 0.2107** 与 **4.6038 s / rtf 0.2558** | `asr147_bench_mask2_{GPU0,NPU}.json` → `B3_e2e_18s.wall_s` / `.rtf`（**带 `lock_record`**、`timing_valid=true`）|
| mask2 300 s 流式（GPU.0 / NPU） | **rtf 0.5397 / 46 段 / 829 词** 与 **rtf 0.5259 / 46 段 / 831 词** | 同上 → `B4_stream_300s.rtf` / `.n_segs` / `.total_words` |
| stateful vs mask2 **同 runner 300 s / 18 s 并排**（GPU.0 / NPU） | **300 s RTF** GPU **0.2627 / 0.5397**（**0.49×**）、NPU **0.3496 / 0.5259**（**0.66×**）；**18 s wall** GPU **1.4541 / 3.7929 s**（**0.38×**）、NPU **1.706 / 4.6038 s**（**0.37×**）；**每 token p50** GPU **16.4051 / 81.0881 ms**（**0.2×**）、NPU **17.7664 / 89.6434 ms**（**0.2×**）；**300 s 出字 p50** GPU **0.0951 / 0.1317 s**、NPU **0.1451 / 0.1264 s**（**NPU stateful 慢 15%**）🔴 **GPU 提速只能写区间：RTF 口径约 1.6–2.1×**（10 分钟跑 **1.6×**、300 s 跑 **2.1×**）—— mask2 GPU 每 token p50 在 10 分钟跑是 **56.7728 ms**、300 s 跑是 **81.0881 ms**，**相差 43%**，两次各只跑 1 遍 ⇒ **不报单点、不要求补跑**；🔴 **NPU 首字归因（stateful vs mask2 同在 NPU）**：mask2 首 token 是**一次 512 静态前向**、B1 p50 **89.6434 ms**，stateful prefill p50 **94.7818 ms** ⇒ **量级相同** ⇒ 持平或略慢**预期内** | `asr135_bench_{GPU0,NPU}.json` → `B1_per_token.decode_ms_p50` / `B3_e2e_18s.wall_s` / `B4_stream_300s.rtf` / `B4_stream_300s.first_tok_latency_p50` ＋ `asr147_bench_mask2_{GPU0,NPU}.json`（**同字段**）＋ `asr138_10min_stateless_GPU0/summary.json` → `rtf` / `probe.decode_ms_p50` |
| NPU prefill p50（stateful） | **94.7818 ms**（GPU.0 60.2073 ms ⇒ 慢 **34.5745 ms**（差值，由两字段相减）） | `asr135_bench_{NPU,GPU0}.json` → `B2_prefill.prefill_ms_p50`（⇒ NPU 出字延迟变差的主因）|
| **按段配对 WER**（stateful NPU vs mask2 GPU0） | **Δ +0.2251 pp，CI [-0.2906, 0.776]，`significant_worse=false`** | `asr146_wer_seg_paired.json` → `comparisons[2].delta_pp` / `.ci95` / `.significant_worse`（`mode`=`segment_paired`，`n_blocks`=93，`scorer`=`reviewer_minimax_global`）|
| 按段配对 WER：stateful GPU0 vs mask2 GPU0 | **Δ -0.0563 pp，CI [-0.5775, 0.4638]，不显著** | 同上 → `comparisons[0]` |
| B 机套件 `b_kit_stateful` | **65 文件（磁盘实际）/ 63 进哈希 / 2348478744 B**（assets 356067863/11、models 1884374957/6、ref_A 15391/8、scripts 121679/12、wheels 107868519/23）⇒ **文件数 == MANIFEST `n_files`**；`--check` **0 处不符** | `b_kit_stateful/MANIFEST.json` → `n_files` / `n_hashed_files` / `total_bytes` / `dir_sizes`；`SHA256SUMS.txt` 同源；`bk_sha256.py --check` |
| B 机套件 A 机自测（`--mel torch`） | **46/46 段文本逐位同、词数 831=831、词级差 0、RTF 差 6.43% ⇒ 7/7 PASS** | `b_kit_stateful/results/bk_cmp_selftest_torchmel.json` → `txt_same` / `total_words_new` / `word_diff_count` / `rtf_rel_diff` / `verdict` |
| B 机套件 A 机自测（`--mel fft`，免 torch） | **43/46 段同、词数 831=831、词级差 6 词（0.72%）、RTF 差 8.22%** | `b_kit_stateful/results/bk_cmp_selftest_numpymel.json` |
| mel 数值差归因 | 填充/窗/帧化**逐位同**；谱差 **1.3487e-06**（相对 8.04e-08）⇒ 差异**双来源**：FFT 实现（**不可消除**）＋ dtype/log10（**可消除**）；`--mel torch` 与 transformers **逐位同（maxdiff 0.0）** | `b_kit_stateful/results/bk_mel_bench.json` → `cases[].pad_bitwise_same` / `.window_bitwise_same` / `.frames_bitwise_same` / `.spec_diff_numpy_vs_torch` / `.torch_mode_all_bitwise_same` |
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |

### 已撤回的旧结论（**不作为结论**，仅备查）

- 🔴 **§88④/⑤ 的「App 侧接入在 NPU 上逐字节复现参照」「对 GPU.0 零回归」已撤回** ⇒ **APP-121 §2 复核成立**：`_app120_asr_3mat.py` 用的是 **ASR 模块**的 `bk_run.run_stream` ＋ `asr065_backend.Asr065Runner`，**没经过 App 的 `ASR06BStatefulBackend`** ⇒ 只能证明「包里的模型文件与 ASR 模块用同一份」。🔴 **补充**：即便改用 App 代码，**交付版**（`dfb225e` 引入的「`allowed_prefix` 减 `reserve`」）在 NPU 档会把前缀**多砍 32–64 token**⇒ 口径本就与 ASR 参照不同 ⇒ **大概率仍不会逐字节相同**。🟡 **§88「GPU.0 与 ASR 模块 11-19 基准逐字节相同」本身仍成立**（ASR 模块**内部**前后自比）；**撤回**的是把它当作「**App 接入**零回归」的证据。详见 §89。
- 🔴 **§85⑦ 的「4 档全带 ≈ +1.9 GB RSS / +1.19 GB 私有」已撤回** ⇒ §86 fresh 进程实测：**分档相对 base = +1127.61 MB RSS / +1121.70 MB Private**（reviewer 指出：那是 4 个**单档**相加、含 base 里本来就有的 2400 档 ⇒ 真实增量只算 400+800+1600 三档）
- 🔴 **§85 反推的「① 单独（仅降 pml）= −19.76%」已撤回** ⇒ §86 **直接实测**：**−13.72% / −22.34% / −17.94%**（SPE/英/中，配对 bootstrap）⇒ 反推值偏高约 6 pp（分档收益被算进残差）
- §84④ 的「①+② 组合降幅 **−31.6% / −53.2% / −42.2%**」⇒ **已撤回**（base 臂受干扰 ＋ 四臂**按臂顺序**跑、未交错）⇒ **§85 交错重测 18 臂**：both vs base = -20.41% / -27.00% / -26.00%（SPE/英/中）。
- §84④ 的「② 分档单独降幅 **−2.0% / −41.7% / −2.8%**」⇒ **已撤回**（`tier_spe`/`tier_zh` 的 wall **含懒编译**）⇒ **§85（计时前全编译好）**：-5.62% / -9.04% / -6.66%（SPE/英/中）。
- §84⑨ 的「① 与 ② 有正交互（组合优于线性叠加 3.1–6.7%）」⇒ **已撤回**（tier 懒编译伪影把 ② 高估）⇒ **§85 正确口径下二者收益可叠加、无正交互**。
- §84⑥ 的「prefill 耗时与真实长度无关 ⇒ **不是**补齐到 `MAX_PROMPT_LEN`」⇒ **已撤回**（该反驳推理不成立：真实长度 26–285 **不能**否定静态补齐）⇒ **§85 实测按 T//32 分桶的 prefill p50 是平的** ⇒ **NPUW 确实按 `MAX_PROMPT_LEN` 静态补齐后计算**（reviewer 原推断正确）。
- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。
- §79② 的「旧 `ov-dec-06b-past-int8` 在 NPUW 下即编过 ⇒ **判断成立**」⇒ **ASR-055 已撤回**（`asr130…json` → `verdict.reviewer_hypothesis_npuw_only` = **`"REFUTED"`**；真条件 = `inputs_embeds`-only 端口形态 ＋ `NPUW_LLM` 缺一不可）。
- §79④ 的「**RTF 降到 mask2 的 0.38×（≈2.6× 加速）、出字延迟降到 0.39×**」⇒ **ASR-055 已撤回**（mask2 基线取自 10-25 旧 runner ⇒ **跨脚本**；同脚本同口径见关键数字表，**NPU 出字延迟反而慢 15%**）。
- §79⑥ 的「stateful NPU 对 mask2 GPU **显著变差 True**」⇒ **ASR-055 已撤回**（配对 bootstrap 只分 5 块 ⇒ 假象；改**按段配对** null 块后 6 组**全部不显著**，`asr146_wer_seg_paired.json`）。

## 未完成纠偏
| 编号 | 一句话 | 状态 |
|---|---|---|
| ASR-042 | VAD 门控 / 降频 / ASR+MT+TTS 并发 TTS RTF | ✅ **① VAD 门控已落盘**（§72.⑧-1；只给数据、不改默认值）；✅ **② 降频/合并窗口已落盘**（§72.⑧-2）；🟡 **③ 第 3 步（ASR+MT+TTS 同跑对比 TTS RTF）**⇒ **需与 TTS 线程协调 + 共用 TTS-044 负载脚本** ⇒ **本模块单方无法完成** |
| ASR-036 | 压缩 STATUS 与 CORRECTIONS（索引表每个编号一行 + ≤40 KB） | 🟡 **压缩本体已完成**（STATUS ≤160 行；CORRECTIONS 25.7 KB ≤ 40 KB）；🔴 **索引表已由 reviewer 补到 ASR-046 ⇒ 只缺 ASR-047/048 共 2 行** ⇒ CORRECTIONS 由 reviewer 维护且不提交 ⇒ **待 reviewer 补齐**（本模块不改不提交） |

> 🟡 **本模块已把可独立完成的部分做完**；ASR-042 第 3 步是**跨模块协作项**，等待 TTS 线程配合。

## 最近章节

> 只保留最近 3 节；更早的章节见 `status/archive/STATUS_ASR_upto_20261030.md`。
> 🔴 **§66–§68 的全文已归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文只留摘要；明细在 `status/asr/notes/asr_s6*.md`（**已提交**）。
> 🔴 **§70 / §71 / §72 已移入归档**（ASR-036「只保留最近 3 节」门禁）⇒ 明细见 `status/asr/notes/asr_s40.md` / `asr_s41.md` / `asr_s72.md`。

- ✅ **§94（ASR-067（FYI）独立核实：reviewer 对 §93 三条契约风险的答复逐条比对 ＋ 新发现第 5 条契约风险（2026-11-23 16:15–16:30））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec94_upto_20261123.md`

- ✅ **§95（ASR-068（FYI）独立核实：reviewer 五条修复的口径核验 ＋ 新发现 1 条 delivery 侧问题（2026-11-23 17:33–17:55））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec95_upto_20261123.md`

- ✅ **§97（巡检 ＋ APP-128 独立核实：§96 发现 A/B/C 已闭环，新发现 clone_s2 零标签不可归因（2026-11-23 20:49–21:05））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec97_upto_20261123.md`
- ✅ **§98（巡检 ＋ reviewer 对 §97「clone_s2 零标签」裁定的独立复核（2026-11-23 22:05–22:35））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec98_upto_20261124.md`
- ✅ **§99（巡检（无新 ASR 纠偏）＋ EXT v0.4.20 只读复核 ＋ 新发现「克隆计数未进 stats_full」（2026-11-24 11:20–11:45））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec99_upto_20261124.md` ＋ `status/asr/notes/asr_s99.md`

### §99 巡检（无新 ASR 纠偏）＋ EXT v0.4.20 只读复核 ＋ 新发现「克隆计数未进 stats_full」（2026-11-24 11:20–11:45）

> 🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**；邮件新增 3 封（APP-129/130/131）**均为 App 编号**，不进本模块 `last_ack`、无 ASR 动作项。**EXT 已推进到 v0.4.20（`4740b06`）**。🔴 **§97/§98 的开口项仍开口**（v0.4.20 `ext/bridge.py` L2514 `spk_reason` 仍只进段级表、未进 `stats_full`）；🔴 **新发现同型缺口**（`ext/clone_voice.py` 的 `_reasons` 只写日志、不进 `stats_full`）⇒ **APP-131 第 2 项要的 `tts_nearest_voice`/`gender_switch`/`gender_selfref` 当前取不到数（字段不存在，不是值为 0）**。🟢 性别守门实测生效（`gender_ab/v0420/bridge.log` **4** 行；v0.4.19 对照臂 **0** 行），但计数仍只可从日志读、不可机器解析。🟡 克隆模式两臂 e2e 复算 87/87 段、`dub_dropped`=0、`sep_rtf_p50` 0.267→0.258、`bg_clone_from_vocals` 78→83；🟡 **新澄清**：克隆模式标签来自 `clone_voice` 的 `SpeakerVoiceTable`、**不是 `bridge.tracker`** ⇒ `speaker.n_speakers` **不能**当「旁路有没有标签」的判据（旁路仍看 `spk_bypass.n_label`）。🔴 仍缺 v0.4.18 对照臂、`shared/bgkeep/vocals/` 仍不存在。🔴 **本轮未跑推理/计时/WER/分离器、未取 MACHINE_LOCK**（被 App 模块持有）、未改 4 个 ASR 交付文件、未改 `live_caption/`、未改 EXT 源码（只读）、未改纠偏文件内容、未打包。**全文** ⇒ `status/archive/STATUS_ASR_sec99_upto_20261124.md` ＋ `status/asr/notes/asr_s99.md`
