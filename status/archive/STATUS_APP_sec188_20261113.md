# STATUS_APP §188 整块逐字归档（2026-11-13）

归档时间：2026-11-13 06:49:24
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §189 出陠。
正文一字未删。

---

> **① 纠偏文件复核（只读、未改、未提交）**：开工＝收尾 **105 条**／最大 **APP-105**／SHA `321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1`／**344 419 B**／mtime **2026-11-12 14:25:47** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）。
> **② 其它通道全空（⇒ 无遗漏指令）**：`shared/NOTICE*` 最新仍 **11-05**（`NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`）｜agent-mail 工具仍回 **`not_bound`**（面板虽显示 connected，**实际未开通**）｜`conversation_search` 两次不同措辞均 **0 命中**｜git `origin/main..main=0` 且 `main..origin/main=0`｜`claude-clone`（worktree `clone_dev`）用 `git log claude-clone --not main` = **0**（**方向性判据**，不用 `merge-base --is-ancestor`）｜`MACHINE_LOCK` **NOT_PRESENT**（未占设备）。
> **③ 🔴 本轮修掉的真缺陷（判据层，产品代码零改动）**：§187 的**打包前闸门④** `check_app086_2a_narrowing` **的判据本身 fail-open** ⇒ 实测放行了 **2 类语义无效守卫**：
>    * **① `not _bound` 挂在 OR 上**：`elif not _bound or self._has_clone_voice():` ⇒ 旧判据「**test 树里任意位置出现过 `not _bound`**」⇒ **判 PASS**；但 `_bound` 为真**且**有克隆音色时该分支**照样会被取**⇒ **守卫是摆设 ⇒ 串音照旧**；
>    * **② 悬空调用**：`use_clone = self._has_clone_voice()` + `if use_clone:` ⇒ 旧判据**只扫 `If.test`**⇒ **一个分支都看不到**⇒ 判「不适用」⇒ **PASS**；但代码**完全没守卫**。
>    ⇒ **判据自问自答**（**「这条判据若被人当真去改生产代码，会不会改坏」**）：**会** —— 照旧判据写 `not _bound or …` 就能过闸门，而那正是**把串音改回来**。
> **④ 修法（只改 `pack_v13.py`）**：判据从「**出现过** `not _bound`」换成「分支条件**逻辑蕴含** `not _bound`」（`Or` 要求**每一支**都蕴含；`And` 只要**一支**蕴含）＋新增**悬空调用登记**（把「含 `_has_clone_voice()` 调用的赋值」也纳入候选条件）。**只读，绝不改包目录**；闸门链位置不变（③ 之后、zip 之前，`pack_v13.py:1322`）。
> **⑤ 鉴别力（合成矩阵 12/12，`app519`）**：`defective_v24_shape` FAIL｜`narrowed_dev_shape` PASS｜`guard_parenthesised` PASS｜`guard_sibling_conjunct` PASS｜**`guard_in_or_left`／`guard_in_or_right` FAIL（改前都 PASS ⇒ 缺口已封）**｜`guard_unrelated_operand` FAIL｜`no_clone_branch` PASS｜**`hoisted_call_unguarded` FAIL（改前 PASS）**｜`hoisted_call_guarded` PASS｜`hoisted_call_guarded_at_use` PASS｜`hoisted_call_guarded_or_at_use` FAIL。
> **⑥ 真包判定**（`app519` 9/9）**未变：**v2.2／v2.3／v2.3_aborted／v2.4 全 FAIL**（＝带 APP-086·2a 缺陷）｜**v2.1／v2.0／v1.13／rc10／dev 全 PASS** ⇒ **§185 的交付阻断项依然成立**（修判据**没有改动真实产物的判定**）。
> **⑦ e2e fail-closed**（`app520` VERDICT PASS）：带缺陷文件 ⇒ 闸门④ **rc=1**；换成 dev 树收窄文件 ⇒ **rc=0**；**闸门③在真包 v2.4 上仍 rc=0（PASS）** ⇒ ③ 的缺口仍在、**只能靠闸门④补**（两道闸门互补）。
> **⑧ 复跑既有闸门 3/3 复现 §185／§187 结论**：`app157` dev **11 PASS/0 FAIL**｜`app510` 反证 **VERDICT PASS**（M1–M4 注入缺陷全被识破）｜`app512` 包矩阵 v1.13／v2.0／v2.1 **PASS 11/0**、**v2.2 9-2／v2.3 8-3／v2.3_aborted 8-3／v2.4 9-2 FAIL**、v1.5 **2/8 属判据不适用**；4 个 evidence json 复跑后与 HEAD **逐字节一致**（**零 diff 噪声**）。
> **⑨ 打包脚本回归**：`pack_v13.py` **87 615 B**／CRLF **1 776 行／裸 LF 0**（原文件就是 CRLF）／`ast.parse` OK／`--help` 正常／`import` OK（`PKG_VERSION=2.5`）／difflib 复核**删除 17 行全是旧判据实现（含 docstring 两行）、纯插入 94 行**；闸门④位于 `zipfile.ZipFile(tmp_zip)`（`pack_v13.py:1371`）**之前** ⇒ 打包链路唯一入口均受约束。
> **⑩ 纪律**：**未打包**（用户不通知不打包；rc9／rc10 已打好 ⇒ 绝不重打包；**v2.5 未打**）｜**未改任何客户包**（全部只读）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 `CORRECTIONS_APP.md`**｜**未跑推理／未计时 ⇒ 未取 `MACHINE_LOCK`**｜**未调 MiniMax**｜**未通知用户**｜**未提交** ASR／MT／TTS 其它模块的 700+ 个未提交文件。
> **⑪ 本条需等 reviewer 复核**：① **完整版 v2.5 必须带 APP-086·2a 收窄**（闸门④已 fail-closed；但 **v2.5 仍未打包**，需 reviewer 决定何时打）；② v2.2／v2.3／v2.4 是否作废／标注；③ §185 新增 5 个脚本 … 以及**本轮新增 2 个证据 JSON**（`app519`／`app520`，脚本本身存于 **临时目录、未入库**）是否保留（与 APP-101 §1.d「不再新增审计／判据脚本」有张力）；④ rc10 仍待 B 机实测；⑤ **闸门④判据是否接受本轮改动**（蕴含规则 … 悬空调用登记）。
