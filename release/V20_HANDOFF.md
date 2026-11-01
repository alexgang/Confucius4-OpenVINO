# V2.0 交付清单 — Live Dub EXT（实时翻译配音插件）

> ★ **给 App 线程（APP-057 打包）用**。EXT 负责交付物本身 + 这份清单；**打包动作由 App 线程执行**。
> ★ 打包时需要改的东西只有两处，**都在本文末「打包时必改」小节**列清楚了。

---

## 0. 一句话结论（reviewer 先看这里）

| 项 | 状态 |
|---|---|
| 插件 unpacked 目录 | ✅ **可打包** —— `extension/`（**15 个文件 / 219 021 B**），零测试驱动残留 |
| 桥接服务 | ✅ **可打包** —— `ext/`（21 个 .py），**不依赖任何开发机目录**（实测见 §7） |
| **EXT-028（配音听不清）** | ✅ **已修**（根因 + 修法 + 42 项自测全绿，见 §6）⇒ **不构成打包阻塞** |
| **EXT-027（抓流 / 按序播放）** | 🟡 **代码侧已修**，但 **tabCapture 生产路径未实测**（自动化拿不到，需用户点一次扩展图标）⇒ 见 §8「打包前必须知道的事」 |
| **EXT-029（说话人旁路）** | ✅ **已修**（独立线程 + 有界队列 + 异步回填，不反压 ASR）⇒ 见 §8 |
| 音色克隆 | ⛔ **仍不可用**（`voice_source` 全 `'preset'`，引擎层 `voice` 参数未接进 `tts_engine.stream()`）⇒ **发行版按「预设音色」发布** |
| Python 依赖 | ⚠️ **App 包内缺 2 个**：`websockets` / `psutil`（**必须补装**，见 §3） |

---

## 1. 插件 unpacked 目录（打进 V2.0 的 `extension/`）

