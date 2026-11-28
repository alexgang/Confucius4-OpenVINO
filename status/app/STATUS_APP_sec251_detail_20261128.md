# STATUS_APP §251 — 六通道复核（**无新 App 纠偏**，`last_ack` 仍 **APP-157**）＋ 🔴 接续死会话（TAKEOVER）⇒ 闭合 §251 断点 ＋ 🔴 **查出并修掉一个真缺陷：`ext/extension/player.js` 的 3×U+FFFD ⇒ 阻断下一次出包**（**已进客户 v1.2.1.zip**）

> 生成时间：2026-11-28 19:31:40（`Get-Date` 实测）
> 本轮性质：**接续轮（TAKEOVER）**——上一会话（token `7c56f91a`，11-28 16:21:02 起、**17:36:34 最后心跳**＝**55 min 前**、`alive=False`、`live_pids=[]`）在做 §251（打包路径闸门自检）时**心跳超时死掉**，**没写 STATUS、没提交、没发信** ⇒ 本轮从其断点**继续**，不从头重做。
> **`last_ack` 不变**（仍 **APP-157**）：六通道复核 ⇒ **无编号 > APP-157 的新条目**。
> 🔴 本节按纪律**只追加**，不回头改旧章节；`status/app/CORRECTIONS_APP.md` **一字未改**（§7 收尾指纹）。
> 🔴 **本轮最重要产出**：死会话留下的守卫**只证明了「闸门清单能抽出来」，没证明「闸门是绿的」** ⇒ 本轮把 `--pkg` 闸门**真跑起来**，**当场抓出一个真缺陷**（§3、§4）。

---

## §0 本轮顺序与依据

1. **第 0 步租约**：`session_lease.py acquire app` ⇒ **exit 0 / TOKEN=7d2414d5**，输出 **`TAKEOVER stale lease`**
   （旧 token `7c56f91a`／started 11-28 16:21:02／last_beat 11-28 17:36:34＝**55 min 前**／`alive=False`／`live_pids=[]`）
   ⇒ **上一会话已死** ⇒ 按纪律「先读它留下的 note、STATUS 和产物，**从断点继续**」。
   ⇒ 它的 note ＝ `闸门守卫7/7 PASS; 验证--pkg闸门对v2.6` ⇒ **它自己写明了下一步就是「验证 --pkg 闸门对 v2.6」，但没做完**。
2. **六通道复核** ⇒ **无新纠偏**（§1）。
3. **独立复核死会话的 3 处修改 + 守卫 + 2 个反证组** ⇒ 全部**复现通过**，确认它没做错（§2）。
4. 🔴 **补上它没做完的那一步**（守卫的 `--pkg` 能力）⇒ **当场抓出真缺陷**（§3）。
5. 🔴 **修掉真缺陷**（EXT 源文件，非客户包）＋ **独立复核 10/10**（§4）。
6. 写 STATUS §251 ⇒ 提交（App 侧文件）⇒ 发 STATUS 邮件 ⇒ 收尾指纹（§6、§7）。

---

## §1 六通道逐通道证据（⇒ **无新 App 纠偏**）

| # | 通道 | 实测 | 结论 |
|---|---|---|---|
| 1 | 局域网 `status/app/CORRECTIONS_APP.md` | **46 642 B**／sha256 `cc1067b7c4908e15…`／mtime **2026-11-27 15:08:17**／`## APP-xxx` 条目 **15** 条／编号 = 001,002,003,004,146,147,148,149,150,151,153,154,155,156,157 ⇒ **max = APP-157** | **无 > APP-157 的新条目** |
| 2 | QQ 收件箱 | 收件箱最新 = **APP-157**（`msg_8s6eELs8zrm5Euqkw7cI5tyTsOivbUwHdDGzjWyDShX62Q`，2026-11-27T07:08:16Z）；`q=APP-15` 搜索命中 **APP-157**（`msg_8s6eELs8…`）＋ **APP-152**（`msg_67grwLF4…`，旧编号）⇒ **max = APP-157** | **无新条目** |
| 3 | QQ spam | **0 封**（`ListMessages dir=spam` → `data:[]`） | 空 |
| 4 | QQ trash | **1 封**：`msg_Ui-Sz0CwNYT2DX-…`（2026-11-13，B 机 rc9 性能报告，**与 App 纠偏无关**） | 无关 |
| 5 | agent-mail | `mcp__agent-mail__ListMessages` → **`status: not_bound`**（「Agent 邮箱尚未开通」）⇒ 该通道**不可用**（与前几轮一致） | 不可用 |
| 6 | 全库检索 | `grep -rE "APP-(15[89]|1[6-9][0-9]|[2-9][0-9][0-9])"` ⇒ 命中**全部**是历史记忆里的旧编号引用与「APP-178」历史注释，**无新编号** | 无新条目 |

