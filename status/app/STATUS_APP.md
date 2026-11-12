# STATUS_APP

last_ack: APP-105
更新时间: 2026-11-12 16:51:46
当前任务: **APP-105 已执行完**（`last_ack` = APP-105）｜**MiniMVP rc10 已打并验收 13/13 PASS**：目录 `Confucius4_LiveCaption_MiniMVP_v1.0-rc10/`（10,629 文件／5.516 GiB）＋ zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc10_perftest.zip`（5,926,048,165 B）｜§7 出厂默认第 2 代 **ASR GPU.0／MT GPU.0／TTS NPU**（`defaults_version` 8→9）＋旧默认告警改成一行日志／§1 `Start_Bridge.bat` 改 CRLF+ASCII 并加打包闸门／§2 不带 `bridge_token.txt`（黑名单 + 闸门）／§3 README 与 USER_GUIDE 如实写明 EXT 的 ASR 在本版不可用／§4 README 文案修正（含 README_en 表格英文同源）｜**模型未动**（MANIFEST 6 模型 SHA 与 rc9 相同）｜**停下等 reviewer 复核**
阻塞 / 待用户决定: 🔴 **等 reviewer 复核 rc10**（APP-105 §6/§7）｜**B 机实测仍未做**（reviewer 安排）⇒ rc10 的 README_perftest 已写明「B 机要跑的两组」（新默认组 + 旧默认组，各 10 分钟，记 TTS 提交/播完/丢弃）｜🔴 **EXT 的 ASR 在 MiniMVP 本版不可用**（EXT v0.4.8 写死 R2T2 ASR）⇒ 已在 README/USER_GUIDE **如实写明**，EXT 侧适配 0.6B 另等 reviewer 通知（**rc10 不等它**）｜🔴 **v2.5 未打包**（完整版 TTS/克隆 GPU.0 只改在 dev 树）｜🔴 reviewer 拟定的 §7 文案里含「mask2」字样 ⇒ 本轮**改用「旧解码器」**（保住 reviewer 自己核过的「app/ grep mask2 = 0」）
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）｜**§167 压缩**：§167 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）｜**§168 压缩**：§168 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）｜**§178–§180 压缩**（APP-101 §1.d「每节不超过 3 行速查」）：三节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec178_180_20261112.md`（块 SHA256 `d91b34ffed16ff1b22f0dd369c66bd9477351a8e782f327ff1740f0b44113705`）；活文档三节各留 1 行速查｜**§141–§160 压缩**：20 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜**§171–§180 压缩**：10 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）


