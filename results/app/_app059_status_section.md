
## §59 🔴 巡检（APP-022 = `last_ack`，**本轮无新 APP 纠偏条目**）+ 🔴🔴 修「`submit()` 丢唤醒竞态 ⇒ 命令永久滞留 `_queue` ⇒ 该句永远不被朗读」（2026-10-27 03:26）｜**本条已完成**｜**已提交 `36e3d1e` 并推送**

### 59.1 巡检结论（无新条目）

| 项 | 实测 |
|---|---|
| `status/app/CORRECTIONS_APP.md` SHA256 | `682aced289a58d18b9303cffa6cc5a60dd21c83e226cfefa3d3f2171f81aea00` |
| 大小 / mtime | **48 457 B** / **2026-10-26 16:18:08** |
| `## APP-xxx` 条目数 | **22** |
| 最大编号 | **APP-022** |
| 头部 `last_ack` | **APP-022** |
| **编号差** | **0** ⇒ **不触发逐条执行** ⇒ `last_ack` **保持 APP-022** |

⇒ 本轮**无新 reviewer 纠偏条目**（**第 23 次**同一口径复核）；
该文件**全程只读、零修改**（§57/§58 巡检时 SHA 相同 ⇒ 逐位一致）。

### 59.2 🔴🔴 本轮修的缺陷：`submit()` 的**丢唤醒竞态（lost wakeup）**

#### 59.2.1 缺陷 A（主）：命令**永远发不出去**

`submit()` 旧实现把「读 `state`」与「登记在途 / 入队」拆成了**两个临界区**：

```python
with self.lock:                       # ① 临界区
    ...
    ready = (self.state == 'ready')   # ← 读状态
    dead  = (self.state == 'error')
...
else:
    with self.lock:                   # ② 临界区
        self._queue.append(cmd)       # ← 入队
```

而 `ready` 事件的处理**在锁外**改状态：

```python
if kind == 'ready':
    self.state = 'ready'              # ← 锁外
    self._flush_queue()               # ← 快照 _queue（当时可能为空）
```

⇒ **丢唤醒**（实测时序）：

| 时刻 | 线程 | 动作 |
|---|---|---|
| t1 | App | ① 锁内读到 `state == 'loading'` ⇒ `action='queue'` |
| t2 | 事件 | `state = 'ready'` ⇒ `_flush_queue()` ⇒ 快照 `_queue`（**空的**）⇒ 无事可做 |
| t3 | App | ② 入队 ⇒ 命令**留在 `_queue` 里** |

⇒ worker **已经 ready** ⇒ **再也不会有第二个 `ready` 事件**
⇒ `_flush_queue()` **永远不会再跑**
⇒ 这条命令**永远发不出去**
⇒ `pending[jid]` **永久悬挂** ⇒ `drain()` **必超时**（GUI 白等 30 s / CLI 白等 120 s）
⇒ 🔴 **用户可见后果：这一句译文永远不会被朗读**，且界面「提交」比「已播 + 丢句」多 1。

#### 59.2.2 缺陷 B（同源）：`_inflight` 登记与「孤儿清理」交错 ⇒ **幽灵在途句**

`_inflight.add(jid)` 也在**另一个**临界区 ⇒ 可与 worker 级 error 的
「孤儿清理」（`pending.clear()` + `_inflight.clear()` + 计丢句）交错
⇒ 交错后 `_inflight` 里多了一个**从未真正在途**的 jid（**幽灵**）
⇒ worker 崩溃时 `lost = sorted(self._inflight)` 把它算成「在途丢失」
⇒ `n_dropped` **双记** ⇒ 不变式破坏。

#### 59.2.3 与 §58 的区别（为什么这是**另一个**破口）

| 轮次 | 破口 | 命令**是否被下发** |
|---|---|---|
| §58 | `cancel()` **漏清 `_queue`** | **是**（被重新下发 ⇒ 主进程记错） |
| **§59** | `submit()` **丢唤醒** | **否**（根本没下发 ⇒ 永久滞留） |

