last_ack: ASR-045
更新时间: 2026-11-05 05:12
当前任务: **无新纠偏（CORRECTIONS 全文最大编号 **ASR-045** == `last_ack`）⇒ 本轮**待命**，只维护 STATUS**：① 复核 `CORRECTIONS_ASR.md` 全文 **14** 条（ASR-032…045 在文件内 + ASR-036/001…031 归档）⇒ **无编号 > ASR-045 的条目**⇒ **不执行任何纠偏、不开新实验、不跑推理/测速**（App 模块 2026-11-05 05:02:52 起持 `MACHINE_LOCK`（pid 34960）⇒ 本轮**未碰设备、未抢锁**）；② 🔴 **发现 1 处口径缺口（本模块不自行修改）**：`CORRECTIONS_ASR.md` 的**索引表只到 ASR-036**，**ASR-037…045 共 9 条有全文但索引表无行** ⇒ 与 ASR-036「每个编号一行」要求不符 ⇒ CORRECTIONS 由 **reviewer 维护且不提交** ⇒ **本模块不改不提交**，仅在此记录待 reviewer 补齐；③ ✅ **ASR-045 五项验收留痕复核通过**（log「说话人旁路窗口：5.000 s」/ 召回 **10/12**、误报 **0** / 5 s 静态 seg IR 一致性 / 4 文件 md5 清单 / NOTICE 已发）；④ ASR-042 ③ 仍为**跨模块协作项**。
阻塞 / 待用户决定: 🟡 **待 App 侧落地**（ASR 侧已就绪）：**①** 把 4 个 ASR 文件（含新增 `asr_spk_window.py`）打进包；**②** 把 **5 s 静态 seg IR** 放进 `models/spk/pyannote_seg_3_0/fp16-w5/`；**③** App 侧 `sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 追加 `asr_spk_window.py`（**必须确认 4 个文件全部到位**，否则内核算不到窗口常量 ⇒ `import` 直接失败）。⚠️ **回退路径**：`asr_spk_window.WIN_S_DEFAULT = 10.0`（或 env `ASR_SPK_WINDOW_S=10.0` / `LIVECAP_SPK_WINDOW_S=10.0`）⇒ 内核/App/IR 三处自动跟随。⚠️ 非纠偏项遗留 **3 条，等用户指派才做** ⇒ 详见「未完成纠偏」小节。🔴 **本轮新增待办（reviewer 侧）**：CORRECTIONS 索引表补 ASR-037…045 共 9 行。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。
自指大小: 22129 B / 108 行


## 最近更新
- 2026-11-05 05:12 **无新纠偏（`last_ack` 保持 **ASR-045**）⇒ 待命**：① CORRECTIONS 全文最大编号 **ASR-045** == `last_ack`（**无 ASR-046+**）⇒ 本轮**未执行任何纠偏、未开新实验、未跑推理/测速**（App 模块 05:02:52 起持 `MACHINE_LOCK`，pid 34960 ⇒ 本轮未碰设备、未抢锁）；② 🔴 **发现 1 处口径缺口**：`CORRECTIONS_ASR.md` 的**索引表只到 ASR-036**，**ASR-037…045 共 9 条有全文但索引表无行** ⇒ 与 ASR-036「每个编号一行」不符 ⇒ **CORRECTIONS 由 reviewer 维护且不提交 ⇒ 本模块不改**，记此待 reviewer 补齐；③ ✅ **ASR-045 五项验收留痕复核通过**（log「说话人旁路窗口：5.000 s」/ 召回 **10/12**、误报 **0** / 5 s 静态 seg IR 一致性数据 / 4 文件 md5 清单 / NOTICE `NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`）；④ 🟡 **ASR-042 ③ 仍为跨模块协作项**（TTS-048 已闭环：cp unroll 判 NO-GO，contended RTF 1.0577 ⇒ 到 ≤0.82 需**再降 22.5 %** ⇒ 差额归 **App 侧减争用** ⇒ 等用户决定，非 ASR 单方可完成）。
- 2026-11-04 21:32 **ASR-045 / ASR-044 / ASR-043 落地：说话人旁路窗口 5 s 的**内核**真改好（自然路径召回 10/12、误报 0）+ 评测集建成（3 段 / 15 min）+ v2.2 实为 10 s**：① 🔴 **内核不再写死 10 s** ⇒ 改为读 `scripts/asr_spk_window.py`（`WIN_S`/`WIN_N`/`N_FRAMES`/`FPS` 全部推导，import 期自洽守卫）⇒ **客户包 ASR 文件 3 → 4 个**；② 🔴 **自然路径重跑**（不 patch 任何常量）5 s 臂 **召回 10/12、误报 0**、log「说话人旁路窗口：5.0 s」⇒ **ASR-045 验收通过**；③ 🔴 **seg IR**：10 s IR 是静态 `(1,1,160000)` ⇒ **吃不了 80000** ⇒ 已另导 5 s 静态 IR（二值化一致率 1.0、帧级最大差 0.0850691647638907）⇒ 动态 IR **稳态慢 12.651 倍** ⇒ **包内放静态 5 s IR**；④ 🔴 **评测集** 3 段 / 900 s / 26 换人点 / 5 说话人（标注**只在 dev 目录**，不在任何打包路径内）；⑤ 🔴 **v2.2 实测确实跑 10 s**（内核 md5 与 ASR-040/041 自测代码逐字相同 ⇒ ASR-044 的「不一致才复测」前提不成立）；⑥ 🔴 **ASR-042** 见 §72（① ② 已落盘；③ 需 TTS 线程配合）。产物 `asr108_kernel_5s_natural_rerun.json` + `asr107_seg_ir_shape_and_consistency.json` + `asr110_seg_ir_perf.json` + `asr112_v22_actual_code.json` + `asr111_evalset_metrics.json`。
- 2026-11-02 10:25 **ASR-041 已落地：说话人旁路窗口 10 s vs 5 s 对比 ⇒ 建议切到 5 s**：① 🔴 **召回持平**（10 s 窗 **10/12**、5 s 窗 **10/12**，误报**各 0**）⇒ 满足 ASR-041 切换条件「5 s 召回 ≥ 10 s 且误报 ≤1」；② 🔴 **标签到达延迟减半**：10 s 窗 P50/P95 = **10.0003/10.0013 s** ⇒ 5 s 窗 **5.0002/5.0008 s**；③ 🔴 **每窗口耗时**（GPU.0，编译一次、多次推理）：旁路分段 10 s 窗 **0.04159 s** ⇒ 5 s 窗 **0.021128 s**；嵌入 10 s/5 s 同量 **0.006476 s**（GPU.0）/ **0.024536 s**（CPU 对照）；④ 🔴 **口径先修缺陷再谈数字**：延迟口径（负数 -24.9 s，**作废**）、runtime 硬编码 `WIN_N`/`FPS`（5 s IR 抛 shape 不兼容 ⇒ 临时改常量、**交付源码零改动**）、**帧率不是窗口的一半**（58.9 vs **58.6**）；⑤ 🔴 **第一版整轮作废**（瞬间喂音 ⇒ 队列积压 ⇒ `bypass_degraded` ⇒ 召回假塌成 0/12）⇒ 改**实时喂音** + **降级守卫**；⑥ 🔴 **窗口常量单一来源** `scripts/asr_spk_window.py` 已落地（`WIN_S` 仍 10.0）。产物 `asr105_spk_window_5s_vs_10s.json` + `asr105_window_bench.json` + `asr105_verify.json`。明细 `status/asr/notes/asr_s41.md`。
- 2026-11-02 00:59 **ASR-040 收尾（STATUS 自检与压缩）**：① 🔴 **ASR-038 持续约束的处置**（该条已 ack 但从未撤销 ⇒ 持续有效）：本轮**曾**新建 `status_verify` 类脚本与产物 ⇒ **一律不作为交付物保留、不进 git、已删除**，STATUS/notes **未引用**它们 ⇒ **结论字段不依赖**它们；② 🔴 **STATUS 行数门禁**（ASR-038③ ≤160 行）：写入 §70 后曾达 **184 行** ⇒ **已压回 128 行**（§69 全文归档至 `status/archive/STATUS_ASR_upto_20261030.md` → `## §69 `，正文留 3 行摘要 + 归档指针；归档原有 7917 行**逐字未改**、§69 正文 61/61 行**逐字在归档**）；③ 🔴 **本轮两次真缺陷的教训**：写入脚本**不幂等** ⇒ 曾在已含 §70 的文件上重跑导致 §70 被追加两次（184→219 行）⇒ 已加**幂等守卫**并**从备份还原**后重跑；STATUS 里 4 个延迟数字**手抄**成了旧产物值 ⇒ 已按当前产物实测订正（`app_thr40` = **0.0194**、base = **1.4248**）并补**臂名**。明细 `status/asr/notes/asr_s40.md`。
- 2026-11-02 00:52 **ASR-040 已落地：说话人换人点召回 7/12 → 9/12（App 48 段空间），误报仍 0；改法 = `thr` 0.35→0.40（+ 可选 `min_clean_ratio` 0.8→0.4 达 12/12）**：① 🔴 **上一会话的投影守卫抓到了 3 处真口径缺陷**（off-by-one / 双重平移 / 守卫自身约定错）⇒ 本轮**先修缺陷再重跑**，23:03 的旧产物**未引用**；② **①逐点归因**（H1/H2/H3）：base 臂漏检 idx 5（H3 聚类并人）与 idx 19（H1 真值无标签 + H2 not_clean_speech）；「段太短」「首段 1.5 s」「3 s 重算」三个假设**实测否掉**；③ **②两个改法**（26 臂）：`thr` 0.40 ⇒ 11/12（误报 0）、叠加 `min_clean_ratio` 0.4 ⇒ 12/12（误报 1，唯一误报即 H1 真值点）；`min_dur_s` 1.5 无增益；④ **平台区**：thr 0.38–0.60 **9 个连续阈值全部 11/12、误报 0** ⇒ 非刀尖；⑤ **残余上限 11/12**（参照自身标签序列只能表达 11 个）；⑥ 产物 `asr104_spk_change_point_diag.json`（26 臂）+ `asr104_spk_change_point_sweep.json`（独立细扫）。明细 `status/asr/notes/asr_s40.md`。
- 2026-11-01 16:26 **ASR-039 已落地：巡检会话模块租约（session lease）+ 本模块自动化指令改造**：① 自动化指令已插入「第 0 步 acquire / 会话中间 beat / 收尾 release」并回读生效（不需用户手改）；② 本轮实测 `acquire` exit 0 → TOKEN=055db860、反证 BUSY exit 10 与 LOST exit 11、收尾 `release` ⇒ RELEASED；③ 新增 §69（含指令 diff 全文）。明细 `status/asr/notes/asr_s39.md`。
- 2026-10-31 11:03 **ASR-037 + ASR-038 已落地：停止 STATUS 自我审计循环 / 彻底停止 status_verify 类脚本**：§66–§68 全文归档（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文压到 119 行；未新增任何 `asr1xx` 守卫脚本；`asr098` 已还原为原始字节；§62 遗留的 `asr050` timing_valid / clips_manifest n_both 已在 §66 修掉并划掉。明细 `status/asr/notes/asr_s37.md`。
- 2026-10-31 07:45 **§68（无新纠偏，last_ack 保持 ASR-036）+ 复核抓出 3 类真缺陷**：④ 头部「已压缩:」行重复 ⇒ 只留 1 行；⑤ 「扫描产物」是动态量 ⇒ 数值每次从产物读；⑥ notes 引可改脚本的 size/mtime ⇒ 无限自指 churn ⇒ notes 里脚本一律只引内容事实。明细 `status/asr/notes/asr_s68.md`。
- 2026-10-31 07:40 **§67（无新纠偏，last_ack 保持 ASR-036）+ 只读复核抓出 3 类真缺陷**：① 「关键数字」表字段路径不可解析（11 处）⇒ 全部改成实测可解析路径（数值未改）；② `asr093` 基线与 `--inject` 写同一产物 ⇒ 注入证据被覆盖 ⇒ 拆成基线/注入两个产物；③ `asr096` 扫描数只 print 不落盘 ⇒ 显式落 `n_json_scanned`。明细 `status/asr/notes/asr_s67.md`。
- 2026-10-31 01:40 **§66（无新纠偏，last_ack 保持 ASR-036）+ 修掉 2 个遗留真缺陷**：① `timing_valid=true` 但 `lock_probe_checks=0` ⇒ 改标 `timing_valid=null`（原值挪 `timing_valid_observed`，实测数值未改）；② `clips_manifest` 的 `n_both=0` 却 `tp=8` ⇒ 建 v2 清单（71 事件 = 29 预测 + 50 真值 − 8 合并；v1 79 条与 79 个音频 md5 锚定未动）。明细 `status/asr/notes/asr_s66.md`；正文全文见 `status/archive/STATUS_ASR_upto_20261030.md`。

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

