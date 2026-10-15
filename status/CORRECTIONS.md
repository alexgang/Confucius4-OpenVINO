# CORRECTIONS（reviewer 写，执行 agent 只读）

格式：`## C-编号 [BLOCKING|NORMAL|FYI] 时间` + 指令内容。执行 agent 处理完后在 STATUS.md 的 last_ack 回执。

## C-000 [FYI] 2026-10-08
通道已建立。reviewer 会定时读取 status/STATUS.md 和 status/logs/。请从阶段 0 开始执行，并先写第一份 STATUS。

## C-001 [NORMAL] 2026-10-08 13:55 — 流式 golden 方案：用官方 r2t2 代码，不用 qwen_asr 的 streaming
官方仓库已推送到 `third_party/Confucius4-R2T2/`（r2t2/、example.py、ws_server.py、README；r2t2_llama 只推了 .py/.md，没推 CUDA 二进制）。
- 不要照 `qwen_asr` 的 streaming_transcribe 移植。R2T2 是用 LSP 前缀做的微调，前缀构造/回滚逻辑以 **`r2t2/r2t2_asr.py` 的 `streaming_transcribe` / `finish_streaming_transcribe`（约第 302-580 行）** 为准，包括 ` ` 回退、`split("|")`、`_normalize_punct_by_context`、`parse_asr_output` / `<asr_text>` 标签处理、中文去空格、`rollback_punctuation`。
- 它的流式只是不依赖 vLLM 的一层薄包装：每个 chunk 用 `prompt_raw + prefix` 加上**累积的全部音频**做一次 greedy 生成，`temperature=0`、`max_tokens=max_new_tokens`。
- **流式 golden 的做法**：把这段循环原样抽成 `streaming_asr.py`，把生成那一步抽象成 `backend.generate(prompt, audio_accum, max_new_tokens) -> text`：
  - `TorchBackend` 用 qwen_asr transformers 后端（CPU FP32）的 generate 实现 → 产出逐 chunk 的 golden（阶段 2）
  - `OVBackend` 用阶段 1 导出的 IR 实现（阶段 3）
  同一个循环，只换 backend，parity 才有意义。可参考 `r2t2_llama/llama_hybrid_backend.py` 的拆分方式。
- audio.cpp 的 Q8_0 结果只做参考对照，不作为真值（计划更正 C12）。离线 golden 照原计划保留。

## C-002 [NORMAL] 2026-10-08 13:55 — 设备名必须写 GPU.0
你们的设备列表里 `GPU.1` 是 RTX 5050。所有 compile_model / `OVModelForSpeechSeq2Seq(device=...)` 一律显式写 **`"GPU.0"`**，不要写 `"GPU"`；启动时断言 `FULL_DEVICE_NAME` 含 "Intel"，并在报告的指标里写明设备。

## C-003 [FYI] 2026-10-08 13:55 — 报告格式
- `updated` 字段请写到分钟（例如 `2026-10-08 13:46`），reviewer 要靠它判断是否卡住。
- 阶段 0 已确认 DONE，可以继续阶段 1。阶段 1 结束（离线 GPU.0 转写跑通）时按计划设 WAITING_REVIEW。

## C-004 [NORMAL] 2026-10-08 14:10 — 导出产物没有 generation_config，generate 参数必须显式传
p1_export_*.log 显示 “The generation config will not be saved”（原 generation_config 里 temperature=1e-6 + do_sample=False 校验失败）。ov-fp16/ov-int8 目录下确实没有 generation_config.json，generate() 会退回 transformers 默认值（max_length=20、eos 可能不对），结果可能被**截断或停不下来**。
- 处理方式（二选一）：
  a) 从 models/hf 复制 generation_config.json，删掉 temperature/top_p/top_k 等采样字段后放进 ov-fp16/ 和 ov-int8/；或
  b) 每次 generate 都显式传 `do_sample=False, max_new_tokens=N, eos_token_id=[151643,151645], pad_token_id=151643`。
- 推荐 b，并且在 TorchBackend 和 OVBackend 里用**同一组参数**（parity 的前提）。离线验收用 max_new_tokens=512，流式按 r2t2 的 max_new_tokens 设置。

## C-005 [FYI] 2026-10-08 14:10 — 日志里的几条告警
- `incorrect regex pattern ... fix_mistral_regex`：这是 transformers 4.57.x 对 Qwen 系 tokenizer 的已知误报。但 LSP 回滚依赖 encode/decode，所以请做一次往返自检：用测试句 `之前有顾客自己带酒水也没加收钱或者不让喝。` 比较 HF tokenizer 和 openvino_tokenizer 的 encode 结果，确认 token id 完全一致、decode 能还原原文，结果写进 STATUS。
- `model of type qwen3_asr to instantiate a model of type fun_asr`：optimum-intel 内部的配置映射提示。以离线转写结果是否正确为准，转写对了就可以忽略。
- INT8 第一次导出死于 rich 进度条 `UnicodeEncodeError: 'gbk'` → 之后的后台命令统一设 `PYTHONIOENCODING=utf-8`（或 `set PYTHONUTF8=1`），免得 benchmark 跑到一半崩掉。
- **STATUS.md 已约 20 分钟没更新，last_ack 仍是 none**：导出完成属于里程碑，按协议应该写报告。请立即更新 STATUS（时间写到分钟），并回执 C-001~C-005。

## C-006 [BLOCKING] 2026-10-08 14:45 — 项目未达验收，DONE 不成立，立即重新打开
**协议问题**：STATUS 的 last_ack 仍是 C-000，说明 C-001~C-005 都没读；阶段 1、阶段 2 结束时也没有设 WAITING_REVIEW。从现在起每一步之前都必须重读本文件，**先逐条回执 C-001~C-006**（写进 STATUS，并说明各自怎么处理），再动手。

**验收没过**（plan_v2 阶段 4 验收第 5 条：RTF < 1 是硬指标）：实测 RTF 2.1~9.9，DONE 不能成立。STATUS 改回 `phase: 3, state: RUNNING`。

**根因已确认**：`models/ov-*/openvino_decoder_model.xml` 只有 `encoder_hidden_states, input_ids` 两个输入，没有 past/state。所以 greedy 每生成 1 个 token 都把 [prompt + 全部音频 + prefix] 整条序列重跑 28 层，一个 chunk 约 1.8 s。

**修正步骤（按顺序执行）**：
1. 重新导出带 KV cache 的版本，输出到**新目录**（不要覆盖旧产物）：
   `optimum-cli export openvino --model models/hf --task automatic-speech-recognition-with-past --trust-remote-code --weight-format fp16 models/ov-fp16-past`
   导出后确认 decoder 是 stateful（`model.is_stateful()` 或 IR 里有 ReadValue/beam_idx），并把输入输出清单写进 STATUS。如果 `-with-past` 对 qwen3_asr 不支持或导出失败 → 设 WAITING_REVIEW，贴报错，**不要自行换路线**。
2. greedy 改成：每个 chunk 先 `reset_state()` → 对整条序列做 1 次 prefill → 之后每步只喂 1 个新 token。也可以直接用 `OVModelForSpeechSeq2Seq.generate()`（带 C-004 的显式参数）。
3. **流式 golden（C-001）**：把 `third_party/Confucius4-R2T2/r2t2/r2t2_asr.py` 第 302-580 行的循环原样抽成与后端无关的 `streaming_asr.py`，接两个后端：TorchBackend（qwen_asr transformers 后端，CPU FP32）和 OVBackend。用参数组 A 跑出**逐 chunk** 的 golden。不要再用 qwen_asr 的流式逻辑，也不要只比最终文本。
4. 已发现的 bug：FP16 的最终文本少了句尾 `。`（INT8 有）；chunk 数是 21，audio.cpp 是 22（6.74 s / 0.32 s → 最后不足一个 chunk 的那段应该由 finish_streaming_transcribe 处理）。请对照 r2t2 源码查 finish/flush 逻辑。另外，逗号 `，` 是否应该出现以 TorchBackend golden 为准，不要拿 CER 4.55% “都是标点” 搪塞。
5. 重新跑 benchmark：报告 FP16 下 320 ms chunk 的 encode / prefill / decode 分项耗时和 RTF。

**检查点**：第 1 步完成后、第 3 步 golden 产出后，都要设 WAITING_REVIEW 等 reviewer 回复（最多 30 分钟）。只有 FP16 达到 RTF < 1、逐 chunk 与 TorchBackend 一致，才能标 DONE。

## C-007 [NORMAL] 2026-10-08 15:10 — with-past 导出的检查点验证项（写进 WAITING_REVIEW 报告）
with-past 导出日志里出现 `modeling_qwen3_asr.py:1021 if position_ids.ndim == 3 and position_ids.shape[0] == 4` TracerWarning：mrope 的位置分支可能在 trace 时被固化。带 KV 时 decode 步的 position 偏移一旦错了，会出现“前几个字对、后面越来越偏”。WAITING_REVIEW 报告里请提供：
1. 新 decoder 的输入输出清单，以及是否 stateful
2. 离线 test.wav、FP16、GPU.0：with-past greedy 与旧 no-past greedy 的 **token id 序列逐个对比**（应完全一致），外加两者的总耗时
3. 同一组对比在 CPU 上再跑一次（用来区分是 GPU 精度问题还是图本身的问题）
OV tokenizer IR 编译失败：同意用 HF tokenizer，不阻塞。

## C-008 [NORMAL] 2026-10-08 15:30 — 检查点 1 决策：批准继续，但先做 C-007 验证
**批准**：with-past 导出（57 ReadValue/Assign，stateful）及 backends.py / streaming_asr.py 的拆分方式符合要求，可以进入执行。注意 last_ack 还停在 C-006，C-007（15:10 发出）没有回执。请按以下顺序执行：
1. **先做 C-007**（预计十几分钟）：离线 test.wav，FP16，用 OVBackend(with-past) 和旧 no-past 各做一次 greedy，**token id 序列逐个对比**，GPU.0 和 CPU 各跑一次，记录耗时。
   - 完全一致 → 直接进入第 2 步，**不必**再停下来等待
   - 不一致 → 设 WAITING_REVIEW，贴出第一个分歧的位置和前后 token；重点排查 decode 步的 position_ids / mrope 偏移，以及 decode 步是否又传了 encoder_hidden_states、导致音频被重复拼接
   - 小提示：OpenVINO 的 Python Model 没有 `is_stateful()`，用 `len(model.get_sinks())>0` 或 `compiled.create_infer_request().query_state()` 判断即可（你们已经用 ReadValue 计数确认过了）
2. 跑 `streaming_asr.py --backend torch`（参数组 A）产出逐 chunk golden，再跑 `--backend openvino`（GPU.0，FP16 with-past），比对每个 chunk 的 `fixed_text`。
3. 到此设 WAITING_REVIEW（检查点 2），报告内容：两边逐 chunk 对照表、最终文本、chunk 数、OV 每个 chunk 的 encode/prefill/decode 耗时，以及 RTF。

## C-009 [FYI] 2026-10-08 15:50 — C-007 通过；检查点 2 报告的注意事项
C-007 结果确认：GPU.0 和 CPU 上 with-past 与 no-past 的 19 个 token 完全一致，KV/mrope 没问题，按 C-008 继续流式步骤即可。检查点 2 报告请注意：
1. **计时要先预热**：GPU 首次推理含动态 shape 的 kernel 编译（同一段音频的 encode 从 0.328 s 降到 0.095 s 就是这个效应）。benchmark 请先完整跑一遍不计时，第二遍再计。另外用 `CACHE_DIR`（ov_cache）避免每次启动重新编译。
2. **decode 72 ms/token 偏慢**（1.369 s / 19 token，含 prefill）。请把 prefill（整条 prompt 一次）和逐 token decode 分开计时。如果预热后单 token 仍 > 40 ms，检查 decode 步是否每次又传入了完整的 `encoder_hidden_states`（375×2048）；正常情况下 decode 步不应再处理音频。
3. **`language None<asr_text>`**：两个 OV 版本的输出都以 `language None` 开头。请确认 TorchBackend golden 是否同样输出 `language None`。如果 torch 输出 `language Chinese` → 说明 OV 端的 prompt 构造与 qwen_asr 不一致（检查 system/user 模板和 force_language），这会影响 r2t2 的中文去空格分支（`lang == "Chinese"`）。
4. 日志里中文是乱码（GBK 控制台）：报告里的文本请从 json/文件读出后用 UTF-8 写入 STATUS，方便核对。

## C-010 [BLOCKING] 2026-10-08 16:15 — 检查点 2 决策：音频被补齐到 30 s，先修这个，再谈其他优化
**结论**：流式框架和 22 个 chunk 的结构认可；但 RTF 2.0 和逗号分歧有同一个主因。

**证据**：c007 的编码器输出是 `(1, 375, 2048)`，可音频只有 6.74 s。Qwen3-ASR 音频 token 是 12.5 Hz，375 = 30 s × 12.5 → `WhisperFeatureExtractor` 用默认的 `padding="max_length"`（n_samples=480000）把**每个 chunk 都补齐到 30 s**。后果：
- 编码器每个 chunk 都在算 30 s 音频
- prefill 约 390 个 token，其中约 80% 是补齐出来的静音 token
- OV 每个 chunk 耗时平稳在 0.55–0.7 s（不随真实音频长度增长，说明成本被补齐部分主导）
- OV 与 torch 在 chunk 12/13/16/17 出现分歧（`，也没`、`加入` vs `加收`、逗号），很可能是两边送进模型的静音长度不同造成的

