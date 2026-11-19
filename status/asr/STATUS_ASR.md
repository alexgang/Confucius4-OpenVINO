last_ack: ASR-062
更新时间: 2026-11-19 13:12
当前任务: 🟢 **已完成**（`last_ack` ASR-061 → **ASR-062**，2026-11-19 13:12）：**ASR-062**（降 `NPUW_LLM_MAX_PROMPT_LEN` ＋ encoder 按长度分档对 **NPU 流式** RTF 的影响）**全部跑完并落地**（§84）：① **12 臂持锁跑完**（{base, pml, tier, both} × {SPE 10min, FLEURS 英, FLEURS 中}）—— 前 8 臂由上一会话跑完，本轮 **12:49 TAKEOVER** 后用新脚本 `asr162_resume.py` **只补跑缺的 4 臂**（`tier_zh` ＋ `both_{spe,en,zh}`），**未重跑**已完成的 8 臂；🔴 上一会话**未释放锁** ⇒ 本轮**自动回收陈旧锁**后重新取锁、跑完**已释放**（**锁自检 8 次 / 0 被抢** ⇒ `timing_valid=true`）；② **NPU 流式 RTF**：base **0.3658 / 0.4836 / 0.3890** ⇒ ①+② 组合 **0.2501 / 0.2264 / 0.2249**（**降幅 −31.6% / −53.2% / −42.2%**）；③ **WER/CER 不劣化** —— 🔴 **12 臂的 `transcript.txt` 全部逐字节相同** ⇒ 配对 bootstrap **Δ = +0.0000 pp、CI95 = [0.0000, 0.0000]**（12/12 组），WER **SPE 9.7355% / 英 7.6223% / 中 5.5754%**（与 §83 流式值**逐位一致**）；④ **截断 0**（12/12 臂 `n_prompt_over_pml` = 0，`pml=320` ≥ 实测 max T=**285**）；⑤ 🔴 **只写数据，交付默认未改**（`asr06b_stateful_backend.py` **未动**）。
阻塞 / 待用户决定: 🟢 **ASR-062 已完成 ⇒ ASR 线程待命**（无用户指派不自开新实验）。🟡 **待用户决定（本轮新增 1 项）**：**①** 要不要把「**降 `NPUW_LLM_MAX_PROMPT_LEN` → 320 ＋ encoder 按长度分档（400/800/1600/2400）」**加成交付默认**？（数据在 §84：**NPU 流式 RTF 降 31.6–53.2%，WER/CER 逐字不变**；但**本轮只写数据，未改交付**，且分档需**多带 3 份 encoder IR（约 1.1 GB）**）。🟡 **待用户决定 3 项**（仍来自 ASR-060 §7，**未变**）：**①** 要不要把「整段离线转写」加成一条交付路径（**未改交付默认**）；**②** 「RTF≈0.05」对外怎么写（建议分口径写）；**③** 🔴 **encoder 静态上限 = 2400 mel 帧 = 24.0 s**（不是那两套 PR 宣称的 30 s）⇒ 要上 30 s 上下文**得重导出 encoder**。🟡 **待 App 侧落地 3 项**（未变）：5 个 ASR 文件进 v2.3 / MiniMVP ＋ `ASR_FILES` 4→6；5 s **静态** seg IR 进 `models/spk/pyannote_seg_3_0/fp16-w5/`；App 侧 import `asr_runtime_switches` ＋ 实现 `LIVECAP_SPK_MIN_CLEAN_RATIO`。🟡 **待 App 线程决定**：新说话人首次登记用哪段音频（推荐**方案 B**）。🟡 **ASR-028 换人点抽听**：仍为**用户侧待办**。⚠️ **ASR-042 第 3 步仍暂停**（ASR-047）⇒ **本模块不跑 TTS**。🔴 **B 机实测已关闭**（11-15 用户决定，ASR-059）⇒ B 套件冻结。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。 §80 全文归档见 `status/archive/STATUS_ASR_sec80_upto_20261115.md`。
自指大小: 39200 B / 154 行