⇒ **`last_ack` 保持 APP-157 不变**；**本轮无编号 > APP-157 的新纠偏条目** ⇒ 按纪律**不执行任何新纠偏**；本节记录的是**接续轮的闭合动作 + 本轮自查发现的真缺陷**。

---

## §2 独立复核死会话（token `7c56f91a`）留下的 3 处修改 ＋ 守卫 ＋ 2 个反证组

> 🔴 **纪律**：**不采信**它自己落的 JSON verdict ⇒ **逐个重跑**，用**它没用过的方法**复核。

### §2.1 三处修改（逐个独立重跑）

| # | 文件 | 改动 | **独立重跑结果** | 判定 |
|---|---|---|---|---|
| ① | `results/app/app049_pkg_path_hardcode_gate.py` | 白名单 **+10 条**（`_app133_verify_pkg.py` / `_app233_verify_*` ×4 / `_app234_*` ×3 / `_app235_verify_evidence_scope.py` / `live_caption/_app137_candidate_check.py`） | 闸门实跑 ⇒ **0 处违规 / PASS**（`rc=0`）；**过期白名单 = 0 条**；逐个核这 10 个文件在 `Confucius4_LiveCaption_v2.6/app/` 里**都不存在** ⇒ **全是「不进包的一次性历史诊断脚本」**，与既有白名单口径一致 ⇒ **不削弱交付保证**（类别 B 仍是 0 违规） | ✅ 真修 |
| ② | `results/app/app049_gate_selftest.py` | 复制临时副本时**只复制 `*.py`**（不再 `copytree` 整树） | ① 复核**根因真实**：`results/app/app526_app107_rc11_acceptance/iso_localappdata/Confucius4LiveCaption/` 下**实测 23 个 Windows junction**（`cache` / `clone_voices` / `ext_*_cache` / `npu_*` / `tts_*` 等）⇒ `copytree` 会**跟随 junction 展开成真实副本** ⇒ 磁盘写满；② 闸门**只判 `.py` 文件** ⇒ 只复制 `.py` **不改变闸门行为**；③ 重跑自检 ⇒ **7/7 PASS**（S1 干净仓库 PASS / S2 含「0 处违规」/ S3 注入缺陷 FAIL / S4 抓到类别 A / S5 抓到类别 B / S6 违规数=2 / S7 移除后回 PASS） | ✅ 真修 |
| ③ | `check_internal_material.py` | `SKIP_CONTENT_EXT` 加字体扩展名（`.woff/.woff2/.ttf/.otf/.eot/.fon`） | ① 复核**误报真实**：`Confucius4_LiveCaption_v2.6/cuda_env/Lib/site-packages/.../fonts/IBMPlexMono/IBMPlexMono-Bold.woff2` 的**随机字节里真的出现 `qgS`** ⇒ 命中 `\bQ[G]S\b` ⇒ 报「会议特征串」；② **字体仍查文件名**（`NAME_PATTERNS` 不变）；③ 用 **HEAD 版本**跑 v2.6 ⇒ 命中 **2** 个（字体 + player.js）；用**修后版本**跑 ⇒ 只剩 **1** 个（player.js）⇒ 修法**只消掉了误报，没消掉真检出** | ✅ 真修 |

### §2.2 守卫 + 2 个反证组（独立重跑）

