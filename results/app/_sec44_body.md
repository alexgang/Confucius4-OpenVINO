
## §44 🔴 巡检（APP-017 无新纠偏条目）+ 🔴🔴 查出并**修法已就绪**：「草稿→正式稿」配对存在**跨段离群错配** ⇒ 正式稿译文被搬到**几十段之外**（MT 通知 13 的「假前缀」在 **App 渲染层同样成立**）（2026-10-26 01:56）

### §44.0 巡检结论（与 §43 同口径）

| 项 | 实测值 |
|---|---|
| `status/app/CORRECTIONS_APP.md` SHA256 | `baaa16ae869e3855a0a231946db81727ccb98a1fa2eeaab842ca51df038fd9cc`（**与 §43 开始时逐位一致 ⇒ 只读零改动**） |
| 文件大小 / mtime | 35 386 B / 2026-10-25 15:38:05.008683900 +0800（**未变**） |
| `## APP-xxx` 条目数 | **17**（APP-001 … APP-017） |
| 最大编号 | **APP-017** |
| `STATUS_APP.md` 头部 `last_ack` | **APP-017** |
| ⇒ **是否有新条目** | 🔴 **无**（第 21 次同一口径）⇒ `last_ack` **保持 APP-017**（**不变**） |

🔴 **本轮新增外部输入**：`shared/NOTICE_mt_to_app_20261026_notice13.md`
（**2026-10-26 00:47 新增**，6 188 B）= **MT 通知 13**。
🔴 **本轮机器锁状态**：巡检期间 `shared/MACHINE_LOCK` 由 **ASR** 持有
（01:47:14 `p3_diag_mask2_prefix` → 01:51:10 换手为 `p3_diag_device_mem`）
⇒ 本轮**全程未与持锁方并行启动 `python.exe` 作业**（详见 §44.6）。

---

### §44.1 🔴 本轮的核心发现：**通知 13 说的「假前缀」，在 App 渲染层同样成立**

#### §44.1.1 通知 13 说了什么（MT 口径，App 不引用为结论）

`NOTICE_mt_to_app_20261026_notice13.md` §13.1 / §13.3 / §13.4：

- 🔴 MT 侧旧口径「**双向包含 + 取最短**」会产出**假前缀** ⇒ 把草稿配到几十段之外
  ⇒ 报出 **563.86 s** 的假长尾（**真实上界 13.4 s**）；
- 通知 13 §13.1 明确写：**「产品里『草稿→正式稿替换』的机制完全不受影响」**
  ⇒ **不需要改任何产品逻辑**；
- 建议的修正口径三步：① **只接受正向**（正式原文以草稿原文为前缀且更长）
  ② **词边界**（前缀之后不能是字母/数字，也不能是「撇号 + 字母数字」）
  ③ **跳过过短草稿**（长度 < 10）。

#### §44.1.2 🔴🔴 但 App 侧的核实结果与该结论**不一致**（通知 13 的「不受影响」在 App 层**不成立**）

🔴 **App 渲染层的产品代码**：`live_caption/caption_render.py::match_draft_to_final`
（§41 已落地并在 HEAD 中，commit `0363e8c`）。

| 通知 13 的三步 | App 渲染层现状 | 判定 |
|---|---|---|
| ① 只接受正向 | ✅ **已是方向性**（rank0 相等 / rank1 正向前缀 / rank2 子串兜底；反向拒绝） | ✅ **已满足** |
| ② 词边界 | 🔴 **没有**。`norm_src` 的 `_PUNCT_RE = [^\w\s]` ⇒ **删掉撇号** ⇒ `'That'` → `'that'`，`"That's where we are today."` → `'thats where we are today'` ⇒ **rank1 成立 ⇒ 假前缀成立** | 🔴 **缺失** |
| ③ 跳过过短草稿 | 🔴 **故意不抄**（§41.3.5 已写明理由：渲染层不能因草稿太短就放弃替换，否则浅色草稿永远不被替换） | ⛔ **设计决策，不抄** |

🔴 **实测（真实 MT 产物 `hy_bench/runs/c111_half/c111_v5_ts10_nopunct.json` 的 `C_draft` 臂，
109 draft / 158 final；证据 `results/app/app053_draft_prefix_boundary_evidence.json`）**：

