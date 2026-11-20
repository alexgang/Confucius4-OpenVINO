# STATUS_APP §217 明细（APP-116 续 + APP-117 + APP-118）

> 🔴 本文件是 `status/app/STATUS_APP.md` **§217 的正文**（活文档逼近 40 000 B 限额 ⇒ 正文放 companion）。
> 活文档里只有 §217 标题行 ＋ 一段摘要 ＋ 指向本文件的指针行。

**时间**：2026-11-20 15:29 → 收尾时间见活文档头部「更新时间」
**执行条数**：APP-116（续做）／APP-117／APP-118（last_ack: APP-116 → **APP-118**）
**来源**：`status/app/CORRECTIONS_APP.md` 的 `## APP-116`（10:20）／`## APP-117`（10:30）／`## APP-118`（11:00）
＋ **QQ 邮箱**三封同源邮件（`alexchen7694@agent.qq.com`）：
`[C4][A][CORRECTION][APP] APP-116`（11-20 10:00:40）／`APP-117`（11-20 11:04:15）／`APP-118`（11-20 11:34:28）
⇒ **两条来源内容一致 ⇒ 按协议只执行一次**。

**开工时的现场**（TAKEOVER）：
上一会话（token `881292b2`）在 11-20 14:24 **心跳超时被接管** ⇒ 它已做完
**APP-116 §1/§2/§3 的代码与 v2.5 复制/定点同步**，但 **v2.5 的「全集补齐」「EXT 升级」
「profile 裁剪」「验收」全未做** ⇒ 本轮**从断点继续**，不重做已完成的 §1/§2/§3。

---

## §0 本轮先说结论（三条纠偏的执行状态）

| 纠偏 | 状态 | 一句话 |
|---|---|---|
| **APP-116** | 🟢 **已完成**（§1/§2/§3 由上一会话做完并留证；本轮补齐 v2.5 全集） | 输出设备修好、预设 B（男声·模型生成）已生成、GUI 去 4 选项 |
| **APP-117** | 🟢 **已完成**（12/12 PASS × 2 档缩放） | 总状态灯按钮**从界面去掉**；**报错可见性不受影响**（12 条判据含 5 条「报错仍可见」） |
| **APP-118** | 🟢 **已完成**（除「10 语种真跑配音」与「CUDA 档真跑整链」外，见下） | v2.5 = **全集**（CUDA + 0.6B + EXT v0.4.18 + 10 语种）；**一份代码三形态**已落地；**模型身份 0 错误** |

🔴 **未打 zip**（用户长期规则：**不通知 ⇒ 不打包**）⇒ 交付物是**包目录** `Confucius4_LiveCaption_v2.5`。

---

## §1 APP-117：界面去掉总状态灯「有模块待处理」

### 1.1 改了什么（**只在 dev 树 `live_caption/live_caption_app.py`**）

| 位置 | 改动 |
|---|---|
| 顶栏建控件处（约 L2891） | **删掉** `self.btn_global_light = ttk.Button(...)` ＋ `pack` ＋ `_fit_status_light_width()` 调用 ⇒ **按钮不再存在** |
| `_update_strips()`（约 L7000） | **不再**更新按钮文字/颜色（按钮已不存在 ⇒ 写了也看不见）；**只保留内部汇总状态**（`_global_light` / `_global_light_color`） |
| `_apply_global_light_style()`（约 L7031） | 改成**空操作**（`getattr(self, 'btn_global_light', None)` 为 None ⇒ 直接 return）⇒ **既有诊断脚本（`app238` 用 `getattr` 量像素）不会 AttributeError** |
| `_show_global_status()`（约 L7115） | **不再弹 `messagebox`** ⇒ 改为**只写会话日志**（`append_session_log`，**不走 `_ui_log`**） |
| **新增** `_global_status_summary()` | 汇总逻辑**保留为内部函数**（reviewer 明示：「汇总逻辑如被别处引用，可保留为内部函数，但界面不再出现」） |

### 1.2 🔴 **报错可见性不受影响**（APP-117 的硬要求）

reviewer 原文：
> **报错不能因此变得不可见**：各模块自身的状态条 / 状态栏照常显示警告和错误，
> 特别是 APP-116 第 1 条要求的「无法打开所选输出设备 ⇒ 已改用系统默认」，
> 以及「NPU 共用，语音可能卡顿」等提示，仍要在状态栏或对应模块条上能看到。

⇒ **总状态灯只是「三区汇总视图」，不是错误信息的唯一载体**。本轮用 **5 条行为级判据**证明：

| 判据 | 内容 | 结果 |
|---|---|---|
| B1 | ASR / 翻译 / 语音 **三条状态条都还在** | ✅ PASS |
| B2 | TTS 条**能显示 warn 级别**（真设一个 warn ⇒ `level()=='warn'`） | ✅ PASS |
| B3 | **「NPU 共用 / 语音可能卡顿」真显示出来**（改 `_dev_choices` 触发条件 ⇒ `_fill_tts_strip()` ⇒ 文案进 TTS 条） | ✅ PASS（实测文案：`NPU 共用 语音可能卡顿 NPU 共用：MT、ASR 与 TTS 同在 NPU`） |
| B4 | **「无法打开所选输出设备 ⇒ 已改用系统默认」写进顶部状态行 `var_status`** | ✅ PASS |
| B4b | 顶部状态行控件 `_lbl_status` **仍存在**（没被删） | ✅ PASS |
| **B5** | **调用 `_show_global_status()` 不得覆盖状态行里的错误消息** | ✅ PASS（**这条是本轮抓到的真风险**：汇总文本很长 ⇒ 若走 `_ui_log` 会把 `var_status` 挤掉 ⇒ 反而把真错误挤没了 ⇒ 改成**只落盘不上屏**） |

