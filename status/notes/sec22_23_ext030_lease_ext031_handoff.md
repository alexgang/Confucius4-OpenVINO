# §22 / §23 全量明细 —— EXT-030（模块租约）+ EXT-031（V2.0 交付清单）

> ★ 本文件是 `status/STATUS_EXT.md` 中 **§22 / §23 两节的全量明细**。
> ⚠️ **不回头改旧章节的结论**——数字一字未改。
> ★ 依据 **EXT-016 写作规则**（STATUS ≤ 300 行 / ≤ 40 KB / < 归档/10 = 22 483 B）。

---

## §22.1 ★★ EXT-030①：自动化指令新增段落原文（reviewer 要看的「新指令文本」）

★ **载体**：WorkBuddy 自动化 `EXT 模块纠偏定期检查（CORRECTIONS_EXT）`
（id = `9ec49c32-eda2-48e1-9d97-21202a2c3fab`，`FREQ=HOURLY;INTERVAL=1`，status=`ACTIVE`）
★ **改法**：用 WorkBuddy 的**自动化编辑功能**在现有「第 0 步」**之前**插入租约段，
并在「执行步骤」之后追加心跳 / 长作业 / 收尾三段。
★ **未改**其他四个模块的自动化（EXT-030 说的是「修改本模块自己的自动化指令」）。

### 新增段 ①（插在「第 0 步」之前）

```
## ★ 第 0 步之前：先拿「模块租约」（EXT-030，五个模块统一）
★ 目的：同一个模块**不能**有两个会话同时 working（否则互相抢 MACHINE_LOCK、重复打包/重复测速、token 白白浪费）。
```
"C:\Users\Trekker-PTL\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\Trekker-PTL\shared\tools\session_lease.py" acquire ext
```
- **exit 0** ⇒ 拿到 `TOKEN=xxxx` ⇒ 把这个 token 记下来，**后续所有** beat / addpid / release 都带上它。
  ★ 若输出里出现 `TAKEOVER` ⇒ 上一会话已经死了 ⇒ **先读**它留下的 note、`STATUS_EXT.md`、`EXEC_LOG.md` 与已落盘的产物，**从断点继续**，不要从头重做。
- **exit 10（BUSY）** ⇒ 另一个会话或它的后台作业还活着 ⇒ 只输出一句「上一会话仍在进行，跳过本轮」，然后**立即结束**：不读其他文件、不改任何东西、不碰锁、不提交。
- 其它非 0 退出码 ⇒ 按「无法解析，跳过本轮」处理，零改动结束。
```

### 新增段 ②（会话心跳，EXT-030②）

```
## ★ 会话心跳（EXT-030 ②）
★ **每完成一步、以及每次耗时操作前后**，都要跑一次：
```
"C:\Users\Trekker-PTL\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\Trekker-PTL\shared\tools\session_lease.py" beat ext <token> "<一句话进度>"
```
★ 心跳超过 30 分钟会被视为死会话。
★ **exit 11（LOST）** ⇒ 租约已被别的会话接管 ⇒ **立即停止**，不再写任何文件、不提交、不动锁。
```

### 新增段 ③（长作业，EXT-030③）

```
## ★ 长作业（打包 / 计时 / e2e）的做法（EXT-030 ③）
一律用 `schtasks` 或 `Start-Process` **后台启动**，**拿到 PID 后马上**登记：
```
"C:\Users\Trekker-PTL\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\Trekker-PTL\shared\tools\session_lease.py" addpid ext <token> <pid>
```
★ **不要**在一个工具调用里同步等待超过 20 分钟 ⇒ 分次轮询，**轮询之间 beat**。
★ 只要登记的 PID 还活着，新会话就会拿到 BUSY ⇒ 不会重复启动同一个作业。
```

### 新增段 ④（本轮结束，EXT-030④）

```
## ★ 本轮结束（最后一步；**无论是否跳过都要做**）
```
"C:\Users\Trekker-PTL\.workbuddy\binaries\python\envs\default\Scripts\python.exe" "C:\Users\Trekker-PTL\shared\tools\session_lease.py" release ext <token>
```
★ 若还有后台作业活着，脚本会自动**保留**租约（输出 `KEPT`）—— 这是正常行为，**不要**手工删 `C:\Users\Trekker-PTL\shared\leases\` 下的文件。
```