| 规则 | 配对数 | 覆盖率 | **跨段 max** | 跨段 > 10 | 段号倒流 | 正式稿被多草稿共用 |
|---|---|---|---|---|---|---|
| **产品现版**（App HEAD） | 95 | 0.8716 | 🔴 **85** | **2** | 0 | 0 |
| + 词边界（通知 13 第 2 步） | 95 | 0.8716 | 🔴 **33** | **1** | 0 | 0 |
| + 词边界 + min_len=10（通知 13 全三步） | 91 | 0.8349 | **2** | 0 | 0 | 0 |
| 🔴 **+ 跨段上限 2（拟实现的修法）** | **95** | **0.8716** | **2** | **0** | 0 | 0 |

⇒ 🔴 **产品现版确有 2 条离群错配**（跨段 85 / 33 段），
⇒ 🔴 **通知 13 的「词边界」单独用抓不住其中一条**（`Okay` + 逗号 ⇒ 词边界**合法**），
⇒ 🔴 **通知 13 的第 3 步（min_len=10）在渲染层不可用**（§41.3.5 的设计决策）。

#### §44.1.3 🔴 两条离群错配的**完整机制**（逐条查证到根因）

| 草稿 | 现版配到 | 跨段 | 真相 |
|---|---|---|---|
| `DRAFT::That`（seg 22，原文 `That`，**4 字符**） | seg 107 `That's where we are today.` | **85 段** | 🔴 **假前缀**：撇号被删 ⇒ `'that'` 是 `'thats where we are today'` 的前缀 ⇒ rank1 成立 ⇒「最短剩余正式稿优先」把**远处那个短句**选中 ⇒ 挤掉同段的正确候选（seg 22 `That does not mean we won't use external options…`） |
| `DRAFT::Okay`（seg 6，原文 `Okay`，**4 字符**） | seg 39 `Okay, next slide.` | **33 段** | 🔴 **短草稿 + 词边界合法**（`Okay` 后是逗号）⇒ **词边界判据抓不住**。🔴 进一步查证：seg 7 的草稿 `Okay So you recall, Alex spoke about…` 凑齐后提交于 **seg 8**，正式稿 `Okay So you recall, Alex spoke about business growth…` 正是 **seg 8** 的单元 ⇒ **`Okay` 的正确对象在 seg 8（跨 2 段）**，现版却抓到 33 段外 |

🔴 **共同的规律**：两条草稿都**只有 4 个字符** ⇒ 前缀条件极易成立
⇒ 而**短**正式稿在远处 ⇒ 「最短剩余正式稿优先」把它选中
⇒ 🔴 **产品渲染层**的既有排序键 `(rank, -len(dn), len(fn), di, fi)`
**没有「段相邻性」这一维**。

#### §44.1.4 ✅ 判据来源：**产品自身的 docstring 已经写明了段相邻性，只是没落到判据里**

🔴 `live_caption/caption_render.py` 模块 docstring（第 36–37 行）**原文**：

- 草稿单元的 `seg` = **段尾半句所在的那一段**（如段 5）；
- 正式稿单元的 `seg` = **凑齐后提交的那一段**（如段 6）

⇒ **草稿被正式稿替换 ⇒ 正式稿必然在段 N 或 N+1 附近**
⇒ 🔴 **「跨段上限」不是新造的产品行为，而是把 docstring 已声明的语义补进判据**。

---

### §44.2 🔴 用户可见的后果（③ 层实测）

🔴 `render_lines` 的逻辑（`caption_render.py` 第 300–330 行）：
正式稿**一旦就绪**就被从段聚合里**剔除**、**搬到草稿那一行**显示。
⇒ **配错 ⇒ 正式稿的译文出现在错误的段**，而**它自己那一段反而没有这句译文**
⇒ 🔴 **用户看到的是「译文挂在了不相干的位置」**。

🔴 **实测（`app053` 的 Q3 组，用真实产物喂进渲染层）**：
`DRAFT::That` 配到 seg 107 ⇒ 正式稿 seg 与草稿 seg **不一致** ⇒ **用户可见错位**（已 PASS 断言）。

