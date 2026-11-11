# STATUS_APP §176（归档件 · write-once）

> 🔴 **归档件 = write-once**：本文件落盘后**逐字节不再改**；活文档 `status/app/STATUS_APP.md`
> 只保留 ≤3 行索引（APP-052 ④）。任何更正都写进**新章节**，不改本文件。

## §176 执行 APP-100（last_ack=APP-100）｜修掉 **3 个 App 侧真缺陷**：**① 长跑片段口径的假前提**（§175 的「本机只有 300 s」经实测证伪 ⇒ 改用 SPE **0–600 s 连续** canonical 片段）＋ **② harness 超时 1500 s 误杀 B 臂**（B 臂 ASR 实测**已完成** 600.4 s／92 段，被杀在 **TTS drain** 阶段）＋ **③ 采样线程静默死掉**（`psutil` 缺失 ⇒ 显存/RSS 峰值**悄悄丢失**）｜**本条需等 reviewer 复核**

---

### 一、本轮基线（磁盘实测，非沿用旧结论）

| 项 | 值 | 取法 |
|---|---|---|
| `CORRECTIONS_APP.md` SHA256（开工） | `219ef841fc2c11a56fe8117774633c86d4ef8110e1e089b27e5d5608de9ce199` | `hashlib.sha256` 全文件 |
| 字节数 / mtime（开工） | 308 340 B ／ 2026-11-10 10:38:52 | `os.path.getsize` / `getmtime` |
| `## APP-xxx` 条数 / 最大编号 | **100 条** ／ **APP-100** | 正则 `^## (APP-\d+)` |
| STATUS 头部 `last_ack`（开工） | **APP-099** | `status/app/STATUS_APP.md` 第 3 行 |
| ⇒ 本轮新条目 | **APP-100**（唯一，编号 > last_ack） | 100 条 − 最大 APP-100 |
| 其它通道 | 全空：`shared/NOTICE*` 最新仍 11-05／agent-mail `not_bound`／`conversation_search` 命中 0／git ahead=0·behind=0／`claude-clone` 相对 main **0 个新提交** | — |

🔴 **纠偏文件全程只读**：开工＝收尾**逐字一致** ⇒ **SHA 零改动**（未改、未提交）。

---

### 二、APP-100 原文与 App 侧落点

`status/app/CORRECTIONS_APP.md` → **APP-100 [FYI] 2026-11-11 10:38**（用户决定：长跑评测改用 10 分钟片段）：

> 「以后凡是要求"全长 / 61 分钟 / SPE 全集"的 WER/CER 或 RTF 长跑，一律改用**同一段固定的 10 分钟片段**。
> 片段起止秒写进脚本和结果 json，所有臂、所有版本都用这同一段，保证可比。建议取 SPE 的 0–600 s；
> 如果开头有长静音或纯音乐，就顺延到第一段语音开始，并写明起点。」
> 「配对 bootstrap 照做……结果里注明"10 分钟片段口径"，不要和旧的 61 分钟数字直接放在一起比。」
> 「已下发、还没做完的纠偏（例如 ASR-053 第 3 项、APP-099）里的长跑，也按本条执行。」
> 「本条不改任何默认值，也不改判据阈值本身，只改素材长度。」

⇒ App 侧落点 = **APP-099 §4.2 的 A 机 GPU 同占两臂**（`results/app/_app437_app099_device_jobs.py`）。

---

### 三、🔴 缺陷①：§175 的片段口径建立在**一个假前提**上

#### 3.1 §175 当时写下的东西

`results/app/_app437_app099_device_jobs.py`（§175 落盘版，mtime 12:28:55）docstring 原文：

> 「本机只有 ``SPE_0000_0500.wav``（实测 **300.0 s**），无法直接取 0–600 s 原始片段
> ⇒ 固定片段 = **0–300 s**，`--loop` 播 **2 次** = 600 s 音频时间线」

代码同源常量（`git show HEAD:results/app/_app437_app099_device_jobs.py` 实测）：

```
LONG_AUDIO       = r'C:\Users\Trekker-PTL\shared\SPE_0000_0500.wav'
LONG_SEG_END_S   = 300.0
LONG_LOOPS       = 2
rc = p.wait(timeout=1500)
```

#### 3.2 三条独立证据 ⇒ **前提证伪**

