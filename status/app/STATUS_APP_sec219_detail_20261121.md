# §219 · APP-119 执行详情（companion）

> 活文档只留标题行 ＋ 指针行（APP-052④：正文放 companion）。
> 本文件对应 `status/app/STATUS_APP.md` 的 **§219** 一节。
> 写入时间：**2026-11-21 04:34:48**（Get-Date 实测）｜执行轮次：App 模块巡检自动化 · 接续上一会话（TAKEOVER）。

## 〇、本轮来源与执行口径

- 🔴 **纠偏来源双通道**：局域网 `status/app/CORRECTIONS_APP.md` **118 条 / max APP-118**
  （**无 APP-119**）＋ **QQ 邮箱**白名单 `alexchen7694@agent.qq.com` 的
  `[C4][A][CORRECTION][APP] APP-119`（`msg_m2KGjpprMhxfEjquuAyYsmzzzdaBx96mAQziBhMQewslDw`，
  created_at **2026-11-20T14:15:11Z**）
  ⇒ 按 **T-MAIL-002**「同一编号两边都收到只执行一次」⇒ **邮件是本条唯一来源**，执行了 **1 次**。
- 🔴 **接续上一会话**：本轮 `session_lease.py acquire app` 返 **TAKEOVER**
  （上会话 token `5dda28b6`，last_beat 11-21 02:05，已死 61 min）
  ⇒ 从断点继续：上会话已做完 §1 默认/迁移/删互斥（迁移判据 15/15 PASS）与 v2.5 同步，
  **死在验收臂跑一半** ⇒ 本轮接管后**补完验收 ＋ 修掉一个真缺陷 ＋ 复跑**。
- 🔴 **APP-119 §4 巡检纪律**：本轮**有**新纠偏 ⇒ 正常写 §219 章节 ＋ 正常提交 git；
  **不打包**（§3 明令「先不打 zip」）⇒ **v2.5 目录已更新、zip 未打**。

## 一、§1 出厂默认（ASR=GPU.0 ／ MT=GPU.0 ／ TTS=NPU）

- 🔴 **出厂默认改成**：`ASR=GPU.0`／`MT=GPU.0`／**`TTS=NPU`**
  （**取代** APP-099 0.1 的「完整版 TTS=GPU.0」；**ASR 模型仍是 R2T2 1.7B**，不改）。
- 🔴 **代次提升**：完整版 `defaults_version` **9 → 11**
  （`CONFIG_DEFAULTS_VERSION_FULL=11`）；**MiniMVP=9 / SpecialMVP=10 不变**
  ⇒ 代次只在**同一 profile 内**比较 ⇒ **不影响**其它两种包形态的用户选择。
