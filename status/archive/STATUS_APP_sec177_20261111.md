## §177 执行 APP-100（last_ack=APP-100）｜canonical 10 分钟片段两臂**都自然退出**（A 951.9 s／B 1759.1 s，**PASS**）＋ 查出并修掉 **1 个 App 侧真缺陷**（`late_drop` 双记 ＋ drain 永不退出）｜**本条需等 reviewer 复核**

> 🔴 **归档件 = write-once**：本文件落盘后**逐字节不再改**；活文档 `status/app/STATUS_APP.md`
> 只保留 ≤3 行索引（APP-052 ④）。任何更正都写进**新章节**，不改本文件。

---

### 一、本轮基线（纠偏文件**只读**，全程未改未提交）

| 项 | 值 | 取法 |
|---|---|---|
| `CORRECTIONS_APP.md` SHA256（开工＝收尾） | `219ef841fc2c11a56fe8117774633c86d4ef8110e1e089b27e5d5608de9ce199` | `hashlib.sha256` 全文件 |
| 字节数 / mtime | 308 340 B ／ 2026-11-11 10:38:52 | `getsize` / `getmtime` |
| `## APP-xxx` 条数 / 最大编号 | **100 条** ／ **APP-100** | 正则 `^## (APP-\d+)` |
| STATUS 头部 `last_ack`（开工） | **APP-099** | `status/app/STATUS_APP.md` 第 3 行 |
| ⇒ 本轮新条目 | **APP-100**（唯一，编号 > last_ack） | 100 条 − 最大 APP-100 |
| 其它通道 | 全空：`shared/NOTICE*` 最新仍 11-05／agent-mail **`not_bound`**（面板虽显示 connected）／`conversation_search` 命中 0／git ahead=0·behind=0／`claude-clone` 相对 main **0 个新提交** | — |

🔴 **纠偏文件全程只读**：开工＝收尾**逐字一致** ⇒ **SHA 零改动**（未改、未提交）。
🔴 **接管说明**：本轮开工时发现**上一会话在 B 臂 TTS drain 阶段死亡**（租约 `94473c5e` 心跳超时 65 min，
`TAKEOVER`；其 3 个登记 PID 用 `ctypes OpenProcess` 探得 **err=87 ⇒ 确定已死**）⇒ **从断点继续**，未从头重做。

---

### 二、APP-100 原文与 App 侧落点

`status/app/CORRECTIONS_APP.md` → **APP-100 [FYI] 2026-11-11 10:38**：

> 「以后凡是要求"全长 / 61 分钟 / SPE 全集"的 WER/CER 或 RTF 长跑，一律改用**同一段固定的 10 分钟片段**。」
> 「片段起止秒写进脚本和结果 json，**所有臂、所有版本都用这同一段，保证可比**。建议取 SPE 的 0–600 s。」
> 「配对 bootstrap 照做（按句或按段配对）。结果里注明"10 分钟片段口径"，**不要和旧的 61 分钟数字直接放在一起比**。」
> 「**已下发、还没做完的纠偏（例如 ASR-053 第 3 项、APP-099）里的长跑，也按本条执行**。」
> 「本条不改任何默认值，也不改判据阈值本身，只改素材长度。」

⇒ App 侧落点 = **APP-099 §4.2 的 A 机 GPU 同占两臂**（`results/app/_app437_app099_device_jobs.py`）。

---

### 三、canonical 片段（唯一事实来源）

`results/app/_app455_app100_segment.py`（9 925 B／SHA256 `141fc1ab92f56c71…`）：

| 项 | 值 | 取法 |
|---|---|---|
| 源 | `test_audio/260902_SPE_audio.wav`（3671.189 s／16 kHz／mono／117 478 136 B） | 常量 `SOURCE_WAV` |
| 片段边界 | **0.0 – 600.0 s**（起点**不顺延**） | `START_S` / `END_S` |
| 起点依据 | 首 10 s 窗 rms=0.035654／peak=0.351379 ⇒ 开头即语音 ⇒ 不顺延 | ASR-054 `asr137_make_10min_clip.py` |
| 产物 | `test_audio/clip_10min_0_600.wav`（19 200 044 B／SHA256 `d412f00af6b792ce…`） | `getsize` / `sha256` |
| **payload** SHA256（语义契约） | `2f02e4c0b172bd952e5ba20018eeaeeb91673c0e778fa85c4a6305edf62fd54e` | 只哈希 PCM payload（不含 44 B 头） |
| **跨模块同段** | 与 ASR 侧 canonical clip **逐字节相同** | `qwen3asr_06b/dev/asr044_evalset/clip_10min_0_600.wav` 同 SHA |