### 1.3 验收（**12/12 PASS × 2 档缩放**）

脚本：`live_caption/diag_app117_global_light.py`（**行为级**，不是 grep）
证据：`results/app/app117_global_light_evidence_100.json`（12 PASS / 0 FAIL）
　　　`results/app/app117_global_light_evidence_150.json`（12 PASS / 0 FAIL）
截图：`results/app/app117_gui/app117_100pct.png`（52 762 B，SHA `a330436c…`）
　　　`results/app/app117_gui/app117_150pct.png`（74 654 B，SHA `34caa1a6…`）
⇒ **两张 SHA 不同**（证明缩放真的生效，不是同一张图）

判据全表：A1 界面上没有总状态灯按钮／A2 没有指向 `_show_global_status` 的按钮入口／
A3 顶栏控件无重叠（**10 个控件**）／A4 不再弹 modal／A4b 仍返回文本／
A5 汇总逻辑仍可内部调用／B1–B5（见上）。

**布局目视复核**（150 % 截图）：顶栏只剩
`Confucius4实时字幕 ｜ ▶开始 ｜ 清空 ｜ 保存 ｜ ☑屏幕字幕 … 会话 00:00 ｜ ▾高级`
⇒ **无空洞、无重叠、无裁剪**；且 APP-116 §3 的 4 个选项（草稿译文／重试翻译／
区分说话人／显示说话人）在界面上**确实不见了**。

### 1.4 🔴 **本轮在验收脚本里踩到的 3 个坑**（都会造成**假 FAIL**／**假 PASS**）

| # | 坑 | 修法 |
|---|---|---|
| 1 | **顶栏是局部变量 `top`**（不是 `self.top`）⇒ 判据「找不到顶栏容器」 | 用**会话计时标签的 master** 反查；兜底用「含『会话』文字的 Label 的 master」 |
| 2 | **把容器 Frame 自己也算进 x 区间比对** ⇒ 它必然「包含」子控件 ⇒ **必然报重叠** | **只比 `top` 的直接子控件**（同一层的兄弟） |
| 3 | `_fill_tts_strip()` 在 `tts is None` 时**提前 return** ⇒ 「NPU 共用」那段代码**根本走不到** | 给 `app.tts` 塞**桩**（只提供 `stats()` / `pending` / `_queue`）⇒ 走**真代码路径**、**不加载任何模型**、不占 GPU/NPU |

---

## §2 APP-118 §1：v2.5 = 全集（**补齐了什么**）

### 2.1 🔴 **先说一个真缺陷**（否则这轮交付是错的）

`active_asr_engines()` 的旧实现是
`return ENGINES_ASR06B if _asr06b_models_present() else ENGINES`
⇒ **「有 0.6B 模型就只用 0.6B」**（**二选一**）。

⇒ APP-118 把 0.6B 的模型**也放进完整版 v2.5** 之后，这行会**把完整版从 R2T2
翻成 0.6B** ⇒ **违反 APP-118 §1**（「保留 Confucius4-R2T2 1.7B … **完整版默认仍用它，
默认值不变**；同时带上 Qwen3-ASR 0.6B … **作为可选项**」）。

🔴 **本轮先写判据再改代码**（顺序很重要）：把 v2.5 的 0.6B 模型复制进去**之后**、
改代码**之前**跑判据 ⇒ **复现了 6 条 FAIL**（`results/app/app118_asr_engines_evidence.json`）：

```
引擎表：{"gpu_int8": "asr06b", "npu_int8": "asr06b"}     ← 🔴 R2T2 整族消失
[FAIL] A1 v2.5 的 ASR 引擎表**同时**含 R2T2 与 0.6B 两族  — R2T2=0 0.6B=2
[FAIL] A2 ASR **默认**仍是 R2T2（非 stateful）  — key=gpu_int8 kind=asr06b
```

### 2.2 修法（**dev 树 3 个文件**）

| 文件 | 改动 |
|---|---|
| `live_caption/live_caption_app.py` | ① `active_asr_engines()` 改成**三态**：只有 0.6B ⇒ 原表；只有 R2T2 ⇒ 原表；**两族都有 ⇒ 合并表**（R2T2 在前 ⇒ **默认仍是 R2T2**）｜② 新增 `_r2t2_models_present()`（R2T2 侧三件套判据）｜③ 新增 `ASR06B_KEY_PREFIX='asr06b_'` ＋ `ASR06B_LABEL_SUFFIX='（Qwen3-ASR 0.6B）'`｜④ 新增 `_asr06b_engine_table_with_prefix()`（**改写副本，不动原表** ⇒ MiniMVP/SpecialMVP 的 key 与 label **一字不变**）｜⑤ `active_asr_precision()` **同源**合并｜⑥ `default_asr_engine_for_device()` 改成**两轮**（先 R2T2 族，再 0.6B 族）｜⑦ `build_asr_options()` 给 0.6B 的 label **加后缀** |
| `live_caption/device_config.py` | ⑧ 新增 `has_nvidia_gpu()`（**硬件**判据：OV 枚举得到 NVIDIA 设备）｜⑨ `tts_extra_devices()` 加**第三道闸**：**必须有真 NVIDIA 硬件**才给 CUDA 档 |
| `live_caption/package_profile.py` | ⑩ `allow_cuda()` 的注释与语义更新（完整版**读标记文件**的 `allow_cuda`，**无标记文件时仍为 False** ⇒ v2.4 等老包行为不变） |

