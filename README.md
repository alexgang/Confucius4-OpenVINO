# Confucius4-R2T2 流式 ASR → Intel OpenVINO（Panther Lake Xe3 集显）

把官方 `netease-youdao/Confucius4-R2T2`（Qwen3-ASR-1.7B 流式微调，架构 `Qwen3ASRForConditionalGeneration`）
用 **OpenVINO 2026.4** 在 **Intel Core Ultra 7 356H（Panther Lake）Xe3 集显** 上跑通，
**INT8 权重压缩 + with-past stateful** 实现短音频 RTF ≈ 0.45（640 ms chunk），
**VAD 切句分段** 让任意长度音频 RTF 稳定 < 0.8。

## 验收结果（C-013 + C-014/C-016/C-018 最终方案）

| 指标 | 值 | 备注 |
|--|--|--|
| 设备 | Intel Xe3 iGPU (Panther Lake) | `GPU.0`，`FULL_DEVICE_NAME` 启动断言 Intel |
| 精度 | **INT8**（NNCF 权重量化）| 2.0 GB；57 ReadValue/Assign，stateful |
| chunk | **640 ms** | `unfixed_chunk_num=0, unfixed_token_num=5, adaptive_budget=True` |
| **RTF (6.74s 测试音频)** | **0.444** | 11 chunks, wall=2.99s |
| **RTF (28.5s 长音频)** | **0.730** | 45 chunks, wall=20.76s |
| **RTF (61.19 min 英文)** | **0.639** | 226 段 (VAD 切), wall=2348s |
| **WER (61.19 min, MiniMax 参考)** | **7.88%** | C-047 自适应生成长度（原 17.87%） |
| decode ms/token | **33 ms** | vs FP16 64 ms（1.9× speedup）|
| 与 torch golden 文本对比（去标点 CER）| **0%** | 内容字完全一致；INT8 自然输出 `。` |
| 末段文本（短音频）| `之前有顾客自己带酒水也没加收钱或者不让喝。` | 与 CUDA baseline（Q8_0）一致 |

> 详细报告见 `status/STATUS.md`，原始日志在 `reports/`。
> **最终报告：`reports/PROJECT_REPORT.md`**（精度基线为 MiniMax 云端 asr-1.0，非 CUDA）
> WER 与根因分析见 `reports/C047_CUDA_PARITY.md`（C-047）。

## 三个根因与修复顺序（详见 `reports/PROJECT_REPORT.md` §3）

| # | 根因 | 怎么发现的 | 修复 | 61-min WER |
|---|---|---|---|---|
| ① | optimum-intel 导出的 audio encoder **丢失了原模型的全局注意力**（参考实现的 `_prepare_attention_mask` 定义了但从未被调用） | torch 逐层对比：4 s 时逐 token cosine 只有 0.64，60 s 0.29 | 用 reviewer 的整段 encoder（`ov-encoder-segment-reviewer`，固定 `[1,128,2400]` + `n_valid`，全局注意力） | 23.5% → 17.9%<br>（与 ② 合计） |
| ② | 窗口编码器把**不满窗当成满窗**：`n_full_windows` 按块数向上取整而非按帧数向下取整，补的零帧被当有效音频编码且被永久缓存 | 逐 chunk 增长日志里 N_audio 与公式值不符（7.68 s：应是 100，实为 104） | `n_full_windows = mel_len // 800` | 同上（11 个最差段重复 4-gram 183 → 1） |
| ③ | **`max_new_tokens` 固定成 32，错译了官方的自适应生成预算**（1–4 token 负反馈） | 与 CUDA 官方 `example.py:118-155` 逐项对齐的 8 变体受控实验：只改这一项，5 段 40.27% → 4.36%；改 chunk/k/lookahead 全部无效 | `_adaptive_budget_init/update` + 中文分支，默认开启 | **17.87% → 7.88%** |

必须知道的两个耦合约束：

- **自适应必须配 `unfixed_token_num=5`** —— k=1 + 自适应在 640 ms 下退化到 29.19%（比固定 32 更差）。
  `transcribe_stream.py` 在检测到该组合时会打印告警。
- **不要照搬 CUDA 的 160 ms chunk** —— 实测换来 3.2 倍墙钟、WER 几乎无变化。
- **段尾 flush 预算保持 `max(64, ...)`** —— 官方段尾用 `first_max_new_tokens`（640 ms 时为 8），
  但 61-min 受控实验证明改过去会**截断段尾**：D 从 54 涨到 153，WER 7.88% → 8.41%（更差）。
  原因是 OV 的流式过程未必在最后一个 chunk 收敛。实验开关保留为
  `SegmentedStreamer(finish_budget='first')`，不作默认。


## 长音频 / OOM（C-014 关键修复）

### 复现结论（不分段时）

- **不是 OOM，是 encoder 位置编码上限**：`audio_config.max_source_positions=1500`（即 1500 × 80 ms = **120 s**）
- 崩溃点：音频累积约 **120.3 s** 时 encoder 内部 `Add_774378: Argument shapes are inconsistent`（n_audio ≈ 1556）
- 实时性：
  - 30 s 后 chunk wall 0.7 s（**瞬时 RTF ≈ 1.1**，已失守）
  - 80 s+ chunk wall 1.7-2.2 s（**瞬时 RTF ≈ 2.6-3.4**）
- 内存：RSS 平稳 4-4.8 GB（不是内存瓶颈，是计算量 + 位置编码上限）
- 曲线外推：30 min 时 n_audio ≈ 22500，crash 早在 120 s 就会发生

### 修复：VAD 切句分段（C-018 修正版）

- **不按固定时长盲切**（会把单词/句子从中间切断）
- 累积到 `min_segment_sec`（默认 **12 s**）后，在 `[12 s, max_segment_sec]`（默认 **20 s**）内找静音点切
- 切点必须走 `finish_streaming_transcribe` flush 尾巴（修了 C-015 #3 丢字）
- 新段 `unfixed_chunk_num=0`（per 官方 ws_server）
- 简单能量 VAD（100 ms 帧，最低 RMS 段中点）；无静音则硬切到 `max_segment_sec`

### CUDA（audio.cpp）不分段也有同样的上限

这不是 OV 独有的问题，是**同一份 HF 模型架构的固有上限**：

| 输入长度（不分段流式，Q8_0 + RTX 5050） | 结果 |
|---|---|
| 3 min / 4 min | ✅ 文本正确（RTF 1.37 / 1.64） |
| **5 min / 10 min** | ❌ `audio encoder token count exceeds max_source_positions` |

