# STATUS_APP

last_ack: APP-080
更新时间: 2026-11-07 01:45:30
当前任务: **§145 无新纠偏（last_ack=APP-080）｜APP-080 打包链路就绪度静态盘点 18/0 ＋ 反证 7/7；打包链路 NOT_WIRED 列入 ⑤ 待办，APP-075/079/080 仍停 reviewer 复核，v2.3 未打包**
阻塞 / 待用户决定: 🔴🔴 **APP-075 未闭环（BLOCKING）**：r2 已交付但 F0 闸门未通过，`app299` 是 `offline_stat_embed`（统计嵌入，硬判据 cos_S2_S2=0.745841 < cos_S2_S1=0.772995 ⇒ FAIL）⇒ **真 x-vector 需 reviewer 复核**；第 2 臂（preset 对照）因设备作业被会话中断杀死未跑（已用 ctypes err=87 确证 PID 死并回收孤儿锁）→ **按 APP-075「需 Opus 复核」节点停止，不自行判定通过，v2.3 不打包**｜🔴 **v2.3 打包待办**：5 个 ASR 文件＋`models/spk/pyannote_seg_3_0/fp16-w5/`＋`assert_pkg_clean.py` 闸门＋桥接 .lnk 指向 `bridge_bootstrap`（本轮**未打包、未落进任何包**）｜🔴 **reviewer 本轮中途追加 APP-078**：纠偏文件开工 77 条 / SHA `3f759ebe…7f359` ⇒ 收尾 **78 条** / SHA `bbc95c43…d82af`（全程只读未改，**不得声称零改动**）｜旧包 v2.0/v2.1/v2.2 目录与 zip **一字节未动**，受影响清单见 §140，等 reviewer 转告用户｜本轮需 reviewer 复核：r2 F0 表 / APP-074 结论改正 / 3 个旧包清单 / 未打包 ｜**§141 补充**：本轮 `ac61878` 已提交且 `origin/main..HEAD` 为空（无半交付漏项）；APP-075 的 r2 F0 表／APP-074 结论改正／3 旧包 `bridge_token.txt` 清单／本轮未打包 **仍等 reviewer 复核**
已压缩: 压缩索引（旧正文逐字归档）⇒ `status/archive/STATUS_APP_compress_index_upto_20261107.md`；限额 ≤40000 B / ≤300 行（APP-052④）｜**§145 压缩**：§144 正文＋§143 产物表 ⇒ `status/archive/STATUS_APP_sec144_20261107.md` ／ `status/archive/STATUS_APP_sec143_artifacts_20261107.md`


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

## §143 APP-079 静态归因 + APP-080「v2.3 只交付预设音色」构建期补丁与静态自证（2026-11-06 23:22:36）

