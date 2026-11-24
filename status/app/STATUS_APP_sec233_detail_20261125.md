# §233 巡检详情（2026-11-25 01:5x）

> 🔴 本文件是 `status/app/STATUS_APP.md` 的 **§233** 节正文（APP-052④：正文放 companion，活文档只留标题行＋指针行）。
> 归档件 write-once（写一次不再改）。

## §0 六通道复核 ⇒ **无新 App 纠偏**，`last_ack` 仍 **APP-133**（值不变）

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| 1 | 局域网 `status/app/CORRECTIONS_APP.md` | **130 条／max APP-133**／SHA256 `2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda`／**440 181 B**／mtime **2026-11-24 13:56:42**／纯 LF | 与 §232 轮**逐字一致** ⇒ **无新增** |
| 2 | QQ 收件箱（`alexchen7694@agent.qq.com`） | 最新 **App 封 = APP-133**（`msg_HbiVRXlg…`，2026-11-24T05:56:40Z）＝ §230 已执行；其后仅 **H-028 [MT]**（10:11:12Z），其正文明确「**App 接入等本条验收后另发 APP 纠偏**」 | ⇒ **不据此动 App 代码** |
| 3 | QQ 垃圾箱 | **0** | — |
| 4 | QQ 已删除 | **1**（`msg_Ui-Sz0Cw…`，MiniMVP rc9 性能报告，11-13，**与 App 无关**） | — |
| 5 | 全库检索 `APP-1(3[4-9]|[4-9][0-9])` | **0 个真命中**（唯一命中是 `results/app/win_capture.py:49` 的 **APP-178** 注释，10-31，属**别的模块**编号引用） | ⇒ **无 APP-134+** |
| 6 | 根 `status/CORRECTIONS.md` | max **C-135**（已冻结）｜`shared/NOTICE*` 最新仍 **2026-11-05 09:35**｜agent-mail **`not_bound`**（工具明确「当前请勿重试」⇒ 试 1 次即停） | — |

⇒ **本轮是待命轮**（APP-085 §2）＋ **TAKEOVER 接续轮**（下一节）⇒ `last_ack` **仍 APP-133**，**值不变**。

## §1 TAKEOVER 交接（上一会话死在「核实事实」中途）

- `acquire app` ⇒ exit 0 / **TAKEOVER**：上一 token **`b1933ada`**，started **11-24 23:07:24**，last_beat **11-24 23:50:08**（＝接管时 **108 min 前**）⇒ **死会话**；note＝`verified 6 channels empty; found 4 real defects; verifying facts`；`live_pids=[]` `alive=False`。
- 本轮 token **`b13b16db`**，beats ×N ⇒ 收尾 `release`。
- 🔴 **上一会话未留下任何可交付物**：仓库内**无**它新增/修改的文件（实测 11-24 22:50 → 11-25 01:40 全仓 mtime 扫描：**0 个**文件）；`status/app/STATUS_APP.md` **没有 §233**；automation memory **最后一条仍是 §232**；当日日志 `2026-11-24.md` **无本轮条目**。
- ⇒ **取证方式**：按纪律「**WorkBuddy 会话 JSONL 是最强取证源**」，从
  `~/.workbuddy/projects/c-Users-Trekker-PTL-confucius4-openvino/bb563780-642b-4d0d-9260-b258a87aa629.jsonl`
  （430 条记录／162 次 `function_call`）**重建**上一会话的分析链，取回其「4 处真缺陷」清单。
- 🔴 **纪律**：上一会话的结论**不直接采信** ⇒ 本轮把 4 处**逐条独立复核**（§2）后，才动手改。

## §2 四处真缺陷：逐条根因 → 修法 → 独立复核

### §2.1 缺陷①：**`STATUS_APP.md` 只剩 196 B 余量**（结构性阻塞，本轮必修）