🔴 **为什么要 key 前缀 + label 后缀**（**§170/§171 已踩过的坑**）：
`ENGINES` 与 `ENGINES_ASR06B` 的 key **同名**（都是 `gpu_int8`/`npu_int8`）
⇒ 直接合并会**互相覆盖**；而 GUI 靠 **label 反查**引擎（`_cur_asr_opt()`）
⇒ 两族 label 都是「Intel GPU（集显） · INT8」⇒ **静默错档**（选了 NPU 那条、
实际仍用 GPU 那条）。

🔴 **`default_asr_engine_for_device()` 为什么必须两轮**：
`ENGINES['npu_int8']` **没有** `device` 键 ⇒ 它对 `'NPU'` **不匹配**
⇒ 单轮会一路落到 0.6B 的 `asr06b_npu_int8` ⇒ **默认值被静默改掉**。

### 2.3 🟢 修完的验收（**12/12 PASS**，真跑包内代码）

脚本：`live_caption/diag_app118_asr_engines.py --pkg <v2.5>`
证据：`results/app/app118_asr_engines_evidence.json`

```
引擎表：{"gpu_int8":"ov","gpu_int4":"ov","npu_int8":"npu","npu_int4":"npu",
         "asr06b_gpu_int8":"asr06b","asr06b_npu_int8":"asr06b"}
[A1] PASS 两族都在（R2T2=4 0.6B=2）
[A3] PASS 0.6B 是可选项而不是唯一引擎
[A2] PASS ASR 默认仍是 R2T2 —— key=gpu_int8 kind=ov
[A4] PASS GUI 下拉 label 全唯一
[A5] PASS 0.6B 的 label 能与 R2T2 分辨
[A6] PASS --check 能列出两族（6 个）
[B1] PASS MT 默认 = INT8-CW（mt2-int8sym-cw-q）
[B2] PASS MT INT4 仍可选（4 档）
[B3] PASS 目标语言 = 10 种
[C1] PASS 包形态 = full
[C2] PASS allow_cuda / allow_clone_voice = True
[D1] PASS CUDA 档的出现与 NVIDIA 硬件一致（extra=['CUDA'] has_nvidia=True）
```

GUI 下拉实测（**6 条，label 全唯一**）：
```
Intel GPU（集显） · INT8 ／ Intel GPU（集显） · INT4 ／ Intel NPU · INT8 ／
Intel NPU · INT4 ／ Intel GPU（集显） · INT8（Qwen3-ASR 0.6B） ／
Intel NPU · INT8（Qwen3-ASR 0.6B）
```

### 2.4 资源补齐（**从 SpecialMVP sp5 复制进 v2.5**，脚本 `_app118_assets_to_v25.py`）

🔴 **纪律**：**复制前先查冲突**（同路径但 SHA 不同的 ⇒ **停下报告，不静默覆盖**）
⇒ 预检「0 个同路径文件、0 冲突」⇒ 全部是**新增**。

| 资源 | 文件数 | 字节 | SHA 复核 |
|---|---|---|---|
| `cuda_env/`（torch 2.11.0+cu128） | 34 126 | 5 105 789 206 | ✅ 逐文件相同 |
| `models/tts_cuda/` | 12 | 2 516 104 532 | ✅ 逐文件相同 |
| `models/asr06b-decoder-int8/` | 2 | 755 242 318 | ✅ 逐文件相同 |
| `models/asr06b-encoder-fp16/` | 2 | 373 557 473 | ✅ 逐文件相同 |
| `models/asr06b-tokenizer/` | 7 | 4 468 999 | ✅ 逐文件相同 |
| `models/embed_tokens_06b_f16.npy` | 1 | 311 165 056 | ✅ 逐文件相同 |

证据：`results/app/app118_assets_to_v25_evidence.json`

### 2.5 包形态标记（**新增 `package_profile.json`**，包根）

```json
{ "profile": "full", "allow_cuda": true, "allow_clone_voice": true,
  "target_langs": 10, "note": "用户 2026-11-20 决定（APP-118）：完整版 = 默认「全集」环境…" }
```
脚本：`_app118_profile_marker_v25.py`（写前验「目标不存在」⇒ **不覆盖**；写后回读复核 4 字段）

### 2.6 EXT 升级到 **v0.4.18**（`live_dub_ext@ee45ce5`）

脚本：`_app118_ext_to_v25.py`｜证据：`results/app/app118_ext_to_v25_evidence.json`

