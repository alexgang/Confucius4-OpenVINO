# STATUS_APP

last_ack: APP-054
更新时间: 2026-11-01 16:25
当前任务: **§123 ✅ APP-052 / APP-053 / APP-054 已全部执行完毕**（`last_ack` APP-051 → **APP-054**）—— ① **APP-052 ①**：桌面 `.lnk` 坏链已修（改用 `WScript.Shell.CreateShortcut` 生成 ＋ 判据改为 COM 读回 ＋ 3 条反证 ⇒ `app192` **13 PASS / 0 FAIL**）② **APP-052 ②**：`ACCEPTED.json` 已按 **app191 口径**重签（`code_fingerprint` + `binding_gate=app191` + **6 个编号子项 ①–⑥ ＋ `1b_lnk_shortcut`**）⇒ **zip 已按 `--same-version` 重打**（**11 232 363 846 B** / **14 192 文件** / SHA256 `a13bee66c602496cbcefaa6df7b823ae10829ecaf61056ea0cf57820f4647db8` / mtime **2026-11-01 15:02:24**）⇒ `app186` **34 PASS / 0 FAIL**（含 `app191` **18/0**）③ **APP-052 ③**：`results/mt2_acc_outputs/` 已整目录排除（22 个文件，zip 内 **0** 命中）＋ docstring 开发机路径 → `<HOME>` ＋ MANIFEST 增 v1.13 修订说明 ＋ **打包闸门又抓到 2 类真缺陷**（7 个脚本写死包路径 / `speaker_tracker.py` 的 2 个 U+FFFD 乱码）并已修 ④ **APP-052 ④**：本文件已压缩到 ≤ 40 KB / ≤ 300 行（§109–§122 正文**原样归档**）⑤ **APP-053**：说话人标签覆盖率 **7.23 % → 93.48 %**（43/46；与 pyannote 自身差 **2.17–4.35 pp** ⇒ ≤ 5 pp）⇒ `app202` **9 PASS / 0 FAIL**；顺带订正 `app195` 的 **M8 恒假判据**（簇号 vs 人工编号无语义对应 ⇒ 置换后 **82.61 %**）⑥ **APP-054**：旁路**默认关闭** ＋ **线程化** ＋ **攒整窗** ＋ **降级不反压** ⇒ A/B 实测旁路开 **300.6 s / 积压 1.2 s / 延迟 316 ms**（vs reviewer 缺陷态 838.5 s / 195.1 s）⇒ **4 PASS / 0 FAIL**；🔴 **根因在 ASR 侧**（`run_seg_side` 每次调用重编译模型 ⇒ 3 000 次编译 ≈ 538 s）⇒ 已写 `shared/NOTICE_app_to_asr_app054_spk_recompile.md` **待主会话转达**
阻塞 / 待用户决定: ① 🔴 **需用户实听 3 段 1.2–1.3× 配音素材**（`C:\Users\Trekker-PTL\shared\app_accel_listen\`：1.2× / 1.3× / 1.3×）＋ **reviewer 判定音质 / 不变调 / 可懂**（本轮只判链路 + 结构 + 数字自洽）；② 🔴 **§123 待 reviewer 复核 9 项**（详见 §123 ⑤）—— 其中最关键：**APP-053 的 GUI 转写区正式行仍未取到带 `[Sx]` 前缀的图**（本轮 GUI 已实测 `[spk] 标签补到：第 19 段 = S1` ＋ ASR 区「当前 S1」＋ 语音区「说话人：S1」＋「说话人识别」勾选框生效，但 **MT 目标语言=关闭 时 GUI 不产出正式行** ⇒ 只显示灰色草稿行 ⇒ 该子项**记为未达成**，**不粉饰**）③ 🔴 **APP-052 ② 的三个子项口径缺口仍待 reviewer 认可**（① `app175` 的 7.23 % 旧口径；② `app179` 的 B4「滞后越大倍率越大」**空真** ⇒ 未验证；③ APP-048 两张截图只拍到空闲态，**运行中截图仍缺**）④ 🔴 **APP-054 的 NOTICE 待主会话转达 ASR**（治本项：ASR 侧 `run_seg_side` 每次调用重编译模型）⑤ 🔴 **§122 遗留的 `app191` 四项口径**本轮未改动，仍待复核 ⑥ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围**仍待 reviewer 确认（§112 已证它会让 `torch` 假阳性；§109/§110 为静态字节比对，未受影响）⑦ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入文件，SHA256 `edddefcd…5ad7d6` 零改动）⑧ 🔴 **§115 / §114 / §113 / §112 的待复核项**本轮未动 ⑨ 🔴 **v1.12 / v1.5 等历史 zip 仍是旧内容**（历史包**未重打**、旧包目录**未删除** —— 删除属破坏性操作，需用户确认）⑩ 🔴 **§119 §5.6 的 `.gitattributes`** 议题（会触发全仓行尾重写 ⇒ 需 reviewer 裁定）
已压缩: 本文件 39830 B / 265 行（APP-052 ④ 限额 ≤ 40 000 B / ≤ 300 行）；**§109–§122 正文已原样归档**到 `status/archive/STATUS_APP_sec109_122_upto_20261101.md`（116062 B，SHA256 `249eae7c31e396e339b83333cbeb6c90af85ad02de01777aca9023c10d817403`）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`


## 最近更新
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
| 客户包目录 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13`（**当前最新**；v1.12 目录仍在，未删除） | `Confucius4_LiveCaption_v1.13/MANIFEST.json` → `version=1.13`（`DELIVERY_1.13.json` → `manifest_version`） |
| 客户包 zip | **v1.13**（**2026-11-01 15:02:24 重打** / **11 232 363 846 B** / **14 192 文件** / SHA256 **`a13bee66c602496cbcefaa6df7b823ae10829ecaf61056ea0cf57820f4647db8`**）⇒ **含** APP-045/047/048/050/051/052/053/054 代码 ＋ `ACCEPTED.json`（含 `code_fingerprint` + `binding_gate=app191` + **6 个编号子项 ①–⑥ ＋ `1b_lnk_shortcut`**）＋ `NOTICE` ＋ `THIRD_PARTY.md` | `results/app/DELIVERY_1.13.json` → `sha256` / `bytes` / `mtime`；`sha256sum` **独立复核一致**；打包日志 → 「比对 N 个文件 / 全部逐字节一致」 |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | TTS 走 NPU（F16 / INT8 视配置） | `app048_layout_1920x1080.png`（语音区实测「语音区 · Intel NPU · F16」） |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出） | `app185_app048_gui_layout_pkg_evidence.json` → `verdict=PASS` / `n_pass=64` / `n_fail=0`（**在客户包内代码上跑**） |
| 桌面快捷方式 | **已指向 v1.13**（`Confucius4 实时字幕 v1.13.lnk` **2 099 B**，**由 `WScript.Shell.CreateShortcut` 生成**（COM 读回 `TargetPath` 非空、指向包内 `Start_LiveCaption.bat`）⇒ **不再是坏链**） | `results/app/app192_lnk_coldstart_evidence.json` → `lnk_verify.com.target` / `checks`（13 PASS / 0 FAIL） |
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

### §123 ✅ **APP-052 / APP-053 / APP-054 —— 桌面 `.lnk` 坏链修复 ＋ `ACCEPTED` 重签 ＋ 说话人标签覆盖率 7 % → 93.48 % ＋ 旁路线程化止血 ＋ STATUS 压缩** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

> **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec123_upto_20261101.md`（逐字保留，内容一字未删）。
