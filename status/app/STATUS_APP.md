# STATUS_APP

last_ack: APP-051
更新时间: 2026-11-01 01:07
当前任务: **§117 ✅ APP-051 三条子项全部完成** —— ① **重打 v1.13**（持共享机器锁，`--same-version` 不吃版本号）：11 233 347 633 B / **14 213 文件** / 压缩 557 s / 压缩率 82.1 % / `testzip()` Ok / **zip ⇄ 包目录 14 213 文件逐字节一致** / **SHA256 `6576dabd3c100646eeed9f45cdaf48ad3af028eba190fee519ca9f39ec2181d5`**（已用 `sha256sum` **独立复核**一致）⇒ 打包闸门 §48（0 处违规）/ §113 版本标识 + NOTICE 署名（I1~I6 + D1~D5 全 PASS）/ 内部素材 0 命中 / 内部会议内容 0 残留 / 第三方素材 0 / 音色 B·C·克隆素材 0 / 开发脚本 0；**NOTICE 9 644 B + THIRD_PARTY.md 3 784 B 在包内**（pyannote MIT / wespeaker CC BY 4.0 / babelvox Apache-2.0 / Qwen3-TTS Apache-2.0）② **APP-043 真机验收 5 子项全 PASS**（总闸门 `app186` **25 PASS / 0 FAIL**，`accepted=true`）：①pythonw 冷启动（`n_pass=11`/`n_fail=0`，两次 `client_n_colors=[552,550]`）②SPE Q&A 双说话人克隆（`n_pass=26`/`n_fail=0`，`83+0==83`，`n_clone_rows=52`，`n_spk_tagged_lines=7`）③GUI 加速播放（`n_pass=8`/`n_fail=0`，`n_accel_rows=21`/`rows=22`）＋ 公式一致性（`app183` **6/0**，`n_samples=21`，步长限制触发 2 次）④APP-048 两种分辨率（`app185` 在**包内代码**上跑 **64/0**，`diff_pixels=9492`）⑤3 段 1.2–1.3× 实听素材（`app184` **7/0**，零推理切出，SHA256 互不相同）；🔴 **判据鉴别力实测**（`app186_discrimination_test.py`）：注入 **5 处**已知缺陷 ⇒ **恰好 5 条**判据 FAIL ⇒ `verdict=FAIL`，对照组 PASS ⇒ **判据非恒真**；③ **`ACCEPTED.json` 已写**（909 B / `accepted_at=2026-11-01 00:43:32` 实测值 / **已随包进 zip**）＋ **桌面快捷方式已指向 v1.13**（`Confucius4 实时字幕 v1.13.lnk` 554 B，旧的无版本号已清理，桌面仅 1 个）⇒ 详见 **§117**
阻塞 / 待用户决定: ① 🔴 **需用户实听 3 段 1.2–1.3× 配音素材**（`C:\Users\Trekker-PTL\shared\app_accel_listen\`：1.2× / 1.3× / 1.3×）＋ **reviewer 判定音质 / 不变调 / 可懂** —— 本轮 `app186` 总闸门只覆盖**链路 + 结构 + 数字自洽**（`ACCEPTED.json.scope` 已明写），**质量判定不在其中**；② 🔴 **§117 待 reviewer 复核 3 项**（① APP-043「通过」口径 ② `app186` 总闸门 25 条判据口径 ③ `app186` 写死包版本的修法）；③ 🔴 **v1.12 / v1.5 等历史 zip 仍是旧内容**（v1.12 内 README/NOTICE 自称 v1.6 的缺陷**只在 v1.13 已修**，历史包本轮**未重打**、旧包目录**未删除**（破坏性操作需用户确认））；④ 🔴 **§115 待 reviewer 复核 5 项**（① `EXECUTION_DEVICES` 返回类型口径——**推翻了 §82 的旧解读** ② `absent`/`unknown` 分离 ③ `talker` 聚合所有桶 ④ App 不调 `build()` ⇒ 第②条不适用 ⑤ TTS 模块 `cp_decode_device` 未被消费 ⇒ App 无需改动）；⑤ 🔴 **§114 待 reviewer 复核 4 项**（CI 判据口径 / 写法差异 vs 真错误拆分规则 / 多 3 句真错误是否提示用户 / 是否用最新包重跑）；⑥ 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围待 reviewer 确认**（§112 已证明它会让 `torch` 假阳性；§109/§110 为静态字节比对，未受影响）；⑦ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入，SHA256 `327f8653…39904` 零改动）；⑧ 🔴 **§113 待 reviewer 复核 4 项**（版本标识闸门口径 / 「改动说明」归为提醒不阻断 / `sync_c172`「只改身份行不改内容」设计 / v1.13 改动说明排期）
已压缩: 原文见 `status/archive/STATUS_APP_upto_20261030.md`（1 437 968 B，只读归档）；纠偏归档见 `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_APP_full_before_compress_20261030.md`）。**本文件 52 895 B / 408 行**（原 1 437 968 B / 18 977 行 ⇒ **−96.4%**；§117 追加后）。


## 最近更新

- 2026-11-01 01:07 **§117 APP-051 三条子项全部完成** ⇒ ① **重打 v1.13**（持共享机器锁，`--same-version`）：11 233 347 633 B / **14 213 文件** / 557 s / `testzip()` Ok / **zip ⇄ 包目录逐字节一致** / **SHA256 `6576dabd…181d5`**（`sha256sum` 独立复核一致）；闸门 §48 0 违规 / §113 版本标识 + NOTICE 署名全 PASS / 内部素材 0 / 克隆音色 0 / 示例音色 0；**NOTICE 9 644 B + THIRD_PARTY.md 3 784 B 在包内** ② **APP-043 真机验收 5 子项全 PASS**（`app186` 总闸门 **25/0**，`accepted=true`）；🔴 **鉴别力实测**：注入 5 处缺陷 ⇒ 恰好 5 条 FAIL ⇒ 判据非恒真 ③ **`ACCEPTED.json` 已写（909 B，已进 zip）＋ 桌面快捷方式指向 v1.13**（554 B，旧的无版本号已清理）
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
| 客户包目录 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13`（**当前最新**；v1.12 目录仍在，未删除） | `Confucius4_LiveCaption_v1.13/MANIFEST.json` → `version=1.13`（`DELIVERY_1.13.json` → `manifest_version`） |
| 客户包 zip | **v1.13**（**2026-11-01 00:55:58 重打** / **11 233 347 633 B** / **14 213 文件** / SHA256 **`6576dabd3c100646eeed9f45cdaf48ad3af028eba190fee519ca9f39ec2181d5`**）⇒ **含** APP-045/047/048/050/051/052 代码 ＋ `ACCEPTED.json` ＋ `NOTICE` ＋ `THIRD_PARTY.md` | `results/app/DELIVERY_1.13.json` → `sha256` / `bytes` / `mtime`；`sha256sum` **独立复核一致**；`results/app/pack_v13_app051_repack4.log` → 「比对 14 213 个文件 / 全部逐字节一致」 |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | TTS 走 NPU（F16 / INT8 视配置） | `app048_layout_1920x1080.png`（语音区实测「Intel NPU · F16」） |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出），顶部只留全局 | `app185_app048_gui_layout_pkg_evidence.json` → `verdict=PASS` / `n_pass=64` / `n_fail=0` / `pkg_under_test=…_v1.13\app`（**在客户包内代码上跑**） |
| 桌面快捷方式 | **已指向 v1.13**（`Confucius4 实时字幕 v1.13.lnk` 554 B / SHA256 `770271ac…bdffd`；旧的**无版本号**快捷方式已清理 ⇒ 桌面仅 1 个） | §117 ③ 表格；目标 `…_v1.13\Start_LiveCaption.bat`（`shortcut_update.py` 真机验收门 `is_accepted()` 通过） |

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
| APP-043 | ASR 说话人接口已交付，APP-039/040 克隆资产可取（真机验收全套） | ✅ **本轮已完成**（§117）：真机验收 5 子项全 PASS（`app186` 总闸门 **25/0**）⇒ `ACCEPTED.json` **已写**（909 B，已进 zip）；🔴 **仍需用户实听 3 段 1.2–1.3× 素材**（`shared/app_accel_listen/`）＋ **reviewer 判定音质 / 不变调 / 可懂**（本轮只判链路 + 结构 + 数字自洽） |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | ✅ **本轮已完成**（§117）：桌面快捷方式已指向 **v1.13**（`Confucius4 实时字幕 v1.13.lnk` 554 B）⇒ **③ 已闭合**；**② 打包后自动更新**仍生效（`shortcut_update.py` 的 `is_accepted()` 真机验收门） |
| APP-048 | GUI 状态信息按 ASR / 翻译 / 语音输出分区 | ✅ **本轮已完成**（§117）：「和 v1.13 一起交付」**已满足** —— 布局代码在 v1.13 包内（`app185` 在包内代码上跑 **64/0**）+ 三张截图落盘 `shared/app_gui_layout/` |
| APP-049 | 压缩 STATUS / CORRECTIONS | ✅ 本节已完成（§111）；🔴 需 reviewer 确认归档内容与索引表无误 |
| APP-051 | 重打 v1.13（记录 SHA256 / NOTICE 署名 / 打包闸门）＋ APP-043 真机验收 ＋ `ACCEPTED.json` ＋ 桌面快捷方式 | ✅ **本轮已完成**（§117）：三条子项全做完；🔴 **待 reviewer 复核 3 项**（见 §117 ⑤） |


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