| 动作 | 落点 |
|---|---|
| EXT 桥接 Python 包（**23 个 .py**，CRLF 化） | `ext/bridge/*.py` |
| **新增** `ext/bridge/__main__.py`（打包侧入口，让 `python -m ext.bridge` 可执行） | `ext/bridge/` |
| 浏览器插件（15 个文件 + icons） | `ext/extension/*` |
| `manifest.json`：**version → 0.4.18**、**`liveDub.release` → true** | `ext/extension/` |
| **桥接启动器** `tools/ext_launcher.py`（44 696 B，CRLF） | `tools/` |
| **`Start_Bridge.bat`**（486 B，**CRLF + 纯 ASCII**） | 包根 |
| `.runtime_deps/`（websockets / psutil） | **包根**（与 `ext_launcher.py` 的 `ROOT` 对齐） |
| 旧的 `ext/bridge/bridge_launcher.py` / `start_bridge.cmd` | **改名挪到包外**（`.superseded-*.bak`）⇒ 🔴 **本机有「安全删除 shim」⇒ 删除会失败 ⇒ 不删** |

🔴 **包内实测**（用包自己的 python）：
```
EXT bridge import OK
version.py EXT_VERSION = 0.4.18 2026-11-17
manifest version = 0.4.18 ；liveDub.release = True
Start_Bridge.bat：CRLF=13 LF=13 ascii=True
```

### 2.7 ASR-065 并入 0.6B 路径（APP-118 §1 要求）

| 项 | ASR-065 要求的 | 本轮落地 |
|---|---|---|
| `NPUW_LLM_MAX_PROMPT_LEN` | 512 → **320**（`MIN_RESPONSE_LEN` 保持 64） | ✅ `NPUW_PROPS` 改为 320 |
| 超长前缀**左截断**（默认开） | 从左截（保留右端＝最新内容）；**不抛错、不回退 512** | ✅ `build_inputs_embeds()` 按**实际生效上界**截（NPU=320 / GPU=512） |
| `prefix_truncations` 计数 | int 累加 + 日志字段 | ✅ `probe['prefix_truncations']`（**独立**于 512 上界的总截断） |
| `asr_enc_tiers` 开关 | **默认 off** ⇒ 行为与现状完全一致 | ✅ `ASR_ENC_TIERS` 环境变量；**默认 off**；ON ⇒ 运行时从 base IR 现场构建 4 档 → **直接 compile → 不落盘**；**断言 `patched == 60`**，不满足 ⇒ **退回单档 2400** |

文件：`live_caption/asr06b_stateful_backend.py`（+228/−8）

---

## §3 APP-118 §2：一份代码，三种包靠 profile 裁剪

### 3.1 规则定义（**只写一处**：`live_caption/package_profiles.py`）

| profile | ASR | MT | TTS | CUDA | 克隆 | 语种 |
|---|---|---|---|---|---|---|
| `full` | R2T2 1.7B **＋** 0.6B | INT8-CW（默认）＋ INT4 | OpenVINO（默认）＋ CUDA | ✅ | ✅ | 10 |
| `minimvp` | **只有** 0.6B | **只有** INT8-CW | **只有** OpenVINO | ❌ | ❌ | 10 |
| `specialmvp` | **只有** 0.6B | **只有** INT8-CW | OpenVINO ＋ **CUDA** | ✅ | ❌ | 10 |

🔴 **裁剪＝「挑文件进清单」，不是「删文件」**（本机删除会被 shim 拦）。

### 3.2 dry-run 结果（**证明可以裁出来**；本次**不真打**这两个包）

| profile | 保留 | 排除 | 保留体积 |
|---|---|---|---|
| `full` | **48 633** 文件 | 0 | **26 045 563 372 B（24.257 GiB）** |
| `minimvp` | 14 450 文件 | 34 183 | **10 094 789 422 B（9.402 GiB）** |
| `specialmvp` | 48 588 文件 | 45 | **17 716 683 160 B（16.500 GiB）** |

体积构成（`full`）：`models` 18.710 GiB（170 文件）｜`cuda_env` 4.755 GiB（34 126 文件）｜
`python` 0.784 GiB（14 046 文件）｜`app` 0.004 GiB（78 文件）｜`ext` 0.003 GiB（198 文件）｜
`docs` 4 文件｜根文件 9｜`results` 2

清单落盘：`results/app/app118_profile_{full,minimvp,specialmvp}_manifest.json`（各约 6.0 MB，
含**逐文件**相对路径 + 字节数 + 顶层目录体积构成 + 该 profile 的 `package_profile.json` 标记）

🔴 **未打 zip**（用户长期规则：不通知 ⇒ 不打包）⇒ MiniMVP / SpecialMVP **本轮不出包**。

---

## §4 APP-118 §3：验收

### 4.1 包上自检（`--check`）—— ✅ 环境正常

