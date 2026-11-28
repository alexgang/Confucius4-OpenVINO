# STATUS_APP §250 — 六通道复核（**无新 App 纠偏**，`last_ack` 仍 **APP-157**）＋ 🔴 接续上一会话（TAKEOVER）⇒ **闭合 §250 断点** ＋ 🔴 修掉 **§249 终检的 4 处判据缺陷**

> 生成时间：2026-11-28 13:24:58（`Get-Date` 实测）
> 本轮性质：**接续轮（TAKEOVER）**——上一会话（token `a958b358`，11-28 10:35 起、11:43:47 最后心跳）在**写完 §250 的脱敏动作后**心跳超时 ⇒ 本轮从其断点**继续**，不从头重做。
> **`last_ack` 不变**（仍 **APP-157**）：六通道复核 ⇒ **无编号 > APP-157 的新条目**。
> 🔴 本节按纪律**只追加**，不回头改旧章节；`status/app/CORRECTIONS_APP.md` **一字未改**（§7 收尾指纹）。

---

## §0 本轮顺序与依据

1. **第 0 步租约**：`session_lease.py acquire app` ⇒ **exit 0 / TOKEN=8a7eb339**，输出 **`TAKEOVER stale lease`**
   （旧 token `a958b358`／started 11-28 10:35:54／last_beat 11-28 11:43:47＝**83 min 前**／`alive=False`／`live_pids=[]`）
   ⇒ **上一会话已死** ⇒ 按纪律「先读它留下的 note、STATUS 和产物，**从断点继续**」。
   ⇒ 它的 note ＝ `§250脱敏已应用+行为等价验证通过(stdout/stderr/rc还原后逐字相等)`。
2. **六通道复核** ⇒ **无新纠偏**（§1）。
3. **核 §250 断点**：读死会话留下的全部产物 ⇒ 发现**「行为等价验证通过」这句结论没有落盘证据**（§2）⇒ 本轮**独立重算**（§3）。
4. 🔴 **查出 §249 终检的 4 处判据缺陷** ⇒ §250 的成立前提被推翻 ⇒ 修掉并重做（§3、§4）。
5. 写 STATUS §250 ⇒ 提交（App 侧文件）⇒ 发 STATUS 邮件 ⇒ 收尾指纹（§6、§7）。

---

## §1 六通道逐通道证据（⇒ **无新 App 纠偏**）

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| 1 | **局域网** `status/app/CORRECTIONS_APP.md` | **46 642 B**／sha256 `cc1067b7c4908e1583d7b6537f4f1c6e01b8a3831f1996f7272c0682f517ebae`／mtime 2026-11-27 15:08:17／`## APP-xxx` **15 条**／max **APP-157** | 与 `last_ack`(=APP-157) **相等** ⇒ **无新条目** |
| 2 | **QQ 收件箱**（`after=2026-11-27T00:00:00Z`） | **1 封**：`msg_8s6eELs8zrm5Euqkw7cI5tyTsOivbUwHdDGzjWyDShX62Q`（2026-11-27T07:08:16Z）＝ **APP-157**（＝`last_ack`，**已执行**） | **无新 App 纠偏** |
| 3 | **QQ spam**（`after=2026-11-20`） | 空（`data: []`） | 无 |
| 4 | **QQ trash** | 1 封：`MiniMVP rc9 Complete Performance Report`（2026-11-13，**与 App 纠偏无关**） | 无 |
| 5 | **agent-mail** | `{"status": "not_bound"}`（与前几轮相同，**该通道本会话不可用**） | 不适用 |
| 6 | **全库检索** `APP-1(5[89]|[6-9][0-9])` | 命中 4 处，**全部**是 `status/app/STATUS_APP_sec233/234/235/249_detail_*.md` 里的**「APP-178」历史注释**（别的模块编号，2026-10-31） | **无新 App 纠偏** |

**⇒ 六通道一致：`last_ack` 仍 = APP-157，本轮不执行任何新编号。**

---

## §2 死会话的 §250 断点：结论与证据**对不上**（🔴 本轮的第一个真缺陷）

死会话留下的 §250 产物（mtime 全部实测）：