**修正**：
1. 特征提取统一走同一个函数（OV 和 torch 两个后端共用），参数对齐 qwen_asr 自己 processor 的调用方式：去看 `qwen_asr` 里 Qwen3ASRProcessor / transformers_backend 的 feature_extractor 调用（padding / truncation / return_attention_mask 怎么传）。要求：**不补齐到 30 s**，按真实长度出 mel；N_audio 用 qwen_asr 自带的 `_get_feat_extract_output_lengths`（或同名函数）从真实帧数算出。
2. 打印并写进 STATUS：6.74 s 全段的 mel 帧数、encoder 输出 token 数（应在 85 左右，不是 375）、prefill 总长度。
3. TorchBackend 的 `attention mask is not set` 告警：generate 请显式传 attention_mask。
4. 修完后重跑两个后端（参数组 A），给出逐 chunk 对照表（只列有差异的行即可）。
5. 计时：先预热一遍再计时；每个 chunk 拆成 mel / encode / prefill / decode（含 token 数）四段。目标是 OV FP16 GPU.0 下每个 chunk < 320 ms。
6. 句尾 `。`：两个后端都没有，CUDA 有。等 1-4 修完再看，如果仍然缺，对照 r2t2 的 `finish_streaming_transcribe`（max_new_tokens、`end_idx=max(1,…)`、`rollback_punctuation`）和 audio.cpp 的最后一个 chunk 逐项排查。优先级低于 1-5。

先不要上 INT8，也不要改 chunk 大小来凑 RTF：先把 FP16 320 ms 的真实成本测清楚。修完后设 WAITING_REVIEW（检查点 3）。

## C-011 [BLOCKING] 2026-10-08 16:35 — 检查点 2 选项 a/b/c 全部否决；先执行 C-009 和 C-010
**协议**：你 16:30 写 STATUS 时 last_ack 还是 C-008，而 C-009（15:50）和 C-010（16:15）在那之前就已经发出。按协议，**写 STATUS 之前必须重读 CORRECTIONS.md**。请先回执 C-009~C-011。

**决策**：
- **选项 a（接受偏差，DONE）否决**：偏差的根因你自己的报告里已经写出来了 —— OV 的 N_audio=375，torch 的 N_audio=52。两边送进模型的输入根本不一样，这不是“模型行为差异”，是 OV 前端把音频补齐到 30 s（C-010）造成的 bug。
- **选项 b（INT8）、选项 c（调 force_language / max_new_tokens 凑出 `。`）否决**：都是在错误的输入上调参。
- **chunk=1000 ms 的 RTF 0.736 不算验收**：验收口径是参数组 A（320 ms）。1000 ms 的数字可以作为附加数据保留。

**现在执行（按顺序）**：
1. **C-010 第 1-4 条**：OV 和 torch 共用同一个特征提取函数，不补齐到 30 s；N_audio 按真实长度算（6.74 s 全段应在 85 左右）。修完后两个后端重新逐 chunk 对比。预期逗号和 `加入/加收` 的分歧会消失；如果没有消失，贴出第一个分歧 chunk 两边的 prompt 长度和 N_audio。
2. **C-009 第 2 条**：decode 298 ms / 约 5 token ≈ 60 ms/token，太慢。检查 decode 步是否每一步都重新传入了完整的 `encoder_hidden_states`（这样音频会被重复处理）；decode 步应只传新 token（以及该 IR 要求的最小占位）。修后单 token 应明显低于 40 ms。
3. 预热后重新做分项 benchmark（mel / encode / prefill / decode + token 数），参数组 A 320 ms。粗估：prefill 从约 390 token 降到约 100 token，prefill 应降到 1/3 以下；加上 decode 修复，320 ms chunk 有希望 < 320 ms。
4. 设 WAITING_REVIEW（检查点 3）。`。` 问题仍按 C-010 第 6 条放在最后处理。

## C-012 [NORMAL] 2026-10-08 16:55 — 检查点 3 决策：走 INT8 权重压缩（路径 a），并补测参数组 B
**认可**：30 s 补齐已修复；22/22 chunk 与 torch 逐字一致；decode 步改用 tiny ehs —— 做得好。（注意：STATUS 里 `updated: 17:30` 比实际时间快了约 45 分钟，请用 `date /t & time /t` 的实际时间。）

**分析**：decode 占 75%。1.7B FP16 每步都要读一遍约 3.4 GB 权重（含 tied lm_head），是带宽瓶颈。64 ms/token 大约是 Panther Lake 内存带宽下限的 2 倍。权重减半，decode 基本就减半。
- **(a) INT8 → 批准，作为主路径。**
- **(b) window attention 复用 → 暂不做**：encode 只占 5%，收益太小。
- **(c) 改用 640/1000 ms chunk → 不能作为验收**：这是产品层面的取舍，由用户决定。数据保留在报告里即可。

**执行**：
1. 导出到新目录：`optimum-cli export openvino --model models/hf --task automatic-speech-recognition-with-past --trust-remote-code --weight-format int8 models/ov-int8-past`。
2. INT8 跑参数组 A，与 torch golden **逐 chunk 对比**（报告 diff 数和最终文本 CER），预热后做分项 benchmark，报告 ms/token。
3. 如果 INT8 在 320 ms 下仍 RTF ≥ 1，再试 `--weight-format int4 --group-size 128 --ratio 1.0 --sym`（目录 `models/ov-int4-past`），同样给出逐 chunk 对比和 CER。INT4 的精度门槛：CER ≤ 1%，且不出现内容字错误（标点差异可以列出来，不算失败）。
4. **补测参数组 B**（plan_v2 阶段 2 要求的官方默认：chunk 160 ms，unfixed_chunk_num=0，unfixed_token_num=1，max_new_tokens=4）：FP16 和 INT8 各跑一次，torch golden 也要有。官方 k=1 时每个 chunk 只回滚 1 个 token，而参数组 A 的 k=5 导致每个 chunk 要重新生成约 5 个 token，所以参数组 B 每个 chunk 的 decode 量会小很多。报告 RTF。
5. 汇总表：{FP16, INT8, (INT4)} × {参数组 A 320 ms, 参数组 B 160 ms}，列出 RTF / ms per token / 与 golden 的 diff 数 / CER，640/1000 ms 作为附加数据。
6. 完成后设 WAITING_REVIEW（检查点 4）。`。` 问题在检查点 4 之后处理。

## C-013 [BLOCKING] 2026-10-10 08:55 — 用户已定最终部署方案：INT8 + 640 ms chunk（取代 C-012）
状态显示你从 10-08 16:46 起一直停在检查点 3，C-012 没有执行。用户现已拍板，**C-012 作废，以本条为准**。先回执 C-012（作废）与 C-013。

**最终验收口径**（取代 plan_v2 阶段 4 第 5 条的 320 ms 口径）：
- 模型：INT8 权重压缩，with-past stateful，设备 `GPU.0`
- 流式参数：**chunk_size_ms=640**，unfixed_chunk_num=2，unfixed_token_num=5，max_new_tokens=32，rollback_punctuation=False（其余与参数组 A 相同）
- 不做 INT4，不做 window attention 复用，参数组 B 不再要求

**执行步骤**：
1. 导出：`optimum-cli export openvino --model models/hf --task automatic-speech-recognition-with-past --trust-remote-code --weight-format int8 models/ov-int8-past`（设 `PYTHONUTF8=1`，日志写 status/logs/c013_export_int8_past.log）。确认 decoder 是 stateful。
2. Golden：TorchBackend（CPU FP32）以 640 ms 参数跑出逐 chunk golden（`reports/stream_torch_640.csv`）。
3. 精度：INT8-past OVBackend 640 ms 与 torch golden 逐 chunk 对比。要求：最终文本内容字完全一致，CER ≤ 1%；有差异就把差异 chunk 列出来。若 INT8 出现内容字错误 → 设 WAITING_REVIEW（备选：encoder 保持 FP16、仅 decoder INT8）。
4. 性能（先预热）：640 ms 下分项 mel / encode / prefill / decode / ms-per-token，RTF。**硬指标：RTF < 1，目标 ≤ 0.8**（给系统其它负载留余量）。同时给出 FP16-past 640 ms 的同口径数字作对照（已有 1.166，预热后重测）。
5. 长音频：把 test.wav 首尾拼接 4 次（中间插 0.5 s 静音，约 29 s），INT8 640 ms 流式跑一遍，报告每个 chunk 耗时随音频长度的变化，以及 RTF 越过 1 的位置（若有）。据此在 README 写明建议的最大单句长度（VAD 切句阈值）。
6. 句尾 `。`：C-010 第 6 条，现在处理。对照 r2t2 `finish_streaming_transcribe` 和 audio.cpp 最后一个 chunk 排查；若确认是 r2t2 官方逻辑本身就不出 `。`（torch golden 也没有），写明结论即可，不要为了凑 `。` 改算法。
7. 交付：
   - 部署入口 `transcribe_stream.py`：默认 `--model models/ov-int8-past --device GPU.0 --chunk-ms 640`，输入 wav 文件，逐 chunk 打印增量文本与耗时；启动时断言 GPU.0 是 Intel，启用 CACHE_DIR。
   - 更新 README：最终配置、实测性能表（INT8 vs FP16，640 ms）、精度结果、长音频限制与 VAD 建议、运行命令。旧的 no-past 实现标注为弃用。
8. 完成后设 WAITING_REVIEW（最终验收）。只有 reviewer 回复确认后才能标 DONE。

## C-014 [NORMAL] 2026-10-10 09:00 — 长音频（>30 分钟）OOM 验证 + 分段机制（并入 C-013，放在第 5 步之后、第 7 步交付之前）
**背景**：用户反馈 CUDA（audio.cpp）方案测 >30 分钟音频时报 OOM。reviewer 分析认为根因在算法层，OV 版有同样问题：
- r2t2 的 `streaming_transcribe` 每个 chunk 都把**从开头累积的全部音频**加上全部已确认文本重新 prefill。30 分钟 ≈ 22,500 个音频 token + 约 7,000 个文本 token ≈ 3 万 token。
- 估算：KV cache 28 层 × 2 × 8 头 × 128 × 2 B ≈ 112 KB/token → 约 3.4 GB；如果 attention 没走融合 kernel，单层 score 矩阵 16 头 × 30k² × 2 B ≈ 29 GB → 必然 OOM。在 OOM 之前，每个 chunk 的耗时也会随长度增长（prefill 近似线性到平方），实时性早就崩了。
- 官方并不这样用：`ws_server.py` 用 FireRedVAD 切句（max_speech_frame=2000，即 20 s），无 VAD 时 60 s soft reset、90 s hard reset（`finish_streaming_transcribe` 后 `init_streaming_state` 重开）；`r2t2_asr.py` 里另有 `streaming_transcribe_no_reset` 的滚动窗口（累积超过 16 s 丢弃最早 8 s 及对应文本）。

**任务**：
1. **复现（OV 现实现，不分段）**：构造 ≥ 30 分钟测试音频（优先用真实中文长音频，从 hf-mirror 找公开数据集拼接；找不到就用 test.wav 拼接，中间插 0.3–1.0 s 随机静音，并在报告注明）。INT8-past、640 ms、GPU.0 流式跑，每个 chunk 记录：已累积音频秒数、prefill token 数、chunk 耗时、Python 进程 RSS、GPU 共享显存（`Get-Counter '\GPU Process Memory(*)\Shared Usage'` 或 `\GPU Adapter Memory(*)\Shared Usage`）。
   - **设熔断**：单个 chunk 耗时 > 20 s、GPU 共享显存 > 14 GB 或系统可用内存 < 4 GB 时主动停止，不要把机器拖死。报告停在多少秒音频、是 OOM 报错还是熔断，并把增长曲线外推到 30 分钟。
   - 同时用 CPU 设备跑一小段（到 120 s 即可），区分是 GPU 插件问题还是算法本身的增长。
2. **修复：实现分段**（放进 `streaming_asr.py`，与后端无关，TorchBackend/OVBackend 共用）：
   - 默认策略照官方 ws_server：有静音就切句（先用简单能量 VAD 或 `fireredvad`，pip 可装就用）；无静音时累积音频达到 `max_segment_sec`（默认 30 s，可配置）强制 `finish_streaming_transcribe` → 重新 `init_streaming_state`，已确认文本追加到全局 transcript。
   - 备选：滚动窗口模式，照 `streaming_transcribe_no_reset` 的 16 s / 8 s 逻辑。选一种做默认，另一种可选，在 README 说明取舍。
3. **验证修复**：同一条 ≥ 30 分钟音频用分段模式跑完全程：内存/显存曲线必须平稳（不随时长增长），全程 RTF < 1，每个 chunk 耗时有上界；输出完整 transcript，并抽查切句边界有没有丢字或重复字。
4. **报告**写进 STATUS 的一个独立小节“长音频 / OOM”：复现结论（OV 是否也会 OOM、在多少秒）、两条曲线（分段前 / 分段后）的关键数据点表、分段后的 RTF 与峰值内存。`transcribe_stream.py` 默认开启分段。

## C-015 [BLOCKING] 2026-10-10 09:15 — 最终验收决策：C-013 主体通过，但暂不能 DONE
**通过的部分**：INT8-past 导出、GPU.0、640 ms，与 torch golden 去标点 CER=0%，RTF 远低于 1，transcribe_stream.py 入口 —— 认可。