两者都会破坏不变式，但**根因不同、修的位置不同** ⇒ 必须分别修。

### 59.3 ✅ 修法（`live_caption/tts_service.py`，**4 处**）

1. **读 `state` + 登记在途 + 决定「直接下发 vs 入队」合并到同一临界区**
   ⇒ 孤儿清理看不到半状态 ⇒ 杜绝缺陷 B；
2. **入队前在同一把锁内复查 `state`** ⇒ 若已 ready 则**自己下发**（不入队）
   ⇒ 杜绝缺陷 A；
3. **`_handle_event('ready')` 的 `state = 'ready'` 移进锁内**
   ⇒ 与 ② 的复查**互斥** ⇒ 「入队」与「补发」**不可能两边都错过**：
   - 复查看到 `'ready'` ⇒ `_flush_queue()` 的快照要么还没取（一定取得到我们的命令），
     要么已经取完（那它看到的是空队列 ⇒ 我们必须**自己**下发）；
   - 复查看到非 `'ready'` ⇒ `_flush_queue()` 必定在我们之后跑（它读 `state` 前我们已入队）⇒ 一定取得到；
4. **顺带补齐「worker 级 error 落在窗口内 ⇒ 不得入队」**
   ⇒ `_queue` 不再无上限增长；⚠️ 计数口径 = **只有该句此刻仍在 `pending` 里才计丢句**
   （否则与「孤儿清理」的计数重复 ⇒ 双记）。

### 59.4 ✅ 验收（`results/app/app089_tts_submit_lost_wakeup.py`）

**REAL 17/17 PASS**（桩 worker，**不跑推理 / 不测速 / 不占 GPU / 不取机器锁 / 不调 MiniMax**）。

🔴 **关键手法：确定性复现，不靠概率** —— 真实世界里那个窗口只有几微秒宽，
靠「多跑几次」抓不到 ⇒ 本脚本用**可注入的锁包装器**，在 `submit()` 的
**第一个临界区释放之后**（= 窗口的精确位置）**同步**触发 `ready` 事件
⇒ **每次都必现**。
⚠️ 触发点必须在**释放锁之后**：修复后 `_handle_event('ready')` 自己要取锁
⇒ 若在持锁时调用 ⇒ 直接自死锁（那正是修复后的**正确**行为）。

| 组 | 断言 | 结果 |
|---|---|---|
| A | 丢唤醒：命令**没有**滞留待发队列（`n_queue=0`） | OK |
| A | 不变式成立（无悬挂） | OK |
| A | 这句**真的被播出来了** | OK |
| A | `drain()` **正常返回**（`elapsed=0.00 s`，不超时） | OK |
| B | 幽灵在途句：孤儿清理与 `submit()` 交错 ⇒ 不变式成立 | OK |
| B | `_inflight` **无残留**（`inflight=[]`） | OK |
| B | 丢句数**恰好 1**（只算一次） | OK |
| C | 正常路径：worker 未 ready 时提交 ⇒ ready 后 **3/3 补发并播出** | OK |
| C | 不变式成立 / 待发队列清空 | OK |

**反证（固定 commit `421d2d0` 的源码，子进程跑同一场景）3/3 命中**：

| # | 断言（命中 = 预期成立） | 修复前实测 |
|---|---|---|
| D1 | 命令**永久滞留**待发队列 | `n_queue=1`（应为 0） |
| D2 | 这句**永远悬挂**（没播出、也没离开 `pending`） | `played=0` / `pending=1` |
| D3 | `drain()` **超时** | `drain_ok=False`，`elapsed=6.01 s` |

⚠️ 反证基线**用固定 commit SHA `421d2d0`**（= §58 的提交，本缺陷类别**尚未**修）
⇒ 提交后 HEAD 变成修复版也不影响反证。

**回归 11 个既有套件全部未回归**：
`app057` / `app086` / `app088` / `test_tts_drop_crash` / `test_tts_close_gui_quit` /
`test_tts_close_leak` / `test_tts_close_orphan` / `test_tts_error_isolation` /
`test_tts_exit_played` / `test_tts_restart_regression` / `test_tts_stderr`
⇒ 全部 PASS（REAL 全过 + 反证仍命中）。

