# §85 明细 —— ASR-063 落地（交错重跑 ＋ tier 剔懒编译 ＋ §84⑥ 机理改正 ＋ 补 3 项缺项）

- 生成时间：2026-11-19 18:37:20
- 来源：`results/asr163/analysis.json` ＋ `tbound.json` ＋ `mem.json`
- 脚本：`scripts/_asr063/asr163_rerun.py` ＋ `asr163_resume.py` ＋ `asr163_analyze.py` ＋ `asr163_mem_one.py` ＋ `asr163_tbound.py`

## 一、交接说明（上一会话死在哪）

- 上一会话（lease `c10fd9b0`，15:22–15:43，note「交错重跑进行中，STATUS early 已写」）在**跑第 2 臂时死掉**，只完成 **1/18 臂**（`base_r1_spe`），**未释放 MACHINE_LOCK**（残留 pid 28260 已死）。
- 本轮 **TAKEOVER** 接续：新建 `asr163_resume.py`（只补跑缺的臂）＋ 修掉 `set_lang_prompt` 不幂等的真缺陷。

## 二、① 交错重跑表（每格 2 轮，带范围）

| 素材 | base (pml=512) | tier (pml=512) | both (pml=320) | tier vs base | both vs base |
|---|---|---|---|---|---|
| SPE 10min | 0.3291 / 0.3425（0.3291–0.3425） | 0.3160 / 0.3176（0.3160–0.3176） | 0.2766 / 0.2573（0.2573–0.2766） | -5.62% | -20.41% |
| FLEURS 英 | 0.3020 / 0.2943（0.2943–0.3020） | 0.2699 / 0.2724（0.2699–0.2724） | 0.2171 / 0.2181（0.2171–0.2181） | -9.04% | -27.00% |
| FLEURS 中 | 0.2932 / 0.3004（0.2932–0.3004） | 0.2676 / 0.2866（0.2676–0.2866） | 0.2155 / 0.2238（0.2155–0.2238） | -6.66% | -26.00% |

## 三、② 降幅（配对 + 区间两种口径）

| 素材 | 臂 | 配对均值 | 配对区间（逐轮） | 区间口径（min/max 组合） |
|---|---|---|---|---|
| SPE 10min | tier | -5.62% | [-7.27%, -3.98%] | [-7.74%, -3.49%] |
| SPE 10min | both | -20.41% | [-24.88%, -15.95%] | [-24.88%, -15.95%] |
| FLEURS 英 | tier | -9.04% | [-10.63%, -7.44%] | [-10.63%, -7.44%] |
| FLEURS 英 | both | -27.00% | [-28.11%, -25.89%] | [-28.11%, -25.89%] |
| FLEURS 中 | tier | -6.66% | [-8.73%, -4.59%] | [-10.92%, -2.25%] |
| FLEURS 中 | both | -26.00% | [-26.50%, -25.50%] | [-28.26%, -23.67%] |

### 逐轮配对明细

- **both_en_vs_base_en**
  - r1：base 0.3020 → both_en 0.2171（-28.11%）
  - r2：base 0.2943 → both_en 0.2181（-25.89%）
- **both_spe_vs_base_spe**
  - r1：base 0.3291 → both_spe 0.2766（-15.95%）
  - r2：base 0.3425 → both_spe 0.2573（-24.88%）
- **both_zh_vs_base_zh**
  - r1：base 0.2932 → both_zh 0.2155（-26.50%）
  - r2：base 0.3004 → both_zh 0.2238（-25.50%）
- **tier_en_vs_base_en**
  - r1：base 0.3020 → tier_en 0.2699（-10.63%）
  - r2：base 0.2943 → tier_en 0.2724（-7.44%）
- **tier_spe_vs_base_spe**
  - r1：base 0.3291 → tier_spe 0.3160（-3.98%）
  - r2：base 0.3425 → tier_spe 0.3176（-7.27%）
- **tier_zh_vs_base_zh**
  - r1：base 0.2932 → tier_zh 0.2676（-8.73%）
  - r2：base 0.3004 → tier_zh 0.2866（-4.59%）

