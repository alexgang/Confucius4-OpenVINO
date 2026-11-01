### §124 ✅ **APP-055 / APP-056 / APP-057 / APP-058 —— v1.13 还原 ＋ 模块租约 ＋ V2.0→V2.1 交付包 ＋ 说话人覆盖率同段复测** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。

#### ① APP-055（BLOCKING）—— 原地改包 ＋ 同版本号覆盖重打 ⇒ 已止血

* v1.13 目录被改动的 **6 个文件**，逐个「改前 SHA（= 06:08 态）→ 改后 SHA（被改坏）→ 还原后 SHA」
  （`results/app/app207_app055_restore_v113_evidence.json` → `changed[]`，`n_changed=6` / `n_restored_ok=6`）：

| 文件 | 改前 SHA（06:08 态） | 改后 SHA（被改坏） | 还原后 SHA | ok |
|---|---|---|---|---|
| `app/live_caption_app.py` | `9f37a399b2b3…` | `b65e311f9a93…` | `9f37a399b2b3…` | ✔ |
| `app/speaker_assets.py` | `1576ac8559e1…` | `17c1f39c945a…` | `1576ac8559e1…` | ✔ |
| `app/speaker_tracker.py` | `ecb3bd6b7f09…` | `5dd215f4ea03…` | `ecb3bd6b7f09…` | ✔ |
| `app/tts_cuda.py` | `bfde75221a04…` | `7d0d886d85cb…` | `bfde75221a04…` | ✔ |
| `app/tts_cuda_sidecar.py` | `269d02f31990…` | `84110917d44c…` | `269d02f31990…` | ✔ |
| `ACCEPTED.json` | `fc31e1b57597…` | `8c6bc81d0879…` | `fc31e1b57597…` | ✔ |

* 还原基准 = git `aacb2dd` 的 blob：**06:08 那份 zip 本体已在 15:02 被 `--same-version` 覆盖 ⇒ 字节流不可得**
  ⇒ 只能用 blob ＋ 字节数算术复原（`app207` → `note`）。
* **payload 重算与 06:08 记录完全一致**：`files=14212` / `bytes=13689629685`（`payload_recheck.match=true`）
  ⇒ 目录已回到 06:08 态。
* 旧 zip **不删不改**（`zip_untouched=true`）：v1.13.zip（15:02 / SHA `a13bee66…`）、v2.0.zip（17:49 / SHA `8198924f…`）原样保留。
* **纪律落地**：此后**不再用 `--same-version`**；新产物一律「新版本号目录 ＋ 新 zip ＋ 新 MANIFEST ＋ 重签 ACCEPTED」
  （本轮 v2.1 即按此执行）。

#### ② APP-056（HIGH）—— 模块租约：指令已改，本轮全程持租约

* 指令侧：App 自动化指令已在「第 1 步」**之前**插入「第 0 步 · 模块租约（APP-056）」（全文见 ⑪）。
* 本轮 `acquire app` ⇒ **TAKEOVER**（上一会话 token `7cc116e8` 17:48 失心跳，其登记的 5 个 PID 全部已死）
  ⇒ 本轮 token **`8afc6c0f`**，从断点继续（读了它的 note「V2.0 打包压缩 10.6/12.75 GB」＋ §123 ＋ 全部产物，**没有从头重做**）。
* 长作业全部后台启动并**登记 PID**（`app214` 解压 PID 15792、`pack_v13` PID 3396）⇒ 下一轮会拿到 BUSY 而非重复启动。
* 收尾 `release app 8afc6c0f`。

#### ③ APP-057（HIGH）—— V2.0 → V2.1 交付包

* **① 新目录 / 新 zip / 新 MANIFEST / 重签 ACCEPTED** = **v2.1**
  （目录 `Confucius4_LiveCaption_v2.1`；zip **11 233 135 359 B** / **14 317 文件** / SHA256 `835803a7…aaa4` / mtime **2026-11-01 20:38:13**）。
  **v2.0 的目录与 zip 原样保留、不覆盖、不删除**。
