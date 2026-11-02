# STATUS_APP

last_ack: APP-065
更新时间: 2026-11-02 20:55
当前任务: **§132 APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 ＋ APP-065 A 界面重排 ＋ B 改名 —— 代码层已执行** —— ① **D4 bug** 修好：enforce 命中后**重读 opt** ＋ enforce 内补 set_engine→set_device ⇒ **MT 不再被覆盖回 NPU**（行为探针 `mt.device=GPU.0` / `engine_key=gpu_int8cw`）＋ **CLI 同 NPU 也自动改 GPU.0** ② **D2 四入口**补齐：GUI 启动/`_on_tts_toggled` 自动开旁路 ｜ CLI `--tts-voice follow_speaker` 自动开旁路 ｜ 取消勾选 ⇒ 音色切回「预设 A」＋提示 ｜ 会话进行中**真正拉起旁路线程**（`ensure_started`）③ **D1**：ASR 侧 `asr_spk_window.WIN_S` 已改 5.0 ⇒ **App 同源自动跟随**（实测 5.0），但 **ASR 内核仍写死 10 s** ⇒ **跨模块错位**（已发 NOTICE 给 ASR ＋ reviewer）④ **APP-065 A 界面重排**：**5 组竖排 GroupBox**（①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级）＋ 组内统一网格（**标签列右边缘 4 组全 56 px @100 % / 76 px @150 %**、**控件列全 233 px**、行高一致）＋ **4 张截图**（100 %/150 % × 启动后/配音开启后）＋ **控件→所在组清单** ⇒ **本条需等 reviewer 复核**（reviewer 明文「截图先交 reviewer，通过后才打包」）⑤ **APP-065 B**：「说话人识别」改名「区分说话人（用于克隆）」并移入高级 ｜ `app229` **38/0** ｜ `app227` **34/0** ｜ `app165` **PASS** ｜ `app220/226/228` **39/10/8 全 PASS**
阻塞 / 待用户决定: 🔴 **本轮停在 reviewer 复核点**（APP-065 A：「截图先交 reviewer，通过后才打包」⇒ **未打包 v2.3**）；⛔ **D1 的跨模块错位未解**（ASR 内核 `WIN_N/N_FRAMES/FPS` 仍写死 10 s ⇒ 与 App 的 5 s **错位** ⇒ 旁路会零标签；已发 `shared/NOTICE_app_to_asr_spk_window_5s_alignment.md`）｜🔴 **70 % 字幕区 vs 5 组竖排冲突**（实测 66.88 % ⇒ 需 reviewer 在「接受」与「允许 ④ 组第二个标签列」之间选）｜🔴 **seg IR 是否已导成 5 s 静态形状**待 ASR 回答 ｜🔴 **app215 的 2 条既有 FAIL**（与本轮无关，HEAD 版同样 FAIL）待 reviewer 决定是否顺手修 ｜🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**（v2.1、v2.2 一个字节都没动；本轮只建了**影子包** `shared/app065_shadow` 供设备级实测）
已压缩: 本文件 39023 B / 221 行（APP-052 ④ 限额 ≤ 40000 B / ≤ 300 行）；**§109–§124 正文＋旧「最近更新」条目＋「已撤回的旧结论」备查块已原样归档**；**§131 正文已原样归档**到 `status/archive/STATUS_APP_sec131_upto_20261102.md`到 `status/archive/STATUS_APP_sec124_upto_20261101.md`（**逐字保留，内容一字未删**；更早的见 `STATUS_APP_sec109_122_upto_20261101.md`）


