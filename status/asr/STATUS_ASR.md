# STATUS_ASR
last_ack: ASR-009
更新时间: 2026-10-25 16:40
当前任务: **ASR-006 §5② / §6 + ASR-007 / ASR-008 / ASR-009 已执行**。① ✅★ **「0.6B INT4 不可行」被证伪** —— `INT4_ASYM g128 + AWQ + SE`（backup INT8_ASYM，lm_head 保 FP16）**文本正常**：5 分钟切片 **882 词 vs INT8 928 词**，定长 top1 **69.44% vs INT8 70.83%**、top5 **85.71% vs 87.90%** ⇒ **INT4 在 0.6B 上可用**；② 🔴 **照搬 R2T2 的「INT4_SYM 按通道 + AWQ + SE」在 0.6B 上崩坏**（切片仅 **98 词**、定长 top1 **16.27%**）⇒ **配方必须换**，差异来自模型规模/宽度；③ ✅ **P3 INT8 61 分钟全长质量数据已落盘**（`results/p3_p3_61min_gpu_int8/`：**553 段 / 11825 词 / rule 518+34+1 / 段长 p50 6.4s p95 8.96s max 12.16s / 跑满 3671.19 s** ⇒ 满足 ASR-006 §3「跑整个 wav」）；④ ✅ **ASR-006 §2 切点重复诊断已完成**（并发会话产出）：rule1 占全部切点 **93.67%**、「切在词中间」**9.54%**、**静音内切点 0.0%** ⇒ 「重复词去重」路线天花板 **≤0.963pp**（仅覆盖 reviewer 观测的 178 个多余插入的 **≤61.8%**）⇒ **接缝去重不是主因**；⑤ ✅ **ASR-007 对比矩阵已更新**（`qwen3asr_06b/reports/compare/` **17 个文件**，新增 2 个 INT4 格子 + 更新 INT8/INT4 汇总）；⑥ ⏳ **规范锁路径持锁重跑在等锁**（`app` PID 32652 存活）
阻塞 / 待用户决定: ① 🔴 **0.6B 的 WER 全部空缺**（`wer_pct: null`）—— 本模块**不自算 WER**（ASR-002 铁律）⇒ 需 reviewer 用本机 baseline + 全局对齐复算 **INT8 / INT4_ASYM 的 61 分钟全长 WER**（对照 0.6B 流式参照 10.97%、R2T2 App 路径 B 10.58%），并裁定 **INT4 是否值得为 0.6B 做**；② ⏳ **0.6B INT8 61 分钟持锁重跑未拿到计时**（规范锁被 `app` 占用，16:23 起等待中）⇒ 交付级 RTF / 首字延迟 / 内存**仍全部作废**（现有都是 n=1 或被干扰）；③ 🔴 **0.6B 在 NPU 上仍 BLOCKED**（输出复读 prompt；`ov-dec-06b-past-int8` stateful IR 在 NPU 编译失败：`to_shape was called on a dynamic shape`）⇒ **NPU 格写明原因，不硬凑**；④ ⚠️ **「提高 rule1 静音要求」必须改代码**（`min_silence_ms=300` / `SIL_LOOKBACK_SEC=3.0` 在 `live_caption_app.py` 里硬编码、**无 env**）⇒ **属 App 模块**（ASR-003 边界），本模块只给离线指标（req≥500ms ⇒ 51.69% 的 rule1 切点不再触发）；⑤ ⚠️ **reviewer 指定的 R2T2 R2 标定点未跑**（同口径 teacher-forcing top1）；⑥ ⚠️ **P0 参照重跑未做**（P0 流式参照本身少跑 11.19 s）；⑦ ⚠️ **设备内存（iGPU/NPU）未测**（`mem_device` 均为「未匹配到设备」）；⑧ 🔴 **锁路径纪律**：只能用 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`（仓库内相对路径会让 4 模块互锁失效，见 TTS `NOTICE_tts_lock_path_20261025.md`）⇒ 本轮已新写 `scripts/p3_run_with_lock.py`（双格式写锁 / 多编码读锁 / finally 删锁）

## 最近更新
- 2026-10-25 16:40 **INT4 补测完成、「0.6B INT4 不可行」被证伪（§20）**：① ✅★ **`INT4_ASYM g128 + AWQ + SE`（backup INT8_ASYM，lm_head 保 FP16）文本正常** —— 新配方量化 `results/p2_quant_decoder_int4__asymg128.json`（15:58，2153 B，`recipe`=INT4_ASYM g128、`dst_mib`=**518.3**、`n_i4`=**392**、`ignored_scope`=lm_head ✔）；5 分钟切片（720–1020 s）**882 词 vs INT8 928 词**、定长 top1 **69.44% vs 70.83%**、top5 **85.71% vs 87.90%** ⇒ **INT4 在 0.6B 上可用**；② 🔴 **INT4_SYM 按通道（R2T2 R2 照搬）在 0.6B 上崩坏**（切片 **98 词**、定长 top1 **16.27%**、top5 **28.77%**）⇒ **照搬 R2T2 配方不成立**，差异来自模型规模/宽度；③ ✅ **P3 INT8 61 分钟全长质量数据已落盘**（`results/p3_p3_61min_gpu_int8/`，4 文件）：**553 段 / 11825 词 / rule 518+34+1 / 段长 p50 6.4s p95 8.96s max 12.16s / covered 3671.19 s 且 `complete`=true**；④ 🔴 **该次计时作废且锁路径用错**（写在仓库内 `shared/MACHINE_LOCK` ⇒ 互锁失效，TTS 已实测记录）⇒ 已回收孤儿锁 + 新写 `scripts/p3_run_with_lock.py`（只用规范路径）⇒ **规范路径持锁重跑在等 `app` 锁**；⑤ ✅ **ASR-006 §2 切点诊断完成**（并发会话，16:35）：rule1 占切点 **93.67%**、「切在词中间」**9.54%**、**静音内 0.0%**、去重收益上界 **≤0.963pp**（仅覆盖 178 个多余插入的 **≤61.8%**）⇒ **接缝去重不是主因**；⑥ ✅ **ASR-007 矩阵更新**（`reports/compare/` 17 文件，新增 2 个 INT4 格子）
- 2026-10-25 13:40 **P3 根因大反转（§19）**：① 🔴 **撤回「INT8 decoder 量化损坏」**（§18.3）—— 10 层静态比对**全部相同**（**1523 个算子实例 attrs 零差异** / 341 个 3D-4D 常量**多重集**相同 / 196 个 int8 权重重算 cos 0.999929 / 位置 id **运行时**相同 / 张量精度分布相同 / .bin 存储精度全 native）；② 🔴 **撤回「FP16 端到端必崩、INT8 正常」**（§18.3/§18.4）—— `p3_diag_surgery.json` 显示**固定 6.4s + 无 prefix** 时 **FP16 10 步全程正常英文**（`all`→` right`→` good`→` morning`→` everyone`→…），而 **INT8 反而重复退化**（`.`↔`Good`/` morning` 循环）⇒ **模型都没坏，是输入条件差异**；③ 🔴 **撤回 §18.2 的 teacher-forcing 判据**（target 序列本身 = **4824 'ь' 连续 20 次** ⇒ FP16 的 100% 是**自一致 tautology**）；④ ✅ **右对齐结论仍成立且已补证据**（`p3_diag_align.json` 左对齐两图**都给 `<|im_end|>`**；`p3_diag_pos_sem.json` 证明 IR **不是恒取 511** ⇒ 内容落点会改 logits）；⑤ 🔴 **「logits 全向量 cos」在 151936 维稀疏尖峰上不可用**（INT8 只在 margin 0.77/0.027 的 2 个位置翻转，其余 10/12 命中且 margin 很大）；⑥ ⚠️ **P3 长跑 timing_valid=false**（机器锁在启动前已被 `mt` 占用）⇒ 质量可用、计时作废
- 2026-10-25 12:12 **P3 重大发现（§18）**：① ✅ **NPU 阻塞解除**（encoder 静态化 → NPU 编译 4 IR 全过除 stateful decoder）；② ✅★ **OV decoder IR 恒取位置 511 ⇒ 必须右对齐**（左对齐产出 padding 区 logits；OV/torch 都给 `all` vs `<|im_end|>`，左右 cos −0.154）⇒ **P1 的 teacher-forcing 判据无效** ⇒ **§15.3 的 enc cos 0.978 / dec cos 0.975 / top1 100% 全部作废**；③ 🔴 **INT8 decoder 在 CPU 上与 FP16 的 logits cos ≈ 0**（CPU −0.000094 / GPU −0.139394 / NPU −0.129165）⇒ **decoder 量化损坏**（encoder 完好，cos≥0.9997）；④ 🔴 **GPU 上 FP16 decoder 反而崩**（端到端矩阵）⇒ 两个独立问题；⑤ ✅ **ASR-006 §5 第③点核实通过**（fake-quant 未误量化 tied 权重 ⇒ 旧数据有效）；⑥ **rule1 接缝去重已由 App 模块完成** ⇒ 本模块该诊断降级为可选
- 2026-10-25 09:35 **收到 ASR-006 / ASR-007**：① **ASR-004 通过可关闭**（A 10.80% / B 10.58%，Δ −0.22pp CI [−0.64,+0.20] ⇒ v1.4 不用回退）；🔴 **新发现：App 实时路径比交付基准差 2.6pp**（+2.63pp CI [+1.80,+3.41] 显著，主因 rule1 切点**切在词中间** ⇒ 前后两段重复转写该词，插入多 178 个集中在段首/段尾 3 词）⇒ **只诊断不改代码**，排在 P3 之后。② **P0 参照两处修正（根因已查明）**：`--minutes 61` 截断 ⇒ wav **真实 3671.19s**，**少跑 11.19s**（reviewer 说 6s）⇒ P3 跑整个 wav；`rtf_this_run=0.8167` 是**续跑尾部的分母只剩 30.56s** ⇒ **已删该字段**；`n_runs=1` 是**progress 只每 60 步落盘、本次只跑 3 步没更新** ⇒ **已修为运行开始锁定**。⚠️ §13.6「两份参照上限相同」被推翻（离线对流式 **+3.83pp CI [+2.94,+4.70]**）⇒ **P3 以段级流式为主参照**。③ ⚠️ **§15.4「INT4 不可行」被退回（证据不足，暂不关闭）** ⇒ 该结论**降级**，本模块**不再宣称 INT4 不可行**；新判据 = **多 token teacher-forcing top1**（≥20 个 ≥12 分钟评测段，R2T2 的 R2 同口径标定）+ GPU `INT4_ASYM g128+AWQ+SE` 5 分钟切片解码，限时 ≤2h，排在 P3 之后。④ **ASR-007 用户决定：0.6B 只作实验，不进交付** ⇒ P3 改为**出对比报告**（R2T2 INT8/INT4 × 0.6B FP16/INT8/INT4 × GPU.0/NPU/CUDA，指标=WER/延迟/内存/体积/设备摆放；json 放 `qwen3asr_06b/reports/compare/` 每格一份）
- 2026-10-25 00:05 **ASR-005 P2 收尾 + git 冻结已释放**：**`shared/GIT_FREEZE` 已删除**（21:12 时还在，本轮 00:01 实测消失 ⇒ ASR-005 的「文件存在才禁提交」禁令**自动解除**）；**本地 HEAD = `origin/main` = `6fd7806`** ⇒ 无 divergent history，**明确不做 `reset --hard`**（工作区有 4 模块 500+ 未提交改动，会摧毁在途工作）。**P2 产物 8 个 IR 全部复核在盘**（INT8 候选 enc 180 MiB + dec 721 MiB；⚠️ **命名更正**：FP16 decoder 真实目录是 `ov-dec-06b-embed-fp16`，§15 里写的 `ov-dec-06b-fp16` 不存在）。**P2 检查点正式停靠，P3 不启动**；待 reviewer ① 算三份转写 WER ② 复核 INT8 候选（§15.3）③ **裁定 INT4**（本模块结论 = 0.6B 上不可行，7 条证据链；剩 GPTQ 一条路未做）④ 认可 P0 流式口径。**P3 计时类作业需持机器锁**，当前锁 `app-pack` PID 18380 **已死**（陈旧锁，等放行后回收独占）
- 2026-10-24 21:12 **ASR-005 P2 量化完成（停在 P2 检查点）**：**INT8 可用**（`ov-encoder-06b-int8sym` 180 MiB + `ov-dec-06b-embed-int8sym` 721 MiB，**lm_head 保 FP16** ⇒ 量化后该层权重 cos **1.000000**）⇒ enc cos **0.978472** / dec cos **0.974973** / **top1 匹配 100%**，体积 1497→901 MiB（**−39.8%**），与 R2T2 自己的 INT8_SYM encoder（cos 0.993 / top1 98.75%）同量级。**INT4 在 0.6B 上不可行**：三个配方（按通道+AWQ+SE / +ratio0.8+hessian / +ratio0.5+hessian）dec cos 全为负、top1 0%。**根因链 7 条独立证据**（§15.4）：① torch 侧 fake-quant 独立复现（INT8 cos 0.9777 / INT4 **0.1138** ⇒ 与 OV 侧一致 ⇒ **不是 OV/NNCF bug**）② 逐层累积（量化 49 层 cos 0.766 → 196 层 0.114）③ 手工解包 int4 后写回 FP16 IR ⇒ **W_deq 本身 cos 0.607 就打坏模型**，而 OV-INT4 vs OV-FP16(deq) = **0.971235** ⇒ **OV 运行时反量化正确** ④ 三设备一致（CPU 0.569 / GPU 0.607 / NPU 0.599 ⇒ 与设备无关）⑤ AWQ 插入数与 R2T2 完全相同（+196 vs +197）⑥ scale 轴正确（`[out,1]`）⑦ **根因 = 0.6B 层矩阵 3072×1024 vs R2T2 6144×2048** ⇒ 每通道 15 级撑不住。**顺带发现**：encoder 是 conv 结构**无 MatMul ⇒ AWQ 静默跳过** ⇒ encoder INT4 等于无校准（不可用）⇒ encoder 保留 FP16。⚠️ `GIT_FREEZE` 仍存在 ⇒ 不 commit
- 2026-10-24 20:07 **ASR-004 完成 + ASR-005 P0 完成（停在检查点）**：① ASR-004 A/B 61 分钟逐段转写完成 ⇒ **B 的 >12s 1.12%→0.18%、最长段 17.92s→14.08s、空段 1→0**、总词数只差 35 词（−0.31%）⇒ **WER 交 reviewer**；A 组交叉校验通过（分段版 vs 单进程版 part0 内 36/36 文本逐位相同）。② ASR-005 P0 两份参照完成：离线 RTF **0.2249**（31 块/0 OOM）+ 段级流式 RTF **0.6749**（552 段）⇒ **停一次等 reviewer**。③ ASR-005 P1 提前完成：encoder/decoder 两个 FP16 IR 导出 + 端到端 teacher-forcing **enc cos 0.999999 / dec cos 0.999983 / top1 100%**（要求 0.999/99%）✅。**架构发现**：R2T2 就是 Qwen3-ASR 系列（`model_type=qwen3_asr`），与 0.6B 同构 ⇒ R2T2 导出/量化脚本可原样复用。⚠️ `GIT_FREEZE` 仍存在 ⇒ 不 commit
- 2026-10-24 15:30 **ASR-004 ① 完成并修好一处合并缺陷**：A/B 逐段转写跑完（A 538 段 / B 558 段，GPU INT8 交付配置，61 分钟全长）⇒ 发现 `asr004_ab_chunked.py::merge_group()` **漏加 part 偏移**（part 文件是分段内局部时间，合并时没平移 ⇒ 交付产物时间轴重复 16 次，`segments_A.json` 的 `A[37].start_s` 又是 `0.0`）⇒ 新写 `results/asr_diag/asr004_ab_remerge.py` **只重合并、不重跑**（推理结果未动；自检：段数 538/558 不变、rule 分布不变、段长 p50/p90/p95 不变，**只有时间轴变为全局 0→3665s**）⇒ **reviewer 请用 15:14 后的 `reports/asr004_ab/transcript_{A,B}.txt`**，旧版已备份为 `*.bak_prefix`。交叉校验：分段版 A 与单进程 A 的**前 36 段逐位相同**（切点与文本全同），分歧恰好始于 part 边界（强制 flush），全文词级相似度 0.97411（11420 vs 11403 词）
- 2026-10-24 15:30 **ASR-005 P0 离线参照已完成、段级流式参照此前漏跑**：离线 31 块 wall **823.1s** / RTF **0.2249** / 60760 字符，产物 `qwen3asr_06b/results/p0_offline/`（4 文件，mtime 12:35）；串行执行器 `run_p0_all.sh` 的日志 `logs/p0_all.log` **停在第 1 步** ⇒ 流式参照此前**只有 1 分钟冒烟产物**（`results/p0_smoke3/`）⇒ 本轮 15:12 用「长跑 python 进程本身作后台任务主体」的写法重新启动 `scripts/p0_stream_seg.py --minutes 61 --out results/p0_stream`（断点 `results/p0_stream/stream_seg_chunks.jsonl`，**持机器锁** PID 14644）
- 2026-10-24 12:25 **两条长跑并行启动**（设备不冲突：ASR-004 走 Intel GPU.0 插件、ASR-005 走 NVIDIA CUDA）：① ASR-004 ① 改**可续跑分段版**（16 段 × 240s，段末强制 flush ⇒ A/B 同分段，对比公平）；② ASR-005 P0 离线参照（31 块 × 120s，断点续跑）。**长跑被杀的根因已定位**：`run_in_background` 里再套 `nohup/&` 起的孙进程会被回收 ⇒ **必须把长跑 python 进程本身作为后台任务主体**。**已修 chunked 续跑 bug**（原判「文件非空即已完成」会静默跳过被杀到一半的段，实测 `A_000.jsonl` 只到 10.24s / 应到 240s）⇒ 改为校验末条 `end_s` 是否到段末。**架构发现：R2T2 = Qwen3-ASR 系列**（`models/hf` 的 `model_type=qwen3_asr`），与 0.6B **同构**（仅宽度/层数不同）⇒ ASR-005 的 OV 导出/量化可几乎原样复用 R2T2 脚本
- 10:47 **收到 ASR-005**（用户新任务，09:13）：Qwen3-ASR-0.6B → NPU INT8/INT4，P0→P1→P2→P3，**P0 末 / P2 末各停一次等 reviewer**。已启动 P0：官方权重下载中（sha 5eb14417…）、独立 venv `qwen3asr_06b\.venv` 装 **torch 2.11.0+cu128（CUDA True）**、P0 脚本 `scripts\p0_torch_ref.py`（离线 + 640ms 流式自适应 max_new_tokens）。**流式口径**：官方流式仅 vLLM ⇒ 用 transformers 后端复刻同语义（已写入产物 `stream_note`，待 reviewer 认可）。**git 冻结**：`shared/GIT_FREEZE` 不存在 ⇒ 可提交
- 10:44 **ASR-004 ① 在跑**：61 分钟真实 Segmenter + GPU INT8 A/B 逐段转写（`reports/asr004_ab/`，脚本 `results/asr_diag/asr004_ab_transcribe.py`）；前一次 09:36 启动的进程已死无产物 ⇒ 本次重启，日志 `results/asr_diag/asr004_ab_full.log`
- 10:36 **ASR-004 ② 完成**（C-108 空段校验，61 分钟 × hang 0.8/0.6/0.5 × A/B × gain 1.0/0.3/0.1，wall 326.2s）：**gain=1.0 三档空段数 B ≤ A**（hang0.8: A 1→B 5、hang0.6: A 1→B 8、hang0.5: A 1→B 8，**绝对口径 B > A**；**相对口径 B 全部为 0 ≤ A 的 4/7/8**）。**低电平档**：gain=0.3 A 绝对空段 74~75、B 276~357（绝对口径在低电平下天然失真）；**相对口径 A 1 / B 0**。gain=0.1 相对口径 A 0 / B 0。产物 `results/asr_diag/asr004_c108_empty.json`
- 09:17 **收到 ASR-004**（reviewer 08:56）：§10 新切段规则已随 v1.4 交付（App 提交 d0c146e），但**缺 61 分钟全长质量验证** ⇒ 补 ① 61 分钟真实 Segmenter + GPU INT8 **A/B 逐段转写**（A=旧行为/B=新行为，**WER 交 reviewer 算**）② **C-108 空段校验 hang 0.8/0.6/0.5 三档 × A/B**（gain 0.3/0.1 补相对口径空段数）③ 产物写入 §12。顺带更正：§5.9 标题 12:00→**11:14**（ebc6107 实际提交时间）、开头更新时间改用**实际时钟**
- 15:05 **§11 回环补测 + 修正 §9.3 表述**：绝对判据失效的真正条件是「该段音频没有 ≥800ms 连续静音」（**素材内容决定**），不是「回环这个音源」。D1（13:24，你报告现象那段）静音帧 12.2%、≥800ms 静音**仅 1 个** ⇒ 基线 17.28s/62.5%；D2（当前播放）静音帧 34.3%、≥800ms 静音**11 个** ⇒ **基线本身 6.40s/0%**。**新判据两种素材都成立**（62.5%→6.2% / 0%→0%）⇒ 普适
## §1 交付基线（ASR-001 指定；**按 ASR-002 修正为两列口径**）

⚠️ **口径警告（ASR-002）**：8.17% / 7.95% / 0.772 **来自两套不同计分器，不能放在同一列比较**。
以后做判定时，**Δ 只和同一计分器的基线比较**。

### 1.1 目标机计分器（R4 json 用的同一套；全局对齐 + 分段配对 bootstrap）

| 指标 | 数值 | 产物 / 出处 |
|---|---|---|
| GPU INT8 参照 WER | **7.798%** | `reports/c086d_full61_all_npu_matrix.json` → `results_full61min.wer_A_pct=7.798`；同族 `reports/c089_int4/R4_npu_full_wer.json` 的 `ref_wer_pct=7.798` |
| 全 NPU INT8 cleanie WER | **7.952%** | 同上 → `results_full61min.wer_pct=7.952`、`verdict.wer_pct=7.952`、`slice_consistency_check.full61min.all_npu=7.952` |
| 全 NPU vs GPU Δ | **+0.154 pp**，`ci95=[-0.288, +0.584]`，`significant_vs_A=false` | 同上 → `results_full61min.delta_pp_vs_A=0.154` / `ci95` / `significant_vs_A` |
| 全 NPU 61 分钟 RTF | **0.7722**（`seg_rtf_p50=0.7718` / `p95=0.7942` / `max=0.8152`） | 同上 → `results_full61min.rtf=0.7722`、`seg_rtf_p50/p95/max`；`wall_s=2834.59`（47.24 min）/ `audio_sec=3671.0`（61.19 min）/ `n_segs=226` / `paired_n_segs=226` / `ref_words=11067` |
| 配方 | `enc@NPU + dec@NPU (cleanie INT8_SYM)` | 同上 → `config.name`（encoder/decoder 均 NPU） |

> 📎 **R4 INT4 配方的处置**（目标机口径，判定用）：
> `reports/c089_int4/R4_npu_full_wer.json` — `wer_pct=9.795`、`ref_wer_pct=7.798`、
> `delta_pp=1.997`、`ci95=[0.95, 3.095]`、`significantly_worse=true`、`ci_contains_zero=false`
> ⇒ **R4 INT4 在 NPU 上显著劣化，不可用**（这条结论口径一致、成立）。

### 1.2 reviewer 计分器（reviewer 本机 compare_wer.py + paired_bootstrap.py，MiniMax baseline）

| 指标 | 数值 | 出处 |
|---|---|---|
| GPU INT8（enc FP16 + dec INT8）WER | **8.17%** | reviewer 本机 `~/asr_baseline/report/data/npu.json` 与 `OV_vs_CUDA_INT4_INT8_report.md`（**产物在 reviewer 本机，不在本仓库**） |
| 全 NPU WER | **8.27%** | 同上 |
| 全 NPU vs GPU Δ | **+0.10 pp**，`[-0.41, +0.56]` | 同上 |
| 全 NPU 61 分钟 RTF | P50 **0.7722** / P95 0.7942 / max 0.8152 | 同一次全长运行，226 段（与 1.1 的目标机 RTF 数值一致） |

> ✅ **本仓库 `reports/` 下没有 reviewer 口径的 WER 产物**（`8.17` / `8.27` 搜不到），
> 按 ASR-002「找不到就如实写『产物缺失』，**不需要为此补测**」—— 此处如实标注为
> **产物在 reviewer 本机**，不是本仓库的缺失。
>
> 🔴 **修正记录（ASR-002 指出）**：本节上一版把「8.17%」的产物写成
> `reports/c089_int4/R4_npu_full_wer.json`、并把「全 NPU 7.95%」写成该 json 的
> `ref_wer_pct` —— **两处都错**：
> ① R4 json 里只有 **7.798** 这个**目标机口径的 GPU 参照**，没有 8.17；
> ② `ref_wer_pct=7.798` 是 **GPU** 参照，**不是 NPU**（NPU 是 `wer_pct=7.952`）。

## §2 最近一周的结论摘要（均引用产物）

### 2.1 切段策略（属本模块范围）
| 编号 | 结论 | 产物 |
|---|---|---|
| C-108 | 按 Qwen3-ASR-Flash-Realtime 方案改造定稿规则：规则1（段长≥MIN_SEG 且近 3s 内有 ≥300ms 静音）+ 规则2（静音超时 0.8s 优先）+ 空段守卫（须有 ≥200ms 连续语音帧高于 -35dB） | 提交 `c7d7ef1`；`runs/c108_qwen3/`（cut0.8.json / cut1.2.json / 4 个 diag_seg_qwen3_result.json） |
| C-109 | MIN_SEG_SEC 12s → **6s**（用户决策，不做 Manual 模式）：41 段 → **72 段**，段长 p50 6.40s | 提交 `63020bf`；`runs/c109_minseg6/min6.0_cut0.8.json`（min_seg=6.0, cut=0.8, guard_ms=200, wall=329.0s, 72 段） |
| C-110 | **标点触发切点不可行**，不建议实施（详见 §3） | `runs/c110_punct/`（punct_probe_12min.json / punct_value_12min.json / punct_after_hist.npy） |

### 2.2 量化 / 摆放
- R4 配方 NPU 全量：`reports/c089_int4/R4_npu_full_wer.json` — `wer_pct=9.795`，参照 `ref_wer_pct=7.798`，`delta_pp=1.997`，`ci95=[0.95, 3.095]`，`significantly_worse=true`，`ci_contains_zero=false` ⇒ **R4 INT4 在 NPU 上显著劣化，不可用**。
- 61 分钟产物目录：`reports/c058_61min/`（summary_int4lmhead_dec.json + transcript_int4lmhead_dec.txt）。

### 2.3 已知硬边界（对本模块后续所有工作有效）
| 边界 | 数值 | 出处 |
|---|---|---|
| 编码器单段上限 | `MAX_CHUNKS=24` → `MAX_FRAMES=2400` mel 帧（≈23.9s 音频） | `live_caption/segment_encoder_backend.py`；实测 P3 策略在 600s 处触发 `AssertionError: segment too long: 2432 > 2400` |
| 延迟保护期 | 绝对阈值 ∪ 相对阈值（C-105） | 提交 `322654f`；真实录音上白字提前中位 5.76s |
| `enable_hallucination_reset` | **受 C-036 用户决策约束，不得擅自打开** | — |

## §3 C-110 标点切句调研结论（已落档，供 reviewer 审查）

**问题**：能否把「标点切句机制」加入定稿机制 / 把翻译层的实现前移到切段层？

**结论：技术上可行，但实测「标点触发切点」不可行，不建议实施。**
- 判定逻辑前移 ✅ 干净可行；切点位置由标点决定 ❌ 不可行（无词级时间戳 + 标点位置 ≠ 语音结束）；标点作辅助条件 ⚠️ 机制有效但收益被 6s 门槛吃掉。

**三个反直觉发现（均有产物）**：
1. **ASR 的句末标点 ≠ 语音结束位置**。12 分钟真实演讲、1126 chunk 快照（真实 OV gpu_int8 引擎）：真句末标点 260/1126（23.1%），伪句号（缩写/小数点/版本号）**0 个**；标点处尾部静音 p50 = **0.04s**，静音 <0.3s 占 78.8%、<0.8s 占 97.3%；标点后 1 秒内「仍在讲话」时间占比 p50 = **0.54**。→ 标点是「说话人语义停顿」的产物，不是「音频静音」的产物。
2. **标点信号本身不稳定**：严格口径下句末标点跨 chunk 确认率仅 **26.2%**（260 次首现 → 68 次确认，192 次被 prefix 回退抹掉）。根因 `streaming_asr.py` 的 `rollback_punctuation=False` → `k = unfixed_token_num(5)` 恒定回退末 5 token，尾部标点处于「未定」区会被反复改写。
3. **现状切点本身就不在静音里**：2 分钟真实切点分类 —— rule2（静音超时 0.8s）2 个切点尾部静音 0.82/0.81s ✅；rule1（段长≥6s 且近 3s 内**某处**有 300ms 静音）16 个切点里 **14 个尾部静音 = 0.00s** ❌（因为规则1 只要求 lookback 窗口内**某处**有静音，不要求**末尾**有静音）。⇒ **不能拿「切点是否落在静音里」评价新规则**。

**四策略真实 ASR 对照**（12 分钟，各自独立跑真实引擎）：

| 策略 | 段数 | 段长 p50/p95 | 段尾完整句率 | 挂起词数占比 | 切在静音里 | vs 基线词级差 |
|---|---|---|---|---|---|---|
| P0 现状 | 109 | 6.40/8.30s | 56.0% | 45.5% | 22.0% | — |
| P1 标点辅助 | 105 | 6.40/9.60s | 57.1% | 43.6% | 17.1% | 丢失 40 / 多出 26 |
| P2 纯标点 | 164 | 3.90/7.70s | 53.7% | 45.8% | 17.7% | 丢失 107 / 多出 99 |
| P3 标点+静音 | 72 | 7.30/**18.15s** | 31.9% | 64.7% | 6.9% | 丢失 **416** / 多出 54 |

**标点口径（用户 2026-10-23 正式定义）**：只认 `.` `!` `?` `。` `！` `？` 为句末；`;`/`；`/冒号/引号/逗号/顿号**不算**。`translator._SENT_END = '.?!。？！；;…'` 与该口径**唯一不一致的是分号**（分句边界是既有设计，本轮未动）。

## §4 C-111 翻译层「段尾半句当段即翻」（**已实现；按 ASR-002 归属 MT + app 模块，已移交 —— 详见 §6**）

### 4.1 用户决策（本轮）
- 同意**不动切段规则**，改**翻译层**的挂起时机；
- 追加：每次定稿就执行一次翻译，完整句时再翻译一次，并修正之前的翻译错误；
- 粒度：**做法A**（按句翻，段尾半句也立刻翻）；修正范围：**只修段尾半句**。

### 4.2 实现（已落盘，未提交）
| 文件 | 改动 |
|---|---|
| `live_caption/translator.py` | `_carry`（挂起）→ `_half`（当段即翻）；`_Job.kind` 扩展 `final`/`half`/`fix`/`draft`；`submit()` 改为段尾半句当段即翻；半句闭合时**原地覆盖**重翻（用户要的「修正」）；`flush()` 只标记不再重翻 |
| `live_caption/live_caption_app.py` | GUI `_pump_tts` 与 CLI `run_cli` 的 outbox 消费：`half` 只显示不朗读，`final`/`fix` 朗读 ⇒ 同一句不念两遍 |

### 4.3 验证结果（全部落盘）
**A) 状态机（假引擎，秒级）** — `live_caption/diag_c111_half.py`，10 个用例 ALL PASS：半句当段即翻 / 整段半句 / 链上每段各留一份 / flush / 跨段整句原地修正 / TTS 不重复朗读 / 段间无越界串词 / 超长句 / 去重。

**B) 段归属对照（真实 C-109 定稿 72 段，12 分钟演讲）** — `live_caption/diag_c111_own.py`，产物 `hy_bench/runs/c111_half/c111_ownership.json`：

| 指标 | 旧机制(C-099① 挂起) | 新机制(C-111) |
|---|---|---|
| **本段原文的词在本段译文里能找到** | 1181 / 1405（**84.1%**） | 1405 / 1405（**100.0%**） |
| 缺失词数 | **224** | **0** |
| 被推迟显示的词 | 100 | **0** |
| 丢失的词 | 0 | 0 |
| 段尾半句归本段 | 3/29 | **29/29** |

### 4.4 过程中修正的三个实现缺陷（均由对照实验暴露）
1. **补全句归错段**：初版把整句归「当前段」，导致上一段的半句译文「消失」（缺失词 224→307，更差）⇒ 改为**原地覆盖**半句槽位、归属不变。
2. **半句链上的中间段为空**：段7/段8 连续两段都是半句、直到段9才闭合 ⇒ 初版把整条链的译文都归闭合段，段7/段8 的 `seg_keys` **全空**（比旧机制更糟）⇒ 改为**链上每段各留一份**（各自那部分原文作槽位）。
3. **本段首半句被粘连**：首半句没有句末标点，会和后续内容粘成一句、归属到更后面的段 ⇒ 改为首半句**单独切分、单独翻、单独归本段**（kind='half'，不朗读，因整句已由 'fix' 朗读）。

### 4.5 未完成 / 待办
- **端到端真实翻译模型验证未完成**：`diag_c111_e2e.py` 在翻译模型加载阶段退出（日志仅到「等待翻译模型加载…」，`hy_bench/runs/c111_half/e2e.log` 70 B），推测与 app 模块并行占用 GPU 有关。需**持共享机器锁**重跑，测：翻译次数增量、RTF、队列积压、段尾半句译文延迟（T3）。
- **未做 git 提交**，未同步客户包 `Confucius4_LiveCaption_v1.3`（按 APP-002，仓库与客户包是双副本，须写定点替换 sync 脚本）。
- **模块边界待裁决**：C-111 改的是 `translator.py`（翻译层）⇒ 按 ASR-001 的划分属 **MT 模块**；但它服务于 ASR 的切段输出（段-译对应）。请 reviewer 明确：留在 ASR 模块，还是移交 MT 模块？

---

## §5 C-111 收尾：bug 修复、三套验证重跑、客户包同步（2026-10-23 11:35）

### 5.1 端到端暴露的第 4 个实现缺陷（已修复并回归）
**症状**：真实翻译模型 e2e（首轮，持锁）产出 `fix` 事件 59 次，但 key 大量重复 ——
`And then the last` 9 次、`We see the benefit of that today...` 8 次、
`Like as an example, Silicon by itself` 7 次、`Who` 6 次、`So, welcome` 3 次；
追踪 job 序列看到同一个槽位被连续改写成三句不同的话：

```
fix  | So, welcome | So, welcome Welcome to our Q3 26 [REDACTED].
half | Welcome to our Q3 26 [REDACTED].
fix  | So, welcome | So, welcome Agenda topics today.   ← 已闭合的链首被再次修正
half | Agenda topics today.
```

**根因**：**半句链闭合后 `self._half` 未被清空**。本段没有产生新半句时，`self._half`
仍保留上一个已闭合的链首 ⇒ 下一段把它当成**新链头**再走一遍闭合流程 ⇒ 同一槽位被反复 fix。

**修复**（`translator.py`「本段文本分句」分支）：链已闭合而本段无新半句 ⇒ `self._half = None`。
同时简化链延长分支的 `self._half` 赋值（去掉冗余的 `chain_head_key`/`chain_head_seg`，
回到 `{'text': merged, 'key': prev_half['key'], 'seg': prev_half['seg']}`）。

### 5.2 三套验证重跑结果（全部通过）
| 验证 | 脚本 | 产物 | 结果 |
|---|---|---|---|
| 状态机 10 用例 | `live_caption/diag_c111_half.py` | stdout | **ALL PASS**（半句当段即翻 / 链上每段各留一份 / 跨段整句原地修正 / TTS 不重复朗读 / 段间无越界串词 / 超长句 / 去重 等） |
| 段归属对照（真实 C-109 定稿 72 段） | `live_caption/diag_c111_own.py` | `hy_bench/runs/c111_half/c111_ownership.json` | 覆盖率 **1405/1405 = 100%**、缺失词 **0**、推迟词 **0**、段尾半句归本段 **29/29** |
| fix-key 回归（假引擎 + 真实 72 段） | `live_caption/diag_c111_fixkey.py`（**本轮新建**） | `hy_bench/runs/c111_half/c111_fixkey.json` | fix 事件 **25 次 / 唯一 key 25 个**、事件序列全部合法（`[half]`/`[half,fix]`/`[final]`/`[fix]`）、fix 均为整句覆盖 ⇒ **§5.1 的 bug 已修好** |

**判据修正记录（两处，都是我自己的判据写错，不是实现错）**：
1. 「一个 key 只应有一个译文」是**错判据** —— `half` → `fix` 的两段历史正是 C-111 的设计意图
   （半句先占位、补全后整句覆盖）。正确判据是「终态只能有一个，且必须在序列末尾」。
2. 「fix 必须是整句」判据里我**只给 half 剥了 `ZH:` 假引擎前缀**、忘了给 fix 也剥 ⇒ 误报 25 个
   「未覆盖原半句」。修正后全部通过。

### 5.3 真实翻译模型端到端（首轮，**timing_valid=false**）
首轮 e2e 虽已跑出结果，但**当时 ASR-001 的机器锁规则尚未生效**、且与 app 模块并行占用 GPU
⇒ 按 ASR-001「数值和质量作业不需要锁，但被干扰时要把计时标记为 `timing_valid=false`」处理。
产物 `hy_bench/runs/c111_half/c111_e2e.json`：

| 指标 | 旧机制（C-099① 挂起） | 新机制（C-111） | 变化 |
|---|---|---|---|
| 翻译次数 | 126 | 196 | **+55.6%** |
| 事件构成 | `{'final':126}` | `{'half':94, 'final':43, 'fix':59}` | — |
| 总墙钟 | 44.5s | 105.3s | +136.6% |
| 段提交→译完 中位 | 0.597s | 1.537s | — |
| 段提交→译完 P95 | 1.147s | 2.355s | — |
| 段提交→译完 最大 | 1.404s | 2.658s | — |
| TTS 朗读次数 | 126 | 102 | 半句不朗读 |

**实时性判定（不积压）**：105.3s 墙钟对应 720s 音频 = **7.64x 实时**；段间隔约 10s、
每段翻译 1.31s ⇒ 翻译线程远快于段产出速度，**不会积压**。
⚠️ 该轮的 `fix` 计数含 §5.1 的 bug（重复修正）⇒ 修复后需重跑，**当前数值为修复前**。

### 5.4 e2e 脚本的加固（本轮）
`live_caption/diag_c111_e2e.py`：
- **自持机器锁**：`acquire_lock()` / `release_lock()`，锁已存在且持有者 PID 存活 ⇒ **直接退出
  （不抢、不排队、不干扰别的模块）**；PID 已不在或锁早于开机时间 ⇒ 回收后继续。
  已实测：TTS 模块持锁（PID 36608 存活）时本脚本正确拒绝运行。
- 新增 **fix key 唯一性**与**事件序列合法性**两项检查，写入 `c111_e2e.json`。
- 修正 `_pid_alive()` 的实现错误（`wintypes` 未导入 ⇒ 任何锁都会被误判为孤儿锁）。

### 5.5 客户包同步（已完成）
`live_caption/sync_c111_to_pkg.py`（**本轮新建**）—— 目标是 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`：
- `translator.py`：**整文件复制**。前置安全闸 —— 客户包旧版必须与**仓库 HEAD** 字节一致
  （实测 SHA256 `eb0417dc…` 相同）才允许覆盖，否则拒绝执行；覆盖前备份到**包外**
  `Confucius4_LiveCaption_v1.3/_backup_c111/`（**不留 `.bak` 在包内**，避免污染交付物）。