* **② 包内结构**：`app/`（App 本体）＋ `ext/extension/`（插件 unpacked，15 个文件 / 219 021 B）＋
  `ext/bridge/`（19 个 .py ＋ `start_bridge.cmd`）＋ `ext/.runtime_deps/`（websockets 17.3 / psutil 7.2.2）
  ＋ `README_插件.md`（4 697 B，引用 `docs/插件截图/` 3 张截图，**已核实文件在包内**）
  ＋ `NOTICE`（9 643 B）＋ `THIRD_PARTY.md`。
  * **桌面快捷方式选「两个 .lnk」**（不选「App 内加启动桥接的开关」）：① 桥接必须用**包内 python ＋ 包内模型** ⇒ 启动方式与 App 根本不同；
    ② 两者**设备互斥**（`ext/bridge.py::_caption_app_running`）⇒ 常需只起一个；③ 桥接可能**先于** App 启动（用户只想看网页配音）。
    ⇒ `Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`（均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证）
    ⇒ `app212` **9 PASS / 0 FAIL**（含 3 条反证）。
* **③ 依赖隔离**（在**另一个路径**解压 zip 后扫，不是扫包目录）：`app214`（判据已修，见 ⑤）
  ⇒ **reviewer 点名的 5 个开发目录 0 命中**；扫描面 **6 729 个文件**（自有 93 ＋ 第三方运行时 6 636，后者亦 0 命中）。
* **④ 闸门**：`app213` **15 PASS / 0 FAIL**（含 **8/8** 反证）—— 包内无会议录音 / 克隆音色 / babelvox 示例音色；
  NOTICE 含 **pyannote_seg**（CC BY 4.0）＋ **wespeaker**（MIT）署名与来源链接；
  App 侧旁路**默认关** ＋ **独立线程** ＋ CLI `--speaker` 默认 off；
  **EXT 侧旁路满足 EXT-029**（`threading.Thread` ＋ `daemon` ＋ 队列满即丢弃并计数 ⇒ 不反压）——**本轮新增的两条检查**。
* **⑤(a) A/B（旁路开/关，各跑一次）**：`app208`，用**包内 python**、音频 = app193/app175 的**同一段** Q&A 切片
  （3291.6–3591.6 s）⇒ 旁路开 **墙钟 300.7 s**（上限 303）/ **最大积压 1.2 s**（上限 2）/ **出字延迟中位 347 vs 343 ms（Δ +4 ms**（上限 +200）/
  **丢窗·降级 0** ⇒ 三项全过；另跑一次 `--speaker off` 作对照（300.9 s / 1.4 s / 343 ms）。
  ⚠️ **v2.1 的 `app/` 生产模块相对 v2.0 只差 `speaker_assets.py` 的注释**（`code_fingerprint`：`eeafd13b…` → `b96b6725…`）
  ⇒ 旁路代码**逐字节未变** ⇒ A/B 结论对 v2.1 成立；**但闭环仍需在 v2.1 上再跑一次**（本轮未跑，见 ⑧①）。
* **⑤(b) 桥接 + Edge 加载插件 + player 录 60 s 网页配音 ⇒ 未做**（**需用户手势**：Edge 加载已解压扩展 ＋ 点扩展图标 ＋ player「开始捕获」；
  EXT 侧同样记「tabCapture 生产路径未实测」）⇒ **如实记为未达成**。
