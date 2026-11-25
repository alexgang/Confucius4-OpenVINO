# STATUS_APP §238 — 执行 **APP-137 §1–§3** ＋ **APP-134 a** ＋ **APP-135 §1–§3**（`last_ack` = APP-136 → **APP-137**）

> 本节正文全文。**§237 及以前各节一字未改**（只在文末追加本节）。
> 头部 `last_ack` 由 `APP-136` 更新为 `APP-137`；「更新时间」＝ `Get-Date` 实测值。
> 生成时间：2026-11-25（Asia/Shanghai）。

## §0 本轮性质与顺序

- 本轮**接续 §237**（APP-136 已闭环）⇒ 按 reviewer **APP-137 明文规定的顺序**执行：
  **APP-136 → APP-137 → APP-134 a–c → APP-135**。
- 本节覆盖：**APP-137 §1–§3（前半）**、**APP-134 a**、**APP-135 §1–§3（代码侧）**。
  🔴 **未完成**：APP-137 §3 的 A 上三轮实测＋缺模型降级、APP-134 b/c、APP-135 §4–§5。
- 🟡 **本轮中途用户要求暂停**（14:13「要跑 live demo」）⇒ 已停作业、已释放 `MACHINE_LOCK`、
  保留 App 租约；**15:05 demo 结束后**已重新拿租约（token `1c76617d`）并续跑。
  暂停事件已落 `shared/bgkeep/e2e_app134a/_lock_events.jsonl` ＋ 当日日志。

## §1 APP-134 a —— **e2e 改成「排空到 n_pending=0」并重跑两臂**

### 1.1 🔴 本轮先修掉一个**真缺陷**（否则 10 分钟臂全丢）

| 项 | 内容 |
|---|---|
| 症状 | 第一次跑 10 分钟臂 ⇒ `rc=1`，`e2e_stdout.txt` 报 `ConnectionClosedError: sent 1011 (internal error) keepalive ping timeout` |
| 根因 | 桥接是**单线程 asyncio** ⇒ NPU 合成一段要 **10–16 s** ⇒ 事件循环在这期间**不转** ⇒ 客户端默认 `ping_interval=20 / ping_timeout=20` ⇒ 桥接来不及回 pong ⇒ **客户端主动发 1011** ⇒ 排空阶段拿不到 stats |
| 证据 | `shared/bgkeep/e2e_app134a/bgkeep_on_npu/bridge.log`（那一轮）**桥接本身完全健康**（日志持续到 `t_start=343`）⇒ **不是桥接挂了，是客户端自己把连接掐了** |
| 修法 | `_app137_e2e_drain.py`：`websockets.connect(..., **ping_interval=None**)`（**关掉协议层 ping**）＋ 排空循环**捕获断连**并如实记 `drain.disconnected`（不再一断就崩、丢已采数据） |
| 复核 | 修完**先跑 60 s 冒烟**：`rc=0`／`drained_to_zero=true`／`synth_rtf=1.046`／`cross_check_ok=true` ⇒ 再上正式臂 |

> 🟢 本轮还把 e2e 驱动器从 **PowerShell 改写成 Python**
> （本机 `Path`/`PATH`/`path` **三个键并存** ⇒ .NET `Process.Start` 组装环境字典时撞
> 「字典关键字重复」⇒ `Start-Process` 直接抛异常；Python 的 `os.environ` 在 nt 上
> **大小写不敏感**⇒ 天然去重）。

### 1.2 两臂结果（**这是 reviewer 要的数据**）