- `live_caption_app.py`：**5 处定点替换**（`clear()` 清 `seg_half`、GUI 文案、CLI 两处 outbox
  消费、CLI 落盘文案），每处 `assert` 命中恰好 1 次。
- **幂等**：重跑输出「已完成：共 0 处改动」（已在临时副本 `/tmp/pkgtest` 上验证两遍）。
- 落地后校验：客户包 `translator.py` 与仓库**字节一致**、`_carry` 已全部改为 `_half`
  （仅剩合法字段名 `seg_carry`）、C-111 标记 8 处（translator）+ 2 处（app）、两文件语法检查通过。
- **客户包代码上的行为验证**（假引擎，直接 `import` 客户包的 `translator.py`）：
  ```
  half  ZH:So welcome                ← 段尾半句当段即翻、只显示
  final ZH:Good morning everyone.
  final ZH:Let us start.
  fix   ZH:So welcome to our Q3 meeting.   ← 补全后整句原地覆盖
  half  ZH:to our Q3 meeting.
  final ZH:Then we cover AI.
  ```
  ⇒ 客户包代码里 `half` / `fix` 语义确实生效。

### 5.6 本轮新产物清单
| 产物 | 文件数 | 说明 |
|---|---|---|
| `hy_bench/runs/c111_half/c111_ownership.json` | 1 | 段归属对照（覆盖率 100%） |
| `hy_bench/runs/c111_half/c111_fixkey.json` | 1 | fix-key 回归（**本轮新建**） |
| `hy_bench/runs/c111_half/c111_e2e.json` | 1 | 真实翻译模型 e2e（**timing_valid=false**，修复前） |
| `live_caption/diag_c111_fixkey.py` | 1 | fix-key 回归脚本（**本轮新建**） |
| `live_caption/sync_c111_to_pkg.py` | 1 | 客户包同步脚本（**本轮新建**） |
| `live_caption/wait_and_run_e2e.py` | 1 | 等锁 + 自动跑 e2e 的排队脚本（**本轮新建**） |
| `status/asr/STATUS_ASR.md` | 1 | 本文件 |

### 5.7 下一步计划
1. **持共享机器锁重跑 e2e**（`python live_caption/diag_c111_e2e.py`）—— 确认修复后
   翻译次数、事件构成、`fix` key 不再重复；这次 `timing_valid=true`。
   （脚本已自带锁逻辑：锁被别的模块持有时**直接退出不抢**；孤儿锁可回收。）
   **已启动排队任务** `live_caption/wait_and_run_e2e.py`（本轮新建）：每 30s 查一次锁，
   锁释放（或变孤儿锁）就自动跑 e2e 并把日志写到 `hy_bench/runs/c111_half/e2e.log`。
   ⇒ **TTS 模块持锁期间不抢锁、不干扰**（ASR-001 规则）。
2. ~~**git 提交**（只提本线程的改动，见 §5.8 的 hunk 边界）~~ → **已完成**，见 §5.9。
3. **等 reviewer 裁决**模块边界（C-111 属 ASR 还是 MT）与「GPU INT8 8.17%」的产物路径。

### 5.9 提交（已完成，2026-10-23 11:14）
提交 `ebc6107`「C-111：翻译层『段尾半句当段即翻 + 补全后修正』」，**8 文件 +1686 / -56**：

> 📎 **时间戳更正（ASR-004 顺带更正①）**：本标题原写「2026-10-23 12:00」，
> 实际提交时间按 git 记录为 **2026-10-23 11:14:59 +0800**（`git show -s --format=%ci ebc6107`），
> 已改正。

| 文件 | 状态 | 说明 |
|---|---|---|
| `live_caption/translator.py` | M | 全部 224 增 / 48 删，逐行核对过**全部属 C-111**（删除行全是旧挂起机制 `_carry`） |
| `live_caption/live_caption_app.py` | M | **仅 C-111 的 5 处**（`clear()` 的 `seg_half.clear()`、GUI 文案、CLI 两处 outbox 消费、CLI 落盘文案）⇒ **不含任何 TTS 代码** |
| `live_caption/diag_c111_half.py` | A | 状态机 10 用例 |
| `live_caption/diag_c111_own.py` | A | 段归属对照 |
| `live_caption/diag_c111_e2e.py` | A | 真实翻译模型 e2e（含机器锁自持 + fix-key 检查） |
| `live_caption/diag_c111_fixkey.py` | A | fix-key 回归（本轮新建） |
| `live_caption/sync_c111_to_pkg.py` | A | 客户包同步（本轮新建） |
| `status/asr/STATUS_ASR.md` | A | 本模块状态文件 |

**做法**：工作区含 app/TTS 线程的未完成改动（`npu_delivery_backend.py` /
`npu_embeds_backend.py` / `pack_v13.py` / `update_manifest_v13.py` / `tts_service.py` /
`tts_worker.py` / `status/CORRECTIONS.md` + `live_caption_app.py` 的 TTS 面板 hunk），
**不能整文件提交** ⇒ 对 `live_caption_app.py` 用「HEAD 版 + C-111 的 5 处定点替换」
构造**独立可运行**的版本再 stage（`git hash-object -w` + `git update-index --cacheinfo`）。
- 关键前提：**HEAD 版 `live_caption_app.py` 里没有 `tts` 变量** ⇒ C-111 的 app 改动
  若带上 `tts.submit` 引用会造成 NameError，故必须剥离。
- 已验证 staged 版本 `py_compile` 通过（app + translator）。
- **未提交**、留给 app/TTS 线程的文件一律保持工作区原样，未做任何改动。

### 5.8 待提交内容与 hunk 边界（工作区含他人未完成改动，不能整文件提交）
| 文件 | 提交范围 |
|---|---|
| `live_caption/translator.py` | **全部**（224 增 / 48 删，逐行核对过：全部属 C-111） |
| `live_caption/live_caption_app.py` | **仅 outbox 消费相关 hunk**（`_save_text` 文案、`clear()` 的 `seg_half.clear()`、CLI 两处消费）；**排除** TTS 面板、`_cache()` 改动等属于 app/TTS 线程的 hunk |
| `status/asr/STATUS_ASR.md` | 全部（本模块） |
| `live_caption/diag_c111_{half,own,e2e,fixkey}.py` | 全部（验证脚本） |
| `live_caption/sync_c111_to_pkg.py` | 全部（客户包同步） |
| **不提交** | `npu_delivery_backend.py` / `npu_embeds_backend.py` / `pack_v13.py` / `update_manifest_v13.py` / `tts_service.py` / `tts_worker.py` / `status/CORRECTIONS.md`（均属 app / TTS 线程） |

---

## §6 ASR-002 回执：§1 口径修正 + C-111 移交 MT/app（2026-10-23 11:20）

> `last_ack: ASR-002`。本节只追加，不回头改旧章节；上一版的错误归因在 §1 的「修正记录」里点明。

### 6.1 §1 基线：改为两列口径（ASR-002 第 1 条，已执行）
- §1 已重写为 **1.1 目标机计分器** / **1.2 reviewer 计分器** 两张表。
- **目标机口径**（产物在本仓库 `reports/c086d_full61_all_npu_matrix.json`）：
  GPU INT8 参照 **7.798%**（`results_full61min.wer_A_pct`）、全 NPU INT8 cleanie **7.952%**
  （`results_full61min.wer_pct`）、Δ **+0.154 pp**（`delta_pp_vs_A`，`ci95=[-0.288,+0.584]`，
  `significant_vs_A=false`）、RTF **0.7722**（`rtf`；`seg_rtf_p50=0.7718` / `p95=0.7942` /
  `max=0.8152`；`wall_s=2834.59` / `audio_sec=3671.0` / `n_segs=226` / `paired_n_segs=226` /
  `ref_words=11067`）、配方 `config.name = enc@NPU + dec@NPU (cleanie INT8_SYM)`。
- **reviewer 口径**（产物在 reviewer 本机）：GPU INT8 **8.17%**、全 NPU **8.27%**、
  Δ **+0.10 pp** `[-0.41,+0.56]`，出自 `~/asr_baseline/report/data/npu.json` 与
  `OV_vs_CUDA_INT4_INT8_report.md`；RTF P50 0.7722 / P95 0.7942 / max 0.8152（226 段，
  与目标机数值一致）。
- **撤回上一版的两处归因错误**（ASR-002 指出，均为我方错误）：
  ① 上一版把「GPU INT8 8.17%」的产物写成 `reports/c089_int4/R4_npu_full_wer.json`
     —— **错**，该 json 里只有目标机口径的 GPU 参照 **7.798**，没有 8.17；
  ② 上一版把「全 NPU 7.95%」写成该 json 的 `ref_wer_pct` —— **错**，
     `ref_wer_pct=7.798` 是 **GPU** 参照，NPU 是 `wer_pct=7.952`。
- ✅ 遵守「**不需要为此补测**」：本仓库 `reports/` 下确实没有 reviewer 口径的 WER 产物
  （8.17 / 8.27 都搜不到），§1 如实标注其**产物在 reviewer 本机**，不写成"本仓库缺失"。
- 📌 **判定规则（已写入 §1 表头警示）**：以后做判定时，**Δ 只和同一计分器的基线比较**。

### 6.2 C-111 移交（ASR-002 第 2 条）—— 移交说明
**归属**：翻译层（`translator.py`）⇒ **MT 模块**；App 的 outbox 消费
（`live_caption_app.py`）⇒ **app 模块**；**均不属于 ASR**。
reviewer 已上报主会话协调移交；**ASR 线程自此不再推进 C-111**（§4/§5 保留原样作档案）。

**改动文件清单**
| 文件 | 归属 | 改动 |
|---|---|---|
| `live_caption/translator.py` | MT | `_carry`（挂起）→ `_half`（当段即翻）；`_Job.kind` 扩展 `final`/`half`/`fix`/`draft`；`submit()` 重写；半句闭合**原地覆盖**重翻；`flush()` 只标记不再重翻；`seg_half` 字典 |
| `live_caption/live_caption_app.py` | app | outbox 消费（`half` 只显示不朗读、`final`/`fix` 朗读 ⇒ 同一句不念两遍）；`clear()` 清 `seg_half`；文案「（半句，接续下一段）」→「（译文生成中…）」 |
| `live_caption/diag_c111_half.py` | MT | 状态机 10 用例（假引擎，秒级） |
| `live_caption/diag_c111_own.py` | MT | 段归属对照（真实 72 段） |
| `live_caption/diag_c111_fixkey.py` | MT | fix-key 回归（本轮新建） |
| `live_caption/diag_c111_e2e.py` | MT | 真实翻译模型 e2e（**已加机器锁自持**） |
| `live_caption/sync_c111_to_pkg.py` | app | 客户包同步（translator 整文件复制带 SHA256 安全闸 + app 5 处定点替换，幂等） |
| `live_caption/wait_and_run_e2e.py` | MT | 等锁自动跑 e2e 的排队脚本（**已按 ASR-002 停用并终止**） |

**两个诊断脚本怎么跑**（接手方直接可用，均**不需要 GPU、不需要模型、不需要机器锁**）
```bat
cd C:/Users/Trekker-PTL/confucius4-openvino
.venv\Scripts\python.exe live_caption\diag_c111_half.py     :: 状态机 10 用例，秒级，末尾输出 ALL PASS
.venv\Scripts\python.exe live_caption\diag_c111_own.py      :: 段归属对照，读 hy_bench\runs\c109_minseg6\min6.0_cut0.8.json
.venv\Scripts\python.exe live_caption\diag_c111_fixkey.py  :: fix-key 回归（同上输入）
```
- 共同前置：仓库 `.venv`（Python 3.12.10，含 numpy）；假引擎 = 输出 `ZH:`+原文的 `FakeTr`。
- `diag_c111_e2e.py`（真实翻译模型）**需持共享机器锁**，脚本自带
  `acquire_lock()`/`release_lock()`：锁被别的模块持有 ⇒ **直接退出不抢**；
  孤儿锁（PID 已不在 / 早于开机时间）才回收。

**产物位置**
| 产物 | 路径 | 内容 |
|---|---|---|
| 段归属对照 | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_ownership.json` | 覆盖率 100%（1405/1405）、缺失词 0、推迟词 0、段尾半句归本段 29/29 |
| fix-key 回归 | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_fixkey.json` | fix 25 次 / 唯一 key 25 个、事件序列全部合法 |
| 真实模型 e2e | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_e2e.json` | ⚠️ **`timing_valid=false`**（未持锁且与 app 模块并行占 GPU），且含 §5.1 的 bug ⇒ **修复后需重跑**才可作结论 |

**🔴 需要主会话裁决的既成事实**（ASR-002 要求「保持现状，不提交 git、不同步客户包」，
但这两件事**在 ASR-002 到达前已经发生**）：
- 已提交 3 次：`ebc6107`（C-111 主体，8 文件 +1686/−56）、`3ce0919`（§1 产物定位补记）、
  `6f05815`（客户包行为验证 + 排队脚本）。
- 已同步客户包 `C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.3/app`
  （`translator.py` 整文件复制 + `live_caption_app.py` 5 处定点替换；
  备份在**包外** `Confucius4_LiveCaption_v1.3\_backup_c111\`）。
- 请主会话裁决：保留（归入 MT/app 提交历史）／回退（`git revert` + 客户包还原）／其他。
  **ASR 线程不自行处置。**

### 6.3 C-110（ASR-002 第 3 条）
reviewer 认可「标点触发切点不实施、现状切段规则（C-108 + C-109 MIN_SEG=6s）不变」。
`rollback_punctuation=False` ⇒ 尾部 5 token 恒定回退这条发现**记录在案，不擅自改**
（会改定稿行为与 WER；如要改，需先给出 61 分钟 WER 配对 bootstrap 方案并经用户同意）。

### 6.4 ASR 本模块状态（ASR-002 第 4 条）
**待命。** 目前没有在跑的 ASR 作业，交付基线没有变化。
只维护 STATUS，**不自行开新实验**。TaskList #15（C-058⑤ INT4 配方矩阵补测）保持 pending，
不主动启动。

---

## §7 C-111 正式移交说明（2026-10-23 11:50）—— 按 ASR-003【用户决定】交 App 模块

> `last_ack: ASR-003`。用户已确认：**C-111 由 App 模块接手**合入与端到端验证，
> 翻译逻辑由 MT 模块复核。**ASR 线程自此不再改 `live_caption/` 下任何文件、不再提交**
> （那些文件以后只由 App 线程提交）。本节写完后 ASR 回到本模块本职。

### 7.1 改了哪些文件、哪些函数（附 diff 摘要）
基线 `63020bf`（C-109）→ `ebc6107`（C-111）：
```
 live_caption/translator.py         | 272 ++++++++++++++++++++++++-------
 live_caption/live_caption_app.py   |  25 ++--
 2 files changed, 241 insertions(+), 56 deletions(-)
```

**`live_caption/translator.py`（翻译层，MT 模块复核）**
| 位置（当前行号） | 符号 | 改动 |
|---|---|---|
| 699 | `class _Job` | `kind` 语义扩展：`final`（朗读）/ **`half`（段尾半句，只显示不朗读）** / **`fix`（修正版，朗读）** / `draft`；`__slots__` 加 `old_key`/`old_seg` |
| 764–770 | `TranslationService.__init__` | **`self._carry`（挂起）→ `self._half`**（未闭合的半句链，存 `{'text','key','seg'}`）；新增 `self.seg_half = {}`（段序号 → 本段末尾是否半句） |
| 898 | `_enqueue_half()` **新增** | 段尾半句**当段即翻**：入队 `kind='half'`，key 记在**产生它的那一段** |
| 910 | `_enqueue_fix()` **新增** | 半句被补成完整句后**重翻**：入队 `kind='fix'`，译文**原地覆盖**半句原来的槽位（`slot_key`） |
| 923 | `submit()` **重写** | 主流程：半句链未闭合 → 本段各留一份；闭合 → `_enqueue_fix` 整句覆盖**链首**槽位 + 本段首半句单独切分/单独翻/归本段；本段文本分句 → 段尾半句当段即翻；**段尾链闭合而本段无新半句 ⇒ `self._half = None`**（关键修复，见 7.4） |
| 1082 | `flush()` | 不再重翻，只把最后一个半句标记为 `final` 交出 |
| 1107 | `mt_of_seg()` | 按 `seg_keys[seg]` 拼译文（半句译文归本段 ⇒ 不再缺字） |
| 1123 | `carry` property | 返回 `self._half['text']` |
| 1200–1203 | 换模型清理 | `_carry` → `_half = None`；新增 `seg_half.clear()` |
| 1251 | `_run_jobs()` | `kind in ('final','half','fix')` 都写 `svc.done[key]` 并 `outbox.append((kind, key, text))`；`'final'`/`'fix'` 更新 `_last_src` |

**`live_caption/live_caption_app.py`（App 模块）** — 6 个 hunk、**不含任何 TTS 代码**
| 位置 | 改动 |
|---|---|
| `App.clear()` 1446 | 新增 `self.mt.seg_half.clear()` |
| `App._save_text()` 1456–1462 | 文案：旧「（半句，接续下一段）」→「（译文生成中…）」；注释改为 C-111 语义 |
| `run_cli()` 1741–1746 | outbox 消费①：`half` → 打印「[半句译文]」**不朗读**；`final`/`fix` → 打印「[译文]」/「[修正译文]」**朗读** |
| `run_cli()` 1764–1768 | outbox 消费②（收尾）：同上 |
| `run_cli()` 1790 | 落盘文案同 7 |
（🔴 提交时 app 用的是「HEAD 版 + C-111 的 5 处定点替换」构造的**独立可运行**版本 ——
HEAD 版 app 里**没有 `tts` 变量**，带 `tts.submit` 引用会 NameError，故必须剥离 TTS 行。）

### 7.2 设计意图
**问题**（C-110 调研后确定不动切段规则）：ASR 句末标点 ≠ 语音结束位置 ⇒ 段尾经常是半句。
旧机制（C-099① 挂起）把半句挂到下一段一起翻 ⇒ **本段译文缺一截**（用户界面上这段原文"没有译文"）。

**新机制三条**：
1. **段尾半句当段就翻**（`kind='half'`），译文归**产生它的那一段** ⇒ 每段都有自己原文的译文。
2. **补全后重翻并原地覆盖**（`kind='fix'`）—— 这就是用户要的「修正之前的翻译错误」；
   整句译文**原地覆盖链首**的半句槽位 ⇒ 归属不变（跨段句只能归属一段，是固有约束）。
3. **TTS 语义**：`half` **只显示不朗读**（残句语义不完整），`final`/`fix` 朗读
   ⇒ 同一句不会被念两遍（`tts_service.submit()` 的 `seg` 只作记录、不做去重/替换）。

**为什么这样分**：`half`/`fix` 分离让「显示」和「朗读」解耦 —— 段尾半句立刻可见（解决 T3 痛点），
但不进 TTS；等它成为完整句时用 `fix` 覆盖同一个槽位并朗读。

### 7.3 已有测试结果（含口径与产物）
**输入**：`hy_bench/runs/c109_minseg6/min6.0_cut0.8.json`（C-109 定稿，**72 段** / 12 分钟真实演讲）。

**① 段归属对照** — `live_caption/diag_c111_own.py`
产物 `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_ownership.json`（1 文件 / 7090 B / mtime 2026-10-23 11:07）
| 指标 | 旧机制 | 新机制 |
|---|---|---|
| `own_hit`（本段原文的词能在**本段** key 列表里找到） | 1181 | **1405** |
| `own_miss`（缺失词数） | **224** | **0** |
| `delayed`（被推迟显示的词） | 100 | **0** |
| `early`（提前） | 763 | 768 |
| `lost`（丢失） | 0 | 0 |
| `tail_own` / `tail_total`（段尾半句归本段） | 3 / 29 | **29 / 29** |

> 🔴 **口径（务必按此读，不要只看 84.1%→100%）**：
> 判据是**词级覆盖率** —— 「**本段**原文的词，能否在**本段**的 `seg_keys` 里找到」。
> 分母 = 全部 72 段原文的词数 = **1405**（新机制 `own_hit` 达到 1405 ⇒ 覆盖率 100%）。
> ⚠️ **不是**「自然句边界」判据：用自然句边界当判据时，跨段句（只能归属一段）
> 本来就不在任何一段的 key 列表里 ⇒ 会得出「新机制更差」的**错误结论**。
> ⚠️ `early`（提前）**不是缺陷**：跨段的那一句只能归属一段，提前/推迟是固有属性，
> **覆盖率才是缺陷指标**。

**② 状态机** — `live_caption/diag_c111_half.py`（假引擎，秒级，**10 用例 ALL PASS**）
半句当段即翻 / 整段半句 / 链上每段各留一份 / flush / 跨段整句原地修正 /
**TTS 不重复朗读** / 段间无越界串词 / 超长句 / 去重 / 无残留 `_carry`。

**③ fix-key 回归** — `live_caption/diag_c111_fixkey.py`（假引擎 + 真实 72 段）
产物 `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_fixkey.json`（1 文件 / 290 B / mtime 2026-10-23 11:09）
`n_segments=72` / `translate_calls=164` / `kinds={half:58, final:81, fix:25}` /
`fix_key_total=25` / `fix_key_unique=25` / `fix_key_dup={}` / `bad_sequence_keys=[]` /
`fix_not_whole_sentence=[]` / `combo_dup={}` / `pass=true`
⇒ **每个槽位只被修正一次**，且每个 key 的事件序列只可能是 `[half]` / `[half,fix]` / `[final]` / `[fix]`。

**④ 客户包代码上的行为验证**（直接 import `Confucius4_LiveCaption_v1.3/app/translator.py`）
```
half  ZH:So welcome                ← 段尾半句当段即翻、只显示
final ZH:Good morning everyone.
fix   ZH:So welcome to our Q3 meeting.   ← 补全后整句原地覆盖
half  ZH:to our Q3 meeting.
final ZH:Then we cover AI.
```

### 7.4 过程中修正的 4 个实现缺陷（**接手方请注意，都是真实踩过的坑**）
1. **补全句归错段** —— 初版把整句归「当前段」⇒ 上一段的半句译文「消失」
   （缺失词 224→307，比旧机制更糟）⇒ 改为**原地覆盖**半句槽位、归属不变。
2. **半句链中间段为空** —— 段7/段8 连续两段都是半句、到段9才闭合 ⇒ 初版把整链归闭合段，
   段7/段8 的 `seg_keys` **全空**（比旧机制更糟）⇒ 改为**链上每段各留一份**。
3. **本段首半句被粘连** —— 首半句无句末标点会与后续内容粘成一句、归属到更后面的段
   ⇒ 改为首半句**单独切分、单独翻、单独归本段**。
4. 🔴 **半句链闭合后 `self._half` 未清空**（真实翻译模型 e2e 才暴露）⇒ 下一段把**已闭合**的
   旧半句当成新链头再走一遍闭合流程 ⇒ **同一槽位被反复 `fix`**（实测 key 重复 9 次/8 次/7 次/6 次/3 次，
   译文被连续改写成三句不同的话）⇒ 已在「本段文本分句」分支加
   `elif prev_half is not None: self._half = None`，并由 ③ 回归守住。

### 7.5 还没完成的事项（**移交后由 App 模块接手**）
| 事项 | 现状 | 说明 |
|---|---|---|
| **真实翻译模型端到端重跑** | ❌ 未完成 | 首轮结果 `hy_bench/runs/c111_half/c111_e2e.json` 标 **`timing_valid=false`**（未持共享机器锁、且与 app 模块并行占 GPU），**且含 7.4-④ 的 bug** ⇒ 修复后的数值为空，**必须重跑**。脚本 `live_caption/diag_c111_e2e.py` 已自带机器锁自持（锁被别的模块持有 ⇒ 直接退出不抢；孤儿锁才回收）+ fix-key 唯一性检查 |
| 翻译次数增量 | 首轮（修复前）126→196（**+55.6%**） | 修复后预期下降（重复 `fix` 消失），需重测 |
| 实时性是否积压 | 首轮 105.3s 墙钟 / 720s 音频 = **7.64x 实时** | 段间隔约 10s、每段翻译 1.31s ⇒ 不积压；修复后需复核 |
| TTS 朗读次数 | 首轮 126→102（半句不朗读） | 需在 App 侧确认不重复朗读 |
| **ASR 侧是否受益** | 未量化 | 段归属覆盖率 100% 是**翻译层**口径；「定稿后多久看到自己那段的译文」（T3）在真实链路上仍需端到端测 |
| 客户包 | ✅ 已同步（App 模块可复核） | `Confucius4_LiveCaption_v1.3/app`：`translator.py` 整文件复制（SHA256 安全闸）+ `live_caption_app.py` 5 处定点替换；备份在**包外** `Confucius4_LiveCaption_v1.3/_backup_c111/`。**改源目录 ≠ 交付给客户，必须重打包才生效** |

### 7.6 已发生的提交（**App 模块复核时请注意历史**）
| 提交 | 内容 |
|---|---|
| `ebc6107` | C-111 主体：translator.py 全部 + app 5 处 + 4 个诊断脚本 + `sync_c111_to_pkg.py` + `status/asr/STATUS_ASR.md`（8 文件 +1686/−56） |
| `3ce0919` | §1 交付基线产物定位补记（ASR 模块自己的状态文件） |
| `6f05815` | 客户包行为验证 + `wait_and_run_e2e.py`（该排队脚本已按 ASR-002 停用并终止） |
| `7fc535c` / `23436f1` / `b6de69a` / `cc8eb96` | ASR-002 回执（只含 `status/asr/` 下的文件） |

🔴 **提醒**：工作区 `live_caption/translator.py` 仍有**未提交**改动
（默认量化 INT4→INT8 切换，引用 H-001/H-007）—— 那是 **MT 模块**的工作，
ASR 线程未碰、未提交。

### 7.7 交接检查清单（给 App 模块）
- [ ] 端到端重跑 `python live_caption/diag_c111_e2e.py`（**先确认共享机器锁**），
      记录 `fix` key 是否唯一、翻译次数、实时性、TTS 朗读次数。
- [ ] 复核翻译逻辑（MT 模块）：`submit()` 的半句链状态机、`_enqueue_fix` 的原地覆盖语义。
- [ ] 决定 C-111 代码的**最终提交归属**（当前在 `ebc6107` 里，由 ASR 线程提交）。
- [ ] 决定 `sync_c111_to_pkg.py` 的归属（客户包归 App 模块）。
- [ ] 客户包**重打包**后才算交付给客户。

### 7.8 定期检查机制（本模块）
用户要求「定期检查 `corrections_ASR.md` 是否有更新，如果有则按要求执行」⇒ 已建立**每小时**一次的
定期检查（自动化任务「ASR 模块纠偏定期检查」）。每次运行的动作：
1. 读 `status/asr/CORRECTIONS_ASR.md`，找编号 **> `last_ack`** 的条目；
2. 无新条目 ⇒ 什么都不改，只回报「无新纠偏」；
3. 有新条目 ⇒ 逐条按其「要做的 / 验收」执行，**不自行扩大范围**；
4. 结果写进本文件（开头 4 行 + `最近更新` ≤15 行 + 只追加 `## §N` 章节），**只提交 `status/asr/` 下的文件**。