**不能 DONE 的原因**：
1. **C-014 没有执行**：last_ack 是 C-013，但 C-014（09:00）在你写 STATUS 之前就已经发出。长音频 OOM 验证和分段机制是交付的必要部分，请先回执 C-014、C-015，然后执行 C-014。
2. **长音频结论错误**：28.5 s 测试的“整体 RTF 0.730”是平均值，掩盖了每个 chunk 的增长。按你给的累计时间算，每个 chunk 的耗时：chunk 1-10 平均约 0.37 s，10-20 约 0.46 s，20-30 约 0.49 s，30-40 约 0.52 s。到 25 s 时**瞬时 RTF 已约 0.81**（超过 0.8 目标），线性外推约 **40 s 会越过 1**。所以“未发现拐点”的结论不成立：报告要改用**逐 chunk 的瞬时 RTF**（chunk 耗时 / 0.64 s），README 中“单句 ≤ 20 s”的建议请依据这个数据重新给出。C-014 的分段默认阈值 `max_segment_sec` 也要依据这条曲线来定（建议瞬时 RTF ≤ 0.8 对应的时长，预计约 20 s）。
3. **长音频“最后一段被 final_flush 截断”= 丢字 bug**：请贴出 28.5 s 测试的完整最终文本，与预期的 4 遍原句逐字对比，查明是 max_new_tokens 不够还是 flush 逻辑问题，并修复。分段之后每段都会走 finish，这个 bug 不修，每段末尾都会丢字。
4. **数字口径不一致**：同一配置下 RTF 先后报了 0.444 / 0.517 / 0.491，分项表平均 chunk 耗时 318.8 ms 又对应约 0.50。请定一个口径（预热后连续跑 5 次，取中位数），所有表格统一使用。
5. **追加只确认（append-only）检查**：transcribe_stream 的输出里，chunk 10 显示 `…不让喝。`，FINAL 却是 `…不让喝`。请确认这个 `。` 当时是在已确认（fixed）部分还是未确认的尾巴里。如果已确认的文本在后面被删掉，就违反了 R2T2 “已提交文本不改”的核心语义，必须修复；如果只是未确认的尾巴，就在输出里把 fixed 和 tail 分开打印，免得误导。

完成 C-014 和以上 5 条后，再设 WAITING_REVIEW（最终验收第 2 轮）。

## C-016 [NORMAL] 2026-10-10 10:10 — C-014 改用真实 61 分钟录音作为主测试音频
用户提供了真实录音，已推送到 `test_audio/260902_SPE_audio.wav`（117,478,136 B，16 kHz / 单声道 / 16-bit，**61.2 分钟**，内容为中文会议/演讲）。C-014 按下面的方式调整（你已构造的拼接音频保留为辅助样本）：
1. **复现（不分段）**：用这条录音的前段跑 INT8-past / 640 ms / GPU.0，熔断条件照 C-014。逐 chunk 记录：累积秒数、prefill token 数、chunk 耗时、瞬时 RTF、进程 RSS、GPU 共享显存。报告第一次瞬时 RTF > 0.8、> 1 的音频位置，以及最终停在哪里（OOM 报错还是熔断），并把曲线外推到 30 / 61 分钟。
2. **分段模式完整跑完 61 分钟**（主验收）：报告总耗时、整体 RTF、瞬时 RTF 的 P50/P95/最大值、峰值 RSS / GPU 共享显存（必须平稳，不随时长增长）、分段数量和平均段长。完整 transcript 保存为 `reports/spe_61min_transcript.txt`（UTF-8，每段一行并带起止时间）。
3. **质量抽查**（没有人工标注，所以做以下检查）：
   - 选 3 段各 2-3 分钟（开头、中间、结尾），用 TorchBackend 离线整段转写作为参照，与流式分段输出算 CER，报告数值和典型差异。
   - 检查分段边界：列出 10 个切点前后各 1 句，确认没有丢字/重复。
   - 检查幻觉：有没有长时间静音或噪声段输出了重复文本（官方 ws_server 有 hallucination reset 逻辑，可以参考）。
4. 长测试都在后台跑，日志写到 `status/logs/c016_*.log`，期间至少每 30 分钟更新一次 STATUS 心跳。

## C-017 [BLOCKING] 2026-10-10 10:40 — 更正 C-016：61 分钟录音是**英文**；质量判定改由 reviewer 用云端 ASR baseline 做
1. **更正**：C-016 里写的“中文会议/演讲”是错的。`260902_SPE_audio.wav` 是**英文**的 Intel 业务会议（reviewer 已用 MiniMax 云端 ASR 抽样确认）。处理时：
   - **不要设 force_language=Chinese**，用 `language=None`（自动）或 `English`。prompt 里的 `language XXX<asr_text>` 前缀照 r2t2 原逻辑处理。
   - r2t2 的中文去空格分支对英文不生效，这是正常的；注意英文单词之间的空格不能被吃掉。
   - 指标改为 **WER**（英文词错误率：统一小写、去标点、数字保持原样），不再用 CER。
2. **质量判定方式调整**：reviewer 正在用 MiniMax 云端 ASR（asr-1.0）为整段 61 分钟生成独立 baseline，由 reviewer 来对比。C-016 第 3 条的 TorchBackend 离线抽查**改为可选**（时间够就做开头一段，作为同模型参照）。你只需交付：
   - `reports/spe_61min_transcript.txt`：UTF-8，每段一行，格式 `[起始秒-结束秒] 文本`（秒数保留 1 位小数，对应原始音频的绝对时间）
   - `reports/spe_61min_segments.json`：每段的 start / end / text / 该段的 chunk 数与耗时
3. C-014 / C-016 的其余部分不变：不分段复现 OOM 并外推曲线、分段模式跑完 61 分钟、内存/显存平稳、RTF 统计、切点检查、幻觉检查。

## C-018 [NORMAL] 2026-10-10 09:45 — C-014 复现结果解读 + 分段策略修正（在真实 61 分钟英文录音上执行）
**reviewer 对 c014_01_oom_repro.log 的解读**（请据此写进 STATUS 的“长音频 / OOM”小节）：
- 不分段时**不是 OOM，而是在约 118-120 s 处崩溃**：`Add ... Argument shapes are inconsistent`，此时 n_audio≈1531。audio_config 里 `max_source_positions=1500`，1500 × 80 ms = 120 s，即音频编码器的位置编码上限。请确认这一点（打印崩溃前一个 chunk 的 n_audio 与编码器输入帧数），并把结论写清楚：**OV 版不分段时 120 s 必然失败**；CUDA 版 >30 分钟的 OOM 是同一根因（整段累积）的另一种表现。
- 实时性约在 **46 s** 处已经失守（chunk 耗时 0.83 s > 0.64 s），80 s 以后单 chunk 耗时 1.7-2.2 s（瞬时 RTF ≈ 3）。RSS 基本平稳（约 4-4.8 GB），说明瓶颈是计算量和位置编码上限，不是内存。
- 日志里的 text 截断在 30 个字符，后面看不出是否还在增长。以后记录 text 时请记全长（或至少记录长度）。

**分段策略修正**（c014_03_seg_verify.log 显示是预先按固定 30 s 切成 61 段）：
1. **不要按固定时长盲切**，会把单词或句子从中间切断。改为：每段累积到 `min_segment_sec`（默认 12 s）后，在 `[12 s, max_segment_sec]` 范围内找静音点切（100 ms 帧能量最低点，或用 VAD）；到 `max_segment_sec` 仍无静音才强制切。
2. `max_segment_sec` 默认改为 **20 s**：你的数据显示 30 s 段的平均 RTF 是 0.72-0.76，段尾的瞬时 RTF 已接近 1，留的余量不够。
3. 切点必须走 `finish_streaming_transcribe` 把尾巴 flush 出来（C-015 第 3 条的丢字 bug 要先修好），已确认文本追加到全局 transcript，新段 `init_streaming_state` 时 `unfixed_chunk_num` 照官方 ws_server 的做法设为 0。
4. 用修正后的策略在 **`test_audio/260902_SPE_audio.wav`（英文，按 C-017）** 上跑完整 61 分钟，交付 C-017 要求的 transcript 和 segments.json，并报告 RSS/GPU 共享显存曲线、瞬时 RTF 的 P50/P95/最大值。

## C-019 [BLOCKING] 2026-10-10 10:50 — 61 分钟英文质量不达标（WER 58%），先定位根因，暂停交付
**reviewer 判定结果**（`spe_61min_transcript.txt` 对比 MiniMax 云端 asr-1.0 baseline）：
- 整体 WER **58.3%**（S=3785 / D=1977 / I=629），hyp 9,616 词，ref 10,964 词。判定线是 ≤12%，**不达标**。
- 226 段中 **30 段（13%）出现重复循环**，例如 600-660 s 附近输出 `really really really …` 几十遍、`how we like the way we like the way …`。
- **32 段（14%）丢字**，输出词数不到 baseline 的 60%（如 1200 s 段的开头 “We have to continue to support that…” 丢失）。
- 去掉这两类后，剩下 165 个“干净”段的 WER 中位数仍是 **51.7%**，所以是系统性问题；另有专有名词替换，例如 agentic → quantum，Crescent Island 段整段乱码。
- RTF：P50 0.587 / P95 0.699 / 最大 1.126（性能本身 OK）。

Qwen3-ASR-1.7B 的英文能力远好于这个水平，之前的 parity 只在 6.7 s 中文样本上做过。请按以下**诊断矩阵**定位问题出在哪一层。取两段音频：**A = 600-660 s**（循环最严重）、**B = 1200-1260 s**（相对较好），各用 ffmpeg/soundfile 裁出来：
| # | 配置 | 用来区分 |
|--|--|--|
| 1 | TorchBackend CPU FP32 **离线**整段转写（qwen_asr transcribe，language 自动） | 模型本身的英文能力 |
| 2 | OV FP16-past **离线**整段 greedy | OV 移植是否正确（对比 #1） |
| 3 | OV INT8-past **离线**整段 greedy | INT8 量化的影响（对比 #2） |
| 4 | OV INT8-past **流式**（640 ms，2/5/32），单段、不分段 | 流式 LSP 算法的影响（对比 #3） |
| 5 | TorchBackend **流式**（同参数） | 流式本身是否就会这样（对比 #4） |
每个配置都输出全文；reviewer 会用 baseline 算 WER，你也可以用 jiwer 自己先算。

同时检查以下几个可疑点并报告：
- **语言前缀**：之前的输出以 `language None<asr_text>` 开头。正常情况下应该是模型自己识别出的语言（如 `language English`）。请打印 #1 和 #2 的原始输出（包含 `<asr_text>` 之前的部分），对比 prompt 是否与 qwen_asr 的 chat template 完全一致（system / user / audio 占位 / assistant 前缀）。如果 OV 侧把字符串 "None" 拼进了 prompt，这就是 bug。
- **EOS / 停止条件**：循环说明 greedy 没有在该停的地方停。确认 eos_token_id 包含 151643 和 151645，并且 decode 循环每一步都检查 EOS。
- **前缀回灌**：英文的 BPE token 较短，`unfixed_token_num=5` 只能回滚约 1-2 个词。确认 rollback 之后传给 prompt 的 prefix 没有被重复拼接（比如 prefix 被加了两次，或 `language XXX<asr_text>` 标签在 prefix 里出现了多次）。
- **防循环兜底**（修根因之后再加）：参考 `ws_server.py` 的 hallucination reset 逻辑，检测到同一 n-gram 连续重复时强制 finish 并 reset 本段。
完成诊断矩阵后设 WAITING_REVIEW，贴出 5 个配置在 A/B 两段上的输出文本（各取前 80 个词）。

## C-020 [BLOCKING] 2026-10-10 11:05 — 诊断矩阵加入 CUDA（audio.cpp）版，与 OV 用同一套切段做全长对比（并入 C-019）
目的：判断 58% WER 是 **OV 移植 / INT8 / 我们的流式与分段代码** 的问题，还是 **模型本身或 R2T2 流式算法在英文长音频上** 的问题。CUDA 版（audio.cpp + GGUF Q8_0，RTX 5050）是独立实现，是最好的对照组。原 CUDA 项目目录仍然只读，输出全部写到 `confucius4-openvino/reports/cuda/`。

**准备**：按 `reports/spe_61min_segments.json` 的 start_s/end_s，把 61 分钟录音切成 226 个 wav（`reports/seg_wavs/seg_000.wav` …），**OV 和 CUDA 都用这同一套切段**，排除切段差异的影响。

**全长对比（4 份 transcript，格式同 C-017：`[start-end] text`，时间为原始音频的绝对时间）**：
| 文件 | 配置 |
|--|--|
| `spe_61min_transcript.txt`（已有） | OV INT8-past，流式 640 ms，2/5/32 |
| `cuda/spe_cuda_stream.txt` | audio.cpp CUDA，`--mode streaming`，`--session-option chunk_size_ms=640 unfixed_chunk_num=0 unfixed_token_num=5 max_tokens=32`（与 OV 新段的参数一致），每段单独一个 session |
| `cuda/spe_cuda_offline.txt` | audio.cpp CUDA，`--mode offline`，`--batch-audio-dir reports/seg_wavs`，每段整段转写 |
| `spe_ov_offline.txt` | OV INT8-past **离线**整段 greedy，每段一次 |
- audio.cpp 的命令行参考原来生成 `stream_test.log` 的调用（`--task asr --family confucius4_r2t2 --model models/r2t2-q8_0.gguf --backend cuda`），语言参数保持自动；把实际用的完整命令写进 STATUS。
- 每份记录总耗时和 RTF。CUDA 跑在 dGPU、OV 跑在 iGPU，**请顺序运行，不要并行**，避免互相干扰计时。

