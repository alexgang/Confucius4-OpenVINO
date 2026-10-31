### §118 ✅ **无新纠偏条目（`last_ack` 仍 APP-051）｜ 按 APP-046 继续做 ⇒ 抓到 3 个真缺陷：① §117 验收链产物一个都没入库 ② HEAD 上 fresh clone 打包必失败 ③ 验收链脚本「写死仓库根」导致 clone 验收是假象** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

> 🔴 **本节只追加，不改旧章节**；旧结论被本轮推翻的地方写在 ④「撤回 / 更正」里。
> 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入）⇒ 该文件本轮开工前 mtime `2026-10-31 10:48:42` / 120 787 B / SHA256 `327f8653b62f28b602bb9f50171d1bb453eb1c722adeb0988856d91b01339904`（**零改动**，本轮收尾复核一致）。
> 🔴 **本轮巡检**：`## APP-xxx` **51** 条（APP-001 … APP-051），最大 **APP-051** = `last_ack` ⇒ **无新纠偏条目**（**第 32 次**同一口径复核）⇒ `last_ack` **不变** ⇒ 按 **APP-046**「追平后仍有未完成项 ⇒ 直接继续做，不空转」推进。
> 🔴 **本轮未取机器锁、未打包、未重打 zip、未发 FTP**（全程只读 + 离线判据，**不计时** ⇒ 不需要锁；且守 **APP-035** FTP 永久关闭 / 用户「未经通知不主动打包」）。
> 🔴 **本轮未在 CPU 上跑推理或测速**；**未调 MiniMax**（质量判定仍交 reviewer）。

#### ① 🔴 **巡检 + 半交付四层自查（§104 归纳）**

| 层 | 检查项 | 本轮实测 | 结论 |
|---|---|---|---|
| ① zip 旧 | 交付 zip 是否含本轮代码 | zip mtime `2026-11-01 00:55:58`；仓库 `live_caption`/`results/app`/`status/app` 下**无 .py 晚于 00:56** | ✅ 不旧 |
| ② 包目录内容不合规 | 包目录是否含内部素材等 | §117 已验（§48 闸门 0 违规 / 内部素材 0 / 克隆音色 0） | ✅ 合规 |
| ③ 包目录代码 ≠ 仓库 | 仓库 `live_caption/*.py` ⇄ 包 `app/*.py` | **28 个 .py 归一化行尾后逐字节一致，MISMATCH=0** | ✅ 一致 |
| ④ 🆕 **产物本身没进仓库** | STATUS 引用的每个产物是否 `git ls-files` 在册 | **❌ 3 份证据 + 7 个生产者脚本未入库** | 🔴 **本轮修掉** |

🔴 **第 ④ 层怎么发现的**：不是靠 commit message 自述（**§104 的教训：自述不算数**），
而是**逐文件 `git ls-files --error-unmatch` 逐个核**。
⇒ 本轮据此新增了可执行闸门 `app187`（见 ③）。

#### ② 🔴🔴🔴 **三个真缺陷（本轮修掉）**

**缺陷 ①：§117 的验收链产物一个都没入库**（§104 已犯过一次的同类错误，**复发**）

§117 的 commit `d866c47` 只入了 `app183`/`app184`/`app185`/`app186`（18 文件），
而总闸门 `app186` 校验的 **3 份子项证据**及其 **7 个生产者脚本** **全部未跟踪**：

| 产物 | §117 的结论 | 本轮开工时入库状态 |
|---|---|---|
| `results/app/app186_app051_acceptance_gate.py`（总闸门） | 「已入库」 | ✅ TRACKED |
| `results/app/app181_pythonw_coldstart_v2_evidence.json` | 「子项①的证据」 | ❌ **UNTRACKED** |
| `results/app/app175_app043_clone_acceptance_evidence.json` | 「子项②的证据」 | ❌ **UNTRACKED** |
| `results/app/app179_app042_gui_accel_evidence.json` | 「子项③的证据」 | ❌ **UNTRACKED** |
| `results/app/app183_app042_formula_evidence.json` | 「子项③的证据」 | ✅ TRACKED |
| `results/app/app185_app048_gui_layout_pkg_evidence.json` | 「子项④的证据」 | ✅ TRACKED |
| `results/app/app184_app051_accel_listen_manifest.json` | 「子项⑤的清单」 | ✅ TRACKED |
| `app175`/`app176`/`app177`/`app178`/`app179`/`app180`/`app181`/`app182`（8 个脚本） | 未提及 | ❌ **UNTRACKED** |

⇒ **后果**：fresh clone 跑 `app186` ⇒ 找不到 3 份证据 ⇒ 报 FAIL ⇒
「**已交付**」在别人机器上**不成立**。
⇒ ✅ **本轮补交 16 个文件**（8 脚本 + 8 证据/manifest），逐文件 `git add`（**未用 `-A`**）。

