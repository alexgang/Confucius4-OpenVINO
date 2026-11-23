# ASR §95 — ASR-068（FYI）独立核实：EXT 侧 5 条修复的口径核验

> 🔴 **只读核实**（ASR-068 明写「ASR 模块本轮仍不用改交付文件」⇒ 本模块不改交付代码）。
> 🔴 **本轮未跑推理 / 未跑计时 / 未跑 WER / 未跑 Demucs 分离 / 未取 MACHINE_LOCK / 未改 4 个 ASR 交付文件 / 未改 `live_caption/` / 未改 EXT 源码 / 未打包。**
> 🔴 唯一的一次「执行」是 **CPU 单组件只读诊断**（`read_model` 读 IR 形状；`compile_model("CPU")` 只编译、**不推理**）——按纪律「CPU 只用于单组件诊断」。

---

## 0. 本轮输入与通道核对

| 项 | 值 |
|---|---|
| 纠偏文件 | `C:\Users\Trekker-PTL\confucius4-openvino\status\asr\CORRECTIONS_ASR.md` |
| 大小 / md5 / mtime | **109 822 B** / `3d25680748cf7934fe172f3bb372ec1a` / **2026-11-23 16:55**（§94 时是 107 625 B / `10e85771…` / 14:03 ⇒ **确有更新**） |
| 新条目 | **ASR-068 [FYI] 2026-11-23**（最大编号 068 ⇒ `last_ack` ASR-067 → **ASR-068**） |
| QQ 收件箱新邮件 | `msg_tHwjDsvTKlufBDo6pyhm4IB3rG6j2nvzS3L_58wMzPidDQ`（`[C4][A][CORRECTION][ASR] ASR-068`，**08:55:15Z**）—— 与纠偏文件同源、逐条对应 |
| 同批其它邮件 | `msg_kIvssywoXkD700Oy3uU4i8uBBqDjwRwpqVY1J1PsU7vbQA` = **APP-127**（HIGH，App 模块编号）⇒ 🔴 **`last_ack` 只跟 ASR-xxx 编号走，APP-127 不改本模块 `last_ack`**；`msg_W92uQ20EqJvnUY4SX28NJUiaqrbuUlwGiuqOFyfxCg76bg` = **APP-126**（App 模块）⇒ 本轮不处理 |

**ASR-068 的 5 条要点**（reviewer 自述）：① 段帧轴改用全局样本下标 `_seg_block_start`；② 单测入库 `live_dub_ext/tests/test_ext0419_bgkeep.py`（12 项）；③ 阈值同源（从 `asr052_speaker_tracker_api` 读 `DEFAULT_MIN_CLEAN_RATIO`）；④ seg IR 按 `seg_ir_subdir_for(rt.WIN_S)` 选变体 ＋ 形状守卫；⑤ `_spk_use_vocals()`（只有 `state=="ok"` 才喂人声，其余喂原声）＋ 丢块计数上报留到下一版。

---

## 1. 核实方法与边界（先说清楚「我验了什么、没验什么」）

### 1.1 ✅ 我能验的（ASR 侧交付物，本机可读）

EXT 的修复是 reviewer 在**机器 A** 上写的，**本机 `C:\Users\Trekker-PTL\live_dub_ext` 拿不到 v0.4.19 的改动**（见 §2.1）⇒ 我**不能**逐行核对 reviewer 的新代码。但 ASR-068 里的**每一条断言都引用了 ASR 侧交付物的具体接口和数值** ⇒ 这些**可以**在 A 机上只读核对，是本轮的主要核实对象：

| ASR-068 的断言 | 核验对象 | 结果 |
|---|---|---|
| ③ `DEFAULT_MIN_CLEAN_RATIO`（ASR-067 第 3 条） | `asr052_speaker_tracker_api.py` | ✅ **0.6**（L146） |
| ④ `rt.WIN_N == 80000` | `asr052_spk_runtime.WIN_N` | ✅ **80000**（`WIN_S=5.0`） |
| ④ `seg_ir_subdir_for(5.0) == 'fp16-w5'` | `asr_spk_window.py` L181 | ✅ **'fp16-w5'** |
| ④ `fp16 == [1,1,160000]` | `models/spk/pyannote_seg_3_0/fp16/*.xml` | ✅ **160000** |
| ④ `fp16-w5 == [1,1,80000]` | `models/spk/pyannote_seg_3_0/fp16-w5/*.xml` | ✅ **80000** |
| ④ `FPS`（帧轴复刻要用） | `asr_spk_window.FPS` | ✅ **58.6**（`N_FRAMES=293`） |

