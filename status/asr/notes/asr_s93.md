# ASR §93 明细（2026-11-23 13:39–14:05）

> 本轮 = **纯巡检 ＋ 只读影响面分析**（新邮件是 App/TTS 模块纠偏，但含 ASR 域条款）。
> 🔴 未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 `live_caption/`、未改纠偏文件、未改旧章节。

## 一、纠偏通道 ＋ 邮箱（本轮只读）

| 通道 | 结果 |
|---|---|
| `CORRECTIONS_ASR.md` | **105 868 B** / md5 **`b6fd2e14d04d20268af28b2340dd49a`** / mtime **2026-11-20 15:33** ⇒ 与前 20+ 轮**逐字节相同**；最大编号 **ASR-066**、**无 ASR-067+** ⇒ `last_ack` **保持 ASR-066** |
| QQ 收件箱 | **有 4 封新邮件**（§92 之后 ⇒ 11-23 12:40～13:39 之间到达）⇒ **全部非 ASR 编号**：**APP-125**（12:56）、**APP-124**（12:55）、**APP-122**（12:40）、**APP-123**（12:39）＋ 重复的 APP-122 背景副本（12:39）⇒ **无 `ASR-` 编号邮件** ⇒ `last_ack` 不变 |
| 其余邮件 | TTS-077（10:34）、TTS-076（10:15）、APP-121（09:03，§89 已回复）⇒ 非本模块 |
| 垃圾箱 | 空 |

🔴 **口径**：`last_ack` 只跟 **ASR-xxx 编号**走。App 模块的 `APP-xxx` 编号**不进入**本模块 `last_ack`（各模块只写自己的 STATUS）。

## 二、4 封新邮件的归属判定

| 邮件 | 编号 | 主题要点 | 是否 ASR 域 |
|---|---|---|---|
| `msg_lYpv89vQ6bv5x6UTds1ETz5h_YEubqNHEBeInh2WYzheqA` | **APP-125** | 再次改分工：「保留背景音」**全部代码**（`extension/` 与 `ext/*.py`、分离 worker、**说话人改用人声**）由 **reviewer 来写**；App 线程**不要开发 APP-122/APP-124 的任何代码**，只等交接后打包与实测 | ❌ App 模块 |
| `msg_lDq3obO0lD3eyEyatNV9Nd-4635wKLh8Hw08EFt2CNlEPQ` | **APP-124** | 改 APP-122 分工：Chrome 插件端（`extension/`）reviewer 改；App 线程只做桥接服务（`ext/*.py`）、分离进程、**说话人链路改用人声**、打包 v2.6、实测。附 JSON+base64 接口约定 | 🟡 **含 ASR 域条款**（说话人链路） |
| `msg_djWcINRxPgegPoiRuYE8iZ4btopNbjLfEqZJC-OQUqHSMg` | **APP-122** | 新功能 EXT「保留背景音」（默认打开）：Demucs 分离背景，与配音混合后按延迟同步播放；先进 v2.6 全集，不进 MiniMVP | 🟡 **含 ASR 域条款**（说话人链路 + ASR 断句/识别口径） |
| `msg_gW7oBPmECHAasy3D7Oep8pVIvqNHgzZ2HhxxkEEAXYM88Q` | **APP-123** | 接入 TTS-075「小窗口流式声码器 c13」到 v2.6 | ❌ App 模块（TTS 路径） |

## 三、🔴 本轮实质产出：APP-122/124 的 ASR 域条款 ⇒ **3 条 ASR 契约风险**（只读分析）

APP-122 §要做的 2 有一条**直接改动 ASR 拥有的说话人链路**：

> 「**用户 11-23 定：开关打开时，说话人分段（pyannote）、声纹（WeSpeaker 跟踪/音色守卫）、克隆（Qwen3-TTS speaker encoder 取 x-vector）三条全部改用分离出的人声**，不是可选项。分离人声重采样到各模型要求的采样率（16 kHz）。」
> 「**ASR 断句与识别仍用原声 16 kHz 上行（用户 11-23 确认）**」

⇒ 这条**不要求 ASR 改代码**（ASR 断句/识别明确留在原声），但它**改变 ASR 交付的说话人旁路的输入音频**，而 ASR 交付集合里有一套**按原声标定**的参数 ⇒ 3 条风险（下列每条都给出**代码行号**与**原始字段**）。

### 风险 ①（🔴 高）说话人旁路的时间轴契约：分离人声**晚于**原声到达 ⇒ 段边界与 `clean_ranges` 整体错位

**事实**（ASR 侧交付集合，唯一事实来源 = `qwen3asr_06b/scripts/`）：

