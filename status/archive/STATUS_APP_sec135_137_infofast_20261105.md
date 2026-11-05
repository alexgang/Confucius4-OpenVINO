# STATUS_APP §135–§137 正文（2026-11-05 15:28 归档）

> 本件为 `status/app/STATUS_APP.md` 中 §135／§136／§137 三节的**逐字原文**。
> 因 §138 追加后文件超出 APP-052 ④ 限额（≤ 40 000 B），按该惯例把三节正文
> **原样移入归档**，STATUS 内只留指针行。**内容一字未删**。
> 各节的**完整版本**另见 `STATUS_APP_sec135_upto_20261105.md`／`STATUS_APP_sec136_upto_20261105.md`／`STATUS_APP_sec137_20261105.md`。

---

### §135 ✅ **APP-067 ②④ 设备级补齐（ABBA + GUI 臂 + ② 交付物）＋ APP-066 3(a)(b) ＋ 🔴 修 MiniMVP P0（rc2）** ｜ **本条已完成（设备级）｜ 本条需等 reviewer 复核**（2026-11-05 08:38）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec135_upto_20261105.md`（**逐字保留，内容一字未删**）。
> 🔴 **速查**：④ ABBA **10/0** ＋ GUI 臂 **5/0**；② 交付物 **12/0**（`shared/app_listen/v23_clone/`）；3(a) CLI **8/0**；**3(b) 首次 NPU 编译 1209.3 s（真冷）→ 第二次启动 9.5 s（热）**＋ 100 %/150 % 主窗口截图；🔴 **修好 rc2 的 `ACCEPTED.pkg_dir` 与 R2 白名单 ⇒ app191 9/6 → 18/0**；⛔ 3(c) zip 未打。

### §136 ✅ **APP-068 + APP-069 + APP-070 三条新纠偏的代码侧全部落地 ＋ MiniMVP rc3 已出（设备级 3(a) PASS 9/0）** ｜ **本条已完成（代码 + 部分设备级）｜ 仍需 reviewer 复核**（2026-11-05 11:20）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec136_upto_20261105.md`（**逐字保留，内容一字未删**）。
> 🔴 **速查表**（每项都有落盘证据，脚本见归档件）：

| # | 条目 | 结论 | 证据 |
|---|---|---|---|
| ① | **APP-069① 根因** | 🔴 **rc2 的 24 段全零是「落盘算法」假象，不是产品静音** | `app267` **6/0**（模型预测 24 段 vs 实测 24 段**精确对应** 54.18 s vs 54.24 s ＋ **反证** 5 个模型族全复现不出 ＋ 合成侧 peak/rms **76/76 健康**） |
| ② | **①(b)(c) 修 dump ＋ 判据** | dump 改**顺序拼接** ＋ 回填逐句 `wav_t0`/`wav_t1`/`peak`/`rms_db`；判据 4 条 | `app268` **4/0**（rc2 旧 wav **FAIL/受损 24 句**＝reviewer 口径；rc3 新 wav **PASS/零段 0**） |
| ③ | **①(d) v2.2 评估 wav** | `v23_clone` 逐句 wav **0** 段；**ABBA 臂时间轴 wav 3/3 有**（33/29/32 段）⇒ 同一个落盘假象 | `app267` H5 |
| ④ | **APP-068 文件清单/前提** | 4 个交付文件 md5 **逐字对上**；**ASR 已自己清过绝对路径**；清理器能力 1→0；`WIN_S=5.0` | `app266` **7/0** |
| ⑤ | **APP-069⑤ 5 项清理** | torch 拆 `backends_torch.py`（不进包）／`auto` label **动态**（包内实测 INT4-CW）／标题产品名／隐藏说话人行／site-packages 清理 ＋ **G4 整包** | 回归 `app215` **29/0**・`app227` **34/0**・`app229` 反证 PASS・`app237` **9/0** |
| ⑥ | **③＋070① 口径 ＋ 删前清单** | 文案一律「**INT8 权重 · FP16 计算（NPU）· babelvox-openvino-int8**」＋ NOTICE 补许可证；候选删 **8 个 / 975.9 MB**，**一个文件都没删** | `app270` **4/0**（两个独立证据交叉验证：代码级 × 分支级） |
| ⑦ | **④＋070② A+C** | 未就绪**不排队**／就绪**清积压**（只念新句）／GUI「首次准备中 xx%」 | 代码已落；**设备级指标待跑** |
| ⑧ | **rc3 ＋ 设备级 3(a)** | rc3 **6 843.8 MB / 10 503 文件**（导入冒烟 24/24）；3(a) **PASS 9/0**（wall 381.86 s／76 句全成／判据 4 条全过／交付 wav ＋ **带 wav 指标列**的 tsv） | `app269` + `app271` |
| ⑨ | **APP-069② 启动崩溃** | `--check` 臂 **10/10 零崩溃**；GUI 臂 **待锁**（TTS 模块在跑 e2e） | `app272_crash_out/` |

