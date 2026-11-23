# §222 App 巡检轮（接续上一会话 TAKEOVER）· 2026-11-23 12:2x

> 生成脚本：`live_caption/_app222_closure_evidence.py`（**只读交付面**，数字全部从证据 json 读出）。
> 证据：`results/app/app222_closure_evidence.json`。

## §0 一句话结论

🟢 **六通道复核：没有新的 App reviewer 纠偏**（局域网 `CORRECTIONS_APP.md` **119 条 / max APP-121** ＝ `last_ack`；QQ 收件箱最新 App 封仍是 **APP-121**＝已执行；spam 0；trash 1（非 reviewer）；agent-mail `not_bound`）⇒ **`last_ack` 保持 APP-121**。
🔴 **但上一会话（token `ae2aabbb`，09:15 起，10:32 后失联）死在了收尾** ⇒ 本轮从断点继续，**闭合它遗留的 4 处半交付**（发信记录与事实不符／证据脚本未入库／复算底本未入库／构建依赖未入库）。
🟢 **交付面只读复核全部成立**：v1.1.1 zip **10 881 条 / 解压 6 701 780 843 B**、README 数字逐项吻合；`ACCEPTED.json` 指纹 31 模块 **==** zip 内 `app/*.py` 31 个（**双向等集**）；dev 树 ＝ v2.5 ＝ v1.1.1 **同字节**（5 个模块全同）。
🟡 **两项待 reviewer/用户裁定**（本轮**未自行推进**）：ASR §91 ④ 的 NPU 前缀截断处置、⑤ 的归因订正范围。
**本条需等 reviewer 复核**。

## §1 六通道复核（纠偏来源）

| 通道 | 结果 |
|---|---|
| 局域网 `status/app/CORRECTIONS_APP.md` | **119 条 / max APP-121** ⇒ **无 APP-122+**；SHA256 `784474d0deed33caa8568bf8dded7550c31b4efd26414cf02c4afdfad8ffcf8a`／**407 531 B**／mtime **2026-11-23 09:04:26** |
| QQ 收件箱 | 最新 App 封 = **APP-121**（11-23 09:03，**已执行**＝§221）；其后新增 3 封均为 **TTS-076/077**（TTS 模块，**非 App**）⇒ **无 APP-122+** |
| QQ 垃圾箱 | **0 封**（按 `APP-` 检索） |
| QQ 回收站 | 1 封＝MiniMVP rc9 性能报告（收件人 `alexgang.chen@gmail.com`，**非 reviewer** ⇒ **未动、未标已读**） |
| QQ 已发 | 上一轮的 APP-121 STATUS 邮件**已发出**（`msg_TLpF6ASrLJ0eMX66kNa27tOTntU-DbIRGoNAc4XYjwiCRA`，11-23 10:44:31）⇒ 本轮**不重发**同一封 |
| agent-mail | **`not_bound`**（仍未开通）⇒ 走 QQ 邮箱 |

🔴 **开工 / 收尾各测一次** `CORRECTIONS_APP.md` 的 SHA／字节／mtime／条数 ⇒ **四项一致 ⇒ SHA 零改动**（本轮**从未写入**该文件，它是 reviewer 独占）。
🔴 **执行纪律**：一条新纠偏都没有 ⇒ **未改任何产品代码／未改客户包／未打包／未跑推理或计时（⇒ 未取 `MACHINE_LOCK`）／未调 MiniMax／未连 B 机（APP-109 ④）**。

## §2 上一会话遗留的 4 处半交付（本轮闭合）

上一会话的租约 note 停在「zip 已打好；解压自检运行中」，但它**在 note 之后继续做完了 §221 并提交推送**（`88b9ea8` 已在 `origin/main`）⇒ 真正的残留在**它没来得及做的收尾动作**上：

### HD1 🔴 `results/app/_app121_email_body.txt`：**仓库里的「发信记录」与实际发出的邮件不符**

