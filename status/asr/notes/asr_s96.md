# §96 — 巡检 ＋ 首次「EXT v0.4.19 已在本机落地」的独立核实（2026-11-23 18:56–19:20）

> 🔴 **本轮性质**：纠偏通道**无新条目**（`last_ack` 保持 **ASR-068**）⇒ 按纪律**不新增待办、不改交付文件**。
> 但 🔴 **reviewer 的 EXT v0.4.19 代码在本轮已落地本机**（`live_dub_ext` HEAD `5121d99`，工作区干净）⇒ **§95 的「待 A 机自证」3 项现在可在本机只读核实** ⇒ 本轮把这些项做掉了，并**发现 2 条新缺陷**。

---

## 0. 前置事实（与 §95 的差异）

| 项 | §95（17:50） | 本轮（18:56） |
|---|---|---|
| `live_dub_ext` HEAD | `ee45ce5`（v0.4.18）＋ 未提交草稿 | **`5121d99`（v0.4.19，已提交）** |
| `tests/test_ext0419_bgkeep.py` | 不存在 | **存在**（5 134 B，mtime 11-23 16:53） |
| `git grep _seg_block_start` | 0 命中 | **有命中**（`ext/spk_engine.py` L170/380/385） |

⇒ 🔴 **§95 的 ⓪ 前置事实「A 机才是权威现场」在本轮不再成立**（EXT 代码已同步到本机，且 commit 已被 App 线程记入 `5f4d1c0`）。

---

## 1. 纠偏通道与邮件（只读）

- `CORRECTIONS_ASR.md`：**109 822 B** / md5 **`3d25680748cf7934fe172f3bb372ec1a`** / mtime **2026-11-23 16:55:15** ⇒ 与 §95 读到的**逐字相同**（**未再更新**）。
- `## ASR-` 标题共 **38 个**，最大编号 **ASR-068**；搜 `ASR-069` / `ASR-070` → **0 命中**；文件尾即 ASR-068 正文（无未加标题的追加条目）。
- ⇒ **`last_ack` 保持 `ASR-068`**（同批 APP-127 / APP-126 是 **App 模块编号**，按口径不改本模块 `last_ack`）。
- 邮件（qq-mail MCP，只读）：inbox 最新 3 封 = **APP-127**（08:55:39Z）／**ASR-068**（08:55:15Z）／**APP-126**（08:55:11Z）⇒ 搜 `ASR` 标题（after 08:55:00Z）**唯一命中 ASR-068**（已读、已落地）⇒ **无新 reviewer ASR 邮件**；spam **0 封**；trash **1 封**（11-13 rc9 性能报告，非纠偏）。

---

## 2. §95 三项「待 A 机自证」的逐项核实（只读 ＋ 跑现成单测）

### ② 单测 12 项 → ✅ **本机实测 12/12 PASS**

```
$ cd C:\Users\Trekker-PTL\live_dub_ext
$ C:\Users\Trekker-PTL\miniforge3\python.exe tests/test_ext0419_bgkeep.py
  [PASS] samples fed == timeline length
  [PASS] t_end of last feed == 0.5 s
  [PASS] starting: speaker path uses the original
  [PASS] running: speaker path uses vocals
  [PASS] unavailable: back to the original
  [PASS] onset = speech (14.75 s), not the burst (11.0 s)
  [PASS] no speech in the segment ⇒ unchanged
  [PASS] no vocals yet ⇒ nothing sent, kept pending, returns at once
  [PASS] vocals arrived ⇒ dub_shift with the onset
  [PASS] too late ⇒ dropped, no message
  [PASS] frames == round(consumed·FPS/SR) (no overlap double-count)
  [PASS] consumed covers the session minus one window
RESULT: PASS (12/12)
```

⇒ ✅ **ASR-068 第 2 条「单测已入库（12 项）」成立**（§95 记的「本机不存在」是**当时**的事实，现已过时）。

### ③ 阈值同源 → ✅ **成立**

`ext/spk_engine.py` L60–65：

```python
try:
    from asr052_speaker_tracker_api import DEFAULT_MIN_CLEAN_RATIO as MIN_CLEAN_RATIO
except Exception:
    MIN_CLEAN_RATIO = 0.6
```

实测（`app/asr_spk` 在 `sys.path` 上时）：

```
spk_engine.MIN_CLEAN_RATIO = 0.6
ASR source DEFAULT_MIN_CLEAN_RATIO = 0.6
=> same-source? True
```

⇒ ✅ **ASR-068 第 3 条成立**（§95 记的「本机 EXT 仍硬编码 0.8」已过时）。

### ① 段帧轴 → ✅ **代码与 ASR-068 描述一致**（§95 已用纯算术证明修法成立，本轮只读确认代码已落地）

