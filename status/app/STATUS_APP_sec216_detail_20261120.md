# STATUS_APP §216 明细（APP-116）

> 🔴 本文件是 `status/app/STATUS_APP.md` **§216 的正文**（活文档逼近 40 000 B 限额 ⇒ 正文放 companion）。
> 活文档里只有 §216 标题行 ＋ 一段摘要 ＋ 指向本文件的指针行。

**时间**：2026-11-20 10:29 → 收尾时间见活文档头部「更新时间」
**执行条数**：APP-116（last_ack: APP-115 → **APP-116**）
**来源**：`status/app/CORRECTIONS_APP.md` 的 `## APP-116 [HIGH] 2026-11-20 10:20` ＋
邮件 `[C4][A][CORRECTION][APP] APP-116`（alexchen7694@agent.qq.com，11-20 10:00:40）——
**两条内容一致 ⇒ 按协议只执行一次**。
**代码提交**：`31e5c67`（已推 origin/main；本轮把 GitHub 推送从 22 端口换到
`ssh.github.com:443`，host key 已按 `api.github.com/meta` 公布的指纹逐条核对）。

---

## §1 🔴 TTS 输出设备选「耳机」无效（用户实测）

### 1.1 根因（**已实测定位，不是猜测**）

界面里「显示名 → 设备 id」的反查表 `self._out_label_back` 的**字典推导式把两个变量写反了**：

```python
# 旧（错）：.items() 给出的是 (key=oid, value=name)，却被解包成 name=oid / oid=name
self._out_label_back = {name: oid for name, oid in self._out_label.items()}
```

⇒ 建出来的是 `{id: 显示名}`，**和正向表 `_out_label` 一模一样**，
⇒ 按显示名反查设备 id **恒为 `None`**。

后果链（A 机实测，可逐跳复现）：

| 跳 | 位置 | 实际值 |
|---|---|---|
| hop0 | 用户在「语音输出 → 输出设备」选耳机 | GUI 显示「输出设备改为：头戴式耳机 (Plantronics C320-M)（2 声道）」 |
| hop1 | GUI `self._out_label_back.get(显示名)` | **`None`**（反查表方向反了） |
| hop2 | `TTSService(out_device=None)` → `cmd` | **不带** `--out-device` |
| hop3 | worker `args.out_device` | **`None`** |
| hop4 | `Player` ⇒ `resolve_out_device(None)` | `None` ⇒ 落回系统默认设备 |

原始日志（A 机）：`%LOCALAPPDATA%\Confucius4LiveCaption\session_20261120_091149.log`
- `09:12:12 [tts] 输出设备改为：头戴式耳机 (Plantronics C320-M)（2 声道）`
- `09:12:16 [TTS] [tts_worker] 播放流已启动：sr=22050 device=默认设备 ⇒ **实际输出: Speaker (Realtek(R) Audio)（hostapi=MME…）**`

⇒ **与设备类型 / 精度 / CUDA / NPU 全无关**；同一条日志里 TTS 就绪、MT 切换都正常。

**独立复现**（用客户包 v2.4 的 python 跑 `audio_source.list_output_devices()`）：
`head {2e4a781d-…}` → 名字 `头戴式耳机 (Plantronics C320-M)（2 声道）`；
用**旧写法**建反查表再 `.get(该名字)` ⇒ **`None`**；用**修复后写法** ⇒ 拿到 id。
⇒ 证明「这一行」就是根因（反证组，见 1.3 的 A2）。

### 1.2 改了什么（4 个文件）

| 文件 | 改动 |
|---|---|
| `live_caption/live_caption_app.py` | ① 反查表改成正确写法（与「音频来源」「识别语种」两张表一致）；② **hop1 日志**（显示名 ⇒ id，反查失败明说）；③ `_on_tts_out_changed` 改为**先试运行中切换**，失败才回落「重启 TTS」 |
| `live_caption/tts_service.py` | ④ **hop2 日志**（`--out-device=…` 实际传了什么）；⑤ 新增 `set_out_device()`；⑥ 新增 `out_device` 事件处理（回执里写「实际输出」与回落原因） |
| `live_caption/tts_worker.py` | ⑦ **hop3 日志**（worker 收到的 argv）；⑧ `Player._open_stream()` 抽出为唯一入口（初始化与切设备同一条逻辑）；⑨ **解析失败不再静默**（日志 + `out_fallback` + `out_requested` 遥测）；⑩ 新增 worker 指令 `set_out_device` ⇒ 只**重开播放流**（不重启 worker、不重载模型、**不丢在途句子**：同一个 `Player`、同一个音频队列，只换 `_stream`） |

### 1.3 验收（**A 机实测**，21/21 PASS）

证据：`results/app/app116_device_gui_evidence_100pct.json`、`…_150pct.json`
（脚本 `live_caption/diag_app116_device_gui.py`，用**客户包 v2.4 的 python**跑真实声卡）

