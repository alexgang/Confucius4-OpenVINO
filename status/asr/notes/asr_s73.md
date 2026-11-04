# ASR 巡检 §73 —— 无新纠偏（2026-11-05 05:12）

> 🔴 **本轮结论**：**无新纠偏** ⇒ `last_ack` 保持 **ASR-045** ⇒ 待命，只维护 STATUS。
> 明细备份：`_tmp_STATUS_ASR_bak_asr116.md`（本 worktree 内，不进 git）。

---

## 1. 新纠偏判定（ASR-039 第 1 步）

| 项 | 值 |
|---|---|
| 纠偏文件 | `status/asr/CORRECTIONS_ASR.md` |
| 文件内**全文**条目数 | **14**（ASR-036、ASR-032…035 在「进行中的纠偏」/「最近 5 条」区；ASR-037…045 在「最近 5 条」之后的追加区） |
| 全文最大编号 | **ASR-045** |
| `STATUS_ASR.md` 的 `last_ack` | **ASR-045** |
| 编号 > ASR-045 的条目 | **0 条** ⇒ **无新纠偏** |
| 归档 | `status/archive/CORRECTIONS_ASR_closed_upto_20261030.md`（ASR-001…031 全文） |

⇒ 本轮**不执行任何纠偏**、**不开新实验**、**不跑推理/测速**。

## 2. 本轮做了什么（只读核查 + STATUS 维护）

| # | 动作 | 结果 |
|---|---|---|
| 1 | 拿模块租约 | `acquire asr` exit 0 ⇒ `TOKEN=0aa36b3b` |
| 2 | 查 `MACHINE_LOCK` | App 模块持有（pid 34960，started 2026-11-05 05:02:52，进程存活）⇒ 本轮**未碰设备、未抢锁** |
| 3 | 复核 ASR-045 五项验收留痕 | ✅ 全部在位（见 §4） |
| 4 | 查 ASR-042 ③ 可否单方推进 | ❌ 不可：TTS-048 已闭环（cp unroll 判 NO-GO），差额归 **App 侧减争用** ⇒ 等用户决定 |
| 5 | 写 STATUS（脚本 + 独立复核） | ✅ 22 129 B / 108 行（CRLF 108 / 裸 LF 0），自指大小不动点收敛 |
| 6 | 提交 | `971045c`（`git commit --only status/asr/STATUS_ASR.md`）⇒ 已 push，`HEAD == origin/main` |

## 3. 🔴 本轮发现的 1 处口径缺口（**本模块不自行修改**）

`CORRECTIONS_ASR.md` 的**索引表只到 ASR-036**：

| 项 | 值 |
|---|---|
| 索引表行数 | **36** 行（ASR-001…036） |
| 有全文但**索引表无行**的编号 | **ASR-037、038、039、040、041、042、043、044、045（共 9 条）** |
| 冲突条款 | ASR-036 原文：「CORRECTIONS 文件里只保留：顶部一张索引表（**每个编号一行**：编号 / 一句话 / 状态 已完成·已关闭·进行中）」 |
| 处置 | **CORRECTIONS_ASR.md 由 reviewer 维护且不提交**（铁律 1）⇒ **本模块不改、不提交** ⇒ 已在 STATUS「未完成纠偏」表新增 ASR-036 一行记录，**待 reviewer 补齐索引表** |

🔴 **为什么不自行补**：① 铁律 1（CORRECTIONS 不提交）；② 索引表的「一句话 + 状态」是 reviewer 的口径（哪些算「已完成 / 已关闭 / 进行中」由 reviewer 判定，本模块自填会引入第二套状态口径）；③ 追加式改表会与 reviewer 后续推送产生冲突。

## 4. ASR-045 五项验收留痕复核（✅ 全过）

| 验收项 | 证据（产物 / 字段） | 结论 |
|---|---|---|
| log 出现「说话人旁路窗口：5.000 s」 | `asr108_kernel_5s_natural_rerun.json` → `/arms/0/log_capture/sample_lines/0` = `说话人旁路窗口：5.000 s 音频 / 推理 1.368 s` | ✅ 逐字命中 |
| 召回 ≥10/12、误报 0 | 同上 → `/arms/0/evaluation/analysis_raw/n_hit` = **10**、`n_ref_switches` = **12**、`n_false_positive` = **0**（5 s 与 10 s 两臂同值） | ✅ |
| seg IR 方案与一致性数据 | `asr107_seg_ir_shape_and_consistency.json`（静态 5 s `(1,1,80000)`；帧级最大差 0.0850691647638907；二值化一致率 1.0）+ `asr110_seg_ir_perf.json`（动态稳态慢 12.651 倍 ⇒ 撤回「优先用动态 IR」） | ✅ |
| 客户包文件清单（4 个 + md5） | `status/asr/notes/asr_s72.md` §3（含 `asr_spk_window.py` md5 `7d719e1d7f251be9ce68503be4361807`） | ✅ |
| NOTICE 给 App | `shared/NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md` | ✅ |

## 5. ASR-042 ③ 现状（跨模块协作项，仍未完成）

- TTS 侧：**TTS-047 + TTS-048 已闭环（§69，2026-11-04 12:55）** ⇒ cp unroll 路线判 **NO-GO**（负载下每步边际 1.1517–3.7669 ms，判据 ≤1.0 ms，14 锚点全超标；整帧 K14 合图 vs 串行 ratio 1.0520 / 0.9136 ⇒ 只省 0–8.6 %）。
- 🔴 **TTS-048 差额数字**：contended RTF **1.0577**（solo 0.7659）⇒ 到硬下限 ≤0.82 需**再降 22.5 %**、到设计目标 ≤0.75 需**再降 29.1 %**；只靠 cp 需降 43.5 % / 56.3 % ⇒ **算术不可达** ⇒ **差额只能由 App 侧减争用补（用户决定）**。
- ⇒ ASR 侧 ASR-042 ③（ASR+MT+TTS 同跑对比 TTS RTF）**在「门控进交付运行时」之前没有意义**：TTS 的负载脚本 `qwen3tts_eval/app_load_sim_tts024.py` 复刻的是 App 真实管线，**门控尚未进交付路径**（`asr106` 的注入点是**包装 backend 的 proxy**，交付源码零改动）⇒ 门控开/关对 App 真实负载**暂无差异**。
- ⇒ **本模块单方无法完成**，等用户决定（是否让门控进交付路径 / 是否把减争用交 App）。

## 6. 本轮写盘方式（铁律 20/21/22）

- STATUS **一律用脚本改**（`_tmp_asr116_status_write.py`）：模板 + `@@SZ@@` 占位符 + 不动点迭代（**用上一轮真实数字回填**，不用 0 ⇒ 避免假收敛）+ 原子写（tmp → flush+fsync → `os.replace`）。
- 独立复核脚本 `_tmp_asr116_verify_status.py`（**不复用写入脚本的自检**）判据：裸 LF = 0、CRCRLF = 0、无残留占位符、自指大小 == 实测、`last_ack` 未变、行数 ≤160、bullets ≤15、旧章节逐字未改、新行在「最近更新」顶部、章节标题唯一 ⇒ **PASS**。
- 🔴 **复核脚本自身曾误报 1 次**（`block_of` 返回的第 0 项是标题本身 ⇒ 判「新行不在顶部」误判）⇒ 修判据后重跑 PASS ⇒ 记录此坑。