## 最近更新
- 2026-11-02 10:58 **§131 APP-062（D1–D4）已执行** ⇒ **D1** 旁路窗长改**配置项**（`LIVECAP_SPK_WINDOW_S`）＋**与 ASR 侧同源**（读 `asr_spk_window.WIN_S`）｜**D2** 选「跟随说话人」⇒ **自动开旁路**（三处同步）＋ 状态栏「说话人分离：开（克隆需要）」｜**D3** **客户包去掉 TTS=CUDA**（界面不显示 ＋ CLI 拒绝 exit 2）＋ `pkg_exclude` 排除 3 个文件 ⇒ **包内 grep `_fq3tts_env` 命中 0 处**｜**D4** **禁止** MT+TTS 同 NPU ⇒ MT 自动改 GPU.0 ＋ 告知 ＋ 写日志 ＋ 启动时同样处理 ⇒ `app227` **34/0**、`app228` **8/0** ⇒ 回归 `app215` **29/0**、`app220` **39/0**、`app219` **13/0**、`app224` **5/0**（均与 §129 一致）⛔ D2/D4 截图与设备级实测仍未做（TTS 模块持 `MACHINE_LOCK`）🔴 **更正 §130**：reviewer 于 **09:17:51 追加了 APP-062** ⇒ §130「SHA 零改动」结论作废
- 2026-11-02 09:56 **§130** ⇒ 无新纠偏（61 条 = APP-061）⇒ **自查 3 个真缺陷并修好**：① `app224` 的「字符串常量逐字不变」**按下标比** ⇒ 合法增删一个常量就整体错位 ⇒ `app223` 炸出 **483 条**假「值变了」⇒ **闸门在正确代码上永久 FAIL**（实测 **3 PASS / 2 FAIL**）⇒ 改按**多重集**比 ＋ 拆出 docstring（散文会合法演进）＋ 加 ⑦⑧ 两组判据自检 ⇒ 改后 **5 PASS / 0 FAIL** ＋ 真实产物负向测试 **5/5** ② CUDA 路线「回落预设」**不换参考音频** ⇒ 边车里仍是上一人的克隆音频 ⇒ **串音** ⇒ 4 个回落出口**收敛到共用出口** ⇒ `app226` **10/0** （含反证：改回旧行为必 FAIL）③ `app215` 的 2 处判据被重构波及（反证锚点缩进 ＋ ①b 作用域：`ast.walk(If)` 会遍历 `else` 分支）⇒ **语义不变地**跟着走 ⇒ 回归 `app215` **29/0**、`app220` **39/0**、`app219` **13/0**（与 §129 逐字一致）＋ ⛔ **设备级实测仍未跑**（本轮定位到干扰源 = **ASR 持锁跑 D1**；用户 v2.1 会话实测 **0.000 s/10 s** ⇒ 不干扰）
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
| §131 | **APP-062（D1–D4：用户对 APP-061 的四项决定）** —— 代码层全完成（D1 窗口同源配置项 / D2 自动开旁路 / D3 客户包去 CUDA / D4 禁 MT+TTS 同 NPU） ｜ **本条需等 reviewer 复核** | 已归档 |
| §132 | **APP-063/064/065**：D4 bug ＋ D2 四入口 ＋ D1 窗口（ASR 未同源⇒跨模块错位）＋ 锁纪律 ＋ **界面重排 5 组**（截图/清单已交）＋ 改名 | **本轮新增（见下）** |

### §130 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 自查出并修掉 3 个真缺陷（闸门口径 1 个 ＋ 串音 1 个 ＋ 判据作用域 2 个）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 09:56）

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec130_upto_20261102.md`（逐字保留，内容一字未删）。

### §131 🔄 **APP-062（D1–D4：用户对 APP-061 的四项决定）—— 本条已执行（代码层全部完成）** ｜ **本条需等 reviewer 复核**（2026-11-02 10:58）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec131_upto_20261102.md`（逐字保留，内容一字未删）。

### §132 🔄 **APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 ＋ APP-065 A 界面重排 ＋ B 改名** ｜ **本条已完成（代码层 ＋ 设备级）** ｜ **本条需等 reviewer 复核**（2026-11-03 00:05）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec132_upto_20261103.md`（**逐字保留，内容一字未删**）。

**结论速查（全部数字以归档正文为准）**

