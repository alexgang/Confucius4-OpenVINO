# ASR-056 明细 —— STATUS_ASR §81 的全文

> 🔴 **本文件是 `status/asr/STATUS_ASR.md` §81 的明细全文**（ASR-036：长日志、明细归 notes）。
> **数字必须逐字来自产物 json**；每个数字都写了 json 路径 + 字段名。
> 本轮：**未打包、未动 App 树 / 客户包 / `live_caption/`、未补跑 61 分钟、
> 未重跑 10 分钟 WER、未做新的导出或量化**（ASR-056 §3「不做的事」逐条遵守）。

---

## 0. 本轮范围（ASR-056 的 6 项）

| # | 纠偏要求 | 状态 |
|---|---|---|
| ① | §79 正文 4 处旧结论标撤回；「已撤回的旧结论」清单补 3 条 | ✅ §81 ① |
| ② | 旧计时 json 标 `unverified` / 补 `lock_record`；`bk_run.py` 无锁改 `"no_lock"` | ✅ §81 ② |
| ③ | 清 json 里的跨脚本比较块；`asr138*` 加 `superseded_by` | ✅ §81 ③ |
| ④ | 关键数字表补 300 s / 18 s 并排行；提速写区间；NPU 首字延迟归因 | ✅ §81 ④ |
| ⑤ | 套件最终版脚本持锁补跑 4 组 + 验收 | ✅ §81 ⑤ |
| ⑥ | 套件交付前小修 a–f | ✅ §81 ⑥ |

---

## 1. ① §79 正文 4 处标撤回（**只加标注，不删原句**）

**做法**：在 §79 的 4 处**结论句**行首加 `🔴 **（已撤回，见 §80：…）**`。
**没有删除或改写任何原句**（铁律：旧章节只追加、不回头改）。

| 处 | 原句（截） | 加的标注 |
|---|---|---|
| §79② | 「⇒ **判断成立**（不开 NPUW 报 `to_shape…`，开 NPUW 即编过）。」 | 纠偏已核实 `asr130…json` → `verdict.reviewer_hypothesis_npuw_only` = `"REFUTED"`；开 NPUW **仍**报 `to_shape`。真条件 = `inputs_embeds`-only 端口形态 ＋ `NPUW_LLM` 缺一不可 |
| §79④ | 「⇒ **iGPU 上 RTF 降到 mask2 的 0.38×（≈2.6× 加速）、出字延迟降到 0.39×（≈2.6×）**…」 | mask2 基线取自 10-25 旧 runner ⇒ **跨脚本**；同脚本同口径的提速见关键数字表，且 **NPU 出字延迟反而慢 17%** |
| §79⑥ | asr138 表内「stateful NPU … **0.2251 pp** … **True**」 | 5 块 CI 无意义；按段配对（93 块）后 `significant_worse` = **false** |
| §79 61 分钟 | 「⇒ ⚠️ **61 分钟口径下显著差、10 分钟口径下不显著** ⇒ 差异**随素材长度变化**…」 | **「随素材长度变化」已删** ⇒ 改成「**跨脚本，不作为 stateful 更差的证据**；**<1pp 不作决策依据**；**不补跑 61 分钟**」 |

### 1.1 「已撤回的旧结论」清单补 3 条（追加在 §80 之前）

* §79② 的「旧 `ov-dec-06b-past-int8` 在 NPUW 下即编过 ⇒ **判断成立**」⇒ ASR-055 已撤回。
* §79④ 的「**RTF 降到 mask2 的 0.38×（≈2.6× 加速）、出字延迟降到 0.39×**」⇒ ASR-055 已撤回。
* §79⑥ 的「stateful NPU 对 mask2 GPU **显著变差 True**」⇒ ASR-055 已撤回。

---

## 2. ② 旧计时 json 标 `unverified`

### 2.1 证据查找过程

* 找锁记录：`qwen3asr_06b\.venv\Scripts\_lock_record_*.json` ⇒ **6 个**，全部是
  **13:18–13:45 的套件自测**（`task` = `bk_selftest_stateful_GPU0_300s` /
  `bk_selftest_torch_mel_GPU0_300s` / `bk_diag_mel*`），**与下面这些产物无对应关系**。