- **开工基线与断点**：`status/app/CORRECTIONS_APP.md` **80 条**（APP-001..APP-080）／SHA256 `b3ae9ea9…f392b937d5`／**224 562 B**／mtime **2026-11-06 21:40:34** ⇒ 大于 `last_ack: APP-078` 的新条目为 **APP-079、APP-080**。租约 `acquire app` ⇒ **TAKEOVER**（TOKEN `2506f224`；上一会话 21:58 起、心跳停 22:08、`alive=False`）⇒ 按 APP-056 先读其 note／STATUS／产物**从断点续做**：上一会话已落盘 `v23_preset_only.py` 与 `_app314`／`_app315` 两份自证脚本，但 22:08–22:09 改完脚本后**未复跑、未写 STATUS、未提交** ⇒ 本轮复跑两份自证并收口，不从头重做。头部 `last_ack` 按 APP-080 明文「开始处理时写 last_ack=APP-080」更新为 **APP-080**（**不代表 ⑤⑥ 已验收**）。
- 🔴 **APP-079 本条需等 reviewer 复核**（BLOCKING）：`results/app/_app314_app079_static_triage.py` → `_app314_app079_static_triage.json` ⇒ **`verdict=PASS` / `n_pass=10` / `n_fail=0` / `counterproof_identified=4/4`**。原始字段（`measured`）：`n_submit=82`／`n_tts=46`／`spk_conf_null=82`（**82/82 全 null ⇒ `REG_CONF_MIN` 门槛在该链路拿不到输入**）／`spk_null=73`、`spk_non_null=9`／`clone_active_false=46`／`voice_kind_clone=44`／`voice_spk_non_null=43`（**tts.jsonl 43/46 非空 ⇒ 标签其实经晚到绑定进了 worker，不能简单归因为「完全没传」**）／`seg_conf_non_null=43`（最小 `0.0602`，**断链发生在 seg→submit 传递**）／`f0_verdict_counts={'true':21,'false':19,'none':6}`（与 reviewer 独立复核一致）。⇒ ① `voice_kind='clone'` 与 `clone_active=False` 自相矛盾 ⇒ **旧判据失真**；② `clone_active` 恒 False 的**确切根因记「无法判定」**，须靠 (a) 的 TTS 入口运行期日志定案；③ reviewer「spk/spk_conf 全为 null」与本机 9/82 行 `spk` 非空存在**口径差异**（`reviewer_claim.submit_spk_all_null_consistent=false`，可能与 `_app309` 补齐的提交映射版本有关）⇒ 记「需 reviewer 确认」，不判 reviewer 错、也不自行改写结论。**(b)(c)(d) 未做**：按 APP-080「克隆修复移到后续版本／v2.3 发布前不再为克隆占用设备」转入后续版本；本轮未占设备、未调 MiniMax、**未改 `live_dub_ext`**（APP-079 明文注意事项）。
- 🔴 **APP-080 本条需等 reviewer 复核**：`_app315` ⇒ **`verdict=PASS` / `n_pass=36` / `n_fail=0` / `n_unknown=0` / `counterproof_identified=8/8`**。①②③④ 的**构建期定点补丁 + 静态自证**已落盘；⑤⑥ 需打新版本包与设备级验收 ⇒ 按「用户不通知不打包」＋纠偏原文「reviewer 复核通过后才通知用户」停下。
  - **① 界面**：`_app315` → `applied_patches['live_caption/live_caption_app.py']` = **P00–P10 共 11 条**（下拉 `tts_voices=['A']`、标签去「克隆·实验」、复选框改「区分说话人（字幕标注）」、提示语改字幕标注、启动回落、克隆采集器恒 False、状态栏固定「预设 A」、onchange 去克隆分支、CLI 回落、help 不再宣传克隆）；`--tts-voice` 的 `choices` **保留** `follow_speaker` 只为兼容旧配置、不报错。
  - **② 运行时**：`tts_service.py` S00–S02、`tts_worker.py` W00–W03 共 **7 处闸门**（克隆登记／speaker_enc 克隆调用／旁路触发的音色切换一律不执行）；`normalize_voice()` 对 6 类残留值（`follow_speaker` / `clone` / `B` / 空 / `None` / `object()`）**全部回落 A 且写日志、不抛异常**；音色固定预设 A。
  - **③ 说话人旁路**：`caption_render.render_lines` 输出行带 `spk` 键、`App._retry_spk_labels()`、CLI `--speaker on` ⇒ **旁路仍有「字幕标注」用途 ⇒ 不整块隐藏**；`KEEP_SPK_FILES` **5 个**与 `_app304` 清单一致，随 v2.3 保留，ASR-050 `min_clean_ratio` 默认 0.6 同源跟随。**包体积变化**：v2.2 目录只读实测 8 个 babelvox 示例音色共 **18 145 B**（`_app315` → `v22_babelvox_samples.total_bytes`）；zip 层按 APP-078 为 **0 命中 ⇒ zip 体积／SHA 不因本项改变**；🔴 **未打包 ⇒ 这是只读基准，不是「已交付」**。
  - **④ 包内容**：`PKG_EXCLUDE_PATTERNS` 覆盖 `bridge_token.txt`（APP-077）／4 人 ×2 = 8 个 babelvox 示例音色（APP-078）／克隆音色／`v23_clone*/` 测试 wav；`assert_pkg_clean.py` 在**真实 v2.2 目录只读扫描** ⇒ `v22_gate_violations=9`（含 APP-077/078 历史违规），干净临时目录 `gate_clean_dir_pass` ⇒ `violations=[]`；**SpeakerLibrary 无示例音色仍正常**：`speaker_library_probe={'profiles_no_builtin':0,'save_load_roundtrip':'probe','profiles_when_builtin_dir_absent':0}`，`tts_engine.py` 有 `isdir`／`src is None` 守卫（纯 CPU，无推理）。
  - 🔴 **判据盲区已修（`_app316`）**：`_app315` 首版闸门插在 `def` 与 docstring 之间 ⇒ 补丁后 5 个目标函数 `__doc__` 全变 `None`（ast 实测 dev 有值／patched 全 None）⇒ 属「自证 PASS 却静默改了另一条语义」。`results/app/_app316_docstring_guard_fix.py`（**6 个替换块全部唯一命中 + `ast.parse` + 写后逐字节复核**，报告 `_app316_docstring_guard_fix.json` ⇒ `verdict=PASS`）改为 **ast 定位 docstring 结束行后插入闸门**，并给 `_app315` 加 `docstrings_preserved_after_guard` 判据与反证 **E8**（把闸门插回 docstring 之前必须被识破）⇒ 复跑 **36/0、反证 8/8**。🔴 E8 首跑 `7/8` 是**夹具缺陷**（`patched[k_svc]` 是 CRLF，`'…:\n'` 锚点命不中）⇒ 归一化为 LF 后 8/8，属「FAIL 先怀疑判据／环境」，不是产品缺陷。
  - **构建期补丁规范**：`live_caption/v23_preset_only.py`（dev 新增，克隆实现**一字未改**，供后续版本复用）→ `_app315_v23_preset_only.diff`（**8 021 B**）：**18 个锚点全部唯一命中**（P 11／S 3／W 4），补丁后 `ast.parse` 通过、`live_caption_app.py` LF 与另两份 CRLF **行尾还原**；补丁只在内存里应用，**dev 源文件与任何已发布目录均未被写入**。⚠️ 包内必须同时带 `PKG_INCLUDE_FILES=['app/v23_preset_only.py','app/assert_pkg_clean.py']`，否则 `from v23_preset_only import …` 会 ImportError。
