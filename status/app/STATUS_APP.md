# STATUS_APP

last_ack: APP-098
更新时间: 2026-11-11 06:32:29
当前任务: **巡检无新纠偏**（`last_ack=APP-098`；纠偏文件仍是 97 条 / 最大 APP-097 ⇒ 无编号更大的新条目）｜**本轮修掉 2 个 App 侧真缺陷**：**① 🔴 self_ref 克隆漏「克隆模式」闸门**（§168 ⑤ 实测 `--tts-voice A` 时 **78/78 句** `voice_kind='clone'` ⇒ 用户选预设 A 却每句都在克隆⇒ 与 reviewer 2026-11-07 已定口径「preset voice selected => never register clone voices」**冲突**⇒ 已补闸门：GUI 用 `_clone_enabled`、CLI 用 `_want_clone`（**与姊妹闸门 98cf8fc 同源同口径**）⇒ **行为级判据 8/8 PASS**（含反证 2/2）｜**② 🔴 开发期 `assert_*.py` 闸门可能随包泄漏**（§173 ⑥ 下一轮必读项：`pkg_exclude` 只排 `_` 前缀 ⇒ `assert_sec_per_char_calibrated.py` 等 3 个开发闸门**不会被排除** ⇒ 内含开发机路径 ⇒ 已加 `APP_DEV_ONLY_ASSERT_RE` 排除规则（`assert_pkg_clean.py` **必须随包** ⇒ 白名单例外）⇒ **判据 13/13 PASS**（含反证 2/2）｜**既有闸门复跑全绿**（sec_per_char 27/27、app109 34/34、pkg_clean 对 v2.4 0 违规、window 同源 PASS）｜**未打包 v2.5、未同步任何客户包、未通知用户、未调 MiniMax、未占设备**｜结果见 §174｜**本条需等 reviewer 复核**
阻塞 / 待用户决定: 🔴 **GUI 布局缺陷修复仍未同步进客户包**（只在 dev 树 + 影子包）⇒ **v2.5 未打包、未同步任何客户包目录**（APP-055 须走打新版本号）⇒ **请 reviewer 裁定**：立刻修还是随 v2.5 一起出｜🔴 **该缺陷的历史影响「已定界」**（§171：D1 零交付物受影响／**D2 影响已交付的 rc5**）⇒ **不再是「未评估」**｜🔴 **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972 ⇒ 不可分）⇒ 未自行换判据｜🔴 **§3.6「切段真实发生时的设备开销」在本素材上结构性不可测**（质心恒 1）⇒ 需 reviewer 裁定是否调聚类阈值/换素材｜**APP-097 §2-4 的 `_SEC_PER_CHAR` 已由 §172 回填**（de .073／fr .070／es .085／pt .080／it .081／ru .083；zh/en/ja/ko 未动；守卫阈值只会变松）｜**倍率地板仍未裁定** ⇒ 等 reviewer｜🔴 **本轮 2 处修复待 reviewer 复核**：① self_ref 克隆闸门（**已改 dev 树**，客户包未动 ⇒ **已交付的 rc6/rc7 不受影响**——判据已证 `clone_voice.py` 不在包内 ⇒ 该路径为死代码）② `assert_*.py` 排除规则（**只改打包规则**，不改任何客户包目录）｜🔴 **C 盘 22.7 G 可用（99 %）** ⇒ v2.5 打包需 10–15 G（**本轮未删任何文件**）｜**未打包 v2.5、未通知用户**
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）｜**§167 压缩**：§167 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec167_20261110.md`（12277 B／块 SHA256 `f072058905e5663af6f2faa1244af68aea08ffd1b2de86700a1f754f17773e88`）｜**§168 压缩**：§168 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec168_20261110.md`（8599 B／块 SHA256 `f7c1462abbe2a03fc6a0887fcaae762984a2ef3fbfcfcb78ece98acf1e65b343`）


