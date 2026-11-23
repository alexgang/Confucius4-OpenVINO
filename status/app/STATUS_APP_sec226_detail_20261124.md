# §226 巡检（**无新 reviewer 纠偏**，`last_ack` 仍 **APP-128**）｜🔴 **接续上一会话（TAKEOVER）并闭合其遗留的「入库字节不一致」缺陷**｜🟢 **已修：reviewer 复算底本现在逐字节入库，clone 可复现公布的 SHA256**｜🟢 **反证组证明修法承重**｜**本条需等 reviewer 复核**

> 本节正文全文。上下文见 `status/app/STATUS_APP.md`（活文档只留标题行 ＋ 指针行，APP-052④）。

## §0 六通道复核：**无新 reviewer 纠偏**

| 通道 | 实测 | 结论 |
|---|---|---|
| 局域网 `status/app/CORRECTIONS_APP.md` | **125 条／max APP-127**／SHA256 `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48`／**429 255 B**／mtime **2026-11-23 16:55:40** | 与 §225 开工指纹**四项逐字一致** ⇒ **无 APP-128+**（reviewer 断网，纠偏只走邮件，属正常） |
| **QQ 邮箱**（reviewer `alexchen7694@agent.qq.com`） | 收件箱最新 App 封 = **APP-128 补充**（`msg_fGIsiLHODyOPwNYqu7_98Pa_yjPt80xLFhbTGTT26hLfvA`，2026-11-23T12:52:07Z）＝**上一轮 §225 已执行完毕**；其后仅 NAS 模块 T-004（`msg_9P13OL2H…`）与 ASR-068（`msg_tHwjDsvT…`）⇒ **与 App 无关** | **无 APP-129+** |
| 邮件 spam / trash | spam **0 封**；trash 仅 1 封无关旧邮件 | 无 |
| 根 `status/CORRECTIONS.md` | 无 `APP-` token | 无跨模块误投 |
| `shared/NOTICE*` | 最新仍 **2026-11-05 09:35**（`NOTICE_asr_to_app_asr045_…`） | 无新交接单 |
| 本轮开工时 `git log` | HEAD = `a236fa2`（ASR §97 邮件正文入库） | App 上一次提交 = `b7507cb`（§225） |

⇒ **`last_ack` 保持 `APP-128`**（无新编号 ⇒ 不改 `last_ack`）；本轮是**待命轮 ＋ 闭合上一会话遗留项**。

## §1 上一会话（TAKEOVER）留下的未结项

- `session_lease.py acquire app` ⇒ **TAKEOVER**：上一 token `40e251eb`，started **11-23 23:08:56**，last_beat **23:17:16**（心跳 **63 分钟**前 ⇒ 判定为死会话），note = **`step4: found autocrlf byte-divergence in committed reviewer source jsons; scanning scope`**，`live_pids=[]`。
- ⇒ 本轮**从断点继续**（不从头重做）：把它发现的 autocrlf 字节不一致**做完并修掉**。

## §2 🔴 缺陷根因（实测，非推断）

- 本仓 `git config core.autocrlf` = **`true`**，且**仓库根与 `results/app/app128b_e2e7_src/` 此前都没有 `.gitattributes`** ⇒ `git add` 会把 **CRLF 规整成 LF** 再入库。
- §225（提交 `b7507cb`）入库了 **3 份 reviewer 自己的原始 json**（`results/app/app128b_e2e7_src/{off,on_gpu,on_cpu}_bgkeep_e2e.json`）。**reviewer 原始文件是 CRLF**（实测 `CRLF=1424 / 裸 LF=0`）。
- ⇒ **工作区字节 = reviewer 原件**（正确），但 **index/blob 里是规整后的 LF**（**入库件 ≠ 原件**）。

| 臂 | reviewer 原件 | 工作区 | **修前 index blob** | 修前 blob 字节 |
|---|---|---|---|---|
| off | `04ccb407…`／30 897 B | `04ccb407…` | **`22361b4e…`** | 29 473（LF） |
| on_gpu | `1fb2ef95…`／31 432 B | `1fb2ef95…` | **`5754da4a…`** | 29 953（LF） |
| on_cpu | `47bb7ca9…`／31 403 B | `47bb7ca9…` | **`fa8f7bab…`** | 29 924（LF） |

