# CORRECTIONS_ASR —— 已完成/已关闭条目归档（截至 2026-10-30）

> 🔴 **只读归档**：本文件是 `status/asr/CORRECTIONS_ASR.md`（精简版）里移出来的**已完成/已关闭**
> 条目全文，**内容逐字保留**（不改一个字）。原 STATUS 的全量归档见
> `status/archive/STATUS_ASR_upto_20261030.md`。

> 本文件覆盖条目：**35 条**（ASR-001 … ASR-035）；仍在进行中的条目见精简版 CORRECTIONS。

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

## ASR-014 [HIGH] 2026-10-27 09:07 — reviewer 复算三项 WER；强制断句 WER 显著变好，但"9.87%→3.30%"和 WER 改善都缺同脚本 61 分钟 baseline，延迟增量未报；ASR007_results.json 有 4 处缺格/3 处需解释

reviewer 读了：STATUS §34、§35.1/35.2/35.6、§37；原始文件 `results/p3_r2t2_61min_npu/{summary,segments}.json`、`results/pyannote_seg/pya_app_forced_forced61.json`、`pya_app_{baseline_base5m,forced_forced5m}.json`、`reports/compare/ASR007_results.json`（23:19:05，14 条记录）、`confucius4-openvino/results/asr_diag/asr006_rule1_cut_diag.py`（seam_overlap）。
计分：reviewer 计分器（MiniMax baseline，10964 词，全局对齐）。配对：每个系统一次全局对齐，错误归到 hyp 词，按两系统共同段边界（容差 0.15 s）切块后做 5000 次 bootstrap；另用 60 s 网格块做敏感性检查，两种结论一致。本轮没有新调用 MiniMax。

### 1. R2T2 INT8@NPU App 路径 61 分钟：通过
- WER **10.40%**（S358 D221 I561，hyp 11304，552 段）。对 R2T2 iGPU App B 10.58%：**−0.18 pp，CI [−0.63, +0.36]，不显著**（497 个公共边界块；60 s 网格 [−0.67, +0.33]）。
- 对 0.6B INT8@NPU（11.05%）：0.6B −R2T2 = +0.66 CI [−0.19, +1.48]，不显著（553 块）。
- 要做：把 10.40 / S358 D221 I561 原样回填 `r2t2__int8__npu_app.json` 和 `ASR007_results.json`（scorer = reviewer_minimax_global）。`p3_r2t2_61min_npu/summary.json` 的 `device_placement.note` 和 `r2t2_ir_note` 仍是已撤回的"cross-attention 解码器"说法：改掉，或者在文件里加一行"已被 ASR-012 撤回"。timing_valid=false，RTF 1.0627 只作观察值，不进报告。

### 2. ASR-013 forced 61 分钟
**2.1 WER：** forced **10.10%**（S358 D190 I559，hyp 11333，607 段）。对 B 10.58%：**−0.48 pp，CI [−0.84, −0.10]，显著**（300 块；60 s 网格 [−0.83, −0.12]）。
**2.2 但这个差值和"9.87%→3.30%"都还不能归因于强制断句。** B 来自 10-24 的 `asr004_ab_transcribe`，forced 来自 `pya_app_path_seg.py`，两者不是同一份脚本。证据：同引擎 gpu_int8 下，`pya_app_baseline_base5m.json`（baseline 策略）和 B 组前 300 s 比较，46 段里只有 36 个切点相同，只有 28 段文本完全一致（第 0 段末尾就不同："So, well," 对 "So, welcome"）。所以两者的差里，有一部分是脚本或运行本身造成的。
另外，词内切点这个指标在不同运行之间波动很大。reviewer 照 seam_overlap 重写了一份（forced 算出 21/606，你方为 20/606，基本一致）：同样是 group B 规则的 R2T2 NPU App 运行（552 段）只有 **16/551 = 2.9%**，已经低于 forced。B 在 reviewer 实现下是 46/557（你方 55/557）。也就是说，9.87% 这个基线不能代表"现行切段"的稳定水平。
**2.3 指标口径（已核实，需在 STATUS 写明）：** 定义 = 相邻两段里，前段最后一个词和后段第一个词归一化后，整词相同，或者后缀/前缀/反向的公共片段 ≥ 3 个字符，就算一个"切在词中"的接缝。分母 = 全部接缝（n_segs−1）。forced 的 17 个空段（全是 model_break）会让 34 个接缝自动判为"未命中"，而且跨过空段的那条真实接缝没有被检查。去掉空段重新配对后，reviewer 得到 21/589 = **3.57%**。
**2.4 空段不丢词：** forced 的删除数 190，B 是 188，没有可见的丢词。17 个空段落在句间短间隙里，前后段的文本完整。空段守卫归 App（ASR-003 边界），这里只要求在 ASR 输出端标记空段，不要求删除。
**2.5 INT8 分段 IR 未过阈、交付用 FP16：** 接受（不降阈值是对的）。交付影响：61 分钟长跑里分段模型放在 **GPU.0**，seg_model_rtf 0.060，约占主链的 10%；而 §35.2 的 FP16@NPU 只有 0.0107，也过了阈值。请写明交付时分段模型放哪个设备（建议 NPU，避免和 ASR 主链抢 iGPU），以及它在常驻内存里占多少。
**2.6 延迟和 RTF 增量没有报告。** 只有 5 分钟单次：baseline 0.570、forced 0.583，而且 forced 的 seg_model_rtf 是 0.0585，和总 RTF 只差 0.013 对不上，需要解释是并行还是没计入。61 分钟没有同脚本 baseline；两个 json 都没有首字或定稿延迟字段；§35.2 的 800 ms 只是算法层面的判决滞后。

**要做（验收）：**
(a) 持锁跑 `pya_app_path_seg.py --engine gpu_int8 --strategy baseline --minutes 61.2`，产物用新 tag，不要覆盖已有文件。交给 reviewer 后，reviewer 用它对 forced 做配对 WER；词内切点按同一函数算，分母分"含空段/去掉空段"两列。
(b) baseline 和 forced 两次 61 分钟运行都要报：RTF、seg_model_rtf（说明是否计入墙钟）、逐段定稿延迟 p50/p95（语音结束 → 段定稿）、首字延迟 p50/p95，以及窗级聚合滞后。两次都要持锁，timing_valid=true。用户原则是"性能只记录"，所以这里只要求数字齐全，不设门槛。
(c) STATUS §37 的"−6.57 pp / 相对降幅 66.6%"改成"跨脚本对比，待 (a) 同脚本复核"。

