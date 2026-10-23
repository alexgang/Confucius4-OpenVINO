## APP-001 [HIGH] 2026-10-23 09:12 — 模式切换启动单：App 模块（live caption 集成、打包、git）改用独立的 STATUS_APP.md 和 CORRECTIONS_APP.md
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
用户已确认：翻译默认量化从 INT4 改成 **INT8 按通道（int8sym-cw-q）**（MT 模块 H-001：INT8 和 BF16 等价，INT4 低 1.5–1.8 chrF++；INT8 GPU 37.5 tok/s，满足实时）。
- 要做的事：
  ① 把 `live_caption/translator.py` 里 MT_ENGINES 的默认值改为 INT8-CW（GPU.0），INT4 保留为可选项，GUI 的下拉框默认选中 INT8。
  ② 下一版客户包带上 INT8-CW 的 IR（路径、文件清单和 SHA256 以 MT 模块 STATUS 里给的为准）。如果包体积受限，可以去掉 INT4，在 STATUS 里说明包的大小变化。
  ③ 改完后跑一次 CLI 回放，确认翻译正常，并记录翻译延迟和对 ASR RTF 的影响（计时要持机器锁）。
  ④ git 提交。提交说明写上"默认 MT 改 INT8-CW（用户决定）"。

## APP-003 [BLOCKING] 2026-10-23 09:45 — 客户包 results/ 里有内部会议转写内容，不能进包；APP-002（默认 INT8-CW）还没执行；CORRECTIONS 里编号撞车；STATUS 时间写到了未来

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