- 🔴 **迁移判据（值判据，不是代次判据）**：
  * `defaults_version >= 11` ⇒ **一律信任**（用户手动选过的保持不变）；
  * 代次更旧 ⇒ 只有当**三个键整体等于上一代出厂默认**（GPU.0/GPU.0/**GPU.0**）
    ⇒ 才迁移到新默认；
  * **已知局限**（写在迁移提示里）：「旧代次里用户手动把 TTS 选成 GPU.0」
    与「出厂默认 GPU.0」**无法区分** ⇒ 统一按旧默认迁移（reviewer 对 MiniMVP 同款口径）。
- 🔴 **迁移写进日志/提示**：`stale_device_note()` 产出说明 ⇒ CLI 的 `[device] …` 与
  GUI 状态条都能看到；提示文案含「没有手动改过 ⇒ 按 APP-119 §1 迁移」等口径。
- 🔴 **README / 界面 / device_config 三处一致**：
  `README_zh.md` §5「出厂默认改为『语音输出走 NPU』＋ 取消 NPU 独占限制（APP-119）」
  ＋ `README_en.md` 对应段 ＋ `device_config.DEFAULT_DEVICES`（**唯一事实来源**）。
- 🟢 **迁移判据实测**：**15 / 15 PASS**（`app119_migration_test.json`，
  `result=PASS`、`n_fail=0`）—— 覆盖：旧出厂默认只迁 tts／新代次不迁／
  手动改过保持不变／迁后手动选回保持不变／无代次残留旧配置迁移／无配置用新默认／
  完整版代次=11／MiniMVP 与 SpecialMVP 不受影响 等。

## 二、§2 设备自由配置（取消 NPU 互斥）

- 🔴 **删掉**强制规则「MT 与 TTS 不能同在 NPU ⇒ 自动把 MT 挪到 GPU.0」：
  * `_enforce_no_npu_conflict()`（GUI+CLI）**整体删除**；
  * `_sync_mt_combo_to_gpu0()`（把翻译下拉强行指回 GPU.0）**整体删除**；
  * 启动时读 `device_config.json` 的 D4 冲突处理**删除** ⇒ 用户写的组合**原样生效**。
- 🔴 **不再自动改用户的选择**：GUI 选 MT/TTS 设备、CLI 的 `--asr-device`/`--mt-device`/
  `--tts-device`、`device_config` **一视同仁，不加限制**；
  **任意组合都允许，包括三个模块全部放在 NPU**。
- 🟢 **黄色警告不再阻止任何操作**：保留**一条不阻塞**的性能提示
  （`_npu_conflict_note()`：NPU 共用 ⇒ 合成可能慢 25–30 %），**挂在语音输出（TTS）状态条**上；
  **APP-117 的全局状态灯没有被加回来**。
- 🔴 **失败必须显式报错**：编译失败 / NPU 内存不足 ⇒ 由各模块状态条
  （`tts.stats()['last_error']` / `mt.err`）**显式报错 ＋ 写日志**；
  **绝不静默换设备**、**不启动崩溃**。
- 🔴 **回退链仍不含 NPU**（ASR/MT 只在 GPU.x → CPU 之间回退）：
  回退只在「**用户选的设备本机根本不存在**」时发生 ⇒ 落到 NPU 等于把模块
  悄悄挪到用户**没选的设备**上 ⇒ 与「绝不静默换设备」直接冲突。
  🔴 **理由已更新**：APP-028① 当年排除 NPU 的理由是「NPU 独占给 TTS」
  ⇒ 该理由**已随 APP-119 §2 作废**，但**结论保留**（理由换成上面那条）。

## 三、§3 验收（三臂）

### 臂 1 · 新出厂默认（ASR=GPU.0 ／ MT=GPU.0 ／ TTS=NPU）—— **必须 PASS**

🟢 **PASS（14 / 14 项检查全过，`n_fail=0`，`verdict=PASS`，`rc=0`）**
—— 证据 `results/app/app119_default_summary.json` ＋
`results/app/app591_acceptance_app119_default_run20261121-032253.json`

| APP-119 §3 的 PASS 口径 | 实测 | 判定 |
|---|---|---|
| **不丢句** | 丢句（任何原因）= **0**（worker丢弃 0 ＋ 溢出丢弃 0 ＋ worker失败丢弃 0） | 🟢 PASS |
| 译文 == 进 TTS ＋ 丢弃（无其它丢失路径） | **150（译文）== 150（进 TTS）+ 0（丢弃）** | 🟢 PASS |
| **语速上限 1.7×** | max = **1.4368**（p50 1.1／p95 1.416） | 🟢 PASS |
| **积压可控** | 积压峰值 **88.805 s** ⇒ 收尾**排空到 69.635 s**；**一句不丢** | 🟢 PASS（见下「🔴 诚实口径」） |
| 报告 `synth_rtf` P90 | 中位 **0.9656** ／ **P90 1.0604** ／ max 1.1273 | 报告项 |
| 报告总延迟 | 整链 **678.3 s**（600 s 片段）；TTS 就绪 **11.0 s**；ASR 就绪 5.3 s；MT 就绪 7.2 s | 报告项 |

🔴 **诚实口径（两条，不粉饰）**：
1. **`timing_valid=false`** —— 唯一原因是 **synth_rtf P90=1.060 > 0.75（合成 RTF 异常 ⇒ 机器被占） ⇒ **计时类结论不成立**（计数类结论不受影响）**。
   🔴 但**锁全程未被抢**（看门狗 67 采样／非本作业变动 0 次）、**外部写入 []**、
   **运行前后 GPU 占用列表逐项相同** ⇒ **计数类结论（150==150／丢弃 0／语速上限）成立**，
   **计时类结论按 APP-115 口径作废**（本机 NPU TTS 达不到 0.75 那条线）。
2. **NPU TTS 比 CUDA TTS 慢**：本臂 `synth_rtf` 中位 0.9656，
   而 §217 的 CUDA 档是 **0.63** ⇒ **新默认（NPU）能跟上实时但不宽裕**
   ⇒ 积压峰值 88.805 s、收尾才排空。
   🔴 这是 **NPU 档位本身的特性**，不是 v2.5 回归（对照：旧默认「全 GPU.0」是
   RTF≈4.4 ⇒ 积压 917 s ⇒ **FAIL**）。

### 臂 2 · 极限组合（三模块全 NPU）—— 只需「能启动、不崩、不静默换设备」

🟢 **reviewer 给这一臂的 PASS 口径三条全达成**（能启动／不崩／不静默换设备）；
🔴 **但验收脚本的总判 = FAIL**（`n_fail=1`）
—— 🔴 **唯一 FAIL 项是「ASR/TTS 并行生效（并行=on）」**：
all-NPU 时 **ASR 与 TTS 同在 NPU** ⇒ 按**新判据「同卡才串行」**
⇒ **本来就该串行、且确实是串行** ⇒ 这一项**属设计内**，
**不是缺陷、不是静默换设备**（本臂 PASS 条件里也**没有**这一项）。
证据：`results/app/app119_allnpu_summary.json` ＋
`results/app/app591_acceptance_app119_allnpu_run20261121-040755.json`
- **能启动**：ASR=NPU／MT=NPU／TTS=NPU 三个模块**全部落在 NPU**，
  日志里各模块的**实际设备 == 所选设备** ⇒ **没有静默换设备**
  （🔴 日志里「自动改到 GPU.0」出现次数 = **0**）。
- **不崩**：进程 rc=0 收尾，无启动崩溃。
- 如实记录（**不作为 PASS 条件**）：`synth_rtf` 中位 1.065 ／ P90 1.3228 ／
  max 1.6232；丢句 **0**；就绪前排队 4；TTS 就绪 11.5 s；
  积压峰值 178.163 s；整链耗时 758.0 s。
- 🔴 **NPU 编译时间**：ASR `1.7` s（`[asr06b_npu_int8] 加载 … s`）、
  翻译 `2.4` s（`翻译模型就绪（… · NPU，加载 … s）`）、
  TTS 引擎 `5.7` s（`[tts_engine] 模型加载完成（… s）`）、
  TTS worker `8.3` s（`[tts_worker] 模型加载完成 …s`）。
- 🟢 **进程内存**（**Windows 工作集**口径，并行采样 152 次）：包内 python 进程
  **合计峰值 8891.4 MiB** ／ **单进程峰值 4815.5 MiB**
  （采样到 3 个包内进程；证据 `results/app/app119_allnpu_memprobe.json`）。

### 臂 3 · 混合组合冒烟（ASR=NPU ／ MT=NPU ／ TTS=GPU.0）

🟢 **PASS**（`results/app/app119_mixed_smoke.json`，
`9` 项检查 / `n_fail=0`；rc=0、耗时 187.5 s）：
选中 **ASR=NPU ／ MT=NPU ／ TTS=GPU.0**，60 s 片段
- **ASR 实际设备 = NPU**（`[asr06b-stateful] EXECUTION_DEVICES：encoder=NPU，decoder=NPU`）
- **MT 实际设备 = NPU**（`[asr06b_npu_int8] 翻译 target=zh 后端=auto 设备 NPU`）
- **TTS 实际设备 = GPU.0**（`[tts_engine] EXECUTION_DEVICES talker=GPU.0，cp_prefill=GPU.0，
  cp_decode=GPU.0，decoder=GPU.0` ＋ `实测执行设备：GPU.0`）
- 🔴 **最关键的一条**：**MT 没有被自动挪到 GPU.0** ⇒ **APP-119 §2「不再自动改用户的选择」
  在混合组合下实证成立**（旧 D4 规则在这里会强制改设备）。

## 四、🔴 本轮修掉的**真缺陷**：并行加载判定把「CUDA」写死

🔴 **现象**：臂 1 的**第一次跑**（`run20261121-030855`）**唯一 FAIL 项**是
「ASR/TTS 并行生效（并行=on）」⇒ `parallel=False`；其余 14 项全过
（`n_fail=1`）。

🔴 **根因**：APP-113 §2 的「ASR 与 TTS 并行加载」判定写死成
**「TTS 档位 == CUDA」**（`live_caption_app.py` 的 CLI 侧 `_tts_parallel` 与 GUI 侧
`__init__` 同一处），理由是「**同一张卡上并行编译会把 GUI 卡死**」。
🔴 **但 APP-119 §1 把完整版出厂默认改成 `TTS = NPU`** ⇒ 默认配置是
`ASR=GPU.0` ／ `TTS=NPU` ⇒ **本来就是异卡**，却因为「TTS 不是 CUDA」
⇒ **默认配置被静默地永远串行** ⇒ **默认配置白丢 APP-113 §2 的并行收益**。

🔴 **修法（不弱化判据，改产品）**：判定从「TTS 是不是 CUDA」改成
**「ASR 与 TTS 是否同一张加速卡」**（新增 `_accel_class()` / `_same_accel()`）：
- **同卡**（GPU↔GPU、NPU↔NPU）⇒ **串行**（沿用「auto=False 防编译死锁」，**原行为不变**）；
- **异卡**（GPU↔NPU、GPU↔CUDA、NPU↔CUDA）⇒ **允许并行**（各编各的卡，无同卡死锁）；
- **任一未知** ⇒ 🔴 **保守当同卡**（保持原串行行为）。
- 🔴 **只改加载顺序**，**不改任何模块的落点**，**不引入任何设备限制**。

🟢 **行为级判据（9/9 PASS ＋ 反证组）**：`_same_accel()` 的真值表逐条跑通
（GPU.0/NPU⇒并行、NPU/NPU⇒串行、NPU/GPU.0⇒并行、GPU.0/GPU.0⇒串行、
GPU.0/CUDA⇒并行、GPU.1/GPU.0⇒串行、空⇒串行 …）；
🔴 **反证组**：把 `_same_accel` 换成「恒 False」（= 老实现恒当同卡）
⇒ 被 **5 条**用例识破 ⇒ 判据**有鉴别力**（不是恒真恒假）。

🟢 **复跑实测（`run20261121-032253`，同一脚本、同一命令、同一 600 s 片段）**：
**14 / 14 全 PASS**，`parallel=**True**`；
🔴 **TTS 就绪 20.4 s → 11.0 s（省 9.4 s）**；
**就绪前排队 0（原 4）**；
`play_lag_max` **106.711 → 88.805 s**；`play_lag_end` **84.771 → 69.635 s**；
`synth_rtf` 中位 0.9881 → 0.9656／P90 1.0731 → 1.0604；
整链 695.4 → 678.3 s；锁看门狗 69 采样／非本作业变动 0 次 → 67 采样／非本作业变动 0 次。

## 五、包同步证据（v2.5；**不打 zip**）

- 🟢 `device_config.py` ／ `live_caption_app.py` 与 dev 树**逐字节一致**
  （证据 `results/app/app119_sync_v25_evidence.json` ＋ `..._r2.json`：
  `identical_to_dev=true`、写前写后 `ast.parse` 自检过、临时文件 → `os.replace` 落盘）。
- 🟢 **包文件数 48790**（两轮同步前后一致 ⇒ 没有误删/误改）。
- 🟢 **README_zh / README_en** 的 APP-119 口径**只读核对通过**（`needles_ok=true`）。
- 🔴 **v2.4 / rc11 / sp5 逐字节未动**（`device_config.py` 与 `live_caption_app.py`
  的 SHA 与 mtime 均早于本轮；sp5 = `847f825a…`／`0572bfd0…`，与上一轮记录一致）。
- 🔴 **未打 zip**（APP-119 §3 明令「**先不打 zip**」；用户长期规则「不通知 ⇒ 不打包」）。

### 🔴 包上自检发现的**上一轮遗留违规**（本轮已修）

🔴 **APP-119 §3「包上自检照旧」⇒ 跑 `assert_pkg_clean.scan(v2.5)` ⇒ 命中 1 项违规**：
`ext/bridge_token.txt`（32 B，mtime 2026-11-20 18:13）
⇒ 命中 `PKG_EXCLUDE_PATTERNS: (?i)(^|/)bridge_token\.txt$`
⇒ **APP-077 ① 明令「固定鉴权 token 不得进客户包」**。
- 🔴 **根因**：**§217 那轮换嵌 EXT v0.4.18 时把它一起拷进了 v2.5 包目录**
  ⇒ 上一轮 11-20 16:18 的模型身份核验（**早于 18:13 的换嵌**）查不到它
  ⇒ **本轮是第一次在换嵌之后跑洁净度闸门**。
- 🔴 **zip 闸门查不到它**（`pack_v13.py` 用 `pkg_exclude.iter_package_files()`）
  ⇒ 只有**包目录**闸门能查出来（这正是 `assert_pkg_clean.py` 存在的理由）。

🟢 **本轮处置（v2.5 未交付给用户 ⇒ APP-119 明确允许重新生成该目录）**：
- 🔴 **改名挪到包外**（**不删除**；本机删除被安全删除 shim 拦）：
  `v2.5/ext/bridge_token.txt` → `results/app/_pkg_v25_removed_bridge_token_20261121.txt`
  （32 B／sha `bc25a408…`／原 mtime 2026-11-20 18:13:43）。
- 🟢 **功能零影响（已证）**：`ext/bridge/bridge.py` 的 `TokenStore._load_or_create()`
  **文件不存在时自己生成** `secrets.token_urlsafe(24)` ⇒ 该文件**不是预置载荷**。
  ⇒ 🟢 **EXT 冒烟复跑 7 PASS / 0 FAIL**（`results/app/app118_ext_smoke_evidence.json`
  ⇒ A3 /health 200、A4 /status 200、A5 /pair 契约、A6 端口被占拒绝启动 rc=6、A7 互斥检查）
  ⇒ **移除后 EXT 桥照常工作**。
- 🟢 **洁净度闸门复跑：0 违规**（`python live_caption/assert_pkg_clean.py <v2.5>` ⇒ PASS）。
- 🔴 **但「桥接自己会生成这个文件」是必须写清的一条**：
  🔴 实测 **EXT 冒烟跑完后** `ext/bridge_token.txt` **又被生成了**
  （mtime **2026-11-21 04:28:02**、内容＝一串**新随机** token
  `M62uqacuZKo24c8yPBaoyPufyLu7z8KX`）⇒
  ① **交付时不得带预置 token**（APP-077 ①，已挪出），
  ② 但**包一旦被运行过**，**目录**洁净度闸门就会命中这个**运行时产物**
  ⇒ 这是**闸门与运行时行为的已知交互**，**不是**「随包交付了凭据」
  ⇒ 本轮已把运行时生成的那一份也**改名挪出**
  （`results/app/_pkg_v25_runtime_token_20261121_0428.txt`，32 B／sha `ca1cc29c…`）
  ⇒ **交付目录当前 0 违规**。
- 🟢 **模型身份核验照旧全过**：21 个模型组**全量 SHA 逐文件相等**
  （含 `cuda_env` 34 126/34 126 文件）、0.6B decoder bin SHA = `0059531a…`、
  R2T2/0.6B/MT/TTS-OV/TTS-CUDA 全部覆盖（证据 `results/app/app118_model_identity_evidence.json`）。
- 🔴 **包文件数因此 48789**（比换嵌后少 1 个＝被挪出去的那个 token 文件）。

## 六、未结项 / 纪律

- ⓿ **预设 B（男声）等 reviewer 联网后拉给用户抽听** ⇒ **在此之前仍不进包**
  （APP-119 开头 ②；沿用 APP-116 §2）。
- ⓿ **预设 A/B 都不进 v2.5**（§217 的结论不变）。
- ⓿ **v2.5 zip 等用户通知**才打。
- 🔴 **APP-109 ④ 仍然有效**：本轮**没有连接 B 机**（无 ping / 无 ssh 探测）；
  §218 里「A 机已离开 192.168.2.0/24」的推断**不再追**（B 机的事由 reviewer 处理）。
- 🔴 **`status/app/CORRECTIONS_APP.md` 只读**：本轮**一个字都没改**（收尾复核 SHA 逐字一致）。
- 🔴 **未跑 MiniMax**（质量判定由 reviewer 回转写）；**未占他模块的锁**。

## 七、本轮产物清单（文件数 / mtime / 字节数 / SHA256 见各 json 内的原始字段）

| 产物 | 说明 |
|---|---|
| `results/app/app119_migration_test.json` | 迁移判据 15/15 |
| `results/app/app119_sync_v25_evidence.json` | v2.5 首轮同步（含 README 定点替换） |
| `results/app/app119_sync_v25_evidence_r2.json` | v2.5 二轮同步（并行判定修复后的 .py） |
| `results/app/app119_default_summary.json` + `app591_acceptance_app119_default_run20261121-030855.json` | 臂 1 **第一次跑**（唯一 FAIL＝并行） |
| `results/app/app119_default_summary.json` + `app591_acceptance_app119_default_run20261121-032253.json` | 臂 1 **复跑**（14/14 PASS） |
| `results/app/app119_allnpu_summary.json` + `app591_acceptance_app119_allnpu_run20261121-040755.json` | 臂 2 极限组合 |
| `results/app/app119_mixed_smoke.json` + `app119_mixed_run.log` | 臂 3 混合组合冒烟 |
| `status/app/STATUS_APP_sec219_detail_20261121.md` | 本 companion |

---

> 🔴 **本条需等 reviewer 复核**（§219）。