| 版本 | 字节 | 占位符 `COMMIT_SHA` | 说「详见附件」 | 含真 SHA `88b9ea8` | 含 companion SHA |
|---|---|---|---|---|---|
| **HEAD（已提交）** | 3 398 | **有**（`提交 COMMIT_SHA（main）`） | **有** | **无** | 无 |
| **工作区** | 3 120 | 无 | 无 | **有** | **有**（`bf176bdbddb7fb2b`） |

* 实际发出的那封邮件 `msg_TLpF6ASrLJ0eMX66kNa27tOTntU-DbIRGoNAc4XYjwiCRA`：`has_attachments=**false**` ⇒ **根本没有附件**；正文是「正文见 A 机 `status/app/STATUS_APP_sec221_detail_20261123.md`（24085 B，SHA bf176bdbddb7fb2b）…提交 **88b9ea8**（main）」⇒ **＝ 工作区版本**。
* ⇒ **HEAD 版是一份从未发出的草稿**：里面既写着未填的占位符、又许诺了一个不存在的附件。reviewer 若翻到仓库里的这份「发信记录」，会看到与实际收到的邮件**两份不一样的正文**。
* 🔴 **处置**：本轮**提交工作区版本**（＝实际发出的那份）⇒ 仓库记录与事实一致。

### HD2 🔴 `live_caption/_app121_zip_extract_check.py`：**证据在，产生证据的脚本不在**

* 它的产物 `results/app/app121_zip_extract_check.json` **已入库**，且被 **§221 §3（reviewer 第 3 条「解压自检」）** 直接引用。
* 其它 **13** 个 `_app121_*.py` 脚本**全部已入库** ⇒ 只剩它一个漏网。
* ⇒ reviewer 要复核「解压自检」这一项时，**脚本不在仓库里** ⇒ 无法重跑、无法验证。
* 🔴 **处置**：本轮入库。

### HD3 🔴 本轮 10 分钟整链的**逐句 jsonl ＋ 积压曲线**未入库

* §221 §5 引用的验收 json `app591_acceptance_app121_v111_default_run20261123-1000.json` **已入库**；但它的**底本**（逐句 `tts.jsonl` 258 211 B ＋ `backlog_curve.csv` 22 759 B）**未入库**。
* **同侪臂（app119/sp5）的同类文件全部入库** ⇒ 这不是「本就不入库」的约定，是漏了。
* 🔴 **依据**：reviewer 对 APP-120 的 10 分钟整链**就是用 jsonl 复算的**（§221 §0 引 review 原话：「reviewer 本机用 jsonl 复算（SHA **b3a72990…**）」—— 该 SHA 即 `_app591_app120_v11_..._tts_out.wav.tts.jsonl` 的实测 SHA）⇒ **jsonl 是 reviewer 复算的底本**。
* ⇒ 缺了它，reviewer **无法独立复算本轮 14/14 的数字**。
* 🔴 **处置**：本轮入库 jsonl ＋ csv（**wav 本体不入库**，与同侪一致：`_app591*.wav` 全仓库 0 个入库）。

### HD4 🔴 `live_caption/package_profiles.py`：**已入库的构建脚本 import 了一个未入库的模块**

* `live_caption/_app120_build_minimvp_v11.py`（**已入库**）第 42 行：`from package_profiles import PROFILE_RULES, is_excluded, top_dirs`。
* `package_profiles.py` 本身 **未入库**（9 763 B，SHA `4ca63cc4ae0bf937…`）—— 它是 APP-118 §2「**一份代码三形态**」的裁剪规则**唯一定义处**（`full` / `minimvp` / `specialmvp` 三张表）。
* ⇒ **干净 clone 后跑 MiniMVP 构建 ⇒ `ImportError` ⇒ 无法重建包**。
* 🔴 **处置**：本轮入库。

## §3 交付面只读复核（本轮实测）