```
── ASR 后端（识别）──
  [ OK ] Intel GPU · INT8           模型齐全
  [ OK ] Intel GPU · INT4           模型齐全
  [ OK ] Intel NPU · INT8           模型齐全
  [ OK ] Intel NPU · INT4（实验）   模型齐全
  [ OK ] Intel GPU · INT8 (stateful) （Qwen3-ASR 0.6B） 模型齐全
  [ OK ] Intel NPU · INT8 (stateful) （Qwen3-ASR 0.6B） 模型齐全
── 翻译后端（Hy-MT2-1.8B）── INT8-CW（默认）/ INT4-CW / NPU 两档 / 自动
── CUDA 语音后端 ──
  CUDA 运行时：…\v2.5\cuda_env\Scripts\python.exe  [ OK ] 存在
  TTS CUDA 模型：…\v2.5\models\tts_cuda  模型文件：12 个（随包离线可用）
  CUDA 可用性：[ OK ] torch 2.11.0+cu128 / CUDA 12.8 / available=True
  结论：环境正常。ASR 可用后端 6 个，Intel 集显可用。
```
交付洁净度：`app/assert_pkg_clean.py .` ⇒ **[PASS] 交付洁净度闸门：0 违规**

### 4.2 模型身份（**config 维度 + 逐文件权重 SHA 对源目录**）—— ✅ **0 错误**

脚本：`_app118_model_identity.py`｜证据：`results/app/app118_model_identity_evidence.json`

| 模型 | 比对结果 |
|---|---|
| `models/asr06b-decoder-int8` | ✅ 2/2 文件 SHA 相同 |
| `models/asr06b-encoder-fp16` | ✅ 2/2 |
| `models/asr06b-tokenizer` | ✅ 7/7 |
| `models/embed_tokens_06b_f16.npy` | ✅ 1/1 |
| `models/tts_cuda` | ✅ 12/12 |
| `cuda_env` | ✅ **34 126/34 126** |
| **0.6B decoder bin SHA** | ✅ **`0059531a2b4ccd4c…`**（reviewer 点名的那个） |

基线内模型（无独立源目录 ⇒ 按 **config 维度**判）：
R2T2 `decoder-gpu-int8`（hidden 2048 / 28 层 / 16 头）、`decoder-gpu-int4`、
`decoder-npu-int8`、`decoder-npu-int4`、`encoder-int8/int4/fp16`、
MT `mt2-int8sym-cw-q`（hidden 2048 / 32 层）与 `mt2-int4sym-cw-q`、
TTS-OV `qwen3tts/{int8,weights,tokenizer,voices}`、`spk`、`tokenizer`（hidden 2048 / 28 层）

### 4.3 10 语种冒烟

`results/app/app118_lang10_evidence.json` —— **A 组 5/5 PASS**（纯逻辑，零占设备）：
10 种目标语言齐备｜MT 目标名可解析｜TTS language id 可解析｜界面标签齐备｜**三张表的名字一致**

### 4.4 10 分钟固定片段整链

**见活文档 §217 的摘要与本文件末尾「本轮未完成项」。**

---

## §5 本轮**未完成** / **未结**项（如实登记）

| # | 项 | 原因 | 下一步 |
|---|---|---|---|
| 1 | **预设 B 的抽听样本（4 条）与 CER/WER 对比** | 🔴 reviewer 明文「**用户点头前不进包**」⇒ 本轮**没有**把 `preset_B.wav` 放进 v2.5；抽听样本要**跑 GPU 合成 + ASR 回转写** | 用户抽听 + 下一轮跑 `live_caption/_app116_eval_preset.py` |
| 2 | **10 语种的「真跑配音」**（每种 1 句真合成） | 本轮只跑了 A 组（纯逻辑）⇒ **B 组要占 GPU** | 与整链臂同批跑（`diag_app118_lang10.py --live`） |
| 3 | **CUDA 档的真跑整链** | 本轮只验到「档出现 + 运行时 torch 可用」⇒ **未跑真整链** | 需在有 NVIDIA 卡的机器上跑整链（**本机就是 RTX 5050 ⇒ 可跑**） |
| 4 | **「没有 NVIDIA 卡的机器上 CUDA 档被隐藏/置灰」** | 🔴 **本机有 NVIDIA 卡** ⇒ **无法实测「无卡」形态** | 需另一台无独显的机器；本轮用**代码路径 + 判据**保证（`has_nvidia_gpu()` 为 False ⇒ 不列 CUDA 档 ＋ 状态行给出原因） |
| 5 | **EXT v0.4.18 的端到端冒烟**（真起桥接服务） | 本轮只验到**包内 import OK + 版本一致** | 起桥接服务跑一次往返 |
| 6 | **v2.5 的 zip** | 🔴 用户长期规则：**不通知 ⇒ 不打包** | 等用户通知 |
| 7 | **APP-071/075 的 F0 闸门** | 与本轮无关（克隆音色 F0 闸门是旧项） | 沿用 |
| 8 | **§214 未结项其余 3 条** | 沿用上轮 | 沿用 |

---

## §6 纪律自检（本轮）

- 🔴 **未改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占文件，只读）
- 🔴 **未改其他模块的未提交改动**（全仓脏文件数与上轮同量级，未吞 ASR/MT/TTS 的改动）
- 🔴 **未删任何客户包/zip**（旧目录旧 zip **一律保留**）
- 🔴 **未打包**（用户长期规则）
- 🔴 **未跑 MiniMax**（质量判定归 reviewer）
- 🔴 **未通知用户测试**（APP-118 §3：「验收通过前不要通知用户测试」）
- 🟢 **机器锁**：整链验收全程持 `shared/MACHINE_LOCK`（`app 9584 … app118-v25-full-zh`），
  跑完由脚本释放
