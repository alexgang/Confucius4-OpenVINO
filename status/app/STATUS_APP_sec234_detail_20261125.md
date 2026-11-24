# §234 待命轮正文全文（2026-11-25 03:49）

> 配套活文档：`status/app/STATUS_APP.md` 的 `## §234` 章节。
> 本文件是**活文档 §234 的完整正文**（与 §218/§219/§233 同款 companion 做法）。
> **只追加**：本轮不改旧章节；旧结论若被推翻，在 §234 内写「撤回 §x」。

---

## §0 六通道复核：仍无新 App 纠偏 ⇒ `last_ack` 仍 **APP-133**（**值不变**）

开工指纹（`status/app/CORRECTIONS_APP.md`）：
**130 条 / max APP-133 / SHA256 `2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda` /
440 181 B / mtime 2026-11-24 13:56:42**（与 §232、§233 轮**逐字一致** ⇒ 本轮期间**无人追加**）。

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| 1 | 局域网 `status/app/CORRECTIONS_APP.md` | 130 条／max **APP-133**／SHA `2db65bf1…`／440 181 B／mtime 11-24 13:56:42 | 无新条目 |
| 2 | QQ 收件箱（reviewer `alexchen7694@agent.qq.com`） | 最新 App 封仍 = **APP-133**（`msg_HbiVRXlg…`，11-24 05:56:40Z）＝**已执行**；其后仅 **H-028 [MT]**（`msg_23BciIYN…`，11-24 10:11:12Z），正文明写「本条只做 MT 模块的模型侧工作，**不要改 App 代码和任何客户包**；App 侧替换由 reviewer 在本条验收后**另发 APP 纠偏**」 | **不据此动 App 代码** |
| 3 | QQ 垃圾箱（spam） | 0 封 | 空 |
| 4 | QQ 已删除（trash） | 1 封＝MiniMVP rc9 性能报告（`msg_Ui-Sz0Cw…`，11-13） | 无关 |
| 5 | 全仓 `APP-134+` 检索 | 命中 **0**（唯一 `APP-178` 是 `results/app/win_capture.py` 注释里的历史编号） | 无新条目 |
| 6 | 根 `status/CORRECTIONS.md` | max **C-135**（已冻结） | 与 App 无关 |
| ＋ | `shared/NOTICE*` | 最新仍 **11-05 09:35** | 无新通知 |
| ＋ | agent-mail（`mcp__agent-mail`） | `not_bound`（工具明确「当前请勿重试」⇒ 试 1 次即停） | 通道不可用 |

⇒ **本地 max（APP-133）＝ QQ max（APP-133）＝ `last_ack`（APP-133）** ⇒
**无新 App 纠偏** ⇒ **`last_ack` 不变**（头部仍 `APP-133`）。

---

## §1 本轮结论：🔴 **不是空转** —— 找到并修掉 **3 处真缺陷**（其中 1 处**阻断下一版成包**）

待命轮按惯例只改 STATUS 头「更新时间」一行；但本轮在**只读复核交付面**时
发现了 3 处**可复现的真缺陷**（全部有硬证据、全部有反证组），故按 §232/§233
同款做法：**修掉 + 如实登记 + 写 §N**。

### 缺陷①（🟡 可复现性）`live_caption/_app129_changelog_2.6_{zh,en}.md` **未入库**

- **实测**：`git ls-files --error-unmatch live_caption/_app129_changelog_2.6_zh.md`
  ⇒ `did not match any file(s) known to git`；`git status` 显示 `??`。
- **危害**：已入库的复核脚本 `results/app/_app233_verify_sync_c172_e2e.py`
  **依赖**这两个文件（`CL_ZH` / `CL_EN` 常量）⇒ **干净 clone 无法跑**该复核
  ⇒ 违反项目「入库完整性（§222）」纪律。
- **实证**：`git archive HEAD | tar -x` 到临时目录 ⇒
  `_app233_verify_sync_c172_e2e.py` **在**、`_app129_changelog_2.6_zh.md` **不在**。
- **修法**：**入库**（不删不改内容）。
  - SHA256 `10d522387ab37bcfb…`／1 995 B／LF×38；
  - SHA256 `ce4de8847c927e20…`／2 450 B。

### 缺陷②（🔴 **阻断下一版成包**）完整版成包路径**从不执行**版本标识同步

