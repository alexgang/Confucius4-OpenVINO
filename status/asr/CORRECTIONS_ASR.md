## ASR-001 [HIGH] 2026-10-23 09:12 — 模式切换启动单：ASR 模块改用独立的 STATUS_ASR.md 和 CORRECTIONS_ASR.md
### 新的协作方式（2026-10-23 起，用户指示）
整个项目拆成 4 个模块并行：a ASR（R2T2）、b MT（Hy-MT2）、c TTS（Qwen3-TTS）、d App 集成、打包和 git。目标机 WorkBuddy 上每个模块一个线程，本机每个模块一个独立的 reviewer。**各模块只读写自己的 STATUS 和 CORRECTIONS**，旧的共用 `confucius4-openvino\status\CORRECTIONS.md`（C 编号）冻结在 C-135，以后不再使用。
**STATUS 文件格式（reviewer 只读文件开头和新增的章节，以节省双方的上下文）**：
```
# STATUS_<模块>
last_ack: <本模块最新已读的纠偏编号>
更新时间: YYYY-MM-DD HH:MM
当前任务: 一句话
阻塞 / 待用户决定: 无 或 列出
## 最近更新（最多 15 行，新的写在最上面，每行一条：时间 + 结论 + 产物路径）
```
在这之后**只追加**编号章节 `## §N 标题（YYYY-MM-DD HH:MM）`，不要回头改旧章节。旧结论如果错了，就在新章节里写"撤回 §x"。
**证据规则**：结论必须引用结果文件和其中的原始字段；列出的产物要附上文件数和 mtime；没落盘的东西不能写"已交付"。
**共享机器锁**（4 个线程共用一台机器）：计时或测速作业开始前，先创建 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`（内容写：模块名 PID 开始时间），结束后删除。锁已经存在就等待；如果锁的 PID 已经不在，或者锁早于开机时间，可以回收。数值和质量作业不需要锁，但被干扰时要把计时标记为 timing_valid=false。
**用户的总原则**：先保证正确性（和参照一致），后做性能；不在 CPU 上跑推理或测速（CPU 只用于单组件诊断）；质量由 reviewer 用 MiniMax 回转写判定，目标机不自己调用 MiniMax。
### 本模块
- 状态写到 `confucius4-openvino\status\asr\STATUS_ASR.md`（请新建），纠偏读本文件，编号 ASR-xxx。旧的 STATUS.md 和 STATUS_ARCHIVE 作为档案保留。
- 范围：R2T2 模型的 enabling、精度和量化、GPU/NPU 摆放、流式和切段策略、RTF 调优。App 集成、打包和 git 归 app 模块。
- 交付基线（判定时用全长 61 分钟、全局对齐加分段配对 bootstrap）：GPU INT8 WER 8.17%，全 NPU INT8 cleanie RTF 0.772 / WER 7.95%。
- 请先在 STATUS_ASR.md 写出：当前任务、最近一周的结论摘要（引用产物）、下一步计划。写好后 reviewer 开始审查。

## ASR-002 [NORMAL] 2026-10-23 11:12 — 回答 §1 基线出处（两套计分器不能混用）；C-111 冻结、不再在 ASR 线程推进

**读了什么**：STATUS_ASR.md 全文（111 行，last_ack ASR-001）；`reports/c089_int4/R4_npu_full_wer.json`；reviewer 本机 `~/asr_baseline/report/data/npu.json` 与 `OV_vs_CUDA_INT4_INT8_report.md`。

### 1. §1 基线表有两处归因错误，请改正
- 8.17% / 7.95% / 0.772 **来自两套不同计分器**，不能放在同一列比较：
  - **reviewer 计分器**（本机 compare_wer.py + paired_bootstrap.py，MiniMax baseline）：GPU INT8（enc FP16 + dec INT8）= **8.17%**，全 NPU = **8.27%**，Δ = +0.10 pp [-0.41, +0.56]。
  - **目标机计分器**（你的 R4 json 用的同一套）：GPU INT8 参照 = **7.798%**（即 R4 json 的 `ref_wer_pct`），全 NPU INT8 = **7.952%**，Δ = +0.154 pp [-0.288, +0.584]。
  - 全 NPU 61 分钟 RTF：P50 **0.7722**，P95 0.7942，max 0.8152（同一次全长运行，226 段）。
- 所以：表里「GPU INT8 8.17% 产物 = R4 json」是错的（R4 json 里只有 7.798 这个目标机口径的 GPU 参照）；「全 NPU 7.95% = 同上 ref_wer_pct」也是错的（ref_wer_pct=7.798 是 GPU，不是 NPU）。
- **要做的**：§1 改成两列（目标机口径 / reviewer 口径），目标机口径行引用你自己的产物：在 `reports/` 下找全 NPU 61 分钟那次运行（wer 7.952、rtf 0.7722 字段）的 json 并写出路径；reviewer 口径行写「reviewer 本机 asr_baseline/report/data/npu.json」。找不到全 NPU 的 json 就如实写"产物缺失"，**不需要为此补测**。以后做判定时，Δ 只和**同一计分器**的基线比较。
- 验收：§1 每个数字都有产物路径或明确标注出处，且口径一致。

### 2. C-111（translator.py / live_caption_app.py）的归属
- 按 ASR-001 的划分，翻译层和 App 的 outbox 消费属于 MT 模块和 app 模块，**不属于 ASR**。reviewer 已上报主会话，由主会话协调移交；在得到答复前：
  - 保持现状，**不提交 git、不同步客户包、不写 sync 脚本**（客户包归 app 模块）；
  - **不在 ASR 线程跑 `diag_c111_e2e.py`**（翻译模型的端到端计时归 MT 模块；它当时在加载阶段退出，现在 TTS 正持有 MACHINE_LOCK）。
  - 在 STATUS §4 写一段移交说明：改动的文件列表、`diag_c111_half.py`/`diag_c111_own.py` 怎么跑、`hy_bench/runs/c111_half/c111_ownership.json` 的位置，方便接手方直接使用。
- 先前未持锁的 translation e2e 已标为 timing_valid=false，处理正确。

### 3. C-110 结论 reviewer 认可
标点触发切点不实施，现状切段规则（C-108 + C-109 MIN_SEG=6s）不变。`rollback_punctuation=False` 导致尾部 5 token 恒定回退是一条有价值的发现，记录在案即可，**不要擅自改**（会影响定稿行为和 WER，改动需要先给出 61 分钟 WER 配对 bootstrap 方案并经用户同意）。

### 4. ASR 本模块接下来
目前没有在跑的 ASR 作业，交付基线也没有变化。移交 C-111 后如果暂时没有用户指派的 ASR 任务，就**待命**，只维护 STATUS，不要自行开新实验。

## ASR-003 [NORMAL] 2026-10-23 11:17 — 【用户决定】C-111 交给 App 模块；ASR 线程只写移交说明，以后不再改 live_caption 代码
用户已确认 reviewer 的建议：C-111（段尾半句当段就翻，以及段归属）**由 App 模块接手**合入和端到端验证，翻译逻辑由 MT 模块复核。ASR 线程要做的事：
- 在 STATUS_ASR 里写一份**移交说明**：改了哪些文件和函数（附 diff 摘要）、设计意图、已有的测试结果（段归属覆盖率从 84.1% 提到 100% 的口径和产物）、还没完成的事项。
- 写完以后，**不要再改 `live_caption/` 下的任何文件，也不要提交**。它们以后只由 App 线程提交。
- 按 ASR-002 修正基线表（两列口径，注明出处）。之后继续做 ASR 本身的工作：模型、量化、设备摆放、流式和切段策略、RTF。

## ASR-004 [HIGH] 2026-10-24 08:56 — §10 切段改动已随 v1.4 客户包交付，但缺 61 分钟全长质量验证；请补 A/B WER + C-108 空段校验

**读了什么**：STATUS_ASR §8–§11（行 519–1067）；目标机 git：`live_caption/live_caption_app.py` 与 `audio_source.py` 的 §10 改动已由 App 提交 `d0c146e`（2026-10-24 03:18，"v1.4 客户包…App 侧改动入库"），当前文件里有 `SIL_REL_DROP_DB`、`_speech_ratio_ok`，即**新切段策略已经在交付包里**。

**问题**：§10 的验证只覆盖了"定稿间隔、硬切、空段、切点安全"这些切段指标，用的是回环 120s 和**真实演讲 12 分钟**。没有任何 WER 数据。切点位置变了（演讲 108→110 段，规则2 切点 6→10），会直接影响 ASR 的上下文和定稿文本。按 BRIEF：12–27 分钟切片看不出 1–2pp 的差距，**质量判定必须用 61 分钟全长**。另外，你们自己在 §8.6 第 2 条写过"必须重跑 C-108 的空段校验（61 分钟素材，hang 0.8/0.6/0.5 三档）"，这一步也还没做。gain=0.3/0.1 时空段（绝对口径）18→48、35→119，§10.2 只用"口径失真"一句话解释了，没有给出相对口径下的逐档数字。

**要做的**（这是质量作业，不需要机器锁；计时数字不做要求）：
1. 用 <redacted> **61 分钟全长**，走**真实的 `Segmenter`**（和 App 实时路径相同的切段，加上交付配置 GPU INT8，有余力再跑全 NPU），跑 A/B 两组：A=`LIVECAP_SIL_REL=0 LIVECAP_SPK_REL=0 LIVECAP_MIN_REL_COVER=0`（旧行为；如果关掉空段拒切的 env 不是这个名字，请写明你实际用的开关），B=默认（新行为）。每组输出逐段转写 json，字段包括段起止时间、文本、切段规则（rule）。
2. 在同一份 61 分钟素材上重跑 C-108 空段校验（hang 0.8/0.6/0.5 三档），A/B 都要跑。gain 0.3/0.1 档补充**相对口径**的空段数。
3. 把产物路径写进 STATUS 的新章节。**WER 不用你们自己算**，reviewer 会在本机用 MiniMax baseline 跑 compare_wer + paired_bootstrap 做独立复核。

**验收**：B 相对 A 的 Δ WER 配对 bootstrap 置信区间不显著劣化（CI 上界不要明显大于 0，具体以 reviewer 复核为准）；C-108 三档的空段数在 B 下不多于 A。如果 B 显著变差，在 STATUS 里标出来，并给出回退用的 env 组合（不用改代码），由主会话转告 App。

**顺带更正（不单独推送）**：① §5.9 标题写的是"已完成 2026-10-23 12:00"，`ebc6107` 实际提交时间约为 11:14，请改正。② 开头写的"更新时间 15:05"晚于文件实际写入时间（15:02）和提交 `75e82a5` 的时间（15:03），以后请用实际时钟。③ 开始处理本条时，先把 last_ack 改成 ASR-004，并写一行"最近更新"。

## ASR-005 [HIGH] 2026-10-24 09:13 — 【用户新任务】仿照 R2T2 的方法，把 Qwen3-ASR 0.6B 量化成 NPU 能运行的 INT4/INT8 版本；另附 git 冻结协议
### 一、新任务（用户指派）
用户要求：**沿用 Confucius4-R2T2 的方法，把 Qwen3-ASR 0.6B 也做成 NPU 上能运行的 INT8 和 INT4 版本**，作为更小、更快的 ASR 候选。ASR-004（新切段规则的 61 分钟 WER 复核）照旧先做，做完再开始这项。阶段和检查点如下：
- **P0 基准**：从 hf-mirror 或 ModelScope 获取 Qwen3-ASR-0.6B 官方权重，记录版本。先用官方 torch 推理（CUDA）在 61 分钟 <redacted> 上跑出 **离线和流式（640 ms，自适应 max_new_tokens）两份参照转写**，这就是 0.6B 的质量上限。转写交给 reviewer 用 MiniMax baseline 算 WER（全局对齐）。
- **P1 OV 导出（照搬 R2T2 的经验，不要重新踩坑）**：
  - encoder 导出成**整段全局注意力** IR（输入 mel 加 n_valid）。optimum 默认导出的分窗注意力是错的，这是 R2T2 的根因 ①。
  - 窗口计数按 mel_len//800（根因 ②）；max_new_tokens 用官方的自适应规则（根因 ③）。
  - decoder：GPU 用 stateful IR；NPU 用**只保留 inputs_embeds 端口**的标准 KV 形式，走 NPUW_LLM，动态维度要设上界或静态化。每个样例前都要 `reset_state()`。
  - 每一步都用 teacher-forcing 和 torch 对比（cos ≥ 0.999，top1 ≥ 99%）。
- **P2 量化**：
  - INT8_SYM 按通道（R2T2 在 NPU 上的交付配方）；
  - INT4：按通道无校准的版本在 R2T2 上会出乱码，所以直接用 R2T2 验证过的可用配方（按通道 + AWQ + scale estimation，必要时 ratio 0.8 加 hessian），校准集**不能包含评测音频**（用 0–12 分钟校准，≥12 分钟评测）。
  - GPU 和 NPU 各出一版，**NPU 是主要目标**。
- **P3 验收**：
  - 61 分钟全长 WER，和 0.6B 的 torch 参照、R2T2 的交付基线（GPU INT8 8.17% / 全 NPU 7.95%，reviewer 口径）分别做配对 bootstrap；
  - NPU 上的 RTF P50/P95（多次 fresh 进程运行，持机器锁）、首字延迟和内存；
  - 最后给一张对比表：0.6B（INT8 / INT4 × GPU / NPU）对比 R2T2 的交付版本。
- 检查点：P0 结束、P2 结束，各停一次，等 reviewer 复核（最多 30 分钟）。
- 工作目录建议新建 `C:\Users\Trekker-PTL\qwen3asr_06b`，用独立 venv。STATUS 继续写在 STATUS_ASR.md 里，新开章节。
### 二、git 冻结协议
**git 冻结协议（App 改写历史期间）**：App 开始改写之前会创建 `C:\Users\Trekker-PTL\shared\GIT_FREEZE`（内容写起止说明）。**只要这个文件存在，就不要在 `confucius4-openvino` 仓库里 commit、push 或 pull**，可以照常改本地文件，但不要提交。App 改写和强制推送完成后会删掉这个文件，并在 STATUS_APP 里公布改写前后的 SHA 对照。之后已有的本地 clone 要**重新 clone 或者 `git fetch` 后 `reset --hard origin/main`**，不能直接 pull（注意先备份未提交的改动）。

## ASR-006 [HIGH] 2026-10-25 08:35 — P2 检查点复核结论：ASR-004 通过；P3 放行（只做 INT8）；INT4"不可行"结论证据不足，暂不关闭；新发现：App 实时路径比交付基准差 2.6pp（切点处重复词）

**读了什么**：STATUS_ASR §12–§16（行 1117–1891）；拉回本机：`reports/asr004_ab/{transcript,segments}_{A,B}`、`qwen3asr_06b/results/p0_offline/offline_segments.json`、`p0_stream/{stream_transcript.txt,stream_segments.json,p0_stream_summary.json}`；目标机上读了 `results/asr_diag/asr004_ab_chunked.py`、`asr004_ab_remerge.py`、`git check-ignore`。WER 全部由 reviewer 在本机用 MiniMax baseline（ref 10964 词）全局对齐计算。A/B 和 0.6B 的段数不同，所以用"全局对齐→错误归到 hyp 词→按两边共同切点分块"的配对 bootstrap（5000 次）。这个工具已经用 226 段的同切分样本对照过：结果与 `paired_bootstrap.py` 逐位一致（8.17% / 8.27%，CI [-0.39,+0.54] 对 [-0.40,+0.56]）。

### 1. ASR-004：通过，可以关闭
| 组 | WER | S/D/I |
|---|---|---|
| A 旧切段 | 10.80% | 368/175/641 |
| B 新切段（v1.4） | 10.58% | 353/188/619 |
Δ(B−A) = **−0.22pp**，95% CI [−0.64, +0.20]（300 个共同切点块）；按 60 s 网格分块是 [−0.70, +0.25]。B 不劣化，**v1.4 的切段改动不用回退**。
- §14.1 的 merge_group 偏移缺陷**确实存在，修复也正确**：重合并后 A/B 每个 part 都严格覆盖 [240i, 240(i+1)]，无缝隙、无重叠。但它在 `results/asr_diag/`（`.gitignore` 第 87 行排除；`git grep merge_group` 在受控代码里没有命中），只是评测脚本的缺陷，**不是"交付级缺陷"，不影响 v1.4 包**。以后请按实际影响范围定级。

### 2. 新发现（比 ASR-004 本身重要）：App 实时路径的 WER 显著差于交付基准
- A 对交付基准 `int8dec_fp16enc`（8.17%，226 段）：**+2.63pp，CI [+1.80, +3.41]，显著**。B 同样约 +2.4pp。
- 主要来源是插入：641 对 463，多 178 个。按位置统计，多出来的插入集中在**段首 3 个词（129 对 37）和段尾 3 个词（184 对 47）**，段中间反而更少（328 对 379）。按切点规则归类：段尾插入 181 个、段首插入 119 个都落在 **rule1 切点**上（A、B 情况相同）。典型例子：`...future technology | technology needs...`、`...kernel development | development you know...`，也就是切点穿过一个词时，前后两段都把这个词转写了出来。
- 这个问题是 6.4 s 量级 rule1 切点本来就有的，不是 ASR-004 引入的，A 和 B 都有。另外 A 用的是 enc int8asym，基准是 enc FP16，这里面有一小部分编码器差异。
- **要做的**（在 ASR 职责范围内，只做诊断，不改 `live_caption`，ASR-003）：用现有 parts 产物离线分析 rule1 切点处的能量和静音，找出"切在词中间"的比例；给出不改代码就能试的方案（env 参数，比如加大 rule1 的静音要求），或者需要 App 实施的方案（比如段间做 n-gram 去重、或者切点前后保留重叠再去重）。每个方案都要在 61 分钟 A 组产物上做离线去重模拟，给出估计的 WER 收益（reviewer 复核）。排在 P3 INT8 之后做；用户如果另有优先级，以主会话为准。

### 3. ASR-005 P0 参照
| 转写 | WER | S/D/I |
|---|---|---|
| 0.6B 离线（31 × 120 s） | 14.80% | 736/351/536 |
| 0.6B 段级流式 | 10.97% | 450/168/585 |
- **流式口径可以接受**，但要定性为"App 路径等价参照"，不是官方 vLLM 流式。它用的是真实 Segmenter（B 行为），所以能直接和 R2T2 的 App 路径配对：0.6B 流式对 R2T2-B 是 **+0.39pp，CI [−0.33, +1.14]**；对 R2T2-A 是 +0.17pp，CI [−0.60, +0.91]，都**不显著**。
- **§13.6 里"两份参照质量上限大致相同"的说法不成立**：离线对流式是 +3.83pp，CI [+2.94, +4.70]，31 块中有 30 块是离线更差。从误差形态看，离线把错误分散在各处（没有 ≥10 词的大段漏转），像是 120 s 长段的风格化或规整化输出。**P3 请以段级流式为 0.6B 的参照**，离线只作旁证。
- 小瑕疵：0.6B 只跑到 3660.0 s（`--minutes 61`），R2T2 的 A/B 跑到 3665.9 s，最后约 6 s 没跑，影响 ≤0.06pp。P3 请跑整个 wav。`p0_stream_summary.json` 里 `n_runs=1`、`wall_this_run_s=wall_s=2470.1`，但 `rtf_this_run=0.8167` 和 `rtf=0.6749` 对不上，请查明或删掉这个字段（CUDA RTF 不作验收，只是字段要自洽）。

### 4. INT8 候选：现在没有可复核的 WER 或 RTF
§15.3 只有 3 段 teacher-forcing，"top1 100%" 实际只是 3 个 token 的 argmax 一致，不能作为质量证据。enc cos 0.978 低于 R2T2 同口径的数（INT8_SYM 是 0.993，INT8_ASYM 是 0.997）；dec cos 0.962 没有 R2T2 的同口径数可以对比。是否可用，要等 P3 的 61 分钟 WER 来判定。

### 5. INT4"在 0.6B 上不可行"：证据不足，暂不关闭；但也不是只剩 GPTQ 一条路
- "宽度 1024 不够，所以每通道误差翻倍"是推断，没有数据支撑。每通道量化误差主要由输入维的离群值分布决定，不随维度线性变化；而且同宽度（hidden 1024）的 Qwen3-0.6B 文本 LLM 做 INT4 是常规配置。
- 判据本身有问题：只看了 3 个位置的末位 logits cos。连 INT8 fake-quant 也只有 0.978，这已经说明这个指标对这个模型过于敏感，不能单靠它判"崩坏"。
- 需要核实：`p2_fakequant_probe.py` 用的是 `named_parameters + dim()==2`，有没有把 tied 的 embed_tokens/lm_head（以及 audio tower 的 2D 参数）也一起量化了？如果有，fake-quant 那一环证据要作废。
- **要做的**（限时 ≤2 小时，在 P3 INT8 之后做；做不完就如实写，不要拖 INT8）：① 把判据换成**多 token teacher-forcing top1**：≥20 个 ≥12 分钟的评测段，统计全部输出 token，同时用 R2T2 的 R2（AWQ+SE 按通道，WER 10.84%）在同一口径下做标定点；② 在 GPU 上试 `INT4_ASYM g128 + AWQ + SE`（backup INT8_ASYM，lm_head 保持 FP16），跑 5 分钟切片（≥12 分钟区段）的贪心解码看文本是否正常。①② 都确认崩坏，才能写"0.6B INT4 不可行"。只有在 ①② 显示有希望、但按通道版不行时，才考虑 GPTQ。

### 6. P3 放行（INT8）
- 61 分钟全长，走 App 路径（真实 Segmenter，B 行为，**单进程不分 part**，跑整个 wav），这样能和 0.6B 流式参照（552 段）用原版 `paired_bootstrap.py` 逐段配对。产出 GPU 和 NPU 两版 INT8 转写；GPU 版同时给出 enc FP16（或 INT8_ASYM）的变体。
- 对比对象：0.6B 段级流式参照、R2T2 App 路径 B（10.58%）。R2T2 交付基准 8.17% 是 226 段离线切分，和 App 路径不是同一口径，只作参考列。
- 计时：持机器锁（目前锁为空），多次 fresh 进程，记 P50/P95、首字延迟、内存，`timing_valid` 落盘。

**验收**：P3 的转写放到 `qwen3asr_06b/results/p3_*/`，在 STATUS 新开章节写清路径。WER 由 reviewer 复核：0.6B INT8 对 0.6B 流式参照的配对 CI 不显著劣化，就算通过。§2 的诊断结论和 §5 的 INT4 补测写成单独小节。开始处理本条时，先把 last_ack 改成 ASR-006。

## ASR-007 [HIGH] 2026-10-25 09:18 — 【用户决定】Qwen3-ASR-0.6B 只作为实验，不进交付内容；交付一份 R2T2 与 Qwen3-ASR 在不同量化精度和设备上的对比分析报告
用户已经确认：**Qwen3-ASR-0.6B 只是实验，不进 App 和客户包**（交付仍用 R2T2）。ASR-006 的 P3 改成以**出对比报告**为目标：
### 对比矩阵（能做的都做；做不了的格子写明原因，不要硬凑）
| 模型 | 精度 | 设备 |
|---|---|---|
| R2T2（1.7B） | INT8、INT4（已有交付级数据，可以复用并注明来源） | GPU.0、NPU；CUDA Q8/Q4 作参照 |
| Qwen3-ASR-0.6B | FP16、INT8、INT4（INT4 按 ASR-006 的 2 小时限时补测，做不出来就写明"不可用"并附证据） | GPU.0、NPU；CUDA（torch 官方）作参照 |
### 每一格要的指标
- **准确率**：260902_SPE 61 分钟全长 WER，**统一走 App 实时路径的流式口径**（640 ms 分块、自适应 max_new_tokens）。转写交给 reviewer 用本机的 baseline 和全局对齐复算，配对 bootstrap 的 CI 也由 reviewer 算。目标机自己算的 WER 只作参考。
- **延迟**：RTF 的 P50/P95/最大值（逐段统计，至少跑 2 次 fresh 进程，持机器锁，给出范围）；首字和出字延迟（chunk 输入到文字出现）的 P50/P95；模型加载和首次编译的耗时（分有缓存和没有缓存两种情况）。
- **内存**：fresh 进程测量，iGPU 或 NPU 的设备内存加上主机内存（峰值和稳态）；模型文件体积。
- 设备摆放：encoder 和 decoder 分别放在哪个设备上，要写清楚。
### 产出
- 结果 json 统一放到 `qwen3asr_06b\reports\compare`，每一格一份，包含原始字段和 timing_valid；
- STATUS 里写一节汇总表，注明每个数字的来源文件；
- reviewer 会复核 WER，并汇编成 HTML 对比报告（沿用之前 OV 和 CUDA 对比报告的格式）。
- 计时作业一律持共享机器锁，串行执行。准确率作业不需要锁。

## ASR-008 [NORMAL] 2026-10-25 10:38 — RESUME：额度已重置，请从 last_ack 继续
目标机额度已经在 10:00 重置。还没完成的事项，按 §17 的顺序做：
1. **ASR-006 / ASR-007**：修正 0.6B 参照 → P3 INT8（App 路径、单进程、持锁计时）→ INT4 限时 2 小时补测 → rule1 切点重复词诊断数据（交给 App）→ R2T2 和 0.6B 的精度×设备对比报告（结果放到 reports\compare\）。
开始做的时候，请先在 STATUS_ASR 头部写一行"最近更新"。

## ASR-009 [NORMAL] 2026-10-25 15:38 — RESUME：额度已重置，请从 last_ack 继续
目标机额度已经在 15:00 重置。请接着做 ASR-006/007：0.6B INT8（App 路径，持锁）→ INT4 限时补测 → 切点重复诊断（交给 App）→ R2T2 对比 0.6B 报告（reports\compare\）。

## ASR-010 [HIGH] 2026-10-26 09:15 — reviewer 复核：§23 根因成立；mask2 INT8 WER 10.94%（与 torch 参照持平），INT4 11.57%（显著差 0.63pp）；§28 结论需限定配方；ASR-007 还缺 NPU 61 分钟格、计时和内存格，以及交付用 json

先在 STATUS 里写 last_ack: ASR-010，再加一行最近更新，然后按 §4 的顺序执行。

### §1 §23 根因：接受
- 读了 `scripts/p1_export_decoder.py` 和 `p1_export_decoder_mask2.py` 的差异。旧版 `Exportable.forward` 调用的是 `self.tm(inputs_embeds=..., use_cache=False)`，没有传 attention_mask，内容又是右对齐的（前 512-L 位是 padding），所以 padding 位置被当成有效 token 参与注意力。新版自建的 mask 是 `causal & (content | eye)`，作用等同于 HF `_unmask_unattended` 的做法：内容行的可见范围和标准 mask 完全一致，padding 行只放开对角线，用来避开 OV SDPA 遇到整行被屏蔽时输出 NaN 的问题。由于是因果 mask，位置 511 的 logits 和标准 mask 数学等价。这个判断成立。
- 61 分钟的独立验证（reviewer 计算，见 §2）：mask2 INT8 和 torch 流式参照的差值是 Δ −0.04pp，CI [−0.32, +0.25]；552 个块中 471 个块的错误数相同。说明 OV 路径已经忠实复现了 torch 参照，修复在全长音频上成立。
- 受影响、必须标作废的结论（大部分你已经标了，下面这条还没标）：MATRIX 里 `int4_sym_chan__gpu0` 的 "BROKEN"、`int4__all` 的 "INT4_SYM 按通道在 0.6B 上崩坏"，以及"做不了的格子"一节里列出的这两项（NPU BLOCKED、INT4_SYM BROKEN），用的都是旧图，不能再作为结论引用。请把它们移出"做不了的格子"，改成"旧图结论作废、待新图重测"。
- FYI（不阻塞）：R2T2 的 `c069g_export_stage3_fp16.py` 和这里是同一个写法（`forward` 只接收 inputs_embeds，不传 mask）。请用一行写清楚：R2T2 交付或已测的 IR（GPU INT8 / NPU INT8 cleanie）是否由 c069g 派生、是否有左侧 padding。R2T2 的 61 分钟 WER 已经做过端到端验证，所以这里只是确认，不需要重跑。

### §2 reviewer 本机复算的 WER（MiniMax 基线，参考词数 10964，全局对齐）。请原样填进格子，并标 `wer_scorer: reviewer_minimax_global`
| 被测 | WER | S/D/I |
|---|---|---|
| 0.6B mask2 INT8 @GPU.0（iGPU），App 路径，553 段 | **10.94%** | 433/177/589 |
| 0.6B mask2 INT4（ASYM g128 + AWQ + SE）@GPU.0，App 路径 | **11.57%** | 475/209/584 |

配对 bootstrap，重采样 5000 次：
- INT4 − INT8：**+0.63pp，CI [+0.16, +1.10]，显著**（同一切分，553 段，原版 paired_bootstrap）。这和 §27.3 的 teacher-forcing top1 结果方向一致（INT8 99.29% / INT4 92.71%）。
- INT8 − torch 流式参照（10.97%）：−0.04pp，CI [−0.32, +0.25]，不显著；INT4 − torch：+0.59pp，CI [+0.08, +1.12]，显著。
- 对 R2T2 App 路径（ASR-004 B，10.58%）：INT8 +0.36pp，CI [−0.36, +1.07]，不显著；INT4 +0.99pp，CI [+0.30, +1.67]，显著。
- 对交付基准 8.17%（非 App 路径，按 30 秒网格分块）：INT8 +2.76pp，CI [+2.00, +3.53]；INT4 +3.39pp，CI [+2.64, +4.17]。两者路径不同，**公平的对照是 10.58%**，报告里要写清楚这一点。

结论：0.6B INT8 在 App 路径上和 R2T2 INT8 的差别不显著；0.6B INT4 显著更差。§26.2 说"INT4 代价极小"只适用于速度和体积，质量上有 +0.63pp 的代价，请改写。

### §3 §28 "NPU 上 INT4 比 INT8 慢 38.4%"：数字接受，结论要限定范围
- `results/p3_npu_mask2_text_r2/summary.json` 中，两轮 RTF 的差别不到 0.5%（INT4 为 0.3765 和 0.3778），而 INT4 和 INT8 相差 38%，所以方向是可靠的。
- 但是：(a) 被测的配方是 **INT4_ASYM g128**。NPU 原生的 INT4 通路是对称、按通道量化，分组非对称的权重在 NPU 上大概率要额外解压。因此只能写成"INT4_ASYM g128 在 NPU 上比 INT8 慢 38%"，**不能写成"NPU 上 INT4 最慢"**。(b) summary 里没有设备摆放字段：脚本中 `OVRunner(ENC_IR_FP16, dec_ir, args.device)` 把 encoder 也放在 NPU 上，请在 json 里写明 enc 和 dec 各自的设备。summary 里也没有 `timing_valid` 和持锁信息（锁的持有者、PID、开始时间），请补上。(c) 这是整段贪心的口径，不是 App 路径，不能进入 ASR-007 的 RTF 列。

### §4 ASR-007 还缺的格子（精度 INT8/INT4 × 设备 GPU.0/NPU，CUDA 只作参照；FP16 按用户 10-25 21:20 的决定删除，reviewer 接受）
1. **0.6B INT8@NPU 和 INT4@NPU，61 分钟 App 路径**（`p3_ov_app.py --device NPU`，切段器和参数与 §26.2 相同），产出 transcript 和 segments，由 reviewer 算 WER。如果 encoder 上不了 NPU，就写明实际的摆放（例如 enc GPU.0 + dec NPU），不要硬凑。
2. **INT4_SYM 按通道（+AWQ+SE，lm_head 保持 FP16）在 mask2 新图上重测**：先跑 teacher-forcing top1 和 300 秒切片（GPU.0 和 NPU 都跑）。如果 top1 不低于 INT4_ASYM g128 的 92.7%，就把它作为 INT4@NPU 格子的配方再跑一次 61 分钟；否则写明不可行并附证据。
3. **计时和内存**（需要持锁，每次都是 fresh 进程，每格 3 次）：格子包括 0.6B INT8/INT4 × GPU.0/NPU，以及 R2T2 INT8 × GPU.0/NPU（都用 App 路径）。用固定的 600 秒切片 [720, 1320] 来测：
   - RTF：给出每次运行的值，以及 P50/P95（分块重采样）；
   - 首字延迟 P50/P95；出字延迟 P50/P95（段尾到定稿文本输出的时间）；
   - 加载时间和编译时间，冷启动与有缓存各一组；
   - 主机内存：进程峰值的 working set 和 private bytes；
   - 设备内存：GPU USM 的 device/host 两项，NPU 给出可读取的属性。
   - 质量仍然以 61 分钟单次运行为准。§27.4 那种在同一进程里依次编译得到的差值，只能作为近似值，不能填进内存格。
4. R2T2 的 INT8@NPU 也需要一份 61 分钟 App 路径的 transcript（和 0.6B NPU 做同口径对比）。R2T2 INT4 不需要新跑，引用已有数据，并注明口径（非 App 路径、计分器）。
5. **交付文件** `qwen3asr_06b/reports/compare/ASR007_results.json`，每格一条记录，字段包括：model、precision、recipe、enc_device、dec_device、enc_ir、dec_ir、path（app / whole_seg / torch_ref）、transcript、n_segs、wer_pct、wer_scorer、rtf_runs、rtf_p50、rtf_p95、first_tok_p50/p95、final_lat_p50/p95、load_s、compile_s_cold、compile_s_cached、mem_host_peak_mb、mem_device_mb、timing_valid、lock_holder、source_files。MATRIX.md 的 WER 列必须带上计分器列，目标机计分器的 7.952 / 9.795 不能和 reviewer 计分器的数字放在同一列里比较。

验收标准：上面第 1 条和第 4 条的 transcript 落盘，reviewer 复算 WER；第 3 条每格 3 次，timing_valid 为 true，并附持锁证据；ASR007_results.json 字段齐全、可以追溯。做完后在 STATUS 里写一节，交给 reviewer 汇编 HTML 报告。

## ASR-011 [HIGH] 2026-10-26 09:24 — 【用户决定】ASR-007 对比报告按**精简版**做（约 2 小时），不再做全矩阵
用户已确认：Qwen3-ASR-0.6B 只是实验，对比报告用精简版。ASR-010 第④条按下面的范围收缩，**只补这些**：
1. **0.6B INT8 @ NPU**：61 分钟 App 路径转写一份（转写交给 reviewer 复算 WER）。
2. **R2T2 INT8 @ NPU**：61 分钟 App 路径转写一份（同上）。
3. **速度和内存**：每一格只测 **1 次** fresh 进程（不用 3 次），持锁。报告 RTF 中位/P95、出字延迟 P50、有缓存时的加载时间、峰值内存，并写清设备摆放。
4. INT4_SYM 按通道在新图上的重测：**不做了**。报告里写"旧图结论作废，新图没有重测"。
5. 用已有的 mask2 INT8/INT4 @ iGPU 结果，加上上面几格，汇总成 `reports\compare\ASR007_results.json`（每个数字附来源文件），交给 reviewer 汇编 HTML 报告。
ASR-010 的其他条目照旧：把旧图结论从"做不了"清单里移出；补上 §28 的设备摆放、持锁和 timing_valid 字段；用一行确认交付的 R2T2 IR 是不是由 c069g 派生的。

## ASR-012 [NORMAL] 2026-10-26 10:52 — 0.6B INT8@NPU 61分钟 WER 11.05%（对 iGPU +0.12pp 不显著）；§29.4 结论接受但理由要改

### 1. 0.6B INT8@NPU 61 分钟（reviewer 本机复算，请原样回填到格子 wer_pct 和 STATUS）
- 输入：`qwen3asr_06b/results/p3_mask2_61min_int8_npu/segments.json`（553 段），MiniMax baseline（10964 词），`paired_bootstrap.py`（全局对齐，按段配对，5000 次）。
- 段边界核实：和 iGPU INT8 格（`p3_mask2_61min_int8`）**553/553 逐位相同**（start_s/end_s 最大差 0.0 s），文本相同 447/553，词数 11412。§31.2 的说法成立。
- **INT8@NPU WER 11.05%**（1212 个错误）；INT8@iGPU 10.94%（1199 个错误）。
- NPU−iGPU = **+0.12pp，95% CI [−0.05, +0.29]，不显著**（按段比：17 段更好 / 510 段持平 / 26 段更差）。
- 对比 R2T2 App 路径 B（10.58%，两边切段不同，用时间块配对 bootstrap，498 块）：0.6B@NPU − R2T2-B = **+0.47pp，CI [−0.24, +1.17]，不显著**。
- 计时字段已经按 timing_valid=false 作废，这一点正确。

### 2. §29.4（R2T2 交付 IR 和 mask）：结论接受，有两条理由写错了，请改
reviewer 读了代码：`c079b_build_clean_embeds_ir.py` 的 PAIRS = `qwen3-lm-int8sym-lastlogit-ov → qwen3-lm-int8sym-cleanie-ov`（int4 同理）；`c069g` 的 OUT_DIR = `models/ov-dec-embed-fp16`，live_caption/*.py 里没有任何地方引用它。所以"不派生自 c069g"成立。
写错的两处：
- (a) "R2T2 走 cross-attention + 逐 token 解码，每步只喂当前 token 的 embedding，所以没有 padding 概念"——不对。`npu_embeds_backend.py:211-214` 的 prefill 一次喂进 **T 个 prompt token**（音频 embedding + 模板），也就是 decoder-only 的整段 prefill，和 0.6B 是同一种结构；只是之后的 decode 每步喂 1 个 token。
- (b) 全 1 mask 正确的**真实理由**：batch=1、没有任何 padding token，mask 长度刚好等于真实 token 数（prefill 是 T，decode 是 past+1）；IR 保留了 attention_mask 端口（c079b 第 30 行），静态化到 512 的 padding 由 NPUW_LLM 在内部完成，NPUW 会根据传入的 attention_mask 自己生成 mask。0.6B 旧图的问题在于：自己手写把输入 padding 到固定长度 512，而图里**没有 mask 端口**。R2T2 不具备这个条件，所以不存在同样的根因风险。再加上实测证据：全 NPU 61 分钟 7.95% 对 GPU +0.10pp 不显著（c086d）。
- 要你做的：把 §29.4 第 3 点的理由改成 (b)，删掉 "cross-attention / 每步只喂当前 token" 这一句（报告会引用这一段）。不需要重跑。

### 3. 待办
- R2T2 INT8@NPU App 路径 61 分钟（pid25264，10:41 开始，results/p3_r2t2_61min_npu 目前还是空目录）：跑完后把 segments.json 留在原处，WER 由 reviewer 复算（对比 App 路径 R2T2 iGPU B 10.58%）。
- 开始处理某一条纠偏时，先写 last_ack 和一行最近更新。

## ASR-013 [HIGH] 2026-10-26 16:20 — 新功能（用户决定）：接入 pyannote/segmentation-3.0，① 给 ASR 做强制断句 ② 给出说话人 id，供 TTS 切换克隆音色

**优先级**：先把手上的 ASR-007/011 精简版对比报告收尾，再做本条。本条 ASR 线程负责：分段模型的导出和部署、断句策略、说话人 embedding 和在线聚类（身份是从音频侧得出的，归 ASR）。TTS 的音色切换由 TTS 线程做，集成由 App 做。

### 共用约定（ASR/TTS/App 三个模块一致，主会话定）
- 模型：pyannote/segmentation-3.0（HF，MIT 许可，gated 需登录接受条款；只有 pytorch_model.bin，约 1.5M 参数）。输入 16 kHz 单声道 10 s 窗 [1,1,160000]，输出约 589 帧 × 7 类 powerset（≤3 个局部说话人 + 重叠）。可以转 ONNX/OV IR（sherpa-onnx 有现成导出可对照）。转换用的 torch 只在导出环境里，运行时不依赖 torch。
- 它只做**窗内**说话人分段（哪一帧有人说话、窗内是 1/2/3 号谁在说、有没有重叠），**不给跨窗的身份**。跨时间认出"同一个人"，要另外用说话人 embedding 做在线聚类。主会话的建议：**直接复用 Qwen3-TTS Base 自带的 speaker encoder 提的 x-vector**（就是 spkonly 用的那个），同一个向量既当身份、又当克隆音色，不再引入第三个模型。如果它区分说话人的能力不够，再评估 wespeaker-resnet34 / CAMPPlus。
- 设备：iGPU 或 NPU，**不在 CPU 上跑**（CPU 只能做单组件对拍诊断）。NPU 用静态 10 s 窗形状；如果 LSTM 在 NPU 上编译不过，就放 GPU.0。注意 TTS 现在全部在 NPU 上，要实测争用。
- 事件字段：ASR 的定稿段增加 `spk`（全局说话人 id，S1、S2…；身份还没定下来时为 null）以及 `spk_conf`。App 把它原样传给 MT 和 TTS 事件；MT 不需要改翻译逻辑。
- 隐私：克隆当前说话人仍然是**可选项，默认用预设音色 A**。说话人的 x-vector 只存在内存里，会话结束就丢弃，不落盘、不进客户包。测试素材里的会议录音和克隆音色仍然只限内部使用。

### 要做的事
1. 导出 segmentation-3.0 → OV IR（FP16；再试 INT8），和 torch 输出逐帧对拍（powerset logits cos ≥ 0.999，帧级类别一致率 ≥ 99%）。分别在 GPU.0 和 NPU 上测单窗耗时和内存。
2. 流式断句：用 10 s 窗滑动，步长和 640 ms 分块对齐（或者 1.28 s），把重叠的部分聚合成帧级的"有人说话 / 说话人变化"概率。断点规则：(a) 静音 ≥ X ms；(b) 局部说话人切换，并且稳定 ≥ N 帧；(c) 最长段兜底。**断点只能落在静音或说话人切换处，不能切在词中间**（这正是 App 路径 WER 10.58% 对 8.17% 的主因）。X、N、判决滞后要扫参，并报告判决滞后给定稿带来的额外延迟。
3. 说话人身份：对定稿段里单人、无重叠、≥ 2 s 的语音提 x-vector，做在线聚类（余弦阈值 + 均值逐步更新 + 说话人数上限），给每段输出 spk 和 spk_conf。
4. 参照：在 CUDA 上**离线**跑 pyannote/speaker-diarization-3.1，结果当作伪真值（只用来评估，不进交付）。

### 验收
- ① WER：61 分钟 SPE 会议走 App 路径，和现在的 10.58%（R2T2 iGPU INT8）做配对 bootstrap，reviewer 复算。同时报告断点落在词内的比例，和现在的约 1.6× 对比。
- ② 延迟和性能：定稿延迟 P50/P95 的增量；ASR RTF 的增量；和 TTS 同时跑在 NPU 上时的争用（计时要持机器锁）。
- ③ 说话人：对照 3.1 伪真值，报告说话人切换点的 F1（±0.5 s 容差）、段级说话人纯度、全局 id 的混淆和碎片化（一个人被拆成多个 id 的次数）。
- 产物放在 results/pyannote_seg/，结果写进 STATUS 新章节。开始时先写 last_ack 和一行最近更新。
