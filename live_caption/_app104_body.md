## §104 🔴🔴🔳 **开工即查出「§103 声称已入库、实际未入库」的半交付 ⇒ 已补交入库；zip 仍半交付（锁被 TTS 持有）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 10:52）
### 104.1 🔴 **巡检：44 条 APP 编号 = `last_ack: APP-044` ⇒ 无新纠偏条目（第 30 次同一口径）**

- 🔴 **只读复核** `status/app/CORRECTIONS_APP.md`：
  SHA256 `08e231a24c22b567bdf5be09a46896128fa4b2aa5d2d32ed32fa029a501361a6` /
  **111 198 B** / mtime `2026-10-30 08:50:04` ⇒ `## APP-xxx` **44 条**（APP-001…APP-044）。
- ✅ **`last_ack` = APP-044** = 最大编号 ⇒ **无新纠偏条目** ⇒ `last_ack` **保持 APP-044**。
- ✅ **该文件本轮只读零改动**（末次复核 SHA256 逐位一致）；`git status` 仍显示 ` M`（reviewer 自己的未提交改动）⇒ **保持未暂存、未入库**。

### 104.2 🔴🔴🔴 **开工自查查出「上轮 §103 的半交付」：4 个证据文件「STATUS 里写了、实际没入库」**

- 🔴🔴🔴 **§103.4 的表述**：「✅ **本轮新产物（均已入库）**」并列出 4 个产物
  ⇒ 结论「✅ **4 产物已入库**（`27d5b41` → `f13fd89`，均已普通 push）」。
- 🔴 **实测（`git ls-files` + `git status --porcelain` 逐个核）**：

  | 文件 | §103/§97/§101 的表述 | 实测 | 处置 |
  |---|---|---|---|
  | `results/app/app160_app102_zip_evidence_v1.11.json` | §103.4「4 产物已入库」 | ❌ **未入库**（`git ls-files` 空 ⇒ `??`） | ✅ **本轮补交** |
  | `results/app/app149_app042_worker_side_speed_evidence.json` | §97.2.2「证据 …」 | ❌ **未入库** | ✅ **本轮补交** |
  | `results/app/app157_app043_thread_env_gate_evidence_pkg.json` | §101.5「对包内源码 14 PASS」 | ❌ **未入库** | ✅ **本轮补交** |
  | `results/app/app157_follow_speaker_regression_evidence_pkg.json` | §101.5「对包内源码 11 PASS」 | ❌ **未入库** | ✅ **本轮补交** |

- 🔴 **根因**：§103 的两次 commit（`27d5b41` 只含 `app160_app102_zip_verify.py`、
  `f13fd89` 只含同 1 个文件）**只提交了脚本、没提交配套证据 JSON**；
  而 §103.4 的「均已入库」结论是**照抄 §102/§101 的口径**、**没有逐个核 `git ls-files`**
  ⇒ **「做出来了、STATUS 里写了、但没入库」的半交付**（记忆 §九「半交付三层」之外的**第四层**：
  **产物本身没进仓库** ⇒ 换台机器复现不了）。
- ✅ **证据内容复核（`node` 只读解析，避免干扰持锁中的 TTS 计时作业）**：
  - `app160_app102_zip_evidence_v1.11.json` ⇒ `pass=4` / `fail=10` / `verdict=FAIL`
    （= v1.11 缺陷版干跑 ⇒ **判据不恒真的证明**，内容与 §103.2 表格一致）；
  - `app149_app042_worker_side_speed_evidence.json` ⇒ `schema=app.app042.worker_side_speed.v2`
    （`n_sent_old=76` / `n_sent_new=76` / `old_submit_time.n_always_1=76` /
    `new_dequeue_time.measured_n_in_1p2_1p3=75` / `injected_falsify.behavior_judgment_failed=true`）；
  - `app157_app043_thread_env_gate_evidence_pkg.json` ⇒ `pass_=14` / `fail=0` / `verdict=PASS`；
  - `app157_follow_speaker_regression_evidence_pkg.json` ⇒ `pass_=11` / `fail=0` / `verdict=PASS`。
- ✅ **处置**：**逐文件 `git add`（未用 `-A`）** ⇒ commit `c82f7e9`（**4 files / +390 行**）
  ⇒ `git diff --cached --name-only | grep -c CORRECTIONS` = **0**
  （**未提交 reviewer 独占文件**）；其它模块 **519 项**未提交改动**全部保留在工作区、未吞**。

