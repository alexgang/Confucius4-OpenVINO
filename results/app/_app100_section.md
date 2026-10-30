## §100 🔴🔴🔴 **APP-039/040「音色按句绑定」第二轮审计又查出 4 处断链（G/H/I/J）⇒ 已全部修复 ＋ 修掉 4 处「我自己写的验收判据缺陷」＋ 客户包 v1.11 已定点同步并持锁重打 zip（**但 zip 为半交付**，见 §100.7）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 09:37）

> ⚠️ **章节编号说明**：本轮有**两个 App 会话并行**（本会话 + APP-043/044 会话）
> ⇒ 本章节**只记本会话的产出**；APP-043/044 与 §100 断链 G 的**回归修复**记在 **§101**
> （§101.4 已认领该回归修复）⇒ **两章节互补、不重复**。

### 100.0 本轮起点与**中途口径变化**

- 🔴 **开工巡检（08:5x）**：`status/app/CORRECTIONS_APP.md` 最大编号 = **APP-042**
  = `STATUS_APP.md` 头部 `last_ack: APP-042` ⇒ **无新条目**（第 27 次同一口径复核）
  ⇒ 本轮按 §99 的口径，改为**对 APP-039/040 链路做第二轮逐条反查**。
- 🔴🔴🔴 **本轮中途 reviewer 追加了两条新纠偏**（本会话**全程只读**该文件，未改一个字节）：
  **APP-043**（08:48，ASR 说话人接口已交付 ＋ **App 进程须在 numpy/OpenVINO import 之前限线程**）
  ＋ **APP-044**（08:50，客户包**带上** pyannote/wespeaker 的 OV IR ＋ NOTICE 署名）。
  ⇒ 这两条由**并发会话**执行，见 **§101**；本会话**不抢、不重做、不吞**。
- 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（**reviewer 独占写入文件**）。

### 100.1 🔴🔴🔴 **第二轮审计查出 4 处断链（G/H/I/J）**

> 🔴 **发现方式**：与 §99 同法 —— 不跑既有回归（那必然全绿），而是**逐条对着 APP-039/040
> 的明文问「这条要求在真机上成立吗」**。4 处全部落在**离线验收覆盖不到**的边界上
> ⇒ 既有 `app150`/`app152`/`app154` 全绿**不能证明**链路闭合。

#### 断链 G：`spk=None` 时**什么都不做** ⇒ 用上一个人的声音冒充（串音）

- **现象**：旧 `synth()` 里 `if spk: self._apply_spk_voice(spk)` ⇒ **`else` 分支是空的**
  ⇒ `self.speaker_embed` / `self.speaker_name` **仍留着上一个人的音色**
  ⇒ 下一句**没有说话人标签**时，用的是**上一个人的声音**。
- **违反**：APP-040② 明文「**不能用上一个人的声音冒充新的人**」。
- **为何以前不显现**：旧「跟随说话人（克隆）」路线只在用户**显式勾选**时才换全局音色
  ⇒ 常态下 `speaker_embed` 就是预设 A ⇒ 不显现。
  ⚠️ **但 APP-039/040 的按句绑定把这件事变成了常态** ⇒ 必然串音。
- **首版修复**：`else: self._fallback_to_preset('no_spk_label')`。
  🔴🔴🔴 **首版有 BLOCKING 回归**（会打死 APP-027⑤ 的 `follow_speaker` 克隆功能）
  ⇒ **已由 §101.4 的模式感知版修掉** ⇒ **以 §101.4 为准**。

#### 断链 H：逐句 jsonl **缺「这句属于谁 / 实际用了谁的声音」** ⇒ reviewer 的混淆表算不出来

- **现象**：`_APP030_JSONL_KEYS` 里**没有** `voice_spk` / `voice_kind`。
- **违反**：APP-039 验收①明文要求「**每句实际用的音色和该句 spk 一致的比例**（报告混淆表）」。
  ⇒ 要算这个比例，**必须逐句**同时知道：① 这句**属于谁** ② 这句**实际用了谁的声音**
  ⇒ 旧实现**两个都没有** ⇒ reviewer 拿到 jsonl **无法算混淆表** ⇒ **验收①客观做不了**。
- **修复**：新增两个字段；**成功行与失败/丢句行都要带**（否则 reviewer 算分母时**只算成功句** ⇒ 对比失真）
  ⇒ 且 `_fallback_to_preset()` 内**同步复位**这两个字段（否则 jsonl 会写 `voice_kind='clone'`
  而实际用的是预设 A ⇒ **矛盾字段** ⇒ 混淆表失真）。