### 1.2 🔴 我**不能**验的（须 reviewer 在 A 机自证 ⇒ 已列入待办）

1. EXT v0.4.19 的 5 条改动**是否真的落地**（本机代码是 v0.4.18 ＋ 未提交的 v0.4.19 草稿）。
2. `tests/test_ext0419_bgkeep.py` 的 **12 项单测是否真的通过**。
3. reviewer 的实时 e2e（voice=clone）**标签是否真的产出**。

---

## 2. 逐条核实结果

### 2.1 🔴 前置事实：**v0.4.19 的 EXT 改动在本机不可见**

```
C:\Users\Trekker-PTL\live_dub_ext\git HEAD        = ee45ce5  "EXT v0.4.18: ..."
C:\Users\Trekker-PTL\live_dub_ext\ext\version.py   = EXT_VERSION = "0.4.19"   ← 已改但未提交
git status                                          = M ext/bridge.py, M ext/version.py, M extension/*, ?? ext/bg_separator.py, ?? tests/ext0419_bg_harness.js, ?? tools/bgkeep_e2e.py
git fetch github → github/live-dub-ext HEAD          = ee45ce5  (= v0.4.18)
git grep "_seg_block_start" github/live-dub-ext       = 无命中
git ls-tree github/live-dub-ext tests/ | grep 0419   = 无命中
```

⇒ 🔴 **ASR-068 的 ①②③④⑤ 全部改动**（`_seg_block_start`、`_spk_use_vocals`、`seg_ir_subdir_for`、`MIN_CLEAN_RATIO` 同源、形状守卫）在**本机工作区和已推分支上都不存在**（`grep` 全仓 0 命中）。

⇒ 🟡 **这是预期的**：ASR-068 明写「代码由 reviewer 写」「reviewer 会在 A 上跑实时 e2e，结果附在 v0.4.19 交接里」⇒ **A 机才是权威现场**。本机 `live_dub_ext` 的工作区是**共享的、reviewer 未提交的草稿**（`ext/spk_engine.py` L22–23 仍明写「**不复用** `asr052_speaker_tracker_api.SpeakerTracker`」）。

⇒ 🔴 **纪律**：`live_dub_ext` **不属于本模块**（EXT 代码由 reviewer 写）⇒ 本轮**只读不改**。

### 2.2 ✅ ① 段帧轴：**reviewer 的修法在数学上成立**，纯算术复刻如下

**复刻方法**（**不跑推理、不跑 CPU 推理**；脚本 `/tmp/asr068/probe2.py`，用 WorkBuddy python 3.13.12）：忠实复刻 EXT `spk_engine.feed` → `_advance_seg` → `_infer_seg` 的**块结构**（`STRIDE_MS=1280` ⇒ `STRIDE=20480`；`BLOCK_MIN=WIN_N+STRIDE=100480`；每块消费 `A−STRIDE`；`agg=FrameAggregator(ceil(len/SR*FPS))`），并把 ASR 侧真实常量（`WIN_N=80000`、`FPS=58.6`）灌进去。

**600 s、100 ms 喂入（= ASR-068 单测口径）**：

| 实现 | `_seg_frames` 长度 | 真值 `round(T·FPS/SR)` | 偏差 | 末帧对应时间 |
|---|---|---|---|---|
| **旧**（现状：整块帧全追加） | **43 912** | 35 160 | **+24.89 %** | 749.35 s（**偏早 149.35 s**） |
| **新**（ASR-068 ① 的公式） | **34 868** | 35 160 | **−0.83 %** | 595.02 s（偏早 4.98 s） |

