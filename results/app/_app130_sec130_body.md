### §130 ✅ **巡检无新纠偏（61 条 = `last_ack` APP-061）⇒ 自查出并修掉 3 个真缺陷（闸门口径 1 个 ＋ 串音 1 个 ＋ 判据作用域 2 个）** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-11-02 09:56）

**开工基线（`CORRECTIONS_APP.md` 只读）**：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / 条目 **61**（APP-001…APP-061）⇒ **无新纠偏** ⇒ `last_ack` **不变（APP-061）**。

**租约**：`session_lease.py acquire app` ⇒ `TOKEN=77c10eea`（**无 TAKEOVER**）⇒ 本轮全程持租约（每步 + 耗时操作前后 `beat`）。

#### ① 🔴🔴🔴 **闸门自身第 4 种「坏法」：`app224` 的「字符串常量逐字不变」按下标比 ⇒ 假 FAIL**

**实测（改判据前）**：用**当前**代码跑 `app224` 的 `check_escape_fixes()` ⇒ **3 PASS / 2 FAIL** ⇒ 而仓库里已提交的证据记的是 **5 PASS / 0 FAIL** ⇒ **仓库证据与当前判据已不一致**。

**根因**（`results/app/app224_app061_escape_lock_gates.py` 改前）：
```python
for i, (x, y) in enumerate(zip(s_head, s_now)):   # 🔴 按下标逐位比
    if x == y: continue
    if only_ctrl_to_visible(x, y): diffs.append('控制字符→可见字面量')
    else: diffs.append('#%d 值变了' % i)
```
⇒ `ast.walk` 的**遍历顺序不稳定** ⇒ 代码里**合法新增/删除一个字符串常量**，
后面所有下标就**整体错位** ⇒ 把「错位的两个不同常量」误判成「值变了」。

**实测证据**（`collections.Counter` 多重集复核）：

| 文件 | 基线常量 | 当前常量 | 下标口径报出 | 多重集口径 | 真相 |
|---|---|---|---|---|---|
| `live_caption/tts_cuda_sidecar.py` | 152 | 152 | **27 条**「值变了」 | 丢 1 / 增 1 | 真变化 **1** 个（§129 合法改 docstring） |
| `results/app/app223_app061_device_acceptance.py` | 524 | 556 | **483 条**「值变了」 | 丢 **0** / 增 **32** | **全是假 FAIL**（§129 合法新增自检分支） |

**🔴 假 FAIL 的两个来源可分辨**：① emoji 差异（`🔴🔴🔴` vs `🔴🔴🔳`）是**错位假象**
⇒ 两份文件**都含** `🔴🔴🔴` 版本（实测 `count('🔴🔴🔴')=19` / `count('🔴🔴🔳')=2`）⇒ **不是字符被改坏**；
② `app223` 的 **32 个新增常量**（§129 合法增量）。

**修法**（3 处，全部在闸门脚本内，**不改产品代码**）：
1. **改按多重集比**（`collections.Counter`）：「值一个都没变」⇒ **`Counter(base) - Counter(now)` 为空**
   （基线里每个常量值仍以**相同出现次数**存在于当前文件）⇒ **允许新增**（记 `added`）。
2. **拆出 docstring**（`split_constants()`）：**docstring 是会合法演进的散文**
   （§129 就给 `_start_command_reader` 的 docstring **追加了一整段崩溃根因与修法说明**
   ⇒ 该 docstring 的**值必然变**）⇒ docstring **只报告不阻断**（记 `docstring_drift`）；
   **非 docstring 的字符串常量**（格式串/键名/字面量）是**行为承载**的 ⇒ **严格判**。
3. **保留「控制字符→可见字面量」豁免**（docstring 改 raw 时 `\n` 变字面量是**故意**的）。

**🔴 判据自检（新增 ⑦⑧，**双向**证明非恒真/非恒假）**：
- ⑦ 多重集口径自检 **5/5**：①真丢一个值 ⇒ FAIL ②只新增 ⇒ PASS ③值被替换 ⇒ FAIL
  ④仅重排 ⇒ PASS ⑤控制字符豁免 ⇒ PASS。
- ⑧ docstring 拆分自检 **3/3**：①拆分计数正确 ②docstring 演进后行为常量仍 PASS
  ③**行为常量 `"alpha"`→`"ALPHA"` ⇒ 必须 FAIL**（证明豁免**没**变成「什么都放过」）。
- 🔴 **另做真实产物的负向测试**（`results/app/_app130_negative_test.py`，**5/5**）：
  拿**已知有缺陷的旧产物**（基线版本）跑同一套判据 ⇒ 「告警已归零」必须判 **False**；
  改掉 / 删掉一个**行为常量** ⇒ 必须判 **False**；合法新增 / 仅重排 ⇒ 判 **True**。

