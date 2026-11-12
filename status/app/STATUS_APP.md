# STATUS_APP

last_ack: APP-105
更新时间: 2026-11-13 06:49:24
当前任务: **无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 **105 条**／最大 **APP-105**／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47 ⇒ 开工＝收尾**逐字一致**；**6 通道全查空** ⇒ 无遗漏指令）｜`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）｜**复跑既有闸门 3/3 复现 §185／§188 结论**（app157 dev 11/0、app510 反证 VERDICT PASS、app512 包矩阵**完整版判定未变**）｜🔴 **本轮修掉 2 个 App 侧真缺陷**：① **打包闸门④的检测范围有洞**（只看**分支条件**里有没有 `_has_clone_voice()` ⇒ **分支①**（`if self.clone_mode and not _bound:`）**看不见** ⇒ 它去掉守卫后闸门④ 仍 PASS ⇒ 实测真串音）＋ **守卫可指向不存在的属性**（`not self._bound` 整个模块不存在）② **app512 的包过滤漏扫全部 10 个 MiniMVP 包** ⇒ 此前「真包矩阵 9/9」**只覆盖完整版** ⇒ 实测 **MiniMVP v1.0/rc1–rc5 同样缺收窄**｜新证据 `app521`（**静态闸门④ × 行为判据 app157 B3 交叉验证**：合成 12/13、真包 17/18、e2e fail-closed PASS）｜**§185 的交付阻断项仍未裁定**（完整版 v2.5 必须带 APP-086·2a 收窄）｜未打包、未调 MiniMax、未通知用户
阻塞 / 待用户决定: 🔴 **待 reviewer 裁定**：磁盘上的**完整版**包 **v2.2／v2.3／v2.4** 的 `synth()` 分支 ② 是 `elif self._has_clone_voice():`（**缺 APP-086·2a 的 `and not _bound` 守卫**）⇒「按句绑定模式 + 标签晚到（spk=None）」会**沿用上一句克隆音色、不回落预设 A**⇒ 判据 **B3 FAIL**（观测 `after_embed=VEC_S2`）⇒ 即「**男声被配成女声／串音**」根因；**收窄只在 dev 树与 MiniMVP rc7/rc8/rc9/rc10**（rc10 克隆置灰 ⇒ 该路径惰性）⇒ **完整版 v2.5 必须带上收窄后才可交付**（本轮未打包；**闸门④已 fail-closed**（本轮又补上分支①与「守卫须指向真实绑定」），打包时会自动拦截）｜**当前交付版 v2.1 无分支② ⇒ 不受此缺陷影响**｜🔴 **本轮新查实**：**MiniMVP v1.0／rc1／rc2／rc3／rc4／rc5 同样缺收窄**（此前 6 轮从未扫到，因 app512 包过滤只认完整版）⇒ **带缺陷的包共 10 个**｜🔴 **等 reviewer 复核 rc10**（APP-105 §6／§7）｜**B 机实测仍未做**｜**v2.5 未打包**｜**EXT 的 ASR 在 MiniMVP 本版不可用**
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）｜**§167 压缩**：§167 正文整块归档 ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12 277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）｜**§168 压缩**：§168 正文整块归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8 599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）｜**§178–§180 压缩**（APP-101 §1.d「每节不超过 3 行速查」）：三节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec178_180_20261112.md`（块 SHA256 `d91b34ffed16ff1b22f0dd369c66bd9477351a8e782f327ff1740f0b44113705`）；活文档三节各留 1 行速查｜**§141–§160 压缩**：20 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec141_160_20261112.md`（块 SHA256 `444da45055a7a2c8d95bf89aca691d6bdb4241bb26f987123e16f58751174fe5`）｜**§171–§180 压缩**：10 节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜**§170 + §183 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（块 SHA256 见 §185）｜**§186 + §187 压缩（2026-11-13）**：两节正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）｜**「最近更新」5 条较旧条目（APP-104／APP-102／接单 APP-101／APP-099×2）整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_20261113.md`（块 SHA256 见 §188）｜**§188 压缩**（2026-11-13）：§188 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec188_20261113.md`（块 SHA256 见 §189 末）


## 最近更新
> 🔴 2026-11-13 06:49:24 ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜**修掉 2 个 App 侧真缺陷**：① **打包闸门④的检测范围有洞** ⇒ 只看分支条件里的 `_has_clone_voice()` ⇒ **分支①**（`if self.clone_mode and not _bound:`）看不见 ⇒ 实测「分支①去守卫」⇒ 闸门④ 仍 PASS 而行为判据 **B3 FAIL**（真串音）⇒ 改为「分支体里自己执行 keep-logger 调用」也算（**不下钻进嵌套 If**）＋ **守卫必须指向真实存在的绑定**（`not self._bound` 整个模块不存在）② **app512 漏扫 10 个 MiniMVP 包** ⇒ 实测 **MiniMVP v1.0/rc1–rc5 也缺 APP-086·2a 收窄**｜新证据 `app521`：**静态闸门④ × 行为判据 app157 B3 交叉验证**（合成 12/13、真包 17/18、e2e fail-closed PASS）｜复跑既有闸门 3/3 复现 §185／§188 结论｜未打包、未改客户包、未改产品代码、未通知用户
> 🔴 2026-11-13 04:46:11 ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门④判据本身 fail-open** ⇒ 旧判据「test 树里出现过 `not _bound`」会放行 ①`not _bound` 挂在 OR 上 ②悬空调用（两者改前都 PASS）⇒ 改为「分支条件**逻辑蕴含** `not _bound`」＋悬空调用登记｜合成矩阵 **12/12**、真包矩阵 **9/9 判定未变**（v2.2／v2.3／v2.4 FAIL；v2.1／v2.0／v1.13／rc10／dev PASS）、e2e fail-closed **PASS**｜复跑既有闸门 3/3 复现 §185 结论｜未打包、未改客户包、未改产品代码、未通知用户
> 🔴 2026-11-13 03:32:16 ｜ **巡检无新 reviewer 纠偏**（纠偏文件 105 条／最大 APP-105／SHA `321be59c…`／344 419 B／mtime 11-12 14:25:47，6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门放行 APP-086·2a 缺陷** ⇒ 新增**打包前闸门④**（`pack_v13.py` → `check_app086_2a_narrowing`：AST 查`self._has_clone_voice()` 分支必须带 `not _bound` 守卫，缺则拒绝打包）｜鉴别力 **12/12**（真包 v2.2/v2.3/v2.4 全 FAIL、v2.1/v2.0/v1.13/rc10/dev 全 PASS；去守卫反证 ⇒ FAIL）｜e2e **PASS**（闸门③ PASS 的缺陷包被闸门④ FAIL 拦住）｜复跑既有闸门 3/3 复现 §185 结论｜未打包、未改客户包、未改产品代码、未通知用户｜**复跑既有闸门 3/3 复现 §185 结论**（app157 dev 11/0、app510 反证 VERDICT PASS、app512 包矩阵：v1.13/v2.0/v2.1 PASS 11/0、v2.2 9-2／v2.3 8-3／v2.3_aborted 8-3／v2.4 9-2 FAIL、v1.5 判据不适用；rc10 11/0）｜🔴 **完整版 v2.5 必须带 APP-086·2a 收窄**（§185 交付阻断项待裁定）｜未打包、未改客户包、未改产品代码、未通知用户
> 🔴 2026-11-12 16:51:46 ｜ **APP-105 执行完（rc10）**｜rc10 目录 10,629 文件／5.516 GiB ＋ zip 5,926,048,165 B｜包上验收 13/13 PASS｜**出厂默认第 2 代 ASR GPU.0／MT GPU.0／TTS NPU**（`defaults_version` 8→9，rc9 存的旧默认按代次忽略）｜`Start_Bridge.bat` 改 CRLF+ASCII（cmd /c 实测能拉起启动器）｜包内**无** `bridge_token.txt`（黑名单闸门）｜README/USER_GUIDE 如实写明 EXT 的 ASR 不可用｜整链 10 分钟：ASR EXECUTION_DEVICES=GPU.0、TTS 实测落点 NPU（12 个组件）、TTS 提交 158／播完 126／丢弃 32｜模型未动｜未打 v2.5、未调 MiniMax、未通知用户
> 🔴 本节 5 条较旧「最近更新」条目（APP-104 执行完（rc9）／APP-102 执行完（rc8）／接单 APP-101／APP-099 开始／APP-099 执行完）原文已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_20261113.md`（块 SHA256 见 §188）；活文档本节仅留本指针行。
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

