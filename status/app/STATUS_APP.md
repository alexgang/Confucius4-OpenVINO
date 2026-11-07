# STATUS_APP

last_ack: APP-081
更新时间: 2026-11-07 17:14:32
当前任务: **§149 执行 APP-081（last_ack=APP-081）｜v2.3 已按「只交付预设音色」打新目录＋新 zip（不动 v2.0/2.1/2.2）；闸门回归 18/0・反证 3/3；建包 14 463→14 460 文件（剔除 9 违规＋新增 6）・18 锚点补丁全通过・洁净度 0 违规；⑥ 验收：zip SHA／干净目录 --check／GUI 100%+150%／CLI（r2 重跑 70 句零段 0）均 PASS，黑名单三态 UNKNOWN（1 项口径歧义待裁定），ASR WER=null 待 reviewer；原始结果文件与产物清单见 §149**
阻塞 / 待用户决定: APP-081 第 2 点已作废旧的「APP-075 未闭环 BLOCKING / 需 Opus 复核 / v2.3 不打包」整段——APP-071/075/079 是克隆修复，APP-080 明文转后续版本、v2.3 不为克隆占设备，与 v2.3 无关。当前节点 = **reviewer 复核 §149 的 ⑥ 全套原始结果文件（自算 zip SHA、抽查 zip 内容、看 100%/150% 截图）⇒ 复核通过后才由 reviewer 通知用户**；本轮不改桌面 .lnk、不通知用户。D5 已按 APP-081 第 3 点裁定取 dev 当前 fp16-w5（xml SHA 见 §149），不再问 reviewer。
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§145 压缩**：§144 正文＋§143 产物表 ⇒ `status/archive/STATUS_APP_sec144_20261107.md` ／ `status/archive/STATUS_APP_sec143_artifacts_20261107.md`｜**§146 压缩**：§145 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec145_20261107.md`｜**§147 压缩（首版 42 844 B 超限被拦，STATUS 未落盘 ⇒ 二次压缩）**：§146 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec146_20261107.md`；§143 正文＋§144/§145 速查行整块逐字归档 ⇒ `status/archive/STATUS_APP_sec143_20261107.md`


## 最近更新
> 🔴 §139 / §140 两条「最近更新」原文（2 行）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261107.md`（块 SHA256 `853a0d85678f895f4b88ee294faaaeabec61ca31c2a3a247958a8f8c442f1c8d`）；速查：§139 APP-073/074 冒烟 7/0＋rev2 最终 SHA `90ae8b9d…`；§140 APP-076/077/078 39/0・26/0＋27/0・28/0＋14/0，APP-075 需等复核。
> 🔴 2026-11-05 及更早的「最近更新」条目（16 行）已**逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261106.md`（块 SHA256 `b14fb9b97026e9eaef29fbd3d8a7bc6277e7d4477000344d61c5693819817d47`）；本节只留 §139 / §140 两条速查。
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