- 🟢 **reviewer 声称的「原实现 +25.6 %」** ⇒ 本地独立复刻 **+24.89 %** ⇒ **量级与方向一致 ✅**（§94 记的是 +25.7 %，差异来自「末块是否计入」的取整口径，**不影响结论**）。
- 🟢 **新实现的单调性**：119 块**每块新增 293–294 帧**（理论 `consumed·FPS/SR = 293.00`），**零增长块 = 0** ⇒ 全局帧轴**严格递增、无重叠、无空洞** ✅ ⇒ 与 `on_final` 的 `round(t·FPS)`（`_seg_slice` L633–634）**同轴** ✅。
- 🟡 **新实现仍有 −0.83 % 残差（292 帧 = 4.983 s）**：来自**尾部未消费的 `STRIDE=20480`（1.28 s）** ＋ **首次块的 `WIN_N` 起步偏移**（首块要攒满 `WIN_N+STRIDE` 才起跑 ⇒ 前 5 s 无帧）。⇒ 🟡 **这 4.98 s 是「段级标签在会话开头 5 s 内不可得」的固有延迟，不影响中段对齐**（§94 的旧实现是 **+25 % ⇒ 段轴偏早 149 s**，那个是**真错位**；新实现是 **−0.8 % ⇒ 只差尾部不足 5 s**，性质完全不同）。
- 🟢 **喂入粒度无关性**：50/100/200 ms/3 s 四种粒度下 `_seg_frames` 长度分别为 34 868 / 34 868 / 34 874 / 34 909（偏差 −0.83 %～−0.71 %）⇒ **新实现不依赖喂入粒度** ✅（旧实现同样与粒度无关，但恒定 +25 %）。

### 2.3 🟡 ② 单测：**「已入库」在本机不成立**（属 A 机，待 reviewer 自证）

```
ls C:/Users/Trekker-PTL/live_dub_ext/tests/test_ext0419_bgkeep.py   → 不存在
ls tests/ | grep -i "0419|bgkeep"                                   → 仅 ext0419_bg_harness.js（JS harness，非 pytest）
git ls-tree github/live-dub-ext tests/ | grep 0419                  → 无命中
```
⇒ 🟡 本机无该文件 ⇒ **无法核对 12 项是否真的通过** ⇒ 列入待 reviewer 自证（§4）。

### 2.4 ✅ ③ 阈值同源：**ASR 侧接口完全支持**（EXT 侧改动待 A 机自证）

```
C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.5\app\asr_spk\asr052_speaker_tracker_api.py
  L146: DEFAULT_MIN_CLEAN_RATIO = 0.6        ← ASR-050 用户决定（0.8 → 0.6）
  L157: def _min_clean_ratio_from_env(default: float = DEFAULT_MIN_CLEAN_RATIO ...)
  L330–335: 环境变量未设/非法 ⇒ 回落 DEFAULT_MIN_CLEAN_RATIO（0.6）
实测 import（miniforge3 python，WorkBuddy python 无 numpy）：
  import asr052_speaker_tracker_api as A  ⇒ OK, DEFAULT_MIN_CLEAN_RATIO = 0.6
```
⇒ 🟢 **`from asr052_speaker_tracker_api import DEFAULT_MIN_CLEAN_RATIO` 这条 import 路径在包内可直接成功**（`ext/speaker_bypass.py` L202–203 已把 `<包根>/app/asr_spk` 插进 `sys.path` ⇒ import 前置条件已具备）✅。
⇒ 🟡 **但本机 `ext/spk_engine.py` L61 仍是 `MIN_CLEAN_RATIO = 0.8`（硬编码）** ⇒ ASR-068 的 ③ 同样是**待 A 机自证**。
⇒ 🟢 **本模块维持**：不在分离人声素材上重标定前，沿用 `thr=0.35` / `min_clean_ratio=0.6` / `overlap_ratio_max=0.02` 语义（ASR-021 / ASR-050 口径）。

### 2.5 ✅ ④ seg IR 变体 + 形状守卫：**ASR 侧两个变体都在，且形状与 ASR-068 声称完全一致**

**IR 形状（只读 XML，不推理）**：

| 变体 | 目录 | IR 输入形状 | 对应窗口 |
|---|---|---|---|
| `fp16` | `models/spk/pyannote_seg_3_0/fp16/pyannote_seg_3_0.xml` | **`[1,1,160000]`** | 10 s |
| `fp16-w5` | `models/spk/pyannote_seg_3_0/fp16-w5/pyannote_seg_3_0_w5.xml` | **`[1,1,80000]`** | 5 s |

**ASR 侧选型函数**：`asr_spk_window.seg_ir_subdir_for(5.0) → 'fp16-w5'`；`seg_ir_subdir_for(10.0) → 'fp16'`；未登记窗口**退回 `'fp16'`**（并由 `run_seg_side` L540–558 的形状守卫**显式抛错**，不静默）✅。