🔴 **§175 的「本机只有 300 s」前提经实测证伪**（全长源一直在本仓库 `test_audio/` 里）
⇒ 旧口径「0–300 s `--loop` ×2」**违反 APP-100「所有臂都用这同一段」** ⇒ 本轮改 canonical 0–600 s **连续**。

---

### 四、🔴 缺陷①：`late_drop` **双记** ＋ **drain 永不退出**（App 侧真缺陷，已修）

#### 4.1 现象（设备实测，两臂都复现）

| 臂 | 日志原文 | 推算 |
|---|---|---|
| A `gpu_same_asr_mt` | `drain 超时：仍有 66 句未完成`；`最终统计（close 后）：提交 159 播完 93 丢弃 132 关闭作废 66` | `93 + 132 = 225 ≠ 159` ⇒ **多 66 句** |
| B `gpu_control_asr_npu` | `drain 超时：仍有 152 句未完成`；`最终统计：提交 162 播完 10 丢弃 304 关闭作废 152` | `10 + 304 = 314 ≠ 162` ⇒ **多 152 句** |
| 逐句 jsonl 实测 | A：`late_drop` **66** 句／`eos` 93 句；B：`late_drop` **152** 句／`eos` 10 句 | **多计的句数 == late_drop 句数**（逐字对上） |

#### 4.2 根因（读码定案，`live_caption/tts_service.py`）

`_handle_event()` 的 `kind == 'late_drop'` 分支只做了 `self.n_dropped += 1`
⇒ **没有把 jid 从 `self.pending` 里摘掉** ⇒

* **① drain 必然空等到超时**：`drain()` 的退出条件是
  `pending_n == 0 and n_done >= n_sub`；late_drop 的句**仍留在 `pending`** ⇒
  `pending_n` 永远 > 0 ⇒ **永远不成立** ⇒ 必然走满 timeout
  （APP-036 C4：`timeout = max(120, 1.5×积压)`）。
  **实测代价**：A 臂积压 229.22 s ⇒ timeout 343.8 s；B 臂积压 **763.70 s** ⇒ timeout **1145.6 s**
  ⇒ B 臂 ASR 跑完后**白等 1157.8 s ≈ 19 分钟**（CPU 0%，日志静默）。
* **② 同一句被计两次丢句**：late_drop 已 `n_dropped += 1`；`close()` 收尾时又把
  **仍在 pending 的同一批**当 orphan 再 `n_dropped += len(orphan)`
  ⇒ §29 不变式 `n_played + n_dropped == n_submitted` 被破坏。

#### 4.3 修法（只改 dev 树，**不改任何客户包**）

late_drop 分支改走 §60 已建立的**唯一原子口径** `_drop_one(jid)`
（`pending.pop` + `_inflight.discard` + `n_dropped += 1` **同一把锁内**）
⇒ ① 摘出 pending ⇒ drain 能正常退出；② close() 的 orphan 集合里不再有它 ⇒ 不会二次计。
⚠️ `register_dropped=False`：late_drop 之后 worker **不会**再为这一句回 `played` ⇒ 不必登记 `_dropped_ids`。
⚠️ 兜底：`_drop_one` 异常时**仍然计丢句**（否则该句永远留在 pending ⇒ drain 卡死，更糟）。

**改动文件**：`live_caption/tts_service.py`（141 346 B／SHA256 `b92f8a24c66bac2f…`）
⇒ **只改 dev 树** ⇒ v2.4／rc5／rc6／rc7 等**已交付包零影响**（它们各自带旧代码副本）。

#### 4.4 判据（行为级 ＋ 反证组）

`results/app/app465_late_drop_ledger.py`（14 660 B／SHA256 `d0bc683077541e76…`）
⇒ 产物 `results/app/app465_late_drop_ledger.json`（2 138 B／SHA256 `a1c24456561126e3…`）

