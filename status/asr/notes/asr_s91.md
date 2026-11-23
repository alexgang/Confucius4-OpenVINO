# ASR §91 —— 纯巡检 ＋ App §221 交付面只读复核（2026-11-23 10:57–11:15）

> 🔴 **本轮性质**：**纯巡检 ＋ 只读复核**。
> - 纠偏文件通道：**无新 ASR 条目**（`CORRECTIONS_ASR.md` **105 868 B** / md5 `b6fd2e14…` / mtime **2026-11-20 15:33** ⇒ 最大编号 **ASR-066**、**无 ASR-067+**）⇒ **`last_ack` 保持 `ASR-066`**。
> - QQ 邮箱通道：**无新 ASR 邮件**（收件箱最新 = reviewer 的 **APP-121**，11-23 09:03，已于 §89 回复 `msg_Ex0uv-KzX…`；其后 3 封是 **TTS-076 / TTS-077 / MT H-027**，均非 ASR 编号）。
> - 🔴 **本轮只读**：未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 `live_caption/`、未改纠偏文件、未改旧章节。
> - 🟢 **但 App 线程在 §90 之后落了 `88b9ea8`（APP-121 §221）** ⇒ 交付面发生了实质变化 ⇒ **本轮对 App 的交付面做了只读复核**，并**首次发现 1 条 ASR 契约层面的新问题**（见 §三）。

---

## 一、§90 的 3 条只读结论，逐条复核现在的状态

| §90 结论 | 本轮复核结果 |
|---|---|
| ① 现有 zip（v1.1）解压后过不了自己的验收绑定闸门（`CONTENT_MISMATCH`，缺 `tts_cuda*`） | 🔴 **仍然成立，且已复现**（旧 zip 未被覆盖）：`v1.1.zip` 内 `ACCEPTED.json` `version=1.1`、**`n_fp=33`**，但 zip 内 `app/` 根目录**没有** `tts_cuda.py` / `tts_cuda_sidecar.py` ⇒ `missing = ['tts_cuda.py','tts_cuda_sidecar.py']`。**处置**：App §221 §3 已把这两个模块**改名挪到包外（未删）** ⇒ **新 zip 不再有此问题**；但**旧 `v1.1.zip` 仍在磁盘上（5 212 356 737 B / 11-22 16:51）且仍不自证** ⇒ 🔴 **交付前必须确认发出去的是 `v1.1.1.zip`，不是 `v1.1.zip`**。 |
| ② `MiniMVP_v1.1.1` 目录已同步修法版但 `ACCEPTED.json` 未重签（`VERSION_MISMATCH`） | 🟢 **已解决**（App §221 §5 重签 1.1.1）⇒ 本轮用**权威闸门** `pack_v13.check_acceptance_binding` 只读复跑：`v1.1.1` 目录 ⇒ **`ok=True` / `reason=OK`**（`accepted_version=1.1.1` / `n_registered=31` / `n_current=31` / `n_changed=0` / `n_missing=0` / `n_extra=0`）；`v1.1` 目录 ⇒ 也 `ok=True`（`n_registered=33` / `n_current=33`）—— 🔴 注意：**`v1.1` 目录自己是自洽的**，它不自洽的是**它的 zip**（见①）。 |
| ③ item 2 的 App 后端三素材 md5 补测仍未产出 | 🟢 **已产出**（App §221 §2）：`results/app/app121_asr_app_3mat_{NPU,GPU0,GPU0_OLD_v11}.json`（**走 App 后端** `ASR06BStatefulBackend`，非 ASR 模块的 `bk_run`）⇒ **§88④/⑤ 撤回后一直缺的替代证据，本轮到位**。明细见 §二。 |

---

## 二、App §221 交付面的只读复核（ASR 侧关心的部分）

