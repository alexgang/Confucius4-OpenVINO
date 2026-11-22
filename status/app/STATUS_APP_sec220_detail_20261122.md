# APP-120 §220 详情（companion）

> 本文件是 `status/app/STATUS_APP.md` 的 `## §220` 的**正文**；活文档只留标题行 + 摘要 + 指针行。
> 生成脚本：`live_caption/_app120_sec220_body.py`（**数字全部从证据 json 读出**）。

生成时间：2026-11-22 16:54:00

## §0 ASR-065/066 优化是否已接入（逐项）

| # | reviewer 的问法 | 结论 | 证据 |
|---|---|---|---|
| ① | NPUW `MAX_PROMPT_LEN=320`；超长前缀按 token **左截断**（计数 `prefix_truncations`、不抛错、不回退 512）**默认开** | ✅ |
| ② | `asr_enc_tiers` / `--asr-enc-tiers` **默认 off**；分档失败自动退回 2400 单档（`build_tiers_with_fallback`） | 🟡 见下 |
| ③ | `max_new ≤ 64`（KV=320+64）；段长 ≤ `MAX_SEG_SEC=20 s`；`base_len > pml` 显式报错 | ✅ |
| ④ | 包内 python 跑 §86 三素材（SPE/EN/ZH），md5 = `cd67417e`/`ed3f52aa`/`d93062a6`；报 NPU 与 GPU.0 的 RTF | 🟡 NPU 全对；GPU.0 不对（已定位根因） |

### ① 320 + 前缀左截断（**默认开**）

* `live_caption/asr06b_stateful_backend.py:75-76` —— `NPUW_PROPS = {… 'NPUW_LLM_MAX_PROMPT_LEN': '320', 'NPUW_LLM_MIN_RESPONSE_LEN': '64'}`
* `live_caption/asr06b_stateful_backend.py:278-280` —— **实例属性** `self._max_prompt_tok`：NPU 档 = 320，GPU 档 = 512（GPU 不走 NPUW ⇒ 仍用 IR 硬上界）
* `live_caption/asr06b_stateful_backend.py:485-507` —— **左截断**（`prefix_ids = prefix_ids[drop:]`，保留右端＝最近内容）＋ `self.probe['prefix_truncations']` 累加 ＋ 打印日志；**不抛错、不回退 512**
* `live_caption/asr06b_stateful_backend.py:489-493` —— **`base_len > pml` 显式报错**：`allowed_prefix < 0` ⇒ `raise ValueError('prompt 骨架 %d + 预留 %d > stateful 上界 %d（音频过长）')`（**比 handoff 的条件更严**：连 `reserve` 一起算）
* 默认开 = **不需要任何开关**：NPU 档构造期就把 320 写进 NPUW 属性。

### ② encoder 分档（**默认 off**）

* `live_caption/asr06b_stateful_backend.py:94-105` —— `_env_tiers_enabled()`：只读环境变量 `ASR_ENC_TIERS` ∈ {1,on,true,yes}；**不设置 ⇒ False ⇒ 默认 off**（行为与优化前逐字一致）
* `live_caption/live_caption_app.py` —— 新增 `--asr-enc-tiers on|off`（默认 `None`＝不动环境变量 ⇒ 仍是 off）

🔴 **本轮修掉的真缺陷（ASR-066 §2 的两处回退，原实现只有一处或零处）**：

* **原状**：构造期只把**编成功**的档塞进 `self.enc_tiers`，**编失败的档不留痕**；`encode_audio()` 里 `self.enc_tiers.get(_picked) or self.enc` 会**拿 2400 的模型去喂 400 帧的输入**（模型与输入形状不一致）⇒ 静默出错。
* **修法（handoff §5.1 的两处）**：
  ① 构建处 `build_tiers_with_fallback()`：任一档失败 ⇒ `tier_cms = {}`（**不残留半截分档**）＋ 记 `fallback_reason`；
  ② 调用处：`fallback_reason` 非空 ⇒ **强制 `use_tier=False`（`self.asr_enc_tiers = False`）**。
