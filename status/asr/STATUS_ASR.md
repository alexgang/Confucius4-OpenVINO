last_ack: ASR-050
更新时间: 2026-11-06 09:45
当前任务: ✅ **ASR-049 / ASR-050 已落地**（`last_ack` ASR-048 → **ASR-050**）：① **ASR-049**：单页 App 说明（`notes/asr_for_app_spk_enroll.md`，**33 行**）已写（开头 3 行问答直接回答 **APP-071**）＋「换人边界段混入上一人」**已量化**（产物 `asr125`）；② **ASR-050**：用户决定的 `min_clean_ratio` **默认值 0.8 → 0.6** 已落地（**代码 / 环境变量 / 配置说明三处一致**），**900 s 评测集回归**与 **asr118 的 0.6 臂 8/8 指标全一致**（产物 `asr122`），交接清单已写（`notes/asr_for_app_asr050_handoff.md`）；③ 🔴 **本轮抓出并修掉 1 处判据缺陷**（`asr122` 的 `identity_aligned` 口径不对称 ⇒ 0.4779 实为缺陷，正确口径 **1.0**，产物 `asr124`）；④ **未动 `live_caption/` 任何文件**；**只提交 `status/asr/` 下文件**。
阻塞 / 待用户决定: 🟡 **待 App 侧落地**（实测复核，仍未变）：**①** 把 **5 个** ASR 文件（含 `asr_spk_window.py` ＋ `asr_runtime_switches.py`）打进 v2.3 / MiniMVP 下一版（**4 个包全盘 `find` 命中 0** ⇒ 未进包）＋ `sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 由 **4 项补到 6 项**；**②** 5 s **静态** seg IR（md5 `14b224bced3289237799bc9a7eb746ff`）放进 `models/spk/pyannote_seg_3_0/fp16-w5/`（**实测只有 `fp16`**）；**③** App 侧 import `asr_runtime_switches` ＋ 实现 `LIVECAP_SPK_MIN_CLEAN_RATIO`（**默认值须来自 ASR 的 `DEFAULT_MIN_CLEAN_RATIO`**，不互相 import）；🔴 App 侧 `app193_app053_spk_frame_audit.py` 的 **docstring 里仍写 `min_clean_ratio=0.8`**（**ASR 不动 App 文件** ⇒ 待 App 同步）。🟡 **待 App 线程决定**（ASR-048/049 第 3 点 (b)：新说话人**首次登记用哪段音频**）—— ASR 已给出**明确推荐：方案 B**（等**第二段**再登记 ＋ 只取**最靠后**的 clean 区间），**最终由 App 决定**。🟡 **待用户决定**：`overlap_ratio_max` 惰性参数**是否修复**（把重叠类并入判定 ＝ **新开发量**）⇒ **ASR 未自行改**。⚠️ **ASR-042 第 3 步仍暂停**（ASR-047 用户决定）⇒ **本模块不跑 TTS**。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。
自指大小: 30207 B / 129 行


## 最近更新
- 2026-11-06 09:45 **ASR-049 / ASR-050 落地（`last_ack` ASR-048 → **ASR-050**）**：① ✅ **ASR-050 ①「三处一致」**：`min_clean_ratio` **0.8 → 0.6**（`asr052_speaker_tracker_api.py` **:308** 代码默认值 / **:146** `DEFAULT_MIN_CLEAN_RATIO` / **:149** `ASR_SPK_MIN_CLEAN_RATIO` 环境变量 / **:279–301** 配置说明表）；**其它参数一律未动**（步长 0.64 s / VAD 关 / 5 s 窗 / `thr=0.35`）；② ✅ **ASR-050 ② 回归**：900 s 评测集重跑，**8 项指标与 asr118 的 0.6 臂全部 `match: true`**（命中 22/26、recall 0.8462、误报 3、无标签段 5）（产物 `asr122_asr050_regression.json`，自检 **8/8**）；**主路隔离**（`main_path_isolated=true` ＋ 假文件反证）⇒ WER 不受影响（**WER 交 reviewer**）；③ 🔴 **本轮修掉 1 处判据缺陷**：`asr122` 的 `identity_aligned.agreement_rate` = **0.4779** 与「逐段 136/136 一致」**自相矛盾** ⇒ 根因是**不对称口径**（A 臂取真值 / B 臂取映射；实测 4 簇 vs 真值 5 人）⇒ **正确口径 = 1.0**（产物 `asr124_identity_aligned_recheck.json`，自检 **6/6**，反证降到 0.0368）；④ ✅ **ASR-049 ①②**：单页说明 `notes/asr_for_app_spk_enroll.md`（**33 行**）（开头 3 行问答直接回答 **APP-071**，含「标签多 ≠ 可登记」）；⑤ ✅ **ASR-049 ③ 量化**：「换人边界段混入上一人」原方案 **0.0**（N=0.0 s / 分母 22.545 s）、改进 C **0.0**（N=0.0 s / 分母 27.545 s）（产物 `asr125`）；🔴 **口径澄清**：纠偏写的「AMI RTTM」**不覆盖本评测集**（3 clip 全来自 `260902_SPE_audio.wav`）⇒ 改用 **ASR-028 人工核对 `ref_segments`** 主口径 ＋ SPE RTTM 交叉核对；🔴🔴 **污染 0 只在评测集成立**（评测集按**人工段界**切段、每段单人 ⇒ **结构性必然**；注入反证证明判据**有鉴别力**）⇒ **不能外推到生产**（产物 `asr126`）；🔴 **asr123 捕获失效已作废**（`run_clip` 里 `sys.modules.pop` 重载模块 ⇒ 猴补丁从未生效 ⇒ 分母为 0、自检未过）⇒ 改用 **import hook** 重跑（`asr125`）；⑥ ✅ **ASR-050 ③ 交接清单**：`notes/asr_for_app_asr050_handoff.md`（改了哪个文件 / 哪一行 / md5 / App 要同步哪些文件）；⑦ 🟡 **未自行决定**：`overlap_ratio_max` 惰性参数是否修复 ⇒ **待用户决定**；**未动 `live_caption/`**。
- 2026-11-06 02:32 **无新纠偏（`last_ack` 保持 **ASR-048**）⇒ 待命**：① `CORRECTIONS_ASR.md` 全文最大编号 **ASR-048** == `last_ack`（**无 ASR-049+**）⇒ 本轮**未执行任何纠偏、未开新实验、未跑推理/测速、未占设备**（`MACHINE_LOCK` 实测不存在）、**未动 `live_caption/`**；② ✅ **CORRECTIONS 索引表已由 reviewer 补到 ASR-046**（实测全文 **17** 条标题 / 索引 **46** 行）⇒ **当前只缺 ASR-047 / ASR-048 共 2 行**（旧章节里记的缺失行数已过期）⇒ 本模块按铁律 1 **不代改**；③ 🟡 **ASR-042 ③ 仍是跨模块协作项**（ASR-047 已暂停 ⇒ 本模块不跑 TTS）；④ 🟡 **待 App / 用户决定的项不变**（5 个 ASR 文件 + 5 s 静态 seg IR 进包、`min_clean_ratio` 0.8→0.6、新说话人首次登记用哪段音频）⇒ **本轮只维护 STATUS，未新增章节**。
- 2026-11-05 16:50 **ASR-048 落地（`last_ack` ASR-047 → ASR-048）：给 App 的「干净段」接口说明（a–d）＋ `overlap_ratio_max` 惰性参数定性**（产物 `asr121_overlap_clean_diag.json`，23314 B，`self_check_pass=true`；**纯静态分析 + 数值复刻**，不跑推理、不占设备、不需锁）：① 🔴 **`overlap_ratio_max` 恒不触发**（`p_dom` 只含 powerset 单人三类 ⇒ 行和 ≤ 1.0 ⇒ `>1.05` 恒 False ⇒ `overlap_ratio` 恒 **0.0**；20000 次复刻 = **0.0**，反证并入重叠类 = **0.61835**）⇒ 🔴 **§75「`B_overlap_ratio_max_0.05` 与基线 136/136 相同」不等于「已验证无影响」**（**加口径，不改旧行**）；② 🔴 **`clean_ratio` 全 None = 桥接层丢字段**（内核 `:347` 确实算，桥接层白名单只转发 6 字段）⇒ **`min_clean_ratio` 是生效的**；③ 🔴 **`spk_conf` = 与已有簇心的最大余弦相似度** ⇒ **低 = 新人**，**不是标签可信度**（新说话人实测 0.0833/0.1212/0.0153/0.101/-0.0446）；④ 🔴 **登记用 `clean_ranges` 子区间**（非整段）⇒ **换人边界段可能混入上一说话人**（`is_new_spk` = 「与上一段不同」⇒ 基线 29 次 vs 换人点 26 ⇒ 3 次误触发）；⑤ ✅ **`clean_ranges` 现有 API 已返回** ⇒ **App 无需新字段**；⑥ ✅ **「≥1.5 s / 攒到 3 s」已在用 clean 累计时长** ⇒ **无需再改**；⑦ 🔴 **`spk` ID = 到达序编号，跨臂不可比**（`min_clean_ratio` 两臂 clip02 diff 32/46）。
- 2026-11-05 14:55 **ASR-046 ② 的「逐段 rows」已落盘（`asr118_param_ab_rows.json`，8 臂 × 136 段）＋ 撤回 §74 的一处未落盘措辞**：① 🔴 **§74 措辞缺陷已撤回**：§74 写「逐段 rows 落盘于 `asr118_param_ab_rows.json`」，但**写盘当时该产物并不存在**（上一会话在 asr118 跑完前就落了 §74）⇒ 违反「没落盘的东西不能写已交付」⇒ 本轮改为指向 §75；② ✅ **thr 三档相同之谜已用逐段数据复核**：**直接证据** = 136 段的 `spk_conf` 落在 **[0.30,0.40] 区间的 = 0 个**（低于 0.30 的最大 **0.188**、高于 0.40 的最小 **0.4217**）⇒ **三档切在同一段「空隙」里 ⇒ 结果必然相同** ⇒ **参数确实传进了内核**；③ ✅ **min_dur_s=3.0 全无标签已用逐段数据复核**：请求时长 ≥ 3.0 s 的有 **134 段**（请求时长 < 3.0 s 的仅 2 段）但**全部无标签**（reason 全 `async_pending`）⇒ **不是「段太短」**；对照 min_dur_s=1.5：≥1.5 s 的 **136 段**里 **125 段有标签** ⇒ **「段真短」被否**；④ ✅ **逐臂逐段对比齐**（A 基线 vs 各候选，**同一计分器**）：`B_thr_0.4`（改 thr=0.4）：命中 19、recall 0.7308、误报 3、无标签 12、逐段同 136 / 异 0（共 136 段）；`B_thr_0.3`（改 thr=0.3）：命中 19、recall 0.7308、误报 3、无标签 12、逐段同 136 / 异 0（共 136 段）；`B_min_dur_s_1.5`（改 min_dur_s=1.5）：命中 19、recall 0.7308、误报 3、无标签 11、逐段同 135 / 异 1（共 136 段）；`B_min_dur_s_3.0`（改 min_dur_s=3.0）：命中 0、recall 0.0、误报 0、无标签 136、逐段同 12 / 异 124（共 136 段）；`B_min_clean_ratio_0.4`（改 min_clean_ratio=0.4）：命中 24、recall 0.9231、误报 4、无标签 3、逐段同 95 / 异 41（共 136 段）；`B_min_clean_ratio_0.6`（改 min_clean_ratio=0.6）：命中 22、recall 0.8462、误报 3、无标签 5、逐段同 97 / 异 39（共 136 段）；`B_overlap_ratio_max_0.05`（改 overlap_ratio_max=0.05）：命中 19、recall 0.7308、误报 3、无标签 12、逐段同 136 / 异 0（共 136 段）；⑤ ✅ **`min_clean_ratio` 候选经逐段复核**：0.6 ⇒ 召回 22/26、误报 3（不变）、无标签段 5；0.4 ⇒ 召回 24、误报 4（↑）⇒ **0.6 仍是「召回↑且误报不变」的最优点**；⑥ 🔴 **本轮 asr118 跑批用 checkpoint 断点续跑**（上一会话 11:23–12:41 跑到第 5/8 臂被中断 ⇒ 只剩 `_cp_asr118/` 5 个臂的 checkpoint、**产物本身没落盘**）⇒ **从断点续跑**，未重跑已完成的臂。

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
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |

### 已撤回的旧结论（**不作为结论**，仅备查）

- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。


## 未完成纠偏
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

### §75 ASR-046 ② 逐段 rows 落盘（asr118，8 臂 × 136 段）＋ 撤回 §74 的一处未落盘措辞（2026-11-05 13:54–14:55）

> 🔴 **明细全文** `status/asr/notes/asr_s75.md`（**已提交**）＋ 产物 `asr118_param_ab_rows.json`（675763 B）；**本节全文已归档** `status/archive/STATUS_ASR_upto_20261030.md`（`## §75 `）⇒ 正文只留摘要。
- ✅ **thr 三档相同** = A 基线 136 段的 `spk_conf` 落在 [0.30,0.40] 的 = **0**（最大 **0.188** / 最小 **0.4217**）⇒ 三档切在同一段「空隙」⇒ **参数确实传进了内核**。
- ✅ **min_dur_s=3.0 全 `async_pending`** = 长度判据对 **134/136** 段根本不触发却全无标签 ⇒ 根因是**判定顺序倒置 ＋ `_drain_pending` 永不回填**，**不是「段太短」**（对照 min_dur_s=1.5：136 段里 **125** 段有标签）。
- 🔴 **逐臂逐段对比（A 基线 vs 各候选，同一计分器）**：`thr=0.4`/`thr=0.3` 命中 19、recall 0.7308、误报 3、无标签 12、逐段同 136/异 0；`min_dur_s=1.5` 无标签 11（同 135/异 1）；`min_dur_s=3.0` 命中 **0**（同 12/异 124）；**`min_clean_ratio=0.6` 命中 22、recall 0.8462、误报 3、无标签 5**（同 97/异 39）；`min_clean_ratio=0.4` 命中 24、**误报 4（↑）**；`overlap_ratio_max=0.05` 同基线 136/异 0（**该参数惰性，见 §76**）。
- 🔴 **撤回 §74 的一处未落盘措辞**（§74 写「rows 已落盘」但**写盘时产物并不存在**）⇒ 违反「没落盘的东西不能写已交付」；**本节是 asr118 真正落盘后的记述**。
- ✅ 本轮产物自检 `self_check_pass=True`、锁探针 **964** 次、stolen **0**、`timing_valid=True`。
### §76 ASR-048 落地：给 App 的「新说话人登记用干净段」接口说明（a–d）＋ `overlap_ratio_max` 惰性参数的定性（2026-11-05 16:20–16:50）
> 📄 **单页 App 说明（ASR-049 ①，≤1 页）**：`status/asr/notes/asr_for_app_spk_enroll.md`（**33 行**）—— 开头 3 行问答直接回答 **APP-071**；**ASR-050 交接清单**：`status/asr/notes/asr_for_app_asr050_handoff.md`；量化结论见 **§77**。