| 指标 | 值 | 来源产物 / 字段 |
|---|---|---|
| **说话人标签覆盖率（修复后）** | **93.48 %**（**43 / 46** 句带标签）⇒ 修复前 **7.23 %**（**×12.9**） | `results/app/app202_app053_coverage_evidence.json` → `after.measured_coverage_pct` / `before.coverage_pct` |
| 覆盖率 vs pyannote 自身（1c 口径） | App 原规则 **89.13 %** ⇒ 差 **4.35 pp**；ASR 参考真值 **95.65 %** ⇒ 差 **2.17 pp**（均 ≤ 5 pp） | `app202…` → `pyannote_offline_1c` / `checks`；1c 来源 `app193_app053_spk_frame_audit.json` |
| **旁路开时墙钟（修复后）** | **300.6 s / 300 s 音频** ⇒ reviewer's 缺陷态 **838.5 s**（**×2.79 提速**） | `app199_app054_ab_evidence.json` → `arms[on].wall_s` |
| **旁路开时最大积压** | **1.2 s** ⇒ reviewer's 缺陷态 **195.1 s**（**×163**） | `app199…` → `arms[on].max_backlog_s` |
| **出字延迟中位（旁路开 vs 关）** | **316 ms vs 331 ms** ⇒ Δ = **−15 ms**（≤ +200 ms ⇒ **不增加延迟**） | `app199…` → `arms[].first_char_latency_ms` |
| 旁路开时 RTF | **0.616**（旁路关 **0.632**）⇒ 旁路**不再拖慢** ASR | `app199…` → `arms[].rtf` |
| 旁路线程化闸门（含 4 条反证） | **11 PASS / 0 FAIL**（T8 用 v1.13 包内**旧产物**跑 ⇒ 正确 FAIL ⇒ 判据非恒真） | `results/app/app197_app054_bypass_nonblocking_evidence.json` → `n_pass` / `n_fail` |
| 段自身区间时间对齐闸门（含 2 条反证） | **7 PASS / 0 FAIL** | `results/app/app196_app053_batching_fix_evidence.json` → `n_pass` / `n_fail` |
| 客户包同步「骨架等价」闸门（含 4 条反证） | **10 PASS / 0 FAIL** | `results/app/app201_pkg_skeleton_evidence.json` → `n_pass` / `n_fail` |
| 快捷方式冷启动闸门（COM 读回 + 3 条反证 + 冷启动 ×2 + 截图） | **13 PASS / 0 FAIL** | `results/app/app192_lnk_coldstart_evidence.json` → `n_pass` / `n_fail` |
| `app195` M8 判据缺陷订正 | 原判据**恒假**（簇号 vs 人工编号无语义对应 ⇒ 0 %）⇒ 改为**最优编号置换** ⇒ **82.61 %**（≥ 60 %）⇒ **不是产品缺陷** | `results/app/app200_app053_m8_criterion_evidence.json` → `criterion_defect` / `checks`（3 PASS / 0 FAIL） |
| GUI 三分区布局验收 | **64 PASS / 0 FAIL** | `results/app/app165_app048_gui_layout_evidence.json` → `n_pass` / `n_fail` |
| 失败态 vs 正常态截图像素差 | **9 492 px**（证明不是同一张图） | `app165_app048_gui_layout_evidence.json` → `diff_pixels_normal_vs_failed` |
| 失败态截图 error 红色像素 | **767 px**（整行变色确实生效） | `app165_app048_gui_layout_evidence.json` → `error_red_pixels_in_failed` |
| 说话人资产同步验收 | **30 PASS / 0 FAIL** | `results/app/app164_app047_spk_resync_evidence.json` → `pass_` / `fail` |
| 克隆纯内存等价性 | **10 PASS / 0 FAIL**；mel `max|Δ|=0.000e+00`；入参逐位相同 | `results/app/app161_app045_clone_inmemory_equivalence.json` → `n_pass` / `n_fail` |
| 克隆 vs 旧落盘路径差 | `max|Δ|=4.101e-05` ⇒ **PCM_16 量化误差，非回归**（内存路径更精确） | `results/app/app161_app045_clone_inmemory_equivalence.json` → 判据②b |
| 内置音色不落用户目录 | **5 PASS / 0 FAIL**；用户目录 8 文件已**移出**（备份可回滚） | `results/app/app162_app045_speakerlib_no_copy.json` → `n_pass` / `n_fail` |
| 版本标识一致闸门 | **18 PASS / 0 FAIL**；BUG 组（修复前副本）**D1~D5 全部命中 FAIL** ⇒ 判据非恒真 | `results/app/app170_version_identity_gate_evidence.json` → `pass` / `fail` / `verdict` |
| 打包流水线 dry-run | §48 闸门 **0 处违规 / PASS** ｜ 内部素材 **0 命中** ｜ **结论 PASS** | `pack_v13.py --dry-run --same-version` 本轮实测输出 |
| MiniMax 回转写 CER（预设 A / 克隆） | **3.0243 %** / **3.0901 %**（ed 46 / 47 · ref 1521 字符） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `cer.cuda_preset/cuda_clone.total_cer_pct` |
| 克隆 − 预设A 的 Δ | **+0.0657 pp**，95% CI **[−0.7961, +0.9302]**（**含 0** ⇒ 未构成明显劣化） | 同上 → `pair_cuda_preset_vs_clone.bootstrap.delta_pp` / `ci_lo_pp` / `ci_hi_pp` |
| 判据非恒真（反证组） | 预设臂整体错位 ⇒ Δ = **−125.2465 pp**，CI **[−140.8994, −112.9758]** ⇒ 必判 FAIL | 同上 → `counterproof.swap_arms_bootstrap` |
| APP-050 启动日志 `EXECUTION_DEVICES` 一行 | `talker=NPU`，`cp_prefill=NPU`，`cp_decode=NPU`，`decoder=NPU`×9 | `results/app/app174d_worker_startup_e2e.json` → `key4_line`（真 worker stdout） |
| 各组件落点（直接调引擎） | **17 个组件全 NPU**；`on_cpu=[]`；`on_unknown=[]` | `results/app/app174c_startup_log_evidence.json` → `actual` / `on_npu` / `on_cpu` / `on_unknown` |
| `EXECUTION_DEVICES` 返回类型（实测） | NPU 档 = **字符串 `'NPU'`**；CPU 档 = **列表 `['CPU']`** ⇒ 旧代码 `list(devs)` 把字符串**逐字符拆开** | `results/app/app174a_exec_devices_type.json` → `probes.NPU.raw_type` / `probes.CPU.raw_type` |
| APP-050 离线单测（含 5 条反证） | **34 PASS / 0 FAIL**；反证组**全部命中** ⇒ 判据非恒真 | `results/app/app174b_exec_devices_unit.py` → `n_pass` / `n_fail` / `counterproof` |

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

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec135_upto_20261105.md`（18 133 B，逐字保留）＋ 本轮追加的 §135–§137 三节原文另见 `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：④ ABBA **10/0** ＋ GUI 臂 **5/0**；② 交付物 **12/0**（`shared/app_listen/v23_clone/`）；3(a) CLI **8/0**；**MiniMVP P0 已修（rc2）**。

