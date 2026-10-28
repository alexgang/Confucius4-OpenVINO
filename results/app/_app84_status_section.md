## §84 🔴🔴 **APP-027 V3（克隆）实测跑完（CUDA + NPU 两组，各 20 PASS / 0 FAIL）＋ 自查抓出并修掉 2 个真实缺陷（CLI 路径根本没有克隆链路 / 真实播放路径的逐句遥测整组字段丢失）**（2026-10-28 14:56）｜**本条已完成**｜**本条需等 reviewer 复核**

### §84.0 本节结论（一句话）

**APP-027 的 V3（克隆）从「客观做不了」变成「两组都跑完并通过」** ⇒ 但 **CER 对比（MiniMax 回转写）与 CAMPPlus 余弦相似度仍归 reviewer**（本模块**不自己调 MiniMax**，APP-033 第 1 条）⇒ **APP-027 仍未完**（V4 用户实听未做）⇒ ⛔ **zip 不重打**（APP-031 合打）⇒ 按 §66 口径 **不写「已交付」**。

### §84.1 🔴 为什么本轮做 V3（巡检结论 + 依据）

- ✅ **巡检**：`status/app/CORRECTIONS_APP.md` 条目 = **APP-001 … APP-033**（33 条）；本模块 `last_ack` = **APP-033** ⇒ **无新条目** ⇒ 依据自动化记忆「若无新条目 ⇒ 补做遗留的 App 职责内事项」推进 §81.11 列出的遗留项。
- 🔴 **该文件只读、零改动**（SHA256 `bb2896ee9143cd89e4bd2f8a3d0e8f8327079945237ccffc6c6bbd0d825ea043`，90 321 B，mtime 2026-10-28 00:47:55）。
- 📌 **本轮目标 = APP-027 V3**（明文：「**V3 克隆**：用 SPE 前 5 分钟切片（单一男声）实时跑，**开启克隆**，落盘 ≥ 10 句 wav。reviewer 在本机做两件事：(a) MiniMax 回转写，CER 不劣于预设 A 同一批句子；(b) 用 CAMPPlus 算余弦相似度，**相对克隆源的相似度要明显高于预设 A 输出相对克隆源的相似度**（每句差值 > 0，且均值差 ≥ 0.15）。CUDA 和 NPU 各一组。克隆用的源音频和嵌入**不得落盘**」）。

### §84.2 🔴🔴🔴 自查抓出的**真实缺陷①**：CLI 路径**根本没有克隆链路** ⇒ V3 客观做不了

#### 根因（三条，都在 `live_caption_app.py` 的 CLI 侧）

1. **采集器是 GUI 实例方法** ⇒ `run_cli` 构造 `Session(eng, src, on_final=on_final)` ⇒ **没传 `on_audio`** ⇒ `Session._loop` 里的 `self.on_audio(pcm)` **永远不执行** ⇒ **克隆源 PCM 从不离开主进程**；
2. **`run_cli` 构造 `TTSService(...)` 时没传 `clone=True`** ⇒ worker 侧 `--clone` 参数**不加** ⇒ `clone_mode` 恒为 False；
3. **worker 的逐句 jsonl 里没有「这句用的音色来源」字段** ⇒ reviewer 拿到 wav **无法判断某句是不是克隆音色的产物** ⇒ 只能靠「目录名」猜 ⇒ **结论不可核**。

⇒ **V3 在 CLI 下客观做不了**（GUI 需要人操作桌面快捷方式，无法自动化实测）。

#### 修法（3 个文件）