- 🟢 **只改 App 模块文件**：`live_caption/{live_caption_app,device_config,package_profile,
  asr06b_stateful_backend}.py` ＋ 新增脚本/判据；**未碰 `app/asr_spk/`**（ASR 模块的）

---

## §7 接续轮（TAKEOVER，2026-11-20 18:00 → 18:2x）｜🔴 **10 语种「0/10」是假 FAIL：连修 3 处「判据自身」缺陷后才 10/10 PASS**｜🟢 **整包体积实测 24.26 GiB**｜🟢 **EXT v0.4.18 冒烟 7/7 PASS**｜🔴 **完整版出厂默认（ASR+MT+TTS 全 GPU.0）10 分钟整链仍 FAIL**

### 7.1 开工现场（TAKEOVER ⇒ 从断点继续）

- 租约：`session_lease.py acquire app` ⇒ **TAKEOVER**（上一会话 token `0745f901`，
  `last_beat 11-20 16:57:25`，**心跳超时 62 min ⇒ 已死**）⇒ 本轮**不重做**已完成的活。
- 上一会话留下的现场（**全部已落盘、可核对**）：
  v2.5 目录已建成、`ext/` 已换 v0.4.18、模型身份已核对、10 语种静态表已核、
  CUDA 档显隐已核、zh 整链臂（FAIL）、zh CUDA 整链臂（PASS）、§217 companion 初稿。
- 上一会话**死在哪**：**16:57** 的「10 语种真跑」**判为 FAIL（0/10）** ⇒ 会话即死在该处。

### 7.2 🔴 那个「0/10 FAIL」是**假 FAIL**：判据自身有 3 处缺陷（本轮逐一修掉）

| # | 缺陷 | 现象 | 真相 | 修法 |
|---|---|---|---|---|
| ① | `tts_engine.make_engine()` **没有 `voice` 参** | `TypeError: make_engine() got an unexpected keyword argument 'voice'` ⇒ 引擎**根本没建起来** ⇒ B 组 0/10 | 签名是 `(device, model_path, cache_dir, on_log, precision)`（`tts_engine.py:711`）；**音色不是引擎参数**，走 `speaker_embed`／内置 `speaker`（`tts_worker.py:1566-1626` 的 `_setup_babelvox_voice()`） | 先 `make_engine(device=…)` ⇒ `tts_engine.speaker_embedding(eng, preset_voice_path('A'))` ⇒ `tts_engine.stream(eng, text, language=…, speaker_embed=…)` |
| ② | 把**语言代号** `'zh'` 直接喂给引擎 | 日志 `Language 'zh' not recognized; … Falling back to language-agnostic mode.` ⇒ **等于没测到该语种** | 产品真实路径是 `tts_engine.map_language(lang)`（`tts_worker.py:3385`）⇒ `'zh'→'Chinese'`；babelvox 只认**英文全称** | 改走 `map_language()`；并**新增两条判据**：**B2** 引擎**不得**报任何 `not recognized`；**B3** 映射后的 id 必须都在 `SUPPORTED_LANGS` 内 |
| ③ | `translator.translate(text, tgt)` 的 `tgt` 传了**全名** | `KeyError: 'Chinese'` ⇒ C 组 0/10 | `build_messages()` 内部做 `_LANG_NAME[tgt]`（`translator.py:760-780`）⇒ `tgt` 必须是**代号** | 传代号；并把 MT 源句**固定成英文**（源语==目标语会走「同语免译」短路 ⇒ 没测到模型） |

**还改了「反证组」的判据口径**（原判据也不对）：
引擎对**未知语言**其实**会**告警并回落、**照样出声**（实测 0.96 s）⇒ 不能拿
「引擎不出声」当判据；产品真正的两道闸是 ① `map_language(lang, strict=True)` **抛错**
② `language_supported(原始 id)` = **False** ⇒ 反证组改成查这两道闸。

**最终结果**：`results/app/app118_lang10_evidence.json`（8 988 B／SHA `7ce6fa9dbed0d1b0…`
／2026-11-20 18:10:39）＝ **10 PASS / 0 FAIL**。

| 语种 | zh | en | ja | ko | de | fr | es | pt | it | ru |
|---|---|---|---|---|---|---|---|---|---|---|
| 配音时长(s) | 1.60 | 1.52 | 2.48 | 1.52 | 2.00 | 2.32 | 1.92 | 1.60 | 2.56 | 2.16 |
| RTF(集显) | 4.97 | 3.93 | 4.50 | 3.25 | 3.99 | 3.94 | 3.23 | 3.82 | 3.84 | 3.96 |

- **B 10/10 配音出声**（peak 0.3756–0.6765，**非静音**）；**B2/B3** 映射正确（**零回落**）。
- **C 10/10 字幕出译文**（`skipped=False`，逐条实测：zh「今天天气很好，我们可以去公园散步。」／
  ja「今日は天気が良く、公園で散歩に行けます。」／ko「오늘 날씨가 좋으니 공원에서 산책을 할 수 있어요.」／
  de「Das Wetter ist heute schön…」／ru「Сегодня хорошая погода…」…）。
- **D 反证组 PASS**：`map_language('xx', strict=True)` 抛错 ＋ `language_supported('xx')`=False。

