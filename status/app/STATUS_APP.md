# STATUS_APP

last_ack: APP-061
更新时间: 2026-11-02 02:00
当前任务: **§127 APP-061 已执行**（`last_ack` = APP-061）：用户实测 v2.1 的 6 个问题（CUDA 无声 / 离线无参考音色 / 卡顿 / 克隆约 10 s 一次 / 男声被女声播出 / 界面不紧凑）⇒ **代码层全部修复**（①④⑤ 上一会话做的 ＋ ③⑥ 本轮做的）⇒ **v2.2 新目录 + 新 zip 已产出**（v2.1 一个字节都没改；桌面快捷方式**未改**）
阻塞 / 待用户决定: 🔴 **D1–D4 仍由 reviewer/用户决定**（旁路窗口时长 / 是否自动开旁路 / 客户包是否保留 CUDA 选项 / NPU 共用是警告还是禁止）⇒ 本轮按「用户决定之前的默认实现」落地；⛔ **设备级实测未做**（①⑤ GUI+SPE 5 分钟复测、③ SPE 5 分钟遥测、③(e) CPU 卸载 A/B）⇒ **未实测的数字不写「已通过」**
已压缩: 本文件 30590 B / 190 行（APP-052 ④ 限额 ≤ 40000 B / ≤ 300 行）；**§109–§124 正文＋旧「最近更新」条目＋「已撤回的旧结论」备查块已原样归档**到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（**逐字保留，内容一字未删**；更早的见 `STATUS_APP_sec109_122_upto_20261101.md`）


## 最近更新
- 2026-11-02 02:00 **§127 APP-061 已执行** ⇒ ①⑤③⑥ 代码层全部修复（`app215` 29 PASS / 0 FAIL；`app220` 39 PASS / 0 FAIL；`app219` 13 PASS / 0 FAIL，v2.1 同口径 **FAIL** ⇒ 判据非恒真）⇒ **v2.2 新目录 + 新 zip**（v2.1 未改一字节；桌面快捷方式未改）⇒ ⛔ 设备级实测与 D1–D4 仍待办
- 2026-11-01 22:23 **§127 APP-061 开工**（`last_ack` APP-060 → **APP-061**）⇒ **BLOCKING**：用户实测 v2.1 的 6 个问题（CUDA 无声／离线无参考音色／卡顿／克隆每 10 s 一次／男声被女声播出／界面不紧凑）⇒ reviewer 已定位根因 ⇒ 在开发版 `live_caption/` 修 ⇒ **打新版本 v2.2**（v2.1 目录与 zip 一个字节都不许改）
- 2026-11-01 21:13 **§126 APP-060 已执行** ⇒ ① **交付版 = v2.1**（zip 20:38 SHA `835803a7…`）⇒ **v2.0 标 superseded**（`DELIVERY_2.0.json` / `DELIVERY_2.1.json`，只追加字段）② 桌面 **v2.0.lnk 已由 reviewer 21:10 删除** ⇒ `app212` 加 **SUPERSEDED 硬闸门**（被取代 ⇒ exit 2、不写 .lnk；已反证）③ **未通知安装 / 未打包**；今后改动只打 v2.2+ ④ **CORRECTIONS_APP.md 本轮中途被追加 APP-060**（⇒ §125 ⑧ 的「零修改」作废）
- 2026-11-01 21:10 **§125 APP-059 已执行** ⇒ ① **口径 A 作废、口径 B 为唯一口径**（7/12 = 58.33 %、误报 0 ⇒ 仍 FAIL、差 1 个点；**未换口径、未调阈值、未改参照**）② **README_zh/en 写明说话人标签局限**（v2.1 包内 L92-94 / L111-115）③ **更正 §124 两处**（许可证写反 / 「只差 speaker_assets 注释」不成立：实测 5 个 py 不同）④ **补齐 `app/MANIFEST.json` SHA 三元组** ＋ 写明 **v1.13.zip 与目录不一致 ⇒ 不要再从它安装**⑤ **EXT-028 未通过** ＋ **HOWTO 已写**（`shared\ext_listen21\HOWTO.txt`）⑥ **未通知安装、未打包**
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

