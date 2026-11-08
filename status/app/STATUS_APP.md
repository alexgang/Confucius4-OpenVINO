# STATUS_APP

last_ack: APP-084
更新时间: 2026-11-08 14:33:52
当前任务: **§153 执行 APP-084（last_ack=APP-084）｜APP-084 为 FYI：v2.4 已由 reviewer 构建并交付用户测试，App 无需动作、仅 ack；本轮停在「等用户测完 + reviewer 发起把 claude-clone 合回 main」节点，不打包、不改五处文件、不通知用户**
阻塞 / 待用户决定: **v2.3 已作废（APP-083：不交付／不验收，目录与 zip 保留不动）；v2.4 已由 reviewer 构建并交付用户测试（APP-084：App 不参与打包／验收）｜当前节点＝等用户测完，由 reviewer 发起把 claude-clone 合回 main；APP-082 审计是否对 v2.4 做、以何口径转 reviewer 裁定；本轮不改桌面 .lnk、不通知用户**
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§145 压缩**：§144 正文＋§143 产物表 ⇒ `status/archive/STATUS_APP_sec144_20261107.md` ／ `status/archive/STATUS_APP_sec143_artifacts_20261107.md`｜**§146 压缩**：§145 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec145_20261107.md`｜**§147 压缩（首版 42 844 B 超限被拦，STATUS 未落盘 ⇒ 二次压缩）**：§146 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec146_20261107.md`；§143 正文＋§144/§145 速查行整块逐字归档 ⇒ `status/archive/STATUS_APP_sec143_20261107.md`｜**§150 压缩**：§149 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec149_20261107.md`（块 SHA256 `29784e3e09e787a4c3328e8c3d5559eef5b459a42554a182d0ddd6745567aebe`）｜**§153 压缩**：§152 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec152_20261108.md`（块 SHA256 `3902c3035665e61903397474d0905fe9142d2f0fbb0049d16ca3e83e87b5c9bc`）


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