**改后实测**：`app224` ⇒ **5 PASS / 0 FAIL**（锁闸门仍 **42/42**；改前基线 **30/39**）⇒ 与 §129 一致。

#### ② 🔴🔴 **CUDA 路线「回落预设」不换参考音频 ⇒ 串音**（真缺陷，改前既有）

**现象**：`live_caption/tts_worker.py` 的 `_apply_spk_voice()`：`spk` **有值**但**该 spk 没登记音色**
（`row is None`）⇒ 回落预设 A，但**没有** `eng.set_ref_audio(预设A的参考音频)`
⇒ **边车里仍是上一个说话人的克隆参考音频** ⇒ 实播**串音**（听到的是上一个人的声音），
且逐句遥测写 `voice_kind='preset'` **与实际不符** ⇒ **矛盾字段**。

**对比**：`_fallback_to_preset()` 的 CUDA 分支**本来就会**换 ref ⇒ **两条「回落预设」出口行为不一致**。

**修法**（**只改开发版 `live_caption/tts_worker.py`**）：
- 新增共用出口 `_fallback_to_preset_ref_cuda(why)`（CUDA 路线**只换 ref 音频**、
  **`speaker_name` 保持 `'A'`**、**不清空**）。
- `_apply_spk_voice()` 的 **3 个**回落出口（`row is None` / 该 spk 没有 ref / 切换抛异常）
  **全部收敛**到它；`_fallback_to_preset()` 的 CUDA 分支**也收敛**到它
  ⇒ 以后再漏就会很明显。
- ⚠️ **BabelVox 路线完全不受影响**（`_apply_spk_voice` 的 else 分支原样保留）。

**验收**（`results/app/app226_app061_cuda_fallback_ref.py` ⇒ **10 PASS / 0 FAIL / 0 无法判定**）：
① 未登记 spk ⇒ 边车最终 ref = `preset_A.wav`（`set_ref_audio` 恰好 1 次）
② 已登记 spk ⇒ ref = 该 spk 的克隆音频 ③ **完整时序 S1 克隆 → S2 未登记 ⇒ ref 由
`S1_clone.wav` 切回 `preset_A.wav`**（**串音场景已消除**）④ 该 spk 无 ref ⇒ 切回预设
⑤ 切换抛异常 ⇒ 切回预设 ⑥ **反证：BabelVox 路线不受影响**（embed 仍为预设向量）
⑦ **反证：把修复改回旧行为 ⇒ 判据必须 FAIL**（实测 ref=`None` ⇒ 被抓住 ⇒ **非恒真**）。

#### ③ 🔴 **改代码 ⇒ 既有回归套件必须复跑**（`app215` 判据被重构波及，**2 处判据要跟着走**）

`app215` 的 **M2/M3 反证锚点**与 **①b 判据**都指向**被 §130 重构搬走的代码**：

| 项 | 现象 | 修法（**语义一字不变**） |
|---|---|---|
| `MUT_W_1B_OLD/NEW` | 变异点命中 0 次 ⇒ `[ABORT]` | 代码搬进 `_fallback_to_preset_ref_cuda()` ⇒ **只改缩进**（12 → 8 空格） |
| ①b `1b_cuda_fallback_keeps_name` | 判 FAIL | ① **`ast.walk(cuda_branch)` 会把 `else` 分支也遍历进去** ⇒ 语义被污染 ⇒ 改**只看 `cuda_branch.body`** ② 委派检测**改用 AST 找 `Call`**（不用源码片段：`ast.get_source_segment` 对合成节点取不到 ⇒ 恒 False）③ **鉴别力不变**：两处都没有 BoolOp 赋值 ⇒ 仍 FAIL（v2.1 形态必须被抓出来） |

**复跑结果（与 §127/§129 完全一致 ⇒ 无回归）**：

| 套件 | §127/§129 | §130 | 结论 |
|---|---|---|---|
| `app215`（①④⑤ 语音/克隆） | 29 / 0 | **29 / 0** | ✅ 一致 |
| `app220`（③ 卡顿遥测/预缓冲/倍速封顶） | 39 / 0 | **39 / 0** | ✅ 一致 |
| `app219`（⑥ 界面紧凑） | 13 / 0 | **13 / 0** | ✅ 一致 |
| `app224`（② 附带问题 + 锁闸门） | 5 / 0 | **5 / 0** | ✅ 一致（判据本身修了） |
| `app226`（本轮新增：CUDA 回落换 ref） | — | **10 / 0** | ✅ 新增 |

🔴 **复跑输出**：仓库内 3 份证据 JSON 的 **`n_pass`/`n_fail`/`verdict` 与 §129 逐字相同**
（`app215` 29/0、`app219` 13/0、`app220` 39/0）⇒ **只有时间戳变了** ⇒ 已随本轮提交。

