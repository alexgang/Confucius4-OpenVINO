# §227 巡检（**无新 reviewer 纠偏**，`last_ack` 仍 **APP-128**）｜🔴 **接续上一会话（TAKEOVER）并闭合其遗留的 3 处半交付**｜🟢 **已修：MEMORY.md 超限 710 字符被截断**｜🟢 **已补：上一会话从未写的 automation memory ＋ 当日日志**｜**本条需等 reviewer 复核**

> 🔴 本节正文全文（APP-052④：活文档只留标题行 ＋ 指针行，正文放 companion）。
> 上下文见 `status/app/STATUS_APP.md`。

## §0 六通道复核：**无新 reviewer 纠偏**（本轮开工 05:21，收尾 05:5x）

| 通道 | 实测 | 结论 |
|---|---|---|
| 局域网 `status/app/CORRECTIONS_APP.md` | **125 条／max APP-127**／SHA256 `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48`／**429 255 B**／mtime **2026-11-23 16:55:40** | 与 §225／§226 开工指纹**四项逐字一致** ⇒ **无 APP-128+**（reviewer 断网，纠偏只走邮件，属正常） |
| **QQ 邮箱**收件箱（reviewer `alexchen7694@agent.qq.com`） | 最新 App 封 ＝ **APP-128 补充**（`msg_fGIsiLHODyOPwNYqu7_98Pa_yjPt80xLFhbTGTT26hLfvA`，2026-11-23T12:52:07Z）＝**§225 已执行完毕**；其后仅 NAS `T-004`（`msg_9P13OL2HWZYf3TDKr-…`，12:52:08Z）与 ASR-068（`msg_tHwjDsvTKlufBDo6pyhm4IB3rG6j2nvzS3L_58wMzPidDQ`，08:55:15Z）⇒ **与 App 无关**；**全库检索 `APP-129` 命中 0** | **无 APP-129+** |
| 邮件 **spam**／**trash** | spam **0 封**；trash 仅 1 封无关旧邮件（2026-11-13 07:33Z 发给 `alexgang.chen@gmail.com` 的 rc9 性能报告） | 无 |
| 根 `status/CORRECTIONS.md` | 最大编号 **C-135**；`APP-` 仅 1 次命中（第 1883 行「`status/app/CORRECTIONS_APP.md`（APP-xxx）」＝**路径指路**，非纠偏条目） | 无跨模块误投 |
| `shared/NOTICE*` | 最新仍 **2026-11-05 09:35:48**（`NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`） | 无新交接单 |
| **agent-mail** | `not_bound`（该通道本机未开通） | 不适用 |

⇒ **`last_ack` 保持 `APP-128`**（无新编号 ⇒ 不改 `last_ack`）；本轮是**待命轮 ＋ 闭合上一会话遗留项**。

## §1 TAKEOVER 交接：上一会话（`4dc753a6`）已死

- `session_lease.py acquire app` ⇒ **TAKEOVER**：上一 token `4dc753a6`，started **11-24 00:20:07**，last_beat **00:45:18**（心跳 **276 min**前 ⇒ 判定死会话），note = **`step11: STATUS email sent msg_73akZokC... (2833B, 3 landmarks verified, no truncation); recording evidence`**，`live_pids=[]`。
- 本轮 token = **`019b41f0`**（beats ×7；收尾 `release`）。
- ⇒ **从断点继续**（不从头重做）：上一会话的**代码/STATUS/邮件都已落盘并推送**（`55edcf4`／`633e760`／`58439ba`，`git rev-list --left-right --count origin/main...main` ＝ **0 0**）；但它**死在 step11 之后**，留下 **3 处半交付**。

## §2 🔴 遗留项 ①：**MEMORY.md 超限 710 字符 ⇒ 会话启动注入被截断**（本轮已修）

### 实测（不是推断）

| 项 | 值 |
|---|---|
| 文件自声明上限 | **≤9 700 字符**（文件头第 3 行） |
| 压缩前实测 | **10 410 字符**／**18 909 B**／68 行 ⇒ **超限 710 字符** |
| 本次会话开头告警 | 「Your MEMORY.md has exceeded the size limit and was truncated during injection」 |
| 压缩后实测 | **9 699 字符**／**17 479 B**／68 行 |

### 修法（照搬项目既有约定，不新发明）

