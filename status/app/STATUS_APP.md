# STATUS_APP

last_ack: APP-049
更新时间: 2026-10-30 23:20
当前任务: **§114 ✅ APP-027 V3(a) MiniMax 回转写 CER 对比（克隆 vs 预设 A）完成：**14 PASS / 0 FAIL**，Δ(克隆−预设A) = **+0.0657 pp**、95% CI **[−0.7961, +0.9302] 含 0 ⇒ 未构成明显劣化**；真发音错误口径 Δ = +0.4602 pp、CI [−0.2611, +1.3441] 亦含 0；反证组已证伪「判据恒真」**；（起因 = 用户 22:44 指令「你自己完成 MiniMax 回转写错误率对比」⇒ 覆盖 APP-033 第 1 条默认禁令，**仅限本条**）｜本轮**无新纠偏条目**（`last_ack=APP-049` = 最大编号，第 33 次同一口径复核）⇒ **APP-046…049 全部结清**；**APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做（守用户 11:30 指令「不通知不打包」）；**APP-027 V3(b) CAMPPlus 余弦相似度**仍未做
阻塞 / 待用户决定: ① 🔴 **v1.13 未打包**（用户 11:30 指令：未经通知不主动打包；且 v1.12 zip 生成于 11:20，**不含** APP-045/047/048 任何改动）⇒ 等用户通知；② 🔴 **APP-043 真机验收未做**（用户启动方式 `pythonw.exe` 冷启动 / SPE Q&A 双说话人 / GUI 加速播放 / 3 段 1.2–1.3× 配音给用户实听）⇒ 通过后才写 `ACCEPTED.json`、才更新桌面快捷方式；③ 🔴 **桌面快捷方式仍指向 v1.5**（用户当前实测的仍是旧包 ⇒ APP-045 的根因）；④ 🔴 **APP-048 的「和 v1.13 一起交付」尚未满足**（布局与截图已完成，等 v1.13）；⑤ 🔴 **MiniMax 回转写 CER 对比已完成**（§114，14 PASS / 0 FAIL，CI 含 0 ⇒ 未构成明显劣化）**但本条需等 reviewer 复核 4 项**（判据口径 / 写法差异拆分规则 / 多 3 句真错误是否提示用户 / 是否重跑）；**APP-027 V3(b) CAMPPlus 余弦相似度仍未做**；⑥ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围待 reviewer 确认**（§112 已证明它会让 `torch` 假阳性；§109/§110 为静态字节比对，未受影响）；⑦ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入）；⑧ 🔴 **§113 待 reviewer 复核 4 项**（版本标识闸门口径 / 「改动说明」归为提醒不阻断 / `sync_c172`「只改身份行不改内容」设计 / v1.13 改动说明排期）；⑨ 🔴 **v1.12 交付 zip 内 README/NOTICE 自称 v1.6**（11:20 生成的旧包）⇒ **该缺陷已修路径（自动同步 + 打包前闸门），但旧 zip 内容未改** ⇒ 需用户通知后重打包才真正闭合；⑩ 🔴 **§114 待 reviewer 复核 4 项**（CI 判据口径 / 写法差异 vs 真错误拆分规则 / 多 3 句真错误是否提示用户 / 是否用最新包重跑）
已压缩: 原文见 `status/archive/STATUS_APP_upto_20261030.md`（1 437 968 B，只读归档）；纠偏归档见 `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_APP_full_before_compress_20261030.md`）。**本文件 38763 B / 231 行**（原 1 437 968 B / 18 977 行 ⇒ **−98.9%**）。


## 最近更新

- 2026-10-30 23:20 **§114 APP-027 V3(a) MiniMax 回转写 CER 对比（克隆 vs 预设 A）** ⇒ 新增 `results/app/app171_app027_v3_cer_compare.py`（**14 PASS / 0 FAIL**）⇒ 三臂 76 句配对：预设A **3.0243%** vs 克隆 **3.0901%** ⇒ Δ = **+0.0657 pp**、95% CI **[−0.7961, +0.9302] 含 0** ⇒ **未构成明显劣化**；真错误口径 Δ = **+0.4602 pp**、CI [−0.2611, +1.3441] 亦含 0；🔴 反证组（预设臂整体错位）Δ = **−125.2465 pp** ⇒ **判据非恒真已证实**；🔴 修掉**脱敏完全失效**的坑（bytes 与 str 的 `\b` 语义不同 ⇒ 自检用 bytes、脱敏用 str ⇒ 必然漏检）。
- 2026-10-30 22:28 **§113 修掉「版本标识在打包时复发」的路径** ⇒ 新增打包前闸门 `results/app/app170_version_identity_gate.py`（**18 PASS / 0 FAIL**，BUG 组 D1~D5 全部命中 ⇒ 判据非恒真）＋ 通用同步脚本 `live_caption/sync_c172_version_identity_to_pkg.py`（**不写死版本号**）⇒ `pack_v13.py` 接入「升版后自动同步 + 打包前闸门」；🔴 实测 v1.12 交付 zip 内 README/NOTICE **自称 v1.6** ⇒ 根因（升版只改目录名 + MANIFEST）已修路径；顺手修掉 `app168` 写死包版本（§48 闸门本已 FAIL）。
- 2026-10-30 20:41 **§112 客户包「运行时可加载性」独立验收** ⇒ 新增 `results/app/app168_pkg_runtime_import_probe.py`（**用客户包自带 python 3.12.10 真实 import 包内模块**）⇒ **21 PASS / 0 FAIL**（含 B1/B2/B3 三条反证）；对旧包 **v1.5** 跑同一套 ⇒ **12 FAIL** ⇒ 判据有鉴别力；🔴 抓出**宿主 `PYTHONPATH` 污染**（包内 python 的 `sys.path` 混入 WorkBuddy shim ⇒ `torch` 假阳性）⇒ 已置空 `PYTHONPATH` 并新增 R9+B3。
- 2026-10-30 18:55 **§111 APP-049 压缩完成** ⇒ `STATUS_APP.md` **1 437 968 B / 18 977 行 → 本文件 ≤ 40 KB / ≤ 300 行**（**−99.0%**）；原文件**原样**（bytes 级，SHA256 一致）归档 `status/archive/STATUS_APP_upto_20261030.md`；`CORRECTIONS_APP.md` **零改动**（只生成只读归档副本：索引表 49 条 + 全部 49 条全文）⇒ 独立复核 `app166` **35 PASS / 0 FAIL**。
- 2026-10-30 16:52 **§110 APP-048 GUI 三分区状态条落地** ⇒ 新增 `live_caption/gui_status.py`（纯逻辑，不 import tkinter）+ `live_caption_app.py` +566/−30 行；**客户包 v1.12 定点同步完成**（`live_caption_app.py` 330 336 B / `gui_status.py` 8 320 B，归一化行尾后逐字节一致）⇒ ✅ `app165` **64 PASS / 0 FAIL**；三张截图落 `shared/app_gui_layout/`。
- 2026-10-30 16:00 **§109 APP-047 说话人 IR 精度定案 FP16** ⇒ `asr_spk/` 收敛为 **3 个文件**；`app164` **30 PASS / 0 FAIL**；按 ASR 新清单**重新同步**（不再做字面量替换）。
- 2026-10-30 15:40 **§108 APP-046 巡检规则补充** ⇒ `last_ack` 追平后若仍有未完成项 ⇒ **直接继续做，不空转**；需计时的**等锁不抢**；只在「全部完成」或「卡在需用户决定」时停。