| 产物 | mtime | 状态 |
|---|---|---|
| `.tmp_recover_app/_app250_redact.py`（脱敏施加脚本） | 11-28 11:35 | 在 |
| `results/app/app250_redact.json`（脱敏动作证据） | 11-28 11:42 | 在，**11 文件 / 19 处** |
| `results/app/app250_sites.json` / `app250_idxmap.json` / `app250_indep_scan.json` | 11:00 / 10:41 / 10:50 | 在 |
| `results/app/app250_fullscan.json`（全范围扫描，296 552 B） | 11-28 08:40 | 在 |
| 🔴 **`results/app/app250_behavior.json`**（行为等价的**最终证据**） | — | **不存在** |
| `results/app/app250_patch.json`（`app250_patch_desen.py` 的 OUT） | — | **不存在** |

🔴 **缺陷①（死会话的结论缺落盘证据）**：
死会话 note 写「**行为等价验证通过**(stdout/stderr/rc 还原后逐字相等)」，
但 `app250_behavior.py` 的 `OUT = results/app/app250_behavior.json` **从未产出** ⇒
**该脚本的「after」阶段根本没跑完** ⇒ 「通过」这句结论**没有可核验的证据**。

🔴 **缺陷②（死会话的判据选错 ⇒ 假 FAIL）**：
死会话留下的 `shared/app250_behavior_base/full_before.json` vs `full_after.json`
⇒ 直接比**原始输出** ⇒ 4 个脚本里 **3 个显示 DIFF** ⇒ 按它的口径会判「行为变了」。
真相：那 3 处 DIFF **全部是脱敏本身要造成的文本替换**（占位符 vs 原句）＋ **易变字段**
（`generated_at` / `elapsed_sec`）⇒ **判据选错 ⇒ 假 FAIL**，不是产品缺陷。

🔴 **缺陷③（死会话的解释器选错 ⇒ 假 PASS）**：
`app250_behavior.py` 对所有脚本用 `py`（系统 **3.13**，**无 numpy**）
⇒ `live_caption/diag_c111_half.py` **直接 ModuleNotFoundError 崩溃**
⇒ before/after **两边都 rc=1** ⇒ 「rc 相同」变成**空洞恒真**。
🔴 且它的 `JOBS` 里 `app053_draft_prefix_boundary_probe.py` **压根没有备份文件**
⇒ 那一项**无法比对**，却被算进分母。

🔴 **缺陷④（§222 入库完整性缺口）**：
§250 的**全部产出脚本**（`app250_fullscan.py`／`app250_provenance.py`／
`app250_patch_desen.py`／`app250_behavior.py`／`_app250_redact.py` 等）
**全部 untracked** ⇒ **干净 clone 跑不出 §250 的任何结论**。

⇒ **本轮处置**：不采信死会话的结论，**从零独立重算**（§3），并把脚本**入库**（§5）。

---

## §3 🔴 本轮的核心发现：**§249 终检的 4 处判据缺陷**（⇒ §250 的成立前提曾被推翻）

死会话的 §250 是为修「**§249 的『残留 0』是假绿**」而起的。查 §249 的终检脚本
（`.tmp_recover_app/_app249_verify_desen_final.py`）⇒ **确认 §249 的『残留 0』是范围受限的假绿**：

| # | §249 判据缺陷 | 实测 | 后果 |
|---|---|---|---|
| **D-1** | §249 §1 残留扫描只扫 **6 个文本扩展名**（`.md/.json/.txt/.tsv/.csv/.jsonl`） | **`.py` / `.bak` / `.c027bak` 从未被扫过** | 「残留 0」**不覆盖代码文件** |
| **D-2** | §249 §1 扫描**跳过** `SKIP_SUFFIX = ('.transcript.txt', '.mt.txt', '.tts.jsonl')` | 这 3 类后缀**恰好是 39 个 GT 源文件的后缀** | 跳过它们是**必须的**（否则 GT 自指），但**必须单独统计** |
| **D-3** | §249 §1 判据是「**整句相等**」 | GT 句**嵌在更大句子里**时判不出 | §249 已用「归一化+索引映射」在 apply 侧修掉，**但扫描侧仍是整句** |
| **D-4** | §249 的「还原式复核」按**替换后长度**定位 | 行数变会错位 ⇒ **假 FAIL** | §249 已记录此坑（`§249` §4） |

