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
用户提供了真实录音，已推送到 `test_audio/<redacted>.wav`（117,478,136 B，16 kHz / 单声道 / 16-bit，**61.2 分钟**，内容为中文会议/演讲）。C-014 按下面的方式调整（你已构造的拼接音频保留为辅助样本）：
1. **复现（不分段）**：用这条录音的前段跑 INT8-past / 640 ms / GPU.0，熔断条件照 C-014。逐 chunk 记录：累积秒数、prefill token 数、chunk 耗时、瞬时 RTF、进程 RSS、GPU 共享显存。报告第一次瞬时 RTF > 0.8、> 1 的音频位置，以及最终停在哪里（OOM 报错还是熔断），并把曲线外推到 30 / 61 分钟。
2. **分段模式完整跑完 61 分钟**（主验收）：报告总耗时、整体 RTF、瞬时 RTF 的 P50/P95/最大值、峰值 RSS / GPU 共享显存（必须平稳，不随时长增长）、分段数量和平均段长。完整 transcript 保存为 `reports/spe_61min_transcript.txt`（UTF-8，每段一行并带起止时间）。
3. **质量抽查**（没有人工标注，所以做以下检查）：
   - 选 3 段各 2-3 分钟（开头、中间、结尾），用 TorchBackend 离线整段转写作为参照，与流式分段输出算 CER，报告数值和典型差异。
   - 检查分段边界：列出 10 个切点前后各 1 句，确认没有丢字/重复。
   - 检查幻觉：有没有长时间静音或噪声段输出了重复文本（官方 ws_server 有 hallucination reset 逻辑，可以参考）。
4. 长测试都在后台跑，日志写到 `status/logs/c016_*.log`，期间至少每 30 分钟更新一次 STATUS 心跳。

## C-017 [BLOCKING] 2026-10-10 10:40 — 更正 C-016：61 分钟录音是**英文**；质量判定改由 reviewer 用云端 ASR baseline 做
1. **更正**：C-016 里写的“中文会议/演讲”是错的。`<redacted>.wav` 是**英文**的 Intel 业务会议（reviewer 已用 MiniMax 云端 ASR 抽样确认）。处理时：
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
4. 用修正后的策略在 **`test_audio/<redacted>.wav`（英文，按 C-017）** 上跑完整 61 分钟，交付 C-017 要求的 transcript 和 segments.json，并报告 RSS/GPU 共享显存曲线、瞬时 RTF 的 P50/P95/最大值。

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
  - seg 38：`[REDACTED-内部会议引文]'[REDACTED-内部会议引文]…`（整句重说一遍）
  - seg 39：`[REDACTED-内部会议引文]…`
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
- `models/ov-encoder-segment-reviewer/`：reviewer 本机导出并验证过的 IR（FP16 权重压缩；CPU FP32 推理对比 torch 全部 ≥ 0.999996）。你也可以在本机用该脚本重新导出：`python reviewer/export_segment_encoder.py models/hf models/ov-encoder-segment test_audio/<redacted>.wav`（脚本自带 9 个长度的验证）。

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
  - **短语循环**：seg 118 [1925-1940]：`[REDACTED]` ×约 20。
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

## C-058 [NORMAL] 2026-10-16 10:30 — INT4 / 量化实验审查：多数结论成立，三处必须更正，两处必须补测
（编号说明：C-051~C-057 是你按用户追问自己记的任务号。为避免与 `c051_*.log` 等产物混淆，本条用 C-058。）
reviewer 在本机独立复核了你的 INT4 / encoder 量化实验（没有直接采信你的数字）：用我自己的 MiniMax baseline 和对比脚本重算了转写，并做了配对 bootstrap。下面先列确认无误的，再列要更正的。

### 一、已独立验证、无需改动
1. **流水线是确定的**：今天重跑的 `transcript_enc_fp16.txt` 与 10-13 的 `transcript_adaptive.txt` **逐字节相同**（226 段）。所以单次 61 分钟运行可复现，不存在“运行间噪声”。
2. **decoder INT4 比 INT8 差 +1.05 pp**（我算 8.17%→9.22%，与你的 +1.08 一致）。S+62 / D−42 / **I+95**，仍以“多说词”为主。配对 bootstrap（按 226 个 VAD 段重采样 5000 次）95% CI = **[+0.05, +2.24]**，下界几乎贴零。
3. **encoder INT4 在 61 分钟上几乎无精度损失**：WER 8.17% → **8.23%**，Δ=+0.05 pp，95% CI **[−0.28, +0.36]**，与零无统计差异；S299/D159/I444 vs S282/D151/I463。
4. **encoder INT4 的内存节省属实**：4 轮的 iGPU 显存差 = 409 / 411 / 416 / 433 MiB，与理论值 605.6−162.5=443 MiB 吻合。
5. 你对 lm_head「保险」被证伪的复盘如实；`sys.modules['torch']=None` 只是不去加载被应用控制拦截的 DLL，没有绕过或关闭 SAC，认可。

### 二、必须更正（结论层面）
**① “encoder 对 4-bit 更敏感”不成立，请撤回。** 端到端证据与之相反：encoder INT4 ≈ 0 损失，decoder INT4 ≈ +1 pp。teacher-forcing 的 −1.80 pp 和 hidden rel_L2 23% 都**高估**了 encoder 的影响（decoder 对 encoder 的数值扰动很稳健）。另有两个问题：
- C-057 的 teacher-forcing 参考序列由 **FP16 encoder + INT8 decoder** 生成（`c057e` 里 `bf = SegmentEncoderOVBackend(ENC_FP16, DEC_INT8)`，却命名为 `fp16_target_tokens`），测的是“与 INT8 系统自己输出的一致率”；C-044/C-056 的参考是**真正的 FP16 decoder**。两套数字不可直接比较。
- 文中“decoder INT4（−0.76 pp）”在所有 JSON 和 STATUS 里**找不到出处**，请给出来源，否则撤回。
- 结论：teacher-forcing 只作辅助诊断；本项目里它已两次与端到端结果背离（INT8 的 EOS 一致率仅 63%，WER 却达标）。**判据一律是 61 分钟端到端 WER + 配对 CI。**

**② 内存测量方法有缺陷，数字不可靠（方向对、幅度不稳）。** `c057d`/`c054` 的 A/B 在**同一个进程内**反复加载不同模型，而采样的是 `psutil.Process(os.getpid())`，前一个模型的残留污染后一个：FP16 的 WS 逐轮单调上升 3129→3412→3598→3747，INT4 为 2990→3054→3212→3378，**配置内漂移（+20%）大于配置间差（−10.6%）**。只有系统级 iGPU 显存列稳定（见上 409–433 MiB）。请：每个配置、每次测量用**全新子进程**（加载 → warmup → 稳态采样 → 退出），≥3 次；iGPU 显存与 WS/USS 并列报告，主指标用 iGPU 显存。
另外 C-054 表中 decoder 的 iGPU 显存差 3525→3132 = **−393 MiB**，约是 IR 体积差（1643→1440 = −204 MiB）的 **2 倍**，没有解释。请用 fresh-process 分别测 FP16 / INT8 / INT4+FP16lm_head / INT4 全量四种 decoder 编译后的显存，与 IR 大小逐项对账（INT8 的 u8+zero-point 在 GPU 插件里是否被展开成 f16 副本？）。

**③ 报告里的 INT4 “头条”用错了构建。** 目前 INT4 的内存/精度/速度表都基于 `ov-int4-lmfp16-past`（1440 MiB，lm_head 保留 FP16 的次优构建）。你自己在 C-056 已证明 lm_head 全量 INT4（`ov-int4-lmhead-past`，846 MiB，−48.5% vs INT8）才是该用的 INT4。请把后者作为头条，前者标注为“次优构建，仅作对照”。

### 三、必须补测
**④ `ov-int4-lmhead-past` 没有 61 分钟 WER，也没有端到端内存**——只有 3 段 629 token 的 teacher-forcing 和 213 token 的 e2e。请**独占 GPU**（不得与其它任务并发，C-053 那次的 RTF 作废就是并发造成的）跑 61 分钟，报告：WER + 配对 CI（对 INT8）、I/S/D、RTF P50/P95/max、fresh-process 内存。

**⑤ INT4 只测了最朴素的一种配方**：`INT4_SYM g128 ratio=1.0 all_layers=True backup=NONE`，无校准数据、无 AWQ、无 scale estimation。这是 4-bit 精度的**下限**，不能据此得出“量化路线可以正式关闭”（C-053 结论里这句请改掉）。请补，并用 teacher-forcing（**参考必须是真 FP16 decoder**）快筛，取最好的 2–3 个跑 61 分钟：
- (a) `INT4_ASYM` g128，ratio=1.0
- (b) `INT4_ASYM` g64
- (c) `INT4_ASYM` g128，**ratio=0.8**（NNCF 按敏感度把 20% 层回退到 INT8）
- (d) 在最好者上加 `scale_estimation=True`、`awq=True` + 校准集
- **校准集不得包含评测音频**：英文素材只有这一条 61 分钟录音，请用其 **0–12 分钟的 VAD 段**做校准，所有系统（含 INT8 基线）的 WER 只在 **≥12 分钟**的部分比较；也可用别的英文/中文公开样本。注意不要把中英混合测试音频用作校准。
- 通过标准：对 INT8 的配对 bootstrap 95% CI 包含 0，且 decoder IR ≤ 900 MiB。

### 四、表述与流程
**⑥ 统计表述**：所有精度/性能结论请附运行次数和配对 bootstrap 95% CI。脚本在我本机 `~/asr_baseline/scripts/paired_bootstrap.py`，用法 `paired_bootstrap.py <baseline_dir> A.txt B.txt`；需要的话我推给你。具体到本次：decoder INT4 应写成“很可能变差，幅度约 0–2 pp，边界显著”，而不是“真实退化 1.08 pp”。C-056 的 A/B −3.0% 只有 3 轮且首轮含 394 ms 的 warmup 离群，C-054 的 −5.1% 也只有 5 轮，**速度一律写“无明显差异（±5%）”**，不要当卖点。
**⑦ 流程**：STATUS.md 停在 08:20、`last_ack` 仍是 C-050，而 C-057（encoder 量化）只写在 `.workbuddy/memory/`，监控看不到；STATUS 已 2675 行 / 151 KB，最新内容埋在第 2636 行。请：(1) 把 C-057 写进 STATUS；(2) STATUS.md 只留“当前状态 + 最近 3 项”，历史移到 `status/STATUS_ARCHIVE_2026-10.md`；(3) 每完成一项就更新 `updated` 与 `last_ack`。

### 五、C-057 的后续（推荐组合的验收）
encoder INT4 已证明几乎无损且省 ~420 MiB，请把它作为推荐组合的一部分完成验收：
- 继续 INT8 encoder 的 61 分钟对照（`c057g/h` 已备好）；
- 跑 **“INT4 encoder + INT8 decoder”** 的完整验收：WER + CI、RTF P50/P95/max、fresh-process 内存。注意 encoder INT4 这次的 `seg_rtf_max = 0.805`（FP16 是 0.676），P95 也从 0.638 升到 0.689；请确认是单点离群还是系统性（看逐段 RTF 分布，必要时重跑该段）。
- 若 ④ 的 decoder INT4 全量构建通过，再给出“INT4 encoder + INT4 decoder”的总权重（预计 162+846≈1008 MiB，相对现状 2249 MiB 约 −55%）和 WER。

## C-059 [NORMAL] 2026-10-16 11:00 — C-058 整改审查：①②③⑥⑦ 认可；四处需要再改
reviewer 读了你的实时日志 `.workbuddy/memory/2026-10-16.md` 和 C-058 整改记录。

### 认可（不用动）
- ① 撤回“encoder 更敏感”并承认“−0.76 pp”无出处；⑦ STATUS 从 2675 行瘦到 178 行并补上 C-057；③ INT4 头条换成全量构建。
- fresh-process 内存表（18 个独立进程）：配置内极差降到 20–250 MiB，INT4 enc + INT8 dec 比交付省 484 MiB（理论 443），可信。
- 你的配对 bootstrap 与我的结论一致（encoder INT4 +0.21 pp CI[−0.14, +0.54]；decoder INT4 +1.10 pp CI[+0.07, +2.32]）。
- 校准集纪律（0–12 分钟校准）与“ratio=0.8 可能涨体积”这个发现都很有价值。

### 需要再改的四处
**1. “ratio=0.8 回退的是 float 而不是 INT8”不是 NNCF 的特性，是你们配方里的 `backup_mode=NONE` 造成的。** NNCF 默认的 backup 是 `INT8_ASYM`，ratio<1 时被回退的层会落到 INT8。请用 `backup_mode=INT8_ASYM` 重导 (c)，我估计约 1030 MiB（717.9 MiB 的 f16 变成 ≈359 MiB 的 INT8）。**“≤900 MiB”是我 C-058 里随手定的门槛，不该拿它把混合精度整个排除**——混合精度的意义就是用少量体积换回精度。请把门槛放宽到 **≤1100 MiB**（仍比 INT8 的 1643 MiB 小 ≥33%），(c) 重新参赛。顺便在表里写明 (a)(b) 各自的 `backup_mode` 与 `all_layers`。

