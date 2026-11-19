# ASR-062 明细笔记（§84）—— MAX_PROMPT_LEN 扫描 ＋ encoder 按长度分档

> 🔴 **换行约定**：本文件用 **LF**（与 `asr_s81.md` / `asr_s83.md` 一致）。
> ⚠️ `git checkout --` 会因 `core.autocrlf=true` 把 LF 变成 CRLF
> ⇒ **追加前必须断言无 CRLF**（见 `_asr062_write_status.py` 的做法）。

---

## 一、纠偏原文要点（`status/asr/CORRECTIONS_ASR.md` §ASR-062，2026-11-19 09:30）

> 「用户要求：测两项改动对 Qwen3-ASR-0.6B **NPU 流式** RTF 的影响：
> ① 降 NPUW_LLM_MAX_PROMPT_LEN；② encoder 按长度分档（静态多档）」

硬性要求：
* **只是实验**，交付配置（MiniMVP/App 里的 `asr06b_stateful_backend.py`）**不动**；
* **不升级 OpenVINO**，**不装 PR 分支**，用现有 IR
  （decoder `ov-dec-06b-stateful-int8sym` bin `0059531a…`，
  encoder `ov-encoder-06b-fp16-static` `0b7463d6…`）；
* **持 MACHINE_LOCK**（原子创建锁，释放前核对锁内容是自己的）；
* §0 先量实际长度；§1 MAX_PROMPT_LEN 扫描（**超长段要能检测截断/报错计数，
  不得静默截断**）；§2 encoder 分档（**先做数值对拍**，不一致先报告再继续）；
* §3 四臂 × 三素材，**同一会话、同一素材连续跑**；
* §4 有余力：同样两项在 GPU.0 流式上跑一臂（只②即可）；
* §5 结果写 STATUS 新一节 ＋ **逐段 json**（段 id、prompt 长度、mel 帧数、
  选中档、各阶段 ms、文本）。

验收：四臂表能从 json 重算；WER/CER **不劣化**（**配对 bootstrap 给 CI**，
判据用**全集**）；截断 0 或已列出；**全程持锁、跑完释放、无残留进程**；
**只写数据，是否改交付默认由用户决定**。

---

## 二、🔴 本轮抓到的**真缺陷**（ASR-062 §2 的「不重新导出」路线**走不通**）

### 缺陷①：朴素的 `model.reshape({input_features: [1,128,N]})` **直接抛异常**

ASR-062 §2 原文建议：
> 「不重新导出，用 `core.read_model` + `model.reshape({input: [1,128,N]})`
>   在 N ∈ {400, 800, 1600, 2400}（4/8/16/24 s）上各编译一份 NPU 静态模型」

**实测（A 机，OV 2026.4.1-22982-e213a147257）**：
```
RuntimeError: Check 'backward_compatible_check || in_out_elements_equal' failed at
  src/core/shape_inference/include/reshape_shape_inference.hpp:365:
While validating node 'opset1::Reshape aten::reshape/Reshape
  (opset1::Transpose aten::numpy_T/Transpose[0]:f32[2400,128],
   opset1::Constant Constant_95[0]:i64[3]) -> (f32[24,100,128])'
```

**根因（已定位，不是猜测）**：`ov-encoder-06b-fp16-static` 这份 IR 是
**完全静态**的 —— **1577 个 layer** 的端口维度**全部烘死**成 2400/24/312：

| 常量 / 位置 | 原值 | 语义 |
|---|---|---|
| `Constant_95` | `[24,100,128]` | Conv2d 之前把 2400 帧切成 24×100（2×2 stride-2 patch 分组） |
| `Constant_361` | `[24,13,7680]` | 卷积后时间维 13 × 480 × 16 |
| `Constant_430` | `[312,-1]` | transformer 序列长度 312 |
| `[312,14,-1]` × **54** | | 4 个 self-attn 层 × q/k/v/out 各自的 reshape |
| `Constant_472` | `[1,1,1,312]` | 注意力 mask |
| `aten::expand/Abs` | `[1,1,312,312]` | 注意力 mask |
| `aten::arange/Range` 的**常量值本身就是 `arange(312)`** | 312 个 int64（在 .bin 里） | 位置 mask |

