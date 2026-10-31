### §121 ✅ **无新纠偏条目（`last_ack` 仍 APP-051）｜ 按 APP-046 继续做 ⇒ 收 git 尾时发现 `app076`/`app092` 两个闸门在跑 ⇒ 抓到「两个判据自身缺陷」（弱判据误报 + 过期断言）｜ 另修掉 `app187` 因 §120 正文引用一次性写入器而判 MISSING 的连带问题** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

#### 1. 本轮巡检口径

| 项 | 实测 |
|---|---|
| `status/app/CORRECTIONS_APP.md` | SHA256 `327f8653b62f28b6…39904` / **120 787 B** / mtime `2026-10-31 10:48:42` ⇒ **零改动**（reviewer 独占写入，只读） |
| `## APP-xxx` 条目数 | **51** 条（APP-001…APP-051） |
| 最大编号 | **APP-051** |
| `STATUS_APP.md` 头部 `last_ack` | **APP-051** ⇒ **无新纠偏条目**（**第 34 次**同一口径复核） |
| 本轮锁 | **未取锁**（全程只读 + 离线判据 + 静态 AST 分析，不计时、不跑推理） |

⇒ 按 **APP-046**「`last_ack` 追平后只要还有未完成项就自己继续做，不要空转」推进。

#### 2. 本轮起因：收 git 尾时**实跑** `app076`，抓到两个 FAIL

§120 的 git 收尾完成后，工作区仍有一批 **App 侧验收产物未入库**（`results/app/app015/036/044/045/047/069/070/072/073/076/079/089/097/105/107/129b/131/136/139/141/142/145/152/154/158/161/168` 等 **28 个已跟踪文件**有内容改动）。
逐个抽查 PASS/FAIL 计数时，**`app076` 的 `.txt` 是 `48 PASS / 1 FAIL`**（含 1 条 FAIL）⇒ 🔴 **不能直接入库** ⇒ 必须查清。

⇒ 实跑 `python results/app/app076_tts_playback_observability.py` ⇒ **47 PASS / 2 FAIL**，失败项：

| 判据 | 实测输出 |
|---|---|
| **A8** 源码：`played` 只在 `wait_consumed` 之后发出 | `played emit 点 1 个；before_wait=[False]` |
| **E9** 全目录扫描：无脚本再用「`n_played >= 1`」判定出声 | `扫了 391 个文件，违规 1 处：app186_app051_acceptance_gate.py: L174: ev2.get('n_played', 0) + ev2.get('n_dropped', 0) == ev2.get('n_submitted', -1)` |

⇒ 追查后确认：**两个 FAIL 都是「判据自身缺陷」，不是被测代码缺陷**（详见 §3、§4）。

#### 3. 🔴🔴🔴 真实缺陷①：`audible_criterion_lint` 的 E9 **误报**（弱判据 ⇒ 闸门恒 FAIL）

**根因（AST 拆解过粗）**：原实现用 `ast.walk(cmp)` 找比较器里的整数常量 ⇒ 把
`ev2.get('n_submitted', -1)` 里的 **`-1`** 拆成 `UnaryOp(USub, Constant(1))`
⇒ 其中 `Constant(1)` 命中 `VIOLATION_CONSTS = (1, 0)` ⇒ **把「守恒不变式」误判成弱判据**。

**被误判的那行**（`results/app/app186_app051_acceptance_gate.py` L174）：

```python
inv = ev2.get('n_played', 0) + ev2.get('n_dropped', 0) == ev2.get('n_submitted', -1)
```

⇒ 这是 **§60 `_drop_one()` 建立的不变式**（丢句记账守恒：`n_played + n_dropped == n_submitted`）
⇒ 它**比较的是两个和式**，**不是**「用 `n_played >= 1` 判定出声」⇒ **不是 APP-021 点名的弱判据**。

**修法（两处，都在 `results/app/audible_criterion_lint.py`）**：

1. 新增 `_comparator_int_value()`：**只认 comparator 本身**是整数常量，或 comparator 是 `UnaryOp(USub)` 且 operand 是整数常量 ⇒ **负数按其真实值算**（`-1` ⇒ `-1` ⇒ 不在 `VIOLATION_CONSTS` ⇒ 不命中）；
2. 新增 `_is_conservation_form()`：左值若是 **和式/差式**（`BinOp`）⇒ **守恒式** ⇒ 不命中。

**鉴别力自检（10/10 PASS ⇒ 判据非恒真）**：