- CUDA 不分段触发阈值 **240–300 s**；OV 旧 IR 是 **120 s**（`max_source_positions=1500`）
- 结论：**CUDA 与 OV 都需要调用方自己做 VAD 切句**，audio.cpp 本身不支持长音频
- 按同一套 VAD 切段（226 段）跑完整 61 min，CUDA 流式是干净的：**WER 7.62%**（本机口径）/
  7.69%（reviewer 口径）。它是同一算法的 dGPU 参照，**不是本项目的验收基线**
  —— 验收基线是 MiniMax 云端 asr-1.0

### 验证（61.19 min 英文录音）

- 音频：`test_audio/<redacted>.wav`（16 kHz mono，Intel 业务会议英文）
- 计划 **226 段**（VAD 切），实测段长 min 0.6s / mean 16.2s / max 20s
- 全文 RTF ≈ 0.6，段 RTF P50 ≈ 0.58 / P95 ≈ 0.7 / max ≈ 0.99
- 全程 RSS 4.0-4.8 GB，**不随时长增长**（与分段前 30 s 后失守形成对比）
- 交付：
  - `reports/spe_61min_transcript.txt`（每段一行 `[起始秒-结束秒] 文本`）
  - `reports/spe_61min_segments.json`（每段 start/end/text/chunks/wall/rtf）

### `transcribe_stream.py` 默认行为（C-047 起为交付配置）

| 场景 | 行为 |
|--|--|
| 默认 | `SegmentEncoderOVBackend`（`ov-encoder-segment-reviewer` 整段全局注意力 encoder + `ov-int8-past` weight-only INT8 stateful decoder）|
| 短音频（≤ 20 s）| VAD 切成 1-2 段，行为与单段流式几乎一致 |
| 长音频（> 20 s）| VAD 在 12-20 s 内找静音切，226 段 ≈ 60 min |
| 生成长度 | **C-047 自适应**（默认开启）：每 chunk 按官方负反馈动态决定，base=8 / floor=16，取代固定 `max_new_tokens=32` |
| `--no-adaptive-budget` | 退回固定 `max_new_tokens=32`（仅复现历史行为；WER 17.87%）|
| `--no-seg` | 关闭分段，恢复单段（短音频 < 24 s 用；更长会撞 segment encoder 2400 帧硬上限） |
| `--strategy rolling` | 按 `max_segment_sec` 等分硬切（fallback） |
| `--strategy vad_roll` | VAD 优先，超过 max 强制切 |
| `--decoder-dir` | 切换 decoder IR。**C-043/C-044 的混合精度变体已证伪**，默认 `ov-int8-past` 即为达成 7.88% 的配置 |
| `--backend window` | 旧窗口 encoder 路径（仅复现历史行为用，非交付配置）|

> **C-045 变更说明**：旧默认是 `OVBackend` + optimum encoder IR（`models/ov-int8-past` 的 encoder 部分）
> + rolling 30 s。C-021 已实测该 encoder IR 全长度都错（4 s cos 0.64），已废弃。
> 现默认与 C-039 61-min 验收配置的 encoder/decoder 完全一致。

> **C-047 变更说明（重要）**：`max_new_tokens` 从固定 32 改为**自适应生成长度**。
> 这是 C-033 移植 R2T2 官方流式时漏掉的机制（见
> `third_party/Confucius4-R2T2/example.py:118-155`）。固定 32 会让单次自回归失控
> 直接写满冻结前缀，造成重复复读（61-min 实测 n3 重复 1983 次、插入错误 1025 词）。
> 61-min 全量集：**WER 17.87% → 7.88%，RTF 0.687 → 0.639**。
> 7.88% 已持平 C-045 的离线/两遍式 7.84%，**故两遍式方案不再需要**
> （省 3 秒段尾延迟 + 二次计算）。详见 `reports/C047_CUDA_PARITY.md`。

## 项目结构

```
confucius4-openvino/
├── transcribe_stream.py         # 部署入口（segment encoder + INT8 / 640ms / GPU.0 / VAD 12-20s / 自适应预算）
├── seg_stream.py                # C-014 分段驱动（VAD 找静音 + max 硬切）
├── backends.py                  # OVBackend + TorchBackend + ASRBackend 接口
├── segment_encoder_backend.py   # C-039 整段全局注意力 encoder backend（交付路径）
├── window_encoder_backend.py    # C-023 窗口 encoder backend（历史/对照）
├── streaming_asr.py             # backend-agnostic LSP 主循环 + C-047 自适应生成长度
├── c045_export_variants.py      # C-045 decoder 量化候选导出（mix4/mix8/INT4+AWQ）
├── c045_teacher_force.py        # C-045 候选确定性评估（top-1 / EOS / RTF）
├── c045_61min.py                # C-045 61-min 全长验证（可指定 decoder）
├── c045_two_pass.py             # C-045 两遍式第二遍（C-047 后已非必需，保留作对照）
├── c046_diag_stream.py          # C-046 流式 WER 差距根因取证（5 变体扫描）
├── c046_stream_fix.py           # C-046 LocalAgreement 共识提交修复（备选方案）
├── c046_loop_guard.py           # C-046 严格循环守卫（替代误报的 _detect_any_loop）
├── c047_cuda_parity.py          # C-047 CUDA/OV 流式逐项对齐对比（定位错误引入点）
├── c048_61min.py                # C-047/C-049 61-min 全量验证（baseline/adaptive/finish_first）
├── c045_wer.py                  # WER + S/D/I 分解（本机口径，与 c026 MiniMax baseline 对齐）
├── wer_check.py / wer_breakdown.py  # 真实 WER / S-D-I 误差分解（验收口径）
├── benchmark_int8_step.py       # C-013 分项 benchmark
├── diff_int8.py                 # INT8 vs torch 逐 chunk 对比 + CER
├── test_fe.py / test_decode_no_ehs.py  # 30s padding / tiny ehs 验证
├── test_audio/<redacted>.wav     # 61.19 min 英文真实录音（C-016 验收样本）
├── models/
│   ├── hf/                      # 原始 HF checkpoint
│   ├── ov-encoder-segment-reviewer/  # C-039 整段全局注意力 encoder IR（交付用）
│   ├── ov-fp16-past/            # FP16 stateful decoder IR（参考用，3.9 GB）
│   ├── ov-int8-past/            # INT8 stateful decoder IR（交付用，2.0 GB）
│   └── ov-mix4-past/ ...        # [已证伪，非交付路径] C-043/C-044 混合精度 decoder 变体
│                                #   lm_head-FP16 / per-group / per-layer 敏感度
│                                #   → C-047 证明 WER 瓶颈不在量化，这些产物仅存档
├── reports/                     # benchmark CSV/log + 流式输出 + transcript
│   └── PROJECT_REPORT.md        # 最终交付报告（精度基线 = MiniMax 云端 asr-1.0）
├── status/                      # 与 reviewer 通信：STATUS + history + CORRECTIONS
└── third_party/Confucius4-R2T2/ # 官方 r2t2 源码参考
```