| 文件 | 改动 |
|---|---|
| `live_caption/clone_collector.py`（**新建**） | 采集逻辑抽成独立类 `CloneCollector` ⇒ **GUI 与 CLI 共用同一份实现**（避免逻辑漂移 ⇒ 假证据）；常量 `_CLONE_MIN_S=3.0` / `_CLONE_MAX_S=10.0` / `_CLONE_UPDATE_INTERVAL_S=30.0` / `_CLONE_NEW_VOICED_S=6.0` / `_CLONE_FRAME=320` 与旧 GUI 实现**逐字一致** |
| `live_caption/live_caption_app.py` | ① 常量改为从 `clone_collector` 取别名（**值逐字不变**，向后兼容）；② `App._collect_clone_pcm` 改为**薄封装**（委托共享采集器 + 同步回旧 GUI 字段）；③ 原实现保留为 `_collect_clone_pcm_legacy`（**作等价性反证基线，勿删**）；④ `run_cli` 接上 `Session(..., on_audio=_clone_col.feed)` + `TTSService(..., clone=_want_clone)`；⑤ CLI 收尾新增克隆证据行（`n_updates`/`n_sent_fail`/`clone_active`/`clone_mode`/`clone_dur_s`） |
| `live_caption/tts_worker.py` | `_APP030_JSONL_KEYS` 追加 `clone_active` / `clone_mode` / `clone_audio_s`；两条克隆路线分别记路线（`xvector` = BabelVox / `ref_audio` = CUDA 边车）；`_fallback_to_preset()` 回落时同时清 `clone_mode`（避免字段自相矛盾）；**合成之前**取快照（不是会话结束时） |

### §84.3 🔴🔴🔴 自查抓出的**真实缺陷②**：**真实播放路径**的逐句遥测**整组字段丢失**

#### 现象（首跑实测抓到的）

首跑 V3 CUDA 组：**V3-2 / V3-5 / V3-5b 三条 FAIL** ⇒ 查原始 jsonl（`v3_cuda_run_20261028_143216`）发现 **76 行里 `clone_active` / `clone_mode` / `clone_audio_s` 一个都没有**，连 APP-030⑤ 明文要求的 `lang` / `lang_src` / `end_reason` / `n_chars` / `est_frames` / `frames` / `max_new_tokens` **也全都没有**。

#### 根因

- 真实播放路径下，**逐句 jsonl 行是看门狗线程**（`TTSWorker._finish_played`）用**重算出来的 tel** 写的（重算原因：播放侧的 `read_delta`/`cb_delta`/欠载必须用「播完之后」的值）；
- 而 APP-030⑤ 的 7 个字段与 APP-027 V3 的 3 个字段**只在合成线程的 `synth()` 里填过**（`tel['lang'] = ...` / `tel['clone_active'] = ...`）；
- ⇒ **看门狗重算的 tel 里这些字段全丢** ⇒ **播放路径整组字段缺失**。

⚠️ **这个缺陷不只影响 V3**：它同时让 **APP-030⑤ 的逐句语言/失控遥测在真实播放路径下完全不可用**（reviewer 想按语言分组核对「日文失控」就查不到）⇒ **影响 §78 的日文实测口径** ⇒ 已一并修好。

#### 修法

- 合成线程把**合成那一刻**的这些字段**快照**进 `_played_q` 的 job（`meta={k: tel.get(k) for k in _APP030_JSONL_KEYS}`）；
- 看门狗重算完 tel 后**再覆盖回去**（`for k, v in _meta.items(): if v is not None: tel[k] = v`）；
- ⚠️ **必须在合成时快照**（不能在看门狗执行时读 `self._last_*`）⇒ 否则并发合成下一句会把上一句的值冲掉；
- ⚠️ 只覆盖 APP-030⑤ + clone 这组字段 ⇒ 播放侧遥测（`consumed`/`read_delta`/`cb_delta`/欠载）**保持看门狗重算的值**（那才是播完后的权威口径）。

### §84.4 ✅ 验收（`results/app/app121_app027_v3_clone_cli.py`）：**28 PASS / 0 FAIL**（零推理、零 GPU、零 NPU、不调 MiniMax）

