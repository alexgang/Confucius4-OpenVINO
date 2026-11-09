# STATUS_APP

last_ack: APP-092
更新时间: 2026-11-10 07:40:54
当前任务: **MiniMVP rc4 已打包**（zip 8.02 GB／SHA256 `f0ebcc72…`，10 480 条逐条 CRC 全对；rc3 两个 zip 逐字未动）＋ **从 zip 解压的干净包** `--check` 显示「Intel NPU · INT8 模型齐全」、`EXECUTION_DEVICES` encoder=NPU／decoder=NPU ⇒ **本条已完成**
阻塞 / 待用户决定: **reviewer 复核 §162**（音色归属匹配率 35 % 是否达标／CER 回转写／过载臂 `--speed 2.0`）｜**未打 v2.5、未通知用户**（APP-087⑦/088④/092④）
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§159 压缩**：§159 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec159_20261109.md`（块 SHA256 `da8241c04798cbf70798b0588f54fd7da8a35e5c4530cfff1eb653f3df9d32db`）｜**§160 压缩**：头部「已压缩」行原文（2012 B）已归档进同一索引 ⇒ 头部只留精简行｜**§161 压缩**：§161 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec161_20261110.md`（块 SHA256 `0636d5145b65f2c142d886f62e529d9cd2e1a1d966035fbee75bed842574a557`）


## 最近更新
> 🔴 2026-11-10 07:41 ｜ **MiniMVP rc4 zip 已出**：`shared/minimvp/Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip`（8 609 378 581 B／SHA256 `f0ebcc72…`）；**10 480 条逐条 CRC32 全对**、缺/多条目 0/0；**rc3 两个 zip SHA 逐字未变**；**从 zip 解压的干净包**（10 480 条／68.29 s）用**包内 python** 跑 `--check` 显示「**Intel NPU · INT8 模型齐全**」、`EXECUTION_DEVICES` encoder=NPU／decoder=NPU；🔴 打包前修掉 README 沿用 rc3 数字（6.7 GB/10 474 ⇒ 实测 10.0 GB/10 480）这一 **APP-073(c) 同类**缺陷。
> 🔴 2026-11-10 ｜ **MiniMVP rc4 已建**：补 `encoder-fp16`／`decoder-npu-int8`／`decoder-npu-int4`（+3.28 GB）⇒ `--check` 显示「**Intel NPU · INT8 模型齐全**」；设备级：EXEC_DEVICES encoder=NPU／decoder=NPU、WER 15.53 %（iGPU 14.55 %，两档直接差 2.56 %）、RTF 0.803（iGPU 0.696）、峰值内存 5 212.6 MB；**包内 0 个预编译 blob** ⇒ 目标机现编；🔴 rc3 曾被硬链接写穿，已用已交付 zip 权威字节**逐字节复原**并复核 PASS。
> 🔴 2026-11-09 12:46:57｜**APP-086② 接线已完成**：口径裁定＝**复用 App 既有的那一份旁路与音色表**（不双旁路）＋策略层只做策略（不登记）＋worker 侧「沿用上一句音色」收窄为「非按句绑定模式」⇒ **无标签句回落预设 A，绝不沿用上一句的克隆音色**；判据 **6/6 PASS ＋ 反证 6/6 识破**（`app360…json`）；回归 **4 PASS/2 FAIL（与 §159 同基线，无新增）**；**未打包／未建 v2.5／未通知用户** ⇒ 停在 APP-086⑤ 等 reviewer 复核。
> 🔴 §139 / §140 两条「最近更新」原文（2 行）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261107.md`（块 SHA256 `853a0d85678f895f4b88ee294faaaeabec61ca31c2a3a247958a8f8c442f1c8d`）；速查：§139 APP-073/074 冒烟 7/0＋rev2 最终 SHA `90ae8b9d…`；§140 APP-076/077/078 39/0・26/0＋27/0・28/0＋14/0，APP-075 需等复核。
> 🔴 2026-11-05 及更早的「最近更新」条目（16 行）已**逐字归档** ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261106.md`（块 SHA256 `b14fb9b97026e9eaef29fbd3d8a7bc6277e7d4477000344d61c5693819817d47`）；本节只留 §139 / §140 两条速查。
> 🔴 2026-11-08 21:52:39｜**APP-085 本条已完成**（验收待 reviewer 复核）：待命期停止巡检脚本＋§章节＋归档＋提交 ⇒ 不建脚本/json、不新增章节、不归档、不 commit/push；纠偏 84→85 条、SHA `b3a1a900…b62`→`1f7dcc28…642` ⇒ **中途追加，不声称零改动**（只读未改未提交）；`app350` 已按验收清除；APP-083/084 停下节点不变。
> 🔴 2026-11-09 2026-11-09 09:24:27｜**APP-086 / APP-087 / APP-088 已 ack，开始按编号执行**（APP-088「ack 要求」）：纠偏 85→**88 条**（新增 3 条 [HIGH] 用户决定），开工 SHA `d66746ed…6c1f`／**242 619 B**／mtime **2026-11-09 09:11:06**；APP-086⑤／APP-087⑦／APP-088④ 顺序＝**先做完 APP-086（合并＋克隆 a–f＋GUI＋验收数字）→ 停下等 reviewer 复核 → 复核通过后才打 v2.5（含 EXT、CUDA 排除）**；APP-083/084「等用户测完」节点由 APP-086 解除；本轮不打包、不通知用户；APP-085 待命期空巡检禁令在有新条目时解除。
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

