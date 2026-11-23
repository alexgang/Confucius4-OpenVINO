# STATUS_APP §223 正文（2026-11-23）— APP-122 / APP-123 / APP-124 / APP-125 / APP-126 / APP-127

> 本文件是 `status/app/STATUS_APP.md` 的 §223 companion（正文全文）。
> 活文档只留标题行 + 指针行（APP-052④ 限额 ≤40 000 B / ≤300 行）。

## §223 执行 **APP-122 / APP-123 / APP-124 / APP-125 / APP-126 / APP-127**（last_ack=APP-121 → **APP-127**，2026-11-23 18:5x）

**本条已完成**（APP-122/124/125 = 分工调整，零代码；APP-126 §2–§6 = 全部完成；APP-127 = 无陈旧锁需删）
**本条需等 reviewer 复核**（APP-123 = 开发完成但**不进包**、整链与抽听待 reviewer 复核后再做；APP-126 = 等 reviewer 复核本条结果）

### §0 本轮纠偏来源与指纹（收尾复核）

| 通道 | 结果 |
|---|---|
| 局域网 `status/app/CORRECTIONS_APP.md` | **125 条 / max APP-127**（开工时 125 / max APP-127 ⇒ **收尾复核逐字一致**） |
| QQ 邮箱 `alexchen7694@agent.qq.com` | 最新一封 = **APP-127**（`msg_kIvssywoXkD700Oy3uU4i8uBBqDjwRwpqVY1J1PsU7vbQA`，08:55:39Z）⇒ **与局域网同一编号两边都到 ⇒ 按 T-MAIL-002/003 只执行一次** |
| QQ 垃圾箱 | **0 封** |
| agent-mail | 未绑定 |

- **开工指纹**：`SHA256 fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48` / **429 255 B** / mtime **2026-11-23 16:55:40** / **125 条**
- **收尾复核**：**同 SHA、同字节数、同 mtime、同条数** ⇒ **SHA 零改动**（只读、绝对未写、未 staged）
- 🟢 `last_ack` 由 **APP-121 → APP-127**（本轮执行完的最大编号）

### §1 APP-122 / APP-124 / APP-125 —— 分工变更，**App 线程零代码**

- 🔴 **APP-125 覆盖 APP-122 §1–§5 与 APP-124**（「保留背景音」的全部代码——`extension/` 与 `ext/*.py`、分离 worker、说话人改用人声——**都由 reviewer 写**；App 线程**不要开发**）。
- 🟢 **App 线程在 APP-125 生效前未动过 `live_dub_ext`**：开工时工作区的未提交改动**全部是 reviewer 自己的**（`ext/bg_separator.py` 等 9 改 + 3 新），App 线程本轮**未写过一个字节**到 `live_dub_ext`；按 APP-125 §1「保持工作区不动」的要求，**未提交、未 stash**。
- 🟢 **APP-122 的验收/实测部分保留但等交接**：reviewer 在 APP-126 §1 已把 v0.4.19 最终代码交到 A 机 ⇒ 由 App 线程负责的部分是「把新 EXT 与 Demucs 模型打进 v2.6 + 跑 APP-122 §验收」⇒ 🔴 **按 APP-126 §7「不要开始 v2.6 打包」，本轮未打包、未跑 APP-122 的 10 分钟整链**（等 reviewer 复核本条结果 + 定下默认分离设备后再交接）。
- 🟢 **零新增客户包目录 / 零 zip / 零客户包既有文件改动**。

### §2 APP-126 §2 —— 15 个 stage 文件落 `live_dub_ext` + md5 核对 ✅ **15/15 逐个一致**