## 部署运行

```powershell
# 1. 装环境（首次）
.venv/Scripts/python.exe -m pip install -r requirements.txt

# 2. 跑流式（默认 segment encoder + INT8 / 640ms / GPU.0 / VAD 12-20s / 自适应生成长度）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav

# 自定义参数
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --chunk-ms 320 --max-new-tokens 32

# 退回固定 max_new_tokens=32（C-047 前的历史行为，WER 17.87%）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --no-adaptive-budget

# 关闭分段（短音频 < 24 s 用）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --no-seg

# 换 decoder IR（注意：C-043/C-044 的混合精度变体已证伪，
# 7.88% 就是在默认 ov-int8-past 上达成的，混合精度不再更优）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --decoder-dir models/ov-int8-past

# 强制等分硬切（fallback，不推荐；会切到词中间）
.venv/Scripts/python.exe transcribe_stream.py path\to.wav --strategy rolling --max-segment-sec 20

# 流式输出示例
# [seg   0] start=   0.00s end=  13.68s chunks=22 wall= 7.16s RTF=0.523 text='Good morning everyone. Morning, let\'s ge'
# [seg   1] start=  13.68s end=  29.69s chunks=24 wall= 9.13s RTF=0.572 text='...'
# [transcribe] strategy=vad max_segment_sec=20.0 segments=226 chunks=...
```

---

## 实时麦克风应用（`mic_asr_app.py`）

把上面这套流式 ASR 包装成桌面应用：采集本机麦克风 → 逐 chunk 增量解码 →
窗口实时显示识别文本。模型和参数与离线 `transcribe_stream.py` 完全一致，
所以显示质量与 61-min 验收口径一致。

```powershell
# 装依赖（仅首次；sounddevice 用于麦克风采集）
.venv/Scripts/python.exe -m pip install sounddevice

# 启动 GUI（默认走系统默认输入设备）
.venv/Scripts/python.exe mic_asr_app.py

# 列出可用输入设备
.venv/Scripts/python.exe mic_asr_app.py --list-devices

# 指定设备
.venv/Scripts/python.exe mic_asr_app.py --device 1

# 终端模式（无窗口，边说边打印，Ctrl-C 结束）
.venv/Scripts/python.exe mic_asr_app.py --cli

# 用音频文件按实时速度回放（无麦克风时自测用）
.venv/Scripts/python.exe mic_asr_app.py --cli --file test_audio/<redacted>.wav
```

界面自上而下：麦克风电平条 → 已定稿文本（黑色）→ 当前段临时结果（灰色斜体）→
状态/RTF 仪表。点「开始识别」开始采集，再点停止会 flush 残留音频。

### 与离线的差异：在线分段

离线路径是「先看完整段音频再规划切点」，实时下做不到，改成**边来边切**：

- 累积到 12 s 后开始盯着最近 3 s 的静音，有静音就切（说完整句再切）
- 到 20 s 硬切（segment encoder 上限 ≈24.3 s，不能超）
- **切点只落在 chunk 边界**（640 ms），不切在 chunk 内部

最后一条是关键。曾经把切点设在静音中点，结果切点后的音频**已经参与过本段的
encoder**、又被当作 carry 喂给下一段，同一段音频被识别两遍，段尾段首出现重复短语
（实测输出 `...for performance, for cost.` 后接 `Cost and for power...`）。
对齐 chunk 边界后，carry 恒等于 `state.buffer`，是一段从未解码过的干净残余。

段收尾也不能直接用 `finish_streaming_transcribe`：它看到非空 buffer 就会把 buffer
拼进 `audio_accum` 再生成一次，等于吞掉要留给下一段的音频。所以 `_finalize()`
自己走一遍收尾生成，只用 `audio_accum`、不动 buffer。
停止时（没有下一段了）才用官方 `finish` 收尾。

### 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--device N` | 系统默认 | 输入设备序号，`--list-devices` 查看 |
| `--file WAV` | — | 用文件按实时速度回放，便于无麦克风自测 |
| `--cli` | 关 | 终端模式，不弹窗口 |
| `--encoder-dir` | `models/ov-encoder-segment-reviewer` | encoder IR |
| `--decoder-dir` | `models/ov-int8-past` | decoder IR |
| `--device-target` | `GPU.0` | OpenVINO 推理设备 |
| `--no-adaptive-budget` | 关 | 退回固定 32（历史行为，WER 17.87%） |
| `--no-seam-dedup` | 关 | 关掉段接缝的 1 词去重 |

`force_language` 默认 `None`（自动）：中英混合场景下模型逐 chunk 自行判语言。
需要锁定单一语言时可用 `--asr-lang`（见下）或界面里的「识别语种」下拉 ——
强制单一语言会让另一种语言的输出变差，所以只在确实只说一种语言时用。

---

## 实时字幕应用（`live_caption/live_caption_app.py`）

比 `mic_asr_app.py` 更完整的实时字幕台：多后端切换、实时翻译、屏幕置顶字幕条、
译文保存。**音频输入支持三种**，在界面「音频来源」下拉里切换：

| 来源 | 采集内容 | 典型场景 |
|---|---|---|
| **麦克风** | 系统默认或指定的输入设备 | 自己对着麦克风说话 |
| **系统声音** | WASAPI 回环，采集**正在播放的输出设备**的混音 | 给会议软件 / 浏览器视频 / 播放器做字幕 |
| **音频文件** | 用户上传的本地音频文件 | 复现某个片段、离线跑批 |

「系统声音」这一路是给会议和视频场景准备的：麦克风会把本地声音、对方声音和
房间噪音一起录进来，而回环只取输出混音，信噪比明显更好，也不会占用麦克风。

### 识别语种（可手动指定）

界面「识别语种 Language」下拉框可指定 ASR 的识别语种，默认「自动检测」。
可选模型内置的 30 种语言（`Chinese` / `English` / `Japanese` / `Korean` …，
取自 `models/hf/config.json` 的 `support_languages`），语种名用**模型的英文名**。
命令行等价参数 `--asr-lang English`。