**证据落盘**：`results/app/app089_tts_submit_lost_wakeup_evidence.json`
（`verdict="PASS"`、`real_fail=[]`、`baseline_commit="421d2d0"`）。

### 59.5 ✅ 客户包定点同步（**双副本纪律**）

- 🔴 **精确字符串替换 + 唯一命中断言**，**禁整目录覆盖**；
- 🔴 **不手抄代码** ⇒ `git show 421d2d0:` + `difflib` **自动派生**替换块
  ⇒ **8 块**全部唯一命中；
- ✅ **幂等**：复跑 `--check` = **ALREADY**；
- ✅ **包外备份**：`C:\Users\Trekker-PTL\pkg_backup_app_c152\tts_service.py.bak_20261027_032521`；
- ✅ **仓库 ⇄ 包** `tts_service.py` **SHA256 完全相同**：`db6f2412980184f99a1ba27cb9f8b3fa9829190bc79777ac2b5fda5de6c54a1f`
  / **80 036 B**（改前 73 481 B / `3fd812719bbb620998c1dc7f5d66f048f103947bb72266f6b01f2c5ac5af637f`）；
- ✅ **对包内那份单独跑同一套断言**：REAL **17/17 PASS** + 反证 **3/3 命中**
  （`--pkg C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.5`）；
- ✅ `check_internal_material.py --pkg <v1.5>` **PASS（命中 0）**。

#### 59.5.1 🔴 同步脚本自身踩的坑（已修，**记进下次巡检必读**）

🔴🔴 **包内是 CRLF、`git show` 出来的永远是 LF**
⇒ 推导出的替换块是 LF 文本 ⇒ 在 CRLF 的包内容里**命中 0 次**
⇒ 首版报「**纯新增块找不到唯一锚点**」（`FAIL-block-cannot-anchor`）。
⇒ 修法：**推导与匹配全程在归一化（LF）文本上进行**，
写盘时**还原成包原本的换行风格**（按 `pkg_bytes.count(b'\r\n') > 0` 判定）
⇒ 同步后仓库 ⇄ 包**逐字节 SHA256 相同**（含 CRLF 行尾，**1370 CRLF / 1370 LF**）。
⚠️ 教训：**「块数对得上」不等于「字节对得上」** ⇒ 必须做**归一化逐字节比对**。

### 59.6 git 提交

- commit **`36e3d1e`**（**4 个 App 职责内文件**）：
  `live_caption/tts_service.py`（修改）、
  `live_caption/sync_c152_to_pkg.py`（新增）、
  `results/app/app089_tts_submit_lost_wakeup.py`（新增）、
  `results/app/app089_tts_submit_lost_wakeup_evidence.json`（新增）；
- → `git push origin main` **普通快进** `6235df4..36e3d1e`（**未 force**）；
- 🔴 **`status/app/CORRECTIONS_APP.md` 未入暂存** ⇒ 远端 blob 仍是 `7082400b…`
  （**与 `421d2d0` 逐位一致** ⇒ reviewer 独占文件未被提交）；
- 🔴 **其它模块 465 项未提交改动全部保留在工作区**（**未吞**），
  含 `status/CORRECTIONS.md` / `live_caption/translator.py` / ASR `c0*.py` / `diag_c111_*` 等；
- ⚠️ 起点 `6235df4` 是**并发会话的 ASR §38 提交** ⇒ **未被吞**。

### 59.7 未推进（**均等 reviewer / 用户裁定**，本轮**未擅自推进**）

