# STATUS_APP §140 正文归档（2026-11-06）

> 本章是 `status/app/STATUS_APP.md` 的 §140 **逐字正文**。STATUS 主文件按
> APP-049 / APP-052 ④ 的限额（≤ 40 000 B / ≤ 300 行）只保留速查行。

## §140 APP-075 / 076 / 077 / 078 逐条执行（2026-11-06 13:59:48，Get-Date 实测）

### 0. 租约 / 纠偏文件基线（APP-056 / 步骤 4）

* 租约：`session_lease.py acquire app` ⇒ **TAKEOVER**（上一会话心跳停、alive=False），
  token `d81f6e75`；每步 beat；收尾 release。
* 🔴🔴 **reviewer 本轮中途追加了新条目** ⇒ **不得声称「SHA 零改动」**：
  | | SHA256 | 字节 | mtime (UTC+8) | `## APP-` 条数 |
  |---|---|---|---|---|
  | 开工 | `3f759ebe0b61738c360ed6bc9ba043e5452dde31881b7c27ee03b3a80ed7f359` | 219 810 | 2026-11-06 09:25:17.368967300 | **77**（APP-001..077） |
  | 收尾 | `bbc95c4382f29fa3c8b4f1b49ff644339b025f78447a3bb263e6b680ad4d82af` | 220 735 | 2026-11-06 13:31:54.736485600 | **78**（新增 **APP-078**） |
  ⇒ `CORRECTIONS_APP.md` 全程**只读、未改、未提交**；新增的 APP-078 已按编号顺序一并执行。

### 1. APP-075 — **本条需等 reviewer 复核**（未完成，v2.3 不打包）

**(a)(b) 代码落地**（上一会话遗留，本轮复核并纳入证据）：
`live_caption/speaker_voice.py`（+382 行）与 `live_caption/live_caption_app.py`（+105 行）：
`note_final(seg, spk, clean_ranges=None, spk_conf=None)`；新增 4 个常量
`REG_CONF_MIN=0.5` / `REG_MIN_CONT_S=2.5` / `SWITCH_GUARD_S=0.5` /
`CONT_GAP_TOL_S=0.5`；`qualified_runs()` / `registration_ticket()` /
`mark_registered()` / `mark_fallback()` / `gate_stats()`；最长合格段优先、
只有更长合格段才升级；无合格段回落预设 A 并记日志。
自检 `results/app/_app294_gate_selftest.json` **11 PASS / 0 FAIL**
（S2 最终登记票 `[44.8, 102.4]` 57.6 s，F0 中位 114.29 Hz；反证「先来先登记」
会选女声段 19.2–32.0 s / 188.24 Hz ⇒ 判据非恒真）。

**(c) 第二份材料复验**：`results/app/_app298_conf_window_recheck.json`
**3 PASS / 0 FAIL**（ASR-122，900 s / 3 clip / 136 段）：
`REG_CONF_MIN=0.5` 挡住 9/30 首现段；换人边界首现段 18/27 的 conf ≥ 0.5
⇒ conf 门槛**挡不住边界段**（与单样本一致）；8/8 低 conf 首现段均落在换人边界。
caveat：该材料无 `clean_ranges` 具体区间，只能复验 conf 维度。

**(d) 诊断落盘**：`results/app/app299_app075_reg_diag/`（13 文件）。
🔴 **mode = `offline_stat_embed`**（纯 CPU 统计嵌入），其 `mode_note` 自述
「**不能**替代 reviewer 的真 x-vector 判据」；判定 **5 PASS / 1 FAIL / verdict=FAIL**
—— 硬判据「S2 登记向量对原声 S2 余弦 > 对其它说话人」不成立
（cos_S2_S2 = 0.745841 < cos_S2_S1 = 0.772995）；反证项 PASS
（换成 S1 后 cos 降到 0.545746）。⇒ **真 x-vector 余弦矩阵仍缺**。