| 检查 | 结果 |
|---|---|
| A2 修复后：名称→id 反查得到设备 id | PASS（`{0.0.0.00000000}.{2e4a781d-…}`） |
| A2 **反证组**：旧写法反查恒为 `None` | PASS |
| A2 **反证组**：修复前后结果**不同** | PASS |
| A3 `resolve_out_device(耳机 id)` 解析出设备 | PASS ⇒ 播放索引 **5**（端点 id → 「头戴式耳机 (Plantronics C320-M)」→ 索引 5） |
| A4 播放流打开成功 | PASS |
| A4 **实际输出落在所选设备** | PASS ⇒ `头戴式耳机 (Plantronics C320-M)（hostapi=MME, ch=8）` |
| A4 **没有回落到系统默认** | PASS（`out_fallback=''`、`out_is_default=False`） |
| A4 遥测带上「用户选的设备」 | PASS（`out_requested` = 耳机 id） |
| A5 运行中切到扬声器 ⇒ 实际输出跟着变 | PASS ⇒ `Speaker (Realtek(R) Audio)` |
| A5 运行中切回耳机 ⇒ 实际输出回到所选设备 | PASS |
| A5 切换后**没有**回落 | PASS |

⚠️ **「切到设备就出那个设备的声音」的听感确认**仍待用户在 A 机亲耳确认
（reviewer 原文：「听感由用户确认」）—— 本轮只做到「日志里的『实际输出』= 用户选的设备」。

### 1.4 仍待做的验收（reviewer 的 §1 验收三项）

reviewer 原文：「验收：A 机接耳机（Plantronics C320-M）实测 ①启动前选耳机 ②运行中从扬声器切到耳机 ③运行中从耳机切回扬声器，
三种情况日志「实际输出」都对；截图 + 日志片段写进 STATUS。听感由用户确认。」

- 本轮已完成的是 **Player/引擎层**的 ①（启动即落在耳机）＋ ②③（双向切换）。
- **worker 指令通路**（GUI ⇒ service ⇒ worker `set_out_device` ⇒ 回执）的端到端验证脚本
  已写好：`live_caption/diag_app116_worker_switch.py`（起**真实 worker 进程**、
  下发 `set_out_device`、校验 `out_device` 事件；含「不存在的设备 ⇒ 不许静默」一组）。
  该验证需要加载 TTS 模型 ⇒ **占 GPU** ⇒ 排在 v2.5 出包验收之后执行。

---

## §2 预设音色增加一个男声（预设 B）

### 2.1 来源（**无任何真人素材**，许可证允许分发）

| 项 | 值 |
|---|---|
| 模型 | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` |
| 许可证 | **Apache-2.0**（HF `cardData.license`）⇒ 允许分发 |
| 下载 | `https://hf-mirror.com/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`（直连 huggingface.co 实测 21 s 超时不通） |
| 生成方法 | `model.generate_custom_voice(text=…, language="Chinese", speaker="Uncle_Fu")` |
| speaker | `Uncle_Fu`（官方描述：Seasoned male voice, mellow timbre · 中文） |
| 生成文本 | 「你好，这是一段用于生成预设音色的参考音频。声音清晰平稳，没有背景噪音，语速适中，像平常说话一样朗读这段文字。」 |
| 备选（已生成未采用） | `Dylan`（Youthful Beijing male voice）—— 13.68 s / peak 0.4712 / rms −26.6 dBFS / 0 削波；因带**北京口音**、且更「年轻」，未作为默认男声 |
| ❌ **没有**用 | 录音 / 同事音色 / 克隆音色 / babelvox 样本 / 任何真人素材 |

### 2.2 定稿资产 `preset_B.wav`

`results/app/app116_preset_b_gen/preset_B_manifest.json`（开发树副本：
`models/qwen3tts/voices/preset_B.wav`）

| 项 | 值 |
|---|---|
| SHA256 | `ad8e3e80fbada9f409d953e2ad93eba6615de1c601df64318c7b2c242c8b5703` |
| 采样率 / 声道 | **24000 Hz / 单声道** |
| 时长 | **10.000 s**（在 8–12 s 内） |
| peak / rms | 0.7080（−3 dBFS）/ −21.7 dBFS |
| 削波样本 | 0 |
| 处理链 | 去首尾静音（帧 RMS < −45 dBFS）→ 起点 0.520 s → 裁 10.0 s → 峰值归一 −3 dBFS → 去直流 → 10 ms 淡入淡出 → PCM_16 |
| 自检 | 7/7 PASS（采样率/单声道/时长/不削波/非静音/直流/峰值） |

### 2.3 代码改动

| 文件 | 改动 |
|---|---|
| `live_caption/tts_engine.py` | `preset_voice_path(voice='A')` 支持 A/B；新增 `preset_voices_available()`（按文件是否存在判定） |
| `live_caption/tts_worker.py` | `_setup_babelvox_voice` 按 `key` 取对应预设（其它值回落 A）；`speaker=` **只传内置 speaker**（否则 CUDA 路线会把 `'B'` 当内置 speaker 名） |
| `live_caption/live_caption_app.py` | 音色下拉显示名改「**预设 A（女声）**」；**B 只在参考音频文件真的存在时列出**（APP-007 的教训：列一个选不了的项 = 静默错标）；`--tts-voice` 增加 `B` 档 |

