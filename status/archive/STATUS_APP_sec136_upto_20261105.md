### §136 ✅ **APP-068 + APP-069 + APP-070 三条新纠偏的代码侧全部落地 ＋ MiniMVP rc3 已出（设备级 3(a) PASS 9/0）** ｜ **本条已完成（代码 + 部分设备级）｜ 仍需 reviewer 复核**（2026-11-05 11:20）

> 🔴 **本节的每条结论都有落盘证据**（脚本 + json + 文件 SHA256，见每项后面的「证据」）。

#### ① **APP-069① 的根因判定：零段是「落盘算法假象」，不是产品静音**（`app267` 6 PASS / 0 FAIL）

reviewer 实测 rc2 的 `minimvp_v1.0_tts.wav` 有 **24 段全零**（每段 > 0.3 s，合计 54.24 s）⇒ 以为「24 句是静音」。

**本轮判定（字节级复现，不是相关性）**：`--tts-out` 的落盘算法（`tts_worker.py::_flush_timeline`）把每句音频放在
「**本句合成完成**的时刻 − 首句完成时刻」处，长度取**原始**时长 ⇒
① 某句合成比 1× 快 ⇒ 两句之间留**空洞**；② 某句合成比 1× 慢 ⇒ 两句**重叠**，而重叠处是 `out[i:j] += w`（**相加**）⇒ 幅度翻倍（实测 wav peak 触到 **0.99997**）。

| 判据 | 结果 |
|---|---|
| H1 模型预测的全零段 vs 实测 | **24 / 24 精确对应**（预测 54.18 s vs 实测 54.24 s） |
| H2 **反证**：换模型族（首块锚点 / 变速长度）⇒ 复现不出 | **0 / 5 命中**（判据非恒真） |
| H2b 同族变体（末块锚点）必须同样复现 | **24 / 24**（模型有判别力） |
| H3 合成侧逐句 peak/rms 全健康 | **76/76**（min peak 0.375 / min rms 0.0764）⇒ **不是「合成出静音」** |
| H4 每个零段都不被任何单句区间完整包含 | **0 / 24**（是空洞，不是句子被清零） |

⇒ **结论：产品没静音，是 dump 写错。** 证据：`results/app/app267_app069a_rootcause_evidence.json`（96 451 B / SHA `7bdb808c95723c70`）。

#### ② **APP-069①(b)(c)：修 dump ＋ 建内容判据 ＋ 反证精确命中 24 句**（`app268` **4 PASS / 0 FAIL**）

* **代码修复**（`live_caption/tts_worker.py`）：`_flush_timeline` 改成**顺序拼接**（不再按墙钟时间戳摆位）⇒ 无空洞、无重叠相加；
  内容改为**变速后**的音频（真正送进 OutputStream 的那段）；并**回填逐句** `wav_t0`/`wav_t1`/`wav_peak`/`wav_rms_db` 进 jsonl。
  ⇒ 补丁脚本 `live_caption/_app069_patch_tts_worker_dump.py`（**唯一命中断言 + `ast.parse` 校验 + 保留 CRLF**）。
* **内容判据**（reviewer ①(c) 原文 ⇒ 4 条硬判据）：C1 逐句 `rms_db > −45` 且 `peak > 0.05` 比例 == **100 %**；C2 wav 里 **≥ 0.3 s 的全零段数 == 0**；C3 逐句 `wav_t0`/`wav_t1` 齐备且**互不重叠**；C4 按 `wav_t0`/`wav_t1` 切段后幅度达标。
* **反证**：rc2 旧 wav 跑**同一**判据 ⇒ **FAIL**，受损句数 **== 24**（与 reviewer 实测口径逐字一致）。
* **正向组**：rc3 新 wav ⇒ **PASS**（零段 **0** / 76 段区间齐备 / 0 重叠 / 0 坏句）。
* 证据：`results/app/app268_app069_content_criterion_evidence.json`（4 777 B / SHA `a332794fab37c277`）。

#### ③ **APP-069①(d)：v2.2 评估用过的 dump wav 全零段数量**（只报数量，不重做）

