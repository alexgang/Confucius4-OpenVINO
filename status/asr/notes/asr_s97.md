# ASR §97 — 巡检 ＋ APP-128 独立核实：§96 发现 A/B 两条待 reviewer 做已闭环，🔴 新发现 clone_s2 臂仍零标签（原因待查）

- 时间：2026-11-23 20:49–21:05
- 租约：`session_lease.py acquire asr` ⇒ TOKEN=`584c5013`（exit 0，无 TAKEOVER）
- 性质：🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**；但 §96 的两条「待 reviewer 做」**已被 APP-128（App 编号）落地** ⇒ 本轮做**只读独立核实**。

## 一、纠偏通道（文件 ＋ 邮件，双通道复核）

| 通道 | 实测 | 结论 |
|---|---|---|
| 纠偏文件 | `status/asr/CORRECTIONS_ASR.md` **109 822 B** / md5 `3d25680748cf7934fe172f3bb372ec1a` / mtime **2026-11-23 16:55:15** | 与 §96 **逐字相同** |
| 标题计数 | `^## ASR-0[6-9][0-9]` 命中 9 条（ASR-060…ASR-068），**最大 ASR-068** | 无 ASR-069+ |
| 全文搜 `ASR-069`/`ASR-070`/`ASR-071` | **0 命中** | 无新条目 |
| QQ 收件箱（after 2026-11-23T08:55:00Z） | 7 封：**APP-128**（11:40:19Z，附件 3）、APP-128 补充（11:40:34Z）、**APP-127**（08:55:39Z）、**APP-126**（08:55:11Z）、ASR-068（08:55:15Z，已读已落地）、NAS T-004（12:06:18Z）、NAS T-003（12:00:14Z） | **无新 reviewer ASR 邮件**；APP-*/NAS-* 属其它模块编号，按口径**不进本模块 `last_ack`** |
| spam / trash | spam **0** 封；trash **1** 封 = MiniMVP rc9 性能报告（11-13，**非纠偏**） | — |

⇒ **`last_ack` 保持 `ASR-068`**（未变）。

## 二、§96 发现 A/B 的闭环核实（只读；EXT 代码由 reviewer 写，ASR 侧不代改）

### 2.1 代码侧（EXT `live_dub_ext`）

- HEAD = **`3573b2d`**（`EXT v0.4.19: speaker bypass picks the 5 s segmentation IR (fp16-w5) — add app/asr_spk to sys.path before the IR lookup; fix the bypass note; real-path unit test`），分支 `claude-dev...github/live-dub-ext` ⇒ **已推送**（`5121d99..3573b2d`）；**工作区干净**。
- 该 commit **只改 3 个文件**：`ext/speaker_bypass.py`（+5）、`ext/bridge.py`（±2）、`tests/test_ext0419_bgkeep.py`（+26），共 **+33/−2** ⇒ 与 APP-128 §2 的预期完全一致。
- 工作区 md5 与 APP-128 表**逐个一致**：`ext/speaker_bypass.py` = `69f9fce5221c8bf6149ab91cc6503c78`；`ext/bridge.py` = `7be3f8aa06cc2c85169c1b55f9c38523`；`tests/test_ext0419_bgkeep.py` = `d19d2f64a0a460b55724576cedb01b54`。
- ✅ **发现 B 的根因已修**：`ext/speaker_bypass.py` `_load()` L217–222 现在是
  ```
  # v0.4.19 (ASR-096 B): app/asr_spk must be importable BEFORE the IR lookup …
  if d not in os.sys.path: os.sys.path.insert(0, d)
  seg_ir, wes_ir = self._asset_paths()
  ```
  ⇒ **路径注入在 `_asset_paths()` 之前**（§96 指出的最小改法），且注释**逐字引用「ASR-096 B」**。
- ✅ **发现 C 已补回归**：`tests/test_ext0419_bgkeep.py` 新增第 6 组「segmentation IR variant follows the window, with app/asr_spk importable (ASR-096 B)」⇒ 用**真实路径**（不 mock `_asset_paths`）。

### 2.2 单测（本机实跑，只跑现成测试、不改它、不跑模型）

```
cd C:\Users\Trekker-PTL\live_dub_ext
C:\Users\Trekker-PTL\miniforge3\python.exe tests/test_ext0419_bgkeep.py
⇒ RESULT: PASS (14/14)
```
- §96 实测为 **12/12**；本轮 **14/14**（新增第 6 组 2 条：`window 5 s ⇒ pyannote fp16-w5`、`_load() puts app/asr_spk on sys.path before _asset_paths()`）。
- ⇒ **§96 发现 B/C 两条「待 reviewer 修」已闭环**，且**新增用例覆盖了 §96 发现 B 的那条路径**。