* 新增日志字段 `enc_tiers_fallback_reason`（null = 未回退）⇒ 写进 `probe`。
* **反证组（单测，全 PASS）**：全档失败 ⇒ `tier_cms={}` + 原因非空；**部分失败（800）⇒ 仍 `tier_cms={}`**（不残留半截）；全档成功 ⇒ `{400,800,1600}` + 原因 `None`。

### ③ `max_new ≤ 64` / 段长 20 s / `base_len > pml` 报错

* `live_caption/live_caption_app.py:2175` —— `max_new_tokens=32`；`:2224` —— `max_new_tokens=64` ⇒ **每次 `max_new ≤ 64`** （KV 容量 = 320 + 64 = 384 成立）
* `live_caption/live_caption_app.py:566` —— `MAX_SEG_SEC = 20.0` （段长前提成立）
* `base_len > pml` ⇒ 显式报错（见 ① 的行号）

### ④ 三素材 md5 ＋ 双设备 RTF（**包内 python**）

* 运行器 = **MiniMVP v1.1 包内 python**：``；**OV 2026.4.1-22982-e213a147257-releases/2026/4**（与 §86 参照同版本 ⇒ handoff §七「口径警告」要求的 2.4.1）；python 3.12.10
* 模型 IR **取自包内** `models/asr06b-encoder-fp16` / `models/asr06b-decoder-int8`；embed 表 **取自包内** `models/embed_tokens_06b_f16.npy`（与 kit 的 `embed_tokens.npy` **逐字节相同**，SHA256 `e8d4448c…`）
* 流程 = ASR-065 的同一套 decode（`bk_run.run_stream` ＋ `Asr065Runner`，**pml=320 / mrl=64 / use_tier=False**）

| 设备 | pml | 素材 | transcript md5 | 与 §86 参照 | 逐字节相同 | RTF |
|---|---|---|---|---|---|---|
| NPU | 320 | spe | `cd67417e64` | ✅ 一致 | 是 | **0.2754** |
| NPU | 320 | en | `ed3f52aaf1` | ✅ 一致 | 是 | **0.2483** |
| NPU | 320 | zh | `d93062a686` | ✅ 一致 | 是 | **0.2416** |
| GPU.0 | 320 | spe | `e9f783ab39` | ❌ 不同 | 否 | **0.2126** |
| GPU.0 | 320 | en | `f8384c408f` | ❌ 不同 | 否 | **0.1829** |
| GPU.0 | 320 | zh | `812873dfd2` | ❌ 不同 | 否 | **0.1722** |
| GPU.0 | 512 | spe | `e9f783ab39` | ❌ 不同 | 否 | **0.2039** |
| GPU.0 | 512 | en | `f8384c408f` | ❌ 不同 | 否 | **0.1791** |
| GPU.0 | 512 | zh | `812873dfd2` | ❌ 不同 | 否 | **0.1685** |

🔴 **GPU.0 的 md5 与参照不同 ⇒ 已定位根因（不是 App 侧接入造成的）**：

* **对照臂**：GPU.0 **pml=512**（ASR-065 之前的基线）跑同一三素材 ⇒ **md5 与 GPU.0 pml=320 完全相同**
  * `spe` → `e9f783ab39`（pml=512）
  * `en` → `f8384c408f`（pml=512）
  * `zh` → `812873dfd2`（pml=512）
* ⇒ **降 pml（512→320）＋ 前缀左截断在两个设备上都**不改变**转写**；
  差异只来自 **NPU（NPUW，INT8 计算）↔ GPU.0（OV GPU，FP32 计算）的跨加速器数值差异**。