| 项 | 实测 | 判定 |
|---|---|---|
| `Confucius4_LiveCaption_MiniMVP_v1.1.1.zip` | **5 212 403 155 B**（mtime 11-23 10:31:48） | — |
| zip 内文件条目 | **10 881** | ✅ 与 README 所写 10 881 一致 |
| zip 内条目**解压后**总字节 | **6 701 780 843 B** | ✅ 与 README 所写 6 701 780 843 一致 |
| `ACCEPTED.json` 指纹键集 vs zip 内 `app/*.py` | **31 vs 31，双向等集**（`fp-not-in-zip=[]`、`zip-not-in-fp=[]`） | ✅ 「签的和发的同一份」成立 |
| `ACCEPTED.json` version | **1.1.1** | ✅ |
| dev 树 ＝ v2.5 ＝ v1.1.1 | 5 个模块 SHA **全同**（`asr06b_stateful_backend.py` `36f20581799f`／`live_caption_app.py` `9cd8e8bf72c6`／`device_config.py` `4e6b50266340`／`tts_worker.py` `ae9007450ee9`／`tts_engine.py` `c2b031726e12`） | ✅ 一份代码三处同字节 |
| `Confucius4_LiveCaption_v2.5/ACCEPTED.json` | version 仍 **2.4**、pkg_dir 仍指向 **v2.4** | 🔴 **未重签 ⇒ 闸门 fail-closed ⇒ v2.5 仍打不出 zip**（沿用 §220 未结项，本轮**未改**） |

🔴 **一个口径澄清（reviewer APP-121 §4 的数字来源）**：reviewer 给的「**6 701 773 512 B**」是 **v1.1** zip 的解压总量（**本轮实测：v1.1 zip 解压 ＝ 6 701 773 512 B，v1.1.1 zip 解压 ＝ 6 701 780 843 B**，差 7 331 B ＝ README 自身改动）。README 写的是**它所在那个 zip（v1.1.1）**的实际数字 ⇒ **不是没照 reviewer 改，而是 reviewer 的数字取自上一个 zip**。

## §4 ASR §91 的两条交叉结论（本模块自证，**不替 ASR 下结论**）

### ④ App 侧 NPU 的 `prefix_truncations` ＝ 3（ZH）— **属实**

* 证据（本模块自己的产物）：`results/app/app121_asr_app_3mat_NPU.json` ⇒ **ZH `prefix_truncations=3`**（spe 0／en 0）；`…_GPU0.json` ⇒ **三素材全 0**。
* ⇒ 与 ASR §91 ④ 完全一致：**NPU 档在 App 生产路径上确实会触发前缀截断**（GPU.0 同素材 0 次 ⇒ 设备档差异，非素材差异）。
* 🔴 **本轮不自行处置**（三个选项各自都要 reviewer/用户拍板，见 §5 ①）。

### ⑤ 「① 切段器不同 ⇒ 段边界/段数本就不一致」— **§221 正文不需要撤回；缺陷在别处**

* ASR 引的那句话**不在** §221 companion 正文里 —— §221 §2 正文写的是「**段边界一致**：三个素材的段数 App 与参照**完全相同**（spe 93/93、en 65/65、zh 66/66）⇒ **切段器行为一致**，差异**不在切段**」。
* 那句话**只在**证据 json 的 `ref_diff_explanation[].reasons[0]` —— **harness 里的一段静态字面量**（`live_caption/_app121_asr_app_3mat.py` L288-290）。
* 🔴 **且该 json 自相矛盾**：它自己的 `n_segs_app` **==** `n_segs_ref`（三素材 93/65/66 全同）⇒ reasons[0] 断言的「段数本就不一致」**被本文件自己的实测否掉**。
* ⇒ **§221 的正文结论无需撤回**；**真正要修的是那段静态说明串**（它会误导读者）。本轮**只报告、不擅自改写已入库的证据产物**（改写＝篡改历史证据）⇒ 列为 §5 ② 待 reviewer 裁定处置范围。

## §5 待 reviewer / 用户裁定（本轮**未自行推进**，逐条列出）

