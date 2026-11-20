# §86 明细 —— ASR-064 + ASR-065 合并一轮（pml=320 默认形态 ＋ 前缀截断降级 ＋ encoder 分档可选开关）

- 生成时间：2026-11-20 14:15
- 来源：`results/asr165_ov241/`（bench 15 臂 ＋ analysis ＋ trunc_test ＋ mem 5 场景 ＋ probe）
- 脚本：`scripts/_asr065/`（`asr165_bench.py` / `asr165_analyze.py` / `asr065_trunc_test.py` / `asr065_mem_cum.py` / `asr165_determinism_probe.py` / `asr165_chain_ov241.py`）
- 解释器：**`_ov241_kitenv`（OpenVINO 2026.4.1-22982-e213a147257）** —— 与 §85 参照同版本
- 交付说明：`qwen3asr_06b/dev/asr065_handoff.md`

## 〇、交接说明（上一会话死在哪）

- 上一会话（lease `d127413f`，10:27–11:07，note「bench running, probe script ready」）**在 bench 跑完后、STATUS 收尾时死掉**。
- 本轮 **TAKEOVER**（token `62ae3401`）：发现 bench **15 臂已跑完**（`results/asr165/`，OV **2.5.0rc1**），但 **transcript md5 与 §85 参照全部不符**。
- 🔴 **本轮最重要发现**：md5 不符的根因 = **OpenVINO 版本**，不是模型/代码问题（详见 §一）。

## 一、🔴 根因定位：md5 不符 = **OpenVINO 版本**（不是 NPU 非确定性）

`asr165_determinism_probe.py` 跑同一臂（SPE base 全长）两个独立进程，只换解释器：

| 解释器 | OpenVINO | RTF | wall | transcript md5 | == §85 参照 `cd67417e…` |
|---|---|---|---|---|---|
| `_ov265rc_env` | **2026.5.0-23816-92096e1c255**（rc1） | 0.4642 | 278.55 s | `d4f01c246e4a5e71f77641106b0d7679` | ❌ |
| `_ov241_kitenv` | **2026.4.1-22982-e213a147257** | 0.5968 | 358.10 s | `cd67417e64ae6009c0b703453f7c5316` | ✅ |

⇒ **换回 kit wheels 的 2026.4.1 即复现 §85 参照** ⇒ 根因 = **OpenVINO 版本差异**，
**不是**「NPU 跨进程浮点非确定性」，**不是**模型/代码改动。

🔴 **口径纪律**：**凡是与 §85 直接比较的数字（md5 / 准确率 / RTF 基线）必须在 2026.4.1 下测**。
本轮 15 臂全部在 **2.4.1** 下重跑 ⇒ 结论**与 §85 同口径**。

### 确定性复核（2.4.1 下同臂跑两次，独立进程）

`results/asr165_ov241/probe241/probe.json`：**2/2 全部 `identical_to_sec85=true`**（md5 均 `cd67417e…`，RTF 0.3235 / 0.3206）
⇒ 🔴 **同版本下跨进程完全可复现**（把「NPU 非确定性」这条候选解释排除掉）。

## 二、① pml-only 交错臂（ASR-065 第 3 项，**必做**）

- 顺序：**按素材 `base(512) → pml(320)` × 2 轮**（SPE / FLEURS英 / FLEURS中）= **12 臂**；再 `pmltiers`（pml320 + 分档 on）各 1 轮 = **3 臂**；共 **15 臂**。
- **编译全在计时窗口外**：3 个 runner 先建好；分档**运行时构建 + 直接 compile（不落盘）**。
- 启动期合计 **188.37 s**（base enc 17.02 + dec 7.49；pml enc 18.19 + dec 6.96；pmltiers enc 18.86 + dec 7.25 ＋ **分档 build 0.15 s + compile 33.40 s**）。

### RTF（不含编译）

| 素材 | base(512) r1 / r2 | pml(320) r1 / r2 | **① pml vs base** | pmltiers 各 1 轮 | ①+② vs base |
|---|---|---|---|---|---|
| SPE 10min | 0.3313 / 0.3524 | 0.2860 / 0.3039 | **−13.72%**（−13.76 / −13.67） | 0.2475 | −25.29% |
| FLEURS 英 | 0.3413 / 0.3190 | 0.2619 / 0.2507 | **−22.34%**（−23.26 / −21.41） | 0.2219 | −34.98% |
| FLEURS 中 | 0.2961 / 0.2946 | 0.2418 / 0.2429 | **−17.94%**（−18.34 / −17.55） | 0.2197 | −25.80% |

