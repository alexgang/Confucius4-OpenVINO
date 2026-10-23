# STATUS_APP
last_ack: APP-003
更新时间: 2026-10-23 11:24
当前任务: APP-003 ①②③④ 全部落地（§6 内部内容隔离 / §8 默认 MT 改 INT8-CW / CORRECTIONS 只由 reviewer 写 / 时间戳更正）；§8.7 CLI 回放等锁排队中
阻塞 / 待用户决定: ① 是否重打包并重建 FTP 硬链接（现在**必须**重打才能交付 INT8 默认 + results/ + C-106~109 + 瘦身）；② **TTS IR 交付形态**（INT8_SYM ≈1.4 GB vs 原版 2.54 GB）；③ babelvox 依赖随包附还是 pip 装；④ 参考音频接口（ASR 缓冲导出）；⑤ **是否剔除 INT4-CW**（可再省 0.97 GB，但低配机失去可选项）

## 最近更新
- 11:24 **APP-003 全部落地**：① results/ 内部会议内容已隔离（11 文件移至 `pkg_internal_quarantine/`，dry-run 0 残留）；② 默认翻译改 **INT8-CW**（IR 12/12 SHA256 核对一致，客户包 `DEFAULT_MODEL` 实测指向 INT8）；③ CORRECTIONS 第 23 行原自写「APP-002」改为「[目标机工作记录·非纠偏]」并把正文迁至 §7；④ **更正 §4 的时间戳**（见 §9）
- 11:20 §8：默认 MT 改 INT8-CW 的代码/IR/文档改动全表 + 包体积变化（8.28 → 9.97 GB，+1.69 GB）
- 11:10 §5 实测：客户包 Python 3.12 **能直接跑** Qwen3-TTS；最小依赖集 **297 MB**（可裁 numpy/sklearn）+ IR **2542 MB**；现有 7 个 app 模块在 numpy 2.5.4 下全部 import OK
- 09:34 补齐 APP-001 要求的 4 项现状汇总（§4）：TTS 链路 6 处改动、service 层 3 个 bug、Qwen3-TTS 新引擎接口、v1.3 包与 git 状态
- 09:34 核实 §29.8 的落盘证据：`_tts_replay_cli.wav` **不存在**，8 句全部 `dropped:true` ⇒ 该轮 CLI 回放**没有真正念出声音**
- 09:45 C-133 落地：编译缓存从包内 `app/ov_cache`（4181 MB）移到 `%LOCALAPPDATA%\Confucius4LiveCaption\`；源目录 12.37 GB → 8.28 GB。详见 §7
- 09:30 确认现网 v1.3.zip 是 **C-105 旧包**（zip 内 live_caption_app.py = 92654 B ≡ `.bak_c105`），`results/` 0 条 ⇒ 本轮改动对客户零效果，需重打才生效
- 09:20 确认仓库 `live_caption/` ≠ 客户包 `app/`（两份独立副本，仓库多一套 TTS 面板）⇒ 只能用 sync 脚本定点移植，禁止整目录覆盖
- 09:12 APP-001 启动单：App 模块启用独立 STATUS/CORRECTIONS

---

## §1 现状汇总（2026-10-23）

### 1.1 v1.3 客户包
| 项 | 状态 |
|---|---|
| 源目录 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3` — **9087 文件 / 8.28 GB**（C-133 清理后） |
| 源目录内容 | `app/`(11 个 .py + MANIFEST) / `models/`(encoder×3 + decoder×4 + mt + tokenizer) / `python/`(自带 3.12) / `results/`(35 文件正确率基准) / 4 个 .bat + 2 个 README + THIRD_PARTY |
| 现网 zip | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3.zip` — 9187406116 B / 9326 条 / **8.55 GB** ⚠️ **是 C-105 旧包** |
| FTP | `C:\Users\Trekker-PTL\FTP_Share\Confucius4_LiveCaption_v1.3.zip`（与上面是**硬链接**，link count=2）；2121 端口**当前无监听** |
| 版本 | v1.3，翻译模型只附带 **INT4**（`models/mt/mt2-int4sym-cw-q`，约 993 MB）；INT8 后端可用但不随包 |
| 备份 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3_pre_c133_backup\`（C-133 移植前的 3 个 .py） |

### 1.2 仓库 ↔ 客户包 的**双副本**关系（重要）
仓库 `confucius4-openvino/live_caption/` 是**研发态**，客户包 `app/` 是**交付态**，**两份独立维护**：

| 文件 | 仓库 | 客户包 app/ | 说明 |
|---|---|---|---|
| `live_caption_app.py` | 114596 | 102166 | 仓库多 TTS 面板 + C-106~109 |
| `streaming_asr.py` | 25485 | 24888 | |
| `audio_source.py` | 20116 | 20321 | |
| 其余 7 个 .py | 一致 | 一致 | |
| `tts_service.py` / `tts_worker.py` | **有** | **无** | 仓库独有 |

⇒ **同步必须用定点替换脚本**，仓库已有 `sync_c108_to_pkg.py` / `sync_c109_to_pkg.py` / **`sync_c133_to_pkg.py`**（本轮新增），模式统一为「精确字符串替换 + `assert count == 1`」。

### 1.3 git 同步状态
- 分支：仅 `main`（远端 `git@github.com:alexgang/Confucius4-OpenVINO.git`），历史已连通 ⇒ 可快进推送，**不要 force push**
- HEAD：`63020bf C-109：MIN_SEG_SEC 12s → 6s（用户决策），不做 Manual 模式`
- **未提交**（本轮之前就存在）：`M live_caption/live_caption_app.py`、`M live_caption/tts_service.py`、`M live_caption/tts_worker.py`、`M status/CORRECTIONS.md`、`?? fix_manifest_v13d.py`、`?? live_caption/diag_punct_*.py`(6 个)、`?? live_caption/diag_seg_qwen3*_result.json`(4 个)、`?? reviewer/find_int8enc.ps1`
- ⚠️ **有并行会话在同一项目工作**，推送后可能冒出新改动 ⇒ 先看清再决定入库还是问用户
- 本轮新增未跟踪：`pkg_exclude.py`、`live_caption/sync_c133_to_pkg.py`、`status/app/STATUS_APP.md`

### 1.4 TTS 链路现状
- 仓库已有 `live_caption/tts_service.py` / `tts_worker.py`（git status 显示**已被修改**，未提交），`live_caption_app.py` 内有 TTS GUI 控件区（1029–1061 行）与 `_on_tts_toggled` / `_on_tts_voice_changed` / `_pump_tts` / `_tts_meter` 回调
- **引擎已经从 Confucius4-TTS 换成 Qwen3-TTS**（见 `qwen3tts_eval/`），worker 侧需适配新引擎接口（流式分块播放、首包延迟、音色加载）
- ⚠️ **TTS 实测性能远达不到实时**：Confucius4-TTS 中文 101 token 需 105.1 s（RTF ≈ 52，目标 ≤0.5）；Qwen3-TTS 0.6B 真流式首包 0.66 s、RTF 中位 1.03 ⇒ 「流式 TTS」模式必须做**性能降级与状态提示**
- 音色克隆：Qwen3-TTS **内置** speaker encoder（9 MB），省掉 CAMPPlus + w2v-BERT 两套 OV 编码器
- ⚠️ **客户包里不能带**会议录音、克隆音色素材、同事音色

### 1.5 C-133 客户包瘦身已完成（详见 §7）
代码与源目录都已就位，**但未重打包** ⇒ 对客户零效果。详见本文件 **§7**。

**验证过的关键结论**：
- 编译缓存已从包内移到 `%LOCALAPPDATA%\Confucius4LiveCaption\`；起真实引擎（`gpu_int8`，13.7 s 加载成功）后 `app/ov_cache` **未被重建**
- 客户包 `--check` 全绿：6 个 ASR 后端全 `[ OK ]`，5 个翻译后端 3 个 `[ OK ]` + 2 个 `[ — ]`（本包不附带该量化）
- `pack_v13.py --dry-run` PASS：9086 文件 / 8892594610 B

**下次打包时的兑现**：zip 8.55 GB → ≈6.82 GB（−20%）、`results/` 首次进包（兑现 MANIFEST notes 的承诺）、C-106~109 首次交付。

---

## §2 工具与脚本约定

| 脚本 | 作用 | 备注 |
|---|---|---|
| `pkg_exclude.py` | 排除规则**单一数据源** | `pack_v13.py` / 两个 manifest 脚本共用；stdlib only |
| `pack_v13.py` | 打包 + 校验 | 支持 `--dry-run` / `--pkg` / `--zip` / `--prefix` / `--level`；MANIFEST files/bytes 已改**硬校验** |
| `live_caption/sync_c1XX_to_pkg.py` | 仓库 → 客户包定点移植 | 精确字符串替换 + `assert count == 1`，幂等 |
| `patch_zip_readme.py` | 增量替换包内任意文件 | 比重新打包快；重写 9 GB zip 约 15 分钟 |

**验证脚本铁律**：不得写死版本号/包路径，按 `Confucius4_LiveCaption_vX.Y` 版本号元组取最大自动发现。

## §3 待办
- [ ] **重打 v1.4 zip + 重建 FTP 硬链接**（需用户确认；兑现 APP-002 的全部收益）
- [ ] **TTS 集成实际编码**（详见 TTS 模块；App 侧待做：`Player` 设备 index + 原生采样率 + 重采样、worker 单线程 FIFO、timing/RTF 上报、`tts_doc.py`、GUI 模式切换 + 离线面板 + 参考音频上传、失败重试）
- [ ] 提交 git（本轮改动 + 之前遗留的未提交项，需先确认并行会话状态）
- [ ] 清理仓库孤儿缓存：`live_caption/ov_cache`(2.2 G) / `mt_cache`(2.4 G) / `npu_cache`(644 M)
- [ ] 排查 `%LOCALAPPDATA%\Confucius4LiveCaption\mt_cache` 涨到 13 GB 的原因

---

## §4 APP-001 现状汇总补齐（2026-10-23 09:34）

> APP-001 要求在 STATUS 开头做 4 项现状汇总。§1 已含 ①v1.3 客户包 ②git 同步状态；
> 本节补齐缺的两项（**TTS 链路 6 处改动**、**service 层 bug**），
> 并按 APP-001 第 19 行补上 **Qwen3-TTS 新引擎接口细节**。
> 所有结论标注了**磁盘核实结果**（证据规则：没落盘的不写"已交付"）。

### 4.1 `live_caption_app.py` 已有的 TTS 链路改动（6 处）

来源：`confucius4-tts/status/STATUS_tts.md` §29.6 / §29.7（2026-10-22）。
**当前仓库实测**：`live_caption_app.py` = **2319 行 / 114596 B**，mtime Oct 23 09:28
（仓库 `git status` = `M`，**未提交**）。

| # | 位置（实测行号） | 改动 | 证据 |
|---|---|---|---|
| 1 | `live_caption_app.py:2280-2292` | 加 `--tts` / `--tts-device` / `--tts-precision` / `--tts-voice` / `--tts-out` / `--tts-out-device` **6 个 CLI 参数** | 实测行号 |
| 2 | `:1152-1184` | GUI 加 **TTS 行**：勾选「语音输出」+ 音色下拉（预设 A / 预设 B / 克隆说话人）+ **输出设备下拉** + 耳机提示 + 状态标签 | 实测行号 |
| 3 | `:1545-1572` `_pump_tts()` | **补齐 GUI 侧提交链路**（原来只加控件没接链路 ⇒ 译文从来没送到 TTS）。挂在 `_poll()` 首行（`:1696`）；只提交 `kind in ('final','fix')`；**outbox 一定要 pop** | 实测行号 |
| 4 | `:1430-1441` `stop()` | 停的时候 `mt.flush(seg=len(self.blocks)-1)` **补翻挂起的半句**，否则最后半句的译文（含 TTS）会丢 | 实测行号 |
| 5 | `:1637-1659` `quit()` | 退出前 `_pump_tts()` → `tts.drain(timeout=30)` → `tts.close()` ⇒ 不半路掐断正在念的句子 | 实测行号 |
| 6 | `:1928-1993` `run_cli()` | CLI 收尾统一改用 `tts.drain(timeout=120)`（原先手写 120 s 循环，两套逻辑会漂移） | 实测行号 |

另有 3 个回调（GUI 侧，实测行号）：
`_on_tts_toggled` `:1498`（起/停 worker，TTS 加载失败**不影响**字幕翻译）、
`_on_tts_voice_changed` `:1533`（切音色需重启 worker，音色条件在加载时绑定）、
`_tts_meter` `:1574`（底栏统计：首包 / 积压 / 最大积压 / 丢句 / 已播）。

⚠️ **C-111 后的 kind 语义**（`_pump_tts` docstring 实测记录）：
`'half'`（段尾半句初翻）**不朗读**；`'fix'`（补全后的修正译文）**朗读**。

### 4.2 service 层修掉的 bug（3 个）

来源：§29.4 / §29.8。**当前仓库实测已含全部修复**（`tts_service.py` 16803 B mtime Oct 22 12:36、
`tts_worker.py` 31821 B mtime Oct 22 12:09，均为 `M` 未提交）。

| # | bug | 现象 | 修法 | 实测位置 |
|---|---|---|---|---|
| ① | `n_dropped` **双重计数** | 「提交 9」却报「丢弃 16」 | worker 的 `dropped` 事件**不再计数**（只记日志），因为所有丢弃都由主进程发起 | `tts_service.py:327-333` |
| ② | worker **加载期间**把积压句全丢了 | 加载 36.9 s（CPU），期间 8/9 句被误伤丢弃 | `_update_backlog()` 里 `state != 'ready'` 时**只记录积压，不丢句** | `tts_service.py:372-376` |
| ③ | `drain()` 不知道 worker 还没 ready | 收尾立刻判定「没排空」⇒ 白等到超时 | 拆两阶段：**阶段 1** 等 ready（`min(60, timeout/2)`），**阶段 2** 等排空 | `tts_service.py:255-272` |

worker 侧另有 3 个致命 bug（§29.4，已修）：
- `_HERE` **从未定义**却被用 2 处 ⇒ `NameError` ⇒ 音色加载必崩 ⇒ `ready=False`
  （修：模块顶部加 `_HERE = os.path.dirname(os.path.abspath(__file__))`）—— 实测 `tts_worker.py:52` ✅
- `OVRuntime.load()` 的 IR 文件名写死 `ir/s2a_estimator.xml` 等，但实际产物在 `ir_dyn/` 且带精度后缀
  ⇒ **3 个组件从来没加载过**（克隆音色链路直接不可用）；`ir/bigvgan_dynamic.xml` 在 GPU 上算错（SNR ≈ −8 dB）
  （修：改候选列表 + 多目录兜底）—— 实测 `tts_worker.py:258-305` ✅
- `_extract_cond_ov` / `_update_clone` 拿错对象（编码器方法在 `OVRuntime` 上，不在 `OVSynth` 上）
  ⇒ `AttributeError`（修：新增 `self.ov_runtime`）—— 实测 `tts_worker.py:628/678` ✅
- 附带：`_synth_ov()` 的 seed/步数写死（`seed=1234, n_timesteps=25, cfg_rate=0.7`）⇒ 改用 `self.seed/self.steps/self.cfg_rate`
  —— 实测 `tts_worker.py:527-530` ✅

### 4.3 🔴 §29.8 的 CLI 回放**没有真正念出声音**（本节新发现，与 §29.8 表述有出入）

§29.8 写「链路全部打通 … 合成 → 落盘 wav + jsonl」。**磁盘核实结果（2026-10-23 09:34）**：

| 产物 | 状态 |
|---|---|
| `confucius4-tts/results/_tts_replay_cli.wav` | 🔴 **不存在** |
| `confucius4-tts/results/_tts_replay_cli.wav.tts.jsonl` | 存在，1503 B，mtime Oct 22 12:35，**8 行全部 `dropped: true`**、`t_first_packet: null`、`dur_s: null` |
| `confucius4-tts/results/_tts_smoke.wav` | 存在，6185716 B，mtime Oct 22 12:19 ✅ |
| `confucius4-tts/results/_tts_smoke.tts.jsonl` | 存在，391 B，mtime Oct 22 12:19，2 行**都是** `dropped: false`、`t_first_packet` 179.07 / 115.85、`dur_s` 4.191 / 3.413 ✅ |

⇒ **撤回「CLI 回放全链路打通」**：那一轮 8 句**全部被丢弃、一句都没念**，
且混音 wav 未生成。真正跑通的是 **smoke 那轮**（CPU，2 句，首包 179.07 / 115.85 s）。
⇒ 修复顺序：先让 CLI 回放不丢句（bug ② 的 ready 判定），再重跑。

### 4.4 Qwen3-TTS 新引擎接口（APP-001 第 19 行要求写清楚）

引擎 = `djwarf/babelvox-openvino-int8` + PyPI `babelvox` 1.7.1，
venv = `C:\Users\Trekker-PTL\qwen3tts_eval\.venv-qwen3tts`（**无 PyTorch**，满足 C-101 铁律）。

**调用侧要换成它，接口与现有 worker 完全不兼容 —— 逐项差异：**

| 维度 | 现有 worker（Confucius4-TTS） | Qwen3-TTS（babelvox） |
|---|---|---|
| 导入 | `from tts_ov.runtime import OVRuntime` / `from tts_ov.synth_ov import OVSynth`（依赖 `LIVECAP_TTS_DIR` 环境变量指向 `confucius4-tts/`） | `from babelvox.pipeline import BabelVox`（**pip 包**，不依赖外部目录） |
| 推理 API | `OVSynth.synth(text, lang, cond, seed=, n_timesteps=, cfg_rate=)` → dict | `BabelVox.generate_stream(text, language=, ref_audio=, ref_text=, speaker_embed=, speaker=, chunk_frames=, split_on_silence=, cancel_event=)` → **yield `(wav_chunk, 24000)`** |
| 输出采样率 | **22050 Hz**（`tts_worker.py:46` `SR = 22050`） | **24000 Hz**（`pipeline.py:1004`「sample_rate is 24000」） |
| 音色 | `voices/*.npz`（preset_A / preset_B / clone_C，`_load_conds()` 加载） | **speaker encoder 内置**（9 MB）：`extract_speaker_embedding(audio_path)` → `(1,1024)`；或 `SpeakerLibrary` 命名音色 |
| 克隆参考 | worker 内置 `_update_clone(pcm)`（吃 base64 PCM） | `generate(ref_audio=<路径>)`，可配 `ref_text` 提升克隆质量 |
| 流式 | `native_stream.synth_stream`（first_chunk 25 token / chunk 50 / overlap 10） | `generate_stream` 内建，`chunk_frames=12`（≈1 s），`split_on_silence=True` 时在词间静音处 yield（无爆音），`crossfade_samples=1200`（50 ms @24k） |
| 取消 | `cancel` 命令 + `self._cancelled` 集合 | 传 `cancel_event`（`threading.Event`） |
| 推理设备 | `--device GPU.0 / CPU / NPU` + `--precision f32/f16` | `BabelVox(device="NPU", precision="int8"/"fp16", talker_buckets=, max_decoder_frames=)` |

**流式分块播放的关键约束（worker 侧要改的点）：**
1. `generate_stream()` **持有 `self._inference_lock`** ⇒ worker 侧只能有**一个**生成协程在跑 ⇒
   **worker 的 `run()` 必须改成单线程 FIFO**（现实现是 `run()` 每收到 `synth` 就 `threading.Thread(...).start()`，
   **只保证不并发、不保证顺序**）。
2. `chunk_frames=12` ≈ 1 s 音频 ⇒ 24 kHz 下每 chunk 28800 样本；
   `crossfade_samples=1200` 需要**相邻 chunk 重叠淡化** ⇒ 写进 `RingBuffer` 前要先做 crossfade，
   否则每 1 s 一个接缝爆音。
3. `Player` 的 `sr` 硬编码 22050 ⇒ 换成 24000，且 `sounddevice` 的设备原生采样率
   （44.1k / 48k）**不一定等于 24000** ⇒ 需要**重采样**（现 `Player.__init__` 直接 `samplerate=sr`）。
4. `cancel_event` 只能在 `generate_stream` 生成器内部检查 ⇒ worker 收到 `cancel` 命令时
   要 `cancel_event.set()`，**不能**靠现有的 `self._cancelled` 集合。

**首包延迟 / 性能基线（TTS 模块实测，TTS-001 已确认）：**
- 真流式首包 **0.66 s**（NPU INT8），**与句长无关**
- RTF 中位 **1.04** ⇒ **未达 ≤0.5 目标**
- 🔴🔴 **`max_decoder_frames` 一参两用**（① 静态形状定解码耗时 ② `effective_max` 定截断）
  ⇒ **降它会砍断长句**。这个坑踩过两次（NPU + iGPU）
  ⇒ **通用自检**：正确配置的输出**不应出现大量完全相同的时长**；看到「多句时长完全相同」= 被截断。
- 长句正解 = **按句切分 + 流式拼接**（RTF 1.372 → 1.063，分段反而更快）
- iGPU(GPU.0) 真实 RTF ≈ **1.51** ⇒ 达不到 RTF<1，**NPU 才是正解**
- 🔴 **BabelVox 采样无 seed** ⇒ wav 级对比**必须先锁 seed**（`np.random.seed(SEED_BASE + idx)`，`SEED_BASE=20261023`）
- ⚠️ **不要用 INT4**（同设备口径 talker cos 0.9395 / 相对误差 50.2%）；**必须用 INT8_SYM**
  （与原 IR 逐位相等，max|Δ| 精确 0，端到端 30/30 SNR 99 dB）

**App 侧要向 TTS 模块确认的 3 件事（跨模块需求，请 reviewer 转达）：**
1. **音色加载**：Qwen3-TTS 的 `speaker encoder` 需要**参考音频 wav 路径**；
   App 侧「默认用 ASR 输入音频的音色」⇒ 需要一个「从 ASR 采集缓冲导出参考 wav」的能力
   （现 `tts_worker.py` 的 `_update_clone(pcm)` 是吃 base64 PCM 的 Confucius4 路径，**接口不通用**）。
2. **模型部署形态**：客户包里 TTS 走 `pip install babelvox` 还是随包附带 IR？
   现客户包 `app/` 里**没有** `babelvox`、也没有 Qwen3-TTS 的 IR（实测 `app/` 只有 11 个 .py + MANIFEST）。
   ⇒ **打包体积影响未评估**（Qwen3-TTS INT8_SYM 约 447 MB + cp_decode 79 MB）。
3. **GPU.0 / NPU 摆放**：TTS 模块结论是「NPU 才是正解」，但 ASR/MT 也在抢 NPU
   ⇒ 需明确 App 的**设备摆放表**（ASR GPU.0 / MT NPU? / TTS NPU?），否则三路推理抢同一条 NPU。

### 4.5 与 §1 的差异（不撤回 §1，只补证据）

- §1.4 说「Confucius4-TTS 中文 101 token 需 105.1 s（RTF ≈ 52）」——
  这是 **Confucius4 引擎**的旧数据；**App 侧现在要对接的是 Qwen3-TTS**（首包 0.66 s / RTF 1.04）⇒
  「流式模式必须做性能降级与状态提示」这个结论**依然成立**，但**依据的数值要换成 Qwen3-TTS 的**。
- §1.3 说 git HEAD = `63020bf`（C-109）—— **实测仍然成立**（2026-10-23 09:34 `git log --oneline -3` 一致）。⚠️ **现已过时**：HEAD 已前进到 `b6de69a ASR-002`（并行会话提交），见 §9.4。
- §1.3 列的未跟踪文件清单**已过时**（实测多出 `status/app/`、`status/asr/`、
  `live_caption/diag_c111_*.py`、`live_caption/translator.py` 等）⇒ 以 `git status --short` 现场为准。

---

## §5 Qwen3-TTS 客户包部署可行性（2026-10-23 11:10）

> 回答 §4.4 待确认项 ②：**babelvox 走 pip 还是随包附 IR？跑起来要多大的体积？**
> **结论：能跑通 ✅；最小依赖集 297 MB + IR 2542 MB ⇒ 客户包 +2.84 GB。**
> 验证脚本 `confucius4-openvino/verify_tts_deploy.py`，
> 结果文件 `confucius4-openvino/results/tts_deploy_verify.json`（3281 B，mtime 11:09）。

### 5.1 实测方法
**不修改客户包**：所有依赖装到临时 `--target` 目录，用 `PYTHONPATH` 叠加验证。
客户包 Python = `Confucius4_LiveCaption_v1.3/python/python.exe`（**3.12.10**，自带 pip 25.0.1、有网）。

### 5.2 依赖缺口（babelvox 1.7.1 声明 vs 客户包现状）

| 依赖 | babelvox 声明 | 客户包现状 | 实测结论 |
|---|---|---|---|
| `transformers` | `>=5.0` | **4.57.6** | ✅ **不满足声明但实测可用** —— `AutoTokenizer.from_pretrained('Qwen/Qwen3-TTS-12Hz-0.6B-Base')` 成功，vocab **151676**，中文分词正常 |
| `huggingface_hub` | `>=1.0` | **0.36.2** | ✅ 实测可用（`HF_HUB_OFFLINE=1` 下从本地缓存加载） |
| `numpy` | `>=2.0` | 2.4.6 | ✅ 满足 |
| `openvino` | `>=2025.4` | 2026.4.1 | ✅ 满足 |
| `scipy` / `librosa` / `num2words` / `defusedxml` | 必需 | **全缺** | ❌ 需新增 |

⚠️ transformers 加载时有一条 regex 警告（Mistral-Small-3.1 相关），
建议 `fix_mistral_regex=True`。**但客户包 transformers 4.57.6 不支持该参数**
⇒ 需在 App 侧判断是否影响中文分词质量（**待 TTS 模块用 golden 30 句验证**）。

### 5.3 最小依赖集：**297 MB**（比 pip 全量解算省 87 MB）

**实测裁掉的**：
- 🔴 **`numpy`** —— pip 默认会装 numpy 2.5.4 **把客户包的 2.4.6 顶掉**（PYTHONPATH 优先级）
  ⇒ **必须显式不装 numpy**，用客户包原生 2.4.6
- ✅ **`scikit-learn`（41 MB）** —— babelvox 不 import，只有 `librosa.decompose` 的 docstring 提到
  ⇒ 实测不装也跑通

**不可裁**：`llvmlite`(117 MB) + `numba`(30 MB) —— `librosa.filters` **硬 import** `from numba import jit`；
`llvmlite` 0.11.0 / 1.0.0 都不行 ⇒ **147 MB 是 librosa 的固定成本**。

| 方案 | 体积 | numpy | 实测 |
|---|---|---|---|
| pip 全量解算 | **384 MB** | 被顶到 **2.5.4** ⚠️ | 跑通 |
| **最小依赖集** | **297 MB** | **2.4.6 保持不变** ✅ | **跑通** |

最小集包清单：`babelvox==1.7.1 librosa==1.0.0 scipy==1.18.1 soundfile soxr lazy_loader
joblib pooch audioread decorator msgpack num2words defusedxml cloudpickle
numba==0.68.0 llvmlite==0.50.0 platformdirs requests certifi idna urllib3
charset_normalizer packaging`

### 5.4 IR 体积：**2542 MB**

| 目录 | 体积 | 内容 |
|---|---|---|
| `int8/` | **1672.8 MB** | talker 444 MB ×3（talker/talker_prefill/talker_decode）+ cp_decode 79 MB + cp_prefill 79 MB + tokenizer_decoder 114 MB + tokenizer_encoder 48 MB + speaker_encoder 8.9 MB + 6 个 .xml |
| `weights/` | **869.5 MB** | numpy embedding 表（cp_embedding_0..14 等） |
| **合计** | **2542.3 MB** | |

🔴 **注意**：TTS 模块 §2.8 的结论是「**INT8_SYM 自量化** 体积 1754 → **447 MB**（−74%），
且与原 IR **逐位相等**」⇒ **客户包应只附 INT8_SYM 自量化产物，不是这 1673 MB 的原版**。
⇒ 需 TTS 模块交付自量化产物的**目录结构**（哪些文件、放在哪）。
⚠️ `weights/` 869 MB 是 numpy 权重表，**不能量化**（本身就是 numpy 数组）⇒ 打包下限 ≈ 870 MB + 量化 IR。

### 5.5 端到端实测（CPU，仅验功能，**不报性能**）

```
客户包 Python 3.12.10 + 最小依赖集 + 本地 IR：
  import babelvox            → OK
  BabelVox(device=CPU, precision=int8) 加载 → load_ok=True
  generate_stream(...)        → chunks=3, sr=24000, sizes=[23040,23040,3840], 总 2.08 s
  generate('这是一句测试。') → wav shape=(40320,), float32, 峰值 0.3818
```
✅ **结论：客户包 Python 3.12 + 现有 site-packages 可以直接跑 Qwen3-TTS，不需升级 Python、不需装 transformers 5。**

### 5.6 现有链路兼容性（numpy 被顶高时的实测）

叠 `PYTHONPATH`（pip 全量解算把 numpy 顶到 2.5.4）后，客户包 `app/` 的 7 个模块**全部 import 正常**：
`audio_source` / `seg_stream` / `segment_encoder_backend` / `npu_delivery_backend` /
`npu_embeds_backend` / `translator` / `backends` 全 OK。
⇒ **numpy 2.4.6 → 2.5.4 本身不炸**，但**仍建议用最小集**（保持 2.4.6 零变更 + 省 87 MB）。

### 5.7 给 TTS 模块 / 用户的 3 个决策点

1. **IR 交付形态**：客户包附 **INT8_SYM 自量化产物**（约 447+79 MB + weights 870 MB ≈ **1.4 GB**）
   还是原版 int8（**2.54 GB**）？⇒ 直接决定客户包最终体积。
2. **babelvox 依赖怎么装**：随包附 `python/Lib/site-packages/`（+297 MB，**客户机零安装**）
   还是首次运行 `pip install`（**需要联网**，且要处理 numpy 顶高问题）？
   ⇒ 客户包已有 `pip` + `ensurepip`（APP-002 决策 4 保留），技术上两条路都可行。
3. **tokenizer regex 警告**：`fix_mistral_regex=True` 在 transformers 4.57.6 下不可用
   ⇒ 需确认中文分词质量是否受影响（**建议 TTS 模块用 golden 30 句回转写验证**）。

### 5.8 顺带记录（不在本次范围）
- `babelvox` 依赖 `transformers>=5.0` / `huggingface_hub>=1.0`，但客户包是 4.57.6 / 0.36.2
  ⇒ **pip install babelvox（带依赖）会尝试升级 transformers/hub**，
  **可能破坏 ASR/MT 现有链路**（`translator.py` 依赖 transformers 的 `AutoTokenizer`）
  ⇒ **必须用 `--no-deps` + 手工白名单安装**（§5.3 的包清单）。
- `qwen3tts_eval/.venv-qwen3tts` 是 **Python 3.13**，客户包是 **3.12**
  ⇒ babelvox 声明 `Requires-Python: >=3.10` ⇒ 3.12 满足，已实测。

---

## §7 C-133 客户包瘦身（工作记录，2026-10-23 09:20~09:45）

> 按 APP-003③ 从 `CORRECTIONS_APP.md` 迁入此处（原标题「APP-002」编号撞车，APP 编号只由 reviewer 发放）。

### 用户决策（2026-10-23）
1. **仍不重新打包** —— 只改代码 + 清源目录，改动在下次打包时生效
2. 缓存路径改动：**改仓库 + 写 sync 脚本移植到客户包**（仓库是 source of truth）
3. **保留 `python/**/__pycache__`**，只剔 `app/__pycache__`（省客户机首次启动 1~5 s 重编译）
4. 边角料**全部保留**：`pip` / `ensurepip` / `models/tokenizer/` / `idlelib` 等 / `tests/`
5. 编译缓存改到 `%LOCALAPPDATA%\Confucius4LiveCaption\`，接受客户机首次启动多 5~19 s 编译，**不加 GUI 文案**
6. 源目录**现在物理全清**

### 🔴 必须知道：现网 zip 比源目录落后一整个版本（**本轮改动对客户零效果**）
实测 `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3.zip`（9187406116 B / 9326 条）：
- zip 内 `app/live_caption_app.py` = **92654 B**，md5 `41f50cf6b591cbf95028d87fba283c78`
  ≡ 源目录的 `app/live_caption_app.py.bak_c105`（**逐字节相同**）
  ⇒ **现网 zip 是 C-105 时代的包**，缺 C-106 / C-107 / C-108 / C-109 的分句改进
- zip 内 `results/` = **0 条**，而 `MANIFEST.json` 的 notes 已在**两次**版本说明里宣称
  「完整矩阵与逐句输出随包附在 `results\`」⇒ **这是对客户不成立的承诺**
- zip 内 `app/ov_cache/` 274 条（压缩后约 1.73 GB）—— 客户拿到的仍是含 4.1 GB 缓存的 8.55 GB 包
⇒ **下次打包**（需用户另行确认）才会兑现：C-133 瘦身 + `results/` 进包 + C-106~109 交付。
预计 zip **8.55 GB → ≈ 6.82 GB**（−20%），条目 9326 → 约 9051。

### 🔴 必须知道：仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
实测（字节数）：
| 文件 | 仓库 | 客户包 app/ | zip 内 |
|---|---|---|---|
| `live_caption_app.py` | 114596 | 102166 | 92654 |
| `streaming_asr.py` | 25485 | 24888 | — |
| `audio_source.py` | 20116 | 20321 | — |
| `translator.py` / `backends.py` / `segment_encoder_backend.py` / `seg_stream.py` / `npu_delivery_backend.py` / `npu_embeds_backend.py` / `selftest_audio_sources.py` | 一致 | 一致 | — |

仓库版**独有** `tts_service.py` / `tts_worker.py` + TTS 面板 ⇒
**严禁整目录覆盖同步**，否则会把未交付的 TTS 功能带进 v1.3。
⇒ 本轮用 `live_caption/sync_c133_to_pkg.py`（与 `sync_c109_to_pkg.py` 同构：
精确字符串替换 + `assert count == 1`）做定点移植，只动 3 处。

### 本轮改动清单（全部已落盘并验证）
| # | 文件 | 改动 |
|---|---|---|
| 1 | `confucius4-openvino/pkg_exclude.py`（**新建**） | 排除规则**单一数据源**：目录名 `{ov_cache, npu_cache, mt_cache}`（任意层级）+ 路径前缀 `{app/reports/, reports/}` + 文件名含 `.bak`；`python/**/__pycache__` 保留。提供 `is_excluded()` / `iter_package_files()` / `iter_excluded()` / `package_stats()` |
| 2 | `live_caption/live_caption_app.py::_cache()` | 改为 `%LOCALAPPDATA%\Confucius4LiveCaption\<name>` + `try/except` + `os.access(W_OK)` 探测 + **回落 `APP_DIR/<name>`**。删掉误导性注释（原「开发机上会沿用已有的缓存目录」——实测 `~/.openvino/models/ov_cache` **根本不存在**，那个分支是死代码，实际一直在往包内写） |
| 3 | `live_caption/npu_delivery_backend.py:59` | `DEFAULT_NPU_CACHE` 从 `'./reports/npu_cache'`（WORK 相对）改为用户目录绝对路径 |
| 4 | `live_caption/npu_embeds_backend.py:96` | `cache_dir` 缺省从 `"./reports/npu_cache"` 改为 `None` + 函数内兜底到用户目录（原值在客户包里会解析到 `<包根>/app/reports/npu_cache`，污染包目录） |
| 5 | `live_caption/sync_c133_to_pkg.py`（**新建**） | 定点移植上述 3 处到客户包 `app/`（幂等：已是新版则跳过） |
| 6 | `pack_v13.py` | `import pkg_exclude`；打包改用 `iter_package_files`；**打包前自动刷新 MANIFEST**；`MUST_NOT` 拆成 `MUST_NOT_EXACT`（原 5 条 + 4 条 `.bak_c10x`）与 `MUST_NOT_PREFIX`（**从 `pkg_exclude` 导入**，带尾 `/`）；MANIFEST files/bytes 改**硬校验**；新增 argparse `--pkg/--zip/--prefix/--level/--dry-run` |
| 7 | `fix_manifest_v13d.py` / `update_manifest_v13.py` | 统计口径统一到 `pkg_exclude.package_stats()`（此前两脚本口径互不相同：符号链接处理不一致） |
| 8 | 客户包源目录 | **物理删除**：`app/ov_cache/`（288 文件 / 4181.4 MB）、`app/*.bak_c105/c106/c108/c109`（4）、`app/__pycache__/`（1） |
| 9 | `status/app/STATUS_APP.md`（**新建**） | APP-001 要求的现状汇总 |

### 实测验证结果
- 源目录：**9380 文件 / 12.37 GB → 9087 文件 / 8.28 GB**（剔 293 文件 / 4.08 GB）
- `pack_v13.py --dry-run`：**PASS**，将打包 9086 文件 / 8892594610 B（MANIFEST 自身不计入统计）
- `MANIFEST.json` 已刷新：`files 9361 → 9086`、`bytes 11005807200 → 8892594610`
- 客户包 `--check`：依赖 / OpenVINO 设备 / **6 个 ASR 后端全 [ OK ]** / 5 个翻译后端（3 个 [ OK ] + 2 个 [ — ]「本包不附带该量化版本」）/ 音频设备**全 [ OK ]**
- **关键验证 —— 缓存不再回写包内**：用客户包 `app/live_caption_app.py` 起真实引擎（`gpu_int8`，13.7 s 加载成功），
  跑完 `app/ov_cache` **未被重建**、`app/npu_cache` / `app/reports` / 根级 `ov_cache` 均不存在；
  编译产物落在 `%LOCALAPPDATA%\Confucius4LiveCaption\ov_cache`（2.3 GB）
- zip 与 FTP **未动**：`Confucius4_LiveCaption_v1.3.zip` 与 `FTP_Share\` 下同名文件仍为 9187406116 B（硬链接，link count=2）；2121 端口无监听

### 顺带记录（不在本次范围）
- `%LOCALAPPDATA%\Confucius4LiveCaption\mt_cache` 已达 **13 GB**（`translator.py:614-617` 的注释只说 2.4 GB）。位置正确（不在包内），但值得后续排查为什么涨这么快。
- 仓库 `live_caption/ov_cache`(2.2 G) / `mt_cache`(2.4 G) / `npu_cache`(644 M) 在 `_cache()` 改后成为孤儿（已 gitignore，不进包），可后续手工清理。
- `models/tokenizer/`（9 文件 / 15.2 MB）是**孤儿目录**（不在 `_MODEL_ALIASES`、无代码引用、内容与 `decoder-gpu-int8/` 内同名文件逐字节相同）—— 零风险可剔，本轮按用户决策保留。

### 下一步（需用户确认）
- 重打 v1.4 zip 并重建 FTP 硬链接（兑现 `results/` 进包 + C-106~109 交付 + 体积 −20%）
- TTS 集成实际编码（`Player` 设备 index + 原生采样率 + 重采样、worker FIFO、timing/RTF 上报、`tts_doc.py`、GUI 模式切换与离线面板、参考音频上传、失败重试）

---

## §6 APP-003① 客户包 results/ 内部会议内容隔离（2026-10-23 11:14）

> APP-003① 原文要求：
> (a) `pkg_exclude.py` 加排除规则 + `pack_v13.py` MUST_NOT 硬校验；
> (b) 把 results/ 下所有 json 的 source/ref 字段扫一遍（含 `hf_fp32_zh2en.json`），列出每个文件的语料来源；
> (c) MANIFEST notes 关于 results 的说法改成和实际进包内容一致；
> (d) 客户包源目录里的 spoken 文件**移出到包外**（不要删）；
> **验收：贴出 `pack_v13.py --dry-run` 的输出，证明 0 个 `*_spoken*` 文件，并给出 results/ 每个文件的来源表。**

### 6.1 语料来源判定方法

`mt2_acc_outputs/*.json` 的**顶层 `dir` 字段**直接标识语料方向：

| `dir` 值 | 语料 | 判定 |
|---|---|---|
| `en2zh` | wmt24pp en-zh_CN **公开新闻语料**（Vicente Siso 画展报道） | ✅ 可进包 |
| `zh2en` | 同上，**反向构造**（FLORES 仓库受限取不到） | ✅ 可进包 |
| `spoken` | **内部会议录音**的转写/翻译（20 句） | 🔴 禁止进包 |

`rows[]` 里**没有**独立的 `source` / `ref` 字段 —— 语料归属只在顶层 `dir`。
（reviewer 要求的「source/ref 字段扫描」已按此口径完成：`rows[]` 内
`src` = 源句、`out`/`hyp` = 译文，**均为句子内容而非语料来源标识**。）

### 6.2 results/ 全部文件的来源表（实测，逐文件）

**进包（客户包 `results/`，共 24 个文件）**

| 文件 | 顶层 `dir` | rows | 语料来源 | 判定 |
|---|---|---|---|---|
| `mt2_accuracy.json` | — (顶层键 en2zh/zh2en) | — | wmt24pp 200 句 × 6 配置的汇总指标 | ✅ |
| `mt2_accuracy.md` | — | — | 同上（人读版表格） | ✅ |
| `mt2_acc_outputs/bf16_cpu_en2zh.json` | `en2zh` | 200 | wmt24pp | ✅ |
| `mt2_acc_outputs/bf16_cpu_zh2en.json` | `zh2en` | 200 | wmt24pp 反向 | ✅ |
| `mt2_acc_outputs/hf_fp32_en2zh.json` | `en2zh` | 10 | wmt24pp 前 10 句 | ✅ |
| `mt2_acc_outputs/hf_fp32_zh2en.json` | `zh2en` | 10 | wmt24pp 前 10 句 | ✅ |
| `mt2_acc_outputs/int4_gpu_en2zh.json` | `en2zh` | 200 | wmt24pp | ✅ |
| `mt2_acc_outputs/int4_gpu_zh2en.json` | `zh2en` | 200 | wmt24pp 反向 | ✅ |
| `mt2_acc_outputs/int4_npu_en2zh.json` | `en2zh` | 200 | wmt24pp | ✅ |
| `mt2_acc_outputs/int4_npu_zh2en.json` | `zh2en` | 200 | wmt24pp 反向 | ✅ |
| `mt2_acc_outputs/int8_gpu_en2zh.json` | `en2zh` | 200 | wmt24pp | ✅ |
| `mt2_acc_outputs/int8_gpu_zh2en.json` | `zh2en` | 200 | wmt24pp 反向 | ✅ |
| `mt2_acc_outputs/int8_npu_en2zh.json` | `en2zh` | 200 | wmt24pp | ✅ |
| `mt2_acc_outputs/int8_npu_zh2en.json` | `zh2en` | 200 | wmt24pp 反向 | ✅ |
| `mt2_acc_outputs/*_en2zh.txt`（4 个） | — | 各 200 行 | wmt24pp 逐句译文 | ✅ |
| `mt2_acc_outputs/*_zh2en.txt`（4 个） | — | 各 200 行 | wmt24pp 逐句译文 | ✅ |

（`hf_fp32_*` 只有 `.json` 无 `.txt`；`*_hf_fp32_*` 共 2 个文件已计入。）

**不进包（已移出到 `C:/Users/Trekker-PTL/pkg_internal_quarantine/results/`，共 11 个文件）**

| 文件 | 顶层 `dir` | rows | 首句实测（`rows[0].src`） | 判定 |
|---|---|---|---|---|
| `mt2_acc_outputs/bf16_cpu_spoken.json` | `spoken` | 20 | `[REDACTED]` | 🔴 内部会议 |
| `mt2_acc_outputs/bf16_cpu_spoken.txt` | — | 20 行 | — | 🔴 |
| `mt2_acc_outputs/int4_gpu_spoken.json` | `spoken` | 20 | 同上 | 🔴 |
| `mt2_acc_outputs/int4_gpu_spoken.txt` | — | 20 行 | — | 🔴 |
| `mt2_acc_outputs/int4_npu_spoken.json` | `spoken` | 20 | 同上 | 🔴 |
| `mt2_acc_outputs/int4_npu_spoken.txt` | — | 20 行 | — | 🔴 |
| `mt2_acc_outputs/int8_gpu_spoken.json` | `spoken` | 20 | 同上 | 🔴 |
| `mt2_acc_outputs/int8_gpu_spoken.txt` | — | 20 行 | — | 🔴 |
| `mt2_acc_outputs/int8_npu_spoken.json` | `spoken` | 20 | 同上 | 🔴 |
| `mt2_acc_outputs/int8_npu_spoken.txt` | — | 20 行 | — | 🔴 |
| `mt2_memory.json` | — | 5 条 | `out` = **「[REDACTED-内部会议引文]」** | 🔴 **reviewer 未点名，本模块额外发现** |

⚠️ **`mt2_memory.json` 是本模块在执行 (b) 时额外发现的内部内容**（reviewer 只点了 `*_spoken.*`）。
其 `out` 字段原文是「[REDACTED-内部会议引文]」⇒ 含客户交付信息，
按同一条纪律排除，已加入 `pkg_exclude.INTERNAL_EXACT` 精确点名。

### 6.3 代码改动

| # | 文件 | 改动 |
|---|---|---|
| 1 | `pkg_exclude.py` | 新增 `SPOKEN_FILE_RE = re.compile(r'_spoken', re.I)`、`RESULTS_DIR = 'results/'`、`INTERNAL_EXACT = ('results/mt2_memory.json',)`；`is_excluded()` 加第 2.5 步；`iter_package_files()` 加对应过滤；`__all__` 与 docstring 同步 |
| 2 | `pack_v13.py` | `MUST_NOT_EXACT += list(pkg_exclude.INTERNAL_EXACT)`；新增 `MUST_NOT_NAME_RE = pkg_exclude.SPOKEN_FILE_RE`；zip `--check` 段新增 `spoken_hit` / `internal_hit` 断言并纳入 FAIL 条件；`--dry-run` 新增「源目录残留」提示段（用 `os.walk` 看真实状态，因 `iter_package_files` 已过滤） |
| 3 | `live_caption/app` 的 `MANIFEST.json` | notes 三处精确替换（备份在包外 `pkg_backup_app003/MANIFEST.json.bak_app003`） |

**MANIFEST notes 改写后的原文（3 处）**：
- `（en→zh 正向、zh→en 反向构造，因 FLORES 仓库受限；另含 20 句会议口语子集）`
  → `（en→zh 正向、zh→en 反向构造，因 FLORES 仓库受限）`
- `完整矩阵与逐句输出随包附在 results\（...）`
  → `质量矩阵（BLEU / chrF++ / paired bootstrap 95% CI）随包附在 results\（...，均为**公开新闻语料** wmt24pp；**内部会议录音的转写与译文不含在包内**）`
- `（见 results\mt2_memory.json）` → `（内存实测数据未随包附）`

### 6.4 `pack_v13.py --dry-run` 原始输出（**验收证据**）

```
======================================================================
[dry-run] Confucius4_LiveCaption_v1.3
======================================================================
源目录: C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.3

将打包: 9075 文件 / 8892571918 字节 (8.28 GB)

将排除的内容：
  __pycache__                   2 文件        0.2 MB
  .bak_*                        2 文件        0.1 MB

关键文件检查：
  [OK] app/translator.py
  [OK] app/live_caption_app.py
  [OK] app/MANIFEST.json
  [OK] README_zh.md
  [OK] README_en.md
  [OK] THIRD_PARTY.md
  [OK] Start_LiveCaption.bat
  [OK] Diagnose.bat
  [OK] models/mt/mt2-int4sym-cw-q/openvino_model.xml
  [OK] models/mt/mt2-int4sym-cw-q/openvino_model.bin
  [OK] models/mt/mt2-int4sym-cw-q/config.json
  [OK] models/mt/mt2-int4sym-cw-q/chat_template.jinja

内部会议内容检查（results/ 下 *_spoken.* 与点名文件）：
  源目录残留: 0 个内部内容文件

结论：PASS（dry-run，未写 zip）
```

✅ **0 个 `*_spoken*` 文件**、**0 个点名文件**残留。

### 6.5 隔离区（包外，未删除）

路径：`C:/Users/Trekker-PTL/pkg_internal_quarantine/results/`
- `mt2_memory.json` — 1448 B
- `mt2_acc_outputs/` — 10 个 `*_spoken.{json,txt}`（1.78~4.76 KB / 个）

⚠️ **备份不放包内**：C-133 教训 —— `_backup_*` 目录不被 `.bak` 排除规则覆盖，会污染包。
本轮 `MANIFEST.json.bak_app003` 也已从 `app/` 移到 `C:/Users/Trekker-PTL/pkg_backup_app003/`。

### 6.6 MANIFEST files/bytes 已刷新

- 刷新前：`files 9086 / bytes 8892594610`
- 刷新后：`files 9075 / bytes 8892571918`（MANIFEST 自身 **14807 B** 不计入统计）
- 校验：`bytes + MANIFEST 自身 = 8892571918 + 14807 = 8892586725`

---

## §8 APP-003② 默认翻译量化改 INT8-CW（2026-10-23 11:20）

> APP-002（reviewer 于 CORRECTIONS_APP.md 第 89 行发布）①–④ 执行情况。
> **注意**：§6 已把 CORRECTIONS 里那段自写的「APP-002」标题改为
> `## [目标机工作记录·非纠偏]`，本节的 **APP-003②** 才是 reviewer 真正那条纠偏。

### 8.1 结论

✅ **默认翻译量化已由 INT4 改为 INT8 按通道**（`mt2-int8sym-cw-q`），INT4 保留为可选。
代码、IR、文档三处均已落地并实测。

### 8.2 代码改动（仓库 `live_caption/translator.py` + 客户包 `app/translator.py`）

| # | 位置（实测行号） | 改动 |
|---|---|---|
| 1 | `:58-68` `DEFAULT_MODEL` | 默认目录 `mt2-int4sym-cw-q` → **`mt2-int8sym-cw-q`**；**保留 INT4 作回退**（INT8 目录不存在时仍能跑） |
| 2 | `:54` `_HY_ROOT` | 注释同步（客户包路径示例） |
| 3 | `:99-116` 注释块 | **撤回**旧结论「INT8 质量与 INT4 持平（同义改写级差异），对客户机没有实际收益」；改引 H-001/H-007 的语料级 bootstrap 数值 |
| 4 | `:123-133` `_MT_CANDIDATES` | 重新排序（`gpu_int8cw` 在前，标「默认」）；4 项 `bundled` 全改 `True`（INT8 与 INT4 **都随包**） |
| 5 | `:137-139` `MT_ENGINES['auto']` | label → `自动 · INT8-CW 模型（默认）` |
| 6 | `:156-158` `MT_ALL_CANDIDATES['auto']` | label 同上 |

**GUI 默认选中项**：`live_caption_app.py:1125-1128` 用
`self.mt_eng_keys = [k for k in MT_ENGINES]` + `var_mt_eng` 初值取
`args.mt_engine`（= `MT_DEFAULT` = `'auto'`）⇒ **下拉默认落在「自动 · INT8-CW 模型（默认）」**，
且 `auto` 的 `model=None` ⇒ `TranslationService.model_dir` 保持 `DEFAULT_MODEL`
= INT8 目录。**无需额外改 GUI 代码**（实测已验证，见 8.5）。

**移植方式**：`live_caption/sync_c134_to_pkg.py`（**新建**，与 `sync_c133_to_pkg.py` 同构：
精确字符串替换 + `assert count == 1`，幂等）⇒ 6 处全部移植成功。

### 8.3 IR 落包（客户包 `models/mt/mt2-int8sym-cw-q/`）

来源：`C:/Users/Trekker-PTL/hy_bench/ov/mt2-int8sym-cw-q`（MT 模块研发态产物）
**12 个文件全量 SHA256 与 MT 模块交接单（STATUS_hy §37.3）逐一核对 ⇒ 12/12 一致**：

| 文件 | 字节 | SHA256 核对 |
|---|---|---|
| chat_template.jinja | 654 | ✅ `b7491ec0…acee` |
| config.json | 1,402 | ✅ `04db8100…96b5` |
| generation_config.json | 221 | ✅ `0e28667f…d6f` |
| special_tokens_map.json | 488 | ✅ `bb9f5999…85eb` |
| tokenizer_config.json | 165,815 | ✅ `53bd8581…b07c` |
| tokenizer.json | 9,527,287 | ✅ `b475bbef…530a` |
| openvino_tokenizer.xml | 27,568 | ✅ `cb02ae46…aba8` |
| openvino_tokenizer.bin | 4,620,103 | ✅ `9f35d0a3…8ad1` |
| openvino_detokenizer.xml | 9,266 | ✅ `c4a750f4…9ee9` |
| openvino_detokenizer.bin | 1,817,980 | ✅ `aed86402…d23` |
| openvino_model.xml | 2,958,965 | ✅ `0963454f…3740` |
| **openvino_model.bin** | **1,792,991,738** | ✅ `a9956484…c36` |

📌 6 个共享小文件（tokenizer/config 系）**从客户包现有 INT4 目录复制** ——
实测客户包 INT4 目录的这 6 个文件 SHA256 与交接单的 INT8 表**完全相同**
⇒ 同源，复制等价。

### 8.4 包体积变化（**APP-002 ② 要求说明**）

| 目录 | 文件数 | 字节 | 折 GB |
|---|---|---|---|
| `models/mt/mt2-int4sym-cw-q` | 12 | 1,040,491,337 | 0.969 |
| `models/mt/mt2-int8sym-cw-q` | 12 | 1,812,121,487 | 1.688 |
| **净增** | **+12** | **+771,631,118** | **+0.719** |

**客户包整体**（`pack_v13.py --dry-run` 实测）：
- 改前：**9075 文件 / 8,892,571,918 B（8.28 GB）**
- 改后：**9087 文件 / 10,704,695,313 B（9.97 GB）**
⇒ **净增 1,812,123,395 B（+1.69 GB）**（含 MANIFEST notes 增长）。

⚠️ **本轮没有剔除 INT4**（MT 模块交接单给的两个选项：「默认 INT8 + 保留 INT4」
或「剔 INT4 净减 0.25 GB」）。选择**保留 INT4**，理由：
1. INT4 仍是**唯一**能同时在「显存紧张的集显机」上跑 INT8 的替代方案
   （INT8 显存 +0.75 GB，README 已注明显存不足时选 INT4）；
2. 用户已明确「INT4 保留为可选」（APP-002 ①）；
3. 剔 INT4 只省 0.25 GB，但会让「低配机」失去可选项 ⇒ 收益/代价比不划算。
⇒ **若用户决定剔 INT4，体积可再降约 0.97 GB**（待确认）。

### 8.5 客户包运行时实测（**客户包自己的 Python 3.12.10**）

```
$ cd Confucius4_LiveCaption_v1.3/app && ../python/python.exe -c "import translator as t; ..."
DEFAULT_MODEL = C:/Users/Trekker-PTL/Confucius4_LiveCaption_v1.3/models/mt/mt2-int8sym-cw-q
MT_DEFAULT    = auto
MT_ENGINES keys = ['auto', 'gpu_int8cw', 'gpu_int4cw', 'npu_int8cw', 'npu_int4cw']
  auto        | 自动 · INT8-CW 模型（默认）     | bundled= None
  gpu_int8cw  | Intel GPU · INT8-CW（默认）     | bundled= True
  gpu_int4cw  | Intel GPU · INT4-CW            | bundled= True
  npu_int8cw  | Intel NPU · INT8-CW            | bundled= True
  npu_int4cw  | Intel NPU · INT4-CW            | bundled= True
```
✅ `DEFAULT_MODEL` 已指向 INT8-CW 目录；`py_compile` 通过；
仓库与客户包 `translator.py` **逐字节相同**（`diff -q` = IDENTICAL）。

### 8.6 文档同步（MANIFEST notes + 双语 README）

| 文件 | 改动 |
|---|---|
| `app/MANIFEST.json` | notes **前置 v1.4 修订说明**（3 条：默认 INT8-CW / 编译缓存外移 / results 只含公开语料）；更正 2 处过时表述（「只剩一个产物…INT8 不随包」「只附带 INT4 一个量化版本…没有实际收益」）⇒ 明确标注**旧结论已被语料级 bootstrap 推翻** |
| `README_zh.md` | 9 处：系统要求磁盘 9→10 GB、加载耗时、后端表格 5 行全部重写、准确度口径改语料级 bootstrap、模型目录表加 INT8 行、「只附带 INT4」段落改写、故障排查路径、局限条目 |
| `README_en.md` | 7 处，同上 |

⚠️ **v1.3 的旧表述必须保留「撤回」痕迹**（不能直接删）——
客户如果对照过旧版文档，需要能看出结论变了及为什么变。

### 8.7 CLI 回放（APP-002 ③）—— **⏳ 进行中**

脚本：`live_caption/replay_c134_mt.py`（**新建**）
- **等锁**：轮询 `C:/Users/Trekker-PTL/shared/MACHINE_LOCK`；锁内 PID 不在了
  或锁早于开机时间 ⇒ 回收；否则每 20 s 打印等待进度。
- **持锁**：创建锁（内容：模块名 / PID / 开始时间 / 主机名），跑完删除。
- **ABBA**：`off / on / on / off` 四轮，同一段音频（`test_audio/<redacted>.wav`，
  取前 60 s）、同一个 ASR 后端（`gpu_int8`）、语种锁 `Chinese`。
- **记录**：ASR RTF、段数、逐段文本、墙钟；落盘 `results/c134_replay/`。

⚠️ 启动时机器锁被 **TTS 模块**占用（`module: tts / pid: 36608 / started 11:04:02`，
实测该 PID 存活）⇒ 回放脚本正在**排队等待**，未抢锁、未跑推理。
⇒ **本节在回放完成后补写实测数字**（翻译延迟、ASR RTF、锁持有记录）。

⚠️ **端到端墙钟不能作性能判据**（机器漂移 60~130 s）⇒ 结论以 ABBA 差值为准。

---

## §9 APP-003④ 时间戳更正 + APP-003③ 编号修正（2026-10-23 11:24）

> reviewer 原文：
> **④ [NORMAL] STATUS 的时间写到了未来** —— 「STATUS 头部写"更新时间 10:20"，
> 最近更新里有 10:15 和 10:20 两条，§4.3/§4.5 也写了"10:15/10:20 核实"。
> 但这个文件的 mtime 是 09:34:33，reviewer 本机审查时是 09:43（两台机器的时钟一致）。
> 时间一律用 `Get-Date` 的实际值，不要推算。请在下一节写明"更正 §4 的时间戳"。」
>
> **③ [NORMAL] CORRECTIONS 只由 reviewer 写** —— 「第 23–88 行是你写的工作报告，
> 不是纠偏。请把这一节的标题改成 `## [目标机工作记录·非纠偏] C-133 客户包瘦身（已迁至 STATUS §N）`，
> 正文挪到 STATUS 新章节里。STATUS §1.5 里的"C-133（APP-002）"也改掉。」

### 9.1 时间戳更正（§4 的 10:15 / 10:20 是**推算值**）

**更正内容**：§4 标题与 §4.3 / §4.5 里写的「10:15」「10:20」**全部作废**。
这两个时间是当时凭印象写的，**不是 `Get-Date` 实测值** —— reviewer 实测本文件
mtime = 09:34:33、审查时刻 = 09:43，两机时钟一致 ⇒ 确认写到了未来。

| 位置 | 原写（**作废**） | 更正后 |
|---|---|---|
| §4 标题 | `## §4 APP-001 现状汇总补齐（2026-10-23 10:20）` | `## §4 APP-001 现状汇总补齐（2026-10-23 09:34）` |
| §4.3 | `磁盘核实结果（2026-10-23 10:15）` | `磁盘核实结果（2026-10-23 09:34）` |
| §4.5 | `实测仍然成立（2026-10-23 10:20 git log --oneline -3 一致）` | `实测仍然成立（2026-10-23 09:34 git log --oneline -3 一致）` |
| 头部「最近更新」 | `- 10:20 补齐 APP-001 要求的 4 项现状汇总（§4）…` | `- 09:34 补齐 APP-001 要求的 4 项现状汇总（§4）…` |
| 头部「最近更新」 | `- 10:15 核实 §29.8 的落盘证据…` | `- 09:34 核实 §29.8 的落盘证据…` |

⇒ **§4 实际落盘时刻 = 09:34**（与文件 mtime 一致）。后续所有章节时间
**一律用 `Get-Date` 实测值**，本轮实测值：
`2026-10-23 11:10:43`（§5）、`11:14:55`（§6）、`11:18:38`（§8 起稿）、`11:24`（头部）。

### 9.2 编号修正（APP-003③）

| 项 | 改前 | 改后 |
|---|---|---|
| `CORRECTIONS_APP.md` 第 23 行标题 | `## APP-002 [HIGH] 2026-10-23 09:40 — C-133 客户包瘦身…` | `## [目标机工作记录·非纠偏] C-133 客户包瘦身（已迁至 STATUS §7）` |
| 该节正文（第 24–88 行，4497 字符） | 在 CORRECTIONS 里 | **迁至 `STATUS_APP.md` §7**（内容逐字保留） |
| `STATUS_APP.md` §1.5 标题 | `### 1.5 C-133 客户包瘦身（APP-002）已完成` | `### 1.5 C-133 客户包瘦身已完成（详见 §7）` |
| `STATUS_APP.md` §1.5 正文 | `详见 CORRECTIONS_APP.md 的 APP-002` | `详见本文件 §7` |
| 头部 `last_ack` | `APP-002` | **`APP-003`** |

CORRECTIONS 里现只留一行占位（备份在包外 `pkg_backup_app003/CORRECTIONS_APP.md.bak_app003`）。
⇒ **以后只在 STATUS 汇报，APP 编号只由 reviewer 发。**

### 9.3 本轮（APP-003）改动清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `pkg_exclude.py` | 新增 `SPOKEN_FILE_RE` / `RESULTS_DIR` / `INTERNAL_EXACT`；`is_excluded()` 加第 2.5 步；`iter_package_files()` 加过滤；`__all__` + docstring 同步 |
| 2 | `pack_v13.py` | `MUST_NOT_EXACT += INTERNAL_EXACT`；新增 `MUST_NOT_NAME_RE`；zip `--check` 增 `spoken_hit` / `internal_hit` 断言并纳入 FAIL；`--dry-run` 增「源目录残留」提示段 |
| 3 | 客户包 `app/MANIFEST.json` | notes 3 处（results）+ 2 处（INT8 默认）替换 + 前置 v1.4 修订说明；`files` / `bytes` 刷新到 **9087 / 10,704,695,313** |
| 4 | 客户包 `app/translator.py` | C-134 定点移植 6 处（`sync_c134_to_pkg.py`） |
| 5 | 仓库 `live_caption/translator.py` | 同上（source of truth） |
| 6 | 客户包 `models/mt/mt2-int8sym-cw-q/` | 新增 12 文件（1.81 GB），SHA256 12/12 与 MT 交接单一致 |
| 7 | 客户包 `README_zh.md` / `README_en.md` | 9 处 / 7 处表述更新（默认 INT8、体积、准确度口径） |
| 8 | `live_caption/sync_c134_to_pkg.py` | **新建**（C-134 定点移植，幂等） |
| 9 | `live_caption/replay_c134_mt.py` | **新建**（等锁 + ABBA CLI 回放） |
| 10 | `status/app/STATUS_APP.md` | 追加 §6/§7/§8/§9；头部与 §1.5 更正 |
| 11 | `status/app/CORRECTIONS_APP.md` | 第 23 行标题改正 + 正文迁出 |
| 12 | 包外备份 | `C:/Users/Trekker-PTL/pkg_backup_app003/`（MANIFEST.json.bak_app003 / translator.py.bak_c134 / README_zh.md.bak_c134 / README_en.md.bak_c134 / CORRECTIONS_APP.md.bak_app003） |

### 9.4 ⚠️ 未提交 git（本轮）

`git status --short` 实测（HEAD = `b6de69a ASR-002`）：
- 已修改：`live_caption/{translator,npu_delivery_backend,npu_embeds_backend,live_caption_app,tts_service,tts_worker}.py`、`pack_v13.py`、`update_manifest_v13.py`、`status/CORRECTIONS.md`
- 未跟踪：`pkg_exclude.py`、`verify_tts_deploy.py`、`live_caption/sync_c133_to_pkg.py`、`live_caption/sync_c134_to_pkg.py`、`live_caption/replay_c134_mt.py`、`status/app/`、`results/`、`fix_manifest_v13d.py`、`live_caption/diag_punct_*.py`(11)、`live_caption/diag_seg_qwen3*.json`(4)、`reviewer/find_int8enc.ps1`

⚠️ **有并行会话在同一项目工作**（HEAD 已从 `63020bf C-109` 前进到 `b6de69a ASR-002`，
且 `live_caption/tts_service.py` / `tts_worker.py` / `live_caption_app.py` 的改动**不是本模块做的**）
⇒ **本模块只提交自己负责的文件**，不碰 TTS/ASR 模块的改动。

**本模块该提交的文件**：
`pkg_exclude.py`、`pack_v13.py`、`update_manifest_v13.py`、`fix_manifest_v13d.py`、
`live_caption/translator.py`、`live_caption/npu_delivery_backend.py`、
`live_caption/npu_embeds_backend.py`、`live_caption/sync_c133_to_pkg.py`、
`live_caption/sync_c134_to_pkg.py`、`live_caption/replay_c134_mt.py`、
`live_caption/live_caption_app.py`（C-133 缓存外移那 3 处 —— **需先确认是否与 TTS 模块改动混在同一文件**）、
`verify_tts_deploy.py`、`status/app/`、`results/`。
