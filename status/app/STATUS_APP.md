# STATUS_APP

last_ack: APP-060
更新时间: 2026-11-01 21:13
当前任务: **§126 ✅ APP-059 + APP-060 已执行完毕**（`last_ack` APP-058 → **APP-060**）—— ① **APP-059**：**口径 A 作废、口径 B（文本对齐）为唯一口径**，召回率 **7/12 = 58.33 %**（误报 0）⇒ 仍 **FAIL、差 1 个点**（**未调阈值、未改参照**）；**README_zh/en 已写明**「实验功能／默认关闭／换人时可能漏标」（v2.1 包内 L92-94 / L111-115）；**更正 §124 两处**（许可证写反 ⇒ 以 NOTICE 为准；「与 v1.13 只差 speaker_assets 注释」不成立 ⇒ 实测 **5 个 py 不同**）；**补齐 `app/MANIFEST.json` SHA 三元组** ＋ 写明 **v1.13.zip（15:02）装的是 14:33 代码 ⇒ 不要再从它安装 v1.13**；**EXT-028 未通过** ＋ **HOWTO 已写**（`shared\ext_listen21\HOWTO.txt`）② **APP-060**：**交付版 = v2.1**（zip 20:38 SHA `835803a7…`），**v2.0 已标 superseded**；桌面 **v2.0.lnk 已由 reviewer 删除**、`app212` 加 **SUPERSEDED 硬闸门**（exit 2）；**本轮未打包**（今后改动只打 v2.2+）
阻塞 / 待用户决定: ① 🔴 **判据④ 召回率仍未达标**：唯一口径 B = **58.33 %（7/12）**，需 ≥ 8/12 ⇒ **差 1 个点**（已记为「已知局限」＋ README 写明；**未换口径、未调阈值、未改参照**；治本在 ASR 侧 ⇒ 需主会话转达）② 🔴 **APP-057 ⑤(b) 仍未做**：EXT-028 **未通过**（EXT `last_ack` 仍 EXT-031、EXT-032 未执行）⇒ 只把**用户操作步骤**准备好（`shared\ext_listen21\HOWTO.txt`），等 EXT 交出实录后由用户手势执行并抽听③ 🔴 **交付 zip 内 README 仍是改前版本**（APP-059 ① 只写进了 v2.1 目录，21:05）⇒ 按 APP-060 ④ 需**另打 v2.2**；**本轮未打包**④ ℹ️ **v2.1 已定为交付版**；v2.0 目录与 zip **保留作历史记录、不再对外**⑤ ℹ️ **v2.1 仍缺用户实听 3 段 1.2–1.3× 配音素材**（`sharedpp_accel_listen\`）＋ reviewer 判定音质/不变调/可懂⑥ ℹ️ **§123 待复核项**（GUI 正式行 `[Sx]` 前缀取不到图 / `app179` B4 空真等）仍在等 reviewer
已压缩: 本文件 39986 B / 276 行（APP-052 ④ 限额 ≤ 40000 B / ≤ 300 行）；**§109–§124 正文＋旧「最近更新」条目＋「已撤回的旧结论」备查块已原样归档**到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（**逐字保留，内容一字未删**；更早的见 `STATUS_APP_sec109_122_upto_20261101.md`）


## 最近更新
- 2026-11-01 21:13 **§126 APP-060 已执行** ⇒ ① **交付版 = v2.1**（zip 20:38 SHA `835803a7…`）⇒ **v2.0 标 superseded**（`DELIVERY_2.0.json` / `DELIVERY_2.1.json`，只追加字段）② 桌面 **v2.0.lnk 已由 reviewer 21:10 删除** ⇒ `app212` 加 **SUPERSEDED 硬闸门**（被取代 ⇒ exit 2、不写 .lnk；已反证）③ **未通知安装 / 未打包**；今后改动只打 v2.2+ ④ **CORRECTIONS_APP.md 本轮中途被追加 APP-060**（⇒ §125 ⑧ 的「零修改」作废）
- 2026-11-01 21:10 **§125 APP-059 已执行** ⇒ ① **口径 A 作废、口径 B 为唯一口径**（7/12 = 58.33 %、误报 0 ⇒ 仍 FAIL、差 1 个点；**未换口径、未调阈值、未改参照**）② **README_zh/en 写明说话人标签局限**（v2.1 包内 L92-94 / L111-115）③ **更正 §124 两处**（许可证写反 / 「只差 speaker_assets 注释」不成立：实测 5 个 py 不同）④ **补齐 `app/MANIFEST.json` SHA 三元组** ＋ 写明 **v1.13.zip 与目录不一致 ⇒ 不要再从它安装**⑤ **EXT-028 未通过** ＋ **HOWTO 已写**（`shared\ext_listen21\HOWTO.txt`）⑥ **未通知安装、未打包**
## 当前有效结论

> 🔴 **每个数字都注明来源产物**；**被推翻的旧结论不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| 客户包目录 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1`（**当前最新**；v2.0 / v1.13 目录仍在，未删除） | `Confucius4_LiveCaption_v2.1/MANIFEST.json` → `version=2.1`（`DELIVERY_2.1.json` → `manifest_version`） |
| 客户包 zip | **v2.1**（**2026-11-01 20:38:13** / **11 233 135 359 B** / **14 317 文件** / SHA256 **`835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`**）⇒ 含 APP-053/054 代码 ＋ **EXT 插件 + 桥接服务** ＋ `ACCEPTED.json`（`pkg_dir` = `<HOME>\Confucius4_LiveCaption_v2.1` ＋ `code_fingerprint` + `binding_gate=app191`）＋ `NOTICE` ＋ `THIRD_PARTY.md` ＋ `README_插件.md` ⇒ **v2.0 首包（17:49 / SHA `8198924f…`）保留不删** | `results/app/DELIVERY_2.1.json` → `sha256` / `bytes` / `mtime`；打包日志 → 「比对 14 317 个文件 / 全部逐字节一致」＋ `testzip()` OK |
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