## §3 🔴 影响（这就是「假 FAIL」的来源）

`results/app/app128b_e2e7_table_evidence.json` 公布的是 **CRLF 原件**的 `source_sha256`（`04ccb407…` / `1fb2ef95…` / `47bb7ca9…`）。

**实测（修前）**：`git -c core.autocrlf=false clone`（模拟 Linux reviewer 拉仓库）⇒ clone 出来的三份文件分别是 **29 473 / 29 953 / 29 924 B 的 LF 版本**，SHA256 = `22361b4e…` / `5754da4a…` / `fa8f7bab…` ⇒ **与公布的 SHA256 全部对不上** ⇒ reviewer 拿证据 json 里的 SHA 去核对入库件会**必然对不上**（§222「reviewer 的复算底本必须入库」这条**在 clone 口径下不成立**）。

🔴 **补充说明（避免夸大）**：在 `core.autocrlf=true` 的机器（含本机）上 clone 出来是 CRLF ⇒ SHA **恰好对得上**；所以此缺陷**只对 `autocrlf=false` 的机器（Linux/macOS 默认、部分 CI）暴露**。但 §222 的用途正是「reviewer 能在自己机器上复算」，**reviewer 机器的 git 配置不可控** ⇒ 必须修。

## §4 🟢 修法（定点、只碰 App 模块自己的目录）

1. 新增 `results/app/app128b_e2e7_src/.gitattributes` ⇒ 内容 `*.json -text`（**不做任何行尾转换**，git 按工作区字节原样入库）+ 3 行中文说明（背景＝autocrlf 规整 ⇒ clone 口径对不上 SHA）。
   - 用**目录局部 `.gitattributes`** 而非仓库根：作用域限于本目录，**不影响其它 851 个文件，也不影响其它模块**。
2. `git add --renormalize results/app/app128b_e2e7_src/` ⇒ 让 index blob 变成工作区字节原样。
   - 🔴 **踩坑记录**：只 `git add` 不够 —— git 的 stat cache 会认为文件未变而**跳过重新规整**（实测 blob 仍是 `22361b4e…`）；必须 `--renormalize` 才真正重算 blob。

## §5 🟢 验收（**四路复核 ＋ 反证组**，脚本 `live_caption/_app226_eol_verify.py`）

| 复核 | 口径 | 结果 |
|---|---|---|
| ① 工作区 vs reviewer 原件 | 逐字节 | **3/3 相等** |
| ② **index blob** vs reviewer 原件 | 逐字节 | **3/3 相等** |
| ③ index blob 的 sha256 vs 证据 json 公布的 `source_sha256` | 逐字段 | **3/3 相等**（`04ccb407…` / `1fb2ef95…` / `47bb7ca9…`） |
| ④ **行为级真跑**：真 `git -c core.autocrlf=false clone --no-hardlinks` 后取文件算 sha256 | 与公布值比 | **3/3 相等**，字节 30 897 / 31 432 / 31 403 |
| 🟢 **反证组**：在**修前**提交 `a236fa2` 上跑**同一 clone 口径** | 应**全部对不上** | **3/3 对不上**（29 473 / 29 953 / 29 924 B）⇒ **修法承重（load-bearing）**，不是「口径恰好通过」 |

⇒ `RESULT: PASS`（`all_pass=true`）。证据落盘：`results/app/app226_eol_verify_evidence.json`（**4 653 B**／SHA256 `72c6151e11346cfb8bff9461fbc9a5e46102bdff7961861d5f6f70416885fb77`）。

🔴 **本轮自己修掉的一处「假 PASS」**：验证脚本**第一版**写成「先 clone、再 `git config core.autocrlf false`」⇒ **checkout 早在 clone 时就按当时配置做完** ⇒ 测的是「autocrlf=true 的 clone」⇒ **必然通过 = 假 PASS**。已改为 `git -c core.autocrlf=false clone`（配置作用于 clone 本身）**并加反证组**；修好前脚本第一版在**修后 HEAD** 上跑出过 `all_pass=false`（因 clone 读 HEAD 而修法当时仅在 index 里）⇒ 提交后才转 PASS。