| # | 证据 | 实测值 | 取法 |
|---|---|---|---|
| E1 | **全长素材一直在 App 仓库自己的 `test_audio/` 里** | `test_audio/260902_SPE_audio.wav` = **3671.189 s**／16 kHz／mono／117 478 136 B／mtime 2026-10-10 09:12 | `wave` 头 + `getsize` |
| E2 | **`shared/SPE_0000_0500.wav` 只是它的前 300 s 截断拷贝** | 旧件 payload SHA256 `a42284e61a8afc0fddf07bd0abcc2dd252d3be59be112a15bd3cb82b8995f52` ＝ 源前 300 s payload SHA256（**逐字节相同**） | `wave.readframes` + `sha256` |
| E3 | **ASR 侧 canonical clip 在本作业开工前 40 分钟就已存在** | `qwen3asr_06b/dev/asr044_evalset/clip_10min_0_600.wav` mtime **2026-11-11 10:52:30**；本作业 `app437_app099_device.json.created_at` = **2026-11-11 11:32:08** | `getmtime` vs json 字段 |
| E4 | **旧口径与 ASR 的口径内容不同** | 旧「0–300 s ×2」＝ 前 300 s 播两遍；canonical「0–600 s」＝ 连续 600 s ⇒ **违反 APP-100「所有臂都用这同一段，保证可比」** | §3.2 E2 + canonical 定义 |

#### 3.3 修正后的 canonical 片段（**唯一事实来源**）

新增 `results/app/_app455_app100_segment.py`（9 925 B／SHA256 `141fc1ab92f56c71…`）：

| 项 | 值 | 取法 |
|---|---|---|
| 源 | `test_audio/260902_SPE_audio.wav`（3671.189 s） | 常量 `SOURCE_WAV` |
| 片段边界 | **0.0 – 600.0 s**（起点**不顺延**） | `START_S` / `END_S` |
| 起点依据 | 首 10 s 窗 rms=0.035654／peak=0.351379 ⇒ 开头即语音 ⇒ 不顺延 | ASR-054 `asr137_make_10min_clip.py` 实测 |
| 产物 | `test_audio/clip_10min_0_600.wav`（19 200 044 B／mtime 13:49:47／SHA256 `d412f00af6b792ce033d5d36c71f9c0a0efd1da19d0643107a56336e16f378d0`） | `getsize` / `getmtime` / `sha256` |
| **payload** SHA256（语义契约） | `2f02e4c0b172bd952e5ba20018eeaeeb91673c0e778fa85c4a6305edf62fd54e` | 只哈希 PCM payload（不含 44 B 头）⇒ 与 wav 写法无关 |
| **跨模块同段** | 与 ASR 侧 canonical clip **逐字节相同**（`d412f00a…` == `d412f00a…`） | 两文件全量 `sha256` 相等 |

🔴 **App 侧自持副本**：不依赖 ASR 仓库路径 ⇒ 从**本仓库的源**现算＋现切，
再与 ASR 侧文件**逐字节核对**（`A.byte_identical_to_asr_canonical`）。

---

### 四、🔴 缺陷②：harness 超时 1500 s **误杀** B 臂

§175 把 `gpu_control_asr_npu` 判为「不可比」，理由是 `exit_code=-9`。
**实测证明该结论过重**——`results/app/app437_app099_device/gpu_control_asr_npu.log` 尾部：

```
[npu_int8] 音频 600.4s  墙钟 610.8s  RTF(计算) 0.931  出字延迟中位 6326 ms  最大积压 10.6s  段 92
```

⇒ B 臂的 **ASR 早已跑完 600.4 s、产出 92 段**（与 A 臂**同段数 92**），
被杀发生在其后的 **TTS drain 阶段**（日志尾部仍是「⏭ 跳过过期句（lag=11.1 s）」连续 146 句）
⇒ `rc=-9` 是**框架超时强杀**，**不是**被测程序崩溃，**也不是** ASR 没跑完。

⇒ 修正：`ARM_TIMEOUT_S` **1500 → 2700 s**（45 min，留足 TTS drain；仍 < `TOTAL_BUDGET_S`=55 min）。
🔴 `rc=-9` 的既有语义（框架强杀 ≠ 崩溃）保持不变。

---

### 五、🔴 缺陷③：采样线程**静默死掉** ⇒ 显存/RSS 峰值悄悄丢失

§175 的 `Sampler._run()` 把 `import psutil` 写在**线程体第一行**。
在本机**系统 Python** 上它抛 `ModuleNotFoundError` ⇒ **采样线程直接死掉**
⇒ `n_samples=0`，而**主流程照样往下跑** ⇒ 显存/RSS 峰值**无声丢失**。

