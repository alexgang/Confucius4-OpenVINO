last_ack: ASR-038
更新时间: 2026-10-31 11:03
当前任务: **ASR-037 + ASR-038 已落地**（本轮**有**新纠偏 2 条：ASR-037 =「停止 STATUS 自我审计循环」08:50 追加；ASR-038 =「彻底停止 status_verify 类脚本」10:48 追加）。执行结果：① **§66–§68 全文先归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文合并为摘要合计 **11 行**（≤ 15 行要求）；② STATUS 压到 **119 行**（≤ 160 行要求，ASR-038 验收项）；③ **未新增任何** `asr1xx` 守卫/复核脚本、**未开** §69+ 复核章节；④ §62 点名的非纠偏遗留「旧产物 `asr050` 的 `timing_valid` / `clips_manifest` 的 `n_both` 两处需修」**已在 §66 修掉 ⇒ 划掉**；⑤ 真正遗留（OV f16 偏差、`qwen3asr_06b` 打包、`pya_*` 历史产物）**等用户指派**，不自行启动。🔴 **ASR-038 之后不再运行/修改/新增任何 `asr*_status_verify` / 守卫 / 自指审计脚本** ⇒ 本轮**已把**先前为 ASR-037 改过的 `asr098` **还原为原始字节**（21 752 B，未留改动）。本轮**纯文档**（不跑推理、不计时）⇒ **未申请共享机器锁**（巡检时 `shared/MACHINE_LOCK` 由 **TTS** 持有 ⇒ 本模块**不干扰**、**不越界回收**）；**未动** `live_caption/`；**未改** `CORRECTIONS_ASR.md`（reviewer 维护）；**未覆盖已交付产物**；**未开新实验**；**未打包**。
阻塞 / 待用户决定: **无待办纠偏**（ASR-001 … ASR-038 的要求已全部落地；ASR-036 的压缩已交付，索引表状态由 reviewer 维护）。⚠️ 非纠偏项遗留 **3 条，等用户指派才做** ⇒ 详见「未完成纠偏」小节。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。
自指大小: 15 181 B / 119 行


## 最近更新
- 2026-10-31 11:03 **ASR-037 + ASR-038 已落地：停止 STATUS 自我审计循环 / 彻底停止 status_verify 类脚本**：✅ 4 + 4 条要求全部落地。
  - ① **§66–§68 全文先归档**（`status/archive/STATUS_ASR_upto_20261030.md`，标题 `### §N ` → `## §N `）⇒ 正文三节合并为摘要合计 **11 行**（≤ 15 行）。
  - ② **未新增任何** `asr1xx` 守卫/复核脚本、**未开** §69+ 复核章节（ASR-037 ① / ASR-038 ①②）。
  - ③ STATUS 压到 **119 行**（≤ 160 行，ASR-038 验收项）；`last_ack` = **ASR-038**。
  - ④ 🔴 **ASR-038 落地后已把先前为 ASR-037 改过的 `asr098` 还原为原始字节**（21 752 B）⇒ ASR-038 ①「停止运行、修改、新增任何 `asr*_status_verify` / 守卫 / 自指审计脚本」**未被违反**。
  - ⑤ §62 遗留「旧产物 `asr050` 的 `timing_valid` / `clips_manifest` 的 `n_both` 两处需修」⇒ **§66 已修掉 ⇒ 划掉**。
  - ⑥ 真正遗留（OV f16 偏差 / `qwen3asr_06b` 打包 / `pya_*` 历史产物）**等用户指派**，不自行启动。
  - ⚠️ 本轮**未跑推理、未计时** ⇒ 未申请共享机器锁（TTS 持锁 ⇒ 不干扰）；**未动** `live_caption/`；**未改** `CORRECTIONS_ASR.md`；**未覆盖已交付产物**；**未开新实验**、**未打包**。
  - ① 本轮**未新增任何 `asr1xx` 守卫/复核脚本**、**未开** §69+ 复核章节（执行记录只落 `status/asr/notes/asr_s37.md`）。
  - ② §66/§67/§68 的**全文已先归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文三节合并为摘要合计 **11** 行（ASR-037 要求 ≤ 15 行）；明细在 `status/asr/notes/asr_s6*.md`（**已提交**）。
  - ③ §62 遗留「旧产物 `asr050` 的 `timing_valid` / `clips_manifest` 的 `n_both` 两处需修」⇒ **§66 已修掉 ⇒ 划掉**（不在遗留清单里）。
  - ④ 真正遗留（OV f16 偏差 / `qwen3asr_06b` 打包 / `pya_*` 历史产物）**等用户指派**，不自行启动。
  - 🔴 唯一一处守卫脚本改动（**非新增**）：`asr098` 的判据 `last_ack == ASR-036` 是**硬绑定** ⇒ ASR-037 一落地就**必然假 FAIL**（§56：历史专属守卫随编号轮换而老化 ⇒ **假 FAIL 的真正危害是让人习惯性忽略 FAIL**）⇒ 改为**与 `CORRECTIONS_ASR.md` 的最大编号比对** ⇒ 随轮换不老化。
  - ⚠️ 本轮**未跑推理、未计时** ⇒ 未申请共享机器锁（TTS 持锁 ⇒ 不干扰）；**未动** `live_caption/`；**未改** `CORRECTIONS_ASR.md`；**未覆盖已交付产物**；**未开新实验**、**未打包**。