* `shared/` 下的 `.MACHINE_LOCK.released_*` ⇒ 最新的是 **10-10**，**没有 11-11 的**。
⇒ **找不到锁证据** ⇒ 按 ASR-055 §2.5「找不到证据就标 `unverified`，**不要求重跑**」处理。

### 2.2 改了哪 10 个文件、哪些字段

| 文件 | 改的字段 |
|---|---|
| `results/asr135_bench_GPU0.json` | 顶层 `timing_valid`（`True`→`"unverified"`）、`timing_note`（新增说明）；`mask2_baseline_same_kpi.timing_valid` / `.timing_note` |
| `results/asr135_bench_NPU.json` | 同上 |
| `results/asr135_stream_GPU0/summary.json` | `timing_valid`、`timing_note` |
| `results/asr135_stream_NPU/summary.json` | 同上 |
| `results/asr138_10min_stateful_GPU0/summary.json` | 同上 |
| `results/asr138_10min_stateless_GPU0/summary.json` | 同上 |
| `results/asr138_10min_stateful_NPU/summary.json` | 同上 |
| `results/asr138_10min_stateless_NPU/summary.json` | 同上 |
| `results/asr133_stateful_61min_gpu/summary.json` | 同上 |

**除 `timing_valid` / `timing_note` 外，一个字段都没动**（脚本改前/改后逐字段核对，
只允许这两类路径变动 ⇒ **0 处非预期变动**）。

### 2.3 `bk_run.py` 的 `no_lock`

**原状**（`b_kit_stateful/scripts/bk_run.py`）：无 `ASR_LOCK_RECORD` 环境变量时
`info['timing_valid'] = True`（**写死 True**）。
**现状**：无锁时写 **`"no_lock"`** ＋ `timing_note` 说明「B 机没有共享锁目录 ⇒
如实记录，**不代表计时无效**，但**不得**声称持锁测得」。
（有锁时仍按锁记录驱动：`true` / 锁记录回填不完整则 `"unverified"`。）

---

## 3. ③ json 里的跨脚本比较块清理

### 3.1 改了哪 4 个文件、哪些字段

| 文件 | 改动 |
|---|---|
| `results/asr135_bench_GPU0.json` | `comparison_vs_mask2` ⇒ **改名为 `cross_script_ref_1025`** ＋ 加 `"comparable": false` ＋ `"legacy_10_25_baseline": true` ＋ `note` 改写；其内 `metrics.*.stateful` ⇒ **`this_arm`**、`stateful_better` ⇒ **`this_better`** |
| `results/asr135_bench_NPU.json` | 同上 |
| `results/asr147_bench_mask2_GPU0.json` | 同上（**这一处原来把 mask2 自己标成了 `stateful`** ⇒ 标签颠倒，已修） |
| `results/asr147_bench_mask2_NPU.json` | 同上 |

**保留**：`comparison_same_runner_peer`（那是**同 runner、同一时段**的合法对照）。

### 3.2 `superseded_by`

* `results/asr138_wer_10min.json` ⇒ 加 `"superseded_by": "asr146_wer_seg_paired.json"`
* `results/asr138c_wer_npu_same_device.json` ⇒ 同上

理由：这 2 个文件用的是 **120 s 时间块**（10 分钟只有 **5** 块）⇒ CI 无意义、
「显著变差 True」是分块太少造成的假象 ⇒ 正式结果以 **按段配对（93 块）**的
`asr146_wer_seg_paired.json` 为准。

### 3.3 🔴 自查抓到的 1 处真缺陷（已修）

`_asr056_fix_jsons.py` 在把 `metrics.*.stateful` 改名为 `this_arm` 时，
把布尔 `stateful_better` **一并改成了 `this_better: False`** ⇒ **语义反了**
（本臂数值本来就低于 10-25 参考值 ⇒ `this_better` 必须是 **true**）。
由**独立脚本** `_asr056_repair_cross.py` 修回 **16 个布尔**（4 文件 × 4 指标），
**数值一个未动**（脚本内逐值核对）。

### 3.4 交叉核对（独立来源）