🔴 本轮**实测复现**该故障（第一次起作业即触发，日志 `results/app/_app458_run.log`）：

```
Exception in thread Thread-6 (_run):
  File ".../_app437_app099_device_jobs.py", line 182, in _run
    import psutil
ModuleNotFoundError: No module named 'psutil'
```

⇒ 修正（三处）：
1. `import psutil` 失败 ⇒ **记进 `self.error` 并停止采样**（不再无声死掉）；
2. `summary()` 增 **`sampler_error`** ＋ **`sampling_ok`**（=`error is None and n_samples>0`）⇒ 判据看得见「没采到」；
3. 作业**改用仓库 `.venv` 的 Python**（`.venv/Scripts/python.exe`：psutil 7.2.2／win32pdh／numpy／soundfile 全在）⇒ 采样线程真能跑。

🔴 本轮自踩 4 个坑（已修 ⇒ 留档）：
① **`nohup … &` 随 shell 退出被杀** ⇒ 第一次后台作业（PID 32816）被杀、**留孤儿锁** ⇒ 按 fail-closed 探针（`OpenProcess` err=**87** ⇒ PID 不存在 ⇒ 死）回收锁后改用 `run_in_background` 重起；
② **`ctypes.get_last_error()` 默认永远返回 0**（`windll` 不保存 last-error）⇒ 必须 `ctypes.WinDLL('kernel32', use_last_error=True)` 才能拿到 **err=87**；
③ **手搓 WAV 头写错 bits-per-sample 字段**（写成 1 而非 16）⇒ 切出的片段时长读成 1200 s ⇒ 改用 `wave` 模块写（与 ASR 侧 `asr137` 同一写法）⇒ **逐字节等于** ASR canonical；
④ **反证构造会坏**：首版反证把 `LONG_SEG_END_S` 改成 300.0 后读 `b['no_old_end300']`（该键不存在）⇒ **KeyError** ⇒ 反证组自己崩 ⇒ 改成「**真 import 改写后的模块**、读**运行时**常量」。

---

### 六、判据：行为级 ＋ 反证组 ＋ 非空自证

`results/app/_app456_app100_segment_gate.py`（13 242 B／SHA256 `06cf0f9fa877612f…`）
⇒ 产物 `results/app/app456_app100_segment_gate.json`（4 561 B／SHA256 `45f4736ba626c552…`）

🔴 **行为级**（不是正则匹配）：对长跑脚本**真 import**（`importlib` + `exec_module`）读**运行时**常量；
片段**真读 wav、真算 SHA256**。

**A · 片段模块行为（9 项）**｜`A.clip_exists` / `A.duration_600s` / `A.payload_sha_matches` /
`A.file_sha_matches` / `A.start_is_0_no_shift` / `A.end_is_600` / `A.loops_is_1_continuous` /
`A.recomputed_from_source`（**从全长源独立复算**前 600 s payload SHA256）/
`A.byte_identical_to_asr_canonical`（**跨模块同段**）

**B · 长跑脚本运行时常量（7 项）**｜`B1.end_s_is_600` / `B2.loops_is_1` / `B3.audio_is_canonical_clip` /
`B4.start_s_is_0` / `B5.timeline_is_600` / `B6.uses_seg_module` /
`B7.arm_timeout_ge_2700`（**§175 的 1500 会 FAIL**）

**C · 结果 json 字段（4 项）**｜`C1.new_block_has_fields` / `C2.new_block_has_sha256` /
`C3.new_block_is_canonical` / `C4.legacy_block_detected_as_legacy`
（**能区分**旧块 `end_s=300 & loops=2` ⇒ 判据有鉴别力）

**反证组（6 项，全部必须被识破 ⇒ 证明判据不是恒 PASS）**

| # | 反证构造 | 期望被哪条判据抓住 | 实测 |
|---|---|---|---|
| R1 | `LONG_SEG_END_S` → `300.0` | B1／B5 | ✅ `end_s=300.0 timeline=300.0` |
| R2 | `LONG_LOOPS` → `2` | B2／B5 | ✅ `loops=2 timeline=1200.0` |
| R3 | `LONG_AUDIO` → 旧 300 s 截断件 | B3（且 A 组对该文件 FAIL） | ✅ `duration=300.0` |
| R4 | 篡改片段 1 个字节 | A3 | ✅ `sha=b3e36387937a4233…` |
| R5 | 报告块删掉 SHA256 字段 | C2 | ✅ `has_sha=False is_canonical=False` |
| R6 | `ARM_TIMEOUT_S` → `1500` | B7 | ✅ `ARM_TIMEOUT_S=1500` |

