# STATUS_APP §249 — 六通道复核（无新 App 纠偏）＋ 🔴 修掉 §248 的 2 处真缺陷 ＋ 🟢 把 APP-153 §5 修复接回生产路径

> 生成时间：2026-11-27 21:40（`Get-Date` 实测）
> 本轮性质：**待命轮**（六通道复核 ⇒ **无编号 > `last_ack`(=APP-157) 的新条目**）
> ⇒ 按纪律 **`last_ack` 不变**（仍 **APP-157**），但**§248 有两处结论不成立** ⇒ 本节按 APP-052④「只追加 §N」写明更正。

---

## §0 本轮顺序与依据

1. **第 0 步租约**：`session_lease.py acquire app` ⇒ **exit 0 / TOKEN=3a88151e**（**无 TAKEOVER、无 BUSY**）
   ⇒ 不是接续轮，是独立待命轮。
2. **六通道复核** ⇒ 无新纠偏（§1）。
3. 复核上一轮（§248）的交付面 ⇒ **发现 2 处真缺陷**（§2）⇒ 本轮修掉（§3、§4）。
4. 复核「包内 vs 开发树」⇒ 发现 **APP-153 §5 的修复只在包副本里、生产路径没有** ⇒ 回灌（§5）。
5. 写 STATUS §249 ⇒ 提交（App 侧文件）⇒ 发 STATUS 邮件 ⇒ 收尾指纹（§6、§7）。

---

## §1 六通道逐通道证据（⇒ **无新 App 纠偏**）

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| 1 | **局域网** `status/app/CORRECTIONS_APP.md` | 46 642 B／sha256 `cc1067b7c4908e1583d7b6537f4f1c6e01b8a3831f1996f7272c0682f517ebae`／mtime 2026-11-27 15:08:17／`## APP-xxx` **15 条**／max **APP-157** | 与 `last_ack`(=APP-157) **相等** ⇒ 无新条目 |
| 2 | **QQ 收件箱** | 全部 App 封的 max ＝ **APP-157**（`msg_8s6eELs8zrm5Euqkw7cI5tyTsOivbUwHdDGzjWyDShX62Q`，2026-11-27T07:08:16Z）＝**已执行**；其后仅 `H-028 [MT]`(11-24) 与 `R-029 [FQ]`(11-26) 等**非 App** 封 | **无新 App 纠偏** |
| 3 | **QQ spam** | 空（`data: []`） | 无 |
| 4 | **QQ trash** | 1 封（`MiniMVP rc9 Complete Performance Report`，2026-11-13，**与 App 纠偏无关**） | 无 |
| 5 | **agent-mail** | `status: not_bound`（与前几轮相同，**该通道本会话不可用**） | 不适用 |
| 6 | **全库检索** `APP-1(5[89]|[6-9][0-9])` | 命中全是 `results/app/_dead_session_think_dump.txt`（**死会话思考转储**，非纠偏文件）与 `results/app/win_capture.py:49`／`STATUS_APP_sec233/234/235` 的**「APP-178 实测修正」历史注释**（2026-10-31，**别的模块编号**） | **无新 App 纠偏** |

⇒ **结论：无编号 > APP-157 的新条目 ⇒ `last_ack` 保持 APP-157。**

---

## §2 🔴 本轮发现的 2 处真缺陷（§248 的结论不成立）

### §2.1 缺陷①：§248 登记「脱敏完成」，而**它自己的证据是 FAIL**

`results/app/app155_desens_verify.json`（写于 2026-11-27 15:36:44）的 `verdict` ＝ **`FAIL`**
（`n_pass` 33／`n_fail` 43；含 1 个 `FAIL_JSON`）。
⇒ **§248 §3.2「812 处替换 / 76 个文件；穷尽重扫：仍命中 0 个文件」与 §8/§9.5 的「脱敏完成」登记与证据不符，§248 未写这一条。**

**根因（我独立查清，非采信任一方）：**

* `app155_desens_ground_truth.json` 的 `hits` **每文件只记 14 行**（抽样）；
* `app155_desens_apply.py` **只遍历 `hits` 记到的行** ⇒ 每文件另外 **~45 行从未被访问、从未被替换**；
  （实测 `results/app/app332_v23_cli_output.txt`：HEAD 含会议原句的行 **59 行**，`hits` 只记 **14 行** ⇒ **漏 45 行**）