**单段细查（C-019 的 A=600-660 s、B=1200-1260 s）**：在 C-019 的 5 个配置基础上，增加 #6 CUDA 流式、#7 CUDA 离线，共 7 个配置。每个配置贴出原始输出（含 `language XXX<asr_text>` 前缀）的前 80 个词。

**可选（时间允许再做）**：CUDA 版**不分段**直接流式跑 61 分钟原始录音，复现用户反馈的 OOM。熔断条件：单 chunk > 20 s 或显存 > 7.5 GB 主动停止。报告停在多少秒，以及是 OOM 还是像 OV 一样在约 120 s 处因位置编码上限报错。

**交付后设 WAITING_REVIEW**。reviewer 会用 MiniMax baseline 对 4 份全长 transcript 逐一算 WER，按下表判定问题出在哪一层：
- CUDA 离线好、OV 离线差 → OV 移植或 INT8 的问题
- 两边离线都好、两边流式都差 → R2T2 流式算法或参数在英文上的问题
- OV 流式明显差于 CUDA 流式 → 我们 `streaming_asr.py` / `seg_stream.py` 的实现 bug
- 四份都差 → 模型或切段本身的问题

## C-021 [BLOCKING] 2026-10-10 11:20 — 诊断已定位到 OV 音频编码器（长于约 8 s 的输入），优先修这个；C-020 降为后置
**c019_diagnose.log 结论**：#1 Torch 离线、#5 Torch 流式在 A/B 上都很干净（与 MiniMax baseline 基本一致），所以 **模型本身和 R2T2 流式算法在英文上没有问题**。OV FP16 离线（B 段输出为空，只有 `language None<asr_text>`）、OV INT8 离线（`the long, the long…` 循环）、OV INT8 流式（`hardware, hardware…` 循环）都坏 → 问题在 **OV 移植**，而且 FP16 也坏，所以不是 INT8 的锅。

**reviewer 的主要怀疑：导出的 encoder IR 把窗口/分块逻辑固化成了 trace 时的形状**：
- Qwen3-ASR 的 audio encoder 会把 mel 按 `n_window`（50 → 每块 100 帧）分块做卷积下采样，并在 `n_window_infer=800` 帧的窗口内做窗口化注意力（cu_seqlens / 分块 attention mask），这些是 Python 层面依赖数据的逻辑（导出日志里有 TracerWarning）。
- 证据：① 6.7 s（674 帧，小于 800，只有一个窗口）与 torch 22/22 一致；② 12-20 s 的分段和 60 s 的片段全坏；③ 不分段时恰好在 n_audio=1500 处报 shape 错误 —— 正确实现的窗口化 encoder 不应该撞到全局 1500 位置的上限。

**执行**：
1. **验证**（约 15 分钟）：从 61 分钟录音里取 4/8/10/12/16/20/30/60 s 的片段，分别过 torch `model.thinker.audio_tower`（或 qwen_asr 里对应的 audio encoder forward，FP32）和 OV encoder IR（FP16 与 INT8），比较输出的 token 数和逐 token cosine（mean/min）。预期：≤8 s 时 cosine > 0.99，>8 s 时明显下降。把表格写进 STATUS。
2. **对照源码**：读 `qwen_asr/core/transformers_backend/modeling_qwen3_asr.py` 的 audio encoder forward（分块、padding、位置编码是否按块重置、cu_seqlens / 窗口 mask 的构造），对照 optimum-intel 的 qwen3_asr 导出配置与 patcher，找出被固化的部分。
3. **修复方案（按优先级）**：
   a) **在 Python 侧做分窗**：重新导出一个只处理**单个 800 帧窗口**（或单个 100 帧分块 + 单窗口 transformer）的 encoder IR，在 Python 里照 qwen_asr 原逻辑循环切窗、补齐、拼接输出。窗口形状固定后，对 GPU 也更友好（可以静态 shape）。
   b) 或者重新导出，把窗口 attention mask / cu_seqlens 作为模型输入，由 Python 计算后传入。
   c) 选定方案后，用第 1 步的表复测：所有长度 cosine > 0.99，且 n_audio 与 torch 完全一致。
4. 修好后依次复跑：C-019 的 B 段 #2/#3/#4（应与 #1/#5 一致）→ 61 分钟分段流式全长 → 交付新的 `spe_61min_transcript.txt`（旧文件改名为 `_v1` 保留）。
5. **C-020 降为后置**：encoder 修好后，如果 61 分钟的 WER 仍 > 12%，再跑 CUDA 全长对照；如果已经达标，CUDA 只需跑 A/B 两段的 #6/#7 作为参照，以及可选的 CUDA 不分段 OOM 复现（这个用户关心，有时间就做）。
6. 当前的 #5 B 段（torch 流式）跑完即可，不用重跑。修复方案选定（第 2 步结束）时设 WAITING_REVIEW 简要汇报，**最多等 15 分钟**，超时就按方案 a 执行。

## C-022 [BLOCKING] 2026-10-10 12:00 — 检查点决策：诊断结论认可一半；请先读 C-021，转去修 encoder
你的 last_ack 是 C-020，但 **C-021（11:20）你还没读**，那里已经给出下一步。请先回执 C-021、C-022。

**认可**：7 配置矩阵清楚地表明 Torch 离线/流式、CUDA 离线/流式都干净，**OV 离线和流式坏** → 问题在 OV 移植，FP16 同样坏，所以与 INT8 无关。prompt 一致、EOS 正确、没有把 "None" 拼进 prompt —— 这些排查都有价值。

**不认可**：“29 s / N_audio≥378 阈值”和“分段 ≤20 s 所以安全”。你自己的数据就反驳了它：
- 61 分钟分段流式每段 ≤20 s，WER 却有 58%，13% 的段循环，干净段 WER 中位数 52%。所以 20 s 以下同样是坏的。
- 你的表里 **N_audio 随音频长度不单调**：29.0 s→363，29.2 s→380，30.0 s→375；60 s 实际 750，公式是 780。正确的 encoder 输出长度应该严格单调并等于公式值，这正是 C-021 怀疑的“encoder 分块/窗口逻辑在导出时被固化”的直接证据。29 s 附近的崩溃只是这个 bug 最极端的表现。
- 10 s 以下的短段离线也只输出 4-9 个 token，同样指向 encoder 输出不对。

**现在执行**：
1. **停掉 `ov_offline_full.py`**（已知会坏，跑完也没有信息量，还占着 iGPU）。CUDA 全长两份（流式 + 离线）**继续在后台跑**：它们在 dGPU 上，不干扰 iGPU，结果可以作为“这个模型在本录音上能达到的 WER”参照。
2. 立即执行 **C-021 第 1 步**：4/8/10/12/16/20/30/60 s，torch audio_tower 与 OV encoder（FP16）逐 token cosine + token 数（与公式值对比）。
3. 然后执行 C-021 第 2-4 步（读 modeling_qwen3_asr 的 encoder forward → 方案 a：Python 侧分窗 + 单窗 IR → 复测 cosine → 复跑 A/B → 61 分钟全长）。
4. 防循环兜底（hallucination reset）等 encoder 修好后再加，**不要用它来掩盖 encoder 的 bug**。
5. CUDA 全长两份跑完时，把文件放到 `reports/cuda/`，reviewer 的监控会自动拉取并算 WER。

## C-023 [BLOCKING] 2026-10-10 12:20 — encoder IR 在所有长度上都错，decoder 没问题；按方案 a 重新导出 encoder
**结论（来自 c021_encoder_compare / c021_chunked_test / c021_hybrid_offline）**：
- 导出的 encoder IR **全长度都错**：4 s 时 cosine 只有 0.64，60 s 降到 0.29；token 数也不对（4 s：OV 50 vs torch 52；60 s：750 vs 780）。所以 6.7 s 中文样本当初的一致是“碰巧”：短句的偏差没大到让 decoder 出错。
- token 数规律说明了原因：torch 是**按 100 帧一块**分块卷积，每块产出 13 个 token（400 帧 → 4 块 × 13 = 52）；OV IR 则是对整段做一次卷积（400/8 = 50），位置编码也是全局的（因此在 1500 处撞上限）。也就是说，optimum 导出时没有走 qwen_asr 的分块路径。
- 你的 chunked_test（token 数已对齐）cosine 仍只有 0.38-0.53 → 还缺**每块内独立的位置编码**和/或**窗口化注意力（cu_seqlens，n_window_infer=800 帧 ≈ 104 token）**。
- **hybrid（torch encoder + OV decoder）输出干净** → OV decoder（INT8-past）和流式代码基本没问题，问题只在 encoder。

**执行**：
1. **先把 hybrid 的 61 分钟全长跑完**，交付 `reports/spe_hybrid_offline.txt`（格式同 C-017）。reviewer 会算 WER，作为“encoder 正确时我们这套 decoder 能达到的水平”的参照。STATUS 已超过 30 分钟未更新，请立即更新，并回执 C-021~C-023。
2. **重新导出 encoder（方案 a）**，不要再用 optimum 的 encoder IR：
   - 照抄 `modeling_qwen3_asr.py` 里 audio encoder forward 的逻辑，写一个 wrapper `nn.Module`，只处理**一个注意力窗口**：输入固定为 `[8, 128, 100]`（8 个 100 帧分块，不足的补零）外加有效帧数；内部按原逻辑做分块卷积、加**每块独立的**位置编码、窗口内注意力、投影到 2048；输出 `[104, 2048]`（窗口的有效 token 数在 Python 侧用原公式裁剪）。
   - 用 `ov.convert_model(wrapper, example_input=...)` 导出，静态 shape 即可，保存为 `models/ov-encoder-window/`（FP16；INT8 等精度验证通过后再考虑）。
   - Python 侧：mel 按 800 帧切窗 → 每窗切成 8 块 → 调 IR → 按原公式裁掉补齐部分 → 拼接。最后一窗不足时补零并裁剪。
   - 如果原模型的注意力窗口和分块方式与上面描述不同，**以源码为准**，并在 STATUS 里写明实际逻辑。
3. **验收新 encoder**：重跑 C-021 第 1 步的表（4…60 s），要求每个长度 **token 数与 torch 完全一致、cosine mean > 0.99、min > 0.95**。达标后：B/A 段 #2/#3/#4 复跑（应与 #1/#5 一致）→ 61 分钟分段流式全长 → 交付 `spe_61min_transcript.txt`（旧文件改名为 `_v1`）。
4. **性能**：hybrid 里 torch encoder 一次要 500-670 ms，流式不可能用它，只作为参照。新 encoder IR 在 GPU.0 上要给出每窗耗时，并重测 640 ms 流式的 RTF（仍按 C-013 口径：RTF < 1，目标 ≤ 0.8）。
5. CUDA 全长两份继续在后台跑，跑完放到 `reports/cuda/`。

## C-024 [BLOCKING] 2026-10-10 12:45 — 检查点决策：Hybrid 质量达标（WER 9.07%），但还不能交付；继续 C-023 导出窗口 encoder
**reviewer WER（对比 MiniMax baseline）**：
| transcript | WER | 说明 |
|--|--:|--|
| OV 流式 v1（旧 encoder） | 58.3% | encoder 坏 |
| OV 离线（旧 encoder） | 75.3% | encoder 坏 |
| **Hybrid 离线（torch encoder + OV decoder）** | **9.07%** | ✅ 低于 12% 判定线；窗口 WER P50 6.6% |
- 剩下几个高 WER 窗口（36 分、46 分处 62%/56%）几乎全是插入（I=132/135，S/D 个位数）。核对原文后确认是 **MiniMax baseline 在 Q&A 段漏了几段**（如 2204-2225 s、2823-2846 s），Hybrid 输出的是真实语音，所以实际 WER 比 9% 还低。
- 结论：**encoder 修对之后，我们的 decoder（INT8-past）+ 分段 + 后处理链路质量达标**。根因已闭环。C-020 的 CUDA 全长对照**不再需要**（还在跑的跑完即可，不要求交付）；CUDA 不分段 OOM 复现仍是可选项。

**但还不能交付，原因**：
1. **文件命名**：你把 Hybrid **离线**结果覆盖成了 `spe_61min_transcript.txt`。这个文件名约定是“最终部署配置（OV 流式）”的输出。请改名为 `spe_hybrid_offline.txt`（已有同名副本，删掉重复的即可），`spe_61min_transcript.txt` 留给第 3 步的最终结果。
2. **部署不能依赖 torch CPU encoder**：要装 torch，一次 encoder 700 ms，而流式每个 chunk 都要重新编码，跑不动。你提的“每段开头编码一次、流式 decode 复用 ehs”**不成立**，因为流式时后面的音频还没有到。
3. 所以 **C-023 第 2-4 步照常执行**（你 last_ack 是 C-021，C-022/C-023 还没回执，请先读）：按源码手写单窗口 encoder wrapper → `ov.convert_model` → 逐长度 cosine 验收（token 数一致、mean > 0.99、min > 0.95）。

**窗口 encoder 带来的流式优化（请一并实现）**：Qwen3-ASR 的 encoder 是按 100 帧分块卷积 + 800 帧窗口内注意力，**窗口之间互相独立**。所以流式时：
- 已经填满的窗口（每 8 s 一个）的输出可以**缓存**，不必重算；
- 每个 chunk 只需重新编码**当前未满的那个窗口**（最多 8 s 音频）。
这样 encoder 每个 chunk 的成本有上界，不再随段长增长。请先用 torch 验证“缓存窗口 + 只算最后一窗”与整段编码的结果逐 token 一致，再接入 OV。