| 核对 | 结果 |
|---|---|
| `asr135_bench_{GPU0,NPU}.json` ↔ `asr135_stream_*/summary.json`（10 字段 + `rule_counts`） | **0 处不一致** |
| `asr147_bench_mask2_{GPU0,NPU}.json` ↔ `asr147_stream_mask2_*/summary.json`（同上） | **0 处不一致** |
| 18 s `text_head`：stateful vs mask2（同 prompt）GPU0 / NPU | **逐字相同** |

---

## 4. ④ 关键数字表新增 300 s / 18 s 并排行

### 4.1 同 runner 并排（出处 = json 路径 + 字段名）

| 指标 | GPU.0 stateful / mask2 | NPU stateful / mask2 | 出处 |
|---|---|---|---|
| 300 s 流式 RTF | **0.2627 / 0.5397**（**0.49×**） | **0.3496 / 0.5259**（**0.66×**） | `asr135_bench_{GPU0,NPU}.json` → `B4_stream_300s.rtf` ＋ `asr147_bench_mask2_{GPU0,NPU}.json` → `B4_stream_300s.rtf` |
| 18 s 端到端 wall | **1.4541 / 3.7929 s**（**0.38×**） | **1.706 / 4.6038 s**（**0.37×**） | 同上 → `B3_e2e_18s.wall_s` |
| 每 token p50（300 s 跑） | **16.4051 / 81.0881 ms**（**4.9×**） | **17.7664 / 89.6434 ms**（**5.0×**） | 同上 → `B1_per_token.decode_ms_p50` |
| 300 s 出字延迟 p50 | **0.0951 / 0.1317 s** | **0.1451 / 0.1264 s**（**stateful 慢 15%**） | 同上 → `B4_stream_300s.first_tok_latency_p50` |

### 4.2 🔴 GPU 提速为什么只能写区间

* mask2 GPU 的**每 token p50**：10 分钟跑 = **56.7728 ms**、300 s 跑 = **81.0881 ms**
  ⇒ **相差 42.85%**，两次都**只跑了 1 遍**。
* ⇒ **GPU 上 stateful 的提速只能写成区间**。按 **RTF 口径**：
  10 分钟 **1.6×**（0.2479 → 0.3998）、300 s **2.0×**（0.2627 → 0.5397）
  ⇒ **约 1.6–2.0×**，**不报单点**、**不要求补跑**。
  （出处：`asr138_10min_{stateful,stateless}_GPU0/summary.json` → `rtf`；
  `asr135_bench_GPU0.json` / `asr147_bench_mask2_GPU0.json` → `B4_stream_300s.rtf`）
* NPU 同口径：10 分钟 **1.5×**（0.384 → 0.5696）、300 s **1.5×**（0.3496 → 0.5259）。

### 4.3 🔴 NPU 首字延迟归因（stateful vs mask2 **同在 NPU**）

* mask2 的首 token 是**一次 512 静态前向** ⇒ `B1_per_token.decode_ms_p50` = **89.6434 ms**
  （`asr147_bench_mask2_NPU.json`）。
* stateful 的 prefill p50 = **94.7818 ms**（`asr135_bench_NPU.json` → `B2_prefill.prefill_ms_p50`）。
* ⇒ **两者量级相同** ⇒ 首字延迟持平或略慢是**预期内的**。
* （§80 另已核实：NPU 对 GPU 的 prefill 差 **34.5745 ms** 是 **stateful 在两种设备之间**的差，
  与本条**不是同一个问题**。）

---

## 5. ⑤ 套件最终版脚本持锁补跑 4 组

### 5.1 为什么必须补跑（纠偏原文的背景）

* `bk_run.py` 最后修改 **13:40**、`bk_mel.py` **13:43**，而默认 fft 自测 **13:34 完成**
  ⇒ **交给 B 的默认路径没有用最终版脚本跑过**。
* **NPU 臂和 stateless 臂一次都没有通过套件跑过**。

### 5.2 跑法

**最终版脚本 ＋ 默认 `--mel fft`（不传 `--mel`）＋ 外层 `p3_run_with_lock.py` 持锁**
⇒ 每组 `summary.json` 都带**完整 `lock_record`**（含 `released_at`/`exit_code`）
且 `timing_valid=true`。

### 5.3 结果