---

### §44.3 🔴 拟实现的修法：**跨段上限 `MAX_SEG_SPAN = 2`**

#### §44.3.1 修法本体（候选文件，**本轮未改产品代码**）

候选文件：**`results/app/app053_caption_render_segcap_candidate.py`**
（23 094 B，sha256 `305c51b06671d3b1…`，由 HEAD 版 `git show HEAD:live_caption/caption_render.py`
经**唯一命中断言**（`assert count == 1`）派生 ⇒ **不是手抄**）

两处改动：
1. **新增常量** `MAX_SEG_SPAN = 2`（置于 `_PUNCT_RE` / `_WS_RE` 之后）；
2. **配对循环内**加跨段过滤：

```python
_draft_seg = d.get('seg')
...
_final_seg = f.get('seg')
if (isinstance(_draft_seg, int) and isinstance(_final_seg, int)
        and (_final_seg - _draft_seg) > MAX_SEG_SPAN):
    continue
```

🔴 **上限取 2 而非 1 的依据**：`DRAFT::Okay`(seg6) 的正确对象在 **seg8**
（草稿 seg7 凑齐后提交于 seg8）⇒ **span=2 合法**。

#### §44.3.2 ✅ 修法效果（真实 MT 产物实测，`app053` 证据 json）

| 指标 | 现版 | 候选 | 判定 |
|---|---|---|---|
| 配对数 | 95 | **95** | ✅ **零损失** |
| 覆盖率 | 0.8716 | **0.8716** | ✅ **零损失** |
| 草稿集合（被替换的草稿） | 109 中 95 | **完全相同** | ✅ |
| 跨段 max | 85 | **2** | ✅ |
| 跨段 > 10 的错配 | 2 | **0** | ✅ |
| 段号倒流 | 0 | **0** | ✅ |
| 正式稿被多草稿共用 | 0 | **0** | ✅ |
| 短草稿替换能力（§41.3.5 设计意图） | 保留 | **保留**（4 条 < 10 字符仍被替换） | ✅ |

🔴 **与「最小改动版」的差异 = 恰好 2 条**，且这 2 条**都是被修正的离群错配**：

| 草稿 | 现版（错） | 候选（对） |
|---|---|---|
| `DRAFT::Okay`（seg 6） | seg 39 `Okay, next slide.`（跨 33 段） | **seg 8** `Okay So you recall, Alex spoke about business growth…`（跨 2 段） |
| `DRAFT::That`（seg 22） | seg 107 `That's where we are today.`（跨 85 段） | **seg 23** `That Could be in situations like chipsets…`（跨 1 段） |

#### §44.3.3 ✅ 候选版本的回归验收（**零回归**）

| 验收脚本 | 结果 |
|---|---|
| `results/app/test_app015_caption_render.py`（§41） | ✅ **REAL 23/23 PASS ｜ BUG 5/5 命中 ｜ verdict=PASS** ⇒ **零回归** |
| `results/app/app047_app_gate_test.py`（§41） | ⚠️ **27/28** ⇒ 唯一 FAIL = **M9**（见 §44.3.4） |
| `results/app/app053_draft_prefix_boundary_probe.py`（本轮） | ✅ **16/16 PASS ｜ verdict=PASS** |

🔴 **回归跑法**：造「影子 `live_caption` 目录」只放**候选** `caption_render.py`
⇒ 把回归脚本的 `sys.path` 指向影子目录 ⇒ **不碰工作区的产品代码**
（`results/app/app053_regression_check.py`，3 358 B）。

#### §44.3.4 🔴 `app047` 的 M9 **前提已过期**（不是产品缺陷）

🔴 **M9 原文**：

```python
check('MATCH', 'M9 真实语料：与「最小改动版」逐条一致',
      m == minimal(drafts, finals), ...)
```

⇒ M9 的原意是验证「§41 落地的产品规则 == §41 的另一个候选『最小改动版』」⇒ 二者本就应一致。
🔴 **§44 故意引入新判据** ⇒ 产品规则**故意**不再等于「最小改动版」⇒ **M9 必然 FAIL**。
✅ **基线对照已做**：用**原版** `caption_render` 跑 `app047` = **28/28 PASS**；
用**候选**跑 = **27/28** ⇒ **唯一差异就是 M9** ⇒ 其余 27 项**零回归**。