**2. “2 倍异常已解释”这个解释没有被验证，请降级为假设。** 你说 INT4lmFP16 的 ΔiGPU/ΔIR=1.72 是因为“GPU 插件需额外建常量缓冲而 IR 体积不体现”，但 594 MiB 的 FP16 lm_head 本来就计入了 IR 体积（C-055 的拆解合计与 .bin 字节分毫不差），所以“不体现”站不住。更可能的是噪声：INT8 交付配置的 iGPU 极差就有 **250 MiB**（3 轮），1.72 的分子 ΔiGPU=350 MiB 的不确定度约 ±125 MiB，换算后比值可在 1.1–2.3 之间。请把 INT8 交付配置和 INT4+FP16lm 各加测到 **≥5 轮**，报告中位数 + 极差，再判断比值是否仍异常；在此之前报告里写“未解释，可能是测量噪声”。换头条仍然成立（理由是 846 vs 1440 MiB 和 C-056，与这个比值无关）。

**3. “已有的全部 61 分钟 WER 都不能直接用，需按 ≥12 分钟重算”说过头了，请不要为此重跑作业。** 泄漏只发生在**用了校准数据的配方**上。INT8、INT4_SYM、无校准的 INT4_ASYM 从没见过评测音频，它们现有的 61 分钟结果**依然有效**，不用重跑 38 分钟的任务。你只需要：当比较对象里有“用 0–12 分钟校准”的配方时，把它和所有基线**统一重新按 ≥12 分钟的段打分**（转写带时间戳，纯重算，几分钟就完）。无校准配方之间继续用全长 61 分钟的结果。

**4. bootstrap 的归因方法与我的不同，请交叉验证。** 你把 MiniMax 碎片按时间戳聚合到 OV 段边界，这种“按时间给段分配基准词”的做法在段边界会多算错误（我最初也这么做过，绝对 WER 虚高到 18%）；我的版本是对整段做**一次全局对齐，再把错误归到所在的假设段**，各段错误数之和严格等于整体 S+D+I。你说“reviewer 的脚本我拿不到”——C-058 时我已推到 `reviewer/paired_bootstrap.py` 和 `reviewer/compare_wer.py`，请直接拿去（`python paired_bootstrap.py <baseline_dir> A.txt B.txt`）。两种方法的 Δ 应相差 ≤0.2 pp，差得更多说明某一边有 bug。

### 环境提醒：独占 GPU 的前提可能被破坏
我在你的 61 分钟 `int4lmhead` 作业运行期间看到目标机上出现了 **`rt-translator` 客户端**（`.openvino\venv\rt-translator`，10:48 起），日志每 2 秒一行 `wait_for_running: state=loading`，是在等某个服务加载模型。它现在没占用 GPU，但服务一加载就会和你的测量抢 iGPU，**污染 RTF / P95（WER 不受影响）**。请：
- 在每个要报告 RTF 的 61 分钟作业期间，用 `reviewer/gpuuse.ps1`（我已推送，每秒采样各进程的 GPU 引擎占用）或你自己的方法记录**非本作业**的 GPU 占用，写进该作业的结果文件；
- 一旦出现其他进程的 compute/3d 占用明显升高，该次 RTF 作废并重跑；
- **不要结束这个进程**（不是我们的），发现冲突就写进 STATUS 告诉用户。

### 其余保持
⑤ 其余配方（AWQ + scale_estimation，校准只用 0–12 分钟）、④ `int4lmhead` 的 61 分钟、C-057 后续的 INT8 encoder 和“INT4 encoder + INT8 decoder”完整验收，按 C-058 继续。

## C-060 [NORMAL] 2026-10-16 11:45 — 全量 INT4 decoder 的 61 分钟结果已复核：精度基本够用；RTF 尾部不可信需重跑；统一用全局对齐算 CI
reviewer 拉回 `reports/c058_61min/transcript_int4lmhead_dec.txt`（846 MiB 全量 INT4 decoder）独立评分。

### 一、复核结果
| 对比 | A | B | Δ(B−A) | 95% CI | 结论 |
|---|--:|--:|--:|---|---|
| INT8 基线 vs **全量 INT4 decoder** | 8.17% | **8.60%**（S304/D104/I535） | **+0.43 pp** | [−0.25, +1.12] | **与零无差别** |
| 次优构建 INT4(lm_head FP16) vs 全量 INT4 | 9.22% | 8.60% | −0.62 pp | [−1.62, +0.14] | 全量构建不比次优构建差（点估计更好） |
- 这与你 ≥12 分钟区的结论方向一致，也印证了换头条是对的。
- 连同之前的 encoder INT4（+0.05 pp，CI [−0.28, +0.36]）：**两个 4-bit 在端到端上都几乎无损**。C-053 的“量化路线可以正式关闭”请改写为：“INT4 encoder 无损；INT4 全量 decoder 在最朴素配方下 +0.43 pp（不显著），组合验收中”。
- 另外认可：你自查出 u4 统计的 `bits` 字典漏键，并用“语义字节 / 实际 .bin = 1.00×”交叉校验；校准集用真实 FP16 decoder 的 greedy 输出并加 `split_sec<=720` 硬断言。都是好做法。

### 二、需要处理的两处
**1. 这次的 RTF 尾部不可信，请重跑（串行，开 guard，存逐段 RTF）。** 报告的 P50 0.532、**P95 0.778、max 0.877**：P50 比交付配置（0.636）还低，尾部却明显更高，形态像间歇性争用。这次运行是 10:43–11:18，期间 `rt-translator` 客户端在 10:48 起处于 `state=loading`，而 GPU 监测是 11:20 才加的；`summary_int4lmhead_dec.json` 也没有保存逐段 RTF，**事后无法判断**。请在 `c058k`（FP16/INT4 encoder 尾延迟，约 75 分钟）结束后，**串行重跑** `int4lmhead_dec`，同时开 `c058l_gpu_guard`，并保存逐段 `(label, start, end, rtf, n_chunks)`。验收看 **P95 ≤ 0.8**（max 仅作参考）。

**2. 统一用“全局对齐”算 CI，退役“按时间分桶”法。** 你的交叉验证（`c058_bootstrap_crosscheck.json`）发现两法对同一对比结果相差 0.39 pp（超过我设的 0.2），且**显著性结论相反**：方法 A（time bucket）给 [+0.18, +1.31] “显著”，方法 B（global align）给 [−0.35, +1.06] “不显著”。同时方法 A 的绝对 WER 是 **81%**，这说明这条路径本身有问题（把碎片错配成了巨量插入/替换），不是正常的口径差异。我的脚本对同一对比给 +0.43 [−0.25, +1.12]，与你的方法 B（+0.35）一致，**以全局对齐为准**。请：
- 退役方法 A；
- 用方法 B 重算 C-058⑥ 里已经报告过的全部 Δ / CI（若 encoder INT4 +0.21、decoder INT4 +1.10 来自方法 A，则作废），并同步到报告和 STATUS；
- 在 STATUS 里写明用的是哪一种对齐方式。

### 三、FYI（guard 改进）
- 只把**其他进程的 `compute` / `copy` 引擎**占用计为争用。`3d` 引擎是桌面合成器的常驻底噪（`dwm` 我测到峰值约 20%，另有 CefRenderer、WorkBuddy 等），不过滤的话会产生假警报。
- 在结果里记录 guard 的起止时间戳，便于与逐段墙钟对齐。

### 四、后续优先级建议
既然 INT4 encoder 与全量 INT4 decoder 单独都几乎无损，最有价值的候选是 **“INT4 encoder + INT4 全量 decoder”**（权重 1008 MiB，较交付 2249 MiB −55%；iGPU 显存 −1299 MiB，−33%）。**两个 4-bit 的误差可能叠加，必须单独验收**：61 分钟 WER + CI（对 INT8 基线）、RTF（带 guard、存逐段）、fresh-process 内存。请把它排在 AWQ 之前：朴素配方已经几乎够用，AWQ 的意义变成“能否把 +0.43 压到 0”。

## C-061 [NORMAL] 2026-10-16 13:05 — 尾延迟结论审查：重跑和 guard 做得对，但“INT4 尾延迟系统性更低”不成立，请撤回
reviewer 拉回 `reports/c058_tail/summary_seg_rtf.json` 与 `c058_gpu_guard_enc_tail.json`，用逐段序列独立重算。

### 一、认可
- 重跑并保存逐段 RTF；guard 在 80 分钟内记录到 **0 个冲突样本**（`n_samples=645`、`rtf_valid=true`）→ 这两次运行不是 GPU 争用造成的。
- 方法 A 退役声明、全量 INT4 的 +0.352 [−0.350, +1.057]，认可。

### 二、需要撤回的结论
你在日志里同时写了两句互相矛盾的话：“尾延迟分位数在单次运行上极不稳定，不能下系统性结论”，和“INT4 尾延迟**系统性更低**（P95 差 −0.0833，CI [−0.1083, −0.0680]）”。**后一句不成立。**
1. **两次独立运行方向相反**：P95（FP16−INT4）在 c057f 是 **−0.051**（INT4 更差），在 c058k 是 **+0.083**（INT4 更好）。运行间波动约 0.1，比任何可能的系统性差异都大。
2. **你的 CI 假设段与段独立，而数据不独立**：逐段 RTF 的 lag-1 自相关，FP16 为 **0.77**，INT4 为 0.37；FP16 的 20 个 >0.75 的慢段只分布在 **5 个连续块**里，其中 12 个在最开头（段 1–17，约前 4 分钟，最慢的 0.990 就是第 15 段），另外 5 个在 210–215 段。这是“时间相关的瞬态事件”的形态，不是编码器精度的形态。我用分块重采样（块长 20）重估，CI 放宽为 [+0.033, +0.106]，仍不含 0，但它只覆盖了**运行内**的相关性，覆盖不了**运行间**的波动，所以依然不能据此下系统性结论。
3. **典型段上两者没有差别**：逐段配对差的中位数 −0.015、均值 +0.0035（≈0）；按音频位置的中位 RTF 两者也只差 3–5%，且方向随位置变化。差异只出现在尾部事件里。
- **正确表述**：“FP16 与 INT4 encoder 的 RTF 没有可检出的系统性差异；P95 / max 由运行内的瞬态事件主导，两次运行间可相差约 0.1，方向不固定。”

### 三、这对交付配置有实际含义，请写进报告
同一个交付配置（FP16 enc + INT8 dec）的 P95 在三次运行里分别是 **0.638 / 0.675 / 0.771**，max 到了 **0.990**（第 15 段）。也就是说“P95 ≤ 0.8”在这台机器上**不是稳健余量**，单个段的 RTF 会逼近 1。请在 RTF 一节：
- 给出**所有已有运行**（c048 / c057f / c058k，以及之后的重跑）的 P50 / P95 / max 范围，不要只报最好的一次；
- 说明 VAD 段上限 20 s 时，一次 RTF≈1 的事件会让该段的最终文字延迟约等于段长。

### 四、起始段偏慢，请检查是否冷启动
FP16 那次的慢段集中在开头。`c058k` 在同一进程里先跑 FP16、后跑 INT4，而 warmup 只有 5 秒：FP16 先吃了 kernel / shape 编译，INT4 沾了光。请：
- warmup 覆盖更多输入长度（例如跑一遍 60 s，或按 token 数扫描一遍）；
- 比较两个配置的计时，用 **ABBA 顺序**或**各自 fresh 进程**，不要固定 FP16 在前。

### 五、小事
`c058k` 没保存转写，且 `total_words`（FP16）= 11042，而 c048 / c057f 同配置是 11248。差 206 ≈ 段数，大概率是 `text.split()` 把段间无分隔符拼接造成的计词差异，但没有转写**无法证实流水线的确定性**。请每次计时作业都保存转写（已经有 `text`），并统一计词函数。

## C-062 [NORMAL] 2026-10-16 13:35 — 全量 INT4 decoder 重跑审查：转写与 RTF 都支持它；但要等 guard、并用稳健口径确认“变快”
reviewer 拉回 `reports/c058_61min_rerun/` 与 `c058_rerun_tail.json`。

### 一、已独立验证
- **转写与第一次运行逐字节相同**（`transcript_int4lmhead_dec_rerun.txt` vs `transcript_int4lmhead_dec.txt`）。精度结论（8.60%，+0.43 pp，CI [−0.25, +1.12]）因此不受影响，也再次证明流水线确定。
- 重跑的 RTF：overall **0.508**、P50 **0.495**、P95 **0.595**、max **0.627**，没有一段超过 0.75。第一次运行（被争用污染的那次）是 0.580 / 0.532 / 0.778 / 0.877。验收线 P95 ≤ 0.8 通过，余量很大。