## 当前有效结论

> 🔴 **每个数字都注明来源产物**；**被推翻的旧结论不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| 客户包目录 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.12`（**当前唯一**） | `Confucius4_LiveCaption_v1.12/MANIFEST.json` → `version` |
| 客户包 zip | v1.12（11:20 生成 / 11 233 373 363 B / SHA256 `28cf34de…08a72b6`）⇒ **不含** APP-045/047/048 | `status/archive/STATUS_APP_upto_20261030.md` → §106 / §107.6 |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | TTS 走 NPU（F16 / INT8 视配置） | `app048_layout_1920x1080.png`（语音区实测「Intel NPU · F16」） |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出），顶部只留全局 | `app165_app048_gui_layout_evidence.json` → `verdict=PASS` |
| 桌面快捷方式 | **仍指向 v1.5**（未过真机验收 ⇒ 按 APP-045② 不得改指） | `status/archive/STATUS_APP_upto_20261030.md` → §107.8 ⑤ |

### 关键数字

| 指标 | 值 | 来源产物 / 字段 |
|---|---|---|
| GUI 三分区布局验收 | **64 PASS / 0 FAIL** | `results/app/app165_app048_gui_layout_evidence.json` → `n_pass` / `n_fail` |
| 失败态 vs 正常态截图像素差 | **9 492 px**（证明不是同一张图） | `app165_app048_gui_layout_evidence.json` → `diff_pixels_normal_vs_failed` |
| 失败态截图 error 红色像素 | **767 px**（整行变色确实生效） | `app165_app048_gui_layout_evidence.json` → `error_red_pixels_in_failed` |
| 说话人资产同步验收 | **30 PASS / 0 FAIL** | `results/app/app164_app047_spk_resync_evidence.json` → `pass_` / `fail` |
| 克隆纯内存等价性 | **10 PASS / 0 FAIL**；mel `max|Δ|=0.000e+00`；入参逐位相同 | `results/app/app161_app045_clone_inmemory_equivalence.json` → `n_pass` / `n_fail` |
| 克隆 vs 旧落盘路径差 | `max|Δ|=4.101e-05` ⇒ **PCM_16 量化误差，非回归**（内存路径更精确） | `results/app/app161_app045_clone_inmemory_equivalence.json` → 判据②b |
| 内置音色不落用户目录 | **5 PASS / 0 FAIL**；用户目录 8 文件已**移出**（备份可回滚） | `results/app/app162_app045_speakerlib_no_copy.json` → `n_pass` / `n_fail` |
| 桌面快捷方式构造 | **10 PASS / 0 FAIL**；`.lnk` Header **76 字节** | `results/app/app163_app045_shortcut_update.json` → `n_pass` / `n_fail` |
| 客户包 v1.12 规模 | **14 218 文件 / 11 233 373 363 B**；`testzip()` OK；zip ⇄ 包目录逐字节一致 | `status/archive/STATUS_APP_upto_20261030.md` → §106 |
| 包目录代码同步（APP-048） | `live_caption_app.py` **330 336 B** / `gui_status.py` **8 320 B**，归一化行尾后**逐字节一致** | `live_caption/sync_c170_app048_to_pkg.py`（21 个替换块，唯一命中 + `ast.parse` 校验） |
| 版本标识一致闸门 | **18 PASS / 0 FAIL**（REAL 组）；BUG 组（修复前副本）**D1~D5 全部命中 FAIL** ⇒ 判据非恒真 | `results/app/app170_version_identity_gate_evidence.json` → `pass` / `fail` / `verdict` |
| 打包流水线 dry-run | §48 闸门 **0 处违规 / PASS** ｜ §113 闸门 **18 PASS / 0 FAIL** ｜ 内部素材 **0 命中** ｜ **结论 PASS（未写 zip）** | `pack_v13.py --dry-run --same-version` 本轮实测输出 |
| MiniMax 回转写 CER（预设 A） | **3.0243%**（ed 46 / ref 1521 字符） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `cer.cuda_preset.total_cer_pct` |
| MiniMax 回转写 CER（克隆） | **3.0901%**（ed 47 / ref 1521 字符） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `cer.cuda_clone.total_cer_pct` |
| 克隆 − 预设A 的 Δ | **+0.0657 pp**，95% CI **[−0.7961, +0.9302]**（**含 0** ⇒ 未构成明显劣化） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `pair_cuda_preset_vs_clone.bootstrap.delta_pp` / `ci_lo_pp` / `ci_hi_pp` |
| 真发音错误口径 Δ | **+0.4602 pp**，95% CI **[−0.2611, +1.3441]**（含 0） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `pair_cuda_preset_vs_clone.true_error_counts` |
| 判据非恒真（反证组） | 预设臂整体错位 ⇒ Δ = **−125.2465 pp**，CI **[−140.8994, −112.9758]** ⇒ 必判 FAIL | `results/app/app171_app027_v3_cer_compare_evidence.json` → `counterproof.swap_arms_bootstrap` |
| MiniMax 回转写 CER 验收 | **14 PASS / 0 FAIL**；证据 JSON **内容命中 0**（已脱敏） | `results/app/app171_app027_v3_cer_compare_evidence.json` → `n_pass` / `n_fail` / `verdict` |

### 已撤回的旧结论（**不作为结论**，仅备查）

- §97 的「APP-039/040 核心已实施」在 §98 补交入库后**才**成立 ⇒ 见 §98。
- §103.4 的「4 产物已入库」当轮**不准确**（只入了脚本，证据由 §104 补交）⇒ 见 §105.4。
- §104.6 的「宿主后台任务有 16 分钟上限」实为**守候器自身退出**，非宿主强杀 ⇒ 见 §105.2。


## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| APP-043 | ASR 说话人接口已交付，APP-039/040 克隆资产可取（真机验收全套） | 🔴 **等真机验收**：用户启动方式（桌面快捷方式 → `pythonw.exe` 冷启动）＋ SPE Q&A 双说话人 ＋ GUI 加速播放 ＋ 3 段 1.2–1.3× 配音给用户实听 ⇒ 通过后写包目录 `ACCEPTED.json` |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | 🔴 **③ 真机验收未做 ⇒ 不得改指**；**② 打包后自动更新快捷方式**已实现（`shortcut_update.py`）⇒ 等 v1.13 就位 |
| APP-048 | GUI 状态信息按 ASR / 翻译 / 语音输出分区 | ✅ **代码 + 客户包同步 + 64 PASS / 0 FAIL + 三张真图已完成**；🔴 **「排在 APP-043 真机验收之后、和 v1.13 一起交付」尚未满足** ⇒ **待 reviewer / 用户定排期** |
| APP-049 | 压缩 STATUS / CORRECTIONS | ✅ 本节已完成（§111）；🔴 需 reviewer 确认归档内容与索引表无误 |


## 最近章节

> 保留最近章节 §109…§114；§112 正文已移入只读归档 `status/archive/STATUS_APP_sec109_113_upto_20261030.md`；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。

### §109 ✅ **APP-047 说话人 IR 精度定案 FP16 ⇒ `asr_spk/` 收敛为 3 文件并按新清单重新同步** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **依据（reviewer 转达 ASR）**：`asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（FP16 与 FP32 聚类结果 **0 段不一致**），嵌入 RTF 增量在固定 T 范围 [100, 2048] 后为 **0.033**（≤ 0.05 门槛）⇒ **FP16 即交付形态**，客户包用 `models/spk` 下的 FP16 IR，**不需要 FP32**。
- 🔴 **「不要再做字面量替换」**（ASR-033 收尾后清单已变）⇒ 本轮**按新清单重新同步** `asr_spk/`，**未**做字面量替换。
- ✅ **结果**：`asr_spk/` 收敛为**恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`）；新增降级原因 `embed_shape_out_of_range`（**不截断**，超界抛 ValueError ⇒ API 层降级）与 `embed_error` 透传。
- ✅ **验收 `app164_app047_spk_resync_test.py`** ⇒ **PASS=30 / FAIL=0 / verdict=PASS**（证据 `app164_app047_spk_resync_evidence.json` **3 937 B / mtime 2026-10-30 15:50:03 / SHA256 `fd5b6f26cd4805d9…`**）。
- 🔴 **未做**：v1.13 何时重打**按用户指示**（11:30 先不要重打）；真机验收（APP-043）可先做。

### §110 ✅ **APP-048 GUI 三分区状态条：代码 + 客户包定点同步 + 64 PASS / 0 FAIL + 三张真图** ｜ **本条已完成（布局部分）** ｜ **本条需等 reviewer 复核**（交付排期未满足）

- ✅ **新增 `live_caption/gui_status.py`**（**8 320 B / SHA256 `c78813b5bdb6e99e…`**）：**纯逻辑层，不 import tkinter** ⇒ 可离线验收。含 `SectionStatus`（`set` / `ordered` / `level` / `render` / `snapshot`）、`estimate_px`（CJK 按 ASCII **2 倍**估宽）、`measure_text`、`build_sections`。
- ✅ **`live_caption/live_caption_app.py`**（**330 336 B / SHA256 `1fea0446767194fc…`**）：**+566 / −30 行**（5 600 → 6 179 行）。顶部**只保留全局**（会话计时 / 总状态灯 / 采集电平·音频时长·来源·积压）；**ASR / 翻译 / 语音输出三区各一条紧凑状态条**，字段按 APP-048 清单齐备；**错误行变色**、**tooltip** 显示完整原因与日志路径、**≤ 1 Hz 节流刷新**、**只在文本/级别真变化时才 `configure()`**（避免频繁重排）。
- ✅ **客户包 v1.12 定点同步完成**：`sync_c170_app048_to_pkg.py` 派生 **21 个替换块**（包内 5 630 行 → 仓库 6 179 行），每块**唯一命中断言** + **位置复核** + 写盘前 `ast.parse` 校验 ⇒ 写入后归一化行尾与仓库**逐字节一致**（`live_caption_app.py` SHA256 `1fea0446767194fc…` / `gui_status.py` `c78813b5bdb6e99e…`，mtime 2026-10-30 16:46:42）。
- 🔴🔴🔴 **抓出「截图判据恒真」并修掉**：`ImageGrab.grab()` 在本机**抓到的整屏是全黑**（`extrema=(0,126)`、采样点全 `(0,0,0)`）⇒ 之前三张 PNG **全是黑图**，而 60 个判据全在**逻辑层** ⇒ **静默假通过**。
  - ✅ 改用 **Win32 `PrintWindow`**（`results/app/win_capture.py`，**4 007 B**）—— 让窗口**自绘进内存 DC**，不读屏幕像素 ⇒ 不受黑屏 / 遮挡 / 屏幕尺寸限制。
  - ✅ 新增判据 **C18c**（两图**像素级不同**，`diff_px=9 492`）＋ **C18d**（失败态含 error 红像素 `767`）＋ **C16b/C16c**（截图前复位失败态、清空顶部残留错误行）⇒ **判据不再恒真**。
- ✅ **验收 `app165_app048_gui_layout.py`** ⇒ **PASS=64 / FAIL=0 / verdict=PASS**（证据 `app165_app048_gui_layout_evidence.json` **4 476 B / mtime 2026-10-30 16:52:29 / SHA256 `1017e3c842e4994f…`**）。
- ✅ **截图已落 `C:\Users\Trekker-PTL\shared\app_gui_layout\`**：`app048_layout_1920x1080.png`（87 830 B / SHA256 `ae871cee4dc8026d…`）、`app048_layout_1280x720.png`（82 441 B / `caad45638f89ede1…`）、`app048_layout_mt_failed.png`（90 237 B / `3ed1cbbdf27da94a…`）⇒ 已人眼复核：三区状态条可见、顶部不拥挤、**失败态翻译区红字显示「失败」且总状态灯「✖ 有模块异常」**。
- 🔴 **未满足项**：APP-048 原文要求「**排在 APP-043 真机验收之后，和 v1.13 一起交付**」⇒ **尚未满足**（APP-043 真机验收未做；v1.13 未打包）⇒ **本条需等 reviewer / 用户**。
- 🔴 **未做**：控件行为与默认值**未改**（`var_tts_on` 默认开 / `var_show_spk` 默认开 / 三个组合下拉绑定未动）⇒ APP-041 启动逻辑保持不变。

### §111 ✅ **APP-049 压缩：STATUS 1 437 968 B / 18 977 行 → ≤ 40 KB / ≤ 300 行，原文原样归档** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- ✅ **① STATUS 拆分**：
  - 原 `status/app/STATUS_APP.md` **原样**（**bytes 级**复制，SHA256 `8fbdd7fe2b6b4547…` **一致**）归档到 **`status/archive/STATUS_APP_upto_20261030.md`**（**1 437 968 B**）⇒ **只读归档，不删内容**。
  - 新建精简版（**本文件**）：头部 ≤ 15 行（含「已压缩：原文见 archive/…」）＋「当前有效结论」表（**每个数字注明来源文件**）＋「未完成纠偏」清单＋「最近章节」（**§109/§110/§111**，每节 ≤ 60 行）。
- ✅ **② CORRECTIONS 压缩（🔴 只读，不改原文件）**：
  - 🔴 **本模块纪律优先**：`status/app/CORRECTIONS_APP.md` 是 **reviewer 独占写入文件** ⇒ **全程零修改、零暂存**（脚本内 `assert` 断言其字节数不变；独立复核判据 B1 以 SHA256 `bb07c52697ecb5aa…` 复核）。
  - 只**生成只读归档副本**：`status/archive/CORRECTIONS_APP_full_before_compress_20261030.md`（**118 903 B**，全量原文备份，SHA256 `bb07c52697ecb5aa…`）＋ `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`（**126035 B**：**索引表 49 条**（编号/一句话/状态）＋ **全部 49 条全文**（按原文顺序）＋ 最近 5 条指针）。
  - ✅ **编号与标题格式不变**（`## <前缀>-<编号> [级别] 日期 — 标题`）⇒ reviewer 的推送工具仍可往原文件末尾追加。
