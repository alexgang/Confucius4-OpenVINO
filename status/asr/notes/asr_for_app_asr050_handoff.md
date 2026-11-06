# ASR-050 交接清单：`min_clean_ratio` 默认值 0.8 → 0.6（给 App）

> 供 **App 线程**（`APP-071` / `APP-076`）同步客户包用。ASR 只交文件与口径，**是否采用由 App 决定**。
> 明细：`status/asr/notes/asr_s76.md`（长文）、`status/asr/notes/asr_for_app_spk_enroll.md`（单页登记说明）。

## ① 改了什么（ASR 侧只改了这一个默认值，其它参数一律不动）

| 项 | 改前 | 改后 |
|---|---|---|
| `min_clean_ratio`（说话人旁路「段内干净语音占比」下限） | 0.8 | **0.6** |
| 步长 `stride_ms` / chunk | 0.64 s | **0.64 s（未动）** |
| VAD 门控 | 关闭 | **关闭（未动）** |
| 旁路窗口 | 5 s | **5 s（未动）** |
| `thr` | 0.35 | **0.35（未动）** |
| `overlap_ratio_max` | 0.02 | **0.02（未动，且是惰性参数）** |
| `min_dur_s` | 2.0 | **2.0（未动）** |

## ② 改了哪个文件、哪一行

**交付文件（App 实际 import 的那个）**：`qwen3asr_06b/scripts/asr052_speaker_tracker_api.py`
md5 `61be393ce6343bfa63892ce0c35f5c44`（33478 B，644 行）

| 行号 | 内容 | 说明 |
|---|---|---|
| **146** | `DEFAULT_MIN_CLEAN_RATIO = 0.6` | 🟢 **单一事实来源**（新增） |
| **149** | `MIN_CLEAN_RATIO_ENV = 'ASR_SPK_MIN_CLEAN_RATIO'` | 🟢 **环境变量名**（新增） |
| **152–173** | `_min_clean_ratio_from_env(default=DEFAULT_MIN_CLEAN_RATIO)` | 🟢 **环境变量读取**（新增；非法值退回默认） |
| **279–301** | `SpeakerTracker` docstring「🔴🔴 门槛参数（配置说明，ASR-050）」表 | 🟢 **③ 配置说明**（新增） |
| **308** | `min_clean_ratio: float = 0.6` | 🟢 **① 代码默认值**（`__init__` 签名） |
| **319–333** | 取值优先级逻辑 | 🟢 显式非默认值 → env → `DEFAULT_MIN_CLEAN_RATIO` |
| **114–142** | 顶部注释块（ASR-050 依据 + 措辞纪律） | 🟢 新增 |

**legacy 文件（非交付、非被 import，只为同语义一致）**：`qwen3asr_06b/scripts/asr_speaker_tracker.py`
md5 `5c1e6738f24f10fedd11441606b0f9c6`（17691 B）— 第 **129** 行 `clean_ratio_min: float = 0.6`（原 0.8）。

**未改动**：`asr052_spk_runtime.py`（md5 `2ff82933edec80becd01f9d28d202ea6`）、`asr_thread_defaults.py`（`0482f9c49105490ac219194c2fa7c184`）、`asr_spk_window.py`（`7d719e1d7f251be9ce68503be4361807`）、`asr_runtime_switches.py`（`7f12e9a5575d7a88cafcd3f54689e326`）——**md5 与上一轮一致，App 侧若已同步这 4 个则无需再动**。

## ③ 「三处一致」的口径（ASR-050 第 1 条）

1. **代码默认值**：`asr052_speaker_tracker_api.py:308` = `0.6`
2. **环境变量开关的默认值**：`ASR_SPK_MIN_CLEAN_RATIO` 未设/非法 ⇒ 退回 `DEFAULT_MIN_CLEAN_RATIO`（**0.6**，唯一一份默认值，**不写第二份**）
3. **配置说明**：`asr052_speaker_tracker_api.py` 的 docstring 门槛参数表（:279–301）