⇒ **§250 的立项理由成立**（D-1 是真缺陷）⇒ 死会话的**脱敏动作**方向正确。

---

## §4 独立复核（🟢 本轮从零重算，**不复用死会话任何中间产物**）

### §4.1 独立复核脚本

🔴 **不复用**死会话的 `app250_verify_indep*.py` 等任何中间产物；本轮**新写**：
- `results/app/app250_verify_indep3.py`（⇒ `results/app/app250_verify_indep3.json`）
- `results/app/app250_anticontrol.py`（⇒ `results/app/app250_anticontrol.json`）**反证组**
- `results/app/_app250_chk_invariants3.py`（⇒ `results/app/app250_invariants.json`）**逐文件不变量**

🔴 **本轮自己的判据也踩了 5 个坑**（全部是**判据缺陷**、非产品缺陷，逐个修掉才拿到 PASS）：

| # | 本轮判据缺陷 | 症状 | 修法 |
|---|---|---|---|
| C-1 | 还原映射用「**全局** idx→原句」 | 同一 idx 在不同文件对应**不同原句**（idx 55 既对应 len=21 sha8=`301202c0` 那句、又是 len=21 sha8=`301202c0` 的标点变体）⇒ 假 FAIL | 改为**逐文件**建映射 |
| C-2 | 跑脚本**不备份 evidence** | 跑完**污染工作树**（实测污染 3 个 tracked evidence 文件） | 备份 + 跑后**复原** |
| C-3 | 解释器用系统 `py`(3.13) | 无 numpy ⇒ 脚本崩溃 ⇒ 「rc 相同」**空洞恒真** | numpy 脚本改用**包内 `.venv` python 3.12**（numpy 2.4.6） |
| C-4 | evidence 要求**逐字节相等** | evidence 记的是**由语料长度派生的数字**（`src_chars` 204→195）⇒ 假 FAIL | 改判**断言判定（ok 标志/verdict/计数）全同** ＋ **单独核验**数字差恰等于替换的字符数差（**−9** ＝ 占位符比原句短 9 字符） |
| C-5 | 把「脚本崩溃」一律判 FAIL | `diag_c111_half.py` 在**脱敏前后都**在同一行抛同一个 AssertionError（**既有缺陷**，与脱敏无关） | 改判**before/after 崩溃完全一致**（同 rc ＋ 同末行）⇒ 如实登记该既有缺陷 |

### §4.2 四条判据结果（**全部 PASS**）

| 判据 | 口径 | 实测 | 结论 |
|---|---|---|---|
| **§1 残留扫描** | **reviewer 权威基线句（归一化去重后 73 条）× 全部 tracked 文件**（子串粒度）；GT 源文件按定义含原句 ⇒ **单独统计** | 扫 **2 786** 个 tracked 文件（已排除 39 个 GT 源）⇒ 残留 **1 个文件**，**豁免外 0** | 🟢 **PASS** |
| **§2 diff 法**（与施加算法无关） | `git diff` 取增删行 ⇒ **删行必须含 GT 句**、**增行必须无 GT 句** | **11/11** 文件通过 | 🟢 **PASS** |
| **§3 语法/JSON** | `.py` 改后仍能 `ast.parse`；`.json` 改后仍能 `json.loads` | **11/11** 通过 | 🟢 **PASS** |
| **§4 行为等价（还原式）** | 4 个真会被执行的脚本 ⇒ 跑「备份版（脱敏前）」vs「当前版（脱敏后）」⇒ **占位符逐文件还原成原句后**，stdout/stderr/evidence/rc 逐字节相等；**且两边都不得崩溃**（崩溃须完全一致） | **4/4** 通过（app015：rc 0/0、28 条断言 **28→28** 全 True；app127：rc 1/1、17 条断言 12→12；diag：rc 1/1、崩溃末行一致） | 🟢 **PASS** |