### §123 ✅ **APP-052 / APP-053 / APP-054 —— 桌面 `.lnk` 坏链修复 ＋ `ACCEPTED` 重签 ＋ 说话人标签覆盖率 7 % → 93.48 % ＋ 旁路线程化止血 ＋ STATUS 压缩** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec123_upto_20261101.md`（逐字保留，内容一字未删）。

### §124 ✅ **APP-055 / APP-056 / APP-057 / APP-058 —— v1.13 还原 ＋ 模块租约 ＋ V2.0→V2.1 交付包 ＋ 说话人覆盖率同段复测** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。

### §125 ✅ **APP-059 —— 口径 B 定为唯一口径 ＋ README 说话人标签局限说明 ＋ 两处表述更正 ＋ MANIFEST SHA 三元组 ＋ EXT-028 状态 ＋ HOWTO** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。
> 开工基线：`CORRECTIONS_APP.md` SHA256 `ccdb7712e893c6d20df0fe09c0e438d2f596410db458c5f5c7debb8654b213f8` / **150 636 B** / mtime **2026-11-01 20:56:19** / **59** 条（APP-001…APP-059）⇒ `last_ack` APP-058 → **APP-059**（reviewer：「开始处理时写 last_ack=APP-059」）。

#### ① APP-059 ①：口径 A 作废，**口径 B（文本对齐）为唯一口径**；召回率仍 **FAIL（差 1 个点）**

