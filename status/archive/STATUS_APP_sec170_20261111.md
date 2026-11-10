## §170 执行 APP-098（MiniMVP rc7 修整）｜**无新纠偏落文件**｜**本条需等 reviewer 复核**

> 🔴 **APP-098 由 reviewer 口头下达**（`status/app/CORRECTIONS_APP.md` **仍是 97 条 / 最大 APP-097** ⇒ 本条**未落该文件**；该文件**全程只读、未改、未提交**）。

### ① 开工/收尾基线（纠偏文件**只读**）

| 项 | 值 |
|---|---|
| `CORRECTIONS_APP.md` SHA256 | `36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2`（开工＝收尾，**未变**） |
| 字节数 / mtime | 285 671 B / 2026-11-10 11:49:26 |
| `## APP-xxx` 条数 | **97**（最大 APP-097）⇒ **无新纠偏可执行** ⇒ 本轮做的是 **reviewer 口头指示的 APP-098** |
| `last_ack` | APP-097 → **APP-098**（头部定点改，旧正文一字未删） |

### ② 🔴 本轮最重要的结论：**「共用部分只改一处」怎么落地**（不是靠复制两份代码）

* 🔴 **先查清了一个架构事实**：MiniMVP rc5 的 `app/` 与开发树 `live_caption/` 是**两条独立的代码血脉**
  （rc5 是 rc4→rc3 一路打补丁上来的；dev 树另走一路）⇒ 「rc5 改一处、dev 树改一处」= **两处** ⇒ 必然漏。
* ⇒ **本轮的做法**：**dev 树成为唯一源码**，MiniMVP 包**直接用 dev 树的文件**（`app/*.py` 全量对齐），
  两个包的差别只由**两样**驱动：
  ① **包内标记 `package_profile.json`**（产品形态 ⇒ CUDA / 克隆音色开关）；
  ② **模型是否就位**（0.6B vs R2T2 的 ASR 引擎族 ⇒ `active_asr_engines()` 自动选）。
  ⇒ **0.6B 的引擎表/别名/接线也从 rc5 的「构建脚本字符串补丁」搬进了 dev 树**（`ENGINES_ASR06B`）⇒ **代码只有一份**。
* 🔴 **副作用（已核对）**：dev 树原本**模块级 import `clone_voice`** ⇒ MiniMVP 包里没有这个文件 ⇒ **一 import 就崩**
  ⇒ 已改成**按包形态条件 import**（`package_profile.allow_clone_voice()`）⇒ 完整版照旧、MiniMVP 不 import。
* 🔴 **本轮新查出的真缺陷（§⑤）**：这条「共用一份代码」的路线上，`kind=='asr06b'` **不是** `'ov'` 也**不是** `'npu'`
  ⇒ 落进了 `build_asr_options()` 的「遍历所有设备」分支 ⇒ **两个 ASR 档 label 完全相同** ⇒ GUI 靠 label 反查 ⇒ **静默取错档**。

### ③ 一、界面和后端（**全部 PASS**，证据见 §④）