| 臂 | 设备 / 形态 / 时长 | `exec_devices` | `mel_mode` | `lock_record`（取锁→放锁） | 关键数字 |
|---|---|---|---|---|---|
| A1 | GPU.0 / stateful / 300 s | `['GPU.0']` | `fft` | 15:18:41 → 15:20:03，exit 0 | `rtf` **0.244** / 46 段 / **831** 词 |
| A2 | NPU / stateful / 18 s | `['NPU']` | `fft` | 15:20:03 → 15:20:47，exit 0 | `B3_e2e_18s.wall_s` **1.4672** |
| A3 | NPU / stateless / 18 s | `['NPU']` | `fft` | 15:20:47 → 15:23:24，exit 0 | `B3_e2e_18s.wall_s` **4.6058** |
| A4 | GPU.0 / stateless / 18 s | `['GPU.0']` | `fft` | 15:23:25 → 15:23:37，exit 0 | `B3_e2e_18s.wall_s` **3.7853** |

产物目录：`b_kit_stateful/results_A_local/bk_asr056_*/summary.json`。

### 5.4 验收（独立复核脚本 `scripts/_asr056_verify_kit4.py`，**不复用**写入脚本）

**31/31 PASS**：

| 验收项 | 结果 |
|---|---|
| 4 组 `exec_devices` 正确 | ✅ `['GPU.0']` / `['NPU']` |
| 4 组 `summary.json` 有 `mel_mode` | ✅ 全为 `fft` |
| 4 组 `lock_record` 完整 | ✅ 全含 `acquired_at`/`released_at`/`exit_code`=0 |
| 300 s 段界与 `asr135_stream_GPU0` **46/46 逐位同** | ✅ |
| 300 s 词数与 asr135 相同 | ✅ **831 = 831** |
| 300 s RTF 差 ±10% | ✅ **0.244 vs 0.2627 ⇒ 差 7.12%** |
| 18 s wall 差 ±15% | ✅ NPU stateful **14.00%** / NPU mask2 **0.04%** / GPU0 mask2 **0.20%** |
| 18 s `text_head` 逐字相同 | ✅ 3 组全同 |

### 5.5 B 机模拟自检（`scripts/_asr056_verify_bmachine.py`）—— **0 FAIL**

屏蔽 `torch` / `transformers` / `qwen_asr` / `scipy` / `live_caption_app` / `soundfile` 后：

* `bk_mel` / `bk_segmenter` / `bk_sha256` / `bk_run` **全部仍可 import**；
* `log_mel(mode="fft")` 正常 ⇒ 形状 **(128, 500)**、dtype **float32**；
* `--mel torch` 后端**如期 ImportError**（**不静默降级**）。

---

## 6. ⑥ 套件交付前小修 a–f

| 项 | 做了什么 |
|---|---|
| **(a)** | 新增 **`run_bk.cmd`**（Windows 版，与 `run_bk.sh` 同逻辑；解释器取自 `BK_PYTHON` 或第 1 个参数）＋ README §3.1 由「6 组」改成「**12 组**（2 形态 × 2 设备 × 3 时长）」 |
| **(b)** | 新增 **`wheels/`**（**23** 个 wheel / **107868519** B，cp312 + win_amd64 + py3-none-any 混合，含全部传递依赖）＋ README §2 给出离线命令 `pip install --no-index --find-links wheels "numpy==2.5.4" "openvino==2026.4.1" "tokenizers==0.22.2" soundfile`；并写明「B 机须 CPython 3.12 64 位」与 3.13 的重下载命令 |
| **(c)** | MANIFEST 加 **`sources`** 字段：套件文件 → 源目录 + 源 SHA（`src_rel`/`src_path`/`src_present`/`src_sha256`/`kit_sha256`/`identical`）＋ `source_root`。**stateful decoder bin 的 `src_sha256` = `0059531a2b4ccd4c…` ⇒ 与 reviewer 11-11 实算值一致**；`identical` 全为 true |
| **(d)** | 交付内容剔除 **`scripts/__pycache__/`** 与 **`results/`**（后者改名 `results_A_local/` 且**不进哈希清单**）；5 个 A-only 脚本（`bk_check_parity` / `bk_diag_mel` / `bk_mel_bench` / `bk_export_assets` / `bk_cmp_selftest`）移入 **`scripts/a_only/`**（并修它们的 `sys.path` 与 `KIT` 根路径：原来 `KIT = os.path.dirname(HERE)`，搬到子目录后须上跳两级）＋ A 机参照结果放 **`ref_A/`**（**4 组** × `summary.json` + `transcript.txt` = **8** 个文件）＋ README §8 写明「**B 上不要跑**」 |
| **(e)** | README 第 298 行「⇒ 差异**唯一根因 = FFT 实现**」⇒ 改成与 STATUS §80 一致的「**双来源**（① FFT 实现**不可消除**；② dtype/log10 环节**可消除**，`--mel torch` 与 transformers **max abs diff = 0.0**）」 |
| **(f)** | 重生成 `SHA256SUMS.txt` / `MANIFEST.json` ⇒ **61 文件 / 2348474131 B**，`bk_sha256.py --check` ⇒ **校验 61 个文件，0 处不符** |

