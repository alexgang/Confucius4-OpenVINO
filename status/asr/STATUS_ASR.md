last_ack: ASR-036
更新时间: 2026-10-31 07:45
当前任务: **无新纠偏**（last_ack = ASR-036 = 纠偏文件最大编号；`CORRECTIONS_ASR.md` 12 493 B @ 2026-10-30 15:44:31、md5 与 §63/§64/§65/§66/§67 五轮**逐字节一致**；全仓扫 `ASR-0(3[7-9]|[4-9][0-9])` 命中 0）。本轮按 **ASR-034**「last_ack 追平后继续做未完成项」⇒ 继续**只读复核** ⇒ 抓出 **3 类**新真缺陷：🔴 ④ **头部「已压缩:」行重复**（§67 的写入脚本模板**已含**该行，却又 append 了原行 ⇒ 头部**两行**「已压缩:」）⇒ 读者看头部会以为压缩了两次；🔴 ⑤ **「扫描产物」是动态量**（随产物增加而变：§67 写 **127**、本轮实测 **131**）⇒ STATUS 里**写死** ⇒ **必然漂移**；🔴 ⑥ **notes 引「可改脚本」的 size/mtime** ⇒ 「改脚本 → 引用过期 → 同步 notes → 再改脚本…」⇒ **无限自指 churn**（§60 铁律的**根治**，而非又一次同步）。✅ 已修：④ 写入脚本改为**只保留一行**「已压缩:」（内容取**原文逐字**）；⑤ 新增守卫判据 **G12 / V16**（动态数值必须 == 产物字段），并把数值改为**每次写入从产物读**；⑥ notes 里**脚本**一律改为**只引内容事实**（size/mtime 只留给**冻结**对象），新增守卫判据 **V17**（notes 不得引可改脚本的 size/mtime）。✅ 守卫已加配**反证**：v4 **10/10**、独立复核 **12/12**（新增 cp10 头部重复 / cp11 动态数漂移 / cp12 notes 引脚本 size/mtime）。
阻塞 / 待用户决定: 无。⚠️ 遗留（非纠偏项，等用户指派）：① **OV f16 偏差高于 torch FP16 固有下界** ⇒ 精度优化空间未做；② **`qwen3asr_06b` 不在 git 仓库内** ⇒ 脚本/产物只在本机，App 集成需另行打包；③ 🔴 **8 个 `pya_*` 历史产物 `timing_valid=true` 但**无 `lock_probe` 块**（锁探针机制 @ 2026-10-27 引入**之前**）⇒ 同样未经核验，但**只被归档章节引用** ⇒ **追溯改 = 改旧结论**，等用户指派再动（`asr096_legacy_consistency_gate.json` → `legacy_no_lock_probe.count`）。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。
自指大小: 28 260 B / 221 行