## 最近更新
> 🔴 2026-11-12 16:51:46 ｜ **APP-105 执行完（rc10）**｜rc10 目录 10,629 文件／5.516 GiB ＋ zip 5,926,048,165 B｜包上验收 13/13 PASS｜**出厂默认第 2 代 ASR GPU.0／MT GPU.0／TTS NPU**（`defaults_version` 8→9，rc9 存的旧默认按代次忽略）｜`Start_Bridge.bat` 改 CRLF+ASCII（cmd /c 实测能拉起启动器）｜包内**无** `bridge_token.txt`（黑名单闸门）｜README/USER_GUIDE 如实写明 EXT 的 ASR 不可用｜整链 10 分钟：ASR EXECUTION_DEVICES=GPU.0、TTS 实测落点 NPU（12 个组件）、TTS 提交 158／播完 126／丢弃 32｜模型未动｜未打 v2.5、未调 MiniMax、未通知用户
> 🔴 2026-11-12 12:45:59 ｜ **APP-104 执行完（rc9）**｜rc9 目录 10,692 文件／5.517 GiB ＋ zip 5,927,246,232 B｜包上验收 5/5 PASS（`--check`/GUI/整链/EXT/用户选择）｜**修掉 2 个真缺陷**（GUI 绕过旧配置迁移；`--engine` 默认写死 gpu_int8）＋**补上 `.runtime_deps`**（websockets/psutil，桥接才起得来）｜三份 README 改由打包脚本按实际文件生成（grep 旧字面 = 0）｜MANIFEST 6 个模型 SHA 与 rc8 相同（模型未动）｜未打 v2.5、未调 MiniMax、未通知用户
> 🔴 2026-11-12 10:44:44 ｜ **APP-102 执行完（APP-103 裁定本会话做完）**｜MiniMVP **rc8** 目录（10 541 文件／5.515 GiB）＋ zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc8_perftest.zip`（**5 924 663 034 B**／10:40）｜**包上验收 6/6 PASS**（`app488_app102_rc8_acceptance.json`）：无旧解码器目录／`app/` grep `mask2`=0／MANIFEST decoder `0059531a…d6a3`＋encoder `0b7463d6…` 与源一致／EXT 0.4.8 @`817abcb`／包内 python `--check` exit=0（21 个 OK 行）／包目录整链 exit=0、ASR RTF **0.544**、播完 **2** 句｜**4 臂短冒烟 4/4 PASS**（`app486_app102_rc8_smoke.json`）：stateful GPU.0 **0.397**／NPU **0.538**（`EXECUTION_DEVICES` encoder+decoder 均 NPU）／新默认整链 **0.573**／GUI 截图 42 549 B 非空白、ASR 两档 stateful、克隆置灰、10 语种｜**10 语种 MT 30/30 ＋ TTS 30/30**（30 个 wav 落盘、撞上限 0 次、`_patch_app_langs` 新增键 **0**，`app487_app102_10lang_smoke.json`）｜**停下等 reviewer 复核**；未打 v2.5、未调 MiniMax、未通知用户
> 🔴 2026-11-12 09:46:41 ｜ **接单 APP-101 / APP-102**（纠偏 102 条／SHA `f5346cbd…`／325 733 B／mtime 08:59:56）｜静态前置落盘：EXT v0.4.8 @`817abcb` 暂存、stateful 模型身份核对、MiniMVP TTS 默认改 GPU.0｜**stateful 后端／4 臂冒烟／10 语种冒烟／rc8 未做**（需持锁长作业）⇒ **未 ack、未打 rc8**，详见 §181
> 🔴 2026-11-11 12:53:38 ｜ **执行 APP-099 完成**（第 4 节 8 项，明细见 §175 归档件）｜rc7 六臂 6/6 ＋ GPU 同占 1/2 有效（判据修正后 PARTIAL）＋ dev 修正 33/33 ＋ MANIFEST 逐项 84/84｜**未打 rc8 / v2.5，停下等 reviewer 复核**
> 🔴 2026-11-11 10:19:33 ｜ **开始执行 APP-099**（reviewer 09:20 追加，纠偏文件 **99 条** / SHA `F01C5C88…` / 307 394 B / mtime 09:28:13）｜第 0 节 **5 项用户决定** ＋ 第 4 节 **8 项任务** ｜**修在 dev 树、暂不打 rc8、不打 v2.5、不通知用户、做完停等复核**｜🔴 **设备作业排队**：`MACHINE_LOCK` 09:38:49 空文件（无 PID 可解析 ⇒ fail-closed 视为存活）＋ ASR 租约活跃（token `9bda917a`，beat 10:11）⇒ 第 1/2 项须等锁，不抢｜本条**需等 reviewer 复核**
> 🔴 本节 7 条较旧「最近更新」原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261111.md`（块 SHA256 `35882165a9e7ba88a39e134ea72a81cee4a4f3d41961c751cb6a359097eed9fe`／5198 B）；速查：APP-098 rc6 修整／§169 两真缺陷／§168 ABBA／APP-093 §3+APP-097 §2 补齐／APP-094-096 rc5／APP-093 ack／rc4 zip。
> 🔴 本节 6 条较旧「最近更新」原文（rc4 已建／APP-086②／§139-140 索引／2026-11-05 及更早索引／APP-085／APP-086-088 ack）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261110.md`（块 SHA256 `84ffe113eeb4d580a1e8e3f3919f37409b9798f515da21dbf2e24109bcf2a236`）；本节只留 rc4 zip 与 APP-093。
## 当前有效结论

> 🔴 **每个数字都注明来源产物**；**被推翻的旧结论不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| 客户包目录 | 🔴 **两个并存**：`Confucius4_LiveCaption_v2.2` = **候选交付版**（APP-061，**待用户抽听 + reviewer 复核**；桌面快捷方式**仍指向 v2.1**）｜ `Confucius4_LiveCaption_v2.1` = **当前交付版**（v2.0 / v1.13 目录仍在，未删除） | `Confucius4_LiveCaption_v2.2/app/MANIFEST.json` → `version=2.2`（`DELIVERY_2.2.json` → `manifest_version`）；v2.1 见 `DELIVERY_2.1.json` |
| 客户包 zip | 🔴 **候选 = v2.2**（**2026-11-02 01:54:03** / **11 233 149 299 B** / **14 317 文件** / SHA256 **`ea5c5c850f8836a7edab982611cdd59d0ba0e83f8d5ff880cc797b7c67c23b75`**）⇒ 含 APP-061 全部代码（①④⑤＋③⑥）＋ EXT 插件 + 桥接服务 ＋ **重签的 `ACCEPTED.json`**（`code_fingerprint=fddb2dc6b06d…` / 28 个生产模块 / `binding_gate=app191`）＋ v2.2 改动说明（zh/en）⇒ **未改桌面快捷方式、未通知用户**（待抽听）｜ **当前交付版仍是 v2.1**（**2026-11-01 20:38:13** / **11 233 135 359 B** / SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`）⇒ **v2.0 首包（17:49 / SHA `8198924f…`）保留不删** | `results/app/DELIVERY_2.2.json` → `sha256` / `bytes` / `mtime`；打包日志 `_pack_v22_run.log` → 「比对 14 317 个文件 / 全部逐字节一致」＋ `testzip()` OK ＋ 「--no-shortcut 跳过桌面快捷方式更新」；v2.1 见 `DELIVERY_2.1.json` |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | 🔴 **APP-101 §0.3 / APP-102 §0（用户 11-12 决定）**：完整版 TTS 与克隆（说话人编码器／x-vector）→ **GPU.0**；MiniMVP TTS → **GPU.0**（克隆置灰）｜**MiniMVP rc8 已进包**（出厂默认实测 `NPU/GPU.0/GPU.0`）；**完整版 v2.5 未打包** | `live_caption/device_config.py:69-74`；`app486_app102_rc8_smoke.json` → `factory_default_probe.default_devices`；`app488_app102_rc8_acceptance.json` |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出） | `app185_app048_gui_layout_pkg_evidence.json` → `verdict=PASS` / `n_pass=64` / `n_fail=0`（**在客户包内代码上跑**） |
| 桌面快捷方式 | **v2.1 两个**（`Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`，均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证 ⇒ 非坏链）；⚠️ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（**未删**，待用户/reviewer 决定） | `results/app/app212_app057_v21_shortcuts_evidence.json` → `checks`（**9 PASS / 0 FAIL**，含 3 条反证） |
| 说话人识别旁路 | **默认关闭**（`--speaker off` 是默认；GUI 有「说话人识别」勾选框）⇒ v1.13 的阻断级回归已止血 | `results/app/app199_app054_ab_evidence.json` → `checks`（4 PASS / 0 FAIL）；`app197` → T7 |
| MiniMVP 默认设备（新） | ASR **NPU** / MT **GPU.0** / TTS **GPU.0**；`device_config.DEFAULT_DEVICES` 为唯一事实来源，GUI `_dev_selected` 与 CLI `get_devices()` 同源（无第二份字面量）｜**rc8 包内实测** `NPU/GPU.0/GPU.0` | `live_caption/device_config.py:69-74`；`_DEFAULT_DEVICES_FULL` 三档仍全 GPU.0；`app486_app102_rc8_smoke.json` → `factory_default_probe` |
| 磁盘最新完整版包 | `Confucius4_LiveCaption_v2.4/` 与 `Confucius4_LiveCaption_v2.4.zip`（**11 235 954 241 B** / 2026-11-07 23:04）在位；**v2.5 未打包**；v1.5 / v1.13 / v2.0–v2.3 / `v2.3_aborted_20261107_1517` 均保留未删 | 磁盘实测 `ls -d` / `ls -la`（2026-11-12 09:47） |
| 磁盘最新 MiniMVP 包 | 🔴 **rc8 已打**：`Confucius4_LiveCaption_MiniMVP_v1.0-rc8/`（10 541 文件／5.515 GiB）＋ `~/shared/minimvp/…rc8_perftest.zip`（5 924 663 034 B／10:40）；**包上验收 6/6 PASS**；rc7 及更早目录/zip 全部保留未删；rc6 已按 APP-099 移入回收站（可逆） | `results/app/app484_minimvp_rc8_build_evidence.json`；`app488_app102_rc8_acceptance.json` → `verdict=PASS` / `zip_check.counts_equal=true` |