**源目录**：`live_dub_ext\extension\` —— **15 个文件 / 219 021 B**（实测 `find extension -type f`）。

| 文件 | 字节 | 说明 |
|---|---|---|
| `manifest.json` | 1 694 | MV3 清单。★ 打包时改 `liveDub.release` → `true`、`liveDub.captureModes` → `["tabCapture"]`（见 §9） |
| `sw.js` | 14 268 | Service Worker（`type: module`）。含路由 `/hello` `/capture_info` `/flush` |
| `offscreen.js` | 25 064 | 离屏抓流。★ `tabCapture` 抓标签页音频（EXT-027①）；发行版禁用整机 `getDisplayMedia` 回退 |
| `offscreen.html` | 156 | offscreen 承载页 |
| `player.js` | 119 667 | 播放页主体：PCM 重建、排程播放、诊断链路 |
| `player.html` | 3 267 | 播放页 |
| `popup.js` | 20 622 | 扩展弹窗（面板设置、8 个控件**改了就落盘**） |
| `popup.html` | 5 502 | 弹窗 |
| `capture-worklet.js` | 8 281 | 采集 AudioWorklet |
| `onset-worklet.js` | 2 801 | 起音检测 worklet |
| `USER_GUIDE.md` | 16 808 | 用户指南（**建议随包**，但注意里面有开发机路径，见 §9 第 3 条） |
| `icons/icon16.png` | 116 | 图标 |
| `icons/icon32.png` | 152 | 图标 |
| `icons/icon48.png` | 180 | 图标 |
| `icons/icon128.png` | 443 | 图标 |

⇒ **插件侧只需剔除 1 个文件**：`extension/probe-worklet.js`（391 B）★ **全目录零引用**
（`grep -rn "probe-worklet" extension/ tests/` ⇒ 无结果）⇒ 属遗留探针件，已删。
⇒ 其余 15 个文件**全部保留**：`extension/` 内**零** Playwright 驱动 / 测试脚本
（自测 `test_plugin_dir_has_no_test_driver` 断言文件名双查）。

---

## 2. 桥接服务入口命令

**桥接代码**：随包放在 `<包根>\ext\`（**21 个 .py**），与 App 的 `app/` **平级**。

### 2.1 生产启动命令（发行版）

```bat
:: 用 App 包内自带的 python（**不要**用系统 python）
"<包根>\python\python.exe" "<包根>\ext\bridge.py" ^
    --real ^
    --target-lang en ^
    --host 127.0.0.1 --port 8765 ^
    --pair-port 8766 ^
    --pipeline ^
    --spk-bypass
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--real` | 关 | ★ 生产**必须**带（否则是回声自测模式）。`--echo` 是回声模式，**发行版不要用** |
| `--target-lang` | `en` | 目标语言（`en`/`ja`/`ko`/`zh` …） |
| `--host` / `--port` | `127.0.0.1` / `8765` | 桥接 WS 服务 |
| `--pair-port` | `8766` | 配对服务（= `--port` + 1） |
| `--pipeline` | **默认开** | 流水线模式（按段定稿 → 翻译 → 合成 → 排程播放） |
| `--spk-bypass` | **默认开** | 说话人旁路（EXT-029）；`--no-spk-bypass` 关闭 |
| `--warmup-strict` | 关 | 预热失败即退出（发行版建议**开**，避免半残状态启动） |
| `--token-file` | `bridge_token.txt` | 见 §5 |
| `--margin-out` / `--audio-dump-out` | 无 | ★ **诊断落盘**，发行版**自动失效**（EXT-031③） |

### 2.2 发行版必须加的环境变量

```bat
set EXT_RELEASE=1
```
（或在包根放 `release.json` = `{"release": true}` —— 见 §9 第 1 条）

★ **作用**：`RELEASE_MODE=True` ⇒
① 抓流白名单**只留 `tabCapture`**（整机 `getDisplayMedia` 回退被剔除）；
② `--audio-dump-out` / `--margin-out` **不生效**（诊断产物不进用户机器）。

---

## 3. Python 依赖（包名 + 版本 + App 包内缺哪些）

### 3.1 全部依赖（`ext/` 里真正 `import` 的第三方包）

| 包名 | 实测版本（WorkBuddy python） | App 包内 v1.13 实测版本 | App 包内**有没有** | 用途 |
|---|---|---|---|---|
| `numpy` | **2.5.4** | **2.4.6** | ✅ 有 | 音频缓冲 / 特征 |
| `openvino` | （WorkBuddy python 无） | **2026.4.1** | ✅ 有 | OpenVINO 推理运行时 |
| `openvino-genai` | （WorkBuddy python 无） | **2026.4.1.0** | ✅ 有 | GenAI（TTS） |
| `websockets` | **17.3** | — | ❌ **缺** | ★ **桥接 WS 服务端**（`ext/bridge.py` 的 `websockets.serve`） |
| `psutil` | **7.2.2** | — | ❌ **缺** | ★ **重复启动检测**（`ext/bridge.py` 扫进程，端口占用时给友好提示而不是整屏 traceback） |

> ★ **App 包内 `python/` 只有 `pip` 可用**时，请按 §3.3 补装。

### 3.2 ★★ App 包内**还需要**补装的（**打包必做**）

```bat
"<包根>\python\python.exe" -m pip install --no-warn-script-location ^
    --target "<包根>\ext\.runtime_deps" websockets==17.3 psutil==7.2.2