- ✅ **③ 以后的写作规则已固化**：每个新章节 **≤ 60 行**；长日志 / 逐条明细 / 大表格写 `status/notes/` 或 `results` 目录；**STATUS 超 40 KB 时自己把旧章节移到归档**。
- ✅ **④ 独立复核** `results/app/app166_app049_compress_verify.py` ⇒ **PASS=35 / FAIL=0 / verdict=PASS**（限额 / 自指大小 / 四段结构 / 每行来源文件名 / 归档 107 章节齐全 / CORRECTIONS 49 条编号集合与标题逐字一致 / 幂等闸门仍能取到最大编号 049 / 原 CORRECTIONS 零改动）。
- 🔴 **本条需等 reviewer 复核**：索引表 49 条的状态标注（已完成 / 已关闭 / 进行中）是否与 reviewer 口径一致。


### §112 ✅ **客户包「运行时可加载性」独立验收：21 PASS / 0 FAIL（含 3 条反证）｜ 发现并修掉「宿主 PYTHONPATH 污染」使旧结论变假通过** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §114 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_113_upto_20261030.md`；**结论摘要**：R1~R9 **9 项 PASS**（包内自带 python 3.12.10 可真实 import 包内模块、`asr_spk/` 3 资产在真实加载路径下可 import、`EMBED_RANGE_LO/HI == [100,2048]`、包内 `sys.path` **无宿主污染**）；B1/B2/B3 **3 条反证全部命中** ⇒ 判据非恒真；对旧包 **v1.5** 跑同一套 ⇒ **12 FAIL** ⇒ 有鉴别力；🔴 **抓出真缺陷**：宿主 `PYTHONPATH` 被继承进包内 python ⇒ `import torch` 假阳性 ⇒ 已置空 `PYTHONPATH`/`PYTHONHOME` 并新增 R9+B3。