- **实测**：写前 **39 804 B**／硬上限 **40 000 B**（APP-052④／APP-049）⇒ **余量 196 B**；行数 116／300。
- **为何是「阻塞」**：历史每轮追加一个 `## §N`（标题行＋指针行＋「最近更新」条目）实测 **792–1 958 B**
  （§228 = 1 224 B／§229 = 1 362 B／§230 = 1 658 B／§231 = 819 B／§232 = 792 B）
  ⇒ **下一轮写 §N 必然超限** ⇒ 会把「下轮纠偏记录」直接卡死。
- **修法（沿用本仓既有成例，非新发明）**：把 **§211–§227 的「标题行＋指针行」整块逐字归档**（write-once），
  活文档换 **1 行指针**。成例①`status/archive/STATUS_APP_sec181_210_headers_20261123.md`（15 517 B）
  成例②`…_sec162_169_headers_20260720.md` 成例③`…_sec135_140_headers_20261113.md`。
- **为何可只归档「标题行＋指针行」**：§211–§227 的**正文本来就不在活文档里**（全在 companion／archive），
  活文档这 **15 115 B** 全是标题行＋指针行 ⇒ **归档不丢任何正文**。
- **归档前逐条校验**：该区域内 **14 个** `status/...` 指针目标**全部存在**（**14/14**，缺失 0）。
- **产出**：`status/archive/STATUS_APP_sec211_227_headers_20261125.md`（**15 392 B**／SHA256 `06321204a90df5d87b8ca27b06078634a67accd1864fb470d6b2a3e39f2f9c0a`／
  归档块 SHA256 `5ffe7d1749d37efa…`／**15 115 B**）；活文档 **39 804 → 24 998 B**（余量 **196 → 15 002 B**）。
- **独立复核**（`results/app/_app233_verify_status.py`，**另起脚本**，不 import 被检脚本）：**17/17 PASS**
  ① ≤40 000 B／≤300 行 ② 归档件**逐字含原区间字节** ③ 头部声明 SHA/字节数与实际块一致
  ④ **还原式复核＝逐字节等于写前备份** ⑤ 每个旧节号都被交代（live∪archived，lost=0）⑥ `last_ack` 唯一且仍 APP-133
  ⑦ 归档件内 **15 个**指针目标全存在 ⑧ 头部索引含新归档件路径
  ⑨ **反证组**：篡改归档块 1 字节 ⇒ 判据 2/3/4 **全部 FAIL** ⇒ 判据有鉴别力、非常 PASS。

### §2.2 缺陷②：**v2.6 的 README 出现双标题**（客户可见缺陷）

- **实测**（真包 `Confucius4_LiveCaption_v2.6`）：
  `README_zh.md` 的 `## v2.6 改动说明` 出现 **2 次**（**第 1 个是空段**：其后紧跟第 2 个同名标题）；
  `README_en.md` 出现空的 `## What's new in v2.6` ＋ `## v2.6 changes`。
- **根因（不是「人写错了」）**：`live_caption/sync_c172_version_identity_to_pkg.py` 插入新章节时
  **自己写一个标题**（`## vX.Y 改动说明`），随后把**人撰写的正文**接在标题下面；
  而正文文件 `live_caption/_app129_changelog_2.6_zh.md`（首行 `## v2.6 改动说明`）／
  `_app129_changelog_2.6_en.md`（首行 `## v2.6 changes`）**自身首行就是同一个标题**
  ⇒ 两个标题叠在一起 ⇒ 前一个成空段。
- **修法（开发树 `sync_c172`，真包未动）**：新增 `strip_leading_heading()`，
  **插入前**若正文首行是与插入标题**语义相同**的二级标题则**剥离**（**窄口径**：
  ① 只看**首行**；② 必须是**恰好 `## `**（`### 1. xxx` 属正文小节，**绝不剥**）；
  ③ 文字相同**或**含本版本号 `v<ver>`（英文 `## v2.6 changes` 即属此类））⇒ **幂等**（正文不带标题时是 no-op）。