① 🔴 **APP-022 集成阶段**需等 **ASR-013 + TTS-019** 交付（§55 只做接口预留，**未集成**）；
② 🔴 **APP-021 验收 C** 仍需用户配合（交互会话 + 音量 ≥ 50% + 戴耳机/外放
⇒ 先点「🔊 测试声音」再点离线朗读念一句 ⇒ 回填会话日志路径与遥测行）；
③ 🔴 **v1.5 zip 未重打**（守 **APP-020**：等 `cp_prefill` 同步后的最终版 + 机器锁）
⇒ 🔴 **不写「已交付」**；
④ 🔴 **散包目录仍有第三方素材残留**（babelvox speakers **8** + scipy 测试音频 **22**）
⇒ `pkg_exclude.py` 的排除规则**已在**（APP-018② / APP-019），
但**散包目录未物理清理** ⇒ 需重打时由规则覆盖；
⑤ 🔴 **术语表 / `packaging` 默认值待用户决定**（MT 通知 14 建议：`packaging` 放可选集
⇒ 属 App 默认值 ⇒ 本轮**未擅自改**）；
⑥ 🔴 §45.6①–⑤ / §44 `MAX_SEG_SPAN=2` / §49.7 / §46.5 / §42.3 / MT 通知 13 回复
⇒ **均等裁定**；⑦ ⛔ **FTP 仍关闭**（守 APP-009③）；⑧ ⛔ 包体优化未做（用户已接受）。

## 🔴 下次巡检必读（本轮新增）

- 🔴🔴 **「读状态」与「据此行动」必须放在同一把锁内** —— `submit()` 拆成两个临界区
  ⇒ 与事件线程的「状态转换 + 补发」形成**丢唤醒**窗口
  ⇒ 命令**永久滞留队列** ⇒ 永远不被朗读、且 `drain()` 必超时。
  ⇒ 通用判据：**任何「先看状态、再决定做什么」的代码，检查这两步是否原子**。
- 🔴🔴 **丢唤醒的另一半在事件侧**：`_handle_event('ready')` 的状态赋值
  **必须在锁内** ⇒ 否则它与「入队临界区」之间的窗口依旧存在
  ⇒ **两侧都改**才闭合（复查 + 锁内置状态）。
- 🔴 **注入式复现优于概率式复现**：真实竞态窗口只有几微秒宽
  ⇒ 「多跑几次」抓不到 ⇒ 用**可注入的锁包装器**在**精确位置**同步触发事件
  ⇒ **每次必现**、证据可复现。
- ⚠️ **注入点必须在「释放锁之后」** —— 修复后事件处理自己要取锁
  ⇒ 在持锁时调用 ⇒ **自死锁**（那是修复后的**正确**行为，不是脚本 bug）
  ⇒ 第一版脚本就是这么挂死的（跑满 5 分钟被 kill）。
  ⇒ 教训：**测试脚本被修复后的行为「卡死」时，先分清是「脚本写错」还是「修复生效」**。
- 🔴🔴 **包内 CRLF vs `git show` 的 LF** ⇒ 替换块**命中 0 次**
  ⇒ 报「纯新增块找不到唯一锚点」（**误导性报错**，真因是换行不匹配）。
  ⇒ 同步脚本必须**全程归一化匹配 + 写盘还原**；
  ⇒ 验收判据 = **归一化后逐字节 SHA256 相同**（不是「块数对得上」）。
- 🔴 **`self.lock` 是非可重入 `threading.Lock`** ⇒ `_handle_event` 里
  **绝不能**在持锁状态下再取锁（自死锁）⇒ `state='ready'` 的 `with` 块
  与 `_flush_queue()` 必须**分开**（后者自己取锁）。
- 🔴 **「worker 级 error 落在窗口内」也要堵**（不只是 `ready`）
  ⇒ 否则那句会入队 ⇒ worker 判死后**永不再 ready** ⇒ 永久滞留 ⇒ `_queue` 无上限增长。
- 🔴 **计数口径**：窗口内定案的句子，**只有它此刻仍在 `pending` 里**才计丢句
  ⇒ 否则与「孤儿清理」的计数**重复** ⇒ 又一次双记。
- ✅ **同步脚本沿用 `git show` + `difflib` 自动派生**（不手抄代码）
  ⇒ 8 块全部唯一命中 ⇒ **禁整目录覆盖**的双副本纪律仍然成立。