| # | 事项 | 背景 | 为什么不能自行决定 |
|---|---|---|---|
| ① | **NPU 档前缀截断的处置** | ASR §91 ④：App 侧 NPU 在 ZH 上 `prefix_truncations=3`（GPU.0 ＝ 0）；机制上会丢句首，但**质量影响本轮未观测到**（4 个长段 NPU/GPU 转写逐字节相同，4 处差异全在短段） | ASR 给了三个选项：① `MAX_SEG_SEC` 降到 ≈19 s（不动 pml／不动 §86 RTF／不动 GPU 档）／② 超预算丢段尾前缀而非左截断／③ 上调 pml（**会改变 §86 全部 RTF 数字 ⇒ 必须重测**）。**任一选项都会改产品行为与交付内容** ⇒ 须 reviewer/用户拍板，且 **③ 必须重测** |
| ② | **§221 证据 json 里的静态说明串** | `app121_asr_app_3mat_{NPU,GPU0,GPU0_OLD_v11}.json` 的 `reasons[0]` 断言「段数本就不一致」，与**同文件**的 `n_segs_app==n_segs_ref` 矛盾；§221 companion 正文已写对 | **改写已入库的证据产物＝篡改历史证据**。可选：① 保持原样、在 STATUS 里注明（**§222 已做**）／② 由 reviewer/用户授权后**重跑**该 harness 生成新证据替换／③ 只在 harness 源码里加注释说明、产物不动 |
| ③ | **README 是否加「NPU 档长段会触发前缀截断」已知问题** | ASR §91 提到的读者可见问题；**App §221 §4 重写后的 README 目前没有这一条** | 改 README ⇒ 改客户包 ⇒ 须走新版本号（APP-055）＋ 重签 ACCEPTED ＋ 重打 zip ⇒ 须先有决定 |
| ④ | **v2.5 重签 ACCEPTED** | `v2.5/ACCEPTED.json` 仍指向 v2.4 ⇒ 闸门 fail-closed ⇒ **v2.5 打不出 zip** | APP-120 只授权签 v1.1；**连续多轮已报 reviewer，仍未获授权** ⇒ 本轮**未自行重签** |
| ⑤ | **发客户必须确认发的是 `v1.1.1.zip`** | 旧 `v1.1.zip` 的 `ACCEPTED.json` 指纹里**含 `tts_cuda.py`/`tts_cuda_sidecar.py`**（33 条），而 v1.1 zip 内 `app/*.py` 只有 31 个 ⇒ **旧 v1.1 zip 不自证**；v1.1.1 是 31==31 **自证** | 发哪个包是**交付决定**（且旧 zip 还在盘上，**按纪律不覆盖不删**） |

## §6 本轮纪律

* 🔴 **只提交 App 模块负责的文件**：`results/app/_app121_email_body.txt`（HD1）、`live_caption/_app121_zip_extract_check.py`（HD2）、本轮整链 `tts.jsonl` ＋ `backlog_curve.csv`（HD3）、`live_caption/package_profiles.py`（HD4）、`status/app/STATUS_APP.md` ＋ 本 companion、`results/app/app222_closure_evidence.json`、本证据脚本。
* 🔴 **绝不提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占；它的 ` M` 是 reviewer 真追加）；**不吞** `status/CORRECTIONS.md`、`status/STATUS_ARCHIVE_2026-10.md` 及其它模块的未提交改动（`status/CORRECTIONS.md` 的 ` M` 同样是 reviewer 真追加）。
* 🔴 **刻意不提交**（附理由，避免下一轮误当漏网）：`app523_pack_must_ttsworker_evidence.json`（§199/§200 **明确 hold**「等 reviewer 对 app523 裁定，不预判」）／`app170_version_identity_gate_evidence.json`（早期残留，**§191 已引用**它 ⇒ 不擅自替换被引用的证据产物，列为待裁定）／`app157_*.json` 与 `app468_*.json`（**autocrlf 假阳性**，`git diff --numstat` 无内容差异）／`live_caption/sync_c*.py`（§57 **归属未判定**的历史遗留）。
* 🔴 **未打包**（用户不通知不打包）、**未改任何客户包既有文件**、**未跑推理/计时**（⇒ 未占设备）、**未调 MiniMax**、**未连 B 机**（APP-109 ④）、**未改 `CORRECTIONS_APP.md`**（四项指纹收尾复核一致）。