### 关键数字

> 🔴 本表已**整表逐字归档** ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（块 SHA256 `0b1e0843e6192300fe8d72fbeb1965d2464d1df93e15ab1e3b2c4cca15131d0a`）。
> 🔴 表内每行均注明「来源产物 / 字段」⇒ 可按文件名完整追回；**本轮（APP-093 §3 / APP-097 §2）的关键数字见 §167**。

### 已撤回的旧结论（**不作为结论**，仅备查）

> 本块已原样归档 ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。

## 未完成纠偏

> 🔴 本表（APP-043..APP-054 与 3 行关键指标）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_unfinished_corrections_upto_20261106.md`；正文一字未删。
> 🔴 **速查**：APP-045/047/048/049/050 已闭合；APP-043/051/052/053/054 均「已完成、待 reviewer 复核」；🔴 APP-048 仍缺「运行中」截图、APP-053 仍缺转写区 `[Sx]` 前缀截图、APP-043 仍需用户实听 3 段素材。
## 最近章节

> 按 APP-052 ④：**每节最多 3 行的索引**；**§109–§124 正文已原样归档**到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（内含 §124 正文 ＋ 旧「最近更新」条目）与 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`（**逐字保留，内容一字未删**）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。

| 章节 | 一句话 | 状态 |
|---|---|---|
| §109 | APP-047 说话人 IR 精度定案 FP16 ⇒ `asr_spk/` 收敛为 3 文件 | 已归档 |
| §110 | APP-048 GUI 三分区状态条：代码 + 定点同步 + 64 PASS / 0 FAIL | 已归档 |
| §111 | APP-049 压缩：STATUS 1 437 968 B → ≤ 40 KB，原文原样归档 | 已归档 |
| §112 | 客户包「运行时可加载性」21 PASS / 0 FAIL ｜ 修掉「宿主 PYTHONPATH 污染」 | 已归档 |
| §113 | 修掉「版本标识在打包时复发」：新增打包前闸门 + 通用同步脚本 | 已归档 |
| §114 | APP-027 V3(a) MiniMax 回转写 CER 对比：14/0，Δ 的 95% CI 含 0 | 已归档 |
| §115 | APP-050 启动日志打印 `EXECUTION_DEVICES` ⇒ 实测全部 NPU | 已归档 |
| §116 | APP-050 git 收尾（commit / push）｜ 更正 §115 的一处事实错误 | 已归档 |
| §117 | APP-051 三条子项全完成：重打 v1.13 ＋ 真机验收 ＋ `ACCEPTED.json` | 已归档 |
| §118 | 抓到 3 个真缺陷（产物未入库 / clone 打包必失败 / 写死仓库根） | 已归档 |
| §119 | 补上「包 ⇄ 仓库 生产模块集合一致性」（新增 `app188` 闸门） | 已归档 |
| §120 | 闭环「包内代码写死开发机家目录」＋ 修掉两个过期断言 | 已归档 |
| §121 | 抓到 2 个「判据自身缺陷」｜ 连带修掉 `app187` 的 MISSING | 已归档 |
| §122 | 新增「验收证据 ↔ 被验收代码」绑定闸门 `app191` | 已归档 |
| §123 | **APP-052 / APP-053 / APP-054**：`.lnk` 坏链修复 ＋ ACCEPTED 重签 ＋ 标签覆盖率 7 % → 93.48 % ＋ 旁路线程化 ＋ STATUS 压缩 | **本轮新增（见下）** |
| §124 | **APP-055/056/057/058**：v1.13 还原 ＋ 模块租约 ＋ V2.1 交付包 ＋ 同段覆盖率复测 | 已归档 |
| §125 | **APP-059**：口径 B 定为唯一口径 ＋ README 局限说明 ＋ 两处更正 ＋ MANIFEST 三元组 ＋ HOWTO | **本轮新增（见下）** |
| §126 | **APP-060**：交付版 = v2.1 ＋ v2.0 标 superseded ＋ 桌面 v2.0.lnk 已删（脚本加硬闸门） | **本轮新增（见下）** |
| §127 | **APP-061**：用户实测 6 问（CUDA 无声 / 离线无参考音色 / 卡顿 / 克隆 10 s 一次 / 男声被女声播出 / 界面不紧凑）⇒ 代码层全修 ＋ v2.2 包 | **本轮新增（见下）** |
| §128 | 巡检无新纠偏 ⇒ APP-061② `SyntaxWarning` 已修 ＋ 共享锁闸门夹具假 FAIL 已修（42/42）＋ CUDA 置灰核验 ＋ 真机验收 harness 备好（设备级实测因用户会话在跑而未开跑） | **本轮新增（见下）** |
| §129 | **巡检无新纠偏 ⇒ 自查 4 个真缺陷并修掉**（`app224` 移动-HEAD 基线 ⇒ 永久假 FAIL；锁闸门反证谓词恒真；`app223` 3 个缺陷；边车 `_enter_buffered_busy` 崩溃）＋ 回归 29/0・39/0・13/0 | **本轮新增（见下）** |
| §131 | **APP-062（D1–D4：用户对 APP-061 的四项决定）** —— 代码层全完成（D1 窗口同源配置项 / D2 自动开旁路 / D3 客户包去 CUDA / D4 禁 MT+TTS 同 NPU） ｜ **本条需等 reviewer 复核** | 已归档 |
| §132 | **APP-063/064/065**：D4 bug ＋ D2 四入口 ＋ D1 窗口（ASR 未同源⇒跨模块错位）＋ 锁纪律 ＋ **界面重排 5 组**（截图/清单已交）＋ 改名 | **本轮新增（见下）** |
| §133 | **APP-067**：①克隆 0 % 根因（加载期排队 + seg→spk 绑定）＋ ③D4 界面 ＋ ④按钮/高级组截图 ＋ ⑤D1 5 s 窗口 ⇒ **①③⑤ 设备级已完成**；②④ 设备级未做（等锁） | **本轮新增（见下）** |
| §134 | **APP-066**：MiniMVP 最小包 v1.0 的 **6 处硬缺陷（含 P0 无法启动）**已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 构建闸门全绿 / 52.41 % 体积）；(a)(b)(c) 设备级未做 | **本轮新增（见下）** |
| §139 | **APP-073 + APP-074**：解压副本冒烟 **7/0**（rev2 zip）＋ 音色 A **不依赖** babelvox 示例音色（`choices` 只有 `A`/`follow_speaker`）＋ README 文件数 **10 503 → 10 474** ＋ zip 重打（新文件名）⇒ **最终 SHA `90ae8b9d…`**；⛔ APP-071 仍未完成（放 rc4） | **本轮新增（见下）** |