⇒ 🟢 **ASR-068 第 4 条的 4 个数字全部核实成立**：WIN_N=80000、fp16=160000、fp16-w5=80000、`seg_ir_subdir_for(5.0)='fp16-w5'` ✅。
⇒ 🟢 **ASR 侧已有形状守卫可移植**：`asr052_spk_runtime.run_seg_side`（L540–558）在编译后、推理前核对 IR 输入长度 ≠ `WIN_N` ⇒ `RuntimeError` ⇒ **EXT 直接复用该模块即自动获得守卫** ✅。
⇒ 🔴 **本轮新发现（delivery 侧，ASR-068 未提）**：**MiniMVP 包（`Confucius4_LiveCaption_MiniMVP_v1.1.1` 与 `v1.1`）的 `models/` 下**只有 `asr06b-decoder-int8` / `asr06b-encoder-fp16` / `asr06b-tokenizer` / `embed_tokens_06b_f16.npy` / `mt` / `qwen3tts` ⇒ **没有 `models/spk/`** ⇒ 🔴 **EXT 的说话人旁路在 MiniMVP 包里找不到任何 seg IR / 嵌入 IR ⇒ 旁路直接 `no_spk_ir` 降级**（`ext/speaker_bypass.py` L195–200）⇒ **「实时 e2e 确认分段标签真的产出」这条验收，在 MiniMVP 包上不可能成立**（只有 v2.5 / v2.4 全集有 `models/spk/`）⇒ **reviewer 的 e2e 须在 v2.5 全集或 A 机完整包上跑**。

### 2.6 🟡 ⑤ 缺段 / 丢块：**方向正确，但「丢块计数上报」按 ASR-068 自己说「留到下一版」⇒ 本模块记为未闭环**

- 🟢 **`_spk_use_vocals()`（只有 `state=="ok"` 才喂人声）＝ 方向正确** ✅：现状 `_bg_wants_vocals()`（`ext/bridge.py` L1886–1891）在 `sep.state=="starting"` 时返回 **True** ⇒ 原声不喂、人声也没有 ⇒ **缺一段**（§94 已记）；改成「只有 `ok` 才用人声」⇒ `starting`/`unavailable`/关闭 **都喂原声** ⇒ **轴不断** ✅。
- 🟢 **队列上限**：EXT `ext/speaker_bypass.py` L63 `DEFAULT_QUEUE_MAXSIZE = 64`；ASR-068 说「旁路队列上限 64 项」⇒ **与代码一致** ✅；🟡 但 ASR-068 同时说「人声按约 5.85 s 一项喂入」⇒ **64 × 5.85 s ≈ 374 s 缓冲**（不是 10 分钟）⇒ 🟡 「实测 10 分钟未触发丢块」与「64 项上限」只有在**大量项被及时消费**时才能同时成立 ⇒ **实际余量待 e2e 数据**。
- 🔴 **丢块计数上报＝本模块仍未闭环**：现状 EXT 只在**自己的** `stats()` 里计 `spk_queue_drop`（`ext/speaker_bypass.py` L134/L423）⇒ **不上报给 ASR 侧**；ASR 侧（App 的 `live_caption/speaker_tracker.py`）走的是**显式 `_degrade('backlog_over_limit')`**（L685/L688–693）⇒ 🔴 **两套口径不通**。ASR-068 明写「丢块上报 ASR 侧留到下一版（若你那边要求，再单开一条）」⇒ 🟢 **本轮据此单开一条待办**（§4 ①）。
- 🟡 **EXT 旁路队列的实际形态**：`ext/bg_separator.py` L242 的下行队列 `maxsize=4000`（**4000 块**，不是 64）⇒ 64 是**旁路消费队列**（`speaker_bypass`）⇒ 两者都要看，**ASR-068 只提了 64** ⇒ 🟡 建议 reviewer 明确「分离器下行队列 4000 块」的丢块语义。

---

## 3. 结论汇总（对 ASR-068 五条的判定）

| ASR-068 条目 | 判定 | 依据 |
|---|---|---|
| ① 段帧轴改全局样本下标 | ✅ **修法在数学上成立**（本地纯算术复刻：旧 +24.89 % → 新 −0.83 %，单调递增、零空洞、粒度无关）；🟡 **代码待 A 机自证** | §2.2 |
| ② 单测入库（12 项） | 🟡 **本机不存在该文件** ⇒ 只能由 reviewer 在 A 机自证 | §2.3 |
| ③ 阈值同源 | ✅ **ASR 侧接口就绪且 import 路径可用**（`DEFAULT_MIN_CLEAN_RATIO=0.6`）；🟡 本机 EXT 仍硬编码 0.8 ⇒ 待 A 机自证 | §2.4 |
| ④ seg IR 变体 + 形状守卫 | ✅ **ASR-068 的 4 个数字全部成立**；🟢 ASR 侧守卫可被 EXT 直接复用；🔴 **新发现：MiniMVP 包无 `models/spk/` ⇒ 旁路必然 `no_spk_ir` ⇒ e2e 须在 v2.5 全集跑** | §2.5 |
| ⑤ 缺段 / 丢块 | 🟢 **方向正确**（`starting` 期间喂原声）；🟡 **「丢块计数上报 ASR 侧」按 ASR-068 自述留到下一版 ⇒ 本模块记为未闭环并单开待办**；🟡 分离器下行队列 4000 项未在 ASR-068 中提及 | §2.6 |