| 指标 | **bgkeep_on · TTS=NPU** | **bgkeep_on · AUTO**（＝ `Start_Bridge` 实际配置） |
|---|---|---|
| dubs | 123 | 123 |
| **媒体结束时** `n_submitted` / `n_emitted` / **`n_pending`** | 121 / 72 / **49** | 121 / 120 / **1** |
| **排空后** `n_submitted` / `n_emitted` / `n_pending` | 123 / 123 / **0** | 123 / 123 / **0** |
| `drained_to_zero` | **True** | **True** |
| **排空耗时** | **292.77 s** | **4.01 s** |
| `dub_late` max / p90 / p50（秒） | **530.835 / 464.442 / 179.707** | **2.329 / −1.147 / −6.152** |
| `last_segment_lag`（秒） | **279.1193** | **0.0** |
| 滞后斜率 / r² | **−0.534037 / 0.943061** | −0.001543 / 0.007121 |
| **`synth_rtf`**（EXT `RTF_out`，自算值与 EXT 值**交叉核对一致**） | **1.2792**（cross_check=true，n=123） | **0.5907**（cross_check=true，n=123） |
| `speech_over_src` / `tts_over_src` | 1.1472 / 1.4675 | 1.1784 / 0.6961 |
| `bg_late_blocks` | 0 | 0 |
| 峰值内存（`proc_mem_mb`） | 3937.4 MB | 7442.2 MB |
| `npu_pct` / `igpu_pct` | **76.4** / 7.4 | 0.0 / 0.0 |
| **实际设备**（从 `bridge.err` 解析） | ASR **GPU.0** / MT **GPU.0** / TTS **NPU**（`cp_decode` 自检 0.105 s、`cp_prefill` 0.169 s、NaN 守卫 2 个、窗口 `chunk=8 ctx=25 window=33 buckets=[38]`、`MultiDecoderBabelVox`） | ASR **GPU.0** / MT **NPU** / TTS **CUDA 边车**（`NVIDIA GeForce RTX 5050 Laptop GPU`，torch 2.11.0+cu128，**端到端启动 45.3 s**） |
| `dup_dropped` / `n_dropped` | 0 / 0 | 0 / 0 |
| `bg_state` / `sep_device` | ok / GPU.0 | ok / GPU.0 |

**锁事件**（`shared/bgkeep/e2e_app134a/_lock_events.jsonl`）：
`lock_acquired` 15:06:53（waited 0 s）⇒ `arm_done bgkeep_on_npu rc=0 elapsed=953 lock_lost=0`
⇒ `arm_done bgkeep_on_auto rc=0 elapsed=677 lock_lost=0` ⇒ `lock_released` 15:34:04。
🔴 **`lock_lost` 事件数 = 0**（本轮全程一次持锁到底）。

**原始产物**（文件数/字节/SHA256/mtime）：
| 文件 | 字节 | SHA256（前 32） | mtime |
|---|---|---|---|
| `shared/bgkeep/e2e_app134a/bgkeep_on_npu/bgkeep_e2e.json` | 73 464 | `8e878443b30f5377febc4eb787ebbf29` | 2026-11-25 15:22:45 |
| `shared/bgkeep/e2e_app134a/bgkeep_on_auto/bgkeep_e2e.json` | 58 467 | `c94352cc85fc1e3a0c588d265202969b` | 2026-11-25 15:34:02 |
| 汇总 | — | `results/app/app134a_summary.json` | — |

### 1.3 🔴 **口径更正**（reviewer APP-134 问题①）

reviewer 原话：
> 「丢句 0」「收尾积压 0.0」**不成立**。… 会话在媒体结束时就关了，没有排空，
> 所以有 22%/26%/33% 的句子到最后也没配上音。

**本轮实测确认（且给出更准的数字）**：

| 臂 | 媒体结束时未配音（`n_pending`） | 占总句数 | 排空耗时 | 排空后 |
|---|---|---|---|---|
| **TTS=NPU** | **49** | **40.5 %** | **292.77 s** | 0（全部配上） |
| **AUTO** | **1** | **0.8 %** | **4.01 s** | 0 |

- ✅ **「丢句 0」不成立**（NPU 臂 40.5 % 的句子在媒体结束那一刻**还没有配音**）。
- ✅ **「收尾积压 0.0」不成立**：NPU 臂**收尾积压 = 292.77 s**（排空耗时），
  末句滞后 **279.12 s**。
- 🟢 **但要如实说清另一半**：排空后 `n_pending` **确实归 0** ⇒
  **最终每一句都配上了音**（`dubs=123`／`n_emitted=123`），
  `dub_dropped=0` ⇒ **没有主动丢弃**。
  ⇒ 正确表述是：**「不是丢句，是**迟到**；迟到量在 NPU 臂高达 292.77 s」**。
- 🔴 **滞后线性增长不回落**：NPU 臂 `slope=−0.534 s/s`、`r²=0.943`
  （与 reviewer 读旧三臂得到的 r² 0.96–0.98 **同一现象**）⇒
  旧字段 `lag_curve end_sec=0` **不代表收尾积压**（reviewer 判断**正确**）。