> 🔴 **本节正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec149_20261107.md`（12416 B／块 SHA256 `29784e3e09e787a4c3328e8c3d5559eef5b459a42554a182d0ddd6745567aebe`；含开工/收尾指纹、4a–4e 全部原始字段、20 项产物清单、r1 事故与 reviewer 待裁定项）。
> 🔴 **速查**：APP-081 **第 1–4 点已完成**（v2.3 新目录／新 zip `4b4a977a…cbfed`／14 320 条目／全套验收结果文件落盘）；**第 5 点需等 reviewer 复核**（自算 zip SHA／抽查 zip 内容／看 100%+150% 截图／裁定黑名单 1 项口径歧义与 `spk_conf` 缺陷）⇒ 复核通过后才由 reviewer 通知用户。

## §150 巡检无新纠偏（last_ack=APP-081）｜APP-081 第 5 点仍停在「需等 reviewer 复核」节点（2026-11-07 17:43:17）

- **步骤 1–3**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，全程只读／未改／未提交）全文 **81 条**（APP-001..APP-081 无缺号），全文最大编号 **81**；`STATUS_APP.md` 头部 `last_ack: APP-081` ⇒ **编号大于 last_ack 的新条目 = 0**（`results/app/app341_app_patrol_20261107.json` → `new_items_after_last_ack=[]`、`verdict=NO_NEW_CORRECTION__STOP_AT_REVIEWER_GATE`），本轮无条目可执行。租约 `acquire app` exit 0（TOKEN `b68c0cf5`，**无 TAKEOVER**）。
- 🔴 **本条需等 reviewer 复核**：APP-081 第 5 点明文「reviewer 将自算 SHA、抽查 zip 内容、看截图后再通知用户」；§149 已把 v2.3 全套验收原始结果文件与 20 项产物清单（逐项 `bytes`／`mtime`／`sha256`）落盘。按任务「若纠偏明确写了需要停下来等 reviewer 复核就做到那一步停止」＋ APP-081 第 6 点「不要再新增『覆盖审计/静态自证』类轮次、本条处理完前不自创其他任务」⇒ **本轮不自行推进、不自创任务、不重跑静态自证**。当前节点仍是 reviewer 复核 §149 后由 reviewer 通知用户；本轮**不通知用户、不改桌面 .lnk、不重打包、不动 v2.0/2.1/2.2 与 v2.3**。
- **证据（结果文件 → 原始字段）**：`results/app/app339_v23_verify_final.json` → `items`（`zip_sha`/`unzip_check`/`gui`/`cli` 均 PASS、`blacklist=UNKNOWN`）／`artifacts` **20 项**；`app332_v23_zip_sha.json` → `sha256=4b4a977a…cbfed`／`bytes=11235945990`／`n_zip_entries=14320`；`app337_v23_cli_rerun.json` → `verdict=PASS`／`tts_final_stats.submitted=70`／`zero_segment_check.n_bad_rows=0`。本轮**未打包、未产出新交付物、未写「已交付」**。
- **半交付／环境巡检（实测字段，见巡检 JSON）**：`git` → `head=4f0e931`／`branch=main`／`ahead=0` ⇒ 上轮 69 文件已普通 push、**无半交付**；`machine_lock.exists=false`；`prior_background_pids` 两条 PID 17220／7396 均由 `ctypes OpenProcess` **`verdict=DEAD_err87`** 确证死 ⇒ 无孤儿锁、无登记 PID。工作区 `n_worktree_changes=644` 且 `corrections_file_modified_in_worktree=true` ⇒ 本轮**逐文件 `git add`**，绝不 `git add -A`、绝不提交纠偏文件、不吞 ASR/MT/TTS 其它模块改动。
- **收尾复核（步骤 4）**：`CORRECTIONS_APP.md` 开工 SHA `d80ad25d1da40…c5dd9a`／**227 215 B**／mtime **2026-11-07 14:51:02**／**81 条**；收尾重取 `close_fingerprint` 与 `open_fingerprint` 逐项相同（`corrections_open_equals_close=PASS`）⇒ reviewer 本轮**未追加新条目**，可如实写 SHA 零改动；全程只读、未改、未提交。
- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：

  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |
  |---|---|---|---|---|---|
  | `status/archive/STATUS_APP_sec149_20261107.md` | §149 正文整块逐字归档（APP-052④ 压缩） | 1 | 2026-11-07 17:43:17 | 12416 | `29784e3e09e787a4c3328e8c3d5559eef5b459a42554a182d0ddd6745567aebe` |
  | `results/app/app341_app_patrol_20261107.json` | 本轮巡检事实记录（指纹／编号／git／锁／PID／14 项自检） | 1 | 2026-11-07 17:43:17 | 4607 | `10427f9e94203afa4e3f82b30d3c78b51234f497d550eb97dc610619ab40ec75` |

- **纪律**：纯 CPU 静态巡检；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push。`last_ack` 保持 **APP-081**（无更大编号可推），「更新时间」取 `Get-Date` 实测 2026-11-07 17:43:17。

> 🔴 §151 正文（3985 B）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec151_20261107.md`（块 SHA256 `d2c36c15a1e75b442c3950b8a8ecf393cd24a0b604a3a88e4eabec39a0dc9250`）；速查：§151 无新纠偏、last_ack=APP-081、停在 APP-081 第 5 点 reviewer 复核节点（该节点已由 §152 撤回）。


