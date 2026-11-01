last_ack: ASR-039
更新时间: 2026-11-01 16:26
当前任务: **ASR-039 已落地**（本轮**有**新纠偏 1 条：ASR-039 =「巡检会话互相重叠：每个会话开工前先拿模块租约」15:40 追加）。执行结果：① 本模块自动化指令已插入「第 0 步 `acquire` + 会话中间 `beat` + 收尾 `release`」并**回读确认生效**（`automation_update` 工具可用 ⇒ **不需用户在 UI 里手改**）；② 本会话已实际走完一轮租约（`acquire` exit 0 ⇒ TOKEN=055db860；反证：二次 `acquire` = BUSY exit 10、`beat` 错误 token = LOST exit 11）；③ 租约文件 `shared\leases\asr.json` 收尾 `release` ⇒ RELEASED（无后台作业 ⇒ 不留租约）；④ STATUS 追加 §69（含自动化指令改动 diff 全文）；⑤ 本轮**纯文档**（不跑推理、不计时）⇒ **未申请** `shared\MACHINE_LOCK`（巡检时该锁**不存在**）；**未动** `live_caption/`；**未改** `CORRECTIONS_ASR.md`（reviewer 维护）；**未覆盖已交付产物**；**未新增任何** `asr1xx` 守卫/自指审计脚本（ASR-038 ① 继续遵守）；**未开新实验**；**未打包**。
阻塞 / 待用户决定: **无待办纠偏**（ASR-001 … ASR-039 的要求已全部落地；ASR-039 的最终验收动作「reviewer 查看 `shared\leases\` 与 automation.log，确认不再出现同一模块两个会话同时 working」**属 reviewer 验收**）。⚠️ 非纠偏项遗留 **3 条，等用户指派才做** ⇒ 详见「未完成纠偏」小节。
已压缩: 原文见 `status/archive/STATUS_ASR_upto_20261030.md`；纠偏归档见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_ASR_full_before_compress_20261030.md`）。
自指大小: 17 721 B / 155 行


## 最近更新
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
| 扫描产物 | **131** 个 JSON | `asr096_legacy_consistency_gate.json` → `n_json_scanned`（**动态量**，随产物增加而变 ⇒ 数值每次从产物读） |

### 已撤回的旧结论（**不作为结论**，仅备查）

- §47 的「TTS speaker encoder 几乎无区分度 / margin 高 22× / 纯度 1.0」⇒ ASR-023 已撤回（比较口径不一致）。
- §42.1/§42.3 的「forced 的词内切点确实更好」⇒ ASR-020 已撤回（差距全来自分母）。
- §40 的「ASR 走 NPU 也占集显 74–82%」⇒ §60 更正为「需重判」（正则丢 LUID）。
- ASR-031 §2 的 `rel_max_abs_diff ≤ 1e-3` 作为 ASR-025 验收门槛 ⇒ reviewer 撤回，改按「**聚类结果一致**」。


## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| —— | **无**（ASR-001 … ASR-039 的要求已全部落地） | —— |

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

### §67 无新纠偏（last_ack 保持 ASR-036）+ 只读复核抓出 3 类新真缺陷 + 加装 `asr099` v4 守卫（2026-10-31 07:20–07:40）
> 🔴 **明细见 `status/asr/notes/asr_s67.md`**（已提交）。
- 3 类缺陷：① 「关键数字」表的**字段路径不可解析**（**11** 处）⇒ 全部改成实测可解析路径（**数值未改**）；② `asr093` 基线与 `--inject` **写同一产物** ⇒ 注入证据被基线覆盖 ⇒ 拆成基线/注入**两个产物**；③ `asr096` 扫描数只 print 不落盘 ⇒ 显式落 `n_json_scanned`。
- 守卫 `asr099` v4（**22** 项判据、反证 **10/10**）+ 独立复核 `asr100`（**28** 项判据、反证 **12/12**）。