| 编号 | 一句话 | 状态 |
|---|---|---|
| ASR-045 | 5 s 旁路窗口内核真改 + 5 s 静态 seg IR + 交付 4 文件 + NOTICE | ✅ **已落地**（本轮 §72.①②③④） |
| ASR-043 | `WIN_S` 默认 5.0 + 锁纪律 + ack 042 | ✅ **已满足**（`WIN_S_DEFAULT` 早已 5.0；本轮补「内核真按 5 s 跑」+ 全程持锁） |
| ASR-044 | 评测集 + 双窗口指标 + 错误分析 + 每项改动 A/B + v2.2 说明 | ✅ **已落地**（本轮 §72.⑤⑥⑦；v2.2 内核 == 自测代码 ⇒ 无需复测） |
| ASR-042 | VAD 门控 / 降频 / ASR+MT+TTS 并发 TTS RTF | ✅ **① VAD 门控已落盘**（§72.⑧-1；只给数据、不改默认值）；✅ **② 降频/合并窗口已落盘**（§72.⑧-2）；🟡 **③ 第 3 步（ASR+MT+TTS 同跑对比 TTS RTF）**⇒ **需与 TTS 线程协调 + 共用 TTS-044 负载脚本** ⇒ **本模块单方无法完成** |
| ASR-036 | 压缩 STATUS 与 CORRECTIONS（索引表每个编号一行 + ≤40 KB） | 🟡 **压缩本体已完成**（STATUS ≤160 行；CORRECTIONS 25.7 KB ≤ 40 KB）；🔴 **索引表缺 ASR-037…045 共 9 行** ⇒ CORRECTIONS 由 reviewer 维护且不提交 ⇒ **待 reviewer 补齐**（本模块不改不提交） |