### §136 ✅ **APP-068 + APP-069 + APP-070 三条新纠偏的代码侧全部落地 ＋ MiniMVP rc3 已出（设备级 3(a) PASS 9/0）** ｜ **本条已完成（代码 + 部分设备级）**（2026-11-05 11:20）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec136_upto_20261105.md`（12 364 B，逐字保留，含 9 项速查表）＋ `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：APP-069① 根因＝**rc2 的 24 段全零是「落盘算法」假象**（`app267` 6/0）；dump 已修（顺序拼接＋回填 `wav_t0`/`wav_t1`/`peak`/`rms_db`）；内容判据 `app268` **4/0**；APP-068 `app266` **7/0**；APP-069⑤ 5 项清理全落地（含 torch 拆 `backends_torch.py`）；APP-070① **删 IR 清单已出（8 个 / 975.9 MB，一个都没删）**；rc3 **6 843.8 MB / 10 503 文件**；设备级 3(a) **PASS 9/0**（wall 381.86 s / 76 句全成）；APP-069② `--check` 臂 **10/10 零崩溃**。

### §137 ✅ **无新纠偏（70 条 = last_ack APP-070）⇒ 按 APP-046 从 §136 断点续做** ｜ **APP-069⑥ 已完成｜①③④ 需等 reviewer 复核**（2026-11-05 13:37）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec137_20261105.md`（9 705 B，逐字保留，含 14 个产物的字节数／mtime／SHA256 清单）＋ `status/archive/STATUS_APP_sec135_137_infofast_20261105.md`。
> 🔴 **速查**：APP-069⑥ MT INT4 vs INT8 **本条已完成**（46 段／`exact_same_pct=4.35`）；🔴 夹具缺陷**已修**（首跑 `APP273_EXIT=2` ＝ 0 段）；口径差异已说明（reviewer 写 76 段，本机英文定稿 **46**）；APP-069② GUI 臂 **需等 reviewer 复核**（`--check` 10/10 零崩溃 ✅，GUI 有效启动 0/10）；本轮回收 2 个孤儿机器锁（`OpenProcess err=87` 确证死）。

### §138 ✅ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成** ｜ **APP-071 仍未完成（BLOCKING）** ｜ **本条需等 reviewer 复核**（2026-11-05 15:28）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec138_20261105.md`（28 336 B，逐字保留，含 README 全文、全部产物元数据、闸门原始字段）＋ 本轮压缩前的**逐字正文**另见 `status/archive/STATUS_APP_sec138_live_20261105.md`。
> 🔴 **速查**：zip `…_v1.0-rc3_perftest.zip`（5 591 630 138 B／10 474 条目／SHA `dda6f229…2d45f1`）；三闸门全过（黑名单 **6/0**／NOTICE 署名 PASS／`--check` **5/0**）＋ GUI 冒烟 **5/0**；README_perftest.txt 9 155 B 进包；⛔ APP-071 **(a)(b)(c)(d) 全未做** ⇒ v2.3 不打包（续见 §139 ⑨）。

