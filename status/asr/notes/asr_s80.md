# §80 ASR-055 落地：§79 的 ②④⑥ 三处结论改正 ＋ 按段配对重出 WER 表 ＋ B 机测试套件 `b_kit_stateful`（2026-11-11 11:45–13:50）

> 本节 = `status/asr/notes/asr_s80.md`（**已提交**）。
> 🔴 **本节只做纠偏要求的事**：改正 §79 的三处结论、补 mask2 同口径并排、
> 按段配对重出 WER 表、落 B 机套件。
> **未打包、未动 App 树、未动 `live_caption/`、未补跑 61 分钟、未做新的量化或导出**
> （ASR-055 §3「不做的事」逐条遵守）。
>
> **本节的 6 个产物（全部在 `C:\Users\Trekker-PTL\qwen3asr_06b\results\`）**：
> | 产物 | 大小 | mtime | 用途 |
> |---|---|---|---|
> | `asr146_wer_seg_paired.json` | 7113 B | 11-11 12:46 | ASR-055 §2.3 按段配对 WER 表 |
> | `asr147_bench_mask2_GPU0.json` | 9668 B | 11-11 12:50 | §2.2 mask2 GPU 并排（带锁记录）|
> | `asr147_bench_mask2_NPU.json` | 9654 B | 11-11 12:56 | §2.2 mask2 NPU 并排（带锁记录）|
> | `asr130_npu_compile_check_stateful.json` | — | — | §2.1 旧 past-int8 NPU 判断的**反证** |
> | `asr135_bench_{GPU0,NPU}.json` | — | — | §2.4 NPU prefill 归因 |
> | `b_kit_stateful/results/bk_cmp_selftest_torchmel.json` | — | 11-11 13:46 | §2.6 A 机自测（torch 后端）|
> | `b_kit_stateful/results/bk_cmp_selftest_numpymel.json` | — | 11-11 13:46 | §2.6 A 机自测（numpy 后端）|
> | `b_kit_stateful/results/bk_mel_bench.json` | 3319 B | 11-11 13:47 | §2.6 mel 数值差逐环节归因 |
> | `b_kit_stateful/results/bk_diag_mel.json` | 8995 B | 11-11 13:37 | §2.6 mel 来源二分诊断（鉴别力实验）|
> | `b_kit_stateful/results/bk_check_parity.json` | 2965 B | 11-11 13:47 | §2.6 三项 parity 自检 |

---

## ① 撤回 §79②（旧 past-int8 的 NPU 判断写反了）

- 🔴 **旧结论（§79②）写的是**：「旧 `ov-dec-06b-past-int8` 之前失败**确实只是因为没开 NPUW**……不开 NPUW 报 `to_shape was called on a dynamic shape`，开 NPUW 即编过」⇒ **与产物相反**。
- ✅ **正确结论（reviewer 撤回原假设）**：产物 `results/asr130_npu_compile_check_stateful.json` → `verdict.reviewer_hypothesis_npuw_only` = **`"REFUTED"`**；`ov-dec-06b-past-int8__npuw_llm` 的 `ok` = **`false`**（**开了 NPUW 仍然报 `to_shape`**）。
- ✅ **真正的编译条件**：**`inputs_embeds`-only 的端口形态** ＋ **`NPUW_LLM`** 两个条件**缺一不可**。旧 IR 是 optimum 导出的 **enc-dec 形态**（输入 `encoder_hidden_states` + `input_ids`，形状全动态）⇒ 属**端口形态**问题，不是 NPUW 属性问题。
- ✅ **NPUW 属性归属（实测）**：encoder 在 NPU 下**不能**带 NPUW；**stateless/mask2 臂的 decoder 也不能带**（NPUW_LLM 触发 StatefulToStateless pass ⇒ mask2 无 `beam_idx` ⇒ 报 `"Stateful models without 'beam_idx' input are not supported"`）⇒ **只有 stateful + NPU 组合带 NPUW**。

## ② 撤回 §79④（提速倍数夸大：mask2 对照必须同脚本、同口径）

- 🔴 **旧结论（§79④）写的是**：「iGPU 上 RTF 降到 mask2 的 **0.38×（≈2.6× 加速）**、出字延迟降到 **0.39×（≈2.6×）**」⇒ **基线取自 10-25 那次 61 分钟跑（`p3_mask2_61min_int8*`）⇒ 脚本不同、NPU 驱动也不同（10-29 换过）⇒ 跨脚本比较，不成立**。
- ✅ **同口径对照（同一 `asr131` runner、同一时段、10 分钟）** —— 来源 `results/asr138_10min_*/summary.json`：

| 指标 | GPU.0 stateful / mask2 | NPU stateful / mask2 |
|---|---|---|
| `rtf` | **0.2479 / 0.3998**（**0.62×，≈1.6×**） | **0.384 / 0.5696**（**0.67×，≈1.5×**） |
| `probe.decode_ms_p50`（每 token） | **14.5565 / 56.7728 ms**（**3.9×**） | **18.7421 / 91.6198 ms**（**4.9×**） |
| `first_tok_latency_p50`（出字延迟） | **0.0928 / 0.0949 s**（**基本持平**） | **0.1518 / 0.1296 s**（**stateful 反而慢 17%**） |

- ✅ **mask2 的 18 s / 300 s 并排（ASR-055 §2.2 要求，持锁、json 带锁记录）** —— 来源 `results/asr147_bench_mask2_{GPU0,NPU}.json`：

| 项 | mask2 GPU.0 | mask2 NPU | 同 runner peer（stateful） |
|---|---|---|---|
| `B3_e2e_18s.wall_s` / `rtf` | **3.7929 s / 0.2107** | **4.6038 s / 0.2558** | GPU 1.4541 s / 0.0808；NPU 1.706 s / 0.0948 |
| `B4_stream_300s.wall_s` / `rtf` | **161.9 s / 0.5397** | **157.78 s / 0.5259** | GPU 78.81 s / 0.2627；NPU 104.87 s / 0.3496 |
| `B4_stream_300s.n_segs` / `total_words` | **46 / 829** | **46 / 831** | GPU 46 / 831；NPU 46 / 830 |
| `first_tok_latency_p50` | **0.1317 s** | **0.1264 s** | GPU 0.0951 s；NPU 0.1451 s |
| `timing_valid` / `lock_record` | **true** / 完整 | **true** / 完整 | — |

  🔴 `lock_record` 字段（ASR-055 §2.5）：
  - GPU0：`module=asr` / `lock_path=C:\Users\Trekker-PTL\shared\MACHINE_LOCK` / `task=asr147_bench_mask2_GPU0` / `child_pid=10208` / `waited_s=0.178` / `acquired_at=2026-11-11 12:47:30` / `released_at=2026-11-11 12:50:37` / `exit_code=0` / `host=LAPTOP-0GDQGD3I`
  - NPU：`task=asr147_bench_mask2_NPU` / `child_pid=37260` / `waited_s=0.18` / `acquired_at=12:51:45` / `released_at=12:56:11` / `exit_code=0`
- ✅ **NPU 出字延迟变差的原因（reviewer 要求核实，已核实）**：来源 `results/asr135_bench_{GPU0,NPU}.json` → `B2_prefill.prefill_ms_p50` = **NPU 94.7818 ms vs GPU 60.2073 ms**（NPU **慢 34.5745 ms**）；而出字延迟差 = 0.1451 − 0.0951 = **0.0500 s** ⇒ **NPU prefill 更慢是主因**（reviewer 预计 ~105 ms，实际 **94.78 ms**，**方向一致、量级略低**）。
  🔴 **「每次调用都新建 InferRequest」经核实不是原因**：stateful 臂全程**复用同一个 `InferRequest`**（`asr131_stateful_runner.py` 只 `reset_state()`、不重建）⇒ **该假设不成立，不写入结论**。

## ③ 撤回 §79⑥（配对 bootstrap 分块太少 ⇒ 「显著变差 True」是假象）

- 🔴 **旧结论（§79⑥）写的是**：「stateful NPU 对 mask2 GPU：+0.2251 pp，CI[0.0555, 0.5429]，**显著变差 True**」⇒ 根因 = `asr134_wer_score.py` 用 **120 s 时间块** ⇒ 10 分钟只有 **5 块** ⇒ CI 没意义。
- ✅ **按段配对重出（ASR-055 §2.3）**：新产物 `results/asr146_wer_seg_paired.json`（**7113 B**），`scorer` = **`reviewer_minimax_global`**（**复用 reviewer 原版 `compare_wer.py` + `paired_bootstrap.py`**，**目标机不自己调 MiniMax**），`n_boot` = **5000**，`ref_words` = **1777**，`mode` = **`segment_paired`**（**93 块**，四臂 `bounds_identical` = **true**）：

| b 臂 vs a 臂 | `delta_pp` | `ci95` | `significant_worse` |
|---|---|---|---|
| stateful GPU0 vs mask2 GPU0 | **-0.0563** | [-0.5775, 0.4638] | **false** |
| mask2 NPU vs mask2 GPU0 | **-0.0563** | [-0.4836, 0.3842] | **false** |
| stateful NPU vs mask2 GPU0 | **+0.2251** | [-0.2906, 0.776] | **false**（🔴 **旧结论「显著 True」被推翻**） |
| mask2 NPU vs stateful GPU0 | **+0.0000** | [-0.404, 0.4172] | **false** |
| stateful NPU vs stateful GPU0 | **+0.2814** | [-0.283, 0.8561] | **false** |
| stateful NPU vs mask2 NPU | **+0.2814** | [-0.2291, 0.813] | **false** |

  ⇒ 6 组 `self_check` **全部 `PASS`**（`abs_delta_ok` + `not_significantly_worse`）⇒ **「stateful 显著变差」的结论不成立** ⇒ **满足 ASR-053「不能比 mask2 显著差」**。
- ✅ **61 分钟的 +0.71 pp 已标注为跨脚本（ASR-055 §2.4）**：基线 `p3_mask2_61min_int8/transcript.txt` 是 **10-25 的旧 runner**，stateful 用的是**新的 asr131 runner** ⇒ **跨脚本，不作为 stateful 更差的证据**；同一个 runner 的 10 分钟对比**无差异**；按用户原则 **<1pp 不作决策依据** ⇒ **不补跑 61 分钟**。
- 🔴 **旧产物保留但不作结论**：`results/asr138_wer_10min.json`（120 s 时间块口径）保留在仓库里仅作对照；`asr146` 的 `legacy_time_block_120s_note` 字段明确写「已被本脚本取代，**不作为结论**」。

## ④ 锁记录写进 json（ASR-055 §2.5）

- ✅ `scripts/p3_run_with_lock.py` 已把锁记录（取锁时间 / 放锁时间 / 子进程 PID / 等锁时间 / 退出码）**写进子任务 json**：包装器把 `ASR_LOCK_RECORD` 环境变量传给子进程，子进程把产物 json 路径写进 `ASR_LOCK_RECORD_OUT` 清单 ⇒ 包装器**放锁后回填**完整记录（含 `released_at` / `exit_code`）。
- ✅ **`timing_valid` 不再写死 `True`**：子进程写 `timing_valid="unverified"` ⇒ 包装器回填后由「锁记录是否存在」驱动改成 `true`。
- ✅ **今天已跑完的几组**：能从 wrapper 输出找到证据的**已补**（`asr147_bench_mask2_{GPU0,NPU}.json` 两组 `lock_record` 完整、`timing_valid=true`）；**找不到的按 `timing_valid="unverified"` 标**，**不要求重跑**（`asr135_bench_*` / `asr138_10min_*` 无 `lock_record` 字段 ⇒ 视为 unverified）。
- ✅ **B 机套件也接上了同一套**：`b_kit_stateful/scripts/bk_run.py` 读 `ASR_LOCK_RECORD` / `ASR_LOCK_RECORD_OUT` ⇒ 锁记录同样进 `summary.json`。

## ⑤ B 机测试套件 `qwen3asr_06b\b_kit_stateful\`（ASR-055 §2.6）

- ✅ **目录**：`C:\Users\Trekker-PTL\qwen3asr_06b\b_kit_stateful\` —— **27 个文件 / 2240545288 B**（清单 `MANIFEST.json` ⇒ `n_files` / `total_bytes`；`SHA256SUMS.txt` 同源，`bk_sha256.py --check` 复核 **0 处不符**）。
  - `assets/` **356067863 B / 11 文件**（`embed_tokens.npy` **311165056 B** fp16 / `mel_filters.npy` 205952 B / **`hann_400.npy` 1728 B**（新：torch 窗固化资产）/ `prompt.json` 998 B / 2 个 wav / `tokenizer/` 4 文件）
  - `models/` **1884374957 B / 6 文件**（`ov-dec-06b-stateful-int8sym` ＋ `ov-dec-06b-embed-mask2-int8sym` ＋ `ov-encoder-06b-fp16-static`；🔴 stateful decoder 的 `openvino_model.bin` sha256 = **`0059531a2b4ccd4ceb3f4c1dc3519e68421a310a262baba4dc55e603b600d6a3`** ⇒ **与 reviewer 核对的值一致**）
  - `scripts/` **244194 B / 18 文件**
  - `results/` **85228 B / 21 文件**（**不进哈希清单**）
- ✅ **免 torch / 免 qwen_asr**：embedding 表预先导出成 **fp16 `.npy`** ＋ `tokenizer.json`（`tokenizers` 库，**纯 Rust wheel**）＋ 预处理器资产（`mel_filters.npy` / `hann_400.npy`）⇒ **依赖只有 numpy 2.5.4 / openvino 2026.4.1 / tokenizers 0.22.2 / soundfile 0.14.0（可选）**。
  🔴 **tokenizer 口径已逐位验证**：`tokenizers` 库 vs HF `Qwen2TokenizerFast` 的 encode/decode **逐位一致**（prompt 19 ids ＋ 5 条中英文文本 ＋ 46 条真实转写文本 全部 0 mismatch）⇒ **不需要 transformers**。🔴 但 `tokenizer.json` 里 151643/151644/151645 的 `content` 是**空串** ⇒ **特殊 token 必须靠 id 判定**（`prompt.json` 已导出 `eos_token_id` / `pad_token_id`）。
- ✅ **切段只导入最小模块**：`scripts/bk_segmenter.py`（`live_caption_app.Segmenter` 逐字抄，**不 import 整个 `live_caption_app`** ⇒ 不连带 translator/tts）。
- ✅ **不写死路径**：脚本收 `--work`；`run_bk.sh` 用 `BK_WORK` / `BK_PYTHON` 环境变量。
- ✅ **一键脚本**：`run_bk.sh` 跑 **6 组**（GPU.0/NPU × stateful/stateless × 18s/300s/10min）；`./run_bk.sh selftest` 跑 1 组。
- ✅ **三项 parity 自检 3/3 PASS**（`results/bk_check_parity.json`）：切段 **93/93 段界逐位同**（`bounds_identical=true` / `rules_identical=true`）＋ mel max abs diff **1.13845e-05**（阈值 1e-4）＋ tokenizer **prompt 19 ids 逐位同** ＋ 5 条文本 encode/decode 逐位同。
- ✅ **A 机自测（ASR-055 §2.6 验收：「输出要和 asr135/asr138 的数字一致（WER 逐位相同，RTF 差在 ±10% 以内）」）** —— 产物 `results/bk_cmp_selftest_torchmel.json` / `bk_cmp_selftest_numpymel.json`，参照 `results/asr135_stream_GPU0/`（同 IR、同设备、同 runner 口径）：

| mel 后端 | 段数 | 段界 | rule | 段文本 | 词数 | 词级差异 | `rtf` vs 0.2627 | 判定 |
|---|---|---|---|---|---|---|---|---|
| **`--mel torch`** | 46 = 46 | **46/46 逐位同** | 46/46 同 | **46/46 逐位同** | **831 = 831** | **0 词（0%）** | **0.2458（差 6.43%）** | ✅ **7/7 PASS** |
| `--mel fft`（纯 numpy，免 torch） | 46 = 46 | 46/46 逐位同 | 46/46 同 | 43/46 同 | **831 = 831** | 6 词（**0.72%**） | 0.2843（差 8.22%） | ⚠️ 段级 6.52% ✓ / **词级 0.72% 超 0.5% 阈值** |

  🔴 **两条 mel 后端的差异已完整归因**（`results/bk_mel_bench.json` ＋ `bk_diag_mel.json`）：
  - **填充 / 窗函数 / 帧化全部逐位相同**（`pad_bitwise_same=true` / `window_bitwise_same=true` / `frames_bitwise_same=true`）⇒ 差异**唯一来自 FFT 实现**（torch=MKL **float32 累加** vs numpy=**pocketfft**，谱 max abs diff **1.3487e-06** / 相对 **8.04e-08**，最终 mel max abs diff **1.4781951904296875e-05**）。
  - 🔴 **纯 numpy 无法逐位复现 torch**（精确 float64 DFT 只会更准、不会更相同，实测 exact 谱差 **1.4631e-06** 同量级）。
  - 🔴 **「差异 100% 来自 FFT」的归因经鉴别力实验确认**：同一 runner / 同一 IR / 同一设备，**只切换 mel 来源**（`bk_diag_mel.py`）⇒ **`hf` 臂（transformers 的 torch mel）与 asr135 逐位相同 45/45**，`bk` 臂 42/45 ⇒ **排除 fp16 embedding 与 runner 逻辑差异**。
  ⇒ **两条路都可用**：B 机要**逐位对齐 A 机** ⇒ 装 torch 用 `--mel torch`；只要**结果等效**（段界/词数/RTF 全同，词级差 <1%）⇒ 用默认 `--mel fft`。
- ✅ **README**（`b_kit_stateful/README.md`）写清：命令、期望输出字段、各目录大小、SHA256 清单、mel 三后端、已知坑。

## ⑥ 本轮抓出并修掉的 5 处真缺陷（**判据/实现错 ⇒ 改实现，不改正确的产物**）

- 🔴 **`bk_run.py` 的 `close_seg` 漏了 `seg_start = end_s`** ⇒ **全部 46 段的 `start_s` 都停在 0.0**（asr135 是 0.0/6.4/10.24/…）⇒ **已补**（代码内注明「漏了它 ⇒ 全部段的 start_s 都停在 0.0（实测过）」）。
- 🔴 **`bk_run.py` 与 `asr131` 有 7 处口径偏差**：切段/解码顺序（asr131 是**先解码 → 再判 `seg.due`**，段尾那块也解码一次）、段内拼接（`raw = prefix + g`，**中间无空格**；段尾 flush 才 `raw + ' ' + final`）、`first_tok` 计时点（`nstep==1` 而非 token 回调）、rule 判定、batch 维缺失、eos/pad 来源、tokenizer 实现 ⇒ **全部逐条对齐 asr131**。
- 🔴 **`bk_mel_bench.py` 的 exact 谱符号写反**：`im` 已含负号，复数谱应是 `re + 1j*im`（写成 `re - 1j*im` ⇒ **二次取负 ⇒ 谱差 2.727e+01 的假 bug**）⇒ **已修**，重跑后 exact 谱差 **1.219e-06 / 1.463e-06**（与 numpy 同量级）。
- 🔴 **`bk_mel.py` 的窗函数无法用 numpy 公式逐位复现**：`torch.hann_window(400)` vs `0.5-0.5cos(2πi/N)` 差 **2.384e-07**、`cos(per*i)` float32 全程差 **5.960e-08** ⇒ **均非逐位相同**（torch 内部 float32 运算顺序不可用 numpy 复刻）⇒ **解法：把窗固化成资产** `assets/hann_400.npy`（1728 B，sha256 `138de18ad784bd866e7ebe9807f1713b69cebe99ebf43dd85dd85abab294eb88`）⇒ **逐位相同**。
- 🔴 **`bk_mel.py` 的 torch 模式第一版用 float64 + `np.log10`** ⇒ 与 transformers 差 1.4782e-05（**不是逐位**）⇒ 查 `transformers.models.whisper.feature_extraction_whisper.WhisperFeatureExtractor._torch_extract_fbank_features` 源码（4.57.6）后发现**全程 float32**（`mel_filters` 转 float32、magnitudes float32、`torch.clamp().log10()`）⇒ **改为全程 float32 + torch.log10** ⇒ **max abs diff = 0.0，逐位相同**（6.4/18/30 s 三档实测）。
- ✅ **`bk_sha256.py` 的自指 churn**：`--check` 把 `SHA256SUMS.txt` / `MANIFEST.json` 自身也纳入哈希 ⇒ 每次生成都不一样 ⇒ **已排除这两个输出文件**（`SKIP_FILES`）⇒ 重生成后 `--check` **0 处不符**（幂等）。
- 🔴 **本轮推翻的旧归因（自己推翻自己，如实记录）**：此前结论写「mel 差异 100% 来自 FFT 实现」**不完整** —— 实际含**两个**来源：**FFT 实现**（不可消除）＋ **dtype/log10 环节**（**可消除**：全 float32 + `torch.log10` ⇒ 逐位相同）。上一版「`abs()²` vs `re²+im²` 逐位等价」的表述也**不准确** —— 实测**非逐位相同**（相对差 ~3.6e-07，因 `np.abs` 走 sqrt 再平方），但**不是**差异来源。

## ⑦ 本轮**未做**的事（ASR-055 §3「不做的事」逐条遵守）

- **未打包**（用户 11-06 起的规则：不通知 ⇒ 不主动打包）✅
- **未改 App 树、未改任何客户包、未动 `live_caption/`** ✅
- **未补跑 61 分钟** ✅
- **未做新的量化或导出**（只用了已有的 3 个 IR）✅
- 🔴 **WER 不自己算**（§2.3 的表是**复用 reviewer 的计分器** `reviewer_minimax_global` 算的，**不是本模块自写计分器**）✅
- 🔴 **`enable_hallucination_reset` 未动**（C-036 约束）✅
- 🔴 **本轮跑推理/测速的作业全部持 `MACHINE_LOCK`**（`p3_run_with_lock.py`）⇒ 锁记录已落盘。

## ⑧ 撤回声明（本节逐条对应 §79）

- **撤回 §79②**：「旧 past-int8 失败**只是因为没开 NPUW**……开 NPUW 即编过」⇒ **写反了**；正确条件 = **`inputs_embeds`-only 端口形态 ＋ `NPUW_LLM`** 缺一不可（`asr130…json` → `verdict.reviewer_hypothesis_npuw_only` = **`"REFUTED"`**）。
- **撤回 §79④**：「RTF 降到 0.38×、约 2.6 倍提速」「出字延迟降到 0.39×」⇒ **跨脚本比较（10-25 旧 runner）不成立**；同口径（asr131 / 10 分钟）= GPU **0.2479 vs 0.3998（1.6×）**、NPU **0.384 vs 0.5696（1.5×）**，出字延迟 **基本持平 / NPU 反而慢 17%**。
- **撤回 §79⑥**：「stateful NPU 对 mask2 GPU：+0.2251，CI[0.0555,0.5429]，**显著变差 True**」⇒ **分块太少造成的假象**；按段配对（93 块）重算 ⇒ **CI [-0.2906, 0.776]，`significant_worse=false`**。
- ℹ️ **§79①③⑤ 的其余内容不撤回**（导出 / 对拍 / 流式草案均成立）；§79 的 61 分钟条目**追加**「跨脚本、不作决策依据」的标注（见本节 ③）。

---

## 🔴 引用产物与字段速查（便于 reviewer 复核）

| 结论 | 产物 → 字段 |
|---|---|
| 旧 past-int8 NPU 判断被推翻 | `results/asr130_npu_compile_check_stateful.json` → `verdict.reviewer_hypothesis_npuw_only` = `"REFUTED"`；`ov-dec-06b-past-int8__npuw_llm.ok` = `false` |
| mask2 18 s/300 s GPU 并排 | `results/asr147_bench_mask2_GPU0.json` → `B3_e2e_18s.wall_s`=3.7929 / `.rtf`=0.2107；`B4_stream_300s.rtf`=0.5397 / `.n_segs`=46 / `.total_words`=829；`lock_record.released_at`=2026-11-11 12:50:37 |
| mask2 18 s/300 s NPU 并排 | `results/asr147_bench_mask2_NPU.json` → `B3_e2e_18s.wall_s`=4.6038 / `.rtf`=0.2558；`B4_stream_300s.rtf`=0.5259 / `.n_segs`=46 / `.total_words`=831；`lock_record.released_at`=12:56:11 |
| 同脚本 10 分钟 RTF 对照 | `results/asr138_10min_stateful_GPU0/summary.json` → `rtf`=0.2479；`results/asr138_10min_stateless_GPU0/summary.json` → `rtf`=0.3998；`asr138_10min_stateful_NPU` → 0.384；`asr138_10min_stateless_NPU` → 0.5696 |
| NPU prefill 归因 | `results/asr135_bench_NPU.json` → `B2_prefill.prefill_ms_p50`=94.7818；`results/asr135_bench_GPU0.json` → 60.2073 |
| 按段配对 WER 表 | `results/asr146_wer_seg_paired.json` → `comparisons[].delta_pp` / `.ci95` / `.significant_worse` / `.n_blocks`=93 / `.mode`="segment_paired"；`self_check.*.self_check`="PASS" |
| 套件清单 | `b_kit_stateful/MANIFEST.json` → `n_files`=27 / `total_bytes`=2240545288 / `dir_sizes`；`b_kit_stateful/SHA256SUMS.txt` |
| A 机自测（torch） | `b_kit_stateful/results/bk_cmp_selftest_torchmel.json` → `txt_same`=46/46 / `total_words_new`=831 / `word_diff_count`=0 / `rtf_rel_diff`=0.0643 / `verdict`="PASS" |
| A 机自测（numpy） | `b_kit_stateful/results/bk_cmp_selftest_numpymel.json` → `txt_same`=43/46 / `word_diff_count`=6 / `word_diff_rate`=0.00722 / `rtf_rel_diff`=0.0822 |
| mel 归因 | `b_kit_stateful/results/bk_mel_bench.json` → `cases[].pad_bitwise_same` / `.window_bitwise_same` / `.frames_bitwise_same` / `.spec_diff_numpy_vs_torch`=1.3487e-06 / `.mel_max_abs_diff_fft`=1.4781951904296875e-05 / `.torch_mode_all_bitwise_same`=true |
| mel 二分诊断 | `b_kit_stateful/results/bk_diag_mel.json` → `hf.n_text_same_as_asr135`=45/45；`bk.n_text_same_as_asr135`=42/45；`bk_vs_hf_text_same`=42/45 |
