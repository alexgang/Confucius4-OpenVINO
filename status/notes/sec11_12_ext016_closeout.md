# §11 / §12 —— EXT-016 落地与收口（逐条明细）

> 本文件是 `status/STATUS_EXT.md` §11 / §12 的**明细全文**。
> ⚠️ **为什么在这里**：§15 落地后精简版 STATUS 涨到 **24 604 B**，
> 撞上 `tests/test_ext016_compression.py` 的「精简版 < 归档/10」硬断言
> （224 833 B / 10 = **22 483 B**）⇒ 按 **EXT-016 的写作规则**，
> **把逐条明细下沉到 notes**，而不是删内容。
> ⇒ §11 / §12 的结论仍在精简版 STATUS 里（骨架 + 关键数字），
> 逐条细节在这里；**归档 `status/archive/STATUS_EXT_upto_20261030.md` 里的 §1~§10 原文一字未删**。

---

## §12 EXT-016 收口（接手被中断的一轮）+ EXT-017②「2 秒内可见输出」补行为级验收（2026-10-30 21:06）

**依据**：闸门 `tools/next_instruction.py --json` → **exit 1**（`already_executed`，
latest=EXT-017 / last_ack=17）⇒ 按闸门应跳过；
但**交叉证据表明上一轮（EXT-016 压缩）被中断** ⇒ 按「接手未完成的轮次」处理，
**不认领新编号**（last_ack 保持 EXT-017）：

| 证据 | 正常做完 | 本轮实测（被中断） |
|---|---|---|
| `git status --porcelain` | 干净 | **脏**：staged rename + 3 个未跟踪文件 |
| 归档与精简版 | 都已提交 | `status/archive/STATUS_EXT_upto_20261030.md`（224 833 B）与 `status/STATUS_EXT.md`（11 043 B）**都没入库** |
| 新增自测 | 已入库 | `tests/test_ext016_compression.py` **未入库** |
| EXEC_LOG | 有该轮记录 | **无 EXT-016 记录**（最新仍是 2026-10-30 16:11 EXT-017） |
| 闸门解析 | — | 压缩后仍正常（exit 1 / latest=EXT-017）⇒ 压缩本身没坏闸门 |

⇒ **① EXT-016 收口**：归档原文与精简版**逐字节校验与 HEAD 一致**（`cmp` 通过）⇒ 只补提交，不重做。
`status/CORRECTIONS_EXT.md` **只读、未修改、未入库**（`.gitignore:34` 仍在）；
已关闭条目归档 `status/archive/CORRECTIONS_EXT_closed_upto_20261030.md`（23 067 B / EXT-001~EXT-014 全文）**入库**
（与 app/hy/tts 模块的同名归档做法一致）。

⇒ **② ★ 本轮抓到 2 个真缺陷**（都是上一轮 691 PASS 掩盖掉的）：

* **缺陷 29（★ 产品缺陷）`_caption_app_running()` 阻塞 start 4.208 秒**
  —— 旧写法 `psutil.process_iter(["pid","name","cmdline"])` 对**全部 369 个进程**取 `cmdline`
  ⇒ **实测 4.208 s** ⇒ `start()` 在这 4.2 秒里**什么都不显示**
  ⇒ **直接违反 EXT-017②「start 之后 2 秒内必须出现『正在加载模型…』」**。
  修法：① 先只取 `name`（实测 **0.005 s**）② 只对**候选**进程再取 `cmdline`（**0.003 s**）
  ⇒ **4.208 s → 0.0015–0.022 s**；⚠️ 候选名单必须含 python/pythonw ——
  App 是用自己的 `pythonw.exe` 跑的（`Start_LiveCaption.bat`）⇒ `live_caption` 只在**命令行**里。
  **检出正确性已验证**：有 live_caption 进程 ⇒ True（0.021 s）；杀掉 ⇒ False（0.006 s）。