### 2.1 §1 缺陷已修（长段不再让字幕整条停掉）—— 本轮独立复现
- 旧包 `v1.1`（`app/asr06b_stateful_backend.py` md5 **`a92c02f2…`** ＝ §89 判定的缺陷版）：`results/app/app121_asr_npu_longseg_old_v11.json` ⇒ **`rc=1`**、`has_valueerror=true`、**字幕 `n_final_lines=0`**、`ValueError: prompt 骨架 281 + 预留 64 > stateful 上界 320（音频过长）`。
- 新包 `v1.1.1`（同文件 md5 **`4b43dcbc…`** ＝ 修法版）：`…_new_v111.json` ⇒ **`rc=0`**、`has_valueerror=false`、**字幕 `n_final_lines=2` / `n_chars=514`**。
- ⇒ 🟢 **§89 的 HIGH 缺陷已闭环**；§89 补正的 handoff 契约（`allowed_prefix = limit − skeleton`，**不减 reserve**）与 App 实现**一致**：`live_caption/asr06b_stateful_backend.py` L583-591（`is_npu` 分支）确实是 `allowed_prefix = limit - skeleton` ＋ `skeleton > limit` 才抛错 ＋ 总量检查 `prompt + reserve ≤ limit + 64`；**GPU 档（L593-598）一字未动**。
- 🟢 **单测口径自证**：`results/app/app121_asr_npu_prefix_unit.json` ⇒ **11/11 PASS**、`n_fail=0`、`result="PASS"`；含**反证组**（`anti_group`：旧文件 sha256 `07fff396…`，9 个 NPU 用例中旧版错抛 4 次、其中 2 个「本该通过」被错抛）⇒ **反证组证明新逻辑确实改掉了行为，不是空转**；**截断口径一致性 3/3 PASS**（同一 `n_audio` 下 `reserve=32` 与 `reserve=64` 保留的前缀数相同 ⇒ 流式档与段尾档口径统一）。

### 2.2 交付面自证（§90 reviewer item 2/3）—— 本轮独立复算
- 🟢 **新 zip 自证通过（本轮自己算的，不是转述）**：`Confucius4_LiveCaption_MiniMVP_v1.1.1.zip`（**5 212 403 155 B**，11-23 10:31）内 `ACCEPTED.json` `version=1.1.1`、`n_fp=31`；用 **`pack_v13._acc_module_fingerprints` / `_acc_aggregate` 同一口径**（§90 教训：**不要手写**）从 zip 内 `app/` 逐个重算 ⇒ **`ok=31` / `missing=[]` / `changed=[]` / `extra=[]`**，且 zip 内 `app/` 根目录恰好 **31 个 .py** ⇒ 🔴 **§90 的「zip 必须自证」这一条对新 zip 成立**。
- 🟢 **README 的 zip 口径数字是对的**（本轮核过，不是错）：README 写「**10 881 个文件 / 6 701 780 843 B（6.242 GiB）**」⇒ 实测 zip **entries=10881**、**解压后总字节=6701780843** ⇒ 是**解压后**口径，**与 zip 磁盘占用 5 212 403 155 B 不同**（压缩比正常）⇒ **不是缺陷**。
- 🟢 **ACCEPTED 模块清单已对齐**：App 把 `tts_cuda.py` / `tts_cuda_sidecar.py` **改名挪到包外（未删）** ⇒ `v1.1.1/app/` 根目录 **31 个 .py**，与 `ACCEPTED.json` 的 31 条**一一对应**（本轮实测 `extra=[]`）。
- 🟡 **`timing_valid=false` 的归因已更正**：App 已撤回「机器被占」这个无证据归因，改记 `synth_rtf P90=1.1126 > 0.75` ⇒ **计时类结论不作数，计数类不受影响**（164 句 / 丢弃 0）。⇒ 🟢 **ASR 侧不引用 App 的计时数字**。

### 2.3 item 2 的 App 后端三素材 md5 —— 本轮独立复核结果
`results/app/app121_asr_app_3mat_{NPU,GPU0,GPU0_OLD_v11}.json`（`backend_class` = 包内 `live_caption_app.py.asr06b_stateful_backend.ASR06BStatefulBackend`；`env.ov_version` = **2026.4.1-22982** ⇒ **OV 版本口径与 §86/§87 参照一致** ✅）：