* 而「穷尽重扫」按**整句**切（`sentences()`）⇒ **嵌在更大句子里的会议原句判不出** ⇒ 报 0 命中（**假绿**）。
  例：HEAD 第 34 行 `[实时] Agenda topics today` —— 整句归一化后 ≠ GT 的 `agenda topics today` ⇒ 漏。

**第二个真缺陷（更严重）：§248 的 apply **弄坏了 12 个 JSON 文件。**
`app155_desens_apply.py` 的 `body.replace(target, …)` 里的 `target` 是**剥掉日志前缀后的整句**，
在 JSON 字符串里替换时**连收尾引号一起吞掉** ⇒ JSON 结构被破坏：

```
HEAD: "text": "Discussion. Very successful execution on Patrick and Wildcat, and Novelick on a base derivative model."
NOW : "text": "Discussion. [会议句 idx 170]        ← 收尾引号没了 ⇒ JSON 非法
```

实测 **12 个** JSON 文件 **HEAD 可解析 → 现在不可解析**：
`app121_asr_app_3mat_GPU0.json` / `_OLD_v11.json` / `_NPU.json`、
`app418_rc6_tts_direct.json` ＋ `app418_rc6_tts_direct/{de,en,es,fr,it,ko,pt,ru}/wavs.json`。

### §2.2 缺陷②：APP-153 §5 的修复**只在包副本里，生产路径（dev 树）没有**

包 `LiveCaption_MiniMVP_v1.2.1` 里已带 APP-153 §3/§5 的修复（GUI 标题 v1.2.1、`--check` 中性措辞、
开发机路径脱敏、黑名单正则泛化），但 **dev 树 `live_caption/` 没有**。
而**打包路径是 dev → 包**（`_app151_sync_app_py.py`、`pack_v13.py` 都从 dev 取 `app/*.py`）
⇒ **下一次打包会把这些修复全部丢掉**。
🔴 这与 §234 修掉的缺陷**同类**：「§233 的修法没接进生产路径」；§248 把修复只写进了**包副本**。

---

## §3 修法①：脱敏**重做**（先回到干净基线，再按正确判据重做）

### §3.1 做法（**不用** §248 的脚本，另写一套并**逐条独立复核**）

* **回到干净基线**：`git restore --source=HEAD --worktree` 还原 121 个文件
  （把 §248 弄坏的 12 个 JSON 也一并还原回合法状态）⇒ **基线可信**。
* **判据换成「子串粒度」**：§248 用**整句相等** ⇒ 漏；本轮用**行归一化后包含任一 GT 句**（子串）⇒ **不漏**。
  ground truth ＝ 39 个受控逐句产物里的 **571 条**句（去重、归一化、按长度 ≥ 12 过滤）。
* **替换用「归一化 + 索引映射」**：归一化时**同时记录每个字符对应的原文下标**
  ⇒ 命中 span **换算回原文**再替换 ⇒
  ① **完整**（标点/空白变体也命中）；② **精确**（只动命中 span，其余逐字节不变）。
* **raw form 不用作匹配键**：raw form 原文匹配会漏掉标点变体（GT `Good morning, everyone.`
  vs README `Good morning everyone`）⇒ 改用归一化串 + 索引映射。

### §3.2 写前不变量（逐文件，**全部 PASS**）

1. **行尾风格不变**（CRLF/LF 各自计数不变，且不混入另一种行尾）；
2. **非替换部分逐字节不变**（逐行核对：改后行去掉占位后，各片段能在改前行里**按序**找到）；
3. `.json` **不得从「可解析」变成「不可解析」**（改前就坏的**如实登记**，不修不判）。

### §3.3 结果

| 项 | §248 | **本轮** |
|---|---|---|
| 处理文件 | 76 | **121** |
| 替换处数 | 812 | **1 987** |
| 命中行（子串口径） | 未测 | **3 360**（160 个文件） |
| **改坏的 JSON** | **12** | **0** |
| 改后 JSON 可解析 | — | **63 / 63** |

**另补上 2 个 §248 完全没碰的 `.tts.jsonl`**（`app294_rc4_npu_out/npu_full/tts.jsonl`、
`app415_rc6_langs/ja/tts.jsonl`）⇒ **51 处 / 8 处**。

### §3.4 独立终检（**4 条判据全 PASS**，`results/app/app249_desen_final_verify.json`）

