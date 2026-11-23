# STATUS_APP §225 详情 — APP-128 补充（e2e7 三臂表补发）

- 轮次：**2026-11-23 21:49–21:5x**（巡检 + 执行 APP-128 补充）
- `last_ack`：**APP-128 → APP-128（不变）**｜本条**不是新编号 APP-129**，是 reviewer 对 APP-128 的**补充要求**
- 租约：`session_lease.py acquire app` ⇒ exit 0 / `TOKEN=159a829b`（**无 TAKEOVER / 无 BUSY**）｜beats 全程正常｜收尾 `release`
- 本节结论：**本条已完成**；**本条需等 reviewer 复核**

## §0 纠偏来源（唯一通道 = QQ 邮箱）

reviewer 现在连不上 A 机（局域网断），纠偏只走邮件：

| 项 | 值 |
|---|---|
| message_id | `msg_fGIsiLHODyOPwNYqu7_98Pa_yjPt80xLFhbTGTT26hLfvA` |
| created_at | 2026-11-23T12:52:07Z（＝北京 **20:52:07**） |
| from | `alexchen7694@agent.qq.com` |
| subject | `[C4][A][CORRECTION][APP] APP-128 补充：STATUS 正文被截断，请单独补发 e2e7 三臂表` |

**reviewer 复核结论（原文）**：「md5、测试 14/14 + 18/18 + 回归、e2e9（三臂 seg IR=fp16-w5、分段失败 0、spk_bypass.enabled=true）、提交 3573b2d、两个 ogg 附件都已收到，**通过**。clone_s2 n_speakers=0 判为正常（前 15 s 是配乐，台词每句约 1 s，到不了单人 3 s 干净语音的登记门槛），不用处理。」

**本条唯一要求**：「邮件正文从「speaker.n_speakers 2 / 0 / 1」之后直接跳到结尾，中间的内容（e2e7 三臂表等）没有到。请**单独发一封短邮件**，正文只放下面这张表（纯文本，不要长段落），主题 `[C4][A][STATUS][APP] APP-128 e2e7 三臂表` … 数据来自 `shared\bgkeep\e2e7\{off,on_gpu,on_cpu}\bgkeep_e2e.json`（dub_late_vs_play_s.max/p90/n_late、bg_late_blocks、stats_bg.sep_rtf_p50/p90）。**不要做别的；v2.6 交接等这张表到了再发。**」

🔴 **执行边界**：本轮**只**做「补发这一张表」这一件事 ⇒ **不打包、不进 v2.6、不跑整链、不抽听**（reviewer 明写「不要做别的」「v2.6 交接等这张表到了再发」）。

## §1 六通道复核（开工时）

| 通道 | 结果 |
|---|---|
| 局域网 `status/app/CORRECTIONS_APP.md` | **125 条／max APP-127**（SHA256 `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48`／**429 255 B**／mtime **2026-11-23 16:55:40**）⇒ **无 APP-128+**（与上轮一致，reviewer 断网） |
| QQ 收件箱 | 最新 App 封＝**APP-128 补充**（12:52:07Z）；其后仅 1 封 **NAS T-004**（12:52:08Z，**非 App 模块**） |
| QQ spam | **0 封** |
| QQ trash | **1 封**＝11-13 MiniMVP rc9 旧报告（`msg_Ui-Sz0CwNYT2DX-PcwWwuiYbYR6skSey_XvrjVA6uZLw_Q`）⇒ **非 reviewer 纠偏** |
| agent-mail | **仍 `not_bound`**（工具明确「当前请勿重试」⇒ 试 1 次即停） |
| `shared/NOTICE*` | 最新仍 **11-05 09:35**（`NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`） |
| 根 `status/CORRECTIONS.md` | max **C-135**（10-24）；`status/asr/CORRECTIONS_ASR.md`（mtime 11-23 16:55:15）内 APP token max **125** ⇒ **无 APP-128+** |
| `results/app/` | 最新＝`_app128_email_body.txt`（11-23 20:35，§224 自身产物） |

## §2 e2e7 三臂表（数据源 = **reviewer 自己的 e2e7 产物**，本轮只读，未改源文件）