### 2.3 实时 e2e（**第一次真正开了旁路**）—— 发现 A 闭环

- 启动脚本：`shared/bgkeep/run_bgkeep_v9_spk.ps1` L36
  `-m ext.bridge --real --pipeline --port 8765 --delay 20 --target-lang zh --spk-bypass` ⇒ **带 `--spk-bypass`**（§96 发现 A 的直接修法）。
- 产物：`shared/bgkeep/e2e9/{clone_s1,clone_s2,clone_cs2}/bgkeep_e2e.json`（mtime 20:18 / 20:20 / 20:22）＋ 各臂 `bridge.log` / `bridge.err`。

**逐臂原始字段（`stats_full.spk_bypass` / `stats_full.speaker`）：**

| 臂 | 媒体（时长） | `spk_bypass.enabled` | seg IR（bridge.log） | `engine.seg_ready` / `seg_error` | `n_feed`/`n_final_req`/`n_label`/`n_no_label` | `speaker.n_speakers` | `engine.embed_count` | `spk_queue_drop` |
|---|---|---|---|---|---|---|---|---|---|
| clone_s1 | `clips/s1.wav`（22.7 s） | **true** | `pyannote_seg_3_0_w5.xml @ NPU`（编译 1 次 / 1.19 s） | **true** / **null** | 35 / 4 / **3** / 1 | **2** | 3（2.682 s） | **0** |
| clone_s2 | `clips/s2.wav`（30.7 s） | **true** | `pyannote_seg_3_0_w5.xml @ NPU`（1 次 / 1.30 s） | **true** / **null** | 31 / 5 / **0** / 5 | **0** | **0**（0.0 s） | **0** |
| clone_cs2 | `clips/cs2.wav`（73.6 s） | **true** | `pyannote_seg_3_0_w5.xml @ NPU`（1 次 / 1.29 s） | **true** / **null** | 40 / 21 / **17** / 4 | **1** | 17（9.307 s） | **0** |

- ✅ **形状守卫不再触发**：bridge.log 三臂都打印「[spk] 说话人资产（包内）：wespeaker fp16；**pyannote_seg_3_0 fp16-w5（窗口 5.000 s，来源 asr_spk_window）**」⇒ 变体解析正确（§96 实测错选 `fp16`）。
- ✅ **「分段推理失败」/「IR 输入长度」次数 = 0**：三臂 `bridge.err` grep `Traceback|Error|分段推理失败|IR 输入` ⇒ **0 命中**；`engine.seg_error = null`、`seg_infer_count` = 3 / 4 / 11、`seg_compile_count` = **1**（会话级缓存生效）。
- ✅ **§96「ASR-068 第 5 条末尾『实时 e2e 确认分段标签真的产出』零证据」这条验收，现已有证据**：clone_s1 出 **3** 个标签（`new_spk {'spk': 'S1'}`、`seg_256000 标签=S1 音色=self_256000.wav`）、clone_cs2 出 **17** 个标签（`seg_183040 标签=S1 音色=S1_1.wav`）。
- ✅ **`bg_late_blocks` 三臂全部 = 0**（§96 记的待核项）。
- ✅ **`spk_queue_drop` 三臂全部 = 0** ⇒ 旁路 64 项有界队列**本次无丢块**（`queue_maxsize=64`、`spk_worker_busy_ms` = 101.5 / 252.2 / 324.2 ms、`spk_gpu_lock_held_ms` = 2712.1 / 31.6 / 9661.2 ms、`shares_device_lock_with_asr=true`）。

**三臂 `dubs` / `dub_late_vs_play_s` / `bg_late_blocks`（APP-128 §6 要求列表，本模块只读复算）：**

| 臂 | `dubs` | `dub_late_vs_play_s.max` | `.p90` | `.n_late` | `bg_late_blocks` | `bg_blocks` |
|---|---|---|---|---|---|---|
| clone_s1 | 4 | 5.9 | 3.5 | 1 | **0** | 23 |
| clone_s2 | 5 | 3.91 | 0.72 | 1 | **0** | 31 |
| clone_cs2 | 21 | **−0.16** | **−3.2** | **0** | **0** | 74 |

**e2e7 三臂对照（reviewer 用于定默认分离设备，本模块只读）：**

| 臂 | `dubs` | `max` | `p90` | `n_late` | `bg_late_blocks` |
|---|---|---|---|---|---|
| e2e7/off | 123 | 2.43 | −1.54 | 7 | **0** |
| e2e7/on_gpu | 123 | 3.41 | −1.43 | 8 | **0** |
| e2e7/on_cpu | 123 | 3.41 | −1.69 | 8 | **0** |