## §170 与 §183｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（4713 B／块 SHA256 `ded2cae481bf6ca175f7a1a71255ad508e12318edc862bf413737f180cd345a8`）｜活文档留此指针行
## §171–§180（本批 10 节）｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec171_180_20261112.md`（块 SHA256 `d99afb9af214f84d64d4da021101f743a2ee405e51114034c554d65119fd55d2`）｜活文档留此指针行

## §181 接单 APP-101 / APP-102（2026-11-12 09:46:41）｜静态前置完成；设备作业与 rc8 未做
> 🔴 **已做**（证据 `results/app/app482_app101_102_model_identity.json`）：EXT v0.4.8 @`817abcbe…` 用 `git archive` 暂存 `_ext_v048_stage`（167 文件／`ext/accel_usage.py` 在位／manifest `version=0.4.8`）；decoder bin SHA `0059531a…d6a3` 与 reviewer 一致、IR `inputs_embeds [1,1..512,1024]`、hidden 1024／28 层、encoder bin `0b7463d6…` 前缀一致；`device_config.py:69-74` MiniMVP `tts` `NPU`→`GPU.0`（`ast.parse` OK、GUI/CLI 同源）。
> 🔴 **未做**（需持 `MACHINE_LOCK` 长作业，**不虚报**）：`backends_stateful.py` 后端／`make_backend` 分派／`manifest_gen` 源目录／rc8 打包脚本、4 臂短冒烟、10 语种冒烟、GUI 截图、rc8 目录+zip 与包上验收 ⇒ **未打 rc8／v2.5、未通知用户、未调 MiniMax、未占设备**；`last_ack` 保持 `APP-100`（理由见头部），**等 reviewer 裁定**。