| 要求 | 结果 | 证据 |
|---|---|---|
| 三后端去掉所有 NVIDIA/CUDA（含 audio.cpp CUDA、CUDA TTS） | **PASS** | `ENGINES` 删 `cuda_q8`/`cuda_q4`；`build_tts_options()` 删 CUDA 条目；`device_config.detect_devices()` 过滤 NVIDIA 设备；CLI `--tts-device CUDA` **明确报错退出 2** |
| 只保留 Intel GPU / Intel NPU 两档 | **PASS** | `--check`「ASR 后端」= **2 行**（Intel GPU · INT8 / Intel NPU · INT8） |
| 翻译用包里实际有的 INT4-CW、默认档指向实际存在的模型 | **PASS** | `MT_ENGINES` 实测：`DEFAULT_MODEL=mt2-int4sym-cw-q`（**存在**）；「（默认）」标记**按实际默认动态生成** |
| 下拉框不出现灰色「缺」选项 | **PASS** | MT 下拉只含**本机存在的**档；INT8-CW 在 `--check` 报 `[ — ]（本包不附带该量化版本）` ⇒ **不再报「缺模型」** |
| 克隆音色 GUI 置灰 + 提示「MiniMVP 不提供音色克隆」、默认预设 A | **PASS** | `package_profile.clone_voice_unavailable_reason()`；下拉项文字 = `跟随说话人（克隆·实验）〔MiniMVP 不提供音色克隆〕`；**选中即拒绝并回落 A** |
| CLI 传 `follow_speaker` 回落 A 并打一行日志 | **PASS** | `run_cli()` 回落 + `print('[TTS] 🔴 … 已回落「预设 A」')` |
| 目标语言扩到 10 种（按 APP-097 口径） | **PASS** | `TARGETS`/`TARGET_LABELS`/`_LANG_NAME` 各 **10**；`LANG_MAP` **31** 项；GUI 下拉 **11 项**（含「关闭」） |
| 拉丁字母之间不跳翻译、西里尔判 ru | **PASS** | `_SKIP_EQ_SAFE = {zh,ja,ko,ru}`（`'en'` **不在**集合内 ⇒ 拉丁文本永不凭脚本跳过）；`_CYRILLIC ⇒ 'ru'` |
| 未知语言码报错、不静默回落英文 | **PASS** | `map_language('nl', strict=True)` → **ValueError**；`'xx'` 同 |

### ④ 二、rc5 五个实测问题（**全部 PASS**，含「改前/改后」对照）

| 要求 | 改前（rc5 实测） | 改后（rc7 实测） |
|---|---|---|
| ① 编码崩溃（英文 Windows + 重定向到文件） | **崩**：`UnicodeEncodeError: 'gbk' codec can't encode character '\xae'` ⇒ **exit=1** | **exit=0**，输出 **UTF-8 可解码**、含中文、**无** UnicodeEncodeError（**清空全部 `PYTHON*` 环境变量**的子进程里验的） |
| ② R2T2 残留 `models/tokenizer/`（hidden 2048） | 存在（9 个文件） | **已删** ⇒ zip 清单里 `models/tokenizer/` 计数 **0**（0.6B 读的是 `asr06b-tokenizer`） |
| ③ ASR 打印 EXECUTION_DEVICES | **无** | `asr06b_backend` 编译完 encoder+decoder 后打印（**字符串不逐字符拆** ⇒ 不会把 `'NPU'` 读成 `['N','P','U']`）；**六臂实测**：`encoder=GPU.0，decoder=GPU.0` / `encoder=NPU，decoder=NPU`（见 §⑥） |
| ④ ASR+MT 同占 GPU 崩溃（268 s → `CL_OUT_OF_RESOURCES`） | 无提示 | GUI 与 CLI **都给提示**（建议 ASR 放 NPU）⇒ **只提示、不改用户选的设备**（与 APP-062 D4 的「MT 自动改 GPU」**刻意不同**） |
| ⑤ README_perftest 自相矛盾 | 写「rc5 9.97 GB」（= 模型字节数当压缩体积）／写「rc5 未改 ASR 侧」（**错**，rc5 已换 0.6B）／基准表是 rc3 的数 | 体积/文件数**按实测重写**（zip 与解压后**分开写**）；「未改 ASR 侧」已**改正**；旧基准表**明确标注是 rc3 的 ASR、不能代表本包**；**新增「Meteor Lake 155H 实测」节**（iGPU RTF 2.71 / NPU RTF 3.35 / ASR+MT 同占 iGPU 崩溃 ⇒ **不能实时**） |

### ⑤ 🔴🔴🔳 本轮**新查出并修掉**的 GUI 真缺陷（`asr06b` 的 label 撞车）

* **现象**：GUI「识别后端」下拉**两项文字完全相同**（都是「Intel GPU（集显） · INT8」），
  且**NPU 档在 GUI 里根本不存在**（截图 `01_combo_asr.png` 实拍）。