* **口径 A 作废**（reviewer 判定为**判据实现缺陷**，不算换口径）：拿 App 的行号（48 行）直接对参照的段号（46 段）**没有做对齐**；且检出点记「新说话人的第一行」、参照记「旧说话人的最后一段」⇒ 两者**系统性差 1 段**。
* **唯一口径 = 口径 B（文本对齐）**。原始字段（源 `results/app/app210_app058_recall_diagnosis_evidence.json` → `method_B_text_aligned`）：
  `n_ref_switches=12`｜`n_meas_switches=7`｜`n_hit=7`｜`recall=0.5833333333333334`（**7/12 = 58.33 %**）｜`n_false_positive=0`｜`false_positives=[]`
  命中明细（参照段号 → 实测行号）：`[[2,2],[22,22],[35,35],[36,36],[38,38],[41,42],[44,44]]`
* **结论**：按 APP-058 标准（需 ≥ 8/12）仍 **FAIL，差 1 个点** ⇒ 已按 reviewer 指示记为「**已知局限**」；**App 侧未为凑满 60 % 调阈值、未改参照**。
* 上限参照：`reference_self_consistency` = `n_ref_label_switches=11` vs `n_manual_switches=12`，`manual_only=[19]` ⇒ **参照自身与人工标注就差 1 处 ⇒ 上限 91.7 %**。
* 治本在 **ASR 侧**（说话人切换判定）⇒ **由主会话转达**；App 侧不自行处理。

#### ② APP-059 ①：README_zh/en 已写明说话人标签局限（v2.1 包内实测）

* `Confucius4_LiveCaption_v2.1/README_zh.md` **L92-94**（原文）：
  ```
  * 字幕上的说话人标签（`S1 / S2 …`）属**实验功能**：旁路**默认关闭**；
    开启后若**换人**（说话人切换）**可能漏标**（内部实测：12 个人工标注的换人点
    只检出 7 个）⇒ 标签仅作参考，**不影响**字幕内容与翻译。
  ```
* `Confucius4_LiveCaption_v2.1/README_en.md` **L111-115**（原文）：
  ```
  * Speaker labels on the subtitles (`S1 / S2 …`) are an **experimental feature**:
    the bypass is **off by default**; once enabled, a **speaker change may be
    missed** (internal measurement: 7 of 12 hand-labelled switch points were
    detected) ⇒ labels are for reference only and do **not** affect the caption
    text or the translation.
  ```
* 落地方式（`results/app/app215_readme_speaker_note.py` ⇒ `results/app/app215_readme_speaker_note_evidence.json`）：**定点替换 + 唯一命中断言 + 包外备份 + 写后逐字节复核**（旧正文操作 delete=0，只许改「许可证那 1 行」＋「插入局限说明」）。

  | 文件 | 改前 | 改后 | 旧正文操作（del/rep/ins） |
  |---|---|---|---|
  | `README_zh.md` | 47 497 B / `1b022c33d04f7eca…` | 47 786 B / `6300285e9d7c51bd…`（mtime 21:05:26） | 0 / 1 / 3 |
  | `README_en.md` | 52 950 B / `42cdd5a146a8fb87…` | 53 291 B / `91cbca2ef1096b41…`（mtime 21:05:37） | 0 / 2 / 5 |
  （全量 SHA256 见 `results/app/app215_readme_speaker_note_evidence.json`）

* **ACCEPTED 绑定未受影响**：只动包根**两个文档文件**，`app/` 生产模块未动 ⇒ 按 `app191` 口径重算指纹（**28 个生产模块**）= `b96b6725944c8d19aa9a4a980dee2ac370c6922a19fe7204abae7270b8a9b421` = `ACCEPTED.json` 的 `code_fingerprint` ⇒ **MATCH**。
* 🔴 **zip 未动**（reviewer：「都不用重打包」）⇒ `Confucius4_LiveCaption_v2.1.zip`（20:38，11 233 135 359 B）内 README 仍是**改前**版本 ⇒ **下一版本号打包时带入**；本轮**未打包**（用户未授权打包）。

#### ③ APP-059 ②：更正 §124 的两处表述错误