> 🔴 §152 正文（7789 B）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec152_20261108.md`（块 SHA256 `3902c3035665e61903397474d0905fe9142d2f0fbb0049d16ca3e83e87b5c9bc`）；速查：§152 执行 APP-082 / APP-083（last_ack=APP-083）、APP-083 作废 v2.3 且 App 暂停打包、停在等 reviewer 交付 v2.4 节点（该节点已由 §153 关闭）。


## §153 执行 APP-084（last_ack=APP-084）｜FYI：v2.4 已由 reviewer 构建并交付用户测试；App 仅 ack，停在「等用户测完 + reviewer 发起合并」节点（2026-11-08 14:33:52）

- **步骤 1–3 编号对账**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，全程只读／未改／未提交）全文 **84 条**（APP-001..APP-084，`missing_numbers=[]`／`duplicate_numbers=[]`／`max_heading_num=84`）；`STATUS_APP.md` 头部原 `last_ack: APP-083` ⇒ **编号大于 last_ack 的新条目 1 条＝APP-084**（`results/app/app344_app_patrol_20261108.json` → `n_new_headings=1`／`new_headings=["APP-084"]`／`status_last_ack_before=APP-083`／`status_last_ack_after=APP-084`）。按编号顺序通读该条全文（标题＋4 条 bullet，含验收数据与停下节点）后执行，逐条结论见下。
- **APP-084 [NORMAL, 2026-11-07 23:15] — 本条已完成（ack，App 无需动作）**：① **包**：`Confucius4_LiveCaption_v2.4\` ＋ `Confucius4_LiveCaption_v2.4.zip`（11,235,954,241 B；pack_v13 全部闸门 PASS、确定缺失 0、逐字节一致 14320/14320），桌面新增 `Confucius4 实时字幕 v2.4.lnk`。本轮只读实测 zip **11 235 954 241 B**／mtime **2026-11-07 23:04:25**（`app344…json` → `v24.zip_bytes`／`v24.zip_mtime`；与纠偏记载字节数一致），目录存在（`v24.dir_exists=true`）；**未做全量 SHA 复算 ⇒ 不写「一字节未动」实测结论**。② **源**：clone_dev 分支 `claude-clone`（main 已合入）：`3a8e45f` 克隆升级、`a3d2137` 懒编译声码器/桶 8-16-32-33/说话人聚类 v2 默认、`98cf8fc` 预设音色不再登记克隆、`92a6492+7e60afb` 构建脚本与 pack 闸门版本化；建包脚本 `results/app/app_v24_build.py` 属 reviewer 领地、本轮零写入；纠偏明载「app/ 全部模块取 dev ⇒ APP-082 的版本错配在 v2.4 已消除」。③ **验收**（同一 SPE Q&A 300 s 片段）：克隆 82/84 句、男声段 22/23 为男声、女声 50/50；预设 84/84；`spk_conf` 报错 0（v2.3 同片段 45）；TTS NPU 冷编译 1209→468 s；结尾滞后 v2.4 150 s vs v2.3 154 s（NPU 吞吐上限，非回归）。🔴 **以上均为 reviewer 报数，本轮未复跑、未复核 ⇒ 记为「reviewer 交付数据」，不写「App 已验收」**。④ **待合并**：「等用户测完再把 claude-clone 合回 main（reviewer 发起）。App 期间不要改这几处文件」⇒ 明确停下节点（`APP-084.stop_at_reviewer=true`）。
- **本轮裁定（ack-only，不自行推进）**：APP-084 标题与正文明写「**App 无需动作，ack 即可**」，叠加 APP-083 第 3 点「App 现在要做的：**什么都不打包**」与 APP-081 第 6 点「不要再新增覆盖审计/静态自证类轮次；本条处理完前不自创其他任务」⇒ 本轮**仅 ack**：不打包／不打新版本目录与 zip／不改客户包与桌面 .lnk／不改 dev 侧克隆五处文件／不通知用户／不新增自证轮次。巡检脚本只做指令要求的开工-收尾指纹复核与元数据采集（`app344…json` → `discipline.*`），**不是**新开覆盖审计。
- 🔴 **APP-082 审计口径交 reviewer 裁定（不自行启动、也不宣称作废）**：APP-083 第 3 点原话「APP-082 的审计**可改为对 v2.4 做（reviewer 交付后再说）**」；现 v2.4 已交付，但最新 APP-084 明确「App 无需动作」，且 reviewer 已报 `spk_conf` 报错 0、版本错配在 v2.4 已消除 ⇒ 本轮**不启动** APP-082 审计（对象改 v2.4 的 md5 逐文件比对＋AST 跨模块关键字签名匹配＋「错配文件数」「签名不匹配调用数」两计数＋下一版 CLI `unexpected keyword`=0），`APP-082.audit_performed_this_round=false`；是否仍需做、以何口径由 reviewer 定，不因「交付已完成」自行推断为触发。v2.3 已作废 ⇒ 不对 v2.3 做任何审计／验收。
- 🔴 **撤回 / 更正旧结论**：§152 的「当前节点＝等 reviewer 构建并交付 v2.4」因 APP-084 交付完成而**关闭**，新节点＝「等用户测完 ＋ reviewer 发起把 claude-clone 合回 main」。`## 当前有效结论 → 交付配置` 表中「v2.1 = 当前交付版 / v2.2 = 候选交付版」为 2026-11-01/02 旧快照，已被 APP-083（v2.3 作废）与 APP-084（v2.4 已交付用户测试）取代 ⇒ **旧表不再作为当前交付口径**，以 §152 / §153 为准；按纪律**不回头改旧章节**，在此新章节写明更正。
- **开工／收尾复核（步骤 4）**：开工 `corrections_open` SHA `b3a1a90037c399d59875494bed8b8a02e899d02e6d5c480cae033b4ebda59b62`／**231064 B**／mtime **2026-11-07 23:10:48**／**84 条**；收尾重取 `corrections_close` 逐项比对（`corrections_open_equals_close`／`reviewer_appended_this_round` 见 `app344…json`）⇒ **如实记录，不预先声称零改动**；全程只读、绝不修改该文件，也未 `git add`（`git.corrections_worktree_status` 仍为 reviewer 自己的 `M`）。
- **半交付／环境巡检（实测字段）**：`git.head=7f0b3fa`／`git.branch=main`／`git.ahead=0` ⇒ 上轮 4 文件已普通 push、**无半交付**；`git.staged_before=[]`；`machine_lock.exists=false`；未占设备、未在 CPU 推理或测速、未调 MiniMax。
- **STATUS 写入（APP-052④）**：写前 **38 999 B／203 行**（限额 ≤40 000 B／≤300 行，余量仅 1 001 B）⇒ 把 §152 正文 **7789 B 整块逐字归档**到 `status/archive/STATUS_APP_sec152_20261108.md`（块 SHA256 `3902c3035665e61903397474d0905fe9142d2f0fbb0049d16ca3e83e87b5c9bc`）并留速查行；头部只改 5 行（last_ack→APP-084、更新时间→`Get-Date` 实测 **2026-11-08 14:33:52**、当前任务、阻塞/待用户决定、已压缩索引追加本轮归档）；旧章节正文逐字未变（归档即逐字保留）。写后 **39654 B／207 行**，写前自检 **10/10 PASS**（反向还原==旧全文・归档件逐字命中・唯一命中断言・章节不减・LF 未破・限额内・产物表 SHA 与磁盘一致）＋临时文件原子替换＋写后磁盘逐字节复核（脚本内断言，失败即回滚）。
- **本轮产物**（文件数／mtime／字节数／SHA256 全部落盘实测）：

  | 产物 | 用途 | 文件数 | mtime | 字节数 | SHA256 |
  |---|---|---|---|---|---|
  | `results/app/app344_app_patrol_20261108.json` | 本轮巡检事实记录（开工/收尾指纹・84 条编号・APP-084 原文与裁定・git・锁・v2.4 元数据・判据与反证・STATUS 写回自检） | 1 | 2026-11-08 14:34:39 | 7884 | `0423d8875fa5c801a447cad94dff76e0b42a7fc687585b31c999ef758896497e` |
  | `results/app/app344_app_patrol_20261108.py` | 巡检取证 + STATUS §153 定点写入脚本 | 1 | 2026-11-08 14:34:28 | 29090 | `9fb036d80a1e0eb512b6a2a796463649e72fd8c286fb16655ba7c4ad429038b9` |
  | `status/archive/STATUS_APP_sec152_20261108.md` | §152 正文整块逐字归档 | 1 | 2026-11-08 14:34:38 | 7789 | `3902c3035665e61903397474d0905fe9142d2f0fbb0049d16ca3e83e87b5c9bc` |

- **纪律**：纯 CPU 静态；未建 `MACHINE_LOCK`、未占设备、未在 CPU 跑推理或测速、未调 MiniMax；未打包／未打 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未提交纠偏文件（逐文件 `git add`）。`last_ack` → **APP-084**，「更新时间」取 `Get-Date` 实测 **2026-11-08 14:33:52**。
- **下一轮必读**：① 停在「等用户测完 ＋ reviewer 发起把 claude-clone 合回 main」节点；② 合并完成／reviewer 新指令前不打包、不通知用户、不自创「覆盖审计/静态自证」轮次、不改 claude-clone 五处文件；③ 若 reviewer 裁定要做 APP-082 审计 ⇒ 对象 **v2.4**（非已作废的 v2.3），产出 json 的「错配文件数」「签名不匹配调用数」＋ CLI `unexpected keyword`=0；④ 若后续需修任何缺陷 ⇒ 打 **v2.5 新目录＋新 zip**，绝不原地改 v2.4（APP-055）；⑤ STATUS 现 39654 B，写 §154 前仍按限额评估压缩；⑥「不主动打包」规则不变。