### 104.3 🔴🔴 **另外 2 个「已入库」产物被复跑覆盖 ⇒ 记录的 SHA256 与现文件不一致（已定位，未擅自改动）**

| 文件 | §101/§99 记录的指纹 | 现文件指纹 | 差异性质 |
|---|---|---|---|
| `results/app/app158_app043_bridge_wiring_evidence_pkg.json` | 1 987 B / `51a2dd3e86a9e0af…` | **1 983 B** / `baff1de277db623e` / 09:50:20 | **临时目录名 + `live` 路径写法**变了（`C:\...\Temp\app158_bridge_js7xl6yz` → `..._14u4iq_v`；`C:\Users\...` → `C:/Users/...`）⇒ **仅路径字符串**，判据 `pass_=9 / fail=0 / verdict=PASS` **未变** |
| `results/app/app154_app039_wiring_gap_evidence.json` | （未记 SHA） | 5 381 B / `82d783cc1c00cd02` / 09:36:25 | **行号漂移**（`_pump_spk_voices@3794` → `@3829`、`@4694` → `@4783`）⇒ `pass=20 / fail=0 / total=20` **未变** |

- 🔴 **处置**：这两个文件**是「复跑同一套验收脚本」的自然产物**（时间戳/临时路径随运行变）
  ⇒ **内容等价**、**结论等价**（PASS 数与 verdict 未变）⇒ **不是回归**。
- ⛔ **本轮未提交它们**（属并发会话的复跑产物，**归属未判定** ⇒ 按纪律「不吞别人的未提交改动」不动）
  ⇒ **提请 reviewer 裁定**：是否把它们作为「复跑产物」统一入库，或在验收脚本里**固定临时目录名**让证据可复现。

### 104.4 🔴🔴🔴 **「半交付」判据本轮扩展为四层（§103.3 的三层 + 本轮新增一层）**

| 层 | 现象 | 查出它的手段 |
|---|---|---|
| ① zip 旧 | 包目录对，但 zip 没重打 | `app156` / `app160` |
| ② 包目录内容不合规 | 包里有内部素材（§102 查出）| `pack_v13.py --dry-run` 触发内部素材闸门 |
| ③ 包目录代码 ≠ 仓库 | 两份独立副本漂移 | 归一化行尾后逐字节 SHA256 对比 |
| ④ 🆕 **产物本身没进仓库** | STATUS 写了「已入库」，实际 `git ls-files` 为空 | **逐个 `git ls-files` + `git status --porcelain` 核** |

⇒ 🔴 **教训（§103.4 的教训）**：**「已入库」不能靠 commit message 自述** ⇒ 必须**逐文件核 `git ls-files`**。
⇒ 🔴 **「N 个产物已入库」这种整体表述最容易漏** ⇒ 以后写成**逐文件表格**（本节 §104.2 即为范例）。

### 104.5 ✅ **「半交付」第 ③ 层（包目录代码 ≠ 仓库）本轮实测：已闭合**

- 🔴 **逐文件归一化行尾后 SHA256（前 16 位）对照**（仓库 `live_caption/` ⇄ 包 `Confucius4_LiveCaption_v1.12/app/`）：

  | 文件 | 仓库 | 包目录 | 结论 |
  |---|---|---|---|
  | `tts_worker.py` | `73c756420fd1c1ee` | `73c756420fd1c1ee` | ✅ MATCH |
  | `tts_service.py` | `4b34e8015d6ad538` | `4b34e8015d6ad538` | ✅ MATCH |
  | `live_caption_app.py` | `e5440190eadcef1f` | `e5440190eadcef1f` | ✅ MATCH |
  | `translator.py` | `c5ab5e0760e2ea88` | `c5ab5e0760e2ea88` | ✅ MATCH |
  | `speaker_tracker.py` | `4b03f19fbaf127e8` | `4b03f19fbaf127e8` | ✅ MATCH |
  | `speaker_voice.py` | `42a7aaeedc944916` | `42a7aaeedc944916` | ✅ MATCH |
  | `caption_render.py` | `be9e1d43918424c3` | `be9e1d43918424c3` | ✅ MATCH |
  | `tts_cuda.py` | `884d90d26838dcf3` | `884d90d26838dcf3` | ✅ MATCH |
  | `tts_cuda_sidecar.py` | `269d02f319906a6c` | `269d02f319906a6c` | ✅ MATCH |

