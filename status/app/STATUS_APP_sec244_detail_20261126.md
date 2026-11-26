# STATUS_APP §244 — 执行 **APP-149 / APP-150 / APP-151**（`last_ack` APP-148 → **APP-151**）

> 本节正文全文。**§243 及以前各节一字未改**。
> 头部 `last_ack` 由 `APP-148` 更新为 **`APP-151`**。
> 生成时间：2026-11-26（Asia/Shanghai）。

## §0 本轮性质

reviewer 于 **2026-11-26 16:14:36** 在 `status/app/CORRECTIONS_APP.md` 追加了
**APP-149 / APP-150 / APP-151**（文件从 18 308 B 增至 27 323 B／7 条 → 10 条）。
这三条都排在**打 zip 之前**，且**都命中了 §243 报出来的阻塞点**：

* **APP-149**：EXT 插件侧的 ASR 只支持 R2T2 ⇒ MiniMVP 包上 ASR 起不来
  ⇒ 套用 reviewer 写好的 **EXT v0.4.23**（ASR 支持 0.6B）；
* **APP-150**：打 zip 前的**清洗与硬门禁**（运行产物不入包、ACCEPTED 不进包、
  三轮逐项零失控零丢句、README 补 NPU 排障、APP-143 两项不能漏）；
* **APP-151**：候选目录 `app\translator.py` 是 11-20 旧版、只认 mt2
  ⇒ **App 界面上 MT 一项都没有** ⇒ 重做候选目录时 `app\*.py` 必须**整体**同步。

🔴 **本节先记录已闭合的部分**；APP-149 第 6/7 项（60 s 冒烟 ＋ 三轮重跑）
仍在进行 ⇒ **未打 zip、未签 ACCEPTED**（APP-147/150 的门禁未满足）。

## §1 APP-149 第 1/2/3 项 —— EXT v0.4.23（**已推送 GitHub**）

**commit `c955411`**（`live-dub-ext`，普通 push）：`EXT v0.4.23: ASR works with
Qwen3-ASR 0.6B packages (MiniMVP/SpecialMVP) — pick the model family the
package actually ships`。

### §1.1 套用 reviewer 的文件

来源：`C:\Users\Trekker-PLT_PLACEHOLDER\shared\ext_v0423_stage\engine_runtime.py`
（基于我的 `e901cad`，**只改 ASR 部分**；`git diff --no-index` 实测
**92 增 24 删**）。

新增 `_asr_family()`：

| 包内实际带的模型 | 判定 |
|---|---|
| `models/encoder-int8` ＋ `models/decoder-gpu-int8`（R2T2） | **`r2t2`** |
| `asr06b-encoder-fp16` ＋ `asr06b-decoder-int8` ＋ `asr06b-tokenizer` ＋ `embed_tokens_06b_f16.npy`（**四样齐全**） | **`06b`** |
| 两族都有 | **`r2t2`**（与 App 合并表的默认一致） |
| 都没有 | `None` ⇒ `_load_asr` 抛 `EngineNeedsChange`，**报错里列出查过的路径** |

`EXT_ASR_FAMILY=06b|r2t2` 可**强制**（指定的族缺文件 ⇒ `None` ⇒ 由调用方报缺模型）。
0.6B 分支与 App `OVEngine`（`kind=='asr06b'`）**同一构造方式**：
`asr06b_stateful_backend.BACKEND_CLASS(encoder_dir, decoder_dir, tokenizer_dir,
embed_npy, device, precision='f16', cache_dir)`。
预热标签与「ASR 就绪」日志按**实际模型族**写
（`ASR 就绪（Qwen3-ASR 0.6B INT8 @ GPU.0，…）`）。

### §1.2 🔴 我做的**接口兼容性核对**（reviewer 只改了加载，没改调用）

EXT 的调用点（`_make_asr_state` ＋ `asr()`）用的是 **App 的
`seg_stream`／`streaming_asr`**：

