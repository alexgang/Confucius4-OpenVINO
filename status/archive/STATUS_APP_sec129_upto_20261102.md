# STATUS_APP 归档（§129 正文逐字留存）

> 本文件由 `results/app/_app130_archive_sec129.py` 于 2026-11-02 生成。
> **§129 的正文逐字保留，内容一字未删**；原位留有指针行（见 `status/app/STATUS_APP.md`）。

### §129 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 自查出并修掉 4 个真缺陷（闸门自身缺陷 3 个 + 边车崩溃 1 个）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 04:47）


**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ `last_ack` **APP-061** ⇒ **无新纠偏条目**（本轮**不执行**任何新条目；`last_ack` **不变**）。

**租约**：`session_lease.py acquire app` ⇒ `TOKEN=2aa48e52`（**无 TAKEOVER**）⇒ 本轮全程持租约。

#### ① 🔴🔴 **闸门自身缺陷 1（真缺陷，不是产品缺陷）**：`app224` 用**移动的 `git HEAD`** 当「改前基线」⇒ 修复一提交，闸门就在**正确的代码上永久报 FAIL**

* **现象**：§128 把 escape 修复提交进 `25a4974` 后，重跑 `app224` ⇒ **0 PASS / 5 FAIL**（5 个文件全 FAIL，`warn_before=0 warn_after=0`）。
* **根因**：`check_escape_fixes()` 的 `baseline = git_head_bytes(rel)` = **移动的 HEAD** ⇒ 修复入库后 HEAD 变成「改后」⇒ `warn_baseline` 变空 ⇒ `warn_cleared = 恒 False` ⇒ **闸门永久红**。
* 🔴 **这不是「代码退化」**：实测 `fae75d9`（§128 的父提交）里 4 个文件**各有 1 条 `SyntaxWarning`**，`25a4974` 里 **0 条** ⇒ **代码是对的，闸门是错的**（对齐记忆「判据 FAIL 先怀疑判据/环境」）。
* **改法**：基线**钉死**到 `BASE_REV = 'fae75d9'`（`app223` 是 §128 新建文件、不在该提交里 ⇒ 回落到 §128 的改前备份 `shared/app223_backup_20261102/`）。
* 🔴 **顺带补一个弱标记的洞**：若基线取不到，原实现会「**恒 PASS**」（`warn_cleared` 只要求 `not warn_now`）⇒ 现在要求 `baseline_had_warn`（**基线本身必须有告警**）⇒ 否则判「无法判定」。
* 🔴 **并新增 ⑥「判据自检」**：造一份**故意带 `SyntaxWarning` 的坏文件**跑同一套判据 ⇒ 必须被判成「没归零」⇒ **判据非恒真**。
* **改后实测**：`app224` ⇒ **5 PASS / 0 FAIL**（① escape 5/5 PASS，② 锁闸门 **42/42**，③ 改前基线 `fae75d9` **30/39**（9 条假 FAIL，与 §128 记录的 30/39 **一致**），④ CUDA 置灰 **4/4**，⑥ 判据自检 PASS）⇒ 证据 `results/app/app224_app061_escape_lock_gates_evidence.json`（**7 379 B** / SHA256 `a97d35b49e648a3f…` / mtime 2026-11-02 04:43:26）。

#### ② 🔴🔴 **闸门自身缺陷 2**：`test_machine_lock_app.py` 第 11 组的 AST 反证**判据恒真**（抓不到 `os.path.exists`）

* **发现**：反证用的谓词是 `node.func.attr == 'exists' and isinstance(node.func.value, ast.Name) and node.func.value.id == 'os'` ⇒ 它只能匹配 `os.exists(x)`；而代码里写的是 **`os.path.exists(x)`**（`func.value` 是 `ast.Attribute`，**不是** `ast.Name`）⇒ **谓词永远匹配不到** ⇒ `old_has_exists` 恒 `False` ⇒ 「修复前的 acquire 没有 exists 前置判断」这条断言**恒 PASS** ⇒ **反证没有鉴别力**。
* 🔴 **实测确认**：把当前源码（**含** `os.path.exists(lock_path)`）喂给该谓词 ⇒ 仍返回 `False`；只有人为注入 `os.exists(...)`（Name 形态）才返回 `True` ⇒ **谓词与真实代码形态脱节**。
* ⚠️ **本轮只定位，**未改判据**（属共享锁闸门、影响 ASR/MT/TTS 三个模块共用的 `machine_lock_app.py`）⇒ 留证交 reviewer 裁定（见 §129 ⑧）。
* 🔴 **同时确认**：`acquire` 的「先探测、后创建」修法**本身是对的**（`3b07811` 引入 `os.path.exists` 守卫，`8d6bcc1` 及其父提交都没有）⇒ **被测对象无缺陷，缺陷在判据**。

#### ③ 🔴🔴 **闸门自身缺陷 3**：`app223` 真机验收 harness 的 3 个问题（`--dry-run` 跑不出来 / 自检**冲掉**真机证据 / 反证臂**从不判定**）