- ⛔ **⑤⑥ 停止点与 v2.3 打包待办**（APP-080 ⑥「reviewer 复核通过后才通知用户」＋用户级「不通知不打包」）：本轮 **未打包／未打新版本目录／未打 zip／未改任何客户安装目录与旧 zip／未改桌面 .lnk／未创建 `MACHINE_LOCK`（未占设备）／未在 CPU 跑推理测速／未调 MiniMax**。⑤ 待并：APP-063/065 界面修复、5 s 窗口静态 seg IR（`models/spk/pyannote_seg_3_0/fp16-w5/`）、APP-077 不带 `bridge_token.txt`、v2.1 快捷方式「启动失败弹提示框＋日志写用户目录＋不写死版本目录」（EXT-042）。⑥ 待验收：干净目录解压 `--check`／CLI SPE 5 分钟（ASR WER／配音零段／RTF／积压）／GUI 100 %＋150 % 两张截图确认无克隆入口／黑名单扫描（会议录音・克隆音色・babelvox 音色・开发路径・torch/cuda）／zip SHA256。**没落盘的一律不写「已交付」**。
- **口径更正（不回头改旧章节）**：头部「阻塞 / 待用户决定」中 §140–§142 时代「APP-075 未闭环 ⇒ v2.3 不打包」的措辞按 APP-080 **已变更**：克隆修复（APP-071/075/079）**转入后续版本**，不再阻塞 v2.3；新阻塞条件 = 「⑤⑥ 打包与设备级验收完成 ＋ reviewer 复核通过 ＋ 用户明确通知」。旧章节正文一字未改，本条为口径更正。
- **纠偏文件收尾复核（全程只读、未改、未提交）**：开工 SHA `b3ae9ea9…f392b937d5`／224 562 B／2026-11-06 21:40:34／**80 条** ⇒ 收尾 SHA `b3ae9ea9…f392b937d5`／224 562 B／2026-11-06 21:40:34／**80 条**（最大 APP-080）⇒ **与开工逐字一致（reviewer 本轮未追加）**，全程只读、未改、未提交。
- **产物清单（写 STATUS 时磁盘实测，共 12 个文件；每个附 mtime／字节数／SHA256）**：