🔴 **本轮未完成**：⑥ MT INT4 vs INT8 对比（脚本 `app273` 已备好）／② GUI 臂 10 次／070① 删 IR（**须先 ③ e2e 证明**）／070② A+C 设备指标／⑦ 3(c) zip（待 ② 完成）。
🔴 **待 reviewer 裁定**：TTS IR 候选删除体积 **975.9 MB** vs reviewer 估「约 567 MB」的**出入**。
🔴 **本轮回收了一个孤儿机器锁**（ASR 的 `MACHINE_LOCK` PID 25792 **已死**，`OpenProcess err=87` 确证 ⇒ 用项目自带 fail-closed 脚本 `_app239_reclaim_orphan_lock.py --reclaim` 回收 ⇒ 非手写 tasklist）。
🔴 **本轮接管死租约（第 3 次）**：上一会话租约 `911516db` 心跳停在 08:33（82 min 前）⇒ `TAKEOVER`；其 PID 48948 **已死** ⇒ 本轮**从断点继续**（未重做已完成的 §135）。
🔴 **`CORRECTIONS_APP.md` 收尾复核**：开工基线 **SHA `3c06baa98d3f612a…` / 206 686 B / 70 条**（mtime 09:35:14）⇒ 收尾时**重新取 SHA/字节/mtime/条数**（若中途被追加则如实记录）。

### §137 ✅ **无新纠偏（70 条 = last_ack APP-070）⇒ 按 APP-046 从 §136 断点续做** ｜ **APP-069⑥ 已完成｜①③④ 需等 reviewer 复核**（2026-11-05 13:37）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec137_20261105.md`（逐字保留，含 **14 个产物**的字节数／mtime／SHA256 清单）。
> 🔴 开工/收尾 `CORRECTIONS_APP.md`：**SHA `3c06baa98d3f612a…`／206 686 B／mtime 09:35:14／70 条**（APP-001..APP-070）⇒ **无编号 > last_ack 的新条目**，收尾与开工**逐字相同**（reviewer 未追加；本轮只读、未改、未提交）。**TAKEOVER 第 4 次**（上租约 `0c4889a6` 心跳停 11:11、`alive=False`）⇒ 从断点续做，**未重做** rc3／3(a)／`--check` 10/10。

| # | 事项 | 结论 | 证据（文件 → 原始字段） |
|---|---|---|---|
| ① | **APP-069⑥ MT INT4 vs INT8** | **本条已完成**：GPU.0／同一 `translate()`／46 段 ⇒ `exact_same_pct=4.35`（2/46）、`chrf_mean=74.029`、`chrf_median=76.697`、`n_different=44`（20 条差异样例落盘）、`wall_int4_s=19.85`／`wall_int8_s=28.91` | `app273_mt_int4_vs_int8_evidence.json`（9 482 B／SHA `29eb9d07731ec9c3…`）＋ `.tsv`（14 513 B／47 行）＋ `app273_mt_compare_run.log` |
| ② | **⑥ 夹具缺陷反证** | 首跑 `APP273_EXIT=2`（**0 段**）：原按 `lang='en'` 读 `minimvp.tts.jsonl`，而 76 行全是中文译文（`lang='zh'`）⇒ 真实英文定稿 = `app253_minimvp_out/minimvp.txt` **46 行**（`summary.segs=46`）；定点修正（唯一命中＋`ast.parse`＋写后逐字节复核） | `app274_app069_loader_fix_evidence.json` **4 PASS / 0 FAIL**（F3 反证：旧口径 0 段）＋ `_app274_fix_app273_loader.py` |
| ③ | 🔴 **口径差异** | reviewer 写 76 段，本机英文定稿仅 **46**（76 = TTS 侧中文译文句数）⇒ 按 46 跑、**未切句凑 76／未改参照**；`chrf_impl` = `SequenceMatcher.ratio()*100`（**非 sacrebleu chrF**）⇒ **需等 reviewer 复核** | `app273…evidence.json` → `source.scope_note`／`source.reviewer_expected_n_segments=76`／`chrf_impl` |
| ④ | **APP-069② GUI 臂** | **需等 reviewer 复核**：`--check` **10/10 零崩溃**（§136）；GUI 有效启动 **0/10**，2 次验证均 `loaded=false`／`rc=1`／`wall≈90.5 s`／日志 1 行 ⇒ **harness 超时被 terminate，非产品崩溃**（`crashed=false`、rc≠3221226505）；已补音频源（§135 `app259` L261）＋ `PYTHONUNBUFFERED`，本会话仍取不到「模型加载完成」 | `app276_app069_gui_harness_fix_evidence.json` **4/0**；`app272_crash_out/app272_crash_stats_evidence.json` → `n_runs=12`／`n_crash_0xC0000409=0`／`crash_rate_pct=0.0`／`verdict=INCOMPLETE`／`by_phase.gui.n=2` |
| ⑤ | **设备纪律** | 3 次设备作业均先探安静窗口（20 s，`QUIET True`）＋持 `MACHINE_LOCK`；**回收 2 个孤儿锁**（asr PID 46528／app PID 47088，均 `OpenProcess err=87` 确证死）⇒ 项目 fail-closed 脚本 `--reclaim` | `app273_mt_compare_run.log`／`app272_gui_phase_run*.log`／`app275_gui_probe.log` |

🔴 **仍待办（§136 未清项，不越界）**：⛔ **APP-070① 删 IR**（**975.9 MB vs reviewer 估 567 MB 待裁定**；顺序 清单→删→e2e ⇒ **一个文件都没删**）｜⛔ **APP-070② A+C 设备指标**／**APP-069④ (i)–(iv)**（冷启 ≈ 20 min）｜⛔ **APP-069⑦ rc3 zip**（依赖 ② 完成＋用户通知）｜⛔ **APP-069① reviewer 回转写 MER ≤ 8 %**（不自行调 MiniMax）｜⛔ **v2.3 继续暂缓**。
🔴 **未通知用户／未改桌面快捷方式／未动 v2.1、v2.2、rc1、rc2 一字节**（rc3 目录为 §136 构建，本轮未改）；本轮产物 **14 个**（全量元数据见归档件），**未打任何 zip**。