### 分段配对 bootstrap（每段对 2 轮取平均，5 段一块做 bootstrap，B=5000，seed=20261120）

| 素材 | 段数 | ① pml vs base 均值 | CI95 | ② 分档 vs pml（**仅 1 轮**） |
|---|---|---|---|---|
| SPE | 186 | **−13.93%** | [−14.50, −13.37] | −13.46% |
| FLEURS 英 | 130 | **−22.73%** | [−23.48, −22.10] | −15.27% |
| FLEURS 中 | 132 | **−18.39%** | [−18.84, −17.93] | −9.14% |

🔴 **①（pml 单独）的降幅比 §85 反推的 −19.76% 小**：§85 的「① 单独」是**反推**（由 ①+② 与 ② 相减），
本轮是**直接实测** ⇒ **§85 反推值偏高约 6 pp**（原因：§85 的 both 臂同时含分档，
分档收益会被算进 ① 的反推残差里）。⚠️ ②（分档）**只有 1 轮** ⇒ 其数值**弱于 ① 的证据强度**。

### prefill p50/p95（ms）

| 臂 | FLEURS 英 r1 | SPE r1 | FLEURS 中 r1 |
|---|---|---|---|
| base | 109.90 / 114.14 | 94.71 / 99.21 | 95.82 / 98.90 |
| pml | **68.58 / 74.68** | **67.49 / 72.32** | **66.09 / 70.55** |
| pmltiers | 65.78 / 68.40 | 65.62 / 68.39 | 65.34 / 68.98 |

⇒ 🔴 **降 pml 顺带降 prefill 耗时**（prefill 成本 ∝ T，pml 从 512 降到 320 ⇒ T 变短）。
⚠️ 注意：**prefill 耗时只随 `MAX_PROMPT_LEN` 变，与真实音频长度无关**（§84⑥ 的改正，本轮再次成立）。

### 出字延迟（**口径 = 每次 `generate` 的计算耗时 ms；不含 640 ms 分块等待与排队**）

| 臂 | first p50 (SPE/英/中) | incr p50 | flush p50 |
|---|---|---|---|
| base | 147.9 / 156.4 / 144.9 | 153.5 / 159.5 / 147.7 | 560.2 / 444.9 / 405.2 |
| pml | 121.8 / 116.6 / 114.7 | 124.5 / 119.0 / 117.3 | 543.2 / 383.1 / 367.5 |
| pmltiers | 96.1 / 95.4 / 97.9 | 100.7 / 100.5 / 102.0 | 487.6 / 364.0 / 361.7 |

🔴 **分档只降 encoder 自身耗时、降 prefill 的幅度很小；降 pml 才降出字延迟**。
⚠️ flush p95 base = 773.8 / 631.7 / 643.4 ms（长尾明显）。

### 阶段占比（%）

| 臂 | 素材 | prefill | decode | encoder |
|---|---|---|---|---|
| base | 英 | 64.56 | 17.53 | 17.91 |
| pml | 英 | 55.08 | 21.84 | 23.09 |
| pmltiers | 英 | 63.42 | 24.39 | **12.19** |

⇒ 分档把 encoder 占比从 17.9% 压到 **12.2%**；但 pml 的收益体现在 **prefill 绝对耗时**（109.9 → 68.6 ms）。

## 三、② 截断降级验收（ASR-064 问题 1 / ASR-065 第 1 项）—— **全部通过**

产物：`results/asr165_ov241/trunc_test.json`（OV 2.4.1）

### 验收①（强制 T 超限）：**3/3 通过**

| 目标 T | 抛错 | 输出 | 降级计数 | T_before → T_after | 前缀 token 丢弃 |
|---|---|---|---|---|---|
| 321 | 否 ✅ | 「。」 | 1 | 321 → 320 | 43 → 42（丢 1） |
| 330 | 否 ✅ | 「方法。」 | 1 | 330 → 320 | 52 → 42（丢 10） |
| 350 | 否 ✅ | 「如何在硬件上」 | 1 | 350 → 320 | 72 → 42（丢 30） |

