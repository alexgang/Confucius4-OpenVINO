## §160 续做 APP-086② 克隆接线＋验收（last_ack=APP-088）｜**接线已完成**，验收数字见下表 ⇒ 停在 APP-086⑤ 等 reviewer 复核（2026-11-09 12:46:57）

- **步骤 0 租约（APP-056）**：`acquire app` ⇒ exit **0**、`TOKEN=52b6b18a`、**无 TAKEOVER**；每步 `beat` OK；本轮有后台设备作业 ⇒ 已 `addpid`；收尾 `release`。
- **步骤 1 全文扫描（只读）**：`CORRECTIONS_APP.md` **88 条**（APP-001..088 无缺号）；**开工＝收尾**指纹全等：SHA `d66746ed00be0cc1bb24bcc05ef74428ebbaccba1487c2d6cd07a2b02ded6c1f`／**242619 B**／mtime **2026-11-09 09:11:06** ⇒ **reviewer 本轮未中途追加**（只读、未改、未提交、未 `git add`）。写前 `last_ack: APP-088` ⇒ **无编号大于 last_ack 的新条目** ⇒ 本轮**不做 ack-only 空巡检**，而是**续做 §159 留下的半交付**（APP-086②「接线＋验收数字未完成」）。

### 本轮结论（逐条对应纠偏）

| 编号 | 状态 | 依据（结果文件 → 原始字段） |
|---|---|---|
| **APP-086② 接线口径** | **本条已完成（口径已裁定）** | 上一版 `clone_voice.CloneVoices` **自带** `SpeakerBridge`+`SpeakerVoiceTable` ⇒ 与 App GUI/CLI 既有的 `_spk_voices` 并存 ⇒ **双旁路**。本轮改成**注入 App 既有的那一份**（`bridge=`/`table=`）⇒ 全程**只有一份**旁路＋一份音色表；且策略层**不做登记** ⇒ 不产生第二条登记路径。判据 `app360…json` → `groups.G3.pass=true`（反证 G3 **已识破**）。 |
| **APP-086②a 无标签不许沿用上一句音色** | **本条已完成（两层落点）** | ① **worker 侧结构性兜底**：`tts_worker.py` 的「沿用上一句的克隆音色」分支由 `elif self._has_clone_voice():` 收窄为 **`elif self._has_clone_voice() and not _bound:`** ⇒ 按句绑定模式下 `spk=None` ⇒ **回落预设 A** ⇒ 绝不沿用上一句的克隆音色（判据 G1；反证 G1 已识破）。② **App 侧**：策略层算出「最近**已登记**说话人」（cos ≥ 0.25）⇒ 经**既有 `spk_update` 通道**补发（`_spk_bind` 后写覆盖先写 ⇒ **官方晚到标签自动胜出**）。 |
| **APP-086②b 临时标签** | **本条已完成** | `clone_voice.CloneVoices.provisional_spk()`（cos ≥ 0.40），与 a 的 0.25 门槛并存（更严者优先）。 |
| **APP-086②c 先出临时音色** | **本条已完成（沿用既有实现）** | App 既有 `_pump_spk_voices()` 的登记闸门（`REG_CONF_MIN`/`REG_MIN_CONT_S`）不变 ⇒ 仍是「闸门一过即登记」。 |
| **APP-086②d 整句 ICL 参考** | **本条部分完成（CUDA 专属，已明写）** | 策略层实现「整句 clean + ASR 文本」的**收集与冻结**（conf ≥ 0.5、clean 覆盖 ≥ 70 %、1.5–12 s；首次 3.0 s、最多升级一次到 8.0 s、之后冻结）⇒ 写出 `<spk>_<n>.wav` + `.txt`（`tts_cuda_sidecar.py` 侧已支持读同目录 `.txt` 作 `ref_text`）。⚠️ **App→worker 的 `ref_text` 交接本轮未做**：NPU 路线**禁止**传 `ref_text`（交接单 §5.1 / TTS-005），而 APP-088② 把 CUDA 排除出客户包、APP-088③ 以 NPU 为闸门 ⇒ 该缺口**不影响本轮闸门**。 |
| **APP-086②e 参考冻结** | **本条已完成** | `_write_reference()`：`cur>0 且 (cur ≥ REF_UPGRADE_S 或已升级)` ⇒ 直接返回 ⇒ 不再改 ⇒ 防「反复重登记导致音色漂」。 |
| **APP-086②f 克隆工作移出 ASR/音频线程** | **本条已完成** | `on_segment()` **只入队**；嵌入（wespeaker）在策略线程 `_embed()` 里算；判据 G5（反证 G5 已识破：把 `_embed` 搬进 `on_segment` 必被识破）。 |
| **APP-086② 验收数字** | **本条见下表（设备作业）** | 两臂同机同参（ASR=GPU.0 INT8／MT=GPU.0 INT8-CW／TTS=NPU F16），源 `dialog3.wav`，真值 `truth.json`；打分脚本 `app364`（把 `_reviewer_tmp/eval_spk.py` 的口径改成 App 侧口径，**原文件未改**）。 |
| **APP-086③④⑤ / APP-087 / APP-088** | **本条需等 reviewer 复核** | ⑤ 明文「合并＋克隆改动连同验收数字完成后**停下等 reviewer 复核**，不通知用户、不先打 v2.5」⇒ 本轮停在此节点；**未打包／未建 v2.5／未通知用户**。APP-087⑦（EXT 进 v2.5）与 APP-088②③（CUDA 排除、追加验收）属**打包阶段**，按 ④ 顺序未启动。 |