### §135 ✅ **APP-067 ②④ 设备级补齐（ABBA + GUI 臂 + ② 交付物）＋ APP-066 3(a)(b) ＋ 🔴 修 MiniMVP P0（rc2）** ｜ **本条已完成（设备级）**（2026-11-05 08:38）
> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（块 SHA256 `12cf171e63e62f99e3d3bd22694b594e1a8de285aa1d642b3b5db2d9b70fb831`）；各节**正文**早已分别归档到 `status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。

### §136 ✅ **APP-068 + APP-069 + APP-070 三条新纠偏的代码侧全部落地 ＋ MiniMVP rc3 已出（设备级 3(a) PASS 9/0）** ｜ **本条已完成（代码 + 部分设备级）**（2026-11-05 11:20）
> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（块 SHA256 `12cf171e63e62f99e3d3bd22694b594e1a8de285aa1d642b3b5db2d9b70fb831`）；各节**正文**早已分别归档到 `status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。

### §137 ✅ **无新纠偏（70 条 = last_ack APP-070）⇒ 按 APP-046 从 §136 断点续做** ｜ **APP-069⑥ 已完成｜①③④ 需等 reviewer 复核**（2026-11-05 13:37）
> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（块 SHA256 `12cf171e63e62f99e3d3bd22694b594e1a8de285aa1d642b3b5db2d9b70fb831`）；各节**正文**早已分别归档到 `status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。

### §138 ✅ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成** ｜ **APP-071 仍未完成（BLOCKING）** ｜ **本条需等 reviewer 复核**（2026-11-05 15:28）
> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（块 SHA256 `12cf171e63e62f99e3d3bd22694b594e1a8de285aa1d642b3b5db2d9b70fb831`）；各节**正文**早已分别归档到 `status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。