| 素材 | 段数（App / 参照） | NPU md5 | GPU.0 md5（新 v1.1.1） | GPU.0 md5（旧 v1.1） | NPU `prefix_truncations` | GPU.0 `prefix_truncations` |
|---|---|---|---|---|---|---|
| SPE | 93 / 93 | `2d7218ae…` | `d68715df…` | `d68715df…` | **0** | **0** |
| EN | 65 / 65 | `8a7e64cf…` | `fbe91f2a…` | `fbe91f2a…` | **0** | **0** |
| ZH | 66 / 66 | `e4efbe48…` | `57ce6bc1…` | `57ce6bc1…` | 🔴 **3** | **0** |

- 🟢 **「GPU 档对旧包零回归」本轮独立复核成立**：新旧包 GPU.0 三素材 md5 **逐字节相同**（`d68715df…` / `fbe91f2a…` / `57ce6bc1…`）⇒ **§1 的 NPU 档修改没有碰到 GPU 档**。
- 🔴 **App 侧 NPU md5 与 §86 参照 md5 不相同**（SPE `2d7218ae…` ≠ `cd67417e…`、EN `8a7e64cf…` ≠ `ed3f52aa…`、ZH `e4efbe48…` ≠ `d93062a6…`）⇒ **§88④「App 侧 NPU 逐字节复现参照」撤得对**；**这次是真正用 App 代码跑的**，证实**撤得对**。
- 🟢 **但要注意 App 自己写的「3 条原因」里有 1 条不成立**（见 §三 ②）⇒ 差异的真正机理见 §三。

---

## 三、🔴 本轮新发现：App 侧 NPU 的 `prefix_truncations=3`（ZH）—— ASR 契约层面的一条新问题

### 3.1 现象（原始字段）
- `results/app/app121_asr_app_3mat_NPU.json` ⇒ ZH 素材 `prefix_truncations=3`、**GPU.0 同素材 `prefix_truncations=0`** ⇒ **同素材、同样切段，NPU 档多砍了 3 次前缀，GPU 档 0 次** ⇒ **这是设备档差异，不是素材差异**。
- 🔴 **同时意味着**：§86/§87 的参照（**NPU 档**、pml=320、OV 2026.4.1）在 15 臂上 `prefix_truncations` **全为 0**（`bench.json` 每条 run 都是 `prefix_truncations=0`），而 **App 的 NPU 路径在同一素材上打出了 3 次** ⇒ **ASR 侧参照的「计数 0」不能代表 App 生产路径**。

### 3.2 机理（本轮只读定位，未跑推理）
**不是** App 的 `allowed_prefix` 口径问题（§2.1 已验证修法正确）。真正机理是 **ASR 参照与 App 的「前缀内容」口径不同**：

| | ASR 参照（`bk_run.run_stream`） | App（`live_caption_app.py`） |
|---|---|---|
| 前缀来源 | `_prefix_for_chunk(tok, raw, nstep)`：`nstep <= UNFIXED_CHUNK_NUM(=2)` ⇒ **前缀为空**；否则取 `decode(ids[:len-5])` | `streaming_asr.py` L262-286：`state.chunk_id < state.unfixed_chunk_num` ⇒ 空；否则 `decode(cur_ids[:end_idx])`，`end_idx = len(cur_ids) - unfixed_token_num(=5)` |
| 前缀内容 | **流式解码的 `raw`**（段内累积） | **段尾 `_finalize()` 的 `st._raw_decoded`**（整段累积文本） |
| 实测前缀长度 | `probe_detail.prefix_len_tokens`：**max=1**、p95=1.0、`n_nonzero=66/797` ⇒ **前缀几乎恒为空/1 token** | `_finalize` 传的是**整段文本** ⇒ 段长 20.48 s 的 ZH 段前缀 **21–43 token** |

