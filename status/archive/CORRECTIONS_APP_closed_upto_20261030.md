# CORRECTIONS_APP —— 已完成/已关闭条目归档（截至 20261030）
> 🔴 **只读归档**：本文件由 `status/app/CORRECTIONS_APP.md` 派生，**不替代**原文件。
> 原文件仍是 reviewer 独占写入的活文件（编号与标题格式不变，reviewer 的推送工具继续往末尾追加）。
> 全量原文备份见 `CORRECTIONS_APP_full_before_compress_20261030.md`。

## 索引表
| 编号 | 一句话 | 状态 |
|---|---|---|
| APP-001 | 模式切换启动单：App 模块改用独立流程与独立 STATUS | 已完成 |
| APP-002 | 默认翻译模型改为 Hy-MT2 INT8-CW | 已完成 |
| APP-003 | 客户包 results/ 含内部会议转写，不得进包 | 已关闭 |
| APP-004 | C-111 交给 App 模块；TTS 模型文件随客户包分发 | 已完成 |
| APP-005 | 内部会议转写被提交推送到 GitHub；pack_v13 仍把内部目录进包 | 已关闭 |
| APP-006 | 改写 git 历史彻底删除内部会议转写并强推 | 已关闭 |
| APP-007 | 复核 APP-006② 清单：有条件通过 | 已关闭 |
| APP-008 | 跨模块转达：v1.4 新切段规则未验证质量 | 已完成 |
| APP-009 | 接受 APP-007 全部条件，开始改写 git 历史 | 已关闭 |
| APP-010 | 用户抽听判定 TTS 音质不合格（杂音/音色突变/重复词） | 已完成 |
| APP-011 | 复核 APP-007/009：改写通过但二次改写有必要 | 已关闭 |
| APP-012 | MT 半句方案采用 C；实时路径切点导致重复词 | 已完成 |
| APP-013 | 会议记录相关事项不再跟踪，撤销二次改写 | 已关闭 |
| APP-014 | TTS 改为正式功能；先修实时路径切点重复词再打包 | 已完成 |
| APP-015 | MT 半句方案 C 确认（草稿只显示在字幕上） | 已完成 |
| APP-016 | Qwen3-ASR-0.6B 只作实验，不进 App 和客户包 | 已完成 |
| APP-017 | RESUME：额度已重置，从 last_ack 继续 | 已完成 |
| APP-018 | v1.5 包审查：SHA 与内部素材扫描通过，检查点 3 是最大缺口 | 已完成 |
| APP-019 | v1.5 包大小（约 10.45 GiB）可接受 | 已完成 |
| APP-020 | TTS 的 cp_prefill 也要挪到 NPU | 已完成 |
| APP-021 | 离线朗读「听不到声音」：played≠出声，判据无效 | 已完成 |
| APP-022 | 预告新功能：pyannote 强制断句 + 按说话人切换克隆音色 | 已完成 |
| APP-023 | 用户从桌面快捷方式实测：TTS CUDA/NPU 两条路径均异常 | 已完成 |
| APP-024 | §49.7 裁定：两方案都不采纳，BACKLOG_MAX_S 保持 8 | 已完成 |
| APP-025 | 补充 APP-023：用户界面原话与修改要求 | 已完成 |
| APP-026 | 不再跑 61 分钟长跑，统一用 SPE 前 5 分钟切片 | 已完成 |
| APP-027 | APP-023 L4：两后端能出声，但 NPU 卡顿 / CUDA 全丢 | 已完成 |
| APP-028 | 默认设备摆放；TTS 连续推理加内存缓存，取消丢句 | 已完成 |
| APP-029 | pyannote 只做说话人识别，不再断句 | 已完成 |
| APP-030 | 日文「卡住」=生成不收尾撞 2048 帧上限 | 已完成 |
| APP-031 | 优先级提醒：先做 APP-030，再做 APP-028/027 实测 | 已完成 |
| APP-032 | RESUME：额度已重置，从 last_ack 继续 | 已完成 |
| APP-033 | 回应 STATUS 头部阻塞③ / CUDA 组 | 已完成 |
| APP-034 | 用户决定方案 A（TTS 不等 spk） | 已完成 |
| APP-035 | FTP 已永久关闭：不得重发 v1.6、不得运行发布脚本 | 已完成 |
| APP-036 | 语音滞后主因不是 TTS RTF 而是排队/调度 | 已完成 |
| APP-037 | APP-030 复核：CUDA/NPU 引擎级 cap/hang=0 已核实 | 已完成 |
| APP-038 | 目标机 NPU 驱动已升级到 32.0.201.14005 | 已完成 |
| APP-039 | 音色要按句绑定原说话人，换人时一次性克隆 | 已完成 |
| APP-040 | APP-039 细化：用 pyannote 检测换人并绑定音色 | 已完成 |
| APP-041 | 启动时「语音输出」默认开启但未初始化设备 | 已完成 |
| APP-042 | 滞后追赶采用自适应加速播放（App 与插件统一） | 已完成 |
| APP-043 | ASR 说话人接口已交付（ASR-029），APP-039/040 克隆资产可取 | 进行中 |
| APP-044 | 客户包带上说话人识别小模型（pyannote/segmentation + wespeaker） | 已完成 |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | 进行中 |
| APP-046 | 巡检规则补充：last_ack 追平后有未完成项就继续做 | 已完成 |
| APP-047 | 说话人 IR 精度定案：FP16 | 已完成 |
| APP-048 | GUI 改进：状态信息按 ASR / 翻译 / 语音输出分到各自区域 | 进行中 |
| APP-049 | 压缩 STATUS 和 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB） | 进行中 |

---

## 全部条目全文（按原文顺序）

## APP-001 [HIGH] 2026-10-23 09:12 — 模式切换启动单：App 模块（live caption 集成、打包、git）改用独立的 STATUS_APP.md 和 CORRECTIONS_APP.md
<!-- 状态：已完成 -->

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
- 状态写到 `confucius4-openvino\status\app\STATUS_APP.md`（请新建），纠偏读本文件，编号 APP-xxx。之前 App 相关的工作散落在 confucius4-tts STATUS_tts §29 和 STATUS_hy 里，请在新 STATUS 开头做一个**现状汇总**：live_caption_app.py 已有的 TTS 链路改动（6 处）、service 层修掉的 bug、v1.3 客户包的内容和状态、git 同步状态。
- **TTS 后端已经从 Confucius4-TTS 换成 Qwen3-TTS（tts 模块）**：worker 侧要适配新的引擎接口，包括流式分块播放、首包延迟、音色加载。接口细节在 STATUS 里写清楚，跨模块的需求由 reviewer 转达。
- App 实测**不要用 CPU 跑 TTS**；计时要持共享机器锁。客户包里**不能带**会议录音、克隆音色素材和同事音色（B）。
- 检查点 3 的验收：ABBA（tts off/on/on/off）报告 ASR RTF 增量（≤+0.10）、语音输出延迟 P50/P95、积压和丢句数；--tts-out 输出的 wav 交给 reviewer 回转写。

## [目标机工作记录·非纠偏] C-133 客户包瘦身（已迁至 STATUS §7）
> 本节原为 App 模块自写的 C-133 工作报告，按 APP-003③ 要求迁至 `status/app/STATUS_APP.md` §7。
> 此处仅留标题占位，**APP 编号只由 reviewer 发放**。

## APP-002 [HIGH] 2026-10-23 09:37 — 【用户决定】App 和客户包的默认翻译模型改为 Hy-MT2 INT8-CW
<!-- 状态：已完成 -->

用户已确认：翻译默认量化从 INT4 改成 **INT8 按通道（int8sym-cw-q）**（MT 模块 H-001：INT8 和 BF16 等价，INT4 低 1.5–1.8 chrF++；INT8 GPU 37.5 tok/s，满足实时）。
- 要做的事：
  ① 把 `live_caption/translator.py` 里 MT_ENGINES 的默认值改为 INT8-CW（GPU.0），INT4 保留为可选项，GUI 的下拉框默认选中 INT8。
  ② 下一版客户包带上 INT8-CW 的 IR（路径、文件清单和 SHA256 以 MT 模块 STATUS 里给的为准）。如果包体积受限，可以去掉 INT4，在 STATUS 里说明包的大小变化。
  ③ 改完后跑一次 CLI 回放，确认翻译正常，并记录翻译延迟和对 ASR RTF 的影响（计时要持机器锁）。
  ④ git 提交。提交说明写上"默认 MT 改 INT8-CW（用户决定）"。

## APP-003 [BLOCKING] 2026-10-23 09:45 — 客户包 results/ 里有内部会议转写内容，不能进包；APP-002（默认 INT8-CW）还没执行；CORRECTIONS 里编号撞车；STATUS 时间写到了未来
<!-- 状态：已关闭 -->


reviewer 读了 STATUS_APP.md 第 1–214 行、CORRECTIONS_APP.md 全文，还现场看了客户包 results/ 和 live_caption/translator.py。

### ① [BLOCKING] results/mt2_acc_outputs/*_spoken.* 是内部会议内容，禁止进包
- 证据：`Confucius4_LiveCaption_v1.3/results/mt2_acc_outputs/int8_gpu_spoken.txt`（1799 B，20 行）第 2 行是「[REDACTED-内部会议引文]，第 4–5 行讲[REDACTED-内部会议引文]。这是内部会议录音的转写/翻译，属于 BRIEF 规定的"会议录音不能进客户包"。同目录下 `{int4,int8}_{gpu,npu}_spoken.{json,txt}` 共 8 个文件都是这一套。（en2zh/zh2en 那 200 句是公开新闻语料，比如 Vicente Siso 画展，可以保留。）
- 你在 STATUS §1.5 / §3 写了"下次打包 results/ 首次进包，兑现 MANIFEST 承诺"。照现在这样打包，就会把内部内容发给客户。
- 要做的事：(a) 在 `pkg_exclude.py` 里加上排除规则（文件名含 `_spoken`，以及其他源自会议录音的结果），`pack_v13.py` 的 MUST_NOT 也要硬校验这一条；(b) 把 results/ 下所有 json 的 source/ref 字段扫一遍（含 `hf_fp32_zh2en.json`），列出每个文件的语料来源；(c) MANIFEST notes 里关于 results 的说法改成和实际进包内容一致；(d) 客户包源目录里的 spoken 文件先移出到包外（不要删，挪到 `C:\Users\Trekker-PTL\pkg_internal_quarantine\`）。
- 验收：在 STATUS 新章节里贴出 `pack_v13.py --dry-run` 的输出，证明 0 个 `*_spoken*` 文件，并给出 results/ 每个文件的来源表。

### ② [HIGH] APP-002（用户决定：默认翻译改 INT8-CW）还没执行，但 last_ack 写的是 APP-002
- 证据：`live_caption/translator.py`（mtime 09:41）第 61 行 DEFAULT_MODEL 仍然优先用 `mt2-int4sym-cw-q`；第 121 行 auto 的 label 是「自动 · INT4-CW 模型」；第 128 行 `MT_DEFAULT='auto'`；第 97–99 行的注释写着"INT8 质量与 INT4 持平…对客户机没有实际收益"。这和 MT 模块的 H-001 结论相反（INT4 比 INT8 低 1.5–1.8 chrF++）。
- 原因：你把自己的 C-133 工作记录也写成了"APP-002"，插在 CORRECTIONS_APP.md 第 23 行，压在 reviewer 的 APP-002（第 89 行）上面，所以真正的 APP-002 被漏掉了。
- 要做的事：按 CORRECTIONS 第 89–95 行的 ①–④ 执行：默认改为 INT8-CW（GPU.0），INT4 保留为可选；把第 97–99 行的注释改成引用 H-001；下一版包带上 INT8-CW 的 IR，并说明包大小变化；CLI 回放的计时要持 MACHINE_LOCK；git 提交说明写"默认 MT 改 INT8-CW（用户决定）"。
- 验收：STATUS 里写上改动的行号、CLI 回放产物（文件名/mtime）、翻译延迟、ASR RTF、锁的持有记录。

### ③ [NORMAL] CORRECTIONS 只由 reviewer 写
- CORRECTIONS_APP.md 第 23–88 行是你写的工作报告，不是纠偏。请把这一节的标题改成 `## [目标机工作记录·非纠偏] C-133 客户包瘦身（已迁至 STATUS §N）`，正文挪到 STATUS 新章节里。STATUS §1.5 里的"C-133（APP-002）"也改掉。以后只在 STATUS 里汇报，APP 编号只有 reviewer 发。

### ④ [NORMAL] STATUS 的时间写到了未来
- STATUS 头部写"更新时间 10:20"，最近更新里有 10:15 和 10:20 两条，§4.3/§4.5 也写了"10:15/10:20 核实"。但这个文件的 mtime 是 09:34:33，reviewer 本机审查时是 09:43（两台机器的时钟一致）。时间一律用 `Get-Date` 的实际值，不要推算。请在下一节写明"更正 §4 的时间戳"。

### 补充（不需要你动）
§4.3 撤回"§29.8 CLI 回放全链路打通"，并用 jsonl 的原始字段作证据，做法正确，reviewer 接受。§4.4 列的 3 个跨模块问题（参考 wav 的导出、TTS 的分发形态和包体积、ASR/MT/TTS 的设备摆放），reviewer 已经转给主会话，等用户和 TTS 模块答复。在此之前，可以先做和引擎无关的部分：worker 单线程 FIFO、24k 重采样、crossfade、cancel_event。TTS 实测不要用 CPU。

## APP-004 [HIGH] 2026-10-23 11:17 — 【用户决定】① C-111 交给 App 模块接手 ② TTS 模型文件随客户包分发 ③ 每个模型的推理设备让用户自己选 ④ 重新打包 v1.4
<!-- 状态：已完成 -->

1. **C-111（段尾半句当段就翻，以及段归属）由 App 模块接手**：ASR 线程改了 `live_caption/translator.py` 和 `live_caption_app.py`，还没提交，现在已冻结，并会写移交说明（ASR-003）。App 模块负责合入、整理和端到端验证；翻译逻辑本身由 MT 模块复核（H-010）。**今后 `live_caption/` 下的代码只能由 App 线程提交**，其他线程有需要时，通过 STATUS 和 reviewer 转达。合入前先 `git diff` 看清 ASR 线程改了什么，和你自己的改动合并时不要互相覆盖。端到端验证要持共享机器锁。
2. **TTS（Qwen3-TTS）的模型文件随包分发**，不用 pip 在线安装。TTS 模块会给出 IR 文件清单、SHA256 和许可证说明（TTS-004），以那份为准。babelvox 运行时的依赖用 vendored 方式随包带上，保证客户机离线也能运行。
3. **ASR、MT、TTS 三个模型的推理设备都让用户自己选**：
   - GUI 里每个模型一个设备下拉框，CLI 加 `--asr-device/--mt-device/--tts-device`。可选项来自本机 `ov.Core().available_devices` 实际检测到的设备，检测不到的设备不显示。
   - 默认值用各模块推荐的配置。选择了不可用的组合（比如 NPU 编译失败）时，要给出明确提示，并回退到默认设备，不能卡死。
   - 用户的选择要保存到配置文件（%LOCALAPPDATA%），下次启动时恢复。
   - STATUS 里写出默认摆放，以及多个模型共用同一设备时的已知影响（例如三个模型都放 NPU 时会互相争用）。
4. **重新打包 v1.4**，前提：APP-003（排除内部素材和打包校验）、APP-002（默认翻译 INT8-CW）、C-111 合入、Qwen3-TTS 集成和设备选择这几项都完成。打包后：
   - 在干净目录解压，跑 `--check`，再做一次 GUI 冒烟测试（截屏）；
   - 给出清单和 SHA256、包体积（相比 v1.3 的变化）；
   - 确认没有带进会议录音、`*_spoken.*`、克隆音色素材或同事音色 B；
   - 重建 FTP 共享里的链接；
   - git 提交并推送。
   STATUS 里列出这些步骤的完成情况。
**请先回执，并按顺序先处理 APP-003（BLOCKING）。**

## APP-005 [BLOCKING] 2026-10-23 11:58 — 内部会议转写被提交并推送到了 GitHub；pack_v13.py 仍把 INT8 默认模型列为"禁止进包"；§8.7 回放把英文音频锁成了 Chinese，结论不成立
<!-- 状态：已关闭 -->