```
streaming_asr.streaming_transcribe 用到 backend 的：
  backend.init_streaming_state / backend.generate_with_prefix
  backend.tokenizer / backend.log / backend.name
```

⇒ **0.6B 后端 `ASR06BStatefulBackend` 全都有这些方法**
（`init_streaming_state`／`generate_with_prefix`／`tokenizer`／`name`）
⇒ **加载换成 0.6B 即可用，调用路径不必改** ⇒ 与 reviewer 的实现一致，**无冲突**。

### §1.3 单测（`tests/test_ext0423_asr_family.py`，**新增 16 用例**）

mock 文件系统覆盖 reviewer 指定的 5 种情况
（「只有 R2T2 → r2t2」「只有 0.6B → 06b」「两族都有 → r2t2」
「`EXT_ASR_FAMILY=06b` 强制」「都没有 → `EngineNeedsChange`（报错列出查过的路径）」）
＋ **反证组**（把被检对象换成「永远返回 r2t2」/「永远返回 None」的假实现
⇒ 判据必须 FAIL）⇒ **16/16 PASS**。

🔴 踩坑：测试的 dummy 类第一版漏了 `_asr_backend` 等属性
⇒ `_load_asr` 里 `if self._asr_backend is not None:` 直接 `AttributeError`
⇒ 已补齐。

### §1.4 全量单测（APP-150 §4 的「EXT 全量单测 0 failed」的诚实口径）

用**包内 python 3.12.10** 跑（APP-120 口径）：

| | 文件数 | rc 非零 | FAIL 用例 |
|---|---|---|---|
| BASELINE（干净 HEAD） | 39 | 15 | 62 |
| AFTER（v0.4.23） | 41 | **14** | **47** |

逐文件比对：**变差 0 个**；`test_ext009_adaptive_speed.py` 由红转绿（fail 15 → 0）；
两个新增测试（`test_ext0422_mt3_turbo.py` 17/17、`test_ext0423_asr_family.py` 16/16）全过；
其余 **14 个红文件是基线既有的环境/历史问题**（非本轮引入），
**本轮无法做到「全量 0 failed」** ⇒ 如实登记，**不粉饰**。
产物：`live_dub_ext/results/ext0423_all_tests_AFTER.json`。

🔴 `test_ext0422_mt3_turbo.py` 的版本号断言**原来写死 0.4.22** ⇒ 升版本就误报
⇒ 改成「**两处一致 ＋ ≥ 0.4.22**」（版本升级不再误报，「两处不一致」仍会被抓到）。

## §2 APP-139 的 turbo 落到**真正的编译点**（本轮的关键修正）

### §2.1 🔴 之前漏在哪：真正的 NPU 编译在 `babelvox/pipeline.py`

| 位置 | 代码 | turbo 能注入吗 |
|---|---|---|
| `babelvox/pipeline.py::_compile_npu` | `core.compile_model(model, "NPU")` | ❌ **不传任何属性** |
| `live_caption/tts_engine.py` 的 cp_prefill/cp_decode | 我上一轮改的 `_npu_compile_props` | ✅ 但**实测没被触发** |

⇒ 已在**候选包的 `app/tts_engine_patch.py`** 覆写 `_compile_npu`：
带 turbo 编译 ⇒ 编译失败/不支持 ⇒ 退回 `super()._compile_npu`
（**不让 turbo 拖垮 TTS**）⇒ 日志打**实际值**。

### §2.2 🔴 三个真缺陷（都是**实测**抓到的，不是推测）

1. **`from npu_turbo import ...` 静默失败**
   ⇒ `tts_engine_patch.py` 是用 `importlib.util.spec_from_file_location` 加载的
   ⇒ **不在 `sys.path` 里** ⇒ 同目录的 `npu_turbo` **import 不到**
   ⇒ `_turbo_props=None` ⇒ **整个 turbo 分支被静默跳过**（日志一条都没有）
   ⇒ 修法：按**本文件所在目录**显式加载。