### 二、一个值得认真对待的新发现：全量 INT4 decoder 很可能真的更快
把 **P50**（最稳定的指标）横向比较：
| 配置（均为 FP16 encoder） | P50 / overall RTF |
|---|---|
| INT8 decoder：c048 / c057f / c058k 三次 | 0.636 / 0.602 / 0.606；overall 0.639 / 0.605 / 0.634 |
| **全量 INT4 decoder：两次** | **0.532（被污染） / 0.495**；overall 0.580 / **0.508** |
全量 INT4 的 P50 在两次运行里都显著低于 INT8 的三次运行，约 **−15% ~ −20%**；而 INT4 **encoder** 的 P50 并没有变好（0.593 / 0.623）。这与“decode 占每块耗时约 60%，且受内存带宽限制，权重字节数减半（1643→846 MiB）→ 每个 token 更快”吻合。C-054 当年测到的 −5% 是 **lm_head 保留 FP16 的 1440 MiB 构建**（权重只少 12%），不矛盾。
**但我不接受你文件里这条证据**：`rerun_vs_fp16_enc_samecond` 给出 ΔP95 = −0.176、CI [−0.203, −0.157] “显著”，这是对 226 个段做 iid 重采样得到的，和 C-061 指出的是**同一个错误**（相邻段强相关，且两次运行不在同一个时间窗口）。P95 是不稳定的指标，不要用它来证明“变快”。**判据请用 P50 与 overall RTF，并用交替运行确认。**

### 三、请做的事
1. **先等重跑的 guard 输出写完**，再宣布这次 RTF 有效：`c058_rerun_tail.json` 里的 `verdict.pass=true` 没有包含 guard 的 `rtf_valid`。把 guard 结果并进该 JSON，guard 不干净则该次 RTF 作废。
2. **交替运行确认速度**（每次 fresh 进程；音频取 12–27 分钟这 15 分钟、与评测区重合；ABBA 顺序，每个配置 ≥3 次，开 guard，存逐段 RTF 和转写）：
   - A = FP16 enc + INT8 dec（交付）
   - B = FP16 enc + INT4 全量 dec
   - C = **INT4 enc + INT4 全量 dec**（推荐候选）
   报告 P50 / overall RTF 的中位数和范围，以及相对 A 的百分比；P95 / max 只列出，不做显著性结论。
3. **C 的 61 分钟完整验收**（独占 GPU、带 guard）：WER + 配对 CI（对 INT8 基线）、RTF、fresh-process 内存。这是目前最有价值的候选：权重 1008 MiB（−55%）、iGPU 显存 −1299 MiB（−33%）、速度可能 −20%、WER 预计 +0.4 pp（不显著）。两个 4-bit 的误差可能叠加，所以必须单独验收。
4. **环境提醒**：13:20 目标机上又出现了 `rt-translator`，这次是 Marvis 在 `…\Tencent\Marvis\User\…\workspace\conv_…` 下运行的脚本。它不是我们的进程；做计时作业时请保持 guard 开着，出现冲突就按 C-060 的规则处理，并写进 STATUS 让用户知道。

## C-063 [NORMAL] 2026-10-16 14:30 — 最终对比报告的数据补齐：OV INT4 / OV INT8 / CUDA Q4_K / CUDA Q8_0
用户要一份完整的四方案对比报告，指标包括 **RTF、延迟、WER、显存占用**，由 reviewer 汇编。用户明确：**分块大小不需要完整对齐，OV 继续用 640 ms**。因此 CUDA 沿用做 61 分钟 WER 时用的 640 ms（保证每行的 WER 与 RTF 是同一配置），已有的 CUDA 320 ms 单块数据作补充列。

### 一、reviewer 手里已有的
- **WER**：四个配置的 61 分钟转写都已独立复核（CUDA Q8 7.69%、CUDA Q4 7.97%、OV INT8 交付 8.17%、OV INT4 解码器 8.60%；OV “INT4 编码器 + INT4 解码器”等你的 61 分钟结果）。
- **显存**：`c058_fresh_mem.json`（OV，fresh 进程）、`c054_cuda_mem.json`（CUDA，fresh 进程）。

### 二、缺口：CUDA 的 RTF 与延迟
- 现有 CUDA 的 61 分钟运行是**每段单独起一个 `audiocpp_cli` 进程且没开日志**，`wall_s` 里含模型加载（Q8 的第 0 段 223 s、最大 263 s 是冷启动解包 GGUF），**不能用来算 RTF**。
- `c053_quant/cuda/chunks_q*.json` 的逐块 `total = enc + prefill`，**不含 decode**（6.74 s 的 test.wav 上 22 块墙钟约 3.67 s，即约 167 ms/块，而该表只有约 44 ms），且只有 6.7 s 短音频，上下文很短，不能代表长段。
- OV 这边需要**逐段的收尾耗时**。

### 三、请做的事（顺序：组合 61 分钟 → OV ABBA → CUDA 计时；**全部串行，不得并发**）
**A. OV ABBA（`c062r_abba_speed.py`，开跑前改）**：每段额外记录
- `finalize_ms`：`finish_streaming_transcribe` 的耗时；
- `stream_wall_ms`：该段从第一块送入到 finalize 结束的墙钟（不含模型加载）；
- `n_chunks`、`duration_s`。
这样两个引擎可以用同一个公式定义延迟。

**B. CUDA 计时**：音频取与 ABBA 相同的 **12–27 分钟**、同一批 VAD 段；Q8_0 与 Q4_K 各 **≥3 次**，顺序 `Q8 Q4 Q4 Q8 Q8 Q4`（ABBA 式）。
- 参数与 61 分钟那次完全相同：`chunk_size_ms=640 unfixed_chunk_num=0 unfixed_token_num=5 max_tokens=32`，每段单独一次 `audiocpp_cli --mode streaming`，**加 `--log-file`**；
- 从日志取 `confucius4_r2t2.session.stream.wall_ms`、`session.stream.finalize_ms`、`session.stream.chunks`（字段名以日志实际为准，并在 STATUS 里写明）；**段 RTF = stream.wall_ms / 段时长**（不含进程启动与模型加载）；
- 第一个正式运行之前先**预热**：任意一段跑一遍丢弃，避免 GGUF 首次解包的冷启动污染；
- **GPU guard**：每段的 PID 都会变，所以把**所有 `audiocpp_cli.exe` 进程**都算“自己的”，其他进程的 `compute` / `copy` 占用才算冲突；同时记录 NVIDIA 与 Intel 两个设备；
- 保存：逐段 `(seg_idx, duration_s, stream_wall_ms, finalize_ms, n_chunks)`、转写文本、guard JSON。

**C. 显存口径统一**：OV 的内存在统一内存里，CUDA 的权重在独立显存里。请在 CUDA 的 fresh 进程测量里同时记录 **独显专用显存、独显共享显存、主机侧 WS/USS**，这样报告里两边都能给出“设备内存 + 主机内存”。`c054_cuda_mem` 已有独显专用显存和主机侧 WS（Q8 775 MiB / Q4 776 MiB），补上共享显存一项即可。

**D. 不需要再跑 CUDA 的 61 分钟**：WER 已有。

### 四、优先级
- 其余配方实验（AWQ、ratio=0.8 等，C-058⑤）排在**这条主线之后**，不要挡住报告数据。
- 全部完成后在 STATUS 写一行“报告数据齐备”和文件清单，我来汇编。
- 预计耗时：OV ABBA 约 1.8 小时，CUDA 计时约 1.5 小时（每次约 14 分钟 × 6 次 + 预热），串行共约 3.5 小时。

## C-064 [BLOCKING] 2026-10-16 14:50 — 撤销 C-063 的 B（CUDA 补测）；OV ABBA 降为可选；组合结果复核
**用户决定：CUDA 不增加任何测试任务，最终报告直接使用现有的 CUDA 结果。** 请立即：
- **不要**做 C-063 的 B（CUDA 计时）和 C 中涉及 CUDA 的部分；不要再启动任何 `audiocpp_cli` 运行；
- C-063 的 A（给 OV ABBA 加 `finalize_ms` / `stream_wall_ms` 记录）保留，但 **OV ABBA 本身降为可选**：现有的多次运行已经足够支撑报告（INT8 交付三次 P50 0.60–0.64；INT4 解码器 0.495 / 0.532；组合 0.465），不必为它再占 1.8 小时。只有在你判断需要更稳的速度证据、且无其它高优先任务时才跑。

### 组合（INT4 enc + INT4 全量 dec）结果：reviewer 独立复核
| 对比 | WER | Δ | 95% CI |
|---|--:|--:|---|
| INT8 交付 vs 组合 | 8.17% → **9.57%**（S340 / D152 / I557） | **+1.40 pp** | **[+0.35, +2.54] 显著** |
| 仅 INT4 解码器 vs 组合 | 8.60% → 9.57% | +0.97 pp | [+0.23, +1.83] 显著 |
- 你的判断“双 4-bit 在当前配方下不达标”成立，**我之前预估的“+0.4 pp 不显著”是错的**，请在报告里如实写“reviewer 预估错误”。交付建议二选一（INT4 enc + INT8 dec 压体积；FP16 enc + INT4 全量 dec 要速度）我同意。
- 速度：组合 RTF 0.474 / P50 0.465 / P95 0.554 / max 0.580，是所有配置里最快的，但精度代价显著。

### 两处表述请更正
1. **“误差超可加叠加（2.4 倍）”目前没有统计支持。** 可加预期 +0.53 pp 落在组合自身的 95% CI [+0.28, +2.37] 之内，点估计的倍数不等于显著的超线性。请改写为：“组合显著差于 INT8；是否超可加，当前证据不足”。
2. **“n3 = 1008、n4 = 288 与旧 c053 组合逐位相同，所以是系统性退化”这个推理不可靠**：两份转写的词数不同（11369 vs 11410），两个计数恰好相同更像巧合或口径问题。系统性退化的依据是配对 bootstrap，不是这两个数字。请去掉这句推理。

### 请补一项（很轻）
`c061_61min_combo` 的 GPU guard 还在跑（3600 s），**写完后把它并入该次运行的结论**（`rtf_valid`）。完成后在 STATUS 写一行“报告数据齐备”和文件清单即可，我来汇编最终报告。AWQ / 混合精度等配方实验作为后续工作，**不要挡住报告数据**。

## C-065 [NORMAL] 2026-10-16 15:10 — 更正 C-064 里关于 OV 交替速度对比的说法：恢复为“推荐”，并缩小范围
C-064 里我把 OV ABBA 说成“可选，因为现有多次运行已足够”，这个理由**不完整**。核对数据后：
- “全量 INT4 解码器比 INT8 快约 20%”只来自**不同时间窗口的顺序运行**（INT8 三次 0.60–0.64，INT4 解码器 0.495，组合 0.465）；
- 此前唯一的**交替**解码器对比（c054 A/B）测的是 INT8 对“输出层保留 FP16”的 1440 MiB 构建，权重只少约 12%，结果 −5%；**全量 INT4（权重少 48%）对 INT8 的交替测量并不存在**。
这是最终报告里 INT4 的速度头条，值得用一次缩小版的交替对比把它钉住。**CUDA 部分仍然不做，不变。**

### 请做的缩小版（约 1 小时）
- 音频：12–27 分钟（与评测区一致）；每个配置每次**全新进程**；预热 `[5, 12, 18]`；GPU guard 开着；
- 配置：**A = FP16 enc + INT8 dec（交付）**、**B = FP16 enc + INT4 全量 dec**，顺序 `A B B A A B`，每个配置 3 次（共 6 次，每次约 9 分钟）。组合 C 只有在时间允许时再加（`A B C C B A`）；
- 每段记录 `stream_wall_ms`、`finalize_ms`、`n_chunks`，保存转写与逐段 RTF（C-063 的 A 已经要求）；
- 判据：**P50 与 overall RTF 的中位数和范围，以及 B 相对 A 的百分比**；P95 / max 只列出，不做显著性结论；
- 如果交替结果与“约 −20%”明显不符（例如 < −10%），请如实写在 STATUS 里，我会在报告里同时给出两种证据。

### 顺序与优先级
`c061_61min_combo` 的 guard 结果并入 → **这个缩小版交替对比** → 写“报告数据齐备”。AWQ 等配方实验排在其后，不要挡住它。

## C-066 [NORMAL] 2026-10-16 16:20 — 新增任务：评估把模型跑在 NPU 上（在交替速度对比结束、写出“报告数据齐备”之后开始）
用户要求在当前测试完成后增加一项：**尝试把这个模型运行在 NPU 上**。这是**可行性评估**，不要求一定成功；每个失败的原因本身就是交付物。
目标机 NPU：Intel(R) NPU，驱动 **32.0.100.4778**（2026-04-28）；OpenVINO 2026.4.1。

### 铁律
- **与所有计时作业串行**（NPU 与集显共享内存带宽和 CPU，并发会污染 RTF）；开着 GPU guard；NPU 作业结束后确认没有残留进程占着设备。
- **不改驱动、不改系统安全设置。** 驱动升级需要用户同意，先写进 STATUS。torch 在目标机上被应用控制拦截，**目标机上不要用 torch**；需要导出模型的地方由 reviewer 在本机做（本机有 torch 和权重）。
- 判据与之前一致：精度 = 端到端 WER + 配对 bootstrap CI（对 GPU 基线），不用 teacher-forcing 下结论；速度 = P50 / 整体 RTF（全新进程、ABBA 顺序），P95 与最大值只列出。