| 判据 | 内容 | 实测 |
|---|---|---|
| §1 **彻底** | 说明类文件**逐行子串扫描**（1 251 个文件）⇒ GT 命中 | **仍命中 0 个文件** ✅ |
| §2 **无损** | **diff 法**（与施加算法无关）：逐行比 HEAD 与当前 ⇒ 删除段必属 GT 句、插入段只有占位 | **121 PASS / 0 FAIL** ✅ |
| §3 **结构** | `.json` 改后不可解析数（**新坏**） | **0**（新坏 0） ✅ |
| §4 **反证组** | 把一处占位**改回**真会议句 ⇒ §1 扫描必须命中 | **命中=True** ✅（判据有鉴别力） |

> 🔴 **§2 判据的两次修正（如实登记）**：
> ① 我第一版用「占位还原 ⇒ 与 HEAD 逐字节相等」⇒ **假 FAIL 75 个** ⇒ 根因＝还原时多加了空格 ⇒ 改用 diff 法；
> ② diff 法第一版用**字符级**对齐 ⇒ 报「插入非占位 `x`」⇒ 根因＝difflib 把 `Good morning` 里的 `x` 对齐到别处
>    ⇒ **假 FAIL** ⇒ 改用**词级**对齐（占位当原子 token）⇒ 全 PASS。
> ⇒ **两次都是判据缺陷、不是产品缺陷**（MEMORY：「FAIL 先怀疑判据/环境」）。

---

## §4 修法②：把 APP-153 §5 的修复**接回生产路径**（dev 树）

* 做法：**精确字符串替换 + 唯一命中断言**（**不整目录覆盖**）⇒ 逐文件 6/3/1/1 个替换块，
  每个块在 dev 里**恰好命中 1 次**才动手，否则**中止不改**。
* 写前不变量：行尾风格不变；行数变化**等于**替换块预期行数差（有的块把 2 行并成 1 行）；
  `.py` 仍可 `ast.parse`。
* 结果（`results/app/app249_pkg_to_dev_sync.json`）：

| 文件 | 替换块 | 写后与包**逐字节一致** |
|---|---|---|
| `live_caption/live_caption_app.py` | 6 | ✅ |
| `device_config.py` | 3 | ✅ |
| `asr06b_stateful_backend.py` | 1 | ✅ |
| `v23_preset_only.py` | 1 | ✅ |

⇒ **dev 树 `app/*.py` 与包内 `app/*.py` 共有 34 个 ⇒ 内容不同 0 个**（此前 4 个不同）。
⇒ 复核：dev 树 GUI 标题 `实时字幕 MiniMVP v1.2.1`；`Trekker-PTL` 残留 **0**；`rc5 在 B 机` 措辞 **0**；
黑名单正则 `r'(?i)C:\\Users\\[^\\\\]+'`（泛化）。

---

## §5 本轮**未做/待裁定**（如实登记）

1. 🔴 **APP-144 ①（GitHub 历史改写）本轮未做**：
   * reviewer 队列里它排在 v1.2.1 之后（APP-146 §6、APP-155「顺序不变：先 APP-153/154，再做 APP-144 ①」），
     v1.2.1 已完成 ⇒ **本轮它已解锁**；
   * 但**方法被 APP-148 §2 改过**（「不能只用 §237 的特征句表做替换、再用同一张表 grep 验收」⇒ 必须
     **逐文件通读 `git log -p --all -- <文件>` 的完整上下文**，把该文件里**所有**会议原句与译文都列入替换表）；
   * 且 APP-155/156 §3 要求**扫描范围扩大到 status/ 下全部模块的 STATUS_*/CORRECTIONS_***（含 reviewer 推过来的条目）。
   * ⇒ **本轮先把「工作树侧」的脱敏补做完整并验证**（§3），**历史改写本身需要按 APP-148 §2 的新方法重做**
     （逐文件通读历史上下文建表）⇒ **本轮未做，留给下一轮**（本轮已把方法与范围写清，避免再走 §237 的旧路）。
   * 🔴 **历史改写是 `--force-with-lease` 强推 ⇒ 属不可逆操作 ⇒ 按纪律需要 reviewer 明确放行再做**。
2. 🔴 **§222 入库完整性**：`results/app/app155_desens_*.json` 三个证据文件**已被本轮覆盖**（`app249_*` 为新证据），
   而**产生它们的脚本**（`app155_desens_apply.py` 等）**仍未入库** ⇒ 下一轮需一并入库（本轮已把本轮的
   5 个脚本登记为待入库）。