* ⇒ **§86 的参照 md5 是 NPU 口径**（ASR-065 bench `device=NPU`）；**App 侧接入（pml=320）在 NPU 上逐字节复现参照**，这正是 handoff §七「App 改完请回归对照」要的结论。
* 🔴 **诚实结论**：reviewer 写的「md5 必须 = …」在 **NPU 上成立**；**GPU.0 上不成立**（同一模型、同一 IR、同一 python/OV，仅换加速器 ⇒ 转写文本不同）。**未**用任何手段把 GPU.0 的数字凑成一致。

🔴🔴🔳 **本轮新增的决定性对照（把「不是 App 造成的」从推断升级为实证）**：

* 把 App 集成后的 GPU.0 三素材转写，与 **ASR 模块自己在 11-19（ASR-062 时代）跑的 GPU.0 臂**（`qwen3asr_06b/results/asr162/_smoke_gpu/`）**逐字节对比**：
  * `spe`：App 产出 `e9f783ab391b` vs ASR 模块 GPU.0 基准 `e9f783ab391b` ⇒ **逐字节相同**
  * `en`：App 产出 `f8384c408fe9` vs ASR 模块 GPU.0 基准 `f8384c408fe9` ⇒ **逐字节相同**
  * `zh`：App 产出 `812873dfd2e5` vs ASR 模块 GPU.0 基准 `812873dfd2e5` ⇒ **逐字节相同**
* ⇒ **3/3 逐字节相同** ⇒ App 侧接入（pml=320 ＋ 前缀左截断 ＋ `asr_enc_tiers` 默认 off ＋ 两处回退）**对 GPU.0 零回归**；GPU.0 与参照的差异**全部**来自 NPU(NPUW/INT8) ↔ GPU.0(OV GPU/FP32) 的跨加速器数值差异，**与本轮改动无关**。
* 证据：`results/app/app120_asr_gpu0_vs_asrmodule_baseline.json`

* 编译耗时（**不计入 RTF**）：NPU enc 19.98 s / dec 7.29 s；GPU.0 enc 1.41 s / dec 2.64 s
* 锁自检：NPU 臂 `timing_valid=True`；GPU.0 臂 `timing_valid=True`（锁全程未被抢）
* **§86 参照 RTF（pml 臂，NPU）**：SPE 0.2860 / 0.3039；EN 0.2619 / 0.2507；ZH 0.2418 / 0.2429 ⇒ 本轮 NPU 数字在同量级。

### §0 小结

**§0 四个问法全部已接入并逐项验证**；其中 ④ 的 md5 判定**在 NPU 上全数通过**（逐字节相同），**GPU.0 上因跨加速器数值差异不通过**（已用 pml=512 对照臂证明与 App 侧接入无关）。

## §1 MiniMVP v1.1 包内容（从 v2.5 全集按 minimvp profile 裁剪）

* 来源包：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5`（**只读**，未改一字）
* 新目录：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.1`（**新目录**，未改 rc11 / v2.5 / sp5）
* 保留 **10904 文件 / 6702048025 B（6.242 GiB）**；排除 **37885 文件 / 19346365557 B**；排除原因分布 `{'pycache': 3525, 'profile_exclude': 34344, 'blacklist_suffix': 2, 'compiled_blob_cache': 14}`
* 裁剪规则 = APP-118 的 `minimvp` profile（`live_caption/package_profiles.py`）＋ **本轮追加的排除项**：
  * `models/spk`
  * `models/tokenizer`
  * `ext/.runtime_deps`
  * `docs/CUDA_TTS.md`
  * `ACCEPTED.json`
* 体积构成（顶层，实测）：
  * `models`：84 文件 / 5926971291 B（5.520 GiB）
  * `python`：10638 文件 / 770581090 B（0.718 GiB）
  * `app`：40 文件 / 1927701 B（0.002 GiB）
  * `.runtime_deps`：82 文件 / 1283883 B（0.001 GiB）
  * `ext`：44 文件 / 882048 B（0.001 GiB）
  * `docs`：3 文件 / 210065 B（0.000 GiB）
  * `(根文件)`：10 文件 / 138516 B（0.000 GiB）
  * `tools`：1 文件 / 44696 B（0.000 GiB）
  * `results`：2 文件 / 8735 B（0.000 GiB）
