# STATUS_APP

last_ack: APP-061
更新时间: 2026-11-02 04:47
当前任务: **§129 巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 自查出并修掉 4 个真缺陷：① `app224` 用移动 `git HEAD` 当基线 ⇒ 修复一提交闸门就在正确代码上永久 FAIL（改钉 `fae75d9` ＋ 判据自检）② 锁闸门第 11 组 AST 反证谓词**恒真**（抓不到 `os.path.exists`）③ `app223` 的 `--dry-run` 跑不出来 / 自检**冲掉**真机证据 / 反证臂**从不判定**（3 个全修）④ APP-061②「附带问题」`Fatal Python error: _enter_buffered_busy`（边车退出崩溃，已用裸 fd 修，A/B 实测 orig 崩 3221225477 / fixed rc=0）** ｜ 🔴 **设备级实测本轮未开跑**（安静窗口不可用：用户 v2.1 GUI 会话 PID 14712 **实测仍在烧 CPU 0.656 s/5 s** ⇒ 不与用户抢 NPU）⇒ **①③④⑤ + ③(e) 的设备级数字仍未实测**
阻塞 / 待用户决定: 🔴 **D1–D4 仍由 reviewer/用户决定**（旁路窗口时长 / 是否自动开旁路 / 客户包是否保留 CUDA 选项 / NPU 共用是警告还是禁止）；🔴 **§128 新增 1 项待 reviewer 裁定**：共享锁 `stale_boot` 分支**优先于 PID 存活判断** ⇒ 时钟异常时会**抢走活锁**（本轮只写成显式断言，**未改实现语义**）；🔴 **§129 新增 1 项待 reviewer 裁定**：锁闸门第 11 组的 AST 反证谓词**恒真**（只认 `os.exists`、抓不到 `os.path.exists`）⇒ 修它要动**共享锁闸门**（ASR/MT/TTS 共用）⇒ 本轮**只定位、只留证**；⛔ **设备级实测（①③④⑤ + ③(e)）仍未做**：harness `app223` **本轮已修好 3 个缺陷 ⇒ 一键可跑**，等机器安静 + 用户会话结束后即可跑
已压缩: 本文件 37279 B / 228 行（APP-052 ④ 限额 ≤ 40000 B / ≤ 300 行）；**§109–§124 正文＋旧「最近更新」条目＋「已撤回的旧结论」备查块已原样归档**到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（**逐字保留，内容一字未删**；更早的见 `STATUS_APP_sec109_122_upto_20261101.md`）


## 最近更新
- 2026-11-02 04:47 **§129** ⇒ 无新纠偏（61 条 = APP-061）⇒ **自查 4 个真缺陷并修好**：① `app224` 用**移动 `git HEAD`** 当基线 ⇒ 修复一提交就在**正确代码上永久 FAIL**（0/5）⇒ 改钉 `fae75d9` ＋ **判据自检**（坏文件必被抓住）⇒ **5/0** ② 锁闸门第 11 组 AST 反证谓词**恒真**（只认 `os.exists`、抓不到 `os.path.exists`）⇒ **只定位留证、待 reviewer 裁定** ③ `app223` **3 个缺陷**（`--dry-run` 跑不出来 / 自检冲掉真机证据 / 反证臂从不判定）全修 ④ **APP-061② 附带问题** `Fatal Python error: _enter_buffered_busy`（边车退出崩溃）⇒ 改裸 fd `os.read` ⇒ **A/B 实测 orig 崩 3221225477 / fixed rc=0（两组都收到数据）** ＋ 回归 `app215` 29/0、`app220` 39/0、`app219` 13/0 ⇒ ⛔ **设备级实测仍未开跑**（用户会话 PID 14712 实测仍在烧 CPU 0.656 s/5 s）＋ 🔴 v2.2 包内仍是改前版 ⇒ 下一版打 v2.3
- 2026-11-02 03:16 **§128** ⇒ 无新纠偏（61 条 = APP-061）⇒ APP-061② `SyntaxWarning` 已修（5 文件，告警全归零，字符串值未变）＋ 共享锁闸门夹具写死日期导致的 **8 条假 FAIL 已修（32/40 → 42/42）**＋ **CUDA 置灰 4/4 落点核验通过** ＋ 真机验收 harness `app223` 已备好（判据自检 5/5 ⇒ 非恒真）⇒ ⛔ **设备级实测未开跑**（用户 v2.1 会话在跑）＋ 🔴 新增待裁定：`stale_boot` 优先于 PID 存活 ⇒ 时钟异常会抢活锁
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
| §128 | 巡检无新纠偏 ⇒ APP-061② `SyntaxWarning` 已修 ＋ 共享锁闸门夹具假 FAIL 已修（42/42）＋ CUDA 置灰核验 ＋ 真机验收 harness 备好（设备级实测因用户会话在跑而未开跑） | **本轮新增（见下）** |
| §129 | **巡检无新纠偏 ⇒ 自查 4 个真缺陷并修掉**（`app224` 移动-HEAD 基线 ⇒ 永久假 FAIL；锁闸门反证谓词恒真；`app223` 3 个缺陷；边车 `_enter_buffered_busy` 崩溃）＋ 回归 29/0・39/0・13/0 | **本轮新增（见下）** |