### 2.4 🔴 本轮新发现（不推翻 §96，但需 reviewer 侧补数据才能定性）

**clone_s2 臂仍为「零标签」**（`n_label=0`、`n_no_label=5`、`speaker.n_speakers=0`），但**原因已与 §96 完全不同**：

- §96 的零标签是「seg IR 变体解析失败 ⇒ 形状守卫 RuntimeError ⇒ `_seg_ready` 永假」⇒ **机制性失效**；
- 本轮 clone_s2 的 `engine.seg_ready=true`、`seg_error=null`、`seg_infer_count=4`、`seg_infer_sec=0.251` ⇒ **分段侧完全正常**；`embed_count=0` ⇒ 卡片在**嵌入之前**就被判「无标签」。
- 该臂 5 段中前 2 段 ASR 转写为 **`—`（空）**、`dub_items` 里 `src=""`、`tgt=""`；`bridge.log` 显示 4 段有中文古风台词。
- `ext/spk_engine.py` `on_final()`（L456–483）的「无标签」出口有 3 类：`too_short`（< `MIN_DUR_S` = 2.0 s）、`not_clean_speech`（`clean_ratio < MIN_CLEAN_RATIO` = 0.6）、`overlap`（`overlap_ratio > OVERLAP_RATIO_MAX` = 0.02）。
- 🔴 **但产物里查不到是哪一类**：`bridge.py` L2504 把 `spk_reason` 写进**段级表**（`_spk_rows`），而 `bgkeep_e2e.json` **只导出 `stats_full`**，**不导出段级表**；`bridge.log` 也没有打印 `reason` ⇒ **从现有产物无法判定 clone_s2 的零标签属于哪一类**。
- ⇒ **待 reviewer / EXT 侧补 1 项**：把 `on_final` 的 `reason` 分布做成计数并进 `stats_full`（或把段级表 `spk_reason` 导出到 json）⇒ 否则「旁路零标签」以后仍**不可归因**。
- 🟡 **本模块的判断**：`clone_s2` 素材是中文古风音频、含大量非语音段与重叠 ⇒ **更像素材/阈值侧的「不干净语音」拒绝**，**不像 v0.4.19 缺陷**；但**在拿到 `reason` 分布前不下结论**（避免重复 §96 那种「措辞与事实不符」的误判）。

### 2.5 🟡 §96 三条待办的最终状态

| §96 待 reviewer 做 | 状态 | 依据 |
|---|---|---|
| ① 补跑「开了旁路」的实时 e2e | **部分闭环** | e2e9 三臂已跑、已带 `--spk-bypass`、已有标签证据（s1=3 / cs2=17）⇒ 🔴 **但仍缺「修前（v0.4.18 / `5121d99`）」对照臂** ⇒ 「修前为零标签 ⇒ 修后有标签」的对账**尚不完整** |
| ② 修 seg IR 变体解析的调用顺序 | ✅ **闭环** | `3573b2d` 把 `sys.path.insert(0, d)` 提到 `_asset_paths()` 之前；e2e9 bridge.log 三臂均选中 `fp16-w5` |
| ③ 修 note 措辞 ＋ 补不 mock `_asset_paths()` 的回归用例 | ✅ **闭环** | `ext/bridge.py` 改了 2 行 note；单测新增第 6 组（真实路径）⇒ 14/14 PASS |

## 三、本轮未做（纪律）

🔴 **未跑推理/计时/WER/分离器**（e2e9 是 App 线程跑的，本模块只读产物）；**未取 MACHINE_LOCK**（本机当前无锁）；**未改 4 个 ASR 交付文件**；**未改 `live_caption/`**；**未改 EXT 源码**；**未改纠偏文件内容**；**未打包**；**未自己调 MiniMax**。
🟡 `shared/bgkeep/vocals/` 本轮实测**仍不存在** ⇒ 「原声 vs 分离人声」WER 对比**继续等 reviewer 提供**（两侧须同一 ASR 臂 `pml=320` NPU 档 ＋ OV **2026.4.1**）。

## 四、产物

- `status/asr/notes/asr_s97.md`（本文件）
- `status/asr/STATUS_ASR.md` §97（`last_ack` 保持 ASR-068）
- 只读引用的外部产物：`live_dub_ext` commit `3573b2d`；`shared/bgkeep/e2e9/{clone_s1,clone_s2,clone_cs2}/bgkeep_e2e.json`（3 文件，mtime 20:18/20:20/20:22）；`shared/bgkeep/e2e7/{off,on_gpu,on_cpu}/bgkeep_e2e.json`（3 文件）；`shared/bgkeep/run_bgkeep_v9_spk.ps1`（3 646 B，20:14）。