### §139 ✅ **APP-073（解压副本冒烟）＋ APP-074（更正：babelvox 示例音色不许放回）本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-05 18:08）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec139_20261105.md`（逐字保留，含 10 项速查表、全部产物元数据、纪律自检）。
> 🔴 **开工/收尾 `CORRECTIONS_APP.md`（reviewer 独占文件，全程只读、未改、未提交）**：SHA `1dd0bcca…9c42900`／215 258 B／mtime 2026-11-05 16:03:18／**74 条**（APP-001..APP-074）⇒ 开工与收尾**逐字相同**（reviewer 本轮未追加）。
> 🔴 **速查**：**解压副本冒烟 7 PASS / 0 FAIL**（rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色）＋ 内容判据 **PASS**（零段 0）＋ 反证 **PASS**（rc2 旧产物 FAIL/受损 24）｜🔴 **核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**（`--tts-voice` 的 `choices` 只有 `A`/`follow_speaker` ⇒ **传不进 cindy**；`A` → `preset_A.wav`，**在包内**）｜**README 文件数已改正**（10 503 → **10 474**）＋ **zip 已重打（新文件名 ⇒ 不覆盖旧 zip）**：**最终 SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**（`shared/minimvp/…_v1.0-rc3_perftest_rev2.zip`／5 591 630 139 B／10 474 条目）｜**一致性对账**：逐条 CRC32 ⇒ **只 `README_perftest.txt` 1 个不同**，其余 10 473 个逐条未变；旧 zip SHA 逐字未变｜🔴 **APP-074(a)② 已答**：预设 A 在 v1.13/v2.0/v2.1/v2.2/rc3 五个包里 **SHA 全部相同**（来源 **Amphion metis prompt.wav**，NOTICE 署名 Apache-2.0）⇒ **不来自 babelvox 示例 ⇒ v2.x 不违规**｜⛔ **APP-071 仍未完成（BLOCKING，放 rc4）**：本轮未动，上一会话的 `app283_app071_diag/` 一字未动 ⇒ **v2.3 不打包**。


### §140 ✅ APP-076/077/078 已完成 ｜ 🔴 APP-075 需等 reviewer 复核（2026-11-06 13:59）

> 全文（4 条证据／md5 表／3 旧包清单／8 音色与 r2 顶层文件**完整 SHA256**／日志原文／口径订正）**逐字归档** ⇒ `status/archive/STATUS_APP_sec140_20261106.md`；本节仅速查。
> 🔴 `CORRECTIONS_APP.md` 只读未改：开工 `3f759ebe…7f359`／219 810 B／77 条 ⇒ 收尾 `bbc95c43…d82af`／220 735 B／**78 条**（中途追加 APP-078）；**SHA/字节/条数均变，不声称零改动**。
> 🔴 **APP-075 需等复核**：r2 最终 **54 文件／20 175 499 B**（manifest 自记＝磁盘；`_app309` **18/0** 补齐静默漏拷的 `submit.jsonl`，旧「52／20 160 623 B」为写前口径）；F0 **21/19/6**，19 FAIL 全 `male→female`，S2 已登记仍串女声；真 x-vector 未产出、第 2 臂未跑 ⇒ **v2.3 不打包**。
> 🔴 **APP-076 已完成**：`_app304` **39/0**（5 文件 md5／`ASR_FILES` 4→5／0.6 同源／app193 正则／克隆门槛未放宽）；MiniMVP「不适用」。v2.3 带 5 文件＋`fp16-w5/`。
> 🔴 **APP-077 已完成**：`_app302` **26/0**（3 旧 zip 同值 `bridge_token.txt`，完整清单见归档件 §3；MiniMVP 无 token）＋`pkg_exclude` 两处独立拦；`_app305` **27/0**（版本无关启动器）；**未生成桌面 .lnk**，待 v2.3 接线。
> 🔴 **APP-078 已完成**（13:31 追加）：`_app306` **28/0** —— **目录 ≠ zip**（3 安装目录各 8 音色，3 zip 均 0；完整 SHA 见归档件 §4①）⇒ **改正 §139「v2.x 不违规」：只对 zip 成立**；`assert_pkg_clean.py`＋`_app307` **14/0**；旧包一字节未动。
> 🔴 **纪律**：未打包／未打 zip／只读扫描旧包／未改 .lnk／未动 `v23_clone/`／未在 CPU 跑推理测速／未调 MiniMax／未提交纠偏文件／逐文件 `git add`＋main 普通 push。**没落盘的不写已交付**。

## §141 无新纠偏（last_ack=APP-078）｜§140 证据链自证 48/0 全数落盘（2026-11-06 19:58:30）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec141_142_20261106.md`（§141 全文，逐字保留）。
> 🔴 **速查**：`_app310` **48 PASS / 0 FAIL**（34 条「结果文件＋原始字段」断言／3 条反证全被识破／11 条 STATUS 锚点命中）；`ac61878` 已提交、`origin/main..HEAD=0`；APP-075 停在「需 Opus 复核」⇒ v2.3 不打包。