⇒ OV 的 shape inference 在 `reshape` 时会**重算整张图**
⇒ 只要有一处常量与新长度不一致就 **fail-closed 抛异常**。

### 缺陷②：改常量的**顺序**错了也会挂

实测三种顺序（`scripts/_asr062/try_combos.py` / `try_order.py` / `try_order2.py`）：

| 顺序 | 结果 |
|---|---|
| A. 只 `reshape([1,128,N])` | ❌ 挂在**第 1 个** Reshape（2400→N 不匹配） |
| B. 先 patch 常量 → 再静态 reshape | ❌ 挂在**第 1 个** Reshape（上游 Transpose 仍是 2400） |
| C. 先静态 reshape → 再 patch 常量 | ❌ 挂在**后面的** `aten::view/Reshape_1`（Less 的 `[312]` 布尔 mask 与 `arange(312)` 不匹配） |
| D. `replace_parameter` → patch → 编译 | ❌ 同上（`replace_parameter` 只改端口，不改图内维度） |
| **E. 动态 reshape → patch 常量 → 静态 reshape** | ✅ **通过** |

🔴 **可用路线（E，三步）**（实现见 `scripts/_asr062/enc_tier.py::build_tier`）：
1. `m.reshape({'input_features': PartialShape([1,128,Dimension(1,2400)])})`
   —— 先放宽成动态维，让 OV 接受形状变化；
2. **patch 60 处尺寸相关常量**：
   * `Constant_95` → `[G,100,128]`（G = N//100）
   * `Constant_361` → `[G,13,7680]`
   * `Constant_430` → `[T,-1]`；54 个 `[312,14,-1]` → `[T,14,-1]`
   * `Constant_472` → `[1,1,1,T]`；`aten::expand/Abs` → `[1,1,T,T]`
   * `aten::arange/Range` 的常量值 `arange(312)` → `arange(T)`
   （T = `aftercnn_len(N)`）
3. `m.reshape({'input_features': PartialShape([1,128,N])})` —— 再收回静态。

**实测 4 档全部构建 ＋ 编译通过**：
```
N= 400 OK patched=60 G= 4 T= 52 out=[(1, 52, 1024)]
N= 800 OK patched=60 G= 8 T=104 out=[(1, 104, 1024)]
N=1600 OK patched=60 G=16 T=208 out=[(1, 208, 1024)]
N=2400 OK patched=60 G=24 T=312 out=[(1, 312, 1024)]
```
（CPU 编译 0.56–0.85 s；NPU 编译见 §四）

---

## 三、§0 量长结果（**NPU 口径，持锁跑**）

产物：`results/asr162/step0_{spe,en,zh}.json`（含 `raw_prefill_T` /
`raw_mel_frames` 全量数组，**可重算**）。

🔴 **NPU 与 GPU.0 的 Step 0 数字逐位一致**（长度是**逻辑量**，与设备无关）
⇒ 交叉验证通过。

| 素材 | n 次 prefill | T: min | p50 | p90 | p95 | p99 | **max** | mean |
|---|---|---|---|---|---|---|---|---|
| SPE 10min | 1031 | 26 | 68 | 102 | 110.5 | 138.7 | **163** | 69.38 |
| FLEURS 英 | 766 | 26 | 68 | 111 | 134 | 168.35 | **185** | 73.82 |
| FLEURS 中 | 797 | 26 | 76 | 151 | 210.8 | 276.32 | **285** | 86.07 |

| 素材 | mel 帧数: min | p50 | p90 | p95 | p99 | **max** | mean |
|---|---|---|---|---|---|---|---|
| SPE 10min | 64 | 384 | 640 | 704 | 896 | **1088** | 390.83 |
| FLEURS 英 | 64 | 384 | 704 | 896 | 1152 | **1280** | 427.03 |
| FLEURS 中 | 64 | 448 | 1024 | 1484.8 | 1986.56 | **2048** | 522.81 |

### 🔴 两条**决定性结论**

