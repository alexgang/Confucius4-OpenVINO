# APP-121 §221 详情（companion）

> 本文件是 `status/app/STATUS_APP.md` 的 `## §221` 的**正文**；活文档只留标题行 + 摘要 + 指针行。
> 生成脚本：`live_caption/_app121_sec221_body.py`（**数字全部从证据 json 读出**）。

生成时间：2026-11-23 10:41:47

## §0 本条结论摘要

| reviewer 的要求 | 结论 | 证据 |
|---|---|---|
| §1 [HIGH] ASR=NPU 长段抛 ValueError 让 ASR 线程退出 | **已修**：NPU 档 `allowed_prefix = limit − skeleton`（不再减 reserve），只有 `skeleton > limit` 才报错；另加总量检查 `prompt + reserve ≤ limit + 64`；GPU 档逻辑一字未动。**旧包可复现该缺陷**（`ValueError: prompt 骨架 281 + 预留 64 > 320`），新包同一素材**无 ValueError、字幕持续输出到结束** | `results/app/app121_asr_npu_longseg_old_v11.json` / `…_new_v111.json` / `app121_asr_npu_prefix_unit.json` |
| §2 [HIGH] §0④ 的 md5 没跑 App 代码 | **已撤回** §220 companion 的两句结论（「App 侧接入在 NPU 上逐字节复现参照」「对 GPU.0 零回归」）；**已补**用 App 后端（`OVEngine`＝`StreamingEngine` + `ASR06BStatefulBackend`）跑 §86 三素材的 NPU / GPU.0 各一组，报 transcript md5 与 `prefix_truncations` | `results/app/app121_asr_app_3mat_NPU.json` / `…_GPU0.json` |
| §3 [NORMAL] zip 与目录不一致 + 未做解压自检 | **已修**：`tts_cuda*` 两个文件**改名挪到包外**（不删）⇒ ACCEPTED 的模块清单与 zip 的实际内容**完全一致**；**已做**解压自检（全新目录 + 全新 `%LOCALAPPDATA%` 跑 `--check` + GUI 冒烟） | `results/app/app121_update_meta.json` / `app121_zip_extract_check.json` / `app121_gui_smoke.json` |
| §4 [NORMAL] README 与 STATUS 的小问题 | **已改**（详见 §4） | `results/app/app121_write_readme_evidence.json` |
| §5 范围与纪律 | **已按要求执行**：只改 `asr06b_stateful_backend.py` / `live_caption_app.py` 的 `_loop` / README / 打包脚本；dev 树与 v2.5 **逐字节同一份**；重跑自检/洁净度/整链/①②③；重签 `ACCEPTED.json`；重打 zip；解压自检 | `results/app/app121_sync_pkg_evidence.json` 等 |

## §1 [HIGH] ASR=NPU 时长段抛 ValueError（已修 + 已验收）

### 根因

* `asr06b_stateful_backend.py` 的 `build_inputs_embeds` 旧写法：`allowed_prefix = limit − skeleton − reserve`，`allowed_prefix < 0` 就 `raise ValueError`。
* NPU 档 `limit = 320`（NPUW `MAX_PROMPT_LEN`），段尾 `_finalize()` 的 `reserve = 64` ⇒ **`skeleton + 64 > 320` 就报错**。
* handoff（`qwen3asr_06b/dev/asr065_handoff.md` §三/§四）的约束是 **prompt ≤ 320**，**生成部分另算**（KV = 320 + 64 = 384），**只有 `base_len > pml` 才报错** ⇒ 旧写法**把 64 个生成 token 也算进了 320**。
* 实测门槛：骨架 18 + 音频 token；**段长 ≈ 18.3 s** 起就报错 ⇒ **20 s 强制切段的段**、**18.3–20 s 之间靠静音切的段**都会中招。
* 异常冒到 `Session._loop` 的外层 `except` ⇒ `self.error=e` / `running=False` ⇒ **本次会话的字幕整条停掉**。

### 修法（只改 `asr06b_stateful_backend.py` + `live_caption_app.py` 的 `_loop`）