| 用例 | 期望违规 | 实测 |
|---|---|---|
| `st.get('n_played', 0) >= 1`（APP-021 点名） | ✅ 违规 | ✅ 命中 |
| `st.get('n_played', 0) > 0` / `== 1`（等价写法） | ✅ 违规 | ✅ 命中 |
| `st.get('n_played', 0) > played_before`（相对增量） | ❌ 不违规 | ❌ 不命中 |
| `self.n_played += 1`（service 内部记账） | ❌ 不违规 | ❌ 不命中 |
| `ev2.get('n_played', 0) + ev2.get('n_dropped', 0) == ev2.get('n_submitted', -1)`（守恒不变式） | ❌ 不违规 | ❌ 不命中 |
| `x.get('n_played') == 1`（真弱判据） | ✅ 违规 | ✅ 命中 |
| `x.get('n_played') == -1`（负数阈值） | ❌ 不违规 | ❌ 不命中 |

#### 4. 🔴🔴🔴 真实缺陷②：`app076` 的 A8 **过期断言**（判据前提被 APP-028② 移除）

**根因**：**APP-028②**（用户明文「语音播放的时候，直接连续推理 TTS 音频流，**不要使用丢句这个方式**」）已把**播放路径**的 `played` emit 从 `synth()` 挪到**播放看门狗线程**的 `_finish_played()`（`live_caption/tts_worker.py` L2486）。
而 A8 的 AST 提取 `re_finditer_played()` **只扫 `synth()` 这一个函数** ⇒
`synth()` 里只剩**落盘路径**那个 `played` emit（L2401，`if not wait_play:` 分支）
⇒ 抓到的是**一个本来就不该等播放的分支** ⇒ 判据语义被彻底误读（`before_wait=[False]`）。

**当前代码的两处 `played` emit（实测）**：

| 行号 | 所在函数 | 语义 | 是否适用「须在 wait_consumed 之后」 |
|---|---|---|---|
| L2401 | `synth()` | **落盘模式 / 无播放器** ⇒ 不等播放，直接定案 | ❌ **不适用** |
| L2486 | `_finish_played()` | **播放看门狗** ⇒ 先 `wait_consumed()` 成功，再发 `played` | ✅ **适用**（L2443 的 `wait_consumed` < L2486） |

**修法（`results/app/app076_tts_playback_observability.py`）**：

1. `re_finditer_played()` 改为**按函数作用域**判定（全模块扫所有 `FunctionDef`）：
   - 所在函数**有** `wait_consumed` ⇒ **播放路径** ⇒ `played` emit **必须**在 `wait_consumed` **之后**（行号更大）；
   - 所在函数**没有** `wait_consumed` ⇒ **落盘路径** ⇒ **不适用**该约束（`before_wait = None`，**三态**）；
2. A8 断言本体改为：**适用路径必须全部 `before_wait=True`** **且必须至少有一个适用路径**
   ⇒ 否则判据**空转**（恒 PASS）⇒ 必须 FAIL（§36 同源教训）。

**鉴别力自检（4/4 PASS ⇒ 判据非恒真，注入法）**：

| 注入形态 | 期望合规 | 实测 |
|---|---|---|
| 真实合规形态（落盘分支 + 看门狗分支） | ✅ 合规 | ✅ |
| 注入缺陷①：`played` 在 `wait_consumed` **之前** | ❌ | ❌ 正确识破 |
| 注入缺陷②：播放路径**完全没有** `wait_consumed` | ❌ | ❌ 正确识破 |
| 注入缺陷③：全模块**没有任何** `played` emit（判据空转） | ❌ | ❌ 正确识破 |

#### 5. 🔴 顺手修掉第三个弱判据：`app092` 的 C2 用子串匹配

**原实现**：`check('C2 app076 全部 PASS（0 FAIL）', '0 FAIL' in (r.stdout or ''), ...)`
⇒ 🔴 **只要 `app076` 输出里任何地方出现 `"0 FAIL"` 字样**（例如某条 PASS 的 detail 里写着「违规 0 FAIL 项」）⇒ 就会**误判为合规** ⇒ 即使 `app076` 真有 N 个 FAIL 也照样 PASS ⇒ **闸门形同虚设**。

**修法**：改为**解析 `app076` 的汇总行**「结果：N PASS / M FAIL（共 K 项）」⇒ **只认这一行的 M** ⇒ `M == 0` 才算合规。

**反证（证明旧判据是弱判据）**：