✅ **M9 的候选替换块**（精确字符串替换 + 唯一命中断言）已备好：
**`results/app/app053_m9_assertion_candidate.txt`**（5 468 B，sha256 `125b82808f513fad…`）
⇒ 新断言 = 「**差异恰好 2 条** 且这 2 条**都是跨段错配的修正**」（差异数 ≠ 2 ⇒ 判 FAIL ⇒ 改动越界会被抓住）
⇒ 追加一条 **M9b**：「配对的跨段距离无离群错配（≤ 10 段）」。

🔴 **已实测**：在影子目录应用该替换块 ⇒ `app047` **29/29 PASS ｜ verdict=PASS**。

---

### §44.4 🔴🔴 **本轮未改产品代码**（等 reviewer 裁定，理由如下）

🔴 **依据本模块的既有做法**（§28.5 / §29.10 / §30.7 / §40.7 一致）：
**「字幕显示层的判据变更」属产品行为变更 ⇒ 只记录 + 附证据 + 等 reviewer 裁定**。

✅ **降低风险的三个事实**（供 reviewer 决策）：
1. 🔴 **方案 C 尚未进入交付包** ⇒ **本缺陷当前不影响已交付的 v1.5**
   —— v1.5 包内 `live_caption_app.py` 的 `caption_render` 命中数 = **0**；
   —— HEAD 版 `live_caption_app.py` 的 `caption_render` 命中数 = **0**
   ⇒ **方案 C 是工作区在制品**（`live_caption/live_caption_app.py` 命中 **4**，未提交）；
2. ✅ **修法不是新造行为**，而是把 `caption_render.py` **自身 docstring 已写明**的
   「草稿 seg = 段尾半句所在段 / 正式稿 seg = 凑齐后提交段」补进判据；
3. ✅ **零代价**：配对数 95 → 95、覆盖率 0.8716 → 0.8716、**零回归**
   （`test_app015` 23/23 + BUG 5/5 全过）。

🔴 **采纳时需要动的文件（仅 3 个）**：

| 文件 | 动作 |
|---|---|
| `live_caption/caption_render.py` | 用 `results/app/app053_caption_render_segcap_candidate.py` **覆盖**（候选由 HEAD 派生 ⇒ 唯一命中） |
| `results/app/app047_app_gate_test.py` | 应用 `results/app/app053_m9_assertion_candidate.txt` 的**替换 1 + 替换 2** |
| `results/app/app053_draft_prefix_boundary_probe.py` | 已在仓库（探针本身，无需改） |

⚠️ **本轮未做**：**未改 `live_caption/caption_render.py`**（保持 HEAD 原样）
⇒ ⇒ **未重打包、未重发 FTP**（本轮改动**不在包内**）。

---

### §44.5 ✅ 本轮产物清单（全部落盘，附实测元数据）

| 文件 | 字节 | mtime | sha256（前 16） |
|---|---|---|---|
| `results/app/app053_draft_prefix_boundary_probe.py` | 28 753 | 2026-10-26 01:53:39 | `4c5c4b4347b1cffc` |
| `results/app/app053_draft_prefix_boundary_evidence.json` | 4 711 | 2026-10-26 01:53:42 | `86d5d3950a9e35ec` |
| `results/app/app053_caption_render_segcap_candidate.py` | 23 094 | 2026-10-26 01:55:29 | `305c51b06671d3b1` |
| `results/app/app053_m9_assertion_candidate.txt` | 5 468 | 2026-10-26 01:56:16 | `125b82808f513fad` |
| `results/app/app053_regression_check.py` | 3 358 | 2026-10-26 01:55:11 | `eff32f773de08e59` |

🔴 **源产物（只读，未改）**：`hy_bench/runs/c111_half/c111_v5_ts10_nopunct.json`
430 633 B，mtime 2026-10-25 13:59:01，臂 `C_draft`（109 draft / 158 final）。

---

### §44.6 🔴 本轮纪律自检

