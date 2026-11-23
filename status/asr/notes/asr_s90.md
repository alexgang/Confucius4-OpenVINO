# §90 明细 —— 纯巡检 ＋ 只读交付面自检（2026-11-23 09:33–09:45）

> 本文件是 `status/asr/STATUS_ASR.md` §90 章节的明细（**notes 用 LF**）。
> 🔴 **本轮性质：纯巡检**。未跑推理/计时、未取 MACHINE_LOCK、未改交付文件、未打包、
> 未动 `live_caption/`、未改纠偏文件、未改旧章节。

---

## 一、双通道核查结果（无新纠偏 ⇒ `last_ack` 不动）

### 1.1 纠偏文件通道

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\Trekker-PTL\confucius4-openvino\status\asr\CORRECTIONS_ASR.md` |
| 字节 | **105 868 B** |
| md5 | **`b6fd2e14…`**（`b6fd2e142d04d20268af28b2340dd49a`） |
| mtime | **2026-11-20 15:33**（与前 25+ 轮逐字相同） |
| `## ASR-` 标题数 | **35** |
| 最大编号 | **ASR-066** |
| `ASR-067+` 命中 | **0** |
| 结论 | 🔴 **无新 ASR 纠偏条目** ⇒ **`last_ack` 保持 `ASR-066`** |

### 1.2 QQ 邮箱通道（`1985197690@qq.com`）

收件箱（`after=2026-11-22`）：

| 消息 ID | 主题 | 时间 | 处置 |
|---|---|---|---|
| `msg_Nz6bxdO7DCc6M5vrw3fbQIdOWwXuYdRjFVGNmdYk1VS8iQ` | `[C4][A][CORRECTION][APP] APP-121 [HIGH] 2026-11-23 09:03` | 2026-11-23 09:04 | ✅ **已在 §89 响应**，已回复 `msg_Ex0uv-KzXep11NSNBfOVzCgjRnJPZ3rSB7XR1p1L4YxuPw`（09:31:34Z，`has_attachments=true`） |
| `msg_hsOIvMgPRRfrJCD_dkOA9dZOasydVjfFXIgPgmBAUY_Dog` | `[C4][A][CORRECTION][APP] APP-120 [HIGH] 2026-11-22` | 2026-11-22 13:26 | ✅ **已在 §88 响应** |

⇒ 🔴 **本轮无新邮件**。已发件箱核对：本模块 §89 回复在列；其余为 App/TTS/MT 线程的 STATUS 邮件。

---

## 二、核心动作：**reviewer item 3「zip 没做解压自检」的第一手实测**

### 2.1 为什么这一项该由 ASR 侧做（边界说明）

- reviewer item 3 写的是「zip 没做解压自检」⇒ 属 **App 线程的交付面**。
- 🟢 但 **ASR 侧有独立动机**：§89 已判定 **zip 内那份后端是缺陷版**（md5 `a92c02f2…`）⇒
  **若此 zip 直接发给客户，ASR=NPU 时 ≥~18.3 s 的段仍会停字幕** ⇒ 这直接命中本模块
  「NPU 档可用性」结论 ⇒ **只读核验是必要的**，**不代做**（不重签、不重打 zip、不改包）。

### 2.2 权威闸门是什么

`pack_v13.check_acceptance_binding(pkg_dir, expect_version=None)`（`pack_v13.py` L1560+），
即 **§208 打包前闸门⑤「验收绑定」**，fail-closed。口径：

- 身份：`ACCEPTED.json` 的 `version` 必须 == 目录名里的 `_vX.Y`（`_acc_pkg_version`）；
  `pkg_dir` 去掉 `<HOME>` 后的 basename 必须 == 目录 basename。
- 内容：`ACCEPTED.json` 的 `code_fingerprints` 必须与 **包内 `app/` 实际文件**逐条一致。
- 指纹算法（**app191 口径**，`_acc_module_fingerprints` + `_acc_aggregate`）：
  - 单模块：`sha256(归一化行尾后的字节)`（`_acc_norm_bytes`：**只把 CRLF 还原成 LF**，其余不动）；
  - 聚合：`sha256( 名称 + b'\0' + bytes.fromhex(单模块 sha256) )`，**按名排序**依次喂入。

