# STATUS_APP §189 整块逐字归档（2026-11-13）

归档时间：2026-11-13 08:21:30
归档原因：活文档逼近 **40 000 B** 上限（APP-052④），为 §190 出陠。
正文一字未删。

---


> **① 纠偏文件复核（只读、未改、未提交）**：开工＝收尾 **105 条**／最大 **APP-105**／SHA `321be59c0c6b4ae4531833f48ba3fcca36aa03fbf7d9146163a0478534b70bf1`／**344 419 B**／mtime **2026-11-12 14:25:47** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` 保持 **APP-105**（不写 APP-106：那是 reviewer 的编号）。
> **② 其它通道全空（⇒ 无遗漏指令）**：`shared/NOTICE*` 最新仍 **11-05**｜agent-mail 工具仍回 **`not_bound`**｜`conversation_search` 两次不同措辞均 **0 命中**｜git `main...HEAD` ahead=0/behind=0｜`claude-clone`（worktree `clone_dev`）`git log claude-clone --not main` = **0**（**方向性判据**，不用 `merge-base --is-ancestor`）｜`MACHINE_LOCK` **NOT_PRESENT**（未占设备）。
> **③ 复跑既有闸门 3/3 复现 §185／§188 结论**：`app157` dev **11 PASS/0 FAIL**｜`app510` 反证 **VERDICT PASS**（M1–M4 注入缺陷全被识破）｜`app512` 包矩阵**完整版判定未变**（v1.13／v2.0／v2.1 PASS 11/0；**v2.2 9-2／v2.3 8-3／v2.3_aborted 8-3／v2.4 9-2 FAIL**；v1.5 **2/8 判据不适用**）＋ **新增 MiniMVP 10 行**（见 ⑦）。`app157`／`app510` 两个 evidence 复跑后与 HEAD **逐字节一致**（归一化行尾后，零 diff 噪声）。
> **④ 🔴 真缺陷 1（判据层；产品代码零改动、客户包零改动）：打包前闸门④ 的**检测范围**有洞**。旧闸门④ 只在**分支条件里**调用 `self._has_clone_voice()` 时才把分支纳入检查 ⇒ **分支①**（`if self.clone_mode and not _bound:`，分支体里只调 `self._log_keep_clone()`、**不调** `_has_clone_voice()`）**根本看不见** ⇒ 它的 `and not _bound` 一去掉（=「按句绑定模式 + 标签晚到 ⇒ 沿用上一句克隆音色」⇒ **串音**）时，闸门④ **仍判 PASS** ⇒ **实测探针**：闸门④ **rc=0（放行）** 而 app157 行为判据 **B3 FAIL**（观测 `after_embed=VEC_S2`／`after_kind=clone`）⇒ **判据自问自答**（「这条判据若被人当真去改生产代码，会不会改坏」）：**会**（照旧判据把分支① 的守卫删掉是「安全的」⇒ 等于把串音改回来）。
> **⑤ 修法（只改 `pack_v13.py`）**：**91 872 B**／CRLF **1 856 行／裸 LF 0**（原文件即 CRLF）／`ast.parse` OK／`--help` OK／`import` OK（`PKG_VERSION=2.5`）／difflib 复核＝**删 10 行全是旧判据实现、增 90 行**。
>    * **补丁 A（范围）**：把「**分支体里自己**执行了 keep-logger 调用（`_log_keep_clone`／`_log_keep_last_clone`）」也纳入分支识别 ⇒ 🔴 **不下钻进嵌套 If**（否则外层 `if not self._apply_self_ref_voice():` 会被误判成 keeper ⇒ fail-closed 误拦**正确**的包）。
>    * **补丁 B（守卫）**：`not X` 里的 `X` 必须**在本模块里真的被绑定过**（Name 出现在 Store 上下文／`self.X` 真被赋值过）⇒ 修掉 `not self._bound`（`self._bound` **整个模块不存在** ⇒ 守卫是摆设 ⇒ `AttributeError`／恒假）。
>    * 闸门链位置**不变**：闸门④ 在 `pack_v13.py:1402`，`zipfile.ZipFile(tmp_zip,'w')` 在 **`:1451`** ⇒ 仍在建 zip **之前**（`app521` 用 AST 独立验过）。
> **⑥ 鉴别力 + 交叉验证（新脚本 `results/app/app521_gate4_scope_crosscheck.py` ＋ evidence `results/app/app521_gate4_scope_crosscheck_evidence.json`）**：**静态闸门④** 与 **行为判据 app157 B3** 两条**互相独立**的判据**同判**才算一致。
>    * **合成矩阵 12/13 一致**：`b1_guard_removed`（分支①去守卫）**改前闸门④ PASS ⇒ 改后 FAIL**（缺口已封）｜`b2_guard_removed` FAIL｜`both_guards_removed` FAIL｜`b1_guard_parens` PASS｜`b1_guard_not_self_bound` **改前 PASS ⇒ 改后 FAIL**（补丁 B 生效）｜`b1_guard_or` FAIL｜`b2_guard_or` FAIL｜`b2_guard_and_other` PASS｜`hoisted_unguarded` FAIL｜`hoisted_guarded` PASS｜`hoisted_guarded_or` FAIL｜**唯一不一致 = `b1_guard_equiv_attr`**（`not self._spk_voices` 语义等价但闸门④ 判 FAIL）⇒ **fail-closed（安全方向）**，不放大成漏洞。
>    * **真包矩阵 17/18 一致**：**唯一不一致 = v1.5**（代码早于按句绑定 ⇒ B3 **判据不适用**，§188 已记录）。
>    * **e2e fail-closed PASS**：v2.4 基线 rc=**1**（分支② 无守卫）｜v2.4 ＋ 分支①去守卫 rc=**1**｜dev 树收窄文件 rc=**0**。
> **⑦ 🔴 真缺陷 2（工具覆盖漏洞）：`app512` 的包过滤只认完整版**。`pkg_dirs()` 用 `startswith('Confucius4_LiveCaption_v')` ⇒ **MiniMVP 的目录名是 `Confucius4_LiveCaption_MiniMVP_v1.0-rcN` ⇒ 10 个目录全部漏扫** ⇒ §185／§186／§188 反复引用的「真包矩阵 9/9」**只覆盖了完整版**。已修（app512 现在扫 **17** 个包）⇒ **新查实结论**：**MiniMVP v1.0／rc1／rc2／rc3／rc4／rc5** 的 `app/tts_worker.py` 分支② 是 `elif self._has_clone_voice():` ⇒ **同样缺 APP-086·2a 收窄**（app157 行为判据 **9/2**、B3=**False** ⇒ 与闸门④ rc=1 **同判**）｜MiniMVP **rc7／rc8／rc9／rc10** PASS **11/0**。
> **⑧ 🔴 交付阻断项（结论更新）**：**带 APP-086·2a 缺陷的包共 10 个** ＝ 完整版 **v2.2／v2.3／v2.3_aborted／v2.4**（4）＋ MiniMVP **v1.0／rc1／rc2／rc3／rc4／rc5**（6）⇒ **完整版 v2.5 必须带收窄**（闸门④ 现已覆盖分支①/分支②，且 fail-closed）｜MiniMVP 的缺陷路径**此前记录为惰性**（MiniMVP 克隆置灰 ⇒ `clone_mode` 恒 False、无克隆音色 ⇒ 走 `else` 回落预设 A）⇒ **风险等级低于完整版**，但代码仍带缺陷；**本轮未做设备级复核**（纯静态、零推理）｜**当前交付版 v2.1 无分支② ⇒ 不受此缺陷影响**。
> **⑨ 纪律**：**未打包**（用户不通知不打包；rc9／rc10 已打好 ⇒ 绝不重打包；**v2.5 未打**）｜**未改任何客户包**（全部只读）｜**未改产品代码**（`live_caption/` 零改动）｜**未改 `CORRECTIONS_APP.md`**｜**未跑推理／未计时 ⇒ 未取 `MACHINE_LOCK`**｜**未调 MiniMax**｜**未通知用户**｜**未提交** ASR／MT／TTS 其它模块的 700+ 个未提交文件｜探针与临时脚本全在**临时目录**，只把 `app521` 脚本＋evidence 入库（可复现）。
> **⑩ 本条需等 reviewer 复核**：① **完整版 v2.5 必须带 APP-086·2a 收窄**（何时打包由 reviewer 定）；② **v2.2／v2.3／v2.4 ＋ MiniMVP v1.0／rc1–rc5 是否作废／标注**；③ **闸门④ 本轮两处判据改动**（分支体 keep-logger 检测 ＋ 守卫须指向真实绑定）是否接受；④ **app512 扩到 MiniMVP** 后 evidence json 变了（**5 137 B → 11 507 B**，多 10 行）是否接受；⑤ 新增 `app521` 脚本＋evidence 与 **APP-101 §1.d「不再新增审计／判据脚本」** 的张力（本次已入库 ⇒ 可复现；reviewer 可要求删除）。