- 🔴 **注意原始字节不相等**（如 `tts_worker.py` 220 854 B vs 216 896 B）⇒ **纯 CRLF/LF 差异**
  ⇒ **必须归一化行尾后再比**（否则误判成「包内是旧版」）。
- ✅ **`git show HEAD:live_caption/<f>` ⇄ 包目录**：9/9 全部 MATCH ⇒ **包目录 = 仓库 HEAD**。
- ✅ **§101 的模式感知回落修复在源码里确认在位**（`tts_worker.py` L1685-1694）：
  `_bound = bool(self._spk_voices)` → `if self.clone_mode and not _bound:` ⇒ 保留克隆音色；
  `else:` ⇒ `_fallback_to_preset('no_spk_label')` ⇒ **符合记忆 §五「音色回落必须模式感知」铁律**。

### 104.6 🔴 **锁仍被 TTS 持有 ⇒ zip 仍半交付 ⇒ 本轮不写「已交付」**

- 🔴 **实测锁内容**：`module: tts` / `pid: 28892` / `started: 2026-10-30 10:25:39` / `host: LAPTOP-0GDQGD3I`
  ⇒ ctypes `OpenProcess`(SYNCHRONIZE) + `GetExitCodeProcess` 实测 **exit code = 259（STILL_ACTIVE）**
  ⇒ **TTS 正在持锁做计时作业** ⇒ **本模块不抢锁、不杀进程**（铁律：别人活只能等）。
- ✅ **重打 v1.12 的作业已在排队**（不是本轮新起的）：
  `pack_v13.py --version 1.12 --lock-timeout 7200 --quiet-seconds 45 --quiet-timeout 1800`
  ⇒ PID **23320**（venv 启动器）/ **37168**（真解释器 `Python312`），启动于 **10:26:35**
  ⇒ ctypes 实测**两个进程都 alive（exit 259）** ⇒ **仍在等锁**（`machine_lock_app.acquire()`
  的「先探测、后创建」实现 ⇒ **等锁期间 0 次文件创建/删除**）。
- 🔴 **打包口径**：**必须显式 `--version 1.12`**（`discover_max_version()` = **1.12**
  ⇒ 默认 `bump_version()` 会推到 **1.13** ⇒ 白建一个目录）。
- 🔴 **锁一释放后待做（本轮未做）**：
  1. 等 `pack_v13.py --version 1.12` 跑完（原子写：写 `ZIP.tmp` → 校验 → `os.replace`）；
  2. `results/app/app160_app102_zip_verify.py 1.12` 跑到 **0 FAIL**；
  3. 记录 zip 的 **文件数 / mtime / 字节数 / SHA256 / `testzip()` / MANIFEST `version`+`files`**，
     并确认「目录版本 == zip 版本 == MANIFEST version」三者一致；
  4. 才可在 STATUS 写「已交付」。
- ⚠️ **本轮观察**：§103.5 记的等锁守候器（`/tmp/app102_lockwait.py`）**本轮已不在进程表**
  ⇒ 本轮**未另起守候器**（避免「取得锁就退出 = 白拿白放」的老坑，记忆 §二）
  ⇒ **由打包作业自己等锁**（`pack_v13.py` 内置 `LockHeld(timeout=)`）。

### 104.7 ✅ **本轮产物（已入库）**

| 产物 | 文件数 | 字节 | SHA256(16) | 说明 |
|---|---|---|---|---|
| `results/app/app160_app102_zip_evidence_v1.11.json` | 1 | 3 054 | `78221a91608b4d95` | §103 的 v1.11 干跑证据（判据自检）|
| `results/app/app149_app042_worker_side_speed_evidence.json` | 1 | 3 437 | `6d41bedc4e13bd20` | §97.2.2 的 APP-042 定速证据 v2 |
| `results/app/app157_app043_thread_env_gate_evidence_pkg.json` | 1 | 2 810 | `9fcccd282550087c` | §101.5 对包内源码 14/14 |
| `results/app/app157_follow_speaker_regression_evidence_pkg.json` | 1 | 2 497 | `231872acce272b1a` | §101.5 对包内源码 11/11 |

⇒ commit **`c82f7e9`**（**4 files / +390 行 / −0**）⇒ **普通快进** push（未 force）。

### 104.8 🔴 **本轮只记录、不改动的 App 职责内遗留（等 reviewer 裁定）**