`ext/spk_engine.py` L170 `_seg_block_start = 0`（注释「global sample index of `_pending[0]`（frame-axis anchor）」）；L380–385 用 `bs_f = self._seg_block_start / SR * FPS`、`want_end = round((self._seg_block_start + consumed) / SR * FPS)`、L385 `self._seg_block_start += consumed` ⇒ 与 ASR-068 第 1 条**逐字对应**。

---

## 3. 🔴🔴 新发现（2 条，均为真缺陷；本模块**只读不改**，EXT 代码由 reviewer 写）

### 🔴 发现 A：**reviewer 的 e2e 从未启用说话人旁路 ⇒「实时 e2e 确认分段标签真的产出」这条验收根本没被执行**

- **证据 1（启动参数）**：`shared/bgkeep/run_bgkeep_v3.ps1` / `v4` / `v5` / `v5_app` / `v5_app_arm` **5 个启动脚本全部**用同一行启动 bridge：

  ```
  -m ext.bridge --real --pipeline --port 8765 --delay 20 --target-lang zh
  ```

  ⇒ **没有 `--spk-bypass`**。

- **证据 2（默认值）**：`ext/bridge.py` L4574 `ap.set_defaults(spk_bypass=False)`；L4570 `--spk-bypass` 是 `store_true`（默认关）⇒ **不显式打开就恒为关**。
- **证据 3（无环境变量开关）**：`grep -rn "environ|getenv" ext/*.py tools/*.py | grep spk_bypass` → **0 命中** ⇒ 没有别的打开方式。
- **证据 4（产物实测）**：e2e5 / e2e7 / e2e8 **共 19 个臂**的 `bgkeep_e2e.json` → `stats_full.spk_bypass.enabled` **全部 `false`**、`speaker.n_speakers` **全部 `0`**（e2e8 7 臂：`clip_cs2/s1/s2/tuffy` + `clone_cs2/s1/s2`；e2e7 7 臂；e2e5 5 臂）。
- **证据 5（代码侧自述）**：`ext/bridge.py` L3078–3084，未接旁路时固定输出：

  ```python
  {"enabled": False, "spk_queue_drop": 0, "spk_worker_busy_ms": 0.0,
   "note": "本会话未接说话人旁路（EXT-029：串行会话无 GPU 互斥锁 ⇒ 不接）"}
  ```

  ⚠️ **该 note 的措辞与事实不符**：这 19 臂跑的是 **`--pipeline`（`PipelineSession`）**，而 `PipelineSession` **是支持旁路的**（`ext/bridge.py` L3337–3345：`if self.spk_bypass_enabled:` ⇒ 建 `SpeakerBypass` 并 start）；真正的原因是**命令行没加 `--spk-bypass`**。⇒ **note 会误导后续读者**（包括 App 模块 §223 的「`n_speakers = 0` 是计数器口径不同，不是功能缺陷」这一判断）。

- ⇒ 🔴 **结论**：**ASR-068 第 5 条末尾「reviewer 会在 A 上用 voice=clone 跑实时 e2e，确认分段标签真的产出（修前应为零标签）」** ⇒ 🔴 **这批 e2e 无法作为该验收的证据**：它既没有开旁路，**也没有验证「修前为零标签 ⇒ 修后有标签」这个对比**（没有修前的对照臂）。**分段标签是否真的产出，目前仍是零证据。**

### 🔴 发现 B：**即使加了 `--spk-bypass`，旁路仍会因「seg IR 变体解析失败」而拿不到任何标签 ⇒ 发现 A 修好后仍会零标签**

- **机制**：`ext/speaker_bypass.py` `_load()` 的调用顺序是

  | 行 | 动作 |
  |---|---|
  | L212 | `d = self._app_spk_dir()` → `<root>/app/asr_spk` |
  | **L217** | **`seg_ir, wes_ir = self._asset_paths()`** ← **此时 `app/asr_spk` 还不在 `sys.path` 上** |
  | L225–226 | `os.sys.path.insert(0, d)` ← **路径注入在 `_asset_paths()` 之后** |

  `_asset_paths()` → `_find_seg_for_window()`（L85–104）靠 **`import asr052_spk_runtime`** 取 `WIN_S`，再 `from asr_spk_window import seg_ir_subdir_for` 选变体 ⇒ **这两个模块只存在于 `<root>/app/asr_spk/`**（实测：`app/asr052_spk_runtime.py` **不存在**，`app/asr_spk/asr052_spk_runtime.py` 存在）。

- **实测（只读，复刻 `_load()` 真实顺序）**：

  ```
  STEP1 _app_spk_dir = C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.5\app\asr_spk
  STEP2 _asset_paths seg = .../models/spk/pyannote_seg_3_0/fp16      ← 错！应是 fp16-w5
  STEP3 asr052_spk_runtime now importable, WIN_N = 80000
  ```

  `import asr052_spk_runtime` 在 L217 时刻 ⇒ `ModuleNotFoundError: No module named 'asr052_spk_runtime'` ⇒ `_find_seg_for_window` 的 `except Exception: return ""` 吞掉 ⇒ **回落到 `_find(...)` 的 `("fp32", "fp16")` 旧顺序 ⇒ 选中 `fp16`**。