## 四、③ tier 臂不含懒编译的核对

| 臂_轮_素材 | wall s | rtf | 计时外编译 s | 档位分布 |
|---|---|---|---|---|
| both_r1_spe | 166.0 | 0.2766 | 27.76 | {'400': 556, '800': 457, '1600': 18} |
| tier_r1_spe | 189.6 | 0.3160 | 26.19 | {'400': 556, '800': 457, '1600': 18} |
| both_r2_spe | 154.4 | 0.2573 | 27.76 | {'400': 556, '800': 457, '1600': 18} |
| tier_r2_spe | 190.6 | 0.3176 | 26.19 | {'400': 556, '800': 457, '1600': 18} |
| both_r1_en | 97.4 | 0.2171 | 27.76 | {'400': 388, '800': 323, '1600': 55} |
| tier_r1_en | 121.0 | 0.2699 | 26.19 | {'400': 388, '800': 323, '1600': 55} |
| both_r2_en | 97.8 | 0.2181 | 27.76 | {'400': 388, '800': 323, '1600': 55} |
| tier_r2_en | 122.1 | 0.2724 | 26.19 | {'400': 388, '800': 323, '1600': 55} |
| both_r1_zh | 100.8 | 0.2155 | 27.76 | {'400': 386, '800': 276, '1600': 103, '2400': 32} |
| tier_r1_zh | 125.1 | 0.2676 | 26.19 | {'400': 386, '800': 276, '1600': 103, '2400': 32} |
| both_r2_zh | 104.6 | 0.2238 | 33.03 | {'400': 386, '800': 276, '1600': 103, '2400': 32} |
| tier_r2_zh | 134.0 | 0.2866 | 31.95 | {'400': 386, '800': 276, '1600': 103, '2400': 32} |

## 五、⑤ prefill 按 prompt 长度分桶（支撑 §84⑥ 机理改正）

> 分桶键 = `T // 32`（0 ⇒ T<32）。若 NPUW 是「按真实长度补齐」，各桶 p50 应随 T 上升；**实测是平的** ⇒ 说明按 `MAX_PROMPT_LEN` 静态补齐。

| base_en | r1 | T//32=0: n=65 p50=95.84；T//32=1: n=258 p50=95.27；T//32=2: n=253 p50=94.89；T//32=3: n=146 p50=95.05；T//32=4: n=32 p50=96.01；T//32=5: n=12 p50=94.49 |
| base_en | r2 | T//32=0: n=65 p50=93.66；T//32=1: n=258 p50=93.76；T//32=2: n=253 p50=93.62；T//32=3: n=146 p50=94.05；T//32=4: n=32 p50=93.83；T//32=5: n=12 p50=93.56 |
| both_en | r1 | T//32=0: n=65 p50=64.72；T//32=1: n=258 p50=64.46；T//32=2: n=253 p50=64.58；T//32=3: n=146 p50=65.46；T//32=4: n=32 p50=65.28；T//32=5: n=12 p50=65.71 |
| both_en | r2 | T//32=0: n=65 p50=65.72；T//32=1: n=258 p50=65.73；T//32=2: n=253 p50=66.19；T//32=3: n=146 p50=66.52；T//32=4: n=32 p50=66.08；T//32=5: n=12 p50=65.89 |
| both_zh | r1 | T//32=0: n=66 p50=66.53；T//32=1: n=259 p50=66.06；T//32=2: n=223 p50=66.67；T//32=3: n=130 p50=68.05；T//32=4: n=48 p50=68.96；T//32=5: n=19 p50=69.05；T//32=6: n=16 p50=71.16；T//32=7: n=16 p50=69.32；T//32=8: n=20 p50=69.65 |
| both_zh | r2 | T//32=0: n=66 p50=69.36；T//32=1: n=259 p50=69.80；T//32=2: n=223 p50=69.82；T//32=3: n=130 p50=70.61；T//32=4: n=48 p50=70.42；T//32=5: n=19 p50=72.84；T//32=6: n=16 p50=73.26；T//32=7: n=16 p50=73.29；T//32=8: n=20 p50=70.58 |
| tier_en | r1 | T//32=0: n=65 p50=93.65；T//32=1: n=258 p50=93.24；T//32=2: n=253 p50=93.42；T//32=3: n=146 p50=93.68；T//32=4: n=32 p50=93.60；T//32=5: n=12 p50=93.20 |
| tier_en | r2 | T//32=0: n=65 p50=94.92；T//32=1: n=258 p50=95.06；T//32=2: n=253 p50=95.20；T//32=3: n=146 p50=95.83；T//32=4: n=32 p50=96.36；T//32=5: n=12 p50=94.58 |