- **独立复核 1**（`results/app/_app233_verify_sync_c172.py`，**行为级真跑** `build_blocks`）：**16/16 PASS**
  ① ZH 标题恰好 1 次 ② 无空标题段 ③ EN `## v2.6 changes` 消失 ④ 剥离后正文**逐字**等于原正文
  ⑤ 幂等（正文不带标题 ⇒ 产出不变）⑥ 不误伤 `###` 小节
  ⑦ **反证组**：把剥离函数换成恒不剥离的旧实现 ⇒ 判据 1/2 **FAIL**（ZH 标题数 = 2、EN 残留 1）⇒ 判据有鉴别力。
- **独立复核 2**（`results/app/_app233_verify_sync_c172_e2e.py`，**影子包端到端**）：
  把真包的 README/NOTICE/MANIFEST **复制**到 `%TEMP%` 影子目录，在**影子**上真跑
  `python live_caption/sync_c172_version_identity_to_pkg.py --pkg <影子> --changelog-zh … --changelog-en …`：
  **23/23 PASS** ① dry-run **一个字节都不写** ② 走**插入分支**后 ZH 标题**恰好 1 次**、EN `## v2.6 changes` **消失**
  ③ MANIFEST.version `2.5 → 2.6` ④ NOTICE 首行 = 2.6 ⑤ 正文小节仍在、正文与源文件**逐字相同**
  ⑥ **幂等**（再跑一次 4 个文件 SHA 不变）⑦ **已含 v2.6 段的包 ⇒ 脚本跳过、不重写**（章节正文归人撰写）
  ⑧ **真包 4 个文件 SHA256 跑前跑后一致** ⇒ 影子隔离有效 ⑨ 反证组（正文不带标题 ⇒ 仍恰好 1 个标题）。
- 🔴 **真包未动**（APP-055：禁止原地修改已签 ACCEPTED 的包）⇒ v2.6 的 README 仍带该缺陷
  ⇒ **如实登记于 §4**；**下一版**（v2.7）自然带对。

### §2.3 缺陷③：**v2.6 的 `app/MANIFEST.json` 写着 `version=2.5`**

- **实测**：`Confucius4_LiveCaption_v2.6/app/MANIFEST.json` → `version=2.5`，
  且与 `Confucius4_LiveCaption_v2.5/app/MANIFEST.json` **逐字节相同**（md5 均为 `239ea82a4b1a12f9ad2e8cf55f244097`）
  ⇒ 它是 robocopy 复制来的**原件，从未被刷新**（其 mtime 仍是 **11-20 11:29:16**＝v2.5 那次）。
- **根因（生产路径）**：`app/MANIFEST.json` 的 `version` 字段**只有** `pack_v13.py` 的
  `refresh_manifest()` 会写（实测该函数在 `pack_v13.py:474`，其 `data['version'] = PKG_VERSION` 在 `pack_v13.py:505`），
  而它挂在 **`_run()`（打包阶段）**里 ⇒ **完整版线（v2.x）从来不出 zip**（用户规则「不通知 ⇒ 不打包」）
  ⇒ 打包阶段**永不执行** ⇒ 这个字段**永远不会被刷新**。
  （v2.1/v2.2/v2.3/v2.4/v2.5 的 MANIFEST.version 都对，唯独 v2.6 错 ⇒ 与「v2.6 走了 copy+sync 而没走 pack」吻合。）
- **闸门为什么没拦住**：`results/app/app170_version_identity_gate.py` 的 **I1b** 把这种不一致**降级为「提醒」**，
  且原文写「**zip 级断言兜底**」⇒ 但完整版线**没有 zip** ⇒ **那个兜底不存在** ⇒ 提醒实际无人兜底。
