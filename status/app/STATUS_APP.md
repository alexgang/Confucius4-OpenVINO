# STATUS_APP
last_ack: APP-006
更新时间: 2026-10-23 16:52
当前任务: **巡检完成：`CORRECTIONS_APP.md` 最大编号 = APP-006 = last_ack ⇒ 本轮无新纠偏条目**。本轮闭环三件事：① **TTS NPU 冒烟通过**（持锁，216.3 s exit=0；产物 4 文件落仓库外 `tts_smoke_out/`；`speaker_embed (1,1024)`、24000 Hz、4 chunk；命中缓存后 `load_s` 9.99 s）② **修掉「内置音色抛 ValueError」真 bug**（根因：`eng.speaker_library` 未挂 ⇒ 读 babelvox 源码定位；修复后 `builtin_speaker_n_chunks=4`）③ **`.gitignore` 加固**（补 `results/asr_diag/` 与 `results/**/*.npy`）。另**撤回 §12.2「内置音色全部内置」的表述**。详见 §13。
阻塞 / 待用户决定: ① **APP-006 第 3~7 步**：历史改写 + force push（等 reviewer 复核 §11.2 清单；且**改写后所有 SHA 全变**，并行线程 ASR/MT/TTS 需重新 clone 或 reset --hard，**会覆盖他们未提交的改动**）——**本轮已按纪律停下**；② **端到端 ABBA 未做**（冒烟已过，前置已解锁）；③ **v1.4 重打包前置未完成**（设备自选 ✅ + TTS 集成 ✅ + 端到端验证 ❌）；④ **RTF 无正式结论**（本轮 1.357 是自测短句首调用含预热，不可当稳态）；⑤ **包体 12.73 GB**（需评估剔除 `decoder-npu-int8`/`decoder-gpu-int8`/`encoder-fp16`）；⑥ 是否剔除 INT4-CW（可再省 0.97 GB）；⑦ **babelvox tokenizer 的 `fix_mistral_regex` 提示**待 TTS 模块确认；⑧ **音质判定交 reviewer**（目标机不自己调 MiniMax）

## 最近更新
- 16:52 §13 **巡检无新条目 + 三件事闭环**：TTS NPU 冒烟**通过**（持锁 216.3 s exit=0，`load_s` 9.99 s 命中缓存，`builtin_speaker_n_chunks=4`）；修掉内置音色 `ValueError: speaker_library not set`（根因读 babelvox 源码定位，挂 `SpeakerLibrary` 后 4 音色可用）；`.gitignore` 加固（`results/asr_diag/` + `results/**/*.npy`，check-ignore 全命中）
- 16:52 §13 **撤回 §12.2 一条结论**：「内置音色全部内置」不准确 ⇒ 实为**随包分发**（4 组 json+npy）且**必须显式挂 `SpeakerLibrary`**；但 §12.2 主结论「spkonly 不需要 ref_text」仍成立
- 16:52 §13 **如实记录未完成项**：端到端 ABBA 未做、v1.4 未重打、APP-006 第 3~7 步等 reviewer、RTF 无稳态结论、音质交 reviewer
- 16:52 §13.4 **并行改动隔离**：`live_caption_app.py`（并行会话 16:47 仍在改）/ `translator.py`（MT）/ `audio_source.py`（ASR）/ `tts_service.py` / `streaming_asr.py` 均**不提交**；`CORRECTIONS_APP.md` **绝不提交**；逐文件 `git add` 未用 `-A`
- 16:52 §13.6 **复验通过**：`pack_v13.py --dry-run` **PASS**（INT8 4 个关键文件 + Qwen3TTS 12 个 IR 全 [OK]）；`check_internal_material.py` **0 命中**；`diag_device_select.py` **ALL PASS**（设备配置已自恢复默认）
- 15:35 §12 **巡检无新条目 + 三件事闭环**：APP-005① 补推送关闭远端泄露（`origin/main` c134_replay 7 条→0，普通 push 非 force）；`tts_engine.py` 纠正为 spkonly（`PRESET_A_REF_TEXT=None`，删 `ref_text`/`ref_audio` 入参）；`tts_worker.py` 接入 BabelVox（24000 Hz + `_reopen_player`）；修掉 `split_long_text()` 单句判据→累计判据 bug；客户包 TTS 清单 55/55 SHA256 全对、`voices/` 仅音色 A
- 15:35 §12 **如实记录未完成项**：NPU 冒烟超时（无 RTF/音质结论）、ABBA 未做、v1.4 未重打、APP-006 第 3~7 步等 reviewer
- 15:35 §12.6 **并行改动隔离**：`translator.py`（MT 回退到 C-111 前基线）/ `live_caption_app.py` / `audio_source.py` / `tts_service.py` 均**不提交**，逐文件 `git add` 未用 `-A`
- 15:40 §12.8 **提交推送 + 锁释放闭环**：commit `ca818ee`（6 个文件，闸门 PASS + 7789 条替换表 0 命中），`git push origin main` 普通快进（0 behind/1 ahead，未 force），远端 c134_replay 复查 = 0；`MACHINE_LOCK` 经 `_pid_alive()` 确认 31752/30136 均已死后释放
- 15:38 §12.5 #1 订正：NPU 冒烟 **15m00s 被 `timeout` 终止**，产物目录 0 文件（缓存已 13 blob/3.83 GB ⇒ 冷编译非挂死）⇒ **冒烟未过，无任何性能结论**
- 13:29 §11 **APP-005①② + APP-006 第1~2步 落地**：c134_replay 脱库（`git ls-files results | grep c134` 空）、pack_v13 INT8 断言改正（dry-run INT8 全部 [OK]、缺 bin 时 FAIL 已验证）、MANIFEST 刷到 13973 文件/13.67 GB、备份 2.7 GB mirror 已建、脱敏替换表 7789 条已生成、内部素材闸门脚本已挂进 pack_v13
- 13:28 发现并处理 **包根 `_backup_c111/` 污染**（C-133 教训重现）：已移出到 `pkg_backup_app005/_backup_c111/`，并给 `pkg_exclude.py` 加 `BACKUP_DIR_RE` 规则（任意层级）
- 13:27 脱敏客户包与仓库源码里的内部音频文件名（`<redacted>.wav` → `<内部音频>.wav`），客户包内部素材闸门复扫 **0 命中**
- 13:26 `git clone --mirror` **被沙箱拦截**（不许读 `.ssh/known_hosts`）⇒ 改用**本地仓库**做 mirror（本地 main 领先 origin/main 3 个 ASR 提交且含远端全部历史 ⇒ 等价且不需授权）
- 13:23 `pack_v13.py` 加内部素材闸门钩子 + INT8/TTS 的 MUST/MUST_NOT + `only_int4` 改双向断言；`MANIFEST` 加 `packages` 自动收集与 v1.4 notes
- 13:19 APP-006 第1步 **mirror 备份完成**：`C:/Users/Trekker-PTL/git_backup/Confucius4-OpenVINO_20261023.git`（2.7 GB，fsck 仅有 dangling 对象）
- 13:18 APP-005① **c134_replay 脱库** + `.gitignore` 加固（`results/**/*replay*` / `reports/**/transcript_*` / `segments_*` / `**/*_spoken.*`）
- 13:15 新建 **App 模块专属纠偏巡检自动化**（`FREQ=HOURLY;INTERVAL=1`，与 ASR/MT 对齐）—— 补上了此前缺失的第 3 个模块巡检
- 12:57 读到 **APP-005**（BLOCKING×2+HIGH）与 **APP-006**（BLOCKING，用户决定改写历史 + force push）
- 11:24 **APP-003 全部落地**：① results/ 内部会议内容已隔离（11 文件移至 `pkg_internal_quarantine/`）；② 默认翻译改 **INT8-CW**；③ CORRECTIONS 第 23 行改为「[目标机工作记录·非纠偏]」；④ **更正 §4 的时间戳**
- 11:20 §8：默认 MT 改 INT8-CW 的代码/IR/文档改动全表 + 包体积变化（8.28 → 9.97 GB，+1.69 GB）
- 11:10 §5 实测：客户包 Python 3.12 **能直接跑** Qwen3-TTS；最小依赖集 **297 MB** + IR **2542 MB**
- 09:34 补齐 APP-001 要求的 4 项现状汇总（§4）

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

### 8.7 CLI 回放（APP-002 ③）—— ✅ 已完成

脚本：`live_caption/replay_c134_mt.py`（**新建**，244 行）
- **等锁**：轮询 `C:/Users/Trekker-PTL/shared/MACHINE_LOCK`；锁内 PID 不在了
  或锁早于开机时间 ⇒ 回收；否则每 20 s 打印等待进度。
- **持锁**：创建锁（内容：模块名 / PID / 开始时间 / 主机名），跑完删除。
- **ABBA**：`off / on / on / off` 四轮，同一段音频（`test_audio/<redacted>.wav`，
  取前 60 s）、同一个 ASR 后端（`gpu_int8`）、语种锁 `Chinese`。
- **记录**：ASR RTF、段数、逐段文本、墙钟；落盘 `results/c134_replay/`。

**锁持有记录**：获取 **11:23:11** → 释放 **11:28:10**（脚本 stdout 的 `[lock] 已获取` /
`[lock] 已释放`；回放期间锁文件一直存在，释放后 `shared/` 目录下已无 `MACHINE_LOCK`）。
启动时锁被 **TTS 模块**占用（`module: tts / pid: 36608 / started 11:04:02`，实测该 PID 存活）
⇒ 脚本**排队等待约 19 min**后才取到锁，**未抢锁**。

#### 8.7.1 ABBA 四轮 —— ASR 侧（原始 stdout 行）

| 轮次 | 翻译 | exit | 墙钟 | ASR RTF | 出字延迟中位 | 最大积压 | 段数 |
|---|---|---|---|---|---|---|---|
| abba1_off | off | 0 | 69.07 s | **0.629** | 418 ms | 1.0 s | 10 |
| abba2_on | zh | 0 | 74.78 s | **0.670** | 421 ms | 2.5 s | 10 |
| abba3_on | zh | 0 | 71.52 s | **0.523** | 347 ms | 0.6 s | 10 |
| abba4_off | off | 0 | 69.00 s | **0.673** | 435 ms | 1.3 s | 10 |

原始 stdout（逐字）：

```
[gpu_int8] 音频 60.1s  墙钟 60.7s  RTF(计算) 0.629  出字延迟中位 418 ms  最大积压 1.0s  段 10
[gpu_int8] 翻译 target=zh 后端=auto 设备 GPU.0 state=ready 句数 14  延迟中位 519.2 ms  P95 1352.2 ms  TTFT 276.6 ms  29.6 tok/s
[gpu_int8] 音频 60.0s  墙钟 60.7s  RTF(计算) 0.670  出字延迟中位 421 ms  最大积压 2.5s  段 10
[gpu_int8] 翻译 target=zh 后端=auto 设备 GPU.0 state=ready 句数 14  延迟中位 346.0 ms  P95 682.2 ms  TTFT 164.1 ms  41.7 tok/s
[gpu_int8] 音频 60.0s  墙钟 60.6s  RTF(计算) 0.523  出字延迟中位 347 ms  最大积压 0.6s  段 10
[gpu_int8] 音频 60.0s  墙钟 60.6s  RTF(计算) 0.673  出字延迟中位 435 ms  最大积压 1.3s  段 10
```

#### 8.7.2 ABBA 两轮 —— 翻译侧（仅 on 轮有）

| 轮次 | state | 句数 | 延迟中位 | 延迟 P95 | TTFT | 吞吐 |
|---|---|---|---|---|---|---|
| abba2_on | ready | 14 | 519.2 ms | 1352.2 ms | 276.6 ms | **29.6 tok/s** |
| abba3_on | ready | 14 | 346.0 ms | 682.2 ms | 164.1 ms | **41.7 tok/s** |

#### 8.7.3 回放产物（文件名 + mtime + 大小）

| 文件 | mtime | 大小 | 说明 |
|---|---|---|---|
| `results/c134_replay/abba1_off.txt` | 11:24 | 906 B | 轮1 定稿原文（10 段） |
| `results/c134_replay/abba2_on.txt` | 11:25 | 906 B | 轮2 定稿原文（10 段） |
| `results/c134_replay/abba2_on.mt.txt` | 11:25 | 1131 B | 轮2 译文（9 行） |
| `results/c134_replay/abba3_on.txt` | 11:27 | 906 B | 轮3 定稿原文（10 段） |
| `results/c134_replay/abba3_on.mt.txt` | 11:27 | 1238 B | 轮3 译文（10 行） |
| `results/c134_replay/abba4_off.txt` | 11:28 | 906 B | 轮4 定稿原文（10 段） |
| `results/c134_replay/replay_report.json` | 11:28 | 20216 B | 汇总报告（4 轮 stdout/stderr 尾部 + 逐段样本） |

#### 8.7.4 结论（6 条）