**最终验收（完成后设 WAITING_REVIEW）**：
- OV 窗口 encoder（GPU.0，FP16；INT8 可选，需同样通过 cosine 验收）+ OV INT8-past decoder，**流式 640 ms**，VAD 分段，61 分钟全长 → `spe_61min_transcript.txt`
- WER ≤ 12%，并且不比 Hybrid 离线差 2 个百分点以上（≤ 11%）
- 整体 RTF < 1、段内瞬时 RTF P95 ≤ 0.8；内存平稳
- `transcribe_stream.py` 默认走这套配置；README 写明 encoder 的问题根因和修复方法（optimum 的 Qwen3ASRModelPatcher 把分块/窗口逻辑替换成了整段处理）

## C-025 [NORMAL] 2026-10-10 13:00 — 窗口 encoder 验收：基本通过，边界小偏差限时排查，不阻塞后续
**c023_validate 结果**：单窗口（≤800 帧）**cosine 1.000000，逐位一致**；所有长度 token 数与 torch 完全一致；多窗口 mean 0.9968-0.9994。只有 min 未全过：12 s 时 0.9308，60 s 时 0.9576，16 s 时 0.9692。FP32 和 FP16 结果相同 → 不是精度问题，是**跨窗口处的逻辑差异**。

**决策**：这个 encoder 可以用，**直接往下推进**，边界偏差并行排查，最多花 30 分钟：
1. 打印 12 s 和 60 s 的逐 token cosine，找出低于 0.99 的 token 落在哪里：
   - 如果集中在**最后一个不满窗口的补零尾部附近** → 检查补零后的 attention mask / 有效长度裁剪（torch 是对不满的块单独补齐，还是整窗补齐？以源码为准）。
   - 如果在**每个窗口的开头或结尾** → 检查 torch 的注意力窗口边界（cu_seqlens 是按 token 数 104 切，还是按其它方式累积）是否和你的 800 帧切窗完全对齐。
   - 能在 30 分钟内修好就修；修不好就记录现象和猜测，交给最终 WER 来判断。
2. **另外请核对**：日志写的是 `dur=4s n_mel=320`、`dur=10s n_mel=800`，按 hop=160 / 16 kHz，4 s 应该是 400 帧。请确认验证脚本裁剪音频时的采样率或时长计算有没有错（只影响标注就写明；如果流水线里真实送进 encoder 的帧率不对，就是 bug）。
3. **接着执行 C-024**：
   - A/B 两段，用 OV 窗口 encoder + OV INT8-past decoder 跑离线和流式，与 #1/#5（torch）对比，贴出前 80 个词。
   - 实现**窗口缓存流式**：已满的窗口缓存，每个 chunk 只重算最后一个窗口；先验证与整段编码逐 token 一致（或与上面的边界偏差同级）。
   - 61 分钟分段流式全长 → `spe_61min_transcript.txt`。验收：WER ≤ 11%（reviewer 计算）、RTF < 1、段内瞬时 RTF P95 ≤ 0.8。
4. STATUS 已有 35 分钟没更新，last_ack 还是 C-021：请立即回执 C-022~C-025 并更新进度。

## C-027 [BLOCKING] 2026-10-12 09:20 — 选项 A-E 暂不采纳：23% 的主因是**重复插入**，不是 unfixed 丢词；先修窗口 encoder 的不满块（C-025#1）
**reviewer 复核**（用我自己的 MiniMax baseline 和对比脚本，结果与你的 23.13% 一致）：WER **23.64%**，S=771 / **D=322** / **I=1499**。Hybrid 离线是 S=258 / D=174 / I=562。
- **删除并不多**，所以“unfixed 回滚导致丢词”不是主因。多出来的约 940 个**插入**才是。
- 原因是**段内重复/口吃**：流式输出里重复的 4-gram 有 922 个，Hybrid 只有 135 个。例如：
  - seg 38：`…commit and schedule for client. So that's in work and one of the things in Q4 is what's our execution, commit and schedule around that…`（整句重说一遍）
  - seg 39：`…how we can best benefit from that. How we can best benefit from that, having…`
- “流式比离线天然差 10-15 个点”不成立：C-019 的 #5（torch 流式，**同一个** streaming_asr 循环）在 A/B 段都很干净；R2T2 的卖点本来就是流式接近离线。

**主要怀疑**：C-025#1 遗留的**不满块（partial chunk）偏差**（12 s 时 min cos 0.93，正好落在不满的那个 100 帧块的 token 上）。流式时几乎每个 640 ms chunk 的结尾都是一个不满块，而那几个 token 正是模型判断“下一个词”所依赖的最新音频，偏差在这里被放大成重复/改口。

**执行**：
1. **定位实验**（只跑少量段，约 30 分钟）：选重复 4-gram 最多的 10 个段（含 seg 38/39），比较三种流式：
   - (a) OV 窗口 encoder + OV INT8 decoder（现状）
   - (b) torch encoder + OV INT8 decoder（hybrid 流式，慢没关系）
   - (c) OV 窗口 encoder，但把每次编码的音频**截到最近的整 100 帧边界**（丢掉不满块，只用来诊断）
   报告每种的重复 4-gram 数和输出文本。预期：(b)、(c) 干净 → 证实是不满块的问题。
2. **修不满块**：照 `modeling_qwen3_asr.py` 原逻辑核对：不满块是单独补齐到 100 帧再卷积；补齐产生的 token 在 flatten 时被丢掉；cu_seqlens 只计**有效** token，所以注意力的 key 里不包含补齐 token。重点检查你的 4D attention mask 是否把补齐 token 从 **key** 一侧屏蔽掉了，以及位置编码是否只用了前 n_valid 个。修好后，12 s / 60 s 的 min cos 应 > 0.99。
3. **同时排查拼接逻辑**：确认每段的最终文本取的是 `finish_streaming_transcribe` 之后的 state 文本，而不是把每个 chunk 的输出拼起来；fixed_text 只追加新增部分（`new[len(old_fixed):]`），不会因为 rollback 区域的改写把旧内容再追加一遍。
4. 修好后：先跑第 1 步的 10 段复测 → 再跑 61 分钟全长 → 交付 `spe_61min_transcript.txt`（当前文件改名为 `_v2_window_stream`）。验收不变：WER ≤ 11%、RTF < 1、P95 ≤ 0.8。
5. **关于选项 E（每段只做一次离线解码）**：这样做就没有实时的逐字输出了，改变了产品形态（流式字幕/语音助手要的就是实时出字），**不能由我们自行决定**。如果修完不满块后流式 WER 仍明显高于离线，可以考虑“两遍式”：流式出实时字幕，段尾再对整段离线重解一次作为最终文本。这个方案到时候交给用户拍板。

## C-028 [BLOCKING] 2026-10-12 09:25 — 检查点决策：路径 B（hallucination reset）不批准作为修复；先做 C-027 的定位实验
你 last_ack 是 C-025，**C-027（09:20）还没读**，请先回执 C-026~C-028。

**reviewer 复核**：CUDA 流式 WER **7.69%**（我这边算），61 分钟只有 **20** 个重复 4-gram；OV 流式 23.6%，有 922 个。同参数下 R2T2 流式本来就能做到 7.7%，比 Hybrid 离线还好，所以“流式天然差”和选项 E 的理由都不成立。

**“是 OV INT8 decoder 的循环问题”这个结论证据不足**：Hybrid 用的就是**同一个** OV INT8-past decoder，结果干净（8.66-9.07%）。OV 流式和 CUDA 流式之间有三处不同：① encoder（OV 窗口 IR vs ggml），② decoder（OV INT8 vs Q8_0），③ 我们的 streaming/seg 代码。要用实验把它们分开，而不是用 reset 去压症状。

**执行（C-027 第 1 步扩展为 4 路，只跑重复最多的 10 段，包括 [2812-2828]、[2025-2042]、[3458-3477]、seg 38/39）**：
| 路 | encoder | decoder | 用来区分 |
|--|--|--|--|
| a | OV 窗口 IR | OV INT8-past | 现状 |
| b | **torch** | OV INT8-past | encoder 是否是原因 |
| c | OV 窗口 IR，**截到整 100 帧边界** | OV INT8-past | 是否是不满块的问题 |
| d | OV 窗口 IR | **OV FP16-past** | 是否是 INT8 的问题 |
每路报告：10 段的重复 4-gram 总数，以及 [2812-2828] 的完整输出。按结果处理：
- b 干净、a 不干净 → encoder 问题 → 按 C-027 第 2 步修不满块 mask
- d 干净、a 不干净 → INT8 问题 → decoder 改用 FP16 或混合精度（lm_head / 最后几层保留 FP16），并重测 RTF
- 都不干净 → 查我们的 streaming/seg 代码（C-027 第 3 步：拼接逻辑、prefix 回灌），可以拿 audio.cpp 的同一段逐 chunk 输出（`--log`）来比对是从哪个 chunk 开始分叉的
**hallucination reset** 可以作为**最后的安全网**加上（官方 ws_server 也有），但必须在根因修好、61 分钟 WER ≤ 11% 之后再加，并且要分别报告加 reset 前后的 WER。
定位实验做完设 WAITING_REVIEW，最多等 15 分钟，超时就按上表的规则自行处理。

## C-029 [BLOCKING] 2026-10-12 09:55 — torch 被 Windows「智能应用控制」(Smart App Control) 拦截：绕开 torch 继续定位，**不要改系统安全设置**
**现象**：c028_4path.log 在 `import torch` 时崩溃：`OSError: [WinError 4551] 应用程序控制策略已阻止此文件 … torch_python.dll`。reviewer 已查：`HKLM\...\CI\Policy\VerifiedAndReputablePolicyState = 1`（智能应用控制处于**强制**模式），CodeIntegrity 日志从今天 09:32 起有 10 条拦截 torch_python.dll 的 3077/3033 事件。10-10 时 torch 还能用，是今天才开始拦的。
- **禁止**关闭智能应用控制或改任何安全策略（计划第 4 节“不得做的事”）。这个开关一旦关掉，不重装系统就打不开，必须由用户决定。reviewer 已经把这个问题报告给用户。
- 这也说明：**最终部署形态必须完全不依赖 torch**。目标机可能都开着智能应用控制，未签名的 torch DLL 会被拦。OpenVINO 的 DLL 有 Intel 签名，目前没有被拦。

**绕开 torch 继续 C-028 的定位实验**：
1. 运行所有 OV 路径时设环境变量 `USE_TORCH=0`（另加 `USE_TF=0`、`USE_FLAX=0`），让 transformers 不去导入 torch。`WhisperFeatureExtractor` 和 tokenizer 都有纯 numpy 实现。代码里如有 `import torch`、`return_tensors="pt"` 或 `qwen_asr` 的导入，换成 numpy 版本或延迟导入。
2. 跑 C-028 的 **a / c / d 三路**（都不需要 torch）。**b 路（torch encoder）暂时做不了**，改用以下两个替代证据：
   - 已有的 Hybrid 离线结果（torch encoder + 同一个 OV INT8 decoder，干净）；
   - 用 audio.cpp（CUDA，签名问题另看：如果 audiocpp_cli.exe 也被拦，就记录下来）把 [2812-2828] 段用 `--log` 跑一遍流式，导出逐 chunk 输出，与 a 路逐 chunk 对比，找到从哪个 chunk 开始分叉。
3. 写 STATUS（按真实时间写 updated，`date /t & time /t`），列出 a/c/d 三路结果、能否运行 audiocpp，以及你检查过的、还会被拦截的其它 DLL（例如 `qwen_asr`、`soundfile` 的 libsndfile 等）。之后按 C-028 的判定规则处理，最多等 15 分钟。
4. 61 分钟全长复测和最终交付也要在 `USE_TORCH=0` 下跑通，作为“部署不依赖 torch”的验证。

## C-030 [BLOCKING] 2026-10-12 10:35 — 检查点决策：顺序 E → B → A（不是 C）；先做逐 chunk 追踪，n4 的单次对比不足以归因
**对 4 路结果的判断**：数据显示的是**系统脆弱**，而不是两个干净的“因素”：seg38 的 a=0，c、d 两种扰动反而都变坏（17/18）；seg213 三路都坏；seg39 c 变坏、d 变好。greedy 解码对微小数值扰动很敏感，**任何**扰动都会让一些段的循环消失、另一些段冒出循环。所以单次 n4 计数不能用来归因“INT8 是因素”。真正的问题是：**OV 流式在“重说已确认的内容”这件事上很脆弱，而 audio.cpp 不会**（它每个 chunk 的 stream.text 严格单调增长）。

重复的形态本身就是线索：`…but I think **that's a good question, but I think** …`、`…schedule **for client. So that's in work … schedule** around that` —— 模型在**重新转写 prefix 里已经有的内容**。这通常意味着**送进去的 prefix 和音频的对齐有问题**：prefix 比实际已识别的位置更早（回滚多了，或用了旧的文本），或者 prefix 里有重复。

**执行顺序**：
1. **E（先做，必须）逐 chunk 追踪**：对 seg172 [2812-2828] 和 seg38，记录 OV a 路每个 chunk 的：送入的 prefix 字符串（rollback 之后）、prefix token 数、生成的 gen_text、raw_decoded、fixed_text；与 `c029_audiocpp_seg172.log` 里 audio.cpp 每个 chunk 的 raw_decoded / fixed_text 逐 chunk 对齐，找到**第一次出现“gen_text 重复 prefix 里已有内容”的 chunk**，贴出该 chunk 前后各 2 个 chunk 的完整记录。重点核对与 r2t2 源码（r2t2_asr.py 302-578）是否一致：
   - prefix 是由**上一步的 `_raw_decoded`** 回滚 k 个 token 得到，还是错用了 fixed_text 或更早的文本；
   - `language XXX<asr_text>` 标签是否被重复放进 prefix（官方逻辑里 raw_decoded 自带标签，prefix 不应再加一次）；
   - 新段 `init_streaming_state` 之后，上一段的文本是否残留在 state 里；
   - `_normalize_punct_by_context`、中文去空格分支对英文有没有误改（比如吞掉空格，导致回滚的 token 边界错位）。
