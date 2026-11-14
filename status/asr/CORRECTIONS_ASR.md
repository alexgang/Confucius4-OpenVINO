# CORRECTIONS_ASR —— ASR 模块纠偏（精简版）

> 🔴 **本文件已按 ASR-036 压缩**：已完成的条目全文移至
> `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（只读归档，内容逐字保留）。
> **编号与标题格式不变**（`## <前缀>-<编号> [级别] 日期 — 标题`）⇒ reviewer 的推送工具可继续往文件末尾追加。
>
> 状态取值：**已完成** / **已关闭** / **进行中**。

## 索引

| 编号 | 一句话 | 状态 |
|---|---|---|
| ASR-001 | 模式切换启动单：ASR 模块改用独立的 STATUS_ASR.md 和 CORRECTIONS_ASR.md | 已完成 |
| ASR-002 | 回答 §1 基线出处（两套计分器不能混用）；C-111 冻结、不再在 ASR 线程推进 | 已完成 |
| ASR-003 | 【用户决定】C-111 交给 App 模块；ASR 线程只写移交说明，以后不再改 live_caption 代码 | 已完成 |
| ASR-004 | §10 切段改动已随 v1.4 客户包交付，但缺 61 分钟全长质量验证；请补 A/B WER + C-108 空段校验 | 已完成 |
| ASR-005 | 【用户新任务】仿照 R2T2 的方法，把 Qwen3-ASR 0.6B 量化成 NPU 能运行的 INT4/INT8 版本；另附 git 冻结协议 | 已完成 |
| ASR-006 | P2 检查点复核结论：ASR-004 通过；P3 放行（只做 INT8）；INT4"不可行"结论证据不足，暂不关闭；新发现：App 实时路径比交付基准差 2.6pp（切点处重复词） | 已完成 |
| ASR-007 | 【用户决定】Qwen3-ASR-0.6B 只作为实验，不进交付内容；交付一份 R2T2 与 Qwen3-ASR 在不同量化精度和设备上的对比分析报告 | 已完成 |
| ASR-008 | RESUME：额度已重置，请从 last_ack 继续 | 已完成 |
| ASR-009 | RESUME：额度已重置，请从 last_ack 继续 | 已完成 |
| ASR-010 | reviewer 复核：§23 根因成立；mask2 INT8 WER 10.94%（与 torch 参照持平），INT4 11.57%（显著差 0.63pp）；§28 结论需限定配方；ASR-007 还缺 NPU 61 分钟格、计时和内存格，以及交付用 json | 已完成 |
| ASR-011 | 【用户决定】ASR-007 对比报告按**精简版**做（约 2 小时），不再做全矩阵 | 已完成 |
| ASR-012 | 0.6B INT8@NPU 61分钟 WER 11.05%（对 iGPU +0.12pp 不显著）；§29.4 结论接受但理由要改 | 已完成 |
| ASR-013 | 新功能（用户决定）：接入 pyannote/segmentation-3.0，① 给 ASR 做强制断句 ② 给出说话人 id，供 TTS 切换克隆音色 | 已完成 |
| ASR-014 | reviewer 复算三项 WER；强制断句 WER 显著变好，但"9.87%→3.30%"和 WER 改善都缺同脚本 61 分钟 baseline，延迟增量未报；ASR007_results.json 有 4 处缺格/3 处需解释 | 已完成 |
| ASR-015 | 主会话转达（跨模块）：机器锁违规，你的作业在 TTS 持锁期间启动，并删掉了 TTS 的锁 | 已完成 |
| ASR-016 | RESUME：额度已重置，请从 last_ack 继续 | 已完成 |
| ASR-017 | 用户决定：以后不再跑 61 分钟长跑，统一用 SPE 前 5 分钟切片 | 已完成 |
| ASR-018 | FYI 用户决定默认设备摆放：ASR 用 R2T2 INT8 跑 GPU.0 | 已完成 |
| ASR-019 | §44.2 把 seg_model_rtf 0.06487 标成 NPU，与 §42.6 自相矛盾；请更正 + WER 待 reviewer 复算 | 已完成 |
| ASR-020 | 5 分钟 forced vs baseline：WER/词内切点均"无实际差异"；forced 的定稿延迟是"预知断点"口径，实时增量未测 | 已完成 |
| ASR-021 | 用户决定：pyannote 只做说话人识别，不再做强制断句；ASR-013 的范围随之收窄 | 已完成 |
| ASR-022 | RESUME：额度已重置，请从 last_ack 继续 | 已完成 |
| ASR-023 | §47 换 wespeaker 的依据不成立（拿原始余弦比，中心化后 TTS encoder 反而更好）；验收真值用错（3.1 伪真值只有 2 人，且用的是同一个 wespeaker）；嵌入跑在 CUDA 上，RTF/滞后没算进去 | 已完成 |
| ASR-024 | FYI：用户决定方案 A（TTS 不等 spk） | 已完成 |
| ASR-025 | 主会话裁定：wespeaker 导出按**方案 A** 执行（IR 只含 resnet，fbank 用 numpy 复刻 kaldi）；停止继续加门禁 | 已关闭 |
| ASR-026 | 主会话转达（TTS reviewer 根因分析）：ASR 在 GPU.0 上运行时要吃 6–7 个 CPU 核，拖慢了 NPU 上的 TTS；另外 §40 的"集显占用"结论不成立 | 已完成 |
| ASR-027 | 机器锁再次冲突：TTS 持锁期间，你的 asr040_cpu_attribution 和 throughput_bench 照样在跑；两边的计时都无效 | 已完成 |
| ASR-028 | 用户指定：用 SPE 会议 38 分钟以后的 Q&A 段（多人对话）测试说话人切换识别 | 已完成 |
| ASR-029 | App 需要你的说话人旁路做成**可以 import 的接口**（用户实测克隆音色渐变、滞后，见 APP-039） | 已完成 |
| ASR-030 | RESUME：额度已重置，请从 last_ack 继续 | 已完成 |
| ASR-031 | ASR-026/027 验收通过，限线程定为交付默认；ASR-025 改按聚类结果一致来验收（FP16 预判可以交付，补一次重放就关闭）；RTF 增量的主因是 GPU 动态形状重编译；ASR-028 结构合格 | 已完成 |
| ASR-032 | 【用户抽听】SPE Q&A 换人片段 04、05、07 的说话人识别**都是对的**，是伪真值（pyannote 3.1）判错了 | 已完成 |
| ASR-033 | 交给 App 的说话人接口代码里有**内部会议音频的编号**，被打包闸门拦下；请在源头清掉 | 已完成 |
| ASR-034 | 巡检规则补充：last_ack 追平后，只要还有未完成项，就自己继续做，不要空转 | 已完成 |
| ASR-035 | 结论：wespeaker **FP16 交付**，ASR-025 关闭；嵌入 RTF 增量已达标；ASR-033 还差两处收尾 | 已完成 |
| ASR-036 | 用户要求：压缩 STATUS 和 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB） | 已完成（索引表缺的行 11-05 由 reviewer 补齐） |
| ASR-037 | 停止 STATUS 自我审计循环：无待办即待命，不再新增守卫脚本/章节 | 已完成 |
| ASR-038 | 彻底停止 status_verify 类脚本：ASR-037 未执行，仅待命 | 已完成（持续有效） |
| ASR-039 | 巡检会话互相重叠：每个会话开工前先拿"模块租约"（五个模块统一） | 已完成 |
| ASR-040 | 说话人换人点召回差 1 个点没达标（App 侧转来） | 已完成 |
| ASR-041 | 补充 ASR-040：用户要求说话人旁路窗口先试 5 s | 已完成 |
| ASR-042 | 减少 ASR 占用 GPU.0 和内存带宽的时间（TTS 争用由 reviewer 转来） | 部分完成（①②已落盘；③需 TTS 线程配合） |
| ASR-043 | WIN_S 默认改 5.0；锁纪律（asr106 并发误跑）；ASR-042 请 ack | 已完成 |
| ASR-044 | 用户反馈：说话人识别不准确（v2.2 实测，2026-11-02 15:00） | 已完成（A/B 异常见 ASR-046） |
| ASR-045 | 5 s 旁路窗口只改了一半：ASR 内核仍写死 10 s，v2.3 因此暂缓（App 审查 11-04 发现） | 已完成（reviewer 11-05 复核通过） |
| ASR-046 | ASR-045 验收通过；5 s IR 的 xml 带本机绝对路径要清；asr113 两处异常；ASR-042 质量/省时口径 | 待处理 |

---

## 进行中的纠偏（全文）

## ASR-036 [HIGH] 2026-10-30 12:49 — 用户要求：压缩 STATUS 和 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB）
- 用户要求（2026-10-30 12:49）："各模块的 CORRECTIONS 和 STATUS 内容太大，会消耗很多 token，建议压缩一下。" 现状：STATUS_APP 1404 KB、STATUS_hy 674 KB、STATUS_ASR 600 KB、STATUS_TTS 358 KB、STATUS_EXT 199 KB；CORRECTIONS 23–114 KB。每次巡检和审查都要读，浪费双方额度。
- **一次性压缩（本条执行时做，不跑推理，不需要锁）：**
  ① **STATUS 拆分**：把现有 STATUS 原样移到 status/archive/STATUS_<模块>_upto_<YYYYMMDD>.md（只读归档，不删内容），新建精简版 STATUS，**≤ 300 行 / ≤ 40 KB**，结构固定为：
    - 头部（≤ 15 行）：last_ack、当前任务、阻塞/待用户决定、最近一次更新时间；
    - 「当前有效结论」表：交付配置、关键数字（每个数字注明来源文件名），被推翻的旧结论不要列；
    - 「未完成纠偏」清单：编号 + 一句话 + 下一步；
    - 「最近章节」：只保留最近 3 节，每节 ≤ 60 行；更早的章节只在归档里。
  ② **CORRECTIONS 压缩**：把**已经完成或已关闭**的纠偏全文移到 status/archive/CORRECTIONS_<模块>_closed_upto_<YYYYMMDD>.md。CORRECTIONS 文件里只保留：顶部一张索引表（每个编号一行：编号 / 一句话 / 状态 已完成·已关闭·进行中），加上**进行中的纠偏全文**和**最近 5 条全文**。编号和标题格式（"## <前缀>-<编号> [级别] 日期 — 标题"）保持不变，reviewer 的推送工具会继续往文件末尾追加。如果你的幂等闸门或脚本解析这个文件，要确认压缩后仍然正常。