| 目录 | 文件数 | 有全零段的文件 | 备注 |
|---|---|---|---|
| `shared/app_listen/v23_clone/wav_clone/` ＋ `wav_presetA/` | 12 | **0** | **逐句** wav ⇒ 本来就没有空洞 |
| `shared/app_listen/v23_clone/`（原音频） | 1 | **0** | |
| `results/app/app250_device_out/`（**ABBA 臂的时间轴混音 wav**） | 3 | **3**（33 / 29 / 32 段，77.8 / 74.5 / 76.2 s） | 与 rc2 **同一个落盘算法** ⇒ 同一个假象 |

⇒ 🔴 **v2.2 交付评估用的 ABBA 臂 wav 也带同样的空洞** ⇒ 若 reviewer 用它回转写，结论会同样受影响。证据同 ① 的 `app267`（H5）。

#### ④ **APP-068：ASR 5 s 旁路窗口的文件清单与前提 —— 全部核对通过**（`app266` **7 PASS / 0 FAIL**）

| 判据 | 结果 |
|---|---|
| H1 ASR 交付的 4 个 py ＋ `pyannote_seg_3_0_w5.bin` 的 md5 | **与 APP-068 逐字一致**（`a1dd6e7b…` / `2ff82933…` / `0482f9c4…` / `7d719e1d…` / `32d5bc9a…`） |
| H2 `w5` xml 的 md5 | 清路径前 `5295ec9c…`（与 APP-068 一致）／清路径后 **`14b224bced3289237799bc9a7eb746ff`**（73 172 B） |
| H3 xml 内绝对路径命中数 | **0** ⇒ 🔴 **ASR 已经清过**（`pyannote_seg_3_0_w5.xml.bak_before_path_scrub_20261105_085534` 是清之前的备份） |
| H4 `export_meta.json` 不进包 | ✅（同步脚本的搬运清单里没有它） |
| H5 `speaker_assets.resolve()` 解析到 **fp16-w5** | ✅（影子包实测：`pyannote_seg_3_0 fp16-w5（窗口 5.000 s，来源 asr_spk_window）`） |
| H6 App 侧绝对路径清理器能把 xml 清到 **0 命中** | ✅（拿**清之前**的 xml 当输入：1 → 0） |
| H7 `asr_spk_window.WIN_S` | **5.0**（`WIN_N = 80000` / `SEG_WIN_S = 5.0`） |

⛔ **设备级那一条（本包 log 出现「说话人旁路窗口：5.000 s」）本轮未跑** ⇒ 属 **v2.3** 线（APP-067 的顺序 1→2→3、4→5→才能打包 v2.3）⇒ **本轮不动 v2.3**。证据：`results/app/app266_app068_pkg_gate_evidence.json`。

#### ⑤ **APP-069⑤：5 项清理 —— 代码侧全落地**（回归 `app215` 29/0、`app227` 34/0、`app229` 反证全 PASS、`app237` 9/0）

| # | 清理项 | 落地方式 |
|---|---|---|
| 1 | `import torch` 清理 | `TorchBackend` / `HybridBackend` / `extract_audio_features` 的 torch 实现 / `npu_embeds_backend` 的 torch 分支 ⇒ 全部搬到**新模块 `live_caption/backends_torch.py`**（**开发专用，不进包**）；`backends.py` 只留**薄壳**（懒加载 + **清楚的错误**「请改用 OpenVINO 后端」） |
| 2 | `auto` 的 label 写死「INT8-CW」 | `translator.py` 新增 `_auto_model_label()` ⇒ **按 `DEFAULT_MODEL` 实际目录动态生成** ⇒ **包内实测显示「自动 · INT4-CW 模型（默认）」**（与实载 INT4 一致） |
| 3 | 窗口标题是内部名称 | 改成**产品名**「实时字幕 MiniMVP v1.0」 |
| 4 | MiniMVP 隐藏说话人行 | ASR 条的「说话人」/「当前」行**不显示**（不再是「降级」）；语音行的「说话人：—（未标注）」**不拼**（只显示音色） |
| 5 | site-packages 清理 ＋ **G4 扫描范围扩大到整个 python 目录** | rc3 构建时**物理删除** `transformers/kernels/**/*.cu|*.cuh`（**15 个**）＋ `safetensors/torch.py`（共 228 041 B）；**G4 改整包扫描**（`.cu/.cuh` **0** 个；`import torch` **app/ 0 处**／site-packages 1 939 处）＋ 生成 **`G4_WHITELIST.md`**（逐项原因） |