**当前状态**：`last_ack: ASR-003`，**无新纠偏**；ASR 侧无用户指派任务 ⇒ **待命**。
（ASR-003 提到的本模块本职：模型、量化、设备摆放、流式与切段策略、RTF ——
切段参数实际定义在 App 模块的 `live_caption_app.py`
（`MIN_SEG_SEC` 默认 6.0 / `MAX_SEG_SEC` 20.0，均可用 `LIVECAP_*` 环境变量覆盖），
ASR 侧只做策略研究与验证，**不直接改 App 文件**。）

---

## §8 实时「定稿间隔 >12s」根因定位（2026-10-23 13:05）—— ASR 侧诊断，代码改动待 App 模块

### 8.1 口径对齐（与用户 2026-10-23 12:55 确认）
「定稿间隔」= **从第 i 次定稿到第 i+1 次定稿的间隔**。
连续切段时它**等于**第 i+1 段的段长（段首尾相接）⇒ 统计段长即可等价。
本节全部数字都按这个口径。

### 8.2 结论（一句话）
**C-109 的 6s 改动确实已实施、且在"正常电平"下有效；实时跑之所以还是 >12s，
是因为 `_has_speech()` 空段守卫用的是**绝对电平阈值**（-35dBFS），
在麦克风输入电平偏低时恒为 False ⇒ 它在 `due()` 最前面**短路**，
规则1/规则2 全被跳过 ⇒ 只能等 `MAX_SEG_SEC=20s` 硬切。**
⇒ 用户看到的 >12s，实际是 **20.48s**（20s 门槛 + 0.64s chunk 粒度）。

### 8.3 证据链

**证据 1：改动已实施（两处都在）**
- 仓库版 `live_caption/live_caption_app.py` 行 98：`MIN_SEG_SEC = float(os.environ.get('LIVECAP_MIN_SEG_SEC', '6.0'))`
- 用户启动路径就是这个文件 ⇒ 走的就是 6.0s。
- 用户进程环境无 `LIVECAP_*` 覆盖（实测 `os.environ` 扫描结果为空）⇒ 不会被改回 12。
- 客户包 `Confucius4_LiveCaption_v1.3/app` 同值，切段逻辑与仓库 diff 一致。

**证据 2：正常电平下改动有效（用真实 `Segmenter.due()`，12 分钟真实演讲）**
```
gain=1.0  段数=108  规则={rule1:102, rule2:6}
  定稿间隔 p50=6.40s p90=7.68s p95=8.32s max=11.52s | >12s: 0/108 (0.0%)
```
⇒ 与 C-109 离线产物（72 段 / p50=6.40 / p95=8.90 / max=11.50 / >12s 0/72）**一致**
⇒ **切段逻辑本身没问题**。

**证据 3：低电平 ⇒ 间隔恒为 20.48s（本节核心）**
输入增益扫描（同一段真实音频整体乘 g，模拟麦克风音量/底噪差异），
**直接调用真实的 `seg.due()`**：
```
gain=1.0  音频p50=-37.5dB p90=-24.4dB  段数=108  间隔 p50=6.40  max=11.52  >12s: 0/108   (0.0%)
gain=0.7  音频p50=-40.6dB p90=-27.5dB  段数=101  间隔 p50=6.40  max=16.64  >12s: 3/101   (3.0%)
gain=0.5  音频p50=-43.5dB p90=-30.5dB  段数= 86  间隔 p50=6.40  max=20.48  >12s: 12/86  (14.0%)
gain=0.3  音频p50=-47.9dB p90=-34.9dB  段数= 46  间隔 p50=20.48 max=20.48  >12s: 31/46  (67.4%)
gain=0.2  音频p50=-51.4dB p90=-38.4dB  段数= 36  间隔 p50=20.48 max=20.48  >12s: 35/36  (97.2%)
gain=0.1  音频p50=-57.5dB p90=-44.4dB  段数= 35  间隔 p50=20.48 max=20.48  >12s: 35/35  (100.0%)
```
>12s 的段的判据明细（gain=0.5 / 0.3）：
```
dur=20.48 has_speech=False silence_tail=False seg_p90=-34.5 frac_sil=0.70 max_run=190ms
dur=20.48 has_speech=False silence_tail=True  seg_p90=-38.7 frac_sil=0.85 max_run=90ms
```
⇒ **`has_speech=False` 是特征**：段内**最长连续 >-35dB 的帧只有 70~190ms < 200ms 门槛**
⇒ `_has_speech` 恒 False ⇒ `due()` 在第 446 行 `return False` ⇒ 规则2/规则1 全跳过
⇒ 只有第 442 行 `dur >= MAX_SEG_SEC(20s)` 能出段 ⇒ **间隔恒 20.48s**。

**证据 4：`_has_speech` 的电平依赖是"断崖式"的**
把真实录音整体衰减，统计"最长连续 >-35dB 的帧数"：
```
gain=1.000  语音帧占比 38.8%  最长连续 0.67s  pass=True
gain=0.500  语音帧占比 19.5%  最长连续 0.34s  pass=True
gain=0.300  语音帧占比  5.1%  最长连续 0.16s  pass=False   ← 断崖
gain=0.200  语音帧占比  0.5%  最长连续 0.07s  pass=False
gain=0.100  语音帧占比  0.0%  最长连续 0.00s  pass=False
```
⇒ 只要**说话时的帧电平跌破 -35dBFS**，守卫立刻从"放行"翻成"拦截"，
**没有任何过渡区** ⇒ 这是一个**开关**，不是渐变。

**证据 5：A/B 验证 —— 换成相对判据后，低电平也正常**
把 `_has_speech` 改成**相对判据**（段内 p90 - 18dB，与 `_silence_tail` 的 C-105 相对判据同思路）：
```
现状   gain=0.5  段数= 86  间隔 p50=6.40 p90=13.44 max=20.48  >12s: 12/86  (14.0%)
相对   gain=0.5  段数=116  间隔 p50=6.40 p90= 6.72 max=10.88  >12s: 0/116  (0.0%)
现状   gain=0.3  段数= 46  间隔 p50=20.48 max=20.48          >12s: 31/46  (67.4%)
相对   gain=0.3  段数=130  间隔 p50=6.40 p90= 6.40 max=7.68   >12s: 0/130  (0.0%)
现状   gain=0.7  段数=101  间隔 p50=6.40 p90= 8.32 max=16.64  >12s: 3/101  (3.0%)
相对   gain=0.7  段数=110  间隔 p50=6.40 p90= 7.10 max=11.52  >12s: 0/110  (0.0%)
```
⇒ **相对判据在所有电平下都把间隔拉回 6.4s 量级**，且正常电平下**不变差**
（gain=1.0：现状 108 段/0 个 >12s ↔ 相对 110 段/0 个 >12s）。

### 8.4 产物清单
| 文件 | 说明 | mtime |
|---|---|---|
| `results/asr_diag/diag_realtime_latency.py` | 第一版（判据有缺陷，见 8.5） | 2026-10-23 12:56 |
| `results/asr_diag/diag_realtime_latency2.py` | 修正版（**直接调用真实 `seg.due()`**） | 2026-10-23 12:59 |
| `results/asr_diag/diag_has_speech_gate.py` | A/B（绝对 vs 相对判据） | 2026-10-23 13:01 |
| `results/asr_diag/realtime_latency.json` | 增益扫描产物（第 1 版） | 2026-10-23 12:58 |
| `results/asr_diag/realtime_latency2.json` | 增益扫描产物（真实 due，含逐段判据明细） | 2026-10-23 12:59 |
| `results/asr_diag/has_speech_gate.json` | A/B 产物 | 2026-10-23 13:01 |
| `results/mic_noise_probe.npy` | 麦克风底噪实测（10s，p50=-96.5dB） | 2026-10-23 12:55 |

### 8.5 自我修正（判据写错的教训）
第 1 版 `diag_realtime_latency.py` **自己复现**了 `due()` 的判定顺序，
漏掉了 `_has_speech` 守卫**在最前面直接 `return False`** 的短路语义
⇒ 低电平下误判成"rule1 触发"，得出"低电平也无影响"的错误结论。
第 2 版改为**直接调用真实的 `seg.due()`**，明细只用于事后解释，才拿到正确结论。
**教训：诊断脚本必须调用真实实现，不要复现判定逻辑。**

### 8.6 建议的修复方向（**待 App 模块实施；ASR 侧不改 `live_caption/`**）
按 ASR-003，ASR 线程**不再改 `live_caption/` 下任何文件**。建议交 App 模块：

1. **首选**：把 `_has_speech()` 的判据从**绝对电平**（-35dBFS）改为**相对电平**
   （段内 p90 - drop），drop 建议 **18dB**（与 `GUARD_REL_DROP_DB` 一致），
   并保留绝对判据作并集（`绝对 ∪ 相对`，与 `_silence_tail` 的 C-105 思路一致，
   保证**只放宽不收紧**）。
2. **或**（更保守）：把空段守卫的绝对阈值从 -35dBFS 降到 -45dBFS，
   并把 `SEG_MIN_SPEECH_RUN_MS` 从 200ms 降到 100ms。
   ⚠️ 但这会**削弱空段守卫的防切空段能力**（C-108 的原始目的）⇒
   必须重跑 C-108 的空段校验（61 分钟素材，hang 0.8/0.6/0.5 三档）。
3. **零代码的即时缓解**：调高系统麦克风输入增益 / 靠近麦克风；
   或用 `LIVECAP_MIN_SPEECH_FRAME_DB` 环境变量（**注意：该常量当前是硬编码
   `SEG_SPEECH_FRAME_DB = -35.0`，没有 env 开关**，需 App 模块先加开关）。

### 8.7 待用户决定
- 是否按 8.6 建议 1（相对判据）改？改动涉及 App 模块的 `live_caption_app.py`。
- 是否需要 ASR 侧补测「空段守卫改动后的空段数」以保证不切空段？
- 是否需要在 GUI 里显示「当前输入电平 dB」与「定稿间隔」两个实时指标，便于用户自查。

---

## §9 【重要修正】用户输入源是**系统回环（B 站在线视频）**⇒ §8 的根因**不适用**，真实根因是「全程无静音」（2026-10-23 13:30）

### 9.1 触发修正的关键信息
用户 2026-10-23 13:17 补充：**测试模式的输入音源是 B 站在线视频**
（`https://www.bilibili.com/video/BV1jS411c79s/...&p=3`）
⇒ 走的是 **`SystemAudioSource`（WASAPI 回环）**，**不是麦克风**。
⇒ §8 定位的「`_has_speech` 绝对电平 -35dBFS 拦截」**对你的场景不成立**（见 9.3）。

### 9.2 撤回 §8 的根因结论
**撤回 §8.2 的一处归因**：`_has_speech` 的绝对电平阈值**不是**你这次 >12s 的原因。
它**是**一个真实存在的隐患（麦克风电平偏低时会踩到，§8.3 证据 3/4/5 依然成立），
但**与你的视频输入无关**。
§8 的**结论 C-109 已实施、正常电平下有效**（§8.3 证据 2）**依然成立**。

### 9.3 真实根因：**视频音频全程没有静音** ⇒ 两条规则都废 ⇒ 只剩 20s 硬切
用 `probe_loopback_live.py` **实测采集你正在播放视频时的回环信号**（120s）：
```
帧dB: p10=-41.9 p50=-21.8 p90=-13.9 max=-9.2      整段 RMS=-18.3dB
低于 -40dB 的帧占比 = 12.2%
逐 2 秒窗口的最长连续静音：0.00 ~ 0.43s（19 个窗口里只有 1 个窗口 >0.3s）
```
⇒ **电平正常**（帧 p50=-21.8dB ≫ -35dBFS）⇒ `_has_speech` 守卫**放行**（实测"守卫OK"）
⇒ **但几乎没有静音**：最长连续静音 0.00~0.43s，**全部 < 0.8s**
⇒ **规则2**（段尾连续静音 ≥0.8s）**永不触发**
⇒ **规则1**（近 3s 内有 ≥300ms 静音）**也永不触发**（最长才 0.43s）
⇒ **只剩 `MAX_SEG_SEC=20s` 硬切** ⇒ **定稿间隔恒 20.48s**

**用你的真实回环数据跑真实 `seg.due()` 的直接确认**：
```
真实回环采集 39.7s  RMS=-18.7dB
段数=1   间隔 20.48s   rule=max(硬切)   该段最长静音=1.56s   守卫=True   规则2=False
```
⇒ **就是 20.48s 硬切**，与用户观感「>12 秒」完全吻合。

**机制验证（合成背景声）**：在真实演讲上叠加恒定电平背景声，
用真实 `seg.due()` 扫描：
```
背景声   无      静音帧占比 0.428  间隔 p50= 6.40  max=11.52  >12s 0/108 (0.0%)
背景声 -45dBFS   静音帧占比 0.383  间隔 p50= 6.40  max=11.52  >12s 0/107 (0.0%)
背景声 -42dBFS   静音帧占比 0.310  间隔 p50= 6.40  max=11.52  >12s 0/105 (0.0%)
背景声 -40dBFS   静音帧占比 0.074  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)  ← 跳变
背景声 -38dBFS   静音帧占比 0.000  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)
背景声 -20dBFS   静音帧占比 0.000  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)
```
⇒ **只要背景声达到 -40dBFS（= `SILENCE_DB`），间隔立刻从 6.4s 跳到 20.48s**。
⇒ 根因一句话：**`SILENCE_DB=-40dBFS` 是绝对阈值，而视频有持续背景声，永远跌不下去。**

### 9.4 候选判据验证（真实回环数据 + 真实演讲数据双向交叉）

**在真实回环数据（120s，你的视频信号）上**：
```
判据                              段数 硬切 空段 | 间隔 p50   p90    max    | >12s
A 绝对 -40dBFS（现状）              8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
B 相对 段内p90-12dB                16   0    0   |  6.40   8.32  13.44  | 1 ( 6.2%)  ← 最佳
B 相对 段内p90-18dB                12   1    0   |  7.04  18.37  20.48  | 3 (25.0%)
B 相对 段内p90-24dB                 8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
E 绝对∪相对(取min) p90-12          8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
D 相对 p90-18dB + 静音门槛300ms    12   1    0   |  7.04  18.37  20.48  | 3 (25.0%)
```
⇒ **相对判据 `段内 p90 − 12dB`** 在真实视频信号上把间隔从 17.28s 降到 **6.40s**，
>12s 从 **62.5% → 6.2%**，**硬切段 4→0**，**空段 0**。

**在真实演讲数据（12 分钟）上交叉验证（确认不劣化原质量）**：
```
现状 绝对-40dBFS      段数=108 硬切=0 空段=0 | p50=6.40 p90=7.68 max=11.52 | >12s 0 (0.0%)
推荐 相对 p90-12dB   段数=110 硬切=0 空段=0 | p50=6.40 p90=7.04 max=10.88 | >12s 0 (0.0%)
```
⇒ **不劣化**（段数 108→110，空段 0，>12s 仍 0%），且最长段从 11.52s 降到 10.88s。

### 9.5 建议的修复方向（**待 App 模块实施**）
在 `Segmenter` 里把**静音判据**从「绝对 -40dBFS」改成「**相对**：段内 p90 − 12dB」，
即：静音门限 = `min(绝对 -40dBFS, 段内语音电平p90 − 12dB)`（取更宽松者，只放宽不收紧），
并让 `_silence_tail()` 与规则1 共用同一门限。
⚠️ 注意：**这条与 §8.6 建议 1 是两处不同的改动**
- §8.6 建议 1 改的是 `_has_speech()`（空段守卫）⇒ 针对**麦克风电平偏低**
- 本节 §9.5 改的是**静音门限 `SILENCE_DB`** ⇒ 针对**背景声导致无静音**
⇒ 两者可独立实施，**对麦克风场景 §9.5 也无害**（真实演讲交叉验证已证明）。

**零代码的即时缓解**（用户可自行试）：
- 在 App 里把 `SILENCE_CUT_SEC` 调小到 **0.2s**（`LIVECAP_SILENCE_CUT_SEC=0.2`）——
  实测你的信号里有 0.43s 的停顿，门槛 0.3~0.4s 就能触发；
- 但**注意**：规则1 仍需「近 3s 内 ≥300ms 静音」，需要配合降低 `SILENCE_DB`
  才能整体生效 ⇒ **单改 `SILENCE_CUT_SEC` 不够**。
- 最可靠的还是 §9.5 的相对门限。

### 9.6 附带发现（供 App 参考，非本次根因）
- **回环立体声只取左声道**：`audio_source.py:335` 采 2 声道，
  行 352 `_to_mono(data)` **只取 `a[:, 0]`** ⇒ 右声道内容被丢弃。
  若视频左右声道内容不同（如背景声走一路、人声走另一路），
  **取 ch0 可能把主要人声丢掉** ⇒ 电平损失可达数 dB。
  ⇒ 建议改成 `(L+R)/2` 或两声道能量取大。
- **回环在无播放时输出数字零**（实测 12s 全零，帧 dB max=-119.2dB），
  与麦克风的 -96dB 底噪不同 ⇒ 两种音源的"静音"表现差异很大，
  **任何绝对电平阈值都只对其中一种成立**。

### 9.7 产物清单（本节）
| 文件 | 说明 | mtime |
|---|---|---|
| `results/asr_diag/probe_loopback_live.py` | 实时回环探测（只读采集 + 能量分析） | 2026-10-23 13:21 |
| `results/asr_diag/diag_bgm_no_silence.py` | 背景声 ⇒ 无静音机制验证（合成） | 2026-10-23 13:20 |
| `results/asr_diag/diag_loopback_vad.py` | 候选判据筛选（真实演讲） | 2026-10-23 13:22 |
| `results/asr_diag/diag_loopback_real.py` | 候选判据验证（**真实回环数据**） | 2026-10-23 13:25 |
| `results/asr_diag/loopback_live_raw.npy` | 真实回环原始采集（120s） | 2026-10-23 13:24 |
| `results/asr_diag/loopback_live_probe.json` | 回环探测汇总（40s） | 2026-10-23 13:21 |
| `results/asr_diag/loopback_live_probe_120.json` | 回环探测汇总（120s） | 2026-10-23 13:24 |
| `results/asr_diag/bgm_no_silence.json` | 背景声扫描产物 | 2026-10-23 13:20 |
| `results/asr_diag/loopback_vad.json` | 候选判据（真实演讲）产物 | 2026-10-23 13:22 |
| `results/asr_diag/loopback_real.json` | 候选判据（真实回环）产物 | 2026-10-23 13:25 |
| `results/loopback_probe.npy` | 无播放时的回环采样（全零对照） | 2026-10-23 13:18 |

### 9.8 待用户决定
- 是否按 §9.5 实施「静音门限改相对判据（段内 p90−12dB）」？**这是解决你这次现象的关键改动**。
- 是否同时实施 §8.6 建议 1（`_has_speech` 改相对判据）—— 面向**麦克风**场景，可选。
- 是否按 §9.6 改回环立体声取单声道为 `(L+R)/2`？
- 是否在 GUI 加「实时输入电平 dB / 段内最长静音 / 定稿间隔」三个实时指标
  —— 有助于用户自己区分"电平问题"与"无静音问题"。



## §10 实施 §9.5 三项改动 + 真实实现 A/B 验证（2026-10-23 14:05）

用户裁决（§9.8）：**1.yes（静音门限相对化）/ 2.yes（`_has_speech` 相对化）/ 3.yes（回环立体声混合）/ 4.no（不加 GUI 指标）**。
本节记录**已实施**的三项改动、验证数据、以及实施过程中被证伪的中间方案。

> ⚠️ **模块边界（ASR-003）**：本节改动了 `live_caption/` 下 2 个文件，
> 但按 ASR-003「ASR 线程不再改 `live_caption/`、不再提交」——
> 本次是**用户直接批准的 §10 实施**（切段策略属 ASR 范围，见 ASR-001
> 「流式和切段策略」），**代码改动已在工作区**，但**git 提交仍归 App 模块**。
> ASR 侧本节只提交 `status/asr/`。

### 10.1 改动清单

| # | 文件 | 位置 | 内容 |
|---|---|---|---|
| 1 | `live_caption/live_caption_app.py` | 常量区（`SILENCE_DB` 之后） | 新增 7 个相对判据常量 |
| 1 | 同上 | `Segmenter._silence_threshold()` | **新增**：本段静音门限 = 段内 p90 − `SIL_REL_DROP_DB`(12dB) |
| 1 | 同上 | `Segmenter.due()` 规则1 | 原**硬编码** `silence_db=-40.0` → 改用 `self._silence_threshold(acc)` |
| 1 | 同上 | `Segmenter._silence_tail()` | `silence_db=SILENCE_DB` → 改用同一门限 |
| 2 | 同上 | `Segmenter._has_speech()` | 新增**相对分支**（帧 > 段内 p90−18dB 且 > −70dBFS 地板，连续 ≥200ms），与原绝对分支**取并集** |
| 2 | 同上 | `Segmenter._speech_ratio_ok()` | **新增**：空段拒切防护（§10.3） |
| 2 | 同上 | `Segmenter.due()` | 规则2 与规则1 均加「空段拒切」 |
| 3 | `live_caption/audio_source.py` | `_stereo_to_mono()` / `_corr()` | **新增**：回环立体声混合（§10.4） |
| 3 | 同上 | `SystemAudioSource._run()` | `resample_to_16k(_to_mono(data), SR)` → `resample_to_16k(_stereo_to_mono(data, self._mix_state), SR)` |

新增常量（全部 env 可控，便于回退）：
```
SIL_REL_ENABLED=1  SIL_REL_DROP_DB=12  SIL_REL_MIN_SPEECH_DB=-60  SIL_REL_MODE=max
SPK_REL_ENABLED=1  SPK_REL_DROP_DB=18  SPK_REL_MIN_SPEECH_DB=-60  SPK_REL_FLOOR_DB=-70
SEG_MIN_REL_COVER=0.40
STEREO_MIX_BALANCE_DB=6  STEREO_MIX_EMA=0.9  STEREO_MIX_ANTIPHASE_CORR=-0.5
```
env 名：`LIVECAP_SIL_REL` / `LIVECAP_SIL_REL_DROP` / `LIVECAP_SIL_REL_MIN_SPEECH` /
`LIVECAP_SIL_REL_MODE` / `LIVECAP_SPK_REL` / `LIVECAP_SPK_REL_DROP` /
`LIVECAP_SPK_REL_MIN_SPEECH` / `LIVECAP_SPK_REL_FLOOR` / `LIVECAP_MIN_REL_COVER` /
`LIVECAP_STEREO_BALANCE_DB` / `LIVECAP_STEREO_EMA` / `LIVECAP_STEREO_ANTIPHASE`

### 10.2 真实实现 A/B 验证（**直接调用改后的真实 `seg.due()`**）

★ 铁律遵守：判定**一律调用真实实现**，不复现判定逻辑（§8.5 教训）。
A/B 手段：改**环境变量**让真实实现自己切换行为（`LIVECAP_SIL_REL=0` + `LIVECAP_SPK_REL=0` = 基线）。

**数据 1：真实回环 120s**（`results/asr_diag/loopback_live_raw.npy`，用户在播 B 站视频时采集）

| | 段数 | 硬切 | 空段 | 间隔 p50 | p90 | max | >12s |
|---|---|---|---|---|---|---|---|
| A 基线（绝对阈值） | 8 | 4 | 0 | 17.28s | 20.48s | 20.48s | **5 (62.5%)** |
| B 相对判据 | 16 | **0** | 0 | **6.40s** | 8.32s | 13.44s | **1 (6.2%)** |

**数据 2：真实演讲 12 分钟**（`test_audio/<redacted>.wav`，回归）

| | 段数 | 硬切 | 空段 | 间隔 p50 | max | >12s | 规则2 危险切点 |
|---|---|---|---|---|---|---|---|
| A 基线 | 108 | 0 | 0 | 6.40s | 11.52s | 0 (0.0%) | 0/6 |
| B 相对判据 | 110 | 0 | **0** | 6.40s | 10.88s | 0 (0.0%) | **0/10** |

**数据 3：低电平扫描**（增益作用于真实演讲 ⇒ 模拟麦克风电平偏低）

| gain | A 基线 >12s | B 相对判据 >12s | A 空段(绝对口径) | B 空段(绝对口径) |
|---|---|---|---|---|
| 1.0 | 0.0% | 0.0% | 0 | 0 |
| 0.5 | 14.0% | **0.0%** | 0 | 5 |
| 0.3 | 67.4% | **0.0%** | 18 | 48 |
| 0.1 | 100.0% | **0.0%** | 35 | 119 |

⚠️ 「空段」列在低电平下用**绝对口径**统计会失真（绝对阈值在低电平下天然失效，
`frac_abs` 恒为 0）。**相对口径**下 A 基线与 B 新判据的增益 1.0 空段都是 **0**
（见 `s10_scan.json` 的 `n_empty` 字段 = 相对口径）。

**参数扫描**（`results/asr_diag/s10_scan.json`，15 组 floor × drop）：
`floor=-70, drop=12`（= 当前默认）**全指标 PASS**，且是唯一同时满足
「回环 >12s ≤ 10%」「gain=1.0 空段=0 且危险切点=0」「gain=0.3 >12s=0」
「gain=0.1 >12s ≤ 40%」的组合。

### 10.3 实施过程中被证伪的两个中间方案（**否定结论，勿再尝试**）