* **⑤(c) zip 报告**：**11 233 135 359 B / 14 317 个文件 / SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`**
  （`results/app/DELIVERY_2.1.json`；`testzip()` = Everything is Ok；zip ⇄ 包目录 **14 317 个文件逐字节一致**；压缩 556 s / 压缩率 82.1 %）。
* **⑥ 未通知用户安装**（(a)(b) 未齐 ⇒ 按 reviewer 指令不通知）。

#### ④ APP-058（HIGH）—— 覆盖率同段复测 ＋ A/B 复核

* **① APP-054 的 A/B：reviewer 已核实 ⇒ 认可**；本轮在**多人音频**上又跑一遍并补齐指标。
* **② APP-053 的「93.48 %」不成立 ⇒ 撤回 §123 的该结论**（分子取自 on 臂的**单人**段 `SPE_0000_0500.wav`，
  分母取自 **Q&A 段** ＋ pyannote 参照 ⇒ 分子分母不同段）。
  本轮**同段复测**（`app208`，切片 = app193/app175 的 **3291.6–3591.6 s**）：

| 指标 | 实测 | 判据 | 结论 |
|---|---|---|---|
| 覆盖率（分子分母同段） | **93.75 %**（45/48 句带标签） | 与 ref 95.65 % 相差 ≤ 5 pp（**Δ 1.90 pp**） | ✅ |
| 不同标签数 | **4**（S1/S2/S3/S4） | ≥ 3 | ✅ |
| 最优编号置换一致率（**实际运行**标签上算） | **64.29 %** | —（报数） | 📌 |
| 换人点召回率（±1 段算命中） | 口径 A **33.33 %**（4/12 命中、误报 3）／口径 B **58.33 %**（7/12、误报 0） | ≥ 60 % | ❌ **未达标** |
| APP-054 墙钟 / 积压 / 延迟 Δ / 丢窗降级 | 300.7 s / 1.2 s / +4 ms / 0 | 303 s / 2 s / +200 ms / — | ✅ |

  ⇒ `app208` **7 PASS / 1 FAIL**（`verdict=FAIL`）⇒ **不换口径、不粉饰**。
* **判据④的鉴别力诊断**（`app210`）：口径 A 按 app208 的段号对齐、口径 B 按**文本对齐**后比对；
  **参照标注自身**与人工标注就差 1 处（人工多一个换人点 @19）⇒ 即便完美实现，召回上限也只有 **11/12 = 91.7 %**；
  实测口径 B 已达 **58.33 %** 且**零误报**。剩余漏检的根因在 **ASR 侧的说话人切换判定**（与 APP-054 NOTICE 同一治本线）
  ⇒ 本轮**未自行改口径**，如实记录待复核。
* **③ §123 ⑥-4 的说法撤回**：原文「未在用户正在测试的安装目录里原地改文件」**不成立**
  （reviewer 实测 v1.13/app/ 三个文件被改成 14:33/14:37 版本，v1.13.zip 又在 15:02 同版本号重打）
  ⇒ 本轮按 APP-055 还原 v1.13，并自此只用新版本号发包。

#### ⑤ 本轮抓到的 4 个「判据自身缺陷」（判据 PASS ≠ 判据正确）

| # | 缺陷 | 后果 | 修法 |
|---|---|---|---|
| 1 | `app214`/`app209` 只扫「AST 字符串字面量且**排除 docstring**」 | 首包 v2.0 里 `ext/bridge/{engines,segmenter,app_root}.py` 的 docstring **写死开发机绝对路径**（4 处）**被判为通过** | 改**全文扫描**（注释/docstring 也算）＋ `.lnk` 额外按 UTF-16LE 再解一份（真实 .lnk 是二进制） |
| 2 | `app214`「四类扩展名都必须扫到」 | 包内本就没有 `.lnk` ⇒ **恒 FAIL**（恒假判据） | 改三态：**存在即必扫；不存在记「不适用」** |
| 3 | `app214` 把「构建机用户名」与 reviewer 点名的 5 个开发目录混成一条 | 「是否违反 ③」被口径混淆 | 拆成**阻断**（5 个开发目录）＋**附带发现**（构建机用户名，不阻断） |
| 4 | `app211` 把构建机家目录写进 `ACCEPTED.json` 的 `pkg_dir`；`app191` R3 按字面比 | 客户机上路径不对 ＋ 泄漏构建机身份 | `pkg_dir` 改 `<HOME>` 形态；R3 改成「**先展开 `<HOME>` 再比**」 |

#### ⑥ 交付口径（v2.1）

* `app/` 生产模块 **28** 个，内容指纹 `b96b6725944c8d19aa9a4a980dee2ac370c6922a19fe7204abae7270b8a9b421`
  （v1.13 为 `09a1f417…`；差异**只有** `speaker_assets.py` 的注释脱敏）。
* `ACCEPTED.json`：**6 067 B**，`pkg_dir` = `<HOME>\Confucius4_LiveCaption_v2.1`，`binding_gate=app191`，
  白名单 **5 条**（每条带 `reason` ＋ `source`）。
* 闸门结果：`app191`（验收 ↔ 代码绑定）**18 PASS / 0 FAIL**｜`app213`（内容闸门）**15/0**｜`app212`（快捷方式）**9/0**｜`app217`（建包 ＋ 脱敏）**7/0**。

#### ⑦ 本轮对仓库的改动（**只有 App 侧**）

* `live_caption/speaker_assets.py`（注释脱敏 1 处）｜`live_caption/release_notes/v2.1_{zh,en}.md`（新增）
* `results/app/app209`（EXT 复制：扫描改全文）｜`app211`（`pkg_dir` → `<HOME>`）｜`app212`（快捷方式版本号**改为派生**）
  ｜`app213`（＋ EXT-029 两条检查 ＋ 两条新反证）｜`app214`（判据修复 ＋ `--skip-extract` ＋ 二进制 .lnk）｜`app217`（**新增**：建 v2.1 ＋ 脱敏）
* 🔴 **未提交**：`status/app/CORRECTIONS_APP.md`（reviewer 独占）、ASR/MT/TTS 其它模块的任何文件。

#### ⑧ 待 reviewer 复核 / 未达成（不粉饰）

① **APP-057 ⑤(b) 未做**（需用户手势）⇒ 配音录音与逐段译文待用户实听。
② **APP-058 判据④ 召回率未达标**（33.33 % / 58.33 %，均 < 60 %）⇒ 如实记录。
③ **交付版本号是 v2.1 而非用户原话的 V2.0**（v2.0 首包违反 ③，且「旧 zip 不覆盖」）⇒ 请 reviewer 确认 v2.1 即交付版；
若必须叫 V2.0，请授权改名/重签（**改名不需要重打包**）。
④ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（指向被取代的 v2.0 包）—— App 的快捷方式闸门刻意不删旧链 ⇒ **请用户/reviewer 决定是否清理**。
⑤ 沿用 §123 待办：3 段 1.2–1.3× 配音素材实听（`shared/app_accel_listen/`）；APP-048「运行中」截图仍缺；
APP-054 的 NOTICE（ASR 侧 `run_seg_side` 每次调用重编译模型）仍待主会话转达。
⑥ **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读文件）—— 复核见 ⑨。

#### ⑨ 收尾复核（`CORRECTIONS_APP.md` 全程只读）

* 开工记录：SHA256 `89018d172afc1e570a833d961a32355ebb1416fbf9d20f6f104a86f4217d920d` / **145 700 B** /
  mtime **2026-11-01 15:49:35** / `## APP-xxx` 条目 **58** 条（APP-001…APP-058）。