3. 🟡 **`.gitignore` 的 `*.tts.jsonl` 规则不覆盖** `*/tts.jsonl`（无点前缀）⇒
   `app415_rc6_langs/ja/tts.jsonl` 等**仍可能被再次提交** ⇒ 已在本轮补做时脱敏，但**规则本身待补**。
4. 🟡 根 `.gitattributes`（§226 根治项）**仍未做**，等 reviewer 裁定（跨模块）。
5. 🟡 §244/§248 提到的其它待裁定项（v2.7 是否出、`.staging`、v2.5 重签 ACCEPTED、默认分离设备、
   `n_speakers=0` 口径）**本轮未动**。

---

## §6 本轮纪律自查

* 🟢 **只提交 App 侧文件**：`results/app/app249_*`（脚本＋证据）＋ `live_caption/` 的 4 个 App 侧文件
  ＋ `status/app/STATUS_APP.md`（本节）＋ 被脱敏的 `results/app/**` 与 `status/**` 说明类文件。
* 🟢 **绝不提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占；本轮**未修改**它，`git status` 里的
  ` M` 是 reviewer 自己追加的 271 行 ⇒ 与本轮无关，见 §7 指纹）。
* 🟢 **未吞** ASR/MT/TTS 其它模块的未提交改动（`status/archive/STATUS_ASR_upto_20261030.md`、
  `status/asr/notes/asr_s83.md` 的改动**全部是本轮/§248 的脱敏占位替换**，已逐行核对：
  **每个文件的新增行 100% 含占位**，无夹带 ⇒ 见 §3.4 §2 判据）。
* 🟢 **未打包**：本轮**没打任何 zip**，**没动任何客户包目录**（只读了 v1.2.1 目录做比对），
  **没改** `LiveCaption_MiniMVP_v1.2.1` 里的任何文件。
* 🟢 **未跑推理/测速** ⇒ 未取 `MACHINE_LOCK`（本轮无计时作业）。
* 🟢 **未调 MiniMax**、**未连 B 机**、**未通知用户**。
* 🟢 **未改** `CORRECTIONS_APP.md`（只读）。
* 🟢 **未 force push**：本轮**不推主仓**（APP-156 §3：脱敏完成前主仓不推 GitHub）⇒ 提交只在本地。
  🔴 **注意**：上一轮留了 2 个**未推送**的本地提交（`c51c556`、`a661844`）⇒ 本轮**沿用同一策略**，
  主仓推送**等 APP-144 ① 历史改写完成后**再做（§5.1）。

---

## §7 收尾指纹（`CORRECTIONS_APP.md` 只读）

| 项 | 开工时 | 收尾时 | 一致？ |
|---|---|---|---|
| 字节数 | 46 642 | 46 642 | ✅ |
| sha256 | `cc1067b7c4908e1583d7b6537f4f1c6e01b8a3831f1996f7272c0682f517ebae` | 同左 | ✅ |
| mtime | 2026-11-27 15:08:17 | 同左 | ✅ |
| `## APP-xxx` 条数 | 15 | 15 | ✅ |
| max 编号 | APP-157 | APP-157 | ✅ |

⇒ **本轮零改动**（reviewer 独占文件未被触碰）。

---

## §8 STATUS 邮件（已发并核对三地标）

* `message_id` = `msg_C4jsDkA-4mVKlh0b7l7fCyaMvRVxY7y5y3tILeZCedT8Pg`
* 收件人 `alexchen7694@agent.qq.com`，发出时间 **2026-11-27T13:42:34Z**
* 正文 **7 012 B**／sha256 `2c72a61d6218b0c1cf55e0e095882ae3ec11c3b1b95eddee42230bc2c528c58b`
  （正文落盘 `results/app/_app249_status_email_body.txt`；投递证据 `results/app/app249_status_email_sent.json`）
* 🔴 **正文里的 `<文件>` 已改成 `[文件]`**（§224 教训：邮件通道会吃掉 `<`）
* **三地标全部命中同一 message_id ⇒ 中段未被截断**：
  首 `[C4][A][STATUS] §249 待命轮` ／ 中 `§2 无损：diff 法（与施加算法无关）` ／
  尾 `results/app/app249_desen_apply_full.json / app249_desen_scan_full.json`
* 🔴 **未发附件**：邮件通道拒收内联附件（§248 已实证 40001）⇒ 门禁表/证据改为正文给**路径 + 字节数 + sha256**。