#### 断链 I：**CLI 路径完全没有说话人标签**（GUI 有、CLI 无）

- **现象**：GUI 侧有 `self._spk_by_seg`；**CLI 侧完全没有** ⇒ APP-040④
  「原文字幕和译文字幕每句前面都显示说话人标签」**在 CLI 路径上从未实现**
  ⇒ **两条路径口径不一致**。
- **修复**：CLI 增加 `_spk_by_seg`；原文 `--out` 与译文 `.mt.txt` 都加 `[S1/S2]` 前缀；
  渲染层 `render_lines(..., spk_by_seg=_spk_by_seg)` 透传。
  ⚠️ **只加前缀、不改文本本身** ⇒「原文守恒」不变式仍成立。

#### 断链 J：ASR 侧 `on_spk_update` **没有任何调用方** ⇒ 「补标签」客观做不了

- **现象**：ASR 侧 `on_final()` 在旁路分段没覆盖到该段时返 `spk=None` + `pending=True`，
  文档说「标签随后由 `on_spk_update` 补发」⇒ **但 `on_spk_update` 没有调用方**
  ⇒ `pending=True` 的段**标签永远不到** ⇒ APP-040④「spk 晚到时补标签」**客观做不了**。
- **修复（不代改 ASR）**：ASR 侧判定依赖 `_seg_frames`，而它**随 `feed()` 推进**
  ⇒ **过一段时间再问一次同一个 seg** 就能拿到标签。
  ⇒ App 侧新增 `SpeakerBridge.retry_pending(max_n=8)`（拿到标签后 `_pending.discard(seg)` 出队）
  ⇒ GUI 侧 `App._retry_spk_labels()` 挂 `_poll()`；CLI 侧 `_cli_retry_spk_labels()` 挂主循环与收尾。
  ⚠️ **不阻塞**（守 APP-034 方案 A：字幕/翻译/语音**不为**说话人识别增加延迟）。

### 100.2 ✅ §100 的验收脚本 `app155`（**36/36 PASS**，含 6 条反证 + 4 条固定基线）

- 脚本：`results/app/app155_app039_second_audit_test.py`（本轮新建）
- 结构：**REAL 19 + 行为 7 + 反证 6 + 固定基线 4** ⇒ 合计 **36 PASS / 0 FAIL**
- 🔴 **反证基线用固定 commit `b741240`**（§100 之前的 HEAD）⇒ **不用 HEAD**
  （否则修复后 HEAD 就是修复版 ⇒ 反证永远落空 ⇒ 失去证据价值）。
- 🔴 **过程中修掉 4 处「我自己写的判据缺陷」**（判据不恒真才算数）：
  ① `REPO` 路径算错（剥两层不够，脚本在 `results/app/` 下 ⇒ 要三层）；
  ② 反证注入的缩进与源码实际缩进不符（16 vs 12 空格）⇒ `replace` 静默不生效；
  ③ 反证正则命中了 `on_final()` 方法体内那处，而非 `retry_pending` 体内那处；
  ④ 🔴🔴🔴 **判据用字符串包含判「是否调用 `on_final`」⇒ 命中了 docstring**
  ⇒ 判据恒真 ⇒ 改为 **AST `ast.Call` 节点**检测（`discard` 同理）后才真正打掉反证。
- 🔴 **另修一处「反证读盘绕过注入」**：`check_J` 内部对 `live_caption_app.py` **独立从磁盘读**
  ⇒ 即使传入被注入的 `src_text`，App 侧判据仍读原文件 ⇒ 反证永远打不掉 ⇒ 假通过
  ⇒ 给 `check_J` 增加 `app_text` 参数。

### 100.3 🔴 **「包内那份」也必须过同一套判据**（铁律 §九：包里代码对 ≠ 已交付）

- 🔴 **本轮给 `app155` 加了 `APP155_LIVE_DIR` 覆盖** ⇒ 可对**客户包内源码**跑同一套 36 条。
- 结果：**仓库版 36/36 PASS**；**包内 v1.11 版 36/36 PASS**
  （证据另存 `app155_app039_second_audit_evidence_pkg.json` ⇒ 两轮证据互不覆盖、可比对）。

### 100.4 ✅ 客户包定点同步（§100 的 3 个文件）

- 脚本：`live_caption/sync_c162_to_pkg.py`（新建）⇒ 复用 §99 的 `difflib` 派生替换块机制
  （**OLD 取自「包内实际内容」**、两端**归一化 LF**、每块**唯一命中断言**、
  写盘前 `compile()`、写盘后**逐字节**断言）。