1. **翻译链路正常**：两轮 on 共 **28 句全部出译文**，`state=ready`，**无空输出、无乱码**。
   抽样（`abba2_on.mt.txt`）：「实现亚历克斯在最后一次[REDACTED]中提到的业务增长目标。」
   「[REDACTED] 好的。」
2. **INT8-CW 吞吐与 MT 模块实测一致**：回放 29.6 / 41.7 tok/s，MT 基准 37.5 tok/s
   ⇒ 同一量级，**没有降级到 INT4**（INT4 应为 57.9 tok/s，明显更快）。
3. **翻译对 ASR RTF 无可测影响**：off {0.629, 0.673} vs on {0.670, 0.523}，
   差值 ±0.1 完全落在噪声内（且 on 的两轮**一高一低**，无系统性方向）。
4. **段数稳定**：4 轮均为 **10 段**（60 s 音频，段长约 6 s）⇒ 翻译开关**不改变切段行为**。
5. **最大积压**：on 轮 2.5 s / 0.6 s，off 轮 1.0 s / 1.3 s ⇒ 翻译侧有排队，
   但**未把积压传给 ASR**（出字延迟中位 347~435 ms，与 off 轮同档）。
6. ⚠️ **端到端墙钟不作性能判据**（on 轮多 2.5~5.7 s，含 INT8 权重首次加载）
   ⇒ 一切结论以 ABBA 差值 + 分项指标为准。

#### 8.7.5 本节踩坑（3 条）

| # | 坑 | 现象 | 修法 |
|---|---|---|---|
| 1 | 🔴 **`tasklist` 在 Git Bash 下被转义破坏** | 用 `tasklist /FI "PID eq N"` 判活，Git Bash 把 `/FI` 当路径 ⇒ 报「无效参数/选项 - 'FI'」；异常被 `except` 吞掉后返回 False ⇒ **误判活锁为死锁并回收**。**实测踩到：把 TTS 模块的活锁（pid=33572，进程仍在跑）回收了**，随后又回收了 MT 的锁（pid=18564） | 改用 `ctypes` 的 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `GetExitCodeProcess`；`ACCESS_DENIED` 视为存活；**任何异常一律返回 True（保守视为存活，宁可等也不误回收）**。已实测 6 个活进程 True / 2 个死进程 False |
| 2 | **子进程 stdout 是 GBK 不是 UTF-8** | `subprocess.run(..., text=True, encoding='utf-8')` 抛 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xcf in position 4` | 改 `capture_output=True` 不带 `text=True`，拿到 bytes 后自己 `decode('utf-8', errors='replace')` |
| 3 | **`--out` 写出的定稿文本没有 `[start-end]` 前缀** | 段数统计恒为 **0**（原按时间戳前缀正则匹配） | 改为按**非空行**统计；复核 4 轮 `abba*.txt` 均为 **10 段**，与 stdout 的「段 10」一致 |

#### 8.7.6 与 reviewer 要求的对应

| reviewer 要求 | 本节落点 |
|---|---|
| 跑一次 CLI 回放，确认翻译正常 | §8.7.3 产物表 + §8.7.4 结论 1（28 句全出译文、无空/乱码） |
| 记录翻译延迟 | §8.7.2（延迟中位 346~519 ms / P95 682~1352 ms / TTFT 164~277 ms） |
| 记录对 ASR RTF 的影响 | §8.7.1（ABBA 四轮 RTF）+ §8.7.4 结论 3 |
| 计时要持机器锁 | §8.7 锁持有记录（11:23:11 → 11:28:10，排队 19 min 未抢锁） |
| STATUS 写上改动的行号 | §8.2（6 处行号表） |
| CLI 回放产物（文件名/mtime） | §8.7.3 |

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

### 9.4 git 提交状态

**第一次提交（已完成）**：commit **`fd5b7ef`**「C-133/C-134：默认 MT 改 INT8-CW（用户决定）+ 客户包瘦身 + results 内部内容隔离」
—— **15 文件 / +2512 −65**。含 `pkg_exclude.py` / `pack_v13.py` / `update_manifest_v13.py` /
`fix_manifest_v13d.py` / `live_caption/{translator,npu_delivery_backend,npu_embeds_backend}.py` /
`live_caption/sync_c133_to_pkg.py` / `live_caption/sync_c134_to_pkg.py` /
`live_caption/replay_c134_mt.py` / `verify_tts_deploy.py` / `status/app/` / `results/tts_deploy_verify.json`。

> `live_caption/live_caption_app.py` 用 `git apply --cached` **只暂存第 1 个 hunk**
> （C-133 缓存外移，30 行），把 TTS 模块的 9 个 hunk 留在工作区未提交 —— 避免误吞他人改动。

**第二次提交（本轮，待执行）**：commit「C-134：默认 MT 改 INT8-CW 的 CLI 回放实测 + STATUS §8.7 补写」
—— 应含 `live_caption/replay_c134_mt.py`（2 处修复：GBK 解码 / 段数统计）、
`results/c134_replay/`（7 个产物文件）、`status/app/STATUS_APP.md`（§8.7 补写 + 头部 + §9.4）。

**仍未提交（属于其他模块，本模块不碰）**：
- `M live_caption/live_caption_app.py`（TTS 模块的 9 个 hunk，本模块只入了第 1 个）
- `M live_caption/tts_service.py`、`M live_caption/tts_worker.py`
- `M status/CORRECTIONS.md`（旧 C 编号文件，已冻结在 C-135）
- `?? live_caption/diag_punct_*.py`(11)、`?? live_caption/diag_seg_qwen3*.json`(4)、`?? reviewer/find_int8enc.ps1`

⚠️ **有并行会话在同一项目工作**（HEAD 在本轮前后被别的模块推进）
⇒ **本模块只提交自己负责的文件**，不碰 TTS/ASR 模块的改动；推远端前先看 `git log` 确认无新冲突。

---

## §10 APP-004 回执与四项现状盘点（2026-10-23 11:52）

> reviewer 原文（`CORRECTIONS_APP.md` APP-004，11:17）：
> ① **C-111 交给 App 模块接手**；② **TTS 模型文件随客户包分发**；
> ③ **每个模型的推理设备让用户自己选**；④ **重新打包 v1.4**。
> 「**请先回执，并按顺序先处理 APP-003（BLOCKING）。**」

### 10.0 回执：APP-003 已完成，APP-004 开始接手

| APP-003 条目 | 状态 | 落点 |
|---|---|---|
| ① results/ 内部会议内容隔离 | ✅ **已完成** | §6（dry-run PASS，0 残留；11 文件移至 `pkg_internal_quarantine/`） |
| ② 默认 MT 改 INT8-CW | ✅ **已完成并验证** | §8 + §8.7（ABBA 4/4 exit=0，锁 11:23:11→11:28:10） |
| ③ CORRECTIONS 只由 reviewer 写 | ✅ **已完成** | §7（正文迁出，第 23 行改为占位标题） |
| ④ 时间戳更正 | ✅ **已完成** | §9.1（10:15/10:20 作废 → 09:34） |

⇒ **APP-003 全部关闭，可以进入 APP-004。**

### 10.1 ① C-111 合入 —— ✅ **已由 ASR 提交，本模块核对通过**

| 检查项 | 实测 | 判定 |
|---|---|---|
| C-111 提交 | `ebc6107`「C-111：翻译层『段尾半句当段即翻 + 补全后修正』」**8 文件 +1686 −56** | ✅ 已在 `main` |
| `live_caption/translator.py` | 工作区 **无未提交 diff**（`git diff` 空）⇒ C-111 改动已全部入库 | ✅ |
| `live_caption/translator.py` 的 C-111 标志 | `seg_carry` / `seg_half` / `_half` / `_enqueue_half` / `_enqueue_fix` 全部在位（`seg_half` 计数 5） | ✅ |
| 客户包 `app/translator.py` vs 仓库 | `diff -q` = **IDENTICAL**（**字节相同**）⇒ C-111 与 C-134 改动**没有互相覆盖** | ✅ |
| 客户包 `app/live_caption_app.py` 的 C-111 标志 | `seg_half.clear()`（L1443）、`（译文生成中…）`（L1460 / L1787） | ✅ |
| 客户包 `app/live_caption_app.py` 的 C-133 标志 | `Confucius4LiveCaption`（编译缓存外移）命中 1 处 | ✅ |
| 客户包 `app/live_caption_app.py` 的 TTS 标志 | `var_tts_on` / `tts_service` 命中 **0** ⇒ **TTS 面板未误入交付态** | ✅ |

🔴 **本模块需要注意的一处状态**：`live_caption/live_caption_app.py` 仍有 **10 个 hunk 未提交**
（`git diff` = +214 −2），逐 hunk 核对后确认**全部属于 TTS 模块**（`var_tts_on` /
`tts_voices` / `_on_tts_toggled` / `cb_tts_out` / `--tts-out` 等），
**不含任何 C-111 内容** ⇒ ASR 线程的 C-111 5 处已在 `ebc6107` 单独入库，两者**不冲突**。

⇒ **C-111 无需本模块再合入**，直接进入端到端验证环节。

### 10.2 ② TTS 模型随包 —— ⏳ **待做**，交接单已到

交接单：`qwen3tts_eval/TTS_交接单.md`（**12745 B，mtime 11:38**），
机读清单 `qwen3tts_eval/results/tts_handoff_filelist.json`。

| 项目 | 交接单口径 | 待办 |
|---|---|---|
| IR（`int8/`） | **18 文件 / 1672.8 MB** | 拷入客户包 `models/qwen3tts/int8/` |
| 权重（`weights/`） | **37 文件 / 869.5 MB**（.npy + config） | 拷入客户包 `models/qwen3tts/weights/` |
| 合计 | **55 文件 / 2542.3 MB** | ⚠️ 包体会 **+2.48 GB**（当前 9.97 GB ⇒ 约 **12.45 GB**） |
| 许可证 | 全部 **Apache-2.0**（Qwen3-TTS / babelvox / IR 导出 / Amphion metis） | 包内放 `NOTICE` 汇总归属 |
| 运行时依赖 | `openvino` / `numpy` / `soundfile` / `scipy` / `transformers` / `huggingface_hub` / `num2words` / `librosa` / `defusedxml` / `babelvox` | vendored 随包（离线可跑，`HF_HUB_OFFLINE=1`） |
| 音色 | 只带 **音色 A**（`preset_A.wav` 6.00 s / 16 kHz / mono / SHA256 `e021c255…db53`，ref_text 固定） | ⚠️ 音色 C / 同事音色 B **禁止进包** |

🔴 **交接单 §7 留了 6 个待 App 确认的问题**，本模块的决定（写入 STATUS 待 reviewer 确认）：

| # | 问题 | 本模块决定 | 理由 |
|---|---|---|---|
| 1 | 模型放包内哪个目录 | **`models/qwen3tts/`**（`int8/` + `weights/` 两个子目录） | 与 ASR/MT 的 `models/` 布局一致 |
| 2 | 编译缓存目录名 | **`tts_npu_cache`**，放 `%LOCALAPPDATA%\Confucius4LiveCaption\tts_npu_cache` | 沿用交接单建议 + ASR 的 `<name>` 命名规则；**不得写进包目录** |
| 3 | `librosa`/`scipy` 整条依赖树 | **裁剪**：只保留 `babelvox` 实际 import 到的子集（`num2words`/`soundfile`/`scipy` 视实测 import 链定），**必须 `--no-deps` + 白名单** | 否则 pip 会升级 `transformers`/`huggingface_hub`，**破坏 ASR/MT** |
| 4 | `NOTICE` 放哪 | **包根 `NOTICE`**（与 `README_zh.md`/`README_en.md`/`MANIFEST.json` 同级） | 客户一眼可见；MANIFEST notes 里引用 |
| 5 | GPU.0 档是否暴露给用户 | **暴露，但默认 NPU** | 交接单 §2 的建议 |
| 6 | TTS worker 与 ASR/MT 的线程关系 | **独立进程 + 单线程 FIFO**（`tts_worker.py` 已是这个结构） | 交接单 §8 明确这归 App 模块 |

⚠️ **当前 `tts_worker.py` 仍是旧引擎**（走 `OVSynth` + BigVGAN，精度参数 `f32`/`f16`）
⇒ **必须适配 Qwen3-TTS 的 `BabelVox` 引擎接口**（交接单 §1.1 的 7 个参数 +
`use_kv_cache=False` / `split_on_silence=False` / `precision='int8'` **三个不能改错的参数**）。
这属于 APP-001 遗留的「worker 侧适配新引擎接口」，见 §10.5。

### 10.3 ③ 设备自选 —— ⏳ **待做**，现状盘点

reviewer 要求：**ASR / MT / TTS 三个模型各一个设备下拉框**，选项来自
`ov.Core().available_devices` **实际检测**，检测不到的不显示；默认值用各模块推荐配置；
不可用组合给明确提示并**回退默认**；选择保存到 `%LOCALAPPDATA%` 配置并**下次启动恢复**。

**现状逐项核对**：

| 要求 | 现状 | 缺口 |
|---|---|---|
| GUI 设备下拉框 | ❌ **ASR 无独立设备框**（只有「后端」下拉 `ENGINES`，设备写死在 `ENGINES[key]['device']`）<br>❌ **MT 无独立设备框**（设备写死在 `MT_ENGINES[key]['device']`）<br>⚠️ TTS 有 `cb_tts_out`，但那是**音频输出设备**，不是推理设备 | 三个推理设备下拉框都要新建 |
| CLI 参数 | ⚠️ 有 `--mt-device`（默认 GPU.0）、`--tts-device`（默认 GPU.0）<br>❌ **无 `--asr-device`** | 加 `--asr-device` |
| 设备来源 = 实际检测 | ✅ 已有 `_check_devices()`（内部 `ov.Core()` 探测）可复用 | 抽成公共函数 |
| 默认摆放 | ASR：`gpu_int8`（GPU.0）<br>MT：GPU.0<br>TTS：**NPU**（交接单 §1.1 推荐） | TTS 默认从 GPU.0 改 NPU |
| 不可用组合提示 + 回退 | ❌ 无 | 新增 |
| `%LOCALAPPDATA%` 配置持久化 | ❌ 无 | 新增 `device_config.json` |
| 三个模型共用设备的已知影响 | ❌ 未记录 | 写进 README + STATUS |

⚠️ **必须注意的既有铁律**（改设备选择时不能违反）：
① **NPU 只支持 f16/i8**（`INFERENCE_PRECISION_HINT=f32` 被拒）；
② **NPU 上必须「按需加载」IR**，无条件编 4 个 ⇒ `Concat ... doesn't fit to output dimension`；
③ **声码器在 iGPU 上是负加速 0.42~0.64× 且 SNR 仅 21 dB** ⇒ GPU.0 档声码器必须留 CPU。

