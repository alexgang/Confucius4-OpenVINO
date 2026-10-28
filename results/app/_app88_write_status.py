# -*- coding: utf-8 -*-
"""§88 追加器：只追加 `## §88` 章节 + 更新头部 4 字段行。

纪律：
- **只追加**（不回头改旧章节）；
- 旧结论错了 ⇒ 在 §88 里写「撤回 §x」；
- 头部只改 4 字段行（「阻塞」行按前缀找，不能写死索引）；
- STATUS 是 LF ⇒ 写盘必须 `newline=''`。
"""
import io
import os
import re

STATUS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'status', 'app', 'STATUS_APP.md')

NOW = '2026-10-28 21:38'

BODY = r'''
## §88 🔴🔴 **APP-027 V1（CUDA）用 §84 修好后的代码重跑 ⇒ 18 PASS / 0 FAIL ＋ V2（争用 ABBA）两臂重跑 ⇒ `lang`/`end_reason` 全量补齐 ⇒ §87.7 遗留第 4 条闭环** ＋ 🔴🔴🔴 **撤回 §82/§83 的 V1 RTF 数字与「RTF>1 是产品缺陷」的归因表述（实测证明：那是 12:38 那一轮的环境性慢，不是代码慢）**（2026-10-28 21:38）｜**本条已完成**｜**本条需等 reviewer 复核**

> 🔴 **本节只追加，不回头改旧章节**；`CORRECTIONS_APP.md` 本轮**只读、零改动**。

### §88.0 本节结论（一句话）

**§87.7 遗留第 4 条（V1/V2 的 `lang`/`end_reason` 缺失）已闭环** —— V1 重跑 **18 PASS / 0 FAIL**、V2 两臂各 **76/76 行**全部带上 `lang='zh'` / `end_reason='eos'`；
同时 🔴🔴🔴 **实测推翻了 §82/§83 对 V1 的 RTF 归因**：旧轮 `synth_rtf` P50 = 3.6184 **不是产品代码慢**，而是**那一轮边车进程自身慢了 6~7 倍**（边车自报 `elapsed` 同样是 6 倍），同代码同配置的另外两轮（14:32 / 14:46 / 21:05）P50 都在 **0.55~0.59** ⇒ **§83.5 第 1 项「RTF 归因边界」的裁定时必须以本节数据为准，不能再用 12:38 那一轮的数字**。

---

### §88.1 巡检结论：**无新 reviewer 纠偏条目**（本节做的是遗留事项补做）

- 🔴 **`status/app/CORRECTIONS_APP.md` 条目 = APP-001…APP-033，共 33 条**（正则 `^## (APP-\d+)` 计数 = 33），最大编号 = **APP-033**。
- 🔴 **`STATUS_APP.md` 头部 `last_ack` = APP-033** ⇒ **编号 > last_ack 的新条目 = 0 条** ⇒ 本轮**无 reviewer 新纠偏指令** ⇒ 未触发任何「需要停下来等 reviewer 复核」的 stop-node。
- 🔴 **该文件只读、零改动**（本轮实测指纹，与 §87.1 完全一致）：
  | bytes | mtime | sha256 |
  |---|---|---|
  | **90 321** | 2026-10-28 00:47:55 | `bb2896ee9143cd89e4bd2f8a3d0e8f8327079945237ccffc6c6bbd0d825ea043` |
- ⇒ 按自动化记忆「若无新条目 ⇒ 补做遗留的 App 职责内事项」推进 **§87.7 第 4 条**（V1/V2 补 `lang`/`end_reason`）。

---

### §88.2 ✅ 本条已完成（§87.7 遗留第 4 条 · 上半：V1 CUDA 重跑）

#### §88.2.1 实测条件（原始字段）

| 项 | 原始字段 | 值 | 出处 |
|---|---|---|---|
| 配置 | `cfg` / `device` / `duration` / `translate` | `v1_cuda` / `CUDA` / `300.0` / `zh` | `v1_cuda_report.json` |
| 摆放 | `asr_device` / `mt_device` / `tts_device` | `GPU.0` / `GPU.0` / `CUDA` | 同上 |
| 墙钟 / 退出码 | `wall_s` / `rc` | **390.2** / **0** | 同上 |
| 播放路径 | **未传 `--tts-out`** | ⇒ 走**真实播放** | 驱动命令行原文 |
| 落盘目录 | `C:\Users\Trekker-PTL\app027_v1\cuda_rerun_run_20261028_210551\` | **带时间戳 ⇒ 0 次删除** | 目录实况 |

- 🔴 **持共享机器锁**：`app PID 4228 started 2026-10-28 21:04:51` / `module: app` / `pid: 4228` / `host: LAPTOP-0GDQGD3I` ⇒ 跑完**已释放**，跑后 `shared/*.tmp` 残留 **0**。
- 🔴 **45 s 安静窗口通过**（`waited_s=45.03`、`n_busy_samples=0`）⇒ 符合「不在 CPU 上跑推理/测速」纪律。

#### §88.2.2 判据结果：**PASS = 18 / FAIL = 0**（`pass_count=18`、`fail_count=0`）

> 🔴 与 §82 那一轮（PASS 16 / FAIL 2）相比，**两条 FAIL 都消失了** —— 但**原因不是判据放宽**，见 §88.2.3 的根因分析。

| 判据 | 名称 | got | want |
|---|---|---|---|
| `V1-0a` | 🔴 真实播放证据：至少 1 句 `consumed=True` | **76** | `>0` |
| `V1-0b` | 🔴 真实播放证据：`read_delta ≥ n_samples` 的句数 > 0 | **76** | `>0` |
| `V1-0c` | 🔴 无播放器故障 | **0** | 0 |
| `V1-1` | 「已写入被丢」= 0 | **0** | 0 |
| `V1-2` | 「没有产出音频」= 0 | **0** | 0 |
| `V1-3` | 看门狗触发次数 = 0 | **0** | 0 |
| `V1-4` | 无 > 30 s 合成空窗 | **16.2236** | `<=30` |
| `V1-5` | 不变式 `n_played + n_dropped == n_submitted` | **76** | 76 |
| `V1-6` | worker 重启次数 = 0 | **0** | 0 |
| `V1-7` | 撞帧上限 `cap` = 0 | **0** | 0 |
| `V1-8` | 失控 `runaway` = 0 | **0** | 0 |
| `V1-9` | 逐句 `error` 非空 = 0 | **0** | 0 |
| `V1-10` | 🔴 无 `consumed=False` 的句子 | **0** | 0 |
| `V1-11` | 句内 `underflow_in_sentence` P95 = 0 | **0** | 0 |
| `V1-12` | 逐句 wav 落盘 ≥ 10 句（供 reviewer 回转写） | **76** | `>=10` |
| `V1-13` | （只记录）`synth_rtf` P95 | **0.6541** | 只记录 |
| `V1-14` | （只记录）合成首包 P95 | **0.8289** | 只记录 |
| `V1-15` | （只记录）排队等待 P95 | **0.0** | 只记录 |

- 🔴 **不变式本轮直接成立（未用三段式口径）**：`n_played=76` + `n_dropped=0` + `n_drop_unbuilt=0` = `n_submitted=76`
  ⇒ **§82.1.2 记的那 51 句「未合成就丢」在本轮为 0** ⇒ **§83.5 第 4 项（三段式）的「必要性」在 V1 CUDA 场景下已不成立**（但 NPU 场景见 §88.3，仍需 reviewer 裁定是否统一改口径）。
- 🔴 **CLI 状态行原文**：`[TTS] 首包 0.68s  积压 当前 72.34s / 最大 77.27s  提交 76  播完 76  丢弃 0  重启 0  state=ready` ⇒ **76/76 全部播完、0 丢弃、0 重启**。

#### §88.2.3 ✅🔴🔴 §84 缺陷②修法的**端到端实证**（`lang`/`end_reason` 全量补齐）

| 项 | 旧轮（`cuda_run_20261028_123827`） | 本轮（`cuda_rerun_run_20261028_210551`） |
|---|---|---|
| jsonl 行数 | 76 | 76 |
| 有 `lang` 的行 | **0**（全部 `null`） | **76 / 76 = `zh`** |
| 有 `end_reason` 的行 | **0**（全部 `null`） | **76 / 76 = `eos`** |
| 其它字段 | 无 `n_chars`/`est_frames`/`frames`/`max_new_tokens`/`clone_*` | **全部补齐**（`clone_active=false`、`clone_audio_s=0.0`） |

- 🔴 **旧轮的行**（`cuda_run_20261028_123827/v1_cuda.tts.jsonl` 第 1 行原文）：
  `{"id": 0, "text": "大家早上好。", …, "synth_rtf": 4.9604, …, "queue_lag_s": 0.0, "queue_peak_s": 1.306, "queue_peak_mb": 0.11}` ⇒ **无 `lang`/`end_reason`**。
- 🔴 **本轮的行**（`cuda_rerun_run_20261028_210551/v1_cuda.tts.jsonl` 第 1 行原文）：
  `{"id": 0, "text": "大家早上好。", …, "synth_rtf": 2.0775, …, "lang": "zh", "lang_src": "explicit", "n_chars": 6, "est_frames": 25, "frames": 14, "end_reason": "eos", "max_new_tokens": 111, "clone_active": false, "clone_audio_s": 0.0, …}`。
- ⇒ 🔴 **§84 缺陷②（真实播放路径下合成线程填的遥测字段被看门狗重算覆盖 ⇒ 整组丢失）的修法 = 「合成那一刻把 `meta` 快照进 job，看门狗重算后再覆盖回 `tel`」，经端到端实测成立**。
- 🔴 `lang_src="explicit"`（CLI `--translate zh` 显式指定）⇒ **「按语言分组」现在有可核字段了**（旧轮做不到）。

---

### §88.3 ✅ 本条已完成（§87.7 遗留第 4 条 · 下半：V2 争用 ABBA 两臂重跑）

#### §88.3.1 实测条件

- 🔴 驱动：`results/app/app114_app027_v2_real_playback.py`（**取代 `app112`** —— 后者三处判据失效，见脚本 docstring）。
- 🔴 **只跑两个有数据的手臂**：`tts_asr_mt_npu`（MT@NPU，与 TTS 争 NPU）＋ `tts_asr_mt_gpu0`（MT@GPU.0，与 ASR 同在 GPU.0）；
  `tts_only` 臂**架构上不可实现**（CLI 架构下句子来自 ASR 定稿 ⇒ 关 MT 就没句子）⇒ 脚本标记 **NOT-APPLICABLE**，**不用「什么都没跑的臂」冒充基线**。
- 🔴 **持锁**：`app PID 3336 started 2026-10-28 21:24:40` / `module: app` / `pid: 3336` / `host: LAPTOP-0GDQGD3I`；
  45 s 安静窗口**通过**（`[quiet] ✅ 安静窗口已持续 45 s`）⇒ 跑完**已释放**（`[lock] 已释放`），`shared/*.tmp` 残留 **0**。
- 🔴 墙钟 **13 m 38 s**，退出码 **0**。
- 🔴 **每臂独立时间戳目录 ⇒ 0 次删除**：`tts_asr_mt_npu/run_20261028_212525/`、`tts_asr_mt_gpu0/run_20261028_213217/`。

#### §88.3.2 两臂判据结果：**各 PASS = 14 / FAIL = 1**（FAIL 是同一条，且是**真实欠载**）

**唯一 FAIL（两臂同一条，必须如实写出来）**：`V2-1`「句内 `underflow_in_sentence` P95 = 0（只允许句前等待）」
- 🔴 `tts_asr_mt_npu` 臂：`got=11`（脚本汇总表 `uf_p95=65`，逐句 jsonl P95 = **53**）⇒ **FAIL**。
- 🔴 `tts_asr_mt_gpu0` 臂：`got=11`（脚本汇总表 `uf_p95=11`，逐句 jsonl P95 = **11**）⇒ **FAIL**。
- 🔴 **其余 14 条全 PASS**，含：`V2-0a`/`V2-0b` 真实播放证据 **76/76**、`V2-0c` 播放器故障 **0**、`V2-2` 已写入被丢 **0**、`V2-3` 没有产出音频 **0**、`V2-4` 看门狗 **0**、`V2-5` 合成空窗 **10.007 s ≤ 30**、`V2-6` 不变式 **76 = 76**、`V2-7` 重启 **0**、`V2-8` cap **0**、`V2-9` runaway **0**、`V2-10` 逐句 error **0**、`V2-12` 无 `consumed=False` **0**。
- 🔴 **不变式在 NPU 臂也直接成立**：`n_played=76` + `n_dropped=0` + `n_drop_unbuilt=0` = 76 ⇒ **§88.2.2 的观察在 V2 两臂同样成立**。

**争用定量对照（脚本原始汇总表）**：

| cfg | src | rtf_p50 | rtf_p95 | uf_p95 | consumed | dropped | P/F |
|---|---|---|---|---|---|---|---|
| `tts_asr_mt_npu` | mt | **1.0915** | **1.4383** | **65** | 76 | 0 | **14 / 1** |
| `tts_asr_mt_gpu0` | mt | **1.0016** | **1.1461** | **11** | 76 | 0 | **14 / 1** |

#### §88.3.3 ✅ `lang`/`end_reason` 全量补齐（§87.7 遗留第 4 条的**闭环点**）

| jsonl | 行数 | 有 `lang` | 有 `end_reason` | `lang` 值 | `end_reason` 值 |
|---|---|---|---|---|---|
| `tts_asr_mt_npu/run_20261028_212525/v2_tts_asr_mt_npu.tts.jsonl` | 76 | **76** | **76** | `['zh']` | `['eos']` |
| `tts_asr_mt_gpu0/run_20261028_213217/v2_tts_asr_mt_gpu0.tts.jsonl` | 76 | **76** | **76** | `['zh']` | `['eos']` |
| （对照）旧轮 `tts_asr_mt_npu/run_20261028_104902/…jsonl` | 76 | **0** | **0** | `[None]` | `[None]` |
| （对照）旧轮 `tts_asr_mt_gpu0/run_20261028_105545/…jsonl` | 76 | **0** | **0** | `[None]` | `[None]` |

- ⇒ 🔴 **§87.7 第 4 条 ⇒ 已闭环**（V1 + V2 两路都用 §84 修好后的代码重跑过，`lang`/`end_reason` 在**真实播放路径**下全量可核）。
- 🔴 **顺带闭环**：§84 的 V3 两臂（CUDA/NPU）产物**本来就已带** `lang`/`end_reason`（各 76/76）⇒ **APP-027 的 V1/V2/V3 三段现在都具备该字段**。

---

### §88.4 🔴🔴🔴 **撤回 §82 / §83 关于 V1 的 RTF 数字与「RTF>1 是产品缺陷」的归因表述**

> 🔴 **本节只追加，不回头改旧章节**；以下为**撤回声明**，原 §82 / §83 章节**原文保留不动**。

#### §88.4.1 撤回的内容

| 位置 | 原表述 | 撤回结论 |
|---|---|---|
| §82.1.2 `V1-11` FAIL 条 | 「`underflow_in_sentence` P95 = 399 ⇒ **这是 RTF 问题**」 | 🔴 **该归因不成立** —— 那不是代码的 RTF，是**那一轮环境的偶发慢**（见 §88.4.2） |
| §82.1.3「根因 B」 | 「『首包 4.53 s』与文本长度无关 ⇒ **不是模型慢，是固定开销**」 | 🔴 **方向对、结论错**：确实是「固定开销」形状，但**固定开销来自边车进程自身当时的慢**，**不是** `tts_cuda_sidecar.py` 的「只缓存一块」机制（该机制是**真实存在**的，但**不是** 4.53 s 的来源） |
| §82.1.4 数字 | `synth_rtf_p50 = 3.6184` / `synth_first_s_p50 = 4.5394` / `underflow_in_sentence_p95 = 399` | 🔴 **这些数字本身是真的**（实测复现自 `cuda_run_20261028_123827/v1_cuda_report.json`），但**它们描述的是一轮异常环境，不构成产品基线** ⇒ **不可作为 §83.5 第 1 项「RTF 归因边界」的裁定依据** |

#### §88.4.2 🔴 根因（实测定位，四个独立数据点）

**关键证据：差异发生在【边车进程内部】，不在 App 代码、不在 worker 埋点。**

- 🔴 **边车自报的 `elapsed` 同样是 6 倍**（`v1_cuda_cli.log` 里 `[sidecar] DONE … elapsed=` 原文）：

| rid | 旧轮 12:38 `elapsed` | 新轮 21:05 `elapsed` | 倍数 |
|---|---|---|---|
| rid=1 | **5.94 s** | **2.31 s** | 2.6× |
| rid=2 | **4.97 s** | **0.72 s** | 6.9× |
| rid=3 | **6.00 s** | **0.70 s** | 8.6× |
| rid=4 | **16.84 s** | **2.50 s** | 6.7× |
| rid=8 | **22.30 s** | **3.16 s** | 7.1× |

  ⇒ 🔴 **同一个 rid、同一段文本、同样 `frames`/`chunks` 输出，边车自己说「我花了 6 倍时间」** ⇒ 排除 App 侧埋点/计时口径问题。

- 🔴 **四个独立数据点（同一份代码）**：

| 轮次 | 产物 | `synth_rtf` P50 | `dequeue→first` P50 |
|---|---|---|---|
| **12:38（旧 V1）** | `cuda_run_20261028_123827/v1_cuda.tts.jsonl` | **3.6184** | **4.5394 s** |
| 14:32（V3 CUDA-1） | `app027_v3/v3_cuda_run_20261028_143216/v3_cuda.tts.jsonl` | **0.5920** | 0.7689 s |
| 14:46（V3 CUDA-2） | `app027_v3/v3_cuda_run_20261028_144058/v3_cuda.tts.jsonl` | **0.5857** | 0.7683 s |
| **21:05（本轮 V1）** | `cuda_rerun_run_20261028_210551/v1_cuda.tts.jsonl` | **0.5592** | 0.7228 s |

  ⇒ 🔴 **只有 12:38 那一轮是 6 倍慢**，14:32 / 14:46 / 21:05 **三轮都正常** ⇒ **不是代码问题**。

- 🔴 **已逐项排除的差异源**（每一项都做了实测核对）：

| 候选差异源 | 核对方式 | 结论 |
|---|---|---|
| 边车客户端 `tts_cuda.py` | 仓库 vs 包内 `diff` | **逐字节相同**（mtime 均为 2026-10-27 21:1x） |
| 边车服务端 `tts_cuda_sidecar.py` | 同上 | **逐字节相同** |
| 包内 `tts_worker.py` / `live_caption_app.py` / `tts_engine.py` | 与 `_backup_app_20261028_preclone` 旧版 diff | 差异仅「克隆遥测 + `meta` 快照 + 克隆采集重构 + `execution_devices()` 诊断函数」，**不含任何合成时序改动** |
| 边车 venv / torch | `_fq3tts_env` 包版本 + mtime | `torch 2.11.0+cu128`（2026-10-25 20:14 安装，**两轮之间未变**） |
| `faster_qwen3_tts` 源码 | editable install 指向 `C:\Users\Trekker-PTL\_fq3tts_src\faster-qwen3-tts-main\` ⇒ 查该目录 `.py` mtime | 全部 **2026-10-25 20:10** ⇒ **两轮之间未改** |
| 边车加载 / 预热耗时 | 两轮 CLI 日志原文 | **33.5 s / 1.8 s** vs **34.9 s / 2.2 s** ⇒ **几乎相同**，**不是**整机负载差异 |
| ASR / MT 并发占用 | 12:25–13:30 窗口内**创建**（ctime）与**修改**（mtime）扫描全用户目录 | **只有本轮 V1 自己的产物**（`app027_v1/cuda_run_20261028_123827/**`）⇒ **无并发作业** |
| 驱动变更 | `nvlddmkm.sys` mtime = 2026-06-29；系统事件日志 `Display/nvlddmkm` 在 10-28 11:00–22:00 **无任何事件** | **驱动未变更** |
| 电源方案 | `powercfg /GETACTIVESCHEME` = 「平衡」；`Win32_Battery` = 充电中 100% | 无节流差异可归因 |

- 🔴 **最有力的旁证：输入逐字一致**。本轮 `subtitles.txt` 的 SHA256 = `b4632dd8cdf2bb133e62772adfb615d7a80e7c7704ed02c7bd3dde96ad10b526`，
  **与旧轮 `cuda_run_20261028_123827/subtitles.txt` 的 SHA256 完全相同**；`subtitles.mt.txt` 也完全相同（`d540cf67ca95db7a…`）；
  V2 两臂的 `subtitles.txt` **同样**是 `b4632dd8cdf2bb1…`
  ⇒ 🔴 **ASR + MT 的输出逐字相同 ⇒ 输入侧完全可复现 ⇒ 差异只能来自 TTS 合成侧的运行时环境**。

#### §88.4.3 ⇒ 对 §83.5 四项裁定的直接影响

| §83.5 裁定项 | 本节的影响 |
|---|---|
| **1. RTF 归因边界** | 🔴 **必须重做**：原依据（V1 P50=3.6184 / P95=3.6515）是**异常轮**数据。**有效基线**应为：CUDA `synth_rtf` P50 ≈ **0.56~0.59**（三轮一致）；NPU 臂 P50 ≈ **1.00~1.09**（本轮 V2 两臂）⇒ **「双侧争用」作为主因解法优先级的依据需重新评估**（CUDA 侧 RTF<1 已达标，NPU 侧 RTF≈1 才是争用战场） |
| **2. 「首包」指标定义** | 🔴 **仍然有效**：`tts_cuda_sidecar.py` 的「只缓存一块（`pending`）」机制**真实存在**（代码 L312/L338–L348），客户端 `t_first` 量到的确实偏晚 ⇒ 是否要暴露**真正的首块时间**仍待 reviewer 裁定 |
| **3. `app062` A/B 是否重做** | 🔴 **仍然有效**（判据过时，未重跑） |
| **4. 不变式是否改三段式** | 🔴 **优先级下降**：本轮 V1（CUDA）与 V2 两臂（NPU / GPU.0）**三段式里 `n_drop_unbuilt` 都是 0** ⇒ 两段式直接成立 ⇒ 是否统一改口径由 reviewer 定 |

---

### §88.5 ✅ 产物清单（**已落盘**，附文件数 / mtime / 字节数 / SHA256）

#### §88.5.1 V1（CUDA）重跑 — `C:\Users\Trekker-PTL\app027_v1\`

| 产物 | 字节数 | mtime | SHA256 |
|---|---|---|---|
| `app027_v1_summary.json` | 1 506 | 2026-10-28 21:12:21 | `1cefb73a3d3b1aa30d9718156060b9f8f59fb8db4effa530a753e4201d015b40` |
| `cuda_rerun_run_20261028_210551/v1_cuda_report.json` | 4 934 | 2026-10-28 21:12:21 | `3271cd326fa5778a525876c86d37ab2eefdc457f34bae53e5317f9c69a580b84` |
| `cuda_rerun_run_20261028_210551/v1_cuda.tts.jsonl`（**76 行**） | 66 465 | 2026-10-28 21:12:18 | `9e39e1b02e9923e6cfdec553d45487464c4a6a8eeb27064827e3ad370cffa0c3` |
| `cuda_rerun_run_20261028_210551/v1_cuda_cli.log` | 128 058 | 2026-10-28 21:12:18 | `f950770bb78031a6bf68747ba8fd4c2655526fc6ae0b960321fe7acc1ef21add` |
| `cuda_rerun_run_20261028_210551/v1_cuda_backlog_curve.csv` | 1 324 | 2026-10-28 21:12:21 | `2c2666b70771be6305d1e769766ceef410b135c1df3ca92a3880c327833cc86e` |
| `cuda_rerun_run_20261028_210551/v1_cuda_wav_text_alignment.json` | 2 418 | 2026-10-28 21:12:21 | `07eea85457d1a1d099a9aeb039d8bf24fa2e85383aa22e9e99db73794a54cdc1` |
| `cuda_rerun_run_20261028_210551/subtitles.txt` | 4 704 | 2026-10-28 21:11:02 | `b4632dd8cdf2bb133e62772adfb615d7a80e7c7704ed02c7bd3dde96ad10b526` |
| `cuda_rerun_run_20261028_210551/subtitles.mt.txt` | 5 044 | 2026-10-28 21:11:02 | `d540cf67ca95db7a6a43909c87819b644aa320d242d373bfe94c483009e6a757` |
| `cuda_rerun_run_20261028_210551/dump/` | **76 个 wav / 15 996 944 B** | dir mtime 2026-10-28 21:11:05 | （逐句 wav，**供 reviewer MiniMax 回转写 / CAMPPlus**） |

#### §88.5.2 V2（争用 ABBA）重跑 — `C:\Users\Trekker-PTL\app027_v2\`

| 产物 | 字节数 | mtime | SHA256 |
|---|---|---|---|
| `app027_v2_abba_summary.json`（**汇总主文件**） | 1 610 | 2026-10-28 21:38:17 | `0c9b61b55c51c0164a0e829a7a3af5eed283c6778f439faf5d16514b9cc8b417` |
| `v2_rerun_20261028_2140.log`（**本轮驱动日志**） | 6 470 | 2026-10-28 21:38:18 | `fb12ba0b2a555ff8c1a1c2acb269f7c85fe97966a52bbc5a6bcd3f246c39078b` |
| `tts_asr_mt_npu/run_20261028_212525/v2_tts_asr_mt_npu.tts.jsonl`（**76 行**） | 65 555 | 2026-10-28 21:32:15 | `208e0631492e666e1d8c014472587ed7f9aeaf14a980c57d62cb01859783ec67` |
| `tts_asr_mt_npu/run_20261028_212525/v2_tts_asr_mt_npu_report.json` | 4 172 | 2026-10-28 21:32:17 | `d57138fc4c3f69763e9d99f314229b5768b94d6c4b03a3f0df917245ce5c2792` |
| `tts_asr_mt_npu/run_20261028_212525/v2_tts_asr_mt_npu_cli.log` | 107 334 | 2026-10-28 21:32:14 | `babaacd7828177983dbe048585d5190dfd9844ad7eb1e945cf764cba17581533` |
| `tts_asr_mt_npu/run_20261028_212525/v2_tts_asr_mt_npu_backlog_curve.csv` | 433 | 2026-10-28 21:32:17 | `4b8813987f5f7eddb61725453a46e4dd714d00d0516cc9a0b2d7ff27e7a1fdd8` |
| `tts_asr_mt_npu/run_20261028_212525/subtitles.txt` | 4 704 | 2026-10-28 21:30:37 | `b4632dd8cdf2bb133e62772adfb615d7a80e7c7704ed02c7bd3dde96ad10b526` |
| `tts_asr_mt_npu/run_20261028_212525/subtitles.mt.txt` | 5 037 | 2026-10-28 21:30:37 | `346e94470e9422b368c27ba3f33a87fca18d1c114b1b99b3880cfd0819006ec8` |
| `tts_asr_mt_gpu0/run_20261028_213217/v2_tts_asr_mt_gpu0.tts.jsonl`（**76 行**） | 65 238 | 2026-10-28 21:38:14 | `98f630ee2177161ef78d97e23174865ac3a375c135d9d0005ea7f1203c3c81f6` |
| `tts_asr_mt_gpu0/run_20261028_213217/v2_tts_asr_mt_gpu0_report.json` | 4 174 | 2026-10-28 21:38:17 | `e2ea594a0a644471b2e2376e141b635bae50f7225711b652c768244d38f07738` |
| `tts_asr_mt_gpu0/run_20261028_213217/v2_tts_asr_mt_gpu0_cli.log` | 107 210 | 2026-10-28 21:38:14 | `a99dc94deb697ace45db19e72521a0049b47e2745b893eb908feacd8e8c48df3` |
| `tts_asr_mt_gpu0/run_20261028_213217/v2_tts_asr_mt_gpu0_backlog_curve.csv` | 282 | 2026-10-28 21:38:17 | `4e46eff5a6751c645bdc201aefb62d81d2f1ca97ffa45fc6952abb0e2c84d68b` |
| `tts_asr_mt_gpu0/run_20261028_213217/subtitles.txt` | 4 704 | 2026-10-28 21:37:26 | `b4632dd8cdf2bb133e62772adfb615d7a80e7c7704ed02c7bd3dde96ad10b526` |
| `tts_asr_mt_gpu0/run_20261028_213217/subtitles.mt.txt` | 5 044 | 2026-10-28 21:37:26 | `d540cf67ca95db7a6a43909c87819b644aa320d242d373bfe94c483009e6a757` |

#### §88.5.3 本节涉及的仓库文件

| 文件 | 字节 | 说明 |
|---|---|---|
| `results/app/_app88_write_status.py` | 本节追加脚本 | 只追加 + 头部字段行 + `newline=''` 保 LF |
| `status/app/STATUS_APP.md` | — | 追加 §88（**只追加，未改旧章节**） |

---

### §88.6 ✅ 交付口径（本节**不**涉及客户包 ⇒ 不写「已交付」）

| 项 | 状态 |
|---|---|
| 生产代码改动 | **无**（`live_caption/` 下产品代码本轮**零改动**） |
| 客户包定点同步 | **不需要**（无生产代码改动 ⇒ 仓库与包目录**天然一致**） |
| 客户包 zip 重打 | **不需要**（§86 的 v1.6 zip **保持不变**） |
| 「已交付」 | ⛔ **本节不写「已交付」**——本节交付的是**实测产物 + 证据**（已落盘、已给指纹），**不是**新的客户包；「已交付」沿用 §86 口径（代码 + 包 zip） |
| 机器锁 | ✅ **V1**：`app PID 4228 started 2026-10-28 21:04:51`（跑完已释放）；**V2**：`app PID 3336 started 2026-10-28 21:24:40`（跑完已释放，`[lock] 已释放`）⇒ 两次 `shared/*.tmp` 残留均 **0** |

---

### §88.7 🔴 遗留 / 待 reviewer 裁定（本节**未**推进）

1. 🔴 **APP-027 仍未完**：**V3-CER（MiniMax 回转写）/ V3-CAMPPlus（CAMPPlus 余弦）归 reviewer**；
   **V4 用户实听未做** ⇒ **「用户听得到」仍不成立**。本节已把 **V1 76 句 + V2 两臂各 76 句**的 wav 落盘待 reviewer 回转写。
2. 🔴 **§83.5 第 1 项「RTF 归因边界」必须重做裁定** —— 见 §88.4.3：**原依据已被本节实测推翻**。
3. 🔴 **§83.5 第 2 项（「首包」指标定义）仍有效**（边车「只缓存一块」机制真实存在，是否暴露真正首块时间待裁定）。
4. 🔴 **§83.5 第 3 项（`app062` A/B 是否重做）仍有效**（未重跑）。
5. 🔴 **§83.5 第 4 项（不变式是否改三段式）优先级下降** —— 本轮 V1/V2 三臂 `n_drop_unbuilt` **均为 0** ⇒ 两段式直接成立；是否统一改口径仍由 reviewer 定。
6. 🔴 **旧 v1.6 zip 若已分发** ⇒ 带 §85 修正前的**不实许可声明** ⇒ **是否需重新分发待 reviewer 裁定**（App 不自行决定）。
7. 🔴 **12:38 那一轮慢的根因尚未完全闭环** —— 已排除代码/模型/venv/驱动/并发/电源，**但「边车进程自身为何那一次慢 6 倍」未定位到具体机制**（不排除宿主机瞬时资源争用）。
   ⇒ 🔴 **若 reviewer 需要可复现的「慢轮」样本，本轮无法提供**（未复现）。
8. ⛔ 本节**未跑 CPU 推理**（两轮都持锁 + 45 s 安静窗口）；**未向 MiniMax**；**未开 FTP**；
   **未跑 `verify_pkg_zip.py` / `publish_ftp.py`**；**未修改 `CORRECTIONS_APP.md`**（零改动，指纹见 §88.1）；
   **未用 `git add -A`**（逐文件 `git add --`）。

### §88.8 头部字段

- `last_ack` = **APP-033**（**保持不变**：本轮**无新 reviewer 纠偏条目** ⇒ 无编号可 ack；
  本节是对**已 ack 的历史条目**（APP-027 的 V1/V2 证据缺口）做遗留事项补做）。
- 「更新时间」= **2026-10-28 21:38**（`Get-Date -Format "yyyy-MM-dd HH:mm"` **实测值**，非推算）。
'''