### 6.1 套件最终目录清单

```
b_kit_stateful/                     61 文件 / 2348474131 B
├── README.md
├── SHA256SUMS.txt
├── MANIFEST.json                   （含 sources 溯源表）
├── run_bk.sh
├── run_bk.cmd
├── assets/                         356067863 B / 11 文件
├── models/                        1884374957 B / 6 文件
├── ref_A/                             37939 B / 8 文件（4 组参照）
├── scripts/                           104776 B / 10 文件（4 个核心 + a_only/ 6）
└── wheels/                          107868519 B / 23 文件
```

### 6.2 B 机一键命令

```bat
:: 1) 离线装依赖
python -m pip install --no-index --find-links wheels ^
    "numpy==2.5.4" "openvino==2026.4.1" "tokenizers==0.22.2" soundfile

:: 2) 校验完整性
python scripts\bk_sha256.py --check

:: 3) 跑（先单组试，再全跑 12 组）
run_bk.cmd
REM 或指定解释器：run_bk.cmd "C:\path\to\venv\Scripts\python.exe"
```

---

## 7. 本轮改动文件清单

### 7.1 `qwen3asr_06b\`（**不在 git 内**）

* `results/asr135_bench_{GPU0,NPU}.json`、`results/asr147_bench_mask2_{GPU0,NPU}.json`
  （§2 ②③）
* `results/asr135_stream_{GPU0,NPU}/summary.json`、
  `results/asr138_10min_*/summary.json`、`results/asr133_stateful_61min_gpu/summary.json`
  （§2 ②）
* `results/asr138_wer_10min.json`、`results/asr138c_wer_npu_same_device.json`（§3 ③）
* `b_kit_stateful/`（§6 ⑥ + §5 ⑤）
* `scripts/_asr056_*.py`（本轮的工作脚本，**不是 status_verify 类**——它们是**一次性写入/修复脚本**，
  不产生 STATUS 自审计循环；`bk_sha256.py --check` 是 ASR-055 §2.6 明确要求的**交付校验**，
  按 ASR-038 的「只禁 status_verify 类」**不在禁止范围内**）

### 7.2 `confucius4-openvino\`（**git 内，只提交本模块文件**）

* `status/asr/STATUS_ASR.md`（§81）
* `status/asr/notes/asr_s81.md`（本文件）
* `status/archive/STATUS_ASR_sec78_upto_20261111.md`（§78 全文归档，逐字保留）

🔴 **`live_caption/` 未动**；**`CORRECTIONS_ASR.md` 未提交**（reviewer 维护）。

---

## 8. STATUS 写入与压缩的最终形态（2026-11-11 15:40）

### 8.1 写入结果

| 项 | 值 |
|---|---|
| `status/asr/STATUS_ASR.md` | **159 行 / 38921 B**（原 156 行 / 39119 B）|
| 章节 | **3**（§79 / §80 / §81）|
| `last_ack` | **ASR-056** |
| 门禁 | ASR-038「≤160 行」✅ ＋ ASR-036「≤40 KB」✅ |
| 行尾 | 全 CRLF，**裸 LF = 0**、CRCRLF = 0 |
| 自指大小 | **38921 B / 159 行**（与实际**自洽**）|