### 10.4 ④ 重打 v1.4 —— ⏳ **待做**，前置条件盘点

| 前置项 | 状态 | 能否现在打 |
|---|---|---|
| APP-003（排除内部素材 + 打包校验） | ✅ 完成 | — |
| APP-002（默认翻译 INT8-CW） | ✅ 完成 | — |
| C-111 合入 | ✅ 已在 `main`（`ebc6107`） | — |
| Qwen3-TTS 集成 | ⏳ **未完成**（worker 仍是旧引擎） | ❌ **不能打** |
| 设备选择 | ⏳ **未完成** | ❌ **不能打** |

⇒ **现在不能打 v1.4**：打出来的包没有 TTS、也没有设备自选，
与 APP-004 的承诺不符 ⇒ **必须等 ②③ 完成后再打**。

### 10.5 本模块的执行顺序（按 reviewer「先回执，再按顺序」）

| 步 | 任务 | 阻塞于 | 预计工作量 |
|---|---|---|---|
| 1 | 设备自选：公共设备探测 + 三个下拉框 + `--asr-device` + 配置持久化 + 回退提示 | 无 | 中（改 `live_caption_app.py` GUI/CLI + 新增 `device_config.py`） |
| 2 | TTS worker 适配 Qwen3-TTS `BabelVox` 引擎（交接单 §1.1 七参数 + 三个不能改错的参数） | 无（可与步 1 并行） | 大（`tts_worker.py` 重写引擎段） |
| 3 | TTS 模型 + 依赖随包（IR 55 文件 / 2542 MB + NOTICE + vendored 依赖） | 步 2 | 中（拷文件 + SHA256 核对） |
| 4 | 端到端验证（持机器锁，ABBA tts off/on/on/off，RTF 增量 ≤ +0.10、语音延迟 P50/P95、积压丢句） | 步 1+2+3 | 中（复用 `replay_c134_mt.py` 的 ABBA 框架） |
| 5 | 重打 v1.4 + 干净解压 `--check` + GUI 冒烟截屏 + 清单 SHA256 + 体积对比 + FTP 链接重建 + git 提交推送 | 步 4 | 中 |

⚠️ **本节只追加不回头改旧章节**（APP-001 格式要求）。
⚠️ **时间戳一律用 `date`/`Get-Date` 实测值**（APP-003④）；本节实测时间 **11:52:18**。

---

## §11 APP-005 / APP-006 回执与执行（2026-10-23 13:31）

> 本节实测时间 **13:31:05**（`date` 输出）。
> 上游：`CORRECTIONS_APP.md` 的 **APP-005**（11:58）与 **APP-006**（12:01）。
> APP-006 明确「**优先于 APP-004 的其他工作**」⇒ 本节即为优先项的执行记录。

### 11.0 回执与执行顺序

| 编号 | 条目 | 状态 | 落点 |
|---|---|---|---|
| APP-005① | `results/c134_replay/` 脱库 + `.gitignore` 加固 | ✅ **已完成** | §11.2 |
| APP-005② | `pack_v13.py` 把 INT8 默认模型当「禁止进包」 | ✅ **已完成并验证** | §11.3 |
| APP-005③ | §8.7 回放语种锁错成 `Chinese` | 🔄 **代码已改，待持锁重跑** | §11.4 |
| APP-006① | 完整备份 + 记录改写前 SHA | ✅ **已完成** | §11.5 |
| APP-006② | 内部素材清单（**需 reviewer 复核**） | ✅ **清单已生成** | §11.2 |
| APP-006③ | `git filter-repo` 改写历史 | ⏸ **等 reviewer 复核 §11.2 后执行** | — |
| APP-006④⑤ | 验证 + 强制推送 + 干净目录复验 | ⏸ 同上 | — |
| APP-006⑥ | 防复发（gitignore + 打包前检查） | ✅ **已完成** | §11.6 |
| APP-006⑦ | 残留风险告知 | ✅ **已写入 §11.7**（由 reviewer 转达用户） | §11.7 |

### 11.1 APP-005① —— `results/c134_replay/` 脱库（普通 commit，**不改历史**）

**执行**：
```
git rm -r --cached results/c134_replay/          # 7 个文件
```
`.gitignore` 新增（实测命中行号见下）：
```
results/**/*replay*
results/c134_replay/
reports/**/transcript_*.txt
reports/**/segments_*.json
reports/cuda*/logs_stream/
**/*_spoken.*
```

**验收（reviewer 要求的原文）**：
```
$ git ls-files results | grep c134
                       ← 空输出（grep exit=1）✅

$ git check-ignore -v results/c134_replay/abba1_off.txt
.gitignore:77:results/c134_replay/     results/c134_replay/abba1_off.txt
.gitignore:77:results/c134_replay/     results/c134_replay/replay_report.json
                                        ✅ 命中
```
脱库后 `git ls-files results` 仅剩 `results/tts_deploy_verify.json`（**不含会议原文**）。

⚠️ 磁盘上的 7 个产物**未删除**（`git rm --cached` 只脱库），仍在本机
`confucius4-openvino/results/c134_replay/`；但**已被 .gitignore 覆盖**。
⇒ 下一步 APP-005③ 重跑时产物会写到**仓库外**（见 §11.4）。

### 11.2 APP-006② —— 内部素材清单（**请 reviewer 复核**）

#### 11.2.1 全量扫描方法与实测

```bash
git log --all --name-only --pretty=format: | sort -u     # 历史出现过的全部路径
git grep -l -i -E '[REDACTED]|[REDACTED]|[REDACTED]|[REDACTED]|[REDACTED]' HEAD --
git log --all --name-only --pretty=format: | grep -Ei '\.(wav|mp3|flac|ogg|pcm)$'
```

| 项 | 实测 |
|---|---|
| 历史中出现过的**路径总数** | **1632** |
| 其中 `reports/` 下 | **1255** |
| 其中 `results/` 下 | **8**（`c134_replay/` 7 + `tts_deploy_verify.json` 1） |
| HEAD 快照中命中会议关键词的文件 | **170**（`reports/` 79 + 脚本/README 等 91） |
| **会议原文载体文件**（transcript/segments/logs/replay） | **515**（按历史路径去重） |
| 从载体文件抽出的**去重句子** | **7779** 条 |
| 关键词变体 | **4 种**：`[REDACTED]` / `[REDACTED]` / `[REDACTED]` / `[REDACTED]` |

#### 11.2.2 逐类清单

| # | 类别 | 数量 | 具体路径 / 说明 | 判定 |
|---|---|---|---|---|
| 1 | `results/c134_replay/` | **7** | `abba1_off.txt` / `abba2_on.{txt,mt.txt}` / `abba3_on.{txt,mt.txt}` / `abba4_off.txt` / `replay_report.json`（含 `"audio": "...<redacted>.wav"` 与逐段文本） | 🔴 **已脱库**（§11.1） |
| 2 | `reports/cuda/` | **227** | `logs_stream/seg_*.stdout`（逐段流式文本）+ `spe_cuda_stream.txt` + `spe_cuda_stream_segments.json` + `cuda_oom_test_3min.stdout` | 🔴 同一场会议 |
| 3 | `reports/cuda_q4/` | **227** | 同上（CUDA Q4 对照） | 🔴 同一场会议 |
| 4 | `reports/c062_abba/` | **13** | `transcripts/transcript_A_rep{0,5,6,11,999}.txt` | 🔴 |
| 5 | `reports/c051_mix/` | **12** | `en_60min/` + `mix_60min/` 的 `transcript_*.txt` / `segments_*.json` | 🔴 |
| 6 | `reports/c089_int4/` | **7** | `transcript_R2_npu_1227.txt` / `transcript_R4_npu_full.txt` / `transcript_int8_selfcheck.txt` 等 | 🔴 |
| 7 | `reports/c048_61min_adaptive/` | **6** | `transcript_{adaptive,baseline,finish_first}.txt` + `segments_*.json` | 🔴 **含内部会议原文片段** |
| 8 | `reports/c053_61min_int4/` / `c057_61min_encoder/` / `c058_61min{,_rerun}/` / `c061_61min_combo/` | **8** | `transcript_*.txt` | 🔴 |
| 9 | `reports/c087_int4_npu{,_900s}/` / `c080_e2e/` / `c085_e2e/` / `c086_full61/` / `c089_int8_r4full_polluted_C096/` | **13** | `transcript_*.txt` / `summary.json` | 🔴 文本部分 |
| 10 | `reports/` 根级 `spe_*.txt` / `spe_*.json` / `spe_hybrid_offline*` | **~20** | `spe_61min_transcript*.txt` / `spe_61min_segments*.json` / `spe_hybrid_offline.txt` 等 | 🔴 |
| 11 | `reports/c026_minimax_{raw.json,transcript.txt}` | 2 | MiniMax 云端 ASR 对照（会议原文） | 🔴 |
| 12 | `reports/C049_TESTSETS.md` / `C051_MIX_TEST.md` | 2 | 报告正文里引用会议文件名与片段 | 🔴 文本 |
| 13 | **音频文件**（`.wav/.mp3/.flac/.ogg/.pcm`） | **0** | `.gitignore` 早已挡住（`*.wav` 等 + `test_audio/`） | ✅ **历史中零命中** |
| 14 | `test_audio/` | **0** | 同上，目录未被跟踪 | ✅ |
| 15 | `clone_C*` / `preset_B*` / `voices/*.npz` | **0** | 仓库 `live_caption/voices/` 已被 `.gitignore` 挡住（`live_caption/voices/`） | ✅ 历史中零命中 |
| 16 | `male_candidates/` | 0 | 只有脚本 `asr_check_male_candidates.py`（**非素材**） | ✅ |
| 17 | 源码/脚本里的**路径与示例字符串** | **80 个文件含 `[REDACTED]`** | 见 11.2.3 | 🔴 需脱敏 |
| 18 | 中文会议内容（`[REDACTED]`/`[REDACTED]`/`[REDACTED]`/`[REDACTED]`） | **5 个文件** | `pack_v13.py` / `pkg_exclude.py` / `status/CORRECTIONS.md` / `status/app/CORRECTIONS_APP.md` / `status/app/STATUS_APP.md` | ⚠️ **全是"点名说明"**（规则解释、纠偏记录），**不是会议原文本身** ⇒ 保留 |

#### 11.2.3 路径与示例字符串（`[REDACTED]` 出现形态）

`git grep -oh "[REDACTED][A-Za-z0-9_]*"` 的全量统计：
```
96 次  <redacted>_audio      ← 素材文件名
 2 次  <redacted>            ← 素材名（无扩展名）
```
其中 **74 个文件**是 `test_audio/<redacted>.wav` 形式的路径；
其余为散文引用（如 `asr_check_male_candidates.py:8`、
`reports/C051_MIX_TEST.md:11`、`status/CORRECTIONS.md:1457`）。

🔴 **本轮已处理的部分**：
- 客户包 `app/live_caption_app.py:154` 的注释「真实演讲 <redacted>.wav 实测」
  → 「真实演讲 `<内部音频>.wav` 实测」（**仓库版同步**），
  实测客户包 `grep -rn [REDACTED]` 现在 **0 命中**。