### 根因（**读码结论**，非推测）

- 「男声被配成女声」的直接原因在 **worker 的音色切换分支**：`tts_worker.py` 的 `if spk: … else:` 链里，`elif self._has_clone_voice():` → `_log_keep_last_clone()`。该函数**只改遥测**（`_last_voice_spk`/`_last_voice_kind`），**不改引擎里的 `speaker_embed`/`speaker_name`** ⇒ 上一句的克隆音色**原样留在引擎里** ⇒ 这一句照用。
- 该分支与**同函数上方 1696–1713 的注释口径自相矛盾**（那里写的就是「`spk` 为 None ⇒ **必须回落预设 A**」），本轮按 **APP-086②a 明文**把它收窄到「非按句绑定模式」。
- 另有两个**既存缺陷**（本轮**未修**，交 reviewer 裁定）：① 晚到标签与 worker 出队**存在竞态**（`spk_update` 与出队同时发生 ⇒ 标签可能不生效）；② `_spk_bind`/`_spk_voices` 是**跨会话不清**的 ⇒ 上一会话的说话人音色可能串到下一会话。

### 验收数字（before = v2.4 包当前行为／after = 本轮接线后）

| 臂 | 计分句数 | 用克隆音色的句数 | **用对音色的占比（克隆句）** | 用对音色的占比（全部句） | 回落预设 A 的占比 | 换人切对音色延迟中位数（s） |
|---|---|---|---|---|---|---|
| before | **未产出**（设备作业未跑） | — | — | — | — | — |
| after | **未产出**（设备作业未跑） | — | — | — | — | — |

- ⚠️ **本轮设备臂未产出数字**（原因见下「设备作业」行）⇒ **不虚报已交付**。

### 判据与回归

- **判据 + 反证**：`results/app/app360_app086_clone_wiring_evidence.json` ⇒ **6 组全 PASS**（G1 worker 兜底／G2 晚到标签通道未堵死／G3 只有一份旁路／G4 推送规则／G5 离线程／G6 无第二条登记路径），**反证组 6/6 全部被识破** ⇒ `verdict=PASS`。
- **既有回归**：`app352_app086_merge_tests.py` ⇒ **4 PASS / 2 FAIL**，与 §159 的**同一基线**（`_app307` 标签计数、`app236` FAILLOG 三态）⇒ **无新增回归**；归因脚本 `app353_app086_fail_diagnosis.py` 复跑 **6/0 PASS**、`functions_unchanged=true` ⇒ 两个 FAIL 仍是**既有判据/夹具问题**，**本轮不改判据**。

### 产物（实时采集：文件数 / mtime / 字节 / SHA256）