2. **裸 `print` 无处可去**
   ⇒ 桥接进程用 `pythonw.exe`（**无 console**）
   ⇒ 改走 babelvox 的 logger 又被**级别过滤**
   （`babelvox.pipeline.logger` 的 level=**WARNING**、handlers=**[]** ⇒ `logger.info` 一条不出）
   ⇒ 修法：加 `set_turbo_logger(on_log)`，由 `tts_engine.make_engine` 注入
   **on_log 通道**（**唯一真能落盘的通道**）。
3. **`core.available_devices` 是「属性」不是方法**
   ⇒ 第一版写成 `core.available_devices()` ⇒ 真实 OV 上抛 `TypeError`
   ⇒ 被单测当场抓到 ⇒ 现兼容两种形态，**单测两种都覆盖**。

### §2.3 行为级真跑（真实 `ov.Core` ＋ 真实 IR，**冷编译**）

`results/app/app146_turbo_real_compile.json` —— **6 PASS / 0 FAIL**：

| | 编译 | 读回 `NPU_TURBO` | 读回 `EXECUTION_DEVICES` |
|---|---|---|---|
| 带 turbo | 成功 | **True** | **NPU** |
| 关掉（反证） | 成功 | **`<RuntimeError>`（属性不存在 ⇒ 读不到）** | NPU |

### §2.4 🔴 EXT 的 `DEVICE_TTS` 默认是 **AUTO** ⇒ 开发机上会走 CUDA

实测：EXT 探测到本机有 CUDA 边车（RTX 5050）⇒ **TTS 走 CUDA** ⇒
**NPU 从未被编译** ⇒ turbo 无处注入、也测不到「出厂默认」这条路。
客户机没有 CUDA ⇒ 会回落 NPU ⇒ **NPU 才是 MiniMVP 的真实出厂路径**
⇒ 三轮统一显式钉 `EXT_TTS_DEVICE=NPU|EXT_MT_DEVICE=GPU.0`。

## §3 APP-151 第 1 项 —— 候选目录 `app\*.py` **整体**同步

同步前实测：候选 `app/` 的 **34 个** `.py` 里**只有 2 个**与 dev 树不同：

| 文件 | 方向 | 原因 |
|---|---|---|
| `translator.py` | 候选 ← dev | ★ 候选是 **11-20 旧版**（96 701 B）⇒ **只认 mt2** ⇒ GUI 的 MT 下拉 0 项 |
| `tts_engine_patch.py` | dev ← 候选 | 本轮 turbo 注入只写进了候选 |

同步后：**差异清单 = 0 项**（`results/app/app151_app_py_sync.json`）；
`translator.py` 的 **mt3 引用在第 65/68/69/70/72/73 行**（共 6 行）；
`translator.py` mtime = **2026-11-26 17:25:42**。

另改 `live_caption_app.py` 的 **3 处** `Hy-MT2-1.8B` → `Hy-MT3-1.8B`
（`--check` 的「翻译后端」标题、CLI help、模块 docstring）。

## §4 APP-151 第 2 项 —— App 侧引擎可用自查（**已做**）

用**候选目录自带 python** 跑包内 `--check`：

```
── ASR 后端（识别）──
  [ OK ] Intel GPU · INT8 (stateful) 模型齐全
  [ OK ] Intel NPU · INT8 (stateful) 模型齐全
── 翻译后端（Hy-MT3-1.8B）──
  [ OK ] Intel GPU · INT8-CW（默认） GPU.0
  [ OK ] Intel NPU · INT8-CW        NPU
  [ OK ] 自动 · INT8-CW 模型（默认） 跟随 --mt-device
结论：环境正常。ASR 可用后端 2 个，Intel 集显可用。
```

MT 引擎列表（`translator.MT_ENGINES`）：**auto / gpu_int8cw / npu_int8cw，
三项 `mt_available` 全为 True**；`DEFAULT_MODEL` =
`…\models\mt\mt3-int8sym-cw-q`（**mt3 生效**）。