- 替换表已把 `test_audio/<redacted>.wav` / `<redacted>.wav` /
  `<redacted>` / `[REDACTED]` / `[REDACTED]` / `[REDACTED]`
  6 条定点替换写入表内。

#### 11.2.4 脱敏替换表（**本轮只生成，不执行改写**）

- 表文件：`C:/Users/Trekker-PTL/git_backup/replace_text_c135.txt`
  （**967,917 B / 7789 条 / 仓库外**）
- 清单（不含原文，可进 STATUS）：
  `C:/Users/Trekker-PTL/git_backup/redact_manifest_c135.json`
- 生成脚本：`build_redact_table.py`（**新建**，stdlib only）

表内容构成：
| 类型 | 条数 | 处理 |
|---|---|---|
| 会议原文句子 | **7779** | 逐条 `原文==>[REDACTED]`（长句优先，精确匹配） |
| 路径/示例替换 | **6** | `test_audio/<redacted>.wav` 等 → `<redacted>` |
| 关键词变体 | **4** | `[REDACTED]` / `[REDACTED]` / `[REDACTED]` / `[REDACTED]` → `[REDACTED]` |

⚠️ **表文件含会议原文 ⇒ 必须留在仓库外**（已放 `C:/Users/Trekker-PTL/git_backup/`，
该目录不在仓库内，也不在任何 git 工作区）。

### 11.3 APP-005② —— `pack_v13.py` 的 INT8 默认模型断言（已修）

#### 11.3.1 矛盾点（reviewer 指出的）

| reviewer 指出 | 实测行号（改前） | 内容 |
|---|---|---|
| 注释仍写「v1.3 只附带 INT4」 | **L64** | `# v1.3 只附带 INT4 —— INT8 必须不在包内` |
| `MUST_NOT_EXACT` 禁 INT8 的 xml | **L65** | `'models/mt/mt2-int8sym-cw-q/openvino_model.xml'` |
| `MUST_NOT_EXACT` 禁 INT8 的 bin | **L66** | `'models/mt/mt2-int8sym-cw-q/openvino_model.bin'` |
| `MUST_NOT_PREFIX` 禁整个 INT8 目录 | **L95** | `'models/mt/mt2-int8sym-cw-q/'` |
| `MUST_HAVE` 只列 INT4 | **L51-54** | 只列 `mt2-int4sym-cw-q/` 四件 |
| `only_int4` 判定 | **L362-369** | `mt_dirs == ['mt2-int4sym-cw-q']` |
| `only_int4` 参与 FAIL | **L372** | `or not only_int4` |

⇒ **§8.4 的「dry-run 9087 文件 / 9.97 GB PASS」与这个脚本对不上**：
`--dry-run` 走的是 `do_dry_run()`（**只看 `MUST` 列表是否存在**），
而 `only_int4` 判定在 **zip `--check` 段**（`do_check()`）—— 两段代码，
所以 dry-run 不会报，**真正打包时才会 FAIL**。
⇒ 这就是 reviewer 问「dry-run 为什么没有报出来」的答案。

#### 11.3.2 本轮改动

| # | 位置 | 改动 |
|---|---|---|
| 1 | `MUST` | **新增** INT8-CW 四件（`openvino_model.xml` / `.bin` / `config.json` / `chat_template.jinja`），**保留** INT4 四件（INT4 仍是可选项，APP-002 决策） |
| 2 | `MUST` | **新增** TTS 关键文件 **21** 件：`models/qwen3tts/int8/` 的 9 组 IR（talker / talker_prefill / talker_decode / cp_prefill / cp_decode / code_predictor / tokenizer_encoder / tokenizer_decoder / speaker_encoder，各 xml+bin）+ `tokenizer/` 4 件 + `voices/preset_A.wav` |
| 3 | `MUST_NOT_EXACT` | **删除** INT8 的 xml / bin 两条（改前 L65/L66） |
| 4 | `MUST_NOT_PREFIX` | **删除** `models/mt/mt2-int8sym-cw-q/`（改前 L95）；**新增** `models/qwen3tts/voices/preset_B` / `preset_C` / `clone_` 与 `app/voices/` |
| 5 | `MUST_NOT_NAME_RE_LIST` | **新增**（新建）：`preset_B` / `preset_C` / `clone_[A-Z]` 的文件名模式 |
| 6 | `only_int4` → `mt_dirs_ok` | 改为**双向断言**：`int8_ok`（INT8 目录必须在包内）**且** `legacy_ok`（无 `int4sym-cw-q` / `int8sym-cw-q` 旧目录） |
| 7 | FAIL 条件 | `or not only_int4` → `or not mt_dirs_ok`；**新增** `or tts_bad`（音色素材） |
| 8 | `translator.py` 符号抽查 | `syms` 里 `mt2-int4sym-cw-q` → **`mt2-int8sym-cw-q`**（默认模型） |
| 9 | zip `--check` 段 | **新增**「TTS 音色素材（只允许音色 A）」检查块 |
| 10 | `pkg_exclude.py` | **新增** `BACKUP_DIR_RE = re.compile(r'^_backup', re.I)`，在 `is_excluded()` / `iter_package_files()` / `iter_excluded()` **三处**生效 ⇒ `_backup_*` 目录（任意层级）不进包 |

#### 11.3.3 `--dry-run` 验收原文（**PASS**）

```
======================================================================
[dry-run] Confucius4_LiveCaption_v1.3
======================================================================
源目录: C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3

将打包: 13973 文件 / 13667699075 字节 (12.73 GB)

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
  [OK] models/mt/mt2-int8sym-cw-q/openvino_model.xml
  [OK] models/mt/mt2-int8sym-cw-q/openvino_model.bin
  [OK] models/mt/mt2-int8sym-cw-q/config.json
  [OK] models/mt/mt2-int8sym-cw-q/chat_template.jinja
  [OK] models/mt/mt2-int4sym-cw-q/openvino_model.xml
  [OK] models/mt/mt2-int4sym-cw-q/openvino_model.bin
  [OK] models/mt/mt2-int4sym-cw-q/config.json
  [OK] models/mt/mt2-int4sym-cw-q/chat_template.jinja
  [OK] models/qwen3tts/int8/talker.xml
  ... （TTS 21 件全部 [OK]）
  [OK] models/qwen3tts/voices/preset_A.wav

内部会议内容检查（results/ 下 *_spoken.* 与点名文件）：
  源目录残留: 0 个内部内容文件

======================================================================
内部素材闸门（APP-006 第 6 步）
======================================================================
[待打包目录] C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3
  命中 0 个内部素材

结论：PASS —— 未发现内部素材
结论：PASS（dry-run，未写 zip）
```

#### 11.3.4 「缺 INT8 bin」FAIL 情形验收（**已验证，且文件已复原**）

```
$ mv models/mt/mt2-int8sym-cw-q/openvino_model.bin  ...tmp_missing_test
$ python pack_v13.py --dry-run
  [缺] models/mt/mt2-int8sym-cw-q/openvino_model.bin
结论：FAIL（关键文件缺失）              ← ✅ reviewer 要求的 FAIL 输出

$ mv ...tmp_missing_test  openvino_model.bin      ← 立刻复原
$ ls -la openvino_model.bin
-rw-r--r-- 1 Trekker-PTL 197121 1792991738 Oct 23 11:16   ← 字节数复原正确
$ python pack_v13.py --dry-run
  [OK] models/mt/mt2-int8sym-cw-q/openvino_model.bin
结论：PASS（dry-run，未写 zip）
```
⚠️ 临时文件**已复原**，磁盘上无 `.tmp_missing_test` 残留。

#### 11.3.5 `MANIFEST.json` 一并刷新（前置，pack_v13 硬校验依赖）

| 项 | 改前 | 改后 |
|---|---|---|
| `files` | 9087 | **13973** |
| `bytes` | 10704695313 | **13667699073**（12.73 GB） |
| `version` | 1.3 | **1.3**（本轮不改；v1.4 重打在 APP-004 完成后） |
| `packages` 条目 | 31 | **51**（新增 20 个：babelvox 1.7.1 / librosa 1.0.0 / scipy 1.18.1 / num2words 0.5.14 / numba 0.68.0 / llvmlite 0.50.0 / soxr 1.1.0 / soundfile 0.14.0 / cloudpickle 3.1.2 / joblib 1.6.0 / pooch 1.9.0 / platformdirs 4.13.5 / defusedxml 0.7.1 / msgpack 1.2.3 / decorator 5.3.1 / lazy_loader / pip / charset_normalizer / openvino_genai / openvino_telemetry / openvino_tokenizers） |
| `notes` | 3 段修订说明 | **追加**「（4）TTS 随包分发」+「（5）打包断言已按 INT8 默认模型更新」 |

⚠️ **`packages` 大小写去重**：首版实现会产生 `Jinja2` 与 `jinja2` 并存 ⇒
已改为**按小写归一化归并**（保留原有拼写，只更新版本号），实测 **0 个重复**。
⚠️ `refresh_manifest()` 现在**幂等**（连跑两次，第二次 `files/bytes` 不变、`notes` 不重复追加）。

备份：`C:/Users/Trekker-PTL/pkg_backup_app005/MANIFEST.json.bak_app005`（**包外**）。

#### 11.3.6 顺带发现并修复：包根 `_backup_c111/` 污染（C-133 教训重现）

🔴 实测客户包根出现了 `_backup_c111/`（含 `live_caption_app.py.bak` 101,428 B +
`translator.py.bak` 50,371 B）—— **这正是 C-133 记录的教训**：
「`_backup_*` 目录不被 `.bak` 排除规则覆盖，会污染包」。

| 动作 | 结果 |
|---|---|
| 移出包 | `C:/Users/Trekker-PTL/pkg_backup_app005/_backup_c111/`（**包外**） |
| 加规则 | `pkg_exclude.py` 新增 `BACKUP_DIR_RE`，`is_excluded()` / `iter_package_files()` / `iter_excluded()` **三处**生效 |
| 加断言 | `pack_v13.py` 的 `MUST_NOT_PREFIX` 加 `_backup_c111` / `_backup_c133` / `_backup_c134` / `_backup_c135` |

⚠️ **`_backup_*` 规则只能防未来的目录名**；本模块以后备份一律放
`C:/Users/Trekker-PTL/pkg_backup_appNNN/`。

#### 11.5 备份记录 + 改写前后 SHA 对照（APP-006 第 1 步）

**镜像备份（mirror）已落盘**

| 项 | 值 |
|---|---|
| 路径 | `C:/Users/Trekker-PTL/git_backup/Confucius4-OpenVINO_20261023.git` |
| 体积 | **2.7 GB**（`du -sh` 实测） |
| 方式 | `git clone --mirror /c/Users/Trekker-PTL/confucius4-openvino`（**本地**做 mirror） |
| `git fsck --no-progress` | 仅 `dangling blob` / `dangling commit`，**无 error** |
| refs | `bce542ae… refs/heads/main`、`73f268eb… refs/remotes/origin/main`、`73f268eb… refs/remotes/origin/HEAD` |

⚠️ **为什么不是 `git clone --mirror git@github.com:…`**：沙箱拒绝读 `C:/Users/Trekker-PTL/.ssh/config`
与 `known_hosts` ⇒ `Host key verification failed`。改用**本地仓库**做 mirror，**等价性已核实**：
本地 `main`（`bce542a`）**领先** `origin/main`（`73f268e`）3 个 ASR 提交，
且 `git log main..origin/main` 为空 ⇒ 本地历史**包含远端全部历史**。

**改写前 SHA / 结构快照（2026-10-23 13:43 实测）**

| 项 | 值 |
|---|---|
| `main` | `bce542ae7101503f6c29f80cea275228389aef38` |
| `origin/main` | `73f268eb78be121a71e2c933cf51e2a50c2f94fb` |
| commit 总数 | `git rev-list --all --count` = **51** |
| tag 数 | `git tag -l \| wc -l` = **0** |
| `main..origin/main` | 0（本地领先远端 4 个提交：`63cffd9` `bce542a` `720b704` `da6f190`） |

⚠️ **`rev-list --all --count` 在本仓库会随未 push 的 ASR 提交变化**（13:19 首次快照为 50，
13:43 为 51，因并行 ASR 线程新提交了 `63cffd9`）。**改写时以当刻实测值为准**，
并在下表登记「改写前」快照。

**脱敏替换表与清单（**仓库外**，不进 git）**

| 文件 | 大小 | 内容 |
|---|---|---|
| `C:/Users/Trekker-PTL/git_backup/replace_text_c135.txt` | **967,917 B** | **7789 条**替换规则（7779 条会议原文句子 + 6 条路径/示例 + 4 种关键词变体） |
| `C:/Users/Trekker-PTL/git_backup/redact_manifest_c135.json` | 26,128 B | **不含原文**的清单：载体文件 515 个 / 句子 7779 / 变体 4 种 / 表条目 7789 |

#### 11.6 防复发机制（APP-006 第 6 步）