### 新增段 ⑤（铁律区补一条）

```
- **模块租约**（EXT-030）：开工前 `acquire`、过程中 `beat`、长作业 `addpid`、结束 `release`。租约管的是「同一模块不能有两个会话同时 working」，`MACHINE_LOCK` 管的是「不同模块不要同时占用设备」——**两者都要遵守，互不替代**。
```

---

## §22.2 ★★ 本轮实测：EXT-030 描述的故障**当场复现**

### 时间线（实测）

| 时刻 | 事件 | 证据 |
|---|---|---|
| 15:42:39 | 另一 EXT 会话 `acquire ext` 成功 ⇒ token=`c3389eb3`，note=`EXT-029 A/B PASS(10/0) + EXT-031 改造中` | `shared/leases/ext.json` |
| 15:44:46 | 该会话**最后一次** `beat` | 同上（`beat` 字段） |
| 16:06:29 | **本会话**开工 ⇒ 探测租约 ⇒ `alive=True`、心跳已 **21.7 min** 未更新 | `session_lease.py status ext` |
| 16:06~16:14 | **本会话** `acquire ext` ⇒ **exit 10 (BUSY)** ⇒ ★ 按铁律**不抢**，改**后台轮询等待**（每 20 s 一次 × 40 次） | 41 次尝试日志 |
| 16:14:53 | 心跳满 **30 min** TTL ⇒ `acquire` 返回 **exit 0 + `TAKEOVER stale lease`** ⇒ 本会话拿到 **`TOKEN=16a4f381`** | 轮询日志第 41 次 |

★ **结论**：租约机制**真实生效** —— ① 重叠会话被 BUSY 挡住；② 死会话超时后新会话**自动接管**；
③ 接管后**从断点继续**（上一会话的 EXT-031 改造**已在 HEAD `daaa00d` 里** ⇒ 本轮**未推倒重做**，只补缺的部分）。

★ ⚠️ **本轮踩到的一个真问题**：`acquire` 的 `TAKEOVER` 只在**心跳超 30 min** 后才发生
⇒ 上一会话若在 30 min 内活跃但**已卡死**，新会话会**干等 30 分钟**。
⇒ 这是 `session_lease.py` 的 TTL 设定（reviewer 部署的脚本）⇒ **本模块不改它**（只读使用），
★ 但**如实报出**：若 reviewer 想缩短等待时间，可把 `TTL_MIN` 从 30 调到 10–15。

---

## §22.3 机器锁（本轮）

★ 本轮**未跑计时刻速作业**（EXT-031 的模拟包验证是**纯路径解析**，不占 GPU/NPU、不跑推理）
⇒ **未创建也未回收** `C:\Users\Trekker-PTL\shared\MACHINE_LOCK`。
⇒ 两套机制**互不替代**：租约管「同一模块不能有两个会话」，MACHINE_LOCK 管「不同模块不要同时占设备」。

---

## §23.1 EXT-031① 交付清单 `release/V20_HANDOFF.md`

**新建文件**：`release/V20_HANDOFF.md`（★ 打包由 **App 线程（APP-057）**执行，EXT 只交清单）。

### 插件 unpacked 目录（实测 `find extension -type f` ⇒ **15 文件 / 219 021 B**）

| 文件 | 字节 |
|---|---|
| `manifest.json` | 1 694 |
| `sw.js` | 14 268 |
| `offscreen.js` | 25 064 |
| `offscreen.html` | 156 |
| `player.js` | 119 667 |
| `player.html` | 3 267 |
| `popup.js` | 20 622 |
| `popup.html` | 5 502 |
| `capture-worklet.js` | 8 281 |
| `onset-worklet.js` | 2 801 |
| `USER_GUIDE.md` | 16 808 |
| `icons/icon16.png` | 116 |
| `icons/icon32.png` | 152 |
| `icons/icon48.png` | 180 |
| `icons/icon128.png` | 443 |

★ **剔除**：`extension/probe-worklet.js`（391 B）—— ★ **全目录零引用**
（`grep -rn "probe-worklet" extension/ tests/` ⇒ 无结果）⇒ 遗留探针件。