**缺陷 ②：🔴🔴🔴 HEAD 上 fresh clone 无法打包（真·断裂依赖）**

- HEAD 的 `pack_v13.py` L763/L1031 传 `--expect-version` 给 `app170_version_identity_gate.py`；
- 而 HEAD 的 `app170` **不认这个参数**（`git show HEAD:…` 实测 `expect_version` 零命中）；
- ⇒ `argparse: error: unrecognized arguments: --expect-version 1.13`
- ⇒ `check_version_identity()` 返 **rc=1** ⇒ **拒绝打包**。

🔴 **实测复现（真 fresh clone，不是模拟）**：
```
git clone --depth 1 file:///C:/Users/Trekker-PTL/confucius4-openvino /tmp/fresh_clone_test
cd /tmp/fresh_clone_test && python -c "import pack_v13; print(pack_v13.check_version_identity(<v1.13>, expect_version='1.13'))"
⇒ rc = 1   （修复前）
```
⇒ ✅ **修后同一条命令在新的 fresh clone 上 `rc = 0`**（闸门 PASS=20 / FAIL=0）。
⇒ ✅ **入库**工作区已有的 `app170` 修复（`--expect-version` + I1a/I1b 拆分：升版未刷新 `MANIFEST.version` 时降级为**提醒**，zip 级硬断言兜底）。

**缺陷 ③：验收链脚本「写死仓库根」⇒ fresh clone 验收是**假象****

`app175` / `app177` / `app184` / `app186` 四个**验收链**脚本都用
`REPO = os.path.join(HOME, 'confucius4-openvino')`（或绝对路径写死）
⇒ 脚本搬到**任何其它位置**时，它读的证据仍来自**原仓库**
⇒ 「在 clone 上跑 `app186` 通过」是**假象**（它根本没读 clone 里的文件）。

🔴 **本轮亲自踩到**：第一次跑 fresh clone 时 `app186` 报的证据路径是
`C:\Users\Trekker-PTL\confucius4-openvino\results\app\…`（**原仓库**），
而 clone 在 `C:\Users\Trekker-PTL\AppData\Local\Temp\fc3` ⇒ **验证无效**。
⇒ ✅ **修法**：仓库根改为**从本脚本自身位置推导**
`os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`。
⇒ ✅ **修后复验**：clone 内 `app186` 报的证据路径变成 `…\Temp\fc3\results\app\…`（**clone 自己**）⇒ `PASS 25 / FAIL 0 / verdict=PASS`。

#### ③ 🔴 **新增可执行闸门 `app187`（把 §104 的教训变成判据）**

- **脚本**：`results/app/app187_repo_artifact_in_repo_gate.py`（**16 380 B** / SHA256 `83ab99323f4c5ec3…`）
  ⇒ 扫 `STATUS_APP.md` 引用的每个产物路径 ⇒ 逐个核对 `git ls-files` 在册
  ⇒ **「STATUS 写了结论但产物没进库」当场暴露**。
- **三类口径**（避免误伤）：
  - `MISSING` —— 引用了但**完全没入库** ⇒ **FAIL**；
  - `DIRTY` —— 入库了但**工作区内容 ≠ HEAD 内容** ⇒ **FAIL**（别人 clone 拿到的是 HEAD）；
  - `IGNORED` —— 被 `.gitignore` 约定排除（如 `*.log`，`.gitignore` L19）⇒ **不算漏交**（否则判据恒 FAIL ⇒ 恒 FAIL 的闸门等于没有闸门）。
- 🔴 **追加「写死仓库根」检查（AST 判定）**：
  - ⚠️ **正则会误伤**：实测 `live_caption/speaker_assets.py` 的 **docstring 里正引用** ASR 侧 `REPO = r'…confucius4-openvino'` ⇒ 那是**散文**不是代码 ⇒ 假阳性会让闸门恒 FAIL。
  - ⇒ 改用 **AST**（只看真实 `Assign`/`AnnAssign`，目标名 ∈ `REPO`/`REPO_ROOT`/`REPO_DIR`）⇒ **零误伤**（docstring/注释天然不覆盖）。
  - ⇒ **范围收窄**：**只对「STATUS 引用的脚本」判 FAIL**；其余 **51 处历史一次性脚本**列为**存量清单**（`n_hardcoded_repo_backlog`，**不阻断**，供后续逐批清理）⇒ 否则闸门恒 FAIL。