## 最近更新
> 🔴 2026-11-10 20:31:40 ｜ **执行 APP-098（MiniMVP rc6 修整）**（reviewer 口头下达；`CORRECTIONS_APP.md` **仍是 97 条 / 最大 APP-097 ⇒ APP-098 未落该文件**；本文件**只读未改**）｜**开工基线**：`last_ack` APP-097 → APP-098（头部定点改，旧正文一字未删）｜代码改在 dev 树 `live_caption/`，MiniMVP 与 v2.5 共用部分只改一处（**共用代码走 dev 树**，MiniMVP 专属行为走**包内标记**而非第二份副本）｜本轮**未打包 v2.5**、**未通知用户**、**未调 MiniMax**。
> 🔴 2026-11-10 18:51:52 ｜ **巡检无新纠偏**（纠偏文件仍 97 条 / `last_ack=APP-097`）；**查出并修掉 2 个 App 侧真缺陷**：① §167 归档件引用了**磁盘上不存在**的路径 `results/app/_app326_app097_lang_out/mt.json`（真实路径 `results/app/app326_app097_lang_out/mt.json`，122 674 B；**§167 ④ 的数字逐字段复核全部成立** ⇒ 只是路径写错）｜② `speaker_tracker.py` 注释仍写「ASR 侧默认 10 s / 589 帧 / 兜底 10.0 = ASR 侧默认值」⇒ **与 ASR 现状（5.0 / 293 帧）不符**，且「= ASR 侧默认值」这句**假陈述会诱导把兜底改成 5.0 ⇒ 破坏 IR 配套 ⇒ 旁路静默降级** ⇒ **只改注释、不动代码**（AST 证明 8/8 PASS）｜新增 3 道静态闸门（引用路径可定位 34/34 PASS、窗长同源+兜底配套 8/8 PASS、注释-only AST 证明）｜**本条需等 reviewer 复核**；未打 v2.5、未通知用户、未调 MiniMax、未改任何默认值。
> 🔴 2026-11-10 16:53:01 ｜ **巡检无新纠偏**（纠偏文件仍 97 条 / `last_ack=APP-097`）；**补做 APP-093 §3.6「切段开/关的 ASR RTF」对照**（设备跑，持锁，ABBA 五臂）：切段开 0.621 vs 切段关 0.627（Δ -0.0055）⇒ **切段路径确实被走到**，但**质心恒 1 ⇒ 切段自身设备开销 = 0**（详见 §168）｜**本条需等 reviewer 复核**；未打 v2.5、未通知用户。
> 🔴 2026-11-10 15:59 ｜ **APP-093 §3 + APP-097 §2 已补齐**（详见 §167）：🔴 **定位并修掉一个阻断级真缺陷** —— `commit 874924a` 把 `_clone_nearest` **误插进 `App.__init__` 中间** ⇒ **整个 GUI 布局代码被吞进该方法体** ⇒ GUI 一直只是空壳 `tk` 200×200（无标题/无控件/引擎不加载/字幕永不出现）⇒ **dev 树已修**（纯搬移，8 项校验全 PASS）｜**§3.7 截图 PASS**（主窗 1455×1132＋**三行字幕条** 1638×157，读图确认 译文/原文/实时 三行）｜**§3.3 过载臂**：过载段 20 句/19 句被跳过，**恢复用时 3.597 s**；**§3.5 判据失效已量化**（三人真值余弦 0.957–0.972）⇒ 未自行换判据；MT 8 语种 ×20 句 **0 空译/0 错误**；TTS **撞帧上限 0**；模型身份 12/12 一致｜**本条需等 reviewer 复核**｜未打 v2.5、未通知用户。 **APP-097 已 ack**（reviewer 11-10 中途追加，96→97 条）：目标语言从 zh/en/ja/ko 扩到 **Qwen3-TTS 支持的全部 10 种**（+de/fr/es/pt/it/ru）；`LANG_MAP`/`SUPPORTED_LANGS`/`_LANG_NAME`/`TARGETS`/`TARGET_LABELS` 已扩；**未知语言不再静默退回 English**（`map_language(strict=True)` 显式报错）；**西里尔判成 ru**、**拉丁字母语言之间不再凭脚本跳过翻译**；GUI/CLI 下拉自动跟随｜**逐语种设备验收未跑 ⇒ 本条需等 reviewer 复核**｜EXT 内嵌版本以 reviewer 最后通知为准（**v0.3.7 @c414294**）。
> 🔴 2026-11-10 12:15:35 ｜ **APP-094/095/096 已执行**：MiniMVP **rc5** 出包（ASR→**Qwen3-ASR-0.6B** mask2 INT8；R2T2 的 ASR IR **全删**；zip 清单 INT4/R2T2 计数 **0**；4424246739 B／SHA256 `1fd56fbd9572…`／10473 条目 CRC32 全对）；**两臂设备验收**：iGPU RTF **0.73**／延迟 472 ms／峰值 3585.5 MB，NPU RTF **0.89**／延迟 670 ms／峰值 3455.1 MB（WER 交 reviewer 复算）；**EXECUTION_DEVICES 直证 encoder=NPU/decoder=NPU**；**APP-094① keep-first 落地**（判据 5/5，含反证组）｜**APP-093 §3 只完成 §3.2 ⇒ 需等 reviewer 复核**；未打 v2.5、未通知用户。
> 🔴 2026-11-10 08:49 ｜ **APP-093 [HIGH] 已 ack**（reviewer 08:13 中途追加，92→93 条）：§162 复核「移植结构接受／验收不通过」⇒ **app394 `verdict=FAIL` 如实入册**、`app391…json` 幻影产物撤回、`tts_late_drop_sec` 默认保持 6.0；§3.1 静态诊断＋§3.4 before 补算已落盘（app395／app396）⇒ 设备作业（阈值 A/B・过载臂重做・切段・GUI 截图）本轮未跑 ⇒ **本条需等 reviewer 复核**；未打 v2.5、未通知用户。
> 🔴 2026-11-10 07:41 ｜ **MiniMVP rc4 zip 已出**：`shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip`（8 609 378 581 B／SHA256 `f0ebcc72…`）；**10 480 条逐条 CRC32 全对**、缺/多条目 0/0；**rc3 两个 zip SHA 逐字未变**；**从 zip 解压的干净包**（10 480 条／68.29 s）用**包内 python** 跑 `--check` 显示「**Intel NPU · INT8 模型齐全**」、`EXECUTION_DEVICES` encoder=NPU／decoder=NPU；🔴 打包前修掉 README 沿用 rc3 数字（6.7 GB/10 474 ⇒ 实测 10.0 GB/10 480）这一 **APP-073(c) 同类**缺陷。
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
| 语音输出设备 | TTS 走 NPU（F16 / INT8 视配置） | `app048_layout_1920x1080.png`（语音区实测「语音区 · Intel NPU · F16」） |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出） | `app185_app048_gui_layout_pkg_evidence.json` → `verdict=PASS` / `n_pass=64` / `n_fail=0`（**在客户包内代码上跑**） |
| 桌面快捷方式 | **v2.1 两个**（`Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`，均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证 ⇒ 非坏链）；⚠️ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（**未删**，待用户/reviewer 决定） | `results/app/app212_app057_v21_shortcuts_evidence.json` → `checks`（**9 PASS / 0 FAIL**，含 3 条反证） |
| 说话人识别旁路 | **默认关闭**（`--speaker off` 是默认；GUI 有「说话人识别」勾选框）⇒ v1.13 的阻断级回归已止血 | `results/app/app199_app054_ab_evidence.json` → `checks`（4 PASS / 0 FAIL）；`app197` → T7 |

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