| 编号 | 一句话 | 下一步 |
|---|---|---|
| APP-043 | ASR 说话人接口已交付，APP-039/040 克隆资产可取（真机验收全套） | ✅ 链路与结构已通过（`app186` 总闸门）；🔴 **仍需用户实听 3 段 1.2–1.3× 素材**（`shared/app_accel_listen/`）＋ **reviewer 判定音质 / 不变调 / 可懂** |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | ✅ **已闭合**（§123）：`.lnk` 改为 COM 生成（**2 099 B**），COM 读回 `TargetPath` 指向 v1.13 包内 `Start_LiveCaption.bat`；从 `.lnk` 冷启动 **2 次**均成功 |
| APP-048 | GUI 状态信息按 ASR / 翻译 / 语音输出分区 | ✅ 布局代码在 v1.13 包内（`app185` **64/0**）＋ §123 已清理 markdown 星号与研发术语；🔴 **仍缺一张「运行中」截图** |
| APP-049 | 压缩 STATUS / CORRECTIONS | ✅ 本轮（§123 ④）压缩到 ≤ 40 KB / ≤ 300 行；🔴 需 reviewer 确认归档内容与索引表无误 |
| APP-051 | 重打 v1.13 ＋ APP-043 真机验收 ＋ `ACCEPTED.json` ＋ 桌面快捷方式 | ✅ 三条子项全做完；🔴 **待 reviewer 复核 3 项**（见 §117 ⑤） |
| **APP-052 ①** | 桌面 `.lnk` 是**坏链**（手工拼字节 ⇒ 字段错位 4 字节） | ✅ **本轮已完成**：改用 `WScript.Shell.CreateShortcut` 生成；判据改为 **COM 读回**（`TargetPath` 非空 / 所指文件存在 / 在 v1.13 包内 / `LinkFlags` 含目标定位位）＋ **3 条反证**（手工坏链 / 目标不存在 / 指向包外 **必须判 FAIL**）⇒ `app192` **13 PASS / 0 FAIL**；🔴 待 reviewer 复核 |
| **APP-052 ②** | `ACCEPTED.json` 未绑定重打的 zip；子项口径有缺口 | ✅ **本轮已完成**：`code_fingerprint`（app191 口径）＋ `binding_gate=app191` ＋ **6 个编号子项 ＋ `1b_lnk_shortcut`** ＋ 新 `accepted_at`；zip 的 SHA 记在 `DELIVERY_1.13.json`（**不循环**）；**旧 SHA `6576dabd…` / `3ca36ce3…` 已作废**；🔴 **待 reviewer 复核**（3 个口径缺口：`app175` 旧口径 / `app179` B4 **空真** / APP-048 截图只拍到空闲态） |
| **APP-052 ③** | 包内残留 `results/mt2_acc_outputs/*.json` ＋ notes 仍是「v1.6 修订」＋ docstring 写死开发机用户名 | ✅ **本轮已完成**：`pkg_exclude` 增 `results/mt2_acc_outputs/`（**22 个文件**整目录排除，**不误伤** `results/mt2_accuracy.json/.md`）；`pack_v13.py` 增 **v1.13 修订说明** ＋ 历史段落脱敏；3 个 docstring 改为 `<HOME>` 占位；🔴 **打包闸门实测又抓到 2 类真缺陷**（见 §123 ③⑤） |
| **APP-053** | 说话人切换时字幕显示不同说话人（v1.13 覆盖率 7 % 不达标） | ✅ **本轮已完成（修复 + 验收）**：查因 = **段自身区间口径** + **攒整窗喂音**；修复后 **93.48 %**（43/46）⇒ 与 pyannote 自身差 **2.17–4.35 pp**；`app202` **9 PASS / 0 FAIL**；🔴 **待 reviewer 复核**（① `app195` **M8 恒假判据**已订正为最优编号置换 ⇒ 82.61 %；② **GUI 转写区正式行的 `[Sx]` 前缀仍未取到图** ⇒ 记为未达成） |
| **APP-054** | 说话人旁路**同步阻塞 ASR 主循环**（墙钟 838.5 s / 300 s 音频，最大积压 195.1 s） | ✅ **本轮已完成（止血 + 治本定位 + 验收）**：旁路**默认关闭** ＋ **线程化** ＋ **攒整窗** ＋ **降级不反压**；A/B 实测旁路开 **300.6 s / 积压 1.2 s / 延迟 316 ms** ⇒ 三条判据全 PASS（`app199` **4 PASS / 0 FAIL**）；🔴 **根因在 ASR 侧**（`run_seg_side` 每次调用重编译模型）⇒ 已写 NOTICE **待主会话转达**；🔴 待 reviewer 复核（旁路默认关闭是否认可） |