🔴 **关键算术（本轮用 `bk_mel.total_aftercnn_len` 同公式复算）**：
- 20.48 s 段 ⇒ 2048 mel 帧 ⇒ **音频 token = 266** ⇒ `skeleton = 18 + 266 = 284` ⇒ NPU 档 `allowed_prefix = 320 − 284 = **36**`。
- App 的 4 个 20.48 s ZH 段前缀长度（本轮用包内 tokenizer 只做 tokenize、**无推理**）= **39 / 43 / 32 / 21 token** ⇒ 🔴 **39 与 43 > 36 ⇒ 这 2 段必然触发截断**（另 2 段 32/21 尚在预算内）；实际计数 **3** ⇒ 第 3 次应来自**同一长段内的流式块调用**（App 的流式块与段尾 `_finalize` 走**同一条** `build_inputs_embeds`，前缀同样随 `audio_accum` 增长）⇒ 🟡 **json 只给总数、未给逐次 trunc 明细** ⇒ **第 3 次的确切来源本轮未逐次定位**。
- ⇒ 🔴 **触发条件**：**段长 ≈20.5 s（`skeleton=284`）＋ 段内累积文本 ≥ ~36 token** ⇒ **NPU 档必然截断**；而 **GPU 档 `limit=512` ⇒ `allowed_prefix = 512 − 284 − 64 = 164`** ⇒ **同样的前缀（21–43）远不到 164 ⇒ 0 次** ⇒ **完美解释「NPU=3 / GPU=0」**。

### 3.3 后果与定性
- 🟢 **实测：4 个 20.48 s 长段的 NPU 与 GPU.0 转写「逐字节相同」**（`same=True`，4/4）⇒ 🔴 **重要限定**：**本轮没有观察到长段被截断后丢字** ⇒ **「截断 ⇒ 丢句首」在本轮数据上未被证实**（不能下这个结论）。
- 🟡 **NPU 与 GPU.0 的 ZH 转写差异（`difflib` 字符级相似度 0.9975）共 4 处，差异段全是 6–11 s 的短段**（seg 9 / 30 / 50 / 60，**无一落在 4 个长段上**）⇒ 差异形态是**同音/近形词分歧**（`黑化`↔`黑话`、`克，`↔`克·`、`，并`↔`。并`）＋ **1 处句首多字**（NPU「**是**年轻恐龙的尾巴」 vs GPU「年轻恐龙的尾巴」，NPU 多 1 字）⇒ **更像是 NPU 与 GPU.0 的浮点数值分叉（贪心解码在分叉点走岔）**，**不是**前缀截断造成的（截断只发生在长段，而长段两侧完全一致）。
- 🔴 **所以本条新发现的定性是**：
  - ✅ **成立且重要**：**App 的 NPU 生产路径在真实素材上会打 `prefix_truncations=3`**（ZH）⇒ **handoff §四 的「正常素材不会触发（计数 0）」在 App 路径上不成立** ⇒ **前提要改写**。
  - 🟡 **「截断导致质量下降」目前无证据**：本轮 4 个长段两侧逐字节相同 ⇒ **质量影响仍属「未测」**（与 ASR-066 当时的措辞一致），**不能**因为出现计数就断言丢字。
  - 🟡 **但风险真实存在**：截断丢弃的是**前缀左端（段内较早的已确认文本）** ⇒ 若某段的前缀长度**超过** `allowed_prefix`，句首会被砍；本轮最长前缀 43 token vs 预算 36 ⇒ **已经贴边** ⇒ **段内文本再长一点就会真丢** ⇒ **属「机制成立、本轮未触发到可见损失」的边界情形**。
- 🔴 **更关键**：`§三之二` 写「段长 ≤ `MAX_SEG_SEC` = 20.0 s（实测最长 20.48 s）⇒ `base_len ≤ 284 ≤ 320` ⇒ **余量 36 token** ⇒ **永不触发**」⇒ 🔴 **这 36 token 的余量只够骨架，**不够**带上前缀** ⇒ **前提不完整**：真正的余量约束应是「**段长上限 ＋ 前缀长度 ≤ 320**」，而 App 的前缀长度**随段内累积文本增长** ⇒ **段越长、文本越多 ⇒ 越容易越界** ⇒ **这不是 App 的 bug，是 handoff 的前提写漏了一项**。