**🔴 非空自证**（把 §175 的**旧字节**喂进**同一判据** ⇒ 必须 FAIL）：
`git show HEAD:results/app/_app437_app099_device_jobs.py` 真导入 ⇒
`LONG_SEG_END_S=300.0` ⇒ **B1 FAIL**；`LONG_LOOPS=2` ⇒ **B2 FAIL**；
`LONG_AUDIO=shared/SPE_0000_0500.wav` ⇒ **B3 FAIL**；
（`B5 timeline==600` 仍 PASS ⇒ **正因如此** B3 的内容核对不可省）

**判据汇总：26/26 PASS，0 FAIL**（`app456_app100_segment_gate.json` → `n_pass=26`／`n_fail=0`／`pass=true`）。

---

### 七、本轮改动清单（**只改 App 模块负责的文件**）

| 文件 | 改动 | 字节／SHA256 |
|---|---|---|
| `results/app/_app455_app100_segment.py` | **新增**：canonical 片段唯一事实来源（切片＋校验＋元信息） | 9 925 B／`141fc1ab92f56c71…` |
| `results/app/_app456_app100_segment_gate.py` | **新增**：行为级判据＋反证组＋非空自证 | 13 242 B／`06cf0f9fa877612f…` |
| `results/app/app456_app100_segment_gate.json` | **新增**：判据产物（26/26） | 4 561 B／`45f4736ba626c552…` |
| `results/app/_app437_app099_device_jobs.py` | **改**：片段口径 → canonical；`ARM_TIMEOUT_S` 1500→2700；采样线程错误可见；`--outroot/--report` 参数化（重跑不覆盖 §175 证据）；`LEASE_TOKEN` 改环境变量 | 23 291 B／`10cf12523680ce0e…` |
| `results/app/_app459_lock_reclaim.py` | **新增**：fail-closed 锁回收（`use_last_error=True` ⇒ err=87） | 2 563 B／`cf34b8b40e59f9d4…` |
| `test_audio/clip_10min_0_600.wav` | **新增**：canonical 片段（**gitignored**，与本仓库其它 wav 一致） | 19 200 044 B／`d412f00af6b792ce…` |

🔴 **未改**：任何生产代码（`live_caption/*.py`）、任何客户包目录、任何默认值、任何判据阈值
⇒ **已交付包零影响**；**未打包 v2.5／未打 rc8／未通知用户／未调 MiniMax**。

---

### 八、canonical 片段 GPU 两臂重跑（APP-099 §4.2，§176）

| 项 | 值 |
|---|---|
| 作业脚本 | `results/app/_app437_app099_device_jobs.py --part gpu`（**venv Python** ⇒ 采样线程真能跑） |
| 片段 | **SPE 0.0–600.0 s 连续**（`loops=1` ⇒ **不加 `--loop`**，避免 600 s 边界回卷污染尾端） |
| 产物目录 | `results/app/app458_app100_device/`（**新目录 ⇒ 不覆盖 §175 证据**） |
| 报告 | `results/app/app458_app100_device.json` |
| 锁 | `machine_lock_app` fail-closed 排队；PID 36180；`MACHINE_LOCK` 内容含 module/PID/started/host |
| 租约 | 本轮 token `94473c5e`；`addpid 36180` ⇒ 下一会话拿 **BUSY** |

**结果见 §九（活文档「最近更新」行）**。

---

### 九、⏳ 待 reviewer 复核（本条）

1. **§174 的 self_ref 克隆闸门** ＋ **`assert_*.py` 排除规则**（上一轮，仍在等）
2. **§175 的 rc7 六臂冒烟 6/6 ＋ MANIFEST 84/84**（仍在等）
3. **本轮**：APP-100 片段口径修正（canonical 0–600 s）＋ 3 个真缺陷（假前提／误杀／静默采样）
4. **倍率地板** 与 **`tts_late_drop_sec`**：用户 11-11 定「下次再定」⇒ 仍未裁定
5. **GUI 布局修复**仍未同步客户包（v2.5 未打包）
6. **§3.5 音色归属判据失效**（三人真值余弦 0.957–0.972）＋ **§3.6 切段开销不可测** ⇒ 仍需 reviewer 裁定
7. **§4.6(a)(b) 阈值四臂** 暂缓（用户决定）＋ **`xv_reg_*` 阻塞**
