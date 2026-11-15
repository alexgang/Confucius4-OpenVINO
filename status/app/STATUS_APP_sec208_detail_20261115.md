# STATUS_APP §208 完整正文（companion，2026-11-15）

归档原因：活文档逼近 **40 000 B** 上限（APP-052④）⇒ §208 完整正文放 companion，
活文档只留速查（APP-101 §1.d：每节不超过 3 行速查）。
生成时间：2026-11-15 10:18:04

§208 完整正文 SHA256：f17208823b7af18efaa209620a2a61f93e74ba197361d0f390caa51b905319a3（11716 B）

---- 活文档速查（以下 6 行＝**唯一事实来源**；writer 按此**原样**追加到活文档）----
\n> 🔴 **完整正文**（①–⑫ 证据字段／矩阵全表／反证组）见 **companion** ⇒ `status/app/STATUS_APP_sec208_detail_20261115.md`（正文块 **{cbytes} B**／SHA256 `{csha}`）⇒ 活文档只留速查（APP-101 §1.d）。
> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾**逐字一致** ⇒ SHA256 `30a55189…`／**360 842 B**／mtime **11-14 15:38:28**／**109 条**／最大 **APP-109** ⇒ **SHA 零改动**；`last_ack` **仍 APP-109**。**② 其它 5 通道全空**：agent-mail 工具层仍 **`not_bound`**（**第 11 轮** ⇒ **查不了**，非「查了为空」）｜`conversation_search` **0**｜`NOTICE` **11-05 09:35**｜git **0/0**（HEAD `39c503a`）｜ASR 最大 **ASR-058**（无 App 条目）｜根 **C-135**；全盘扫：09:00 后仓库内**只有我自己的改动** ⇒ reviewer 无新文件；**`MACHINE_LOCK` 全程 NOT_PRESENT**。
> **③【真缺陷（闸门层 · 完整版形态）】**`pack_v13.py`（=**v2.5 要用的脚本**）**全程零验收绑定**：`ACCEPTED.json` 全仓**只有 `shortcut_update.py` 读**（且在 **zip 写完之后**才跑）；会查漂移的 `app191_acceptance_code_binding_gate.py` **从未被调用** ⇒ **验收证据不参与出包决策 ⇒ 验收后改包照样能出包**（§204–§207 只审过另两条链 ⇒ **完整版从未被审过**）。**④【鉴别力矩阵 `app571`，15/15 PASS（12 矩阵 ＋ 3 反证组）】**改前臂＝HEAD 逐字原文、改后臂＝工作区；两臂**同款桩**、在**临时假包**上**真跑 `_run()`**，⇒ **改前 4 臂全 fail-open**（rc=0 **且真的产出 zip**），改后 ⇒ **rc=1、0 字节 zip**；T4 合法包两臂都出包且 md5 相同；**AST 直读表**：改前臂**全文件**无函数读 `ACCEPTED.json`；**反证组 3/3**。
> **⑤【修法（只改交付脚本 `pack_v13.py`；产品代码零改动）】**新增**打包前闸门⑤** `check_acceptance_binding()`：**身份绑定**（`NO_ACCEPTED`／`NOT_ACCEPTED`／`VERSION_MISMATCH`／`PKG_MISMATCH`）＋ **内容绑定**（`NO_CONTENT_BINDING`／`CONTENT_MISMATCH`／`CONTENT_SET_MISMATCH`／聚合指纹兜底），**两层都 fail-closed**；接在闸门④之后、`do_dry_run` 之前；另加 `acceptance_gate_selftest()`（9 臂反证自测，随脚本走）＋ CLI `--self-test-acceptance`。**⑥【绑定范围：复用既有格式，验收侧一字不改】**＝包内 `app/` **生产模块**（`.py`，排除 dev-only）（与 **app191 口径一致**）⇒ 复用既有 `ACCEPTED.json` 指纹；⚠️ README／NOTICE／MANIFEST.json **不在范围内**（打包会重写）。
> **⑦【真包零漂移 ⇒ 交付物未受损（如实记录，不夸大）】**真 v2.1／v2.2／v2.4 指纹与当前包内容**逐模块一致**（28/28、28/28、29/29）⇒ 本缺陷是**闸门层潜在 fail-open**，**不是**已发生的交付污染；真包**只读**判定 **PASS**（非假 FAIL），变异只在**临时副本**上做 ⇒ 真包**零写入**。**⑧【证据】**`app571_ful_version_acceptance_gate_matrix.json`＝**10 956 B**／**10:17:14**／`9777ec82…`（`n_pass=15`／`n_fail=0`）；`pack_v13.py`＝**111 670 B**／**diff 258 插入 0 删除**。
> **⑨【回答 §207 ⑪④：`_app500`（rc10 模板）**不**改】**rc10 的 zip **已交付且已复核** ⇒ 改历史脚本不能改变已交付物；APP-055 禁止重打包 ⇒ rc10 不会重建；**反而有害**（搬进 `_app500` ⇒ 重跑 rc10 构建会被挡死）⇒ **改为保证不再继承**：rc12 应复制 **rc11 的 `_app524`（已修）**，其内置自测**跟着走**。🔴 请确认该链向约定。**⑩【纪律】****未打包**（用户不通知不打包）｜**零客户包写入**｜**未改产品代码**｜**未改 `CORRECTIONS_APP.md`**｜未跑推理 ⇒ 未取 `MACHINE_LOCK`｜未调 MiniMax｜**逐文件** `git add`。**⑪ 本条需等 reviewer 复核**：定性／闸门⑤改法／绑定范围／`_app500` 决策／**是否留 `--allow-unaccepted` 出口**（闸门⑤会拦「合法但未重签 ACCEPTED」的包）｜沿用未变：sp2 的 zip／TTS 丢句／OPEN-1／10 个缺陷包／**v2.5**／EXT 换嵌／目标机 SHA256／`cuda_env` 范围。**⑫【偏离如实申报】**本轮**确实无新纠偏**，但产出**一项可复算的交付闸门层真缺陷**及修法、矩阵与反证组 ⇒ 写入本节并按限额**归档 §207**（整块逐字）⇒ 新增 § 章节 1 节／归档件 1 个／companion 1 个／客户包写入 0 文件／未打包。
\n
---- 完整正文（以下逐字；**正文块 SHA256 ＝ 本分隔线之后的全部内容**）----
\n> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾**逐字一致** ⇒ SHA256 `30a55189bb358c952cf3a600357bbf68e0103bae98b77100dec5fa2afd98f503`／**360 842 B**／mtime **2026-11-14 15:38:28**／**109 条**／最大 **APP-109** ⇒ **可写「SHA 零改动」**（只读、未入库、未提交）；`last_ack` **仍 APP-109**（无新纠偏 ⇒ **不写自己的编号**）⇒ 本轮**无新条目可执行**。

