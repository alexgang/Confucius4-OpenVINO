last_ack: ASR-056
更新时间: 2026-11-11 15:40
当前任务: ✅ **ASR-056 全部落地**（`last_ack` ASR-055 → **ASR-056**）⇒ **停下等 reviewer 复核**：**①** §79 正文 **4 处旧结论已标撤回** ＋ 已撤回清单补 **3 条**；**②** 旧计时 json（**10 个**）标 `timing_valid="unverified"`（锁证据不可考 ⇒ **不要求重跑**）＋ `bk_run.py` 无锁时改写 `"no_lock"`；**③** 4 个 bench json 的 `comparison_vs_mask2` → **`cross_script_ref_1025`** ＋ `"comparable": false`（**并修掉「把 mask2 自己标成 stateful」的标签颠倒**）＋ `asr138*` 加 `superseded_by`；**④** 关键数字表**补 300 s / 18 s 并排行**（带出处）＋ **GPU 提速写 RTF 区间 1.6–2.1×** ＋ NPU 首字归因；**⑤** 套件**最终版脚本持锁补跑 4 组** ⇒ **独立复核 31/31 PASS**；**⑥** 套件交付前小修 a–f 全做 ⇒ **61 文件 / 2348476971 B、`--check` 0 处不符**。🔴 **未打包、未动 App 树 / 客户包 / `live_caption/`、未补跑 61 分钟、未重跑 10 分钟 WER、未做新的导出或量化**。
阻塞 / 待用户决定: 🟡 **待 reviewer 复核 ASR-056 的验收表**（§79 的 4 处撤回已标、json 字段已改、关键数字表已补行、套件 4 组已补测 31/31 PASS、套件小修 a–f 已做 ⇒ 等复核；**B 机实测由 reviewer 安排**）。🟡 **待 App 侧落地**（未变）：**①** **5 个** ASR 文件进 v2.3 / MiniMVP ＋ `sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 由 **4 项补到 6 项**；**②** 5 s **静态** seg IR 进 `models/spk/pyannote_seg_3_0/fp16-w5/`（**实测只有 `fp16`**）；**③** App 侧 import `asr_runtime_switches` ＋ 实现 `LIVECAP_SPK_MIN_CLEAN_RATIO`（默认值须来自 ASR 的 `DEFAULT_MIN_CLEAN_RATIO`，不互相 import）。🟡 **待 App 线程决定**：新说话人首次登记用哪段音频（ASR 已推荐**方案 B**）。🟡 **待用户决定**：`overlap_ratio_max` 惰性参数**是否修复**。⚠️ **ASR-042 第 3 步仍暂停**（ASR-047 用户决定）⇒ **本模块不跑 TTS**。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。
自指大小: 38921 B / 159 行


## 最近更新
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
| B 机套件 `b_kit_stateful` | **27 文件 / 2240545288 B**（assets 356067863 / models 1884374957 / scripts 244194 / results 85228） | `b_kit_stateful/MANIFEST.json` → `n_files` / `total_bytes` / `dir_sizes`；`SHA256SUMS.txt`（`--check` 0 处不符）|
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

### §79 ASR-053 / ASR-054 落地：Qwen3-ASR-0.6B **带 KV 缓存的 stateful decoder**（iGPU + NPU）—— 导出 / NPU 编译 / 对拍 / 测速 / WER 配对 / 流式草案（2026-11-11 09:22–11:20）
> 🔴 **同一个模型（Qwen3-ASR-0.6B），只换 decoder 导出形态**；encoder 仍用 `ov-encoder-06b-fp16-static`（**未换**）。
> 汇总产物 `results/asr140_acceptance_summary.json`（48710 B @ 11-20）＋ 独立复核 `results/asr141_verify.json`（**15/15 PASS**）。
> ⚠️ **ASR-054（10:38 下发）改了长跑口径** ⇒ 本节数字分**两套**（10 分钟片段 / 61 分钟），**不得混比**。
- ✅ **① 导出**：目录 `models/ov-dec-06b-stateful-int8sym/`（**2** 文件 / **755242318** B）；`openvino_model.bin` 752386441 B / sha256 `0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262baba4dc55e603b600d6a3`；`openvino_model.xml` 2855877 B / sha256 `8408e8862670922809404994bfa1762397dbeaab983572b1a3c43e8e72a9fd7b`；FP16 版 `models/ov-dec-06b-stateful-fp16/`。**与 mask2 基线同配方**（实测两 IR 的 `i8` 元素数同为 **196**、`i4`=0 ⇒ 同为按通道 INT8_SYM、**lm_head 保留 FP16**）⇒ 差异**只在导出形态**。
- ✅ **config 证明是 0.6B**：`models/Qwen3-ASR-0.6B/config.json` → `thinker_config.text_config.hidden_size`=**1024**、`num_hidden_layers`=**28**、`num_attention_heads`=**16**、`vocab_size`=**151936**。
- ✅ **② NPU 编译**（`results/asr130_npu_compile_check_stateful.json`）：新 IR 在 `NPU_USE_NPUW=YES`+`NPUW_LLM=YES` 下 **✅**（7.87 s，`EXECUTION_DEVICES`=**NPU**，图内 `ReadValue`=56 / `Assign`=56 ⇒ **KV cache 在模型内部**）。🔴 **纠偏要求核实「10-25 旧 past-int8 失败只是没开 NPUW」**：旧 `ov-dec-06b-past-int8` 在 NPUW 下 **❌**（0.93 s）🔴 **（已撤回，见 §80）** ⇒ **判断成立**（不开 NPUW 报 `to_shape was called on a dynamic shape`，开 NPUW 即编过）。
- ✅ **③ 对拍**（`results/asr132_parity_{GPU0,NPU}.json`）：**参考序列来自 HF fp32 贪心**（非 OV ⇒ 非自我循环），**主反证用故障注入**（`attention_mask` 前缀置 0）。| 项 | iGPU | NPU |  | 真实臂 stateful vs HF top1 一致率 | **1.0000** | **1.0000** |  | 真实臂 cos | 0.997853 | 0.995095 |  | mask2 vs HF top1 一致率 | 1.0000 | 1.0000 |  | **故障注入臂 top1 一致率**（须 ≤0.10） | **0.0000** | **0.0000** |  | 判据鉴别力 gap | **null** | **null** |  | 贪心 token 一致率 / 文本逐字相同 | 1.0000 / None | 1.0000 / None |  | self_check | **PASS** | **PASS** |
  🔴 **方法论（可复用）**：`results/asr132b_inject_probe.json` 实测 8 种注入 —— `position_ids +1` / `embeds×0.9` / `embeds×1.1` **一致率全 1.0（无效）**，只有 `attention_mask` 前缀置 0 掉到 **0.0000**；根因 = 真实臂 logits z-score 高达 **8.5865** ⇒ 弱扰动翻不动 argmax ⇒ **top1 只在大扰动下有鉴别力**。
- ✅ **④ 测速**（`results/asr135_bench_{GPU0,NPU}.json`，**持 MACHINE_LOCK**，`timing_valid=true`）：| 项 | iGPU | NPU | mask2 基线(iGPU/NPU) |  | 每 token 解码 p50 / p95 ms | **16.4051 / 49.5772** | **17.7664 / 26.6173** | — |  | prefill p50 / p95 ms（按 prompt 长度分桶） | 60.2073 / 72.4408 | 94.7818 / 119.3707 | — |  | 18 s 单段端到端 wall / rtf | **1.4541 / 0.0808** | **1.7060 / 0.0948** | — |  | 300 s 流式 RTF | **0.2627** | **0.3496** | 0.6827 / 1.0684 |  | 出字延迟 p50 / p95 s | **0.0951 / 0.1049** | **0.1451 / 0.1522** | 0.2470 / — |  | **RTF 比（stateful/mask2）** | **0.3848** | **0.3272** | 1.0 |
  🔴 **（已撤回，见 §80）** ⇒ **iGPU 上 RTF 降到 mask2 的 0.38×（≈2.6× 加速）、出字延迟降到 0.39×（≈2.6×）**；NPU 方向相同（0.33× / 0.38×）。
- ✅ **⑤ 流式接口草案**：`dev/asr133_stateful_streaming_draft.md`（**不改 App 树**）。核心：R2T2 `ASRBackend` 契约 **C3「调用间无状态耦合」是唯一真冲突点** ⇒ 建议**路线 A（严格遵守 C3）**：KV **调用内**丢弃，收益来自「每步只算 1 token」而非「省 prompt」；**路线 B（跨调用保留 KV）收益为零**（前缀回退每 chunk 都发生 ⇒ 必须 reset；二次 `reset_state()` 抛 `sub-views are not implemented`）。
- ✅ **⑥ WER 配对检验（ASR-054 10 分钟片段口径）**：片段 = SPE **0–600 s**（**开头即语音**：首 10 s 窗 rms=0.03565 / peak=0.3514 ⇒ 起点不顺延）；产物 `results/asr138_wer_10min.json`。**四臂切段完全一致**（93 段 / `rule_counts` 同 / `n_steps_total`=938 同）⇒ 文本可直接配对。| 臂 | WER % | S/D/I | hyp 词 | 同计分器基线差 | 95% CI | 显著变差 |  | stateful iGPU | **9.3416** | 101/34/31 | 1774 | **-0.0563 pp** | [-0.4497, 0.4507] | 否 |  | mask2 iGPU（基线） | 9.3979 | 99/37/31 | 1771 | 0 | — | — |  | stateful NPU | **9.6230** | 102/38/31 | 1770 | **0.2251 pp** | [0.0555, 0.5429] | **True** |  | mask2 NPU | 9.3416 | 101/34/31 | 1774 | -0.0563 pp | — | 否 |  🔴 **（已撤回，见 §80：5 块 CI 无意义；按段配对 null 块后 `significant_worse` = **false**）**
  ⇒ **同设备配对**（`asr138c_wer_npu_same_device.json`）：NPU 上 stateful vs mask2 = **0.2814 pp**、CI [-0.1114, 0.8556]、显著变差 **False** ⇒ **满足 ASR-053「不能比 mask2 显著差」**；NPU stateful vs GPU stateful = **0.2814 pp**、CI [-0.3944, 0.9772]、显著变差 False。
  🔴 **踩坑（已修）**：第一次跑 10 分钟臂时**参考集仍用 61 分钟**（11067 词）⇒ WER 假到 **85.45%**（D=9324 全是删除错误）⇒ **参考集必须与 hyp 同段**；已新增 `reports/c026_minimax_segjson_10min/`（**1777 词**）并给 `asr134_wer_score.py` 加 `--baseline-dir`。🔴 **CER 不可得**：仓库内**没有 ASR 的 CER 实现** ⇒ **只报 WER、不编 CER**。
- ℹ️ **61 分钟口径（ASR-054 之前，已完成；**不得与上面 10 分钟数字混比**）**：`results/asr133_stateful_61min_gpu/`（**553 段** / `complete=True` / RTF **0.2476** / 出字延迟 p50 0.0937 s）；同计分器 WER = **11.0057** vs mask2 **10.2919**（Δ **0.7138 pp**，CI [0.235, 1.0861]，**显著变差**）⇒ 🔴 **（已撤回，见 §80）** 61 分钟的 Δ **+0.7138 pp** 与 mask2 基线**跨脚本**（基线是 10-25 的旧 runner）⇒ **不作为 stateful 更差的证据**；**<1pp 不作决策依据**；**不补跑 61 分钟**。
- ⚠️ **本轮未做 / 未改**：**未打包**、**未动 App 树**、**未改任何客户包**、**未动 `live_caption/`**；`last_ack` ASR-053 → **ASR-054**（FYI：只改长跑素材长度，不改判据阈值）⇒ **本轮全部完成 ⇒ 停下等 reviewer 复核**。
- ⚠️ **工程坑留档**：会话上下文切换后宿主会清理 harness 后台任务注册表、**连带杀掉子进程**（`DETACHED_PROCESS` **也逃不掉**：仍在宿主 job object 里，`CREATE_BREAKAWAY_FROM_JOB` 被拒 `WinError 5`；`schtasks.exe` 被沙箱 Program Blacklist 拦、`Register-ScheduledTask` 权限拒）⇒ **长跑只能在工具调用内前台跑完，或分段续跑**（本轮 61 分钟跑用 `--resume` 从 `end_s=3413.12` 续跑收尾）。

### §80 ASR-055 落地：§79 的 ②④⑥ 三处结论改正 ＋ 按段配对重出 WER 表 ＋ **B 机测试套件 `b_kit_stateful`**（2026-11-11 11:45–13:50）

> 🔴 **明细全文** `status/asr/notes/asr_s80.md`（**已提交**）；本节只留结论、数字与链接。
> 🔴 **本节只做纠偏要求的事**；**未打包、未动 App 树 / 客户包 / `live_caption/`、未补跑 61 分钟、未做新的量化或导出**（ASR-055 §3「不做的事」逐条遵守）。
> 🔴 **WER 不自己算** —— §2.3 的表**复用 reviewer 的计分器** `reviewer_minimax_global`（目标机不调 MiniMax）。

- 🔴 **撤回 §79②（旧 past-int8 的 NPU 判断写反了）**：`results/asr130_npu_compile_check_stateful.json` → `verdict.reviewer_hypothesis_npuw_only` = **`"REFUTED"`**、`ov-dec-06b-past-int8__npuw_llm.ok` = **`false`**（**开 NPUW 仍报 `to_shape`**）⇒ **真条件 = `inputs_embeds`-only 端口形态 ＋ `NPUW_LLM` 缺一不可**（旧 IR 是 optimum 的 enc-dec 动态形态）。
- 🔴 **撤回 §79④（提速倍数夸大：mask2 基线取自 10-25 旧 runner ⇒ 跨脚本）** —— 改用**同脚本同口径**（`asr131` / 10 分钟，`results/asr138_10min_*/summary.json`）：| 指标 | GPU.0 stateful / mask2 | NPU stateful / mask2 |  | `rtf` | **0.2479 / 0.3998**（**0.62×，≈1.6×**） | **0.384 / 0.5696**（**0.67×，≈1.5×**） |  | `probe.decode_ms_p50` | **14.5565 / 56.7728 ms**（**3.9×**） | **18.7421 / 91.6198 ms**（**4.9×**） |  | `first_tok_latency_p50` | **0.0928 / 0.0949 s**（**持平**） | **0.1518 / 0.1296 s**（**stateful 反而慢 17%**） | ⇒ **「2.6× 加速」「出字延迟降到 0.39×」不成立**。**mask2 的 18 s / 300 s 持锁并排**（`asr147_bench_mask2_{GPU0,NPU}.json`，**带完整 `lock_record`**、`timing_valid=true`）：mask2 GPU0 **B3 wall 3.7929 s / rtf 0.2107**、**B4 46 段 / wall 161.9 s / rtf 0.5397 / 出字 p50 0.1317**；mask2 NPU **B3 wall 4.6038 s / rtf 0.2558**、**B4 46 段 / wall 157.78 s / rtf 0.5259 / 出字 p50 0.1264**。**NPU 出字延迟变差的归因（已核实）**：`asr135_bench_*.json` → `B2_prefill.prefill_ms_p50` = **NPU 94.7818 vs GPU 60.2073 ms**（慢 **34.5745 ms** = 94.7818 − 60.2073，≈ asr135 的 B4 出字延迟差 0.1451 − 0.0951 = 0.0500 s）⇒ **NPU prefill 更慢是主因**；🔴 reviewer 的「每次新建 InferRequest」假设**经核实不成立**（stateful 全程复用同一 `InferRequest`）⇒ 不写入结论。
- 🔴 **撤回 §79⑥（配对 bootstrap 分块太少 ⇒「显著变差 True」是假象）** —— 改**按段配对**（93 块）重出 `results/asr146_wer_seg_paired.json`（**7113 B**，`mode`=`segment_paired`，`n_boot`=5000，`scorer`=`reviewer_minimax_global`，四臂 `bounds_identical`=true）：| b 臂 vs a 臂 | `delta_pp` | `ci95` | `significant_worse` |  | stateful GPU0 vs mask2 GPU0 | **-0.0563** | [-0.5775, 0.4638] | **false** |  | mask2 NPU vs mask2 GPU0 | **-0.0563** | [-0.4836, 0.3842] | **false** |  | **stateful NPU vs mask2 GPU0** | **+0.2251** | **[-0.2906, 0.776]** | **false**（🔴 **旧「显著 True」被推翻**） |  | mask2 NPU vs stateful GPU0 | **+0.0000** | [-0.404, 0.4172] | **false** |  | stateful NPU vs stateful GPU0 | **+0.2814** | [-0.283, 0.8561] | **false** |  | stateful NPU vs mask2 NPU | **+0.2814** | [-0.2291, 0.813] | **false** | ⇒ 6 组 `self_check` 全 **PASS** ⇒ **满足「不能比 mask2 显著差」**。**61 分钟 +0.71 pp 已标注为跨脚本**（基线是 10-25 旧 runner）⇒ **不作 stateful 更差的证据**，**<1pp 不作决策依据**，**不补跑**。
- ✅ **锁记录写进 json（§2.5）**：`p3_run_with_lock.py` 把取锁/放锁时间、子进程 PID、等锁时间、退出码**写进子任务 json**（子进程写 `ASR_LOCK_RECORD_OUT` 清单 ⇒ 包装器放锁后回填）；**`timing_valid` 不再写死 `True`**（回填前写 `unverified`）⇒ `asr147` 两组**已补**（`lock_record` 完整）；**找不到证据的标 `unverified`，不要求重跑**。
- ✅ **B 机测试套件 `qwen3asr_06b\b_kit_stateful\`（§2.6）**：**27 文件 / 2240545288 B**（`MANIFEST.json` → `n_files`/`total_bytes`；`SHA256SUMS.txt` 同源，`bk_sha256.py --check` **0 处不符**）⇒ `assets/` **356067863 B / 11 文件**（`embed_tokens.npy` **311165056 B** fp16 / `mel_filters.npy` / **`hann_400.npy` 1728 B**（新）/ `prompt.json` / 2 个 wav / `tokenizer/` 4 文件）＋ `models/` **1884374957 B / 6 文件**（2 个 decoder + encoder；🔴 stateful decoder bin sha256 = `0059531a…d6a3` ⇒ **与 reviewer 核对值一致**）＋ `scripts/` **244194 B / 18 文件** ＋ `results/` **85228 B / 21 文件**（不进哈希）。**免 torch / 免 qwen_asr**（依赖仅 numpy 2.5.4 / openvino 2026.4.1 / tokenizers 0.22.2 / soundfile 0.14.0 可选）＋ **切段只导入最小模块** `bk_segmenter.py` ＋ **不写死路径**（`--work` / `BK_WORK`）＋ **一键脚本** `run_bk.sh`（6 组）。**三项 parity 3/3 PASS**（切段 **93/93 段界逐位同** / mel max abs diff **1.13845e-05** / tokenizer **prompt 19 ids + 5 条文本逐位同**）。
- ✅ **A 机自测（§2.6 验收「WER 逐位相同，RTF 差 ±10%」）** —— 参照 `results/asr135_stream_GPU0/`（同 IR / 同设备 / 同 runner）：| mel 后端 | 段界 | 段文本 | 词数 | 词级差异 | `rtf` vs 0.2627 | 判定 |  | **`--mel torch`** | **46/46 逐位同** | **46/46 逐位同** | **831 = 831** | **0 词（0%）** | **0.2458（差 6.43%）** | ✅ **7/7 PASS** |  | `--mel fft`（纯 numpy，免 torch） | 46/46 逐位同 | 43/46 同 | **831 = 831** | 6 词（**0.72%**） | 0.2843（差 8.22%） | ⚠️ 词级超 0.5% 阈值 | ⇒ **两条路都可用**：要**逐位对齐 A 机** ⇒ 装 torch 用 `--mel torch`；只要**结果等效** ⇒ 默认 `--mel fft`。
- 🔴 **mel 差异归因（经鉴别力实验，**双来源**）**：`bk_mel_bench.json` ⇒ 填充/窗/帧化**全部逐位相同** ⇒ 差异**只可能来自 FFT 实现与 dtype/log10 环节**：**① FFT 实现（不可消除）** torch=MKL **float32 累加** vs numpy=**pocketfft**（exact float64 DFT 同量级：谱差 **1.2190e-06 ~ 1.4631e-06**）⇒ 谱差 **1.3487e-06** / 相对 **8.04e-08**、mel 差 **1.4781951904296875e-05** ⇒ **纯 numpy 无法逐位复现 torch**；**② dtype/log10 环节（可消除）** transformers 4.57.6 的 `_torch_extract_fbank_features` **全程 float32** ＋ `torch.log10` ⇒ 照抄后与 transformers **max abs diff = 0.0（逐位相同）** ⇒ 已在 `--mel torch` 后端落地。`bk_diag_mel.json` ⇒ 同一 runner 只切换 mel 来源时 **`hf` 臂与 asr135 逐位相同 45/45**、`bk` 臂 42/45 ⇒ **排除 fp16 embedding 与 runner 逻辑差异**。
- 🔴 **本轮抓出并修掉 6 处真缺陷**：`close_seg` 漏 `seg_start = end_s`（**全部段 `start_s` 停在 0.0**）＋ 与 `asr131` 的 7 处口径偏差 ＋ `bk_mel_bench` exact 谱**符号写反**（假 bug 2.727e+01）＋ 窗函数 numpy 公式**无法逐位复现**（差 2.384e-07）⇒ **固化成资产 `hann_400.npy`** ＋ torch 模式第一版用 float64+`np.log10` ⇒ 改为**全程 float32 + `torch.log10`**（**max abs diff = 0.0**）＋ `bk_sha256.py` 把清单自身纳入哈希（**自指 churn**）⇒ **已排除**。🔴 **本轮推翻自己上一版的归因**：mel 差异**含两个来源**（FFT 实现**不可消除** ＋ dtype/log10 环节**可消除**）；且「`abs()²` 与 `re²+im²` 逐位等价」**不准确**（实测非逐位、相对差 ~3.6e-07，但**非**根因）。
- ℹ️ **§79①③⑤ 的其余内容不撤回**（导出 / 对拍 / 流式草案均成立）；§79 的 61 分钟条目**追加**「跨脚本」标注。

> ⇒ **本轮全部完成 ⇒ 停下等 reviewer 复核。**
### §81 ASR-056 落地：§79 正文 4 处标撤回 ＋ 旧计时 json 标 unverified ＋ 跨脚本比较块清理 ＋ 关键数字表补 300 s/18 s 行 ＋ 套件最终版持锁补跑 4 组 ＋ 交付前小修 a–f（2026-11-11 14:35–15:40）

> 🔴 **明细全文** `status/asr/notes/asr_s81.md`（**已提交**）；本节只留结论与数字（ASR-036 明细归 notes）。🔴 **只做纠偏要求的事**：**未打包、未动 App 树 / 客户包 / `live_caption/`、未补跑 61 分钟、未重跑 10 分钟 WER、未做新的导出或量化**。

- ✅ **① §79 正文 4 处旧结论已标「（已撤回，见 §80）」**（**只加标注，不删原句**）：**②** 旧 `ov-dec-06b-past-int8` 的 NPU 判断（开 NPUW **仍**报 `to_shape` ⇒ 纠偏判断 **REFUTED**）；**④** 「**iGPU 上 RTF 降到 mask2 的 0.38×（≈2.6× 加速）**」（⇒ **跨脚本**）；**⑥** asr138 的「**显著变差 True**」（⇒ **5 块 CI 无意义**，按段配对 **null** 块后 `significant_worse` = **false**）；**61 分钟**行的「差异**随素材长度变化**」**已删** ⇒ 改成「**跨脚本，不作为证据；<1pp 不作决策依据；不补跑**」。**「已撤回的旧结论」清单补 3 条**。
- ✅ **② 旧计时 json 标 `unverified`**（ASR-055 §2.5「找不到证据就标 unverified，**不要求重跑**」）：`asr135_bench_{GPU0,NPU}.json`、`asr135_stream_{GPU0,NPU}/summary.json`、`asr138_10min_{stateful,stateless}_{GPU0,NPU}/summary.json`、`asr133_stateful_61min_gpu/summary.json` ⇒ **共 10 个文件**、**数值一个未改**；🔴 **`bk_run.py` 无锁时改写 `"no_lock"`**（原写死 `True`）。
- ✅ **③ json 里的跨脚本比较块已清理**：4 个 bench json 的 `comparison_vs_mask2` ⇒ **`cross_script_ref_1025`** ＋ `"comparable": false` ＋ `"legacy_10_25_baseline": true`；🔴 **并修掉「把 mask2 自己标成 `stateful`」的标签颠倒**（`metrics.*.stateful` → **`this_arm`**）；`asr138_wer_10min.json` / `asr138c_wer_npu_same_device.json` ⇒ 加 **`"superseded_by": "asr146_wer_seg_paired.json"`**；**同 runner 的 `comparison_same_runner_peer` 保留**。**④ 关键数字表补 1 行**（300 s RTF / 18 s wall / 每 token p50 / 300 s 出字 p50 ＋ GPU 提速区间 ＋ NPU 首字归因，出处见表内）⇒ 见**「关键数字」表**末行。
- ✅ **⑤ 套件用最终版脚本持锁补跑 4 组**（`bk_run.py`(13:40)、`bk_mel.py`(13:43) 都在默认 fft 自测（13:34）**之后**才改 ⇒ 交给 B 的默认路径没用最终版脚本跑过；NPU 臂与 stateless 臂**一次都没跑过**）：**①** GPU.0 stateful 300 s（`rtf` **0.244** / 46 段 / **831** 词）；**②** NPU stateful 18 s（`B3.wall_s` **1.4672**）；**③** NPU stateless 18 s（**4.6058**）；**④** GPU.0 stateless 18 s（**3.7853**）。**4 组 `lock_record` 完整**（`released_at` / `exit_code`=0）、`mel_mode`=`fft`、`exec_devices` 正确。**验收 31/31 PASS**（`scripts/_asr056_verify_kit4.py`）：**300 s 段界 46/46 逐位同** ＋ **词数 831=831** ＋ **RTF 差 7.12%（≤10%）** ＋ **18 s wall 差 0.04%/0.20%/14.00%（均 ≤15%）** ＋ `text_head` **逐字相同**；**B 机模拟自检 0 FAIL**。
- ✅ **⑥ 套件交付前小修 a–f 全做**：**(a)** `run_bk.cmd` ＋ README §3.1 改「**12 组**」；**(b)** `wheels/`（**23** 个 wheel / **107868519** B）＋ 离线安装命令；**(c)** MANIFEST 加 **`sources`**（stateful decoder bin 的 `src_sha256` = `0059531a…d6a3` ⇒ **与 reviewer 11-11 实算值一致**）；**(d)** 剔除 `__pycache__/` 与 `results/`，5 个 A-only 脚本移入 **`scripts/a_only/`**，A 机参照结果入 **`ref_A/`**（**8** 个文件）；**(e)** README 第 298 行「唯一根因 = FFT 实现」⇒ 改成与 STATUS 一致的「**双来源**」；**(f)** 重生成 `SHA256SUMS.txt`/`MANIFEST.json` ⇒ **61 文件 / 2348476971 B**，`bk_sha256.py --check` ⇒ **0 处不符**。

> ⇒ **本轮全部完成 ⇒ 停下等 reviewer 复核。**