```powershell
# 终端模式：指定识别语种
.venv/Scripts/python.exe live_caption/live_caption_app.py --cli --source file \
    --file live_caption/test_en_60s.wav --speed 0 --asr-lang English
```

**实现要点（踩过的坑）**：语种提示是以 prompt 后缀 `language {lang}<asr_text>`
注入的 —— 但**不能**只写进 `state.prompt_raw`。三个 backend 实际喂给模型的是
**预构建的静态 prompt 模板**（`ids_left + audio_pad*N + ids_right`），
`ids_right` 来自不含语种的模板，语种提示根本没进模型输入。后果是模型仍自动
判语种，而解析层按 `force_language` 处理，输出被 `language None<asr_text>`
之类的元信息污染（实测强制 English 时整段文本前堆了 16 个该前缀）。

修法：新增 `_build_prompt_template_ids_for(force_language)`，把语种后缀
**编码进 `ids_right` 末尾**（语种后缀落在模板右半部分，即 assistant 起始之后）；
NPU 走 embedding 路线，对应地在 `build_inputs_embeds` 里把语种后缀的
embedding 插在 `emb_right` 之后、`prefix` 之前。

验证：同一段英文录音，强制 `Chinese` 时模型输出「但我们正在取得进展」，
强制 `English` 时输出英文 —— 证明语种提示确实进了模型。

### 草稿译文（默认关闭，可选）

「草稿译文」指**还没定稿的那半句**的实时翻译预览（界面里浅蓝色的「〔译〕」行）。
v1.2 起**默认关闭** —— 默认只翻译**已经定稿**的文本。

- GUI：界面「翻译后端」那一行右侧有「**草稿译文 Draft**」复选框，**可运行时开关**
  （不用重启程序）；关掉时残留的预览会立刻清掉。
- CLI：`--mt-draft` 开启（默认不开）。
- 环境变量：`LIVECAP_DRAFT=1` 开启（脚本 / CI 场景）。
  原来的 `LIVECAP_NO_DRAFT=1` 语义随「默认关闭」已失效，不再读取。

实现上，`TranslationService.DRAFT_ON` 类常量改为**实例属性 `draft_on`**，
并新增 `set_draft(on)`（关闭时清空 `self.draft` 与 `self._draft_key`）。
`maybe_draft()` 在 `draft_on` 为假时直接返回，翻译队列不受影响。

为什么默认关：草稿每次要翻近一整句 partial，是 GUI 下 ASR 积压的主要来源。
实测矩阵（gpu_int8 ASR + GPU 翻译，60s ABBA 各 2 次）：

| 草稿配置 | RTF 增量 | 积压增量 |
|---|---|---|
| 间隔 0.8s 无暂停 | +0.274 | +0.30s |
| 间隔 0.8s + 积压暂停 | +0.246 | +0.60s |
| 间隔 1.5s + 积压暂停（打开时的配置） | +0.144 | +0.25s |
| 草稿全关（**默认**） | +0.042 | +0.05s（噪声级） |

### 屏幕字幕（overlay）的四行

屏幕底部的置顶字幕条是**四行**：

| 行 | 内容 | 颜色 | 出现条件 |
|---|---|---|---|
| 1 | 最近定稿的英文原文 | 白 | 始终 |
| 2 | 正在识别的实时文本 | 黄 | 有 partial 时 |
| 3 | **定稿文本的译文** | 青 | 翻译开着且该段已译完 |
| 4 | 草稿译文预览 | 浅蓝 | 勾选了「草稿译文」且有预览 |

★ **关掉草稿译文，第 3 行仍然要显示译文** —— 草稿只影响第 4 行。
译文取最近 3 段的译文拼接。

> 这里曾有个缺陷：算 overlay 译文时写的是 `for b in self.blocks[-3:]`，
> 迭代出的是**原文文本**，而 `_mt_of(seg)` 要的是**段序号**（blocks 的下标），
> 查 `seg_keys` 自然查不到 —— 结果是屏幕字幕的译文行**永远为空**
> （主文本区的译文正常，所以很难发现）。现已改为按下标取。
> 另有一处：原来用 `mt_tail or draft`，定稿译文一出现就把草稿预览顶掉了，
> 现在草稿单独占第 4 行。

验证：`verify_overlay.py`（18 项，无 Tk 模拟）+ GUI 自测截图。

### 翻译后端（设备 × 量化）

`translator.MT_ENGINES` 是翻译侧的「设备 × 量化」可选项，与 ASR 的 `ENGINES` 同构。
候选项定义在 `_MT_CANDIDATES`，**只有本机真实存在模型目录的才进下拉**，
所以客户机上不会出现「缺模型」的项。

| key | 设备 | 量化 | 模型目录 | 实测 tok/s | TTFT 中位 | 加载 | 随包 |
|---|---|---|---|---|---|---|---|
| `gpu_int4cw` | GPU.0 | INT4_SYM cw | `mt2-int4sym-cw-q`（993 MB） | 57.9 | 35 ms | 6.9 s | ✅ |
| `gpu_int8cw` | GPU.0 | INT8_SYM cw | `mt2-int8sym-cw-q`（1.7 GB） | 37.5 | 44 ms | — | ❌ |
| `npu_int4cw` | NPU | INT4_SYM cw | `mt2-int4sym-cw-q`（993 MB） | 44.0 | 292 ms | 15.7 s | ✅ |
| `npu_int8cw` | NPU | INT8_SYM cw | `mt2-int8sym-cw-q`（1.7 GB） | 29.6 | 300 ms | — | ❌ |

（实测数据来自 `hy_bench/bench_mt2.py`，7 句 × 3 次取中位。）

> **v1.3 客户包只附带 INT4**（INT8 1.7 GB 已移除，包体少约 1.8 GB）。
> 理由：INT8 与 INT4 的译文差异仅为同义改写（相似度中位 0.966），
> 却多占约 700 MB 显存、慢约 33%，对客户机没有实际收益。
> 开发机 `hy_bench/ov/` 下仍保留 INT8 产物供对比测试。
>
> 代码上用 `_MT_CANDIDATES` 的 **bundled 标记**区分「本包不附带」与「本机缺模型」：
> `--check` 对前者显示 `[ — ]（本包不附带该量化版本）`，不会让客户误判为安装故障；
> GUI 下拉本身无需改动（模型目录不存在时该项自动不出现）。