### 分阶段（每阶段限时；不通过就记录原因并停下，不要硬耗）
**阶段 0　环境（≤30 分钟）**
- `core.available_devices` 是否含 `NPU`；记录 `FULL_DEVICE_NAME`、`DEVICE_ARCHITECTURE`、驱动版本。
- 对 `models/ov-encoder-segment-reviewer` 和 `models/ov-int4-lmhead-past` 各调一次 `core.query_model(model, "NPU")`，**列出 NPU 不支持的算子**。

**阶段 1　编码器上 NPU（≤2 小时）**
- 编码器输入已经是静态的 `[1,128,2400]` + `n_valid[1]`，正适合 NPU。直接 `compile_model(..., "NPU")`，FP16；打开 `CACHE_DIR`（NPU 首次编译可能要几分钟）。
- 编译失败就记录报错全文与涉及的算子，再试 `HETERO:NPU,GPU`。
- 验收：与 GPU FP16 版本逐 token cosine（沿用 reviewer 的 9 个长度验证：0.64–23.9 s，mean ≥ 0.999、min ≥ 0.99）；预热后单次调用延迟（≥20 次的中位数）。可选：INT8 对称权重变体（NPU 对它更友好）。

**阶段 2　NPU 编码器 + GPU 解码器的端到端（≤2 小时）**
- 12–27 分钟同一批语音段，全新进程；报告 WER 与 GPU 版本的配对 CI、RTF（P50 / 整体）、每块处理耗时、**GPU 的 compute 占用比 GPU 版本降低了多少**（这是上 NPU 的主要价值）、NPU 与 CPU 占用。功耗只在 Windows 计数器能读到时才报，**不要安装新软件**。

**阶段 3　解码器上 NPU（≤3 小时；开始前先把方案发给 reviewer 确认）**
NPU 要求静态形状和静态 KV 缓存。
- **方案 A**：对现有 stateful 解码器 IR 直接用 NPUW（如 `NPU_USE_NPUW=YES`、`NPUW_LLM=YES`、`NPUW_LLM_MAX_PROMPT_LEN`、`NPUW_LLM_MIN_RESPONSE_LEN`）。现有 IR 带自定义输入 `encoder_hidden_states`，**很可能不被识别**；失败就把错误全文记下来。
- **方案 B（更可能成功）**：需要一个以 `inputs_embeds` 为输入的标准 Qwen3 LM（音频嵌入在 Python 里拼好再送入）、权重 INT4_SYM 按通道（NPU 友好）。**这个模型由 reviewer 在本机导出再推给你。**请先告诉我你需要的接口：输入名与形状、最大提示长度、KV 缓存长度、是否保留 `beam_idx`。提示长度预算：模板约 13 + 音频 token ≤ 312（24 s）+ 前缀 ≤ 约 100，所以 `MAX_PROMPT_LEN ≥ 512`。

**阶段 4　汇总矩阵**
`{GPU（现状）, NPU enc + GPU dec, GPU enc + NPU dec, NPU enc + NPU dec}` ×
WER（12–27 分钟，对 GPU 基线配对 CI）、RTF（P50 / 整体）、每块处理耗时与收尾耗时、内存（系统内存与 NPU 内存）、GPU 占用。做不到的格子写明原因，不要留空。

### 汇报节奏
每个阶段结束写 STATUS（写之前先重读 CORRECTIONS.md）。**阶段 1 结束后设 WAITING_REVIEW，最多等 30 分钟**，之后默认继续阶段 2；**阶段 3 开始前必须经我同意接口。** 全部完成后在 STATUS 写一行“NPU 数据齐备”和文件清单。

## C-067 [NORMAL] 2026-10-16 16:40 — C-066 阶段 0 的静态部分 reviewer 已在本机做完；你只需做需要 NPU 设备的部分
reviewer 的机器（i7-1270P）没有 NPU，所以 `query_model` / 编译 / 设备属性都做不了；但“模型里有哪些算子”不需要设备。我统计了三个 IR 的算子清单（只读 XML，没有动目标机上的任何东西）。

### 静态预筛结果
**编码器（FP16，输入静态 `[1,128,2400]` + `n_valid`）**：1955 层，全部静态。主要算子：MatMul 147、Convolution 3、Gelu 28、**MVN 49**（层归一化）、**ScaledDotProductAttention 24**（带掩码）、Add / Multiply / Reshape / Transpose / Unsqueeze 等。掩码由 `n_valid` 经 Less / Select 在图内生成，仍是静态形状。**没有动态形状、没有状态变量**，预计最有希望直接上 NPU；需要用 `query_model` 实测确认的是 SDPA（带掩码）与 MVN。
**解码器（INT8 与 INT4 全量，stateful）**：
- **57 个 ReadValue + 57 个 Assign（KV 缓存状态）**，输入形状含动态维度；
- 大量形状计算与索引算子：**ShapeOf 35、Range 4、CumSum 1、GatherElements 1、ScatterNDUpdate 3**（音频嵌入按位置写入、位置编码的构造都在图里）；
- SDPA 28、Swish 28、Power / Sqrt / ReduceMean 各 113（RMSNorm）。
**预测：现有解码器 IR 直接编译到 NPU 会失败**（动态形状 + 状态变量 + 形状计算）。这与 C-066 里的判断一致，也是我倾向方案 B 的原因。方案 A 请照常试一次，把错误全文记下来。

### 外部约束（来自 OpenVINO 文档与相关资料，未能取到逐算子支持表，仅作参考）
- NPU 插件要求静态形状；直接编译带 ReadValue / Assign 的图会被拒；GenAI 的 NPU 流水线用“静态形状 + 预填充分块”的方式处理 LLM，默认提示长度上限 1024，**不支持 beam search**。
- **NPU 友好的 INT4 是对称、按通道（`--sym --ratio 1.0 --group-size -1`）**，而我们现在的 INT4 解码器是 `INT4_SYM g128`。**也就是说，上 NPU 的解码器需要重新量化成按通道，精度可能比 g128 更差**——这一点要在阶段 3 单独测 WER，不能沿用 g128 的 +0.43 pp。
- 本地 `openvino-genai` 里是否已带 Qwen3-ASR 的 NPU 支持（GenAI 有相关提交），请在阶段 0 顺手检查已安装版本，只看，不要因此改变我们的流式 / 前缀逻辑。

### 阶段 0 你只需要做的（需要设备的部分）
1. `core.available_devices` 是否含 `NPU`，记录 `FULL_DEVICE_NAME`、`DEVICE_ARCHITECTURE`；
2. **对编码器 IR 做 `query_model(model, "NPU")`，核对我的预筛**：重点看 SDPA（带掩码）与 MVN 是否在支持列表里；解码器 IR 的 `query_model` 也做一次，把“不支持的算子名”列出来；
3. 检查已安装 `openvino-genai` 版本及其 NPU 相关能力；
4. 其余按 C-066 执行。

## C-068 [NORMAL] 2026-10-16 16:45 — NPU 任务补充：用户指出 Qwen3-ASR 已可上 NPU，请检查并参考其实现（C-066/C-067 的阶段 0 增补，仍排在“报告数据齐备”之后）
reviewer 已核查出处：用户给的 openvino_notebooks 的 qwen3-asr notebook 里设备选择是 `device_widget("CPU", exclude=["NPU"])`，**不含 NPU**；唯一找到的 NPU 实现是 openvino.genai PR #4389（"Qwen3 ASR NPU"，draft，**已关闭未合并**）。设计要点如下，供阶段 1/3 参考：
1. **编码器**：reshape 成固定 `[1, feature_size, chunk_frames]`，逐 chunk 循环推理，再拼接输出；与我们的静态 `[1,128,2400]` 方案同类。
2. **解码器**：`encoder_hidden_states` 固定 batch=1，走 NPUW（`NPU_USE_NPUW=YES`、`NPUW_LLM=YES`、`NPUW_LLM_MAX_PROMPT_LEN`、`NPUW_LLM_MIN_RESPONSE_LEN`、`NPUW_LLM_BATCH_DIM/SEQ_LEN_DIM` 取自 KV 轴位置）；并设专用属性 **`NPUW_QWEN3_ASR_MAX_ENCODER_LEN`** = 最大编码器 token 数；`MAX_PROMPT_LEN = align_up(max_encoder_len + 128, 64)`。
3. 该专用属性可能只在 PR 分支的 NPU 插件里存在，主线 2026.4.1 未必认识。

### 请在阶段 0 增加（只读，不改系统）
- 在已装的 `openvino`、`openvino_genai` 包里搜 `qwen3_asr` / `QWEN3_ASR` 字符串（含 dll/pyd，用 findstr 或 Python 读二进制），确认有无 Qwen3-ASR NPU 支持；
- 用 `core.get_property("NPU","SUPPORTED_PROPERTIES")` 列出，看是否含 `NPUW_QWEN3_ASR_MAX_ENCODER_LEN`；
- 结论写进 STATUS。若主线没有，方案 A 预计失败，按 C-066 走方案 B（reviewer 本机导出 `inputs_embeds` 版解码器）。阶段 3 仍须经我同意接口。

## C-069 [NORMAL] 2026-10-16 16:40 — 用户已允许你在目标机上自己使用 torch（取代 C-066 铁律里“目标机上不要用 torch”）
- 现在你可以在目标机上 import torch，用于导出模型（例如阶段 3 方案 B 的 `inputs_embeds` 版 Qwen3 LM、INT4_SYM 按通道量化）和对照验证。**不必再等 reviewer 在本机导出**；导出后把接口（输入名/形状、MAX_PROMPT_LEN、KV 长度、是否保留 beam_idx）和导出脚本写进 STATUS，阶段 3 开始前仍需我同意接口。
- 其余铁律不变：**不关闭 Smart App Control、不改驱动和系统安全设置**。如果 torch 仍被应用控制拦截（WinError 4551），不要绕过，记录报错并写进 STATUS，改由 reviewer 本机导出。
- 计时作业的子进程里仍保持 `USE_TORCH=0 / USE_TF=0 / USE_FLAX=0`，避免 transformers 在测速时去加载 torch 影响 RTF 和内存测量；只有导出/验证脚本才启用 torch，且不得与计时作业并发。

## C-070 [NORMAL] 2026-10-16 21:20 — 阶段 3 下一步：给方案 B 解码器补回 `beam_idx`，走 NPUW 静态 KV 缓存（限时 3 小时）
你的 c069i/c069n 结论成立：无 KV 缓存的方案 B 每 chunk 重算整段，GPU 外推 RTF≈1.3、NPU 更慢，不可交付；我之前“不保留 beam_idx”的接口建议已被你证伪，以此为准。ABBA 已并入报告，数据齐备确认，NPU 任务可以独占设备。
### 任务
1. 导出一个 **stateful + 带 `beam_idx`** 的 `inputs_embeds` 解码器（KV 用 ReadValue/Assign 或 optimum 的 stateful 变换均可，目标是让 NPUW 的 `StatefulToStateless` 能识别）。参考：`MAX_PROMPT_LEN=512`（实测 prompt 最长 339，可取 384 或 512）、`MIN_RESPONSE_LEN` ≥ 单次最大输出 token（实测均值 7.6、最大约 9，留余量到 32）、权重先用 FP16，能跑通再试 INT8_SYM / INT4_SYM 按通道。
2. 用 `NPU_USE_NPUW=YES`、`NPUW_LLM=YES`、`NPUW_LLM_MAX_PROMPT_LEN`、`NPUW_LLM_MIN_RESPONSE_LEN` 编译，**必须实跑**（编译成功不作判据）。验收：与 GPU stateful 的 logits 余弦、同一批 prompt 的逐 token 输出一致率；单 token 延迟（≥20 次中位数）对比 GPU stateful 的 28.8 ms。
3. 注意：本流式方案每个 chunk 都重新 prefill 整条 prompt（均值 269 token，每段约 25 次），所以 **prefill 吞吐比单 token 延迟更关键**，请分别报 prefill（256/384/512）与 decode 单步。NPUW 的 prefill 是分块的，记录 `NPUW_LLM_PREFILL_CHUNK_SIZE` 的取值影响。
4. 若 3 小时内 prefill 或 decode 任一项比 GPU 慢 >30% 或无法实跑，停止，记录原因，不要继续硬耗；阶段 4 矩阵里对应格子写明原因。
### 铁律不变
与计时作业串行、开 GPU guard、不改驱动与系统策略、torch 只用于导出/验证脚本，计时子进程保持 `USE_TORCH=0`。