### §68 无新纠偏（last_ack 保持 ASR-036）+ 复核抓出 3 类新真缺陷（头部重复行 / 动态量漂移 / notes 自指 churn）（2026-10-31 07:00–07:43）
> 🔴 **明细见 `status/asr/notes/asr_s68.md`**（已提交）。
- 3 类缺陷：④ 头部「已压缩:」行**重复** ⇒ 只保留 1 行；⑤ 「扫描产物」是**动态量** ⇒ 数值**每次从产物读**；⑥ notes 引**可改脚本**的 size/mtime ⇒ **无限自指 churn** ⇒ notes 里脚本一律**只引内容事实**。

### §69 ASR-039 落地：巡检会话「模块租约」（session lease）+ 本模块自动化指令改造（2026-11-01 16:17–16:26）
> 🔴 **明细见 `status/asr/notes/asr_s39.md`**（本轮新增 1 个明细文件）。
**本轮读到的新纠偏**：**ASR-039** [HIGH] 2026-11-01 15:40（`CORRECTIONS_ASR.md` mtime = 2026-11-01 15:36、size = 17 462 B，**只读未改**）；旧 `last_ack` = ASR-038 ⇒ 本轮**有**新纠偏 1 条。索引表止于 ASR-036（ASR-037/038/039 未列入）⇒ 索引表由 reviewer 维护，本模块**不改**。
**① 第 0 步租约已落地并实测（ASR-039 要求 ①②③④）**
- `acquire asr` ⇒ **exit 0**，打印 `TOKEN=055db860`；**无** `TAKEOVER`（`shared\leases\asr.json` 此前不存在）⇒ 非断点续跑。
- **反证 1**：二次 `acquire asr` ⇒ 打印 `BUSY … alive=True` ⇒ **exit 10**（另一个会话/作业还活着 ⇒ 零改动立即结束）。
- **反证 2**：`beat asr <错误 token>` ⇒ 打印 `LOST lease (已被接管或已释放) … → 立即停止，不要再改任何文件。` ⇒ **exit 11**。
- 收尾 `release asr 055db860` ⇒ **RELEASED**（本轮无后台作业 ⇒ 不留租约）。
- `addpid` 本轮**未调用**：纯文档作业，无后台长作业可登记。
- 🔴 **只引内容事实，不引 `session_lease.py` 的 size/mtime**：脚本可被 reviewer 改 ⇒ 引 size/mtime 会造成「改脚本→引用过期→同步→再改」的自指 churn（§68 ⑥ / §68-根治）⇒ 只引退出码与原始输出文本。
**② 本模块自动化指令已改造并回读确认（ASR-039 要求 ①⑤）**
- 工具能力：用 WorkBuddy 的 `automation_update`（`mode=update`）直接改本模块自动化**成功** ⇒ **不需用户在 UI 里手改**（ASR-039 要求 ⑤ 的「需用户在 UI 里改」分支**不适用**）。
- 自动化 id = `0cc12c3b-6fc1-42ad-98f3-0a1d9661d5a6`，name = **「ASR 模块纠偏定期检查」**，`rrule = FREQ=HOURLY;INTERVAL=1`，`status = ACTIVE`；改完**回读**（`mode=view`）确认新指令生效。
- ⚠️ 原指令**没有「第 0 步」**（直接从「执行步骤：1.」开始）⇒ 本轮把 `acquire` 放在**最前**，作为**新增的「第 0 步（必须最先执行）」**；原指令其余内容**一字未删**。
**改动 diff（唯一一处插入，位置 = 原「执行步骤」之前）**：
```text
第 0 步（模块租约，必须最先执行；依 ASR-039）：
python C:\Users\Trekker-PTL\shared\tools\session_lease.py acquire asr
- exit 10 (BUSY)：另一个会话或它的后台作业还活着。只输出一句「上一会话仍在进行，跳过本轮」，然后立即结束：不读其他文件，不改任何东西，不碰 MACHINE_LOCK。
- exit 0：拿到 TOKEN=xxxx，记下这个 token，后面的步骤都带上它。
- 若打印 TAKEOVER：上一会话已经死了 ⇒ 先读它留下的 note、STATUS 和产物，从断点继续，不要从头重做。
- 调用 session_lease.py 用 WorkBuddy 自带 python：C:\Users\Trekker-PTL\.workbuddy\binaries\python\versions\3.13.12\python.exe。
会话中间（每完成一步，以及每次耗时操作前后）：
python C:\Users\Trekker-PTL\shared\tools\session_lease.py beat asr <token> "<一句话进度>"
- exit 11 (LOST)：租约已被别的会话接管 ⇒ 立即停止，不再写任何文件。
长作业（打包、计时、e2e）：
- 一律用 schtasks 或 Start-Process 后台启动，拿到 PID 后马上执行：
  python C:\Users\Trekker-PTL\shared\tools\session_lease.py addpid asr <token> <pid>
- 不要在一个工具调用里同步等待超过 20 分钟，要分次轮询，轮询之间 beat。
- 只要登记的 PID 还活着，新会话就会拿到 BUSY，不会重复启动同一个作业。
本轮结束（包括「无新纠偏、跳过」的情况）的最后一步：
python C:\Users\Trekker-PTL\shared\tools\session_lease.py release asr <token>
- 如果还有后台作业活着，脚本会自动保留租约（输出 KEPT）。
```