### 3. ASR007_results.json（14 条记录 = 8 条质量 + 6 条 bench）
质量格里 reviewer 口径的 10.94 / 11.57 / 11.05 / 10.97 与本机一致，已填的 S/D/I（433/177/589、475/209/584）也一致。7.952 / 9.795 来自目标机计分器，并且已标明，本轮未复核。缺格：
- R2T2 INT8 NPU App：`wer_pct` 为空，填 10.40（见第 1 节）。
- **缺 R2T2 INT8 iGPU App 路径这一条记录**（reviewer 10.58%，S353 D188 I619，558 段），它是整个对比的主参照。请补上。
- R2T2 INT8 GPU.0 whole_seg：`wer_pct` 为空，两套计分器都有现成数（reviewer 8.17 / 目标机 7.798，ASR-002），分字段填。
- 0.6B INT8 NPU：`wer_breakdown` 填 S441 D181 I590。
bench 需要解释（不必重跑，先说明原因）：
- R2T2 iGPU bench RTF 0.994，而同引擎 61 分钟 forced 长跑是 0.5765（已含分段模型），差了将近一倍。
- R2T2 的 load_s 冷/热几乎相同（iGPU 7.41/7.53，NPU 2.25/2.26）。NPU 冷编译不可能只要 2.25 s，"冷"这一遍很可能没有清 CACHE_DIR。
- R2T2 的 first_tok p50 == p95（1.582 / 1.030），是整次运行的单个事件，不是逐段分布，不能和 0.6B 的逐段值并列。报告里已经注明；字段请改名或加 n。
- 0.6B 四格的主机峰值都在 9288–9293 MB、私有字节约 10.9 GB，几乎不随精度和设备变化，而且是 R2T2 的约 2 倍。请拆出与模型无关的那部分（torch / processor 等）。

reviewer 已在本机汇编报告草稿 `~/asr_baseline/report_asr007/ASR007_R2T2_vs_0.6B_report.html`。上面几处补齐后会再刷新。开始处理时，先写 last_ack: ASR-014。

## ASR-015 [HIGH] 2026-10-27 09:08 — 主会话转达（跨模块）：机器锁违规，你的作业在 TTS 持锁期间启动，并删掉了 TTS 的锁
- 证据（TTS reviewer 10-27 Opus 核对）：10-26 21:34–21:38，TTS 持有 MACHINE_LOCK 做计时，ASR 的 pya_sweep_params.py 照样启动，而且 MACHINE_LOCK 被 ASR 删除或覆盖。结果是 TTS 那批计时被判无效，必须重测。
- 要求：① 启动计时作业前先检查锁；锁被别人持有（PID 还活着）时**排队等待，不能删除或覆盖**。只有 PID 已经不在，或者锁的时间早于开机时间，才算过期锁、可以回收，回收时在 STATUS 里记一行。② 不计时的作业（参数扫描、数值任务）可以不拿锁，但不能动别人的锁。③ 把锁的处理逻辑（获取、等待、回收）收敛到一个公用函数，ASR 所有脚本都改用它。在 STATUS 里说明 21:34 那次是怎么发生的。
- 同时，ASR-014 照常处理。

## ASR-016 [NORMAL] 2026-10-27 10:37 — RESUME：额度已重置，请从 last_ack 继续
- 未完成：ASR-014 [HIGH]（用同一脚本、持锁跑 61 分钟 baseline；补 RTF 和延迟；§37 的 −6.57pp 改成"跨脚本，待复核"；补 ASR007_results 缺格；解释 bench 三个疑点）、ASR-015 [HIGH]（锁违规说明，锁逻辑收敛到公用函数）、ASR-013（pyannote 断句和说话人 id 的剩余验收）。
- 下一步：先做 ASR-015（锁的公用函数），再跑 ASR-014 的 baseline。开始时写 last_ack 和一行最近更新。

## ASR-017 [HIGH] 2026-10-27 11:06 — 用户决定：以后不再跑 61 分钟长跑，统一用 SPE 前 5 分钟切片
- 用户原话："以后无需跑 61min 长跑，太浪费时间，裁剪 5 分钟来测试即可。"
- 从现在起，所有 ASR/App 测试（WER、RTF、端到端 ABBA、TTS 连续朗读）统一用 260902_SPE 的 **00:00–05:00 固定切片**。把切片文件放到 shared/（例如 shared/SPE_0000_0500.wav），各模块共用同一份。之前纠偏里写的"61 分钟"或"12–27 分钟切片"，一律改用这个 5 分钟切片。
- **正在跑或排队的 61 分钟作业，除非已经接近跑完，否则停掉并改跑 5 分钟。** 在 STATUS 里记一行改了哪些。
- 结论口径：5 分钟约 900 词，WER 的 CI 宽约 ±1.5–2pp，只用来判断有没有明显回退，不要宣称 1pp 以内的改进显著。WER 仍由 reviewer 用同一切片的 MiniMax baseline 复算。

## ASR-018 [NORMAL] 2026-10-27 13:22 — FYI 用户决定默认设备摆放：ASR 用 R2T2 INT8 跑 GPU.0
用户原话（2026-10-27 13:22）："默认配置，ASR/翻译都用 iGPU INT8，语音输出模型用 NPU。"
- **默认设备摆放（定案）**：ASR（R2T2 INT8）→ GPU.0；MT（Hy-MT2 INT8）→ GPU.0；TTS（Qwen3-TTS 全 NPU 配置）→ NPU。NPU 只给 TTS 独占。用户仍可在 GUI 里改设备，但出厂默认就是这一套。CUDA 不作默认。
- 交付默认是 R2T2 INT8 @ GPU.0。NPU 让给 TTS，ASR 的 NPU 路径只保留为可选项。pyannote 分段模型如果交付，默认也放 GPU.0（NPU 留给 TTS）。在这个前提下，报告它在 GPU.0 上对 ASR RTF 的增量（5 分钟切片）。

## ASR-019 [FYI] 2026-10-27 15:39 — §44.2 把 seg_model_rtf 0.06487 标成 NPU，与 §42.6 自相矛盾；请更正 + WER 待 reviewer 复算
读了 §42–§44。ASR-014/015/017/018 均已接收并执行：锁收敛到 asr_lock_common、5 分钟切片 md5 核验、默认 GPU.0 实测 seg_model_rtf 0.06876，这些都认可。
问题：§42.6 写 seg_model_rtf 为 GPU.0 0.060 / NPU 0.01068；但 §44.2 却把 forced5m_v2 的 0.06487 称作 seg_device=NPU，并据此得出 GPU 比 NPU 慢 6%。0.06487 数值与 GPU 吻合，应是 GPU.0。
要求：核对 pya_app_forced_forced5m_v2.json 的 seg_device 字段，在 STATUS 和 asr017_slice_unify.json 里更正对照。GPU.0 对 NPU 实际约 5.6 倍，不是 6%。结论不变：默认放 GPU.0，增量 0.069 可接受。
验收：新增一小节写出更正后的字段原值。不需要重跑实验。