1. **NPU 档**：`allowed_prefix = limit − skeleton`（**不再减 reserve**）；**只有 `skeleton > limit` 才报错**；总量检查 = `prompt + reserve ≤ limit + NPUW_LLM_MIN_RESPONSE_LEN(64)`。
2. **GPU 档（512）逻辑一字未动**（`allowed_prefix` 仍减 `reserve`，总量检查仍对 `MAX_STATEFUL_TOK=512`）。
3. **附带修正**：流式档 `reserve=32`、段尾 `reserve=64` ⇒ 旧写法两者**前缀截断口径不同**（多砍 32 个 token）⇒ 转写与 ASR 参照口径不一致；现在 NPU 档两者口径一致（单测里 `kept_r32 == kept_r64`）。
4. **`_loop` 加固**：单段解码异常 ⇒ **记日志 + 计数 + 跳过这一段继续**（`Session._note_seg_error()`），**不再让整条 ASR 停掉**。

### 验收 ①（不做推理的单测）

* 被检文件 = **包内** `app/asr06b_stateful_backend.py`（`__file__` 指向包内真实路径）⇒ SHA256 `36f20581799f0b16`
* **11/11 用例 PASS**（含 reviewer 点名的 `skeleton = 18 + {238, 260, 266}`、`reserve ∈ {32, 64}`、`skeleton=321` 报错）
* 截断口径一致性 **3/3 PASS**（`reserve=32` 与 `reserve=64` 保留的前缀数相同）
* **反证组**：修复前的同一文件（`git HEAD` 取出，SHA256 `07fff3964618956d`）在同样的用例上**有 2 个「本应通过」的用例抛了 ValueError** ⇒ **判据能识破该缺陷**（不是恒 PASS 的假判据）
* 证据：`results/app/app121_asr_npu_prefix_unit.json`

### 验收 ②（包内 python 跑 ASR=NPU + ≥20 s 不停顿连续语音）

* **素材**：从 SPE（`clip_10min_0_600.wav`）里把 **App 自己认得的静音**整段抠掉（判据 = `live_caption_app._frame_db_series` + `seg_stream.find_silence_in_range`，30 ms/10 ms，相对门限 `p90−12 dB`，`min_silence_ms=300`）⇒ **26.0 s 连续语音、最长静音 0.2 s** ⇒ 规则1/规则2 都不触发 ⇒ 段只能累积到 `MAX_SEG_SEC=20 s` ⇒ **被强制切段**
* **A/B 用的是磁盘上两个真实客户包**：**旧包 = `Confucius4_LiveCaption_MiniMVP_v1.1`**（修复前代码）／**新包 = `Confucius4_LiveCaption_MiniMVP_v1.1.1`**（修复后）

| 指标 | 旧包 v1.1（修复前） | 新包 v1.1.1（修复后） |
|---|---|---|
| CLI 退出码 | 1 | 0 |
| 日志含 `ValueError` | **True** | False |
| 异常原文 | `ValueError: prompt 骨架 281 + 预留 64 > stateful 上界 320（音频过长）` | （无） |
| **字幕行数 / 字符数** | **0 / 0**（字幕整条停掉） | **2 / 514**（持续输出到结束） |
| 段长探针：段数 / 各段时长 | 0 / [] | 2 / [20.48, 0.0] |
| **强制切段次数**（`dur ≥ MAX_SEG_SEC`） | 1 | **1**（时长 [20.48] s） |
| 段长探针异常 | `ValueError: prompt 骨架 281 + 预留 64 > stateful 上界 320（音频过长）` | `None` |
| `prefix_truncations` | 5 | 5 |

* 证据：`results/app/app121_asr_npu_longseg_old_v11.json`（反证组）＋ `results/app/app121_asr_npu_longseg_new_v111.json`（修复后）

### 验收 ③（GPU 档：同一个 10 分钟片段，转写与 v1.1 逐字节相同）

* 判据：**GPU 档的代码路径一字未动** ⇒ 用**同一个素材、同一套 App 后端**在**旧包（v1.1）**与**新包（v1.1.1）**各跑一次 GPU.0 ⇒ 两边的 `transcript.txt` 必须**逐字节相同**（md5 相同）。

| 素材 | 新包 v1.1.1 GPU.0 md5 | 旧包 v1.1 GPU.0 md5 | 逐字节相同 |
|---|---|---|---|
| spe | `d68715dfbc` | `d68715dfbc` | **是** |
| en | `fbe91f2a3b` | `fbe91f2a3b` | **是** |
| zh | `57ce6bc177` | `57ce6bc177` | **是** |