**App 链路真翻译 3/3 成功**（GPU.0，246～586 ms；`results/app/app151_app_mt3_check.json`）：

| 原文 | 译文 |
|---|---|
| `Hello, welcome to the live caption demo.` | `你好，欢迎来到实时字幕演示。` |
| `The meeting starts in ten minutes.` | `会议将在十分钟后开始。` |
| `Please make sure the background music is kept.` | `请确保背景音乐保持不变。` |

## §5 APP-149 第 5 项 —— 候选目录换 v0.4.23 ＋ README 更新（**已做**）

* `ext/bridge/engine_runtime.py`（v0.4.23）／`ext/bridge/version.py`（**0.4.23**）／
  `ext/extension/manifest.json`（**0.4.23**）／`release.json`（`ext.version=0.4.23`）。
* README（中/英）：**删掉**「插件（EXT）侧的语音识别在本包不可用」那段
  ⇒ 改为写明「**插件（EXT）用的识别模型就是本包里的 Qwen3-ASR-0.6B**」；
  并按 **APP-150 §3** 在「设备配置 / 常见问题」里加了 **NPU 排障两行**
  （NPU 配音有杂音/异常 ⇒ 改 TTS=GPU.0，或设 `LIVECAP_NPU_TURBO=0`），
  **用客户能看懂的话**，不出现内部编号。

## §5＋ §6 APP-149 第6 项的前半：ASR 0.6B 加载验证通过

| 项 | 结果 |
|---|---|
| `_asr_family()` | **06b**（正确识别包里带的是Qwen3-ASR 0.6B，不是R2T2） |
| ASR 加载 | 成功，**12.4 s**，backend = **ASR06BStatefulBackend** |
| 就绪日志原文 | **ASR 就绪（Qwen3-ASR 0.6B INT8 @ GPU.0，12.3s）** |
| 落点 | encoder=GPU.0，decoder=GPU.0 |
| EXT 调用链需要的接口 | 全部具备（missing interface = **[]**） |

执行方式：用**候选目录自带 python**， + 包内 `ext/bridge/engine_runtime.py`（不是开发树的 EXT） ⇒ 验的就女拿到的那份代码。本项只加载模型、不跑推理 ⇒ 不占推理资源 ⇒ 可在等机器锁期间独立验证；「端到端出数据」仍需 APP-149 第6 项的 60 s 冒烟（等LFM 让锁）。脚本： `live_caption/_app149_asr_load_check.py`；结果： `results/app/app149_asr_load_check.json`

## §5＋＋ §6 APP-149 item5 (final check): candidate ext/bridge is content-identical to the EXT source (real content difference = 0)