| 脚本 | 独立重跑结果 | 判定 |
|---|---|---|
| `results/app/_app251_pack_gates_guard.py` | 从 `pack_v13.py` 源码 **AST 抽**出 **4** 个闸门调用；**7 PASS / 0 FAIL / 3 SKIP** | ✅ 可用（但**有缺口**，见 §3） |
| `results/app/_app251_anticontrol.py` | **9 PASS / 0 FAIL**（A1 真实仓库 PASS / A2 基线含「0 处违规」/ B1 注入缺陷 FAIL / B2 抓到类别 A / B3 抓到类别 B / B4 违规数=2 / B5 未白名单的新脚本仍被抓 / B6 移除后回 PASS / **B7 修复前的闸门在同一副本上 FAIL（判据有鉴别力）**） | ✅ 反证组有鉴别力 |
| `results/app/_app251_anticontrol_material.py` | **8 PASS / 0 FAIL**（C1 真会议特征串（.txt）仍被抓 / C2 报出「内容关键词」/ C3 真 U+FFFD（.js）仍被抓 / C4 报出「U+FFFD 乱码」/ **C5 字体里的偶然字节命中不再误报** / C6 字体「文件名规则」仍生效（preset_B 被抓）/ C7 .png 仍按原口径不读内容 / **C8 中文会议关键词仍被抓（判据有鉴别力）**） | ✅ 反证组有鉴别力 |

⇒ **死会话的 3 处修改 + 守卫 + 2 个反证组全部正确，本轮予以保留并入库。**
⇒ 🟢 **它没有做错任何事**；**唯一的问题是它停在了「守卫只能抽清单」这一步**（§3）。

---

## §3 🔴 死会话守卫的**真实缺口**：「抽得出清单」≠「闸门是绿的」

🔴 **死会话的 note 明写下一步是「验证 --pkg 闸门对 v2.6」，但它没做完** ——
它写的守卫把 **3 个需要 `--pkg` 的闸门全部 SKIP**（理由写的是「需指定客户包，本轮不代选」）
⇒ **它证明的只是「闸门清单能抽出来」，没有证明「闸门是绿的」**
⇒ 而**恰恰是这 3 个被 SKIP 的闸门里，有一个是红的** ⇒ **假绿**。

### §3.1 补齐：守卫真的把 `--pkg` 闸门跑起来

新增 `results/app/_app251_pack_gates_guard_pkg.py`：

- **必须显式 `--pkg`**（**不猜、不代选**）⇒ 不给 `--pkg` 就**只跑离线闸门**，绝不误触客户包；
- 逐个跑：`check_internal_material.py --pkg`（**只读**）、`results/app/app170_version_identity_gate.py --pkg`（**只读**，它自建影子包，不碰真包）；
- 🔴 **区分「只读闸门」与「会写盘的闸门」**：`live_caption/sync_c172_version_identity_to_pkg.py` **会写包**（`os.replace` 改 `MANIFEST.json`）⇒ 本脚本**强制给它加 `--dry-run`**（脚本自带该开关 ⇒ 真跑校验逻辑但不写盘），并用 `assert` 保证**永远**带；
- 每个闸门记 **rc + 输出要点** ⇒ 落盘成证据。

### §3.2 实跑 v2.6 的结果（**当场抓出真缺陷**）

`python results/app/_app251_pack_gates_guard_pkg.py --pkg "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.6"`
⇒ **PASS 3 / FAIL 1 / SKIP 0 ⇒ 总判定 FAIL**（证据 `results/app/app251_pack_gates_guard_pkg.json`，2 675 B，sha256 `284865215cb988e4…`）：

| 闸门 | rc | 判定 | 实测输出要点 |
|---|---|---|---|
| `results/app/app049_pkg_path_hardcode_gate.py` | 0 | ✅ PASS | 0 处违规 |
| 🔴 `check_internal_material.py --pkg v2.6` | **1** | 🔴 **FAIL** | **`ext/extension/player.js`（编码规则：文本编码：含 3 个 U+FFFD 乱码字符）** |
| `results/app/app170_version_identity_gate.py --pkg v2.6` | 0 | ✅ PASS | 19/0（2 条**不阻断**提醒：MANIFEST.version 2.5→2.6、README_zh 改动说明段 count=2） |
| `live_caption/sync_c172_version_identity_to_pkg.py --pkg v2.6 --dry-run` | 0 | ✅ PASS | **DRY-RUN OK，未写包**（`[APPLIED] app\MANIFEST.json` 仅 dry-run 报告） |

---

## §4 🔴 真缺陷：EXT `extension/player.js` 的 3×U+FFFD（**阻断出包**，且**已进客户 zip**）

### §4.1 缺陷本体与影响面（**真检出，不是误报**）

- **位置**：`ext/extension/player.js` 第 **1639** 行（EXT-034 ① 的注释行）：
  `// ★★★★★ EXT-034 ①：**每段配音都要能算<3×U+FFFD>同步误差**（不靠 onset 配对）。`