- 🔴 **鉴别力实测**（`results/app/app187_discrimination_test.py`，**8 760 B** / SHA256 `6f3a6a90c6870cf5…`）⇒ **9 PASS / 0 FAIL**：
  - **对照组**：造「干净基线」（剔除引用未入库产物的行）⇒ `verdict=PASS`、**零 MISSING / 零 DIRTY**；
  - **注入组**：在干净基线上注入 **3 处**「引用未入库产物」⇒ `verdict=FAIL`、
    **恰好 3 条 MISSING**（T5 精确命中，**非「多抓了几个」取胜**）、
    **无额外 MISSING**（T7）、**已入库路径无假阳性**（T6）。
  - 🔴 **踩坑自纠**：第一版鉴别力测试把注入组建在**原 STATUS** 上 ⇒ 混入了原 STATUS 自带的真实缺陷
    ⇒ T5/T7 判 FAIL ⇒ 正是**判据把「我的测试设计缺陷」抓出来了** ⇒ 改为**注入到底稿 = 干净基线**。
- **证据**：`results/app/app187_repo_artifact_in_repo_gate_evidence.json`（**11 025 B** / SHA256 `180bd6723aa33e0a…`）
  → 原始字段：`n_candidates=38`、`n_tracked=36`、`n_missing=0`、`n_dirty=0`、`n_hardcoded_repo=0`、`n_ignored_by_convention=1`、`verdict="PASS"`。
  ⚠️ 该证据是**修完之后**的复跑结果（`DIRTY=0` / `MISSING=0`）⇒ 与「fresh clone 内跑同一闸门」的结果**一致**（**36 PASS / 0 FAIL**）。

#### ④ 🔴 **撤回 / 更正**

- 🔴 **撤回 §117 隐含的「验收链产物已入库」** —— §117 的 commit `d866c47` **只入了 18 个文件**，
  而总闸门依赖的 3 份子项证据 + 8 个生产者脚本**未入库** ⇒ §117「已交付」的**可复现性**当时**不成立**。
  ⇒ **本轮补交后成立**（fresh clone 内 `app186` = `PASS 25 / FAIL 0`）。
  ⚠️ **不撤回 §117 的业务结论**（重打 v1.13 / APP-043 五子项全 PASS / ACCEPTED.json / 快捷方式）——
  那些结论有落盘证据且**本轮在 fresh clone 上复核通过**。
- 🔴 **更正「fresh clone 能跑通打包闸门」的旧状态** —— §117 之后（HEAD=`d866c47`）**不能**（rc=1）⇒ 现（HEAD=`ae7178d`）**能**（rc=0）。
- ✅ **不撤回 §115 的 `EXECUTION_DEVICES` 口径**（本轮未触碰该路径）。

#### ⑤ 🔴 **git 收尾**

- **commit 1** `bcf8c37`（**23 个 App 职责内文件**）：16 个 §117 验收链产物 + `app170` 修复 + `app165` evidence 复跑覆盖 + `app187` 闸门与鉴别力实测（脚本 + 证据）。
- **commit 2** `ae7178d`（**6 个文件**）：`app175`/`app177`/`app184`/`app186` 的「写死仓库根」修复 + `app187` 闸门升级为 AST 判定 + 闸门证据复跑。
- 🔴 **逐文件 `git add`（未用 `-A`）**；两次 commit 的 `git show --name-only --format="" HEAD | grep -c CORRECTIONS` 均为 **0**
  ⇒ **未提交 reviewer 独占文件** `status/app/CORRECTIONS_APP.md`。
- 🔴 **未吞他模块改动**：工作区仍 **523** 项他模块改动（`live_caption/diag_c111_*`、`status/CORRECTIONS.md`、
  ASR `c0*.py`、`hy_bench` 等）**全部保留在工作区**。
- 🔴 **普通 push，未 force**；仓库仍只有 `main` 分支。

#### ⑥ 🔴 **本轮未推进（等 reviewer / 用户）**

- 🔴 **需用户实听** 3 段 1.2–1.3× 配音素材（`C:\Users\Trekker-PTL\shared\app_accel_listen\`）＋ **reviewer 判定音质 / 不变调 / 可懂** —— 本轮只覆盖**链路 + 结构 + 数字自洽**，**质量判定不在其中**。
- 🔴 **§117 待 reviewer 复核 3 项**（APP-043「通过」口径 / `app186` 总闸门 25 条判据口径 / `app186` 写死包版本的修法）—— ⚠️ 本轮已把「写死包版本」升级成「写死**仓库根**」一并修掉 ⇒ **第 ③ 项已闭环**。
- 🔴 **§115 / §114 / §113 / §112 待复核项**（见头部阻塞表）—— 本轮未触碰。
- 🔴 **存量 51 处「写死仓库根」的历史一次性脚本**（`app007_*`/`app010_*`/`app023_*` 等）—— 已列入 `app187` 的 `hardcoded_repo_backlog`，**不阻断**，供后续逐批清理。
- 🔴 **v1.12 / v1.5 等历史 zip 仍是旧内容**（**未重打**、旧包目录**未删除** —— 删除属破坏性操作，需用户确认）。