## 最近更新
- 2026-11-19 2026-11-19 13:12 **ASR-062 已落地（§84）：NPU 流式 RTF 降 31.6–53.2%，WER/CER 逐字不变**—— **12 臂持锁跑完**（TAKEOVER 后**只补跑 4 臂**，锁自检 8 次 0 被抢）；**①+② 组合 RTF 0.2501 / 0.2264 / 0.2249**（base 0.3658 / 0.4836 / 0.3890）；**① 降 pml 512→320**：prefill p95 英 **267.18→70.60 ms（−73.6%）**；**② encoder 分档**：encoder p50 英 **37.00→11.50 ms（−68.9%）**；🔴 **12 臂 transcript 逐字节相同** ⇒ 配对 bootstrap **Δ=+0.0000 pp、CI95=[0,0]**；**截断 0**；**只写数据，交付默认未改**。
- 2026-11-19 09:16 **ASR-061 已读（`last_ack` → **ASR-061**）⇒ ASR-060（§83）**reviewer 复核通过、关闭；不需重跑**，ASR 线程**待命**（**纯文档**：未跑实验/未取锁/未打包/未动 `live_caption/`）**：reviewer 拉回 `results/asr/asr160/` **35 个文件**（mtime 2026-11-17 17:08:47）在本机**独立重算** —— **RTF**（Σ`blocks.total_s`/Σ`duration_s`）NPU 离线 EN **0.0496** / ZH **0.0448** / SPE **0.0665**、GPU.0 离线 **0.0383 / 0.0323 / 0.0526** 与 §83 **逐位一致**；**去掉第 1 块**（编译不计入）⇒ NPU **0.0487 / 0.0445 / 0.0666**、GPU **0.0365 / 0.0318 / 0.0524** ⇒ 首次推理影响 **≤0.002**；`total` = 各阶段之和**最大差 2e-06**；流式 Σdec_wall/Σ音频 **0.3056 / 0.2860 / 0.3138**（加 wall 后 **0.309 / 0.291 / 0.317**）；**WER/CER**（`compare_wer.norm` ＋ `jiwer`）EN/ZH 三臂与 §83 **逐位一致**，SPE 用 <600 s 的 **1765 词** ⇒ NPU 离线 **5.55%** / GPU 离线 **5.89%** / 流式 **9.46%**（§83 用 1777 词得 6.30 / 6.47 / 9.74 ⇒ **差别只来自参照截取，排序相同**）；离线**删除数少于流式**（EN **8 vs 14**）⇒ 没掉字；**流式阶段（reviewer 由 probe 算）**：EN 766 次 generate × prefill 96 ms ≈ **74 s（54%）**、1118 token × 19.8 ms ≈ **22 s（16%）**、其余 ≈ 41 s（30%）是 701 步里**重复的 mel ＋ encoder**；离线每 token：NPU **17–18 ms** / GPU **13 ms**；**模型身份**：dec bin `0059531a…`、enc `0b7463d6…`（两份相同）、encoder 输入**静态** `[1,128,2400]` ⇒ 按 **24 s** 切块正确；三轮持锁（PID 27088/30040/18920）**18 次自检 0 被抢**、16:15–17:10 无他模块目录写入 ⇒ `timing_valid` 成立；🔴 **3 个小问题只记录不重跑**（① `EXECUTION_DEVICES` 只读 decoder、漏打 encoder；② FLEURS 是**拼接 wav**按 24 s 切块、非 45 个单句（单句口径 prefill 占比更高、RTF 略高）；③ `compile_cache` 冷/热**未真清缓存** `cache_dirs_cleared=[]`）⇒ 明细见 `status/asr/notes/asr_s83.md` §八。
- 2026-11-17 17:20 **ASR-060 已落地（`last_ack` → **ASR-060**）⇒ 整段离线 vs 流式 RTF 对照完成（**只测速，未改交付默认**）**：**9 臂**（{NPU 离线, NPU 流式, GPU.0 离线} × {FLEURS EN 448.34 s, ZH 467.40 s, SPE 10 min 600.0 s}）**全部持锁跑完**（**锁自检 18 次全 True / 0 被抢**，跑完释放锁、**无残留进程**）；**NPU 离线 RTF 0.0496 / 0.0448 / 0.0665**、**NPU 流式 0.3094 / 0.2912 / 0.3165**、**GPU 离线 0.0383 / 0.0323 / 0.0526** ⇒ 🔴 **差距是测法不是补丁**（离线口径与宣称的 RTF≈0.05 同量级）；**WER/CER 同 normalizer**（reviewer `compare_wer.norm`）：离线 EN **5.2332%**/CER 2.7439%、ZH **4.3603%**/6.4050%、SPE **6.3028%**/2.5641% vs 流式 EN **7.6223%**/4.2917%、ZH **5.5754%**/7.7135%、SPE **9.7355%**/4.2005% ⇒ 离线**没掉字、反而更准**；**各阶段占比**：encoder 仅 1.9–7.6%、**每 token 解码 81–91%** ⇒ 瓶颈在解码不在 encoder；**冷/热编译** NPU 29.71/29.67 s（本机**无 NPUW 编译缓存目录** ⇒ 无缓存加速）、GPU.0 6.59/4.55 s（**1.45×** 真实命中）；🔴 **本轮修掉 2 个真缺陷**（流式臂中文**误用 English prompt** ⇒ 修正前 1231 汉字 + 589 拉丁字母、修正后 **1405 汉字 + 18 拉丁字母（逐字对齐 rc9）**、中文流式 WER **16.08% → 5.58%**；SPE 片段**误判为中文** ⇒ 实测是英文 ⇒ 重跑）；🔴 **限制**：encoder 静态上限 **2400 帧 = 24.0 s**（不是 30 s）⇒ 按 24.0 s 切块；FLEURS **逐句 wav 不在本机** ⇒ 逐句归属用「词数等分」（可重算）⇒ **总 WER 才是结论**；**未测打了 PR 的 IR** ⇒ 不能声称「合入后还能再快」⇒ 详见 **§83**（明细 `status/asr/notes/asr_s83.md`）。
- 2026-11-15 12:05 **ASR-059 已读（`last_ack` → **ASR-059**）⇒ B 机实测待办**已关闭**，ASR 线程**待命**（纯文档，未跑实验/未取锁）**：用户 **11-15 决定 B 机（192.168.2.206）不跑 ASR 套件** ⇒ 头部「B 机实测由 reviewer / 主会话安排」改为「**11-15 用户决定不做（ASR-059）**」；**ASR-028 换人点抽听**仍为**用户侧待办**（本线程**无动作**）。🔴 **本轮只改文档**：未跑计时/WER、未取 MACHINE_LOCK、未改套件文件、未打包、未动 `live_caption/`；🔴 **为腾出 ASR-036（≤40 KB / ≤160 行）余量**，**§80 全文归档** ⇒ `status/archive/STATUS_ASR_sec80_upto_20261115.md`（**逐字保留**）＋ 正文留一行摘要（结论/数字仍在「关键数字」表 ＋「已撤回的旧结论」清单，**未丢结论**）。
- 2026-11-14 16:25 **ASR-058 已读（`last_ack` → **ASR-058**）⇒ ASR-057 关闭，ASR 线程**待命**（按 §3 **不写新章节**）**：reviewer 验收**全通过** —— `run_bk.cmd` **3764 B / CRLF 134 / 裸 LF 0 / 纯 ASCII / SHA256 `3c9b387a…b3c1`**（与 SHA256SUMS 一致），三种用法 **12/1/1 组 rc=0**，假桩失败 ⇒ 打印 **failed 12/1/1 且 rc=1**，两参 ⇒ 用法 **rc=2**；套件 **65 文件 == `n_files` 65**（去 `MANIFEST.json`+`SHA256SUMS.txt` ⇒ **2 348 478 744 B** == §82），无 `.bak*`/`results_A_local`/`.pyc`；`ref_A/` **8 文件 = 最终版 4 组**；`sources` **14 条**（4 条派生 `identical=null`+`derived=true`）；10min 口径 SPE **0–600 s** 一致；本轮**只读复核**：`_asr057_verify_status.py` **32 PASS**、`_asr057_verify_kit.py` **26 PASS**（哈希 0 处不符）⇒ **未打包、未动 `live_caption/`、未上 B 机**。
- 2026-11-13 10:10 **ASR-057 已落地（`last_ack` ASR-056 → **ASR-057**）⇒ 停下等 reviewer 复核**：**①** 🔴 `run_bk.cmd` **CRLF + 纯 ASCII** ＋ **`all`(12 组) / `selftest` 分支** ＋ **失败非 0 退出** ⇒ **假桩实测 12 / 1 / 1**（`bk_check_cmd.py` **8 PASS / 0 FAIL**）；**②** `.bak_asr056/` ＋ `results_A_local/` **移出套件** ＋ `SKIP_DIRS` 收窄 ⇒ **文件数 65 == MANIFEST `n_files` 65**；**③** `ref_A/` 补**最终版 18 s 三组** ＋ 删旧脚本 3 组 ⇒ **最终版 4 组**；**④** `sources` 拆 **copy/derived** ⇒ **14 条**（copy 10 / derived 4）＋ **tokenizer + `prompt.json`** 补齐；**⑤** 遗留项「待用户决定 `overlap_ratio_max`」**已删**（用户 11-07 已决定不修）；**附带修掉 2 处真缺陷**（`n_files` 语义 ＋ **MANIFEST.json 在 PS 5.1 解析失败**）；**验收 26 PASS / 0 FAIL**、`--check` **0 处不符** ⇒ 详见 **§82**。
- 2026-11-11 15:40 **ASR-056 已落地（`last_ack` ASR-055 → **ASR-056**）⇒ 停下等 reviewer 复核**：**①** §79 正文 **4 处标撤回** ＋ 已撤回清单补 **3 条**；**②** 旧计时 json（**10 个**）标 `unverified` ＋ `bk_run.py` 无锁改 `"no_lock"`；**③** 跨脚本比较块清理（4 个 bench json → `cross_script_ref_1025` ＋ `"comparable": false`，**并修掉标签颠倒**）＋ `asr138*` 加 `superseded_by`；**④** 关键数字表**补 300 s / 18 s 并排行**（带出处）＋ GPU 提速写 **RTF 区间 1.6–2.1×**；**⑤** 套件**最终版脚本持锁补跑 4 组** ⇒ **31/31 PASS**；**⑥** 套件小修 a–f 全做 ⇒ **61 文件 / 2348476971 B**；**未打包、未动 App 树 / 客户包 / `live_caption/`** ⇒ 详见 **§81**。
- 2026-11-11 13:50 **ASR-055 已落地（`last_ack` ASR-054 → **ASR-055**）⇒ 停下等 reviewer 复核**：**①** 撤回 §79②（旧 past-int8 的 NPU 判断**写反** —— `asr130_npu_compile_check_stateful.json` → `verdict.reviewer_hypothesis_npuw_only` = **"REFUTED"**；真条件 = **`inputs_embeds`-only 端口形态 ＋ `NPUW_LLM`** 缺一不可）；**②** 撤回 §79④（提速倍数夸大 —— 同口径 10 分钟：GPU **0.2479 vs 0.3998（1.6×）**、NPU **0.3840 vs 0.5696（1.5×）**、出字延迟 GPU 持平 / NPU 反而慢 17%；mask2 18 s/300 s 持锁并排 `asr147_bench_mask2_{GPU0,NPU}.json` **带完整 `lock_record`**）；**③** 撤回 §79⑥（按段配对重出 —— `asr146_wer_seg_paired.json`，93 块，6 组**全部不显著**，「显著变差 True」被推翻）；**④** 61 分钟 +0.71 pp 标注**跨脚本**、<1pp 不作决策依据；**⑤** 锁记录写进 json（`timing_valid` 不再写死 True）；**⑥** B 机套件 `b_kit_stateful\`（**27 文件 / 2240545288 B**，SHA256 清单 **0 处不符**，三项 parity **3/3 PASS**，A 机自测 `--mel torch` **46/46 段逐位同 / 词数 831=831 / 词级差 0 / RTF 差 6.43%** ⇒ **7/7 PASS**）；**未打包、未动 App 树 / 客户包 / `live_caption/`、未补跑 61 分钟、未做新量化或导出** ⇒ 详见 **§80**。

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

- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。
- §79② 的「旧 `ov-dec-06b-past-int8` 在 NPUW 下即编过 ⇒ **判断成立**」⇒ **ASR-055 已撤回**（`asr130…json` → `verdict.reviewer_hypothesis_npuw_only` = **`"REFUTED"`**；真条件 = `inputs_embeds`-only 端口形态 ＋ `NPUW_LLM` 缺一不可）。
- §79④ 的「**RTF 降到 mask2 的 0.38×（≈2.6× 加速）、出字延迟降到 0.39×**」⇒ **ASR-055 已撤回**（mask2 基线取自 10-25 旧 runner ⇒ **跨脚本**；同脚本同口径见关键数字表，**NPU 出字延迟反而慢 15%**）。
- §79⑥ 的「stateful NPU 对 mask2 GPU **显著变差 True**」⇒ **ASR-055 已撤回**（配对 bootstrap 只分 5 块 ⇒ 假象；改**按段配对** null 块后 6 组**全部不显著**，`asr146_wer_seg_paired.json`）。


## 未完成纠偏
| ASR-062 | 测 MAX_PROMPT_LEN ＋ encoder 分档对 NPU 流式 RTF 的影响 | ✅ **已落地**（§84；**只写数据，交付默认未改**）|
| ASR-061 | reviewer 复核通过 ASR-060（§83），关闭；不需重跑 | ✅ **已关闭**（FYI）|
| ASR-059 | 用户决定：B 机不跑 ASR 套件；关闭 STATUS「B 机实测」待办 | ✅ **已关闭**（FYI）|
| ASR-058 | 记录 ASR-057 验收通过并关闭；B-kit 可交 B；ASR 线程待命 | ✅ **已关闭**（FYI）|
| ASR-057 | 修 `run_bk.cmd`（CRLF+ASCII / all+selftest / 失败非 0 退出）/ 清出套件里的 `.bak`+`results_A_local` / `ref_A` 补最终版 18s 三组 / `sources` 拆 copy+derived / 删过期遗留项 | ✅ **已落地**（§82）|
| ASR-056 | §79 正文 4 处标撤回 / 旧计时 json 标 unverified / 清跨脚本比较块 / 关键数字表补 300s-18s 行 / 套件最终版补测 4 组 / 交付前小修 a-f | ✅ **已落地**（§81）|
| ASR-055 | §79 的 ②④⑥ 改正 ＋ 按段配对 WER 重出 ＋ 锁记录写进 json ＋ B 机测试套件 `b_kit_stateful` | ✅ **已落地**（§80）|
| ASR-051 | 生产口径污染比例（或写明无法得到的原因）；不改 App 包 | ✅ **已落地**（§78）|
| ASR-050 | 用户决定：`min_clean_ratio` 默认 0.8 → 0.6；要求三处一致 + 900 s 回归 + 交接清单 | ✅ **已落地**（§77）|
| ASR-049 | 单页 App 说明（≤1 页）+ 直接回答 APP-071 + 量化「换人边界段混入上一人」 | ✅ **已落地**（§77）|

| 编号 | 一句话 | 状态 |
|---|---|---|
| ASR-047 | 用户决定：默认 0.64 s ＋ VAD 关闭；ASR-042 ③ 暂停；开关保留但默认关闭 | ✅ **已落地**（§74.⑤） |
| ASR-046 | 5 s IR 绝对路径清理 / asr113 两处异常 / min_clean_ratio 0.6 候选 / ASR-042 口径更正 / 环境变量开关 / 删 asr116 | ✅ **全部落地**（§74.①③④⑤⑥⑦ ＋ **§75** 补齐 ② 的**逐段 rows**）；**`min_clean_ratio` 默认值是否 0.8 → 0.6 仍由用户决定** |
| ASR-045 | 5 s 旁路窗口内核真改 + 5 s 静态 seg IR + 交付 4 文件 + NOTICE | ✅ **已落地**（本轮 §72.①②③④） |
| ASR-043 | `WIN_S` 默认 5.0 + 锁纪律 + ack 042 | ✅ **已满足**（`WIN_S_DEFAULT` 早已 5.0；本轮补「内核真按 5 s 跑」+ 全程持锁） |
| ASR-044 | 评测集 + 双窗口指标 + 错误分析 + 每项改动 A/B + v2.2 说明 | ✅ **已落地**（本轮 §72.⑤⑥⑦；v2.2 内核 == 自测代码 ⇒ 无需复测） |
| ASR-042 | VAD 门控 / 降频 / ASR+MT+TTS 并发 TTS RTF | ✅ **① VAD 门控已落盘**（§72.⑧-1；只给数据、不改默认值）；✅ **② 降频/合并窗口已落盘**（§72.⑧-2）；🟡 **③ 第 3 步（ASR+MT+TTS 同跑对比 TTS RTF）**⇒ **需与 TTS 线程协调 + 共用 TTS-044 负载脚本** ⇒ **本模块单方无法完成** |
| ASR-036 | 压缩 STATUS 与 CORRECTIONS（索引表每个编号一行 + ≤40 KB） | 🟡 **压缩本体已完成**（STATUS ≤160 行；CORRECTIONS 25.7 KB ≤ 40 KB）；🔴 **索引表已由 reviewer 补到 ASR-046 ⇒ 只缺 ASR-047/048 共 2 行** ⇒ CORRECTIONS 由 reviewer 维护且不提交 ⇒ **待 reviewer 补齐**（本模块不改不提交） |

> 🟡 **本模块已把可独立完成的部分做完**；ASR-042 第 3 步是**跨模块协作项**，等待 TTS 线程配合。
## 最近章节

> 只保留最近 3 节；更早的章节见 `status/archive/STATUS_ASR_upto_20261030.md`。
> 🔴 **§66–§68 的全文已归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文只留摘要；明细在 `status/asr/notes/asr_s6*.md`（**已提交**）。
> 🔴 **§70 / §71 / §72 已移入归档**（ASR-036「只保留最近 3 节」门禁）⇒ 明细见 `status/asr/notes/asr_s40.md` / `asr_s41.md` / `asr_s72.md`。

- ✅ **§76（ASR-048 落地：给 App 的「新说话人登记用干净段」接口说明（a–d）＋ `overlap_ratio_max` 惰性参数的定性）**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec76_upto_20261111.md`（逐字保留）；结论摘要：给 App 的「新说话人登记用干净段」判据接口说明已交付（≤1 页版见 `status/asr/notes/asr_for_app_spk_enroll.md`）；`overlap_ratio_max` 惰性参数**定性为「是否修复＝新开发量」**，**ASR 未自行改** ⇒ 列为待用户决定项。
- ✅ **§77（ASR-049 / ASR-050 落地：单页 App 说明 ＋ `min_clean_ratio` 默认值 0.8→0.6（三处一致）＋ 900 s 回归 ＋ 污染比例量化 ＋ 交接清单）**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec77_upto_20261111.md`（逐字保留）；结论摘要：单页说明 `status/asr/notes/asr_for_app_spk_enroll.md`（33 行）已交付；`min_clean_ratio` 默认值 **0.8 → 0.6**（代码默认值 / env 回退 / docstring **三处一致**）＋ 900 s 回归 **8/8 全 match**；交接清单 `notes/asr_for_app_asr050_handoff.md`；`overlap_ratio_max` 惰性参数**定性为「是否修复＝新开发量」**，**ASR 未自行改**。
- ✅ **§80（ASR-055 落地：§79 的 ②④⑥ 三处结论改正 ＋ 按段配对 WER 重出 ＋ **B 机测试套件 `b_kit_stateful`**）**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec80_upto_20261115.md`（逐字保留）；结论摘要：三处撤回（§79② **REFUTED**／§79④ **跨脚本提速夸大**／§79⑥ **「显著变差 True」被推翻**）；**按段配对 WER** 6 组**全部不显著**（stateful NPU vs mask2 GPU0 **Δ +0.2251 pp**，CI [-0.2906, 0.776]，`significant_worse=false`，`asr146_wer_seg_paired.json`，93 块）；**同脚本同口径 10 分钟 RTF** GPU **0.2479 / 0.3998**、NPU **0.384 / 0.5696**；**B 套件** `b_kit_stateful`（明细见「关键数字」表末行 ＋ `status/asr/notes/asr_s80.md`）。

