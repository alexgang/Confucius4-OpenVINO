# §235 接续轮正文全文（2026-11-25 05:5x）

> 配套活文档：`status/app/STATUS_APP.md` 的 `## §235` 章节。
> 本文件是**活文档 §235 的完整正文**（与 §218/§219/§233/§234 同款 companion 做法）。
> **只追加**：本轮不改旧章节；旧结论若被推翻，在 §235 内写「撤回 §x」。

---

## §0 租约：TAKEOVER 接续上一会话（上一会话已死）

- `session_lease.py acquire app` ⇒ exit **0** / **TAKEOVER**
  （上一 token `14ce4ac0`，started **11-25 03:15:31**，last_beat **11-25 03:52:12**
  ＝ **114 min 前** ⇒ 死会话；note=`confirming operator-order effect`；
  `live_pids=[]` `alive=False`）⇒ 本轮 token **`d2f7f45a`**，全程 beats ⇒ 收尾 `release`。
- 🔴 **上一会话留下的状态**：`## §234` **已写入** STATUS（30 634 B／87 行）＋
  companion `status/app/STATUS_APP_sec234_detail_20261125.md`（14 311 B）；
  但**四件事一件都没做**：**未提交 / 未推送 / 未发 STATUS 邮件 / 未写当日日志与 automation memory**
  ⇒ 本轮**从断点继续**，不从头重做。

---

## §1 六通道复核：仍无新 App 纠偏 ⇒ `last_ack` 仍 **APP-133**（**值不变**）

开工指纹（`status/app/CORRECTIONS_APP.md`）：
**130 条 / max APP-133 / SHA256 `2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda` /
440 181 B / mtime 2026-11-24 13:56:42**（与 §232／§233／§234 轮**逐字一致**
⇒ 本轮期间**无人追加**）。

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| 1 | 局域网 `status/app/CORRECTIONS_APP.md` | 130 条／max **APP-133**／SHA `2db65bf1…`／440 181 B／mtime 11-24 13:56:42 | 无新条目 |
| 2 | QQ 收件箱（reviewer `alexchen7694@agent.qq.com`） | 最新 App 封仍 = **APP-133**（`msg_HbiVRXlg…`，11-24 05:56:40Z）＝**已执行**；其后仅 **H-028 [MT]**（`msg_23BciIYN…`，11-24 10:11:12Z ＝ 18:11 GMT+8），正文明写「本条只做 MT 模块的模型侧工作，**不要改 App 代码和任何客户包**；App 侧替换由 reviewer 在本条验收后**另发 APP 纠偏**」 | **不据此动 App 代码** |
| 3 | QQ 垃圾箱（spam） | **0 封**（空） | 空 |
| 4 | QQ 已删除（trash） | 1 封＝MiniMVP rc9 性能报告（11-13，**无关**） | 无关 |
| 5 | 全仓 `APP-134+` 检索 | 命中 **0**（唯 2 处 `APP-178` 是 `results/app/win_capture.py` 注释里的历史编号；`APP-134+` 命中全在**本模块自己发的**记忆/邮件正文里的否定式表述） | 无新条目 |
| 6 | 根 `status/CORRECTIONS.md` | 119 条／max **C-135**（已冻结） | 与 App 无关 |
| ＋ | `shared/NOTICE*` | 最新仍 **11-05 09:35** | 无新通知 |
| ＋ | QQ 已发箱 | 最新 App 封 = **§233** 的 `msg_20-nHCSHXAk9kUm3XTwenP4ahiiluV1WvXRsRdj_8VqDzQ`（11-24 18:06:48Z）⇒ **§234 的邮件上一会话没发** | 本轮补发 |

⇒ **本地 max（APP-133）＝ QQ max（APP-133）＝ `last_ack`（APP-133）** ⇒
**无新 App 纠偏** ⇒ **`last_ack` 不变**（头部仍 `APP-133`）。

---

## §2 独立复核 §234 的 3 处修法（**不直接采信上一会话的结论**）

上一会话留下的 3 处修法全部**重跑复现**（各脚本均含**反证组**）：