### §123 ✅ **APP-052 / APP-053 / APP-054 —— 桌面 `.lnk` 坏链修复 ＋ `ACCEPTED` 重签 ＋ 说话人标签覆盖率 7 % → 93.48 % ＋ 旁路线程化止血 ＋ STATUS 压缩** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**


> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec123_upto_20261101.md`（逐字保留，内容一字未删）。

### §124 ✅ **APP-055 / APP-056 / APP-057 / APP-058 —— v1.13 还原 ＋ 模块租约 ＋ V2.0→V2.1 交付包 ＋ 说话人覆盖率同段复测** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**


> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec124_upto_20261101.md`（逐字保留，内容一字未删）。

### §125 ✅ **APP-059 —— 口径 B 定为唯一口径 ＋ README 说话人标签局限说明 ＋ 两处表述更正 ＋ MANIFEST SHA 三元组 ＋ EXT-028 状态 ＋ HOWTO** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**


> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec126_upto_20261101.md`（逐字保留，内容一字未删）。


### §126 ✅ **APP-060 —— 交付版定为 v2.1；v2.0 标 superseded；桌面 v2.0.lnk 已由 reviewer 删除（脚本加硬闸门）；今后改动只打 v2.2+** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**


> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec126_upto_20261101.md`（逐字保留，内容一字未删）。

