## §175 执行 APP-099（last_ack=APP-099）｜rc7 六臂冒烟重做 + A 机 GPU 同占复现 + dev 树修正 + MANIFEST｜**本条需等 reviewer 复核**

### ① 开工／收尾基线（纠偏文件**只读**，全程未改未提交）

| 项 | 开工基线 | 收尾复核 |
|---|---|---|
| `status/app/CORRECTIONS_APP.md` SHA256 | `F01C5C88…` | `219ef841fc2c11a56fe8117774633c86d4ef8110e1e089b27e5d5608de9ce199` |
| 字节数 | 307394 | 308340 |
| mtime | 2026-11-11 09:28:13 | 2026-11-11 10:38:52 |
| `## APP-xxx` 条数 / 最大 | 99 / APP-099 | 100 / APP-100 |

* 🔴 中途 reviewer 追加 **APP-100**（10:38，长跑改 10 分钟片段）⇒ 开工 99 条 → 收尾 100 条，**不声称「SHA 零改动」**；本文件只读未改未提交。
* 🔴 APP-100 对本轮生效：GPU 同占两臂改用**固定 0–300 s 片段 `--loop ×2`**（本机只有 300.0 s 的 `SPE_0000_0500.wav`，取不到 0–600 s）⇒ 600 s 时间线、两臂完全同段。

### ② 第 0 节 5 项用户决定

| # | 决定 | 落地 |
|---|---|---|
| 1 | 完整版 v2.5 去 CUDA；TTS／克隆说话人编码器默认 GPU.0 | `live_caption/device_config.py` `_DEFAULT_DEVICES_FULL` = ASR/MT 仍 GPU.0（**未变**）、TTS GPU.0；`speaker_enc` 随 `make_engine(device=)` 联动 ⇒ 同走 GPU.0 |
| 2 | MiniMVP 默认 ASR=NPU / MT=GPU.0 | `_DEFAULT_DEVICES_MINIMVP` = ASR NPU / MT GPU.0 / TTS NPU；GUI `_dev_selected` 同源读 `DEFAULT_DEVICES` |
| 3 | `tts_late_drop_sec` 与新语言倍率地板**下次再定** | 未改；§4.6(a) 阈值 4 臂重跑**暂缓** ⇒ §4.6(b) `xv_reg_count`/`xv_reg_at` 无真实运行日志可报（`app442_app099_status_errata.json` → `section6b.status=BLOCKED_BY_USER_DECISION`） |
| 4 | 删除作废 rc6（目录 + zip），rc5/rc7 不动，记删除前后 C 盘空间 | `app438_app099_rc6_delete.json` → `before.free_gb` / `after.free_gb` / `freed_gb` |
| 5 | MiniMVP **暂不打包**（等 ASR-053 KV cache 版 0.6B），修复落 dev 树 | 本轮 **未打 rc8 / 未打 v2.5**；只把脚本准备好并 dev 自测 |

### ③ 第 4 节 8 项逐项 PASS/FAIL

| 项 | 结论 | 数字（json → 字段） |
|---|---|---|
| 1 rc7 六臂冒烟 | **PASS** | `app437_app099_device.json` → `arms[].pass` = **6/6**；MT·NPU / TTS·GPU / TTS·NPU 均真在被测设备上且有产出；`no_auto_redirect=true` |
| 2 A 机 GPU 同占复现 | **PARTIAL** | `app452_app099_device_verdict_recheck.json` → `fixed_criterion.verdict` / `timing_valid` = `False`；`app437_app099_device.json` → `gpu_arms[].sampling.*`；gpu_same_asr_mt: dedicated=0.0 MB / shared=2262.1 MB / rss=7676.5 MB, exit=0, 自然退出；gpu_control_asr_npu: dedicated=0.0 MB / shared=1810.6 MB / rss=7096.0 MB, exit=-9, 框架超时强杀(非程序自崩) |
| 3 dev 树 5 处修正 | **PASS** | `app436_app099_dev_gate.json` → `summary.checks_pass/checks_total` = **33/33**、`neg_detected/neg_total` = **7/7**；`app439_app099_lang_evidence.json` → `pass=true` |
| 4 MANIFEST | **PASS** | `app443_app099_manifest_selftest.json` → `summary` = 9/9 ＋反证 4/4；`app444_app099_manifest_wiring.json` → `pass=true`；真实逐项：`app448_app099_manifest_real.json` → `n_match_total/n_files_total` = **84/84**、`all_match=True` |
| 5 不打 rc8、脚本准备好 | **PASS（未执行全套）** | `app446_app099_reaccept_scripts.json` → `n_pass/n_checks` = **16/16**、`n_neg_detected/n_neg` = **7/7**、`prod_code_unchanged=true` |
| 6 APP-093/094 收尾 | **部分完成／BLOCKED** | (a) 阈值 4 臂按第 0 节 3 暂缓；(b) `xv_reg_*` 无 4 臂真实日志 ⇒ 阻塞；(c) 可分性 `SEPARABLE` ＋ 四组重算 `RAN`（4 组，见 ③-补2）；预设 A 对照组重跑 **NOT_RUN_BLOCKED_BY_SHADOW_ALIGNMENT**；(d) 勘误 + 当前交付配置表见 ④ |
| 7 v2.5 可见变化清单 | **PASS（只列不打包）** | `app441_app099_v25_changes.json` → `n_changes` = **11** |
| 8 EXT v0.3.8 @181233f | **PASS（只核对不暂存）** | `app440_app099_ext_check.json` → `v038.short` = `181233f`；`staging.EXT_VERSION` = `0.3.6`（仍是 v0.3.6） |