### §116 ✅ **APP-050 git 收尾（commit / push）** ｜ 🔴 **顺带抓出并更正 §115 的一处事实错误：「v1.13 zip 仍不存在」—— zip 其实存在，只是不含本轮代码** ｜ **本条已完成** ｜ **本条需等 reviewer 复核（2 项）**

> 本节**只追加**，不改 §115 任何正文。§115 里被更正的那句，用下面的「撤回」条目显式撤回。

#### ① ✅ git 收尾（commit + push）

| 项 | 结果 |
|---|---|
| commit | **`8f1a645`** —— `feat(app): §115 —— APP-050 TTS 启动日志打印各组件 EXECUTION_DEVICES（修正 list() 逐字符拆分误读）` |
| 提交范围 | **13 个文件**：`live_caption/tts_engine.py`（改）、`live_caption/sync_c173_app050_to_pkg.py`（新）、`results/app/app174{a,b,c,d,e}_*`（8 个）、`results/app/app174_run_with_lock.py`、`status/app/STATUS_APP.md`（改）、`status/archive/STATUS_APP_sec109_114_upto_20261031.md`（新） |
| 变更规模 | 2 259 insertions / 158 deletions |
| push | **普通 push 成功**：`6cc0054..8f1a645  main -> main`（`git push origin main`）⇒ **未用 force push** |
| 分支 | **仅 `main`**（`git branch -a` = `main` + `remotes/origin/main`；无其它本地分支）⇒ 符合「仓库只保留 main 分支」 |
| 同步状态 | `git rev-list --left-right --count origin/main...main` = **0  0** ⇒ 本地与远端**完全一致** |
| 🔴 **未吞别的模块改动** | 工作区共有 **553 项** `git status --porcelain` 变更（ASR / MT / TTS / 根目录脚本等）⇒ **逐文件 `git add`**（**未用 `-A`**）⇒ 本次 commit **只含上表 13 个 App 侧文件** |
| 🔴 **`CORRECTIONS_APP.md` 未入库** | `git show --name-only --format="" HEAD \| grep CORRECTIONS` ⇒ **空**；且工作区文件仍 **119 646 B / SHA256 `0e402635244db8ef62e28cd024263a6fded223ccfce072a0a0e1e415901884c4`**（**零改动**，reviewer 独占写入） |

