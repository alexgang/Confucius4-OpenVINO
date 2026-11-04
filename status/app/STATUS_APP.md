# STATUS_APP

last_ack: APP-067
更新时间: 2026-11-04 21:12
当前任务: **§133 APP-067（①克隆 0 % 根因 / ②APP-065 C 交付物 / ③D4 界面 / ④设备验收 / ⑤D1 5 s 窗口）＋ §134 APP-066（MiniMVP 最小客户包 rc1）—— 代码层与构建层已执行** —— ① **APP-067 ①③⑤ 已完成（设备级）**：`app243` **9 PASS / 0 FAIL**（clone **41/42 = 97.62 %**、带 spk 句 36/42 = 85.71 %、「没有可用引擎」= 0、加载期排队补登记、5.000 s 窗口 45 次）＋ 4 条反证全被抓住 ｜ ② **APP-066 v1.0 的 6 处硬缺陷（含 P0 无法启动）已修** ⇒ 新目录 **`MiniMVP_v1.0-rc1`**（**7 个构建闸门全绿**、10 507 文件 / 6 843.9 MB = v2.2 的 **52.41 %**）
阻塞 / 待用户决定: 🔴 **本轮停在 reviewer 复核点**（APP-067 与 APP-066 都写明「需等 reviewer」）｜⛔ **APP-067 ②④ 的设备级部分未做**（② 每段音色表 ＋ 男/女各 3 段 wav ＋ 原声参考；④ ABBA / GUI 臂 / ASR RTF +0.122 复测）⇒ 需持 `MACHINE_LOCK`（本轮 **ASR 模块持锁**，pid 49688，20:34:25 ⇒ 未抢锁、未占设备）｜⛔ **APP-066 3(a)(b)(c) 未做**（CLI 5 分钟片段指标 ＋ 配音 wav；GUI 冷启动 ＋ 100 %/150 % 截图；**zip 未生成** ⇒ 验收后再打）｜🔴 **待 reviewer 裁定**：① APP-066「不能 import torch」字面口径（包内 app/ 3 处，均在 `backends.py` 的 torch/hybrid 后端 ⇒ 运行不可达；改开发版会波及 v2.x）② MT INT4 质量数据引用口径 ｜🔴 **v2.3 继续暂缓**（APP-067 原文「顺序 1→2→3、4→5→才能打包」）｜🔴 **未通知用户 / 未改桌面快捷方式 / 未改任何 v2.x 客户包目录**（v2.1、v2.2 一个字节都没动）
已压缩: 本文件 35351 B / 181 行（APP-052 ④ 限额 ≤ 40000 B / ≤ 300 行）；**§132 正文已原样归档**到 `status/archive/STATUS_APP_sec132_upto_20261103.md`（逐字保留）⇒ 文件内只留速查行（**本轮新增 §133/§134 为同一惯例**）


## 最近更新
- 2026-11-04 21:12 **§133 + §134 已写** ⇒ **APP-067 ①③⑤ 已完成（设备级，`app243` 9/0 + 4 反证）**｜**APP-066 v1.0 的 6 处硬缺陷（含 P0 无法启动）已修** ⇒ **`MiniMVP_v1.0-rc1`**（7 闸门全绿 / 52.41 % 体积）｜⛔ ②④ 与 (a)(b)(c) 未做（等锁）｜🔴 `CORRECTIONS_APP.md` 零改动（67 条 / SHA `cf71e427…`）
- 2026-11-04 20:41 **§133/§134 开工** ⇒ **两条新纠偏（APP-066 MiniMVP 最小包 / APP-067 克隆 0 % 根因 + D4 + ABBA + D1）**；`last_ack` **APP-065 → APP-067**；**接管上一会话（TAKEOVER，117 min 前失联）**：其 3 个提交（`42b62e7`/`e804108`/`e88e3f1`）已入库但 **STATUS 未写** ⇒ 本轮从断点续做
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
| §133 | **APP-067**：①克隆 0 % 根因（加载期排队 + seg→spk 绑定）＋ ③D4 界面 ＋ ④按钮/高级组截图 ＋ ⑤D1 5 s 窗口 ⇒ **①③⑤ 设备级已完成**；②④ 设备级未做（等锁） | **本轮新增（见下）** |
| §134 | **APP-066**：MiniMVP 最小包 v1.0 的 **6 处硬缺陷（含 P0 无法启动）**已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 构建闸门全绿 / 52.41 % 体积）；(a)(b)(c) 设备级未做 | **本轮新增（见下）** |

