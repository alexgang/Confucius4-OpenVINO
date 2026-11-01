# STATUS_APP

last_ack: APP-058
更新时间: 2026-11-01 20:45
当前任务: **§124 ✅ APP-055 / APP-056 / APP-057 / APP-058 已执行完毕**（`last_ack` APP-054 → **APP-058**）—— ① **APP-055**：v1.13 目录被改的 **6 个文件**已全部还原（`app207` **6/6**；payload 重算 `files=14212` / `bytes=13689629685` 与 06:08 记录**完全一致**；旧 zip **不删不改**）⇒ 此后**不用 `--same-version`**，新产物只走「新版本号目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED」② **APP-056**：自动化指令已插「第 0 步 模块租约」；本轮 **TAKEOVER** 后持 token `8afc6c0f`，长作业（解压 PID 15792 / 打包 PID 3396）全部后台启动并登记 ⇒ **收尾 release**③ **APP-057**：交付包 **v2.1**（zip **11 233 135 359 B** / **14 317 文件** / SHA256 `835803a7…aaa4` / 20:38:13）；闸门 `app191` **18/0** ＋ `app213` **15/0**（含新增的 EXT-029 两条）＋ `app212` **9/0** ＋ `app214` **4/0**（reviewer 点名的 5 个开发目录 **0** 命中）；**v2.0 目录与 zip 原样保留**④ **APP-058**：同段复测（3291.6–3591.6 s）覆盖率 **93.75 %**（ref 95.65 % ⇒ Δ 1.90 pp）、不同标签 **4**、置换一致率 **64.29 %**、APP-054 三项全过 ⇒ **7 PASS / 1 FAIL**；🔴 **换人点召回率 33.33 %（口径A）/ 58.33 %（口径B）⇒ 未达 60 %**（不换口径）⑤ 本轮抓到并修掉 **4 个判据自身缺陷**（漏扫 docstring / 恒假覆盖判据 / marker 口径混淆 / `pkg_dir` 写死构建机家目录）
阻塞 / 待用户决定: ① 🔴 **APP-057 ⑤(b) 未做**（桥接 + Edge 加载插件 + player 录 60 s 网页配音 ⇒ **需用户手势**：Edge 加载已解压扩展 ＋ 点扩展图标 ＋ player「开始捕获」）⇒ 配音录音与逐段译文待用户实听；② 🔴 **APP-058 判据④ 召回率未达标**（33.33 % / 58.33 %，均 < 60 %；参照标注自身与人工标注就差 1 处 ⇒ 上限 91.7 %）⇒ **如实记录、未换口径**，根因指向 ASR 侧说话人切换判定；③ 🔴 **交付版本号是 v2.1 而非用户原话的 V2.0**（v2.0 首包违反 ③，且「旧 zip 不覆盖」）⇒ 请 reviewer 确认 v2.1 即交付版（改名/重签**不需要**重打包）；④ 🔴 **v2.1 上尚未重跑 ⑤(a) A/B**（本轮 A/B 跑在 v2.0 上，而 v2.1 的 `app/` 生产模块与 v2.0 **只差** `speaker_assets.py` 的注释）⇒ 闭环需再跑一次；⑤ 🔴 **桌面仍残留 `实时配音桥接服务 v2.0.lnk`**（指向被取代的 v2.0 包；快捷方式闸门刻意不删旧链）⇒ 请用户/reviewer 决定是否清理；⑥ 🔴 **需用户实听 3 段 1.2–1.3× 配音素材**（`C:\Users\Trekker-PTL\shared\app_accel_listen\`）＋ reviewer 判定音质 / 不变调 / 可懂；⑦ 🔴 **APP-054 的 NOTICE 待主会话转达 ASR**（治本项：`run_seg_side` 每次调用重编译模型）；⑧ 🔴 **§123 待复核项**（GUI 正式行的 `[Sx]` 前缀取不到图 / `app179` B4 空真 / APP-048 运行中截图仍缺）本轮未动；⑨ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读；开工 SHA256 `89018d17…d920d` / 145 700 B / mtime 15:49:35 / 58 条目 ⇒ 收尾**复核零改动**）；⑩ 🔴 已写 `shared/NOTICE_app_to_ext_devpath_leak.md`（EXT 侧 `ext/bridge/*.py` 的 docstring 里仍有开发机绝对路径）**待主会话转达 EXT**
已压缩: 本文件 39296 B / 288 行（APP-052 ④ 限额 ≤ 40 000 B / ≤ 300 行）；**§109–§122 正文已原样归档**到 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`（116062 B，SHA256 `249eae7c31e396e339b83333cbeb6c90af85ad02de01777aca9023c10d817403`）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`


## 最近更新
- 2026-11-01 20:45 **§124 APP-055 / APP-056 / APP-057 / APP-058 已执行** ⇒ ① **v1.13 目录还原**（6/6；payload `files=14212` / `bytes=13689629685` 与 06:08 记录一致；旧 zip 不删不改）② **模块租约**（TAKEOVER 后持 `8afc6c0f`；长作业后台 + 登记 PID）③ **交付包 v2.1**（zip **11 233 135 359 B** / **14 317 文件** / SHA256 `835803a7…aaa4` / 20:38:13；`app191` **18/0** ＋ `app213` **15/0** ＋ `app212` **9/0** ＋ `app214` **4/0**；**v2.0 原样保留**）④ **同段复测**（3291.6–3591.6 s）覆盖率 **93.75 %**（Δ 1.90 pp）、不同标签 **4**、置换 **64.29 %**、APP-054 三项全过 ⇒ **7 PASS / 1 FAIL**；🔴 召回率 **33.33 %/58.33 % ⇒ 未达 60 %** ⑤ 修掉 **4 个判据自身缺陷**
- 2026-11-01 16:25 **§123 APP-052 / APP-053 / APP-054 全部执行完毕** ⇒ ① `.lnk` 坏链已修（COM 生成 ＋ COM 读回判据 ＋ 3 条反证 ⇒ `app192` **13/0**）② `ACCEPTED.json` 重签（`code_fingerprint` + 6 子项 ＋ `1b`）＋ **v1.13 重打**（**11 232 363 846 B** / 14 192 文件 / SHA256 `a13bee66…47db8` / 15:02:24）⇒ `app186` **34/0** ③ `results/mt2_acc_outputs/` 已排除（zip 内 **0** 命中）＋ docstring 路径 → `<HOME>` ＋ 打包闸门又抓到 **2 类真缺陷**（7 脚本写死包路径 / 2 个 U+FFFD 乱码）已修 ④ STATUS 压缩 ≤40 KB/≤300 行 ⑤ **说话人标签覆盖率 7.23 % → 93.48 %**（43/46；差 2.17–4.35 pp ⇒ ≤5 pp）⇒ `app202` **9/0**；顺带订正 `app195` 的 **M8 恒假判据**（置换后 82.61 %）⑥ **旁路默认关闭 ＋ 线程化 ＋ 攒整窗 ＋ 降级** ⇒ A/B：旁路开 **300.6 s / 积压 1.2 s / 延迟 316 ms**（vs 缺陷态 838.5 s / 195.1 s）⇒ **4/0**；🔴 根因在 **ASR 侧**（`run_seg_side` 每次调用重编译 ⇒ 3 000 次编译 ≈ 538 s）⇒ 已写 NOTICE 待转达
- 2026-11-01 08:09 **§122 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 按 APP-046 继续做，补上 **「验收证据 ↔ 被验收代码」绑定这一维** ⇒ 🔴 **真实缺口**：`ACCEPTED.json`（00:43:32）之后 §120（`aacb2dd`，05:57:04）改了客户包 **5 个生产模块**、zip 06:08:44 重打 ⇒ **交付代码 ≠ 被验收代码**、`accepted=true` 仍成立 ⇒ **无闸门会发现**；⇒ ✅ **新增 `app191`**（R1 漂移检测 / R2 漂移分类 / R3 声明自洽 / R4 指纹连续性）⇒ 5 个漂移模块**全部** `home_path_rewrite` ⇒ **良性**；⇒ 集成进 `app186` 为**第 ⑥ 子项**（**25/0 → 26/0**）
- 2026-11-01 06:32 **§121 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 抓到 2 个「判据自身缺陷」（弱判据误报 + 过期断言）⇒ `app076` 修回 **49/0**；`app092` 的 C2 子串匹配弱判据已修
- 2026-11-01 06:21 **§120 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 闭环「客户包内代码写死开发机家目录」这个真实缺陷 ＋ 修掉两个 TTS 验收脚本的「过期断言」
- 2026-11-01 02:35 **§119 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 补上「包 ⇄ 仓库 生产模块集合一致性」这一维（新增 `app188` 闸门）
- 2026-11-01 02:26 **§118 无新纠偏条目（`last_ack` 仍 APP-051）** ⇒ 抓到 **3 个真缺陷**：① §117 验收链产物一个都没入库 ② HEAD 上 fresh clone 打包必失败 ③ 验收链脚本「写死仓库根」导致 clone 验收是假象
- 2026-11-01 01:07 **§117 APP-051 三条子项全部完成** ⇒ ① 重打 v1.13 ② APP-043 真机验收 5 子项全 PASS（`app186` **25/0**）③ 写 `ACCEPTED.json` + 桌面快捷方式更新到 v1.13
- 2026-10-31 10:32 **§115 APP-050 TTS 启动日志打印各组件 `EXECUTION_DEVICES`** ⇒ talker / cp_prefill / cp_decode / decoder **首次被探测** ＋ `absent`/`unknown` 分离 ＋ **实测全部 NPU**
- 2026-10-30 23:20 **§114 APP-027 V3(a) MiniMax 回转写 CER 对比（克隆 vs 预设 A）** ⇒ **14 PASS / 0 FAIL** ⇒ Δ = **+0.0657 pp**、95% CI **含 0** ⇒ **未构成明显劣化**
- 2026-10-30 22:28 **§113 修掉「版本标识在打包时复发」的路径** ⇒ 新增打包前闸门 `app170`（**18 PASS / 0 FAIL**，BUG 组 D1~D5 全部命中）
- 2026-10-30 20:41 **§112 客户包「运行时可加载性」独立验收** ⇒ `app168` **21 PASS / 0 FAIL** ⇒ 抓到**宿主 `PYTHONPATH` 污染**（会让 `torch` 假阳性）
- 2026-10-30 18:55 **§111 APP-049 压缩完成** ⇒ STATUS **1 437 968 B / 18 977 行 → ≤ 40 KB / ≤ 300 行**（**−99.0 %**）
- 2026-10-30 16:52 **§110 APP-048 GUI 三分区状态条落地** ⇒ `app165` **64 PASS / 0 FAIL**；三张截图落盘 `shared/app_gui_layout/`
- 2026-10-30 16:00 **§109 APP-047 说话人 IR 精度定案 FP16** ⇒ `asr_spk/` 收敛为 **3 个文件**；`app164` **30 PASS / 0 FAIL**

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

- §97 的「APP-039/040 核心已实施」在 §98 补交入库后**才**成立 ⇒ 见 §98。
- §103.4 的「4 产物已入库」当轮**不准确**（只入了脚本，证据由 §104 补交）⇒ 见 §105.4。
- §104.6 的「宿主后台任务有 16 分钟上限」实为**守候器自身退出**，非宿主强杀 ⇒ 见 §105.2。
- §122 头部「客户包 zip 是 06:08 那份」的 SHA `3ca36ce3…e020` **已作废**（本轮重打）⇒ 见 §123。
- §122 头部「桌面 .lnk 554 B」**已作废**（那是**坏链**，554 B）⇒ 现为 **2 099 B**（COM 生成）⇒ 见 §123。


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

> 按 APP-052 ④：**每节最多 3 行的索引**；**§109–§122 正文已原样归档**到 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`（**逐字保留，内容一字未删**）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。

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
| §124 | **APP-055/056/057/058**：v1.13 还原 ＋ 模块租约 ＋ V2.1 交付包 ＋ 同段覆盖率复测 | **本轮新增（见下）** |

### §123 ✅ **APP-052 / APP-053 / APP-054 —— 桌面 `.lnk` 坏链修复 ＋ `ACCEPTED` 重签 ＋ 说话人标签覆盖率 7 % → 93.48 % ＋ 旁路线程化止血 ＋ STATUS 压缩** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec123_upto_20261101.md`（逐字保留，内容一字未删）。

### §124 ✅ **APP-055 / APP-056 / APP-057 / APP-058 —— v1.13 还原 ＋ 模块租约 ＋ V2.0→V2.1 交付包 ＋ 说话人覆盖率同段复测** ｜ **本条已执行** ｜ **本条需等 reviewer 复核**

> 本节只追加，不改旧章节；旧结论若被推翻，在本节写明「撤回 §x」。

#### ① APP-055（BLOCKING）—— 原地改包 ＋ 同版本号覆盖重打 ⇒ 已止血

* v1.13 目录被改动的 **6 个文件**，逐个「改前 SHA（= 06:08 态）→ 改后 SHA（被改坏）→ 还原后 SHA」
  （`results/app/app207_app055_restore_v113_evidence.json` → `changed[]`，`n_changed=6` / `n_restored_ok=6`）：

| 文件 | 改前 SHA（06:08 态） | 改后 SHA（被改坏） | 还原后 SHA | ok |
|---|---|---|---|---|
| `app/live_caption_app.py` | `9f37a399b2b3…` | `b65e311f9a93…` | `9f37a399b2b3…` | ✔ |
| `app/speaker_assets.py` | `1576ac8559e1…` | `17c1f39c945a…` | `1576ac8559e1…` | ✔ |
| `app/speaker_tracker.py` | `ecb3bd6b7f09…` | `5dd215f4ea03…` | `ecb3bd6b7f09…` | ✔ |
| `app/tts_cuda.py` | `bfde75221a04…` | `7d0d886d85cb…` | `bfde75221a04…` | ✔ |
| `app/tts_cuda_sidecar.py` | `269d02f31990…` | `84110917d44c…` | `269d02f31990…` | ✔ |
| `ACCEPTED.json` | `fc31e1b57597…` | `8c6bc81d0879…` | `fc31e1b57597…` | ✔ |

* 还原基准 = git `aacb2dd` 的 blob：**06:08 那份 zip 本体已在 15:02 被 `--same-version` 覆盖 ⇒ 字节流不可得**
  ⇒ 只能用 blob ＋ 字节数算术复原（`app207` → `note`）。
* **payload 重算与 06:08 记录完全一致**：`files=14212` / `bytes=13689629685`（`payload_recheck.match=true`）
  ⇒ 目录已回到 06:08 态。
* 旧 zip **不删不改**（`zip_untouched=true`）：v1.13.zip（15:02 / SHA `a13bee66…`）、v2.0.zip（17:49 / SHA `8198924f…`）原样保留。
* **纪律落地**：此后**不再用 `--same-version`**；新产物一律「新版本号目录 ＋ 新 zip ＋ 新 MANIFEST ＋ 重签 ACCEPTED」
  （本轮 v2.1 即按此执行）。

#### ② APP-056（HIGH）—— 模块租约：指令已改，本轮全程持租约

* 指令侧：App 自动化指令已在「第 1 步」**之前**插入「第 0 步 · 模块租约（APP-056）」（全文见 ⑪）。
* 本轮 `acquire app` ⇒ **TAKEOVER**（上一会话 token `7cc116e8` 17:48 失心跳，其登记的 5 个 PID 全部已死）
  ⇒ 本轮 token **`8afc6c0f`**，从断点继续（读了它的 note「V2.0 打包压缩 10.6/12.75 GB」＋ §123 ＋ 全部产物，**没有从头重做**）。
* 长作业全部后台启动并**登记 PID**（`app214` 解压 PID 15792、`pack_v13` PID 3396）⇒ 下一轮会拿到 BUSY 而非重复启动。
* 收尾 `release app 8afc6c0f`。

#### ③ APP-057（HIGH）—— V2.0 → V2.1 交付包

* **① 新目录 / 新 zip / 新 MANIFEST / 重签 ACCEPTED** = **v2.1**
  （目录 `Confucius4_LiveCaption_v2.1`；zip **11 233 135 359 B** / **14 317 文件** / SHA256 `835803a7…aaa4` / mtime **2026-11-01 20:38:13**）。
  **v2.0 的目录与 zip 原样保留、不覆盖、不删除**。
* **② 包内结构**：`app/`（App 本体）＋ `ext/extension/`（插件 unpacked，15 个文件 / 219 021 B）＋
  `ext/bridge/`（19 个 .py ＋ `start_bridge.cmd`）＋ `ext/.runtime_deps/`（websockets 17.3 / psutil 7.2.2）
  ＋ `README_插件.md`（4 697 B，引用 `docs/插件截图/` 3 张截图，**已核实文件在包内**）
  ＋ `NOTICE`（9 643 B）＋ `THIRD_PARTY.md`。
  * **桌面快捷方式选「两个 .lnk」**（不选「App 内加启动桥接的开关」）：① 桥接必须用**包内 python ＋ 包内模型** ⇒ 启动方式与 App 根本不同；
    ② 两者**设备互斥**（`ext/bridge.py::_caption_app_running`）⇒ 常需只起一个；③ 桥接可能**先于** App 启动（用户只想看网页配音）。
    ⇒ `Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`（均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证）
    ⇒ `app212` **9 PASS / 0 FAIL**（含 3 条反证）。
* **③ 依赖隔离**（在**另一个路径**解压 zip 后扫，不是扫包目录）：`app214`（判据已修，见 ⑤）
  ⇒ **reviewer 点名的 5 个开发目录 0 命中**；扫描面 **6 729 个文件**（自有 93 ＋ 第三方运行时 6 636，后者亦 0 命中）。
  🔖 **证据留痕**：v2.0 那次跑的 `app214…v20_clean_test_evidence.json` 被本轮同名覆盖 ⇒ 其**控制台输出已另存**
  `results/app/_app214_run_v20_oldcriterion.txt`（当时为 **1 PASS / 2 FAIL** ＝ **旧判据**下的结果：只命中 `ACCEPTED.json` 的 `pkg_dir` ＋ 覆盖判据恒 FAIL）；
  本轮 v2.1 的权威证据 = `results/app/app214_app057_v21_clean_test_evidence.json`（**4 PASS / 0 FAIL**）。
* **④ 闸门**：`app213` **15 PASS / 0 FAIL**（含 **8/8** 反证）—— 包内无会议录音 / 克隆音色 / babelvox 示例音色；
  NOTICE 含 **pyannote_seg**（CC BY 4.0）＋ **wespeaker**（MIT）署名与来源链接；
  App 侧旁路**默认关** ＋ **独立线程** ＋ CLI `--speaker` 默认 off；
  **EXT 侧旁路满足 EXT-029**（`threading.Thread` ＋ `daemon` ＋ 队列满即丢弃并计数 ⇒ 不反压）——**本轮新增的两条检查**。
* **⑤(a) A/B（旁路开/关，各跑一次）**：`app208`，用**包内 python**、音频 = app193/app175 的**同一段** Q&A 切片
  （3291.6–3591.6 s）⇒ 旁路开 **墙钟 300.7 s**（上限 303）/ **最大积压 1.2 s**（上限 2）/ **出字延迟中位 347 vs 343 ms（Δ +4 ms**（上限 +200）/
  **丢窗·降级 0** ⇒ 三项全过；另跑一次 `--speaker off` 作对照（300.9 s / 1.4 s / 343 ms）。
  ⚠️ **v2.1 的 `app/` 生产模块相对 v2.0 只差 `speaker_assets.py` 的注释**（`code_fingerprint`：`eeafd13b…` → `b96b6725…`）
  ⇒ 旁路代码**逐字节未变** ⇒ A/B 结论对 v2.1 成立；**但闭环仍需在 v2.1 上再跑一次**（本轮未跑，见 ⑧①）。
* **⑤(b) 桥接 + Edge 加载插件 + player 录 60 s 网页配音 ⇒ 未做**（**需用户手势**：Edge 加载已解压扩展 ＋ 点扩展图标 ＋ player「开始捕获」；
  EXT 侧同样记「tabCapture 生产路径未实测」）⇒ **如实记为未达成**。
* **⑤(c) zip 报告**：**11 233 135 359 B / 14 317 个文件 / SHA256 `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`**
  （`results/app/DELIVERY_2.1.json`；`testzip()` = Everything is Ok；zip ⇄ 包目录 **14 317 个文件逐字节一致**；压缩 556 s / 压缩率 82.1 %）。
* **⑥ 未通知用户安装**（(a)(b) 未齐 ⇒ 按 reviewer 指令不通知）。

#### ④ APP-058（HIGH）—— 覆盖率同段复测 ＋ A/B 复核

* **① APP-054 的 A/B：reviewer 已核实 ⇒ 认可**；本轮在**多人音频**上又跑一遍并补齐指标。
* **② APP-053 的「93.48 %」不成立 ⇒ 撤回 §123 的该结论**（分子取自 on 臂的**单人**段 `SPE_0000_0500.wav`，
  分母取自 **Q&A 段** ＋ pyannote 参照 ⇒ 分子分母不同段）。
  本轮**同段复测**（`app208`，切片 = app193/app175 的 **3291.6–3591.6 s**）：

| 指标 | 实测 | 判据 | 结论 |
|---|---|---|---|
| 覆盖率（分子分母同段） | **93.75 %**（45/48 句带标签） | 与 ref 95.65 % 相差 ≤ 5 pp（**Δ 1.90 pp**） | ✅ |
| 不同标签数 | **4**（S1/S2/S3/S4） | ≥ 3 | ✅ |
| 最优编号置换一致率（**实际运行**标签上算） | **64.29 %** | —（报数） | 📌 |
| 换人点召回率（±1 段算命中） | 口径 A **33.33 %**（4/12 命中、误报 3）／口径 B **58.33 %**（7/12、误报 0） | ≥ 60 % | ❌ **未达标** |
| APP-054 墙钟 / 积压 / 延迟 Δ / 丢窗降级 | 300.7 s / 1.2 s / +4 ms / 0 | 303 s / 2 s / +200 ms / — | ✅ |

  ⇒ `app208` **7 PASS / 1 FAIL**（`verdict=FAIL`）⇒ **不换口径、不粉饰**。
* **判据④的鉴别力诊断**（`app210`）：口径 A 按 app208 的段号对齐、口径 B 按**文本对齐**后比对；
  **参照标注自身**与人工标注就差 1 处（人工多一个换人点 @19）⇒ 即便完美实现，召回上限也只有 **11/12 = 91.7 %**；
  实测口径 B 已达 **58.33 %** 且**零误报**。剩余漏检的根因在 **ASR 侧的说话人切换判定**（与 APP-054 NOTICE 同一治本线）
  ⇒ 本轮**未自行改口径**，如实记录待复核。
* **③ §123 ⑥-4 的说法撤回**：原文「未在用户正在测试的安装目录里原地改文件」**不成立**
  （reviewer 实测 v1.13/app/ 三个文件被改成 14:33/14:37 版本，v1.13.zip 又在 15:02 同版本号重打）
  ⇒ 本轮按 APP-055 还原 v1.13，并自此只用新版本号发包。

#### ⑤ 本轮抓到的 4 个「判据自身缺陷」（判据 PASS ≠ 判据正确）

| # | 缺陷 | 后果 | 修法 |
|---|---|---|---|
| 1 | `app214`/`app209` 只扫「AST 字符串字面量且**排除 docstring**」 | 首包 v2.0 里 `ext/bridge/{engines,segmenter,app_root}.py` 的 docstring **写死开发机绝对路径**（4 处）**被判为通过** | 改**全文扫描**（注释/docstring 也算）＋ `.lnk` 额外按 UTF-16LE 再解一份（真实 .lnk 是二进制） |
| 2 | `app214`「四类扩展名都必须扫到」 | 包内本就没有 `.lnk` ⇒ **恒 FAIL**（恒假判据） | 改三态：**存在即必扫；不存在记「不适用」** |
| 3 | `app214` 把「构建机用户名」与 reviewer 点名的 5 个开发目录混成一条 | 「是否违反 ③」被口径混淆 | 拆成**阻断**（5 个开发目录）＋**附带发现**（构建机用户名，不阻断） |
| 4 | `app211` 把构建机家目录写进 `ACCEPTED.json` 的 `pkg_dir`；`app191` R3 按字面比 | 客户机上路径不对 ＋ 泄漏构建机身份 | `pkg_dir` 改 `<HOME>` 形态；R3 改成「**先展开 `<HOME>` 再比**」 |

#### ⑥ 交付口径（v2.1）

* `app/` 生产模块 **28** 个，内容指纹 `b96b6725944c8d19aa9a4a980dee2ac370c6922a19fe7204abae7270b8a9b421`
  （v1.13 为 `09a1f417…`；差异**只有** `speaker_assets.py` 的注释脱敏）。
* `ACCEPTED.json`：**6 067 B**，`pkg_dir` = `<HOME>\Confucius4_LiveCaption_v2.1`，`binding_gate=app191`，
  白名单 **5 条**（每条带 `reason` ＋ `source`）。
* 闸门结果：`app191`（验收 ↔ 代码绑定）**18 PASS / 0 FAIL**｜`app213`（内容闸门）**15/0**｜`app212`（快捷方式）**9/0**｜`app217`（建包 ＋ 脱敏）**7/0**。

#### ⑦ 本轮对仓库的改动（**只有 App 侧**）

* `live_caption/speaker_assets.py`（注释脱敏 1 处）｜`live_caption/release_notes/v2.1_{zh,en}.md`（新增）
* `results/app/app209`（EXT 复制：扫描改全文）｜`app211`（`pkg_dir` → `<HOME>`）｜`app212`（快捷方式版本号**改为派生**）
  ｜`app213`（＋ EXT-029 两条检查 ＋ 两条新反证）｜`app214`（判据修复 ＋ `--skip-extract` ＋ 二进制 .lnk）｜`app217`（**新增**：建 v2.1 ＋ 脱敏）
* 🔴 **未提交**：`status/app/CORRECTIONS_APP.md`（reviewer 独占）、ASR/MT/TTS 其它模块的任何文件。

#### ⑧ 待 reviewer 复核 / 未达成（不粉饰）

① **APP-057 ⑤(b) 未做**（需用户手势）⇒ 配音录音与逐段译文待用户实听。
② **APP-058 判据④ 召回率未达标**（33.33 % / 58.33 %，均 < 60 %）⇒ 如实记录。
③ **交付版本号是 v2.1 而非用户原话的 V2.0**（v2.0 首包违反 ③，且「旧 zip 不覆盖」）⇒ 请 reviewer 确认 v2.1 即交付版；
若必须叫 V2.0，请授权改名/重签（**改名不需要重打包**）。
④ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（指向被取代的 v2.0 包）—— App 的快捷方式闸门刻意不删旧链 ⇒ **请用户/reviewer 决定是否清理**。
⑤ 沿用 §123 待办：3 段 1.2–1.3× 配音素材实听（`shared/app_accel_listen/`）；APP-048「运行中」截图仍缺；
APP-054 的 NOTICE（ASR 侧 `run_seg_side` 每次调用重编译模型）仍待主会话转达。
⑥ **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读文件）—— 复核见 ⑨。

#### ⑨ 收尾复核（`CORRECTIONS_APP.md` 全程只读）

* 开工记录：SHA256 `89018d172afc1e570a833d961a32355ebb1416fbf9d20f6f104a86f4217d920d` / **145 700 B** /
  mtime **2026-11-01 15:49:35** / `## APP-xxx` 条目 **58** 条（APP-001…APP-058）。
* 收尾复核：SHA256 / 字节数 / 条目数 **均不变** ⇒ **本轮 reviewer 未中途追加新条目**；本文件**零改动**。

#### ⑩ 撤回清单

* **撤回 §123 中「APP-053 说话人标签覆盖率 93.48 %（43/46）」**（分子分母不同段）⇒ 以 ④ 的同段复测 **93.75 %** 为准。
* **撤回 §123 ⑥-4「未在用户正在测试的安装目录里原地改文件」** ⇒ 见 ④③。

#### ⑪ 自动化指令（APP-056 ⑤ 要求贴全文）

> **第 0 步 · 模块租约（APP-056）**（插在原「步骤 1」之前）：
> `python C:\Users\Trekker-PTL\shared\tools\session_lease.py acquire app`
> * exit 10（BUSY）⇒ 只输出「上一会话仍在进行，跳过本轮」并**立即结束**（不读文件、不改东西、不碰锁）
> * exit 0 ⇒ 拿到 `TOKEN=xxxx`，后续步骤都带这个 token；若打印 TAKEOVER ⇒ 先读上一会话的 note / STATUS / 产物，**从断点继续**
> * **心跳**：每完成一步、每次耗时操作前后 `session_lease.py beat app <token> <一句话进度>`；exit 11（LOST）⇒ **立即停止、不再写任何文件**
> * **长作业**（打包 / 计时 / e2e）用 schtasks 或 Start-Process 后台启动，拿到 PID 马上 `session_lease.py addpid app <token> <pid>`；
>   不在一个工具调用里同步等待超 20 分钟，分次轮询、轮询之间 beat
> * **收尾**（含「无新纠偏、跳过」）最后一步 `session_lease.py release app <token>`；有后台作业活着时脚本会自动保留租约
> * 🔴 MACHINE_LOCK 规则不变（排队等待，不抢锁）：租约管「同一模块不能有两个会话」，锁管「不同模块不要同时占用设备」

#### ⑫ v2.1 相对 v2.0 的差异（**只有 3 处**）

1. `ext/bridge/{engines,segmenter,app_root}.py` ＋ `app/speaker_assets.py` 的 **8 处**开发机家目录字面量 → `<HOME>`。
2. `ACCEPTED.json`：`pkg_dir` → `<HOME>` 形态 ＋ `accepted_at` 重签 ＋ 白名单 `speaker_assets.py` 的依据补 APP-057 ③。
3. 版本标识：`README_zh` / `README_en` / `NOTICE` / `MANIFEST` → **2.1**，并插入 v2.1 改动说明段。