- **后果链（实测）**：`fp16` 的 seg IR 输入长度 = **160000**（10 s 窗），而 `rt.WIN_N` = **80000**（5 s 窗）⇒ **ASR-068 第 4 条新加的形状守卫会直接拒绝**：

  ```
  seg IR input length = 160000  | rt.WIN_N = 80000
  => shape guard would REJECT (RuntimeError)
  ```

  ⇒ `ext/spk_engine.py` L224–227 抛 `RuntimeError` ⇒ 被 L252–254 的 `except Exception` 捕获 ⇒ `_seg_error` 被置位、`_seg_ready` 永假 ⇒ `_advance_seg()` 首行 `if not self._ensure_seg(): return` ⇒ **全程零分段帧 ⇒ 零标签**。

- **对照（App 侧同一台机器上是正确的）**：`Confucius4_LiveCaption_v2.5/app/speaker_assets.py` `find_seg_ir()` 用 `importlib` **按文件路径**加载 `app/asr_spk/asr_spk_window.py`（不依赖 `sys.path`）⇒ 实测返回 **`fp16-w5`（窗口 5.000 s，来源 asr_spk_window）`** ⇒ ✅ App 对、EXT 错。
- **现成 workaround（实测有效）**：环境变量 `EXT_SPK_SEG_IR` **优先**于所有探测（`_find_seg_for_window` L88–90 命中即返回）⇒ 设成 `...\models\spk\pyannote_seg_3_0\fp16-w5` ⇒ 实测 `_asset_paths()` 返回 `fp16-w5`、IR 输入长度 **80000** ⇒ 与 `WIN_N` 匹配 ⇒ 形状守卫放行。
  ⇒ **建议 reviewer 的修法（两处，二选一或都做）**：
  1. **把 `sys.path.insert(0, d)` 提到 `_asset_paths()` 之前**（最小改动，直接修掉根因）；
  2. **或**让 `_find_seg_for_window` 改用 App 同款 `importlib` 按路径加载 `asr_spk_window.py` / `asr052_spk_runtime.py`（不依赖 `sys.path`）。

### 🟡 发现 C（次要）：**EXT-029 回归单测 mock 掉了恰好会暴露发现 B 的那一段**

`tests/test_ext029_spk_bypass.py` L759–760：

```python
bp._app_spk_dir = lambda: os.path.join(ROOT, "ext")
bp._asset_paths = lambda: ("seg_ir", "wes_ir")
```

⇒ **`_asset_paths()` 被整个 mock 掉** ⇒ **发现 B 这条路径在回归单测里永远测不到** ⇒ 建议补 1 条针对 `_find_seg_for_window()` 的真实路径用例。

---

## 4. 其余待办的现状（不重复写，只记状态）

- **分离人声素材**：🔴 `shared/bgkeep/vocals/` **仍不存在** ⇒ 「原声 vs 分离人声」WER 对比**继续等 reviewer 提供**（工具已齐备：`dev/asr044_evalset/clip_10min_0_600.wav`、`reviewer/compare_wer.py`、`scripts/asr146_wer_seg_paired.py`；🔴 两侧须同一 ASR 臂 `pml=320` NPU 档 ＋ OV **2026.4.1**，**本模块不自己调 MiniMax**）。
- **MiniMVP 包无 `models/spk/`**：§95 已记 ⇒ 「实时 e2e 确认分段标签真的产出」**必须在 v2.5/v2.4 全集跑**；本轮确认 reviewer 的 e2e 用的正是 **v2.5**（`run_bgkeep_v5_app_arm.ps1` L12 `$app = "...Confucius4_LiveCaption_v2.5"`）⇒ **场地选对了，但旁路没开**。
- **丢块计数上报 ASR 侧**：仍未闭环（EXT 只在自家 `stats()` 计 `spk_queue_drop`）⇒ 沿用 §95 单开的待办。

---

## 5. 动作边界

- 🔴 **本轮只读 ＋ 跑现成单测**：读了 `live_dub_ext` v0.4.19 源码、跑了 `tests/test_ext0419_bgkeep.py`（12/12 PASS，**不跑模型、不跑推理**）、读了 e2e 产物 json、做了 `_asset_paths()` / IR 形状的**只读诊断**（`ov.Core().read_model()` **只读 IR 不推理**）。
- 🔴 **未跑** ASR 推理 / NPU·GPU 计时 / WER / Demucs 分离；🔴 **未取 MACHINE_LOCK**（纯只读巡检）。
- 🔴 **未改** 4 个 ASR 交付文件、`live_caption/`、**EXT 源码**、纠偏文件内容、旧章节（§95 逐字归档）。
- 🔴 **未打包**。
- ✅ 唯一「执行」＝**跑 reviewer 已入库的测试文件**（不改它）。