### 2.3 🔴 实测 ①：现有 zip（v1.1）解压后**过不了自己的闸门**

**做法**（全程只读，**不解压到交付目录**）：用 `zipfile` 只把 zip 内 `app/*.py`
（**37 个**）＋ `ACCEPTED.json` 读到**临时目录**（`%TEMP%\asr090_zipcheck_*`），
再对临时目录跑 `check_acceptance_binding` ⇒ **跑完即删临时目录**。

**结果**：

```
GATE blocked= True   reason= CONTENT_MISMATCH
   n_registered = 33
   n_current    = 31
   n_changed    = 0
   changed      = []
   n_missing    = 2
   missing      = ['tts_cuda.py', 'tts_cuda_sidecar.py']
   n_extra      = 0
   extra        = []
   accepted_version = 1.1
   package_version  = 1.1
```

**判读**：

- ✅ `n_changed = 0` ⇒ **33 个已登记模块中存在的 31 个，内容逐字节与 `ACCEPTED.json` 一致**
  （说明 zip 的内容本身没被篡改，**是集合不完整**）。
- 🔴 `n_missing = 2` ⇒ **`tts_cuda.py` 与 `tts_cuda_sidecar.py` 在 `ACCEPTED.json` 的
  `code_fingerprints` 里声明存在，但 zip 里没有**。
  ⇒ 对应 reviewer item 3 的两个候选处置：**要么把这两个模块从 `code_fingerprints` 里去掉，
  要么让 zip 带上它们** ⇒ **zip 与 ACCEPTED 必须自洽**。
- 🔴 **另查（同一 zip）**：`app/asr06b_stateful_backend.py` md5 = **`a92c02f2eff02ec7cd29013cfdd2f8b8`**
  ⇒ **＝ 缺陷版**（§89 判定的那份，与 `git show HEAD:live_caption/asr06b_stateful_backend.py` 同 md5）。
  ⇒ **客户若拿到此 zip，ASR=NPU 时 ≥~18.3 s 的段仍会抛 `ValueError`**
  （`prompt 骨架 281 + 预留 64 > stateful 上界 320`）⇒ **字幕整条停掉**。

### 2.4 🟡 实测 ②：方法论纠错（重要，避免误报）

🔴 **第一次复算我用了错算法**：把「模块 sha256」当成字节再哈希一次 ⇒ 得出 31 个模块全部 mismatch。
**错因**：`code_fingerprints` 里存的**就是** `sha256(归一化字节)` 的 hex；聚合时要用
`bytes.fromhex(fp)`（**原始 32 字节**），不是 hex 字符串的字节。
**纠正后**：`n_changed = 0`、`n_changed` 的判定自洽 ⇒ **结论可信**。
⇒ **教训记入本 notes**：复算指纹**必须复用 `pack_v13` 自己的函数**（`_acc_module_fingerprints` /
`_acc_aggregate`），不要手写。

### 2.5 🔴 实测 ③：v1.1.1 目录已同步修法版，但 `ACCEPTED.json` **完全没重签**

**目录现状**（`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.1.1`）：

| 文件 | md5 / 字段 | 值 | 说明 |
|---|---|---|---|
| `app/asr06b_stateful_backend.py` | md5 | **`4b43dcbcd6ce5cb44cf8c07bc084a50f`** | ✅ **＝ 工作树修法版**（§89 的 B 版） |
| `app/live_caption_app.py` | mtime | 2026-11-23 09:22:42 | ✅ 已更新（App 的 `_loop` 加固） |
| `ACCEPTED.json` | `version` | **`1.1`** | 🔴 **没改成 1.1.1** |
| `ACCEPTED.json` | `pkg_dir` | **`<HOME>\Confucius4_LiveCaption_MiniMVP_v1.1`** | 🔴 **仍指 v1.1** |
| `ACCEPTED.json` | `accepted_at` | **`2026-11-22 16:33:56`** | 🔴 **仍是 11-22 旧值**（v1.1.1 与 v1.1 的 ACCEPTED.json **逐字节相同**，均 4 737 B） |
| `ACCEPTED.json` | `code_fingerprint` | **`9c732366eeaaf091f37ad95762787b06cf5ca3a668053312b5a6bbdb058017d6`** | 🔴 **仍是旧值**（对 v1.1.1 实际内容复算应为 `9c0c93c5…`） |