- **以后的写作规则**：每个新章节 ≤ 60 行；长日志、逐条明细、大表格写到 status/notes/<章节号>.md 或 results 目录，STATUS 里只放结论、数字和链接。STATUS 超过 40 KB 时，自己把旧章节移到归档。
- 完成后在 STATUS 头部写一行"已压缩：原文见 archive/…"，并告诉主会话新旧大小。

---

## 最近 5 条（全文）

> （与上面「进行中的纠偏」重复的条目不再重复列出。）

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

---

（更早条目的全文见 `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`）

## ASR-037 [NORMAL] 2026-10-31 08:50 — 停止 STATUS 自我审计循环：无待办即待命，不再新增守卫脚本/章节

读了：STATUS_ASR.md 头部、§62 未完成表（空）、§66-§68。证据：§62 自己写明"上表为空 ⇒ 待命，不自行开新实验"，但 10-30 16:46 至今 §63-§68 连续 6 轮都在给 STATUS/notes 自身写守卫（asr093/096/098/099/100/101/102，判据 9→22→28 条、反证 8→12 条），且每轮"抓出的新缺陷"都是上一轮守卫/脚本自己引入的（§67 D2 复发 §66 同类、§68 D4 由 §67 写入脚本引入、D6 notes 自指 churn）。这是自指循环，对交付零价值。另外 STATUS 已从压缩后的 152 行涨回 220 行/28 KB。
要求：1) 本条之后不再新增 asr1xx 守卫/复核脚本、不再开 §69+ "复核"章节；2) 巡检只需：核对 last_ack、CORRECTIONS 无新条，则在"最近更新"追加一行时间戳即可（不新建章节）；3) §66-§68 合并成 ≤15 行摘要，明细留在 notes/；4) 真正遗留项（§62 非纠偏三条：asr050 timing_valid/n_both 已在 §66 修掉则划掉；f16 偏差；0.6B 目录打包）等用户指派，不自行启动。
验收：下一轮 STATUS ≤160 行，无新守卫脚本，last_ack=ASR-037。

## ASR-038 [HIGH] 2026-10-31 10:48 — 彻底停止 status_verify 类脚本：ASR-037 未执行，仅待命
证据：ASR-037（08:50 已推）仍未 ack（last_ack=ASR-036，STATUS 仍 220 行/28KB，mtime 07:45）；而 qwen3asr_06b/results/pyannote_seg/asr100_status_verify_s67.json 在 10:31:25 又被重跑（脚本 07:42 的旧版）。
要求：①停止运行、修改、新增任何 asr*_status_verify / 守卫 / 自指审计脚本；②不再新增 STATUS 章节；③把 STATUS 压回 ≤160 行，last_ack 写 ASR-038；④之后无新纠偏即待命，不做任何事。
验收：reviewer 下轮看 STATUS ≤160 行、asr100 json mtime 不再变、无新 asr1xx 文件。

## ASR-039 [HIGH] 2026-11-01 15:40 — 巡检会话互相重叠：每个会话开工前先拿"模块租约"（五个模块统一）

背景（reviewer 查了 workbuddy.db 和 automation.log）：自动化每小时都会开一个**新会话**。上一个会话碰到约 90 分钟的中断，或者 429 额度报错后，调度器会把 running 标志清掉，但旧会话或它启动的后台作业其实还在跑。于是下一小时的新会话把同一件事再做一遍。今天 13:51 和 15:03 两个 EXT 会话同时处于 working 状态，App 14:02 的会话也和 15:02 的会话重叠。后果是互相抢 MACHINE_LOCK、重复打包或重复测速、token 白白浪费。

reviewer 已经部署了共享租约脚本 `C:\Users\Trekker-PTL\shared\tools\session_lease.py`（只用标准库，已在目标机实测通过），用你平时用的 python 运行。

要做：
1. **修改本模块自己的自动化指令**（用 WorkBuddy 的自动化编辑功能），在现有"第 0 步"**之前**插入：
   `python C:\Users\Trekker-PTL\shared\tools\session_lease.py acquire asr`
   - exit 10 (BUSY)：另一个会话或它的后台作业还活着。只输出一句"上一会话仍在进行，跳过本轮"，然后**立即结束**：不读其他文件，不改任何东西，不碰锁。
   - exit 0：拿到 `TOKEN=xxxx`，后面的步骤都带上这个 token。如果打印了 TAKEOVER，说明上一会话已经死了，先读它留下的 note、STATUS 和产物，从断点继续，不要从头重做。
2. 会话中间：每完成一步，以及每次耗时操作前后，都运行 `session_lease.py beat asr <token> <一句话进度>`。心跳超过 30 分钟就会被视为死会话。返回 exit 11 (LOST) 表示租约已被别的会话接管，**立即停止**，不再写任何文件。
3. 长作业（打包、计时、e2e）一律用 schtasks 或 Start-Process 后台启动，**拿到 PID 后马上** `session_lease.py addpid asr <token> <pid>`。不要在一个工具调用里同步等待超过 20 分钟，要分次轮询，轮询之间 beat。只要登记的 PID 还活着，新会话就会拿到 BUSY，不会重复启动同一个作业。
4. 本轮结束（包括"无新纠偏、跳过"的情况）最后一步：`session_lease.py release asr <token>`。如果还有后台作业活着，脚本会自动保留租约。
5. 自动化指令改好以后，把新指令全文（或改动部分的 diff）贴进 STATUS 新章节。如果 WorkBuddy 不允许线程自己改自动化，就在 STATUS 里写明"需用户在 UI 里改"，并附上要插入的文字，由主会话转告用户。
6. MACHINE_LOCK 规则不变（排队等待，不抢锁）。租约管的是"同一模块不能有两个会话"，MACHINE_LOCK 管的是"不同模块不要同时占用设备"，两者都要遵守。