🔴 **顺带查出一个「潜在风险」（本轮**不改产品代码**，登记为未结项）：
`map_language()` **非 strict** 对未知码**静默回落 English**；而 `tts_worker` 是
`map_language(lang)` **之后**才判 `language_supported(blang)` ⇒ 这道闸**抓不到**未知码。
实测未知码在**原始 id** 上判定正确（False）。⇒ 风险面＝App 只会传 `TARGETS` 里的 10 个合法码 ⇒ **不构成交付阻塞**。

### 7.3 🟢 整包体积（APP-118 §3：「报告整包体积（预计 20 GB 以上）及各部分的体积构成」）

`results/app/app118_pkg_size.json`（1 628 B／SHA `87081f0d19c101e5…`／18:03:52）：
**26 048 403 469 B ＝ 24.26 GiB／48 789 文件**

| 部分 | 字节 | GiB | 文件数 |
|---|---|---|---|
| `models/` | 20 090 013 347 | 18.71 | 170 |
| `cuda_env/` | 5 105 789 206 | 4.76 | 34 126 |
| `python/` | 842 064 347 | 0.78 | 14 046 |
| `app/` | 3 933 803 | 0.004 | 78 |
| `ext/` | 3 701 492 | 0.003 | 207 |
| 其余（`.runtime_deps`/`docs`/README 等） | < 2.5 MB | — | 162 |

⇒ **>20 GB 的预期成立**（24.26 GiB）。

### 7.4 🟢 EXT v0.4.18 冒烟（APP-118 §3：「EXT v0.4.18 冒烟一次」）

`results/app/app118_ext_smoke_evidence.json`（2 782 B／SHA `064629149952ca46…`／18:14:13）＝ **7 PASS / 0 FAIL**
（**进程级 + HTTP 级**，不是 grep）：
A1 版本一致（`version.py` 与 `manifest.json` 都是 **0.4.18**）｜A2 桥接**真能启动**｜
A3 `/health` 200+JSON｜A4 `/status` 200+JSON 且 popup 需要的字段齐全｜
A5 `/pair` 契约符合 v0.4.0（固定 `token="nopair"`）｜A6 端口被占 ⇒ **退出码 6**（不白等）｜
A7 与实时字幕 App 互斥（本机 App 未运行 ⇒ 不适用）。

- 🔴 **第一版判据自己错了 2 处**（本轮已修并如实记录）：
  ① `python ext/bridge/bridge.py` **跑不起来**（`ImportError: attempted relative import with no
  known parent package`）⇒ **必须 `-m ext.bridge`**（cwd＝包根、`PYTHONPATH`＝包根+`.runtime_deps`）
  ——这正是**产品启动器** `tools/ext_launcher.py:494` 用的那条命令；
  ② `/status` 的契约里**本来就不含版本号**（版本一致性由 A1 单独验）、`/pair` 自 **v0.4.0** 起
  **取消 token 配对**（固定 `nopair`）⇒ 原先那段 Origin 校验在 `return` **之后**＝**死代码**
  （**EXT 自己 v0.4.0 的决定，属 EXT 模块 ⇒ 本轮只记录、不改**）。
- 🔴 **口径限制（如实登记）**：本轮用 **`--echo`（回声自测）模式** ⇒ **不加载** ASR/MT/TTS 引擎
  ⇒ 零占 GPU。⇒ **`--real` 真引擎链路本轮未覆盖**（需独占 GPU 窗口）⇒ 登记为未结项。

### 7.5 🔴 完整版**出厂默认**的 10 分钟整链＝**FAIL**（承上一会话，本轮定性）

| 臂 | 包 | TTS 后端 | 结论 |
|---|---|---|---|
| zh（**出厂默认** ASR/MT/TTS 全 GPU.0） | v2.5 | OV/babelvox（集显 f32） | 🔴 **FAIL**（rc=1／`timing_valid=false`）：译文 150 ⇒ 只提交 **36** 句进 TTS；积压涨到 **917 s**；`r_recent≈4.4` ⇒ **合成跟不上** |
| zh（**CUDA 档**） | v2.5 | NVIDIA CUDA | 🟢 **PASS**（rc=0／`timing_valid=true`）：译文 **150** == 进 TTS **150**，丢弃 **0**，就绪前排队 8 → 补发 8；`speed max=1.576`；RTF P90 **0.6314**；锁全程未被抢（61 采样 0 次外来变动） |

证据：`results/app/app591_acceptance_app118_v25_zh_run20261120-162601.json`
（23 948 B／SHA `0089c6ff02efe618…`）／`…_zh_cuda_run20261120-164527.json`
（25 331 B／SHA `9dcf4498ab531afb…`）。

🔴 **定性（重要）**：查了**全部**历史 `app591_acceptance_*.json` ⇒ **之前的 10 分钟整链臂
（APP-113/114/115 那些）全部跑在 SpecialMVP sp5 上（TTS＝NPU）**，**完整版（v2.x）的 OV 整链
从来没有过一条 PASS**。⇒ **这不是 v2.5 引入的回归**，而是**完整版出厂默认
（ASR+MT+TTS 全塞 Intel 集显 GPU.0）在 10 分钟连续负载下追不上**的**既有局限**。