自检（开发树，CPU）：`preset_voices_available() = ('A', 'B')`；两条路径都解析到 ✓。

### 2.4 🔴 **用户点头前不进包**

reviewer 明文：「挑 4 条放到 `results/app/app116_preset_b_listen/` 给用户抽听，**用户点头前不进包**。」

⇒ 本轮 **v2.5 客户包里不含 `models/qwen3tts/voices/preset_B.wav`**
⇒ 客户机上的音色下拉**不列出**「预设 B（男声）」（代码按文件存在性自动判断）
⇒ 用户抽听点头后，随**下一个版本**把该文件带进包。

⚠️ **本条尚未完成**：
- ⓿ 抽听样本（zh 2 条 + en 2 条）**待生成**（需 GPU 合成 + ASR 回转写 ⇒ 排在 v2.5 验收之后）；
- ⓿ zh/en 各 10 句的 **CER/WER 对比**（预设 A vs 预设 B）待跑
  （脚本 `live_caption/_app116_eval_preset.py` 已写好：dev 树 `tts_worker` 用
  `models/qwen3tts/{int8,tokenizer,weights}` 的 **junction** 指向客户包模型
  ⇒ 不复制 14 GB、**不改包本身**；回转写复用仓库现成的 `backends.OVBackend`）。

---

## §3 GUI 去掉 4 个选项

移除：**草稿译文** / **重试翻译** / **区分说话人** / **显示说话人**（都在「高级」面板）。

**行为与默认值一律不变**（只是不再在界面上出现）：

| 项 | 变量 | 默认值 | 依据 |
|---|---|---|---|
| 草稿译文 | `self.var_mt_draft`（仍在 ③ 翻译组建好） | **关闭** | APP-015；命令行 `--mt-draft` / `LIVECAP_DRAFT` 保留 |
| 重试翻译 | `self.btn_mt_retry` 置 `None` | — | `_retry_mt()` 函数保留；命令行/配置项保留 |
| 区分说话人 | `self.var_speaker` | = `self._speaker_enabled`（**False**，旁路默认关） | APP-054；变量名不改（`app227` D2 判据要求 AST 含 `var_speaker`） |
| 显示说话人 | `self.var_show_spk` | **True**（开） | APP-040④ |

**布局**：删掉 3/4/5/6 四行后，后续项**上移**（离线朗读→3、测试声音→4、戴耳机→5）
⇒ 行号**连续**（0–5，**无空洞**）；顺带消除旧代码里「区分说话人」提示文字与
「离线朗读」按钮**同占 row=7/column=1** 的重叠。

**验收（21/21 PASS × 2 档）**：
- 控件 `chk_mt_draft` / `cb_show_spk` / `cb_speaker` **不存在**；
- 遍历整棵控件树，**界面上不再出现**那 4 个选项的文字（`[]`）；
- 默认值自检：草稿关 / 显示说话人开 / 区分说话人 = 旁路默认值；
- 高级面板行号连续 `[0,1,2,3,4,5]`、**同格重叠 `{}`**；
- 截图（**tk scaling 必须在建控件前设**，否则两次截图逐字节相同 —— 本轮踩过）：
  - `results/app/app116_gui_100pct.png`（scaling 1.3330，47 941 B）
  - `results/app/app116_gui_150pct.png`（scaling 2.0014 ＝ ×1.5，73 676 B）
  - 两张 **SHA256 不同**；150 % 下无截断/无重叠/无空洞。

---

## §0 打包规则（用户 11-20，长期有效）

- 默认打包**只出 `Confucius4_LiveCaption`（完整版）**这一套配置。
- **SpecialMVP 不必打包**（sp5 的 zip 不用打），**MiniMVP 同理**（没说就不出）。
  ⇒ 本轮**只做完整版**；未碰任何 SpecialMVP / MiniMVP 目录与 zip。
- 客户包仍**不含**录音、同事音色、克隆音色、babelvox 样本
  ⇒ `assert_pkg_clean.scan()` 在 v2.4 基底上实测 **0 违规**（5 条规则）；
  ⇒ 本轮新增进包的只有 **`.py` 源文件**（无任何音频资产）⇒ 闸门仍为 0 违规。
- 验收要核**模型身份**（config 维度 + 权重 SHA 对源目录）。

## 附带修正（同一轮）

- 语速上限 **1.70×**、TTS 就绪前**不丢句**（APP-114 / APP-115）——这两项此前**只在开发树里**，
  v2.4 包里没有 ⇒ v2.5 第一次把它们带进客户包（`time_stretch.SPEED_MAX=1.70`、
  `_TTS_QUEUE_OVERFLOW_S=None` + `clear_on_worker_failure()`）。
- 验收脚本 `results/app/_app588_sp4_acceptance.py` 增加
  `--asr-device/--mt-device/--tts-device/--tts-voice/--tts-out-device`
  五个参数（**原默认值不变** ⇒ 不影响 APP-114/115 的既有口径）。