* **根因（读码定案）**：`build_asr_options()` 只分三种 kind：`'ov'`（遍历设备）、`'npu'`（写死 NPU）、`'cuda'`（已删）。
  而 0.6B 的 kind 是 **`'asr06b'`** ⇒ **既不是 `'ov'` 也不是 `'npu'`** ⇒ 落进「遍历所有设备」分支
  ⇒ `gpu_int8` 与 `npu_int8` **两个引擎档各自产出一条同 label 的选项**。
* **危害（比「重复」严重）**：GUI 靠 **label 反查**（`_cur_asr_opt()`：`for o in self._asr_opts: if o['label'] == lab`）
  ⇒ **永远命中第一条** ⇒ 用户在 GUI 里选不到 NPU 档 ⇒ **静默错档**（以为在 NPU、实际在 GPU）。
* **修法**：0.6B 的设备**由引擎表自己写死**（`cfg['device']`）⇒ **不参与「设备 × 精度」笛卡尔积**
  （0.6B encoder 是 fp16 静态图 ⇒ GPU/NPU 各一份 IR ⇒ 本来就是**两条固定的档**）⇒ 两档 label 天然不同。
* **修复后实测**：下拉 = **「Intel GPU（集显） · INT8」+「Intel NPU · INT8」**（截图 `01_combo_asr.png`，SHA `c213cd28d2ea290e…`）。
* 🔴 **修在 dev 树**（`live_caption/live_caption_app.py::build_asr_options`）⇒ **rc7 包内与 dev 树逐字节一致**（diff 0 行）。

### ⑥ 三、验收（**全部 PASS**）

> 🔴 **验收跑在哪个包上（必须写清）**：下面 5 项验收**全部跑在 rc6 目录**上（当时 rc6 目录内是**修复后**代码）。
> 由于该目录随后**已回滚**（见 §⑦-1），需说明**验收结论对 rc7 是否成立**：
> **rc7 目录 ⟷ 当时的 rc6 目录：10 496 文件全量逐字节比对 ⇒ 仅 2 个文件不同**
> （`README_perftest.txt` / `release.json`，且内容差异**只有版本号 / zip 字节数**）
> ⇒ **代码、模型、脚本、配置全部逐字节相同** ⇒ **验收结论对 rc7 成立**。
> （该比对由 `_app423_rc6_dir_rollback.py` 复算并留证。）

| 项 | 结果 | 产物 |
|---|---|---|
| ① GUI 截图（识别/翻译/语音三下拉 + 克隆控件 + 目标语言下拉） | **PASS 6/6**（主窗 1455×1132 + 5 个下拉展开） | `results/app/app413b_rc6_gui_shots/`（6 PNG，逐张过**像素级守卫**：非黑 + 内容密度 > 0） |
| ② `--check` 全文 | **PASS**：NVIDIA/CUDA/缺 **0 处**；MT 段 INT8-CW 报「本包不附带该量化版本」；默认指向 **INT4-CW** | rc7 包内 `python/python.exe -s app/live_caption_app.py --check` |
| ③ 冒烟（ASR/MT/TTS × GPU/NPU，各 60 s） | **PASS 6/6**：六臂 **exit=0** 且**有输出**；`EXECUTION_DEVICES` 直证 ASR encoder/decoder 落点与请求一致 | `results/app/app414_rc6_smoke.json`（六臂日志在 `app414_rc6_smoke/`） |
| ④ 10 语言（每种 5 句 MT + 2 句 TTS，wav + json） | **PASS 10/10**：每语种 **译文 3 条**（**与原文相同 0 条**）＋ **wav 2 个**（合计 20 个 wav、时长 27.5–38.6 s） | `results/app/app419_rc6_langs_summary.json` + `app419_rc6_langs_summary_payload.json`（原文/译文/wav 路径） |
| ⑤ 模型身份 | **PASS**：ASR 两个 bin SHA **与 rc5 一致**（decoder `7fbeb8ef999ddfba…` / encoder `0b7463d6f952dd64…`）；**反证组有效**（改 1 文件 ⇒ 树 SHA 必变）；禁项（R2T2 / INT4-ASR / `models/tokenizer/`）**全 0** | `results/app/app417_rc6_model_identity.json` |