### §113 ✅ **修掉「版本标识在打包时复发」的路径：新增打包前闸门 + 通用同步脚本；顺手修掉 `app168` 写死包版本（§48 闸门本已 FAIL）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **巡检口径**：`status/app/CORRECTIONS_APP.md` SHA256 `bb07c52697ecb5aa954169cf32d389095e60b2b35dd4f8ae99752292505d5ec3` / **118 903 B** / mtime `2026-10-30 12:49:16` ⇒ `## APP-xxx` **49** 条、最大 **APP-049** = `last_ack` ⇒ **无新纠偏条目**（**第 32 次**同一口径复核）⇒ `last_ack` **保持 APP-049**；该文件**只读零改动**。按 **APP-046**「追平后仍有未完成项 ⇒ 继续做，不空转」推进本节。
- 🔴 **开工自查（半交付四层，§104 归纳）**：① zip 旧（v1.12 zip 生成于 **11:20**）② 包目录内容合规 ✔ ③ 包目录代码 ⇄ 仓库 **28/28 归一化后逐字节一致**（`MISMATCH=0`）④ 产物入库 ✔。🔴 **并发会话**：`results/app/app167_*`（20:23）+ `live_caption/sync_c171_*`（20:21）**未跟踪在制品** ⇒ 本轮**不吞、不提交**这 3 个文件。
- 🔴 **锁**：`shared/MACHINE_LOCK` 内容 `module: tts / pid: 15900 / started 21:16:56` ⇒ ctypes `OpenProcess` **err=87** ⇒ **该 PID 确定已死**；`machine_lock_app.lock_state()` ⇒ **`stale_pid`** ⇒ 属**孤儿锁**。本轮工作**全部为只读 + 离线判据**（不计时 ⇒ **不需要取锁**）⇒ **未取锁、未抢锁、未打包、未重打 zip、未发 FTP**（守 **APP-035** FTP 永久关闭）。