| **说话人标签覆盖率（同段口径 · 修复后）** | **93.75 %**（45/48 句带标签，**分子分母同一段** Q&A 切片 3291.6–3591.6 s）⇒ 与 app193 参照 95.65 % 相差 **1.90 pp**（≤ 5 pp） | `results/app/app208_app058_spk_retest_evidence.json` → `measured.coverage_pct` / `checks` ② |
| **换人点召回率（APP-058 判据④）** | 口径 A **33.33 %**（4/12 命中、误报 3）／口径 B **58.33 %**（7/12、误报 0）⇒ **均 < 60 % ⇒ 未达标**（参照标注自身与人工标注差 1 处 ⇒ 上限 91.7 %） | `app208…` → `measured.switch_analysis`；`app210_app058_recall_diagnosis_evidence.json` → `method_A_index` / `method_B_text_aligned` |
| **v2.1 内容闸门 / 绑定闸门 / 快捷方式 / 依赖隔离** | `app213` **15/0**（8/8 反证）｜`app191` **18/0**｜`app212` **9/0**｜`app214` **4/0**（reviewer 点名的 5 个开发目录 **0** 命中；扫 6 729 个文件） | `results/app/app213_app057_v21_gates_evidence.json` / `app191_v21_binding_evidence.json` / `app212_app057_v21_shortcuts_evidence.json` / `app214_app057_v21_clean_test_evidence.json` |

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

### §123 ✅ **APP-052 / APP-053 / APP-054 —— 桌面 `.lnk` 坏链修复 ＋ `ACCEPTED` 重签 ＋ 说话人标签覆盖率 7 % → 93.48 % ＋ 旁路线程化止血 ＋ STATUS 压缩** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec123_upto_20261101.md`（逐字保留，内容一字未删）。

### §124 ✅ **APP-055 / APP-056 / APP-057 / APP-058 —— v1.13 还原 ＋ 模块租约 ＋ V2.0→V2.1 交付包 ＋ 说话人覆盖率同段复测** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。

### §125 ✅ **APP-059 —— 口径 B 定为唯一口径 ＋ README 说话人标签局限说明 ＋ 两处表述更正 ＋ MANIFEST SHA 三元组 ＋ EXT-028 状态 ＋ HOWTO** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec126_upto_20261101.md`（逐字保留，内容一字未删）。


### §126 ✅ **APP-060 —— 交付版定为 v2.1；v2.0 标 superseded；桌面 v2.0.lnk 已由 reviewer 删除（脚本加硬闸门）；今后改动只打 v2.2+** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec126_upto_20261101.md`（逐字保留，内容一字未删）。

### §127 ✅ **APP-061 —— 用户实测 v2.1 的 6 个问题（CUDA 无声 / 离线无参考音色 / 卡顿 / 克隆约 10 s 一次 / 男声被女声播出 / 界面不紧凑）：代码层全部修复 ＋ 打 v2.2 交付包** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。
> 🔴 **本轮是「接手上一会话的半成品」**：上一会话（租约 `67f14126`）在 22:21 之后**心跳中断**（22:41 仍有文件落盘）⇒ 本轮按 APP-061 的**断点继续**，**不从头重做**（已完成的 ①②④⑤ 代码改动**保留**，本轮在其上补 ③⑥ ＋ 打包）。

**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ `last_ack` **APP-061**（APP-061 明文要求「开工前先写 last_ack」⇒ 上一会话已写，本轮沿用）。

#### ① ① CUDA 语音无声 ＋ ② 离线「无参考音色」（同一根因，已修）
* 根因（reviewer 定位）：CUDA 分支只缓存 `_preset_ref_path`、**未缓存 `_preset_name`** ⇒ 回落把 `speaker_name` 清空 ⇒ `synth()` 的音色检查成立 ⇒ 每句「没有可用的音色」⇒ **请求根本没送到边车**。
* 改法：`tts_worker.py` 的 CUDA 分支补 `self._preset_name = 'A'`；回落路径在 CUDA 下**只换参考音频、不清空音色名**；音色检查对 `USES_REF_AUDIO` 后端改为查「当前有没有参考音频」（`_has_ref_audio()`）。
* 判据：`results/app/app215_app061_voice_clone_evidence.json` → `n_pass=29` / `n_fail=0`（**含 7 条反证，全部被抓住**）

#### ② ④ 克隆从「每 10 s 一次」改为「换人时才取样」
* 停用旧的 APP-027 定时采集器（`CloneCollector`）⇒ 克隆只走按句绑定（`is_new` 取样首段 ≥1.5 s → 3 s 定稿 → 老说话人复用缓存）。
* GUI 文案去掉「每 30 s」；`_retry_spk_labels` 补登记 `is_new`（CLI 同步路径同修）。
* 判据：同 ① 的 `app215` 证据（`4a_timer_collector_disabled` / `5b_gui_retry_is_new` / `5b_cli_retry_is_new` 全 PASS）。