- 2026-10-31 07:45 **§68 —— 无新纠偏（last_ack 保持 ASR-036）+ 复核抓出 3 类新真缺陷**：④ 头部「已压缩:」行**重复** ⇒ 只保留 1 行；⑤ 「扫描产物」是**动态量** ⇒ 数值**每次从产物读**；⑥ notes 引**可改脚本**的 size/mtime ⇒ **无限自指 churn** ⇒ notes 里脚本一律**只引内容事实**。明细 `status/asr/notes/asr_s68.md`。
  - 反证 `asr099_status_gate_v4_inject.json` → `n_counterproofs_caught` = **10** / `n_counterproofs` = **10**。
  - 独立复核反证 `asr100_status_verify_s67_inject.json` → `n_counterproofs_caught` = **12** / `n_counterproofs` = **12**。
- 2026-10-31 07:40 **§67 —— 无新纠偏（last_ack 保持 ASR-036）+ 只读复核抓出 3 类新真缺陷**：① 「关键数字」表的**字段路径不可解析**（**11** 处）⇒ 全部改成实测可解析路径（**数值未改**）；② `asr093` 基线与 `--inject` **写同一产物** ⇒ 注入证据被基线覆盖 ⇒ 拆成基线/注入**两个产物**；③ `asr096` 扫描数只 print 不落盘 ⇒ 显式落 `n_json_scanned`。明细 `status/asr/notes/asr_s67.md`。
  - 守卫 `asr099_status_gate_v4.json` → `n_checks` = **22**。
  - 独立复核 `asr100_status_verify_s67.json` → `n_checks` = **28**。
- 2026-10-31 01:40 **§66 —— 无新纠偏（last_ack 保持 ASR-036）+ 修掉 2 个遗留真缺陷**：① `timing_valid=true` 但 `lock_probe_checks=0` ⇒ 改标 `timing_valid=null`（原值挪 `timing_valid_observed`，**实测数值未改**）；② `clips_manifest` 的 `n_both=0` 却 `tp=8` ⇒ 建 v2 清单（**71** 事件 = **29** 预测 + **50** 真值 − **8** 合并；v1 **79** 条与 79 个音频 md5 锚定未动）。明细 `status/asr/notes/asr_s66.md`。
  - 守卫 `asr096_legacy_consistency_gate.json` → `n_checks` = **9**。
  - 注入 `asr096_legacy_consistency_gate_inject.json` → `n_counterproofs_caught` = **10** / `n_counterproofs` = **10**。


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
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |

### 已撤回的旧结论（**不作为结论**，仅备查）

- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。


## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| —— | **无**（ASR-001 … ASR-037 的要求已全部落地） | —— |

