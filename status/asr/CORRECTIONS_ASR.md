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