* **REAL 组**（桩 worker，stdlib only，**不占 GPU/NPU、不跑推理、不取机器锁**）**4/4 PASS**：
  R1 late_drop 后 `pending` 里不再有该 jid｜R2 `n_played + n_dropped == n_submitted`｜
  R3 `drain()` 在 timeout 之前**返回 True**（用时 0.00 s）｜R4 `close()` 之后不变式仍成立。
* **反证组**（把修复块**整块精确替换**回旧写法 ⇒ 独立子进程真跑）**4/4 全触发**：
  R5 `n_pending=5`（>0）｜R6 扩展不变式 `played+dropped+pending=10 ≠ submitted=5` 被破坏｜
  R7 `drain()` 等满 6.01 s 才返回 False｜R8 `close()` 后 `sum=10 ≠ submitted=5`（双记）。
* 🔴 **反证构造自检**：副本必须**同名** `tts_service.py`（子进程 `sys.path[0]` 即临时目录）
  ⇒ 一定拿到改坏的那份；且 `ast.parse` 语法必须合法 ⇒ 否则「反证」是自己崩、不是判据命中。
* 🔴 **本轮自踩 3 个坑（判据层，已修）**：
  ① 首版反证用**字符串拼接**注入 ⇒ 缩进错乱 ⇒ 反证子进程自己 `IndentationError` ⇒ **反证无效**；
  ② 首版反证把 `sys.path` 指向仓库 `live_caption` ⇒ `import tts_service` 拿到**仓库版**（修好的）⇒ 反证落空；
  ③ R6 口径写错：旧写法下 **`n_played + n_dropped` 仍等于 submitted**（破坏的是**扩展不变式**
  `+ len(pending)`，且破坏点在 `close()` 之后）⇒ 改成扩展不变式 + R8 覆盖 close 后双记。

---

### 五、🔴 缺陷②：harness 的 **verdict 期望臂数口径**错（本轮自踩，已修）

`verdict` 原本硬编码「`n_arms == 6 and n_gpu_arms == 2`」
⇒ `--part gpu`（只跑 GPU 两臂）或 `--only-arm`（单臂补跑）时**必然假阴性 PARTIAL**。
⇒ 改为**按本轮实际要跑的臂数**（受 `--part` 与 `--only-arm` 双重约束）算期望值。

**反证（行为级）**：

| 场景 | 旧硬编码 6/2 | 新期望臂数口径 |
|---|---|---|
| `--part gpu`（smoke=0, gpu=2）全绿 | **PARTIAL**（假阴性） | PASS |
| `--only-arm gpu_control_asr_npu`（smoke=0, gpu=1）全绿 | **PARTIAL**（假阴性） | PASS |
| `--part both`（smoke=6, gpu=2）全绿 | PASS | PASS |

⇒ 同时加了 `--only-arm`（逗号分隔）⇒ 补跑单臂**不重跑**已完成的臂，不浪费设备时间。

---

### 六、🔴 缺陷③：`--outroot` 相对路径 ⇒ **产物落进客户包 + 判据假 FAIL**（本轮自踩，已修）

**事故**：本轮首次启动时 `--outroot results/app/app461_app100_device` 用了**相对路径**
⇒ 被测程序以 `cwd=pkg` 运行 ⇒ `--out` / `--tts-out` 落进
**rc7 包目录内**（`Confucius4_LiveCaption_MiniMVP_v1.0-rc7/results/app/app461_app100_device/`）
⇒ ① 证据散落在**客户包**里；② 判据按（相对仓库根的）`out_path` 读 ⇒ 读不到 ⇒ `asr_nonempty=False` ⇒ **假 FAIL**。

**修法**：`outroot` / `report` 一律 `os.path.abspath()` ⇒ 无论 cwd 在哪都落回指定证据目录。

**善后（已完成，客户包已复原）**：
1. 10 个产物**逐字节核对**后从 rc7 抢救回仓库证据目录（`results/app/app461_app100_device/`）⇒ **10/10 identical=True**；
2. 删掉 rc7 内误落的 10 个文件 + 3 层空目录 ⇒ **rc7 包根恢复原状**（`results/` 已不存在，
   其余 `app/`、`models/`、`python/`、`docs/` 等 mtime 全为打包时，**未受影响**）；