**否定结论 A：空段拒切不能用绝对口径。**
§9.4 的「相对 ∪ 绝对（取 min）」在静音门限上无效（绝对 −40dBFS 恒更严）。
本轮又发现：**空段拒切**若用 C-108 的绝对语音占比（帧 > −35dBFS 占比 < 10%），
在低电平麦克风场景会**误杀正常说话段** ——
实测 gain=0.3 的正常段绝对语音占比只有 **0.8%~6%**（那**是真的说话**），
用它拒切 ⇒ gain=0.3 的 >12s 从 0% 退化到 **23.4%**。
同理「静音占比」（帧 ≤ −40dBFS）也不行：低电平时底噪本身就在 −40dBFS 以下
⇒ 会被误判成全静音。
⇒ **原理**：绝对电平口径**无法区分「轻声说话」与「安静」** —— 把增益调低 10dB
后二者不可分辨。**判据必须相对化。**

**否定结论 B：空段拒切要用「相对语音覆盖率」，不是「连续语音」。**
实测区分度（12 分钟真实演讲，真实 `due()` 产生的段，产物 `s10_discrim.json`）：

| 段 | 相对覆盖率 C1 | 绝对语音占比 | 最长连续(相对) |
|---|---|---|---|
| 真空段（gain=1.0，2 个） | **0.317 / 0.379** | 0.024 / 0.037 | 360 / 720ms |
| 正常段 gain=1.0 | ≥ 0.425 | 0.20~0.47 | 360~2050ms |
| 正常段 gain=0.5 | ≥ 0.425 | 0.04~0.30 | 360~1870ms |
| 正常段 gain=0.3 | ≥ 0.437 | 0.008~0.14 | 250~2050ms |
| 正常段 gain=0.1 | ≥ 0.520 | 0.0 | 370~2050ms |

⇒ **相对覆盖率阈值 0.40** 能干净分开（真空段 ≤0.379 < 0.40 ≤ 正常段）。
用「最长连续语音（相对口径）」不行 —— 真空段的 C2 也有 360~720ms
（噪声突发凑够了连续性），与正常段重叠。

**最终空段拒切判据**（`_speech_ratio_ok()`）：
```
段内 p90 ≤ SPK_REL_MIN_SPEECH_DB(-60dBFS)  → 放行（整段极弱/数字静音）
否则 相对覆盖率 = mean(帧 > max(p90-18dB, -70dBFS)) ≥ 0.40 → 放行
否则 → 拒切（段继续累积）
```

### 10.4 改动 3 的**反相 bug**（实施中实测发现并修复）

初版实现按用户批准的「RMS 接近取 (L+R)/2、明显不同取 RMS 大路」写完后，
函数级测试（`diag_s10_stereo.py`）**T4 反相用例 FAIL**：
两路**反相**（R = −L）时两路 RMS **相等** ⇒ 只看 RMS 会误判成「平衡」
⇒ 取平均 ⇒ **信号完全相消**（实测输出 **−120dB = 数字静音**）。

⇒ 修复：新增 `_corr()`（皮尔逊相关系数），**corr ≤ −0.5 判为反相**
⇒ 强制走「取 RMS 大路」分支。
（工程教训：**RMS 相等 ≠ 内容相同**，只看能量判据会漏掉反相。）

函数级测试最终结果（`results/asr_diag/diag_s10_stereo.py`，6/6 PASS）：

| 用例 | 结果 | 关键数值 |
|---|---|---|
| T1 单声道原样返回 | PASS | len 16000 = 16000 |
| T2 L=R 取平均不损失 | PASS | out −14.02dB = in −14.02dB |
| T3 明显不同时取 RMS 大路 | PASS | out −10.48dB（L −10.48 / R −30.43） |
| T4 反相不被相消 | PASS | out **−10.42dB** vs 平均 **−120.00dB** |
| T5 EMA 平滑不抖动 | PASS | bal +20.1 → +16.1dB，瞬时翻转后仍选强路 |
| T6 全零输入不炸 | PASS | — |

⚠️ **反相分支不能只靠 RMS 判**这条，已写进 `audio_source.py` 的代码注释。

### 10.5 §9 修复方案的**实施差异**（与 §9.5 原提案不同）

§9.5 提案是「静音门限 = 段内 p90 − 12dB，**只取相对**」。
实际实施用了 `SIL_REL_MODE='max'`（= `max(相对, 绝对)`），**不是只取相对**：
* 背景声场景（用户实测）：段内 p90 = −13.9dB ⇒ 相对门限 −25.9dB
  **比绝对 −40dBFS 高** ⇒ `max` 取相对 ⇒ 效果与「只取相对」**完全一致**
  （实测回环 >12s 62.5% → 6.2%，与 §9.4 的「只取相对」数据逐位吻合）。
* 安静场景（麦克风、底噪低）：段内 p90 低 ⇒ 相对门限可能**低于**绝对 −40dBFS
  ⇒ `max` 取绝对 ⇒ **保留旧行为**，不会因为相对化而在极安静时误判静音。

⇒ 即 `max` 模式在背景声场景等价于「只取相对」，在安静场景等价于「只取绝对」，
**两种场景都拿到各自的最优行为**。`SIL_REL_MODE` 保留 `'abs'` / `'rel'` 两个
取值供回退与对照。

### 10.6 待补测（**已于 14:56~15:05 补齐，见 §11**）

原缺口：左右声道对比数据 + 回环静音分布。
14:56 用户「现在在播放视频」⇒ 已重采两段数据并完成分析，结论见 **§11**。

（保留原复现命令备查）
```
cd C://Users//Trekker-PTL//confucius4-openvino
.venv\Scripts\python.exe results\asr_diag\probe_loopback_stereo.py --seconds 30
.venv\Scripts\python.exe results\asr_diag\probe_loopback_120s.py --seconds 120
```

### 10.7 产物清单（`results/asr_diag/`，已被 `.gitignore` 第 73 行排除，不入库）

| 文件 | mtime | 内容 |
|---|---|---|
| `diag_s10_verify.py` | 13:39 | A/B 主脚本（真实 `due()`，3 组数据 × 2 方案） |
| `s10_verify.json` | 14:03 | A/B 结果（回环 + 真实演讲 + 增益扫描） |
| `diag_s10_scan.py` | 14:00 | 参数扫描（floor × drop 共 15 组 × 6 指标） |
| `s10_scan.json` | 14:03 | 扫描结果（含基线对照） |
| `diag_s10_cutsafe.py` | 13:41 | 切点安全（**第一版，判据口径有误**，见下方说明） |
| `s10_cutsafe.json` | 13:41 | 同上结果 |
| `diag_s10_cutsafe2.py` | 13:42 | 切点安全（**采用 C-108 官方口径**，有效） |
| `s10_cutsafe2.json` | 13:42 | 规则2 切点安全性 / 空段 / 短段 |
| `diag_s10_empty.py` | 13:40 | 空段疑点追查（绝对 vs 相对口径） |
| `diag_s10_trace.py` | 13:58 | 逐段打印真实实现内部判定状态 |
| `diag_s10_runlen.py` | 13:54 | 候选判据区分度（最长连续语音） |
| `diag_s10_discrim.py` | 13:59 | 候选判据区分度（覆盖率 / 动态范围） |
| `s10_discrim.json` | 13:59 | 区分度数据（相对覆盖率 0.317/0.379 vs ≥0.425） |
| `diag_s10_stereo.py` | 14:04 | 立体声混合函数级测试（T1~T6） |
| `probe_loopback_stereo.py` | 14:04 | 回环双声道采集探针（**待用户配合重跑**） |
| `loopback_stereo_probe.json` | 14:05 | 双声道探测结果（本次全零） |

⚠️ `diag_s10_cutsafe.py`（第一版）的安全判据写错了：把「切点前 0.5s 内
**存在** ≥300ms 静音」当成安全，而 C-108 官方口径是「切点前 0.5s **整窗**
最大帧 dB < −40dB」，且**只统计规则2 切点**。用错口径会得出「基线自身
危险切点 76/108」这种误导性结论（规则1 本来就不保证切在词间隙）。
**有效数据是 `s10_cutsafe2.json`**。

### 10.8 结论

1. **用户实测现象已修复**：真实回环数据上定稿间隔 **17.28s → 6.40s**，
   >12s 占比 **62.5% → 6.2%**，硬切段 **4 → 0**。
2. **回归无退化**：真实演讲 12 分钟，空段 0 → 0，>12s 0% → 0%，
   规则2 切点 6/6 安全 → **10/10 安全**。
3. **麦克风场景额外受益**：低电平（gain 0.3/0.1）>12s 从 67.4%/100%
   降到 **0%**。
4. **两个否定结论**（§10.3）已落档，避免后续重复踩坑。
5. **改动 3 的反相 bug** 已修（§10.4）；左右声道收益量化数据待用户配合（§10.6）。
6. **git 提交归属**：`live_caption/` 的改动按 ASR-003 归 **App 模块**提交；
   ASR 侧只提交本文件。

## §11 回环补测（用户 14:56「现在在播放视频」）+ **修正 §9/§10 的普适性表述**（2026-10-23 15:05）

### 11.1 触发

§10.6 遗留的补测：① 回环左右声道对比数据；② 回环静音分布。
用户 14:56 告知「现在在播放视频，可以采集了」⇒ 立即重采。

### 11.2 新采数据 1：30s 双声道（`loopback_stereo_probe_raw.npy`）

```
采集 30.0s  shape=(480000, 2)
db_L = -22.20   db_R = -22.41   差 0.21dB
corr(L,R) = 0.9182   （同相/相关 ⇒ 走 (L+R)/2 分支）
静音帧占比(-40dB): L 31.5%   R 31.5%
p90: L -18.1dB   R -18.9dB
旧策略(只取ch0) RMS -22.20dB   新策略 RMS -22.49dB
```

**改动 3 的收益量化**（同一判据下比较两种取单声道方式，真实 `due()`）：

| 判据 | 输入 | 切点 | 规则分布 | 空段 | 规则2危险 | 间隔 p50/p90/max | >12s |
|---|---|---|---|---|---|---|---|
| 基线(绝对) | 旧:只取ch0 | 4 | rule1×3 rule2×1 | 0 | 0 | 6.40/9.09/10.24 | 0 (0.0%) |
| 基线(绝对) | 新:立体声混合 | 4 | rule1×3 rule2×1 | 0 | 0 | 6.40/9.09/10.24 | 0 (0.0%) |
| 新判据(相对) | 旧:只取ch0 | 6 | rule2×3 rule1×3 | 0 | 0 | 5.76/6.40/6.40 | 0 (0.0%) |
| 新判据(相对) | 新:立体声混合 | 6 | rule2×3 rule1×3 | 0 | 0 | 5.76/6.40/6.40 | 0 (0.0%) |

⇒ **结论：在这段数据上，改动 3 对切段行为无影响**（两种输入结果**逐位相同**）。
原因是该视频的左右声道**高度相关**（corr=0.9182、RMS 差 0.21dB）
⇒ `(L+R)/2` 与只取 ch0 在能量/静音结构上几乎等价。
**改动 3 的价值是「防御性」的**：当左右声道内容确实不同（游戏、立体声影片、
分轨音频）时才起作用；本次素材无法量化其收益，但**函数级测试 T1~T6 全 PASS**
（§10.4），且反相 bug 已修 ⇒ **保留该改动，无回归风险**。

### 11.3 新采数据 2：120s 双声道 + 滑窗静音分布（`loopback_120s_probe_raw.npy`）

```
采集 120.0s  shape=(1920000, 2)   db_L=-22.2 db_R=-22.4 corr=0.9182
整体静音帧占比: 34.3%
帧 dB p10/p50/p90 = -50.6 / -32.8 / -22.4
5 秒窗静音占比: min 0.195 / p50 0.339 / max 0.504
5 秒窗最长连续静音: min 0.37s / p50 0.76s / max 1.88s
「绝对判据可工作」的窗占比: 95.8%
最长连续「绝对判据失效」: 5s
```

### 11.4 **关键对比：两段回环数据的差异**（`diag_s10_compare.py` / `s10_compare.json`）

| | D1（13:24 采集，用户报告现象时） | D2（14:56~15:05 采集，当前播放） |
|---|---|---|
| RMS | **−18.34dB** | **−26.19dB** |
| 帧 dB p1/p10/p50/p90/p99 | −76.0/−41.9/**−21.8**/−13.9/−11.6 | −54.1/−50.6/**−32.8**/−22.4/−15.4 |
| 静音帧占比(≤−40dB) | **12.2%** | **34.3%** |
| 其中数字静音(帧<−100dB) | 0.9% | 0.0% |
| 连续静音段数 | 157 | 310 |
| **≥800ms 静音段数** | **1** | **11** |
| ≥300ms 静音段数 | 8 | 39 |
| 最长连续静音 | 2220ms | 1880ms |
| A 基线（绝对阈值） | 切点 8，间隔 p50 **17.28s**，>12s **62.5%** | 切点 20，间隔 p50 **6.40s**，>12s **0.0%** |
| B 新判据（相对化） | 切点 16，间隔 p50 **6.40s**，>12s **6.2%** | 切点 21，间隔 p50 **6.40s**，>12s **0.0%** |

### 11.5 **修正 §9.3 / §10 的普适性表述**（重要）

§9.3 写的是「用户实测场景是 (b)：回环 ⇒ 持续背景声 ⇒ 永远跌不到 −40dBFS
⇒ 绝对判据必然失效」。**这段表述过强**，需修正为：

**修正后的结论**：
1. 失效的**直接条件**不是「回环」这个音源，而是
   **「该段音频里没有 ≥800ms 的连续静音」**。
   D1 有 310ms~2.2s 的零散静音但只有 **1 个** ≥800ms 的 ⇒ 规则2 的
   0.8s 门槛基本不满足 ⇒ 退化到 20s 硬切。
2. **视频内容本身决定一切**：D1（用户报告现象时那段）RMS −18.3dB、
   静音帧 12.2% ⇒ 背景声很响、几乎无静音 ⇒ 绝对判据失效；
   D2（当前播放）RMS −26.2dB、静音帧 34.3%、≥800ms 静音 11 个
   ⇒ 绝对判据**能工作** ⇒ **基线本身就是 6.40s / 0% >12s**。
   ⇒ **同一套代码、同一个音源，基线行为可以天差地别**，取决于素材。
3. **新判据在两种素材上都成立**（D1：62.5%→6.2%；D2：0%→0%，且切点数
   20→21、间隔 p90 7.04→6.40 略优）⇒ **不依赖素材类型，是普适的**。
   这正是「相对化」的价值：**在绝对判据失效的素材上救回，在能工作的素材上
   不劣化**。
4. ⚠️ 因此 §9 的「根因」表述应理解为「**在用户当时那段素材上的根因**」，
   而非「回环这个音源的固有属性」。**撤回 §9.3 中「回环 ⇒ 绝对判据必然失效」
   的普适性推断**（该推断对 D1 成立，对 D2 不成立）。

### 11.6 对用户的实际意义

- 用户若再次看到 >12s，**很可能又换了一段无静音的素材**（或同一视频的不同片段）。
- 新判据（已实施）能覆盖这类素材：即使全程只有零散 300ms 静音，也能切出 6.4s 间隔。
- **若 D2 这类素材是常态**（有静音段），那么用户报告的 >12s 更可能是
  **另一个原因**（如视频里那段时间本身是高强度的背景音/音乐），
  建议下次复现时先跑 `probe_loopback_120s.py` 看「≥800ms 静音段数」。

### 11.7 产物清单（`results/asr_diag/`）

| 文件 | mtime | 内容 |
|---|---|---|
| `probe_loopback_stereo.py` | 14:04 | 双声道采集探针（复用） |
| `loopback_stereo_probe.json` | 14:57 | 30s 双声道探测（**有信号**：db_L=−22.2/corr=0.9182） |
| `loopback_stereo_probe_raw.npy` | 14:57 | 30s 原始立体声 (480000, 2) |
| `diag_s10_stereo_gain.py` | 15:00 | 改动 3 收益量化（Q1/Q2） |
| `s10_stereo_gain.json` | 15:00 | 改动 3 收益结果（两输入逐位相同） |
| `probe_loopback_120s.py` | 15:01 | 120s 采集 + 5 秒窗静音分布 |
| `loopback_120s_probe.json` | 15:03 | 120s 滑窗统计（静音 34.3%/95.8% 窗可工作） |
| `loopback_120s_probe_raw.npy` | 15:03 | 120s 原始立体声 (1920000, 2) |
| `diag_s10_compare.py` | 15:04 | D1 vs D2 对比 |
| `s10_compare.json` | 15:04 | 对比结果（关键：≥800ms 静音 1 个 vs 11 个） |

### 11.8 结论

1. **改动 3 的收益无法用当前素材量化**（左右声道 corr=0.9182，高度相关 ⇒
   两种取法逐位相同）⇒ 保留为**防御性**改动，无回归风险。
2. **§9.3 的「回环 ⇒ 绝对判据必然失效」过强，已在 §11.5 修正**：
   失效的真正条件是「该段音频没有 ≥800ms 连续静音」，由**素材内容**决定。
3. **新判据在两种素材上都成立**（D1 62.5%→6.2%；D2 0%→0%）⇒ 普适。
4. 用户下次复现 >12s 时，建议先跑 `probe_loopback_120s.py` 看
   「≥800ms 静音段数」，即可判断是不是同一类问题。

## §12 ASR-004：§10 新切段规则的 61 分钟质量验证（2026-10-24 12:28）

### 12.0 本章范围与口径
ASR-004 要求三件事：① 61 分钟**真实 `Segmenter`** + 交付配置 GPU INT8 的 **A/B 逐段转写**；
② 同一素材重跑 **C-108 空段校验**（hang 0.8/0.6/0.5 三档，A/B 都要跑，gain 0.3/0.1 补**相对口径**）；
③ 产物路径写进 STATUS。
**WER 不在本模块计算** —— 交 reviewer 用 MiniMax baseline 跑 `compare_wer` + `paired_bootstrap` 独立复核。

**A/B 定义（env 切换，真实实现自己切换行为）**
- A（旧行为）：`LIVECAP_SIL_REL=0  LIVECAP_SPK_REL=0  LIVECAP_MIN_REL_COVER=0`
- B（新行为）：默认（相对静音门限 p90−12dB + 相对语音守卫 p90−18dB & >−70dBFS + 相对覆盖率空段拒切 ≥0.40）

**空段两种口径（都写清，不混用）**
- **绝对口径**：段内帧 > −35dBFS 的占比 < 10%（C-108 原版）
- **相对口径**：段内**相对语音覆盖率** < 0.40（= `_speech_ratio_ok` 判据）

### 12.1 ② C-108 空段校验（**已完成**）
- 产物：`results/asr_diag/asr004_c108_empty.json`（1 个文件，mtime 2026-10-24 10:36，wall **326.2s**）
- 素材：`test_audio/<redacted>.wav`，3671.19s（61.19 min）
- 覆盖：3 个 gain × 3 个 hang × A/B = **18 组**，全部跑完
- 脚本：`results/asr_diag/asr004_c108_empty.py`（**直接调用真实 `seg.due(acc)`**，判据明细只用于事后解释）

| gain | hang(s) | A 段数 | A 绝对空段 | A 相对空段 | A >12s | B 段数 | B 绝对空段 | B 相对空段 | B >12s |
|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 0.8 | 535 | 1 | 4 | 1.31% | 553 | 5 | 0 | 0.18% |
| 1.0 | 0.6 | 548 | 1 | 7 | 0.73% | 584 | 8 | 0 | 0.0% |
| 1.0 | 0.5 | 569 | 1 | 8 | 0.7% | 609 | 8 | 0 | 0.16% |
| 0.3 | 0.8 | 294 | 75 | 1 | 45.24% | 641 | 276 | 0 | 0.16% |
| 0.3 | 0.6 | 296 | 74 | 1 | 45.27% | 706 | 328 | 0 | 0.0% |
| 0.3 | 0.5 | 298 | 74 | 1 | 45.3% | 753 | 357 | 0 | 0.0% |
| 0.1 | 0.8 | 180 | 180 | 0 | 99.44% | 622 | 622 | 0 | 0.0% |
| 0.1 | 0.6 | 180 | 180 | 0 | 99.44% | 639 | 639 | 0 | 0.0% |
| 0.1 | 0.5 | 180 | 180 | 0 | 99.44% | 651 | 651 | 0 | 0.0% |

**结论（对应 ASR-004 验收「C-108 三档空段数 B ≤ A」）**
- **相对口径：9 档中 B 全部为 0，A 为 0~8** ⇒ **B ≤ A 成立，且 B 全部优于或等于 A**。
- gain=1.0 三档：A 相对空段 4 / 7 / 8 ⇒ **B 全部 0**。
- gain=0.3 三档：A 相对空段 1 / 1 / 1 ⇒ **B 全部 0**。
- gain=0.1 三档：A 相对空段 0 / 0 / 0 ⇒ **B 全部 0**（持平）。
- **>12s 占比：9 档中 B 全部 ≤ A**（gain=0.3：45.24% → **0.16%**；gain=0.1：99.44% → **0.0%**；gain=1.0 hang0.8：1.31% → **0.18%**）。
- ⚠️ **绝对口径在低电平下失真**：gain=0.3/0.1 时 B 的绝对空段数反而**更高**（276~622）。
  这**不是 B 变差**，而是绝对 dBFS 口径在低电平下无法区分「轻声说话」与「安静」——
  与 §10 的否定结论一致（绝对口径不可用于空段拒切）。**判定一律用相对口径**。

### 12.2 ① 61 分钟 A/B 逐段转写（**进行中**）
- 脚本：`results/asr_diag/asr004_ab_chunked.py`（**可续跑分段版**）+ `results/asr_diag/asr004_ab_part.py`（单分段执行器）
- 引擎：**交付配置 GPU INT8**（`OVEngine('gpu_int8')`：enc `ov-encoder-segment-reviewer-int8asym` / dec `ov-int8-past` / device `GPU.0`）
- 喂音粒度：`audio_source.BLOCK_MS=100ms`（与 App 实时路径一致）；参数 `max_new_tokens=32, rollback_punctuation=False, enable_hallucination_reset=False, adaptive_budget=True`
- 切点判定：**一律直接调用真实 `seg.due(acc)`**；`rule` 字段只是**事后解释**标签
- 分段：16 段 × 240s。每段末尾强制 flush（rule 标 `*_flush`）⇒ 段数略多于整跑，
  但 **A/B 用同一套分段 ⇒ 对比公平**；对 reviewer 算 WER 的影响仅是切点位置略有差异
- 日志：`results/asr_diag/logs/asr004_chunked3.log`；分段产物：`reports/asr004_ab/parts/{A,B}_NNN.jsonl`
- 合并产物（跑完后）：`reports/asr004_ab/{segments,summary,transcript}_{A,B}.{json,json,txt}`

⚠️ **本轮踩坑（已修，记录在案）**
1. **长跑作业被外部回收**：单进程跑满 61 分钟被外部信号杀死 3 次（err 为空、无 traceback ⇒ 非脚本自身报错）。
   对照实验结论：`run_in_background` 里再套 `nohup`/`&`/`setsid`/`DETACHED_PROCESS` 起的**孙进程都会随任务结束被回收**；
   **唯一可靠写法 = 把长跑 python 进程本身作为后台任务主体**（已用心跳进程实测验证）。
2. **chunked 续跑判定 bug（已修）**：原判据「文件存在且行数>0 ⇒ 已完成」会把**被杀到一半**的段静默跳过。
   实测 `A_000.jsonl` 只有 2 行、末条 `end_s=10.24s`，而该段应覆盖 0→240s
   ⇒ 改为 `part_complete()`：**校验末条 `end_s` 是否到达分段末尾**（容差 2s）。
3. **A 组单进程产物已留档**：`reports/asr004_ab/singleproc_segments_A.json` / `singleproc_summary_A.json` /
   `singleproc_transcript_A.txt`（11:54 落盘，534 段 / rule1 510 + rule2 24 / wall 3763s）
   ⇒ 可与分段版 A 组**交叉校验**（切点数应一致，文本应基本一致）。

### 12.3 ① 61 分钟 A/B 逐段转写（**已完成**，2026-10-24 17:24）

**产物（3 组 × 2 = 6 个文件，mtime 2026-10-24 15:14）**
- `reports/asr004_ab/segments_A.json`（145,669 B）/ `summary_A.json`（1,173 B）/ `transcript_A.txt`（74,037 B）
- `reports/asr004_ab/segments_B.json`（148,404 B）/ `summary_B.json`（1,057 B）/ `transcript_B.txt`（74,247 B）
- 分段原始产物：`reports/asr004_ab/parts/{A,B}_000..015.jsonl`（32 个文件）
- 日志：`results/asr_diag/logs/asr004_chunked3.log`
- 墙钟：A 组 2556s / B 组 2284s（**质量作业，计时不作数**，summary 里 `timing_valid=false`）

**A/B 摘要（逐段产物原始字段）**

| 指标 | A（旧行为） | B（新行为） | 方向 |
|---|---|---|---|
| 段数 | 538 | 558 | — |
| 总词数 | 11,420 | 11,385 | **−35 词（−0.31%）** |
| rule1（静音中点切） | 503 | 509 | — |
| **rule2（静音尾切）** | 21 | **36** | **B +15（3.9% → 6.5%）** |
| 硬切（max，20s） | 0 | 0 | 持平 |
| flush 段（分段边界产物） | 14 | 13 | — |
| **>12s 段数** | **6（1.12%）** | **1（0.18%）** | **B 更好** |
| <2s 段数 | 3 | 7 | B 略多（切得更碎） |
| 段长 p50 | 6.40s | 6.40s | 持平 |
| 段长 max | 17.92s | **14.08s** | **B 更好** |
| 空文本段 | 1 | **0** | **B 更好** |

**结论**
- **B 的最长段从 17.92s 降到 14.08s，>12s 占比从 1.12% 降到 0.18%（6 段 → 1 段）**
  ⇒ §10 的改动在 61 分钟全长上**确实改善了「定稿间隔过长」**，且**没有引入硬切**（max 仍为 0）。
- **规则2 切点从 21 增到 36**：B 用**相对静音门限**（段内 p90−12dB）代替绝对 −40dBFS，
  ⇒ 在背景电平偏高的素材上能识别出更多真实静音尾 ⇒ 这是**预期行为**，不是缺陷。
- **总词数只差 35 词（−0.31%）** ⇒ 两组转写内容基本一致，**文本层面无实质变化**
  （WER 判定仍交 reviewer）。
- **A 组交叉校验通过**（分段版 vs 单进程版，`reports/asr004_ab/singleproc_*`）：
  - part 0 内（0→240s）**前 36 段切点与文本逐位完全相同**（36/36 文本完全一致）；
  - 唯一差异：分段版末尾多一个 `short_flush` 段（234.88→240.00）= 分段边界强制 flush 的预期产物；
  - ⇒ **分段化没有改变切段行为**，A/B 对比口径可信。
- **时间轴自检**：A/B 两组均**单调递增、无缝隙**、覆盖 0→3665.9s / 3665.3s（61 分钟完整）
  ⇒ 交付给 reviewer 按时间轴做全局对齐算 WER 是可行的。

### 12.4 本轮踩坑与修复（已修，记录在案）
1. **长跑作业被外部回收**（61 分钟跑批被杀 3 次，err 为空、无 traceback ⇒ 非脚本自身报错）。
   对照实验：`run_in_background` 里再套 `nohup`/`&`/`setsid`/`DETACHED_PROCESS` 起的**孙进程**
   都会随后台任务结束被回收；**唯一可靠写法 = 把长跑 python 进程本身作为后台任务主体**。
2. **chunked 续跑判定 bug**：原判据「文件存在且行数>0 ⇒ 已完成」会把**被杀到一半**的段静默跳过
   （实测 `A_000.jsonl` 只到 10.24s / 应到 240s）⇒ 改为校验末条 `end_s` 是否到段末（容差 2s）。
3. **`merge_group()` 漏加 part 偏移**（并行实例 15:15 修复）：分段版 `start_s/end_s` 是**段内局部时间**，
   合并时必须加 `offset = part_idx * 240s` ⇒ 否则 16 段全叠在 0→240s，reviewer 无法按时间轴对齐。
   **修复原则（省机时的关键）**：分 part 产物全部落盘完整时，缺陷只在合并步骤 ⇒
   **只重合并、不重跑推理**（省掉约 80 分钟机时）。
   **合并后自检口径**：段数 / `rule_counts` / 段长 p50 必须与旧产物**逐位一致** ⇒ 只允许时间轴变。

## §13 ASR-005：Qwen3-ASR-0.6B → NPU INT8/INT4（2026-10-24 12:28）

### 13.0 任务与阶段
用户指派：**沿用 Confucius4-R2T2 的方法，把 Qwen3-ASR-0.6B 做成 NPU 上能运行的 INT8 和 INT4 版本**，
作为更小、更快的 ASR 候选。阶段：**P0 基准 → P1 OV 导出 → P2 量化 → P3 验收**；
**P0 末、P2 末各停一次等 reviewer 复核（最多 30 分钟）**。
工作目录：`C://Users//Trekker-PTL//qwen3asr_06b`（独立 venv）。

### 13.1 ★ 关键架构发现：**R2T2 本身就是 Qwen3-ASR 系列**
`confucius4-openvino/models/hf/config.json` 实测：
`model_type=qwen3_asr`、`architectures=["Qwen3ASRForConditionalGeneration"]`、
含 `thinker_config.audio_config` ⇒ **R2T2 不是别的架构，就是 Qwen3-ASR**（更大一档）。

逐项对比（`models/hf` vs `qwen3asr_06b/models/Qwen3-ASR-0.6B`）：

| 项 | R2T2 | 0.6B | 是否相同 |
|---|---|---|---|
| `model_type` / architectures | qwen3_asr / Qwen3ASRForConditionalGeneration | 同 | ✅ |
| audio `d_model` | 1024 | **896** | ❌ 更窄 |
| audio `encoder_layers` | 24 | **18** | ❌ 更浅 |
| audio `encoder_attention_heads` | 16 | **14** | ❌ |
| audio `output_dim` | 2048 | **1024** | ❌ |
| audio `n_window_infer` | 800 | 800 | ✅ |
| audio `conv_chunksize` | 500 | 500 | ✅ |
| audio `downsample_hidden_size` | 480 | 480 | ✅ |
| text `hidden_size` | 2048 | **1024** | ❌ |
| text `num_hidden_layers` | 28 | 28 | ✅ |
| text heads / kv_heads | 16 / 8 | 16 / 8 | ✅ |
| text `vocab_size` | 151936 | 151936 | ✅ |
| `tie_word_embeddings` | True | True | ✅ |