⇒ `check_1 = {n_cases:3, n_ok:3, n_with_output:3, n_truncations_total:3, pass:true}`

### 验收②（正常素材逐字节相同）：**3/3 通过**

| 素材 | transcript md5（独立 `md5sum` 复核） | == §85 参照 | 降级次数 | max_T |
|---|---|---|---|---|
| SPE | `cd67417e64ae6009c0b703453f7c5316` | ✅ | 0 | 163 |
| FLEURS 英 | `ed3f52aaf1415ca01d785da4e3a78cb4` | ✅ | 0 | 185 |
| FLEURS 中 | `d93062a686fc1e647b34f4a813bad01d` | ✅ | 0 | 285 |

🔴 **脚本自判 `check_2.pass=false` 是**假阴性**：脚本用 `REF_MD5[lang]` 取参照，
而 **SPE 素材的 `lang` 也是 `'en'`** ⇒ SPE 被拿去比 **FLEURS-EN** 的参照 ⇒ 必然不等。
（`asr165_analyze.py` 用 `MAT_LABEL[(material, lang)]` 组合键 ⇒ 判 `true`。）
✅ **已修**：`asr065_trunc_test.py` + `asr165_bench.py` 改用 `ref_md5_of(mat, lang)` 组合键
（与 analyze 同口径）⇒ 上表 md5 用 `md5sum` **独立复核**，3/3 逐字节相同。

### 15 臂 transcript md5（`analysis.json` → `md5_vs_sec85`）

**base / pml / pmltiers 三个臂 × 三个素材 = 全部 `true`** ⇒ 🔴 **降 pml 与分档都不改变文本**。
`prefix_truncations` 全 15 臂 **total = 0**（正常素材全程 0 次降级）。

## 四、③ 前缀来源与上界（ASR-064 问题 2）

### 来源（代码级，`b_kit_stateful/scripts/bk_run.py`）

- `_prefix_for_chunk(tok, raw, nstep)`（**第 348–361 行**）：
  `nstep <= UNFIXED_CHUNK_NUM(=2)` ⇒ 前缀 = `''`；否则 `ids = tok.encode(raw)`，
  取 `ids[:len(ids)-k]` 解码成前缀，`k` 初始 = `UNFIXED_TOKEN_NUM`(=5)，
  若解码出 `'�'` 则 `k += 1` 重试（避免切在多字节字符中间）。
- `raw` 的来源（第 473–474 行）：`raw = prefix + g`（**段内累积文本**，与 `asr131` 逐字一致）。

### 长度由什么决定

**由「本段已解码出的累计文本长度」决定 ⇒ 随段内累积增长 ⇒ 没有硬上限**。

### 实测分布（15 臂，`analysis.json` → `prefix_len_tokens`）

| 素材 | max | p95 | mean | 非零次数/总次数 |
|---|---|---|---|---|
| SPE | **29** | 1 | 0.542 | 256 / 2062 |
| FLEURS 英 | 18 | 1 | 0.265 | 158 / 1532 |
| FLEURS 中 | 1 | 1 | 0.083 | 132 / 1594 |

### T_max 与 320 的理由

- `T = 18（模板 token）+ aftercnn_len(mel_frames)（音频 token）+ len(tok.encode(prefix_text))`
- `aftercnn_len(2048) = 266`（实测，`asr065_backend.py`）
- 段长上限 `bk_segmenter.MAX_SEG_SEC = 20.0 s`；实测最长段 **2048 mel 帧**（zh 素材）⇒ 音频 token 266
- ⇒ **T_max = 18 + 266 + 前缀上限**
- 实测最大前缀 = **29** ⇒ **真实流水线 T_max = 18 + 266 + 29 = 313**
- **pml=320 ⇒ 余量 = 320 − 313 = 7 token** ⇒ 实测 15 臂全程 0 次降级，**与观察一致**。
- 🔴 **前缀没有硬上限** ⇒ 余量只够覆盖「当前素材类型」；
  一旦某素材前缀超过 36 token（313−320 的边界再往前），**必须靠截断兜底**（已实现并实测）。

## 五、④ 内存（ASR-064 问题 3）—— **改正 §85⑦ 的说法**

