# STATUS_APP §236 正文（2026-11-25 07:38）

> 本文件是 `status/app/STATUS_APP.md` 的 **§236 节正文**（活文档只留标题行 ＋ 指针行）。
> 依据：APP-052④（STATUS ≤40 000 B / ≤300 行）＋ MEMORY「§9 压缩 STATUS」。

---

## §0 本轮性质与依据

- **六通道复核 ⇒ 仍无新 App 纠偏** ⇒ **`last_ack` 仍 APP-133**（值不变，见 §1）。
- 本轮**不是**待命轮空转：复核中发现 **3 处真缺陷 ＋ 1 处安全缺口**，已逐条修复并独立复核。
- 🔴 本轮**未打包**（用户级纪律「不通知 ⇒ 不打包」）、**未跑推理/测速**（⇒ 未取 `MACHINE_LOCK`）、
  **未调 MiniMax**、**未连 B 机**、**未改任何客户包**、**未改 `CORRECTIONS_APP.md`**。

---

## §1 六通道逐通道证据（复核时刻：2026-11-25 07:02–07:38）

| 通道 | 结果 | 证据 |
|---|---|---|
| ① 局域网 `status/app/CORRECTIONS_APP.md` | **130 条／max APP-133** | SHA256 `2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda`／**440 181 B**／mtime **2026-11-24 13:56:42** |
| ② QQ 收件箱 | 最新 App 封仍 = **APP-133**（`msg_HbiVRXlgp8eXsg7kDK4uUcgmLi_ao2pMbVJcZzbdbNhmGw`，05:56:40Z）＝**已执行** | 其后仅 **H-028 [MT]**（10:11:12Z，正文明写「**不要改 App 代码和任何客户包**」）⇒ **不据此动 App 代码** |
| ③ QQ 垃圾箱／已删除 | **0**／**1**（MiniMVP rc9 报告，无关） | `ListMessages(spam/trash)` |
| ④ 根 `status/CORRECTIONS.md` | max **C-135**（本文件已冻结） | `## C-135`（2026-10-23） |
| ⑤ `shared/NOTICE*` | 仍 ≤ **11-05**（最新 `NOTICE_asr_to_app_asr045_window_5s_kernel_fix.md`） | `ls shared/` |
| ⑥ agent-mail | **`not_bound`**（工具明确「当前请勿重试」⇒ 试 1 次即停） | `ListMessages` 返回 `{"status":"not_bound"}` |

**另**：全库 `APP-134+` 命中 **0**（除本轮自身产物与 STATUS 引用）。

⇒ **本地 max APP-133 ＝ QQ max APP-133 ＝ `last_ack` APP-133** ⇒ **`last_ack` 不变（值不变）**。

---

## §2 🔴 真缺陷 ①：**app049 打包闸门从 §233 起一直红着 ⇒ v2.7 打不出来**

### 2.1 事实

- `results/app/app049_pkg_path_hardcode_gate.py`（**§48「包路径写死」闸门**）本轮实测 **exit = 1（总判定 FAIL，10 处违规）**。
- 🔴 **它是 `pack_v13.py` 的打包前置闸门**（`pack_v13.py:711` → `gate_pkg_path_hardcode()`）：
  `if r.returncode != 0: print('⚠️ 「包路径写死」闸门未通过 ⇒ 拒绝打包'); return 1`
  ⇒ **下一个包（v2.7）根本打不出来**。
- 起因：APP-133 / §233 / §234 / §235 四轮新增了 **9 个一次性历史诊断脚本**
  （`_app133_verify_pkg.py`、`_app233_verify_*`×4、`_app234_*`×3、`_app235_verify_evidence_scope.py`），
  它们**按设计**必须写死当时的包版本（v2.5/v2.6/v2.7/v2.8/v2.9/v2.10）
  ⇒ 被 `ACTIVE_RE = (^test_|_gate|_check|_verify|_probe)` 判成「活跃验收脚本」。
- 🔴 **为什么一直没被发现**：该闸门只在**打包时**跑；而**完整版线自 v2.5 起从未打过 zip**
  （用户规则「不通知 ⇒ 不打包」）⇒ 闸门一直红着没人触发。
- 🔴 **类别 B（会进包的生产模块 `live_caption/*.py`）实测 0 违规** ⇒ 该闸门**不削弱交付保证**。