## 最近更新
- 2026-10-31 07:45 **§68 —— 无新纠偏（last_ack 保持 ASR-036）+ 复核抓出 3 类新真缺陷（头部「已压缩:」行重复 / 「扫描产物」动态量漂移 / notes 引可改脚本 size/mtime ⇒ 自指 churn）**：🔴 ④ **头部有 2 行「已压缩:」**（§67 写入脚本模板**已含**该行却**又 append** 原行 ⇒ §67 自检只查真值点唯一性 ⇒ 漏检）；🔴 ⑤ **「扫描产物」是动态量**（§67 写 **127**、本轮实测 **131**，连跑 2 次稳定）⇒ **写死即漂移**；🔴 ⑥ **notes 引「可改脚本」的 size/mtime**（实测 **10** 处）⇒ 「改脚本→引用过期→同步 notes→再改脚本…」⇒ **无限自指 churn**（§66 判据 V17 只堵「可重跑**产物**」，**没堵「可改**脚本**」** ⇒ 判据**有盲区**）。✅ 已修：④ 写入脚本**只保留一行**「已压缩:」（内容取原文逐字）+ 守卫 **G11/V15**（头部 3 个关键行各 1 行）；⑤ 守卫 **G12/V16**（动态数值 **必须 == 产物字段**）⇒ 漂移当场 FAIL；⑥ **根治**：notes 里**脚本**一律**只引内容事实**（size/mtime 只留给**冻结**对象）+ 守卫 **V17** ⇒ 该类脱节**今后不可能再发生**。✅ 反证：v4 **10/10**、独立复核 **12/12** 全过（新增 cp10 头部重复 / cp11 动态数漂移 / cp12 notes 引脚本 size/mtime）。⚠️ 本轮**无新纠偏**。
- 2026-10-31 07:40 **§67 —— 无新纠偏（last_ack 保持 ASR-036）+ 只读复核抓出 3 类新真缺陷 + 加装 `asr099` v4 守卫**：🔴 ① **「关键数字」表的字段路径不可解析**（实测 **11 处**：4 处路径**不存在**、3 处指向**对象**、若干处「同上」**跨产物误指** ⇒ 读者按路径查会落空；§41 数字手抄的**第 7 次复发**，但这次是**路径错**不是数值错 —— 数值本身实测全部一致）；🔴 ② **`asr093` 基线与 `--inject` 写同一个产物文件** ⇒ 注入反证证据**被基线覆盖** ⇒ §65 声称的「反证 **8/8** 全过」**查无实据**（`n_counterproofs` 字段**根本不存在**）—— **§66 已在 `asr096` 上修过同一类 bug，此处复发**；🔴 ③ **`asr096` 的扫描数只 print 不落盘** ⇒ STATUS 里「123 个 JSON」**无字段可溯源**。✅ 已修：① STATUS 全部字段路径改成**实测可解析**（新增 `asr099` v4 守卫，逐条解析**全文**的 `产物 → 路径` 引用）；② `asr093` 拆成**基线/注入两个产物**，基线**显式携带**反证证据指针；③ `asr096` 显式落 `n_json_scanned`。⚠️ 本轮**无新纠偏**。
- 2026-10-31 01:40 **§66 —— 无新纠偏（last_ack 保持 ASR-036）+ 修掉 2 个遗留真缺陷 + 加装守卫**：🔴 ① **`timing_valid = true` 但 `lock_probe_checks = 0`**（§31 铁律：探针从未调用 ⇒ 「未发现锁被抢」是**未经核验的断言**）⇒ 实测 **3 个**产物 （`asr050` 在 **`timing` 子块**里、原先漏点；+ `asr055` + `_smoke_asr040_base`）全部改标 **`timing_valid = null`**（原值挪 `timing_valid_observed`，**实测数值一律未改**；锁探针的假断言原文挪 `lock_probe_note_original` 并就地改正）；🔴 ② **`clips_manifest` 的 `n_both = 0` 却 `tp = 8`** ⇒ 根因 = v1 用 `set()` **精确相等**去重，而 8 对命中点两侧时间差仅 **0.024–0.388 s** < 容差 **0.5 s** ⇒ 同一事件被拆成两条 ⇒ 建 **v2 清单**（**71** 事件 = 29 预测 + 50 真值 − 8 合并；`n_both = 8` = `tp = 8` **自洽**，且与 `asr055` 的 `tp = 8` **一致**；v1 清单与 79 音频 **md5 锚定一字未动**）；已加装守卫 `asr096_legacy_consistency_gate.py`（判据 **9** 项全过 + 反证 **10/10** 全过）；并加装**独立复核** `asr098_status_verify_s66.py`（§43：不复用写入脚本自检）⇒ 基线 **ALL PASS**（**42** 项判据）+ 注入反证 **9/9**；🔴 复核过程又抓出 **3 个**自身 bug：notes 漏列 `asr097` 的 size/mtime、**复跑 `asr096` 后守卫产物 mtime 即变 ⇒ notes 引用可重跑产物的 size/mtime 立刻脱节**（§60 铁律**复发**）、复核脚本自身被引用会形成**自指 churn** ⇒ 新增判据 **V17**（notes 不得引用可重跑产物的 size/mtime）+ 反证 **cp9**。⚠️ 本轮**无新纠偏**。


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