## §141 无新纠偏（last_ack=APP-078）｜§140 证据链自证 48/0 全数落盘（2026-11-06 19:58:30）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec141_142_20261106.md`（§141 全文，逐字保留）。
> 🔴 **速查**：`_app310` **48 PASS / 0 FAIL**（34 条「结果文件＋原始字段」断言／3 条反证全被识破／11 条 STATUS 锚点命中）；`ac61878` 已提交、`origin/main..HEAD=0`；APP-075 停在「需 Opus 复核」⇒ v2.3 不打包。

## §142 无新纠偏（last_ack=APP-078）｜版本纪律与证据落盘静态自证 26/0（2026-11-06 20:55:30）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec142_20261109.md`（2128 B／块 SHA256 `912e9b29e5b6ee4eb44849cc4ffaf8094ace2d4a89702fdb75e4dc47c5c2cd84`；含版本纪律与证据落盘 26/0 静态自证）。
> 🔴 **速查**：APP-078 版本纪律（不 `--same-version`／不原地改客户包）与证据落盘口径不变；26 PASS / 0 FAIL。
## §149 执行 APP-081（last_ack=APP-081）｜v2.3 新目录＋新 zip 已打，APP-080 ⑥ 全套验收（2026-11-07 17:14）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec149_20261107.md`（12416 B／块 SHA256 `29784e3e09e787a4c3328e8c3d5559eef5b459a42554a182d0ddd6745567aebe`；含开工/收尾指纹、4a–4e 全部原始字段、20 项产物清单、r1 事故与 reviewer 待裁定项）。
> 🔴 **速查**：APP-081 **第 1–4 点已完成**（v2.3 新目录／新 zip `4b4a977a…cbfed`／14 320 条目／全套验收结果文件落盘）；**第 5 点需等 reviewer 复核**（自算 zip SHA／抽查 zip 内容／看 100%+150% 截图／裁定黑名单 1 项口径歧义与 `spk_conf` 缺陷）⇒ 复核通过后才由 reviewer 通知用户。