1. **压缩前全文逐字下沉**到 `MEMORY_MODULES.md` 的**新附录·四十九**（**append-only**；write-once ⇒ 标题已存在即拒绝，幂等）。
2. **逐条不删，只压从句** ⇒ 压缩后校验（全部在**内存新文本**上跑，不写盘就 FAIL ⇒ 源文件零改动）：① 行数不变 ② `## ` 章节数不变 ③ **每行判据标记（🔴/🟢/🟡）数量不减少** ④ 全部 `APP-/TTS-/ASR-/MT-/C-/§` 编号存活 ⑤ 字符数 ≤ 9 700 ⑥ 逐行 diff **禁止删整行**。
3. **临时文件 → `os.replace`**（不用 `open(p,'w')`，那会先截断）＋ **写后另起脚本独立复核**。

### 写后独立复核（`live_caption/_app227_verify_memory.py`，**ALL PASS**）

| 复核项 | 结果 |
|---|---|
| ① 字符数 ≤ 9 700／行数不变／章节数不变 | **PASS**（9 699／68／14） |
| ② MODULES 附录·四十九**逐字含压缩前全文**（10 410 字符） | **PASS** |
| ③ 附录·四十九**只出现一次**（write-once／幂等） | **PASS**（count=1） |
| ④ 每行判据标记数**不减少** | **PASS**（0 处减少） |
| ⑤ 章节**身份**（节号）不变、无节被删／合并 | **PASS**（14 vs 14）｜标题改写 **2 处**（§十二 去掉每轮都变的日期戳「（2026-11-24 00:4x；」；§十二之补 去掉一个「的」）—— **只压从句，不删节** |
| ⑥ 全部 `APP-/TTS-/ASR-/MT-/C-/§` 编号存活 | **PASS** |
| ⑦ 无 CR 引入／结尾有换行 | **PASS** |
| ⑧ 被压掉的反引号标识符**每个都在 MODULES 里有逐字原文** | **PASS**（只压掉 1 个：`invalid character`——纯错误提示串，不承载判据） |

### 🔴 手法留痕（本轮踩过的坑，供下轮直接用）

- 🔴 **「只压从句」不能用「子串级唯一命中」**：MEMORY.md 里同一句式多处重复 ⇒ 改成**行级补丁**（行号 ＋ **该行内唯一锚点**）⇒ 不会出现改错位置。
- 🔴 **反引号标识符「全部存活」是过严的判据**：MEMORY.md 的定位本就是「只留指针与最易踩坑的 token」；**判据改成「每行 🔴/🟢 标记数不减少 + 编号全存活 + 被压掉的标识符在 MODULES 里有逐字原文」**才既守得住又不做无用功。
- 🔴 **章节标题「逐字不变」也是过严**：每轮都变的日期戳留在标题里会撑爆预算 ⇒ 判据改为**节号身份不变 ＋ 改写如实登记**。
- 🔴 **候选稿要先测尺寸再定稿**：`live_caption/_app227_MEMORY_new.md`（候选）＋ `_app227_compress_memory.py`（不变量校验 ＋ 下沉 ＋ 写盘）＋ `_app227_verify_memory.py`（**写后独立复核**）＋ `_app227_repl.py`／`_app227_trim2..7.py`（定点裁剪清单，唯一命中断言）。

## §3 🔴 遗留项 ②：上一会话**从未写** automation memory ＋ 当日日志（本轮已补）

上一会话（`4dc753a6`）在 step11（记录实发邮件）之后死掉 ⇒ **两处记忆文件都没有 §226 的条目**：

| 文件 | 补写前实测 | 补写后 |
|---|---|---|
| `.workbuddy/memory/automations/c773e368-530e-4404-9b0d-66da2193cbf6/memory.md` | `grep -c '§226'` ＝ **0**（最后一条是 §225，2026-11-23 21:49–22:07） | **171 301 → 173 253 字符**，§226 命中 **4**（含正文与交叉引用） |
| `.workbuddy/memory/2026-11-24.md` | 只有 **2 条 TTS** 巡检条目（01:51 第 120 轮／04:22 第 121 轮），**无 App §226 条目** | **2 282 → 3 588 字符**，新增 `### 2026-11-24 00:4x · App 巡检轮 §226 …` |

🔴 两个文件都是 **append-only**：脚本**读原文 → 末尾追加 → 原子写回**，并断言「**原文逐字仍在新文件里**」＋「追加块只命中 1 次」；备份在 `%TEMP%/{memory,2026-11-24}.md.bak_app227_append`。
（依据：MEMORY.md §一「`.workbuddy/memory/automations/*/memory.md` 只许追加、禁覆盖」——曾误覆盖 79 轮历史。）