## 六、⑥ transcript 逐字节比对（新跑 vs ASR-062 base）

- 全部相同：**True**
- md5 按素材：{'spe': ['cd67417e64ae6009c0b703453f7c5316'], 'en': ['ed3f52aaf1415ca01d785da4e3a78cb4'], 'zh': ['d93062a686fc1e647b34f4a813bad01d']}

## 七、⑦ 补 (a) 每档 encoder 常驻内存增量（fresh 进程）

> 指标：`rss_mb` = 进程 RSS；`private_commit_mb` = Windows Private Usage（私有提交量）；`vms_mb` = 虚拟大小。**NPU 权重由插件映射进系统/NPU 内存**⇒ 进程视角只能看到用户态那部分。

| 档位 N | 编译 s | ΔRSS vs assets (MB) | ΔRSS 仅编译 (MB) | Δ Private 提交 (MB) |
|---|---|---|---|---|
| 400 | 6.93 | 451.6 | 434.8 | 391.3 |
| 800 | 8.26 | 462.1 | 436.7 | 391.8 |
| 1600 | 15.72 | 465.5 | 449.2 | 404.7 |
| 2400 | 17.46 | 499.1 | 457.0 | 412.6 |

- **N=400**：compile 6.93 s；baseline RSS 22.8 MB → after_assets 88.7 MB → after_compile 523.8 MB → after_infer 540.3 MB；Δ(assets→infer) RSS 451.6 MB / Private 391.3 MB
- **N=800**：compile 8.26 s；baseline RSS 22.5 MB → after_assets 89.0 MB → after_compile 525.9 MB → after_infer 551.1 MB；Δ(assets→infer) RSS 462.1 MB / Private 391.8 MB
- **N=1600**：compile 15.72 s；baseline RSS 22.8 MB → after_assets 88.5 MB → after_compile 538.0 MB → after_infer 554.0 MB；Δ(assets→infer) RSS 465.5 MB / Private 404.7 MB
- **N=2400**：compile 17.46 s；baseline RSS 22.6 MB → after_assets 89.0 MB → after_compile 546.2 MB → after_infer 588.1 MB；Δ(assets→infer) RSS 499.1 MB / Private 412.6 MB

## 八、⑧ 补 (b) 出字/定稿延迟 p50/p95

> 分类：`first` = 每段第一次调用（首字）；`incr` = 段内增量出字；`flush` = 段尾定稿（判据：本次 mel 帧数 == 上一次）。单位 ms。