**⇒ 总判定 `all_pass = true`（4/4 判据全 PASS）**
（证据：`results/app/app250_verify_indep3.json` → `all_pass`／`sec1_residual.pass`／`sec2_diff.pass`／`sec3_syntax.pass`／`sec4_behavior.pass`）

### §4.3 逐文件不变量终检（**11/11 PASS**，对照 §250 备份目录逐字节）

🔴 本轮的还原算法也踩了 3 个坑（v1 前缀法 ⇒ 一行多占位符错位；v2 顺序对齐 ⇒ 字面量被吞时锚点错位；v3 `"\n".join` **丢末尾换行**）⇒ 最终用**哨兵 + difflib 字符级对齐**。

四项不变量 **11/11 全 PASS**（`results/app/app250_invariants.json` → `all_pass=true`）：
① 行尾风格不变（CRLF/LF 计数不变且不混用）② 行数不变
③ **非替换部分逐字节不变**（还原后与备份逐字节相等）④ 占位符个数 == applied 记录数。

### §4.4 反证组（**3/3 PASS** ⇒ 判据**有鉴别力**）

🔴 纪律：「PASS ≠ 正确」——判据必须**被有缺陷的旧产物识破**；反证组必须**有鉴别力**。

| # | 被检对象 | 故意改坏的方式 | 判据反应 | 结论 |
|---|---|---|---|---|
| **AC-1** | §1 残留扫描 | 把一条 GT 原句注入**已 tracked** 的文件 | `HIT n=1` | 🟢 **PASS** |
| **AC-2** | §2 diff 法 | **改动**一行**不含** GT 句的既有内容（使其进入 diff 的 minus 侧） | `minus_all_have_gt=False` | 🟢 **PASS** |
| **AC-3** | §4 行为等价 | 在被改脚本里注入真行为变化（让某条断言的 ok 翻转） | `verdicts_same=False`，ok_true **28→27** | 🟢 **PASS** |

🔴 **反证组自身也踩了 2 个坑**（**反证组的设计缺陷**，不是判据没鉴别力）：
① AC-1 首版用 **untracked** 探针文件 ⇒ `git ls-files` 扫不到 ⇒ §1 必然「NO HIT」⇒ 假 FAIL；
② AC-2 首版**只插入**一行中性内容 ⇒ diff 的 **minus 侧**没有非 GT 行 ⇒ 假 FAIL。
⇒ 改为「注入进 tracked 文件」＋「**改动**既有非 GT 行」后 ⇒ 3/3 真实鉴别力成立。

---

## §5 §250 脱敏本身的结论（**成立**）＋ 1 处**如实登记**的豁免

- **脱敏已落盘**：**11 文件 / 19 处**（证据 `results/app/app250_redact.json` → `n_changed_files=11`／`n_replacements=19`）。
- **处置三类**（逐处理由写在脚本 `DECISIONS` 里）：`doc`（docstring/comment，纯文档）**改**；`gen`/`prod`（companion 生成器、证据生成器、诊断脚本语料）**改**（产物已脱敏而生产者未脱敏 ⇒ 重跑会**回灌**原句）；`func`（**断言比较操作数**）**不改**。
- 🔴 **1 处豁免（如实登记，不改）**：`results/app/app053_draft_prefix_boundary_probe.py`
  —— 命中落在**断言比较操作数**（GT 句 len=15 sha8=`9726b63b`）
  ⇒ 换成占位符后**恒不等** ⇒ `ok_wrong` 恒 False ⇒「`Okay` 不再被错配」变成**空洞恒真（假绿）**
  ⇒ **判据失去鉴别力** ⇒ **不改**。
  🟢 该豁免**不影响** §1 结论（豁免外残留 = 0）；且其**产物证据**
  `app053_draft_prefix_boundary_evidence.json` 实测**不含**该句（`grep -c Okay` = **0**）。

### §5.1 🔴 本轮新发现：**入库前的泄漏自查**抓到 7 处泄漏（含**我自己**的 3 处）

🔴 纪律：**证据文件里也不写会议原句**（APP-155／RULES §0）⇒ 入库前**必须**逐个自查。