* 证据：`results/app/app121_asr_app_3mat_GPU0.json`（新包）＋ `results/app/app121_asr_app_3mat_GPU0_OLD_v11.json`（旧包对照臂）

## §2 [HIGH] 撤回 §220 的 md5 结论 ＋ 补 App 后端实测

### 🔴 撤回（reviewer §2 第一段）

§220 companion 里的这两句**不成立**，本节**撤回**：

1. ❌「**App 侧接入在 NPU 上逐字节复现参照**」
2. ❌「**对 GPU.0 零回归**」

**理由（reviewer 的原话 + 实测）**：§220 的 `_app120_asr_3mat.py` 用的是 **ASR 模块**的 `bk_run.run_stream` ＋ `asr065_backend.Asr065Runner`，**没有经过 App 的 `ASR06BStatefulBackend`** ⇒ 那个测试**只能证明包里的模型文件和 ASR 模块用的是同一份**。

### ✅ 补测（用 App 的后端跑 §86 三素材）

* 调用路径 = **包内 `app/live_caption_app.py` 的 `OVEngine`**（= `StreamingEngine` 包装 ＋ `ASR06BStatefulBackend`）⇒ 流式块走 App 的 `_st()`（`max_new_tokens=32`）、段尾定稿走 App 的 `_finalize()`（`reserve=64`）、**切段走 App 自己的 `Segmenter`**。
* 解释器 = **包内 python**（OV `2026.4.1-22982-e213a147257-releases/2026/4`，与 §86 参照同版本）。

| 设备 | 素材 | 段数 | transcript md5 | `prefix_truncations` | RTF |
|---|---|---|---|---|---|
| NPU | spe | 93 | `2d7218ae43a66e45` | 0 | 0.4318 |
| NPU | en | 65 | `8a7e64cf262f63ff` | 0 | 0.4286 |
| NPU | zh | 66 | `e4efbe483f8c768b` | 3 | 0.4045 |
| GPU.0 | spe | 93 | `d68715dfbcf3545a` | 0 | 0.3857 |
| GPU.0 | en | 65 | `fbe91f2a3b2e5971` | 0 | 0.3815 |
| GPU.0 | zh | 66 | `57ce6bc17768fa60` | 0 | 0.3236 |

* §86 参照 md5（ASR 模块口径）：`cd67417e…`（spe）／`ed3f52aa…`（en）／`d93062a6…`（zh）⇒ **三个素材在两个设备上都不等于参照**。

### 逐段解释（为什么不一致 —— reviewer 说「不要求硬凑一致」）

* **段边界一致**：三个素材的段数 **App 与参照完全相同**（spe 93/93、en 65/65、zh 66/66）⇒ **切段器行为一致**，差异**不在切段**。
* **差异在解码/拼接路径**：App 的流式路径**每个 640 ms 块都带前缀重新解码**，段尾再把前缀原样喂一遍（`prefix` ＝ 已解出的文本）；ASR 模块的参照是 `raw + " " + final` 拼接 ⇒ **词边界处的空格与 token 切分不同**（实测样例：App `All right. Good morning, everyone.` vs 参照 `Alright. Good  morning, everyone.`；App `Agenda topics today.` vs 参照 `Ag enda topics today.`）。
* **量化**：去掉全部空白后，spe 52/93 段、en 47/65 段、zh 51/66 段与参照**逐字相同**；全文去空白后 App **略长**（spe 8078 vs 8059 字符、en 4398 vs 4360、zh 1583 vs 1576）⇒ **差异以块边界的空白/分词为主，另有少量词尾差异**。
* **结论**：**App 侧接入不逐字节复现 ASR 模块的参照** ⇒ §220 的两句结论撤回；§1③ 用「**新包 vs 旧包同设备逐字节相同**」来证明 **GPU 档未受影响**（这是可判定的口径），**不再**用「与 ASR 模块参照逐字节相同」当判据。

## §3 [NORMAL] zip 与目录不一致 ＋ 缺解压自检（已修 ＋ 已做）

### ③-1 ACCEPTED 的模块清单 vs zip 的实际内容