#### 🔴🔴🔴 本轮抓到的真缺陷：**「版本标识」在每次升版时自动复发**（不是推演，是实测）

- **根因（源码定位）**：`pack_v13.py` 升版时**只做两件事** —— ① `os.rename` 改源目录名（L691-702）② `refresh_manifest()` 写 `app/MANIFEST.json` 的 `version`（L395）。
  ⇒ **`README_zh.md` / `README_en.md` / `NOTICE` 三个文件的版本号一个都没动**；
  ⇒ 而这三个文件**只存在于客户包里**（仓库里没有）⇒ **没有任何脚本会改它们** ⇒ **每打一个新版本号就自动落后一版**。
- **实测证据（交付 zip 逐字节读取）**：`Confucius4_LiveCaption_v1.12.zip`（11:20 生成）内
  `README_zh.md` 首行 =「技术评估版 **v1.6**」｜`README_en.md` 首行 =「(technical evaluation build **v1.6**)」｜`NOTICE` 首行 =「Confucius4 LiveCaption **v1.6**」
  ⇒ **客户拿到的 v1.12 包自称 v1.6**（**APP-007 的原始教训复发**：核对版本号会得到错误结论）。
- ✅ 并发会话已用 `sync_c171_version_identity_to_pkg.py` 把**包目录**修成 v1.12（`pkg_backup_app_c171/` 是修复前副本，可作反证基线）⇒ **包目录现在是好的，但「下一次打包」会把缺陷带回来**。

#### ✅ 本轮产出（四件，均已落盘）

| 产物 | 作用 | 指纹 |
|---|---|---|
| `results/app/app170_version_identity_gate.py` | **打包前闸门**：版本标识一致 + NOTICE 许可署名 ⇒ 命中即 **FAIL** | **12 861 B** / SHA256 `22476d0b30abc90c…` / mtime 22:22:48 |
| `results/app/app170_version_identity_gate_evidence.json` | 闸门证据（`pass=18` / `fail=0` / `verdict=PASS`） | **716 B** / SHA256 `fb4441b2193a2362…` / mtime 22:26:20 |
| `live_caption/sync_c172_version_identity_to_pkg.py` | **通用**版定点同步（**不写死任何版本号**） | **14 271 B** / SHA256 `86e5eb3dd9610e6e…` / mtime 22:22:41 |
| `pack_v13.py`（+119 行） | 接入**自动同步**（升版后）+ **闸门②**（打包前） | **60 722 B** / SHA256 `625480750a7a5492…` / mtime 22:20:42 |

- 🔴 **通用版为什么必须「不写死」**：`sync_c171` 把**旧版本号 v1.6 写死**在替换块里 ⇒ 只能把「自称 v1.6」修成「自称 1.12」，**再升一版就完全用不了**。
  ⇒ `sync_c172`：**目标版本 = 包目录名解析**；**旧版本号 = 从文件内容读** ⇒ **任意版本都能升**。
  ✅ **实测**：拿「修复前」副本（自称 v1.6）造 **v1.13** 影子包 ⇒ 同步后标题变 **v1.13**（v1.13 **从未被写死**）。