翻译侧是 `og.LLMPipeline(model_dir, device)`，**GPU 与 NPU 走同一条代码路径**，
没有 NPU 专属分支 —— 所以加一个新设备×量化组合只需往 `_MT_CANDIDATES`
加一行 + 放好模型目录，不用改推理逻辑。

**v1.3 翻译模型由 Hunyuan-1.8B-Instruct 换成 Hy-MT2-1.8B**：
旧模型是通用指令模型而非翻译模型，遇专业术语会乱译、偶尔输出解释性文字。
Hy-MT2-1.8B（`tencent/Hy-MT2-1.8B`，架构同为 `hunyuan_v1_dense`）是翻译专用模型，
换过去后**译文质量明显提升，且速度不降反升**（INT4 57.9 vs 49.4 tok/s）。

配套改动（`live_caption/translator.py`）：
- prompt 改用官方 Default Translation 指令模板 —— **无 system prompt**，指令与待译文本同放 user 消息；
- 带上下文的分支改用官方 Structured Data 模板的简化版（`[Background Information]` + `[Source Text]`）；
- `generation config` 去掉旧 Instruct 专用的 `</answer>` stop_strings（MT2 直接输出译文正文，EOS 自停）；
- 模型目录解析全部指向 `mt2-*`（客户包 `models/mt/mt2-*` → 开发机 `hy_bench/ov/mt2-*`）。

> ⚠️ **Hy-MT2-1.8B 与 Hunyuan-1.8B-Instruct 的 `config.json` 几乎完全相同**
> （同 `HunYuanDenseV1ForCausalLM` / `hunyuan_v1_dense` / 32 层 / hidden 2048 / 16 头 /
> vocab 120818 / ctx 262144），**光看 config.json 无法区分两者**。
> 判别要看 `chat_template.jinja` 与实际输出行为。

**v1.2 新增 `gpu_int8cw`（Intel GPU · INT8-CW）**：
INT8 量化比 INT4 多占约 700 MB 显存、慢约 35%，但翻译质量与 INT4 持平且无乱码。
ASR 默认也在集显上，两个模型会争抢显存和算力 —— 已在选项说明文字里提示。
机器吃紧时优先用 INT4-CW。

```powershell
# 装依赖（仅首次）
#   sounddevice  麦克风采集
#   soundfile    音频文件解码
#   av (PyAV)    m4a/mp4 等 libsndfile 不支持的容器
#   soundcard    WASAPI 回环（系统声音），纯 cffi 实现，不需要 ffmpeg
.venv/Scripts/python.exe -m pip install sounddevice soundfile av soundcard

# 启动 GUI
.venv/Scripts/python.exe live_caption/live_caption_app.py

# 列出麦克风 + 可回环的系统输出设备
.venv/Scripts/python.exe live_caption/live_caption_app.py --list-devices

# 终端模式：麦克风
.venv/Scripts/python.exe live_caption/live_caption_app.py --cli --source mic

# 终端模式：系统声音（采集正在播放的内容）
.venv/Scripts/python.exe live_caption/live_caption_app.py --cli --source system

# 终端模式：音频文件（--speed 0 = 全速跑批，1.0 = 实时回放）
.venv/Scripts/python.exe live_caption/live_caption_app.py --cli --source file \
    --file live_caption/test_en_60s.wav --speed 0
```

### 环境检查（`--check`）

客户包里的 `Diagnose.bat` 会调 `live_caption_app.py --check`，输出一份体检报告：

```
── 依赖 ──                          numpy / openvino / openvino_genai / transformers / 音频库
── OpenVINO 设备 ──                 CPU / Intel 集显 / NPU / 独显，并单独给「集显可用」「NPU 可用」结论
── ASR 后端（识别）──               6 个后端各自的模型文件是否齐全、设备是否匹配
── 翻译后端（Hunyuan-1.8B）──        5 个「设备 × 量化」后端的模型是否在本机
── 音频设备 ──                       可用麦克风 + 可回环的系统输出设备
```

每一项前面是 `[ OK ]`（可用）或 `[缺 ]`（不可用）；缺项在括号里给原因
（`缺 audio.cpp（audiocpp_cli.exe），本包不自带` / `缺模型` / `本机没有该设备`）。

**注意不检查 torch** —— 本程序刻意 `USE_TORCH=0` 不依赖它，客户包也不带 torch，
列成「缺」只会误导客户。

### 相对路径（不依赖安装位置）

`live_caption_app.py` / `translator.py` 里**不写死盘符和用户名**，全部相对包根推导：

```
APP_DIR   = <代码所在目录>            # live_caption/ 或客户包的 app/
PKG_ROOT  = dirname(APP_DIR)         # 包根
MODELS    = <包根>/models             # 可用 LIVECAP_MODELS_DIR 覆盖
```

客户包把开发机的模型目录**重命名并重组**过（权重逐个 md5 一致，只是目录名不同），
所以额外有一层解析：

- `_MODEL_ALIASES`：逻辑名 → 客户包目录名列表（`ov-int8-past` → `decoder-gpu-int8`）
- `_model_path(name)`：先查别名，再回退开发版原名；分隔符统一按 `/` 处理
  （`ENGINES` 里写的 `c089_int4\R4` 和别名表的 `c089_int4/R4` 都能命中）
- 散落文件（如 NPU 用的 `embed_tokens_f16.npy`，包内被提到 `models/` 根）
  走「别名 + 文件名」两级回退

其它路径：

| 用途 | 查找顺序 | 环境变量 |
|---|---|---|
| 翻译模型 | `models/mt/<name>` → `hy_bench/ov/<name>` → `~/.openvino/models/...` | `LIVECAP_MT_MODEL` / `LIVECAP_MT_CW_ROOT` |
| CUDA 运行包 | `<包根>/cuda/` → `~/confucius4-r2t2`（须有 `audio.cpp/audiocpp_cli.exe`） | `LIVECAP_CUDA_DIR` |
| 编译缓存 | `~/.openvino/models/...` → `<代码目录>/<name>` | — |

编译缓存放用户目录而不是包内，是因为包可能装在 `Program Files`（只读）。

实测：整包复制到带空格与中文的全新路径后，ASR 与翻译端到端均正常。

### 三种输入的实现要点

三种来源最终都归一到 **16 kHz 单声道 float32**，差异全部封在
`live_caption/audio_source.py` 里：

- **麦克风**（`sounddevice`）：走设备原生采样率（44.1/48 kHz 都有），
  在下游重采样。插值刻意不放在 PortAudio 的实时回调里 —— 回调线程做
  numpy 插值会挤占实时线程，丢帧的风险比音质损失大。