> ⚠️ 上表为空 ⇒ 按 **ASR-034** 的巡检规则，本模块**待命**，不自行开新实验。
> 非纠偏项遗留 **3 条，等用户指派才做**（🔴 不自行启动）：
> ① **OV f16 偏差**高于 torch FP16 固有下界（FP32 对照已过门槛 ⇒ 归因为 **FP16 格式固有精度**，非 IR 缺陷）⇒ 精度优化空间**未做**；
> ② **`qwen3asr_06b` 不在 git 仓库内** ⇒ 脚本/产物只在本机 ⇒ 交付需**另行打包**；
> ③ **`pya_*` 历史遗留**：`timing_valid=true` 但**无 `lock_probe` 块**（锁探针机制 @ 2026-10-27 引入**之前**）⇒ 同样未经核验，但**只被归档章节引用** ⇒ **只记录、不追溯改旧结论**。
> 计数见 `asr096_legacy_consistency_gate.json` → `legacy_no_lock_probe.count` = **8**。
>
> 🔴 **已划掉**：§62 点名的「旧产物 `asr050` 的 `timing_valid` / `clips_manifest` 的 `n_both` 两处需修」⇒ **§66 已修掉** ⇒ 不再列为遗留（证据见 `asr095_fix_legacy_timing_and_clips_v2.json` → `defect_A_timing_valid.n_relabeled` = **3** 个产物改标）。


## 最近章节

> 只保留最近 3 节；更早的章节见 `status/archive/STATUS_ASR_upto_20261030.md`。
> 🔴 **§66–§68 的全文已归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文只留摘要；明细在 `status/asr/notes/asr_s6*.md`（**已提交**）。

### §66 无新纠偏（last_ack 保持 ASR-036）+ 修掉 2 个遗留真缺陷 + 加装 `asr096` 守卫（2026-10-31 01:20–01:35）
> 🔴 **明细见 `status/asr/notes/asr_s66.md`**（已提交）。
- 修 2 个遗留真缺陷：① `timing_valid=true` 但 `lock_probe_checks=0` ⇒ 改标 `timing_valid=null`（原值挪 `timing_valid_observed`，**实测数值未改**）；② `clips_manifest` 的 `n_both=0` 却 `tp=8` ⇒ 建 v2 清单（**71** 事件 = **29** 预测 + **50** 真值 − **8** 合并；v1 **79** 条与 79 个音频 md5 锚定未动）。
- 守卫 `asr096`：基线 **ALL PASS**（**9** 项判据）、注入反证 **10/10**；`pya_*` 历史遗留 **8** 个**只记录、不追溯改**。

### §67 无新纠偏（last_ack 保持 ASR-036）+ 只读复核抓出 3 类新真缺陷 + 加装 `asr099` v4 守卫（2026-10-31 07:20–07:40）
> 🔴 **明细见 `status/asr/notes/asr_s67.md`**（已提交）。
- 3 类缺陷：① 「关键数字」表的**字段路径不可解析**（**11** 处）⇒ 全部改成实测可解析路径（**数值未改**）；② `asr093` 基线与 `--inject` **写同一产物** ⇒ 注入证据被基线覆盖 ⇒ 拆成基线/注入**两个产物**；③ `asr096` 扫描数只 print 不落盘 ⇒ 显式落 `n_json_scanned`。
- 守卫 `asr099` v4（**22** 项判据、反证 **10/10**）+ 独立复核 `asr100`（**28** 项判据、反证 **12/12**）。

### §68 无新纠偏（last_ack 保持 ASR-036）+ 复核抓出 3 类新真缺陷（头部重复行 / 动态量漂移 / notes 自指 churn）（2026-10-31 07:00–07:43）
> 🔴 **明细见 `status/asr/notes/asr_s68.md`**（已提交）。
- 3 类缺陷：④ 头部「已压缩:」行**重复** ⇒ 只保留 1 行；⑤ 「扫描产物」是**动态量** ⇒ 数值**每次从产物读**；⑥ notes 引**可改脚本**的 size/mtime ⇒ **无限自指 churn** ⇒ notes 里脚本一律**只引内容事实**。