- **事实**：`_app129_build_v26.py` 的 stage 有 4 个：`copy` / `sync` / `pack` / `cleanup`。
  - `stage=sync` 只写 `app/tts_engine.py`、`app/tts_worker.py`、`ext/bridge/*`、
    `ext/extension/*`、`ext/extension/manifest.json`、`Start_Bridge.bat`、
    `models/bgsep/*` ⇒ **从不碰** `README_zh.md` / `README_en.md` / `NOTICE` /
    `app/MANIFEST.json`；
  - 唯一会调 `sync_c172` 的是 `pack_v13.py` 的 `main()`；
  - 而**完整版线（v2.x）从来不出 zip**（用户长期规则「不通知 ⇒ 不打包」）
    ⇒ `stage=pack` **不执行** ⇒ `sync_c172` **不执行**。
- **硬证据**：`results/app/app129_build_v26.log`（6 810 B）全文只有
  `stage=copy`（×2）与 `stage=sync`（×5），**没有一行 `stage=pack`**；
  v2.6 的 `README_zh.md` mtime = **2026-11-24 13:14:55**（与
  `_app129_changelog_2.6_zh.md` 的 13:14 同批）⇒ 版本标识是**人工带外**做的。
- **后果**：§233 把修法放进 `sync_c172`（**对的**），但**没接进完整版的成包路径**
  ⇒ 下一版（v2.7）照抄同一套 stage 又要人工做一遍。
- **修法**：
  1. 新增 `live_caption/sync_pkg_identity.py`（**通用、版本无关**）：
     `sync_c172`（**与 pack_v13 同一调用路径**）＋ `app170` 闸门（**同一道闸门**）
     ＋ **自己的一套硬断言**（🔴 闸门的 I1b/D4/D5 是 ADV 建议项 ⇒ 不足以
     fail-closed ⇒ 本脚本另做**硬**判定：README_zh/README_en/NOTICE 标题版本号、
     `app/MANIFEST.json` 的 `version`、本版「改动说明」段**恰好 1 次**）。
  2. `_app129_build_v26.py` 新增**第 5 个 stage `identity`**，并纳入 `all`。
  3. `sync_pkg_identity` 带 **APP-055 护栏**：包内 `ACCEPTED.json` 的
     `version` **等于**目标版本（＝已签的同版本包）⇒ **拒绝改写**（rc=3）；
     升版时新目录带的是**上一版**的 `ACCEPTED.json` ⇒ **放行**（rc=0）。

### 缺陷③（🔴 **阻断下一版成包**）插入锚点的唯一性判据与选取口径**不一致**

- **根因**：`build_blocks()` 用**行锚定正则**（`_ZH_SEC_RE` / `_EN_SEC_RE`）挑插入锚点，
  而 `apply_file()` 的唯一性判据用的是 **`text.count(old)`（子串计数）**。
- **触发条件**：真包 v2.6 的 `README_zh.md` 里 `## v2.6 改动说明` **出现 2 次**
  （第 1 次是**空段**、第 2 次才是正文段 —— 正是 §233 登记的缺陷②，真包按
  APP-055 未动）；而**下一版**是 `robocopy v2.6 ⇒ v2.7` ⇒ **原样继承**这两个标题
  ⇒ 插入 v2.7 段时锚点 = `## v2.6 改动说明` ⇒ `text.count(anchor) == 2`
  ⇒ `apply_file` 报**「命中 2 次（要求恰好 1 次）」** ⇒ **整个身份同步失败**
  ⇒ v2.7 的「改动说明」段**根本插不进去**。
- **为什么 APP-233 的 23/23 复核没抓到**：它的影子包是「**把整段 v2.6 内容切掉**」
  ⇒ 锚点落在 `## v2.5 改动说明`（该串在影子包里**唯一**）⇒ 走的是**另一条路径**
  ⇒ **判据覆盖不到真实路径**（与本项目反复踩的「修了 harness ≠ 修了产品」同型）。
  （§233 的三个复核脚本**本轮全部原样重跑，仍 16/16、23/23、19/19 全 PASS**
  ⇒ **无回归**。）
- **修法（窄口径：只扩展锚点，**不改任何既有章节标题**）**：
  新增 `sync_c172.unique_anchor(text, anchor, pos)`：锚点若已唯一 ⇒
  **原样返回（一个字节都不扩展）**；若不唯一 ⇒ **逐行向后扩展**（先空行、
  再下一个标题行）到全文中**恰好出现 1 次**为止。
  扩展部分**是既有原文**，会原样回填 ⇒ **既有正文一字不变**。
  ZH / EN 两处锚点取用处均改用它。

