last_ack: ASR-036
更新时间: 2026-10-30 16:05
当前任务: **ASR-036 已落地**（STATUS/CORRECTIONS 压缩完成）。ASR-031 … ASR-036 全部结清 ⇒ **本模块无未完成纠偏项，待命**。
阻塞 / 待用户决定: 无。⚠️ 遗留（非纠偏项）：① **OV f16 偏差高于 torch FP16 固有下界** ⇒ 精度优化空间未做（属新开实验，等用户指派）；② **`qwen3asr_06b` 不在 git 仓库内** ⇒ 脚本/产物只在本机，App 集成需另行打包；③ 旧产物的 `asr050`（`timing_valid=true` 但 `lock_probe_checks=0`）与 `clips_manifest`（`n_both=0` 却 `tp=8`）**复用前需修**。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。


## 最近更新
- 2026-10-30 16:05 **§62 补记 —— 自指大小数字修正 + 复核加固**：🔴 **抓出「STATUS 内写的自身大小与实际不符」**（生成脚本的不动点循环在占位符被替换后提前 `break` ⇒ 写入的是替换**前**的长度，偏差 34 B）⇒ 已修正为「每轮都从带占位符的模板重新计算」并重生成，现 **`os.path.getsize` == 文内数字 == 16 143 B / 145 行**；独立复核脚本新增**自指大小一致性**检查项（2 处全部 PASS）⇒ 该类缺陷今后由机器拦住，不靠人眼。
- 2026-10-30 15:45 **ASR-036 落地（§62）**：① ✅ **压缩完成** —— `STATUS_ASR.md` **614 722 B / 7 538 行 → 17 508 B / 153 行**（≤ 40 KB / ≤ 300 行）；`CORRECTIONS_ASR.md` **84 715 B → 12 493 B**（36 条 → 索引表 + 进行中 1 条全文 + 最近 4 条全文）；归档落 `status/archive/`（STATUS 全量 + 纠偏已完成条目 + 纠偏全量原文备份）；② ✅ **压缩无内容丢失**（独立复核脚本：编号并集 == 原 36 条、标题/级别/日期逐字一致、已完成条目正文逐字在归档中、标题格式不变 ⇒ reviewer 推送工具可继续追加）；③ ✅ **ASR-033 ①** 重跑 `asr079` 闸门（`passes=true`、关键字 0、越界 0、隔离自洽 true、反证 4/4）；④ ✅ **ASR-035 ②** NOTICE 占位符化（`asr085` 闸门：命中 0、反证 4/4）；⑤ 🔴 **抓出 NOTICE §11.1 的数字溯源缺陷**（表里的 8 个数字在**任何产物里都不存在** ⇒ 属 §41 第 4 次复发）⇒ 已按 `asr081` 实值改写并加字段路径；⑥ ✅ **ASR-031…035** 结论全部落 §62；⑦ ⚠️ **WER 未跑**（交 reviewer）；**未动 `live_caption/`**。
- 2026-10-30 09:45 **ASR-031（开工登记）**：收到 2 条新纠偏（ASR-031 HIGH / ASR-032 NORMAL）⇒ `last_ack` ASR-030 → ASR-031；4 项待做（限线程交付默认 / 聚类一致性重放 / RTF 增量归因 / ASR-028 结构合格）。
- 2026-10-30 01:20 **ASR-030（RESUME）接续 + ASR-025 ② 精度归因定性（§61）**：FP16 偏差 = **格式固有精度，非 IR 缺陷**（FP32 对照 rel 1.12e-06、FP16 对照 0.001432、torch FP16 固有下界 3.14e-04）；FP32 IR 过门槛（bin ×2.00、嵌入耗时 ×3.56）；抓出「相对偏差随参考侧线程数漂移」。
- 2026-10-29 23:55 **ASR-024 … ASR-029 全部落地（§60）**：base 7.8074 核 / RTF 0.6444 vs ovthreads 0.9981 核 / RTF 0.5302（≤2 核达标）；SPE Q&A 说话人切换实测（207 段 / 5 人 / 29 换人点）；`SpeakerTracker` 可 import 接口 + NOTICE。
- 2026-10-29 08:55 **§59**：把 §58 的「严格 JSON」结论推广到**全模块门禁**（532/532 合规）+ 归一 4 个非标准 JSON 产物。
- 2026-10-28 23:30 **§57**：补上参数级自检的**结构性盲区**（程序级规格）+ 量化出「余弦 ≥0.999」单独用的**鉴别力缺口**（3/7 缺陷会误判）⇒ 验收须 cos AND rel。


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
| 说话人：换人点 F1（±0.5 s / ±3.2 s） | 0.2025 / 0.6582 | 同上 → `switch_points_vs_pseudo_truth.tol_0p5s.f1` / `tol_3p2s.f1` |
| 说话人：识别人数 | 5（伪真值 6 人） | `asr055_spk_qa_reference_eval.json` → `asr_side_report.n_speakers` / `ref_meta.n_speakers` |
| 嵌入 RTF 增量（改法① 落地前 / 后） | 0.0494 / **0.0315** | `asr081_range_hi_coverage.json` → `arms.embed_dynamic.rtf_increment_vs_asr_only` / `arms.embed_range_2048.rtf_increment_vs_asr_only` |
| 嵌入墙钟（落地前 / 后） | 5.921 s / **0.551 s** | 同上 → `embed_wall_s` |
| 嵌入向量一致性（落地后 vs 动态） | 43 段逐段，cos 最小 1.0、rel 最大 0.0 | 同上 → `consistency_vs_dynamic.embed_range_2048` |
| 生产段帧数上界 | 1998 帧（= MAX_SEG_SEC 20.0 s）；落地取 EMBED_RANGE_HI **2048** | 同上 → `offline_segment_length` |
| FP16 嵌入保真（余弦 / rel） | 0.999998775537715 / 0.001432037985732332（**不过** 1e-3 门槛） | `asr060_wespeaker_precision_attrib.json` → `experiments.ov_fp16_vs_torch_fp32` |
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