**权威闸门判定**：

```
check_acceptance_binding('…MiniMVP_v1.1.1')
  blocked = True    reason = VERSION_MISMATCH
  accepted_version = 1.1
  package_version  = 1.1.1
  accepted_pkg_dir = <HOME>\Confucius4_LiveCaption_MiniMVP_v1.1
```

⇒ 🔴 **fail-closed 成立**：版本身份先不符 ⇒ **连内容比对都没走到**。
⇒ 🔴 **目录当前处于「改了代码但未重签」的中间态** ⇒ **重打 zip 前必须先重签**，
且重签要同时改 `version`（→ `1.1.1`）与 `pkg_dir`（→ `…_v1.1.1`）
（签名脚本 `_app120_sign_accepted_v11.py` 的 `pkg_dir` 是按**目录名**拼的 ⇒ 传 `--pkg …_v1.1.1` 即可，
但 `--version` 要显式传 `1.1.1`）。

### 2.6 🟡 实测 ④：item 2 的 App 后端三素材 md5 补测**仍未产出**

`results/app/` 下与 ASR 相关的产物盘点：

| 产物 | 时间 | 走的代码路径 | 能否当 item 2 的证据 |
|---|---|---|---|
| `app120_asr_3mat_{NPU,GPU0,pml320,pml512}.json` | 11-22 14:20–14:31 | **ASR 模块的 `bk_run.run_stream` ＋ `asr065_backend.Asr065Runner`** | ❌ **否**（§89 已判定：不经过 App 的 `ASR06BStatefulBackend`） |
| `app121_asr_npu_longseg_old_v11.json` | 11-23 09:32 | **App CLI 走 v1.1 包**（`--asr-device NPU`） | ❌ 是**长段缺陷复测**，不是三素材 md5 |
| `app121_asr_npu_longseg_new_v111.json` | 11-23 09:30 | **App CLI 走 v1.1.1 包** | ❌ 同上 |
| `app121_asr_npu_prefix_unit_devtree.json` | 11-23 09:20 | dev 树**前缀口径**单元测试 | ❌ 是**前缀口径**验证，不是三素材 md5 |

**App 侧长段复测的两条关键原始字段**（`app121_asr_npu_longseg_old_v11.json`，
只读摘录，**供 App/reviewer 参考**）：

- `cli.rc = 1`；`cli.has_valueerror = True`；
  `valueerror_lines` = `['    raise ValueError(', 'ValueError: prompt 骨架 281 + 预留 64 > stateful 上界 320（音频过长）']`
- `segment_probe.n_forced_cuts = 1`，`forced_cut_durations_s = [20.48]`，
  `segment_probe.prefix_truncations = 5`、`truncations = 5`、
  `segment_probe.exception = 'ValueError: prompt 骨架 281 + 预留 64 > stateful 上界 320（音频过长）'`
- `cli.n_final_lines = 0` ⇒ **字幕一条都没出**（对应 §89 的「整条停掉」）。

⇒ 🟡 **§88④/⑤ 撤回后的替代证据仍缺** ⇒ **本模块不代跑**（同机、不重复占资源、属 App 交付面）。

---

## 三、只读巡检到的其他事实（不改任何东西，仅备案）