## C-071 [HIGH] 2026-10-16 21:35 — 撤回「NPUW 属性数 = 0 → 上限由 OpenVINO 版本决定」；按 C-070 继续
c069m/n 的实测画像很好（每段 24.88 次调用 = n_chunks、每次 7.6 token、方案 B GPU RTF 1.317），这部分结论接受，报告会引用。polyfit 两个坑记录得也对。
但「主线 2026.4.1 NPU 的 `SUPPORTED_PROPERTIES` 里 NPUW 属性数 = 0，所以上限由版本决定」**不成立**，与你自己的证据矛盾：
1. NPUW 是 NPU 插件内部的分区/LLM 层，它的 `NPUW_*` 选项**本来就不出现在 `SUPPORTED_PROPERTIES` 里**，但传给 `compile_model` 会被接受。列表里没有 ≠ 不支持。
2. 你在 18:55–19:15 已经用 `NPU_USE_NPUW` 编译成功过（「冻结成 [1,1] + NPUW → OK(20.5s)」）；方案 B 的 `NPUW_LLM=YES` 报的是 **`StatefulToStateless` 变换里的错误**——这个变换就是 NPUW LLM 流水线的一部分，说明 NPUW_LLM 在这一版**存在且被调用**了，失败原因是模型缺 `beam_idx`，不是版本。
3. 缺的只是 PR #4389 那个 Qwen3-ASR 专用属性 `NPUW_QWEN3_ASR_MAX_ENCODER_LEN`；而方案 B 用 `inputs_embeds` 把音频嵌入拼进提示，本来就不需要它。
### 请做
- 在 STATUS 里把这条改为「NPUW_* 不在 SUPPORTED_PROPERTIES 列表中，但可用（证据：NPU_USE_NPUW 编译成功、NPUW_LLM 进入 StatefulToStateless）」。
- **按 C-070 执行**：导出 stateful + `beam_idx` 的 `inputs_embeds` 解码器（KV 状态 + `beam_idx`，形如 optimum 的 stateful 导出），`NPUW_LLM=YES` 编译并**实跑**。
- 结合 c069m：每个 chunk 都 reset + 全量 prefill（均值 269 token），所以验收要分别报 **prefill（256/384/512）** 与 **decode 单步**，对照 GPU stateful 的 94 ms / 28.8 ms；用你的倍数法估端到端 RTF（prefill 25.2%、decode 57.7%、encoder 17.2%）。
- 3 小时止损条款不变。

## C-072 [HIGH] 2026-10-16 23:00 — c070o/p/q 审查：手写静态 KV 图不是 NPUW 能吃的形态；判据也比错了基线。请换导出路线再测一次
### 1. 先纠正 c070p 的判定口径
- 你把「手写图 @NPU」与「生产 stateful IR @GPU（94 / 28.8 ms）」比，得出 1.46× / 2.64× 慢。但**同一张手写图在 GPU 上是 167.3 / 93.1 ms**——手写图本身就比生产 IR 慢 1.8× / 3.2×（FP32 KV、每步都对整块 512 做注意力、常量写入位置）。
- 同图对比：prefill NPU 137.4 vs GPU 167.3 ms（**NPU 快 18%**）；decode NPU 76.0 vs GPU 93.1 ms（快 18%，但见第 2 条，数值不对，不能算）。
- 请两种比较都列：「同图 NPU/GPU」反映设备差异；「对生产 GPU」才是交付判据。**这一轮不触发止损**——NPUW 路线还没有一次真正跑起来。
### 2. decode0@plain_npu 数值错误，延迟作废
cos 0.782、argmax 11 vs CPU 不一致。prefill 正确（0.999998）而 decode 错，最可能是 NPU 上状态变量（ReadValue/Assign）的初值或读写不对（与 19:15 的 state descriptor 问题同源）。另外 c070q 的 decode 验证是 “torch-side manual cache math”，**没有验证 OV decode IR 本身**；请补一次 OV CPU 跑 decode IR 对源模型的对照。数值不对的配置不报延迟。
### 3. NPUW 失败的根因：图已经被你静态化了
NPUW_LLM 会**自己**把模型 reshape 成 prefill（MAX_PROMPT_LEN）和 generate（1 token）两个变体、KV 长度 = MAX_PROMPT_LEN + MIN_RESPONSE_LEN。它要求输入是**动态形状的标准 stateful LLM**（`inputs_embeds`/`input_ids [?,?]`、`attention_mask [?,?]`、`position_ids [?,?]`、`beam_idx [?]`，KV 作为状态且序列维动态）。你的图把 384 写进了 Reshape 常量、把 KV 固定成 512、Broadcast 目标是常量，NPUW reshape 后就出现 `[1,512,2048] → [1,384,16,128]` 与 `Expecting 1 or 8192, got 16` 两个错误。这与版本无关。
### 4. 建议路线（先做 a，a 不过就停）
**a. 速度可行性（不需要 inputs_embeds）**：reviewer 已核对源码，`get_rope_index` 对纯文本/音频把三路 position 设成同一值（modeling_qwen3_asr.py:442–444），interleaved MRoPE 就**等价于普通 1D RoPE**。所以文本主干可以映射成标准 `Qwen3ForCausalLM`（`thinker.model.*` → `model.*`、`thinker.lm_head` → `lm_head`，config 取 `text_config`，注意 q/k norm、rope_theta、tie_word_embeddings）。
  - 先在 torch 上验证：同一真实 prompt（用 `inputs_embeds` 喂两边）logits cos ≥ 0.9999；
  - `optimum-cli export openvino --task text-generation-with-past --weight-format fp16`（再做 INT8_SYM 与 INT4_SYM 按通道）；
  - 用 `NPU_USE_NPUW=YES, NPUW_LLM=YES, NPUW_LLM_MAX_PROMPT_LEN=512, NPUW_LLM_MIN_RESPONSE_LEN=64` 编译并**实跑**；测 prefill 256/384/512 与 decode 单步，同一 IR 也在 GPU 上测。prefill/decode 的算量与是否用 `inputs_embeds` 无关，这一步就能定 NPU 速度上限。
**b. 只有 a 的 prefill 与 decode 都不比生产 GPU 慢 >30% 时**：再把 IR 的 embedding Gather 换成 `inputs_embeds` 参数（或按 optimum VLM 的语言模型导出方式），接进 `seg_stream`，跑 12–27 分钟端到端 WER + 配对 CI 与 RTF。
### 5. 其他
- 当前 guard 设了 3600 s；作业已结束的话按实际时长重跑一个短 guard 或等它自然结束，别 kill（你记过：中途 kill 会丢 json）。
- 止损：a 做完仍无法实跑，或 prefill/decode 比生产 GPU 慢 >30%，就停，写阶段 4 矩阵。原 3 小时时限从本条起算。

## C-073 [NORMAL] 2026-10-16 23:25 — 对 22:50 那节日志的两点补充（C-072 优先执行，止损按 C-072 重新起算）
你 22:50 按 C-070#4 停下是对的；但该节写于 C-072 之前，**请按 C-072 继续**（标准 Qwen3ForCausalLM + optimum 导出 + NPUW_LLM）。另有两处表述要改：
1. 「方案 A 判死的真正原因是缺 `beam_idx`」**未证明**：补上 beam_idx 后 plain NPU 的 decode 仍然 cos 0.78 / argmax 不一致，状态读写在 NPU 上是否正确仍是开放问题。请写成「补 beam_idx 后 prefill 能正确实跑；带状态的 decode 在 plain NPU 上数值错误，原因未定」。
2. 「OV 没有 set_state，prefill 状态喂不进 decode 图」不对：`for s in req.query_state(): s.state = ov.Tensor(arr)`（C++ 是 `VariableState::set_state`）可以写入状态。需要验证 decode 图数值时可以这样把 prefill 的 KV 灌进去；不过走 C-072 的 NPUW 路线后，prefill/generate 由 NPUW 内部衔接，不需要你手动串图。
3. c070r 的「1.243 → decode 是唯一决定性环节」基于作废的 decode 延迟，请标注为不可用。

## C-074 [HIGH] 2026-10-17 10:20 — c072a/b/c 审查：NPUW 已真正跑通、数值正确，这是第一个有效的 NPU 解码数据。止损先别判，FP16 不是 NPU 的目标精度
做得好：文本主干等价（311 个权重、cos≈1.0、argmax 全一致）、optimum 导出、NPUW_LLM 编译**并实跑**、NPU 对 CPU 数值通过（len12/256/1 全部 argmax 一致）。这证明了 C-072 的路线可行。
### 1. 「STOP_LOSS_TRIGGERED」暂不成立
- 测的是 **FP16** 权重（≈3.4 GB）。decode 单步受内存带宽限制：3.4 GB / 104 ms ≈ 33 GB/s；生产 GPU 是 INT8（≈1.7 GB）/ 28.8 ms。NPUW 的 decode 路径就是为**压缩权重**设计的，官方 NPU 推荐格式是 **INT4_SYM 按通道**（`--sym --ratio 1.0 --group-size -1`）。C-072 本来就要求测 FP16 / INT8_SYM / INT4_SYM 三种，**止损按最好的那个精度判**，不按 FP16 判。
- 请接着导出并实跑：INT4_SYM 按通道（首选）、INT8_SYM 按通道；数值对 CPU FP16 仍按 cos/argmax 门控。
### 2. prefill 与长度无关（~221 ms），说明没分块
256/384/512 三个长度都是 ~221 ms，即每次都按 512 的静态形状整块算。生产流式 prompt 均值 269、最长 339。请测 `NPUW_LLM_PREFILL_CHUNK_SIZE` = 128 / 256（若该版本不认，记下报错），并按真实 prompt 长度分布（c069m）报加权平均 prefill。
### 3. 「vs_custom_gpu」用错了基线
167.3 / 93.1 ms 是**旧的手写图**在 GPU 上的数，不是这次的 IR。C-072 要求「**同一个 IR 也在 GPU 上测**」：请把 `qwen3-lm-*-ov`（FP16 与 INT4/INT8 各一）在 GPU 上测同样的 prefill/decode，作为“同图 NPU/GPU”列。
### 4. 计时要开 GPU guard
现在只有 `c072c_npuw_f16_probe.py` 一个进程，没看到 guard。NPU 计时同样会被 GPU/CPU 上的其他负载干扰，请按惯例用 `c058l_gpu_guard.py` 包住计时脚本（别中途 kill）。
### 止损
三种精度都测完后：最好的那个若 prefill（按真实长度加权）或 decode 比生产 GPU（94 / 28.8 ms）慢 >30%，就停并写阶段 4 矩阵；否则进入 C-072 b。

## C-075 [HIGH] 2026-10-17 11:05 — c072c–f 审查：INT8_SYM 的 NPU decode 已接近生产 GPU；判据改为端到端，进入 C-072b
### 1. 关键数据（c072f 多步实跑，比 c072c 单步更可信）
| IR | 设备 | decode 中位 | prefill（单次，512 静态） |
|---|---|--:|--:|
| FP16 | NPU | 57.4 ms | 369 ms |
| FP16 | GPU | 62.8 ms | 299 ms |
| **INT8_SYM** | **NPU** | **34.1 ms** | 242 ms |
| INT8_SYM | GPU | 32.8 ms | 313 ms |
| 生产 INT8 | GPU | 28.8 ms | 94 ms |
- c072c 里 FP16 NPU decode 104 ms 与 c072f 的 57 ms 差近一倍，c072c 的单步计时口径（每次是否带了 reset / 首步开销）请说明，**以多步中位为准**。
- **INT8_SYM NPU decode = 生产 GPU 的 1.18×**，在 30% 之内。
### 2. 同一 IR 在 GPU 上 prefill 比生产慢 2–4×：原因多半是 lm_head 对全序列算 logits
optimum 默认导出对 T 个位置都算 `[1,T,151936]` logits（256 token 时约 80 GFLOP + 大块输出），生产 IR 只取最后一位。prefill 随长度线性涨（194→282→403 ms）也符合这个解释。请对 GPU 对照组做「只取最后位置 logits」（openvino.genai 的 slice-before-matmul 变换，或手动在 lm_head 前插 Slice/Gather 取 `[:, -1:, :]`），再测一次同图 GPU；NPUW 内部本来就只算最后一位。
### 3. 数值门控：这组“短 prompt + 贪心 12 步”不够格
FP16 三设备完全一致，很好；但 INT8 的 CPU/GPU/NPU 在第 4–6 步分叉，而这个 prompt 第 0 步就出了 EOS（151645），后面都是 EOS 之后的无意义续写，分叉多半是近似平票，**不能据此判 INT8 或 INT4 的精度**。INT4 的 len1 argmax 不一致同理。真正的精度判据只能是**真实音频 prompt 上的端到端 WER + 配对 CI**。
### 4. 判据调整（取代 C-074 的逐环节止损）
NPU 的价值是把解码器（≈83% 的耗时）从 GPU 移走，所以按**端到端**判，不按单环节：
- 倍数法估算（份额 encoder 17.2% / prefill 25.2% / decode 57.7%，基线 RTF 0.578）：INT8_SYM NPU，prefill 242 ms 时 RTF ≈ 0.578×(0.172 + 0.252×242/94 + 0.577×34.1/28.8) ≈ **0.87**；若分块把 prefill 降到 ~160 ms 则 ≈ **0.75**。都 <1。
- 新止损：**估算 RTF > 0.9，或 WER 相对 GPU 基线配对 CI 显著变差（下界 > 0）**，停。
### 5. 下一步（C-072b，INT8_SYM 为主，INT4_SYM 作对照）
1. 把 INT8_SYM IR 的 embedding Gather 换成 `inputs_embeds` 参数（或按 optimum VLM 语言模型的方式导出），与 `seg_stream` 的 prompt 拼接对接；先在 CPU 上对源模型做真实音频 prompt 的逐 token 对拍。
2. 测 `NPUW_LLM_PREFILL_CHUNK_SIZE` 128/256（不认就记下），按真实长度加权报 prefill。
3. 12–27 分钟端到端：GPU 编码器 + NPU 解码器（INT8_SYM），全新进程、GPU guard；报 WER 与配对 CI（对 ABBA 配置 A 的转写）、P50/整体 RTF、**GPU compute 占用对比配置 A 降了多少**、NPU 占用。
4. c072d/e 是旧手写图，归档即可，不要再花时间。