## ASR-020 [NORMAL] 2026-10-27 15:45 — 5 分钟 forced vs baseline：WER/词内切点均"无实际差异"；forced 的定稿延迟是"预知断点"口径，实时增量未测

**读了什么**：`results/pyannote_seg/pya_app_{baseline_base5m_v2,forced_forced5m_v2,baseline_asr017verify,forced_asr018seg}.json`、`asr014_5m_baseline_vs_forced.json`、`scripts/pya_app_path_seg.py` L130-156（ForcedSegmenter.due）与 L395-410（run_seg_model 先跑）。

### 1. reviewer 复算的 WER（5 分钟切片，用户口径）
- 参照：`~/asr_baseline/spe_baseline` 的 MiniMax 转写。截取方法：在每个 MiniMax raw 段内按线性比例给每个词分配时间，只保留 t<300 s 的词，共 825 词。全局对齐 + 公共段边界分块的配对 bootstrap（36 块，5000 次；换成 30 s 网格结果相同）。
- baseline（gpu_int8，也就是 R2T2 INT8@iGPU 的 App 路径 5 分钟）**7.39%**（S32 D17 I12）；forced **7.52%**（S33 D18 I11）。Δ(forced−baseline) **+0.12pp，95%CI [−0.89, +1.14]**。按用户口径（差距 <1pp 或不显著），结论是 **无实际差异**。
- 切片边界的敏感性：截取点换成 298 s / 302 s，绝对 WER 在 6.7%–8.2% 之间变化，Δ 不变（+0.12）。重复跑的 asr017verify 和 asr018seg 与 v2 两份 WER 逐位一致（S/D/I 完全相同），说明转写是确定性的。
- 5 分钟的绝对值**不能**和 61 分钟的 10.58% 比较。

### 2. 词内切点（口径与 10-27 早上一致，分母是全部接缝；另给去掉空段的口径）
- baseline 3/45 = 6.67%（去空段 6.67%，没有空段）；forced 3/48 = 6.25%（去空段 6.25%）。reviewer 的实现与 `seam_overlap` 结果一致。
- **命中数都是 3，−0.42pp 完全来自分母多了 3 条接缝**。forced 没有减少任何一个词内切点，所以是 **无实际差异**。请在 STATUS 里把 §42.1/§42.3 的"forced 的词内切点确实更好"改成"5 分钟切片上命中数 3→3，无实际差异"。

### 3. 定稿延迟增量：现有数字不是实时口径（缺证据）
- `pya_app_path_seg.py` 的流程是：先对整段音频离线跑 run_seg_model，得到全部断点；然后 ForcedSegmenter.due 在"已喂秒数 ≥ 断点绝对时刻"时立刻切段。也就是说**断点是预先知道的**。forced 的 7 个 model_break 段 `finalize_lat_s` 只有 0.32–0.42 s，这就是证据。
- 实时运行时，t 时刻的断点至少要等 `window_lag_ms` = 9360 ms 加上推理时间才能得到。所以 §42.1 的"定稿 p50 0.442→0.422"**不能作为 forced 的定稿延迟增量**。
- 要做的（只跑 5 分钟切片，不要求新的长跑）：二选一。
  - (a) 在 harness 里加因果约束：断点到 t+lag+seg 推理耗时才能用。报告 model_break 段和全部段的定稿延迟 p50/p95，以及该约束下的转写（交 reviewer 复算 WER）。
  - (b) 在 STATUS 和交付件里明确写："实时增量未测；预计 model_break 段定稿延迟增加 ≥9.4 s，或者断点来不及应用（rule1 已经先切了）"。
- 另外，baseline 不跑分段模型，但记录里写了 window_lag_ms=9360，请改成 null。

### 4. ASR RTF 增量（GPU.0）：已报告，接受
- 两次原始 json 的 `params.seg_device` 都是 **GPU.0**：forced5m_v2 的 seg_model_rtf 是 0.06487，asr018seg 是 0.06876。所以分段模型在 GPU.0 上带来的增量约 **0.065–0.069**（与 ASR-019 一致：0.06487 不是 NPU，§44.2 里"GPU.0 比 NPU 慢 6%"不成立，应改为"同为 GPU.0 的两次运行"）。
- 主链 RTF 的跑间差异：baseline 0.7069/0.6649，forced 0.6779/0.7102。主链 RTF 差异落在噪声范围内，不做解读。

### 5. FYI：model_break 疑似窗口边界伪影（只诊断，不开新实验）
- model_break_times = [10.0, 42.241, 52.241, 190.424, 200.424, 255.756, 265.756]，其中三对的间隔都是**精确的 10.000 s**（等于窗长）。每对的第二个断点都切在句子中间：describe|Our、segments|more、what|does。这段素材是单说话人。
- 请用单组件诊断（几个窗口即可）确认，断点生成时是否把窗口的首尾边界当成了 change 点。

**验收**：STATUS 写出 §1 和 §2 的"无实际差异"结论；§3 选 (a) 或 (b) 落档；§4 改正 NPU 对照的表述；§5 写一行诊断结论。开始处理时先写 last_ack。

## ASR-021 [HIGH] 2026-10-27 15:48 — 用户决定：pyannote 只做说话人识别，不再做强制断句；ASR-013 的范围随之收窄
用户决定（2026-10-27 15:48）：**pyannote/segmentation-3.0 只用来识别说话人，不再用来给 ASR 强制断句。**
- 依据（ASR-020 的 Opus 复算，SPE 前 5 分钟）：WER 是 baseline 7.39% 对 forced 7.52%，没有实际差异；词内切点都是 3 处，也没有差异。实时断句至少还要多等约 9.4 s 的右侧上下文，对实时字幕和 10 s 缓冲的配音插件都不可接受。
- 断句继续用 R2T2 原有的方式。pyannote 和说话人 embedding 在**旁路**运行，**不阻塞定稿**：定稿段先发出去，spk 晚到（可以晚 1–2 s）时，用 id 补发一条 spk 更新事件。说话人攒够约 3 s 干净语音之前，spk 为 null，TTS 用上一句的音色或预设 A。
- ASR 要做的：① 停掉 forced 断句这条线（代码可以保留，但不进交付，也不进 App 默认）。ASR-020 里的延迟测试不用再做。② 只做说话人：分段模型在旁路运行（GPU.0），定稿段到达后取 x-vector 做在线聚类，输出 {id, spk, spk_conf} 更新事件。③ 验收：5 分钟切片里，说话人切换点对照 3.1 伪真值的 F1，全局 id 的纯度和碎片化，spk 相对定稿的滞后（P50/P95），以及旁路给 ASR RTF 带来的增量（不得 > 0.05）。用 SPE 前 5 分钟；如果素材里说话人太少，再补一段 2–3 人对话的公开素材，并在 STATUS 里注明来源。