#### ③ ⑤ 男声被女声播出（已修）
* 三处根因：a. GUI 构造 `TTSService` **漏传 `clone=`**（CLI 传了）⇒ worker `clone_mode=False` ⇒ 每句回落预设 A；b. `_retry_spk_labels` **丢掉 `is_new`** ⇒ 新说话人永不被取样；c. 标签未到时**一律回落预设 A**。
* 改法：a. 补传 `clone=self._clone_enabled`；b. `is_new` 为真时执行 `_spk_pending_embed.append((seg, spk))`；c. **已有克隆音色时沿用上一句**（`keep_last`，日志固定关键词 `spk_pending⇒keep_last`）⇒ 没有克隆音色时才用预设 A。
* 判据：`app215` 证据 → `5c_keep_last_helper` / `5c_synth_calls_keep_last` PASS；反证 M4（M4_5a_mutant_is_caught）/ M5（M5_5b_mutant_is_caught）**均被抓住**。

#### ④ ③ 卡顿（遥测 ＋ 预缓冲 ＋ 倍速封顶 ＋ NPU 提示）
* (a) 逐句遥测新增 `uf_in_sentence` / `uf_in_sentence_ms` / `uf_idle` / `uf_idle_ms` / `uf_total_ms`（**句内 = 听得见的断音**；句间空闲单列）；主进程累计「句内欠载总时长」「句内欠载 = 0 的句数」；GUI 会话日志**每 30 s** 打一行 `asr_rtf / asr_backlog_s / mt_lat_p50 / tts_synth_rtf / uf_in_sentence_ms`。
* (b) 预缓冲公式升级为 **`est_dur × (1 − 1/(r·speed))`**（r = 最近 8 句实测 「合成墙钟 ÷ 音频时长」）；`r·speed ≤ 1` ⇒ 退化为首块即播（0.3 s 底线）；**speed = 1 时与旧公式逐位相同 ⇒ 零回归风险**。
* (c) **倍速动态封顶** `speed ≤ 1/r_recent`（合成跟不上时宁可滞后，不靠加速把环形缓冲抽空；**用户定的 1.30× 上限不变**）；封顶在 `self._last_speed = _sp` **之前**生效 ⇒ 下一句拿到的是实际用掉的倍率。
* (d) MT/ASR 与 TTS 同在 NPU ⇒ 语音区**标黄提示**「NPU 共用，语音可能卡顿」（**只提示、不禁止** ⇒ D4 待决）。
* 判据：`results/app/app220_app061_stutter_evidence.json` → `n_pass=39` / `n_fail=0` / `n_none=0`（**含 5 条反证**：M1 去 speed 因子 / M2 去封顶 / M3 删 uf 字段 / M4 删 30 s 行 / M5 把 warn 改成 error ⇒ **全部被抓住**）
* 行为探针（实测值）：`speed=1.0 ⇒ 预缓冲 0.947 s`、`speed=1.30 ⇒ 1.651 s`；`r=1.31 ⇒ cap=1.0000`（不许加速）、`r=0.50 ⇒ cap=1.3000`（用户上限）、无实测 RTF ⇒ 不封顶。

#### ⑤ ⑥ 界面紧凑（已修）
* 控件压缩到 ≤ 2 行；不常用控件进**可折叠「高级」面板**（默认收起）；三个分区说明行**并进状态栏 tooltip**；字幕字体保持 13 pt；最小宽度 1024。
* **顺带修掉一个真缺陷**：三个分区的说明行被移进**未映射**的「高级」面板 ⇒ Tk 对未映射控件 `winfo_width()` 恒返 **1** ⇒ 说明行拿不到换行宽度 ⇒ `wraplength=0` ⇒ **展开面板时横向溢出**（实测最长 reqwidth = **3 003 px**）⇒ 新增 `_wrap_width()`（容器未布局时**回退到窗口宽**）＋ 展开/收起后重算。
* 判据：`results/app/app219_app061_gui_compact_evidence.json` → `n_pass=13` / `n_fail=0` / `n_none=0`；**字幕区占比 78.88 %（v2.1 同口径 31.5 %）** ⇒ 同一判据在 **v2.1 上 FAIL**（`app219_app061_gui_compact_v21_evidence.json` → `n_pass=7` / `n_fail=2`）⇒ **判据能识破旧版缺陷（非恒真）**。
* 状态栏 **1 行**（三个分区各 21 px）；1024 宽**无控件越界/被裁剪**（判据含反证探针 ⇒ 被抓住）。
* 前后对比截图 4 张：`shared/app_gui_layout/app061_v21_*.png` 与 `app061_v22_*.png`（1280×800 与 1024×800 各 2 张）。