| 组 | 判据 | 结果 |
|---|---|---|
| **A 等价性** | A1 新采集器与旧实现「触发时机」完全一致｜A2 确实发出更新｜A3 发的是去静音后的语音｜A4 `enabled=False` 零副作用｜A5 语音时长落在 APP-027 明文的 [3, 10] s｜A6 旧新实现发出的语音时长**逐次一致**｜A7 旧新「已发送累计秒数」一致 | **7/7 PASS** |
| **B CLI 接线** | B1 `Session(...)` 带 `on_audio=` 且**不是常量 None**｜B2 `TTSService(...)` 带 `clone=`｜B3 构造了 `CloneCollector`｜B4 `on_audio` 传的是采集器的 `feed` | **4/4 PASS** |
| **C worker 遥测** | C1×3 三个新键｜C2 失败/丢句行（tel 为空）也带音色来源｜C3 有「合成那一刻」的快照｜C4 回落时清路线｜**C5 播放路径把字段快照进 job**｜**C6 看门狗把 meta 覆盖回 tel** | **8/8 PASS** |
| **D 反证** | D1 去掉 `on_audio=` ⇒ B1 **FAIL**｜D2 去掉 `clone=` ⇒ B2 **FAIL**｜D3 去掉 worker 新键 ⇒ C1 **FAIL**｜**D4 去掉 meta 快照 ⇒ C5 FAIL** | **4/4 PASS** |
| **E 基线** | E1 修复前（`a2bb97a`）的 `run_cli` 没有 `on_audio` ⇒ 缺陷曾真实存在｜E2 修复前不存在 `clone_collector.py` | **2/2 PASS** |
| **F 包同步** | 客户包内 `live_caption_app.py` / `tts_worker.py` / `clone_collector.py` 与仓库**逐字一致**（LF 归一化） | **3/3 PASS** |

> ⚠️ **反证用固定 commit `a2bb97a`**（§83 的 commit = 本轮修复前的最后一个入库点）⇒ 不用 HEAD（HEAD 修好后反证会落空 ⇒ 假证据，§31 教训）。
> ⚠️ **闸门自检**：B1 判据在第一次写时**太弱**（`on_audio=None` 也算通过）⇒ 被反证 D1 抓出来 ⇒ 已改成「值不能是常量 None」⇒ D1 才 PASS。**这正是反证存在的意义。**

### §84.5 ✅ APP-027 V3 实测（`results/app/app123_app027_v3_clone_real.py`）：**CUDA 组 20 PASS / 0 FAIL ＋ NPU 组 20 PASS / 0 FAIL**

#### 口径（与 APP-027 V3 明文逐条对齐）

| APP-027 V3 明文 | 本轮落实 |
|---|---|
| 用 SPE 前 5 分钟切片（单一男声）实时跑 | `--file C:\Users\Trekker-PTL\shared\SPE_0000_0500.wav --speed 1.0 --max-seconds 300` |
| **开启克隆** | `--tts-voice follow_speaker`（CLI 与 GUI 共用 `clone_collector`） |
| 落盘 **≥ 10 句 wav** | `--tts-dump-dir` ⇒ **CUDA 76 句 / NPU 76 句** |
| **CUDA 和 NPU 各一组** | ✅ 两组都跑（持机器锁 + 45 s 安静窗口） |
| 克隆源音频和嵌入**不得落盘** | 判据 `V3-6` / `V3-6b` **PASS**（见 §84.5.3） |
| reviewer 做 MiniMax 回转写 + CAMPPlus | ⛔ **本模块不做** ⇒ 判据 `V3-CER` / `V3-CAMP` 标 **`[NO-EVIDENCE]`** |

#### §84.5.1 两组的关键原始字段（全部取自 `v3_*_report.json`）