#### ② 🔴 **入库前两道素材闸门（都 PASS）**

| 闸门 | 结果 |
|---|---|
| `check_internal_material.py --staged --repo . --verbose` | **命中 0 个内部素材 ⇒ PASS**（脚本自报） |
| `app007_cn_exact.json` **20 条精确中文引文**独立复核（不依赖闸门正则 ⇒ 防「闸门正则失效导致假通过」） | **命中 0**（对 13 个待提交文件全文扫描） |
| 归档逐字复核 | HEAD 版 STATUS 的 **§109~§114 共 6 个章节**正文 **逐字**存在于 `status/archive/STATUS_APP_sec109_114_upto_20261031.md`（25 909 B）⇒ **无一缺失**（旧章节内容**一字未删**） |
| STATUS 自指大小 | 实测 **27 925 B / 178 行**；文内 `本文件 34744 B / 241 行` ⇒ **一致**（两遍法收敛 + 独立复核） |

#### ③ 🔴🔴 **撤回 §115 的一处事实错误：「v1.13 zip 仍不存在」**

- 🔴 **§115 原文（现撤回）**（两处：⑥ 与 ⑧）：
  > 「🔴 **本轮未打包**（用户 11:30 指令：未经通知不主动打包）⇒ **v1.13 zip 仍不存在** ⇒ 客户机上**看不到**本条改动（须等用户通知后打包）。」
  > 「🔴 **未打包**（用户 11:30 指令）⇒ v1.13 zip 不存在 ⇒ **客户机上还看不到这一行**。」

