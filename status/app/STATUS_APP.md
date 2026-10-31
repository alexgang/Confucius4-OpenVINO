# STATUS_APP

last_ack: APP-050
更新时间: 2026-10-31 10:32
当前任务: **§115 ✅ APP-050 TTS 启动日志打印各组件 `EXECUTION_DEVICES` —— talker / cp_prefill / cp_decode / decoder 实测**全部 NPU**（17 个组件 `on_npu=17` / `on_cpu=[]` / `on_unknown=[]`）；顺带修掉「`EXECUTION_DEVICES` 被逐字符拆开」这个**误读根因**（旧代码 `list('NPU')` ⇒ 误把字符拆分当 fallback 链，且会**静默漏报 CPU 回落**）＋ talker 桶 int 键从未被探测 ＋ 解码器桶从未被探测 ＋「未启用」与「落点不明」混同；**App 不调 `build()`** ⇒ APP-050 第②条（`cp_decode_device="NPU"`）对 App **不适用**（走 `_move_*_to_npu()` 搬运）；**本轮无新纠偏条目**（`last_ack=APP-050` = 最大编号）
阻塞 / 待用户决定: ① 🔴 **v1.13 未打包**（用户 11:30 指令：未经通知不主动打包）⇒ **本条改动（APP-050 那一行日志）客户机上还看不到**；② 🔴 **APP-043 真机验收未做**（用户启动方式 `pythonw.exe` 冷启动 / SPE Q&A 双说话人 / GUI 加速播放 / 3 段 1.2–1.3× 配音给用户实听）⇒ 通过后才写 `ACCEPTED.json`、才更新桌面快捷方式；③ 🔴 **桌面快捷方式仍指向 v1.5**（用户当前实测的仍是旧包 ⇒ APP-045 的根因）；④ 🔴 **APP-048 的「和 v1.13 一起交付」尚未满足**（布局与截图已完成，等 v1.13）；⑤ 🔴 **§115 待 reviewer 复核 5 项**（① `EXECUTION_DEVICES` 返回类型口径——**推翻了 §82 的旧解读** ② `absent`/`unknown` 分离 ③ `talker` 聚合所有桶 ④ App 不调 `build()` ⇒ 第②条不适用 ⑤ TTS 模块 `cp_decode_device` 未被消费 ⇒ App 无需改动）；⑥ 🔴 **§114 待 reviewer 复核 4 项**（CI 判据口径 / 写法差异 vs 真错误拆分规则 / 多 3 句真错误是否提示用户 / 是否用最新包重跑）；⑦ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围待 reviewer 确认**（§112 已证明它会让 `torch` 假阳性；§109/§110 为静态字节比对，未受影响）；⑧ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入）；⑨ 🔴 **§113 待 reviewer 复核 4 项**（版本标识闸门口径 / 「改动说明」归为提醒不阻断 / `sync_c172`「只改身份行不改内容」设计 / v1.13 改动说明排期）；⑩ 🔴 **v1.12 交付 zip 内 README/NOTICE 自称 v1.6**（11:20 生成的旧包）⇒ **该缺陷已修路径（自动同步 + 打包前闸门），但旧 zip 内容未改** ⇒ 需用户通知后重打包才真正闭合
已压缩: 原文见 `status/archive/STATUS_APP_upto_20261030.md`（1 437 968 B，只读归档）；纠偏归档见 `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_APP_full_before_compress_20261030.md`）。**本文件 27925 B / 178 行**（原 1 437 968 B / 18 977 行 ⇒ **−98.9%**）。


## 最近更新