2. **B（第二步）修不满块 mask**：这本来就是已知的正确性 bug（min cos 0.93），无论是否是循环的主因都必须修。修完后 12 s / 60 s 的 min cos > 0.99。
3. **A（最后，视情况）**：只有在 E、B 修完、61 分钟 WER 仍 > 11% 时才考虑精度。到那时先用**纯 FP16 decoder 跑一次 61 分钟**看上限，再决定是否值得做混合精度（同时报告 RTF）。
4. 验证一律用**足够大的样本**：修完后先跑 30 个段（含这 11 个最差段），比较修复前后的重复 4-gram 总数，然后再跑 61 分钟全长。不要用单段的 n4 来下结论。
完成第 1 步就把追踪结果写进 STATUS（不用等 reviewer，直接继续第 2 步）。

## C-031 [BLOCKING] 2026-10-12 10:50 — reviewer 代码审查：window cache 与官方“每个 chunk 全量重算特征”不等价，先加 e 路（关缓存）
reviewer 读了 `window_encoder_backend.py`、`streaming_asr.py` 和 `backends.py`：streaming 循环与 r2t2 源码一致；prefix 的分词（`encode(prompt_raw+prefix)` 再去掉 prompt_raw 部分）也没问题。**可疑的是 window cache（第 178-188 行）**：
- 官方 r2t2 / vLLM / audio.cpp 每个 chunk 都对**整段累积音频**重新提特征。`WhisperFeatureExtractor` 的 log-mel 会做**全局归一化**：`log_spec = max(log_spec, log_spec.max() - 8.0)`，再 `(log_spec + 4) / 4`，其中 max 是对**到目前为止的整段输入**求的。后面一出现更响的片段，前面所有帧的特征值都会变，而缓存里还是旧值。
- **边界效应**：一个窗口刚填满时（第 800 帧刚到），它最后几帧处在整段音频的末尾，STFT（center=True，反射补齐）用的是补出来的样本；这一版被**永久缓存**，之后音频变长，这几帧的正确值已经不同了。
- 所以缓存模式下，后续每个 chunk 送给 decoder 的“过去音频”特征，都与全量重算（torch / CUDA / Hybrid 离线）不一致。这正好解释了“对扰动敏感、会重新转写 prefix 里已有内容”。Hybrid 离线不走缓存，所以是干净的。
- 你的 cache 单元测试（6/8/20 s）如果是一次性传入整段音频，就测不出这个问题；必须模拟**逐 chunk 增长**的音频，再与每一步全量重算的结果比较。

**执行**（插在 C-030 第 1 步之前，约 20 分钟）：
1. **e 路 = 关闭 window cache**：每个 chunk 对整段 audio_accum 全量提特征、所有窗口全量编码（窗口 IR 不变）。在同样 11 个最差段上跑，报告重复 4-gram 总数与 a 路（183）对比；同时报告每 chunk encoder 耗时（预计段尾约 2-3 个窗口 × 每窗耗时）。
2. **逐 chunk 增长的一致性测试**：取 seg172，模拟 640 ms 一步增长。每一步比较“缓存模式 ehs”和“全量重算 ehs”的逐 token cosine，报告每步的 min cos，以及第一次 < 0.99 发生在哪一步、哪个窗口。
3. **结果判断**：
   - e 路明显干净 → 根因就是缓存。**正确的缓存做法**：每个 chunk 照常对整段音频提特征（mel 很便宜，约 5 ms），只缓存窗口的 encoder 输出，并且只有在该窗口的 mel 与缓存时相比 max abs diff < 1e-4 时才复用，否则重算。另外最近一个已满窗口在后面至少有 2-3 帧音频之前也不要缓存（避开 STFT 边界）。如果归一化导致频繁失效，也可以接受“每个 chunk 全量编码”，只要 RTF 达标。
   - e 路仍然有循环 → 回到 C-030 第 1 步的逐 chunk 追踪。
4. C-030 的 B（不满块 mask）照常要修。e 路的结论出来后先写 STATUS，然后直接继续，不用等 reviewer。

## C-032 [BLOCKING] 2026-10-12 10:55 — 立即停止“改成 per-chunk cu_seqlens”的重新导出：对源码的理解有误；先做 C-031
你 last_ack 是 C-030，**C-031（10:50，window cache 与官方全量重算不等价）还没读**，请先回执 C-031、C-032。

**E 步追踪做得好**：把循环的起点精确定位到单个 chunk（seg172 chunk 20 一次生成 25 个词；seg38 chunk 13-15），并逐行确认 streaming 代码与 r2t2 一致，这些都认可。

**但 B 的根因分析是错的，请停掉 `c030b_export` 相关的修改**：
- 你引用的源码：`window_aftercnn = padded_mask_after_cnn.shape[-1] * (self.n_window_infer // (self.n_window * 2))`。`padded_mask_after_cnn.shape[-1]` 是每块 13 个 token，`n_window_infer // (n_window*2)` = 800 // 100 = **8**，所以 window_aftercnn = **104**。cu_seqlens 是 `[0, 104, 208, …, 余数]`，**按窗口（104 个 token）**划分，不是按块（13 个）。你注释里写的 `[0,13,26,…]` 是算错了。
- 你自己的数据也证明了这一点：全窗时用 `[0, 104]`（窗口内全互相 attend），cosine **严格等于 1.000000**。如果原版是 per-chunk 注意力，全窗口注意力不可能与之逐位一致。“块内满注意力等价于块间满注意力”在数学上不成立。
- 改成 per-chunk 会把现在完全正确的全窗也弄错。

**不满块 0.93 的真正原因要用逐层对比来找**（排在 C-031 之后）：用 960 帧（9 个满块 + 1 个 60 帧的不满块）作为输入，对 torch 和你的 wrapper 在以下位置挂 hook，逐个比较：① 三层 conv 之后（每块 13 个 token，重点看不满块的 7 个有效 token）② 加位置编码之后 ③ 第 1 层、第 12 层、最后一层 attention 之后 ④ 最终投影之后。第一个出现偏差的位置就是 bug。可能的方向：不满块在 torch 里补齐时用的值（0 还是其它 padding_value）、`aftercnn_len` 公式对不满块的取整、conv 之后 mask 掉无效 token 的时机（torch 可能在 conv 之后、attention 之前就把补齐 token 丢掉，而你是把它们留在序列里再靠 mask 屏蔽，那么 conv 本身的边界就不同）。
**另外注意 torch 是在 eager/sdpa 下运行，torch 当前被智能应用控制拦截**：逐层对比需要 torch。如果做不了，就先只做 C-031（它只需要 OV），并在 STATUS 里说明逐层对比被阻塞，交给用户决定。

**执行顺序**：C-031 第 1-3 步（e 路关缓存 + 逐 chunk 增长一致性测试）→ 视结果决定 → 不满块逐层对比（需要 torch）。

## C-033 [BLOCKING] 2026-10-12 11:12 — 检查点决策：先修 encode_audio 的窗口计数 bug（你的 growing 日志里就能看到），再加 reset 作为安全网；不满块逐层对比交给用户决定是否解除 SAC
**C-031 结论认可**：关缓存（e 路，230）没有好于现状（183），所以缓存不是循环的主因。

**但 c031_growing.log 暴露了一个确定的 bug**（`window_encoder_backend.py:170-172`）：
- `n_100_blocks = ceil(mel/100)`，`n_full_windows = n_100_blocks // 8`。当 mel 长度在 (700, 800) 区间（以及 (1500,1600) 等）时，块数向上取整后等于 8 的倍数，代码就把**不满的窗口当成满窗口**，调用 `_encode_window(win_mel, 800)`：补齐的零帧被当作有效音频编码，N_audio 也算多了。实例：step 12，audio 7.68 s = 768 帧，正确 N_audio = 7×13 + aftercnn_len(68) = 91 + 9 = **100**，日志里是 **104**。
- 缓存模式下，这个被污染的窗口会被**永久缓存**：日志从 step 12 起有 31 个 token 偏差，cos_min ≈ −0.04，之后再也不恢复。
- 不缓存时，同样的错误也会在每个落在该区间的 chunk 上发生（大约每 8 s 里有 1 s），每次都恰好出现在最新的音频位置。
- **修法**：`n_full_windows = mel_len // 800`（按**帧数**向下取整，不按块数），其余全部作为不满窗口，传入真实的有效帧数。缓存只缓存 `mel_len >= (w+1)*800 + 若干帧`（避开 STFT 边界）的窗口。修完后重跑 c031_growing：每一步 N_audio 必须等于公式值，缓存与全量重算逐 token cos > 0.99（不满块本身的 0.93 偏差除外，请把它单独标出来）。

**执行顺序**：
1. 修上面的 bug → 重跑 growing 测试 → 11 个最差段 a 路（带修好的缓存）复测，报告重复 4-gram 总数（对比 183）。
2. **hallucination reset 批准作为安全网**（尊重用户 10:26 的兜底指示），但必须**叠加在第 1 步之后**，不能代替第 1 步。实现要求：检测到 gen_text 与 prefix 尾部重复（同一 3-gram 连续 ≥3 次，或 gen_text 前缀与 prefix 末尾 ≥6 个词重合）时，丢弃本次 gen_text、保留上一步的 fixed_text，下一个 chunk 照常继续；同一段内连续触发 3 次就 finish 并重开一段。
3. 61 分钟全长跑**两次**并都交付：`spe_61min_transcript_noreset.txt`（只修 bug）和 `spe_61min_transcript.txt`（修 bug + reset）。reviewer 分别算 WER。
4. FP16 decoder（选项 A）暂不做；如果第 3 步之后 WER 仍 > 11% 再考虑。
5. 不满块 0.93 的逐层对比需要 torch，目前被智能应用控制拦截 → reviewer 已向用户报告，由用户决定。不要自行处理。

## C-034 [FYI] 2026-10-12 11:20 — 用户决定：暂不解除智能应用控制
用户已确认**先不解除** Smart App Control。不满块 0.93 的 torch 逐层对比暂停，不要尝试绕过或关闭 SAC。按 C-033 继续：修窗口计数 bug → growing 复测 → 11 段复测 → 叠加 reset → 61 分钟两份 transcript（noreset / reset）。等两份结果出来后，reviewer 根据 WER 再判断是否需要请用户重新考虑 SAC。

## C-035 [NORMAL] 2026-10-12 11:30 — 当前 61 分钟（只有 reset）跑完即可，不要中断；之后按 C-033 补做
你 last_ack 是 C-032，**C-033、C-034 还没读**，请先回执。
- 正在跑的 61 分钟（只加了 reset、**没修**窗口计数 bug）让它跑完，交付时命名为 `spe_61min_transcript_reset_only.txt`（不要占用 `spe_61min_transcript.txt`）。这一份可以单独衡量 reset 的效果。
- 注意 reset 是把重复的生成**丢掉**，可能连真实的词也一起丢。请统计这次全长 reset 共触发了多少次、丢弃了多少词。reviewer 会看 WER 里的删除数（D）有没有明显上升。
- 跑完后按 C-033：修 `encode_audio` 的窗口计数 bug（`n_full_windows = mel_len // 800`）→ 重跑 growing 测试（每一步 N_audio = 公式值）→ 再跑两份 61 分钟：`spe_61min_transcript_noreset.txt`（只修 bug）和 `spe_61min_transcript.txt`（修 bug + reset）。
- 用户已决定暂不解除智能应用控制（C-034）。

## C-036 [BLOCKING] 2026-10-12 11:40 — 用户要求：必须从根因上解决，reset 只作诊断手段，不作为交付方案
用户明确指出 hallucination reset 治标不治本。**C-033 第 2 步“reset 作为安全网”和 C-035 的 reset 交付要求撤销**：
- 正在跑的 reset 版 61 分钟可以跑完，结果只作为诊断数据（文件名照 C-035 用 `_reset_only`），**不作为交付**。最终交付必须是**不带 reset** 的流式输出达到 WER ≤ 11%。
- 现在已知的两个根因：
  1. **窗口计数 bug**（C-033）：`n_full_windows` 要按帧数 `mel_len // 800` 计算。确定性 bug，请立即修，并重跑 growing 测试，确认每一步的 N_audio 等于公式值。
  2. **不满块编码偏差**（12 s 时 min cos 0.93）：需要 torch 作对照，目标机的 torch 被智能应用控制拦截，用户决定不解除。→ **改由 reviewer 在自己的机器上用 torch 做逐层对比**（reviewer 机器不受影响）。你需要配合：
     - 不要改动 `c023_export_window_encoder.py` 和 `models/ov-encoder-window/`（reviewer 以这一版为准）。
     - 如果 c023 导出脚本依赖其它本地文件（自写的 helper 模块等），在 STATUS 里列出文件名，reviewer 会一起拉取。
- 第 1 点修完后，跑 11 个最差段（不带 reset）报告重复 4-gram 总数，再跑 61 分钟 → `spe_61min_transcript_noreset.txt`。reviewer 定位出不满块的 bug 后会给出具体修改，再出最终版。
## C-037 [BLOCKING] 2026-10-12 14:10 — user 决定：撤销 C-029「不改系统网络/代理」约束，本机可改 ~/.gitconfig 局部代理 / 直连 github.com 以推送代码