## §6 🔴 顺带查清但**本轮不修**的更大面（避免夸大范围、避免越界）

- 全仓 `git ls-files --eol` ⇒ **854 个**跟踪文件是 `i/lf + w/crlf`（同一 autocrlf 现象的普遍面）；其中 **48 个**的工作区 SHA256 在仓库内被引用过。
- 🔴 **当前 App 活文档里「公布 SHA ⇒ 指向入库件」的共 5 份**（全仓扫 `status/app/*.md` ＋ `live_caption/*.py|txt|md` 的 64-hex 命中）：
  | # | 文件 | 公布处 | 修前 blob | 本轮处置 |
  |---|---|---|---|---|
  | 1 | `results/app/app128b_e2e7_src/off_bgkeep_e2e.json` | `app128b_e2e7_table_evidence.json` | `22361b4e…`（LF） | ✅ **已修** |
  | 2 | `results/app/app128b_e2e7_src/on_gpu_bgkeep_e2e.json` | 同上 | `5754da4a…`（LF） | ✅ **已修** |
  | 3 | `results/app/app128b_e2e7_src/on_cpu_bgkeep_e2e.json` | 同上 | `fa8f7bab…`（LF） | ✅ **已修** |
  | 4 | `results/app/app591_acceptance_spsp5_zh_run20261117-140853.json` | `status/app/STATUS_APP_sec214_detail_20261117.md` L212 | `16c0f6f6…`（LF） | 🔴 **本轮不修**（见下） |
  | 5 | `results/app/_app591_spsp5_zh_run20261117-140853_tts_out.wav.tts.jsonl` | 同上 L213 | `73bd4871…`（LF） | 🔴 **本轮不修**（见下） |
- ✅ **本轮只修 1–3**：它们是 **reviewer 自己的源文件**（＝上一会话 note 里的「committed reviewer source jsons」＝ **§222「reviewer 的复算底本必须入库」**的直接对象）⇒ **本轮遗留项的正解**。
- 🔴 **4–5 本轮一律不动**：① 属 **APP-115（§214）已闭合轮次**的历史产物，reviewer 早已复核过；改其 blob 等于改写**已复核历史条目的入库字节**；② 不是 reviewer 源文件；③ 修法虽同（精确路径 `-text` ＋ `--renormalize`），但**须 reviewer 明确裁定后再做**，本轮**只如实报告，不自行执行**。
- 🔴 **其余 849 个文件同理不动**：大量属**其它模块**（ASR/MT/TTS）的产物，App 线程**不得越界改写**；真正要根治需**仓库根 `.gitattributes`（或统一 `text=auto`）** ＋ 一次性 `--renormalize` 全仓 ⇒ 那是**跨模块、影响面 851 文件**的变更，**须 reviewer 裁定后再做**，本轮只把事实与建议写进 STATUS 与邮件，**不自行执行**。

## §7 提交 ＋ 邮件

- **`73a2e22`**（main）：5 个文件 ＝ `results/app/app128b_e2e7_src/.gitattributes`（新）＋ 3 份 reviewer 底本（blob 重规整为 CRLF）＋ `live_caption/_app226_eol_verify.py`（复核脚本）。
- **`55edcf4`**（main）：STATUS §226 ＋ companion ＋ 归档 ＋ 证据 json ＋ 写入/复核脚本。
- **`633e760`**（main）：实发邮件正文留档 ＋ 生成脚本。
- 逐文件 `git add`（**禁 `-A`**）；**未 add** `status/app/CORRECTIONS_APP.md`；**未吞** ASR/MT/TTS 其它模块的未提交改动。**均已 push `origin/main`**（`a236fa2..633e760`）。

### §7.1 邮件（T-MAIL-003「STATUS 邮件必须发」）