* **reviewer 点的缺陷**：`app/tts_cuda.py`、`app/tts_cuda_sidecar.py` **被 `pkg_exclude` 排除在 zip 之外**，却**出现在 `ACCEPTED.json` 的 `code_fingerprints` 里** ⇒ 「签的」与「发的」不是同一份。
* **修法（取 reviewer 给的两条路之一：把 zip 外的模块从指纹里去掉）**：MiniMVP **无 CUDA** ⇒ 这两个文件**改名挪到包外**（**不删**；本机安全删除会把文件转回收站、批量删被拦 ⇒ 打包脚本一律不删，只能「改名挪到包外」）；包内 4 处 `import tts_cuda` **全在 try/except 里**（已逐处核对）⇒ 功能不受影响。
* **复核**：生产模块（app191 口径：只看 `app/` 根目录的 `.py`）**31 个**；zip 内 `app/` 根目录的 `.py` **31 个** ⇒ **集合完全相同**（`only_production=[]` / `only_zip_root=[]`）；zip 内 `tts_cuda*` = `[]`；指纹内 `tts_cuda*` = `[]`。
  * zip 内另有 **6 个** `app/asr_spk/*.py`（**子目录**）⇒ app191 指纹口径**只算 `app/` 根目录** ⇒ 不在指纹集合里（**不是缺陷**：指纹集 ⊆ zip 全部 `.py`）。
