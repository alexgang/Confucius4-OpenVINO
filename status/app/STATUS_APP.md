# STATUS_APP

last_ack: APP-097
更新时间: 2026-11-10 15:59:16
当前任务: **APP-093 §3 + APP-097 §2 的设备/静态验收已补齐**（§3.3 单会话过载臂・§3.4 before 臂・§3.5 音色归属・§3.6 切段分析・**§3.7 截图 PASS**；APP-097 §2-2 MT・§2-3 TTS・§2-4 时长・§2-5 回归+ja/ko 冒烟・§2-6 模型身份）｜🔴 **本轮定位并修掉一个阻断级真缺陷**：`commit 874924a` 把 `_clone_nearest` **误插进 `App.__init__` 中间** ⇒ **整个 GUI 布局代码被吞进该方法体** ⇒ GUI 一直只是空壳 `tk` 200×200（无标题/无控件/引擎不加载/字幕永不出现）⇒ **dev 树已修**（纯搬移，8 项校验全 PASS）｜**本条需等 reviewer 复核**
阻塞 / 待用户决定: 🔴 **GUI 布局缺陷修复未同步进客户包**（只在 dev 树 + 影子包 `after_fix_tmp`）⇒ **v2.5 未打包、未同步任何客户包目录**（APP-055 须走打新版本号）⇒ **请 reviewer 裁定**：是立刻修还是随 v2.5 一起出｜🔴 **该缺陷的历史影响未评估**（`874924a` 之后的 GUI 类验收都跑在空壳 GUI 上）｜**§3.5 音色归属判据失效已量化**（三人真值 x-vector 两两余弦 0.957–0.972 ⇒ 余弦尺度上不可分）⇒ **未自行换判据**｜**§3.6「切段开/关的 ASR RTF」对照未跑** ⇒ 已列入 gaps 未报数｜**APP-097 §2-4 只报实测 p50、未改 `_SEC_PER_CHAR` 默认值**｜阈值取舍由 reviewer 拿 §3.1/§3.2 数字报主会话请用户决定（**默认值仍 6.0**）｜**未打包 v2.5、未通知用户**
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§166 压缩**：§166 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec166_20261110.md`（块 SHA256 见该节末）｜**§135–§140 压缩**：摘要行整块归档 ⇒ `status/archive/STATUS_APP_sec135_140_summary_20261110.md`（6 442 B／块 SHA256 `12cf171e63e62f99…`）｜**关键数字表压缩**：整表逐字归档 ⇒ `status/archive/STATUS_APP_key_numbers_20261110.md`（5 540 B／块 SHA256 `0b1e0843e6192300…`）


## 最近更新
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

### ① 🔴🔴🔴 本轮最重要的发现：**GUI 布局代码被吞进 `_clone_nearest` ⇒ GUI 一直是空壳**

**现象**（§3.7 反复失败）：
* GUI 起来后 Win32 只枚举到一个 `TkTopLevel 216×239 title='tk'`（Tk **默认**标题/尺寸）⇒ 主窗标题「实时字幕 MiniMVP v1.0」**从未出现**。
* 字幕**永不出现** ⇒ §3.7「截一张有三行字幕的图」在结构上**不可能成功**。
* 探针（`_app331b_gui_probe.py`）5 分钟内始终 `216×239 'tk'`。

**定位过程（三步递进）**：
1. `faulthandler` ⇒ 主线程停在 `tkinter/__init__.py:1505 mainloop` ⇒ 曾误判「GUI 已初始化完毕」。⚠️ **该证据实为误取**（pythonw 的 stdout 为 None ⇒ App 内 `print` 全丢 ⇒ `gui.log` 恒 0 B）。
2. Tk 内部探针（`_app331e_gui_tkprobe.py`，patch `Tk.title`/`Tk.geometry`）⇒ **`Tk.title` 从未被调用**；`root.title()=='tk'`、`wm_geometry=='200x200+234+234'` ⇒ **不是枚举问题，是代码没跑到**。
3. `ast` 精确解析 ⇒ **`App.__init__` 的 ast 范围只有 2205–2292（88 行）**；而 `root.title('实时字幕 MiniMVP v1.0')`（第 2468 行）落在 **`_clone_nearest`（2389–3157）** 体内 ⇒ **`__init__` 被提前截断**。

**根因（git 溯源定案）**：`commit 874924a`（APP-086(2)「clone 策略层接入」）把
`def _clone_nearest(self, seg, spk, sim):` **误插进 `App.__init__` 的中间** ⇒
`__init__` 提前结束 ⇒ **原本属于 `__init__` 的 GUI 布局代码（`root.title` / `root.geometry` /
全部控件构建 / `prewarm_transformers()` / `self.load_engine()`）被吞进 `_clone_nearest` 的方法体**
⇒ **运行时永不执行** ⇒ GUI 永远只有一个空的 `tk` 200×200 窗口。
* 溯源证据：`git log` 逐 commit 跑 ast ⇒ `b1496ba`（`__init__` 2177–2996，**正常**）→ `874924a`（2181–2259，**BROKEN**）⇒ **缺陷由 874924a 引入**。
* 中招范围（实测）：dev 树 `live_caption/live_caption_app.py`、影子包 `after`/`before` **均中招**；`after2`/`after2_pre`/真包 v2.4（`__init__` 2176–2995）**未中招**。
* 被吞代码里用了 `args.tts_voice` ⇒ 在 `_clone_nearest` 里本应是 **NameError**（该方法无 `args` 形参）⇒ 该方法一被调用就会炸。

**修法（`results/app/_app334_fix_gui_init_indent.py`，纯搬移、零内容改写）**：
把 **2407–3157 整块**（原属 `__init__`）搬回 `__init__` 末尾；`_clone_nearest` 只保留它本来的 `try/except`（2397–2406）。
**8 项校验全 PASS**（`results/app/app334_app093_gui_init_indent_fix.json` → `checks`）：
`ast_parse` / `title_owned_by_init` / `init_covers_title_line` / `clone_nearest_small` /
`const_multiset_same`（常量多重集不变）/ `stmt_multiset_same`（语句多重集不变）/ `line_count_same`（行数守恒）/ `eol_preserved`。
* 修后：`App.__init__` = 2205–**3043**；`_clone_nearest` = 3140–**3157**（18 行）。
* dev 树文件：458 919 B（**字节数不变**），SHA256 前 16 = `25b1626cf391417b`。
* 🔴 **本轮未把该修复同步进客户包**（见 ③「未做」）。

### ② APP-093 §3.7 字幕条截图 —— **PASS**（修复后）

| 项 | 值 | 来源产物 / 字段 |
|---|---|---|
| 判定 | **`verdict=PASS`** | `results/app/app331_app093_gui_shot.json` → `verdict` |
| 主窗 | hwnd 1248278 / title「实时字幕 MiniMVP v1.0」/ 1455×1132 px | 同上 → `window` / `png.size` |
| 主窗 png | `results/app/app331_gui_shot/after_fix_tmp/after_fix_tmp_caption.png`（90 095 B） | 同上 → `png.path` / `png.bytes` |
| 主窗三道守卫 | `not_black=true` / `client_height_ge_700=true`（1098 px）/ `content_density_gt_0=true`（0.278057） | 同上 → `guards` |
| **三行字幕条** | hwnd 9047410 / **1638×157** / x=205 y=1034（屏幕下半部） | 同上 → `overlay_window` |
| 字幕条 png | `…/after_fix_tmp_overlay.png`（23 535 B） | 同上 → `overlay_png.path` / `.bytes` |
| 字幕条守卫 | `not_black=true` / `content_density_gt_0=true`（0.129481）/ `wide_bar=true` | 同上 → `overlay_guards` |
| **三行内容（已读图确认）** | ① 青 = 定稿译文「…如寄咖啡。于是，咖啡便成了提醒。没错，你不需要意志力，只需要一个已经存在的触发因素即可。」② 白 = 定稿原文「…es the reminder. Exactly, you don't need willpower, you just need a trigger that already exists.」③ 黄 = 实时识别「That makes sense.」 | 截图人工读图（`overlay_png`） |

* 🔴 **字幕条不能用标题找**：`CaptionOverlay` 是 `tk.Toplevel` + `overrideredirect(True)` ⇒ **Win32 标题继承父窗口标题**（实测与主窗**完全相同**）⇒ 上一版 `find_window('字幕')` 抓到的是**主窗**（hwnd 相同）。⇒ 改用**几何 + 位置**三重判据：宽 ≫ 高（w > 3h）＋ 位于**下半屏**（top ≥ 屏高×0.55）＋ 尺寸下限。
  ⚠️ 中途踩坑：判据原写「贴屏幕底部（bottom ≥ 屏高−40）」⇒ **误杀**（本机屏高 1280，字幕条 bottom=1191，差 89）⇒ 字幕条贴在**工作区**底部而非物理屏底。
* 抓图工具：`results/app/win_capture.py` 的 `capture_hwnd()`（Win32 `PrintWindow` + 三级降级）⇒ **不用** `PIL.ImageGrab`（本机全黑，本项目铁律）。

### ③ APP-093 其余分项 —— 已跑完

* **§3.3 单会话过载臂**（1.0× → 2.0× → 1.0×，同一时间轴）：`results/app/app327b_app093_overload_recompute.json`
  * 修正前 → 修正后：**overload 段 n_rows 1 → 20**、**n_late_drop 0 → 19**；normal 9 → 10（late_drop 1）；recover 49 → 51（late_drop 2）。
  * **恢复用时 = 3.597 s**（阈值 6.0 s，字段 `speed_lag_s`）⇒ **反证组 PASS**（把 `speed_lag_s` 全 +1000 ⇒ 恢复用时变 `None`）。
  * 字幕完整度：`n_subtitle_lines=54` == `n_seg_rows=54` ⇒ `n_sub_n_seg_equal=true`（跳句只丢语音，不影响字幕/转写）。
  * 🔴 **本轮修掉两个分析缺陷**（否则数字会误导）：① `sitecustomize` 的 `__import__` hook **永不触发**（App 以 `__main__` 运行 ⇒ `import live_caption_app` 从不发生）⇒ 改**轮询 `sys.modules['__main__']`**；② `late_drop` 行 `play_wall=None`（22 句）⇒ 只用 `play_wall` 定位会**整体漏掉过载期** ⇒ 改用 `wall_est = t_submit + median(play_wall − t_submit)`（offset std=1.6686 s）。
* **§3.4 before 臂**（静态补算，未重跑设备）：`results/app/app396_app093_before_arm_scores.json` —— tight：synth_rtf_p50 0.8919 / play_lag_p50 16.5585 / speed_lag_p50 13.8845 / end_reason={eos:78} / n_hit_frame_cap=0 / subtitles=35；dave：synth_rtf_p50 0.9634 / play_lag_p50 33.532 / speed_lag_p50 28.88 / end_reason={eos:84} / n_hit_frame_cap=0 / subtitles=55。
* **§3.5 音色归属**（4 组 before/after × dialog3/tight，NPU 设备跑，持锁）：`results/app/app329_app093_voice_attrib.json`
  * 命中率 `match_rate_truth_ref`：before_dialog3 **0.4691**（38/81）｜after_dialog3 **0.3418**（27/79）｜before_tight **0.6026**（47/78）｜after_tight **0.3696**（17/46）。
  * 🔴 **判据可分性极低**：三人**真值参考**两两余弦 = dialog3 组 A-B 0.967428 / A-C 0.971264 / B-C 0.957272；tight 组 A-B 0.968116 / A-C 0.971529 / B-C 0.957555 ⇒ 「取最接近正确说话人」在余弦尺度上**几乎不可分** ⇒ **命中率低不等于 App 缺陷** ⇒ **未自行换判据**，等 reviewer 裁定。
  * **反证组 4/4 PASS**（把真值余弦压到最低 ⇒ 命中数必须下降；实测 `neg_n_match` 全部 = 0 < base）。
* **§3.6 切段分析**（静态，未重跑设备）：`results/app/app328_app093_split_analysis.json` —— tight 35 段 `n_split` 全 0、`spk` 全 S1、ASR RTF 0.723；dave 55 段 `n_split` 全 0 但 `spk`={S1:12, S2:42, None:1}、ASR RTF 0.862。
  * 🔴 根因线索：聚类 `delta_new=0.30` **远低于**三人互余弦（0.957–0.972）⇒ 永远不会新建簇 ⇒ 「切段 0 段」。
  * ⚠️ **gap（已写入 `gaps`）**：「切段开/关的 ASR RTF 对照」**本轮未跑**（需两次设备跑）⇒ **不报数**。

### ④ APP-097 §2 逐语种设备验收 —— 已跑完

| 分项 | 结果 | 来源产物 / 字段 |
|---|---|---|
| §2-2 MT（8 语种 × 20 句 = 160） | **0 空译 / 0 错误 / 输出语种 100 %**；`zh_skipped_rate=1.0`（源=中文、目标=非中文 ⇒ 不跳） | `results/app/_app326_app097_lang_out/mt.json`（122 674 B） |
| §2-3 TTS（8 语种 × 预设/克隆，**240 行全落盘**） | **撞帧上限 0**（双口径：`end_reason` 字段 240 行全 `None`；独立判 `frames_out >= max_new_tokens` ⇒ 0）⇒ 判据**未恒真**（反证组：抬 3 行 `frames_out` ⇒ 计数 0 → 3 ⇒ PASS） | `results/app/app326_tts_post.json` |
| §2-4 时长校准 | 8 语种 `sec_per_char_p50` 与 `src_dur_ratio_p50` 全部落盘（例：zh preset rtf_p50 0.8546 / spc_p50 0.217143 / ratio_p50 1.2987；ru preset rtf_p50 0.809 / spc_p50 0.082645 / ratio_p50 1.4125） | 同上 → `by_lang` |
| §2-5 回归（zh before/after） | `n_tts_rows` 81/81、`n_segments` 54/54、`n_subtitle_lines` 54/54 **逐项一致**；`synth_rtf_p50` 0.9963 → 0.9586（Δ −0.0377）；⚠️ **`n_late_drop` 6 → 5 不一致（如实记录，未声称一致）** | `results/app/app333_app097_regress.json` → `zh_compare` |
| §2-5 ja/ko 冒烟 | 各 5 句，rc=0，**0 空译**；ja rtf_p50 0.8906 / ko 0.8778；`EXECUTION_DEVICES` 全部 NPU（speaker_enc / cp_prefill / cp_decode / talker_bucket / decoder_bucket） | 同上 → `smoke` |
| §2-6 模型身份 | **真包 v2.4 vs 影子包 12/12 模型目录树 SHA 全部一致** ⇒ `all_same=true`；`same_physical_dir=true`（realpath 同一 `…\Confucius4_LiveCaption_v2.4\models`）；MANIFEST `files=14319` / `bytes=13692564165` / `version="2.4"` | `results/app/app332_app097_model_identity.json` → `compare` / `manifest` |

* 🔴 §2-5 的前提已实测：两个影子包 `models` **realpath 相同** ⇒ 模型相同 ⇒ 差异只来自代码（`roots.same_models_dir=true`）。
* 🔴 §2-6 反证组 PASS：把内存里 `tokenizer/added_tokens.json` 的 SHA 换成全 0 ⇒ 树 SHA 由 `488d8442…` 变为 `9fa4917a…` ⇒ 判据能触发。

### ⑤ 🔴 未做 / 停下等 reviewer
* 🔴 **GUI 布局缺陷的修复尚未同步进客户包**：修复只落在 **dev 树**（`live_caption/live_caption_app.py`，SHA `25b1626cf391417b…`）＋ 影子包 `_app_shadow/after_fix_tmp`（§3.7 验证用）⇒ **v2.5 未打包、未同步任何客户包目录**（APP-055：同步必须走**打新版本号**）。
  ⇒ **reviewer 需先裁定**：这个缺陷是**必须立刻修**（GUI 完全不可用）还是**随 v2.5 一起出**；本轮**不自行打包**。
* 🔴 **该缺陷的历史影响未评估**：`874924a`（11-09）之后的**所有 GUI 相关验收**都跑在空壳 GUI 上 ⇒ 凡依赖 GUI 的结论都需复查（本轮 §3.7 是第一个真 GUI 验收）。
* 🔴 **CLI 路径不受影响（已实测）**：`run_cli` 段在 dev 修复版与 `after` 影子包**逐字节相同**（段 SHA `420933deb7d2a15a`，6916–7933 行）⇒ **本节 ③/④ 的全部数字（CLI 跑）仍然有效**。
* **§3.5 判据失效** ⇒ 未自行换判据，等 reviewer 裁定；**§3.6 切段开关的 ASR RTF 对照未跑** ⇒ 不报数；**§2-4 只报实测 p50、未改 `_SEC_PER_CHAR` 默认值**。
* 阈值取舍仍由 reviewer 拿 §3.1/§3.2 数字报主会话请用户决定（**默认值仍 6.0**）。
* **未打包 v2.5、未通知用户**（APP-093/APP-097 明文）。
* ⚠️ **§166 与更早的旧结论本轮未改**（§166 已整块归档到 `status/archive/STATUS_APP_sec166_20261110.md`）。
* 🔴 **`CORRECTIONS_APP.md` 全程只读**：开工基线与收尾复核**完全一致** —— SHA256 `36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2` / 285 671 B / mtime 2026-11-10 11:49:26 / **97 条**（APP-001…APP-097）⇒ **reviewer 本轮中途未追加新条目**。