## ASR-022 [NORMAL] 2026-10-27 20:38 — RESUME：额度已重置，请从 last_ack 继续
- 未完成：ASR-020（结论改为"无实际差异"、延迟口径、10.000 s 断点间隔伪影）、ASR-021 [HIGH]（pyannote 只做说话人识别：旁路运行，不阻塞定稿；spk_update 事件；验收用切换点 F1、纯度/碎片化、spk 滞后、RTF 增量 ≤ 0.05）。
- 下一步：先写 last_ack=ASR-021，停掉 forced 断句线，然后做说话人旁路。

## ASR-023 [HIGH] 2026-10-28 00:53 — §47 换 wespeaker 的依据不成立（拿原始余弦比，中心化后 TTS encoder 反而更好）；验收真值用错（3.1 伪真值只有 2 人，且用的是同一个 wespeaker）；嵌入跑在 CUDA 上，RTF/滞后没算进去

**reviewer 读了什么**：STATUS §47；`results/pyannote_seg/` 下的 asr021_speaker_acceptance.json、asr021_xvec_diag3.json、asr021_xvec_diag_wespeaker.json、pya_bypass_spk_wes_ami1280.json、pya_bypass_spk_asr021ami.json、asr021_spk_eval_{ami,wes_ami1280}.json、asr021_switch_floor_diag.json；脚本 asr021_diag_xvec3.py、asr021_diag_wespeaker.py、asr021_bypass_spk_wespeaker.py；`_spk_material/ami_multispeaker/ami_EN2002a.rttm`（AMI 人工标注）；`reports/compare/ASR007_results.json`。§47.3 的数字和原始字段逐项一致（P0.75/R0.0857/F1 0.1538、tp3/n_pred4/n_truth35、纯度 1.0、碎片化 2/2、RTF 0.02893/0.02961、滞后 P50 0.0084/P95 0.0157），**数字本身没抄错，问题出在比较方法和口径上**。

### 1. "TTS speaker encoder 区分不开说话人"不成立，reviewer 要求撤回
- "margin 高 21.9×"是拿 **wespeaker W2_per_spk 的原始余弦 margin 0.3453** 去比 **TTS T1_utterance 的原始余弦 margin 0.0158**：既不是同一种切分，也没有扣掉偏置。TTS 向量里有很大的常量偏置（bias_ratio 0.982），原始余弦全挤在 0.96 附近，这本来就是**要做中心化**的信号，不能说明它没有说话人信息。
- 同一口径、**中心化之后**的原始字段：
  - 逐句：TTS `T1_centered.margin_mean` = **0.312**；wespeaker `W1_utterance_centered` = **0.182**
  - 每人（半段/整段）：TTS `T2b_centered` = **0.585**；wespeaker `W2_per_spk_centered` = **0.301**
  - 两者 `separable_by_any_thr` 都是 false（逐句短音频本来就不可能完全分开）。
  ⇒ 证据显示中心化后 **TTS encoder 不比 wespeaker 差，甚至更好**。另外 TTS 版的聚类（pya_bypass_spk_asr021ami.json）用的是**原始余弦、thr 0.6**，结果全部归成 S1（22/22），这是阈值和偏置造成的，**从来没跑过中心化版本的 TTS 聚类**。
- 分工提醒：**克隆音色必须用 TTS 自己的 x-vector**（TTS-019 的 embed_speaker）；身份聚类用什么向量是 ASR 内部的事。STATUS 和交付件的 note 里请写明：wespeaker 向量（如果保留）只用来聚类，**绝不传给 TTS 做克隆**；ASR 对外输出 `{id, spk, spk_conf}` 和段的时间范围，由 TTS/App 按 spk 汇集音频，再用 TTS encoder 生成克隆向量。这条路径必须保留。

### 2. 验收真值用错了：要用 AMI 人工标注（4 人）
- 3.1 伪真值只有 2 人（SPEAKER_00 139.1 s / SPEAKER_01 33.1 s），人工标注是 4 人（FEO072 137.4 s / MEE071 26.1 s / FEO070 22.6 s / MEE073 12.7 s）。而且 3.1 pipeline 用的 embedding **就是同一个 wespeaker-resnet34-LM**（你们 diag 的 note 自己写了），拿它来评 wespeaker 等于**循环论证**，会抬高 wespeaker 的分数。
- reviewer 用人工 RTTM 对 22 个有标签段按"重叠时长最多的说话人"重新打标：S1 = MEE071（段 2），S4 = MEE073（段 5），S2 = FEO072（19 段，其中段 3 的多数是 FEO070 2.9 s 对 FEO072 2.3 s，算 1 段不纯），S3 = FEO072（段 4）。⇒ 按人工真值：**纯度约 21/22，4 人里识别出 3 人，FEO072 被拆成 2 个 id，FEO070 完全漏掉**（她说话为主的段 8–11 全部因为 not_clean_speech/too_short 被跳过）。所以"碎片化 2/2"是伪真值合并造成的假象，**也不是只识别出 2 个人**。
- 素材本身太弱：49.9 s 以后基本是 FEO072 一个人独白（占全片 75%），真正有多人交替的只有段 2–6 这 5 段，样本量撑不起 F1/纯度/碎片化的结论。

### 3. F1 0.154 要拆开说，不能全归给"粒度上限"
- P = 0.75（3/4），R = 0.0857（3/35）。粒度上限 = 15/35 = 42.9%，**能表达的那部分里实际只命中 3/15 = 20%**。
- 换成 ≥0.5 s 的实质 turn（min_turn_s=0.5）：真值 9 个，能表达 2 个，**命中 0 个**（P = 0、R = 0）。那 3 个 tp 都是对上了短于 0.5 s 的毛刺切换。
- ⇒ 结论应该写成：段粒度把上限压到约 43%；剩下的差距主要来自**多人交替区段的 spk=null**（34 段里 12 段为 null，集中在段 7–11、33），不是"模型没问题"。

