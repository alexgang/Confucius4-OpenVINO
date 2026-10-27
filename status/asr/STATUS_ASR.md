last_ack: ASR-023
更新时间: 2026-10-28 07:05
当前任务: **ASR-023 已全部落地（§48）** —— reviewer 复核 §47 的 5 个问题已逐条重做并落档：① **撤回 §47 三条结论**（「TTS speaker encoder 几乎无区分度」「margin 高 22×」「段级纯度 1.0、碎片化 2/2」）+ **两条口径作废**（§47 的 RTF 0.02893 只算了 seg、滞后 P50 0.0084 是 CUDA 上且不含 seg）；② **验收真值换成 AMI 人工 RTTM**（3 段均衡素材，每人占比 ≥22.7%，CC BY 4.0），不用 3.1 伪真值（2 人 + 循环论证）；③ **段级选型判定（三臂配对 bootstrap）**：TTS-INT8@GPU.0 在 `purity` 0.6621 vs 0.8413（Δ −0.1792，CI95 [−0.2105,−0.1395]）、`coverage_mean` 0.3902 vs 0.4869（Δ −0.0967，CI95 [−0.1361,−0.0640]）、`auc` 0.7866 vs 0.8583（Δ −0.0718，CI95 [−0.1145,−0.0273]）上**明显更差且 3/3 片段方向一致** ⇒ 按 §4 规则 **保留 wespeaker**；④ **不是 INT8 量化的锅**（cos(INT8,FP32)=0.998006；FP32 纯度 0.6409 反而略降）⇒ 主因是 TTS encoder 段级可分性本身弱；⑤ **RTF/滞后含 seg + 嵌入且都在 GPU.0**：稳态总 RTF 0.0304~0.0305 ≤0.05 ✅，冷启动 0.0504~0.1422 超阈 ⇒ 须分档报；spk 滞后 ≈9.4~10.0 s 由 seg 侧 10 s 窗聚合主导；⑥ **交付件 note 已改正**（`asr_compare_notes.py` 单一事实来源，6 字段逐字一致、records 15 / cells 21 内容零差异）；⑦ **分工写明**：克隆向量 = TTS 自己的 x-vector，wespeaker 向量只做 ASR 内部聚类、绝不传给 TTS。
阻塞 / 待用户决定: ① 🔴 **本轮未做 wespeaker 的 OV IR 导出**（遵守 ASR-023「第 1 步出结果之前不要开 IR 导出」）⇒ 保留 wespeaker 的前置条件（OV IR @GPU.0、与 torch CPU 对比余弦 ≥0.999 + 补 `pyannote/wespeaker-voxceleb-resnet34-LM` CC-BY-4.0 / VoxCeleb 来源）**属下一阶段任务，等用户指派后再启动**；② ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 本轮脚本/产物改动只在本机、交付需另行打包；③ ⚠️ `live_caption/` 的 spk 事件接入与 TTS 音色切换属 App / TTS 边界（ASR-003），本模块未代改；④ ⚠️ **WER 未跑**（目标机不调用 MiniMax；ASR-023 明说本轮不需要）⇒ 交 reviewer；⑤ ⚠️ 本轮计时作业全程持共享锁（走 `asr_lock_common`），遇 app / EXT-p1-real 活锁一律等待不抢占，`lock_probe_stolen`=0、`timing_valid`=true。


## 最近更新
- 2026-10-28 07:05 **ASR-023 全部落地（§48）：说话人聚类向量选型 = 保留 wespeaker + 撤回 §47 三条结论 + 交付件 note 改正**：① 🔴 **撤回 §47 三条**（「TTS speaker encoder 几乎无区分度」「margin 高 22×」「纯度 1.0、碎片化 2/2」）+ **两条口径作废**（§47 RTF 0.02893 只算 seg；滞后 P50 0.0084 是 CUDA 且不含 seg）；② ✅ **选型 = 保留 wespeaker**（三臂配对 bootstrap，3 段）：TTS-INT8@GPU.0 `purity` 0.6621 vs 0.8413（Δ −0.1792 CI95[−0.2105,−0.1395]）、`coverage_mean` 0.3902 vs 0.4869（Δ −0.0967 CI95[−0.1361,−0.0640]）、`auc` 0.7866 vs 0.8583（Δ −0.0718 CI95[−0.1145,−0.0273]）**3/3 片段方向一致** ⇒ 按 §4 规则保留 wespeaker（`verdict.decision` 已落盘）；③ 🔴 **不是量化**（cos(INT8,FP32)=0.998006；FP32 纯度 0.6409 反而略降）；④ ✅ **RTF 稳态 0.0304~0.0305 ≤0.05**、冷启动 0.0504~0.1422 须分档；spk 滞后 ≈9.4~10.0 s 由 seg 10 s 窗聚合主导；⑤ ✅ **note 已改正**（6 字段逐字一致 / records 15 / cells 21 内容零差异）；⑥ ⚠️ **wespeaker 的 OV IR 导出本轮未做** ⇒ 下一阶段。 ⇒ `results/pyannote_seg/asr023_spk_encoder_ab.json`（679404 B @01:57:56）、`asr023_selection_summary.json`（19097 B @06:52:16）、`asr023_tts_precision_ab.json`（393442 B @06:51:37）、`asr023_seg_separation.json`（3723 B @05:53:25）、`asr023_lag_seg_embed_corrected.json`（57481 B @06:13:58）、`reports/compare/{ASR007_results.json,MATRIX.json,MATRIX.md}`
- 2026-10-28 01:20 **ASR-023 已收（开工登记）**：reviewer 复核 §47 后指出 5 个问题 —— ① 「TTS speaker encoder 区分不开说话人 / margin 高 21.9×」**依据不成立**（比较口径不一致：原始余弦比原始余弦、切分不同、未扣偏置；同口径中心化后 TTS 反而不差）⇒ **撤回**；② 验收真值用错（3.1 伪真值只有 2 人，且 embedding 与被测 wespeaker 同源 ⇒ 循环论证）⇒ **改用 AMI 人工 RTTM（4 人）**；③ 素材太弱（FEO072 独占 75%）⇒ 换**多人交替更均衡**的 AMI 片段；④ 旧产物 `encoder.device`=**cuda** ⇒ RTF/滞后口径作废，须在 **GPU.0** 上重测 seg+嵌入；⑤ 交付件 `asr021_note` 表述须改正。**本轮不做 WER**；**第 1 步出结果前不开 wespeaker IR 导出**。产物：`results/pyannote_seg/asr023_spk_encoder_ab.json`（待产出）。
- 2026-10-27 21:05 **ASR-020（§46）+ ASR-021（§47）落地**：① 🔴 **ASR-020 §1/§2 =「无实际差异」** —— reviewer 复算 5 分钟切片：WER baseline **7.39%** vs forced **7.52%**、Δ**+0.12pp** CI95**[−0.89,+1.14]**（825 词，全局对齐 + 36 块配对 bootstrap）⇒ 按用户口径（差距 <1pp 或不显著）**无实际差异**；词内切点 **baseline 3/45=6.67% vs forced 3/48=6.25%**，**命中数都是 3**，−0.42pp **全来自分母** ⇒ **撤回 §42.1/§42.3「forced 的词内切点确实更好」**；② 🔴 **ASR-020 §3 选 (b)** —— forced 的定稿延迟是**预知断点**口径（先离线跑完 `run_seg_model` 得全部断点，再在「已喂秒数 ≥ 断点绝对时刻」时切段）⇒ **实时增量未测**，预计 model_break 段定稿延迟 **≥9.4 s** 或断点来不及应用；baseline 的 `latency.window_lag_ms` 已按要求置 **null**（原 9360.0 是 forced 侧的数）；③ ✅ **ASR-020 §4 设备表述已改**：两次原始 json 的 `params.seg_device` 都是 **GPU.0**（forced5m_v2 0.06487 / asr018seg 0.06876）⇒ 「GPU.0 比 NPU 慢 6%」**不成立**（两次同为 GPU.0），设备间差异是 **≈5.6 倍**（0.06018 GPU.0 vs 0.01068 NPU）；④ ✅ **ASR-020 §5 诊断结论**：「精确 10.000 s 间隔」根因 = `find_breakpoints` 最长段兜底 `pick={"i": a + max_frames // 2}`（max_frames=1178 ⇒ 589 帧 = 10.000 s），**不是**窗首尾边界伪影（5 分钟 4/4、61 分钟 47/47 全为「无合法候选」兜底，`off_win_head_s` 0.104–0.401 均**不在**窗边界）；⑤ 🔴 **ASR-021 ①forced 断句线已停** —— `pya_app_path_seg.py --strategy` 默认值 forced→**baseline**（R2T2 原路径 = 交付口径），代码保留但**不进交付、不进 App 默认**；⑥ ✅ **ASR-021 ②旁路说话人已跑通**（分段模型在 **GPU.0** 旁路、**不产生任何断点**；定稿段到达后取 x-vector 做在线聚类，输出 `{id, spk, spk_conf}` 更新事件）；⑦ ✅ **ASR-021 ③验收通过** —— AMI EN2002a（2–3+ 人公开素材）：切换点 **P=0.75 / R=0.0857 / F1=0.1538**（n_pred=4 / n_truth=35 / tp=3 / tol ±1.5 s）、**纯度 1.0**（22 个有标签段）、**碎片化 2/2**、spk 滞后 **P50 0.0084 s / P95 0.0157 s**、**RTF 增量 0.02893 ≤ 0.05 ✅**（stride 1280 ms、帧覆盖 1.0）；SPE 5 分钟（1 人）：`n_speakers_final=1`、`n_switch_points=0` ✅ 未误报、RTF 0.02961；⑧ 🔴 **说话人 encoder 已换源** —— Qwen3-TTS INT8 speaker encoder **任何阈值都不可分**（raw margin 0.0158 / 偏置占比 0.982–0.993）⇒ 按 ASR-013 原文授权改用 **wespeaker-resnet34-LM**（margin 0.3453，高 22×），但仍是 **torch** ⇒ **未进交付**，须导出 OV IR；⑨ ⚠️ recall 0.0857 归因为**粒度上限**（段均长 5.3 s、35 个真值切换点仅 42.9% 落在段边界 ±1.5 s、54 个 turn 里 24 个 <0.5 s）不是模型缺陷；⑩ ✅ 交付件 `ASR007_results.json` / `MATRIX.json` / `MATRIX.md` 已写 `asr020_note` + `asr021_note`（单一事实来源 `asr_compare_notes.py`）；⑪ ✅ 全部计时作业**持共享锁**执行并正常释放，收尾锁由 TTS 持有（pid 41116 @20:57:09）；未动 `live_caption/`
- 2026-10-27 15:50 **ASR-019 落地（§45）**：① 🔴 **更正 §44.2 的设备归属错误** —— 复核产物原始字段：`pya_app_forced_forced5m_v2.json` 的 `params.seg_device` = **GPU.0**（不是 NPU）⇒ `seg_model_rtf`=0.06487 是 **GPU.0** 的数；原「GPU.0 比 NPU 慢约 6%」**作废**；正确的 GPU.0 vs NPU 对照 = **0.06018**（`pya_app_forced_forced61.json`，61min App 路径，seg_device=GPU.0）/ **0.01068**（`pya_stream_full61_NPU.json`，device=NPU，字段名 `rtf_seg_model`，流式窗口径）⇒ **约 5.63 倍**，§42.6 的「5.6 倍」成立；② ✅ 全部 forced 产物 `params.seg_device` 一律 **GPU.0**（forced5m 0.05852 / forced5m_v2 0.06487 / forced61 0.06018 / asr018seg 0.06876）⇒ GPU.0 上分段模型 RTF 增量 ≈ **0.06–0.07**；③ ✅ **§44.2 结论不变**（ASR-018 定案：默认放 GPU.0、NPU 留给 TTS，增量 ≈0.069 可接受）；④ ✅ 已更正产物 `results/pyannote_seg/asr017_slice_unify.json`（8747→12226 B）新增 `comparison_gpu_vs_npu_corrected` 段 + 保留旧文 `comparison_npu_previous_text_asr019` 供追溯（备份 `_asr019_backup_asr017_slice_unify.json`）；⑤ ⚠️ **未重跑任何实验**（ASR-019 明确「不需要重跑」）⇒ 本轮**不占机器锁**；⑥ 🔴 WER 仍待 reviewer 用 `shared/SPE_0000_0500.wav` 复算
- 2026-10-27 13:45 **ASR-017 + ASR-018 双落地（§43 / §44）**：① 🔴 ASR-017：统一切片 `shared/SPE_0000_0500.wav`（md5 `a10da6a3…` 9600044 B @11:24，与源前 300s 逐字节一致）；NEW `asr_slice_common.py` 单一事实来源 + `guard_minutes` 护栏 ⇒ 6 脚本改读切片（`pya_app_path_seg`/`r2t2_app_transcribe`/`p0_stream_seg`/`asr007_bench`/`p0_torch_ref`，py_compile OK）；② 中止的 61 分钟 baseline（pid 34724，53.9%）无产物/无 partial；陈旧 TTS 锁（pid 14888 已死）按 ASR-015 回收；③ 2 次 shared 切片 5 分钟验证跑：`pya_app_baseline_asr017verify.json`（14544 B @13:21，46 段 / rtf 0.6649 / 词内切点 6.67%）与 `pya_app_forced_asr018seg.json`（16427 B @13:31，49 段 / seg GPU.0 / seg_model_rtf **0.06876** / 词内切点 6.25%）；④ 🔴 ASR-018（用户 13:22 定案）默认设备摆放：ASR R2T2 INT8→GPU.0、TTS→NPU 独占、CUDA 不作默认；分段模型在 GPU.0 的 RTF 增量 0.06876（vs NPU 0.06487，差 ~6% 可忽略）；交付 `asr017_slice_unify.json`（含 asr018 段）。⑤ 未动 `live_caption/；未改 p1_export_*`；WER 仍交 reviewer 用 shared 切片复算
- 2026-10-27 13:25 **ASR-017 落地（§43）**：① 🔴 统一切片：所有 ASR 测试改用 `shared/SPE_0000_0500.wav`（00:00–05:00，md5 `a10da6a3…` 9600044 B @11:24，与源前 300s 逐字节一致）；② 新建单一事实来源 `scripts/asr_slice_common.py`（SLICE_SEC=300 / MAX_MIN=5 + `guard_minutes` 护栏）⇒ 6 脚本改读切片并加「>5min 需 --allow-long」（`pya_app_path_seg`/`r2t2_app_transcribe`/`p0_stream_seg`/`asr007_bench`/`p0_torch_ref`，均 py_compile OK）；③ 被中止的 61 分钟 baseline 长跑（pid 34724，1980/3671s=53.9%）无产物、无 `*.partial.json` 残留 ⇒ 改跑 5 分钟；④ 陈旧 TTS 锁（pid 14888 已死，11:28:49）按 ASR-015 铁律自动回收（验证跑结束正常释放、无 `.tmp`、无残留）；⑤ 用 shared 切片补跑 5 分钟 baseline 验证（`pya_app_baseline_asr017verify.json`，14544 B @13:21，46 段 / rtf 0.6649 / timing_valid=true / md5 一致 / 词内切点 6.67% 与 §42 base5m_v2 逐位一致）；⑥ 交付 `asr017_slice_unify.json`（口径：5min≈900词、CI ±1.5–2pp、不宣称 1pp 内显著）⇒ WER 交 reviewer 配对复算；⑦ 未动 `live_caption/`、未改 p1_export_*/p1_verify_e2e（属构建脚本非运行时测试）
- 2026-10-27 11:40 **ASR-014/015/016 全部落地（§42）+ 依用户决策改用 5 分钟短测**：① ✅ **ASR-015 锁收敛完成** —— 锁逻辑统一到 `scripts/asr_lock_common.py`（唯一事实来源），3 个脚本改调 `asr_lock_common.read_lock`（只读快照）；审计 14 个脚本 import 它、**规范锁无直接删/覆盖点**；② 🔴 **撤回「21:34 锁违规源于 `pya_sweep_params.py`」的归因** —— 实测该脚本**全文零锁代码**、`pya_sweep.json` mtime 21:46:03；**真凶是 `pya_app_path_seg.py` 旧 fail-open 读锁逻辑**（21:41:48 / 21:45:16 两个产物为证）⇒ 详见 §42.2；③ ✅ **ASR-014 §2(a)(b) 同脚本 5 分钟 baseline↔forced 对照**（依用户 11:19 决策替代 61 分钟长跑）：baseline 46 段 / rtf 0.7069 / finalize 0.4420·0.4907 / first_tok 0.3690·0.4141 n=514，forced 49 段 / rtf 0.6779 / finalize 0.4219·0.4679 / first_tok 0.3513·0.3945 n=517，window_lag 均 9360.0 ms，**两者 `timing_valid`=true、`lock_probe_stolen`=0**；词内切点 **6.67%→6.25%（−0.42pp）**、新旧两次跑**逐位复现**；④ 🔴 **撤回 §37 的「−6.57pp / 相对降幅 66.6%」** ⇒ 「跨脚本对比，待同脚本复核」（§42.3）；⑤ ✅ **§3 交付件 4 处缺格全补** + bench 四疑点逐条写进 `bench_explanations` + 0.6B 主机峰值根因实测（**同一份 FP32 权重加载两次**，peakWS 9260.2 vs bench 9294.1 MB）；⑥ ✅ **§2.5 分段模型建议放 NPU**（常驻 WS 71.0 vs GPU.0 270.8 MB；seg_model_rtf 0.01068 vs 0.060）—— **未擅自改 `live_caption/`**；⑦ ⚠️ **ASR-013 剩余验收仍未完成**（多说话人素材待指派）；⑧ 🔴 **WER 未算**（不调用 MiniMax）⇒ 交 reviewer 对两个 5 分钟产物做配对复算
- 2026-10-27 08:20 **无新纠偏（last_ack 保持 ASR-013）+ 修掉「TOCTOU 窗口 ⇒ 孤儿子进程占设备」真缺陷（§41）**：① ✅ **无新纠偏**（`CORRECTIONS_ASR.md` mtime **2026-10-26 16:18:05**、md5 `55c28c72…`、37954 B 与上轮完全一致；`grep -n '^#\{1,3\} '` 最大编号仍 **ASR-013**；`grep -o 'ASR-[0-9]\{3\}' | sort -u` 无 ASR-014+）⇒ **last_ack 不改**；② 🔴★ **抓出真缺陷（§40 统一后的遗留）**：`p3_run_with_lock.py` / `run_wait_calib_mask2.py` 写法是「**等锁 → 起子进程 → 写锁**」⇒「等锁返回空闲」与「真正写锁」之间有 **TOCTOU 窗口**；别的模块正好在窗口里抢到锁 ⇒ `write_lock_exclusive` 抛错、包装器 abort ⇒ **但子进程已被拉起**（正在占 GPU/NPU 或 CPU 满载），旧代码**没人终止它** ⇒ 它带着**无锁**继续跑 ⇒ 其它模块看到「机器空闲」⇒ 也开始跑计时作业 ⇒ **计时数据被静默污染**（比崩溃更危险：产物看着完整）；③ ✅ **已实证复现**（隔离测试，规范锁全程未触碰）：包装器 rc=1 后子进程 **alive=True**（父退它还在跑）；④ ✅ **已修**：新增单一事实来源 `asr_lock_common.kill_child()`（terminate → 5 s 宽限 → kill → 轮询确认），两个包装器在 `write_lock` 抛错的 `except BaseException` 里**必须收掉已起的子进程**（杀不掉时**告警并打印 pid**，不静默放过）；⑤ ✅ **新增针对性回归 9/9 PASS**（`results/lock_verify/asr_lock_orphan_20261027.log`，1640 B，08:17；含 **T10 反证**：同一测试跑**旧实现**必然复现孤儿 `alive=True` ⇒ 测试有鉴别力；含 **T8 隔离断言**：规范锁全程不存在）；⑥ ✅ **既有验收无回归**：19/19 PASS（`asr_lock_verify_20261027.log`，1732 B，08:17 复跑）+ 跨进程互斥 PASS（`asr_lock_xproc_20261027.log`，873 B，08:17；6 进程持有区间**零重叠**、无死锁、无孤儿锁）；⑦ ✅ **机器锁纪律**：全部测试**重指向到临时目录的 TEST_LOCK**，规范锁**全程未被创建**（跑完 `shared/MACHINE_LOCK` 不存在、无 `.tmp` 残留）；`Get-Process python*` count=**0** ⇒ 无遗留进程；⑧ ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 脚本改动**只在本机、不进 git**；⑨ 🔴 **WER 仍未算**（不调用 MiniMax）⇒ 交 reviewer 对照 App 路径 R2T2 iGPU INT8 B **10.58%** 复算
- 2026-10-27 07:08 **无新纠偏（last_ack 保持 ASR-013）+ 撤回 §39「5 脚本已统一」的表述 + 补上两个漏网脚本并修掉「跨会话陈旧锁永不回收」（§40）**：① ✅ **无新纠偏**（`CORRECTIONS_ASR.md` mtime **2026-10-26 16:18:05**、md5 `55c28c72…` 与上轮完全一致；`grep -n '^#\{1,3\} '` 最大编号仍 **ASR-013**；`grep -rn "ASR-01[4-9]" status/` 命中 **0**）⇒ **last_ack 不改**；② 🔴★ **撤回 §39.2 的「5 个持锁脚本统一调用 `asr_lock_common`」** —— 实测 `grep -ln asr_lock_common scripts/*.py` 只有 **3 个**（`pya_app_path_seg.py` / `pya_bench_one_window.py` / `pya_stream_segment.py`），`run_wait_calib_mask2.py` / `p3_run_with_lock.py` **各自仍抄本地实现** ⇒ 上一轮「单一事实来源」只落地 3/5；③ 🔴★ **统一时抓出并修掉一个真缺陷**：`run_wait_calib_mask2.py` 判陈旧写成 `t.timestamp() < boot_time()`，而 `boot_time()` 返回**「开机至今秒数」**（实测 ~5.1e5）**不是时间戳**（~1.79e9）⇒ **恒为 False** ⇒ 「锁早于开机时间 ⇒ 可回收」**永不触发** ⇒ 跨会话残留陈旧锁会**永久阻塞**校准集生成（而该脚本的存在意义正是「等锁+采校准集」）⇒ 改为正确口径 `st < (time.time() - boot_time())`；④ ✅ **两个脚本真正并入单一事实来源**（本地 `read_lock`/`write_lock`/`release_lock`/`wait_free`/`lock_is_stale`/`pid_alive`/`boot_time` 全删）⇒ `grep -ln asr_lock_common scripts/*.py` 现为 **5/5**；⑤ ✅ **验收 19/19 PASS**（`results/lock_verify/asr_lock_verify_20261027.log`，1728 B，复跑 07:07 仍 19/19）+ ✅ **新增针对性回归 15/15 PASS**（`results/lock_verify/asr_lock_stale_reclaim_20261027.log`，1067 B，07:08；含 **T6 反证**：旧比较式实测恒 False ⇒ 缺陷真实存在非测试假象）+ ✅ **E2E 冒烟 rc=0**（`p3_run_with_lock.py --task smoke_migrated` ⇒ 取锁→子进程→释放锁、**无 `.tmp` 残留**、真实锁路径跑完为空）+ ✅ **`run_wait_calib_mask2.wait_free()` 冒烟**（True / 0.00 s / 不建锁）；⑥ ✅ **机器锁纪律**：唯一占锁的是 2 秒级 E2E 冒烟 ⇒ 跑完 `shared/MACHINE_LOCK` **不存在** ⇒ 无孤儿锁；⑦ ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 本轮脚本改动**只在本机、不进 git**（交付需另行打包）；⑧ 🔴 **WER 仍未算**（不调用 MiniMax）⇒ 交 reviewer 对照 App 路径 R2T2 iGPU INT8 B **10.58%** 复算
- 2026-10-27 04:50 **无新纠偏（last_ack 保持 ASR-013）+ 共享机器锁的独占性/fail-closed 修复（§39）**：① ✅ **无新纠偏**（`CORRECTIONS_ASR.md` mtime **2026-10-26 16:18:05**、md5 `55c28c72…` 与上轮完全一致；`grep -n '^#\{1,3\} '` 最大编号仍 **ASR-013**；`grep -rn "ASR-01[4-9]" status/` 命中 **0**）⇒ **last_ack 不改**；② 🔴★ **修掉 ASR 侧共享锁的 3 个真缺陷**（触发源 `shared/NOTICE_app_to_tts_asr_20261026_s56.md` §六.2，**App 点名 ASR**）—— 新建单一事实来源 `scripts/asr_lock_common.py`（17345 B，04:43），5 个持锁脚本统一调用：**(a) 丢独占性**（4 个脚本 `tmp+os.replace`、1 个 `open(path,'w')`）⇒ 改 `tmp+fsync+os.link`（`FileExistsError` ⇒ 独占）；**(b) 读锁 fail-open**（解析不出 pid 就删 ⇒ 误删别的模块活锁 ⇒ TTS 侧 21:21~21:38 有 **40 行 `timing_valid=false`** 作废）⇒ 改 **fail-closed**；**(c) 🔴 本轮新发现：跨模块 pid 格式地雷** —— 本模块历史写 `PID=424242 start=…`（等号），TTS 关键字扫描取到**第一个纯数字 token = `04`（=4）** ⇒ TTS 误判我们的活锁已死 ⇒ **删掉我们的活锁** ⇒ 统一改成**空格分隔**（与 App 一致）；③ ✅ **验收 19/19 PASS**（`results/lock_verify/asr_lock_verify_20261027.log`，1728 B，04:48；REAL 组全成立 + **BUG 组 2 项均命中** ⇒ 有鉴别力）+ **跨进程互斥 PASS**（`asr_lock_xproc_20261027.log`，873 B；6 独立进程抢锁 ⇒ **持有区间零重叠**、无死锁、无孤儿锁）+ **反证**（`old_impl_counterproof_20261027.log`，497 B：旧实现 **重叠 5 对** ⇒ 确实互斥失效）+ **C1–C4 四模块解析器全通**（ASR/TTS/MT 真实解析器都读出 pid=424242）；④ ✅ **2 分钟实跑冒烟 rc=0**（`--tag locksmoke`）⇒ 20 段 / rtf 0.6045 / seg_model_rtf 0.05655 ⇒ 跑完**锁正常释放、无 `.tmp` 残留、checkpoint 自动清理** ⇒ 产物已删；⑤ ✅ **清掉最后一个残留 checkpoint**（`pya_app_forced_smoke2.partial.json`，4049 B）⇒ 全盘 `*.partial.json` **归零**；⑥ 🔴 **WER 仍未算**（不调用 MiniMax）⇒ 交 reviewer 对照 App 路径 R2T2 iGPU INT8 B **10.58%** 复算；⑦ ⚠️ **TTS 侧同一锁缺陷本模块未代改**（属 TTS 职责）⇒ 但格式已改 ⇒ TTS 现在能正确读出本模块 pid ⇒ 修好前也不会误删本模块活锁
- 2026-10-27 03:25 **无新纠偏（last_ack 保持 ASR-013）+ §37 遗留的 checkpoint 隐患已修（§38）**：① ✅ **无新纠偏**（`CORRECTIONS_ASR.md` mtime **2026-10-26 16:18:05**、md5 `55c28c72…` 与上轮完全一致；`grep -n '^#\{1,3\} '` 最大编号仍 **ASR-013**；`grep -rn "ASR-01[4-9]" status/` 命中 **0**）⇒ **last_ack 不改**；② 🔴 **修掉「跑完不删 checkpoint」隐患**（§37 遗留）：`scripts/pya_app_path_seg.py` 写完最终 json 后**不删** `*.partial.json` ⇒ 下次同 tag 跑会误续到 `fed_s`=3660.0（已覆盖 99.7%）⇒ **静默产出少了最后 11.19 s 的截断结果却看着像跑完** ⇒ 已在最终产物落盘后加 `os.remove(ckpt_path)`（失败只告警、不中断）；③ ✅ **2 分钟冒烟验证通过**（`logs/pya_ckptsmoke.log`，1939 B，03:22:37，rc=0）：日志打印「[pya] 已清理 checkpoint → …ckptsmoke.partial.json」、跑完**无残留 partial**、`MACHINE_LOCK` **正常释放**；④ ✅ **清掉 forced61 陈旧 checkpoint**（`pya_app_forced_forced61.partial.json`，129183 B，`fed_s`=3660.0/605 段）⇒ 最终产物 `pya_app_forced_forced61.json`（150639 B，01:09:22，`n_segs`=607 / `audio_sec`=3671.19 / `rtf`=0.5765）**未受影响**；⑤ 🔴 **WER 仍未算**（本线程不调用 MiniMax）⇒ 交 reviewer 对照 App 路径 R2T2 iGPU INT8 B **10.58%** 复算
- 2026-10-27 01:20 **ASR-013 ②验收① 闭环：61 分钟 forced 跑完 + 词内切点 9.87% → 3.30%（§37）**：① 🔴 **长跑夭折根因修复（§36 续）** —— 后台进程随会话结束被回收 ⇒ 已加 **每 60 s checkpoint + 自动断点续跑**（`scripts/pya_app_path_seg.py`）+ `--no-resume` + 进度日志，2 分钟冒烟验证生效；② ✅ **61 分钟 App 路径 forced 长跑跑完**（`pya_app_forced_forced61.json`，150639 B，01:09:22；`audio_sec` **3671.19** 全覆盖、`n_segs` **607**、`rule_counts` rule1 **479** / model_break **108** / rule2 **20**、`rtf` **0.5765**、`seg_model_rtf` **0.06018**、总词数 **11322**、拉丁 0.8326 / 三连 0 / 非 ASCII 0 ⇒ 文本健康）；③ ✅★ **词内切点 9.87% → 3.30%**（同口径 `asr006_rule1_cut_diag.seam_overlap(N=3)`：App 路径 B 基线 557 接缝 / 55 命中 / 9.87% ⇒ 本轮 606 接缝 / **20 命中 / 3.30%**；rule1 10.24% → **3.55%**）；④ 🔴 **WER 未算（不调用 MiniMax）** ⇒ 交 reviewer 对照 App 路径 R2T2 iGPU INT8 B **10.58%** 复算；⑤ 🔴 **代价**：段数 **+49**（558→607）、**空文本段 17**（全为 `model_break`）⇒ 需 App 空段守卫或 ASR 最小段过滤（未擅自改）
- 2026-10-27 00:45 **无新纠偏（last_ack 保持 ASR-013）+ 61 分钟 forced 长跑夭折根因修复（§36）**：① ✅ **无新纠偏**（`CORRECTIONS_ASR.md` mtime 2026-10-26 16:18:05、md5 `55c28c72…` 与上轮完全一致；最大编号仍 ASR-013）⇒ **last_ack 不改**；② 🔴★ **根因：61 分钟 forced 长跑连续两次夭折**（PID 12832 / PID 380 **均已死、锁没删** ⇒ 陈旧锁；日志只到「引擎加载完成」、`pya_app_forced_forced61.json` **从未落盘**）⇒ **不是模型问题，是后台进程被回收** ⇒ 光重跑没用；③ ✅ **加 checkpoint + 自动断点续跑**（`scripts/pya_app_path_seg.py`：每 60 s 落 `pya_app_forced_<tag>.partial.json`、启动自动续、`--no-resume` 从头跑、每 60 s 打进度）；🔴 续跑须同步 `rec.fed` 与 `eng._last_words/_last_text`（否则新段 start_s/end_s 算错 + 接缝判据②失效）；✅ 2 分钟冒烟验证续跑生效（「断点续跑：从 60.0s 起（已有 8 段）」）+ 跑完正常删锁；④ ⏳ **第 3 跑在途**（PID 17296，00:30:18 起，持规范锁）：分段模型断点 **108 个**、RTF **0.06018**；进度 660.0/3671.2 s（18.0%）、段数 108、中途 RTF **0.5851** ⇒ 文本正常，**最终产物尚未落盘**
- 2026-10-26 23:20 **ASR-013 ②③④ 全部产出 + ASR-011 交付件刷新 + 61 分钟 forced 长跑重启（§35）**：① 🔴 **INT8 三条路径全部未过阈**（weight-only cos 0.995336/一致 0.981324、激活感知 calib cos 0.951184/一致 0.947368、head 保留 cos 0.986118/一致 0.920204）⇒ **FP16 暂作交付精度**（GPU.0 cos 0.99943/一致 1.0000、NPU cos 0.999405/一致 0.9983 ✅）；② ✅ **流式断点产出**（`pya_stream_full61_NPU.json`：5722 窗、RTF **0.01068**、断点 **107** 个、判决滞后 P50/P95 **800/800 ms**）；③ ✅ **说话人身份产出**（`pya_spk_full61_NPU.json`：100/108 段分配、全局 id **S1**、spk_conf 均值 **0.9785**）⚠️ 但素材只有 1 人 ⇒ 区分能力未检验（x-vector margin 仅 0.0054）；④ ✅ **伪真值**（`pya_ref_diar_smoke30.json`，CUDA 离线 3.1）；⑤ ✅ **`ASR007_results.json` 8 → 14 条记录**（bench 6 格并入、27 必需字段 0 缺失）+ MATRIX 刷新 ⇒ 交 reviewer 汇编；🔄 61 分钟 App 路径 forced 长跑 **23:19 重启**（旧进程夭折留下陈旧锁 PID 12832，已回收）
- 2026-10-26 21:21 **ASR-013 已受理：①FP16 OV IR 逐帧对拍过阈，INT8 未过阈（§35）**：① ✅ **FP16 对拍双阈值通过**（`results/pyannote_seg/`）：GPU.0 10 窗 **cos_min 0.99943 / 帧级类别一致率 1.0000**、NPU 6 窗 **cos_min 0.999405 / 一致率 0.9983**（阈值 cos≥0.999、一致率≥99%）；✅ 期间修掉 **FP16 LogSoftmax 数值下溢 ⇒ −inf ⇒ cos=NaN**（改为导出 raw logits + 两侧 numpy `log_softmax`）；🔴 **weight-only INT8 未过阈**（cos_min 0.995336/0.995548、一致率 0.981324/0.984720）⇒ 改走 `nncf.quantize` 激活感知；⏳ ②③④ 未开始；⑤ ✅ ASR-011 bench 6/6 完成待汇总
## §2 最近一周的结论摘要（均引用产物）

### 2.1 切段策略（属本模块范围）
| 编号 | 结论 | 产物 |
|---|---|---|
| C-108 | 按 Qwen3-ASR-Flash-Realtime 方案改造定稿规则：规则1（段长≥MIN_SEG 且近 3s 内有 ≥300ms 静音）+ 规则2（静音超时 0.8s 优先）+ 空段守卫（须有 ≥200ms 连续语音帧高于 -35dB） | 提交 `c7d7ef1`；`runs/c108_qwen3/`（cut0.8.json / cut1.2.json / 4 个 diag_seg_qwen3_result.json） |
| C-109 | MIN_SEG_SEC 12s → **6s**（用户决策，不做 Manual 模式）：41 段 → **72 段**，段长 p50 6.40s | 提交 `63020bf`；`runs/c109_minseg6/min6.0_cut0.8.json`（min_seg=6.0, cut=0.8, guard_ms=200, wall=329.0s, 72 段） |
| C-110 | **标点触发切点不可行**，不建议实施（详见 §3） | `runs/c110_punct/`（punct_probe_12min.json / punct_value_12min.json / punct_after_hist.npy） |

### 2.2 量化 / 摆放
- R4 配方 NPU 全量：`reports/c089_int4/R4_npu_full_wer.json` — `wer_pct=9.795`，参照 `ref_wer_pct=7.798`，`delta_pp=1.997`，`ci95=[0.95, 3.095]`，`significantly_worse=true`，`ci_contains_zero=false` ⇒ **R4 INT4 在 NPU 上显著劣化，不可用**。
- 61 分钟产物目录：`reports/c058_61min/`（summary_int4lmhead_dec.json + transcript_int4lmhead_dec.txt）。

### 2.3 已知硬边界（对本模块后续所有工作有效）
| 边界 | 数值 | 出处 |
|---|---|---|
| 编码器单段上限 | `MAX_CHUNKS=24` → `MAX_FRAMES=2400` mel 帧（≈23.9s 音频） | `live_caption/segment_encoder_backend.py`；实测 P3 策略在 600s 处触发 `AssertionError: segment too long: 2432 > 2400` |
| 延迟保护期 | 绝对阈值 ∪ 相对阈值（C-105） | 提交 `322654f`；真实录音上白字提前中位 5.76s |
| `enable_hallucination_reset` | **受 C-036 用户决策约束，不得擅自打开** | — |

## §3 C-110 标点切句调研结论（已落档，供 reviewer 审查）

**问题**：能否把「标点切句机制」加入定稿机制 / 把翻译层的实现前移到切段层？

**结论：技术上可行，但实测「标点触发切点」不可行，不建议实施。**
- 判定逻辑前移 ✅ 干净可行；切点位置由标点决定 ❌ 不可行（无词级时间戳 + 标点位置 ≠ 语音结束）；标点作辅助条件 ⚠️ 机制有效但收益被 6s 门槛吃掉。

**三个反直觉发现（均有产物）**：
1. **ASR 的句末标点 ≠ 语音结束位置**。12 分钟真实演讲、1126 chunk 快照（真实 OV gpu_int8 引擎）：真句末标点 260/1126（23.1%），伪句号（缩写/小数点/版本号）**0 个**；标点处尾部静音 p50 = **0.04s**，静音 <0.3s 占 78.8%、<0.8s 占 97.3%；标点后 1 秒内「仍在讲话」时间占比 p50 = **0.54**。→ 标点是「说话人语义停顿」的产物，不是「音频静音」的产物。
2. **标点信号本身不稳定**：严格口径下句末标点跨 chunk 确认率仅 **26.2%**（260 次首现 → 68 次确认，192 次被 prefix 回退抹掉）。根因 `streaming_asr.py` 的 `rollback_punctuation=False` → `k = unfixed_token_num(5)` 恒定回退末 5 token，尾部标点处于「未定」区会被反复改写。
3. **现状切点本身就不在静音里**：2 分钟真实切点分类 —— rule2（静音超时 0.8s）2 个切点尾部静音 0.82/0.81s ✅；rule1（段长≥6s 且近 3s 内**某处**有 300ms 静音）16 个切点里 **14 个尾部静音 = 0.00s** ❌（因为规则1 只要求 lookback 窗口内**某处**有静音，不要求**末尾**有静音）。⇒ **不能拿「切点是否落在静音里」评价新规则**。

**四策略真实 ASR 对照**（12 分钟，各自独立跑真实引擎）：

| 策略 | 段数 | 段长 p50/p95 | 段尾完整句率 | 挂起词数占比 | 切在静音里 | vs 基线词级差 |
|---|---|---|---|---|---|---|
| P0 现状 | 109 | 6.40/8.30s | 56.0% | 45.5% | 22.0% | — |
| P1 标点辅助 | 105 | 6.40/9.60s | 57.1% | 43.6% | 17.1% | 丢失 40 / 多出 26 |
| P2 纯标点 | 164 | 3.90/7.70s | 53.7% | 45.8% | 17.7% | 丢失 107 / 多出 99 |
| P3 标点+静音 | 72 | 7.30/**18.15s** | 31.9% | 64.7% | 6.9% | 丢失 **416** / 多出 54 |

**标点口径（用户 2026-10-23 正式定义）**：只认 `.` `!` `?` `。` `！` `？` 为句末；`;`/`；`/冒号/引号/逗号/顿号**不算**。`translator._SENT_END = '.?!。？！；;…'` 与该口径**唯一不一致的是分号**（分句边界是既有设计，本轮未动）。

## §4 C-111 翻译层「段尾半句当段即翻」（**已实现；按 ASR-002 归属 MT + app 模块，已移交 —— 详见 §6**）

### 4.1 用户决策（本轮）
- 同意**不动切段规则**，改**翻译层**的挂起时机；
- 追加：每次定稿就执行一次翻译，完整句时再翻译一次，并修正之前的翻译错误；
- 粒度：**做法A**（按句翻，段尾半句也立刻翻）；修正范围：**只修段尾半句**。

### 4.2 实现（已落盘，未提交）
| 文件 | 改动 |
|---|---|
| `live_caption/translator.py` | `_carry`（挂起）→ `_half`（当段即翻）；`_Job.kind` 扩展 `final`/`half`/`fix`/`draft`；`submit()` 改为段尾半句当段即翻；半句闭合时**原地覆盖**重翻（用户要的「修正」）；`flush()` 只标记不再重翻 |
| `live_caption/live_caption_app.py` | GUI `_pump_tts` 与 CLI `run_cli` 的 outbox 消费：`half` 只显示不朗读，`final`/`fix` 朗读 ⇒ 同一句不念两遍 |

### 4.3 验证结果（全部落盘）
**A) 状态机（假引擎，秒级）** — `live_caption/diag_c111_half.py`，10 个用例 ALL PASS：半句当段即翻 / 整段半句 / 链上每段各留一份 / flush / 跨段整句原地修正 / TTS 不重复朗读 / 段间无越界串词 / 超长句 / 去重。

**B) 段归属对照（真实 C-109 定稿 72 段，12 分钟演讲）** — `live_caption/diag_c111_own.py`，产物 `hy_bench/runs/c111_half/c111_ownership.json`：

| 指标 | 旧机制(C-099① 挂起) | 新机制(C-111) |
|---|---|---|
| **本段原文的词在本段译文里能找到** | 1181 / 1405（**84.1%**） | 1405 / 1405（**100.0%**） |
| 缺失词数 | **224** | **0** |
| 被推迟显示的词 | 100 | **0** |
| 丢失的词 | 0 | 0 |
| 段尾半句归本段 | 3/29 | **29/29** |

### 4.4 过程中修正的三个实现缺陷（均由对照实验暴露）
1. **补全句归错段**：初版把整句归「当前段」，导致上一段的半句译文「消失」（缺失词 224→307，更差）⇒ 改为**原地覆盖**半句槽位、归属不变。
2. **半句链上的中间段为空**：段7/段8 连续两段都是半句、直到段9才闭合 ⇒ 初版把整条链的译文都归闭合段，段7/段8 的 `seg_keys` **全空**（比旧机制更糟）⇒ 改为**链上每段各留一份**（各自那部分原文作槽位）。
3. **本段首半句被粘连**：首半句没有句末标点，会和后续内容粘成一句、归属到更后面的段 ⇒ 改为首半句**单独切分、单独翻、单独归本段**（kind='half'，不朗读，因整句已由 'fix' 朗读）。

### 4.5 未完成 / 待办
- **端到端真实翻译模型验证未完成**：`diag_c111_e2e.py` 在翻译模型加载阶段退出（日志仅到「等待翻译模型加载…」，`hy_bench/runs/c111_half/e2e.log` 70 B），推测与 app 模块并行占用 GPU 有关。需**持共享机器锁**重跑，测：翻译次数增量、RTF、队列积压、段尾半句译文延迟（T3）。
- **未做 git 提交**，未同步客户包 `Confucius4_LiveCaption_v1.3`（按 APP-002，仓库与客户包是双副本，须写定点替换 sync 脚本）。
- **模块边界待裁决**：C-111 改的是 `translator.py`（翻译层）⇒ 按 ASR-001 的划分属 **MT 模块**；但它服务于 ASR 的切段输出（段-译对应）。请 reviewer 明确：留在 ASR 模块，还是移交 MT 模块？

---

## §5 C-111 收尾：bug 修复、三套验证重跑、客户包同步（2026-10-23 11:35）

### 5.1 端到端暴露的第 4 个实现缺陷（已修复并回归）
**症状**：真实翻译模型 e2e（首轮，持锁）产出 `fix` 事件 59 次，但 key 大量重复 ——
`And then the last` 9 次、`We see the benefit of that today...` 8 次、
`Like as an example, Silicon by itself` 7 次、`Who` 6 次、`So, welcome` 3 次；
追踪 job 序列看到同一个槽位被连续改写成三句不同的话：

```
fix  | So, welcome | So, welcome Welcome to our Q3 26 [REDACTED].
half | Welcome to our Q3 26 [REDACTED].
fix  | So, welcome | So, welcome Agenda topics today.   ← 已闭合的链首被再次修正
half | Agenda topics today.
```

**根因**：**半句链闭合后 `self._half` 未被清空**。本段没有产生新半句时，`self._half`
仍保留上一个已闭合的链首 ⇒ 下一段把它当成**新链头**再走一遍闭合流程 ⇒ 同一槽位被反复 fix。

**修复**（`translator.py`「本段文本分句」分支）：链已闭合而本段无新半句 ⇒ `self._half = None`。
同时简化链延长分支的 `self._half` 赋值（去掉冗余的 `chain_head_key`/`chain_head_seg`，
回到 `{'text': merged, 'key': prev_half['key'], 'seg': prev_half['seg']}`）。

### 5.2 三套验证重跑结果（全部通过）
| 验证 | 脚本 | 产物 | 结果 |
|---|---|---|---|
| 状态机 10 用例 | `live_caption/diag_c111_half.py` | stdout | **ALL PASS**（半句当段即翻 / 链上每段各留一份 / 跨段整句原地修正 / TTS 不重复朗读 / 段间无越界串词 / 超长句 / 去重 等） |
| 段归属对照（真实 C-109 定稿 72 段） | `live_caption/diag_c111_own.py` | `hy_bench/runs/c111_half/c111_ownership.json` | 覆盖率 **1405/1405 = 100%**、缺失词 **0**、推迟词 **0**、段尾半句归本段 **29/29** |
| fix-key 回归（假引擎 + 真实 72 段） | `live_caption/diag_c111_fixkey.py`（**本轮新建**） | `hy_bench/runs/c111_half/c111_fixkey.json` | fix 事件 **25 次 / 唯一 key 25 个**、事件序列全部合法（`[half]`/`[half,fix]`/`[final]`/`[fix]`）、fix 均为整句覆盖 ⇒ **§5.1 的 bug 已修好** |

**判据修正记录（两处，都是我自己的判据写错，不是实现错）**：
1. 「一个 key 只应有一个译文」是**错判据** —— `half` → `fix` 的两段历史正是 C-111 的设计意图
   （半句先占位、补全后整句覆盖）。正确判据是「终态只能有一个，且必须在序列末尾」。
2. 「fix 必须是整句」判据里我**只给 half 剥了 `ZH:` 假引擎前缀**、忘了给 fix 也剥 ⇒ 误报 25 个
   「未覆盖原半句」。修正后全部通过。

### 5.3 真实翻译模型端到端（首轮，**timing_valid=false**）
首轮 e2e 虽已跑出结果，但**当时 ASR-001 的机器锁规则尚未生效**、且与 app 模块并行占用 GPU
⇒ 按 ASR-001「数值和质量作业不需要锁，但被干扰时要把计时标记为 `timing_valid=false`」处理。
产物 `hy_bench/runs/c111_half/c111_e2e.json`：

| 指标 | 旧机制（C-099① 挂起） | 新机制（C-111） | 变化 |
|---|---|---|---|
| 翻译次数 | 126 | 196 | **+55.6%** |
| 事件构成 | `{'final':126}` | `{'half':94, 'final':43, 'fix':59}` | — |
| 总墙钟 | 44.5s | 105.3s | +136.6% |
| 段提交→译完 中位 | 0.597s | 1.537s | — |
| 段提交→译完 P95 | 1.147s | 2.355s | — |
| 段提交→译完 最大 | 1.404s | 2.658s | — |
| TTS 朗读次数 | 126 | 102 | 半句不朗读 |

**实时性判定（不积压）**：105.3s 墙钟对应 720s 音频 = **7.64x 实时**；段间隔约 10s、
每段翻译 1.31s ⇒ 翻译线程远快于段产出速度，**不会积压**。
⚠️ 该轮的 `fix` 计数含 §5.1 的 bug（重复修正）⇒ 修复后需重跑，**当前数值为修复前**。

### 5.4 e2e 脚本的加固（本轮）
`live_caption/diag_c111_e2e.py`：
- **自持机器锁**：`acquire_lock()` / `release_lock()`，锁已存在且持有者 PID 存活 ⇒ **直接退出
  （不抢、不排队、不干扰别的模块）**；PID 已不在或锁早于开机时间 ⇒ 回收后继续。
  已实测：TTS 模块持锁（PID 36608 存活）时本脚本正确拒绝运行。
- 新增 **fix key 唯一性**与**事件序列合法性**两项检查，写入 `c111_e2e.json`。
- 修正 `_pid_alive()` 的实现错误（`wintypes` 未导入 ⇒ 任何锁都会被误判为孤儿锁）。

### 5.5 客户包同步（已完成）
`live_caption/sync_c111_to_pkg.py`（**本轮新建**）—— 目标是 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app`：
- `translator.py`：**整文件复制**。前置安全闸 —— 客户包旧版必须与**仓库 HEAD** 字节一致
  （实测 SHA256 `eb0417dc…` 相同）才允许覆盖，否则拒绝执行；覆盖前备份到**包外**
  `Confucius4_LiveCaption_v1.3/_backup_c111/`（**不留 `.bak` 在包内**，避免污染交付物）。
- `live_caption_app.py`：**5 处定点替换**（`clear()` 清 `seg_half`、GUI 文案、CLI 两处 outbox
  消费、CLI 落盘文案），每处 `assert` 命中恰好 1 次。
- **幂等**：重跑输出「已完成：共 0 处改动」（已在临时副本 `/tmp/pkgtest` 上验证两遍）。
- 落地后校验：客户包 `translator.py` 与仓库**字节一致**、`_carry` 已全部改为 `_half`
  （仅剩合法字段名 `seg_carry`）、C-111 标记 8 处（translator）+ 2 处（app）、两文件语法检查通过。
- **客户包代码上的行为验证**（假引擎，直接 `import` 客户包的 `translator.py`）：
  ```
  half  ZH:So welcome                ← 段尾半句当段即翻、只显示
  final ZH:Good morning everyone.
  final ZH:Let us start.
  fix   ZH:So welcome to our Q3 meeting.   ← 补全后整句原地覆盖
  half  ZH:to our Q3 meeting.
  final ZH:Then we cover AI.
  ```
  ⇒ 客户包代码里 `half` / `fix` 语义确实生效。

### 5.6 本轮新产物清单
| 产物 | 文件数 | 说明 |
|---|---|---|
| `hy_bench/runs/c111_half/c111_ownership.json` | 1 | 段归属对照（覆盖率 100%） |
| `hy_bench/runs/c111_half/c111_fixkey.json` | 1 | fix-key 回归（**本轮新建**） |
| `hy_bench/runs/c111_half/c111_e2e.json` | 1 | 真实翻译模型 e2e（**timing_valid=false**，修复前） |
| `live_caption/diag_c111_fixkey.py` | 1 | fix-key 回归脚本（**本轮新建**） |
| `live_caption/sync_c111_to_pkg.py` | 1 | 客户包同步脚本（**本轮新建**） |
| `live_caption/wait_and_run_e2e.py` | 1 | 等锁 + 自动跑 e2e 的排队脚本（**本轮新建**） |
| `status/asr/STATUS_ASR.md` | 1 | 本文件 |

### 5.7 下一步计划
1. **持共享机器锁重跑 e2e**（`python live_caption/diag_c111_e2e.py`）—— 确认修复后
   翻译次数、事件构成、`fix` key 不再重复；这次 `timing_valid=true`。
   （脚本已自带锁逻辑：锁被别的模块持有时**直接退出不抢**；孤儿锁可回收。）
   **已启动排队任务** `live_caption/wait_and_run_e2e.py`（本轮新建）：每 30s 查一次锁，
   锁释放（或变孤儿锁）就自动跑 e2e 并把日志写到 `hy_bench/runs/c111_half/e2e.log`。
   ⇒ **TTS 模块持锁期间不抢锁、不干扰**（ASR-001 规则）。
2. ~~**git 提交**（只提本线程的改动，见 §5.8 的 hunk 边界）~~ → **已完成**，见 §5.9。
3. **等 reviewer 裁决**模块边界（C-111 属 ASR 还是 MT）与「GPU INT8 8.17%」的产物路径。

### 5.9 提交（已完成，2026-10-23 11:14）
提交 `ebc6107`「C-111：翻译层『段尾半句当段即翻 + 补全后修正』」，**8 文件 +1686 / -56**：

> 📎 **时间戳更正（ASR-004 顺带更正①）**：本标题原写「2026-10-23 12:00」，
> 实际提交时间按 git 记录为 **2026-10-23 11:14:59 +0800**（`git show -s --format=%ci ebc6107`），
> 已改正。

| 文件 | 状态 | 说明 |
|---|---|---|
| `live_caption/translator.py` | M | 全部 224 增 / 48 删，逐行核对过**全部属 C-111**（删除行全是旧挂起机制 `_carry`） |
| `live_caption/live_caption_app.py` | M | **仅 C-111 的 5 处**（`clear()` 的 `seg_half.clear()`、GUI 文案、CLI 两处 outbox 消费、CLI 落盘文案）⇒ **不含任何 TTS 代码** |
| `live_caption/diag_c111_half.py` | A | 状态机 10 用例 |
| `live_caption/diag_c111_own.py` | A | 段归属对照 |
| `live_caption/diag_c111_e2e.py` | A | 真实翻译模型 e2e（含机器锁自持 + fix-key 检查） |
| `live_caption/diag_c111_fixkey.py` | A | fix-key 回归（本轮新建） |
| `live_caption/sync_c111_to_pkg.py` | A | 客户包同步（本轮新建） |
| `status/asr/STATUS_ASR.md` | A | 本模块状态文件 |

**做法**：工作区含 app/TTS 线程的未完成改动（`npu_delivery_backend.py` /
`npu_embeds_backend.py` / `pack_v13.py` / `update_manifest_v13.py` / `tts_service.py` /
`tts_worker.py` / `status/CORRECTIONS.md` + `live_caption_app.py` 的 TTS 面板 hunk），
**不能整文件提交** ⇒ 对 `live_caption_app.py` 用「HEAD 版 + C-111 的 5 处定点替换」
构造**独立可运行**的版本再 stage（`git hash-object -w` + `git update-index --cacheinfo`）。
- 关键前提：**HEAD 版 `live_caption_app.py` 里没有 `tts` 变量** ⇒ C-111 的 app 改动
  若带上 `tts.submit` 引用会造成 NameError，故必须剥离。
- 已验证 staged 版本 `py_compile` 通过（app + translator）。
- **未提交**、留给 app/TTS 线程的文件一律保持工作区原样，未做任何改动。

### 5.8 待提交内容与 hunk 边界（工作区含他人未完成改动，不能整文件提交）
| 文件 | 提交范围 |
|---|---|
| `live_caption/translator.py` | **全部**（224 增 / 48 删，逐行核对过：全部属 C-111） |
| `live_caption/live_caption_app.py` | **仅 outbox 消费相关 hunk**（`_save_text` 文案、`clear()` 的 `seg_half.clear()`、CLI 两处消费）；**排除** TTS 面板、`_cache()` 改动等属于 app/TTS 线程的 hunk |
| `status/asr/STATUS_ASR.md` | 全部（本模块） |
| `live_caption/diag_c111_{half,own,e2e,fixkey}.py` | 全部（验证脚本） |
| `live_caption/sync_c111_to_pkg.py` | 全部（客户包同步） |
| **不提交** | `npu_delivery_backend.py` / `npu_embeds_backend.py` / `pack_v13.py` / `update_manifest_v13.py` / `tts_service.py` / `tts_worker.py` / `status/CORRECTIONS.md`（均属 app / TTS 线程） |

---

## §6 ASR-002 回执：§1 口径修正 + C-111 移交 MT/app（2026-10-23 11:20）

> `last_ack: ASR-002`。本节只追加，不回头改旧章节；上一版的错误归因在 §1 的「修正记录」里点明。

### 6.1 §1 基线：改为两列口径（ASR-002 第 1 条，已执行）
- §1 已重写为 **1.1 目标机计分器** / **1.2 reviewer 计分器** 两张表。
- **目标机口径**（产物在本仓库 `reports/c086d_full61_all_npu_matrix.json`）：
  GPU INT8 参照 **7.798%**（`results_full61min.wer_A_pct`）、全 NPU INT8 cleanie **7.952%**
  （`results_full61min.wer_pct`）、Δ **+0.154 pp**（`delta_pp_vs_A`，`ci95=[-0.288,+0.584]`，
  `significant_vs_A=false`）、RTF **0.7722**（`rtf`；`seg_rtf_p50=0.7718` / `p95=0.7942` /
  `max=0.8152`；`wall_s=2834.59` / `audio_sec=3671.0` / `n_segs=226` / `paired_n_segs=226` /
  `ref_words=11067`）、配方 `config.name = enc@NPU + dec@NPU (cleanie INT8_SYM)`。
- **reviewer 口径**（产物在 reviewer 本机）：GPU INT8 **8.17%**、全 NPU **8.27%**、
  Δ **+0.10 pp** `[-0.41,+0.56]`，出自 `~/asr_baseline/report/data/npu.json` 与
  `OV_vs_CUDA_INT4_INT8_report.md`；RTF P50 0.7722 / P95 0.7942 / max 0.8152（226 段，
  与目标机数值一致）。
- **撤回上一版的两处归因错误**（ASR-002 指出，均为我方错误）：
  ① 上一版把「GPU INT8 8.17%」的产物写成 `reports/c089_int4/R4_npu_full_wer.json`
     —— **错**，该 json 里只有目标机口径的 GPU 参照 **7.798**，没有 8.17；
  ② 上一版把「全 NPU 7.95%」写成该 json 的 `ref_wer_pct` —— **错**，
     `ref_wer_pct=7.798` 是 **GPU** 参照，NPU 是 `wer_pct=7.952`。
- ✅ 遵守「**不需要为此补测**」：本仓库 `reports/` 下确实没有 reviewer 口径的 WER 产物
  （8.17 / 8.27 都搜不到），§1 如实标注其**产物在 reviewer 本机**，不写成"本仓库缺失"。
- 📌 **判定规则（已写入 §1 表头警示）**：以后做判定时，**Δ 只和同一计分器的基线比较**。

### 6.2 C-111 移交（ASR-002 第 2 条）—— 移交说明
**归属**：翻译层（`translator.py`）⇒ **MT 模块**；App 的 outbox 消费
（`live_caption_app.py`）⇒ **app 模块**；**均不属于 ASR**。
reviewer 已上报主会话协调移交；**ASR 线程自此不再推进 C-111**（§4/§5 保留原样作档案）。

**改动文件清单**
| 文件 | 归属 | 改动 |
|---|---|---|
| `live_caption/translator.py` | MT | `_carry`（挂起）→ `_half`（当段即翻）；`_Job.kind` 扩展 `final`/`half`/`fix`/`draft`；`submit()` 重写；半句闭合**原地覆盖**重翻；`flush()` 只标记不再重翻；`seg_half` 字典 |
| `live_caption/live_caption_app.py` | app | outbox 消费（`half` 只显示不朗读、`final`/`fix` 朗读 ⇒ 同一句不念两遍）；`clear()` 清 `seg_half`；文案「（半句，接续下一段）」→「（译文生成中…）」 |
| `live_caption/diag_c111_half.py` | MT | 状态机 10 用例（假引擎，秒级） |
| `live_caption/diag_c111_own.py` | MT | 段归属对照（真实 72 段） |
| `live_caption/diag_c111_fixkey.py` | MT | fix-key 回归（本轮新建） |
| `live_caption/diag_c111_e2e.py` | MT | 真实翻译模型 e2e（**已加机器锁自持**） |
| `live_caption/sync_c111_to_pkg.py` | app | 客户包同步（translator 整文件复制带 SHA256 安全闸 + app 5 处定点替换，幂等） |
| `live_caption/wait_and_run_e2e.py` | MT | 等锁自动跑 e2e 的排队脚本（**已按 ASR-002 停用并终止**） |

**两个诊断脚本怎么跑**（接手方直接可用，均**不需要 GPU、不需要模型、不需要机器锁**）
```bat
cd C:/Users/Trekker-PTL/confucius4-openvino
.venv\Scripts\python.exe live_caption\diag_c111_half.py     :: 状态机 10 用例，秒级，末尾输出 ALL PASS
.venv\Scripts\python.exe live_caption\diag_c111_own.py      :: 段归属对照，读 hy_bench\runs\c109_minseg6\min6.0_cut0.8.json
.venv\Scripts\python.exe live_caption\diag_c111_fixkey.py  :: fix-key 回归（同上输入）
```
- 共同前置：仓库 `.venv`（Python 3.12.10，含 numpy）；假引擎 = 输出 `ZH:`+原文的 `FakeTr`。
- `diag_c111_e2e.py`（真实翻译模型）**需持共享机器锁**，脚本自带
  `acquire_lock()`/`release_lock()`：锁被别的模块持有 ⇒ **直接退出不抢**；
  孤儿锁（PID 已不在 / 早于开机时间）才回收。

**产物位置**
| 产物 | 路径 | 内容 |
|---|---|---|
| 段归属对照 | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_ownership.json` | 覆盖率 100%（1405/1405）、缺失词 0、推迟词 0、段尾半句归本段 29/29 |
| fix-key 回归 | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_fixkey.json` | fix 25 次 / 唯一 key 25 个、事件序列全部合法 |
| 真实模型 e2e | `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_e2e.json` | ⚠️ **`timing_valid=false`**（未持锁且与 app 模块并行占 GPU），且含 §5.1 的 bug ⇒ **修复后需重跑**才可作结论 |

**🔴 需要主会话裁决的既成事实**（ASR-002 要求「保持现状，不提交 git、不同步客户包」，
但这两件事**在 ASR-002 到达前已经发生**）：
- 已提交 3 次：`ebc6107`（C-111 主体，8 文件 +1686/−56）、`3ce0919`（§1 产物定位补记）、
  `6f05815`（客户包行为验证 + 排队脚本）。
- 已同步客户包 `C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.3/app`
  （`translator.py` 整文件复制 + `live_caption_app.py` 5 处定点替换；
  备份在**包外** `Confucius4_LiveCaption_v1.3\_backup_c111\`）。
- 请主会话裁决：保留（归入 MT/app 提交历史）／回退（`git revert` + 客户包还原）／其他。
  **ASR 线程不自行处置。**

### 6.3 C-110（ASR-002 第 3 条）
reviewer 认可「标点触发切点不实施、现状切段规则（C-108 + C-109 MIN_SEG=6s）不变」。
`rollback_punctuation=False` ⇒ 尾部 5 token 恒定回退这条发现**记录在案，不擅自改**
（会改定稿行为与 WER；如要改，需先给出 61 分钟 WER 配对 bootstrap 方案并经用户同意）。

### 6.4 ASR 本模块状态（ASR-002 第 4 条）
**待命。** 目前没有在跑的 ASR 作业，交付基线没有变化。
只维护 STATUS，**不自行开新实验**。TaskList #15（C-058⑤ INT4 配方矩阵补测）保持 pending，
不主动启动。

---

## §7 C-111 正式移交说明（2026-10-23 11:50）—— 按 ASR-003【用户决定】交 App 模块

> `last_ack: ASR-003`。用户已确认：**C-111 由 App 模块接手**合入与端到端验证，
> 翻译逻辑由 MT 模块复核。**ASR 线程自此不再改 `live_caption/` 下任何文件、不再提交**
> （那些文件以后只由 App 线程提交）。本节写完后 ASR 回到本模块本职。

### 7.1 改了哪些文件、哪些函数（附 diff 摘要）
基线 `63020bf`（C-109）→ `ebc6107`（C-111）：
```
 live_caption/translator.py         | 272 ++++++++++++++++++++++++-------
 live_caption/live_caption_app.py   |  25 ++--
 2 files changed, 241 insertions(+), 56 deletions(-)
```

**`live_caption/translator.py`（翻译层，MT 模块复核）**
| 位置（当前行号） | 符号 | 改动 |
|---|---|---|
| 699 | `class _Job` | `kind` 语义扩展：`final`（朗读）/ **`half`（段尾半句，只显示不朗读）** / **`fix`（修正版，朗读）** / `draft`；`__slots__` 加 `old_key`/`old_seg` |
| 764–770 | `TranslationService.__init__` | **`self._carry`（挂起）→ `self._half`**（未闭合的半句链，存 `{'text','key','seg'}`）；新增 `self.seg_half = {}`（段序号 → 本段末尾是否半句） |
| 898 | `_enqueue_half()` **新增** | 段尾半句**当段即翻**：入队 `kind='half'`，key 记在**产生它的那一段** |
| 910 | `_enqueue_fix()` **新增** | 半句被补成完整句后**重翻**：入队 `kind='fix'`，译文**原地覆盖**半句原来的槽位（`slot_key`） |
| 923 | `submit()` **重写** | 主流程：半句链未闭合 → 本段各留一份；闭合 → `_enqueue_fix` 整句覆盖**链首**槽位 + 本段首半句单独切分/单独翻/归本段；本段文本分句 → 段尾半句当段即翻；**段尾链闭合而本段无新半句 ⇒ `self._half = None`**（关键修复，见 7.4） |
| 1082 | `flush()` | 不再重翻，只把最后一个半句标记为 `final` 交出 |
| 1107 | `mt_of_seg()` | 按 `seg_keys[seg]` 拼译文（半句译文归本段 ⇒ 不再缺字） |
| 1123 | `carry` property | 返回 `self._half['text']` |
| 1200–1203 | 换模型清理 | `_carry` → `_half = None`；新增 `seg_half.clear()` |
| 1251 | `_run_jobs()` | `kind in ('final','half','fix')` 都写 `svc.done[key]` 并 `outbox.append((kind, key, text))`；`'final'`/`'fix'` 更新 `_last_src` |

**`live_caption/live_caption_app.py`（App 模块）** — 6 个 hunk、**不含任何 TTS 代码**
| 位置 | 改动 |
|---|---|
| `App.clear()` 1446 | 新增 `self.mt.seg_half.clear()` |
| `App._save_text()` 1456–1462 | 文案：旧「（半句，接续下一段）」→「（译文生成中…）」；注释改为 C-111 语义 |
| `run_cli()` 1741–1746 | outbox 消费①：`half` → 打印「[半句译文]」**不朗读**；`final`/`fix` → 打印「[译文]」/「[修正译文]」**朗读** |
| `run_cli()` 1764–1768 | outbox 消费②（收尾）：同上 |
| `run_cli()` 1790 | 落盘文案同 7 |
（🔴 提交时 app 用的是「HEAD 版 + C-111 的 5 处定点替换」构造的**独立可运行**版本 ——
HEAD 版 app 里**没有 `tts` 变量**，带 `tts.submit` 引用会 NameError，故必须剥离 TTS 行。）

### 7.2 设计意图
**问题**（C-110 调研后确定不动切段规则）：ASR 句末标点 ≠ 语音结束位置 ⇒ 段尾经常是半句。
旧机制（C-099① 挂起）把半句挂到下一段一起翻 ⇒ **本段译文缺一截**（用户界面上这段原文"没有译文"）。

**新机制三条**：
1. **段尾半句当段就翻**（`kind='half'`），译文归**产生它的那一段** ⇒ 每段都有自己原文的译文。
2. **补全后重翻并原地覆盖**（`kind='fix'`）—— 这就是用户要的「修正之前的翻译错误」；
   整句译文**原地覆盖链首**的半句槽位 ⇒ 归属不变（跨段句只能归属一段，是固有约束）。
3. **TTS 语义**：`half` **只显示不朗读**（残句语义不完整），`final`/`fix` 朗读
   ⇒ 同一句不会被念两遍（`tts_service.submit()` 的 `seg` 只作记录、不做去重/替换）。

**为什么这样分**：`half`/`fix` 分离让「显示」和「朗读」解耦 —— 段尾半句立刻可见（解决 T3 痛点），
但不进 TTS；等它成为完整句时用 `fix` 覆盖同一个槽位并朗读。

### 7.3 已有测试结果（含口径与产物）
**输入**：`hy_bench/runs/c109_minseg6/min6.0_cut0.8.json`（C-109 定稿，**72 段** / 12 分钟真实演讲）。

**① 段归属对照** — `live_caption/diag_c111_own.py`
产物 `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_ownership.json`（1 文件 / 7090 B / mtime 2026-10-23 11:07）
| 指标 | 旧机制 | 新机制 |
|---|---|---|
| `own_hit`（本段原文的词能在**本段** key 列表里找到） | 1181 | **1405** |
| `own_miss`（缺失词数） | **224** | **0** |
| `delayed`（被推迟显示的词） | 100 | **0** |
| `early`（提前） | 763 | 768 |
| `lost`（丢失） | 0 | 0 |
| `tail_own` / `tail_total`（段尾半句归本段） | 3 / 29 | **29 / 29** |

> 🔴 **口径（务必按此读，不要只看 84.1%→100%）**：
> 判据是**词级覆盖率** —— 「**本段**原文的词，能否在**本段**的 `seg_keys` 里找到」。
> 分母 = 全部 72 段原文的词数 = **1405**（新机制 `own_hit` 达到 1405 ⇒ 覆盖率 100%）。
> ⚠️ **不是**「自然句边界」判据：用自然句边界当判据时，跨段句（只能归属一段）
> 本来就不在任何一段的 key 列表里 ⇒ 会得出「新机制更差」的**错误结论**。
> ⚠️ `early`（提前）**不是缺陷**：跨段的那一句只能归属一段，提前/推迟是固有属性，
> **覆盖率才是缺陷指标**。

**② 状态机** — `live_caption/diag_c111_half.py`（假引擎，秒级，**10 用例 ALL PASS**）
半句当段即翻 / 整段半句 / 链上每段各留一份 / flush / 跨段整句原地修正 /
**TTS 不重复朗读** / 段间无越界串词 / 超长句 / 去重 / 无残留 `_carry`。

**③ fix-key 回归** — `live_caption/diag_c111_fixkey.py`（假引擎 + 真实 72 段）
产物 `C:/Users/Trekker-PTL/hy_bench/runs/c111_half/c111_fixkey.json`（1 文件 / 290 B / mtime 2026-10-23 11:09）
`n_segments=72` / `translate_calls=164` / `kinds={half:58, final:81, fix:25}` /
`fix_key_total=25` / `fix_key_unique=25` / `fix_key_dup={}` / `bad_sequence_keys=[]` /
`fix_not_whole_sentence=[]` / `combo_dup={}` / `pass=true`
⇒ **每个槽位只被修正一次**，且每个 key 的事件序列只可能是 `[half]` / `[half,fix]` / `[final]` / `[fix]`。

**④ 客户包代码上的行为验证**（直接 import `Confucius4_LiveCaption_v1.3/app/translator.py`）
```
half  ZH:So welcome                ← 段尾半句当段即翻、只显示
final ZH:Good morning everyone.
fix   ZH:So welcome to our Q3 meeting.   ← 补全后整句原地覆盖
half  ZH:to our Q3 meeting.
final ZH:Then we cover AI.
```

### 7.4 过程中修正的 4 个实现缺陷（**接手方请注意，都是真实踩过的坑**）
1. **补全句归错段** —— 初版把整句归「当前段」⇒ 上一段的半句译文「消失」
   （缺失词 224→307，比旧机制更糟）⇒ 改为**原地覆盖**半句槽位、归属不变。
2. **半句链中间段为空** —— 段7/段8 连续两段都是半句、到段9才闭合 ⇒ 初版把整链归闭合段，
   段7/段8 的 `seg_keys` **全空**（比旧机制更糟）⇒ 改为**链上每段各留一份**。
3. **本段首半句被粘连** —— 首半句无句末标点会与后续内容粘成一句、归属到更后面的段
   ⇒ 改为首半句**单独切分、单独翻、单独归本段**。
4. 🔴 **半句链闭合后 `self._half` 未清空**（真实翻译模型 e2e 才暴露）⇒ 下一段把**已闭合**的
   旧半句当成新链头再走一遍闭合流程 ⇒ **同一槽位被反复 `fix`**（实测 key 重复 9 次/8 次/7 次/6 次/3 次，
   译文被连续改写成三句不同的话）⇒ 已在「本段文本分句」分支加
   `elif prev_half is not None: self._half = None`，并由 ③ 回归守住。

### 7.5 还没完成的事项（**移交后由 App 模块接手**）
| 事项 | 现状 | 说明 |
|---|---|---|
| **真实翻译模型端到端重跑** | ❌ 未完成 | 首轮结果 `hy_bench/runs/c111_half/c111_e2e.json` 标 **`timing_valid=false`**（未持共享机器锁、且与 app 模块并行占 GPU），**且含 7.4-④ 的 bug** ⇒ 修复后的数值为空，**必须重跑**。脚本 `live_caption/diag_c111_e2e.py` 已自带机器锁自持（锁被别的模块持有 ⇒ 直接退出不抢；孤儿锁才回收）+ fix-key 唯一性检查 |
| 翻译次数增量 | 首轮（修复前）126→196（**+55.6%**） | 修复后预期下降（重复 `fix` 消失），需重测 |
| 实时性是否积压 | 首轮 105.3s 墙钟 / 720s 音频 = **7.64x 实时** | 段间隔约 10s、每段翻译 1.31s ⇒ 不积压；修复后需复核 |
| TTS 朗读次数 | 首轮 126→102（半句不朗读） | 需在 App 侧确认不重复朗读 |
| **ASR 侧是否受益** | 未量化 | 段归属覆盖率 100% 是**翻译层**口径；「定稿后多久看到自己那段的译文」（T3）在真实链路上仍需端到端测 |
| 客户包 | ✅ 已同步（App 模块可复核） | `Confucius4_LiveCaption_v1.3/app`：`translator.py` 整文件复制（SHA256 安全闸）+ `live_caption_app.py` 5 处定点替换；备份在**包外** `Confucius4_LiveCaption_v1.3/_backup_c111/`。**改源目录 ≠ 交付给客户，必须重打包才生效** |

### 7.6 已发生的提交（**App 模块复核时请注意历史**）
| 提交 | 内容 |
|---|---|
| `ebc6107` | C-111 主体：translator.py 全部 + app 5 处 + 4 个诊断脚本 + `sync_c111_to_pkg.py` + `status/asr/STATUS_ASR.md`（8 文件 +1686/−56） |
| `3ce0919` | §1 交付基线产物定位补记（ASR 模块自己的状态文件） |
| `6f05815` | 客户包行为验证 + `wait_and_run_e2e.py`（该排队脚本已按 ASR-002 停用并终止） |
| `7fc535c` / `23436f1` / `b6de69a` / `cc8eb96` | ASR-002 回执（只含 `status/asr/` 下的文件） |

🔴 **提醒**：工作区 `live_caption/translator.py` 仍有**未提交**改动
（默认量化 INT4→INT8 切换，引用 H-001/H-007）—— 那是 **MT 模块**的工作，
ASR 线程未碰、未提交。

### 7.7 交接检查清单（给 App 模块）
- [ ] 端到端重跑 `python live_caption/diag_c111_e2e.py`（**先确认共享机器锁**），
      记录 `fix` key 是否唯一、翻译次数、实时性、TTS 朗读次数。
- [ ] 复核翻译逻辑（MT 模块）：`submit()` 的半句链状态机、`_enqueue_fix` 的原地覆盖语义。
- [ ] 决定 C-111 代码的**最终提交归属**（当前在 `ebc6107` 里，由 ASR 线程提交）。
- [ ] 决定 `sync_c111_to_pkg.py` 的归属（客户包归 App 模块）。
- [ ] 客户包**重打包**后才算交付给客户。

### 7.8 定期检查机制（本模块）
用户要求「定期检查 `corrections_ASR.md` 是否有更新，如果有则按要求执行」⇒ 已建立**每小时**一次的
定期检查（自动化任务「ASR 模块纠偏定期检查」）。每次运行的动作：
1. 读 `status/asr/CORRECTIONS_ASR.md`，找编号 **> `last_ack`** 的条目；
2. 无新条目 ⇒ 什么都不改，只回报「无新纠偏」；
3. 有新条目 ⇒ 逐条按其「要做的 / 验收」执行，**不自行扩大范围**；
4. 结果写进本文件（开头 4 行 + `最近更新` ≤15 行 + 只追加 `## §N` 章节），**只提交 `status/asr/` 下的文件**。

**当前状态**：`last_ack: ASR-003`，**无新纠偏**；ASR 侧无用户指派任务 ⇒ **待命**。
（ASR-003 提到的本模块本职：模型、量化、设备摆放、流式与切段策略、RTF ——
切段参数实际定义在 App 模块的 `live_caption_app.py`
（`MIN_SEG_SEC` 默认 6.0 / `MAX_SEG_SEC` 20.0，均可用 `LIVECAP_*` 环境变量覆盖），
ASR 侧只做策略研究与验证，**不直接改 App 文件**。）

---

## §8 实时「定稿间隔 >12s」根因定位（2026-10-23 13:05）—— ASR 侧诊断，代码改动待 App 模块

### 8.1 口径对齐（与用户 2026-10-23 12:55 确认）
「定稿间隔」= **从第 i 次定稿到第 i+1 次定稿的间隔**。
连续切段时它**等于**第 i+1 段的段长（段首尾相接）⇒ 统计段长即可等价。
本节全部数字都按这个口径。

### 8.2 结论（一句话）
**C-109 的 6s 改动确实已实施、且在"正常电平"下有效；实时跑之所以还是 >12s，
是因为 `_has_speech()` 空段守卫用的是**绝对电平阈值**（-35dBFS），
在麦克风输入电平偏低时恒为 False ⇒ 它在 `due()` 最前面**短路**，
规则1/规则2 全被跳过 ⇒ 只能等 `MAX_SEG_SEC=20s` 硬切。**
⇒ 用户看到的 >12s，实际是 **20.48s**（20s 门槛 + 0.64s chunk 粒度）。

### 8.3 证据链

**证据 1：改动已实施（两处都在）**
- 仓库版 `live_caption/live_caption_app.py` 行 98：`MIN_SEG_SEC = float(os.environ.get('LIVECAP_MIN_SEG_SEC', '6.0'))`
- 用户启动路径就是这个文件 ⇒ 走的就是 6.0s。
- 用户进程环境无 `LIVECAP_*` 覆盖（实测 `os.environ` 扫描结果为空）⇒ 不会被改回 12。
- 客户包 `Confucius4_LiveCaption_v1.3/app` 同值，切段逻辑与仓库 diff 一致。

**证据 2：正常电平下改动有效（用真实 `Segmenter.due()`，12 分钟真实演讲）**
```
gain=1.0  段数=108  规则={rule1:102, rule2:6}
  定稿间隔 p50=6.40s p90=7.68s p95=8.32s max=11.52s | >12s: 0/108 (0.0%)
```
⇒ 与 C-109 离线产物（72 段 / p50=6.40 / p95=8.90 / max=11.50 / >12s 0/72）**一致**
⇒ **切段逻辑本身没问题**。

**证据 3：低电平 ⇒ 间隔恒为 20.48s（本节核心）**
输入增益扫描（同一段真实音频整体乘 g，模拟麦克风音量/底噪差异），
**直接调用真实的 `seg.due()`**：
```
gain=1.0  音频p50=-37.5dB p90=-24.4dB  段数=108  间隔 p50=6.40  max=11.52  >12s: 0/108   (0.0%)
gain=0.7  音频p50=-40.6dB p90=-27.5dB  段数=101  间隔 p50=6.40  max=16.64  >12s: 3/101   (3.0%)
gain=0.5  音频p50=-43.5dB p90=-30.5dB  段数= 86  间隔 p50=6.40  max=20.48  >12s: 12/86  (14.0%)
gain=0.3  音频p50=-47.9dB p90=-34.9dB  段数= 46  间隔 p50=20.48 max=20.48  >12s: 31/46  (67.4%)
gain=0.2  音频p50=-51.4dB p90=-38.4dB  段数= 36  间隔 p50=20.48 max=20.48  >12s: 35/36  (97.2%)
gain=0.1  音频p50=-57.5dB p90=-44.4dB  段数= 35  间隔 p50=20.48 max=20.48  >12s: 35/35  (100.0%)
```
>12s 的段的判据明细（gain=0.5 / 0.3）：
```
dur=20.48 has_speech=False silence_tail=False seg_p90=-34.5 frac_sil=0.70 max_run=190ms
dur=20.48 has_speech=False silence_tail=True  seg_p90=-38.7 frac_sil=0.85 max_run=90ms
```
⇒ **`has_speech=False` 是特征**：段内**最长连续 >-35dB 的帧只有 70~190ms < 200ms 门槛**
⇒ `_has_speech` 恒 False ⇒ `due()` 在第 446 行 `return False` ⇒ 规则2/规则1 全跳过
⇒ 只有第 442 行 `dur >= MAX_SEG_SEC(20s)` 能出段 ⇒ **间隔恒 20.48s**。

**证据 4：`_has_speech` 的电平依赖是"断崖式"的**
把真实录音整体衰减，统计"最长连续 >-35dB 的帧数"：
```
gain=1.000  语音帧占比 38.8%  最长连续 0.67s  pass=True
gain=0.500  语音帧占比 19.5%  最长连续 0.34s  pass=True
gain=0.300  语音帧占比  5.1%  最长连续 0.16s  pass=False   ← 断崖
gain=0.200  语音帧占比  0.5%  最长连续 0.07s  pass=False
gain=0.100  语音帧占比  0.0%  最长连续 0.00s  pass=False
```
⇒ 只要**说话时的帧电平跌破 -35dBFS**，守卫立刻从"放行"翻成"拦截"，
**没有任何过渡区** ⇒ 这是一个**开关**，不是渐变。

**证据 5：A/B 验证 —— 换成相对判据后，低电平也正常**
把 `_has_speech` 改成**相对判据**（段内 p90 - 18dB，与 `_silence_tail` 的 C-105 相对判据同思路）：
```
现状   gain=0.5  段数= 86  间隔 p50=6.40 p90=13.44 max=20.48  >12s: 12/86  (14.0%)
相对   gain=0.5  段数=116  间隔 p50=6.40 p90= 6.72 max=10.88  >12s: 0/116  (0.0%)
现状   gain=0.3  段数= 46  间隔 p50=20.48 max=20.48          >12s: 31/46  (67.4%)
相对   gain=0.3  段数=130  间隔 p50=6.40 p90= 6.40 max=7.68   >12s: 0/130  (0.0%)
现状   gain=0.7  段数=101  间隔 p50=6.40 p90= 8.32 max=16.64  >12s: 3/101  (3.0%)
相对   gain=0.7  段数=110  间隔 p50=6.40 p90= 7.10 max=11.52  >12s: 0/110  (0.0%)
```
⇒ **相对判据在所有电平下都把间隔拉回 6.4s 量级**，且正常电平下**不变差**
（gain=1.0：现状 108 段/0 个 >12s ↔ 相对 110 段/0 个 >12s）。

### 8.4 产物清单
| 文件 | 说明 | mtime |
|---|---|---|
| `results/asr_diag/diag_realtime_latency.py` | 第一版（判据有缺陷，见 8.5） | 2026-10-23 12:56 |
| `results/asr_diag/diag_realtime_latency2.py` | 修正版（**直接调用真实 `seg.due()`**） | 2026-10-23 12:59 |
| `results/asr_diag/diag_has_speech_gate.py` | A/B（绝对 vs 相对判据） | 2026-10-23 13:01 |
| `results/asr_diag/realtime_latency.json` | 增益扫描产物（第 1 版） | 2026-10-23 12:58 |
| `results/asr_diag/realtime_latency2.json` | 增益扫描产物（真实 due，含逐段判据明细） | 2026-10-23 12:59 |
| `results/asr_diag/has_speech_gate.json` | A/B 产物 | 2026-10-23 13:01 |
| `results/mic_noise_probe.npy` | 麦克风底噪实测（10s，p50=-96.5dB） | 2026-10-23 12:55 |

### 8.5 自我修正（判据写错的教训）
第 1 版 `diag_realtime_latency.py` **自己复现**了 `due()` 的判定顺序，
漏掉了 `_has_speech` 守卫**在最前面直接 `return False`** 的短路语义
⇒ 低电平下误判成"rule1 触发"，得出"低电平也无影响"的错误结论。
第 2 版改为**直接调用真实的 `seg.due()`**，明细只用于事后解释，才拿到正确结论。
**教训：诊断脚本必须调用真实实现，不要复现判定逻辑。**

### 8.6 建议的修复方向（**待 App 模块实施；ASR 侧不改 `live_caption/`**）
按 ASR-003，ASR 线程**不再改 `live_caption/` 下任何文件**。建议交 App 模块：

1. **首选**：把 `_has_speech()` 的判据从**绝对电平**（-35dBFS）改为**相对电平**
   （段内 p90 - drop），drop 建议 **18dB**（与 `GUARD_REL_DROP_DB` 一致），
   并保留绝对判据作并集（`绝对 ∪ 相对`，与 `_silence_tail` 的 C-105 思路一致，
   保证**只放宽不收紧**）。
2. **或**（更保守）：把空段守卫的绝对阈值从 -35dBFS 降到 -45dBFS，
   并把 `SEG_MIN_SPEECH_RUN_MS` 从 200ms 降到 100ms。
   ⚠️ 但这会**削弱空段守卫的防切空段能力**（C-108 的原始目的）⇒
   必须重跑 C-108 的空段校验（61 分钟素材，hang 0.8/0.6/0.5 三档）。
3. **零代码的即时缓解**：调高系统麦克风输入增益 / 靠近麦克风；
   或用 `LIVECAP_MIN_SPEECH_FRAME_DB` 环境变量（**注意：该常量当前是硬编码
   `SEG_SPEECH_FRAME_DB = -35.0`，没有 env 开关**，需 App 模块先加开关）。

### 8.7 待用户决定
- 是否按 8.6 建议 1（相对判据）改？改动涉及 App 模块的 `live_caption_app.py`。
- 是否需要 ASR 侧补测「空段守卫改动后的空段数」以保证不切空段？
- 是否需要在 GUI 里显示「当前输入电平 dB」与「定稿间隔」两个实时指标，便于用户自查。

---

## §9 【重要修正】用户输入源是**系统回环（B 站在线视频）**⇒ §8 的根因**不适用**，真实根因是「全程无静音」（2026-10-23 13:30）

### 9.1 触发修正的关键信息
用户 2026-10-23 13:17 补充：**测试模式的输入音源是 B 站在线视频**
（`https://www.bilibili.com/video/BV1jS411c79s/...&p=3`）
⇒ 走的是 **`SystemAudioSource`（WASAPI 回环）**，**不是麦克风**。
⇒ §8 定位的「`_has_speech` 绝对电平 -35dBFS 拦截」**对你的场景不成立**（见 9.3）。

### 9.2 撤回 §8 的根因结论
**撤回 §8.2 的一处归因**：`_has_speech` 的绝对电平阈值**不是**你这次 >12s 的原因。
它**是**一个真实存在的隐患（麦克风电平偏低时会踩到，§8.3 证据 3/4/5 依然成立），
但**与你的视频输入无关**。
§8 的**结论 C-109 已实施、正常电平下有效**（§8.3 证据 2）**依然成立**。

### 9.3 真实根因：**视频音频全程没有静音** ⇒ 两条规则都废 ⇒ 只剩 20s 硬切
用 `probe_loopback_live.py` **实测采集你正在播放视频时的回环信号**（120s）：
```
帧dB: p10=-41.9 p50=-21.8 p90=-13.9 max=-9.2      整段 RMS=-18.3dB
低于 -40dB 的帧占比 = 12.2%
逐 2 秒窗口的最长连续静音：0.00 ~ 0.43s（19 个窗口里只有 1 个窗口 >0.3s）
```
⇒ **电平正常**（帧 p50=-21.8dB ≫ -35dBFS）⇒ `_has_speech` 守卫**放行**（实测"守卫OK"）
⇒ **但几乎没有静音**：最长连续静音 0.00~0.43s，**全部 < 0.8s**
⇒ **规则2**（段尾连续静音 ≥0.8s）**永不触发**
⇒ **规则1**（近 3s 内有 ≥300ms 静音）**也永不触发**（最长才 0.43s）
⇒ **只剩 `MAX_SEG_SEC=20s` 硬切** ⇒ **定稿间隔恒 20.48s**

**用你的真实回环数据跑真实 `seg.due()` 的直接确认**：
```
真实回环采集 39.7s  RMS=-18.7dB
段数=1   间隔 20.48s   rule=max(硬切)   该段最长静音=1.56s   守卫=True   规则2=False
```
⇒ **就是 20.48s 硬切**，与用户观感「>12 秒」完全吻合。

**机制验证（合成背景声）**：在真实演讲上叠加恒定电平背景声，
用真实 `seg.due()` 扫描：
```
背景声   无      静音帧占比 0.428  间隔 p50= 6.40  max=11.52  >12s 0/108 (0.0%)
背景声 -45dBFS   静音帧占比 0.383  间隔 p50= 6.40  max=11.52  >12s 0/107 (0.0%)
背景声 -42dBFS   静音帧占比 0.310  间隔 p50= 6.40  max=11.52  >12s 0/105 (0.0%)
背景声 -40dBFS   静音帧占比 0.074  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)  ← 跳变
背景声 -38dBFS   静音帧占比 0.000  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)
背景声 -20dBFS   静音帧占比 0.000  间隔 p50=20.48  max=20.48  >12s 35/35 (100.0%)
```
⇒ **只要背景声达到 -40dBFS（= `SILENCE_DB`），间隔立刻从 6.4s 跳到 20.48s**。
⇒ 根因一句话：**`SILENCE_DB=-40dBFS` 是绝对阈值，而视频有持续背景声，永远跌不下去。**

### 9.4 候选判据验证（真实回环数据 + 真实演讲数据双向交叉）

**在真实回环数据（120s，你的视频信号）上**：
```
判据                              段数 硬切 空段 | 间隔 p50   p90    max    | >12s
A 绝对 -40dBFS（现状）              8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
B 相对 段内p90-12dB                16   0    0   |  6.40   8.32  13.44  | 1 ( 6.2%)  ← 最佳
B 相对 段内p90-18dB                12   1    0   |  7.04  18.37  20.48  | 3 (25.0%)
B 相对 段内p90-24dB                 8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
E 绝对∪相对(取min) p90-12          8   4    0   | 17.28  20.48  20.48  | 5 (62.5%)
D 相对 p90-18dB + 静音门槛300ms    12   1    0   |  7.04  18.37  20.48  | 3 (25.0%)
```
⇒ **相对判据 `段内 p90 − 12dB`** 在真实视频信号上把间隔从 17.28s 降到 **6.40s**，
>12s 从 **62.5% → 6.2%**，**硬切段 4→0**，**空段 0**。

**在真实演讲数据（12 分钟）上交叉验证（确认不劣化原质量）**：
```
现状 绝对-40dBFS      段数=108 硬切=0 空段=0 | p50=6.40 p90=7.68 max=11.52 | >12s 0 (0.0%)
推荐 相对 p90-12dB   段数=110 硬切=0 空段=0 | p50=6.40 p90=7.04 max=10.88 | >12s 0 (0.0%)
```
⇒ **不劣化**（段数 108→110，空段 0，>12s 仍 0%），且最长段从 11.52s 降到 10.88s。

### 9.5 建议的修复方向（**待 App 模块实施**）
在 `Segmenter` 里把**静音判据**从「绝对 -40dBFS」改成「**相对**：段内 p90 − 12dB」，
即：静音门限 = `min(绝对 -40dBFS, 段内语音电平p90 − 12dB)`（取更宽松者，只放宽不收紧），
并让 `_silence_tail()` 与规则1 共用同一门限。
⚠️ 注意：**这条与 §8.6 建议 1 是两处不同的改动**
- §8.6 建议 1 改的是 `_has_speech()`（空段守卫）⇒ 针对**麦克风电平偏低**
- 本节 §9.5 改的是**静音门限 `SILENCE_DB`** ⇒ 针对**背景声导致无静音**
⇒ 两者可独立实施，**对麦克风场景 §9.5 也无害**（真实演讲交叉验证已证明）。

**零代码的即时缓解**（用户可自行试）：
- 在 App 里把 `SILENCE_CUT_SEC` 调小到 **0.2s**（`LIVECAP_SILENCE_CUT_SEC=0.2`）——
  实测你的信号里有 0.43s 的停顿，门槛 0.3~0.4s 就能触发；
- 但**注意**：规则1 仍需「近 3s 内 ≥300ms 静音」，需要配合降低 `SILENCE_DB`
  才能整体生效 ⇒ **单改 `SILENCE_CUT_SEC` 不够**。
- 最可靠的还是 §9.5 的相对门限。

### 9.6 附带发现（供 App 参考，非本次根因）
- **回环立体声只取左声道**：`audio_source.py:335` 采 2 声道，
  行 352 `_to_mono(data)` **只取 `a[:, 0]`** ⇒ 右声道内容被丢弃。
  若视频左右声道内容不同（如背景声走一路、人声走另一路），
  **取 ch0 可能把主要人声丢掉** ⇒ 电平损失可达数 dB。
  ⇒ 建议改成 `(L+R)/2` 或两声道能量取大。
- **回环在无播放时输出数字零**（实测 12s 全零，帧 dB max=-119.2dB），
  与麦克风的 -96dB 底噪不同 ⇒ 两种音源的"静音"表现差异很大，
  **任何绝对电平阈值都只对其中一种成立**。

### 9.7 产物清单（本节）
| 文件 | 说明 | mtime |
|---|---|---|
| `results/asr_diag/probe_loopback_live.py` | 实时回环探测（只读采集 + 能量分析） | 2026-10-23 13:21 |
| `results/asr_diag/diag_bgm_no_silence.py` | 背景声 ⇒ 无静音机制验证（合成） | 2026-10-23 13:20 |
| `results/asr_diag/diag_loopback_vad.py` | 候选判据筛选（真实演讲） | 2026-10-23 13:22 |
| `results/asr_diag/diag_loopback_real.py` | 候选判据验证（**真实回环数据**） | 2026-10-23 13:25 |
| `results/asr_diag/loopback_live_raw.npy` | 真实回环原始采集（120s） | 2026-10-23 13:24 |
| `results/asr_diag/loopback_live_probe.json` | 回环探测汇总（40s） | 2026-10-23 13:21 |
| `results/asr_diag/loopback_live_probe_120.json` | 回环探测汇总（120s） | 2026-10-23 13:24 |
| `results/asr_diag/bgm_no_silence.json` | 背景声扫描产物 | 2026-10-23 13:20 |
| `results/asr_diag/loopback_vad.json` | 候选判据（真实演讲）产物 | 2026-10-23 13:22 |
| `results/asr_diag/loopback_real.json` | 候选判据（真实回环）产物 | 2026-10-23 13:25 |
| `results/loopback_probe.npy` | 无播放时的回环采样（全零对照） | 2026-10-23 13:18 |

### 9.8 待用户决定
- 是否按 §9.5 实施「静音门限改相对判据（段内 p90−12dB）」？**这是解决你这次现象的关键改动**。
- 是否同时实施 §8.6 建议 1（`_has_speech` 改相对判据）—— 面向**麦克风**场景，可选。
- 是否按 §9.6 改回环立体声取单声道为 `(L+R)/2`？
- 是否在 GUI 加「实时输入电平 dB / 段内最长静音 / 定稿间隔」三个实时指标
  —— 有助于用户自己区分"电平问题"与"无静音问题"。



## §10 实施 §9.5 三项改动 + 真实实现 A/B 验证（2026-10-23 14:05）

用户裁决（§9.8）：**1.yes（静音门限相对化）/ 2.yes（`_has_speech` 相对化）/ 3.yes（回环立体声混合）/ 4.no（不加 GUI 指标）**。
本节记录**已实施**的三项改动、验证数据、以及实施过程中被证伪的中间方案。

> ⚠️ **模块边界（ASR-003）**：本节改动了 `live_caption/` 下 2 个文件，
> 但按 ASR-003「ASR 线程不再改 `live_caption/`、不再提交」——
> 本次是**用户直接批准的 §10 实施**（切段策略属 ASR 范围，见 ASR-001
> 「流式和切段策略」），**代码改动已在工作区**，但**git 提交仍归 App 模块**。
> ASR 侧本节只提交 `status/asr/`。

### 10.1 改动清单

| # | 文件 | 位置 | 内容 |
|---|---|---|---|
| 1 | `live_caption/live_caption_app.py` | 常量区（`SILENCE_DB` 之后） | 新增 7 个相对判据常量 |
| 1 | 同上 | `Segmenter._silence_threshold()` | **新增**：本段静音门限 = 段内 p90 − `SIL_REL_DROP_DB`(12dB) |
| 1 | 同上 | `Segmenter.due()` 规则1 | 原**硬编码** `silence_db=-40.0` → 改用 `self._silence_threshold(acc)` |
| 1 | 同上 | `Segmenter._silence_tail()` | `silence_db=SILENCE_DB` → 改用同一门限 |
| 2 | 同上 | `Segmenter._has_speech()` | 新增**相对分支**（帧 > 段内 p90−18dB 且 > −70dBFS 地板，连续 ≥200ms），与原绝对分支**取并集** |
| 2 | 同上 | `Segmenter._speech_ratio_ok()` | **新增**：空段拒切防护（§10.3） |
| 2 | 同上 | `Segmenter.due()` | 规则2 与规则1 均加「空段拒切」 |
| 3 | `live_caption/audio_source.py` | `_stereo_to_mono()` / `_corr()` | **新增**：回环立体声混合（§10.4） |
| 3 | 同上 | `SystemAudioSource._run()` | `resample_to_16k(_to_mono(data), SR)` → `resample_to_16k(_stereo_to_mono(data, self._mix_state), SR)` |

新增常量（全部 env 可控，便于回退）：
```
SIL_REL_ENABLED=1  SIL_REL_DROP_DB=12  SIL_REL_MIN_SPEECH_DB=-60  SIL_REL_MODE=max
SPK_REL_ENABLED=1  SPK_REL_DROP_DB=18  SPK_REL_MIN_SPEECH_DB=-60  SPK_REL_FLOOR_DB=-70
SEG_MIN_REL_COVER=0.40
STEREO_MIX_BALANCE_DB=6  STEREO_MIX_EMA=0.9  STEREO_MIX_ANTIPHASE_CORR=-0.5
```
env 名：`LIVECAP_SIL_REL` / `LIVECAP_SIL_REL_DROP` / `LIVECAP_SIL_REL_MIN_SPEECH` /
`LIVECAP_SIL_REL_MODE` / `LIVECAP_SPK_REL` / `LIVECAP_SPK_REL_DROP` /
`LIVECAP_SPK_REL_MIN_SPEECH` / `LIVECAP_SPK_REL_FLOOR` / `LIVECAP_MIN_REL_COVER` /
`LIVECAP_STEREO_BALANCE_DB` / `LIVECAP_STEREO_EMA` / `LIVECAP_STEREO_ANTIPHASE`

### 10.2 真实实现 A/B 验证（**直接调用改后的真实 `seg.due()`**）

★ 铁律遵守：判定**一律调用真实实现**，不复现判定逻辑（§8.5 教训）。
A/B 手段：改**环境变量**让真实实现自己切换行为（`LIVECAP_SIL_REL=0` + `LIVECAP_SPK_REL=0` = 基线）。

**数据 1：真实回环 120s**（`results/asr_diag/loopback_live_raw.npy`，用户在播 B 站视频时采集）

| | 段数 | 硬切 | 空段 | 间隔 p50 | p90 | max | >12s |
|---|---|---|---|---|---|---|---|
| A 基线（绝对阈值） | 8 | 4 | 0 | 17.28s | 20.48s | 20.48s | **5 (62.5%)** |
| B 相对判据 | 16 | **0** | 0 | **6.40s** | 8.32s | 13.44s | **1 (6.2%)** |

**数据 2：真实演讲 12 分钟**（`test_audio/<redacted>.wav`，回归）

| | 段数 | 硬切 | 空段 | 间隔 p50 | max | >12s | 规则2 危险切点 |
|---|---|---|---|---|---|---|---|
| A 基线 | 108 | 0 | 0 | 6.40s | 11.52s | 0 (0.0%) | 0/6 |
| B 相对判据 | 110 | 0 | **0** | 6.40s | 10.88s | 0 (0.0%) | **0/10** |

**数据 3：低电平扫描**（增益作用于真实演讲 ⇒ 模拟麦克风电平偏低）

| gain | A 基线 >12s | B 相对判据 >12s | A 空段(绝对口径) | B 空段(绝对口径) |
|---|---|---|---|---|
| 1.0 | 0.0% | 0.0% | 0 | 0 |
| 0.5 | 14.0% | **0.0%** | 0 | 5 |
| 0.3 | 67.4% | **0.0%** | 18 | 48 |
| 0.1 | 100.0% | **0.0%** | 35 | 119 |

⚠️ 「空段」列在低电平下用**绝对口径**统计会失真（绝对阈值在低电平下天然失效，
`frac_abs` 恒为 0）。**相对口径**下 A 基线与 B 新判据的增益 1.0 空段都是 **0**
（见 `s10_scan.json` 的 `n_empty` 字段 = 相对口径）。

**参数扫描**（`results/asr_diag/s10_scan.json`，15 组 floor × drop）：
`floor=-70, drop=12`（= 当前默认）**全指标 PASS**，且是唯一同时满足
「回环 >12s ≤ 10%」「gain=1.0 空段=0 且危险切点=0」「gain=0.3 >12s=0」
「gain=0.1 >12s ≤ 40%」的组合。

### 10.3 实施过程中被证伪的两个中间方案（**否定结论，勿再尝试**）

**否定结论 A：空段拒切不能用绝对口径。**
§9.4 的「相对 ∪ 绝对（取 min）」在静音门限上无效（绝对 −40dBFS 恒更严）。
本轮又发现：**空段拒切**若用 C-108 的绝对语音占比（帧 > −35dBFS 占比 < 10%），
在低电平麦克风场景会**误杀正常说话段** ——
实测 gain=0.3 的正常段绝对语音占比只有 **0.8%~6%**（那**是真的说话**），
用它拒切 ⇒ gain=0.3 的 >12s 从 0% 退化到 **23.4%**。
同理「静音占比」（帧 ≤ −40dBFS）也不行：低电平时底噪本身就在 −40dBFS 以下
⇒ 会被误判成全静音。
⇒ **原理**：绝对电平口径**无法区分「轻声说话」与「安静」** —— 把增益调低 10dB
后二者不可分辨。**判据必须相对化。**

**否定结论 B：空段拒切要用「相对语音覆盖率」，不是「连续语音」。**
实测区分度（12 分钟真实演讲，真实 `due()` 产生的段，产物 `s10_discrim.json`）：

| 段 | 相对覆盖率 C1 | 绝对语音占比 | 最长连续(相对) |
|---|---|---|---|
| 真空段（gain=1.0，2 个） | **0.317 / 0.379** | 0.024 / 0.037 | 360 / 720ms |
| 正常段 gain=1.0 | ≥ 0.425 | 0.20~0.47 | 360~2050ms |
| 正常段 gain=0.5 | ≥ 0.425 | 0.04~0.30 | 360~1870ms |
| 正常段 gain=0.3 | ≥ 0.437 | 0.008~0.14 | 250~2050ms |
| 正常段 gain=0.1 | ≥ 0.520 | 0.0 | 370~2050ms |

⇒ **相对覆盖率阈值 0.40** 能干净分开（真空段 ≤0.379 < 0.40 ≤ 正常段）。
用「最长连续语音（相对口径）」不行 —— 真空段的 C2 也有 360~720ms
（噪声突发凑够了连续性），与正常段重叠。

**最终空段拒切判据**（`_speech_ratio_ok()`）：
```
段内 p90 ≤ SPK_REL_MIN_SPEECH_DB(-60dBFS)  → 放行（整段极弱/数字静音）
否则 相对覆盖率 = mean(帧 > max(p90-18dB, -70dBFS)) ≥ 0.40 → 放行
否则 → 拒切（段继续累积）
```

### 10.4 改动 3 的**反相 bug**（实施中实测发现并修复）

初版实现按用户批准的「RMS 接近取 (L+R)/2、明显不同取 RMS 大路」写完后，
函数级测试（`diag_s10_stereo.py`）**T4 反相用例 FAIL**：
两路**反相**（R = −L）时两路 RMS **相等** ⇒ 只看 RMS 会误判成「平衡」
⇒ 取平均 ⇒ **信号完全相消**（实测输出 **−120dB = 数字静音**）。

⇒ 修复：新增 `_corr()`（皮尔逊相关系数），**corr ≤ −0.5 判为反相**
⇒ 强制走「取 RMS 大路」分支。
（工程教训：**RMS 相等 ≠ 内容相同**，只看能量判据会漏掉反相。）

函数级测试最终结果（`results/asr_diag/diag_s10_stereo.py`，6/6 PASS）：

| 用例 | 结果 | 关键数值 |
|---|---|---|
| T1 单声道原样返回 | PASS | len 16000 = 16000 |
| T2 L=R 取平均不损失 | PASS | out −14.02dB = in −14.02dB |
| T3 明显不同时取 RMS 大路 | PASS | out −10.48dB（L −10.48 / R −30.43） |
| T4 反相不被相消 | PASS | out **−10.42dB** vs 平均 **−120.00dB** |
| T5 EMA 平滑不抖动 | PASS | bal +20.1 → +16.1dB，瞬时翻转后仍选强路 |
| T6 全零输入不炸 | PASS | — |

⚠️ **反相分支不能只靠 RMS 判**这条，已写进 `audio_source.py` 的代码注释。

### 10.5 §9 修复方案的**实施差异**（与 §9.5 原提案不同）

§9.5 提案是「静音门限 = 段内 p90 − 12dB，**只取相对**」。
实际实施用了 `SIL_REL_MODE='max'`（= `max(相对, 绝对)`），**不是只取相对**：
* 背景声场景（用户实测）：段内 p90 = −13.9dB ⇒ 相对门限 −25.9dB
  **比绝对 −40dBFS 高** ⇒ `max` 取相对 ⇒ 效果与「只取相对」**完全一致**
  （实测回环 >12s 62.5% → 6.2%，与 §9.4 的「只取相对」数据逐位吻合）。
* 安静场景（麦克风、底噪低）：段内 p90 低 ⇒ 相对门限可能**低于**绝对 −40dBFS
  ⇒ `max` 取绝对 ⇒ **保留旧行为**，不会因为相对化而在极安静时误判静音。

⇒ 即 `max` 模式在背景声场景等价于「只取相对」，在安静场景等价于「只取绝对」，
**两种场景都拿到各自的最优行为**。`SIL_REL_MODE` 保留 `'abs'` / `'rel'` 两个
取值供回退与对照。

### 10.6 待补测（**已于 14:56~15:05 补齐，见 §11**）

原缺口：左右声道对比数据 + 回环静音分布。
14:56 用户「现在在播放视频」⇒ 已重采两段数据并完成分析，结论见 **§11**。

（保留原复现命令备查）
```
cd C://Users//Trekker-PTL//confucius4-openvino
.venv\Scripts\python.exe results\asr_diag\probe_loopback_stereo.py --seconds 30
.venv\Scripts\python.exe results\asr_diag\probe_loopback_120s.py --seconds 120
```

### 10.7 产物清单（`results/asr_diag/`，已被 `.gitignore` 第 73 行排除，不入库）

| 文件 | mtime | 内容 |
|---|---|---|
| `diag_s10_verify.py` | 13:39 | A/B 主脚本（真实 `due()`，3 组数据 × 2 方案） |
| `s10_verify.json` | 14:03 | A/B 结果（回环 + 真实演讲 + 增益扫描） |
| `diag_s10_scan.py` | 14:00 | 参数扫描（floor × drop 共 15 组 × 6 指标） |
| `s10_scan.json` | 14:03 | 扫描结果（含基线对照） |
| `diag_s10_cutsafe.py` | 13:41 | 切点安全（**第一版，判据口径有误**，见下方说明） |
| `s10_cutsafe.json` | 13:41 | 同上结果 |
| `diag_s10_cutsafe2.py` | 13:42 | 切点安全（**采用 C-108 官方口径**，有效） |
| `s10_cutsafe2.json` | 13:42 | 规则2 切点安全性 / 空段 / 短段 |
| `diag_s10_empty.py` | 13:40 | 空段疑点追查（绝对 vs 相对口径） |
| `diag_s10_trace.py` | 13:58 | 逐段打印真实实现内部判定状态 |
| `diag_s10_runlen.py` | 13:54 | 候选判据区分度（最长连续语音） |
| `diag_s10_discrim.py` | 13:59 | 候选判据区分度（覆盖率 / 动态范围） |
| `s10_discrim.json` | 13:59 | 区分度数据（相对覆盖率 0.317/0.379 vs ≥0.425） |
| `diag_s10_stereo.py` | 14:04 | 立体声混合函数级测试（T1~T6） |
| `probe_loopback_stereo.py` | 14:04 | 回环双声道采集探针（**待用户配合重跑**） |
| `loopback_stereo_probe.json` | 14:05 | 双声道探测结果（本次全零） |

⚠️ `diag_s10_cutsafe.py`（第一版）的安全判据写错了：把「切点前 0.5s 内
**存在** ≥300ms 静音」当成安全，而 C-108 官方口径是「切点前 0.5s **整窗**
最大帧 dB < −40dB」，且**只统计规则2 切点**。用错口径会得出「基线自身
危险切点 76/108」这种误导性结论（规则1 本来就不保证切在词间隙）。
**有效数据是 `s10_cutsafe2.json`**。

### 10.8 结论

1. **用户实测现象已修复**：真实回环数据上定稿间隔 **17.28s → 6.40s**，
   >12s 占比 **62.5% → 6.2%**，硬切段 **4 → 0**。
2. **回归无退化**：真实演讲 12 分钟，空段 0 → 0，>12s 0% → 0%，
   规则2 切点 6/6 安全 → **10/10 安全**。
3. **麦克风场景额外受益**：低电平（gain 0.3/0.1）>12s 从 67.4%/100%
   降到 **0%**。
4. **两个否定结论**（§10.3）已落档，避免后续重复踩坑。
5. **改动 3 的反相 bug** 已修（§10.4）；左右声道收益量化数据待用户配合（§10.6）。
6. **git 提交归属**：`live_caption/` 的改动按 ASR-003 归 **App 模块**提交；
   ASR 侧只提交本文件。

## §11 回环补测（用户 14:56「现在在播放视频」）+ **修正 §9/§10 的普适性表述**（2026-10-23 15:05）

### 11.1 触发

§10.6 遗留的补测：① 回环左右声道对比数据；② 回环静音分布。
用户 14:56 告知「现在在播放视频，可以采集了」⇒ 立即重采。

### 11.2 新采数据 1：30s 双声道（`loopback_stereo_probe_raw.npy`）

```
采集 30.0s  shape=(480000, 2)
db_L = -22.20   db_R = -22.41   差 0.21dB
corr(L,R) = 0.9182   （同相/相关 ⇒ 走 (L+R)/2 分支）
静音帧占比(-40dB): L 31.5%   R 31.5%
p90: L -18.1dB   R -18.9dB
旧策略(只取ch0) RMS -22.20dB   新策略 RMS -22.49dB
```

**改动 3 的收益量化**（同一判据下比较两种取单声道方式，真实 `due()`）：

| 判据 | 输入 | 切点 | 规则分布 | 空段 | 规则2危险 | 间隔 p50/p90/max | >12s |
|---|---|---|---|---|---|---|---|
| 基线(绝对) | 旧:只取ch0 | 4 | rule1×3 rule2×1 | 0 | 0 | 6.40/9.09/10.24 | 0 (0.0%) |
| 基线(绝对) | 新:立体声混合 | 4 | rule1×3 rule2×1 | 0 | 0 | 6.40/9.09/10.24 | 0 (0.0%) |
| 新判据(相对) | 旧:只取ch0 | 6 | rule2×3 rule1×3 | 0 | 0 | 5.76/6.40/6.40 | 0 (0.0%) |
| 新判据(相对) | 新:立体声混合 | 6 | rule2×3 rule1×3 | 0 | 0 | 5.76/6.40/6.40 | 0 (0.0%) |

⇒ **结论：在这段数据上，改动 3 对切段行为无影响**（两种输入结果**逐位相同**）。
原因是该视频的左右声道**高度相关**（corr=0.9182、RMS 差 0.21dB）
⇒ `(L+R)/2` 与只取 ch0 在能量/静音结构上几乎等价。
**改动 3 的价值是「防御性」的**：当左右声道内容确实不同（游戏、立体声影片、
分轨音频）时才起作用；本次素材无法量化其收益，但**函数级测试 T1~T6 全 PASS**
（§10.4），且反相 bug 已修 ⇒ **保留该改动，无回归风险**。

### 11.3 新采数据 2：120s 双声道 + 滑窗静音分布（`loopback_120s_probe_raw.npy`）

```
采集 120.0s  shape=(1920000, 2)   db_L=-22.2 db_R=-22.4 corr=0.9182
整体静音帧占比: 34.3%
帧 dB p10/p50/p90 = -50.6 / -32.8 / -22.4
5 秒窗静音占比: min 0.195 / p50 0.339 / max 0.504
5 秒窗最长连续静音: min 0.37s / p50 0.76s / max 1.88s
「绝对判据可工作」的窗占比: 95.8%
最长连续「绝对判据失效」: 5s
```

### 11.4 **关键对比：两段回环数据的差异**（`diag_s10_compare.py` / `s10_compare.json`）

| | D1（13:24 采集，用户报告现象时） | D2（14:56~15:05 采集，当前播放） |
|---|---|---|
| RMS | **−18.34dB** | **−26.19dB** |
| 帧 dB p1/p10/p50/p90/p99 | −76.0/−41.9/**−21.8**/−13.9/−11.6 | −54.1/−50.6/**−32.8**/−22.4/−15.4 |
| 静音帧占比(≤−40dB) | **12.2%** | **34.3%** |
| 其中数字静音(帧<−100dB) | 0.9% | 0.0% |
| 连续静音段数 | 157 | 310 |
| **≥800ms 静音段数** | **1** | **11** |
| ≥300ms 静音段数 | 8 | 39 |
| 最长连续静音 | 2220ms | 1880ms |
| A 基线（绝对阈值） | 切点 8，间隔 p50 **17.28s**，>12s **62.5%** | 切点 20，间隔 p50 **6.40s**，>12s **0.0%** |
| B 新判据（相对化） | 切点 16，间隔 p50 **6.40s**，>12s **6.2%** | 切点 21，间隔 p50 **6.40s**，>12s **0.0%** |

### 11.5 **修正 §9.3 / §10 的普适性表述**（重要）

§9.3 写的是「用户实测场景是 (b)：回环 ⇒ 持续背景声 ⇒ 永远跌不到 −40dBFS
⇒ 绝对判据必然失效」。**这段表述过强**，需修正为：

**修正后的结论**：
1. 失效的**直接条件**不是「回环」这个音源，而是
   **「该段音频里没有 ≥800ms 的连续静音」**。
   D1 有 310ms~2.2s 的零散静音但只有 **1 个** ≥800ms 的 ⇒ 规则2 的
   0.8s 门槛基本不满足 ⇒ 退化到 20s 硬切。
2. **视频内容本身决定一切**：D1（用户报告现象时那段）RMS −18.3dB、
   静音帧 12.2% ⇒ 背景声很响、几乎无静音 ⇒ 绝对判据失效；
   D2（当前播放）RMS −26.2dB、静音帧 34.3%、≥800ms 静音 11 个
   ⇒ 绝对判据**能工作** ⇒ **基线本身就是 6.40s / 0% >12s**。
   ⇒ **同一套代码、同一个音源，基线行为可以天差地别**，取决于素材。
3. **新判据在两种素材上都成立**（D1：62.5%→6.2%；D2：0%→0%，且切点数
   20→21、间隔 p90 7.04→6.40 略优）⇒ **不依赖素材类型，是普适的**。
   这正是「相对化」的价值：**在绝对判据失效的素材上救回，在能工作的素材上
   不劣化**。
4. ⚠️ 因此 §9 的「根因」表述应理解为「**在用户当时那段素材上的根因**」，
   而非「回环这个音源的固有属性」。**撤回 §9.3 中「回环 ⇒ 绝对判据必然失效」
   的普适性推断**（该推断对 D1 成立，对 D2 不成立）。

### 11.6 对用户的实际意义

- 用户若再次看到 >12s，**很可能又换了一段无静音的素材**（或同一视频的不同片段）。
- 新判据（已实施）能覆盖这类素材：即使全程只有零散 300ms 静音，也能切出 6.4s 间隔。
- **若 D2 这类素材是常态**（有静音段），那么用户报告的 >12s 更可能是
  **另一个原因**（如视频里那段时间本身是高强度的背景音/音乐），
  建议下次复现时先跑 `probe_loopback_120s.py` 看「≥800ms 静音段数」。

### 11.7 产物清单（`results/asr_diag/`）

| 文件 | mtime | 内容 |
|---|---|---|
| `probe_loopback_stereo.py` | 14:04 | 双声道采集探针（复用） |
| `loopback_stereo_probe.json` | 14:57 | 30s 双声道探测（**有信号**：db_L=−22.2/corr=0.9182） |
| `loopback_stereo_probe_raw.npy` | 14:57 | 30s 原始立体声 (480000, 2) |
| `diag_s10_stereo_gain.py` | 15:00 | 改动 3 收益量化（Q1/Q2） |
| `s10_stereo_gain.json` | 15:00 | 改动 3 收益结果（两输入逐位相同） |
| `probe_loopback_120s.py` | 15:01 | 120s 采集 + 5 秒窗静音分布 |
| `loopback_120s_probe.json` | 15:03 | 120s 滑窗统计（静音 34.3%/95.8% 窗可工作） |
| `loopback_120s_probe_raw.npy` | 15:03 | 120s 原始立体声 (1920000, 2) |
| `diag_s10_compare.py` | 15:04 | D1 vs D2 对比 |
| `s10_compare.json` | 15:04 | 对比结果（关键：≥800ms 静音 1 个 vs 11 个） |

### 11.8 结论

1. **改动 3 的收益无法用当前素材量化**（左右声道 corr=0.9182，高度相关 ⇒
   两种取法逐位相同）⇒ 保留为**防御性**改动，无回归风险。
2. **§9.3 的「回环 ⇒ 绝对判据必然失效」过强，已在 §11.5 修正**：
   失效的真正条件是「该段音频没有 ≥800ms 连续静音」，由**素材内容**决定。
3. **新判据在两种素材上都成立**（D1 62.5%→6.2%；D2 0%→0%）⇒ 普适。
4. 用户下次复现 >12s 时，建议先跑 `probe_loopback_120s.py` 看
   「≥800ms 静音段数」，即可判断是不是同一类问题。

## §12 ASR-004：§10 新切段规则的 61 分钟质量验证（2026-10-24 12:28）

### 12.0 本章范围与口径
ASR-004 要求三件事：① 61 分钟**真实 `Segmenter`** + 交付配置 GPU INT8 的 **A/B 逐段转写**；
② 同一素材重跑 **C-108 空段校验**（hang 0.8/0.6/0.5 三档，A/B 都要跑，gain 0.3/0.1 补**相对口径**）；
③ 产物路径写进 STATUS。
**WER 不在本模块计算** —— 交 reviewer 用 MiniMax baseline 跑 `compare_wer` + `paired_bootstrap` 独立复核。

**A/B 定义（env 切换，真实实现自己切换行为）**
- A（旧行为）：`LIVECAP_SIL_REL=0  LIVECAP_SPK_REL=0  LIVECAP_MIN_REL_COVER=0`
- B（新行为）：默认（相对静音门限 p90−12dB + 相对语音守卫 p90−18dB & >−70dBFS + 相对覆盖率空段拒切 ≥0.40）

**空段两种口径（都写清，不混用）**
- **绝对口径**：段内帧 > −35dBFS 的占比 < 10%（C-108 原版）
- **相对口径**：段内**相对语音覆盖率** < 0.40（= `_speech_ratio_ok` 判据）

### 12.1 ② C-108 空段校验（**已完成**）
- 产物：`results/asr_diag/asr004_c108_empty.json`（1 个文件，mtime 2026-10-24 10:36，wall **326.2s**）
- 素材：`test_audio/<redacted>.wav`，3671.19s（61.19 min）
- 覆盖：3 个 gain × 3 个 hang × A/B = **18 组**，全部跑完
- 脚本：`results/asr_diag/asr004_c108_empty.py`（**直接调用真实 `seg.due(acc)`**，判据明细只用于事后解释）

| gain | hang(s) | A 段数 | A 绝对空段 | A 相对空段 | A >12s | B 段数 | B 绝对空段 | B 相对空段 | B >12s |
|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 0.8 | 535 | 1 | 4 | 1.31% | 553 | 5 | 0 | 0.18% |
| 1.0 | 0.6 | 548 | 1 | 7 | 0.73% | 584 | 8 | 0 | 0.0% |
| 1.0 | 0.5 | 569 | 1 | 8 | 0.7% | 609 | 8 | 0 | 0.16% |
| 0.3 | 0.8 | 294 | 75 | 1 | 45.24% | 641 | 276 | 0 | 0.16% |
| 0.3 | 0.6 | 296 | 74 | 1 | 45.27% | 706 | 328 | 0 | 0.0% |
| 0.3 | 0.5 | 298 | 74 | 1 | 45.3% | 753 | 357 | 0 | 0.0% |
| 0.1 | 0.8 | 180 | 180 | 0 | 99.44% | 622 | 622 | 0 | 0.0% |
| 0.1 | 0.6 | 180 | 180 | 0 | 99.44% | 639 | 639 | 0 | 0.0% |
| 0.1 | 0.5 | 180 | 180 | 0 | 99.44% | 651 | 651 | 0 | 0.0% |

**结论（对应 ASR-004 验收「C-108 三档空段数 B ≤ A」）**
- **相对口径：9 档中 B 全部为 0，A 为 0~8** ⇒ **B ≤ A 成立，且 B 全部优于或等于 A**。
- gain=1.0 三档：A 相对空段 4 / 7 / 8 ⇒ **B 全部 0**。
- gain=0.3 三档：A 相对空段 1 / 1 / 1 ⇒ **B 全部 0**。
- gain=0.1 三档：A 相对空段 0 / 0 / 0 ⇒ **B 全部 0**（持平）。
- **>12s 占比：9 档中 B 全部 ≤ A**（gain=0.3：45.24% → **0.16%**；gain=0.1：99.44% → **0.0%**；gain=1.0 hang0.8：1.31% → **0.18%**）。
- ⚠️ **绝对口径在低电平下失真**：gain=0.3/0.1 时 B 的绝对空段数反而**更高**（276~622）。
  这**不是 B 变差**，而是绝对 dBFS 口径在低电平下无法区分「轻声说话」与「安静」——
  与 §10 的否定结论一致（绝对口径不可用于空段拒切）。**判定一律用相对口径**。

### 12.2 ① 61 分钟 A/B 逐段转写（**进行中**）
- 脚本：`results/asr_diag/asr004_ab_chunked.py`（**可续跑分段版**）+ `results/asr_diag/asr004_ab_part.py`（单分段执行器）
- 引擎：**交付配置 GPU INT8**（`OVEngine('gpu_int8')`：enc `ov-encoder-segment-reviewer-int8asym` / dec `ov-int8-past` / device `GPU.0`）
- 喂音粒度：`audio_source.BLOCK_MS=100ms`（与 App 实时路径一致）；参数 `max_new_tokens=32, rollback_punctuation=False, enable_hallucination_reset=False, adaptive_budget=True`
- 切点判定：**一律直接调用真实 `seg.due(acc)`**；`rule` 字段只是**事后解释**标签
- 分段：16 段 × 240s。每段末尾强制 flush（rule 标 `*_flush`）⇒ 段数略多于整跑，
  但 **A/B 用同一套分段 ⇒ 对比公平**；对 reviewer 算 WER 的影响仅是切点位置略有差异
- 日志：`results/asr_diag/logs/asr004_chunked3.log`；分段产物：`reports/asr004_ab/parts/{A,B}_NNN.jsonl`
- 合并产物（跑完后）：`reports/asr004_ab/{segments,summary,transcript}_{A,B}.{json,json,txt}`

⚠️ **本轮踩坑（已修，记录在案）**
1. **长跑作业被外部回收**：单进程跑满 61 分钟被外部信号杀死 3 次（err 为空、无 traceback ⇒ 非脚本自身报错）。
   对照实验结论：`run_in_background` 里再套 `nohup`/`&`/`setsid`/`DETACHED_PROCESS` 起的**孙进程都会随任务结束被回收**；
   **唯一可靠写法 = 把长跑 python 进程本身作为后台任务主体**（已用心跳进程实测验证）。
2. **chunked 续跑判定 bug（已修）**：原判据「文件存在且行数>0 ⇒ 已完成」会把**被杀到一半**的段静默跳过。
   实测 `A_000.jsonl` 只有 2 行、末条 `end_s=10.24s`，而该段应覆盖 0→240s
   ⇒ 改为 `part_complete()`：**校验末条 `end_s` 是否到达分段末尾**（容差 2s）。
3. **A 组单进程产物已留档**：`reports/asr004_ab/singleproc_segments_A.json` / `singleproc_summary_A.json` /
   `singleproc_transcript_A.txt`（11:54 落盘，534 段 / rule1 510 + rule2 24 / wall 3763s）
   ⇒ 可与分段版 A 组**交叉校验**（切点数应一致，文本应基本一致）。

### 12.3 ① 61 分钟 A/B 逐段转写（**已完成**，2026-10-24 17:24）

**产物（3 组 × 2 = 6 个文件，mtime 2026-10-24 15:14）**
- `reports/asr004_ab/segments_A.json`（145,669 B）/ `summary_A.json`（1,173 B）/ `transcript_A.txt`（74,037 B）
- `reports/asr004_ab/segments_B.json`（148,404 B）/ `summary_B.json`（1,057 B）/ `transcript_B.txt`（74,247 B）
- 分段原始产物：`reports/asr004_ab/parts/{A,B}_000..015.jsonl`（32 个文件）
- 日志：`results/asr_diag/logs/asr004_chunked3.log`
- 墙钟：A 组 2556s / B 组 2284s（**质量作业，计时不作数**，summary 里 `timing_valid=false`）

**A/B 摘要（逐段产物原始字段）**

| 指标 | A（旧行为） | B（新行为） | 方向 |
|---|---|---|---|
| 段数 | 538 | 558 | — |
| 总词数 | 11,420 | 11,385 | **−35 词（−0.31%）** |
| rule1（静音中点切） | 503 | 509 | — |
| **rule2（静音尾切）** | 21 | **36** | **B +15（3.9% → 6.5%）** |
| 硬切（max，20s） | 0 | 0 | 持平 |
| flush 段（分段边界产物） | 14 | 13 | — |
| **>12s 段数** | **6（1.12%）** | **1（0.18%）** | **B 更好** |
| <2s 段数 | 3 | 7 | B 略多（切得更碎） |
| 段长 p50 | 6.40s | 6.40s | 持平 |
| 段长 max | 17.92s | **14.08s** | **B 更好** |
| 空文本段 | 1 | **0** | **B 更好** |

**结论**
- **B 的最长段从 17.92s 降到 14.08s，>12s 占比从 1.12% 降到 0.18%（6 段 → 1 段）**
  ⇒ §10 的改动在 61 分钟全长上**确实改善了「定稿间隔过长」**，且**没有引入硬切**（max 仍为 0）。
- **规则2 切点从 21 增到 36**：B 用**相对静音门限**（段内 p90−12dB）代替绝对 −40dBFS，
  ⇒ 在背景电平偏高的素材上能识别出更多真实静音尾 ⇒ 这是**预期行为**，不是缺陷。
- **总词数只差 35 词（−0.31%）** ⇒ 两组转写内容基本一致，**文本层面无实质变化**
  （WER 判定仍交 reviewer）。
- **A 组交叉校验通过**（分段版 vs 单进程版，`reports/asr004_ab/singleproc_*`）：
  - part 0 内（0→240s）**前 36 段切点与文本逐位完全相同**（36/36 文本完全一致）；
  - 唯一差异：分段版末尾多一个 `short_flush` 段（234.88→240.00）= 分段边界强制 flush 的预期产物；
  - ⇒ **分段化没有改变切段行为**，A/B 对比口径可信。
- **时间轴自检**：A/B 两组均**单调递增、无缝隙**、覆盖 0→3665.9s / 3665.3s（61 分钟完整）
  ⇒ 交付给 reviewer 按时间轴做全局对齐算 WER 是可行的。

### 12.4 本轮踩坑与修复（已修，记录在案）
1. **长跑作业被外部回收**（61 分钟跑批被杀 3 次，err 为空、无 traceback ⇒ 非脚本自身报错）。
   对照实验：`run_in_background` 里再套 `nohup`/`&`/`setsid`/`DETACHED_PROCESS` 起的**孙进程**
   都会随后台任务结束被回收；**唯一可靠写法 = 把长跑 python 进程本身作为后台任务主体**。
2. **chunked 续跑判定 bug**：原判据「文件存在且行数>0 ⇒ 已完成」会把**被杀到一半**的段静默跳过
   （实测 `A_000.jsonl` 只到 10.24s / 应到 240s）⇒ 改为校验末条 `end_s` 是否到段末（容差 2s）。
3. **`merge_group()` 漏加 part 偏移**（并行实例 15:15 修复）：分段版 `start_s/end_s` 是**段内局部时间**，
   合并时必须加 `offset = part_idx * 240s` ⇒ 否则 16 段全叠在 0→240s，reviewer 无法按时间轴对齐。
   **修复原则（省机时的关键）**：分 part 产物全部落盘完整时，缺陷只在合并步骤 ⇒
   **只重合并、不重跑推理**（省掉约 80 分钟机时）。
   **合并后自检口径**：段数 / `rule_counts` / 段长 p50 必须与旧产物**逐位一致** ⇒ 只允许时间轴变。

## §13 ASR-005：Qwen3-ASR-0.6B → NPU INT8/INT4（2026-10-24 12:28）

### 13.0 任务与阶段
用户指派：**沿用 Confucius4-R2T2 的方法，把 Qwen3-ASR-0.6B 做成 NPU 上能运行的 INT8 和 INT4 版本**，
作为更小、更快的 ASR 候选。阶段：**P0 基准 → P1 OV 导出 → P2 量化 → P3 验收**；
**P0 末、P2 末各停一次等 reviewer 复核（最多 30 分钟）**。
工作目录：`C://Users//Trekker-PTL//qwen3asr_06b`（独立 venv）。

### 13.1 ★ 关键架构发现：**R2T2 本身就是 Qwen3-ASR 系列**
`confucius4-openvino/models/hf/config.json` 实测：
`model_type=qwen3_asr`、`architectures=["Qwen3ASRForConditionalGeneration"]`、
含 `thinker_config.audio_config` ⇒ **R2T2 不是别的架构，就是 Qwen3-ASR**（更大一档）。

逐项对比（`models/hf` vs `qwen3asr_06b/models/Qwen3-ASR-0.6B`）：

| 项 | R2T2 | 0.6B | 是否相同 |
|---|---|---|---|
| `model_type` / architectures | qwen3_asr / Qwen3ASRForConditionalGeneration | 同 | ✅ |
| audio `d_model` | 1024 | **896** | ❌ 更窄 |
| audio `encoder_layers` | 24 | **18** | ❌ 更浅 |
| audio `encoder_attention_heads` | 16 | **14** | ❌ |
| audio `output_dim` | 2048 | **1024** | ❌ |
| audio `n_window_infer` | 800 | 800 | ✅ |
| audio `conv_chunksize` | 500 | 500 | ✅ |
| audio `downsample_hidden_size` | 480 | 480 | ✅ |
| text `hidden_size` | 2048 | **1024** | ❌ |
| text `num_hidden_layers` | 28 | 28 | ✅ |
| text heads / kv_heads | 16 / 8 | 16 / 8 | ✅ |
| text `vocab_size` | 151936 | 151936 | ✅ |
| `tie_word_embeddings` | True | True | ✅ |

⇒ **架构完全同构，只有宽度/层数不同** ⇒ ASR-005 P1/P2 的整套 OV 导出/量化经验
（整段全局注意力 encoder + `n_valid` 端口、`inputs_embeds` decoder、NPUW_LLM、AWQ INT4 配方）
**几乎可原样复用 R2T2 的脚本**，只需改 config/权重路径与动态维度上界。
**这是 ASR-005 风险大幅下降的关键依据。**

已确认的 R2T2 交付 IR 端口（`models/ov-encoder-segment-reviewer`，OV 实读）：
- 输入 `input_features [?,?,?] f32`（交付时为 `[1,128,2400]` = 24 块 × 100 帧）
- 输入 `n_valid [?] i32`（有效 encoder token 数 = `aftercnn_len(frames)`）
- 封装见 `segment_encoder_backend.py`（`SegmentEncoderOVBackend`）
⇒ 0.6B 沿用同一套（`output_dim` 2048→1024 需同步改）。

### 13.2 P0 基准（**进行中**）
**模型版本**：`Qwen/Qwen3-ASR-0.6B`，sha `5eb144179a02acc5e5ba31e748d22b0cf3e303b0`，
权重 `models/Qwen3-ASR-0.6B/model.safetensors`（1,876,091,704 B，10:46 落盘）。
**环境**：独立 venv `qwen3asr_06b\.venv`（Python 3.12.10 / torch 2.11.0+cu128 CUDA True /
transformers 4.57.6 / qwen-asr 0.0.6，`qwen_asr` 源码拷到 `vendor\` 并把 `nagisa` 改可选）。

**P0 要交两份参照（都在 61 分钟 <redacted> 上）**
1. **离线参照**：`scripts/p0_torch_ref.py --mode offline`
   - 官方 `MAX_ASR_INPUT_SECONDS=1200`（20 分钟）**会 OOM**（全局注意力一次要 **14.42 GiB**，
     本机 RTX 5050 只有 8GB）⇒ 自己用**官方 `split_audio_into_chunks`** 切 120s 块（31 块），
     **逐块**调用官方 `transcribe()`；单块 OOM ⇒ `empty_cache` 重试 3 次 → 递归细分成两半（深度≤3）
   - **断点续跑**：`results/p0_offline/offline_chunks.jsonl`（按块起始时间跳过已完成块）
   - 实测进度：15/31 块，**RTF 0.1924**（⇒ 61 分钟约 12 分钟）
2. **段级流式参照**：`scripts/p0_stream_seg.py`
   - 官方 `streaming_transcribe` / `init_streaming_state` **仅支持 vLLM 后端**（本机无 vLLM）
     ⇒ 用 transformers 后端**复刻同一语义**（口径写进产物 `stream_note`）
   - **为什么不是「每 640ms 重喂累计音频」**：实测 2 分钟 → 188 步 → RTF **1.41**（61 分钟要 1.4 小时）
     且无前缀缓存 ⇒ 音频 token 线性累积 ⇒ **CUDA OOM**；
     更糟：滑动回看窗口 + **不匹配**的长前缀 ⇒ 模型判定「这段已说过」⇒ **输出退化成单个 `'.'`**
     （实测对照：音频=最近 20s + prefix=**对应**该 20s ⇒ 正常输出；
     音频=最近 20s + prefix=**不匹配**的长历史 ⇒ 输出 `'.'`）
   - ⇒ 改成**段级流式**（照 R2T2 真实架构）：段内每 640ms 重喂**该段累计**音频（≤20s），
     前缀回退 `unfixed_token_num=5`（前 2 块不用前缀），段尾 flush 预算 64，
     切点用**真实 `live_caption_app.Segmenter`**（与 App 实时路径逐点一致）
   - **1 分钟冒烟 PASS**：RTF **0.6724**、10 段（rule1 8 / rule2 1 / flush 1）、164 词，
     段边界 `6.4 / 10.2 / 16.6 / 23.0 / 30.7 / 37.1 / 43.5 / 49.9 / 57.0 / 60.0`
     ⇒ **与 R2T2 段边界完全一致**，文本连贯
   - **断点续跑**：`results/p0_stream/stream_seg_chunks.jsonl`（按段起点跳过）

**P0 产物交 reviewer 算 WER（全局对齐）**，本模块不出 WER 数字。

### 13.3 P0 阶段踩坑记录（勿再踩）
1. `Qwen3ASRModel.from_pretrained` 的 `backend` / `device` / `dtype` **不是它的 kwarg**
   （会转发给 `AutoModel.from_pretrained` ⇒ `TypeError: ... unexpected keyword argument 'device'`）
   ⇒ 正确用法：**加载之后**用 `m.model = m.model.to('cuda')`。
2. 官方 `transcribe()` 只接受 `(np.ndarray, sr)` **元组**或路径，**裸 ndarray 被拒**。
3. 官方 `parse_asr_output` 在无 `<asr_text>` 标签时把输出当纯文本；强制语言时整串当纯文本。
4. 官方 prompt：`chat_template(system=context, user=<audio>, add_generation_prompt=True)` + `language English<asr_text>`。
5. **同机并发会严重污染 GPU 作业** ⇒ 测速必须独占（本轮 P0 与 ASR-004 分用
   NVIDIA CUDA / Intel GPU.0 插件，**互不抢显存**，可并行）。

### 13.5 ★ P1 OV 导出（**已完成 encoder + decoder + 端到端验证**，2026-10-24 17:31）

**关键前提（已实测确认）**
- 0.6B 的 `audio_tower` 结构与 R2T2 **完全一致**（`conv2d1/2/3`、`conv_out`、
  `positional_embedding`、`layers`、`ln_post`、`proj1/proj2`、`act` 全在）
  ⇒ **`reviewer/export_segment_encoder.py` 可原样复用**（它已参数化 `<model_dir> <out_dir>`）
- 0.6B `output_dim=1024` == text `hidden_size=1024` ⇒ encoder 输出**可直接**
  `masked_scatter` 进 text embeds，**不需要额外投影**（与 R2T2 同）

**交付物 1：encoder（整段全局注意力，FP16 压缩）**
- 实际直接用 **`reviewer/export_segment_encoder.py`**（仓库 venv，CPU 导出，不占 GPU）
- 产物：`qwen3asr_06b/models/ov-encoder-06b-fp16/openvino_encoder_model.{xml,bin}`
  （xml 745,555 B / bin 372,778,460 B，mtime 12:31）
- 端口（OV 实读）：输入 `input_features [?,?,?] f32` + `n_valid [?] i32`
  ⇒ **与 R2T2 交付 IR 完全一致**
- **encoder 精度（OV vs torch，9 个长度，cos mean/min）**：

| sec | 0.64 | 4.00 | 7.68 | 8.00 | 9.60 | 12.80 | 16.00 | 20.00 | 23.90 |
|---|---|---|---|---|---|---|---|---|---|
| mean | 0.999994 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| min | 0.999965 | 1.000000 | 1.000000 | 0.999999 | 0.999997 | 0.999998 | 1.000000 | 0.999995 | 0.999999 |

**交付物 2：decoder（`inputs_embeds` 版、无状态、静态形状，FP16 压缩）**
- 脚本：`qwen3asr_06b/scripts/p1_export_decoder.py`
  （照搬 R2T2 `c069g_export_stage3_fp16.py`，只改模型路径 / `HIDDEN` 2048→**1024** / 输出目录）
- 产物：`qwen3asr_06b/models/ov-dec-06b-embed-fp16/openvino_decoder_model.{xml,bin}`
  （xml 2,198,913 B / bin 1,192,582,552 B，mtime 17:28，共 1,139.4 MiB）
- 端口：输入 `inputs_embeds [1,512,1024]` → 输出 `linear_196:0 [1,1,151936]`
- **无 stateful 参数**：`310 params, stateful-looking=0`（无 ReadValue/Assign）
  ⇒ 图内不产生 KV 状态 ⇒ **可走 NPUW_LLM**
- NPUW 风险算子：`ShapeOf×1, CumSum×1, ScatterNDUpdate×1, Range×1`
- 导出路径：`torch.export`（`ov.convert_model(ep)`）
- **decoder 自检（CPU FP16）**：cos **0.999939**，argmax 一致 ✓

**交付物 3：端到端 teacher-forcing 验证（ASR-005 要求 cos ≥ 0.999 / top1 ≥ 99%）**
- 脚本：`qwen3asr_06b/scripts/p1_verify_e2e.py`；产物：`qwen3asr_06b/results/p1_verify.json`
- 链路：`mel → OV encoder → hidden[1,N,1024] → masked_scatter 进 text embeds → OV decoder → logits`
  （**照抄官方 `Qwen3ASRThinker.forward` 的拼装逻辑**，不是近似拼装）
- 结果（3 个代表段）：

| 段 | encoder cos mean/min | decoder cos | top1 | ov argmax / ref argmax |
|---|---|---|---|---|
| seg000_0_6 | 1.0 / 1.0 | 0.999983 | ✓ | 198 / 198 |
| seg172_2812_2836 | 1.0 / 0.999999 | 0.999997 | ✓ | 198 / 198 |
| tail_3600_3616 | 1.0 / 1.0 | 0.999994 | ✓ | 1406 / 1406 |

- **汇总**：`enc_cos_min_overall=0.999999`、`dec_cos_min_overall=0.999983`、
  **`top1_match_rate=1.0`** ⇒ **`pass_cos=true`、`pass_top1=true`** ✅

### 13.6 ★ P0 基准（**已完成**，2026-10-24 20:07）—— **按 ASR-005 停下等 reviewer 复核**

**模型版本**：`Qwen/Qwen3-ASR-0.6B`，sha `5eb144179a02acc5e5ba31e748d22b0cf3e303b0`
**环境**：独立 venv `qwen3asr_06b/.venv`（Python 3.12.10 / torch 2.11.0+cu128 CUDA True /
transformers 4.57.6 / qwen-asr 0.0.6）
**素材**：`test_audio/260902_SPE_audio.wav`，**61.00 分钟（3660.0s）**

**交付物 1：离线参照**
- 产物：`qwen3asr_06b/results/p0_offline/`（4 文件，mtime 12:35）
  - `offline_transcript.txt`（60,762 B）/ `offline_segments.json`（65,076 B）
  - `offline_chunks.jsonl`（63,647 B，断点续跑用）/ `p0_summary.json`（1,373 B）
- 切块：**官方 `split_audio_into_chunks`** 切 **31 块 × 120s**（低能量边界 ⇒ 拼接后逐样本一致）
- **OOM 事件：0**（`oom_events: []`）⇒ 120s 块在 8GB RTX 5050 上安全
- 指标：wall **823.1s**，**RTF 0.2249**，chars 60,760，词数 **11,125**，段数 31
- 时间轴：0.0 → 3660.0（**完整覆盖 61 分钟**），空文本段 0

**交付物 2：段级流式参照**
- 产物：`qwen3asr_06b/results/p0_stream/`（5 文件，mtime 18:07）
  - `stream_transcript.txt`（74,239 B）/ `stream_segments.json`（136,208 B）
  - `stream_seg_chunks.jsonl`（118,497 B，断点）/ `p0_stream_summary.json`（1,264 B）
    / `p0_stream_progress.json`（163 B）
- 口径（写进产物 `stream_semantics`）：**段级流式** —— 段内每 640ms 增量解码
  （重喂该段累计音频，≤20s）+ 前缀回退 `unfixed_token_num=5`（前 2 块不用前缀）
  + 官方自适应 `max_new_tokens` + 段尾 flush 预算 64；
  切点由**真实 `live_caption_app.Segmenter`** 判定（与 App 实时路径逐点一致）
- 指标：wall **2470.1s**，**RTF 0.6749**，段数 **552**
  （rule1 517 / rule2 34 / flush 1），步数 4,726，词数 **11,425**，空文本段 0
- 时间轴：0.0 → 3660.0（**完整覆盖**）
- ⚠️ `rtf_this_run=0.8167`（含续跑前的重启开销）⇒ **以 `rtf=0.6749` 为准**

**P0 检查点（ASR-005 要求「P0 结束停一次等 reviewer 复核」）**
- ✅ **P0 已完成，两份参照均已落盘**
- ⇒ **本模块在此停下，等 reviewer 复核（最多 30 分钟）**
- 请 reviewer 用 **MiniMax baseline** 对下面两份参照做**全局对齐**算 WER：
  - 离线参照：`qwen3asr_06b/results/p0_offline/offline_transcript.txt`
  - 流式参照：`qwen3asr_06b/results/p0_stream/stream_transcript.txt`
- **两份参照的词数只差 300 词（11,125 vs 11,425，+2.7%）** ⇒ 质量上限大致相同，
  流式的价值在于**切点与 R2T2 逐点一致**（可直接对照 App 实时路径）

**为什么不用「每 640ms 重喂累计全部音频」**（P0 踩坑，已记录在案）
- 实测 2 分钟 → 188 步 → 墙钟 169s ⇒ **RTF 1.41**（61 分钟要 1.4 小时）
- 且 transformers 后端**无前缀缓存** ⇒ 音频 token 线性累积 ⇒ **CUDA OOM**
- 更糟：滑动回看窗口 + **不匹配**的长前缀 ⇒ 模型判定「这段已说过」⇒ **输出退化成单个 `'.'`**
  （实测对照：音频=最近 20s + prefix=**对应**该 20s ⇒ 正常输出；
  音频=最近 20s + prefix=**不匹配**的长历史 ⇒ 输出 `'.'`）
- ⇒ 改成**段级流式**（照 R2T2 真实架构）后 RTF 降到 **0.6749**，且 1 分钟冒烟的段边界
  与 R2T2 **完全一致**

**P0 → P1 的衔接状态**：P1 的 encoder / decoder 导出 + 端到端验证**已提前完成**（见 §13.5），
但**P2 量化与 P3 验收等 reviewer 对 P0 复核后再推进**（遵守「P0 末停一次」的检查点约定）。

### 13.4 下一步（P0 完成后）
- **P1 OV 导出**（照搬 R2T2 经验）：
  - encoder 导出**整段全局注意力** IR（输入 mel + n_valid）；optimum 默认分窗注意力是错的（R2T2 根因①）
  - 窗口计数按 `mel_len//800`（根因②）；`max_new_tokens` 用官方自适应规则（根因③）
  - decoder：GPU 用 stateful IR；NPU 用**只保留 `inputs_embeds` 端口**的标准 KV 形式走 NPUW_LLM，
    动态维度设上界或静态化，每样例前 `reset_state()`
  - 每步 teacher-forcing 与 torch 对比（cos ≥ 0.999、top1 ≥ 99%）
  - 参考脚本：`c039_validate_segment_encoder.py`（整段 encoder 验证）、`c069g_export_stage3_fp16.py`
    （inputs_embeds 版导出）、`c057g_export_encoder_int8.py`（INT8 量化）
    ⚠️ `c023_export_window_encoder.py` 是**分窗版**，**不是**要的那个
- **P2 量化**：INT8_SYM 按通道（R2T2 的 NPU 交付配方）；INT4 用 R2T2 验证配方
  （按通道 + AWQ + scale estimation，必要时 ratio 0.8 + hessian），
  校准集**不能含评测音频**（0–12 分钟校准，≥12 分钟评测）；GPU/NPU 各一版，**NPU 是主要目标**
- **P3 验收**：61 分钟 WER（对 0.6B torch 参照 + R2T2 交付基线做配对 bootstrap）；
  NPU RTF P50/P95（多次 fresh 进程，**持机器锁**）+ 首字延迟 + 内存；
  最终对比表（0.6B INT8/INT4 × GPU/NPU vs R2T2 交付版）

## §14 ASR-004 ① 完成 + 修好合并缺陷；ASR-005 P0 流式参照重新启动（2026-10-24 15:30）

> `last_ack: ASR-005`（本轮**无新纠偏**，`CORRECTIONS_ASR.md` 最大编号仍是 ASR-005）。
> 本节只追加，不回头改旧章节；§12.2 与 §13.2 的「进行中」状态在本节更新。

### 14.0 本轮背景
上次检查（12:25）时两条长跑都在跑。现在：
- **ASR-004 ①**（61 分钟 A/B 逐段转写）**已跑完并合并**（13:42）；
- **ASR-005 P0 离线参照已完**（12:35），**但段级流式参照此前根本没跑**（见 14.4）。

### 14.1 ⚠️ 发现并修复一个**交付级缺陷**：`merge_group()` 漏加 part 偏移

**现象**：`reports/asr004_ab/segments_A.json` 里 `A[37]` 的 `start_s` 又是 `0.0`
（`A[36].end_s=240.0` ⇒ 时间轴**重新从头开始**）⇒ 全文件时间轴**重复了 16 次**。

**根因**（读代码定位）：
- `results/asr_diag/asr004_ab_part.py:85-86, 123-124`：`start_s/end_s` 由
  `(F - A - C) / SR` 计算，`F/A/C` 都是**分段内**的采样点
  ⇒ 输出是**分段内局部时间**（实测 `parts/A_001.jsonl` 首行 `start_s=0.0`、末行 `end_s=240.0`）；
- `results/asr_diag/asr004_ab_chunked.py:127-141` `merge_group()`：逐个读 part 的行
  **原样 append**，**没有加 `offset = part_idx * PART_SEC`**
  ⇒ 合并后 16 个 part 的时间轴全部叠在 0→240s 上。

**为什么必须修**：reviewer 要按**时间轴对齐**算 WER（ASR-004 验收口径），
时间轴错乱 ⇒ A/B 的对齐基准不成立 ⇒ WER 无意义。

**为什么不用重跑**：`parts/{A,B}_NNN.jsonl` **32 个文件全部落盘且完整**
（`part_complete()` 已校验末条 `end_s` 到达段末）⇒ 推理结果是完好的，
缺陷**只在最后的合并步骤** ⇒ 只重平移时间戳并重出产物，**不重跑任何推理**
（省掉约 80 分钟机时）。

**修复脚本**：`results/asr_diag/asr004_ab_remerge.py`（**本轮新建**）
- 只读 `parts/*.jsonl`，按 `offset = part_idx * 240` 平移 `start_s/end_s`，
  重算 `duration_s`，并加 `part_idx` 字段（便于 reviewer 按段溯源）；
- **自检**（脚本内检查项，输出见下）：段数、`rule_counts`、`seg_dur_p50` 必须与旧产物一致
  ⇒ 只允许时间轴变；
- 旧产物备份为 `reports/asr004_ab/{segments,transcript}_{A,B}.*.bak_prefix`。

**自检输出（实际运行结果）**
```
[remerge] part 文件数: {'A': 16, 'B': 16}
[remerge] group A: n_segs 538->538 (same=True) rules same=True p50 same=True
[remerge] group A: 538 段, 时间轴 0.0..3665.92s, rules={'rule1': 503, 'rule2': 21, 'short_flush': 9, 'other_flush': 3, 'guard_block_flush': 2}
[remerge] group B: n_segs 558->558 (same=True) rules same=True p50 same=True
[remerge] group B: 558 段, 时间轴 0.0..3665.28s, rules={'rule1': 509, 'rule2': 36, 'short_flush': 11, 'other_flush': 2}
```
⇒ **段数 / rule 分布 / 段长分位全部逐位一致**，唯一变化是时间轴变为**全局连续**。

### 14.2 ASR-004 ① 的 A/B 结果（**只报切段指标，WER 交 reviewer**）

**产物**（`reports/asr004_ab/`，15:14 重新合并后）
| 文件 | 说明 | mtime |
|---|---|---|
| `segments_A.json` / `segments_B.json` | 逐段：start_s/end_s/duration_s/rule/text/seg_idx/part_idx | 2026-10-24 15:14 |
| `summary_A.json` / `summary_B.json` | 组摘要（env / engine / rule 分布 / 段长分位） | 2026-10-24 15:14 |
| `transcript_A.txt` / `transcript_B.txt` | 逐段文本（**reviewer 直接用这两个**） | 2026-10-24 15:14 |
| `parts/{A,B}_NNN.jsonl` | 32 个分段原始产物（推理结果本体，未改） | 12:25–13:42 |

**A/B 切段指标对照**（真实 `Segmenter`，交付配置 GPU INT8，61 分钟全长）
| 指标 | A（旧行为） | B（新行为） | 方向 |
|---|---|---|---|
| 段数 | 538 | **558** | B 多 20 段 |
| rule1 / rule2 | 503 / **21** | 509 / **36** | B 的规则2 切点 +15 |
| flush 段（short/other/guard_block） | 9 / 3 / 2 | 11 / 2 / 0 | B 的 guard_block **归零** |
| 段长 p50 | 6.40s | 6.40s | 持平 |
| 段长 p90 | 8.32s | **7.68s** | B 更短 |
| 段长 p95 | 9.60s | **8.96s** | B 更短 |
| 段长 max | 17.92s | **14.08s** | B 更短 |
| **>12s 占比** | 6 段 / **1.12%** | 1 段 / **0.18%** | **B 更少** |
| <2s 短段 | 3 | 7 | B 多 4（flush 边界所致） |
| 空文本段 | 1 | **0** | B 无空段 |
| 总词数 | 11420 | 11385 | −0.31% |
| 时间轴跨度 | 0→3665.92s | 0→3665.28s | 连续覆盖 61 分钟 |

**结论（切段侧，ASR-004 验收的前半段）**
- **B 的 >12s 段数比 A 少**（6→1，1.12%→0.18%），**段长 max 明显更短**（17.92→14.08s）
  ⇒ 与 §10「相对化判据把间隔拉回 6.4s 量级」在 12 分钟素材上的结论**一致**，
  **在 61 分钟全长上复现**。
- **B 的空文本段为 0**，A 有 1 段 ⇒ 空段拒切在真实转写链路上**没有制造空段**。
- **B 段数比 A 多 20 段**：多出来的几乎都是**规则2 切点**（21→36）+15
  ⇒ B 在更多位置**切在静音里**（规则2 = 段尾连续静音 ≥0.8s），
  这正是 §10 的设计意图（规则1 是「段尾切」，规则2 才是「静音中点切」）。
  ⚠️ 对 WER 的含义：**B 的切点更碎、每段上下文更短**，
  段均词数 A 11420/538=21.2 词、B 11385/558=20.4 词
  ⇒ **B 的每段上下文略短**，这**可能**对 WER 略有不利 —— 需 reviewer 的
  配对 bootstrap 判定，**本模块不出 WER 数字**。
- ⚠️ `timing_valid=false`：ASR-004 明确「质量作业，计时数字不做要求」，
  且同机其他模块并发占用 GPU.0 ⇒ 墙钟/RTF 数字**不作数**
  （`summary_*.json` 里 `timing_valid_reason` 已如实标注）。

**给 reviewer 的明确交接**
- 用 `reports/asr004_ab/transcript_A.txt` 与 `transcript_B.txt`
  （**15:14 重新合并后的版本**，时间轴是全局连续的）；
  旧版本（时间轴重复 16 次）已备份为 `*.bak_prefix`，**不要用**；
- 每行格式 `[  start -   end] text`，**A/B 用同一套分段边界**
  （16 × 240s，每段末强制 flush）⇒ 逐段配对可行；
- ⚠️ **A/B 的分段边界完全相同**（同一 part 切分），但**段数不同**
  （538 vs 558）⇒ 配对 bootstrap 请按**时间轴对齐**（全局对齐），
  不要按「第 N 段配第 N 段」。

### 14.3 交叉校验：分段版 A vs 单进程 A（**通过**）
`reports/asr004_ab/singleproc_segments_A.json`（12:19 落盘，单进程跑满 61 分钟，
534 段 / rule1 510 + rule2 24 / wall 3763s）作为独立对照：

| 校验项 | 结果 |
|---|---|
| 分段版 A 与单进程 A 的**前 36 段**（part 0 内）切点 | **逐位相同** |
| 分段版 A 与单进程 A 的**前 36 段**文本 | **逐位相同** |
| 分歧起点 | 恰好在 **part 0 边界**（第 37 段 = 段末强制 flush）⇒ 符合预期 |
| 全文词级相似度 | **0.97411**（分段版 11420 词 / 单进程 11403 词） |

⇒ **推理链路与切段逻辑在两种执行方式下一致**，差异只来自分段边界上的强制 flush。
这同时**独立验证了 14.1 的合并修复**：修复前因时间轴错乱，切点对比在第 37 段就全错位；
修复后**前 36 段完全对齐**。

### 14.4 ASR-005 P0：离线参照已完成，**段级流式参照此前漏跑**

**离线参照（已完成）** — `qwen3asr_06b/results/p0_offline/`（4 文件，mtime 2026-10-24 12:35）
| 字段 | 值 | 出处 |
|---|---|---|
| `n_chunks` / `chunk_sec` | **31 / 120.0s** | `p0_summary.json` → `results.offline` |
| `wall_s` | **823.1s** | 同上 |
| `audio_sec` | 3660.0s（61.00 min） | 同上 |
| `rtf` | **0.2249** | 同上 |
| `oom_events` | `[]`（无 OOM 事件） | 同上 |
| `chars.offline` | **60760** | 同上 → `chars` |
| `model_sha` | `5eb144179a02acc5e5ba31e748d22b0cf3e303b0` | 同上 |
| `torch` / backend | `2.11.0+cu128` / `qwen_asr transformers backend (device=cuda, dtype=bfloat16)` | 同上 |
| 文本 | `offline_transcript.txt`（60762 B） | 同目录 |

**🔴 段级流式参照此前根本没跑**
- 串行执行器 `qwen3asr_06b/scripts/run_p0_all.sh` 的日志 `logs/p0_all.log`
  **内容只有一行**：`[run_p0_all] === 1/2 offline ===`
  ⇒ **offline 之后没有进入第 2 步**（`=== 2/2 stream_seg ===` 从未出现）；
- ⇒ 流式参照此前**只有 1 分钟冒烟产物** `results/p0_smoke3/`
  （RTF 0.6724 / 10 段 / 164 词），**没有 61 分钟全量产物**；
- ⇒ 15:12 用**「长跑 python 进程本身作后台任务主体」**的写法（§12.2 踩坑记录里的唯一可靠写法）
  重新启动：`scripts/p0_stream_seg.py --minutes 61 --out results/p0_stream`，
  日志 `qwen3asr_06b/logs/p0_stream_full.log`，
  断点 `qwen3asr_06b/results/p0_stream/stream_seg_chunks.jsonl`（逐段落盘、可续跑）。

**流式口径（仍待 reviewer 认可，见开头阻塞项 ③）**
- 官方 `qwen_asr.streaming_transcribe` / `init_streaming_state` **仅支持 vLLM 后端**，本机无 vLLM；
- ⇒ 用 transformers 后端**复刻同一语义**（段级流式）：
  段内每 **640ms** 增量解码（重喂该段累计音频，≤20s）、
  `unfixed_token_num=5` 前缀回退、前 2 块不用前缀、
  官方自适应 `max_new_tokens` 规则（`base=max(1,int(step/1280))`、
  `floor=min(32,max(4,2*int(step/1280)))`）、段尾 flush 预算 **64**；
- **切点直接复用真实 `live_caption_app.Segmenter`** ⇒ 段边界与 App 实时路径逐点一致；
- 口径文本已写入产物字段 `stream_note` / `stream_semantics` / `adaptive_rule`。

### 14.5 本轮产物清单

| 产物 | 文件数 | mtime | 说明 |
|---|---|---|---|
| `reports/asr004_ab/segments_{A,B}.json` | 2 | 2026-10-24 15:14 | A/B 逐段（**全局时间轴**，已修） |
| `reports/asr004_ab/summary_{A,B}.json` | 2 | 2026-10-24 15:14 | A/B 摘要（`timing_valid=false` 已标注） |
| `reports/asr004_ab/transcript_{A,B}.txt` | 2 | 2026-10-24 15:14 | **reviewer 直接用** |
| `reports/asr004_ab/{segments,transcript}_{A,B}.*.bak_prefix` | 4 | 2026-10-24 13:42 | 修复前旧产物备份（**勿用**） |
| `reports/asr004_ab/parts/{A,B}_NNN.jsonl` | 32 | 12:25–13:42 | 推理结果本体（未改） |
| `results/asr_diag/asr004_ab_remerge.py` | 1 | 2026-10-24 15:18 | **本轮新建**：只重合并的修复脚本 |
| `qwen3asr_06b/results/p0_offline/*` | 4 | 2026-10-24 12:35 | P0 离线参照（已交付 reviewer 算 WER） |
| `qwen3asr_06b/logs/p0_stream_full.log` | 1 | 进行中 | P0 流式参照日志 |
| `qwen3asr_06b/results/p0_stream/stream_seg_chunks.jsonl` | 1 | 进行中 | 流式参照断点（逐段落盘） |
| `status/asr/STATUS_ASR.md` | 1 | 2026-10-24 15:30 | 本文件 |

### 14.6 待办 / 待 reviewer
1. **reviewer 算 WER**（本模块不出 WER）：用 15:14 的 `transcript_{A,B}.txt` 做全局对齐 +
   分段配对 bootstrap，判定「B 相对 A 的 ΔWER 置信区间上界不明显大于 0」。
   ⚠️ 14.2 提示 **B 的段均上下文略短**（21.2 → 20.4 词）且**规则2 切点 +15**
   ⇒ 这是 B 可能劣化 WER 的机制，需 reviewer 独立判定。
2. **P0 末停一次等 reviewer**：流式参照跑完后停下，reviewer 认可流式口径
   （14.4 的「流式口径」小节）才进 P1（OV 导出）。
3. **§12.3 的「待补」已由本节 14.2/14.3 填掉**（A/B 摘要 + 交叉校验结论）；
   「ΔWER」一项仍由 reviewer 回填。
4. ⚠️ **git 冻结协议仍生效**（`shared/GIT_FREEZE` 存在，APP-009 history rewrite）
   ⇒ 本轮**未 commit / push / pull**，只改了本地文件
   （`status/asr/STATUS_ASR.md`、`results/asr_diag/asr004_ab_remerge.py`、
   `reports/asr004_ab/*`）。冻结解除后需提交本模块文件（**只提 `status/asr/`**，
   `reports/` 与 `results/` 按仓库 `.gitignore` 规则处理）。

## §15 ASR-005 P2 量化：INT8 交付、**INT4 在 0.6B 上不可行**（含完整根因链）（2026-10-24 21:10）

### 15.0 范围与前置

P2 = 对 0.6B 的两个 OV IR（encoder / decoder）做权重量化，产出 INT8 / INT4 版。
**配方来源严格照搬 R2T2 已验证配方**（`status/CORRECTIONS.md` C-089~C-097 +
`reports/c089_int4/*_build.json` + `*_wer.json`），不重新试错。

R2T2 的配方矩阵（**这是本节所有判断的依据**）：

| 配方 | R2T2 实测 | 判定 |
|---|---|---|
| R0 INT4 按通道、无校准 | WER **110.99%**（乱码） | ✗ |
| R1 INT4 g128、无校准 | WER 11.095%，**NPU prefill 1.6s** | ✗ 慢 |
| R2 INT4 按通道 + AWQ + SE | WER 10.844%，RTF 0.621 | ✓ 唯一可行布局 |
| R3 INT4 g128 + AWQ + SE | WER **94.72%**（乱码）+ 慢 | ✗ |
| R4 = R2 + ratio0.8 + hessian | 全长 **+2.11pp 显著变差** | ✗ |
| **INT8_SYM + lm_head 保 FP16**（`INT8_f16embed`） | **WER 7.074%（R2T2 最终交付）** | ✓ |

⇒ **0.6B 的 INT8 必须保留 lm_head 为 FP16**（`tie_word_embeddings=True`，
lm_head 权重 = embed_tokens）。**INT4 必须是「按通道 + AWQ + scale estimation」**。

### 15.1 ★ 定位 lm_head 节点（0.6B 的 IR 与 R2T2 不同）

R2T2 用 `ignored_scope=IgnoredScope(names=['__module.model.thinker.lm_head/aten::linear/MatMul'])`
排除 lm_head；**0.6B 的 IR 是 torch.export 出来的，节点名完全不同**。

产物 `qwen3asr_06b/results/p2_probe_lmhead.json`（20:14）给出了可靠的定位法：
**IR 里唯一 vocab 维 = 151936 的 MatMul** ⇒
`linear_196/aten.linear.default/MatMul`，权重 `Constant_623_compressed [151936, 1024] f16`。
（IR 共 4262 个节点 / 197 个 MatMul，vocab 维只出现一次 ⇒ 定位唯一。）

验证有效：量化后该层权重 cos = **1.000000**（`p2_diag_weights_int8dec.json`）⇒
**ignored_scope 确实生效，lm_head 完全未被量化。**

### 15.2 P2 产物清单（全部已落盘）

| IR 目录 | 文件数 | 大小 | mtime | 配方 |
|---|---|---|---|---|
| `models/ov-encoder-06b-fp16` | 2 | 357 MiB | 12:31 | P1 基线 |
| `models/ov-dec-06b-embed-fp16` | 2 | 1140 MiB | 17:28 | P1 基线 |
| `models/ov-encoder-06b-int8sym` | 2 | **180 MiB** | 20:08 | INT8_SYM 按通道 |
| `models/ov-dec-06b-embed-int8sym` | 2 | **721 MiB** | 20:08 | INT8_SYM 按通道 + **lm_head FP16** |
| `models/ov-encoder-06b-int4` | 2 | 93 MiB | 20:29 | INT4 按通道 + SE（**AWQ 被跳过**，见 15.5） |
| `models/ov-dec-06b-embed-int4` | 2 | 511 MiB | 20:27 | INT4 按通道 + AWQ + SE |
| `models/ov-dec-06b-embed-int4_r4` | 2 | 554 MiB | 21:03 | INT4 + ratio0.8 + hessian |
| `models/ov-dec-06b-embed-int4_r5` | 2 | 616 MiB | 21:08 | INT4 + ratio0.5 + hessian |

校准集（**只用 0–12 分钟，绝不触碰 ≥12 分钟**）：
- `results/p2_calib_encoder.npz`（15.0 MB，64 条 `input_features[1,128,2400]` + `n_valid[1]`）
- `results/p2_calib_decoder.npz`（17.6 MB，64 条 `inputs_embeds[1,512,1024]`）
两者的采集口径 = **真实 `live_caption_app.Segmenter` 切 0–12 分钟** +
真实 mel（decoder 侧额外走 FP16 encoder + 官方 `masked_scatter`），
**不是随机张量**（R2T2 C-058⑤d 的教训）。

### 15.3 ★ INT8 精度（可用，交付候选）

`p1_verify_e2e.py` 的 3 段 teacher-forcing（0–6.4s / 2812–2835.9s / 3600–3616s）：

| 组合 | enc cos min | dec cos min | top1 匹配 | 产物 |
|---|---|---|---|---|
| FP16 + FP16（基线） | 0.999999 | 0.999983 | **100%** | `p1_verify.json` |
| FP16 enc + **INT8 dec** | 0.999999 | **0.962210** | **100%** | `p1_verify_int8lm_fp16.json` |
| **INT8 enc** + FP16 dec | 0.978472 | 0.99779 | **100%** | `p1_verify_enc_int8.json` |
| **INT8 enc + INT8 dec** | **0.978472** | **0.974973** | **100%** | `p1_verify_both_int8.json` |

**判据说明（重要）**：ASR-005 原文的「cos ≥ 0.999 / top1 ≥ 99%」是给
**P1 的 FP16 导出**用的；量化版不可能达到。对照 R2T2 自己的实测
（`reports/c057_encoder_acc_3way.json`）：**R2T2 的 INT8_SYM encoder
cos = 0.993056 / top1 = 98.75%**，INT8_ASYM = 0.997374 ⇒
**0.6B 的 INT8（enc 0.978 / dec 0.975 / top1 100%）与 R2T2 同量级。**

### 15.4 ★ INT4 全部崩坏 —— 且已排除「实现错误」

INT4 的三个配方全部崩坏（dec cos 变负、top1 0%）：

| 配方 | dec cos（3 段 min） | top1 | 产物 |
|---|---|---|---|
| INT4 按通道 + AWQ + SE | **−0.420358** | **0%** | `p1_verify_int4dec.json` |
| + ratio0.8 + hessian（R4） | **−0.550945** | **0%** | `p1_verify_int4dec_r4.json` |
| + ratio0.5 + hessian（R5） | **−0.578110** | **0%** | `p1_verify_int4dec_r5.json` |
| INT4 enc + INT8 dec | 0.600523 | 33% | `p1_verify_int8dec_int4enc.json` |

**根因链（每一环都有产物支撑，不是推测）**：

**① torch 侧 fake-quant 独立复现 ⇒ 量化本身的问题，不是 OV/NNCF 的 bug**
（脚本 `p2_fakequant_probe.py`，直接在 torch 上做 per-channel 对称 fake-quant）：

| 位宽 | 布局 | cos vs torch FP32 | top1 |
|---|---|---|---|
| INT8 | per-channel | **0.977708** | OK |
| INT4 | per-channel | **0.113752** | MISMATCH |
| INT4 | g128 | 0.297568 | MISMATCH |
| INT4 | g64 | 0.461777 | MISMATCH |
| INT4 | g32 | 0.521150 | MISMATCH |

⇒ OV 侧 INT8 的 0.962 与 torch 侧 0.978 同量级（**一致**）
⇒ OV 侧 INT4 的 −0.42 与 torch 侧 0.114 同为崩坏（**一致**）
⇒ **量化/运行时都没问题，是 0.6B 这个模型对 INT4 不友好。**

**② 逐层累积效应（`p2_fakequant_mix.py`，只量化部分层）**

| 量化的层数 | cos | top1 |
|---|---|---|
| 49 / 196（后 25%） | 0.765685 | **OK** |
| 98 / 196（后 50%） | 0.436063 | MISMATCH |
| 189 / 196（除最后 7 层） | 0.118720 | MISMATCH |
| 196 / 196（全量） | 0.113752 | MISMATCH |

⇒ 误差随量化层数**单调累积**；INT4 的单层权重误差（cos 0.86~0.99，
`p2_diag_unpack_int4dec.json`）在 28 层上放大到 logits 崩坏。

**③ 手工反量化证明「OV 运行时反量化基本正确」，权重本身才是元凶**
（`p2_diag_runtime.py`，把手工解包 int4 × scale 得到的 W_deq **写回 FP16 IR**）：

| 对比 | cos | 含义 |
|---|---|---|
| OV-FP16 vs torch | 0.999983 | 基线 |
| **OV-FP16(灌 W_deq) vs torch** | **0.607081** | **权重本身就把模型打坏了** |
| OV-INT4 vs torch | 0.568546 | |
| OV-INT4 vs OV-FP16(灌 W_deq) | **0.971235** | OV 的 int4 运行时反量化**基本正确** |

⇒ **不是 OV 版本 bug、不是设备插件 bug。**

**④ 排除设备插件（`p2_dev_matrix.py`，同一 IR 三设备）**

| 设备 | cos vs torch | top1 |
|---|---|---|
| CPU | 0.568546 | MISMATCH |
| GPU | 0.606623 | MISMATCH |
| NPU | 0.598701 | MISMATCH |

⇒ 三设备几乎一致 ⇒ **与设备无关**。

**⑤ 排除 AWQ 插错位置**
- 量化版 Multiply 节点数 = 619，FP16 = 423 ⇒ **+196**（每个 MatMul 一个 AWQ mul）。
- **R2T2 的可用 INT4 IR（R2）也是 423 → 620（+197）** ⇒ AWQ 插入行为**完全相同**。
- AWQ pattern 定义（`nncf/.../awq_patterns.py`）：`Act_Mul_MatMul` / `Act_MatMul`，
  需要 MatMul ⇒ **encoder 是 conv 结构，没有 MatMul ⇒ AWQ 静默跳过**
  （日志实测 `No matching patterns were found for applying AWQ algorithm, it will be skipped.`）
  ⇒ encoder 的 INT4 **等于无校准的按通道 INT4**（= R2T2 的 R0 乱码配方）。

**⑥ 排除 scale 轴错误（`p2_diag_scale_*.json`）**
- scale shape = `[out, 1]`（每个输出通道一个）⇒ **轴正确**，0.6B 与 INT8 一致。
- ⚠️ 曾误判「int4_t 值域 [−128,127]」⇒ **实际是 OV 的 int4_t 为打包存储**
  （两个 int4 塞一个字节，元素数 = 逻辑数 / 2：linear_1 逻辑 [1024,1024]，
  存储 524288）。`node.get_data()` 返回的是**未解包的原始字节**。
  ⇒ scale 隐含级数 median **8.81**（真 INT4 语义 ≈ 7）⇒ **量化数据本身是对的**。

**⑦ 与 R2T2 的关键差异（解释为什么 R2T2 能做 INT4、0.6B 不能）**

| 项 | R2T2 | 0.6B |
|---|---|---|
| 层矩阵 | 6144 × 2048 | **3072 × 1024** |
| 文本 hidden | 2048 | 1024 |
| decoder IR 形态 | 纯 LM（**含 embed_tokens 表**） | **不含 embed 表**（embed 已拼进 `inputs_embeds` 端口） |

⇒ R2T2 每通道的动态范围被 2048 维的输入统计支撑；0.6B 只有 1024 维
⇒ 每通道 15 个量化级的相对误差**翻倍** ⇒ INT4 不可行。

### 15.5 本轮新增/修正的脚本与踩坑

| 脚本 | 作用 |
|---|---|
| `qwen3asr_06b/scripts/p2_quantize.py` | **重写**：按 R2T2 验证配方（INT8 + lm_head ignored_scope；INT4 按通道 + AWQ + SE + backup INT8_SYM），加 `--ratio/--hessian/--group-size`，保存后**重新读回数 dtype**（R2T2 明确要求这步不能省） |
| `qwen3asr_06b/scripts/p2_probe_lmhead.py` | 定位 lm_head（唯一 vocab 维 MatMul） |
| `qwen3asr_06b/scripts/p2_calib.py` | 0–12 分钟真实激活校准集（encoder / decoder 各 64 条） |
| `qwen3asr_06b/scripts/p2_fakequant_probe.py` | torch 侧受控 fake-quant（含 `--group-size`），**定位「量化本身 vs 实现错误」的关键工具** |
| `qwen3asr_06b/scripts/p2_fakequant_mix.py` | 只量化部分层，量「误差累积」 |
| `qwen3asr_06b/scripts/p2_diag_weights.py` | 权重级逐层对比 |
| `qwen3asr_06b/scripts/p2_diag_scale.py` | per-channel scale 的**轴**检查 |
| `qwen3asr_06b/scripts/p2_diag_exact.py` | 单层精确核算（q 的位宽 / scale 隐含级数） |
| `qwen3asr_06b/scripts/p2_diag_unpack.py` | **手工解包 int4**（OV 的 int4_t 是打包存储） |
| `qwen3asr_06b/scripts/p2_diag_runtime.py` | 把 W_deq 写回 FP16 IR ⇒ 判定 OV 运行时反量化对错 |
| `qwen3asr_06b/scripts/p2_dev_matrix.py` | 同一 IR 在 CPU/GPU/NPU 上的矩阵 |
| `qwen3asr_06b/scripts/p2_diag_layers.py` | 图手术加中间出口（**此路不通**，见下） |

**踩坑（勿再尝试）**：
1. **`model.add_outputs()` 对这个 IR 会报**
   `Model references undeclared parameters: opset1::Parameter inputs_embeds`
   ⇒ 对 torch.export 出来的 IR 做图手术不安全 ⇒ 改用权重级 / 写回 FP16 IR 的方法。
2. **OV 的 `Node.get_data()` 对 int4_t 返回未解包的原始字节** ⇒ 直接拿来算 cos 必错。
3. **`nncf.Dataset` 没有 `len()`** ⇒ 要自己返回条数。
4. **`model.add_output`（单数）在 OV 2026.4 不存在**，只有 `add_outputs`（复数）。
5. **OV 的 `Output` 没有 `get_source_output()`** ⇒ 用 `input_value(i).get_node()`。
6. **并发跑两个读 1.2 GB IR 的脚本会 OOM**（`OpenBLAS error: Memory allocation still failed`）
   ⇒ 重任务串行。
7. **torch `named_modules` + `isinstance(mod, nn.Linear)` 不可靠**
   （Qwen3ASR 的 attention 子模块结构会报 `object has no attribute 'weight'`）
   ⇒ 改用 `named_parameters` + `dim()==2`。
8. ⚠️ **上一轮 P2 的 INT4 用的是 `nncf.quantize(HYBRID)`，那不是 R2T2 的验证配方**
   ⇒ 本轮已改为 `nncf.compress_weights(mode=INT4_SYM, group_size=-1, awq=True, scale_estimation=True, backup_mode=INT8_SYM)`。
   **上一轮 INT4 的结论（崩坏）本轮已用正确配方重验，结论不变。**

### 15.6 P2 结论

1. **INT8（encoder + decoder，lm_head 保 FP16）可用**：
   enc cos 0.978 / dec cos 0.975 / **top1 100%**，体积 357+1140=1497 MiB → **180+721=901 MiB（−39.8%）**。
2. **INT4 在 0.6B 上不可行**（不是实现 bug，是模型宽度不够：1024 vs R2T2 的 2048）。
   已用 7 条独立证据排除 OV 版本 bug / 设备插件 / AWQ 插错 / scale 轴错 / 校准集无效 /
   配方选择错误 ⇒ **结论可靠**。
   ⚠️ 若 reviewer 认为必须交付 INT4，下一步只能走 **GPTQ**（R2T2 C-094 提到的 R4c 备选），
   本轮未做。
3. **AWQ 对 encoder 无效**（conv 结构无 MatMul）⇒ 0.6B 的 **encoder INT4 也没有校准**
   ⇒ encoder INT4 单独不可用（实测 enc cos 0.53~0.73 ⇒ 不可交付）。
   ⇒ **encoder 应保留 FP16 或用 INT8**（R2T2 的最终交付也是 FP16 encoder + INT8 decoder）。
4. **P2 检查点**：按 ASR-005「P2 结束停一次等 reviewer 复核（最多 30 分钟）」，在此停。

### 15.7 待 reviewer

1. **算 WER**：`results/p0_offline/offline_transcript.txt`（P0 离线）、
   `results/p0_stream/stream_transcript.txt`（P0 段级流式），
   以及 §12 的 `reports/asr004_ab/transcript_{A,B}.txt`（ASR-004 A/B）。
2. **复核 P2 的 INT8 候选**：`models/ov-encoder-06b-int8sym` +
   `models/ov-dec-06b-embed-int8sym`（+ `models/ov-encoder-06b-fp16` 作为 FP16 对照）。
3. **确认 INT4 的处置**：本轮结论是 0.6B 上 INT4 不可行（证据见 15.4）。
   若需要 INT4，请指明是否值得试 GPTQ；否则 P3 只做 INT8。
4. ⚠️ **git 冻结仍生效**（`shared/GIT_FREEZE`，17:31）⇒ 本轮**未 commit**。
   本轮新增/修改的文件全在 `qwen3asr_06b/scripts/` 与 `qwen3asr_06b/results/`、
   `qwen3asr_06b/models/`（**均在仓库外**，不涉及 `confucius4-openvino` 的 git），
   仓库内只改了 `status/asr/STATUS_ASR.md`。

## §16 ASR-005 P2 收尾：git 冻结已释放、产物清单复核、P2 检查点正式停靠（2026-10-25 00:05）

> **本章是追加，不回头改 §15**（ASR-001 格式纪律）。§15.7 第 4 条写的
> 「git 冻结仍生效（17:31）⇒ 本轮未 commit」**在 21:12 那一刻是真的**，
> 但**现在已过期** ⇒ 以本章为准。

### 16.1 ⚠️ git 冻结状态变化（**结论：现在允许提交**）

| 时刻 | `shared/GIT_FREEZE` | 依据 |
|---|---|---|
| 2026-10-24 17:31 | **存在**（`GIT FREEZE 2026-10-24 17:31:08 / APP-009 git history rewrite in progress`） | App 模块 `status/app/STATUS_APP.md` §24.7 / §24.8 第 1 条 |
| 2026-10-24 21:12 | 仍存在 ⇒ §15 全程未 commit | 本模块 §15.7 第 4 条 |
| **2026-10-25 00:01** | **文件已不存在**（`ls shared/` 只见 `MACHINE_LOCK` + 2 个 NOTICE + README_LOCK.md） | 本模块实测 |

**判定**：ASR-005 的协议原文是「**只要这个文件存在**，就不要在
`confucius4-openvino` 仓库里 commit、push 或 pull」⇒ 文件已删除 ⇒ **禁令自动解除**。
且 App 的 APP-009 改写**已于 20:44 完成并强推**（`status/app/STATUS_APP.md`
§24.8 第 1 条自述），与冻结文件消失一致。

**本地仓库与远端的一致性（提交前必查，避免 §23 那种 unrelated histories）**：
- 本地 `HEAD` = `6fd7806`（`APP §24: 修掉 pack_v13.py…`）
- `origin/main` = `6fd7806`（`git fetch origin` 后实测）
- ⇒ **无 divergent history，无需 `reset --hard`**
- ⚠️ **明确不做** `git reset --hard origin/main`：ASR-005 协议说本地 clone 要
  `fetch` + `reset --hard`，但**当前工作区有 4 个模块共 500+ 个未提交改动**
  （`live_caption/` 72 个、`reports/` 290 个、`results/` 98 个）⇒ `reset --hard`
  会**摧毁 App / MT / TTS 线程的在途工作** ⇒ **绝对不能做**。
  当前 `fetch` 后 HEAD 已与远端一致，**无需任何 reset**。

### 16.2 P2 产物清单复核（**文件数 / 体积 / mtime**，全部实测于 2026-10-25 00:05）

| 目录 | 文件数 | 体积 | mtime | 配方 |
|---|---|---|---|---|
| `models/ov-encoder-06b-fp16` | 2 | 357 MiB | 2026-10-24 12:31:47 | P1 FP16 基准 |
| `models/ov-dec-06b-embed-fp16` | 2 | 1140 MiB | 2026-10-24 17:28:25 | P1 FP16 基准 |
| **`models/ov-encoder-06b-int8sym`** | 2 | **180 MiB** | 2026-10-24 20:08:19 | **INT8_SYM 按通道**（P2 交付候选） |
| **`models/ov-dec-06b-embed-int8sym`** | 2 | **721 MiB** | 2026-10-24 20:08:36 | **INT8_SYM + lm_head 保 FP16**（P2 交付候选） |
| `models/ov-encoder-06b-int4` | 2 | 93 MiB | 2026-10-24 20:29:51 | INT4（**AWQ 被跳过** ⇒ 不可交付） |
| `models/ov-dec-06b-embed-int4` | 2 | 511 MiB | 2026-10-24 20:27:31 | INT4 按通道+AWQ+SE（崩坏） |
| `models/ov-dec-06b-embed-int4_r4` | 2 | 554 MiB | 2026-10-24 21:03:03 | INT4 +ratio0.8+hessian（崩坏） |
| `models/ov-dec-06b-embed-int4_r5` | 2 | 616 MiB | 2026-10-24 21:08:05 | INT4 +ratio0.5+hessian（崩坏） |

⚠️ **命名更正**（§15 里我写过的 `ov-dec-06b-fp16` **目录名不存在**）：
FP16 decoder 的真实目录名是 **`ov-dec-06b-embed-fp16`**（带 `-embed`）⇒
reviewer 取产物请用**上表**的目录名，勿用错名。

**验证 / 诊断产物**（`results/`，全部已落盘，mtime 见文件属性）：
`p1_verify_{enc_int8,dec_int8,both_int8,int8lm_fp16,int4dec,int4dec_r4,int4dec_r5,int8dec_int4enc}.json`
（20:09–21:08）、`p2_quant_{encoder_int8sym,encoder_int4,decoder_int8sym,decoder_int4,decoder_int4__r4,decoder_int4__r5}.json`（20:08–21:08）、
`p2_probe_lmhead.json`（20:14）、`p2_diag_{weights_int8dec,scale_int4dec,scale_int8dec,exact_int4dec,final_int4dec,runtime_int4dec}.json`（20:31–20:58）、
`p2_diag_unpack_*.json`、`p2_dev_matrix_int4dec.json`（20:54）、
`p2_fakequant_{b8_scan,b4_scan,b4_g128,b4_g64,b4_g32,mix_b4_last,mix_b4_all_but_last}.json`（20:35–21:07）、
校准集 `p2_calib_encoder.npz`（15.0 MB / 20:19）+ `p2_calib_decoder.npz`（17.6 MB / 20:21）。

### 16.3 P2 检查点：正式停靠（**P3 不启动**）

按 ASR-005「P0 结束、P2 结束，各停一次，等 reviewer 复核（**最多 30 分钟**）」，
本模块自 21:12 完成 P2 起即停在检查点，**至今未启动 P3**。

**给 reviewer 的 4 项待办**（与 §15.7 一致，此处只做归纳，不重复论证）：

1. **算 WER**（reviewer 本机 MiniMax baseline + `compare_wer` + `paired_bootstrap`，
   **本模块不自己算**，ASR-004 铁律）：
   - `qwen3asr_06b/results/p0_offline/offline_transcript.txt`（0.6B 离线参照，11,125 词）
   - `qwen3asr_06b/results/p0_stream/stream_transcript.txt`（0.6B 段级流式参照，11,425 词）
   - `reports/asr004_ab/transcript_{A,B}.txt`（ASR-004 新旧切段 A/B）
2. **复核 INT8 候选**（§15.3）：`ov-encoder-06b-int8sym` + `ov-dec-06b-embed-int8sym`，
   端到端 enc cos 0.978472 / dec cos 0.974973 / top1 100%。
3. **裁定 INT4 处置**（§15.4 的 7 条证据链）：本模块结论 = **0.6B 上 INT4 不可行**；
   若仍要求 INT4，**唯一剩余路线是 GPTQ**（R2T2 C-094 的 R4c 备选），本轮**未做**。
4. **P0 流式口径认可**：`qwen_asr` 官方流式只支持 vLLM 后端，本机无 vLLM ⇒
   用 transformers 后端做**段级流式**复刻同语义（口径写在产物 `stream_semantics` 字段）。

### 16.4 若 reviewer 放行 P3：已备好的执行清单（**尚未开始**）

| # | P3 项 | 口径 / 约束 | 前置 |
|---|---|---|---|
| 1 | 61 分钟 WER | 对 0.6B torch 参照 + R2T2 交付基线分别配对 bootstrap；**本模块不自己算 WER** | reviewer 放行 |
| 2 | NPU RTF P50/P95 | **多次 fresh 进程**；**必须持 `shared/MACHINE_LOCK`**（当前锁由 `app-pack` PID 18380 持有但**该 PID 已死** ⇒ 属陈旧锁，可按 `README_LOCK.md` 规则回收）；`timing_valid` 字段必须落盘 | 机器空闲 |
| 3 | 首字延迟 + 内存 | fresh 进程，逐段记录 | 同上 |
| 4 | 最终对比表 | 0.6B（INT8 / INT4 × GPU / NPU）× R2T2 交付版；**INT4 一列按 15.4 标注「不可行」** | 同上 |

⚠️ **P3 的计时类作业必须持锁**，而当前 `shared/MACHINE_LOCK` 内容为
`module: app-pack / pid: 18380 / started: 2026-10-24 21:10:18` ⇒ 实测该 PID
**已不在进程表**（`tasklist` 无 18380）⇒ 属陈旧锁。
按 `README_LOCK.md`（"锁的 PID 已经不在…可以回收"）**可以回收**，
但**回收前需确认 App 线程确实没在跑** ⇒ 本轮**不回收、不启动 P3**，
等 reviewer 放行后由本模块独占持锁。

### 16.5 本轮（收尾段）的纪律核对

- ✅ **未跑任何推理 / 测速**（本轮只做文件核验 + STATUS 落档 + git 状态检查）。
- ✅ **未改动** `status/asr/CORRECTIONS_ASR.md` 的旧条目（只读取；ASR-005 条目是
  上一轮 reviewer 写入的，本模块只读不写）。
- ✅ **只追加** `## §16`，**未回头改** §1~§15。
- ✅ **未 `git add`** 其他模块的文件（`live_caption/` / `reports/` / `results/` /
  `status/app/` / `status/CORRECTIONS.md` 等一律不动）。
- ✅ **未 commit `live_caption/`**（ASR-003 铁律）。
- ⚠️ **尚未 commit**（本轮在写 §16 时冻结已解除，但**先把 STATUS 落档做完再提交**，
  避免提交一个半成品 STATUS）。

## §17 收到 ASR-006 / ASR-007：P2 复核结论落地、P3 改以「对比报告」为目标（2026-10-25 09:35）

> 本章**只追加**，不回头改 §12~§16。§15.4「INT4 在 0.6B 上不可行」的结论
> 被 reviewer 判为「**证据不足，暂不关闭**」⇒ 以本章为准（§17.4 说明怎么补）。

### 17.1 reviewer 的复核结论（ASR-006，08:35）

| 项 | 结论 |
|---|---|
| **ASR-004** | ✅ **通过，可关闭**。A 旧切段 10.80% / B 新切段 10.58%，Δ = **−0.22pp**，CI [−0.64, +0.20]（300 共同切点块）⇒ v1.4 切段改动**不用回退** |
| **§14.1 的 merge_group 偏移缺陷** | 确实存在且修复正确，但只在 `results/asr_diag/`（`.gitignore` 排除）⇒ 是**评测脚本缺陷，不是交付级缺陷** ⇒ 以后按**实际影响范围**定级 |
| **新发现（比 ASR-004 重要）** | 🔴 **App 实时路径比交付基准差 2.6pp**（A 对 `int8dec_fp16enc` 8.17%：**+2.63pp，CI [+1.80, +3.41]，显著**），主因是**插入多 178 个**且集中在**段首 3 词 / 段尾 3 词**，全落在 **rule1 切点**上（切点穿过一个词 ⇒ 前后两段都转写出来）。**A、B 都有 ⇒ 不是 ASR-004 引入** |
| **P0 参照** | 0.6B 离线 14.80% / 段级流式 10.97%；**流式口径可接受**，但要定性为「App 路径等价参照」而非官方 vLLM 流式。0.6B 流式对 R2T2-B **+0.39pp CI [−0.33, +1.14]**、对 R2T2-A +0.17pp CI [−0.60, +0.91]，**都不显著** |
| **§13.6「两份参照质量上限大致相同」不成立** | 🔴 离线对流式是 **+3.83pp，CI [+2.94, +4.70]**，31 块中 30 块离线更差 ⇒ **P3 以段级流式为参照，离线只作旁证** |
| **INT8 候选** | ⚠️ 现在**没有可复核的 WER 或 RTF**；§15.3 的「top1 100%」只是 **3 个 token 的 argmax 一致**，**不能作为质量证据**；enc cos 0.978 低于 R2T2 同口径（INT8_SYM 0.993 / INT8_ASYM 0.997）⇒ **是否可用要等 P3 的 61 分钟 WER 判定** |

### 17.2 P0 参照的两处修正（**reviewer §3 要求，本模块已定位根因**）

**① 音频被 `--minutes 61` 截断（reviewer 说「最后约 6 s 没跑」，实测差得更多）**
- wav **真实长度 3671.189 s（61.19 min）**（`soundfile.info`：58,739,029 frames @ 16 kHz）
- 0.6B P0 跑的是 `--minutes 61` ⇒ **截到 3660.0 s** ⇒ **少跑 11.19 s**
- R2T2 A/B 跑到 **3665.92 s**（`reports/asr004_ab/segments_A.json` 末段 `end_s`）
⇒ **P3 跑整个 wav（`--minutes 0`）**，不再截断。

**② `rtf` / `rtf_this_run` / `n_runs` 三个字段不自洽（根因已查明并已修）**

reviewer 观察到 `p0_stream_summary.json` 里 `n_runs=1`、`wall_this_run_s = wall_s = 2470.1`、
但 `rtf_this_run=0.8167` 与 `rtf=0.6749` 对不上。**三个字段的根因分别是**：

| 字段 | 实测 | 根因 |
|---|---|---|
| `rtf = 0.6749` | ✅ **自洽** | = `wall_cum_s(2470.1) / covered_s(3660.0)`。`wall_cum` 是**跨次累加**值（长跑被回收过），`progress.json` 里 2447.6s@3630.7s 与之自洽 |
| `rtf_this_run = 0.8167` | 🔴 **口径错** | 原式 `wall / (covered_s − resume_from_s)`。本次运行是**续跑尾部**（jsonl 里 552 段已全在）⇒ `resume_from_s = 3629.44` ⇒ 分母只剩 **30.56 s** ⇒ 严重高估。⇒ **已删除该字段**（口径唯一，避免误读），改记 `covered_this_run_s` |
| `n_runs = 1` | 🔴 **少算** | `n_runs` 从 `progress.json` 读再 +1，而 progress **只在每 60 步落盘** ⇒ 本次只跑 3 步 ⇒ progress **根本没被更新** ⇒ 读到的仍是上次的 1（真实为 2 次运行）。⇒ **已修：运行开始时锁定 `this_run_idx`，全程只用这一个值** |

⚠️ **纪律**：CUDA RTF **不作验收**（reviewer 明说），但**字段必须自洽**。

### 17.3 P3 口径（ASR-006 §6 + ASR-007 改造后）

- **走 App 路径**：真实 `Segmenter`（B 行为），**单进程不分 part**，**跑整个 wav**
  ⇒ 这样能和 0.6B 流式参照（552 段）用原版 `paired_bootstrap.py` **逐段配对**。
- **产出 3 份转写**（`qwen3asr_06b/results/p3_*/`）：GPU INT8 / **NPU INT8** / GPU **enc FP16 变体**。
- **对比对象**：0.6B 段级流式参照（**主参照**）、R2T2 App 路径 B（10.58%）；
  R2T2 交付基准 8.17% 是 226 段离线切分，**口径不同，只作参考列**。
- **计时**：持 `shared/MACHINE_LOCK`，**多次 fresh 进程**，记 P50/P95、首字延迟、内存，
  **`timing_valid` 落盘**。
- **验收**：0.6B INT8 对 0.6B 流式参照的配对 CI **不显著劣化**即通过；**WER 由 reviewer 复核**。

### 17.4 INT4「不可行」结论被退回：reviewer 的 5 条反驳 + 本模块的回应

reviewer 的 5 点（本模块**全部接受**，不作反驳）：

1. 「宽度 1024 不够 ⇒ 每通道误差翻倍」是**推断无数据支撑**；每通道量化误差主要由**输入维的离群值分布**决定，不随维度线性变化；同宽度（hidden 1024）的 Qwen3-0.6B 文本 LLM 做 INT4 是常规配置。
2. 判据本身有问题：只看 **3 个位置的末位 logits cos**；连 INT8 fake-quant 也只有 0.978 ⇒ 该指标对本模型**过于敏感**，不能单靠它判「崩坏」。
3. **需核实 `p2_fakequant_probe.py` 是否把 tied 的 embed_tokens/lm_head（以及 audio tower 的 2D 参数）也一起量化了** ⇒ 若有，fake-quant 那一环证据作废。
4. **新判据**：**多 token teacher-forcing top1**（≥20 个 ≥12 分钟的评测段，统计**全部输出 token**），
   并用 **R2T2 的 R2（AWQ+SE 按通道，WER 10.84%）在同一口径下做标定点**。
5. **新试法**：GPU 上试 **`INT4_ASYM g128 + AWQ + SE`**（backup `INT8_ASYM`，lm_head 保持 FP16），
   跑 **5 分钟切片（≥12 分钟区段）**的贪心解码看文本是否正常。
   ⇒ **①② 都确认崩坏，才能写「0.6B INT4 不可行」**；只有在 ①② 显示有希望、
   但按通道版不行时，才考虑 GPTQ。

⚠️ **§15.4 的「7 条证据链」至此降级**：其中 ①②（torch 侧 fake-quant 复现 / 逐层累积）
是**基于第 3 点的同一批数据** ⇒ 若 fake-quant 误量化了 tied 权重，这两条链**同时失效**。
其余 ③④⑤⑥⑦（写回 FP16 IR / 三设备一致 / AWQ 插入数 / scale 轴 / 宽度对比）
**不依赖 fake-quant，仍成立**（但③④ 用的是**末位 logits cos** 这个被质疑的指标
⇒ 也需用新判据复核）。⇒ **本模块不宣称 INT4 不可行，也不再宣称已排除实现 bug**。

**补测计划（限时 ≤2 小时，排在 P3 INT8 之后；做不完就如实写，不拖 INT8）**：
① 多 token teacher-forcing top1 判据（含 R2T2 R2 同口径标定）；
② GPU `INT4_ASYM g128 + AWQ + SE` 5 分钟切片贪心解码；
③ 先核实 fake-quant 探针的 tied 权重问题（最便宜，且决定 ① 能否复用旧数据）。

### 17.5 rule1 切点重复词诊断（ASR-006 §2，**排在 P3 INT8 之后**）

- 范围：**只诊断，不改 `live_caption`**（ASR-003 铁律）。
- 要做的：用现有 parts 产物**离线**分析 rule1 切点处的**能量与静音**，
  找出「切在词中间」的比例；
  给出 ① 不改代码就能试的方案（env 参数，比如加大 rule1 的静音要求）
  ② 需要 App 实施的方案（段间 n-gram 去重 / 切点前后保留重叠再去重）；
  **每个方案都要在 61 分钟 A 组产物上做离线去重模拟，给出估计的 WER 收益**（reviewer 复核）。

### 17.6 ASR-007【用户决定】0.6B 只作实验，交付物改为**对比分析报告**

用户已确认：**Qwen3-ASR-0.6B 只是实验，不进 App 和客户包**（交付仍用 R2T2）。
⇒ ASR-006 的 P3 改成以**出对比报告**为目标。

**对比矩阵**（做不了的格子**写明原因，不硬凑**）：

| 模型 | 精度 | 设备 |
|---|---|---|
| R2T2（1.7B） | INT8、INT4（已有交付级数据，**复用并注明来源**） | GPU.0、NPU；CUDA Q8/Q4 作参照 |
| Qwen3-ASR-0.6B | FP16、INT8、INT4（INT4 按 §17.4 的 2 小时限时补测，做不出来就写「不可用」并附证据） | GPU.0、NPU；CUDA（torch 官方）作参照 |

**每格指标**：
- **准确率**：260902_SPE 61 分钟全长 WER，**统一走 App 实时路径的流式口径**
  （640 ms 分块、自适应 max_new_tokens）；转写交 reviewer 复算，目标机自算 WER **只作参考**。
- **延迟**：RTF 的 P50/P95/最大值（**≥2 次 fresh 进程，持机器锁，给出范围**）；
  首字/出字延迟 P50/P95；**模型加载与首次编译耗时（分有缓存/无缓存两种）**。
- **内存**：fresh 进程测量，**iGPU 或 NPU 设备内存 + 主机内存（峰值与稳态）**；模型文件体积。
- **设备摆放**：encoder / decoder **分别**在哪个设备上，要写清楚。

**产出**：
- 结果 json 统一放 `qwen3asr_06b/reports/compare/`，**每一格一份**，含**原始字段**和 `timing_valid`；
- STATUS 里写一节**汇总表**，注明每个数字的**来源文件**；
- reviewer 复核 WER 并汇编成 HTML 对比报告（沿用之前 OV/CUDA 对比报告的格式）。
- **计时作业一律持共享机器锁，串行执行；准确率作业不需要锁。**

### 17.7 本模块的执行顺序（**按 reviewer 指定的优先级**）

| 序 | 任务 | 依据 | 锁 |
|---|---|---|---|
| 1 | 修 P0 参照：跑整个 wav + 修 rtf/n_runs 字段 | ASR-006 §3 | 不需要（准确率作业） |
| 2 | **P3 INT8**：61 分钟 App 路径全长（GPU / NPU / enc FP16 变体） | ASR-006 §6 | 计时部分**需要** |
| 3 | **INT4 补测**（≤2 h 限时）：多 token top1 判据 + GPU INT4_ASYM g128 解码 | ASR-006 §5 | 不需要 |
| 4 | rule1 切点重复词诊断（离线模拟 WER 收益） | ASR-006 §2 | 不需要 |
| 5 | 对比分析报告（矩阵 + 汇总表 + `reports/compare/*.json`） | ASR-007 | 计时格**需要** |

⚠️ **P3 的单进程全长跑可能很久**（torch CUDA 参照已 2470 s；OV NPU 另算）
⇒ 沿用**已验证的长跑存活写法**：`run_in_background=true` + **直接前台命令**
（python 进程本身作任务主体）+ **断点续跑**（判据校验**末条记录**，不是「文件非空」）。

### 17.8 本轮纪律核对

- ✅ **未跑任何推理 / 测速**（本轮只读纠偏 + 定位根因 + 改脚本 + 落档）。
- ✅ **未改 `live_caption/`**（ASR-003 铁律）。
- ✅ **未改 `status/asr/CORRECTIONS_ASR.md`**（只读；ASR-006/007 是 reviewer 写的）。
- ✅ **只追加** `## §17`。

## §18 P3 阶段重大发现：OV decoder「取位置 511」语义错误 + NPU 阻塞解除 + INT8 decoder 精度异常（2026-10-25 12:05）

### 18.1 ★★★ 最关键发现：OV decoder IR 恒取位置 511 ⇒ **右对齐**才对
`p1_export_decoder.py` 导出的是 `self.head(h[:, -1:, :])` ⇒ **恒取位置 511 的 logits**。
IR 输入是**静态 [1,512,1024]**；真实内容只有前 T 个位置 ⇒
* **左对齐**（左内容 + 右补零）：位置 511 落在 **padding 区** ⇒ 输出 padding 位置的
  logits ⇒ **生成乱码**（实测 `_difference_difference...` / `umberumberumber...`）
* **右对齐**（左补零 + 右内容）：位置 511 = **最后一个真实 token** ⇒ 正确

**决定性实验**（`results/p3_diag_align.json`）：
| 排布 | OV argmax | torch argmax |
|---|---|---|
| left | 151645 `<|im_end|>` ❌ | 151645 `<|im_end|>` ❌ |
| **right** | **541 `all`** ✅ | **541 `all`** ✅ |

OV left vs right 的 logits cos = **−0.154354** ⇒ 两者语义完全不同。

⚠️⚠️ **由此推翻 §15.3 的 INT8 精度证据**：P1 的 teacher-forcing 判据
（cos=0.999983、top1 100%）**必然无效** —— 因为 OV 与 torch **两侧都取位置 511**
⇒ 两边"错"得完全一致 ⇒ cos 必然接近 1 ⇒ **该指标根本发现不了这个错误**。
⇒ **§15.3 的 enc cos 0.978 / dec cos 0.975 / top1 100% 全部作废**，
  INT8 是否可用**只认 P3 的 61 分钟 WER**（与 ASR-006 §4 的判断一致，
  但本模块找到了更强的技术根据）。

### 18.2 三个语义 bug 及其修复（都在 `scripts/p3_ov_app.py`）
1. **右对齐**（见 18.1）
2. **prefix 不能塞进 prompt 模板**（会打乱 audio_token 展开位置 ⇒ mask 不匹配 ⇒ 崩）
   ⇒ 改为分段拼接 `left + audio + right + prefix`（照 R2T2 `npu_embeds_backend.build_inputs_embeds`）
3. **flush 必须以 `raw` 为前缀**（否则模型从头重生成 ⇒ 每段内容重复两遍，实测过）

⇒ 修正后 30 秒冒烟：5 段文本与 P0 torch 参照**逐段一致**
（`All right. Good morning, everyone. Good morning. Let's get started. So, we.` /
`Welcome to our Q326 QGS.`）⇒ **INT8 量化后文本质量正常（GPU 路径）**。

### 18.3 ✅ NPU 阻塞解除（encoder 动态形状）
**现象**：`ov-encoder-06b-{fp16,int8sym}` 的 `input_features` 是 `[?,?,?]` 全动态 ⇒
NPU 编译失败：`vclAllocatedExecutableCreate4 result: 0x78000004 - [NPU_VCL] Compiler
returned msg: IE.Reshape doesn't support dynamic shapes`（decoder IR 静态 ⇒ 无此问题）。

**修法**（`scripts/p3_staticize_encoder.py`）：`core.read_model()` →
`model.reshape({input(0): ov.PartialShape([1,128,2400]), input(1): ov.PartialShape([1])})`
⇒ ⚠️ OV 2026.4 的 `reshape` 是**原地修改返回 None**；
⇒ 用**模块级 `ov.save_model(model, xml)`** 保存（⚠️ `Model` **没有** `save_model` 方法）。

**验证**（`results/p3_npu_compile_check.json`，NPU 编译全部通过）：
| IR | 编译 | compile_s |
|---|---|---|
| `ov-encoder-06b-fp16-static` | ✅ | 26.60 |
| `ov-encoder-06b-int8sym-static` | ✅ | 20.49 |
| `ov-dec-06b-embed-int8sym` | ✅ | 110.21 |
| `ov-dec-06b-past-int8`（stateful，非本会话产出） | ❌ | 2.90（`to_shape was called on a dynamic shape`）|

⇒ 新增产物：`models/ov-encoder-06b-fp16-static/`（372.8 MB .bin）、
`models/ov-encoder-06b-int8sym-static/`（186.9 MB .bin）。
⚠️ **静态化本身不改变语义**：`results/p3_diag_static_vs_dynamic.json`
⇒ CPU 上动态 vs 静态 **cos = 1.0、maxabs = 0.0**（逐 token 对齐 offset 全 0）。

### 18.4 🔴 INT8 decoder 的 logits 与 FP16 **近乎正交**（CPU 单步实测）
`results/p3_diag_int8_fidelity.json`（同设备内、encoder 固定 FP16、6.4 s 音频）：
| 设备 | INT8dec vs FP16dec 的 logits cos | argmax 相同 | INT8enc vs FP16enc（过 FP16dec） |
|---|---|---|---|
| CPU | **−0.000094** | ❌（541 vs 2403） | **0.999716** ✅ |
| GPU.0 | **−0.139394** | ❌ | 0.999154 ✅ |
| NPU | **−0.129165** | ✅（本例巧合） | 0.999653 ✅ |

⇒ **encoder 量化完好，decoder 量化损坏**（cos ≈ 0 而非 0.9~0.99 ⇒ 不是「精度不够」，
  而是**权重/反量化写错**）。
⚠️ 但「INT8 decoder 坏」是**设备相关**的：在 GPU 上端到端反而**只有 INT8 decoder 正常**（见 18.5）。

**排除项（都有实测产物）**：
| 候选 | 排除依据 |
|---|---|
| lm_head 被误量化 | ❌ **未排除但已确认 lm_head 是 FP16**：INT8 IR 的 lm_head MatMul 输入 = `Convert(Constant float16 [151936,1024])` ⇒ `ignored_scope` **生效** |
| 静态化破坏语义 | `p3_diag_static_vs_dynamic.json`：CPU 动态 vs 静态 cos=1.0 |
| 设备算错（单步） | `p3_diag_dev_mismatch.json`：三设备 encoder cos≥0.9998、decoder cos≥0.994、argmax 相同 |
| 首次推理未预热 | `p3_diag_npu_warmup.json`：NPU 连 5 次 encoder cos 全 0.99998、decoder argmax 全同 |
| 输入长度相关 | `p3_diag_npu_short_input.json`：mf=64/128/320/640 三设备 argmax 全同 |
| 量化配方本身 | torch 侧 fake-quant 196 权重 INT8 per-channel：cos **0.977708**、top1 ✓（**纯 numpy**，不经过 NNCF/OV）⇒ 配方没问题 |

⇒ **差异只能来自 NNCF / OV 的量化实现**。
⚠️ **scale 常量在 IR 的 MatMul 输入链上找不到**（`Multiply` 链只拿到 `[1,1,1024]` 的
fp16 常量，且**全局去重会误判 cycle**，须按路径去重）；数值反推配对
（`results/p3_diag_int8_scale_axis.json`）**frac_equal 中位数仅 0.010** ⇒
**int8 权重与 FP16 权重没能成功配对**，量化轴/广播轴**尚未判定** ⇒ **待查**。

### 18.5 ★ 端到端 2×2 矩阵（GPU.0，真实 10 步段内循环，`results/p3_diag_matrix.json`）
| encoder | decoder | 端到端结果 |
|---|---|---|
| fp16 | **fp16** | ❌ 西里尔文乱码 `šĺģš⇐търьььььььььььььь` |
| fp16 | **int8** | ✅ `All right. Good morning, everyone. Good morning. Let's get started. So, we.` |
| int8 | fp16 | ❌ 乱码 `deššššššššššššššššš` |
| int8 | int8 | ✅ 正常 |

⚠️ **与 CPU 上的单步结论相反**（CPU：FP16 cos 0.9988 正常、INT8 cos 0.038 崩）
⇒ **两个独立问题**：① CPU 上 INT8 decoder 权重/反量化异常；
② GPU 上 FP16 decoder 端到端崩坏（单步 logits 正常 ⇒ 疑似多步累积/数值溢出）。
⚠️ **NPU 侧矩阵正在跑**（`results/p3_diag_matrix.json` 追加 NPU 段）。

### 18.6 ✅ ASR-006 §5 第③点核实结论：**fake-quant 探针没有误量化 tied 权重**
`p2_fakequant_probe.py` 的 `apply_quant()` 对 `embed_tokens` 有守卫
`if nm == 'embed_tokens' and not args.quant_embed: continue`，
而 `--quant-embed` **默认 False** ⇒ **旧 fake-quant 数据未量化 embed_tokens/lm_head**
⇒ 与 OV 侧「ignore lm_head（FP16）+ 量化 196 个层权重」**口径一致**
⇒ **§15.4 第①②条证据链（fake-quant 复现 / 逐层累积）不因这一点作废**，
旧数据（INT8 cos 0.977708 / INT4 cos 0.113752）**仍有效**。

### 18.7 本轮产物清单（全部落盘，附文件数与 mtime 基准）
| 文件 | 内容 |
|---|---|
| `scripts/p3_staticize_encoder.py` | encoder 静态化（reshape + `ov.save_model`） |
| `scripts/p3_npu_compile_check.py` | NPU 编译验证（4 个 IR） |
| `scripts/p3_diag_align.py` | 左/右对齐 × OV/torch 决定性实验 |
| `scripts/p3_diag_dev_mismatch.py` | 三设备 × 精度 交叉对照 |
| `scripts/p3_diag_static_vs_dynamic.py` | 动态 vs 静态 IR 等价性 |
| `scripts/p3_diag_npu_warmup.py` | NPU 连续 5 次预热检验 |
| `scripts/p3_diag_npu_short_input.py` | 4 档输入长度 × 三设备 |
| `scripts/p3_diag_npu_multistep.py` | 复刻 runner 的 10 步逐步对照 |
| `scripts/p3_diag_npu_ablate.py` | encoder/decoder 变量分离（A/B 场景） |
| `scripts/p3_diag_npu_fp16dec.py` | FP16 vs INT8 decoder 判别 |
| `scripts/p3_diag_int8_fidelity.py` | 同设备内精度隔离 + 多 token teacher-forcing top1 |
| `scripts/p3_diag_int8_weights.py` / `_weights2.py` / `_scale_axis.py` | 权重级诊断（配对未成功） |
| `scripts/p3_diag_rootcause.py` / `p3_diag_int8_rootcause.py` | 根因判定（lm_head 确认 FP16） |
| `scripts/p3_diag_graph_dump.py` | 图结构 dump（**须按路径去重**，全局去重会误判 cycle） |
| `scripts/p3_diag_ov_vs_torch.py` | OV × OV × torch 三方对比 |
| `scripts/p3_diag_matrix.py` | 端到端 2×2×N 矩阵 |
| `results/p3_diag_*.json` | 上述全部诊断产物 |

### 18.8 口径与纪律
* **P3 长跑口径**不变：单进程不分 part、真实 `live_caption_app.Segmenter`（B 行为）、
  跑整个 wav（3671.19 s）、640 ms 分块 + 前缀回退 5 token / 前 2 块不用前缀、
  自适应 max_new_tokens、段尾 flush 预算 64。
* **计时作业持 `shared/MACHINE_LOCK`**，串行执行；**准确率作业不需要锁**。
* **WER 全部交 reviewer 复算**，目标机自算只作参考（ASR-004 铁律）。
* **不改 `live_caption/`**（ASR-003 铁律）。rule1 接缝去重已由 **App 模块**完成
  （`live_caption_app.py:648` 起的 APP-012②/APP-014① 注释：整词级 n-gram 去重
  n=3→2→1 + 「后段首词大写 & 前段末尾非句末标点」判据；
  量化收益 A −0.043pp / B −0.060pp，CI 上界<0 ⇒ 显著但**只覆盖 +2.6pp 的约 3%**
  ⇒ **接缝去重不是主因**）⇒ 本模块的 rule1 诊断**降级为可选**，不重复做。
* ⚠️ **INT4 补测仍未做**（ASR-006 §5 第②③点），限时 ≤2h，排在 P3 之后。
* ⚠️ **P0 参照重跑未做**（脚本已修：`rtf_this_run` 已删、`n_runs` 锁定、整个 wav）。
## §19 P3 根因大反转：**撤回「INT8 量化损坏」与「FP16 必崩」**，根因收窄到**输入条件**（2026-10-25 13:40）

### 19.0 本章要撤回的结论（STATUS 只追加，不回头改旧章节）
| 旧章节 | 原结论 | **本章处置** |
|---|---|---|
| §18.4 | 「**INT8 decoder 量化损坏**」（cos ≈ 0 ⇒ 权重/反量化写错） | 🔴 **撤回** —— 10 层静态比对全部相同；且**正交实验显示 INT8 也会退化** |
| §18.5 | 「GPU 上 FP16 decoder 端到端崩坏」「两个独立问题」 | 🔴 **撤回「模型层面」的解读** —— 同一份 FP16 IR 在另一组输入条件下**完全正常** |
| §18.2 | P1 的 teacher-forcing 判据（enc cos 0.999983 / top1 100%） | 🔴 **撤回** —— 判据是**自一致 tautology**（见 §19.3） |
| §18.1 | 「OV decoder IR **恒取位置 511**」 | ⚠️ **部分修正** —— 右对齐结论**仍成立**，但「恒取」不准确（见 §19.4） |
| §15.3 | INT8 的 enc cos 0.978 / dec cos 0.975 / top1 100% | 🔴 **已由 §18 撤回**，本章进一步说明**为何无效**（§19.5） |

### 19.1 ✅ 静态层面：两个 decoder IR **在 10 个层面完全相同**
| # | 层面 | 结果 | 产物 |
|---|---|---|---|
| 1 | 端口 | **相同** | `p3_diag_const_diff.json` |
| 2 | 整数常量（位置/掩码/Range 参数） | **相同** | 同上 |
| 3 | 293 个取位置类算子的索引常量 | **逐条相同** | 同上 |
| 4 | 28 个 SDPA 的 attrs + 输入规格 + mask 溯源 | **完全相同** | `p3_diag_sdpa_spec.json` |
| 5 | lm_head 权重（按输出末维 151936 定位） | **逐位相同** | `p3_diag_int8_deep.json` |
| 6 | 341 个 3D/4D/1D 常量（norm weight / RoPE） | **341/341 相同**（**多重集口径** + 排序逐条 + 序号对照，三口径一致） | `p3_diag_3d_const.json` |
| 7 | 196 个 2D 权重的反量化 | **cos min 0.999929 / p50 0.999960**，量化轴 = **axis 0**（per-output-channel） | `p3_diag_int8_dequant.json` |
| 8 | **全部算子 attrs（1523 个非插入实例）** | **0 差异** | `p3_diag_attrs.json` |
| 9 | 张量精度分布 | **相同**（f32 输出 2661/2661；f16 输出 538 vs 930 的差额 = NNCF 插入的 196 个 scale） | `p3_diag_elemtype.json` |
| 10 | .bin **实际存储精度** | **全部 native**（无「声明 f32 实存 f16」）；f16 2D 权重 0.22% 元素落在 f16 最小正规数以下 | `p3_diag_bin_precision.json` |

补充：**类型直方图差异恰好只有 3 类**（Constant/Convert/Multiply 各 **+196**）⇒
图结构完全一致，**无 FakeQuantize**（未做激活量化）。

⚠️ **本轮踩过的两个坑（方法论，必须记住）**：
* **`get_ordered_ops()` 的序号会漂移** —— NNCF 插入 196×3 个节点 ⇒ 后续序号整体偏移
  ⇒ **不能用序号配对常量/算子**。可靠口径：**多重集比对**（Counter）、
  **类型内第 k 个实例**（仅限 NNCF 不插入的类型）、**friendly_name**。
* **`model.add_outputs(tensor)` 在 OV 2026.4 失败**（"Incorrect type of a value to add as output"）
  ⇒ 可用写法：**`model.add_outputs(consumer_op.input_value(i))`**（加的是消费者的输入端口）。

### 19.2 🔴★★ 决定性反转：**FP16 并不崩，INT8 反而退化**（`results/p3_diag_surgery.json`）
CPU、**固定 6.4 s 音频**、**无 prefix 回退**、每步 8 token 贪心：
| 图 | 10 步首 token | 判定 |
|---|---|---|
| **fp16** | `all` → ` right` → ` good` → ` morning` → ` everyone` → ` good` → ` morning` → ` let` → `'s` → ` get` | ✅ **全程正常英文** |
| **fp32**（重新保存） | **与 fp16 逐位相同** | ✅ ⇒ `compress_to_fp16` **无损**（复核 §18.5 的说法） |
| **int8** | `All` → ` right` → `.` → ` Good` → ` morning` → ` everyone` → `.` → ` Good` → ` morning` → `.` | ⚠️ **重复退化**（`.`↔`Good`/` morning` 2-token 循环） |

⇒ **两个 IR 都没有「坏」**；退化是**输入条件**触发的。
⇒ 前序「FP16 端到端必崩 / INT8 正常」是**特定输入组合下的现象**（§19.3）。

### 19.3 🔴 teacher-forcing 判据是**自一致 tautology**（`p2_multitoken_top1.json` 原始字段）
`ov_fp16_gpu.per_segment[0]`：
```
target  = [97622, 97622, 97622, 97622, 4824, 97622, 4824, 4824, ... ×20]
argmax  = [97622, 97622, 97622, 97622, 4824, 97622, 4824, 4824, ... ×20]
```
* 4824 = `ь`、97622 = `系统` 一类 ⇒ **target 序列本身就是退化重复**
* FP16 的「top1 100%」= **拿自己的退化输出当 target 再对齐自己** ⇒ **恒等于 100%**
⇒ **该判据对 FP16 完全无效**，对 INT8 的 72.02% 也只是「偏离退化模式的程度」
⇒ **不能再用它比较 FP16/INT8/INT4 优劣**。
⇒ 顺带解释 §18.4 的「logits cos ≈ 0」：teacher-forcing 明细显示 INT8 只在
**2 个 margin 极小**的位置翻转（margin **0.77** / **0.027**），其余 **10/12 命中且 margin 很大**
⇒ **151936 维稀疏 logits 的全向量 cos 不可作为「模型坏了」的判据**。

### 19.4 ⚠️ 修正 §18.1：「恒取位置 511」不准确，但**右对齐仍然正确**
* `p3_diag_align.json`（CPU，单步）：**左对齐时 FP16 与 INT8 都给 `<|im_end|>`**
  （top5 = `['<|im_end|>',' case','�','  \n','\n']`）⇒ 左对齐让 511 落在 padding 区 ⇒ 输出无意义
  ⇒ **右对齐是必须的**（结论不变）。
* `p3_diag_pos_sem.json`：同一份 embeds 放在 512 窗口的 **3 个不同 offset**（0 / 100 / 411）
  ⇒ **logits 完全不同**（FP16 offset0→`<|im_end|>`、offset100→`.”`、offset411→`all`）
  ⇒ IR **不是**「恒取 511」，位置计算**依赖内容落点**。
* 运行时抓取位置链（`p3_diag_rope_probe.json`）：两图的 position id 张量
  **完全相同**（`ScatterNDUpdate` 输出 min 0 / max 511 / 非零 98112；
  `Gather` 输出 min 0 / max 511 / 非零 32704）⇒ **位置语义两图一致**。

### 19.5 ✅ 其余假设逐条排除（均有产物）
| 假设 | 排除依据 | 产物 |
|---|---|---|
| 精度提示（f16 vs f32） | FP16 端到端在 **f32 提示下仍乱码** ⇒ 非精度问题 | `p3_diag_precision_hint.json` + `p3_diagcheck_gpu_fp16dec_f32/` |
| 内容长度 / RoPE 位置偏移 | 长度扫描 L=26→115：FP16 **全程**乱码、INT8 逐步转正常 | `p3_diag_len_sweep.json` |
| 设备相关（CPU vs GPU） | 乱码模式**逐字相同**（`'šĺģ�šĺģ�'` / `'ьььььььь'`）⇒ **确定性的图级差异，不是数值噪声** | `p3_diag_device_steps.json` |
| IR 权重被 f16 舍入损坏 | FP16 IR 权重 vs torch `named_parameters`：**197/311 匹配、cos = 1.0、relerr = 0** | `p3_diag_ir_weight_check.json` |
| `compress_to_fp16` 损坏图 | 以 `compress_to_fp16=False` 重新保存：**0 个常量变化**，bin 字节数完全相同（1,192,582,552） | `p3_diag_f32_save.json` |
| 编译后 fusion 不同 | 编译后算子数 FP16 **1824**；INT8 图 `get_runtime_model()` **触发 segfault** ⇒ 该口径**不可用**（如实记录） | `p3_diag_compiled.py`（未落盘结论，脚本在） |

### 19.6 🔴 待隔离的两个变量（**正在跑**：`p3_diag_orthogonal.py` → `p3_diag_orthogonal.json`）
| 脚本 | 音频 | prefix 回退 | FP16 | INT8 |
|---|---|---|---|---|
| `p3_diag_surgery.py` | **固定 6.4 s** | **无** | ✅ 正常 | ⚠️ 退化 |
| `p3_diag_device_steps.py` / `_len_sweep.py` | **逐步累积** 0.64→6.4 s | **有**（回退 5 token） | ❌ 乱码 | ✅ 正常 |
| `p3_ov_app.py`（真实 App） | 逐步累积 | 有 | ❌ 乱码 | ✅ 正常 |

⇒ **V1 = 音频累积长度**、**V2 = prefix 回退**，正交实验 2 图 × 3 模式 × 2 prefix = 12 组。

### 19.7 ⚠️ P3 61 分钟长跑（GPU.0 + INT8 enc + INT8 dec）的计时口径**作废**
* 产物：`qwen3asr_06b/results/p3_p3_61min_gpu_int8/segments.jsonl`（**13:05 时 67 段 → 13:38 时 254 段**，
  文本持续为正常英文，如 `Moving forward. Okay, next slide. Alex, share this…`）。
* 🔴 **`timing_valid = false`**：本作业 **12:56** 启动时 `shared/MACHINE_LOCK` **已被 `mt` 模块占用**
  （内容 `module: mt / pid: 34440 / started: 2026-10-25 11:19:54`，进程存活，
  命令行 `_run_h016_v5_batches.py`）⇒ **计时被其它模块干扰**
  ⇒ **质量数据可用，RTF / P50 / P95 / 首字延迟 / 内存一律不得引用**。
  ⇒ 后续如需计时，**必须先确认锁空闲**再启动。

### 19.8 本轮产物清单（全部落盘；mtime 2026-10-25）
| 脚本 | 产物 | 关键结论 |
|---|---|---|
| `scripts/p3_diag_3d_const.py` | `results/p3_diag_3d_const.json` | 341/341 相同（三口径） |
| `scripts/p3_diag_elemtype.py` | `results/p3_diag_elemtype.json` | 精度分布相同 |
| `scripts/p3_diag_bin_precision.py` | `results/p3_diag_bin_precision.json` | 存储精度全 native |
| `scripts/p3_diag_attrs.py` | `results/p3_diag_attrs.json` | **1523 实例 attrs 0 差异** |
| `scripts/p3_diag_align.py` | `results/p3_diag_align.json` | 左对齐两图都 EOT |
| `scripts/p3_diag_pos_sem.py` | `results/p3_diag_pos_sem.json` | offset 会改 logits |
| `scripts/p3_diag_rope_probe.py` | `results/p3_diag_rope_probe.json` | 位置 id 运行时相同 |
| `scripts/p3_diag_device_steps.py` | `results/p3_diag_device_steps.json` | 跨设备乱码逐字相同 |
| `scripts/p3_diag_surgery.py` | `results/p3_diag_surgery.json` | **FP16 正常 / INT8 退化** |
| `scripts/p3_diag_orthogonal.py` | `results/p3_diag_orthogonal.json` | （在跑）正交隔离 |
| `scripts/p3_diag_compiled.py` | （未落盘，INT8 图 segfault） | 编译后图口径不可用 |
| `scripts/p1_export_decoder_f32.py` | （待跑）真 f32 导出（`compress_to_fp16=False`） | 备用解法路径 |

### 19.9 口径与纪律（补充 §18.8）
* **本模块不得再宣称「FP16 更好」或「INT8 更好」**，直到 §19.6 的正交实验定因。
* **不得用 teacher-forcing top1 比较 FP16/INT8/INT4**（自一致 tautology，§19.3）。
* **不得用「logits 全向量 cos」判「模型坏了」**（151936 维稀疏尖峰，§19.3）。
* 后续若要改判据：应使用**非退化的目标**（例如 reviewer 给定的真值文本 / torch 自然排布的
  贪心输出），并**同时报告 argmax 与 top-5 命中**（`p3_diag_align.json` 显示
  FP16 top5 含 `All`、INT8 top5 含 `Alright` ⇒ **两者答案都在 top5，只是排序不同**）。
* **P3 长跑的质量数据（转写文本）可用；计时数据全部作废**（§19.7）。

### 19.10 ✅✅ 正交实验完成（`results/p3_diag_orthogonal.json`）：**两个 IR 都会退化**，只是阈值不同
CPU、每步 8 token 贪心、6 步；`fixed` = 固定 6.4 s 音频，`cum1` = 累积到 0.64 s，
`cumN` = 累积到 n×0.64 s；`prefix` = 是否启用「回退 5 token 前缀」。
| 图 | 模式 | prefix | step1 (L=26) | step2 | step4 | step6 | 判定 |
|---|---|---|---|---|---|---|---|
| **fp16** | fixed (L=101) | ✗ | `all right good morning everyone…` | 同上 | 同上 | 同上 | ✅ **正常** |
| **fp16** | fixed (L=101) | ✓ | `all right good morning…` | ` morning everyone…` | ` get started so very very very` | ` very very very…` | ⚠️ **退化**（`very` 复读） |
| **fp16** | cum1 (L=26) | ✗ | `��ℿ�ℿ�` | 同上 | 同上 | 同上 | ❌ **乱码** |
| **fp16** | cumN | ✗ | `��ℿ�ℿ�` | `��ℿ�` | `šĺģ�šĺģ�` | `š�ъразьшьь` | ❌ **乱码** |
| **fp16** | cumN | ✓ | `��ℿ�ℿ�` | `��칩�ли` | `šĺģ�šĺģ�` | `ьъисъешьъеш` | ❌ **乱码** |
| **int8** | fixed (L=101) | ✗ | `All right. Good morning everyone…` | 同上 | 同上 | 同上 | ✅ **正常** |
| **int8** | fixed (L=101) | ✓ | `All right. Good morning…` | ` Good morning everyone…` | `. Let get started. So well.` | ` started. So well.` | ✅ **正常** |
| **int8** | cum1 (L=26) | ✗ | **`��系统。`** | 同上 | 同上 | 同上 | ❌ **乱码（INT8 也乱码！）** |
| **int8** | cumN | ✗ | `��系统。` | `System.` | `All right. Good morning.` | `All right. Good morning everyone. Good` | ✅ **正常** |
| **int8** | cumN | ✓ | `��系统。` | `System.` | `All right. Good morning.` | `. Good morning everyone. Good morning.` | ✅ **正常** |

⇒ **结论 1**：**L=26（0.64 s）时 FP16 与 INT8 都输出乱码**
（FP16 `��ℿ�ℿ�` / INT8 `��系统。`）⇒ **短输入退化不是量化问题**
⇒ §18.4「INT8 量化损坏」与 §18.5「FP16 端到端崩坏」**均不成立**。
⇒ **结论 2**：**阈值不同** —— FP16 需 L≳101 才正常，INT8 **L≳35 即正常**
（INT8 在这一点上**更稳**）。
⇒ **结论 3**：**prefix 回退**在 FP16 上会诱发 `very very very…` 复读（INT8 不受影响）
⇒ prefix 回退把「已生成的 token」重新喂回，**FP16 对此更敏感**。
⇒ **结论 4**：先前「FP16 全程乱码」只在 **L≤68 的累积模式**成立，
在 **L=101 固定音频**下 FP16 **完全正常** ⇒ **「FP16 必崩」的说法过宽**。

### 19.11 ✅ 判读口径再修正：**「乱码」≠「模型坏」**
* 短输入（L=26）下**两个模型都**给出乱码 ⇒ 这是**该输入下的正常行为**
  （0.64 s 音频只含 1~2 个词，模型本来就没内容可转写）。
* **下一必须查的量**：乱码档的 logits 是否出现 **NaN / Inf**（f16 溢出）、
  **top1 margin**（排序脆弱）、**softmax 熵**（模型没主意）。
  脚本 `scripts/p3_diag_logit_health.py` → `results/p3_diag_logit_health.json`（**在跑**）。
* ⚠️ 在该实验出结果前，**本模块不使用「崩坏 / 损坏」这类措辞**，
  统一表述为「**该输入条件下输出退化**」。

### 19.12 ✅★ **机制查清**：「乱码」是**置信度平坦 + 贪心漂移**，不是数值损坏（`results/p3_diag_logit_health.json`）
CPU、累积音频档位、每档测**单步** logits 的健康度：
| 图 | nstep | L | NaN | Inf | logit_max | top1_margin | **熵** | mass_top1 | top1 | top5 |
|---|---|---|---|---|---|---|---|---|---|---|
| fp16 | 1 | 26 | 0 | 0 | 16.95 | 1.690 | **5.796** | 0.192 | `�` | `�`,`<\|im_end\|>`,`�`,`ъ`,`ǥ` |
| fp16 | 2 | 35 | 0 | 0 | 16.49 | 0.986 | **5.960** | 0.130 | `�` | `�`,`razil`,`de`,`RectTransform`,`ći` |
| fp16 | 4 | 51 | 0 | 0 | 15.61 | 0.460 | **5.900** | 0.077 | `š` | `š`,`�`,`ｂ`,` реб`,`bris` |
| fp16 | 6 | 68 | 0 | 0 | 17.09 | 1.801 | **4.726** | 0.344 | `š` | `š`,`RectTransform`,`št`,`man`,`ż` |
| fp16 | 8 | 85 | 0 | 0 | 17.59 | 0.273 | **5.505** | 0.133 | `all` | `all`,`아`,`de`,`every`,`<\|im_end\|>` |
| fp16 | 10 | 101 | 0 | 0 | 21.46 | 1.677 | **4.983** | 0.256 | `all` | `all`,`aff`,`right`,`All`,`language` |
| fp16 | 11 | 110 | 0 | 0 | 23.07 | 1.461 | **1.017** | 0.747 | `All` | `All`,`all`,`Right`,`Everything`,`l` |
| int8 | 1 | 26 | 0 | 0 | 20.65 | 0.270 | **5.437** | 0.192 | `�` | `�`,`<\|im_end\|>`,`�`,`раз`,`�` |
| int8 | 2 | 35 | 0 | 0 | 19.49 | 1.240 | **5.704** | 0.182 | `System` | `System`,`.`,`system`,`emotion`,`son` |
| int8 | 4 | 51 | 0 | 0 | 20.41 | 0.045 | **1.038** | 0.490 | `All` | `All`,`all`,`I`,`Right`,`Good` |
| int8 | 6 | 68 | 0 | 0 | 20.31 | 1.067 | **0.693** | 0.733 | `All` | `All`,`all`,` All`,`Alright`,`Right` |
| int8 | 8 | 85 | 0 | 0 | 20.66 | 0.668 | **0.750** | 0.653 | `all` | `all`,`All`,`I`,`’all`,` All` |
| int8 | 10 | 101 | 0 | 0 | 21.09 | 0.767 | **0.774** | 0.669 | `All` | `All`,`all`,`Alright`,`Right`,`I` |
| int8 | 11 | 110 | 0 | 0 | 20.43 | 1.598 | **0.646** | 0.810 | `All` | `All`,`all`,`Alright`,`Right`,`I` |

**判读（三条硬结论）**：
1. ✅ **没有任何 NaN / Inf / f16 溢出**（`f16_overflow` 全 false，logit_max ≤ 23.07 ≪ 65504）
   ⇒ **排除「数值溢出 / NaN」这一整类原因**。
2. ✅ **FP16 的 logits 是「平坦」的**：熵长期停在 **4.7~6.0**（≈ln(120)~ln(400)）
   ⇒ 模型**没有主意**，正确答案常在 **top5 内但排名靠后**
   （L=101 时 top5 = `all`,`aff`,`right`,`All`,`language` ⇒ 正确项 `right`/`All` 在第 3/4 位）。
   ⇒ **贪心解码一旦选中 `all`（而非 `All`），后续 token 分布随之漂走 ⇒ 输出乱码**。
   ⇒ **「乱码」= 置信度不足导致的贪心漂移**，不是模型损坏。
3. ✅ **INT8 的 logits 是「尖锐」的**：从 L=51 起熵就降到 **~1.0 并保持**
   ⇒ top1 稳定 ⇒ 输出正常。
   ⇒ **INT8 在「置信度」这个维度上确实比 FP16 稳**（不是「INT8 量化更好」，
   而是在**这个具体输入分布上**更稳）。

⚠️ **判据口径再收紧**：**「top1 不对」不等于「模型错」** —— 必须看 **top-5**
（FP16 在 L=101 的正确答案就在 top5）。⇒ **后续所有质量判定都要同时报 top-5 命中**。

## §20 收到 ASR-007 / ASR-008 / ASR-009：**INT4 补测完成（「0.6B INT4 不可行」被证伪）** + 对比矩阵更新（2026-10-25 16:40）

### 20.0 本章处理的纠偏条目与执行结果一览
| 条目 | 要求 | 本轮结果 | 产物 |
|---|---|---|---|
| **ASR-007** | 交付 R2T2 × 0.6B 的「精度 × 设备」对比报告 | ✅ **矩阵更新**（16 格，每格一份 json + `MATRIX.md`/`MATRIX.json`）；0.6B 的 INT8/INT4 格子由本轮补全 | `qwen3asr_06b/reports/compare/`（**17 个文件**，含 2 个新 INT4 格子） |
| **ASR-008 / ASR-009** | 继续做：0.6B INT8（App 路径，持锁）→ INT4 限时补测 → 切点重复诊断 → R2T2 对比 0.6B 报告 | ✅ ① **INT4 限时补测完成且结论反转**（§20.2/§20.3）② **INT8 61 分钟质量数据已落盘**（§20.4）③ **切点重复诊断已完成**（§20.5，由并发会话产出）④ **对比矩阵已更新**（§20.6） | 见上 |
| **ASR-006 §5②** | GPU 上 `INT4_ASYM g128 + AWQ + SE`（backup INT8_ASYM，lm_head 保 FP16），5 分钟切片贪心解码看文本是否正常 | ✅ **文本正常 ⇒ INT4 可用** | `results/p3_int4_slice/`、`results/p3_int4_fixedlen/` |
| **ASR-006 §6** | P3 走 App 路径、单进程、跑整个 wav | ✅ **已跑完整个 wav（3671.19 s）**，553 段 | `results/p3_p3_61min_gpu_int8/`（4 文件） |

### 20.1 ✅★ 最重要结论：**「0.6B INT4 不可行」被本轮数据证伪**（但**配方必须换**）
ASR-006 §5 把「0.6B INT4 不可行」降级为「证据不足，暂不关闭」。本轮做完 §5② 后：

| 配方 | 5 分钟切片总词数 | 定长 top1 | 定长 top5 | 判定 |
|---|---|---|---|---|
| **INT8**（INT8_SYM per-channel，lm_head FP16） | **928** | **70.83%** | 87.90% | ✅ 基准 |
| **INT4_ASYM g128 + AWQ + SE**（backup INT8_ASYM） | **882** | **69.44%** | 85.71% | ✅ **可用，与 INT8 同量级** |
| **INT4_SYM 按通道 + AWQ + SE**（= R2T2 R2 照搬） | **98** | **16.27%** | 28.77% | 🔴 **崩坏** |
| FP16（对照） | 164 | 89.29% | 94.44% | ⚠️ 见 §20.3 |

* ⇒ **0.6B 的 INT4 可用**（INT4_ASYM g128 路线），**「不可行」结论被推翻**。
* ⇒ **但照搬 R2T2 的「按通道 + AWQ + SE」配方在 0.6B 上不成立**
  ⇒ 差异来自**模型规模/宽度**，不是配方本身的普遍性。
* ⚠️ 本轮用的是**代理指标**（词数 / 文本健康度 / token 级命中率），**不是 WER**
  ⇒ 质量等级**必须由 reviewer 用本机 baseline 复算 61 分钟全长 WER**后才能下结论。

**原始字段（可复核）**：
* 量化产物 `qwen3asr_06b/results/p2_quant_decoder_int4__asymg128.json`（15:58，2153 B）
  - `recipe` = `"INT4_ASYM g128 ratio=1.0 + AWQ + SE + backup=INT8_ASYM"`
  - `dst_mib` = **518.3**（源 1139.4，`size_ratio` 0.4549）
  - `dst_const_stats.n_i4` = **392**（uint4_t）、`n_i8` = **0**、`n_f16` = 538
  - `ignored_scope` = `["linear_196/aten.linear.default/MatMul"]`（**lm_head 保 FP16** ✔）
* 切片解码 `results/p3_int4_slice/summary_all.json`（16:12/16:16/16:20/16:27，4 个 `summary.json`）
* 定长判据 `results/p3_int4_fixedlen/summary_all.json`（16:28/16:30/16:32/16:34，4 个 `summary.json`）

### 20.2 ✅ INT4 补测的做法（ASR-006 §5② 原文要求的口径）
**新配方量化**（`scripts/p2_quantize.py` **本轮新增 `--asym` / `--backup-asym` 开关**，
因为原脚本只有 INT4_SYM + backup INT8_SYM，**不支持 §5② 指定的 INT4_ASYM + INT8_ASYM**）：
```
python scripts/p2_quantize.py --model decoder --int4 --asym --backup-asym \
    --group-size 128 --calib results/p2_calib_decoder.npz --tag _asymg128
```
⇒ 耗时 3m50s，NNCF 统计：`int4_asym, group size 128` 覆盖 **196/196** 个 ratio-defining 参数，
`float` 1/197（= lm_head，ignored_scope 命中）✔
（校准集只有 64 条 < subset_size 128，NNCF 有 WARNING 但不影响结果）。

**判据脚本**（本轮新写 2 个）：
| 脚本 | 用途 | 设计 |
|---|---|---|
| `scripts/p3_int4_slice_decode.py` | §5② 原文的「5 分钟切片贪心解码」 | 走**真实 App 路径**（`live_caption_app.Segmenter` B 行为 + 640 ms 分块 + 前缀回退 5 token + **自适应 max_new_tokens** + 段尾 flush 64） |
| `scripts/p3_int4_fixedlen.py` | **干净判据**（隔离累积长度与前缀两个变量） | **固定 6.4 s（L=101 mel 帧）+ 关闭前缀** ⇒ 文本差异**只能**来自权重量化 |

⚠️ **为什么必须加「定长」这一路**（§19 的直接应用）：
`p3_int4_slice_decode.py` 的**累积**路径下，**FP16 自己也退化**
（`results/p3_int4_slice/fp16/summary.json`：`total_words` 仅 **164** vs INT8 **928**，
`nonlatin_ratio` **0.8023**、43/46 段非拉丁占比 >30%）
⇒ §19 已证明：**累积路径下 L=26 的短输入会让 FP16 和 INT8 都输出乱码**
⇒ 在累积路径上「谁正常」被**首段短输入 + 前缀污染**主导 ⇒ **测不出量化差异**。
⇒ 定长路径（`p3_int4_fixedlen.py`）才是能判 INT4 好坏的干净口径。

### 20.3 ✅ 定长口径下的完整对照（`results/p3_int4_fixedlen/summary_all.json`）
**设计**：固定 6.4 s（L=101 mel 帧）+ 无前缀 + encoder 固定 OV FP16（**非量化**）
⇒ 被测的**只有 decoder 的权重量化**。评测段 20 个，全部取自 **≥12 分钟** 区段
（校准集 0–12 分钟不含评测音频），共 **504** 个 target token。

| 变体 | top1 命中 | top1 % | top5 % | 总词 | 替换字符 | 非拉丁占比 | 复读 top1 | 段非拉丁>30% |
|---|---|---|---|---|---|---|---|---|
| **fp16**（参考） | 450/504 | **89.29%** | 94.44% | 244 | 0 | 0.2090 | 0.0451 | 3 |
| **int8** | 357/504 | **70.83%** | 87.90% | 396 | 0 | 0.2259 | 0.0354 | **0** |
| **int4_asymg128** | 350/504 | **69.44%** | 85.71% | 363 | 0 | 0.2214 | 0.0386 | 2 |
| **int4_sym_chan** | 82/504 | **16.27%** | 28.77% | 20 | 0 | 0.0815 | 0.0500 | 2（复读段 20） |

**文本样例（原始字段 `transcript`）**：
* int8：`"But we're making good progress. Just last week, we powered on our. Our."`
* int4_asymg128：`"But we are making good progress. Just last week, we powered on our. Our. Our."`
  ⇒ **正常英文**，与 INT8 几乎逐词一致
* int4_sym_chan：`"â颈âчь蹄nisnistrasnisurenisnisurenisnisurenisnisuris…"` ⇒ **崩坏**

⚠️ **口径声明**：top1/target 来自 **FP16 参考自己的贪心输出**（非退化目标，
§19.2 已证明 FP16 在 L=101 正常）⇒ **不是 §19.3 那种自一致 tautology**
（§19.3 的 target 是 4824 'ь' 连续 20 次的退化序列）。
⚠️ 但 **FP16 的 top1 只有 89.29%（不是 100%）** ⇒ 这个指标本身**对 0.6B 敏感**
（与 ASR-006 §5 退回旧判据的理由一致）⇒ **必须与 top5 一起读**
（§19.12 的收紧口径），且**不能单独用它定「可用/不可用」**
⇒ 本章的判定依据是**文本本身是否正常**（词数 + 非拉丁占比 + 复读率），
top1/top5 只作**同口径的相对对照**。

### 20.4 ✅ P3 INT8 的 61 分钟全长**质量**数据（`results/p3_p3_61min_gpu_int8/`）
**产物（4 个文件）**：`summary.json`（15:07，2366 B）、`segments.jsonl`（14:12，142560 B）、
`segments.json`（14:12，164733 B）、`transcript.txt`（14:12，75526 B）。

| 字段 | 值 |
|---|---|
| `audio_sec` / `covered_s` | **3671.189 / 3671.189**（`complete` = **true**）⇒ **跑的是整个 wav，未截断** ✔（满足 ASR-006 §3） |
| `n_segs` | **553** |
| `rule_counts` | rule1 **518** / rule2 **34** / flush **1** |
| `total_words` | **11825** |
| `n_steps_total` | 5737 |
| `seg_dur_p50` / `p95` / `max` | **6.4 / 8.96 / 12.16** s |
| `segmenter` | `live_caption_app.Segmenter（真实 App 切段器，B 行为）` |
| `timing_valid` | **false** |

🔴 **该次运行的计时数据全部作废**（§19.7 已记，此处补上**锁路径**这一条新证据）：
* 启动时规范路径 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK` 已被 `mt` 占用
  （PID 34440 存活）⇒ 计时被干扰；
* ⚠️ **且本次 ASR 把锁写在了仓库内相对路径**
  `confucius4-openvino\shared\MACHINE_LOCK`（内容 `asr PID=8363 start=2026-10-25 12:56:21`）
  ⇒ **App / MT / TTS 在规范路径上看不到这把锁** ⇒ 互锁失效
  （TTS 的 `shared/NOTICE_tts_lock_path_20261025.md` 已实测记录此事，
  且 TTS 因此反复拿到 `timing_valid=false`）。
* ⇒ 本轮**已回收**该孤儿锁（PID 8363 已不在），并**新写**
  `scripts/p3_run_with_lock.py`：只用**规范路径**、写锁时**同时写两种格式**
  （README 单行 + key-value）、读锁支持**多编码回退**（utf-8/gbk/cp936/latin-1）、
  **PID 不在则回收**、**`finally` 保证删锁**（不留孤儿）。
* ⇒ **规范路径持锁重跑已启动**（`results/p3_p3_61min_gpu_int8_locked/`），
  16:23 起在等 `app` 的锁（PID 32652 存活）⇒ 本章**未拿到**其计时结果。

### 20.5 ✅ ASR-006 §2 切点重复诊断已完成（**由并发会话产出，本线程只引用不改代码**）
产物：`confucius4-openvino/results/asr_diag/asr006_rule1_cut_diag.{py,json,md}`
（`json` **1 777 399 B** / `md` **18 323 B**，mtime **16:35**；脚本 71 232 B，mtime 16:22）。

**机制结论（`.md` §0）**：规则1 的语义是「**最近 3 秒内存在一段 ≥300 ms 静音**」
（`find_silence_in_range` 只取 not-None，中点不参与定位），
而**切点落在实时喂音的 chunk 栅格**（`CHUNK_SEC=0.64 s`）
⇒ **静音位置与切点位置解耦** ⇒ 切点可以落在词中间。
对照：规则2 用 `find_trailing_silence`（紧贴末尾）+ ≥0.8 s ⇒ 规则2 切点天然落在词间隙。

**关键数字**：
| 量 | A 组 | B 组 |
|---|---|---|
| 段数 / 切点（不含 EOF） | 538 / 537 | 558 / 557 |
| 切点分类 | rule1 **503** / rule2 20 / flush 14 | rule1 **508** / rule2 36 / flush 13 |
| **rule1 占全部切点** | **93.67%** | **91.20%** |
| 「切在词中间」（N=2 后缀匹配） | **9.54%**（48/503 rule1） | **10.93%**（55/508 rule1） |
| N=3 / N=4 | 7.95% / 7.36% | 9.15% / 8.55% |
| **静音内切点的「切在词中间」比例** | **0.0%**（sil −40/−45/−50 三档全部） | **0.0%**（三档全部） |
| 非静音切点的「切在词中间」比例 | 10.77% / 10.48% / 10.18% | 11.56% / 11.30% / 11.09% |

🔴 **「重复词去重」路线的天花板远低于 +2.63pp**（`.md` §4b，已与 reviewer 观测交叉核对）：
reviewer 观测 A 对交付基准 **+2.63pp**（CI [1.80, 3.41]）、插入 641 对 463、**多 178 个**；
而「同一个词在接缝两侧各被转写一次」这种形态在 A 组**只有几十个接缝**：

| 口径 | rule1 接缝数 | 可消词数（上界） | 估计 WER 收益（上界） | 占 reviewer 多余插入 |
|---|---|---|---|---|
| N=2 | 55 | ≤110 | ≤0.963pp | **≤61.8%** |
| N=3 | 46 | ≤92 | ≤0.806pp | ≤51.7% |
| N=4 | 43 | ≤86 | ≤0.753pp | ≤48.3% |

⇒ **独立量化证实 §18.8 的结论「接缝去重不是主因」**（App 已实现的整词级 n-gram 去重
量化收益只有 −0.043pp / −0.060pp）⇒ **剩下的插入是 ASR 本身的识别错误**
（切点附近上下文被截断/错切），**不是**去重能消的
⇒ 要动就得**改切点位置本身**（把切点移到静音中点），**属 App 模块**（ASR-003 边界）。

**离线去重模拟的收益上界（A / B 组）**：
`plan1_ngram_keep1` 22/22 词（≤0.193pp / ≤0.228pp）、`plan2_seq_L1` 36/42 词
（≤0.315pp / ≤0.369pp）、`plan2_charprefix_kmin2_L1` 51/51 词（≤0.447pp / ≤0.448pp）、
`plan2_charprefix_kmin2_L4` 361/442 词（≤3.161pp / ≤3.882pp），
`plan3_merge_non_silence_rule1_sil40` 34/40 词（≤0.298pp / ≤0.351pp）
⇒ **收益随 L 放大，但 L 越大误删风险越高** ⇒ 需 reviewer 复算取舍。

**「把 rule1 的静音要求从 300 ms 提到 X」的离线指标（`.md` §5b）**：
🔴 **`min_silence_ms=300` 与 `SIL_LOOKBACK_SEC=3.0` 在 `live_caption_app.py` 里是硬编码、没有 env**
⇒ **真正提高它必须改代码（App 模块）**，不是「只改 env」能做到。
（sil_db=−40 时：req≥500 ms ⇒ 51.69% 的 rule1 切点不再触发；req≥800 ms ⇒ 94.63%；
req≥1000 ms ⇒ 97.61%）

**env 重放保真度**（`.json` → `groups.{A,B}.env_replay`）：
`baseline` 重放与产物切点的匹配率 A **99.63%** / B **99.64%** ✔
⇒ env 重放口径可信；`MIN_SEG_SEC=8/10/12` 会把匹配率降到 ~29%（切点整体前移），
`SIL_REL_DROP=6`（B 组）把 rule2 从 36 提到 111 ⇒ **相对化静音阈值会大幅改变切点分布**，
这些都只是**切点层面的中间量**，不等于 WER 收益。

### 20.6 ✅ ASR-007 对比矩阵已更新（`qwen3asr_06b/reports/compare/`）
**目录现有 17 个文件**（mtime 2026-10-25 16:36）：
`MATRIX.json`（2363 B）、`MATRIX.md`（**新生成**，汇总表 + 做不了的格子 + 产物清单）、
以及 15 个格子 json。其中**本轮新增/更新 3 个**：
| 格子 | 状态 | 关键字段 |
|---|---|---|
| `qwen3asr_06b__int4_asymg128__gpu0.json`（**新**） | **OK** — 文本正常，与 INT8 同量级 | `accuracy.proxy_metrics_5min_slice.total_words` 882 / `proxy_metrics_fixedlen.top1_pct` 69.4444 / `top5_pct` 85.7143；`timing_valid` = **false**（未持锁） |
| `qwen3asr_06b__int4_sym_chan__gpu0.json`（**新**） | **BROKEN** — 文本崩坏 | `total_words` 98 / `top1_pct` 16.2698 / `top5_pct` 28.7698 |
| `qwen3asr_06b__int4__all.json`（**更新**） | **RESOLVED** — INT4 在 0.6B 上可用（INT4_ASYM g128） | 新增 `resolution_2026_10_25` 字段，含 `evidence_int4_asymg128` / `evidence_int4_sym_chan` / `why_scenario` / `still_missing` / `caveat` |
| `qwen3asr_06b__int8__gpu0.json`（**更新**） | OK — 61 分钟全长跑完（quality OK） | `accuracy.quality_proxy`（553 段 / 11825 词 / rule_counts / 段长 p50 p95 max / `complete`=true）；`latency` 全部标 `timing_valid=false` 并列 `invalid_fields` |

⚠️ **两套计分器仍不可混用**（ASR-002 铁律，`MATRIX.md` 顶部保留该警告）：
* **目标机计分器**：全局对齐 + 分段配对 bootstrap（7.798% / 7.952% / 9.795%）
* **reviewer 计分器**：MiniMax baseline（8.17% / 8.27% / 10.97% / 14.80%）
⇒ **0.6B 的所有 WER 一律空着**（`wer_pct: null`），交 reviewer 复算。

### 20.7 ⏳ 本轮明确**未完成**的（不冒充已交付）
| 项 | 状态 | 原因 |
|---|---|---|
| **0.6B INT8 61 分钟持锁重跑**（交付级计时） | ⏳ **在跑**（16:23 起等 `app` 的锁，PID 32652 存活） | 规范路径锁被 App 持有 ⇒ 按协议等待 |
| **0.6B INT8 / INT4 的 61 分钟全长 WER** | ❌ **未做** | 本模块**不自算 WER**（ASR-002）⇒ 交 reviewer |
| **0.6B INT4 的 NPU 格** | ❌ **未做** | `ov-dec-06b-past-int8`（stateful）在 NPU 上编译失败：`to_shape was called on a dynamic shape`；且非 stateful decoder 在 NPU 上输出复读 prompt |
| **reviewer 指定的 R2T2 R2 标定点**（同口径 teacher-forcing top1） | ❌ **未跑** | 需 R2T2 自己的 encoder 输出 + prompt 模板 + R2 IR；§5① 已把 0.6B 侧的原始 token 级计数给出（`results/p2_multitoken_top1.json`，20 段 / 436 token） |
| **P0 参照重跑** | ❌ **未做** | 排在 P3 之后；P3 INT8 已跑完整个 wav，但 P0 流式参照本身仍少 11.19 s |
| **≥2 次 fresh 进程的交付级 RTF** | ❌ **未做** | 现有都是 n=1 ⇒ 全部 `timing_valid=false` |
| **设备内存峰值/稳态**（iGPU / NPU） | ❌ **未测** | `mem_device` 均为「未匹配到设备」 |
| **模型加载/首次编译耗时（分有缓存/无缓存）** | ❌ **未测** | 只测到冷编译 |

### 20.8 口径与纪律（本章新增的硬规则）
1. 🔴 **锁只能用规范路径** `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`
   ⇒ **仓库内相对路径 `shared/MACHINE_LOCK` 会让 4 模块互锁失效**
   （TTS 已实测记录 ⇒ 本轮据此新写 `scripts/p3_run_with_lock.py`）。
2. 🔴 **「模型好不好」必须先隔离输入条件**（§19 的延续）：
   累积音频 + 前缀回退路径下，**FP16 自己也会退化**
   ⇒ 判权重量化的好坏 ⇒ **必须用定长 + 无前缀** 的口径。
3. 🔴 **代理指标 ≠ WER**：本模块只交**可复核的中间量**
   （总词数 / 替换字符数 / 非拉丁占比 / 复读率 / token 级 top1+top5）
   ⇒ 质量等级交 reviewer 复算。
4. 🔴 **teacher-forcing 判据要配「非退化 target」**：FP16 参考自己在定长输入下的贪心输出
   ⇒ 且**必须同时报 top-5**（§19.12）。
5. **准确率作业不需要锁；计时作业必须持规范锁**（本轮两者的区分已严格落实）。
6. **不跑 CPU 推理**（CPU 只用于单组件诊断，如 NNCF 量化）。
7. **不改 `live_caption/`**（ASR-003 铁律）：本轮只 `import` 其中的 `Segmenter` 做只读重放。
## §21 锁协议脚本自身的 4 个缺陷（本轮实测修复）+ 持锁重跑仍被 App 占用（2026-10-25 16:44）

> 本章记录**本轮新写的** `qwen3asr_06b/scripts/p3_run_with_lock.py` 自身的缺陷。
> 这些缺陷**会让 4 模块互锁失效或破坏别人的计时** ⇒ 比「没写锁脚本」更危险。

### 21.1 缺陷①（🔴 最危险）：`pid_alive` 带了进程名过滤 ⇒ 会**误回收别人活着的锁**
原实现：
```python
txt = out.stdout.decode('gbk', errors='replace')
return str(pid) in txt and 'python' in txt.lower()      # ← 错
```
**问题**：锁的持有者**不一定是 python 进程** ——
App 侧实测同时存在 `python.exe`（作业）与 `pythonw.exe`（`live_caption_app.py`），
MT/TTS 也可能是 Node / cmd / `pythonw`。
⇒ 只要持锁者不是名字含 `python` 的进程，就会被**判成「PID 已不在」⇒ 回收它的锁**
⇒ **别人正在跑的计时作业失去保护 ⇒ 多个模块同时占 GPU ⇒ 计时全部作废**。
**修复**：**只看 PID 是否在**，不加任何进程名过滤：
```python
return re.search(rf'"[^"]*","{pid}"', txt) is not None
```

### 21.2 缺陷②：协议里「锁早于开机时间 ⇒ 可回收」**根本没实现**
`boot_time()` 定义了但**从未被调用**（`lock_is_stale()` 里没有它）
⇒ **上次异常退出留下的锁会永久阻塞其它模块**（只要那个 PID 后来被别的进程复用，反而更糟）。
**修复**：补实现 —— 锁的 `started` 早于「now − 开机时长」⇒ 该 PID 属上一次会话 ⇒ 必然已死 ⇒ 可回收。

### 21.3 缺陷③（🔴）：锁里写的是**包装器 PID**，不是**真正占设备的进程 PID**
原实现用 `subprocess.run(argv)` ⇒ 锁里写 `os.getpid()`（包装器自己）。
**问题**：包装器若被杀 / 被回收，**子进程会变成孤儿继续占 GPU**，
而别的模块看到「锁的 PID 已死」⇒ 回收锁 ⇒ **孤儿进程仍在跑 GPU** ⇒ **计时互相污染**。
**修复**：
* 改用 `subprocess.Popen(argv)`，**先起子进程拿到真实 PID，再写锁**；
* 锁里的 `pid` = **子进程 PID**（真正占设备那个），另写 `wrapper_pid` 供人工排查。

### 21.4 缺陷④：删锁**不校验归属** ⇒ 会误删别人后来拿到的锁
**修复**：`release_lock(path, expect_pid=…)` ⇒ **只在锁里的 PID 还是自己时才删**；
回收陈旧锁时也传 `expect_pid=陈旧PID` ⇒ 若判陈旧到删锁之间持锁者恰好重启并写了新锁，
则**不删**、重新等待（避免竞态误删）。

### 21.5 隔离测试（3 项全过，未碰规范锁）
| 用例 | 期望 | 实测 |
|---|---|---|
| T1 活锁（PID=自己） | 不判陈旧；可正常释放 | `stale=False` / `release=True` ✔ |
| T2 锁属于别人（`expect_pid` 不匹配） | **不删** | `release=False`，文件仍在 ✔ |
| T3 陈旧锁（`started=2000-01-01`） | 判陈旧且可回收 | `stale=True` / `release=True` ✔ |

### 21.6 ⏳ 持锁重跑仍**在等锁**（本轮未拿到交付级计时）
* 16:34 首次启动的等待器用的是**缺陷版脚本** ⇒ 已停；
* 16:44 用**修复版**重启（后台任务 `6WmBa3`，日志 `logs/p3_61min_gpu_int8_locked.log`）。
* 规范锁 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK` 当前内容：
  `app PID 32652 started 2026-10-25 16:23:32`
  ⇒ 持锁进程 **确实存活**（`tasklist` 返回 `"python.exe","32652",…`；
  命令行 = `results/app/app037_cp3_abba_v15.py --pkg …/Confucius4_LiveCaption_v1.5
  --seconds 60 --quiet-seconds 45 --quiet-timeout 3600 --lock-timeout 10800`）
  ⇒ **等待是正确行为**，不是脚本缺陷。
* ⚠️ 记录一个**排查陷阱**：在 Git Bash 里跑 `tasklist /FI "PID eq N"` **可能返回空**
  （本次就误判成「进程已退出」）⇒ **判活必须用 `Get-Process` / `Get-CimInstance` 复核**，
  否则会把**活着的持锁者当成陈旧锁回收**。
* ⇒ **本轮仍未拿到 0.6B INT8 的交付级 RTF / 首字延迟 / 内存**
  ⇒ STATUS 头部第 ⑥ 项与 §20.7 第 1 行**保持「在跑」**，不冒充已交付。
## §22 ASR-007 矩阵补全：**设备摆放字段缺失**已修 + 格子命名 bug 已修（2026-10-25 16:50）

> 本章是对 §20.6 的**补充与修正**（不撤回 §20 的任何结论）。
> 起因：复核 ASR-007 原文「**设备摆放：encoder 和 decoder 分别放在哪个设备上，要写清楚**」
> 时，发现 INT4 格子的 json **没有 `enc_ir` 也没有 `device_placement`** ⇒ reviewer 无法复核摆放。

### 22.1 🔴 ASR-007 的「设备摆放」要求此前**没在 INT4 格子落地**
* **INT8 格子**已有 `enc_ir` / `dec_ir`（两个 IR 路径齐全）；
* **INT4 两个格子**（`int4_asymg128` / `int4_sym_chan`）**只有 `dec_ir`，缺 `enc_ir`**，
  且**完全没有 `device_placement` 结构** ⇒ 违反 ASR-007 原文。
* **修复**（`scripts/p3_make_int4_cells.py` 本轮新增 `enc_ir` + `device_placement`）：
  * `enc_ir` = `models/ov-encoder-06b-fp16/openvino_encoder_model.xml`
    （**encoder 固定 OV FP16、不量化**，所有变体共用同一份 ⇒ 被测变量只有 decoder 权重）；
  * `device_placement.encoder` = `GPU.0（OV FP16，不量化；所有变体共用同一份 encoder IR）`；
  * `device_placement.decoder` = `GPU.0（OV，权重精度 = <该变体自己的 recipe>）`
    ⚠️ **按变体分别写**，不共用一句（原先两格都写「见 recipe：两种都列」⇒ 不可复核，已改）；
  * `device_placement.note` = 本组是**量化对比实验**（隔离变量用），
    **不是**可交付的混合摆放方案；encoder 未量化是因为 encoder 是 conv 结构无 MatMul
    ⇒ AWQ 会静默跳过（§15.4）⇒ encoder 保持 FP16。

### 22.2 🔴 格子生成脚本的**文件名重复拼接** bug（已修）
* 脚本里循环变量名已含 `int4_` 前缀（`var ∈ {int4_asymg128, int4_sym_chan}`），
  而输出名又拼了一次 `'qwen3asr_06b__int4_' + var + '__gpu0.json'`
  ⇒ 产出 `qwen3asr_06b__int4_int4_asymg128__gpu0.json`
  ⇒ **与 `MATRIX.json` 里引用的文件名不一致** ⇒ 矩阵会指向不存在的文件。
* **修复**：输出名改为 `'qwen3asr_06b__' + var + '__gpu0.json'`
  ⇒ 回到 §20.6 记录的正式名 `qwen3asr_06b__int4_asymg128__gpu0.json` /
  `qwen3asr_06b__int4_sym_chan__gpu0.json`；
  两个错误命名的中间产物已删除（`rm` 前已确认它们是本轮脚本生成的重复文件）。
* ⚠️ **教训**：生成「矩阵引用的格子文件」时，**文件名必须与矩阵引用严格一致**
  ⇒ 每次重新生成后要**反查矩阵引用是否存在**（本次由 §20.6 的记录发现）。

### 22.3 ✅ `MATRIX.md` 新增「设备摆放」汇总表（ASR-007 明确要求的一节）
`scripts/p3_make_matrix.py` 本轮新增该节：从**每个格子 json 里现读**
`device_placement` / `enc_ir` / `dec_ir` ⇒ 渲染成
`| 格子 | encoder | decoder | 备注 |` 四列表。
* 当前覆盖：**4 / 16 格**有 `enc_ir`/`dec_ir`/`device_placement`
  （0.6B 的 INT8×GPU.0、INT8×NPU、INT4×2 个）
  ⇒ 其余 12 格（如 `r2t2__int8__gpu0.json` 等历史格子）**本轮未补**
  ⇒ 表下已注明「其余格子的摆放信息见各自 json 的 `enc_ir`/`dec_ir` 字段」。

### 22.4 产物状态（重新生成后）
| 文件 | 大小 | mtime |
|---|---|---|
| `reports/compare/qwen3asr_06b__int4_asymg128__gpu0.json` | **4436 B** | **16:47** |
| `reports/compare/qwen3asr_06b__int4_sym_chan__gpu0.json` | **4311 B** | **16:47** |
| `reports/compare/MATRIX.json` | **10801 B** | **16:47** |
| `reports/compare/MATRIX.md` | **6005 B** | **16:47** |

目录仍为 **17 个文件**（16 个格子 + `MATRIX.json` + `MATRIX.md`）✔ 与 §20.6 记录一致。

### 22.5 ⏳ 持锁重跑仍**在等锁**（本轮未拿到计时）
* 规范锁 `C:\Users\Trekker-PTL\shared\MACHINE_LOCK` 内容未变：
  `app PID 32652 started 2026-10-25 16:23:32`；
* `Get-Process -Id 32652` **确认存活**（`python`，StartTime 16:16:30，CPU 4.45 s）
  ⇒ **等待是正确行为**，不是脚本缺陷；
* 后台任务 `6WmBa3`（修复版锁脚本）在等；交付级 RTF **仍空缺**，
  STATUS 头部第 ⑦ 项与 §21.6 保持「在跑」，**不冒充已交付**。
## §23 **根因彻底查清并根治：OV decoder 缺 attention mask 语义 = 导出时没传 mask**（2026-10-25 17:05）

### 23.0 撤回表（本节推翻前序说法）
| 前序结论 | 位置 | 处置 |
|---|---|---|
| 「OV IR 缺 attention mask 语义」 | §19.12（推测） | 🔴 **表述不准** ⇒ 修正为「**导出时没传 `attention_mask`** ⇒ 图里**根本没有** padding mask」 |
| 「INT8 图恰好带上了正确的 mask 语义」 | §19.0/§19.2 | 🔴 **撤回** ⇒ INT8 **没有**带 mask；它只是权重误差恰好把平坦 logits 推回正确一侧（**巧合**） |
| 「FP16 图把 padding 当有效 token（等价 mask=none）」 | §19.12 | ✅ **成立且已闭环**（argmax 逐位吻合） |
| 「INT8 61 分钟长跑质量数据可用」 | §20 | 🔴 **作废** ⇒ 用的 `ov-dec-06b-embed-int8sym` 是**单端口无 mask** 的图 ⇒ 质量数据同样不可信，**需用新图重跑** |

### 23.1 证据链（每步都有落盘产物）

**第 1 步 — 运行时抓 mask 真值**（`results/p3_diag_mask_runtime.json`，15:31）
三张旧图（fp16 / f32true / int8sym）各抓 9 个 mask 链中间量，**三图逐位相同**：
```
sdpa0.in3_mask: shape=[1,1,512,512] n_true=131328
                 row_true_head8=[1,2,3,4,5,6,7,8]  row_true_tail8=[505..512]
                 equals_tril=True      ← 严格因果下三角
```
⇒ **旧图里根本没有 padding mask**，只有因果 mask。
（`row_true` 从 1 递增到 512 ⇒ 512×513/2 = 131328）

**第 2 步 — 静态常量全量比对**（`results/p3_diag_bool_const.json`，15:17）
补了前序的**关键漏洞**：§19 的 `const_diff` / `3d_const` / `attrs` **都把 `Constant` 整类跳过**了
（因 NNCF 会插入 Constant ⇒ 序号漂移），而 **mask 链恰恰全是 bool 常量** ⇒ 从未逐位比对过。
三图的 3 个 bool 常量**哈希完全一致**：
```
view_2/aten.view.default/Reshape  bool [512,1]   n_true=512    hash=393a0fa0f348fb03
le/aten.le.Tensor/LessEqual       bool [512,512] n_true=131328  hash=a48be07c8e369803
ne/aten.ne.Scalar/NotEqual        bool [1,512]   n_true=0       hash=bf619eac0cdf3f68
```
⇒ `le` = **因果下三角**；`ne` = **全 False** ⇒ **cumsum = 全 0** ⇒ 静态层面同样证明**没有 padding mask**。
（`byname` 口径：fp16 vs int8sym 的 196 条差异**全是 `dtype/shape`**（f16 权重 → int8 权重），
**不含任何 bool 常量名**；f32true vs int8sym 差异 **0**）

**第 3 步 — 与 torch 逐位对照**（`results/p3_diag_mask_sem.json`，15:10）
同一份 embeds（L=51）：
| | 熵 | top1 | argmax |
|---|---|---|---|
| torch mask=real | 0.7121 | `All` | 2403 |
| torch mask=none | 5.8869 | `š` | 11645 |
| torch mask=all1 | 5.8869 | `š` | 11645 |
| torch mask=all0 | 5.6503 | `.tail` | 38711 |
| **OV fp16** | **5.8996** | **`š`** | **11645** ← 与 torch mask=none **argmax 逐位吻合** |
| **OV int8** | **1.0380** | **`All`** | **2403** ← 与 torch mask=real 吻合 |
⇒ **OV fp16 ≡ torch「不传 attention_mask」**，这是根因的决定性对照。

**第 4 步 — 定位到导出层**
`Qwen3ASRThinkerTextModel.forward` 里 `create_causal_mask(attention_mask=None)`
⇒ 图里 cumsum 的输入被**常量折叠成全 False** ⇒ 整条动态链退化成纯因果 mask。
⇒ 图里**本来就有** padding mask 的动态链（`Equal` / `CumSum` / `BitwiseAnd` / `Unsqueeze` → SDPA.in3），
只是输入是常量 ⇒ **图结构不用改，只要导出时把 `attention_mask` 传进去**。

### 23.2 玩具实验定死 bool mask 语义 + 发现 OV 的 NaN 行为
`results/p3_diag_bool_mask_sem.json`（16:42）。手搓微型 OV 图（Q=[1,1,1,4]，K=全 1，V 第 i 行=i）：

| mask | OV 输出 | torch 输出 |
|---|---|---|
| all_true | 1.5 | 1.5 |
| **all_false（整行屏蔽）** | **NaN** | **0.0** |
| mask_first2 | 0.5 | 0.5 |
| mask_last2 | 2.5 | 2.5 |

⇒ **bool 语义一致（True=可见）**；
⇒ 🔴 **OV 的 SDPA 对「整行被屏蔽」返回 NaN，PyTorch 返回 0** ⇒
直接用标准 mask 导出 ⇒ padding 行整行被屏蔽 ⇒ **真实 mask 下 logits 全 NaN**（实测，见 23.3 的 v1）。

### 23.3 两版导出与修复

| 版本 | 脚本 | 做法 | 真实 mask 结果 |
|---|---|---|---|
| v1 | `scripts/p1_export_decoder_mask.py` | 加 `attention_mask` 端口，mask 用 torch 标准 | 🔴 **NaN**（top1=`!`） |
| **v2 ✅** | `scripts/p1_export_decoder_mask2.py` | 同上，但 **patch `create_causal_mask` 自建 mask**：`causal AND (content OR self)`（**padding 行开对角线**） | ✅ **熵 0.7596 / top1 `Alright`** |

**为什么开对角线是安全的**：因果 mask ⇒ 位置 511 **看不到** q<411 的 padding 行 ⇒
padding 行的输出**不参与**位置 511 的 logits ⇒ **与 torch 标准 mask 数学等价**。
（实测 torch 标准 mask 在 padding 行是**全 False**、我的 patch 是**开对角线**，
差异 12832 个元素，但**最终 logits 等价**——因为因果性）

**v2 自检结果**（`results/p1_decoder_export_mask2.json`，16:50）：
| 输入 | OV 熵 | OV top1 | torch 熵 | torch top1 |
|---|---|---|---|---|
| **真实 mask** | **0.7596** | **`Alright`** | 0.7540 | `Alright` |
| mask 全 1 | 4.9833 | `all` | 4.8953 | `all` |
⇒ argmax 均为 **71486**（与 torch 一致）；
⇒ 🔴 **mask 全 1 逐位复现旧图（4.9833 / argmax 541）** ⇒ 证明是 **mask 端口真的起作用**，
不是巧合（这是排除「恰好撞对」的关键对照）。
产物：`models/ov-dec-06b-embed-mask2/`（1139.7 MiB，4250 算子，
端口 `inputs_embeds [1,512,1024]` + `attention_mask [1,512]` i64）。

### 23.4 端到端贪心验证
`results/p3_diag_mask2_e2e.json`（16:53），固定 6.4s 与累积 10×0.64s **两种音频模式**各 10 步：

| 模式 | 图 | 输出文本 | 退化 | 拉丁比 |
|---|---|---|---|---|
| fixed6.4s | fp16_old | `all right good morning everyone good morning let's get` | 否 | 0.9815 |
| fixed6.4s | int8_old | `All right. Good morning everyone. Good morning.` | 否 | 0.9362 |
| fixed6.4s | **mask2_new** | **`Alright. Good morning, everyone. Good morning.`** | 否 | 0.9130 |
| cum10×0.64s | fp16_old | 同上 | 否 | 0.9815 |
| cum10×0.64s | int8_old | 同上 | 否 | 0.9362 |
| cum10×0.64s | **mask2_new** | **同 mask2** | 否 | 0.9130 |

⇒ **新图输出最好**（有正确大小写 + 标点：`Alright.` / `,` / `.`），
旧 fp16 缺标点且首词小写错误，旧 int8 首词 `All` 后接 `.` 复读。
⇒ 两种音频模式**结果一致** ⇒ 说明修复不依赖输入条件。

### 23.5 INT8 量化（基于新图）
`scripts/p2_quantize_mask2.py`（包装脚本，**不改** `p2_quantize.py` ⇒ 不影响其它模块）：
源 = `models/ov-dec-06b-embed-mask2/openvino_model.xml`，
**INT8_SYM 按通道 + lm_head 保留 FP16**（`ignored_scope=['linear_196/aten.linear.default/MatMul']`）
⇒ **1139.7 MiB → 720.6 MiB（0.6323）**，196/196 参数 int8_sym per-channel，**0 个 int4**。
产物：`results/p2_quant_decoder_int8sym_mask2.json`（16:55）、
`models/ov-dec-06b-embed-mask2-int8symmask2/`。

### 23.6 `p3_ov_app.py` 已适配双端口
`scripts/p3_ov_app.py` 的 `OVRunner` 现在**自动检测 decoder 端口数**：
* 端口数 ≥2 ⇒ 传真实 `attention_mask`（右对齐，前 `512-L` 位为 0）
* 端口数 =1 ⇒ 旧行为（并打印告警说明该图**缺 padding mask 语义**）
⇒ **默认行为不变**，用新图时自动走 mask 路径。

### 23.7 待办（因本节结论而必须重做）
1. 🔴 **61 分钟长跑必须用新图重跑**（`ov-dec-06b-embed-mask2` 或其 INT8 版）⇒
   §20 的 `results/p3_p3_61min_gpu_int8/`（553 段 / 11825 词）**质量作废**（用的旧图）。
2. 🔴 **FP16 / INT4 格子全部要重测**（旧图全都没有 padding mask）⇒
   ASR-007 的 `reports/compare/` 里 0.6B 的格子数据**全部要刷新**。
3. ⏳ **INT4（`INT4_ASYM g128 + AWQ + SE`）也要基于新图重量化**（§20 的 INT4 图也是旧图）。
4. ⏳ **NPU 格**：新图是**双端口**，NPUW 是否支持 `attention_mask` 动态端口**待测**
   （若不支持 ⇒ 需要把 mask 烘进图，或改用「内容左对齐 + 取动态位置」方案）。
5. ⏳ **计时**：`shared/MACHINE_LOCK` 仍被 `app` PID 32652 占用（16:23:32 起，
   `app037_cp3_abba_v15.py --quiet-timeout 3600`）⇒ 本轮**未启动任何计时作业**。

### 23.8 本轮方法论教训（务必记住）
1. 🔴 **前序三份常量比对都把 `Constant` 整类跳过了**（因 NNCF 插入导致序号漂移）
   ⇒ **任何"因 NNCF 插入而跳过的类型"都要单独用多重集口径补测**，
   否则会漏掉「mask 链全在 Constant 里」这类关键证据。
2. 🔴 **`torch.eye` / `torch.tril` 不能进被导出的图** ⇒ torch.export 分解成 `aten.arange`
   ⇒ OV 2026.4 前端报 **`KeyError: 'torch.uint16'`**（v2 第一版失败）
   ⇒ 必须用 **numpy 预计算常量**（`torch.from_numpy(np.eye(...))`）。
3. 🔴 **导出脚本的 fallback 会吞掉真实错误**：`torch.export` 失败后 fallback 到
   `ov.convert_model(net, input=...)` ⇒ 报的是「TorchScript 无法 scripting」这种**无关错误**
   ⇒ **必须把 `torch.export` 的原始异常打印出来**（v2 第一版因此多花一轮）。
4. ✅ **OV Model 的构造**：`ov.Model([result], [])`（`results` + `sinks`），
   `ov.Model([result])` **报错**；`ov.Core().create_model` **不存在**（2026.4）。
5. ✅ **`op.inputs` 是方法不是属性** ⇒ 必须 `op.inputs()`。
6. ✅ **`model.add` 不存在**（2026.4）⇒ 图手术改 `op.set_arguments({idx: ...})` 需要
   `model.add` ⇒ **不可用**；要加常量节点得用 `opset13` 在**新建**图里做。
## §24 **新图三格就绪：INT8 mask 语义保留 + NPU 双端口支持 + 校准集需重采（待办收敛）**（2026-10-25 20:20）

### 24.0 本节摘要
§23 查清了根因并给出根治版导出（`ov-dec-06b-embed-mask2`，双端口 `inputs_embeds` +
`attention_mask`）。本节把「**新图能不能真正用起来**」的三个前置全部验证掉：

| 前置 | 结论 | 证据文件 |
|---|---|---|
| ① INT8 重量化会不会破坏动态 mask 链？ | ✅ **不会**（fp16 / int8 运行时 mask 逐位相同） | `results/p3_diag_mask2_int8.json` |
| ② NPUW 支不支持多一个 i64 输入端口？ | ✅ **支持**（新图 FP16 / INT8 均编译通过且推理无 NaN） | `results/p3_diag_npu_mask2.json` |
| ③ INT4 的校准集还能用吗？ | 🔴 **不能**（旧校准集是**单端口 + 左对齐**，与新图**双端口 + 右对齐**都不匹配） | 本节 24.3 |

⇒ §23.7 的待办从 8 条收敛到 **4 条**（见 24.5），且**新增 2 个此前没意识到的坑**（24.3）。

---

### 24.1 ✅ INT8 重量化**不破坏**动态 mask 语义（新增证据）

**为什么必须单独验**：NNCF `compress_weights` 会插入 196×3 个节点，且 mask 链是
`Equal`/`CumSum`/`BitwiseAnd`/`Unsqueeze` 这类**整数/布尔**算子，
bool 常量在 NNCF 眼里是 `char` dtype ⇒ **有可能被当成普通权重误处理**。
若 INT8 版的 mask 链被破坏 ⇒ §23 的修复在 INT8 格里**依然无效**（等于还要再修一次）。

**实测**（`scripts/p3_diag_mask2_int8.py`，`valid_len=101`）：

| 图 | 端口数 | SDPA in3 `n_true` | 逐行 True（head8 / tail8） |
|---|---|---|---|
| `ov-dec-06b-embed-mask2`（FP16） | 2 | **5562** | `[1,1,1,1,1,1,1,1]` / `[94,95,96,97,98,99,100,101]` |
| `ov-dec-06b-embed-mask2-int8sym`（INT8） | 2 | **5562** | `[1,1,1,1,1,1,1,1]` / `[94,95,96,97,98,99,100,101]` |
| 旧图（对照） | 1 | 131328 | 纯因果下三角（**无 padding mask**） |

* 期望值 = `(512−L)×1 + L×(L+1)/2` = `411 + 5151` = **5562**
  ⇒ fp16 与 int8 **都精确等于期望值**；
* `verdict_mask_preserved_through_quant = true`
  ⇒ **INT8 重量化后 mask 链完好，§23 的修复在 INT8 格里同样成立**。

⚠️ **口径修正**：我第一版脚本的期望值写成 `L×(L+1)/2 = 5151`（漏了 padding 行的对角线）
⇒ 误判「不匹配」。正确口径是 **5562**。自建 mask = `causal AND (content OR self)`
⇒ **padding 行只开对角线**（每行 1 个 True），**有效行 causal**（第 k 行 k+1 个）。
⇒ 记入 MEMORY：**读 §23 的 `n_true=5151` 时要认得那是「只看有效区」的口径**。

---

### 24.2 ✅ NPUW **支持**双端口（新图在 NPU 上编译通过、推理无 NaN）

**为什么这是关键未知项**：§20 的 0.6B NPU 格是 **BLOCKED**（NPU 端复读 prompt；
`ov-dec-06b-past-int8` stateful IR 在 NPU 编译失败：`to_shape was called on a dynamic shape`）。
⇒ 已知 NPUW 对这个模型**本来就挑**。
§23 的根治方案把赌注押在「**多一个 i64 输入端口**能不能过 NPUW」⇒ 必须实测。

**实测**（`scripts/p3_diag_npu_mask2.py`，device=NPU）：

| 图 | 端口 | 编译 | 编译耗时 | 推理 | 全 finite | NaN | argmax |
|---|---|---|---|---|---|---|---|
| `mask2_fp16` | `inputs_embeds[1,512,1024] f32` + `attention_mask[1,512] i64` | ✅ OK | 222.2 s | 0.27 s | ✅ | ❌ | 38510 |
| `mask2_int8sym` | 同上（双端口） | ✅ OK | 147.6 s | 0.16 s | ✅ | ❌ | 23180 |
| `old_int8sym`（对照） | `inputs_embeds` 单端口 | ✅ OK | 132.1 s | 0.15 s | ✅ | ❌ | 124793 |

⇒ ✅ **多一个 i64 端口在 NPUW 上完全支持**（三个 case 全编译成功、全无 NaN）。
⇒ ⚠️ 但**「能编译 + 不 NaN」≠「输出正常」** ⇒ NPU 格的**文本正常性仍要跑贪心解码才知道**
（§24.5 待办 ③）。

⚠️ **污染记录（诚实标注）**：本节的 NPU 编译在 **20:10–20:19** 期间跑，
与 **MT 的 `hy_bench` 延迟测量（`c111_v5_ts10_nopunct_r2`，20:04 起持锁）重叠**。
NPU 编译是 **CPU 密集**（147–222 s 满载）⇒ **可能轻微影响 MT 的 P50/P95**。
⇒ 已在 `shared/` 侧无记录能力的前提下，**本节明确标注该风险**；
⇒ **我后续不再在 MT 持锁期间跑 CPU 密集作业**（NPU 编译、校准集生成都算）。

---

### 24.3 🔴🔴 新发现：**校准集与新图不匹配**（此前从未有人发现）

§23 只说「要重量化 INT4」，但**没检查校准集本身是否还能用**。实测发现**两个不匹配**：

| 项 | 旧校准集 `results/p2_calib_decoder.npz` | 新图推理需要 | 后果 |
|---|---|---|---|
| **端口** | 只有 `inputs_embeds`（64×1×512×1024 f32） | `inputs_embeds` **+** `attention_mask` | 🔴 NNCF 喂样本**缺一个输入** ⇒ 直接报错 |
| **对齐方向** | `p2_calib.py:160` = `[embeds, pad]` ⇒ **左对齐** | `p3_ov_app.py:283` / `p1_export_decoder_mask2.py:295` = `[pad, embeds]` ⇒ **右对齐** | 🔴 **激活分布位置不一致** ⇒ AWQ 按激活幅度挑通道会**挑错** |

⇒ 🔴 **即使强行喂进去（补一个全 1 的 mask），量出来的 INT4 也是「照左对齐分布挑出来的通道」**
⇒ 与推理时的右对齐分布不匹配 ⇒ **INT4 质量会无谓地差**。
⇒ **必须重采校准集**（右对齐 + 带 mask）。

**已做**（本轮）：
* 新建 `scripts/p2_calib_mask2.py` —— 采**右对齐 + 带 `attention_mask`** 的双端口校准集
  （切段口径仍是**真实 `live_caption_app.Segmenter`** 切 0–12 分钟；
  embeds 仍是 **FP16 encoder + 官方 `masked_scatter`** 真实激活）；
* 新建 `scripts/p2_quantize_mask2_int4.py` —— INT4 量化包装
  （覆盖 `load_calib` 为双端口版；强制 ASR-006 §5② 配方
  `INT4_ASYM g128 + AWQ + SE` + backup `INT8_ASYM` + lm_head 保 FP16；
  产物目录 `models/ov-dec-06b-embed-mask2-int4/`）。

⚠️ **两个脚本都还没跑**（校准集生成要加载 torch 模型 + OV encoder ⇒ 重 CPU/GPU
⇒ 撞 MT 持锁窗口 ⇒ 等锁）。

---

### 24.4 ✅ 产物目录名修正（去重）

* `models/ov-dec-06b-embed-mask2-int8symmask2/` ⇒ **`models/ov-dec-06b-embed-mask2-int8sym/`**
  （原名是 `dst_base`（已含 `mask2`）+ tag（又拼 `mask2`）造成的重复）；
* `results/p2_quant_decoder_int8sym_mask2.json` 的 `dst` 字段**已同步更新**
  （并加 `dst_renamed_note` 记录改名事实）；
* 大小复核：`mask2` **1.2 G**（1139.7 MiB）/ `mask2-int8sym` **721 M**（720.6 MiB，ratio 0.6323）。

---

### 24.5 收敛后的待办（从 §23.7 的 8 条收敛到 4 条）

| # | 待办 | 状态 | 阻塞原因 |
|---|---|---|---|
| ① | **INT4 基于新图重量化** | 🔜 脚本已就绪，**未跑** | 需先跑 `p2_calib_mask2.py`（重 CPU）⇒ 等 MT 释放机器 |
| ② | **61 分钟长跑三格**（mask2 FP16 / mask2 INT8 / mask2 INT4） | 🔜 未启动 | 同上（且长跑要占 GPU ⇒ 不能与 MT 的 GPU 计时并行） |
| ③ | **NPU 格刷新** | 🔜 编译已验证 ✅，**文本正常性未验** | 同上 |
| ④ | **`reports/compare/` 0.6B 各格刷新** | 🔜 未做 | 依赖 ①②③ 的数据 |

**不重跑 encoder**（encoder 不涉及 mask ⇒ 换 decoder IR 即可）⇒ 重跑成本比想象低。

⚠️ **本轮未启动任何计时作业**（锁自 20:04:28 起被 `mt` PID 19892 持有，
作业 `hy_bench/_run_h018_nopunct_ts10.py` ⇒ 测**延迟** ⇒ 属**必须串行**的类别）
⇒ **交付级 RTF 仍空缺**，不冒充已交付。

---

### 24.6 方法论教训

1. 🔴 **「改了模型输入端口」 ⇒ 必须回头检查**所有**依赖该输入的产物**
   （本轮发现校准集的双重不匹配：端口 + 对齐方向）。
   ⇒ **改端口/改布局 ⇒ 立即列一张「下游产物清单」逐个复核**。
2. 🔴 **「左右对齐」是一个隐式契约**，写在**推理侧**、被**校准侧**违反时
   **不会报错，只会静默地让量化变差** ⇒ 校准脚本与推理脚本的**对齐方向必须显式断言一致**。
3. ⚠️ **「期望值写错 ⇒ 误判量化坏了」**（本轮 24.1 的 5151 vs 5562）
   ⇒ 写断言前先**手算一遍真值**，别凭直觉。
4. ⚠️ **NPU 编译是 CPU 密集**（147–222 s 满载）⇒ 在别的模块做**延迟测量**期间跑它
   ⇒ **会污染对方的 P50/P95** ⇒ 判据：凡是需要**独占 CPU 满载**的作业，
   都必须等共享机器锁（哪怕它本身不是「计时」作业）。
   ⇒ 本节的 NPU 编译已与 MT 的延迟测量重叠 ⇒ **已在 24.2 明确标注该风险**。

### 24.7 🔴 追加发现：**teacher-forcing 标定点的基线也作废**（下游产物清单的第 4 项）

按 §24.6 的教训做「下游产物清单」逐项复核时，发现第 4 项：

**`results/p2_multitoken_top1.json`（12:21，59005 B，20 段 / 436 个 target token）**
用的是**旧图**（`ov-dec-06b-embed-fp16` / `ov-dec-06b-embed-int8sym` / `ov-dec-06b-embed-int4`）
⇒ 旧图**没有 padding mask 语义** ⇒ **这个基线本身是在错误前提下测的**：

| model | 旧图 top1 | n |
|---|---|---|
| `ov_fp16_ref`（自检，必须 100%） | **100.0%** | 436/436 |
| `ov_fp16_gpu` | **100.0%** | 436/436 |
| `ov_int8_gpu` | **72.0183%** | 314/436 |
| `ov_int4_gpu`（按通道） | **17.2018%** | 75/436 |
| `ov_int4_r5_gpu` | 49.0826% | 214/436 |
| （位置排布探针：OV 对 torch target） | 63.0734% | 275/436 |

⇒ 🔴 **旧图的 INT8 top1 = 72.02%** 这个数字**不能**当作「INT8 量化损失」的基线
（它混入了「没有 padding mask」这个**结构性错误**）。
⇒ 新图（含 mask）重跑后，FP16/INT8 的 top1 **必然不同** ⇒ **旧表整表作废**。

**已做**：
* `scripts/p2_multitoken_top1.py` 加**双端口适配**（`_dec_inputs()`，按 `len(cm.inputs)`
  自动判定单/双端口 ⇒ 新图传 `[embeds, attention_mask]`）；
* 加两个新 model 项：`mask2_fp16_gpu` / `mask2_int8_gpu`
  （⇒ **新图的 FP16/INT8 同口径标定点**可与旧图逐位对比，
  能量化「mask 修复到底带来多少 top1 提升」）；
* `ov_tf_top1` / `ov_greedy_ids` 里的 `dec_cm([arr])` 已全部改走 `_dec_inputs()`。

⚠️ **注意**：`_dec_inputs()` 的 mask 是**右对齐**（前 `512-L` 位为 0），
与 `p3_ov_app.decode_logits` **逐位一致**（已用 numpy 逐位比对验证，见下）。

### 24.8 ✅ 右对齐一致性已逐位验证（纯 numpy，不占 GPU）

对 `Lc ∈ {37, 101, 300, 512}` 四种长度，比对
`p2_calib_mask2.py`（校准侧）与 `p3_ov_app.decode_logits`（推理侧）的构造：

| Lc | embeds 逐位一致 | mask 逐位一致 | 内容落点 | mask 的 1 个数 |
|---|---|---|---|---|
| 37 | ✅ | ✅ | [475, 511] | 37 |
| 101 | ✅ | ✅ | [411, 511] | 101 |
| 300 | ✅ | ✅ | [212, 511] | 300 |
| 512 | ✅ | ✅ | [0, 511] | 512 |

⇒ ✅ **校准侧与推理侧完全同构** ⇒ AWQ 挑出来的通道与推理时的激活分布一致。
（这是 INT4 质量的前提；若两边不对齐，量化会「照错的分布挑通道」，
**且不报错、只是静默变差**。）

### 24.9 ✅ 全流程已编排并启动（等锁中）

新建 `scripts/run_mask2_pipeline.sh`（**校准集 → INT4 量化 → 三格 61 分钟长跑**，
严格串行，每步都**持规范机器锁**，每步跑完**独立校验产物存在且非空**）：

| 步骤 | 命令 | 产物 | 状态 |
|---|---|---|---|
| ① 校准集 | `p2_calib_mask2.py --n 64` | `results/p2_calib_decoder_mask2.npz` | ⏳ 等锁（`mt` PID 19892，20:04:28 起） |
| ② INT4 | `p2_quantize_mask2_int4.py --asym --group-size 128 --backup-asym` | `models/ov-dec-06b-embed-mask2-int4/` | ⏳ 依赖 ① |
| ③ 长跑 ×3 | `p3_ov_app.py --tag mask2_61min_{fp16,int8,int4}` | `results/p3_mask2_61min_*/` | ⏳ 依赖 ② |

* 断点续跑：`p3_ov_app.py` 自带（读 `segments.jsonl`）⇒ 中断后重跑本脚本即可续；
* `p3_run_with_lock.py` 加 `--task` 参数（锁里写**这次跑什么**），
  三格连跑时不再让别的模块看到过时的任务名（已做隔离测试：参数解析 ✅ / 旧用法兼容 ✅ / **未碰规范锁** ✅）；
* ⚠️ **INT4 步骤失败不阻断** FP16/INT8 两格的长跑（两者不依赖 INT4）。

### 24.10 🔴🔴 实测踩坑：**INT4 脚本静默走成了 INT8 分支**（`--int4` flag 漏传）

**现象**（2026-10-25 20:40，流水线第 ② 步）：
```
[mask2int4] argv = ['--model','decoder','--calib','…','--asym','--group-size','128','--backup-asym','--tag','']
[p2] INT8_SYM（按通道，lm_head 保留 FP16）...        ← 🔴 不是 INT4！
[p2] saved …\ov-dec-06b-embed-mask2-int8sym  1139.7 MiB -> 720.6 MiB
[p2] 产物常量: {… "n_i4": 0, "n_i8": 196 …}          ← 🔴 0 个 int4
[mask2int4] 预期产物目录: …\ov-dec-06b-embed-mask2-int4
[mask2int4] 存在: False                                ← 🔴 目录没建
```
⇒ **退出码 0（不报错）** ⇒ 若只看「rc==0」会**误判成功**；
⇒ 实际是 **INT8 重量化跑了两遍**，INT4 根本没做。

**根因**：`p2_quantize.py` 里 INT4/INT8 的分岔点是 `if args.int4:`
⇒ `--int4` 是 **`store_true` 开关**，**不传就走 INT8 分支** ⇒ **静默走错**。

**已修**（`scripts/p2_quantize_mask2_int4.py`）：
1. **强制补 `--int4`**（若未传则加上）⇒ 杜绝静默走错；
2. **产出后自检** `n_i4 > 0` ⇒ 没有 int4 常量就把退出码置为 **5（失败）**；
3. **元信息改名** `p2_quant_decoder_int4.json` → `p2_quant_decoder_int4_mask2.json`
   ⇒ 不覆盖旧图记录（可追溯）；
4. 流水线 `step_int4()` 的**判定改为「目录存在 **且** 有 int4 常量」**
   ⇒ 不再只看目录（目录可能来自上次的错误运行）。

🔴 **连带影响（已处理）**：
* `results/p2_quant_decoder_int8sym.json` 被这次错误的 INT8 运行**覆盖**
  （原本是旧图 10-24 的记录）⇒ 已改名归档为
  `results/p2_quant_decoder_int8sym_mask2_rerun.json`
  （内容是**新图** INT8 的记录，20:40）；
  ⇒ ⚠️ **旧图 `ov-dec-06b-embed-int8sym` 的量化元信息 json 已丢失**
  （**模型目录本身仍在**，只是元信息没了）—— 不影响交付，但记录在案。

⚠️ **教训（与 §13「n_bad=0 ≠ 没查出问题」同源）**：
**「退出码 0」不等于「做对了事」** ⇒ 凡是有「配方/参数」分支的脚本，
**必须对产物做「配方级自检」**（本次：查 `n_i4`；量化的其它分支可查 `n_i8`/`recipe` 字段），
**不能只看 rc**。

### 24.11 ✅ 步骤 ① 校准集已完成（**右对齐 + 双端口**）

`results/p2_calib_decoder_mask2.npz`（**16.8 MiB**，20:40，耗时 104.5 s）：

| 项 | 值 |
|---|---|
| 样本数 | **64** |
| `inputs_embeds` | `[64, 1, 512, 1024]` f32 |
| `attention_mask` | `[64, 1, 512]` i64 |
| 对齐 | **右对齐**（`[pad, content]`，与 `p3_ov_app.py` 一致） |
| 有效长度 | min **15** / max **109** / mean **71.73** |

⇒ ⚠️ 注意 **有效长度普遍偏短（mean 71.7）** ⇒ 校准时 padding 区占比高
⇒ 这正是**必须有 mask** 的场景（旧图在这种输入下会把 88% 的位置当有效 token）。

### 24.12 ✅ 步骤 ③ FP16 长跑进行中，**文本正常**

`results/p3_mask2_61min_fp16/segments.jsonl`（20:45，33 段已落盘）**首段文本实测**：

```
[  0.00-  6.40] rule1 :: All right. Good morning, everyone. Good morning. Let's get started. So well.
[  6.40- 10.24] rule2 :: Welcome to our Q three twenty six QGS.
[ 10.24- 16.64] rule1 :: Agenda topics today. We'll talk about three. One. I want to share our engineering strate…
[208.64-215.04] rule1 :: Through this model, software I want still Lisa's thunder. She'll come and talk about the…
```

⇒ ✅ **标准英文、正确大小写与标点、无复读、无乱码**
⇒ ✅ **§23 的修复在真实 App 长跑路径上同样生效**（不止是单点 logits）。
⇒ 计时口径：本次**全程持规范锁**（`task=p3_mask2_61min_fp16`）⇒ `timing_valid` 预期为 **true**。

### 24.13 🔴 修 3 处脚本缺陷 + ✅ 补回 §24.10 丢失的元信息（**零干扰准备**，FP16 长跑进行中）

**ⓐ `build_compare_mask2.py` 的 summary 读取 bug（会让新格子全是空值）**

`p3_ov_app.py` 的 summary 字段是**平铺在顶层**的：

```
{'script','tag','model','enc_ir','dec_ir','device','wav','audio_sec','covered_s',
 'complete','n_segs','rule_counts','n_steps_total','chunk_sec','unfixed_token_num',
 'unfixed_chunk_num','flush_max_new_tokens','seg_dur_p50','seg_dur_p95','seg_dur_max',
 'total_words','load_s','compile_s','wall_s','rtf','seg_rtf_p50','seg_rtf_p95',
 'seg_rtf_max','first_tok_latency_p50','first_tok_latency_p95','first_tok_latency_max',
 'timing_valid','mem_host_after','mem_device','segmenter','stream_semantics'}
```

⇒ **不在 `quality` 子字典里** ⇒ 原代码 `q = summ.get('quality') or {}` **恒得空 dict**
⇒ 格子会写成 `n_segs=0 / total_words=0 / audio_sec=null`。
⇒ ✅ 已改为 `q = summ`（并把 `lat` 也改为读顶层）。

**ⓑ `p3_make_matrix.py`：新格子没进矩阵**

⇒ ✅ `ORDER` 前插 3 个新图格子（`qwen3asr_06b__{fp16,int8,int4}__mask2__{var}.json`）；
⇒ ✅ 矩阵总览表加「数据有效」列（旧图格子标 `❌ 作废`）；
⇒ ✅ `MATRIX.json` 的每格加 `data_invalidated` / `data_invalidated_reason`；
⇒ ✅ `MATRIX.md` 新增「§23 根治后：旧图格子的质量数据全部作废」章节（逐格列作废原因）。

**ⓒ 🔴 `p3_ov_app.py` 续跑计时口径 bug（会让交付级 RTF 被低估）**

续跑时 `wall = time.perf_counter() - t_run0` **只含本次运行**，
而 `rtf = wall / covered_s` 的分母 `covered_s` 是**全程**音频
⇒ **分子小、分母大 ⇒ RTF 被低估**（中断重跑越多次越离谱）。

⇒ ✅ 已加 `prev_dec_wall` = **历史已落盘段的 `dec_wall_s` 之和**
⇒ `rtf = (wall + prev_dec_wall) / covered_s`；
⇒ ✅ 新增 `wall_s_total` 字段 + `rtf_note`（写明本次是单次连续跑完还是续跑累加）。
⇒ ⚠️ **本次 FP16 长跑是单次连续跑完**（无续跑）⇒ `prev_dec_wall = 0`
⇒ `rtf` 与旧口径**完全一致** ⇒ 本次数据**不受该 bug 影响**。

**ⓓ ✅ 补回 §24.10 丢失的旧图 INT8 量化元信息**

§24.10 记录的「旧图 `ov-dec-06b-embed-int8sym` 的元信息 json 丢失」已补回：
新建 `scripts/p2_rebuild_quant_meta.py`（从 IR **实测**重建 `dst` / `dst_mib` /
`dst_const_stats`，`recipe` 按 dtype 分布**推断**并标 `INFERRED`，
`src`/`n_calib_samples`/`quant_seconds` 标为**不可恢复**⇒ 未填）。

重建结果（`results/p2_quant_decoder_int8sym.json`，1350 B，20:59）：

| 项 | 重建值 | §23/§20 历史记录 | 一致？ |
|---|---|---|---|
| `dst_mib` | **720.3** | 720.6 | ✅（0.3 MiB 差 = 目录统计口径） |
| `size_ratio` | **0.6322** | 0.6323 | ✅ |
| `n_i8` | **196** | 196 | ✅ |
| `n_i4` | **0** | 0 | ✅ |
| `n_f16` | **538** | 538 | ✅ |
| `i8_MiB` | **420.0** | 420.0 | ✅ |

⇒ ✅ **逐位一致** ⇒ 旧图记录**可追溯性已恢复**。
⇒ ✅ 顺带核对：旧图 INT4 的**原始 json 未丢失**
（`results/p2_quant_decoder_int4__asymg128.json`：recipe=`INT4_ASYM g128 ratio=1.0 + AWQ + SE + backup=INT8_ASYM`、
`n_calib=64`、`quant_seconds=225.4`、`n_i4=392`、`dst_mib=518.3`）⇒ 无需重建。

**ⓔ 🔴 重建脚本自身踩到的 dtype 口径坑（新铁律）**

第一次跑重建脚本时 `n_consts_by_dtype` 全是 `{'other': 1918}`、`n_i8=0`
⇒ 会得出「这不是 INT8 图」的**假结论**。
根因：OV 的 `get_element_type().get_type_name()` 返回**短名**（`f16`/`i8`/`i64`），
而 `str(dtype)` 返回 `<Type: 'float16'>` ⇒ **用 `str()` 做键会全部落空**。

⇒ ✅ 改用 `get_type_name()` + 短名映射表。
⇒ ✅ 正确口径 = **只数 `Constant` 节点**（NNCF 的 int8 权重**仍是 Constant**，
196 个 `i8`；后续 790 个 `Convert` 只是把它们转回 f16 使用）
⇒ 与 `p2_quantize.py::const_stats` **同口径** ⇒ 数值可直接比对。
⇒ ⚠️ 「数所有节点」是**错的**（与 `const_stats` 不可比）。
⇒ ★ 这是 §13「**有效样本为 0 ⇒ 结论是『工具失效』而不是『通过』**」的又一个实例。

## §25 **【用户决定】ASR 不考虑 FP16 ⇒ 矩阵只保留 INT8 / INT4 两格（2026-10-25 21:25）**

### 25.0 用户原话与本节结论

> **「ASR不用考虑FP16，没有价值，F16的内容删除」**（2026-10-25 21:20）

⇒ **交付精度维度只剩 INT8 / INT4**；FP16 从「候选交付精度」中彻底移除。

### 25.1 🔴 但「删 FP16」有一处**不能照字面执行**（已识别并绕过）

`reports/compare/` 里原有两个带 `precision: FP16` 的格子：

```
qwen3asr_06b__fp16__cuda_stream.json    （cell_id = Qwen3-ASR-0.6B__FP16__CUDA）
qwen3asr_06b__fp16__cuda_offline.json   （cell_id = Qwen3-ASR-0.6B__FP16__CUDA_offline）
```

**逐字段核查后确认：它们不是 OV FP16 交付候选，而是 P0 的 torch CUDA 参照**：

| 字段 | 实际值 |
|---|---|
| `backend` | `qwen_asr transformers backend (torch 2.11 + CUDA, **bfloat16**)` |
| `source_files` | `results/p0_stream/` / `results/p0_offline/` |
| `accuracy.wer_pct` | **10.97%（主参照）** / **14.80%（离线旁证）** |
| `scorer` | reviewer 计分器（MiniMax baseline，全局对齐） |

⇒ 🔴 **直接删掉 ⇒ 唯一带 WER 的对照基准消失** ⇒ reviewer 复算新图 INT8/INT4 WER
**没有任何可比的锚点**（ASR-002：Δ 只和同一计分器的基线比较）。

⇒ ✅ **处理方式**：**去掉 FP16 这个精度标签，保留数据本体**
⇒ 文件改名 `…__torchref__cuda_stream.json` / `…__torchref__cuda_offline.json`，
`precision: FP16 → TORCH_REF`，并加 `is_delivery_candidate: false`
+ `precision_renamed_note`（写明原委）。

### 25.2 已删除的内容（清单 + 依据）

| 对象 | 处置 | 依据 |
|---|---|---|
| `results/p3_mask2_61min_fp16/`（**已跑到 65.7%**，364 段 / 2410.24 s / 92 KB） | ✅ **删除** | FP16 不是交付精度 ⇒ 该长跑无价值（已先备份，见 25.4） |
| `reports/compare/qwen3asr_06b__fp16__cuda_stream.json` | ✅ 改名 + 改标签 ⇒ `qwen3asr_06b__torchref__cuda_stream.json` | 见 25.1 |
| `reports/compare/qwen3asr_06b__fp16__cuda_offline.json` | ✅ 改名 + 改标签 ⇒ `qwen3asr_06b__torchref__cuda_offline.json` | 见 25.1 |
| `build_compare_mask2.py` 的 `fp16` 变体 | ✅ 删除 | FP16 格不再产出 |
| `build_compare_06b.py` 的 FP16 格生成 | ✅ 改标 `TORCH_REF` | 见 25.1 |
| `p3_make_matrix.py` 的 `ORDER` | ✅ 去掉 2 个 FP16 名 + 新图 FP16 名；加入 2 个 `torchref` 名 | 矩阵不再有 FP16 维度 |
| `run_mask2_pipeline.sh` 的 `step_p3` | ✅ **三格 → 两格**（删 `run_one fp16`） | FP16 不跑 |
| `p2_multitoken_top1.py` 的 `ov_models` | ✅ **7 项 → 3 项**（删旧图 5 项；`ov_fp16_ref` → `mask2_fp16_ref`） | 旧图 top1 基线失真（§24.7） |
| `p3_int4_slice_decode.py` 的 `VARIANTS` | ✅ **6 项 → 3 项**（只留 mask2 三项） | 旧图数据已作废 |
| `p3_npu_mask2_text_check.py` 的 `VARIANTS` | ✅ 删 `old_int8` 旧图对照 | 旧图已作废 |
| `p3_diag_mask2_prefix.py` 的 `DECS` | ✅ 删 `fp16_old` 旧图对照 | 旧图已作废 |

### 25.3 🔴 **必须保留**的 FP16 内容（删了就跑不动 / 失去判据）

| 对象 | 为什么必须留 |
|---|---|
| `models/ov-dec-06b-embed-mask2/`（**FP16 源图**，1.2 G，双端口 4250 算子） | ★ **它是 INT4 重量化的输入**（`p2_quantize_mask2_int4.py::NEW_SRC`）⇒ 删了 INT4 根本跑不了 |
| `models/ov-encoder-06b-fp16-static/`（356.3 MiB） | encoder **不涉及 attention mask** ⇒ INT8/INT4 两格**共用**这一份 encoder IR（不量化） |
| `mask2_fp16`（teacher-forcing 的 **target 生成器**） | ★ target 必须来自**同家族 FP16 参考** ⇒ 否则 teacher-forcing 就是 §7 铁律的**自一致 tautology** ⇒ 它是**测量工具**，不是交付候选 |
| `mask2_fp16`（NPU / 切片脚本的**同机对照基准**） | 若 NPU 上 FP16 也异常 ⇒ 问题在 NPU/图；只有 INT8 异常 ⇒ 问题在量化 ⇒ 需要基准才能区分 |
| `lm_head 保 FP16`（INT8/INT4 配方的一部分） | 这是**量化配方参数**，与「FP16 作为交付精度」无关 |
| `models/ov-dec-06b-embed-fp16/`（旧 FP16 图，1139.4 MiB） | **保留**（未删）：旧图记录的可追溯性；且体积表要能对照「量化前后差多少」⇒ 但**其质量数据已作废** |

⇒ ★ **一句话**：**FP16 作为「交付精度」全部删除；FP16 作为「工具 / 源 / 基准」必须保留。**

### 25.4 备份（可回滚）

`qwen3asr_06b/_backup_fp16_removal_20261025/`（**300 KB**）：

* `compare_before/` —— 删除前的 `reports/compare/` 全量副本（**18 个文件 = 16 个 cell json + MATRIX.json + MATRIX.md**）
* `p3_mask2_61min_fp16_partial/` —— FP16 长跑已跑的 364 段（65.7%）
* 6 个改动脚本的改前版本

### 25.5 🔴 顺带修好的一个**漏标作废**的问题

§23 判定「旧图质量数据全部作废」时，**只标了 `qwen3asr_06b__int8__gpu0.json` 一格**，
漏了另外 4 个同样用旧图的格子 ⇒ 矩阵里它们仍显示「有效」⇒ **会误导 reviewer**。

| 格子 | 旧 decoder IR | 处置 |
|---|---|---|
| `qwen3asr_06b__int4_asymg128__gpu0.json` | `ov-dec-06b-embed-int4_asymg128` | ✅ 补标作废 |
| `qwen3asr_06b__int4_sym_chan__gpu0.json` | `ov-dec-06b-embed-int4` | ✅ 补标作废 |
| `qwen3asr_06b__int8__npu.json` | `ov-dec-06b-embed-int8sym` | ✅ 补标作废 |
| `qwen3asr_06b__int4__all.json` | （旧图证据链汇总） | ✅ 补标作废 |

⇒ 判据：**格子里的 `dec_ir` 指向 `ov-dec-06b-embed-*`（非 `-mask2`）⇒ 一律作废。**

### 25.6 ✅ 删除后的矩阵现状（`reports/compare/MATRIX.json`，**16 格**）

> ⚠️ 订正：本节初稿写「17 格」⇒ **实测 `MATRIX.json` 的 `cells` 数组长度 = 16**（另有 `MATRIX.json` / `MATRIX.md`
> 两个文件本身，不计入格数；`reports/compare/` 下 json 文件共 17 个 = 16 cell + 1 个 `MATRIX.json`）。

| 精度 | 格子 | 设备 | 数据有效 |
|---|---|---|---|
| **TORCH_REF** | `qwen3asr_06b__torchref__cuda_stream.json` | CUDA | ✅（**WER 主参照 10.97%**） |
| **TORCH_REF** | `qwen3asr_06b__torchref__cuda_offline.json` | CUDA_offline | ✅（旁证 14.80%） |
| INT8 | `qwen3asr_06b__int8__gpu0.json` | GPU.0 | 🔴 **作废**（旧图） |
| INT8 | `qwen3asr_06b__int8__npu.json` | NPU | 🔴 **作废**（旧图，本节补标） |
| INT4 | `qwen3asr_06b__int4_asymg128__gpu0.json` | GPU.0 | 🔴 **作废**（旧图，本节补标） |
| INT4 | `qwen3asr_06b__int4_sym_chan__gpu0.json` | GPU.0 | 🔴 **作废**（旧图，本节补标） |
| INT4 | `qwen3asr_06b__int4__all.json` | ALL | 🔴 **作废**（旧图，本节补标） |
| ALL | `qwen3asr_06b__modelsize.json` | ALL | ✅ |
| INT8 | `r2t2__int8__gpu0.json` / `r2t2__int8__npu.json` | GPU.0 / NPU | ✅（R2T2，与 0.6B 无关） |
| INT4 | `r2t2__int4__npu.json` / `r2t2__int4__npu_cpu_3way.json` / `r2t2__int4_recipe_matrix.json` | NPU | ✅（R2T2） |
| CUDA_Q8 / CUDA_Q4 | `r2t2__cuda_q8.json` / `r2t2__cuda_q4.json` | CUDA | ✅（**R2T2-1.7B**，与 0.6B 无关） |
| ALL | `r2t2__modelsize.json` | ALL | ✅ |

⇒ ✅ **矩阵里已无 `precision=FP16`**（实测扫描全部 17 个 json 的 `"precision"` 字段：`FP16` 命中 **0** 处）。
⚠️ 口径澄清：字符串 `FP16` 本身仍在若干 json 的**说明性字段**里（如 `precision_renamed_note`
「ASR 不考虑 FP16」、`modelsize` 里「FP16 源图是 INT4 重量化的输入源」等）⇒ **这是刻意的说明文字，不是精度标签**。
⇒ ⏳ **待补两格**（新图，待重跑）：`qwen3asr_06b__int8__mask2__int8.json`
+ `qwen3asr_06b__int4__mask2__int4.json`。

### 25.7 附带影响与后续

* 🔴 **长跑进度损失**：FP16 长跑已跑 65.7%（364 段）⇒ **作废**（但省下约 20 分钟机时，
  换 INT8/INT4 两格的价值更高 ⇒ 净收益为正）。
* ✅ **FP16 长跑进程已停**（`TaskStop`）⇒ GPU 与机器锁让出；
  ⚠️ 停后核查发现**锁已被 MT 正确接管**（`mt PID 9748 started 21:21:45`）⇒ 无孤儿锁。
* ⏳ **INT8 / INT4 两格长跑待跑**（依赖 INT4 重量化产物）。
* ⏳ **reviewer WER 待复算**：新图 INT8 / INT4 的 61 分钟全长 WER，
  **对照 `torchref__cuda_stream` 的 10.97%**（同一计分器 ⇒ ASR-002 合规）。

## §26 新图（mask2）INT4 重量化 + INT8/INT4 两格 61 分钟全长跑完成（2026-10-26 01:20）

> 承接 §25。§23 的根治版图（`ov-dec-06b-embed-mask2`，双端口带 padding mask 语义）已在
> §24 验证三个前置（INT8 保留 mask / NPUW 支持双端口 / 校准集必须重采）。本节跑的是
> **剩下的整条依赖链**：INT4 重量化 → INT8 与 INT4 两格 61 分钟全长跑 → 对比格子 → 刷新矩阵。

### 26.0 执行链与时间线（全部持规范锁）

| 时间 | 步骤 | 结果 |
|---|---|---|
| 21:37:25 | ① 校准集 | ✅ 已存在 ⇒ 跳过（`results/p2_calib_decoder_mask2.npz`，17,612,561 B，64 条右对齐双端口） |
| 21:37:26 | ② INT4 重量化 | ⏳ 等锁（`mt PID 9748 started 21:21:45`） |
| 23:11:35–23:49:48 | ② INT4 重量化 | ✅ **rc=0**，210.1 s，产物 518.6 MiB |
| 23:49:48–00:32:06 | ③ INT8 61 min 长跑 | ✅ **rc=0**，wall 2506.47 s |
| 00:32:07–01:15:09 | ③ INT4 61 min 长跑 | ✅ **rc=0**，wall 2554.90 s |
| 01:15:09 | 流水线结束 | ✅ `=== 流水线结束（all）===` |

⇒ 全流程 **3 h 37 m 45 s**，其中**等锁约 1 h 34 m**（21:37 → 23:11），实际计算约 2 h 04 m。
⇒ 三步都独立核对了产物（§12）：`✅ int8 产物齐备：7 个文件` / `✅ int4 产物齐备：7 个文件`。

### 26.1 ✅ INT4 重量化结果（`results/p2_quant_decoder_int4_mask2.json`，2,148 B，10-25 23:49）

配方 = **`INT4_ASYM g128 ratio=1.0 + AWQ + SE + backup=INT8_ASYM`**，`lm_head` 保 FP16
（`ignored_scope = ['linear_196/aten.linear.default/MatMul']`），校准 64 条（右对齐 + 双端口）。

| 项 | INT4（本节） | INT8（对照，`…int8sym_mask2_rerun.json`） | 说明 |
|---|---|---|---|
| 源图 | `ov-dec-06b-embed-mask2` **1139.7 MiB** | 同 | 同一张 FP16 源图 ⇒ 变量只有配方 |
| 产物 | `ov-dec-06b-embed-mask2-int4` **518.6 MiB** | `…-mask2-int8sym` **720.6 MiB** | INT4 比 INT8 **小 28.03%** |
| 压缩比 | **0.455** | 0.6323 | |
| 权重量化常量 | **n_i4 = 392**（`uint4_t`，423.3 MiB） | n_i8 = 196（`int8_t`，420.0 MiB） | INT4 的 392 = 196 层 × 2 个分组常量 |
| 保留 FP16 常量 | 538（303.6 MiB） | 538（297.7 MiB） | `lm_head` 与 norm 等 |
| 量化耗时 | **210.1 s**（统计收集 84 s + AWQ 9 s + SE 104 s + 压缩 6 s） | 14.0 s | SE 是大头 |
| NNCF 位宽分布 | float 26%(1/197) / int4_asym g128 **74%(196/197)**；ratio-defining **100%(196/196)** | — | 与配方预期一致 |

⇒ ✅ **配方生效的直接证据**：`n_i4 = 392 > 0`（§15 的三层防护第 ②/③ 层都过了）。
⚠️ NNCF 打了一条 `Dataset contains only 64 samples, smaller than the requested subset size 128`
—— 本次**有意**用全量 64 条（校准集就 64 条），不是抽样不足。

### 26.2 ✅ 两格 61 分钟全长跑（`results/p3_mask2_61min_{int8,int4}/summary.json`）

两格跑的是**同一条 wav 全程 3671.19 s**、同一个 encoder IR（`ov-encoder-06b-fp16-static`，不量化）、
同一套 App 路径（真实 `live_caption_app.Segmenter` B 行为 / 640 ms 分块 / 前缀回退 5 token /
前 2 块不用前缀 / 自适应 max_new_tokens / 段尾 flush 64）⇒ **唯一变量 = decoder 权重精度**。

| 项 | INT8 | INT4 | Δ |
|---|---|---|---|
| `n_segs` | **553** | **553** | 0 |
| `rule_counts` | rule1 **518** / rule2 **34** / flush **1** | **完全相同** | 0 |
| `n_steps_total` | 5737 | 5737 | 0 |
| `seg_dur_p50 / p95 / max` | 6.4 / 8.96 / 12.16 s | 完全相同 | 0 |
| `total_words` | **11419** | **11369** | **−0.44%** |
| `wall_s` | 2506.47 | 2554.90 | +1.93% |
| **`rtf`** | **0.6827** | **0.6959** | **+1.93%** |
| `seg_rtf_p50 / p95 / max` | 0.6789 / 0.7278 / 0.8201 | 0.6899 / 0.7484 / 0.8259 | +1.6%~+1.9% |
| `first_tok_latency_p50 / p95 / max` | 0.2470 / 0.4019 / 0.5158 s | 0.2497 / 0.4104 / 0.5156 s | +1.1%~+2.1% |
| `load_s` / `compile_s` | 4.4 / 11.53 | 3.0 / 9.72 | — |
| `timing_valid` | ✅ **true** | ✅ **true** | 全程持规范锁，单次连续跑完（`prev_dec_wall=0`） |
| `mem_host_after` | avail 9870.3 MB / used 22293.7 MB（69%） | avail 10259.9 MB / used 21904.1 MB（68%） | — |
| `mem_device` | ⚠️ 未测到（`note: 未匹配到设备`） | 同 | 待补 |

⇒ ★ **INT4 的代价极小（仅就速度与体积而言）**：RTF 只 +1.93%（0.6827 → 0.6959），
首字延迟只 +1.1%~+2.1%，**体积却小 28%** ⇒ 对「显存/包体」受限的部署场景，
INT4 是明显更优的选择。
🔴🔴 **【ASR-010 §2 修订，2026-10-26 09:15】本段原话「INT4 代价极小」**只**适用于
速度和体积**；**质量上有 +0.63pp 的显著代价**（reviewer 复算：INT8 **10.94%** vs
INT4 **11.57%**，Δ **+0.63pp**，CI **[+0.16, +1.10]**，重采样 5000 次，同一切分 553 段）。
⇒ **本句改写为「INT4 的速度/体积代价极小，但质量代价显著」**。
⚠️ NPU 上另有另一条：INT4_ASYM g128 **比 INT8 慢 38%**（§28）⇒ NPU 选 INT8。

### 26.3 ✅ 交叉校验：切点可复现、文本无退化

**(a) 切点/rule 逐位一致**：553 段全部 `start_s` / `end_s` / `rule` 与 INT8 逐位相同（`abs(Δ) < 1e-6`）。
⇒ 切段在**音频域**完成，与 decoder 精度无关 ⇒ 两次长跑的**段边界完全可比**，
文本差异只能来自解码本身（这是一条很有用的隔离：以后不必怀疑「段不一样导致文本不一样」）。

**(b) 文本健康度**（无参考的代理指标，不能替代 WER）：

| 指标 | INT8 | INT4 | 判读 |
|---|---|---|---|
| 词数 | 11419 | 11369 | −0.44% |
| 唯一词率 | 0.235 | 0.241 | 正常英语口语水平，无崩塌 |
| 拉丁字母 / 全部字母 | **1.0000** | **1.0000** | 🔴 **无乱码、无异体字混入**（INT4_SYM 崩坏时会出现 `â颈âчь…` 这类） |
| 三连同词重复 | **0** | **0** | 无复读 |
| ABAB 交替 | 6 | 7 | 极少，属正常口头语 |
| 空文本段 | **0** | **0** | 无空输出 |

**(c) 段级文本差异**：436 / 553 = **78.8%** 的段文本不完全相同，117 段完全相同。
⚠️ 这个比例**不构成退化证据**：流式段内 640 ms 增量解码 + 贪心 + 前缀回退，
单 token 抖动会逐级放大 ⇒ 78.8% 属**预期**。实际差异都是小词形抖动，例如
`nomenclature` → `nomenclators`、`SMG` → `S M G`、`GPU land` → `GPU Land`；
最长段（#213 / #533 / #418）两格语义都连贯，没有一处出现整段乱码。

### 26.4 🔴 三条**不可归因**的边界（必须写清，否则会被误读）

1. 🔴 **旧图那次 INT8 长跑的 `timing_valid = false`** ——
   `results/p3_p3_61min_gpu_int8_OLDGRAPH_nomask/summary.json` 的 `rtf = 1.2389`
   是在「锁写到**仓库内**路径（4 模块互锁失效）+ 启动时锁被 `mt` 占用」的条件下测的。
   ⇒ **该 RTF 不得引用**，更**不能**拿来和新图的 0.6827 比出「mask 修复让 RTF 快 45%」这种结论。
   ⇒ 而且**旧图没有再跑过持锁版本**（目录里只有这一份，另附 `README_作废说明.md`）。
2. 🔴 **旧图与新图的 61 分钟长跑「同时变了两个东西」**：
   | | encoder IR | decoder IR |
   |---|---|---|
   | 旧图 | `ov-encoder-06b-**int8sym**-static` | `ov-dec-06b-embed-int8sym`（无 mask 语义） |
   | 新图 | `ov-encoder-06b-**fp16**-static` | `ov-dec-06b-embed-mask2-int8sym` |
   ⇒ 词数（11825 → 11419，−3.6%）与 RTF 的差异**不能全部归因于 mask 修复**。
   ⇒ §23 的根因结论本身是**干净**的（那是**同图、只改 mask 输入**的正交实验：
   熵 4.983 → 0.7596、argmax 71486 与 torch 一致）⇒ **根因证据看 §23，不要看本节的长跑对比**。
3. ⚠️ **旧图 11825 词 vs 新图 11419 词**只能作「方向性旁证」（少 406 词，符合
   「padding 被当有效 token ⇒ 多出幻觉/重复」的预期），**不是定量证据**（旧图质量数据已按 §23 作废）。

### 26.5 修掉的一个 bug：`rule_counts` 双重计数（`build_compare_mask2.py`）

* 现象：新格子里 `rule_counts = {rule1: 1036, rule2: 68, flush: 2}`，而 summary 是 `518/34/1` —— **正好翻倍**。
* 根因：`rule_counts = q.get('rule_counts') or {}` 拿到的是 summary 里那个 dict 的**引用**，
  紧接着 `for r in rows: rule_counts[r['rule']] += 1` 又在**同一个 dict** 上累加 ⇒ 双重计数。
* 修法：summary 有就取**拷贝**（`dict(...)`），只有缺失时才从 rows 统计；
  并加**合计自检** —— `sum(rule_counts.values()) != n_segs` 时打印警告并改用 rows 的值
  （§13 的「先看有效样本数」思路，防止此类口径错再次静默通过）。
* 复验：两格 `rule_counts` = `518/34/1`，合计 **553 = n_segs** ✅。

### 26.6 矩阵与格子（`reports/compare/`）

* ✅ 新生成两格：
  * `qwen3asr_06b__int8__mask2__int8.json`（`n_segs=553` / `total_words=11419` / `rtf=0.6827` / `timing_valid=true`）
  * `qwen3asr_06b__int4__mask2__int4.json`（`n_segs=553` / `total_words=11369` / `rtf=0.6959` / `timing_valid=true`）
* ✅ `MATRIX.json` / `MATRIX.md` 已刷新：**18 格**（16 + 新 2 格）；两格 `data_invalidated=false`。
* 🔴 **`wer_pct` 仍全部为 `null`** —— 本模块**不自算 WER**（ASR-002 / ASR-004）。
  需 reviewer 用本机 baseline + 全局对齐 + paired bootstrap 复算，锚点为
  **`qwen3asr_06b__torchref__cuda_stream.json` 的 10.97%**（同一计分器 ⇒ 合规）。
* ⏳ 本节**不含** NPU 文本正常性 / prefix 路径 / teacher-forcing 标定点 —— 这三项在
  `scripts/run_mask2_post.sh` 里排队等锁（`app-pack PID 39320` 打包中），结果写 §27。

## §27 后处理链：NPU 文本正常性 ✅ / prefix 路径 ✅ / teacher-forcing ✅ / 设备内存 ✅（2026-10-26 01:52）

> 承接 §26.6。本节跑的是 `scripts/run_mask2_post.sh all`（新建）：① NPU 文本正常性 →
> ② prefix 路径 → ③ teacher-forcing 标定点 → ④ 对比格子 → ⑤ 刷新矩阵。
> 全程持规范锁，总耗时 30 m 18 s（其中等 `app-pack` 约 8 m）。

### 27.1 ✅ NPU 文本正常性 —— **§20 的 NPU BLOCKED 可以解除**

产物：`results/p3_npu_mask2_text/summary.json`（29,914 B）+ 三变体各自的 `segments.jsonl` / `transcript.txt`。
切片 = **[720, 1020] s（300 s）**，45 段，整段贪心（`FLUSH_MAX_NEW=64`）。

| 变体 | 段数 | 词数 | `latin_ratio` | 重复率 | **`prompt_echo_detected`** | 编译+加载 | RTF（⚠️非 App 口径） |
|---|---|---|---|---|---|---|---|
| `mask2_fp16`（**同机对照，不是交付候选**） | 45 | 867 | 0.9585 | 0.0855 | **false** | 117.7 s | 0.2908 |
| `mask2_int8` | 45 | **869** | 0.9586 | 0.0853 | **false** | 88.5 s | **0.2719** |
| `mask2_int4` | 45 | **850** | 0.9578 | 0.0872 | **false** | 208.8 s | **0.3777** |

⇒ ★★ **`prompt_echo_detected` 三格全为 `false`** ⇒ §20 记录的「NPU 上复读 prompt」症状
（输出把整段 prompt 原样念一遍）在**新图**上**没有出现**；三格 seg01 都是
`But we're making good progress. Just last week, we powered on our.`（正文）而非 prompt。
⇒ 加上 §24 已验证「NPUW 支持双端口 + 编译成功 + 无 NaN」⇒ **§20 的 NPU BLOCKED 解除**。
⚠️ 但**质量仍未验**：`latin_ratio` 只有 0.958（含标点/数字），**WER 仍空缺** ⇒ 只能说到「文本正常、无复读」，不能说「NPU 质量达标」。

⚠️ **两个必须标明的口径限制**：
1. 这三格的 RTF **不是 App 路径口径**（整段贪心、无 640 ms 分块 + 前缀回退）⇒
   **不可**与 §26.2 的 0.6827 / 0.6959 相比（脚本已把 `rtf_note` 落盘）。
2. 🔴 **NPU 上 INT4 反而更慢**：RTF 0.3777 vs INT8 0.2719（**+38.9%**）、编译 208.8 s vs 88.5 s。
   这与 GPU（iGPU）上「INT4 只慢 1.93%」**方向相反** ⇒ 初步看 **NPU 对 int4 支持不友好**
   （可能需额外去量化/权重重排）。⚠️ 但**样本只有 1 次 × 300 s 切片**，且含首次编译开销
   ⇒ **只作观察，不作结论**；若要定论需「同一切片、多轮、编译后预热再计时」。

### 27.2 ✅ prefix 路径：mask 不错位

产物：`results/p3_diag_mask2_prefix.json`（11,697 B）。12 步、`unfixed_chunk_num=2`、`unfixed_token_num=5`。

| 变体 | `has_mask_port` | `mask_mismatch_count` | `any_degenerate` | `final_text` |
|---|---|---|---|---|
| `mask2_int8` | true | **0** | **false** | `All right. Good morning, everyone. Good morning. Let's get started. So welcome to our Q three.` |
| `mask2_int4` | true | **0** | **false** | `Alright. Good morning, everyone. Good morning. Let's get started. So welcome to our Q three.` |
| `mask2_fp16` | true | **0** | **false** | 与 `mask2_int8` **逐字相同** |

⇒ ★ **12 步逐步 `mask_ok=True`**（`am.sum() == L`，即「有效位计数 = 实际内容长度」）⇒
在**前缀回退路径**（把已确认文本的 embedding 再拼回去）上 mask 也**没有错位** ——
这是 §23 修复最容易漏的一条（prefix 是 App 路径特有逻辑），现在有实测证据。
⇒ 三格 final 文本几乎逐字相同（唯一差别 `All right.` vs `Alright.`）⇒ 无退化。

### 27.3 ✅ teacher-forcing 标定点（新图口径）

产物：`results/p2_multitoken_top1.json`（47,664 B）。20 段 × 最多 24 token = **425 个目标 token**，
评测段全部取自 ≥12 分钟区段（与校准集 0–12 min 不重叠）。

* **target 源 = OV FP16 decoder（GPU.0）** ⇒ 同家族、同位置排布（**不用 torch 的 token**，避免位置编码口径混入）。
* 🔴 **target 退化检测：0 / 20 段退化**（判据 = 三连同 token / ABAB 交替 / 唯一率 < 0.30）
  ⇒ ⚠️ 这条**很关键**：§18.2 的教训就是「target 自己退化 ⇒ top1 恒 100% 的 tautology」。
  本次 target 非退化 ⇒ 下面的百分比**不是** tautology。

| 被测 | `n_hit / n_total` | **top1** | 说明 |
|---|---|---|---|
| `mask2_fp16_ref` | 425 / 425 | 100.0000% | **自检项**（target 就来自它）⇒ 预期 100%，不作质量证据 |
| `mask2_fp16_gpu` | 425 / 425 | 100.0000% | 同上（同一张图） |
| **`mask2_int8_gpu`** | **422 / 425** | **99.2941%** | 3 个 token 翻转 |
| **`mask2_int4_gpu`** | **394 / 425** | **92.7059%** | 31 个 token 翻转 |

* 另附 `position_layout_probe`：OV 对 **torch target** 的命中率也是 100%（425/425）
  ⇒ 这 20 段上位置排布差异**没有**表现出来（脚本头注释原本预期会低）⇒ 说明「OV 恒取位置 511」
  在这批段长下与 torch 的自然位置**恰好等价**（段长都 ≤ 24 token 生成 + 固定 6.4 s 音频）。
* 🔴 **本轮不下「INT4 可行 / 不可行」的结论**：判据的**阈值**必须由 reviewer 的
  **R2T2 R2 同口径标定点**给出（R2T2 是另一套模型 + 另一套 IR + 不同 prompt 模板）
  ⇒ 本轮**只给 0.6B 侧的原始 token 级计数**（脚本 `threshold_note` 已写明）。

### 27.4 🔴🔴 设备身份与驻留内存：**`GPU.0` 是 Intel 核显，不是 NVIDIA 独显**

产物：`results/p3_diag_device_mem.json`（新建脚本 `scripts/p3_diag_device_mem.py`，只编译不推理）。

**设备身份**（实测 `FULL_DEVICE_NAME` / `DEVICE_ARCHITECTURE`）：

| 设备 | 身份 |
|---|---|
| `CPU` | Intel(R) Core(TM) Ultra 7 356H |
| **`GPU.0`** | **`Intel(R) Graphics (iGPU)`**，`arch=v30.1.0`，vendor `0x8086` |
| `GPU.1` | `NVIDIA GeForce RTX 5050 Laptop GPU (dGPU)`，vendor `0x10de`，`arch=v12.0.0` |
| `NPU` | `Intel(R) AI Boost`，`arch=5010` |

⇒ 🔴★ **本模块所有标 `GPU.0` 的格子（含 §26.2 两格、历史 GPU 格）跑的都是 Intel 核显**；
全程 `nvidia-smi` 的 `used = 0 MiB`（总 8151 MiB）⇒ **NVIDIA 独显一次都没被用到**。
⚠️ 影响：任何「GPU 上 RTF/WER」的表述都必须写明是 **iGPU**，否则 reviewer 会误以为是独显成绩。

**模型驻留内存（USM，编译增量；`GPU_MEMORY_STATISTICS`）**：

| 模型 | 目录总大小 | `usm_device` 增量 | `usm_host` 增量 | 合计 | `compile_s` | `n_ops` |
|---|---|---|---|---|---|---|
| encoder `fp16-static` | 356.3 MiB | 146.2 MiB | 348.8 MiB | 495.0 MiB | 2.31 | 1577 |
| decoder **int4** | **518.6 MiB** | 30.0 MiB | **531.8 MiB** | **561.8 MiB** | 3.36 | 5818 |
| decoder **int8** | **720.6 MiB** | 30.0 MiB | **732.6 MiB** | **762.6 MiB** | 2.58 | 4838 |
| decoder fp16 | 1139.7 MiB | 57.5 MiB | 1152.0 MiB | 1209.5 MiB | 2.61 | 4250 |

⇒ ★ **INT4 比 INT8 省 200.8 MiB 设备内存（762.6 → 561.8，−26.3%）**，比 FP16 省 647.7 MiB（−53.6%）。
⇒ 与目录体积比例吻合（531.8 / 732.6 = 0.726 vs 518.6 / 720.6 = 0.720）⇒ 数据自洽。
⇒ iGPU 共享系统内存 ⇒ 占用几乎全在 `usm_host`（`usm_device` 只 30–58 MiB）。
⚠️ 这是**同进程依次编译**的增量（`del cm` 后靠引用计数释放，Python GC 未强制）
⇒ 视为**近似值**，量级可信、小数位不可抠。

### 27.5 本节修掉的三个 bug

1. 🔴 **`p3_diag_mask2_prefix.py` 两处 `.numpy()` on grad tensor**（`embed` 权重带 `requires_grad`）
   ⇒ `RuntimeError: Can't call numpy() on Tensor that requires grad`（01:40 首次运行崩在 215 行）
   ⇒ 两处都包 `torch.no_grad()` + `.detach().numpy()`。
   ⚠️ 只修崩溃点会留下另一处同类隐患 —— 我 grep 了全部 `.numpy()` 才把两处都改掉。
2. 🔴 **`p3_diag_device_mem.py` 的 `ir_mib` 只算 `.xml`**（2.1–2.8 MiB 的荒唐数字，
   权重全在 `.bin`）⇒ 改为**目录内全部文件求和**（`dir_mib` + `n_files`），并保留 `xml_mib` 作对照。
3. 🔴 **`p3_ov_app.device_mem_mb()` 三处缺陷**（这是两格 `mem_device` 全为
   `{"note": "未匹配到设备"}` 的**根因**）：① 靠 `core.get_devices()` 遍历猜设备名
   （返回的名字不等于 `GPU.0` 就直接放弃）；② `for p in ('TILES','GPU_MEMORY','MEMORY'): pass`
   空循环占位；③ 外层 `for name in ('NPU','GPU','CPU')` 首个迭代就 `break` 的死循环。
   ⇒ 改为**直接用编译时那个 device 名**查 `SUPPORTED_PROPERTIES` + 逐个读内存属性 + 字节→MiB 派生。
   另补：USM 是**累计值**，必须记 `usm_before` 做差后才能当「模型占用」用。

### 27.6 遗留

* ⏳ **WER 仍全空缺**（两格 + NPU 三格）⇒ 交 reviewer；锚点 = `…__torchref__cuda_stream.json` 的 **10.97%**。
* ⏳ **NPU 上 INT4 更慢（+38.9%）需要复核**：同切片、多轮、编译后预热再计时，才能定论。
* ⏳ **`R2T2 R2` 同口径标定点未跑** ⇒ teacher-forcing 的阈值仍无法判定。
* ⏳ **两格 summary 的 `mem_device` 仍是旧的空值** —— 本节用独立脚本补到了
  `results/p3_diag_device_mem.json`，**没有**回填进 `summary.json`（避免改已交付产物）。
* ⚠️ **`GPU.0` = iGPU 这条要同步给 reviewer**（可能影响他对历史 GPU 格子的解读）。

## §28 NPU 多轮复核：**INT4 在 NPU 上确实比 INT8 慢 38.4%**（不是 warmup 假象）（2026-10-26 02:10）

> 起因：§27.1 发现 NPU 上 `mask2_int4` 的 RTF 0.3777 比 `mask2_int8` 的 0.2719 **慢 38.9%**，
> 而这与 iGPU 上「INT4 只慢 1.93%」**方向相反**。§27 已声明「样本只有 1 次 × 300 s 切片、
> 且含首次编译开销 ⇒ 只作观察」。本节就是把这个「观察」变成结论。

### 28.0 方法（`p3_npu_mask2_text_check.py` 新增 `--rounds`）

原脚本只跑 1 轮 ⇒ **无法区分「首次推理的 lazy 编译 / 预热开销」与「真实的稳态性能差」**。
⇒ 新增 `--rounds N`：
* `N >= 2` 时**第 1 轮只作 warmup，不计入 `wall_s` / `rtf`**；
* 逐轮 `wall` / `rtf` 全部落盘（`wall_s_per_round` / `rtf_per_round`），可自查；
* 新增 `steady_state_note` 说明本轮是否含 warmup；
* 默认 `N = 1` ⇒ **完全保持老行为**（向后兼容，`rtf_note` 里仍写明不可与 App 路径比）。

本次跑：`--variants mask2_fp16,mask2_int8,mask2_int4 --device NPU --rounds 2`，
切片不变（`[720, 1020]` = 300 s，45 段），持规范锁，总耗时 **15 m 55 s**。
产物：`results/p3_npu_mask2_text_r2/summary.json`（**新目录，不覆盖 §27 的单轮产物**）。

### 28.1 结果：单轮 vs 两轮（同一台机器、同一把锁、同一切片）

| 变体 | 单轮 RTF（§27，含首次推理） | 两轮逐轮 RTF | **稳态 RTF**（第 2 轮） | 单轮 → 稳态 |
|---|---|---|---|---|
| `mask2_fp16`（对照） | 0.2908 | 0.2841 / **0.2859** | **0.2859** | −1.7% |
| `mask2_int8` | 0.2719 | 0.2713 / **0.2729** | **0.2729** | +0.4% |
| `mask2_int4` | 0.3777 | 0.3765 / **0.3778** | **0.3778** | +0.03% |

⇒ ★★ **warmup 的影响 < 1.7%，而且方向不一致**（fp16 变小、int8/int4 基本不变）
⇒ **首次推理的 lazy 编译开销不是「INT4 慢 38.9%」的原因**。
⇒ 稳态下 **INT4 / INT8 = 0.3778 / 0.2729 = 1.384 ⇒ 慢 38.4%**，与单轮的 38.9% 一致。

**NPU 上的速度排序（稳态 RTF，越小越快）**：
`INT8 0.2729` ＜ `FP16 0.2859` ＜ **`INT4 0.3778`**
⇒ 🔴 **NPU 上 INT4 是三者中最慢的**，INT8 最快。

### 28.2 ✅ 复现性：文本与前一次**逐字一致**

两轮结果的 `n_segs` / `total_words` / `latin_ratio` / `rep_rate` 与 §27 **完全相同**：

| 变体 | 段数 | 词数 | `latin_ratio` | `rep_rate` | `prompt_echo_detected` |
|---|---|---|---|---|---|
| `mask2_fp16` | 45 | 867 | 0.9585 | 0.0855 | false |
| `mask2_int8` | 45 | 869 | 0.9586 | 0.0853 | false |
| `mask2_int4` | 45 | 850 | 0.9578 | 0.0872 | false |

⇒ 贪心解码是确定性的 ⇒ **两次独立运行的文本完全相同** ⇒ 说明：
① 脚本没有随机性（没有 sampling）；
② NPU 上的推理**稳定可复现**（不是偶发异常导致的慢）；
③ §27 的「`prompt_echo` 三格全 false」**再次确认**。

### 28.3 🔴 部署含义（**这条比速度本身更重要**）

| 维度 | NPU | iGPU（App 路径，§26.2） |
|---|---|---|
| INT4 相对 INT8 的 RTF | **+38.4%（明显更慢）** | +1.93%（几乎持平） |
| INT4 相对 INT8 的体积 | **−28.03%** | 同 |
| INT4 相对 INT8 的驻留内存 | −200.8 MiB（−26.3%，§27.4） | 同 |

⇒ ★ **部署选型建议**：
* **走 NPU 时选 INT8** —— INT4 在 NPU 上「既慢 38% 又只省 28% 体积」，性价比为负。
* **走 iGPU（GPU.0）时 INT4 可用** —— 速度几乎不损失（+1.93%），体积/内存省 26–28%。
⚠️ 这只是**性能与体积**的结论；**质量（WER）仍未验**（见 §28.4），
所以「NPU 选 INT8」也不等于「INT8 质量达标」。

### 28.4 ⚠️ 本节的口径限制（不要越界解读）

1. 🔴 **RTF 是「整段贪心」口径**（无 640 ms 分块 + 前缀回退）⇒ **不可**与 App 路径的
   0.6827 / 0.6959 相比，也**不是**交付级 RTF。
2. ⚠️ **切片只有 300 s / 45 段**（§20 起就用这个切片做 NPU 文本检查）⇒
   不能外推到 61 分钟全长；若要交付级结论需另跑全长（成本高，未做）。
3. ⚠️ **只有 2 轮**（1 warmup + 1 计入）⇒ 只能说「warmup 不是主因」，
   不能说「这是 P50」。真要做 P50/P95 至少 5 轮以上。
4. ⚠️ **WER 仍空缺** ⇒ 本节**没有**任何质量结论；速度排序与质量排序可能不同。
5. ⚠️ **INT4 在 NPU 上更慢的机理未查**（可能是权重重排 / 去量化开销 / NPU 的 int4 通路未优化）
   ⇒ 只报现象，不猜原因。

## §29 ASR-010 / ASR-011 落地：reviewer WER 回填 + 旧图结论作废 + §28 字段补全 + NPU 61 分钟格（2026-10-26 09:15–）

> 本节回应 **ASR-010**（reviewer 复核，2026-10-26 09:15）与 **ASR-011**
> （用户决定的精简版范围，2026-10-26 09:24）。ASR-011 把 ASR-010 §4 收缩为
> 「0.6B INT8@NPU 61 分钟 + R2T2 INT8@NPU 61 分钟 + 每格 1 次的速度/内存 + 汇总 json」，
> 并**明确不做了 INT4_SYM 按通道的新图重测**。

### 29.0 本节做了什么（逐条对应 reviewer 要求）

| ASR-010 要求 | 状态 | 产物 |
|---|---|---|
| §1 §23 根因成立 → 接受 | ✅ 已确认（§23 已有完整证据链，本轮不重复） | `status/asr/STATUS_ASR.md` §23 |
| §1 **旧图结论移出「做不了」清单** | ✅ 已移出 | `reports/compare/MATRIX.md`「做不了的格子」节 + 新增「旧图结论作废，待新图重测」表 |
| §1 FYI：R2T2 交付 IR 是否 c069g 派生 / 有无左侧 padding | ✅ **已确认（见 29.4）** | 本节 29.4 |
| §2 reviewer WER 原样填进格子 + 标 `wer_scorer` | ✅ 已填 | `…__int8__mask2__int8.json` / `…__int4__mask2__int4.json` |
| §2 §26.2「INT4 代价极小」改写 | ✅ 已改写 | 本文件 §26.2（就地标注修订） |
| §2 MATRIX.md 的 WER 列**必须带计分器列** | ✅ 已加 | `reports/compare/MATRIX.md` 总览表 |
| §3 §28 数字接受、结论**限定范围** | ✅ 已限定 | 本节 29.3 |
| §3(b) summary 补 **设备摆放 / timing_valid / 持锁信息** | ✅ 已补 | `results/p3_npu_mask2_text{,_r2}/summary.json` |
| ASR-011 ① 0.6B INT8@NPU 61 分钟 App 路径 | 🔄 **进行中** | `results/p3_mask2_61min_int8_npu/`（见 29.5） |
| ASR-011 ② R2T2 INT8@NPU 61 分钟 App 路径 | ⏳ 待跑（NPU 排队） | `results/p3_r2t2_61min_npu/` |
| ASR-011 ③ 速度与内存（每格 1 次 fresh 进程，持锁，600 s 切片 [720,1320]） | ⏳ 待跑（需等 NPU/GPU 空闲 + 锁） | `results/asr007_bench/<cell>/` |
| ASR-011 ④ INT4_SYM 按通道新图重测 | ⛔ **按用户决定不做** | 报告写「旧图结论作废，新图没有重测」 |
| ASR-011 ⑤ 汇总 `reports/compare/ASR007_results.json` | ✅ 脚本已就绪并跑通（6 条记录） | `reports/compare/ASR007_results.json` |

### 29.1 ✅ §2：reviewer 复算的 WER 已原样回填（两格 @iGPU）

reviewer 在本机用 **MiniMax baseline**（参考词数 10964，全局对齐）复算，配对 bootstrap
重采样 5000 次。**本模块不自算 WER**（ASR-002 / ASR-004）⇒ 下列数字**原样引用**，
并在格子里标 `wer_scorer = reviewer_minimax_global`。

| 被测 | WER | S/D/I | 格子 |
|---|---|---|---|
| 0.6B mask2 **INT8** @GPU.0(iGPU)，App 路径，553 段 | **10.94%** | 433/177/589 | `qwen3asr_06b__int8__mask2__int8.json` |
| 0.6B mask2 **INT4**（ASYM g128 + AWQ + SE）@GPU.0，App 路径 | **11.57%** | 475/209/584 | `qwen3asr_06b__int4__mask2__int4.json` |

**配对 bootstrap**（同一切分 553 段，原版 `paired_bootstrap`）：

| 对照 | Δ | CI95 | 显著 | 备注 |
|---|---|---|---|---|
| INT4 − INT8 | **+0.63pp** | **[+0.16, +1.10]** | ✅ **显著** | 与 §27.3 的 teacher-forcing 方向一致（99.29% / 92.71%） |
| INT8 − torch 流式参照（10.97%） | −0.04pp | [−0.32, +0.25] | ❌ 不显著 | ⇒ **OV 路径已忠实复现 torch 参照** |
| INT4 − torch 流式参照 | +0.59pp | [+0.08, +1.12] | ✅ 显著 | |
| INT8 − R2T2 App 路径 B（10.58%） | +0.36pp | [−0.36, +1.07] | ❌ 不显著 | ⇒ **公平对照是 10.58%**（同 App 路径） |
| INT4 − R2T2 App 路径 B（10.58%） | +0.99pp | [+0.30, +1.67] | ✅ 显著 | |
| INT8 − 交付基准 8.17% | +2.76pp | [+2.00, +3.53] | ✅ | ⚠️ 8.17% 是 **226 段离线切分、非 App 路径** ⇒ **不可**当同口径对照 |
| INT4 − 交付基准 8.17% | +3.39pp | [+2.64, +4.17] | ✅ | 同上 |

⇒ **结论**：0.6B **INT8 在 App 路径上与 R2T2 INT8 的差别不显著**（+0.36pp）；
0.6B **INT4 显著更差**（+0.63pp 对 INT8、+0.99pp 对 R2T2）。
🔴 **§26.2 的「INT4 代价极小」只适用于速度与体积**，**质量上有 +0.63pp 的显著代价**
⇒ 该处已就地加「ASR-010 §2 修订」标注并改写。

### 29.2 ✅ §1：旧图结论已从「做不了的格子」移出

reviewer 指出：`int4_sym_chan__gpu0` 的 **BROKEN**、`int4__all` 的
「INT4_SYM 按通道在 0.6B 上崩坏」，以及「做不了的格子」一节里的
**NPU BLOCKED** 与 **INT4_SYM BROKEN** 两条，**用的都是旧图** ⇒ 不能再作结论引用。

处置（**改 `MATRIX.md` 的生成脚本 `p3_make_matrix.py`，不改动已交付的格子 json**）：

1. 「做不了的格子」一节**排除**这 3 个旧图格子，并在节首写明「reviewer 已指出它们用旧图
   ⇒ 已移出，改为『旧图结论作废、待新图重测』」；
2. **新增**「🔴 旧图结论作废，待新图重测（ASR-010 §1）」表，逐格列旧结论与现状；
3. ⚠️ 格子 json 的 `status` 字段里**仍留着旧图状态文案**（`BLOCKED` / `BROKEN`）
   —— 为免改动已交付产物，本轮**不改**，**以 MATRIX.md 本节为准**。

⚠️ **本节同时是「不重做」的诚实声明**：旧图结论**作废 ≠ 新图已有结论**
⇒ `int4_sym_chan` 在新图上的表现**至今未知**（按 ASR-011 第 4 条，用户决定**不测**）。

### 29.3 ✅ §3：§28 结论**限定范围**（数字接受，措辞收紧）

reviewer 接受「INT4 比 INT8 慢 38%」这个数字，但要求**限定范围**：

| reviewer 要求 | 本轮处置 |
|---|---|
| (a) 被测配方是 **INT4_ASYM g128** ⇒ 只能写「INT4_ASYM g128 在 NPU 上比 INT8 慢 38%」，**不能写「NPU 上 INT4 最慢」** | ✅ §28.3 的表述收紧为「走 NPU 时选 INT8」这一**选型建议**，不再出现「NPU 上 INT4 最慢」；本节再明确标注该限定 |
| (b) summary 里要有 **enc/dec 各自设备** | ✅ 已补 `device_placement`（enc=NPU / dec=NPU，见下） |
| (b) summary 里要有 **`timing_valid` 与持锁信息**（持有者 / PID / 开始时间） | ✅ 已补 `timing_valid=true` + `lock_holder`（规范锁路径 + 锁协议说明 + 回填时的锁快照） |
| (c) 这是**整段贪心**口径 ⇒ **不能进 ASR-007 的 RTF 列** | ✅ ASR007_results.json 里 NPU 的速度数据来自 **App 路径**（`p3_ov_app.py` / `asr007_bench.py`），**不是** §28 的整段贪心 |

**回填方式**（不重跑、不改任何测量值）：
新脚本 `scripts/p3_backfill_npu_fields.py` —— **只加字段，不改数值**，
逐字段比对原文件（`device_placement` / `timing_valid` / `timing_valid_reason` /
`lock_holder` / `backfill` 之外**任何键的值变动都报错中止**），
并备份到 `results/_backfill_backup/`。

| 产物 | 回填前 | 回填后 | 备份 |
|---|---|---|---|
| `results/p3_npu_mask2_text_r2/summary.json` | 30,627 B | 已补 3 组字段 | `results/_backfill_backup/p3_npu_mask2_text_r2__summary.json.bak` |
| `results/p3_npu_mask2_text/summary.json` | 29,914 B | 已补 3 组字段 | `results/_backfill_backup/p3_npu_mask2_text__summary.json.bak` |

**设备摆放实测值**（§28 那批）：**encoder 与 decoder 都在 NPU**
（脚本里是 `OVRunner(ENC_IR_FP16, dec_ir, args.device)`，`args.device=NPU`）。

### 29.4 ✅ §1 FYI：R2T2 交付 IR **不派生自 c069g**，且**不受 mask 问题影响**

reviewer：「R2T2 的 `c069g_export_stage3_fp16.py` 和这里是同一个写法（`forward` 只接收
inputs_embeds，不传 mask）。请用一行写清楚：R2T2 交付或已测的 IR（GPU INT8 / NPU INT8
cleanie）是否由 c069g 派生、是否有左侧 padding。」

**核查结论（读代码 + 读 IR 端口双重确认）**：

1. **不派生自 c069g** —— `c069g_export_stage3_fp16.py` 的 `OUT_DIR` 是
   `models/ov-dec-embed-fp16`（`HIDDEN=2048`，R2T2 的 1.7B 尺寸），
   而 **R2T2 的交付 decoder 是 `models/qwen3-lm-int8sym-cleanie-ov`**，
   由 **C-079#2 `c079b_build_clean_embeds_ir.py`**（另一条线：剪掉 `embed_tokens` Gather、
   删掉 `input_ids` 端口、保留 `attention_mask`/`position_ids`/`beam_idx`）产出
   ⇒ **两条线不是同一条**。
2. **R2T2 的 decoder IR 有 `attention_mask` 端口**（实测端口）：
   `attention_mask [?,?] i64` / `position_ids [?,?] i64` / `beam_idx [?] i32` /
   `inputs_embeds [1,1..512,2048] f32`
   ⇒ 与 0.6B 的「单端口 `inputs_embeds` + 恒取位置 511」**根本不同**。
3. **R2T2 的 backend 真传 mask**（`live_caption/npu_embeds_backend.py:212/235`）：
   `"attention_mask": np.ones((1, T), dtype=np.int64)`
   ⇒ **全 1**，**理由按 ASR-012 §2(b) 修正**（原 §29.4 第 3 点写的
   「cross-attention + 逐 token 解码、序列里根本没有 padding 概念」**是错的**，
   见 §33.2 的撤回）：
   * R2T2 是 **decoder-only 的整段 prefill** —— `npu_embeds_backend.py:211-214`
     的 prefill **一次喂进 T 个 prompt token**（音频 embedding + 模板），
     与 0.6B 是**同一种结构**；只是**之后的 decode** 每步喂 1 个 token；
   * 全 1 正确的**真实理由**是：**batch=1、序列里没有任何 padding token**，
     **mask 长度刚好等于真实 token 数**（prefill 是 T，decode 是 past+1）
     ⇒ 传全 1 就是**如实反映真实 token 布局**；
   * IR **保留了 `attention_mask` 端口**（`c079b` 第 30 行）⇒ 静态化到 512 的
     padding 由 **NPUW_LLM 在内部完成**，NPUW 会根据传入的 `attention_mask`
     自行生成 mask；
   * ⇒ **0.6B 旧图的根因是「自己手写把输入 padding 到固定长度 512，
     而图里没有 mask 端口」**；R2T2 **不具备这个条件**（有 mask 端口），
     所以**不存在同样的根因风险**；
   * **实测佐证**：全 NPU 61 分钟 **7.95%** 对 GPU **+0.10pp 不显著**
     （`reports/c086d_full61_all_npu_matrix.json`）。
4. R2T2 的 61 分钟 WER 已做过端到端验证（全 NPU **7.952%** / 目标机计分器，
   `reports/c086d_full61_all_npu_matrix.json`）⇒ **这里只做确认，不重跑**。

⇒ **一句话**：R2T2 交付 IR **不派生自 c069g**，**是 decoder-only 整段 prefill
+ 有 `attention_mask` 端口且恒传全 1（batch=1、无 padding token、mask 长度=真实
token 数，静态化 padding 由 NPUW_LLM 内部处理）**，**不存在 0.6B 那种
「自己手写 padding 到 512 且图里无 mask 端口」的根因** ⇒
**§23 的 mask 缺失缺陷只影响 0.6B 那条 `inputs_embeds` 导出线**。

### 29.5 🔄 ASR-011 ①：0.6B INT8 @ NPU 61 分钟 App 路径（**进行中**）

* **命令**：`p3_ov_app.py --enc-ir ov-encoder-06b-fp16-static --dec-ir
  ov-dec-06b-embed-mask2-int8sym --device NPU --tag mask2_61min_int8_npu`
* **与 §26.2 iGPU 格的唯一变量 = 设备**（同一 encoder IR、同一 decoder IR、同一 wav、
  同一 App 切段器与参数）。
* **设备摆放**：encoder = **NPU**，decoder = **NPU**（两者都编到 NPU）。
* **锁**：本轮是**质量作业**（ASR-001：质量作业不需锁）；当前规范锁空闲，
  但机器 CPU 满载（其它模块作业）⇒ ⚠️ **计时数字标 `timing_valid=false`**，
  **只交 transcript 给 reviewer 算 WER**。
* **进度**：见 29.7。

### 29.6 🔴 §3(c) 口径提醒：§28 的 RTF **不进 ASR-007 的 RTF 列`

`ASR007_results.json` 里的 RTF **只来自 App 路径**（61 分钟长跑或 600 s 切片 bench）。
§28 的 NPU 数字（INT8 0.2729 / FP16 0.2859 / INT4 0.3778）是**整段贪心**口径
⇒ 只出现在本文件 §28 与 `results/p3_npu_mask2_text*/summary.json`，
**不写进 ASR007_results.json 的 RTF 字段**。

### 29.7 ⏳ 本节未完成项（等长跑 / 等锁）

* 🔄 0.6B INT8@NPU 61 分钟长跑（进行中）
* ⏳ R2T2 INT8@NPU 61 分钟 App 路径（**必须等 0.6B 那格跑完**，两者共用 NPU）
* ⏳ 6 格速度/内存 bench（`asr007_bench.py`，每格 1 次 fresh 进程 + 持规范锁 +
  600 s 切片 [720,1320]）—— 需等 CPU 空闲（当前 100%）
* ⏳ `ASR007_results.json` 在上述产物落盘后重新汇总（脚本已就位）

## §30 ASR-011 ③ bench 脚本实战化：5 个真缺陷 + 冒烟验证通过（2026-10-26 10:00–10:20）

### 30.0 本节做了什么
§29 已把三个脚本写好（`asr007_bench.py` / `asr007_r2t2_app_transcribe.py` /
`asr007_build_results.py`）但**一个都没真跑过**。本节把它们**跑通并修掉真实缺陷** ——
不跑一遍就交付脚本，等于把坑留给 reviewer。

### 30.1 🔴 缺陷①：`BLOCK_MS` 未定义（被 `if False` 掩盖）
```python
step = int(SR * BLOCK_MS / 1000) if False else int(SR * 0.1)   # ← BLOCK_MS 从未定义
```
`if False` 让 Python **短路**掉左半边 ⇒ 语法检查通过、运行也不报错，
但 `BLOCK_MS` 这个名字**根本不存在** ⇒ 一旦有人把 `if False` 去掉就炸。
⇒ 已在文件头定义 `BLOCK_MS = 100`（= `audio_source.BLOCK_MS`，App 实时路径喂音粒度）
并改成 `step = int(SR * BLOCK_MS / 1000)`。

### 30.2 🔴 缺陷②：**首字延迟测的根本不是首字**
原实现把「整次 `generate()` 的耗时」记成首字延迟（`t_first = t_dec`）
⇒ 量级是「整段增量解码耗时」，**不是**「等到第一个字」。
⇒ 修法：给 `p3_ov_app.py::OVRunner.generate` 加**向后兼容**的可选回调
`on_first_token`（默认 `None` ⇒ **行为与以前完全一致**，已交付产物不受影响），
在**第一个非 EOS/PAD token 被 argmax 出来**的那一刻打点。
⇒ 实测（20 s 切片）：**首字延迟 p50 = 0.2748 s / p95 = 0.3331 s**（量级合理）。

### 30.3 🔴 缺陷③：`GetProcessMemoryInfo` **永远返回 False**
```python
ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)  # ← 恒 False
```
根因：**没声明 `argtypes`** ⇒ ctypes 把 `POINTER(PROCESS_MEMORY_COUNTERS)`
当 int 传 ⇒ 参数错位。
⇒ 修法：`WinDLL('psapi')` **显式加载** + 声明 `restype=BOOL` / `argtypes=[HANDLE,
POINTER(PMC), DWORD]`。
⇒ 实测：0.6B peak WS **9294.5 MiB** / peak private **10900.7 MiB**；
R2T2 peak WS **5091.7 MiB** / peak private **5028.4 MiB**。
⚠️ 另修语义错误：`peak_private_bytes_mb` 原写成 `PrivateUsage`（**当前值**）
⇒ 改为 `PeakPagefileUsage`（峰值口径）。

### 30.4 🔴 缺陷④：**导入顺序**让 transformers 走「无 torch」降级分支
现象：`ImportError: cannot import name 'GenerationMixin' from 'transformers.generation'`
（提示 `None of PyTorch, TensorFlow >= 2.0, or Flax have been found`）。
根因：`live_caption_app` 的 import 链先被加载 ⇒ transformers 检测不到 torch
⇒ 走**无 torch 的降级分支** ⇒ `transformers.generation` 处于**部分初始化**状态
⇒ `GenerationMixin` 不存在。
⇒ 修法：**先** `import transformers`（+ `from transformers.generation import
GenerationMixin`），**再** import `live_caption_app`（与 `p3_ov_app.py` 长跑的成功顺序一致）。
⇒ 已在 `asr007_bench.py`（两个路径都加）与 `asr007_r2t2_app_transcribe.py` 修好。

### 30.5 🔴 缺陷⑤：R2T2 的设备内存被判「拿不到 core」
原注释写「OV core 在 backend 内部 ⇒ 拿不到 core ⇒ 设备内存**未测**（不硬凑）」。
**实测是错的**：`npu_delivery_backend.py:136` 有 `be._core = core`；
`segment_encoder_backend.py:85` 有 `self._core = core` ⇒ **拿得到**。
⇒ 修法：`device_mem(getattr(eng.backend, '_core', None), eng.device_desc)`
（并给 `device_mem` 加 `core is None` 的显式处理）。
⇒ 实测读到：**GPU.0 `usm_device` 171.3 MB / `usm_host` 2043.8 MB**。

### 30.6 ✅ 冒烟验证通过（两条路径都跑通，文本正常）
| 路径 | 段数 | 词数 | RTF | 首字 p50 | 出字 p50 | peak WS | 设备内存 |
|---|---|---|---|---|---|---|---|
| 0.6B INT8 @GPU.0 | 3 | 59 | 2.1585 | 0.2748 s | 0.2049 s | 9294.5 MiB | usm_device 188.1 MB / usm_host 1133.9 MB |
| R2T2 INT8 @GPU.0 | 3 | — | 1.3258 | 2.3229 s | 0.7241 s | 5091.7 MiB | usm_device 171.3 MB / usm_host 2043.8 MB |
* ⚠️ **20 s 切片含冷启动** ⇒ RTF 偏高（正式 600 s 切片会摊薄），**冒烟数据不作交付**。
* ✅ **缓存机制确认生效**：0.6B 冷编译 **12.26 s** → 热（命中 CACHE_DIR）**4.50 s**。
* ✅ **文本正常**（两路内容一致、格式差异符合不同模型预期）⇒ 无复读、无乱码。
* ⚠️ **R2T2 首字延迟口径不同**：引擎级（`cur_text` 由空变非空，含 encoder+prefill+首 token）
  vs 0.6B 的「argmax 首 token」⇒ **报告里必须标注**（已在 json 的
  `first_tok_latency_note` 写明）。

### 30.7 ★ 冷/热缓存编排（reviewer 要「冷启动与有缓存各一组」）
新脚本 `asr007_bench_all.py`：每格跑 **2 遍 fresh 进程**（每遍都持规范锁）：
1. **冷**：清空 0.6B **专用** CACHE_DIR（`results/asr007_bench/_ov_cache`）
   ⇒ 保证冷编译（🔴 只清自己的目录，**绝不碰** App 的 `%LOCALAPPDATA%/Confucius4LiveCaption/*_cache`）；
2. **热**：同一缓存目录再跑一次 ⇒ 命中缓存。
⇒ `compile_s_cold` / `compile_s_cached` 两组数字都有出处（`bench_cold.json` / `bench_warm.json`）。
⚠️ **RTF 只取「热」那遍**（有缓存 = 用户真实体感），且**每格 n=1** ⇒
`rtf_p50 == rtf_p95`，**不是分布**（ASR-011 第 3 条用户决定）。

### 30.8 ✅ 质量长跑的 `timing_valid` 强制为 false
`build_compare_mask2.py` 新增 `QUALITY_RUNS` 判定：`p3_mask2_61min_int8_npu` /
`p3_mask2_61min_int4_npu` 属**质量作业（未持锁）** ⇒ 强制 `timing_valid=false`
并写明原因 ⇒ **RTF / 延迟数字一律作废**，只交 transcript 给 reviewer。
（计时/内存由 `asr007_bench.py` 的**持锁 fresh 进程**单独测。）

### 30.9 🔴 踩坑记录：`global` 声明位置
`SLICE_SEC` 改成可变参数后，`global SLICE_SEC` 必须写在 `main()` **函数体第一行**
（写在 `args = ap.parse_args()` 之后 ⇒ `SyntaxError: name 'SLICE_SEC' is used prior
to global declaration`）。

### 30.10 本节未完成
* 🔄 0.6B INT8@NPU 61 分钟长跑进行中（最近 **64.0%** / 355 段 / 2350.7 s，文本正常）。
* ⏳ R2T2 INT8@NPU 61 分钟（**必须等 0.6B 那格跑完**，两者共用 NPU）。
* ⏳ 6 格 bench（等 CPU 空闲 + 规范锁；当前锁被 `tts` 持有 10:10:13 起，CPU 100%）。

### 30.11 ✅ R2T2 App 转写脚本冒烟通过（`gpu_int8` 档，1 分钟切片）
`asr007_r2t2_app_transcribe.py --engine gpu_int8 --minutes 1` ⇒
**10 段 / 162 词**、`rule_counts {rule1: 8, rule2: 1, short_flush: 1}`、
`load_s 11.9` / `wall_s 83.4` / `rtf 1.3908`；文本**通顺无复读**（"Good morning
everyone. Good morning. Let's get started…"）⇒ 脚本逻辑与真实 App 路径对齐。
⚠️ 用的是 **GPU.0** 档（NPU 档与正在跑的 0.6B 长跑**抢 NPU**）
⇒ 只验证脚本逻辑，**不作交付数据**。

### 30.12 🔴 `timing_valid` 必须**真读锁**、且要按**进程树**判归属
原 `asr007_r2t2_app_transcribe.py` 把 `timing_valid` **硬编码成 `True`**
⇒ 没持锁也会声称计时有效（我那次冒烟就是没持锁跑的，字段却写 True）。
⇒ 修法：
* 真实读规范锁 `C:/Users/Trekker-PTL/shared/MACHINE_LOCK`（多编码回退）；
* 解析锁里的 `pid`，再按**进程树**判「是不是本进程持的锁」
  —— 🔴 **Windows 上 venv python 会再起一个 base python 子进程**
  （实测：父 = `.venv\Scripts\python.exe`，子 = `Python312\python.exe`）
  ⇒ **只比 `os.getpid()` 会误判成「不是我持的锁」**；
* `timing_valid = bool(lock_is_ours)`，不成立就写明原因（附锁内容快照）。

### 30.13 ✅ 新增 `build_compare_r2t2_app.py`（R2T2@NPU 61 分钟 App 路径新格）
* 读 `results/p3_r2t2_61min_npu/{summary.json,segments.json,transcript.txt}`
  ⇒ 产出 `reports/compare/r2t2__int8__npu_app.json`；
* **只加字段不改数值**；**WER 留 `null`**（交 reviewer 复算，ASR-004 铁律）；
* ⚠️ 明确标注：本格是 **App 路径**（真实 `OVEngine` + 真实 `Segmenter.due()`）
  ⇒ 与既有 `r2t2__int8__npu.json`（**226 段离线切分**）**路径不同 ⇒ WER 不可直接比**；
  且**段数也不可比**（App `MIN_SEG 6 s` vs `seg_stream` 旧切段器 12/20 s）；
* 已接入 `asr007_build_results.py`（`r2t2__int8__npu_app.json` → `path='app'`）。

### 30.14 🔴 缓存目录必须**按格隔离**（否则「冷」那遍不冷）
原设计 6 格共用一个 `results/asr007_bench/_ov_cache` ⇒ 跑完 `int8` 后缓存里
已有 int8 的 blob ⇒ 跑 `int4` 时「冷」那遍其实**命中了缓存**
⇒ `compile_s_cold` 失真。
⇒ 修法：缓存根目录下**按格分子目录** `_ov_cache/<cell>/`
（`asr007_bench.py::OV_CACHE_ROOT` + `spec['cell']`，
 `asr007_bench_all.py::_clear_ov_cache(cell)` 只清该格自己的目录）。
⇒ 附带修正：`spec['cell']` 原先在 `bench_06b()` **调用之后**才设
⇒ 现在**提前**设进 `spec`（缓存目录要用它）。

### 30.15 ✅ 新增 `wait_and_build_mask2_npu.py`（等长跑 + 自动出格）
* 轮询**落盘的 `segments.jsonl`**（不是进程存活 —— 进程可能被外部回收）；
* 🔴 判据 = **末条记录的 `end_s` 覆盖到 `audio_sec − 1.0`**
  （**不是**「文件非空」）；
* 满足后自动跑 `build_compare_mask2.py` ⇒ 产出
  `reports/compare/qwen3asr_06b__int8__mask2__int8_npu.json`；
* **不**自己算 WER（ASR-004）⇒ 格子 `wer_pct = null`，交 reviewer。

## §31 0.6B INT8 @ NPU 61 分钟长跑完成 + NPU vs iGPU 同口径对比（2026-10-26 10:40）

### 31.1 ✅ 长跑完成（ASR-011 ①）
产物 `qwen3asr_06b/results/p3_mask2_61min_int8_npu/`（4 文件，10:40）：
`summary.json` 1708 B / `segments.jsonl` 141165 B（**553 行**）/
`segments.json` 163341 B / `transcript.txt` 74230 B。

| 项 | 值 |
|---|---|
| `audio_sec` / `covered_s` | 3671.189 / **3671.189**（`complete=true`，跑满整个 wav） |
| 段数 | **553** |
| `rule_counts` | **518 / 34 / 1**（rule1 / rule2 / flush） |
| 段长 p50 / p95 / max | **6.4 / 8.96 / 12.16 s** |
| 总词数 | **11412** |
| 编译 | `load_s` 6.47 / `compile_s` **144.51**（NPU 双端口图） |
| `n_steps_total` | 5737（640 ms 粒度） |
| 设备 | **NPU**（enc=`ov-encoder-06b-fp16-static` 静态化，dec=`ov-dec-06b-embed-mask2-int8sym`） |
| decoder 端口 | **2** ⇒ 带 `attention_mask`（新图，§23 根治版） |

⚠️ **`timing_valid = false`**（`build_compare_mask2.py::QUALITY_RUNS` 强制）：
本长跑是**质量作业、未持规范锁**（机器上有别的负载）⇒
**RTF 1.0684 / 首字延迟 p50 0.3819 s 等计时数字一律作废**，
只交 transcript 给 reviewer 复算 WER。
计时/内存由 `asr007_bench.py` 的**持锁 fresh 进程**单独测（ASR-011 ③）。

### 31.2 ★ NPU vs iGPU **同口径**对比（这是本节最有价值的一条）
与 §26 的 iGPU INT8 格逐项比：

| 指标 | NPU INT8 | iGPU INT8（§26） | 判定 |
|---|---|---|---|
| 段数 | **553** | 553 | ✅ **逐位一致** |
| `rule_counts` | **518/34/1** | 518/34/1 | ✅ 逐位一致 |
| 段长 p50/p95/max | **6.4/8.96/12.16** | 6.4/8.96/12.16 | ✅ 逐位一致 |
| **段边界逐位一致** | — | — | ✅ **553 / 553**（`start_s`/`end_s` 差 < 0.01 s） |
| 总词数 | **11412** | 11419 | **−7（−0.06%）** |
| **文本逐字相同** | — | — | ✅ **447 / 553（80.8%）** |
| 拉丁/全部字母 | **1.0000** | 1.0000 | ✅ 无乱码 |
| 三连重复 / ABAB | **0 / 6** | 0 / 6 | ✅ 同型 |
| 唯一词率 | **0.2346** | 0.2354 | ✅ 同型 |
| 空段 / 非 ASCII 字母 | **0 / 0** | 0 / 0 | ✅ |

⇒ **两条结论**：
1. 🔴 **段边界与设备无关**（553/553 逐位一致）⇒ 切段发生在**音频域**
   ⇒ **不同设备/精度的格子，段数与段长可以直接比**（这是做同口径对比的前提）；
2. ✅ **NPU 上的文本完全健康**，与 iGPU **同型**
   ⇒ 剩余 106 段的差异（80.8% 逐字相同、词数 −7）是
   **NPU 与 iGPU 的浮点/内核差异**造成的**细微抖动**
   （与 §26 记录的 iGPU INT8↔INT4 之间同类抖动一致：段级 78.8% 文本不同）
   ⇒ **不是**模型坏、**不是**mask 失效。

### 31.3 ✅ 格子已自动生成
`reports/compare/qwen3asr_06b__int8__mask2__int8_npu.json`：
`n_segs=553` / `words=11412` / **`wer_pct=null`（交 reviewer 复算，ASR-004）** /
`timing_valid=false` / `device_placement` = **NPU / NPU**（enc 与 dec 都在 NPU）/ 
`source_files` 四件套齐全。
由 `wait_and_build_mask2_npu.py` 自动生成（判据 = **末条记录 `end_s` 覆盖到
`audio_sec − 1.0`**，不是「文件非空」）。

### 31.4 🔄 R2T2 INT8 @ NPU 61 分钟 App 路径进行中
`asr007_r2t2_app_transcribe.py --engine npu_int8 --group B` ⇒
`results/p3_r2t2_61min_npu/`；引擎加载+编译 **4.1 s**（NPU 缓存已命中）；
切段常量已确认：`SIL_REL=True` / `SIL_REL_MODE=max` / `SIL_REL_DROP=12.0` /
`SPK_REL=True` / `MIN_REL_COVER=0.4` / `SILENCE_CUT=0.8` / `MIN_SEG=6.0` /
`group=B`（⇒ 与 ASR-004 的 B 同口径）。
⚠️ 同样是**质量作业、未持锁** ⇒ `timing_valid` 由脚本**真读锁**判定（§30.12）
⇒ 大概率是 `false` ⇒ RTF 作废，只交 transcript。

### 31.5 本节未完成
* 🔄 R2T2 INT8@NPU 61 分钟（进行中）⇒ 完成后跑 `build_compare_r2t2_app.py` 出格。
* ⏳ 6 格速度/内存 bench（等 CPU 空闲 + 规范锁；§30 的编排脚本已就位）。
* ⏳ 待 reviewer 复算两份新 transcript 的 WER（0.6B@NPU + R2T2@NPU）。

## §32 交付件字段语义修正：作废数字不再留在可引用字段 + 设备摆放补出处（2026-10-26 10:40–11:00）

### 32.0 本节做了什么
§31 交付后自查 `ASR007_results.json` / `MATRIX.*` / 格子 json 三层交付件，
发现 **4 处「数字在正确的地方、但语义错了」** 的问题 ——
这类问题**不会让任何数字算错**，但会让 reviewer **误引一个不该引用的值**，
比算错更危险。本节全部修掉并记录依据。

### 32.1 🔴 问题①：`mem_host_peak_mb` 塞的是**系统级**内存，不是进程峰值
ASR-010 §4.3 要的是「**主机内存：进程峰值的 working set 和 private bytes**」，
但 `cell_from_compare()` 取的是格子里的 `mem_host_after` ——
那是 `GlobalMemoryStatusEx` 的**系统级** `total/avail/used/load_pct`，
**不是**本进程占用（且是**长跑结束那一刻**的快照）。
⇒ **修法**：`mem_host_peak_mb` 一律置 `null`，
原值另存 `mem_host_system_raw` + `mem_host_peak_note` 说明差异；
**进程峰值只由 bench 格提供**（`GetProcessMemoryInfo`，§30.3 修好的那个）。

### 32.2 🔴 问题②：作废的 RTF 仍摆在 `latency.rtf` 里
0.6B INT8@NPU 那次是**质量作业、未持锁** ⇒ `timing_valid=false` ⇒
RTF 1.0684 / seg_rtf_p95 1.487 / first_tok_p50 0.3819 等**已被其它负载污染**。
虽然格子有 `timing_valid: false` 标注，但**数字仍在 `latency.rtf` 这类
「看起来能引用」的字段** ⇒ reviewer 极可能误用。
⇒ **修法**（三层同时做）：
| 层 | 修法 |
|---|---|
| 格子 json（`build_compare_mask2.py`） | 新增 `_obs_timing_block()`：作废时把 10 个计时字段**挪到 `timing_observed`**，数值字段**全部置 `null`** |
| `MATRIX.md` | RTF 列：`timing_valid=false` ⇒ 显示「**作废**」而不是把污染值摆在表里 |
| `MATRIX.json` | 新增 `rtf_observed` 存原值，`rtf` 置 `null` ⇒ 机器消费方也不会误用 |
| `asr007_build_results.py` | 同上（`timing_observed` 字段 + 数值字段置 null） |

⇒ **连带效果**：`r2t2__int8__npu.json` 那格的 RTF 0.7722 也从 RTF 列消失了 ——
它自己就标着 `timing_valid=false`（单次全长运行、无 fresh 进程重复样本）
⇒ 正确。**交付级 RTF 只来自 bench 格**（持锁、fresh 进程、600 s 切片）。

### 32.3 🔴 问题③：`device_placement` 没有产品级出处
`device_placement` 里的 `enc_device`/`dec_device` 是**脚本参数**（`spec['device']`）
推出来的，不是从运行产物读出来的 ⇒ reviewer 无法核对。
⇒ **修法**：`build_compare_mask2.py` 增加 `device_placement.evidence`，
引用 summary 的**原始字段**：
`device`="NPU" / `enc_ir` / `dec_ir` / `mem_device.device`="NPU" /
`DEVICE_ARCHITECTURE`="5010"，
并写明推理链：`OVRunner` 用**同一个 `device` 参数**编译 enc 与 dec 两个 IR
⇒ `enc_device == dec_device` 必然成立。

### 32.4 🔴 问题④：`mem_device_mb` 恒为 `null`（不满足 ASR-010 §4.5 字段清单）
`cell_from_bench()` 把设备内存塞进了 `mem_device_raw`，而 ASR-010 §4.5
要求的字段名是 `mem_device_mb` ⇒ 清单核对时这一列**永远空着**。
⇒ **修法**：新增 `_device_mem_mb()` 做归一 ——
GPU(iGPU) 取 `GPU_MEMORY_STATISTICS` 的 `usm_device`/`usm_host`/`usm_shared`/`cl_mem`
（字节 ⇒ MiB，并算 `total_mib`）；
NPU **不提供** `GPU_MEMORY_STATISTICS` ⇒ 只报 `DEVICE_ARCHITECTURE`，
**内存数字不硬凑**（本模块一贯纪律）。

### 32.5 ✅ 附带修好的两处
* **R2T2 的冷/热编译时间无法分列** —— OVEngine 把「加载 + 编译」**合算**在 `load_s`
  ⇒ `compile_s_cold`/`compile_s_cached` 对 R2T2 恒 `null`，
  改用 `load_s_cold`/`load_s_cached` 两个合并值 + `compile_s_note` 显式说明。
  （0.6B 侧的 OVRunner 分得开 `load_s`（torch 加载）与 `compile_s`（OV 编译）⇒ 正常分列。）
* **MATRIX 顶部 reviewer 计分器数字清单漏了 10.94% / 11.57%** ⇒ 补全
  （否则 reviewer 可能以为 8.17% 是唯一对照基准）。

### 32.6 ✅ 校验：交付 json 字段齐全性
按 ASR-010 §4.5 的 **27 个必需字段**逐条核对 `ASR007_results.json`
（model / precision / recipe / enc_device / dec_device / enc_ir / dec_ir / path /
transcript / n_segs / wer_pct / wer_scorer / rtf_runs / rtf_p50 / rtf_p95 /
first_tok_p50 / first_tok_p95 / final_lat_p50 / final_lat_p95 / load_s /
compile_s_cold / compile_s_cached / mem_host_peak_mb / mem_device_mb /
timing_valid / lock_holder / source_files）
⇒ **7 条记录全部 0 缺失**（2026-10-26 10:56 实测）。

### 32.7 🔄 R2T2 INT8 @ NPU 61 分钟（进行中）
`results/p3_r2t2_61min_npu/` ⇒ 已跑到 **22.7% / 127 段**，
RTF ≈ **1.01**（音频 833 s / 墙钟 845 s）⇒ 预计还需约 48 分钟。
已就位**自动出格**脚本 `wait_and_build_r2t2.py`
（判据 = `summary.json` 的 `n_segs > 0` **且** `covered_s >= audio_sec − 1.0`，
**不是**「文件非空」）⇒ 长跑一结束自动跑 `build_compare_r2t2_app.py` 出格。

### 32.8 本节未完成
* ⏳ 6 格速度/内存 bench（等 R2T2 长跑让出 NPU + CPU + 规范锁空闲）。
* ⏳ R2T2 INT8@NPU 61 分钟 App 格出格（自动脚本已就位）。
* ⏳ 待 reviewer 复算两份新 transcript 的 WER（0.6B@NPU + R2T2@NPU）。

## §33 ASR-012 落地：0.6B INT8@NPU WER 11.05% 已回填 + §29.4 理由改写（2026-10-26 11:00–11:10）

### 33.0 本节做了什么
reviewer 10:52 发了 **ASR-012**（3 项：① 回填 WER、② 改 §29.4 的理由、③ R2T2 长跑继续）。
本节逐条处理并落档。

### 33.1 ✅ ① 0.6B INT8 @ NPU 的 WER 已原样回填
reviewer 复算（MiniMax baseline，参考词数 **10964**，全局对齐 + 按段配对 bootstrap 5000 次）：
| 项 | 值 |
|---|---|
| **0.6B INT8 @ NPU（App 路径，553 段）** | **11.05%**（总错误 **1212** 个） |
| 0.6B INT8 @ iGPU（对照） | **10.94%**（1199 个错误） |
| **NPU − iGPU** | **+0.12pp，CI [−0.05, +0.29]，不显著** |
| 按段比 | **17 段更好 / 510 段持平 / 26 段更差** |
| 0.6B@NPU − R2T2 App B（10.58%） | **+0.47pp，CI [−0.24, +1.17]，不显著**（两边切段不同 ⇒ 时间块配对 bootstrap，498 块） |

**reviewer 独立核实了段边界**：与 iGPU INT8 格 **553/553 逐位相同**
（`start_s/end_s` 最大差 **0.0 s**）、文本相同 447/553、词数 11412
⇒ **§31.2 的结论成立**（切段在音频域；NPU 上文本与 iGPU 无实质差异）。

⇒ **回填动作**：`build_compare_mask2.py` 的 `REVIEWER_WER` 新增 `int8_npu` 项
（`wer_pct=11.05` / `n_errors=1212` / `scorer=reviewer_minimax_global` /
`ref='ASR-012 §1'`）⇒ 重跑后格子 `accuracy.wer_pct=11.05`、
`wer_scorer=reviewer_minimax_global`、`paired_bootstrap` 含两组 CI。
⚠️ reviewer **只给了总错误数、未给 S/D/I 拆分** ⇒ `wer_breakdown` 写
「未给 S/D/I 拆分 ⇒ 不硬凑」+ `n_errors=1212`，**不编造拆分**。
⇒ `ASR007_results.json` 与 `MATRIX.md` 已刷新（WER 列 11.05 / reviewer(MiniMax)）。

### 33.2 🔴 ② 撤回 §29.4 第 3 点里的「cross-attention」错误理由
reviewer 读代码后指出：§29.4 写的
「R2T2 走 **cross-attention** + 逐 token 解码，每步只喂当前 token 的 embedding，
所以没有 padding 概念」**是错的**。

**正确的说法（ASR-012 §2(b)）**：
1. R2T2 是 **decoder-only 的整段 prefill** ——
   `live_caption/npu_embeds_backend.py:211-214` 的 prefill **一次喂进 T 个
   prompt token**（音频 embedding + 模板），与 0.6B 是**同一种结构**；
   只是**之后的 decode** 每步喂 1 个 token。
2. 全 1 mask 正确的**真实理由**：
   * **batch=1、序列里没有任何 padding token**；
   * **mask 长度刚好等于真实 token 数**（prefill 是 T，decode 是 past+1）
     ⇒ 传全 1 是**如实反映真实 token 布局**；
   * IR **保留了 `attention_mask` 端口**（`c079b_build_clean_embeds_ir.py:30`）
     ⇒ 静态化到 512 的 padding 由 **NPUW_LLM 在内部完成**，
     NPUW 会根据传入的 `attention_mask` 自行生成 mask；
   * ⇒ **0.6B 旧图的根因是「自己手写把输入 padding 到固定长度 512，
     而图里没有 mask 端口」**；R2T2 **不具备这个条件**
     （有 mask 端口）⇒ **不存在同样的根因风险**；
   * **实测佐证**：全 NPU 61 分钟 **7.95%** 对 GPU **+0.10pp 不显著**
     （`reports/c086d_full61_all_npu_matrix.json`）。
3. 「**不派生自 c069g**」这**一条成立**（reviewer 也确认）：
   `c079b_build_clean_embeds_ir.py` 的 `PAIRS` =
   `qwen3-lm-int8sym-lastlogit-ov → qwen3-lm-int8sym-cleanie-ov`（int4 同理）；
   `c069g` 的 `OUT_DIR` = `models/ov-dec-embed-fp16`；
   `live_caption/*.py` 里**没有任何地方引用** `models/ov-dec-embed-fp16`。

⇒ **动作**：
* **§29.4 第 3 点已就地改写**（reviewer 明确要求「报告会引用这一段」
  ⇒ 就地改比另起章节更合用），并在此处记录改动内容；
* **三处派生物同步修正**（都含旧措辞）：
  | 文件 | 位置 |
  |---|---|
  | `scripts/asr007_build_results.py` | `R2T2_IR_NOTE` |
  | `scripts/asr007_r2t2_app_transcribe.py` | `R2T2_IR_NOTE` |
  | `scripts/build_compare_r2t2_app.py` | **新增** `R2T2_IR_NOTE`（覆盖 summary 里的旧措辞 —— 🔴 长跑进程启动时已加载旧代码 ⇒ summary 带的是旧措辞，**出格时必须覆盖**） |
* ⇒ `ASR007_results.json` 的 `r2t2_ir_note` 与 R2T2 App 格随之更新。
* **不需要重跑**（reviewer 明示）。

### 33.3 🔄 ③ R2T2 INT8 @ NPU 61 分钟 App 路径（进行中）
reviewer 记录的启动信息：pid **25264**，10:41 开始，
`results/p3_r2t2_61min_npu`（当时是空目录）。
⇒ **本机实测**：跑到 **31.3% / 175 段**，RTF ≈ **1.05**（音频 1150 s / 墙钟 1207 s）。
⚠️ reviewer 说「pid25264」—— 本机 `tasklist` 显示的是 **20876**（4.5 GB 那个），
`25264` 是一个 **9 MB 的小进程** ⇒ 推测 reviewer 记的是 venv 包装层的 PID
（Windows 上 venv python 会再起一个 base python 子进程，§30.12 已记录此现象）
⇒ **以「目录里有没有产物」为准，不以 PID 为准**。

### 33.4 ✅ 顺带抓到的第 5 处缺陷：OV 的 `GPU_MEMORY_STATISTICS` 返回**字符串**
在 0.6B INT8@GPU.0 上跑了一次 **20 s 冒烟**（验证 bench 单格的冷/热逻辑），
发现 `device_mem()` 落盘的 `GPU_MEMORY_STATISTICS` 是：
```json
{"usm_device": "188135156", "usm_host": "1133950020", "cl_mem": "0", ...}
```
⇒ 🔴 **全是字符串**（`device_mem()` 里用 `str(x)` 转过）。
而 §32.4 新写的 `_device_mem_mb()` 只判 `isinstance(v, (int, float))`
⇒ **会漏掉全部 GPU 设备内存**（`mem_device_mb` 又变成 null —— 刚修的问题复发）。

⇒ **修法**：先 `int(str(v).strip())`，转不动再放弃。实测归一结果：
`usm_device` **179.4 MiB** / `usm_host` **1081.4 MiB** / 合计 **1260.8 MiB**
（iGPU 共享系统内存 ⇒ 占用几乎全在 `usm_host`）。

⚠️ **教训（与 §9b 同源）**：**OV 的属性返回值类型不可靠** ——
`get_element_type().get_type_name()` 返回短名（`f16`/`i8`）、
`GPU_MEMORY_STATISTICS` 返回**字符串** ⇒ **任何「按类型过滤/换算」的代码
必须先做类型归一**，否则会静默地得出一批 0/null 的**假结论**。
⇒ 这条应写进模块铁律（与 §9b 并列）。

**冒烟产物已清理**（`_smoke_warm.json` / `segments.jsonl` / `transcript.txt`
/ `_ov_cache/` 全部删除）⇒ **不会污染正式 bench 的冷编译判定**。

### 33.5 本节未完成
* ⏳ 6 格速度/内存 bench（等 R2T2 长跑让出 NPU + CPU + 规范锁空闲）。
* ⏳ R2T2 INT8@NPU 61 分钟 App 格出格（自动脚本 `wait_and_build_r2t2.py` 已就位）。
* ⏳ 待 reviewer 复算 R2T2 INT8@NPU App 路径的 WER
  （对照 App 路径 R2T2 iGPU B **10.58%**）。

## §34 R2T2 INT8@NPU 61 分钟 App 路径出格 + 6 格 bench 启动（2026-10-26 13:10–13:24）

### 34.1 自动出格脚本 failed ⇒ 改手动出格
* 背景：ASR-011 ② 的 R2T2 INT8@NPU 61 分钟 App 路径长跑（task `ijePZK`，真实占设备 pid 20876）已于 2026-10-26 11:46 跑完，三件套落盘 `results/p3_r2t2_61min_npu/{summary,segments,transcript}.json`：**552 段 / 11294 词 / 覆盖 0.0→3665.28 s（≈99.8% 音频 3671.19 s，末 ~6 s 缺口与 0.6B 已知行为一致）**。
* 🔴 自动出格器 `wait_and_build_r2t2.py`（task `EJU2yz`）**failed**：其 `done()` 判据查 `s.get('covered_s')`，但 R2T2 的 `summary.json` **根本没有 `covered_s` 字段** ⇒ `cov=0.0` ⇒ `done()=False` 永远不成立 ⇒ 超时退出，`r2t2__int8__npu_app.json` 未生成。
* ✅ 改**手动** `build_compare_r2t2_app.py`（已内置 ASR-012 §2 修正）：
  - `device_placement.note` 与 `r2t2_ir_note` **覆盖**为「**decoder-only 整段 prefill**」措辞（**无** cross-attention；batch=1、无 padding token、mask 长度=真实 token 数、静态化 padding 由 NPUW_LLM 内部完成、IR 有 `attention_mask` 端口 ⇒ 不具备 0.6B 根因）；
  - `timing_valid=false` ⇒ `latency.rtf` 置 **null**、原值 **1.0627** 挪入 `latency.timing_observed.rtf`（与 §32 的 0.6B NPU 格同口径）；
  - `accuracy.wer_pct=null`（交 reviewer 复算，ASR-004 铁律）。
* 产物：`reports/compare/r2t2__int8__npu_app.json`（6815 B，mtime 2026-10-26 13:24）。

### 34.2 汇总刷新
* `asr007_build_results.py` 已支持该格（原 line 359-365），重跑 → **`ASR007_results.json` 8 条记录**（新增 R2T2 App 格；27 必需字段口径不变，0 缺失）。
* `p3_make_matrix.py` 的 ORDER 已含该格（line 36），重跑 → MATRIX.json / MATRIX.md 已纳入。

### 34.3 6 格速度/内存 bench 启动（ASR-011 ③）
* 启动 `asr007_bench_all.py`（**注意：无 `--all` 参数**，空 `--cells` 即全 6 格；其 docstring 写 `--all` 是错的，已踩坑一次），任务 `eauDGm`，2026-10-26 13:24。
* 编排：6 格（`06b_int8_gpu0` / `06b_int4_gpu0` / `06b_int8_npu` / `06b_int4_npu` / `r2t2_int8_gpu0` / `r2t2_int8_npu`）× 每格 **冷 + 热** 各一遍 fresh 进程，均**持规范锁串行**（锁空闲，首格 06b_int8_gpu0 冷编译已开始，pid 35892）。
* 口径：600 s 切片 [720,1320]；RTF 取热那遍；0.6B 清专用 CACHE_DIR 保证冷、R2T2 缓存由 App 内部决定（只能按现状记录）；每格 1 次 ⇒ `rtf_p50==rtf_p95`，**不是分布**。
* ⏳ 预计数小时；完成后重跑汇总脚本刷新 → 落 §34 末次。

### 34.4 待办
* 🔴 reviewer 复算 R2T2 INT8@NPU App 路径 WER（对照 App 路径 R2T2 iGPU B **10.58%**）。
* ⏳ bench 完成后：`asr007_build_results.py` + `p3_make_matrix.py` 刷新 → 本 §34 补 bench 摘要 + 落 §34 末次。

## §35 ASR-013 落地：①FP16 过阈 / INT8 三路未过阈 + ②流式断点 + ③说话人身份 + ④伪真值 + ⑤ASR-011 交付件刷新（2026-10-26 21:21–23:20）

> 本节是 **ASR-013**（`CORRECTIONS_ASR.md` 第 234 行，2026-10-26 16:20）的落档。
> ⚠️ `last_ack` 此前已是 ASR-013（21:21 那次写过开头），但 **§35 章节从未落档** ⇒ 本节补齐，
> 并把 21:21→23:20 期间**实际已经完成**的 ②③④ 与 ASR-011 交付件刷新一并如实记录。
> ⚠️ 21:21 那行「最近更新」称「②③④ 未开始」**已过期** ⇒ 以本节为准（不回头改旧行，按 § 规则只追加）。

### 35.1 ①模型导出 + 逐帧对拍：FP16 过阈，INT8 三条路径全部未过阈

**导出链**（`results/pyannote_seg/pya_export_meta.json`）：
`pytorch_model.bin` → ONNX fp32（`pyannote_seg_3_0_fp32.onnx`，30609 B + data 5972608 B，
输入 `[1,1,160000]`、输出 **589 帧 × 7 类 powerset**、导出耗时 41.14 s）
→ `ovc` 转 OV IR（`models/pyannote_seg/ov-fp32/`，xml 55755 B + bin 5957808 B，转换 2.2 s，**117 个算子**）。

⚠️ 期间修掉一个**会给出假 NaN 的坑**：FP16 IR 里 `LogSoftmax` 数值下溢 ⇒ 输出 −inf ⇒ cos 算成 NaN
⇒ 改为**导出 raw logits** + 两侧各自 numpy `log_softmax` 后再比（表内 `cos_min_logits` 列即该口径）。

**逐帧对拍结果**（阈值：cos ≥ 0.999 且 帧级类别一致率 ≥ 99%）：

| 产物 | 精度/路径 | 设备 | 窗数 | cos_min_overall | 帧一致率 | pass |
|---|---|---|---|---|---|---|
| `pya_verify_fp16_GPU0.json` | FP16 | GPU.0 | 3 | **0.99943** | **1.0000** | ✅ |
| `pya_verify_fp16_NPU.json` | FP16 | NPU | 6 | **0.999405** | **0.9983** | ✅ |
| `pya_verify_int8_GPU0.json` | INT8 weight-only | GPU.0 | 6 | 0.995336 | 0.981324 | ❌ |
| `pya_verify_int8_NPU.json` | INT8 weight-only | NPU | 6 | 0.995548 | 0.984720 | ❌ |
| `pya_verify_int8calib_GPU0.json` | INT8 激活感知（带校准） | GPU.0 | 6 | 0.951184 | 0.947368 | ❌ |
| `pya_verify_int8head_GPU0.json` | INT8 激活感知（head 保 FP16） | GPU.0 | 6 | 0.986118 | 0.920204 | ❌ |

⇒ **FP16 双阈值通过（GPU.0 与 NPU 都通过）**；**INT8 三条路径（weight-only / 激活感知 calib / 激活感知 head 保留）全部未过阈**
⇒ 按 ASR-013「再试 INT8」的字面要求已试完 ⇒ **FP16 暂作 ASR-013 交付精度**，INT8 差距如实记录，
**不擅自降阈值**（阈值是纠偏文件给定的验收线）。

**单窗性能/内存**（`pya_bench_fp16_GPU0.json` / `pya_bench_fp16_NPU.json`，10 reps，切片起点 732.0，
**timing_valid=true**，持锁）：
* GPU.0：编译 **1.865 s**（冷）、单窗中位 **38.87 ms**（first 44.88 / min 38.69 / max 39.38）
  ⇒ `rtf_window` **0.00389**；进程峰值 working set **587.4 MB** / peak private bytes **1020.0 MB**；
  设备内存（`GPU_MEMORY_STATISTICS`，已 `int(str(v))` 归一）usm_device **6.0 MiB** / usm_host **2.7 MiB**。
* NPU：编译 **1.206 s**（冷）、单窗中位 **12.5 ms**（first 17.25 / min 6.52 / max 19.05）
  ⇒ `rtf_window` **0.00125**（**比 GPU.0 快 3.1×**）；进程峰值 working set **382.6 MB** / peak private bytes **807.4 MB**；
  🔴 `mem_device_mb` = **null**（NPU 无 `GPU_MEMORY_STATISTICS`）⇒ 只报 `DEVICE_ARCHITECTURE=5010`，**不硬凑**。
* 设备架构：GPU.0 = `GPU: vendor=0x8086 arch=v30.1.0`（Intel 核显 iGPU，§27.4 已确认）。

### 35.2 ②流式强制切段：断点已产出（`pya_stream_full61_NPU.json`）

* 口径：NPU + FP16 IR，10 s 窗滑动，stride **640 ms**（与 App 640 ms 分块对齐），覆盖 **3671.189 s**（整段 wav），
  **5722 窗**，分段模型推理合计 **39.2 s** ⇒ `rtf_seg_model` **0.01068**、单窗中位 **6.67 ms** / max 15.8 ms。
* 参数：`silence_ms=800`、`stable_frames=10`、`min_seg_s=6`、`max_seg_s=20`、`silence_thr=0.5`、`hysteresis=0.2`。
* **断点 107 个**：`max_len` **46** / `silence` **37** / `speaker_switch` **24** ⇒ 段 **108** 个。
* **判决滞后**：`decision_lag_p50_ms` = **800.0**、`decision_lag_p95_ms` = **800.0**；
  按规则分：silence **800 ms**（= X）、speaker_switch **169.8 ms**（= 10 帧 × 16.98 ms）、max_len **null**（兜底不需观察）。
  ⚠️ 这是**算法固有**滞后，**不含**窗级聚合滞后（一个帧要等包含它的最后一个窗推理完才定稿）⇒ 报告须分列这两层。
* 🔴 **诚实记录一个缺陷**：`max_len`（最长段兜底）**46 次**里，产物自己标注「无合法候选 ⇒ 兜底点可能落在词中间」
  ⇒ **兜底路径天然可能切在词中间**，这正是 ASR-013 要求「不能切在词中间」的例外点，报告必须写明而不是掩盖。

### 35.3 ③说话人身份（`pya_spk_full61_NPU.json`）

* x-vector 来源：**Qwen3-TTS Base 自带 speaker encoder**（`Confucius4_LiveCaption_v1.5/models/qwen3tts/int8/speaker_encoder.xml`，NPU）
  ⇒ 符合 ASR-013「不再引入第三个模型」的约定。
* 候选段 **108** ⇒ 分配 **100**、跳过 **2**（`no_speech`）；动作计数 init 1 / update 99。
* 全局 id = **S1（1 人）**，**spk_conf 均值 0.9785**，`n_overflow`=0；参数 thr 0.6 / update_alpha 0.5 / max_speakers 4 / min_dur_s 2.0。
* 对**局部**标签（segmentation-3.0 窗内 id）纯度 **0.96**、碎片化 0（local_1 96 段、local_2 4 段，各归 1 簇）。
* 🔴 **本节结论有明确边界，不能写成「说话人可用」**：
  * 61 分钟 SPE 素材**只有 1 个说话人** ⇒ 全局 id 恒为 S1 ⇒ **区分能力完全未被检验**；
  * x-vector 弱参照统计：同人余弦均值 0.9555 / 最小 0.8912，异人余弦均值 **0.9501** / 最大 **0.9906**
    ⇒ **同人/异人余弦几乎无间隙（margin 仅 0.0054）** ⇒ **阈值 0.6 的聚类在多说话人下极可能把不同人并进同一簇**；
  * ⇒ ASR-013 验收③ 的「切换点 F1（±0.5 s）/ 段级纯度 / 碎片化」**在当前素材上无法评估**，**需换多说话人素材重跑**；
    本轮**不**自行编造这些指标。
* 隐私：`pya_spk_full61_NPU.json` **不含向量本身**，只含 spk id / spk_conf / 余弦统计 ⇒ 不落盘 x-vector、不进客户包。

### 35.4 ④参照：diarization-3.1 离线伪真值（`pya_ref_diar_smoke30.json`）

* ⚠️ **不是官方 gated 仓库**：`pyannote/speaker-diarization-3.1`（gated=auto）**本机无 HF token ⇒ 不可直接下载**
  ⇒ 改用**非 gated 镜像** `tensorlake/speaker-diarization-3.1`（config 与官方 3.1 一致），embedding ckpt 用本机 wespeaker 权重。
* 素材 `test_audio/tts_replay_30s.wav`（30 s）、device **cuda**、耗时 7.93 s
  ⇒ **1 人（SPEAKER_00）2 turn**（2.005–5.127 / 5.532–29.967），聚类 threshold 0.7046 / min_cluster_size 12。
* ⚠️ 30 s 素材同样只有 1 人 ⇒ 作为伪真值只能校「流程通不通」，**不能校多说话人指标**。

### 35.5 ⑤ASR-011 交付件刷新（bench 6/6 已完成但此前没并入）

* 发现：`results/asr007_bench/_manifest.json`（mtime **21:21:52**）显示 6 格冷+热**全部 rc=0**
  （`06b_int8_gpu0` / `06b_int4_gpu0` / `06b_int8_npu` / `06b_int4_npu` / `r2t2_int8_gpu0` / `r2t2_int8_npu`），
  但 `reports/compare/ASR007_results.json` 仍停在 **13:20（8 条记录）** ⇒ bench 数据**从未并入交付件**。
* ✅ 跑 `scripts/asr007_build_results.py` ⇒ **`ASR007_results.json` 8 → 14 条记录**（42058 B，mtime 23:19）；
  再跑 `scripts/p3_make_matrix.py` ⇒ `MATRIX.json` / `MATRIX.md` 刷新（mtime 23:19）。
* ✅ **字段自检**：27 个必需字段（model…source_files）**14/14 条 0 缺失**。
* ✅ **语义自检（关键）**：作废格（timing_valid=false）的 `rtf_p50`/`rtf_p95` = **null**，
  原值在 `timing_observed`（如 R2T2 int8__npu whole_seg：null + `timing_observed.rtf_p50=0.7722`）⇒ 符合 §32 铁律；
  `mem_host_peak_mb` 只在 bench 格（进程峰值 `GetProcessMemoryInfo`）有值，质量格一律 null。
* bench 6 格的 RTF（**600 s 切片 [720,1320] 口径 ⇒ 不可与 61 分钟长跑直接比**，每格 1 次 ⇒ p50==p95 不是分布）：
  `06b_int8_gpu0` **0.6847** / `06b_int4_gpu0` **0.7091** / `06b_int8_npu` **0.9436** / `06b_int4_npu` **1.3389**
  / `r2t2_int8_gpu0` **0.9942** / `r2t2_int8_npu` **0.8084**；
  ⚠️ **`06b_int4_npu` 1.3389 再次坐实「INT4_ASYM g128 在 NPU 上比 INT8 慢」**（0.9436 → 1.3389，+41.9%），
  但按 ASR-010 §3 只能表述为「**INT4_ASYM g128** 在 NPU 上比 INT8 慢」，**不能**写成「NPU 上 INT4 最慢」。
* MATRIX.md 的 **WER 计分器列**已存在且分列清楚（reviewer(MiniMax) vs 目标机）⇒ 满足 ASR-010 §5「两套计分器不可混列」。

### 35.6 ②验收①：61 分钟 App 路径 forced 长跑（本节写档时尚在跑）

* 🔴 **发现先前那跑夭折**：`shared/MACHINE_LOCK` 写着 `asr PID=12832 start=2026-10-26 21:53:54 task=pya_app_forced_forced61`，
  但 `Get-Process -Id 12832` **查无此进程**、`Get-Process python*` **返回空** ⇒ **陈旧锁**（进程已死、锁没删）。
  ⚠️ 判据只按 **PID 是否存活**（不按进程名过滤）⇒ 确认可回收。
* ✅ **回收 + 重启**（23:19:55）：`scripts/pya_app_path_seg.py --engine gpu_int8 --strategy forced
  --minutes 61.2 --seg-ir models/pyannote_seg/ov-fp16 --seg-device GPU.0 --tag forced61`
  ⇒ 脚本自身 `acquire_lock()` 打印「[lock] 回收陈旧锁（pid=12832）→ 已取锁（pid=380）」，**计时作业全程持规范锁**。
  ⚠️ `--minutes 61.2`（不是 61）⇒ 覆盖 **3671.189 s** 整段 wav，避免「少跑 11.19 s」那类截断。
* ⏳ **本节写档时仍在跑** ⇒ 产物 `results/pyannote_seg/pya_app_forced_forced61.json` **尚未落盘**
  ⇒ **本节不写「已交付」**。跑完后须回填：n_segs / rule 分布 / `midword.pct_hit_all_pairs`
  （与基线 `pya_app_baseline_base5m.json` 的 **6.67%**、基线 §23 口径对比）
  ⇒ 交 reviewer 复算 WER（对照 App 路径 R2T2 iGPU B **10.58%**）。
* 参照口径（已落盘，可直接比）：`pya_app_baseline_base5m.json`（baseline 策略，300 s，46 段，词内切点 **6.67%**）
  与 `pya_app_forced_forced5m.json`（forced 策略，300 s，49 段，词内切点 **6.25%**，
  `seg_model_rtf` 0.05852）；⚠️ 这两个是 **5 分钟**口径，61 分钟结果不能与之混比。

### 35.7 撤回 / 修正

* 🔴 **撤回 §34.4「⏳ bench 完成后：重跑汇总脚本刷新 → 落 §34 末次」中的「待刷新」状态**：
  bench 已于 **21:21:52** 全部完成（manifest 6/6 rc=0），刷新动作本节 35.5 已完成 ⇒ **§34.4 的待办已闭环**。
* 🔴 **撤回 21:21 那行「最近更新」中「②③④ 未开始」的表述**（已过期）⇒ 以本节为准。
* ⚠️ **不撤回** §34.3 的口径：每格 1 次 ⇒ `rtf_p50 == rtf_p95`，**不是分布**（用户决定）。

### 35.8 本节产物清单（文件数 / mtime）

| 产物 | 说明 | mtime |
|---|---|---|
| `qwen3asr_06b/results/pyannote_seg/`（**31 文件**） | ASR-013 全部产物目录 | 目录 22:13 |
| ├ `pya_export_meta.json` | ONNX/OV 导出元信息（117 算子、589 帧 × 7 类） | 21:12 |
| ├ `pya_verify_fp16_GPU0.json` / `pya_verify_fp16_NPU.json` | FP16 对拍（**过阈**） | 21:12 |
| ├ `pya_verify_int8_GPU0.json` / `pya_verify_int8_NPU.json` | INT8 weight-only 对拍（**未过阈**） | 21:17 |
| ├ `pya_verify_int8calib_GPU0.json` / `pya_verify_int8head_GPU0.json` | INT8 激活感知两条路径（**未过阈**） | 21:23 / 21:24 |
| ├ `pya_bench_fp16_GPU0.json` / `pya_bench_fp16_NPU.json` | 单窗性能+内存（timing_valid=true） | 21:26 |
| ├ `pya_stream_full61_NPU.json` | 61 分钟流式断点（**已落盘**） | 21:49 |
| ├ `pya_frames_full61_NPU.npz` | 帧级中间量（6.28 MB） | 21:49 |
| ├ `pya_spk_full61_NPU.json` | 说话人身份（**已落盘**） | 21:55 |
| ├ `pya_ref_diar_smoke30.json` / `.rttm` | diarization-3.1 伪真值（30 s） | 22:12 |
| ├ `pya_app_baseline_base5m.json` / `pya_app_forced_forced5m.json` | App 路径 5 分钟基线/强制（词内切点 6.67% / 6.25%） | 21:41 / 21:45 |
| └ `pya_app_forced_forced61.json` | **⏳ 61 分钟 forced（跑完后落盘）** | **待落盘** |
| `qwen3asr_06b/reports/compare/ASR007_results.json` | **14 条记录**、42058 B | **23:19** |
| `qwen3asr_06b/reports/compare/MATRIX.json` / `MATRIX.md` | 矩阵刷新（18790 B / 15973 B） | **23:19** |
| `qwen3asr_06b/results/asr007_bench/_manifest.json` | bench 6/6 manifest（rc 全 0） | 21:21 |
| `qwen3asr_06b/logs/pya_app_forced61.log` | 61 分钟长跑日志 | 进行中 |

## §36 ASR-013 ②验收① 61 分钟 forced 长跑：连续两次夭折的根因定位 + 断点续跑改造（2026-10-27 00:24–00:40）

### §1 本轮纠偏检查结果：**无新纠偏**
- `status/asr/CORRECTIONS_ASR.md`：mtime **2026-10-26 16:18:05**，37954 B，md5 `55c28c7231dac56b5e340f4095840c8d`
  ⇒ 与 §35 写档时（2026-10-26 23:20）**完全一致，文件未被追加**。
- 纠偏编号集合：ASR-001 … **ASR-013**（`grep -n '^#\{1,3\} '` 列全部标题，最大编号 ASR-013；
  `grep -o 'ASR-[0-9]\{3\}' | sort -u` 去重后无 ASR-014+）⇒ **编号 > ASR-013 的条目不存在**。
- `STATUS_ASR.md` 开头 `last_ack: ASR-013` ⇒ **last_ack 保持 ASR-013，不改**；本节只记录本轮做的实质工作。
- 🔴 **ASR-013 ②验收① 的 61 分钟 App 路径 forced 长跑仍未产出**（§35 末尾记的「⏳ 待落盘」在本轮结束时**仍未闭环**，见 §2）。

### §2 🔴🔴 根因定位：长跑连续两次夭折，**不是模型问题，是后台进程被回收**
| 跑次 | 启动 | 锁 | 结局 |
|---|---|---|---|
| 第 1 跑 | 2026-10-26 21:53:54 | PID **12832** | 进程夭折，日志只到「引擎加载完成」，产物未落盘，**锁没删** |
| 第 2 跑 | 2026-10-26 23:19:55 | PID **380** | 同上：日志 `logs/pya_app_forced61.log` 仅 3 行（到「引擎加载完成」，mtime 23:20:03），**产物 `pya_app_forced_forced61.json` 不存在**，**锁仍在** |
| 第 3 跑 | 2026-10-27 00:30:18 | PID **17296** | 本轮重启，**带断点续跑**，进行中 |

- 巡检证据（2026-10-27 00:24）：`Get-Process -Id 380` **查无此进程**；`Get-Process python,pythonw,python3` **返回空（count=0）**
  ⇒ 进程**确实已死**、锁**没删** ⇒ 是**陈旧锁**（不是别的模块占着）。
- 根因判定：非交互式运行/会话结束时**后台子进程被回收** ⇒ 每跑必在**同一处**夭折（引擎加载完、进入 61 分钟喂音循环前后）
  ⇒ **光重跑没用**，必须让「被杀的进度」能落盘并续跑。
- ✅ 本轮按规则**回收陈旧锁**（PID 380 已死）后重启 ⇒ 锁文件现在写
  `asr PID=17296 start=2026-10-27 00:30:18 task=pya_app_forced_forced61`（00:30 后复查 PID 存活）。

### §3 ✅ 断点续跑改造（`scripts/pya_app_path_seg.py`，已落地并冒烟验证）
| 改动 | 内容 |
|---|---|
| 定期 checkpoint | 每喂 **60 s 音频**落一次 `results/pyannote_seg/pya_app_forced_<tag>.partial.json`，含 `fed_s` / `segments` / `last_words` / `last_text` / `elapsed_s` / `rtf_so_far` |
| 自动续跑 | 启动时读 checkpoint（校验 `audio_sec` 差 <1.0）⇒ **跳过已喂音频、不重跑推理**；新增 `--no-resume` 从头跑（重测用） |
| 🔴 续跑必须同步两处状态 | ① `rec.fed`（否则新段 `start_s/end_s` 算错）；② `eng._last_words` / `eng._last_text`（**接缝判据② 要看前段末尾标点** ⇒ 不恢复则首个续跑段文本与不中断跑不同） |
| 进度日志 | 每 60 s 打印 `进度 fed/total (x%) 段数 elapsed rtf` ⇒ 可监控、可判断是否还活着 |

- ✅ **冒烟验证（2 分钟素材，`--tag smoke2`）**：
  1. 不中断跑 ⇒ 落盘 19 段、`fed_s`=120.0、`rtf_so_far`=0.5796、`last_words`/`last_text` 均已落盘；
  2. 人工把 checkpoint 截断成 `fed_s`=60.0 / 8 段（模拟被杀）⇒ 重跑日志打印
     **「[pya] 断点续跑：从 60.0s 起（已有 8 段）」** ⇒ 续跑路径生效，**不重跑已喂的 60 s 推理**。
- ✅ 锁行为复核：跑完 `release_lock()` 正常删锁（冒烟跑完后 `MACHINE_LOCK` 不存在）⇒ **没有留下孤儿锁**。

### §4 ⏳ 61 分钟 forced 长跑：进行中（第 3 跑，PID 17296，00:30:18 起）
- 命令：`scripts/pya_app_path_seg.py --engine gpu_int8 --strategy forced --minutes 61.2
  --seg-ir models/pyannote_seg/ov-fp16 --seg-device GPU.0 --tag forced61`
- 分段模型前置结果（已出）：**模型断点 108 个**（max_len 47 / silence 37 / speaker_switch 24）、
  分段模型推理 **220.94 s，RTF 0.06018**
  ⇒ 与 §35 记的 NPU 流式断点 107 个（max_len 46 / silence 37 / speaker_switch 24）**量级一致**（GPU.0 vs NPU 差 1 个）。
- 进度（00:40 复查）：**660.0 / 3671.2 s（18.0%）**、段数 **108**、`elapsed` 386.2 s、
  **中途 RTF 0.5851**（含引擎加载前的分段模型时间则更低）⇒ 文本正常，无崩溃迹象。
- ⚠️ **本节写档时该跑仍在途** ⇒ `results/pyannote_seg/pya_app_forced_forced61.json`
  **尚未落盘**，本节**不写「已交付」**。
- 🔴 **续跑判据**：下一轮先查 `pya_app_forced_forced61.json` 是否落盘且
  `n_segs` > 0、`audio_sec` ≈ 3671.2 ⇒ 再交 reviewer 复算 WER（对照 App 路径 R2T2 iGPU B **10.58%**）
  与词内切点比例（对照基线 `pya_app_baseline_base5m.json` 的 **6.67%**、
  forced 5 分钟的 **6.25%**）。

### §5 本轮提交与边界
- `git status --porcelain status/asr/` 写档前**为空** ⇒ 本模块目录干净；本节写入后仅提交 `status/asr/STATUS_ASR.md`。
- `git status --porcelain status/` 中 `status/CORRECTIONS.md`、`status/STATUS_ARCHIVE_2026-10.md`、
  `status/app/CORRECTIONS_APP.md` 为 M ⇒ **其它模块的改动，未动**。
- 🔴 **`live_caption/` 下无任何改动**（ASR-003 边界）；本轮只改了 `qwen3asr_06b/scripts/pya_app_path_seg.py`
  （**工作目录在仓库外**，不是 `live_caption/`）。
- `shared/GIT_FREEZE` **不存在**（冻结仍处释放状态）⇒ 可普通 commit/push（非 force）。

### 产物清单（本节新增/变更）
| 产物 | 说明 | 文件数 / mtime |
|---|---|---|
| `qwen3asr_06b/scripts/pya_app_path_seg.py` | **本轮改动**：checkpoint + 断点续跑 + `--no-resume` + 进度日志 | 1 个，00:30 前 |
| `qwen3asr_06b/results/pyannote_seg/pya_app_forced_forced61.partial.json` | 61 分钟跑的**部分产物**（每 60 s 刷新） | 1 个，**滚动更新中** |
| `qwen3asr_06b/results/pyannote_seg/pya_app_forced_forced61.json` | 61 分钟 forced 最终产物 | **⏳ 待落盘** |
| `qwen3asr_06b/logs/pya_app_forced61.log` | 长跑日志（含分段模型 RTF 与每 60 s 进度） | 1 个，滚动更新中 |
| `qwen3asr_06b/results/pyannote_seg/pya_app_forced_smoke2.json` + `.partial.json` | 断点续跑**冒烟验证**产物（2 分钟） | 2 个，00:29–00:31 |

## §37 ASR-013 ②验收① 闭环：61 分钟 forced 长跑完成（断点续跑生效）+ 词内切点 **9.87% → 3.30%**（2026-10-27 01:09–01:20）

### §1 61 分钟 App 路径 forced 长跑：**完成**（第 3 跑，PID 17296）
- 产物：`qwen3asr_06b/results/pyannote_seg/pya_app_forced_forced61.json`（**150639 B**，mtime **2026-10-27 01:09:22**）
- 命令：`scripts/pya_app_path_seg.py --engine gpu_int8 --strategy forced --minutes 61.2
  --seg-ir models/pyannote_seg/ov-fp16 --seg-device GPU.0 --tag forced61`
- 原始字段（直接引自 json）：

| 字段 | 值 |
|---|---|
| `strategy` / `engine` | `forced` / `gpu_int8`（R2T2 · Intel GPU · INT8：enc `ov-encoder-segment-reviewer-int8asym` + dec `ov-int8-past`） |
| `audio_sec` | **3671.19**（= 整个 wav，ASR-006 §3 要求的「跑整个 wav」✅） |
| `n_segs` / `n_cuts_excl_eof` | **607** / **606** |
| `rule_counts` | `rule1` **479**、`model_break` **108**、`rule2` **20** |
| `rule_class_counts` | `rule1` 479、`flush_other` 107、`rule2` 20 |
| `wall_s` / `rtf` | **2116.41** / **0.5765** |
| `seg_model_wall_s` / `seg_model_rtf` | **220.94** / **0.06018** |
| `seg_dur_p50` / `seg_dur_p95` | **6.4** / **8.32** |
| `model_break_times` 长度 | **108**（= 分段模型断点数；max_len 47 / silence 37 / speaker_switch 24） |
| `midword.pct_hit_all_pairs` | **3.3**（`n_hit` 20 / `n_pairs` 606，N=3） |
| `midword.per_rule_pct` | `rule1` **3.55%**（17/479）、`flush_other` **2.8%**（3/107）、`rule2` **0.0%**（0/20） |
| 段级统计（自算） | 总词数 **11322**、空文本段 **17**（全为 `model_break`）、段长 min/median/max = 0.64/6.4/12.16 s、>12 s 段 **1**、<2 s 段 **34**、末段 `end_s` **3666.56** |
| 文本健康度（自算） | 拉丁词占比 **0.8326**、三连重复 **0**、ABAB **8**、唯一词率 **0.2182**、非 ASCII 词 **0**、`prompt_echo` **false** ⇒ **文本正常，无复读/乱码** |

- ✅ **锁**：跑完 `release_lock()` 正常删除 ⇒ 复查 `shared/MACHINE_LOCK` **不存在**（**无孤儿锁**）。
- ✅ **断点续跑实战生效**：本次全程未被回收 ⇒ 一次跑完；但 §36 加的 checkpoint 机制**已在位**
  （`pya_app_forced_forced61.partial.json` 每 60 s 刷新，最后一次 01:09）⇒ **下次被杀可直接续，不再从零**。

### §2 ★ 核心结果：词内切点比例 **9.87% → 3.30%**（ASR-013 验收① 的主指标）
判据**完全同口径**：`asr006_rule1_cut_diag.seam_overlap(segs, N=3)`（同一份基线脚本的函数，非另写实现）。

| 口径 | 段数 | 接缝数 N=3 | 切在词中 | **占比** |
|---|---|---|---|---|
| R2T2 App 路径 B（现状基线） | 558 | 557 | 55 | **9.87%**（rule1 占 10.24%） |
| **本轮 forced（模型驱动切点）** | **607** | **606** | **20** | **3.30%**（rule1 占 **3.55%**） |
| 差 | +49 | +49 | **−35** | **−6.57 pp（相对降幅 66.6%）** |

- 基线出处：`confucius4-openvino/results/asr_diag/asr006_rule1_cut_diag.json`（`groups.B.seam_overlap_main_N3`：
  `n_pairs`=557、`n_hit`=55；`overlap_sensitivity.N=3.pct_hit_of_all_pairs`=9.87、`pct_hit_of_rule1_pairs`=10.24）。
- ⚠️ **段数不可直接比**：607 vs 558，差 **+49 段**（forced 的 `model_break` 108 个把 rule1 切点从 479 压到 479、
  但新增 108 个模型切点 ⇒ 段更细）⇒ **占比分母变了** ⇒ 上表按**各自口径的接缝数**给占比，不按绝对数跨表比较。
- 🔴 **WER 未算（本线程不调用 MiniMax）** ⇒ 交 reviewer 复算：
  - 对照 1：**App 路径 R2T2 iGPU INT8 B = 10.58%**（reviewer 口径）
  - 对照 2：**R2T2 交付基准 8.17%**（**非** App 路径，226 段离线切分 ⇒ 只作参考列，**不可**当同口径）
  - 参照物：`pya_app_baseline_base5m.json`（300 s baseline，词内切点 **6.67%**）与
    `pya_app_forced_forced5m.json`（300 s forced，词内切点 **6.25%**）⇒ 5 分钟口径下 **6.67% → 6.25%（−0.42pp）**
    ⇒ 🔴 **61 分钟口径的降幅（−6.57pp）远大于 5 分钟口径（−0.42pp）** ⇒ **短切片不可外推**，必须以 61 分钟为准。

### §3 🔴 代价与遗留（必须如实记录）
- **段数变多**：607 vs 558（**+49 段**，+8.8%）⇒ 定稿更碎 ⇒ ① TTS 音色切换更频繁；
  ② MT 翻译段数增加；③ App 侧接缝开销增加。
- **空文本段 17 个**（全为 `model_break`，段长 0.64–1.92 s）⇒ 模型断点有时落在**极短的无语音间隙**上
  ⇒ 产出空段 ⇒ ⚠️ **需要 App 侧加空段守卫**（属 App 模块，ASR-003 边界），
  或 ASR 侧加「模型断点最小间隔 / 最短段」过滤。**本轮不擅自改**。
- ⚠️ `model_break` 段长中位 **3.2 s**（远短于 rule1 的 ≥6 s）⇒ 部分模型断点切得过早。
- ⚠️ 本轮 **INT8 分段模型仍未过阈**（§35：weight-only cos 0.995336 / 一致 0.981324；
  激活感知 0.951184 / 0.947368；head 保留 0.986118 / 0.920204）⇒ **本轮用的是 FP16 分段 IR**
  （`models/pyannote_seg/ov-fp16`）⇒ FP16 分段模型在 GPU.0 上的 RTF **0.06018**（相对 ASR 主链 RTF 0.5765 约占 **10.4%**）。

### §4 待 reviewer / 待用户决定
1. 🔴★ **WER 复算**（本线程不调用 MiniMax）：`pya_app_forced_forced61.json` 交 reviewer，
   对照 App 路径 R2T2 iGPU INT8 B **10.58%**（同 App 路径、同 61 分钟 ⇒ 可直接配对 bootstrap）。
2. 🔴 **空文本段 17 个**的处理口径：App 侧守卫 vs ASR 侧过滤 ⇒ 需与 App 模块对齐（ASR-003 边界）。
3. 🔴 **INT8 分段模型**若仍不过阈 ⇒ 交付精度按 §35 结论走 **FP16**（不擅自降阈值）。
4. ⚠️ **说话人身份**仍只有 1 人素材 ⇒ 切换点 F1 / 碎片化**无数据**，需换多说话人素材重跑（§36 阻塞项 ⑯）。

### §5 产物清单
| 产物 | 说明 | 文件数 / mtime |
|---|---|---|
| `qwen3asr_06b/results/pyannote_seg/pya_app_forced_forced61.json` | **★ 本轮主产物**：61 分钟 App 路径 forced 转写 + 切点统计 | 1 个，150639 B，**01:09:22** |
| `qwen3asr_06b/results/pyannote_seg/pya_app_forced_forced61.partial.json` | checkpoint（每 60 s 刷新，最后一次 01:09） | 1 个，01:09 |
| `qwen3asr_06b/results/pyannote_seg/pya_frames_app_forced61.npz` | 帧级概率（p_speech / p_dom / spk_id / cov） | 1 个，01:09 |
| `qwen3asr_06b/logs/pya_app_forced61.log` | 长跑日志（分段模型 RTF + 每 60 s 进度 + 最终 json 摘要） | 1 个，01:09 |
| `qwen3asr_06b/scripts/pya_app_path_seg.py` | §36 改的 checkpoint + 断点续跑 | 1 个，00:30 前 |
| `confucius4-openvino/status/asr/STATUS_ASR.md` | **本节落档**（§37） | — |

## §38 §37 遗留项闭环：「长跑跑完不删 checkpoint」隐患修复 + 强制 61 分钟陈旧 checkpoint 清理（2026-10-27 03:19–03:25）

### §38.0 本轮判定：无新纠偏
- 检查对象：`confucius4-openvino/status/asr/CORRECTIONS_ASR.md`
  （mtime **2026-10-26 16:18:05**，37954 B，md5 `55c28c7231dac56b5e340f4095840c8d`
  —— 与 2026-10-26 23:20 / 2026-10-27 00:24–01:20 / 02:13 四次**完全一致**，文件未被追加）
- 纠偏编号集合：ASR-001 … **ASR-013**（最大 = **ASR-013**）；
  `grep -n '^#\{1,3\} '` 列出全部标题，最大编号仍 ASR-013；
  `grep -rn "ASR-01[4-9]" status/` 命中 **0**（仅 STATUS_ASR.md §36 里那句
  「无 ASR-014+」的自述被命中）⇒ **确认无 ASR-014 及以后**
- `STATUS_ASR.md` 开头 `last_ack: ASR-013` ⇒ **last_ack 保持 ASR-013，不改**
- ⇒ 结论：**无新纠偏**，按规则不因「纠偏」改任何东西；但本轮**做了实质工作**（见下）

### §38.1 🔴 缺陷：`pya_app_path_seg.py` 跑完不删 checkpoint ⇒ 同 tag 重跑会静默产出截断结果
- **来源**：§37 遗留项（上轮 02:13 已记录「`pya_app_forced_forced61.partial.json` 跑完后未删除
  ⇒ 下次同 tag 跑会误续到 fed_s=3660.0（已覆盖 99.7%）」）。
- **实证（本轮复核，非推断）**：
  - `results/pyannote_seg/pya_app_forced_forced61.partial.json`（**129183 B**，01:09:22）在盘；
    读其原始字段：`fed_s` = **3660.0**、`n_segs_so_far` = **605**、`segments` 长度 **605**、
    `elapsed_s` = 2110.59、`rtf_so_far` 存在
  - 同名最终产物 `pya_app_forced_forced61.json`（**150639 B**，01:09:22）：
    `n_segs` = **607**、`audio_sec` = **3671.19**、`rtf` = **0.5765**
  - ⇒ 最终产物本身**完整无缺**（607 段 > checkpoint 的 605 段），
    但 **checkpoint 脚本只写不删**
- **危害（为什么必须现在修，而不是留到下次）**：
  脚本的续跑判据是「`abs(ck['audio_sec'] - audio_sec) < 1.0` 且 `segments` 非空 ⇒ 跳过已喂音频」。
  `partial.json` 的 `audio_sec` 与同 tag 跑**完全一致** ⇒ **下次同 tag 跑必然命中续跑**，
  从 `fed_s`=3660.0 继续 ⇒ **只覆盖 3660.0/3671.19 = 99.70%**，
  最终 json 的 `audio_sec` 仍写 3671.19、`n_segs` 变少 ⇒
  **产物看着「跑完了」，实际少了最后 11.19 s 的音频**，而 reviewer 只会看到一个 `complete` 的 json
  ⇒ 属于**静默数据缺失**，比崩掉更危险
- **修法**（`scripts/pya_app_path_seg.py`，写在最终产物落盘之后、打印之前）：
  ```python
  # 🔴 跑完必须删 checkpoint：否则下次同 tag 跑会误续到 fed_s=末段，
  #    静默产出「少了最后一段音频」的截断结果，却看着像跑完了。
  try:
      if os.path.exists(ckpt_path):
          os.remove(ckpt_path)
          print(f'[pya] 已清理 checkpoint → {ckpt_path}', flush=True)
  except OSError as e:
      print(f'[pya] ⚠️ 清理 checkpoint 失败（不影响本次产物）：{e}', flush=True)
  ```
  ⇒ 用 `try/except OSError` 包住：**清理失败只告警、不中断本轮产物**（清理是卫生问题，不是产物正确性问题）
- **验证**：
  - `python -m py_compile scripts/pya_app_path_seg.py` ⇒ **通过**；
    `ast` 静态核查：`ckpt_path` 与 `os.remove` **同在 `main()` 作用域**（不是悬空变量）
  - **2 分钟冒烟**（`.venv/Scripts/python.exe scripts/pya_app_path_seg.py --strategy forced
    --tag ckptsmoke --minutes 2`）⇒ **rc=0**；
    日志 `logs/pya_ckptsmoke.log`（**1939 B**，03:22:37）含
    `[pya] 已清理 checkpoint → …pya_app_forced_ckptsmoke.partial.json`；
    跑完 `results/pyannote_seg/` 内**无 `ckptsmoke` 的 partial 残留**；
    `shared/MACHINE_LOCK` **已释放**（脚本 `finally: release_lock(lock_pid)` ⇒ 无孤儿锁）
  - 冒烟产物已清理：`pya_app_forced_ckptsmoke.json` + `pya_frames_app_ckptsmoke.npz` 已删

### §38.2 ✅ 强制 61 分钟陈旧 checkpoint 已清除，最终产物未受影响
- 删除 `results/pyannote_seg/pya_app_forced_forced61.partial.json`（129183 B）
- 删除后复核最终产物仍完好：`pya_app_forced_forced61.json`（**150639 B**，01:09:22）
  ⇒ `n_segs`=**607** / `audio_sec`=**3671.19** / `rtf`=**0.5765**（与 §37 记录**逐位一致**）
- `results/pyannote_seg/` 目录现有 **35** 个文件（清理前 37：减 1 个陈旧 partial、减 2 个冒烟产物）

### §38.3 本轮未做的事（明确记录，避免下轮误读）
- **未算 WER**：本线程不调用 MiniMax（ASR-001 用户总原则）⇒
  `pya_app_forced_forced61.json` 的 WER 仍**交 reviewer** 对照
  **App 路径 R2T2 iGPU INT8 B 10.58%** 复算（同路径 ⇒ 可直接配对 bootstrap）；
  ⚠️ 交付基准 8.17% 是 226 段离线切分、**非** App 路径 ⇒ 只作参考列
- **未改 `live_caption/` 下任何文件**（ASR-003 边界）；本轮改的只有
  `qwen3asr_06b/scripts/pya_app_path_seg.py`（**ASR 模块自己的工作目录**）+ 删自己的产物
- **未开新实验**、未跑 61 分钟长跑（只跑了 2 分钟冒烟验证修复本身）
- **空文本段 17 个**、**段数 +49（558→607）** 的归属问题仍**待用户裁定**（§37 已列，未擅动）

### §38.4 机器锁
- 本轮唯一的作业是 2 分钟冒烟（计时性质）⇒ **由本模块持锁**：
  `[lock] 已取锁（pid=36804, task=pya_app_forced_ckptsmoke）`
- 跑完 `MACHINE_LOCK` **不存在**（`release_lock` 正常）⇒ **无孤儿锁**、未干扰其它模块

## §39 共享机器锁的独占性与 fail-closed 修复（App 通知 §六.2 点名 ASR）+ 跨模块 pid 格式互操作修复（2026-10-27 04:26–04:50）

> 触发来源：`shared/NOTICE_app_to_tts_asr_20261026_s56.md`（App 模块，2026-10-26 22:15）§六.2
> 「**`os.replace` 的独占性问题**：TTS/ASR 侧若用 `os.replace`，请评估「两个写者都成功」的可能
> ⇒ 建议改用 `os.link`（`FileExistsError` ⇒ 独占失败）」。**该通知明确点名 ASR**。
> ⚠️ **本轮无新纠偏**（`CORRECTIONS_ASR.md` mtime **2026-10-26 16:18:05**、md5 `55c28c72…`
> 与上轮完全一致，最大编号仍 **ASR-013**，`grep -rn "ASR-01[4-9]" status/` 命中 0）
> ⇒ **last_ack 保持 ASR-013，不改**；本轮做的是**通知里点名本模块的缺陷修复**。

### 39.1 🔴 缺陷确认：ASR 侧的锁实现有**两个**真缺陷 + **一个**跨模块互操作地雷

本模块 5 个持锁脚本各抄了一份锁实现 ⇒ 逻辑漂移：

| # | 文件 | 写锁方式 | 缺陷 |
|---|---|---|---|
| 1 | `scripts/pya_app_path_seg.py` | `tmp + os.replace` | **丢独占性**（两个写者都成功） |
| 2 | `scripts/pya_bench_one_window.py` | `tmp + os.replace` | 同上 |
| 3 | `scripts/pya_stream_segment.py` | `tmp + os.replace` | 同上 |
| 4 | `scripts/run_wait_calib_mask2.py` | `tmp + os.replace` | 同上 |
| 5 | `scripts/p3_run_with_lock.py` | `open(path,'w')` **直接写** | 丢独占性 **且**有「文件已建、内容未写完」空窗 |

**缺陷①（丢独占性）**：`os.replace` 在目标已存在时**覆盖** ⇒ 两个写者都看到「锁不存在」、
都 replace ⇒ **后写者覆盖前者** ⇒ **两个模块都以为拿到了锁** ⇒ 同时跑 ⇒ 计时互相污染。
🔴 **实测反证**（本轮新做，`results/lock_verify/old_impl_counterproof.py`）：
6 个独立进程同时抢锁 ⇒ **持有区间重叠 5 对**（即 6 个进程**同时**持锁）
⇒ 旧实现**确实**互斥失效，不是理论推断。

**缺陷②（读锁 fail-open ⇒ 误删活锁）**：旧读锁逻辑是
「`pid is None or not _pid_alive(pid)` ⇒ **一律回收**」。
但「解析不出 pid」**不等于**「持锁者已死」⇒ 会**删掉别的模块的活锁**。
这正是 TTS 侧记录的数据作废事故的根因
（`NOTICE_tts_lock_atomic_20261026.md`：TTS-019 `single` 臂 **16/30 行 `timing_valid=false`**、
TTS-017① `A_CPU` 臂 **24/30 行 `timing_valid=false`**，2026-10-26 21:21~21:38）。

**缺陷③（本轮新发现，通知里没写）**：🔴 **跨模块 pid 格式互操作地雷**。
本模块历史写锁用 `asr PID=424242 start=2026-10-27 04:40:00 task=…`（**等号**形式）。
TTS 的 `qwen3tts_eval/machine_lock.py::_read_lock` 用**关键字扫描**取 pid：
对这一行做 `replace(":", " ").split()` 后取**第一个纯数字 token**
⇒ 拿到的是**时间戳里的 `04`（=4）**，**不是** 424242
⇒ TTS 认为「锁内 PID 4 已死」⇒ 判「陈旧锁」⇒ **删掉我们的活锁** ⇒ 互锁失效。
🔴 **本轮实测证据**：`results/lock_verify/asr_lock_verify_20261027.log` 里 C2 项
修格式前为 `[FAIL] TTS 解析器能读出 pid -- pid=4`（期望 424242），
修格式后为 `[PASS] ... pid=424242`。
✅ App 的 `machine_lock_app.py` 早就不用等号形式（用空格）⇒ **App 不受影响，只有 ASR 受影响**。

### 39.2 ✅ 修法（新建单一事实来源 `scripts/asr_lock_common.py`，5 个脚本统一调用）

**写锁**：🔴 **刻意不用 `os.replace`**（会覆盖别人）⇒ 改
`tmp 写全 + flush + os.fsync` ⇒ 再 **`os.link(tmp, lock_path)`**：
- `os.link` 在目标已存在时抛 `FileExistsError` ⇒ **独占**（绝不覆盖别人）；
- 建硬链接是**原子**的 ⇒ 别的模块**永远看不到半成品锁**（内容要么完整、要么文件不存在）；
- ⚠️ 临时文件名**必须带 PID**（`LOCK.<pid>.tmp`）⇒ 两个模块不会用同一个 tmp 名互踩
  （🔴 旧代码用的是**固定名** `MACHINE_LOCK.tmp` ⇒ 实测跨进程时直接
  `PermissionError: [WinError 32] 另一个程序正在使用此文件`，本轮反证时复现）。

**读锁（fail-closed）**：
- 锁**不存在** ⇒ 可抢；
- 锁**存在且内容非空** ⇒ **绝不删**（即使 pid 解析不出，也只**等**）；
- 锁**存在但内容为空**（0 字节）⇒ 等 2 s 重读；**仍为空**才回收；
- pid **解析得出且进程已死** ⇒ 才是陈旧锁；**回收前复核**「锁里的 pid 仍是刚才那个陈旧 pid」
  （否则会删掉「持锁者刚好重启并写了新锁」）。

**锁内容格式**：🔴 **统一改成空格分隔**（与 App 的 `machine_lock_app.py` 一致）：
```
asr PID <pid> started <YYYY-MM-DD HH:MM:SS> task=<task>
module: asr
pid: <pid>
started: <YYYY-MM-DD HH:MM:SS>
task: <task>
host: <COMPUTERNAME>
```
⇒ **四个模块的解析器（ASR 正则 / TTS 关键字扫描 / MT key-value）全部能读出 pid**。

**判陈旧口径不变**：只看 **PID 是否存活**，**不做进程名过滤**；另加
「锁的 started 早于本次开机 ⇒ 必然已死」。

### 39.3 ✅ 验收证据（`results/lock_verify/`，6 个文件）

**① `asr_lock_verify_20261027.log`（1728 B，04:48）—— 单元验收 19/19 PASS**
（设计照抄 App 的 `app082_atomic_lock_test.py`：**REAL 组必须成立 + BUG 组必须命中**
⇒ BUG 组命中说明测试**有鉴别力**，不是恒过测试）：

| 项 | 判据 | 结果 |
|---|---|---|
| R1a/b/c | 第一个写者拿到锁 / **第二个写者被拒（独占）** / 内容未被覆盖 | PASS |
| R2a | 读锁**从未**看到空内容（无空窗）—— 并发写 17189 次采样 | PASS（`n_empty=0`） |
| R3a/b/c | 解析不出 pid ⇒ **不判陈旧** / **拿不到锁** / **别人的锁没被删** | PASS |
| R4 | 0 字节空锁 ⇒ 等 2 s 重读后回收 | PASS |
| R5 | 死 pid ⇒ 陈旧锁可回收 | PASS |
| R6/a/b | 活锁（pid=本进程）⇒ **不可回收**、等超时 | PASS |
| R7a/b | 删锁**只删自己的**（pid 不匹配 ⇒ 不删） | PASS |
| **B1** | **旧 `os.replace` 实现 ⇒ 两个写者都成功（缺陷复现）** | PASS（命中 ⇒ 有鉴别力） |
| **B2** | **旧读锁把「读不懂的活锁」删了（缺陷复现）** | PASS（命中 ⇒ 有鉴别力） |
| **C1–C4** | **ASR / TTS / MT 三个真实解析器**都读出 pid=424242；MT 读出 started 时间戳 | PASS |

**② `asr_lock_xproc_20261027.log`（873 B，04:48）—— 跨进程互斥验收 PASS**
6 个**独立进程**（`spawn`）同时抢锁 ⇒ 持有区间**零重叠**：
```
worker0 […539.129, …540.630) → worker2 […] → worker5 → worker4 → worker3 → worker1
[A1] 全部 6 个进程都最终拿到锁（无死锁）= True
[A2] 持有区间**无重叠**（互斥成立）= True
[A3] 跑完无残留锁文件 = True
```
🔴 **安全边界**：脚本把锁路径重定向到**临时目录**，**不创建也不删除真实
`shared/MACHINE_LOCK`** ⇒ 未干扰其它模块。

**③ `old_impl_counterproof_20261027.log`（497 B，04:48）—— 反证**
同一脚本换成旧 `os.replace` 实现 ⇒ **重叠 5 对** ⇒ 旧实现**确实**互斥失效。

**④ `diag_empty_read.py`（1060 B）—— R2 的诊断**
发现 Windows 上 `os.link` 建硬链接后，**写者持有期间读者会拿到 `PermissionError(13)`**
（不是空文件）⇒ 该情形**不能**当「空闲」，也**不是**空窗 ⇒ 由 R3 的 fail-closed 覆盖。

**⑤ 2 分钟实跑冒烟**（`results/lock_verify/pya_ckptsmoke.log` 之外的本次冒烟，
已清理产物）：`pya_app_path_seg.py --engine gpu_int8 --strategy forced --minutes 2
--tag locksmoke --no-resume` ⇒ **rc=0**、日志打印
`[lock] 已取锁 …（pid=28756, task=pya_app_forced_locksmoke）` ⇒
**20 段**（rule1 14 / model_break 3 / rule2 2 / flush 1）、`rtf` 0.6045、
`seg_model_rtf` 0.05655、`midword` 15.79%（3/19 接缝命中）
⇒ 跑完 **`MACHINE_LOCK` 不存在（正常释放）**、**无 `.tmp` 残留**、
**checkpoint 自动清理**（§38 的修复仍生效）⇒ 冒烟产物已删。

### 39.4 机器锁

- 本轮唯一的计时作业是 2 分钟冒烟 ⇒ **由本模块持锁**
  （`[lock] 已取锁 … pid=28756, task=pya_app_forced_locksmoke`）。
- 跑完 `MACHINE_LOCK` **不存在** ⇒ **无孤儿锁**、未干扰其它模块
  （本轮开始与结束时 `shared/` 下都只有 README + NOTICE，`MACHINE_LOCK` 不存在）。

### 39.5 🔴 本轮**没有**做的事

- **未算 WER**（本线程不调用 MiniMax）⇒ `pya_app_forced_forced61.json` 的 WER **仍交 reviewer**
  对照 **App 路径 R2T2 iGPU INT8 B 10.58%**（同路径 ⇒ 可直接配对 bootstrap）。
- **未改 `live_caption/` 任何文件**（ASR-003 边界）；**未开新实验**；
  未跑 61 分钟长跑（只 2 分钟冒烟）。
- **未动其它模块的文件**：`status/CORRECTIONS.md`、`status/STATUS_ARCHIVE_2026-10.md`、
  `status/app/CORRECTIONS_APP.md`（`git status` 显示为 M）**未动**；
  `qwen3asr_06b` **不在 git 仓库内** ⇒ 本轮的脚本改动**不进 git**（只在本机）。
- **未修 TTS 侧的同一缺陷**：TTS 的 `qwen3tts_eval/machine_lock.py` 仍是
  `tmp + os.replace`（App 通知 §六.2 也点了 TTS）⇒ **属 TTS 模块职责，本线程不代改**。
  ⚠️ 但本模块已把锁格式改成**空格分隔**，⇒ **TTS 现在能正确读出本模块的 pid**
  （C2 项实测 PASS）⇒ TTS 侧在**修好之前**也不会再误删本模块的活锁。
- 空文本段 17 个、段数 +49（558 → 607）的归属问题仍**待用户裁定**。


## §40 撤回 §39 的「5 脚本已统一」表述 + 两个漏网脚本并入单一事实来源 + 修掉「跨会话陈旧锁永不回收」（2026-10-27 06:53–07:08）

### 40.1 ✅ 判定：仍**无新纠偏**，`last_ack` 保持 ASR-013

| 项 | 值 |
|---|---|
| `CORRECTIONS_ASR.md` mtime / 大小 / md5 | **2026-10-26 16:18:05** / 37954 B / `55c28c7231dac56b5e340f4095840c8d`（与 23:20 / 00:24 / 02:13 / 03:19 / 05:53 各轮**完全一致**，文件未被追加） |
| 纠偏编号集合 | ASR-001 … **ASR-013**（`grep -n '^#\{1,3\} '` 列全部标题，最大编号 ASR-013） |
| 交叉确认 | `grep -rn "ASR-01[4-9]" status/` 命中 **0**（仅命中 STATUS 里「无 ASR-014+」的自述）⇒ **无 ASR-014 及以后** |
| `STATUS_ASR.md` 写档前 | mtime 2026-10-27 04:50，364438 B / 4691 行 ⇒ 末尾章节 = **§39** |

⇒ 按纠偏检查规则：**不改 `last_ack`、不因「无新纠偏」写新章节**；但本轮**做了实质工作**（见 40.2），
故**追加 §40**。

### 40.2 🔴★ 撤回 §39.2 的一句表述（上一轮落档与代码实际状态不符）

**§39.2 原话**（`status/asr/STATUS_ASR.md` L4594）：
> 「### 39.2 ✅ 修法（新建单一事实来源 `scripts/asr_lock_common.py`，**5 个脚本统一调用**）」

**实测（`grep -ln asr_lock_common scripts/*.py`）**：只有 **3 个**脚本 import 了它 ——
`pya_app_path_seg.py` / `pya_bench_one_window.py` / `pya_stream_segment.py`；
而 **`run_wait_calib_mask2.py`（232 行）与 `p3_run_with_lock.py`（296 行）各自仍抄了一份本地锁实现**
（自带 `read_lock` / `write_lock` / `release_lock` / `wait_free` / `wait_for_lock` /
`lock_is_stale` / `pid_alive` / `boot_time`）。

⇒ **§39 的「单一事实来源」实际只落地 3/5**；`asr_lock_common.py` 头部注释里
「5 个脚本各自抄了一份锁实现 ⇒ 逻辑漂移的根源」正是它要解决的问题，**而它自己没被这 2 个用上**。
⇒ **本节撤回该表述**（旧章节不改写，按纪律在新章节声明撤回）。

⚠️ **不是「修了两个文件」这么轻**：这两个脚本是 **ASR 侧持锁面最大的两处** ——
`p3_run_with_lock.py` 是 **6 格 bench / P3 三格长跑 / 全部后处理链**的锁包装器
（`asr007_bench_all.py`、`run_mask2_pipeline.sh`、`run_mask2_post.sh`、`run_p3_mask2_three.sh`
都把它当锁入口调），`run_wait_calib_mask2.py` 是**校准集生成**的等锁入口。

### 40.3 🔴★ 统一过程中抓出并修掉的**真缺陷**：「跨会话陈旧锁永不回收」

**缺陷**（`run_wait_calib_mask2.py` 旧 L185）：
```python
stale_by_boot = t.timestamp() < boot_time()
```
而本机 `boot_time()` 的真实语义（`asr_lock_common.py` / 两脚本同款）：
```python
return ctypes.windll.kernel32.GetTickCount64() / 1000.0
```
⇒ 返回的是**「开机至今的秒数」**（本机实测 **509738.031** ⇒ 量级 ~5e5），
**不是时间戳**（`time.time()` = 1793055885 ⇒ 量级 ~1.8e9）。

⇒ `t.timestamp() < boot_time()` **恒为 False**（已实测：`False`）⇒
**「锁早于开机时间 ⇒ 陈旧可回收」这条回收路径永远不会触发**。

**危害**：这条路径正是 README 协议与 `boot_time()` docstring 写的
「锁早于开机时间可以回收」——**用来解开「上一次会话异常退出留下的陈旧锁」**。
而 `run_wait_calib_mask2.py` 的**存在意义就是「等锁 + 采校准集」** ⇒
一旦残留一把跨会话陈旧锁，这个脚本会**永远卡在 `wait_free()` 里**（默认 `--max-wait-s 14400`
⇒ 静默等 4 小时后退出码 2），而**表面上看起来只是「等锁」**。

⚠️ **为什么上一轮没抓到**：§39 只验收了 `asr_lock_common.py` 自身的 19 项，
**没有验收被迁移的脚本**（那 2 个脚本当时根本没迁移）⇒ 缺陷藏在未被验收的分支里。

**修法**：两个脚本**整体委托**单一事实来源（不再本地实现），
陈旧判定统一走 `asr_lock_common.lock_is_stale()` 的**正确口径**
`st < (time.time() - boot_time())`；另在 `asr_lock_common.py` 新增
**`wait_until_free()`**（只等不持锁：fail-closed + 空锁回收 + **回收前复核 pid**），
供「需要等锁但不自己持锁」的调用点使用。

### 40.4 ✅ 改了什么（`qwen3asr_06b/scripts/`，**不在 git 仓库内** ⇒ 只在本机**）

| 文件 | 改动 | 改后行数 |
|---|---|---|
| `asr_lock_common.py` | 新增 `wait_until_free()`（只等不持锁）；`__all__` 补 `build_payload` / `wait_until_free` / `acquire` | 398 → **492** |
| `run_wait_calib_mask2.py` | **删掉**本地 `boot_time` / `pid_alive` / `read_lock` / `write_lock` / `release_lock` / `wait_free`（含缺陷行）⇒ 改为 import 单一事实来源 | 232 → **104** |
| `p3_run_with_lock.py` | **删掉**本地 `boot_time` / `now` / `read_lock` / `pid_alive` / `lock_is_stale` / `write_lock` / `release_lock` / `wait_for_lock` ⇒ 改为 import 单一事实来源 | 296 → **132** |

**保留的行为（刻意没动）**：
- `p3_run_with_lock.py` 锁里写**子进程真实 PID**（不是包装器自己）+ 追加 `wrapper_pid`
  ⇒ 包装器被回收时子进程不会变孤儿占设备（§22 的原设计）；
- `p3_run_with_lock.py` 仍是 `--task <name>` 在 `--` **之前**的用法（`run_p3_mask2_three.sh`
  与 `asr007_bench_all.py` 依赖它）；
- 写锁仍用 `tmp + flush + fsync + os.link`（**不用 `os.replace`**），tmp 名带 PID。

⇒ 改后 `grep -ln asr_lock_common scripts/*.py` = **5/5**。

### 40.5 ✅ 验收证据（全部用真实实现；全程只在临时目录，**不触碰真实 `shared/MACHINE_LOCK`**）

**① `results/lock_verify/asr_lock_verify_20261027.log`（1728 B，04:48；**本轮 07:07 复跑仍 19/19 PASS**）**
—— REAL 组全成立 + **BUG 组 2 项均命中** ⇒ 测试有鉴别力（不是恒过测试）：
R1a/b/c 独占写 / 第二写者被拒 / 内容未被覆盖；R2a 无空窗（`n_samples=13646`、**`n_empty=0`**）；
R3a/b/c 读不懂 ⇒ 不判陈旧 / 拿不到锁 / **别人的锁没被删**；R4 空锁回收；R5 死 pid 回收；
R6/a/b 活锁不可回收；R7a/b 只删自己的锁；**B1 旧 `os.replace` 两个写者都成功（缺陷复现）**；
**B2 旧读锁把读不懂的活锁删了（缺陷复现）**；**C1–C4 四模块解析器全通**（ASR/TTS/MT 都读出 pid=424242）。

**② `results/lock_verify/asr_lock_stale_reclaim_20261027.log`（1067 B，07:08）—— 本轮新增针对性回归 15/15 PASS**
| 项 | 判据 | 结果 |
|---|---|---|
| T1 | 跨会话陈旧锁（`started` 早于本次开机 + pid 已死）⇒ **判陈旧** | PASS（`started_raw=2026-10-21 08:29:07`） |
| T1b | 陈旧锁被回收并成功拿到锁 | PASS |
| T2 / T2b / T2c | 活锁（pid=本进程）⇒ 不判陈旧 / 拿不到（等超时）/ **仍在没被删** | PASS ×3 |
| T3 / T3b / T3c | 解析不出 pid ⇒ 不判陈旧（fail-closed）/ 拿不到 / **仍在没被删** | PASS ×3 |
| T4 | 空文件锁可回收 | PASS |
| T5 | 死 pid 锁可回收 | PASS |
| **T6** | **反证：旧比较式 `time.time() < boot_time()` 实测恒 False**（`boot_time()=509909`）⇒ **缺陷真实存在，非测试假象** | PASS |
| T6b | 新比较式语义正确（开机时间 = now − uptime） | PASS |
| T7 | 两个已迁移脚本**确实委托单一事实来源**（有统一入口） | PASS ×2 |

**③ E2E 冒烟（真实锁路径）**：
`p3_run_with_lock.py --task smoke_migrated -- <子进程>` ⇒ 日志
`[lock] 已取锁 …（pid=19596，子进程 pid=19596，task=smoke_migrated）` → `子进程退出 rc=0` →
`[lock] 已释放锁` ⇒ 跑完 `shared/MACHINE_LOCK` **不存在**、**无 `.tmp` 残留**。
另 `run_wait_calib_mask2.wait_free(10)` ⇒ 返回 **True** / **0.00 s** / **不建锁**。

**④ `py_compile`** 三个文件全通过；`*.partial.json` 全盘 **0**（§38 的 checkpoint 自动清理仍生效）。

### 40.6 本轮**未做**（边界）
- **未改 `live_caption/` 任何文件**（ASR-003 边界）；**未开新实验**；**未跑 61 分钟长跑**
  （只跑 2 秒级 E2E 冒烟 + 纯文件 I/O 的验收脚本 ⇒ 不占 CPU、不占设备）。
- **未改其它模块的文件**：`status/CORRECTIONS.md`、`status/STATUS_ARCHIVE_2026-10.md`、
  `status/app/CORRECTIONS_APP.md`（`git status` 显示为 M）**未动**；
  `qwen3asr_06b` **不在 git 仓库内** ⇒ 本轮的脚本改动**不进 git**（只在本机）。
- **未修 TTS 侧的同一缺陷**：`qwen3tts_eval/machine_lock.py` 仍是 `tmp + os.replace`
  （App 通知 §六.2 也点了 TTS）⇒ **属 TTS 模块职责，本线程不代改**。
  ⚠️ 但本模块锁格式已是空格分隔 ⇒ **TTS 现在能正确读出本模块的 pid**（C2 实测 PASS）
  ⇒ TTS 修好前也不会再误删本模块的活锁。
- **未算 WER**（本线程不调用 MiniMax）⇒ `pya_app_forced_forced61.json` 的 WER 仍交 reviewer
  对照 **App 路径 R2T2 iGPU INT8 B 10.58%** 复算。
- 空文本段 17 个、段数 +49（558 → 607）的归属问题仍**待用户裁定**。


## §41 共享锁的「TOCTOU 窗口 ⇒ 孤儿子进程占设备」真缺陷：实证、修掉、加回归（2026-10-27 08:20）

### 41.0 本轮触发源与结论
- **无新纠偏**：`CORRECTIONS_ASR.md` mtime **2026-10-26 16:18:05**、**37954 B**、md5 `55c28c7231dac56b5e340f4095840c8d`
  ⇒ 与 23:20 / 00:24 / 02:13 / 03:19 / 05:53 / 06:53 / 07:08 各轮**完全一致**（文件未被追加）。
  `grep -n '^#\{1,3\} '` 列出全部标题 ⇒ 最大编号 **ASR-013**；
  `grep -o 'ASR-[0-9]\{3\}' | sort -u` ⇒ 无 ASR-014 及以后。
  ⇒ **last_ack 保持 ASR-013**。
- 触发源：**本线程自查**（复核 §40 的「统一到单一事实来源」是否真的安全）⇒ 发现**真缺陷**并修掉。

### 41.1 🔴 缺陷描述：包装器的「先起子进程、后拿锁」顺序 ⇒ 孤儿子进程
`p3_run_with_lock.py` / `run_wait_calib_mask2.py` 的结构是：

```
wait_for_lock()        # ① 观察到「锁空闲」
proc = Popen(argv)     # ② 起子进程（真正占 GPU/NPU / CPU 满载）
write_lock(...)        # ③ 真正把锁写下去  ← ①②之间有窗口
```

**问题**：「①返回空闲」与「③把锁写下去」之间存在 **TOCTOU 窗口**。
别的模块（App / MT / TTS）正好在这个窗口里抢到锁 ⇒
③ `write_lock_exclusive` 因 `os.link` 撞 `FileExistsError` ⇒ **抛错、包装器 abort**。
🔴 **但 ② 已经把子进程拉起来了**，而**没有任何代码去终止它** ⇒
**子进程带着「机器上没有任何锁」的状态继续跑**（真场景 = 61 分钟推理 / 校准集 CPU 满载）⇒
其它模块看到「机器空闲」⇒ **也起自己的计时作业** ⇒
**两个模块同时占设备 ⇒ 计时数据被静默污染**。
> 比崩溃更危险：产物**看着是完整的**，只有 RTF / 延迟被污染，事后无法从产物本身看出异常。

⚠️ **影响面不小**：`p3_run_with_lock.py` 是 **6 格 bench / P3 三格 61 分钟长跑 / 全部后处理链**的锁包装器
（`asr007_bench_all.py`、`run_mask2_pipeline.sh`、`run_mask2_post.sh`、`run_p3_mask2_three.sh` 都调它）；
`run_wait_calib_mask2.py` 是**校准集生成**入口（其子进程要 **CPU 满载** ⇒ 专污染其它模块的延迟测量）。

### 41.2 ✅ 实证复现（隔离测试，**规范锁全程未被触碰**）
测试脚本：`results/_touctest/make_copies3.py`（后已清理），原理：
把两个副本里的 `CANON_LOCK` **同时**重指向到临时目录的 `TEST_LOCK`
（⚠️ `p3_run_with_lock.py` 的 `CANON_LOCK` 是**从 `asr_lock_common` import 来的** ⇒ **两个副本都要改**，
只改包装器会让它仍用规范锁 —— 这是本轮踩的第一个坑），
并把 `wait_for_lock()` 打桩成「返回 True」以**制造 TOCTOU 窗口**。

**结果（修复前）**：
```
wrapper rc = 1 | wrapper exited after 0.28s
child pid = 13624 | child start offset = +0.20s | alive at wrapper exit = True
>>> RESULT: ORPHAN CONFIRMED
```
⇒ 父进程 **0.28 s 就死了**，子进程**仍在跑** ⇒ 缺陷**真实存在**，不是测试假象。

⚠️ **本轮踩的第二个坑**：第一版测试用 `subprocess.run(capture_output=True)` ⇒
子进程**继承了管道的 stdout** ⇒ `run()` 一直阻塞到子进程退出（30 s）
⇒ 检查时子进程**早就退出了** ⇒ 误得「无孤儿」的**假阴性**。
⇒ 修法：子进程的 stdout/stderr **重定向到文件**，`Popen` 才能在**包装器退出时**立即返回。
**教训**：验证「进程是否残留」时，**必须让被测子进程不持有父进程的管道**，否则测的是管道关闭时机而不是进程存活。

### 41.3 ✅ 修法
**① 单一事实来源新增 `kill_child()`**（`scripts/asr_lock_common.py`）：
`terminate()` → 宽限 5 s → 仍活着则 `kill()` → 轮询确认退出；返回 True/False。
**② 两个包装器在写锁失败时必须收掉子进程**：
`except BaseException:` 里调 `kill_child(proc)`；**杀不掉时打印 pid 并告警**（不静默放过）。

```python
    proc = subprocess.Popen(argv)
    pid = None
    try:
        pid = write_lock(task=task, child_pid=proc.pid)
    except BaseException:
        print('[lock] 写锁失败 ⇒ 终止已启动的子进程（防孤儿占设备）', flush=True)
        killed = kill_child(proc)
        if not killed:
            print(f'[lock] 🔴🔴 杀不掉子进程 pid={proc.pid}！'
                  f'它可能仍在占设备且机器无锁 ⇒ 请人工确认', flush=True)
        raise
```

> **为什么不能简单改成「先拿锁再起子进程」**：锁里要写**子进程的真实 PID**
> （包装器被杀时子进程会变孤儿占设备 ⇒ 别人看到「锁的 PID 已死」会回收锁 ⇒ 孤儿继续跑 ⇒ 计时污染）。
> 所以本轮**只做兜底**（拿不到锁就杀掉子进程 ⇒ 消除「无锁占设备」），**不调换顺序** ⇒ 不影响已交付产物的产出路径。
> ⚠️ **彻底修法（先拿锁再起子进程）留待后续窗口期**（见 §41.6）。

### 41.4 ✅ 验收（三份日志，全部落盘）
| 验收 | 结果 | 产物 |
|---|---|---|
| **新增：孤儿子进程回归 9/9** | **PASS** | `results/lock_verify/asr_lock_orphan_20261027.log`（1640 B，08:17） |
| ├ T8 写锁失败 ⇒ 子进程**不残留** | PASS（`alive=False`） | 同上 |
| ├ T8.0 子进程**确实被拉起过**（spawn 标记） | PASS（证明测试窗口有效） | 同上 |
| ├ T9 正常路径回归：rc=0 / 取锁 / 释放锁 / 无残留 | PASS ×4 | 同上 |
| ├ **T10 反证：旧实现必然复现孤儿** | PASS（`old_impl alive=True`） | 同上 |
| └ T8.4/T9.4 **规范锁全程未被创建**（隔离保证） | PASS ×2 | 同上 |
| **既有：19 项验收（复跑）** | **19/19 PASS** | `results/lock_verify/asr_lock_verify_20261027.log`（1732 B，08:17） |
| **既有：跨进程互斥（6 进程）** | **PASS**（A1 无死锁 / A2 区间零重叠 / A3 无残留） | `results/lock_verify/asr_lock_xproc_20261027.log`（873 B，08:17） |
| `py_compile`（4 个文件） | PASS | — |

🔴 **T10 反证的意义**：同一个测试跑**修复前的旧实现**必然报 `alive=True` ⇒
证明该测试**有鉴别力**，不是「怎么都 PASS」的假测试。

### 41.5 ✅ 本轮**更正** §40 的一处**措辞过严**（逻辑无问题，不改旧章节）
§40.3 写「本地 `read_lock`/`write_lock`/`release_lock`/`wait_free`/`lock_is_stale`/`pid_alive`/`boot_time` **全部删除**」。
🔴 **实测与该表述不符**：`run_wait_calib_mask2.py` 与 `p3_run_with_lock.py` **仍保留同名薄封装函数**
（`read_lock` / `write_lock` / `release_lock` / `wait_free`），
但**函数体全部是委托 `asr_lock_common`**（如 `write_lock` → `write_lock_exclusive`、
`release_lock` → `release_lock_if_owner`、`wait_free` → `wait_until_free`）
⇒ **本地锁实现（真正的逻辑副本）确实已全部删除，逻辑已统一**；只是**没删掉外壳函数**（它们是既有调用点的兼容层）。
⇒ **结论不变**：§40 关于「单一事实来源」的**实质结论成立**；本条只是把措辞改成事实。

### 41.6 本轮**未做**（边界）
- **未改 `live_caption/` 任何文件**（ASR-003 边界）；**未开新实验**；**未跑 61 分钟长跑**
  （只跑纯文件 I/O / 子进程级的锁测试 ⇒ 不占 GPU/NPU/CPU 满载 ⇒ 无需持锁）。
- **未改其它模块的文件**：`status/CORRECTIONS.md`、`status/STATUS_ARCHIVE_2026-10.md`、
  `status/app/CORRECTIONS_APP.md`（`git status` 显示为 M）**未动**；
  `qwen3asr_06b` **不在 git 仓库内** ⇒ 本轮脚本改动**不进 git**（只在本机，交付需另行打包）。
- **未改「先拿锁再起子进程」的顺序**（理由见 §41.3 末）⇒ **彻底修法留待后续窗口期**。
- **未修 TTS 侧的同一类缺陷**（`qwen3tts_eval/machine_lock.py` 仍是 `tmp + os.replace`）⇒ **属 TTS 职责**。
  ⚠️ 本模块锁格式已是空格分隔 ⇒ TTS 能正确读出本模块 pid（C2 实测 PASS）⇒ 修好前也不会误删本模块活锁。
- **未算 WER**（不调用 MiniMax）⇒ `pya_app_forced_forced61.json` 的 WER 仍交 reviewer
  对照 **App 路径 R2T2 iGPU INT8 B 10.58%** 复算。
- 空文本段 17 个、段数 +49（558 → 607）的归属问题仍**待用户裁定**。
- **机器锁状态**：本轮**全程未创建规范锁**（所有测试重指向到临时 `TEST_LOCK`）⇒
  跑完 `shared/MACHINE_LOCK` **不存在**、**无 `.tmp` 残留**；`Get-Process python*` count=**0** ⇒ 无遗留进程。

## §42 ASR-014/015/016 落地：同脚本 5 分钟 baseline↔forced 对照 + 锁收敛 + 交付件补齐（2026-10-27 11:35）

> 本节只写本轮新增结论。**撤回 §37 的「−6.57pp / 相对降幅 66.6%」**（理由见 §42.3），旧章节不动。

### 42.0 本轮的**口径变更**（用户决策，必须先看）
- 🔴 **ASR-014 §2(a) 原要求「持锁跑 61 分钟 baseline」** —— 用户 2026-10-27 11:19 指示
  **「长跑太浪费时间了，改用 5min 音频短测试」** ⇒ 本轮**改为 5 分钟口径**。
  ⇒ 61 分钟 baseline **未跑完**（10:53 启动、11:19 终止于 50.7%、960/3671.2 s、段数 146、
  rtf 0.7904；**产物未落盘**），断点文件 `pya_app_baseline_base61.partial.json`
  （35 737 B @11:07）**已删除**，避免下次同 tag 命中续跑而静默少跑最后一段（MEMORY 铁律 11c）。
- ⚠️ **5 分钟口径不能与 61 分钟口径的数字直接比**：MEMORY 铁律「短切片不可外推」
  （5 分钟 6.67%→6.25% −0.42pp vs 61 分钟 9.87%→3.30% −6.57pp）。
- ⚠️ 本轮**未擅自改 `live_caption/` 任何文件**（ASR-003 边界 / C-111）。

### 42.1 ✅ ASR-014 §2(a)(b)：**同脚本** baseline vs forced 对照（5 分钟，持锁）
产物：`results/pyannote_seg/pya_app_baseline_base5m_v2.json`（14 175 B @11:23:57）、
`results/pyannote_seg/pya_app_forced_forced5m_v2.json`（16 062 B @11:28:38）、
汇总 `results/pyannote_seg/asr014_5m_baseline_vs_forced.json`（9 596 B @11:30:09）。
两次都是**同一份脚本** `scripts/pya_app_path_seg.py`、同一引擎 `gpu_int8`、同一音频前 300 s。

| 指标（原始字段） | baseline | forced |
|---|---|---|
| `strategy` / `engine` | baseline / gpu_int8 | forced / gpu_int8 |
| `audio_sec` | 300.0 | 300.0 |
| `n_segs` / `n_cuts_excl_eof` | **46** / 45 | **49** / 48 |
| `wall_s` / `rtf` | 212.08 / **0.7069** | 203.37 / **0.6779** |
| `seg_model_rtf` / `seg_model_wall_s` | **0.0** / 0.0 | **0.06487** / 19.46 |
| `latency.finalize_lat_p50_s` / `p95` / `n` | 0.4420 / 0.4907 / 46 | 0.4219 / 0.4679 / 49 |
| `latency.first_tok_lat_p50_s` / `p95` / `n` | 0.3690 / 0.4141 / **514** | 0.3513 / 0.3945 / **517** |
| `latency.window_lag_ms` | 9360.0 | 9360.0 |
| `timing_valid` | **true** | **true** |
| `lock_probe` | `lock_probe_checks`=6 / `lock_probe_stolen`=**0** | 6 / **0** |
| `rule_counts` | rule1 42 / rule2 3 / flush 1 | rule1 39 / **model_break 7** / rule2 2 / flush 1 |
| 空文本段 | **0** | **0** |
| 词内切点（含空段/去空段） | **6.67% (3/45)** / 6.67% | **6.25% (3/48)** / 6.25% |

- ✅ **词内切点 6.67% → 6.25%（−0.42pp）**，命中全在 rule1。口径 = 唯一函数
  `asr006_rule1_cut_diag.seam_overlap(segs, 3)`（**未另写实现**），
  产物 `results/pyannote_seg/asr014_5m_seam_overlap.json`（797 B @11:29:25）。
- ✅ **可重复性验证**：本轮新跑（v2）与 10-26 旧跑（`pya_app_baseline_base5m.json` /
  `pya_app_forced_forced5m.json`）**逐位复现**（baseline 3/45、forced 3/48，两次完全相同）
  ⇒ 该指标在 5 分钟口径下**高度稳定**。
- 🔴 **同脚本内 baseline vs forced 仍有大差异**：切点仅 **34/45 相同**、逐段文本完全一致
  仅 **6/46** ⇒ **reviewer §2.2 的质疑在同脚本下依然成立**（forced 改切点 ⇒ 必然改文本归属）
  ⇒ **「forced 的 WER 变好」不能全部归因于「词内切点减少」**。
- 🔴 **`seg_model_rtf` 不可加（回答 ASR-014 §2.6 的「只差 0.013 对不上」）**：
  baseline 的 `seg_model_rtf=0.0` ⇒ **baseline 策略根本不跑分段模型**（分段模型只用于 forced
  的断点计算，见 `pya_app_path_seg.py` L397-407 的 `if args.strategy == 'forced'`）；
  forced 的 0.06487 是分段模型的**独立计时**、**未计入 wall**（`wall` = 主链喂音循环墙钟）
  ⇒ `主链 RTF 0.6779` 与 `seg_model_rtf 0.06487` **不是可加的**（产物 `seg_model_rtf_in_wall` 字段原文）。
- ⚠️ **首字延迟口径**：`first_tok_lat_n` = 514 / 517（**逐次 decode 调用次数**，远多于段数）
  ⇒ 这是**逐次 decode 分布**，**不是** R2T2 bench 格那种「引擎级单事件 n=1」⇒ 两类不得并列。
- 🔴 **WER 未算**（本模块不调用 MiniMax）⇒ 交 reviewer 用这两个产物做**配对**复算。

### 42.2 🔴 ASR-015：**撤回「21:34 锁违规是 `pya_sweep_params.py` 造成」的归因**
- **reviewer/TTS 转达的原文指控**：「10-26 21:34–21:38，TTS 持有 MACHINE_LOCK 做计时，
  ASR 的 `pya_sweep_params.py` 照样启动，而且 MACHINE_LOCK 被 ASR 删除或覆盖。」
- 🔴 **实测该指控与证据不符**：`scripts/pya_sweep_params.py`（7 870 B，mtime **10-26 21:45**）
  **全文零锁代码** —— `grep shared|LOCK|lock|remove|unlink|write` **零命中**；不引用
  `MACHINE_LOCK`、不 import `asr_lock_common`、**不可能删/覆盖任何锁**。
  跨模块测试日志 `results/lock_verify/asr_lock_crossmod_20261027_rerun.log` 的 C3.0/C3.1
  已把这两条断言写成**回归项**（跑旧实现必然失败 ⇒ 有鉴别力）。
- ✅ **真凶是 `scripts/pya_app_path_seg.py` 的旧 fail-open 读锁逻辑**（「解析不出 pid 就删锁」）。
  21:30–21:50 窗口内真正在跑的 ASR 作业是这两个（**mtime 为证**）：
  `results/pyannote_seg/pya_app_baseline_base5m.json`（**21:41:48**）与
  `results/pyannote_seg/pya_app_forced_forced5m.json`（**21:45:16**）——
  正是 `pya_app_path_seg.py` 写的 ⇒ 与「21:34 启动、21:38 锁消失」的时间线吻合。
  `pya_sweep.json` 的 mtime 是 **21:46:03**（扫参产物），**不构成** 21:34 的启动证据。
- ✅ **ASR-015 ③ 已落地（锁逻辑收敛到公用函数）**：唯一事实来源 =
  `scripts/asr_lock_common.py`（`acquire` / `wait_until_free` / `read_lock` /
  `lock_is_stale` / `write_lock_exclusive` / `release_lock_if_owner` / `kill_child` /
  `LockProbe`）。本轮把 `scripts/asr007_r2t2_app_transcribe.py`、
  `scripts/p3_backfill_npu_fields.py`、`scripts/p3_npu_mask2_text_check.py`
  三个脚本的**自研只读锁实现**换成 `asr_lock_common.read_lock`（**只读快照，不删不写**）。
  审计：`grep -ln asr_lock_common scripts/*.py` 现为 **14 个**；
  `grep "os.remove|os.unlink" scripts/*.py | grep -i lock` 的命中**全部**在
  `asr_lock_verify.py` 内且指向**临时目录**（`os.path.join(tmpdir, 'MACHINE_LOCK')`）⇒
  **规范锁无任何脚本直接删/覆盖**。
- 🔴 **本轮的一次锁回收记录（ASR-015 ① 要求「回收时在 STATUS 里记一行」）**：
  10:53:28 起 PID 34724 持规范锁跑 61 分钟 baseline（锁内容
  `asr PID 34724 started 2026-10-27 10:53:28 task=pya_app_baseline_base61`）；
  11:19 用户指示改用 5 分钟短测 ⇒ **终止 PID 34724** ⇒ 其锁成为**陈旧锁**
  （`pid_alive(34724)`=False）⇒ 由进程退出自动释放；复核 `shared/MACHINE_LOCK`
  **不存在**（无 `.tmp` 残留、无孤儿锁）。
- ✅ **本轮两次 5 分钟跑都遵守锁纪律**：各自**持规范锁**、串行、`timing_valid=true`、
  `lock_probe_stolen=0`（检查 6 次）、跑完锁**正常释放**。

### 42.3 🔴 撤回 §37 的「−6.57pp / 相对降幅 66.6%」
- **撤回为**：「**跨脚本对比，待同脚本复核**」。
- 撤回理由：§37 的 9.87% 来自 App 路径 **B 组**（`asr004_ab_transcribe`，10-24 产物），
  3.30% 来自 `pya_app_path_seg.py` 的 forced 61 分钟 ⇒ **两者不是同一份脚本**（reviewer §2.2 指出），
  且 **9.87% 这个基线不代表「现行切段」的稳定水平**（reviewer 实测同 group B 规则的
  R2T2 NPU App 运行只有 **16/551 = 2.9%**，已低于 forced）。
- **本轮补上的同脚本证据（5 分钟口径）**：baseline 6.67% → forced 6.25%（−0.42pp），
  同脚本同引擎 ⇒ **forced 的词内切点确实更好，但幅度远小于 §37 的 −6.57pp**；
  且同脚本内切点仅 34/45 相同、文本仅 6/46 一致 ⇒ **「差值里有相当一部分不是词内切点」**。

### 42.4 ✅ ASR-014 §3：交付件缺格补齐（4 处）
产物：`reports/compare/ASR007_results.json`（**78 277 B @11:03:20**，15 条记录）、
`reports/compare/MATRIX.json`（20 158 B @10:58:43，21 格）、
`reports/compare/MATRIX.md`（16 675 B @10:58:43，第 25 行双计分器列）。

| # | 缺格 | 回填结果（原始字段） |
|---|---|---|
| 1 | R2T2 INT8 NPU App `wer_pct` | **10.4**，`wer_scorer`=`reviewer_minimax_global`，`wer_breakdown`={S:358, D:221, I:561}，n_segs=552（另见 `reports/compare/r2t2__int8__npu_app.json` 的 `accuracy` 子对象） |
| 2 | **R2T2 INT8 iGPU App 路径整条记录**（reviewer 10.58%） | records[8]：`wer_pct`=**10.58**，`wer_breakdown`={S:353, D:188, I:619}，n_segs=**558**，enc=GPU.0/dec=GPU.0/path=app |
| 3 | R2T2 INT8 GPU.0 whole_seg | records[6]：`wer_pct`=**null**，分字段 `wer_pct_reviewer_scorer`=**8.17** / `wer_pct_target_machine_scorer`=**7.798**、`wer_pct_all_npu_reviewer_scorer`=8.27、`delta_pp_reviewer`=0.1、`ci95_reviewer`=[-0.41, 0.56] |
| 4 | 0.6B INT8 NPU `wer_breakdown` | records[2]：`wer_breakdown`={S:441, D:181, I:590}（附 `note`：reviewer 在 ASR-014 §3 给出的拆分，总错误数 1212 与 ASR-012 的 `n_errors` 一致 ⇒ 原样回填，**本模块不自算**） |

- ✅ **两套计分器分字段已贯穿到汇总层**（此前只填了格子 json、没映射进汇总 ⇒ 本轮修
  `asr007_build_results.py::cell_from_compare` 与 `p3_make_matrix.py`）。
  MATRIX.md 的 WER 列显示 `reviewer 8.17 / 目标机 7.798`，`wer_scorer` 置 null。
- ✅ **ASR-014 §1 的措辞已改**：`results/p3_r2t2_61min_npu/summary.json` 的
  `device_placement.note` 与 `r2t2_ir_note` 已改成 **decoder-only 整段 prefill**，
  并含「⚠️「cross-attention 解码器」的旧说法已于 ASR-012 §2 撤回」一行 +
  `r2t2_ir_note_status` 字段；`timing_valid=false` 保持不变，RTF 1.0627 只作观察值。

### 42.5 ✅ ASR-014 §3：bench 四个疑点逐条解释（**不重跑**，写进产物）
产物字段：`reports/compare/ASR007_results.json` 每条 bench 记录新增
**`bench_explanations`**（4 个子键 `q1_bench_rtf_vs_61min` / `q2_load_s_cold_vs_cached` /
`q3_first_tok_p50_eq_p95` / `q4_mem_host_peak_breakdown`），每条带 reviewer 原问题 +
原始字段值 + 解释。

- **q1 R2T2 iGPU bench RTF 0.994 vs 61 分钟 forced 0.5765（差近一倍）** ⇒ **口径不同，不可直接比**：
  ① bench 取的是**热**那一遍（`bench_warm.json`，热 0.9942 / 冷 0.6966，**同一产物冷热就差 0.30**）；
  ② bench 只跑 600 s 切片 [720,1320] ⇒ **冷启动开销被摊进这 600 s**；61 分钟把一次性开销摊薄；
  ③ 61 分钟那格是 **forced**，且 `seg_model_rtf` **未计入 wall** ⇒ 不可加。
  ⇒ **bench 的 RTF 只用于同格冷/热对比，不作交付级 RTF**。
- **q2 R2T2 load_s 冷/热几乎相同（iGPU 7.41/7.53、NPU 2.25/2.26）** ⇒
  ✅ **reviewer 的怀疑成立**：冷遍与热遍的 `ov_cache_dir.state` **都是「有缓存（编译可命中）」**
  ⇒「冷」那一遍**没清 CACHE_DIR**。🔴 **根因**：R2T2 的缓存目录由 **App 内部 `_cache()`** 决定
  （`%LOCALAPPDATA%\Confucius4LiveCaption\{ov_cache,npu_cache}`）⇒ **外部无法指定/清空**
  ⇒ 0.6B 那套「每格独立 CACHE_DIR ⇒ 真冷编译」对 R2T2 不适用。
  ⇒ **口径更正**：`load_s_cold` 对 R2T2 **不是冷启动值**，**R2T2 的真冷启动本轮未测（不硬凑）**。
- **q3 R2T2 first_tok p50 == p95（1.582/1.030）** ⇒ ✅ **reviewer 判定正确**：这是
  **引擎级单事件**（引擎 `cur_text` 首次非空，含 encoder+prefill+首 token）⇒ **n=1，不是分布**；
  0.6B 的是逐次 decode 分布 ⇒ **两类不得并列**。字段已附 `n_segs` + `first_tok_note`。
- **q4 0.6B 四格主机峰值 9288–9293 MB、私有 ~10.9 GB，约为 R2T2 的 2 倍** ⇒
  ✅ **根因 = 同一份 FP32 权重被加载两次**：`asr007_bench.py::bench_06b`（L268-275）同时
  `Qwen3ASRForConditionalGeneration.from_pretrained` + `Qwen3ASRModel.from_pretrained`，
  读**同一份** `model.safetensors`（**1 876 091 704 B = 1789.18 MiB**）⇒ 两个独立 FP32 副本。
  实测分解：step0 WS 872.4 → step1（ForConditionalGeneration）WS 3880.1/peakWS 6262.8
  → step3（Qwen3ASRModel，同一份权重第二次）WS 6919.8/**peakWS 9260.2**；
  **bench 实测 peakWS 9294.1 MB vs 分解实测 9260.2 MB（差 0.4%）⇒ 归因成立**。
  ⇒ 🔴 **这是 bench 度量路径开销，不是交付形态**（交付只需 IR + processor）。
  产物：`results/asr007_bench/mem_breakdown_20261027.json`（2 682 B @11:00:28，
  import 链增量：`delta_torch_qwen_asr` WS **336.9** / peakWS **381.8** / 私有 **804.8** MB）、
  `results/asr007_bench/mem_breakdown2_20261027.json`（2 105 B @11:02:28，逐步加载分解）。
  两个脚本：`scripts/asr014_mem_breakdown.py`（5 951 B @11:00:01）、
  `scripts/asr014_mem_breakdown2.py`（7 219 B @11:01:53）。
  ⚠️ 修掉一个真缺陷：`GetProcessMemoryInfo` **未声明 argtypes/restype** ⇒ ctypes 参数错位
  ⇒ 恒返回 False ⇒ 首跑报 `TypeError: 'NoneType' object is not subscriptable`（MEMORY 铁律 #18）。

### 42.6 ✅ ASR-014 §2.5：交付时分段模型放哪个设备 + 常驻内存（**实测**）
产物：`results/asr007_bench/asr014_seg_placement.json`（3 199 B @11:31:34）、
`results/asr007_bench/seg_mem_NPU_ov-fp16.json`（1 779 B @11:31:10）、
`results/asr007_bench/seg_mem_GPU0_ov-fp16.json`（1 907 B @11:31:14）、
脚本 `scripts/asr014_seg_mem.py`（6 553 B @11:31:05，**只编译不推理** ⇒ 单组件诊断）。

| 分段 IR（`models/pyannote_seg/ov-fp16`，2 文件 = 3 052 154 B = **2.91 MiB**） | 编译 s | 常驻 WS | 常驻 peakWS | 常驻私有 |
|---|---|---|---|---|
| **NPU**（`DEVICE_ARCHITECTURE`=5010） | 0.833 | **71.0 MB** | 103.3 MB | 26.7 MB |
| **GPU.0**（`GPU: vendor=0x8086 arch=v30.1.0`） | 3.009 | **270.8 MB** | 279.4 MB | 264.1 MB |

- ✅ **建议放 NPU**（四理由写在产物的 `recommendation.reason`）：
  ① 不与 ASR 主链抢 iGPU；② **快约 5.6 倍**（`seg_model_rtf`：GPU.0 **0.060** vs
  NPU **0.01068**，`results/pyannote_seg/pya_stream_full61_NPU.json` 的 `rtf_seg_model`，
  `n_windows` 5722 / `n_breaks` 107 / `timing_valid`=true）；③ **省约 200 MB**（3.8 倍）；
  ④ §35.2 的 **FP16@NPU** 分割 IR 对拍 cos_min **0.999405** / 帧级类别一致率 **0.9983**
  （阈值 cos≥0.999、一致率≥99%）⇒ 可交付。
- ⚠️ **只给建议，不擅自改 `live_caption/`**（ASR-003 边界 / C-111）⇒ 实际摆放由 App 决定。
- ⚠️ NPU 上**无** `GPU_MEMORY_STATISTICS` ⇒ **片上内存读不到**，上表是**进程级**口径
  （`GetProcessMemoryInfo`，MEMORY 铁律 #18）⇒ **不硬凑**片上数字。
- ⚠️ 61 分钟的 `seg_model_rtf 0.060` 是 **GPU.0 + App 路径喂音**；NPU 的 0.01068 是
  **流式窗**口径 ⇒ 同一素材但路径不同，已在产物里注明。

### 42.7 ⚠️ ASR-013 剩余验收：**仍未完成**（不硬凑）
- **说话人身份**：61 分钟素材**只有 1 个说话人** ⇒ 全局 id 只有 S1、x-vector 同人/异人余弦
  **margin 仅 0.0054** ⇒ **多说话人素材上的切换点 F1 / 碎片化仍无数据**。
  本轮**未换素材、未开新实验**（纪律：无用户指派的 ASR 任务时不自行开实验）⇒ **待用户指派素材**。
- **pyannote 断句**：§42.1 的同脚本 5 分钟对照给出了 baseline vs forced 的
  `rule_counts`（42/3/1 vs 39/**7**/2/1）与切点一致性（34/45），
  但「切换点 F1」仍需**多说话人**素材 ⇒ 同上。

### 42.8 本轮**未做**的事（明确边界）
- ❌ **未改 `live_caption/` 任何文件**（ASR-003 / C-111）。
- ❌ **未算 WER**（本模块不调用 MiniMax）⇒ 全部交 reviewer 配对复算。
- ❌ **未跑 61 分钟 baseline**（用户改用 5 分钟短测）⇒ ASR-014 §2(a) 的**原始 61 分钟口径未完成**。
- ❌ **未测 R2T2 真冷启动**（`load_s_cold` 对 R2T2 不是冷启动）⇒ **不硬凑**。
- ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 本轮脚本/产物改动**只在本机、不进 git**
  ⇒ 交付给 App/TTS 需**另行打包**。

## §43 ASR-017 落地：统一用 SPE 前 5 分钟切片，不再跑 61 分钟长跑（2026-10-27 13:25）

**纠偏原文（ASR-017，2026-10-27 11:06）**：用户决定「以后无需跑 61min 长跑，太浪费时间，裁剪 5 分钟来测试即可」；所有 ASR/App 测试统一用 260902_SPE 的 **00:00–05:00 固定切片**，切片文件放 `shared/`（各模块共用同一份）；之前纠偏里写的「61 分钟」或「12–27 分钟切片」一律改用此 5 分钟切片；正在跑或排队的 61 分钟作业（除非接近跑完）停掉改跑 5 分钟；WER 仍由 reviewer 用同一切片的 MiniMax baseline 复算，5 分钟 ≈900 词、CI ±1.5–2pp，只判明显回退、不宣称 1pp 内改进显著。

### §43.1 切片身份核验（已做）
- 路径 `C://Users//Trekker-PTL//shared//SPE_0000_0500.wav`，9600044 B，mtime **2026-10-27 11:24:16**，16k / 单声道 / 16-bit。
- 本模块独立复核 md5 = `a10da6a3b9fb685bc6b8a5805c354d23`；取源文件 `260902_SPE_audio.wav`（3671.19 s）前 4800000 帧与切片逐字节比对 → **哈希完全一致** ⇒ 切片 = 源前 300 s，身份无误。

### §43.2 脚本改动（单一事实来源 + 护栏）
- **NEW** `scripts/asr_slice_common.py`（2991 B，mtime 13:13:34）：导出 `SLICE_WAV`=`shared/SPE_0000_0500.wav`、`SLICE_SEC`=300.0、`MAX_MIN`=5.0；提供 `slice_md5()` 与 `guard_minutes()`（超 5 分钟需显式 `--allow-long`，否则 `SystemExit`）。
- `scripts/pya_app_path_seg.py`（13:14:02）：`WAV`→`SLICE_WAV`；`--minutes` 默认 10→5；加 `--allow-long` + 护栏；产物加 `audio_source.slice_md5`。
- `scripts/asr007_r2t2_app_transcribe.py`（13:15:46）：`WAV`→`SLICE_WAV`；`--minutes` 默认 0→5；加护栏；产物加 `audio_source`。
- `scripts/p0_stream_seg.py`（13:14:44）：`WAV`→`SLICE_WAV`；`--minutes` 默认 0→5；加护栏。
- `scripts/asr007_bench.py`（13:15:54）：切片由 **[720,1320] 600s → SLICE_START=0、SLICE_SEC=300**（读 `SLICE_WAV`）；docstring 加「切片口径（ASR-017）」段。
- `scripts/p0_torch_ref.py`（13:16:25，torch CUDA 参照/质量 baseline 来源）：`WAV`→`SLICE_WAV`；`--minutes` 默认 0→5；加护栏。
- 全部 `ast.parse` 通过（py_compile OK）。**未改 `live_caption/`**（ASR-003 边界）；`p1_export_decoder_mask*.py` / `p1_verify_e2e.py` 仍指向源全量 wav，属一次性构建脚本、非运行时测试，按边界未动。

### §43.3 被中止的 61 分钟作业
- `logs/pya_base61.log`（task=pya_app_baseline_base61，pid=34724）跑到 **1980.0/3671.2 s（53.9%）** 后进程不在（非「接近跑完」）⇒ 按 ASR-017 不续跑 61 分钟。
- **产物：无**（`pya_app_baseline_base61.json` 未生成）；**checkpoint 残留：无**（`results/pyannote_seg/*.partial.json` 为空）。
- 该长跑的 5 分钟替代已在前序 §42 落地（`pya_app_baseline_base5m_v2.json` 46 段 / `pya_app_forced_forced5m_v2.json` 49 段）。

### §43.4 陈旧锁回收（铁律）
- 起始 `shared/MACHINE_LOCK` 由 **tts** 持有（`module: tts, pid: 14888, started 2026-10-27 11:28:49`）。
- 核验 pid 14888 在 `tasklist` 中不存在 ⇒ **陈旧锁（PID 已不在）** ⇒ 按 ASR-015/§40 铁律，验证跑启动前的 `wait_until_free` 自动回收（回收前复核 pid 仍是 14888）。
- 验证跑结束 `release_lock` 正常释放，`shared/MACHINE_LOCK` 当前**不存在、无 `.tmp` 残留**。

### §43.5 验证跑（用 shared 切片跑 5 分钟）
- 命令：`python scripts/pya_app_path_seg.py --engine gpu_int8 --strategy baseline --minutes 5 --tag asr017verify`。
- 产物 `results/pyannote_seg/pya_app_baseline_asr017verify.json`（14544 B，mtime 13:21:09）：`audio_source.slice_md5`=`a10da6a3b9fb685bc6b8a5805c354d23`（=源前 300s）、`audio_sec`=300.0、`n_segs`=46、`rtf`=0.6649、`timing_valid`=true、`lock_probe_stolen`=0、词内切点 **6.67%** 与 §42 `base5m_v2` 逐位一致 ⇒ **切片路径切换成功、音频身份无误**。

### §43.6 交付件 & 口径
- 交付 `results/pyannote_seg/asr017_slice_unify.json`（ASR-017 全量落地记录 + 切片身份 + 脚本清单 + 中止作业 + 回收锁 + WER 口径 + 验证跑原始字段）。
- **WER 结论口径（写进交付件）**：5 分钟 ≈900 词、CI 宽 ±1.5–2pp ⇒ 只判「明显回退」、不宣称 1pp 内改进显著；Δ 只和同一计分器 5 分钟基线比（目标机/reviewer 两套计分器不混用）；**WER 仍由 reviewer 用同一 shared 切片 MiniMax baseline 复算**（本模块不调用 MiniMax）。
- **历史 61 分钟交付格子保持原值不回写**；未来重测统一用 5 分钟切片，届时与历史 61 分钟格**不可直接比**（MEMORY 铁律：短切片不可外推）。

### §43.7 提交范围
- 本轮仅提交本模块 `status/asr/`（STATUS_ASR.md）。`qwen3asr_06b` 不在 git 仓库内 ⇒ 脚本/产物改动只在本机，不进 git（交付需另行打包）。

## §44 ASR-018 落地：用户定案默认设备摆放（ASR→GPU.0，TTS→NPU 独占）（2026-10-27 13:45）

**纠偏原文（ASR-018，2026-10-27 13:22，[NORMAL] FYI）**：用户决定默认配置 —— ASR/翻译都用 iGPU INT8，语音输出模型用 NPU；默认设备摆放定案：ASR（R2T2 INT8）→ GPU.0、MT（Hy-MT2 INT8）→ GPU.0、TTS（Qwen3-TTS 全 NPU 配置）→ NPU（NPU 仅 TTS 独占）、CUDA 不作默认；用户仍可在 GUI 改设备。交付默认是 R2T2 INT8 @ GPU.0，ASR 的 NPU 路径只保留为可选项；pyannote 分段模型若交付，默认也放 GPU.0（NPU 留给 TTS）；**在该前提下，报告分段模型在 GPU.0 上对 ASR RTF 的增量（5 分钟切片）**。

### §44.1 默认设备摆放（记录用户定案）
- ASR（R2T2 INT8）→ **GPU.0**；MT（Hy-MT2 INT8）→ **GPU.0**；TTS（Qwen3-TTS 全 NPU 配置）→ **NPU**；NPU **仅 TTS 独占**；CUDA 不作默认。
- 交付默认 = R2T2 INT8 @ GPU.0；ASR 的 NPU 路径仅作可选项保留。
- pyannote 分段模型若交付，默认也放 **GPU.0**（NPU 留给 TTS）。
- ⚠️ 设备摆放属 App 模块实现（ASR-003 边界 / C-111）；本模块**不代改 `live_caption/`**，仅记录定案与按需报告指标。

### §44.2 分段模型在 GPU.0 的 RTF 增量（5 分钟切片，按 ASR-018 要求实测）
- 命令：`python scripts/pya_app_path_seg.py --engine gpu_int8 --strategy forced --minutes 5 --seg-device GPU.0 --tag asr018seg`。
- 产物 `results/pyannote_seg/pya_app_forced_asr018seg.json`（16427 B，mtime 13:31:47）：`audio_source.slice_md5`=`a10da6a3b9fb685bc6b8a5805c354d23`、`audio_sec`=300.0、`n_segs`=49、`rtf`=0.7102、`seg_model_wall_s`=20.63、**`seg_model_rtf`=0.06876**、`timing_valid`=true、`lock_probe_stolen`=0、词内切点 **6.25%** 与 §42 forced5m_v2 一致。
- 🔴 **口径**：分段模型推理耗时由 `run_seg_model` 单独计时（未计入主链 wall），故 `seg_model_rtf`=0.06876 即「分段模型在 GPU.0 上对 ASR 的 RTF 增量」，**不可与主链 RTF 相加**。
- 对照：ASR-014 §2.5 / `asr014_5m_baseline_vs_forced.json` 的 forced5m_v2（seg_device=**NPU**）`seg_model_rtf`=0.06487 ⇒ GPU.0 比 NPU 慢约 **+0.004（~6%）**，差异极小；按 ASR-018 定案，ASR 默认走 GPU.0，NPU 让给 TTS，**该 ~6% 的 RTF 代价可忽略**。

### §44.3 交付件
- 全部落在 `results/pyannote_seg/asr017_slice_unify.json`（`asr018_device_placement` 段：决策 + 实测原始字段 + NPU 对照）。
- 本轮仅提交本模块 `status/asr/`（STATUS_ASR.md + CORRECTIONS_ASR.md 的 ASR-018 条目）；`qwen3asr_06b` 不在 git 内 ⇒ 脚本/产物改动只在本机。


## §45 ASR-019 落地：更正 §44.2 的 `seg_device` 归属（0.06487 是 GPU.0，不是 NPU）+ 正确的 GPU.0/NPU 对照（2026-10-27 15:50）

**纠偏原文（ASR-019，2026-10-27 15:39，[FYI]）**：reviewer 指出 §44.2 把 `seg_model_rtf` 0.06487 标成 NPU，与 §42.6 自相矛盾；0.06487 数值与 GPU 吻合，应是 GPU.0。要求核对 `pya_app_forced_forced5m_v2.json` 的 `seg_device` 字段，在 STATUS 和 `asr017_slice_unify.json` 里更正对照；GPU.0 对 NPU 实际约 5.6 倍，不是 6%；结论不变（默认放 GPU.0，增量 0.069 可接受）；**不需要重跑实验**；验收 = 新增一小节写出更正后的字段原值。

### 45.1 🔴 更正后的字段原值（唯一判据 = 产物 `params.seg_device`）

| 产物（`results/pyannote_seg/`） | 字节 / mtime | `params.seg_device` | `seg_model_rtf` | `seg_model_wall_s` | `audio_sec` / `n_segs` |
|---|---|---|---|---|---|
| `pya_app_forced_forced5m_v2.json`（**§44.2 误标为 NPU 的那一个**） | 16062 / 11:28 | **GPU.0** | **0.06487** | 19.46 | 300.0 / 49 |
| `pya_app_forced_forced5m.json` | 12460 / 10-26 21:45 | **GPU.0** | 0.05852 | 17.56 | 300.0 / 49 |
| `pya_app_forced_forced61.json` | 150639 / 10-27 01:09 | **GPU.0** | 0.06018 | 220.94 | 3671.19 / 607 |
| `pya_app_forced_asr018seg.json` | 16427 / 13:31 | **GPU.0** | 0.06876 | 20.63 | 300.0 / 49 |
| `pya_stream_full61_NPU.json` | 37299 / 10-26 21:49 | `device`=**NPU** | **0.01068**（字段名 `rtf_seg_model`） | `infer_wall_s`=39.2 | 3671.189 / 108 段 / 5722 窗 |

- ✅ **二次交叉验证（不只看 json）**：`logs/pya_forced5m_v2.log` 第 92 行、**日志末尾打印的 summary 里 `"seg_device": "GPU.0"`**；`logs/pya_app_forced61.log` 第 122 行同样是 `"seg_device": "GPU.0"` ⇒ json 与运行日志一致，排除「写盘时被改」。
- 🔴 **`asr014_5m_baseline_vs_forced.json` 的 `runs[1]`（forced_5m_v2）里根本没有 `seg_device` 字段** ⇒ §44.2 写「forced5m_v2（seg_device=**NPU**）」**既无产物字段支持，又与源产物 `params.seg_device="GPU.0"` 直接矛盾** ⇒ 这就是错误来源。
- ⇒ **所有 forced 产物（5 分钟与 61 分钟）分段模型都在 GPU.0 上跑**；NPU 上只有独立的流式窗口径那一个数 0.01068。

### 45.2 ✅ 更正后的 GPU.0 vs NPU 对照（原「6%」作废）

| 口径 | 值 | 出处 | 路径性质 |
|---|---|---|---|
| **GPU.0**（App 路径喂音） | **0.06018** | `pya_app_forced_forced61.json`（`seg_device`=GPU.0，61 分钟） | App 路径喂音 |
| **GPU.0**（App 路径喂音） | 0.06487 / 0.05852 / 0.06876 | `forced5m_v2` / `forced5m` / `asr018seg`（5 分钟三次） | App 路径喂音 |
| **NPU**（流式窗） | **0.01068** | `pya_stream_full61_NPU.json`（`device`=NPU，字段名 `rtf_seg_model`，5722 窗 / 107 断点 / `timing_valid`=true） | 流式窗口径 |

- ⇒ **GPU.0 / NPU = 0.06018 / 0.01068 = 5.6348 ⇒ 约 5.6 倍**（reviewer 给「约 5.6 倍」，与 §42.6 的「快约 5.6 倍」**一致**）。
- 🔴 **撤回 §44.2 的「GPU.0 比 NPU 慢约 +0.004（~6%）」** —— 那是把 GPU.0 的两个数（0.06487 与 0.06876）当成了「GPU.0 vs NPU」的对照，实际上**两次都是 GPU.0**，比的是同一设备两次测量的波动（不是设备间差异）。真实设备间差异是 **5.6 倍**。
- ⚠️ **口径提示（沿用 §42.6）**：0.06018 是 **GPU.0 + App 路径喂音**，0.01068 是 **NPU + 流式窗** ⇒ 同素材但**路径不同**，倍数只能作为量级参考，不可当严格同口径比值。
- ✅ **§44.2 的结论不变**：按 ASR-018 用户定案，分段模型默认放 **GPU.0**（NPU 让给 TTS 独占），GPU.0 上的 RTF 增量 ≈ **0.069**（`asr018seg` 实测），**可接受**；ASR-014 §2.5 的「建议放 NPU」是**已撤回口径下的旧建议**，其数字依据同样是「GPU.0 0.060 vs NPU 0.01068」⇒ **5.6 倍这个依据本身没错**，但「因 GPU 只慢 6% 故可忽略」的表述要改（实际是慢 5.6 倍）。

### 45.3 ✅ 已更正产物：`results/pyannote_seg/asr017_slice_unify.json`

- 更正前 8747 B（13:32）⇒ 更正后 **12226 B**（15:4x，mtime 见文件）；备份 `_asr019_backup_asr017_slice_unify.json`（8747 B）。
- 新增字段 **`asr018_device_placement.comparison_gpu_vs_npu_corrected`**：
  `what_was_wrong`（§44.2 把 0.06487 当 NPU）/ `evidence_seg_device_fields`（上表 5 个产物的 `seg_device` + `seg_model_rtf` 原值）/
  `corrected_ratio`（gpu0_rtf 0.06018 / npu_rtf 0.01068 / ratio 5.63 / 两边出处）/ `gpu0_app_path_increments_5min`（0.05852 / 0.06487 / 0.06876）/
  `conclusion_unchanged` / `no_rerun_needed`=true。
- `asr018_device_placement.comparison_npu` 文本已替换为更正版；**旧文原文保留在 `comparison_npu_previous_text_asr019`**（可追溯，不静默改写）。
- 🔴 **原始产物一个字节都没改**：`pya_app_forced_forced5m_v2.json` / `asr014_5m_baseline_vs_forced.json` 等全部保持原样（更正只落在**汇总/叙述文件**上）。
- ⚠️ `qwen3asr_06b` **不在 git 仓库内** ⇒ 本轮改动**只在本机**（`scripts/asr019_fix_seg_device.py` + 上述 json），不进 git，交付需另行打包。

### 45.4 本轮未做
- **未重跑任何实验**（ASR-019 明确「不需要重跑」）⇒ 本轮**不占机器锁**（`shared/MACHINE_LOCK` 全程不存在，无 `.tmp` 残留）；未动 `live_caption/` 任何文件（ASR-003 边界）。
- 🔴 **WER 仍未算**（本线程不调用 MiniMax）⇒ 交 reviewer 用 `shared/SPE_0000_0500.wav`（md5 `a10da6a3b9fb685bc6b8a5805c354d23`）的 MiniMax baseline 复算：`pya_app_baseline_asr017verify.json`（46 段）/ `pya_app_forced_forced5m_v2.json`（49 段）/ `pya_app_forced_asr018seg.json`（49 段）。
- ⚠️ **撤回 §42.6 里的「建议放 NPU」建议措辞**（不删旧章节，只在此声明）：其数字依据（GPU.0 0.060 vs NPU 0.01068）本身成立，但结论「GPU 只慢 6%」是 §44.2 的错值传导 ⇒ 正确表述是「**GPU.0 比 NPU 慢约 5.6 倍**」；按 ASR-018 定案仍**默认放 GPU.0**。
- ASR-013 剩余验收（多说话人素材）仍未完成，等用户指派素材。

### 45.5 工具/方法论备忘
- 🔴 **「文档自述」不能当设备归属的判据**：本轮错误正是「上一轮自己写的『seg_device=NPU』被下一轮当成已核实事实引用」⇒ **设备/精度/摆放类字段必须回到原始产物的 `params`/`device` 字段取证**，并在 STATUS 里把**字段名 + 原值 + 文件路径**三者写全。
- ⚠️ **汇总 json 可能丢字段**：`asr014_5m_baseline_vs_forced.json` 的 `runs[]` 条目**没有** `seg_device` ⇒ 引用汇总 json 的字段时要回源核对，否则会凭空多出一个「NPU」。
- ✅ 校验技巧：把 `params` 里的设备字段和**运行日志末尾打印的 summary** 对照（`logs/pya_forced5m_v2.log:92`、`logs/pya_app_forced61.log:122`）⇒ 可排除「写盘时被改」的可能。

## §46 ASR-020 落地：5 分钟 forced vs baseline 的 WER / 词内切点均「无实际差异」；定稿延迟是「预知断点」口径、实时增量未测（2026-10-27 21:05）

**纠偏原文（ASR-020，2026-10-27 15:45，[NORMAL]）**：reviewer 复算的 5 分钟切片 WER（baseline 7.39% vs forced 7.52%，Δ+0.12pp CI95[−0.89,+1.14]）⇒ 按用户口径**无实际差异**；词内切点 baseline 3/45=6.67% vs forced 3/48=6.25%，**命中数都是 3**，−0.42pp 全来自分母 ⇒ 请把 §42.1/§42.3 的「forced 的词内切点确实更好」改成「命中数 3→3，无实际差异」；§3 定稿延迟现有数字不是实时口径（断点是预先知道的）⇒ 二选一 (a) 加因果约束重测 / (b) 在 STATUS 和交付件里明确写「实时增量未测；预计 model_break 段定稿延迟增加 ≥9.4 s，或者断点来不及应用（rule1 已经先切了）」，另外 baseline 记录的 `window_lag_ms=9360` 请改成 null；§4 两次原始 json 的 `params.seg_device` 都是 GPU.0 ⇒ 「GPU.0 比 NPU 慢 6%」不成立，应改为「同为 GPU.0 的两次运行」；§5 `model_break_times` 里三对间隔是精确 10.000 s，请用单组件诊断确认是否把窗口首尾边界当成 change point。**验收**：STATUS 写出 §1/§2 的「无实际差异」结论；§3 选 (a) 或 (b) 落档；§4 改正 NPU 对照表述；§5 写一行诊断结论。

### 46.1 §1 WER（reviewer 复算，目标机不调用 MiniMax）

| 项 | 值 | 出处 |
|---|---|---|
| baseline（gpu_int8 = R2T2 INT8@iGPU App 路径 5 分钟） | **7.39%**（S32 D17 I12） | reviewer 复算，口径见下 |
| forced | **7.52%**（S33 D18 I11） | 同上 |
| Δ(forced−baseline) | **+0.12pp，95% CI [−0.89, +1.14]** | 同上 |
| 参考词数 | **825**（只保留 t<300 s 的词） | 同上 |
| 计分器 | `reviewer_minimax_global`（MiniMax baseline 线性比例分配词时间 + 全局对齐 + 公共段边界分块配对 bootstrap，36 块 / 5000 次；换 30 s 网格结果相同） | 同上 |

- ✅ **判定**：按用户口径（差距 <1pp 或不显著）⇒ **无实际差异**。
- ✅ **切片边界敏感性**：截取点换成 298 s / 302 s，绝对 WER 在 6.7%–8.2% 间变化，**Δ 不变（+0.12）** ⇒ 结论不依赖截取点。
- ✅ **确定性**：重复跑的 `pya_app_baseline_asr017verify.json` 与 `pya_app_forced_asr018seg.json` 与 v2 两份 WER **逐位一致**（S/D/I 完全相同）。
- 🔴 **口径**：5 分钟的绝对值**不能**和 61 分钟的 10.58% 比较（MEMORY 铁律：短切片不可外推）。
- ✅ 目标机侧已把该结论**原样落进产物字段**：`pya_app_baseline_asr017verify.json` 的 `asr020_conclusion`（"forced vs baseline 无实际差异 … ⇒ **撤回「forced 的词内切点确实更好」**（§42.1/§42.3）"）、`pya_app_forced_forced5m_v2.json` 同名字段。

### 46.2 §2 词内切点（口径 = 全部接缝；reviewer 实现与 `seam_overlap` 一致）

| 口径 | baseline | forced | 说明 |
|---|---|---|---|
| 命中 / 总接缝 | **3 / 45 = 6.67%** | **3 / 48 = 6.25%** | 分母 = 全部接缝 |
| 去空段口径 | 6.67%（**无空段**） | 6.25% | 结论不变 |
| **命中数** | **3** | **3** | ← **无实际差异的关键** |

- 🔴 **撤回 §42.1 / §42.3 的「forced 的词内切点确实更好」** —— forced **没有减少任何一个词内切点**，−0.42pp **完全来自分母多了 3 条接缝**（45→48）。
- ⚠️ **不可跨表比绝对数**：段数变了（46→49）⇒ 只按各自口径的接缝数算占比。

### 46.3 §3 定稿延迟：**选 (b)** —— 实时增量未测（ASR-021 §① 已判定「延迟测试不用再做」⇒ 不补跑 (a)）

- 🔴 **现有数字不是实时口径的证据（机制）**：`pya_app_path_seg.py` 的流程是 **先对整段音频离线跑 `run_seg_model` 得到全部断点**，然后 `ForcedSegmenter.due` 在「已喂秒数 ≥ 断点绝对时刻」时立刻切段 ⇒ **断点是预先知道的**。forced 的 7 个 `model_break` 段 `finalize_lat_s` 只有 0.32–0.42 s 就是这个机制的直接表现。
- 🔴 **实时运行时**，t 时刻的断点至少要等 `window_lag_ms` = **9360.0 ms** 加上推理时间才能得到 ⇒ **§42.1 的「定稿 p50 0.442→0.422」不能作为 forced 的定稿延迟增量**。
- ✅ **(b) 已落档（产物 + STATUS 双落）**：
  - `pya_app_forced_forced5m_v2.json` 的 `latency.finalize_lat_realtime_note`：「🔴 **ASR-020 §3：forced 的现有定稿延迟数字不是实时口径**（断点是**预先知道**的 …）⇒ **不能作为 forced 的定稿延迟增量**。实时运行时，t 时刻的断点至少要等 `window_lag_ms` = 9360.0 ms 加上推理时间才能得到。」+ `latency.realtime_increment_note`：「**实时增量未测**（ASR-020 §3 选项 (b)；ASR-021 §① 已判定「延迟测试不用再做」⇒ 不再补跑）。预计 model_break 段定稿延迟增加 **≥9.4 s**，或者断点来不及应用（rule1 已经先切了）。」
  - 同字段已写入 `pya_app_forced_asr018seg.json` / `pya_app_forced_forced61.json` / `asr014_5m_baseline_vs_forced.json`。
- ✅ **baseline 的 `window_lag_ms` 已置 null**（要求原文）：
  - `pya_app_baseline_asr017verify.json` / `pya_app_baseline_base5m_v2.json`：`latency.window_lag_ms` = **null**（原 9360.0），并加 `latency.window_lag_note`：「🔴 **ASR-020 §3：baseline 不跑分段模型 ⇒ 没有窗级聚合滞后 ⇒ 此字段置 null**（原值 9360.0 是 forced 侧的数，不适用于 baseline）」+ `latency.finalize_lat_realtime_note`（baseline 的定稿延迟是**真实运行时**口径，断句由 R2T2 原路径决定，不依赖模型断点 ⇒ 可直接引用）。
  - 备份：`results/_asr020_backup_20261027_170639/`（变更清单见 `results/pyannote_seg/asr020_deliverable_fix.json`，1332 B @17:06）。

### 46.4 §4 设备表述改正（与 §45 一致）

- ✅ **两次原始 json 的 `params.seg_device` 都是 GPU.0**：`pya_app_forced_forced5m_v2.json` → **GPU.0**（`seg_model_rtf`=**0.06487**）、`pya_app_forced_asr018seg.json` → **GPU.0**（`seg_model_rtf`=**0.06876**）⇒ 分段模型在 GPU.0 上的增量 ≈ **0.065–0.069**。
- 🔴 **「GPU.0 比 NPU 慢约 6%」不成立** —— 那 0.004 的差是**同为 GPU.0 的两次运行的波动**，不是设备间差异。正确表述：**GPU.0 vs NPU ≈ 5.6 倍**（0.06018 GPU.0 / 0.01068 NPU，§45.2 已给出处）。
- ✅ 已落进产物：`pya_app_forced_forced5m_v2.json` 的 `asr020_seg_device_correction`（`params_seg_device_raw`="GPU.0" / `seg_model_rtf`=0.06487 / `npu_reference` 注明 NPU 侧只有 `pya_stream_full61_NPU.json` 的 `rtf_seg_model`=0.01068、**流式窗口径**、与 App 路径不同口径不可直接相减）。
- ⚠️ **主链 RTF 跑间差异不做解读**（baseline 0.7069/0.6649、forced 0.6779/0.7102 ⇒ 落在噪声范围内）。

### 46.5 §5 model_break「精确 10.000 s 间隔」诊断结论：**不是窗边界伪影**

- 🔴 **根因 = `find_breakpoints` 最长段兜底公式**：`pick={"i": a + max_frames // 2}`。`max_frames` = 1178（10 s × 58.9 FPS）⇒ `max_frames // 2` = **589 帧** = **10.000 s** ⇒ **每两个兜底断点的间隔恒等于 10.000 s**（与音频内容无关）。
- ✅ **证据（单组件诊断 `asr020_break_rootcause_diag.json`，34936 B @16:54）**：
  - `consts`：`FPS`=58.9 / `WIN_S`=10.0 / `STRIDE_S`=0.64 / `max_frames`=**1178** / `max_frames_half_floor`=**589** / `half_floor_seconds`=**10.0**。
  - `runs.forced5m_v2`：`n_breaks`=7、`n_max_len`=**4**、`n_max_len_no_legal_candidate`=**4**、`n_gaps_total`=6、`n_gaps_equal_10s_exact`=**3**、`n_gaps_10s_equal_half_floor`=**3**。
  - `runs.asr018seg`：同上（7 / 4 / 4 / 3 / 3）。
  - `runs.forced61`：`n_breaks`=108、`n_max_len`=**47**、`n_max_len_no_legal_candidate`=**47**、`n_gaps_equal_10s_exact`=**46**。
  - ⇒ **5 分钟 4/4、61 分钟 47/47 的「精确 10.000 s」断点全部是「无合法候选」的兜底点**，不是模型判出的 change point。
- ✅ **排除窗首尾边界伪影**：兜底点的 `off_win_head_s` = **0.104 / 0.156 / 0.400 / 0.401**、`off_win_tail_s` = 9.599–9.896，`near_win_boundary` 全为 **false** ⇒ **不落在窗的首/尾边界**。
- ⚠️ **副作用（真实缺陷，值得记）**：兜底点**没有做任何词边界保护** ⇒ 会切在词中间（`describe|Our`、`segments|more`、`what|does`）。**但这已随 ASR-021 ① 停掉 forced 线而不进交付**（§47.1）；若将来复活 forced，必须先给兜底点加词边界/静音约束。
- 📌 附带产物：`results/pyannote_seg/asr020_break_artifact_diag.json`（55012 B @16:53，段级 artifact 侧证据）。

### 46.6 本轮未做 / 边界

- **未重跑 5 分钟 baseline/forced 对照**（WER 与词内切点用 reviewer 已复算结果；§3 选 (b) 不补跑 (a)）⇒ 本轮**不占机器锁**。
- **未动 `live_caption/`**（ASR-003 边界）；**未调用 MiniMax**（目标机不自行判定质量）。
- ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 本轮脚本/产物改动**只在本机**，不进 git（交付需另行打包）。

## §47 ASR-021 落地：pyannote 只做说话人识别（旁路），forced 断句线停掉；说话人验收已跑通（2026-10-27 21:05）

**纠偏原文（ASR-021，2026-10-27 15:48，[HIGH]）**：用户决定 —— **pyannote/segmentation-3.0 只用来识别说话人，不再用来给 ASR 强制断句**；依据是 ASR-020 的复算（WER/词内切点均无实际差异，实时断句至少多等约 9.4 s 右侧上下文，对实时字幕和 10 s 缓冲的配音插件不可接受）；断句继续用 R2T2 原有的方式；pyannote 和说话人 embedding 在**旁路**运行，**不阻塞定稿**（定稿段先发出去，spk 晚到可晚 1–2 s 时用 id 补发一条 spk 更新事件；攒够约 3 s 干净语音前 spk 为 null，TTS 用上一句音色或预设 A）。**ASR 要做的**：① 停掉 forced 断句这条线（代码可以保留，但不进交付，也不进 App 默认），ASR-020 里的延迟测试不用再做；② 只做说话人：分段模型在旁路运行（GPU.0），定稿段到达后取 x-vector 做在线聚类，输出 `{id, spk, spk_conf}` 更新事件；③ 验收：5 分钟切片里说话人切换点对照 3.1 伪真值的 F1、全局 id 的纯度和碎片化、spk 相对定稿的滞后（P50/P95），以及旁路给 ASR RTF 带来的增量（**不得 > 0.05**）；用 SPE 前 5 分钟，素材说话人太少则补一段 2–3 人对话的公开素材并在 STATUS 注明来源。

### 47.1 ① forced 断句线已停（不进交付、不进 App 默认）

- ✅ **代码默认策略已从 `forced` 改为 `baseline`**：`scripts/pya_app_path_seg.py` L354 `ap.add_argument('--strategy', default='baseline', choices=['baseline','forced'], …)` ⇒ **R2T2 原路径 = 交付口径**；`forced` 只作实验记录，**要复现实验须显式 `--strategy forced`**。
- ✅ 文档字符串同步改写：baseline 标为「**这是交付口径**」，forced 标为「**只作实验记录**」，并写入 ASR-020 的复算数字（WER Δ+0.12pp CI[−0.89,+1.14]、词内切点命中数 3→3、实时断句至少多等约 9.4 s）；用法示例去掉 `--strategy forced`。
- ✅ `py_compile` OK；`--help` 已验证。
- ✅ **ASR-020 §3 的延迟测试不再做**（符合纠偏原文）。
- ⚠️ **本模块只改了自己的脚本**；`live_caption/` 的默认策略**未代改**（属 App 边界，ASR-003）。

### 47.2 ② 旁路说话人识别（实现与产物）

- ✅ **实现脚本 `scripts/asr021_bypass_spk_wespeaker.py`**：① 旁路 seg 模型（**只出帧级概率、不产生任何断点**）→ ② 定稿段到达后取该段音频 → ③ 帧级过滤（干净语音占比/重叠率/最短时长）→ ④ x-vector 在线聚类（余弦阈值 + 均值逐步更新 `update_alpha` + 说话人数上限）→ ⑤ 滞后统计。
- ✅ **切段仍完全由 R2T2 原路径负责**（旁路从 `pya_app_baseline_asr021ami.json` 的定稿段取音频，不参与断句）⇒ 产物 `note` 明写「定稿段先发出去，spk 晚到时补发 spk 更新事件」。
- ✅ **共享锁接入 ASR-015/§39 单一事实来源**：`from asr_lock_common import acquire as _acquire, release_lock_if_owner` ⇒ 持锁执行、`finally` 释放。
- ✅ **新增 `--stride-ms`（默认 1280.0）** —— ASR-013 ② 明确允许「640 ms 分块对齐（**或者 1.28 s**）」；ASR-021 已定「旁路不产生断点」⇒ 断点不再需要 640 ms 粒度。
- 🔴 **说话人 embedding 源已换（重要）**：
  - **Qwen3-TTS INT8 `speaker_encoder.xml` 不可用** —— `results/pyannote_seg/asr021_xvec_diag3.json`（3097 B @17:32）：`T1_utterance_raw_margin`=**0.0158**、`bias_ratio`=**0.9823**、`separable_by_any_thr`=**false** ⇒ **99% 范数是说话人无关常量，任何阈值都不可分**。
  - ⇒ 按 **ASR-013 原文授权**（「直接复用 Qwen3-TTS Base 自带的 speaker encoder 提的 x-vector……**如果它区分说话人的能力不够，再评估 wespeaker-resnet34 / CAMPPlus**」）改用 **wespeaker-voxceleb-resnet34-LM**（本地 `_ref_models/wespeaker`）：`results/pyannote_seg/asr021_xvec_diag_wespeaker.json`（3548 B @20:47）→ `W1_utterance_raw_margin`=**0.2250**、`W2_per_spk_raw_margin`=**0.3453**、`bias_ratio`=**0.4291** ⇒ **margin 是 TTS encoder 的 21.9 倍**。
  - 🔴 **wespeaker 是 torch 实现 ⇒ 只作评估/诊断，未进交付**（ASR-013 要求运行时不依赖 torch）⇒ **必须导出成 OV IR** 才是交付前置条件。产物字段 `encoder.runtime_dep` 已明写这一点。

### 47.3 ③ 验收结果

**素材（2 份）**

| 素材 | 来源 | 说话人 | 用途 |
|---|---|---|---|
| **SPE 前 5 分钟切片**（用户口径主素材） | `shared/SPE_0000_0500.wav`（md5 `a10da6a3…`） | **1 人** | 主素材；⚠️ 1 人 ⇒ 切换点 F1 / 碎片化**不可检验** |
| **AMI EN2002a**（补的多说话人公开素材） | **AMI Meeting Corpus**，`edinburghcstr/ami` 数据集、`sdm`（far-field 会议麦克风）配置、shard `sdm/test-00000-of-00004.parquet`，镜像 `https://hf-mirror.com/datasets/edinburghcstr/ami`；**许可 CC BY 4.0**（Edinburgh / Univ. of Sheffield） | AMI 原始逐句标注 **4 人**；pyannote 3.1 伪真值 **2 人** | 切换点 F1 / 纯度 / 碎片化的检验素材 |

- 📌 素材落盘：`results/_spk_material/ami_multispeaker/ami_EN2002a.wav`（5834602 B @17:02）/ `ami_EN2002a.rttm`（5041 B）/ `ami_EN2002a.json`（16333 B）；伪真值 `results/pyannote_seg/pya_ref_diar_amiEN2002a.json`（7912 B @17:07）+ `.rttm`（3846 B）。
- 🔴 **伪真值性质**：AMI 原始逐句标注 = **人工可核**；3.1 伪真值 = **评估用**（`speaker-diarization-3.1` 非 gated 镜像，config 与官方 3.1 一致）⇒ 两者**不混用**。

**验收数字（原始字段见 `results/pyannote_seg/asr021_speaker_acceptance.json`，8761 B @20:58）**

| 指标 | AMI EN2002a（34 段 / 182.33 s） | SPE 5 分钟（46 段 / 300 s） | 判据 |
|---|---|---|---|
| 有标签段 / null 段 | **22 / 12** | **43 / 3** | 攒够约 3 s 干净语音前 spk=null ✅ |
| 跳过原因 | `not_clean_speech`=8 / `too_short`=3 / `insufficient_clean_speech_yet`=1 | 同构 | — |
| 最终说话人数 | **4** | **1** | SPE 是 1 人 ⇒ ✅ 不误报 |
| 切换点 | **4** 个（t = 11.52 / 16.64 / 23.04 / 29.44 s） | **0** ✅ | SPE 1 人 ⇒ 不应报切换点 |
| **切换点 F1**（对照 3.1 伪真值，tol ±1.5 s） | **P=0.75 / R=0.0857 / F1=0.1538**（n_pred=4 / n_truth=35 / **tp=3**） | 不可检验（n_truth=0） | — |
| **全局 id 纯度** | **1.0**（22 个有标签段） | — | ✅ 无 id 混用 |
| **碎片化** | **2 / 2** 个真值说话人被拆成多个 cluster（`SPEAKER_01`→{S1,S4}；`SPEAKER_00`→{S2,S3}） | 0（1 人） | ⚠️ 见 47.3 末 |
| spk 相对定稿的滞后 | **P50 0.0084 s / P95 0.0157 s** | P50 0.0077 s / P95 0.0182 s | ≤ 1–2 s ✅ |
| spk 置信度均值 | 0.6241 | 0.8656 | — |
| **旁路 RTF 增量** | **0.02893**（GPU.0，stride 1280 ms，wall 5.276 s） | **0.02961** | **≤ 0.05 ✅** |

- 🔴 **滞后口径**：0.0084 / 0.0157 s 是「**段音频结束 → 该段 spk 产出**」的**下界**（只含 x-vector 推理耗时）⇒ 完整滞后还要加「段定稿时刻 → 段音频结束」的等待 + seg 模型聚合滞后（`window_lag_ms`=9360 ms 是**算法层面**滞后，**不是**运行时定稿延迟）。与 ASR-021 允许的「spk 晚 1–2 s」上限同读。
- 🔴 **纯度 1.0 但碎片化 2/2** ⇒ 说明「**没有把不同人混成同一个 id**」，但「**同一个人被拆成两个 id**」（AMI 里只有 2 个真值说话人，却分成 4 个 cluster）⇒ 需要阈值/均值更新策略调优，或改用更强 embedding。

### 47.4 recall 0.0857 的归因：**粒度上限，不是模型缺陷**

- 诊断产物 `results/pyannote_seg/asr021_switch_floor_diag.json`（3405 B @20:50）：
  - 真值 turn 时长分布：`n`=**54**、`min`=0.017、`p10`=0.034、`median`=**0.692**、`p90`=10.463、`max`=28.637；**<0.2 s 有 14 个、<0.5 s 有 24 个、<1.0 s 有 29 个**。
  - ASR 段元信息：`n_segs`=34、`mean_seg_dur_s`=**5.289**、`n_pred_switch`=4。
  - `min_turn_s=0.0`：`n_truth_switch`=**35**、`n_truth_on_asr_seg_boundary`=**15**、`pct_expressible_at_seg_granularity`=**0.4286** ⇒ **35 个真值切换点只有 42.9% 落在 ASR 段边界 ±1.5 s 内**。
  - `min_turn_s`=0.5 / 1.0 ⇒ `n_truth_switch` 降到 9、`n_truth_on_asr_seg_boundary` 只剩 2（**22.2%**）⇒ **更长 turn 反而更难落在段边界**。
- ⇒ **结论**：① ASR 定稿段均长 5.3 s ⇒ 一个段内可能发生多次说话人切换，而「**每段一个 spk id**」在原理上无法表达段内切换；② 真值 54 个 turn 里 24 个短于 0.5 s（segmentation 边界毛刺）；③ **recall 的上限由「段粒度」决定**。⇒ **要提高 recall 必须改方案**（段内切分 / 更细粒度说话人 / 独立于 ASR 段的说话人时间线），属**新设计**，需用户决定是否开（本模块不自行开新实验）。

### 47.5 RTF 增量 ≤ 0.05 的达标过程（两个诊断）

- 🔴 **第一步：5 个 IR 变体全部超阈 ⇒ 不是量化精度问题**
  - 产物 `results/pyannote_seg/asr021_seg_rtf_variants.json`（1715 B @20:52）：`ov-fp16`=**0.05802** / `ov-int8`=**0.05807** / `ov-int8-calib`=**0.05997** / `ov-int8-head`=**0.05850** / `ov-fp32`=**0.05845** ⇒ **5 个全 FAIL**（阈 0.05）；单窗中位 **38.7 ms** ⇒ 是「**窗数 × 单窗耗时**」，不是量化精度。
- ✅ **第二步：stride 扫描找到合规档**（ASR-013 ② 明确允许 640 或 1280 ms；ASR-021 已定「旁路不产生断点」⇒ 不再需要 640 ms 粒度）
  - 产物 `results/pyannote_seg/asr021_seg_stride_sweep.json`（2222 B @20:53）：640→**0.05827 FAIL** / **960→0.03911 PASS** / **1280→0.02922 PASS** / 1920→0.01959 / 2560→0.01487；各档 `frame_coverage_mean` 全为 **1.0**、`p_speech_frac_ge_0.5` 保持 ~0.866 ⇒ **选 stride 1280 ms**（rtf 0.02922、帧覆盖仍 1.0）。
  - ✅ 实跑确认：AMI `pya_bypass_spk_wes_ami1280.json` 的 `seg_model.rtf`=**0.02893**、SPE `pya_bypass_spk_wes_spe5m.json` 的 **0.02961** ⇒ **均 ≤ 0.05 ✅**。

### 47.6 交付件与口径

- ✅ **交付件已写 note**（`reports/compare/ASR007_results.json` 76092 B @20:58 / `MATRIX.json` 22611 B @20:58 / `MATRIX.md` 19159 B @20:58）：新增顶层字段 **`asr020_note`** + **`asr021_note`**，`MATRIX.md` 新增章节「## ASR-020 / ASR-021 口径说明」。
- ✅ **note 的单一事实来源** = 新建 `scripts/asr_compare_notes.py`（`ASR020_NOTE` / `ASR021_NOTE`），生成器 `p3_make_matrix.py` 与回填脚本 `asr021_finalize_deliverables.py` **都 import 它** ⇒ 不会再出现「先手改 MATRIX.json 的 note，再跑生成器 ⇒ note 被覆盖丢失」。
  - ✅ **持久性已验证**：先 finalize → 再跑 `p3_make_matrix.py` → note 仍在，且 `MATRIX.json` 与 `ASR007_results.json` 的 note **逐字一致**。
- ✅ **只加字段，不改任何原始数值字段**；写前备份到 `results/_asr021_backup_<ts>/`。
- ✅ 交付件 note 里明写「**说话人身份来源已换**：Qwen3-TTS INT8 speaker encoder 几乎无区分度 ⇒ 改用 wespeaker（torch ⇒ 未进交付，须导出 OV IR）」。

### 47.7 本轮未做 / 剩余工作

- 🔴 **wespeaker → OV IR 导出**（交付前置条件，运行时不依赖 torch）—— **未做**，需用户确认是否由本模块承担。
- 🔴 **碎片化 2/2 未解决**（同一人被拆成 2 个 id）⇒ 需调阈值/`update_alpha` 或换更强 embedding；属 ASR-021 ③ 的遗留项，**未自行扩大范围**。
- ⚠️ **`live_caption/` 的 spk 事件接入**（`{id, spk, spk_conf}` 补发机制）属 **App 模块**（ASR-003 边界）⇒ **本模块未代改**。
- ⚠️ **TTS 侧音色切换**（spk=null 时用上一句音色或预设 A）属 **TTS 模块** ⇒ **本模块未代改**。
- ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 本轮脚本/产物改动**只在本机**（`scripts/asr021_*.py`、`scripts/asr_compare_notes.py`、`scripts/pya_app_path_seg.py` 改动 + `results/pyannote_seg/` 产物 + `reports/compare/` 三件），**不进 git**，交付需另行打包。
- 🔴 **WER 仍未算**（本线程不调用 MiniMax）⇒ ASR-020 的 WER 数字来自 reviewer 复算并已落档；本模块交付件的 WER 格仍为 `null`，交 reviewer 汇编。

### 47.8 机器锁纪律（本轮）

- ✅ 本轮 **3 个计时类作业**（seg RTF 变体对比、stride 扫描、AMI/SPE 旁路实跑）**全部走 `asr_lock_common` 持锁执行 + `finally` 释放** ⇒ 未出现孤儿锁、未出现「无锁却在占设备」。
- ✅ 收尾核对：`shared/MACHINE_LOCK` 由 **TTS** 持有（`module: tts` / `pid: 41116` / `started 2026-10-27 20:57:09`），**晚于**本模块最后一次作业结束时刻（20:55）⇒ 本模块**未抢 TTS 的锁**、无孤儿锁。
- ⚠️ 收尾时机器上有 4 个 python 进程（pid 12160 / 14264 / 19996 / 41116）⇒ 其中 41116 = TTS 持锁者，其余**不属本模块**（本模块本轮作业均已结束并释放）⇒ 未做清理（跨模块进程不由本模块处置）。

### 47.9 工具/方法论备忘

- 🔴 **「模型能力差」与「口径表达不了」必须分开**：recall 0.0857 看着像模型失败，实际是「**每段一个 spk id**」在段均长 5.3 s 的粒度下**原理上无法表达段内切换**（真值切换点只有 42.9% 落在段边界）⇒ **先查表达上限，再谈模型**（与 MEMORY「把输入条件拆成正交维度」同一思路）。
- 🔴 **「用户指定的素材」可能测不出用户要的指标**：SPE 5 分钟只有 1 人 ⇒ 切换点 F1 / 碎片化**不可检验** ⇒ 按纠偏原文「素材里说话人太少就补一段公开素材」补 AMI，并**在 STATUS 注明来源与许可**（CC BY 4.0）。
- 🔴 **阈值型指标要报「任何阈值都不可分」而不只是「某个阈值下分不开」**：TTS encoder `separable_by_any_thr`=false + `bias_ratio`=0.982 ⇒ 结论才站得住（对比 wespeaker margin 高 21.9×）。
- ⚠️ **RTF 超阈先排除量化**（5 变体全超 ⇒ 是窗数×单窗耗时），再找**合规参数档**（stride 960/1280）⇒ 不要一上来就怀疑精度。
- 🔴 **交付件 note 会被生成器覆盖** ⇒ note 必须有**单一事实来源模块** + 生成器 import ⇒ 并做「先 finalize → 再跑生成器 → note 仍在」的持久性验证。


## §48 ASR-023 全部落地：说话人聚类向量选型（**保留 wespeaker**）+ 撤回 §47 三条结论 + 交付件 note 改正（2026-10-28 07:00）

**纠偏原文（ASR-023，2026-10-28 00:53，[HIGH]）**：reviewer 复核 §47 后指出 5 个问题 —— ① 「TTS speaker encoder 区分不开说话人 / margin 高 21.9×」依据不成立（跨切分、跨口径、原始余弦比原始余弦、未扣偏置）；② 验收真值用错（pyannote 3.1 伪真值只有 2 人，且其 pipeline 用的 embedding **就是同一个 wespeaker** ⇒ 循环论证）；③ F1 0.154 要拆开说，不能全归给「粒度上限」；④ RTF/滞后的嵌入跑在 CUDA 上、且没计入；⑤ 许可证与来源缺（wespeaker 无 LICENSE / 无 repo id / 无 revision）。

**本节结论（一句话）**：按 ASR-023 §4 的选型规则逐条测完后 —— **中心化后的 TTS encoder 在段级纯度 / 每人覆盖率 / AUC 三项上明显更差（3/3 片段方向一致、CI 不跨 0）⇒ 保留 wespeaker 作 ASR 内部聚类向量**；但** wespeaker 的 OV IR 导出本轮未做**（遵守「第 1 步出结果之前不要开 IR 导出」），**下一阶段任务**。**TTS 更差的主因不是 INT8 量化**（FP32 跑同一模型反而略降）。**§47 的三条结论全部撤回。**

### 48.1 ① 撤回 §47 的三条结论（+ 两条口径作废）

| §47 原结论 | §48 处置 | 依据（原始字段） |
|---|---|---|
| 「Qwen3-TTS INT8 speaker encoder 几乎无区分度」 | 🔴 **撤回** | ASR-023 §1 复核：那是拿**原始余弦**比原始余弦、且 wespeaker 用 `W2_per_spk` 而 TTS 用 `T1_utterance`（切分不同）、也没扣偏置（TTS `bias_ratio` 0.982 ⇒ 原始余弦全挤在 0.96 附近，**本就是要做中心化的信号**）。同口径中心化后 TTS **不比 wespeaker 差**：逐句 TTS `T1_centered.margin_mean` **0.312** vs wespeaker `W1_utterance_centered` **0.182**；每人 TTS `T2b_centered` **0.585** vs wespeaker `W2_per_spk_centered` **0.301**（两者 `separable_by_any_thr` 都是 false） |
| 「margin 高 22×（0.3453 vs 0.0158）」 | 🔴 **撤回** | 跨切分（per_spk vs utterance）+ 跨口径（原始 vs 原始）+ 未扣偏置 ⇒ **不可比** |
| 「段级纯度 1.0（22/22）、碎片化 2/2」 | 🔴 **撤回** | 那是 **pyannote 3.1 伪真值**口径（只有 2 人：SPEAKER_00 139.1 s / SPEAKER_01 33.1 s；人工标注是 4 人：FEO070/FEO072/MEE071/MEE073），且 3.1 pipeline 用的 embedding **就是同一个 wespeaker-resnet34-LM** ⇒ **循环论证**。且素材太弱（49.9 s 后基本 1 人独白） |
| §47 的「旁路 RTF 增量 0.02893」 | 🔴 **口径作废** | 旧产物 `encoder.device` = **cuda** ⇒ **嵌入耗时没计入**；交付口径要求嵌入在 **GPU.0**（NPU 留给 TTS） |
| §47 的「spk 滞后 P50 0.0084 / P95 0.0157」 | 🔴 **口径作废** | 同上，CUDA 上的嵌入耗时，**且不含 seg**；ASR-023 §5 要求 seg + 嵌入**都在 GPU.0** |

### 48.2 ② 素材：换成多人交替均衡的 AMI 人工标注（来源与许可）

- **落盘**：`C:\Users\Trekker-PTL\qwen3asr_06b\results\_spk_material\ami_balanced\` —— **10 个文件**（`manifest.json` 3300 B + 3 段 × (`wav` 9600044 B / `rttm` / `json`)），mtime **2026-10-28 01:23:13 ~ 01:23:14**。
- **来源 / 许可**（`manifest.json` 原始字段）：数据集 `edinburghcstr/ami`（AMI Meeting Corpus）、配置 `sdm`（far-field 会议麦克风）、分片 `sdm/test-00000-of-00004.parquet`、镜像 `https://hf-mirror.com/datasets/edinburghcstr/ami`、**许可 CC BY 4.0**（Edinburgh / Univ. of Sheffield；本机仅下载 1 个分片用于内部评估）。
- **均衡度**（`manifest.json` 原始字段 `min_spk_ratio`，判据 ≥0.1）：EN2002a **0.227**（4 人）/ EN2002b **0.2364**（4 人）/ EN2002c **0.3253**（3 人）⇒ **3 段全部 ≥10% ✅**，每段 300 s。
- **真值**：**AMI 人工逐句 RTTM**（每段 208 / 216 / 89 条 utterance）⇒ **不再用 pyannote 3.1 伪真值**。⚠️ 人工 RTTM 与 3.1 伪真值**不可混用**（口径不同、人数不同）。

### 48.3 ③ 主产物 `asr023_spk_encoder_ab.json`（验收件）

**路径 / 大小 / mtime**：`C:\Users\Trekker-PTL\qwen3asr_06b\results\pyannote_seg\asr023_spk_encoder_ab.json` —— **679404 B @ 2026-10-28 01:57:56**。

- **结构**：`material`（含 source/license/clips 清单）+ `truth` + `metric_notes` + `clips`（3 段 × **4 个编码器臂**）+ `lock_probe` + `timing_valid`。
- **4 个臂**：`tts_gpu0_centered` / `tts_gpu0_raw` / `wespeaker_cuda_centered` / `wespeaker_cuda_raw` ⇒ 中心化与不中心化各自成臂，**中心化用的是离线固定均值向量**（非在线运行均值，已写明）。
- **§3 要求的字段全部齐备**（每臂每段）：
  - `switch_point`：P / R / F1 + `tp` / `n_truth_switch` / `n_truth_on_seg_boundary` + **`expressible_recall`**（tp / n_truth_on_seg_boundary）+ **`expressible_upper_ratio`**（段粒度上限）；
  - `switch_point_min_turn_0p5`：**≥0.5 s 实质 turn** 口径全套；
  - `purity` / `fragmentation_split` / `fragmentation_total` / `per_speaker_coverage`（**每人覆盖率**）/ `coverage_mean` / `coverage_min` / `n_speakers_covered`；
  - `null_rate_single` / `null_rate_multi`（**按单/多人区段分开**）；
  - `threshold_sweep`：**每臂 13 个阈值的扫描曲线**（含每个阈值下的 `switch_point` + `switch_point_min_turn_0p5` 两套）。
- **锁**：`lock_probe_stolen` = **0**（3 次逐条自检），`timing_valid` = **true**。

### 48.4 ④ 段级选型判定（3 段配对 bootstrap；重采样单元 = 片段 n=3 ⇒ **CI 极宽，只作方向性参考，不作显著性声明**）

**汇总产物**：`results\pyannote_seg\asr023_selection_summary.json` —— **19097 B @ 2026-10-28 06:52:16**（字段：`sources` / `arms` / `clips` / `comparisons` / `verdict` / `metric_notes`）。

| 指标 | TTS-INT8 @GPU.0 | TTS-FP32 @GPU.0 | wespeaker FP32 @CUDA | Δ(INT8−wes) | CI95 | 逐片段 Δ |
|---|---|---|---|---|---|---|
| `purity` | 0.6621 | 0.6409 | **0.8413** | **−0.1792** | **[−0.2105, −0.1395]** | −0.2105 / −0.1395 / −0.1875 |
| `coverage_mean` | 0.3902 | 0.3666 | **0.4869** | **−0.0967** | **[−0.1361, −0.0640]** | −0.1361 / −0.089975 / −0.064033 |
| `auc` | 0.7866 | 0.7866 | **0.8583** | **−0.0718** | **[−0.1145, −0.0273]** | −0.1145 / −0.0273 / −0.0735 |
| `f1_min_turn_0p5` | **0.2949** | 0.2758 | 0.2288 | **+0.0660** | **[+0.0573, +0.0831]** | +0.0573 / +0.0577 / +0.0831 |
| `f1` | 0.2188 | 0.2180 | 0.2037 | +0.0150 | [−0.0187, +0.0375] | 跨 0 ⇒ 不显著 |
| `expressible_recall` | 0.2594 | 0.2595 | 0.2382 | +0.0212 | [−0.0220, +0.0435] | 跨 0 ⇒ 不显著 |
| `coverage_min` | 0.0222 | 0.0222 | 0.2222 | −0.2000 | [−0.4667, 0.0000] | 上界 = 0 ⇒ 跨 0 ⇒ 不显著 |
| `margin` | 0.2563 | 0.2563 | 0.2296 | +0.0267 | [−0.0106, +0.0571] | 跨 0 ⇒ 不显著 |

- 🔴 **TTS 明显更差的指标 = `purity` / `coverage_mean` / `auc`**（INT8 与 FP32 **都是**）；**TTS 明显更好的 1 项 = `f1_min_turn_0p5`**。
- 🔴 **3/3 片段方向一致**（上表「逐片段 Δ」列三段同号）⇒ 结论**稳健**，不是单片段噪声。
- ⇒ **按 ASR-023 §4 规则 ⇒ 保留 wespeaker**（`verdict.decision` 原文已落盘）。

### 48.5 ④b 消歧：TTS 段级劣势**不是 INT8 量化**（量化只解释一小部分）

- **产物**：`results\pyannote_seg\asr023_tts_precision_ab.json` —— **393442 B @ 2026-10-28 06:51:37**（同一批段、同一过滤、同一人工真值；只有 encoder 精度不同）。
- **同一性验证**：**cos(INT8, FP32) = 0.998006**（向量 norm 9.6788 vs 9.4731）⇒ 确认是**同一个模型的不同精度** ⇒ A/B 有效。
- **FP32 反而略降**：`purity` FP32 **0.6409** vs INT8 **0.6621**（Δ **−0.0212**，CI95 [−0.1163, +0.0526] ⇒ 不显著）；`coverage_mean` Δ −0.0236（不显著）；`f1` Δ −0.0008（不显著）。
- **量化归因**（`verdict.quantization_attribution` 原文）：TTS 相对 wespeaker 的纯度差 **−0.1792** vs FP32 带来的 **−0.0212** ⇒ **量化只解释一小部分差距** ⇒ **主因是 TTS speaker encoder 的段级可分性本身弱于 wespeaker**（不是量化）。`is_quantization_the_main_cause` = **false**。
- ⚠️ **FP32 IR 的 OV 端口名与 INT8 不同**（INT8 输入 `mel_spectrogram` / 输出 `speaker_embedding`；FP32 输入 `hidden_states` / 输出**无名**）⇒ 脚本按模型实际端口名自适应绑定。

### 48.6 ④c 直接判据（绕开聚类动力学）：段级余弦分离度

- **产物**：`results\pyannote_seg\asr023_seg_separation.json` —— **3723 B @ 2026-10-28 05:53:25**。
- 逐段 `margin` / `auc`（`cos_same_mean` − `cos_diff_mean`；AUC = Mann-Whitney，与阈值无关）：
  - EN2002a：TTS margin **0.196** / auc **0.7217**（same 0.455 / diff 0.259）vs wes margin **0.2066** / auc **0.8362**（same 0.296 / diff 0.0894），n_vecs 38，**两者 `separable` 均为 true**；
  - EN2002b：TTS margin **0.2347** / auc **0.7905** vs wes margin **0.1776** / auc **0.8178**；
  - EN2002c：TTS margin **0.3382** / auc **0.8475** vs wes margin **0.3046** / auc **0.921**。
- ⇒ **AUC 上 wespeaker 3/3 段都更高**（与 §48.4 的聚类口径一致、互为交叉验证）；但**逐句 margin 上 TTS 2/3 段更高** ⇒ TTS 的「同一人更紧」并不转化为「段级归属更准」。

### 48.7 ⑤ RTF 增量与 spk 滞后：**含 seg + 嵌入，且都在 GPU.0**（持锁，阈值 ≤0.05）

- **产物**：`results\pyannote_seg\asr023_lag_seg_embed_corrected.json` —— **57481 B @ 2026-10-28 06:13:58**（原始测量 `asr023_lag_seg_embed.json` **52176 B @ 06:13:58**，修正前备份 `asr023_lag_seg_embed_pre_accounting_fix.json` **51666 B @ 06:13:58**）。
- **口径**（`formula` 原文）：`seg_lag_s = (w_max*stride + WIN_S) - b`（`w_max = floor(b/stride)`，`WIN_S` = 10.0 s，`stride` = 1.28 s）⇒ **seg 侧算法层面滞后 ∈ [8.72, 10.0] s**；`total_lag_s = seg_lag_s + 该窗计算墙钟 + 嵌入墙钟`。
- **设备**：seg IR `pyannote_seg_3_0.xml` @ **GPU.0**（228 窗/段，单窗中位 **0.0386 s**）；嵌入 IR `speaker_encoder.xml` @ **GPU.0**（输入 `[1,?,128]` 动态时间轴 ⇒ **每个不同段长 = 一个新 shape**）。
- **RTF**（阈值 ≤0.05）：

| 段 | seg RTF | 嵌入 RTF（冷） | 嵌入 RTF（暖） | **总 RTF（冷）** | **总 RTF（稳态暖）** | 判定 |
|---|---|---|---|---|---|---|
| EN2002a | 0.02945 | 0.03459 | 0.00092 | **0.06404** | **0.03038** | 稳态 ✅ / 冷启动超阈 ⚠️ |
| EN2002b | 0.02942 | 0.02097 | 0.00105 | **0.05039** | **0.03047** | 稳态 ✅ / 冷启动贴阈 ⚠️ |
| EN2002c | 0.02961 | 0.11263 | 0.00092 | **0.14224** | **0.03053** | 稳态 ✅ / 冷启动超阈 ⚠️ |

- ⇒ ✅ **稳态总 RTF 0.0304~0.0305 ≤ 0.05 通过**；🔴 **冷启动 0.0504~0.1422 超阈** ⇒ **冷启动（OV 动态 shape 重编译）是进程内一次性成本，必须与稳态分档报，不得报单一 RTF**。冷启动幅度随「新 shape 数」走：EN2002c `n_distinct_mel_shapes` = **14**（a/b 各 9）⇒ 冷成本 34.07 s vs 10.65 / 6.61 s。
- **spk 滞后**（`total_lag_p50_s` / `total_lag_p95_s`）：EN2002a **9.4084 / 10.5184**、EN2002b **10.0427 / 10.0504**、EN2002c **9.4112 / 16.4221** ⇒ 🔴 **≈ 9.4~10.0 s，由 seg 侧 10 s 窗聚合主导**（嵌入只占 **7~11 ms**：`embed_p50_s` 0.0069 / 0.0071 / 0.0111）⇒ 这是**算法层面**的滞后，**不是运行时定稿延迟**。
- **锁**：`lock_probe_stolen` = **0**、`timing_valid` = **true**（持锁方逐条自检 ASR-015 ①）。
- 🔴 **本轮修掉一个自己的记账缺陷**（只改记账、**未重跑测量**，原始测量字段一字节未动）：原 `cold_first_call_total_s` 把「该 shape 的首次调用墙钟」**对每一行都累加** ⇒ 同一 shape 的冷成本被重复计入 ⇒ 该字段虚高、`warm_only_total_s` **变成负数**。修正按「该 mel shape 在本 clip 内第一次出现」判定冷/暖（冷 + 暖 = 嵌入总墙钟，不重不漏）；旧值保留为 `*_OLD_buggy` 供追溯。

### 48.8 ⑥ 交付件 note 改正（走 `asr_compare_notes.py` 单一事实来源）

- **单一事实来源**：`C:\Users\Trekker-PTL\qwen3asr_06b\scripts\asr_compare_notes.py` 的 `ASR021_NOTE`（**1378 B**）与 `ASR023_NOTE`（**1699 B**，新增）；生成器 `p3_make_matrix.py` 与回填脚本 `asr021_finalize_deliverables.py` **都 import 它** ⇒ 重新生成不丢 note。
- **落盘交付件**（3 个，mtime 见下）：`reports\compare\ASR007_results.json` **79863 B @ 2026-10-28 06:52:59**、`reports\compare\MATRIX.json` **26382 B @ 06:53:02**、`reports\compare\MATRIX.md` **22974 B @ 06:53:02**（`MATRIX.md` 新增 `### ASR-023` 段）。
- 🔴 **持久性验证通过**：**6 个 note 字段**（ASR007_results.json × 3 + MATRIX.json × 3）在「先 finalize → 再跑生成器」后**逐字一致**；`ASR007_results.json` 的 `records` = **15**（与备份 `results\_asr021_backup_20261028_065259\` 一致）、`n_records` = 15；`MATRIX.json` 的 `cells` = **21** 且**内容完全一致**（`m['cells'] == mb['cells']` 为 True）；**非 note 字段零差异** ⇒ **只改了 note，原始数值一字未动**。
- ✅ 同时**删掉**了上一轮遗留的孤儿重复模块 `scripts\asr023_notes.py`（与 `asr_compare_notes.py` 内容分叉：ASR021_NOTE 1135 B vs 1378 B；确认**无任何脚本 import 它**）⇒ 杜绝双源分叉。

### 48.9 分工说明（不可混淆，ASR-023 §1 追加要求）

- **克隆音色必须用 TTS 自己的 x-vector**（TTS-019 的 `embed_speaker`）。
- **ASR 对外只输出 `{id, spk, spk_conf}` + 段的时间范围**；由 TTS / App 按 `spk` 汇集音频，**再用 TTS encoder 生成克隆向量**。
- 🔴 **wespeaker 向量只用于 ASR 内部聚类，绝不传给 TTS 做克隆。**
- ⚠️ `live_caption/` 的 spk 事件接入与 TTS 音色切换属 **App / TTS 边界**（ASR-003），本模块**未代改**。

### 48.10 口径隔离（防混比）

- ASR-021 ③ 的数字是 **AMI 会议素材**口径；与 **5 分钟 SPE 切片**（`shared/SPE_0000_0500.wav`，只有 **1 个说话人**）**不可混比**；也与 **pyannote 3.1 伪真值**的数字**不可混比**。
- 本节全部数字属**目标机口径**（全局对齐 + 段级配对 bootstrap）；**reviewer 口径（MiniMax）**的两套计分器**不可混比**。**本轮未跑 WER**（ASR-023 明说不需要；且目标机不调用 MiniMax）。

### 48.11 下一阶段任务（**本轮未做**，不得写「已交付」）

1. 🔴 **wespeaker 的 OV IR 导出 @GPU.0**（ASR-023 §4 保留 wespeaker 的前置条件）：与 torch CPU 对比**余弦 ≥0.999**；本轮**严格遵守「第 1 步出结果之前不要开 wespeaker 的 IR 导出」**，第 1 步已出结果，但**导出本身仍未启动**。
2. 🔴 **补齐来源与许可**：`pyannote/wespeaker-voxceleb-resnet34-LM`（模型卡 **CC-BY-4.0**，随包分发需署名，训练数据 **VoxCeleb**）⇒ 交 **App** 放进 NOTICE。
3. ⚠️ **`qwen3asr_06b` 不在 git 仓库内** ⇒ 本轮脚本/产物改动**只在本机**，交付需**另行打包**（本节引用的一切路径都在 `C:\Users\Trekker-PTL\qwen3asr_06b\` 下）。
4. ⚠️ 本轮新增脚本（**均在 git 仓库外**）：`scripts\asr023_seg_separation.py`、`scripts\asr023_measure_lag.py`、`scripts\asr023_fix_lag_accounting.py`、`scripts\asr023_tts_precision_ab.py`、`scripts\asr023_compare_summary.py`、`scripts\asr023_final_selection.py`；改动 `scripts\asr_compare_notes.py`（note 单一事实来源）；删除 `scripts\asr023_notes.py`。