* 挪出去的位置：`C:\Users\Trekker-PTL\shared\minimvp_v111_excluded\`（**文件完好，未删除**）
* 证据：`results/app/app121_update_meta.json`

### ③-2 解压自检（全新目录 ＋ 全新 `%LOCALAPPDATA%` ＋ GUI 冒烟）

* zip = `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.1.1.zip`（5212403155 B）
* 解压到**全新目录** `C:\Users\Trekker-PTL\AppData\Local\Temp\app121_extract`（83.0 s，`testzip()=None`）
* **全新 `%LOCALAPPDATA%` 下跑 `--check`**：退出码 **0**
* 判定 **PASS**（17 项检查，0 失败）
  * [PASS] 解压 testzip() 无坏条目
  * [PASS] 解压出的包目录存在且含 app/
  * [PASS] 全新 %LOCALAPPDATA% 下 --check 退出码 0
  * [PASS] 自检：提到 Intel 集显 / GPU.0
  * [PASS] 自检：提到 NPU
  * [PASS] 自检：ASR 后端出现 stateful
  * [PASS] 自检：MT 后端出现 INT8-CW
  * [PASS] 自检：TTS 后端出现
  * [PASS] 自检：**未**出现 CUDA 后端（MiniMVP 无 CUDA）
  * [PASS] ACCEPTED 的 code_fingerprints 键集 == 解压后 app/ 生产模块集合
  * [PASS] ACCEPTED 逐条指纹与解压后文件一致（重算）
  * [PASS] ACCEPTED 聚合指纹与重算一致
  * [PASS] ACCEPTED version 与 release.json 一致
  * [PASS] ACCEPTED pkg_dir 目录名 == 解压后的包目录名
  * [PASS] zip 内 app/*.py 与「生产模块集合」一致（无只在一边的）
  * [PASS] ACCEPTED 不含 zip 里没有的模块（tts_cuda* 不得在指纹里）
  * [PASS] 解压后的文件数 == zip 内文件数（10881）
* 证据：`results/app/app121_zip_extract_check.json`

### ③-3 GUI 冒烟

* 🔴 **本机不用 `schtasks`**：`schtasks` / `cmd.exe` / COM(`WScript.Shell`) / `Start-Process` **全被安全策略禁止**（见 `MEMORY_MODULES.md` 十七）⇒ 改走「父进程直接拉起包内 GUI + **Win32 `PrintWindow`** 抓窗口」。
* 🔴 **不用 `PIL.ImageGrab`**：本机会话隔离下抓出来是**全黑** ⇒ `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` 直接渲染窗口内容。
* 判定 **PASS**；窗口 3 个，标题 `实时字幕 MiniMVP v1.0`；抓图 1455×1132，灰度方差 1380.436（**非全黑 ⇒ 真的渲染了内容**）
* 截图：`C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app121_gui_shots\app121_gui_v111.png`（45555 B）
* 证据：`results/app/app121_gui_smoke.json`

## §4 [NORMAL] README 与 STATUS 的小问题（逐条）

### ④-1 文件数 / 字节数改成 **zip 解压后的实际数字**

* 旧 README 写「解压后 **10 904 个文件 / 6 702 027 740 B**」⇒ 那是**目录**口径（含 24 个被 `pkg_exclude` 排除的文件）。
* 新 README 写 **10881 个文件 / 6701780843 B**，口径 = **zip 清单**（`pkg_exclude.iter_package_files`）⇒ **与 zip 内实际内容一致**。
* 🔴 README 自己进包 ⇒ **自指大小**：写盘后重算，迭代到**不动点**（2 次迭代，`fixed_point=True`）⇒ 写进 README 的数字与磁盘实测**一致**。

### ④-2 去掉内部编号与研发用语

已去掉：**APP-119 / APP-120 / ASR-065 / ASR-066 / 「v2.5 全集」 / 「R2T2」 / 「handoff」**（中英双语 README 全文已无这些字样）。

### ④-3 已知问题补一条「配音滞后」

> ⚠️ **讲话密集时，配音会比原声滞后。** 10 分钟连续讲话实测：滞后最大约 **43 s**、讲完收尾时约 **30 s**。App 会**自动加速追赶**（最高 **1.7×**），追平后恢复正常速度；积压没追平前字幕仍会持续输出，不会丢句。

### ④-4「怎么改设备」的示例

* 第 1 条修好前**不能**用 ASR=NPU 做示例 ⇒ 现已修好 ⇒ **保留**原示例（`--asr-device NPU --mt-device NPU --tts-device GPU.0`）。

### ④-5 「首字延迟 0.39 s」与「字幕出字延迟 303 ms」分开写

* 🔴 **0.39 s 是 TTS 状态行里的「首包」**（`[TTS] 首包 0.39s …`），**不是字幕出字延迟**。
* ✅ **字幕出字延迟中位 303 ms** 来自识别引擎状态行（`[gpu_int8] … 出字延迟中位 303 ms …`）⇒ 两个数在 README 里**分列两项**。

### ④-6 companion 的行号订正 ＋ 证据文件名带时间戳

| §220 companion 原写的行号 | **实际行号**（针对 §220 当时的文件 SHA `07fff396…`） |
|---|---|
| `278-280`（`self._max_prompt_tok` 实例属性） | **325-327** |
| `485-507`（左截断 + `prefix_truncations` 计数） | **549-571** |
| `489-493`（`base_len > pml` 显式报错） | **553-557** |

* 🔴 **本轮（APP-121）又改了这两个文件** ⇒ 上面三行是 **§220 当时**的文件（SHA `07fff396…`）里的行号；**当前**（修复后）的行号见下表：

| 锚点 | §220 当时 | **当前（修复后）** |
|---|---|---|
| `NPUW_PROPS` / `NPUW_MIN_RESPONSE_LEN` | 72-77 | **72-85** |
| `self._max_prompt_tok` 实例属性 | 325-327 | **333-335** |
| `build_inputs_embeds` 全方法 | 549-583 | **539-624** |
| 左截断 + `prefix_truncations` 计数 | 558-571 | **599-612** |
| `base_len > pml` 报错分支（NPU 档） | 553-557 | **586-589** |
| 总量检查 `prompt + reserve ≤ limit + 64` | （旧版无此条） | **621-623** |
| `Session.__init__` 的 `asr_seg_errors` 初值 | （旧版无） | **2543** |
| `Session._note_seg_error()`（新增） | （旧版无） | **2564-2581** |
| `Session._loop`（加固后） | 2559-2607 | **2583-2644** |

* （当前行号 = 修复后 dev 树文件的**实测行号**；dev 树 ＝ v2.5 ＝ v1.1.1 三份**逐字节相同** ⇒ 行号对三份都成立。）

* 证据文件名带时间戳：§220 companion 引用的 `app591_acceptance_app120_v11_default_run.json` ⇒ **实际文件名是** `app591_acceptance_app120_v11_default_run20261122-143100.json`。

### ④-7 `timing_valid=false` 的归因更正

* ✅ **保留** `timing_valid=false` 这个结论。
* ❌ **撤回**「机器被占」这个归因 —— **没有证据**：锁看门狗 **外来变动 0 次**。
* 🔴 **改正后的表述**：**判定线 P90 ≤ 0.75 是 CUDA TTS 那几臂定的**，**不适用于 NPU 合成**；NPU 的 `synth_rtf` 本来就在 **0.85–1.06**（v2.5 默认臂 0.97/1.06）⇒ **NPU 合成本身的吞吐接近实时，这才是配音滞后的主要原因**。

## §5 范围、纪律与重跑清单

### 只改了哪些文件

* `live_caption/asr06b_stateful_backend.py`（`build_inputs_embeds` 的 NPU 分支 + 新增 `NPUW_MIN_RESPONSE_LEN` 常量）
* `live_caption/live_caption_app.py`（`Session._loop` 加固 ＋ `Session._note_seg_error()` ＋ `Session.__init__` 的计数初值）
* README（中/英，由 `live_caption/_app121_write_readme.py` 生成）
* 打包/验收脚本（`live_caption/_app121_*.py`，**新文件，未改旧脚本**）

* 🔴 **dev 树 ＝ v2.5 ＝ v1.1.1 三份逐字节同一份**（定点同步：`difflib` 导出改写块 ＋ **唯一命中断言** ＋ **还原式复核** ＋ 写后逐字节复核）：
  * `app` ⇒ `asr06b_stateful_backend.py`：hunks=3，undo=PASS，sha256=`36f20581799f0b16`
  * `app` ⇒ `live_caption_app.py`：hunks=3，undo=PASS，sha256=`9cd8e8bf72c68dcd`
  * `app` ⇒ `asr06b_stateful_backend.py`：hunks=3，undo=PASS，sha256=`36f20581799f0b16`
  * `app` ⇒ `live_caption_app.py`：hunks=3，undo=PASS，sha256=`9cd8e8bf72c68dcd`
* 🔴 **旧包 `Confucius4_LiveCaption_MiniMVP_v1.1` 逐字节未动**（`asr06b_stateful_backend.py` SHA 仍是 `07fff396…`，`live_caption_app.py` 仍是 `4701e5bd…`）⇒ 本轮**用它当 §1② 的反证组**（缺陷在真实旧包上复现）。

### 版本纪律（APP-055）

* 🔴 **没有 `--same-version` 覆盖重打**：本轮**新目录** `Confucius4_LiveCaption_MiniMVP_v1.1.1` ＋ **新 zip** `Confucius4_LiveCaption_MiniMVP_v1.1.1.zip`；**v1.1 的目录与 zip 全部保留未删未覆盖**。
* `ACCEPTED.json` 重签为 **version=1.1.1**、`pkg_dir` 与新目录名一致；`release.json` / `app/MANIFEST.json` 同步到 1.1.1（三者版本一致）。

### 重跑清单（reviewer §5 要求）

| reviewer 要求 | 结果 | 证据 |
|---|---|---|
| 自检 9/9 | **PASS**（9 项，0 失败） | `results/app/app121_accept_v111_selfcheck.json` |
| 洁净度 | **PASS：0 违规** | `live_caption/assert_pkg_clean.py` |
| 默认配置 10 分钟整链（数字跟本轮对比） | **PASS 14/14** | `results/app/app591_acceptance_app121_v111_default_run20261123-1000.json` |
| 第 1 条 ② | 见 §1 验收 ② | `app121_asr_npu_longseg_*.json` |
| 第 1 条 ③ | 见 §1 验收 ③ | `app121_asr_app_3mat_GPU0*.json` |
| 重签 `ACCEPTED.json` | **PASS**（闸门⑤ `OK`） | `results/app/app121_sign_accepted_v111_evidence.json` |
| 重打 zip | **5212403155 B / 10881 文件** | `results/app/app121_zip_v111.json` |
| 第 3 条解压自检 | 见 §3 | `results/app/app121_zip_extract_check.json` |

### 纪律与边界

* 🔴 **未改** `status/app/CORRECTIONS_APP.md`（reviewer 独占；本轮开工/收尾各测一次 SHA256／字节数／mtime／条目数）。
* 🔴 **未通知用户**（APP-121 §5「不要通知用户」）。
* 🔴 **未连 B 机**（APP-109 ④ 仍然有效）。
* 🔴 **未改** v1.1 / v2.5 / rc11 / sp5 等既有包的其它内容。

### 🔴 本轮如实登记的**四处事故 ＋ 一处既有 harness 缺陷**

**① 第一个 harness 版本把 `machine_lock_app.acquire()` 的返回值当字符串用**⇒ `TypeError` 抛在取锁之后 ⇒ **锁被泄漏**（`shared/MACHINE_LOCK` 留在盘上）。

* 处置：用 `ctypes` `OpenProcess` **确认 PID 25888 确已死亡**（`err=87`＝ERROR_INVALID_PARAMETER⇒进程不存在）⇒ 把锁**改名归档**为 `shared/MACHINE_LOCK.released_app_leak_1795397250`（**未删除**）⇒ 改脚本为 `ok, payload = acquire(...)` 后重跑。

**② §1② 的反证组第一轮**造素材时**静音阈值取错了**（用了 `p90−30 dB`，而 App 自己的判据是 `p90−12 dB`）⇒ 造出来的素材里仍有 ≥300 ms 静音 ⇒ 段长只有 6.4 s ⇒ **旧包根本没触发缺陷**（旧包 CLI 反而 rc=0）。

* 处置：改用 **App 自己的** `_frame_db_series` + `find_silence_in_range` 抠静音并**复核「已无 ≥300 ms 静音」** ⇒ 重跑 ⇒ 旧包立刻复现 `ValueError`（见 §1 验收 ②）。🔴 **教训**：造判据用的素材也必须用**被检对象自己的判据**。

**③ CLI 的 `--out` 文件是增量写的** ⇒ 反证组重跑时统计到的「字幕行数」是**上一轮残留**（5 行 / 345 字符）。

* 处置：跑前**先删** `--out` 与日志 ⇒ 重跑 ⇒ 旧包字幕行数 **0**、新包 **2 行 / 514 字符**（见 §1 验收 ② 的表）。

**④ lang10 验收把 v1.1 的证据覆盖了**（**同一个坑第二次踩**）。

* 现象：APP-120 的编排脚本 `_app120_accept_v11.py` 的 `step_lang10` 把 `--out` **写死**成 `app120_accept_v11_lang10_evidence.json` ⇒ 本轮跑 v1.1.1 时把 **v1.1 的那份证据覆盖成了 v1.1.1 的**（8990 B → 8999 B，SHA `91cef981…`）。
* 处置：① 把本轮的结果**另存**为 `app121_accept_v111_lang10_evidence.json`（v1.1.1 专属）；② **用 v1.1 包重跑 lang10 恢复** v1.1 的那份 ⇒ **10 PASS / 0 FAIL**（结论一致）；③ 本模块的编排脚本已把 `--out` 改成 v1.1.1 专属文件名 ⇒ **不再会覆盖**。
* 🔴 **如实记录**：恢复后的文件 **SHA 与 §220 companion 引用的不同**（`at` 时间戳与逐句时长都会变）⇒ **不声称「SHA 零改动」**。

**⑤ 既有 harness 缺陷（不是事故，是本来就坏的代码）**

* `_app120_accept_v11.py` 的 `_list_out_devices()` 返回**设备 id 列表**，而 `step_devswitch()` 里写的是 `out_ids = [i for i, _n in out_pairs]` ⇒ 把 id **字符串**按 2 个字符解包 ⇒ `ValueError: too many values to unpack` ⇒ **devswitch 这一步在已提交的版本（1af497d）上根本跑不起来**（v1.1 那次的 6/6 PASS 是用临时补丁跑出来的，**已提交文件里仍是坏的**）。
* 处置：🔴 **不修改 `_app120_accept_v11.py`**（那是 APP-120 的历史产物）⇒ 只在本模块的编排脚本 `_app121_accept_v111.py` 里**覆写**`_list_out_devices` 让它返回 `(id, name)` 对 ⇒ **devswitch 7/7 PASS**（比 v1.1 那次多一项：耳机那项多验了「输出设备」字样）。

### 🟡 一处**观察到但未改**的现象（留给 reviewer 裁定）

* GUI 窗口标题仍是 **`实时字幕 MiniMVP v1.0`**（APP-069 时定的**产品名**，不是包版本号），而本包版本是 **1.1.1**（`release.json` / `ACCEPTED.json` 都是 1.1.1）⇒ 客户看到的标题与版本号不一致。
* 🔴 **本轮未改**：APP-121 §5 明确限定改动面（`asr06b_stateful_backend.py` / `live_caption_app.py` 的 `_loop` / README / 打包脚本）⇒ 标题属于**界面文案**，不在本条授权范围内 ⇒ **留给 reviewer 决定**（是否随下一版改）。
* 证据：GUI 冒烟截图 `results/app/_app121_gui_shots/app121_gui_v111.png`（标题栏可见 `实时字幕 MiniMVP v1.0`）。