> **② 其它 5 通道全空**（逐条实测）：agent-mail 工具层仍返 **`not_bound`**（**连续第 11 轮**——面板显示 connected，但**工具**未开通 ⇒ 该通道**查不了**，**不是**「查了为空」）｜`conversation_search` **0 命中**｜`shared/NOTICE*` 最新 **2026-11-05 09:35**｜git `origin/main...main` **0/0**（HEAD `39c503a`）／`claude-clone --not main` = **0**｜ASR 侧最大 **ASR-058**（**无 App 条目**）｜根 `status/CORRECTIONS.md` 最大 **C-135**。**全盘扫**：2026-11-15 09:00 之后仓库内**只有我自己的改动**（`.workbuddy/memory/2026-11-15.md`）⇒ reviewer 未产出新文件。**`MACHINE_LOCK` 本轮全程 NOT_PRESENT**（上一轮 reviewer 08:28 持有的那把已释放）⇒ 本轮**未取锁、未做设备作业**。

> **③【真缺陷（闸门层 · 完整版形态）】**`pack_v13.py`（= **下一版 v2.5 要用的那个打包脚本**）**全程没有任何验收闸门**：
> - `ACCEPTED.json` 全仓**只有 `shortcut_update.py` 读它**（`ACCEPTED_MARKER`），而它是在 **zip 已经写完之后**（`_run` → `_finish` → 之后）才跑的，只决定「**要不要改桌面快捷方式**」；
> - 真正会查漂移的 `results/app/app191_acceptance_code_binding_gate.py`（R1 逐模块指纹漂移检测）**从未被 `pack_v13.py` 调用** ⇒ 仓库内**零调用点**（已 grep 确认）；
> - ⇒ **验收证据不参与出包决策** ⇒ **验收后改包照样能出包**（交付包 ≠ 被验收过的包）。
> ⇒ 与 §204（Special MVP）／§205／§206／§207（MiniMVP）修掉的是**同一类 fail-open**，只是**完整版这一形态从来没被审过**（前四轮只审了两条链）。