### §130 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 自查出并修掉 3 个真缺陷（闸门口径 1 个 ＋ 串音 1 个 ＋ 判据作用域 2 个）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 09:56）

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec130_upto_20261102.md`（逐字保留，内容一字未删）。

### §131 🔄 **APP-062（D1–D4：用户对 APP-061 的四项决定）—— 本条已执行（代码层全部完成）** ｜ **本条需等 reviewer 复核**（2026-11-02 10:58）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec131_upto_20261102.md`（逐字保留，内容一字未删）。

### §132 🔄 **APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 ＋ APP-065 A 界面重排 ＋ B 改名** ｜ **本条已完成（代码层 ＋ 设备级）** ｜ **本条需等 reviewer 复核**（2026-11-03 00:05）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec132_upto_20261103.md`（**逐字保留，内容一字未删**）。

### §133 ✅ **APP-067（①克隆 0 % 根因 / ②APP-065 C 交付物 / ③D4 界面 / ④设备验收 / ⑤D1 5 s 窗口）** ｜ **①③⑤ 本条已完成（设备级）｜ ②④ 的设备级部分未做（等锁）** ｜ **本条需等 reviewer 复核**（2026-11-04 21:10）

> 🔴 **接管上一会话**（TAKEOVER：token `fa098d83`，18:25 起 117 min 无心跳）：它的 3 个提交（`42b62e7`/`e804108`/`e88e3f1`）**已入库但 STATUS 未写** ⇒ 本轮从断点续做；`CORRECTIONS_APP.md` 开工基线 = 收尾实测（SHA `cf71e427…` / 192 381 B / 2026-11-04 09:52:22 / **67 条**）⇒ **本轮零改动**。

| 子项 | 状态 | 证据（原始字段） |
|---|---|---|
| ①(a) worker 加载期丢 `spk_voice` | ✅ 已修（入队 ⇒ 加载完成后补登记） | `app236` → `checks` **9 PASS / 0 FAIL**（9 条反证全被抓住，`n_counterproof_failed_to_detect=0`） |
| ①(b) seg→spk 绑定断点 | ✅ 已定位 = **音色从未登记成功**（不是窗口滞后） | `app235` → `label_vs_submit.A_voice_never_registered=46` / `B_label_after_submit=0` |
| ① **设备级验收** | ✅ **clone 41/42 = 97.62 %**；带 spk 句 **36/42 = 85.71 %**；「没有可用引擎」= **0** | `app243` → `n_pass=9 / n_fail=0 / n_none=0`，**4 条反证全被抓住** |
| ③ D4 界面仍显示 NPU | ✅ 已修（状态栏取真值 `engine_key`） | `app238` → `n_pass=7 / n_fail=0`（含 100 %/150 % 截图） |
| ④ 「有模块待处理」按钮截断 + 高级组截图 | ✅ 已修 | `app238` → G1 像素量按钮宽 95/164/85/164 px（≥ 需求 66/131/58/131） |
| ④ **ABBA / GUI 臂 / ASR RTF +0.122 复测** | ⛔ **未做**（需持 `MACHINE_LOCK`） | 本轮 **ASR 模块持锁**（pid 49688，20:34:25）⇒ 未抢锁、未占设备 |
| ② APP-065 C 交付物（每段音色表 ＋ 男/女各 3 段 wav ＋ 原声参考） | ⛔ **未做**（同上；且需先选一段有男有女的 SPE 片段） | 待办 |
| ⑤ D1 5 s 窗口 | ✅ 包侧落地（`ASR_FILES` 4 项）＋ **设备级实测 log「说话人旁路窗口：5.000 s」45 次** | `app237` → 9 PASS / 0 FAIL；`app243` → 判据⑧ |

