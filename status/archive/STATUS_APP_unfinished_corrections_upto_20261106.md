# 归档：STATUS_APP「未完成纠偏」表（2026-11-06，逐字保留）

## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| APP-043 | ASR 说话人接口已交付，APP-039/040 克隆资产可取（真机验收全套） | ✅ 链路与结构已通过（`app186` 总闸门）；🔴 **仍需用户实听 3 段 1.2–1.3× 素材**（`shared/app_accel_listen/`）＋ **reviewer 判定音质 / 不变调 / 可懂** |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | ✅ **已闭合**（§123）：`.lnk` 改为 COM 生成（**2 099 B**），COM 读回 `TargetPath` 指向 v1.13 包内 `Start_LiveCaption.bat`；从 `.lnk` 冷启动 **2 次**均成功 |
| APP-048 | GUI 状态信息按 ASR / 翻译 / 语音输出分区 | ✅ 布局代码在 v1.13 包内（`app185` **64/0**）＋ §123 已清理 markdown 星号与研发术语；🔴 **仍缺一张「运行中」截图** |
| APP-049 | 压缩 STATUS / CORRECTIONS | ✅ 本轮（§123 ④）压缩到 ≤ 40 KB / ≤ 300 行；🔴 需 reviewer 确认归档内容与索引表无误 |
| APP-051 | 重打 v1.13 ＋ APP-043 真机验收 ＋ `ACCEPTED.json` ＋ 桌面快捷方式 | ✅ 三条子项全做完；🔴 **待 reviewer 复核 3 项**（见 §117 ⑤） |
| **APP-052 ①** | 桌面 `.lnk` 是**坏链**（手工拼字节 ⇒ 字段错位 4 字节） | ✅ **本轮已完成**：改用 `WScript.Shell.CreateShortcut` 生成；判据改为 **COM 读回**（`TargetPath` 非空 / 所指文件存在 / 在 v1.13 包内 / `LinkFlags` 含目标定位位）＋ **3 条反证**（手工坏链 / 目标不存在 / 指向包外 **必须判 FAIL**）⇒ `app192` **13 PASS / 0 FAIL**；🔴 待 reviewer 复核 |
| **APP-052 ②** | `ACCEPTED.json` 未绑定重打的 zip；子项口径有缺口 | ✅ **本轮已完成**：`code_fingerprint`（app191 口径）＋ `binding_gate=app191` ＋ **6 个编号子项 ＋ `1b_lnk_shortcut`** ＋ 新 `accepted_at`；zip 的 SHA 记在 `DELIVERY_1.13.json`（**不循环**）；**旧 SHA `6576dabd…` / `3ca36ce3…` 已作废**；🔴 **待 reviewer 复核**（3 个口径缺口：`app175` 旧口径 / `app179` B4 **空真** / APP-048 截图只拍到空闲态） |
| **APP-052 ③** | 包内残留 `results/mt2_acc_outputs/*.json` ＋ notes 仍是「v1.6 修订」＋ docstring 写死开发机用户名 | ✅ **本轮已完成**：`pkg_exclude` 增 `results/mt2_acc_outputs/`（**22 个文件**整目录排除，**不误伤** `results/mt2_accuracy.json/.md`）；`pack_v13.py` 增 **v1.13 修订说明** ＋ 历史段落脱敏；3 个 docstring 改为 `<HOME>` 占位；🔴 **打包闸门实测又抓到 2 类真缺陷**（见 §123 ③⑤） |
| **APP-053** | 说话人切换时字幕显示不同说话人（v1.13 覆盖率 7 % 不达标） | ✅ **本轮已完成（修复 + 验收）**：查因 = **段自身区间口径** + **攒整窗喂音**；修复后 **93.48 %**（43/46）⇒ 与 pyannote 自身差 **2.17–4.35 pp**；`app202` **9 PASS / 0 FAIL**；🔴 **待 reviewer 复核**（① `app195` **M8 恒假判据**已订正为最优编号置换 ⇒ 82.61 %；② **GUI 转写区正式行的 `[Sx]` 前缀仍未取到图** ⇒ 记为未达成） |
| **APP-054** | 说话人旁路**同步阻塞 ASR 主循环**（墙钟 838.5 s / 300 s 音频，最大积压 195.1 s） | ✅ **本轮已完成（止血 + 治本定位 + 验收）**：旁路**默认关闭** ＋ **线程化** ＋ **攒整窗** ＋ **降级不反压**；A/B 实测旁路开 **300.6 s / 积压 1.2 s / 延迟 316 ms** ⇒ 三条判据全 PASS（`app199` **4 PASS / 0 FAIL**）；🔴 **根因在 ASR 侧**（`run_seg_side` 每次调用重编译模型）⇒ 已写 NOTICE **待主会话转达**；🔴 待 reviewer 复核（旁路默认关闭是否认可） |

| **说话人标签覆盖率（同段口径 · 修复后）** | **93.75 %**（45/48 句带标签，**分子分母同一段** Q&A 切片 3291.6–3591.6 s）⇒ 与 app193 参照 95.65 % 相差 **1.90 pp**（≤ 5 pp） | `results/app/app208_app058_spk_retest_evidence.json` → `measured.coverage_pct` / `checks` ② |
| **换人点召回率（APP-058 判据④）** | 口径 A **33.33 %**（4/12 命中、误报 3）／口径 B **58.33 %**（7/12、误报 0）⇒ **均 < 60 % ⇒ 未达标**（参照标注自身与人工标注差 1 处 ⇒ 上限 91.7 %） | `app208…` → `measured.switch_analysis`；`app210_app058_recall_diagnosis_evidence.json` → `method_A_index` / `method_B_text_aligned` |
| **v2.1 内容闸门 / 绑定闸门 / 快捷方式 / 依赖隔离** | `app213` **15/0**（8/8 反证）｜`app191` **18/0**｜`app212` **9/0**｜`app214` **4/0**（reviewer 点名的 5 个开发目录 **0** 命中；扫 6 729 个文件） | `results/app/app213_app057_v21_gates_evidence.json` / `app191_v21_binding_evidence.json` / `app212_app057_v21_shortcuts_evidence.json` / `app214_app057_v21_clean_test_evidence.json` |