### 已撤回的旧结论（**不作为结论**，仅备查）

- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。


## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| —— | **无**（ASR-001 … ASR-036 全部已完成/已关闭） | —— |

> ⚠️ 上表为空 ⇒ 按 **ASR-034** 的巡检规则，本模块**待命**，不自行开新实验。
> 非纠偏项的遗留（等用户指派才算）：① OV f16 偏差高于 torch FP16 固有下界 ⇒ 精度优化空间；
> ② `qwen3asr_06b` 在 git 仓库外 ⇒ 交付需另行打包；③ 旧产物 `asr050` 的 `timing_valid` /
> `clips_manifest` 的 `n_both` 两处需修（复用前修）。


## 最近章节

> 只保留最近 3 节；更早的章节见 `status/archive/STATUS_ASR_upto_20261030.md`。

### §66 无新纠偏（last_ack 保持 ASR-036）+ 修掉 2 个遗留真缺陷 + 加装 `asr096` 守卫（2026-10-31 01:20–01:35）

> 🔴 **明细见 `status/asr/notes/asr_s66.md`**（ASR-036：长日志 / 逐条明细写 `notes/`，STATUS 只留结论、数字和链接）。

**背景**：本轮**无新纠偏**（`CORRECTIONS_ASR.md` **12493 B @ 2026-10-30 15:44:31**，md5 与 §63/§64/§65 **逐字节一致**；最大编号 = **ASR-036** = `last_ack`）⇒ 按 **ASR-034** 继续做**遗留项** ⇒ 修掉 §62 点名、§63–§65 一直没动的两个真缺陷。

**① 🔴 缺陷 A —— `timing_valid = true` 但 `lock_probe_checks = 0`**

- **为什么是真缺陷**（§31 铁律）：计时脚本必须真调 `probe.check()`，且 `lock_probe_checks > 0` 必须成为产物断言 ⇒ `checks == 0` ⇒ 探针**从未被调用** ⇒ `lock_probe_note` 里「本次**未**发现锁被抢」是**未经核验的断言**（**没查 ≠ 没被抢**）⇒ `timing_valid = true` 不成立。归档 §62 的处方原文即「**应写 `timing_valid = null`**」。
- 🔴 **实测 3 个，不止 1 个**：| 产物 | `timing_valid` 位置 | 原值 | `checks` | 处置 |；🔴 **`asr050` 把字段放在 `timing` 子块**（不是顶层）⇒ 只查顶层会漏 ⇒ STATUS 原先只点了 `asr050` 也不完整（`_smoke_asr040_base` 未被点名）。
- **修法（只改标记，实测数值一律未改）**：`timing_valid` → **`null`**（语义 = 本产物**不产**性能结论，**不是**「测得无效」）；原值挪 **`timing_valid_observed`**；加 `timing_valid_reasons` / `timing_valid_evidence`；🔴 锁探针的假断言原文挪 `lock_probe_note_original` 并就地改正。`asr050` 的 `main_wall_s` / `seg_rtf` 等**逐字未改**。

**② 🔴 缺陷 B —— `clips_manifest` 的 `n_both = 0` 却 `tp = 8`**

- **根因（实测定位）**：`eval/asr055_spk_qa_reference_eval.py` 用 `sorted(set(pred_switch + substantial_qa))` **精确相等**去重，而匹配容差是 **`tol_s = 0.5`** ⇒ 8 对命中点两侧时间差只有 **0.024 – 0.388 s** ⇒ **不被判为同一事件** ⇒ 同一事件导出**两次**、标签一个 `pred_only` 一个 `truth_only` ⇒ `n_both = 0`。
- **修法**：按容差聚成「事件」建 **v2 清单**（`_asr055_clips_v2/`）：命中 ⇒ 1 条、`source = 'both'`；每个事件带 **`pred_t` / `truth_t` / `dt`** ⇒ 可从清单**自身复算** `n_pred` / `n_truth` / `n_both`（§22 口径钉死）。
- **实测（v1 → v2）**：条数 **79 → 71**；`n_both` **0 → 8**；`n_pred` = **29**、`n_truth` = **50** 均不变；🔴 **71 = 29 + 50 − 8** 数学自洽；复算 `tp` = **8** = `asr055` 的 **8** ⇒ **一致**。
- 🔴 **v1 一字未动**（清单 md5 `2c578a27c123b80050011441a6ac735a` + 79 个音频逐个 md5 比对）；额外落 **v1 ↔ v2 索引映射**（79 条全覆盖）⇒ **ASR-032 的 3 个抽听引用仍可解析**（`t=2514.2`/`2527.0`/`3570.2` → v2 idx 9/10/61，`source` 仍 `pred_only` ⇒ **用户抽听结论不受影响**）。