### ⑦ 🔴 交付包 = **rc7**（rc6 zip 一字未动；rc6 **目录**曾被误改 ⇒ 已回滚并留证）

* 🔴 **为什么不是 rc6**：本轮 §⑤ 修掉了 `asr06b` label 撞车 ⇒ **rc6 的代码是缺陷代码**
  ⇒ 按「**永不原地改旧版**」纪律 ⇒ **新打 rc7**（新目录 + 新 zip），**rc6 zip / rc5 及更早 zip 一字未动**。
* rc7 目录：`%USERPROFILE%\Confucius4_LiveCaption_MiniMVP_v1.0-rc7`（**10 496 文件 / 5.514 GB**）
* rc7 zip：`%USERPROFILE%\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc7_perftest.zip`
  （**4 420 655 883 B／SHA256 `290b9b2e83d41da1…`／10 466 条目／CRC32 逐条一致 10 466 条**）
* 构建证据：`results/app/app420_minimvp_rc7_build_evidence.json`
* zip 证据：`results/app/app422_rc7_zip_evidence.json`
* 🔴 **rc6 zip（4 420 655 558 B／SHA256 `76b400e40f95fd21…`）登记为「含缺陷、未交付」** ⇒ **不可当交付物**。

#### ⑦-1 🔴🔴 本轮**自查出的自违规**并已纠正：「验收时在 rc6 目录就地改了代码」

* **事实**：§⑤ 的 `asr06b` 修复当时是**直接写进 rc6 目录**的（`app/live_caption_app.py`，
  23:01:08）⇒ **rc6 目录 ≠ rc6 zip**（zip 内 475 504 B＝缺陷代码；目录内 476 874 B＝修复后代码）
  ⇒ **违反「永不原地改旧版」** ⇒ 必须纠正，不能带着不一致的 rc6 目录交付。
* **处置（本轮已完成）**：**把 rc6 目录回滚**到与 **rc6 zip 逐字节一致**
  （`results/app/_app423_rc6_dir_rollback.py` → `results/app/app423_rc6_dir_rollback.json`）。
  ⇒ **rc6 zip 一字未动**（SHA 前后一致）；**rc6 目录**不再冒充「修好的 rc6」。
* **判据（三条 + 双反证组，全 PASS）**：
  ① rc6 目录 ↔ rc6 zip **10 466 条目 SHA256 逐条一致**（diff = 0）；
  ② rc6 目录 ↔ rc7 目录差异 **恰好 3 个文件** = `README_perftest.txt`（差 zip 字节数）/
     `release.json`（差版本号）/ `app/live_caption_app.py`（差 `asr06b` 修复块，**+18 行 / −0 行，纯增量**）；
  ③ **AST 判据**：`build_asr_options` 内处理的 kind —— rc6 = `['npu']`（**无 asr06b**）
     vs rc7 = `['npu','asr06b']` ⇒ **「缺陷代码 vs 修复后代码」可机器判定**。
* 🔴 **反证组（必须能识破，否则判据恒真）**：
  ① 把 rc7 的 `if cfg['kind'] == 'asr06b':` **替换成 `if False:`**（不删行，避免掏空 `if` 块致 SyntaxError）
     ⇒ AST 判据的 kinds 掉回 `['npu']` ⇒ 判据 FAIL ⇒ **有效**；
  ② 篡改 rc7 的 `README_perftest.txt` 一行 ⇒ 「README 差异只有版本号」判据 FAIL ⇒ **有效**。
* 🔴 **回滚前状态的可复算证明**（脚本可重跑 ⇒ 必须能自证历史）：
  rc6 zip 内代码 **AST 判据 = 不处理 asr06b**（SHA `291b076a95c807d7…`／475 504 B），
  dev 树与 rc7 那份 **SHA 相同**（`3c39bdfae8d1398d…`／AST = 处理 asr06b）⇒ 两个 SHA 互相印证。