产物：`results/asr165_ov241/mem/mem_cum.json`（**每场景一个 fresh 进程** ⇒ 互不污染）
Δ = 该场景最终快照 − 只读 assets 快照。

| 场景 | ΔRSS (MB) | ΔPrivate (MB) | compile_s |
|---|---|---|---|
| base_pml512 | 1628.52 | 849.94 | 31.63 |
| base_pml320 | 1628.15 | 852.30 | 30.37 |
| tiers_pml320 | 2755.76 | 1974.00 | 29.61 |
| tiers_pml512 | 2757.50 | 1976.43 | 31.45 |

### 派生结论

| 项 | 值 | 说明 |
|---|---|---|
| **分档相对 base 的增量（RSS）** | **+1127.61 MB** | 🔴 **不是 §85 写的「+1.9 GB」** |
| **分档相对 base 的增量（Private）** | **+1121.70 MB** | 🔴 **不是 §85 的「+1.19 GB」** |
| **pml320 − pml512 的 decoder 常驻内存（RSS）** | **−0.37 MB** | 降 pml **不省内存**（也不多占） |
| **pml320 − pml512 的 decoder 常驻内存（Private）** | **+2.36 MB** | 同上，噪声级 |
| 分档效果与 pml 解耦后（RSS） | −1.74 MB | 分档收益**不依赖** pml 改动 |

🔴 **§85⑦ 的「4 档全带 ≈ +1.9 GB」是错的**（reviewer 指出：那是 4 个**单档**相加，
含 base 里本来就有的 2400 档）⇒ **真实增量 = 400+800+1600 三档 = +1.13 GB RSS / +1.12 GB Private**
（fresh 进程实测）⇒ **撤回 §85⑦ 的 +1.9 GB 说法**。

⚠️ **口径限制**：NPU 权重由插件映射进系统/NPU 内存 ⇒ **进程视角只覆盖用户态部分**。

## 六、⑤ encoder 分档：运行时构建**可行**（ASR-065 第 2/4 项、ASR-064 问题 4）

产物：`results/asr165_ov241/analysis.json` → `startup.tier_runtime_build`

| 档 N | build_s | compile_s | patched | ok |
|---|---|---|---|---|
| 400 | 0.061 | 7.384 | **60** | ✅ |
| 800 | 0.042 | 8.029 | **60** | ✅ |
| 1600 | 0.048 | 17.988 | **60** | ✅ |
| 合计 | **0.151** | **33.401** | — | — |

⇒ ✅ **运行时从 base IR 现场构建各档、直接 compile、不落盘 = 可行**
（三步法：动态 reshape → patch 60 个常量 → 静态 reshape，全在内存里完成）。
⇒ 🔴 **必须断言每档 `patched == 60`**（节点名写死在这份 IR 上）⇒ 不满足就打日志并**退回 2400 单档**（不抛错）。

### 增益与代价（开关 on，vs 开关 off = pml 臂）

| 素材 | pml（off） | pmltiers（on） | 增益 | 启动多编译 |
|---|---|---|---|---|
| SPE | 0.2860 | 0.2475 | **−13.46%** | 33.40 s |
| FLEURS 英 | 0.2619 | 0.2219 | **−15.27%** | 33.40 s |
| FLEURS 中 | 0.2418 | 0.2197 | **−9.14%** | 33.40 s |

代价：**启动多编译 33.40 s** ＋ **常驻内存 +1127.61 MB RSS / +1121.70 MB Private**。

### 分档档位实际使用分布（`tier_used_distribution`）

| 素材 | 400 | 800 | 1600 | 2400 |
|---|---|---|---|---|
| SPE | 556 | 457 | 18 | 0 |
| FLEURS 英 | 388 | 323 | 55 | 0 |
| FLEURS 中 | 386 | 276 | 103 | 32 |

⇒ **2400 档确实被用到（zh 32 次）** ⇒ 不能删 2400（§85 的判断成立）。

## 七、⑥ 清理（ASR-065 第 7 项）—— 已执行

- 运行时构建已证明可行 ⇒ 删除实验遗留：`results/asr162/tiers/`（1.4 GB）＋ `results/asr162/_tier_cpu/`（1.4 GB）。
- **删除前已备份配方 JSON** ⇒ `scripts/_asr062/enc_tiers.json`（53272 B）＋ `enc_tiers_cpu.json`（53918 B）。
- `results/asr162/` 体积 **2.8 GB → 1.9 MB**。