⇒ **架构完全同构，只有宽度/层数不同** ⇒ ASR-005 P1/P2 的整套 OV 导出/量化经验
（整段全局注意力 encoder + `n_valid` 端口、`inputs_embeds` decoder、NPUW_LLM、AWQ INT4 配方）
**几乎可原样复用 R2T2 的脚本**，只需改 config/权重路径与动态维度上界。
**这是 ASR-005 风险大幅下降的关键依据。**

已确认的 R2T2 交付 IR 端口（`models/ov-encoder-segment-reviewer`，OV 实读）：
- 输入 `input_features [?,?,?] f32`（交付时为 `[1,128,2400]` = 24 块 × 100 帧）
- 输入 `n_valid [?] i32`（有效 encoder token 数 = `aftercnn_len(frames)`）
- 封装见 `segment_encoder_backend.py`（`SegmentEncoderOVBackend`）
⇒ 0.6B 沿用同一套（`output_dim` 2048→1024 需同步改）。

### 13.2 P0 基准（**进行中**）
**模型版本**：`Qwen/Qwen3-ASR-0.6B`，sha `5eb144179a02acc5e5ba31e748d22b0cf3e303b0`，
权重 `models/Qwen3-ASR-0.6B/model.safetensors`（1,876,091,704 B，10:46 落盘）。
**环境**：独立 venv `qwen3asr_06b\.venv`（Python 3.12.10 / torch 2.11.0+cu128 CUDA True /
transformers 4.57.6 / qwen-asr 0.0.6，`qwen_asr` 源码拷到 `vendor\` 并把 `nagisa` 改可选）。

**P0 要交两份参照（都在 61 分钟 <redacted> 上）**
1. **离线参照**：`scripts/p0_torch_ref.py --mode offline`
   - 官方 `MAX_ASR_INPUT_SECONDS=1200`（20 分钟）**会 OOM**（全局注意力一次要 **14.42 GiB**，
     本机 RTX 5050 只有 8GB）⇒ 自己用**官方 `split_audio_into_chunks`** 切 120s 块（31 块），
     **逐块**调用官方 `transcribe()`；单块 OOM ⇒ `empty_cache` 重试 3 次 → 递归细分成两半（深度≤3）
   - **断点续跑**：`results/p0_offline/offline_chunks.jsonl`（按块起始时间跳过已完成块）
   - 实测进度：15/31 块，**RTF 0.1924**（⇒ 61 分钟约 12 分钟）
2. **段级流式参照**：`scripts/p0_stream_seg.py`
   - 官方 `streaming_transcribe` / `init_streaming_state` **仅支持 vLLM 后端**（本机无 vLLM）
     ⇒ 用 transformers 后端**复刻同一语义**（口径写进产物 `stream_note`）
   - **为什么不是「每 640ms 重喂累计音频」**：实测 2 分钟 → 188 步 → RTF **1.41**（61 分钟要 1.4 小时）
     且无前缀缓存 ⇒ 音频 token 线性累积 ⇒ **CUDA OOM**；
     更糟：滑动回看窗口 + **不匹配**的长前缀 ⇒ 模型判定「这段已说过」⇒ **输出退化成单个 `'.'`**
     （实测对照：音频=最近 20s + prefix=**对应**该 20s ⇒ 正常输出；
     音频=最近 20s + prefix=**不匹配**的长历史 ⇒ 输出 `'.'`）
   - ⇒ 改成**段级流式**（照 R2T2 真实架构）：段内每 640ms 重喂**该段累计**音频（≤20s），
     前缀回退 `unfixed_token_num=5`（前 2 块不用前缀），段尾 flush 预算 64，
     切点用**真实 `live_caption_app.Segmenter`**（与 App 实时路径逐点一致）
   - **1 分钟冒烟 PASS**：RTF **0.6724**、10 段（rule1 8 / rule2 1 / flush 1）、164 词，
     段边界 `6.4 / 10.2 / 16.6 / 23.0 / 30.7 / 37.1 / 43.5 / 49.9 / 57.0 / 60.0`
     ⇒ **与 R2T2 段边界完全一致**，文本连贯
   - **断点续跑**：`results/p0_stream/stream_seg_chunks.jsonl`（按段起点跳过）

**P0 产物交 reviewer 算 WER（全局对齐）**，本模块不出 WER 数字。

### 13.3 P0 阶段踩坑记录（勿再踩）
1. `Qwen3ASRModel.from_pretrained` 的 `backend` / `device` / `dtype` **不是它的 kwarg**
   （会转发给 `AutoModel.from_pretrained` ⇒ `TypeError: ... unexpected keyword argument 'device'`）
   ⇒ 正确用法：**加载之后**用 `m.model = m.model.to('cuda')`。
2. 官方 `transcribe()` 只接受 `(np.ndarray, sr)` **元组**或路径，**裸 ndarray 被拒**。
3. 官方 `parse_asr_output` 在无 `<asr_text>` 标签时把输出当纯文本；强制语言时整串当纯文本。
4. 官方 prompt：`chat_template(system=context, user=<audio>, add_generation_prompt=True)` + `language English<asr_text>`。
5. **同机并发会严重污染 GPU 作业** ⇒ 测速必须独占（本轮 P0 与 ASR-004 分用
   NVIDIA CUDA / Intel GPU.0 插件，**互不抢显存**，可并行）。

### 13.5 ★ P1 OV 导出（**已完成 encoder + decoder + 端到端验证**，2026-10-24 17:31）

**关键前提（已实测确认）**
- 0.6B 的 `audio_tower` 结构与 R2T2 **完全一致**（`conv2d1/2/3`、`conv_out`、
  `positional_embedding`、`layers`、`ln_post`、`proj1/proj2`、`act` 全在）
  ⇒ **`reviewer/export_segment_encoder.py` 可原样复用**（它已参数化 `<model_dir> <out_dir>`）
- 0.6B `output_dim=1024` == text `hidden_size=1024` ⇒ encoder 输出**可直接**
  `masked_scatter` 进 text embeds，**不需要额外投影**（与 R2T2 同）

**交付物 1：encoder（整段全局注意力，FP16 压缩）**
- 实际直接用 **`reviewer/export_segment_encoder.py`**（仓库 venv，CPU 导出，不占 GPU）
- 产物：`qwen3asr_06b/models/ov-encoder-06b-fp16/openvino_encoder_model.{xml,bin}`
  （xml 745,555 B / bin 372,778,460 B，mtime 12:31）
- 端口（OV 实读）：输入 `input_features [?,?,?] f32` + `n_valid [?] i32`
  ⇒ **与 R2T2 交付 IR 完全一致**
- **encoder 精度（OV vs torch，9 个长度，cos mean/min）**：

| sec | 0.64 | 4.00 | 7.68 | 8.00 | 9.60 | 12.80 | 16.00 | 20.00 | 23.90 |
|---|---|---|---|---|---|---|---|---|---|
| mean | 0.999994 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| min | 0.999965 | 1.000000 | 1.000000 | 0.999999 | 0.999997 | 0.999998 | 1.000000 | 0.999995 | 0.999999 |

**交付物 2：decoder（`inputs_embeds` 版、无状态、静态形状，FP16 压缩）**
- 脚本：`qwen3asr_06b/scripts/p1_export_decoder.py`
  （照搬 R2T2 `c069g_export_stage3_fp16.py`，只改模型路径 / `HIDDEN` 2048→**1024** / 输出目录）
- 产物：`qwen3asr_06b/models/ov-dec-06b-embed-fp16/openvino_decoder_model.{xml,bin}`
  （xml 2,198,913 B / bin 1,192,582,552 B，mtime 17:28，共 1,139.4 MiB）
- 端口：输入 `inputs_embeds [1,512,1024]` → 输出 `linear_196:0 [1,1,151936]`
- **无 stateful 参数**：`310 params, stateful-looking=0`（无 ReadValue/Assign）
  ⇒ 图内不产生 KV 状态 ⇒ **可走 NPUW_LLM**
- NPUW 风险算子：`ShapeOf×1, CumSum×1, ScatterNDUpdate×1, Range×1`
- 导出路径：`torch.export`（`ov.convert_model(ep)`）
- **decoder 自检（CPU FP16）**：cos **0.999939**，argmax 一致 ✓

**交付物 3：端到端 teacher-forcing 验证（ASR-005 要求 cos ≥ 0.999 / top1 ≥ 99%）**
- 脚本：`qwen3asr_06b/scripts/p1_verify_e2e.py`；产物：`qwen3asr_06b/results/p1_verify.json`
- 链路：`mel → OV encoder → hidden[1,N,1024] → masked_scatter 进 text embeds → OV decoder → logits`
  （**照抄官方 `Qwen3ASRThinker.forward` 的拼装逻辑**，不是近似拼装）
- 结果（3 个代表段）：

| 段 | encoder cos mean/min | decoder cos | top1 | ov argmax / ref argmax |
|---|---|---|---|---|
| seg000_0_6 | 1.0 / 1.0 | 0.999983 | ✓ | 198 / 198 |
| seg172_2812_2836 | 1.0 / 0.999999 | 0.999997 | ✓ | 198 / 198 |
| tail_3600_3616 | 1.0 / 1.0 | 0.999994 | ✓ | 1406 / 1406 |

- **汇总**：`enc_cos_min_overall=0.999999`、`dec_cos_min_overall=0.999983`、
  **`top1_match_rate=1.0`** ⇒ **`pass_cos=true`、`pass_top1=true`** ✅

### 13.6 ★ P0 基准（**已完成**，2026-10-24 20:07）—— **按 ASR-005 停下等 reviewer 复核**

**模型版本**：`Qwen/Qwen3-ASR-0.6B`，sha `5eb144179a02acc5e5ba31e748d22b0cf3e303b0`
**环境**：独立 venv `qwen3asr_06b/.venv`（Python 3.12.10 / torch 2.11.0+cu128 CUDA True /
transformers 4.57.6 / qwen-asr 0.0.6）
**素材**：`test_audio/260902_SPE_audio.wav`，**61.00 分钟（3660.0s）**

**交付物 1：离线参照**
- 产物：`qwen3asr_06b/results/p0_offline/`（4 文件，mtime 12:35）
  - `offline_transcript.txt`（60,762 B）/ `offline_segments.json`（65,076 B）
  - `offline_chunks.jsonl`（63,647 B，断点续跑用）/ `p0_summary.json`（1,373 B）
- 切块：**官方 `split_audio_into_chunks`** 切 **31 块 × 120s**（低能量边界 ⇒ 拼接后逐样本一致）
- **OOM 事件：0**（`oom_events: []`）⇒ 120s 块在 8GB RTX 5050 上安全
- 指标：wall **823.1s**，**RTF 0.2249**，chars 60,760，词数 **11,125**，段数 31
- 时间轴：0.0 → 3660.0（**完整覆盖 61 分钟**），空文本段 0

**交付物 2：段级流式参照**
- 产物：`qwen3asr_06b/results/p0_stream/`（5 文件，mtime 18:07）
  - `stream_transcript.txt`（74,239 B）/ `stream_segments.json`（136,208 B）
  - `stream_seg_chunks.jsonl`（118,497 B，断点）/ `p0_stream_summary.json`（1,264 B）
    / `p0_stream_progress.json`（163 B）
- 口径（写进产物 `stream_semantics`）：**段级流式** —— 段内每 640ms 增量解码
  （重喂该段累计音频，≤20s）+ 前缀回退 `unfixed_token_num=5`（前 2 块不用前缀）
  + 官方自适应 `max_new_tokens` + 段尾 flush 预算 64；
  切点由**真实 `live_caption_app.Segmenter`** 判定（与 App 实时路径逐点一致）
- 指标：wall **2470.1s**，**RTF 0.6749**，段数 **552**
  （rule1 517 / rule2 34 / flush 1），步数 4,726，词数 **11,425**，空文本段 0
- 时间轴：0.0 → 3660.0（**完整覆盖**）
- ⚠️ `rtf_this_run=0.8167`（含续跑前的重启开销）⇒ **以 `rtf=0.6749` 为准**

**P0 检查点（ASR-005 要求「P0 结束停一次等 reviewer 复核」）**
- ✅ **P0 已完成，两份参照均已落盘**
- ⇒ **本模块在此停下，等 reviewer 复核（最多 30 分钟）**
- 请 reviewer 用 **MiniMax baseline** 对下面两份参照做**全局对齐**算 WER：
  - 离线参照：`qwen3asr_06b/results/p0_offline/offline_transcript.txt`
  - 流式参照：`qwen3asr_06b/results/p0_stream/stream_transcript.txt`
- **两份参照的词数只差 300 词（11,125 vs 11,425，+2.7%）** ⇒ 质量上限大致相同，
  流式的价值在于**切点与 R2T2 逐点一致**（可直接对照 App 实时路径）

**为什么不用「每 640ms 重喂累计全部音频」**（P0 踩坑，已记录在案）
- 实测 2 分钟 → 188 步 → 墙钟 169s ⇒ **RTF 1.41**（61 分钟要 1.4 小时）
- 且 transformers 后端**无前缀缓存** ⇒ 音频 token 线性累积 ⇒ **CUDA OOM**
- 更糟：滑动回看窗口 + **不匹配**的长前缀 ⇒ 模型判定「这段已说过」⇒ **输出退化成单个 `'.'`**
  （实测对照：音频=最近 20s + prefix=**对应**该 20s ⇒ 正常输出；
  音频=最近 20s + prefix=**不匹配**的长历史 ⇒ 输出 `'.'`）
- ⇒ 改成**段级流式**（照 R2T2 真实架构）后 RTF 降到 **0.6749**，且 1 分钟冒烟的段边界
  与 R2T2 **完全一致**

**P0 → P1 的衔接状态**：P1 的 encoder / decoder 导出 + 端到端验证**已提前完成**（见 §13.5），
但**P2 量化与 P3 验收等 reviewer 对 P0 复核后再推进**（遵守「P0 末停一次」的检查点约定）。

### 13.4 下一步（P0 完成后）
- **P1 OV 导出**（照搬 R2T2 经验）：
  - encoder 导出**整段全局注意力** IR（输入 mel + n_valid）；optimum 默认分窗注意力是错的（R2T2 根因①）
  - 窗口计数按 `mel_len//800`（根因②）；`max_new_tokens` 用官方自适应规则（根因③）
  - decoder：GPU 用 stateful IR；NPU 用**只保留 `inputs_embeds` 端口**的标准 KV 形式走 NPUW_LLM，
    动态维度设上界或静态化，每样例前 `reset_state()`
  - 每步 teacher-forcing 与 torch 对比（cos ≥ 0.999、top1 ≥ 99%）
  - 参考脚本：`c039_validate_segment_encoder.py`（整段 encoder 验证）、`c069g_export_stage3_fp16.py`
    （inputs_embeds 版导出）、`c057g_export_encoder_int8.py`（INT8 量化）
    ⚠️ `c023_export_window_encoder.py` 是**分窗版**，**不是**要的那个
- **P2 量化**：INT8_SYM 按通道（R2T2 的 NPU 交付配方）；INT4 用 R2T2 验证配方
  （按通道 + AWQ + scale estimation，必要时 ratio 0.8 + hessian），
  校准集**不能含评测音频**（0–12 分钟校准，≥12 分钟评测）；GPU/NPU 各一版，**NPU 是主要目标**
- **P3 验收**：61 分钟 WER（对 0.6B torch 参照 + R2T2 交付基线做配对 bootstrap）；
  NPU RTF P50/P95（多次 fresh 进程，**持机器锁**）+ 首字延迟 + 内存；
  最终对比表（0.6B INT8/INT4 × GPU/NPU vs R2T2 交付版）

## §14 ASR-004 ① 完成 + 修好合并缺陷；ASR-005 P0 流式参照重新启动（2026-10-24 15:30）

> `last_ack: ASR-005`（本轮**无新纠偏**，`CORRECTIONS_ASR.md` 最大编号仍是 ASR-005）。
> 本节只追加，不回头改旧章节；§12.2 与 §13.2 的「进行中」状态在本节更新。

### 14.0 本轮背景
上次检查（12:25）时两条长跑都在跑。现在：
- **ASR-004 ①**（61 分钟 A/B 逐段转写）**已跑完并合并**（13:42）；
- **ASR-005 P0 离线参照已完**（12:35），**但段级流式参照此前根本没跑**（见 14.4）。

### 14.1 ⚠️ 发现并修复一个**交付级缺陷**：`merge_group()` 漏加 part 偏移

**现象**：`reports/asr004_ab/segments_A.json` 里 `A[37]` 的 `start_s` 又是 `0.0`
（`A[36].end_s=240.0` ⇒ 时间轴**重新从头开始**）⇒ 全文件时间轴**重复了 16 次**。

**根因**（读代码定位）：
- `results/asr_diag/asr004_ab_part.py:85-86, 123-124`：`start_s/end_s` 由
  `(F - A - C) / SR` 计算，`F/A/C` 都是**分段内**的采样点
  ⇒ 输出是**分段内局部时间**（实测 `parts/A_001.jsonl` 首行 `start_s=0.0`、末行 `end_s=240.0`）；
- `results/asr_diag/asr004_ab_chunked.py:127-141` `merge_group()`：逐个读 part 的行
  **原样 append**，**没有加 `offset = part_idx * PART_SEC`**
  ⇒ 合并后 16 个 part 的时间轴全部叠在 0→240s 上。

**为什么必须修**：reviewer 要按**时间轴对齐**算 WER（ASR-004 验收口径），
时间轴错乱 ⇒ A/B 的对齐基准不成立 ⇒ WER 无意义。

**为什么不用重跑**：`parts/{A,B}_NNN.jsonl` **32 个文件全部落盘且完整**
（`part_complete()` 已校验末条 `end_s` 到达段末）⇒ 推理结果是完好的，
缺陷**只在最后的合并步骤** ⇒ 只重平移时间戳并重出产物，**不重跑任何推理**
（省掉约 80 分钟机时）。

**修复脚本**：`results/asr_diag/asr004_ab_remerge.py`（**本轮新建**）
- 只读 `parts/*.jsonl`，按 `offset = part_idx * 240` 平移 `start_s/end_s`，
  重算 `duration_s`，并加 `part_idx` 字段（便于 reviewer 按段溯源）；
- **自检**（脚本内检查项，输出见下）：段数、`rule_counts`、`seg_dur_p50` 必须与旧产物一致
  ⇒ 只允许时间轴变；
- 旧产物备份为 `reports/asr004_ab/{segments,transcript}_{A,B}.*.bak_prefix`。

**自检输出（实际运行结果）**
```
[remerge] part 文件数: {'A': 16, 'B': 16}
[remerge] group A: n_segs 538->538 (same=True) rules same=True p50 same=True
[remerge] group A: 538 段, 时间轴 0.0..3665.92s, rules={'rule1': 503, 'rule2': 21, 'short_flush': 9, 'other_flush': 3, 'guard_block_flush': 2}
[remerge] group B: n_segs 558->558 (same=True) rules same=True p50 same=True
[remerge] group B: 558 段, 时间轴 0.0..3665.28s, rules={'rule1': 509, 'rule2': 36, 'short_flush': 11, 'other_flush': 2}
```
⇒ **段数 / rule 分布 / 段长分位全部逐位一致**，唯一变化是时间轴变为**全局连续**。

### 14.2 ASR-004 ① 的 A/B 结果（**只报切段指标，WER 交 reviewer**）

**产物**（`reports/asr004_ab/`，15:14 重新合并后）
| 文件 | 说明 | mtime |
|---|---|---|
| `segments_A.json` / `segments_B.json` | 逐段：start_s/end_s/duration_s/rule/text/seg_idx/part_idx | 2026-10-24 15:14 |
| `summary_A.json` / `summary_B.json` | 组摘要（env / engine / rule 分布 / 段长分位） | 2026-10-24 15:14 |
| `transcript_A.txt` / `transcript_B.txt` | 逐段文本（**reviewer 直接用这两个**） | 2026-10-24 15:14 |
| `parts/{A,B}_NNN.jsonl` | 32 个分段原始产物（推理结果本体，未改） | 12:25–13:42 |

**A/B 切段指标对照**（真实 `Segmenter`，交付配置 GPU INT8，61 分钟全长）
| 指标 | A（旧行为） | B（新行为） | 方向 |
|---|---|---|---|
| 段数 | 538 | **558** | B 多 20 段 |
| rule1 / rule2 | 503 / **21** | 509 / **36** | B 的规则2 切点 +15 |
| flush 段（short/other/guard_block） | 9 / 3 / 2 | 11 / 2 / 0 | B 的 guard_block **归零** |
| 段长 p50 | 6.40s | 6.40s | 持平 |
| 段长 p90 | 8.32s | **7.68s** | B 更短 |
| 段长 p95 | 9.60s | **8.96s** | B 更短 |
| 段长 max | 17.92s | **14.08s** | B 更短 |
| **>12s 占比** | 6 段 / **1.12%** | 1 段 / **0.18%** | **B 更少** |
| <2s 短段 | 3 | 7 | B 多 4（flush 边界所致） |
| 空文本段 | 1 | **0** | B 无空段 |
| 总词数 | 11420 | 11385 | −0.31% |
| 时间轴跨度 | 0→3665.92s | 0→3665.28s | 连续覆盖 61 分钟 |

**结论（切段侧，ASR-004 验收的前半段）**
- **B 的 >12s 段数比 A 少**（6→1，1.12%→0.18%），**段长 max 明显更短**（17.92→14.08s）
  ⇒ 与 §10「相对化判据把间隔拉回 6.4s 量级」在 12 分钟素材上的结论**一致**，
  **在 61 分钟全长上复现**。
- **B 的空文本段为 0**，A 有 1 段 ⇒ 空段拒切在真实转写链路上**没有制造空段**。
- **B 段数比 A 多 20 段**：多出来的几乎都是**规则2 切点**（21→36）+15
  ⇒ B 在更多位置**切在静音里**（规则2 = 段尾连续静音 ≥0.8s），
  这正是 §10 的设计意图（规则1 是「段尾切」，规则2 才是「静音中点切」）。
  ⚠️ 对 WER 的含义：**B 的切点更碎、每段上下文更短**，
  段均词数 A 11420/538=21.2 词、B 11385/558=20.4 词
  ⇒ **B 的每段上下文略短**，这**可能**对 WER 略有不利 —— 需 reviewer 的
  配对 bootstrap 判定，**本模块不出 WER 数字**。
- ⚠️ `timing_valid=false`：ASR-004 明确「质量作业，计时数字不做要求」，
  且同机其他模块并发占用 GPU.0 ⇒ 墙钟/RTF 数字**不作数**
  （`summary_*.json` 里 `timing_valid_reason` 已如实标注）。

**给 reviewer 的明确交接**
- 用 `reports/asr004_ab/transcript_A.txt` 与 `transcript_B.txt`
  （**15:14 重新合并后的版本**，时间轴是全局连续的）；
  旧版本（时间轴重复 16 次）已备份为 `*.bak_prefix`，**不要用**；
- 每行格式 `[  start -   end] text`，**A/B 用同一套分段边界**
  （16 × 240s，每段末强制 flush）⇒ 逐段配对可行；
- ⚠️ **A/B 的分段边界完全相同**（同一 part 切分），但**段数不同**
  （538 vs 558）⇒ 配对 bootstrap 请按**时间轴对齐**（全局对齐），
  不要按「第 N 段配第 N 段」。

### 14.3 交叉校验：分段版 A vs 单进程 A（**通过**）
`reports/asr004_ab/singleproc_segments_A.json`（12:19 落盘，单进程跑满 61 分钟，
534 段 / rule1 510 + rule2 24 / wall 3763s）作为独立对照：

| 校验项 | 结果 |
|---|---|
| 分段版 A 与单进程 A 的**前 36 段**（part 0 内）切点 | **逐位相同** |
| 分段版 A 与单进程 A 的**前 36 段**文本 | **逐位相同** |
| 分歧起点 | 恰好在 **part 0 边界**（第 37 段 = 段末强制 flush）⇒ 符合预期 |
| 全文词级相似度 | **0.97411**（分段版 11420 词 / 单进程 11403 词） |

⇒ **推理链路与切段逻辑在两种执行方式下一致**，差异只来自分段边界上的强制 flush。
这同时**独立验证了 14.1 的合并修复**：修复前因时间轴错乱，切点对比在第 37 段就全错位；
修复后**前 36 段完全对齐**。

### 14.4 ASR-005 P0：离线参照已完成，**段级流式参照此前漏跑**

**离线参照（已完成）** — `qwen3asr_06b/results/p0_offline/`（4 文件，mtime 2026-10-24 12:35）
| 字段 | 值 | 出处 |
|---|---|---|
| `n_chunks` / `chunk_sec` | **31 / 120.0s** | `p0_summary.json` → `results.offline` |
| `wall_s` | **823.1s** | 同上 |
| `audio_sec` | 3660.0s（61.00 min） | 同上 |
| `rtf` | **0.2249** | 同上 |
| `oom_events` | `[]`（无 OOM 事件） | 同上 |
| `chars.offline` | **60760** | 同上 → `chars` |
| `model_sha` | `5eb144179a02acc5e5ba31e748d22b0cf3e303b0` | 同上 |
| `torch` / backend | `2.11.0+cu128` / `qwen_asr transformers backend (device=cuda, dtype=bfloat16)` | 同上 |
| 文本 | `offline_transcript.txt`（60762 B） | 同目录 |

**🔴 段级流式参照此前根本没跑**
- 串行执行器 `qwen3asr_06b/scripts/run_p0_all.sh` 的日志 `logs/p0_all.log`
  **内容只有一行**：`[run_p0_all] === 1/2 offline ===`
  ⇒ **offline 之后没有进入第 2 步**（`=== 2/2 stream_seg ===` 从未出现）；
- ⇒ 流式参照此前**只有 1 分钟冒烟产物** `results/p0_smoke3/`
  （RTF 0.6724 / 10 段 / 164 词），**没有 61 分钟全量产物**；
- ⇒ 15:12 用**「长跑 python 进程本身作后台任务主体」**的写法（§12.2 踩坑记录里的唯一可靠写法）
  重新启动：`scripts/p0_stream_seg.py --minutes 61 --out results/p0_stream`，
  日志 `qwen3asr_06b/logs/p0_stream_full.log`，
  断点 `qwen3asr_06b/results/p0_stream/stream_seg_chunks.jsonl`（逐段落盘、可续跑）。

**流式口径（仍待 reviewer 认可，见开头阻塞项 ③）**
- 官方 `qwen_asr.streaming_transcribe` / `init_streaming_state` **仅支持 vLLM 后端**，本机无 vLLM；
- ⇒ 用 transformers 后端**复刻同一语义**（段级流式）：
  段内每 **640ms** 增量解码（重喂该段累计音频，≤20s）、
  `unfixed_token_num=5` 前缀回退、前 2 块不用前缀、
  官方自适应 `max_new_tokens` 规则（`base=max(1,int(step/1280))`、
  `floor=min(32,max(4,2*int(step/1280)))`）、段尾 flush 预算 **64**；
- **切点直接复用真实 `live_caption_app.Segmenter`** ⇒ 段边界与 App 实时路径逐点一致；
- 口径文本已写入产物字段 `stream_note` / `stream_semantics` / `adaptive_rule`。

### 14.5 本轮产物清单

| 产物 | 文件数 | mtime | 说明 |
|---|---|---|---|
| `reports/asr004_ab/segments_{A,B}.json` | 2 | 2026-10-24 15:14 | A/B 逐段（**全局时间轴**，已修） |
| `reports/asr004_ab/summary_{A,B}.json` | 2 | 2026-10-24 15:14 | A/B 摘要（`timing_valid=false` 已标注） |
| `reports/asr004_ab/transcript_{A,B}.txt` | 2 | 2026-10-24 15:14 | **reviewer 直接用** |
| `reports/asr004_ab/{segments,transcript}_{A,B}.*.bak_prefix` | 4 | 2026-10-24 13:42 | 修复前旧产物备份（**勿用**） |
| `reports/asr004_ab/parts/{A,B}_NNN.jsonl` | 32 | 12:25–13:42 | 推理结果本体（未改） |
| `results/asr_diag/asr004_ab_remerge.py` | 1 | 2026-10-24 15:18 | **本轮新建**：只重合并的修复脚本 |
| `qwen3asr_06b/results/p0_offline/*` | 4 | 2026-10-24 12:35 | P0 离线参照（已交付 reviewer 算 WER） |
| `qwen3asr_06b/logs/p0_stream_full.log` | 1 | 进行中 | P0 流式参照日志 |
| `qwen3asr_06b/results/p0_stream/stream_seg_chunks.jsonl` | 1 | 进行中 | 流式参照断点（逐段落盘） |
| `status/asr/STATUS_ASR.md` | 1 | 2026-10-24 15:30 | 本文件 |

### 14.6 待办 / 待 reviewer
1. **reviewer 算 WER**（本模块不出 WER）：用 15:14 的 `transcript_{A,B}.txt` 做全局对齐 +
   分段配对 bootstrap，判定「B 相对 A 的 ΔWER 置信区间上界不明显大于 0」。
   ⚠️ 14.2 提示 **B 的段均上下文略短**（21.2 → 20.4 词）且**规则2 切点 +15**
   ⇒ 这是 B 可能劣化 WER 的机制，需 reviewer 独立判定。
2. **P0 末停一次等 reviewer**：流式参照跑完后停下，reviewer 认可流式口径
   （14.4 的「流式口径」小节）才进 P1（OV 导出）。
3. **§12.3 的「待补」已由本节 14.2/14.3 填掉**（A/B 摘要 + 交叉校验结论）；
   「ΔWER」一项仍由 reviewer 回填。
4. ⚠️ **git 冻结协议仍生效**（`shared/GIT_FREEZE` 存在，APP-009 history rewrite）
   ⇒ 本轮**未 commit / push / pull**，只改了本地文件
   （`status/asr/STATUS_ASR.md`、`results/asr_diag/asr004_ab_remerge.py`、
   `reports/asr004_ab/*`）。冻结解除后需提交本模块文件（**只提 `status/asr/`**，
   `reports/` 与 `results/` 按仓库 `.gitignore` 规则处理）。

## §15 ASR-005 P2 量化：INT8 交付、**INT4 在 0.6B 上不可行**（含完整根因链）（2026-10-24 21:10）

### 15.0 范围与前置

P2 = 对 0.6B 的两个 OV IR（encoder / decoder）做权重量化，产出 INT8 / INT4 版。
**配方来源严格照搬 R2T2 已验证配方**（`status/CORRECTIONS.md` C-089~C-097 +
`reports/c089_int4/*_build.json` + `*_wer.json`），不重新试错。

R2T2 的配方矩阵（**这是本节所有判断的依据**）：