| 项 | 状态 |
|---|---|
| `CORRECTIONS_APP.md` | ✅ **只读零改动**（SHA/size/mtime 与 §43 开始时逐位一致） |
| 结果写入 | ✅ 只写 `status/app/STATUS_APP.md`，**只追加 §44**（未回头改旧章节） |
| `last_ack` | ✅ **APP-017 不变**（无新条目 ⇒ 不变） |
| 「更新时间」 | ✅ **实测值 2026-10-26 01:56**（`Get-Date`） |
| 机器锁 | ✅ **未创建/未删除** `shared/MACHINE_LOCK`（ASR 持有）⇒ 未取锁 |
| 🔴 **不与持锁方并行跑 python** | ✅ 探针运行前用 §43 的 `wait_quiet_window_cpu` **等到了安静窗口**（ASR 进程被判「在等锁/在睡」⇒ 放行，3 次采样 **0 个 busy**）；**未启动任何推理/测速作业**；**未调 MiniMax** |
| 质量判定 | ✅ 未自行下质量结论（只报**结构化硬信息**：段号倒流 / 跨段距离 / 配对数 / 不变式） |
| 产品代码 | ✅ **未改** `live_caption/caption_render.py`（候选另存，等 reviewer 裁定） |
| 客户包 | ✅ **未改、未重打、未发 FTP** |
| git | ✅ 见 §44.7 |

---

### §44.7 git（只提交 App 职责内文件）

> 本节在提交后补记（§43 的做法）。

---

### §44.8 🔴 仍未闭环 / 待决

| # | 事项 | 状态 |
|---|---|---|
| 1 | 🔴 **「跨段上限」是否采纳**（`MAX_SEG_SPAN = 2`） | ⏳ **等 reviewer 裁定** ⇒ 候选 + M9 替换块已备好（§44.4） |
| 2 | 🔴 **MT 通知 13 的「产品不受影响」结论需更正** | ⏳ **需回复 MT**：App 渲染层**确实**受影响（跨段 85 / 33 段）⇒ 但「产品逻辑」的替换机制（`kind=draft/final`）不受影响 ⇒ 两说并存，**请 MT 复核** |
| 3 | 🔴 **通知 13 的「词边界」判据有盲区** | ⏳ **需回复 MT**：`Okay` + 逗号 ⇒ 词边界**合法** ⇒ 词边界**抓不住** ⇒ 建议改用「跨段距离」判据（通知 13 §13.4 的第 1 步 + 段相邻性） |
| 4 | 🔴 **通知 13 §13.5 `inconsistent_rate` 分母只有 10/109** | ⏳ 与 §41.3 一致（建议改报「人工抽看 20 条」）⇒ **App 不引用该率** |
| 5 | ✅ **§42.3 修复待用户实机确认** | 🔴 **只剩用户实机确认**（GUI 日志应出现「输出设备解析 … → 播放索引 N」与「实际输出: <设备名>」） |
| 6 | ✅ **§43 闸门修复待端到端验证** | 🔴 需在下一次 `pack_v13.py` 真实跑一次（本轮改动不在包内 ⇒ 未重打包） |
| 7 | ⛔ **WER +2.6pp 主因** | 未定位（不在 App 范围） |
| 8 | ⛔ **APP-015 方案 C 的 `translator.py` 合入** | 待 MT 移交（APP-009② / H-014，**MT 管辖，App 不代提交**） |
| 9 | ⛔ **包体 10.45 GiB 优化 / V7 残句代价 / 集显 F32 TTS 慢** | 未推进 |
| 10 | ⛔ **APP-017「检查点 3」** | 由**并发 App 会话**在做 ⇒ 本会话不重复跑、不抢锁 |

---

### §44.9 边界声明

🔴 本轮**只处理 App 模块职责**（渲染层匹配规则 / 打包 / 客户包一致性 / git）。
🔴 **未改** `translator.py`（MT 管辖）、**未改**任何他模块 `STATUS_*`、
🔴 **未改** `status/app/CORRECTIONS_APP.md`（reviewer 独占）。
🔴 **未替 reviewer 判定质量**（语义一致性仍以人工抽看为准）。