| item | count |
|---|---|
| EXT src .py | 25 |
| candidate ext/bridge/*.py | 25 |
| byte-identical | 13 |
| EOL-only difference (autocrlf) | 11 |
| **real content difference** | **0** |
| missing in candidate (CUDA-only) | 1 |

The one missing file is `tts_cuda_sidecar_ext.py` - **CUDA sidecar only**; it is referenced only from the CUDA branch of `engine_runtime.py`, and MiniMVP ships no CUDA => not needed. Method: compare **content after normalizing line endings** (otherwise the autocrlf EOL difference would look like a content difference - the §226 lesson). Script: `live_caption/_app149_ext_sync_check.py`; result: `results/app/app149_ext_sync_check.json`

## §6 本轮的提交

| 仓库 | commit | 内容 |
|---|---|---|
| **App（main）** | **`323fcdf`** | turbo 落到真正的编译点 ＋ 候选 `app\*.py` 整体同步 ＋ Hy-MT3 文案 ＋ 证据/脚本入库 |
| **EXT（live-dub-ext）** | **`c955411`** | EXT v0.4.23：ASR 支持 Qwen3-ASR 0.6B 包 |

（App 侧此前还有 `eea625e`＝APP-139 turbo 统一判定，已推 GitHub。）

## §7 未完成 / 下一步

1. 🔴 **APP-149 第 6 项（60 s 冒烟）**：用候选目录自带 python 起桥接、喂 60 s 片段，
   确认日志里有 `ASR 就绪（Qwen3-ASR 0.6B INT8 @ GPU.0 …）`、
   `MT 就绪（Hy-MT3 …）`，且 **n_error=0、asr_segments>0、dubs>0**。
   **本轮启动时机器锁被 LFM 的 LFM-007 占着 ⇒ 按规矩排队等、不抢**
   （job 在后台排队，尚未拿到锁）。
2. 🔴 **APP-149 第 7 项 ＋ APP-146/147/148 三轮重跑**（冒烟通过后）；
   门禁新增：**三轮的 `n_error` 必须为 0**、`asr_segments` 等于提交段数量级。
3. 🔴 **APP-150 §1 的打 zip 白名单检查（已做，18/18 PASS）**
   （脚本 `live_caption/_app150_zip_whitelist.py`，结果 `results/app/app150_zip_whitelist.json`）：
   clone 目录**为空**／**无运行产物**（bridge_token/log/bridge.err/ov_cache/npu_cache/__pycache__）／
   包内文本搜 `Trekker-PLT` **0 处**／**包内没有 device_config.json**（它是**用户级配置**，
   路径 `%LOCALAPPDATA%\Confucius4LiveCaption\`，不入包）／代码里的 MiniMVP 出厂默认
   **ASR=GPU.0 / MT=GPU.0 / TTS=NPU**／profile：NPU_TURBO 开、保留背景音开、
   不带 CUDA、不带 c13、MT=mt3、EXT **v0.4.23**／插件侧「保留背景音」**默认开**、
   「克隆」**默认关**（默认音色＝预设 A）／除 `preset_A.wav` 外**无音视频**／**无 CUDA DLL**／
   **ACCEPTED.json 不在包内**。
   🔴 本轮顺带修掉一个真缺陷：候选包 `package_profile.json` 的 `ext_version` 还写着 **0.4.22** ⇒ 已改 **0.4.23**。
（运行产物不入包、ACCEPTED 不进包、
   包内文本搜 `Trekker-PTL` 为 0 处、`device_config.json` 是出厂默认…）。
4. 🔴 **APP-148 §1b（zip 一致性）与 §1c（抽听样片）**：等有真实配音后再做
   （上一轮因 ASR 失败 ⇒ 混音是静音，样片无可听内容 ⇒ 已如实登记未硬造）。
5. 🔴 **未打 zip、未签 ACCEPTED**（APP-147/149/150 的门禁未满足）。

## §8 纪律自查

| 纪律 | 结果 |
|---|---|
| `CORRECTIONS_APP.md` **只读、未改** | 🟢 收尾复核（见 §9） |
| 只**追加** `## §N` | 🟢 §243 ＋ §244；旧章节一字未改 |
| 头部 `last_ack` | 🟢 → **APP-151** |
| 结论引用结果文件与原始字段 | 🟢 §1.3／§1.4／§2.3／§3／§4 均给文件路径＋原始字段 |
| 只 add App 侧文件；**绝不** add `CORRECTIONS_APP.md` | 🟢 |
| 普通 push，**不 force push** | 🟢 App `323fcdf`（普通）；EXT `c955411`（普通） |
| 机器锁：抢不到就等、**不抢** | 🟢 本轮冒烟**两次**被 LFM 抢锁 ⇒ 排队等待 |
| **不打 zip**（未经用户通知） | 🟢 **未打任何 zip** |
| **未签 ACCEPTED** | 🟢 |
| 未改旧客户包 | 🟢 只改 `.candidate`（还没发出去） |
| 交付口径：没落盘的不写「已交付」 | 🟢 zip / ACCEPTED / 抽听样片 / 三轮（重跑）**均如实写「未完成 + 原因」** |
| 🔴 遇到的真缺陷 | 🟢 3 个（turbo 导入静默失败／print 无效／`available_devices` 是属性）**全部写进代码注释**，不只写在 STATUS |