## §182 执行 APP-102 / APP-103（2026-11-12 10:44:44）｜rc8 已打并验收 6/6 PASS；撤回 §181 的「未做／等裁定」结论
> 🔴 **已做**（证据 `app484…json` / `app486…json` / `app487…json` / `app488…json`）：stateful 后端照 B-kit `bk_run.py`（NPUW_LLM、每次 generate 新建 InferRequest＋`reset_state`、eos/pad 用导出 id、512 上界截最旧前缀且实测截断 0 次）；旧无 KV 基线只在 dev 树，包内旧目录/字面 0（打包闸门反例自测 2/2 能识破）；rc8 目录＋zip 落盘，验收 6/6、4 臂短冒烟 4/4、10 语种 30/30，`last_ack=APP-102`（APP-103 裁定）。
> 🔴 **rc8 后补**（APP-102 §4）：10 分钟片段 4 臂配对 WER/RTF ＋ 整链一臂、预设 A 对照组、交付配置表细项；计时 json 已带锁 `ended` 与 `timing_valid`（`app486/487/488`）。**做完即停，等 reviewer 复核**（B 机实测由 reviewer 安排）；v2.5 未打、未调 MiniMax。

## §170 与 §183｜**正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec170_183_20261113.md`（4713 B／块 SHA256 `ded2cae481bf6ca175f7a1a71255ad508e12318edc862bf413737f180cd345a8`）｜活文档留此指针行

## §184 执行 APP-105（last_ack=APP-105，2026-11-12 16:51:46）｜MiniMVP rc10 已打并验收 13/13 PASS｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec184_20261113.md`（6953 B／块 SHA256 `b746af218d24a41132c6e13a081495c2e9a9044357869f66c35441787ca94cfb`）。
## §185 巡检（last_ack=APP-105，2026-11-13 00:43:00）｜**无新 reviewer 纠偏**；接上个会话断点修好 **app157 判据**（**判据层，产品代码零改动**）｜🔴 **查明完整版 v2.2/v2.3/v2.4 仍带 APP-086·2a 串音缺陷**｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec185_20261113.md`（块 SHA256 见 §187 末）；活文档保留本标题行 + 1 行指针。
## §186 巡检（last_ack=APP-105，2026-11-13 02:03:00）｜**无新 reviewer 纠偏**（6 通道全查空）｜复跑既有闸门 3/3 **复现 §185 结论**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）；活文档保留 §186 标题行 + 1 行指针。
## §187 巡检（last_ack=APP-105，2026-11-13 03:32:16）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门放行 APP-086·2a 缺陷**（新增打包前闸门④）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec186_187_20261113.md`（块 SHA256 见 §188）；活文档保留 §187 标题行 + 1 行指针。


## §188 巡检（last_ack=APP-105，2026-11-13 04:46:11）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 1 个 App 侧真缺陷：打包闸门④的判据本身是 fail-open**｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec188_20261113.md`（块 SHA256 `d7ffc944c78957d906d55838b9bc6d93fb6df3cfe5fba9c57dcb66473db30b0c`）；活文档保留 §188 标题行 + 1 行指针。