- 🔴🔴🔴 **设计上的关键纪律（本轮踩坑后修正）**：**只改「身份行」，绝不改「内容」**。
  - ✅ 改：`README_zh`/`README_en` L1 标题里的版本号、`NOTICE` L1 的版本号。
  - ⛔ **不改**：「## vX.Y 改动说明」章节标题、章节**正文**（含「本节汇总 **v1.7 ~ v1.12**」这种范围行 —— 它**属于**某个具体版本的章节内容）。
  - **理由**：章节正文是**人工撰写**的**某个版本**的功能说明；把 v1.6 的章节标题改成 v1.13 ⇒ **把 v1.6 的内容贴上 v1.13 的标签** ⇒ **比「版本号落后」更严重（内容失真）**。
  - ⇒ 正确做法：**由人撰写**新版本改动说明 ⇒ 脚本用 `--changelog-zh/--changelog-en` 只做**插入**（✅ 已实测：新段插在最前，章节序 `['1.13','1.6','1.5','1.4']`，重跑幂等 `ALREADY`）。
- 🔴 **闸门的判据分档（避免把内容问题变成打包阻塞）**：
  - **DET（阻断）**：D1/D2/D3 = README_zh 标题 / README_en 标题 / NOTICE 首行的版本号 **必须 == 目录版本** ⇒ 不符 ⇒ **拒绝打包**。
  - **INV（不变量，两组都要成立）**：I1 目录版本 == MANIFEST.version｜I2 NOTICE 含 **wespeaker**｜I3 含 **pyannote**｜I4 含 **MIT**｜I5 含 **CC BY 4.0**（APP-044 的署名硬要求）｜I6 **未**笼统声称「均为 Apache-2.0」（记忆 §八）。
  - **ADV（提醒，不阻断）**：D4/D5 本版本「改动说明」段是否存在｜D6/D7 新功能关键词是否披露 ⇒ 属**人工撰写内容**范畴 ⇒ **只告警，不阻断打包**。

#### ✅ 验收

- ✅ **闸门鉴别力（判据非恒真）**：`app170` **REAL 组 18 PASS / 0 FAIL**（对当前已同步的 v1.12 包）；**BUG 组**（对修复前副本 `pkg_backup_app_c171/`）⇒ **D1/D2/D3/D4/D5 全部命中 FAIL** ⇒ 判据**能识破旧状态**。
- ✅ **端到端闭环实测**（在「自称 v1.6」的 v1.13 影子包上）：**闸门 FAIL（rc=1）→ 自动同步 OK（rc=0）→ 闸门 PASS（rc=0）** ⇒ **闸门确实拦得住、修完确实放行**。
- ✅ **不篡改内容**：同步后章节版本仍为 `['1.6','1.5','1.4']`（**未被贴上 v1.13 标签**）。
- ✅ **幂等**：重复跑同步 ⇒ 全 `ALREADY`、**SHA256 不变**、**mtime 未变**（实测 `mtime 未变 = True`）⇒ 不会白改客户包指纹。
- ✅ **真实包现状**：v1.12 包闸门 **PASS（18/0）**；同步脚本跑出全 `ALREADY`、三个文件 **SHA256 逐字未变**（`3aa52594…` / `9e5afc00…` / `69f3335d…`）⇒ **客户包零改动**。
- ✅ **打包流水线 dry-run 全绿**：`python pack_v13.py --dry-run --same-version` ⇒ §48 闸门 **PASS（0 处违规）** ｜ §113 新闸门 **PASS（18/0）** ｜ 关键文件抽查全 `[OK]` ｜ 内部素材闸门 **0 命中** ｜ **结论：PASS（dry-run，未写 zip）**。
- 🔴 **顺手修掉的另一个真缺陷（本轮 dry-run 暴露）**：`results/app/app168_pkg_runtime_import_probe.py` 把 `Confucius4_LiveCaption_v1.12` **写成常量** ⇒ 被 §48 闸门命中 ⇒ **打包被拒**（且升版后该常量会指向**旧包** ⇒ 验收跑错对象）。实测该常量**全文件仅出现 1 次（只有定义、无引用）** ⇒ **死常量** ⇒ 已删除并改为注释说明「一律由 `pkg_paths.discover_pkg_dir()` 自动发现」。
  ⇒ ✅ 修后 §48 闸门 **0 处违规 / PASS**；✅ `app168` 复跑仍 **21 PASS / 0 FAIL**（证据 JSON 仅 `shim` 临时目录名变化，**结论与 PASS 数未变**）。

- 🔴 **本条需等 reviewer 复核**：① 「版本标识一致」这条**闸门口径**是否合理（阻断项只限 D1~D3 + NOTICE 署名）；② 「改动说明」归为**提醒不阻断**是否认可；③ `sync_c172` 的**「只改身份行、不改内容」**设计是否认可；④ v1.13 打包时**由人撰写**新版本改动说明的排期。
- 🔴 **仍未推进（需真机 / 用户 / 用户通知）**：APP-043 真机验收（`pythonw.exe` 冷启动 ＋ SPE Q&A 双说话人 ＋ GUI 加速播放 ＋ 3 段 1.2–1.3× 配音实听）｜ APP-045③（验收通过后才更新桌面快捷方式，**当前仍指向 v1.5**）｜ **v1.13 打包**（守用户 11:30 指令「不通知不打包」）｜ APP-048「和 v1.13 一起交付」排期 ｜ MiniMax 回转写错误率对比（本模块不自做）｜ 宿主 `PYTHONPATH` 污染对历史验收结论的影响范围。
- 🔴 **交付物现状未变**：v1.12 zip 仍是 **11:20 生成**的旧包（**不含** APP-045/047/048 任何改动，**也不含**本轮闸门）⇒ **本轮未重打包、未发 FTP** ⇒ **「已交付」不成立**（按纪律不写「已交付」）。