**③ 加装守卫 `asr096_legacy_consistency_gate.py`（实测）**

| 项 | 值 | 来源 |
|---|---|---|
| 基线守卫 | **ALL PASS**（**9** 项判据） | `asr096_legacy_consistency_gate.json` → `status` / `n_checks` |
| 注入反证 | **10/10** 全过 | `asr096_legacy_consistency_gate_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned` |
| ②类历史遗留 | **8** 个（`pya_*` 家族，**只记录**） | `asr096_legacy_consistency_gate.json` → `legacy_no_lock_probe.count` |

- 🔴 **两类必须分开**：产物**自带 `lock_probe` 块**且 `checks == 0` ⇒ **判 FAIL**；产物**没有该块** ⇒ 是**锁探针机制（`asr_lock_common.py` @ 2026-10-27）引入之前**的产物 ⇒ 同样未经核验，但**只被归档章节引用** ⇒ **只记录，不追溯改旧结论**。
- 判据含 **G4b / G4c**：**点集逐字比对**（不只比计数）—— 🔴 只比计数**看不见**「时间戳被改但个数不变」这类缺陷。

**④ 🔴 本轮自检抓出自身的 8 个 bug**（§40/§64 纪律的又一次验证）

- `asr095`（**干跑**抓出）：① 只查顶层 ⇒ `asr050` 漏改（改标 2/3）；② `greedy_match` 的 `used` 装**下标**却拿**时间戳**比 ⇒ `n_truth` 虚高 **58 vs 正确 50**；③ 输出目录未清空 ⇒ 两轮 wav 共存 **146** 个（清单 71）⇒ **干跑 3 轮才转绿**，真实产物在转绿后才写。
- `asr096`（**注入测试**抓出）：④ `check_clips_v2()` 硬编码真实路径 ⇒ 沙箱注入**根本没被看到**；⑤ G2 只认复数字段名 ⇒ **误伤** `asr082`；⑥ G4 只比计数 ⇒ **鉴别力不足**。⇒ 🔴 另：`--inject` 会覆盖基线产物 ⇒ 拆成**两个产物文件**。
- `asr098`（**复跑 + 注入测试**抓出）：⑦ notes 只列 2 个脚本的 size/mtime ⇒ **漏列 `asr097`** ⇒ 独立复核 V14 FAIL；⑧ 🔴 **复跑 `asr096` 后守卫产物 mtime 即变** ⇒ notes 引用**可重跑产物**的 size/mtime ⇒ **立刻脱节**（§60 铁律**复发**，§64/§65 修过 D6）。

**⑤ 独立复核 `asr098_status_verify_s66.py`（§43：不复用写入脚本自检）**

