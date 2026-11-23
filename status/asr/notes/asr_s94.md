# ASR §94 — ASR-067（FYI）独立核实：reviewer 对 §93 三条契约风险的答复，逐条比对结果

> 日期：2026-11-23 16:15–16:30（本轮）
> 触发：`status/asr/CORRECTIONS_ASR.md` 新增 **ASR-067 [FYI] 2026-11-23**（md5 `10e857710c2d674ece2d973e2caaa253` / 107 625 B / mtime 2026-11-23 14:03）＋ QQ 收件箱新邮件 `msg_J3FGr-WPFnLn21gdfCwrXaRR0FQdDJGvTUAMwpMVq2d-kA`（`[CORRECTION][ASR] ASR-067`，created_at 2026-11-23T06:03:56Z）。
> 本轮动作：**只读核实**（未跑推理、未跑计时、未取 MACHINE_LOCK、未改交付文件、未打包、未动 `live_caption/`、未改纠偏文件）。

---

## 0. 一句话结论

**ASR-067 的 4 条答复中，1 条成立、2 条部分成立但有**未标注的**硬缺口、1 条与代码不符。**
最重的一条：reviewer 称「风险①（时间轴）已在 bridge 里处理」——🔴 **该处理只解决了「喂入样本下标连续」，没有解决「旁路分段帧轴与全局时间轴同轴」**；而旁路分段帧轴（EXT 自研 `ext/spk_engine.py`）在 600 s 素材上**实测漂移 123.2 s**（纯算术复刻，见 §2.1）。

---

## 1. 本轮核实的方法与边界

- 🔴 **只读 + 纯算术/纯 CPU 单组件诊断**：
  - 读代码：`live_dub_ext/ext/bridge.py`、`ext/spk_engine.py`、`ext/speaker_bypass.py`、`ext/bg_separator.py`、`extension/player.js`、`extension/capture-worklet.js`；
  - 读 ASR 交付：`qwen3asr_06b/scripts/asr052_speaker_tracker_api.py`、`asr052_spk_runtime.py`、`asr_spk_window.py`、`asr_thread_defaults.py`（**4 文件 md5：61be393c…／2ff82933…／0482f9c4…／7d719e1d…**）；
  - 读包内实际 IR（`ov.Core().read_model` **只读形状**，不编译不推理）：`Confucius4_LiveCaption_v2.5/models/spk/pyannote_seg_3_0/`；
  - 纯算术复刻（**不跑推理**）：帧轴探针 `_advance_seg`/`_infer_seg`/`FrameAggregator` 的**帧数与索引**；
  - 🔴 **单组件 CPU 诊断**（允许：CPU 只用于单组件诊断）：`compile_model(..., "CPU")` 后喂**形状不符**的输入 ⇒ OpenVINO 在计算前抛错，**未产生实际推理结果**。
- 🔴 **未跑**：ASR 推理、NPU/GPU 计时、WER/MiniMax、Demucs 分离、未取 MACHINE_LOCK。
- 🔴 **未改**：`asr052_*` 4 个交付文件一行未动、`live_caption/` 一行未动、EXT 源码一行未动（**EXT 代码由 reviewer 写，ASR 侧不改**）。

---

## 2. 逐条核实

### 2.1 🔴 风险①（时间轴）——reviewer 称「已在 bridge 里处理」：**只对了一半**

reviewer 的处理（`ext/bridge.py` L1943–1963 `Session._spk_feed(arr, start_idx)`）确实做到了：
- 维护「已喂到的 16 kHz 样本下标」`_spk_fed_until`；
- 换源时**缺口补静音、重叠截掉** ⇒ **喂入侧**的样本下标连续、不断轴。✅ **这一点成立。**