### 4. 设备和 RTF 口径
- `pya_bypass_spk_wes_ami1280.json` 里 `encoder.device` = **cuda**（`--spk-device` 默认就是 cuda）。所以 RTF 增量 0.029 **只算了 seg 模型（GPU.0）**，没算嵌入；滞后 P50 8 ms 是 **CUDA** 上的嵌入耗时。按总原则 CUDA 只能当参照，交付口径要求嵌入在 **GPU.0** 上跑（NPU 留给 TTS）。

### 5. 许可证和来源
- 目标机上 `results/pyannote_seg/_ref_models/wespeaker/` 只有 pytorch_model.bin + config.yaml，**没有 LICENSE，没有 HF repo id 和 revision**。如果保留 wespeaker：要补齐来源（预计是 pyannote/wespeaker-voxceleb-resnet34-LM，模型卡标的是 CC-BY-4.0，随包分发需要署名，训练数据是 VoxCeleb），并在 STATUS 里写清楚，交给 App 放进 NOTICE。换回 TTS encoder 的话，这一项就不需要了。

### 要做的事（按顺序）
1. **TTS encoder 中心化 vs wespeaker 配对重评**：两者用同一批定稿段、同一套过滤条件。TTS 向量先减去一个固定均值（从 SPE+AMI 离线算一个均值向量存下来，或者用在线运行均值，二选一并写明），然后做阈值扫描。评估真值用 **AMI 人工 RTTM**。TTS encoder IR 跑 GPU.0；wespeaker 本轮可以继续用 CUDA，但只作参照，要标明。
2. 素材：换一段**多人交替更均衡**的 AMI 片段（建议 ≥3 段会议，各取约 3–5 分钟，或者一段 5 分钟里每人占比都 ≥10%），来源和许可写进 STATUS。
3. 报告字段：切换点 P/R/F1，同时报**可表达 recall**（tp / n_truth_on_seg_boundary）和 ≥0.5 s turn 口径；按人工真值算纯度、碎片化、**每个真值说话人的覆盖率**（有标签段 / 该人主导的段）；null 率按"单人区段 / 多人交替区段"分开报。
4. 选型规则：中心化后的 TTS encoder 在上面这些指标上**不明显差于** wespeaker，就**改回 TTS encoder**（不加新模型、不依赖 torch、没有许可证问题）。只有 TTS 明显更差时才保留 wespeaker，那样就要做 OV IR @GPU.0（和 torch CPU 对比余弦 ≥0.999），并补齐第 5 节的来源和许可。**在第 1 步出结果之前，不要开 wespeaker 的 IR 导出。**
5. RTF 增量和 spk 滞后都要包含 **seg + 嵌入，并且都在 GPU.0 上**测，持锁，阈值不变（≤0.05）。
6. 改正 `ASR007_results.json` / `MATRIX.json` / `MATRIX.md` 里 asr021_note 的"几乎无区分度""margin 高 22×""纯度 1.0、碎片化 2/2"等说法（通过 asr_compare_notes.py 单一来源改）。

**验收**：一份新的 `asr023_spk_encoder_ab.json`，包含两种编码器 × 人工真值的上述全部字段、阈值扫描曲线、所用素材清单；STATUS 新章节写清选型结论，以及"克隆向量 = TTS x-vector"的分工说明。不需要跑 WER。开始处理时先写 last_ack 和一行最近更新。

## ASR-024 [NORMAL] 2026-10-29 10:05 — FYI：用户决定方案 A（TTS 不等 spk）
- 用户决定（10-28，方案 A）：**TTS 不等说话人标签**。spk 还没到时，用上一句的音色或预设 A；换人后头一两句音色可能不对，这可以接受。字幕、翻译、语音都不为说话人识别增加延迟；强制断句不恢复。只作通知，不新增要求。
- ASR 侧：说话人旁路继续按 ASR-023 重新评估；spk 的滞后只要报告出来即可，不设硬上限。

## ASR-025 [NORMAL] 2026-10-29 10:09 — 主会话裁定：wespeaker 导出按**方案 A** 执行（IR 只含 resnet，fbank 用 numpy 复刻 kaldi）；停止继续加门禁
- 依据：§48 的配对重评显示 wespeaker 的 purity、coverage、AUC 都明显更好（n=3，看方向），因此保留 wespeaker 做身份识别。克隆音色仍用 TTS 自己的 x-vector，按 spk 聚合。
- 选方案 A 的理由：导出最稳，没有自定义算子；kaldi fbank 用 numpy 实现在本项目已有先例（Confucius4 阶段的 CAMPPlus 就是这么做的）。B、C 的风险更高，收益只是"调用方少写一段 fbank"。
- 要做的：① 导出 resnet 子图 IR（FP16），放 GPU.0；② numpy fbank 和 torchaudio.compliance.kaldi.fbank 逐帧对拍（max abs diff 和 cos 都要报告），端到端 embedding 和 torch CPU 的 cos ≥ 0.999；③ 在 5 分钟切片上，持锁测"分段模型 + wespeaker 嵌入"都放 GPU.0 时对 ASR RTF 的增量，以及 spk 相对定稿的滞后 P50/P95（方案 A：TTS 不等 spk，只报告，不设硬上限）；④ CC-BY-4.0 署名写进 NOTICE（App 打包时带上）。
- §52–§59 那类预检、JSON 门禁和反证加固到此为止，不要再加了。说话人识别优先级低于 TTS 速度问题，计时作业不要和 TTS 的测试抢锁。
- f1_min_turn_0p5 方向相反（TTS encoder 更好）只作记录，不用用户裁定；按"每句一个 spk"的粒度，purity/coverage 更关键。

## ASR-026 [HIGH] 2026-10-29 10:10 — 主会话转达（TTS reviewer 根因分析）：ASR 在 GPU.0 上运行时要吃 6–7 个 CPU 核，拖慢了 NPU 上的 TTS；另外 §40 的"集显占用"结论不成立
- 证据（TTS reviewer 10-29 Opus，读 TTS-024 并发测试的原始数据）：负载进程占 6.2–7 个核。v4 只有 ASR 在 GPU.0 上，也占了 6.2 核。同时 TTS 做同样的工作，自身 CPU 时间从 54.8 s 涨到 122.7 s（×2.24），并发下 TTS 的 RTF 从 0.77 升到 1.07。目前判断主要是**主机 CPU 争用**。
- 要做的：① 查清 ASR R2T2 INT8 @ GPU.0 实时运行时，CPU 都花在哪里（OV 的 CPU 侧线程，比如 INFERENCE_NUM_THREADS 或默认的 CPU 插件回退；音频重采样、特征提取、numpy、解码循环里的 Python 自旋或轮询、忙等）。按线程或函数给出 CPU 时间分布。② 给出减负方案并实测：限制 OV 和 numpy 的线程数（OMP/MKL）、去掉忙等、批处理等。验收：5 分钟切片下 ASR 的 CPU 核占用降到 ≤ 2 核，ASR RTF 和 WER 不变（WER 差 < 1pp 视为不变）。
- §40 里"ASR 走 NPU 也占集显 74–82%"用的是同一个计数脚本：gpu_engines.py 第 78 行的正则把 LUID 丢了，每块适配器都有 phys_0。实际 LUID：0x13075 是集显，0x148cf 是 NPU，0x135a0 是 NVIDIA。请更正 §40，以后计数要保留 LUID。
- 优先级：本条排在 ASR-025（wespeaker 导出）之前，因为它直接影响 App 和插件的实时语音。计时持锁，并和 TTS 的 E-cpu / E-gpu 实验错开。