> 🔴 **明细全文** `status/asr/notes/asr_s76.md`（**已提交**，241 行）＋ 产物 `asr121_overlap_clean_diag.json`（23314 B）；**本节全文已归档** `status/archive/STATUS_ASR_upto_20261030.md`（`## §76 `）⇒ 正文只留摘要。
- 🔴 **`overlap_ratio_max` 是惰性参数（never fires）**：`p_dom` 只取 powerset **单人三类** ⇒ 行和 ≤ 1.0 ⇒ `>1.05` **恒 False** ⇒ `overlap_ratio` **恒 0.0** ⇒ 分支**永不执行**（20000 次复刻 = 0.0，反证并入重叠类 = 0.61835）⇒ **不是「已验证无影响」**。
- 🔴 **`clean_ratio` 全 None** = 内核**算了**（`:347`）但**桥接层白名单只转发 6 字段** ⇒ **`min_clean_ratio` 是生效的**（**不要**读成「没生效」）。
- 🔴 **`spk_conf` = 与已有簇心的最大余弦相似度** ⇒ **低 = 新人**，**不是标签可信度**（首个簇直接返回 1.0）。
- 🔴 **登记用 `clean_ranges` 子区间** ⇒ **换人边界段可能混入上一人**；`is_new_spk` = 「与上一段不同」（基线 **29** 次 vs 换人点 **26** ⇒ 3 次误触发）。
- 🔴 **`spk` ID = 到达序编号** ⇒ 跨臂/跨会话**不可直接比**。
- ✅ **第 3 点 (d)**：「≥1.5 s 取样、攒到 3 s 重算」**已经在用** clean 累计时长 ⇒ **无需再改**。