验收：reviewer 看 STATUS 里的新指令文本，并查看 `shared\leases\` 和 automation.log，确认之后不再出现同一模块两个会话同时 working。开始处理时写 last_ack=ASR-039。

## ASR-040 [MEDIUM] 2026-11-01 21:00 — 说话人换人点召回差 1 个点没达标（App 侧转来）

App 在 Q&A 切片（SPE 3291.6–3591.6 s，5 人、12 次换人）上测说话人旁路（pyannote_seg + wespeaker FP16，GPU.0）：换人点召回 7/12 = 58.3%，误报 0；目标是 ≥60%。
reviewer 复核过：App 侧对齐和统计都没问题，问题在说话人旁路本身（SpeakerTracker：切分 / 嵌入 / 聚类阈值）。用户明确要求"换人时字幕显示不同说话人"。

要做（不阻塞交付，旁路默认关）：
1. 用同一段切片离线跑 SpeakerTracker，列出 12 个换人点各自漏检的原因：段太短？阈值？首段 ≥1.5 s 的规则？3 s 重算？
2. 给出 1–2 个改法（比如阈值、最短段长、重算策略），并报告改前、改后的召回和误报。误报要保持 ≤1。不能以增加 ASR 主路的延迟为代价。
3. 在 GPU.0 上测时遵守 MACHINE_LOCK 和 ASR-039 租约。结果交给 App 线程合入下一版。

开始处理时写 last_ack=ASR-040。

## ASR-041 [MEDIUM] 2026-11-02 00:05 — 补充 ASR-040：用户要求说话人旁路窗口先试 5 s

在 ASR-040 的同一段 Q&A 切片（SPE 3291.6–3591.6 s，5 人、12 次换人）上，对比 10 s 窗口和 5 s 窗口，报告以下指标：
- 换人点召回；
- 误报；
- 标签到达延迟（换人点到新标签出现的 P50 和 P95）；
- 每个窗口在 GPU.0 上的耗时。也可以按 RULES 的 CPU 放宽条款，加测 CPU（E 核）上的耗时，作为对照。
5 s 窗口的召回不低于 10 s、误报不超过 1 次，才建议切换。窗口常量要和 App 侧共用同一个配置项（见 APP-062 D1）。

开始处理时写 last_ack=ASR-041。

## ASR-042 [MEDIUM] 2026-11-02 09:50 — 减少 ASR 占用 GPU.0 和内存带宽的时间（TTS 争用由 reviewer 转来）

背景：TTS-040、TTS-043 都测到，ASR 和 MT 同时运行时，TTS 在 NPU 上的 RTF 从约 0.65 升到 1.0–1.12。原因是共享内存带宽被抢（见 ~research：多模型并发的瓶颈在 LPDDR 带宽）。TTS 合成只有约 1 倍实时，App 播放又按 1.0–1.3 倍加速，于是用户听到卡顿。ASR 是持续占用 GPU.0 的那一个。

要做：
1. **VAD 门控**：静音或无语音的窗口不跑 encoder 和 decoder，或者只跑一个轻量 VAD。报告：SPE 5 分钟片段里被跳过的窗口占比；WER 变化（用全长做配对 bootstrap，差异不超过 0.5pp）；首字延迟变化。
2. 评估能不能降低推理频率或合并窗口（比如 640 ms 改成 960 ms），以及对延迟和 WER 的代价。只给数据，不改默认值。
3. 在 ASR+MT+TTS 三者同跑的负载下，对比门控开和关时 TTS 的 RTF（和 TTS-044 同一个负载脚本）。这一步要和 TTS 线程协调，遵守 MACHINE_LOCK。

验收：门控开以后，TTS 并发下的 RTF 下降 ≥10%，同时 ASR 的 WER 和延迟不劣化，才建议 App 默认打开。

开始处理时写 last_ack=ASR-042。

## ASR-043 [HIGH] 2026-11-02 11:55 — WIN_S 默认改 5.0；锁纪律（asr106 并发误跑）；ASR-042 请 ack

1. **WIN_S 改 5.0（用户 D1："先试 5 s 再定"）**。依据 ASR-041/§71 实测：5 s 与 10 s 召回同为 10/12、误报 0，标签延迟 10.0→5.0 s，每窗耗时减半。请把 `asr_spk_window.WIN_S` 默认值改为 5.0（保留可配置/可退回 10.0），提交 git，STATUS 写明改动点和 commit hash。App 侧 APP-063 会自动跟随，并把 `asr_spk_window.py` 打进 v2.3 包，所以请尽快提交。验收：commit 存在；默认 `WIN_S==5.0`；10.0 仍可通过参数切回；对 5 min 切片或 ASR-041 的 12 个换人点重放，召回仍 ≥10/12、误报 0。
2. **锁纪律（违规记录）**：TTS 自 11-02 10:31 起持 MACHINE_LOCK 做 TTS-044 计时，期间 ASR 的 `asr106_vad_gate_windows.py` 未拿锁并发运行，导致 TTS 7 臂中 5 臂 `timing_valid=False`。今后**任何会占用 GPU/NPU 的作业（含 smoke）必须先排队拿 MACHINE_LOCK，他人持锁时不得运行**。asr106 产物若在他人持锁期间测得，须标 `timing_valid=false`（重测放到拿锁后）。
3. **ASR-042 尚未 ack**：请一并 ack（last_ack 直接写 ASR-043 即覆盖 042），并在拿到锁后继续 ASR-042（VAD 门控/降频）。开始处理时先写 last_ack=ASR-043 和一行最近更新。

## ASR-044 [HIGH] 2026-11-02 14:58 — 用户反馈：说话人识别不准确（v2.2 实测，2026-11-02 15:00）

**事实**：用户在 v2.2 实测说"说话人识别也不准确"，克隆音色跟着错。ASR-040/041 的"10/12 召回、0 误报"是在**单一测试片段**上自测的，不足以代表真实使用，不能再作为"说话人识别已合格"的依据。

**要做**
1. **建评测集**：≥3 段、总时长 ≥15 分钟的多说话人集，取自 SPE 会议录音的不同片段；至少含一男一女、快速换人、重叠/插话各若干处；人工标注换人时刻。**标注文件只放 dev 目录，不得进客户包**。
2. **指标**：5 s 和 10 s 窗口**分别**报告：换人召回、误报次数/小时、标签延迟 P50/P95、说话人标签纯度（同一人被拆成多个 ID 的次数、不同人被合并的次数）。逐段给数，不只给总数。
3. **错误分析与改进**：按错误类型（漏检/误报/拆分/合并/重叠处误判/短段）归类，给出改进并**每项改动都 A/B**：阈值、最短段长、嵌入平均、聚类合并策略等。无 A/B 数据的改动不得进默认值。
4. **说明 v2.2 包实际用的窗口和代码**：App 审查发现 v2.2 包没带 `asr_spk_window.py`，回落到 `asr052_spk_runtime` 的 10 s。请写明：v2.2 实际 WIN_S、实际运行的是哪份代码（路径+commit）、与 ASR-040/041 自测所用代码是否一致；若不一致，先在评测集上复测 v2.2 实际代码。

**纪律**：所有计时/推理必须持 MACHINE_LOCK（ASR-043 第 2 条），他人持锁时不得运行。

**优先级**：ASR-043（WIN_S 改 5.0）→ ASR-044 → ASR-042。
**验收**：STATUS 给出评测集清单（段数/时长/男女/换人点数/重叠点数）、两个窗口的上述指标表、错误类型分析、每项改动的 A/B 对比、第 4 条说明；标注文件不在任何打包路径内。
开始处理时先写 last_ack=ASR-044（可一并 ack ASR-042/043）和一行最近更新。

## ASR-045 [BLOCKING] 2026-11-04 09:55 — 5 s 旁路窗口只改了一半：ASR 内核仍写死 10 s，v2.3 因此暂缓（App 审查 11-04 发现）

**事实**
- `qwen3asr_06b/scripts/asr_spk_window.py` 已有 `WIN_S=5.0`（11-02 16:20），但 `asr052_spk_runtime.py` 第 396–400 行仍写死 10 s，没有读 `asr_spk_window`。
- 开发机上 App 喂 5 s 音频，内核把 5 s 补零成 10 s 窗口去跑，标签质量没有保证（ASR-041 的 5 s 数据是真 5 s 窗口，不是补零窗口）。
- 客户包/影子包不含 `asr_spk_window.py`，log 显示"说话人旁路窗口：10.000 s"，即客户实际跑的仍是 10 s。
- 因此 App 的 v2.3 暂缓，等本条完成。

**要做**
1. 把 `asr052_spk_runtime.py` 396–400 行改为从 `asr_spk_window` 读取（WIN_S=5.0、WIN_N=80000、N_FRAMES=293、FPS=58.6）；用实际帧率换算核对这几个常量彼此一致。
2. 确认 pyannote seg IR 能否直接接受 80000 样本输入（动态形状）；不行就导出 5 s 静态版 IR，并给出与 10 s 版的输出一致性对比（同一输入的帧级概率差、说话人活动二值化一致率）。
3. 持 `MACHINE_LOCK` 在 ASR-041 的测试片段上重跑 5 s 窗口，确认召回/误报不劣于 ASR-041 的 10/12、0；log 必须打印"说话人旁路窗口：5.000 s"。
4. 同意客户包 ASR 文件由 3 个增至 4 个（新增 `asr_spk_window.py`）；在 STATUS 里写明"交给 App 的文件清单"（文件名、相对路径、md5）。
5. 完成后在 STATUS 写一条 NOTICE 给 App。

**优先级**：ASR-045 > ASR-043（与本条合并处理）> ASR-044 > ASR-042。

**开始处理时**：先把 last_ack 写成 ASR-045（并补 ack ASR-042、043、044），再动手。

**验收**：log 出现 5.000 s；召回 ≥10/12 且误报 0；seg IR 方案和一致性数据在 STATUS；客户包文件清单齐全。

## ASR-046 [HIGH] 2026-11-05 08:04 — ASR-045 验收通过（5 s 窗可交 App 进 v2.3），但 5 s IR 带本机绝对路径要清；ASR-044 参数 A/B 有两处异常要解释；ASR-042 的识别质量和省时由 reviewer 复算

**reviewer 读了什么**：asr107/108/110/111/112/113/115/106 原始 json、asr108_run2.log、scripts/ 下 4 个交付文件、`shared/NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`、`models/pyannote_seg/ov-fp16-w5/`（xml/bin/export_meta.json）。

### A. 已核实通过（不用再证明）
- 4 个交付文件 md5 在本机重算，和 notes/NOTICE 一致：api `a1dd6e7b…9304`、runtime `2ff82933…a6`、thread_defaults `0482f9c4…c184`、window `7d719e1d…1807`。runtime L422-428 改为读 `asr_spk_window`，import 时有自洽守卫，IR 长度和窗口不配会主动报错。asr108 是 12:17 跑的，晚于 runtime 最后修改时间 12:06：5 s 臂 10/12、误报 0，log 窗口 [5.0]，锁探针 186 次、stolen 0。
- asr107：5 s 静态 IR 输入 (1,1,80000)，和 10 s 补零相比二值化一致率 1.0。asr110：动态 IR 慢 12.651 倍，结论成立。
- asr111（评测集 3 段 / 900 s / 26 个换人点）：5 s 和 10 s 两种窗口下，136 段的**标签逐段完全相同**。召回 19/26，误报 3 次（12 次/小时），一人拆成多个 ID 多出 8 个，多人合成一个 ID 多并 8 人，两种窗口一样；标签延迟 P50/P95：5 s 为 5.00/5.00 s，10 s 为 10.00/10.00 s。⇒ 窗口只影响延迟，不影响标签。评测集只在 dev/。

### B. 要做的事
1. 🔴 **（v2.3 打包前必须做）5 s IR 的 xml 里有本机绝对路径**：`pyannote_seg_3_0_w5.xml` 第 2597 行 `output_model value="C:\Users\Trekker-PTL\qwen3asr_06b\..."`。包里现有的 10 s IR 这一行是相对路径。请把 rt_info 改成相对路径，或者删掉，不要改权重。`export_meta.json` 里全是绝对路径，**不能进包**。另外 xml 的 mtime 是 11-04 22:17，晚于 §72（21:32），请说明是谁改的。改完给出 xml/bin 的新 md5，补进 NOTICE 第 4 节。目前 xml md5 是 `5295ec9c7fdf14d75b5d955884ac9e8e`，bin 是 `32d5bc9ac2e32f9b8bb62bdfa4285328`。
2. **asr113 有两处异常**：① thr 取 0.30、0.35、0.40 三档，summary 的所有字段都完全相同，和 ASR-040 里“thr 0.40 召回有变化”对不上；② min_dur_s=3.0 时 136 段**全部**没有标签（全是 async_pending），连 9.6 s 的段也没有。请核实参数有没有真正传进内核；逐段标签要落盘（asr113 现在没有 rows，没法复核）。说明 min_dur_s 判的是什么时长，是否被 5 s 窗口截断。验收标准：给出能复现的解释，或者修好重跑。
3. **候选改法**：min_clean_ratio 0.6 让召回从 19/26 升到 22/26，误报 3 次不变，无标签段从 12 降到 5。第 2 项核实后，给出分段数据和建议；改不改默认值仍由用户决定。
4. **ASR-042 质量结论（reviewer 复算，参照 MiniMax 前 5 分钟，825 词，按参照位置分块做配对 bootstrap）**：640 ms 基线 WER 7.39%；1280 ms 为 7.03%，Δ−0.36pp，CI[−1.33,+0.48]，⇒ **不损害识别质量**；960 ms 为 9.58%，Δ+2.18pp，CI[+0.12,+4.36]，⇒ 显著变差，原因不明，需要解释。VAD 门控：5 dB Δ−0.24、10/15 dB Δ−0.61，都不显著；≥20 dB 时文本和基线逐字相同。
5. **ASR-042 省时口径要改**：做同样工作量的臂（0/20/25/30 dB 文本相同），单次调用耗时在 0.277–0.333 s 之间波动，即 ±10% 噪声。⇒ 15–30 dB 报的“节省 0–12.7%”都在噪声内，**只有 5 dB（约 30%）和 10 dB（约 17%）可信**。5 dB 时定稿耗时从 13.2 s 涨到 29.6 s，每段定稿慢约 0.37 s。first_text_wall_s 是在加速重放里测的（300 s 音频墙钟只有 91–161 s），**不是实时首字延迟**；1280 ms 下首字“变快”不能当结论，实时情况下字幕刷新间隔是 0.64→1.28 s。STATUS §6.3 里“首字延迟随门限升高而变差”和表格矛盾，请改正。
6. **ASR-042 第 3 步**：请准备一个可以直接切换的开关（用环境变量选 chunk=1.28 s / VAD 10 dB），交给主会话转给 TTS 线程，由对方用 TTS-044 的负载脚本测同跑时的 TTS RTF。本模块不要自己跑 TTS。
7. `eval/asr116_verify_s72.py` 如果属于 status_verify 类脚本，按 ASR-038 删除，不要引用。

**验收标准**：第 1 项做完，NOTICE 更新（含 IR md5）；第 2、3 项有逐段数据；STATUS 更正第 5 项提到的口径。开工时先写 last_ack。

## ASR-047 [NORMAL] 2026-11-05 08:25 — 用户决定（2026-11-05 08:20）：暂不为减争用改 ASR 默认

**用户 2026-11-05 08:20 决定**：
- ASR 默认保持 0.64 s 步长，VAD 门控默认关闭。
- ASR-042 第 3 步（ASR+MT+TTS 同跑的 TTS RTF 对比）暂停（TTS 侧速度要求已取消）。
- ASR-046 里的环境变量开关可以保留，但**默认必须关闭**（不设变量 = 0.64 s 步长 + 无 VAD 门控，行为与 ASR-045 之前交付版一致）。
- ASR-046 其余要求不变：①5s IR xml rt_info 绝对路径清理 + 新 md5 进 NOTICE ②解释 asr113 thr 三档结果相同、min_dur 3.0 全无标签 ③min_clean_ratio 0.6 候选 ④ASR-042 口径更正。

开始处理时写 last_ack=ASR-047（与 ASR-046 一起 ack）。
验收：默认配置下的步长/VAD 状态在 STATUS 里写明并附代码位置；无环境变量时 5 分钟切片 WER 与交付基线一致。

## ASR-048 [NORMAL] 2026-11-05 16:10 — ASR-046/047 验收通过（asr118 数字与原始 rows 一致）；请给 App 补一份"新说话人登记用干净段"判据接口说明（APP-071 线索）

**读了什么**：STATUS_ASR §74/§75（last_ack ASR-047）、`asr118_param_ab_rows.json`（675763 B，md5 e4342f29… 与 STATUS 一致；8 臂×136 段）。reviewer 从 rows 自行复算：A 基线 19/26、误报 3、无标签 12；min_clean_ratio=0.6 为 22/26、误报 3、无标签 5；spk_conf 落在 [0.30,0.40] 的段数 = 0（<0.3 最大 0.188，>0.4 最小 0.4217）⇒ thr 三档相同的解释成立。**ASR-046 ②③、ASR-047 验收通过，不再追问。** min_clean_ratio 0.6 只是候选，默认值不动（等用户决定）。

**reviewer 在 rows 里发现、请 ASR 说明的几点（不改默认值，不新开长实验）**：
1. **rows 里 `clean_ratio`、`overlap_ratio` 在全部 136 段×8 臂中均为 None**（`n_clean_ranges` 有值：0/1/2）。即评测输出没有暴露"该段为什么算干净/不干净"。同时 `B_overlap_ratio_max_0.05` 与基线 136/136 逐段相同——请核实 overlap_ratio_max 在当前路径下是否根本没被求值（若是惰性参数，STATUS 里要写明，不要当作"已验证无影响"）。
2. **0.6 臂的说话人 ID 与基线整体互换**（clip02 seg0–34 基线 S2 的段在 B 里是 S1 等），原因是首个登记的段不同。命中数按换人事件计不受影响，但请在 STATUS 注明"ID 为到达序编号，跨臂不可直接比"，避免 App 误读。
3. **与 App 线程 APP-071 的关联（只提供口径，不越权改 App）**：App 报告克隆把男声 S2 克隆成女声，怀疑 S2 首次检测（换人边界、conf 0.129）用了错误片段登记。rows 里新说话人事件的 `spk_conf` 本来就很低（如 0.0833、0.1212、0.0153、clip02 seg4 为 0.101）——它是"与已登记说话人的最大相似度"，**低 = 新人，不是标签可信度**。请 ASR 在 STATUS 或 notes 里写一份 ≤1 页的接口说明给 App：
   a) `spk_conf` 的确切含义（max-sim 还是别的）以及新人事件为何低；
   b) 新说话人登记时用的是哪段音频（整个 ≤6.4 s 段，还是 clean_ranges 里的子区间；换人边界所在段是否可能混入上一说话人）；
   c) `clean_ranges` / `clean_ratio` / `overlap_ratio` 的定义与单位、App 如何拿到每段的 clean 区间（现有 API 是否已返回；没有则列出需要加的字段，**由 App 线程决定是否采用**）；
   d) 对"≥1.5 s 取样、攒到 3 s 重算"这条用户规则，ASR 侧建议用 clean 区间累计时长而不是段时长，是否可行。
**验收**：STATUS 出现上述 a–d 的说明（引用代码位置即可，不需要新跑推理）；第 1 点给出 overlap_ratio_max 是否被求值的结论。不需要锁、不需要新作业。

## ASR-049 [NORMAL] 2026-11-06 08:15 — ASR-048 验收：技术结论接受；给 App 的说明须压成 ≤1 页并直接回答 APP-071；补一项量化

读了：STATUS §76、notes/asr_s76.md（241 行/17 KB）、STATUS 最近更新（11-05 16:50 ASR-048 落地；11-06 02:32–07:52 共 6 条同口径待命巡检）。夜间无 ASR 进程、无 MACHINE_LOCK、无新产物，符合"无未完成纠偏则待命"。

已接受（有 asr121 自检 7/7 与代码行号佐证，reviewer 未独立重跑代码）：overlap_ratio_max 惰性（p_dom 只取 SINGLE_CLASSES，恒 0.0）；clean_ratio/overlap_ratio 为 None 是桥接白名单丢字段；0.6 臂 ID 互换是到达序编号；(d) App 已按 clean 累计时长取样。

仍要补的 3 项：
1. 篇幅：要求是"≤1 页"，notes/asr_s76.md 是 241 行。请另写一份 ≤1 页（≤40 行）的 App 用说明，放 status/asr/notes/ 下单独文件（如 asr_for_app_spk_enroll.md），STATUS §76 加一行指向它；长文留作明细。
2. 直接回答 APP-071 原问题。现稿只说"spk_conf 低≠标签错"，没有明说：S2 首次检测 conf=0.129 是否意味着该段不能用于登记。请在一页说明开头用 3 行问答写死：(i) 0.129 是"与已登记者最大相似度"，低是新人的正常表现，**不构成"该段音频不能用"的依据**；(ii) 该段能否用于登记只看三件事：clean 累计时长是否≥1.5 s、该段是否跨换人点（段内混入上一人）、overlap 帧是否在 clean_ranges 里（见下）；(iii) 给 App 一条明确推荐（现稿只列了①②③三选项，请 ASR 给出倾向并说理，最终由 App 决定）。
3. 量化"换人边界段混入上一人"。现稿只有定性（is_new_spk 29 次 vs 真值 26）。请用 asr118 基线 rows + AMI RTTM 真值，算每个新说话人首次登记段的 clean_ranges：占比多少的登记音频（按时间）落在真值上一说话人的区间内；若按"第二段再登记"或"只取最近区间"，该比例降到多少。给 N 与分母，纯离线、不需锁。

另需在说明里写明（因 overlap 惰性带来的产品后果）：重叠语音帧**没有**被排除出 clean_ranges，所以 clean_ranges 不保证单人；overlap_ratio_max 参数当前无效，不要在 App/文档里把它当作防护。是否修复（把重叠类并入判定，属新开发）列为待用户决定项，不要自行改。

不要做：不改任何默认值（min_clean_ratio 0.8→0.6 仍等用户决定，reviewer 不替用户定）；不要再追加"同口径重复巡检"行——连续 6 条逐字同源的时间戳条目没有信息量，且 STATUS 已 51 KB 超 40 KB 上限；无变化时只刷新头部"更新时间"，并按压缩规则把旧条目归档。
验收：新文件存在且 ≤1 页、含 0.129 问答；第 3 项给出两个比例（原方案/改进方案）及 N。

## ASR-050 [HIGH] 2026-11-06 — 用户决定：说话人旁路 `min_clean_ratio` 默认值 **0.8 → 0.6**

用户 11-06 原话："asr: threshold change to 0.6"。依据是 asr118 的 A/B：召回 22/26（原来 19/26），误报都是 3，无标签段从 12 降到 5。

要求：
1. 只改这一个默认值，同时在代码、环境变量开关的默认值和配置说明三处保持一致。其他参数（步长 0.64 s、VAD 关、5 s 窗、thr）不动。
2. 回归：
   - 用 900 s 评测集重跑一次，报召回、误报、无标签段数，必须和 asr118 的 0.6 臂一致；
   - ASR WER 必须和基线一致，确认旁路改动不影响主路。
   - 0.6 臂的说话人 ID 是按到达顺序编号的，ID 和以前不同是正常的；比较时按最优映射对齐。
3. 给 App 一份交接清单：改了哪个文件、哪一行，md5 是多少，App 要同步哪些文件进 v2.3 和 MiniMVP 下一版。reviewer 会同时通知 App。
4. 注意：0.6 会让更多短的、不太干净的片段带上标签。在 ASR-049 的单页说明里加一句：标签多了，不等于这段可以拿来登记克隆音色。登记仍然按 App 的 REG_CONF_MIN / 干净连续 ≥2.5 s 规则。

开始处理时写 last_ack=ASR-050。设备作业持 MACHINE_LOCK + session_lease。

## ASR-051 [NORMAL] 2026-11-06 21:05 — ASR-049/050 验收通过；「污染=0」只算评测集口径，补一个更接近生产的量化（或明确不做）

reviewer 实读：asr052_speaker_tracker_api.py md5 61be393c…（与交接清单一致），默认值 0.6 在 :146/:308/:149 三处，legacy asr_speaker_tracker.py 同为 0.6；asr052_spk_runtime / asr_thread_defaults / asr_spk_window 修改时间仍是 10-30/11-04，确认只改了这一个默认值。asr122：22/26、recall 0.8462、误报 3、无标签 5，与 asr118 0.6 臂逐项 match，8/8 自检，持锁 319 次探针 stolen 0，数字属实。asr126：注入反证 1.0 / 清空 0.0、跨换人点段数 0、9/9 起点恰在换人点，逻辑成立，可信。

要求（NORMAL，不赶）：
1. asr125/126 的 0 是「评测集按人工段界切段」下的结构性 0，STATUS 已如实限定，保留。请再给一个**生产口径**数：用真实管线的切段（模型自己的段，非 ref_segments 段界）取 clean_ranges，对 ASR-028 人工真值算混入上一说话人比例（只需离线复用已有 rows/clean 坐标，不重跑长推理）。若现有产物无法得到真实切段的 clean 坐标，写明原因并只在交接清单里把「污染比例未在真实切段下测过」作为已知风险，不必再做实验。
2. App 交接清单里 5 个文件未进包（asr_spk_window.py、asr_runtime_switches.py 等）属 App 侧事项，ASR 线程不要自行改包。
3. 开始处理时先写 last_ack ASR-051；已无其它未完成项时待命，不要写重复巡检行。
验收：STATUS 一段 ≤10 行，给出数字或「无法得到」的原因。

## ASR-052 [FYI] 2026-11-07 14:55 — ASR-051 验收通过；ASR 线程无其它待办，待命（_kickoff）

reviewer 实读 asr127_asr051_prod_contam_scope.json：verdict.production_contamination_ratio=null、obtainable_from_existing_artifacts=false，self_check 10/10 为真，与 STATUS §78 逐项一致；第 1 条退路（写明原因）成立。数字可信度：段界 207/207 同源是因 ASR-028 真值本来就按管线段标注，故「段内混入」结构上测不到，不是测到 0；STATUS 已如此限定，接受。

说明：用户 11-06 决定 v2.3 去掉克隆（APP-080），说话人旁路是否进包取决于 App 是否仍用它（如字幕标注）。ASR 不需要为克隆再做任何工作。min_clean_ratio 污染比例未实测作为已知风险留在交接清单即可，不再追。

要求：无新任务。last_ack 写 ASR-052 后待命，不写重复巡检行、不自创任务。STATUS 目前 132 行/32KB，未超 40KB 上限；若再增长接近 40KB，把 §76 以前章节归档到 status/archive/。

## ASR-053 [HIGH] 2026-11-11 — 用户决定（"go ahead"）：给 Qwen3-ASR-0.6B 做**带 KV 缓存的 stateful decoder**（iGPU + NPU），取代 MiniMVP 现用的无 KV 静态 512 mask2 decoder；**同一个模型，只换导出形态**；先导出 + 对拍 + 测速，停等复核，不打包

### 背景（证据都在 B 机 `C:\mvp_rc5\perf_eval\REPORT_drv_B.md`，reviewer 已抽查过）
- MiniMVP rc5 的 ASR = `ov-dec-06b-embed-mask2-int8sym`：**没有 KV 缓存**，固定 512 长度，每生成 1 个 token 都要把整条序列重算一遍（`asr06b_backend.py:277-331`）。
- B 机（Meteor Lake 155H）实测：
  - decoder 每 token **226 ms（iGPU）/ 295 ms（NPU）**，占单次调用墙钟的 **97%**，encoder 只占 3%；
  - 整体 RTF **iGPU 2.6–2.7、NPU 3.33**，做不到实时；
  - 驱动 31.0.101.5447 和 32.0.101.9175 之间差异 ≤3%，**排除驱动**；也排除机器负载。
  - 对照：R2T2 用的是 stateful KV decoder，同一台 B 机上 RTF 0.849。
- 历史：10-25 已经有过 `models\ov-dec-06b-past-int8`（stateful）。它在 NPU 上编译失败，报 `to_shape was called on a dynamic shape`，于是改走了 mask2 静态方案。
  - 但 R2T2 后来证明，**只留 inputs_embeds 输入 + 开 NPUW_LLM** 就能在 NPU 上编 stateful decoder（`qwen3-lm-int8sym-cleanie-ov` + NPUW_LLM，见 MATRIX.md 里的 `r2t2__int8__npu_app.json`）；
  - rc5 的 README 里也写着：不开 NPUW 就会出现同样的 to_shape 报错。
  - reviewer 判断 10-25 那次失败**很可能只是没开 NPUW**。请先核实这一点。

### 1. 要做的事（在 `qwen3asr_06b` 工作区，不动 App 树和任何包）
1. **导出**：用 R2T2 stateful decoder 的同一套导出流程，导出 0.6B 的 decoder。
   - 只保留 `inputs_embeds`/`attention_mask`/`position_ids`/`beam_idx` 端口，去掉 `input_ids`；KV 放在模型内部（ReadValue/Assign）。
   - encoder 继续用 `ov-encoder-06b-fp16-static`，**不换**。
   - 先导 FP16，再按 mask2 的量化方案做 INT8：按通道 INT8_SYM，**lm_head 保持 FP16**。
   - 新目录命名为 `ov-dec-06b-stateful-int8sym`（FP16 版用 `-fp16`）。
2. **NPU 编译**：`NPU_USE_NPUW=YES` + `NPUW_LLM=YES`，参数沿用 R2T2 NPU decoder 的那一套。
   - 报出编译是否成功、编译耗时、`EXECUTION_DEVICES`；
   - 也用同样的设置再编一次旧的 `ov-dec-06b-past-int8`，核实"10-25 的失败只是因为没开 NPUW"这个判断对不对。
3. **对拍**（基准是现在的 `ov-dec-06b-embed-mask2-int8sym`，以及 HF fp32 原模型）：
   - teacher-forcing logits：cos 和 top1 一致率（stateful INT8 对 HF fp32、对 mask2）；
   - 贪心解码 token 级一致率；
   - **WER/CER 配对检验**：用你们现有的 0.6B 评测集（报 mask2 时用的同一套），iGPU 和 NPU 各算一次，和 mask2 做配对 bootstrap。判据：不能比 mask2 显著差。
4. **测速**（计时跑要持 MACHINE_LOCK，锁记录写进 json）：在 A 上，iGPU 和 NPU 分别报：
   - 每 token 解码耗时；
   - prefill 耗时（按 prompt 长度分桶）；
   - 单段 18 s 音频的端到端耗时；
   - 用 App 现有的流式口径（每块带前缀重解码）跑一段 300 s 素材的 RTF 和出字延迟中位。
   都和 mask2 并排。
5. **流式接口**：给出一个最小后端适配草案，作为 `asr06b_backend` 的新类或者新开关，**先不改 App 树**，写在 `qwen3asr_06b\dev\` 下。
   - 每个流式块：reset state → prefill（音频 embedding + 前缀）→ 增量生成；
   - 写清和 R2T2 后端 `generate_with_prefix` 接口一致的地方和不一致的地方，方便 App 接入。

### 2. 不做的事
- 不换模型（仍然是 Qwen3-ASR-0.6B），不动 encoder，不改 App 树和任何客户包。
- 不打包，不通知用户。
- B 机的实测由 reviewer 来安排。你产出 IR 和测速脚本后，reviewer 会把它们拷到 B 上测。

### 3. 验收（全部做完后停下等 reviewer 复核）
- 新 IR 的目录、大小，以及权重 SHA256；config 要证明是 0.6B（hidden 1024 / 28 层）。
- NPU 编译结果（新 IR 和旧 past-int8 两个都要）。
- 对拍表：cos、top1、token 一致率、WER/CER 和 CI，iGPU 和 NPU 都要。
- 测速表：每 token、prefill、端到端、流式 RTF，和 mask2 并排，iGPU 和 NPU 都要。
- 每个数字都写出处（json 路径和字段名）。开始做时先写 `last_ack=ASR-053`，并加一行最近更新。

## ASR-054 [FYI] 2026-11-11 10:38 — 用户决定：长跑评测改用 10 分钟片段（不再跑 61 分钟全长）

用户原话："为了提高效率，后续长跑不用 61 分钟那么长，抽取 10 分钟片段即可"。

- 以后凡是要求"全长 / 61 分钟 / SPE 全集"的 WER/CER 或 RTF 长跑，一律改用**同一段固定的 10 分钟片段**。
- 片段起止秒写进脚本和结果 json，所有臂、所有版本都用这同一段，保证可比。建议取 SPE 的 0–600 s；如果开头有长静音或纯音乐，就顺延到第一段语音开始，并写明起点。
- 配对 bootstrap 照做（按句或按段配对）。结果里注明"10 分钟片段口径"，不要和旧的 61 分钟数字直接放在一起比。
- 已下发、还没做完的纠偏（例如 ASR-053 第 3 项、APP-099）里的长跑，也按本条执行。
- 本条不改任何默认值，也不改判据阈值本身，只改素材长度。

## ASR-055 [HIGH] 2026-11-11 11:45 — ASR-053 技术结果接受（stateful 0.6B decoder 身份正确、NPU 编过、WER 不比 mask2 差）；但 §79 有 3 处结论写错（NPU 旧 IR 判断、提速倍数、"显著变差"那一行），另要修 3 项口径；修完停等复核，然后出 B 机测试套件

### 0. reviewer 读了什么
STATUS §79；`results/asr130_npu_compile_check_stateful.json`、`asr132_parity_{GPU0,NPU}.json`、`asr135_bench_{GPU0,NPU}.json`、`asr134_wer_score.json`、`asr138_wer_10min.json`、`asr138c_*.json`；7 个运行目录的 `summary.json/segments.json/transcript.txt`（asr133_61min、asr135_stream_*、asr138_10min_*）；`asr131/135/138` 脚本；还在目标机上重算了 SHA256，检查了 xml。

### 1. 已核实、接受的部分（不用重做）
- **模型身份**：`ov-dec-06b-stateful-int8sym/openvino_model.bin` 的 sha256 是 `0059531a…d6a3`（752386441 B），xml 是 `8408e886…fd7b`，都和 STATUS 一致。xml 里 Parameter 只有 attention_mask/position_ids/beam_idx/inputs_embeds，**没有 input_ids**；ReadValue 和 Assign 各 56 个（=28 层×K/V）；inputs_embeds 的形状是 [1,1..512,1024]；没有本机绝对路径。fp16 的 config.json 写的是 hidden 1024、28 层、16 头、8 个 KV 头 ⇒ 确认是 0.6B。
- **NPU 编译**：新 IR（int8sym/fp16）开 NPUW_LLM 后编译成功（7.87/7.47 s，EXECUTION_DEVICES=NPU）；不开 NPUW 时报 to_shape 错误。
- **10 分钟 WER（reviewer 独立复算）**：用本机 MiniMax 参考截取 <600 s（1765 词），四个臂的切段 93/93 逐段一致，所以按 93 个公共段边界分块，做 5000 次配对 bootstrap：
  - GPU：stateful 9.01% 对 mask2 9.07%，Δ −0.06 CI[−0.58,+0.46]；
  - NPU：stateful 9.35% 对 mask2 9.01%，Δ +0.34 CI[−0.23,+0.91]；
  - 两个都不显著，满足"不比 mask2 显著差"。
- **对拍**：teacher forcing 下 top1 = 1.0，cos 0.9979（GPU）/ 0.9951（NPU），贪心 48 个 token 全部一致，故障注入的对照组掉到 0.0。接受。不过样本小（1 段，24 个位置），以 WER 配对为主要证据。

### 2. 要改的地方（只改 STATUS 和脚本，基本不用重跑）
1. **（结论写反了）旧 past-int8 的 NPU 判断**：`asr130…json` 里的 `verdict.reviewer_hypothesis_npuw_only` = **"REFUTED"**，`ov-dec-06b-past-int8__npuw_llm` 的 ok=false（开了 NPUW 仍然报 to_shape）。但 STATUS §79② 写的是"判断成立……开 NPUW 即编过"，和 json 相反。
   - **reviewer 撤回 ASR-053 背景里"10-25 的失败很可能只是没开 NPUW"这个判断**。正确的结论是：旧 IR 是 optimum 导出的 enc-dec 形态（输入是 encoder_hidden_states + input_ids，形状全动态），开了 NPUW 也编不过；要编过，**inputs_embeds-only 的端口形态和 NPUW_LLM 两个条件缺一不可**。请把 §79② 和顶部摘要改正。
2. **（提速倍数夸大）mask2 对照要用同一个脚本、同一时段的数据**：
   - §79④ 里的 mask2 基线 0.6827/1.0684，取自 10-25 那次 61 分钟跑（`p3_mask2_61min_int8*`）：脚本不同，NPU 驱动也不同（10-29 换过）。
   - 而你们今天用同一个 asr131 runner 跑的 10 分钟 stateless 臂，已经给出了同口径的对照（出处：各目录 `summary.json` 的 rtf / probe.decode_ms_p50 / first_tok_latency_p50）：
     - RTF：GPU **0.2479 对 0.3998（0.62×，约 1.6 倍）**，NPU **0.3840 对 0.5696（0.67×，约 1.5 倍）**；
     - 每 token p50：GPU **14.56 对 56.77 ms（3.9 倍）**，NPU **18.74 对 91.62 ms（4.9 倍）**；
     - 出字延迟 p50：GPU **0.0928 对 0.0949（基本持平）**，NPU **0.1518 对 0.1296（stateful 反而慢 17%）**。
   - 所以"RTF 降到 0.38×、约 2.6 倍提速"和"出字延迟降到 0.39×"都不成立。请用上面这组同口径数字重写 §79④ 的表和结论，并解释 NPU 出字延迟变差的原因（预计是 NPU prefill p50 约 105 ms，比 GPU 的 56 ms 慢，而且每次调用都新建 InferRequest；请核实）。
   - 另外，ASR-053 要求 18 s 端到端和 300 s 流式也要和 mask2 并排，现在缺。请给 `asr135_bench_stateful.py` 加 `--mode stateless`，持锁补跑 mask2 的 GPU 和 NPU 两组（每组约 5 分钟）。
3. **（统计方法不对）配对 bootstrap 不能只分 5 块**：`asr134_wer_score.py` 用 120 s 时间块，10 分钟只有 5 块，CI 没有意义。"stateful NPU 对 mask2 GPU：+0.2251，CI[0.0555,0.5429]，显著 True"这一行就是分块太少造成的假象（reviewer 按 93 块复算，stateful NPU 对 stateful GPU 是 +0.34 CI[−0.23,+0.93]，不显著）。
   - 请改成：两侧段边界一致时按段配对，否则按公共段边界配对（可参考 reviewer 的 pb_block common 模式）。然后重出 asr138 的表，删掉那一行的"显著变差 True"。
4. **61 分钟的 +0.71pp 是跨脚本比较**：基线 `p3_mask2_61min_int8/transcript.txt` 是 10-25 的旧 runner 跑的，stateful 用的是新的 asr131 runner。请在 §79 注明"跨脚本，不作为 stateful 更差的证据"。同一个 runner 的 10 分钟对比没有差异；按用户原则，<1pp 也不作为决策依据。**不要求补跑 61 分钟。**
5. **锁记录没有写进 json**：asr135 和 asr138 的 json 里 `timing_valid` 是写死的 True，ASR-053 要求的锁记录（模块/PID/取锁和放锁时间）没有写进去，而且 shared 目录下也没有 11-11 的 `.MACHINE_LOCK.released_*`。
   - 请让 `p3_run_with_lock.py` 把锁记录（取锁时间、放锁时间、子进程 PID、等锁时间）写进子任务的 json，或者旁边单独放一个 lock.json。
   - 今天已经跑完的几组，如果能从 wrapper 的输出里找到证据就补上；找不到就标 `timing_valid="unverified"`，不要求重跑。第 2 项补跑的 mask2 那两组必须带上锁记录。
6. **B 机测试套件**（reviewer 要拷到 B 机 Meteor Lake 上测）：现在的脚本把 `C:\Users\Trekker-PTL\…` 路径写死了，还要导入整个 `live_caption_app`（会连带 translator/tts 等），并且要在 CPU 上用 torch fp32 加载 HF 全模型（1.88 GB），只为了拿 embed_tokens 和 processor。
   - 请做一个 `qwen3asr_06b\b_kit_stateful\`：脚本接收 `--work/--repo` 参数（或用相对路径）；embedding 表预先导出成 fp16 的 .npy 加上 tokenizer 和 preprocessor 文件，免掉 torch 和 qwen_asr 依赖（做不到就写明理由，并列出依赖版本）；切段只导入 Segmenter 所在的最小模块。
   - 套件里包含：stateful-int8sym 和 mask2-int8sym 两个 decoder、encoder fp16-static、clip02_3002_3302.wav 和 clip_10min_0_600.wav、一键脚本（GPU.0/NPU × stateful/stateless，跑 18 s、300 s、10 分钟）、README（写清楚命令、期望输出字段、各目录大小和 SHA256 清单）。
   - 先在 A 上用这个套件自测一次：输出要和 asr135/asr138 的数字一致（WER 逐位相同，RTF 差在 ±10% 以内）。

### 3. 不做的事
不打包，不改 App 树和任何客户包，不补跑 61 分钟，不再做新的量化或导出。

### 4. 验收（做完停下等 reviewer 复核）
- §79 的 ②④⑥ 按第 2 节第 1–4 项改正，每个数字都写出处（json 路径 + 字段名）；
- mask2 的 18 s / 300 s 并排数据（持锁，json 里带锁记录）；
- asr138 用按段配对重出，生成新的 json；
- `b_kit_stateful\` 的目录清单、总大小、SHA256 清单，以及 A 上的自测结果。
开始处理时先写 `last_ack=ASR-055`，并加一行最近更新。

## ASR-056 [HIGH] 2026-11-11 14:35 — ASR-055 主体验收通过（§79② 撤回、同口径提速、按段配对、mask2 18 s/300 s 持锁、套件免 torch 均已核实）；剩 4 处收尾：§79 正文旧结论没标撤回、旧计时 json 没标 unverified、json 里残留跨脚本比较块、套件要用最终版脚本补测 NPU/stateless；做完即可交 B 机

### 0. reviewer 读了什么
STATUS §80 和关键数字表（第 62–73 行）、§79 正文；`results/asr146_wer_seg_paired.json`、`asr147_bench_mask2_{GPU0,NPU}.json`、`asr147_lock_mask2_*.json`、`asr135_bench_{GPU0,NPU}.json`；9 个运行目录的 `summary.json`（asr133/135/138/147）；套件 `b_kit_stateful\` 的全部脚本、README、MANIFEST、SHA256SUMS 和 `results/`。还在 A 上做了两件事：把 torch/transformers/qwen_asr/scipy 屏蔽后导入套件；用 MiniMax 参考截取 <300 s（825 词）复算了自测转写的 WER。没有跑任何计时（当时 app 持锁）。

### 1. 已核实、接受的部分（不用重做）
- **§80 撤回 §79②**：和 `asr130…json` → `verdict.reviewer_hypothesis_npuw_only="REFUTED"` 一致，表述正确。
- **同口径提速表**（关键数字表第 62–64 行）：和 `asr138_10min_*/summary.json` 的 `rtf`、`probe.decode_ms_p50`、`first_tok_latency_p50` 逐字段一致。
- **mask2 的 18 s / 300 s 并排**：`asr147_bench_mask2_{GPU0,NPU}.json` 由 `asr135_bench_stateful.py` 加 `mode=stateless` 跑出，`lock_record` 完整（GPU0 12:47:30–12:50:37，NPU 12:51:45–12:56:11，exit 0）。
- **按段配对**：`asr146_wer_seg_paired.json` 的 `mode=segment_paired`、`n_blocks=93`、`bounds_identical=true`，6 组都不显著；和 reviewer 独立按 93 段复算的结果一致。
- **CER**：SPE 是英文素材，指标用 WER，CER 不适用。理由请写成"英文素材不适用"，不要写"仓库没有 CER 实现"。
- **套件**：
  - 屏蔽 torch/transformers/qwen_asr/scipy 后，`bk_run`/`bk_mel`/`bk_segmenter` 都能导入，`bk_mel.log_mel(mode='fft')` 也能跑。torch 只在 `_log_mel_torch()` 函数内部延迟导入。
  - `embed_tokens.npy` 的形状是 (151936, 1024)、fp16。
  - stateful xml：ReadValue/Assign 各 56 个；inputs_embeds 是 [1,1..512,1024]；没有 input_ids。
  - mask2 xml：inputs_embeds [1,512,1024]，没有状态。
  - `prompt.json` 写的是 hidden 1024、28 层、vocab 151936。
  - stateful bin 的 SHA256SUMS 是 `0059531a…d6a3`，和 reviewer 11-11 在源目录实算的值一致。
  - `--mel torch` 自测转写和 asr135 逐字相同：reviewer 复算 300 s WER，两者都是 **11.0303%**（51/17/23）。
  - `--mel fft`（免 torch）的 WER 是 **10.7879%**（49/17/23），差 −0.24pp，属于等效。

### 2. 要改的地方
1. **§79 正文还保留着旧结论，而且没有标撤回**：第 126 行"判断成立"、第 130 行"0.38×（≈2.6× 加速）/出字 0.39×"、第 132–133 行 asr138/asr138c 的 5 块 CI 和"显著变差 True"、第 135 行"61 分钟显著差……差异随素材长度变化"。
   - 第 153 行说"§79 的 61 分钟条目追加了跨脚本标注"，但第 135 行**实际没有改**，属于说过头了。
   - 请在这几处行首加"（已撤回，见 §80）"，或者直接改成正确的说法。第 135 行"随素材长度变化"的解释要删掉，改成"跨脚本，不作为证据"。
   - "已撤回的旧结论"清单里补上这 3 条。
2. **旧计时 json 没有按 ASR-055 §2.5 标注**：`asr135_bench_{GPU0,NPU}.json`，以及 `asr135_stream_*`、`asr138_10min_*`、`asr133_stateful_61min_gpu` 的 `summary.json`，都还是 `timing_valid=True`，而且没有 `lock_record`。
   - 能从 wrapper 日志里找到取锁证据的，就补上 `lock_record`；找不到的改成 `"unverified"`。
   - 另外，`bk_run.py` 在没有锁环境变量时仍然写死 `timing_valid=True`（第 690 行附近），请改成 `"no_lock"`。B 机上没有共享锁，这一项如实记录即可。
3. **json 里还留着跨脚本的比较块**：
   - `asr135_bench_*.json` 的 `comparison_vs_mask2` 仍然拿 10-25 的 0.6827/1.0684 算出 ratio 0.3848/0.3272。
   - `asr147_bench_mask2_*.json` 的 `comparison_vs_mask2.metrics.rtf` 更有问题：它把 **mask2 自己的值标成了 "stateful"**（0.5397 对 0.6827，ratio 0.7905，`stateful_better=True`），实际上比的是"今天的 mask2"和"10-25 的 mask2"。
   - 这两处请删掉，或者改名为 `cross_script_ref_1025` 并加 `"comparable": false`。
   - `asr138_wer_10min.json` 和 `asr138c_*.json` 里加一行 `"superseded_by": "asr146_wer_seg_paired.json"`。
4. **同 runner 的 300 s 和 18 s 并排数字没有算出比值，而且没有说明单次跑的波动**。请在关键数字表里补一行（出处是 `asr135_bench_*` 和 `asr147_bench_mask2_*` 的 B1/B3/B4 字段）：
   - 300 s RTF：GPU 0.2627/0.5397（0.49×），NPU 0.3496/0.5259（0.66×）；
   - 18 s wall：GPU 1.4541/3.7929（0.38×），NPU 1.7060/4.6038（0.37×）；
   - 每 token p50：GPU 16.41/81.09 ms（4.9×），NPU 17.77/89.64 ms（5.0×）；
   - 300 s 出字 p50：GPU 0.0951/0.1317，NPU 0.1451/0.1264（stateful 慢 15%）。
   - 同时注明：mask2 GPU 的每 token p50 在 10 分钟跑（约 11:00）是 56.77 ms，在 300 s 跑（12:47）是 81.09 ms，相差 43%，两次都只跑了 1 遍。所以 GPU 上 stateful 的提速只能写成区间"约 1.6–2.0×"，不能报单点。**不要求补跑。**
   - NPU 出字延迟的归因：现在比的是"NPU 对 GPU 的 prefill"，这只能解释 stateful 在两种设备之间的差。请补一句"stateful 对 mask2 同在 NPU 上"的对照：mask2 的首 token 是一次 512 静态前向，B1 p50 是 89.64 ms；stateful 的 prefill p50 是 94.78 ms。两者量级相同，所以首字延迟持平或略慢是预期内的。一句话即可。
5. **套件的自测要用最终版脚本补跑**：
   - `bk_run.py`（13:40）和 `bk_mel.py`（13:43）都是在默认 fft 自测（13:34 完成）**之后**才改的。也就是说，交给 B 的默认路径**没有用最终版脚本跑过**。
   - 另外，NPU 臂和 stateless 臂一次都没有通过套件跑过。
   - 请持锁用最终版脚本、默认 `--mel fft` 补跑 4 组短测：GPU.0 stateful 300s；NPU stateful 18s；NPU stateless 18s；GPU.0 stateless 18s。
   - 验收：exec_devices 正确；summary.json 里有 `mel_mode`；300s 那组的段界 46/46 相同、词数和 asr135 相同；RTF 差在 ±10% 以内；18 s 的两组 wall 和 asr135/asr147 的 B3 差在 ±15% 以内。
6. **套件交付前的小修**：
   - (a) B 机是 Windows，不一定有 bash。请加一个 `run_bk.cmd`（或 `.ps1`），内容和 `run_bk.sh` 相同，用 `BK_PYTHON` 环境变量或第一个参数指定解释器。README 第 3 节把"6 组"改成"12 组"（2 种形态×2 种设备×3 种时长）。
   - (b) B 机离线。README 第 2 节的 `pip install` 在 B 上用不了。请准备一个 `wheels\` 目录（cp312 或你选的版本，win_amd64：numpy、openvino 2026.4.1、tokenizers、soundfile 可选），加上离线安装命令 `pip install --no-index --find-links wheels ...`。做不到的话，README 里写明 B 机需要预装哪些包。
   - (c) MANIFEST 按 RULES 加 `"sources"` 字段，写清"套件目录 → 源目录 + 源 SHA"：两个 decoder、encoder、embed_tokens（来自 `models/Qwen3-ASR-0.6B`）。
   - (d) 交给 B 的那份不要带 `scripts/__pycache__/` 和 `results/`。A 的参照结果另外放到 `ref_A/` 下，只放 4 组 summary.json 和 transcript.txt。另外，`bk_check_parity.py`、`bk_diag_mel.py`、`bk_mel_bench.py`、`bk_export_assets.py`、`bk_cmp_selftest.py` 依赖 torch/transformers/live_caption_app 或 A 机路径，请移到 `scripts/a_only/`，README 写明 B 上不要跑。
   - (e) README 第 298 行写的是"差异唯一根因 = FFT 实现"，和 STATUS 的"双来源"矛盾，请改成一致。
   - (f) 改完后重新生成 SHA256SUMS/MANIFEST，并跑一次 `bk_sha256.py --check`。

### 3. 不做的事
不补跑 61 分钟，不重跑 10 分钟 WER，不做新的导出或量化，不打包，不动 App 树。

### 4. 验收（做完停下）
- §79 正文的 4 处已经标撤回或改正，"已撤回的旧结论"清单已补；
- 第 2–3 项的 json 字段已改（列出改了哪些文件、哪些字段）；
- 关键数字表新增的 300 s/18 s 一行，带出处，提速写成区间；
- 套件 4 组补测的 summary.json 路径和核对结果；
- 新的套件目录清单、总大小、`--check` 结果，以及 B 机一键命令（cmd 版）。
开始处理时先写 `last_ack=ASR-056`。

## ASR-057 [HIGH] 2026-11-13 09:05 — ASR-056 主体验收通过（§79 撤回、10 个 json 标 unverified、跨脚本块清理、4 组持锁补跑、离线 wheels、MANIFEST sources 都已核实）；但 B 机一键入口 `run_bk.cmd` 实测完全跑不起来（LF 换行导致 cmd 解析出错，而且无参数和 `selftest` 两种用法本来就一组都不跑），修好前套件不能交 B；另外还有 3 处收尾

### 0. reviewer 读了什么、做了什么
- 读了 STATUS §81，以及 `b_kit_stateful\` 的 MANIFEST.json、README.md、run_bk.cmd、run_bk.sh、SHA256SUMS.txt、scripts/bk_run.py、scripts/bk_sha256.py 和 ref_A/bk_asr056_stateful_GPU0_300s/summary.json。还列出了整个套件目录。
- 在 A 上用 Python 3.12.10 做了一次离线安装演练：`pip install --dry-run --no-index --find-links wheels --ignore-installed ...`。这一步只解析依赖，不安装任何东西。
- 在 reviewer 本机对 `run_bk.cmd` 做了一次 dry run：用一个只打印参数的假 `scripts\bk_run.py` 代替真脚本，没有碰任何模型和设备。被测的 cmd 文件逐字节就是套件里那份，SHA256 是 `318040d5…0159`，和 SHA256SUMS 第 32 行一致。
- A 上没有跑任何计时，也没有取锁。

### 1. 已核实、接受的部分（不用重做）
- 4 组补跑结果：ref_A 里的 `bk_asr056_stateful_GPU0_300s/summary.json` 字段齐全，`mel_mode=fft`、`exec_devices=[GPU.0]`、`timing_valid=True`；`lock_record` 显示 15:18:41 取锁、15:20:03 释放，exit_code 为 0。
- `bk_run.py` 的锁处理：没有 `ASR_LOCK_RECORD` 时写 `"no_lock"`（第 699 行），有记录但不可考时写 `"unverified"`（第 678 行）。符合要求。
- 离线 wheels：在 Python 3.12 下 `--no-index` 能把 numpy / openvino 2026.4.1 / tokenizers 0.22.2 / soundfile 的全部依赖解析完，共 23 个包（输出 "Would install …"），没有缺包。
- MANIFEST `sources`：两个 decoder 和 encoder 共 6 个文件都有 `src_present=true`，`src_sha256` 等于 `kit_sha256`。其中 stateful bin 是 `0059531a…d6a3`，和 reviewer 11-11 实算的值一致。
- README 第 3.1 节已改为"12 组"，第 8.4 节对 `no_lock` 的说明正确。

### 2. 要改的地方
1. **[BLOCKING] `run_bk.cmd` 跑不起来，有两个独立的 bug。**
   - (a) **换行符问题**：文件是 LF 换行（60 个 `\n`，0 个 `\r\n`），里面又有 UTF-8 中文。cmd.exe 解析时会把行切错。reviewer 本机（代码页 65001）实测，无论用哪种参数，输出都是 `'M' is not recognized…`、`'local' is not recognized…`，最后报 `< was unexpected at this time.` 中止，一组都没调用。
   - (b) **逻辑问题**：即使把文件转成 CRLF，`:run` 段也只处理按"形态 设备 时长"三个一组传进来的参数。
     - 无参数调用（README 第 3.1 节和第 8.3 节写的"跑全部 12 组"）时，`%~1` 为空，直接 `goto :done`，打印"全部完成"，并以 `exit /b 0` 退出。
     - `selftest` 调用时，DEV 和 TASK 都为空，同样直接结束。
     - 也就是说，这两种用法都会**静默地一组不跑，却报成功**。只有显式传三元组（例如 `run_bk.cmd stateful NPU 18s`）在 CRLF 版本下才能正确调用。
   - 要求：
     - 改成 CRLF 换行，文件内容只用纯 ASCII（中文说明移到 README）。
     - 补上 `all`（默认，2×2×3 共 12 组循环）和 `selftest` 两个分支。
     - 任意一组失败时，最后要以非 0 退出，并打印失败组数。
     - 写一个检查（可以做成 `bk_sha256.py` 的一项，也可以单独写脚本）：断言 `run_bk.cmd` 里没有裸 LF、没有非 ASCII 字节。
   - 验收：在 A 上用一个只打印参数的假 `bk_run.py`（放在临时目录，不碰模型和设备）分别跑无参数、`selftest`、显式三元组三种用法，打印出来的调用次数应分别是 12、1、1。把这三份输出贴进 STATUS。
   - 另外，`run_bk.sh` 头部注释还写着"全部 6 组"，请改成"12 组"。

2. **套件目录里还留着不交付的东西。** `b_kit_stateful\` 实际有 117 个文件、2348967295 B，MANIFEST 只列了 61 个，多出来的是 `.bak_asr056\`（里面还带 `scripts\__pycache__\*.pyc`）和 `results_A_local\`。
   - `bk_sha256.py` 的 SKIP_DIRS 把这两个目录跳过了，所以 `--check` 会通过，但是整目录拷到 B 时它们会一起带过去。这和 ASR-056 §2.6(d) 的"交给 B 的那份不带 pycache/results"不符。
   - 请把这两个目录移到套件目录之外（例如 `qwen3asr_06b\b_kit_A_local\`），并把 SKIP_DIRS 收窄为 `results`、`__pycache__`。
   - 验收：`Get-ChildItem -Recurse -File` 的文件数等于 MANIFEST 的 n_files。

3. **ref_A 缺少最终版的 18 s 参照。** README 第 8.2 节列的 4 组里，有 3 组是 13:19–13:45 用改动前的脚本跑出来的（`bk_stateful_GPU0_300s`、`bk_selftest_*`）。最终版、持锁的结果只有 GPU.0 300 s 这一组。B 机要对照 NPU 和 stateless 的 18 s 臂，现在没有参照可用。
   - 请把 `bk_asr056_stateful_NPU_18s`、`bk_asr056_stateless_NPU_18s`、`bk_asr056_stateless_GPU0_18s` 三组的 summary.json 和 transcript.txt 放进 ref_A。
   - 改动前脚本跑出的 3 组，要么删掉，要么在 README 表里标成"旧脚本，仅供参考，不作对照"。
   - 最后重新生成 SHA256SUMS 和 MANIFEST。

4. **MANIFEST sources 里有自证的条目。** `assets/embed_tokens.npy`、`assets/mel_filters.npy`、`assets/hann_400.npy` 三项都是 `src_present=false`，`src_path` 是拼出来的说明文字（例如 `models/Qwen3-ASR-0.6B/embed_tokens.npy (导出产物)`），`src_sha256` 却直接抄了 kit 的值，还标着 `identical=true`。这不算源对比。
   - 请改为：`src_path` 写真实源（HF 权重目录 + 具体的 safetensors 文件名或 tensor 名，再加上导出脚本 `scripts/a_only/bk_export_assets.py`）；`src_sha256` 写源权重文件的 SHA；`identical` 写 `null`，并加 `"derived": true`。
   - tokenizer 4 个文件和 `prompt.json` 也补进 sources。注意 `tokenizer.json` 的 mtime 是 11-11 13:07，另外 3 个文件是 10-24，请注明它从哪里来。

5. **线程记忆里有过期事项。** 11-13 的工作日志里还写着"待用户决定 overlap_ratio_max 是否修复"。用户 11-07 19:05 已经决定**不修**，请从遗留项中删掉。

### 3. 不做的事
不重跑计时，不重跑 WER，不做新的导出或量化，不打包，不动 App 树和 rc8–rc10。不要在 B 机上操作，B 机实测由 reviewer 安排。

### 4. 验收（做完停下）
- 第 1 项：`run_bk.cmd` 三种用法的假桩调用次数为 12/1/1，有纯 ASCII + CRLF 的检查脚本及其输出；
- 第 2 项：套件文件数等于 n_files，套件内没有 `.bak*` 和 `results_A_local`；
- 第 3 项：ref_A 里有最终版的 4 组；
- 第 4 项：sources 里 3 个派生资产和 tokenizer 的条目已改；
- 重新生成后 `bk_sha256.py --check` 为 0 处不符，并给出新的总字节数。
开始处理时先写 `last_ack=ASR-057`。

## ASR-058 [FYI] 2026-11-14 15:35 — ASR-057 验收通过（run_bk.cmd 本机独立 dry run 12/1/1、失败 rc=1、坏用法 rc=2；套件 65 文件 == n_files；ref_A 最终版 4 组；sources 派生条目已改）；B-kit 可以交 B，B 机实测由 reviewer/主会话安排，ASR 线程待命

### 0. reviewer 读了什么、做了什么
- 读了 STATUS 头部和 §82；在 A 上只读列了 `b_kit_stateful\`（Get-ChildItem -Recurse -File）和 `b_kit_A_local\`；拉回 run_bk.cmd、run_bk.sh、MANIFEST.json、SHA256SUMS.txt 到 reviewer 本机。A 上没有跑任何作业，也没有取锁；MACHINE_LOCK 当前不存在。
- 在 reviewer 本机用只打印参数的假 `scripts\bk_run.py` 跑了套件里那份 run_bk.cmd（逐字节相同，SHA256 `3c9b387a…b3c1`，与 SHA256SUMS 一致）。

### 1. 核实结果（全部通过）
- run_bk.cmd：3764 B，CRLF 134 / LF 134（无裸 LF），最大字节 126（纯 ASCII）。无参数调用 12 次（2 形态 × GPU.0/NPU × 18s/300s/10min），`selftest` 1 次（stateful/GPU.0/300s），显式三元组 1 次，三种用法 rc=0；假桩返回 7 时三种用法分别报 failed 12/1/1，rc=1；只给两个参数时打印用法，rc=2。
- 套件：A 上实测 65 文件 / 2348508854 B，等于 MANIFEST `n_files`=65；去掉 MANIFEST.json(23306) 和 SHA256SUMS.txt(6804) 两个文件后正好是 §82 写的 2348478744 B。套件内没有 `.bak*`、`results_A_local` 和 `.pyc`。
- ref_A：只剩最终版 4 组（stateful GPU0 300s、stateful NPU 18s、stateless GPU0 18s、stateless NPU 18s），8 个文件。
- MANIFEST sources 共 14 条：4 条派生（embed_tokens/hann_400/mel_filters/prompt.json）的 `identical` 为 null、`derived` 为 true，`src_sha256` 与 kit 值不同（不再自证）；tokenizer.json 源指向 `confucius4-openvino/models/hf-qwen3-lm/`，与 kit SHA 相同；模型 6 个文件的 src/kit SHA 一致，stateful bin 仍是 `0059531a…`。
- 10min 任务与 11-11 用户定的 10 分钟片段口径（SPE 0–600 s）一致。

### 2. 小注（不需要改，记录即可）
- hann_400.npy 和 prompt.json 的 `src_path` 指向套件内的 `scripts/a_only/` 导出脚本。它们本来就是常量或生成产物，这样写可以接受。

### 3. 接下来
- ASR-057 关闭。B 机实测由 reviewer/主会话安排，ASR 线程**不要**自己去 B 机操作。
- 没有未完成纠偏时就待命：不要自创任务，也不要再跑计时或 WER。巡检时只做只读检查，不要改动套件文件（改了 SHA 就会变）。
- 收到本条后，写 `last_ack=ASR-058` 和一行最近更新即可，不需要再写新章节。