- **修法（两处，均在开发树，真包未动）**：
  ① **生产路径补齐**：`sync_c172_version_identity_to_pkg.py` 新增 `sync_manifest_version()`
  （同步 `app/MANIFEST.json` 的 `version`；**只改这一个字段**，
  `files`/`bytes` 仍归打包净载荷口径；写盘格式与 `refresh_manifest()` 一致
  `indent=1`/`ensure_ascii=False`/`newline=''` ⇒ **JSON 往返逐字节稳定**；**幂等**（已是目标版本 ⇒ **一个字节都不写**））。
  ② **闸门提醒措辞**：I1b 的提醒由「zip 级断言兜底」改为**真实修法**
  （`sync_c172_version_identity_to_pkg.py --pkg <包目录>`）⇒ 不再让 reviewer 误以为有兜底。
- **独立复核**（`results/app/_app233_verify_manifest_sync.py`，**行为级真跑**，只在 `%TEMP%` 建临时包）：**19/19 PASS**
  ① version `2.5 → 2.6` ② **其它字段逐字未变**（files/bytes/packages/notes）③ 写盘格式往返逐字节稳定
  ④ **幂等**（ALREADY／内容／mtime／SHA256 全不变）⑤ dry-run **不写盘** ⑥ 无 MANIFEST ⇒ `MISSING` 不炸
  ⑦ **反证组**：换成「恒不写」的旧实现 ⇒ 判据 1/2 **FAIL** ⇒ 判据有鉴别力
  ⑧ **真实包复现**（只读）：`version='2.5'` 且与 v2.5 的 MANIFEST 逐字节相同 ⇒ 缺陷可复现。

### §2.4 缺陷④：**入库的 app170 证据与实包对不上**（追溯性缺陷）

- **实测**：入库 `results/app/app170_version_identity_gate_evidence.json`（mtime **11-24 13:14**，1 093 B）记
  `README_zh.md` sha256 `6f8b933e1dcb4f92…`／**55 968 B**、`D4 count=0`；
  而**实包**是 `0bb23e7cfa39f24d…`／**57 986 B**、`D4 count=2`
  ⇒ **入库件不是实包事实** ⇒ reviewer 拿入库件复算会对不上。
- **根因**：证据生成于 **13:14**（改动说明插入**之前**），之后 README 变了（13:14:55）但**证据没重生成**。
- **修法**：重跑闸门刷新入库证据（`app170_version_identity_gate.py --pkg <v2.6> --expect-version 2.6 --json <入库路径>`；
  该脚本对**真包只读**——实测只写 `%TEMP%` 影子目录与 `--json` 输出）。
- **复核**：刷新后 `README_zh` `0bb23e7cfa39f24d…`／**57 986 B**、`README_en` `6d67d4d690b2fc0c…`／**64 782 B**、
  `NOTICE` `22d70a34316d4e49…`／**10 327 B** ⇒ **与实包磁盘实测逐字节一致**；闸门 **PASS=19 / FAIL=0**；
  两条提醒如实保留：**I1b**（`manifest=2.5 target=2.6`）与 **D4**（`count=2`）⇒ **不掩盖**。

## §3 交付面只读复核（不写任何客户包）