| 字段 | **CUDA 组** | **NPU 组** |
|---|---|---|
| 判据 | **PASS=20 / FAIL=0** | **PASS=20 / FAIL=0** |
| 设备 | TTS=`CUDA`（RTX 5050）｜ASR=`GPU.0`｜MT=`GPU.0` | TTS=`NPU`（f16）｜ASR=`GPU.0`｜MT=`GPU.0` |
| 实测跨度 `wall_s` | **309.0**（`wall_source=jsonl-span`） | **312.2**（`wall_source=jsonl-span`） |
| 退出码 | **0** | **0** |
| 克隆更新次数 `clone_updates` | **18** | **18** |
| 采集语音 `clone_voiced_s` | **107.22 s** | **107.22 s** |
| 已发语音 `clone_sent_voiced_s` | **105.38 s** | **105.38 s** |
| `clone_active` | **True** | **True** |
| `clone_mode` | **`ref_audio`**（CUDA 边车路线） | **`xvector`**（BabelVox 路线） |
| `clone_dur_s` | **10.0** | **10.0** |
| 逐句 jsonl 行数 | **76** | **76** |
| 其中 `clone_active=True` | **76** | **70** |
| 落盘 wav | **76**（克隆 **76** / 预设 **0**） | **76**（克隆 **70** / 预设 **6**） |
| `n_submitted` / `n_played` / `n_dropped` | **76 / 76 / 0** | **76 / 76 / 0** |
| `n_drop_written` / `n_no_audio` / 逐句 error | **0 / 0 / 0** | **0 / 0 / 0** |
| `n_consumed` / `n_not_consumed` | **76 / 0** | **76 / 0** |
| 守恒（jsonl 独立核算） | **76 == 76+0+0** ✅ | **76 == 76+0+0** ✅ |
| `synth_rtf` P50 / P95 | **0.5862 / 0.7009** | **0.9935 / 1.1644** |
| 句内欠载 P95 | 37（只记录） | 20（只记录） |
| 字段矛盾（`clone_active=True` 但 mode 空 / 反之） | **0 / 0** | **0 / 0** |

#### §84.5.2 为什么 **CUDA 组 76/76 全是克隆组、NPU 组只有 70 句是克隆组**

- CUDA 组：日志第 43 行「✅ 克隆音色已更新（CUDA 边车 ref_audio，**3.0 s**）」**早于**第 53 行「首包分段 id=0」⇒ 采集器在 ASR 首句定稿期间就攒够了 3 s 语音 ⇒ **id=0 起就是克隆音色** ⇒ 76/76 是**事实**，不是 bug；
- NPU 组：x-vector 路线要跑 `extract_speaker_embedding`（比 `set_ref` 重）⇒ **前 6 句（id 0–5）用的还是预设 A**，第 6 句后才切到克隆 ⇒ **70 克隆 + 6 预设** ⇒ **恰好同时具备「同批句子的两组」** ⇒ reviewer 做 CER/CAMPPlus 对比**需要的就是这个**。

#### §84.5.3 隐私明文（V3：克隆源音频和嵌入**不得落盘**）—— 两条判据都 PASS