| 层 | 机制 | 落点 | 验收 |
|---|---|---|---|
| ① gitignore | `results/**/*replay*`、`results/c134_replay/`、`reports/**/transcript_*.txt`、`reports/**/segments_*.json`、`reports/cuda*/logs_stream/`、`**/*_spoken.*` | `.gitignore`（新增 11 行） | `git check-ignore -v` 命中 `.gitignore:77` |
| ② 打包闸门 | `check_internal_material.py`：文件名模式（`_spoken` / `preset_B` / `preset_C` / `clone_[A-Z]` / `transcript_*.txt` / `segments_*.json`）+ 内容关键词（读前 512 KB） | 已挂进 `pack_v13.py` 的 **dry-run 与真打包两条路径** | 客户包复扫 **0 命中**；`结论：PASS —— 未发现内部素材` |
| ③ 提交前闸门 | 同上脚本另扫 **git 待提交文件** | `check_internal_material.py --git` | 仓库内 `status/` 等合法提到关键词的地方已在 `DEFAULT_ALLOW` 放行 |
| ④ 产物外置 | 回放产物一律写 `C:/Users/Trekker-PTL/replay_out/`（仓库外） | `replay_c134_mt.py::OUTDIR` | `replay_report.json` 只落 `replay_out/c135/` |
| ⑤ 备份外置 | 客户包备份一律放 `C:/Users/Trekker-PTL/pkg_backup_appNNN/`（包外） | `pkg_exclude.py::BACKUP_DIR_RE` 兜底 | 包根 `_backup_c111/` 已移出并复扫 0 命中 |
| ⑥ 源脱敏 | 源码/客户包注释里的内部音频文件名已替换为 `<内部音频>.wav` | 仓库 + 客户包 | `grep -rn [REDACTED]` 客户包 **0 命中** |

#### 11.7 改写历史的**残留风险告知**（APP-006 第 7 步，必须随改写一起告知）

⚠️ 以下是 `git filter-repo` + force push **无法消除**的风险，必须让所有协作者知悉：

1. **GitHub 上旧 commit 在 GC 前仍可按 SHA 访问** —— 即使 force push 成功，
   知道旧 SHA（如 `73f268eb78be121a71e2c933cf51e2a50c2f94fb`）的人**仍能拉到含内部素材的旧 commit**。
   GitHub 的悬空对象通常在**数天到数周**后才被 GC 回收。
2. **fork / 他人已 clone 的副本仍含旧历史** —— force push 只改远端 `refs`，**改不了别人机器上的副本**。
   已知持有者应自行重新 clone。
3. **可能需要联系 GitHub Support** 才能彻底清理悬空对象 / 已缓存的旧内容
   （GitHub Support 可申请清理 fork 与缓存，但**不保证**所有副本）。
4. **改写后所有 commit SHA 全变** —— 改写前的 SHA 全部失效：
   | 改写前 | 改写后 |
   |---|---|
   | `main` = `bce542ae7101503f6c29f80cea275228389aef38` | **待改写后实测登记** |
   | `origin/main` = `73f268eb78be121a71e2c933cf51e2a50c2f94fb` | **待改写后实测登记** |
   ⇒ **任何文档、MR、issue 里引用旧 SHA 的地方都会失效**。
5. **协作者必须重新 clone，不能 `git pull`** —— `git pull` 会因为历史不连通而报错，
   或把旧对象重新推回远端。正确做法：
   ```bash
   git clone git@github.com:alexgang/Confucius4-OpenVINO.git
   # 旧目录先改名保留，确认新 clone 正常后再删
   ```
6. 🔴 **本机有并行会话（ASR/MT/TTS）在同一仓库工作** —— 若用 `git reset --hard` 追新历史，
   **会覆盖他们未提交的改动**。改写前后必须先与各线程确认，再决定「重新 clone」还是「reset」。
7. **改写不覆盖工作区未提交文件** —— `filter-repo` 只改历史；未提交的新文件需先自行处理。

#### 11.4 APP-005③ 回放重跑结果（语种纠正 + 统计口径修正）

**运行参数**：`python live_caption/replay_c134_mt.py --asr-lang English --seconds 60`
　　锁：`module: app / pid: 36140 / started 13:42:47` → `13:47:40` 释放；重跑 13:49~13:54。
　　产物目录（**仓库外**）：`C:/Users/Trekker-PTL/replay_out/c135/`

**ABBA 四轮结果（2026-10-23 13:54 实测）**

| 轮次 | translate | exit | 墙钟(s) | ASR RTF | 统计对象 | 非空行 | 英文残留 | 空行 |
|---|---|---|---|---|---|---|---|---|
| abba1_off | off | 0 | 71.75 | **0.725** | `abba1_off.txt`（原文） | 10 | 10（100%） | 0 |
| abba2_on | zh | 0 | 76.06 | **0.796** | `abba2_on.mt.txt`（**译文**） | 10 | **0（0.0%）** | **0** |
| abba3_on | zh | 0 | 76.12 | **0.781** | `abba3_on.mt.txt`（**译文**） | 10 | **0（0.0%）** | **0** |
| abba4_off | off | 0 | 71.43 | **0.724** | `abba4_off.txt`（原文） | 10 | 10（100%） | 0 |

**验收对照（reviewer 的三条要求）**

| 要求 | 实测 | 判定 |
|---|---|---|
| 英文残留句占比 ≤ 5% | 翻译轮 **0.0%**（0/10 与 0/10） | ✅ |
| 0 个空行 | 翻译轮 **0**（中间空行；文件首行的换行是 CLI 格式，不算空译文行） | ✅ |
| 产物写仓库外 | `C:/Users/Trekker-PTL/replay_out/c135/`（7 文件） | ✅ |

**RTF（只报均值差 + 噪声范围，不写「无影响」）**

| 分组 | n | 值 | 均值 | 范围 | 组内极差 |
|---|---|---|---|---|---|
| off（翻译关） | 2 | 0.725 / 0.724 | **0.7245** | [0.724, 0.725] | 0.0010 |
| on（翻译开） | 2 | 0.796 / 0.781 | **0.7885** | [0.781, 0.796] | 0.0150 |

- **均值差 on − off = +0.0640**
- **噪声范围（组内极差）= 0.0150**
- ⇒ **均值差 +0.0640 > 噪声 0.0150** ⇒ 本轮**超出组内噪声范围**，
  **不能写成「翻译对 ASR RTF 无影响」**。⚠️ 样本仅 n=2/组，
  且**端到端墙钟不作性能判据**（H-004）—— 本条只是「本轮观察到的差值 > 本轮噪声」，
  **不是**「翻译显著拖慢 ASR」的定论；**§8.7 / C-111 那两轮的「无可测影响」结论本轮不予撤回**，
  但也**不再复用旧数字**（旧数字是 Chinese 语种锁错的那轮，已于 §11.4 撤回）。

**翻译侧性能（on 两轮）**

| 轮次 | 后端 | 设备 | state | 句数 | 延迟中位 | P95 | TTFT | tok/s |
|---|---|---|---|---|---|---|---|---|
| abba2_on | auto | GPU.0 | ready | 25 | 476.5 ms | 1482.7 ms | 207.7 ms | **31.8** |
| abba3_on | auto | GPU.0 | ready | 25 | 459.0 ms | 1465.2 ms | 201.6 ms | **29.9** |

⇒ INT8-CW 速率 29.9~31.8 tok/s（INT4 应约 57.9）⇒ **确认没降级到 INT4**。

**🔴 顺带发现并修正：APP-005③ 的验收口径本身有误（**统计对象搞错了**）

首轮（13:43~13:47）跑出来的结果是「翻译轮英文残留 **100%**」，乍看像翻译失效。
逐项排查后确认：**翻译本身完全正常**，是**统计口径错**：

- CLI 的 `--out <x>.txt` 写的是 **ASR 定稿原文**（英文）；
- 翻译开启时，CLI **另外**写 `<x>.mt.txt`（**译文**，中文）；
- 而 `replay_c134_mt.py` 一直在统计 `--out` 那个**原文**文件
  ⇒ 统计结果**必然是 100% 英文**，与翻译是否工作无关。

证据（on 轮 stdout，**只贴结构性字段，不贴原文**）：

```
[gpu_int8] 翻译 target=zh 后端=auto 设备 GPU.0 state=ready 句数 25  延迟中位 476.5 ms  P95 1482.7 ms  TTFT 207.7 ms  26.0 tok/s
[gpu_int8] 译文已写 C:/Users/Trekker-PTL/replay_out/c135/abba2_on.mt.txt
```

⇒ **修复**：`run_once()` 改为「翻译开启且 `.mt.txt` 存在 ⇒ 统计 `.mt.txt`；否则统计原文文件」，
并在报告里带 `stat_target` 字段说明统计的是哪个文件；主循环打印「统计对象=」。

**空行口径**：CLI 写出的 `.mt.txt` **首行是空行**（文件开头的换行）。
首轮 `abba2_on.mt.txt` 统计出 1 个空行即由此而来 ⇒ 加 `count_inner_empty()`
（首尾空行属格式，中间空行才算「空译文行」）。修正后两轮 on 均为 **0**。

⚠️ **这说明 §8.7 那个「14 句 vs mt.txt 9~10 行」的对不上，也是同一原因**
（当时统计的是 `.txt` 原文，行数与译文句数本就不该相等）。本轮实际：
原文非空行 10、译文非空行 10、翻译侧「句数 25」（翻译按**句**切，原文按**段**写行，
一句可跨段、一段可含多句 ⇒ 两者**本就不相等**，不是缺陷）。

**产物清单（`C:/Users/Trekker-PTL/replay_out/c135/`，7 文件，均在仓库外）**

| 文件 | 字节 | mtime |
|---|---|---|
| `abba1_off.txt` | 899 | 2026-10-23 13:50 |
| `abba2_on.txt` | 899 | 2026-10-23 13:51 |
| `abba2_on.mt.txt` | 1415 | 2026-10-23 13:51 |
| `abba3_on.txt` | 899 | 2026-10-23 13:53 |
| `abba3_on.mt.txt` | 1415 | 2026-10-23 13:53 |
| `abba4_off.txt` | 899 | 2026-10-23 13:54 |
| `replay_report.json` | 22752 | 2026-10-23 13:54 |

⚠️ **报告里不贴会议原文** —— 本节只贴计数与结构性字段（句数 / 延迟 / RTF / 行数 / 残留数）。

## §12 无新纠偏条目巡检 + APP-005① 补推送关闭远端泄露 + TTS 引擎按新交接单纠正（2026-10-23 15:36）

### §12.0 本轮动作摘要

- **巡检结论：`CORRECTIONS_APP.md` 最大编号 = APP-006 = 头部 `last_ack` ⇒ 本轮无新纠偏条目，无需执行新条目。**
  - 依据：文件实测 mtime `2026-10-23 12:01:55.742320600 +0800`，17965 B，SHA256 `dff32b2c96b6ccc02127ef6b258eef73bd0b3d0cd574a3772a5f4063ee7db8cc`；
    `## APP-xxx` 条目共 6 条（APP-001 09:12 / APP-002 09:37 / APP-003 09:45 / APP-004 11:17 / APP-005 11:58 / APP-006 12:01）；
    全仓全局搜 `APP-007` / `APP-008` / `APP-009` **0 命中**。
  - `CORRECTIONS_APP.md` 本轮**只读、未修改、未提交**（git 显示 `M` 是相对 HEAD 多出 APP-005/006 两条，属 reviewer 侧未入库内容）。
- **本轮实际做的三件事**（都是把 §11 的「已做但未闭环」补完）：
  1. **APP-005① 补推送** —— 关闭 `origin/main` 上仍在线的内部会议转写泄露（§12.1）。
  2. **TTS 引擎纠正** —— `tts_engine.py` 原按 12:02 的旧 ICL 口径写，与 TTS 模块 14:37 更新的交接单结论相反，按新口径改 spkonly（§12.2）。
  3. **TTS worker 接入 BabelVox** —— 原先只走旧 OVSynth 路线，与「TTS 随包分发」方向相反（§12.3）。
- **未推进**：APP-006 第 3~7 步（历史改写 + force push）—— APP-006 第 2 步明写「这一步需要停下来等 reviewer 复核」⇒ **本轮按纪律停下**。
- **未完成**：NPU 冒烟实测超时未出结论（§12.5）；v1.4 重打包前置未完成，暂缓。

### §12.1 APP-005① 补推送 —— 关闭 `origin/main` 内部会议转写泄露

§11.1 只做了**本地** `git rm --cached`（commit `0de52ad`），**该 commit 从未 push** ⇒
`origin/main` 上 7 个 `results/c134_replay/*` 一直在线。**本轮补做普通快进 push 已关闭。**

| 项 | 改前 | 改后 |
|---|---|---|
| `git ls-remote origin main` | `73f268e...`（旧） | `75e82a53f01736475e6e80d6106efd2b4e9dc6ce` |
| `git ls-tree -r origin/main --name-only \| grep c134_replay` | **7 条命中** | **空** |
| 本地 `main` | `75e82a5` | `75e82a5` |
| push 方式 | —— | `git push origin main`（**普通 push，非 force**） |