> 🔴 **顺序遵守 APP-089/090/091/092 的「合并一次跑 → 停下等复核」**：本节**只交移植＋验收数字**；**未打 v2.5、未通知用户**。

### ① 移植落地（开发树 `live_caption/`，9 文件）
| 纠偏 | 落地 |
|---|---|
| **APP-089** ① 去掉 ICL | `tts_cuda_sidecar.py` **不再读 `<ref>.txt`** ⇒ 固定 `xvec_only=True`；`clone_voice.py` 不再写 `.txt` |
| **APP-089** ② 会话开始清空 | 会话开始清**克隆目录**＋`_spk_bind`/`_spk_voices`/策略层缓存（`app378` **5 PASS / 0 FAIL**，含反证组） |
| **APP-089** ③ 三项行为 | `self_ref`（本句音频 ≥1.5 s）＋`xv_reference_ticket`（≥3 s 定稿／≥8 s 升级／最长 10 s）＋`split_by_speaker`（**克隆线程**上编译，**不在接收/ASR 线程**） |
| **APP-090** ②a 不等标签 | `n_label_wait` 计数器（默认 `tts_label_wait_sec=0` ⇒ **恒 0**）⇒ jsonl＋stats 均落盘 |
| **APP-090** ②c 中文语速 | 中文目标 **1.10×–1.50×**（`tts_speed_min_zh`/`tts_speed_max_zh`），其他语言仍 1.0–1.30× |
| **APP-091** ③ 字幕条 | **3 行**：① 定稿译文（主字号）② **定稿原文（小字 0.75×）**③ 实时识别（行为不变） |
| **APP-092** ① ASR/MT 永不跳段 | **无** ASR/MT 级 catch-up 代码（`grep` 0 命中） |
| **APP-092** ② TTS 级跳过过期句 | `tts_late_drop_sec`（默认 **6.0 s**，键名可配）⇒ 逐句记「滞后秒数＋阈值」进 jsonl |

### ② 🔴 本轮修掉的一个**真缺陷**（上一会话 02:02 的改法）
* 上一会话把「目标开播墙钟」从 `t0+已消费源秒` 改成 `t0+已消费源秒/实测速率`；**实测速率极不稳定**（隐含速率 p50 **1.49**、范围 **0.28–13.6**，真值恒为 1.0）⇒ **普通跑（speed=1.0）误跳 19 句**（修正前 3 句）⇒ 直接违反 APP-092 §3(d)。
* 改法：`audio_source` 新增 **构造期已知**的 `pace` 属性（`FileSource.speed`／实时源 1.0）⇒ **无估计噪声 ⇒ 确定性**；`speed=0`（全速跑批）⇒ `pace=0` ⇒ 退回旧口径。
* **修后实测**：dialog3 误跳 **19 → 3**（与修正前基线一致）；`--speed 0.35` 臂 **83/83 全跳过 → 0 句**（口径修复的直接证据）。