源文件（**只读**）：`C:\Users\Trekker-PTL\shared\bgkeep\e2e7\{off,on_gpu,on_cpu}\bgkeep_e2e.json`

| 臂 | dubs | dub_late max | dub_late p90 | n_late | bg_late_blocks | sep_rtf p50/p90 | 源文件 SHA256（前 16） | 字节 | mtime |
|---|---|---|---|---|---|---|---|---|---|
| off | 123 | 2.43 | -1.54 | 7 | 0 | —（bg off，未分离） | `04ccb407e7206acf` | 30 897 | 2026-11-23 16:54:51 |
| on_gpu | 123 | 3.41 | -1.43 | 8 | 0 | 0.215 / 0.25 | `1fb2ef9578dc26cb` | 31 432 | 2026-11-23 17:06:52 |
| on_cpu | 123 | 3.41 | -1.69 | 8 | 0 | 0.458 / 0.589 | `47bb7ca952fcf421` | 31 403 | 2026-11-23 17:18:54 |

字段来源（reviewer 指定）：`dub_late_vs_play_s.max` / `.p90` / `.n_late`、`bg_late_blocks`、`stats_bg.sep_rtf_p50` / `stats_bg.sep_rtf_p90`。

**交叉信息（不表内，供 reviewer 判口径）**：`off` 臂 `stats_bg.bg_state=off`／`bg_keep=false`／`sep_device=null`；`on_gpu` 臂 `sep_device=GPU.0`；`on_cpu` 臂 `sep_device=CPU`；三臂 `stats_full.speaker.n_speakers` 均为 0（与 reviewer「e2e7 同为 0 ⇒ 非 v0.4.19 回归」的判断一致）。

## §3 数字**双路复核**（两路独立，都过）

1. **路 A（解析）**：`live_caption/_app128b_e2e7_table.py` 用 `json.loads` 取字段，并把每个值**回到原始 JSON 文本里逐字命中**（`raw_text_crosscheck`，非空值 100 % 命中）。
2. **路 B（不经 json 解析）**：独立脚本用 `re` 在原始文本上切 `dub_late_vs_play_s` / `bg_late_blocks` / `dubs` / `sep_rtf_p50|p90` 片段再取值。

两路结果**逐字段一致**：

| 臂 | dubs | max | p90 | n_late | bg_late_blocks | sep_p50 | sep_p90 |
|---|---|---|---|---|---|---|---|
| off | 123 | 2.43 | -1.54 | 7 | 0 | null | null |
| on_gpu | 123 | 3.41 | -1.43 | 8 | 0 | 0.215 | 0.25 |
| on_cpu | 123 | 3.41 | -1.69 | 8 | 0 | 0.458 | 0.589 |

## §4 已发出的补发邮件（实发记录）

| 项 | 值 |
|---|---|
| message_id | **`msg_52Ta35TCkxRJS1CDLmdVZbCF5yDGbx4gPdFrKHNlMH7bJw`** |
| rfc_message_id | `<tencent_4EFD32D337094CC5F248A95CA3F33401F209@qq.com>` |
| created_at | 2026-11-23T13:53:36Z（＝北京 **21:53:36**） |
| from → to | `1985197690@qq.com` → `alexchen7694@agent.qq.com` |
| subject | `[C4][A][STATUS][APP] APP-128 e2e7 三臂表`（与 reviewer 指定**逐字一致**） |
| 附件 | **0 个**（reviewer 只要一张表 ⇒ 不带附件；也规避 base64 人工转写风险） |
| 正文 | **462 B**，SHA256 `3fc385027894c62dfb95d67f8c0fef9f389b9ba419c5b7cf02b78bc0bd4f5fbb` |
| body_format | MARKDOWN（表头＋3 行＋来源 2 行） |

**发送方式**＝qq-mail 两步 token 流程：先不带 token 调用 ⇒ 服务端返回 `42801` + `ctk_9074034c-d88a-4df7-b9fc-a61e916e7cdc`（`expires_at` 13:58:31Z）⇒ **正文逐字节原样**重发并带 token ⇒ `queued:true` 一次成功。
（🔴 沿用上轮教训：**token 绑定正文 ⇒ 两步之间正文一个字符都不能改**；本次正文由脚本生成，两步用的是同一份字面量。）