- 🔴 **阻断出包**：`check_internal_material.py` 把 `.js` 列入 `TEXT_EXT`，**任何 U+FFFD ⇒ FAIL**
  ⇒ `pack_v13.py` 的打包前闸门 `check_internal_material(PKG)` ⇒ **FAIL ⇒ 拒绝打包**
  ⇒ **下一次出包会被直接拦死**（与 §236「app049 闸门曾红 ⇒ v2.7 打不出来」**同类复发**）。
- 🔴 **已进客户交付物**：实测 `LiveCaption_MiniMVP_v1.2.1.zip`（**发客户的就是这个 zip**）内
  `LiveCaption_MiniMVP_v1.2.1/ext/extension/player.js` = 203 894 B、**U+FFFD = 3** ⇒ **同样带乱码**。

### §4.2 根因（**定位到具体 commit**）

- 引入于 EXT **`9bd09dd`**（`§27 EXT-034/035 交卷`，2026-11-02 21:56:40）。
- 形态：**1 个 3 字节 UTF-8 汉字**被逐字节替换成 U+FFFD（ASCII 解码 `errors='replace'` 的典型形态）⇒ 9 字节 `ef bf bd`×3。
- 🔴 **历史上从未有过干净版本**：逐 commit 扫描 `extension/player.js` ⇒ `c209ec6 … 1686bf8` 都是 **0** 个 U+FFFD，**`9bd09dd` 突然变成 3**，其后每个 commit（`5121d99` / `7a92f12` / `63df9bf` / `1880cbf` / `d0899a4` / `817abcb` / `b864382` / `5372be5` / `027ce22` / `c347abc` / `5979165` / `38a89d5` / `9b8ade4`）**全是 3**
  ⇒ **不能靠 git 回滚恢复**，只能按语义 + 仓库惯用词复原。

### §4.3 复原依据（为什么是「出」）

1. **同文件 1631 行**用同一动词族：`否则 player 端算不出「有符号同步误差」的对齐对象。`
2. **全 EXT 仓库用词统计**：`算出` **17** 次 ／ `算准` **0** 次 ／ `算得` **1** 次。
3. **语义**：`每段配音都要能算出同步误差`（"能算出" ＝ 能把数算出来）✔ 与 EXT-034 ① 意图一致。
4. **字节自洽**：`出` 的 UTF-8 = `e5 87 ba`（3 字节）⇒ 恰好还原那 9 字节。

⇒ 原字符 = **出**。

### §4.4 修法与**独立**复核（10/10 PASS，不采信修法脚本自证）

修法脚本 `results/app/_app251_fix_player_ufffd.py`（**写盘前**在内存里跑 5 条不变量：逐字节不变 / 长度 −6 / U+FFFD 归零 / 合法 UTF-8 / **还原式复核**（把 `出` 换回 3×U+FFFD ⇒ 必须与原文件逐字节相等））：

- 备份：`C:\Users\Trekker-PTL\live_dub_ext\.tmp\app251\player.js.bak_app251_ufffd`（**故意放在 `.tmp/` 而不是 `extension/`** ⇒ 成包脚本按 `git ls-tree` 取文件，**不可能**把它带进包）
- 落盘：临时文件 → `os.replace`（原子）；**只改 1 处 9 字节 → 3 字节**。

**独立复核**脚本 `results/app/_app251_verify_player_ufffd.py`（**换方法重算**）⇒ **10 PASS / 0 FAIL**（证据 `results/app/app251_player_ufffd_verify.json`，1 116 B，sha256 `240ba620a92b3067…`）：

| # | 判据 | 实测 |
|---|---|---|
| ① | 与备份逐字节 diff ⇒ **只有那一处**变（9 B → 3 B，`old=ef bf bd×3` / `new=e5 87 ba`） | PASS |
| ①b | **行数不变**（4 096 vs 4 096） | PASS |
| ①c | **行尾风格不变**（CRLF 4 096 vs 4 096） | PASS |
| ② | 整文件 U+FFFD = **0** | PASS |
| ③ | 整文件**严格** UTF-8 解码通过 | PASS |
| ④ | 复原后的完整句子在**正确位置** | PASS |
| ⑥ | 修好的文件 ⇒ 内部素材闸门 **PASS（rc=0）** | PASS |
| ⑦ | **反证组**：把带 U+FFFD 的旧文件放进临时包 ⇒ 闸门 **FAIL（rc=1）** | PASS |
| ⑦b | 闸门确实**点名 player.js**（不是别的理由 FAIL） | PASS |
| ⑤ | **反证组**：把修好文件里的 `出` 改回 U+FFFD ⇒ 闸门 **FAIL（rc=1）** | PASS |

