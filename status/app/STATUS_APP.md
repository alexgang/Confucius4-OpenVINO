# STATUS_APP

last_ack: APP-078
更新时间: 2026-11-06 20:55:30
当前任务: **§142 无新纠偏（`CORRECTIONS_APP.md` 78 条 = `last_ack: APP-078`）** —— 按 APP-046 ② 不空转，做「版本纪律 + 证据落盘」静态自证（`_app312` **26 PASS / 0 FAIL**、反证 **4/4**、3 个旧包 zip SHA256 实算全等）；🔴 **APP-075 仍停在「需 Opus 复核」节点** ⇒ 按 APP-046 ④ 停止，不自行推进、v2.3 不打包；🔴 1 项历史证据 `app048_layout_1920x1080.png` 仓库内未落盘 ⇒ 记「无法判定」，需 reviewer 确认存放位置
阻塞 / 待用户决定: 🔴🔴 **APP-075 未闭环（BLOCKING）**：r2 已交付但 F0 闸门未通过，`app299` 是 `offline_stat_embed`（统计嵌入，硬判据 cos_S2_S2=0.745841 < cos_S2_S1=0.772995 ⇒ FAIL）⇒ **真 x-vector 需 reviewer 复核**；第 2 臂（preset 对照）因设备作业被会话中断杀死未跑（已用 ctypes err=87 确证 PID 死并回收孤儿锁）→ **按 APP-075「需 Opus 复核」节点停止，不自行判定通过，v2.3 不打包**｜🔴 **v2.3 打包待办**：5 个 ASR 文件＋`models/spk/pyannote_seg_3_0/fp16-w5/`＋`assert_pkg_clean.py` 闸门＋桥接 .lnk 指向 `bridge_bootstrap`（本轮**未打包、未落进任何包**）｜🔴 **reviewer 本轮中途追加 APP-078**：纠偏文件开工 77 条 / SHA `3f759ebe…7f359` ⇒ 收尾 **78 条** / SHA `bbc95c43…d82af`（全程只读未改，**不得声称零改动**）｜旧包 v2.0/v2.1/v2.2 目录与 zip **一字节未动**，受影响清单见 §140，等 reviewer 转告用户｜本轮需 reviewer 复核：r2 F0 表 / APP-074 结论改正 / 3 个旧包清单 / 未打包 ｜**§141 补充**：本轮 `ac61878` 已提交且 `origin/main..HEAD` 为空（无半交付漏项）；APP-075 的 r2 F0 表／APP-074 结论改正／3 旧包 `bridge_token.txt` 清单／本轮未打包 **仍等 reviewer 复核**
已压缩: **§135–§137 的正文均已原样归档**到 `status/archive/STATUS_APP_sec135_upto_20261105.md`（18 133 B）／`STATUS_APP_sec136_upto_20261105.md`（12 364 B）／`STATUS_APP_sec137_20261105.md`（9 705 B）／`STATUS_APP_sec135_137_infofast_20261105.md`（8 585 B）＋ **§138 正文归档**到 `status/archive/STATUS_APP_sec138_20261105.md`（28 336 B）＋ 本轮压缩前的逐字正文另见 `STATUS_APP_sec138_live_20261105.md` ＋ **§139 正文归档**到 `status/archive/STATUS_APP_sec139_20261105.md` ⇒ 本文件内只留**速查行**；限额 ≤ 40000 B / ≤ 300 行（APP-052 ④）｜写后实测见归档件 §3｜**§140 正文归档**到 `status/archive/STATUS_APP_sec140_20261106.md` ｜**§141 本轮压缩**：「最近更新」中 2026-11-05 及更早的条目整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261106.md`（被搬迁块 SHA256 见 `_app311` 证据）


## 最近更新
- 2026-11-05 18:07:58 **§139 已写** ⇒ **APP-073 + APP-074 本条已完成**：**解压副本冒烟 7/0**（rev2 zip 的解压副本：`--check` 5/0／CLI rc=0 wall 87.98 s／log 无 Traceback／**tts.jsonl 非零 wav 17/17**／音色 A 未回落／无 babelvox 示例音色）＋ 内容判据 **PASS**（零段 0）＋ 反证 **PASS**（rc2 旧产物 FAIL/受损 24）｜🔴 **reviewer 的核心疑问已定案：`--tts-voice A` 不依赖被剪掉的 babelvox 示例音色**（`--tts-voice` 的 `choices` 只有 `A`/`follow_speaker` ⇒ **传不进 cindy**；`A` → `preset_A.wav`，**在包内**）｜**README 文件数已改正**（10 503 → **10 474**，唯一命中，写后逐字节复核）｜**zip 已重打（新文件名 ⇒ 不覆盖旧 zip）**：`…_v1.0-rc3_perftest_rev2.zip`（**5 591 630 139 B／10 474 条目／SHA256 `90ae8b9da38eeca6ab9e6a693e9ac6395bdcb678e9377c5a4f655a7c5a06f58f`**）｜**一致性对账**：逐条 CRC32 ⇒ **只 `README_perftest.txt` 1 个不同**，其余 10 473 个逐条未变；旧 zip SHA 逐字未变 ｜🔴 **APP-074(a)② 已答**：预设 A 在 v1.13/v2.0/v2.1/v2.2/rc3 五个包里 **SHA 全部相同**（来源 **Amphion metis prompt.wav**，NOTICE 已署名 Apache-2.0）⇒ **不来自 babelvox 示例 ⇒ v2.x 不违规**｜⛔ **APP-071 仍未完成（BLOCKING）**：本轮未动（reviewer 明文放 rc4）；上一会话的 `app283_app071_diag/` 一字未动
- 2026-11-06 13:59:48 **§140 已写** ⇒ **APP-076/077/078 本条已完成**（39/0｜26/0＋27/0｜28/0＋14/0）、**APP-075 需等 reviewer 复核**（r2 最终 54 文件／20 175 499 B，`_app309` 18/0 补齐 `submit.jsonl`，F0 21/19/6 未通过）；**改正 §139**（目录≠zip）；**reviewer 中途追加 APP-078**（77→78 条，SHA 变化如实记录）；⛔ **v2.3 不打包、旧包一字节未动**
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

- **开工结论：无编号大于 `last_ack` 的新纠偏**（开工读数，非收尾）。`status/app/CORRECTIONS_APP.md` **78 条**（APP-001..APP-078，SHA `bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af`）＝ 头部 `last_ack: APP-078`；按 APP-046 ②「不空转」改做不占设备的证据链自证；按 ④「卡在需 reviewer/用户决定」停止。收尾复核见下方专条。
- **证据链自证**：`results/app/_app310_sec140_evidence_recheck.py` → `results/app/_app310_sec140_evidence_recheck.json`（_app310_sec140_evidence_recheck.json）⇒ **48 PASS / 0 FAIL / verdict=PASS**：34 条「结果文件＋原始字段」断言（`_app302` 26/0、`_app304` 39/0、`_app305` 27/0、`_app306` 28/0、`_app307` 14/0、`_app309` 18/0、`after.n_files=54`／`after.n_bytes=20175499`、`gate` 21/19/6、`_app303` 写前 52／20 160 623 B、`_app295` F0 160/170 Hz、`_app298` 3/0、`app299` `mode=offline_stat_embed`／`verdict=FAIL`）＋ **3 条反证全被识破**（错值／缺字段／错 gate ⇒ 判据非恒真）＋ 11 条 STATUS 文本锚点全部命中；各产物字节数／mtime／SHA256 见 JSON `evidence_files`。⇒ **§140 的报数全部真实落盘，未发现不实结论**。
- **半交付检查**：`git log` ⇒ `ac61878`（§140，41 文件）已提交，`git log origin/main..HEAD` **为空** ⇒ 上一轮无未推送改动；`MACHINE_LOCK` 本轮 `NOT_PRESENT`（未占设备）；工作区另有其它模块大量未提交改动（c0xx 系列／`status/asr/CORRECTIONS_ASR.md`／`status/CORRECTIONS.md` 等）⇒ **一个都没吞**。
- 🔴 **APP-075 本条需等 reviewer 复核**（纠偏原文 L1463「需 Opus 复核：待 r2 交付后」）：r2 已交付（54 文件／20 175 499 B）但 F0 闸门 **21 PASS / 19 FAIL / 6 NONE**，19 个 FAIL 全是 `male→female`；`app299` 仍是 `offline_stat_embed`（统计嵌入，`verdict=FAIL`）⇒ **真 x-vector 余弦矩阵未产出**；第 2 臂 preset 对照未跑；第 1 臂未跑满 300 s ⇒ **本轮不自行判定通过、不往下推进、v2.3 不打包**。待复核清单：r2 F0 表／APP-074 结论改正（目录≠zip）／3 个旧包 `bridge_token.txt` 清单／本轮未打包。
- 🔴 **停止原因（APP-046 ④）**：唯一可继续的实质项（真 x-vector、第 2 臂设备级）落在停止点之后且需占设备；v2.3 打包需用户通知（用户级规则「不通知不打包」）⇒ 本轮 **未打包／未打 zip／未改任何客户安装目录与旧 zip／未改桌面 .lnk／未在 CPU 跑推理测速／未调 MiniMax／未提交 `CORRECTIONS_APP.md`**。旧包 v2.0/v2.1/v2.2 目录与 zip **一字节未动**。
- 🔴 **纠偏文件收尾复核（全程只读、未改、未提交）**：开工 SHA `bbc95c43…d82af`／220735 B／2026-11-06 13:31:54／**78 条** ⇒ 收尾 SHA `bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af`／220735 B／2026-11-06 13:31:54／**78 条**（最大 APP-078）⇒ 一致（reviewer 本轮未追加，可称零改动）；`last_ack` 保持 APP-078。
- **写入纪律**：头部仅 4 行定点改动；「最近更新」旧条目整块逐字归档（块 SHA `b14fb9b97026e9eaef29fbd3d8a7bc6277e7d4477000344d61c5693819817d47`）；末尾仅追加本章节 ⇒ `difflib` 替换块白名单校验旧正文逐字未变；章节数不减、行尾 LF 未破、写后 ≤ 40000 B / ≤ 300 行（见 `_app311_write_status_sec141.json`）。

## §142 无新纠偏（last_ack=APP-078）｜版本纪律与证据落盘静态自证 26/0（2026-11-06 20:55:30）

- **开工结论：无编号大于 `last_ack` 的新纠偏**。`status/app/CORRECTIONS_APP.md` **78 条**（APP-001..APP-078；开工 SHA `bbc95c43…d82af` / **220 735 B** / 2026-11-06 13:31:54）＝ 头部 `last_ack: APP-078`；租约 `acquire app` **exit 0**（TOKEN `6bf382c0`，**无 TAKEOVER**）、`MACHINE_LOCK` 本轮 `NOT_PRESENT`（未占设备）。按 APP-046 ②「不空转」改做不占设备的静态证据自证；按 ④ 卡在「需 reviewer/用户决定」的项一律不自行推进。
- **自证脚本与结果**：`results/app/_app312_sec142_static_recheck.py`（**9 149 B** / 2026-11-06 20:52:55 / SHA256 `dcac15f21753b669b822a5dd6d416cbce4abe78ce12d3f6250fee2bb6633b8a2`）→ `results/app/_app312_sec142_static_recheck.json`（**16 762 B** / 2026-11-06 20:53:23 / SHA256 `2a70cdfb86d70df4ebec0662690e981e065d54cf94f000e30475bc16ca93884c`）⇒ **`verdict=PASS` / `n_pass=26` / `n_fail=0` / `counterproof_identified=4/4`**（原始字段）。四组：A 纠偏基线 + 编号 1..78 连续无重复 + `last_ack=78` 对齐（7 条）；B git 纪律（3 条）；C 证据落盘点验（4 条）；D 3 个旧包 zip 实算（12 条）。🔴 **反证 E1–E4 复用 A5/C2/D-1/A7 的同一判据函数**（`j_ids` / `j_missing` / `j_zip_sha` / `j_ack`），分别注入「全零 SHA / 删掉 APP-040 编号 / 空 unresolved 声明 / `last_ack=77`」⇒ **4/4 全被识破**（`identified=true`）⇒ 判据非恒真。
- **旧包「一字节未动」实算复核**（`_app312` → `zip_audit[].sha256_measured` vs `results/app/DELIVERY_2.x.json` → `sha256` / `bytes` / `mtime`）：**v2.0** `8198924f9aed30010c0fb80f472278f322f160c9b63cbe7861001dbda056eed9` / **11 233 134 015 B** / 2026-11-01 17:49:21；**v2.1** `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4` / **11 233 135 359 B** / 2026-11-01 20:38:13；**v2.2** `ea5c5c850f8836a7edab982611cdd59d0ba0e83f8d5ff880cc797b7c67c23b75` / **11 233 149 299 B** / 2026-11-02 01:54:03 ⇒ **3/3 的 SHA256、字节数、mtime 与基准全等**，`status_anchor_hit=true` 三包皆命中 STATUS 表锚点 ⇒ §141「旧包目录与 zip 一字节未动」首次拿到全量实算支撑。全程只读、未打包、未打 zip、未改任何安装目录。
- **证据文件落盘点验**（`_app312` → `evidence_files[]` 26 项，每项附 `bytes` / `mtime` / `sha256`）：STATUS「当前有效结论」表抽到 **27** 个证据文件 token，`n_found=26`；🔴 **1 个 unresolved**：`app048_layout_1920x1080.png` 在 `results/app/`、`results/`、`status/app/`、仓库根、`status/archive/` 多目录检索均未找到 ⇒ 按三态记为**「无法判定」，不判不合格、也不写成已落盘**；该引用属 APP-048 时代的历史截图，可能在客户包或 reviewer 本机，**需 reviewer 确认存放位置**（本轮不擅自改判、不删 STATUS 引用）。抽取正则已修正为保留可选前导下划线（否则 `_app310` / `_app311` 被误报缺失 ⇒ 属「FAIL 先怀疑判据」）。
- **半交付与纪律**（`_app312` → `git`）：`head=4306e10132d1c7ea473c299eceba7e1ce5ff416b`、`ahead_origin_main=0`、`staged_count=0` ⇒ **无半交付漏项**；`corrections_worktree='M status/app/CORRECTIONS_APP.md'` 是 **reviewer 的未提交改动** ⇒ 本轮只读、未改、未提交，提交时逐文件 `git add` **绝不带它**；工作区另有其它模块大量未提交改动（c0xx 系列等）⇒ **一个都没吞**。未在 CPU 跑推理/测速、未调 MiniMax、未创建 `MACHINE_LOCK`、未改桌面 .lnk、未动 `v23_clone/`。
- 🔴 **APP-075 本条需等 reviewer 复核**（纠偏原文 L1463「需 Opus 复核：待 r2 交付后（F0/x-vector 复核）」）：r2 已交付（**54 文件／20 175 499 B**）但 F0 闸门 **21 PASS / 19 FAIL / 6 NONE**、19 个 FAIL 全是 `male→female`；`app299` 仍是 `offline_stat_embed`（`verdict=FAIL`）⇒ **真 x-vector 余弦矩阵未产出、第 2 臂 preset 对照未跑** ⇒ 本轮不自行判定通过、不往下推进、**v2.3 不打包**。待复核清单（同 §141）：r2 F0 表／APP-074 结论改正（目录≠zip）／3 个旧包 `bridge_token.txt` 清单／本轮未打包。
- 🔴 **纠偏文件收尾复核（全程只读、未改、未提交）**：开工 SHA `bbc95c43…d82af`／220735 B／2026-11-06 13:31:54／**78 条** ⇒ 收尾 SHA `bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af`／220735 B／2026-11-06 13:31:54／**78 条**（最大 APP-078）⇒ **一致（reviewer 本轮未追加，可称零改动）**；`last_ack` 保持 **APP-078**（无新编号可推进）。
- **写入纪律**（见 `_app313_write_status_sec142.json`）：头部仅定点改「更新时间」「当前任务」**两行**；末尾仅追加本章节；旧正文逐字未变、章节数不减、LF 行尾未破、写后 ≤ 40000 B / ≤ 300 行；先临时文件再 `os.replace` 原子替换，写后磁盘逐字复核。