* 证据：`results/app/app120_build_minimvp_v11.json`

### 逐条对照 reviewer 的 §1 清单

| # | 要求 | 落实方式 |
|---|---|---|
| ASR | 只带 Qwen3-ASR-0.6B stateful INT8（含 ASR-065/066 优化）；不带 R2T2 1.7B | 排除 `models/decoder-*` / `models/encoder-*` / `models/embed_tokens_f16.npy` / `models/tokenizer` |
| MT | 只带 Hy-MT2 INT8-CW | 排除 `models/mt/mt2-int4sym-cw-q` |
| TTS | 只带 OpenVINO 版；不带 cuda_env、不带 models/tts_cuda | 排除 `cuda_env` + `models/tts_cuda` ＋ `models/qwen3tts/*.blob`（已编译缓存，铁律「编译缓存绝不写包内」；rc11 也没有） |
| 音色 | 只有预设 A；预设 B 不进包；无克隆 | `voices/` 只有 `preset_A.wav`；`package_profile.json` `allow_clone_voice=false`；排除 `models/spk` |
| 语种 | 10 种 | `package_profile.json` `target_langs=10`（代码与 v2.5 同源） |
| 界面 | APP-116/117 改动全带 | `app/` 直接取 v2.5（v2.5 已含两轮改动） |
| 出厂默认 | ASR=GPU.0 / MT=GPU.0 / TTS=NPU；设备自由配置、无 NPU 互斥 | `app/device_config.py` 同 v2.5（代次 11）＋ `package_profile.json`=minimvp |
| EXT | 照 rc11 的口径；bridge_token/*.pid/*.log 一律不进包 | EXT 取自 v2.5（v0.4.18）；**排除 `ext/.runtime_deps`**（与包根 `.runtime_deps` 逐字节重复、bridge 不引用 ⇒ 与 rc11 的 ext 布局一致）；黑名单 `bridge_token*` / `*.pid` / `*.log` 全未进包 |
| README | 中/英，按实际文件生成；写清版本/默认设备/如何改设备/已知问题 | `live_caption/_app120_write_readme.py`（文件数/字节数/顶层清单/模型清单**全部实测**）；已知问题含 **Meteor Lake NPU 配音杂音 ⇒ 改 GPU.0** ＋ **首次启动 NPU 编译耗时** |

🔴 **本轮额外修正（MiniMVP 打包闸门 APP-105 §2）**：`Diagnose.bat` / `Start_LiveCaption.bat` 从 v2.5 继承的是**含中文注释**（非 ASCII）⇒ 按 rc11 的 MiniMVP 口径改成 **ASCII + CRLF**（3/3 `.bat` 全 PASS）。

## §2 验收（全部通过才打 zip）

### ① 包上自检（`--check`）

* 结果 **PASS**（9 项，0 失败）
  * [PASS] 退出码 0
  * [PASS] 提到 Intel 集显 / GPU.0
  * [PASS] 提到 NPU
  * [PASS] ASR 后端出现 stateful（0.6B stateful 后端）
  * [PASS] ASR 可用后端数 = 2（GPU.0 + NPU）
  * [PASS] MT INT4 标注「本包不附带该量化版本」
  * [PASS] MT 后端出现 INT8-CW / mt2
  * [PASS] TTS 后端出现（qwen3tts / TTS）
  * [PASS] **未**出现 CUDA 后端（MiniMVP 无 CUDA）
* 证据：`results/app/app120_accept_v11_selfcheck.json`

### ① 洁净度闸门 0 违规

* `live_caption/assert_pkg_clean.py <包目录>` ⇒ **`[PASS] … 交付洁净度闸门：0 违规`**
* 「不该有的东西」清单（扫 **10 904** 文件）：**0 命中** —— 无 CUDA、无 R2T2 模型、无 MT INT4、无 preset_B、无克隆音色、无 babelvox 示例音色、无 bridge_token/*.pid/*.log、无录音/同事音色。
* 证据：`results/app/app120_model_identity_v11.json`（D/E/G 项）

### ② 模型身份逐文件核对（config 维度 + 权重 SHA 对源目录）

* 结果 **PASS**（17 项检查，0 失败）
  * `models/asr06b-decoder-int8`：**2/2 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/asr06b-decoder-int8`）
  * `models/asr06b-encoder-fp16`：**2/2 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/asr06b-encoder-fp16`）
  * `models/asr06b-tokenizer`：**7/7 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/asr06b-tokenizer`）
  * `models/embed_tokens_06b_f16.npy`：**1/1 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/embed_tokens_06b_f16.npy`）
  * `models/mt/mt2-int8sym-cw-q`：**12/12 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\hy_bench\ov\mt2-int8sym-cw-q`）
  * `models/qwen3tts/int8`：**18/18 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/qwen3tts/int8`）
  * `models/qwen3tts/weights`：**37/37 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/qwen3tts/weights`）
  * `models/qwen3tts/tokenizer`：**4/4 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/qwen3tts/tokenizer`）
  * `models/qwen3tts/voices`：**1/1 逐文件 SHA 相同**（源 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_SpecialMVP_v1.0-sp5\models/qwen3tts/voices`）
  * `models/asr06b-decoder-int8` config 维度一致（1 字段）
  * `models/mt/mt2-int8sym-cw-q` config 维度一致（8 字段）
  * `models/qwen3tts/weights` config 维度一致（1 字段）
* 0.6B decoder bin SHA 前缀 = `0059531a`（reviewer 点名项）
* 证据：`results/app/app120_model_identity_v11.json`

### ③ 出厂默认 10 分钟固定片段整链

* 命令 = 产品同款调用路径（包内 python + 包内 app）：`--asr-device GPU.0 --mt-device GPU.0 --tts-device NPU --translate zh --tts on --tts-voice A`；音频 = `test_audio/clip_10min_0_600.wav`
* 判定 **PASS**（14 项，0 失败）
  * [PASS] 丢句数（任何原因）= 0 :: worker丢弃=0 + 溢出丢弃=0 + worker失败丢弃=0
  * [PASS] 译文句数 == 进 TTS 句数 + 丢弃总数（无其它丢失路径） :: 164（译文）== 164（进 TTS）+ 0（丢弃）
  * [PASS] 就绪前排队的句子**全部补发**（一句不丢） :: 9（就绪前排队）== 9（已补发）
  * [PASS] 倍率 max ≤ 1.70（APP-114 §1） :: max=1.3917 p50=1.174 p95=1.2315
  * [PASS] 退出码 0 :: rc=0
  * [PASS] 产出齐备（wav + 逐句 jsonl + 积压曲线） :: _app591_app120_v11_default_run20261122-143100_tts_out.wav,_app591_app120_v11_default_run20261122-143100_tts_out.wav.tts.jsonl,_app591_app120_v11_default_run20261122-143100_tts_out.wav.backlog_curve.csv
  * [PASS] 逐句 jsonl **无重复 id**（未混入上一轮的行） :: 重复 id 数=0（[]）
  * [PASS] TTS 就绪时刻已记录 :: TTS就绪=27.4 s（相对进程启动；收尾时进程已运行 637.8 s）
  * [PASS] 积压清空时刻（**报告项**：APP-114 §4「lag 数字只报告、不设判定门槛」） :: 积压清空=None s（口径 —；末句播放滞后 29.852 s；lag max=43.139 s）
  * [PASS] ASR/TTS 并行生效（并行=on） :: parallel=True（请求=on）
  * [PASS] preflight：被测包的语速上限=1.70 / 队列不按时间丢句 :: speed_constants={'LAG_DEADZONE_S': 3.0, 'SPEED_PER_LAG_S': 0.025, 'SPEED_MIN': 1.0, 'SPEED_MAX': 1.7, 'LAG_HYSTERESIS_S': 2.0, 'MAX_STEP_CHANGE': 0.1, 'ZH_SPEED_MIN': 1.1, 'ZH_SPEED_MAX': 1.7} queue_overflow_s=None
  * [PASS] 队列行为探针（§2.1）：300 s 过期仍不丢句；worker 失败才清空 :: 300s后保留=5 丢弃=0；worker失败清空=5 计数=5
  * [PASS] 放锁时锁内容是否还是本作业（**报告项**：APP-115 §3.2） :: 放锁时锁内容='app 352 2026-11-22 14:31:19 app120-v11-default' ⇒ 仍是本作业(PID 352)=**True**；运行期间锁看门狗：采样 64 次 / 内容变动 1 次 / **非本作业的内容变动 0 次**
  * [PASS] synth_rtf 中位 / P90（**报告项**：APP-115 §3.2；判定线 P90≤0.75） :: synth_rtf 中位=0.8518 P90=0.9412 max=1.1935；RTF>1 的句数=8 / 共 164 句

**关键数字（与 v2.5 默认臂 / rc11 同口径对比）**：

| 指标 | MiniMVP v1.1 | v2.5 默认臂（APP-119 §3） | rc11（APP-107 验收） |
|---|---|---|---|
| 判定 | **PASS 14/14** | PASS 14/14 | PASS |
| 译文 / 进 TTS / 播完 / **丢弃** | 164 / 164 / 164 / **0** | 150 / 150 / 150 / **0** | 163 / 155 / 99 / **56** |
| MT 句数 | 164 | — | 163 |
| MT 延迟中位 / P95 | 665.6 / 1132.4 ms | — | 763.5 / 1354.0 ms |
| MT TTFT / tok/s | 182.1 ms / 24.8 | — | 228.1 ms / 23.9 |
| 语速 max | **1.3917** | 1.4368 | — |
| synth_rtf 中位 / P90 | **0.8518 / 0.9412** | 0.9656 / 1.0604 | — |
| 播放滞后 max（**积压峰值**） | **43.139 s** | 88.805 s | 未记 |
| 末句播放滞后（**收尾积压**） | **29.852 s** | 69.635 s | 未记 |
| TTS 合成侧积压 max | **54.90 s** | 99.11 s | 未记 |
| 首字延迟（TTS 首包） | **0.39 s** | 0.40 s | 未记 |
| 就绪前排队 / 已补发 | 9 / 9 | 0 / 0 | — |

🔴 **诚实标注**：`synth_rtf` P90 = **0.9412 > 0.75** 判定线（v2.5 默认臂是 1.0604，更差）⇒ 按 **APP-115** 口径**计时类结论不算干净**（⇒ 不用于宣称速度优势）；**计数类结论成立**（164 句进 TTS / 164 句播完 / 丢弃 0；锁看门狗 64 次采样 / 非本作业变动 0 次）。

🔴 **句数是 164 而不是 reviewer 说的 150**：MiniMVP 用的是 **Qwen3-ASR-0.6B stateful**，断句与完整版的 R2T2 1.7B 不同 ⇒ 同一段 10 分钟音频切出 164 句（rc11 同音频 163 句、v2.5 150 句）。**「一句不丢」的判据是「译文句数 == 进 TTS 句数 + 丢弃总数」且丢弃 = 0** ⇒ 164 == 164 + 0 ⇒ **PASS**。

* 证据：`results/app/app591_acceptance_app120_v11_default_run.json`
* 编排产物：`results/app/app120_accept_v11_chain.json`

### ④ 10 语种各 1 句冒烟（字幕 + 配音）

* 🔴 **上一会话（14:47）那一轮的「B 组 0/10 FAIL」是**假 FAIL**，本轮已定位并重跑：**判据自身缺陷＝用了错的解释器**。
  * 现象：`TTSEngineError("未安装 babelvox：No module named 'babelvox'…")` ⇒ B 组 0/10（配音一条不出声）。
  * 根因：`babelvox` **只随客户包分发**（`Confucius4_LiveCaption_MiniMVP_v1.1/python/Lib/site-packages/babelvox`），**仓库 `.venv` 里没有** ⇒ 上一会话用 `.venv\Scripts\python.exe` 跑这个 harness ⇒ TTS 引擎**根本没建起来** ⇒ B 组必然 0/10。**不是产品缺陷**（包内 python 里有 babelvox ⇒ 客户侧不受影响）。
  * 修法：**用包内 python 跑 harness**（`live_caption/_app120_accept_v11.py` 的 `step_lang10` 本来就是 `PKG_PY`，上一会话是手工用 venv 跑的）。
* ✅ **本轮重跑（包内 python，PID 31588，持机器锁）⇒ 10 PASS / 0 FAIL**：
  * 结论 **10 PASS / 0 FAIL**；设备 ASR=GPU.0 / MT=GPU.0 / TTS=NPU
  * [PASS] A1 目标语言 = 10 种 — 10 种 ['zh', 'en', 'ja', 'ko', 'de', 'fr', 'es', 'pt', 'it', 'ru']
  * [PASS] A2 每种语言的 MT 目标名可解析 — []
  * [PASS] A3 每种语言的 TTS language id 可解析 — []
  * [PASS] A4 每种语言的界面标签存在 — []
  * [PASS] A5 三张表的目标语言名一致（MT/TTS/界面） — []
  * [PASS] B2 10 语种**没有**触发 language-agnostic 回落（映射正确） — 引擎未报任何 not recognized
  * [PASS] B3 10 语种映射后的 id 都在引擎支持列表内 — []
  * [PASS] B 10 语种配音全部出声 — 10/10
  * [PASS] C 10 语种字幕（MT）全部出译文 — 10/10
  * [PASS] D 反证组：未知语种必须被**产品两道闸**拦住（证明 B 组可判失败） — {"strict_raised": true, "strict_msg": "未知目标语言 'xx'；支持：Chinese, English, French, German, Italian, Japanese, Korean, Portu
  * 证据：`results/app/app120_accept_v11_lang10_evidence.json`（7063 B）
* ⚠️ **上一会话那一轮的「假 FAIL」证据已单独留档**（不删不改）：`results/app/app120_lang10_evidence_harnessbug_venvpython_20261122-1447.json`（5 139 B）＋ `results/app/app120_accept_v11_lang10.json`（rc=1）。

### ⑤ 设备切换冒烟

* 结果 **PASS**（6 项，0 失败）
  * [PASS]（allnpu）全 NPU 退出码 0（启动不崩）
  * [PASS]（allnpu）全 NPU：日志出现 NPU 设备（未静默换设备）
  * [PASS]（allnpu）全 NPU：未静默降级成 CUDA
  * [PASS]（tts_gpu0）TTS=GPU.0：日志出现 GPU.0 的语音输出设备
  * [PASS]（tts_gpu0）TTS=GPU.0：未出现 CUDA
  * [PASS]（headphone）耳机输出设备 {0.0.0.00000000}.{05fde43c-4ab6-4b3f-bf39-397ffc978640} 生效（日志含该 id 或「输出设备」）
* 证据：`results/app/app120_accept_v11_devswitch.json`

### ⑥ 全新用户目录启动 ＋ rc11 旧配置启动（迁移）

* 结果 **PASS**（3 项，0 失败）
  * [PASS]（fresh）全新用户目录：出厂默认 ASR=GPU.0 / MT=GPU.0 / TTS=NPU
  * [PASS]（rc11_old）rc11 旧配置：当代同形态 ⇒ 信任（不迁移）且设备不变
  * [PASS]（full_old）完整版残留旧配置：形态不同 ⇒ 三个键全忽略 ⇒ 仍用出厂默认
* 证据：`results/app/app120_accept_v11_freshdir.json`

### ⑦ 签 ACCEPTED.json（version=1.1）

* 生产模块 33 个；聚合指纹 `9c732366eeaaf091f37ad95762787b06cf5ca3a668053312b5a6bbdb058017d6`
  * [PASS] accepted=True
  * [PASS] version=1.1
  * [PASS] pkg_dir 目录名一致
  * [PASS] code_fingerprints 非空
  * [PASS] 逐条指纹一致
  * [PASS] 集合一致（无缺/多）
  * [PASS] 聚合指纹一致
* 出包闸门⑤ `check_acceptance_binding`：**True（OK）**
* 证据：`results/app/app120_sign_accepted_v11_evidence.json`

### ⑧ zip

* zip = `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.1.zip`
* **5212356737 B（4.854 GiB）**；进包 10881 文件 / 原始 6701773512 B；压缩率 **77.8%**；耗时 349.5 s
* 🔴 **zip 的 SHA 未独立对账**（reviewer 明示「zip 的 SHA 不用独立对账」）
* 证据：`results/app/app120_zip_v11.json`

## 纪律与边界

* **未改** rc11 / v2.5 / sp5 任何既有文件（除 v2.5 的 `app/` 两个文件按 APP-120「v2.5 全集同步更新」定点同步：`asr06b_stateful_backend.py`、`live_caption_app.py`）。
* **未改** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。
* **未通知用户**（APP-120 明令「验收通过后由 reviewer 复核，再通知用户；不要自己通知用户」）。
* **未连 B 机**（APP-109 ④ 仍然有效）。

### 🔴 本轮如实登记的**两处事故**（都已修好并留证）

**① 上一会话的 harness 把 v2.5（§217）的 lang10 证据覆盖了。**

* 现象：`live_caption/diag_app118_lang10.py` 的输出路径**写死**为 `results/app/app118_lang10_evidence.json` ⇒ 上一会话拿它跑 MiniMVP v1.1 ⇒ **把 v2.5 那份（8 988 B / SHA `7ce6fa9d…`）覆盖成 v1.1 的**（5 139 B / 7 PASS·1 FAIL）。
* 处置：① **加 `--out` 选项**（默认仍写原路径，旧调用方行为不变）⇒ 以后不同包的证据写不同文件；② **v2.5 那份已重跑恢复**（用 v2.5 包内 python 跑 v2.5 ⇒ **10 PASS / 0 FAIL**，8 989 B / SHA `29ac00d5…`）⇒ **内容等价**（结论一致），但**字节级 SHA 与 §217 companion 里引用的 `7ce6fa9d…` 不同**（`at` 时间戳与 10 语种逐句时长都会变）⇒ **如实记录，不声称「SHA 零改动」**。
* 旧证据（假 FAIL 那份）**未删未改**，单独留档：`results/app/app120_lang10_evidence_harnessbug_venvpython_20261122-1447.json`。

**② 本轮我自己写的打包脚本漏了 `lock.acquire()` ⇒ 第一次打包是「裸奔」的。**

* 现象：`machine_lock_app.LockHeld(...)` 的**构造函数不会取锁**（只有 `__enter__` 才调 `acquire()`）⇒ 我第一次写的版本只 `new` 不 `acquire` ⇒ `shared/MACHINE_LOCK` 全程不存在 ⇒ **未持锁就压 6.2 GiB**。
* 处置：**当场中止**（已写出 657 MB 的 `.tmp` 已删）⇒ 补上显式 `if not lk.acquire(): return 1` ⇒ 重跑（16:37 起）**全程持锁**（锁内容 `app-pack PID 31952`，16:37:18 取、结束后放）。
* ⚠️ **zip 的 `finally` 里放锁**（含校验失败 / 异常路径）⇒ 不会把锁卡死。