* **缺陷 30（测试缺陷）`test_ext017_user_report.py` 假 FAIL**
  —— 固定端口 **18811/18812** + 固定 **8 s** 超时，而桥接冷启动**实测就要 5.0–5.7 s**
  ⇒ 只剩 ~2.3 s 余量 ⇒ 机器一忙就超时 ⇒ `terminate()` 把子进程**杀在启动途中**
  ⇒ 后面 3 条断言因拿不到日志而**一起**失败（4 条同时红）。
  **本轮首次批量跑就复现**（95 PASS / 4 FAIL），**HEAD worktree 复跑却是 99 PASS / 0 FAIL**
  ⇒ 判定为**冷启动抖动**（非回归），并据此定阈值。
  修法：端口改**动态分配**（`_free_port()`）；超时 8 s → **45 s**（是上限不是性能指标）；
  并**单独**加一条「冷启动耗时 ≤ 30 s」的性能口径（实测 5.28 s）。

⇒ **③ ★ 补上 EXT-017② 的行为级验收**（此前只有源码字符串检查 ⇒ 不能证明「用户真能 2 秒内看到」）：
新增 `test_launcher_feedback_within_2s()` —— 真跑 `BridgeRunner.start()`（用**桩命令**当子进程，
**不加载真模型、不占 GPU / NPU**）⇒ 实测 `start()` **4.244 s → 0.032 s**
（连跑 8 次 0.033–0.048 s，8/8 绿）✅ 满足 2 秒口径；
并断言「提示带 PID/端口/日志路径」「状态灯同步切到加载中」「子进程输出既转发到窗口**又**落进日志文件」。
配套改动：`tools/ext_launcher.py` 的 `BridgeRunner` 新增 **自测注入点**
（`cmd=` / `log_path=` / `pid_path=`）⇒ 默认 `None` ⇒ **生产路径完全不变**。

⇒ **④ 自测**：**13 套 / 739 PASS / 0 FAIL**（全 rc=0）：
echo_roundtrip 11 / ext009 57 / ext010 23 / ext011 29 / ext012 75 / ext013_compare 51 /
ext013_cpu_watch 25 / **ext016_compression 39** / **ext017_user_report 108** / browser_contract 102 /
selfcheck 103 / next_instruction 19 / p1_plumbing 97。

⇒ ⛔ 端到端仍不实时（TTS 稳态 RTF **1.0022**）⇒ **TTS 提速仍是上线的唯一前置**；
⛔ 浏览器端人工验收仍未做（tabCapture 需真实用户手势）⇒ **不宣称浏览器链路已验证**；
⛔ 本机无 Chrome（只有 Edge 126）；⛔ 未跑任何真实推理（本轮全程 CPU 侧，**未占 GPU / NPU**）。

---

## §11 EXT-016 落地（2026-10-30 19:05）

**依据**：闸门 `tools/next_instruction.py --json` → **exit 1**（`already_executed`，latest=EXT-017 / last_ack=17）
⇒ 无新纠偏；
但 **EXT-016（压缩 STATUS/CORRECTIONS）从未被认领**（§10 头部自注「EXT-016 压缩 STATUS 未认领」），
且 STATUS 仍 224 833 B ≫ reviewer 要求的 40 KB
⇒ 命中 **EXT-014 ②**（STATUS 仍有未完成项且本模块无进程在跑 ⇒ 直接继续下一项，不空转）。

**① STATUS 拆分**：`status/STATUS_EXT.md` → `status/archive/STATUS_EXT_upto_20261030.md`
（**224 833 B**，原样保留，不删内容）；
新建精简版 `status/STATUS_EXT.md`（头部 ≤ 15 行 + 当前有效结论表 + 未完成纠偏清单 + 最近 3 节，每节 ≤ 60 行）。

**② CORRECTIONS 压缩**：已完成的 EXT-001~EXT-014 全文 → `status/archive/CORRECTIONS_EXT_closed_upto_20261030.md`；
`status/CORRECTIONS_EXT.md` 只留顶部索引表（编号/一句话/状态）+ 进行中全文 + 最近 5 条全文（EXT-013~EXT-017）。

**③ 闸门压缩后仍正常**：`next_instruction.py` → exit 1 / latest=EXT-017（编号与标题格式未变，reviewer 推送工具仍可追加）。

**④ 自测**：新增 `tests/test_ext016_compression.py`（结构 / 大小上限 / 归档存在 / 闸门可解析 / 索引覆盖 / 标题格式）。