### §62 ASR-031 … ASR-036 全部落地 + STATUS/CORRECTIONS 压缩（2026-10-30 09:45–15:45）

**① ASR-031 §1 —— 限线程定为交付默认（✅ 闭环）**

- 单一事实来源 `scripts/asr_thread_defaults.py`（5 个 `*_NUM_THREADS`）；`asr052_speaker_tracker_api.py` 与 `asr_speaker_tracker.py` 均 import 它。
- 机读守卫 `asr073` 用 **AST**（不是 grep）断言「限线程调用在模块级重依赖 import 之前」⇒ `all_entries_limit_before_heavy_import = true`；反证 `asr074` **6/6 全过**（基线放行 + 5 类缺陷全被抓住）。
- 同轮修掉 `asr049` 的 **Recorder.flush 缺口**（末段丢失的根因）⇒ 以后复用不会缺末段；**旧产物不改**（reviewer 已引用，两臂缺的一样不影响结论）。
- NOTICE 第 9 节已把「建议」升级为「交付默认」，并写明 RTF 表述口径（守卫 `rtf_wording_guard.no_forbidden_wording = true`）。

**② ASR-031 §2 + ASR-035 —— ASR-025 关闭：wespeaker FP16 交付（✅ 闭环）**

- `asr067` 重放（`_asr050_cache` 命中，**不重算 ASR/分段**）：FP16 IR @GPU.0 vs FP32 IR @GPU.0 ⇒ `n_diff_segments = 0`、`diff_rate = 0.0`（分母 196 段）⇒ 验收口径「不一致 ≤ 1 段」**通过**。
- 🔴 交付件未被覆盖：`shared/spe_qa_spk.json` 写前/写后 md5 一致（脚本**不走** `asr050` 的 main）。
- 结论：**FP16 即交付形态，ASR-025 关闭，不需要用户裁定**；**INT8 不值得测**（每段嵌入仅 8 ms，无收益且有精度风险）。

**③ ASR-031 §3 —— 嵌入 RTF 增量归因与改法① 落地（✅ 闭环，只记录不阻塞）**