| 项 | 值 | 出处 |
|---|---|---|
| 交付集合 = **4 个文件** | `asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py` / `asr_spk_window.py` | `asr052_speaker_tracker_api.py` L19–23（ASR-033/045 明文） |
| 窗口长**唯一事实来源** | `asr_spk_window.WIN_S`，`WIN_S_DEFAULT = 5.0` ⇒ `WIN_N = 80000`（SR=16000） | `asr_spk_window.py` L86 / L113 / `SR = 16000` L68 |
| 帧覆盖滞后（算法层） | `settle = WIN_S − stride_ms/1000` = **5.0 − 1.28 = 3.72 s** | `asr_speaker_tracker.py` L299（交付 API 同式，L「settle」） |
| `feed()` 的 `t` 参数 | **只用于对齐缓冲起点**（`self._t0 = max(0.0, t − len/sr)`）⇒ **不用于切段** | `asr052_speaker_tracker_api.py` L363–395（`feed`） |
| 段判定用的帧索引 | `i0 = round(t_start × FPS)`、`i1 = round(t_end × FPS)` ⇒ **直接用 ASR 定稿段的全局时间轴** | `asr052_speaker_tracker_api.py` L398+（`on_final`） |
| 音频切片 | `_audio_slice(a, b)` 按**全局样本下标**取 ⇒ 与 `feed()` 的累计样本数**严格同轴** | `asr_speaker_tracker.py` L364–377 |

🔴 **⇒ 结论（契约级）**：`SpeakerTracker` 的「帧覆盖」与「段判定」**共用 ASR 定稿段的全局时间轴**。若把**分离人声**喂进旁路，则分离 worker 的输出**滞后原声约 8–9 s**（APP-122 自述「等分离会多出约 8–9 s 延迟」）⇒ ⇒ **喂进去的分离人声的「全局时刻」与 ASR 定稿段的「全局时刻」不是同一个时间原点** ⇒ 帧覆盖检查（`i0/i1` 落在已覆盖帧内）会**系统性偏移** ⇒ 轻则 `clean_ratio` 算错、重则整段 `not_clean_speech` 被跳过。

🟡 **处置建议（本模块职责范围内、只给建议不改代码）**：分离人声喂旁路时，**必须带自己的时间戳**并按「原声时刻 = 分离时刻 − 分离延迟」换算，或**让旁路维护独立时间轴**并把 ASR 定稿段的时间戳映射过去 ⇒ **不能**沿用「喂进来的块自带 t」这一现口径（现口径下 `t` 只对齐缓冲起点）。

### 风险 ②（🟡 中）三个阈值的标定前提全部是「原声」⇒ 换分离人声后**未标定**

| 参数 | 默认值 | 标定来源（原声口径） | 出处 |
|---|---|---|---|
| `thr`（聚类余弦阈值） | **0.35** | ASR-021 §③：TTS INT8 encoder margin 0.0158（bias 0.982）**任何阈值都不可分** ⇒ 改用 wespeaker；wespeaker `W2_per_spk_raw` margin **0.3453**（bias 0.429）⇒ 取 0.35 | `asr021_speaker_acceptance.json` → `encoder_decision.wespeaker_evidence` / `tts_encoder_evidence`；`asr052_speaker_tracker_api.py` L305 |
| `min_clean_ratio` | **0.6** | ASR-050 **用户决定** 0.8 → 0.6（口径 = 旁路分段模型在**原声**上的 `p_speech ≥ 0.5` 帧占比） | `asr052_speaker_tracker_api.py` L146 `DEFAULT_MIN_CLEAN_RATIO = 0.6`；`asr_speaker_tracker.py` L324–329 |
| `overlap_ratio_max` | **0.02** | ASR-048/asr121 实测 ⇒ **惰性参数**（几乎不触发） | `asr052_speaker_tracker_api.py` L299/L309 |
| `min_dur_s` | **2.0** | 交付 API L310（`asr_speaker_tracker.py` 内部旧版是 1.5） | `asr052_speaker_tracker_api.py` L310 |

🔴 **⇒ 结论**：分离人声是**另一种音频域**（去背景 ⇒ 底噪更低、`p_speech` 帧分布改变、重叠判定失效）⇒ 上述 3 个阈值**在新输入上未标定** ⇒ 🔴 **不能**直接沿用「原声标定的 0.35/0.6/0.02」到分离人声链路 ⇒ **必须重标定**（这是 ASR 侧职责，但需 App 提供分离人声素材）。

🟡 **特别提示**：`overlap_ratio_max = 0.02` 判的是「**多人重叠说话**」⇒ 分离人声**已去掉背景但保留多人重叠人声** ⇒ 该参数**语义仍成立**；真正需要重标的是 **`thr` 与 `min_clean_ratio`**。

### 风险 ③（🟡 中）旁路积压上限 60 s ⇒ 分离延迟 8–9 s 会**吃掉大部分预算**，且超限即**整段会话不再打标签**

| 项 | 值 | 出处 |
|---|---|---|
| 队列积压上限 | `max_queue_s = 60.0`（秒） | `live_caption/speaker_tracker.py` L445 |
| 超限行为 | 丢弃**最旧**的窗口 ＋ 标记 `n_dropped_chunks/n_dropped_samples` ＋ **`_degrade('backlog_over_limit')`** | `speaker_tracker.py` L647/L675–L695 |
| 降级后果 | `_degraded = True` ⇒ 此后 `on_final()` 对**所有**后续段返回 `reason='bypass_degraded'` ⇒ **整段会话不再打说话人标签** | `speaker_tracker.py` L837/L919–921 |