**正文完整性自检**（针对 reviewer 上轮的投诉点）：取已发箱邮件原文（`GetMessage`）逐行核对＝**表头行 ＋ 分隔行 ＋ off/on_gpu/on_cpu 三行 ＋ 空行 ＋ 来源 2 行 = 8 行齐全**，与入库正文文件**逐字节相同**（462 B / 同 SHA256）⇒ **本封未被截断**。

## §5 入库完整性（§222 四条判据，本轮全满足）

| 产物 | 路径 | 说明 |
|---|---|---|
| 产生脚本 | `live_caption/_app128b_e2e7_table.py` | 证据 json 的产生脚本（必须入库，否则干净 clone 无法复算） |
| 证据 json | `results/app/app128b_e2e7_table_evidence.json` | 含三臂原始字段、源文件 sha256/字节/mtime、raw 文本逐字交叉校验、邮件正文与其 SHA256 |
| **实发邮件正文** | `live_caption/_app128b_email_body.txt` | **与实发正文逐字节相同**（462 B，SHA256 同上）⇒ 入库 == 实发 |
| **reviewer 复算底本** | `results/app/app128b_e2e7_src/{off,on_gpu,on_cpu}_bgkeep_e2e.json` | reviewer 自己那三份原始 json **原样复制入库**（3 份，30 897／31 432／31 403 B）⇒ reviewer 可离线复算 |

（脚本与证据 json 均**幂等**：重跑产物字节一致；脚本只读 `shared/bgkeep/e2e7`，不写不改源文件。）

## §6 本轮纪律

- **未打包**（用户长期规则「不通知 ⇒ 不打包」＋ reviewer 明写「不要做别的」）｜**未改任何客户包既有文件**｜**未跑推理·计时**（⇒ **未取 `shared/MACHINE_LOCK`**，本机当前无锁）｜**未调 MiniMax**（质量判定仍归 reviewer）｜**未连 B 机**（APP-109 ④ 仍有效）｜**未改纠偏文件**（§7 四项指纹收尾复核一致）
- **未进 v2.6**（reviewer：「v2.6 交接等这张表到了再发」⇒ 等本封到达后再动）
- 只提交 App 模块负责的文件（逐文件 `git add`，**禁 `-A`**）；**`status/app/CORRECTIONS_APP.md` 绝不 add**（reviewer 独占）；ASR/MT/TTS 其它模块的脏改动不吞（全仓脏 865）

## §7 收尾复核（纠偏文件只读 ⇒ 四项指纹）

| 项 | 开工 | 收尾 | 结论 |
|---|---|---|---|
| SHA256 | `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48` | 同左 | **SHA 零改动** |
| 字节数 | 429 255 | 429 255 | 一致 |
| mtime | 2026-11-23 16:55:40 | 2026-11-23 16:55:40 | 一致 |
| `## APP-xxx` 条数 | 125（max APP-127） | 125（max APP-127） | 一致 |

## §8 下一轮必须读

- **等 reviewer 复核 §225**（e2e7 三臂表是否收到、格式是否符合预期）
- reviewer 说的 **v2.6 交接**：等这张表到达后再启动（APP-122「保留背景音」＋ APP-123「c13 接入」进 v2.6 全集）
- 沿用未结项：**v2.5 的 `ACCEPTED.json` 仍指向 v2.4** ⇒ 出包闸门 fail-closed ⇒ **v2.5 打不出 zip**（须 reviewer／用户点头后重签）
- **发客户必须确认发 `v1.1.1.zip`** 而不是 `v1.1.zip`（旧的 ACCEPTED 含 `tts_cuda*` 33 条，而 zip 内 `app/*.py` 31 个 ⇒ 不自证）
- 目标机三件套（删 zip 授权／实机 `--check`／两端 SHA256 对账）**仍被 A 机已离开 `192.168.2.0/24` 挡住**（现出口 IP `10.188.194.152/21`）
- ASR 那 2 笔 ahead 2 属 **ASR 模块** ⇒ **只报告不代劳**