| 对象 | 实测 | 结论 |
|---|---|---|
| `Confucius4_LiveCaption_v2.6/ACCEPTED.json` | `version=2.6`／`accepted_at=2026-11-24 18:26:21`／`corrections=[APP-129,130,131,132,133,123]`／`ext=v0.4.21(b2a4978)`／`n_production_modules=33`／`code_fingerprint=1a3a849f…` | 🟢 v2.6 **确已签 ACCEPTED** ⇒ 本轮**不碰** |
| v2.6 包规模 | python walk 实测 **48 792 文件／26 156 520 495 B**（含 `models/bgsep`） | 已写入「当前有效结论」表 |
| `Confucius4_LiveCaption_v2.6.staging` | 残留 **25 GB**（`du -sh` 实测） | 🔴 **未删**（删属破坏性 ⇒ **待用户授权**）⇒ 登记于 §4 |
| MiniMVP zip | `Confucius4_LiveCaption_MiniMVP_v1.1.1.zip` **5 212 403 155 B**（11-23 10:31）；旧 `v1.1.zip` **5 212 356 737 B**（11-22 16:51） | 🟢 **发客户发 `v1.1.1.zip`**（旧的不自证） |
| APP-086·2a 缺陷包清单 | **本轮独立复核**：`v2.2`/`v2.3`/`v2.3_aborted`/`v2.4` 的 `app/tts_worker.py` **含** `elif self._has_clone_voice():`（缺 `and not _bound`）⇒ **带缺陷**；`v2.1`/`v2.5`/`v2.6` **不含**该行 ⇒ **无此缺陷** | 🟢 表内「带缺陷共 10 个」的清单**经独立复核成立** |

## §4 🔴 三处**如实登记**（未修 / 不擅自修）

1. **v2.6 包的 README 双标题**（§2.2）——**修法已落在开发树**，但**真包未动**（APP-055 禁止原地改已签包）
   ⇒ **需要出 v2.7 才会带上修复** ⇒ **是否出 v2.7／何时出** ⇒ **待用户与 reviewer 裁定**。
2. **v2.6 包的 `app/MANIFEST.json` `version=2.5`**（§2.3）——同上：**修法已落开发树**，**真包未动**
   ⇒ 随 v2.7 一并带对。**风险等级**：客户核对版本号会得到错误结论（APP-007 的原始教训），
   但**运行时不受影响**（`live_caption_app.py:1277` 只把 `app/MANIFEST.json` 当**标记文件**判「是不是包」，**不读 version**）。
3. **`results/app/app231_pack_lock_events.jsonl` 不存在且未入库** —— 它被 **4 处**当成「生产路径建锁」的审计指针
   （§231 companion §5⑤／`MEMORY_MODULES.md` 第 2955 行／当日日志／automation memory）。
   **根因**：该文件由 §231 修好的**生产路径**（`live_caption/_app116_build_v25.py` 的 `_lock_event()`）在**运行时**创建，
   而 v2.6 那次构建跑在 **§231 修复提交（eb82d17，11-24 20:28）之前** ⇒ **该文件尚未被生产路径产出**。
   ⇒ **正确处置＝如实记录，不伪造**：🔴 **不**创建一个空文件（那是**制造证据**）；
   ⇒ 下一轮真跑成包路径时它会自动出现，届时应一并入库。**§231 的「lock_lost 0 条」结论不受影响**
   （其证据是 `results/app/app132_lock_events.jsonl`，**已入库**且内容属实）。
4. **`Confucius4_LiveCaption_v2.6.staging` 残留 25 GB** —— 属**用户目录下的构建残留**，
   删除是**破坏性操作** ⇒ **本轮未删**，报告待授权。

## §5 独立复核汇总（各脚本均含**反证组**）

| 脚本 | 用途 | 结果 |
|---|---|---|
| `results/app/_app233_verify_status.py` | 压缩后的**独立**写后复核 | **17/17 PASS**（反证组 3 条全 FAIL 如期） |
| `results/app/_app233_verify_sync_c172.py` | 双标题修复**行为级**复核 | **16/16 PASS**（反证组 2 条全 FAIL 如期） |
| `results/app/_app233_verify_manifest_sync.py` | MANIFEST 同步**行为级**复核 | **19/19 PASS**（反证组 2 条全 FAIL 如期） |
| `results/app/_app233_verify_sync_c172_e2e.py` | **影子包端到端**复核 | **23/23 PASS**（含真包隔离检查） |

🔴 **本轮踩到并已修掉的判据坑（可复用）**：
① **「章节号集合不变」是错判据** —— 归档标题行**本来就要**把那些 §N 从活文档移走 ⇒ 该断言**必假 FAIL**
   ⇒ 正确判据是「**没有丢**」：`old ⊆ new ∪ archived`。