| 场景 | 期望 | 旧（子串匹配） | 新（解析汇总行） |
|---|---|---|---|
| 真 2 FAIL ＋ 输出**别处**出现 `"0 FAIL"` 字样 | ❌ FAIL | ✅ **PASS ⇒ 反证成立** | ❌ 正确 FAIL |

⇒ 附带修掉 `app092` 缺 `import re` 的问题（新增的解析用到 `re`）。

#### 6. 🔴 连带修掉：`app187` 因 §120 正文引用一次性写入器而判 **MISSING**

**现象**：`app187`（§118 入库完整性闸门）报 `PASS 49 / FAIL 1` ⇒ `MISSING live_caption/_fix_dev_path_leak_c190.py`。

**根因**：§120 的 STATUS 正文**提到了**这个一次性写入器（§120 §2 的「半交付」表格里列了它）
⇒ `app187` 把它提升为「STATUS 引用的脚本」⇒ 要求它**必须入库**（`git ls-files` 在册）。

**处置**：**不改闸门**（闸门在正确工作），而是**把脚本修好并入库**：

1. 🔴 该脚本本身**写死了开发机仓库根**（`REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'`）
   ⇒ 修掉：改为**向上查找仓库根**（祖先目录含 `live_caption/` ＋ `pkg_paths.py`），**找不到就抛异常拒绝运行**（绝不退化成「用 cwd 猜」）⇒ 与 §119 的纪律一致；
2. **入库**：与仓库既有 **79 个** `_*.py` 一次性脚本先例一致（`_` 前缀**不是**「不入库」约定 —— 实测仓库里 79 个此类脚本**都已入库**）。

**修后实测**：幂等实跑 `PASS`（5 个生产模块的替换块均已应用）；`app187` 恢复 **PASS 50 / FAIL 0**。

#### 7. 本轮产物指纹（全部已落盘）

| 文件 | 字节数 | mtime | SHA256（前 16） |
|---|---|---|---|
| `results/app/audible_criterion_lint.py` | 11 786 | 2026-11-01 06:28:13 | `d3e6fbe06b90be8f` |
| `results/app/app076_tts_playback_observability.py` | 28 650 | 2026-11-01 06:28:34 | `c3d975f5c173cf21` |
| `results/app/app076_tts_playback_observability.txt` | 5 035 | 2026-11-01 06:29:51 | `57b7adfcff9cbdcc` |
| `results/app/app092_audible_criterion_gate_test.py` | 15 259 | 2026-11-01 06:29:16 | `14178d06be968df2` |
| `results/app/app092_audible_criterion_gate_evidence.json` | 4 884 | 2026-11-01 06:29:51 | `9be5e024572fc4fc` |
| `live_caption/_fix_dev_path_leak_c190.py` | 7 459 | 2026-11-01 06:31:16 | `6f64dcdaf1e29dc4` |
| `results/app/app187_discrimination_evidence.json` | 1 508 | 2026-11-01 06:31:50 | `53d1e3a2d6adae73` |

#### 8. 本轮回归（全部实跑，非引用历史结论）

| 闸门 | 结果 |
|---|---|
| `app076_tts_playback_observability.py` | **49 PASS / 0 FAIL**（修前 47/2） |
| `app092_audible_criterion_gate_test.py` | **24 PASS / 0 FAIL**（修前 22/2） |
| `app187_repo_artifact_in_repo_gate.py` | **PASS 50 / FAIL 0**（修前 49/1） |
| `app187_discrimination_test.py` | **PASS 9 / FAIL 0** |
| `app186_app051_acceptance_gate.py` | **PASS 25 / FAIL 0** |
| `app188_pkg_repo_module_parity_gate.py` | **PASS** |
| `app189_pkg_dev_path_leak_gate.py` | **PASS** |
| `app190_dev_path_leak_fix_evidence.py` | **PASS 8 / FAIL 0** |
| `app168_pkg_runtime_import_probe.py` | **PASS 21 / FAIL 0** |
| `app107_app030_lang_runaway.py` | **PASS 42 / FAIL 0** |

#### 9. 本轮 git 收尾

| commit | 内容 |
|---|---|
| `80bbc01` | `docs(app): §120` —— STATUS §120 章节（**198 插入 / 1 删除**，唯一删除行是有意的「更新时间」替换） |
| `47dff22` | `chore(app)` —— 补录 §114/§115 遗留的 `.gitignore` 条目（`results/app/_v3b_clone_src/`、`results/app/_v3_cer_cache/`） |
| `a68a2a4` | `fix(app): §121` —— 修掉 `_fix_dev_path_leak_c190.py` 写死开发机仓库根 ⇒ 可入库 |