> 🟡 **本模块已把可独立完成的部分做完**；ASR-042 第 3 步是**跨模块协作项**，等待 TTS 线程配合。
## 最近章节

> 只保留最近 3 节；更早的章节见 `status/archive/STATUS_ASR_upto_20261030.md`。
> 🔴 **§66–§68 的全文已归档**（`status/archive/STATUS_ASR_upto_20261030.md`）⇒ 正文只留摘要；明细在 `status/asr/notes/asr_s6*.md`（**已提交**）。

### §70 ASR-040 落地：说话人换人点召回 7/12 → 9/12（误报 0）+ 两个改法（含 🔴 上一会话守卫抓出的 3 处真缺陷）（2026-11-02 00:07–00:52）
> 🔴 **明细见 `status/asr/notes/asr_s40.md`**；**全文已归档**：`status/archive/STATUS_ASR_upto_20261030.md` → `## §70 `。
- **一句话**：ASR-040 把说话人换人点召回从 7/12 提到 **9/12**（App 48 段空间），误报 **0**；给出**两个改法**（①`thr` 0.35→0.40；②叠加 `min_clean_ratio` 0.8→0.4 ⇒ **12/12**），并实测「**不增加 ASR 主路延迟**」。
- 🔴 **本轮修掉的 3 处真缺陷**：投影 `to_ref_space_switches()` 的边界约定、命中数量的 ±1 容差掩盖整体偏移、`carry` 的降级语义被当成硬判据 ⇒ 修完守卫 `ok`/`raw_ok`/`carry_ok` 全绿。
- 🔴 **残余上限 ≈ 11/12**：12 个人工换人点里，**参照自身的标签序列只能表达 11 个**。
### §71 ASR-041 落地：说话人旁路窗口 10 s vs 5 s 对比（召回持平、标签延迟减半）（2026-11-02 09:20–10:20）
> 🔴 **明细见 `status/asr/notes/asr_s41.md`**；**全文已归档**：`status/archive/STATUS_ASR_upto_20261030.md` → `## §71 `。
- **一句话**：ASR-041 实测 5 s vs 10 s 窗口 ⇒ **召回持平（各 10/12、误报各 0）**、标签到达延迟**减半**、每窗口耗时**减半**（但窗口数翻倍 ⇒ RTF 略升、总成本持平）⇒ **建议切到 5 s**。
- 🔴 **口径纪律（本轮修掉的 3 处真缺陷 + 1 处作废）**：延迟口径跨时间轴（负数 **作废**）、runtime 硬编码 `WIN_N`/`FPS`（5 s IR 抛 shape 不兼容 ⇒ 临时改常量、**交付源码零改动**）、**帧率不是窗口的一半**（58.9 vs 58.6）；**第一版整轮作废**（瞬间喂音 ⇒ 队列积压 ⇒ `bypass_degraded` ⇒ 召回假塌 0/12）⇒ 改**实时喂音** + **降级守卫**。
### §72 ASR-045 / ASR-044 / ASR-043 / ASR-042 落地：5 s 旁路窗口**内核真改**（自然路径 10/12、误报 0）+ 评测集建成 + ASR-042 ① ② 实测数据（2026-11-04 15:16–21:19）
> 🔴 **明细全文见 `status/asr/notes/asr_s72.md`**（含 asr106 / asr111 / asr113 / asr115 的**全部表格**）；**本节全文已归档**：`status/archive/STATUS_ASR_upto_20261030.md` → `## §72 `。
- **一句话**：ASR-045（BLOCKING）内核**不再写死 10 s**（改读唯一事实来源 `scripts/asr_spk_window.py`）⇒ 自然路径 5 s 臂召回 **10/12**、误报 **0**；ASR-044 评测集建成（**3 段 / 900 s / 26 换人点 / 5 说话人**）；ASR-042 ① VAD 门控（7 臂）与 ② 降频（3 臂）**只给数据、不改默认值**；ASR-043 的 `WIN_S_DEFAULT` 早已是 5.0。
- 🔴 **seg IR**：现役 10 s IR 是**静态** `(1,1,160000)` ⇒ 吃不了 80000 ⇒ 已另导 5 s 静态 IR（帧级最大差 **0.0850691647638907**、说话人活动二值化一致率 **1.0**）；动态 IR 稳态慢 **12.651** 倍 ⇒ 🔴 **撤回「包内优先用动态 IR」** ⇒ 包内放**静态 5 s IR**。
- 🔴 **ASR-042 ① VAD 门控**（`asr106_vad_gate_windows.json`，`self_check_pass`=true、锁探针 **3276**、stolen 0）：跳过占比随门限**单调递减**（5 dB ⇒ **0.4700854700854701**、30 dB ⇒ **0.014957264957264958**）；「整段被跳过」全部 **0/45** ⇒ 从未整段丢内容；🔴 本轮修掉 **3 处真缺陷**（门控方向反 / 窗口级与定稿级计数混用 / 定稿用「下一窗」能量判定）。
- 🔴 **ASR-042 ② 降频**（`asr115_chunk_size_eval.json`，`self_check_pass`=true、锁探针 **1014**、stolen 0）：1280 ms 臂 ⇒ 推理次数 **468 → 234**、推理 RTF **0.492064 → 0.304285**、墙钟相对基线 **0.618385**、首字延迟 **3.7165 s → 1.7999 s**；🔴 `final_text_len` 是**字符数不是 WER** ⇒ 交 reviewer 判定。
- 🔴 **未完成**：ASR-042 第 3 步（ASR+MT+TTS 同跑对比 TTS RTF）**需 TTS 线程配合**（同一负载脚本）⇒ **本模块单方无法完成**。