🟢 `node --check extension/player.js`（node v22.22.2）**通过**。

### §4.5 提交与推送（EXT 仓库）

- EXT commit **`4868a29`**：`EXT v0.4.25: player.js — restore the one CJK char mangled into 3x U+FFFD (EXT-034 ① comment)`（**只改 `extension/player.js` 1 个文件、1 行**）。
- **staged blob 复核**（§226 的 CRLF 坑）：HEAD blob 199 798 B / staged blob 199 792 B ⇒ **只有那 9→3 字节不同**（`old=ef bf bd×3` / `new=e5 87 ba`），**CRLF 计数两边都是 0**（仓库内是 LF 存储）⇒ **未被 autocrlf 改写**。
- 已推：`git push github claude-dev:live-dub-ext` ⇒ `9b8ade4..4868a29` ⇒ 远端 `github/live-dub-ext` = **`4868a29`** ✔
- **未升 EXT 版本号**：本改动**只动注释**，按仓库既有惯例（`3ef76b8` / `32ff975` 同样是改交付文件措辞但**不升版本**）**不升版本**。

### §4.6 修好之后，下一次出包会不会带上？

- **完整版线**：`_app129_build_v26.py` 的 `sync_ext_from_commit(EXT_COMMIT)` 按 **`git ls-tree` + `git show`** 取 `extension/*`
  ⇒ 实测 `b2a4978` 的 `extension/player.js` U+FFFD = **3**、**`4868a29` 的 = 0** ⇒ **下一次出包（指向 `4868a29`）自带修好的文件** ✔
- 🔴 **但 v2.6 目录本身仍是旧文件**（本轮**没有**改客户包 —— 纪律 APP-055：**禁止原地修改 `Confucius4_LiveCaption_v*`**）
  ⇒ **要出 v2.7 时，`EXT_COMMIT` 要指向 `4868a29`**（§5 待办）。

---

## §5 🔴 本轮查出的**系统性缺口**（比单个乱码更重要）

🔴 **MiniMVP 交付线（= 真正发给客户的那条线）上，**打包前闸门**只有 1 个，而且不含内部素材/编码检查**：

| 线 | 打包前闸门 | 有无 `check_internal_material` | 后果 |
|---|---|---|---|
| 完整版（`pack_v13.py`） | app049 路径写死 ＋ **内部素材闸门** ＋ app170 版本标识 ＋ sync_c172 | ✅ **有** | 本轮抓到的乱码**会**被拦住 |
| 🔴 **MiniMVP（`v121_make_zip.py` / `app157_zip_gate.py`）** | `app157_zip_gate.py` **45 项**自检（版本号 / 目录清单 / 无 CUDA / 克隆音色目录为空 / 无 `__pycache__` / 无 `.bak_*` …） | ❌ **无**（实测 `grep -c "check_internal_material"` = **0**） | ⇒ **乱码直接进了客户 zip**（§4.1 实测 `LiveCaption_MiniMVP_v1.2.1.zip` 内 player.js U+FFFD=3） |

⇒ **同一个乱码**：完整版线**拦住**了，MiniMVP 线**放行**并**发给了客户**。
⇒ 🟢 **本轮已把 MiniMVP 线的缺口补上**（§3.1 的守卫带 `--pkg` 就能覆盖 MiniMVP 候选目录），
   但**真正把 `check_internal_material` 接进 MiniMVP 出包路径**属于**改出包流程**，**本轮未做** ⇒ 列入待办（§6.2）。

🔴 另注：`_app129_build_v26.py` 的成包日志（`results/app/app129_build_v26.log`）**只有 `stage=copy` / `stage=sync`**，
**从没有 `stage=pack`** ⇒ **完整版 v2.6 的打包前闸门从未在这个包上跑过** ⇒ 这也是「乱码能进 v2.6 目录」的原因。

---

## §6 未做 / 待办（**如实登记**）

### §6.1 本轮**没有**做（受纪律约束）