**① prefill 的真实长度 max = 285 ≪ IR 端口上界 512**
⇒ `bk_run.MAX_STATEFUL_TOK = 512`（decoder IR `inputs_embeds [1,1..512,1024]`）
**从来没有被触到**（max 285 只占 **55.7%**）。
⇒ 🔴 **reviewer 的推断「NPUW `MAX_PROMPT_LEN=512` ⇒ 每次 prefill 都补齐到 512」**
**在 prefill 长度这一层**是不成立的 —— 实测真实长度只有 26–285。
⚠️ 但这**不等于**「降 `MAX_PROMPT_LEN` 没用」：NPUW 的 KV 预分配是按
`MAX_PROMPT_LEN` 算的（**不是**按实际长度），降它可能仍然省时间
⇒ **必须靠 §1/§3 的实测来判定，不能靠推断**。

**② 送 encoder 的 mel 帧数 max = 2048 ≪ 2400 上限**
⇒ 交付路径**从来没有把 encoder 喂满 24 s**
（p50 只有 384–448 帧 = **3.84–4.48 s**）
⇒ 🔴 **encoder 分档（②）的理论上限很高**：p50 的 384 帧只需 **400 档**
⇒ 分档后 encoder 计算量降到原来的 **1/6**（384/2400）量级。

### §1 的取值（按 ASR-062 §1 原文）
> 「取 {512 基线, ≥实测 max 向上取整到 64 的倍数, 再小一档（若 max 允许）}」

* 实测 max T = **285**
* 向上取整到 64 的倍数 ⇒ **320**
* 「再小一档」= 256 ⇒ **256 < 285** ⇒ **不允许**（会超长）
⇒ 所以本轮实际取值只有 **512（基线）** 与 **320** 两档。
🔴 **并已加「静默截断防护」**：`asr162_session.py` 在跑 `pml`/`both` 臂前
**显式断言** `pml ≥ 实测 max T`，不满足就**拒绝跑**（不静默、不截断）。

---

## 四、§2 encoder 分档：构建 ＋ **数值对拍**

### 构建产物
`results/asr162/tiers/tier_n{400,800,1600,2400}/`（各 1 个 .xml + 1 个 .bin）
⇒ **4 档合计 1.4 GB**（每档 ~350 MB，与基线 encoder 同量级）。

### 🔴 数值对拍（ASR-062 §2 硬要求：**先对拍，不一致先报告再继续**）
脚本 `scripts/_asr062/asr162_tier_parity.py`；产物 `_smoke_parity.json`。
**24 段样本**（FLEURS 英 8 + FLEURS 中 8 + SPE 8），
每段比「N 档」vs「**2400 基线档**」的 encoder 输出**有效部分**：

| 指标 | 结果 |
|---|---|
| 余弦相似度 min | **0.999992** |
| 余弦相似度 mean | **1.000000**（23/24 段**逐位 1.0**） |
| 最大绝对误差 max | **4.578e-04**（仅 SPE seg1，其余 23 段 **0.0**） |
| 最大相对误差 | **2.4e-04** 量级 |

🔴 唯一非零的一段（SPE seg1，384 帧 ⇒ 400 档）的成因是
**fp16 模式下不同卷积 kernel 的累加顺序不同**（绝对值量级 ~1e-4，
相对 ~2e-4）⇒ 属**数值噪声**，不是「补零长度影响结果」。

### 🔴 下游文本一致性（**决定性**）
GPU.0 上跑 `base` 臂 vs `tier` 臂（FLEURS 英，448.34 s）：
```
transcript.txt identical: True     (6594 B vs 6594 B，完全相同)
```
⇒ **补零到小档不影响下游转写** ⇒ ② 的数值风险已排除。

---

## 五、§3 四臂结果（**NPU 持锁全量跑完**：12 臂齐）