## §150 巡检无新纠偏（last_ack=APP-081）｜APP-081 第 5 点仍停在「需等 reviewer 复核」节点（2026-11-07 17:43:17）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec150_20261109.md`（6255 B／块 SHA256 `b3a055b6394c8de9e8f0e5b44005635d75b3202bcd1480efe9817b18e4939521`；含 APP-081 第 5/6 点判据、§149 归档链、产物表与 git 91abc26）。
> 🔴 **速查**：APP-081 第 5 点「reviewer 复核后再通知用户」＋第 6 点「不自创覆盖审计/静态自证轮次」⇒ 本轮仅 ack；不打包、不通知用户、不改 .lnk。
## §158 巡检无新纠偏（last_ack=APP-084）｜APP-084 停下节点未变：等用户测完 + reviewer 发起合回 main（2026-11-08 20:37:51）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec158_20261109.md`（5694 B／块 SHA256 `b5ea34eb55109a6bf72892de1237b408c1257f381466b11d1edb735a4e8a00eb`；含开工/收尾指纹、`merge-base` exit 1、产物表与 v2.3/v2.4 zip 元数据）。
> 🔴 **速查**：无新纠偏（84 条／`b3a1a900…b62`）；ack-only 停在「等 reviewer 发起把 claude-clone 合回 main」；`MACHINE_LOCK` NOT_PRESENT、未打包、未通知用户。