🔴 **但它没有解决真正出问题的那个轴：旁路「分段帧」的全局帧轴。**
- ASR 交付的 `SpeakerTracker`（`asr052_speaker_tracker_api.py` L393–398 `on_final` → L601–602 `_seg_slice`）**用 `i0/i1 = round(t×FPS)`** 直接按**全局时间**取帧 ⇒ 帧列表必须与全局时间轴严格同轴。
- EXT **没有复用** ASR 的 `SpeakerTracker`（`ext/spk_engine.py` 文档串明写「**不复用** `asr052_speaker_tracker_api.SpeakerTracker`」），而是**自研**了 `_advance_seg` + `_infer_seg`（`ext/spk_engine.py` L338–360、L366–410）。
- 🔴 **自研实现的帧轴与全局时间轴不同轴**：
  - `_advance_seg` 每块的 audio 长度 = `WIN_N + STRIDE`（`L342` 阈值 `self._block_min = rt.WIN_N + self._seg_stride_samples`，L219/L234），**但消费时只消费 `A − KEEP`**（`L357–360`，`KEEP = STRIDE`）⇒ 每块都会把**重叠的 STRIDE 部分重复计入帧数**；
  - `_infer_seg` 里 `agg = rt.FrameAggregator(ceil(len(audio)/SR*FPS))`（L369）**每块都从帧 0 起算**，块的全局偏移**没有被加到 `add_window` 的 base 上** ⇒ 拼接后帧总数远超真实帧数。
  - 🔴 **纯算术复刻实测（600 s / 16 kHz，`FPS=58.6`、`WIN_N=80000`、`STRIDE=20480`）**：
    | 量 | 值 |
    |---|---|
    | 拼接后帧数 | **44 204** |
    | 真实总帧数 `ceil(600×58.6)` | **35 160** |
    | 超额 | **+9 044 帧（+25.7 %）** |
    | 末帧（t=599 s）错位 | **读到的是 475.8 s 的音频 ⇒ 偏早 123.2 s** |
  - ⇒ 也就是说：**t=30 s 的定稿段**在 EXT 旁路里读到的是 **24.8 s** 的音频（偏早 5.2 s）；**t=120 s** 读到 **95.4 s**（偏早 24.6 s）；**t=599 s** 读到 **475.8 s**（偏早 **123.2 s**）。
  - ⇒ 🔴 **`_seg_frames` 与 `_archive` 的索引基准不同**（前者按拼接顺序、后者按全局样本），⇒ **`clean_ratio` / `overlap_ratio` 系统性算错、`_seg_slice` 取到错误时刻的帧**。
  - 🟡 **对照：ASR 交付 tracker 的帧轴漂移很小**（同样纯算术复刻，600 s ⇒ 最大 **134.11 帧 = 2.289 s**，且只在小块边界出现）⇒ **EXT 自研内核比 ASR 交付内核更不准**。

🟢 **风险①的另一半成立**：人声比原声晚 8–9 s 到达**只影响标签到达时间**、不改变样本下标（`_spk_feed` 用 `start_idx` 换算）——✅ 这句 reviewer 说对了。

### 2.2 🟡 风险②（阈值按原声标定）——reviewer 同意需重标定：**成立，但 EXT 当前用的值与 ASR 交付不同源**

- ✅ reviewer 同意 `thr=0.35` / `min_clean_ratio=0.6` 按原声标定、换分离人声须重标定 —— **本模块同意，本轮不改**。
- 🔴 **但发现一处同源性问题**：EXT 的 `ext/spk_engine.py` L61 写死 `MIN_CLEAN_RATIO = 0.8`（注释还写「与 ASR 侧默认 `min_clean_ratio=0.8` 一致」），而 **ASR 交付** 的 `asr052_speaker_tracker_api.py` L146 `DEFAULT_MIN_CLEAN_RATIO = 0.6`（**ASR-050 用户决定 0.8→0.6**）⇒ **两处默认值不同源、且差 0.2**。⇒ 这正好说明「阈值必须同源」这件事在代码层还没落地。
- 🟢 `overlap_ratio_max=0.02` 语义仍成立（判「多人重叠」，分离人声保留多人重叠人声）——**本模块维持此口径**。

### 2.3 🟡 风险③（分离不可用时退回原声）——reviewer 称「确认」：**部分成立，但门控方向与「立即」二字有出入**