🔴 **取值优先级**：显式传**非默认值** ⇒ 用传入值（评测脚本 A/B 口径覆盖仍有效）；否则 ⇒ 环境变量；再否则 ⇒ `DEFAULT_MIN_CLEAN_RATIO`。
⚠️ **副作用**：若运维**显式设了** `ASR_SPK_MIN_CLEAN_RATIO`，则「显式传 0.6」也会被 env 覆盖（0.6 == 代码默认值 ⇒ 视为未覆盖）。

🔴🔴 **跨模块陷阱（App 侧必须知道）**：App 的 `results/app/app193_app053_spk_frame_audit.py` 的 `read_asr_gates()` 用**正则从 ASR 源码现读门槛默认值**（`re.search` 取**第一个**匹配）
⇒ **ASR 源码里 `min_clean_ratio` 后面跟数字的第一个出现，必须是 `__init__` 的真实默认值**
⇒ **App 侧不能自己在源码注释里写「`min_clean_ratio` = 0.8」之类的字样**（会被当成默认值读走 ⇒ 静默漂移）。
🔴 App 侧环境变量同义名是 `LIVECAP_SPK_MIN_CLEAN_RATIO`（**由 App 自己实现**，但**默认值必须来自 ASR 的 `DEFAULT_MIN_CLEAN_RATIO`** ⇒ 不互相 import）。

## ④ App 要同步哪些文件进 v2.3 和 MiniMVP 下一版

**必须同步（ASR 侧已改）**：

| 文件 | 源 | md5 | 说明 |
|---|---|---|---|
| `asr052_speaker_tracker_api.py` | `qwen3asr_06b/scripts/` | `61be393ce6343bfa63892ce0c35f5c44` | 🔴 **本轮唯一实质改动** |

**必须补进包（此前一直没进包，ASR-045/046/047 遗留项）**：