- 来源：`shared\bgkeep\v0419_stage\`（reviewer 的 v0.4.19 最终代码 + `MD5SUMS.txt`）
- 🟢 **15/15 md5 逐个核对一致**（含 `.gitignore` / `ext/{bg_separator,bridge,speaker_bypass,spk_engine,version}.py` / `extension/{capture-worklet.js,manifest.json,player.js,popup.html,popup.js,sw.js}` / `tests/{ext0419_bg_harness.js,test_ext0419_bgkeep.py}` / `tools/bgkeep_e2e.py`）
- 🟢 `git diff --stat` **只出现这 15 个文件**（11 改 + 4 新；+1759 / −21）
- 🔴 **开工先备份**：`%TEMP%\live_dub_ext_pre126_bak_20261123_175750\`（14 个既有文件逐个备份；`tests/test_ext0419_bgkeep.py` 原本不存在）
- 🟢 `models/`（107 MB Demucs IR）**未入库**（`.gitignore` 已排除）；`bridge_token.txt` / `*.log` / 音色 / 录音**均未入库**（staged 内容扫过敏感模式，只命中代码里的**字面量** `token`/`wav` 变量名，无真实凭据）

### §3 APP-126 §3 —— 单测 + 回归（**不需要锁**）✅ **全过**

| 项 | 命令 | 结果 |
|---|---|---|
| 新增 node harness | `node tests/ext0419_bg_harness.js` | **18/18 PASS**（rc=0） |
| 新增 python 测试 | `python tests/test_ext0419_bgkeep.py`（**包内 python**） | **RESULT: PASS (12/12)**（rc=0） |
| 回归 python ×5 | `test_ext029_spk_bypass.py` | **70 PASS / 0 FAIL** |
| | `test_ext010_pipeline.py` | **25 PASS / 0 FAIL** |
| | `test_ext026_e2e_behaviors.py` | **21 PASS / 0 FAIL** |
| | `test_t1_capture_mode_stats.py` | **38 PASS / 0 FAIL** |
| | `test_ext028_dub_audio_chain.py` | **42 PASS / 0 FAIL** |
| 回归 node ×4 | `t3_settings_harness.js` | **26 PASS / 0 FAIL** |
| | `t4_lang_harness.js` | **28 PASS / 0 FAIL** |
| | `t5_t6_bounds_persist_harness.js` | **16 PASS / 0 FAIL** |
| | `ext026_segid_harness.js` | **13 PASS / 0 FAIL** |

⇒ **10/10 项全过，无一项失败**（按 APP-126 §3「任何一项失败 ⇒ 停在这里，不提交」——本轮无失败，故继续提交）。

### §4 APP-126 §4 —— 实时 e2e v5（**持机器锁**）✅ **7 臂全跑完**

- 🔴 **执行环境的三处偏离（如实登记，均已修，且不影响被测对象）**：
  1. **reviewer 脚本的锁路径 `C:\MACHINE_LOCK`（C:\ 根）在 App 会话下不可写**（`Open` ⇒ 「访问被拒绝」）⇒ 脚本的「取锁失败就 30 s 重试」分支**静默死循环**，桥接从未启动。
     ⇒ 只改 **锁路径**（`C:\MACHINE_LOCK` → `shared\MACHINE_LOCK`，**项目规范路径**），逐字节其余不动（`run_bgkeep_v5_app.ps1` 与原脚本 diff = **1 行**）。
  2. **本会话 env 有 3 个大小写变体 PATH 键**（`Path` / `PATH` / `path`）⇒ .NET `Start-Process` 抛「字典关键字 Path/PATH 重复」⇒ 桥接起不来。
     ⇒ 加一层 env 清洗（把 3 个变体合并成 1 个 `Path`），**只动环境，不动被测代码**。
  3. **后台任务有 ~2 min 硬上限** ⇒ reviewer 的「7 臂一个进程」跑不完（被杀时 `finally` 来不及删锁 ⇒ **锁泄漏**，已按 ctypes 规则证死并回收）。
     ⇒ 改为**每臂一个进程**（`Run-Arm` 函数体**逐字节相同**，已 assert），7 臂各自持锁/放锁 ⇒ 每臂 < 2 min。
- 🟢 **7 臂全部完成**（`shared\bgkeep\e2e8\`，**35 个文件**，每臂 5 个：`bgkeep_e2e.json` / `bridge.log` / `bridge.err` / `player_mix.wav` / `bg_only.wav`）：

| 臂 | bg_blocks | bg_contiguous | bg_late_blocks | fallback_to_orig_s | dubs | dub_shift msgs/applied | sep_rtf p50/p90 | 设备 |
|---|---|---|---|---|---|---|---|---|
| clip_cs2 | 74 | **True** | **0** | **0.0** | 15 | 10/2 | 0.209 / 0.228 | GPU.0 |
| clip_s1 | 23 | **True** | **0** | **0.0** | 4 | 0/0 | 0.221 / 0.229 | GPU.0 |
| clip_s2 | 31 | **True** | **0** | **0.0** | 5 | 1/1 | 0.219 / 0.231 | GPU.0 |
| clip_tuffy | 46 | **True** | **0** | **0.0** | 7 | 2/1 | 0.234 / 0.266 | GPU.0 |
| clone_s1 | 23 | **True** | **0** | **0.0** | 4 | 0/0 | 0.215 / 0.227 | GPU.0 |
| clone_s2 | 31 | **True** | **0** | **0.0** | 5 | 1/1 | 0.215 / 0.237 | GPU.0 |
| clone_cs2 | 74 | **True** | **0** | **0.0** | 21 | 18/11 | 0.200 / 0.232 | GPU.0 |

- 🟢 **clip_s2 首句 `shift_to` = 14.77 s**（APP-126 §5 要求 ≈14.7–14.8 s；修前 8.0 s）⇒ **达成**
- 🟢 **克隆模式**：`bg_clone_from_vocals` = 20 / 3 / 4（**克隆参考确实取自分离人声**），`bg_clone_fallback_orig` = **0**（无一路退回原声）
- 🟢 背景覆盖 `bg_covered_s` = 73.6 s = 素材全长（clip_cs2），`bg_up_gaps` = **0**

### §5 APP-126 §5 —— 数字核对 ＋ **一处必须如实报告的计数器口径问题**

**🔴 关键发现（reviewer 点名要核的「说话人标签数」）**：
- `stats_full.speaker.n_speakers` = **0**（7 臂全部），`spk_bypass.enabled` = **false**（note：「本会话未接说话人旁路（EXT-029：串行会话无 GPU 互斥锁 ⇒ 不接）」）。
- **但日志里标签是真的有**：`[spk] 段 seg_183040 标签=S1 音色=S1_1.wav` —— clone_cs2 **9 段**带真实标签、clone_s1 **1 段**、clone_s2 **0 段**。
- **已读源码定位根因（不是猜测）**：`ext/bridge.py` L65 `from .speaker import SpeakerTracker` ⇒ `stats_full["speaker"]` 是 **`ext/speaker.py` 那个 tracker**；它的 profile 只由 `_on_spk_label` 灌，而 `_on_spk_label` 是 **`--spk-bypass` 那条路**（`ext/speaker_bypass.py`，EXT-029）—— 本会话**没接**这条路。
  **克隆模式真正用的标签来自另一套实现**：`ext/clone_voice.py` 从 **App 包**（`Confucius4_LiveCaption_v2.5/app/speaker_tracker.py` 的 `SpeakerBridge`，ASR 侧 cluster v2）导入 ⇒ 打印 `[spk] 段 ... 标签=S1` 的就是它；**它的 stats 没有被 `ext/bridge.py` 收进 `stats_full`**。
  ⇒ **`n_speakers = 0` 是「计数器口径不同」，不是功能缺陷**：分离确实跑了、标签确实产生了并被应用。
- 🟢 **按 APP-126 §5「若仍为 0 或报错，原样贴日志片段，不要自行改代码」** ⇒ **本轮未改任何 live_dub_ext 代码**（只交 reviewer 的 15 个文件）。
- 🟢 **reviewer 自己的 e2e7 也是同样口径**（`clip_cs2` / `clip_s1` / `clip_s2` / `clip_tuffy` 的 `n_speakers` **全部 0**）⇒ **不是 v0.4.19 引入的回归**。
- 🟢 **分段模型确认**：`说话人资产（包内）：wespeaker fp16；pyannote_seg_3_0 fp16-w5（窗口 5.000 s，来源 asr_spk_window）`；**「分段推理失败」= 0 次**；**「形状」/「IR 输入长度」错 = 0 次**（3 个 clone 臂全部）⇒ **APP-126 §5 的三条（fp16-w5 / 无失败 / 标签数）前两条达成，第三条如上所述按口径报告**。

**reviewer 的 e2e7（只读，不覆盖）**：

| 臂 | blocks | contig | late | fallback_s | dubs | rtf p50/p90 | 设备 |
|---|---|---|---|---|---|---|---|
| off | 0 | True | 0 | 600.0 | 123 | — | — |
| on_gpu | 600 | True | 0 | **0.0** | 123 | 0.215 / 0.250 | GPU.0 |
| on_cpu | 600 | True | 0 | **0.0** | 123 | **0.458 / 0.589** | CPU |
| clip_cs2 | 74 | True | 0 | 0.0 | 15 | 0.194 / 0.218 | GPU.0 |
| clip_s1 | 23 | True | 0 | 0.0 | 4 | 0.225 / 0.231 | GPU.0 |
| clip_s2 | 31 | True | 0 | 0.0 | 5 | 0.215 / 0.234 | GPU.0 |
| clip_tuffy | 46 | True | 0 | 0.0 | 7 | 0.214 / 0.246 | GPU.0 |

⇒ 🟢 **我们的 e2e8 与 reviewer 的 e2e7 在同一素材上逐项吻合**（blocks 74/23/31/46、contig True、late 0、fallback 0.0、rtf 同量级）⇒ **互为交叉验证**。
⇒ 🟢 **分离 CPU 档 RTF 0.458（p90 0.589）vs GPU.0 档 0.215（p90 0.250）** ⇒ **默认分离设备应定 GPU.0**（CPU 慢约 2.1×）——**此结论供 reviewer 定默认设备时参考**。

**证据落盘**：`results/app/app126_bgkeep_e2e8_evidence.json`（33 698 B，含 e2e8 全量 + e2e7 只读 + `speaker_mode_analysis` 段）。

### §6 APP-126 §6 —— 提交并推 GitHub ✅

- 🟢 **只 `git add` 那 15 个文件**（逐文件 add，未用 `-A`；`git diff --cached --stat` 复核 = 15 个文件）
- 🟢 **提交号 `5121d99`**，提交信息**原样**：
  `EXT v0.4.19: keep background audio (Demucs on OpenVINO) — background replaces the ducked original, speaker/clone use separated vocals, dubs start at the real speech onset; fix speaker frame axis and segmentation IR`
- 🟢 **推送成功**：`ee45ce5..5121d99  claude-dev -> live-dub-ext`（refspec 已配；推前 `git fetch` 且本地与远端**无分叉**（0/0））
- 🟢 提交后 `live_dub_ext` 工作区**干净**；远端 `github/live-dub-ext` 已是 `5121d99`

### §7 APP-127 —— 陈旧 MACHINE_LOCK 判定：**无需删除**

- 开工时 `shared\MACHINE_LOCK` **不存在**；`C:\MACHINE_LOCK` 亦不存在 ⇒ **reviewer 的 `run_bgkeep_v4.ps1` 已正常结束并删了锁**。
- ⇒ APP-127 的三条判定（内容以 `reviewer bgkeep e2e v4` 开头 / 端口 8765-8766 无监听 / 无相关 python 进程）**均不适用**，**本轮未删除任何锁**。
- 🟢 但**本轮自己泄漏过一次锁并按规则回收**：§4 的后台任务被 2 min 上限杀掉 ⇒ 脚本 `finally` 未执行 ⇒ `shared\MACHINE_LOCK` 残留（内容 `app bgkeep e2e v5 ...`）。
  ⇒ 回收前用 **ctypes `OpenProcess` + `GetExitCodeProcess`** 证 owner（PID 29456）**真死**（`OpenProcess` err=**87** = PID 不存在）⇒ 才删除。
  🔴 **本轮修掉自己写的回收脚本里的一个 fail-open 缺陷**：初版 `alive = None`（探测失败）会被 `if alive:` 判假 ⇒ 仍会删锁 ⇒ 已改为 **`alive is not False`** 才允许删（探测失败 ⇒ fail-closed ⇒ 不删）；并把 `wmic` 探测换成 ctypes `CreateToolhelp32Snapshot`（本机 `wmic` 不可用）。

### §8 APP-123 —— c13 小窗口接入 App 的 OV TTS 流式路径（**开发完成，按 APP-126 §7 不进包**）

**§8.1 架构事实（读代码得出，不是推测）—— 这一条改变了做法**

- TTS 模块的 c13 = **自己驱动裸 OV IR**（`qwen3tts_genai_rc2/_tts075_stream_core.py`）：把 `openvino_codec_decoder` 静态 reshape 成 **[1,16,38]**，喂（左上下文 ++ 本块），块间**直接拼接**。
- **App 的 OV 路径 = BabelVox + 本仓库 `tts_engine_patch.py`（`MultiDecoderBabelVox`）**，它**本来就有**：① 左上下文（`ctx_frames`，把历史帧拼在 codes 前一起解码，只取本块 `num_frames*1920` 个采样）；② 长度守恒（切片 `wav_full[start:end]`）；③ 小静态窗口（`decoder_buckets` + `_select_decoder`）。
- 🔴 **所以 App 侧真正缺的不是「另起一套 IR 驱动」**（那是重写，不是接入），而是：**(a) 窗口口径没做成可配的 c13 口径**、**(b) 没有 TTS-076 的峰值限幅与削波计数**。
- 🔴 **另一个必须说清的发现**：babelvox 的 `_yield_chunk` 在 `not split_on_silence` 时**直接走「No crossfade — simple pass-through」分支**（不裁 `wav[:-ol]`），而 App 恒传 `split_on_silence=False` ⇒ **App 的 OV 路径本来就是「直接拼接」**，**没有** TTS-075 在 TTS 模块里发现的「每边界丢 50 ms / 共丢 7.3%」那个缺陷。
  ⇒ APP-123 的 `crossfade_samples=0` 因此是**显式化/加固**（今天不改变行为，但能防止将来有人改 `split_on_silence` 时静默失真），**不是**「修掉了一个 App 侧的丢音频缺陷」——**如实写，别让 reviewer 误读**。

**§8.2 c13 三个参数不是一回事（实测踩坑并修正）**

| c13 参数 | 含义 | 值 | App 侧对应物 |
|---|---|---|---|
| `n1` / `n_next` | **说话人每轮产出多少帧** | 8 | `CHUNK_FRAMES`（babelvox `chunk_frames`） |
| `decoder_ctx_frames` | 声码器**左上下文**帧数 | 25 | `CTX_FRAMES`（patch 的 `ctx_frames`） |
| `decoder_window_len` | 声码器**静态窗口**（= 13+25） | 38 | `DECODER_BUCKETS_CTX` 里选中的桶 |

- 🔴 **初版我把 `CHUNK_FRAMES` 设成 13**（误把「块容量」当成「每轮产出帧数」）⇒ 说话人要攒够 13 帧才吐第一块 ⇒ **首包从 2.9 s 劣化到 4.5 s**（同 seed 同文本实测，zh 句）⇒ **已改回 8**，首包恢复。
- ⇒ **c13 的正确落地 = 说话人每轮 8 帧（不变）+ 声码器固定 38 帧静态窗口 + 直接拼接 + 整句峰值限幅**。

**§8.3 代码改动（只在 dev 树 `live_caption\`，**未动任何客户包目录**）**

| 文件 | 改动 |
|---|---|
| `live_caption/tts_engine.py` | ① 新增 APP-123 口径块（`TTS_CHUNK_FRAMES_C13=8` / `CTX_FRAMES_C13=25` / `TTS_DECODER_WINDOW_C13=38`）；② `CHUNK_FRAMES` / `CTX_FRAMES` / `DECODER_BUCKETS_CTX` 改为**环境变量可配**（默认 = c13）；③ `DIRECT_CONCAT` 开关（默认 1）；④ 引擎日志**显式打印窗口口径**（`chunk= ctx= window= buckets= join=`）；⑤ `stream()` 在 `DIRECT_CONCAT` 下传 `crossfade_samples=0`（**签名探测**，老 babelvox 不认就不传） |
| `live_caption/tts_worker.py` | ① 逐块统计 `n_clipped`（\|x\|≥1.0）/ `n_near_fs`（\|x\|≥0.999）；② 新增 `app123_peak_limit()`（TTS-076 口径**整句缩放**：peak>0.98 ⇒ gain=0.98/peak）；③ 整句装配后限幅并回写逐块；④ 遥测新增 `n_clipped` / `n_near_full_scale` / `peak_before_limit` / `limiter_gain` |
| 🔴 `live_caption/tts_cuda.py` | **零改动**（APP-123 明文「CUDA 路径不动」；`tts_engine_patch.py` 亦零改动） |

- 环境变量：`LIVECAP_TTS_CHUNK_FRAMES` / `LIVECAP_TTS_CTX_FRAMES` / `LIVECAP_TTS_DECODER_BUCKETS` / `LIVECAP_TTS_DIRECT_CONCAT`（reviewer 可一键 A/B）

**§8.4 验收（已完成的）**

- 🟢 **静态 + 行为验证 33/33 PASS**（`live_caption/_app123_verify.py`，含 3 个**反证组**：改坏必须变红）
  - V1 c13 口径可配且默认正确（chunk=8 / ctx=25 / window=38；反证：改 env 后值确实变、非法 env 回退默认）
  - V2 直接拼接（**对着包内真实 babelvox 源码验**，非 mock）：pass-through 分支**不裁尾**、crossfade 分支**确实裁 `wav[:-ol]`**；App 确实传 `crossfade_samples=0` 且先探签名
  - V3 限幅行为（热信号缩到 0.98 且 \|x\|≥0.999 计数 = 0；静信号**逐位不变**；**反证**：硬削会留下 2 个满量程采样 ⇒ 判据有区分力）
  - V4 **CUDA 路径零改动**（`tts_cuda.py` sha256 `7fe6e44cc34bc56f`、无 APP-123 标记；`tts_engine_patch.py` 亦无）
- 🟢 **真跑实测（NPU = 生产档；包内 python + 包内 IR）**：
  - **长度守恒成立**：`samples = frames × 1920`（zh **78 720 = 41×1920**、en **26 880 = 14×1920**），**每块都是 1920 的整数倍**，`n_clipped` = **0**、`n_near_fs` = **0**
  - **窗口 A/B（同 seed ⇒ 同一批 token）**：多桶 [8,16,32,33] vs c13 固定 38 ⇒ **样本数完全相同**、**SNR = 56.44 dB (zh) / 57.99 dB (en)** ⇒ 换窗口是**可测的轻微变化**，不是「同一件事的两种写法」
  - **GPU.0 臂**：两臂 **SNR = ∞ dB（逐字节相同）** —— 因为**桶只在 NPU 生效**（GPU 走动态形状解码器，`tts_engine_patch.py` L195-204）⇒ **桶口径的差异只在 NPU 出现**
  - NPU 首包 **0.55–0.90 s**、RTF **0.856–0.948**
- 🟢 **EXT 侧**：EXT 通过 `ext/engine_runtime.py` 调 **App 的 `tts_engine.stream`** ⇒ **同一份代码，自动用上 c13**；`extension/player.js` **没有固定 0.64 s**（全仓 grep 无此常量），配音按 `b64ToAudioBuffer(msg.pcm24k, sr.rate)` 得到的**实际采样数**排程（`buf.duration`）⇒ **APP-123 §2「按每块实际采样数排程」已满足**。

**§8.5 未做的部分（按 APP-126 §7 + 纪律，如实列出）**

- 🔴 **不进包**：按 APP-126 §7「**不要**开始 v2.6 打包」，本轮**未把 c13 同步进任何客户包目录、未生成新目录/新 zip、未重签 ACCEPTED**；dev 树的改动**只存在于 `live_caption\`**。
- 🔴 **未跑 APP-123 §验收的 10 分钟整链 c13 开/关两轮**：那是「打包与 10 分钟验收」，按 APP-126 §7 等 reviewer 复核本条结果 + 定下默认分离设备后再交接。
- 🔴 **未做 MiniMax 回转写抽查**（10 分钟整链里的随机 30 句）—— 与 APP-122 的抽听样片一起等同一交接点；且**质量判定按纪律由 reviewer 用 MiniMax 回转写，App 线程不自己调用 MiniMax**。
- 🔴 **未准备 `results/app/app123_listen/` 的 6 段样片**：需先跑整链，随整链一起做。
- 🔴 **限幅的诚实边界**（写清楚，别让 reviewer 误读）：OV 路径**每块**的硬削发生在 `babelvox/pipeline.py` L637（`np.clip(wav,-1,1)`），那在**块级**、在我们看到整句之前 ⇒ **块内已越界的采样无法恢复**；本轮做的是**整句**层面保证成品 ≤ 0.98（不再叠加失真）并**如实报出** `n_clipped` / `n_near_fs` / `peak_before` / `limiter_gain`。

### §9 本轮纪律与事故登记

- 🟢 **未打包**（按 APP-126 §7 ＋ 用户「不通知不打包」规则）｜🟢 **未改任何客户包既有文件**｜🟢 **未连 B 机**｜🟢 **未调 MiniMax**｜🟢 **未改纠偏文件**（SHA 零改动）
- 🟢 **只提交 App 侧文件**（`live_caption/` 的两个产品代码文件 + 脚本 + 证据 json + STATUS/companion），**逐文件 `git add`（禁 `-A`）**；**`status/app/CORRECTIONS_APP.md` 未 add**；ASR/MT/TTS 其它模块的脏改动**未吞**。
- 🔴 **本轮如实登记 5 处事故**：
  1. **锁泄漏 ×1**：后台任务被 ~2 min 上限杀掉 ⇒ 脚本 `finally` 未执行 ⇒ `shared\MACHINE_LOCK` 残留 ⇒ 按 ctypes 证死（`OpenProcess` err=87）后回收。
  2. **回收脚本 fail-open**：初版把「探测失败」(`alive=None`) 当成「可删」⇒ 改为 `alive is not False` 才删（fail-closed）。
  3. **CRLF 二次应用**：写文件时把已含 `\r\n` 的文本再 `replace('\n','\r\n')` ⇒ 变成 `\r\r\n` ⇒ `ast.parse` 报 `invalid character '🔴'` ⇒ **从 `%TEMP%` 备份还原**后重做（还原后 `ast.parse` PASS、CRLF 计数与原文一致、孤立 LF = 0）。
  4. **docstring 未闭合**：第一次插限幅 helper 时 `"""` 没闭合 ⇒ 同上还原重做。
  5. **补丁脚本幂等守卫失效 ⇒ 削波计数器被插了 3 份**：守卫只认「helper 定义行」，而计数器是**另一个脚本**插的 ⇒ 重跑时计数器被重复插入 3 次（`n_clipped = 0` 出现 3 次）。
     ⇒ **从备份还原**后，把守卫改成**按各自拥有的标记**判定（脚本 1 守计数器、脚本 2 守 helper/应用块），并**在守卫命中时明确拒绝**而不是静默跳过；现测**重跑两次文件 md5 不变**、各标记**恰好 1 份**。
- 🟢 **本轮踩到并修正的判据/实现错误 2 处**：① **c13 参数语义混淆**（把「块容量 13」当成「每轮产出帧数」⇒ 首包劣化 2.9→4.5 s，实测发现后改回 8）；② **A/B 被采样噪声污染**（babelvox 用**全局** `np.random` 且 App 从不播种 ⇒ 两臂抽到不同 token）⇒ 改为**每臂 `np.random.seed(20261023)`** 后 A/B 才有效（同臂样本数完全一致）。

### §10 待 reviewer 裁定 / 交接

1. 🟡 **`n_speakers = 0` 的口径**（§5）：如上，**不是缺陷**，但**是否要把 App 侧 `SpeakerBridge` 的 stats 收进 `stats_full`**（让 reviewer 一眼看到真实标签数）**请 reviewer 定**（改 `ext/` 属 reviewer 分工，App 线程未动）。
2. 🟡 **默认分离设备**：实测 **GPU.0 0.215 / CPU 0.458**（p50 RTF）⇒ 建议 **GPU.0**；等 reviewer 定。
3. 🔴 **APP-123 的「进 v2.6 + 10 分钟整链 + MiniMax 抽查 + 抽听样片」**：等 reviewer 复核本条（APP-126 结果 + APP-123 开发）后再交接执行。
4. 🔴 **APP-122 的「打包进 v2.6 + APP-122 §验收」**：同上等交接。