### ③-补 判据修正（本轮最重要的自查；不是新增审计闸门）

* 🔴 **`app437` 验收脚本旧判据有三处错**：① `rec['pass']=all(checks.values())` 不看 `exit_code`；② `verdict` 只数 GPU 臂「个数」不看退出状态；③ `timing_valid` 无条件写死 `True`。后果：`gpu_control_asr_npu` 被 `wait(timeout=1500)` 后 `p.kill()` 强杀（rc=-9）仍判 `pass=True`／`verdict=PASS`／`timing_valid=true`。
* 已在 `results/app/_app437_app099_device_jobs.py` **定点修三处**（`pass` 纳入 `exit_code`；区分 `terminated_by_harness` 与 `crash`；`timing_valid`／`verdict` 按实际退出状态重算），并用 `ast` 从修好脚本抽出判据**真跑**、对已落盘原始数据重判 + **7/7 组反证全识破**（`app452_app099_device_verdict_recheck.json` → `pass=True`、`fixed_criterion.verdict=PARTIAL`、`timing_valid=False`、`n_gpu_arms_ok=1`）。
* 🔴 **`app437_app099_device.json` 的 `verdict=PASS`／`timing_valid=true` 作废**（原始证据 write-once 保留、不改写），以 `app452.fixed_criterion.verdict=PARTIAL` 为准。
* 🔴 `rc=-9` 是**测试框架超时强杀**，不是被测程序自崩：修正后两臂 `crash=false`。A 臂（ASR GPU.0 + MT GPU.0，即 B 机 268 s 崩溃组合）**806.3 s 自然退出、未复现崩溃**，峰值 Shared 2262.1 MB / RSS 7676.5 MB；B 对照臂 ASR/MT 已完成（600.4 s 音频、145 句译文），但采样后半段 Shared/RSS 恒定、日志停在 TTS 跳句循环 ⇒ 收尾未退出、与自然退出臂**不可比**，判为无效 ⇒ §4.2 只能 **PARTIAL**。是否重跑对照臂补齐「同样时长」，**交 reviewer 裁定**（本轮不自行重跑）。

### ③-补2 §4.6(c) wespeaker 四组音色归属重算（换嵌入空间，不重跑 App）

* `app445_app099_wespeaker_separability.json` → `verdict=SEPARABLE` / `separability.separable=True`：三人参考两两余弦 **0.129–0.201**（旧 TTS speaker_encoder 是 0.957–0.972）；同人不同段 `same_spk_pairs.min=0.483703` > 异人 `diff_spk_pairs.max=0.401077`（306 / 640 对）⇒ **可分**。纯序关系判据、无自造阈值，反证全通过。
* `app454_app099_wespeaker_voice_attrib.json` → `pass=True` / `verdict=RAN` / `groups=4`；四组 `match_rate_truth_ref`（**旧编码器 → wespeaker**）：**before_dialog3 0.4691→0.3881；after_dialog3 0.3418→0.3881；before_tight 0.6026→0.5231；after_tight 0.3696→0.3953**。判据与 `app329` 逐字一致，只换嵌入空间；TTS dump wav 实测 24 kHz ⇒ 重采样到 16 kHz；四组反证（`truth_cos_suppressed` + `rotated_ref_labels`）全通过；持 MACHINE_LOCK（期间等 ASR 模块持锁 160 s，未抢锁），已释放。
* 🔴 **预设 A 对照组重跑 = 未做**：`app454.preset_a_control_rerun.status=NOT_RUN_BLOCKED_BY_SHADOW_ALIGNMENT`。reviewer 第 3 节要求「在 self_ref 闸门修好以后重跑」，但影子包 `after2` 的 `_maybe_send_self_ref` 计数为 0 ⇒ **未全量对齐 dev 树 §174 闸门修复**，按「混版影子包不能报数」纪律不拿它跑数；且 §4.6(a) 阈值四臂按第 0 节第 3 条暂缓 ⇒ 无干净运行日志。**交 reviewer 裁定**：先同步影子包底座，或指定用 rc7（self_ref 为死路径）重跑。