## C-076 [HIGH] 2026-10-17 11:55 — 你 11:32 的「INT8/INT4 不合格」判早了；请先读 C-075，两种精度都进端到端 WER
1. 口径修正（c072c 每次新建 InferRequest + reset → 104 ms；会话内多步 57.4 ms）做得好，接受。手写图作废，同意。
2. **新的矩阵数据其实很有利**：INT4_SYM NPU decode **22.7 ms**（生产 GPU 28.8，**更快**），INT8_SYM NPU 33.6 ms。
3. 「不合格」的依据不成立：这组 prompt 第 0 步就出 EOS / 数字串，后面是无意义续写；INT4 NPU 输出 `[13, 220,17,15,15,15,82, …]` 与 CPU `[220,17,15,15,15,82, …]` 是**同一序列错开一位**（第 0 步近似平票多出一个 token），不是模型坏了。len1 单 token prompt 的 cos 也不代表 ASR 场景。**按 C-075#3，精度只用真实音频 prompt 的端到端 WER + 配对 CI 判。**
4. 因此请按 C-075#5 执行，**INT8_SYM 与 INT4_SYM 都做**：inputs_embeds 接入 → CPU 上真实音频 prompt 对拍（报逐 token 一致率，作为参考，不作门控）→ 12–27 分钟 GPU 编码器 + NPU 解码器端到端（WER+配对 CI、P50/整体 RTF、GPU compute 占用降幅、NPU 占用）。止损仍是 C-075#4：估算 RTF>0.9 或 WER 配对 CI 下界>0。

## C-077 [NORMAL] 2026-10-17 12:25 — c072c chunk128/256 与 c075b 的两处问题
1. **c075b 的 `int4sym-lastlogit` 体积 1643.3 MiB，与 INT8 版一模一样**——INT4 按通道版应约 996 MiB（你 c072 的 `qwen3-lm-int4sym-ov`）。多半是导出参数没生效或目录/IR 复制错了。请核对该 IR 里 u4/i4 常量个数，修正后再用；**在核对前，任何标成 int4sym-lastlogit 的数据都作废**。
2. **chunk128/256 两份 latency 为空**：被 dummy prompt 的数值门控挡掉了。按 C-075#3/C-076，这个门控不适用于短 dummy prompt；请照常报 prefill（256/384/512 + 按真实长度 269/339 加权）与 decode，数值门控等真实音频 prompt 时再做。
3. c075a 的 `OVTypeError dtype('O')` 是喂了 object 数组（多半是 list 或不齐的嵌套 list 转 numpy），把输入显式 `np.asarray(x, dtype=np.int64)` 即可。

## C-078 [NORMAL] 2026-10-17 12:55 — 矩阵与 last-logits 修复接受；两处小修正，然后进端到端
做得好：发现 `main_export()` 静默忽略 weight_format 并用 i4 常量计数核实（196 个 i4、970.8 MiB）；INT4_SYM @NPU decode 23.0 ms（生产 0.80×）；C-077#3 的 np.asarray 建议确实不适用，以你的 DescriptorTensor 结论为准。
1. **「分块无效果」不准确**：`c072c_npu_npuw_512_chunk256.json`（int4 lastlogit）里 prefill 是 256→237.9 / 384→326.3 / 512→326.8 ms，**随长度分档变化**，说明分块生效了——只是 384/512 要算两块，反而比默认（1024 块、单次 ~220 ms）更慢。结论应写成「分块生效，但 256 块对 269–339 token 的 prompt 需两块，更慢；保持默认」。该文件里 decode 153.9 ms 是单步新建 InferRequest 的旧口径，不要引用。
2. **「INT8 prefill 按真实 269 则 RTF 0.717」请删除**：NPUW 默认 prefill 是静态整块，与真实长度无关（你自己测到 ~220–242 ms 恒定），不能按 269/512 缩放。INT8 @NPU 取 0.862，INT4 @NPU 取 0.707。
3. 下一步按 C-075#5 / C-076：INT8_SYM 与 INT4_SYM（lastlogit 版）换 inputs_embeds → CPU 真实音频 prompt 对拍 → 12–27 分钟 GPU 编码器 + NPU 解码器端到端（WER+配对 CI、P50/整体 RTF、GPU compute 占用降幅、NPU 占用）。

## C-079 [HIGH] 2026-10-17 15:40 — inputs_embeds 全 0：先别关路线，再试两个更可能的原因（各 ≤45 分钟）
你的隔离实验很漂亮（`gather + (p − p)` 正常、真正覆盖就全 0），结论「NPUW 依赖 embed Gather 的路径」可信。但「NPUW_LLM 强制按 input_ids 查表」只是一种解释，还有两种更具体、可验证的原因：
### 1. NPUW 的 host gather 优化
NPUW 默认会把词表 embedding 的 Gather **挪到主机侧执行**（`NPUW_HOST_GATHER`，默认开），把结果直接喂给 NPU 子图的入口。图里的 Gather 被你断开/置零后，这个优化仍可能按 `input_ids` 在主机算 embedding 并写到那个入口，或者写到已断开的位置，于是 NPU 收到的不是你的 `inputs_embeds`。
- 在方案 A（切断 Gather）和方案 B（Select）上加 `NPUW_HOST_GATHER=NO` 再跑；如果这个版本不认这个键，就记下报错。
- 另外用 `get_property('NPU', ...)` 读出所有 `NPUW_*` 的默认值并贴出来，你之前已经能读到 `NPUW_LLM_*` 系列。
### 2. 端口布局不像 VLM 语言模型
openvino.genai 的 VLMPipeline 能在 NPU 上跑，它的语言模型 IR **没有 `input_ids` 端口**，只有 `inputs_embeds [?,?,H]`、`attention_mask`、`position_ids`、`beam_idx`。NPUW_LLM 很可能按「有没有 `inputs_embeds` 端口、有没有 `input_ids`」来选走哪条路径。你的几个变体都还保留了 `input_ids`（「4 端口 + ie」），这会让它走 token 路径。
- 做一个**干净的 4 端口 IR**：切断 Gather 后**删除 `input_ids` Parameter**（`model.remove_parameter`），端口名用 `inputs_embeds`，形状设成 `[1, 1..512, 2048]`（你已经验证过 512 这个上界在 CPU 和 NPU 两边都能用），再用 NPUW_LLM 实跑。
- 也可以照 optimum 导出 VLM 时语言模型那一半的做法去导出。
- 顺带核实：在已装的 `openvino_genai` 包里查 `VLMPipeline` 文档或源码里的 NPU 支持说明，以及 `inputs_embeds` 这个端口名的用法，注意 pyd/dll 字符串可能是 UTF-16。
### 3. 若 1、2 都失败
就把「NPUW_LLM 在 2026.4.1 下不接受外部 embedding」作为结论写进阶段 4 矩阵：
- **NPU 解码器：** 技术上可用，但必须走 token 路径，所以不适用于 ASR。
- **方案 A「编码器融入同一 NPUW 图」：** 不做，工作量和风险都超出评估范围。
- **方案 B「扩 embedding 表」：** 不可行，因为 embedding 表是常量，没法每次调用写入不同的音频嵌入。
### 4. 两处数据标注
- 「last-logits 修复从未生效」：c072c、c072f 里所有 **GPU 同图**的 prefill 都是在全序列 logits 下测的，请在 STATUS 和矩阵里标出来。NPU 的数字不受影响。
- `qwen3-lm-int4sym-ie-ov` 是整目录复制出来的，凡是用了它的结论都作废，请重导出后再测。

## C-080 [HIGH] 2026-10-17 18:35 — clean-ie 路线接受；立即开始端到端（不用再等确认）
c079c 接受：删掉 `input_ids` 后，ie 真正进入 NPU；prefill CPU/NPU cos 0.99991（INT8）/ 0.99973（INT4），首 token 一致。dummy prompt 后续分叉照旧不作判据。找 DLL 契约字符串这个方法很好。你建的每小时巡检也很好。
**现在按 C-075#5 执行端到端，INT4_SYM 先跑（估算 RTF 0.716），INT8_SYM 后跑：**
1. 把 `models/qwen3-lm-{int4sym,int8sym}-cleanie-ov` 接进 `seg_stream`。prompt 拼接（模板 token 的 embedding + 音频嵌入 + 前缀 token 的 embedding）在 Python 里完成，embedding 表从 HF 权重的 `embed_tokens` 取，f32。`position_ids` 按 0..T−1 给（MRoPE ≡ 1D，已验证）。
2. 每个 chunk 照生产逻辑 reset + 全量 prefill，用 `reset_state()`，不要每次新建 InferRequest。自适应 max_new_tokens 与 EOS 规则与生产完全一致。
3. 12–27 分钟切片，全新进程，GPU 编码器 + NPU 解码器，开 GPU guard，计时子进程 `USE_TORCH=0`。报告：
   - WER 与配对 CI：对 ABBA 配置 A 的同一切片转写，用 paired_bootstrap 5000 次。
   - P50 / 整体 RTF，每块耗时中的 prefill 与 decode 分项。
   - **GPU compute 占用对配置 A 的降幅**，以及 NPU 占用。
4. 止损不变：实测 RTF > 0.9，或 WER 配对 CI 下界 > 0，就停在该精度。
5. 转写文件放到 `reports/c080_e2e/`，命名为 `transcript_{int4,int8}_npu.txt`，reviewer 会独立复核。

## C-081 [HIGH] 2026-10-17 20:05 — c080i「GPU 占用反而升 15%」几乎可以肯定是计数口径错：NPU 也挂在 GPU Engine 计数器下
c080g/c080b 接受：INT8_SYM cleanie @NPU + GPU 编码器，12–27 分钟实测 RTF 0.853，WER Δ +0.72 pp CI[−0.38, +1.91] 不显著（reviewer 独立复核 +0.54 pp [−0.62, +1.74]，同结论）。INT4 × NPUW 真实音频乱码、按止损不跑，同意。
### 问题
c080i 显示 NPU 方案 GPU compute 均值 73.7%，高于全 GPU 的 63.9%。这与你自己的分项矛盾：NPU 方案里 GPU 只跑编码器，1491 次 × ~75 ms ≈ 112 s / 767 s wall ≈ **15%**，不可能 74%。
最可能的原因：**Windows 的 `\GPU Engine(...engtype_Compute)` 计数器也包含 NPU**（NPU 在 WDDM 里注册成一个计算适配器，有自己的 LUID）。只按 PID 过滤、不按 LUID 过滤，就把 NPU 的占用算成了“GPU”。目标机上现在能看到两个带 Compute 引擎的 LUID：`0x00012E84` 和 `0x000144F0`。
### 请做
1. 用 `core.get_property("GPU.0","DEVICE_LUID")` 和 `core.get_property("NPU","DEVICE_LUID")` 拿到两者的 LUID（或用 `Get-CimInstance Win32_VideoController` / 适配器名对照），确认哪个 LUID 是 iGPU、哪个是 NPU。
2. c080i 重算：**只统计 iGPU LUID** 的 Compute（以及 Copy）引擎，NPU LUID 单独列为“NPU 占用”。A 与 cleanie 各跑一次，同一 3 分钟切片、全新进程。
3. 同时检查 `c058l_gpu_guard.py` 是否也有同样问题（它过滤的是“其它进程”，NPU 上的其它进程占用也会被算成 GPU 冲突；目前影响不大，但请注明）。
4. 日志里「NPU 方案降载在当前瓶颈结构下不成立」先撤回，等第 2 步数据。

## C-082 [NORMAL] 2026-10-17 21:10 — C-081 接受；NPU 评估收尾
c081a/b 接受：iGPU LUID 0x12E84、NPU LUID 0x144F0；按 LUID 拆分后集显 compute 均值 67.7% → 7.4%（−89%），NPU 67.7%。c080i 的“GPU 占用反而升高”撤回。c081t 的切片口径说明也接受，引用 WER 时一律带上切片范围。
reviewer 已经把 NPU 章节写进最终报告（§7）。
### 收尾
1. 在 STATUS 写阶段 4 矩阵（{GPU 现状, NPU enc + GPU dec, GPU enc + NPU dec INT8, GPU enc + NPU dec INT4, NPU enc + NPU dec}）。每格写 RTF / WER CI / 集显占用，做不到的格子写原因：
   - NPU 编码器：慢 1.5 倍，没有收益；
   - INT4 @NPU：真实音频输出乱码；
   - 全 NPU：没跑，因为编码器在 NPU 上更慢，没有理由跑。
2. 写一行「NPU 数据齐备」和文件清单。
3. **不要继续追 INT4 × NPUW 的根因**，除非用户另行要求。
4. 收尾后检查一遍：`models/` 下中间产物（手写图、ie 复制目录等）占了多少空间，列出可删清单写进 STATUS，**不要自己删**。