- 归因：增量 0.0564 = seg 8.936 s + embed 7.975 s；主因是**输入 T 维动态 ⇒ GPU 插件每次重编译**（不是 FP32/CUDA，也不是线程没限）。
- 改法①（编译前给 T 设上界 `[100, 2048]`）落地到交付集合的运行时内核 ⇒ `embed_wall_s` 5.921 → **0.551 s**，`rtf_increment` 0.0494 → **0.0315**（≤ 0.05 ✅），infer p95 1.092732 → 0.00926，**向量逐段不变**（cos 最小 1.0、rel 最大 0.0）。
- 上界取 **2048** 而非 asr076 的 1000：生产段硬上限 20.0 s ⇒ 1998 帧（实测 207 段里 3 段 > 1000 帧）；落地臂 `covers_prod_upper_bound = True`。
- 新增降级原因 `embed_shape_out_of_range`（**不截断**，超界抛 ValueError ⇒ API 层降级）⇒ App 需补该 `reason` 分支。
- 验证：`asr082`（向量一致 + 超界必抛 + 反证 2/2）、`asr083`（API 降级 + 反证 3/3）。

**④ ASR-032 —— 用户抽听结论入档（✅ 闭环）**

- 用户抽听 10 个片段：标为「疑似误判」的 **04 / 05 / 07 全部识别正确** ⇒ 是**伪真值（pyannote 3.1）判错**，不是我们的错。
- 含义：伪真值算出的纯度/准确率是**偏低**估计；`spe_qa_spk.json` 的标签按现状交 TTS-031 与 App，**不用改**。
- 以后说话人验收以「伪真值 + 用户抽听的**分歧点**」为准，分歧点按用户结论覆盖伪真值后重算；**不必再找别的伪真值**。
- 漏判/判晚（06、08、09、10）属「每句一个 spk」的**粒度限制**，用户已接受，**不追**。

**⑤ ASR-033 / ASR-035 —— 交付集合源头隔离 + NOTICE 占位符化（✅ 闭环）**

- 交付给 App 的只有 **3 个文件**：`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`；评估代码移到 `eval/`（**不交付**）。
- `asr079` 闸门（**最终版本重跑**，产物时间晚于最后一次源文件改动）⇒ `passes = True`、关键字 **0**、运行时链越界 **0**、隔离 import **自洽 True**、反证 **4/4**。
- NOTICE 的示例路径与素材名已全部换成**占位符**（第 1.0 节有对照表）⇒ `asr085` 闸门：命中 **0**、反证 **4/4**。
- 🔴 **本轮抓出的新缺陷（§41 第 4 次复发）**：NOTICE §11.1 的表里 8 个数字**在任何产物里都不存在**（⇒ 属「结论写进文档 ≠ 结论落进产物」）⇒ 已按 `asr081` 实值改写，并在表里加**字段路径**以便逐字核对；旧值清单见 NOTICE 备份 `NOTICE_asr_to_app_speaker_api.md.bak_asr085`。

**⑥ ASR-034 —— 巡检规则（✅ 已遵守）**

- `last_ack` 追平后若仍有未完成项 ⇒ **继续做，不空转**；本轮正是据此把 ASR-033/035 的两处收尾做完，并执行 ASR-036。

**⑦ ASR-036 —— 压缩（✅ 闭环）**

- `STATUS_ASR.md`：**614 722 B / 7 538 行 → 17 508 B / 153 行**（≤ 40 KB / ≤ 300 行，本文）；原文移 `status/archive/STATUS_ASR_upto_20261030.md`（614 722 B，只读归档）。
- `CORRECTIONS_ASR.md`：**84 715 B → 12 493 B**（索引表 36 行 + 进行中 1 条全文 + 最近 4 条全文）；已完成条目全文移 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`，另留**全量原文备份** `CORRECTIONS_ASR_full_before_compress_20261030.md`。
- **编号与标题格式不变**（`## <前缀>-<编号> [级别] 日期 — 标题`）⇒ reviewer 的推送工具可继续往文件末尾追加。
- 独立复核：编号并集 == 原 36 条、标题/级别/日期逐字一致、已完成条目正文逐字在归档中 ⇒ **无内容丢失**。

**⑧ 压缩后的自检加固（16:05 补记）**