🔴 **更正 `app241`**：它的 `ts=2026-11-04 16:58:45` ⇒ 分析的是**修复前**那次运行（影子包 17:08 才建好）⇒ 它的「clone 0 %」**对 17:25 那次运行不成立**；`app243` 是同一判据的**更正版**（切到最新 run）。
🔴 **判据口径坑（新增，写给下一轮）**：`.tts.jsonl` **跨运行累加**（本轮实测 2 段：旧 run 76 句全 preset ＋ 新 run 42 句）⇒ 必须按 `t_submit` 断层切 run（`id` 归零交叉验证一致）⇒ 否则**假 FAIL**（`app243` 的 K1/K4 反证就是防这个）。
🔴 **`app236` 复跑 FAIL ≠ 代码回归**：`real_failure_log_recheck` 依赖 `results/app/app223_device_out/tts_on_clone.log`，而该日志**已被 17:25 的成功运行覆盖**（故障串消失）⇒ 复跑件另存 `app245_regression_rerun_app236_recheck_input_changed.json`；**仓库原证据已 `git checkout` 复原（未覆盖）**。
🔴 **回归复跑口径**：`app215` 必须用**仓库 `.venv`**（WorkBuddy 的 python **无 numpy** ⇒ 27/2 假 FAIL）；换 `.venv` ⇒ **29 PASS / 0 FAIL**（复跑件 `app245_regression_rerun_app215_venv_29_0.json`）。`app227` **34/0**、`app229`/`app237` 复跑**逐字节一致**。

### §134 ✅ **APP-066（MiniMVP 最小客户包）· v1.0 的 6 处硬缺陷已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 个构建闸门全绿）** ｜ **本条已完成（构建层）｜ 设备级验收 (a)(b)(c) 未做（等锁）** ｜ **本条需等 reviewer 复核**（2026-11-04 21:10）

**🔴 v1.0（上一会话建的包）的 6 处硬缺陷**：

| # | 缺陷 | 证据 | rc1 的修法 |
|---|---|---|---|
| **D1（P0）** | **包无法启动**：`live_caption_app.py:121` 顶层 `import clone_collector`，而 v1.0 把它列进了「不带」清单 | v1.0 实测 `ModuleNotFoundError: No module named 'clone_collector'` | **保留** `clone_collector.py`（纯 Python 10.7 KB，App 顶层 import ＋ `_CLONE_*` 常量来源）⇒ 并把**导入冒烟测试做成构建闸门**（G1） |
| **D2** | app/ 是 **v2.2 的旧代码**（2026-11-02 01:33）⇒ 不含 APP-065 界面分组 / APP-067 ①②③④⑤ 修复 | 包内 `live_caption_app.py` mtime | app/ 改从**开发树 `live_caption/`** 取 **17 个生产模块** |
| **D3** | 10 个文件含**开发目录绝对路径** | `app242` → `scan.dev_path_hits` = 10 | 逐文件定点 scrub（`dev_repo`/`asr_module`/`tts_module`/`mt_module`）⇒ 包内命中 **0** |
| **D4** | **torch/CUDA 内容仍在**：OV 的 PyTorch/JAX/Paddle/TF 转换前端（**1 365** 处 `import torch` 命中）＋ `openvino_pytorch_frontend.dll` ＋ `numba/cuda/` ＋ `docs/CUDA_TTS.md` ＋ EXT 插件截图 | `app242` → `torch_import_hits=1365` / `cuda_dlls=1` / `cuda_code_hits=27` | 全部**移出**（大目录用**改名移出**，避免批量删除守卫）⇒ 包内 CUDA DLL **0**、app 内 CUDA 命中 **0** |
| **D5** | **体积口径错**：`app242` 的体积算的是**源包 v2.2**（13.67 GB / 99.84 %）⇒ 误判「最小包没变小」 | 实测 v1.0 = 7.24 GB | 体积分项一律对**已建成的包**现算 ⇒ rc1 = **6 843.9 MB = v2.2 的 52.41 %** |
| **D6** | 没有**新 MANIFEST / ACCEPTED**（包里是 v2.2 的 MANIFEST，且含 `hy_bench` 路径） | 包内 `MANIFEST.json` | 新生成 MANIFEST（`version=1.0-rc1`）＋ 重签 ACCEPTED（`code_fingerprint=5198846a…` / 17 个生产模块） |