## 八、本轮修掉的真缺陷（都在脚本自身）

1. 🔴 **OV 版本口径错误**（最严重）：上一会话用 `_ov265rc_env`（2026.5.0rc1）跑 ⇒ md5 与 §85 参照全不符。
   **不是模型/代码问题，是 OpenVINO 版本问题** ⇒ 已定位并全部改在 2.4.1 下重测。
2. 🔴 **`REF_MD5[lang]` 键冲突**：SPE 的 `lang` 也是 `'en'` ⇒ SPE 被拿去比 FLEURS-EN 的参照
   ⇒ `check_2.pass` 假阴性、bench 的 `same` 标志对 SPE 恒为 false。
   ✅ 已修（`asr065_trunc_test.py` + `asr165_bench.py` 改用 `ref_md5_of(mat, lang)`）。
3. 🔴 **`psutil` 未装进 2.4.1 解释器** ⇒ 累计内存测试 5 场景全失败（`ModuleNotFoundError`）。
   ✅ 已装 `psutil 7.2.2` 并重跑，5 场景全部 rc=0。
4. 🔴 **上一会话死时未释放 MACHINE_LOCK** ⇒ 残留 **app** 模块的锁（pid 16064 **已死**）挡住本轮。
   ✅ 已按 README_LOCK 口径回收（归档为 `MACHINE_LOCK.released_app_stale_1795151051`）。

## 九、产物清单（**按纪律未入库**，在仓库外 `C:\Users\Trekker-PTL\qwen3asr_06b\results\`）

| 路径 | 文件数 | mtime | 说明 |
|---|---|---|---|
| `results/asr165_ov241/bench.json` | 1 | 2026-11-20 13:45 | 15 臂完整记录（含 `prefill_T` / `mel_frames` / `tier_used_counts` / `prefix_len_tokens` 全量数组） |
| `results/asr165_ov241/analysis.json` | 1 | 2026-11-20 13:50 | 汇总 ＋ 降幅 ＋ bootstrap CI ＋ transcript 比对 ＋ 延迟 ＋ 分档统计 |
| `results/asr165_ov241/trunc_test.json` | 1 | 2026-11-20 13:53 | 截断验收 ①+②（3 用例 ＋ 3 素材） |
| `results/asr165_ov241/mem/mem_cum.json` | 1 | 2026-11-20 14:06 | 5 场景 fresh 进程累计内存汇总 |
| `results/asr165_ov241/mem/mem_<场景>.json` | 5 | 2026-11-20 14:05 | 各场景快照（baseline / base_pml512 / base_pml320 / tiers_pml320 / tiers_pml512） |
| `results/asr165_ov241/probe241/probe.json` | 1 | 2026-11-20 14:09 | 确定性复核（2/2 复现 §85） |
| `results/asr165_ov241/run/` | 15 子目录 | 2026-11-20 13:45 | 各臂 `summary.json` ＋ `transcript.txt` ＋ `segments.json(l)` |
| `results/asr165_ov241/normal/` | 3 子目录 | 2026-11-20 13:53 | 截断验收②的 3 素材 transcript |
| `results/asr165_ov241/chain.json` | 1 | 2026-11-20 14:09 | 收尾链执行记录（3 步） |
| `results/asr165_ov241_stdout.log` | 1 | 2026-11-20 13:45 | bench 主日志 |
| `results/asr165_chain_ov241.log` | 1 | 2026-11-20 14:09 | 收尾链日志 |
| **`results/asr165_ov241/`（合计）** | **93 文件** | 2026-11-20 14:09 | 其中 `run/` 15 子目录 ＋ `normal/` 3 子目录 ＋ 6 个 mem json ＋ 4 个 json ＋ 3 个日志 |
| `results/asr165/`（2.5.0 那轮） | — | 2026-11-20 11:30 | ⚠️ **口径不同**（OV 2.5.0rc1）⇒ **只作根因证据，不作结论** |

## 十、锁与纪律