② **行尾 off-by-one**：指针行自带结尾 `\n`，再补一个 `eol` ⇒ 落盘 `\n\n` ⇒ **多 1 字节**＋**孤立 LF**
   ⇒ 由「**还原式复核**」判据如实抓出（39 805 vs 39 804 B）⇒ 修法＝按**实际区域行尾**只写**一个**终止符。
   （🔴 判据：`is_crlf_block` 不能用 `crlf == lf_total` 判 —— §211–§227 区间**CRLF 37／LF 总数 38**
   ⇒ 块**尾**那一行本就是孤立 LF ⇒ 指针行应沿用**单个 LF**。）
③ **测试脚本自己也会造假 FAIL**：第一版 e2e 用 `str.find(正则串)` 找下一段（**字面**匹配 ⇒ -1 ⇒ **把文件截断**）
   ⇒ 表现为「插入后 count=0」⇒ **假 FAIL 源**；已改用 `re.search`。
④ **「修好 harness」≠「修好产品」**：本轮两处包内缺陷的修法都落在**生产路径**
   （`sync_c172`＝通用版本标识同步器，由 `pack_v13` 在打包流程里调用），**不是**落在某次构建的旁路脚本。

## §6 纪律自查

- 🟢 **未打包 zip**（用户级纪律「**不通知 ⇒ 不打包**」＋ APP-055／APP-126 §7）——本轮**未**产出任何 zip。
- 🟢 **未覆盖 / 未删除**任何旧版本目录与 zip；**未改**任何客户包既有文件（v2.6 4 个文件跑前跑后 SHA256 一致）。
- 🟢 **未跑推理 / 未测速** ⇒ **未取 `shared\MACHINE_LOCK`**；**未调 MiniMax**；**未连 B 机**（APP-109 ④）。
- 🟢 **未进 MiniMVP 包**、**未进 v2.6 包**（只读复核）。
- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ **SHA 零改动**，见 §7）。
- 🟢 **未吞其它模块的未提交改动**（全仓脏文件多为 ASR/MT/TTS 的，本轮**只 add App 侧**文件）。
- 🟢 **普通 push，无 force push**；**只 add** App 侧文件；**绝不 add** `status/app/CORRECTIONS_APP.md`。
- 🟢 **未改** `MEMORY.md` 的 `last_ack` 语义（本轮 `last_ack` 仍 APP-133）。

## §7 纠偏文件收尾四项指纹（**SHA 零改动**）

| 项 | 开工时（11-25 01:37） | 收尾时 | 一致 |
|---|---|---|---|
| SHA256 | `2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda` | 同左 | ✅ |
| 字节数 | **440 181 B** | 同左 | ✅ |
| mtime | **2026-11-24 13:56:42** | 同左 | ✅ |
| `## APP-xxx` 条数 | **130 条／max APP-133** | 同左 | ✅ |

⇒ **reviewer 未在本轮中途追加新条目**；本文件**全程只读**。

## §8 下一轮

- `last_ack` 仍 **APP-133**；⏭ 等 reviewer 复核 **§233**（本轮）。
- 🔴 **待 reviewer / 用户裁定**：① **是否出 v2.7**（带 README 双标题 + MANIFEST.version 两处修复）
  ② **是否删除** `Confucius4_LiveCaption_v2.6.staging`（**25 GB**）③ `results/app/app231_pack_lock_events.jsonl`
  等下一轮成包路径产出后**入库** ④ **v2.5 重签 ACCEPTED**（ACCEPTED 仍指 v2.4 的签名）
  ⑤ 仓库根 `.gitattributes` 根治（跨模块，854 个 `i/lf+w/crlf`，§226 §9-2）⑥ 默认分离设备 ⑦ `n_speakers=0` 口径。