#### ④ ⛔ **设备级实测仍未跑（本轮阻塞原因已换人，但结论不变）**

- 🔴 **安静窗口**（`machine_lock_app.wait_quiet_window_cpu(45, 330)`）⇒ **ok=False**（等满 330 s）。
- 🔴 **本轮精确定位了干扰源**（`results/app/_app130_probe_busy.py` ⇒ **连命令行一起记录**）：
  「在算」的是**别的模块**的设备作业，不是用户会话：
  - **ASR**：`qwen3asr_06b\.venv\Scripts\python.exe asr105_spk_window_5s_vs_10s.py --devices GPU.0`
    ⇒ **正在做 D1（旁路窗口 5 s vs 10 s）的评估** ⇒ 且**持有 `shared/MACHINE_LOCK`**
    （`module: asr` / `pid: 27864` / `task: asr041-spk-window-5s-vs-10s`）。
  - **TTS**：`qwen3tts_eval\.venv-qwen3tts\Scripts\python.exe diag_tts044_npu_switch.py --worker --arm turbo`。
- ✅ **用户自己的 v2.1 会话是「常驻但不干活」**：PID **4896**（`bridge_launcher.py --real --pipeline …`）
  ⇒ **CPU 增量 = 0.000 s / 10 s** ⇒ 按项目规则**不算干扰**（MEMORY 十一）。
- ⇒ **结论不变：APP-061 ①③④⑤ + ③(e) 的设备级数字仍未实测** ⇒ **不与 ASR/TTS 抢设备**
  ⇒ 等 ASR 释放 `MACHINE_LOCK` 且机器安静后跑 `python results/app/app223_app061_device_acceptance.py --run`。

#### ⑤ 🔴 **收尾复核（`CORRECTIONS_APP.md` 全程只读）**

* 开工基线：SHA256 `5ee74b79b38e139a875a14d44c82d05a1624ce35b4e693dac189fea683738502` / **168 827 B** / mtime **2026-11-01 21:50:01** / **61 条**。
* 收尾实测（2026-11-02 09:56 现场重算）：**与开工基线逐字相同** ⇒ **本轮 reviewer 未追加新条目** ⇒ 「SHA 零改动」在本轮**成立**（与 §125/§126「中途被追加」那两轮**不同**，勿混为一谈）。
* 本模块对 `CORRECTIONS_APP.md` **全程只读、未写入**。

#### ⑥ 🔴 **本轮新增待 reviewer 裁定（未自行改语义）**

① **共享锁闸门第 11 组的 AST 反证谓词恒真**（只认 `os.exists`、抓不到 `os.path.exists`）
⇒ 修它要动 **ASR/MT/TTS 共用**的 `machine_lock_app.py` ⇒ **仍未改**（§129 已留证，本轮未动）。
② **`lock_state()` 的 `stale_boot` 优先于 PID 存活判断** ⇒ 时钟异常会**抢活锁** ⇒ **仍未改**（§128 已留证）。
③ **本轮新增**：`app224` 的「值没变」判据现在**豁免 docstring** ⇒ 这是**判据口径的放宽**
⇒ **请 reviewer 确认这个口径**（行为承载常量仍严格判 ＋ 有 ⑧ 自检证明豁免没变成「什么都放过」）。

#### ⑦ 本轮交付

* **代码（只改开发版**，客户包一个字节都没动）：
  `live_caption/tts_worker.py`（**237 087 B** / SHA256 `c5ba36d11eb24281…` / 4 167 → 4 211 CRLF 行）。
* **验收脚本**：`results/app/app226_app061_cuda_fallback_ref.py`（新增）、
  `results/app/_app130_negative_test.py`（新增）、`results/app/_app130_probe_busy.py`（新增）、
  `results/app/_app130_probe_procs.py`（新增）、`results/app/_app130_cpu_delta.py`（新增）。
* **修改的既有脚本**：`results/app/app224_app061_escape_lock_gates.py`（判据口径 3 处 ＋ 自检 2 组）、
  `results/app/app215_app061_voice_clone_fix.py`（反证锚点缩进 ＋ ①b 判据作用域）。
* **证据**：`results/app/app226_app061_cuda_fallback_ref_evidence.json`、
  `results/app/app224_app061_escape_lock_gates_evidence.json`（**已重跑覆盖**，改判据后的新结论）、
  `results/app/app215_app061_voice_clone_evidence.json` / `app219…` / `app220…`（**计数与 §129 逐字相同**）。
* 🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**
  （v2.1、v2.2 目录与 zip **一个字节都没动**）⇒ **dev 树又变了 ⇒ 下一版必须打 v2.3**；
  **未提交任何 `CORRECTIONS_*.md`**。
