# STATUS_APP §206 完整正文（companion，2026-11-14）

归档原因：活文档逼近 **40 000 B** 上限（APP-052④）⇒ §206 完整正文放 companion，
活文档只留摘要（§206 标题行 ＋ 摘要条目 ＋ 指针行）。
生成时间：2026-11-14 22:05:11

§206 正文块 SHA256（标题行 ＋ 摘要条目 ＋ 明细；不含活文档那一行指针）：c560fe781bfd6979a68fd19c5bafa1418e43582b53376757c242e2b86fe0b334（9789 B）

---- 以下为 §206 完整正文，逐字 ----
## §206 巡检（**无新 reviewer 纠偏**，last_ack 仍 **APP-109**）｜🔴 **修掉出包闸门的真缺陷：7.86 GiB / 96 个模型文件不在内容绑定范围内 ⇒ 验收后换掉模型照样能出包**｜**鉴别力矩阵 12/12 PASS（改前 5 臂 fail-open）**｜**未打包／零客户包写入／未改产品代码**｜**本条需等 reviewer 复核**
> **① 纠偏文件复核（只读、未改、未入库、未提交）**：开工＝收尾 **109 条**／最大 **APP-109**／SHA256 `30a55189…`／**360 842 B**／mtime **2026-11-14 15:38:28** ⇒ **逐字一致 ⇒ SHA 零改动**；`last_ack` **仍 APP-109**（无新纠偏 ⇒ **不写自己的编号**）⇒ 本轮无新条目可执行。
> **② 其它 5 通道全空**：agent-mail **`not_bound`**（**连续第 9 轮**不可查——面板已连通但**工具未开通** ⇒ 该通道**查不了**，不是「查过为空」）｜`conversation_search` **0 命中**｜`shared/NOTICE*` 最新仍 **11-05 09:35**｜git `origin/main...main`＝**0/0**（HEAD `b884d29`）｜`MACHINE_LOCK` **NOT_PRESENT**｜ASR 侧最大 **ASR-058**（无 App 条目）｜根 `status/CORRECTIONS.md` 最大 **C-135**。
> **③【真缺陷（闸门层，**传递绑定**）：7.86 GiB / 96 个模型文件不在内容绑定范围内 ⇒ 验收后换掉模型照样能出包】**§205 的 `pkg_content` 只绑「代码＋元数据」**31 个文件**；模型 SHA256 **只**记在包内 `app/MANIFEST.json`（验收 A4「登记 96 个，一致 96，不一致 0」即拿它逐文件重算）⇒ 闸门**从不再验那条传递链** ⇒ **验收后换掉模型／塞未登记文件，闸门照样 ALLOW**，而验收记录会（不实地）声称模型身份已核过 ⇒ **交付包里的模型 ≠ 被验收过的模型**。
> **④【鉴别力矩阵 `app567`，12 臂 ⇒ PASS】**改前臂＝**`git cat-file blob HEAD:` 的闸门逐字原文**（**AST 抽函数、不 import**）｜改后臂＝修好的脚本；两臂都对**临时目录假包**真跑 ⇒ **零写客户包、不出 zip**。**改前 fail-open 5 臂**：T2 换模型／T3 `models/` 塞未登记文件／T4 删模型／T6 `app/`**子目录**新增 .py／T11 MANIFEST 指向别的包 ⇒ **改前 ALLOW、改后 BLOCK**；回归臂 T1·T5·T7·T8·T9·T10·T12 ⇒ **两臂 BLOCK/BLOCK 不变**。
> **⑤【修法（只改交付脚本；产品代码零改动）】**① 新增 `check_manifest_model_binding()`：**逐条重算** MANIFEST 登记的模型 SHA256 ＋ **反向集合校验**（`models/` 实际集合须与登记集合**完全相等**）＋ **MANIFEST 自洽**（`pkg_models_root` 须指向**本包** ⇒ 顺带把 §205 真缺陷①在**闸门**上也拦住）；② `app/` 的 .py 反向集合校验由**顶层**改**递归**；③ **fail-closed 顺序**：两遍体积「是否收敛」的判定原写在 `os.replace(tmp, ZIP)` **之后** ⇒ 不收敛时**未收敛的 zip 已落在最终路径** ⇒ 改为**先判定收敛再落位**。
> **⑥【真包复验（零写入）】**`--check-only` 跑**真 sp2** ⇒ **闸门 PASS**：verdict「PASS（有 1 项未结：退出码异常）」／`release.json.version='1.0-sp2'`／内容绑定 **31 文件**（`tree_digest=08949bd2…`）／**模型绑定 8 模型 / 96 文件逐条重算一致**；耗时 **4.6 s**（7.86 GiB）⇒ **无假 FAIL**。**21 个客户包目录本轮写入文件数 ＝ 0**（逐目录扫 mtime，最新仍是 sp2 的 11-14 20:50:12）。
> **⑦【证据（字节／mtime／SHA256）】**`app567_zip_manifest_binding_matrix.json`＝**5 237 B**／**22:04:47**／`9228ebfc…`（`n_pass=12`／`n_fail=0`）；矩阵脚本＝**12 277 B**／`0aede441…`；修好的 `_app537_zip_specialmvp.py`＝**24 854 B**／**22:04:21**／`384b2de4…`（改前 **17 903 B**／`9dba1bea…`）。
> **⑧【纪律】****未打包**（sp2 仍无 zip；`shared/specialmvp/` 仍只有 sp1 的 14 244 490 059 B）｜**零客户包写入**｜**未改产品代码**（`live_caption/`、`pack_v13.py` 零改动）｜**未改 `CORRECTIONS_APP.md`**（只读、未入库、未提交）｜未跑推理 ⇒ 未取 `MACHINE_LOCK`｜未调 MiniMax｜未动 B 机文件｜**逐文件** `git add`（未用 `-A`）。
> **⑨ 本条需等 reviewer 复核**：① 传递绑定定性 ② 闸门改动（模型重算＋反向集合＋MANIFEST 自洽＋递归 .py＋落位顺序）③ **仍有的缺口**：`cuda_env/` **30 731 文件 / 4.68 GiB** **零 sha256**（验收与闸门都不管）⇒ 本轮**未擅自扩范围**（扩它要动你正在复核的 §205 证据）⇒ 请裁定是否记 `cuda_env` 树摘要；④ 沿用未变：**sp2 的 zip**（须**用户通知**）／§194 ④ `tag`／**TTS 默认不丢句**（6.0→0）／**OPEN-1**（0xC0000409）／10 个缺陷包作废还是标注／**v2.5 何时打**（必须带收窄）／EXT 换嵌通知／目标机 SHA256 对账（需**开机＋凭据**）。
> **⑩【与 APP-085 §2「待命期不新增 § 章节」的偏离 —— 如实申报】**本轮**确实无新纠偏**，但产出**一项可复算的交付闸门层真缺陷**及其修法与鉴别力矩阵 ⇒ 写入本节并按 40 000 B 限额归档 §205 ⇒ **新增 § 章节 1 节（§206）／归档件 1 个／companion 1 个／客户包写入 0 个文件**。