### 2.2 修法

按本闸门**既有的「一次性历史诊断脚本」白名单口径**放行（该口径已有 11 条先例，
如 `_app228_verify_pkg.py` / `_app123_ov_probe.py` / `_app589_three_forms_defaults_check.py`），
**理由逐条写明**（哪个 APP 轮次、核对的是哪个版本、为什么必须写死）。
🔴 **不用通配符、不改 `ACTIVE_RE`、不放松任何判定逻辑**。

### 2.3 独立复核

- 闸门改后 **exit = 0（PASS，0 处违规）**。
- **过期白名单检查**：闸门自带的「白名单里已经不再命中」检查 **0 条**（§86 的防腐烂机制仍生效）。
- 🔴 **反证组**（判据须有鉴别力）：新增一个**未白名单**的写死脚本
  `results/app/_app236_probe_violation.py` ⇒ 闸门 **exit = 1 且点名该文件** ⇒ **闸门仍能抓真缺陷**
  （⇒ 不是把闸门放水放成永远绿）⇒ 反证文件已删除，闸门复测 **exit = 0**。
- 🔴 **我自己的脚本也不写死版本**：`_app236_check_producers.py` 的反证样本改用
  `PKG_NAME_PREFIX + '2.6'` 构造（**不写死版本号**）⇒ 该脚本**不再**被闸门判违规；
  同时把判据本身升级为**同时识别**「字面量包名」与「前缀常量 + 版本」两种形态
  （否则判据会漏判仓库**要求**的写法 ⇒ 见 §6 判据坑 ②）。

---

## §3 🟢 真缺陷 ②：§222 入库完整性缺口（②③ 两类）

### 3.1 §222②「证据 json 入库 ⇒ 其产生脚本也要入库」——5 个

| 证据 json（**已入库**） | 生产者脚本（**本轮入库**） | 字节 |
|---|---|---|
| `results/app/app260_tk_geometry_probe.json` | `results/app/_app260_tk_geometry_probe.py` | 3 975 |
| `results/app/app385_app089_accept_runs_after.json` | `results/app/_app385_run_acceptance_all.py` | 7 396 |
| `results/app/app534_special_profile_check.json` | `results/app/_app534_special_profile_check.py` | 4 065 |
| `results/app/app589_three_forms_defaults.json` | `results/app/_app589_three_forms_defaults_check.py` | 7 296 |
| `results/app/app372_app091_subtitle_shot/subtitle_layout.json` | `results/app/app372_app091_gui_subtitle_shot.py` | 9 532 |

⇒ **干净 clone 跑不了**这些**已入库**证据的生产者 ⇒ 复算链断。

### 3.2 §222③「复算底本（jsonl／csv／源 json）必须入库」——9 个

**4 个 json**（被证据以 `path`+`sha256` 字段引用）：
`app037_seam_mechanism.json`（21 847 B）、`app037_segcount_effect.json`（2 208 B）、
`app037_wer_gap_maincause.json`（35 927 B）、`app582_specialmvp_sp3_acceptance.run1.json`（13 468 B）
＋ **`app118_pkg_size.json`**（1 628 B，被**活文档**引用为 v2.5 包规模来源）。

**4 个 jsonl/csv**（10 分钟整链的逐句时间线与积压曲线 ＝ reviewer 的复算底本）：
`_app581_sp1_rerun_tts_out.wav.tts.jsonl`（201 099 B）、`…backlog_curve.csv`（17 115 B）、
`_app582_sp3_tts_out.wav.tts.jsonl`（218 009 B）、`…backlog_curve.csv`（16 736 B）。

### 3.3 🔴 修法：**逐字节入库**（`-text`）

- 本仓 `core.autocrlf=true` 且**仓库根无** `.gitattributes` ⇒ git 在 `add` 时把 **CRLF 规整成 LF**
  ⇒ 入库 blob 与磁盘原始文件**逐字节不同** ⇒ reviewer 在 `core.autocrlf=false` 的机器上 clone
  出来与**已公布 sha256** 对不上 ⇒ **假 FAIL**（§226 同一判据，同一条理由）。
- ⇒ 新建 **`results/app/.gitattributes`**，**逐文件**写 `-text`（🔴 **不用通配符**：
  本目录另有大量普通 .json，通配会把它们全改成 `i/crlf` ⇒ **改变已入库文件的入库形态** ⇒ 越权）。