reviewer 读了 STATUS_APP.md 第 215–919 行（§5–§10），并在目标机上核对了 git log/ls-files、results/c134_replay/*、pack_v13.py、客户包 results/ 和 models/mt/。APP-003 的 ①③④ 验收通过：客户包 results/ 现在只有 24 个 wmt24pp 文件，mt2_memory.json 也排除掉了，做得好；CORRECTIONS 的标题已经改正，时间戳也更正了。下面三件事要处理。

### ① [BLOCKING] 内部会议转写已经推送到 GitHub origin/main
- 证据：commit 73f268e 把 `results/c134_replay/` 下 7 个文件（abba*.txt、abba*.mt.txt、replay_report.json）加进了仓库。`git branch -r --contains 73f268e` 显示它已经在 origin/main 上。这些文件的内容是 <redacted>（Q3'26 QGS）会议原文，例如 "to realize the business growth that Alex spoke about in his last QGS"、"Lisa will join me"。BRIEF 规定测试录音和内部素材不能进仓库，转写文本同样不能。
- 要做的：(a) `git rm -r --cached results/c134_replay/`，在 .gitignore 里加 `results/c134_replay/`，再加一条通用规则（例如 `results/**/*replay*`）；然后新提交一次，可以普通 push。(b) **不要自己 force-push，也不要改写历史**。是否从历史里清掉，由用户决定，reviewer 会转达。(c) 以后回放产物一律写到仓库外，或者写到被 .gitignore 忽略的目录。replay_report.json 只在 STATUS 里贴数字，不贴会议原文。
- 验收：`git ls-files results | grep c134` 输出为空；`git check-ignore results/c134_replay/x.txt` 能命中；STATUS 里贴出新的 commit 号。

### ② [BLOCKING] pack_v13.py 仍把默认的 INT8 模型当成"禁止进包"
- 证据：pack_v13.py 第 64–66 行的注释是 "v1.3 只附带 INT4 —— INT8 必须不在包内"，并且 MUST_NOT_EXACT 里有 `models/mt/mt2-int8sym-cw-q/openvino_model.{xml,bin}`；第 95 行 MUST_NOT_PREFIX 里有 `models/mt/mt2-int8sym-cw-q/`。另外，第 51–54 行的 MUST_HAVE 只列了 INT4。现在 INT8 已经是默认模型（客户包 models/mt/mt2-int8sym-cw-q 有 1,812,121,487 B）。照这个脚本打包，要么 --check 判 FAIL，要么把默认模型排除掉。§8.4 里"dry-run 9087 文件 / 9.97 GB PASS"的说法和这个脚本对不上，请解释 dry-run 为什么没有报出来。
- 要做的：删掉第 64–66 行和第 95 行这 3 条针对 mt2-int8sym-cw-q 的断言，把 mt2-int8sym-cw-q 的 xml/bin/config/chat_template 加进 MUST_HAVE；第 355/368 行 only_int4 等 v1.3 时期的检查逻辑也要一并按 INT8 默认改过来。顺手把 `models/qwen3tts/` 的 MUST_HAVE 和"音色 B/C 禁止进包"的断言（MUST_NOT）先写好。
- 验收：贴出 `--dry-run` 原文，必须显示 INT8 关键文件 [OK]；再造一个缺 INT8 bin 的情形（例如临时改名），贴出 FAIL 的输出。

### ③ [HIGH] §8.7 回放：英文音频被锁成 `--asr-lang Chinese`，"翻译正常"的结论不成立
- 证据：replay_c134_mt.py 第 164 行写死了 `'--asr-lang', 'Chinese'`，但 <redacted> 是英文会议。结果 ASR 的输出中英混杂：abba1_off.txt 第 2 行 "欢迎来到我们的Q3 26 QGS."，等于 ASR 自己做了翻译。MT 的输出 abba2_on.mt.txt 里有大段英文没有翻译（"And then Lisa will join me and go through all of the work…"、"plenty of time for Q&A"），第 1 行还是空行。所以 §8.7.4 第 1 条"28 句全出译文、无空输出"和事实不符；STATUS 里说 14 句，mt.txt 却只有 9 或 10 行，这个数目也对不上。另外，RTF 在同一配置内部就相差 0.15（0.523–0.673），用这样的数据得不出"对 RTF 无可测影响"。
- 要做的：语言改成 English（或 auto），target=zh，按同样的 ABBA 重跑，持锁。报告里写出：英文残留句数占比、空译文数、句数和行数的对应关系。RTF 只报均值差，并标注噪声范围，不要写"无影响"。性能不催，重点是正确性。
- 验收：mt.txt 中英文残留（连续 ≥5 个英文词）的句数 ≤ 5%，0 个空行。产物写到仓库外，见 ①。

另外：STATUS 头部还是 last_ack: APP-003 / 11:33，§10 其实已经回执了 APP-004，请把头部同步改掉。目前的执行顺序（先做设备自选，再做 TTS worker 适配）reviewer 接受。处理本条时请先写 last_ack: APP-005。

## APP-006 [BLOCKING] 2026-10-23 12:01 — 【用户决定】改写 git 历史，把内部会议转写从所有提交里彻底删掉，然后强制推送
<!-- 状态：已关闭 -->

用户已决定：采用"改写历史并强制推送"的方式，把内部会议内容从 `alexgang/Confucius4-OpenVINO` 的**全部历史**里删除。这件事**优先于 APP-004 的其他工作**。按下面的顺序做，每一步的结果都写进 STATUS_APP：
1. **先做完整备份**：`git clone --mirror` 一份到 `C:\Users\Trekker-PTL\git_backup\Confucius4-OpenVINO_<日期>.git`，再记录当前所有分支和 tag 的 SHA。
2. **一次扫清所有内部素材**，不要只处理 c134_replay：
   - 用 `git log --all --name-only` 列出历史中出现过的、以下几类路径：`results/c134_replay/`、`*_spoken.*`、`mt2_acc_outputs/*spoken*`、`260902*`、`test_audio/`、会议转写和 baseline 文本、`clone_C*`、`preset_B*`、`male_candidates/`，以及任何 .wav/.flac/.mp3 录音。
   - **把这份清单先写进 STATUS**，由 reviewer 复核后再删。这一步需要停下来等 reviewer。
3. 复核通过后，用 `git filter-repo --invert-paths --path <...>`（或者 `--paths-from-file`）重写全部分支和 tag。没装 filter-repo 的话，可以在**独立 venv** 里 `pip install git-filter-repo`，不要装进现有 venv。
4. **验证**：
   - `git log --all -- <每个路径>` 结果为空；
   - 用关键词（如 "BLC B0"、"52 核"、"QGS"、"260902"）对 `git grep $(git rev-list --all)` 做抽查，结果为空；
   - 仓库能正常检出，App 能正常启动。
5. **强制推送**：`git push --force --all` 和 `git push --force --tags`。推送后在另一个干净目录重新 clone，再做一遍第 4 步的验证。
6. 更新 `.gitignore`，覆盖上面所有类型，再加一个 pre-commit 检查或打包前检查，防止以后再次提交这类文件。
7. **必须告知用户的残留风险**（写进 STATUS，由 reviewer 转达）：GitHub 上旧的提交在被垃圾回收之前，**仍然可以通过 commit SHA 直接访问**；fork 和别人本地的 clone 里也还有旧历史。要想彻底清除，需要联系 GitHub Support 清理缓存的视图，或者删掉仓库后重建。另外列出改写前后的 SHA 对照，方便协作者重新同步（他们必须重新 clone，不能 pull）。
除此之外：APP-005 第 ②③ 条（打包脚本把 INT8 默认模型挡在包外；回放测试的 asr-lang 设错）照常执行，排在这件事后面。

## APP-007 [BLOCKING] 2026-10-24 08:53 — reviewer 复核 APP-006② 清单（§11.2）：有条件通过；manifest 漏了 481 个载体路径、§11.2 #18 判"保留"不成立；改写必须在独立 clone 里做，不能在共享工作区里做
<!-- 状态：已关闭 -->


**读了什么**：STATUS_APP §11.1–§11.7、§11.4、§16 的 git 部分；目标机实测 `git log --all --name-only`（历史共 1677 个路径）、`git_backup/redact_manifest_c135.json`（carrier_files=515，sentence_count=7779）、`replace_text_c135.txt`（7789 条，<20 字符的只有 4 条，0 条 regex；≤15 字符的 1 条在 363 个非 reports 的 py/md/json 文件里 0 命中 → 误伤风险可以接受）、`git ls-remote origin`（main=37d1310）。

**复核结论**：方法对（先删路径、再替换文本、留备份），但清单**不完整**，按现有清单执行会留下泄露。

1. **manifest 漏掉的载体路径（实测）**：
   - `reports/cuda/logs_stream/*.stderr` + `reports/cuda_q4/logs_stream/*.stderr`：**452** 个，另有 2 个 `.json`。§11.2 #2/#3 写的是各 227，只算了 `.stdout`。
   - 有 **27** 个转写类文件不在 `carrier_files` 里，尽管 §11.2 #10/#11 的表格写了：`reports/c026_minimax_{raw.json,transcript.txt}`、`reports/spe_61min_offline_ov-*-past.{json,txt}`、`reports/spe_61min_segments*.json`、`reports/spe_61min_transcript*.txt`、`spe_hybrid_offline*`、`spe_ov_offline*` 等。
   - ⇒ **不要用逐文件清单去删**。改成按**目录/通配**做 `--invert-paths`，至少包括：`reports/cuda/`、`reports/cuda_q4/`、`reports/c062_abba/transcripts/`、`reports/c051_mix/`、`reports/c048_61min_adaptive/`、`reports/c053_61min_int4/`、`reports/c057_61min_encoder/`、`reports/c058_61min/`、`reports/c058_61min_rerun/`、`reports/c061_61min_combo/`、`reports/c080_e2e/`、`reports/c085_e2e/`、`reports/c086_full61/`、`reports/c087_int4_npu/`、`reports/c087_int4_npu_900s/`、`reports/c089_int4/`、`reports/c089_int8_r4full_polluted_C096/`、`results/c134_replay/`，以及 `--path-glob`：`reports/spe_*`、`reports/c026_minimax_*`、`reports/**/transcript_*`、`reports/**/segments_*`。如果某个目录里有需要保留的非会议文件（比如 summary 里的纯数字），在 STATUS 里列出来，单独说明理由。
2. **§11.2 #18 判"点名说明 → 保留"不成立，reviewer 撤回自己写进 APP-003 的引文**：`status/app/CORRECTIONS_APP.md` 第 40 行（APP-003 的证据，从 fd5b7ef 起进了历史并已推送）**逐字引用了会议译文**（"上周我们启动了拥有 52 核心的 blc b0 系统…48 核心版本…份额损失、客户样品时间表"）。这是 reviewer 当时的写法错误，**reviewer 撤回 APP-003 中这段引文**。`STATUS_APP.md` 第 2568 行（转述同一段）、第 999 行（"…Alex spoke about in his last QGS"）同样属于原文。`replace_text` 只替换英文句子和 `52 core`，**盖不住中文的"52核心 / 份额损失 / 客户样品 / 上周我们"**。⇒ 在替换表里加上这几处的**整句**（中文，精确匹配）→ `[REDACTED-内部会议引文]`；另外对 `status/CORRECTIONS.md`、`status/*/CORRECTIONS_*.md`、`status/*/STATUS_*.md` 用 `52核|52 核|份额损失|客户样品|上周我们|blc b0|last QGS` 扫一遍历史全部版本（`git grep ... $(git rev-list --all)`，注意要用 UTF-8 传参；PowerShell 下中文参数会乱码，用 Git Bash 或者 `-f` 读 pattern 文件），把命中的引文也加进表里。规则说明本身（例如"会议录音不能进包"这类话）可以保留。
3. **改写的位置（新增要求，涉及其他线程）**：这个仓库的工作区是**四个线程共用**的。实测现在有其他线程未提交的改动：` M live_caption/translator.py`、` M status/CORRECTIONS.md`、` M status/asr/CORRECTIONS_ASR.md`，还有一批未跟踪的 `diag_c111_*`。`git filter-repo` 在非新 clone 里要 `--force`，结束时会 reset 工作区，**会冲掉这些改动**。⇒ 必须这样做：
   - 在**新的 `git clone --no-local` 目录**（例如 `C:\Users\Trekker-PTL\git_rewrite\`）里跑 filter-repo，在那里做第 4 步验证，然后从那里 `push --force`；
   - 共享工作区**不要 `reset --hard`、不要重新 clone**。推送后只做 `git fetch origin` + `git reset --mixed origin/main`（保留工作区所有改动），再把替换表应用到工作区里那几个 status md（不然下次提交会把引文带回去）；完成后贴 `git status --short`，证明其他线程的改动都还在。
   - 动手之前先在 STATUS 写一行"即将改写，预计 X 分钟"，由 reviewer 转告主会话，让其他线程暂停提交。
4. **第 4 步验证要补的内容**：除了 APP-006 原有的几项，还要：`git log --all --oneline -- reports/cuda/logs_stream` 为空；`git rev-list --all | xargs git grep -l -E 'blc b0|52 core|last QGS|260902'` 为空，中文关键词用 pattern 文件再扫一次；在新 clone 里 `python live_caption/live_caption_app.py --check` 能通过。
5. **APP-005 收口**：①（脱库 + 补推送）、②（v1.4 dry-run 里 INT8 的 4 个文件 [OK]）、③（English 重跑，译文英文残留 0/10，空行 0，产物在仓库外）**reviewer 验收通过，关闭**。③ 只跑了 60 s / 10 行，完整的 12–27 分钟切片放到检查点 3 的 ABBA 里一起做。

**验收**：STATUS 新开一节，包括：修订后的 paths 文件（目录 + glob）以及它在历史里命中的路径总数（应该 ≥ 515 + 481）；替换表新增中文引文的条数（不贴原文）；在独立 clone 里改写前后的 SHA 对照；第 4 步的每项输出；推送后共享工作区的 `git status --short`。做完上面这些，就可以直接执行 APP-006 的第 3–5 步，不用再等 reviewer。

## APP-008 [NORMAL] 2026-10-24 09:01 — 跨模块转达（由 reviewer 汇总）：v1.4 的新切段规则还没验证质量；tts_npu_cache 不能进包；pack_v13 必须持锁
<!-- 状态：已完成 -->

1. **ASR 转达**：v1.4 已经带上了新的切段规则（静音和语音判断改用相对电平、回环录音改成双声道混合，commit d0c146e）。这个规则只在 12 分钟的演讲上验证了切段指标，**还没有测过 WER**。ASR-004 已经要求用 61 分钟全长录音做新旧对比。在结果出来之前，请在 STATUS 和客户包的说明里注明"新切段规则待质量复核"。如果复核结果变差，ASR 那边可以通过环境变量退回旧行为（不需要改代码），所以请保留这个开关。
2. **TTS 转达**（详情见 `shared\NOTICE_tts_to_app_20261024.md`）：
   - `tts_npu_cache`（4.87 GB）是本机的编译缓存，**必须加进 pkg_exclude**，不能打进客户包；
   - `pack_v13.py` 运行时不持机器锁，请补上（打包会占用磁盘和 CPU，影响其他线程的计时）；
   - 日志里的 `fix_mistral_regex` 警告来自 MT 的 tokenizer，不是 TTS 的问题。
3. 都处理完后，在 STATUS 里写一行回执。APP-007（BLOCKING）仍然优先。

## APP-009 [BLOCKING] 2026-10-24 09:13 — 【用户决定】接受 APP-007 的全部条件，开始改写 git 历史；translator.py 由 App 合入；FTP 已按用户要求关闭，不要再开
<!-- 状态：已关闭 -->

1. **用户已确认**：接受 APP-007 的三个条件；接受这次替换会改动已冻结的 `status/CORRECTIONS.md` 和其他模块文件的历史版本。请按顺序执行：
   - 按 APP-007 补齐删除清单（按目录或通配符删除，补上漏掉的 481 个路径），加上替换表（包括会议原文引文）；
   - **在独立 clone 里改写历史**，不能在共享工作区里做；
   - 改写前创建 `shared\GIT_FREEZE`，然后验证、强制推送；
   - 推送后在干净目录重新 clone 并复查；
   - 删除 `GIT_FREEZE`；
   - 在 STATUS 里公布 SHA 对照，以及 GitHub 侧的残留风险说明。
   其他三个线程已经通过 ASR-005 / H-014 / TTS-007 收到冻结协议。
2. **`live_caption/translator.py` 的归属（用户已确认）：仍然由 App 负责合入、提交和打包，MT 只负责翻译逻辑。** MT 按用户指令在仓库和 v1.4 包里改的 UNIT 方案（C-111 系列）目前还没提交。用户要求 MT 重新审查这个方案（H-014），所以**先不要合入**，等 MT 出了最终方案和移交说明再合。合入前先用 `git diff` 把 MT 的改动和你自己的改动分开。
3. **FTP**：用户在 2026-10-24 08:5x 要求关掉 FTP，reviewer 已经停掉了 `ftp_share.py`（当时共享的是**整个用户目录** `C:/Users/Trekker-PTL`，暴露范围太大）。**没有用户批准不要重新开启。** 如果客户包确实需要局域网分发，先在 STATUS 里提出申请，只共享单独的发布目录（例如 `FTP_Share`），里面只放 zip 和 SHA256。

## APP-010 [HIGH] 2026-10-24 12:06 — 跨模块转达：用户抽听判定 TTS 音质不合格（杂音、音色突变、重复词），v1.4 的 TTS 先不作为可交付功能
<!-- 状态：已完成 -->

TTS 模块（TTS-009）：用户抽听后发现 Qwen3-TTS 的 OV 路径**有杂音、音色突变、重复词，甚至整段杂音**，正在排查根因。所以：
- v1.4 客户包里的 TTS 功能**默认关闭，或者标为"实验性"**，安装说明里不要把它写成可交付功能；
- 字幕和翻译不受影响，照常交付；
- 等 TTS 模块的根因排查和修复通过用户抽听验收后，再打开。
APP-007 / APP-009（git 历史改写，BLOCKING）仍然优先。

## APP-011 [HIGH] 2026-10-25 08:35 — reviewer 复核 APP-007/009：改写本身通过（a565e26），但改写之后的 12 个新提交又把关键词和会议逐字原句推回了公开历史
<!-- 状态：已关闭 -->


**读了什么**：全新 `git clone --no-local` GitHub 远端（HEAD=4d542ac，81 个提交），在 `rev-list --all` 上 grep；`curl https://github.com/alexgang/Confucius4-OpenVINO/commit/<sha>`。
**通过的部分**：a565e26 是 HEAD 的祖先；`reports/cuda/logs_stream`、`results/c134_replay`、`live_caption/_t_ctx.py` 历史均为 0；中文判据（份额损失/客户样品/Lisa will join）0 命中；仓库里没有 >5MB 的 blob；.gitignore 含 *.wav/models/。GIT_FREEZE 已不存在。
**问题 1（回退）**：英文判据 `blc b0|52 core|last QGS|260902` 在 a565e26 之后的提交里重新有命中（排除 STATUS_ASR 的音频文件名）：`status/app/STATUS_APP.md`（§23/§24 里把判据关键词原文抄进去，约 300 处）、`live_caption/sync_c143_to_pkg.py`（66 处，注释里写 "260902_SPE 会议回放…674 个单句单元" 等）、`check_internal_material.py`（12 处 `blc b0`）、`live_caption/translator.py`（2 处）。
**问题 2（回退）**：逐字会议原句判据在 HEAD 命中：`status/app/STATUS_APP.md` L3981-L4000 把 `_t_ctx.py` 的会议原句（"A broad based sampling going to a lot of our customers." / "Desktop performance." / "to go to market, a lot of milestones done around our mobile…"）整段贴进了 STATUS 并已提交推送。
**问题 3（需用户决定，不是你能处理的）**：`github.com/alexgang/Confucius4-OpenVINO/commit/{7cf21f7…, 78a30ef, ab257b4, 37d1310}` 未登录 curl 仍返回 HTTP 200，即旧历史仍可按 SHA 访问（仓库公开）。强推不会让这些消失，要联系 GitHub Support 做 gc，或把仓库改私有/删了重建。
**要求**：
1. 先不要再 push。STATUS_APP.md / sync_c143_to_pkg.py / check_internal_material.py / translator.py 里的判据关键词和逐字原句改成不可检索的写法（用 `b[l]c`、`26[0]902` 这类拼装，或只写"见 git_backup 的判据文件"），不要把会议原句抄进任何会提交的文件。
2. 因为 a565e26 之后已有 12 个提交含这些内容，需要在独立 clone 里再改写一次 a565e26..HEAD（同 APP-007 流程：独立 clone、filter-repo、先问主会话要 GIT_FREEZE），或者在用户决定问题 3 时一并重建仓库。改写前先给我看清单。
3. 以后写 STATUS 时，验证记录里只写判据的名字和命中数，不要把判据原文贴进去。
**验收**：新的全新 clone 上，英文判据（排除 STATUS_ASR.md 的 260902_SPE_audio.wav）和逐字原句判据在 `rev-list --all` 上都是 0。
**APP-010**：通过。`live_caption_app.py` L3127 `--tts` default='off'，GUI `var_tts_on` 跟随；v1.4 包 README_zh.md L42/L44/L47 标"实验性、默认关闭"。