#### §206 明细（companion 专有）

**① 判据矩阵逐条（`results/app/app567_zip_manifest_binding_matrix.json`）**

| 臂 | 场景 | 改前（HEAD blob） | 改后（修好的脚本） | 改后拦下的理由（摘） |
|---|---|---|---|---|
| T1 | 未改动（回归守卫） | ALLOW | ALLOW | — |
| T2 | 模型文件内容被换 | **ALLOW（fail-open）** | **BLOCK** | 模型内容已变 models/m1/w.bin |
| T3 | `models/` 下塞未登记文件 | **ALLOW（fail-open）** | **BLOCK** | models/ 下有未登记的文件 |
| T4 | 模型文件被删 | **ALLOW（fail-open）** | **BLOCK** | 缺模型文件 models/m1/w.bin |
| T5 | `app/` 顶层新增 .py | BLOCK | BLOCK | 验收后新增 .py（改前已拦） |
| T6 | `app/` **子目录**新增 .py | **ALLOW（fail-open）** | **BLOCK** | 验收后新增 .py（递归后） |
| T7 | `app/a.py` 内容被改 | BLOCK | BLOCK | 内容已变 app/a.py |
| T8 | 证据属于另一个包（§204 回归） | BLOCK | BLOCK | 验收证据属于另一个包 |
| T9 | 验收 verdict=FAIL | BLOCK | BLOCK | 包上验收未通过 |
| T10 | 证据无 `pkg_content`（§205 回归） | BLOCK | BLOCK | 缺内容绑定字段 |
| T11 | MANIFEST 指向别的包的 models | **ALLOW（fail-open）** | **BLOCK** | pkg_models_root 指向的不是本包 |
| T12 | `release.json` 版本与目录名不符 | BLOCK | BLOCK | 版本标识不自洽 |