## §142 无新纠偏（last_ack=APP-078）｜版本纪律与证据落盘静态自证 26/0（2026-11-06 20:55:30）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec141_142_20261106.md`（§142 全文，逐字保留）。
> 🔴 **速查**：`_app312` **26/0**＋反证 **4/4**；3 个旧包 zip 全量 SHA256 与 `DELIVERY_2.x.json` 基准全等；🔴 1 项历史证据 `app048_layout_1920x1080.png` 仓库内未落盘 ⇒ 记「无法判定」，**需 reviewer 确认存放位置**。

> 🔴 §143 正文＋§144/§145 速查行（25 行／10301 B／块 SHA256 `855cd58c552ae6e5a88e5ff9ab232c7ffda9b3745fa586fd0d7f033f3a45928c`）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec143_20261107.md`；速查：APP-079 静态归因 10/0、APP-080 构建期补丁 36/0・反证 8/8、docstring 修正、界面/运行时/旁路/包内容四项；⑤⑥ 停 reviewer 复核、v2.3 未打包。

> 🔴 §146 正文（19 行／4629 B／块 SHA256 `9a68ea495d02b5a2b063254ea07ec97fc98e58ffe12a78e9d8fb1cab0976bb2e`）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec146_20261107.md`；速查：`_app322` 33/0・反证 8/8，dev 18/18 锚点唯一命中、v2.2 包内基底仅 14/18（缺 P03/P04/P05/P08）⇒ v2.3 打新版本须先升级包内 3 份源文件基底再套 18 锚点补丁，v2.3 未打包。

> 🔴 §147 正文（22 行／7516 B／块 SHA256 `cd4ea569b3434e1e6327c1b553825ebecf462e80dc3571e3aae9804c2ef84957`）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec147_20261107.md`；速查：`_app324` 25/0・UNKNOWN 1・反证 12/12，v2.2 包内 asr_spk 仅 3/5、5 s seg IR 只在影子包、D5 两份 xml SHA 不同待 reviewer 裁定；`PKG_INCLUDE_FILES` NOT_WIRED、v2.2 包内基底 14/18、`ext/bridge_token.txt` 仍在；v2.3 未打包。

> 🔴 §148 正文（8534 B／块 SHA256 `41fc4e67eee63d789da263bd6e7be5e3e8f550a39ce1a94db3d0958362dea7de`）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec148_20261107.md`；速查：`_app326` 41 PASS/0 FAIL・反证 9/9，随包闸门仅检出 2/6 类违规（APP-081 第 3 点已修复）。

## §149 执行 APP-081（last_ack=APP-081）｜v2.3 新目录＋新 zip 已打，APP-080 ⑥ 全套验收（2026-11-07 17:14）

