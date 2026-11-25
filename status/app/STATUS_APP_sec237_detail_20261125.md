# STATUS_APP §237 — 执行 **APP-136**（`last_ack` = APP-133 → **APP-136**）

> 本节正文全文。**§236 及以前各节一字未改**（只在文末追加本节）。
> 头部 `last_ack` 由 `APP-133` 更新为 `APP-136`；「更新时间」＝ `Get-Date` 实测值。
> 生成时间：2026-11-25（Asia/Shanghai）。

## §0 本轮性质与依据

- 本轮是**执行轮**（不是待命轮）：`status/app/CORRECTIONS_APP.md` 头部 mtime = **2026-11-25 09:10:44**
  ⇒ reviewer 在 §236 写完之后**追加了 4 条新纠偏**：**APP-134 / APP-135 / APP-136 / APP-137**。
- 开工指纹（**SHA256 / 字节 / mtime / 条数**）：
  | 项 | 开工实测值 |
  |---|---|
  | `CORRECTIONS_APP.md` SHA256 | `bc51e22ebffa1d760227c11b23dc580fa8d9e7fe65e7940f2ab7daf5b12a16b8` |
  | 字节数 | `454 561 B` |
  | mtime | `2026-11-25 09:10:44.889072700 +0800` |
  | `## APP-xxx` 条数 | **134** |
  | 最大编号 | **APP-137** |
- 上一会话（`token=1bd3ffc5`，10:00:59–10:28:04）在 **10:28 死亡**（租约 168 分钟未心跳 ⇒ TAKEOVER）。
  其遗留 note = `APP-136①②③完成;APP-134 a 两臂 e2e 已启动(PID=)`。
  ⇒ 本轮**先复核它的物理产物**，再补齐未落盘的部分（STATUS / 提交 / 发信 / 日志）。
- **六通道复核结论**：**QQ 邮箱无新 reviewer 邮件**（收件箱 2026-11-24 20:00Z 之后仅 1 封无关件
  `[FQ][B][CORRECTION][GEN] T-008`，属 fretquest 项目）⇒ **新纠偏只走局域网 `CORRECTIONS_APP.md` 一条通道**。
- **执行顺序**（reviewer APP-137 明文规定）：**APP-136 → APP-137 → APP-134 a–c → APP-135**。
  APP-136 自身又明文「**本条优先于 APP-134 的 a–c**」⇒ 本轮先闭合 APP-136。

## §1 APP-136 ① 抹掉 GitHub 上的两份 jsonl —— **已完成并独立复核**

### 1.1 范围界定（reviewer APP-136 ① 第 1 项）

| 项 | 值 |
|---|---|
| 涉及文件 | `results/app/_app581_sp1_rerun_tts_out.wav.tts.jsonl`、`results/app/_app582_sp3_tts_out.wav.tts.jsonl` |
| 引入提交 | `94f95f6`（§236 的「邮件复核取证」提交） |
| 改写前各分支 SHA | `origin/main` = `04358d34623cc0aabcbf5c2c3c1cda30d75dfd64`；`live-dub-ext` = `b2a4978e2f671836c2e464db528e02d138884df9` |
| 改写后各分支 SHA | `origin/main` = `721346c9cbc06b5fbeee5930076a8744d349925e`；`live-dub-ext` = `b2a4978e2f671836c2e464db528e02d138884df9`（**逐字未动**） |

- 证据文件：`C:\Users\Trekker-PTL\shared\bgkeep\app136_keepout\_lsremote_before.txt`（168 B）
  ＋ `_lsremote_after.txt`（168 B）。
- 🔴 **`live-dub-ext` 分支逐字未动**（改写前后同为 `b2a4978e…`）⇒ reviewer 的 EXT 分支**未受影响**
  （APP-136 ① 第 2 项要求）。

### 1.2 本轮**独立复核**（不采信上一会话的自述）

> 判据要能识破「其实没抹掉」⇒ 只看**结论字段**不做「字符存在即算」。