- 2026-10-31 10:32 **§115 APP-050 TTS 启动日志打印各组件 `EXECUTION_DEVICES`** ⇒ 新增 `_norm_exec_devices()`（**字符串不再逐字符拆**）＋ talker 桶（**int 键**）与解码器桶**首次被探测** ＋ `absent`/`unknown` 分离 ＋ `key4_line` 一行；**实测 talker / cp_prefill / cp_decode / decoder 全部 NPU**（`on_npu=17` / `on_cpu=[]`）
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
| APP-050 启动日志 `EXECUTION_DEVICES` 一行 | `talker=NPU`，`cp_prefill=NPU`，`cp_decode=NPU`，`decoder=NPU`×9 | `results/app/app174d_worker_startup_e2e.json` → `key4_line`（真 worker stdout） |
| 各组件落点（直接调引擎） | **17 个组件全 NPU**；`on_cpu=[]`；`on_unknown=[]` | `results/app/app174c_startup_log_evidence.json` → `actual` / `on_npu` / `on_cpu` / `on_unknown` |
| `EXECUTION_DEVICES` 返回类型（实测） | NPU 档 = **字符串 `'NPU'`**；CPU 档 = **列表 `['CPU']`** ⇒ 旧代码 `list(devs)` 把字符串**逐字符拆开** | `results/app/app174a_exec_devices_type.json` → `probes.NPU.raw_type` / `probes.CPU.raw_type` |
| APP-050 离线单测（含 5 条反证） | **34 PASS / 0 FAIL**；反证组**全部命中** ⇒ 判据非恒真 | `results/app/app174b_exec_devices_unit.py` → `n_pass` / `n_fail` / `counterproof` |

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