* **(a) 许可证写反了 —— 撤回 §124③④ 的写法**：以包内 `NOTICE` 为准 ⇒ **pyannote/segmentation-3.0 = MIT**（`NOTICE` L47）、**wespeaker = CC BY 4.0**（`NOTICE` L37）；`THIRD_PARTY.md` L65-66 同（reviewer §1 已核实 NOTICE 正确）。
  **顺带发现并订正**：v2.1 包内 `README_zh.md` L89 / `README_en.md` L106-107 **也把两者写反**（与 NOTICE 矛盾）⇒ 本轮已一并订正（见 ② 的 replace 行：zh 1 行 / en 2 行）。
* **(b)「v2.1 与 v1.13 的差异只有 `speaker_assets` 注释」不成立 —— 撤回该说法**：实测 v2.1 与 v1.13 的 `app/` 有 **5 个 py 文件不同**（共同 28 个 py；**只差注释的是 v2.1 与 v2.0**（仅 `speaker_assets.py`））。逐文件 SHA256（截断 16 位）：

  | 文件 | v1.13 目录 | v1.13.zip 内 | v2.0 | v2.1 |
  |---|---|---|---|---|
  | `live_caption_app.py` | `9f37a399b2b375e2` | `b65e311f9a931442` | `b65e311f9a931442` | `b65e311f9a931442` |
  | `speaker_assets.py` | `1576ac8559e1a634` | `17c1f39c945ae2bf` | `17c1f39c945ae2bf` | `a3690e54892f6bdc` |
  | `speaker_tracker.py` | `ecb3bd6b7f094fae` | `5dd215f4ea03e433` | `5dd215f4ea03e433` | `5dd215f4ea03e433` |
  | `tts_cuda.py` | `bfde75221a040643` | `7d0d886d85cb7ca1` | `7d0d886d85cb7ca1` | `7d0d886d85cb7ca1` |
  | `tts_cuda_sidecar.py` | `269d02f319906a6c` | `84110917d44c13a5` | `84110917d44c13a5` | `84110917d44c13a5` |

#### ④ APP-059 ③：补全 APP-055 的 `app/MANIFEST.json` SHA 三元组 ＋ `v1.13.zip` 与目录不一致

* `app207` 的证据 JSON **只列了 6 个文件**，未列 `app/MANIFEST.json`（它在 **17:09:10** 被重写）⇒ 本轮补齐：

  | 项 | SHA256 | 字节 | 依据 / 实测字段 |
  |---|---|---|---|
  | **改前**（= `v1.13.zip` 内那一份） | `dc62caabd5b9a2cf4f518332db96b6b75a68ff3c737a08dc182405139f1c278c` | 23 422 | zip 内条目 `Confucius4_LiveCaption_v1.13/app/MANIFEST.json`（zip 内时间戳 **2026-11-01 14:53:30**）；内容 `files=14191` / `bytes=13687238157`，notes **含（18）（19）** |
  | **改后**（app207 §⑥ 重写后的落盘值） | `24a45d19d3499fd0aeeaa86068b9846fc45df6c086fa33d1de79964389981749` | 22 937 | mtime **2026-11-01 17:09:10**；内容 `files=14212` / `bytes=13689629685`，notes **无（18）（19）** |
  | **还原后**（写后逐字节复核 ⇒ 与「改后」一致） | `24a45d19d3499fd0aeeaa86068b9846fc45df6c086fa33d1de79964389981749` | 22 937 | 本轮磁盘实测仍为此 SHA ⇒ app207 的还原**未被后续改动覆盖** |