* **(a) `--dry-run` 单独用时**永远走不到**打印命令的分支**：原实现先判 `if not args.run:` 就 return ⇒ 文档里写的「③ 只打印命令不跑」**实际只跑了自检**。⇒ 改法：`--dry-run`（且未带 `--run`）**先**打印 3 条臂命令并返回，**不跑设备、不写证据文件**。
* **(b) `--self-test` 会覆盖真机证据**：`--out` 默认指向 `app223_app061_device_acceptance_evidence.json` ⇒ 跑一次自检就把**真机跑出来的设备级证据冲成 `SELFTEST_ONLY`**（实测：本轮第一次跑自检就把该文件改了 ⇒ 已 `git checkout` 还原）。⇒ 改法：自检结果**另存** `…_evidence.selftest.json`；实测自检前后 canonical 证据 SHA256 **逐字相同**（`199529db275832601…`）⇒ **未被覆盖**。
* **(c) v2.1 反证臂**只被存进 `out`、**从不判定** ⇒ 「v2.1 用同一套判据**必须 FAIL**」这句话**没有任何强制力**（万一 v2.1 也 PASS，闸门照样报 PASS）。⇒ 改法：用**同一套** `judge()` 判反证臂 ⇒ `counterproof_v21_n_fail == 0` ⇒ **整轮判 FAIL**（不是「无法判定」）。
* **(d) 产物目录卫生**：`results/app/app223_device_out/` 在仓库内 ⇒ `.wav`/`.log` 被根 `.gitignore` 命中，但 **`.jsonl`/`.txt` 不会** ⇒ 真机跑完留一堆未跟踪文件。⇒ 改法：**在产物目录内部**放一个 `.gitignore`（内容 `*`）⇒ **不改仓库根的 `.gitignore`**（那是全仓库共享文件，不该由本模块改）。
* **回归**：改后 `--dry-run` 实测**打印出 3 条完整臂命令**（`tts_off` / `tts_on_preset` / `tts_on_clone`，均含 `--engine gpu_int8 --translate zh --asr-device GPU.0 --mt-device GPU.0 --tts-device NPU`）⇒ `--self-test` **5 PASS / 0 FAIL** 且 canonical 证据 SHA 未变 ⇒ **3 个缺陷全部修好**。

#### ④ 🔴🔴 **APP-061② 的「附带问题」终于处理了**：`Fatal Python error: _enter_buffered_busy`（reviewer 原话：「边车退出时有 `Fatal Python error: _enter_buffered_busy`（21:24:51）」）—— §127 / §128 **都没修**

* **根因（已实测复现，不是推测）**：`sys.stdin.buffer` 是 `BufferedReader`；边车的**命令读取线程**（daemon）阻塞在 `readline()` 时**持有该缓冲对象的内部锁** ⇒ 边车退出 ⇒ CPython 进入 finalizing ⇒ 要 flush/close 同一个 `BufferedReader` ⇒ **抢不到锁** ⇒ `Py_FatalError("_enter_buffered_busy: could not acquire lock for <_io.BufferedReader name='<stdin>'> at interpreter shutdown, possibly due to daemon threads")` ⇒ **边车以 `0xC0000005`（3221225477）崩掉**。
* **修法**：读取线程**不再用 `sys.stdin.buffer`**，改用**裸 fd** 的 `os.read(0, …)`（自己攒行缓冲）⇒ 不持有任何 Python 缓冲对象的锁 ⇒ 退出时不抢锁。
* 🔴 **判据非恒真（A/B 干净对照）**：`results/app/app225_app061_sidecar_crash.py` 跑**两份只差读取方式**的子进程（同一台机、同一套管道、连控制流都照抄真实边车：**`quit` 只塞队列、读取线程不退出** ⇒ 才会卡在「读取线程正持锁阻塞在读」的真实崩溃现场）：

| 组 | 读取方式 | 实测 rc | `_enter_buffered_busy` | 收到数据 |
|---|---|---|---|---|
| `orig`（改前） | `sys.stdin.buffer.readline()` | **3221225477（崩）** | **True** | ✅ |
| `fixed`（改后） | `os.read(0, …)` | **0（正常退出）** | False | ✅ |

  ⇒ **两组都收到了数据** ⇒ 「改后不崩」**不是**因为「没读」⇒ 判据有效。**4 PASS / 0 FAIL** ⇒ 证据 `results/app/app225_app061_sidecar_crash_evidence.json`（**1 948 B** / SHA256 `6e1dbc9c97c44f1a…` / mtime 2026-11-02 04:45:17）。
* 🔴 **改动范围**：**只改开发版 `live_caption/tts_cuda_sidecar.py`**（25 600 B / SHA256 `677daaee11082184…`）⇒ **v2.2 客户包一个字节都没动**（包内仍是改前版）⇒ 下一版必须打 **v2.3**（**禁止 `--same-version`**），**本轮未打包**（未获授权）。

#### ⑤ ⛔ **设备级实测仍未做**（与 §128 同一阻塞，且本轮**再次实测确认**）