| 脚本 | 判据 | 结果 |
|---|---|---|
| `results/app/_app234_verify_patch.py` | `_app129_build_v26.py` 改动：`ast`／唯一命中／**正向重建**＝备份＋3 处已知编辑⇒逐行等于现文件／行尾风格／`git diff --numstat`／**反证组** | **11/11 PASS** |
| `results/app/_app234_verify_identity_tool.py` | `sync_pkg_identity` **行为级真跑**（影子包，真包只读）：A 组 10 条／B 组 2 条（**APP-055 护栏**）／C 组 1 条（真包 4 文件逐字节一致） | **17/17 PASS** |
| `results/app/_app234_verify_anchor_fix.py` | 缺陷③修法：真实 v2.7 成包路径（robocopy v2.6 ⇒ v2.7）／`unique_anchor` 单元行为／**反证组**（换成恒不扩展的旧行为 ⇒ rc≠0）／真包隔离 | **16/16 PASS** |

⇒ **§234 的 3 处修法成立**（本轮独立复现，非转述）。

---

## §3 🟢 修掉 2 处**新**真缺陷（本轮发现）

### 缺陷④（🟡 判据自身缺陷 ⇒ 假 FAIL）`_app234_verify_status.py` 判据 9 恒 FAIL

- **实测**：直接跑上一会话最后写的（03:52，**死前没来得及跑**）复核脚本 ⇒
  **PASS=13 / FAIL=1**，FAIL 项＝判据 9「还原式复核」，
  detail = `len 18244 vs 18250` ⇒ **短 6 个字符**。
- **根因（不是 STATUS 的缺陷，是判据的缺陷）**：判据 9 把整串
  `'更新时间: <ts>'` 替换成**只有时间戳**，**丢掉了 `更新时间: ` 这 6 个字符**
  （4 汉字 + `:` + 空格）⇒ 还原串永远比备份短 6 字符 ⇒ **恒 FAIL**。
- **独立验证**：把该替换改成「连同 `更新时间: ` 前缀一起替换」后
  ⇒ 还原串 **18 250 字符 ＝ 备份 18 250 字符**，且 **逐字节相等**
  （`b.encode('utf-8') == 备份文件字节` ⇒ True）
  ⇒ **STATUS 正文本身没有缺陷**（§234 的写入是干净的）。
- **修法**：修判据（保留前缀）＋ **新增反证组 9b**
  （把还原串**中段挖掉 1 个字符** ⇒ 判据 9 必须 FAIL ⇒ 证明不是恒 PASS）
  ⇒ 重跑 **15/15 PASS**（修正前 13/14）。
- **判据坑（已下沉 MEMORY_MODULES 附录·五十二）**：🔴 **「替换时丢掉定长前缀」**
  ⇒ 还原式复核出现**固定的字符差**（6 字符 = `更新时间: ` 的长度）
  ⇒ **先量差值**（6 字符 ＝ 4 汉字＋`:`＋空格 ⇒ 指向前缀）
  ⇒ **别改被检对象去迎合判据**。

### 🟡 本轮**自己写**的复核脚本也踩了同一个坑（同源，已改正）

`results/app/_app235_verify_status.py` 初版的**反证组 13** 写的是
「移除 §235 后判据 3/4/5 必须 FAIL」⇒ 实测 **FAIL**。
**根因**：判据 5（「末行以 `> ` 开头」）**不具鉴别力** ——
移除 §235 章节后，末行变成 **§234 的 pointer 行**（**同样**以 `> ` 开头）
⇒ 判据 5 仍成立 ⇒ 把它算进反证组 = **恒 FAIL 的假 FAIL**。
⇒ 改法：反证组只保留**有鉴别力**的判据（3/4），
并在判据旁写明**为什么 5 不能进** ⇒ 改正后 **17/17 PASS**。
⇒ 与缺陷④**同源**：都是「**判据绑错了对象**」。
⇒ 🔴 **判据自己也要被反证组审**：写完判据先问
「这条在**去掉被检对象**后会不会仍成立？仍成立 ⇒ 它没鉴别力 ⇒ 不能进反证组」。