> 保留最近章节 §109…§115；**§109~§114 正文已移入只读归档** `status/archive/STATUS_APP_sec109_114_upto_20261031.md`（**逐字保留，内容一字未删**）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`；**§115（APP-050）全文见下**。

### §109 ✅ **APP-047 说话人 IR 精度定案 FP16 ⇒ `asr_spk/` 收敛为 3 文件并按新清单重新同步** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**
- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`；**结论摘要**：见 STATUS 头部「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。
### §110 ✅ **APP-048 GUI 三分区状态条：代码 + 客户包定点同步 + 64 PASS / 0 FAIL + 三张真图** ｜ **本条已完成（布局部分）** ｜ **本条需等 reviewer 复核**（交付排期未满足）
- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`；**结论摘要**：见 STATUS 头部「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。
### §111 ✅ **APP-049 压缩：STATUS 1 437 968 B / 18 977 行 → ≤ 40 KB / ≤ 300 行，原文原样归档** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**
- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`；**结论摘要**：见 STATUS 头部「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。
### §112 ✅ **客户包「运行时可加载性」独立验收：21 PASS / 0 FAIL（含 3 条反证）｜ 发现并修掉「宿主 PYTHONPATH 污染」使旧结论变假通过** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**
- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`；**结论摘要**：见 STATUS 头部「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。
### §113 ✅ **修掉「版本标识在打包时复发」的路径：新增打包前闸门 + 通用同步脚本；顺手修掉 `app168` 写死包版本（§48 闸门本已 FAIL）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**
- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`；**结论摘要**：见 STATUS 头部「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。
### §114 ✅ **APP-027 V3(a) MiniMax 回转写 CER 对比：克隆 vs 预设 A —— 14 PASS / 0 FAIL，Δ 的 95% CI 含 0 ⇒ 未构成明显劣化** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**
- 🔴 **本节正文已移入只读归档**（APP-049 限额：追加 §115 前压缩）⇒ 全文见 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`；**结论摘要**：见 STATUS 头部「当前有效结论」表（§109~§114 的数字均已进该表并注明来源产物）。

### §115 ✅ **APP-050 TTS 启动日志打印各组件 `EXECUTION_DEVICES` —— talker / cp_prefill / cp_decode / decoder 实测**全部 NPU**｜ 顺带修掉「`EXECUTION_DEVICES` 被逐字符拆开」这个**误读根因**｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **依据**：reviewer 转达（TTS reviewer 10-31 Opus）—— `qwen3tts_eval` 里裸 `build()` 默认把 `cp_decode` 放在 CPU，只有调了 `_recompile_cp_on_npu(only=["cp_decode"])` 之后才会到 NPU（TTS-037 正在把默认改成 NPU）；cp_decode 在 CPU 上会让 TTS 的 RTF 变差约 30%（1.01 vs 0.71）。
- 🔴 **APP-050 要求**：① 在 TTS **启动日志**里打印 `talker` / `cp_prefill` / `cp_decode` / `decoder` 各自**实际**的 `EXECUTION_DEVICES`，确认**全部是 NPU**；② 「如果你是直接调 `build()`，要显式传 `cp_decode_device="NPU"`」；③ **把一行日志证据写进 STATUS**；④ **不用另外做测速**。

### ① 先答「App 是不是直接调 `build()`」——**不是**

- 🔴 **App 侧完全不依赖 `qwen3tts` 模块**（`grep` 仓库 `live_caption/tts_engine.py` / `tts_worker.py` / `tts_engine_patch.py` / `tts_service.py` ⇒ `import qwen3tts` **0 命中**；只有注释里提到 `qwen3tts_eval/TTS_交接单.md` 与 `qwen3tts_patch.py` 两个**文件路径**）。
- 🔴 **App 走的是自己的等价路径**：`tts_engine.make_engine()` → `babelvox.BabelVox` / vendored `MultiDecoderBabelVox`（`tts_engine_patch.py`）→ **事后**把 `cp_decode` / `cp_prefill` **重编译到 NPU**（`_move_cp_decode_to_npu()` / `_move_cp_prefill_to_npu()`，`tts_engine.py` L920 / L852）。
- ⇒ **APP-050 第②条的前提不成立** ⇒ 「显式传 `cp_decode_device="NPU"`」**对 App 不适用**（`cp_decode_device` 是 `qwen3tts_patch.QuantEvalBabelVox` 的字段，App 从不构造那个类）。
- ⇒ App 侧的**等价保证**就是那两个 `_move_*_to_npu()` 搬运函数（**已实现**，见 §115③ 的日志证据：`cp_decode: NPU` / `cp_prefill: NPU` 两行）。

### ② 🔴🔴🔴 **本轮抓出的真缺陷：旧代码把 `EXECUTION_DEVICES` 逐字符拆开了**

- 🔴 **实测（本轮新增）**：`results/app/app174a_exec_devices_type.json` ⇒ OV `2026.4.1` 的 `get_property('EXECUTION_DEVICES')` **返回类型随设备而异**：
  - **NPU 档 ⇒ 字符串 `'NPU'`**（`raw_type='str'`）
  - **CPU 档 ⇒ 列表 `['CPU']`**（`raw_type='list'`）
- 🔴 **旧代码写的是 `list(devs)`** ⇒ 对 NPU 档的字符串 `'NPU'` ⇒ `list('NPU')` = **`['N','P','U']`**。
- 🔴🔴 **⇒ 旧文档里那段「NPU 插件返回**缩写 fallback 链** `[N,P,U]`」的解读是错的** —— 那是**把「字符拆分」当成了「fallback 链」**；`chain[0]`（链首 = 首选 = 实际落点）这个结论**建立在误读之上**。
- 🔴🔴 **更要命的推论**：若 CPU 档也返回字符串 `'CPU'` ⇒ `list('CPU')` = `['C','P','U']` ⇒ 链首 `'C'` **不在**旧映射表里 ⇒ 落进 `on_unknown` ⇒ **「NPU 静默回落 CPU」永远不会被 `on_cpu` 抓到** ⇒ **静默漏报**。（反证已固化进单测：`反证.旧实现漏报CPU回落`。）
- ✅ **修法**：新增 `_norm_exec_devices(raw)`（`tts_engine.py`）—— **字符串按「单个设备名」处理**（支持逗号分隔多设备），**绝不逐字符拆**；同时**保留**单字母兼容映射（`N`→`NPU` / `P`→`CPU` / `U`→`UNKNOWN`）⇒ §82 旧证据的解读**不被破坏**，且**真·fallback 链**（若某 OV 版本真返回 `['N','P','U']`）仍能正确解读。

### ③ 🔴🔴🔴 另外三个真缺陷（旧证据里**从来没测到过** talker 桶与解码器桶）

- 🔴 **缺陷 3：talker 桶的键是 `int`，旧代码用 `str` 查 ⇒ 5 个 talker 桶从来没被探测过。**
  `babelvox/pipeline.py` L322-330 ⇒ `for bsize in self.talker_bucket_sizes: self.talker_buckets[bsize] = cm` ⇒ **键 = int**（64/128/256/384/512）；旧代码 `buckets.get('64')` ⇒ **永远取不到** ⇒ **静默丢弃**。
  ⚠️ **连带**：`pipeline.py` 的**有桶分支不编译 `self.talker`** ⇒ `getattr(eng, 'talker')` 是 `None` ⇒ **旧日志里「talker」这一行根本没出现过** ⇒ APP-050 问的「talker 在哪」**从来没被回答过**。
- 🔴 **缺陷 4：解码器多桶 `_dec_bucket_models` 从未被探测。**
  `tts_engine_patch.py` L101/L407 ⇒ 运行时**真正用来解码**的就是这些桶（`_select_decoder()` L107-114）⇒ 旧代码只报了 `tok_decoder`（= 最大桶那个）⇒ **APP-050 要求的「decoder 实际在哪」根本没被测到**。
- 🔴 **缺陷 5：「未启用」与「落点不明」混在一起。**
  `talker_prefill` / `talker_decode` 只在 `use_kv_cache=True` 时才编译（App 恒 `False`）；`code_predictor` 只在 `use_cp_kv_cache=False` 时才编译（App 恒 `True`）⇒ 它们**本来就不该存在** ⇒ 混进 `unknown` 会让 reviewer **误以为「这几个组件落点不明」⇒ 误判成「有组件在 CPU 上」**。
  ⇒ 拆成 `absent`（未启用/不存在）与 `unknown`（取不到落点）**两个字段**。
- ✅ **修法**（全在 `live_caption/tts_engine.py`）：① `_norm_exec_devices()` ② talker 桶用 **int 键**取 ③ 探测 `_dec_bucket_models` ④ `absent` / `unknown` 分开 ⑤ 新增 **`key4_line`**（APP-050 要的那一行）⑥ `talker` 在有桶时**聚合所有桶的落点**（否则永远是 `talker=?` ⇒ 等于没回答）。

### ④ ✅ **APP-050 要的那一行（启动日志原文）**

```text
[tts_engine] EXECUTION_DEVICES talker=NPU，cp_prefill=NPU，cp_decode=NPU，decoder=NPU/NPU/NPU/NPU/NPU/NPU/NPU/NPU/NPU
```

- 🔴 **来源**：`results/app/app174d_worker_startup_e2e.json` → `key4_line`（**真实 TTS worker 进程** stdout 抓取，`ready_seen=true`，`wall_s=13.41`）。
- 🔴 **四个组件全部 NPU** ⇒ **APP-050 的核心问题「确认全部是 NPU」= 已确认**。

### ⑤ ✅ 三层证据（离线单测 / 直接调引擎 / 真 worker 进程）

| 层 | 产物 | 结果 | 关键字段 |
|---|---|---|---|
| ① 前置探针（OV 返回类型） | `results/app/app174a_exec_devices_type.json` | NPU=`'NPU'`(str) / CPU=`['CPU']`(list) | `probes.NPU.raw_type='str'`、`probes.CPU.raw_type='list'` |
| ② 离线单测（含 5 条反证） | `results/app/app174b_exec_devices_unit.py` | **34 PASS / 0 FAIL** | `n_pass=34`、`n_fail=0`、`verdict=PASS` |
| ③ 直接调 `make_engine` | `results/app/app174c_startup_log_evidence.json` | **15 PASS / 0 FAIL**；`on_npu=17`、`on_cpu=[]`、`on_unknown=[]` | `verdict=PASS`、`actual`（17 个组件逐个 NPU） |
| ④ 真 worker 进程 e2e | `results/app/app174d_worker_startup_e2e.json` | **10 PASS / 0 FAIL**；`ready_seen=true` | `key4_line`、`n_pass=10` |

- 🔴 **反证组已固化**（判据**非恒真**）：`反证.旧实现把CPU字符串算成C`、`反证.旧实现漏报CPU回落`、`反证.旧实现把NPU字符串拆成字符`、`反证.旧实现用str键取不到talker桶` 四条 ⇒ 旧实现在这些用例上**必错** ⇒ 新判据能**识破**旧实现。
- 🔴 **17 个组件逐个落 NPU**（`actual` 全量）：`speaker_enc` / `cp_prefill` / `cp_decode` / `tok_decoder` / `talker_bucket@{64,128,256,384,512}` / `decoder_bucket@{8,16,32,33,40,64,128,256}`。
- 🔴 **`devices_raw` 全为字符串 `'NPU'`** ⇒ 在**真实模型**上再次印证了 ② 的类型结论（不是极小探针的特例）。
- 🔴 **`absent` = `['talker_prefill','talker_decode','talker','code_predictor']`** ⇒ 这四个是**该档位下不编译**（`talker` 以 5 个桶形式存在）⇒ **不是**「落点不明」。

### ⑥ ✅ 客户包定点同步（**两份独立副本，禁整目录覆盖**）

- ✅ **新增 `live_caption/sync_c173_app050_to_pkg.py`**（**6 913 B**）—— 沿用 `sync_c170` 的**已验证骨架**：`difflib` 派生替换块（归一化 LF）＋ **OLD 取自包内实际内容** ＋ **唯一命中断言** ＋ **位置复核** ＋ **占位符两阶段/倒序应用** ＋ 写前 `ast.parse` ＋ **按包内原行尾还原** ＋ 写后**逐字节复核**。
- ✅ **同步执行**：先 `--dry-run`（**17 个替换块**）⇒ 再实际写入（**2 个替换块**，第二轮微调）⇒ 包内 `app/tts_engine.py` **85 233 B / SHA256 `0d60ebcc27c25825efd5fa5b8134a227a6e6ffb2f1ac38298ac83b4196af4931`**。
- ✅ **仓库 ⇄ 包目录逐字节一致**（归一化行尾）：`tts_engine.py` repo=`0d60ebcc27c2` pkg=`0d60ebcc27c2`（85 233 B）；`tts_engine_patch.py` / `tts_worker.py` / `tts_service.py` 亦**逐字节一致**。
- 🔴 **本轮未打包**（用户 11:30 指令：未经通知不主动打包）⇒ **v1.13 zip 仍不存在** ⇒ 客户机上**看不到**本条改动（须等用户通知后打包）。

### ⑦ 🔴 **本条需等 reviewer 复核（4 项）**

1. 🔴 **`EXECUTION_DEVICES` 的解读口径**：本轮结论「OV 返回的是字符串 `'NPU'`（NPU 档）/ 列表 `['CPU']`（CPU 档），**不是**缩写 fallback 链」—— 是否接受？**这推翻了 §82 的旧解读**（旧解读虽结论同为「在 NPU」，但**依据错误**，且**漏报 CPU 回落**）。
2. 🔴 **`absent` 与 `unknown` 分离**：把「该档位下不编译的组件」从「落点不明」里拆出来 —— 是否认可？（否则 reviewer 会持续误读「有组件落点不明」。）
3. 🔴 **`talker` 聚合所有桶的落点**（而不是打 `talker=?`）—— 是否认可这个口径？
4. 🔴 **APP-050 第②条「显式传 `cp_decode_device="NPU"`」对 App 不适用**（App 不调 `build()`，走自己的 `_move_*_to_npu()` 搬运）—— 是否认可这一判读？
5. 🔴 **附带建议（不阻塞）**：TTS 模块的 `qwen3tts_patch.py` 里 `cp_decode` 恒编 CPU（`qwen3tts_eval/diag_cp_device_audit.py` 已指出 `cp_decode_device` 是**未被消费的声明字段**）⇒ 若 TTS-037 把默认改成 NPU，**App 侧无需改动**（App 不依赖那个类）—— 请 reviewer 确认这条链路判断。

### ⑧ 🔴 **未做 / 仍阻塞**

- 🔴 **未打包**（用户 11:30 指令）⇒ v1.13 zip 不存在 ⇒ **客户机上还看不到这一行**。
- 🔴 **未测速**（APP-050 明写「不用另外做测速」）⇒ 本条**不涉及** RTF 结论。
- 🔴 **未做质量判定**（交 reviewer；本轮只做设备落点取证，不评音质）。
- 🔴 **APP-043 真机验收 / APP-045③ / v1.13 打包**仍未做 ⇒ 见头部「阻塞 / 待用户决定」。