- ✅ **§81（ASR-056 落地：§79 正文 4 处标撤回 ＋ 旧计时 json 标 unverified ＋ 跨脚本比较块清理 ＋ 关键数字表补 300 s/18 s 行 ＋ 套件最终版持锁补跑 4 组 ＋ 交付前小修 a–f）**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec81_82_upto_20261117.md`（逐字保留）；结论摘要：§79 正文 4 处旧结论已标「（已撤回，见 §80）」；**10 个**旧计时 json 标 `unverified`（数值未改）；4 个 bench json 的跨脚本比较块清理为 `cross_script_ref_1025` ＋ `"comparable": false`；关键数字表补 300 s/18 s 并排行；套件最终版脚本持锁补跑 4 组（**31/31 PASS**）⇒ 详见 `status/asr/notes/asr_s81.md`。
- ✅ **§82（ASR-057 落地：`run_bk.cmd` 修好（CRLF+ASCII / `all`+`selftest` / 失败非 0 退出）＋ 套件清出 `.bak`+`results_A_local` ＋ `ref_A` 补最终版 18 s 三组 ＋ `sources` 拆 copy/derived ＋ 删过期遗留项）**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec81_82_upto_20261117.md`（逐字保留）；结论摘要：`run_bk.cmd` 重写为 **CRLF + 纯 ASCII**（3764 B）＋ 补 `all`(12 组)/`selftest`(1 组) 分支 ＋ **失败 ⇒ `exit /b 1`**；套件磁盘实际 **65 文件 == MANIFEST `n_files` 65**；`ref_A/` = **最终版 4 组 / 8 文件**；`sources` **14 条**（copy 10 / derived 4）⇒ 详见 `status/asr/notes/asr_s82.md`。