- ⚠️ **同步前先核对差异纯度**：包内与仓库的差异**全部**是 §100 的改动，**不夹带历史差异**。
- 结果：`tts_worker.py` repl=6、`speaker_tracker.py` repl=1、`live_caption_app.py` repl=11
  ⇒ 三文件 `match_repo=True`（归一化 LF 后与仓库**逐字节**一致）。
- 🔴 **备份放包外**：`C:\Users\Trekker-PTL\bak_c162_20261030_090304\`
  （⚠️ **不能放包内** ⇒ 会被打进 zip）。
- 🔴🔴 **踩坑并修掉一处「验收脚本自身的判据缺陷」**：`app142` 的包目录自动发现用
  `_v(\d+(?:\.\d+)+)`（**不锚定结尾**）⇒ 我的备份目录名 `Confucius4_LiveCaption_v1.10_bak_c162_…`
  被**误判为「v1.10」** ⇒ 脚本**选中备份目录** ⇒ 全部判据 `FileNotFoundError`（假 FAIL，掩盖真实结果）
  ⇒ 已把正则改为 `_v(\d+(?:\.\d+)+)$`（**版本号必须结尾**）⇒ 修正后 **22/22 PASS**。

### 100.5 ✅ 回归套件复跑（全部 PASS）

| 脚本 | 结果 | 说明 |
|---|---|---|
| `app155_app039_second_audit_test.py` | **36 / 0** | §100 新建（反证全命中 + 基线 4 条全 FAIL）|
| `app155`（`APP155_LIVE_DIR` → 包内 v1.11） | **36 / 0** | 同一套判据跑包内源码 |
| `app142_app042_pkg_check.py` | **22 / 0** | ⚠️ 同步**前**是 20/2（包未同步）⇒ **同步后闭环** |
| `app150_app039_spk_bound_voice` | 17 / 0 | |
| `app152_app151_cli_closure_scope` | 7 / 0 | |
| `app154_app039_wiring_gap_test` | 20 / 0 | |
| `app139_app041_startup_tts` | PASS | |
| `app140_app042_wsola` | PASS | |
| `app141_app042_integration` | 62 / 0 | |
| `app145_app042_cli_target_wall` | PASS | |
- 🔴 **一处「解释器差异」不是代码缺陷**（铁律 §六）：
  用 WorkBuddy 内置 Python **3.13.14** 跑 `app142` ⇒ `ModuleNotFoundError: numpy`
  ⇒ **managed 解释器无 numpy** ⇒ 换项目 `.venv`（**3.12.10 / numpy 2.4.6**）即 **22/22 PASS**
  ⇒ **不是产品缺陷**。

### 100.6 ✅ 客户包 **v1.11 持锁重打 zip**（产物证据）

- **打包命令**：`python pack_v13.py --version 1.11`（system Python **3.12**）
- **机器锁**：`shared/MACHINE_LOCK` 内容 `module: app-pack` / `pid: 10540` /
  `started: 2026-10-30 09:07:13` ⇒ **持锁**打包
  ⇒ ⚠️ **取锁前实测机器上有 4 个外部 python 进程**（**用户正在实跑的 v1.5 客户端**：
  `pythonw.exe ... v1.5\app\live_caption_app.py` PID 30208、
  `tts_worker.py --voice follow_speaker` PID 7480、两个 `tts_cuda_sidecar.py`）
  ⇒ 安静窗口连续被打破 ⇒ **等 465 s** 后「外部 python 均在等锁/在睡」
  ⇒ **安静窗口持续 45 s** ⇒ 才开始打包。
  ⇒ ✅ **没有 `--skip-quiet`**、**没有抢锁**、**没有杀任何进程**。
- **版本号三处一致** ✅：目录 `Confucius4_LiveCaption_v1.11` == zip `Confucius4_LiveCaption_v1.11.zip`
  == MANIFEST `version='1.11'`（`files=14202`）
- **zip 产物**：**11,218,213,281 字节** / mtime **2026-10-30 09:26:11** /
  SHA256 **`72068c32c19ff4166f0875888bbc018d0fff9e3565c51d2a0f83c715b1217a20`** /
  打包脚本自报 **md5 `37a74f36f3f4599b50e2555e5d19a242`**（结论 **PASS**）
- **独立只读复核**（`results/app/app156_app100_zip_verify.py`，本轮新写）：
  **4 PASS / 4 FAIL** ⇒ verdict **FAIL**（**这正是「半交付」的证据，不是脚本失败**）
  ⇒ 原始字段：`zip_sha256=72068c32…17a20` / `zip_bytes=11218213281` /
  `n_entries=14203` / `py_same=6589` / `py_diff=3` /
  `py_diffs=['app/live_caption_app.py', 'app/speaker_tracker.py', 'app/tts_worker.py']` /
  `manifest_version='1.11'` / `manifest_files=14202` / `testzip=None`（无 CRC 错误）。
- **zip 条目数**：**14,203**；打包脚本自带「zip ⇄ 包目录 逐文件 SHA256」
  ⇒ **比对 14,203 个文件全部逐字节一致** ⇒ **已原子改名到正式路径**（**无 `.tmp` 残留**）
- **锁已释放**：打包结束实测 `shared/MACHINE_LOCK` **不存在** ⇒ ✅ **无孤儿锁**

### 100.7 🔴🔴🔴 **「半交付」判定（zip 层面不成立，必须如实记录）**

- 本轮 zip 打成于 **09:26**；而**并发会话**在 **09:32** 才把 APP-044 的
  `speaker_assets.py` 同步进包目录 ⇒ **zip 内**实测（`app156_app100_zip_verify.py`）：
  | 文件 | zip 内 | 包目录内 | 判定 |
  |---|---|---|---|
  | `live_caption_app.py` | `5936e85a4774` | `e5440190eadc` | ❌ DIFF |
  | `tts_worker.py` | `3ecfbc94f9c2` | `73c756420fd1c1ee` | ❌ DIFF |
  | `speaker_tracker.py` | `0b8b082b6723` | `4b03f19fbaf127e8` | ❌ DIFF |
  | `speaker_assets.py` | **不存在** | 10 336 B | ❌ **NOT IN ZIP** |
  ⇒ ⇒ **zip 内不含 §101 的回归修复，也不含 APP-044 的包内资产**
  ⇒ ⇒ **「已交付」在 zip 层面不成立**（只成立于**包目录**层面）。
- 🔴 **需重打 zip**：但 **09:33:28 起 `EXT-p1-real` 持有活锁**
  （PID 41788；本会话用 ctypes `OpenProcess` 判定 **alive, exit code 259 = STILL_ACTIVE**）
  ⇒ **本轮不抢锁** ⇒ **本轮不重打** ⇒ **不写「已交付」**。
- 🔴 **另外发现并修掉一处「复核脚本自身的缺陷」**：`app156` 的 V4 判据把磁盘路径写成
  `os.path.join(PKG, t)`（**少一层 `app/`**）⇒ **FileNotFoundError 崩溃**
  ⇒ 复核脚本自己先挂 ⇒ **拿不到「差异」这个关键结论** ⇒ 已修正为 `os.path.join(PKG, 'app', t)`
  并加容错（文件缺失只判 FAIL，不崩）。

### 100.8 🔴 **本条需等 reviewer 复核**（本会话相关部分）

1. 🔴 **reviewer 的 MiniMax 回转写错误率对比**（APP-042 明文要求，**本模块不得自做**）。
2. 🔴 **用户实听 3 段 1.2–1.3× 配音**（3 段 wav 已落盘 `results/app/app042_soak_run4/clips_1p2_to_1p3/`，
   但 `.gitignore` 忽略 `*.wav` ⇒ 不入库）。
3. 🔴 **APP-039/040 真机 NPU 双说话人音色按句切换**（本轮仅离线 `app150`/`app155`/`app157` 覆盖）。
4. 🔴 **APP-041 桌面快捷方式 → `pythonw.exe` 冷启动真机验收**。
5. 🔴 **GUI 路径的 APP-042 加速播放真机实测**（§96–§99 走的都是 CLI 回放路径）。
6. 🔴 **zip 半交付的处置**：需在拿到锁后重打 ⇒ **本轮不抢 `EXT-p1-real` 的活锁**。
7. 🔴 **§100 的 4 处断链修复在真机上的效果**（尤其断链 G 的串音是否真的消除）。

### 100.9 🔴 **口径变更声明**

- 🔴 **撤回**任何「v1.11 已交付（zip 层面）」的表述 ⇒ 当前口径 =
  **「包目录层面已同步并核验；zip 层面为半交付，待重打」**。
- ⚠️ **§100 断链 G 的首版修复（无条件回落预设 A）已被 §101.4 的模式感知版取代**
  ⇒ **以 §101.4 为准**。