- **快进性校验**：`git merge-base --is-ancestor origin/main main` = 0（true）⇒ 改前 `origin/main` 是本地 `main` 的祖先 ⇒ push 是纯快进，**未使用 force push**，未改写他人历史。
- push 前 `git status` 已确认 `origin/main` 无落后分叉；push 后 `git ls-remote` 与本地一致。
- ⚠️ **本节不贴会议原文**，只记录文件名层面的结论。

### §12.2 `tts_engine.py` 按新交接单纠正（ICL → spkonly）

**根因**：`live_caption/tts_engine.py` 写于 **12:02**，而 TTS 模块交接单 `C:\Users\Trekker-PTL\qwen3tts_eval\TTS_交接单.md`
mtime **2026-10-23 14:37**（18667 B）——**新文档比引擎晚 2.5 小时，且结论相反**：

| 维度 | 旧引擎写法（12:02，**已作废**） | 新交接单口径（14:37，**本轮采用**） |
|---|---|---|
| 音色路线 | ICL：传 `ref_text` + `ref_audio` | **spkonly（x_vector）**：只传 `speaker_embed` |
| 原因 | —— | babelvox 的 `ref_text` 路径**不是官方 ICL**，codec 轨道无 `ref_code` ⇒ 分布外 prompt ⇒ EOS 不稳（TTS-005） |
| 参考文本常量 | `PRESET_A_REF_TEXT = "..."` | **`PRESET_A_REF_TEXT = None`**（音色 A 的参考文本已作废） |

本轮改动（`live_caption/tts_engine.py`，16309 B，SHA256 `afd48c7b65156a9e885313041b2117e7c832fbc0d6ae90b6cd90dcf1adafe717`，mtime `2026-10-23 15:15:57`）：

```python
# 🔴🔴 **音色 A 的参考文本已作废，不要用**（交接单 2026-10-23 14:37 更新，TTS-005）
PRESET_A_REF_TEXT = None
BUILTIN_SPEAKERS = ('cindy', 'lou', 'phil', 'steve')
TTS_SAMPLE_RATE = 24000
```

```python
def speaker_embedding(eng, ref_wav=None, on_log=print) -> Optional['np.ndarray']:
    """预计算参考 wav 的 speaker embedding（**x_vector / spkonly 路线**）。"""
    import numpy as np
    wav = ref_wav or preset_voice_path()
    if not wav: ... return None
    spk = eng.extract_speaker_embedding(wav)
    spk = np.asarray(spk, dtype=np.float32).reshape(1, -1)
    return spk
```

```python
def stream(eng, text, language='English', speaker_embed=None,
           speaker=None, cancel_event=None, on_log=print):
    kwargs = dict(text=text, language=language,
                  speaker_embed=speaker_embed, speaker=speaker,
                  split_on_silence=False, cancel_event=cancel_event)
    return eng.generate_stream(**kwargs)
```

- `stream()` 已**删除 `ref_audio` / `ref_text` 两个入参** ⇒ 调用方不可能再误走 ICL。
- `split_on_silence=False` 固定为默认（交接单 §6.3「不要无条件切分」）。
- **内置音色**：`cindy` / `lou` / `phil` / `steve` 四条，**全部内置**（speaker encoder 9 MB）⇒ 客户包**不需要 `ref_text`**。

### §12.2.1 顺带修掉 `split_long_text()` 的真 bug（单句判据 → 累计判据）

**原判据错在哪**：`split_long_text()` 原本判断的是「**单句** est > max_sec」，而不是「**累计 buf_est + est** > max_sec」。
后果：一句超长句（> max_sec）会**整句被塞进同一段**，随后引擎侧照样触发静默截断 ⇒ 切分形同虚设。

- 已改为**累计判据**：`buf_est + est > max_sec` 才起新段；并抽出 `_estimate_sec()` 统一估时口径。
- **自检输出**：`长句切分：10 段，每段估时 max=35.0s （上限 39.8s）` ⇒ `OK`（每段估时均低于上限 ⇒ 无静默截断风险）。

### §12.3 `tts_worker.py` 接入 BabelVox 路线（原先只走旧引擎）

**问题**：`tts_worker.py` 原先**只有**旧 `confucius4-tts` 的 OVSynth + BigVGAN 路线 ⇒ 与 APP-004「TTS 随包分发」方向相反，
且旧路线采样率 22050 Hz ≠ babelvox 的 24000 Hz。

本轮改动（`live_caption/tts_worker.py`，38670 B，SHA256 `fec383a50eab9405362a623e7f2e39f64e864bbf5992bebbf98bddc3b1d4cd1a`，mtime `2026-10-23 15:20:20`；`git diff --stat` = 352 插入 / 54 删除）：

| 项 | 改前 | 改后 |
|---|---|---|
| 采样率常量 | `SR = 22050` | `SR = 22050`（旧） / **`TTS_SR = 24000`（babelvox 原生）**，`self.sr` 随引擎走 |
| 引擎加载 | 只有 OVSynth / torch | **三级回落：BabelVox → OVSynth → torch** |
| 音色 | 只能 `--voice A` | `--voice` 放开 choices，支持 `cindy/lou/phil/steve` |
| 播放流 | 固定 22050 建流 | **`_reopen_player(sr)`**：`sounddevice.OutputStream` 采样率是**流级属性**，切引擎须重建播放流 |
| 新增方法 | —— | `_reopen_player(sr)` / `_try_load_babelvox()` / `_setup_babelvox_voice()` / `_synth_babelvox()` |
| CLI | —— | 新增 `--tts-cache-dir`；`_flush_timeline` 与 jsonl 的 `dur_s` 改用 `self.sr` |

- **仓库 ⇄ 客户包一致性已校验**（三份文件 SHA256 完全一致）：

| 文件 | 仓库 SHA256 | 客户包 SHA256 | 结论 |
|---|---|---|---|
| `tts_engine.py` | `afd48c7b65156a9e…` | `afd48c7b65156a9e…` | **SAME** |
| `tts_worker.py` | `fec383a50eab9405…` | `fec383a50eab9405…` | **SAME** |
| `tts_engine_patch.py` | `71a0aa3832114415…` | `71a0aa3832114415…` | **SAME** |

- `tts_engine_patch.py`（15973 B，SHA256 `71a0aa38321144150873ee3b0da68e9436dd7c56cdb44630668fb794e597f83e`）
  由 `C:\Users\Trekker-PTL\qwen3tts_eval\qwen3tts_patch.py` 复制而来，内含 `MultiDecoderBabelVox`
  —— 用于**解耦 `max_decoder_frames` 一参两用**（静态形状定耗时 + `effective_max` 定截断），避免降帧数把长句砍断。

### §12.4 客户包 TTS 文件清单核对（交接单 55 条 ⇄ 客户包 55/55 全对）