3. 🔴 **`MACHINE_LOCK` 已在作业结束时正常释放**（`[lock] 已释放`，`MACHINE_LOCK` 不存在）。

---

### 七、两臂设备结果（canonical 0–600 s，**都自然退出**）

判据脚本 `results/app/_app437_app099_device_jobs.py`（**venv Python** ⇒ 采样线程真能跑）
⇒ 原始报告 `results/app/app461_app100_device.json`（9 738 B／SHA256 `e5c3adb12910a721…`）
⇒ **重判** `results/app/app466_app100_device_rejudge.json`（10 770 B／SHA256 `e2725b2ee8cab3ee…`，
脚本 `results/app/_app466_rejudge.py` 6 149 B／SHA256 `30b8d3c3b943ea0c…`，
**用同一套 `judge_arm()`** 对仓库内证据重新判定 ⇒ 不改原报告）。

| 臂 | 配置 | exit | 墙钟 | 自然退出 | ASR 文本 | MT 文本 | TTS wav | 采样 | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| `gpu_same_asr_mt` | ASR GPU.0 ＋ MT GPU.0 ＋ TTS NPU | **0** | **951.9 s** | **是** | 9 796 字符 | 10 318 B | 422.13 s（提交 159／播完 93） | 449 点，shared **2262.1 MB**，RSS **7688.2 MB** | **PASS** |
| `gpu_control_asr_npu` | ASR NPU ＋ MT GPU.0 ＋ TTS NPU | **0** | **1759.1 s** | **是** | 9 795 字符 | 10 359 B | 41.22 s（提交 162／播完 10） | 832 点，shared **1810.6 MB**，RSS **7097.1 MB** | **PASS** |

* **总判定 `verdict = PASS`**，`timing_valid = True`（两臂都是自然退出 ⇒ 计时可比）。
* 🔴 **`peak_gpu_dedicated_mb = 0.0` 是实测**（381/381 样本里 Dedicated Usage 非零数 0，
  而 `n_gpu_instances = 1` ⇒ 计数器实例确实被找到、非失效）⇒ 本机 Intel 集显 UMA 架构下显存计入
  **Shared** ⇒ **不能把 0 解读成「无显存占用」**；只报共享显存与进程 RSS 的实测峰值。
* 🔴 **A 臂未复现 B 机 268 s 崩溃**：A 臂跑满 951.9 s **自然退出**（exit=0）⇒
  「ASR GPU.0 ＋ MT GPU.0 同占」在本机**未触发** §4.2 要复现的崩溃。
* 🔴 **两臂的差异真因是 NPU 争用，不是崩溃**：B 臂 ASR 在 NPU、MT 在 GPU.0 ⇒ MT 与 ASR **不争 NPU**；
  但 **TTS 也在 NPU** ⇒ B 臂 TTS 合成被 ASR 挤 ⇒ 积压峰值 763.70 s（A 臂仅 229.22 s）
  ⇒ 播完句数 10 vs 93、wav 41.22 s vs 422.13 s。
* ⚠️ **与旧数字不可直接比**：§175 用的是「0–300 s ×2」口径（600 s 时间线但**内容重复**），
  本轮是 **0–600 s 连续**（APP-100 要求）⇒ 两轮数字**不同口径**，
  按 APP-100「不要和旧的 61 分钟数字直接放在一起比」同理 ⇒ **不并表**。

---

### 八、其它产物与既有闸门

| 产物 | 字节 / SHA256 | 说明 |
|---|---|---|
| `results/app/_app455_app100_segment.py` | 9 925 B／`141fc1ab92f56c71…` | canonical 片段唯一事实来源 |
| `results/app/_app456_app100_segment_gate.py` | 13 242 B／`06cf0f9fa877612f…` | 片段口径行为级判据（26/26） |
| `results/app/app456_app100_segment_gate.json` | 4 561 B／`45f4736ba626c552…` | **26/26 PASS**（A 组 9／B 组 7／C 组 4／反证 6/6） |
| `results/app/_app459_lock_reclaim.py` | 2 563 B／`cf34b8b40e59f9d4…` | fail-closed 锁回收 |
| `results/app/_app461_launch.py` | 2 010 B／`b83a838c01602a73…` | **完全脱离会话**地启动设备长作业 |
| `results/app/app461_app100_device/` | **14 个文件** | 两臂 log / txt / mt.txt / wav / tts.jsonl / backlog_curve.csv / samples.jsonl |
| `results/app/app465_late_drop_ledger.json` | 2 138 B／`a1c24456561126e3…` | **8/8 PASS**（REAL 4/4 ＋ 反证 4/4） |