## §159 执行 APP-086 / APP-087 / APP-088（last_ack=APP-088）｜合并＋克隆移植＋GUI 文案已落盘，停在「等 reviewer 复核」节点（2026-11-09 09:38:39）

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec159_20261109.md`（11156 B／块 SHA256 `da8241c04798cbf70798b0588f54fd7da8a35e5c4530cfff1eb653f3df9d32db`；含开工/收尾指纹、合并提交号 `9d51ceb`/`b1496ba`、产物表与 v2.3/v2.4 zip 元数据）。
> 🔴 **速查**：APP-086① 合并 `9d51ceb`（11 文件）已完成；② 克隆 a–f **代码资产**已落盘（`clone_voice.py`）但**接线＋验收数字未完成**；③ GUI CUDA 文案已完成；④⑤ / APP-087 / APP-088 ⇒ **停在「等 reviewer 复核」**（未打包、未建 v2.5、未通知用户）。
> 🔴 **续接**：§160 继续做完了 ② 的**接线**（口径裁定见 §160）＋**验收数字**。

## §160 续做 APP-086② 克隆接线＋验收（last_ack=APP-088）｜**接线已完成**，验收数字见下表 ⇒ 停在 APP-086⑤ 等 reviewer 复核（2026-11-09 12:46:57）
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec160_20261110.md`（10985 B／块 SHA256 `82c35e22353d63f7639b4f469b154c19efd9de3e0763e6ba36040c01f4cb6ebf`）。

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
## §171 巡检（last_ack=APP-098，2026-11-11 01:02:00）｜**无新纠偏**；把 §170 ⑨ 两项「历史影响未评估」**定界完毕**（D1 零交付物受影响／**D2 影响已交付的 rc5**）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec171_20261111.md`（10930 B／块 SHA256 `45348f1f5e639e7b91a39e2ff1288264cabe6b60d9be7de4bdfe3842ce7081ff`）。
> 🔴 **速查**：**本轮无新 reviewer 纠偏**（`CORRECTIONS_APP.md` 仍 97 条／最大 APP-097，SHA `36af1620…`／285 671 B／mtime 11-10 11:49:26，开工＝收尾一致 ⇒ **SHA 零改动**；`last_ack` 已是 APP-098）｜**① D1（GUI 布局被吞）历史影响 = 零交付物受影响**：缺陷只在 dev 树的 **2 个 commit 快照**（`874924a`／`1cc86b2`）里，**15 个包逐个 AST 判定 0 中招**（含真包 v2.4 与 rc5/rc6/rc7）；窗口内 `app372` 截图全空（当时未归因）、`app331` 的 PASS 跑的是已修影子包 ⇒ **无 PASS 结论被污染**｜**② 🔴 D2（asr06b 档位 label 撞车）历史影响 = 已交付的 rc5 中招**（§170 未定位到 rc5）：**行为级判定**（把包内 `build_asr_options` 真源码在桩环境里**真跑一遍**统计 label 重复）⇒ **rc5 = BUG**（`Intel GPU（集显） · INT8` 重复）／**rc6 = BUG**（两条 label 完全相同）／**rc7 = OK**（`Intel GPU（集显） · INT8` + `Intel NPU · INT8`）／**其余 12 包 = NA**（无 0.6B 档）；**双设备口径稳健**（`GPU.0+NPU` 与 `GPU.0+NPU+GPU.1` 均同）；**zip 级复核同结论**（rc5/rc6/rc7 三个 zip 的 `app_py` 单独抽出真跑，且 **zip ≡ 目录**）；**dev 树 git 史**：`ENGINES_ASR06B` 只在 `4637861` 进过 dev 树且**同一提交即带修复** ⇒ **历史载体只有 rc5/rc6 两个包**；**rc5 为何没抓到** ⇒ 其验收走 `--cli` + 显式 `--engine` ⇒ **绕开 GUI 下拉**，且**磁盘无任何 rc5 GUI 截图** ⇒ GUI 路径从未验收｜**③ 🔴 D2 判据改了三轮才对**（v1 `literal_eval` 读表失败 ⇒ 假阴性；v2 未只筛 asr06b ⇒ 假阳性；v3 定案＝AST 直读 + `__file__` 指向包内真实路径 ⇒ 模型就位成为事实判定）＋**反证组**（AST 定位把 rc7 的 asr06b 分支换成 `if False:` ⇒ OK→BUG）⇒ **判据有鉴别力**｜**④ 新风险：C 盘 100 %、仅剩 17 G** ⇒ 下次打包空间不足（**本轮未删任何文件**）｜**未打包 v2.5、未改生产代码、未改客户包、未通知用户、未调 MiniMax**。
> 🔴 **证据**：`results/app/app425_hist_scan3.json`（15 包 + 71 commit + zip 级 + 反证组）／`app425_hist_impact_final.json`（定界结论）／`_app425_hist_scan3.py`（定案判据，v1/v2 前身亦留档）／`_app426_write_status171.py`。