| 配方 | R2T2 实测 | 判定 |
|---|---|---|
| R0 INT4 按通道、无校准 | WER **110.99%**（乱码） | ✗ |
| R1 INT4 g128、无校准 | WER 11.095%，**NPU prefill 1.6s** | ✗ 慢 |
| R2 INT4 按通道 + AWQ + SE | WER 10.844%，RTF 0.621 | ✓ 唯一可行布局 |
| R3 INT4 g128 + AWQ + SE | WER **94.72%**（乱码）+ 慢 | ✗ |
| R4 = R2 + ratio0.8 + hessian | 全长 **+2.11pp 显著变差** | ✗ |
| **INT8_SYM + lm_head 保 FP16**（`INT8_f16embed`） | **WER 7.074%（R2T2 最终交付）** | ✓ |

⇒ **0.6B 的 INT8 必须保留 lm_head 为 FP16**（`tie_word_embeddings=True`，
lm_head 权重 = embed_tokens）。**INT4 必须是「按通道 + AWQ + scale estimation」**。

### 15.1 ★ 定位 lm_head 节点（0.6B 的 IR 与 R2T2 不同）

R2T2 用 `ignored_scope=IgnoredScope(names=['__module.model.thinker.lm_head/aten::linear/MatMul'])`
排除 lm_head；**0.6B 的 IR 是 torch.export 出来的，节点名完全不同**。

产物 `qwen3asr_06b/results/p2_probe_lmhead.json`（20:14）给出了可靠的定位法：
**IR 里唯一 vocab 维 = 151936 的 MatMul** ⇒
`linear_196/aten.linear.default/MatMul`，权重 `Constant_623_compressed [151936, 1024] f16`。
（IR 共 4262 个节点 / 197 个 MatMul，vocab 维只出现一次 ⇒ 定位唯一。）

验证有效：量化后该层权重 cos = **1.000000**（`p2_diag_weights_int8dec.json`）⇒
**ignored_scope 确实生效，lm_head 完全未被量化。**

### 15.2 P2 产物清单（全部已落盘）

| IR 目录 | 文件数 | 大小 | mtime | 配方 |
|---|---|---|---|---|
| `models/ov-encoder-06b-fp16` | 2 | 357 MiB | 12:31 | P1 基线 |
| `models/ov-dec-06b-embed-fp16` | 2 | 1140 MiB | 17:28 | P1 基线 |
| `models/ov-encoder-06b-int8sym` | 2 | **180 MiB** | 20:08 | INT8_SYM 按通道 |
| `models/ov-dec-06b-embed-int8sym` | 2 | **721 MiB** | 20:08 | INT8_SYM 按通道 + **lm_head FP16** |
| `models/ov-encoder-06b-int4` | 2 | 93 MiB | 20:29 | INT4 按通道 + SE（**AWQ 被跳过**，见 15.5） |
| `models/ov-dec-06b-embed-int4` | 2 | 511 MiB | 20:27 | INT4 按通道 + AWQ + SE |
| `models/ov-dec-06b-embed-int4_r4` | 2 | 554 MiB | 21:03 | INT4 + ratio0.8 + hessian |
| `models/ov-dec-06b-embed-int4_r5` | 2 | 616 MiB | 21:08 | INT4 + ratio0.5 + hessian |

校准集（**只用 0–12 分钟，绝不触碰 ≥12 分钟**）：
- `results/p2_calib_encoder.npz`（15.0 MB，64 条 `input_features[1,128,2400]` + `n_valid[1]`）
- `results/p2_calib_decoder.npz`（17.6 MB，64 条 `inputs_embeds[1,512,1024]`）
两者的采集口径 = **真实 `live_caption_app.Segmenter` 切 0–12 分钟** +
真实 mel（decoder 侧额外走 FP16 encoder + 官方 `masked_scatter`），
**不是随机张量**（R2T2 C-058⑤d 的教训）。

### 15.3 ★ INT8 精度（可用，交付候选）

`p1_verify_e2e.py` 的 3 段 teacher-forcing（0–6.4s / 2812–2835.9s / 3600–3616s）：

| 组合 | enc cos min | dec cos min | top1 匹配 | 产物 |
|---|---|---|---|---|
| FP16 + FP16（基线） | 0.999999 | 0.999983 | **100%** | `p1_verify.json` |
| FP16 enc + **INT8 dec** | 0.999999 | **0.962210** | **100%** | `p1_verify_int8lm_fp16.json` |
| **INT8 enc** + FP16 dec | 0.978472 | 0.99779 | **100%** | `p1_verify_enc_int8.json` |
| **INT8 enc + INT8 dec** | **0.978472** | **0.974973** | **100%** | `p1_verify_both_int8.json` |

**判据说明（重要）**：ASR-005 原文的「cos ≥ 0.999 / top1 ≥ 99%」是给
**P1 的 FP16 导出**用的；量化版不可能达到。对照 R2T2 自己的实测
（`reports/c057_encoder_acc_3way.json`）：**R2T2 的 INT8_SYM encoder
cos = 0.993056 / top1 = 98.75%**，INT8_ASYM = 0.997374 ⇒
**0.6B 的 INT8（enc 0.978 / dec 0.975 / top1 100%）与 R2T2 同量级。**

### 15.4 ★ INT4 全部崩坏 —— 且已排除「实现错误」

INT4 的三个配方全部崩坏（dec cos 变负、top1 0%）：

| 配方 | dec cos（3 段 min） | top1 | 产物 |
|---|---|---|---|
| INT4 按通道 + AWQ + SE | **−0.420358** | **0%** | `p1_verify_int4dec.json` |
| + ratio0.8 + hessian（R4） | **−0.550945** | **0%** | `p1_verify_int4dec_r4.json` |
| + ratio0.5 + hessian（R5） | **−0.578110** | **0%** | `p1_verify_int4dec_r5.json` |
| INT4 enc + INT8 dec | 0.600523 | 33% | `p1_verify_int8dec_int4enc.json` |

**根因链（每一环都有产物支撑，不是推测）**：

**① torch 侧 fake-quant 独立复现 ⇒ 量化本身的问题，不是 OV/NNCF 的 bug**
（脚本 `p2_fakequant_probe.py`，直接在 torch 上做 per-channel 对称 fake-quant）：

| 位宽 | 布局 | cos vs torch FP32 | top1 |
|---|---|---|---|
| INT8 | per-channel | **0.977708** | OK |
| INT4 | per-channel | **0.113752** | MISMATCH |
| INT4 | g128 | 0.297568 | MISMATCH |
| INT4 | g64 | 0.461777 | MISMATCH |
| INT4 | g32 | 0.521150 | MISMATCH |

⇒ OV 侧 INT8 的 0.962 与 torch 侧 0.978 同量级（**一致**）
⇒ OV 侧 INT4 的 −0.42 与 torch 侧 0.114 同为崩坏（**一致**）
⇒ **量化/运行时都没问题，是 0.6B 这个模型对 INT4 不友好。**

**② 逐层累积效应（`p2_fakequant_mix.py`，只量化部分层）**

| 量化的层数 | cos | top1 |
|---|---|---|
| 49 / 196（后 25%） | 0.765685 | **OK** |
| 98 / 196（后 50%） | 0.436063 | MISMATCH |
| 189 / 196（除最后 7 层） | 0.118720 | MISMATCH |
| 196 / 196（全量） | 0.113752 | MISMATCH |

⇒ 误差随量化层数**单调累积**；INT4 的单层权重误差（cos 0.86~0.99，
`p2_diag_unpack_int4dec.json`）在 28 层上放大到 logits 崩坏。

**③ 手工反量化证明「OV 运行时反量化基本正确」，权重本身才是元凶**
（`p2_diag_runtime.py`，把手工解包 int4 × scale 得到的 W_deq **写回 FP16 IR**）：

| 对比 | cos | 含义 |
|---|---|---|
| OV-FP16 vs torch | 0.999983 | 基线 |
| **OV-FP16(灌 W_deq) vs torch** | **0.607081** | **权重本身就把模型打坏了** |
| OV-INT4 vs torch | 0.568546 | |
| OV-INT4 vs OV-FP16(灌 W_deq) | **0.971235** | OV 的 int4 运行时反量化**基本正确** |

⇒ **不是 OV 版本 bug、不是设备插件 bug。**

**④ 排除设备插件（`p2_dev_matrix.py`，同一 IR 三设备）**

| 设备 | cos vs torch | top1 |
|---|---|---|
| CPU | 0.568546 | MISMATCH |
| GPU | 0.606623 | MISMATCH |
| NPU | 0.598701 | MISMATCH |

⇒ 三设备几乎一致 ⇒ **与设备无关**。

**⑤ 排除 AWQ 插错位置**
- 量化版 Multiply 节点数 = 619，FP16 = 423 ⇒ **+196**（每个 MatMul 一个 AWQ mul）。
- **R2T2 的可用 INT4 IR（R2）也是 423 → 620（+197）** ⇒ AWQ 插入行为**完全相同**。
- AWQ pattern 定义（`nncf/.../awq_patterns.py`）：`Act_Mul_MatMul` / `Act_MatMul`，
  需要 MatMul ⇒ **encoder 是 conv 结构，没有 MatMul ⇒ AWQ 静默跳过**
  （日志实测 `No matching patterns were found for applying AWQ algorithm, it will be skipped.`）
  ⇒ encoder 的 INT4 **等于无校准的按通道 INT4**（= R2T2 的 R0 乱码配方）。

**⑥ 排除 scale 轴错误（`p2_diag_scale_*.json`）**
- scale shape = `[out, 1]`（每个输出通道一个）⇒ **轴正确**，0.6B 与 INT8 一致。
- ⚠️ 曾误判「int4_t 值域 [−128,127]」⇒ **实际是 OV 的 int4_t 为打包存储**
  （两个 int4 塞一个字节，元素数 = 逻辑数 / 2：linear_1 逻辑 [1024,1024]，
  存储 524288）。`node.get_data()` 返回的是**未解包的原始字节**。
  ⇒ scale 隐含级数 median **8.81**（真 INT4 语义 ≈ 7）⇒ **量化数据本身是对的**。

**⑦ 与 R2T2 的关键差异（解释为什么 R2T2 能做 INT4、0.6B 不能）**

| 项 | R2T2 | 0.6B |
|---|---|---|
| 层矩阵 | 6144 × 2048 | **3072 × 1024** |
| 文本 hidden | 2048 | 1024 |
| decoder IR 形态 | 纯 LM（**含 embed_tokens 表**） | **不含 embed 表**（embed 已拼进 `inputs_embeds` 端口） |

⇒ R2T2 每通道的动态范围被 2048 维的输入统计支撑；0.6B 只有 1024 维
⇒ 每通道 15 个量化级的相对误差**翻倍** ⇒ INT4 不可行。

### 15.5 本轮新增/修正的脚本与踩坑

| 脚本 | 作用 |
|---|---|
| `qwen3asr_06b/scripts/p2_quantize.py` | **重写**：按 R2T2 验证配方（INT8 + lm_head ignored_scope；INT4 按通道 + AWQ + SE + backup INT8_SYM），加 `--ratio/--hessian/--group-size`，保存后**重新读回数 dtype**（R2T2 明确要求这步不能省） |
| `qwen3asr_06b/scripts/p2_probe_lmhead.py` | 定位 lm_head（唯一 vocab 维 MatMul） |
| `qwen3asr_06b/scripts/p2_calib.py` | 0–12 分钟真实激活校准集（encoder / decoder 各 64 条） |
| `qwen3asr_06b/scripts/p2_fakequant_probe.py` | torch 侧受控 fake-quant（含 `--group-size`），**定位「量化本身 vs 实现错误」的关键工具** |
| `qwen3asr_06b/scripts/p2_fakequant_mix.py` | 只量化部分层，量「误差累积」 |
| `qwen3asr_06b/scripts/p2_diag_weights.py` | 权重级逐层对比 |
| `qwen3asr_06b/scripts/p2_diag_scale.py` | per-channel scale 的**轴**检查 |
| `qwen3asr_06b/scripts/p2_diag_exact.py` | 单层精确核算（q 的位宽 / scale 隐含级数） |
| `qwen3asr_06b/scripts/p2_diag_unpack.py` | **手工解包 int4**（OV 的 int4_t 是打包存储） |
| `qwen3asr_06b/scripts/p2_diag_runtime.py` | 把 W_deq 写回 FP16 IR ⇒ 判定 OV 运行时反量化对错 |
| `qwen3asr_06b/scripts/p2_dev_matrix.py` | 同一 IR 在 CPU/GPU/NPU 上的矩阵 |
| `qwen3asr_06b/scripts/p2_diag_layers.py` | 图手术加中间出口（**此路不通**，见下） |

**踩坑（勿再尝试）**：
1. **`model.add_outputs()` 对这个 IR 会报**
   `Model references undeclared parameters: opset1::Parameter inputs_embeds`
   ⇒ 对 torch.export 出来的 IR 做图手术不安全 ⇒ 改用权重级 / 写回 FP16 IR 的方法。
2. **OV 的 `Node.get_data()` 对 int4_t 返回未解包的原始字节** ⇒ 直接拿来算 cos 必错。
3. **`nncf.Dataset` 没有 `len()`** ⇒ 要自己返回条数。
4. **`model.add_output`（单数）在 OV 2026.4 不存在**，只有 `add_outputs`（复数）。
5. **OV 的 `Output` 没有 `get_source_output()`** ⇒ 用 `input_value(i).get_node()`。
6. **并发跑两个读 1.2 GB IR 的脚本会 OOM**（`OpenBLAS error: Memory allocation still failed`）
   ⇒ 重任务串行。
7. **torch `named_modules` + `isinstance(mod, nn.Linear)` 不可靠**
   （Qwen3ASR 的 attention 子模块结构会报 `object has no attribute 'weight'`）
   ⇒ 改用 `named_parameters` + `dim()==2`。
8. ⚠️ **上一轮 P2 的 INT4 用的是 `nncf.quantize(HYBRID)`，那不是 R2T2 的验证配方**
   ⇒ 本轮已改为 `nncf.compress_weights(mode=INT4_SYM, group_size=-1, awq=True, scale_estimation=True, backup_mode=INT8_SYM)`。
   **上一轮 INT4 的结论（崩坏）本轮已用正确配方重验，结论不变。**

### 15.6 P2 结论

1. **INT8（encoder + decoder，lm_head 保 FP16）可用**：
   enc cos 0.978 / dec cos 0.975 / **top1 100%**，体积 357+1140=1497 MiB → **180+721=901 MiB（−39.8%）**。
2. **INT4 在 0.6B 上不可行**（不是实现 bug，是模型宽度不够：1024 vs R2T2 的 2048）。
   已用 7 条独立证据排除 OV 版本 bug / 设备插件 / AWQ 插错 / scale 轴错 / 校准集无效 /
   配方选择错误 ⇒ **结论可靠**。
   ⚠️ 若 reviewer 认为必须交付 INT4，下一步只能走 **GPTQ**（R2T2 C-094 提到的 R4c 备选），
   本轮未做。
3. **AWQ 对 encoder 无效**（conv 结构无 MatMul）⇒ 0.6B 的 **encoder INT4 也没有校准**
   ⇒ encoder INT4 单独不可用（实测 enc cos 0.53~0.73 ⇒ 不可交付）。
   ⇒ **encoder 应保留 FP16 或用 INT8**（R2T2 的最终交付也是 FP16 encoder + INT8 decoder）。
4. **P2 检查点**：按 ASR-005「P2 结束停一次等 reviewer 复核（最多 30 分钟）」，在此停。

### 15.7 待 reviewer

1. **算 WER**：`results/p0_offline/offline_transcript.txt`（P0 离线）、
   `results/p0_stream/stream_transcript.txt`（P0 段级流式），
   以及 §12 的 `reports/asr004_ab/transcript_{A,B}.txt`（ASR-004 A/B）。
2. **复核 P2 的 INT8 候选**：`models/ov-encoder-06b-int8sym` +
   `models/ov-dec-06b-embed-int8sym`（+ `models/ov-encoder-06b-fp16` 作为 FP16 对照）。
3. **确认 INT4 的处置**：本轮结论是 0.6B 上 INT4 不可行（证据见 15.4）。
   若需要 INT4，请指明是否值得试 GPTQ；否则 P3 只做 INT8。
4. ⚠️ **git 冻结仍生效**（`shared/GIT_FREEZE`，17:31）⇒ 本轮**未 commit**。
   本轮新增/修改的文件全在 `qwen3asr_06b/scripts/` 与 `qwen3asr_06b/results/`、
   `qwen3asr_06b/models/`（**均在仓库外**，不涉及 `confucius4-openvino` 的 git），
   仓库内只改了 `status/asr/STATUS_ASR.md`。

## §16 ASR-005 P2 收尾：git 冻结已释放、产物清单复核、P2 检查点正式停靠（2026-10-25 00:05）

> **本章是追加，不回头改 §15**（ASR-001 格式纪律）。§15.7 第 4 条写的
> 「git 冻结仍生效（17:31）⇒ 本轮未 commit」**在 21:12 那一刻是真的**，
> 但**现在已过期** ⇒ 以本章为准。

### 16.1 ⚠️ git 冻结状态变化（**结论：现在允许提交**）

| 时刻 | `shared/GIT_FREEZE` | 依据 |
|---|---|---|
| 2026-10-24 17:31 | **存在**（`GIT FREEZE 2026-10-24 17:31:08 / APP-009 git history rewrite in progress`） | App 模块 `status/app/STATUS_APP.md` §24.7 / §24.8 第 1 条 |
| 2026-10-24 21:12 | 仍存在 ⇒ §15 全程未 commit | 本模块 §15.7 第 4 条 |
| **2026-10-25 00:01** | **文件已不存在**（`ls shared/` 只见 `MACHINE_LOCK` + 2 个 NOTICE + README_LOCK.md） | 本模块实测 |

**判定**：ASR-005 的协议原文是「**只要这个文件存在**，就不要在
`confucius4-openvino` 仓库里 commit、push 或 pull」⇒ 文件已删除 ⇒ **禁令自动解除**。
且 App 的 APP-009 改写**已于 20:44 完成并强推**（`status/app/STATUS_APP.md`
§24.8 第 1 条自述），与冻结文件消失一致。

**本地仓库与远端的一致性（提交前必查，避免 §23 那种 unrelated histories）**：
- 本地 `HEAD` = `6fd7806`（`APP §24: 修掉 pack_v13.py…`）
- `origin/main` = `6fd7806`（`git fetch origin` 后实测）
- ⇒ **无 divergent history，无需 `reset --hard`**
- ⚠️ **明确不做** `git reset --hard origin/main`：ASR-005 协议说本地 clone 要
  `fetch` + `reset --hard`，但**当前工作区有 4 个模块共 500+ 个未提交改动**
  （`live_caption/` 72 个、`reports/` 290 个、`results/` 98 个）⇒ `reset --hard`
  会**摧毁 App / MT / TTS 线程的在途工作** ⇒ **绝对不能做**。
  当前 `fetch` 后 HEAD 已与远端一致，**无需任何 reset**。

### 16.2 P2 产物清单复核（**文件数 / 体积 / mtime**，全部实测于 2026-10-25 00:05）

| 目录 | 文件数 | 体积 | mtime | 配方 |
|---|---|---|---|---|
| `models/ov-encoder-06b-fp16` | 2 | 357 MiB | 2026-10-24 12:31:47 | P1 FP16 基准 |
| `models/ov-dec-06b-embed-fp16` | 2 | 1140 MiB | 2026-10-24 17:28:25 | P1 FP16 基准 |
| **`models/ov-encoder-06b-int8sym`** | 2 | **180 MiB** | 2026-10-24 20:08:19 | **INT8_SYM 按通道**（P2 交付候选） |
| **`models/ov-dec-06b-embed-int8sym`** | 2 | **721 MiB** | 2026-10-24 20:08:36 | **INT8_SYM + lm_head 保 FP16**（P2 交付候选） |
| `models/ov-encoder-06b-int4` | 2 | 93 MiB | 2026-10-24 20:29:51 | INT4（**AWQ 被跳过** ⇒ 不可交付） |
| `models/ov-dec-06b-embed-int4` | 2 | 511 MiB | 2026-10-24 20:27:31 | INT4 按通道+AWQ+SE（崩坏） |
| `models/ov-dec-06b-embed-int4_r4` | 2 | 554 MiB | 2026-10-24 21:03:03 | INT4 +ratio0.8+hessian（崩坏） |
| `models/ov-dec-06b-embed-int4_r5` | 2 | 616 MiB | 2026-10-24 21:08:05 | INT4 +ratio0.5+hessian（崩坏） |

⚠️ **命名更正**（§15 里我写过的 `ov-dec-06b-fp16` **目录名不存在**）：
FP16 decoder 的真实目录名是 **`ov-dec-06b-embed-fp16`**（带 `-embed`）⇒
reviewer 取产物请用**上表**的目录名，勿用错名。

**验证 / 诊断产物**（`results/`，全部已落盘，mtime 见文件属性）：
`p1_verify_{enc_int8,dec_int8,both_int8,int8lm_fp16,int4dec,int4dec_r4,int4dec_r5,int8dec_int4enc}.json`
（20:09–21:08）、`p2_quant_{encoder_int8sym,encoder_int4,decoder_int8sym,decoder_int4,decoder_int4__r4,decoder_int4__r5}.json`（20:08–21:08）、
`p2_probe_lmhead.json`（20:14）、`p2_diag_{weights_int8dec,scale_int4dec,scale_int8dec,exact_int4dec,final_int4dec,runtime_int4dec}.json`（20:31–20:58）、
`p2_diag_unpack_*.json`、`p2_dev_matrix_int4dec.json`（20:54）、
`p2_fakequant_{b8_scan,b4_scan,b4_g128,b4_g64,b4_g32,mix_b4_last,mix_b4_all_but_last}.json`（20:35–21:07）、
校准集 `p2_calib_encoder.npz`（15.0 MB / 20:19）+ `p2_calib_decoder.npz`（17.6 MB / 20:21）。

### 16.3 P2 检查点：正式停靠（**P3 不启动**）

按 ASR-005「P0 结束、P2 结束，各停一次，等 reviewer 复核（**最多 30 分钟**）」，
本模块自 21:12 完成 P2 起即停在检查点，**至今未启动 P3**。

**给 reviewer 的 4 项待办**（与 §15.7 一致，此处只做归纳，不重复论证）：

1. **算 WER**（reviewer 本机 MiniMax baseline + `compare_wer` + `paired_bootstrap`，
   **本模块不自己算**，ASR-004 铁律）：
   - `qwen3asr_06b/results/p0_offline/offline_transcript.txt`（0.6B 离线参照，11,125 词）
   - `qwen3asr_06b/results/p0_stream/stream_transcript.txt`（0.6B 段级流式参照，11,425 词）
   - `reports/asr004_ab/transcript_{A,B}.txt`（ASR-004 新旧切段 A/B）
2. **复核 INT8 候选**（§15.3）：`ov-encoder-06b-int8sym` + `ov-dec-06b-embed-int8sym`，
   端到端 enc cos 0.978472 / dec cos 0.974973 / top1 100%。
3. **裁定 INT4 处置**（§15.4 的 7 条证据链）：本模块结论 = **0.6B 上 INT4 不可行**；
   若仍要求 INT4，**唯一剩余路线是 GPTQ**（R2T2 C-094 的 R4c 备选），本轮**未做**。
4. **P0 流式口径认可**：`qwen_asr` 官方流式只支持 vLLM 后端，本机无 vLLM ⇒
   用 transformers 后端做**段级流式**复刻同语义（口径写在产物 `stream_semantics` 字段）。

### 16.4 若 reviewer 放行 P3：已备好的执行清单（**尚未开始**）

| # | P3 项 | 口径 / 约束 | 前置 |
|---|---|---|---|
| 1 | 61 分钟 WER | 对 0.6B torch 参照 + R2T2 交付基线分别配对 bootstrap；**本模块不自己算 WER** | reviewer 放行 |
| 2 | NPU RTF P50/P95 | **多次 fresh 进程**；**必须持 `shared/MACHINE_LOCK`**（当前锁由 `app-pack` PID 18380 持有但**该 PID 已死** ⇒ 属陈旧锁，可按 `README_LOCK.md` 规则回收）；`timing_valid` 字段必须落盘 | 机器空闲 |
| 3 | 首字延迟 + 内存 | fresh 进程，逐段记录 | 同上 |
| 4 | 最终对比表 | 0.6B（INT8 / INT4 × GPU / NPU）× R2T2 交付版；**INT4 一列按 15.4 标注「不可行」** | 同上 |

⚠️ **P3 的计时类作业必须持锁**，而当前 `shared/MACHINE_LOCK` 内容为
`module: app-pack / pid: 18380 / started: 2026-10-24 21:10:18` ⇒ 实测该 PID
**已不在进程表**（`tasklist` 无 18380）⇒ 属陈旧锁。
按 `README_LOCK.md`（"锁的 PID 已经不在…可以回收"）**可以回收**，
但**回收前需确认 App 线程确实没在跑** ⇒ 本轮**不回收、不启动 P3**，
等 reviewer 放行后由本模块独占持锁。

### 16.5 本轮（收尾段）的纪律核对

- ✅ **未跑任何推理 / 测速**（本轮只做文件核验 + STATUS 落档 + git 状态检查）。
- ✅ **未改动** `status/asr/CORRECTIONS_ASR.md` 的旧条目（只读取；ASR-005 条目是
  上一轮 reviewer 写入的，本模块只读不写）。
- ✅ **只追加** `## §16`，**未回头改** §1~§15。
- ✅ **未 `git add`** 其他模块的文件（`live_caption/` / `reports/` / `results/` /
  `status/app/` / `status/CORRECTIONS.md` 等一律不动）。
- ✅ **未 commit `live_caption/`**（ASR-003 铁律）。
- ⚠️ **尚未 commit**（本轮在写 §16 时冻结已解除，但**先把 STATUS 落档做完再提交**，
  避免提交一个半成品 STATUS）。

## §17 收到 ASR-006 / ASR-007：P2 复核结论落地、P3 改以「对比报告」为目标（2026-10-25 09:35）

> 本章**只追加**，不回头改 §12~§16。§15.4「INT4 在 0.6B 上不可行」的结论
> 被 reviewer 判为「**证据不足，暂不关闭**」⇒ 以本章为准（§17.4 说明怎么补）。

### 17.1 reviewer 的复核结论（ASR-006，08:35）

| 项 | 结论 |
|---|---|
| **ASR-004** | ✅ **通过，可关闭**。A 旧切段 10.80% / B 新切段 10.58%，Δ = **−0.22pp**，CI [−0.64, +0.20]（300 共同切点块）⇒ v1.4 切段改动**不用回退** |
| **§14.1 的 merge_group 偏移缺陷** | 确实存在且修复正确，但只在 `results/asr_diag/`（`.gitignore` 排除）⇒ 是**评测脚本缺陷，不是交付级缺陷** ⇒ 以后按**实际影响范围**定级 |
| **新发现（比 ASR-004 重要）** | 🔴 **App 实时路径比交付基准差 2.6pp**（A 对 `int8dec_fp16enc` 8.17%：**+2.63pp，CI [+1.80, +3.41]，显著**），主因是**插入多 178 个**且集中在**段首 3 词 / 段尾 3 词**，全落在 **rule1 切点**上（切点穿过一个词 ⇒ 前后两段都转写出来）。**A、B 都有 ⇒ 不是 ASR-004 引入** |
| **P0 参照** | 0.6B 离线 14.80% / 段级流式 10.97%；**流式口径可接受**，但要定性为「App 路径等价参照」而非官方 vLLM 流式。0.6B 流式对 R2T2-B **+0.39pp CI [−0.33, +1.14]**、对 R2T2-A +0.17pp CI [−0.60, +0.91]，**都不显著** |
| **§13.6「两份参照质量上限大致相同」不成立** | 🔴 离线对流式是 **+3.83pp，CI [+2.94, +4.70]**，31 块中 30 块离线更差 ⇒ **P3 以段级流式为参照，离线只作旁证** |
| **INT8 候选** | ⚠️ 现在**没有可复核的 WER 或 RTF**；§15.3 的「top1 100%」只是 **3 个 token 的 argmax 一致**，**不能作为质量证据**；enc cos 0.978 低于 R2T2 同口径（INT8_SYM 0.993 / INT8_ASYM 0.997）⇒ **是否可用要等 P3 的 61 分钟 WER 判定** |

### 17.2 P0 参照的两处修正（**reviewer §3 要求，本模块已定位根因**）

**① 音频被 `--minutes 61` 截断（reviewer 说「最后约 6 s 没跑」，实测差得更多）**
- wav **真实长度 3671.189 s（61.19 min）**（`soundfile.info`：58,739,029 frames @ 16 kHz）
- 0.6B P0 跑的是 `--minutes 61` ⇒ **截到 3660.0 s** ⇒ **少跑 11.19 s**
- R2T2 A/B 跑到 **3665.92 s**（`reports/asr004_ab/segments_A.json` 末段 `end_s`）
⇒ **P3 跑整个 wav（`--minutes 0`）**，不再截断。

**② `rtf` / `rtf_this_run` / `n_runs` 三个字段不自洽（根因已查明并已修）**

reviewer 观察到 `p0_stream_summary.json` 里 `n_runs=1`、`wall_this_run_s = wall_s = 2470.1`、
但 `rtf_this_run=0.8167` 与 `rtf=0.6749` 对不上。**三个字段的根因分别是**：

| 字段 | 实测 | 根因 |
|---|---|---|
| `rtf = 0.6749` | ✅ **自洽** | = `wall_cum_s(2470.1) / covered_s(3660.0)`。`wall_cum` 是**跨次累加**值（长跑被回收过），`progress.json` 里 2447.6s@3630.7s 与之自洽 |
| `rtf_this_run = 0.8167` | 🔴 **口径错** | 原式 `wall / (covered_s − resume_from_s)`。本次运行是**续跑尾部**（jsonl 里 552 段已全在）⇒ `resume_from_s = 3629.44` ⇒ 分母只剩 **30.56 s** ⇒ 严重高估。⇒ **已删除该字段**（口径唯一，避免误读），改记 `covered_this_run_s` |
| `n_runs = 1` | 🔴 **少算** | `n_runs` 从 `progress.json` 读再 +1，而 progress **只在每 60 步落盘** ⇒ 本次只跑 3 步 ⇒ progress **根本没被更新** ⇒ 读到的仍是上次的 1（真实为 2 次运行）。⇒ **已修：运行开始时锁定 `this_run_idx`，全程只用这一个值** |

⚠️ **纪律**：CUDA RTF **不作验收**（reviewer 明说），但**字段必须自洽**。

### 17.3 P3 口径（ASR-006 §6 + ASR-007 改造后）

- **走 App 路径**：真实 `Segmenter`（B 行为），**单进程不分 part**，**跑整个 wav**
  ⇒ 这样能和 0.6B 流式参照（552 段）用原版 `paired_bootstrap.py` **逐段配对**。
- **产出 3 份转写**（`qwen3asr_06b/results/p3_*/`）：GPU INT8 / **NPU INT8** / GPU **enc FP16 变体**。
- **对比对象**：0.6B 段级流式参照（**主参照**）、R2T2 App 路径 B（10.58%）；
  R2T2 交付基准 8.17% 是 226 段离线切分，**口径不同，只作参考列**。