**② 两臂的取样方式（判据本身可复算）**

- 改前臂源码＝`git cat-file blob HEAD:results/app/_app537_zip_specialmvp.py` 的**逐字原文**（不是「我以为修复前的行为」）；
- 两臂都用 `ast.parse` **只抽函数定义**（`sha256_file` / `_norm_pkg` / `_verdict_ok` / `check_acceptance` / `check_release_identity` / `check_content_binding`〔／改后另有 `check_manifest_model_binding`〕）再 `exec` ⇒ **不 import、不执行脚本主体**（脚本主体的 argparse 与闸门流程一律不跑）⇒ **零副作用**；
- 被测对象＝**临时目录里的假包**（结构与 Special MVP 同形：`app/*.py` ＋ `release.json` ＋ `package_profile.json` ＋ `app/MANIFEST.json` ＋ `models/m1/` ＋ 一份同形的验收证据）⇒ **零写真实客户包、零出 zip**；
- 判据断言：改前臂**不得**含 `check_manifest_model_binding`（HEAD blob 与工作区一致性自检）、改后臂**必须**含 ⇒ 两臂不会「碰巧一样」。

**③ 闸门改动逐条（只改 `results/app/_app537_zip_specialmvp.py`；产品代码零改动）**

| 位置 | 改前 | 改后 |
|---|---|---|
| 新增 `check_manifest_model_binding()` | — | 逐条重算 MANIFEST 登记的模型 SHA256 ＋ 反向集合校验 ＋ MANIFEST 自洽 |
| `check_content_binding()` 的 .py 反向集合 | `os.listdir(app)`（**仅顶层**） | `os.walk(app)`（**递归**） |
| 两遍体积收敛判定 | 在 `os.replace(tmp, ZIP)` **之后** | 在 `os.replace(tmp, ZIP)` **之前**（fail-closed 顺序） |
| `--check-only` 输出 | 只报内容绑定 | 另报「模型绑定 N 个模型 / M 个文件」 |

**④ 字节级证据（本轮）**

| 文件 | 字节 | mtime | SHA256(前 16) |
|---|---|---|---|
| `results/app/_app537_zip_specialmvp.py`（修好） | 24 854 | 2026-11-14 22:04:21 | `384b2de4782859a9` |
| `results/app/_app537_zip_specialmvp.py`（改前 HEAD） | 17 903 | 2026-11-14 20:49:23 | `9dba1bea…` |
| `results/app/_app567_zip_manifest_binding_matrix.py` | 12 277 | 2026-11-14 22:04:45 | `0aede441c6579d2b` |
| `results/app/app567_zip_manifest_binding_matrix.json` | 5 237 | 2026-11-14 22:04:47 | `9228ebfc593787da` |
| `status/app/STATUS_APP_sec206_detail_20261114.md`（本件） | 见文件末 | 2026-11-14 22:05:11 | 见文件末 |
| `status/archive/STATUS_APP_sec205_20261114.md` | 见文件末 | 2026-11-14 22:05:11 | 见文件末 |

**⑤ 真包复验输出（`--check-only`，零写入）**

```
闸门 PASS：验收 verdict='PASS（有 1 项未结：退出码异常）'（证据属于 …SpecialMVP_v1.0-sp2）
            release.json.version='1.0-sp2'（目录名 Confucius4_LiveCaption_SpecialMVP_v1.0-sp2）
⚠️ 验收带未结项（已随证据带入 zip 报告）：['OPEN-1']
            内容绑定：31 个文件，tree_digest=08949bd2a3a6ba71…
            模型绑定：8 个模型 / 96 个文件逐条重算 SHA256 一致
check-only：**未写任何文件**（未出 zip、未改 README）
```

（耗时 **4.6 s** ／ 实测覆盖 **7 866 706 947 B** 模型字节；`cuda_env/` 不在绑定范围，故未纳入本次重算。）