- 沿用仓库既有先例：`results/app/app128b_e2e7_src/.gitattributes`（`*.json -text`，§226 修法）。

### 3.4 独立复核（逐条 ④ 项判据）

**判据**：① 入库 blob sha256 == 磁盘 sha256 ② == 已入库证据公布的 sha256 ③ 长度一致 ④ attr == `-text`。

- **9 个文件全部 4/4 PASS**（逐条明细 ⇒ `results/app/app236_byteexact_verify.json`）。
- 🔴 **反证组 3/3 PASS**：
  R1「经 autocrlf 规整（CRLF→LF）的 blob 与磁盘必不同」⇒ 判据须 FAIL ⇒ **PASS**（证明判据真在比对）；
  R2「blob==disk 但 !=公布 sha」⇒ 须 FAIL ⇒ **PASS**；
  R3「含 CRLF 的复算底本若不 `-text` 就会被规整」⇒ `-text` 是**必要条件** ⇒ **PASS**。
- 🔴 **端到端**：真跑 `git -c core.autocrlf=false clone --no-hardlinks` 到干净目录 ⇒
  **clone 出来的 8 个复算底本 sha256 与证据里公布的**逐个**一致**
  （`a878ce4325…` / `d83b9d0061…` / `ae804d0b64…` / `7d2776f980…` /
  `120dabe542…` / `2e7e775f8fc…` / `d6e688148307…` / `151311efd10…`）
  ⇒ **reviewer 在任何机器上 clone 都能复算出同一个 sha256**。
- 🔴 **干净 clone 里 5 个生产者脚本都在**，且 §2/§3 的审计脚本**在干净 clone 里能直接跑通**。

---

## §4 🔴 真缺陷 ③：app187 闸门的**正则截断** ⇒ 报出一个**从未存在过**的路径

- `results/app/app187_repo_artifact_in_repo_gate.py`（§104/§118「STATUS 引用 ⇒ git ls-files 在册」闸门）
  的 `_PATH_RE` / `_BARE_RE` **扩展名表里没有 `jsonl`**
  ⇒ STATUS 里的 `results/app/app231_pack_lock_events.jsonl` 被**截断成**
  `results/app/app231_pack_lock_events.json` ⇒ 闸门去查一个**从未存在**的文件名
  ⇒ 报出一个**假的** MISSING（真 MISSING 是 `.jsonl` 那个）。
- **修法**（两处，缺一不可）：
  ① 扩展名表补 `jsonl`（`csv` 在 `_PATH_RE` 里本有、`_BARE_RE` 里没有 ⇒ 一并补）；
  ② 🔴 **扩展名必须「长在前」排序**（`jsonl` 在 `json` 之前）——
  正则**分支按书写顺序**尝试 ⇒ `json` 在前时 `xxx.jsonl` 会先匹配到 `json`（后面的 `l` 不在模式里，
  不影响匹配成功）⇒ **又截断了**（本轮实测：只补扩展名表**不够**，仍截断）；
  ③ 加**扩展名边界断言** `(?![A-Za-z0-9])` 做双保险。
- **独立复核**：修复后闸门报的是**真实路径** `.jsonl` ⇒ 那个**从未存在**的 `.json` 消失。
  🔴 **反证组 3/3 PASS**：R1「修复前的正则必须截断 .jsonl」⇒ **PASS**（复现旧缺陷，证明缺陷真实存在）；
  R2「修复后必须完整命中」⇒ **PASS**；R3「修复后不得再出现那个从未存在的 `.json`」⇒ **PASS**。

---

## §5 🔴 安全缺口：**活的 EXT bridge 明文 token 未被 `.gitignore` 覆盖**

- `results/app/_pkg_v25_runtime_token_20261121_0428.txt`（内容 `M62uqacuZKo2…`）与
  `results/app/_pkg_v25_removed_bridge_token_20261121.txt`（内容 `vXLN8S1m0lXR…`）
  是 §219「包内 token 清零/轮换」验收时留下的**明文口令**。
- 🔴 **二者此前未被任何 `.gitignore` 规则覆盖** ⇒ 一次 `git add -A` / `git add .`
  就会**把明文口令提交进仓库**（提交后**不可逆**，需改写历史）。