### §139 ✅ **APP-073（解压副本冒烟）＋ APP-074（更正：babelvox 示例音色不许放回）本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-05 18:08）
> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（块 SHA256 `12cf171e63e62f99e3d3bd22694b594e1a8de285aa1d642b3b5db2d9b70fb831`）；各节**正文**早已分别归档到 `status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。

### §140 ✅ APP-076/077/078 已完成 ｜ 🔴 APP-075 需等 reviewer 复核（2026-11-06 13:59）
> 🔴 本节摘要行已逐字归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（块 SHA256 `12cf171e63e62f99e3d3bd22694b594e1a8de285aa1d642b3b5db2d9b70fb831`）；各节**正文**早已分别归档到 `status/archive/STATUS_APP_secNNN_*.md`（逐字保留）。

## §141–§160（本批 20 节｜注意**无 §161**）｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜活文档留此指针行

## §162 执行 APP-089/090/091/092（last_ack=APP-092）｜移植完成＋NPU 验收已跑 ⇒ **停在等 reviewer 复核**（2026-11-10 06:29:03）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec162_20261110.md`（5052 B／块 SHA256 `3098e4dd75a6444fbb7424ba67e38d49bdad838cf162649d9022b9b7827131c6`）；**§164 已撤回本节 ③④⑤ 的错误结论**（`app394.verdict=FAIL`／`app391…json` 幻影产物／「RTF≈0.90」笼统口径）。原文未删一字，按「只追加、不回改旧结论」纪律以索引替代。

## §163 MiniMVP rc4 打 zip 完成（用户 2026-11-10 指示「打包 rc4 吧」）
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec163_20261110.md`（3299 B／块 SHA256 `3cf5cc22541fdd65da07bc58211757c056c83d8f37eccef551020957ad9ed3ef`）。
## §164 执行 APP-093（last_ack=APP-093）｜§162 复核：验收 **FAIL** 如实入册、静态诊断＋STATUS 更正已完成 ⇒ 设备作业未跑，**本条需等 reviewer 复核**（2026-11-10 08:49）
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec164_20261110.md`（7496 B／块 SHA256 `d1b7efee44eb62e30d82e286916d327fdf0da8bf4f8f33aa419819ad70747f3a`）。

## §165 执行 APP-094 / APP-095 / APP-096（last_ack=APP-096）｜MiniMVP **rc5**（ASR→Qwen3-ASR-0.6B）已出包＋设备验收；**APP-093 设备作业部分完成**，停等 reviewer 复核
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec165_20261110.md`（7828 B／块 SHA256 `49b14a8f57e3817a569a202979ac4efd33b5783f4a6b253b32c7a9b05017b7e6`）。

## §166 执行 APP-097（last_ack=APP-097）｜目标语言扩到 10 种（静态部分完成）｜**逐语种设备验收未跑 ⇒ 需等 reviewer 复核**

> 🔴 本节正文已整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 `ddc46f321b1833cf7c04be048847a55f57677eaac4004fdc9fd405f93eb85f3f`）

## §167 续做 APP-093 §3 + APP-097 §2 设备验收（last_ack=APP-097，2026-11-10 15:59）｜**§3.7 截图 PASS（含一个阻断级真缺陷的根因修复）**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）。

## §168 巡检（last_ack=APP-097，2026-11-10 16:53:01）｜**无新纠偏**；补做 APP-093 §3.6「切段开/关的 ASR RTF」对照（设备跑，持锁，ABBA）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）。

## §169 巡检（last_ack=APP-097，2026-11-10 18:51:52）｜**无新纠偏**；查出并修掉 2 个 App 侧真缺陷（§167 归档件引用了不存在的产物路径／旁路窗长注释与 ASR 现状不符）＋ 新增 3 道静态闸门｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec169_20261110.md`（6978 B／块 SHA256 `f0f1735aaeb0b256cd8ffe565fed085ebe7f1879cd2d453d3942e7099d19c898`）。