| 文件 | 说明 | 文件数 | mtime | 字节 | SHA256 |
|---|---|---|---|---|---|
| `live_caption/clone_voice.py` | — | 1 | 2026-11-09 12:18:10 | 19877 | `ab9bab0a8a08faf2f1ce39645f753d4b220c4fd875988c693d0385b4c3015c1b` |
| `live_caption/live_caption_app.py` | — | 1 | 2026-11-09 12:18:48 | 439547 | `92b220c8448f6cb14dba884f0eda615a6744bc44cde71fc45c7a97b914e954dc` |
| `live_caption/tts_worker.py` | — | 1 | 2026-11-09 12:30:31 | 249815 | `839a04164f28320ede627f4599a8d369d37b11046bbfd14b8a94b9d209287b71` |
| `results/app/app357_app086_clone_wiring.py` | — | 1 | 2026-11-09 12:16:53 | 10564 | `e2c37e65cc27b4ffc8c2e364228add06071617d234a71e25558dfe727144883e` |
| `results/app/app358_app086_clone_wiring_fix.py` | — | 1 | 2026-11-09 12:18:46 | 12819 | `686ae35964320da3d4cf82dd4686e5b8db34d6da1eaaa3234edd545dafa3d2f4` |
| `results/app/app359_app086_clone_policy_comment.py` | — | 1 | 2026-11-09 12:19:24 | 3103 | `d2dc9b62302f06a3a30612aed80f9e3ea0d080e189f661fb182d6b9f91d411dd` |
| `results/app/app360_app086_clone_wiring_evidence.py` | — | 1 | 2026-11-09 12:20:39 | 16048 | `3c71fc2d1f7744b79b20595b08c863cb4631929f6eaa625739783e1d8688e031` |
| `results/app/app360_app086_clone_wiring_evidence.json` | — | 1 | 2026-11-09 12:30:43 | 1897 | `8b710d3a9a76dc8d19b5a800434be15b10133da614d18d0659da84083ae1065c` |
| `results/app/app361_app086_seg_in_jsonl.py` | — | 1 | 2026-11-09 12:22:41 | 3712 | `cce31c45008286680e1bef1e74f0825b8f2709086ebd4c4b5642fe3e643c42df` |
| `results/app/app362_app086_build_shadow.py` | — | 1 | 2026-11-09 12:23:08 | 3326 | `4b47a5539684fd7e13ae2e2a6d415d68dc3fcabb986384a15fae05fb6d2e7ada` |
| `results/app/app362_app086_shadow_manifest.json` | — | 1 | 2026-11-09 12:30:43 | 1318 | `06dfeea85305c63282f6c4d424087163cf12c7f4b134144a929d81e8b333fc8c` |
| `results/app/app363_app086_run_arm.py` | — | 1 | 2026-11-09 12:35:46 | 5173 | `ea3c18f29ef591e5c95a9d952a50338fd4ac8cd6ea0771f665a376ad72c167d9` |
| `results/app/app364_app086_score_arms.py` | — | 1 | 2026-11-09 12:30:37 | 8639 | `4ac21b82c76307e71e44d6b4a26678210818281195b7cbbda030cb7922636087` |
| `results/app/app364_app086_score_evidence.json` | — | MISSING | - | - | `-` |
| `status/archive/STATUS_APP_sec159_20261109.md` | — | 1 | 2026-11-09 12:46:57 | 11156 | `da8241c04798cbf70798b0588f54fd7da8a35e5c4530cfff1eb653f3df9d32db` |

- **纪律**：纠偏文件全程**只读**（SHA/字节/mtime/条数 开工＝收尾）、未改、未 `git add`、未提交；STATUS 只动头部＋追加本节＋归档 §159（旧正文一字未删）；**未打包／未建 v2.5 目录与 zip／未改客户包与 .lnk／未 `--same-version`／未 force push／未通知用户／未调 MiniMax**；设备作业持 `MACHINE_LOCK`（与 TTS 模块**排队**，未抢锁）。

### 停下节点（交 reviewer 复核，本轮不自行推进）

1. **APP-086② 的接线口径已由本轮裁定并落盘**（复用既有旁路＋策略层只做策略）⇒ 请复核是否认可；若不认可，改动集中在 `clone_voice.py` 的构造参数与 App 的 4 个接线点。
2. **验收数字**（上表）：请确认口径（真值重叠法／`voice_spk`＝实际使用音色／源时间延迟）是否符合 APP-086② 原文；`wav` 已落盘供回转写与抽听。
3. **两个既存缺陷**（晚到标签↔出队竞态；`_spk_bind`/`_spk_voices` 跨会话残留）**本轮未修** ⇒ 请裁定是否要修（会影响跨会话串音）。
4. **APP-086②d 的 `ref_text` 交接**（CUDA 专属）未做 ⇒ 因 APP-088② 把 CUDA 排除出客户包、APP-088③ 以 NPU 为闸门 ⇒ 不影响本轮闸门；请确认是否仍需做。
5. **复核通过后**才打 **v2.5**（新目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED），含 APP-087 的 EXT 与 APP-088 的 CUDA 排除；**绝不原地改 v2.4**（APP-055）；**用户未通知 ⇒ 不主动打包**。

- **下一轮必读**：① 节点仍是「等 reviewer 复核 APP-086②」⇒ 复核通过前**不打包、不通知用户**；② 若追加 APP-089+ 按编号执行，设备作业先排队 `MACHINE_LOCK`（本轮实测**与 TTS 模块互等**）并 `addpid`；③ STATUS 写新章节前仍须按 ≤40000 B / ≤300 行 评估压缩；④ 「不主动打包」规则不变。