- **系统声音**（`soundcard`）：向 WASAPI 设备**直接要 16 kHz**，由 Windows 的
  SRC（重采样器）负责降采样，比自己插值干净。输出设备没有声音时 WASAPI
  **不产生任何帧**，直接等会卡住流水线，所以这里改成「超时补静音」，
  让下游的 VAD / 切段能正常看到一段静音。
- **音频文件**（`soundfile` + `av`）：先用 libsndfile 解（WAV/FLAC/OGG/MP3），
  失败再回退 PyAV（m4a/mp4/aac 等）。解码后按实时速度回放，
  `--speed 0` 则是全速跑批（跑批时积压会很大，注意看指标栏）。

### 两个坑（改代码前先读）

1. **COM 公寓**：WASAPI 是 COM 组件，规矩是「每个线程都要自己 `CoInitializeEx`」。
   `soundcard` 自己在 **import 时** 初始化 COM，而设备枚举和采集发生在
   别的线程上。顺序弄错的表现是系统声音模式一启动就报
   `Error 0x100000001`。`audio_source._co_prepare_thread()` 处理了这件事：
   soundcard 没 import 过就让它自己初始化（我们不再插手），import 过了
   才由当前线程自己初始化并配对 `CoUninitialize`。
2. **队列要复用**：`Session` 必须用音源自己的 `out_q`。另建一个队列的话，
   音频永远进不来，表现为「音频 0.0s、队列空、界面不动」。

### 音源自测

```powershell
# 不加载 ASR 引擎，只验证三种音源都能稳定产出 PCM
.venv/Scripts/python.exe live_caption/selftest_audio_sources.py
```

### 切段规则（定稿时机）

`live_caption_app.Segmenter` 有两条切段规则，任一满足即切段并定稿：

1. **常规规则**：段长 ≥ `MIN_SEG_SEC`（12 s）后，最近 `SIL_LOOKBACK_SEC`（3 s）
   内有 ≥300 ms 静音；段长 ≥ `MAX_SEG_SEC`（20 s）硬切。
2. **静音超时规则**：段尾出现连续 ≥ `SILENCE_CUT_SEC`（1.2 s）的静音就立即切段，
   不管段长够不够 12 s。

**为什么加第 2 条**：原规则只在段长 ≥12 s 后才去看静音。短语音（会议里一句
「好的」大约 1–3 秒）说完后，用户要干等到累积满 12 秒才能看到定稿，
字幕不转白、译文也跟着卡住。实测修复前 3 秒语音要等 5.8 s、5 秒语音等 5.2 s；
修复后分别是 1.3 s 和 1.0 s。

**不会损失识别质量**：切段点落在静音区，音频内容已经解码完，提前收尾得到的
文本与等满 12 秒的结果**逐字相同**（`diag_early_cut.py` 对比 cut=1.0/1.5/2.0/3.0 s）。

**保护期** `SILENCE_TAIL_GUARD_SEC`（0.35 s）：刚开口的第一个音节（尤其爆破音
/b/ /p/）本身能量低，可能被静音检测当成静音。保护期内的静音不足以切段，
避免把第一个字切到下一段。保护期是相对**静音起点**算的，不是相对音频末尾。

判定「段尾静音」用的是 `seg_stream.find_trailing_silence()` —— 它找的是
**紧贴音频末尾**的那段连续静音。已有的 `find_silence_in_range()` 找的是范围内
**最长**的静音段，静音持续久了以后最长段会从窗口左边界外开始，算出来的起点
是假的，不能用于这个场景。

阈值可用环境变量微调：

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `LIVECAP_SILENCE_CUT_SEC` | 1.2 | 段尾连续静音多久就切段 |
| `LIVECAP_SILENCE_TAIL_GUARD_SEC` | 0.35 | 静音起点前的语音保护期 |

### 断句（送翻译前）

定稿文本不是整段丢给翻译模型的 —— `translator.split_sentences()` 会先切成
句子，每句单独送翻。断句质量直接决定译文质量。

**依据**：业界实时语音翻译的通行做法（ACL N13-1023《Segmentation Strategies
for Streaming Speech Translation》、EMNLP 2020《Direct Segmentation Models
for Streaming Speech Translation》）：

| 业界结论 | 本项目做法 |
|---|---|
| 标点预测是 BLEU 最高的策略（`pred-punct`） | 按句末标点切（标点来自 ASR 模型输出） |
| 最优平均段长 **8–12 词**（与 MT 训练分布一致） | 目标区间 `TARGET_SEG_WORDS=(8,12)` |
| 固定长度窗口会**破坏语义上下文** | 超限时**优先在从句边界（逗号/顿号）断开**，而非机械按词数硬切 |
| 断句要区分「句末」与「词中」 | 小数点、缩写点不切（见下） |

**为什么不能「见到 . 就切」**：ASR 输出里的小数点、缩写点、版本号点都会把句子
切碎，切碎会**直接产出错误译文**。改造前实测：

| 原文 | 改造前（错误） | 改造后（正确） |
|---|---|---|
| `It cost 1.5 million dollars.` | 「1.5万美元。」+「1.」+「500万美元。」 | 「花费了150万美元。」 |
| `The U.S. economy grew 3.5 percent.` | 「美国」+「经济增长率为3%。」+「百分之五。」 | 「美国经济增长率提高了3.5个百分点。」 |
| `Dr. Smith joined at 9 a.m. today.` | 「医生」+「史密斯于上午9点加入。」+「今天是。」 | 「史密斯医生今天上午9点加入。」 |
| `Prof. Wang will present at 3 p.m.` | 「教授」+「王将在下午3点出席。」 | 「王教授将于下午3点进行报告。」 |

**判定规则**（`translator._is_decimal_point` / `_is_abbrev_boundary`）：

- **小数点**：两侧都是数字 → 不切（`1.5`、`3.14`、`1.2.3`、`v1.0`）
- **缩写点**：整个**点分链**（`U.S.`、`a.m.`）作为一个单位，任一个点都不切
- **已知缩写**：`Dr.` `Prof.` `Mr.` `Jan.` 等称谓/月份/星期
- **守卫**：缩写点后面必须是「空白 + 大写字母」（下一句开头），否则按句末处理。
  这条防止 `We shipped no.` `The max.` 这类普通词结尾的句号被误当缩写，
  导致**该断的句子断不开**

**段长控制**：`MAX_SEG_WORDS = 20` 词 / `MAX_SEG_CHARS = 60` 字（中文没有词
边界，按字符数控制）。超限时优先在逗号/顿号处断 —— 真实案例：