## §4 🔴 遗留项 ③：`.workbuddy/memory/MEMORY.md` 里的 **§226 状态块**与 §226 companion 重复（本轮已压）

- `MEMORY.md` §十二的 §226 行原本把 §226 的**方法细节**（3 份 e2e7 底本 blob＝原件＝公布 SHA256、3/3 复现、反证组 3/3）与 §八 的「§226 修法」**各写一遍**。
- 本轮压缩时：§八 保留**方法**（入库 reviewer 原件 ⇒ 同目录 `.gitattributes`(`*.json -text`)＋`git add --renormalize`；判据＝真跑 `git -c core.autocrlf=false clone`（须作用于 clone 本身）＋反证组；根治＝仓库根 `.gitattributes`＝跨模块 ⇒ 须 reviewer 裁定），§十二 保留**结果与待裁定**（3/3 复现＋反证组 3/3；提交 `73a2e22`…`58439ba`；邮件 `msg_73akZokC…DRHg`（**2 833 B**）；全仓 **854** 个 `i/lf+w/crlf` ⇒ 根治须 reviewer 裁定；未进 v2.6／未打包（APP-126 §7））。
- **全部原文仍在 `MEMORY_MODULES.md` 附录·四十九**（逐字快照，见 §2 复核项②）。

## §4b 📧 STATUS 邮件已发（T-MAIL-003 必须发；§224 截断教训已按三地标复核）

| 项 | 值 |
|---|---|
| message_id | **`msg_XgwviMa-4Kx_aLY4SD3kISdocZyQINV5mr1ZW3BGbOTWYg`** |
| 发出时间 | **2026-11-23T21:53:09Z**（＝**2026-11-24 05:53:09 GMT+8**） |
| 方式 | **回复** APP-128 补充原邮件（`msg_fGIsiLHODyOPwNYqu7_98Pa_yjPt80xLFhbTGTT26hLfvA`）——T-MAIL-003 §5 允许用「回复」；正文首段写明应有主题与编号 |
| 主题 | `Re: [C4][A][CORRECTION][APP] APP-128 补充：STATUS 正文被截断，请单独补发 e2e7 三臂表` |
| 两步 token 流程 | ① 无 token 首发 ⇒ **42801** ＋ `ctk_6e5b4c39-fcb0-443a-8d1c-60eac1e65974`；② **原样**带 token 重发 ⇒ **`queued:true`** ⇒ **一次成功**（token 绑定请求内容 ⇒ 第二次须逐字节相同） |
| 正文 | **3 109 字符／5 206 B**／SHA256 `8887d78a6c56641612db4e2ce6f0f9b835e2c163091d599ac5d9b03c0e4c621e`／**9 段（■ 0–■ 9）** |
| 入库 | `live_caption/_app227_email_body.txt`（**由脚本生成** `_app227_email_body.py` ⇒ 与实发**逐字节相同**） |
| 附件 | **0 个**（base64 人工转写必错 ⇒ 本轮无附件，不走附件通道） |

🟢 **未截断复核（针对 §224 的投诉点）**：在**已发箱**用**内容检索**逐个命中三个地标 —— ① 首段「§227 巡检（无新 reviewer 纠偏）」② **中段**「写后独立复核 ALL PASS：9 699 字符」③ **末段**「目标机三件套仍被 A 机已离开 192.168.2.0/24 挡住」⇒ **首/中/尾全在 ⇒ 中间没丢**；正文长度 **5 206 B ≪ 11 KB**（§224 那次是 11 KB 正文中间丢失）。

## §5 本轮**未**做的事（纪律登记）

🟢 **未打包**（用户长期规则「不通知 ⇒ 不打包」＋ APP-055／APP-126 §7）｜🟢 **未改任何客户包既有文件**（`Confucius4_LiveCaption_v*` 一个字节未动）｜🟢 **未跑推理/计时**（⇒ **未取 `MACHINE_LOCK`**；本机 `shared/MACHINE_LOCK` 实测不存在）｜🟢 **未调 MiniMax**（质量判定留给 reviewer 回转写）｜🟢 **未连 B 机**（APP-109 ④ 仍有效）｜🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ **SHA 零改动**）｜🟢 **未进 v2.6**｜🟢 **未提交 `CORRECTIONS_*.md`**｜🟢 **未吞其它模块的未提交改动**（本轮只 add App 侧文件）｜🟢 **未 force push**（普通 push，main 分支）。