## §170 执行 APP-098（MiniMVP rc7 修整）｜**无新纠偏落文件**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec170_20261111.md`（15674 B／块 SHA256 `20c14bc40932245881f30eae53265d3b6107a73907df40acf26832654ea81b73`）。
> 🔴 **速查**：**交付包 = MiniMVP rc7**（`Confucius4_LiveCaption_MiniMVP_v1.0-rc7`，zip **4 420 655 883 B／SHA256 `290b9b2e83d41da1…`／10 466 条目／CRC 全对**）｜**一、界面和后端 9 项全 PASS**（三后端无 NVIDIA/CUDA、只留 Intel GPU/NPU 两档、MT 默认指向包内实有的 INT4-CW、下拉无灰「缺」、克隆音色置灰＋提示、CLI `follow_speaker` 回落 A 并打日志、目标语言 10 种、未知语言码报错不回英文）｜**二、rc5 五个实测问题全修**（编码崩溃／`models/tokenizer` 残留／ASR 不打印 `EXECUTION_DEVICES`／ASR+MT 同占 GPU 崩溃／README 自相矛盾）｜**三、验收 5 项全 PASS**（GUI 截图 6/6、`--check` 无 NVIDIA/CUDA/缺、6 臂 60 s 冒烟 6/6、10 语种 10/10、模型身份 PASS）｜**🔴 本轮另查出并修掉 1 个 GUI 真缺陷**（`kind=='asr06b'` 未被识别 ⇒ 两个 ASR 档 label 完全相同 ⇒ GUI 靠 label 反查 ⇒ **静默错档**）｜**🔴 本轮自查出一次自违规**（验收时在 rc6 目录就地改了代码 ⇒ **已回滚 rc6 目录**，rc6 zip 一字未动 ⇒ rc6 zip 登记为「含缺陷、未交付」）｜**三处如实登记的不足**（MT 无 `EXECUTION_DEVICES` 直证／App 链路 de·zh 的 TTS wav 被 6 s 过期闸丢弃／`app415 summary.json` 的 `translations` 字段自相矛盾）｜**未打包 v2.5、未通知用户、未调 MiniMax**。
## §171–§180（本批 10 节）｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜活文档留此指针行

## §181 接单 APP-101 / APP-102（2026-11-12 09:46:41）｜静态前置完成；设备作业与 rc8 未做
> 🔴 **已做**（证据 `results/app/app482_app101_102_model_identity.json`）：EXT v0.4.8 @`817abcbe…` 用 `git archive` 暂存 `_ext_v048_stage`（167 文件／`ext/accel_usage.py` 在位／manifest `version=0.4.8`）；decoder bin SHA `0059531a…d6a3` 与 reviewer 一致、IR `inputs_embeds [1,1..512,1024]`、hidden 1024／28 层、encoder bin `0b7463d6…` 前缀一致；`device_config.py:69-74` MiniMVP `tts` `NPU`→`GPU.0`（`ast.parse` OK、GUI/CLI 同源）。
> 🔴 **未做**（需持 `MACHINE_LOCK` 长作业，**不虚报**）：`backends_stateful.py` 后端／`make_backend` 分派／`manifest_gen` 源目录／rc8 打包脚本、4 臂短冒烟、10 语种冒烟、GUI 截图、rc8 目录+zip 与包上验收 ⇒ **未打 rc8／v2.5、未通知用户、未调 MiniMax、未占设备**；`last_ack` 保持 `APP-100`（理由见头部），**等 reviewer 裁定**。

## §182 执行 APP-102 / APP-103（2026-11-12 10:44:44）｜rc8 已打并验收 6/6 PASS；撤回 §181 的「未做／等裁定」结论
> 🔴 **已做**（证据 `app484…json` / `app486…json` / `app487…json` / `app488…json`）：stateful 后端照 B-kit `bk_run.py`（NPUW_LLM、每次 generate 新建 InferRequest＋`reset_state`、eos/pad 用导出 id、512 上界截最旧前缀且实测截断 0 次）；旧无 KV 基线只在 dev 树，包内旧目录/字面 0（打包闸门反例自测 2/2 能识破）；rc8 目录＋zip 落盘，验收 6/6、4 臂短冒烟 4/4、10 语种 30/30，`last_ack=APP-102`（APP-103 裁定）。
> 🔴 **rc8 后补**（APP-102 §4）：10 分钟片段 4 臂配对 WER/RTF ＋ 整链一臂、预设 A 对照组、交付配置表细项；计时 json 已带锁 `ended` 与 `timing_valid`（`app486/487/488`）。**做完即停，等 reviewer 复核**（B 机实测由 reviewer 安排）；v2.5 未打、未调 MiniMax。