#### ⑥ **APP-069③ ＋ APP-070①：TTS 精度口径统一 ＋ TTS IR「删前列清单」**

* **文案统一**（`README_zh/en` ＋ `app/MANIFEST.json` ＋ `NOTICE`）⇒ 一律写
  「**INT8 权重 · FP16 计算（NPU）· 来源 babelvox-openvino-int8**」；**NOTICE 补了 babelvox / djwarf 的来源与再分发说明**（含「不是 FP16 IR」的澄清与质量说明）。
* **「删前列清单」已出**（`app270` **4 PASS / 0 FAIL**）⇒ **一个文件都没删**：
  * 判定依据**不是猜**：**代码级**（解析包内 `babelvox/pipeline.py` 的 `read_model`/`compile_model`）× **分支级**（按 App 的实际配置 `use_kv_cache=False` / `use_cp_kv_cache=True` / `talker_buckets` 非空推演）**两个独立证据交叉验证**。
  * **实际加载** = `talker` / `cp_prefill` / `cp_decode` / `speaker_encoder` / `tokenizer_decoder`（5 个 xml ＋ 5 个 bin）
  * **候选删除** = `talker_prefill` / `talker_decode` / `code_predictor` / `tokenizer_encoder`（8 个文件，**975.9 MB**，xml+bin **成对**）
  * 🔴 **与 reviewer 的「约 567 MB」有出入**（我方口径 975.9 MB）⇒ **待 reviewer 复核**（可能 reviewer 只算了一部分）。
  * 证据：`results/app/app270_tts_ir_inventory_evidence.json`（8 411 B / SHA `f09afd2373580b58`）。

#### ⑦ **APP-069④ ＋ APP-070② A+C：冷启动方案的代码侧已落**（**设备级指标待跑**）

* **不排队**（reviewer 原文：「TTS 编译期间句子一直在排队，编译完成后会从 20 分钟前的句子开始念」）⇒ GUI 与 CLI 两处提交点都在**未 `ready` 时直接跳过**（并诚实计数 `_tts_skip_not_ready` / `_skip_nr`）。
* **就绪后只念新句** ⇒ `tts_service.py` 在 **`loading → ready` 的第一次转换**时**清空待发队列**（运行中的 `ready` 事件**不**清 ⇒ 不影响正常会话）。
* **GUI 显示进度**：状态条在 `loading` 时显示「**首次准备中 xx%**」（tooltip 含组件名、已完成/总数、预计剩余）⇒ 数据源 `tts.stats()['prepare_progress']`。
* ⚠️ 与「不丢句」规则**不冲突**（reviewer 明示：「那条规则针对的是 TTS **已经运行之后**」）。
* ⛔ **设备级指标未跑**：首句可用时间 / 全编完时间（对比 1209 s）/ 峰值内存 / CPU ⇒ **待跑**（每次冷启动 ≈ 20 min ⇒ 10 次 ≈ 3.5 h）。

#### ⑧ **MiniMVP rc3 已出 ＋ 设备级 3(a) PASS（9/0）**

* **rc3 已建**：`Confucius4_LiveCaption_MiniMVP_v1.0-rc3` ⇒ **6 843.8 MB / 10 503 文件**（rc1/rc2 **原样保留不动**）。
  * `models` 6 114.0 MB ／ `python` 728.5 MB ／ `app` 1.3 MB（**24 个模块，导入冒烟 24/24 全 OK**）