* `machine_lock_app.wait_quiet_window_cpu(30)` ⇒ **ok=False**；`last_busy_pids=[14712]` = **用户自己的 v2.1 GUI 会话**（`OpenProcess`+`GetExitCodeProcess` 实测 **alive / 259**）。
* 🔴 **本轮新增的直接证据**：`14712` 的 **CPU 时间增量 = 0.656 s / 5 s**（`GetProcessTimes` 两次采样差）⇒ **用户会话确实在跑、确实在烧 CPU** ⇒ 与用户抢 NPU 会让**两边数字都失真** ⇒ **不开跑**。
* ⇒ **APP-061 ①③④⑤ + ③(e) 的设备级数字仍然「未实测」**（代码层已由 `app215`/`app219`/`app220` 覆盖）⇒ 下一步：机器安静 + 用户会话结束后跑 `python results/app/app223_app061_device_acceptance.py --run`（**本轮已把该脚本的 3 个缺陷修好 ⇒ 一键可跑**）。

#### ⑥ ✅ **既有回归套件复跑（改了代码 ⇒ 必须复跑）**

| 闸门 | 结果 | 说明 |
|---|---|---|
| `app215`（①④⑤ 语音/克隆） | **29 PASS / 0 FAIL / 0 NONE** | 7 条反证全被抓住 |
| `app220`（③ 卡顿遥测/预缓冲/倍速封顶） | **39 PASS / 0 FAIL / 0 NONE** | 5 条反证全被抓住 |
| `app219`（⑥ 界面紧凑） | **13 PASS / 0 FAIL / 0 NONE** | 含 1024×800 截图 |

⇒ 三个闸门**全部与 §127 记录一致**（29/0、39/0、13/0）⇒ **本轮改动没有引入回归**（复跑输出另存 `/tmp/app21*_recheck.json`，**未覆盖**仓库里的原证据）。

#### ⑦ 🔴 **收尾复核（`CORRECTIONS_APP.md` 全程只读）**

* 开工基线：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**。
* 收尾实测（2026-11-02 04:47 现场重算）：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**（APP-001…APP-061）⇒ **与开工基线逐字相同 ⇒ 本轮 reviewer 未追加新条目 ⇒ 「SHA 零改动」在本轮成立**（与 §125/§126「中途被追加」那两轮**不同**，勿混为一谈）。
* 本模块对 `CORRECTIONS_APP.md` **全程只读、未写入**。

#### ⑧ 🔴 **本轮新增待 reviewer 裁定（未自行改语义）**

① **锁闸门第 11 组的 AST 反证谓词恒真**（只认 `os.exists`，抓不到 `os.path.exists`）⇒ 反证**没有鉴别力**。**修它要动共享锁闸门**（`results/app/test_machine_lock_app.py`，被 ASR/MT/TTS 共用的 `machine_lock_app.py` 覆盖）⇒ 本轮**只定位、只留证**，改法与范围交 reviewer 定。
② **`app224` 的基线钉在 `fae75d9`** ⇒ 该提交若被 `git gc`/改写则基线会失效（Git 提交不可变，正常不会变）⇒ 已同时保留 `shared/app223_backup_20261102/` 作第二来源。
③ **APP-061② 另两条附带问题**：边车依赖包外 `C:\Users\Trekker-PTL\_fq3tts_env`（客户机不存在 ⇒ 属 **D3** 待决）＋ **v2.2 包内的 `tts_cuda_sidecar.py` 仍是改前版**（`_enter_buffered_busy` 与 `\_` 告警都在）⇒ **必须打 v2.3 才带上修复** ⇒ **本轮未打包**。

#### ⑨ 本轮交付

* 代码（**只改开发版**，客户包一个字节都没动）：`live_caption/tts_cuda_sidecar.py`（**25 600 B** / SHA256 `677daaee11082184…`）。
* 验收脚本：`results/app/app225_app061_sidecar_crash.py`（**11 189 B** / SHA256 `5bc41eb9cb3bb099…`）、`results/app/_app129_archive_sec127_128.py`。
* 修改的既有脚本：`results/app/app223_app061_device_acceptance.py`（**36 298 B** / SHA256 `91d9b3e6daf5ea15…`）、`results/app/app224_app061_escape_lock_gates.py`（**17 068 B** / SHA256 `bae994ebaef6b276…`）。
* 证据：`results/app/app225_app061_sidecar_crash_evidence.json`（**1 948 B** / SHA256 `6e1dbc9c97c44f1a…`）、`results/app/app224_app061_escape_lock_gates_evidence.json`（**7 379 B** / SHA256 `a97d35b49e648a3f…`）、`results/app/app223_app061_device_acceptance_evidence.selftest.json`（**2 458 B** / SHA256 `e93dd100b250cef2…`）、`status/archive/STATUS_APP_sec127_128_upto_20261102.md`。
* 🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**（v2.1、v2.2 目录与 zip **一个字节都没动**）；**未提交任何 `CORRECTIONS_*.md`**。