| 项 | 值 |
|---|---|
| message_id | **`msg_73akZokCXDeuiOrSl4wc7HlAlytJtuAhD1WY3oO6jnDRHg`** |
| 发出时间 | **2026-11-24 00:42:21**（＝2026-11-23T16:42:21Z） |
| 方式 | **回复 APP-128 补充原邮件**（`msg_fGIsiLHODyOPwNYqu7_98Pa_yjPt80xLFhbTGTT26hLfvA`）—— T-MAIL-003 §5 允许用「回复」；正文首行写明应有主题 |
| 两步 token 流程 | ① 无 token 首发 ⇒ 42801 + `ctk_ef78fdd4-caa2-4a7c-a9b4-2b904cd18206`；② **原样**带 token 重发 ⇒ `queued:true` ⇒ **一次成功** |
| 正文 | **2 833 B**／SHA256 `975e76a5a637807fb09768635bd094a468e4de6957f3684846f731632f1cd96a`／26 行 |
| 入库 | `live_caption/_app226_email_body.txt`（**由脚本生成** ⇒ 与实发逐字节相同）＋ 生成脚本 `live_caption/_app226_email_body.py` |
| 附件 | **0 个**（base64 人工转写必错 ⇒ 不走附件） |

**🟢 未截断复核（针对 §224 的投诉点）**：在**已发箱**用内容检索逐个命中三个地标 —— ① 首行「……§226：reviewer 复算底本入库字节不一致已修（待复核）」② **中段**「更大面如实报告 全仓 854 个跟踪文件」③ **末行**「—— App 线程」⇒ **首/中/尾全在 ⇒ 中间没丢**（§224 那次是 11 KB 正文中间丢失）。

## §8 纪律登记

🟢 未打包（用户长期规则「不通知 ⇒ 不打包」＋ APP-055/APP-126 §7）｜🟢 未改任何客户包既有文件｜🟢 未跑推理·计时（**未取 MACHINE_LOCK**）｜🟢 未调 MiniMax｜🟢 未连 B 机（APP-109 ④ 仍有效）｜🟢 **未改纠偏文件**（收尾四项指纹逐字一致 ⇒ SHA 零改动）｜🟢 未改仓库根 `.gitattributes`（只加了目录局部的）｜🔴 未做全仓 854 文件的根治（**留待 reviewer 裁定**，见 §6）。

## §9 待 reviewer 裁定 / 复核

1. 🔴 **本条 §226 需 reviewer 复核**：三份底本是否已可按公布 SHA 逐字节复现（reviewer 侧建议在 `core.autocrlf=false` 的机器上 clone 后核对 3 个 SHA256）。
2. 🔴 **仓库根 `.gitattributes` 根治**：是否授权在全仓范围加 `.gitattributes` 并 `--renormalize`（影响 **851 个历史文件**的 blob ⇒ **跨模块**，且会改写 reviewer 已在复核的历史条目的入库字节）？**本轮未自行执行**。
3. 🟡 **默认分离设备**（§223 §10-2 未变）：实测 GPU.0 0.215 / CPU 0.458（p50 RTF）⇒ 建议 **GPU.0**，等 reviewer 定。
4. 🟡 **`n_speakers=0` 的口径**（§223 §10-1 未变）：App 侧 `SpeakerBridge` 的 stats 是否收进 `stats_full`（属 reviewer 分工，App 线程未动）。
5. 🔴 **v2.6 交接**：APP-128 补充要求「e2e7 三臂表」**已单独补发**（`msg_52Ta35TCkxRJS1CDLmdVZbCF5yDGbx4gPdFrKHNlMH7bJw`，正文 462 B，未截断）⇒ 交接的前置材料已到位，但 **APP-126 §7「不要开始 v2.6 打包」** 与 reviewer 的 **「v2.6 打包仍等 reviewer 交接」** 仍在 ⇒ **本轮未进 v2.6、未打包、未跑 10 分钟整链、未抽听**，**等 reviewer 明确交接指令**。
6. 🟡 沿用未结项：**v2.5 重签 ACCEPTED**（ACCEPTED 仍指 v2.4）｜**发客户必须确认发 `v1.1.1.zip`**｜**目标机三件套**（删 zip 授权／实机 `--check`／两端 SHA256 对账）**仍被 A 机已离开 `192.168.2.0/24` 挡住**（现 `10.188.194.152/21`）｜**ASR ahead 2 只报告不代劳**。