* 收尾复核：SHA256 / 字节数 / 条目数 **均不变** ⇒ **本轮 reviewer 未中途追加新条目**；本文件**零改动**。

#### ⑩ 撤回清单

* **撤回 §123 中「APP-053 说话人标签覆盖率 93.48 %（43/46）」**（分子分母不同段）⇒ 以 ④ 的同段复测 **93.75 %** 为准。
* **撤回 §123 ⑥-4「未在用户正在测试的安装目录里原地改文件」** ⇒ 见 ④③。

#### ⑪ 自动化指令（APP-056 ⑤ 要求贴全文）

> **第 0 步 · 模块租约（APP-056）**（插在原「步骤 1」之前）：
> `python C:\Users\Trekker-PTL\shared\tools\session_lease.py acquire app`
> * exit 10（BUSY）⇒ 只输出「上一会话仍在进行，跳过本轮」并**立即结束**（不读文件、不改东西、不碰锁）
> * exit 0 ⇒ 拿到 `TOKEN=xxxx`，后续步骤都带这个 token；若打印 TAKEOVER ⇒ 先读上一会话的 note / STATUS / 产物，**从断点继续**
> * **心跳**：每完成一步、每次耗时操作前后 `session_lease.py beat app <token> <一句话进度>`；exit 11（LOST）⇒ **立即停止、不再写任何文件**
> * **长作业**（打包 / 计时 / e2e）用 schtasks 或 Start-Process 后台启动，拿到 PID 马上 `session_lease.py addpid app <token> <pid>`；
>   不在一个工具调用里同步等待超 20 分钟，分次轮询、轮询之间 beat
> * **收尾**（含「无新纠偏、跳过」）最后一步 `session_lease.py release app <token>`；有后台作业活着时脚本会自动保留租约
> * 🔴 MACHINE_LOCK 规则不变（排队等待，不抢锁）：租约管「同一模块不能有两个会话」，锁管「不同模块不要同时占用设备」

#### ⑫ v2.1 相对 v2.0 的差异（**只有 3 处**）

1. `ext/bridge/{engines,segmenter,app_root}.py` ＋ `app/speaker_assets.py` 的 **8 处**开发机家目录字面量 → `<HOME>`。
2. `ACCEPTED.json`：`pkg_dir` → `<HOME>` 形态 ＋ `accepted_at` 重签 ＋ 白名单 `speaker_assets.py` 的依据补 APP-057 ③。
3. 版本标识：`README_zh` / `README_en` / `NOTICE` / `MANIFEST` → **2.1**，并插入 v2.1 改动说明段。