### 缺陷⑤（🔴 **生产路径**缺陷）`sync_pkg_identity.py` 会用**影子包**结果**覆盖**交付包的闸门记录

- **实测**：上一会话在工作区里把规范证据
  `results/app/app170_version_identity_gate_evidence.json` 改成了
  `pkg = %TEMP%\app234_id_klh3m45v\Confucius4_LiveCaption_v2.10`、
  `pkg_version = 2.10`、**`pass` 从 19 变 20**、
  且真实包那两条**真实 advisory**（I1b `manifest=2.5 target=2.6`、
  D4 `count=2`）**整条消失**。
- **根因（生产路径，不是 harness）**：`sync_pkg_identity.py` **无条件**把
  app170 闸门证据写到**规范路径**
  `results/app/app170_version_identity_gate_evidence.json`
  ⇒ 在**任何**影子包／临时目录上跑一次，就会**覆盖**「交付包的闸门记录」。
- **危害**：① 规范证据的 `pkg` 指向**跑完即删**的临时目录 ⇒ reviewer **无法复算**；
  ② 真实包的两条**真实缺陷提示**（MANIFEST.version 未刷新、README 双标题）**被抹掉**
  ⇒ **审计链断**（规范证据不再描述任何真实交付包）。
- **修法（改生产路径，不只改 harness）**：
  - **交付候选包** ⇒ 闸门证据写**规范文件**（与 `pack_v13` 的既定约定一致）；
  - **非交付包**（影子包／`%TEMP%` 临时目录）⇒ 闸门证据写**临时文件**并
    **用后删除** ⇒ ① **绝不覆盖**交付包的规范记录 ② **零仓库污染**；
  - 判定函数 `_is_delivery_pkg()`：目录名须匹配 `Confucius4_LiveCaption_vX.Y`
    **且**不在 `%TEMP%` 之下（MiniMVP 目录名不匹配 ⇒ 不碰）。
- **收尾**：规范证据已用**真实交付包 v2.6** 重刷（rc=**0**，
  `pass=19 / fail=0 / verdict=PASS`，两条 advisory 回到位）
  ⇒ **与 HEAD 逐字节相同**（`git diff --stat` 空）。

### 本轮独立行为级复核：**25/25 PASS**

`results/app/_app235_verify_evidence_scope.py`：

| 组 | 判据 | 条数 |
|---|---|---|
| A | 影子包（`%TEMP%`）⇒ 规范证据**逐字节不变**＋**零新增文件**＋闸门**确实跑了**＋影子确实被同步 | 5 |
| B | `_is_delivery_pkg` 单元行为（交付候选／`%TEMP%` 影子／MiniMVP／非交付名） | 6 |
| C | **反证组**：注入「无条件写规范路径」的**旧行为** ⇒ 规范证据**必须**被改 ⇒ 判据有鉴别力；反证后逐字节还原 | 3 |
| D | **「非空洞」检查**：交付候选目录名 ⇒ 规范证据**必须**被更新 ⇒ 否则 A1 可能只是「工具根本不写」而恒 PASS | 4 |
| E | 收尾：规范证据用**真实交付包**重刷并复核（`pkg`／`pass=19`／两条 advisory）＋真包 4 身份文件未变＋零新增文件 | 5 |

---

## §4 交付面**只读**复核（真包 `Confucius4_LiveCaption_v2.6` 本轮未被改动）

- 真包 **48 792** 个文件，跑前跑后 **0 个变化**（size+mtime 全量快照比对）
- 真包 4 个身份文件 SHA256（跑前跑后**一致**）：
  `README_zh.md` `0bb23e7cfa39f24d…`／`README_en.md` `6d67d4d690b2fc0c…`／
  `NOTICE` `22d70a34316d4e49…`／`app\MANIFEST.json` `84a08d895da4aaa0…`。
- `ACCEPTED.json` 复核：`version=2.6`／`accepted_at=2026-11-24 18:26:21`／
  `corrections=[APP-129,130,131,132,133,123]`／`ext=v0.4.21(b2a4978)`／
  `n_production_modules=33`（**未改**）。