- **步骤 1–2 / 开工基线**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工 SHA `d80ad25d1da40…c5dd9a`／**227 215 B**／mtime **2026-11-07 14:51:02**／**81 条**（APP-001..081 连续）；`last_ack: APP-080` ⇒ 大于它的新条目只有 **APP-081**。租约 `acquire app` exit 0（TOKEN `6b12f7d0`，**无 TAKEOVER**）。APP-081 明文撤销线程自加的「不通知不打包」限制（管的是**通知用户**、不是打包），并作废「APP-075 未闭环 ⇒ v2.3 不打包」整段 ⇒ 本轮按用户 11-06 决定开工 v2.3 打包；**本条按第 5 点需等 reviewer 复核**（自算 zip SHA／抽查 zip 内容／看截图后才通知用户）。
- **APP-081 第 2 点**：STATUS 头部 `当前任务`／`阻塞 / 待用户决定` 两行重写为 APP-080/081 进度，旧「APP-075 BLOCKING / 需 Opus 复核 / v2.3 不打包」措辞作废；旧 §N 章节正文一字未改，`last_ack` → **APP-081**。
- **第 3 点 闸门修复（直接改、不等裁定）**：`live_caption/assert_pkg_clean.py` 的 `scan()` 改为由 `v23_preset_only.PKG_EXCLUDE_PATTERNS` 驱动（5 条规则，独立运行时用同款内置兜底），对每个文件 posix 相对路径跑规则；旧 `TOKEN_RE`／`VOICE_RE` 仅保留兼容、不再参与判定。`results/app/_app328_app081_gate_fix_regression.json` → `verdict=PASS`／`n_pass=18`／`n_fail=0`／`counterproof_identified=3/3`／`n_exclude_rules_loaded=5`：§148 的 6 类夹具 **6/6 全部检出**（原先 3 类零检出已翻正）、3 条干净路径 0 误伤；反证 E1（换回旧 2 类闸门）／E2（清空规则）／E3（删后 3 条）全被识破。真实 v2.2 只读扫描 `v22_readonly.n_violations=9`、`bridge_token_sha_unchanged=true` ⇒ 旧包一字节未动。
- **第 4a 接入建包链路**：`pack_v13.py` 新增 `check_v23_pkg_gate()`（打包前闸门③，v2.3 起强制、dry-run 也跑）⇒ 校验 `PKG_INCLUDE_FILES` 2 文件与 dev 逐字节一致、6 类洁净度 0 违规、3 份生产模块 `verify_source=PASS`，正式日志「⇒ 闸门③ PASS」。`results/app/app329_app081_v23_build.py` 先做「骨架等价校验后升级基底」（dev 顶层符号缺失 **0**）把 3 份源文件升到 dev 基底，再套 `v23_preset_only` 的 **18 锚点**（P 11／S 3／W 4）补丁 ⇒ `app329…json` → `n_anchors_total=18`、3/3 `verify_source_ok=true`（§146 的 v2.2 基底仅 14/18 已绕过）。
- **第 4b 新目录／zip／MANIFEST／ACCEPTED**：新建 `Confucius4_LiveCaption_v2.3/`，v2.0/2.1/2.2 目录与旧 zip 一字节未动（`src_unchanged=true`）；`MANIFEST.version` 2.2 → **2.3**，重签 `ACCEPTED.json`（`version=2.3`／30 生产模块／`code_fingerprint=ca687177…`）。完整性闸门 `n_missing=0`／`n_extra=0`：**14 463 → 14 460 文件**（剔除 **9** = `ext/bridge_token.txt` + babelvox 8 示例音色；新增 **6** = 2 随包文件 + 2 spk + 2 个 w5 IR）；体积 **13 693 019 733 B → 13 696 192 881 B（Δ +3 173 148 B）**；`gate_clean_rc=0`、`n_hardlinks=14173`、`elapsed_s=8.8`。`--dry-run` **PASS**（闸门全绿）；包路径写死闸门按既有「一次性历史诊断脚本」白名单口径新增 2 条并写明理由，本轮新脚本改 `pkg_paths` 动态路径。
- **第 4c 说话人旁路去留**：**保留**（用途 = 字幕 S1/S2 标注，APP-080 ③／§143：`caption_render.render_lines(spk_by_seg=...)`、`App._retry_spk_labels()`）⇒ 5 个 ASR spk 文件 + 5 s 静态 seg IR 随包，ASR dev 与影子包 5/5 SHA 全等；体积变化见上（+3 173 148 B 主要由 w5 IR 与 2 个新 spk 文件贡献，剔除 9 个违规文件约 −18 145 B）。**D5 按 APP-081 第 3 点裁定**：取 dev 当前 `qwen3asr_06b/models/pyannote_seg/ov-fp16-w5/` —— `pyannote_seg_3_0_w5.xml` **73 172 B**／SHA `613b6a5e83e7751b…`／mtime 11-05 10:52（**0 处开发路径**，11-05 已做路径脱敏）；影子包旧 xml **73 206 B**／SHA `4e8b69281f4b0214…`／mtime 11-04 17:07（**1 处开发路径**）⇒ 取 dev 版以满足 APP-080 ⑥ 黑名单；两份 `.bin` 全等（2 978 960 B／SHA `a394cfbd0b390959…`）。
- **版本标识（打包前置）**：`_app330_v23_version_identity_fix.json` → `verdict=PASS`：3 处身份行各唯一命中 1 次、写后逐字节复核、行尾 0→0；NOTICE 旧首行是 `MiniMVP v1.0-rc3` 格式导致 `sync_c172` 中止 ⇒ 改 `LiveCaption v2.3 — 第三方组件归属与许可证`（正文许可署名未动）；`app170` 闸门 **PASS 20 / FAIL 0**。`live_caption/release_notes/v2.3_zh.md`／`v2.3_en.md` 已随包插入 README。
- 🔴 **首轮打包 FAIL 与判据自纠（如实记录）**：首轮压缩到 **11 235 945 990 B** 后，`内容一致性校验`（比对 14 320 文件「全部逐字节一致」）仍报 `结论：FAIL` ⇒ 临时 zip 被丢弃、**未产出正式 zip**，旧包与旧 zip 一字节未动。根因是打包后「包内本地模块导入完整性」把 3 处 `import tts_cuda` 判成「确定缺失」；而 `app/tts_cuda.py`／`tts_cuda_sidecar.py` 在 `pkg_exclude.INTERNAL_EXACT` 里按 **APP-062③（D3）** 有意排除（CUDA 边车只在开发树保留），3 处全是 `try/except` 条件导入（`tts_worker.py` 明写「本包不提供 CUDA 后端模块」）⇒ **判据缺陷、非产品缺陷**。修法：`pack_v13.py` 把 `INTERNAL_EXACT` 里的 `app/*.py` 归为 `by_design_absent` 从 `certain` 剔除并单独打印「按设计不带」（判据对其余模块照常生效），另修掉 `print('[{"OK" if …}] 全部逐字节一致')` 的 f-string 字面量显示 bug ⇒ 闸门 **0 处违规**、`--dry-run` **PASS** 后重打；重打**未用** `--same-version`（首轮无 zip 可覆盖）。
- **第 4d/5 全套验收**：首轮 `app332_v23_verify_summary.json` → `verdicts={"zip_sha":"PASS","unzip_check":"PASS","blacklist":"FAIL","gui":"PASS","cli":"PARTIAL"}`／`all_pass=false` ⇒ 两项未闭合；**不覆盖首轮结果文件、不静默改判**，另落 `app335/336/337/339` 复算与重跑，逐项原始字段见 `app339_v23_verify_final.json` 的 `items`：
  - **zip SHA／文件数**：`app332_v23_zip_sha.json` `verdict=PASS`／`bytes=11235945990`／`mtime=2026-11-07 15:54:15`／`sha256=4b4a977ab1dba640748e1a7347220089a384a7f7e9e8e6778b61902cbadcbfed`／`n_zip_entries=14320`／`n_files=14320`／`top_level=["Confucius4_LiveCaption_v2.3"]`／`has_babelvox_demo=false`／`has_bridge_token=false`；`DELIVERY_2.3.json` `manifest_version=2.3`／`manifest_files=14319`／`manifest_bytes=13692544504`。当前 zip 与两份记录**三方 SHA 实测全等**（`app339.zip_integrity.three_way_equal=true`）⇒ 打包后一字节未动。
  - **干净目录解压 `--check`**：`app332_v23_unzip_check.json` `verdict=PASS`／`rc=0`／`n_extracted_files=14320`／`n_ok_lines=28`／`n_fail_lines=0`（输出 `app332_v23_unzip_check_output.txt`）。
  - **GUI 100%/150% 截图**：`app332_v23_gui_wrapper.json` `verdict=PASS`／`rc=0`；`app332_v23_gui.json` 两臂 `tts_voices=["A"]`／`clone_texts=[]`／`follow_speaker_texts=[]` ⇒ 无克隆入口、无灰选项；两张 PNG 见产物清单。首轮 15:38 干净目录未解压完曾抛 `NotADirectoryError`（`app332_v23_exception_gui.json` 保留），解压完成后重跑 PASS。
  - **黑名单（三态 `UNKNOWN`）**：首轮 `app332_v23_blacklist.json` `FAIL`／`n_hits_real=33` 口径过宽（把裸目录名与 numba/transformers 自带 `.cu` 计入）；`app335_v23_blacklist_recheck.json` 按原始口径 `FAIL`／`n_real_violations=14`／`counterproof_identified=7/7`；`app336_v23_blacklist_forensics.json` 逐项取证 → `verdict=UNKNOWN`／核心 4 类 `n_hits=0`／`n_cuda_native_binary=0`／`n_app_cuda_backend=0`／`n_third_party_python_shim=13`（openvino/torch 与 scipy array_api_compat 纯 Python shim）／`n_true_leaked_file_reference=0`／`n_rule_literal_self_reference=1`／`counterproof_identified=11/11`。**唯一未决**：随包 `app/v23_preset_only.py` 的 `BLACKLIST_PATTERNS` 正则字面量含 `C:\\Users\\Trekker-PTL`，是否计入「开发路径」属口径歧义 ⇒ 按三态「无法判定」≠「不合格」，**交 reviewer 裁定**；按 APP-081 6／不主动打包／APP-055 不原地改包，本轮不重打包，转后续版本去除用户名。
  - **CLI SPE 前 5 分钟＋配音零段＋RTF/积压**：首轮 `app332_v23_cli.json` `PARTIAL`／`rc=0`／`wall_s=314.5`／`n_tts_jsonl_rows=0`；根因 = 验收夹具**漏传 `--translate zh`**（`--translate` 默认 `off` ⇒ MT 未启用 ⇒ `tts.submit` 从不触发）⇒ **撤回**首轮「零段检查 0 命中」（无配音自然无告警，弱标记恒真）。`app337` 显式 `--translate zh`＋设备 `GPU.0/NPU/NPU`（非 CPU），持锁＋`intact()` 前后复核＋45 s 安静窗口后重跑：`app337_v23_cli_rerun.json` `verdict=PASS`／`rc=0`／`wall_s=361.3`／`n_tts_jsonl_rows=70`／`tts_final_stats={submitted:70,played:70,dropped:0,void_on_close:0,empty_sentences:0,failed:0}`／`zero_segment_check.n_bad_rows=0`（判据 = 逐句 `n_samples>0 / peak>0 / not dropped / not error` **本体特征**）／`n_zero_audio_log_lines=0`／`counterproof_identified=4/4`／`lock_chain_ok=true`／`devices_not_cpu=true`；ASR `RTF(计算) 0.798`、出字延迟中位 544 ms、最大积压 2.3 s、46 段；TTS 首包 0.40 s、积压最大 57.08 s、结尾滞后 47.34 s（NPU 上 MT+TTS 争用，如实记录不调阈值）。**ASR WER=`null`** ⇒ 由 reviewer 用 MiniMax 回转写，本轮不自行调用 MiniMax、不在 CPU 算 WER。
  - **4e 旧 clone 回落 A 实测**：`app337_v23_cli_rerun_output.txt` 第 1 行 `[v23] APP-080：音色残留值 'follow_speaker' 不在 v2.3 交付范围 ⇒ 回落预设 A`，`n_clone_fallback_log_lines=1`；TTS worker 另记「已回落到预设 A（不静默）（原因：no_spk_label）」。