> **④【鉴别力矩阵 `app571`，15/15 PASS（12 矩阵 ＋ 3 反证组）】**
> - **A 腿 · 行为级真跑（主证据）**：**改前臂 = `git cat-file blob HEAD:pack_v13.py`（逐字原文）**，**改后臂 = 工作区 `pack_v13.py`**；两臂都在**临时假包**上**真跑 `_run()`**（不是 import、不是看代码），**两臂用完全相同的桩**（① 路径写死 ② 版本标识 ③ APP-081 洁净度 ④ APP-086·2a 收窄 ＋ 内部素材 ＋ zip 内容校验 ＋ 交付指纹落盘）⇒ **唯一变量 = 验收绑定闸门**；观测口径 = **真的产出了 zip 没有**。
>   - **改前臂 4 臂全 fail-open**：T1 无 `ACCEPTED.json` ⇒ rc=0 **并真的产出 zip（336 B）**；T2 版本不符（`ACCEPTED.version=8.8` vs 包 `v9.9`）⇒ rc=0 **产出 zip（794 B）**；T3 验收后改一个字 ⇒ rc=0 **产出 zip（795 B）**；T4 合法包 ⇒ rc=0 产出 zip（793 B）。
>   - **改后臂**：T1 `NO_ACCEPTED`／T2 `VERSION_MISMATCH`／T3 `CONTENT_MISMATCH` ⇒ **rc=1 且 0 字节 zip**；T4 合法包 ⇒ **rc=0 照样出包**，且 zip 的 md5 与改前臂 T4 **完全相同**（`0b92f829…`）⇒ **修法不改变合法包的产出**。
> - **B 腿 · AST 直读表**：改前臂 `_run()` 的闸门集合 = `{check_pkg_path_hardcode, check_version_identity, check_v23_pkg_gate, check_app086_2a_narrowing, check_internal_material}`；**全文件范围内**「函数体里出现 `ACCEPTED.json` / `code_fingerprints` / `check_acceptance`」的函数数 = **0**（改后臂 = 5，含新增的 `check_acceptance_binding`）⇒ 结构层面证明改前臂**无处读验收证据**。
> - **C 腿 · 真包只读复验（防假 FAIL）**：改后臂闸门对**真 v2.1／v2.2／v2.4** 三包**只读**判定 = **PASS**（绑定 28／28、28／28、29／29 个生产模块）⇒ **不是假 FAIL**；同一真包**临时副本**上追加一行注释 ⇒ **BLOCK `CONTENT_MISMATCH`** ⇒ 真包**零写入**。
> - **反证组（矩阵自己的反证，3/3 PASS）**：M1 判据把「本该拦却没拦」判成 PASS ⇒ 必须 FAIL；M2 判据把「放行但没真的产出 zip」判成 PASS ⇒ 必须 FAIL；M3 **把闸门废掉**（变异真的改坏 `check_acceptance_binding` 的 `NO_ACCEPTED` 分支，锚点命中次数有断言）⇒ 矩阵必须报 FAIL（实测 T1 不再被拦 ⇒ `n_fail=1`）⇒ **矩阵不是摆设**。