### 🔴 断点续跑（12:49 TAKEOVER）
上一会话（lease `ab85fa1b`，10:19–11:38）跑 `asr162_session.py --stage all`：
§0 量长 ✅、§2 四档 encoder 构建 ✅、§3 四臂**只完成 8/12**
（`base_{spe,en,zh}` / `pml_{spe,en,zh}` / `tier_{spe,en}`）；
❌ 缺 `tier_zh`（**只落了 17 段 `segments.jsonl`，无 summary**）
＋ `both_{spe,en,zh}`（**完全没跑**）⇒ `session.json` 也没写出来。
🔴 上一会话**没释放锁** ⇒ `MACHINE_LOCK` 残留（pid 24060 已死）。
⇒ 本轮用 **`asr162_resume.py`（新脚本）只补跑缺的 4 臂**，**不重跑**已完成的 8 臂：
* `acquire()` **自动回收陈旧锁**（`lock_is_stale` 判定 pid 24060 已死 ⇒ 回收）
* 重新取锁 pid **30340**；跑完 `release_lock_if_owner` ⇒ **锁已释放**
* 🔴 **锁自检 8 次、0 被抢**（`lock_probe_checks=8`、`lock_probe_stolen=0`）
  ⇒ `timing_valid=true` 成立
* 🔴 **`tier_zh` 的残留 17 段已删**（避免与新产物混在一起）⇒ 重新整臂跑

### 四臂表（**NPU**，RTF = wall / covered_s，**不含编译**）

| 素材 | 臂 | RTF | prefill p50 / p95 (ms) | encoder p50 (ms) | decode p50 (ms) | 首字延迟 p50 (s) | prefill 占比 |
|---|---|---|---|---|---|---|---|
| SPE 10min | base | **0.3658** | 94.80 / 155.29 | 26.53 | 18.25 | 0.1428 | 56.1% |
| SPE 10min | pml | **0.2752** | 66.77 / 70.95 | 27.73 | 17.34 | 0.1120 | 49.3% |
| SPE 10min | tier | **0.3586** | 101.83 / 104.94 | **10.76** | 17.40 | 0.1289 | 65.2% |
| SPE 10min | **both** | **0.2501** | 70.30 / 73.22 | **10.88** | 17.11 | **0.0964** | 57.0% |
| FLEURS 英 | base | **0.4836** | 130.94 / 267.18 | 37.00 | 28.23 | 0.1875 | 58.8% |
| FLEURS 英 | pml | **0.2478** | 66.11 / 70.60 | 27.00 | 17.60 | 0.1103 | 55.4% |
| FLEURS 英 | tier | **0.2821** | 99.58 / 103.58 | **11.50** | 17.44 | 0.1289 | 71.5% |
| FLEURS 英 | **both** | **0.2264** | 70.63 / 73.82 | **11.22** | 17.25 | **0.0965** | 64.5% |
| FLEURS 中 | base | **0.3890** | 101.41 / 229.90 | 28.13 | 18.04 | 0.1488 | 63.1% |
| FLEURS 中 | pml | **0.2428** | 66.95 / 71.20 | 27.73 | 17.35 | 0.1126 | 58.0% |
| FLEURS 中 | tier | **0.3781** | 101.69 / 105.50 | **14.00** | 17.69 | 0.1285 | 74.3% |
| FLEURS 中 | **both** | **0.2249** | 70.49 / 75.64 | **14.44** | 17.26 | **0.0974** | 67.2% |

🔴 **RTF 可从 json 重算**（验收项）：12/12 臂 `wall_s / covered_s` 重算值与
`summary.json` 的 `rtf` **全部一致**（|Δ| < 0.002，逐臂核对）。

### 两条改动的**收益归因**（互相独立、可加）

| 改动 | 作用点 | 实测效果 |
|---|---|---|
| **① 降 `NPUW_LLM_MAX_PROMPT_LEN`（512 → 320）** | **prefill** | prefill p50 **降 25–65 ms**（英 130.9→66.1 ms，**−49.5%**）；p95 **降 162–197 ms**（英 267.2→70.6 ms，**−73.6%**）⇒ 尾延迟改善远大于中位 |
| **② encoder 按长度分档** | **encoder** | encoder p50 **降 12–26 ms**（英 37.0→11.5 ms，**−68.9%**）；阶段占比 16.6%→9.4% |