- 🟢 **实测未泄露**：`git log --all -- <两个文件>` **无任何记录** ⇒ 二者**从未被跟踪**。
- **修法**：`.gitignore` 显式忽略 `results/app/_pkg_v25_runtime_token_*.txt` 与
  `results/app/_pkg_v25_removed_bridge_token_*.txt`（理由写明）；复核 `git check-ignore -v` 命中，
  且 `git status` 不再列出它们。
- 🔴 **顺带做了一次「入库前安全扫描」**（`results/app/_app236_secret_scan.py`）：
  对「被 STATUS 引用但未入库」的 **31 个磁盘候选**分类 ⇒
  **SECRET 2**（上述两个 token 文件，**永不入库**）／**RUNTIME 5**（`.log`，`.gitignore` 已约定 `*.log`）／**SAFE 24**。
  反证组 3/3 PASS（含「高熵裸 token 也必须命中」）。

---

## §6 本轮新学的判据坑（已下沉 `MEMORY_MODULES.md`）

① **判据粗 ⇒ 噪声淹没真缺陷**：初版 §222③ 扫描把「`checks[].name` 这种**检查项名**」当成生产者脚本
   ⇒ 3 143 条命中里绝大多数是噪声；把「证据里**显式声明**的产者字段」与「**AST 判定**真写出该文件」
   分开 ⇒ 收敛到 **5 个真缺口**。
② **「仓库里根本没有这个模块」被当第三方放过**：初版 import 审计写成
   「模块名**不在**已入库集合 ⇒ 当第三方跳过」⇒ 恰恰漏掉 §222④ 要抓的（HD4 同族）；
   改成**三分类**（RESOLVABLE／THIRD_PARTY／MISSING）⇒ 才看得见真缺口。
③ **正则分支按书写顺序** ⇒ 扩展名「长在前」是硬要求（只补扩展名表**不够**）。
④ **磁盘上有同名副本 ≠ 缺口**：results/app 下有大量历史快照副本（`_pkg_backup_*`／`_baseline/`）
   ⇒ 判「未入库」必须看「**所有副本都没入库**」，否则 49 条里 48 条是假阳性。
⑤ **`.jsonl` 的复算底本与 `.wav` 的音频本体的处置不同**：`.wav` 被 `.gitignore` 约定排除；
   `.jsonl`/`.csv` 是**复算底本**（reviewer 靠它复算）⇒ **必须入库**且**逐字节**。
⑥ 🔴 **Edit 工具会把整份文件统一规整成 LF ⇒ 破坏「行尾风格不变」这条真不变量**：
   本文件 `STATUS_APP.md` 是**混合行尾**（行 1-2 CRLF、行 3-4 LF、行 5-10 CRLF、行 11-91 LF
   ⇒ 共 **57 CRLF + 33 LF**）；用 Edit 工具改 1 行 ⇒ **57 个 CRLF 全部消失**（变成纯 LF）
   ⇒ ①违反「行尾风格不变」②使本文件与 HEAD 的差异从「3 处」放大成「整份文件」
   ⇒ ③「旧正文逐字未变」这条判据**失效**。
   ⇒ **修法**：`results/app/_app236_rebuild_status.py` —— 以**写前备份**为基底**在字节层**重做 3 处改动
   （保留每行原有行尾；新增行按所在区域既有行尾写入）⇒ **写前**跑真不变量断言
   （CRLF 数必须**一个不少**／LF 数 = 旧 + 新增行数／difflib 只允许「`更新时间` 行的 replace + 其余纯 insert」）
   ⇒ 全过才**临时文件 + `os.replace`**（原子）落盘。
   🟢 **实测**：重建后 **CRLF 57→57（不变）**、LF 33→36（+3 新增行）⇒ 行尾结构**原样保留**。
   🔴 **另**：判据本身也要防「假 FAIL」—— 用 difflib 的 **opcodes**（而非「逐行等长比较」）才不被行数变化带偏。

---

## §7 未修／待裁定（如实登记，未擅自处理）