## §6 收尾复核：`CORRECTIONS_APP.md` **SHA 零改动**

| 项 | 开工（05:21） | 收尾（05:5x） | 结论 |
|---|---|---|---|
| SHA256 | `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48` | **同左** | **零改动** |
| 字节数 | **429 255** | **429 255** | 同 |
| mtime | **2026-11-23 16:55:40.898165100 +0800** | **同左** | 同（未被写） |
| `## APP-` 条数 | **125** | **125** | 同（无新条目） |

🔴 该文件是 **reviewer 独占写入文件**（只读、绝不修改、绝不 `git add`）——其 ` M` 是 reviewer 真追加。

## §7 待 reviewer 复核 / 裁定

1. 🔴 **本条 §227 需 reviewer 复核**：`MEMORY.md` 压缩后是否仍满足「只留换个会话不知道就会做错的判据」——**可核对**：① `live_caption/_app227_verify_memory.py` 输出 **ALL PASS**；② 压缩前全文在 `MEMORY_MODULES.md` 附录·四十九（**10 410 字符逐字快照**）；③ 被压掉的反引号标识符只 **1 个**（`invalid character`）。
2. 🔴 **§226 的复核仍挂着**（上轮发出，本轮无新信息）：三份底本在 `core.autocrlf=false` 的机器上 clone 后能否按公布 SHA256 逐字节复现（3/3）。
3. 🔴 **仓库根 `.gitattributes` 根治**：是否授权在全仓范围加 `.gitattributes` 并 `--renormalize`（影响 **851 个历史文件**的 blob ⇒ **跨模块**，且会改写 reviewer 已在复核的历史条目的入库字节）？**本轮未自行执行**。
4. 🟡 **默认分离设备**（沿用 §223 §10-2）：实测 GPU.0 0.215 / CPU 0.458（p50 RTF）⇒ 建议 **GPU.0**，等 reviewer 定。
5. 🟡 **`n_speakers=0` 的口径**（沿用 §223 §10-1）：App 侧 `SpeakerBridge` 的 stats 是否收进 `stats_full`（属 reviewer 分工，App 线程未动）。
6. 🔴 **v2.6 交接**：APP-128 补充要求的「e2e7 三臂表」**已单独补发**（`msg_52Ta35TCkxRJS1CDLmdVZbCF5yDGbx4gPdFrKHNlMH7bJw`，正文 **462 B**，未截断）⇒ 前置材料已到位；但 **APP-126 §7「不要开始 v2.6 打包」** 与 reviewer 的「v2.6 打包仍等 reviewer 交接」仍在 ⇒ **本轮未进 v2.6、未打包、未跑 10 分钟整链、未抽听**，**等 reviewer 明确交接指令**。
7. 🟡 沿用未结项：**v2.5 重签 ACCEPTED**（ACCEPTED 仍指 v2.4）｜**发客户必须确认发 `v1.1.1.zip`**｜**目标机三件套**（删 zip 授权／实机 `--check`／两端 SHA256 对账）**仍被 A 机已离开 `192.168.2.0/24` 挡住**（现 `10.188.194.152/21`）｜**ASR ahead 2 只报告不代劳**。

## §8 下一轮起点

- 🔴 `last_ack` 仍 **APP-128**（无新编号 ⇒ 不改）。
- 🟢 租约：`acquire app` ⇒ exit 0 / token `019b41f0`（**TAKEOVER**，上一会话已死）⇒ beats ×7 ⇒ 收尾 `release`。
- 🟢 本轮**新学到的可复用知识**：① **「逐条不删，只压从句」的可操作判据＝「每行 🔴/🟢 标记数不减少 ＋ 编号全存活 ＋ 被压掉的标识符在 MODULES 里有逐字原文」**（原来用「反引号全存活」过严 ⇒ 压不动）；② **章节标题逐字比对也过严**（日期戳每轮都变）⇒ 改判「**节号身份不变 ＋ 改写如实登记**」；③ **子串级唯一命中在长文件上不可靠** ⇒ 改**行级补丁（行号 ＋ 该行内唯一锚点）**；④ **「上一会话死在 step11 之后」会同时漏掉两个记忆文件**（automation memory ＋ 当日日志）⇒ 收尾要把这两处一起写。