```
改造前：...our 28 core has now | hit qs.        <- 切出孤立片段
        译文：「击打。」（模型把 qs 当拼写错误）
改造后：...[REDACTED], | big milestone in that our 28 core has now hit qs.
        译文：「我们的28个核心模块已经达到了里程碑。」
```

**验证**：`verify_segmentation.py`（51 项）、`verify_segmentation_e2e.py`
（真实模型对比改造前后译文）。

### 延迟回归

```powershell
# 量化「说话结束后多久定稿」：喂语音 → 喂静音 → 记录定稿时刻
.venv/Scripts/python.exe live_caption/diag_final_delay.py gpu_int8 3 25
# 期望输出：结论：说话结束 → 定稿耗时 1.3s
```

### 翻译加载的两个坑（v1.2 修复）

「翻译一直显示 GPU.0 加载中…」有两个独立成因，都在 `translator.py`：

**坑 1：transformers 延迟导入的并发竞态**

transformers 4.57 用的是 lazy import（真正 import 某个类时才执行子模块 `__init__`）。
ASR 引擎加载线程（`backends.py`）和翻译加载线程（`translator.py`）都会 import
transformers，**同时**首次导入时必有一方失败：

```
ImportError: cannot import name 'AutoTokenizer' from 'transformers'
```

实测 8 线程并发首次导入有 2 个失败。

对策：
- `translator.import_transformers_auto_tokenizer()` —— 模块级锁把 import 串行化，
  失败重试 4 次（每次间隔 0.2 s，等前一次 import 收尾）
- `translator.prewarm_transformers()` —— 在 GUI **主线程**、引擎加载**之前**调用，
  后台线程再 import 时模块早已就绪（主线程做的，用户还没法操作）
- GUI 启动日志会打一行 `prewarm transformers 2.4s`

**坑 2：线程死掉后状态卡在 loading**

`TranslationService` 用 `self.th` 持有工作线程。加载失败时线程会退出，但
`self.th` 仍指向那个**已死**的线程对象：

```python
if not self.active or self.th is None:   # ← 旧代码：死线程不是 None，判断不出来
    return True
self.state = 'loading'                    # ← 置成 loading，但没有线程会去加载
```

于是用户切换一次翻译后端，状态就变成 `loading` 且**永远不会变** ——
表现就是「翻译 GPU.0 加载中…」一直不变。

对策：
- `TranslationService._thread_alive()` —— 用 `self.th.is_alive()` 判断，
  `set_target()` / `set_engine()` 都改用它
- `set_engine()` 在线程已死时**真的重启**（`_start()`），而不只是保持状态
- `TranslationService.restart()` —— 强制重启（旧线程先停掉再起新的），
  GUI 的「↻ 重试翻译 Retry」按钮调它

**顺带改进的可见性**：状态栏的「加载中…」会显示已等待秒数（>30 s 提示首次编译慢，
>90 s 提示可能卡住）；失败时只显示错误摘要（完整堆栈写进 `live_caption.log` 的
`mt load failed` 行）；失败时亮出重试按钮。

## 关键技术修复（cumulative 12 步）

| 步骤 | 修复 | 效果 |
|--|--|--|
| 1. 导出 with-past | `optimum-cli export --task automatic-speech-recognition-with-past` | decoder stateful（57 ReadValue/Assign）|
| 2. backend 拆分 | TorchBackend（golden）+ OVBackend（生产）| 同接口、同循环 |
| 3. INT8 导出 | `--weight-format int8` | 2 GB（FP16 → INT8），NNCF 量化 |
| 4. **30s padding 修复** | `WhisperFeatureExtractor` `padding="do_not_pad"` | N_audio 85（不是 375），80% 静音被消除 |
| 5. **decode 步 tiny ehs** | `np.zeros((1,1,2048))` 占位 | stateful cross-attn 已缓存，5% 加速 |
| 6. 预热 pass | 先跑一遍不计时 | 避开 GPU 首次 kernel 编译 |
| 7. attention_mask 显式传 | TorchBackend generate | 消除 `attention mask is not set` 告警 |
| 8. decode 重置 state | 每 chunk `dec_infer.reset_state()` | KV 不串味 |
| 9. **VAD 切句** | 12-20 s 内找静音点切 | encoder 位置编码 ≤ 1500 永远满足；长音频 RTF 稳定 |
| 10. **新段 unfixed_chunk_num=0** | per 官方 ws_server | 段首不留 ghost prefix |
| 11. **切点 finish flush** | 段尾必走 `finish_streaming_transcribe` | 修 C-015 #3 丢字 bug |
| 12. **分段** | 简单能量 VAD | backend-agnostic，TorchBackend/OVBackend 共享 |

## 性能对比（6.74s 测试音频，warmup 后）

| 配置 | RTF | decode ms/tok | chunks | 与 torch 内容字差异 |
|--|--:|--:|--:|--|
| FP16 with-past, 320ms chunk | 1.368 | 64 | 22 | 0 |
| FP16 with-past, 640ms chunk | 1.166 | 64 | 11 | 0 |
| FP16 with-past, 1000ms chunk | 0.465 | 64 | 7 | 0 |
| **INT8 with-past, 640ms chunk** | **0.444** | **33** | 11 | **0** |
| CUDA baseline (Q8_0), 320ms | 0.544 | — | 22 | — |

## 句尾 `。` 问题（C-013 #6 结论）

- **torch FP32 golden**：句尾无 `。`
- **INT8**：句尾**有** `。`（chunk 7 / chunk 10）
- **CUDA Q8_0 baseline**：句尾有 `。`
- r2t2 官方 `finish_streaming_transcribe`（third_party/.../r2t2_asr.py:492-578）逻辑：和我们的 `streaming_asr.py:finish_streaming_transcribe` 一致
- **结论**：r2t2 官方逻辑本身 + FP32 torch 模型都不出 `。`，是模型精度问题。INT8 量化反而使 `。` 出现（与 CUDA Q8_0 一致）。**无需为 `。` 改算法**。

## Encoder 根因 & 修复（C-021~C-024）

### 根因

`optimum-intel` 导出的 encoder IR 在长音频上**逐 token 与 torch 不一致**（cosine 0.29-0.64，token 数也错）。
定位：`optimum-intel.Qwen3ASRModelPatcher._patch_audio_encoder` 用一份**简化版 forward** 替换了
`Qwen3ASRAudioEncoder.forward`，简化版对整段 mel 做：