## C-083 [NORMAL] 2026-10-17 22:25 — 阶段 4 矩阵与最终报告 §7 对齐：三处修正（只改 STATUS 文字，不用重测）
「NPU 数据齐备」与可删清单接受，清单写得很清楚，删不删由用户决定。
1. **RTF 混用了两个切片**：矩阵里 WER 是 12–27 分钟切片，RTF 却用了 c081b 的 3 分钟切片（0.6246 / 0.8651，×1.385）。主数据请统一为 **12–27 分钟**：A 取 ABBA 配置 A 的 **0.578**，cleanie 取 c080b 的 **0.853**（×1.475）。3 分钟切片的 RTF 只作为“集显占用测量时的伴随值”另列。报告 §7 用的就是 0.853 对 0.578。
2. **「编码器只占 RTF 0.33%」已经过时**，而且和你自己的 c069m（17.2%）、c080h（15.2%）矛盾，请删掉。NPU 编码器那一格的理由改为：编码器约占流式耗时的 15–17%，在 NPU 上慢 1.5 倍，RTF 约再增加 0.05 个点；集显上能省的也只有剩下这约 7% 的占用，所以没有收益。
3. **INT4 那一格的归因**：同一个 INT4 cleanie IR 在 CPU 上转写正确（c080e/c080f），所以问题在「INT4 权重 × NPU 执行」这个组合，不在 INT4 权重本身，请改成这个表述。

## C-088 [HIGH] 2026-10-18 14:50 — 审查 C-084～C-087（全 NPU、无 GPU 部署、INT4@NPU）：结果接受，三处结论要改，交付前补三件事
说明：你在 STATUS 里把自己的章节也编成了 C-084～C-087，和 CORRECTIONS 的编号撞了。reviewer 的纠偏从本条起用 **C-088**；以后你自己的章节请换个前缀（如 R-088），不要再用 C-。

### 一、接受
- **全 NPU 全长 61 分钟**：RTF 0.7722（P95 0.794，最大 0.815），WER 7.952%，对配置 A 的差值 +0.154 pp，95% CI [−0.288, +0.584]。reviewer 用自己的 MiniMax 参考和配对 bootstrap 独立复核：**+0.10 pp，95% CI [−0.41, +0.56]，不显著**，结论一致。
- 12–27 分钟切片：reviewer 复核 +0.51 pp，95% CI [−0.63, +1.70]，与你的 +0.68 同结论。
- c087 里重跑的 int8_npu 转写与 c085 **md5 完全相同**，说明全 NPU 流水线是确定性的，这是好证据。
- 先跑 2 分钟先导、每 150 s 把 probe 落盘、全长参照先复现 7.798% 再比，这些流程改进都对。

### 二、要改的结论
1. **「全 NPU 比 cleanie 快，是因为省了跨设备传输」的解释不成立。** 真正原因是编码器 IR 搞混了：
   - 流式实际用的是双输入的 `ov-encoder-segment-reviewer`。你自己的 c069d（ABBA 3 轮）显示它在 **NPU 上反而更快**：34.8 ms，集显 45.3 ms，NPU/GPU = 0.769。
   - 「NPU 编码器慢 1.5 倍」测的是单输入的 prod IR（ov-fp16-past / ov-int8-past），流式根本不用它。
   - c083c 虽然标注 `encoder_ir: ov-encoder-segment-reviewer`，实际是 `OVBackend(model_dir='models/ov-int8-past')`，测的也是单输入 IR，**标注错了**。38.8 ms 对 78 ms「数据打架」的主要原因也在这里。
   - 定量核对：(0.8525 − 0.7782) × 900 s ÷ 1491 次 ≈ 45 ms/次，与「cleanie 里集显编码器 78 ms（c080h）− NPU 编码器约 35 ms」吻合，不需要「跨设备开销」这个假设。
   - 请撤回这条「教训」，并把 c083c 的标注改正。reviewer 在 C-082/C-083 里也接受过「NPU 编码器慢 1.5 倍，全 NPU 不必跑」，这是 reviewer 的错，一并撤回。
2. **「本机 NPU 与台式机同为 NPU 3 代，可直接外推」不对。**
   - 本机 Core Ultra 7 356H（Panther Lake）的 NPU 是第 5 代（`DEVICE_ARCHITECTURE=5010`），约 50 TOPS。
   - Arrow Lake-S 台式机（Core Ultra 200S）是 NPU 3，约 13 TOPS。
   - prefill 是算力瓶颈（本机 ≈ 170 ms/次，每 640 ms 一次），在 NPU 3 上很可能慢好几倍，RTF 可能超过 1。
   - 所以结论只能写成「**本机 NPU 5 实测**可实时」；台式机能不能用，必须在目标台式机上实测，不能外推。c083d 里 `why_this_host_is_representative` 一段请改。
3. **「NPU 不能跑 INT4」说得太满。**
   - cleanie INT4 是 **INT4_SYM 按通道 + 18% INT8 回退**，比 GPU 上验证过的 g128 配方粗糙得多。同一个 IR 在 **CPU 上 WER 也有 40%**（reviewer 复核：对 int8_npu +32.1 pp，95% CI [+21.1, +44.4]），而且出现 `Twenty-eight. A. C.` 这类循环。这说明**配方本身就已经坏了**，不是「CPU 慢路径生成更长」：生成预算是自适应的，与设备快慢无关。
   - `OPTIMIZATION_CAPABILITIES` 列的是计算精度，不是权重压缩格式。NPU 跑 INT4 权重的 LLM 恰恰是官方推荐路径，不能拿它当「NPU 不支持 INT4」的证据。
   - 请改写为：「这版按通道 INT4 IR 不可用：CPU 上 WER 40%、NPU 上 110%，NPU 上更差。换更好的 INT4 配方（如 g128，或 AWQ + scale estimation，校准只用 0–12 分钟）在 NPU 上的表现**未测**。」
   - 是否再试由用户决定，**不要自己开跑**。

### 三、交付前补三件事
1. **删清单有误，会弄坏 NPU 路径。** `npu_embeds_backend._load_embed_table()` 读的是 `models/hf-qwen3-lm-lastlogit`，而 C-083 的 tier4 把它列为「0 脚本引用、可删」。
   - 请把 embed_tokens 导出成一个独立的 `.npy`，用 f16，约 0.6 GB，放在 `qwen3-lm-int8sym-cleanie-ov/` 旁边，改为从那里读。
   - 然后更正可删清单。修好之前 tier4 不能删。
2. **全 NPU 后端多加载了一个用不到的解码器。** `make_all_npu_backend()` 先用父类在 CPU 上编译了 `ov-int8-past` 的 cross-attention 解码器；后面替换了 `be.dec`，但 `be.dec_infer` 还引用着它，所以约 1.7 GB 权重一直占着内存。cleanie 路径里它则被编译到 GPU.0，占集显内存。
   - 请做一个交付用的后端：只加载 tokenizer、特征提取器和模板，不编译 aux 解码器，并且两个 compile 都只做一次。
3. **补测资源占用。** 用 3 分钟切片，全新进程，测全 NPU 的：
   - 峰值内存（Private Bytes / Working Set）；
   - CPU 平均占用；
   - 按 LUID 拆分的集显和 NPU 占用：用实测代替「GPU 占用 0」这个推断。
   修好 1、2 之后再测，这样数字代表交付形态。

做完后在 STATUS 写「全 NPU 交付形态齐备」，附上文件清单。

## C-089 [HIGH] 2026-10-18 15:10 — 用户要求：试更好的 INT4 配方让解码器在 NPU 上可用（优先于 C-088 第三部分；C-088 第二部分的文字修正顺手先做）
背景：现有 `qwen3-lm-int4sym-cleanie-ov` 是 INT4_SYM 按通道、无校准，另有约 18% 的层回退成 **INT8_ASYM**。它在 CPU 上 WER 也有约 40%，所以先要把配方修好，再看 NPU。
目标：找一个 INT4 配方，**全 NPU 端到端 WER 与 INT8 全 NPU 没有显著差异**，同时比 INT8 快。

### 做法
- **起点**：统一从已有的 `models/qwen3-lm-fp16-cleanie-ov`（已删 `input_ids`，只留 `inputs_embeds`）出发，用 NNCF 的 `nncf.compress_weights` 直接压缩。这样不用重新导出，也不用再做一遍端口手术。用 `ov.save_model` 保存，**保存后先数一遍 i4 / i8 常量个数，确认真的压成了 INT4**（之前 optimum API 静默变成 INT8 的坑别再踩）。
- **回退精度一律用 `backup_mode=INT8_SYM`**：现有 IR 用的是 INT8_ASYM，这本身可能就是 NPU 上出错的原因之一。
- **校准数据只用 0–12 分钟**：在全 NPU（或集显）流水线里跑 0–12 分钟，把每次调用的真实 prefill 输入（`inputs_embeds`、`attention_mask`、`position_ids`、`beam_idx`）录下来，按 prompt 长度分层抽约 128 条，存成 `reports/c089_int4/calib_0_12min.npz`。**评测只用 12–27 分钟和全长。**

### 配方（按顺序做，前两个不需要校准，很快）
| 编号 | 配方 | 目的 |
|---|---|---|
| R0 | INT4_SYM 按通道（`group_size=-1`），`ratio=1.0`，无校准 | 只把回退从 INT8_ASYM 换成 INT8_SYM，判断回退精度是不是问题 |
| R1 | INT4_SYM `group_size=128`，`ratio=1.0`，无校准 | 分组量化；先确认第 5 代 NPU 能否编译并正确运行分组 INT4 |
| R2 | INT4_SYM 按通道 + `awq=True` + `scale_estimation=True`，用校准数据（`subset_size=128`） | NPU 官方推荐的按通道格式，加上数据驱动校准 |
| R3 | INT4_SYM g128 + AWQ + scale_estimation，用校准数据 | 精度最好的候选（前提是 R1 能在 NPU 上跑） |
| R4（可选） | 在 R2 或 R3 里较好的那个基础上，`ratio=0.8`，`sensitivity_metric=HESSIAN_INPUT_ACTIVATION`（约 20% 敏感层保留 INT8_SYM） | 只在 R2/R3 接近但仍显著变差时才做 |

### 每个配方的评测（都用全 NPU：编码器 + 解码器都在 NPU）
1. **编译并在 1 段真实音频上实跑**，看输出是否像人话。这一步只排除明显的乱码（像 `yay` 那种），**不作精度判据**。
2. **12–27 分钟端到端**，全新进程，`CACHE_DIR` 照旧。报告：
   - WER，以及对 **INT8 全 NPU（c085 转写，md5 `8682554d…`）** 的配对 bootstrap 5000 次 CI；参照先复现 6.643%。
   - 整体 RTF / P50 / P95，prefill 与 decode 的中位耗时。
   - IR 体积，以及 i4 / i8 常量个数。
3. 转写放到 `reports/c089_int4/transcript_R{n}_npu_1227.txt`，reviewer 会独立复核。
4. **第一个通过的配方**（WER 配对 CI 包含 0，且 RTF 低于 INT8 的 0.778）**再跑一次 61 分钟全长**：对 c048 参照算 WER 和 CI，并报 RTF。
5. 如果某个配方在 NPU 上不对、在 CPU 上又看似正常，**只对这一个**在 CPU 上跑 12–27 分钟（约 27 分钟），用来区分是配方问题还是 NPU 问题。其他配方不跑 CPU。

### 止损
- 总时长 **4 小时**。
- R0–R3 都显著变差（CI 下界 > 0）：做 R4。R4 也不行就停，写结论：「在 OpenVINO 2026.4.1 + 本机 NPU 5 上，试过的 INT4 配方都不能达到 INT8 精度」，附各配方的 WER / CI / RTF 表。
- 编译失败、跑出乱码，都按原样记录报错，不要绕过。

### 铁律不变
不改驱动、不改系统设置，计时作业串行，不删任何文件。

## C-090 [NORMAL] 2026-10-18 15:20 — C-089 进展审查：R0/R1 构建通过；R2/R3 失败是校准数据形状问题，修好重跑
接受：
- 校准集只用 0–12 分钟：1147 次调用，按长度分 8 层抽了 128 条。
- R0/R1 确认是真 INT4：196 个 i4 常量，回退为 INT8_SYM，没有 FP16 残留，体积约 973 / 993 MiB。
- C-088#3：
  - embed 表已导出为 f16 `.npy`；
  - 交付后端不再加载 aux 解码器；
  - 资源实测：峰值工作集 4.6 GB、Private 3.4 GB，按 LUID 集显占用 0%。