| 臂_素材 | 轮 | first p50/p95 (ms) | incr p50/p95 (ms) | flush p50/p95 (ms) |
|---|---|---|---|---|
| base_en | r1 | 144.3 / 151.3 | 145.9 / 216.1 | 413.3 / 564.8 |
| base_en | r2 | 139.6 / 145.9 | 142.5 / 201.9 | 397.0 / 551.0 |
| both_en | r1 | 93.3 / 103.1 | 98.3 / 152.5 | 354.0 / 513.0 |
| both_en | r2 | 93.1 / 99.6 | 99.6 / 150.6 | 351.4 / 509.2 |
| tier_en | r1 | 122.6 / 130.8 | 127.8 / 181.3 | 392.3 / 546.2 |
| tier_en | r2 | 123.7 / 132.5 | 129.2 / 184.5 | 392.2 / 546.2 |
| base_spe | r1 | 143.4 / 151.2 | 147.3 / 248.2 | 544.5 / 757.7 |
| base_spe | r2 | 146.8 / 156.6 | 150.5 / 256.5 | 560.5 / 783.1 |
| both_spe | r1 | 102.6 / 133.6 | 108.1 / 226.9 | 530.0 / 725.1 |
| both_spe | r2 | 99.7 / 104.5 | 104.4 / 201.4 | 507.3 / 705.9 |
| base_zh | r1 | 142.3 / 150.5 | 145.7 / 166.8 | 394.4 / 633.1 |
| base_zh | r2 | 146.4 / 153.1 | 149.4 / 165.5 | 408.7 / 658.0 |
| both_zh | r1 | 94.3 / 102.2 | 99.9 / 129.9 | 348.4 / 578.5 |
| both_zh | r2 | 96.3 / 107.3 | 104.4 / 137.7 | 354.6 / 601.2 |

## 九、⑨ 补 (d) T 的理论上界 + 超限线上行为

**解析式**：`T = 18 (模板) + aftercnn_len(mel_frames) + len(tok.encode(prefix_text))`

- 段长上限 = `bk_segmenter.MAX_SEG_SEC` = **20.0 s**（实测最后一块可到 **20.48 s**）
- 合成实测段：20.0 s / 320000 样本 / 2000 mel 帧 / 260 音频 token / 模板 18 token

| 段长 s | mel 帧 | 音频 token | 前缀 token | T |
|---|---|---|---|---|
| 6.4 | 641 | 84 | 0 | 102 |
| 6.4 | 641 | 84 | 50 | 152 |
| 6.4 | 641 | 84 | 100 | 202 |
| 12.8 | 1281 | 167 | 0 | 185 |
| 12.8 | 1281 | 167 | 50 | 235 |
| 12.8 | 1281 | 167 | 100 | 285 |
| 13.0 | 1301 | 170 | 0 | 188 |
| 13.0 | 1301 | 170 | 50 | 238 |
| 13.0 | 1301 | 170 | 100 | 288 |
| 16.0 | 1601 | 209 | 0 | 227 |
| 16.0 | 1601 | 209 | 50 | 277 |
| 16.0 | 1601 | 209 | 100 | 327 |
| 19.2 | 1921 | 250 | 0 | 268 |
| 19.2 | 1921 | 250 | 50 | 318 |
| 19.2 | 1921 | 250 | 100 | 368 |
| 20.0 | 2001 | 261 | 0 | 279 |
| 20.0 | 2001 | 261 | 50 | 329 |
| 20.0 | 2001 | 261 | 100 | 379 |
| 20.48 | 2049 | 267 | 0 | 285 |
| 20.48 | 2049 | 267 | 50 | 335 |
| 20.48 | 2049 | 267 | 100 | 385 |
| 24.0 | 2401 | 313 | 0 | 331 |
| 24.0 | 2401 | 313 | 50 | 381 |
| 24.0 | 2401 | 313 | 100 | 431 |

**ASR-062 实测 max T**：

- `base_spe`：max T **163**（min 26，n=1031）、段长 max 10.88 s / p95 7.936 s、93 段
- `base_en`：max T **185**（min 26，n=766）、段长 max 12.8 s / p95 11.264 s、65 段
- `base_zh`：max T **285**（min 26，n=797）、段长 max 20.48 s / p95 18.56 s、66 段
- `pml_zh`：max T **285**（min 26，n=797）、段长 max 20.48 s / p95 18.56 s、66 段
- `both_zh`：max T **285**（min 26，n=797）、段长 max 20.48 s / p95 18.56 s、66 段

**超限行为实测（pml=320 / 512，各 6 档 T）**：