1. 🔴 **未改任何客户包**：`Confucius4_LiveCaption_v2.6/` 与 `LiveCaption_MiniMVP_v1.2.1.zip` **一个字节未动**
   （纪律 APP-055：禁止原地修改 `Confucius4_LiveCaption_v*`；**且用户未通知 ⇒ 不打包**）。
   ⇒ **v2.6 / v1.2.1 里那个乱码仍在**（**已如实记录在 §4.1**）。
2. 🔴 **未出包**（用户规则：**未经用户通知不打包**）⇒ **未打 zip、未签 ACCEPTED**。
3. 🔴 **未把 `check_internal_material` 接进 MiniMVP 出包路径**（改出包流程 ⇒ 需 reviewer 裁定）⇒ §5。
4. 🔴 **未处理另 2 个 U+FFFD 文件**：
   - `live_dub_ext/tests/smoke/_smoke_common.py`（**2** 个 U+FFFD，**不进包**（`tests/` 不随包分发）⇒ 不阻断出包；
     原文 `为什么有这□文件（EXT-022 已定②）` ⇒ 疑似「这**个**文件」，但**字节级复原依据不足** ⇒ **不擅自改**）。
   - 主仓 `results/app/app074_tts_e2e_cp936.txt`（34 个）、`results/app/app095_pythonw_smoke.json`（170 个）等
     **32 个 tracked 文件**含 U+FFFD ⇒ 多数是**故意的 cp936 乱码测试样本**（文件名即 `cp936`）⇒ **属正常**，不动。
3. 🔴 **未做 APP-144 ① 历史改写**（**需 reviewer 明确放行** ⇒ 不可逆强推）。
4. 🔴 **未删 `.staging`**（25 GB）、**未重签 v2.5 ACCEPTED**、**未改仓库根 `.gitattributes`**（跨模块 ⇒ 待 reviewer 裁定）。

### §6.2 下一轮待办

1. ⏭ **等 reviewer 复核本节**（§251 + §5 的系统性缺口）。
2. 🔴 **出 v2.7 时 `EXT_COMMIT` 指向 `4868a29`**（否则会把旧乱码再带进新包）—— §4.6。
3. 🔴 **MiniMVP 线接 `check_internal_material`**（§5）—— **需 reviewer 裁定后再改出包流程**。
4. 🔴 **客户手上的 `LiveCaption_MiniMVP_v1.2.1.zip` 带乱码** ⇒ 是否**重出一版**（v1.2.2）由 reviewer / 用户决定
   （本轮**不打包**）。
5. 🔴 **APP-144 ① 历史改写**（需放行）、**§222 缺口**（本轮已全部入库 ⇒ 已闭合）。

---

## §7 纪律核对（本轮）

| 项 | 状态 |
|---|---|
| `status/app/CORRECTIONS_APP.md`（reviewer 独占） | 🔴 **一字未改**（§8 四项指纹逐字比对） |
| 客户包 / zip | 🟢 **未改、未覆盖、未删除、未新打**；`v1.13…v2.6` 与 `MiniMVP v1.2/v1.2.1` 的 mtime **全部未变** |
| 推理 / 计时 / 设备 | 🟢 **零推理、零 GPU、零 NPU** ⇒ **未取 MACHINE_LOCK**（终态 FREE） |
| MiniMax | 🟢 **未调用**（质量判定仍归 reviewer） |
| B 机 / 目标机 | 🟢 **未连接** |
| 提交范围 | 🟢 **只提交 App 侧文件**；**未**提交 `CORRECTIONS_APP.md`；**未吞**其它模块未提交改动（EXT 仓库只提交 `extension/player.js` 1 个文件） |
| 推送 | 🟢 **普通 push**（EXT `9b8ade4..4868a29` ⇒ `live-dub-ext`）；**无 force push** |
| 打包 | 🟢 **未打包**（用户未通知） |

---

## §8 收尾指纹（`CORRECTIONS_APP.md` 四项）

| 项 | 开工时 | 收尾时 | 结论 |
|---|---|---|---|
| SHA256 | `cc1067b7c4908e1583d7b6537f4f1c6e01b8a3831f1996f7272c0682f517ebae` | 同左 | **零改动** |
| 字节数 | 46 642 B | 同左 | **零改动** |
| mtime | 2026-11-27 15:08:17 | 同左 | **零改动** |
| `## APP-xxx` 条数 | 15（max **APP-157**） | 同左 | **零改动**（本轮**未追加**，如实记录） |