### 1. R2/R3 报错的原因
`Can't set the input tensor ... model input [1,1..512,2048] vs tensor (1,1,21,2048)` / `(5,1,21,2048)`：npz 里按长度存成了 `[n, 1, T, 2048]`，喂进 `nncf.Dataset` 的每一条**多了一维**（或者整批 5 条被当成一条送进去）。
- 每条样本必须是一个 dict：`inputs_embeds` `[1,T,2048]` f32、`attention_mask` `[1,T]` i64、`position_ids` `[1,T]` i64、`beam_idx` `[1]` i32。
- 按 `emb_T{T}[i]` 逐条拆开，128 条就是 128 个 dict。
- NNCF 的 OV engine 对 stateful 模型会在每条样本前调用 `reset_state()`（`nncf/openvino/engine.py:50–56`），KV 不会跨样本累积，不需要你另外处理。如果在 CPU 上连续 `reset_state()` 报 `sub-views are not implemented`，记下报错再告诉我。
### 2. 大文件放错了目录
R0/R1 的 IR（各约 1 GB 的 `.bin`）放在 `reports/c089_int4/` 下，而 `reports/` 不在 `.gitignore` 里（只忽略了 `npu_cache`）。下次 `git add -A` 会把几个 GB 的权重提交进仓库。
- 请把 R0–R4 的 IR 移到 `models/c089_int4/`，`models/` 已被忽略；
- 或者在 `.gitignore` 加上 `reports/**/*.bin`。
- 校准 npz（108 MiB）也一样处理。
### 3. 记一笔，放到 C-089 之后再查：全 NPU 平均要占 6.1 个 CPU 核
对一台只有 CPU + NPU 的台式机来说，这个开销不小。C-089 做完后用 3 分钟切片定位一下 CPU 花在哪里，比如 mel 特征和 VAD、拼 `inputs_embeds` 的 numpy 拷贝、NPU 插件的主机侧线程。只做测量，不用优化。
### 4. 继续 C-089
修好校准后，按 R0 → R1 → R2 → R3 的顺序跑 12–27 分钟全 NPU 端到端，判据和止损不变。

## C-091 [NORMAL] 2026-10-18 15:25 — 评测和构建在并行跑，RTF 会被污染
现在 `c089c_eval_recipe.py --selfcheck`（全 NPU 实跑）和 `c089b_build_recipe.py R2`（AWQ 校准，CPU 很重）同时在运行。全 NPU 流水线本身就平均占 6.1 个 CPU 核，两者抢 CPU，**这期间测到的 RTF、prefill 和 decode 耗时都无效**。WER 不受影响，因为流水线是确定性的。
- 本轮 selfcheck 只采信 WER 复现，RTF 不要引用。
- 以后先把 R2/R3（以及可能的 R4）全部构建完，再串行跑评测。或者评测期间不跑任何构建。
- 每个评测的 summary 里记一下同时段是否有其他重负载进程（可以复用 guard 的进程扫描）。

## C-092 [HIGH] 2026-10-18 15:40 — c089d 评分脚本有错，会把乱码判成“通过”；修好之前不要按它下结论
### 现象
- `R0_npu_wer.json`：WER 110.99%，Δ +104.3 pp，但 `ci95: [0.0, 0.0]`、`ci_contains_zero: true`。按 C-089 的通过规则，R0 会被判成“通过”。`n_cand_segs: 203`，而转写只有 54/55 段。
- `INT8_f16embed_npu_wer.json`：`n_cand_segs: 1`、`ci95: [0,0]`，WER 7.074%（参照 6.643%）。
### 原因（reviewer 已核对）
1. `transcript_int8_selfcheck.txt` **没有 `[t0-t1]` 时间戳行**，55 段文字被直接拼成一行，段与段之间连空格都没有（如 `QS.So`、`well.And`）。按时间戳拆开、再用空格拼接后，它与 c085 的转写**逐字符完全相同**（14895 字符）。所以 **f16 embed 表无损，INT8 交付后端与 c085 等价**；7.074% 只是边界粘词造成的假差异。
2. 只剩 1 段（或段数与参照对不上）时，bootstrap 退化，CI 就成了 [0,0]。脚本没有检查这一点，还把 [0,0] 当成“包含 0”。
### 要求
1. `c089c` 一律按 `[t0-t1] text` 逐段写转写，与 c085 的格式相同。selfcheck 重写一次，不用重跑：重新生成文件即可。
2. `c089d` 加三道断言，任一不满足就报错退出，不出结论：
   - 候选段数 == 参照段数（55），并且逐段时间戳一致；
   - bootstrap 的 CI 宽度 > 0；
   - 参照自身 WER 复现 6.643%。
3. R0 按修好的脚本重算。从转写看，R0 在 NPU 上仍是 `yay`、土耳其语重复，**结论是失败**。这说明回退精度 INT8_ASYM → INT8_SYM 不是原因。
4. 以后 selfcheck 必须**比转写 md5**。INT8 交付后端应与 c085 的 md5 `8682554d…` 一致；如果不一致，先查格式。
5. R1/R2/R3 照常继续。R2/R3 构建成功（196 个 i4，校准只用 0–12 分钟），这点接受。

## C-093 [NORMAL] 2026-10-18 16:05 — R1 已跑 45 分钟还没结束：加超时和逐段日志
`c089c_eval_recipe.py R1` 从 15:16 开始，到 16:00 仍未结束。12–27 分钟只有 15 分钟音频，跑 45 分钟意味着 RTF 已经超过 3。而且没有 `c089c_R1.log`，看不到进度。
- 先确认 R1 是在推进，还是卡住了。可以看进程的 CPU 时间是否还在增长，或者用 NPU 计数器查占用。
- **可行性上限**：12–27 分钟这一段，墙钟时间超过 **20 分钟**（RTF > 1.33），无论 WER 如何都不可交付。到这个时间就停掉，把已完成的段数、平均每段耗时和最后几段的输出写下来，记为「R1：NPU 上 g128 过慢 / 卡住」。
- R2/R3 的评测脚本也要**每段落盘一次**（时间戳、段号、耗时、文字），用 `python -u` 并重定向到 `reports/c089_int4/R{n}_npu.log`，同时加上同样的 20 分钟上限。
- g128 很可能在 NPU 上走了慢路径（分组反量化），所以 **R3（g128 + AWQ）大概率也慢**。请**先跑 R2（按通道 + AWQ）**，再跑 R3。

## C-094 [HIGH] 2026-10-18 16:40 — R1/R2 审查：AWQ 校准让 INT4 在 NPU 上恢复正常，但精度仍显著变差；停 R3，做 R4
### 结果（reviewer 用 MiniMax 参考独立复核，12–27 分钟，对 INT8 全 NPU）
| 配方 | RTF | prefill / decode 中位 | WER 差值，95% CI（reviewer） | 你的结果 | 判定 |
|---|---|---|---|---|---|
| R0 按通道、无校准 | 0.610 | 159 / 66 ms | 乱码（`yay`、土耳其语） | +104 pp | 失败 |
| R1 g128、无校准 | **2.953** | **1596** / 181 ms | +3.88 pp [+0.42, +8.25] | +4.45 [−0.24, +11.3] | 太慢，且出现语言漂移（第 2 段变成葡萄牙语） |
| **R2 按通道 + AWQ + SE** | **0.621** | 146 / 166 ms | **+3.88 pp [+1.81, +6.28]** | +4.20 [+2.14, +6.39] | 能用但显著变差 |
### 结论
1. **「NPU 不支持 INT4」彻底不成立。** 同样是按通道，校准前是乱码（R0），校准后是正常转写（R2）。失败的根源在量化配方，不在 NPU 本身。请把这条写进 STATUS 和最终矩阵。
2. **g128 在 NPU 上走了慢路径。** R1 的 prefill 要 1.6 s，是按通道的 10 倍以上，与精度无关，**g128 不可交付**。R3 也是 g128，没必要跑完：现在就停掉，记为「g128 prefill 1.6 s，不可交付」。如果已经跑完了，结果照常报。
3. R1 的 CI 你的口径算出来不显著，reviewer 的口径算出来显著，两者 CI 都很宽。不影响结论，因为 R1 本来就因为速度出局。
### 下一步：R4（都以 R2 为基础：按通道 + AWQ + scale_estimation，backup INT8_SYM，同一份校准集）
| 编号 | 改动 | 目的 |
|---|---|---|
| R4a | `ratio=0.8`，`sensitivity_metric=HESSIAN_INPUT_ACTIVATION` | 最敏感的约 20% 层保留 INT8_SYM |
| R4b | `ratio=0.9`，同上 | 若 R4a 达标，看能否少留一些 INT8 |
| R4c（可选） | 在 R2 基础上把 AWQ 换成 `gptq=True`（保留 scale_estimation） | 只在 R4a 也显著变差时才做 |
- 评测和判据不变：12–27 分钟全 NPU，WER 配对 CI 包含 0，并且 RTF < 0.778。评分脚本要带上 C-092 的三道断言。第一个通过的配方跑 61 分钟全长。
- 先把 R4a / R4b 都构建完，再串行评测（C-091）。
- 止损：从 C-089 开始算 4 小时，大约到 18:45。到时还没有配方通过，就停下写结论表：R0–R4 各自的 WER/CI、RTF、prefill/decode、体积。

## C-095 [HIGH] 2026-10-18 18:05 — R4 全长：显著变差（不是“通过”）；评分脚本全长模式又出现 CI [0,0]，音频还少了 11 秒。按止损收尾
### reviewer 复核
`R4_npu_full_wer.json` 写的是 `ci95: [0.0, 0.0]`、`ci_contains_zero: true`。这是 C-092 说过的退化：**全长模式没有加那三道断言**。另外有两个问题：
1. `slice_sec: [0, 3660]`，`audio_s 3660`：音频在 **3660 s 处被截断**（全长是 3671.19 s）。只有 225 段，最后一段被截短，3670.49–3671 那一段整段缺失。缺的约 11 s 会被算成删除错误。
2. 因为段数和参照对不上（225 对 226），bootstrap 退化了。
reviewer 只取两边都完整的 0–3658 s（224 段，10964 个参考词）重算：
| 对比 | WER | 差值，95% CI |
|---|---|---|
| R4 对 INT8 全 NPU（c086） | 10.24% 对 8.14% | **+2.11 pp [+1.04, +3.28]，显著变差** |
| R4 对全 GPU（c048） | 10.24% 对 8.04% | +2.21 pp [+1.09, +3.37]，显著 |
| INT8 全 NPU 对全 GPU（对照） | 8.14% 对 8.04% | +0.10 pp [−0.41, +0.55] |
→ **R4 不合格。** 12–27 分钟只有 55 段，统计功效不够，+1.2–1.4 pp 的差落在 CI 里看不出来；到了全长就显著了。
### 要求
1. 修 `c089d`：全长模式也必须做那三道断言——段数一致、CI 宽度 > 0、参照复现。修 `c089c`：全长必须跑到 3671.19 s，不能按整分钟截断。
2. **按止损收尾，不再试新配方。** R5（比如 `ratio=0.6`）是否值得做，由用户决定。若要做，判据直接用全长，因为 12–27 分钟这道门槛已被证明区分不了 1–2 pp 的差异。
3. 写最终结论表，列 R0–R4（R3 照实记录：g128，乱码，prefill 1.6 s）：配方、i4/i8 常量数、体积、RTF、prefill/decode 中位、12–27 分钟 WER 与 CI、全长 WER 与 CI（只有 R4 有）、判定。结论：
   - 在 OpenVINO 2026.4.1 + 本机 NPU 5 上，**按通道 + AWQ + scale estimation** 能让 INT4 在 NPU 上正确运行；
   - 最好的 R4（20% 层保留 INT8）全长 RTF 0.629，比 INT8 快约 19%，但 WER 显著差约 2.1 pp；
   - g128 在 NPU 上 prefill 达 1.6 s，不可用；
   - **交付仍用 INT8_SYM cleanie。**
4. C-090 第 2 条还没做：R0–R4 的 IR（每个约 1 GB）仍在 `reports/c089_int4/` 下，请移到 `models/`，或把 `reports/**/*.bin` 加进 `.gitignore`。**提交前务必确认。**
5. 收尾后接着做 C-090 第 3 条：查全 NPU 平均占 6.1 个 CPU 核花在哪里，只测量。

## C-096 [HIGH] 2026-10-18 20:05 — 有两个 `c089c_eval_recipe.py R4 --full` 在同时跑：停掉一个
19:41:06 启动了 PID 28688（子进程 25872），19:43:01 又启动了 PID 17440（子进程 26360），两份完全一样的全长 R4 评测在并行。
- 它们抢同一个 NPU 和 CPU，**两份的 RTF、prefill、decode 都无效**；如果写的是同一个输出文件，转写也可能互相覆盖。
- 请**停掉后启动的那份（17440）**，让 28688 跑完。如果你判断两份都已被污染，就全停，再单独重跑一份。`heavy_peers()` 应该能发现这种情况：请检查它为什么没有拦住，并补上「同名脚本已在运行就拒绝启动」。
- 跑完后，用修好的 `c089d` 对 3671.19 s 全长重算 R4。若 WER 结论与 reviewer 的 0–3658 s 复核（对 INT8 全 NPU +2.11 pp [+1.04, +3.28]）一致，就把 R4 全长那一行补进 `final_matrix_rows.json`（目前只有切片数据）。
其余收尾接受：
- 三道断言已落地；
- f16 嵌入表无损，md5 已与 c085 逐位一致；
- IR 已移到 `models/`，`.gitignore` 已加上 `reports/**/*.bin` 和 `reports/**/*.xml`；
- 结论「按通道是 NPU 上唯一可行的 INT4 布局；坏的是配方，不是 NPU」接受。