* 🔴 **本次自纠还暴露了一个判据设计错误（已记）**：v1 判据写「rc6 目录 ↔ rc7 目录差异 = 2 个文件」——
  **回滚后必然是 3 个**（多了 `live_caption_app.py` 这一处**故意**的差异）⇒ 该判据会诱导
  「把回滚撤掉、让 rc6 目录继续冒充修好的版本」⇒ **判据本身会改坏东西** ⇒ 已重写为 v2。
  同类坑：**不能用「全文出现 `if cfg['kind'] == 'asr06b':`」当判据** —— `_check_models()` 里本来就有这一句
  （rc6 zip 内也有）⇒ 锚点不唯一 ⇒ 恒真 ⇒ 改用 **AST 定位函数体**。

### ⑧ 🔴 三处**如实登记**的不足（不粉饰）

1. 🔴 **MT 侧没有 `EXECUTION_DEVICES` 直证**：ASR 与 TTS 都有（前者 `asr06b_backend`、后者 `tts_engine.execution_devices`），
   **MT 没有** —— `openvino_genai` 的 `LLMPipeline` **不暴露该属性**（实测 `dir()` 里无 `execution_devices`）。
   ⇒ MT 臂只能靠日志（「加载翻译模型（GPU.0）…」「翻译模型就绪（… · GPU.0，加载 6.4 s）」）
   ⇒ **「写 device=GPU.0 ≠ 直证在 GPU.0」** ⇒ **不得**据此写「MT 落点已证」。
2. 🔴 **App 真实链路下 de/zh 的 TTS wav 会被丢弃**：`tts_worker` 有**过期丢弃闸**（`lag > 6 s` ⇒ 只出字幕不配音）；
   de 因 TTS 慢（积压峰值 **53.16 s**）⇒ 5 句丢 4 句 ⇒ **App 链路 wav = 1**。
   ⇒ 补测用 **APP-097 §2-3 同款口径**（直接调 `tts_engine.stream()`，参数链 `map_language` → `language_supported`
   → `split_long_text` → `clamp_max_new_tokens` → `estimate_sec` → `stream`）⇒ **10 语种 × 2 句 = 20 个 wav 全部落盘**。
   ⇒ **未改任何生产代码、未改阈值**（该闸门是交付配置的一部分）。
3. 🔴 **`app415` 的 `summary.json` 里 `translations` 取的是 `subtitles.txt`（= 原文）** ⇒ 该字段**自相矛盾**
   ⇒ §⑥④ 的译文一律取 **`subtitles.mt.txt`**（真实译文），并在 `app419` 里逐行比对「与原文相同 = 0」。
4. 🔴 **本轮自身出现一次「原地改旧版」**：§⑤ 修复当时直接写进了 **rc6 目录** ⇒ rc6 目录 ≠ rc6 zip
   ⇒ **已回滚 rc6 目录**（§⑦-1）⇒ 但**过程本身仍是自违规**，如实登记，不含糊。

### ⑨ 未做 / 停下等 reviewer（本轮**一律未自行推进**）

* 🔴 **未打包 v2.5**（APP-055：v2.5 须走新版本号；且 **GUI 布局缺陷同步策略仍等 reviewer 裁定**）
* 🔴 **未通知用户**（APP-098 三.6 明文「不通知用户」）
* 🔴 **未调 MiniMax**（质量判定由 reviewer 回转写；目标机不调）
* 🔴 **MT 的「是否给新语言设 >1× 倍率地板」未改默认值**（APP-097 §2.4：只报数字）
* 🔴 **旧 zip（rc3/rc4/rc5/rc6）一字节未动**（zip 脚本逐个复核 SHA 前后一致）
* 🔴 **未评估 §⑤ 缺陷的历史影响**（该缺陷自 `ENGINES_ASR06B` 进入 dev 树起存在 ⇒ **MiniMVP rc6 之前所有 0.6B 包的 GUI 都受影响**）
* 🔴 **rc6 目录已回滚**（§⑦-1）⇒ **rc6 目录现在等于 rc6 zip（含缺陷代码）** ⇒ **不得再拿 rc6 目录当「修好的包」使用**