```

★ **不污染** App 的 `site-packages`、**不改** App 任何文件（沿用本模块既有做法）。
启动时把 `.runtime_deps` 塞进 `PYTHONPATH`：

```bat
set PYTHONPATH=<包根>\ext\.runtime_deps;%PYTHONPATH%
```

（`ext/bridge.py` **也会**自动把包根 `.runtime_deps` 加进 `sys.path` —— 见 `tools/ext_launcher.py`
同款逻辑；**但发行版用裸 `python.exe ext\bridge.py` 启动时，请显式设 `PYTHONPATH`**。）

### 3.3 若不允许 `--target` 的备选

直接装进 App 包内 python（**需要 App 线程同意**，会改 App 的 site-packages）：
```bat
"<包根>\python\python.exe" -m pip install websockets==17.3 psutil==7.2.2
```

### 3.4 版本约束（**建议**）

| 包 | 约束 | 理由 |
|---|---|---|
| `numpy` | **≥ 2.0**（App 内 2.4.6 已实测通过） | 引擎侧数组接口 |
| `openvino` | **2026.4.1**（= App 内版本，**不另带**） | IR 版本必须与运行时匹配 |
| `openvino-genai` | **2026.4.1.0**（= App 内版本） | 同上 |
| `websockets` | **≥ 14**（实测 17.3） | `websockets.serve` API |
| `psutil` | **≥ 5.9**（实测 7.2.2） | `process_iter` |

---

## 4. 模型和 IR 路径（**映射到 App 包内现有，不另带一份**）

★ **一条铁律**：EXT **不携带任何模型/IR**。全部映射到 App 包内 `models/` 下**已有**的目录。

### 4.1 映射表（代码里的解析逻辑 = `ext/engines.py` → `_resolve_roots()`）

| 用途 | 引擎/文件 | **包内相对路径** | App 包内实测 |
|---|---|---|---|
| ASR 编码器 | R2T2 encoder | `models/encoder-int8` | ✅ 存在 |
| ASR 解码器 | R2T2 decoder | `models/decoder-gpu-int8` | ✅ 存在 |
| MT | Hy-MT2 | `models/mt/mt2-int8sym-cw-q` | ✅ 存在 |
| TTS | Qwen3-TTS | `models/qwen3tts` | ✅ 存在（含 `int8/` `tokenizer/` `voices/` `weights/`） |
| 说话人**分段** | pyannote seg-3.0 | `models/spk/pyannote_seg_3_0/fp16` | ✅ 存在（`.bin` + `.xml`） |
| 说话人**嵌入** | wespeaker-resnet34 | `models/spk/wespeaker-resnet34-fp16` | ✅ 存在（`.bin` + `.xml`） |
| 引擎**代码** | R2T2 / Hy-MT2 / Qwen3-TTS 原件 | `app/`（`seg_stream.py` / `translator.py` / `tts_engine.py`） | ✅ 存在 |
| 说话人 runtime | `asr052_spk_runtime.py` | `app/asr_spk/` | ✅ 存在 |

### 4.2 解析顺序（**显式覆盖永远优先**）

| 目标 | ① 环境变量（可选覆盖） | ② 默认（相对 App 包根） |
|---|---|---|
| App 根目录 | `EXT_APP_ROOT` | 用户目录下 `Confucius4_LiveCaption_v*`（按版本从新到旧选**结构完整**的：`app/` + `models/` + `python/python.exe`） |
| ASR / MT / TTS 代码根 | `EXT_R2T2_ROOT` / `EXT_HY_ROOT` / `EXT_TTS_ROOT` | `<App根>\app` |
| ASR / MT / TTS 模型 | — | `<App根>\models/...`（见 §4.1） |
| 说话人 IR | `EXT_SPK_SEG_IR` / `EXT_SPK_WES_IR` | `<App根>\models/spk/...` |
| App 搜索根 | `EXT_APP_SEARCH_ROOT` | 用户主目录 |

★ **发行包建议显式设 `EXT_APP_ROOT=<包根>`** ⇒ 不依赖「用户目录下恰好有 vX.Y」这个假设。

### 4.3 设备摆放（**不变**）

| 组件 | 设备 |
|---|---|
| ASR（R2T2 INT8） | `GPU.0` |
| MT（Hy-MT2 INT8） | `GPU.0` |
| TTS（Qwen3-TTS） | `NPU` |
| 说话人分段（pyannote） | `NPU` |
| 说话人嵌入（wespeaker） | `GPU.0`（实测 NPU / GPU.1 **均编译失败** ⇒ 只有 GPU.0 可用 ⇒ 与 ASR/MT 共用**公平 FIFO 锁**） |

---

## 5. 端口 / 配置文件 / 日志位置

| 项 | 值 | 说明 |
|---|---|---|
| 桥接 WS 端口 | **8765** | `127.0.0.1:8765`（插件也连这个） |
| 配对端口 | **8766** | = 桥接端口 + 1 |
| Token 文件 | `bridge_token.txt` | ★ **相对当前工作目录** ⇒ 发行版请固定 cwd（建议 `<包根>`） |
| 日志 | `%LOCALAPPDATA%\LiveDubEXT\bridge.log` | UTF-8 |
| TTS 设备报告 | `%LOCALAPPDATA%\LiveDubEXT\tts_exec_devices.json` | 与日志同目录 |
| 桥接接口 ID | `kekgmfkijphpfndbbpakjaokamkeooib` | ★ **由 manifest 的 `key` 现场算**（`ext/extension_id.py`）⇒ 改 `key` 会变 |

★ `/pair` 的 Origin 校验**已收紧**到本插件 ID：本插件 **200** / 别的扩展 **403** / 普通网页 **403** / 无 Origin **403**。

---

## 6. EXT-028（配音听不清）——已修，不阻塞打包

**根因**：服务端下行 TTS 音频**不传 `sample_rate`** ⇒ 插件按 16 kHz 重建 24 kHz 波形
⇒ **1.5× 语速 + 升调** ⇒ 听起来像「听不清 / 变调」。

**修法**：新增 `resolvePcmSampleRate(msg)` —— 优先用服务端下发的 `sample_rate`；
下发缺失时按**实际字节数反推**（不猜）。

**证据**：
- 自测 `tests/test_ext028_dub_audio_chain.py`：**42 PASS / 0 FAIL**
- node harness `tests/ext028_player_harness.js`：**rc=0**
- 真实三引擎 A/B 录音分析：`.tmp/ext028_029_e2e/*/summary.json`

---

## 7. ★★「不依赖开发目录」的实测证据（EXT-031②）

**做法**（不是看代码，是**真跑**）：造一个**模拟发行包根**（目录名故意不叫 `live_dub_ext`），
把 `ext/` 整个拷进去，并：
- `EXT_APP_ROOT` 指向**模拟包**；
- `EXT_APP_SEARCH_ROOT` 指向**空目录**（⇒ 不许回退到开发机的 `Confucius4_LiveCaption_v*`）；
- 环境里**清掉**所有 `EXT_*_ROOT` / `EXT_SPK_*_IR` 覆盖项。

**结果**（脚本 `tests/smoke/ext031_fake_pkg_launch.py`，**6 PASS / 0 FAIL**）：

| 断言 | 实测 |
|---|---|
| `resolve_app_root()` 指向**模拟包** | ✅ `…\ext031_pkg_xxx\Confucius4_LiveCaption_v2.0` |
| 引擎根 / 模型目录 / 说话人 IR **全部落在模拟包内** | ✅ 越界项：**无** |
| 解析结果**不含**任何开发机目录名 | ✅ 命中：**无** |
| `package_root()` = 模拟包根 | ✅ |
| `EXT_RELEASE=1` ⇒ 白名单只留 `tabCapture` | ✅ |

**静态复核**：`ext/` 里**字符串字面量**（AST 级，**不含注释**）不含
`live_dub_ext` / `hy_bench` / `confucius4-openvino` / `qwen3tts_eval` / `Worktrees` / `confucius4-tts`。

**证据落盘**：`.tmp/ext031/fake_pkg_probe.json`

---

## 8. 打包前**必须知道**的事（诚实清单）

| # | 事项 | 影响 | 处理 |
|---|---|---|---|
| 1 | ⛔ **音色克隆不可用** | 发行版只能发**预设音色**（`voice_source` 全 `'preset'`，`clone_wired=false`） | 不宣称克隆音色；引擎层 `tts()` 的 `voice` 参数未接进 `tts_engine.stream()`（**需 TTS 模块改**） |
| 2 | 🟡 **tabCapture 生产路径未实测** | 自动化下拿不到 tabCapture（需**真实用户手势**点扩展图标） | 代码侧已修（`getMediaStreamId` + `chromeMediaSource:'tab'`）；发布前请用户手点一次 |
| 3 | 🟡 **「英译中」未真正测到** | 自动化抓流是整机声音（`getDisplayMedia`）⇒ ASR 混进中文 | 发行版只用 `tabCapture` ⇒ 这条**在发行版自然消失**；但需用户实测确认 |
| 4 | ⛔ **端到端仍不实时** | 稳态 RTF **2.0507**（ASR 0.6563 / MT 0.1507 / **TTS 1.0022**）⇒ 延迟大 | TTS 提速是上线的唯一前置（**由主会话转达 TTS 模块**） |
| 5 | ⛔ **同步误差仍超标** | `sync_err_ms.p50=67289.3` / `n_over_target=22` | 既有阻塞项，**未动引擎** |
| 6 | ⛔ **Edge 真实手势 1 分钟验收未做** | 发布前建议用户做一次 | 双击启动器 → 打开英文视频 → 点扩展「开始」→ player「开始捕获」→ 连播 1 分钟 |

---

## 9. ★ 打包时必改（**只有这 3 处**）

### 第 1 条：包根放 `release.json`

```json
{ "release": true }
```
★ 放在 **`<包根>\release.json`**（`ext/config.py` 的 `_release_mode()` 会读它）。
★ 或者设环境变量 `EXT_RELEASE=1`（**显式覆盖优先**）。

### 第 2 条：改 `extension/manifest.json` 的 `liveDub` 段

```json
"liveDub": {
  "release": true,
  "captureModes": ["tabCapture"]
}
```
★ `manifest.json` 的 `liveDub` 段是**唯一事实源**（`sw.js` / `offscreen.js` 都从它读白名单）。
★ ★ **`key` 字段**保持原样 —— 改了会让扩展 ID 变、插件 ID 对不上 `/pair` 的 Origin 白名单。

### 第 3 条：`USER_GUIDE.md` 里的开发机路径

★ `USER_GUIDE.md`（16 808 B）里有开发机路径字样 ⇒ **要么**删掉该文件（**推荐**，
发行版不需要开发指南），**要么**由 App 线程替换成包内相对路径的说法。

### 附：EXT-031③ 发行版**自动失效**的东西（**不用手工关**）

| 项 | 发行版行为 |
|---|---|
| 整机 `getDisplayMedia` 回退 | ✅ **禁用**（白名单只剩 `tabCapture`） |
| `--audio-dump-out` 逐段音频落盘 | ✅ **忽略**（传了也只打一行警告） |
| `--margin-out` 诊断落盘 | ✅ **忽略** |
| Playwright 驱动 | ✅ **不在发行包内**（只在 `tools/`，不进包） |

---

## 10. 首次启动步骤（用户视角）

1. **装扩展**：Chrome → `chrome://extensions` → 开发者模式 → 加载已解压的扩展程序 → 选 `<包根>\extension`
2. **起桥接**：双击包内的启动脚本（或跑 §2.1 的命令）⇒ 等日志出现「桥接已就绪 / 端口 8765」
3. **打开网页**：打开**英文**网页视频（要抓标签页音频 ⇒ 视频必须在**这个标签页**里播）
4. **点扩展图标 → 「开始」**：这一步会激活 `activeTab` 权限（★ **必须用户手点**，自动化拿不到）
5. **player 页点「开始捕获」** ⇒ 状态条应显示 `capture_mode = tabCapture`
6. **看诊断**：player 页的诊断区应显示「下发到 player」段数 = TTS 段数、无「不顶替」、无 10048
7. **听**：延迟 = ASR + MT + TTS 的总和（见 §8 第 4 条，**目前偏大**）

---

## 11. 自测入口（供 App 线程 / CI 核对，**不进发行包**）

| 套件 | 实测 |
|---|---|
| `tests/test_ext031_release_handoff.py` | 本清单 + 发行版模式 + 模拟包启动（**13 项**） |
| `tests/smoke/ext031_fake_pkg_launch.py` | 模拟发行包启动（**6 PASS / 0 FAIL**） |
| `tests/test_ext028_dub_audio_chain.py` | EXT-028 配音链路（**42 PASS / 0 FAIL**） |
| `tests/test_ext029_spk_bypass.py` | EXT-029 说话人旁路（**70 PASS / 0 FAIL**） |
| `tests/test_ext_selfcheck.py` / `test_echo_roundtrip.py` / `test_next_instruction.py` | 三套明文（**106 / 11 / 19**，全 rc=0） |

---

*生成时间：2026-11-01 16:30（实测）；数据来源：`ext/` 与 `extension/` 的实际文件、`App 包 v1.13` 的实际 `pip list`、`.tmp/ext031/fake_pkg_probe.json`。*