**总体**：ASR-068 是**答复 + 安排**（FYI），**ASR 模块本轮不用改交付文件** ⇒ 本模块**不改任何交付代码** ✅。本轮的实际产出是：
1. **对 reviewer 五条断言逐条只读核实**（ASR 侧可验部分全部成立）；
2. **独立复刻并量化了旧帧轴漂移**（+24.89 % ⇒ 末帧偏早 149.35 s，600 s 口径）⇒ 与 reviewer 的 +25.6 %、§94 的 +25.7 % **三源一致**；
3. **新发现 1 条 delivery 侧问题**（MiniMVP 包无 `models/spk/` ⇒ 说话人旁路在 MiniMVP 上必然降级）⇒ 影响 reviewer 的 e2e 验收场地；
4. **单开 1 条待办**（丢块计数上报 ASR 侧）。

---

## 4. 待办（本模块**不代做**，EXT 代码由 reviewer 写）

- 🔴 **① 丢块计数上报 ASR 侧**（ASR-068 第 5 条明写「留到下一版（若你那边要求，再单开一条）」⇒ **本条即 ASR 侧的要求**）：EXT 丢块须能上报，使 ASR 侧能像 App 侧那样走 `bypass_degraded` / `_degrade('backlog_over_limit')` 口径 ⇒ **目前 EXT 只在自己的 `stats()` 里计 `spk_queue_drop`，ASR 侧看不到**。
- 🟡 **② e2e 验收场地**：§2.5 的 🔴 ⇒ **「实时 e2e 确认分段标签真的产出」必须在带 `models/spk/` 的 v2.5 全集（或 A 机完整包）上跑**；MiniMVP v1.1.1 包上说话人旁路必然 `no_spk_ir`。
- 🟡 **③ 分离器下行队列**：ASR-068 只提「旁路队列上限 64 项」，未提 `ext/bg_separator.py` 的 `maxsize=4000` ⇒ 请 reviewer 明确这两层的丢块语义与丢块后的轴处理。
- 🟡 **④ 分离人声素材**（沿用 §93/§94 未闭环）：`C:\Users\Trekker-PTL\shared\bgkeep\vocals/` **实测不存在** ⇒ 本模块的「原声 vs 分离人声 WER 对比」继续等（🔴 两侧须同一 ASR 臂 `pml=320` NPU 档 ＋ OV **2026.4.1**；**本模块不自己调 MiniMax**）。

---

## 5. 本轮动作边界（纪律自证）

- ✅ **做了**：读纠偏文件（109 822 B / md5 `3d256807…`）、读 STATUS（35 824 B / 125 行）、读 QQ 收件箱（`ASR-068` ＋ `APP-127` ＋ `APP-126`）、**纯算术探针**（`/tmp/asr068/probe{,2,3,4}.py`，WorkBuddy python 3.13.12，**不跑推理**）、**IR 只读形状核对**（读 XML ＋ `read_model`/`compile_model("CPU")` 只编译不推理）、ASR 侧模块 import 核对（miniforge3 python）。
- 🔴 **没做**：未跑 ASR 推理 / 未跑 NPU·GPU 计时 / 未跑 WER / 未跑 Demucs 分离 / **未取 MACHINE_LOCK** / 未改 4 个 ASR 交付文件（`asr06b_stateful_backend.py` 等 md5 一字未动）/ 未改 `live_caption/`（C-111 已移交 App）/ **未改 EXT 源码**（`live_dub_ext` 只读）/ 未改纠偏文件（除追加 ASR-068 条目，reviewer 写入）/ 未改旧章节（§94 已逐字归档）/ **未打包**（用户未要求 ⇒ 不主动打包）。
- 📦 **产物**：`status/asr/notes/asr_s95.md`（本文件）＋ `status/asr/STATUS_ASR.md` §95（＋ `status/archive/STATUS_ASR_sec94_upto_20261123.md`）。