### 1.4 🔴 **APP-134 问题②（测的配置不是包里实际会跑的配置）—— 已实证**

reviewer 原话：
> `Start_Bridge.bat` 不设设备，`ext/bridge/config.py` 里 `EXT_TTS_DEVICE`/`EXT_MT_DEVICE`
> 默认是 AUTO；… 这一档在 v2.6 包上一次都没测过。

**本轮 AUTO 臂实测（`bridge.err` 原文）**：
```
[ext-engine] MT 设备 AUTO => NPU（TTS 走 CUDA 边车）
[ext-engine] MT 就绪（Hy-MT2 INT8 @ NPU，3.9s）
[ext-engine] [tts_cuda] 就绪：NVIDIA GeForce RTX 5050 Laptop GPU / torch 2.11.0+cu128 / 加载 43.1s / 预热 1.7s
[ext-engine] [tts_cuda] 端到端启动耗时 45.3 s
[ext-engine] TTS 就绪（Qwen3-TTS @ CUDA 边车 faster-qwen3-tts，45.3s，GPU=NVIDIA GeForce RTX 5050 Laptop GPU）
```

⇒ **AUTO 档 = ASR GPU.0 / MT **NPU** / TTS **CUDA 边车**（RTX 5050）**
⇒ **与 App 出厂默认（GPU.0/GPU.0/NPU）不是同一档** ⇒ reviewer 的批评**完全成立**。

### 1.5 🟢 给用户裁定「默认摆放」的数据（APP-136「默认设备」条）

- **TTS=NPU 档**：`synth_rtf=1.2792`（>1 ⇒ TTS 引擎自身来不及）⇒
  收尾积压 292.77 s、末句滞后 279.12 s、斜率 −0.534 s/s（**线性恶化**）。
- **AUTO（TTS=CUDA 边车）档**：`synth_rtf=0.5907`（<1 ⇒ 富余）⇒
  收尾积压 4.01 s、末句滞后 0.0 s、斜率 −0.0015 s/s（**基本持平**）。
- ⇒ **同一份 v2.6 包，同一段 10 分钟媒体，两档相差约 73 倍**。
- 🔴 **本轮只报数据，不替用户决定**（reviewer APP-136「先测再定」，用户裁定优先）。
- 🟡 **AUTO 档的代价**：TTS 走 CUDA 边车 ⇒ **需要 `cuda_env/`（本机有 NVIDIA 卡）**；
  在**没有独显**的机器上 AUTO 会退化 ⇒ **不能只按本机数据拍板**。

## §2 APP-137 §1–§3 —— MiniMVP v1.2（**dev 树 profile 改造 ＋ 候选目录**）

### 2.1 §1 dev 树改造（**只改 dev 树**，客户包一个字节没动）

| 文件 | 改动 |
|---|---|
| `live_caption/package_profile.py` | ① `allow_clone_voice()`：**去掉「minimvp ⇒ 硬编码 False」**，改成**读标记文件的 `allow_clone_voice`**（缺字段 ⇒ False，保守）；② **新增** `allow_bgkeep()`；③ **新增** `allow_tts_c13()`；④ `describe()` 加两个字段 |
| `live_caption/package_profiles.py` | minimvp 规则：**不再排除** `models/spk`（克隆链 IR）＋ `models/bgsep`（Demucs）；marker 加 `allow_clone_voice=True`／`allow_bgkeep=True`／`tts_c13=False`／`mt_model='mt2-int8sym-cw-q'`（**留好切 MT3 的开关**） |

🔴 **老 MiniMVP 包（v1.1.1）行为逐字不变**（它的 marker 里 `allow_clone_voice=false`、
**没有** `allow_bgkeep` ⇒ 读出来仍是 False）—— 由**行为级单测**承重：

`results/app/app137_profile_behavior.json` ⇒ **18/18 PASS**
（4 组 marker **真跑**：A 完整版／B 新 MiniMVP v1.2／C **老 MiniMVP v1.1.1**（承重）／D 坏标记
＋ **2 组反证组**：把「minimvp 硬编码 False」改回去 ⇒ 判据必须 FAIL（实测 FAIL，符合预期））。