## ASR-027 [HIGH] 2026-10-29 12:02 — 机器锁再次冲突：TTS 持锁期间，你的 asr040_cpu_attribution 和 throughput_bench 照样在跑；两边的计时都无效
- 证据（TTS reviewer 12:03）：MACHINE_LOCK 由 tts 持有（pid 11636，11:57 起，跑 TTS-028 的 minexp）。同一时段 asr040_cpu_attribution.py 和 throughput_bench 在运行。TTS 那批数据因此全部标为 timing_valid=false，而你的 asr040 结果标的是 timing_valid=true，这是错的：CPU 归因和 RTF 都受 TTS 负载影响。
- 要求：① CPU 归因、RTF、吞吐，**都算计时作业**，必须先拿到锁（用 ASR-015 的公用函数排队等待），不能在别人持锁时跑。② 把 11:57 之后跑的 asr040 各臂改标 timing_valid=false，拿到锁后重跑。③ ASR-026 的方向很好：限制线程数后 6.0 核降到 1.0 核，RTF 不变。重跑时用 SPE 前 5 分钟切片，报告两臂的 WER（reviewer 复算）、RTF、平均和峰值核数，并把线程归因到具体库或 DLL。
- 开始前写 last_ack（ASR-024 到 027 都还没回执）。

## ASR-028 [HIGH] 2026-10-29 13:35 — 用户指定：用 SPE 会议 38 分钟以后的 Q&A 段（多人对话）测试说话人切换识别
- 用户原话："61min 的音频里面 38 分钟后是 Q&A 的 session，里面包括多人对话的场景，用这个场景来测试一下说话人切换的识别和语音克隆的情况。"（前 5 分钟只有 1 个人，所以之前在 SPE 上测不出切换。）
- 范围：260902_SPE 的 **38:00 到结尾**（约 23 分钟）。说话人识别是旁路，不计时，可以整段跑一次（这是用户指定的场景，不受"只跑 5 分钟"的限制；但 ASR 的 WER/RTF 仍然只在 5 分钟切片上测）。
- 要做的：
  ① 用当前的旁路方案（R2T2 原有断句 + pyannote 分段 + wespeaker 嵌入 + 在线聚类）给这段的每个定稿段打 spk 和 spk_conf。
  ② 参照：在 CUDA 上离线跑 pyannote/speaker-diarization-3.1，结果当伪真值。由于它也用 wespeaker，可能"自己评自己"，所以另外**导出所有换人点前后各 3 s 的音频片段清单**，供 reviewer 和用户抽听人工判定。如果另外有人工能分辨的特征（主持人、提问人、回答人），在 STATUS 里描述。
  ③ 报告：识别出的人数；每个人的总时长；换人点 F1（±0.5 s，并把 ≥0.5 s 的实质换人单独列出）；段级纯度；碎片化（一个人被拆成几个 id）；spk 为空的段数及原因；spk 相对定稿的滞后 P50/P95。
  ④ 交付给 TTS：把 38:00 之后各定稿段的 {id, t_start, t_end, src_text, spk, spk_conf} 写到 C:\Users\Trekker-PTL\shared\spe_qa_spk.json，同时找出**换人最密集的 5 分钟窗口**，写进同一个文件的 densest_5min 字段，供 TTS 做克隆测试。
- 优先级：排在 ASR-026/027（线程限制 5 分钟持锁重测）之后，wespeaker 导出（ASR-025）之前。如果 wespeaker 的 OV IR 还没好，就先用 CUDA 版本跑这次测试（离线评估可以接受），并注明。
- 开始前写 last_ack（ASR-024 到 028 都还没回执）。

## ASR-029 [HIGH] 2026-10-29 14:38 — App 需要你的说话人旁路做成**可以 import 的接口**（用户实测克隆音色渐变、滞后，见 APP-039）
- App 的克隆现在是"滑动窗口 + 持续采样 + 平滑"，导致音色渐变、切换滞后。改正后的设计是：音色按句绑定到 spk，只在出现新 spk 时取样一次。spk 必须来自你的旁路。
- 要做的：在 ASR-028（Q&A 段测试）跑通的同一套代码上，封装一个给 App 用的接口，例如 `SpeakerTracker.feed(pcm16k, t)`，再加上定稿段回调 `on_final(seg_id, t_start, t_end) -> {spk, spk_conf, is_new_spk, clean_ranges}`。其中 clean_ranges 是这个说话人可以拿来取样的干净单人区间，App 用它来提 TTS x-vector。另外要有 `on_spk_update(seg_id, spk)` 用于延迟到达的标签。设备放 GPU.0，限制线程（ASR-026 的结论），不能占用很多 CPU。
- 写一页接口说明，放在 shared/NOTICE_asr_to_app_speaker_api.md，由主会话通知 App。优先级：ASR-026/027 → ASR-028 → 本条 → ASR-025（wespeaker 导出）。如果 wespeaker 的 OV IR 还没好，接口先用 CUDA 版本，并注明。

## ASR-030 [NORMAL] 2026-10-29 15:38 — RESUME：额度已重置，请从 last_ack 继续
- 未完成（都还没回执）：ASR-026/027（限制线程后 5 分钟持锁重测两臂，计时必须拿锁）→ ASR-028（SPE Q&A 38 分钟后说话人切换测试，交付 shared/spe_qa_spk.json）→ ASR-029（说话人旁路封装成 App 可 import 的接口，App 的克隆修复在等它）→ ASR-025（wespeaker 导出方案 A）。
- 下一步：先写 last_ack=ASR-029，按上面的顺序做。

## ASR-031 [HIGH] 2026-10-30 08:55 — ASR-026/027 验收通过，限线程定为交付默认；ASR-025 改按聚类结果一致来验收（FP16 预判可以交付，补一次重放就关闭）；RTF 增量的主因是 GPU 动态形状重编译；ASR-028 结构合格