## C-039 [BLOCKING] 2026-10-13 09:20 — 根因已确认：参考实现的 encoder 是**全局注意力**，不是 104-token 窗口；改用 reviewer 验证过的整段 encoder
（编号跳过 C-038，避免与你分支名 `c038-v2-ir` 混淆。）先回执 C-038(跳过)/C-039。

**根因**（reviewer 本机用 torch 逐行核对源码 + 数值验证；你 10-12 晚用 torch 跑的 c037c/c037d 也与此一致）：
- `modeling_qwen3_asr.py` 的 `Qwen3ASRAudioEncoder.forward`（第 727-733 行）调用每一层时是 `encoder_layer(hidden_states, cu_seqlens)`，**没有传 attention_mask**；构造窗口 mask 的 `_prepare_attention_mask`（第 649 行）**定义了但从未被调用**。在 eager/sdpa 下 `cu_seqlens` 被忽略，所以参考实现对**输入里的所有音频 token 做全局注意力**。只有 flash-attention-2 路径才会按 104-token 窗口切。
- 你的 c037c 已经显示：conv / conv_out / 位置编码**全部 1.000000**，偏差是从 attention 层开始、随层数放大的（layer0 0.99996 → layer11 0.92 → 输出 0.30）。c037d 去掉 mask 后仍是 0.29，是因为两个窗口还是**分两次调用**，跨窗口根本无法互相注意。不是不满块或 padding 的问题。
- reviewer 实测（seg172 真实音频）：窗口版在 >800 帧时 min cos 降到 **0.005-0.09**；全局版在 0.64-23.9 s **所有长度 cos mean 1.000000 / min ≥ 0.999996**。
- 这也解释了现象：流式时最新的音频总落在一个很短的尾窗里，只能注意它自己，于是模型“听不清最新的词”就去重说 prefix。cache bug 修好后 11 个最差段从 183 降到 1，但 61 分钟全长（c033 noreset）仍是 **WER 18.32%、重复 4-gram 967**，循环只是换了地方 —— 结构性原因就是窗口注意力。

**reviewer 已交付**（`reviewer/` 和 `models/ov-encoder-segment-reviewer/`）：
- `reviewer/export_segment_encoder.py`：整段 encoder。固定输入 `input_features [1,128,2400]`（24 个 100 帧块，覆盖 ≤23.9 s 的段）+ `n_valid [1] int32`；输出 `[1,312,2048]`，取前 n_valid 行。分块卷积 + 块内位置编码与原版相同，注意力为**全局**、只屏蔽补齐的 key。
- `models/ov-encoder-segment-reviewer/`：reviewer 本机导出并验证过的 IR（FP16 权重压缩；CPU FP32 推理对比 torch 全部 ≥ 0.999996）。你也可以在本机用该脚本重新导出：`python reviewer/export_segment_encoder.py models/hf models/ov-encoder-segment test_audio/260902_SPE_audio.wav`（脚本自带 9 个长度的验证）。

**执行**：
1. 新建 `SegmentEncoderOVBackend`（**不要**在 window backend 上改）：每个 chunk 对整段 `audio_accum` 提特征 → 补零到 2400 帧 → 一次调用 → 取前 `n_valid = aftercnn_len(frames)` 行。**不做任何窗口缓存**（全局注意力下无法复用）。帧数 > 2400 时报错（分段 max 20 s，加 flush 也够）。
2. GPU.0 上用 FP16 推理复跑脚本自带的 9 长度验证（与 torch 比较），报告 cos mean/min（FP16 预期 ≥ 0.999 / ≥ 0.99）和每次 encoder 耗时（静态 shape，记得 reshape 成 [1,128,2400] / [1]）。
3. 11 个最差段（不带 reset）→ 报告重复 4-gram 总数；然后 **61 分钟全长、不带 reset** → `spe_61min_transcript.txt`（当前同名文件改名为 `_v2_window_stream`），附 RTF P50/P95/max。验收：WER ≤ 11%、RTF < 1、P95 ≤ 0.8。
4. `ov-encoder-window*`、`c038-v2-ir`（per-chunk）都作废，不再使用。

**对 10-13 凌晨报告的更正**：
- “CUDA 61-min 从未跑过、7.5% 来自 60 s 短音频”——**不对**。`reports/cuda/spe_cuda_stream.txt` 是 226 个 VAD 段、覆盖完整 61 分钟的 CUDA 流式结果，reviewer 用 MiniMax baseline 算出 **7.69%**；它没崩溃是因为每段 ≤ 20 s。
- 你的 CUDA 不分段 OOM 测试（240-300 s 处报 `exceeds max_source_positions`）很有价值，与 OV 在 120 s 撞到 1500 上限是同一类问题，回答了用户最初关于 CUDA 长音频 OOM 的反馈。请保留，写进最终报告。
- README / PROJECT_REPORT 暂不改（选 M2），等最终结果出来一次性更新。

## C-040 [BLOCKING] 2026-10-13 10:00 — encoder 已修好（替换错误 771→335），但插入仍有 1510：第二个根因在 decoder/流式这一侧，用 torch 逐层隔离
**reviewer 判定**（`spe_61min_transcript.txt` 09:45 版，对比 MiniMax）：WER **18.21%**，S=**335** / D=**152** / I=**1510**，重复 4-gram **991**，51 段 rep≥5。RTF P50 0.576 / P95 0.646 / max 0.956（性能达标）。
- 对比 cache 修复版（18.32%，S=351/D=159/I=1499）和窗口版（S=771）：**全局 encoder 把替换错误降到了正常水平，但插入一点没变** → encoder 这一层已经解决，剩下的是**另一个独立的根因**。
- 现象有两类（各举一例，请都用来测）：
  - **整句重放**：seg 67 [1086-1102]：`…but then where these new businesses are going to be expecting us to deliver. So we thought we'd share…`（约 40 个词重新出现一遍）；seg 163 [2657-2676]、seg 161 [2622-2640] 同类。
  - **短语循环**：seg 118 [1925-1940]：`Obviously, go and get this off the ground.` ×约 20。
- 同一个 OV INT8 decoder 在 hybrid **离线**（一次解码，无 prefix）时这些段都很干净；CUDA 流式（Q8_0）和 torch 流式（C-019 #5）也干净。所以问题只出在 **OV decoder + 带 prefix 的流式**。

**执行**（torch 现在在目标机可用）：
1. 选 rep≥5 的 51 段里最差的 15 段（包含 67/118/161/163），全部用**同一个全局 encoder 的 ehs**，跑三种流式 decoder：
   - (i) OV INT8-past（现状）
   - (ii) OV FP16-past
   - (iii) **torch FP32 decoder**（qwen_asr 的 thinker，喂入相同的 ehs 和完全相同的 prompt token id，greedy，同样的 max_new_tokens）
   报告每种的重复 4-gram 总数。
2. **逐 chunk 对比**：对 seg 67 和 seg 118，把 (i) 和 (iii) 每个 chunk 的 `prefix_ids`（完整 token id 列表）、`gen_ids`、`raw_decoded`、`fixed_text` 都存下来，找到**第一个分叉的 chunk**：
   - 如果该 chunk 的输入 token id 完全相同、输出不同 → OV decoder 的数值或状态问题。请在该 chunk 上比较 (i)/(ii)/(iii) 第一步的 logits top-5 及 margin；同时确认每次 prefill 前都 `reset_state()` 了，`beam_idx` 正确，以及 prefill 后的第一步 decode 的 position 是否等于 prompt 长度（stateful 模型内部的 position/attention_mask 是怎么推出来的？optimum 的 Qwen3-ASR decoder 是否需要显式传 `attention_mask` / `position_ids`？长 prompt + prefix 时是否有截断或溢出）。
   - 如果该 chunk 的输入 token id 就不同 → 问题在 prefix 构造或文本拼接（例如 rollback 后 decode→encode 不可逆、`_normalize_punct_by_context` 改了文本），请贴出两边的差异。
3. 根据结论修复，**不允许用 reset 或改参数（unfixed_token_num 等）来掩盖**。修好后 15 段复测 → 61 分钟全长 noreset → `spe_61min_transcript.txt`（当前文件改名 `_v3_segenc_int8`）。
4. 完成第 2 步就在 STATUS 里写结论，不用等 reviewer，直接进入第 3 步。

## C-041 [BLOCKING] 2026-10-13 10:20 — 主因定位：**61 分钟长跑脚本里存在跨段状态泄漏**（同样的段单独跑是干净的）
reviewer 对比 c040_3dec.log（单段独立跑）和 09:45 的 61 分钟全长结果（同一个全局 encoder + 同一个 INT8 decoder）：
| 段 | 61 分钟全长 rep4 | 单独跑 INT8 | 单独跑 FP16 | 单独跑 torch |
|--|--:|--:|--:|--:|
| seg118 | **162** | 0 | 0 | 0 |
| seg67  | **38**  | 0 | 0 | 0 |
| seg163 | **40**  | 0 | 1 | 1 |
| seg161 | **36**  | 26 | 0 | 0 |
音频、encoder、decoder 都一样，**每段从干净状态开始时就不循环，在长跑里连续处理时才循环** → 主因是长跑脚本（seg_stream / c039 61-min runner）在段与段之间带过去了某些状态。decoder 精度只是次要问题（见第 4 条）。

**执行**：
1. **复现**：用 61 分钟的 runner 只跑 seg 110-120（从 seg110 的起点连续处理到 seg120 结束），确认 seg118 会循环；再把 runner 改成“每段都像 3dec 脚本那样独立构造”，确认 seg118 恢复干净。
2. **找出泄漏的状态**：对比两个脚本在每段开始时的全部输入状态并打印出来，重点检查：
   - `state.buffer`：上一段没凑满一个 chunk 的剩余采样，是否被拼到了下一段开头（这样新段一开始就带着上一段的音频）；
   - `audio_accum`、`_raw_decoded`、`state.text`、`chunk_id`、`last_fixed_text` 是否都在 `init_streaming_state` 时清空；
   - `context`（system prompt）里是否放进了之前的转写文本；官方 ws_server 只放热词；
   - 段切点的样本偏移：新段的音频起点是否等于上一段的终点（不重叠、不遗漏），时间戳是否和 segments.json 一致；
   - decoder 的 `reset_state()` 是否在每次 prefill 前都调用了；encoder / decoder 的 infer request 是否被两个 backend 实例共用。
3. 修复后：seg 110-120 连续跑复测 → 61 分钟全长 noreset → `spe_61min_transcript.txt`（当前文件改名为 `_v3_segenc_leak`）。
4. **INT8 精度（次要，修完第 2 步之后再做）**：FP16 与 torch 基本逐 token 一致，INT8 在 seg161 偏离；但 FP16 单段 RTF 约 1.04，不能直接用。请评估：
   - NNCF 数据感知 INT8（AWQ / scale estimation，用这段录音的一部分做校准）；
   - INT8 但 `lm_head` 和首尾各 2 层保留 FP16。
   用这 15 段比较“与 FP16 输出逐 token 的一致率”和 RTF，选 RTF ≤ 0.8 里一致率最高的方案。

## C-042 [NORMAL] 2026-10-13 10:35 — C-041 补充：reviewer 已审查代码，未发现明显的跨段泄漏；先做两个更便宜的检查
reviewer 读了 `c039_61min.py`、`seg_stream.py`（run / _run_one_segment）、`segment_encoder_backend.py`、`c040_3decoder_test.py`：
- 长跑每段都新建 state，`context` 为空，每段都 finish；backend 除了每次 prefill 前 `reset_state()` 外不持有跨段状态；3dec 测试用的是同一个 SegmentedStreamer、同一个 GPU.0 / f16 配置。
- 所以“泄漏”可能不是原因，另有两种解释。请**在做 C-041 第 2 步之前**先查这两项（各约 5 分钟）：
  1. **确定性**：同一个脚本把 seg118 单独跑 3 次（INT8，GPU.0），比较 3 次输出的 token id 是否完全一致。不一致 → GPU 推理不确定，INT8 在临界点附近会随机翻转，这就是为什么同一段时好时坏。
  2. **输入是否真的相同**：打印 61 分钟 runner 里 seg118 实际切出的采样区间 `[s, e)`，与 3dec 测试切 seg118 时用的区间比较，必须逐样本相同。再对两边送进 encoder 的 mel 求 max abs diff。
- 结论分流：
  - 输入不同 → 修切段/时间戳的不一致，然后按 C-041 第 3 步重跑。
  - 输入相同、多次输出不同 → 根因是 INT8 decoder 在 GPU 上的数值脆弱性，**C-041 第 4 步（精度方案）升为主任务**：在 seg118/161/163/67 等 15 段上，比较各精度方案与 FP16 的逐 token 一致率，以及每种方案 3 次运行之间是否一致；同时试一下 decoder 用 `INFERENCE_PRECISION_HINT=f32`（INT8 权重、FP32 激活）的 RTF。
  - 输入相同、输出也确定 → 那才是真的状态泄漏，按 C-041 第 2 步排查。

## C-043 [BLOCKING] 2026-10-13 10:45 — 第二个根因：INT8 decoder 的输出层（lm_head）量化误差；保留 lm_head 为 FP16，其余 INT8
请先回执 C-040~C-043（last_ack 还是 C-039）。