### Python 依赖（实测 App 包 `v1.13` 的 `pip list`）

| 包 | 本模块实测版本 | App 包内版本 | App 包内有没有 |
|---|---|---|---|
| `numpy` | 2.5.4 | 2.4.6 | ✅ 有 |
| `openvino` | —（本机未装） | 2026.4.1 | ✅ 有 |
| `openvino-genai` | —（本机未装） | 2026.4.1.0 | ✅ 有 |
| `websockets` | 17.3 | — | ❌ **缺** |
| `psutil` | 7.2.2 | — | ❌ **缺** |

★ **打包必做**：补装 `websockets==17.3` + `psutil==7.2.2`
（建议 `--target <包根>\ext\.runtime_deps` ⇒ **不污染** App 的 site-packages）。

### 模型 / IR 映射（**全部映射到 App 包内现有，不另带一份**）

| 用途 | 包内相对路径 | App 包内实测 |
|---|---|---|
| ASR encoder / decoder | `models/encoder-int8` / `models/decoder-gpu-int8` | ✅ |
| MT | `models/mt/mt2-int8sym-cw-q` | ✅ |
| TTS | `models/qwen3tts` | ✅ |
| 说话人分段 | `models/spk/pyannote_seg_3_0/fp16` | ✅ |
| 说话人嵌入 | `models/spk/wespeaker-resnet34-fp16` | ✅ |
| 引擎代码 | `app/`（`seg_stream.py` / `translator.py` / `tts_engine.py`） | ✅ |
| 说话人 runtime | `app/asr_spk/asr052_spk_runtime.py` | ✅ |

---

## §23.2 ★★ EXT-031② 「不依赖开发目录」实测

**脚本**：`tests/smoke/ext031_fake_pkg_launch.py`（新建）

### 做法（真跑，不是看代码）

1. 造**模拟发行包根** `…\Confucius4_LiveCaption_v2.0`（目录名**故意不叫** `live_dub_ext`），
   把 `ext/` 整个拷进去（`shutil.copytree`），并造 `app/` + `models/` 占位。
2. **把开发机从视野里切掉**：
   - `EXT_APP_ROOT` ⇒ 模拟包；
   - `EXT_APP_SEARCH_ROOT` ⇒ **空目录**（不许回退到开发机的 `Confucius4_LiveCaption_v*`）；
   - 环境里**清掉** `EXT_R2T2_ROOT` / `EXT_HY_ROOT` / `EXT_TTS_ROOT` / `EXT_SPK_SEG_IR` / `EXT_SPK_WES_IR`。
3. 在模拟包根里**真启动**探针，打印全部路径相关字段。

### 结果（**6 PASS / 0 FAIL**）

| 断言 | 实测 |
|---|---|
| 探针进程 rc=0 | ✅ |
| `resolve_app_root()` = **模拟包** | ✅ `…\ext031_pkg_xxx\Confucius4_LiveCaption_v2.0` |
| 引擎根 + 模型目录 + 说话人 IR **全部落在模拟包内** | ✅ 越界项**无** |
| 解析结果**不含**任何开发机目录名 | ✅ 命中**无** |
| `package_root()` = 模拟包根 | ✅ |
| `EXT_RELEASE=1` ⇒ 白名单只留 `tabCapture` | ✅ |

**证据落盘**：`.tmp/ext031/fake_pkg_probe.json`（**2 836 B**）
★ 静态复核：`ext/` 里**非 docstring 的字符串字面量**（AST 级）**零**命中
`live_dub_ext` / `hy_bench` / `confucius4-openvino` / `qwen3tts_eval` / `Worktrees` / `confucius4-tts`。

---

## §23.3 ★ EXT-031③ 发行版调试剔除

### 开关（`ext/config.py`）

`RELEASE_MODE` 判定顺序（**显式覆盖永远优先**）：
① 环境变量 `EXT_RELEASE`（`1/true/yes/on` ⇒ True；`0/false/no/off` ⇒ False）；
② 包根 `release.json`（`{"release": true}` ⇒ True）；
③ 默认 **False**（开发目录保持现状）。

### 发行版下**自动失效**的东西（实测）