### 8.2 独立复核（`scripts/_asr056_verify_status.py`，**不复用写入脚本的自检**）

**32 PASS / 0 FAIL**。覆盖：CRLF/裸 LF/CRCRLF ① 门禁（行数/字节）② 章节数与章节号
③ 头部 4 行 ④ 自指大小自洽 ⑤ 无残留 `@@`/TODO ⑥ §79 **4 处撤回标注**
⑦「随素材长度变化」已删 ⑧ 已撤回清单补 **3 条** ⑨ 关键数字表新增行
⑩ 该行 **16 个数字逐字来自产物 json** ⑪ §78 归档**逐字保留** ⑫ 被裁的最近更新条目
**逐字在归档里** ⑬ §79 正文**只有 4 处改动** ⑭ §80 正文**逐字未改**（忽略尾部空行）
⑮ 未完成纠偏表含 **ASR-056** 行。

### 8.3 🔴 压缩动作（ASR-036 门禁 ⇒ 必须做，且**逐字归档**）

写入 §81 后正文一度到 **170 行 / 48415 B** ⇒ 破两个门禁 ⇒ 做了 3 件事：

1. **§81 的明细全文移到本 notes**（ASR-036「明细归 notes」）⇒ §81 只留结论与数字。
2. **关键数字表按纠偏原文「补**一行**」**合并成 1 行**（300 s RTF / 18 s wall / 每 token p50 /
   300 s 出字 p50 ＋ GPU 提速区间 ＋ NPU 首字归因，出处写全）—— 🔴 **纠偏要的是「一行」，
   不是 6 行**。
3. **「最近更新」裁掉最旧 3 条**（ASR-052 2026-11-07 / ASR-053 09:22 / ASR-053 11:20）
   ⇒ **逐字追加**到 `status/archive/STATUS_ASR_recent_updates_upto_20261111.md`，
   **ASR-055（13:50）与 ASR-056（15:40）两条保留在正文**。

🔴 **§78 归档**：`status/archive/STATUS_ASR_sec78_upto_20261111.md` —— **逐字保留**原 §78 正文，
标题头格式与 `STATUS_ASR_sec76/sec77_upto_20261111.md` 对齐（归档用 `## §78 `、正文用 `### §78 `
⇒ 比对时**归一前缀**）。

### 8.4 写入过程中抓出并修掉的 3 处真缺陷（**都属「脚本写好了 ≠ 能跑 / 写对」**）

| # | 缺陷 | 现象 | 修法 |
|---|---|---|---|
| 1 | **自指大小不动点循环不收敛** | 占位符 `@@SELF@@` 替换后**不能再迭代**（数字位数会变） ⇒ `AssertionError: 自指大小未收敛` | 每轮**从带占位符的模板重算**，并在**最终 CRLF 形态**上测字节/行数；收敛后再断言「写的 == 实际的」 |
| 2 | **§81 插错位置** | 插到「最后一个 `### §` 标题的**正下方**」⇒ **落在 §80 标题与正文之间** ⇒ §80 正文变成 §81 的内容 | 改为**追加到文件末尾**（最后一个章节的正文本来就在文件末尾）；锚点**动态**找，不写死章节号 |
| 3 | **§79⑥ 的撤回标注漏标** | asr138 的表被压成**一行**，「显著变差」是**列名**、「**True**」在**同一行末列** ⇒ 整串 `'**显著变差 True**'` **匹配不到** ⇒ 只标了 3/4 处 | 改用**整行**匹配 ⇒ 标注挂在**该行末尾**（不能插进表格中间）|

🔴 **本轮 STATUS 是用 3 个版本的写入器迭代出来的**：
`_asr056_write_status.py`（v1：4 处缺陷）→ `_asr056_write_status2.py`（v2：修 §81 位置/舍入/提速口径/超限，
但 §81 位置与自指大小仍错）→ **`_asr056_write_status3.py`（v3：最终版，门禁 PASS）**。
🔴 **每次重跑都先 `cp STATUS_ASR.md.bak_asr056 STATUS_ASR.md` 恢复干净基线**（备份 **39119 B / 156 行**）
⇒ 杜绝「在错误版本上叠加修改」。