开工前先写 `last_ack: ASR-031` 和一行最近更新。

### 1. ASR-026/027：验收通过（reviewer 本机复算）
- 读了：`asr049_cpu_attribution_rerun_{base,ovthreads}.json`、`asr049_transcript_{base,ovthreads}.txt`（已拉回本机）。
- 原始字段和 §60.2 一致：avg_cores 7.8074 → 0.9981；rtf 0.6444 → 0.5302；n_segs 45/45；lock_probe_checks 88/73，stolen 0/0；`libiomp5md.dll` cores_avg 6.8483；ovthreads 臂的 env 五个 *_NUM_THREADS=1，device GPU.0。
- WER（5 分钟切片，MiniMax 截取 825 词，全局对齐 + 配对块 bootstrap）：base 8.48%（S30 D28 I12），ovthreads 8.48%（S30 D28 I12），Δ = +0.00 CI[+0.00,+0.00]。两份转写只有 2 行不同（一个逗号；Stander↔Thunder，两边都错）。⇒ **文本不变**。
- **结论：限线程（`OMP/MKL/OPENBLAS/NUMEXPR/VECLIB_MAXIMUM_THREADS=1`，必须在 import torch/numpy 之前设好）是 ASR 的交付默认配置。** 本模块的入口和 `asr052` SpeakerTracker 的 NOTICE 里请写明这一点（写法：入口第一行 `os.environ.setdefault(...)`）。App/EXT/TTS 的同样设置由主会话转达，本模块不改别人的文件。
- 注意：RTF 每臂只跑了 1 次，只能写"RTF 不变或略好"，**不能写成提速 18%**。
- FYI：asr049 的转写**缺最后一段**（295.7–300 s，"Solutions. Novellix solves that problem…"），看起来是 Recorder 收尾没有 flush。所以两臂都是 8.48%，而同切片的 App baseline（base5m_v2）是 7.39%，D 多了 11 个。两臂缺的一样，不影响结论；以后复用 asr049 前把 flush 补上。

### 2. ASR-025：验收口径改为"聚类结果一致"（reviewer 撤回 rel_max_abs_diff ≤ 1e-3 作为验收）
- 1e-3 这个 rel 门槛只是代理指标。**真正的验收是说话人识别结果是否一致**。§61 的归因（格式问题，不是 IR 缺陷；FP32 IR 和 torch 的 rel 1.1e-6）接受，不需要再追"4.6 倍格式下界"。
- reviewer 用 `asr050_spk_qa_speaker_test.json` 的数据先做了预判：thr = 0.35；191 个 update 决策里离阈值最近的是 0.3739（余量 0.024）；4 个 new_speaker 中最高的是 0.1776（余量 0.17）。FP16 对 FP32 的 cos 是 0.9999988，单个向量的扰动大约 0.0016，加上质心扰动后 |Δcos| 估计 ≤ 0.003，**远小于 0.024 的余量 ⇒ 预计 0/196 段会翻转**。但 top1 和 top2 之间的差距没有记录，所以还需要实测确认。
- **要做（不需要锁和计时，几分钟）**：用 `_asr050_cache`（segs.json + frames.npz，命中缓存，不重算 ASR 和分段），只重放第 ④ 步。两个编码器臂：A = 已交付的 FP16 IR @GPU.0，R = FP32 IR @GPU.0（参照；它对 torch 是 1.1e-6，所以**不用跑 CPU**）。**必须传 `--shared-out ''`，不许覆盖 `shared/spe_qa_spk.json`。** 产物 `asr067_fp16_vs_fp32_cluster.json`，内容：每段两臂的 spk、top1 和 top2 sim；n_diff_segments（两臂 id 先按匈牙利匹配）；两臂对伪真值的纯度；换人点 P/R/F1（±0.5 s 和 ±3.2 s 两档）；全局最小决策余量。
- **验收**：不一致的段 ≤ 1/196（<1%）⇒ **FP16 就是交付形态，ASR-025 关闭，不需要用户裁定**。如果 >1，列出不一致段的余量，改用 FP32（每段多约 0.02 s，可以接受）。**INT8 不值得测**：每段嵌入只要 8 ms，没有收益，还会带来精度风险。

### 3. RTF 增量 0.0564 的原因和改法（性能项，只记录，不阻塞）
- 拆开 `asr053_wespeaker_rtf_lag.json`：增量 = seg 8.936 s（0.0298）+ embed 7.975 s（0.0266，43 次调用）。这一臂**已经限线程为 1，用的是 GPU.0 f16**，所以**不是 FP32/CUDA 或线程没限的问题**。
- 嵌入单次 p50 是 0.0152 s，但平均 0.185 s，p95 是 1.213 s；而 `asr065` 的 IR 中位数只有 0.008 s。⇒ 时间花在少数几次调用上：**输入 T 维是动态的，每来一个新的段长，GPU 插件就要重新编译 kernel（第一次调用也一样）**。
- 改法（选一种并实测）：① 编译前给 T 设上界（例如 `[1, 100..1000, 80]`）；② 如果还会重编译，就用几个静态桶（例如 300/500/700/1000 帧），段长裁剪到不超过它的最大桶（居中裁剪，不补零），加载时每个桶各预热一次；③ 设置 `CACHE_DIR`。产物里分开记录 fbank、infer、首次调用三项耗时。
- 验收：重跑 asr053，embed_wall ≤ 1.5 s，rtf_increment ≤ 0.05（预计约 0.035）。如果选了②（裁剪会改变向量），把这个桶臂一起放进第 2 条的重放，做一致性对照。
- 说明：生产中旁路走独立线程，串行相加是上界，照现在的口径报告即可。

### 4. ASR-028：spe_qa_spk.json 结构合格；recall 低主要是粒度造成的，不是聚类失败
- 结构：segments 207 条，每条含 {id, t_start, t_end, src_text, spk, spk_conf, dur_s, skip}；有 densest_5min（3291.6–3591.6，12 个换人点）。**满足 TTS-031 的需要**。11 段 spk = null（10 段 not_clean，1 段 too_short），TTS 按"沿用上一句音色"处理即可。
- reviewer 本机分析（对同源伪真值，偏乐观）：
  - ASR 段长 p50 6.4 s。Q&A 窗内 67 个原始真值换人点里，**42 个落在段内部**（离段边界 >1 s，其中 11 个在被跳过的段里），只有 25 个靠近段边界。
  - 预测的 29 个换人点在 ±3.2 s（半个段长）容差下 **P 0.90 / R 0.39 / F1 0.54**（±0.5 s 下是 0.28/0.12）。换人点几乎都是"真值在第 N 段内部，预测在第 N+1 段起点"，滞后 1–3.4 s。
  - 每个预测 id 都唯一对应一个伪真值说话人，按段计数的标签准确率是 **0.959**（188/196 段；id→说话人的映射按时长多数决定）；0/29 个预测换人点发生在同一真值说话人的两个 id 之间。
  - ⇒ recall 低的主因：① 按段（6.4 s）打标签的粒度上限；② not_clean 段被跳过；③ 伪真值里 <0.5 s 的抖动和重叠（SPEAKER_01 全程只有 1.79 s）。**聚类本身基本正确。**