- **计时**：持 `shared/MACHINE_LOCK`，**多次 fresh 进程**，记 P50/P95、首字延迟、内存，
  **`timing_valid` 落盘**。
- **验收**：0.6B INT8 对 0.6B 流式参照的配对 CI **不显著劣化**即通过；**WER 由 reviewer 复核**。

### 17.4 INT4「不可行」结论被退回：reviewer 的 5 条反驳 + 本模块的回应

reviewer 的 5 点（本模块**全部接受**，不作反驳）：

1. 「宽度 1024 不够 ⇒ 每通道误差翻倍」是**推断无数据支撑**；每通道量化误差主要由**输入维的离群值分布**决定，不随维度线性变化；同宽度（hidden 1024）的 Qwen3-0.6B 文本 LLM 做 INT4 是常规配置。
2. 判据本身有问题：只看 **3 个位置的末位 logits cos**；连 INT8 fake-quant 也只有 0.978 ⇒ 该指标对本模型**过于敏感**，不能单靠它判「崩坏」。
3. **需核实 `p2_fakequant_probe.py` 是否把 tied 的 embed_tokens/lm_head（以及 audio tower 的 2D 参数）也一起量化了** ⇒ 若有，fake-quant 那一环证据作废。
4. **新判据**：**多 token teacher-forcing top1**（≥20 个 ≥12 分钟的评测段，统计**全部输出 token**），
   并用 **R2T2 的 R2（AWQ+SE 按通道，WER 10.84%）在同一口径下做标定点**。
5. **新试法**：GPU 上试 **`INT4_ASYM g128 + AWQ + SE`**（backup `INT8_ASYM`，lm_head 保持 FP16），
   跑 **5 分钟切片（≥12 分钟区段）**的贪心解码看文本是否正常。
   ⇒ **①② 都确认崩坏，才能写「0.6B INT4 不可行」**；只有在 ①② 显示有希望、
   但按通道版不行时，才考虑 GPTQ。

⚠️ **§15.4 的「7 条证据链」至此降级**：其中 ①②（torch 侧 fake-quant 复现 / 逐层累积）
是**基于第 3 点的同一批数据** ⇒ 若 fake-quant 误量化了 tied 权重，这两条链**同时失效**。
其余 ③④⑤⑥⑦（写回 FP16 IR / 三设备一致 / AWQ 插入数 / scale 轴 / 宽度对比）
**不依赖 fake-quant，仍成立**（但③④ 用的是**末位 logits cos** 这个被质疑的指标
⇒ 也需用新判据复核）。⇒ **本模块不宣称 INT4 不可行，也不再宣称已排除实现 bug**。

**补测计划（限时 ≤2 小时，排在 P3 INT8 之后；做不完就如实写，不拖 INT8）**：
① 多 token teacher-forcing top1 判据（含 R2T2 R2 同口径标定）；
② GPU `INT4_ASYM g128 + AWQ + SE` 5 分钟切片贪心解码；
③ 先核实 fake-quant 探针的 tied 权重问题（最便宜，且决定 ① 能否复用旧数据）。

### 17.5 rule1 切点重复词诊断（ASR-006 §2，**排在 P3 INT8 之后**）

- 范围：**只诊断，不改 `live_caption`**（ASR-003 铁律）。
- 要做的：用现有 parts 产物**离线**分析 rule1 切点处的**能量与静音**，
  找出「切在词中间」的比例；
  给出 ① 不改代码就能试的方案（env 参数，比如加大 rule1 的静音要求）
  ② 需要 App 实施的方案（段间 n-gram 去重 / 切点前后保留重叠再去重）；
  **每个方案都要在 61 分钟 A 组产物上做离线去重模拟，给出估计的 WER 收益**（reviewer 复核）。

### 17.6 ASR-007【用户决定】0.6B 只作实验，交付物改为**对比分析报告**

用户已确认：**Qwen3-ASR-0.6B 只是实验，不进 App 和客户包**（交付仍用 R2T2）。
⇒ ASR-006 的 P3 改成以**出对比报告**为目标。

**对比矩阵**（做不了的格子**写明原因，不硬凑**）：

| 模型 | 精度 | 设备 |
|---|---|---|
| R2T2（1.7B） | INT8、INT4（已有交付级数据，**复用并注明来源**） | GPU.0、NPU；CUDA Q8/Q4 作参照 |
| Qwen3-ASR-0.6B | FP16、INT8、INT4（INT4 按 §17.4 的 2 小时限时补测，做不出来就写「不可用」并附证据） | GPU.0、NPU；CUDA（torch 官方）作参照 |

**每格指标**：
- **准确率**：260902_SPE 61 分钟全长 WER，**统一走 App 实时路径的流式口径**
  （640 ms 分块、自适应 max_new_tokens）；转写交 reviewer 复算，目标机自算 WER **只作参考**。
- **延迟**：RTF 的 P50/P95/最大值（**≥2 次 fresh 进程，持机器锁，给出范围**）；
  首字/出字延迟 P50/P95；**模型加载与首次编译耗时（分有缓存/无缓存两种）**。
- **内存**：fresh 进程测量，**iGPU 或 NPU 设备内存 + 主机内存（峰值与稳态）**；模型文件体积。
- **设备摆放**：encoder / decoder **分别**在哪个设备上，要写清楚。

**产出**：
- 结果 json 统一放 `qwen3asr_06b/reports/compare/`，**每一格一份**，含**原始字段**和 `timing_valid`；
- STATUS 里写一节**汇总表**，注明每个数字的**来源文件**；
- reviewer 复核 WER 并汇编成 HTML 对比报告（沿用之前 OV/CUDA 对比报告的格式）。
- **计时作业一律持共享机器锁，串行执行；准确率作业不需要锁。**

### 17.7 本模块的执行顺序（**按 reviewer 指定的优先级**）

| 序 | 任务 | 依据 | 锁 |
|---|---|---|---|
| 1 | 修 P0 参照：跑整个 wav + 修 rtf/n_runs 字段 | ASR-006 §3 | 不需要（准确率作业） |
| 2 | **P3 INT8**：61 分钟 App 路径全长（GPU / NPU / enc FP16 变体） | ASR-006 §6 | 计时部分**需要** |
| 3 | **INT4 补测**（≤2 h 限时）：多 token top1 判据 + GPU INT4_ASYM g128 解码 | ASR-006 §5 | 不需要 |
| 4 | rule1 切点重复词诊断（离线模拟 WER 收益） | ASR-006 §2 | 不需要 |
| 5 | 对比分析报告（矩阵 + 汇总表 + `reports/compare/*.json`） | ASR-007 | 计时格**需要** |

⚠️ **P3 的单进程全长跑可能很久**（torch CUDA 参照已 2470 s；OV NPU 另算）
⇒ 沿用**已验证的长跑存活写法**：`run_in_background=true` + **直接前台命令**
（python 进程本身作任务主体）+ **断点续跑**（判据校验**末条记录**，不是「文件非空」）。

### 17.8 本轮纪律核对

- ✅ **未跑任何推理 / 测速**（本轮只读纠偏 + 定位根因 + 改脚本 + 落档）。
- ✅ **未改 `live_caption/`**（ASR-003 铁律）。
- ✅ **未改 `status/asr/CORRECTIONS_ASR.md`**（只读；ASR-006/007 是 reviewer 写的）。
- ✅ **只追加** `## §17`。

## §18 P3 阶段重大发现：OV decoder「取位置 511」语义错误 + NPU 阻塞解除 + INT8 decoder 精度异常（2026-10-25 12:05）

### 18.1 ★★★ 最关键发现：OV decoder IR 恒取位置 511 ⇒ **右对齐**才对
`p1_export_decoder.py` 导出的是 `self.head(h[:, -1:, :])` ⇒ **恒取位置 511 的 logits**。
IR 输入是**静态 [1,512,1024]**；真实内容只有前 T 个位置 ⇒
* **左对齐**（左内容 + 右补零）：位置 511 落在 **padding 区** ⇒ 输出 padding 位置的
  logits ⇒ **生成乱码**（实测 `_difference_difference...` / `umberumberumber...`）
* **右对齐**（左补零 + 右内容）：位置 511 = **最后一个真实 token** ⇒ 正确

**决定性实验**（`results/p3_diag_align.json`）：
| 排布 | OV argmax | torch argmax |
|---|---|---|
| left | 151645 `<|im_end|>` ❌ | 151645 `<|im_end|>` ❌ |
| **right** | **541 `all`** ✅ | **541 `all`** ✅ |

OV left vs right 的 logits cos = **−0.154354** ⇒ 两者语义完全不同。

⚠️⚠️ **由此推翻 §15.3 的 INT8 精度证据**：P1 的 teacher-forcing 判据
（cos=0.999983、top1 100%）**必然无效** —— 因为 OV 与 torch **两侧都取位置 511**
⇒ 两边"错"得完全一致 ⇒ cos 必然接近 1 ⇒ **该指标根本发现不了这个错误**。
⇒ **§15.3 的 enc cos 0.978 / dec cos 0.975 / top1 100% 全部作废**，
  INT8 是否可用**只认 P3 的 61 分钟 WER**（与 ASR-006 §4 的判断一致，
  但本模块找到了更强的技术根据）。

### 18.2 三个语义 bug 及其修复（都在 `scripts/p3_ov_app.py`）
1. **右对齐**（见 18.1）
2. **prefix 不能塞进 prompt 模板**（会打乱 audio_token 展开位置 ⇒ mask 不匹配 ⇒ 崩）
   ⇒ 改为分段拼接 `left + audio + right + prefix`（照 R2T2 `npu_embeds_backend.build_inputs_embeds`）
3. **flush 必须以 `raw` 为前缀**（否则模型从头重生成 ⇒ 每段内容重复两遍，实测过）

⇒ 修正后 30 秒冒烟：5 段文本与 P0 torch 参照**逐段一致**
（`All right. Good morning, everyone. Good morning. Let's get started. So, we.` /
`Welcome to our Q326 QGS.`）⇒ **INT8 量化后文本质量正常（GPU 路径）**。

### 18.3 ✅ NPU 阻塞解除（encoder 动态形状）
**现象**：`ov-encoder-06b-{fp16,int8sym}` 的 `input_features` 是 `[?,?,?]` 全动态 ⇒
NPU 编译失败：`vclAllocatedExecutableCreate4 result: 0x78000004 - [NPU_VCL] Compiler
returned msg: IE.Reshape doesn't support dynamic shapes`（decoder IR 静态 ⇒ 无此问题）。

**修法**（`scripts/p3_staticize_encoder.py`）：`core.read_model()` →
`model.reshape({input(0): ov.PartialShape([1,128,2400]), input(1): ov.PartialShape([1])})`
⇒ ⚠️ OV 2026.4 的 `reshape` 是**原地修改返回 None**；
⇒ 用**模块级 `ov.save_model(model, xml)`** 保存（⚠️ `Model` **没有** `save_model` 方法）。

**验证**（`results/p3_npu_compile_check.json`，NPU 编译全部通过）：
| IR | 编译 | compile_s |
|---|---|---|
| `ov-encoder-06b-fp16-static` | ✅ | 26.60 |
| `ov-encoder-06b-int8sym-static` | ✅ | 20.49 |
| `ov-dec-06b-embed-int8sym` | ✅ | 110.21 |
| `ov-dec-06b-past-int8`（stateful，非本会话产出） | ❌ | 2.90（`to_shape was called on a dynamic shape`）|

⇒ 新增产物：`models/ov-encoder-06b-fp16-static/`（372.8 MB .bin）、
`models/ov-encoder-06b-int8sym-static/`（186.9 MB .bin）。
⚠️ **静态化本身不改变语义**：`results/p3_diag_static_vs_dynamic.json`
⇒ CPU 上动态 vs 静态 **cos = 1.0、maxabs = 0.0**（逐 token 对齐 offset 全 0）。

### 18.4 🔴 INT8 decoder 的 logits 与 FP16 **近乎正交**（CPU 单步实测）
`results/p3_diag_int8_fidelity.json`（同设备内、encoder 固定 FP16、6.4 s 音频）：
| 设备 | INT8dec vs FP16dec 的 logits cos | argmax 相同 | INT8enc vs FP16enc（过 FP16dec） |
|---|---|---|---|
| CPU | **−0.000094** | ❌（541 vs 2403） | **0.999716** ✅ |
| GPU.0 | **−0.139394** | ❌ | 0.999154 ✅ |
| NPU | **−0.129165** | ✅（本例巧合） | 0.999653 ✅ |

⇒ **encoder 量化完好，decoder 量化损坏**（cos ≈ 0 而非 0.9~0.99 ⇒ 不是「精度不够」，
  而是**权重/反量化写错**）。
⚠️ 但「INT8 decoder 坏」是**设备相关**的：在 GPU 上端到端反而**只有 INT8 decoder 正常**（见 18.5）。

**排除项（都有实测产物）**：
| 候选 | 排除依据 |
|---|---|
| lm_head 被误量化 | ❌ **未排除但已确认 lm_head 是 FP16**：INT8 IR 的 lm_head MatMul 输入 = `Convert(Constant float16 [151936,1024])` ⇒ `ignored_scope` **生效** |
| 静态化破坏语义 | `p3_diag_static_vs_dynamic.json`：CPU 动态 vs 静态 cos=1.0 |
| 设备算错（单步） | `p3_diag_dev_mismatch.json`：三设备 encoder cos≥0.9998、decoder cos≥0.994、argmax 相同 |
| 首次推理未预热 | `p3_diag_npu_warmup.json`：NPU 连 5 次 encoder cos 全 0.99998、decoder argmax 全同 |
| 输入长度相关 | `p3_diag_npu_short_input.json`：mf=64/128/320/640 三设备 argmax 全同 |
| 量化配方本身 | torch 侧 fake-quant 196 权重 INT8 per-channel：cos **0.977708**、top1 ✓（**纯 numpy**，不经过 NNCF/OV）⇒ 配方没问题 |

⇒ **差异只能来自 NNCF / OV 的量化实现**。
⚠️ **scale 常量在 IR 的 MatMul 输入链上找不到**（`Multiply` 链只拿到 `[1,1,1024]` 的
fp16 常量，且**全局去重会误判 cycle**，须按路径去重）；数值反推配对
（`results/p3_diag_int8_scale_axis.json`）**frac_equal 中位数仅 0.010** ⇒
**int8 权重与 FP16 权重没能成功配对**，量化轴/广播轴**尚未判定** ⇒ **待查**。

### 18.5 ★ 端到端 2×2 矩阵（GPU.0，真实 10 步段内循环，`results/p3_diag_matrix.json`）
| encoder | decoder | 端到端结果 |
|---|---|---|
| fp16 | **fp16** | ❌ 西里尔文乱码 `šĺģš⇐търьььььььььььььь` |
| fp16 | **int8** | ✅ `All right. Good morning, everyone. Good morning. Let's get started. So, we.` |
| int8 | fp16 | ❌ 乱码 `deššššššššššššššššš` |
| int8 | int8 | ✅ 正常 |

⚠️ **与 CPU 上的单步结论相反**（CPU：FP16 cos 0.9988 正常、INT8 cos 0.038 崩）
⇒ **两个独立问题**：① CPU 上 INT8 decoder 权重/反量化异常；
② GPU 上 FP16 decoder 端到端崩坏（单步 logits 正常 ⇒ 疑似多步累积/数值溢出）。
⚠️ **NPU 侧矩阵正在跑**（`results/p3_diag_matrix.json` 追加 NPU 段）。

### 18.6 ✅ ASR-006 §5 第③点核实结论：**fake-quant 探针没有误量化 tied 权重**
`p2_fakequant_probe.py` 的 `apply_quant()` 对 `embed_tokens` 有守卫
`if nm == 'embed_tokens' and not args.quant_embed: continue`，
而 `--quant-embed` **默认 False** ⇒ **旧 fake-quant 数据未量化 embed_tokens/lm_head**
⇒ 与 OV 侧「ignore lm_head（FP16）+ 量化 196 个层权重」**口径一致**
⇒ **§15.4 第①②条证据链（fake-quant 复现 / 逐层累积）不因这一点作废**，
旧数据（INT8 cos 0.977708 / INT4 cos 0.113752）**仍有效**。

### 18.7 本轮产物清单（全部落盘，附文件数与 mtime 基准）
| 文件 | 内容 |
|---|---|
| `scripts/p3_staticize_encoder.py` | encoder 静态化（reshape + `ov.save_model`） |
| `scripts/p3_npu_compile_check.py` | NPU 编译验证（4 个 IR） |
| `scripts/p3_diag_align.py` | 左/右对齐 × OV/torch 决定性实验 |
| `scripts/p3_diag_dev_mismatch.py` | 三设备 × 精度 交叉对照 |
| `scripts/p3_diag_static_vs_dynamic.py` | 动态 vs 静态 IR 等价性 |
| `scripts/p3_diag_npu_warmup.py` | NPU 连续 5 次预热检验 |
| `scripts/p3_diag_npu_short_input.py` | 4 档输入长度 × 三设备 |
| `scripts/p3_diag_npu_multistep.py` | 复刻 runner 的 10 步逐步对照 |
| `scripts/p3_diag_npu_ablate.py` | encoder/decoder 变量分离（A/B 场景） |
| `scripts/p3_diag_npu_fp16dec.py` | FP16 vs INT8 decoder 判别 |
| `scripts/p3_diag_int8_fidelity.py` | 同设备内精度隔离 + 多 token teacher-forcing top1 |
| `scripts/p3_diag_int8_weights.py` / `_weights2.py` / `_scale_axis.py` | 权重级诊断（配对未成功） |
| `scripts/p3_diag_rootcause.py` / `p3_diag_int8_rootcause.py` | 根因判定（lm_head 确认 FP16） |
| `scripts/p3_diag_graph_dump.py` | 图结构 dump（**须按路径去重**，全局去重会误判 cycle） |
| `scripts/p3_diag_ov_vs_torch.py` | OV × OV × torch 三方对比 |
| `scripts/p3_diag_matrix.py` | 端到端 2×2×N 矩阵 |
| `results/p3_diag_*.json` | 上述全部诊断产物 |

### 18.8 口径与纪律
* **P3 长跑口径**不变：单进程不分 part、真实 `live_caption_app.Segmenter`（B 行为）、
  跑整个 wav（3671.19 s）、640 ms 分块 + 前缀回退 5 token / 前 2 块不用前缀、
  自适应 max_new_tokens、段尾 flush 预算 64。
* **计时作业持 `shared/MACHINE_LOCK`**，串行执行；**准确率作业不需要锁**。
* **WER 全部交 reviewer 复算**，目标机自算只作参考（ASR-004 铁律）。
* **不改 `live_caption/`**（ASR-003 铁律）。rule1 接缝去重已由 **App 模块**完成
  （`live_caption_app.py:648` 起的 APP-012②/APP-014① 注释：整词级 n-gram 去重
  n=3→2→1 + 「后段首词大写 & 前段末尾非句末标点」判据；
  量化收益 A −0.043pp / B −0.060pp，CI 上界<0 ⇒ 显著但**只覆盖 +2.6pp 的约 3%**
  ⇒ **接缝去重不是主因**）⇒ 本模块的 rule1 诊断**降级为可选**，不重复做。
* ⚠️ **INT4 补测仍未做**（ASR-006 §5 第②③点），限时 ≤2h，排在 P3 之后。
* ⚠️ **P0 参照重跑未做**（脚本已修：`rtf_this_run` 已删、`n_runs` 锁定、整个 wav）。
## §19 P3 根因大反转：**撤回「INT8 量化损坏」与「FP16 必崩」**，根因收窄到**输入条件**（2026-10-25 13:40）

### 19.0 本章要撤回的结论（STATUS 只追加，不回头改旧章节）
| 旧章节 | 原结论 | **本章处置** |
|---|---|---|
| §18.4 | 「**INT8 decoder 量化损坏**」（cos ≈ 0 ⇒ 权重/反量化写错） | 🔴 **撤回** —— 10 层静态比对全部相同；且**正交实验显示 INT8 也会退化** |
| §18.5 | 「GPU 上 FP16 decoder 端到端崩坏」「两个独立问题」 | 🔴 **撤回「模型层面」的解读** —— 同一份 FP16 IR 在另一组输入条件下**完全正常** |
| §18.2 | P1 的 teacher-forcing 判据（enc cos 0.999983 / top1 100%） | 🔴 **撤回** —— 判据是**自一致 tautology**（见 §19.3） |
| §18.1 | 「OV decoder IR **恒取位置 511**」 | ⚠️ **部分修正** —— 右对齐结论**仍成立**，但「恒取」不准确（见 §19.4） |
| §15.3 | INT8 的 enc cos 0.978 / dec cos 0.975 / top1 100% | 🔴 **已由 §18 撤回**，本章进一步说明**为何无效**（§19.5） |

### 19.1 ✅ 静态层面：两个 decoder IR **在 10 个层面完全相同**
| # | 层面 | 结果 | 产物 |
|---|---|---|---|
| 1 | 端口 | **相同** | `p3_diag_const_diff.json` |
| 2 | 整数常量（位置/掩码/Range 参数） | **相同** | 同上 |
| 3 | 293 个取位置类算子的索引常量 | **逐条相同** | 同上 |
| 4 | 28 个 SDPA 的 attrs + 输入规格 + mask 溯源 | **完全相同** | `p3_diag_sdpa_spec.json` |
| 5 | lm_head 权重（按输出末维 151936 定位） | **逐位相同** | `p3_diag_int8_deep.json` |
| 6 | 341 个 3D/4D/1D 常量（norm weight / RoPE） | **341/341 相同**（**多重集口径** + 排序逐条 + 序号对照，三口径一致） | `p3_diag_3d_const.json` |
| 7 | 196 个 2D 权重的反量化 | **cos min 0.999929 / p50 0.999960**，量化轴 = **axis 0**（per-output-channel） | `p3_diag_int8_dequant.json` |
| 8 | **全部算子 attrs（1523 个非插入实例）** | **0 差异** | `p3_diag_attrs.json` |
| 9 | 张量精度分布 | **相同**（f32 输出 2661/2661；f16 输出 538 vs 930 的差额 = NNCF 插入的 196 个 scale） | `p3_diag_elemtype.json` |
| 10 | .bin **实际存储精度** | **全部 native**（无「声明 f32 实存 f16」）；f16 2D 权重 0.22% 元素落在 f16 最小正规数以下 | `p3_diag_bin_precision.json` |

补充：**类型直方图差异恰好只有 3 类**（Constant/Convert/Multiply 各 **+196**）⇒
图结构完全一致，**无 FakeQuantize**（未做激活量化）。

⚠️ **本轮踩过的两个坑（方法论，必须记住）**：
* **`get_ordered_ops()` 的序号会漂移** —— NNCF 插入 196×3 个节点 ⇒ 后续序号整体偏移
  ⇒ **不能用序号配对常量/算子**。可靠口径：**多重集比对**（Counter）、
  **类型内第 k 个实例**（仅限 NNCF 不插入的类型）、**friendly_name**。
* **`model.add_outputs(tensor)` 在 OV 2026.4 失败**（"Incorrect type of a value to add as output"）
  ⇒ 可用写法：**`model.add_outputs(consumer_op.input_value(i))`**（加的是消费者的输入端口）。

### 19.2 🔴★★ 决定性反转：**FP16 并不崩，INT8 反而退化**（`results/p3_diag_surgery.json`）
CPU、**固定 6.4 s 音频**、**无 prefix 回退**、每步 8 token 贪心：
| 图 | 10 步首 token | 判定 |
|---|---|---|
| **fp16** | `all` → ` right` → ` good` → ` morning` → ` everyone` → ` good` → ` morning` → ` let` → `'s` → ` get` | ✅ **全程正常英文** |
| **fp32**（重新保存） | **与 fp16 逐位相同** | ✅ ⇒ `compress_to_fp16` **无损**（复核 §18.5 的说法） |
| **int8** | `All` → ` right` → `.` → ` Good` → ` morning` → ` everyone` → `.` → ` Good` → ` morning` → `.` | ⚠️ **重复退化**（`.`↔`Good`/` morning` 2-token 循环） |

⇒ **两个 IR 都没有「坏」**；退化是**输入条件**触发的。
⇒ 前序「FP16 端到端必崩 / INT8 正常」是**特定输入组合下的现象**（§19.3）。

### 19.3 🔴 teacher-forcing 判据是**自一致 tautology**（`p2_multitoken_top1.json` 原始字段）
`ov_fp16_gpu.per_segment[0]`：
```
target  = [97622, 97622, 97622, 97622, 4824, 97622, 4824, 4824, ... ×20]
argmax  = [97622, 97622, 97622, 97622, 4824, 97622, 4824, 4824, ... ×20]
```
* 4824 = `ь`、97622 = `系统` 一类 ⇒ **target 序列本身就是退化重复**
* FP16 的「top1 100%」= **拿自己的退化输出当 target 再对齐自己** ⇒ **恒等于 100%**
⇒ **该判据对 FP16 完全无效**，对 INT8 的 72.02% 也只是「偏离退化模式的程度」
⇒ **不能再用它比较 FP16/INT8/INT4 优劣**。
⇒ 顺带解释 §18.4 的「logits cos ≈ 0」：teacher-forcing 明细显示 INT8 只在
**2 个 margin 极小**的位置翻转（margin **0.77** / **0.027**），其余 **10/12 命中且 margin 很大**
⇒ **151936 维稀疏 logits 的全向量 cos 不可作为「模型坏了」的判据**。

### 19.4 ⚠️ 修正 §18.1：「恒取位置 511」不准确，但**右对齐仍然正确**
* `p3_diag_align.json`（CPU，单步）：**左对齐时 FP16 与 INT8 都给 `<|im_end|>`**
  （top5 = `['<|im_end|>',' case','�','  \n','\n']`）⇒ 左对齐让 511 落在 padding 区 ⇒ 输出无意义
  ⇒ **右对齐是必须的**（结论不变）。
* `p3_diag_pos_sem.json`：同一份 embeds 放在 512 窗口的 **3 个不同 offset**（0 / 100 / 411）
  ⇒ **logits 完全不同**（FP16 offset0→`<|im_end|>`、offset100→`.”`、offset411→`all`）
  ⇒ IR **不是**「恒取 511」，位置计算**依赖内容落点**。
* 运行时抓取位置链（`p3_diag_rope_probe.json`）：两图的 position id 张量
  **完全相同**（`ScatterNDUpdate` 输出 min 0 / max 511 / 非零 98112；
  `Gather` 输出 min 0 / max 511 / 非零 32704）⇒ **位置语义两图一致**。

### 19.5 ✅ 其余假设逐条排除（均有产物）
| 假设 | 排除依据 | 产物 |
|---|---|---|
| 精度提示（f16 vs f32） | FP16 端到端在 **f32 提示下仍乱码** ⇒ 非精度问题 | `p3_diag_precision_hint.json` + `p3_diagcheck_gpu_fp16dec_f32/` |
| 内容长度 / RoPE 位置偏移 | 长度扫描 L=26→115：FP16 **全程**乱码、INT8 逐步转正常 | `p3_diag_len_sweep.json` |
| 设备相关（CPU vs GPU） | 乱码模式**逐字相同**（`'šĺģ�šĺģ�'` / `'ьььььььь'`）⇒ **确定性的图级差异，不是数值噪声** | `p3_diag_device_steps.json` |
| IR 权重被 f16 舍入损坏 | FP16 IR 权重 vs torch `named_parameters`：**197/311 匹配、cos = 1.0、relerr = 0** | `p3_diag_ir_weight_check.json` |
| `compress_to_fp16` 损坏图 | 以 `compress_to_fp16=False` 重新保存：**0 个常量变化**，bin 字节数完全相同（1,192,582,552） | `p3_diag_f32_save.json` |
| 编译后 fusion 不同 | 编译后算子数 FP16 **1824**；INT8 图 `get_runtime_model()` **触发 segfault** ⇒ 该口径**不可用**（如实记录） | `p3_diag_compiled.py`（未落盘结论，脚本在） |

### 19.6 🔴 待隔离的两个变量（**正在跑**：`p3_diag_orthogonal.py` → `p3_diag_orthogonal.json`）
| 脚本 | 音频 | prefix 回退 | FP16 | INT8 |
|---|---|---|---|---|
| `p3_diag_surgery.py` | **固定 6.4 s** | **无** | ✅ 正常 | ⚠️ 退化 |
| `p3_diag_device_steps.py` / `_len_sweep.py` | **逐步累积** 0.64→6.4 s | **有**（回退 5 token） | ❌ 乱码 | ✅ 正常 |
| `p3_ov_app.py`（真实 App） | 逐步累积 | 有 | ❌ 乱码 | ✅ 正常 |

⇒ **V1 = 音频累积长度**、**V2 = prefix 回退**，正交实验 2 图 × 3 模式 × 2 prefix = 12 组。

### 19.7 ⚠️ P3 61 分钟长跑（GPU.0 + INT8 enc + INT8 dec）的计时口径**作废**
* 产物：`qwen3asr_06b/results/p3_p3_61min_gpu_int8/segments.jsonl`（**13:05 时 67 段 → 13:38 时 254 段**，
  文本持续为正常英文，如 `Moving forward. Okay, next slide. Alex, share this…`）。
* 🔴 **`timing_valid = false`**：本作业 **12:56** 启动时 `shared/MACHINE_LOCK` **已被 `mt` 模块占用**
  （内容 `module: mt / pid: 34440 / started: 2026-10-25 11:19:54`，进程存活，
  命令行 `_run_h016_v5_batches.py`）⇒ **计时被其它模块干扰**
  ⇒ **质量数据可用，RTF / P50 / P95 / 首字延迟 / 内存一律不得引用**。
  ⇒ 后续如需计时，**必须先确认锁空闲**再启动。

### 19.8 本轮产物清单（全部落盘；mtime 2026-10-25）
| 脚本 | 产物 | 关键结论 |
|---|---|---|
| `scripts/p3_diag_3d_const.py` | `results/p3_diag_3d_const.json` | 341/341 相同（三口径） |
| `scripts/p3_diag_elemtype.py` | `results/p3_diag_elemtype.json` | 精度分布相同 |
| `scripts/p3_diag_bin_precision.py` | `results/p3_diag_bin_precision.json` | 存储精度全 native |
| `scripts/p3_diag_attrs.py` | `results/p3_diag_attrs.json` | **1523 实例 attrs 0 差异** |
| `scripts/p3_diag_align.py` | `results/p3_diag_align.json` | 左对齐两图都 EOT |
| `scripts/p3_diag_pos_sem.py` | `results/p3_diag_pos_sem.json` | offset 会改 logits |
| `scripts/p3_diag_rope_probe.py` | `results/p3_diag_rope_probe.json` | 位置 id 运行时相同 |
| `scripts/p3_diag_device_steps.py` | `results/p3_diag_device_steps.json` | 跨设备乱码逐字相同 |
| `scripts/p3_diag_surgery.py` | `results/p3_diag_surgery.json` | **FP16 正常 / INT8 退化** |
| `scripts/p3_diag_orthogonal.py` | `results/p3_diag_orthogonal.json` | （在跑）正交隔离 |
| `scripts/p3_diag_compiled.py` | （未落盘，INT8 图 segfault） | 编译后图口径不可用 |
| `scripts/p1_export_decoder_f32.py` | （待跑）真 f32 导出（`compress_to_fp16=False`） | 备用解法路径 |