### 2.2 §2 候选目录（**不打 zip、不签 ACCEPTED**）

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2.candidate\` |
| 来源 | **完整版 v2.6**（v1.1.1 当初是从 v2.5 裁的；v2.6 才带 EXT `b2a4978`＋`models/bgsep`＋APP-130 的 `tts_engine/tts_worker`） |
| 规模 | **10 891 文件 / 6 829 401 234 B（6.360 GiB）** |
| 排除 | 37 902 文件 / 19 327 119 261 B（`profile_exclude` 34 338／`pycache` 3 525／`media_file` 23／`compiled_blob_cache` 14／`bak_or_pyc` 2） |
| 证据 | `results/app/app137_build_minimvp_v12.json` |

### 2.3 §3 包内容核对（**离线只读**，22/22 PASS）

`results/app/app137_candidate_check.json`：

| 组 | 核对 | 结果 |
|---|---|---|
| **A 模型身份** | 6 个模型目录的**权重 SHA256 逐文件对源**（v2.6） | bgsep 2/2、spk/pyannote 4/4、spk/wespeaker 2/2、mt/mt2 12/12、qwen3tts/weights 37/37、tokenizer 4/4 **全部相同** |
| | `config.json` 维度（`hidden_size`/`num_hidden_layers`/`vocab_size`/`num_attention_heads`/`intermediate_size`） | 与源**逐项相等** |
| **B 克隆链** | `models/spk` 两个 IR ＋ `app/` 里 `clone_voice.py`／`clone_collector.py`／`speaker_tracker.py`／`speaker_voice.py`／`speaker_assets.py` | **齐全** |
| | **克隆音色目录** | **只有 `preset_A.wav`**（空目录铁律：首次使用现场采集） |
| **C 媒体文件** | 全包扫 `.wav/.ogg/.mp3/.mp4/.m4a/.flac/.aac/.wma` | **违规 0 个**（`preset_A.wav` 由白名单单独放行） |
| **D CUDA** | `cuda_env/`／`models/tts_cuda/`／CUDA DLL（`cudart`/`cublas`/`cufft`/`curand`/`cusparse`/`cusolver`/`nvrtc`/`nvinfer`/`cudnn`/`nccl`/…） | **全无** |
| **E profile 语义** | `profile=minimvp`、`allow_clone_voice=True`、`allow_bgkeep=True`、`tts_c13=False`、`allow_cuda=False`、`mt_model=mt2-int8sym-cw-q` | **全部符合** |
| **F 不签不打包** | 候选目录**无** `ACCEPTED.json`；**无** v1.2 的 zip | **符合** |

🟢 **候选目录在包内 python 里真跑一遍**（不是只读文件）：
`profile describe` ⇒ `{'profile':'minimvp','is_minimvp':True,'allow_cuda':False,
'allow_clone_voice':True,'allow_bgkeep':True,'allow_tts_c13':False,'target_langs':10}`
｜`DEFAULT_DEVICES` ⇒ **`{'asr':'GPU.0','mt':'GPU.0','tts':'NPU'}`**（**出厂默认不变**）
｜`current_profile()` ⇒ `'minimvp'`。

🔴 **同步纪律**：候选目录的 `app/package_profile.py` 是从 v2.6 裁出来的**旧版**
⇒ 用 `_app137_sync_to_candidate.py` **定点同步**（`difflib` 自动导出改写块 →
**原件上唯一命中** → 从后往前替换 → **写前真不变量** 7 项全 PASS ＋
**反证组**（篡改内容 ⇒ 内容级判据 FAIL）→ 写后复核 5/5 PASS）。
证据：`results/app/app137_sync_to_candidate.json`。

## §3 APP-135 §1–§3 —— dev 树 MT2 → MT3（**只改 dev 树、不出包**）

### 3.1 §1 模型目录切 MT3（**保留切回开关**）

- `live_caption/translator.py`：
  * `DEFAULT_MODEL` 回落链**优先 MT3**（`models/mt/mt3-int8sym-cw-q` → `models/mt3-…` → `_HY_ROOT/mt3-…`），
    **回退**到 MT2，再回退 INT4（老包仍能跑）；
  * **开关**：环境变量 **`LIVECAP_MT_VARIANT=mt2`** 切回 MT2（**默认 `mt3`**）；
    `LIVECAP_MT_MODEL`（显式指定目录）优先级更高、不变；
  * `MT_ENGINES` 的 **INT8-CW 两档**（GPU/NPU）目录名 ⇒ 随变体走；
    **INT4 两档仍指 MT2**（🔴 仓库里**没有** MT3 的 INT4 产物 ⇒ 写 MT3 会让该档**永远「缺模型」**）。
* 🟢 **EXT bridge 侧自动生效**：EXT 的 MT 默认路径走 `LIVECAP_MT_MODEL`（App 侧透传）
  ⇒ **一处改动两处生效**。（EXT 源码在 reviewer 的 `live_dub_ext` 仓库，**本轮未动**。）
* 证据：`results/app/app135_mt3_patch.json`（写前 14 项真不变量 + 写后 4 项，全 PASS）。

### 3.2 §2 🔴 **解码参数必须显式设** —— 本轮**实测出关键事实**

reviewer 说 MT3 的 `generation_config.json` 默认 `do_sample=true`／`temperature 0.7`／
`top_k 20`／`top_p 0.8`，App **不能吃**模型默认值。

🔴 **本轮用真 GenAI（包内 python）实测确认「确实会吃到」**：
`LLMPipeline.get_generation_config()` 在加载 MT3 后返回
`do_sample=true`／`temperature=0.699999988079071`／`top_k=20`／`top_p=0.800000011920929`
⇒ **只靠 `og.GenerationConfig()` 的裸默认（`do_sample=False`）是不够的**
（GenAI 会把模型自带值合进来）⇒ **必须逐项显式覆盖**。

⇒ `translator.py` 现在**逐项显式写死**：
`do_sample=False`（贪心）｜`temperature=1.0`｜`top_k=0`｜`top_p=1.0`｜
`repetition_penalty=1.05`｜`apply_chat_template=False`｜`max_new_tokens`（沿用原公式）。

### 3.3 §2 **单测断言实际生效的是贪心**（**真跑**，不是断言源码里有那行）

`live_caption/_app135_greedy_test.py`（用**包内 python** 跑，APP-120 血泪）⇒
`results/app/app135_greedy_test.json` ⇒ **ALL PASS**：

| 判据 | 实测 |
|---|---|
| `translate_ran`（**真跑一句** `translate('hello world','zh')`） | PASS |
| `do_sample_is_greedy` | **`do_sample=False`** |
| `temperature_neutral` | 1.0 |
| `top_k_neutral` | 0 |
| `top_p_neutral` | 1.0 |
| `repetition_penalty_1_05` | 1.05 |
| `apply_chat_template_false` | False |
| **`app_overrides_model_defaults`** | **四项全部与模型默认值不同**（`do_sample` True→False／`temperature` 0.7→1.0／`top_k` 20→0／`top_p` 0.8→1.0） |
| **`counterexample_must_fail`** | 反证组把 `do_sample=False` 改成 `True` ⇒ **单测 FAIL（符合预期）** ⇒ 判据**有鉴别力** |

🔴 **方法论**：单测用**桩 `openvino_genai`** 替换真模块 ⇒ 不需要装 GenAI 也能跑，
且能**记录 App 实际传给 `generate()` 的那个 GenerationConfig** ⇒
断言的是「**实际生效的值**」，不是「源码里写过那行」。

### 3.4 §3 提示词 —— **本条不改**

按 reviewer 明文「中文原文用中文模板还是英文模板，等 H-029 结论再定，**本条先不改**」
⇒ **提示词模板、`<answer>` 清洗逻辑一字未动**。

## §4 本轮新学的 3 个判据坑

1. 🔴 **「按行号反推」的还原式复核是恒真的**（它只是把 `[j1:j2]` 换回 `[i1:i2]`）
   ⇒ **鉴别力必须由「内容级逐字比对」承担** ⇒ 本轮把两者**分开记**
   （`content_matches` 承重；`note_positional_reverse_is_trivially_true` 如实标注）。
2. 🔴 **锚点重叠 ⇒ 顺序替换会互相干扰**：改写块带前置锚点后，先验唯一性必须在**原件**上做，
   替换必须**从后往前**做。
3. 🔴 **`preset_A.wav` 被两条规则同时命中**（「媒体文件铁律」与「克隆音色白名单」）
   ⇒ 白名单必须在媒体规则**之前**短路返回，否则内置音色会静默丢失。

## §5 未完成 / 待裁定（**如实登记**）

1. 🔴 **APP-137 §3 后半**：候选目录的 **A 上三轮实测**（保留背景音关／开／开+clone）
   ＋ **缺模型降级**（拿掉 `models\bgsep` 的临时副本）**未做** ⇒ 本轮只做了**离线包内容核对**。
2. 🔴 **APP-134 b**（NaN 守卫开 vs 关的两臂比 synth_rtf 中位/P90 与 max_lag）**未做**
   ⇒ 🔴 本轮**已备好影子包工具**（`live_caption/_app137_shadow_pkg.py`：
   `models/`/`python/`/`ext/` 等走 **Windows 目录联接 ⇒ 零拷贝**，`app/` 真拷贝 ⇒ **只 2 MB**；
   实测建/删正常，**源包零改动**）⇒ b/c 两臂的工具已就绪，**下一轮可直接跑**。
3. 🔴 **APP-134 c**（c13 开/关两轮 ＋ TTS=GPU.0 一轮 ＋ 6 段抽听片段
   `results/app/app123_listen/`）**未做**；且按 reviewer 口径 **ACCEPTED 里的 APP-123
   一律标「待验收」**（**本轮未改包** ⇒ 已签的 v2.6 `ACCEPTED.json` 未动）。
4. 🔴 **APP-135 §4**（打包清单/MANIFEST 的 MT 条目改 MT3：模型名／来源
   `ModelScope Tencent-Hunyuan/Hy-MT3-1.8B`／safetensors SHA／IR bin SHA；README 里写 MT2 的地方**列出来**）
   ＋ **§5**（持锁、只用 dev 树跑一轮 10 分钟 + `results/app/app135_mt3_samples.md`）**未做**。
5. 🔴 **活文档「当前有效结论」里那句「出厂默认（ASR+MT+TTS 全 GPU.0）的 10 分钟整链 FAIL
   ⇒ 等用户裁定默认摆放」已过时**（v2.6 的 `_DEFAULT_DEVICES_FULL` 是 GPU.0/GPU.0/NPU）
   ⇒ reviewer APP-134 问题⑦ 要求删掉或注明版本/测次
   ⇒ 🔴 **本轮未改**（STATUS 纪律：只**追加** §N，不回头改旧章节）⇒ **留待下一节**处理。
6. 🔴 **APP-136 的存量 13 个会议译文文件**是否一并抹掉 ⇒ 仍**待 reviewer 裁定**（§237 §5.1）。

## §6 纪律自查

| 纪律 | 结果 |
|---|---|
| `CORRECTIONS_APP.md` **只读、未改** | 🟢 收尾复核四项指纹（SHA/字节/mtime/条数）与开工值**逐字一致** |
| 只**追加** `## §N` | 🟢 §238 追加在文末；旧章节一字未改 |
| 头部 `last_ack` ⇒ 已执行完的最大编号 | 🟢 `APP-136` → **`APP-137`** |
| 「更新时间」用 `Get-Date` 实测 | 🟢 见文首 |
| 结论引用**结果文件与原始字段** | 🟢 §1.2 表逐项给字段名＋原始值；产物给字节/SHA256/mtime |
| **未打包 zip** | 🟢 本轮**未打包任何 zip** |
| **未改任何客户包** | 🟢 v2.6 / v1.1.1 / MiniMVP v1.2 候选目录**都不是交付包**；影子包只建在 `shared\shadow_pkgs\` 且只联接**只读** |
| **未调 MiniMax** | 🟢 |
| **未连 B 机** | 🟢 |
| 只 add **App 侧**文件；**绝不** add `CORRECTIONS_APP.md` | 🟢 已核对 staged 列表无 CORRECTIONS |
| 普通 push，**不 force push** | 🟢 本轮 push 的是**普通提交**（`0f00e2d`），**未 force** |
| 机器锁：一次持锁到底、抢不到就等 | 🟢 两臂同一把锁；`lock_lost` **0**；中途 demo 暂停时**先确认 PID 死**（`OpenProcess` err=87）才回收锁 |

## §7 下一轮

- `last_ack` = **APP-137**；⏭ 剩余：**APP-137 §3 后半**（A 上三轮 + 缺模型降级）
  → **APP-134 b** → **APP-134 c** → **APP-135 §4–§5**。
- 🔴 **待用户/reviewer 裁定**：默认设备摆放（§1.5 给了两档的对照数据）；
  存量 13 个会议译文文件；v2.7 何时出；仓库根 `.gitattributes` 根治。