⚠️ **口径**：`APP-118 §1` 明文「**默认设备不变**：TTS 默认仍按当前完整版的出厂默认（OpenVINO），
CUDA 由用户手动选择。**若要改默认，先问用户**」⇒ 本轮**一个字都没改默认**。
⇒ 该局限**如实登记**，并**等用户裁定**（可选：① 完整版默认把 ASR 挪到 NPU；
② 完整版默认 TTS 改 CUDA；③ 保持现状但把 iGPU 档标成「非实时」）。

### 7.6 🟢 APP-116 §2 的最后一块：**预设 B（男声）**的 CER/WER 与抽听样本

**来源（reviewer 明文要求「写清来源模型、生成文本、参数和许可证」）**：
| 项 | 值 |
|---|---|
| 来源模型 | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`（**Apache-2.0**，HF `cardData.license`） |
| 下载 | `https://hf-mirror.com/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` |
| 生成方法 | `model.generate_custom_voice(text=…, language="Chinese", speaker="Uncle_Fu")` |
| speaker | `Uncle_Fu`（Seasoned male voice, mellow timbre）——**模型自带音色**，非真人素材 |
| 生成文本 | 「你好，这是一段用于生成预设音色的参考音频。声音清晰平稳，没有背景噪音，语速适中，像平常说话一样朗读这段文字。」 |
| 后处理 | 首尾静音裁剪（RMS < −45 dBFS）→ onset 0.52 s → 截到 **10.0 s** → 峰值归一 **−3.0 dBFS** → 去直流 → 10 ms 淡入淡出 → PCM_16 |
| 成品 | `models/qwen3tts/voices/preset_B.wav` **480 044 B / 24 kHz / 单声道 / 10.0 s / peak 0.70798 / RMS −21.69 dBFS**／SHA256 `ad8e3e80fbada9f4…` |
| 合规自检 | 24 kHz ✓／单声道 ✓／8–12 s ✓／不削波 ✓／非静音 ✓／直流小 ✓／峰值归一 ✓ ⇒ **all_checks_pass=true** |
| 真人素材 | **无**（`no_human_material=true`）：不来自录音／同事音色／克隆音色／babelvox 样本 |

**回转写对比（OV ASR `models/ov-int8-past` / GPU.0，**逐句按句 id 配对**）**：
`results/app/app116_preset_eval/preset_eval.json` →

| 音色 | CER（中文，按字） | WER（英文，按词） | 打分句数 |
|---|---|---|---|
| **A（女声）** | **0.0048** | **0.0000** | 20 |
| **B（男声）** | **0.0048** | **0.0000** | 20 |

⇒ **预设 B 与预设 A 同一水平（逐项相等）** ⇒ 满足 reviewer「与 preset_A 同一水平」的要求。
（zh 20 句里 1 句 1 个字差；en 20 句**全对**。）

**抽听样本（用户点头前不进包）**：`results/app/app116_preset_b_listen/`（4 个）

| 文件 | 句 id | 语种 | 该句 err_rate | 字节 | SHA256 |
|---|---|---|---|---|---|
| `presetB_zh_01.wav` | 1 | zh | **0.0000** | 184 364 | `851e54cc8614f373…` |
| `presetB_zh_02.wav` | 2 | zh | **0.0000** | 199 724 | `777c8fcff5175969…` |
| `presetB_en_11.wav` | 11 | en | **0.0000** | 203 564 | `deb938847ec8e89c…` |
| `presetB_en_12.wav` | 12 | en | **0.0000** | 172 844 | `adc32a37d5e764a8…` |

🔴 **`preset_B.wav` 仍**未进包**（`preset_B_manifest.json` → `not_packaged_yet=true`）
⇒ 客户包 `Confucius4_LiveCaption_v2.5/models/qwen3tts/voices/` 里**只有** `preset_A.wav`
⇒ 客户机音色下拉**不会**列出「预设 B（男声）」⇒ **等用户抽听点头**。

🔴 **本轮在这条上踩的 3 个「脚本自身」坑**（都造出假 FAIL，且都**已修**）：
1. `backends.py` 里 `import qwen_asr` ⇒ 该包在 **ASR 线程的 vendor 目录**
   （`C:\Users\Trekker-PTL\qwen3asr_06b\vendor`）⇒ 不加路径 ⇒
   `ModuleNotFoundError: No module named 'qwen_asr'`；
2. `qwen_asr` 又要 **torch** ⇒ 客户包 python **没有 torch** ⇒ 改用
   `C:\Users\Trekker-PTL\qwen3asr_06b\.venv\Scripts\python.exe`
   （torch 2.11.0+cu128 ＋ openvino 2026.4.1 ＋ soundfile ＋ transformers 全齐）；
3. 🔴🔴 **`--dump-dir` 每句会落 1～2 个文件**（主段 `seg_<id>_<seq>.wav` ＋ 变速段
   `seg_<id>_<seq>_acc110.wav`）⇒ **20 句落 30 个文件** ⇒ 旧写法
   `sorted(os.listdir())` 取 `items[i]` 会**整段错位** ⇒ 改成
   **按句 id 匹配 `seg_<id>_*.wav` 且排除 `_acc110`**，参考文本也从 worker 的
   `synth_*.jsonl` 按 id 取（不再靠手写列表）。
⇒ 另加了 `--reuse-synth`（复用已落盘的合成结果，避免重跑 6 分钟 TTS）。