⇒ 逐文件 `git add`（**未用 `-A`**）⇒ 每个 commit 校验 `grep -c CORRECTIONS` **== 0** ⇒ **普通快进 push**（未 force push）⇒ 仓库仍**只有 `main` 分支**。
⇒ 🔴 **本轮未提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占写入，零改动）⇒ 也**未吞** ASR/MT/TTS 其它模块的未提交改动。

#### 10. 本轮**没做**的事（明确留白）

1. 🔴 **未重打包**（本轮改的是**验收脚本**与**一次性写入器**，**不涉及客户包生产模块** ⇒ 包内容无需变化；且按用户级约定「不通知 ⇒ 不主动打包」）；
2. 🔴 **未删除**历史 zip / 旧包目录（破坏性操作需用户确认）；
3. 🔴 **未运行** `publish_ftp.py` / 未启动 FTP 服务（守 APP-035）；
4. 🔴 **未跑推理 / 未测速**（本轮全程只读 + 离线判据 + 静态 AST ⇒ **未取共享机器锁**）；
5. 🔴 **未动**那批「仓库有、包没有」的一次性脚本（`app188` 明确**不判负** ⇒ 只列清单）；
6. 🔴 **未修** §119 §5.6 提出的 `.gitattributes` 议题（会触发全仓行尾重写 ⇒ 需 reviewer 裁定）。

#### 11. 仍等 reviewer 复核（§117–§121 累计）

| # | 事项 |
|---|---|
| ① | 🔴 **需用户实听 3 段 1.2–1.3× 配音素材**（`C:\Users\Trekker-PTL\shared\app_accel_listen\`）＋ reviewer 判定音质 / 不变调 / 可懂 —— `app186` 总闸门只覆盖**链路 + 结构 + 数字自洽**（`ACCEPTED.json.scope` 已明写），**质量判定不在其中** |
| ② | 🔴 **§117 待复核 2 项**（APP-043「通过」口径 / `app186` 总闸门 25 条判据口径） |
| ③ | 🔴 **§115 待复核 5 项**（`EXECUTION_DEVICES` 返回类型口径 —— **推翻了 §82 的旧解读** / `absent`-`unknown` 分离 / talker 聚合所有桶 / App 不调 `build()` / TTS 侧 `cp_decode_device` 未被消费） |
| ④ | 🔴 **§114 待复核 4 项**（CI 判据口径 / 写法差异 vs 真错误拆分 / 多 3 句真错误是否提示用户 / 是否用最新包重跑） |
| ⑤ | 🔴 **宿主 `PYTHONPATH` 污染对历史验收结论的影响范围**（§112 已证明它会让 `torch` 假阳性） |
| ⑥ | 🔴 **§113 待复核 4 项**（版本标识闸门口径 / 「改动说明」归为提醒不阻断 / `sync_c172` 设计 / v1.13 改动说明排期） |
| ⑦ | 🔴 **`app188` 判据口径**（`orphan` 判阻断是否过严 / `repo_only` 不判负是否可接受 / `dev_only_orphan` 是否完全以 `pkg_exclude` 为准） |
| ⑧ | 🔴 **95 处「过期包版本」引用的清点结论**（本轮只清点未改；建议另开专项，不在本轮扩大改动面） |
| ⑨ | 🔴 **§119 §5.6「是否加 `.gitattributes`」**（会触发全仓行尾重写） |
| ⑩ | 🆕🔴 **§120 待复核 3 项**（`app189` 判据口径与是否接入 `pack_v13.py` 打包前闸门 / CUDA 路径仍需用户自设 `LIVECAP_CUDA_PY`，本轮未把 CUDA 变成「客户机开箱可用」 / 两个 TTS 验收脚本「过期断言」的处置方式） |
| ⑪ | 🆕🔴 **§121 待复核 4 项**：① **E9 的「守恒式不算弱判据」这条新规则是否认可**（判据边界由 reviewer 定；本轮把它实现为「左值是 BinOp ⇒ 不命中」＋「比较器常量只认 comparator 本身」）② **A8 改「按函数作用域判定 ＋ 三态」是否认可**（原口径只扫 `synth()` ⇒ 在 APP-028② 之后必然误判）③ **A8 新增的「必须至少有一个适用路径」这条防空转约束是否认可** ④ **「STATUS 正文提到某脚本 ⇒ 该脚本必须入库」这条连带效应是否认可**（本轮据此把一次性写入器修好并入库；或 reviewer 认为应改为「STATUS 不引用一次性脚本」） |