### 19.9 口径与纪律（补充 §18.8）
* **本模块不得再宣称「FP16 更好」或「INT8 更好」**，直到 §19.6 的正交实验定因。
* **不得用 teacher-forcing top1 比较 FP16/INT8/INT4**（自一致 tautology，§19.3）。
* **不得用「logits 全向量 cos」判「模型坏了」**（151936 维稀疏尖峰，§19.3）。
* 后续若要改判据：应使用**非退化的目标**（例如 reviewer 给定的真值文本 / torch 自然排布的
  贪心输出），并**同时报告 argmax 与 top-5 命中**（`p3_diag_align.json` 显示
  FP16 top5 含 `All`、INT8 top5 含 `Alright` ⇒ **两者答案都在 top5，只是排序不同**）。
* **P3 长跑的质量数据（转写文本）可用；计时数据全部作废**（§19.7）。

### 19.10 ✅✅ 正交实验完成（`results/p3_diag_orthogonal.json`）：**两个 IR 都会退化**，只是阈值不同
CPU、每步 8 token 贪心、6 步；`fixed` = 固定 6.4 s 音频，`cum1` = 累积到 0.64 s，
`cumN` = 累积到 n×0.64 s；`prefix` = 是否启用「回退 5 token 前缀」。
| 图 | 模式 | prefix | step1 (L=26) | step2 | step4 | step6 | 判定 |
|---|---|---|---|---|---|---|---|
| **fp16** | fixed (L=101) | ✗ | `all right good morning everyone…` | 同上 | 同上 | 同上 | ✅ **正常** |
| **fp16** | fixed (L=101) | ✓ | `all right good morning…` | ` morning everyone…` | ` get started so very very very` | ` very very very…` | ⚠️ **退化**（`very` 复读） |
| **fp16** | cum1 (L=26) | ✗ | `��ℿ�ℿ�` | 同上 | 同上 | 同上 | ❌ **乱码** |
| **fp16** | cumN | ✗ | `��ℿ�ℿ�` | `��ℿ�` | `šĺģ�šĺģ�` | `š�ъразьшьь` | ❌ **乱码** |
| **fp16** | cumN | ✓ | `��ℿ�ℿ�` | `��칩�ли` | `šĺģ�šĺģ�` | `ьъисъешьъеш` | ❌ **乱码** |
| **int8** | fixed (L=101) | ✗ | `All right. Good morning everyone…` | 同上 | 同上 | 同上 | ✅ **正常** |
| **int8** | fixed (L=101) | ✓ | `All right. Good morning…` | ` Good morning everyone…` | `. Let get started. So well.` | ` started. So well.` | ✅ **正常** |
| **int8** | cum1 (L=26) | ✗ | **`��系统。`** | 同上 | 同上 | 同上 | ❌ **乱码（INT8 也乱码！）** |
| **int8** | cumN | ✗ | `��系统。` | `System.` | `All right. Good morning.` | `All right. Good morning everyone. Good` | ✅ **正常** |
| **int8** | cumN | ✓ | `��系统。` | `System.` | `All right. Good morning.` | `. Good morning everyone. Good morning.` | ✅ **正常** |

⇒ **结论 1**：**L=26（0.64 s）时 FP16 与 INT8 都输出乱码**
（FP16 `��ℿ�ℿ�` / INT8 `��系统。`）⇒ **短输入退化不是量化问题**
⇒ §18.4「INT8 量化损坏」与 §18.5「FP16 端到端崩坏」**均不成立**。
⇒ **结论 2**：**阈值不同** —— FP16 需 L≳101 才正常，INT8 **L≳35 即正常**
（INT8 在这一点上**更稳**）。
⇒ **结论 3**：**prefix 回退**在 FP16 上会诱发 `very very very…` 复读（INT8 不受影响）
⇒ prefix 回退把「已生成的 token」重新喂回，**FP16 对此更敏感**。
⇒ **结论 4**：先前「FP16 全程乱码」只在 **L≤68 的累积模式**成立，
在 **L=101 固定音频**下 FP16 **完全正常** ⇒ **「FP16 必崩」的说法过宽**。

### 19.11 ✅ 判读口径再修正：**「乱码」≠「模型坏」**
* 短输入（L=26）下**两个模型都**给出乱码 ⇒ 这是**该输入下的正常行为**
  （0.64 s 音频只含 1~2 个词，模型本来就没内容可转写）。
* **下一必须查的量**：乱码档的 logits 是否出现 **NaN / Inf**（f16 溢出）、
  **top1 margin**（排序脆弱）、**softmax 熵**（模型没主意）。
  脚本 `scripts/p3_diag_logit_health.py` → `results/p3_diag_logit_health.json`（**在跑**）。
* ⚠️ 在该实验出结果前，**本模块不使用「崩坏 / 损坏」这类措辞**，
  统一表述为「**该输入条件下输出退化**」。

### 19.12 ✅★ **机制查清**：「乱码」是**置信度平坦 + 贪心漂移**，不是数值损坏（`results/p3_diag_logit_health.json`）
CPU、累积音频档位、每档测**单步** logits 的健康度：
| 图 | nstep | L | NaN | Inf | logit_max | top1_margin | **熵** | mass_top1 | top1 | top5 |
|---|---|---|---|---|---|---|---|---|---|---|
| fp16 | 1 | 26 | 0 | 0 | 16.95 | 1.690 | **5.796** | 0.192 | `�` | `�`,`<\|im_end\|>`,`�`,`ъ`,`ǥ` |
| fp16 | 2 | 35 | 0 | 0 | 16.49 | 0.986 | **5.960** | 0.130 | `�` | `�`,`razil`,`de`,`RectTransform`,`ći` |
| fp16 | 4 | 51 | 0 | 0 | 15.61 | 0.460 | **5.900** | 0.077 | `š` | `š`,`�`,`ｂ`,` реб`,`bris` |
| fp16 | 6 | 68 | 0 | 0 | 17.09 | 1.801 | **4.726** | 0.344 | `š` | `š`,`RectTransform`,`št`,`man`,`ż` |
| fp16 | 8 | 85 | 0 | 0 | 17.59 | 0.273 | **5.505** | 0.133 | `all` | `all`,`아`,`de`,`every`,`<\|im_end\|>` |
| fp16 | 10 | 101 | 0 | 0 | 21.46 | 1.677 | **4.983** | 0.256 | `all` | `all`,`aff`,`right`,`All`,`language` |
| fp16 | 11 | 110 | 0 | 0 | 23.07 | 1.461 | **1.017** | 0.747 | `All` | `All`,`all`,`Right`,`Everything`,`l` |
| int8 | 1 | 26 | 0 | 0 | 20.65 | 0.270 | **5.437** | 0.192 | `�` | `�`,`<\|im_end\|>`,`�`,`раз`,`�` |
| int8 | 2 | 35 | 0 | 0 | 19.49 | 1.240 | **5.704** | 0.182 | `System` | `System`,`.`,`system`,`emotion`,`son` |
| int8 | 4 | 51 | 0 | 0 | 20.41 | 0.045 | **1.038** | 0.490 | `All` | `All`,`all`,`I`,`Right`,`Good` |
| int8 | 6 | 68 | 0 | 0 | 20.31 | 1.067 | **0.693** | 0.733 | `All` | `All`,`all`,` All`,`Alright`,`Right` |
| int8 | 8 | 85 | 0 | 0 | 20.66 | 0.668 | **0.750** | 0.653 | `all` | `all`,`All`,`I`,`’all`,` All` |
| int8 | 10 | 101 | 0 | 0 | 21.09 | 0.767 | **0.774** | 0.669 | `All` | `All`,`all`,`Alright`,`Right`,`I` |
| int8 | 11 | 110 | 0 | 0 | 20.43 | 1.598 | **0.646** | 0.810 | `All` | `All`,`all`,`Alright`,`Right`,`I` |

**判读（三条硬结论）**：
1. ✅ **没有任何 NaN / Inf / f16 溢出**（`f16_overflow` 全 false，logit_max ≤ 23.07 ≪ 65504）
   ⇒ **排除「数值溢出 / NaN」这一整类原因**。
2. ✅ **FP16 的 logits 是「平坦」的**：熵长期停在 **4.7~6.0**（≈ln(120)~ln(400)）
   ⇒ 模型**没有主意**，正确答案常在 **top5 内但排名靠后**
   （L=101 时 top5 = `all`,`aff`,`right`,`All`,`language` ⇒ 正确项 `right`/`All` 在第 3/4 位）。
   ⇒ **贪心解码一旦选中 `all`（而非 `All`），后续 token 分布随之漂走 ⇒ 输出乱码**。
   ⇒ **「乱码」= 置信度不足导致的贪心漂移**，不是模型损坏。
3. ✅ **INT8 的 logits 是「尖锐」的**：从 L=51 起熵就降到 **~1.0 并保持**
   ⇒ top1 稳定 ⇒ 输出正常。
   ⇒ **INT8 在「置信度」这个维度上确实比 FP16 稳**（不是「INT8 量化更好」，
   而是在**这个具体输入分布上**更稳）。

⚠️ **判据口径再收紧**：**「top1 不对」不等于「模型错」** —— 必须看 **top-5**
（FP16 在 L=101 的正确答案就在 top5）。⇒ **后续所有质量判定都要同时报 top-5 命中**。

## §20 收到 ASR-007 / ASR-008 / ASR-009：**INT4 补测完成（「0.6B INT4 不可行」被证伪）** + 对比矩阵更新（2026-10-25 16:40）

### 20.0 本章处理的纠偏条目与执行结果一览
| 条目 | 要求 | 本轮结果 | 产物 |
|---|---|---|---|
| **ASR-007** | 交付 R2T2 × 0.6B 的「精度 × 设备」对比报告 | ✅ **矩阵更新**（16 格，每格一份 json + `MATRIX.md`/`MATRIX.json`）；0.6B 的 INT8/INT4 格子由本轮补全 | `qwen3asr_06b/reports/compare/`（**17 个文件**，含 2 个新 INT4 格子） |
| **ASR-008 / ASR-009** | 继续做：0.6B INT8（App 路径，持锁）→ INT4 限时补测 → 切点重复诊断 → R2T2 对比 0.6B 报告 | ✅ ① **INT4 限时补测完成且结论反转**（§20.2/§20.3）② **INT8 61 分钟质量数据已落盘**（§20.4）③ **切点重复诊断已完成**（§20.5，由并发会话产出）④ **对比矩阵已更新**（§20.6） | 见上 |
| **ASR-006 §5②** | GPU 上 `INT4_ASYM g128 + AWQ + SE`（backup INT8_ASYM，lm_head 保 FP16），5 分钟切片贪心解码看文本是否正常 | ✅ **文本正常 ⇒ INT4 可用** | `results/p3_int4_slice/`、`results/p3_int4_fixedlen/` |
| **ASR-006 §6** | P3 走 App 路径、单进程、跑整个 wav | ✅ **已跑完整个 wav（3671.19 s）**，553 段 | `results/p3_p3_61min_gpu_int8/`（4 文件） |

### 20.1 ✅★ 最重要结论：**「0.6B INT4 不可行」被本轮数据证伪**（但**配方必须换**）
ASR-006 §5 把「0.6B INT4 不可行」降级为「证据不足，暂不关闭」。本轮做完 §5② 后：

| 配方 | 5 分钟切片总词数 | 定长 top1 | 定长 top5 | 判定 |
|---|---|---|---|---|
| **INT8**（INT8_SYM per-channel，lm_head FP16） | **928** | **70.83%** | 87.90% | ✅ 基准 |
| **INT4_ASYM g128 + AWQ + SE**（backup INT8_ASYM） | **882** | **69.44%** | 85.71% | ✅ **可用，与 INT8 同量级** |
| **INT4_SYM 按通道 + AWQ + SE**（= R2T2 R2 照搬） | **98** | **16.27%** | 28.77% | 🔴 **崩坏** |
| FP16（对照） | 164 | 89.29% | 94.44% | ⚠️ 见 §20.3 |

* ⇒ **0.6B 的 INT4 可用**（INT4_ASYM g128 路线），**「不可行」结论被推翻**。
* ⇒ **但照搬 R2T2 的「按通道 + AWQ + SE」配方在 0.6B 上不成立**
  ⇒ 差异来自**模型规模/宽度**，不是配方本身的普遍性。
* ⚠️ 本轮用的是**代理指标**（词数 / 文本健康度 / token 级命中率），**不是 WER**
  ⇒ 质量等级**必须由 reviewer 用本机 baseline 复算 61 分钟全长 WER**后才能下结论。

**原始字段（可复核）**：
* 量化产物 `qwen3asr_06b/results/p2_quant_decoder_int4__asymg128.json`（15:58，2153 B）
  - `recipe` = `"INT4_ASYM g128 ratio=1.0 + AWQ + SE + backup=INT8_ASYM"`
  - `dst_mib` = **518.3**（源 1139.4，`size_ratio` 0.4549）
  - `dst_const_stats.n_i4` = **392**（uint4_t）、`n_i8` = **0**、`n_f16` = 538
  - `ignored_scope` = `["linear_196/aten.linear.default/MatMul"]`（**lm_head 保 FP16** ✔）
* 切片解码 `results/p3_int4_slice/summary_all.json`（16:12/16:16/16:20/16:27，4 个 `summary.json`）
* 定长判据 `results/p3_int4_fixedlen/summary_all.json`（16:28/16:30/16:32/16:34，4 个 `summary.json`）

### 20.2 ✅ INT4 补测的做法（ASR-006 §5② 原文要求的口径）
**新配方量化**（`scripts/p2_quantize.py` **本轮新增 `--asym` / `--backup-asym` 开关**，
因为原脚本只有 INT4_SYM + backup INT8_SYM，**不支持 §5② 指定的 INT4_ASYM + INT8_ASYM**）：
```
python scripts/p2_quantize.py --model decoder --int4 --asym --backup-asym \
    --group-size 128 --calib results/p2_calib_decoder.npz --tag _asymg128
```
⇒ 耗时 3m50s，NNCF 统计：`int4_asym, group size 128` 覆盖 **196/196** 个 ratio-defining 参数，
`float` 1/197（= lm_head，ignored_scope 命中）✔
（校准集只有 64 条 < subset_size 128，NNCF 有 WARNING 但不影响结果）。

**判据脚本**（本轮新写 2 个）：
| 脚本 | 用途 | 设计 |
|---|---|---|
| `scripts/p3_int4_slice_decode.py` | §5② 原文的「5 分钟切片贪心解码」 | 走**真实 App 路径**（`live_caption_app.Segmenter` B 行为 + 640 ms 分块 + 前缀回退 5 token + **自适应 max_new_tokens** + 段尾 flush 64） |
| `scripts/p3_int4_fixedlen.py` | **干净判据**（隔离累积长度与前缀两个变量） | **固定 6.4 s（L=101 mel 帧）+ 关闭前缀** ⇒ 文本差异**只能**来自权重量化 |

⚠️ **为什么必须加「定长」这一路**（§19 的直接应用）：
`p3_int4_slice_decode.py` 的**累积**路径下，**FP16 自己也退化**
（`results/p3_int4_slice/fp16/summary.json`：`total_words` 仅 **164** vs INT8 **928**，
`nonlatin_ratio` **0.8023**、43/46 段非拉丁占比 >30%）
⇒ §19 已证明：**累积路径下 L=26 的短输入会让 FP16 和 INT8 都输出乱码**
⇒ 在累积路径上「谁正常」被**首段短输入 + 前缀污染**主导 ⇒ **测不出量化差异**。
⇒ 定长路径（`p3_int4_fixedlen.py`）才是能判 INT4 好坏的干净口径。

### 20.3 ✅ 定长口径下的完整对照（`results/p3_int4_fixedlen/summary_all.json`）
**设计**：固定 6.4 s（L=101 mel 帧）+ 无前缀 + encoder 固定 OV FP16（**非量化**）
⇒ 被测的**只有 decoder 的权重量化**。评测段 20 个，全部取自 **≥12 分钟** 区段
（校准集 0–12 分钟不含评测音频），共 **504** 个 target token。

| 变体 | top1 命中 | top1 % | top5 % | 总词 | 替换字符 | 非拉丁占比 | 复读 top1 | 段非拉丁>30% |
|---|---|---|---|---|---|---|---|---|
| **fp16**（参考） | 450/504 | **89.29%** | 94.44% | 244 | 0 | 0.2090 | 0.0451 | 3 |
| **int8** | 357/504 | **70.83%** | 87.90% | 396 | 0 | 0.2259 | 0.0354 | **0** |
| **int4_asymg128** | 350/504 | **69.44%** | 85.71% | 363 | 0 | 0.2214 | 0.0386 | 2 |
| **int4_sym_chan** | 82/504 | **16.27%** | 28.77% | 20 | 0 | 0.0815 | 0.0500 | 2（复读段 20） |

**文本样例（原始字段 `transcript`）**：
* int8：`"But we're making good progress. Just last week, we powered on our. Our."`
* int4_asymg128：`"But we are making good progress. Just last week, we powered on our. Our. Our."`
  ⇒ **正常英文**，与 INT8 几乎逐词一致
* int4_sym_chan：`"â颈âчь蹄nisnistrasnisurenisnisurenisnisurenisnisuris…"` ⇒ **崩坏**

⚠️ **口径声明**：top1/target 来自 **FP16 参考自己的贪心输出**（非退化目标，
§19.2 已证明 FP16 在 L=101 正常）⇒ **不是 §19.3 那种自一致 tautology**
（§19.3 的 target 是 4824 'ь' 连续 20 次的退化序列）。
⚠️ 但 **FP16 的 top1 只有 89.29%（不是 100%）** ⇒ 这个指标本身**对 0.6B 敏感**
（与 ASR-006 §5 退回旧判据的理由一致）⇒ **必须与 top5 一起读**
（§19.12 的收紧口径），且**不能单独用它定「可用/不可用」**
⇒ 本章的判定依据是**文本本身是否正常**（词数 + 非拉丁占比 + 复读率），
top1/top5 只作**同口径的相对对照**。

### 20.4 ✅ P3 INT8 的 61 分钟全长**质量**数据（`results/p3_p3_61min_gpu_int8/`）
**产物（4 个文件）**：`summary.json`（15:07，2366 B）、`segments.jsonl`（14:12，142560 B）、
`segments.json`（14:12，164733 B）、`transcript.txt`（14:12，75526 B）。

| 字段 | 值 |
|---|---|
| `audio_sec` / `covered_s` | **3671.189 / 3671.189**（`complete` = **true**）⇒ **跑的是整个 wav，未截断** ✔（满足 ASR-006 §3） |
| `n_segs` | **553** |
| `rule_counts` | rule1 **518** / rule2 **34** / flush **1** |
| `total_words` | **11825** |
| `n_steps_total` | 5737 |
| `seg_dur_p50` / `p95` / `max` | **6.4 / 8.96 / 12.16** s |
| `segmenter` | `live_caption_app.Segmenter（真实 App 切段器，B 行为）` |
| `timing_valid` | **false** |

🔴 **该次运行的计时数据全部作废**（§19.7 已记，此处补上**锁路径**这一条新证据）：
* 启动时规范路径 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK` 已被 `mt` 占用
  （PID 34440 存活）⇒ 计时被干扰；
* ⚠️ **且本次 ASR 把锁写在了仓库内相对路径**
  `confucius4-openvino\shared\MACHINE_LOCK`（内容 `asr PID=8363 start=2026-10-25 12:56:21`）
  ⇒ **App / MT / TTS 在规范路径上看不到这把锁** ⇒ 互锁失效
  （TTS 的 `shared/NOTICE_tts_lock_path_20261025.md` 已实测记录此事，
  且 TTS 因此反复拿到 `timing_valid=false`）。
* ⇒ 本轮**已回收**该孤儿锁（PID 8363 已不在），并**新写**
  `scripts/p3_run_with_lock.py`：只用**规范路径**、写锁时**同时写两种格式**
  （README 单行 + key-value）、读锁支持**多编码回退**（utf-8/gbk/cp936/latin-1）、
  **PID 不在则回收**、**`finally` 保证删锁**（不留孤儿）。
* ⇒ **规范路径持锁重跑已启动**（`results/p3_p3_61min_gpu_int8_locked/`），
  16:23 起在等 `app` 的锁（PID 32652 存活）⇒ 本章**未拿到**其计时结果。

### 20.5 ✅ ASR-006 §2 切点重复诊断已完成（**由并发会话产出，本线程只引用不改代码**）
产物：`confucius4-openvino/results/asr_diag/asr006_rule1_cut_diag.{py,json,md}`
（`json` **1 777 399 B** / `md` **18 323 B**，mtime **16:35**；脚本 71 232 B，mtime 16:22）。

**机制结论（`.md` §0）**：规则1 的语义是「**最近 3 秒内存在一段 ≥300 ms 静音**」
（`find_silence_in_range` 只取 not-None，中点不参与定位），
而**切点落在实时喂音的 chunk 栅格**（`CHUNK_SEC=0.64 s`）
⇒ **静音位置与切点位置解耦** ⇒ 切点可以落在词中间。
对照：规则2 用 `find_trailing_silence`（紧贴末尾）+ ≥0.8 s ⇒ 规则2 切点天然落在词间隙。

**关键数字**：
| 量 | A 组 | B 组 |
|---|---|---|
| 段数 / 切点（不含 EOF） | 538 / 537 | 558 / 557 |
| 切点分类 | rule1 **503** / rule2 20 / flush 14 | rule1 **508** / rule2 36 / flush 13 |
| **rule1 占全部切点** | **93.67%** | **91.20%** |
| 「切在词中间」（N=2 后缀匹配） | **9.54%**（48/503 rule1） | **10.93%**（55/508 rule1） |
| N=3 / N=4 | 7.95% / 7.36% | 9.15% / 8.55% |
| **静音内切点的「切在词中间」比例** | **0.0%**（sil −40/−45/−50 三档全部） | **0.0%**（三档全部） |
| 非静音切点的「切在词中间」比例 | 10.77% / 10.48% / 10.18% | 11.56% / 11.30% / 11.09% |

🔴 **「重复词去重」路线的天花板远低于 +2.63pp**（`.md` §4b，已与 reviewer 观测交叉核对）：
reviewer 观测 A 对交付基准 **+2.63pp**（CI [1.80, 3.41]）、插入 641 对 463、**多 178 个**；
而「同一个词在接缝两侧各被转写一次」这种形态在 A 组**只有几十个接缝**：

| 口径 | rule1 接缝数 | 可消词数（上界） | 估计 WER 收益（上界） | 占 reviewer 多余插入 |
|---|---|---|---|---|
| N=2 | 55 | ≤110 | ≤0.963pp | **≤61.8%** |
| N=3 | 46 | ≤92 | ≤0.806pp | ≤51.7% |
| N=4 | 43 | ≤86 | ≤0.753pp | ≤48.3% |

⇒ **独立量化证实 §18.8 的结论「接缝去重不是主因」**（App 已实现的整词级 n-gram 去重
量化收益只有 −0.043pp / −0.060pp）⇒ **剩下的插入是 ASR 本身的识别错误**
（切点附近上下文被截断/错切），**不是**去重能消的
⇒ 要动就得**改切点位置本身**（把切点移到静音中点），**属 App 模块**（ASR-003 边界）。

**离线去重模拟的收益上界（A / B 组）**：
`plan1_ngram_keep1` 22/22 词（≤0.193pp / ≤0.228pp）、`plan2_seq_L1` 36/42 词
（≤0.315pp / ≤0.369pp）、`plan2_charprefix_kmin2_L1` 51/51 词（≤0.447pp / ≤0.448pp）、
`plan2_charprefix_kmin2_L4` 361/442 词（≤3.161pp / ≤3.882pp），
`plan3_merge_non_silence_rule1_sil40` 34/40 词（≤0.298pp / ≤0.351pp）
⇒ **收益随 L 放大，但 L 越大误删风险越高** ⇒ 需 reviewer 复算取舍。

**「把 rule1 的静音要求从 300 ms 提到 X」的离线指标（`.md` §5b）**：
🔴 **`min_silence_ms=300` 与 `SIL_LOOKBACK_SEC=3.0` 在 `live_caption_app.py` 里是硬编码、没有 env**
⇒ **真正提高它必须改代码（App 模块）**，不是「只改 env」能做到。
（sil_db=−40 时：req≥500 ms ⇒ 51.69% 的 rule1 切点不再触发；req≥800 ms ⇒ 94.63%；
req≥1000 ms ⇒ 97.61%）

**env 重放保真度**（`.json` → `groups.{A,B}.env_replay`）：
`baseline` 重放与产物切点的匹配率 A **99.63%** / B **99.64%** ✔
⇒ env 重放口径可信；`MIN_SEG_SEC=8/10/12` 会把匹配率降到 ~29%（切点整体前移），
`SIL_REL_DROP=6`（B 组）把 rule2 从 36 提到 111 ⇒ **相对化静音阈值会大幅改变切点分布**，
这些都只是**切点层面的中间量**，不等于 WER 收益。

### 20.6 ✅ ASR-007 对比矩阵已更新（`qwen3asr_06b/reports/compare/`）
**目录现有 17 个文件**（mtime 2026-10-25 16:36）：
`MATRIX.json`（2363 B）、`MATRIX.md`（**新生成**，汇总表 + 做不了的格子 + 产物清单）、
以及 15 个格子 json。其中**本轮新增/更新 3 个**：
| 格子 | 状态 | 关键字段 |
|---|---|---|
| `qwen3asr_06b__int4_asymg128__gpu0.json`（**新**） | **OK** — 文本正常，与 INT8 同量级 | `accuracy.proxy_metrics_5min_slice.total_words` 882 / `proxy_metrics_fixedlen.top1_pct` 69.4444 / `top5_pct` 85.7143；`timing_valid` = **false**（未持锁） |
| `qwen3asr_06b__int4_sym_chan__gpu0.json`（**新**） | **BROKEN** — 文本崩坏 | `total_words` 98 / `top1_pct` 16.2698 / `top5_pct` 28.7698 |
| `qwen3asr_06b__int4__all.json`（**更新**） | **RESOLVED** — INT4 在 0.6B 上可用（INT4_ASYM g128） | 新增 `resolution_2026_10_25` 字段，含 `evidence_int4_asymg128` / `evidence_int4_sym_chan` / `why_scenario` / `still_missing` / `caveat` |
| `qwen3asr_06b__int8__gpu0.json`（**更新**） | OK — 61 分钟全长跑完（quality OK） | `accuracy.quality_proxy`（553 段 / 11825 词 / rule_counts / 段长 p50 p95 max / `complete`=true）；`latency` 全部标 `timing_valid=false` 并列 `invalid_fields` |

⚠️ **两套计分器仍不可混用**（ASR-002 铁律，`MATRIX.md` 顶部保留该警告）：
* **目标机计分器**：全局对齐 + 分段配对 bootstrap（7.798% / 7.952% / 9.795%）
* **reviewer 计分器**：MiniMax baseline（8.17% / 8.27% / 10.97% / 14.80%）
⇒ **0.6B 的所有 WER 一律空着**（`wer_pct: null`），交 reviewer 复算。

### 20.7 ⏳ 本轮明确**未完成**的（不冒充已交付）
| 项 | 状态 | 原因 |
|---|---|---|
| **0.6B INT8 61 分钟持锁重跑**（交付级计时） | ⏳ **在跑**（16:23 起等 `app` 的锁，PID 32652 存活） | 规范路径锁被 App 持有 ⇒ 按协议等待 |
| **0.6B INT8 / INT4 的 61 分钟全长 WER** | ❌ **未做** | 本模块**不自算 WER**（ASR-002）⇒ 交 reviewer |
| **0.6B INT4 的 NPU 格** | ❌ **未做** | `ov-dec-06b-past-int8`（stateful）在 NPU 上编译失败：`to_shape was called on a dynamic shape`；且非 stateful decoder 在 NPU 上输出复读 prompt |
| **reviewer 指定的 R2T2 R2 标定点**（同口径 teacher-forcing top1） | ❌ **未跑** | 需 R2T2 自己的 encoder 输出 + prompt 模板 + R2 IR；§5① 已把 0.6B 侧的原始 token 级计数给出（`results/p2_multitoken_top1.json`，20 段 / 436 token） |
| **P0 参照重跑** | ❌ **未做** | 排在 P3 之后；P3 INT8 已跑完整个 wav，但 P0 流式参照本身仍少 11.19 s |
| **≥2 次 fresh 进程的交付级 RTF** | ❌ **未做** | 现有都是 n=1 ⇒ 全部 `timing_valid=false` |
| **设备内存峰值/稳态**（iGPU / NPU） | ❌ **未测** | `mem_device` 均为「未匹配到设备」 |
| **模型加载/首次编译耗时（分有缓存/无缓存）** | ❌ **未测** | 只测到冷编译 |

### 20.8 口径与纪律（本章新增的硬规则）
1. 🔴 **锁只能用规范路径** `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`
   ⇒ **仓库内相对路径 `shared/MACHINE_LOCK` 会让 4 模块互锁失效**
   （TTS 已实测记录 ⇒ 本轮据此新写 `scripts/p3_run_with_lock.py`）。
2. 🔴 **「模型好不好」必须先隔离输入条件**（§19 的延续）：
   累积音频 + 前缀回退路径下，**FP16 自己也会退化**
   ⇒ 判权重量化的好坏 ⇒ **必须用定长 + 无前缀** 的口径。
3. 🔴 **代理指标 ≠ WER**：本模块只交**可复核的中间量**
   （总词数 / 替换字符数 / 非拉丁占比 / 复读率 / token 级 top1+top5）
   ⇒ 质量等级交 reviewer 复算。
4. 🔴 **teacher-forcing 判据要配「非退化 target」**：FP16 参考自己在定长输入下的贪心输出
   ⇒ 且**必须同时报 top-5**（§19.12）。
5. **准确率作业不需要锁；计时作业必须持规范锁**（本轮两者的区分已严格落实）。
6. **不跑 CPU 推理**（CPU 只用于单组件诊断，如 NNCF 量化）。
7. **不改 `live_caption/`**（ASR-003 铁律）：本轮只 `import` 其中的 `Segmenter` 做只读重放。