| 项 | 行为 | 实测 |
|---|---|---|
| 整机 `getDisplayMedia` 回退 | ✅ **禁用** | `CAPTURE_MODES` = `['tabCapture']` |
| `--audio-dump-out` | ✅ **忽略**（`ext/bridge.py` 创建点受 `RELEASE_MODE` 保护） | 静态 + 行为双查 |
| `--margin-out` | ✅ **忽略**（退出前落盘受 `RELEASE_MODE` 保护） | 同上 |
| Playwright 驱动 | ✅ **不在发行包内**（只在 `tools/`） | 文件名双查 |

★ **本轮新增的两处改动**（`ext/bridge.py`）：
① `--audio-dump-out` 创建点加 `RELEASE_MODE` 保护（发行版即使显式传也只打一行警告）；
② 退出前的 `_dump_margin(holder, args.margin_out, engine)` 加 `RELEASE_MODE` 保护。

---

## §23.4 自测（实测）

| 套件 | 结果 |
|---|---|
| `tests/test_ext031_release_handoff.py`（新建，**7 个用例**） | **24 PASS / 0 FAIL** |
| `tests/smoke/ext031_fake_pkg_launch.py`（新建） | **6 PASS / 0 FAIL** |
| `tests/test_ext029_spk_bypass.py` | **70 PASS / 0 FAIL** |
| `tests/test_ext028_dub_audio_chain.py` | **42 PASS / 0 FAIL** |
| 三套明文自测 | **106 / 11 / 19**，全 rc=0 |

★ **本轮修掉的 4 个「测试自身的坑」（区分力校准）**：
① 依赖比对用 `openvino_genai`（import 名）去匹配清单里的 `openvino-genai`（PyPI 名）⇒ **误报 FAIL**
⇒ 改为**归一** `_`/`-` 后比对；
② AST 字面量扫描把**docstring** 也算进去了（docstring 里写「原路径是 `C:\…\hy_bench`」是**说明**，不是运行时依赖）
⇒ **误报 FAIL** ⇒ 改为**排除 docstring 节点**；
③ 插件目录「无测试驱动」正则里的 `probe` **误伤**了 `probe-worklet.js`（那本是生产件）
⇒ 改为只匹配 `test_` / `_test.` / `_harness` / `playwright` ⇒ 并**顺手剔掉**真正零引用的 `probe-worklet.js`；
④ `check()` 的 `detail` 传了 **list** ⇒ `TypeError: can only concatenate str (not "list") to str`
⇒ 改为 `"; ".join(...)`。

★ ⚠️ **这 4 条都属于「测试口径」而非「产品缺陷」** ⇒ 按 EXT-016「不改写旧断言掩盖回归」的规则，
本轮**新增**一个独立文件 `tests/test_ext031_release_handoff.py`，**未改动任何既有断言**。

---

## §23.5 ⛔ 明确未做 / 不宣称

- ⛔ **打包动作由 App 线程执行（APP-057）** ⇒ EXT 只交清单，**未产出 zip**。
- ⛔ **音色克隆不可用**（`voice_source` 实测全 `'preset'`、`clone_wired=false`）⇒ **不宣称克隆音色可用**。
- ⛔ **tabCapture 生产路径未实测**（自动化拿不到 ⇒ 需用户点一次扩展图标）。
- ⛔ **「英译中」未真正测到**（抓流仍是整机声音）⇒ 发行版只用 `tabCapture` ⇒ 这条在发行版自然消失，但**仍需用户实测确认**。
- ⛔ **端到端仍不实时**（RTF **2.0507** / TTS **1.0022**）⇒ TTS 提速是上线的唯一前置（**由主会话转达 TTS 模块**）。
- ⛔ **同步误差仍超标**（`sync_err_ms.p50=67289.3` / `n_over_target=22`）。
- ⛔ **Edge 真实手势 1 分钟验收未做**（由用户本人做）。
- ⛔ **未改任何引擎文件**；⛔ **未改 `shared/tools/session_lease.py`**（reviewer 部署 ⇒ 只读使用）。
- ⛔ **未推远程**；⛔ `status/CORRECTIONS_EXT.md` **只读、未修改、未入库**。