- 🔴 **实测事实**（`Get-ChildItem` + `Get-Item`，2026-10-31 10:37 实测）：

  | 对象 | 大小 | mtime | 含义 |
  |---|---|---|---|
  | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13.zip` | **11 233 343 245 B** | **2026-10-31 09:17:06** | **zip 确实存在**（§115 说「不存在」⇒ **错**） |
  | `Confucius4_LiveCaption_v1.13\app\tts_engine.py`（包目录） | 85 233 B | **2026-10-31 10:30:10** | 本轮 APP-050 代码写入**包目录**的时刻 |
  | `confucius4-openvino\live_caption\tts_engine.py`（仓库） | 85 233 B | 2026-10-31 10:31:34 | 仓库副本 |

  ⇒ **zip 的 mtime（09:17:06）早于本轮代码写入包目录（10:30:10）** ⇒ **zip 不含本轮 APP-050 代码**。

- ✅ **结论不变，理由更正**：
  | | §115 的说法（现撤回） | §116 的更正 |
  |---|---|---|
  | zip 是否存在 | 「不存在」 | 🔴 **存在**（11 233 343 245 B / 09:17:06） |
  | 客户机能否看到本条改动 | 「看不到」 | ✅ **仍然看不到**（因为 zip 是**改动前**打的） |
  | 真正的原因 | 「未打包 ⇒ 不存在」 | 🔴 **zip 是 APP-050 改动之前生成的旧包**；本轮**遵守「不主动打包」指令未重打** ⇒ 需用户通知后重打包才闭合 |

- 🔴 **顺带更正头部「交付配置」表的一处过期值**（该表在正文区，按纪律**不改表**，在此记录）：「客户包目录 = `Confucius4_LiveCaption_v1.12`（**当前唯一**）」⇒ 磁盘实测**同时存在** `Confucius4_LiveCaption_v1.12` 与 `Confucius4_LiveCaption_v1.13`（**目录** mtime 2026-10-30 03:57）⇒ **当前最新包目录是 v1.13**，v1.12 目录已非「唯一」。**本轮未删除任何旧包目录 / 旧 zip**（删除属破坏性操作，需用户确认）。
- 🔴 **本轮仍为「未打包」状态**：**没有**运行 `pack_v13.py`，**没有**新 zip 产生（用户 2026-10-30 11:30 指令：未经通知不主动打包；且 `pack_v13.py` 启动即改源目录名，中止会白吃版本号）。

#### ④ 🔴 **本条需等 reviewer 复核（2 项）**

1. 🔴 **「v1.13 zip 已存在但不含本轮代码」这一更正是否接受**？（即：交付口径应以「zip 内容是否含本轮代码」为准，而不是以「zip 文件是否存在」为准 —— 后者曾导致 §115 写出错误事实。）
2. 🔴 **是否要现在重打包 v1.13**？（需要用户明确通知；本轮未打包。**建议在重打包前先跑打包前闸门** `results/app/app170_version_identity_gate.py`，避免 §113 修掉的「版本标识在打包时复发」问题再次发生。）

#### ⑤ 🔴 **未做 / 仍阻塞（本轮不变）**

- 🔴 **未重新打包** ⇒ 客户机上仍看不到 APP-050 那一行日志（**等用户通知**）。
- 🔴 **未测速 / 未做质量判定**（APP-050 明写「不用另外做测速」；质量判定交 reviewer）。
- 🔴 **APP-043 真机验收 / APP-045③（桌面快捷方式仍指向 v1.5）** 仍未做 ⇒ 见头部「阻塞 / 待用户决定」。

### §117 ✅ **APP-051 三条子项全部完成：① 重打 v1.13（SHA256 已记录 / NOTICE+THIRD_PARTY 在包内 / 打包闸门 0 命中）② APP-043 真机验收 5 子项全 PASS（总闸门 25/0）③ 写 `ACCEPTED.json` + 桌面快捷方式更新到 v1.13** ｜ **本条已完成** ｜ **本条需等 reviewer 复核（音质 / 不变调 / 可懂由用户实听 + reviewer 判定）**

> 🔴 **本节只追加，不改旧章节**；旧结论被本轮推翻的地方写在 ④「撤回 / 更正」里。
> 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入）⇒ 该文件在本轮开工前 mtime `2026-10-31 10:48` / 120 787 B / SHA256 `327f8653b62f28b602bb9f50171d1bb453eb1c722adeb0988856d91b01339904`（**零改动**）。
> 🔴 **本轮最大 APP 编号 = APP-051**（`CORRECTIONS_APP.md` 条目 `APP-001` … `APP-051`）⇒ 本轮执行范围 = APP-051（`last_ack` 由 APP-050 推进到 **APP-051**）。

#### ① 🔴 **APP-051① 重打 v1.13 —— 已完成**

- ✅ **重打包命令**（**持共享机器锁**；锁内容 `app-pack PID 1848 started 2026-11-01 00:44:04`，作业结束已释放）：

  ```
  python pack_v13.py --same-version \
      --pkg "C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13" \
      --zip "C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13.zip" \
      --prefix "Confucius4_LiveCaption_v1.13"
  ```
  ⚠️ 用 `--same-version` ⇒ **不递增版本号、不改源目录名**（避免「中止白吃版本号」）。
  ⚠️ 取锁后**等安静窗口 45 s**（实测等待 ~135 s：WorkBuddy 自身后台 python 造成 2 次「在算」误判 ⇒ fail-closed 生效 ⇒ 继续等 ⇒ 通过）。

- ✅ **打包结果**（日志 `results/app/pack_v13_app051_repack4.log`，17 190 B / mtime 2026-11-01 00:59:16 / SHA256 `a5e1f8ecce42c199677c2a234e66775cd1a0ea42aa2b9d704b048a6f3a4f1fa3`）：

  | 项 | 实测值 |
  |---|---|
  | 文件数 | **14 213**（上次 14 212 ⇒ **+1 = `ACCEPTED.json`**） |
  | 原始字节 | **13 689 650 757** |
  | 压缩后字节 | **11 233 347 633**（10.46 GB） |
  | 压缩率 | **82.1 %** |
  | 压缩耗时 | **557 s** |
  | `testzip()` | **Everything is Ok** |
  | zip ⇄ 包目录逐文件 SHA256 | **比对 14 213 个文件 ⇒ 全部逐字节一致** |
  | md5 | `be8634d667b24340d9122c5f1185fdf8` |
  | **SHA256** | **`6576dabd3c100646eeed9f45cdaf48ad3af028eba190fee519ca9f39ec2181d5`** |
  | zip 文件 mtime | **2026-11-01 00:55:58** |

  🔴 **SHA256 独立复核**：`sha256sum Confucius4_LiveCaption_v1.13.zip` = `6576dabd…181d5` ⇒ **与打包脚本落盘值一致**（不是自己抄自己）。
  🔴 **交付指纹**已落盘 `results/app/DELIVERY_1.13.json`（445 B / mtime 2026-11-01 00:59:15 / SHA256 `055a8913a8bff4152fda1e67bd9d74ae034122fcbfec0742ba4adee95e7f01b8`）
  → 原始字段：`version="1.13"`、`bytes=11233347633`、`mtime="2026-11-01T00:55:58"`、`md5="be8634d667b24340d9122c5f1185fdf8"`、`sha256="6576dabd3c100646eeed9f45cdaf48ad3af028eba190fee519ca9f39ec2181d5"`、`manifest_version="1.13"`、`manifest_files=14212`、`manifest_bytes=13689628175`。
  🔴 **旧 zip 指纹（已被本轮取代，留作对照）**：11 233 343 245 B / mtime 2026-10-31 09:17:06 / SHA256 `52d014585b71ce573263536ac0f8f146673396aee504968764ff965c6b661079`。
  🔴 **zip 内 `app/tts_engine.py` SHA256 = `eea087756981eb47efaa2595e2ff444c3a2e8ee9a85bb82bbceb5b419d7ee0c4`** ⇒ 与包目录、与仓库工作区**三者逐字节一致**（APP-052 修复已在包内）。

- ✅ **打包闸门全部通过**（逐条引用日志原文）：

  | 闸门 | 结果 | 日志依据 |
  |---|---|---|
  | §48 包路径写死 | **总判定 PASS（0 处违规）** | 「命中『代码行里有客户包名』的文件数 = 102 / ✅ 0 处违规 / 总判定：PASS」 |
  | §113 版本标识一致 + NOTICE 许可署名 | **I1~I6 + D1~D5 全 PASS** | 「D3 NOTICE 首行版本号 == 1.13 got=1.13」；BUG 组 D3 `got=1.6` ⇒ 判据有鉴别力 |
  | 内部素材闸门（APP-006 第 6 步） | **命中 0 个内部素材** | 「结论：PASS —— 未发现内部素材」 |
  | 内部会议内容 | **源目录残留 0 个** | 「`*_spoken.*`（0 条命中）/ 点名文件（0 条命中）」 |
  | 第三方素材 / 音色 B·C / 克隆素材 / 开发脚本 | **各 0 条命中** | 「第三方素材（0 条命中）」「音色 B/C/克隆素材（0 条命中）」「开发专用脚本（0 条命中）」 |
  | 关键文件抽查 | 全 **[OK]** | `NOTICE` 9 644 B / `THIRD_PARTY.md` 3 784 B / `Start_LiveCaption.bat` / `Diagnose.bat` / `app/MANIFEST.json` / 两套 MT 模型 / Qwen3-TTS 全套 |

- ✅ **第三方许可署名已在包内**（APP-051 明写 wespeaker 是 CC-BY-4.0 必须署名）：
  - zip 内 `NOTICE` = **9 644 B**，首行版本号 **1.13**；
  - zip 内 `THIRD_PARTY.md` = **3 784 B**；
  - 闸门逐条 PASS：`I2 NOTICE 仍含 wespeaker 署名` / `I3 NOTICE 仍含 pyannote 署名` / `I4 NOTICE 仍含 MIT 许可` / `I5 NOTICE 仍含 CC BY 4.0 许可` / `I6 NOTICE 未笼统声称「均为 Apache-2.0」`；
  - 覆盖 **pyannote(MIT) / wespeaker(CC BY 4.0) / babelvox(Apache-2.0) / Qwen3-TTS(Apache-2.0)**。

- 🔴 **本轮抓出并修掉一个真缺陷（由打包闸门抓出，不是我自己想到的）**：
  闸门 §48 在 dry-run 阶段**判 FAIL**，命中 `results/app/app186_app051_acceptance_gate.py` 第 40 行
  `PKG_DIR = os.path.join(HOME, 'Confucius4_LiveCaption_v1.13')` —— **写死版本号** ⇒ 升版后会指着旧包跑（§47.6 同类事故）。
  ⇒ 修法：改用 `pkg_paths.resolve_pkg_dir()`（**§48 单一数据源**）+ 新增 `--pkg` 参数 ⇒ 复跑 dry-run **0 处违规** ⇒ 打包放行。
  ⇒ **教训**：「判据 PASS」不等于「产品无缺陷」——**闸门对自己新增的脚本同样生效**，这是它有效性的旁证。

#### ② 🔴 **APP-051② / APP-043 真机验收 —— 5 个子项全 PASS（总闸门 25 PASS / 0 FAIL）**

- ✅ **总闸门脚本**：`results/app/app186_app051_acceptance_gate.py`（17 105 B / mtime 2026-11-01 00:43:26 / SHA256 `2de6663aec5664d763fa37e48d9784cc298afe7bbf71ad35f93a085663fd063a`）。
  **设计要点**：「验收通过」必须是**一个明确的判据**而不是人工印象 ⇒ 收 5 个子项**已落盘**证据，逐项核对「证据存在 + `verdict=PASS` + **指向 v1.13 包**」⇒ 全部通过才给 `accepted=true`。
- ✅ **证据**：`results/app/app186_app051_acceptance_gate_evidence.json`（5 199 B / mtime 2026-11-01 00:43:32 / SHA256 `feb3ab586c35bf95cb91c3ea7a00f11a332df01aef99cb5928c2f09958be0c44`）
  → 原始字段：`verdict="PASS"`、`n_pass=25`、`n_fail=0`、`accepted=true`、`pkg_dir="C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13"`、`pkg_version="1.13"`、
  `sub_items = {"1_pythonw_coldstart": true, "2_spe_qa_clone": true, "3_gui_accel": true, "4_gui_layout_2res": true, "5_accel_listen_1.2_1.3": true}`。

  | 子项 | 证据文件 | 原始字段 |
  |---|---|---|
  | ① pythonw 冷启动（用户启动方式） | `results/app/app181_pythonw_coldstart_v2_evidence.json` | `verdict=PASS`、`n_pass=11`、`n_fail=0`、`pkg=C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13`、`client_n_colors=[552, 550]`（两次独立冷启动都截到有内容的客户区） |
  | ② SPE Q&A 双说话人克隆 | `results/app/app175_app043_clone_acceptance_evidence.json` | `verdict=PASS`、`n_pass=26`、`n_fail=0`、`pkg=v1.13`、`n_played + n_dropped == n_submitted` ⇒ **83 + 0 == 83**、`n_clone_rows=52`、`n_spk_tagged_lines=7` |
  | ③ GUI 加速播放（链路 + 公式） | `results/app/app179_app042_gui_accel_evidence.json` | `verdict=PASS`、`n_pass=8`、`n_fail=0`、`pkg=v1.13`、`n_accel_rows=21` / `rows=22`（**真的触发了 speed>1.0**） |
  | ③ 加速倍率公式一致性 | `results/app/app183_app042_formula_evidence.json` | `verdict=PASS`、`n_pass=6`、`n_fail=0`、`n_samples=21`、`n_step_limit_triggers=2` |
  | ④ APP-048 两种分辨率（**在包内代码上跑**） | `results/app/app185_app048_gui_layout_pkg_evidence.json` | `verdict=PASS`、`n_pass=64`、`n_fail=0`、`pkg_under_test="C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13\app"`、`diff_pixels_normal_vs_failed=9492`、`error_red_pixels_in_failed=767` |
  | ⑤ 3 段 1.2–1.3× 配音实听素材 | `results/app/app184_app051_accel_listen_manifest.json` | `verdict=PASS`、`n_pass=7`、`n_fail=0`、`listen_dir="C:\Users\Trekker-PTL\shared\app_accel_listen"`、`speeds=[1.2, 1.3, 1.3]`、3 段 wav **逐个验字节数落盘** |

- ✅ **④ 的关键补强**：旧 `app165` 跑的是**仓库源码**（不是客户包）⇒ 本轮 `app165_app048_gui_layout.py` 新增 `--pkg`（把 `sys.path` 指向**包内 `app/`**）与 `--out`（**不覆盖**已入库证据），并**用客户包自带 python 3.12.10**（宿主 python 无 tkinter）且**置空 `PYTHONPATH`/`PYTHONHOME`**（防宿主污染）⇒ 证据文件 `results/app/app185_app048_gui_layout_pkg_evidence.json`（4 558 B / mtime 2026-11-01 00:39:03 / SHA256 `b7286c0f8af8e6224cbcad5ab406bae3133699ffa7d4f0191ca6a55072a6b886`）。

- ✅ **⑤ 的实听素材**（**零推理、零 GPU、不占机器锁** —— 从既有落盘产物切出）：

  | 文件 | 源句 | 速度 | 字节数 | SHA256 | mtime |
  |---|---|---|---|---|---|
  | `001_speed_1.2x_spkNone.wav` | `sent_id=1` | **1.2×** | 337 004 | `a6cc216b3dd2836317852eb9ce819ae57692dd3067b3afcc4569f2a991f2f5e5` | 2026-11-01 00:36:53 |
  | `002_speed_1.3x_spkNone.wav` | `sent_id=74` | **1.3×** | 433 484 | `19e0955dbc372bd9b2f8c7db5c5ca265b2c5318e9c344ef854ec467a06f1541c` | 2026-11-01 00:36:53 |
  | `003_speed_1.3x_spkNone.wav` | `sent_id=67` | **1.3×** | 407 564 | `da4fdc8e8083e98d528df98ffc3b00208b702427f9fa5e75b2f467508d0bc457` | 2026-11-01 00:36:53 |

  目录：`C:\Users\Trekker-PTL\shared\app_accel_listen`（3 个文件）。
  🔴 提取脚本 `results/app/app184_app051_accel_listen_extract.py`（10 117 B / mtime 2026-11-01 00:36:50 / SHA256 `11ddadfbc2437d91f18dadb1b1ee49a11b85c9a5e7ad0483d321ec21311f0afc`）—— **第一版切出重复片段**（1.3× 两次都取到 `sent_id=74`）⇒ 修法：`used_ids` 去重 + 新增判据「源句互不相同」「SHA256 去重」⇒ 复跑后 3 段互不相同。

- ✅ **GUI 截图**（APP-048 状态栏两种分辨率）：

  | 文件 | 字节数 | SHA256 | mtime |
  |---|---|---|---|
  | `C:\Users\Trekker-PTL\shared\app_gui_layout\app048_layout_1920x1080.png` | 88 051 | `a8beaaf84b2349ed…` | 2026-11-01 00:39:00 |
  | `C:\Users\Trekker-PTL\shared\app_gui_layout\app048_layout_1280x720.png` | 82 692 | `8e3820c5212a13c4…` | 2026-11-01 00:39:01 |
  | `C:\Users\Trekker-PTL\shared\app_gui_layout\app048_layout_mt_failed.png` | 90 448 | `969cb806992817b1…` | 2026-11-01 00:39:02 |

- 🔴 **判据鉴别力实测（「判据 PASS ≠ 判据正确」）**：
  脚本 `results/app/app186_discrimination_test.py`（7 187 B / mtime 2026-11-01 00:42:52 / SHA256 `01d888e4731a9882f4c63b64e7abd2f818ce65b8d75f69f7d100e083aebcd15e`）
  证据 `results/app/app186_app051_gate_discrimination_evidence.json`（1 765 B / mtime 2026-11-01 00:43:29 / SHA256 `03466e8f3eef119c47392c9ad29fe0c5e6605f9cfa66b1578397579c7f30ddf9`）
  → 原始字段：`verdict="PASS"`、`n_pass=3`、`n_fail=0`、`n_mutations=5`。
  做法：把 6 个证据文件复制到**临时目录** ⇒ 注入 **5 处已知缺陷**（① pythonw verdict→FAIL ② `n_clone_rows`→0 ③ 公式 verdict→FAIL ④ `pkg_under_test`→**仓库源码** ⑤ 实听速度→全 1.0）⇒ 用**同一个判据**（只改 `--ev`）跑。
  实测：**注入 5 处 ⇒ `verdict=FAIL`、恰好 5 条判据 FAIL**（一一对应：pythonw / 克隆音色 / 公式一致性 / 包内代码 / 1.2–1.3× 素材）；对照组（原证据目录）⇒ `verdict=PASS` ⇒ **判据非恒真**。

#### ③ 🔴 **APP-051③ 写 `ACCEPTED.json` + 桌面快捷方式更新到 v1.13 —— 已完成**

- ✅ **`ACCEPTED.json`**（**已同时落在包目录与 zip 内**）：

  | 项 | 实测值 |
  |---|---|
  | 路径 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13\ACCEPTED.json` |
  | 字节数 | **909** |
  | mtime | **2026-11-01 00:43:32** |
  | SHA256 | `fc31e1b575974304d750c308eb7146cba35dabc33264718f456ad7a7318b53f7` |
  | 原始字段 | `accepted=true`、`version="1.13"`、`pkg_dir="C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13"`、`accepted_at="2026-11-01 00:43:32"`（**`datetime.now()` 实测值，非推算**）、`corrections=["APP-043","APP-045","APP-048","APP-051"]`、`scope="链路 + 结构 + 数字自洽；音质/不变调/可懂由用户实听与 reviewer 判定"` |
  | zip 内 | ✅ **存在**（909 B），`accepted=true` / `accepted_at=2026-11-01 00:43:32` / `version=1.13` |