### ④ 勘误（归档件 write-once，一字不动）

* 🔴 **§174 归档件引用笔误**：`status/archive/STATUS_APP_sec174_20261111.md` 里写的 `app429_self_ref_clone_gate.json` / `app430_pkg_dev_only_assert_gate.json` **不存在**；真实文件是 `results/app/app432_self_ref_clone_gate.json`（8/8）与 `results/app/app433_pkg_dev_only_assert_gate.json`（13/13）。app429 是 §173 指针审计、app430 是 §173 写入。STATUS 活文档 §174 证据行本已正确引用 app432/app433。**归档件不回改**，本行即为勘误。依据 `app442_app099_status_errata.json` → `errata`。
* 🔴 **「交付配置」表（第 24–34 行）已过期**：仍写 v2.2 候选 / v2.1 当前交付、TTS 默认 NPU。**当前真值**：完整版真包 `Confucius4_LiveCaption_v2.4`；MiniMVP `..._v1.0-rc7`（rc6 已作废删除）；完整版默认 ASR GPU.0 / MT GPU.0 / **TTS GPU.0**；MiniMVP 默认 **ASR NPU / MT GPU.0 / TTS NPU**。旧表按「旧正文一字不删」不回改，本行为当前口径。依据 `app442_app099_status_errata.json` → `delivery_table_current`。

### ⑤ rc6 删除与 C 盘空间

* `app438_app099_rc6_delete.json` → `before.free_gb` = **594.986 GB**、`after.free_gb` = **594.977 GB**、`freed_gb` = **-0.009 GB**；只删 rc6 目录与 rc6 zip，rc5/rc7 四个保护对象删除前后均在（`after.protected`）；走 `SHFileOperationW + FOF_ALLOWUNDO`（回收站，可逆）。
* 🔴 **判据更正**：`app438.pass=false` 是旧判据误报 —— `_app447` 把 `SHFileOperationW` 的 `rc=2` 当失败、并隐含「删完应释放空间」；但送回收站属同盘元数据移动，**可用空间本就不释放**（`freed_gb≈0` 正常），`rc` 只是 shell 诊断码。已修 `_app447` 判据；`app453_app099_rc6_delete_recheck.json` → `pass_rechecked=True`、反证 **5/5**。
* 🔴 **可逆性实测**：回收站 `$I` 记录命中 **11620** 条原路径在 rc6 目录下的文件 + **1** 条 rc6 zip 精确记录（`$R` 实体仍在，zip 4420655558 B，与删除前一致），`n_r_missing=0` ⇒ 可从回收站还原。初版 `$I` 解析把 Win10 的「4 字节路径长度」当成路径起点（真起点是 offset 28）导致「零命中」假 FAIL，已修正并在 `app453.why_old_criterion_wrong` 记录。

### ⑥ 锁 / 计时 / 停等

* `app437_app099_device.json` → `lock.{module,pid,started,ended}`；`app452_app099_device_verdict_recheck.json` → `fixed_criterion.timing_valid=False`（原始 `app437.timing_valid=True` 是旧判据恒真值，已作废）；每段持锁 ≤60 min，总预算 55 min；`app448` 大 I/O 与 rc6 删除均**等设备作业结束后**才做，避免 APP-099 §2h「计时被自己的打包作业干扰」。
* 🔴 **停下等 reviewer 复核**：**未打 v2.5、未打 rc8、未通知用户、未调 MiniMax、未改任何默认值或产品判据**（第 3 节裁定除外）；本轮唯一改的是**验收脚本自身的记账判据 bug**（见 ③-补），不是产品阈值／判据。目标机不调 MiniMax。
* reviewer 将在本机对 rc8 的语言 wav 与 dialog3/tight/dave 的 mix.wav 做 MiniMax 回转写。