* **依据**：app207 §⑥「MANIFEST 改回 06:08 口径（files=14212 / bytes=13689629685 / notes 去掉（18）（19）两条）」＋ 写后复核 payload 重算 `files=14212` / `bytes=13689629685` 与 06:08 记录**完全一致**。
* 🔴 **`v1.13.zip` 与 `v1.13` 目录不一致**：现存 `Confucius4_LiveCaption_v1.13.zip`（mtime **2026-11-01 15:02:24**，**11 232 363 846 B**，SHA256 `a13bee66c602496cbcefaa6df7b823ae10829ecaf61056ea0cf57820f4647db8`，本轮实测 `results/app/app215_v113_zip_hash.json`）装的是 **14:33 的代码**（zip 内 5 个 py 的 SHA = 上表「v1.13.zip 内」列 ⇒ **不是** 06:08 还原态），且 zip 内条目共 **14 192**（MANIFEST 自称 `files=14191`）而目录 payload 为 **14 212** ⇒ **任何人都不要再从这个 zip 安装 v1.13**。**zip 本身不删、不改名**（只读保留）。

#### ⑤ APP-059 ④：EXT-028 状态（一行）＋ `shared\ext_listen\v21\HOWTO.txt`

* **EXT-028 未通过**：EXT 模块 `live_dub_ext/status/CORRECTIONS_EXT.md` 的 **EXT-032（2026-11-01 20:30，BLOCKING）** 写明「EXT-028 只修了代码，没有交实录」，且当时 `shared\ext_listen\` **目录不存在**；EXT 模块 `STATUS_EXT.md` 的 `last_ack` 仍是 **EXT-031** ⇒ **EXT-032 未执行、EXT-028 的验收一项未交** ⇒ **⑤(b) 的前置条件不满足**。
  （采样率根因与 `resolvePcmSampleRate()` 修复已被 reviewer 认可；EXT-032 要求的 ①tabCapture 生产路径实录 ②三份音频逐段对比（互相关/SNR）③静音成因与 `sync_err` p50/p95 ④`ext032_<时间>\` 目录＋逐段译文 README **均未交**。）
* **HOWTO 已写好（≤ 6 步）**：`C:\Users\Trekker-PTL\shared\ext_listen\v21\HOWTO.txt`（**3 418 B**，SHA256 `99d5079fdd478fc0fa137567ebb1864eaaccea5519a490707c1f56cdcbefd17a`，mtime **2026-11-01 21:16:16**，UTF-8 无 BOM / CRLF / 20 行）。全文如下：

```
实时配音桥接（V2.1 候选包）· 用户操作步骤
==================================================================
生成：2026-11-01 21:20（App 模块 · APP-059 ④）｜候选包：C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1
【前置状态（如实告知，动手前先看）】
1) 插件侧前置 EXT-028 **尚未通过**：EXT 模块 2026-11-01 20:30 的 EXT-032 写明「EXT-028 只修了代码，没有交实录」——采样率修复（resolvePcmSampleRate）与 42 项自测已被认可，但修复后的 player 录音、逐段三份音频对比、静音成因分析都还没交。
2) 本步骤只是**准备**：APP-059 ⑤ 要求「⑤(b) 完成并且用户抽听通过之前，不要通知用户安装」⇒ **先不要安装/替换正式环境里的包**；桌面旧的 v2.0 桥接快捷方式已由 reviewer 于 21:10 删除。
3) 实时字幕 App 与桥接服务**不能同时开**（抢同一块显卡）⇒ 做这一步前先把字幕 App 关掉。
【6 步操作】
第 1 步 · 关掉实时字幕 App ⇒ 双击桌面「实时配音桥接服务 v2.1.lnk」（它启动 <包根>\ext\bridge\bridge_launcher.py），等窗口出现 `[bridge] 监听 ws://127.0.0.1:8765（...）` 即为就绪。
第 2 步 · Edge 地址栏打开 edge://extensions ⇒ 右上角开「开发人员模式」⇒ 点「加载解压缩的扩展」（Load unpacked）⇒ 选**这一层**目录：C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1\ext\extension（⚠️ 不要选到 ext\ 目录，也不要选到 extension 里的某个文件）。
第 3 步 · 打开一个**纯英文**语音页面并开始播放（音频必须在这个标签页里播）。推荐素材（60.0 s 英文 SPE，16 kHz 单声道，1 920 044 B）：C:\Users\Trekker-PTL\live_dub_ext\.tmp\ext026_spe_60s.wav（直接用 Edge 打开播放即可；不要放中文影视原声，会串台）。
第 4 步 · 点工具栏的「实时翻译配音」扩展图标 ⇒ 勾上「打开延迟画面播放器窗口」⇒ 点「开始」。这一步**必须你手动点**（浏览器不允许网页自动激活标签页音频）。
第 5 步 · 插件会自动打开 player 页 ⇒ 点「开始捕获」⇒ 状态条出现 capture_mode = tabCapture 即为就绪 ⇒ 跑满 60 s ⇒ 回扩展面板点「停止并收尾」（把最后一句跑完）。
第 6 步 · **录音保存到哪里**：发行版 player 页**没有**「保存」按钮（录音在页内 MediaRecorder：window.startDubRecording() / window.dubRecordingBlob()）⇒ 请**保持 player 标签页开着**并告诉线程「已完成第 6 步」；线程用 Playwright 从该页取出音频，落盘到 C:\Users\Trekker-PTL\shared\ext_listen\v21\ ，并在同目录附 README（每段起止时间 + 对应译文），交 reviewer 回转写与用户抽听。
【出问题怎么办】
* 扩展图标不出现 ⇒ 第 2 步的「开发人员模式」没开，或选错目录（要选 ext\extension 这一层）。
* 桥接提示「检测到实时字幕 App 在运行，拒绝启动」⇒ 关掉字幕 App 再启动桥接。
* player 显示 capture_mode = getDisplayMedia ⇒ 没走扩展图标的「开始」，重做第 4 步。
* 配音延迟大 / 长时间没动静 ⇒ 已知限制（端到端 RTF≈2.05、同步误差超标），照样跑完 60 s，**先不要中断**，否则拿不到完整录音。
* 日志：%LOCALAPPDATA%\LiveDubEXT\bridge.log
```

* 步骤摘要见上方全文（6 步：起桥接 → 加载扩展 → 播英文页 → 点扩展「开始」→ player「开始捕获」跑满 60 s → 保持 player 页开着让线程取录音）。

#### ⑥ APP-059 ⑤：未通知安装 / 未改包 / 未动旧链

* **未通知用户安装**（⑤(b) 完成且用户抽听通过之前）。
* **`start_bridge.cmd` 的「V2.0 发行版」注释未改**（reviewer：留到下一版，不为它重打包）；`README_插件.md` 里的「V2.0 发行版」同理未动。
* **桌面 `实时配音桥接服务 v2.0.lnk` 保留未删**（reviewer 要求，等用户决定）。COM 读回（`results/app/_app215_shortcuts.py` ⇒ `results/app/app215_shortcuts.json`）：
  * `实时配音桥接服务 v2.0.lnk` → 目标 `…\Confucius4_LiveCaption_v2.0\python\pythonw.exe`、工作目录 `…\v2.0\ext\bridge`、2 511 B、SHA256 `416509664e9b4525…`、mtime **2026-11-01 17:56:16**（**存在，未删**）
  * `实时配音桥接服务 v2.1.lnk` → 目标 `…\Confucius4_LiveCaption_v2.1\python\pythonw.exe`、工作目录 `…\v2.1\ext\bridge`、2 511 B、SHA256 `60afd1667573a3e2…`、mtime **2026-11-01 20:42:58**
  * ⇒ 两者**并存**，等用户/reviewer 决定是否清理旧的。（**21:10 reviewer 已删除 v2.0.lnk** ⇒ 见 §126 ②）

#### ⑦ 本轮对仓库的改动（**只有 App 侧**）

* 新增：`results/app/app215_readme_speaker_note.py` ＋ `app215_readme_speaker_note_evidence.json`、`results/app/_app215_shortcuts.py` ＋ `app215_shortcuts.json`、`results/app/app215_v113_zip_hash.json`
* 改：`status/app/STATUS_APP.md`（本节 ＋ 头部 ＋ 归档压缩）
* **客户包 v2.1 内改动（不在仓库）**：`README_zh.md` / `README_en.md` 两个**文档**文件
* **未改**：`status/app/CORRECTIONS_APP.md`（全程只读）、`app/` 生产模块、任何 zip、`start_bridge.cmd`、`live_dub_ext/**`（EXT 模块的文件一个都没碰）

#### ⑧ 收尾复核（`CORRECTIONS_APP.md` 全程只读）

* 开工基线：SHA256 `ccdb7712e893c6d20df0fe09c0e438d2f596410db458c5f5c7debb8654b213f8` / **150 636 B** / mtime **2026-11-01 20:56:19** / 条目 **59**（APP-001…APP-059）
* 🔴 **收尾实测：该文件在本轮中途被 reviewer 追加了新条目**（**不是**「SHA 零改动」）⇒ 收尾值 = SHA256 `4aab04746e9356d552af2455ff7ebe3ae2d195205ef39437c772cfd3d2dadade` / **151 541 B** / **21:09:20** / **60 条（新增 APP-060）** ⇒ 追加内容见 **§126**；**本模块全程只读，未写入**。
* 本轮**未打包**（reviewer：「都不用重打包」；用户未授权打包）⇒ 旧目录与旧 zip **一个都没覆盖、没删除**

#### ⑨ 待 reviewer 复核 / 未达成（不粉饰）

① ⛔ **APP-058 判据④ 召回率仍未达标**：唯一口径 B = **58.33 %（7/12）**，需 ≥ 8/12 ⇒ **差 1 个点** ⇒ 已按 reviewer 指示记为「已知局限」＋ README 写明；**未调阈值、未改参照**；治本在 ASR 侧（请主会话转达）。
② ⛔ **⑤(b) 仍未做**：EXT-028 未通过（EXT-032 未执行）⇒ 本轮只把**用户操作步骤**准备好（HOWTO.txt），等 EXT 侧交出实录后由用户手势执行。
③ ⛔ **v2.1 的 zip 与目录 README 现已不一致**（zip 内为改前版本）⇒ 下一个版本号打包时须带上新 README；**本轮未打包**。
④ ℹ️ **请 reviewer 确认 v2.1 即交付版**（v2.0 首包违反「旧 zip 不覆盖」，v2.0 目录与 zip 已原样保留）。
⑤ ℹ️ **桌面两个桥接快捷方式并存**（v2.0 / v2.1）⇒ 是否清理旧的请用户/reviewer 定。
⑥ ℹ️ **本轮只补证据与表述，未新增功能**；`app/` 生产模块 **0 改动** ⇒ ACCEPTED 绑定不受影响（已重算核验）。

### §126 ✅ **APP-060 —— 交付版定为 v2.1；v2.0 标 superseded；桌面 v2.0.lnk 已由 reviewer 删除（脚本加硬闸门）；今后改动只打 v2.2+** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节。

#### ① 交付版 = v2.1；v2.0 标 superseded（APP-060 ①）
* 交付物 = `Confucius4_LiveCaption_v2.1.zip`（2026-11-01 20:38，**11 233 135 359 B**，SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`）；**v2.0 目录与 zip 保留作历史记录、不再对外**。
* 已标 superseded（**只追加字段，原字段逐字保留**）：`DELIVERY_2.0.json` → `status="superseded"` / `superseded_by="2.1"` / `superseded_at="2026-11-01T21:13:39"` / `superseded_note`（857 B，SHA256 `a857b6980260849a…`）；`DELIVERY_2.1.json` → `status="delivery"` / `delivery_decided_by="APP-060 ①（用户决定）"` / `supersedes="2.0"` / `known_gap`（见 ④）（1 383 B，SHA256 `cc83d69b5a360c5f…`）；STATUS 头部同步改写。

#### ② 桌面 v2.0.lnk 已删；**任何脚本都不得再生成**（APP-060 ②）
* 实测（21:13）桌面只剩 `Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`（均 mtime 20:42:58）⇒ **`实时配音桥接服务 v2.0.lnk` 已不在**（reviewer 21:10 删除）。
* 全仓库**只有** `results/app/app212_app057_v20_shortcuts.py` 会生成桌面 `.lnk`（`app192` 的坏链只写临时目录；其余 `_*.py` 是只读探测）；它**版本号从包目录名派生**（`ver = pkg_version_of(PKG)`）⇒ 本就只生成「目标包那个版本」。
* 🔴 但它 `--pkg` **默认值写死 v2.0** ⇒ 裸跑一次就会**重建 v2.0 的快捷方式** ⇒ 已改：默认改为**交付版 v2.1** ＋ 新增硬闸门 `SUPERSEDED = {'2.0': '2.1'}`（被取代 ⇒ **exit 2、一个 .lnk 都不写**）；docstring 改 raw string（消除 `SyntaxWarning: invalid escape sequence '\p'`）。
* **反证实测**：`.venv\Scripts\python.exe results/app/app212_app057_v20_shortcuts.py --pkg "C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.0"` ⇒ 打印 `[ABORT] 版本 v2.0 已被 v2.1 取代（APP-060 ①）…`、**EXIT=2**；复查桌面**仍只有 v2.1 两个 .lnk**（未误建）。

#### ③ APP-059 三项本轮已做完（APP-060 ③ 复核）
* ① 更正两处说法 ✔（§125 ③）② 补全 MANIFEST 哈希 ✔（§125 ④）③ ≤ 6 步用户操作说明 ✔（§125 ⑤，`shared\ext_listen\v21\HOWTO.txt`）；**插件配音实录仍等 EXT-032 通过**后由用户抽听（EXT 模块 `last_ack` 仍 EXT-031 ⇒ EXT-032 未执行）。

#### ④ 🔴 已知缺口（如实记录）：**交付 zip 内的 README 仍是改前版本**
* APP-059 ① 的「说话人标签局限」段落是在 **21:05** 定点写进 **v2.1 目录**的，而 zip 是 **20:38** 打的 ⇒ zip 内 `README_zh.md` = 47 497 B / `1b022c33d04f7eca…`、`README_en.md` = 52 950 B / `42cdd5a146a8fb87…`（**改前**）；目录里是 47 786 B / `6300285e9d7c51bd…` 与 53 291 B / `91cbca2ef1096b41…`。该改动**早于** APP-060 ④（21:10）⇒ 属规则生效前动作；**此后不再原地改 v2.1 的目录与 zip**。
* 要让**交付 zip** 带上这段说明 ⇒ 需**另打 v2.2**（APP-060 ④）⇒ 本轮**未打包**（未获用户授权）⇒ 已写进 `DELIVERY_2.1.json` 的 `known_gap` 字段。

#### ⑤ 收尾复核（本轮真实值）
* 🔴 **CORRECTIONS_APP.md 在本轮中途被 reviewer 追加了新条目**（**不是**「SHA 零改动」）：开工 SHA256 `ccdb7712e893c6d2…` / 150 636 B / 20:56:19 / 59 条 ⇒ 收尾 SHA256 `4aab04746e9356d552af2455ff7ebe3ae2d195205ef39437c772cfd3d2dadade` / **151 541 B** / **21:09:20** / **60 条（新增 APP-060）** ⇒ **§125 ⑧ 原写的「零修改」作废，以本行为准**；该文件本模块全程**只读**。
* 本轮**未打包**、未改任何 zip；v2.0 / v2.1 的目录与 zip **均未覆盖、未删除**。