### §127 ✅ **APP-061 —— 用户实测 v2.1 的 6 个问题（CUDA 无声 / 离线无参考音色 / 卡顿 / 克隆约 10 s 一次 / 男声被女声播出 / 界面不紧凑）：代码层全部修复 ＋ 打 v2.2 交付包** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec127_128_upto_20261102.md`（逐字保留，内容一字未删）。
### §128 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 转做 APP-061② 附带问题 ＋ 共享锁闸门修复 ＋ 备好真机验收 harness；设备级实测因用户会话在跑而未开跑** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 03:16）

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec127_128_upto_20261102.md`（逐字保留，内容一字未删）。

### §129 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 自查出并修掉 4 个真缺陷（闸门自身缺陷 3 个 + 边车崩溃 1 个）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 04:47）

**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ `last_ack` **APP-061** ⇒ **无新纠偏条目**（本轮**不执行**任何新条目；`last_ack` **不变**）。

**租约**：`session_lease.py acquire app` ⇒ `TOKEN=2aa48e52`（**无 TAKEOVER**）⇒ 本轮全程持租约。

#### ① 🔴🔴 **闸门自身缺陷 1（真缺陷，不是产品缺陷）**：`app224` 用**移动的 `git HEAD`** 当「改前基线」⇒ 修复一提交，闸门就在**正确的代码上永久报 FAIL**

* **现象**：§128 把 escape 修复提交进 `25a4974` 后，重跑 `app224` ⇒ **0 PASS / 5 FAIL**（5 个文件全 FAIL，`warn_before=0 warn_after=0`）。
* **根因**：`check_escape_fixes()` 的 `baseline = git_head_bytes(rel)` = **移动的 HEAD** ⇒ 修复入库后 HEAD 变成「改后」⇒ `warn_baseline` 变空 ⇒ `warn_cleared = 恒 False` ⇒ **闸门永久红**。
* 🔴 **这不是「代码退化」**：实测 `fae75d9`（§128 的父提交）里 4 个文件**各有 1 条 `SyntaxWarning`**，`25a4974` 里 **0 条** ⇒ **代码是对的，闸门是错的**（对齐记忆「判据 FAIL 先怀疑判据/环境」）。
* **改法**：基线**钉死**到 `BASE_REV = 'fae75d9'`（`app223` 是 §128 新建文件、不在该提交里 ⇒ 回落到 §128 的改前备份 `shared/app223_backup_20261102/`）。
* 🔴 **顺带补一个弱标记的洞**：若基线取不到，原实现会「**恒 PASS**」（`warn_cleared` 只要求 `not warn_now`）⇒ 现在要求 `baseline_had_warn`（**基线本身必须有告警**）⇒ 否则判「无法判定」。
* 🔴 **并新增 ⑥「判据自检」**：造一份**故意带 `SyntaxWarning` 的坏文件**跑同一套判据 ⇒ 必须被判成「没归零」⇒ **判据非恒真**。
* **改后实测**：`app224` ⇒ **5 PASS / 0 FAIL**（① escape 5/5 PASS，② 锁闸门 **42/42**，③ 改前基线 `fae75d9` **30/39**（9 条假 FAIL，与 §128 记录的 30/39 **一致**），④ CUDA 置灰 **4/4**，⑥ 判据自检 PASS）⇒ 证据 `results/app/app224_app061_escape_lock_gates_evidence.json`（**7 379 B** / SHA256 `a97d35b49e648a3f…` / mtime 2026-11-02 04:43:26）。

#### ② 🔴🔴 **闸门自身缺陷 2**：`test_machine_lock_app.py` 第 11 组的 AST 反证**判据恒真**（抓不到 `os.path.exists`）

* **发现**：反证用的谓词是 `node.func.attr == 'exists' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'os'` ⇒ 它只能匹配 `os.exists(x)`；而代码里写的是 **`os.path.exists(x)`**（`func.value` 是 `ast.Attribute`，**不是** `ast.Name`）⇒ **谓词永远匹配不到** ⇒ `old_has_exists` 恒 `False` ⇒ 「修复前的 acquire 没有 exists 前置判断」这条断言**恒 PASS** ⇒ **反证没有鉴别力**。
* 🔴 **实测确认**：把当前源码（**含** `os.path.exists(lock_path)`）喂给该谓词 ⇒ 仍返回 `False`；只有人为注入 `os.exists(...)`（Name 形态）才返回 `True` ⇒ **谓词与真实代码形态脱节**。
* ⚠️ **本轮只定位，**未改判据**（属共享锁闸门、影响 ASR/MT/TTS 三个模块共用的 `machine_lock_app.py`）⇒ 留证交 reviewer 裁定（见 §129 ⑧）。
* 🔴 **同时确认**：`acquire` 的「先探测、后创建」修法**本身是对的**（`3b07811` 引入 `os.path.exists` 守卫，`8d6bcc1` 及其父提交都没有）⇒ **被测对象无缺陷，缺陷在判据**。

#### ③ 🔴🔴 **闸门自身缺陷 3**：`app223` 真机验收 harness 的 3 个问题（`--dry-run` 跑不出来 / 自检**冲掉**真机证据 / 反证臂**从不判定**）

* **(a) `--dry-run` 单独用时**永远走不到**打印命令的分支**：原实现先判 `if not args.run:` 就 return ⇒ 文档里写的「③ 只打印命令不跑」**实际只跑了自检**。⇒ 改法：`--dry-run`（且未带 `--run`）**先**打印 3 条臂命令并返回，**不跑设备、不写证据文件**。
* **(b) `--self-test` 会覆盖真机证据**：`--out` 默认指向 `app223_app061_device_acceptance_evidence.json` ⇒ 跑一次自检就把**真机跑出来的设备级证据冲成 `SELFTEST_ONLY`**（实测：本轮第一次跑自检就把该文件改了 ⇒ 已 `git checkout` 还原）。⇒ 改法：自检结果**另存** `…_evidence.selftest.json`；实测自检前后 canonical 证据 SHA256 **逐字相同**（`199529db275832601…`）⇒ **未被覆盖**。
* **(c) v2.1 反证臂**只被存进 `out`、**从不判定** ⇒ 「v2.1 用同一套判据**必须 FAIL**」这句话**没有任何强制力**（万一 v2.1 也 PASS，闸门照样报 PASS）。⇒ 改法：用**同一套** `judge()` 判反证臂 ⇒ `counterproof_v21_n_fail == 0` ⇒ **整轮判 FAIL**（不是「无法判定」）。
* **(d) 产物目录卫生**：`results/app/app223_device_out/` 在仓库内 ⇒ `.wav`/`.log` 被根 `.gitignore` 命中，但 **`.jsonl`/`.txt` 不会** ⇒ 真机跑完留一堆未跟踪文件。⇒ 改法：**在产物目录内部**放一个 `.gitignore`（内容 `*`）⇒ **不改仓库根的 `.gitignore`**（那是全仓库共享文件，不该由本模块改）。
* **回归**：改后 `--dry-run` 实测**打印出 3 条完整臂命令**（`tts_off` / `tts_on_preset` / `tts_on_clone`，均含 `--engine gpu_int8 --translate zh --asr-device GPU.0 --mt-device GPU.0 --tts-device NPU`）⇒ `--self-test` **5 PASS / 0 FAIL** 且 canonical 证据 SHA 未变 ⇒ **3 个缺陷全部修好**。

#### ④ 🔴🔴 **APP-061② 的「附带问题」终于处理了**：`Fatal Python error: _enter_buffered_busy`（reviewer 原话：「边车退出时有 `Fatal Python error: _enter_buffered_busy`（21:24:51）」）—— §127 / §128 **都没修**

* **根因（已实测复现，不是推测）**：`sys.stdin.buffer` 是 `BufferedReader`；边车的**命令读取线程**（daemon）阻塞在 `readline()` 时**持有该缓冲对象的内部锁** ⇒ 边车退出 ⇒ CPython 进入 finalizing ⇒ 要 flush/close 同一个 `BufferedReader` ⇒ **抢不到锁** ⇒ `Py_FatalError("_enter_buffered_busy: could not acquire lock for <_io.BufferedReader name='<stdin>'> at interpreter shutdown, possibly due to daemon threads")` ⇒ **边车以 `0xC0000005`（3221225477）崩掉**。
* **修法**：读取线程**不再用 `sys.stdin.buffer`**，改用**裸 fd** 的 `os.read(0, …)`（自己攒行缓冲）⇒ 不持有任何 Python 缓冲对象的锁 ⇒ 退出时不抢锁。
* 🔴 **判据非恒真（A/B 干净对照）**：`results/app/app225_app061_sidecar_crash.py` 跑**两份只差读取方式**的子进程（同一台机、同一套管道、连控制流都照抄真实边车：**`quit` 只塞队列、读取线程不退出** ⇒ 才会卡在「读取线程正持锁阻塞在读」的真实崩溃现场）：

| 组 | 读取方式 | 实测 rc | `_enter_buffered_busy` | 收到数据 |
|---|---|---|---|---|
| `orig`（改前） | `sys.stdin.buffer.readline()` | **3221225477（崩）** | **True** | ✅ |
| `fixed`（改后） | `os.read(0, …)` | **0（正常退出）** | False | ✅ |

  ⇒ **两组都收到了数据** ⇒ 「改后不崩」**不是**因为「没读」⇒ 判据有效。**4 PASS / 0 FAIL** ⇒ 证据 `results/app/app225_app061_sidecar_crash_evidence.json`（**1 948 B** / SHA256 `6e1dbc9c97c44f1a…` / mtime 2026-11-02 04:45:17）。
* 🔴 **改动范围**：**只改开发版 `live_caption/tts_cuda_sidecar.py`**（25 600 B / SHA256 `677daaee11082184…`）⇒ **v2.2 客户包一个字节都没动**（包内仍是改前版）⇒ 下一版必须打 **v2.3**（**禁止 `--same-version`**），**本轮未打包**（未获授权）。

#### ⑤ ⛔ **设备级实测仍未做**（与 §128 同一阻塞，且本轮**再次实测确认**）

* `machine_lock_app.wait_quiet_window_cpu(30)` ⇒ **ok=False**；`last_busy_pids=[14712]` = **用户自己的 v2.1 GUI 会话**（`OpenProcess`+`GetExitCodeProcess` 实测 **alive / 259**）。
* 🔴 **本轮新增的直接证据**：`14712` 的 **CPU 时间增量 = 0.656 s / 5 s**（`GetProcessTimes` 两次采样差）⇒ **用户会话确实在跑、确实在烧 CPU** ⇒ 与用户抢 NPU 会让**两边数字都失真** ⇒ **不开跑**。
* ⇒ **APP-061 ①③④⑤ + ③(e) 的设备级数字仍然「未实测」**（代码层已由 `app215`/`app219`/`app220` 覆盖）⇒ 下一步：机器安静 + 用户会话结束后跑 `python results/app/app223_app061_device_acceptance.py --run`（**本轮已把该脚本的 3 个缺陷修好 ⇒ 一键可跑**）。

#### ⑥ ✅ **既有回归套件复跑（改了代码 ⇒ 必须复跑）**

| 闸门 | 结果 | 说明 |
|---|---|---|
| `app215`（①④⑤ 语音/克隆） | **29 PASS / 0 FAIL / 0 NONE** | 7 条反证全被抓住 |
| `app220`（③ 卡顿遥测/预缓冲/倍速封顶） | **39 PASS / 0 FAIL / 0 NONE** | 5 条反证全被抓住 |
| `app219`（⑥ 界面紧凑） | **13 PASS / 0 FAIL / 0 NONE** | 含 1024×800 截图 |

⇒ 三个闸门**全部与 §127 记录一致**（29/0、39/0、13/0）⇒ **本轮改动没有引入回归**（复跑输出另存 `/tmp/app21*_recheck.json`，**未覆盖**仓库里的原证据）。

#### ⑦ 🔴 **收尾复核（`CORRECTIONS_APP.md` 全程只读）**

* 开工基线：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**。
* 收尾实测（2026-11-02 04:47 现场重算）：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**（APP-001…APP-061）⇒ **与开工基线逐字相同 ⇒ 本轮 reviewer 未追加新条目 ⇒ 「SHA 零改动」在本轮成立**（与 §125/§126「中途被追加」那两轮**不同**，勿混为一谈）。
* 本模块对 `CORRECTIONS_APP.md` **全程只读、未写入**。

#### ⑧ 🔴 **本轮新增待 reviewer 裁定（未自行改语义）**

① **锁闸门第 11 组的 AST 反证谓词恒真**（只认 `os.exists`，抓不到 `os.path.exists`）⇒ 反证**没有鉴别力**。**修它要动共享锁闸门**（`results/app/test_machine_lock_app.py`，被 ASR/MT/TTS 共用的 `machine_lock_app.py` 覆盖）⇒ 本轮**只定位、只留证**，改法与范围交 reviewer 定。
② **`app224` 的基线钉在 `fae75d9`** ⇒ 该提交若被 `git gc`/改写则基线会失效（Git 提交不可变，正常不会变）⇒ 已同时保留 `shared/app223_backup_20261102/` 作第二来源。
③ **APP-061② 另两条附带问题**：边车依赖包外 `C:\Users\Trekker-PTL\_fq3tts_env`（客户机不存在 ⇒ 属 **D3** 待决）＋ **v2.2 包内的 `tts_cuda_sidecar.py` 仍是改前版**（`_enter_buffered_busy` 与 `\_` 告警都在）⇒ **必须打 v2.3 才带上修复** ⇒ **本轮未打包**。

#### ⑨ 本轮交付

* 代码（**只改开发版**，客户包一个字节都没动）：`live_caption/tts_cuda_sidecar.py`（**25 600 B** / SHA256 `677daaee11082184…`）。
* 验收脚本：`results/app/app225_app061_sidecar_crash.py`（**11 189 B** / SHA256 `5bc41eb9cb3bb099…`）、`results/app/_app129_archive_sec127_128.py`。
* 修改的既有脚本：`results/app/app223_app061_device_acceptance.py`（**36 298 B** / SHA256 `91d9b3e6daf5ea15…`）、`results/app/app224_app061_escape_lock_gates.py`（**17 068 B** / SHA256 `bae994ebaef6b276…`）。
* 证据：`results/app/app225_app061_sidecar_crash_evidence.json`（**1 948 B** / SHA256 `6e1dbc9c97c44f1a…`）、`results/app/app224_app061_escape_lock_gates_evidence.json`（**7 379 B** / SHA256 `a97d35b49e648a3f…`）、`results/app/app223_app061_device_acceptance_evidence.selftest.json`（**2 458 B** / SHA256 `e93dd100b250cef2…`）、`status/archive/STATUS_APP_sec127_128_upto_20261102.md`。
* 🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**（v2.1、v2.2 目录与 zip **一个字节都没动**）；**未提交任何 `CORRECTIONS_*.md`**。