> **⑤【修法（只改交付脚本 `pack_v13.py`；产品代码零改动）】**新增**打包前闸门⑤** `check_acceptance_binding(pkg_dir, expect_version)`（两层都 fail-closed）：**身份绑定**（`ACCEPTED.json` 存在 ⇒ `NO_ACCEPTED`；`accepted` 为真 ⇒ `NOT_ACCEPTED`；`version` == 本包版本 ⇒ `VERSION_MISMATCH`；`pkg_dir` 目录名 == 本包目录名 ⇒ `PKG_MISMATCH`）＋ **内容绑定**（`code_fingerprints` 必须存在 ⇒ `NO_CONTENT_BINDING`；**逐条重算** SHA256 ⇒ `CONTENT_MISMATCH`；**反向集合校验**（包内多出模块也算漂移）⇒ `CONTENT_SET_MISMATCH`；另重算聚合指纹 `code_fingerprint` 兜底）。闸门**接在闸门④之后、`do_dry_run` 之前** ⇒ `--dry-run` 也反映「真实能不能打」。另加 `acceptance_gate_selftest()`（**反证自测 9 臂**，随脚本走 ⇒ 下一个版本复制脚本时自测跟着走）＋ CLI `--self-test-acceptance`（**在版本号定案/目录改名之前**早退 ⇒ 自测绝不吃版本号、零写客户包、零产出 zip）。

> **⑥【绑定范围与口径：复用既有格式，不需要新证据格式】**绑定范围 = 包内 `app/` 的**生产模块**（`.py`，排除 `pkg_exclude.is_app_dev_only`）⇒ 与 **app191 口径完全一致** ⇒ **直接复用** `ACCEPTED.json` 里既有的 `code_fingerprints` / `code_fingerprint` ⇒ **验收侧脚本（`app186` / `app_v24_build`）一字不用改**。⚠️ **README／NOTICE／MANIFEST.json 不在绑定范围内**：打包时 `sync_version_identity` 会重写 README/NOTICE、`refresh_manifest` 会重写 MANIFEST ⇒ 字节必然不同 ⇒ 属**语义必需**，不是放水（与 §207 ⑦ 同一理由）。归一化口径 = **CRLF→LF**（§119 铁律：`core.autocrlf=true`）。

> **⑦【真包现状：零漂移，交付物未受损】**实测真 v2.1／v2.2／v2.4 的 `ACCEPTED.json` 指纹与**当前包内容逐模块一致**（28/28、28/28、29/29，聚合指纹亦一致）⇒ 🔴 **本缺陷是闸门层的 fail-open（潜在），不是已发生的交付污染** —— 已交付的 v2.1 不受本轮影响，如实记录，不夸大成「交付包 ≠ 被验收过的包」。

> **⑧【证据（字节／mtime／SHA256）】**
> - `results/app/app571_ful_version_acceptance_gate_matrix.json` = **10 956 B**／**2026-11-15 10:17:14**／`9777ec8239e88fb6…`（`verdict=PASS`／`n_pass=15`／`n_fail=0`；含 `judge_selftest` 三臂）
> - 修好的 `pack_v13.py` = **111 670 B**／sha 见 `git hash-object`（改前 HEAD blob **96 183 B**／`git cat-file -s HEAD:pack_v13.py`）；**diff = 258 插入 / 0 删除**（纯增量，未动任何旧行）；**纯 CRLF、无裸 LF、无 BOM**（`CRLF=2226 / bare_LF=0`）

> **⑨【回答 §207 ⑪④：`_app500`（rc10 模板）**不**改 —— 决策与理由】**
> - **不改**：① rc10 的 zip **已交付**且 reviewer 已独立复核通过（11-13 09:00–09:05）⇒ 改历史脚本**不能改变任何已交付物**；② APP-055 **禁止重打包** ⇒ rc10 不会重建；③ **反而有害**：若把新闸门搬进 `_app500`，则「重跑 rc10 构建」会被新闸门挡死（rc10 的验收证据早于绑定机制 ⇒ 同 §207 ⑧ 的 `NO_CONTENT_BINDING`）⇒ 给历史脚本制造新的死路。
> - **改为保证「缺陷不再继承」**：MiniMVP 链是「复制上一版脚本改常量」⇒ 下一版 rc12 应复制 **rc11 的 `_app524`（已修）** ⇒ 缺陷**不再逐版继承**；且 `_app524` 内已内置 `acceptance_gate_selftest` ⇒ **自测跟着脚本走**（下一版复制即带走）。
> - 🔴 **请 reviewer 确认这条链向约定**（rc12 复制 rc11 的 `_app524`，而不是回头复制 `_app500`）。