- 🔴 **抓出「STATUS 内写的自身大小与文件实际不符」**：压缩首版文内写 `16 177 B`，`os.path.getsize` 实测 **16 143 B**（偏差 34 B）。
- 根因：生成脚本的**不动点迭代**在占位符被替换掉之后，`cand == text` 提前 `break` ⇒ 写入的是**替换前**文本的长度，而非替换后的真实长度。
- 修正：改为「每轮都从**带占位符的模板**重新计算候选文本长度」，迭代到不动点 ⇒ 现文内数字与 `os.path.getsize` **逐字一致**。
- 加固：独立复核脚本新增**自指大小一致性**检查（正则抓 `→ N B / M 行` 逐处比对实际字节与行数，2 处全 PASS）⇒ 同类缺陷今后**由机器拦住**，不再依赖人眼。

### §61 ASR-030（RESUME）接续：ASR-025 ② 的精度归因定性（2026-10-30 01:00–01:15）

- **归因结论**：FP16 嵌入的偏差是 **FP16 格式的固有精度，不是 IR 缺陷**。
- 🔴 **归因守卫**：`asr060` 实测 FP32 臂的 `actual_precision`（GPU 插件可能对 FP32 IR 也强制 f16 ⇒ 不采信 hint）⇒ 对照组**真的跑在 FP32**。
- 三个读数：FP32 对照 rel **1.1163879303042469e-06**（≪ 1e-3） / FP16 对照 rel **0.001432037985732332**（> 1e-3） / torch FP16 固有下界 **0.0003141538654183992**。
- **出路探测**（`asr065`）：FP32 IR 过门槛，代价 bin ×2.00、嵌入中位耗时 ×3.56 ⇒ **交付形态交 reviewer/用户裁定**（后由 ASR-035 定为 FP16）。
- 🔴 **可复现性缺口**：`rel_max_abs_diff` 会随**参考侧 torch 线程数**漂移（限线程 ⇒ 0.0015126；默认 16 线程 ⇒ 0.0014320）⇒ **两个读数都 > 1e-3 ⇒ 门槛结论稳健**，但引用数字必须带口径；且**保真测量不得套用限线程环境**（限线程是生产路径优化）。
- 🔴 **抓出「脚本写好了 ≠ 脚本能跑」**：`asr047` 写了但**从未执行**（产物与 FP32 IR 目录都不存在）⇒ §60 的「已写好归因脚本」是**未经核验的断言** ⇒ 本轮重写为 `asr060` 并跑通（反证 2/2、自检 8/8）。

### §60 ASR-024 … ASR-029 全部落地（2026-10-29 20:41–23:55）

- **ASR-026/027**（持锁重跑，5 分钟切片，**每 2 s `probe.check()`**）：base **7.8074 核** / RTF 0.6444 vs ovthreads **0.9981 核** / RTF 0.5302（定稿段同为 45）⇒ **≤2 核达标，RTF 不降反升**；DLL 归因 = `libiomp5md.dll`（torch OpenMP）。
- 🔴 **更正 §40**：`gpu_engines.py` 第 78 行正则**丢 LUID** ⇒ 「ASR 走 NPU 也占集显 74–82%」**归属需重判**。
- **ASR-028**：SPE 38:00→结尾 **207 个定稿段**、**5 人**、**29 个换人点**、spk 滞后 P50 0.0159 s；伪真值 239 段 / 6 人 ⇒ 可比口径（Q&A 窗内）P 0.2759 / R 0.16 / F1 0.2025、段级纯度 0.9147 ⇒ 交付 `shared/spe_qa_spk.json`。
- **ASR-029**：`SpeakerTracker` 可 import 接口 + `shared/NOTICE_asr_to_app_speaker_api.md` + 接口自检 19/19。
- 🔴 **修掉 5 个真缺陷**：`asr053` 未调 `probe.check()` / `asr055` 读不到 `turns` 键（**指标全空却无报错**）/ `asr055` 形参类型错 / `asr055` 参照与预测**时间窗不一致** / `asr050` 写盘 import 缺失（29 分钟白跑）。
- ⚠️ **WER 未跑**（交 reviewer）；产物**均在 git 仓库外**（`qwen3asr_06b` 不在 repo 内）。