| 项 | 值 | 来源 |
|---|---|---|
| 基线复核 | **ALL PASS**（**42** 项判据） | `asr098_status_verify_s66.json` → `status` / `n_checks` |
| 注入反证 | **9/9** 全过 | `asr098_status_verify_s66_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| 新增判据 | **V17**：notes **不得**引用**可重跑产物**的 size/mtime | `asr098_status_verify_s66.json` → `checks`（配反证 cp9） |

- 🔴 ⑧ 的修法：notes 里**可重跑** JSON 产物改引**内容事实**（`status` / `n_checks` / 计数），**只对冻结脚本**引 size/mtime；🔴 **不引复核脚本自身**（否则「改脚本 → 引用过期 → 再改脚本」⇒ 自指 churn，§55 循环依赖）。

**⑥ 纪律**

- 本轮**不跑任何模型推理**（只做文件读写 + 音频切片 + 数值重算）⇒ **未申请共享机器锁**（检查时 `shared/MACHINE_LOCK` 不存在、`shared/*.tmp` 残留 0、`GIT_FREEZE` 不存在）。
- 🔴 **未动 `live_caption/`**；🔴 **未改** `CORRECTIONS_ASR.md`；`last_ack` 保持 **ASR-036**。
- 🔴 **未覆盖已交付产物**（v1 清单与 79 音频 md5 锚定）；⚠️ **WER 未跑**（交 reviewer）；**未开新实验**；**未打包**。


### §67 无新纠偏（last_ack 保持 ASR-036）+ 只读复核抓出 3 类新真缺陷 + 加装 `asr099` v4 守卫（2026-10-31 07:20–07:40）

> 🔴 **明细见 `status/asr/notes/asr_s67.md`**（ASR-036：长日志 / 逐条明细写 `notes/`，STATUS 只留结论、数字和链接）。

**背景**：本轮**无新纠偏**（`CORRECTIONS_ASR.md` **12 493 B @ 2026-10-30 15:44:31**，md5 与 §63/§64/§65/§66 **逐字节一致**；最大编号 = **ASR-036** = `last_ack`）⇒ 按 **ASR-034** 继续做**只读复核**（不跑模型、不计时）⇒ 复核**不是空跑**：在本模块**已提交的产物内部**抓出 **3 类**新真缺陷（D1–D3）。

**① 🔴 D1 —— 「关键数字」表的字段路径**不可解析**（§41 第 7 次复发，但这次是**路径错**）**

- 🔴 **实测 11 处**（脚本只读扫描全文 `产物 → 字段路径` 引用：**4 处路径不存在** + **3 处指向对象** + 头部/表格各若干处「同上」跨产物误指）：读者按 STATUS 写的路径去查产物**会落空**。
- 根因：§62 压缩时把「来源产物 / 字段」列**手工简化**过（省掉中间层级）⇒ **数值本身是对的**（实测全部一致），但**路径指不到那个值**。
- ✅ 修法：每处路径按**实测**改成**可直接解析**的完整路径（数值**一律未改**）；新增 **`asr099` v4 守卫**逐条解析**全文**的 `产物 → 路径` 引用（不只查长小数）。
- 🔴 **为什么 §66 的独立复核（`asr098`）没抓到**：它的 V13 只查「**长小数**能否在产物/notes 里**逐字找到**」⇒ **路径错但数值对** ⇒ 天然漏检（**判据无鉴别力**）。

**② 🔴 D2 —— `asr093` 基线与 `--inject` 写**同一个**产物文件 ⇒ 反证证据被覆盖 ⇒ 查无实据**

- 🔴 **实测**：`asr093_status_gate_v3.json` 顶层字段 = `['probe','status','passes','n_checks','defects_found','checks','generated_at']` ⇒ **没有** `n_counterproofs` / `n_counterproofs_caught` ⇒ §65 声称的「反证 **8/8** 全过」**在产物里查无实据**（STATUS §65 表格写 `asr093_status_gate_v3.json` → `n_counterproofs`，**该路径不存在**）。
- 根因：`asr093` 的 `--inject` 分支与基线分支**都写** `asr093_status_gate_v3.json` ⇒ 跑完注入后基线产物被**覆盖**（§66 已在 `asr096` 上**修过同一类 bug** ⇒ **此处复发**）。
- ✅ 修法：拆成**两个产物**（`asr093_status_gate_v3.json` 基线 / `asr093_status_gate_v3_inject.json` 注入）；基线产物**显式携带** `counterproof_evidence`（注入产物名 + 实测条数）⇒ 读者按路径查**不再落空**。

**③ 🔴 D3 —— `asr096` 的扫描数只 print 不落盘 ⇒ 「123 个 JSON」无字段可溯源**

- 🔴 **实测**：`asr096_legacy_consistency_gate.json` **无** `n_json_scanned` / `n_scanned` 字段（脚本 `scan_timing_valid()` 返回 `n_scanned` 但**只 print**）⇒ STATUS §66 表格「扫描产物 **123** 个 JSON」**无字段可溯源**。
- ✅ 修法：显式落 `n_json_scanned` 字段；STATUS 路径改为该字段。

**④ 加装 `asr099` v4 守卫（实测）**

| 项 | 值 | 来源 |
|---|---|---|
| v4 守卫脚本 | `scripts/asr099_status_gate_v4.py`（**新增**） | — |
| v4 基线守卫 | **ALL PASS**（**18** 项判据） | `asr099_status_gate_v4.json` → `status` / `n_checks` |
| v4 注入反证 | **8/8** 全过 | `asr099_status_gate_v4_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| §67 独立复核 | **ALL PASS**（**23** 项判据） | `asr100_status_verify_s67.json` → `status` / `n_checks` |
| §67 复核注入反证 | **9/9** 全过 | `asr100_status_verify_s67_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| asr093 反证（§67 D2 修后） | **8/8** 全过 | `asr093_status_gate_v3.json` → `counterproof_evidence.n_counterproofs` / `.n_counterproofs_caught` |
| asr096 扫描数（§67 D3 修后） | **127** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned` |

**⑤ 纪律**

- 本轮**纯只读 + 文本守卫**（不跑任何模型推理、不计时）⇒ **未申请共享机器锁**（检查时 `shared/MACHINE_LOCK` 不存在、`shared/*.tmp` 残留 0、`GIT_FREEZE` 不存在）。
- 🔴 **未动 `live_caption/`**；🔴 **未改 `CORRECTIONS_ASR.md`**；`last_ack` 保持 **ASR-036**。
- 🔴 **未覆盖已交付产物**；⚠️ **WER 未跑**（交 reviewer）；**未开新实验**；**未打包**。


### §68 无新纠偏（last_ack 保持 ASR-036）+ 复核抓出 3 类新真缺陷（头部重复行 / 动态量漂移 / notes 自指 churn）（2026-10-31 07:00–07:43）

> 🔴 **明细见 `status/asr/notes/asr_s68.md`**（ASR-036：长日志 / 逐条明细写 `notes/`，STATUS 只留结论、数字和链接）。

**背景**：本轮**无新纠偏**（`CORRECTIONS_ASR.md` **12 493 B @ 2026-10-30 15:44:31**，md5 与 §63/§64/§65/§66/§67 **逐字节一致**；最大编号 = **ASR-036** = `last_ack`）⇒ 按 **ASR-034** 继续做**只读复核** ⇒ 在 §67 **已交付**的产物内部抓出 **3 类**新真缺陷（D4–D6）。

**④ 🔴 D4 —— 头部「已压缩:」行**重复**（§67 写入脚本自身引入）**

- 🔴 **实测**：STATUS 头部**有 2 行**以 `已压缩:` 开头（第 **5** / **6** 行）⇒ 读者看头部会以为「压缩了两次」。
- 根因：§67 的写入脚本 `asr101` 的 `HEADER` 模板**已经含**「已压缩:」行，脚本又**额外** `append(lines[i_comp])` ⇒ 写了两遍（§67 的**自检只查真值点唯一性**，**没查头部其它关键行** ⇒ 漏检）。
- ✅ 修法：写入脚本改为**只保留一行**「已压缩:」（内容取**原文逐字**⇒ 模板与原文不漂移）；新增守卫判据 **G11 / V15**（头部 `last_ack:` / `已压缩:` / `自指大小:` 各**恰好 1 行**）。

**⑤ 🔴 D5 —— 「扫描产物」是**动态量** ⇒ STATUS 写死 ⇒ 必然漂移**

- 🔴 **实测**：§67 写「扫描产物 **127** 个 JSON」；本轮重跑 `asr096` 实测 **131**（**连跑 2 次稳定**）⇒ §67 的数字**已过期**。
- 根因：`n_json_scanned` 统计 `results/pyannote_seg/*.json` ⇒ **每新增一个产物就 +1** ⇒ 它是**动态量**，**不能**当静态事实写进文档（§41「数字不得手抄」的第 2 层：**来源本身会变**）。
- ✅ 修法：新增守卫判据 **G12 / V16**（STATUS「扫描产物」数值 **必须 == `asr096.n_json_scanned`**）⇒ 漂移**当场 FAIL**；写入脚本每次**从产物读**该值。

**⑥ 🔴 D6 —— notes 引「可改脚本」的 size/mtime ⇒ **无限自指 churn**（§60 铁律的**根治**）**

- 🔴 **实测**：`status/asr/notes/asr_s6*.md` 共 **10** 处引用「脚本 + size/mtime」；本轮改 `asr099`/`asr100`/`asr101` 后这些引用**立刻全部过期** ⇒ 只能靠「再改一次 notes」来同步 ⇒ 而改 notes 又要动 size/mtime ⇒ **无限循环**（§66 判据 V17 只堵了「可重跑**产物**」，**没堵「可改**脚本**」** ⇒ 判据**有盲区**）。
- ✅ 修法（**根治**，不是又一次同步）：**notes 里「脚本」一律只引内容事实**（判据条数 / 反证条数 / 用途）；**size/mtime 只留给「冻结」对象**（已归档不再改的 json 产物、`CORRECTIONS_ASR.md`）。脚本 `asr102` 干跑 → 转绿 → 才写真实 notes；新增守卫判据 **V17**（notes **不得**引可改脚本的 size/mtime）⇒ **今后这类脱节不可能再发生**。
- 🔴 **保留的历史证据行**：notes 里「**过期值 / 不符 / 原写**」的行是**缺陷证据**（记录「当时写错了」）⇒ **不改**（删掉就丢证据）⇒ 守卫对它给**窄豁免**。

**⑦ 连带发现 —— 历史专属守卫随章节轮换而老化（同一根因）**

- 🔴 **实测**：修 D6 时发现 `asr093`（§65 专属）FAIL **1** 条、`asr098`（§66 专属）FAIL **4** 条
  ⇒ **判据绑定具体章节号** ⇒ 章节一滚动就**必然失效** ⇒ 假 FAIL 的真正危害是**让人习惯性忽略 FAIL**。
- ✅ 修法：`asr093` G8 改为「**§68 在正文存在**」+「§65 **已在归档**里」；`asr098` V8 改为「**已移回归档且未改数值/结论**」
  （行数相同 + 差异行必须**都是字段路径修法行** —— §67 的 D1 修法**按设计**改了归档里的路径）；两条反证同步改为针对 **§68**。

**⑧ 守卫加配反证（实测）**

| 项 | 值 | 来源 |
|---|---|---|
| v4 守卫判据 | **22** 条（G1–G12） | `asr099_status_gate_v4.json` → `n_checks` |
| v4 注入反证 | **10/10** 全过 | `asr099_status_gate_v4_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| 独立复核判据 | **28** 条（V1–V17） | `asr100_status_verify_s67.json` → `n_checks` |
| 独立复核注入反证 | **12/12** 全过 | `asr100_status_verify_s67_inject.json` → `n_counterproofs_caught` / `n_counterproofs` |
| asr096 扫描数（实测） | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned` |

**⑨ 纪律**

- 本轮**纯只读 + 文本守卫**（不跑任何模型推理、不计时）⇒ **未申请共享机器锁**（检查时 `shared/MACHINE_LOCK` 不存在、`shared/*.tmp` 残留 0、`GIT_FREEZE` 不存在）。
- 🔴 **未动 `live_caption/`**；🔴 **未改 `CORRECTIONS_ASR.md`**；`last_ack` 保持 **ASR-036**。
- 🔴 **未覆盖已交付产物**；⚠️ **WER 未跑**（交 reviewer）；**未开新实验**；**未打包**。