**既有闸门复跑（纯 CPU 静态，未占设备）**：
`assert_sec_per_char_calibrated.py` **27/27 PASS**（含反证 3/3）｜
`app109_lang_key_guard.py` **34/34 PASS**｜
`assert_window_same_source.py`（对 v2.4）**PASS**｜
`assert_pkg_clean.py`（对 v2.4）**0 违规**｜
`app057_tts_dropped_id_registration.py`（既有 TTS 账本回归）**REAL 全过**（A/B/C/D 组 9/9 ＋ 反证 2/2）。

---

### 九、🔴 本轮自踩 4 个坑（**都是真跑暴露，非静态推断**）

1. **`Start-Process` 起不来**（PowerShell 5.1）：本机环境里**同时存在 `Path` 与 `PATH` 两个键**
   ⇒ Start-Process 重建环境字典时冲突（`已添加项。字典中的关键字:"Path"所添加的关键字:"PATH"`）
   ⇒ 改用 `subprocess.Popen` + `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`（**不重建环境字典**）。
2. **脱离会话的进程仍会被会话带走**：首版 `_app461_launch.py` 起的作业，
   在**调用它的 shell 退出后**进程组被回收 ⇒ 作业被杀（且**留孤儿锁**）
   ⇒ 改用宿主托管的 `run_in_background` 作业（本轮实测可存活 45 min）
   ⇒ 🔴 **教训**：`nohup …&` 与裸 `DETACHED_PROCESS` 都不可靠 ⇒ 长作业要用**宿主托管的后台任务**，
   并**立刻 `addpid`** 到租约。
3. **自己改脚本 ⇒ 改出两个 bug**（verdict 期望臂数口径 §五；`for n, _ in ARMS` 解包崩溃
   ⇒ 臂元组是 `(name, *opts)` **长度不定** ⇒ 必须 `n, *_`）
   ⇒ 🔴 **教训**：**正在跑的作业会加载旧代码** ⇒ 中途改脚本会让「跑出来的结果」与「磁盘上的脚本」不一致
   ⇒ 改完必须**重跑**（本轮已重跑）。
4. **相对路径污染客户包**（§六）⇒ 判据假 FAIL + 证据散落 ⇒ 已修 + 已复原 rc7。

---

### 十、⏳ 待 reviewer 复核（本条）

1. **§174 的 self_ref 克隆闸门** ＋ **`assert_*.py` 排除规则**（上一轮，仍在等）
2. **§175 的 rc7 六臂冒烟 6/6 ＋ MANIFEST 84/84**（仍在等）
3. **本轮**：APP-100 canonical 片段口径（0–600 s 连续）＋ **两臂都自然退出（PASS）**
   ＋ **1 个 App 侧真缺陷**（`late_drop` 双记 ＋ drain 永不退出，已修 dev 树）
   ＋ harness 3 个口径/路径缺陷（verdict 期望臂数、`n, *_` 解包、`--outroot` 绝对路径）
4. **`late_drop` 修复的交付路径**：改在 dev 树 ⇒ **未进任何客户包**（APP-055：同步只能打新版本号；
   且 MiniMVP 按用户决定**暂不打包**）⇒ **等 reviewer 裁定何时随 v2.5 / rc8 出**
5. **倍率地板** 与 **`tts_late_drop_sec`**：用户 11-11 定「下次再定」⇒ 仍未裁定
   （⚠️ 本轮查出的 `late_drop` 缺陷**正落在这条阈值上** ⇒ 修好后该阈值的实际影响面会变）
6. **GUI 布局修复**仍未同步客户包（v2.5 未打包）
7. **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972）＋ **§3.6 切段开销不可测** ⇒ 仍需 reviewer 裁定
8. **§4.6(a)(b) 阈值四臂** 暂缓（用户决定）＋ **`xv_reg_*` 阻塞**