🔴 **⇒ 结论**：分离人声引入 8–9 s 常态延迟后，旁路积压从「≈0」变成「**常态 8–9 s**」⇒ 占 60 s 预算的 **13–15 %** ⇒ 单这一项不致命；但 🔴 **APP-122 的降级路径是「整段会话失效」而非「跳过几段」** ⇒ 一旦积压超限（分离 worker 掉线/超时，APP-122 自己也写了「分离 worker 掉线/超时时整体退回原声」）⇒ **标签整段会话消失** ⇒ **必须**确认分离失败时旁路**退回喂原声**（或至少**不置 `_degraded`**）。

## 四、APP-122 要求的「ASR 输入原声 vs 分离人声 WER 对比」⇒ **本轮可做，但还没做**（材料与工具已核实）

APP-122 §要做的 2 末尾：「另做一组离线对比：同一 10 分钟片段，ASR 输入原声 vs 分离人声的 WER（MiniMax asr-1.0 参照），只报告，不改默认。」

🔴 **口径纪律**：本模块**不自己调 MiniMax**（质量由 reviewer 判定）⇒ WER **参照**用 reviewer 已有的 baseline，**不新建** baseline。

**材料与工具（本轮只读核实，均已在位）**：

| 项 | 结果 | 出处 |
|---|---|---|
| 10 分钟固定片段 | `qwen3asr_06b/dev/asr044_evalset/clip_10min_0_600.wav` = **16 kHz / 单声道 / PCM16 / 600.0 s / 9 600 000 帧** | `dev/asr044_evalset/clip_10min_0_600.meta.json`（`asr137_make_10min_clip.py`） |
| reviewer 参照（同一计分器） | `confucius4-openvino/reports/c026_minimax_segjson_10min`（**1 780 词 / 0–600 s / 1 778 段**；`_index.json` 明写「参考集与 hyp 同段 ⇒ WER 绝对值有意义；**不可与 61 分钟口径的数字混比**」） | `reports/c026_minimax_segjson_10min/_index.json` |
| WER 计分器 | `reviewer/compare_wer.py`（`norm` 唯一事实来源）＋ `reviewer/paired_bootstrap.py`（SPE 参照） | `qwen3asr_06b/scripts/asr160_score_wer.py` L33–37（`REPO = confucius4-openvino`） |
| 段配对 WER（更严口径） | `scripts/asr146_wer_seg_paired.py`（`scorer='reviewer_minimax_global'`、`N_BOOT=5000`、按段配对 bootstrap） | 同上 L259–260、L61 |
| 本模块已有的现成脚本 | `asr160_score_wer.py`（离线/流式各报 WER/CER）、`asr134_wer_score.py`、`asr146_wer_seg_paired.py`、`scripts/_asr062/asr162_score_wer.py` | `scripts/` 目录 |
| 分离器（reviewer 写的参考实现） | `C:\Users\Trekker-PTL\shared\bgkeep\`：`htdemucs_core.xml/.bin`（**106 628 066 B** / 1 341 298 B）、`ov_demucs.py`、`sep.py`、`dub.py`、`mix.py`、`ov_mem.py` | `shared/bgkeep/` 目录实测 |

🟡 **为什么本轮没跑**：**①** 分离人声素材**尚未生成**（`shared/bgkeep/` 只有 IR 与脚本，`sep.py` 的输入是 `C:\bgsep` 的 mp4，**A 机没有**）⇒ 需先产出 10 分钟片段的**分离人声 16 kHz wav**；**②** 这是**质量/数值作业**（不是计时）⇒ 不需要 MACHINE_LOCK，但需 App 线程或 reviewer 先给分离人声素材；**③** 🔴 **口径**：要对比的是「**ASR 输入**原声 vs 分离人声」⇒ **两侧必须用同一 ASR 臂**（§86 的 `pml=320` NPU 档 + OV **2026.4.1**）⇒ 否则数字不可比。

🔴 **本轮处置**：**不自行开实验**（ASR-038「没有用户指派的 ASR 任务时待命」）⇒ 记为**待 App/reviewer 提供分离人声素材后本模块可做**的 1 项。

## 五、本轮动作边界

- 🔴 未跑推理/计时（**未跑 ASR、未跑 WER、未跑分离器**）
- 🔴 未取 `MACHINE_LOCK`
- 🔴 未改交付文件（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py` / `asr_spk_window.py` 一行未动；`live_caption/` 一行未动）
- 🔴 未打包（用户级记忆：不通知不主动打包）
- 🔴 未改纠偏文件（`CORRECTIONS_ASR.md` md5 未变）
- 🔴 未改旧章节（§92 已逐字归档到 `status/archive/STATUS_ASR_sec92_upto_20261123.md`）
- 🔴 未代做 App 线程作业（APP-122/123/124/125 全部是 App 模块的）
- 🟡 唯一实质动作 = **只读影响面分析**（把 App 邮件里的 ASR 域条款翻译成 ASR 侧契约风险）＋ 写 STATUS §93 ＋ 本 note

**产物**：`status/asr/notes/asr_s93.md` ＋ `status/asr/STATUS_ASR.md` §93