**🔴 rc1 的 7 个构建闸门（`app244` → `gates` 全绿）**：G1 导入冒烟 17/17 ✅（**鉴别力**：同一判据在**已知有缺陷**的 v1.0 上 **FAIL** ✅）｜G2 开发目录路径 **0** ✅｜G3 CUDA/torch DLL **0** ✅｜G4 app 内 CUDA 命中 **0** ✅｜G5 包内 app/ == 开发树（17 文件 / **0 差异**）✅｜G6 体积 **52.41 %** ✅｜G7 鉴别力 ✅。

**包体**：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc1`（**10 507 文件 / 6 843.9 MB**；models 6 114.0 / python 728.7 / app 1.2 / docs 0.0）｜模型：ASR **INT8**（encoder 305.1 MB ＋ decoder-gpu 1 661.3 MB ＋ `embed_tokens_f16.npy` 593.5 MB）＋ MT **INT4** `mt2-int4sym-cw-q` 992.3 MB ＋ TTS **唯一一份 IR** 2 546.7 MB（＋ tokenizer/voices/weights）。设备：**ASR/MT = GPU.0，TTS = NPU**；GUI/CLI 无 CUDA 选项。

🔴 **v1.0 目录保留不动**（APP-066「任何已有版本的目录和 zip 都不覆盖、不删除」）⇒ 它是缺陷证据；剔除掉的内容在 `shared/minimvp_rc1_excluded/`（**改名移出**，非删除 ⇒ 不触发批量删除守卫）。
⛔ **未做（需设备级作业）**：3(a) CLI 跑 SPE 英文 5 分钟片段的完整链路指标 ＋ 配音 wav（`shared/app_listen/minimvp_v1.0/`）；3(b) GUI 冷启动（首次 NPU 编译耗时 / 第二次启动耗时）＋ 100 %/150 % 截图；3(c) **zip 未生成**（① 验收未过 ②「用户不通知不打包」）⇒ 预估 zip ≈ 6–6.5 GB（v2.2 的 11.23 GB）。
🔴 **待 reviewer 裁定（口径）**：APP-066 2 节「不能 import torch」的字面口径 —— 包内 app/ 仍有 **3 处** `import torch`（`backends.py` L64 `extract_audio_features` / L145 `TorchBackend.__init__` / L443 `HybridBackend.__init__`）⇒ **torch 本身未随包**（无 torch 目录、无 CUDA/torch DLL）⇒ 这三条是**开发工作流后端**，MiniMVP 走 OV 路线 ⇒ **运行不可达**；改开发版 `backends.py` 会**波及 v2.x** ⇒ 本轮**未擅自改**。第三方库内另有 1 337 处（`huggingface_hub` 的可选 torch 适配层、`openvino/tools/ovc` 的转换器等）⇒ 同样不可达。
🔴 **MT INT4 vs INT8 质量对比**（APP-066 1）：本包用 `mt2-int4sym-cw-q`（**对称 · per-channel weight**）；**开发版已有的 INT4 质量数据未引用到**（在 hy_bench/MT 模块侧）⇒ 已登记进 ACCEPTED 的 `pending_reviewer` ⇒ 待补或由 reviewer 指定口径。
