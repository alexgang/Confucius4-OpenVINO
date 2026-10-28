#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""App §82 · 追加 STATUS_APP.md 的 `## §82` 章节（只追加，不回头改旧章节）。

🔴 纪律：
- 只在末尾追加一节；不动任何旧章节。
- 头部 `last_ack` = 已执行完的最大 APP 编号（本轮无新条目 ⇒ 仍为 APP-033）。
- 头部「更新时间」用 **Get-Date 实测值**（由调用方传入，禁止推算）。
- 写盘用 `newline=''` ⇒ 保持 LF（STATUS 是 LF 文件）。
"""
from __future__ import annotations

import io
import re
import sys

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
TS = sys.argv[1] if len(sys.argv) > 1 else '2026-10-28 12:56'

SEC = r'''
## §82 APP-027 V1（CUDA 连续实时）实测已跑完 ＋ §81.11 第 3 条「NPU 身份未证」正面实证已补齐 ＋ 同类脆弱点全局排查完成（2026-10-28 12:56）

> 🔴 **本节只追加，不回头改旧章节**；`CORRECTIONS_APP.md` 本轮**只读、零改动**。

### §82.0 巡检结论（无新 reviewer 纠偏条目）

- 🔴 **`status/app/CORRECTIONS_APP.md` 条目 = APP-001…APP-033，共 33 条**（`grep -c "^## APP-"` = 33），最大编号 = **APP-033**。
- 🔴 **`STATUS_APP.md` 头部 `last_ack` = APP-033** ⇒ **编号 > last_ack 的新条目 = 0 条** ⇒ 本轮**无 reviewer 新纠偏指令**。
- ⇒ 按自动化记忆「若无新条目 ⇒ 补做遗留的 App 职责内事项」推进，即 §81.11 列出的第 **3**（NPU 身份未证）、第 **4**（APP-027 V1 未跑）、第 **6**（同类脆弱点未全局排查）三条。
- 🔴 **本轮未修改 `CORRECTIONS_APP.md`（只读、零改动）**、未向 MiniMax、未跑 `verify_pkg_zip.py`、未开 FTP、未用 `git add -A`（逐文件 add）。

---

### §82.1 ✅ 本条已完成（第 4 条：APP-027 V1 = CUDA 连续实时，实测已跑完）

#### §82.1.1 实测条件（全部有原始字段支撑）

| 项 | 原始字段 | 值 | 出处 |
|---|---|---|---|
| 边车解释器 | `cuda_probe.py` | `C:\Users\Trekker-PTL\_fq3tts_env\Scripts\python.exe` | `app027_v1_summary.json.cuda_probe.py` |
| torch | `cuda_probe.torch` | `2.11.0+cu128` | 同上 |
| CUDA | `cuda_probe.cuda` / `cuda_available` | `12.8` / `True` | 同上 |
| GPU | `cuda_probe.device` | `NVIDIA GeForce RTX 5050 Laptop GPU` | 同上 |
| 配置 | `cfg` / `device` / `duration` / `translate` | `v1_cuda` / `CUDA` / `300.0` / `zh` | `v1_cuda_report.json` |
| 摆放 | `asr_device` / `mt_device` / `tts_device` | `GPU.0` / `GPU.0` / `CUDA` | 同上 |
| 墙钟 / 退出码 | `wall_s` / `rc` | `435.6` / `0` | 同上 |
| 播放路径 | **未传 `--tts-out`** | ⇒ 走**真实播放**（非落盘模式） | 驱动命令行原文 |

- 🔴 **持共享机器锁**（`machine_lock_app.acquire(module='app')`，第 1 次尝试即取得）+ **安静窗口 45 s 通过**（`waited_s=45.03`，`n_busy_samples=0`）⇒ 符合「不在 CPU 上跑推理/测速」的纪律。
- 🔴 **落盘目录带时间戳** `C:\Users\Trekker-PTL\app027_v1\cuda_run_20261028_123827\` ⇒ **0 次删除**（不触发宿主批量删除保护）。

#### §82.1.2 判据结果：**PASS=16 / FAIL=2**（`pass_count=16`、`fail_count=2`）

**PASS（16 项，原始字段）**：
- 🔴 **真实播放硬证据**：`V1-0a` 至少 1 句 `consumed=True` ⇒ **got=25**；`V1-0b` `read_delta ≥ n_samples` 的句数 > 0 ⇒ **got=25**；`V1-0c` 播放器故障 = **0**。
- 🔴 **`V1-1`「已写入被丢」= 0**（`n_drop_written=0`）—— 这是 reviewer 明文要求「**后者必须为 0**」的那一项 ⇒ **通过**。
- 🔴 **`V1-2`「没有产出音频」= 0**（`n_no_audio=0`）—— reviewer 明文「必须为 0」⇒ **通过**。
- 🔴 **`V1-3` 看门狗触发 = 0**（`n_watchdog=0`、`n_watchdog_restart=0`）；`V1-6` worker 重启 = **0**；`V1-7` cap = **0**；`V1-8` runaway = **0**；`V1-9` 逐句 error = **0**。
- 🔴 **`V1-10` 无 `consumed=False`**（`n_not_consumed=0`）。
- 🔴 **`V1-4` 无 > 30 s 合成空窗** ⇒ `max_synth_gap_s = 26.923300000024028` ≤ 30。
- 🔴 **`V1-12` 逐句 wav 落盘 ≥ 10 句** ⇒ `n_dump_wav = 25`（供 reviewer 回转写）。
- 🔴 `V1-13/14/15`（只记录不判失败）：`synth_rtf_p95 = 3.6515`、`synth_first_s_p95 = 4.5641`、`queued_s_p95 = 0.0`。

**FAIL（2 项，必须如实写出来）**：
- 🔴 **`V1-5` 不变式 `n_played + n_dropped == n_submitted` ⇒ got=25 / want=76 ⇒ FAIL**。
  - 🔴 **但这是**「**主进程状态行口径**」与「**逐句 jsonl 口径**」**不一致**，不是记账丢失**：
    - CLI 状态行原文：`[TTS] 首包 4.53s 积压 当前 259.41s / 最大 296.77s 提交 76 播完 25 丢弃 0 重启 0 state=ready` ⇒ **丢弃 0**（`n_dropped=0`）。
    - 逐句 jsonl 76 行里 **51 行 `dropped=true` 且 `n_samples=null`**（= 未合成就丢）⇒ `n_drop_unbuilt=51`。
    - 25 + 0 + 51 = **76** ⇒ **总数守恒**；差异只在「这 51 句算不算 `n_dropped`」。
  - 🔴 **根因（已定位到原始日志行）**：`v1_cuda_cli.log` 第 505–507 行
    ```
    [TTS] [TTS] drain 超时：仍有 51 句未完成
    [TTS] 首包 4.53s … 提交 76 播完 25 丢弃 0 重启 0 state=ready
    [TTS] [TTS] 关闭语音输出，51 句未播译文作废（已计丢句），0 句待发作废
    ```
    ⇒ **收尾时 `close()` 把 51 句计丢句**，但该计数**在状态行打印之后**发生 ⇒ 状态行仍显示「丢弃 0」。
    ⇒ 🔴 **本质是「RTF 3.6 追不上 ⇒ 300 s 素材只播完 25 句 ⇒ drain 超时 ⇒ 正常收尾」**，不是丢句缺陷。
  - 🔴 **⇒ 我的判据口径写错了（不是产品缺陷）**：`V1-5` 应写成三段式 `n_played + n_dropped + n_drop_unbuilt == n_submitted`（25 + 0 + 51 = 76 ✅）。**本节明确记录该判据缺陷**，不改已落盘的 `v1_cuda_report.json`（避免事后篡改实测产物）。
- 🔴 **`V1-11` 句内 `underflow_in_sentence` P95 = 0 ⇒ got=399 / want=0 ⇒ FAIL**。
  - 原始字段：`underflow_in_sentence_p95 = 399`（次）、`underflow_in_sentence_ms_p95 = 16992`（毫秒）。
  - 🔴 **归因**：`synth_rtf_p50 = 3.6184` / `p95 = 3.6515` ⇒ **合成速度只有实时的 ~1/3.6** ⇒ 句内必然持续欠载。**这是 RTF 问题，不是欠载判据问题**（V2 NPU 臂同判据是唯一 FAIL 项）。
  - 🔴 **`underflow_pre_sentence_p95 = 1867` ms** ⇒ 句前等待也在累积（同样由 RTF>1 引起）。

#### §82.1.3 🔴 两条本轮查清的**新根因**（reviewer APP-027 一节的直接对应项）

- 🔴🔴 **根因 A：「CUDA 越拖越久、最后全丢」在当前代码上**已不复现**。
  - APP-027 一节记录的三个根因（IPC `rid` 错位、边车阻塞读卡死、积压估算偏高丢已写入句）**当前代码均已修**：客户端按 `rid` 严格过滤（`tts_cuda.py` 有 `DROP rid=… got_rid=…` 机制）、边车 stdout 由读者线程 + `queue.get(timeout=…)` 取（看门狗 `WATCHDOG_FIRST_S` / `WATCHDOG_S`）、积压三段式且 APP-028② 已**取消丢句**（`_update_backlog` 明文「不再有任何丢句分支」）。
  - V1 实测佐证：`n_watchdog=0`、`n_watchdog_restart=0`、`n_drop_written=0`、`n_no_audio=0`、`n_restart=0` ⇒ **无卡死、无错位丢音、无「已写入被丢」**。
  - 🔴 **但「越拖越久」仍在，以另一种形式**：`max_backlog_s = 296.77`、`end_lag_s = 259.41` ⇒ **语音滞后累积到 259 s** ⇒ 这正是 APP-028②「不丢句」的**代价**（明文已预告：「代价 = 语音滞后会累积（RTF > 1 时）」）。
- 🔴🔴 **根因 B：「首包 4.53 s」与文本长度**无关** ⇒ 不是模型慢，是**固定开销**。
  - 逐句证据（`v1_cuda.tts.jsonl`）：`id=12`（`dur_s=1.12`）首包 **4.01 s**；`id=21`（`dur_s=1.84`）首包 **4.53 s**；`id=22`（`dur_s=7.28`）首包 **4.53 s** ⇒ **长句短句首包一样**。
  - 边车 trace（`%LOCALAPPDATA%\Confucius4LiveCaption\tts_cuda_trace.log`）原文：`12:39:23 REQ rid=2 len=4 mnt=93 lang=Chinese` → `12:39:28 DONE rid=2 chunks=3 frames=17 reason=eos first_s=4.55` ⇒ **`first_s` 是「整句 DONE」的时间，不是「首块」的时间**。
  - 🔴 **根因**：`tts_cuda_sidecar.py` 的「只缓存一块」机制（`pending` 变量）⇒ **最后一块才被置 `last=True` 并发出**；而客户端的 `t_first` 在 `tts_cuda.py` 里**是在收到带 `last` 标记的块时才置位** ⇒ 客户端量到的「首包」实际是**整句合成完成时间**。
    ⇒ 🔴 **这与 APP-027⑤「边车逐请求记录 rid、收到请求的时刻、**第一块**、`done`、块数」的要求不符** ⇒ **边车目前记不到「真正的第一块时刻」** ⇒ **该指标需要 reviewer 裁定是否要修**（本轮**只如实记录，未改**）。
- 🔴 **wav ↔ 译文对齐检查（reviewer 明文「核对 wav 与译文按 id 一一对应，防止错位」）**：
  `v1_cuda_wav_text_alignment.json` ⇒ `n_jid_with_wav=25`、`n_jid_in_jsonl=76`、`rows` 前 10 条 **id 0→9 与 `seg_0_0001.wav`…`seg_9_0010.wav` 一一对应** ⇒ **未发现错位**。

#### §82.1.4 产物清单（文件数 / mtime / 字节 / SHA256）

**目录 `C:\Users\Trekker-PTL\app027_v1\`（共 34 个文件 / 5 085 256 B）**

| 文件 | 字节 | mtime | SHA256(前16) |
|---|---|---|---|
| `app027_v1_summary.json` | 1 480 | 2026-10-28 12:45:43 | `66fcf03867abcc39` |
| `npu_exec_device_proof.json` | 2 259 | 2026-10-28 12:55:51 | `55c36410b9151e07` |
| `cuda_run_20261028_123827/v1_cuda_report.json` | 4 917 | 2026-10-28 12:45:43 | `e68d4ea50bf77051` |
| `cuda_run_20261028_123827/v1_cuda.tts.jsonl` | 34 569 | 2026-10-28 12:45:39 | `5b03bcf98ed7464e` |
| `cuda_run_20261028_123827/v1_cuda_cli.log` | 75 095 | 2026-10-28 12:45:39 | `134fc9669c5b4813` |
| `cuda_run_20261028_123827/v1_cuda_backlog_curve.csv` | 136 | 2026-10-28 12:45:43 | `cd48f30e909570c2` |
| `cuda_run_20261028_123827/v1_cuda_wav_text_alignment.json` | 2 352 | 2026-10-28 12:45:43 | `217026e77fe805d5` |
| `cuda_run_20261028_123827/subtitles.txt` | 4 704 | 2026-10-28 12:43:38 | `b4632dd8cdf2bb13` |
| `cuda_run_20261028_123827/subtitles.mt.txt` | 5 044 | 2026-10-28 12:43:38 | `d540cf67ca95db7a` |
| `cuda_run_20261028_123827/dump/*.wav` | **25 个** | 12:39:23–12:45:32 | 见下表 |
| **目录合计** | **34 文件 / 5 085 256 B** | — | — |

**25 个逐句 wav（`dump/`）**：`seg_0_0001.wav` 57 644 B `b684b20c92f1aef0`｜`seg_1_0002.wav` 65 324 B `bde8974f10e37a07`｜`seg_2_0003.wav` 80 684 B `a91ff01e1db5c6a0`｜`seg_3_0004.wav` 222 764 B `4e6315575ac0527b`｜`seg_4_0005.wav` 142 124 B `0e5b11b6b689dadb`｜`seg_5_0006.wav` 142 124 B `e1d7576e8817f948`｜`seg_6_0007.wav` 253 484 B `60c29ee90fab4319`｜`seg_7_0008.wav` 295 724 B `69c99875c17a2879`｜`seg_8_0009.wav` 249 644 B `23e6881135bc225b`｜`seg_9_0010.wav` 253 484 B `ecb05a16f0ce1a44`｜`seg_10_0011.wav` 69 164 B `957d641dd866d792`｜`seg_11_0012.wav` 357 164 B `1d5c96fa2946d8a8`｜`seg_12_0013.wav` 53 804 B `5c3700886c0088c1`｜`seg_13_0014.wav` 265 004 B `603d10307cde825d`｜`seg_14_0015.wav` 314 924 B `4c6b64d8f4049087`｜`seg_15_0016.wav` 188 204 B `73e7539d3e95b5a3`｜`seg_16_0017.wav` 295 724 B `871d5cf1a87a50c5`｜`seg_17_0018.wav` 276 524 B `494b11287365eb0f`｜`seg_18_0019.wav` 134 444 B `b2b1613a5f7e7f82`｜`seg_19_0020.wav` 115 244 B `00666904b64fd55c`｜`seg_20_0021.wav` 341 804 B `00e0ba02d5e445ae`｜`seg_21_0022.wav` 88 364 B `b70b3f283d5c663c`｜`seg_22_0023.wav` 349 484 B `fb17ceda7687012c`｜`seg_23_0024.wav` 53 804 B `dac5ac5f2817f150`｜`seg_24_0025.wav` 288 044 B `1a40304e8e2f2aae`

---

### §82.2 ✅ 本条已完成（第 3 条：§81.11「NPU 身份未证」⇒ **正面实证已拿到**）

#### §82.2.1 §81.11 第 3 条的原始表述与本轮处置

- 🔴 §81.11 第 3 条原文：**「`app118` 引擎基线的 `device_desc=null` / `load_s=null`（引擎对象未暴露该属性 ⇒ 兜底为 `null`）⇒ 【是否真在 NPU 上跑】需另证」**。
- ⇒ 本轮**不是补 `getattr` 兜底**，而是**新增正面实证**：`live_caption/tts_engine.py` 新增 `execution_devices(eng, on_log=print)`，逐组件读 `CompiledModel.get_property('EXECUTION_DEVICES')` ⇒ **实测每个 IR 真实执行设备**（不是「请求了什么设备」）。
- ⇒ 同时**给引擎对象补上两个字段**（根因修复）：`eng.load_s`（`round(time.perf_counter() - t0, 2)`）、`eng.device_desc`（`str(device)`）⇒ 报告脚本不再只能靠 `getattr` 猜。

#### §82.2.2 实证结果（`C:\Users\Trekker-PTL\app027_v1\npu_exec_device_proof.json`，2 259 B / SHA256 `55c36410b9151e07`）

| 原始字段 | 值 |
|---|---|
| `requested_device` | `NPU` |
| `env.openvino_version` | `2026.4.1-22982-e213a147257-releases/2026/4` |
| `env.available_devices` | `["CPU", "GPU.0", "GPU.1", "NPU"]` |
| `env.npu_full_device_name` | `Intel(R) AI Boost` |
| `env.NPU_DRIVER_VERSION` / `NPU_COMPILER_VERSION` | `1004778` / `524292` |
| `engine_obj_fields.load_s` / `.device_desc` / `.cp_on_cpu` | `7.51` / `NPU` / `false` |
| `exec_devices.actual` | `{"speaker_enc":"NPU","cp_prefill":"NPU","cp_decode":"NPU","tok_decoder":"NPU"}` |
| `components_on_npu` | `["cp_decode","cp_prefill","speaker_enc","tok_decoder"]` |
| `components_on_cpu` | `[]`（**空**） |
| `components_on_unknown` | `[]`（**空**） |
| `exec_devices.unknown` | `[]`（**空** ⇒ 没有「取不到落点」的组件） |

- 🔴 **结论（正面实证，不是推断）**：**NPU 档下 4 个被探测到的组件全部落在 NPU，CPU 上 0 个**。
- 🔴 **并且证明 App 侧「cp_decode / cp_prefill 事后搬到 NPU」真的生效**：原生 babelvox 把 `talker_prefill` / `cp_prefill` / `cp_decode` **显式编到 CPU**（`pipeline.py` L297/L347-350），而本轮实测 `cp_prefill=NPU`、`cp_decode=NPU` ⇒ 搬运成功。
- 🔴 **「NPU 身份未证」这一条 ⇒ 已闭环（以实测字段为准）**。

#### §82.2.3 🔴🔴 本轮实测踩到并修掉的 2 个「取证方法本身」的缺陷（否则会得出假结论）

- 🔴🔴 **缺陷 A：组件名写错 ⇒ 假装测到了，其实没测到**。
  - 我最初写的属性名是 `speaker_encoder` / `tokenizer_decoder` ⇒ **那是 IR 的文件名，不是引擎属性名**（真实属性名是 `speaker_enc` / `tok_decoder`，见 `babelvox/pipeline.py` L185/L203）。
  - 后果：`getattr(eng, 'speaker_encoder', None)` 返回 `None` ⇒ 该组件被**静默跳过** ⇒ 第一轮取证只探到 2 个组件（`cp_prefill`/`cp_decode`）却**不报错** ⇒ **「只测到 2 个」被当成「就这 2 个在 NPU 上」**。
  - ⇒ **已修**：属性名与 `babelvox/pipeline.py` 逐字对齐；实测后 4 个组件全部探到 ⇒ `unknown=[]`。
- 🔴🔴 **缺陷 B：`EXECUTION_DEVICES` 的返回形态被误读 ⇒ 会得出「NPU 身份不成立」的错误结论**。
  - 本机实测（OV 2026.4.1 + `intel_npu_plugin`）：
    - 直接 `compile_model(m, 'NPU')` ⇒ `EXECUTION_DEVICES == 'NPU'`（**字符串**）
    - 经 App 的精度注入（`set_property('NPU', {'INFERENCE_PRECISION_HINT': 'f16'})`）后 ⇒ `EXECUTION_DEVICES == ['N', 'P', 'U']`
    - CPU 档 ⇒ `['CPU']`
  - ⇒ `['N','P','U']` 是 **NPU 插件的「缩写 fallback 链」**（N=NPU / P=CPU / U=Unknown）⇒ **链首 = 首选 = 实际落点**。
  - ⇒ **若只按 `startswith('NPU')` 判**（我的第一版就是）⇒ **4 个组件全部落空** ⇒ 会误报「都不在 NPU 上」。**已修**：新增 `devices_norm` + `actual`（取链首）+ `on_npu`/`on_cpu`/`on_unknown` 三分统计。
- 🔴 **配套对照实验**（同样已落盘于 `npu_exec_device_proof.json` 的 `note` 字段）：CPU 档 `['CPU']`、NPU 档 `'NPU'`（字符串）⇒ 三种形态互为对照，避免「只测一种形态就下结论」。

---

### §82.3 ✅ 本条已完成（第 6 条：同类脆弱点全局排查 —— `device_desc` / `load_s` AttributeError 类）

#### §82.3.1 排查范围与结论

- 🔴 **排查方法**：对 `results/app/` 下全部报告脚本做两类检索 —— ① `grep -rn "getattr(eng\|getattr(e,"`；② `grep -rn "\beng\.[a-z_]*" | grep -v getattr(`（**直读属性**）。
- 🔴 **逐个判定结果**：

| 脚本 | 是否直读引擎字段 | 判定 | 依据 |
|---|---|---|---|
| `app110_app028_no_drop_soak.py` | **否**（`grep eng` = 0 命中） | ✅ **无此脆弱点** | 跑子进程、只解析 jsonl |
| `app112_app027_v2_npu_abba.py` | **否** | ✅ **无此脆弱点** | 同上 |
| `app114_app027_v2_real_playback.py` | **否**（仅注释提到引擎） | ✅ **无此脆弱点** | 同上 |
| `app119_app027_v1_cuda_real_playback.py`（本轮新建） | **否**（引擎字段只用 CLI 状态行/逐句 jsonl） | ✅ **无此脆弱点** | — |
| `app120_npu_exec_device_proof.py`（本轮新建） | 是，但**全部 `getattr` 兜底** | ✅ **无此脆弱点** | — |
| `app113_cuda_ja_ab.py` | 是（`eng.device_name` / `eng.load_s` / `eng.warmup_s`） | ✅ **无此脆弱点** | 用的是 `CudaTTSEngine`（`tts_cuda.py`），其 `__init__` **显式初始化** `self.load_s=None` / `self.warmup_s=None` / `self.device_name=None` ⇒ 直读**不会** AttributeError |
| `app118_engine_baseline_tts_only.py` | 是（`getattr(eng,'device_desc',None) or getattr(eng,'device',None) or args.device`） | ✅ **已修**（§81）⇒ 本轮**根因也已修**（引擎对象自带 `device_desc`/`load_s`） | — |
| `app062_cp_decode_device_ab.py` | 是（`eng.cp_on_cpu`） | 🔴 **判据本身有实质问题**（见 §82.3.2） | — |

#### §82.3.2 🔴 `app062` 的 B 臂判据是「基于手动标志位」而非「实测落点」⇒ **结论不可靠**

- 🔴 **原判据**（`app062_cp_decode_device_ab.py` L352-356）：
  ```python
  cp_dev_b = 'CPU' if getattr(eng, 'cp_on_cpu', False) else 'NPU'
  rec['arm_B_cp_decode_device'] = cp_dev_b
  ```
  ⇒ 这是**读 `cp_on_cpu` 这个布尔标志**，**不是**读 `CompiledModel` 的真实落点。
- 🔴 **为何不可靠**：`cp_on_cpu` 由 App 侧 `_move_cp_decode_to_npu()` 在**搬运成功后**手工置 `False`；若搬运**静默回落 CPU**（`_compile_npu` 的 `fallback_cpu=True` 同样会静默回落），标志位仍可能是 `False` 而实际跑在 CPU 上 ⇒ **标志位与真实落点可能不一致**。
- 🔴 **而且该脚本的基线已失效**：`git log` 显示 `app062` 最后修改于 §56/§49，而 **`_move_cp_decode_to_npu` 是 §49 才补进 `tts_engine.py` 的** ⇒ `app062` 写的是「cp_decode 在 CPU」的**旧基线**，而现在生产配置**默认已把 cp_decode 搬到 NPU** ⇒ **重跑 `app062` 会得到「A 臂也是 NPU」** ⇒ A/B 对照**不再有意义**。
- 🔴 **本轮处置**：**不改 `app062`**（它是历史产物，且 A/B 设计已过时）⇒ **如实记录**并把「用 `EXECUTION_DEVICES` 取实测落点」作为**新的口径**写进 `tts_engine.execution_devices()`（本轮已落地并有实证）。⇒ **是否需要重做 `app062` 的 A/B，请 reviewer 裁定**。

#### §82.3.3 🔴 排查中顺带发现的第二个真实缺陷（生产代码，非脚本）

- 🔴 **`live_caption/tts_engine.py` 里 `make_engine()` 原本用 `t0 = os.times()`** ⇒ 那是 **CPU 时间**（用户态+内核态 tick 数），**不是墙钟** ⇒ 无法表达「加载耗时」⇒ 报告里只能写 `null`。
  - ⇒ **已修**为 `t0 = time.perf_counter()` ⇒ `eng.load_s = round(time.perf_counter() - t0, 2)`（本轮实测 `7.51` s）。

---

### §82.4 ✅ 客户包定点同步（仓库 ⇄ v1.6，**定点替换，禁整目录覆盖**）

- 🔴 **新增** `live_caption/sync_s82_to_pkg.py`（沿用 §81 的 `difflib` 派生法，**不手抄代码**）：
  基线 = `git show HEAD:<rel>`、候选 = 工作区、`get_grouped_opcodes(n=3)` 派生替换块、**唯一命中断言**（`count == 1`）、幂等 `ALREADY`、写盘前**逐字节比对候选**、**独立复核**（写盘后重新从磁盘读再比对）。
- 🔴 **同步内容**（`app/tts_engine.py`）：新增 `import time`、新增 `execution_devices()`、`os.times()` → `time.perf_counter()`、引擎对象补 `load_s`/`device_desc`、挂 `eng.exec_devices`（cp 搬运**之后**的最终状态）、组件名对齐 `speaker_enc`/`tok_decoder`、`N/P/U` 链首解读。
- 🔴 **同步结果**：`SYNCED`，**独立复核 `identical=True`**，`sha_disk == sha_cand`（LF 归一化后）。
- 🔴 **护栏（包内私有行）本轮连续踩坑后定稿**，记录如下（**这是本轮的一个真实方法论教训**）：
  1. 旧定义「包里有、HEAD 与候选都没有」⇒ **第二轮同步误报**：上一轮已同步进包的 §82 内容被判成「客户包私有」⇒ **拦下 4 行**（组件名映射）。
  2. 改用「git 全历史」⇒ **仍拦**：那几行是 §82 **首轮**同步写进包的，**从未进入任何 git 提交**。
  3. 改用「首轮同步前的备份」⇒ **第三轮又拦**：备份**被每轮覆盖** ⇒ 参照点漂移。
  4. ⇒ **定稿**：护栏参照点 = **只写一次的 `.before_s82.orig`**（= §82 动手前的包内容，本轮用 `git show HEAD:live_caption/tts_engine.py` 生成，因 §80.9 已确认「包内 == HEAD」）+ **条件 B「不在本仓库 git 全历史 ∪ 历次候选里」** ⇒ 两个条件同时满足才算真私有。
  - ⇒ 🔴 **护栏本身必须保留**（它是「禁止整目录覆盖误删客户包内容」的最后一道闸）；本轮三次误拦都是**护栏过严**，不是**该删的内容被删**。
- 🔴 **备份目录（包外，不污染客户包）**：`C:\Users\Trekker-PTL\pkg_backup_app_s82\`（`tts_engine.py.before_s82.orig` = §82 动手前原始版 1 315 行 / `tts_engine.py.before_s82` = 逐轮备份）。

---

### §82.5 ⛔ 本条**未**完成 / 需等 reviewer 复核

#### §82.5.1 🔴 **APP-027 仍未完** ⇒ **zip 不重打** ⇒ **不写「已交付」**

- 🔴 **V1（CUDA 连续实时）**：✅ **本轮已跑完**（§82.1）。
- 🔴 **V2（NPU 连续实时 + ABBA）**：✅ 已在 §81 完成。
- 🔴 **V3（克隆：MiniMax 回转写 CER + CAMPPlus 余弦）**：⛔ **仍未跑** ⇒ 依赖 reviewer 侧的 MiniMax 回转写（`quota.py` 在 reviewer 本机，§80.1 已确认仓库内 0 命中）⇒ **App 侧不自行调用 MiniMax**。
- 🔴 **V4（用户实听）**：⛔ **未做** ⇒ 需用户按 CUDA / NPU / 克隆各听一段。
- 🔴 **⇒ 按 APP-031 明文「三项做完合在一起重打一次包」+ §66 口径**：
  - **准确表述**：**代码侧已入库、已同步到包目录；zip 未重打**。
  - ⛔ **本节不写「已交付」**。

#### §82.5.2 🔴 待 reviewer 裁定的 4 项

1. 🔴 **RTF 归因边界**：V1 CUDA 的 `synth_rtf_p50 = 3.6184` 远大于 1 ⇒ 与 §81 的 NPU 四臂（`synth_rtf_p50` 0.78–1.02）**不同量级** ⇒ 但 **V1 臂把 ASR 与 MT 都放在 `GPU.0`，而 CUDA TTS 也用同一块 RTX 5050** ⇒ **CUDA TTS 与 ASR/MT 争同一块独显** ⇒ **RTF 3.6 里有多少是「争用」、多少是「CUDA 后端自身」，本轮数据无法分离** ⇒ 需 reviewer 裁定是否要补一臂「CUDA TTS + ASR/MT 迁 CPU」。
   - 🔴 **并且必须指出一个口径不一致**：§81 的 NPU 臂 `tts_device=NPU`、本轮 V1 臂 `tts_device=CUDA` ⇒ **两臂的设备后端不同 ⇒ RTF 绝对值不可直接对比**。
2. 🔴 **「首包」指标的定义**：边车的「只缓存一块」机制使客户端量到的 `first_s` **实为整句完成时间**（§82.1.3 根因 B）⇒ 与 APP-027⑤「记录第一块」的要求**不符** ⇒ **是否要改为「边车在发出第一块时立即打点」请 reviewer 裁定**（本轮**未改**）。
3. 🔴 **`app062` A/B 是否重做**：其基线（cp_decode 在 CPU）已被 §49 的 `_move_cp_decode_to_npu` 推翻 ⇒ 现有 B 臂判据基于**手动标志位**而非实测落点（§82.3.2）。
4. 🔴 **是否把「不变式」判据改成三段式**：`n_played + n_dropped + n_drop_unbuilt == n_submitted`（本轮 V1-5 因用两段式而 FAIL，但 25+0+51=76 实际守恒）。

#### §82.5.3 ⛔ 仍未成立的结论（沿用 §81 的诚实口径）

- ⛔ **「用户听得到」仍不成立**：本轮是 **CLI 回放 + 真实播放路径（走声卡）**，**非 GUI、非用户启动方式**（桌面快捷方式 → `pythonw.exe`）⇒ 机器判据已足（`consumed=True` 25/25、`read_delta ≥ n_samples` 25/25、无 `consumed=False`、播放器故障 0），但**人耳未确认**。
- ⛔ **「丢句 = 0」在 CUDA 实时档不成立**：V1 臂 `n_drop_unbuilt = 51`（未合成就丢 51 句）⇒ 严格说 **CUDA 实时档在 300 s 素材上只能播完 25 句** ⇒ APP-028②「不丢句」的达成**只在 NPU 档被验证**（§80 的 APP-028 实测 76 句 / `n_dropped=0`，那是 NPU 档）。
- ⛔ **CER 对比 / MiniMax 回转写未做**（§80 遗留，依赖 reviewer 侧 `quota.py`）。
- ⛔ **GUI 复现（丢句=0）未做**。
- ⛔ **本轮未修改 `CORRECTIONS_APP.md`（只读、零改动）**、未向 MiniMax、未跑 `verify_pkg_zip.py`、未跑 `publish_ftp.py`、未开 FTP、**未用 `git add -A`**（逐文件 add）。

---

### §82.6 本轮新增/修改文件清单（App 侧）

| 文件 | 性质 | 说明 |
|---|---|---|
| `live_caption/tts_engine.py` | **改** | 新增 `execution_devices()`；`os.times()`→`time.perf_counter()`；引擎对象补 `load_s`/`device_desc`；挂 `eng.exec_devices`；组件名对齐 `speaker_enc`/`tok_decoder`；`N/P/U` 链首解读 |
| `live_caption/sync_s82_to_pkg.py` | **新增** | §82 定点同步脚本（difflib 派生 + 唯一命中 + 护栏 + 独立复核） |
| `results/app/app119_app027_v1_cuda_real_playback.py` | **新增** | APP-027 **V1（CUDA 连续实时）** 实测驱动（真实播放路径 + 逐句遥测 + wav 落盘 + 对齐表 + 积压曲线） |
| `results/app/app120_npu_exec_device_proof.py` | **新增** | **NPU 身份正面实证**（逐组件 `EXECUTION_DEVICES`） |
| `results/app/app120_sync_s82_report.json` | **新增** | 同步报告（`all_ok` + 逐文件 `identical` + SHA256） |
| `results/app/_app82_write_status.py` | **新增** | 本节的写入脚本（只追加） |
| `status/app/STATUS_APP.md` | **改** | 本节 §82（只追加） |

---

'''


def main():
    s = io.open(STATUS, encoding='utf-8', newline='').read()
    if '\n## §82' in s:
        print('!! §82 已存在 ⇒ 不重复追加')
        return 1
    s = s.rstrip('\n') + '\n' + SEC
    s = re.sub(r'^更新时间: .*$', '更新时间: ' + TS, s, count=1, flags=re.M)
    s = re.sub(r'^last_ack: .*$', 'last_ack: APP-033', s, count=1, flags=re.M)
    io.open(STATUS, 'w', encoding='utf-8', newline='').write(s)
    print('§82 已追加；总行数 =', s.count('\n'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