def main():
    with io.open(STATUS, 'r', encoding='utf-8', newline='') as f:
        text = f.read()

    assert '\r\n' not in text, 'STATUS 不是 LF ⇒ 先确认换行风格'

    # 头部 4 字段行：只改「更新时间」，其余保持
    lines = text.split('\n')
    n_update = 0
    for i, ln in enumerate(lines[:20]):
        if ln.startswith('更新时间:'):
            lines[i] = '更新时间: %s' % NOW
            n_update += 1
            break
    assert n_update == 1, '未找到「更新时间」行'

    # 当前任务行（按前缀找，不写死索引）
    n_task = 0
    for i, ln in enumerate(lines[:20]):
        if ln.startswith('当前任务:'):
            lines[i] = ('当前任务: **§88 🔴🔴 APP-027 V1（CUDA）用 §84 修好后的代码重跑 ⇒ 18 PASS / 0 FAIL ＋ '
                        'V2（争用 ABBA）两臂重跑 ⇒ `lang`/`end_reason` 全量补齐 ⇒ §87.7 遗留第 4 条闭环** '
                        '⇒ 🔴🔴🔴 **撤回 §82/§83 的 V1 RTF 数字与「RTF>1 是产品缺陷」的归因表述** '
                        '（实测证明：那是 12:38 那一轮的环境性慢，边车自报 `elapsed` 同样是 6 倍；'
                        '同代码的 14:32/14:46/21:05 三轮 P50 均 0.55~0.59）'
                        '⇒ ⛔ **本节不写「已交付」** ⇒ 🔴 **本条需等 reviewer 复核**')
            n_task += 1
            break
    assert n_task == 1, '未找到「当前任务」行'

    # 「阻塞 / 待用户决定」行：按前缀找，不写死索引
    n_block = 0
    for i, ln in enumerate(lines[:20]):
        if ln.startswith('阻塞 / 待用户决定:'):
            lines[i] = ('阻塞 / 待用户决定: ① 🔴 **§87.7 遗留第 4 条（V1/V2 的 `lang`/`end_reason` 缺失）⇒ 本轮已闭环**'
                        '（V1 重跑 18 PASS/0 FAIL；V2 两臂各 76/76 行带 `lang=zh`/`end_reason=eos`）⇒ **该遗留项不再是阻塞**；'
                        '② 🔴 **§83.5 第 1 项「RTF 归因边界」的裁定依据已被本节实测推翻**（§82 的 V1 RTF 数字出自 12:38 异常轮）'
                        '⇒ **必须重做裁定**；③ 🔴 **APP-027 仍未完**（V3-CER / V3-CAMPPlus 归 reviewer、V4 用户实听未做）'
                        '⇒ **「用户听得到」仍不成立**；④ 🔴 **旧 v1.6 zip 若已分发** ⇒ 是否需重新分发待 reviewer 裁定；'
                        '⑤ 🔴 **12:38 那一轮慢的根因未闭环到具体机制**（已排除代码/模型/venv/驱动/并发/电源；未复现）；'
                        '⑥ 🔴 **本轮未修改 `CORRECTIONS_APP.md`**（只读、零改动，指纹 90 321 B / sha256 `bb2896ee…a043` / mtime 00:47:55）、'
                        '未向 MiniMax、未开 FTP、未跑 `verify_pkg_zip.py`、**未用 `git add -A`**（逐文件 add）')
            n_block += 1
            break
    assert n_block == 1, '未找到「阻塞 / 待用户决定」行'

    text = '\n'.join(lines)
    if not text.endswith('\n'):
        text += '\n'
    text = text + BODY.lstrip('\n')

    with io.open(STATUS, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print('已追加 §88；STATUS bytes =', os.path.getsize(STATUS))


if __name__ == '__main__':
    main()