---

## §2 三处修法的**独立复核**（各含**反证组**）

| 复核脚本 | 判据 | 结果 |
|---|---|---|
| `results/app/_app234_verify_patch.py` | 补丁写入的**独立**复核（`ast`、唯一命中、**正向重建**＝备份＋3 处已知编辑⇒逐行等于现文件、行尾风格、`git diff --numstat`、**反证组**） | **11/11 PASS** |
| `results/app/_app234_verify_identity_tool.py` | `sync_pkg_identity` **行为级真跑**（影子包，真包只读）：A 组 10 条（dry-run 零改动／真跑 rc=0／标题版本号／段恰好 1 次／幂等／反证组）、B 组 2 条（**APP-055 护栏**：同版本已签 ⇒ rc=3 且字节未变；升版场景 ⇒ rc=0 放行）、C 组 1 条（真包 4 文件逐字节一致） | **17/17 PASS** |
| `results/app/_app234_verify_anchor_fix.py` | 缺陷③修法**独立**复核：A 组 9 条（**真实 v2.7 成包路径**＝robocopy v2.6 ⇒ v2.7；rc=0；本版段恰好 1 次；标题/NOTICE/MANIFEST 版本号；**既有 v2.6 段原文逐字未变**；幂等）、B 组 4 条（`unique_anchor` 单元行为）、**C 组反证组**（把 `unique_anchor` 换成**恒不扩展**的旧行为 ⇒ rc≠0 ⇒ 判据有鉴别力）、D 组 1 条（真包隔离） | **16/16 PASS** |
| `results/app/_app234_probe_anchor.py` | 锚点机制**探针**（只读）：把「子串计数 vs 行锚定匹配」的差异逐项打印 | 已定位根因 |

### 复核过程中**自己踩的坑**（如实记录，均已改正）

1. 🔴 **判据写死常量 ⇒ 假 FAIL**：`verify_patch` 初版断言「旧正文**零改写**」，
   但 `choices=` 那行**必须**被改（加 `'identity'`）⇒ 假 FAIL
   ⇒ 改为**正向重建**（备份＋3 处已知编辑 ⇒ 逐行等于现文件）⇒ 同时证明
   「该改的都改了」＋「没多改一个字节」。
2. 🔴 **判据用错对象 ⇒ 假 FAIL**：缺陷③的 A8（既有段逐字未变）初版**拿上一版的
   改动说明正文**去跑 v2.7 ⇒ 正文里带上一版标题 ⇒ 段计数虚高、且不是真实成包路径
   ⇒ 改用**本版**正文（首行同名标题，正是缺陷②的形状）。
3. 🔴 **正则与工作参考实现不同口径**：`sync_pkg_identity` 的中文标题正则初版写成
   `实时字幕\s+[（(]`（要求「字幕」与「（」之间**有空格**）⇒ 真包首行**没有空格**
   ⇒ **永远匹配不上** ⇒ 改为与 `sync_c172._ZH_TITLE_RE` **同口径**（全角括号、无空格）。
4. 🔴 **dry-run 的断言对象错**：`--dry-run` 语义是「**不写盘**」⇒ 盘面仍是**旧**状态
   ⇒ 直接对盘面断言**必然**失败 ⇒ 改为：在**临时影子**上真跑一遍再断言
   （真包零改动，断言的是「若真跑会得到什么」）。
5. 🔴 **临时影子目录名必须带版本号**：下游 `sync_c172` / `app170` 的
   `detect_version()` 是**从包目录名**解析版本的 ⇒ 影子目录名不含 `_vX.Y`
   ⇒ 它们直接失败 ⇒ 改为 `.../Confucius4_LiveCaption_v<ver>`（与 `app170`
   的 `make_fake_pkg` 同款做法）。

---

## §3 交付面**只读**复核（真包 `Confucius4_LiveCaption_v2.6` 未被本轮改动）

- 包内 `app/` 36 个文件与开发树 `live_caption/` **逐文件 md5 全部一致**
  （`same 33 / diff 0`；另 3 个 = `MANIFEST.json` 等包内专有文件）。
- 真包 4 个身份文件 SHA256（跑前跑后**一致**）：
  `README_zh.md` `0bb23e7cfa39f24d…`／`README_en.md` `6d67d4d690b2fc0c…`／
  `NOTICE` `22d70a34316d4e49…`／`app\MANIFEST.json` `84a08d895da4aaa0…`。