| 项 | 观测 | 与本模块的关系 |
|---|---|---|
| `live_caption/asr06b_stateful_backend.py` | 工作树 md5 `4b43dcbc…`（修法版），**仍未提交** | §89 已验证其合契约；提交属 App 线程 |
| App 侧在写的新脚本 | `_app121_asr_app_3mat.py`(09:27)、`_app121_asr_npu_longseg.py`(09:32)、`_app121_gui_smoke.py`(09:36)、`_app121_zip_extract_check.py`(09:37) | ⇒ **App 线程正在推进 item 2/3** ⇒ **本模块不重复、不代做** |
| `Confucius4_LiveCaption_MiniMVP_v1.1.1.zip` | **不存在**（v1.1 zip 仍是 11-22 16:51 那份） | ⇒ **重打 zip 未开始** |
| `MACHINE_LOCK` | **不存在** | ⇒ 本轮无需取锁，也无残留 |
| `status/asr/` 工作区 | 干净（`git status --short -- status/asr/` 为空） | ⇒ 本轮写入前后均已核对 |

---

## 四、本轮动作清单（边界内）

- ✅ 读 `CORRECTIONS_ASR.md`（只读）⇒ 确认无新条目 ⇒ `last_ack` 不动。
- ✅ 读 QQ 邮箱收件箱/发件箱（只读）⇒ 确认无新邮件。
- ✅ **只读**做 zip 解压自检（临时目录，跑完即删）⇒ `CONTENT_MISMATCH`。
- ✅ **只读**用权威闸门判定 v1.1.1 ⇒ `VERSION_MISMATCH`。
- ✅ **只读**盘点 `results/app/` ⇒ item 2 未产出。
- ✅ 写 `status/asr/notes/asr_s90.md`（本文件，**LF**）。
- ✅ 追加 §90 到 `status/asr/STATUS_ASR.md`（**只加新章节，不回头改旧章节**）＋ 更新头部 4 行。
- ✅ 归档 §89 全文 ⇒ `status/archive/STATUS_ASR_sec89_upto_20261123.md`（逐字）。
- ✅ 只提交 `status/asr/` ＋ `status/archive/` 下本模块文件。

## 五、🔴 本轮明确**没有**做（纪律）

- **未跑推理/计时**（无 RTF/RTF 数字）⇒ **未取 MACHINE_LOCK**。
- **未改任何交付文件**（`live_caption/`、包目录、zip、`ACCEPTED.json` 一律未动）。
- **未打包**（未生成/替换任何 zip）。
- **未改纠偏文件**（`CORRECTIONS_ASR.md` 逐字未动）。
- **未改旧章节**（§89 归档后正文只留摘要行；结论若有错，只在新章节写「撤回 §x」）。
- **未代做 App 线程的作业**（重签 / 重打 zip / item 2 补测）。
- **未动 `status/app/`、未动 `status/tts/`、未动 `status/mt/`**。

## 六、留给下一轮的交接语（原文）

> 「🔴 **item 2 的补测（用 App 后端跑 §86 三素材、NPU 与 GPU.0 各一次，报 transcript md5 与 `prefix_truncations`）属 App 线程的交付面作业**（App 已有 `_app121_asr_app_3mat.py`，需先重建包 v1.1.1）⇒ **ASR 侧不代跑**（不重复占用同机）；**ASR 侧只读配合**。」

🟢 **追加（§90 新增）**：

> 「🔴 **本轮只读实测：现有 `MiniMVP_v1.1.zip` 解压后过不了自己的验收绑定闸门**
> ⇒ `check_acceptance_binding` 判 **`CONTENT_MISMATCH`**（`n_missing=2`：`tts_cuda.py`、
> `tts_cuda_sidecar.py`）⇒ **zip 与 `ACCEPTED.json` 不自洽**；且 **zip 内后端仍是缺陷版
> `a92c02f2…`** ⇒ **此 zip 不可直接发客户**。
> 🔴 **`MiniMVP_v1.1.1` 目录已同步修法版但 `ACCEPTED.json` 未重签** ⇒ 闸门判
> **`VERSION_MISMATCH`** ⇒ **必须先重签（`version=1.1.1` ＋ `pkg_dir` 改指 v1.1.1），
> 再重打 zip，再做解压自检** ⇒ 三步缺一不可。」