> 🔴 §143 产物清单（14 行表格）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec143_artifacts_20261107.md`（块 SHA256 `38f401fad509a9e32f1e5320bf8754bab952f560905322769095802182518264`）；12 个文件的 mtime／字节／SHA256 见归档件，§144 `_app318` 已逐项自证。
- **git 纪律**：逐文件 `git add`（禁 `-A`）⇒ main **普通 push**、不 force；**绝不提交 `status/app/CORRECTIONS_APP.md`**（其 `M` 状态是 reviewer 的未提交改动），不吞 ASR/MT/TTS 其它模块的未提交改动；提交号与清单见本轮 git 日志。
- **写入纪律（APP-052④）**：写 §143 前先把 §141／§142 正文 **整块逐字归档**到 `status/archive/STATUS_APP_sec141_142_20261106.md`，另把「未完成纠偏」旧表整块归档到 `status/archive/STATUS_APP_unfinished_corrections_upto_20261106.md`（首版 **42 007 B** 超 40 000 B 限额被写前自检拦下 ⇒ 未落盘，压缩后达标），原位只留速查行；头部仅定点改 `last_ack`／`更新时间`／`当前任务` **3 行**；末尾仅追加本章节；自检「旧正文逐字未变・章节数不减・LF 行尾未破・≤40 000 B / ≤300 行」＋临时文件 `os.replace` 原子替换＋写后磁盘逐字节复核，报告 `results/app/_app317_write_status_sec143.json`。

> 🔴 §144 正文（15 行）已**整块逐字归档** ⇒ `status/archive/STATUS_APP_sec144_20261107.md`（块 SHA256 `53214dba94e14e870731c1399e79a248bdd2e89a602f6ccd314ad7b77b8b2461`）；速查：`_app318` 对 §143 产物表 12/12 自证 **23/0 ＋ 反证 7/7**，APP-075/079/080 停在 reviewer 复核节点，v2.3 未打包。

## §145 无新纠偏（last_ack=APP-080）｜APP-080 打包链路就绪度静态盘点 18/0 ＋ 反证 7/7（2026-11-07 01:45:30）

- **步骤 1–2**：`status/app/CORRECTIONS_APP.md`（reviewer 独占，只读／未改／未提交）开工＝收尾 SHA `b3ae9ea9…f392b937d5`／224 562 B／mtime 2026-11-06 21:40:34／**80 条**（APP-001..080 无缺号无重复）⇒ `facts.corrections` 同值；`last_ack: APP-080` 对齐最大编号 ⇒ **无编号大于 last_ack 的新条目，步骤 3 无条可执行**。
- **APP-046② 不空转**：`results/app/_app320_v23_build_readiness.json` ⇒ `verdict=PASS`／`n_pass=18`／`n_fail=0`／`n_unknown=0`／`counterproof_identified=7/7`（7 条反证全被识破，含模拟追加 APP-081・插消费引用・改 SHA・删 include 项）。纯 CPU 静态：`facts.machine_lock_present=false`／未推理／未调 MiniMax／未打包／未改客户安装目录与旧 zip／未改 .lnk／未改 `live_dub_ext`。
- 🔴 **本轮新结论（APP-080 ⑤ 待办，需 reviewer 复核）**：`facts.packaging_chain` ⇒ `pack_v13_bytes=72531`／`pack_v13_sha256=2e7a232e…`／`pack_v13_hits=0`／`build_scripts_scanned=22`／`build_scripts_nonzero_hits={}`／`total_hits=0`／`wired=false`／`verdict=NOT_WIRED` ⇒ **§143 警示的「包内必须同时带 `PKG_INCLUDE_FILES=[app/v23_preset_only.py, app/assert_pkg_clean.py]`」尚未被 `pack_v13.py` 或任何建包脚本消费**。两份 dev 资产与 §143 产物表逐字一致：`facts.app080_assets.v23_preset_only.sha256=362825e6…`／`bytes=17260`；`assert_pkg_clean.sha256=ba769069…`／`bytes=3458`；`pkg_include_files` 两路径在开发树均有源、`ast.parse` 通过；`selftest`＝`PASS/36/0/0/8-8`、`docfix.verdict=PASS`、`diff_bytes=8021`。⇒ **不是代码缺陷，是接入待办**：v2.3 打新版本时须把构建期补丁应用到包内 3 份源文件并复制 2 个随包文件，否则 `from v23_preset_only import …` 会 ImportError。
- 🔴 **判据缺陷已自纠（非产品缺陷）**：`_app320` 首跑 `FAIL/2` —— glob `*build*.py` 把**本自证脚本自身**算进被测集合（29 次自引用）⇒ 假 FAIL；按「FAIL 先怀疑判据」排除自身（`excluded_self=_app320_v23_build_readiness.py`）后复跑 **18/0、反证 7/7**。
- **git / 限额只读核查**：`facts.git` ⇒ `head=c6ae632`／`ahead=0`／`branch=main`／`head_files` 5 个全在 `results/app/`・`status/app/`・`status/archive/` ⇒ 无半交付、上轮提交不含 `CORRECTIONS`、未吞其它模块；`facts.status_before` ⇒ 写前 **39 577 B／200 行**／SHA `ec9e5673…`（限额仅余 423 B）。
- ⛔ **停止点**：APP-075「需 Opus 复核」・APP-079「需 reviewer 复核」・APP-080 ⑤⑥「reviewer 复核通过后才通知用户／v2.3 发布前不再为克隆占用设备」⇒ 本轮未自行推进 ⑤⑥、**v2.3 不打包**；新待办「打包链路接入」并入 ⑤ 等复核。3 个旧包 zip 本轮**未重复全量实算**（§142 已实算留证，`facts.not_rechecked` 如实说明）⇒ 不写新的「一字节未动」结论。
- **写入纪律（APP-052④）**：写 §145 前把 §144 正文（15 行／2964 B／块 SHA `53214dba94e14e870731c1399e79a248bdd2e89a602f6ccd314ad7b77b8b2461`）、§143 产物清单表（14 行／1859 B／块 SHA `38f401fad509a9e32f1e5320bf8754bab952f560905322769095802182518264`）与头部旧「已压缩」行（1072 B／块 SHA `75b01f1482e3f8fbee1e4a2c8ff7cfbd3310ca89474984a8aea3a11afa2be0f3`）**整块逐字归档**，原位留速查/短版；头部仅定点改 `更新时间`／`当前任务`／`已压缩` 3 行；末尾只追加本章节；自检「反向还原==旧全文」・章节不减・LF 未破・限额内＋原子替换＋写后逐字节复核 ⇒ `_app321_write_status_sec145.json`；首版 A+B **40 720 B** 超限被拦（STATUS 未落盘）。
- **纠偏文件收尾复核**：开工＝收尾 SHA `b3ae9ea9…f392b937d5`／224 562 B／2026-11-06 21:40:34／**80 条**（最大 APP-080）⇒ reviewer 本轮未追加；全程只读／未改／未提交，可称零改动；若收尾后出现新条目按步骤 4 如实记录。
- **产物清单（写 STATUS 时磁盘实测，共 5 个文件）**：
| 文件 | mtime | 字节数 | SHA256 |
|---|---|---|---|
| `results/app/_app320_v23_build_readiness.py` | 2026-11-07T01:44:34 | 14763 | `344ad71a212452ebb52da16148efee6649ac9dab8291a588ef46faae0af036e0` |
| `results/app/_app320_v23_build_readiness.json` | 2026-11-07T01:44:37 | 9554 | `0c61c1077b68e1bcded92f31036bbdf8912d09bbd82342f725f87a45fbaa9c94` |
| `status/archive/STATUS_APP_sec144_20261107.md` | 2026-11-07T01:51:55 | 3269 | `bd0529841c8b5c3d80a85ec1f3b5de4c06c43674d78652a7538daf38d3c70b33` |
| `status/archive/STATUS_APP_sec143_artifacts_20261107.md` | 2026-11-07T01:51:55 | 2176 | `e9d914a95af7c4642d463f850e84efe66e1f65945de6f84ad2093dce72085547` |
| `status/archive/STATUS_APP_compress_index_upto_20261107.md` | 2026-11-07T01:51:55 | 1398 | `f0c9cc98febcbc51eed7eb35f7b933bbd9929f64ed7238ad253af4e1141e663b` |

- **git**：逐文件 `git add`（禁 `-A`）⇒ main 普通 push、不 force；不提交 `CORRECTIONS_APP.md`（其 `M` 属 reviewer），不吞其它模块。