- ✅ 成立部分：`ext/bridge.py` L1885–1891 `_bg_wants_vocals()` 在 `self._bg_fail` 非空时返回 `False`；L1880 `_bg_fail` 由「插件没上传立体声上行」触发（L2179–2183 `_bg_fail = "插件没有上传立体声原声（pcm_bg）"`）⇒ **分离器不可用 ⇒ 旁路退回喂原声**，走**同一个 `_spk_feed`** ⇒ 时间轴不断。✅
- 🟢 也成立：`ext/bg_separator.py` `_fail()` L296–299 置 `state="unavailable"` ⇒ `_bg_wants_vocals()` 返回 `False` ⇒ 退回原声。✅
- 🟡 **口径出入**：`_bg_wants_vocals()` 在 **`sep.state == "starting"`** 时返回 **True**（L1891 `return sep is None or sep.state in ("starting","ok")`）⇒ **分离器还没就绪的那段原声**既不喂旁路、也还没有人声 ⇒ **旁路这段音频直接缺一段**（不是"退回喂原声"）。⇒ 🔴 **「立即退回」不成立**；实际是「**等分离器就绪；就绪失败才退回**」。
- 🟡 「不会置 degraded」：EXT 侧确实**没有** `bypass_degraded` 逻辑（该逻辑在 App 的 `live_caption/speaker_tracker.py` L688–693，不在 EXT 的 `ext/speaker_bypass.py`）⇒ ✅ 成立（EXT 队列满只丢旧块计数 `spk_queue_drop`，不置降级）。
- 🔴 **新发现的风险（不在 §93 三条之内）**：EXT 的队列满时**丢最旧的块**（`ext/speaker_bypass.py` L260–270）⇒ **丢掉的音频块会让 `_spk_feed` 的「已喂下标」与实际音频脱节** ⇒ 后续块会被判为「重叠」而截掉（`_spk_feed` 的 `gap < 0` 分支）⇒ **旁路音频整段错位**，且**没有任何计数暴露给 ASR 侧**（只有 `spk_queue_drop`）。⇒ 与 ASR 交付 `speaker_tracker.py` 的 `_degrade('backlog_over_limit')` 相比，EXT 是「**静默丢块**」而不是「显式降级」。

### 2.4 🟢 风险②附带：分离人声素材 —— reviewer 说「v0.4.19 合入后 reviewer 会放到 `shared\bgkeep\vocals\`」

- 🔴 **本轮实测：目录仍不存在**（`C:/Users/Trekker-PTL/shared/bgkeep/vocals/` ⇒ `No such file or directory`）。
- ⇒ 🟡 **本模块的「原声 vs 分离人声 WER 对比」仍等素材**（材料/工具已齐备，见 §93 ⑥）。

---

## 3. 🔴 本轮新发现的第 4 条契约风险（不在 §93/ASR-067 之内）：EXT 旁路的 seg IR 与窗口**不配套** ⇒ 分段整条失效

- ASR 交付默认窗口 `asr_spk_window.WIN_S_DEFAULT = 5.0` ⇒ `WIN_N = 80000` ⇒ ASR 侧按窗口选 IR 变体 `seg_ir_subdir_for(5.0) = 'fp16-w5'`（`asr_spk_window.py` L175–187）。
- 🔴 **EXT 的 `ext/speaker_bypass.py` L168–180 `_asset_paths()` 只探测 `("fp32","fp16")` 两个精度目录** ⇒ **探不到 `fp16-w5`** ⇒ 在 `Confucius4_LiveCaption_v2.5` 里命中的是 `models/spk/pyannote_seg_3_0/fp16/pyannote_seg_3_0.xml`。
- 🔴 **形状实测（`ov.Core().read_model`，只读）**：
  | IR | 输入形状 |
  |---|---|
  | `fp16/pyannote_seg_3_0.xml`（EXT 实际命中） | `[1, 1, 160000]`（= 10 s 窗） |
  | `fp16-w5/pyannote_seg_3_0_w5.xml`（ASR 5 s 窗应配） | `[1, 1, 80000]` |
- 🔴 **CPU 单组件诊断**（`compile_model(..., "CPU")` 后喂形状不符输入，OpenVINO 在计算前抛错，**未产生推理结果**）：
  - `WIN_N=80000` ⇒ **抛错**（`Exception from src\inference\src\cpp\infer_request.cpp:113`）
  - `WIN_N=160000` ⇒ infer OK