- 🔴 **真包的两处已知缺陷仍在**（按 **APP-055 禁止原地改已签包**）：
  ① `README_zh.md` 的 `## v2.6 改动说明` 出现 **2 次**（第 1 次是空段）；
  ② `app/MANIFEST.json` 的 `version` 仍为 **2.5**（与目录名 v2.6 不一致）。
  ⇒ 本轮**未动真包**；缺陷③的修法保证**下一版**插入不再被这条**阻断**。
- `ACCEPTED.json` 复核：`version=2.6`／`accepted_at=2026-11-24 18:26:21`／
  `corrections=[APP-129,130,131,132,133,123]`／`ext=v0.4.21(b2a4978)`／
  `n_production_modules=33`／`code_fingerprint=1a3a849f…`（**未改**）。

---

## §4 🔴 如实登记：**未修** / **待裁定**项

1. 🔴 **真包 v2.6 的两处缺陷仍在**（README 双标题、MANIFEST.version=2.5）
   ⇒ 按 APP-055 **不原地改已签 ACCEPTED 的包** ⇒ **是否出 v2.7 待裁定**。
2. 🔴 **`results/app/app231_pack_lock_events.jsonl` 仍不存在且未入库**
   （§233 已登记；它是修好后的**生产路径**在**运行时**才产出的文件
   ⇒ v2.6 那次构建跑在修复提交**之前** ⇒ **不伪造空文件**）。
3. 🔴 **`Confucius4_LiveCaption_v2.6.staging` 残留 25 GB** ⇒ 删除属**破坏性**操作
   ⇒ **未删**，待授权。
4. 🔴 **`v2.5` 的 `ACCEPTED.json` 仍指向 v2.4**（**未重签**）；`v2.5` 无 zip。
5. 🔴 **仓库根 `.gitattributes` 根治**（854 个 `i/lf+w/crlf`）**跨模块** ⇒ 待裁定。
6. 🔴 **默认分离设备**、**`n_speakers=0` 口径** ⇒ 仍待 reviewer 裁定。
7. 🟡 **本轮新增的 `live_caption/release_notes/` 约定**：完整版线的「改动说明」
   正文历来放在 `live_caption/_appNNN_changelog_vX.Y_{zh,en}.md`（**私有命名**），
   而 `pack_v13` 的自动发现目录是 `live_caption/release_notes/vX.Y_{zh,en}.md`
   ⇒ 两者**不一致**。本轮新增的 `sync_pkg_identity` **两条都支持**
   （约定优先、历史命名兜底）⇒ **不强制迁移**（避免动他人文件），
   但**下一版建议**按约定放 `release_notes/vX.Y_{zh,en}.md`。

---

## §5 纪律自查

- 🟢 **未打包 zip**（用户级纪律「不通知 ⇒ 不打包」）⇒ **无新 zip**；
  旧目录 / 旧 zip **未覆盖、未删除**。
- 🟢 **未改任何客户包**（真包 4 个身份文件 SHA256 跑前跑后一致；`app/` 36 文件未动）。
- 🟢 **未跑推理 / 未测速** ⇒ **未取 `MACHINE_LOCK`**（本轮无计时类作业）。
- 🟢 **未调 MiniMax**（质量判定留给 reviewer）。
- 🟢 **未连 B 机**；**未进 MiniMVP 包**。
- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ SHA 零改动）。
- 🟢 只 `git add` **App 侧**文件；**未吞** ASR/MT/TTS 其它模块的未提交改动
  （全仓脏 962 是别的模块的）。
- 🟢 **未 force push**；仓库只保留 `main` 分支。
- 🟢 只写 `status/app/STATUS_APP.md`（**追加** `## §234`）＋ 本 companion；
  旧章节**未回头改**。

---

## §6 下一轮

- `last_ack` 仍 **APP-133**。
- ⏭ 等 reviewer 复核 **§234**（本轮 3 处缺陷 + 修法 + 复核）。
- 🔴 **待裁定**：**是否出 v2.7**（带本轮 3 处修法）／**是否删** `.staging`（25 GB）／
  **v2.5 重签 ACCEPTED**／仓库根 `.gitattributes` 根治／默认分离设备／
  `n_speakers=0` 口径。
- 🟢 **v2.7 若成包**：`python live_caption/_app129_build_v26.py --stage identity`
  （或 `--stage all`）⇒ 版本标识**自动**同步 + 闸门 + 硬断言 ⇒ **不再需要人工带外**。