#### ⑥ 交付：v2.2 新目录 ＋ 新 zip（v2.1 一个字节都没改）
* `pack_v13.py` 新增 `--no-shortcut` ⇒ **不动桌面快捷方式**（APP-061：「用户抽听以后才能改桌面快捷方式」）。
* 打包前 `--dry-run` 闸门：**PASS**（包路径写死 0 处违规 / 版本标识一致 PASS / 内部素材 0 命中）⇒ 见 `results/app/_pack_v22_dryrun.log`。
* v2.2 目录由 **v2.1 目录**派生（`results/app/app221_app061_v22_build_evidence.json`）：`models/` ＋ `python/` **硬链接**（零拷贝、只读）、其余**真实复制**；**只定点同步本轮改过的 3 个生产模块**（`live_caption_app.py` / `tts_worker.py` / `tts_service.py`，行尾归一 LF ＋ 写后逐字节复核）⇒ **不整目录覆盖**。
* `ACCEPTED.json` **重签**（按新代码算指纹：`code_fingerprint=fddb2dc6b06d…`，**28 个生产模块**）⇒ 否则 zip 内那一份仍绑旧代码（APP-052 ② 的教训）。
* ✅ **v2.2 zip 已生成**：（**11233149299 B** / SHA256 `ea5c5c850f8836a7edab982611cdd59d…` / mtime `2026-11-02T01:54:03`）
* 🔴 **v2.1 原样保留**：本轮**未改、未覆盖、未删除** v2.1 的目录与 zip；v2.2 是**全新目录 + 全新 zip**（新版本号 ⇒ 不是 `--same-version` 覆盖重打）。

#### ⑦ 收尾复核（`CORRECTIONS_APP.md` 全程只读）
* 开工基线：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**（APP-001…APP-061）。
* 收尾实测（2026-11-02 02:01 现场重算）：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ **与开工基线逐字相同 ⇒ 本轮 reviewer 未追加新条目 ⇒ 「SHA 零改动」在本轮成立**（与 §125/§126 那两轮「中途被追加」的情况**不同**，勿混为一谈）。
* 本模块对 `CORRECTIONS_APP.md` **全程只读、未写入**。

#### ⑧ 待 reviewer 复核 / 未达成（不粉饰）
① ⛔ **①⑤ 的真机复测未做**（需 GUI + SPE 前 5 分钟 + 耳机实听）：判据与代码已就绪，**但本轮未跑设备级复测** ⇒ 「没有可用的音色 0 次」「REQ 数 = 提交句数」「`voice_kind=clone` 占比 ≥ 80 %」这些**数字尚未实测** ⇒ **不能写「已通过」**。
② ⛔ **③ 的 SPE 5 分钟实测未做**（`uf_in_sentence_ms` 总和 ≤ 音频时长 0.5 % / ASR RTF 增量 ≤ +0.10 / 丢句 0 / TTS 首包 P50-P95）⇒ 同上，**未实测**。
③ ⛔ **③(e) CPU 卸载候选的 A/B 未做**（旁路 pyannote/wespeaker、克隆 `speaker_enc`、TTS `tok_decoder`）⇒ 需持机器锁的 ABBA 实测；**「改默认摆放要先报主会话」⇒ 本轮未改任何默认摆放**。
④ ℹ️ **D1–D4 仍待用户/reviewer 决定**（线程不自定）：D1 旁路窗口 10 s 能否缩短；D2 选「跟随说话人」是否自动开旁路；D3 客户包是否保留 TTS=CUDA 选项；D4 MT/TTS 同 NPU 是警告还是禁止。**用户决定之前的默认实现已按 STATUS 头部记录落地**（② 检测不到边车 ⇒ CUDA 置灰并显示原因；⑤d 旁路关时明确提示、不静默退回定时克隆）。
⑤ ℹ️ **桌面快捷方式未改**（`--no-shortcut`）⇒ 用户抽听通过后再由主会话改指 v2.2。
⑥ ℹ️ **v2.1 的 zip 与目录 README 仍不一致**（zip 内是 21:05 改前的版本）⇒ 该缺口**已由 v2.2 带上**（v2.2 继承了目录版本 47 786 B）⇒ v2.1 本身**不再原地改**。