| 项 | 结论 |
|---|---|
| **APP-063 ① D4 bug** | ✅ 修好：enforce 命中后**重读 opt** ＋ enforce 内补 set_engine→set_device ⇒ **MT 不再被覆盖回 NPU**（探针 `mt.device=GPU.0`/`engine_key=gpu_int8cw`/落盘 `mt=GPU.0`）；**CLI** 同 NPU 也自动改 GPU.0 ＋ 日志。`app229` **38/0**（含 3 组反证） |
| **APP-063 ② D2 四入口** | ✅ 全补齐：GUI 启动/`_on_tts_toggled` 自动开旁路 ｜ CLI `follow_speaker` 自动开旁路 ｜ 取消勾选 ⇒ 音色切回「预设 A」＋提示 ｜ 会话进行中**真正拉起线程**（`ensure_started`，状态栏「已即时生效，无需重启会话」） |
| **APP-063 ③ D1 窗口** | ⛔ **App 侧已同源（5.0，未写第二份默认值）**，但 **ASR 内核 `asr052_spk_runtime` 仍写死 10 s**（`WIN_N=160000`/`N_FRAMES=589`/`FPS=58.9`）⇒ **跨模块错位**（`app230` 7 PASS/**5 FAIL**）⇒ 已发 `shared/NOTICE_app_to_asr_spk_window_5s_alignment.md` 给 ASR；**v2.3 建议暂缓发布** |
| **APP-064 锁纪律** | ✅ 设备级作业**先拿 `MACHINE_LOCK` 再跑** ＋ **先探安静窗口**（75 s 后取得 45 s 安静；用户 v2.1 GUI CPU 增量实测 0 s/6 s）；`app223 --run` 指向**本轮影子包**（硬链接自 v2.2 ＋ 同步本轮 2 个改动文件）⇒ **测的是本轮代码** |
| **APP-065 A 界面重排** | ✅ **5 组竖排 GroupBox**（①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级）＋ 组内统一网格（**标签列右边缘 4 组全 56 px @100 % / 76 px @150 %**、**控件列全 233 px**、行高一致）＋ **4 张截图**（100 %/150 % × 启动后/配音开启后，`results/app/app065a_shots/`）＋ **控件→所在组清单**（`app231_app065a_control_group_map.txt`）⇒ **需 reviewer 复核**（reviewer 明文「截图先交 reviewer，通过后才打包」） |
| **APP-065 B 改名** | ✅ 「说话人识别」→ **「区分说话人（用于克隆）」**，**移入「⑤ 高级」**，带提示；**变量名 `var_speaker` 不变**（`app227`/`app204` 依赖） |
| **设备级实测**（APP-063 ④） | 🔄 已跑完：**7 PASS / 4 FAIL / 4 NONE**（证据 `results/app/app233_device_acceptance_evidence.json`）。✅ 相对 v2.1 实质进步：**定时克隆更新 27 次 → 0**、**「没有可用音色」= 0**（APP-061①「全程无声」已消除）。❌ ⑤-① **clone 占比 0 %**（根因＝**本机无克隆引擎**，⇒ APP-065 C 在本机**无法判定**，≠ 不合格）｜❌ ③-③ ASR RTF 增量 **+0.122 > +0.10** ｜❌ ④-② 声纹无 new_spk 配对（与 10 s 窗口延迟一致）｜🔴 **判据①曾是假 PASS**（正则漏了 `没有可用引擎`）⇒ **已修**（`app223`，自检 5/0） |
| **回归** | `app229` 38/0 ｜`app227` 34/0 ｜`app165` **PASS**（C4 口径按 APP-065 A 更新为 5，**C3/C5/C6 未动** ⇒ APP-048 核心不变量保住）｜`app220/226/228` 39/10/8 全 PASS ｜`app219` 11 PASS/2 FAIL（**仅 G2**：字幕区 **66.88 % < 70 %**）｜`app215` 27 PASS/2 FAIL（**与本轮无关**：HEAD 版同脚本跑出相同 2 条 ⇒ 既有缺陷） |
| **待 reviewer 裁定** | ① D1 跨模块错位（需 ASR 同源；含「seg IR 是否已导成 5 s 形状」）② **70 % 字幕区 vs 5 组竖排**（实测 66.88 % ⇒ 选「接受」还是「允许 ④ 组第二个标签列」）③ app215 的 2 条既有 FAIL 是否顺手修 ④ 判据①「三条故障串」口径 ⑤ `app230` D1-6（客户包须含 `asr_spk_window.py`） |
| **未做 / 未交付** | ⛔ **未打包 v2.3**（reviewer 明文「截图先交 reviewer，通过后才打包」⇒ 本轮停在复核点；且 ③ 未解前也不该打包）｜⛔ 未通知用户／未改桌面快捷方式｜⛔ **v2.1、v2.2 目录与 zip 一个字节都没动**（本轮只建了**影子包** `shared/app065_shadow` 供设备级实测，不是交付物）｜⛔ **未提交任何 `CORRECTIONS_*.md`**（本模块全程只读）｜⛔ APP-065 C 的「每段克隆音色表 ＋ wav ＋ 相似度」需 CUDA 边车环境；APP-063 ③(e) 的 CPU 卸载 A/B 本轮未做 |


#### ⑩ 🔄 **设备级实测（APP-063 ④）—— 已跑完（影子包 ＝ 本轮代码）：7 PASS / 4 FAIL / 4 NONE**

🔴 **纪律**（APP-064）：先拿 `MACHINE_LOCK`（`app PID 26476 started 2026-11-02 20:59:25`）⇒ 再等安静窗口（**75 s 后取得 45 s 安静**；用户 v2.1 GUI 的 CPU 增量实测 **0 s/6 s** ⇒ 不算干扰）⇒ 才开始。
🔴 **测的是本轮代码**：影子包 `shared/app065_shadow`（硬链接自 v2.2 ＋ 同步本轮 2 个改动文件，自检 PASS）。证据 `results/app/app233_device_acceptance_evidence.json`（28 123 B）。

| 判据 | 结果 | 实测 |
|---|---|---|
| ①「没有可用音色」= 0（preset / clone 臂） | ✅✅ | 0 / 0（⚠️ 见 ⑪：**曾是假 PASS**） |
| ①b CUDA 边车 REQ 数 | 无法判定 | 本机**无 CUDA 运行时** ⇒ CUDA 臂跑不了（≠ 不合格） |
| ③-① 句内欠载总和 ≤ 0.5 % | ✅ | 0 ms（限 1500） |
| ③-② ≥95 % 句子 uf = 0 | ❌ | `n_sent_uf_zero=0`（**取不到句子级 uf** ⇒ 疑口径问题） |
| ③-③ ASR RTF 增量 ≤ +0.10 | ❌ | **+0.122**（0.756→0.878）**超限** |
| ③-④ 丢句 = 0 | ✅ | 0（76 行） |
| ③-⑤ TTS 首包延迟 | 报告 | **P50 0.5651 s / P95 0.7024 s** |
| ④-① 声纹计算 ≤ 2×说话人 | ✅ | 1（说话人 1） |
| ④-② 声纹计算 ±1 s 内有 new_spk 配对 | ❌ | `n_paired=0` / `n_unpaired=1` |
| ④-③ 定时克隆更新 = 0 | ✅ | **0 次（v2.1 的 27 次已归零）** |
| ⑤-① `voice_kind=clone` 占比 ≥ 80 % | ❌ | **0 %**（76 句全 preset）⇒ 见 ⑪ |
| ⑤-② no_spk_label 回落 ≤ 2×说话人 | ✅ | 0 |
| ⑤-③ reviewer 主观核对 | 人工项 | 76 句待抽听 |
| ③(e) CPU 卸载候选 A/B | 无法判定 | 本轮未做（需 GUI+CLI 各一次、ABBA、持锁） |

✅ **相对 v2.1 的实质进步**：④-③ 定时克隆更新 **27 次 → 0**；①「没有可用音色」= 0 ⇒ **APP-061① 的「全程无声」已消除**。

#### ⑪ 🔴 **设备级实测暴露的 3 个问题（本轮新发现）**

1. 🔴 **判据①曾是「假 PASS」** —— 正则只抓 `没有可用的音色`，而**实测**故障串是 **`🔴 没有可用引擎 ⇒ spk 音色登记失败`**（`tts_worker.py:3805`）与 **`⚠️ 没有可用引擎 ⇒ 克隆无法生效`**（`:3763`）⇒ **抓不到真实故障** ⇒ 已把正则扩成**三条**（`app223` 已修，自检 5/0）。
2. 🔴 **⑤-① clone 占比 0 % 的根因 = 本机没有克隆引擎**（CUDA 边车不在本机）⇒ **APP-065 C「克隆有效性」在本机客观无法判定**（≠ 不合格）⇒ 需带 CUDA 边车的环境才能出「每段用了哪个克隆音色」的表 ＋ wav ＋ 相似度。
3. 🔴 **影子包旁路仍是 10 s**（日志 `说话人旁路窗口：10.000 s`）⇒ 因影子包 `app/asr_spk/` **只有 3 个文件**（**不含 `asr_spk_window.py`**）⇒ **实证 `app230` 的 D1-6**（客户包不含唯一事实来源 ⇒ 客户机退回 10 s）；且 ④-②「声纹无 new_spk 配对」与「`第 0 段无说话人标签：async_pending`」都与**10 s 窗口延迟**一致 ⇒ **D1 跨模块同源是克隆生效的前置条件**。

#### ⑫ 📌 **收尾复核（本轮实测）**

| 文件 | SHA256 | 字节 | mtime | 条数 |
|---|---|---|---|---|
| `status/app/CORRECTIONS_APP.md` | `0b9cf6227e22fd57f791f7f4bfe16c360b25d2d74b9db3a14de1844a3f4aa033` | 182008 | 2026-11-02 14:55:36 | **65** |

⇒ **本模块全程只读** `CORRECTIONS_APP.md`（未写入、未提交）⇒ **与开工基线逐字相同**（SHA 未变）。