1. 🔴 **6 个未跟踪的定点同步脚本**（`live_caption/sync_c148b_to_pkg.py` / `sync_c150_to_pkg.py` /
   `sync_c158_to_pkg.py` / `sync_c111_v20_to_pkg.py` / `sync_c111_v3_to_pkg.py` /
   `sync_c111_v3_revert_to_pkg.py`）—— 实测**每一个都有已入库的「后继版本」覆盖同样职责**：

   | 未跟踪 | 已入库的后继 | 覆盖文件 |
   |---|---|---|
   | `sync_c148b_to_pkg.py` | `sync_s48b_to_pkg.py` | `tts_cuda.py` + `tts_cuda_sidecar.py` |
   | `sync_c150_to_pkg.py` | `sync_c156_to_pkg.py` | `caption_render.py` + `live_caption_app.py` |
   | `sync_c158_to_pkg.py` | `sync_c162_to_pkg.py` | `tts_worker.py` + `speaker_tracker.py` + `live_caption_app.py` |
   | `sync_c111_v20/v3(_revert)_to_pkg.py` | （MT 管辖的 `translator.py` 同步）| 🔴 **MT  territory ⇒ App 不提交** |

   ⇒ 属**历史遗留在制品**，**功能已被后继脚本覆盖** ⇒ **本轮不提交**（避免入库两份同职责脚本）。
2. 🔴 **`results/app/` 下另有 124 个未跟踪历史产物**（`app007_*` / `app009_*` / `app023_*` 等）
   ⇒ 与 §57 遗留一致（**归属未判定**）⇒ **本轮不动**。
3. 🔴 **FTP**：`FTP_Share/` 里仍是 v1.4（11 216 051 100 B / 07:47）与 v1.5（11 216 287 107 B / 10:34）
   ⇒ 守 **APP-035**（用户已永久关闭 FTP）⇒ **本轮未运行 `publish_ftp.py`、未开 FTP 服务**。

### 104.9 🔴 **reviewer 复核清单（本轮增量）**

1. 🔴 **§104.2 的补交**：4 个证据文件本轮已入库（`c82f7e9`）⇒ 请确认「补交」处置正确
   （尤其 `app149_app042_worker_side_speed_evidence.json` 的 3 437 B 与 §97.2.2 记录的 **2 104 B**
   **不是同一份** ⇒ §97.2.2 记录的是 **v1（PASS=8/8）**、本文件是 **v2（PASS=11/11）**，
   §97.3 之后被 v2 覆盖 ⇒ **两版口径请以 v2 为准**）。
2. 🔴 **§104.3 的 2 个复跑产物**：是否入库？（或是否应在验收脚本里固定临时目录名以让证据可复现？）
3. 🔴 **§104.4 的第四层判据**：「产物本身没进仓库」是否需纳入常设巡检项？
4. 🔴 **§104.8① 的 6 个遗留脚本**：确认「已被后继脚本覆盖 ⇒ 不入库」的口径。
5. 🔴 **§104.6 的 zip 交付**：等 TTS 释放锁后重打 v1.12 ⇒ 完成后才可写「已交付」。

### 104.10 ✅ **本轮纪律自检**

- ⚠️ **未在 CPU 上跑推理或测速**；本轮全部核查走**只读**手段（`node` 解析 JSON ＋ `git` ＋ `grep`）
  ⇒ **未启动任何 `python.exe`**（避免污染持锁中的 TTS 计时作业的安静窗口）。
- ⚠️ **未碰 `shared/MACHINE_LOCK`**（锁由 TTS 持有 ⇒ 本轮无计时作业 ⇒ 不创建、不删除、不回收）。
- ⚠️ **未调 MiniMax**（质量判定交 reviewer）。
- ⚠️ **未修改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占文件，只读；SHA256 末次复核逐位一致）。
- ⚠️ **未吞其它模块的未提交改动**（逐文件 `git add`，**不用 `-A`**；ASR/MT/TTS 的 `c0xx_*.py` /
  `diag_c111_*` / `sync_c111_*` / `reports/` 一律不动 ⇒ 工作区仍 **519 项**）。
- ⚠️ **未提交 `status/app/CORRECTIONS_APP.md`** ⇒ `git diff --cached --name-only | grep -c CORRECTIONS` = **0**。
- ⚠️ **未运行 `verify_pkg_zip.py`、未运行 `publish_ftp.py`、未启动任何 FTP 服务**（守 §66 / APP-035）。
- ⚠️ **仓库只保留 `main` 分支**（`git branch -a` = `main` + `remotes/origin/main`）；**普通 push**，**未 force push**。