- 🔴 **且 EXT 的 `ext/spk_engine.py` 没有 ASR 侧的形状守卫**（ASR 侧 `asr052_spk_runtime.run_seg_side` L540–558 有显式 `RuntimeError` 守卫 + 提示）⇒ EXT 会**静默失败** ⇒ `_advance_seg` 捕获异常 ⇒ `self._seg_ready = False` ⇒ **旁路全程零标签**（不是精度下降）。
- 🔴 **补充**：EXT 也没有设置 `ASR_SPK_WINDOW_S`（全仓 grep 无命中）⇒ 窗口长只能取 ASR 默认 **5.0 s** ⇒ **窗口与 IR 必然不配套**。
- ⇒ 🟡 **这解释了 EXT 侧为什么可能一直「标签不准/没标签」**：不是阈值问题，是**分段根本没跑起来**。

---

## 4. 🔴 结论与处置建议（ASR 侧）

| # | ASR-067 的说法 | 核实结论 | ASR 侧处置 |
|---|---|---|---|
| ① | 风险①（时间轴）已在 bridge 里处理 | 🟡 **部分成立**：喂入下标连续 ✅；**分段帧轴与全局时间轴不同轴 ❌**（600 s 漂移 123.2 s） | **要求 EXT 修帧轴**：`_infer_seg` 的 `add_window` 必须带**全局帧偏移**（或复用 ASR 的 `FrameAggregator` 口径），并补一个**累积样本数与 `t_end` 精确吻合**的单测（reviewer 在 ASR-067 里已承诺要写，但**本轮 `live_dub_ext/tests/` 下 grep `_spk_feed` 无命中 ⇒ 该单测尚不存在**） |
| ② | 风险③ 确认：分离不可用 → 退回原声 | 🟡 **部分成立**：失败态退回 ✅；**`starting` 态既不喂原声也无人声 ⇒ 缺一段 ❌**；EXT 队列满**静默丢块**（ASR 侧是显式 `_degrade`） | **要求**：① `starting` 期间也喂原声（保证连续）；② 丢块计数**上报给 ASR 侧**或至少不让 `_spk_feed` 误判重叠 |
| ③ | 风险② 同意需重标定 | ✅ **成立**；🔴 另发现 **EXT `MIN_CLEAN_RATIO=0.8` vs ASR `DEFAULT_MIN_CLEAN_RATIO=0.6` 不同源** | **要求同源**：EXT 的阈值从 ASR 侧常量读（ASR 侧已提供 `DEFAULT_MIN_CLEAN_RATIO` 的同源读取范式，`live_caption/speaker_tracker.py` L212–269） |
| ④ | v0.4.19 合入后提供分离人声到 `shared/bgkeep/vocals/` | 🟡 **仍待提供**（目录实测不存在） | **等素材**；拿到后本模块做「原声 vs 分离人声」WER 对比（**同一 ASR 臂：`pml=320` NPU 档 ＋ OV 2026.4.1；本模块不自己调 MiniMax**） |
| ⑤（新增） | （不在 ASR-067 内） | 🔴 **EXT 探测的 seg IR 是 10 s 静态 IR，而 EXT 喂的是 5 s 窗口（80000 样本）⇒ 形状不符 ⇒ 旁路分段全程失效** | **要求 EXT 按 ASR 的 `seg_ir_subdir_for(WIN_S)` 选变体**（或设 `EXT_SPK_SEG_IR` 指向 `fp16-w5`）＋ 移植 ASR 侧形状守卫 |

🔴 **本模块不改任何交付文件**（ASR-067 明写「本条只是答复与安排，ASR 模块本轮不用改交付文件」；且 EXT 代码由 reviewer 写，ASR 侧不代改）⇒ **本轮产出 = 一份核实结论 ＋ 一封给 reviewer 的 STATUS 邮件**。

---

## 5. 本轮产物与边界

- 🟢 **产物**：`status/asr/notes/asr_s94.md`（本文件）＋ `status/asr/STATUS_ASR.md` §94 ＋ `status/archive/STATUS_ASR_sec93_upto_20261123.md`（§93 全文归档）＋ `status/asr/STATUS_ASR.md.bak_asr094`（基线备份）。
- 🔴 **边界**：未跑推理/计时/WER/分离器、未取 MACHINE_LOCK、未改 4 个 ASR 交付文件、未改 `live_caption/`、未改 EXT 源码、未改纠偏文件、未改旧章节（§93 逐字归档）、未打包、未代做 App/reviewer 作业。
- 🔴 **口径**：`last_ack` 由 **ASR-066 → ASR-067**（本轮已读 ASR-067）。