> **⑩【纪律】****未打包**（sp2 仍无 zip；**用户不通知不打包**）｜**零客户包写入**（本轮 21 个客户包目录写入文件数 = **0**；真包只做只读判定，变异只在**临时副本**上做）｜**未改产品代码**（`live_caption/` 零改动；`pack_v13.py` 是**交付脚本**，不是产品代码）｜**未改 `CORRECTIONS_APP.md`**（只读、未入库、未提交）｜未跑推理 ⇒ **未取 `MACHINE_LOCK`**｜未调 MiniMax｜未动 B 机文件｜**逐文件** `git add`（未用 `-A`）。

> **⑪ 本条需等 reviewer 复核**：① 「完整版形态从未被审过 / 闸门层 fail-open」这一定性 ② 新闸门⑤的**改法**（身份绑定＋内容绑定，fail-closed）③ **绑定范围**＝生产模块 `.py`、复用既有 `ACCEPTED.json` 格式（**不动验收侧**）、README/NOTICE/MANIFEST 排除的理由 ④ **`_app500` 不改**的决策与「rc12 复制 rc11 `_app524`」的链向约定 ⑤ **闸门⑤对「合法但未重签 ACCEPTED」的包会拦**（如：升版改名后未重签）⇒ 这是 APP-055「重签 ACCEPTED」纪律的机械化，**是否需要给非交付场景留出口**（例如 `--allow-unaccepted`）**请裁定** ⑥ 沿用未变：**sp2 的 zip**（须**用户通知**）／§194 ④ `tag`／**TTS 默认不丢句**（6.0→0）／**OPEN-1**（0xC0000409）／10 个缺陷包作废还是标注／**v2.5 何时打**（必须带 APP-086·2a 收窄）／EXT 换嵌通知／目标机 SHA256 对账（需**开机＋凭据**）／§206 ⑨③ `cuda_env` 树 sha256 范围仍待裁定。

> **⑫【与「待命期不新增 § 章节」的偏离 —— 如实申报】**本轮**确实无新 reviewer 纠偏**，但产出**一项可复算的交付闸门层真缺陷**及其修法、鉴别力矩阵与反证组 ⇒ 写入本节并按 **40 000 B** 限额**归档 §207**（整块逐字）⇒ **新增 § 章节 1 节（§208）／归档件 1 个／companion 1 个／客户包写入 0 个文件／未打包**。

> **⑬【本轮自检抓到的真问题（都已在落盘前修掉）】**① 闸门自测首版**顺序写错**（`correct_accepted_allowed` 那一臂跑在 `ACCEPTED.json` 落盘**之前** ⇒ 该臂拿到 `NO_ACCEPTED`，随后 `os.remove` 抛 `FileNotFoundError`）⇒ 已改为**先落盘再断言**；② 本机**安全删除 shim**（删除转回收站、`FileNotFoundError` 不吞）⇒ 自测里改用 `_rm()` 助手（吞 `FileNotFoundError`）**且只在临时目录删**；③ 矩阵脚本首版 `acceptance_touching_gates()` 有一行**自造的错误判据**（`n.func` 不存在 ⇒ `AttributeError`）⇒ 已删；④ 矩阵脚本首版**只统计不判定**（会漏掉「放行但没产出 zip」）⇒ 已加 M2 判据 + 断言；⑤ 压 STATUS 正文的辅助脚本把 `SEC208_BODY` 的**首行连同 `r'''` 开引号一起替换掉** ⇒ 写手脚本 `SyntaxError` ⇒ 已用 `_app576` 补回并把压紧逻辑改成「**只替换引号之后的部分**」。

> **⑭【逐字节复核】**写 `STATUS_APP.md` 一律「**临时文件 → `os.replace`**」＋ 写后**逐字节复核**：§207 归档件正文块**逐字命中**（SHA 见该节末）／活文档其余部分**逐字未变**／**还原式复核**（把 §207 的指针行换回原文 ＋ 退回本轮授权改动 ⇒ 与开工备份**逐字节相同**）⇒ 独立复核脚本 `_app577_verify_status_sec208.py` 判定 **PASS**。
\n