| pml | T | 结果 | 说明 |
|---|---|---|---|
| 320 | 280 | ✅ 成功 | 正常出字 |
| 320 | 300 | ✅ 成功 | 正常出字 |
| 320 | 320 | ✅ 成功 | 正常出字 |
| 320 | 321 | 🔴 抛错 | RuntimeError: Exception from src\inference\src\cpp\infer_request.cpp:224: Exception from src\plugins\intel_npu\src\plugin\npuw\llm_infer_request.cpp:1 |
| 320 | 330 | 🔴 抛错 | RuntimeError: Exception from src\inference\src\cpp\infer_request.cpp:224: Exception from src\plugins\intel_npu\src\plugin\npuw\llm_infer_request.cpp:1 |
| 320 | 350 | 🔴 抛错 | RuntimeError: Exception from src\inference\src\cpp\infer_request.cpp:224: Exception from src\plugins\intel_npu\src\plugin\npuw\llm_infer_request.cpp:1 |
| 512 | 280 | ✅ 成功 | 正常出字 |
| 512 | 300 | ✅ 成功 | 正常出字 |
| 512 | 320 | ✅ 成功 | 正常出字 |
| 512 | 321 | ✅ 成功 | 正常出字 |
| 512 | 330 | ✅ 成功 | 正常出字 |
| 512 | 350 | ✅ 成功 | 正常出字 |

- 汇总：`{"n_cases": 3, "n_error": 3, "n_silently_truncated": 0, "detail": [{"T": 321, "ok": false, "err": "RuntimeError: Exception from src\\inference\\src\\cpp\\infer_request.cpp:224:\nException from src\\plugins\\intel_npu\\src\\plugin\\npuw\\llm_infer_request.cpp:1288:\nInput", "out_preview": null}, {"T": 330, "ok": false, "err": "RuntimeError: Exception from src\\inference\\src\\cpp\\infer_request.cpp:224:\nException from src\\plugins\\intel_npu\\src\\plugin\\npuw\\llm_infer_request.cpp:1288:\nInput", "out_preview": null}, {"T": 350, "ok": false, "err": "RuntimeError: Exception from src\\inference\\src\\cpp\\infer_request.cpp:224:\nException from src\\plugins\\intel_npu\\src\\plugin\\npuw\\llm_infer_request.cpp:1288:\nInput", "out_preview": null}]}`
- 🔴 **pml=320 超限时的错误原文**（`tbound.json` → `behavior_pml320_over_limit.detail[].err`）：`Input prompt is longer than configured "NPUW_LLM_MAX_PROMPT_LEN": 320` ⇒ **显式抛错，不是静默截断**（`n_silently_truncated=0`）。

## 十、⑩⑪ 本轮修掉的缺陷与锁记录

- **真缺陷**：`asr163_rerun.py::set_lang_prompt()` 用 `replace("language English<asr_text>")` ⇒ **不幂等** ⇒ 换成 Chinese 后后续轮找不到 English 标记 ⇒ `RuntimeError` ⇒ 作业在 **15/18 臂**处崩。
- **修法**：同时认 English / Chinese 两种标记，按目标语种替换（幂等）；已用 `asr163_resume.py` **只补跑缺的 3 臂**，未重跑已完成的 15 臂。
- **锁**：两轮作业 pid **25024**（15 臂）/ **19804**（3 臂）；`LockProbe` 自检合计 **6 次 / 0 被抢** ⇒ `timing_valid=true`；跑完已释放锁、无残留进程。
- **干扰来源**：本机 live_dub_ext 的 CUDA TTS 侧车（pid 22112）**占 GPU、不占 NPU** ⇒ 是 reviewer 所说「base 臂阵发性变慢」的**最可能来源**；§85 用**同进程交错**摊平。

## 十一、口径限制

- RTF **不含编译**（编译单列 `compile_s_out_of_window`）。
- FLEURS **逐句 wav 不在本机** ⇒ WER 参照沿用 ASR-060 的「词数等分」口径 ⇒ **总 WER 才是结论**。
- **§84③ 的数值对拍设备**：ASR-062 的对拍在 **GPU.0** 上、用 `_tier_cpu` 的 IR 做的，**不是** NPU 上的 `tiers/`；NPU 端的等价性由**端到端转写逐字节相同**保证。
- **本轮只写数据，未改交付默认**（`asr06b_stateful_backend.py` 未动）。