| 文件 | 源 | md5 | 现状（实测） |
|---|---|---|---|
| `asr_spk_window.py` | `qwen3asr_06b/scripts/` | `7d719e1d7f251be9ce68503be4361807` | 🔴 **4 个包全盘 `find` 命中 0** |
| `asr_runtime_switches.py` | `qwen3asr_06b/scripts/` | `7f12e9a5575d7a88cafcd3f54689e326` | 🔴 **不在任何包内**；且 `live_caption/sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 实测**只有 4 项** ⇒ 确无此文件 |

**已在包内、无需重复同步（实测 v2.2 `app/asr_spk/`）**：`asr052_speaker_tracker_api.py`、`asr052_spk_runtime.py`、`asr_thread_defaults.py`。

**还需 App 落地的资产**：`models/spk/pyannote_seg_3_0/fp16-w5/`（5 s **静态** seg IR，xml md5 `14b224bced3289237799bc9a7eb746ff`）——实测 4 个包 `models/spk/pyannote_seg_3_0/` 下**只有 `fp16`、无 `fp16-w5`**。
**并把 `sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` 从 4 项补到 6 项**（加 `asr_runtime_switches.py`；`asr_spk_window.py` 已在列表内）。

## ⑤ 回归结果（ASR 侧实测，ASR-050 第 2 条）

900 s 评测集（3 clip / 136 段 / 26 换人点），用**代码默认值 0.6** 重跑：

| 口径 | asr118 `B_min_clean_ratio_0.6`（基准臂） | asr122（本轮重跑，代码默认值） | 一致 |
|---|---|---|---|
| 命中 / 参照换人点 | 22 / 26 | **22 / 26** | ✅ |
| recall | 0.8462 | **0.8462** | ✅ |
| 误报 `n_false_positive` | 3 | **3** | ✅ |
| 无标签段 | 5 | **5** | ✅ |
| clip00 recall / fp / unlabeled | 0.8333333333333334 / 0 / 2 | 同 | ✅ |
| clip01 recall / fp / unlabeled | 0.8571428571428571 / 3 / 1 | 同 | ✅ |
| clip02 recall / fp / unlabeled | 0.8571428571428571 / 0 / 2 | 同 | ✅ |

🔴 **主路隔离（ASR WER 不受影响的依据）**：静态 import 图证明主路（`streaming_asr.py` / `segment_encoder_backend.py` / `seg_stream.py` / `window_encoder_backend.py`）**零说话人旁路 import** ⇒ 本次改动**不可能**改主路行为；主路转写文本逐段逐字一致（5 分钟切片，`final_text` md5 `32c556292a052cabe1fcfabfd62597c7`）。
⚠️ **WER 数值仍交 reviewer 用 MiniMax 判定**（本模块不产出 WER，铁律）。
🔴 **`spk` ID 是到达序编号，不是人的身份** ⇒ 0.6 臂与基线臂的 ID 顺序会平移（实测 clip02 逐段 diff 32/46）⇒ 比较时**必须按最优映射对齐**（ASR-050 第 2 条）。

## ⑥ 产品后果（务必转达给 App）

🔴 **标签变多 ≠ 这段可以拿来登记克隆音色**：门槛放宽到 0.6 ⇒ 更多**短的、不太干净的**片段会带上标签
⇒ **登记仍然按 App 的 `REG_CONF_MIN` / 干净连续 ≥2.5 s 规则**（`APP-075`）。
⚠️ 另外：`overlap_ratio_max` 是**惰性参数（永不触发）** ⇒ **重叠语音帧没有被排除出 `clean_ranges`** ⇒ `clean_ranges` **不保证单人** ⇒ **不要把它当作防护**（修复属新开发量，**待用户决定，ASR 未自行改**）。

## ⑦ 已知风险（ASR-051，2026-11-06 22:24）：污染比例未在真实切段下测过

🔴 **已知风险**：`asr125` / `asr126` 报的「污染 = 0.0」只在**评测集口径**成立；**污染比例未在真实管线切段（生产口径）下测过** ⇒ 不得据此推断生产环境无污染。ASR 线程按 ASR-051 第 1 条退路**未做新实验**（不重跑 900 s 长推理）。
- 产物 `asr127_asr051_prod_contam_scope.json`（11516 B @ 11-06 22:14，`self_check_pass=true` / 10/10）；结论字段 `verdict.obtainable_from_existing_artifacts=false`、`production_contamination_ratio=null`、`reason_code=SEGMENT_LEVEL_SINGLE_LABEL_TRUTH_CANNOT_EXPRESS_INTRA_SEGMENT_MIXING`。
- 原因 ①：ASR-028 真值 **207** 段与真实切段 `segs.json` **207** 段**逐段同源**（`n_start_exact=207/207`，+2280 s 平移）⇒ 不存在「人工段界 vs 生产切段」两套段界。
- 原因 ②：段级单标签真值 **29/29** 换人点全在段界（`n_inside_segment=0`）、3 clip **133/133** 段连续 ⇒ 真值**结构上表达不了**「段内混入上一人」。
- 原因 ③：`asr125` 首次登记段 **11/11** 的 `clean_ranges` 是段尾借用 **2.5 s** 窗口，非生产段自身整段；`segs.json` 无 `clean_ranges` 字段。
- 原因 ④：全片帧缓存 `frames.npz` 是 **10 s** 窗（81942 帧 / 58.900695735805854 fps），交付为 **5 s** 窗（58.6 fps）⇒ 帧轴不可混用（末尾漂移 418 帧 ≈ 7.133 s）。
- ✅ `asr125` / `asr126` 的 0 与 STATUS §77「不可外推到生产」限定**保留不撤回**（ASR-051 第 1 条）；§77 推荐方案 B 仍按**定性结论**读。
- ⚠️ 第 ④ 节「必须补进包」的文件属 **App 侧事项**，ASR 线程**未自行改包**（ASR-051 第 2 条）。