### 3.4 建议动作（**ASR 侧只提方案，不代改 `live_caption/`**）
1. 🔴 **改 handoff §三之二/§四 的前提表述**（本模块职责，下一轮可做）：把「正常素材不会触发」改成「**ASR 参照口径（流式前缀几乎为空）下 3 素材计数 0；App 生产路径在 NPU 档、段长≈20.5 s、段内文本 ≥ ~36 token 时会触发（实测 ZH 3 次）**」⇒ 并把余量约束写成「**段长上限 ＋ 段内累积前缀 ≤ pml − 18**」。
2. 🟡 **给 App 的建议（需 App 线程决定，本模块不代做）**：NPU 档要么 **① 把 `MAX_SEG_SEC` 从 20 s 降到 ≈19 s**（⇒ `skeleton ≤ 275` ⇒ `allowed_prefix ≥ 45` ⇒ 覆盖实测最长前缀 43），要么 **② 在 NPU 档对前缀做「超预算就丢弃段尾前缀」而非「左截断」**（避免丢句首），要么 **③ 上调 pml**（🔴 **但 320 是 NPUW 的 `NPUW_LLM_MAX_PROMPT_LEN`，改它会改变 §86 的全部 RTF 数字 ⇒ 必须重测**）。⇒ **建议 ①**：它不动 pml、不动 RTF 数字、不动 GPU 档。
3. 🟡 **待用户/reviewer 决定**：是否要把「**NPU 档在 20 s 长段会触发前缀截断（实测 3 次；本轮两侧转写一致，未见丢字，但机制上会丢句首）**」写进客户 README 的已知问题（App §221 §4 已重写 README，**目前没有这一条**）。

---

## 四、🔴 顺带订正：App §221 §2 给的「差异原因」有 1 条不成立（只读实测）

App 在 `app121_asr_app_3mat_*.json` 的 `ref_diff_explanation` 里列了 3 条原因。本轮逐条核：

| App 列的原因 | 本轮实测 | 判定 |
|---|---|---|
| ①「**切段器不同**（App 用自己的 `Segmenter`，MIN 6 / MAX 20 / 静音规则；参照用 ASR 的 `Segmenter`）⇒ **段边界与段数本就不一致**」 | 🟢 **段数完全一致**（93/93、65/65、66/66）⇒ 段数「本就不一致」**不成立**；🔴 进一步逐段比对**边界**：**只有最后一段不同**（App 末段 start=600.0/ref start=597.12；EN 448.34/444.16；ZH 467.4/464.64）⇒ **其余 92/64/65 段边界逐条相同** ⇒ 「段边界不一致」**不成立**（只差末段起点，是末尾残留的归属差）。 | 🔴 **不成立** |
| ②「**解码入口不同**（流式块 `max_new=32`、段尾 `_finalize` `max_new=64`）」 | 🟢 属实（`live_caption_app.py` L2200 `generate_with_prefix(st, st.audio_accum, prefix, 64)`；`streaming_asr.py` 流式块 budget 上界 32）。 | ✅ 成立 |
| ③「**语种 prompt 注入路径不同**（App 走 `force_language` → `_right_ids()`；参照走 `set_lang_prompt()` 直接改 `prompt_raw`）」 | 🟢 属实（App 后端 `build_inputs_embeds(..., force_language)` 里 `_right_ids(force_language)`；ASR 参照 `asr165_bench.py` L135-144 改 `runner.prompt_raw`）。 | ✅ 成立 |

⇒ 🟡 **结论**：App 侧「不要求硬凑一致」的**处置结论是对的**，但它给的**归因 ① 是错的**（段边界其实基本一致）。真正的差异来源（据 §三）是 **③（语种注入 ⇒ token 序列不同 ⇒ 贪心解码分叉）＋ ②（分段解码入口不同）**，而 **NPU 档多出的 3 次前缀截断**（§三）是**第四个因素**（GPU 档 0 次）。🔴 **但要注意**：本轮实测 **4 个长段的 NPU/GPU 转写逐字节相同**，且 **4 处差异全在短段** ⇒ ⇒ **当前 NPU↔GPU 的转写差异不能归因于前缀截断**（那是浮点分叉）；**截断的影响本轮未被观测到**。

---

## 五、本轮做了什么 / 没做什么