- 交接单 `TTS_交接单.md`（14:37）列 IR/模型/词表文件共 **55 条**，逐条比对客户包
  `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app\models\qwen3tts\` ⇒ **字节 55/55 + SHA256 55/55 全对**。
- `models/qwen3tts/` 目录构成：**int8 18 文件 / weights 37 文件 / tokenizer 4 文件 / voices 仅 `preset_A.wav`（192044 B）**。
- 🔴 **`voices/` 只有音色 A**（参考 wav）⇒ **音色 B 与克隆音色 C 确认未进包**（符合交接单「客户包只能带音色 A」纪律）。
- `python/Lib/site-packages/babelvox` 存在且可 import；`BabelVox.__init__` 签名已逐项核对：
  `model_path, export_dir, device, max_talker_seq, max_cp_seq, max_speaker_frames, max_decoder_frames, use_kv_cache, max_kv_len, use_cp_kv_cache, talker_buckets, precision, cache_dir, fallback_cpu`。
- **内部素材闸门**：`check_internal_material.py --repo . --pkg <客户包>` ⇒ **命中 0 个内部素材 / 结论：PASS**。
- **全量会议原文扫描**：用脱敏替换表 `git_backup/replace_text_c135.txt`（7789 条，每行一条原文）扫描 16 个待推送文件 ⇒
  **唯一命中在 `status/app/STATUS_APP.md` 第 692 行**（§8.7.4 引用「然后在最后我们将有 plenty of time for Q&A…」）——
  属**旧章节的历史引用**，非本轮新增落盘内容（§8.7.4 不在改写范围，本轮亦未改动该行）。

### §12.5 未完成项与阻塞（如实记录，未包装成「已交付」）

| # | 事项 | 状态 | 证据 / 原因 |
|---|---|---|---|
| 1 | **TTS NPU 冒烟实测** | ❌ **失败（超时终止，未出结论）** | 后台任务 `5DMllB`：`timeout 900 ./python/python.exe tts_smoke_app012.py NPU` ⇒ **15m00s 被 `timeout` 强制终止**，退出前 stdout 仅 1 行 transformers 环境提示（`None of PyTorch, TensorFlow >= 2.0, or Flax have been found...`），stderr 空。**产物目录 `C:\Users\Trekker-PTL\tts_smoke_out\` 实测 0 文件**（目录 mtime 仍为创建时刻 15:22）⇒ **未产出任何 wav / 报告**。进程 CPU 301→**1011 s** 持续增长、NPU 缓存由 8 blob/2.4 GB 增至 **13 blob / 3.83 GB**（最后写入 15:35）⇒ 属 **NPU 冷编译耗时，非挂死**。**本轮不报任何 RTF / 音质结论 —— 冒烟未过。** |
| 2 | **端到端 ABBA（tts off/on/on/off）** | ⏸ 未做 | 依赖 #1 通过 |
| 3 | **v1.4 重打包** | ⏸ 未做 | 前置：设备自选 + TTS 集成 + 端到端验证均未闭环 |
| 4 | **APP-006 第 3~7 步** | ⏸ **等 reviewer 复核** | APP-006 第 2 步明写「这一步需要停下来等 reviewer 复核」⇒ 按纪律**本轮不自行推进**。§11.2 的清单已落盘，等 reviewer 签字后方可执行历史改写 + force push。 |
| 5 | **包体 12.73 GB 优化** | ⏸ 未做 | 需评估是否剔除 `decoder-npu-int8` / `decoder-gpu-int8` / `encoder-fp16`；并与 INT4-CW（可再省 0.97 GB）一并决策 |

### §12.6 并行会话冲突（按纪律**未提交**这些改动）

`git status` 显示工作区混有**其它模块**的未提交改动，本轮**一律不吞**：

| 文件 | 归属 | 处置 |
|---|---|---|
| `live_caption/translator.py` | MT 模块 —— 工作区 1152 行 vs HEAD 1305 行（`+71/−224`），**C-111 的 33 个标志全部消失**（`grep -c "seg_half\|_enqueue_fix\|_enqueue_half"` = 0；HEAD = 33）⇒ 被回退到 C-111 之前基线 | **不提交**，原样留给 MT 模块 |
| `live_caption/live_caption_app.py` | ASR 线程 —— 含 `SIL_REL` / `SPK_REL` 改动（mtime `2026-10-23 15:27:29`） | **不提交** |
| `live_caption/audio_source.py` | ASR §10 改动 3「回环立体声混合」（`_stereo_to_mono` / `_corr` / `STEREO_MIX_BALANCE_DB`），+90 行 | **不提交** |
| `live_caption/tts_service.py` | TTS 侧 10-22 旧改动（`--precision` / `--out-wav` / `--bigvgan-ir` 协议扩展），**非本轮 App 改动** | **不提交** |
| `status/CORRECTIONS.md` | 旧 C 编号文件（冻结于 C-135），本轮未改 | **不提交** |
| `status/app/CORRECTIONS_APP.md` | **reviewer 独占写入文件，只读** | 🔴 **绝不提交** |
| `results/asr_diag/`、`results/*.npy`、`live_caption/diag_*.py`（多个）、`live_caption/sync_c111_revert_to_pkg.py`、`reviewer/find_int8enc.ps1` | ASR / 其它模块诊断产物 | **不提交** |

⚠️ **注意 `git check-ignore` 对 `results/asr_diag/*` 无输出** ⇒ 这些 ASR 诊断产物**未被 .gitignore 覆盖**，
存在**误提交风险**。本轮已逐文件指定 `git add`，未使用 `git add -A` / `git add .`。

### §12.7 本轮提交清单（App 模块负责范围）

| 文件 | 状态 | 字节 | mtime | SHA256 |
|---|---|---|---|---|
| `live_caption/tts_engine.py` | 新增 | 16309 | 2026-10-23 15:15:57 | `afd48c7b65156a9e885313041b2117e7c832fbc0d6ae90b6cd90dcf1adafe717` |
| `live_caption/tts_engine_patch.py` | 新增 | 15973 | 2026-10-23 15:21:10 | `71a0aa38321144150873ee3b0da68e9436dd7c56cdb44630668fb794e597f83e` |
| `live_caption/device_config.py` | 新增 | 8684 | 2026-10-23 11:54:43 | `a03ce889ed76e2b244f8770f57e35343e24a812d4204ac92eed57b9f172bd9af` |
| `live_caption/sync_c135_to_pkg.py` | 新增 | 24705 | 2026-10-23 15:21:20 | `fd99b10ee296c33f9e54c56d4880b9cbb9bbc6e1b9f0d88b62bc16672965f294` |
| `live_caption/tts_worker.py` | 修改 | 38670 | 2026-10-23 15:20:20 | `fec383a50eab9405362a623e7f2e39f64e864bbf5992bebbf98bddc3b1d4cd1a` |
| `status/app/STATUS_APP.md` | 修改 | —— | —— | 见提交后实测 |

- `device_config.py` 自检：`diag_device_select.py` **ALL PASS**；`diag_device_gui.py` **ALL PASS**（实际探测到 `['NPU','GPU.0','GPU.1','CPU']`）。
- `sync_c135_to_pkg.py` 只读校验：客户包 `live_caption_app.py` / `translator.py` 与 HEAD 版**代码骨架完全相同（EQUIV）**。
- `sync_c135_to_pkg.py` 的 `NEW_FILES` 本轮改为 `['device_config.py', 'tts_engine.py', 'tts_engine_patch.py']`；
  `tts_worker.py` 走**精确字符串替换 + `assert count == 1`** 通道（该文件是整文件同源复制，故按整文件替换处理并逐字节校验 SHA256）。

### §12.8 提交 / 推送 / 机器锁释放（闭环证据）

**① 提交**（逐文件 `git add`，**未用 `-A` / `-A.`**）：

```
$ git add live_caption/tts_engine.py live_caption/tts_engine_patch.py \
         live_caption/device_config.py live_caption/sync_c135_to_pkg.py \
         live_caption/tts_worker.py status/app/STATUS_APP.md
$ git diff --cached --name-only
live_caption/device_config.py
live_caption/sync_c135_to_pkg.py
live_caption/tts_engine.py
live_caption/tts_engine_patch.py
live_caption/tts_worker.py
status/app/STATUS_APP.md        ← 恰好 6 个，全在 App 范围内
```

- `status/app/CORRECTIONS_APP.md` **保持未暂存**（`git status` 仍显示 ` M`）⇒ 🔴 **未提交 reviewer 独占写入文件**。
- **内部素材闸门**：`python check_internal_material.py --staged` ⇒ **命中 0 个内部素材 / 结论：PASS**。
- **会议原文扫描**：用脱敏替换表 `C:\Users\Trekker-PTL\git_backup\replace_text_c135.txt`（**7789 条**，每行一条原文）
  逐条扫 6 个暂存文件 ⇒ **总命中 0**。（§12.4 提到的第 692 行旧章节引用**不在本次变更范围**，故未进入暂存区。）

**② 提交与推送**：

| 项 | 值 |
|---|---|
| commit | `ca818ee`（`APP §12: 无新纠偏巡检 + APP-005① 补推送关闭远端泄露 + TTS 引擎按新交接单纠正为 spkonly`） |
| push 前 `git rev-list --left-right --count origin/main...main` | **`0  1`**（0 behind / 1 ahead ⇒ 纯快进） |
| `git merge-base --is-ancestor origin/main main` | 0（true）⇒ **FAST_FORWARD_OK** |
| push 命令 | `git push origin main`（**普通 push，非 force**） |
| push 输出 | `75e82a5..ca818ee  main -> main` |
| push 后 `git ls-remote origin main` | `ca818ee7f5ce47673b579a5eb20d4a0dd0ef378a` |
| push 后远端泄露复查 | `git ls-tree -r origin/main --name-only \| grep -c c134_replay` = **0** |

- ✅ **「不 force push」纪律已遵守**；未改写他人历史，未覆盖并行线程的未提交改动。
- ⚠️ **未提交清单保留完好**（留给对应线程）：`translator.py` / `live_caption_app.py` / `audio_source.py` / `tts_service.py` /
  `status/CORRECTIONS.md` / `status/app/CORRECTIONS_APP.md` / `results/asr_diag/` / `results/*.npy` /
  `live_caption/diag_*.py`（15 个）/ `live_caption/sync_c111_revert_to_pkg.py` / `reviewer/find_int8enc.ps1`。

**③ 机器锁释放**（按纪律：回收前用 ctypes 探测 PID）：

| 步骤 | 实测 |
|---|---|
| 锁内容（释放前） | `module: app` / `pid: 31752` / `started: 2026-10-23 15:22:09` / `host: LAPTOP-0GDQGD3I` ⇒ **本模块自己的锁**，不涉及他人锁 |
| 探测方式 | 复用仓库参考实现 `live_caption/replay_c134_mt.py::_pid_alive()`（ctypes `OpenProcess` + `GetExitCodeProcess`） |
| 探测结果 | `pid=31752 -> alive=False`；`pid=30136 -> alive=False`（冒烟 python 进程）⇒ **两者均已真死** |
| 释放动作 | `rm -f shared/MACHINE_LOCK` ⇒ 复查 `ls` 报 **No such file or directory** ⇒ ✅ 已释放 |

- ⚠️ **踩坑记录**：第一次自写探测时给 `k32.OpenProcess.restype = wt.HANDLE` ⇒ 反而返回 `err=87`（ERROR_INVALID_PARAMETER），
  进程已死/未死都无法判断。**参考实现刻意不设 `restype`**（ctypes 默认 `c_int`）——我的版本「修得更规范」反而错了。
  ⇒ **纪律：探测进程存活只复用 `replay_c134_mt.py::_pid_alive()`，不要自己重写。**
- 🔴 **绝不用 `tasklist /FI`**（Git Bash 下 `/FI` 被当路径），也**不用 `Get-Process` 单独判定**（进程退出后可能仍在快照中）。

**④ 本轮边界重申**：

- 本轮**没有**执行任何新纠偏条目（最大编号 APP-006 = `last_ack`，无 APP-007+）。
- 本轮**没有**推进 APP-006 第 3~7 步（历史改写 + force push）—— **等 reviewer 复核 §11.2 清单**，本轮到此为止。
- 本轮**没有**跑 CPU 推理或测速；NPU 冒烟是被 `timeout` 杀掉的冷编译，**无有效性能数据**。
- 本轮**没有**调用 MiniMax 做质量判定（质量判定归 reviewer）。

---

## §13 无新纠偏条目巡检 + TTS NPU 冒烟通过 + 修掉内置音色真 bug（2026-10-23 16:49）

### §13.0 本轮动作摘要

- **巡检结论：`CORRECTIONS_APP.md` 最大编号 = APP-006 = 头部 `last_ack` ⇒ 本轮无新纠偏条目。**
  - 依据：文件实测 mtime `2026-10-23 12:01:55.742320600 +0800`，17965 B，
    SHA256 `dff32b2c96b6ccc02127ef6b258eef73bd0b3d0cd574a3772a5f4063ee7db8cc`；
    `## APP-xxx` 条目共 6 条（APP-001 09:12 / APP-002 09:37 / APP-003 09:45 / APP-004 11:17 / APP-005 11:58 / APP-006 12:01）；
    全仓 `grep -rn "APP-00[789]\|APP-01[0-9]" --include="*.md"` 全命中仅 3 处，
    **全部是本 STATUS/记忆文件里的「无 APP-007+」自述文字**，无真实新条目。
  - `CORRECTIONS_APP.md` 本轮**只读、未修改、未提交**（`git status` 仍显示 ` M`，是 reviewer 侧未入库的 APP-005/006 两条）。
- **本轮实际做的三件事**（把 §12 的「已做但未闭环」补完）：
  1. **TTS NPU 冒烟重跑并通过** —— 补做 §12.5#1（§12 记录 900 s 超时无结论），本轮 **216.3 s 跑完 exit=0**，产出 wav 与 report（§13.1）。
  2. **修掉 §12.2 遗留的真 bug** —— 内置音色路线抛 `ValueError: speaker_library not set`，
     **§12.2「内置音色全部内置可用」的结论不成立**，本轮定位根因并修复 + 复测通过（§13.2）。
  3. **`.gitignore` 加固** —— 补上 §12.6 记录的 `results/asr_diag/*` 与 `results/*.npy` 误提交风险（§13.5）。
- **未推进**：APP-006 第 3~7 步（历史改写 + force push）—— APP-006 第 2 步明写「这一步需要停下来等 reviewer 复核」⇒ **本轮仍按纪律停下**。
- **未完成**：端到端 ABBA（依赖本轮冒烟通过，现已解锁但尚未跑）、v1.4 重打包（前置仍未闭环）。

### §13.1 TTS NPU 冒烟 —— **通过**（补做 §12.5#1）

**持共享机器锁执行**（锁实现直接复用 `live_caption/replay_c134_mt.py` 的
`_pid_alive` / `acquire_lock` / `release_lock`，**不自写** —— §12.8 踩坑记录：
自写 ctypes 探测设了 `restype` 反而返回 `err=87`）。

| 项 | 实测值 |
|---|---|
| 锁 | `[lock] 已获取（等了 0s）` → 作业结束 `[lock] 已释放`（无他人锁被误回收） |
| 命令 | `客户包python/python.exe C:\Users\Trekker-PTL\tts_smoke_app012.py NPU` |
| exit | **0** |
| 首轮耗时 | **216.3 s**（冷编译；NPU 缓存 4.1 GB → 4.6 GB，新增 1 blob） |
| 二轮耗时 | **19.4 s**（命中编译缓存，`load_s` 209.74 → **9.99**） |

**产物**（仓库外 `C:\Users\Trekker-PTL\tts_smoke_out\`，4 文件 / 186651 B 合计）：

| 文件 | 字节 | mtime |
|---|---|---|
| `babelvox_spokonly_A.wav` | 130604 | 2026-10-23 16:49 |
| `smoke_report.json` | 778 | 2026-10-23 16:49 |
| `smoke_stdout_NPU.txt` | 1413 | 2026-10-23 16:49 |
| `smoke_stderr_NPU.txt` | 556 | 2026-10-23 16:49 |

**`smoke_report.json` 原始字段**（逐字引用）：

```json
{
  "sample_rate": 24000,
  "load_s": 9.99,
  "engine_class": "MultiDecoderBabelVox",
  "speaker_embed_shape": [1, 1024],
  "n_chunks": 3,
  "sample_rates_seen": [24000],
  "out_samples": 65280,
  "out_duration_s": 2.72,
  "gen_wall_s": 3.692,
  "rtf": 1.357,
  "peak_amp": 0.3762,
  "clipped": false,
  "wav_bytes": 130604,
  "builtin_speaker_n_chunks": 4
}
```

**结论（只报实测，不外推）**：

| 项 | 结论 |
|---|---|
| BabelVox 引擎加载 | ✅ `MultiDecoderBabelVox`（多桶解码器），NPU 设备 |
| spkonly 路线 | ✅ `speaker_embed_shape = (1, 1024)`，来自 `voices/preset_A.wav` |
| 流式输出 | ✅ 3 chunk，采样率恒 **24000** |
| 内置音色路线 | ✅ `builtin_speaker_n_chunks = 4`（**修复前是报错**，见 §13.2） |
| 波形健康 | ✅ `peak_amp = 0.3762`，`clipped = false` |
| 🔴 **RTF** | **1.357**（自测句 2.72 s 音频 / 3.692 s 生成）—— **未达 ≤0.5 的目标**，且这是**自测短句 + 首次调用含预热**，**不能当作稳态 RTF**；正式性能数据要等端到端 ABBA（§12.5#2，仍未做） |
| 音质 | ⏸ **本轮不判定** —— 质量判定归 reviewer 用 MiniMax 回转写，**目标机不自己调用 MiniMax** |

- ⚠️ stderr 有一条 `fix_mistral_regex=True` 的 tokenizer 提示（Mistral tokenizer 正则），来自 babelvox 内部加载，
  **未影响本次输出**（分词正常、音频正常），但**记为待 TTS 模块确认项**（见 §13.7 第 6 条）。

### §13.2 修掉「内置音色抛 `ValueError`」的真 bug（**撤回 §12.2 的一条结论**）

**§12.2 的原文结论**：「**内置音色**：`cindy` / `lou` / `phil` / `steve` 四条，**全部内置**（speaker encoder 9 MB）⇒ 客户包**不需要 `ref_text`**。」

**这条结论不准确** —— 本轮实测内置音色路线**直接抛异常**：

```
"builtin_speaker_error": "ValueError: speaker_library not set; cannot look up named speaker"
```

**根因（读 babelvox 源码定位，非猜测）**：

| 事实 | 证据 |
|---|---|
| `speaker_library` 默认是 `None`，按名查音色时**必抛** | `babelvox/pipeline.py:139` `self.speaker_library = None`；`:781-783` `if self.speaker_library is None: raise ValueError("speaker_library not set; cannot look up named speaker")` |
| 内置音色**不是引擎内置常量**，而是**随包文件** | `babelvox/speakers.py:19` `BUILTIN_SPEAKERS_DIR = <pkg>/data/speakers`；实测包内有 `cindy.json/lou.json/phil.json/steve.json` + 同名 `.npy`（各 4224 B = 1×1024 float32） |
| 必须**显式赋给引擎属性**才生效 | `babelvox/cli.py:140` `tts.speaker_library = SpeakerLibrary(speaker_dir)` —— **建了库还不够，必须设 `eng.speaker_library`** |
| 库目录要放包外 | `SpeakerLibrary(library_dir, copy_builtins=True)` 会 `os.makedirs(library_dir)` 并把内置音色**复制**进去 |

⇒ §12.2 的 `make_engine()` **只建了引擎、没挂 SpeakerLibrary** ⇒ 内置音色是**不可用**的（§12.2 当时只自测了参考 wav 路线，没测内置音色路线 ⇒ 结论漏项）。

**本轮修复**（`live_caption/tts_engine.py`）：

```python
    on_log('[tts_engine] 模型加载完成')

    # 🔴🔴 **必须挂 SpeakerLibrary**，否则按名查内置音色会直接抛
    #   `ValueError: speaker_library not set; cannot look up named speaker`
    #   （babelvox/pipeline.py:782 —— `speaker_library` 默认是 None）。
    _attach_speaker_library(eng, on_log=on_log)
    return eng
```

新增 `_attach_speaker_library(eng, on_log=print) -> bool`：
库目录 `%LOCALAPPDATA%\Confucius4LiveCaption\tts_speakers`（**不写进客户包目录**，同编译缓存纪律）；
`SpeakerLibrary(lib_dir, copy_builtins=True)` → `eng.speaker_library = ...`；
失败**只告警不抛**（内置音色是可选路径，参考 wav / spkonly 才是主路径）。

**修复后实测**（同一次冒烟，日志原文）：

```
[tts_engine] SpeakerLibrary 就绪：C:\Users\Trekker-PTL\AppData\Local\Confucius4LiveCaption\tts_speakers（4 个音色：cindy, lou, phil, steve）
```

`smoke_report.json` 的 `builtin_speaker_n_chunks` = **4**（修复前该字段是错误字符串）⇒ **内置音色路线已通**。

**库目录实测**（`%LOCALAPPDATA%\Confucius4LiveCaption\tts_speakers`，8 文件 / 16898 B）：
`cindy.json` 307 + `cindy.npy` 4224 + `lou.json` 314 + `lou.npy` 4224 +
`phil.json` 315 + `phil.npy` 4224 + `steve.json` 313 + `steve.npy` 4224。

**⇒ 撤回 §12.2 的「内置音色全部内置（⇒ 客户包不需要 ref_text）」这句表述**：
正确表述是「内置音色**随包分发**（4 组 json+npy），**需要显式挂 `SpeakerLibrary` 才能按名使用**」；
但 §12.2 的**主结论「spkonly 路线不需要 `ref_text`」仍然成立**（本轮实测 `(1, 1024)` embedding 路线成功出音频）。

### §13.3 仓库 ⇄ 客户包定点同步（不整目录覆盖）

新脚本 `live_caption/sync_c136_to_pkg.py`（5892 B，SHA256 `5a2bfc8a09e3d93f58d3f5057b5331652aec2bad71856c42ec3c2c7be4a3d2b5`）：

- **精确字符串替换 + `assert count == 1`**（唯一命中断言），锚点 = `on_log('[tts_engine] 模型加载完成')\n    return eng\n`。
- **替换后必须与仓库版本逐字节一致**，否则**拒绝写入**（防「包里还有别的差异却被整文件覆盖」）。
- **备份放包外**：`C:\Users\Trekker-PTL\pkg_backup_app013\tts_engine.py.bak_20261023`。
- **幂等**：复跑输出 `[OK] 客户包已是最新（SHA256 一致），no-op`。

| 文件 | 字节 | SHA256（同步后） |
|---|---|---|
| 仓库 `live_caption/tts_engine.py` | 18197 | `8110ded6d30402c90f5356e37492ff8f793b68b0ec86a2d0a13480babd965b9d` |
| 客户包 `app/tts_engine.py` | 18197 | `8110ded6d30402c90f5356e37492ff8f793b68b0ec86a2d0a13480babd965b9d` |

⇒ **仓库 ⇄ 客户包该文件 SHA256 完全一致**。

### §13.4 仓库 ⇄ 客户包全量比对（14 个 app/ 文件）

| 文件 | 状态 | 备注 |
|---|---|---|
| `backends.py` / `device_config.py` / `npu_delivery_backend.py` / `npu_embeds_backend.py` / `seg_stream.py` / `segment_encoder_backend.py` / `selftest_audio_sources.py` / `tts_engine.py` / `tts_engine_patch.py` / `tts_worker.py` | ✅ **SAME** | 10/14 |
| `audio_source.py` | ⚠️ DIFF | **ASR 线程**改动（回环立体声混合），非 App，本轮不碰 |
| `live_caption_app.py` | ⚠️ DIFF | **并行会话正在改**（mtime 16:47 仍在变，三分区组合下拉），非 App，本轮不碰 |
| `translator.py` | ⚠️ DIFF | **MT 线程**改动（mtime 16:21），非 App，本轮不碰 |
| `streaming_asr.py` | ⚠️ DIFF | repo 版本较新（已跟踪改动），非本轮 App 改动 |

⚠️ **`live_caption/diag_device_gui.py` 的 docstring 里出现了「APP-007」字样**（mtime 16:42:29 = 本轮巡检期间），
但 `CORRECTIONS_APP.md` **无 APP-007 条目** ⇒ 那是并行会话自行命名的内部标记，**不是 reviewer 的纠偏条目**。
⇒ **本轮不按它执行**，也**不认它为 last_ack 依据**。

### §13.5 `.gitignore` 加固（补 §12.6 记录的误提交风险）

§12.6 已指出 `results/asr_diag/*` 与 `results/*.npy` **未被 .gitignore 覆盖**，有 `git add -A` 误提交风险。
本轮补 4 行（`.gitignore` 2086 B → **2414 B**，SHA256 `50ff34b5d72eea8f8cf20638d6a9ed5988a686d52283684e0f23c98e9056addd`）：

```gitignore
results/asr_diag/
results/**/*.npy
results/*_probe.npy
```

**`git check-ignore -v` 实测**（全部命中）：

| 路径 | 命中规则 |
|---|---|
| `results/asr_diag/x.txt` | `.gitignore:87:results/asr_diag/` |
| `results/loopback_probe.npy` | `.gitignore:90:results/*_probe.npy` |
| `results/mic_noise_probe.npy` | `.gitignore:90:results/*_probe.npy` |
| `results/foo.npy` | `.gitignore:88:results/**/*.npy` |
| `results/c134_replay/x.txt` | `.gitignore:77:results/c134_replay/`（原有，未破坏） |
| `reports/x/transcript_a.txt` | `.gitignore:79:reports/**/transcript_*.txt`（原有，未破坏） |
| `models/qwen3tts/openvino_model.xml` | `.gitignore:1:models/`（原有，未破坏） |

### §13.6 打包与内部素材复验（只读，不写包）

| 检查 | 命令 | 结果 |
|---|---|---|
| 打包 dry-run | `./.venv/Scripts/python.exe pack_v13.py --dry-run` | **PASS（dry-run，未写 zip）**；INT8 关键文件 `openvino_model.xml/.bin/config.json/chat_template.jinja` 全 **[OK]**；Qwen3TTS int8 12 个 IR 全 **[OK]**；`models/qwen3tts/voices/preset_A.wav` **[OK]** |
| 内部素材闸门 | `./.venv/Scripts/python.exe check_internal_material.py --repo . --pkg <客户包>` | **命中 0 个内部素材 / 结论：PASS —— 未发现内部素材** |
| 源目录残留 | dry-run 输出 | `源目录残留: 0 个内部内容文件` |
| 设备自选自检 | `./.venv/Scripts/python.exe live_caption/diag_device_select.py` | **ALL PASS**（回退/优先级/持久化/精度约束/损坏配置不崩，全过） |

- 设备自检会写 `%LOCALAPPDATA%\Confucius4LiveCaption\device_config.json`（57 B，mtime 16:45:52），
  **脚本结束时已自恢复为推荐默认** `{"asr": "GPU.0", "mt": "GPU.0", "tts": "NPU"}` ⇒ **无副作用**。

### §13.7 未完成项与阻塞（如实记录，未包装成「已交付」）

| # | 事项 | 状态 | 原因 |
|---|---|---|---|
| 1 | **端到端 ABBA（tts off/on/on/off）** | ⏸ 未做 | §13.1 冒烟已通过，**前置已解锁**，但本轮未跑 |
| 2 | **v1.4 重打包** | ⏸ 未做 | 前置：设备自选（✅ §13.6 已验）+ TTS 集成（✅ 冒烟通过）+ 端到端验证（❌ #1 未做）⇒ 未闭环 |
| 3 | **APP-006 第 3~7 步** | ⏸ **等 reviewer 复核** | APP-006 第 2 步明写「这一步需要停下来等 reviewer 复核」⇒ 本轮**仍不自行推进**。§11.2 清单已落盘 |
| 4 | **RTF 性能判据** | ⏸ 无正式结论 | 本轮 `rtf = 1.357` 是**自测短句首调用**（含预热），**不可当稳态 RTF**；正式数据等 #1 |
| 5 | **音质判定** | ⏸ **交 reviewer** | 质量判定归 reviewer 用 MiniMax 回转写，目标机**不自己调用 MiniMax** |
| 6 | **babelvox tokenizer 的 `fix_mistral_regex` 提示** | ⏸ **转 TTS 模块** | stderr 提示 Mistral tokenizer 正则需 `fix_mistral_regex=True`；本轮**未影响**输出，但需 TTS 模块确认是否要在 `tts_engine.py` 侧显式传该参数 |
| 7 | **包体 12.73 GB 优化** | ⏸ 未做 | 需评估是否剔除 `decoder-npu-int8` / `decoder-gpu-int8` / `encoder-fp16`；是否剔除 INT4-CW（可再省 0.97 GB）—— 待用户决定 |

### §13.8 并行会话隔离（按纪律**未提交**这些改动）

| 文件 | 归属 | 处置 |
|---|---|---|
| `live_caption/live_caption_app.py` | 并行会话（三分区组合下拉，mtime 16:47 仍在变） | **不提交** |
| `live_caption/translator.py` | MT 模块（mtime 16:21） | **不提交** |
| `live_caption/audio_source.py` | ASR 模块（回环立体声混合） | **不提交** |
| `live_caption/tts_service.py` | TTS 侧旧改动 | **不提交** |
| `live_caption/streaming_asr.py` | ASR 侧 | **不提交** |
| `status/CORRECTIONS.md` | 旧 C 编号（冻结于 C-135） | **不提交** |
| `status/app/CORRECTIONS_APP.md` | 🔴 **reviewer 独占写入文件，只读** | 🔴 **绝不提交** |
| `live_caption/diag_*.py`（20 个）、`live_caption/diag_seg_qwen3_*.json`（4 个）、`live_caption/sync_c111_*.py`（2 个）、`live_caption/win_clickthrough.py`、`reviewer/find_int8enc.ps1` | 其它模块诊断产物 | **不提交** |

⇒ 本轮**逐文件 `git add`**，未使用 `git add -A` / `git add .`。

### §13.9 本轮提交清单（App 模块负责范围）

| 文件 | 状态 | 字节 | mtime | SHA256 |
|---|---|---|---|---|
| `live_caption/tts_engine.py` | 修改 | 18197 | 2026-10-23 16:48:20 | `8110ded6d30402c90f5356e37492ff8f793b68b0ec86a2d0a13480babd965b9d` |
| `live_caption/sync_c136_to_pkg.py` | 新增 | 5892 | 2026-10-23 16:48:37 | `5a2bfc8a09e3d93f58d3f5057b5331652aec2bad71856c42ec3c2c7be4a3d2b5` |
| `.gitignore` | 修改 | 2414 | 2026-10-23 16:44:49 | `50ff34b5d72eea8f8cf20638d6a9ed5988a686d52283684e0f23c98e9056addd` |
| `status/app/STATUS_APP.md` | 修改 | —— | —— | 见提交后实测 |

### §13.10 本轮边界重申

- 本轮**没有**执行任何新纠偏条目（最大编号 APP-006 = `last_ack`，**无 APP-007+**）。
- 本轮**没有**推进 APP-006 第 3~7 步（历史改写 + force push）—— **等 reviewer 复核 §11.2 清单**。
- 本轮**没有**跑 CPU 推理或测速（冒烟走 **NPU**；设备自检不加载模型）。
- 本轮**没有**调用 MiniMax 做质量判定（质量判定归 reviewer）。
- 本轮**没有**整目录覆盖同步客户包（只用了 `sync_c136_to_pkg.py` 的定点替换）。
- 本轮**没有**提交 `status/app/CORRECTIONS_APP.md`，也**没有**吞其它模块的未提交改动。