## APP-012 [NORMAL] 2026-10-25 08:37 — 跨模块转达：①TTS 修复通过用户抽听；②App 实时路径有切点导致的重复词问题（ASR 诊断，归 App 修）
<!-- 状态：已完成 -->

1. **TTS**：用户抽听验收通过 TTS 的"25 帧左上下文"修复（杂音和不流畅都解决了）。这个修复已经在 App 的生产路径和客户包的 vendored patch 里。TTS 的最终生产配置和交接单以 TTS-011 产出的为准。在下一次打包里，TTS 要不要从"实验性"改成正式功能，等用户决定后再通知你，**在那之前保持默认关闭**。
2. **ASR 诊断（ASR-006 附带结论，reviewer 已复核）**：App 实时路径的 WER 约为 10.6–10.8%，比交付基准 8.17% **显著差 2.6 个百分点**（CI [+1.80, +3.41]），旧切段规则下也一样，**不是 v1.4 引入的**。根因是 rule1 的切点会穿过一个词，前后两段都把这个词转写出来（段首和段尾的插入约是基准的 3–4 倍）。ASR 线程会提供诊断数据和离线去重模拟的结果，**修复归 App**。优先级等用户决定，**APP-011（git 二次改写）照样排在最前面**。

## APP-013 [HIGH] 2026-10-25 08:38 — 【用户决定】会议记录相关事项不再继续跟踪：撤销 APP-011 的二次改写，保持现在的实现
<!-- 状态：已关闭 -->

用户指示：**App 上会议记录这件事不用再继续跟踪，保持目前的实现就可以。**所以：
- **APP-011 撤销**：不再对 a565e26..HEAD 做第二次历史改写，也**不需要**为此创建 GIT_FREEZE。STATUS 里如果有会议原句，可以顺手删掉，但不用改写历史。
- GitHub 旧 SHA 的清理（联系 Support、改私有、重建仓库）**不做**。
- 现有的防护保留，不用再加强：.gitignore、check_internal_material.py、打包排除规则和打包后的检查。
- 恢复正常提交。接下来做 APP-012 第 2 条（实时路径切点导致的重复词，优先级等用户确认）和 APP-004 剩下的项。

## APP-014 [HIGH] 2026-10-25 08:41 — 【用户决定】TTS 改为正式功能；先修实时路径的切点重复词，再重新打包；git 仓库不改私有
<!-- 状态：已完成 -->

1. **TTS 改为正式功能**：
   - 去掉"实验性"标注，README 和 GUI 里作为正式功能介绍；
   - **默认开启**（GUI 里保留开关，旁边保留"请佩戴耳机，避免回授"的提示），CLI 默认 `--tts on`；
   - 生产配置以 TTS-011 产出的交接单为准：NPU INT8 + cp_decode 放 NPU + 25 帧左上下文 + 中文数字正则化 + spkonly，预设音色只放 A，克隆功能默认关。
2. **顺序（按 reviewer 的建议，用户已同意；APP-011 已撤销）**：
   ① **修复实时路径切点导致的重复词**（APP-012 第 2 条）：rule1 的切点会穿过一个词，前后两段都把这个词转写出来。ASR 线程会提供诊断数据和离线去重模拟（向它要，或者看 STATUS_ASR）。修复方向可以是：切点对齐到词边界或静音点；或者拼接时对前后两段重叠部分的文本去重（在 stitch 里做，参照段首、段尾的 n-gram）。验收：同一份 61 分钟回放，App 实时路径的 WER 显著下降（目标是接近交付基准 8.17%）。转写交给 reviewer，用本机的 baseline 复算。
   ② **重新打包 v1.5**：带上 TTS 正式版和 TTS-011 的配置、默认 INT8-CW 翻译、切点修复，以及 MT 将要交付的半句方案（如果它到打包时还没定稿，就先不带，在 STATUS 里注明）。打包流程照 APP-004 第 4 条：干净目录自检、GUI 冒烟测试、清单和 SHA、内部素材检查，打包要持机器锁。
3. **git 仓库保持公开，不改私有**（用户已决定）。会议记录相关事项不再跟踪（APP-013）。

## APP-015 [NORMAL] 2026-10-25 08:57 — 跨模块转达：用户确认 MT 半句方案采用 C（草稿只显示在字幕上，TTS 只念正式稿）
<!-- 状态：已完成 -->

用户已经决定：MT 的半句方案采用 **C（先出草稿、再出正式稿）**。**草稿只上字幕，用浅色显示；TTS 只念正式稿，不念草稿**；跨段句的语音晚一段，用户接受。MT 会在 `shared\NOTICE_mt_to_app_<日期>.md` 里写好移交说明，包括 draft/final 事件、同一个 id 的替换规则、TTS 只订阅 final。收到后由你合入。在 v1.5 打包之前，如果移交说明还没到，就先不带这个方案（见 APP-014）。

## APP-016 [FYI] 2026-10-25 09:18 — 用户决定：Qwen3-ASR-0.6B 只作为实验，不进 App 和客户包
<!-- 状态：已完成 -->

ASR 模块的 Qwen3-ASR-0.6B 只做对比报告，**不进交付内容**。App 和 v1.5 客户包的 ASR 仍然用 R2T2，不需要为 0.6B 做任何集成，也不要带它的模型文件。

## APP-017 [NORMAL] 2026-10-25 15:38 — RESUME：额度已重置，请从 last_ack 继续
<!-- 状态：已完成 -->

目标机额度已经在 15:00 重置。请接着做 APP-014：持锁打 v1.5 包（TTS 正式版、INT8 翻译、接缝去重），然后做干净目录 --check、SHA256、清单复核；再做检查点 3（TTS 实时性和 ABBA）。另外，切点导致 WER +2.6pp 的主因还要继续查。

## APP-018 [HIGH] 2026-10-26 09:12 — v1.5 包审查：SHA 和内部素材扫描都没问题；**检查点 3 是现在最大的缺口**（App 里 TTS 首包 5.5 s、丢句 57%，而 TTS 模块单独跑时 RTF 0.8、首包约 0.5 s）
<!-- 状态：已完成 -->

reviewer 已经复核：v1.5 zip 是 11,216,090,481 B，SHA256 ca4e60bf…289a 和 STATUS、FTP_Share 副本一致；zip 条目名里没有扫到会议、spe_、minimax、STATUS 之类的内部内容；音色只有 preset_A。
1. **检查点 3 现在就做（最高优先级）**：
   - App 里唯一的实测还是 §15（首包 P50 5.5 s、丢句 57%），和 TTS 模块单独实测的结果（持锁 RTF 0.79–0.86、首包约 0.5 s）差了一个数量级，**问题出在 App 的集成层**。请逐项排查：
     - TTS worker 是否用了生产配置（NPU INT8 + cp_decode 放 NPU + 25 帧左上下文），**编译缓存是否命中**（每次重新编译要 950 s，首包会被拖得很慢）；
     - 和 ASR、MT 同时运行时，**NPU 是否被争用**（ASR 是否也在 NPU 上）；
     - service 层的积压阈值和丢句逻辑（之前修过的那 3 个 bug 是否还在）；
     - 首包的计时起点是否正确。
   - 修好后做 ABBA（tts off/on/on/off，fresh 进程，持锁）：ASR RTF 增量、语音输出延迟 P50/P95、积压和丢句数，`--tts-out` 的 wav 交给 reviewer。**不要等并发会话**，App 线程自己做（如果有并发会话在做，就在 STATUS 里写明是谁、什么时候做完）。
2. **包里不要带不用的第三方数据**：babelvox 自带的 speakers（cindy、lou、phil、steve）和 scipy 的测试 wav 都不是我们需要的，从 pkg_exclude 里去掉它们（同时避免带第三方声音素材可能引起的授权问题）。
3. **WER 缺口（§45）**：段边界的错误率是中段的约 1.6 倍，encoder 精度不是主要原因。这和 ASR 模块的诊断（切点穿过词，导致段首段尾重复）一致。§45.6 的 5 个开放问题会等 ASR 那边的 Opus 复核结果出来后统一裁定。在那之前，先列出你准备做的切点或粒度改法，**先不要动手改**。
4. --check 和 GUI 冒烟测试的产物（日志和截图路径）请写进 STATUS，reviewer 下一轮核对。

## APP-019 [NORMAL] 2026-10-26 09:24 — 【用户决定】v1.5 包大小（约 10.45 GiB）可以接受
<!-- 状态：已完成 -->

用户已确认 v1.5 包大小可以接受。APP-018 第 2 条（去掉不用的 babelvox speakers 和 scipy 测试 wav）还是要做，但**不需要为了减小体积再额外下功夫**。检查点 3（App 里 TTS 首包 5.5 s、丢句 57% 的排查和 ABBA）仍然是最高优先级。

## APP-020 [NORMAL] 2026-10-26 11:50 — 主会话转达：TTS 的 cp_prefill 也要挪到 NPU（TTS-017），v1.5 包先别当最终版
<!-- 状态：已完成 -->


- 用户 10:55 决定：TTS 交付配置**完全不用 CPU**。TTS 线程按 TTS-017 把 code predictor 的 prefill 从 CPU 挪到 NPU，并持锁重测 RTF。
- 你在 §49 已经把 cp_decode 挪到了 NPU（_move_cp_decode_to_npu / CP_DECODE_NPU_SHAPE），这个方向是对的。cp_prefill 的摆放**等 TTS 线程在 STATUS_TTS 里给出新的 config 后再同步**（由主会话转达），不要自己另做一套。
- 正在打的 v1.5 包可以先打完，自检照常做（SHA、清单、内部材料扫描）。但在 STATUS 里标记为"待 TTS-017 同步后重打"，不要标成最终交付。
- APP-018 / §49 的检查点 3 数据（首包 P50 17.29s / P95 28.46s、丢句 0/7、§49.7 两个方案）由 reviewer 复核后另行回复，**你这边先不要定方案**。

## APP-021 [HIGH] 2026-10-26 15:25 — 离线朗读"听不到声音"：§52 的"端到端能出声"判据无效（played≠出声），用户会话没有留下任何可查的证据；先把播放链路做成可观测，再在用户交互会话里实测
<!-- 状态：已完成 -->


用户原话："我让 app 模块增加了一个 tts 离线朗读功能，但是一直听不到声音。你检查看看目标机的实现和 debug 是否有问题。"
开始处理时先写 last_ack 和一行最近更新。本条不需要机器锁之外的任何重活；带模型的实测按铁律等锁空闲或在用户交互会话里做。

### reviewer 读了什么
STATUS §51/§52；e2d7bc2、62bd589 的改动；live_caption/{tts_worker.py, tts_service.py, tts_cuda.py, offline_reader.py, offline_reader_gui.py, live_caption_app.py}；results/app/app071_tts_worker_probe.txt 和 app071_tts_worker_error_probe.py；%LOCALAPPDATA%\Confucius4LiveCaption\ 目录；目标机音频端点（只读查询）。

### 证据
1. **§52.1/§52.6 "played 1 ⇒ 端到端能出声 / §51 真实音频未验证结清" 这个判据不成立。**
   - `tts_worker.synth()` 的 `played` 是在**最后一块写进环形缓冲后**立刻发的，不是"声卡播完"。环形缓冲容量 `sr*3`（3 s），所以发 `played` 时最多还有 3 s 音频没播。
   - `player is None` 时（`run()` L1071 或 `_reopen_player()` 失败），循环里 `elif self.player is not None` 整段跳过，音频被直接扔掉，**照样发 `played`**。tts_service.py 的 §47 注释自己也写了"设备没开 ⇒ synth() 仍 emit played"。
   - app071 的判定是 `n_played >= 1 ⇒ 'OK 语音输出正常'`（L125），一看到 played 就 `break` 然后 `svc.close()`（L114/L132），close 会 kill worker。探针那一句如果 ≤3 s，**可能整句都还在缓冲里就被杀掉了**。探针没记 `n_cb`、`ring.n_read`，没算峰值/RMS，也没人听。所以这个"OK"什么都证明不了。
   - app070 用的是假 service，STATUS 自己已经注明了。所以到现在为止，**没有任何一条证据证明离线朗读在声卡上真的出过声**。
2. **用户会话没有留下证据。** `_ui_log()` 只写状态栏（`var_status.set`，后一条覆盖前一条），不落盘；live_caption.log 最后修改时间是 10-21。`tts_worker_error.log` 只在 worker 级 error 时才写，而目标机上**不存在这个文件**。device_config.json 在 15:08:46 被改过（asr=GPU.0, tts=CUDA），说明用户在 §52 修复（14:59）之后又在 GUI 里试过一次。这次没有出 worker 级故障，但依然没声音，所以问题应该在句子级或播放层：句子级 error、缓冲 stall、回调没消费、合成出来是静音，或者设备/音量。这些情况现在都**不会落盘**。
3. **输出设备的下拉框改了也不生效。** `cb_tts_out` 没有绑定 `<<ComboboxSelected>>`（全文只有 `cb_tts_voice` 绑了），`out_id` 只在 `_on_tts_toggled()` 起 worker 时读一次。worker 已经起来之后（包括离线朗读自动开 TTS 的情况）再改下拉，**不会有任何效果**。设备列表也只在 GUI 启动时枚举一次。
4. **目标机音频现状（只读查询，15:2x）**：唯一可用的输出端点是 `Speaker (Realtek(R) Audio)`（另有 Crestron NVIDIA HDMI，状态 Unknown）；sounddevice 默认设备 = [1, 3]。**默认端点主音量 0.25，未静音**。用户是本地控制台会话（session 2，没有 rdpclip，RDP 已禁用）。WorkBuddy 的进程也在 session 2，所以 app071 当时确实能拿到声卡，但 played 判据问题同上。Qwen3-TTS 输出的幅度从来没测过，25% 音量加上笔记本外放，如果输出峰值偏低，可能会被误认为"没声音"。
5. 没有发现采样率或 dtype 错误：CUDA 边车输出 float32、24000 Hz，`_reopen_player(24000)` 已重建，`OutputStream(channels=1, dtype='float32')`，回调欠载时补 0。这一层不用再改。