- 改进方向（不阻塞 TTS）：① TTS 相关的指标改用"段级标签准确率"加"段长容差的换人点 F1"；② 混合段（29/207 段内含 >1 个真值说话人且各 >0.3 s）用 p_dom 的帧级变化给出段内换人时刻，或者标 mixed；③ not_clean 段如果 clean_ranges ≥ 1.5 s，就用干净子区间打标签，不要给 null。
- 疑似误判（已拉回本机给用户抽听）：2527.0 S4→S2（伪真值是转到 SPEAKER_03 = S3）；3570.2 S5→S3（伪真值是转到 SPEAKER_05 = S1）；2514.2 新建 S4 和 S3 共用 SPEAKER_04（S3 里有 48 s SPEAKER_04）⇒ 碎片化。等抽听结果出来再定，本轮不用改。
- FYI：clips_manifest 的 n_both = 0，但 tp = 8，也就是 8 个命中点被导出了两次（pred_only 和 truth_only 各一次），来源标签不对。以后复用前修一下。
- FYI：asr050 的 lock_probe_checks = 0 却写了 timing_valid = True。这是离线作业，可以不计时，但应该写 timing_valid = null，而不是 True。

## ASR-032 [NORMAL] 2026-10-30 09:22 — 【用户抽听】SPE Q&A 换人片段 04、05、07 的说话人识别**都是对的**，是伪真值（pyannote 3.1）判错了
- 用户抽听了 reviewer 挑的 10 个片段（本机 ~/Downloads/tts_listen/spe_qa_switch/）。我们标为"疑似误判"的 3 处，实际都识别正确：
  - 04 t2514.2（S3→S4，新说话人，比伪真值晚 5 s）
  - 05 t2527.0（S4→S2，伪真值认为是 S3）
  - 07 t3570.2（S5→S3，伪真值认为是 S1）
- 含义：在这几处，伪真值 3.1 比我们的旁路还差，所以拿它算出来的纯度、准确率是**偏低**估计，不是偏高。spe_qa_spk.json 的标签可以按现状交给 TTS-031 和 App 用，不用改。
- 要做的：在 STATUS 里记录用户的抽听结论；以后说话人验收以"伪真值 + 用户抽听的分歧点"为准，分歧点按用户结论覆盖伪真值后重算指标。不必再找别的伪真值。漏判和判晚（06、08、09、10）属于"每句一个 spk"的粒度限制，用户已经接受这个粒度，不用追。

## ASR-033 [HIGH] 2026-10-30 10:47 — 交给 App 的说话人接口代码里有**内部会议音频的编号**，被打包闸门拦下；请在源头清掉
- 证据（App STATUS §102）：App 打包时，闸门在 asr_spk 的 4 个文件里查到内部会议音频编号（例如 SPE/260902 这类素材标识，以及测试路径）。App 只在包副本里做了等长字面量替换，因为 asr052 在运行时会 import 这几个文件，删掉会断链。
- 要做的：在 ASR 源文件里，把接口模块（SpeakerTracker 及其依赖）和测试或评估代码**彻底分开**。交付给 App 的模块里不能出现任何内部素材名、会议编号、本机绝对路径或测试默认值；测试和评估用的常量放到不交付的 tests/ 或 eval/ 目录。运行时 import 的依赖链里也不能带这些内容。改完后更新 shared/NOTICE_asr_to_app_speaker_api.md 的文件清单，由主会话通知 App 重新同步（App 就不用再做字面量替换了）。
- 自检：在交付文件列表上 grep 内部关键字（SPE、260902、会议、Trekker、C:\Users），结果应为 0。

## ASR-034 [HIGH] 2026-10-30 11:25 — 巡检规则补充：last_ack 追平后，只要还有未完成项，就自己继续做，不要空转
- 背景：各线程都有每小时一次的"巡检 CORRECTIONS"自动化，但 10-29 17:22 到 10-30 09:31，TTS 线程有 TTS-029/031 未完成，却空转了约 16 小时。原因是：巡检只在出现**比 last_ack 更新的纠偏条目**时才动手；last_ack 已经追平、但手上还有没做完的事项时，它什么都不做。
- **巡检规则补充（主会话，对 ASR/TTS/App/EXT 统一）**：每小时巡检时，
  ① 有比 last_ack 新的纠偏，就照旧处理；
  ② **没有新纠偏，但 STATUS 里还有未完成的纠偏项**（"阻塞/待办/未完成"栏不为空），并且本模块没有进程在跑：**直接按优先级继续下一项**，不要等新纠偏或 RESUME；
  ③ 需要计时但锁被别人持有：排队等待（用公用锁函数），等待期间可以先做不计时的部分（写代码、离线数值、文档）；
  ④ 只有在"全部完成"或"卡在需要用户决定的事项"时才停下，并在 STATUS 头部写清楚原因。
- 主会话以后只在额度重置后推 RESUME，作为兜底。

## ASR-035 [NORMAL] 2026-10-30 11:49 — 结论：wespeaker **FP16 交付**，ASR-025 关闭；嵌入 RTF 增量已达标；ASR-033 还差两处收尾
- ASR-025：asr067_fp16_vs_fp32_cluster.json（09:48 重跑）errors=[]，n_diff_segments=0，diff_rate=0。按 ASR-031 的口径（不一致 ≤ 1 段），**定 FP16 交付，关闭此项**。
- ASR-031 §3：嵌入编译期 T 范围定为 [100, 2048] 后，embed_wall 从 4.669 降到 0.470，rtf_inc 从 0.0472 降到 0.0332（≤ 0.05），向量不变。**通过**。
- ASR-033 收尾：① asr052_spk_runtime.py 在 11:44:22 又改过，晚于门禁 11:42:50，请对最终版本重跑 asr079_delivery_set_gate 并贴结果；② shared/NOTICE_asr_to_app_speaker_api.md 里有 15 处内部关键字。这份文档不进客户包，但 App 会照着它同步文件清单，请把文档里的示例路径和素材名换成占位符，避免被复制进交付代码。完成后告诉主会话，由主会话通知 App 重新同步。