| # | 泄漏位置 | 性质 | 处置 |
|---|---|---|---|
| L-1 | `.tmp_recover_app/_app250_redact.py`（死会话的**生产脚本** DECISIONS 理由文本） | 理由里**引用了原句** | **改**（改为「GT 句 len=15 sha8=9726b63b」指代）⇒ **重跑生产脚本**（§5.2） |
| L-2 | `results/app/app250_redact.json`（证据 json 的 `reason` 字段） | 随 L-1 传导 | **重跑生成** ⇒ 无泄漏 |
| L-3 | `results/app/app250_verify_indep3.py`（**我自己**写的 EXEMPT 说明） | 我自己犯的 | **改**（同上口径） |
| L-4 | `results/app/app250_verify_indep3.json` | 随 L-3 传导 | **重跑生成** ⇒ 无泄漏 |
| L-5 | `status/app/_app250_append_status.py`（**我自己**的写前自检清单） | 我把**原句硬编码成检查列表** | **改**（改用 **GT 基线句归一化子串判定**，不把原句写进文件） |
| L-6 | `results/app/_app250_gitignore_patch.py`（**我自己**） | 同 L-5 | **改**（同上） |
| L-7 | `.tmp_recover_app/_app250_base/_tmp_app127.py` ＋ `app127_SRC_BACKUP.py` | 死会话的**基线快照目录**里存着**脱敏前**的源副本（与 HEAD **逐字节相同**） | **不删文件**（可逆）⇒ 改用 **`.gitignore` 规则**挡住入库（`git check-ignore` 实测生效） |

🔴 **如实登记**：这是本轮**第 3 次**犯「自己产出的文件里引用会议原句」的错误
（§249 已犯过一次、§250 死会话又犯一次）⇒ **教训固化**：
**任何写进仓的文件（脚本／证据／STATUS）都不得含原句** ⇒ 一律用 **len + sha256 前 8 位**指代。

### §5.2 🟢 **可复现性证明**：重跑生产脚本 ⇒ 输出**逐字节相等**

- 🔴 前置校验：**备份目录 11 个文件 == HEAD 逐字节相等**（否则还原会丢内容）。
- 还原 11 个文件 → 重跑 `_app250_redact.py`（理由文本已修）⇒
  **重跑后 11 文件与重跑前快照 sha256 逐个相等** ⇒ **脚本可复现**（同输入 ⇒ 同输出）。
- 顺带产出**新的** `app250_redact.json`（**无泄漏**，sha `5fae8ed5…` → `779960a8…`）。
- 顺带证明：**该脚本只改这 11 个文件**（其余 tracked 文件 SHA 前后一致）⇒ **无越界写入**。
- ⇒ 修完 L-1 后**重跑全部独立复核** ⇒ **§1/§2/§3/§4 仍 4/4 全 PASS、不变量仍 11/11、反证仍 3/3**。

### §5.3 🟢 入库前泄漏自查（**62 个候选文件 ⇒ 泄漏 0**）

- `results/app/_app250_leak_check.py`（⇒ `results/app/app250_leak_check.json`）：
  对**全部候选入库文件**（tracked 已改 ＋ untracked 的 §249/§250 相关 `.py`/`.json`，
  **已尊重 .gitignore**）用 **reviewer 权威基线句**做归一化子串判定
  ⇒ **泄漏 0**（`pass=true`）。
- ⇒ 该自查脚本本身也**入库** ⇒ 后续入库可复用。

### §5.4 🔴 新发现（**超出 §250 范围，但必须如实登记**）：**39 个 GT 源文件仍含原句且全部 tracked**

- **39 个 GT 源文件**（`results/app/*.mt.txt` / `*.tts.jsonl` 等）**全部被 git 跟踪**
  ⇒ 随仓库推 GitHub。
- 实测（`reviewer 权威基线句` 子串粒度）：**25 / 39** 个仍含原句（最多者 **336 句**）。
- 🔴 `.gitignore` **已有** `*.tts.jsonl` / `*.mt.txt` 类别规则，但 `git check-ignore` 实测
  **`NOT IGNORED`** ⇒ **规则被「文件已 tracked」架空**（gitignore 只影响未跟踪文件）。