1. **1D stride-8 conv**（把 100 帧一块的 chunk 折叠成 stride-8 的等长 token），丢掉 per-chunk 边界
2. **全局位置编码**（不是 per-chunk 循环 0-12），撞 `max_source_positions=1500` 上限
3. **标准 attention**（`is_causal=False` + 单一 mask），忽略 `cu_seqlens` 的 per-window 切分

证据（6.7 s 中文样本 parity，但 12-20 s 全坏）：
- 6.7 s < 800 帧：单 window，per-chunk 位置编码退化为全局，刚好巧合一致
- ≥ 12 s ≥ 1.2 个 window：分块/窗口逻辑被替换，cosine 暴跌
- 不分段 120 s 时 `Argument shapes are inconsistent`（n_audio=1556 > 1500）— 整段累积是另一表现

### 修复（方案 a，chosen）

不走 optimum 的 encoder IR，**自己用 `torch.jit.trace + ov.convert_model` 重新导出单窗 IR**：

- 输入固定 `(1, 128, 800)` + `cu_seqlens (2,) int32`（窗口内 valid token 数）
- 内部按 `qwen_asr.modeling_qwen3_asr.Qwen3ASRAudioEncoder.forward` 原逻辑：
  - 8 块 100-frame × 128-mel → 3 stride-2 conv → per-chunk 位置编码 (0-12，每窗内循环 8 次)
  - 24 层 attention，**显式构造 4D mask (1, 1, 104, 104)** 屏蔽 `cu_seqlens[1]` 之后的位置
    （为什么不用 cu_seqlens：SDPA / FA2 的 varlen 路径与原 eager 实现数值略差，且 trace 时 cu_seqlens 是输入张量；
    显式 4D mask 让 OV 用与原 Qwen3ASRAudioAttention 一致的 attention_interface）
- stride 保持：`mel.T.view(8, 100, 128).transpose(1, 2)`（与原 audio_tower 非 contiguous stride 一致，
  `mel.view(8, 128, 100)` 的 contiguous stride 会让 conv 输出有 0.04 数值差）

```python
# c023_export_window_encoder.py
class SingleWindowEncoder(nn.Module):
    def forward(self, input_features, cu_seqlens):
        x = input_features.squeeze(0)  # (128, 800)
        x = x.T.view(8, 100, 128).transpose(1, 2)  # (8, 128, 100) non-contig
        # 3 stride-2 convs + per-chunk pos emb (0..12) + 24 layers with 4D mask
        # output: (1, 104, 2048), Python side裁到 cu_seqlens[1]
```

导出：`ov.convert_model(traced, example_input=(randn(1,128,800), tensor([0,104], int32))` →
`models/ov-encoder-window/openvino_encoder_model.xml`（FP16 + FP32 两份）

### 验证（`c023_validate_window_encoder.py`）

| dur | n_mel | torch_n | ov_n | cos_mean | cos_min | pass |
|--:|--:|--:|--:|--:|--:|--|
| 4s | 400 | 52 | 52 | 1.0000 | 1.0000 | ✅ |
| 8s | 800 | 104 | 104 | 1.0000 | 1.0000 | ✅ |
| 10s | 800 | 104 | 104 | 1.0000 | 1.0000 | ✅ |
| 12s | 1200 | 156 | 156 | 0.9994 | 0.9984 | ✅ |
| 16s | 1600 | 208 | 208 | 0.9998 | 0.9986 | ✅ |
| 20s | 2000 | 260 | 260 | 0.9996 | 0.9966 | ✅ |
| 30s | 3000 | 390 | 390 | 0.9994 | 0.9916 | ✅ |
| 60s | 6000 | 780 | 780 | 0.9994 | 0.9780 | ✅ |

> 表中 n_mel 已用真实 100 frames/sec（hop=160, 16kHz）修正；之前 c023 验证脚本用
> `dur*80` 的错误标注不影响数值对比（用同一 n_mel 给 torch + OV），仅标签错。

### 流式 window cache（C-024 #3）

Qwen3-ASR encoder 的窗口之间**互相独立**（cu_seqlens per-window），所以流式时：

- 已填满的 800-mel 窗口（每 8 s 音频）的 encoder hidden states 可以**缓存**
- 每 chunk 只重新编码**最后一个未满窗口**（≤ 8 s 音频）
- encoder 每 chunk 成本有上界 ≈ 1 个 window（~30 ms GPU.0）

实现：`window_encoder_backend.py::WindowEncoderOVBackend`：
```python
for w in range(n_full_windows):
    if w < len(self._window_cache_ehs):  # 命中
        out_chunks.append(self._window_cache_ehs[w])
    else:  # 未命中
        ehs = self._encode_window(mel[:, w*800:(w+1)*800], 800)
        self._window_cache_ehs.append(ehs)
# partial 最后一窗永远重算
if last_chunk_count > 0:
    out_chunks.append(self._encode_window(mel[:, n_full_mel:], valid_in_partial))
```

## 性能瓶颈 & 后续优化

- **decode 仍占 60%**（33ms/token × 5-9 token/chunk）。如需进一步降低：
  - **C-006 step4 cached prefix**（prompt 头部 9 token 的 KV 复用）— 未实现，预期省 5-10%
  - **Window attention 复用**（n_window_infer=800）— **C-024 已实现**：encoder 每 chunk 只算最后未满窗（≤8 s 音频），满窗 ehs 缓存
  - **INT4**（`--weight-format int4 --ratio 1.0 --sym`）— 理论再省 30-40%，但精度风险大。**未做**（C-013 明确不做）
- **分段位置编码 hard cap**：encoder `max_source_positions=1500`（120 s）→ 必须 ≤ 20 s 段长。
  - 提升路径：换 encoder IR 重新 trace，把 dynamic shape 上限拉到 4096（成本是 IR 重导 + benchmark）

## 弃用的旧实现

- `ov_r2t2.py`（旧手写 OVR2T2ASR）— 已被 `backends.py::OVBackend` 取代
- `models/ov-fp16/`、`models/ov-int8/`（no-past 版本）— 已被 `models/ov-{fp16,int8}-past/` 取代
- `verify.py`（旧 CER 对比）— 已被 `diff_chunks.py` / `diff_int8.py` 取代
- `monitored_stream.py`（C-014 #1 OOM 监控）— 一次性脚本，验证完保留供复现用

## 协议

执行/监控协议、纠偏通道（CORRECTIONS.md）、检查点报告：见 `status/STATUS.md` 与 `status/CORRECTIONS.MD`。