**(e) r2 交付**：`C:\Users\Trekker-PTL\shared\app_listen\v23_clone_r2\`
（**不覆盖** `v23_clone/`）⇒ **当前磁盘实测 54 文件 / 20 175 499 B**，
且 `manifest.json` 自记 `n_files=54` / `n_bytes=20175499` 与磁盘**完全一致**
（`results/app/_app309_fix_r2_submit.json` **18 PASS / 0 FAIL**，
`manifest_rev=4`）。

🔴 **口径订正（本轮自检发现，不得沿用旧数字）**：

| 阶段 | 文件数 | 字节 | 说明 |
|---|---|---|---|
| 首版 `manifest.json` 自记 | 52 | 20 160 623 | 写 manifest **之前**扫描，不含自身；且**缺 `submit.jsonl`** |
| 写完 manifest 后磁盘实测 | 53 | 20 170 791 | ＋`manifest.json` 自身 10 168 B |
| `_app309` 补齐并重签后（**当前**） | **54** | **20 175 499** | ＋`submit.jsonl` 4 486 B；重签 `manifest.json` 10 390 B |

🔴 **静默漏拷已修复**：`_app303_build_v23_clone_r2.py` 旧代码按
`tts_on_clone_0.submit.jsonl` 找源，但设备作业真实产物叫
`tts_on_clone_0.seg.jsonl.submit.jsonl`；旧写法 `if os.path.isfile(s)`
会**静默跳过** ⇒ r2 一度缺 jid→seg 映射（APP-067 ①(b) 标签晚到的关键诊断件）。
现改为显式 `_JSONL_SRC` 映射 ＋ `assert os.path.isfile(s)`（缺源直接失败）。
反证：旧文件名 `tts_on_clone_0.submit.jsonl` 不存在、真实源存在 ⇒ 判据非恒真。
补齐**只新增 1 个文件**，首跑验收「旧 52 个产物 SHA 逐条未变」，
`incomplete` 原文保留（未掩盖未完成项）。
判据本身修过两次：① 文本包含判据把我写在注释里的旧写法当成真实分支 ⇒ 假 FAIL；
② AST 判据误把读 `tts.jsonl` 的**合法容错** `if` 当成静默跳过 ⇒ 假 FAIL；
最终收窄为「`If` 的 body 内含 `shutil.copy2`」⇒ **18/0**。

顶层 7 个文件（mtime 2026-11-06 13:37:33，`submit.jsonl`／`manifest.json`
为 13:59 补齐重签）：

| 文件 | 字节 | SHA256 |
|---|---|---|
| `clone_r2.wav` | 10 026 284 | `bd7784835459614c815339cc460c9ab46f79c851f2a8f8b3f9e52c15a304d1df` |
| `f0_by_sentence.csv` | 8 141 | `8176d09f4387ccded5c969051af81eb044692ae55a9656b76e5efc577a119675` |
| `f0_by_sentence.json` | 26 189 | `0bbe66b8d4070a6cc9cda2c715b4c3c3cef68b9951d30389034fabf78bc4ac8b` |
| `gate.json` | 9 820 | `bca5ebf6059448e5ff2a7efd682551d1ce8041a49e87d619365effd2a373f2af` |
| `seg.jsonl` | 4 125 | `a95143efc50e32ba0dcfb8ce857eca7282199c0a6034d451f90eac4af14fbce3` |
| `submit.jsonl` | 4 486 | `9218f961f538621b3e2bc6feb250f6480c145661e8dbfc93e772359066336ab7` |
| `tts.jsonl` | 57 800 | `ba64da9b709d6e12e3560f65f75b8310b93dcd0c1262574f4e73b0f7b0079080` |
| `manifest.json` | 10 390 | `c6be9c50eb8ef752e7280a2489c4af47b85ef9e87d16357b848aa085352e4817` |

另 `wav/` 46 个逐句 wav（24 kHz / 单声道 / 16 bit）。逐句 F0 用 `app246` 的
`f0_autocorr`（含八度误差修正），与 `_app295_f0_verify.json` **同一把尺**。

🔴🔴 **F0 闸门 21 PASS / 19 FAIL / 6 NONE ⇒ 克隆男声变女声未修复**：
19 个 FAIL **全部是 `male→female`**（jid 7–25，原声 100–129 Hz 男声，
配音 188–245 Hz 女声）。设备日志
`results/app/app301_device_out/tts_on_clone_0.log` 明确显示
`✅ 说话人 S2 的音色已登记（x-vector，6.4 s）` / `（x-vector，10.0 s）`
⇒ **登记门槛已生效、S2 也成功登记，但登记的音色仍是女声**
⇒ 不是「回落预设 A」造成，需 reviewer 用真 x-vector 复核登记段的实际归属。
反证组 PASS：旧 `v23_clone/wav_clone/male_0*_clone.wav` 三段用同一把尺
实测 218.18 / 255.32 / 218.18 Hz（全为女声）⇒ 判据非恒真。

🔴 **本轮未完成项（不宣称已交付）**：
  ① 第 2 臂（预设 A 对照）**未跑** —— 后台设备作业 PID 16772 在会话中断时被杀；
     `app301_device_out/` 只有 `tts_on_clone_0.*`。已用 ctypes
     `OpenProcess` err=87 确证死亡后回收孤儿 `MACHINE_LOCK`。
  ② **真 x-vector 余弦矩阵未产出**（app299 是统计嵌入，硬判据 FAIL）。
  ③ 第 1 臂也未跑满 300 s（46 句 / 82 个 submit jid）。
⇒ 按 APP-075 原文「**需 Opus 复核**：待 r2 交付后（F0/x-vector 复核）」
  **做到 r2 交付即停止**，不自行往下判定通过；**v2.3 不打包**。

### 2. APP-076 — **本条已完成**

* dev 侧同源：`live_caption/speaker_tracker.py` 新增 `_MIN_CLEAN_RATIO_ENV =
  'LIVECAP_SPK_MIN_CLEAN_RATIO'`，用 **AST 静态解析** ASR 源码模块级
  `DEFAULT_MIN_CLEAN_RATIO`（避免 import 拉 numpy / 兄弟模块）；
  仅当 App 值 ≠ ASR 默认值时显式传 `min_clean_ratio`，其余让 ASR 按自身
  优先级执行。运行时实测 `_MIN_CLEAN_RATIO = 0.6 / 同源
  asr052_speaker_tracker_api.DEFAULT_MIN_CLEAN_RATIO=0.6`；
  `LIVECAP_SPK_MIN_CLEAN_RATIO=0.75` 可覆盖；`WIN_S_DEFAULT` 仍 5.0。
  顺带订正该处新增注释里的 1 个替换字符（乱码）。
* `live_caption/sync_c164_spk_assets_to_pkg.py` 的 `ASR_FILES` **4 → 5 项**
  （补 `asr_runtime_switches.py`）。
* **md5 对照**（`results/app/_app304_app076_md5_audit.json`，**39 PASS / 0 FAIL**；
  三方 = ASR 源 `qwen3asr_06b/scripts/` / 影子包
  `shared/app067_shadow/app/asr_spk/` / 旧包 v2.2）：

  | 文件 | ASR-050 交接单 md5 | ASR 源 | 影子包 | v2.2 旧包 |
  |---|---|---|---|---|
  | `asr052_speaker_tracker_api.py` | `61be393ce6343bfa63892ce0c35f5c44` | ✅ | ✅ | `e6826be3c8aa…`（旧 0.8） |
  | `asr052_spk_runtime.py` | `2ff82933edec80becd01f9d28d202ea6` | ✅ | ✅ | `3e76ff915de6…`（旧） |
  | `asr_thread_defaults.py` | `0482f9c49105490ac219194c2fa7c184` | ✅ | ✅ | ✅ 同值 |
  | `asr_spk_window.py` | `7d719e1d7f251be9ce68503be4361807` | ✅ | ✅ | **ABSENT** |
  | `asr_runtime_switches.py` | `7f12e9a5575d7a88cafcd3f54689e326` | ✅ | ✅ | **ABSENT** |

  ⇒ v2.2 旧包仍是 3 个文件，**本轮未原地改**（APP-055）。
* **app193 正则口径复核**：首跑用自制宽松正则误把注释标题里的历史值
  `0.8` 当成第一个匹配 ⇒ 判据错，已改用 app193 的真实正则
  （`re.search` + 必须带 `=` 的签名形态）⇒ 读到的第一个值 **0.6**；
  反证「把签名改成 0.8 ⇒ 读到 0.8」PASS。
* **克隆登记门槛不放宽**（APP-075/076 第 3 条）：4 个常量 AST 实测
  0.5 / 2.5 / 0.5 / 0.5 全部未变；反证「改成 0.3 会被判 FAIL」PASS。
* **MiniMVP 适用性（如实写）**：`…_rc3_perftest_rev2.zip` 实测
  `app/asr_spk/` = 0、`models/spk/` = 0、`ext/` = 0，**但仍带 3 个旁路代码文件**
  （`speaker_tracker.py` / `speaker_voice.py` / `clone_collector.py`）
  ⇒ 旁路**内核与模型都不在**，`min_clean_ratio` 改动在 MiniMVP 里
  无可运行消费者 ⇒ **APP-076 第 2 条对 MiniMVP「不适用」**。
* 🔴 **v2.3 打包待办**：带 5 个 ASR 文件 +
  `models/spk/pyannote_seg_3_0/fp16-w5/`（本轮**未打包**，未落进任何包）。

### 3. APP-077 — **本条已完成**（② 待 v2.3 打包生效）

**① 固定 token**（`results/app/_app302_app077_token_gate.json`，**26 PASS / 0 FAIL**）：

| 包 | 字节 | 条目 | SHA256 | `ext/bridge_token.txt` |
|---|---|---|---|---|
| `Confucius4_LiveCaption_v2.0.zip` | 11 233 134 015 | 14 317 | `8198924f9aed30010c0fb80f472278f322f160c9b63cbe7861001dbda056eed9` | 32 B |
| `Confucius4_LiveCaption_v2.1.zip` | 11 233 135 359 | 14 317 | `835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4` | 32 B |
| `Confucius4_LiveCaption_v2.2.zip` | 11 233 149 299 | 14 317 | `ea5c5c850f8836a7edab982611cdd59d0ba0e83f8d5ff880cc797b7c67c23b75` | 32 B |

三个 zip 的 token **逐字节同值**：SHA256
`a637f357500c55a4f9cab1291e0b4fb3966b000bfa62805ab49b35c1c82e8fd1`
（内容 `gcJcbNA0szeY2QEn2H2idxvfutQkxlkx`）⇒ reviewer 指控成立。
**MiniMVP 两个 zip 均不含 token**：`…_rc3_perftest.zip`
（5 591 630 138 B / 10 474 / `dda6f229…2d45f1`）与
`…_rc3_perftest_rev2.zip`（5 591 630 139 B / 10 474 /
`90ae8b9d…a06f58f`）⇒ APP-077 原文要求「今天写进 STATUS」已落实。

**打包侧剔除**：`pkg_exclude.py` 新增 `BRIDGE_TOKEN_FILE_RE` +
`is_bridge_token_file()`，并在 **`is_excluded()` 与 `iter_package_files()`
两处独立拦**（🔴 后者不调用前者，只改一处会漏进包，已写进注释）；
`__all__` 同步。反证 5 组全 PASS（去掉规则 ⇒ token 会进包；规则改恒假 ⇒
拦截失效）。v2.2 源目录只读实测：进包清单 14 314 文件**不含** token，
排除清单 149 文件**含** token。
旧包**不原地改**：v2.0/v2.1/v2.2 目录与 zip 一个字节都没动。

**② 快捷方式**（`results/app/_app305_app077_shortcut_selftest.json`，
**27 PASS / 0 FAIL**）：新增 dev 侧
`live_caption/bridge_bootstrap.py`：运行时枚举
`Confucius4_LiveCaption_v*` / `MiniMVP_v*`，按语义版本倒序挑**同时具备**
`pythonw.exe` + `bridge_launcher.py` 的最新目录；`%LOCALAPPDATA%\LiveDubEXT\bridge.log`
（追加 + 5 MB×3 轮转）；`ctypes.MessageBoxW` 失败弹框；
`--token-file %LOCALAPPDATA%\LiveDubEXT\bridge_token.txt`（APP-077 ① 联动）。
另加稳定入口 `CMD_TEMPLATE` / `write_user_launcher()`：.lnk 只指向
**系统 cmd.exe** + 用户目录 `.cmd`（路径零版本号），cmd 用通配符
「借一个 pythonw」再交给 bootstrap 做语义版本选择。
反证 6 组全 PASS（写死版本路径 / 缺 launcher / 反转排序键 / 无 App 目录 /
去掉弹框 / cmd 注入版本路径）。
🔴 **本轮未生成任何桌面 .lnk**：EXT-042 ② 明文「不要动 App 生成的
v2.1 .lnk」，APP-055 禁止原地改用户正在测试的安装目录 ⇒ 改动落在 dev 树，
**待 v2.3 打包时接线生效**。EXT-043 B5 的运行时日志/弹框由 EXT 线程负责，
本启动器是 App 打包侧第二道兜底。

### 4. APP-078（reviewer 13:31 中途追加）— **本条已完成**（③ 待 v2.3 打包生效）

`results/app/_app306_app078_babelvox_audit.json`，**28 PASS / 0 FAIL**。

**① 实际位置与 SHA**（🔴 **目录 ≠ zip，混在一起会得出错误结论**）：

| 口径 | v2.0 | v2.1 | v2.2 |
|---|---|---|---|
| **安装目录** `python/Lib/site-packages/babelvox/data/speakers/` | **8 文件** | **8 文件** | **8 文件** |
| **交付 zip** 同源条目 | **0** | **0** | **0** |

8 个文件（`cindy/lou/phil/steve` 各 `.json` + `.npy`）；**三个目录同名文件
SHA 逐字节全同**，路径前缀均为
`python/Lib/site-packages/babelvox/data/speakers/`：

| 相对路径（前缀同上） | 字节 | SHA256 |
|---|---|---|
| `cindy.json` | 307 | `eebf32802121d2c87334845dcb1e8b470f02ac85fecd15839bf45ef4a78c7751` |
| `cindy.npy` | 4 224 | `a3bf1a752106f4279bec97da40a3d44ff9e3e41b2d4e304b20dd6cb88afbe382` |
| `lou.json` | 314 | `6901ef6e3429bfd00acb1dd3731b3f5a3955ba77bed094c9ed169691de034715` |
| `lou.npy` | 4 224 | `5e6a00d89a46a53e812e8b92ec0cd3a67522645223dc9a99db4aee19afea5536` |
| `phil.json` | 315 | `3144f96d028594de7db783c9c0e796d8b9fd50051a30e425f4f88f6ef1aefb5c` |
| `phil.npy` | 4 224 | `d913381ea0b8014a16cf167a969e1504fc414abf90479f09e170ea5643653ad9` |
| `steve.json` | 313 | `0110df5ac28eb5c60346ed9eb65f38a35b5476fdc19dbb5eb133243198d64986` |
| `steve.npy` | 4 224 | `07fac8aaf3a85c7cd7afbf3eadb721d60bf40d25eeed4459a986004e1cc82606` |

原始字段：`results/app/_app306_app078_babelvox_audit.json` 的
`dirs.{2.0,2.1,2.2}.files[].{rel,bytes,mtime,sha256}`；三目录一致性见
`dir_signature`。v2.0/v2.1/v2.2 **安装目录**各有这 8 个文件，
**交付 zip 各 0 个**（`zips.*`）。
zip 里 babelvox **库代码**仍在（v2.0/2.1/2.2 各 40 条、MiniMVP 15 条）
⇒ 没误删库。MiniMVP rev2 zip 不含示例音色、仍带 `preset_A.wav`。

**② 改正 APP-074 结论**：§139 写的「**v2.x 不违规**」**只对交付 zip 成立**，
**对已安装目录不成立**。reviewer 13:15 从 v2.2 **目录**启动 EXT 桥接看到
`SpeakerLibrary 就绪：…（4 个音色：cindy, lou, phil, steve）` ⇒ **实测成立**。
根因：`pack_v13.py` 用 `pkg_exclude.iter_package_files()` ⇒ zip 干净；
但 `app206_app057_v20_stage.py` / `app221_app061_v22_build.py` 的
`copy_tree()` 是 `os.walk` **整目录复制、完全不调用 pkg_exclude**
（AST/字符串实测 `applies_pkg_exclude_on_copy=False`）⇒ 目录残留。
`--tts-voice A` 的功能结论（来自 Amphion metis `preset_A.wav`，
不依赖这 4 个音色）**不变**。

**③ v2.3 起剔除 + SpeakerLibrary 兼容性**：
* 新增 `live_caption/assert_pkg_clean.py` —— **建包阶段**洁净度闸门，
  同时拦 `bridge_token.txt`（APP-077①）与 4 个示例音色（APP-078③）；
  **只检查不删除**，违规 ⇒ exit 1 拒绝交付。
  自检 `results/app/_app307_assert_pkg_clean_selftest.json`
  **14 PASS / 0 FAIL**：对 v2.0/2.1/2.2 三个真实旧包各判出
  「1 token + 8 音色」并拒绝交付（已知有缺陷的产物能识破 ⇒ 判据非恒真）；
  干净临时目录 0 违规、`preset_A.wav` / babelvox 库代码 / tokenizer 不误伤。
* 🔴 **SpeakerLibrary 无内置音色时正常工作（真运行时验证，非静态推断）**：
  用 v2.2 自带 python，把 `BUILTIN_SPEAKERS_DIR` 指到空目录 ⇒
  `builtin_speakers_available()` 返回 `[]`、
  `_SpeakerLibraryWithBuiltinFallback` 正常构造（`ok=true`）、
  `list_profiles()` 返回 0，rc=0 无异常。dev 与包内
  `tts_engine.py` 都含 `os.path.isdir(base)` 守卫与
  `copy_builtins=False`（只读、不复制）。
  ⚠️ 首跑 3+1 个 FAIL 全是**判据名字/断言写错**（凭记忆写成
  `builtin_speaker_available` / `_copy_builtin_speakers` /
  `_ReadOnlySpeakerLibrary` / 断言 `_builtin is None`），已按真实源码改正。
* 🔴 **v2.3 建包脚本必须调用** `python live_caption/assert_pkg_clean.py <新包目录>`，
  并在 `copy_tree` 阶段就不复制这两类文件（本轮**未打包**，未落进任何包）。

**④ 已发的包不原地改**：v2.0/v2.1/v2.2 目录与 zip 全部只读扫描，
一个字节都没动；受影响清单见上表，reviewer 会告知用户。

### 5. 纪律自检

* 未打包、未打 zip、未改任何客户包目录/zip（只读扫描）；
  未改桌面 .lnk；未动 `v23_clone/`（r2 是**新目录**）；
  未覆盖 `app250_device_out/`（app301 另存）。
* 未在 CPU 上跑推理/测速；设备作业（app301 第 1 臂）持
  `MACHINE_LOCK` + 安静窗口，进程被会话中断杀死后以
  ctypes `OpenProcess` err=87 确证死亡再回收孤儿锁。
* 未调用 MiniMax；未提交 `CORRECTIONS_APP.md`；逐文件 `git add`，
  不吞其它模块未提交改动；main 分支普通 push、不 force。
* 结论均引用结果文件 + 原始字段；产物均附文件数 / 字节 / SHA256。
  🔴 **本轮自检纠正了 2 处证据口径**：① r2 的「52 文件 / 20 160 623 B」
  是 manifest 写前口径，磁盘实际先 53 / 20 170 791，补齐 `submit.jsonl`
  并重签后 **54 / 20 175 499**（manifest 自记与磁盘一致）；
  ② 8 个 babelvox 示例音色原写省略号 SHA，现全部补全并给出原始字段路径。
* 🔴 **r2 补齐只发生在本轮新生成的 `v23_clone_r2/` 内**：
  未碰 `v23_clone/`、未碰任何客户包目录/zip、未打 zip、未改桌面 .lnk；
  `_app303` 修复后未重跑全量构建（避免覆盖已落盘的 46 个 wav 与 F0 表），
  由 `_app309` 单独补落盘并逐条复核旧产物 SHA 未变。
* **没落盘的东西不写「已交付」**：APP-075 的 F0 闸门未通过、
  真 x-vector 未产出、第 2 臂未跑、v2.3 未打包，全部如实标注。