- ⇒ **这正是 APP-144 ①（GitHub 历史改写）的对象**（§249 已把它列为「下一轮按新方法做」，
  且**历史改写是不可逆强推 ⇒ 需 reviewer 明确放行**）。
- ⇒ **本轮未擅自处理**（改写历史需放行；`git rm --cached` 会**改变仓库内容**⇒ 属破坏性操作）。

---

## §6 本轮的提交与交付面

- **提交**（**仅 App 侧文件**）：§250 的 **11 个脱敏文件** ＋ **§222 入库的 §250 脚本与证据**
  ＋ 本轮的独立复核脚本与证据 ＋ `status/app/STATUS_APP.md`（§250 指针行）＋ 本 companion。
- 🔴 **绝不提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占）——**本轮未 add、未改**。
- 🔴 **未打包**（用户规则：**不通知 ⇒ 不打包**）；**未改任何客户包目录**；
  **未跑推理/计时**（**未取 MACHINE_LOCK**）；**未调 MiniMax**；**未连 B 机**。
- 🟢 **§222 入库完整性**：§250 的**产生脚本**（`app250_fullscan.py`／`app250_provenance.py`／
  `app250_patch_desen.py`／`app250_behavior.py`／`_app250_*.py`）与**证据 json** 一并入库
  ⇒ 干净 clone 可复算 §250 的全部结论。

---

## §7 纪律自查 ＋ 收尾指纹

- 🔴 **`status/app/CORRECTIONS_APP.md` 一字未改**（reviewer 独占）——收尾四项指纹**与开工时逐字一致**：
  **46 642 B**／sha256 `cc1067b7c4908e1583d7b6537f4f1c6e01b8a3831f1996f7272c0682f517ebae`／
  mtime 2026-11-27 15:08:17／`## APP-xxx` **15 条**（max **APP-157**）。
  （🔴 该文件 `git status` 显示 ` M` ＝ **reviewer 真追加**（APP-146…157 自 11-26 起未入库）⇒ **永不 add**。）
- 🟢 **`last_ack` 仍 APP-157**（无新纠偏 ⇒ 不变；LOCK-002 另记）。
- 🟢 **§250 已闭合**（脱敏成立 + 4 判据全 PASS + 11/11 不变量 + 3/3 反证）。
- 🔴 **如实登记 5 处未做/待裁定**：
  ① **APP-144 ①（GitHub 历史改写）**——§5.4 查出 39 个 GT 源文件 tracked 且 25 个仍含原句
     ⇒ 需 reviewer **明确放行**（不可逆强推）；本轮**未改写历史、未 `rm --cached`**。
  ② **`.gitignore` 规则被架空**（`*.tts.jsonl` / `*.mt.txt` 对**已 tracked** 文件无效）
     ⇒ 根治须 `git rm --cached` ＋ 历史改写 ⇒ 同属 ①，需放行。
  ③ **§249 终检的 4 处判据缺陷**（D-1…D-4）虽已在 §250 修掉，但 **§249 的
     `app249_verify_desen_final.py` 本身仍是旧判据** ⇒ 未回头改（只追加不回头改）。
  ④ **`diag_c111_half.py` 的既有缺陷**（脱敏前后都在同一行抛 AssertionError，
     `段尾半句应当当段就翻（half）`）⇒ **与脱敏无关**，本轮只登记不修。
  ⑤ **§250 的 `app250_patch.json` / `app250_behavior.json` 两个 OUT 仍不存在**
     （`app250_patch_desen.py` 被 `_app250_redact.py` 取代；`app250_behavior.py` 是**旧判据**版本，
     本轮的等价判据在 `app250_verify_indep3.py`）⇒ 两个脚本入库但**不产出证据**，如实登记。

---

## §8 下一轮待办

1. ⏭ **等 reviewer 复核本节**（§250 + §5.4 的新发现）。
2. 🔴 **APP-144 ① 历史改写**（含 39 个 GT 源文件的 `rm --cached`）——**需 reviewer 明确放行**。
3. 🟢 **§222 已闭合**：§250 全部脚本与证据已入库 ⇒ 干净 clone 可复算。