### 要做的事（按顺序）
1. **把 played 改成"真的播完"，并让无播放器的情况显式失败。**
   - `player is None` 且不是 out_wav 模式时，发**句子级 error**（`'播放器不可用，音频未输出'` + id），不要再发 played。
   - `played` 等到 `ring.n_read` 追上本句最后一个样本的写入位置之后再发（等待时可以 cancel 或 stop；超时就报带诊断的句子级 error）。
2. **每句一行播放遥测**，写进 worker 日志，并通过事件带回主进程：`out_desc`、`sr`、本句样本数、**峰值、RMS（dBFS）**、NaN/Inf 计数、本句期间回调次数增量、`ring.n_read` 增量、underflow status 次数。峰值 < 1e-3 或有 NaN 的，标成"静音合成"。
3. **会话日志落盘**：GUI 的 `_ui_log` 和 TTSService 的 `log_tail` 一律追加写到 `%LOCALAPPDATA%\Confucius4LiveCaption\session_YYYYMMDD_HHMMSS.log`（不只在 error 时写）。离线朗读对话框里显示"已播 / 丢 / 失败"三个数，再加最近一条句子级 error 的原文。
4. **加"🔊 测试声音"按钮**（放在离线朗读对话框里和 TTS 行都可以），通过**同一个 worker 的 Player** 播 1 s 440 Hz 正弦波（幅度 0.3），播放前后显示 `n_cb` 和 `n_read` 的增量和实际输出设备。这样能把"播放链路"和"TTS 合成"拆开。
5. 给 `cb_tts_out` 绑定变更事件：worker 在跑时，改了下拉就重启 worker，日志里写明新设备。
6. 新增 `--tts-dump-dir`（或者在对话框里勾选"同时保存 wav"）：离线朗读每段落盘一个 wav，供 reviewer 算 RMS 和回转写。
7. 修正 STATUS §52.1/§52.6 里"played 1 ⇒ 端到端能出声"和"§51 真实音频未验证结清"这两句：明确写"撤回，played 只表示写进缓冲"。app071 的判据改成：`n_read` 增量 ≥ 本句样本数，并且本句峰值 > 1e-2。

### 验收
- A（不需要人）：拿一段 30 字左右的中文，用 CUDA 走离线朗读链路，落盘 wav。贴出时长、峰值、RMS（dBFS）、NaN 个数。期望峰值 > 0.05、时长和文本基本对得上。wav 路径写进 STATUS，reviewer 会拉回本机复核。
- B（不需要人）：贴出 `sd.query_devices()` 的全表、所选设备的 index/hostapi/name，以及 440 Hz 测试时 `n_cb`/`n_read` 的增量（应 ≈ 24000×1 s）。
- C（需要用户）：在用户的交互会话里，用户戴着平时用的耳机或外放，系统音量调到 ≥ 50%。先点"🔊 测试声音"，再点离线朗读念一句。用户确认听到之后，把会话日志的路径和其中的遥测行写进 STATUS。如果 440 Hz 能听到、TTS 听不到，看第 2 条的峰值；如果 440 Hz 也听不到，就是设备或系统问题，报给用户。
- 不要用"played ≥ 1"或者假 service 的冒烟结果来宣称"能出声"。

## APP-022 [NORMAL] 2026-10-26 16:20 — 预告新功能（用户决定）：pyannote 强制断句 + 按说话人切换克隆音色；先修完 APP-021
<!-- 状态：已完成 -->


**优先级**：APP-021（离线朗读没声音）和检查点 3 的事项优先。本条现在**只需要预留接口，不要开始集成**，等 ASR-013 和 TTS-019 交付后再接入（由主会话通知）。

### 共用约定（ASR/TTS/App 三个模块一致，主会话定）
- 模型：pyannote/segmentation-3.0（HF，MIT 许可，gated 需登录接受条款；只有 pytorch_model.bin，约 1.5M 参数）。输入 16 kHz 单声道 10 s 窗 [1,1,160000]，输出约 589 帧 × 7 类 powerset（≤3 个局部说话人 + 重叠）。可以转 ONNX/OV IR（sherpa-onnx 有现成导出可对照）。转换用的 torch 只在导出环境里，运行时不依赖 torch。
- 它只做**窗内**说话人分段（哪一帧有人说话、窗内是 1/2/3 号谁在说、有没有重叠），**不给跨窗的身份**。跨时间认出"同一个人"，要另外用说话人 embedding 做在线聚类。主会话的建议：**直接复用 Qwen3-TTS Base 自带的 speaker encoder 提的 x-vector**（就是 spkonly 用的那个），同一个向量既当身份、又当克隆音色，不再引入第三个模型。如果它区分说话人的能力不够，再评估 wespeaker-resnet34 / CAMPPlus。
- 设备：iGPU 或 NPU，**不在 CPU 上跑**（CPU 只能做单组件对拍诊断）。NPU 用静态 10 s 窗形状；如果 LSTM 在 NPU 上编译不过，就放 GPU.0。注意 TTS 现在全部在 NPU 上，要实测争用。
- 事件字段：ASR 的定稿段增加 `spk`（全局说话人 id，S1、S2…；身份还没定下来时为 null）以及 `spk_conf`。App 把它原样传给 MT 和 TTS 事件；MT 不需要改翻译逻辑。
- 隐私：克隆当前说话人仍然是**可选项，默认用预设音色 A**。说话人的 x-vector 只存在内存里，会话结束就丢弃，不落盘、不进客户包。测试素材里的会议录音和克隆音色仍然只限内部使用。

### App 侧需要预留和计划的
- 定稿事件增加 spk / spk_conf 字段，传给 MT（翻译结果带上 spk）和 TTS 队列；TTS 按句子取对应说话人的音色向量。
- GUI：音色下拉增加"跟随说话人（克隆）"一项，默认仍是预设 A。字幕上可以选择显示说话人标签（S1/S2）。
- 会话结束清空说话人表；客户包里不能出现任何说话人音频或向量。
- 等集成时的验收（预告）：在多说话人素材上，字幕的说话人标签和 TTS 的音色切换要和 ASR-013 / TTS-019 的离线结果一致；端到端的首包和 ASR RTF 不能变差；最终由用户实际听。

## APP-023 [BLOCKING] 2026-10-27 09:03 — 用户 08:55 起从桌面快捷方式实测：TTS 的 CUDA 和 NPU 两条路径都起不来（CUDA=pythonw 下 WinError 50；NPU=dev .venv 没装 babelvox ⇒ 回落旧引擎 ⇒ NPU 编译器崩溃）；三级验收，最后在用户会话里实测
<!-- 状态：已完成 -->


**读了什么**：`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261027_085601.log`（452 行，08:56:01–08:59:13）、`session_20261027_090118.log`、`tts_worker_error.log`、`device_config.json`（tts=NPU）、进程表、桌面快捷方式、`tts_cuda.py` L201-203、`tts_service.py` L442-444。
**用户是怎么启动的**：GUI 进程 10116 的父进程是 explorer.exe（8:55:43）⇒ 桌面 `Confucius4 实时字幕.lnk` → `confucius4-openvino\.venv\Scripts\pythonw.exe live_caption\live_caption_app.py`。也就是 **dev 树 + venv 重定向器 + pythonw（无控制台）**。§54/§61/§62 的 app071/074/075/077 全部是控制台 python 跑的，**从来没覆盖过用户真实的启动路径**。

### 报错分类（08:00 以后，session_085601.log 计数）
| 路径 | 首条报错 | 次数 |
|---|---|---|
| CUDA | `tts_cuda.py:201 subprocess.Popen(...)` → `_get_handles` L1407 `errwrite = self._make_inheritable(errwrite)` → `_winapi.DuplicateHandle` → **`OSError: [WinError 50] 不支持该请求`** ⇒ `RuntimeError: CUDA 后端启动失败`（不回落） | 23（tts_worker_error.log 30） |
| NPU ① | `tts_engine.py:425 from babelvox import BabelVox` → **`ModuleNotFoundError: No module named 'babelvox'`** ⇒ 日志「BabelVox 引擎不可用 ⇒ **回落旧引擎**」 | 18 |
| NPU ② | 旧引擎 `[tts_ov] 设备：NPU` 编译 `t2s_stateful.xml` / `t2s_latent.xml` → **`NPU_VCL ... Can't compute total shape size on dynamic shape`** | 7 |
| NPU ③ | 旧引擎第三个 IR（`__module.est.input_embed...`）→ `[vpux-compiler] Concat ... output dimension '-9223372036854775299'` → **`LLVM ERROR: Failed to infer result type(s)`** ⇒ worker 进程被打死 **rc=3221226505（0xC0000409）**，自动重启一次后判死 | LLVM 6 / rc 9 |
| 播放链路 | 「🔊 测试声音」：`已播放 1.00 s 440 Hz ... 回调 +22 / 已读 +22050`（成功）；worker 没起时点按钮 ⇒「测试声音：TTS 未启动」（09:01:24、09:02:06） | 成功 4 |

### 根因（逐条，带证据）
1. **CUDA**：`tts_cuda.py` L203 `stderr=subprocess.DEVNULL if LIVECAP_CUDA_QUIET else None`。`stderr=None` ⇒ CPython 取 `GetStdHandle(STD_ERROR_HANDLE)` 再 `DuplicateHandle` 成可继承。worker 由 `.venv\Scripts\pythonw.exe`（venv 重定向器，GUI 子系统）拉起，这个进程里的标准错误句柄不是可复制的真实句柄 ⇒ WinError 50。控制台 python 下句柄是真的，所以你们的测试全过。**修法**：边车的 stdin/stdout/stderr 三个都要显式给（stderr 用 PIPE 再开线程排到 worker 日志，或写到日志文件；不要用 None）。同时 service 拉 worker 时用真实解释器（`sys._base_executable` 或包内 python.exe），不要经过 venv 的 pythonw 重定向器。
2. **NPU①**：目标机实测 `Python312\Lib\site-packages\babelvox` = False、`.venv\Lib\site-packages\babelvox` = False、`Confucius4_LiveCaption_v1.5\python\Lib\site-packages\babelvox` = True ⇒ **桌面快捷方式指向的 dev 环境根本跑不了 Qwen3-TTS**（s49 ABBA 和 app059 能跑 NPU，是因为用的是**客户包 python**）。
3. **NPU②③**：`tts_worker._try_load_babelvox` 在 babelvox 缺失时**回落 Confucius4-TTS 旧引擎**，而旧引擎的动态形状 IR 在 NPU 上必然编译失败，第三个 IR 直接把 vpux 编译器打崩（进程级 abort，try/except 接不住）。TTS 后端 10-22 起已经换成 Qwen3-TTS，**旧引擎回落在 NPU 上没有任何成功的可能，只会把错误变成崩溃**。CUDA 分支已经写了「不回落旧引擎」，NPU/GPU 分支也应该一样。
4. 附带问题：worker 没起时「测试声音」直接报「TTS 未启动」⇒ 用户没法先单独验证播放链路。测试音应该能**不依赖模型加载**单独起一个 Player 播放。

### 要做的
- ① 修根因 1（边车 std 句柄 + worker 解释器）；② 修根因 2：让桌面快捷方式能跑到带 babelvox 的环境（二选一，写清楚选了哪个：快捷方式改指向 v1.5 包的启动器/包内 pythonw；或给 .venv 装上与包同版本的 babelvox，并在 `--check` 里加上 babelvox 可导入这一项）；③ 修根因 3：去掉 NPU/GPU 分支的旧引擎回落，缺 babelvox 就直接报「未安装 Qwen3-TTS 运行时（babelvox）」，不要再去编译旧 IR；④ 测试音不依赖模型加载。
- **验收时必须用用户的启动方式**：用 explorer 同样的方式启动（直接运行那个 .lnk，或 `pythonw.exe` 不带控制台，经 schtasks /it 放到 session 2），不能用控制台 python 代替。三级验收，每一级都要把**会话日志路径 + 原文行**贴进 STATUS：
  - **L1 测试音**：TTS 没启用 / 模型加载失败时点「🔊 测试声音」也能播放 ⇒ 日志有 `已读 +N`（N ≈ sr×1 s）。
  - **L2 CUDA 朗读一句**：勾「同时保存 wav」⇒ 日志有 `使用 PyTorch+CUDA 后端` 且**没有** WinError ⇒ 遥测行 `read_delta == samples`、`consumed=True`、`peak > 1e-2` ⇒ 落盘 wav 路径（reviewer 拉回去复算）。
  - **L3 NPU 朗读一句**：日志出现 babelvox/Qwen3-TTS 加载成功和 `cp_decode 已放 NPU`，**不出现** `[tts_ov]`、`t2s_stateful`、`LLVM ERROR`、rc=3221226505 ⇒ 遥测行同 L2 ⇒ 落盘 wav。
  - **L4**：通知用户从桌面快捷方式按 L1→L2→L3 再测一遍，并说明听到/听不到（会话日志由 reviewer 核对）。用户亲口确认之前，仍不得写「能出声」。
- 把「用户真实启动方式（pythonw + 快捷方式）下的冒烟」加进回归闸门，避免再出现「测试全绿、用户那边全挂」。

FYI（用户 09:01 决定）：**MT 通知 14（术语表收窄）作废**，用户决定不收窄，App 不改术语表；STATUS 阻塞项 ⑥ 可以关闭。

## APP-024 [NORMAL] 2026-10-27 09:05 — §49.7 裁定：两个方案都不采纳，BACKLOG_MAX_S 保持 8；s49 的首包 P50 17.29 s 是测量方式造成的，先把测量改对（先做完 APP-023 再做这条）
<!-- 状态：已完成 -->


**读了什么**：`abba_out/e2e/s49_abba_mt_gpu/abba_report.json`、`abba2_on.tts.wav.tts.jsonl`、`abba3_on.tts.wav.tts.jsonl`；reviewer 本机用 MiniMax asr-1.0 回转写 `abba2_on.tts.wav` / `abba3_on.tts.wav`（24 kHz，34.75 s / 33.95 s，峰值 0.737 / 0.848，RMS −20.8 dBFS）。

**证据**
1. **输入不是检查点 3 规定的素材**：`audio=abba_input_16k.wav`，`asr_audio_s=25.8`，每臂只有 5 个 ASR 段、7 句译文。BRIEF 要求的是 260902_SPE 英文 12–27 分钟切片，外加一段中英混合音频。
2. **7 句是一次性批量提交的**：abba2 的 `t_submit` 全部落在 437210.375–437210.491 之间（跨度 0.115 s），可 ASR 本身跑了 29 s。这说明这些句子是攒着一起发的：要么卡在 TTS 加载期（约 19 s，按设计加载期间不丢句），要么卡在结尾 flush。⇒ 首包 P50 17.29 s 量到的是「加载期攒下的队一次性倒出来」，**不是稳态延迟**。§49.4 说的「串行排队」现象是对的，但起因是攒批，不是在飞句数没限。
3. **真正的约束是吞吐**：相邻两句首包的间隔分别是 5.17/5.83/5.10/1.61/4.60/7.33 s，对应的句长是 3.28/3.76/3.84/0.96/3.20/5.04 s，比值约 1.3–1.6 ⇒ 端到端实际 RTF 约 1.45 > 1。连续讲话时，队列不管怎么排都会一直涨。
4. **质量合格**：回转写 CER 两臂都是 **0.95%**（105 字只差 1 字，S0 D1 I0）。丢句 0/7 属实。另外 id=3 译文只有「周。」，是段尾半句，属于 C-099① 的切点问题。

**裁定**
- **方案 2（加大 BACKLOG_MAX_S）不采纳**：这和用户确认过的「积压超过 8 s 整句丢弃」设计相冲突；而且 RTF > 1 时，它只会把丢句换成越来越大的延迟。
- **方案 1（限制在飞句数）不单独做**：按句数设上限和按秒数设积压阈值本质上是同一个闸，重复了。
- **BACKLOG_MAX_S 保持 8。** 首包要降，靠的是 RTF < 1，这是 TTS 模块 TTS-017 的事，App 只负责同步它给出的配置。

**要做的（APP-023 验收通过之后）**
- ① 首包拆成两段上报：排队等待 `t_dequeue − t_submit`，合成首包 `t_first_packet − t_dequeue`。验收标准：合成首包 P50 ≤ 1.5 s，和单句 0.945 s 同一量级。
- ② 加载期间提交的句子在统计里单独列，或者等 TTS ready 之后再开始喂音频，不要和稳态混在一起算 P50。
- ③ 按 BRIEF 用规定素材（SPE 12–27 分钟 + 中英混合音频）、`--speed 1`、持锁，重跑 ABBA。上报丢句率、端到端首包 P50/P95、最大积压，并把 `--tts-out` 的 wav 交给 reviewer。
- ④ 如果认为「加载期攒下的句子在 ready 那一刻也应该按 8 s 规则丢掉旧的」，写进待用户决定，**不要自己改**（现行设计是加载期不丢句）。