- ✅ **§83（ASR-060 落地：Qwen3-ASR-0.6B INT8「整段离线转写」RTF ＋ 流式对照）**：**9 臂**（{NPU 离线, NPU 流式, GPU.0 离线} × {FLEURS EN/ZH, SPE 10 min}）**全部持锁跑完**（锁自检 18 次 / 0 被抢）；**NPU 离线 RTF 0.0496 / 0.0448 / 0.0665** vs **NPU 流式 0.3094 / 0.2912 / 0.3165** vs **GPU 离线 0.0383 / 0.0323 / 0.0526** ⇒ 🔴 **差距是测法不是补丁**（离线口径已达 RTF 0.045–0.067，与宣称同量级）；离线 **WER 更低**（EN 5.2332% vs 流式 7.6223%）⇒ 没掉字；**encoder 占比仅 1.9–7.6%、每 token 解码 81–91%** ⇒ 瓶颈在解码；🔴 修掉 2 个真缺陷（流式中文**误用 English prompt**、SPE **误判为中文**）⇒ 各重跑一次；明细见 `status/asr/notes/asr_s83.md`。


- ✅ **§83（ASR-060 落地：Qwen3-ASR-0.6B INT8「整段离线转写」RTF ＋ 流式对照（2026-11-17 15:52–17:20））**：**全文已归档** ⇒ `status/archive/STATUS_ASR_sec83_upto_20261119.md`
- ✅ **§84（ASR-062 落地：降 `NPUW_LLM_MAX_PROMPT_LEN` ＋ encoder 按长度分档对 **NPU 流式** RTF 的影响）**：**12 臂持锁跑完**（**TAKEOVER 后只补跑 4 臂**，锁自检 8 次 0 被抢）；**NPU 流式 RTF**：base **0.3658 / 0.4836 / 0.3890** ⇒ ①+② 组合 **0.2501 / 0.2264 / 0.2249**（**−31.6% / −53.2% / −42.2%**）；**①** 降 pml 512→320（实测 max T=285，**断言防静默截断**）⇒ prefill p95 英 **267.18→70.60 ms**；**②** encoder 4 档静态 IR（🔴 朴素 reshape **直接抛异常** ⇒ 改「动态 reshape→patch 60 常量→静态 reshape」）⇒ encoder p50 英 **37.00→11.50 ms**；🔴 **12 臂 transcript 逐字节相同** ⇒ **WER/CER 逐字不变**（配对 bootstrap **Δ=+0.0000 pp、CI95=[0,0]**），WER **9.7355 / 7.6223 / 5.5754%**（与 §83 逐位一致）；**截断 0**；**只写数据，交付默认未改** ⇒ 明细见 `status/asr/notes/asr_s84.md`。