## §172 巡检（last_ack=APP-098，2026-11-11 02:21:21）｜**无新纠偏**；补做 APP-097 §2-4「`_SEC_PER_CHAR` 实测校准」**回填**（reviewer 明文「用它定」）｜**本条需等 reviewer 复核**

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec172_20261111.md`（4415 B／块 SHA256 `92efe1c19232ce508fe83e208ef7682f9ba7911050aef032fe72871c10f8aab3`）｜**归档件逐字节未动**（write-once）｜**本节正文**已按 APP-052④ 索引化，**结论一字未改**。
> 🔴 **速查**：**无新 reviewer 纠偏**（97 条／最大 APP-097，SHA `36af1620…`／285 671 B，**SHA 零改动**、全程只读未改未提交）｜**回填口径（保守，宁高不低）**：`value = ceil3(max(preset_p50, clone_p50))`，源 `app326_app097_lang_out/tts.json`（复算不手抄）⇒ de .073／fr .070／es .085／pt .080／it .081／ru .083；**zh/en/ja/ko 逐字未动**；守卫阈值**只可能变松**｜**倍率地板未改**（等 reviewer 裁定）｜**新闸门** `assert_sec_per_char_calibrated.py` **27/27 PASS**（含反证 3/3）＋ app109 **34/34 PASS**｜**只改开发树** `tts_engine.py`（95 063 B／`b53e5670…`）⇒ **未碰任何客户包**｜**本轮自踩两个坑**（判据层：① 断言「CRLF 个数不变」是**伪不变量** ⇒ 改成真不变量「无裸 LF」；② `ast` 抽表漏抽 `map_language`/`LANG_MAP` ⇒ 落 except ⇒ 别名全归 en ⇒ 补抽后 27/27）｜**产物** `app427_sec_per_char_calibration.json`／`assert_sec_per_char_calibrated.json`／`_app427_apply_sec_per_char.py`／`_app427_app109_regression.json`／`live_caption/assert_sec_per_char_calibrated.py`｜未打包 v2.5、未通知用户、未调 MiniMax。
## §173 巡检（last_ack=APP-098，2026-11-11 04:07:00）｜**无新纠偏**；修掉 STATUS **头部四处过期／自相矛盾** ＋ 新增「归档指针可核对性」判据（25/25 OK ＋ 3 反证全触发）｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec173_20261111.md`（10 835 B／块 SHA256 `2400cc27b26fba6b6ddb71d1cab64e9151fc8595b65a1369aef839e04a0de4a3`）｜**归档件逐字节未动**（write-once）｜**要点**：修掉头部 **H1–H4**（引用滞后／与 §172 自相矛盾／「历史影响未评估」而 §171 已定界／磁盘数过期）｜新增**「归档指针可核对性」判据**（32 指针 OK 25／FAIL 0／7 条早期行「从未声明 SHA」只记信息；反证 3/3 触发）｜既有闸门复跑全绿（27/27、34/34、0 违规、PASS）｜自踩 3 个判据坑（SHA 归属／「没写 SHA」≠「写了核对不上」／键名带修饰致假阴性）⇒ **教训：判据写完必须先跑反证组**｜**未打包 v2.5、未改生产代码、未改客户包、未通知用户、未调 MiniMax、未占设备**｜**本条需等 reviewer 复核**。

## §174 巡检（last_ack=APP-098，2026-11-11 06:22:30）｜**无新纠偏**；修掉 **2 个 App 侧真缺陷**：**① self_ref 克隆漏「克隆模式」闸门**（§168 ⑤ 实测 78/78 句 clone）＋ **② 开发期 `assert_*.py` 闸门可能随包泄漏**（§173 ⑥ 下一轮必读项）｜**本条需等 reviewer 复核**
> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec174_20261111.md`（10904 B／块 SHA256 `367ba690c97b1bd345970291600cb141f1347b4da723804c9857c59a3b02cb39`）｜**归档件逐字节未动**（write-once）。
> 🔴 **速查**：**无新 reviewer 纠偏**（97 条／最大 APP-097，SHA `36af1620…`／285 671 B，**SHA 零改动**、全程只读未改未提交；`last_ack` 仍是 APP-098）｜**修掉 2 个 App 侧真缺陷**：**① self_ref 克隆漏「克隆模式」闸门**（§168 ⑤ 实测 78/78 句 clone ⇒ 补闸门：GUI `_clone_enabled`／CLI `_want_clone` ⇒ 判据 **8/8 PASS** 含反证 2/2）｜**② `assert_*.py` 可能随包泄漏**（§173 ⑥ 必读项 ⇒ 加 `APP_DEV_ONLY_ASSERT_RE`，`assert_pkg_clean.py` 白名单例外 ⇒ 判据 **13/13 PASS** 含反证 2/2）｜**既有闸门复跑全绿**（27/27、34/34、0 违规、PASS）｜**16 包逐个只读扫描 ⇒ 已交付包零影响**（rc6/rc7 的 `clone_voice.py` 不在包内 ⇒ 该路径死代码）｜**未打包 v2.5、未改客户包、未通知用户、未调 MiniMax、未占设备**｜**本条需等 reviewer 复核**。
> 🔴 **证据**：`results/app/app432_self_ref_clone_gate.json`（8/8）／`results/app/app433_pkg_dev_only_assert_gate.json`（13/13）／`_app432_self_ref_clone_gate.py`／`_app433_pkg_dev_only_assert_gate.py`／`status/archive/STATUS_APP_sec174_20261111.md`（§174 正文全文）。