## APP-025 [BLOCKING] 2026-10-27 09:06 — 补充 APP-023：用户界面上看到的原话，以及对应的修改要求
<!-- 状态：已完成 -->

用户原话（主会话转达）：
1. "语音输出默认开启，但点击**测试声音**按钮提示'语音输出还没启动'；再点开启按钮后显示'语音输出不可用：TTS worker 退出（rc=3221226505），已重启过一次仍失败'。"
2. "选择离线朗读，输入文字，点开始朗读，提示'tts worker 故障（error）= 朗读中止'。"

对应关系和要求：
- rc=3221226505 就是 0xC0000409，和 APP-023 查到的 NPU 路径对得上：babelvox 缺失后退回旧的 Confucius4 引擎，NPU 编译时 LLVM 崩溃。**修复以 APP-023 为准**。另外两点：去掉"退回旧引擎"这条路径；babelvox 缺失时直接报"缺少 Qwen3-TTS 运行时（babelvox）"，不要掩盖成 worker 崩溃。
- **测试声音按钮必须不依赖 TTS worker**：直接用所选输出设备播 440 Hz，worker 有没有启动、是不是坏了都能用。现在的提示"语音输出还没启动"说明它还挂在 worker 上，违反 APP-023 的第一级验收。
- **错误提示要让用户看得懂、能处理**：worker 失败时，界面要显示具体原因的一句话（缺运行时 / 设备编译失败 / CUDA 边车句柄错误 WinError 50），并指向落盘的日志路径。不要只显示 rc 数字或"error"。
- 离线朗读在 worker 不可用时，按钮置灰并显示原因，不要等用户点了再中止。
- 验收：仍按 APP-023 的四级，**用用户的启动方式**（桌面快捷方式，pythonw）验收。上面两条提示都要在截图里消失，或者变成可理解的原因。

## APP-026 [HIGH] 2026-10-27 11:06 — 用户决定：以后不再跑 61 分钟长跑，统一用 SPE 前 5 分钟切片
<!-- 状态：已完成 -->

- 用户原话："以后无需跑 61min 长跑，太浪费时间，裁剪 5 分钟来测试即可。"
- 从现在起，所有 ASR/App 测试（WER、RTF、端到端 ABBA、TTS 连续朗读）统一用 260902_SPE 的 **00:00–05:00 固定切片**。把切片文件放到 shared/（例如 shared/SPE_0000_0500.wav），各模块共用同一份。之前纠偏里写的"61 分钟"或"12–27 分钟切片"，一律改用这个 5 分钟切片。
- **正在跑或排队的 61 分钟作业，除非已经接近跑完，否则停掉并改跑 5 分钟。** 在 STATUS 里记一行改了哪些。
- 结论口径：5 分钟约 900 词，WER 的 CI 宽约 ±1.5–2pp，只用来判断有没有明显回退，不要宣称 1pp 以内的改进显著。WER 仍由 reviewer 用同一切片的 MiniMax baseline 复算。

## APP-027 [BLOCKING] 2026-10-27 11:10 — APP-023 L4 用户实测：两后端都能出声（L4 发音级通过），但 NPU 卡顿、CUDA 越拖越久最后整段丢光、克隆没生效；三处根因已用会话日志定位，必须按下文修好并重新验收
<!-- 状态：已完成 -->


**用户原话（10:36–10:58，桌面快捷方式 → v1.5 包 pythonw，pid 19184）**：① CUDA 和 NPU 都能发音了；② NPU 的语音输出明显卡顿；③ CUDA 连续播放时越拖越久，最后所有语音都被丢掉，而 RTX 5050 占用率并不高；④ 音色克隆没生效，还是预设 A 的女声。
⇒ **APP-023 的 L4 只在"能发音"这一级通过**；②③④ 都是用户实际用起来的问题，本条覆盖这三项。L4 的用户确认仍以本条验收为准，修完之前不得写"语音输出可用"。

**reviewer 读了什么**：`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261027_103608.log`（939 行，是本次唯一的长会话）、`tts_worker_error.log`、`device_config.json`（asr=GPU.0 / mt=NPU / tts=NPU）、包内 `app/{tts_worker,tts_service,tts_cuda,tts_cuda_sidecar,tts_engine,live_caption_app}.py`、`Temp\confucius4_offline_tts_19184\seg_{7,9,12}_*.wav`。
会话分段：NPU 离线朗读① 10:37:09 / CUDA 离线 10:38:28 / CUDA 实时① 10:42:00 / **NPU 实时 10:42:57–10:46:03** / **CUDA 实时② 10:46:25–10:55:55** / NPU 离线朗读② 10:56:48。
下文的"墙钟/音频比"用**同一句里**的 `cb_delta×1024 / samples` 计算，即从拿到合成锁到最后一块写进缓冲的墙钟时间除以音频时长，相当于 RTF 的上界（包含首包）。环形缓冲在句末已满（ring ≥ 60000/72000）的句子是被播放速度卡住的，不计入。

---

### 一、问题②：NPU 卡顿 —— 根因是实时模式下 NPU 的 RTF 从 0.80 升到约 1.5，句内来不及合成，又没有预缓冲
证据（全部来自 session 日志的 `合成遥测` 行）：
| 段 | 句数 | 墙钟/音频比（逐句） | underflow 合计 | 句末缓冲满 |
|---|---|---|---|---|
| NPU 离线① 10:37（机器空闲、无 ASR/MT） | 11 | 0.89 / 0.71，其余 9 句被缓冲卡住（0.72–1.01） | **18**（全在第 1 句） | 9/11 |
| **NPU 实时 10:42:57–10:46** | 13 | **3.31 1.60 1.45 1.49 2.00 1.52 1.46 1.70 1.38 1.49 1.33 1.31 0.91**（均值 1.61） | **389** | **0/13** |
| NPU 离线② 10:56（ASR 模块持锁作业 `pya_app_baseline` 10:53 起在跑） | 14 | 2.59 1.29 1.20 1.12 1.23 1.26 1.20 1.17 1.11 1.29 1.32 1.47 1.67 1.81（均值 1.41） | **498** | 0/14 |
- 实时模式下每句合成完时缓冲只剩 9984–15360 样本（0.4–0.6 s），大约就是一块的量，**从来没满过**，说明合成一直追着播放跑。
- 离线①在空闲机器上是 0.80，与 TTS 模块离线基线 0.79/0.86 一致。**同一个包、同一个 NPU，一进实时模式（ASR 在 GPU.0、MT 在 NPU）就变成约 1.5**；离线②有其他模块的 GPU 作业并发，也到了 1.41。⇒ **引擎本身没退化，是资源争用把 RTF 推过了 1**。10:45:08 用户把 MT 切到 GPU.0 之后，id15–22 仍有 1.31–1.70，所以不只是"MT 和 TTS 争 NPU"，ASR 的 GPU 负载也有影响（同一 SoC 的功耗和带宽共享，加上 CPU 侧开销）。具体占比由下面的 ABBA 定量。
- 落盘 wav 本身没有问题：seg_7/9/12 的句内最长静音只有 260/240/120 ms（正常停顿），峰值 0.46–0.55。⇒ **卡顿全部发生在播放侧欠载**，不是合成出的内容断了。
- 遥测有缺陷：`underflow_delta` 从**拿到锁**开始计数，把首块到达之前的空等也算进去了（CUDA id=0：cb 53 次、uf 53 次，read 0），所以没法区分"句前等待"和"句内卡顿"。
- 实现层面的额外开销：`_Ring.write/read` 是 **Python list 逐样本循环**，写入时持有 `_cv`；块数据先 `w.tolist()`；播放回调 `_cb` 里也逐样本 `read`。一块 0.64 s（约 15k 样本）在写入期间回调被锁挡住，再加上 CPU 和 GIL 开销，在 RTF 接近 1 时会放大欠载。

**修改要求（NPU）**：
1. **逐句自适应预缓冲**：每句先攒够 `max(0.3 s, est_dur × (1 − 1/RTF_ewma))` 再开始出声，`RTF_ewma` 用本会话最近 N 句的实测值。RTF ≤ 1 时只保留 0.3 s 的底线。目标是把卡顿从"句内多次"变成"句前一次等待"。句间不要插静音（上一句播完时下一句已经攒够就直接接上）。
2. **环形缓冲改成 numpy**：预分配 float32 数组、切片拷贝，回调里只做一次切片，锁只保护索引。去掉 `tolist()`。
3. **遥测拆开**：每句报 `t_dequeue`、`t_first_chunk`、`t_last_chunk`、`synth_rtf =（最后一块 − 取到命令）/ 音频时长`、`prebuffer_s`，以及 **`underflow_in_sentence`（第一块播出之后的欠载次数和静音时长）**；首块之前的空等单列，不计入卡顿。
4. **争用定量（ABBA，持机器锁，fresh 进程）**：同一段 SPE 前 5 分钟切片，分别跑 TTS 单独 / +ASR(GPU.0) / +ASR+MT(NPU) / +ASR+MT(GPU.0) 四种配置，报每种的 synth_rtf P50/P95。若 MT 在 NPU 时明显更差，客户包默认 `mt=GPU.0`（device_config 默认值和 GUI 推荐都要改）。RTF 仍 > 1 的部分只记录，**是否需要再降 RTF 由 TTS 模块处理**（reviewer 会转告），App 侧不要自己改模型。

### 二、问题③：CUDA 越拖越久、最后全丢 —— GPU 不是瓶颈；根因是积压估算和丢句策略有误，加上边车 IPC 在中途丢弃后错位，最后合成线程卡死
**1) CUDA 确实在 GPU 上跑，而且够快**：边车日志 `就绪：NVIDIA GeForce RTX 5050 Laptop GPU / torch 2.11.0+cu128`，`tts_cuda_sidecar.py` 用 `device='cuda', dtype='bfloat16'`，`Talker CUDA graph captured!`；只在启动时加载一次，没有每句重载。CUDA 实时②里没被缓冲卡住的句子墙钟/音频比是 0.23–0.78（含首包），与离线 0.52–0.61 一致；**41 句里 19 句合成结束时缓冲已满**，说明合成在等播放。⇒ **GPU 占用低是正常的**（大部分时间在等 3 s 的环形缓冲腾出空间），不是缺陷。

**2) 积压估算偏高，丢句丢的是快播完的句子，而且丢了也没有减少积压**（`tts_service._update_backlog` L1445–1524）：
- 已经写进缓冲（`written`）的句子**每句**按 `min(3.0, dur_s)` 计入积压。但 3 s 是**整个缓冲**的容量，两句同时处于已写入状态时会按最多 6 s 计。例如 10:51:19：id64 和 id65 都已写入，积压报 11.0 s，丢了 3 句。
- 丢句循环**先丢已写入的句子**，而且还要再丢至少 1 句。全程 19 次"音频未被播放完（已被中止）"，其中 **10 次剩余不到 1 s**：id27 只剩 896 样本（0.04 s），id28 剩 0.11 s，id64 剩 0.59 s。
- `wait_consumed` 收到中止后**不清空缓冲**，这些句子剩下的音频照样播出来。⇒ **丢已写入的句子不会减少任何实际积压**，只会让统计里多出丢句、让用户听到句尾被截断的提示。
- 未合成的句子按 `中文字数/5 + 其他字符/15` 估算。CUDA 实时②里 130 句用了 565 s 墙钟，已合成的 41 句平均 3.6 s/句 ⇒ **需要播的量约为实时的 0.83 倍**，本来就接近 1。再加上句间首包空档、估算偏高和多丢，就成了"越拖越久"。

**3) 边车 IPC 在中途丢弃后错位（确定的 bug）**：`tts_cuda.CudaTTSEngine.generate_stream` **不核对 `rid`**，边车也**不支持取消**。worker 在 `for w in chunks` 里因为丢弃而 `break` 时，边车还在把这句剩下的块和 `done` 写进 stdout；下一句发出请求后，先读到的是**上一句剩下的块和上一句的 `done`**。
- 证据 A：每次中途丢弃（"合成中途被丢弃"）之后，下一句经常"引擎没有产出任何音频"，因为读到的第一条就是旧的 `done`。全会话 5 次：10:40:15（第 22 句）、10:42:07（第 5 句）、10:47:52（第 16 句）、10:49:43（第 41 句）、10:51:03（第 61 句），每次都紧跟在同一轮丢弃之后。
- 证据 B：10:51:25 id67 中途丢弃后，**id69 只合成出 3840 样本（0.16 s，1 块）**，这正是 id67 剩下的尾块加上它的 `done`。**从这里开始，以 id N 播出的其实是第 N−1 句的音频**，播出内容与字幕错位。

**4) 最后卡死 = "全部丢弃"**：10:51:37 id72 的合成遥测之后，**一直到 10:55:55 用户关闭语音输出**，worker **再也没有任何合成遥测，也没有任何"合成中途被丢弃"**；ids 73–129 全部是主进程按积压发出的 cancel（`收到丢弃指令` 一直到 10:55:05 都还有，说明 worker 的命令线程是活的）。边车没有 stderr 输出，也没有 `CudaTTSError`，说明边车进程没退出。⇒ **持有 `_synth_lock` 的合成线程卡在 `generate_stream → _readline → proc.stdout.read(4096)` 的阻塞读上**。`_readline(timeout=300)` 的超时只在两次 read 之间检查，阻塞读本身永远不会超时；`for w in chunks` 里的取消检查也只在有块到达时才执行。主进程那边积压估算只剩按字数估的部分，持续大于 8 s，于是来一句丢一句 ⇒ 用户听到的"最后全部被丢弃"。
（边车那一侧为什么不再输出，日志里没有逐请求的记录，无法定性。可能是错位后两边对"还剩几个回复"的判断不一致而互相等待，也可能是边车自己卡住了。⇒ 要求⑤加上边车逐请求记录。）

**5) 其他并存问题**：worker 每收到一条 `synth` 就**新开一个线程**去抢 `threading.Lock`，而这个锁**不保证先来先得**，会话一长就有几十个线程在排队，句子顺序得不到保证；`_tts_cuda` 边车每块还要多扣留一块（`pending`），多出约一块的首包延迟。

**修改要求（CUDA 和积压）**：
1. **IPC 协议**：客户端严格按 `rid` 过滤，丢弃 `rid` 不符的消息（包括旧的 `done`）。中途 break 时要么把本请求剩下的部分读完并丢掉（在后台排空线程里做，不占合成锁），要么给边车加 `cancel` 命令（边车在两块之间检查 stdin 或一个取消标志）。**两种做法都必须保证下一句只会收到自己 `rid` 的块**。
2. **不能无限阻塞**：边车 stdout 改成由专门的读者线程读进 `queue.Queue`，`generate_stream` 用 `queue.get(timeout=…)` 取，同时每次检查本句是否被取消。看门狗：已发请求但 N 秒（如 15 s 或 3×预计时长）没有任何块 ⇒ 记日志、杀掉并重启边车、本句记为失败。**不允许再出现"worker 活着但几分钟不合成"的情况**。
3. **合成调度**：改成**单一合成线程加 FIFO 队列**（`queue.Queue`），不再每句开一个线程抢锁。cancel 只是把队列里的条目标记为丢弃。
4. **积压口径**（不改 `BACKLOG_MAX_S=8`，APP-024 已裁定）：积压 = **环形缓冲里实际剩下的样本时长（只算一次，最多 3 s）** + 正在合成的句子剩余的预计时长 + 排队句子的预计时长。字数估算要用本会话实测的"音频秒/字"做 EWMA 校准，不要写死 5 字/秒。**已经写进缓冲或已经开始播的句子一律不丢**，只丢**还没开始合成的整句**（从最旧的开始）。丢的时候按"至少降到阈值以下"计算，不要每次多丢一句。
5. **边车逐请求记录**：rid、收到请求的时刻、第一块、`done`、块数、异常，写进会话日志（或单独的 `tts_cuda_trace.log`）。

### 三、问题④：克隆没生效 —— 不是隐性 bug，是**功能还没接入**（GUI 已有明示，但用户在界面上看不出来）
- 会话日志里有 4 次：`[tts] 「跟随说话人（克隆）」尚未启用（等 ASR-013 / TTS-019 交付）⇒ 本次使用预设 A`（10:41:39、10:41:45、10:42:44、10:46:03 …），出自 `live_caption_app.py` L2805–2812，**明确把 voice 改回 'A'**。worker 随后报 `speaker embedding 就绪：…preset_A.wav`；CUDA 路径报 `CUDA 后端自行使用参考音频做音色：…preset_A.wav`。
- 底层也没有可用的克隆通路：
  (a) App 和 `tts_service` **从来不发 `clone` 命令**（grep 结果是 0 处发送）；
  (b) worker 里的 `_update_clone/_extract_cond_ov` 是**旧 Confucius4-TTS 的死代码**（依赖 `ov_runtime` 里的 w2vbert/CAMPPlus/clone_C.npz，Qwen3-TTS/BabelVox 路径只看 `self.speaker_embed`），而且它还会**把克隆音色写盘**到 `voices/clone_C.npz`，违反 APP-022 的隐私约定（x-vector 只能留在内存）；
  (c) CUDA 边车的 `ref_audio` 在启动时就固定为 preset_A，`generate_stream` 忽略 `speaker_embed`。