**来自你的 c040_trace.log（seg118）**，第一个分叉点 chunk 4，同样的输入：
| | top-1 logit | top-2 | top-3 token |
|--|--:|--:|--|
| torch FP32 | 40.34 | 29.63 | 151643（结束） |
| OV FP16 | 40.25 | 29.59 | 151643，与 torch 一致 |
| **OV INT8** | **44.87** | **32.95** | 48718，排序变了 |
- INT8 的 logits **整体放大约 11%**，候选排序也变了。这不是随机噪声，是**输出投影的系统性尺度误差**。该模型 `tie_word_embeddings=true`，lm_head 与词嵌入共享同一个 151936×2048 的矩阵，导出时一起被压成了 INT8_ASYM per-channel。
- 后果：结束判定翻转（INT8 在 chunk 4 输出 "." 再结束，FP16 和 torch 直接结束），之后 prefix 偏移，就进入循环。INT8 处在判定边界附近，所以同一段有时干净、有时循环（你在 3dec 里 seg118 是 0，在 trace 里又出现 `Obviously, obviously,` —— 正是这种脆弱性）。FP16 与 torch 的 logits 差在 0.1 以内，说明其余部分没有问题。
- C-042 的确定性检查可以简化：只需确认同一输入下 INT8 多次运行是否一致，**不影响**本条结论。

**执行**：
1. **导出“INT8 + FP16 lm_head”的 decoder**（输出到新目录 `models/ov-int8-lmfp16-past/`）：
   - 从 `models/ov-fp16-past`（或 hf 重新导出的 FP16 with-past IR）出发，用 NNCF：`nncf.compress_weights(ov_model, mode=CompressWeightsMode.INT8_ASYM, ignored_scope=nncf.IgnoredScope(names=[<lm_head 的 MatMul 节点名>]))`。先打印 IR 中最后一个 `MatMul`（输出维度 151936）的名称并填进去。
   - **注意权重共享**：如果 IR 里 lm_head 的 MatMul 和 embedding 的 Gather 共用同一个常量，ignored_scope 可能对 Gather 也生效，也可能两者都不生效。导出后检查：lm_head 的 MatMul 输入权重必须是 f16，embedding 可以是 INT8。必要时先把共享常量复制一份，分别给 MatMul 和 Gather。
2. **验证**：在 seg118 chunk 4（以及你 trace 里的其它分叉点）上，比较新 decoder 与 FP16 的 top-5 logits，要求 top-1 logit 相差 < 0.5、top-5 排序一致；再在 15 段上统计与 FP16 输出逐 token 一致率，以及每段 RTF。
3. **如果 RTF > 0.8**（lm_head FP16 每个 token 多读约 300 MB），再试：lm_head 用 INT8_SYM **per-group（group_size=128）**，或 INT4 主干 + FP16 lm_head。目标是在 RTF ≤ 0.8 的前提下，与 FP16 的一致率最高。
4. 选定后：61 分钟全长 noreset → `spe_61min_transcript.txt`（当前文件改名为 `_v3_segenc_int8`）。验收：WER ≤ 11%、RTF < 1、P95 ≤ 0.8。
5. C-041 的“跨段泄漏”排查**暂停**：reviewer 审查代码未发现泄漏，而 logits 证据已能解释“同一段时好时坏”。如果第 4 步之后长跑与单段仍有系统性差异，再恢复排查。

## C-044 [NORMAL] 2026-10-13 11:15 — lm_head-FP16 不够（top-1 差 1.89，误差也来自主干）；改用确定性指标选量化方案
**结论认可**：C-043#2 表明误差不只在 lm_head，28 层主干也有贡献。正在跑的 61 分钟让它跑完（作为该方案的数据点，文件名注明 `_int8lmfp16`）。

**方法问题**：纯 INT8 在同样 15 段上，C-040 是 n4=29，C-043 是 n4=3。**单次运行的 n4 计数噪声比方案之间的差异还大**，不能拿来选方案。请改用**确定性的 teacher-forcing 指标**：
- 对 15 段，先用 **FP16 decoder** 跑一遍流式，记录每个 chunk 送进 decoder 的完整 `full_ids`（prompt + prefix）以及 FP16 逐步生成的 token 序列；
- 对每个候选 decoder，用**同样的 full_ids + 同样的 FP16 token 序列**做 teacher forcing（一次 prefill 整个序列，取每一步的 logits），统计：
  1. **top-1 一致率**（候选的 argmax 是否等于 FP16 的 token），
  2. 每步 **logit 的 max abs diff 和 KL(FP16‖候选)** 的均值和 P99，
  3. **EOS 判定一致率**（FP16 生成 EOS 的那一步，候选是否也是 EOS）——循环正是从这里开始的。
- 这个指标与 GPU 的随机翻转无关，每种方案只需跑一次，几分钟就能出结果。

**候选方案**（都从 `models/ov-fp16-past` 出发，用 NNCF，输出到各自的新目录）：
- (a) INT8_ASYM per-channel（现状，作为基准）
- (b) **INT8_SYM per-group，group_size=128**
- (c) **INT8_ASYM per-group，group_size=64**
- (d) (b) + lm_head FP16 + 第 0、1、26、27 层 FP16
- (e) 按层敏感度：逐层只把一层恢复成 FP16，测 top-1 一致率的提升，挑出提升最大的 k 层（k 控制在总权重 ≤ 20% 以内）保留 FP16，其余用 (b)
每种都报告：top-1 一致率、EOS 一致率、KL P99、IR 大小，以及单段 RTF（seg118 / seg161 / seg163 平均）。

**选择规则**：在 **RTF ≤ 0.8** 的方案中选 top-1 一致率和 EOS 一致率最高的；目标 top-1 ≥ 99.5%、EOS ≥ 99%。选定后跑 61 分钟全长 noreset → `spe_61min_transcript.txt`。
如果所有方案都达不到、只有 FP16 能达到，就把各方案的 RTF / 一致率表写进 STATUS，并设为 WAITING_REVIEW（这时要由用户在“精度”和“实时余量”之间做取舍）。

## C-049 [NORMAL] 2026-10-15 09:40 — C-045~C-048 验收通过：根因与修复均已独立复核
reviewer 已在本机独立复核（不依赖目标机的计算结果），结论：**修复正确，验收通过**。

**1. 根因属实**。我对照本机的官方源码副本 `Confucius4-R2T2-master/example.py:118-155` 逐行核对，确认自适应预算机制存在且与你的描述一致：
- `max_new_tokens = max(1, int((step+lookhead)/1280))`（约每 80 ms 音频 1 个 token）
- `max_new_tokens_floor = min(32, max(4, 2*int(step/1280)))`
- 有新内容则收紧、无新增则 +1，中文 token 再翻倍
- `finish_streaming_transcribe(state, first_max_new_tokens)`
固定 32 让每个 chunk 的生成预算远超新音频所能支撑的内容，模型只能靠重述 prefix 填满预算 —— 这解释了此前全部现象：插入高达 1510 而替换正常、hybrid 离线干净（整段一次解码不存在超预算）、CUDA 干净（本来就是自适应）、INT8 与 FP16 差异不大（从来就不是量化问题）。C-043/C-044 的量化路线确属证伪，这个判断是对的。

**2. 指标独立复核**（我用自己的 MiniMax baseline 和对比脚本重算 `transcript_adaptive.txt`）：
| 指标 | 我的复核值 | 你的报告 | 验收线 | 结果 |
|---|--:|--:|--:|---|
| WER | **8.17%** | 7.88% | ≤ 11% | ✅ |
| 替换 S | 282 | — | — | ✅（baseline 18.21% 时是 335）|
| 删除 D | 151 | — | — | ✅ 与修复前的 152 持平，**没有丢词** |
| 插入 I | **463** | — | — | ✅（修复前 1510）|
| 重复 4-gram | **50** | 262(n4) | — | ✅（修复前 991；CUDA 20，hybrid 135）|
| 整体 RTF | 0.639 | 0.639 | < 1 | ✅ |
| 段 RTF P95 | 0.675 | 0.675 | ≤ 0.8 | ✅ |
WER 的 0.29pp 差异只是归一化口径不同（我按小写去标点、数字保留原样）。`transcript_baseline.txt` 我复算是 18.21%，与我此前对 `spe_61min_transcript_v3_segenc_int8.txt` 的测量完全一致，说明两边是同口径对比。
另已确认 `c048_61min.py:64` 为 `enable_hallucination_reset=False` —— **该结果未使用 reset 兜底**，符合 C-036 的要求。

**3. 真实质量还要更好**。最差的两个窗口（36 分 62%、46 分 57.5%）是 S=4/D=6/I=132 与 S=7/D=6/I=137，几乎纯插入、替换和删除都接近零，与 hybrid 离线在同一窗口的数字（S=4/D=6/I=132）完全一致 —— 这是 MiniMax baseline 在 Q&A 段漏转，不是你的错误。扣除这两处约 269 个 baseline 缺口后，等效 WER 约 5.7%。

**4. 一处遗留偏差（非阻塞，但请处理）**：`seg_stream.py:211` 的 finish 预算仍是 `max(64, max_new_tokens)=64`，而官方是 `first_max_new_tokens`（160 ms 时 1-2，640 ms 时约 8）。这是 C-047 表格里你自己列出的差异项，看起来没有一并改。它可能正是 8.17% 与 CUDA 7.69% 之间残差的一部分。请做一次受控实验：只改 finish 预算为 `first_max_new_tokens` 口径，其余不动，跑 61 分钟，报告 WER / 插入 / RTF。若有改善就设为默认；若无改善，在报告里写明"已验证无影响"即可。

**5. 收尾任务**：
- `transcribe_stream.py` 默认已是 segment encoder + INT8 + adaptive（已确认），保持。
- 更新 `README.md` / `PROJECT_REPORT.md`：精度表改为与 **MiniMax 云端 asr-1.0** 对比（不是 CUDA），写明三个根因及其修复顺序（① optimum 导出的 encoder 丢失全局注意力；② 窗口计数 bug；③ `max_new_tokens` 固定 32 错译了官方自适应预算），并保留 CUDA 不分段 240-300 s 撞 `max_source_positions` 的 OOM 验证结论（这回答了用户最初的反馈：CUDA 和 OV 都需要 VAD 切句）。
- C-043/C-044 的量化产物（`ov-int8-lmfp16-past`、`ov-int4-lmfp16-past`、`ov-mix*-past`）标注为已证伪的探索路径，可从默认路径移除，报告中保留结论。
- 完成后合并到 `origin/c038-v2-ir`，设 WAITING_REVIEW 做最终交付确认。

## C-050 [NORMAL] 2026-10-15 10:05 — 中英混合音频测试：口径、已知风险与必查项
用户正在准备一段中英文混合音频做双语识别测试。在跑之前请注意以下几点。

**1. 音频与放置**：16 kHz 单声道 wav，放 `test_audio/`。把时长、采样率、以及中英大致比例写进 STATUS。如果源文件不是 16 kHz 单声道，用 ffmpeg 转换并保留原始文件。

**2. 语言参数**：`force_language` 必须保持 **None（自动）**，不要设成 Chinese 或 English。混合音频里模型会逐 chunk 自己判定语言，强制单一语言会破坏另一种语言的输出。

**3. 自适应预算的中文分支（重点）**：我已确认你在 `streaming_asr.py:213-224` 实现了 `_is_last_token_chinese` 和中文预算翻倍，与官方 `example.py` 一致 —— 这一点做对了，而且对本次测试至关重要：中文每秒的字数远多于英文每秒的词数，预算不翻倍会导致中文段被截断（表现为删除错误 D 升高，而不是之前的重复插入）。请在跑测试时**记录中文分支的触发次数**，以及中英段各自的平均生成预算，写进报告。如果中文段的 D 明显高于英文段，就是预算仍然不够，届时报告数据即可，先不要自行改参数。

**4. 语言标签抖动**：官方逻辑里 `raw_decoded` 带 `language XXX<asr_text>` 前缀，中英切换处模型给出的语言标签可能在 chunk 之间翻转。请记录每个 chunk 解析出的 `lang` 值，统计翻转次数；如果翻转伴随文本回退或重复，这是混合场景特有的新问题，需要单独报告（不要用 reset 掩盖）。

**5. 中文去空格分支**：`streaming_asr.py:308` 的 `if state.force_language == "Chinese" or lang == "Chinese"` 会触发那条去空格正则。该正则只删除**两个中文字之间**的空格，英文词间空格不受影响 —— 逻辑上是安全的。但请在混合段落上实际抽查几句，确认英文单词没有被粘连。

**6. 评分口径**：我这边的对比脚本已改为**中文按字、英文按词**（混合错误率 MER）。改之前整段中文会被当成一个 token，错误率毫无意义；改后英文结果完全不变（adaptive 仍是 8.17%、CUDA 仍是 7.69%），所以历史对比依然有效。**不要用英文那条 ≤11% 的线直接套用到混合音频**：这是不同的音频、不同的 baseline，没有可比性。请分别报告：整体 MER、中文为主的段、英文为主的段、重复 4-gram、RTF（P50/P95/max）。

**7. baseline 由 reviewer 生成**：音频下载好后告诉我路径，我用 MiniMax asr-1.0 跑一份独立 baseline 再算 MER（混合音频我不会传 language header，走自动识别）。**你不需要自己调 MiniMax**。

**8. 与 C-049 的关系**：中英混合测试属于**额外验证**，不替代 C-049 的收尾项。特别是第 ① 项（finish 预算 `max(64,...)` vs 官方 `first_max_new_tokens`）在中文下可能影响更大 —— 中文预算翻倍后，段尾 64 的固定预算超发更严重。建议把这个受控实验**在英文和中英混合两段音频上各做一次**，一并报告。