- 全程持 `MACHINE_LOCK`（原子创建，释放前核对是自己的）＋ `LockProbe` 自检 **30 次 / 0 被抢** ⇒ `timing_valid=true`。
- bench、截断测试、内存测试、确定性探针**各自独立取锁、跑完释放** ⇒ 无残留进程。
- 🔴 **回收别人的陈旧锁前已核实 pid 16064 已死**（`pid_alive` = False，全机无 python 进程）⇒ 符合 README_LOCK 口径。
- 本轮**只写数据**，**交付文件 `live_caption/` 未动**（ASR-065：改 MiniMVP 由 App 线程在本条验收后再改）。


## 十一、「未完成纠偏」表移出的已关闭旧行索引

（正文已按 ASR-038 行数门禁移出；**结论全部保留**在 `status/archive/` 对应章节与 `notes/asr_s*.md`）

| ASR-063 | ASR-062 复核：RTF 降幅被高估（base 臂受干扰 + tier 臂含懒编译）/ §84⑥ 机理写反 / 补 3 项缺项后关闭 | ✅ **已落地**（§85；**只写数据，交付默认未改**）|
| ASR-062 | 测 MAX_PROMPT_LEN ＋ encoder 分档对 NPU 流式 RTF 的影响 | ✅ **已落地**（§84；**只写数据，交付默认未改**）|
| ASR-061 | reviewer 复核通过 ASR-060（§83），关闭；不需重跑 | ✅ **已关闭**（FYI）|
| ASR-059 | 用户决定：B 机不跑 ASR 套件；关闭 STATUS「B 机实测」待办 | ✅ **已关闭**（FYI）|
| ASR-058 | 记录 ASR-057 验收通过并关闭；B-kit 可交 B；ASR 线程待命 | ✅ **已关闭**（FYI）|
| ASR-057 | 修 `run_bk.cmd`（CRLF+ASCII / all+selftest / 失败非 0 退出）/ 清出套件里的 `.bak`+`results_A_local` / `ref_A` 补最终版 18s 三组 / `sources` 拆 copy+derived / 删过期遗留项 | ✅ **已落地**（§82）|
| ASR-056 | §79 正文 4 处标撤回 / 旧计时 json 标 unverified / 清跨脚本比较块 / 关键数字表补 300s-18s 行 / 套件最终版补测 4 组 / 交付前小修 a-f | ✅ **已落地**（§81）|
| ASR-055 | §79 的 ②④⑥ 改正 ＋ 按段配对 WER 重出 ＋ 锁记录写进 json ＋ B 机测试套件 `b_kit_stateful` | ✅ **已落地**（§80）|
| ASR-051 | 生产口径污染比例（或写明无法得到的原因）；不改 App 包 | ✅ **已落地**（§78）|
| ASR-050 | 用户决定：`min_clean_ratio` 默认 0.8 → 0.6；要求三处一致 + 900 s 回归 + 交接清单 | ✅ **已落地**（§77）|
| ASR-049 | 单页 App 说明（≤1 页）+ 直接回答 APP-071 + 量化「换人边界段混入上一人」 | ✅ **已落地**（§77）|
| ASR-047 | 用户决定：默认 0.64 s ＋ VAD 关闭；ASR-042 ③ 暂停；开关保留但默认关闭 | ✅ **已落地**（§74.⑤） |
| ASR-046 | 5 s IR 绝对路径清理 / asr113 两处异常 / min_clean_ratio 0.6 候选 / ASR-042 口径更正 / 环境变量开关 / 删 asr116 | ✅ **全部落地**（§74.①③④⑤⑥⑦ ＋ **§75** 补齐 ② 的**逐段 rows**）；**`min_clean_ratio` 默认值是否 0.8 → 0.6 仍由用户决定** |
| ASR-045 | 5 s 旁路窗口内核真改 + 5 s 静态 seg IR + 交付 4 文件 + NOTICE | ✅ **已落地**（本轮 §72.①②③④） |
| ASR-043 | `WIN_S` 默认 5.0 + 锁纪律 + ack 042 | ✅ **已满足**（`WIN_S_DEFAULT` 早已 5.0；本轮补「内核真按 5 s 跑」+ 全程持锁） |
| ASR-044 | 评测集 + 双窗口指标 + 错误分析 + 每项改动 A/B + v2.2 说明 | ✅ **已落地**（本轮 §72.⑤⑥⑦；v2.2 内核 == 自测代码 ⇒ 无需复测） |