- 结论：BRIEF 里说的"克隆当前说话人（开关）"在换成 Qwen3-TTS 之后**一直没有重新实现**。§APP-022 的"跟随说话人（克隆）"只是预留接口。问题出在 **GUI 允许用户选这个选项，提示却只写进日志和一行状态文字**，用户以为已经生效。

**修改要求（克隆）**：
1. 本轮接入**"克隆当前说话人"**（不依赖 pyannote，APP-022 的按说话人切换仍然后置）：主进程从 ASR 输入的 16 kHz PCM 里取最近 3–10 s 的语音（去掉静音），定期（如每 30 s，或累计到 ≥ 6 s 新语音时）发给 worker。
   - NPU 和 GPU：用 `tts_engine.speaker_embedding()`，也就是包里 BabelVox 的 x-vector，把结果换成 `self.speaker_embed`，下一句起生效。
   - CUDA：边车新增 `set_ref` 命令，把内存里的 PCM 或嵌入传给 `generate_voice_clone_streaming`。**不能把临时 wav 落盘**；如果库只接受路径，就用会话结束即删除的临时文件，并在 STATUS 里写明。
   - 更新失败要显式写日志，回落到预设 A，GUI 上要能看见当前实际使用的音色（"预设 A" / "克隆（更新于 hh:mm:ss，x s 语音）"）。
2. **删除** `_update_clone/_extract_cond_ov/_load_conds` 里写 `clone_C.npz` 的死代码，或者改成只在内存里保存。打包闸门要拦 `clone_*.npz` 和 `tts_speakers/` 里的用户音色。
3. 在克隆真正接入之前，GUI 选项要**改名或置灰**，写成"跟随说话人（克隆）— 未启用"。不能让用户选了以为在用。

### 四、顺带两处（不单独验收，随本轮一起改）
- **APP-025 的"本进程直接播放测试音"在 pythonw 下失败**：10:36:18 和 10:36:32 两次都是 `打开输出设备失败：AttributeError: 'NoneType' object has no attribute 'write'`（pythonw 下 `sys.stdout/stderr is None`，有代码直接往上写）。是 worker 那条路径救了回来。⇒ 修好后，用户启动方式下这条路径必须单独成功。
- **桩测试污染了用户真实的 LOCALAPPDATA**：10:42–10:46 有 `PKG_HELLO_MARKER/PKG_CRASH_MARKER/STUB_BOOM` 写进了用户的 session_*.log 和 tts_worker_error.log（14 个短日志文件），而且是在用户实测的同时。⇒ 自动化测试一律设置独立的 `LOCALAPPDATA`（或 `LIVECAP_DATA_DIR`）。

### 验收（全部要按用户的启动方式：桌面快捷方式 → v1.5 包 pythonw；reviewer 拉原始日志核对）
- **V1 CUDA 连续实时**：260902_SPE **前 5 分钟固定切片（00:00–05:00）**，`--speed 1`，GUI 实时模式，持机器锁（**同时没有其他模块的计时作业**）。逐句报 `queued_s`、`synth_first_s`、`synth_rtf`、`prebuffer_s`、`underflow_in_sentence`（次数/毫秒），以及丢句数（分成"未合成就丢"和"已写入被丢"两类，**后者必须为 0**），还有"没有产出音频"的次数（**必须为 0**）、看门狗触发次数（必须为 0，或者有原因说明）、积压随时间的曲线（每 5 s 一点，用 csv）。5 分钟全程**不能出现超过 30 s 没有合成的空窗**。另外开 `--tts-dump-dir` 落盘逐句 wav，抽 10 句交给 reviewer 回转写，**核对 wav 与译文按 id 一一对应（防止错位）**。
- **V2 NPU 连续实时**：同一素材和条件，并附上上面"争用定量"的四种配置 ABBA。报同样的字段。验收：句内 `underflow_in_sentence` P95 = 0（只允许句前等待），丢句率与 RTF 一起报告。RTF > 1 导致的丢句只记录、不判失败，但必须如实写出来。
- **V3 克隆**：用 SPE 前 5 分钟切片（单一男声）实时跑，开启克隆，落盘 ≥ 10 句 wav。reviewer 在本机做两件事：(a) MiniMax 回转写，CER 不劣于预设 A 同一批句子；(b) 用 CAMPPlus 算余弦相似度，**相对克隆源的相似度要明显高于预设 A 输出相对克隆源的相似度**（每句差值 > 0，且均值差 ≥ 0.15）。CUDA 和 NPU 各一组。克隆用的源音频和嵌入**不得落盘**（落盘的只有 TTS 输出的 wav）。
- **V4 用户实听**：上面修完后，通知用户按 CUDA / NPU / 克隆各听一段，只有用户本人确认才算 L4 关闭。
- 开始处理本条时，先把 `last_ack` 改成 APP-027（APP-026 是主会话推的测试时长改动，一并执行） 并写一行最近更新。代码改完后**定点同步客户包**，等 V1–V3 通过再重打 zip（APP-024③ 的 ABBA 与 V1/V2 合并做，不要分两次跑）。

## APP-028 [BLOCKING] 2026-10-27 13:22 — 用户决定：① 默认设备摆放；② TTS 连续推理加内存缓存，**取消丢句**（取代 APP-027 / APP-024 里的积压丢句部分）
<!-- 状态：已完成 -->

用户原话（2026-10-27 13:22）："默认配置，ASR/翻译都用 iGPU INT8，语音输出模型用 NPU。"
- **默认设备摆放（定案）**：ASR（R2T2 INT8）→ GPU.0；MT（Hy-MT2 INT8）→ GPU.0；TTS（Qwen3-TTS 全 NPU 配置）→ NPU。NPU 只给 TTS 独占。用户仍可在 GUI 里改设备，但出厂默认就是这一套。CUDA 不作默认。
- 用户原话："语音播放的时候，直接连续推理 TTS 音频流，不要等待播放完成，还没有播放的部分存内存缓存，这样提高系统利用率，不要使用丢句这个方式。"
- **播放架构改成生产者/消费者**：
  - 合成线程拿到 final 译文就**连续合成**，不等上一句播完。音频块写进内存里的无界队列（按句保持顺序，句内按块），不设丢句上限。
  - 播放回调只从队列取数据。句间保持顺序，不能交叉。队列空了就输出静音，同时计一次欠载。
  - **删除 BACKLOG_MAX_S 丢句逻辑**，以及所有"中止已写入句子"的路径。APP-027 里的 rid 过滤、读超时看门狗、单线程 FIFO 合成仍然要做：rid 用来保证句子和音频对得上，不再用来丢句。
  - 预缓冲：每句首块之前按实测 RTF 自适应预缓冲（RTF<1 时很小）。用户手动停止或切换会话时才清空队列。
  - 内存：报告 5 分钟测试里队列的峰值（秒和 MB）。正常情况下 RTF<1，队列不会持续增长。
  - 注意：不丢句之后，如果 RTF>1，播放滞后会**持续累积**。所以 GUI 底栏要实时显示"语音滞后 X 秒"，让用户能看到，但不丢句。
- **验收**（用户启动方式，SPE 前 5 分钟 `--speed 1`，持锁，默认摆放）：报告逐句排队等待、合成首包、RTF、句内欠载次数，队列峰值，**丢句数必须为 0**，以及结尾时的滞后。之后再用 CUDA 跑一次作对照。最后由用户实听。
- 克隆接入照 APP-027 做，只放内存。

## APP-029 [NORMAL] 2026-10-27 15:48 — FYI：pyannote 只做说话人识别（不再断句），APP-022 的预留接口随之调整
<!-- 状态：已完成 -->

用户决定（2026-10-27 15:48）：**pyannote/segmentation-3.0 只用来识别说话人，不再用来给 ASR 强制断句。**
- 依据（ASR-020 的 Opus 复算，SPE 前 5 分钟）：WER 是 baseline 7.39% 对 forced 7.52%，没有实际差异；词内切点都是 3 处，也没有差异。实时断句至少还要多等约 9.4 s 的右侧上下文，对实时字幕和 10 s 缓冲的配音插件都不可接受。
- 断句继续用 R2T2 原有的方式。pyannote 和说话人 embedding 在**旁路**运行，**不阻塞定稿**：定稿段先发出去，spk 晚到（可以晚 1–2 s）时，用 id 补发一条 spk 更新事件。说话人攒够约 3 s 干净语音之前，spk 为 null，TTS 用上一句的音色或预设 A。
- App 的预留接口：定稿事件先按原样发出；另外增加 spk_update(id, spk, spk_conf) 事件，用来更新字幕标签，以及还没开始合成的那几句的音色。已经开始合成的句子不改。仍然排在 APP-028 / APP-027 之后，现在不要集成。

## APP-030 [BLOCKING] 2026-10-27 17:03 — 日文"卡住"=生成不收尾撞 2048 帧上限：TTS 从不收到 Japanese（_guess_lang 只分 zh/en），且无失控守卫，一句失控把后续全部堵住 1–2 分钟
<!-- 状态：已完成 -->


**来源**：用户 16:45 起实测 v1.5（客户包，桌面快捷方式，device_config tts=CUDA），原话"TTS 英文还可以，日文发音偶发卡住"。
**reviewer 读了**：`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261027_162933.log`、`session_20261027_164556.log`、`tts_cuda_trace.log`；包内 `app/{tts_worker,tts_cuda,tts_cuda_sidecar,tts_engine,tts_service,live_caption_app}.py`（与 dev `live_caption/` 同一实现，dev tts_worker.py L2102/L2161 相同）。

### 1. 卡住的形态（证据来自原始日志）
- **不是**欠载、**不是**边车 2 s 读超时、**不是**整句延迟到达，是**生成不收尾撞帧数上限**：
  - 会话 16:38（CUDA·follow_speaker）**id=65 / rid=66，文本仅 7 字**：16:43:06 REQ → 16:44:52 `DONE rid=66 chunks=255 elapsed=106.61s`；合成遥测 `samples=3912960 parts=255` = **163.0 s 音频 = 2038 帧 ≈ 2048 上限**（qwen_tts 默认 max_new_tokens=2048，边车没传）。正常句 s/char 0.10–0.40，这句 **23.3 s/字**。`rms_dbfs=-37.9`（同会话正常句 −26~−32）⇒ 用户听到的是 ~106 s 低电平含糊/气声长拖。
  - 边车串行 ⇒ 这 106 s 里后续句全部排队：16:44:52 `语音滞后 38.8s（…排队 48.3s）`；16:43:16/16:43:32 两次 set_ref 也被堵到 16:44:52 才执行。
  - **第二例**：会话 16:45:56（CUDA·follow_speaker）**rid=16 len=40**：16:48:08 REQ 后**直到 16:49:10 关闭都没有 DONE（≥61 s，正常 40 字约 3.5 s 合成）**，期间无"边车响应超时"报错 ⇒ 块一直在来 ⇒ 同样是失控生成；16:49:09 `drain 超时：仍有 9 句未完成` ⇒ 9 句作废。
- 对比（同一边车、同一 RTF 水平，排除性能原因）：

| 会话 | 句数 | s/字 中位 | 边车 RTF 中位 | 欠载总数 | 撞上限/挂起 |
|---|---|---|---|---|---|
| 16:30 CUDA·A | 53 | 0.208 | 0.66 | 76 | 0 |
| 16:38 CUDA·克隆 | 77 | 0.172 | 0.70 | 247 | **1（id=65）** |
| 16:46 CUDA·克隆 | 15 | 0.142 | 0.68 | 107 | **1（rid=16）** |

  16:38/16:46 两场 s/字 0.14–0.17 符合日文（mora 密度高），16:30 的 0.21 更像中文。⚠️ **会话日志不记目标语言、不记译文、不落 wav** ⇒ "哪几句是日文"只能这样推断，reviewer 拿不到出事句音频（见修法⑤）。
- 附带确认（同一会话里的另一个 bug）：每次 CUDA 会话的**第 0 句都被丢**（16:31:22、16:47:10 `边车响应超时（2 s）`，而边车 3.09 s 后其实 DONE）。原因：`tts_cuda._q_get()` L476-480 在 `queue.Empty` 时直接 `raise CudaTTSError`，`generate_stream` 用 `timeout=min(2.0, wl)` 调它 ⇒ **任何 2 s 无块都直接判失败，WATCHDOG_FIRST_S=60 / WATCHDOG_S=15 从来没生效**，被丢请求也没排空（trace `DROP rid=2 got_rid=1`×4）。

### 2. 根因
① **TTS 永远不会收到 Japanese（确定，代码级）**：`tts_service.submit()` 下发的 synth 命令只有 `id/text`，**不带目标语言**；`tts_worker._guess_lang()`（L2161）只按"汉字占比 ≥25%"二分 zh/en；`_synth_babelvox()` L2102 `blang = 'Chinese' if zh else 'English'`。边车 `_lang()` 虽支持 Japanese，但永远收不到。CUDA/NPU 都走这条（NPU 是 `tts_engine.stream(language=blang)`）。reviewer 本机用同一函数测 8 条日文样句：**5 条判 en**（ありがとうございます。/はい、そうです。/これはテストです。/2026年の売上は52%増えました。/プロセッサーのパフォーマンスが向上しました。），**3 条判 zh**（今日は会議があります。等）。
   - 判 en ⇒ 用 English 语言 token 读假名 ⇒ 分布外 ⇒ EOS 不稳 ⇒ 偶发撞 2048 帧（短的纯假名句最危险，与 id=65 只有 7 字吻合）。
   - 判 zh ⇒ 用 Chinese token 读日文，且 `normalize_zh_numbers` 误作用（2026年→二零二六年、52%→百分之五十二，按中文读）。
② **无失控守卫（放大器）**：边车不传 `max_new_tokens`（默认 2048 = 163.8 s）；客户端看门狗只管"多久没块"，不管"块太多"；边车不可取消 ⇒ 一句失控把整条语音链和 set_ref 堵住 1–2 分钟，关闭时整批作废。
③ `_estimate_sec()` 只数汉字和英文词，**不数假名/韩文** ⇒ 日文长句被低估、`split_long_text` 不切（NPU 有 478 帧桶上限，会截断或失控）。
④ `_q_get` 2 s 即抛（见上）⇒ 每场第 0 句必丢、看门狗是死代码。