### §84 ASR-062 落地：降 `NPUW_LLM_MAX_PROMPT_LEN` ＋ encoder 按长度分档对 NPU 流式 RTF 的影响（2026-11-19 09:30–13:10）
- ✅ **① 12 臂持锁跑完**（{base, pml, tier, both} × {SPE 10min, FLEURS 英, FLEURS 中}）：前 8 臂由上一会话（10:19–11:38）跑完，本轮 **12:49 TAKEOVER** 后用新脚本 `asr162_resume.py` **只补跑缺的 4 臂**（`tier_zh` ＋ `both_{spe,en,zh}`），**未重跑**已完成的 8 臂；🔴 上一会话**未释放锁**（残留 pid 24060 已死）⇒ 本轮 `acquire()` **自动回收陈旧锁**后重新取锁、跑完**已释放**（**锁自检 8 次 / 0 被抢** ⇒ `timing_valid=true`）。
- ✅ **② §0 量长**：每次 prefill 的**真实 prompt 长度** max **163 / 185 / 285**（SPE/英/中，p50 68–76）；每次送 encoder 的 **mel 帧数** max **1088 / 1280 / 2048**（p50 384–448）⇒ 🔴 **两者都远小于上界（512 / 2400）** ⇒ 交付路径**从没把 encoder 喂满 24 s**；§1 取值：max T=**285** ⇒ 向上取整到 64 的倍数 = **320**（「再小一档」256 < 285 ⇒ **不允许**）⇒ 🔴 已加**静默截断防护**（`pml ≥ 实测 max T` **显式断言**，不满足就**拒绝跑**）。
- ✅ **③ §2 encoder 分档（4 档静态 IR）**：🔴 **朴素 `model.reshape([1,128,N])` 在这份 IR 上直接抛异常**（1577 个 layer 的 2400/24/312 维度**全部烘死**）⇒ 改用「**动态 reshape → patch 60 处尺寸常量 → 静态 reshape**」三步法（顺序反了必挂，已逐条实测），N∈{400,800,1600,2400} **全部构建+编译通过**（NPU 编译 6.53–16.84 s/档）；**数值对拍（24 段 vs 2400 基线档）**：余弦 min **0.999992**、max abs err **4.578e-04**（其余 23 段 **0.0**）⇒ 属 fp16 累加顺序噪声，非「补零影响结果」。
- ✅ **④ §3 四臂 RTF（不含编译；12/12 臂 `wall_s/covered_s` 可重算且与 `rtf` 一致）**：