## §189 巡检（last_ack=APP-105，2026-11-13 06:49:24）｜**无新 reviewer 纠偏**（6 通道全查空）｜**修掉 2 个 App 侧真缺陷：打包闸门④的检测范围有洞（分支① 看不见）＋ 守卫可指向不存在的属性；app512 漏扫全部 MiniMVP 包**｜**本条需等 reviewer 复核**

> **① 纠偏文件复核（只读、未改、未提交）**：开工＝收尾 **105 条**／最大 **APP-105**／SHA `321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1`／**344 419 B**／mtime **2026-11-12 14:25:47** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）。
> **② 其它通道全空（⇒ 无遗漏指令）**：`shared/NOTICE*` 最新仍 **11-05**｜agent-mail 工具仍回 **`not_bound`**｜`conversation_search` 两次不同措辞均 **0 命中**｜git `main...HEAD` ahead=0/behind=0｜`claude-clone`（worktree `clone_dev`）`git log claude-clone --not main` = **0**（**方向性判据**，不用 `merge-base --is-ancestor`）｜`MACHINE_LOCK` **NOT_PRESENT**（未占设备）。
> **③ 复跑既有闸门 3/3 复现 §185／§188 结论**：`app157` dev **11 PASS/0 FAIL**｜`app510` 反证 **VERDICT PASS**（M1–M4 注入缺陷全被识破）｜`app512` 包矩阵**完整版判定未变**（v1.13／v2.0／v2.1 PASS 11/0；**v2.2 9-2／v2.3 8-3／v2.3_aborted 8-3／v2.4 9-2 FAIL**；v1.5 **2/8 判据不适用**）＋ **新增 MiniMVP 10 行**（见 ⑦）。`app157`／`app510` 两个 evidence 复跑后与 HEAD **逐字节一致**（归一化行尾后，零 diff 噪声）。
> **④ 🔴 真缺陷 1（判据层；产品代码零改动、客户包零改动）：打包前闸门④ 的**检测范围**有洞**。旧闸门④ 只在**分支条件里**调用 `self._has_clone_voice()` 时才把分支纳入检查 ⇒ **分支①**（`if self.clone_mode and not _bound:`，分支体里只调 `self._log_keep_clone()`、**不调** `_has_clone_voice()`）**根本看不见** ⇒ 它的 `and not _bound` 一去掉（=「按句绑定模式 + 标签晚到 ⇒ 沿用上一句克隆音色」⇒ **串音**）时，闸门④ **仍判 PASS** ⇒ **实测探针**：闸门④ **rc=0（放行）** 而 app157 行为判据 **B3 FAIL**（观测 `after_embed=VEC_S2`／`after_kind=clone`）⇒ **判据自问自答**（「这条判据若被人当真去改生产代码，会不会改坏」）：**会**（照旧判据把分支① 的守卫删掉是「安全的」⇒ 等于把串音改回来）。
> **⑤ 修法（只改 `pack_v13.py`）**：**91 872 B**／CRLF **1 856 行／裸 LF 0**（原文件即 CRLF）／`ast.parse` OK／`--help` OK／`import` OK（`PKG_VERSION=2.5`）／difflib 复核＝**删 10 行全是旧判据实现、增 90 行**。
>    * **补丁 A（范围）**：把「**分支体里自己**执行了 keep-logger 调用（`_log_keep_clone`／`_log_keep_last_clone`）」也纳入分支识别 ⇒ 🔴 **不下钻进嵌套 If**（否则外层 `if not self._apply_self_ref_voice():` 会被误判成 keeper ⇒ fail-closed 误拦**正确**的包）。
>    * **补丁 B（守卫）**：`not X` 里的 `X` 必须**在本模块里真的被绑定过**（Name 出现在 Store 上下文／`self.X` 真被赋值过）⇒ 修掉 `not self._bound`（`self._bound` **整个模块不存在** ⇒ 守卫是摆设 ⇒ `AttributeError`／恒假）。
>    * 闸门链位置**不变**：闸门④ 在 `pack_v13.py:1402`，`zipfile.ZipFile(tmp_zip,'w')` 在 **`:1451`** ⇒ 仍在建 zip **之前**（`app521` 用 AST 独立验过）。
> **⑥ 鉴别力 + 交叉验证（新脚本 `results/app/app521_gate4_scope_crosscheck.py` ＋ evidence `results/app/app521_gate4_scope_crosscheck_evidence.json`）**：**静态闸门④** 与 **行为判据 app157 B3** 两条**互相独立**的判据**同判**才算一致。
>    * **合成矩阵 12/13 一致**：`b1_guard_removed`（分支①去守卫）**改前闸门④ PASS ⇒ 改后 FAIL**（缺口已封）｜`b2_guard_removed` FAIL｜`both_guards_removed` FAIL｜`b1_guard_parens` PASS｜`b1_guard_not_self_bound` **改前 PASS ⇒ 改后 FAIL**（补丁 B 生效）｜`b1_guard_or` FAIL｜`b2_guard_or` FAIL｜`b2_guard_and_other` PASS｜`hoisted_unguarded` FAIL｜`hoisted_guarded` PASS｜`hoisted_guarded_or` FAIL｜**唯一不一致 = `b1_guard_equiv_attr`**（`not self._spk_voices` 语义等价但闸门④ 判 FAIL）⇒ **fail-closed（安全方向）**，不放大成漏洞。
>    * **真包矩阵 17/18 一致**：**唯一不一致 = v1.5**（代码早于按句绑定 ⇒ B3 **判据不适用**，§188 已记录）。
>    * **e2e fail-closed PASS**：v2.4 基线 rc=**1**（分支② 无守卫）｜v2.4 ＋ 分支①去守卫 rc=**1**｜dev 树收窄文件 rc=**0**。
> **⑦ 🔴 真缺陷 2（工具覆盖漏洞）：`app512` 的包过滤只认完整版**。`pkg_dirs()` 用 `startswith('Confucius4_LiveCaption_v')` ⇒ **MiniMVP 的目录名是 `Confucius4_LiveCaption_MiniMVP_v1.0-rcN` ⇒ 10 个目录全部漏扫** ⇒ §185／§186／§188 反复引用的「真包矩阵 9/9」**只覆盖了完整版**。已修（app512 现在扫 **17** 个包）⇒ **新查实结论**：**MiniMVP v1.0／rc1／rc2／rc3／rc4／rc5** 的 `app/tts_worker.py` 分支② 是 `elif self._has_clone_voice():` ⇒ **同样缺 APP-086·2a 收窄**（app157 行为判据 **9/2**、B3=**False** ⇒ 与闸门④ rc=1 **同判**）｜MiniMVP **rc7／rc8／rc9／rc10** PASS **11/0**。
> **⑧ 🔴 交付阻断项（结论更新）**：**带 APP-086·2a 缺陷的包共 10 个** ＝ 完整版 **v2.2／v2.3／v2.3_aborted／v2.4**（4）＋ MiniMVP **v1.0／rc1／rc2／rc3／rc4／rc5**（6）⇒ **完整版 v2.5 必须带收窄**（闸门④ 现已覆盖分支①/分支②，且 fail-closed）｜MiniMVP 的缺陷路径**此前记录为惰性**（MiniMVP 克隆置灰 ⇒ `clone_mode` 恒 False、无克隆音色 ⇒ 走 `else` 回落预设 A）⇒ **风险等级低于完整版**，但代码仍带缺陷；**本轮未做设备级复核**（纯静态、零推理）｜**当前交付版 v2.1 无分支② ⇒ 不受此缺陷影响**。
> **⑨ 纪律**：**未打包**（用户不通知不打包；rc9／rc10 已打好 ⇒ 绝不重打包；**v2.5 未打**）｜**未改任何客户包**（全部只读）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 `CORRECTIONS_APP.md`**｜**未跑推理／未计时 ⇒ 未取 `MACHINE_LOCK`**｜**未调 MiniMax**｜**未通知用户**｜**未提交** ASR／MT／TTS 其它模块的 700+ 个未提交文件｜探针与临时脚本全在**临时目录**，只把 `app521` 脚本＋evidence 入库（可复现）。
> **⑩ 本条需等 reviewer 复核**：① **完整版 v2.5 必须带 APP-086·2a 收窄**（何时打包由 reviewer 定）；② **v2.2／v2.3／v2.4 ＋ MiniMVP v1.0／rc1–rc5 是否作废／标注**；③ **闸门④ 本轮两处判据改动**（分支体 keep-logger 检测 ＋ 守卫须指向真实绑定）是否接受；④ **app512 扩到 MiniMVP** 后 evidence json 变了（**5 137 B → 11 507 B**，多 10 行）是否接受；⑤ 新增 `app521` 脚本＋evidence 与 **APP-101 §1.d「不再新增审计／判据脚本」** 的张力（本次已入库 ⇒ 可复现；reviewer 可要求删除）。