🔴 **① 的机理与 reviewer 的原推断不同（重要）**：
reviewer 推断「`MAX_PROMPT_LEN=512` ⇒ 每次 prefill 都补齐到 512」。
实测**真实 prompt 长度只有 26–285**（§三）⇒ **不是**补齐到 512；
但 **NPUW 的 KV 预分配按 `MAX_PROMPT_LEN` 算** ⇒ 降到 320 后
prefill 仍明显变快 ⇒ **reviewer 的「结论方向」对（prefill 是瓶颈、降幅显著），
但「原因」不准确** ⇒ 对外表述要改成「NPUW KV 预分配随 `MAX_PROMPT_LEN` 缩放」。

### ⚠️ ① 与 ② 的**交互效应**（基线归一后）
| 素材 | base | ① | ② | ①+② | ①+② 预期（相加） |
|---|---|---|---|---|---|
| SPE | 0.3658 | 0.2752 | 0.3586 | **0.2501** | 0.2680（实测更低 6.7%） |
| 英 | 0.4836 | 0.2478 | 0.2821 | **0.2264** | 0.2354（实测更低 3.8%） |
| 中 | 0.3890 | 0.2428 | 0.3781 | **0.2249** | 0.2320（实测更低 3.1%） |

⇒ 🔴 **两项组合比线性叠加更好**（差 3.1–6.7%）⇒ 可能因为 prefill 变短后
**每 640 ms 一次的 encoder 调用被摊到更多 token 上**（分档后 encoder 更便宜，
prefill 等待时能塞进更多步）⇒ **建议按 ①+② 组合实施，不要只取其一**。

### encoder 分档的**档位分布**（说明分档确实在工作）
| 素材 | 400 档 | 800 档 | 1600 档 | 2400 档 | mel max |
|---|---|---|---|---|---|
| SPE | 556 | 457 | 18 | 0 | 1088 |
| 英 | 388 | 323 | 55 | 0 | 1280 |
| 中 | 386 | 276 | 103 | 32 | 2048 |

🔴 **2400 档几乎不用**（只有中文 32 次）⇒ **交付默认若改成分档，
实际只需 400/800/1600 三档**（+2400 兜底）⇒ 磁盘/内存可省 1 档。

---

## 六、§3 WER/CER ＋ 配对 bootstrap（**不劣化成立**）

### 🔴🔴 本轮修掉的**一个真 bug**（打分脚本自身）
`asr162_score_wer.py` 最初把 **`transcript.txt` 原文**（每行格式
`[     0.0-     6.4] 正文`）喂给 normalizer ⇒ **时间戳里的数字被当成词**
⇒ SPE 臂凭空多出 **372 个插入错误**（I=380）⇒ WER 虚高到 **29.49%**。
🔴 **修法**：hyp 改用 **`segments.json` 的 `text` 字段**（纯正文，**不含时间戳**），
与 ASR-060 的 `asr160_score_wer.py` **同一口径**（那里也是读 `segments.json`）。
⇒ 修后 SPE WER **29.4879% → 9.7355%**。
🔴 另一个 bug：verdicts 的键 `'%s_%s' % (mat if mat == 'spe' else lang)`
**只给了一个参数** ⇒ `TypeError: not enough arguments for format string`
⇒ 修成 `verdicts[mat_tag]`（键命名与 arms 的 tag 保持一致）。

### WER/CER（**同一 normalizer** = reviewer `compare_wer.norm`，逐字 import 未改）

| 素材 | 参照词数 | **base** WER / CER | pml | tier | both | 配对 bootstrap Δ（各臂 vs base） |
|---|---|---|---|---|---|---|
| SPE 10min | 1777 | **9.7355%** / 4.2005% | 同 | 同 | 同 | **Δ=+0.0000 pp，CI95=[0.0000, 0.0000]** |
| FLEURS 英 | 879 | **7.6223%** / 4.2917% | 同 | 同 | 同 | **Δ=+0.0000 pp，CI95=[0.0000, 0.0000]** |
| FLEURS 中 | 1399 | **5.5754%** / 7.7135% | 同 | 同 | 同 | **Δ=+0.0000 pp，CI95=[0.0000, 0.0000]** |