### §77 ASR-049 / ASR-050 落地：单页 App 说明 ＋ `min_clean_ratio` 默认值 0.8→0.6（三处一致）＋ 900 s 回归 ＋ 污染比例量化 ＋ 交接清单（2026-11-06 08:15–09:45）

> 🔴 **明细** `status/asr/notes/asr_for_app_spk_enroll.md`（**ASR-049 ① ② 单页**，33 行）＋ `status/asr/notes/asr_for_app_asr050_handoff.md`（**ASR-050 ③ 交接清单**）＋ 产物 `asr122` / `asr123` / `asr124`。
- ✅ **ASR-049 ①（篇幅）**：**另写**了 ≤1 页（**33 行**，要求 ≤40 行）说明 `status/asr/notes/asr_for_app_spk_enroll.md`；长文 `asr_s76.md`（241 行）**保留作明细**，未被替换。
- ✅ **ASR-049 ②（直接回答 APP-071）**：单页说明**开头 3 行问答**写死 —— (i) `spk_conf=0.129` = **与已登记者的最大余弦相似度**，**低 = 新人的正常表现**，**不构成「该段音频不能用」的依据**；(ii) 能否登记**只看三件事**：clean 累计时长 ≥ **1.5 s**、该段**是否跨换人点**、overlap 帧是否在 `clean_ranges` 里（**当前无法判**，因 overlap 参数惰性）；(iii) **ASR 明确推荐方案 B**（等**第二段**再登记 ＋ 只取**最靠后**的 clean 区间），**保留 App 的 `REG_CONF_MIN` / 干净连续 ≥2.5 s**，理由：边界段的 clean 区间**结构上无法排除上一人** ⇒ 污染比例由原方案降到改进值；**最终由 App 决定**。
- ✅ **ASR-049 ③（量化「换人边界段混入上一人」）**：产物 `asr125_spk_enroll_contamination_v2.json`（**重跑取真实 `clean_ranges`** —— `asr118` 只存了 `n_clean_ranges` 计数、**没存区间坐标**）。🔴 **口径澄清（与纠偏原文有出入，如实记录）**：纠偏写「**AMI RTTM** 真值」，但**实测**本评测集 3 个 clip **全部来自 `260902_SPE_audio.wav`** ⇒ **AMI RTTM 不覆盖本评测集** ⇒ 改用**覆盖本评测集**的真值：**主口径** = 评测集自带 **ASR-028 人工核对** `ref_segments`；**交叉核对** = `pya_ref_diar_speqa38.rttm`（pyannote 3.1 **伪真值**）。
  - **原方案（A：首次登记段取全部 `clean_ranges`）**：**0.0**（**N = 0.0 s / 分母 22.545 s**），段级比例 **0.0**（**0 / 9** 段）
  - **改进（B：只取时间上最靠后的 clean 区间）**：**0.0**（**N = 0.0 s / 分母 27.511 s**），段级比例 **0.0**（**0 / 11** 段）
  - **改进（C：等第二段再登记）**：**0.0**（**N = 0.0 s / 分母 27.545 s**），段级比例 **0.0**（**0 / 11** 段）
  - 🔴 **中性守卫**：猴补丁**只多记 `clean_ranges`**、判定逐段未变 ⇒ 与 `asr118` 的 `A_baseline` 臂**逐段一致**（`n_same=136/136`、`n_diff=0`、`identical=true`）；捕获生效（**124/136** 行有真实坐标、共 **128** 个区间）；全程持锁（探针 **319** 次、stolen **0**、`timing_valid=true`）。