| 素材 | base | ① pml=320 | ② tier | ①+② both | ① 降幅 | ② 降幅 | 组合降幅 |
|---|---|---|---|---|---|---|---|
| SPE 10min | 0.3658 | 0.2752 | 0.3586 | **0.2501** | −24.8% | −2.0% | **−31.6%** |
| FLEURS 英 | 0.4836 | 0.2478 | 0.2821 | **0.2264** | −48.8% | −41.7% | **−53.2%** |
| FLEURS 中 | 0.3890 | 0.2428 | 0.3781 | **0.2249** | −37.6% | −2.8% | **−42.2%** |
- ✅ **⑤ 阶段归因（p50，ms）**：**① 降 pml 512→320 ⇒ prefill 变快**（英 p50 130.94→66.11、**p95 267.18→70.60（−73.6%）**；SPE p50 94.80→66.77；中 p50 101.41→66.95）；**② 分档 ⇒ encoder 变快**（英 p50 37.00→**11.50（−68.9%）**、SPE 26.53→10.76、中 28.13→14.00；阶段占比 16.6%→9.4%）；**decode 几乎不变**（17–18 ms）⇒ 瓶颈未转移。**档位分布**：SPE {400:556, 800:457, 1600:18}、英 {400:388, 800:323, 1600:55}、中 {400:386, 800:276, 1600:103, 2400:32} ⇒ 🔴 **2400 档几乎不用** ⇒ 实际只需 **400/800/1600 三档**（+2400 兜底）。
- 🔴 **⑥ ① 的机理与 reviewer 原推断不同（对外表述要改）**：reviewer 推断「`MAX_PROMPT_LEN=512` ⇒ 每次 prefill 都补齐到 512」；实测**真实长度只有 26–285** ⇒ **不是**补齐到 512。但 **NPUW 的 KV 预分配按 `MAX_PROMPT_LEN` 算** ⇒ 降到 320 后 prefill **仍明显变快** ⇒ 🔴 **reviewer 的「结论方向」对（prefill 是瓶颈、降幅显著），但「原因」不准确**。
- ✅ **⑦ WER/CER 不劣化（同一 normalizer = reviewer `compare_wer.norm`，逐字 import 未改）**：🔴 **12 臂的 `transcript.txt` 全部逐字节相同** ⇒ **不是「统计不显著」而是「完全一致」**；配对 bootstrap（5000 次，判据用全集）**Δ = +0.0000 pp、CI95 = [0.0000, 0.0000]**（12/12 组）；WER **SPE 9.7355% / 英 7.6223% / 中 5.5754%**、CER 4.2005 / 4.2917 / 7.7135 ⇒ 🔴 这三个 base WER 与 **§83 流式值逐位一致** ⇒ 跨轮次口径一致、未偷换口径；**截断 0**（12/12 臂 `n_prompt_over_pml` = 0、`n_prompt_over_ir_max` = 0）。
- 🔴 **⑧ 本轮修掉 2 个真缺陷（都在打分脚本自身，**未改交付套件 `bk_run.py`**）**：**①** 评分器把 `transcript.txt` **原文**喂给 normalizer ⇒ **时间戳数字被当成词** ⇒ SPE 臂凭空多 **372 个插入错误**（I=380）⇒ WER 虚高到 **29.4879%** ⇒ 修法：hyp 改用 `segments.json` 的 `text`（纯正文）⇒ **修正后 9.7355%**；**②** verdicts 键格式化串**只给一个参数** ⇒ `TypeError: not enough arguments for format string` ⇒ 修成 `verdicts[mat_tag]`。
- ✅ **⑨ ① 与 ② 有正交互（组合优于线性叠加）**：SPE 预期 0.2680 vs 实测 **0.2501**（低 6.7%）；英 0.2354 vs **0.2264**（低 3.8%）；中 0.2320 vs **0.2249**（低 3.1%）⇒ 🔴 **建议按 ①+② 组合实施，不要只取其一**。**§4 GPU.0 一臂**：只② 也有收益（RTF **0.1845→0.1626，−11.9%**、encoder 占比 33.39%→16.06%、转写逐字节相同）；⚠️ 该冒烟是**上一会话跑的**（非本轮持锁、未做配对 bootstrap）⇒ **仅参考**。
- ⚠️ **⑩ 口径限制**：参照 = SPE 用 reviewer 的 MiniMax baseline（`reports/c026_minimax_segjson_10min`，**1777 词**，同一计分器）；FLEURS 中英用 `bench_data.json` 的 **45 句**逐句文本（**词数等分**到时间轴，**非真实句边界**）⇒ 🔴 **总 WER 才是结论**；RTF **不含编译**（编译单列）；`MAX_PROMPT_LEN` 只对 **decoder** 的 NPUW 生效（encoder 不加 NPUW，与 `bk_run` 一致）；🔴 **本轮只写数据，未改交付默认**（`asr06b_stateful_backend.py` **未动**）⇒ **是否改交付默认由用户决定**。
- ✅ **⑪ 产物（`results/asr162/`，按纪律**未入库**）**：12 个 `<臂>_<素材>/`（各含 `summary.json` ＋ `transcript.txt` ＋ `segments.json` ＋ `segments.jsonl`，含 `raw_prefill_T`/`raw_mel_frames`/`raw_tier_used` **全量数组**）＋ `step0_step0_{spe,en,zh}.json` ＋ `tiers/tier_n{400,800,1600,2400}/`（4 档 IR，合计 1.4 GB）＋ `tiers/enc_tiers.json` ＋ `resume_session.json`（锁自检）＋ `wer_cer.json`（WER/CER + CI + verdicts）＋ `_smoke_parity.json`（数值对拍）⇒ **明细见 `status/asr/notes/asr_s84.md`**。

> ⇒ **本轮完成 ⇒ 停下等 reviewer 复核。**