另把原第 2 步末尾补了半句：「…然后结束（**结束前仍要 release 租约**）。」

**③ MACHINE_LOCK 规则不变（ASR-039 要求 ⑥）**

- 巡检时 `shared\MACHINE_LOCK` **不存在** ⇒ 无模块持锁；本轮**纯文档**（无推理、无计时、无打包）⇒ **不需要**机器锁。
- 租约管「同一模块不能有两个会话」，机器锁管「不同模块不要同时占用设备」⇒ 两者**都要遵守**；原「硬性纪律」段**整段保留未动**。

**④ git 纪律**

- `git fetch origin` 后 **HEAD == origin/main == `087c1cc`**（一致 ⇒ 可提交）；无 `GIT_FREEZE`。
- 只提交 `status/asr/STATUS_ASR.md` + `status/asr/notes/asr_s39.md`；`status/asr/CORRECTIONS_ASR.md`（reviewer 推的）**不提交**；`live_caption/` 下所有文件**不碰**。

**⑤ 本轮顺手修掉的一处正文重复（不改任何数值）**

- 「关键数字」表的「扫描产物」行**重复 3 次**（值与来源完全相同）⇒ 去重为 **1 行**（仍 = **131**，来源 `asr096_legacy_consistency_gate.json` → `n_json_scanned`，**动态量**，每次从产物读）。
- 「未完成纠偏」表的编号范围 `ASR-001 … ASR-037` ⇒ 订正为 `ASR-001 … ASR-039`。

**⑥ §66 已移出「最近章节」（只保留最近 3 节：§67 / §68 / §69）**

- §66 的**压缩前全文**（`## §66 ` 标题 + 完整正文）在 `status/archive/STATUS_ASR_upto_20261030.md`（ASR-036 压缩时已归档）⇒ 移出不丢内容；STATUS 里那 3 行是全文的浓缩，明细另见 `status/asr/notes/asr_s66.md`。

**⑦ 本轮未做（不自行扩范围）**

- **未**跑推理、**未**计时、**未**测速、**未**打包、**未**动 `live_caption/`、**未**改 `CORRECTIONS_ASR.md`、**未**覆盖任何已交付产物、**未**新增任何 `asr1xx` 守卫/复核脚本（ASR-038 ① 继续遵守）、**未**开新实验。
- 非纠偏遗留仍是 **3 条**（OV f16 偏差 / `qwen3asr_06b` 不在 git 内需另行打包 / `pya_*` 历史产物无 `lock_probe` 块）⇒ **等用户指派**。