- 🔴 **r1 事故／孤儿锁（如实）**：首次重跑 PID 17220 中途被外部清理，半成品另存 `app337_r1_partial_*` 4 份（55 句遥测／零段 0，但**未跑完 300 s**、无 `RTF(计算)` 与 `最终统计` ⇒ 不作验收结论）；`ctypes OpenProcess` `err==87` 确证死，`app338_orphan_lock_reap.json` `lock_reaped=true`。r2 PID 7396 完整跑完且 `lock=RELEASED`，当前 `MACHINE_LOCK` 已释放。
- 🔴 **已识别缺陷转 reviewer（未自行改包）**：CLI 日志 **46 次** `SpeakerVoiceTable.note_final() got an unexpected keyword argument 'spk_conf'`（`app337.n_spk_conf_signature_errors=46`）⇒ 包内 `asr_spk_window` 与 dev 基底签名不一致；被 `try/except` 吞掉，字幕 46 段与配音 70 句均正常。按 APP-055 禁止原地改客户包、APP-081 6 不自创任务 ⇒ 本轮不修、不重打包，转后续版本。
- **产物清单**：`app339_v23_verify_final.json` 的 `artifacts` **20 项**，逐项含 `bytes`／`mtime`／`sha256`（自指已排除）。关键项：正式 zip **11 235 945 990 B**／mtime **2026-11-07 15:54:15**／SHA `4b4a977a…cbfed`；`app337_v23_cli_rerun.json` **9 174 B**／17:09:26／`1fe951da506d…`；`app337_v23_cli_rerun_tts.jsonl` **85 986 B**／17:09:22／`df1c32661a9b724d…`（70 行逐句遥测）；CLI 日志 **121 144 B**／17:09:23／`1e5b889d580201f6…`；定稿文本 **4 707 B**／17:08:36／`535608ae01e2e59b…`；段表 **4 094 B**／17:09:23／`50b587c2e7e12f7b…`；`app336_v23_blacklist_forensics.json` **7 473 B**／16:21:00／`1add4596459c…`；`app335_v23_blacklist_recheck.json` **9 459 B**／16:06:50／`6a54cc454aad…`。
- **收尾复核（reviewer 独占文件）**：`CORRECTIONS_APP.md` 收尾 SHA `d80ad25d1da40…c5dd9a`／**227 215 B**／mtime **2026-11-07 14:51:02**／**81 条**，与开工基线逐项相同 ⇒ reviewer 本轮**未追加新条目**，可如实写 SHA 零改动；全程只读、未改、未提交。`last_ack` → **APP-081**。
- **本条状态**：**APP-081 第 1–4 点已完成**（含 v2.3 新目录／新 zip／⑥ 全套验收结果文件落盘）；**第 5 点需等 reviewer 复核**（自算 zip SHA、抽查 zip 内容、看 100%/150% 截图、裁定黑名单 1 项口径歧义与 `spk_conf` 缺陷）⇒ 复核通过后才由 reviewer 通知用户。本轮**不通知用户**、不改桌面 .lnk、不重打包、不动 v2.0/2.1/2.2。