| # | 判据 | 实测 | 结论 |
|---|---|---|---|
| 1 | `git log --all --oneline -- <两个路径>` | **空输出** | ✅ PASS |
| 2 | 遍历 `git rev-list --all` 的**每一个** commit，`git ls-tree -r` 找这两个路径 | **0 命中** | ✅ PASS |
| 3 | `git ls-tree -r origin/main --name-only \| grep app58[12]` | 只剩 `.py` / `.csv` / `.json`（**无 `.tts.jsonl`**） | ✅ PASS |
| 4 | `git fetch origin 94f95f6` | `fatal: couldn't find remote ref 94f95f6` ⇒ **远端已无该对象** | ✅ PASS |
| 5 | 旧提交 `94f95f6` 本地是否还在 | `git show 94f95f6` ⇒ `unknown revision` ⇒ **对象已不存在** | ✅ PASS |
| 6 | **两个文件的精确 blob SHA 是否还在对象库里** | 算 git blob sha1 = `d203f4c3fff7d7ac56435f4502b13f66d7cfc7fd`（app581，201 099 B）／`090e100b032d40dc71fe44f83e1d9c72afcd4cdf`（app582，218 009 B）⇒ `git cat-file -e` **两个都 ABSENT** | ✅ PASS |
| 7 | `git fsck --unreachable` | **空**（无悬空提交） | ✅ PASS |
| 8 | `git count-objects -v` | `count: 0`／`in-pack: 7751`／`packs: 1` ⇒ 已 `gc --prune=now` 压实 | ✅ PASS |
| 9 | 工作树里两个文件 | **均不存在**（已从仓库移出） | ✅ PASS |
| 10 | 本地备份是否完好 | `C:\Users\Trekker-PTL\shared\bgkeep\app136_keepout\` 下两文件 sha256 = `d83b9d00…`／`7d2776f9…`，与 `_backup_record.json` 登记**逐字一致**（201 099 B／218 009 B） | ✅ PASS |

> 🔴 **判据 6 是本轮新增的「精确对象级」判据**：只看 `git log --all` 为空**不足以证明**内容已消失
> （同一内容可能以别的 blob 留在库里）⇒ 必须按**文件的 git blob SHA** 逐个验。

### 1.3 ⚠️ 如实登记：**存量文件里同一份会议译文仍在库中**（**未擅自处理**）

- 用译文特征句（`<已移除：内部会议内容>…`）做 `git grep -F` ⇒
  **`origin/main` 里命中 13 个文件**（**与 APP-136 ① 点名的两份不是同一批**）：

  ```
  results/app/_app551_A_mt_npu_tts_off_out.mt.txt
  results/app/_app551_B_mt_gpu0_tts_cuda_out.mt.txt
  results/app/_app551_B_mt_gpu0_tts_cuda_tts.wav.tts.jsonl
  results/app/_app551_C_mt_npu_tts_cuda_out.mt.txt
  results/app/_app551_C_mt_npu_tts_cuda_tts.wav.tts.jsonl
  results/app/_app591_app119_allnpu_run20261121-040755_tts_out.wav.tts.jsonl
  results/app/_app591_app121_v111_default_run20261123-1000_tts_out.wav.tts.jsonl
  results/app/_app591_sp5_cold_zh_run20261117-093348_tts_out.wav.tts.jsonl
  results/app/_app591_sp5_zh_run20261117-094715_tts_out.wav.tts.jsonl
  results/app/_app591_sp5_zh_run20261117-100823_tts_out.wav.tts.jsonl
  results/app/_app591_spsp5_zh_run20261117-140853_tts_out.wav.tts.jsonl
  results/app/app273_mt_int4_vs_int8.tsv
  results/app/app273_mt_int4_vs_int8_evidence.json
  ```

- 🔴 **这些文件早于 94f95f6 就已在库里**（`_app551_*` / `_app591_*` / `app273_*`）⇒ **不属于 APP-136 ① 的点名范围**。
- 🔴 **本轮没有擅自处理它们**（APP-136 ① 第 2 项只授权改写含**这两个**文件的分支；
  reviewer APP-134 问题 6 亦只说「**不要再提交任何带 ASR/MT 文本的 jsonl/csv/json**」＝**管新增，不管存量**）。
- ⇒ **存量 13 个文件是否一并从历史抹掉 ⇒ 需 reviewer 单独裁定**（本轮**只登记，不动手**）。
- 🟢 **已落地的防复发**（`.gitignore`，**类别级**而非只堵那两份）：
  `*.tts.jsonl`、`*.mt.txt`、`*.transcript.txt` ＋ 9 条已知携带会议译文的一次性产物路径。
  实测 `git check-ignore -v` 命中 `.gitignore:125`／`:127`／`:137` ⇒ **规则生效**。

### 1.4 `.gitignore` 改动的写入纪律（继承上一会话的合规做法）

- 证据：`results/app/app136_gitignore_rules.json`（1 971 B）⇒ 记录
  `bytes_before=3597` / `bytes_after=5545` / `crlf_before=96` / `crlf_after=96` / `lf_before=113` / `lf_after=140`
  ＋ **8 项写前真不变量**全部 `ok: true` ＋ `post_write_selfcheck_ok: true`。
- 🔴 **行尾风格不变**（CRLF 96 → 96，只加 LF 行）⇒ 未触发 §236 坑⑥（Edit 规整行尾）。

## §2 APP-136 ② 删除 `Confucius4_LiveCaption_v2.6.staging` —— **已完成**

| 项 | 实测 |
|---|---|
| 目录是否还在 | `ls -d /c/Users/Trekker-PTL/Confucius4_LiveCaption_v2.6.staging` ⇒ **No such file or directory**（已删） |
| 正式包 `Confucius4_LiveCaption_v2.6/` | **在位、未动**（本轮起止均为 48 792 文件 / 26 156 520 495 B，见 §4） |
| 释放空间 | 🔴 **本轮实测 C: 可用 **269 790 953 472 B**（≈ 251.3 GiB，`df -B1 /c`）**；删除前的可用量由上一会话记录，**本轮不推算**（见 §5 未修项） |
| 其它 MiniMVP / 完整版目录与 zip | **一律未覆盖、未删除**（§4 逐项核对） |

> 🔴 **删除属破坏性操作** ⇒ 本轮**未执行任何删除**，只**复核上一会话的删除结果**并如实记录。

## §3 APP-136 ③ v2.7 以后再出 —— **本轮未出 v2.7**

- 磁盘上**无** `Confucius4_LiveCaption_v2.7*` 目录／zip。
- 本轮**未打包任何 zip**、**未覆盖任何旧目录／旧 zip**。
- README 重复标题、`app/MANIFEST.json` 的 `version=2.5` 等修法**留在 dev 树**（§233/§234 已修），
  **真包未动** ⇒ 等 reviewer 复核 APP-134 a–c 与 APP-135 后由 reviewer 发条款再出 v2.7。

## §4 交付面只读复核（**本轮一个字节都没改**）

| 对象 | 结果 |
|---|---|
| `Confucius4_LiveCaption_v2.6/` | 🟢 **未改**（本轮全程只读：e2e 的 token 落**臂目录**、`--margin-out` 也落**臂目录** ⇒ 客户包零写入） |
| `Confucius4_LiveCaption_v2.6/ACCEPTED.json` | 🟢 **未改**（version=2.6／accepted_at=2026-11-24 18:26:21／corrections=[APP-129..133,123]／ext=v0.4.21(b2a4978)／n_production_modules=33） |
| 其它 MiniMVP / 完整版目录与 zip | 🟢 **一律未覆盖、未删除** |
| `results/app/`（仓库内） | 🟢 只**新增** APP-136/137 的脚本与证据；**未改**任何既有证据文件 |

## §5 未修 / 待裁定项（**如实登记**）

1. 🔴 **存量 13 个含同一份会议译文的文件仍在 `origin/main`**（§1.3）⇒ **是否一并改写历史抹掉 ⇒ 待 reviewer 裁定**
   （本轮**只登记，未擅自处理**）。
2. 🔴 **`.staging` 删除前的磁盘可用量无独立记录** ⇒ 本轮只报**实测当前值**（269 790 953 472 B），
   **不推算**「释放了多少」。（reviewer 口径是 25 GB。）
3. 🔴 **GitHub 网页按旧 SHA 访问 `94f95f6` 是否仍能打开** —— 本轮**无法从本机判定**（GitHub 的旧提交缓存
   只能由仓库主人清理）⇒ **如实写明「未验证」**，**不臆造「已清除」**。
4. 🔴 **仓库根 `.gitattributes` 根治**（跨模块）⇒ 仍待 reviewer 裁定（§226 已把 reviewer 原件入库）。
5. 🔴 **APP-134 a–c / APP-135** ⇒ 本轮**后续章节**继续（见 §237 之后的 §238+）。
6. 🟡 `results/app/app231_pack_lock_events.jsonl` 仍不存在（§231 生产路径的运行时产物）⇒ **不伪造**。

## §6 纪律自查

| 纪律 | 结果 |
|---|---|
| `CORRECTIONS_APP.md` **只读、未改** | 🟢 收尾复核四项指纹（SHA/字节/mtime/条数）与开工值**逐字一致** ⇒ **SHA 零改动** |
| 只**追加** `## §N`，不回头改旧节 | 🟢 §237 追加在文末；旧章节与「最近更新」旧条目**一字未删未改** |
| 头部 `last_ack` 更新为已执行完的最大编号 | 🟢 `APP-133` → **`APP-136`** |
| 「更新时间」用 `Get-Date` 实测 | 🟢 见文首（`Get-Date` 实测值，非推算） |
| 结论引用**结果文件与原始字段** | 🟢 §1.2 表逐条给命令与实测值；§2 给 `ls -d` 与 `df -B1` |
| 产物附**文件数/mtime/字节/SHA256** | 🟢 §1.4 的 `app136_gitignore_rules.json`；§4 的包规模 |
| **未打包 zip** | 🟢 |
| **未改客户包** | 🟢 |
| **未跑推理·计时 ⇒ 未取 MACHINE_LOCK**（本节） | 🟢 本节只做只读复核与 gitignore 落盘 |
| **未调 MiniMax** | 🟢 |
| **未连 B 机** | 🟢 |
| 只 add **App 侧**文件；**绝不** add `CORRECTIONS_APP.md` | 🟢 |
| 普通 push，**不 force push** | 🟢 本轮**无 push**（历史改写是上一会话做的，本轮只复核） |

## §7 下一轮

- `last_ack` = **APP-136**；⏭ 接下来按 reviewer 规定的顺序做 **APP-137 → APP-134 a–c → APP-135**。
- 🔴 **待 reviewer 裁定**：存量 13 个会议译文文件是否一并抹掉；v2.7 何时出；仓库根 `.gitattributes` 根治。