- 🟢 **做了（全部只读）**：租约 acquire/beat/release；读 `CORRECTIONS_ASR.md`（md5/size/mtime/编号）；列 QQ 收件箱 + 按主题搜 `ASR-`；读 App §221 的提交 `88b9ea8`（48 文件）与 15 份 `results/app/*.json`；用 **权威闸门** `pack_v13.check_acceptance_binding` 只读复跑 v1.1.1 与 v1.1 目录；用 **`pack_v13._acc_module_fingerprints` 口径**从**新 zip 内**重算 31 个模块指纹；用 `zipfile` 核 zip entries/解压字节/ACCEPTED；用包内 **tokenizer 只做 tokenize**（无推理、无 IR、无 NPU）测 4 个 20.48 s ZH 段的 token 数；用 `bk_mel.total_aftercnn_len` 复算音频 token 与 `allowed_prefix`；用 `difflib` 量 NPU↔GPU 字符相似度；逐段比对 App 与参照的段边界。
- 🔴 **没做**：未跑任何推理/计时（**未取 MACHINE_LOCK**）；未改 `live_caption/`、未改交付包、**未打包**（用户级记忆：**不通知不主动打包**）；未改纠偏文件；未改旧章节（§90 已逐字归档）；**未代做 App 线程的作业**；**未改 handoff 的前提表述**（§3.4 建议 1 留待下一轮，属本模块文档职责）。
- **产物**：本文件 `status/asr/notes/asr_s91.md`（**LF**）＋ `status/asr/STATUS_ASR.md` §91。

## 五之二、🔴 为守住 ASR-036（≤40 000 B）所做的「最近更新」滚动窗口收缩（**不丢结论**）

🔴 §91 首版载荷写出 **50 699 B**、压缩版 **47 191 B**、再压缩 **41 281 B** ⇒ 均超 **ASR-036 的 40 000 B** ⇒ **每次都先 `cp STATUS_ASR.md.bak_asr091 STATUS_ASR.md` 恢复基线再重写**（未在超限状态上叠加）。
🔴 处置：**①** **明细全部移到本 note**（STATUS 正文只留结论 ＋ 关键原始字段 ＋ 产物路径，同 §83–§90 既有惯例）；**②** **「最近更新」是滚动窗口（≤15 行）⇒ 移出最旧的 5 条**（ASR-055 / ASR-060 / ASR-061 / ASR-062 / ASR-063，均为 11-11～11-19 的）⇒ 🟢 **这些章节的全文与数字仍在归档里**（`status/archive/STATUS_ASR_sec8{3,4,5,6,7}_upto_*.md`）＋ `notes/asr_s8*.md` ⇒ **不丢任何结论**；**③** 🔴 **§90 已逐字归档**（`status/archive/STATUS_ASR_sec90_upto_20261123.md`，3 622 B）⇒ 正文只留一行摘要。
🟢 **最终** `STATUS_ASR.md` = **39 420 B / 134 行**（CRLF 完整、裸 LF 0、末尾 CRLF、`自指大小` 自洽、唯一 `### §91`）⇒ ✅ 合 ASR-036（≤40 000 B）与 ASR-038（≤160 行）。
🟢 **写入器**：`_asr070_write_status.py`（v16，从 v15 派生：归档目标改为 **§90**）＋ 载荷 `_asr070_payload_final.py` / `_asr070_payload.json`（均在**仓库外** `qwen3asr_06b/scripts/_asr065/`，按纪律未入库）。
🟢 **归档副作用（已核）**：本轮新增 `status/archive/STATUS_ASR_sec90_upto_20261123.md`（**3 622 B**，§90 逐字）⇒ **归档目录新增 1 个文件**。

## 六、留给下一轮的动作清单

1. 🔴 **改 handoff `qwen3asr_06b/dev/asr065_handoff.md` 的 §三之二 / §四 前提表述**（ASR 模块自己的文档，本模块职责）：「正常素材不会触发」⇒ 按 §3.2/§3.3 改写；余量约束补上「段内累积前缀」。
2. 🟡 **给 App 线程的 NPU 截断问题**（§3.4 建议 2/3）⇒ 走**邮件**通道给 reviewer（§3.4 建议 1 落地后一并报）。
3. 🟡 **待用户/reviewer 决定**：README 是否加「NPU 档会截断前缀 ⇒ 句首可能丢字」。
4. ⚠️ **交付纪律**：发客户前确认发的是 **`v1.1.1.zip`**（自证通过），**不是** `v1.1.zip`（`CONTENT_MISMATCH`）。