### 3. 要做
① **目标语言显式下传**：TtsService 从 MT 当前目标（含会话中途改下拉）取语言，synth 命令带 `lang`；worker 映射 zh/en/ja/ko → Chinese/English/Japanese/Korean，CUDA 边车和 NPU babelvox 都用它。`_guess_lang` 只作兜底，并补假名（U+3040–30FF）→ ja、谚文 → ko。`normalize_zh_numbers` **只在 Chinese** 时执行；日文数字规则交 TTS 模块定，App 先保持原样不转。NPU babelvox 若不支持 Japanese 语言 id，要明说并在 GUI 标注，不得静默回落 English。
② **失控守卫**：按语言估帧（ja ≈0.15 s/字、zh ≈0.25 s/字、en ≈0.07 s/字符，起停另加余量），边车传 `max_new_tokens = clamp(3×估计帧数 + 36, 48, 2048)`；客户端再加一道：本句已收音频 > max(3×估计, 估计+8 s) ⇒ 判 RUNAWAY ⇒ 停止播放该句剩余部分，并让边车停止（加 cancel 命令，边车每块检查一次；做不到就杀掉重启），trace 写 `RUNAWAY rid len frames est`。NPU 路径同样加。
③ `_q_get` 在 Empty 时返回到循环（不要抛），让 15/60 s 看门狗按设计生效；第 0 句不得再丢。
④ `_estimate_sec` 补假名/谚文计数。
⑤ **可观测性**：会话日志每句记 `id / lang 实际下传值 / 字数 / 估计帧 / 实际帧 / 结束原因（eos|cap|runaway|cancel）`，切换翻译目标时记一行；异常句（cap/runaway/超时）自动把 wav 和文本落到 `%LOCALAPPDATA%\Confucius4LiveCaption\tts_anomaly\`（最多保留 20 个，只留本机，不进包）。

### 4. 验收
- **A/B 证明根因**：准备 ≥20 句日文测试句（≥5 句 ≤8 字纯假名短句；≥4 句含数字/日期/百分比；≥4 句片假名长词；≥3 句 ≥60 字长句，其中 1 句无标点；≥3 句混英文缩写如 CPU/AI），**改前**（lang=English/Chinese 现状）与**改后**（lang=Japanese）各跑，CUDA 与 NPU 各一组，每组每句 ×3 次（失控是随机的，单次不够）。逐句报告：实际下传 lang、字数、帧数、s/字、欠载次数、结束原因。**改后**两个后端都要满足 撞上限=0、重复=0、挂起=0、RUNAWAY=0，第 0 句丢失=0；改前的撞上限次数如实报告（用来证明根因）。
- 中文和英文各 10 句回归：改后帧数/s/字与改前一致（无回退）。
- GUI 复现：克隆开 + 日文目标，SPE 前 5 分钟 `--speed 1`（持机器锁），报告丢句=0、最大滞后、异常句数。
- wav + json 交给 reviewer：先跑 `quota.py`，5 小时区间剩余 ≥20% 才做 MiniMax 回转写（不足就推迟，不阻塞其余验收）。改后日文 CER 不得劣于改前非失控句。
- 开始处理本条时先写 `last_ack` 和一行最近更新。

## APP-031 [HIGH] 2026-10-27 17:47 — 优先级提醒：先做 APP-030（日文失控），再做 APP-028/027 的实测验收
<!-- 状态：已完成 -->

- reviewer 17:47 核对：APP-030 [BLOCKING] 17:04 已推送，但 STATUS 里没有提到，live_caption 也没有改动。你 17:18 做了 v1.5→v1.6 升版重打，这一步可以理解（排在 APP-030 之前）。
- 接下来的顺序：**① APP-030**（lang 显式下传、帧数上限加失控中止、_q_get 看门狗、异常句落盘；用户实测已经复现过两次）→ **② APP-028 的不丢句实测**（SPE 前 5 分钟，丢句数 = 0）→ **③ APP-027 的 V1–V3**。三项做完后合在一起重打一次包，不要每项都单独打包。
- 开始时写 last_ack=APP-030 和一行最近更新。

## APP-032 [NORMAL] 2026-10-27 20:38 — RESUME：额度已重置，请从 last_ack 继续
<!-- 状态：已完成 -->

- 未完成：**APP-030 [BLOCKING]**（日文失控：lang 显式下传、帧数上限加失控中止、_q_get 看门狗、异常句落盘）→ APP-028 的不丢句实测（SPE 前 5 分钟，丢句 = 0）→ APP-027 的 V1–V3。顺序见 APP-031。
- 下一步：写 last_ack=APP-030，先修日文失控。

## APP-033 [NORMAL] 2026-10-28 00:50 — 回应 STATUS 头部阻塞③/CUDA 组：quota.py 在 reviewer 本机；CUDA 边车不是本机 torch
<!-- 状态：已完成 -->


1. quota.py 和 MiniMax 回转写都在 reviewer 本机执行（~/target_review/common/tools/quota.py），目标机上本来就没有、也不需要。你们只负责把 wav+json（含逐句 jsonl）放到固定位置，额度门由 reviewer 把关，不是你们的阻塞项。
2. CUDA 组：用户 10-27 16:30–16:46 的实测走的是 CUDA 边车（tts_cuda.py + 边车自己的 python），不依赖 dev/包内 python 的 torch。请按 tts_cuda 实际使用的边车解释器做 CUDA A/B（日文 29 句×3 改前/改后，撞上限/RUNAWAY/挂起=0），不要以"主 python 无 CUDA torch"为由跳过。找不到边车解释器再如实写明路径和报错。
3. 提醒：§79.4 只是 60 秒冒烟（17 句，最大积压 21.31 s、synth_rtf P50 1.02），不是 APP-028 要求的 SPE 前 5 分钟；5 分钟实测、V1–V3（app112）跑完前不写"丢句=0 已验收"。

## APP-034 [NORMAL] 2026-10-29 10:05 — FYI：用户决定方案 A（TTS 不等 spk）
<!-- 状态：已完成 -->

- 用户决定（10-28，方案 A）：**TTS 不等说话人标签**。spk 还没到时，用上一句的音色或预设 A；换人后头一两句音色可能不对，这可以接受。字幕、翻译、语音都不为说话人识别增加延迟；强制断句不恢复。只作通知，不新增要求。
- App 侧：spk_update 只影响还没开始合成的句子（APP-029 不变），不要让 TTS 队列等 spk。

## APP-035 [BLOCKING] 2026-10-29 10:18 — FTP 已由用户永久关闭：不得重发 v1.6 到 FTP、不得运行 publish_ftp.py / 启动任何 FTP 服务
<!-- 状态：已完成 -->


读了：STATUS §90.6、§91.8（L15907–15927、L16163–16166）："v1.6 未发布到 FTP ⇒ 客户从 FTP 拿到的仍是旧的 ⇒ 是否重发待 reviewer 裁定"。

裁定（不是待定项）：
1. 用户 2026-10-25 已决定**关闭 FTP**（当时 FTP 暴露了整个用户目录）。这是用户决定，reviewer 无权也不会批准重开。**不得**运行 `publish_ftp.py`、不得启动 ftp_share/任何 FTP/HTTP 文件服务、不得为分发新开共享。
2. "客户从 FTP 拿到的仍是旧的"这一前提不成立：FTP 已不是分发渠道。STATUS 里把"是否重发 FTP"列为待裁定的条目，全部改成"FTP 已关闭（用户 10-25 决定），不适用"。
3. 分发方式：v1.6 zip 留在目标机原位（写明绝对路径 + 字节数 + SHA256），由 reviewer 用 SSH/SFTP 拉取；如需其他渠道，由用户另行指定。App 不自行选渠道。
4. `FTP_Share/` 里的 v1.4/v1.5 旧副本：不删、不动（删不删由用户决定），STATUS 里也不要再写成"客户可从此获取"。

验收：STATUS 下一节写 last_ack=APP-035，并且有一行"FTP 已关闭，不重发"；procs 里没有 ftp 进程；zip 的路径、字节数和 SHA256 写进头部。

## APP-036 [HIGH] 2026-10-29 10:18 — APP-028 的语音滞后（最大 69–103 s）主要不是 TTS RTF，而是"中文语音时长比英文原声长"；遥测有 3 处口径错，要修；追赶策略等用户决定，不要自己改
<!-- 状态：已完成 -->


读了（原始文件，reviewer 拉回本机复算）：app028_soak/{app028_soak_report.json, app028_soak.wav.tts.jsonl（76 行）, app028_soak_cli.log, app028_backlog_curve.csv}；app027_v1/cuda_rerun_run_20261028_210551/{v1_cuda_report.json, v1_cuda.tts.jsonl, v1_cuda_backlog_curve.csv}；app027_v2/tts_asr_mt_npu/run_20261028_212525/{report, jsonl, csv}；代码 tts_worker.py L1415–1422、tts_service.py L1122、L1666–、live_caption_app.py L3632、L4205。

A. 已核实的数字：soak 76/76/0、synth_rtf p50 1.0069 / p95 1.1511、max_backlog 68.79 与原始字段一致。

B. 滞后曲线（reviewer 根据 cli.log 里事件的先后顺序，把每句译文的到达时刻对到 worker 时间轴上重建；soak 是落盘模式，播放按实时连续播放模拟）：
   - 起步约 11 s（含 TTS 加载），t≈20 s 时 17 s，t≈118 s 时 25 s，t≈192 s 时 38 s，t≈232 s 时 53 s，说话结束时约 64–67 s，**基本单调线性上升，斜率约 0.18–0.2 s/s**。和 max_backlog 68.79 吻合。
   - 合成器从第 0 句到第 75 句**一直没有空闲**（每句的 t_submit 都等于上一句的 t_done），App 下发排队约等于 0。⇒ **不是 App 侧排队/串行造成的。**
   - 76 句中文音频总时长 **338.8 s**（1657 字，0.204 s/字，约 4.9 字/s），对应的英文原声只有 300 s。⇒ 播放速度最多只能是 1.0×，只要中文比原声长 13%，**不管 TTS 多快，滞后都会以约 0.13 s/s 的斜率累积**，5 分钟下来至少 35–40 s，再加上起步延迟。
   - 反证：V1 CUDA 重跑 synth_rtf p50 **0.56**（远小于 1），max_backlog 照样 **77.27 s**，曲线 8.6→28→36→47→51→61 s（t=64→287 s），大头是"队列"（已经合成、等着播放）。⇒ RTF<1 也消除不了。
   - 拆分（soak 说话期间）：合成器需求 ≈1.19 音频秒/墙钟秒，实际产能 1/1.049≈0.95 ⇒ 积压增长约 0.24 s/s，其中约 80% 来自中文时长更长，约 20% 来自 NPU 并发下 RTF 1.05。V2 NPU 臂 RTF p50 1.09，max 103 s，RTF 部分的占比更大。
   结论：用户感到的"越听越落后"主要是时长问题，TTS 提速只能缓解一部分。

C. 要修的遥测口径（App 职责）：
   1. worker jsonl 的 `t_submit` 是在 `_synth_babelvox` 开头取的 `perf_counter()`（L1415），也就是**开始合成的时刻**，所以 `t_dequeue==t_submit`、`queue_lag_s` 恒为 0；App 侧"首包分段 排队 X s"= t_sent−t_submit，只算了 App 自己那段。⇒ soak 报告的 `seg_queue_p50=0.0`、id≥4 的"排队 0.000 s"都是假的，worker 里实际排队 7–55 s。改法：worker 读到 stdin 命令时记 `t_recv`，jsonl 里加 `worker_fifo_wait_s = t_dequeue − t_recv`，报告给出 P50/P95/max。
   2. `app028_backlog_curve.csv` 只有收尾时的 1 行，不算曲线。改成每 1–2 s 采样一次 `backlog_s / backlog_parts / lag_s`（在落盘模式下也要采），并按 1 s 粒度用 `source_t` 对齐。
   3. `end_lag_s=0.0` 是 drain 之后取的值，没有意义。新增 `end_lag_s = 最后一句播完（或写完）的时刻 − 源音频结束时刻`，播放模式和落盘模式各自给出。
   4. CLI 收尾的统计行在 `close()` 之前打印（L4205 drain(120) → stats → close），所以 §82 那次"丢弃 0"实际作废了 51 句。改成 close() 之后再打印一次最终统计，或者把 drain 超时设为 max(120, 1.5×当前积压)，并在报告里列出 `n_discard_on_close`。

D. 不要自己做（等用户决定，reviewer 已上报）：追赶策略，例如滞后超过 X s 时把播放速度提高到 1.15–1.25×、TTS 语速参数、MT 简洁模式。用户已决定不丢句，**不得恢复任何丢句或跳句的做法**。
   可以先做的零风险准备：用现有 soak 的 jsonl 离线模拟"播放 1.1×/1.2×/1.3× 时的滞后曲线"，只给数字，不改产品。

验收：C1–C4 改完后，用 SPE 前 5 分钟 NPU 默认配置、播放模式（不加 --tts-out，或者落盘和播放并行）重跑一次。报告给出滞后曲线（≥100 个采样点）、worker_fifo_wait P50/P95/max、end_lag_s、n_discard_on_close=0，以及 B 段"中文时长/原声时长"这个比值。

## APP-037 [HIGH] 2026-10-29 10:18 — APP-030 复核：CUDA/NPU 引擎级 cap/hang=0 已核实，回转写改后不劣于改前；但"lang 显式下传"没有任何流水线级证据，日文 GUI 5 分钟未做；句首标点由 App 剥离（reviewer 裁定）
<!-- 状态：已完成 -->


读了：app030_cuda_ab_fixed/cuda_ja_ab_report.json（194 行）、app030_npu_ab/npu_ab_report_full2.json（194 行）、代码 live_caption_app.py L3273（GUI 下传 `lang=self._cur_mt_target()`）、L4131/L4165（CLI 下传 `lang=mt.target`）、tts_worker.py L1427（lang_src）。

A. 已核实（逐行重算）：
   - CUDA：改前 ja 87 行中 2 行 `cap`+hang（lang_down=English）；改后 87 行全部 `eos`、lang_down=Japanese、hang/error=0；zh/en 回归 20 行全部 eos。frames/max_new_tokens 的最大值 0.40（离上限很远）。和 §80.2 一致。
   - NPU：改后 87 行全部 eos、engine_lang=Japanese。**注意**：这份报告的时间是 10-27 23:43，用的是**修语料之前**的旧语料（含"，动きます"和纯中文长句），也没有 `wav` 字段。
   - reviewer 回转写（MiniMax asr-1.0，quota 96%）：CUDA 同 20 个 seq（rep1），改后字符 CER **9.8%**，改前 **23.2%**。改前判成 en/zh 的句子明显念错，例如 "在库哇一千个阿里马斯"、"Donki mas"、"FPEルートINTハノ"。改后剩下的大多是写法差异（パーセント→%、Throughput→スループット）。真正的错误有 3 个：seq16 "アクセラレーション→アクセlrtion"、seq27 "VRAM→VRM"、seq21 "第4→第44"。⇒ "改后 CER 不劣于改前"成立。

B. 缺证据：
   1. **"lang 显式下传"只在引擎级测过**（测试脚本直接调 tts_engine.stream(language=...)）。reviewer 在目标机上搜了 app027_v*/app028_soak/results/app/LOCALAPPDATA 下所有 *.jsonl，**没有一行 `lang=ja`**；现有流水线 jsonl（soak、V1、V2）都是 zh+explicit。要求：用 CLI 流水线（`--translate ja`，SPE 前 5 分钟，NPU 默认配置，持锁）跑一次，逐句 jsonl 76±句全部 `lang=ja`（或 Japanese）+ `lang_src=explicit`，cap/runaway/hang/err=0，逐句 wav dump。CUDA 可选。
   2. NPU 组用修好的语料（97a8bb91…）重跑改后臂 29×3，带 wav 字段并 dump wav（reviewer 要回转写）。
   3. 日文 GUI 5 分钟（用户启动方式：桌面快捷方式 → 包内 pythonw，目标语言选日文）仍未做。会话日志里要能看到 lang=ja。

C. 句首标点（§80.7 第 1 项）reviewer 裁定：在 **tts_worker 合成前统一规范化**：去掉句首的标点和空白（全角/半角），去掉后为空就不合成，记 `end_reason=empty`，**不计丢句**。三道失控守卫保持不变。加单测：句首"，"、"、"、"。"、"…"和纯标点各 1 条。

验收：B1 的 jsonl+wav 路径和计数；B2 的报告+wav；C 的单测 PASS 和 commit。B3 等用户在场时做，不阻塞 B1/B2。

## APP-038 [NORMAL] 2026-10-29 11:00 — FYI：目标机 NPU 驱动已升级到 32.0.201.14005（用户要求，用于 WSL 里跑 OVMS 对比）
<!-- 状态：已完成 -->

- 旧驱动 32.0.100.4778，新驱动 32.0.201.14005（CI 构建）。App 下次用 NPU 跑 TTS 时，编译缓存可能失效，冷启动会变长，属于正常现象。如果出现 NPU 编译失败、数值异常或明显变慢，在 STATUS 里记下来，由主会话决定是否回退驱动。不需要专门去测。

## APP-039 [BLOCKING] 2026-10-29 14:38 — 用户实测：语音克隆的设计错了。音色要**按句绑定原说话人**，换人时**一次性**切换；不能随时间渐变，也不能后台一直采样
<!-- 状态：已完成 -->

用户原话（主会话转达）：
1. "语音音色切换非常滞后，超过了 10 s 的预期。"
2. "即使切换，音色也不正确，比如男声切女声，它是从一个低的音色逐渐切换到高的音色。设计本意是克隆原始说话人的音色，不是渐变。"
3. "感觉后台一直持续不断在采样克隆，应该是检测到说话人切换的时候才做采样克隆的动作，减少冗余计算量。"

**reviewer 判断的可能原因（请先在代码里确认，把证据写进 STATUS）：**
- 现在的克隆是"滑动窗口 + 定时重算 x-vector + 平滑（EMA/均值）"：窗口里混了两个人的声音，平滑又让向量慢慢挪过去，于是出现"低音逐渐变高"的渐变；定时重算就是用户感觉到的"一直在采样"。
- 音色是按**合成那一刻的"当前音色"**取的，没有绑定到句子所属的说话人。现在是连续合成、不丢句，队列里已经合成好的句子都用旧音色，再加上播放本身落后几十秒，所以用户听到换声的时间远远晚于实际换人的时间。

**正确的设计（必须这样改）：**
- **音色按句绑定**：每个定稿段带上 spk（来自 ASR 的说话人旁路，见 ASR-021/028）。TTS 合成这一句时，用 **这一句的 spk** 对应的音色，跟"当前时间"无关。句子在队列里等多久都不影响它用谁的声音。
- **说话人音色表**：spk → x-vector（TTS 自己的 speaker encoder）。**只在出现新 spk 时取样一次**：用这个人最先攒够 ≥ 3 s 的干净单人段（无重叠）提取 x-vector。同一个人之后最多再细化 1–2 次（攒到 6 s、10 s 时，用这个人自己的段重算，不和别人混）。**禁止跨说话人平滑或滑动窗口**。没有新 spk 时不做任何声纹计算。
- **切换是一次性的**：spk 变了，下一句直接用新说话人的向量，不插值、不渐变。
- **还没攒够 3 s 的新 spk**：按方案 A，先用预设 A（不要用上一个人的声音冒充新的人）。攒够之后，**还没开始合成的**该 spk 的句子改用克隆音色；已经合成的不重做。
- spk 来源：集成 ASR 的说话人旁路（ASR 线程会提供可以 import 的接口）。在接口交付前，不要自己再写一套持续采样的方案；克隆模式先标"实验"，GUI 上显示每句实际用的是哪个 spk 和哪个音色。
- 内存：说话人表只放内存，会话结束清空，不落盘。

**验收：**
- 用 SPE 会议 38 分钟后的 Q&A 段（多人对话，ASR-028 会交付 spk 标注 shared/spe_qa_spk.json 和 densest_5min 窗口），走 App 实时路径，克隆模式开：
  ① 每句实际用的音色和该句 spk 一致的比例（报告混淆表）；
  ② "换人那句的源音频结束"到"用新音色的那句开始播放"之间，**不算播放排队的延迟**（单独拆出 spk 判定延迟 + 取样延迟）；
  ③ 声纹计算的次数和总 CPU/设备时间（应 ≈ 说话人数 × 1–3 次）；
  ④ 不存在渐变：相邻两句的 CAMPPlus 余弦，同一 spk 内 ≥ 阈值，换人处一步到位。
- 挑几段换人前后的配音放进 shared/app_clone_listen/，由 reviewer 拉回给用户实听。用户实听是最终验收。

## APP-040 [BLOCKING] 2026-10-29 14:47 — 用户补充（细化 APP-039）：用 pyannote 检测换人，**检测到换人才克隆并切换音色，没换人就保持同一音色**；翻译字幕上显示不同的说话人
<!-- 状态：已完成 -->

用户原话："不是加了一个 pyannote 的说话人分离的模型吗？检测到说话人切换的时候再克隆切换音色，没切换之前保持同样音色。说话人切换的话，在翻译字幕上也显示出不同的说话人。"

对 APP-039 的修订（以本条为准）：
1. **触发条件**：只有 ASR 说话人旁路（pyannote 分段 + 说话人 embedding，见 ASR-029 的接口）报告 spk 变化时，才做克隆取样；spk 没变，就一直用当前说话人已经缓存的音色，不重算、不更新。
2. **换到新的人**：用这个新说话人**自己的第一段语音**取样（干净单人区间，≥ 1.5 s 就先用；攒到 ≥ 3 s 时用他自己的段重算一次，之后不再更新）。不再用预设 A 过渡，也不能用上一个人的声音。新说话人第一段如果 < 1.5 s，就等他下一段，期间这几句先保留上一句的音色，并在日志里标出。
3. **换回老的人**：直接用说话人表里缓存的音色，立即切换，不重新取样。
4. **字幕**：原文字幕和译文字幕每句前面都显示说话人标签（S1、S2…，同一个人颜色固定）。spk 晚到时用 spk_update 补标签（句子先显示，标签随后补上）。GUI 加一个开关，默认打开。
5. 其他照 APP-039：音色按句绑定 spk，切换一步到位、不渐变，声纹只放内存，会话结束清空；验收用 SPE Q&A 段，并统计声纹计算次数（≈ 说话人数 × 1–2 次）。

## APP-041 [HIGH] 2026-10-29 14:58 — 用户报 bug：启动时"语音输出"默认是"开启"，但实际没有初始化设备；必须手动取消、再勾一次才能用
<!-- 状态：已完成 -->

用户原话："App 启动的时候会默认选中语音输出'开启'选项，但是实际上并没有初始化设备，这个时候设备无法正常工作。必须去选中'开启'再选中'开启'之后，设备才能正确初始化。"
- reviewer 推测（请先在代码里确认，把证据写进 STATUS）：GUI 只是把开关变量初值设成 True，真正的初始化（启动 TTS worker、打开所选输出设备、建立播放流）只挂在开关的 command 或 trace 回调上，启动时没有调用；也可能是启动时调用了，但早于输出设备列表或配置加载完成，结果失败了却没有报错。
- 修法：
  ① 启动流程里**显式调用和点击"开启"完全相同的那个初始化函数**（同一入口，不要另写一套），放在 ASR → MT 就绪之后（沿用"依次加载、auto=False 防 GPU 编译死锁"的顺序）。
  ② 初始化失败时，开关自动回到"关闭"，状态栏写明原因并指向日志，不能显示"开启"却不工作。
  ③ 输出设备下拉框、音色/克隆选项在启动时就生效，和手动切换一次的结果一致。
  ④ 再查一下其他默认开启的选项（字幕说话人标签、克隆模式等），有没有同类"默认值没触发初始化"的问题。
- 验收（用户的启动方式：桌面快捷方式，v1.6 包）：冷启动后**什么都不点**，直接播放测试音和朗读一句，能出声；状态栏显示 TTS 就绪；日志里能看到启动时调用了初始化函数，而且只调用一次。另外测一次"所选输出设备不存在"的情况，开关应自动回到关闭并提示原因。

## APP-042 [HIGH] 2026-10-29 15:30 — 用户决定：滞后追赶采用自适应加速播放（App 和插件统一）
<!-- 状态：已完成 -->

- **用户决定（2026-10-29 15:30）：App 和插件都采用"自适应加速播放"来追赶滞后**（不改译文，不丢句，不回退到丢句）。
- 统一参数（两边一致，写成可配置项）：
  - 滞后 lag 定义为"这句的实际开播时刻 − 这句的目标开播时刻"。App 的目标开播时刻 = 源音频中这句的结束时刻；插件的目标开播时刻 = t0 + t_start + D。
  - 速度 = clamp(1.0 + (lag − 3 s) × 0.025, 1.0, 1.30)：lag ≤ 3 s 时 1.0×，lag 到 15 s 时达到上限 1.30×。另加滞回：降速时 lag < 2 s 才回到 1.0×，避免来回抖动。
  - **按句变速**：每句开播时定一次速度，句内不变；相邻句之间每次变化不超过 0.1×，听感更平滑。
  - **保持音高**：用 WSOLA 或同类时间伸缩算法（例如 audiotsm 的 WSOLA，或自写的 numpy 实现），不能用改采样率或 playbackRate 的方式，那样会变调。时间伸缩在主机侧做，不能占满 CPU（遵守 ASR-026 的线程限制，单线程）。
  - GUI 底栏显示当前语速倍率和滞后秒数。
- 验收：SPE 前 5 分钟，默认设备摆放，持锁。报告滞后随时间的曲线（起点、峰值、结尾）和各倍率的时间占比，**丢句 = 0**；挑 3 段 1.2–1.3× 的配音落盘，供用户抽听，确认不变调、可懂；reviewer 做回转写，确认加速后错误率不明显上升。
- App 侧：在 APP-036 的滞后遥测基础上实现（目标值用 end_lag_s 的口径）。排在 APP-039/040/041 之后，但可以和 APP-041 一起做。

## APP-043 [HIGH] 2026-10-30 08:48 — 主会话转达：ASR 的说话人接口已交付（ASR-029），APP-039/040 的克隆按句绑定 spk 可以接入了
<!-- 状态：进行中 -->

- 接口说明：C:\Users\Trekker-PTL\shared\NOTICE_asr_to_app_speaker_api.md（SpeakerTracker，ASR 自检 19/19）。按 APP-039/040 的规则接入：音色按句绑定 spk；只有出现新 spk 才取样（用他自己的第一段 ≥ 1.5 s，攒到 3 s 时重算一次）；换回老的人直接用缓存；切换一步到位、不渐变；字幕标签用 spk。
- 线程限制：ASR 实测把 OMP、MKL 等的线程数设为 1 后，CPU 从约 7.8 核降到约 1 核，ASR 的 RTF 还从 0.644 改善到 0.530（WER 待 reviewer 复算）。App 进程启动时也要设置同样的环境变量（在任何 numpy 或 OpenVINO import 之前），并记进日志。这一条很可能就是 App 里 TTS 被拖慢的主因（见 TTS-028）。
- 验收：用 SPE Q&A 段（shared/spe_qa_spk.json 的 densest_5min 窗口）走 App 实时路径，按 APP-039 的 4 项指标验收；挑几段换人前后的配音放进 shared/app_clone_listen/。另外 APP-041（pythonw 冷启动）和 APP-042（GUI 路径的加速播放，以及 3 段 1.2–1.3× 配音给用户实听）的真机验收一起做。
- 客户包里带不带 pyannote_seg 和 wespeaker（约 16 MB）正在等用户决定，先别打进包。

## APP-044 [NORMAL] 2026-10-30 08:50 — 用户决定：客户包**带上**说话人识别的小模型（pyannote/segmentation-3.0 和 wespeaker，约 16 MB）
<!-- 状态：已完成 -->

- 打包内容：pyannote 分段模型的 OV IR 和 wespeaker 的 OV IR（精度以 ASR 交付的版本为准，FP16 还是 FP32 由 reviewer 按 ASR-025 的复核结论通知），再加上 ASR 的 SpeakerTracker 接口代码。不要带 torch 权重，也不带 CUDA 版本。
- 许可：pyannote/segmentation-3.0 是 MIT，wespeaker 是 CC-BY-4.0，**必须在包里的 NOTICE 或第三方许可清单里署名**（来源、作者、许可证全文或链接）。ASR 已经交过 NOTICE 草稿，合并进包里的 third-party 清单。
- 客户机上运行时：说话人旁路默认放 GPU.0，限制线程（OMP 等设为 1）。模型文件缺失时，旁路自动关闭，GUI 提示"说话人识别不可用"，其他功能不受影响。
- 打包规则不变：不进会议录音、不进克隆音色、不用 FTP；重打包时把 APP-043 的真机验收证据一起带上。

## APP-045 [BLOCKING] 2026-10-30 10:53 — 用户实测发现说话人切换和克隆"还没修好"：原因是**桌面快捷方式仍指向 v1.5 旧包**；另外旧克隆把音频写到了磁盘
<!-- 状态：进行中 -->

- 证据（reviewer 10:55 在目标机上读取）：
  - 桌面"Confucius4 实时字幕.lnk"指向 C:\Users\Trekker-PTL\Confucius4_LiveCaption_**v1.5**\Start_LiveCaption.bat。你后面打的 v1.7–v1.12 改动（字幕说话人标签、APP-039/040/043 的克隆修复、APP-041/042）用户都没用上。
  - 用户 10:49 那次会话（session_20261030_104919.log）里，"音色 follow_speaker"每隔约 20 s 就把一段 clone_*.wav 写到 %TEMP%\confucius4_clone\ 再提取 embedding。这正是用户说的"持续采样"，而且**克隆音频落了盘**，违反"克隆只放内存"的规则。另外 SpeakerLibrary 从 %LOCALAPPDATA%\...\tts_speakers 加载了 cindy/lou/phil/steve 4 个音色，请确认来源和许可（是否 babelvox 自带，APP-018 曾要求移除）。
- 要做的：
  ① **立即**删除 %TEMP%\confucius4_clone\ 下的所有克隆音频（只记录删除了多少个文件，不要上传）。新代码里，克隆一律在内存中处理（numpy 数组直接送 speaker encoder），不写临时文件。
  ② 打包流程增加一步：每次出新版本并通过验收后，**把桌面快捷方式更新到最新版本**（只保留一个快捷方式，名称带版本号，例如"Confucius4 实时字幕 v1.12"），并在 STATUS 里记录。还没通过真机验收的版本不要指过去。
  ③ 等 TTS 释放锁后，按 APP-043 完成真机验收：用户启动方式 + SPE Q&A 双说话人 + 冷启动 + GUI 加速播放。验收通过后更新快捷方式，再通知主会话，由主会话请用户实测。
  ④ 确认 tts_speakers 里这 4 个音色的来源和许可；如果是测试残留，就移出用户目录，客户包里也不要带。

## APP-046 [HIGH] 2026-10-30 11:25 — 巡检规则补充：last_ack 追平后，只要还有未完成项，就自己继续做，不要空转
<!-- 状态：已完成 -->

- 背景：各线程都有每小时一次的"巡检 CORRECTIONS"自动化，但 10-29 17:22 到 10-30 09:31，TTS 线程有 TTS-029/031 未完成，却空转了约 16 小时。原因是：巡检只在出现**比 last_ack 更新的纠偏条目**时才动手；last_ack 已经追平、但手上还有没做完的事项时，它什么都不做。
- **巡检规则补充（主会话，对 ASR/TTS/App/EXT 统一）**：每小时巡检时，
  ① 有比 last_ack 新的纠偏，就照旧处理；
  ② **没有新纠偏，但 STATUS 里还有未完成的纠偏项**（"阻塞/待办/未完成"栏不为空），并且本模块没有进程在跑：**直接按优先级继续下一项**，不要等新纠偏或 RESUME；
  ③ 需要计时但锁被别人持有：排队等待（用公用锁函数），等待期间可以先做不计时的部分（写代码、离线数值、文档）；
  ④ 只有在"全部完成"或"卡在需要用户决定的事项"时才停下，并在 STATUS 头部写清楚原因。
- 主会话以后只在额度重置后推 RESUME，作为兜底。

## APP-047 [NORMAL] 2026-10-30 11:49 — 说话人 IR 精度定案：**FP16**（ASR 的 FP16 和 FP32 聚类结果 0 段不一致）
<!-- 状态：已完成 -->

- 依据：ASR asr067_fp16_vs_fp32_cluster.json，n_diff_segments=0，并且嵌入 RTF 增量在固定 T 范围 [100, 2048] 后为 0.033（≤ 0.05）。客户包用 models/spk 下的 FP16 IR，不需要 FP32。
- ASR-033 正在收尾（交付代码清理内部编号后会重跑门禁）。ASR 通知后，你按新清单重新同步 asr_spk，**不要再做字面量替换**。
- v1.13 什么时候重打，按用户的指示来（用户 11:30 让你先不要重打）。真机验收（APP-043）可以先做。

## APP-048 [NORMAL] 2026-10-30 12:37 — 用户 GUI 改进：状态信息不要全部挤在顶部，**按 ASR / 翻译 / 语音输出 分到各自的区域**
<!-- 状态：进行中 -->

用户原话："现在所有的状态信息全部挤在最顶端，太多而且挤不下。后面建议把 ASR/翻译/TTS 的状态信息分别放在各个模型区域内，这样比较清晰。"
- 布局要求：
  - **ASR 区**（原文字幕区的标题栏或底栏）：设备、模型和精度、加载状态（加载中/就绪/失败及原因）、ASR RTF、说话人识别开关和状态（就绪/降级）、当前说话人。
  - **翻译区**（译文字幕区的标题栏或底栏）：设备、模型、目标语言、加载状态、最近一句的翻译延迟。
  - **语音输出区**（TTS 控件附近）：设备、音色模式（预设/跟随说话人）、输出设备、就绪状态、当前语速倍率、语音滞后秒数、排队句数。
  - **顶部只保留全局信息**：开始/停止、输入源、会话计时、一个总状态灯（全部就绪 / 有模块异常时点击查看）。
- 风格：每个区域用一行紧凑的状态条（图标 + 短字段），数值定时刷新（≤ 1 Hz），不要频繁重排布局；报错时那一行变色，鼠标悬停显示完整原因和日志路径。窗口缩小到 1280×720 时不能截断或溢出，字段过多时先隐藏次要字段。
- 不要改变控件的行为和默认值（APP-041 的启动初始化逻辑保持不变）。
- 验收：在 1920×1080 和 1280×720 下各截一张图（用户启动方式），三个区域的状态都可见，顶部不再拥挤；有一个模块故意加载失败时，对应区域会显示原因。截图放到 shared/app_gui_layout/，由 reviewer 转给用户。排在 APP-043 真机验收之后，和 v1.13 一起交付。

## APP-049 [HIGH] 2026-10-30 12:49 — 用户要求：压缩 STATUS 和 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB）
<!-- 状态：进行中 -->

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

## 最近 5 条（全文见上面的「全部条目全文」区）

- **APP-045**（状态：进行中）— ## APP-045 [BLOCKING] 2026-10-30 10:53 — 用户实测发现说话人切换和克隆"还没修好"：原因是**桌面快捷方式仍指向 v1.5 旧包**；另外旧克隆把音频写到了磁盘
- **APP-046**（状态：已完成）— ## APP-046 [HIGH] 2026-10-30 11:25 — 巡检规则补充：last_ack 追平后，只要还有未完成项，就自己继续做，不要空转
- **APP-047**（状态：已完成）— ## APP-047 [NORMAL] 2026-10-30 11:49 — 说话人 IR 精度定案：**FP16**（ASR 的 FP16 和 FP32 聚类结果 0 段不一致）
- **APP-048**（状态：进行中）— ## APP-048 [NORMAL] 2026-10-30 12:37 — 用户 GUI 改进：状态信息不要全部挤在顶部，**按 ASR / 翻译 / 语音输出 分到各自的区域**
- **APP-049**（状态：进行中）— ## APP-049 [HIGH] 2026-10-30 12:49 — 用户要求：压缩 STATUS 和 CORRECTIONS（旧内容归档，精简版 ≤ 40 KB）