- `V3-6` 扫 `run/`、`dump/`、**客户包**（含 `voices/`、`tts_speakers/`、`clone_*.npz`）⇒ **`clone_leaks = []`**；
- `V3-6b` 扫 `%TEMP%\confucius4_clone\`（worker 落临时参考 wav 的目录）⇒ **`tmp_clone_residue = []`**（会话结束即删，**实测零残留**）；
- ⇒ **落盘的只有 TTS 输出的 wav**（CUDA 76 个 / NPU 76 个）。

#### §84.5.4 给 reviewer 的清单（**防错位**，APP-027 V1 同款要求）

`v3_{cuda,npu}_wav_manifest.json`：**每句一行**，含 `id` / `text` / `wavs[]`（绝对路径）/ `wav_bytes[]` / `wav_sha256[]` / **`clone_active`** / **`clone_mode`** / **`clone_audio_s`** / `n_samples` / `dur_s` / `synth_rtf` / `consumed` / `dropped` ⇒ **wav ↔ 文本 ↔ 音色来源 一一对应** ⇒ reviewer 可直接按 `clone_active` 分组做 MiniMax 回转写与 CAMPPlus 对比。

#### §84.5.5 ⚠️ 边界（诚实声明）

- ⛔ **本轮是 CLI 回放 + 真实播放路径（走声卡）**，**不是 GUI**、**不是用户启动方式**（§63 L4：桌面快捷方式 → `.venv\Scripts\pythonw.exe`）⇒ ⛔ **「用户听得到」仍不成立**（机器判据已足：`consumed=True` 76/76 + `read_delta ≥ n_samples` + 无 `consumed=False`，**但人耳未确认**）。
- ⛔ **V4（用户实听）未做** ⇒ **APP-027 未完**。
- ⛔ **CER 与 CAMPPlus 未做**（本模块**不自己调 MiniMax**，APP-033 第 1 条）⇒ 判据标 `[NO-EVIDENCE]`。
- ✅ **不在 CPU 上跑推理**：TTS 走 **CUDA 边车**（torch `2.11.0+cu128` / CUDA 12.8 / RTX 5050 Laptop GPU）或 **NPU**；ASR/MT 走 **GPU.0**（集显）。
- ✅ **机器锁纪律**：两组**各自持锁**（`shared/MACHINE_LOCK`，内容含模块名/PID/开始时间）⇒ 先取锁、再等 **45 s 安静窗口**（`wait_quiet_window_cpu`，`n_busy_samples=0`）⇒ 结束**删锁**；等锁期间**0 次文件写入**（`machine_lock_app.acquire` 的「先探测后创建」实现）。
- ✅ **0 次删除**：用**带时间戳的 `v3_<group>_run_<YYYYmmdd_HHMMSS>/` 子目录** ⇒ 旧产物原样保留（§81.5 缺陷①的教训）。
- ✅ **未修改 `CORRECTIONS_APP.md`**（只读、零改动）、**未向 MiniMax**、**未开 FTP**、**未跑 `verify_pkg_zip.py`**。

### §84.6 ✅ 客户包定点同步（`results/app/app122_sync_pkg_clone.py`）

- 🔴 **双副本**（仓库 `live_caption/` 与客户包 `Confucius4_LiveCaption_v1.6/app/`）⇒ **禁止整目录覆盖**；
- 同步方式：**基线 = 包内当前内容**（不是 HEAD —— 包内已比 HEAD 新 ⇒ 强行以 HEAD 为基线会把包内已有内容**删掉**）⇒ `difflib.get_grouped_opcodes(n=3)` 派生**增量替换块** ⇒ **唯一命中断言**（命中数 ≠ 1 ⇒ 立即中止）；
- **备份**（包外）：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.6\_backup_app_20261028_preclone\`（`live_caption_app.py` 237 534 B / `tts_worker.py` 171 297 B）；
- 同步结果：`live_caption_app.py` **0 块**（首轮已是最新）｜`tts_worker.py` **9 块**（首轮）→ **2 块**（缺陷②的增量）｜`clone_collector.py` **新增**（原本不存在）⇒ **独立复核：包内逐字 == 仓库**（LF 归一化）⇒ 判据 `F.*` **3/3 PASS**；
- ⚠️ 换行风格：仓库 `live_caption_app.py` 是 **CRLF**，客户包那份是 **LF** ⇒ 同步时**统一按 LF 写入包**（与包内既有风格一致）。

### §84.7 ✅ 本轮改动文件清单（App 侧）

| 文件 | 类型 | 说明 |
|---|---|---|
| `live_caption/clone_collector.py` | **新建** | 克隆源语音采集器（GUI 与 CLI 共用） |
| `live_caption/live_caption_app.py` | 改 | CLI 接上克隆链路；常量改别名；`_collect_clone_pcm` 改薄封装；旧实现保留为 `_collect_clone_pcm_legacy` |
| `live_caption/tts_worker.py` | 改 | 逐句音色来源遥测 3 键 + 两条路线标记 + 回落清路线 + **播放路径 meta 快照（缺陷②的修法）** |
| `results/app/app121_app027_v3_clone_cli.py` | 新建 | 前置修复验收（28 判据，含 4 条反证） |
| `results/app/app121_app027_v3_clone_cli_evidence.json` | 新建 | 验收证据 |
| `results/app/app122_sync_pkg_clone.py` | 新建 | 客户包定点同步（增量替换块 + 唯一命中断言） |
| `results/app/app122_pkg_sync_evidence.json` | 新建 | 同步证据 |
| `results/app/app123_app027_v3_clone_real.py` | 新建 | **APP-027 V3 实测驱动**（CUDA + NPU 两组；持锁 + 安静窗口；`--reanalyze` 支持离线重算） |
| `status/app/STATUS_APP.md` | 追加 | 本节 §84（**只追加，未改旧章节**） |

### §84.8 ⛔ 待 reviewer 裁定 / 待用户确认

1. 🔴 **V3 的 CER 对比** —— reviewer 在本机做 MiniMax 回转写：**CER 不劣于预设 A 同一批句子**。可用材料：CUDA 组 76 句（克隆 76 / 预设 0）、NPU 组 76 句（克隆 70 / 预设 6）⇒ `v3_{cuda,npu}_wav_manifest.json`（含逐句文本与 wav 的 SHA256）。
2. 🔴 **V3 的 CAMPPlus 对比** —— **每句差值 > 0 且均值差 ≥ 0.15**（克隆组相对克隆源的相似度 > 预设组相对克隆源的相似度）。⚠️ **NPU 组有 6 句预设 A**，是**同语料 A/B** 的天然对照组 ⇒ **建议优先用 NPU 组做这个对比**（CUDA 组无预设组可比）。
3. 🔴 **NPU 组「前 6 句还是预设 A」是否算缺陷** —— 事实是 x-vector 提取比 `set_ref` 重 ⇒ 生效较晚。**若 reviewer 认为「克隆必须从第 1 句就生效」⇒ 需要预热机制**（例如会话开始时先采集并完成一次 x-vector 提取，再放开合成）⇒ **本轮未自行推进**。
4. 🔴 **CUDA 组 76/76 全克隆 ⇒ 没有「预设 A 对照」** —— 是否需要**再跑一组「预设 A（`--tts-voice A`）」**作同批对照？本轮**未自行推进**（APP-027 V3 明文只要求「开启克隆」，对照组的必要性由 reviewer 定）。
5. ⛔ **V4 用户实听** —— 通知用户按 **CUDA / NPU / 克隆**各听一段，**只有用户本人确认才算 L4 关闭**。
6. ⛔ **zip 未重打** —— APP-027 的 V1 ✅ / V2 ✅ / V3 ✅（机器判据）但 **V4 未做**、**CER/CAMPPlus 未做** ⇒ 按 APP-031「三项做完后合在一起重打一次包」⇒ **本轮不重打** ⇒ **不写「已交付」**（准确表述：**代码侧已入库、已同步到包目录；zip 未重打**）。
7. ⛔ **§83.5 的 4 项待裁定仍然有效**（RTF 归因边界 / 「首包」指标定义 / `app062` A/B 是否重做 / 不变式是否改三段式）—— 本轮**未自行推进**。
8. 🔴 **新发现的待裁定项（§84.3 缺陷②的连带影响）** —— 缺陷②让 **APP-030⑤ 的逐句语言/失控遥测在真实播放路径下原本完全不可用** ⇒ §78 的日文实测（29 句 ×3 次）当时是**用落盘模式**跑的（`--tts-out`）⇒ 落盘模式走的是**合成线程**的 tel ⇒ **§78 的结论不受影响**；但 **V1/V2 的实测（真实播放路径）里 `lang`/`end_reason` 字段是缺失的** ⇒ 那两轮报告若要补「按语言分组」的字段，**需要用本轮修好的代码重跑**（本轮**未重跑 V1/V2**）。

### §84.9 头部字段

- `last_ack` = **APP-033**（**保持不变**：本轮**无新 reviewer 纠偏条目** ⇒ 无编号可 ack；APP-027 是**已 ack 的历史条目**，本节只是补做它的 V3 验收段）。
- 「更新时间」= **2026-10-28 14:56**（`Get-Date -Format "yyyy-MM-dd HH:mm"` **实测值**，非推算）。