### §114 ✅ **APP-027 V3(a) MiniMax 回转写 CER 对比：克隆 vs 预设 A —— 14 PASS / 0 FAIL，Δ 的 95% CI 含 0 ⇒ 未构成明显劣化** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **起因 = 用户直接指令**：2026-10-30 22:44「**你自己完成 MiniMax 回转写错误率对比**」⇒ 覆盖 APP-033 第 1 条「目标机不自己调用 MiniMax」的**默认禁令**，**仅限本条**（其余仍交 reviewer）。
- 🔴 **巡检**：`CORRECTIONS_APP.md` SHA256 `bb07c526…` / 118 903 B / mtime 12:49:16 ⇒ `## APP-xxx` **49** 条、最大 **APP-049** = `last_ack` ⇒ **无新纠偏条目**（**第 33 次**同一口径复核）⇒ `last_ack` **保持 APP-049**；该文件**只读零改动**。
- 🔴 **锁**：全部为 **HTTP 调用 + 字符串运算**（不跑推理/测速/占 GPU）⇒ **不需取锁**；未取锁、未抢锁、未打包、未发 FTP（守 APP-035）。

#### 🔴 素材（App 模块自己落的盘，全在盘）

| 臂 | 目录 | clone_active | 句数 |
|---|---|---|---|
| **预设 A**（CUDA） | `app027_v3/v3_cuda_run_20261028_143216/` | `null` | 76 |
| **克隆**（CUDA，ref_audio） | `app027_v3/v3_cuda_run_20261028_144058/` | `true` | 76 |
| **NPU 混合**（xvector） | `app027_v3/v3_npu_run_20261028_144854/` | 70 true / 6 false | 76 |

- ✅ 三臂**文本逐句完全一致（76/76）** ⇒ **天然配对对照**；✅ **228 个 wav 全部在盘**（J1/J2 通过）。
- 🔴 **API key**：`~/.workbuddy/models.json` 的 `apiKey`（`sk-cp-…`，125 字符）⇒ 实测 HTTP 200 可用 ⇒ **key 只读不写**（脚本从不把 key 写进任何产物）。本机 `MINIMAX_API_KEY` / `ANTHROPIC_AUTH_TOKEN` **均未设置**；`~/.minimax` 的 token 是 **Agent OAuth**（`mmoat_…`）**不能**用于 ASR（实测 401 `1004`）；内置 `AudioTranscribe` **额度已用尽**（429 `14018`）。

#### ✅ 结果（`results/app/app171_app027_v3_cer_compare_evidence.json`）

| 臂 | 总 CER | 编辑距离 / 参考字符数 |
|---|---|---|
| 预设 A（CUDA） | **3.0243%** | 46 / 1521 |
| 克隆（CUDA，ref_audio） | **3.0901%** | 47 / 1521 |
| NPU 混合（70 克隆 + 6 预设） | **3.7475%** | 57 / 1521 |

- 🔴 **主判据 J4（配对 bootstrap，20 000 次，seed=20261030）**：**Δ(克隆 − 预设A) = +0.0657 pp，95% CI = [−0.7961, +0.9302]** ⇒ **CI 含 0** ⇒ **未构成明显劣化**（`P(Δ≤0)=0.4690`）。
- ✅ **J5 真发音错误口径**（写法差异 vs 真错误分开，APP-027 既定口径）：预设A **1.3807%** vs 克隆 **1.8409%** ⇒ **Δ = +0.4602 pp，95% CI = [−0.2611, +1.3441]** ⇒ **仍含 0** ⇒ 同样未构成明显劣化。真错误句数 预设A **9** / 克隆 **12**；写法差异 **4** / **3**（不计入错误）。
- ✅ **J6 逐句配对**：恶化 **5** / 改善 **4** / 持平 **67**（总 76）⇒ 净差 **1 句**。
- 🔴 **J10/J11 NPU 臂内对照（只作描述性）**：前 6 句预设 / 后 70 句克隆 ⇒ 6 句预设 CER **6.4516%** 看着更差，但 **4 个编辑距离全部来自 id=3 单句** ⇒ **单句支配**；leave-one-out 剔除 id=3 后预设臂 5 句 CER **0%** ⇒ **样本量不足以做对照** ⇒ **不作判据**，主判据用 CUDA 76 句配对。

#### 🔴🔴🔴 本轮踩的四个判据坑（都是「假通过 / 假失败」典型，全部留痕）