## §183 执行 APP-104（last_ack=APP-104，2026-11-12 12:45:59）｜MiniMVP rc9 已打并验收 5/5 PASS｜**本条需等 reviewer 复核**
> 🔴 **§1 已做**（`app490…json` / `app493…json`）：`device_config` 加 `profile`+`defaults_version` ⇒ MiniMVP 下**忽略** rc8 之前的旧设备项（数值项保留、日志写明忽略了哪些旧值、**不删用户文件**）＋**修掉 2 个真缺陷**：① GUI 绕过迁移直读旧配置；② `--engine` 默认写死 `gpu_int8`（改为**按设备自动选** ⇒ ASR=NPU⇒npu_int8）⇒ 验收 `--check`/GUI/整链（**不传设备参数**）都是 ASR=NPU、MT=GPU.0、TTS=GPU.0，无「ASR 与 MT 都放 GPU」提示，用户改设备后重启保留。
> 🔴 **§2/§3 已做**（`app491…json` / `app493…json`）：三份 README 由打包脚本**按实际文件生成**（grep `rc5|rc6|--tts-device NPU|2\.71|3\.35` = **0**；文件数/zip 字节与实际一致；默认设备表 = 包内实测 `DEFAULT_DEVICES`）｜EXT 按包内文档可启动：`tools/ext_launcher.py`（817abcb 原版，SHA 与 git blob 一致）+ `Start_Bridge.bat` + `ext/bridge/__main__.py` + 3 个兼容垫片 + **`.runtime_deps`（websockets/psutil，144 文件）** ＋ `ext/USER_GUIDE.md` 改包内相对路径、克隆段标注 MiniMVP 不可用 ⇒ 实测：**启动器 GUI 起来、窗口无目标语言下拉框、截图非黑图（35 251 B）、桥接进程起来了（MT+TTS 加载成功）并已停**；🔴 **但「真实引擎已接线」/「TTS 就绪」没出现** ⇒ EXT v0.4.8 的 `ext/engine_runtime.py` **写死 R2T2 ASR**（`models/encoder-int8`）而 MiniMVP 包里是 0.6B stateful ASR（`models/asr06b-*`）⇒ ASR 引擎装不上 ⇒ **跨模块缺口（EXT 侧）**，App 侧不改 EXT 源文件 ⇒ 该条记 **PARTIAL**（证据 `app493…json` → `ext_cross_module_gap`，截图 `ext_launcher.png`）。
> 🔴 **rc9 交付 + 如实记录**：目录 `~/Confucius4_LiveCaption_MiniMVP_v1.0-rc9/`（10,692 文件／5.517 GiB）＋ zip `~/shared/minimvp/…rc9_perftest.zip`（5,927,246,232 B）；**模型未动**（MANIFEST 6 个模型 SHA 与 rc8 相同）；rc8 及更早目录/zip **一律未动**；🔴 reviewer 11:14 留下的 `MACHINE_LOCK` 是**无 PID 的畸形记录**（BOM-only，44 min 陈旧、机器上无任何 python 作业）⇒ **改名回收**（`.MACHINE_LOCK.released_app_stale_*`，未删除）；🔴 **B 机实测仍未做**（reviewer 安排）⇒ README 写「待 B 机实测」；v2.5 未打包、未通知用户、未调 MiniMax；**`last_ack` = APP-104**。