- 🔴 **真包的两处已知缺陷仍在**（按 **APP-055 禁止原地改已签包**）：
  ① `README_zh.md` 的 `## v2.6 改动说明` 出现 **2 次**；
  ② `app/MANIFEST.json` 的 `version` 仍为 **2.5**。
  ⇒ **是否出 v2.7 待裁定**（§233／§234 已两次登记）。

---

## §5 🔴 如实登记：**未修** / **待裁定**项

1. 🔴 **真包 v2.6 的两处缺陷仍在** ⇒ 按 APP-055 **不原地改已签 ACCEPTED 的包**
   ⇒ **是否出 v2.7 待裁定**（§233／§234／§235 **第三次**登记）。
2. 🔴 **`results/app/app231_pack_lock_events.jsonl` 仍不存在且未入库**
   （§233／§234 已登记；它是修好后的**生产路径**在**运行时**才产出的文件
   ⇒ v2.6 那次构建跑在修复提交**之前** ⇒ **不伪造空文件**）。
3. 🔴 **`Confucius4_LiveCaption_v2.6.staging` 残留 25 GB** ⇒ 删除属**破坏性**操作
   ⇒ **未删**，待授权。
4. 🔴 **`v2.5` 的 `ACCEPTED.json` 仍指向 v2.4**（**未重签**）；`v2.5` 无 zip。
5. 🔴 **仓库根 `.gitattributes` 根治**（854 个 `i/lf+w/crlf`）**跨模块** ⇒ 待裁定。
6. 🔴 **默认分离设备**、**`n_speakers=0` 口径** ⇒ 仍待 reviewer 裁定。
7. 🟡 `results/app/app234_app170_gate_evidence.json`（本轮**保留**的上一会话影子证据）
   其 `pkg` 指向**已删除的临时目录** ⇒ **不可复算** ⇒ **仅作审计痕迹**；
   **规范证据**已用真实交付包重刷（见 §3 缺陷⑤收尾）。
8. 🟡 `live_caption/release_notes/` 约定 vs 历史私有命名
   （`_appNNN_changelog_vX.Y_{zh,en}.md`）**不一致** ⇒ `sync_pkg_identity` 两条都支持
   ⇒ **不强制迁移**；**下一版建议**按约定放 `release_notes/vX.Y_{zh,en}.md`。

---

## §6 纪律自查

- 🟢 **未打包 zip**（用户级纪律「**不通知 ⇒ 不打包**」）⇒ **无新 zip**；
  旧目录 / 旧 zip **未覆盖、未删除**。
- 🟢 **未改任何客户包**（真包 48 792 文件 0 变化；4 个身份文件 SHA256 一致）。
- 🟢 **未跑推理 / 未测速** ⇒ **未取 `MACHINE_LOCK`**（本轮无计时类作业）。
- 🟢 **未调 MiniMax**（质量判定留给 reviewer）；**未连 B 机**；**未进 MiniMVP 包**。
- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ SHA 零改动）。
- 🟢 只 `git add` **App 侧**文件；**未吞** ASR/MT/TTS 其它模块的未提交改动。
- 🟢 **未 force push**；仓库只保留 `main` 分支。
- 🟢 只写 `status/app/STATUS_APP.md`（**追加** `## §235`）＋ 本 companion；
  旧章节**未回头改**。

---

## §7 下一轮

- `last_ack` 仍 **APP-133**。
- ⏭ 等 reviewer 复核 **§234**（3 处修法 ＋ 独立复现）与 **§235**（2 处新修法）。
- 🔴 **待裁定**：**是否出 v2.7**（带 §233/§234/§235 的修法）／**是否删** `.staging`（25 GB）／
  **v2.5 重签 ACCEPTED**／仓库根 `.gitattributes` 根治／默认分离设备／
  `n_speakers=0` 口径。
- 🟢 **v2.7 若成包**：`python live_caption/_app129_build_v26.py --stage identity`
  （或 `--stage all`）⇒ 版本标识**自动**同步 ＋ 闸门 ＋ 硬断言 ⇒ **不再需要人工带外**；
  且**影子/临时目录不会**再覆盖交付包的闸门证据记录。