1. 🔴 **`results/app/app231_pack_lock_events.jsonl` 仍不存在且未入库** ⇒ **app187 闸门仍 FAIL 1 项**。
   **根因**：它由 §231 修好的**生产路径**（`live_caption/_app116_build_v25.py` 的 `_lock_event()`，
   该修复已在 HEAD `eb82d17`）在**运行时**创建，而 v2.6 那次构建跑在**该修复提交之前**
   ⇒ **该文件尚未被生产路径产出**。
   ⇒ **正确处置＝如实记录，不伪造**（创建空文件＝**制造证据**）⇒
   **下一轮真跑成包路径时它会自动出现，届时应一并入库**。
   （§231 的「lock_lost 0 条」结论不受影响：其证据是 `results/app/app132_lock_events.jsonl`，**已入库**且内容属实。）
2. 🔴 **仓库根 `.gitattributes` 根治**（854→875 个 `i/lf+w/crlf`）**跨模块** ⇒ 仍待 reviewer 裁定。
   （本轮只做了 `results/app/` **局部**逐文件 `-text`，**未碰仓库根**。）
3. 🔴 **v2.6 的两处包内缺陷**（README 双标题／`MANIFEST.json` 的 `version=2.5`）修法**已落开发树**、
   **真包未动** ⇒ 随 v2.7 带；**是否出 v2.7 ⇒ 待用户与 reviewer 裁定**。
4. 🔴 **`v2.5` 的 `ACCEPTED.json` 仍指向 v2.4**（未重签）⇒ 待 reviewer 裁定。
5. 🔴 **`Confucius4_LiveCaption_v2.6.staging` 残留 25 GB** ⇒ **未删**（删除是破坏性操作 ⇒ 待授权）。
6. 🟡 **其余 22 个「被 companion 引用但未入库」的 SAFE 候选**（`app117_*`／`app118_*`／`app120_*` 等）
   ⇒ 本轮**只**入库了 app187 闸门点名的 `app118_pkg_size.json` 与 §222③ 的 8 个；
   其余**留待下一轮**（避免一次性改动面过大），清单 ⇒ `results/app/app236_status_cited_scan.json`。
7. 🔴 **默认分离设备**、**`n_speakers=0` 口径** ⇒ 仍待 reviewer 裁定。

---

## §8 纪律自查

- 🟢 **未打包 zip**（用户级纪律「不通知 ⇒ 不打包」）⇒ **无新 zip**；旧目录/旧 zip **未覆盖未删**。
- 🟢 **未改任何客户包**（v2.6 `ACCEPTED.json` 逐字未动：`version=2.6`／`accepted_at=2026-11-24 18:26:21`／
  `ext=0.4.21(b2a4978)`／`corrections=[APP-129,130,131,132,133,123]`／`n_production_modules=33`／
  `code_fingerprint=1a3a849f…`；**完整版 v2.x 无 zip**，本轮**未新增**）。
- 🟢 **未跑推理 / 未测速** ⇒ **未取 `MACHINE_LOCK`**（本轮全部是纯 CPU 的静态审计）。
- 🟢 **未调 MiniMax**（质量判定留给 reviewer）；**未连 B 机**。
- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（收尾四项指纹逐字一致 ⇒ **SHA 零改动**）。
- 🟢 只 `git add` **App 侧**文件；**未吞** ASR/MT/TTS 其它模块的未提交改动（全仓脏是别的模块的）。
- 🟢 **未 force push**；仓库只保留 `main` 分支。
- 🟢 本轮**只写** `status/app/STATUS_APP.md`（**追加** `## §236`）＋ 本 companion；旧章节**未回头改**。
- 🟢 **行尾结构原样保留**（写前 **57 CRLF + 33 LF** ⇒ 写后 **57 CRLF + 36 LF**，新增 3 行全 LF）
  ⇒ 详见 §6 ⑥（Edit 工具会规整行尾 ⇒ 改用字节层重建脚本 ＋ 写前真不变量断言）。
- 🟢 **STATUS 写入的独立复核 8/8 PASS ＋ 反证组 4/4 PASS**
  （`results/app/_app236_status_verify.json`）。

---

## §9 下一轮

- `last_ack` 仍 **APP-133**。
- ⏭ 等 reviewer 复核 **§236**（3 处真缺陷 ＋ 1 处安全缺口的修法与证据）。
- 🔴 **待裁定**：**是否出 v2.7**（本轮**已把打包闸门解红** ⇒ 出包路径不再被挡）／
  **是否删** `.staging`（25 GB）／**v2.5 重签 ACCEPTED**／仓库根 `.gitattributes` 根治／
  默认分离设备／`n_speakers=0` 口径／**app231_pack_lock_events.jsonl 的入库时机**。