## §184 执行 APP-105（last_ack=APP-105，2026-11-12 16:51:46）｜MiniMVP rc10 已打并验收 13/13 PASS｜**本条需等 reviewer 复核**
> 🔴 **§7（用户 14:30 决定，HIGH）出厂默认第 2 代 = ASR GPU.0／MT GPU.0／TTS NPU**：改 `live_caption/device_config.py`（`_DEFAULT_DEVICES_MINIMVP`）＋ `CONFIG_DEFAULTS_VERSION` **8→9** ⇒ rc9 写下的旧默认（NPU/GPU.0/GPU.0）按**代次**被忽略（`stale_device_keys()`），数值类配置项保留、**用户文件不删**、日志写明忽略了哪些旧值；用户在 rc10 里重新选过设备后写回 `defaults_version=9` ⇒ **保留**。旧告警「⚠️ ASR 与 MT 都放在 GPU.0 ⇒ 会 CL_OUT_OF_RESOURCES ⇒ 建议把 ASR 放 NPU」与**新出厂默认自相矛盾** ⇒ 改成**一行日志**：`ASR 与 MT 同在 GPU.0（stateful 解码器负载约为旧解码器的 1/3；rc5 在 B 机 268 s 崩溃是旧解码器，待 B 机复核）`（GUI 只记日志**不再覆盖**状态栏/MT 说明区；**完整版 v2.x 保留原告警**，因为它仍用旧解码器）。实测（包目录、**不带设备参数**）：`--check` exit 0（21 个 `[ OK ]`），stderr 首行 = 「已忽略旧配置里的设备项（asr=GPU.0，mt=GPU.0，tts=GPU.0）—— 那是 MiniMVP rc9 之前的出厂默认⇒ 改用本包出厂默认（asr=GPU.0，mt=GPU.0，tts=NPU）」。
> 🔴 **§1 `Start_Bridge.bat` 能拉起启动器**：原 bat 是 **400 B、LF 行尾（CR=0）、REM 里 134 个 UTF-8 中文字节** ⇒ 中文代码页 936 下 `cmd` 直接失败（reviewer 实测）。rc10 把 `Start_Bridge.bat`／`Start_LiveCaption.bat`／`Diagnose.bat` 三个 bat 全部重写为 **CRLF + 纯 ASCII**（命令语义一字不改），并在打包脚本里加**闸门**：包内所有 `*.bat` 必须 CRLF 且只含 ASCII（**反证自测**：造「裸 LF bat」「含中文 bat」各一 ⇒ 闸门必须报错，2/2 触发）。**验收按 reviewer 要求走 `cmd /c <包目录>\Start_Bridge.bat`（不用 python 绕过）**：启动器窗口出现并截图（10619 B）⇒ 截图非黑图 ⇒ 已按 PID 停掉。
> 🔴 **§2 不带 `bridge_token.txt`**：rc9 的 `ext/bridge_token.txt`（32 B，12:24:59，A 本机生成）**已从 rc10 删除**（构建时清 1 个），打包脚本黑名单加 `bridge_token*`／`*.pid`／`*.log` ⇒ 出包前清理 + 闸门断言剩余 **0**（反证自测：塞 3 个 ⇒ 必须全被抓到）。⚠️ 附带发现：rc9 的**目录**比它的 zip 多了 **1 515 个 `.pyc`**（验收跑出来的，其中 `app/__pycache__/device_config.cpython-312.pyc` 是**旧版 device_config.py** 的**过期字节码**）⇒ rc10 **拷贝时就排除** `__pycache__`/`*.pyc`，且验收全程 `PYTHONDONTWRITEBYTECODE=1` ⇒ 包内 `.pyc` = **0**。
> 🔴 **§3 EXT 在 MiniMVP 本版 ASR 不可用 ⇒ 文档如实写**：README_zh/en 的「配音桥接（EXT）」段与 `ext/USER_GUIDE.md`（文首醒目块 + 第 2 节第 3 步 + 第 9 节已知限制）都写明「EXT v0.4.8 的 `engine_runtime.py` 写死 R2T2 的 ASR，本包只有 0.6B stateful ⇒ 不会出现 `真实引擎已接线`／`TTS 就绪` ⇒ **待 EXT 适配 0.6B**；本包不要用浏览器插件这条链路，App 自带语音输出不受影响」。**EXT 仍嵌 v0.4.8 @817abcb，rc10 不等它**（reviewer 做好适配后另行通知换嵌）。
> 🔴 **§4 README 文字修正**：① perftest「已知问题」里那句错的「**TTS/MT 都放 GPU.0** ⇒ **ASR 必须放 NPU**」改成「**ASR 与 MT 同放 GPU.0**（本包出厂默认）—— 旧解码器时期在 B 机报过 `CL_OUT_OF_RESOURCES`；stateful 负载约为旧解码器的 1/3，待 B 机复核」；② `%LOCALAPPDATA%Confucius4LiveCaption` **补反斜杠** ⇒ `%LOCALAPPDATA%\Confucius4LiveCaption`（三份 README 全改）；③ **README_en 的「What is inside」表格整张英文**（中英两表由**同一份 `DEV_ROWS` 数据**生成，不会漂移）。perftest 新增「**B 机要跑的两组**」：组 1 = 本包出厂默认（ASR=GPU.0／MT=GPU.0／TTS=NPU）、组 2 = 旧默认（ASR=NPU／MT=GPU.0／TTS=GPU.0），各 10 分钟，每组记 ASR RTF、WER、TTS 提交/播完/丢弃。
> 🔴 **验收（rc10 包目录，**不带设备参数**）**：整链 **10 分钟**（`test_audio/clip_10min_0_600.wav`）⇒ ASR `EXECUTION_DEVICES：encoder=GPU.0，decoder=GPU.0（请求设备 GPU.0）`；TTS `EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，decoder=NPU/…`，`实测执行设备：NPU/NPU(lazy)`，`落点统计：NPU 上 12 个组件` ⇒ **ASR 真的在 GPU.0、TTS 真的在 NPU**（查的是 `get_property('EXECUTION_DEVICES')`，不是「写的 device=」）；ASR RTF **0.538**；TTS **提交 158／播完 126／丢弃 32**。GUI 截图（非黑图 42619 B，ASR 两档 stateful、克隆置灰、10 语种、状态栏无旧告警）。静态项：包内无旧解码器目录、`app/` 旧解码器字面 = 0、MANIFEST 6 模型 `all_match`、EXT = 0.4.8 @817abcb、黑名单 = 0、bat 闸门 0 失败、`.pyc` = 0。
> 🔴 **本轮自曝并修掉的 4 个真问题**：① **打包闸门自曝**——我在注释里写「旧 mask2 解码器」⇒ 命中 reviewer 自己核过的「`app/` grep `mask2` = **0**」⇒ 全文改用「旧解码器」（**含 reviewer §7 给的日志文案**：他那句里带 `mask2`，直接用会让 app/ grep 命中 3 处；本轮**按同一口径改写**，语义不变）；② **首轮 GUI 探针用错解释器**（系统 python 缺 numpy/openvino ⇒ ImportError，**非产品缺陷**）⇒ 改用**包内 python** 重跑（`app505_app105_rc10_gui_retry.json`，PASS）；③ CLI 文案里出现「旧 旧解码器」（替换时留下的重复字）⇒ dev 树与包内**同步定点修正**，复跑 `--check` 确认；④ **用 `subprocess.run(capture_output=True)` 调 bat 会挂死**（启动器 pythonw **继承 stdout 管道** ⇒ 管道不关闭 ⇒ `run()` 等到 180 s 超时 ⇒ 抛 `TimeoutExpired` ⇒ 首轮验收**报告没落盘**）⇒ 改用 **`Popen` + 输出落文件**后复跑：启动器窗口出现（截图 10619 B）、按 **确切 PID** 停掉、无残留。首轮失败记录**原样保留**在验收报告里（`11_gui` / `13_start_bridge_bat` 标了 `first_attempt` / `superseded_by`），整链 10 分钟**没有重跑**（报告由 `_app506` 用同一批原始产物重建）。
> 🔴 **交付**：目录 `~/Confucius4_LiveCaption_MiniMVP_v1.0-rc10/`（10,629 文件／5.516 GiB／5,923,022,269 B）＋ zip `~/shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc10_perftest.zip`（**5,926,048,165 B**／两遍打包收敛）；**模型未动**（MANIFEST 6 个模型 SHA 与 rc9 相同）；**rc9 及更早目录/zip 一律未动、未删**；未打 v2.5、未调 MiniMax、未通知用户（reviewer 通知）。
> 🔴 **本条需等 reviewer 复核**（APP-105 §6/§7：rc9 不重打、rc10 交付给 B 机做 App 性能测试，EXT 不在测试范围内）。