- ✅ **桌面快捷方式已更新到 v1.13（名称带版本号）**：

  | 项 | 实测值 |
  |---|---|
  | 路径 | `C:\Users\Trekker-PTL\Desktop\Confucius4 实时字幕 v1.13.lnk` |
  | 字节数 | **554** |
  | mtime | **2026-11-01 00:39:53** |
  | SHA256 | `770271ac235a8105c4cfb67bd2085b0dce495852fd73674e5c8902ad8b2bdffd` |
  | 目标 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13\Start_LiveCaption.bat`（MS-SHLLINK 纯字节构造：Header `4c000000` / LinkFlags `15004300`） |
  | 旧的无版本号快捷方式 | ✅ **已清理**（桌面仅剩 **1 个** Confucius4 快捷方式 ⇒ 不会误点旧包） |

  🔴 **打包流水线自带这道门**：`shortcut_update.py` 的 `is_accepted()` 读 `ACCEPTED.json` 并要求 `accepted` 为真（**损坏 ⇒ fail-closed 判未通过**）⇒ 本轮打包结束时脚本回执「`✓ 已指向当前版本（幂等，无需重建）`」。

#### ④ 🔴 **撤回 / 更正（旧章节里的过期结论）**

| 旧位置 | 旧结论（现撤回 / 更正） | 本轮更正 |
|---|---|---|
| 头部「阻塞 / 待用户决定」① | 「🔴 **v1.13 zip 已存在但不含本轮代码** ⇒ 客户机上仍然看不到 ⇒ **需用户通知后重打包才闭合**」 | ✅ **已闭合**：v1.13 已按 APP-051 重打（SHA256 `6576dabd…181d5`），zip 内 `app/tts_engine.py` = `eea08775…ee0c4` ⇒ **含**本轮及 APP-052 代码 ⇒ 客户机上**看得到** |
| §116 ④② | 「是否要现在重打包 v1.13？（需要用户明确通知；本轮未打包）」 | ✅ **APP-051 已授权且已重打** ⇒ 此问**已答复并执行** |
| §116 ④⑤ | 「🔴 **未重新打包** ⇒ 客户机上仍看不到 APP-050 那一行日志」 | ✅ **已重打** ⇒ APP-050 的 `EXECUTION_DEVICES` 日志**已在包内**（`tts_engine.py` SHA `eea08775…ee0c4`） |
| 头部「阻塞 / 待用户决定」③ | 「🔴 **桌面快捷方式仍指向 v1.5**（用户当前实测的仍是旧包 ⇒ APP-045 的根因）」 | ✅ **已改为指向 v1.13**（`Confucius4 实时字幕 v1.13.lnk`）⇒ APP-045 ③ **本条闭合** |
| 头部「阻塞 / 待用户决定」② | 「🔴 **APP-043 真机验收未做**」 | ✅ **已做**（5 子项全 PASS / 总闸门 25/0）⇒ `ACCEPTED.json` **已写** |
| 头部「阻塞 / 待用户决定」④ | 「🔴 **APP-048 的「和 v1.13 一起交付」尚未满足**」 | ✅ **已满足**：APP-048 布局代码在 v1.13 包内（`app185` 在包内跑 64/0 PASS）＋ 三张截图落盘 ⇒ **本条闭合** |
| 头部「阻塞 / 待用户决定」⑩ | 「🔴 **v1.12 交付 zip 内 README/NOTICE 自称 v1.6** ⇒ 旧 zip 内容未改 ⇒ 需用户通知后重打包才真正闭合」 | ⚠️ **部分闭合**：**v1.13 新包**已过 §113 闸门（`D3 NOTICE 首行版本号 == 1.13`）⇒ **v1.13 已无此缺陷**；**v1.12 / v1.5 等历史 zip 仍是旧内容**（本轮**未重打历史包**，删除旧包属破坏性操作 ⇒ 需用户确认） |

- 🔴 **本轮**没有**推翻**任何**技术口径**（APP-042 加速公式、APP-050 设备归属口径等仍成立）；本轮只推进了**交付层**（打包 / 验收 / 快捷方式）。

#### ⑤ 🔴 **本条需等 reviewer 复核（3 项）**

1. 🔴 **APP-043 真机验收的「通过」口径是否接受**？
   本轮的总闸门（`app186`）覆盖的是**链路 + 结构 + 数字自洽**（25 条判据全 PASS），
   ⇒ **「音质 / 不变调 / 可懂」不在其中**（`ACCEPTED.json.scope` 已明写）⇒ **需用户实听 + reviewer 判定**。
   ⇒ 请用户实听 `C:\Users\Trekker-PTL\shared\app_accel_listen\` 下的 **3 段**（1.2× / 1.3× / 1.3×）。
2. 🔴 **`app186` 总闸门的 25 条判据口径是否接受**？
   （尤其：④「跑在客户包内代码上」用**目录名精确相等**判，⑤「实听素材真实落盘」用**字节数相等**判。）
3. 🔴 **本轮抓出的 `app186` 写死包版本缺陷（§48 闸门命中）是否接受修法**？
   ⇒ 修法是改用 `pkg_paths.resolve_pkg_dir()` + `--pkg`，**未改任何其它模块**。

#### ⑥ 🔴 **本轮 git 收尾**

- ✅ 逐文件 `git add`（**未用 `-A`**），只提交 App 侧文件；**`status/app/CORRECTIONS_APP.md` 绝不提交**。
- ✅ 未吞 ASR / MT / TTS 其它模块的未提交改动（工作区共 **584** 项未提交改动，其中绝大多数**不属于** App 模块 ⇒ 全部**保持原样**）。
- ✅ 普通 push 到 `origin/main`，**未 force push**（并行会话安全）。
- 🔴 **本轮未跑任何推理 / 测速**（APP-051 未要求；质量判定交 reviewer）；实听素材是**从既有落盘产物切出**，**零推理**。
- 🔴 **本轮唯一一次长时占机作业 = 重打包**（持共享机器锁，压缩 557 s + 逐文件 SHA256 复核）。