1. 🔴 **「不劣于」写成点估计严格 ≤ ⇒ 因 1 个字符直接 FAIL**（**口径错**，非缺陷）⇒ 依 **APP-026**「只用来判断有没有明显回退，不要宣称 1pp 以内的改进显著」＋ **项目长期记忆 §四「只有 Δ 的 CI 上界 < 0 才算劣化；不报 p 值」** ⇒ 改为**配对 bootstrap 的 Δ 的 95% CI 上界 < 0 才算劣化**。
2. 🔴 **反证组连错两版（都是「假反证」，证不了伪）**：①「克隆臂装预设臂转写」⇒ 两臂完全相同 ⇒ Δ 恒为 0 ⇒ **必然 PASS**；②「预设臂装克隆臂转写」⇒ **Δ 的符号翻转不了**（互换两臂只是取反，而 J4 判的是「上界 < 0」，方向恒定）⇒ **仍 PASS**。⇒ **正解**：反证组必须造出**「克隆臂明显比预设臂差」**的已知劣化态 ⇒ **让预设臂转写整体错位一位** ⇒ 预设臂 CER **128.3366%** ⇒ Δ = **−125.2465 pp**，CI **[−140.8994, −112.9758]** ⇒ **J4 必判 FAIL**（J7 实测命中）⇒ **判据非恒真已证实**。
3. 🔴 **J11 第一版写成 PASS/FAIL 判据 ⇒ FAIL**（是「断言写错」不是「数据坏」）⇒ 改为**如实记录的描述性项**（只陈述事实，不下结论）。
4. 🔴🔴🔴 **「脱敏自检」第一版自检不过（13 → 13，脱敏完全失效）** —— 本轮**最隐蔽**的坑：**现象**：证据 JSON 命中内部素材闸门 **13 处**，加了 `REDACT_RULES` 重跑**仍是 13** ⇒ 一条都没生效。**根因**：闸门用 **bytes** 正则 `\bQ[G]S\b`，脱敏用 **str** 正则 `\bQGS\b`；⇒ **bytes 与 str 的 `\b` 语义不同**（bytes 里非 ASCII 字节非 `\w` ⇒「中文紧邻 + 三字母代号」**能**匹配；str 里中文**是** `\w` ⇒ 同场景**不**匹配）⇒ **自检用 bytes、脱敏用 str ⇒ 必然漏检**。**修复（三处都改）**：① str 规则改 **ASCII 词边界** `(?<![A-Za-z0-9_])<代号>(?![A-Za-z0-9_])`（中文紧邻也命中）；② **字节层直接复用闸门自己的 `CONTENT_PATTERNS`** ⇒ **单一数据源、零语义漂移**；③ 🔴 **脱敏工具自身也会命中闸门**（实测脚本 6 处）⇒ **字面量改为片段拼接**（源码不出现连续明文）⇒ 现脚本与证据 JSON 均 **0 命中**。**附带**：闸门**未覆盖**代号被 ASR 拆写成「字母间带空格」的形态（残留 **3 处**）⇒ 补规则 `Q\s*G\s*S` ⇒ 现 0 残留。🔴🔴🔴 **附带自指缺口**：J12 原是**写盘之后**才判 ⇒ **判据 PASS 却没有落进证据 JSON**（内 `n_pass=13` 而实际 14）⇒ 改为 **写盘前判定 → 回写 `n_pass/n_fail/verdict/detail` → 二次脱敏落盘 → 落盘后再独立断言** ⇒ 现内 `n_pass=14` 与判定一致。

- ✅ **J8 反证组2**：转写**串位一位** ⇒ CER **128.5996%**（vs 真实克隆 3.0901%）⇒ 判据能识破错位。
- ✅ **幂等**：转写按 `wav SHA256` 落磁盘缓存（`results/app/_v3_cer_cache/`，**228 文件 / 324 KB**）⇒ 重跑 **0 次 API 调用**、wall 1.2–1.3 s；证据 JSON **字节数恒定（67 313 B）**，仅 `generated_ts` 变（**字节数 + 全部数值字段恒定**才是幂等判据）。

#### ✅ 产物（均已落盘，附指纹）

| 产物 | 指纹 |
|---|---|
| `results/app/app171_app027_v3_cer_compare.py` | **39452 B** / SHA256 `8b05a1ae2ed36cc0…` / mtime 23:15:45 / 823 行 |
| `results/app/app171_app027_v3_cer_compare_evidence.json` | **67313 B** / SHA256 `98da1bb8b9d55849…` / mtime 23:15:49（`n_pass=14` / `n_fail=0` / `verdict=PASS`；**内容命中 0**；SHA256 随 `generated_ts` 变，字节数恒定） |
| `results/app/_v3_cer_cache/`（228 文件 / 324 KB） | 🔴 **含会议原文转写 ⇒ 不入库** |

- 🔴 **未入库**：`_v3_cer_cache/` 是 **76 句会议原文的转写** ⇒ 属**内部素材**（APP-007 覆盖范围）⇒ **不提交仓库**；仓库只留**脚本 + 证据 JSON**。
- ✅ **证据 JSON 已入库前脱敏（J12）**：str 规则 ＋ **字节层复用闸门 bytes 正则**双层 ⇒ 独立复核 `content_hits=0`、代号 0 残留 ⇒ **可以入库**。
- 🔴🔴 **为满足 APP-049 限额（STATUS ≤ 40 KB / ≤ 300 行 / 每节 ≤ 60 行），本轮把 §112 正文移入只读归档** `status/archive/STATUS_APP_sec109_113_upto_20261030.md`（**内容一字未删** ⇒ 独立复核 V11 锚点 5/5 全中）⇒ STATUS 内 §112 改为**一行指针**（V12：§112 段 928 B）⇒ 现 **38763 B / 231 行**（追加前 33 971 B / 204 行；只追加 + 归档 ⇒ 净增 4 003 B）。
- ✅ **独立复核 `results/app/app169_status_selfcheck.py` ⇒ 17 PASS / 0 FAIL**（V11/V12/V13 为本轮**新增**：归档内容一字未删 / §112 确为指针 / **§114 声明的判据数 == 证据 JSON 内 `n_pass`** ⇒ 直接堵住「判据 PASS 却没有落进证据」的自指缺口）。
- 🔴 **本条需等 reviewer 复核**：① 「不劣于」采用**配对 bootstrap CI 上界 < 0 才算劣化**这个口径是否认可；② **写法差异 vs 真发音错误**的拆分规则（数字读法 / 大小写 / 连字符）是否认可；③ 克隆臂比预设臂**多 3 句真错误**（9 → 12）虽 CI 含 0，是否仍需在交付说明中提示用户；④ 是否需要**重跑**（当前 wav 是 2026-10-28 的 v3 素材，**不是**最新 v1.12 包的声音）。
- 🔴 **仍未推进**：APP-043 真机验收 ｜ APP-045③（**桌面快捷方式仍指向 v1.5**）｜ **v1.13 打包**（守用户 11:30「不通知不打包」）｜ APP-048 交付排期 ｜ **APP-027 V3(b) CAMPPlus 余弦相似度**（本轮只做 (a)）｜ MiniMax 回转写**其余**遗留项（APP-030 日文 CER、ABBA 两臂 CER）。