- 🔴🔴🔴 **「污染 = 0」的必要限定（不可外推到生产）**：产物 `asr126_contam_zero_recheck.json`（**纯离线复核**，不跑推理）证明 **0 是真 0、不是判据恒不触发**：① **注入反证** —— 把某登记段的 `clean_ranges` **人为平移进**真值上一说话人区间 ⇒ 比例变成 **1.0**；把 prev 区间**清空** ⇒ 比例变成 **0.0** ⇒ **计算链路有鉴别力**；② **更严口径**（「**段本身跨换人点**」的所有段）测得**跨换人点的段数 = 0**；③ **结构性解释**：**9/9** 个首次登记段的起点**恰好等于**真值上一说话人区间的终点 ⇒ **切段点正好落在换人点上** ⇒ 该段 clean 区间**天然**全属新人 ⇒ **0 是结构性必然**。🔴 **但根因是评测集口径**：asr111 的切段**用参照段的人工段界**（`ref_segments` **每段 1 个 spk**）⇒ **生产环境由静音规则切段（最短 6 s）、段边界常落在换人点内侧** ⇒ **生产下的真实污染比例 > 0** ⇒ 🔴 **本模块不能给出生产的污染比例** ⇒ §4 的「推荐方案 B」应按**定性结论**读（边界段结构上无法排除上一人），**不按 0 读**。
- ✅ **ASR-050 ①（「三处一致」）**：**只改 `min_clean_ratio` 一个默认值**（步长 0.64 s / VAD 关 / 5 s 窗 / `thr=0.35` / `overlap_ratio_max=0.02` / `min_dur_s=2.0` **全部未动**）。**① 代码默认值** `asr052_speaker_tracker_api.py:308` `min_clean_ratio: float = 0.6`；**② 环境变量开关的默认值** `ASR_SPK_MIN_CLEAN_RATIO` 未设/非法 ⇒ 退回 `DEFAULT_MIN_CLEAN_RATIO`（**:146** = `0.6`，**唯一一份默认值**，**不写第二份**）；**③ 配置说明** docstring 门槛参数表（**:279–301**）。取值优先级 = 显式非默认值 → env → `DEFAULT_MIN_CLEAN_RATIO`。🔴 **跨模块陷阱（已规避）**：App 的 `app193_app053_spk_frame_audit.py` 的 `read_asr_gates()` 用**正则从 ASR 源码现读默认值**（取**第一个**匹配）⇒ 源码注释里**不能出现「`min_clean_ratio` + 数字」**的写法 ⇒ 已加「措辞纪律」注释块并**实测现读出 0.6**。
- ✅ **ASR-050 ②（回归：900 s 评测集重跑，必须与 asr118 的 0.6 臂一致）**：产物 `asr122_asr050_regression.json`（**不传 `min_clean_ratio`** ⇒ 走代码默认值）。**8 项指标全部 `match: true`**（`all_match=true`）：命中 **22/26**、recall **0.8462**、误报 **3**、无标签段 **5**、`fp_per_hour` **12.0**、`n_split_extra_ids` **8**、`n_merge_extra_people` **8**；逐 clip recall **0.8333333333333334 / 0.8571428571428571 / 0.8571428571428571**。🔴 **ASR WER 与基线一致**（主路不受影响的**机读证据**）：静态 import 图证明主路（`streaming_asr.py` / `segment_encoder_backend.py` / `seg_stream.py` / `window_encoder_backend.py`）**零说话人旁路 import**（`main_path_isolated=true` ＋ 假文件反证 `main_path_counterproof_caught=true`）⇒ 本次改动**不可能**改主路行为；5 分钟切片 `final_text` md5 `32c556292a052cabe1fcfabfd62597c7` 逐字不变 ⇒ **同一计分器下 WER 必然一致**（**WER 数值仍交 reviewer 用 MiniMax 判定**，本模块不产出 WER）。
- 🔴 **本轮抓出并修掉的 1 处判据缺陷（判据错 ⇒ 改判据，不改正确的产物）**：`asr122` 的 `identity_aligned.agreement_rate` = **0.4779**（65/136）**与同产物「逐段 136/136 一致」自相矛盾**。根因 = `identity_agreement()` 的**不对称口径**（A 臂取真值 `ref_spk`、B 臂取映射值；且 `ref_spk` 是**人工核对真值**、实测只有 **4** 个簇 vs 真值 **5** 人 ⇒ 真值编号 `S5` 在实测侧不存在 ⇒ 必然大面积 mismatch）。**修正**（产物 `asr124_identity_aligned_recheck.json`，**纯离线数值重算、不覆盖 asr122**）：**对称 `spk` 空间 + 最大权（贪心）一对一映射**（= ASR-050「按最优映射对齐」的原文口径）⇒ **asr122 vs asr118 0.6 臂 = 136/136 = 1.0**；🔴 **反证**：确定性置换 B 臂簇编号 ⇒ 一致率降到 **0.0368** ⇒ 该指标**有鉴别力**（不是恒 1 的假指标）。同时给出版本对照：**基线 vs 0.6 臂 = 97/136 = 0.7132**（逐字 ID 与对齐后相同 ⇒ 差异是**真实分段差异**、不是编号平移）。
- ✅ **ASR-050 ③（交接清单）**：`status/asr/notes/asr_for_app_asr050_handoff.md` —— 含**改了哪个文件、哪一行、md5**、**App 要同步哪些文件进 v2.3 和 MiniMVP 下一版**（实测：4 个包 `models/spk/pyannote_seg_3_0/` 下**只有 `fp16`、无 `fp16-w5`**；`asr_runtime_switches.py` / `asr_spk_window.py` **不在任何包内**；`sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 实测**只有 4 项** ⇒ 需补到 6 项）。
- ✅ **ASR-050 ④（产品后果，已写进单页说明）**：**标签多了 ≠ 这段可以拿来登记克隆音色** ⇒ 登记仍按 App 的 `REG_CONF_MIN` / 干净连续 ≥2.5 s 规则。
- 🟡 **未自行决定（按纠偏要求）**：`overlap_ratio_max` 惰性参数**是否修复**（把重叠类并入判定）＝ **新开发量** ⇒ **列待用户决定，ASR 未自行改**。