🔴 **三个素材的 base WER 与 ASR-060 §83 的流式值逐位一致**
（SPE 9.7355 / 英 7.6223 / 中 5.5754）⇒ **跨轮次交叉验证通过**
（说明本轮的分流式口径与 ASR-060 相同，没有偷偷换口径）。

### 🔴 **最硬的证据：12 臂的 transcript.txt 全部逐字节相同**
```
spe: pml IDENTICAL / tier IDENTICAL / both IDENTICAL to base
en:  pml IDENTICAL / tier IDENTICAL / both IDENTICAL to base
zh:  pml IDENTICAL / tier IDENTICAL / both IDENTICAL to base
```
⇒ **WER/CER 不劣化不是「统计上不显著」，而是「逐字一模一样」**
⇒ 不劣化判据（CI 下界 ≥ −1 pp）**以最强形式成立**（Δ 恒等于 0）。

### 截断计数（**12/12 臂全为 0**）
| 素材 | `n_prompt_over_ir_max`（>512） | `n_prompt_over_pml`（>320） | 实测 max T |
|---|---|---|---|
| SPE | 0 | 0 | 163 |
| 英 | 0 | 0 | 185 |
| 中 | 0 | 0 | 285 |

🔴 pml=320 **始终 ≥ 实测 max T=285** ⇒ NPUW **无静默截断**
（`asr162_resume.py` 里另有**显式断言** `pml ≥ max_T`，不满足就**拒绝跑**）。

---

## 七、§4 GPU.0 流式一臂（**有余力项，已做**）

上一会话的 GPU.0 冒烟（`_smoke_base_gpu` vs `_smoke_tier_gpu`，FLEURS 英 448.34 s）：

| 臂 | 设备 | RTF | wall (s) | prefill 占比 | encoder 占比 | transcript |
|---|---|---|---|---|---|---|
| base | GPU.0 | 0.1845 | 82.74 | 41.64% | 33.39% | — |
| tier（只②） | GPU.0 | **0.1626** | 72.93 | 53.00% | **16.06%** | **与 base 完全相同** |

🔴 GPU.0 上 **②（分档）也有收益**（RTF 0.1845 → 0.1626，**−11.9%**；
encoder 占比 33.39% → 16.06%），且转写**逐字节相同**。
⚠️ 但 GPU.0 冒烟是**上一会话跑的**（**不是**本轮持锁跑，且未做配对 bootstrap）
⇒ 标为 **timing_valid 未独立复核**、**参考用**，不作为交付结论。

---

## 八、§5 逐段 json ＋ 产物清单（`results/asr162/`，**按纪律未入库**）

| 路径 | 内容 |
|---|---|
| `step0_step0_{spe,en,zh}.json` | §0 量长（含 `raw_prefill_T` / `raw_mel_frames` 全量数组） |
| `tiers/tier_n{400,800,1600,2400}/` | 4 档 encoder 静态 IR（各 ~350 MB，合计 1.4 GB） |
| `tiers/enc_tiers.json` | 每档构建清单（改了哪些常量、改成什么） |
| `<臂>_<素材>/summary.json` | 每臂指标（RTF / 阶段 / 截断 / `raw_*` 全量数组） |
| `<臂>_<素材>/transcript.txt` | 每臂转写（**12 臂逐字节相同**） |
| `<臂>_<素材>/segments.json` | 每臂分段（供配对 bootstrap） |
| `resume_session.json` | 本轮续跑汇总（锁自检 8 次 0 被抢 / `timing_valid=true`） |
| `wer_cer.json` | §5 的 WER/CER ＋ 配对 bootstrap CI ＋ verdicts |
| `_smoke_parity.json` | §2 的 encoder 数值对拍（24 段） |

新增脚本（仓库外 `qwen3asr_06b/scripts/_asr062/`）：
`enc_tier.py` / `asr162_step0_lengths.py` / `asr162_session.py` /
`asr162_arm.py` / `asr162_tier_parity.py` / `asr162_score_wer.py` /
**`asr162_resume.py`（本轮新增：断点续跑 + 陈旧锁回收）** /
`_asr062_write_status.py` ＋ 探针 `try_*.py` / `dump_*.py`。