### ③ NPU 验收数字（after 臂，一次持锁会话连跑）
素材 `C:\Users\Trekker-PTL\_reviewer_tmp\spktest\`；ASR+MT→GPU.0，TTS→NPU；影子包 `_app_shadow/after/`。
| 素材 | TTS 行 | 有配音 | 只有字幕 | TTS 跳过 | 等标签 | 倍率 min/p50 | 首包 P50/P95 |
|---|---|---|---|---|---|---|---|
| dialog3 | 81 | 78 | 3 | 3 | 0 | 1.1 / 1.1 | 0.5339 / 0.682 |
| dialog3_tight | 78 | 57 | 21 | 21 | 0 | 1.1 / 1.1 | 0.5303 / 0.6621 |
| dialog3_dave | 84 | 54 | 30 | 30 | 0 | 1.1 / 1.1 | 0.5454 / 0.6977 |

* **只有字幕＝TTS 跳过**（APP-092 §2：内容仍完整留在字幕/转写）⇒ **ASR/MT 段数一条不少**。
* **等标签 = 0**（APP-090 §2a「必须是 0」）✅；**倍率 min = 1.10**（APP-091 §2「min 必须 ≥1.10」）✅。
* **音色归属**（`app389`，dialog3）：输出 x-vector 与**本句自己原声**比余弦，严格大于另两人 ⇒ 判「音色最接近本人」：**18/51 = 35.3 %**；**对照（源 vs 源）51/51 = 100.0 %** ⇒ 判据非恒真（源永远 100%）。
  ⚠️ **匹配率 35 % 明显低于对照** ⇒ 克隆音色**离本人原声仍有距离**，**须 reviewer 复核是否达标**（未自行改判据）。
* **换人切段**：dialog3 切 **1** 段（`spk_seg.jsonl` 的 `n_split`）；dialog3_tight 切 **0** 段。
* **克隆目录 `.txt` 数 = 0**（APP-089 §4 结构检查）✅。

### ④ ⛔ 未完成 / 需 reviewer 裁定
* **CER 回转写**：wav＋译文已落盘（`mix.wav` / `subtitles.txt`），**由 reviewer 在本机用 MiniMax 回转写**（本轮**未调 MiniMax**）。
* **过载臂方向修正**：reviewer 原文「`--speed` **调高**」⇒ **调高才是过载**（`speed=S` ⇒ 机器须以 S× 实时产出语音；本机 TTS 有效 RTF≈0.90 ⇒ **S>1.22 才积压**）⇒ 上一轮用 `--speed 0.35` 当过载**方向反了**（它之所以 83/83 全跳，是**旧口径**把 0.35× 消费当 1.0×）⇒ 本轮改用 **`--speed 2.0`** ＋ 0.35 轻负载对照。
* **v2.5 打包**：**未打**（按 APP-089 §5/APP-090 §4/APP-092 §4，须复核通过后才打；EXT 版本以 **APP-092 的 @23aae0b（v0.3.5）** 为准）。
* **未通知用户**（reviewer 明文）。

### ⑤ 产物
* `results/app/app385_app089_accept_runs_after.json`（after 四跑清单）／`app388_app089_scores_after_all.json`（打分）／`app389_app089_voice_margin_after_dialog3.json`（音色归属）／`app375_app089_fixes_static_check.json`（静态闸门 **49 PASS / 0 FAIL**）／`app378_app089_session_reset_check.json`（**5 PASS / 0 FAIL**）／`app391_app089_before_and_overload.json`（before 臂＋过载臂）。

## §163 MiniMVP rc4 打 zip 完成（用户 2026-11-10 指示「打包 rc4 吧」）

### ① 交付物
* **zip**：`C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc4_perftest.zip`
  **8 609 378 581 B（8.018 GB）**｜SHA256 `f0ebcc7272ea26776f6b7bd3cd83ebdc94e5a8bfaa8e5aaeb6f5b16d55ccc4ba`｜打包 192.8 s（7-Zip `-mx=5 -mmt=on`，BELOW_NORMAL 优先级）。
* **rc3 的两个 zip 一字节未动**（SHA 前后逐字相同：`dda6f229…`／`90ae8b9d…`）⇒ **新文件名，不覆盖**（APP-055）。
* 清单口径 **`pkg_exclude`（单一数据源）** ⇒ 与 rc3 zip **同口径**
  （实测 rc3：`pkg_exclude` 10 474 == rc3 zip 条目 10 474 ✔）。

### ② 打包后逐条复核（`app302`）
| 项 | 值 |
|---|---|
| 源文件数 / zip 条目数 | 10 480 / **10 480**（`n_entries_match=true`） |
| 缺条目 / 多条目 | **0 / 0** |
| **逐条 CRC32 不符** | **0 / 10 480**（每个条目都比对了源文件 CRC） |
| 清单里 U+FFFD / 绝对路径 / `.bak` | 0 / 0 / 0 |
| NPU IR 齐全 / iGPU 保留 | 6/6 在 / 2/2 在 |

### ③ 🔴 打包前修掉的一个真实缺陷（APP-073(c) 同类）
rc4 的 README **沿用了 rc3 的**「解压后 约 6.7 GB（10 474 个文件）」⇒ 与实际 **9.967 GB / 10 480 个文件**对不上
⇒ **打进 zip 的说明书本身就是错的**。
⇒ `_app301` 按**实测值**定点改写（7 处，唯一命中断言，写前断链）：
① 磁盘 **约 10.0 GB / 10 480 个文件**（zip 条目口径）② 缓存加 `npu_cache ≈ 0.7 GB` ⇒ **合计留 20 GB 以上**
③ 内存段由「尚未实测峰值内存」改为**实测 5 212.6 MB**（含 OV 编译期）④ CPU 要求**补 Meteor Lake / 100 系列**
⑤ NPU 要求**补「ASR 也可走 NPU」**⑥ 下一版号 rc4→**rc5** ⑦ 本机基准段补实测峰值内存。
⇒ `_app300` 审计确认：README 数字 **== 清单实测**（`readme_matches_actual`）。

### ④ 从 zip 解压出来的干净包验收（`app303`，用户要求 3 的原文）
* 解压到**全新目录** `C:\minimvp_rc4_ziptest\`（先删后建 ⇒ 真干净）→ **68.29 s / 10 480 条**。
* **用包内自带的 python** 跑 `--check`（rc=0）⇒
  `[ OK ] **Intel NPU · INT8  模型齐全**` ／ `[ OK ] Intel NPU · INT4（实验）  模型齐全`。
* **执行设备直证**（`npu_delivery_backend` + `EXECUTION_DEVICES`，**跑在解出来的包里**）：
  `encoder = NPU` ／ `decoder = NPU` ⇒ `verdict=EXEC_ON_NPU_OK`
  （enc 编译 28.2 s／dec 9.7 s；OV 2026.4.1 随包自带；缓存写**独立临时目录** ⇒ 未复用本机 Panther Lake 产物冒充证据）。

### ⑤ 与 §161 的关系
§161 建的是**目录**；本条补的是**zip** ⇒ §161 的「① 交付物」现补齐 zip 一项。
§161 的设备级验收数字（WER 15.53 %／RTF 0.803／峰值 5 212.6 MB／EXEC 双 NPU）**不变**，本条只增加「zip 可用性」这一层。

### ⑥ 未做 / 待确认
* **v2.5（APP-087/088/092）仍未打** ⇒ 仍停在 §162 的「等 reviewer 复核」节点（`last_ack` 保持 **APP-092**）。
* **未通知用户**（reviewer 明文；本条是**用户直接指示**打 rc4 zip，不是 APP 流程里的打包）。
* **纠偏 APP-089…092 的验收数字仍在等 reviewer 复核**（见 §162）。