* **设备级 3(a) 重跑**（rc3 包，NPU TTS ＋ GPU.0 ASR/MT，`SPE_0000_0500.wav` 前 300 s）：**wall 381.86 s / rc 0 / 76 句全成**
  * **内容判据 4 条全过**：C1 坏句 **0** ／ C2 全零段 **0** ／ C3 区间 **76** 齐备、**0** 重叠 ／ C4 坏句 **0**
  * **反证**：rc2 旧 wav 跑同一判据 ⇒ **FAIL / 受损 24 句**
  * TTS RTF 中位 **1.0162** / P95 **1.3799**
  * **交付物**：`shared/app_listen/minimvp_v1.0/minimvp_v1.0_rc3_tts.wav`（15 252 044 B）＋ `minimvp_v1.0_rc3_transcript.tsv`（76 行 / 9 488 B，**含 `wav_t0`/`wav_t1`/`peak`/`rms_db`/`speed` 列** ⇒ reviewer ①(b) 明文要求）
  * 证据：`results/app/app271_app069_rc3_cli_evidence.json`（4 798 B / SHA `045a4172a9586d53`）

#### ⑨ **APP-069②：启动崩溃 0xC0000409 的统计（进行中）**

* ✅ `--check` 臂 **10/10 次启动，崩溃 0**（每次 ≈ 5.3–5.5 s）
* 🔴 GUI 臂 10 次：**首版 harness 有缺陷**（GUI 常驻 ⇒ 脚本挂死 ⇒ 已终止并修好：改为等「模型加载完成」后用 `WM_CLOSE` **关窗**而不是杀进程）⇒ **正在重跑**。
* 证据：`results/app/app272_crash_out/app272_crash_stats_evidence.json`。

#### 🔴 本轮未完成 / 待 reviewer 裁定

1. ⛔ **APP-069⑥（MT INT4 vs INT8 对比）**：脚本 `results/app/_app273_mt_int4_vs_int8.py` 已写好（76 段 / GPU.0 / 同一 `HunyuanTranslator` ⇒ **同样贪心参数**），**本轮未跑**（需设备）。
2. ⛔ **APP-069⑦ 3(c) zip**：**未打**（rc3 的 ①⑤ 已过，但 ② 未完 ⇒ 且 reviewer 原文「zip 放在目标机本地、不通知用户」⇒ 待 ② 完成后打）。
3. ⛔ **APP-070① 1 的「删 NPU 不加载的 IR」**：**只出了清单，一个文件都没删**（reviewer 明文「删前列清单」＋「删后用 e2e 证明 NPU 路径不受影响」⇒ 顺序是 ① 清单 → ② 删 → ③ e2e）。
4. ⛔ **APP-070② A+C 的设备级指标**：首句可用时间 / 全编完时间 / 峰值内存 / CPU（每次冷启动 ≈ 20 min）。
5. 🔴 **待 reviewer 裁定**：TTS IR 候选删除体积 **975.9 MB** vs reviewer 估「约 567 MB」的出入。
6. 🔴 **回收了一个孤儿机器锁**：ASR 的 `MACHINE_LOCK`（PID 25792）持有者**已死**（`OpenProcess err=87` 确证 ＋ 锁内 `started` 与进程 StartTime 不匹配）⇒ 用项目自带的 fail-closed 脚本 `_app239_reclaim_orphan_lock.py --reclaim` 回收（**不是手写 tasklist**）⇒ 之后本模块才取锁跑设备作业。
7. 🔴 **本轮接管了死租约（第 3 次）**：上一会话的租约 `911516db` 心跳停在 08:33（**82 min 前**）⇒ `TAKEOVER`；其 note 是「app264 热启臂重跑中 PID 48948」⇒ 该 PID **已死**（`live_pids=[] alive=False`）⇒ 本轮**从断点继续**（未重做已完成的 §135）。
8. 🔴 **`CORRECTIONS_APP.md` 收尾复核**：开工基线 **SHA `3c06baa98d3f612a…` / 206 686 B / 70 条**（mtime 09:35:14）⇒ **收尾时须重新取 SHA/字节/mtime/条数**（若中途被追加则如实记录）。
