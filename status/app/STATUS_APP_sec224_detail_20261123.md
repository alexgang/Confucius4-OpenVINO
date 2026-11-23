# STATUS_APP §224 —— 执行 **APP-128**（last_ack=APP-127 → **APP-128**，2026-11-23 20:2x）

> 本节正文全文（APP-052④：正文放 companion，活文档只留标题行 ＋ 指针行）。
> 证据路径：`C:\Users\Trekker-PTL\shared\bgkeep\app128_dl\`（本轮产物）｜`C:\Users\Trekker-PTL\shared\bgkeep\e2e9\`（实时 e2e）｜`C:\Users\Trekker-PTL\live_dub_ext\`（仓库 `claude-dev` 分支）。

## §0 本条纠偏的来源与通道（**邮件通道；局域网文件里没有 APP-128**）

- 🔴 **APP-128 只走 QQ 邮箱**（reviewer 断网 ⇒ 代码以邮件附件下发）：主邮件 `msg_hCLuUbZ2nqDKRNg5JY_73JHw-P-kxI6ZCqaGzm57VcuXoQ`（`[C4][A][CORRECTION][APP] APP-128 [HIGH] 2026-11-23`，2026-11-23 11:40:19Z ＝ 19:40:19 本地）＋ 补充邮件 `msg_RCOqtjS9XJ9rhP4CaVQKDiXoXBQAZCiUKpcc_FbogmmuFg`（19:40:34，说明附件名带 `.txt` 后缀）。
- 🟢 **局域网 `status/app/CORRECTIONS_APP.md` 仍止于 APP-127**（开工实测：125 条／max **APP-127**／SHA256 `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48`／429 255 B／mtime 2026-11-23 16:55:40）⇒ **本条未落局域网文件属正常**（T-MAIL-003 §4：断网期间纠偏只走邮件）。
- 🟢 **同一编号只执行一次**：APP-128 仅出现在邮件通道一处 ⇒ 只执行一遍。
- 🔴 **按 APP-128 §2 授权范围**：本条只替换 3 个文件（`ext/speaker_bypass.py`、`ext/bridge.py`、`tests/test_ext0419_bgkeep.py`）⇒ **APP-125 的「App 线程不要开发」禁令在 APP-128 明示的例外范围内**，其余 `live_dub_ext` 文件**一字未动**（收尾 `git status` 干净）。
- 🔴 **APP-128 §6 明确「v2.6 打包仍等 reviewer 交接」** ⇒ 本轮**未打包、未打 zip、未改客户包任何文件**。

## §1 附件替换：3 个文件 md5 **逐个与 reviewer 表格一致**

- 🟢 **附件本身 md5 先核（reviewer §2 第一步）** —— 三个附件的 md5 **与上表「新内容」逐字节一致**：

| 附件 | 目标 | reviewer 新内容 md5 | 实测 md5 | 字节 | 一致 |
|---|---|---|---|---|---|
| `speaker_bypass.py.txt` | `ext\speaker_bypass.py` | `69f9fce5221c8bf6149ab91cc6503c78` | `69f9fce5221c8bf6149ab91cc6503c78` | 24 261 | ✅ |
| `bridge.py.txt` | `ext\bridge.py` | `7be3f8aa06cc2c85169c1b55f9c38523` | `7be3f8aa06cc2c85169c1b55f9c38523` | 288 353 | ✅ |
| `test_ext0419_bgkeep.py.txt` | `tests\test_ext0419_bgkeep.py` | `d19d2f64a0a460b55724576cedb01b54` | `d19d2f64a0a460b55724576cedb01b54` | 6 362 | ✅ |

- 🟢 **覆盖后工作区 md5 仍与上表一致**（脚本落盘用「临时文件 → `os.replace`」＋ 写后逐字节断言，未原地截断）：
  - `ext/speaker_bypass.py` 24 261 B `69f9fce5…`（旧 23 863 B `e07e1531…`）
  - `ext/bridge.py` 288 353 B `7be3f8aa…`（旧 288 306 B `f48024db…`）
  - `tests/test_ext0419_bgkeep.py` 6 362 B `d19d2f64…`（旧 5 134 B `bf4b3fb7…`）
- 🔴 **本轮踩坑（人工转写 base64 必错，如 §222 邮件教训同源）**：**第一次**取小附件时把 base64 手工转写进 `.b64` 文件 ⇒ 解出来的 `test_ext0419_bgkeep.py` **md5 = `ba46e0fc…`（≠ 表值）**，且文件里 `({sum(RES)}.{len(RES)})` 的 **`/` 被转成了 `.`**。
  - 🟢 **修法（不靠人工转写）**：**让 harness 把它自己落盘的工具结果文件当底本** —— `DownloadAttachment` 的返回在超限时被 harness 持久化到 `.workbuddy/projects/.../tool-results/`；脚本扫描这些落盘文件里的 base64 连续段并**逐个算 md5**，命中 `want` 才写出 ⇒ **3/3 md5 全部命中**。
  - 🔴 **沉淀**：**「base64 人工转写必错」这条在本轮再次被证实**（§222 邮件附件同因）⇒ **凡附件落地，一律走「工具结果落盘文件 → 脚本扫描 → md5 命中 → 写出」**，禁止把 base64 手抄进脚本或 shell。

- 🔴 **行尾口径说明（供 reviewer 复核，勿按 LF 口径复算）**：本机 `core.autocrlf=true` 且无 `.gitattributes` ⇒ **工作区是 CRLF、index 是 LF**。故 reviewer 表里「旧」列的 md5（`e07e1531…`／`f48024db…`）**等于旧版工作区 CRLF 字节**，而 `git show :ext/speaker_bypass.py | md5`（index＝LF）= `ea959d6d…`、旧 `bridge.py` = `060b0c54…` ⇒ **两者不是同一个口径**。本轮提交后：`git show :ext/speaker_bypass.py | md5` = **`7748b55e…`**（= 新附件 CRLF 字节归一 LF）、`git show :ext/bridge.py | md5` = **`f5bc35b7…`**、`git show :tests/test_ext0419_bgkeep.py | md5` = **`d19d2f64…`**（测试文件本身是 LF ⇒ 与表值相同）。
  - 🟢 **判据**：**reviewer 指定的「附件本身 md5 ＝ 表值」这条已 3/3 成立**；`git show` 那一列**因行尾归一必然与表值不同**（除非该文件本身是 LF），**属口径差异而非内容差异** —— 复核请以**工作区字节 md5 ＝ 表值**为准。

## §2 代码改动（**与 reviewer §1/§2 描述逐条吻合**）

- 🟢 `ext/speaker_bypass.py` **+5 行**（reviewer 预计「约 +5」）：把 `app/asr_spk` 注入 `sys.path` 的语句**从 `_asset_paths()` 之后提到之前**：

  ```
  +        # v0.4.19 (ASR-096 B): app/asr_spk must be importable BEFORE the IR lookup …
  +        if d not in os.sys.path:
  +            os.sys.path.insert(0, d)
           seg_ir, wes_ir = self._asset_paths()
  ```

- 🟢 `ext/bridge.py` **±2 行**（reviewer 预计「约 ±2」）：`stats_full.spk_bypass.note` 改为「本会话未开启说话人旁路（桥接未带 `--spk-bypass`；克隆模式的说话人标签来自 clone_voice 的 SpeakerBridge）」⇒ **原文「串行会话无 GPU 互斥锁 ⇒ 不接」与事实不符**已改。
- 🟢 `tests/test_ext0419_bgkeep.py` **+26 行**（reviewer 预计「约 +27」）：新增第 6 组单测（真实路径，不 mock `_asset_paths`）⇒ 校验 ① 5 s 窗口选 `fp16-w5` ② `_load()` 里路径注入在 `_asset_paths()` **之前**。
- 🟢 `git diff --cached --stat`（提交前实测）：**只有这 3 个文件**，`3 files changed, 33 insertions(+), 2 deletions(-)`；`numstat` = `speaker_bypass 5/0`、`bridge 2/2`、`test 26/0`。

## §3 本地核实「修法确实是load-bearing」（**行为级真跑 ＋ 反证组**）

- 🟢 **根因在本机代码里复核成立**（改前）：`ext/speaker_bypass.py` 旧版 `_load()` **先**调 `self._asset_paths()`（第 217 行）**后**才 `os.sys.path.insert(0, d)`（第 225 行）；而 `_find_seg_for_window()` 靠 `import asr052_spk_runtime` 取窗口、`import asr_spk_window` 取 IR 变体名 ⇒ **导入失败被 `except Exception: return ""` 静默吞掉** ⇒ 回落选 `fp16`（10 s）⇒ 形状守卫拒绝 ⇒ 零分段。
- 🟢 **行为级真跑（走产品同款调用路径 `SpeakerBypass._load()`；`SpkEngine` 打桩只记录选中的 IR 路径，不编译/不占设备）**：
  - **现版（已修）**：`seg_ir = …\models\spk\pyannote_seg_3_0\fp16-w5` ✅
  - **反证组（同一探针跑备份里的改前代码）**：`seg_ir = …\pyannote_seg_3_0\fp16`（10 s，**正是缺陷态**）✅
  - 🟢 **判据能识破缺陷 ⇒ 结论不是「探针瞎报」**（反证组是真改坏被检的那部分）。
- 🟢 探针脚本：`shared\bgkeep\app128_dl\_behav.py`（输出 `CURRENT (fixed)` / `OLD (pre-fix)` 两行 ＋ `VERDICT: PASS`）。

## §4 单测 ＋ 回归（**不需要锁**）—— **11/11 全过，零失败**

| 项 | 命令 | 结果 |
|---|---|---|
| 新增 python 测试 | `python tests/test_ext0419_bgkeep.py`（**包内 python** v2.5） | **RESULT: PASS (14/14)**（rc=0）✅ |
| 新增 node harness | `node tests/ext0419_bg_harness.js` | **18/18 PASS**（rc=0）✅ |
| 回归 python ×5 | `test_ext029_spk_bypass.py` | **70 PASS / 0 FAIL** |
| | `test_ext010_pipeline.py` | **25 PASS / 0 FAIL** |
| | `test_ext026_e2e_behaviors.py` | **21 PASS / 0 FAIL** |
| | `test_t1_capture_mode_stats.py` | **38 PASS / 0 FAIL** |
| | `test_ext028_dub_audio_chain.py` | **42 PASS / 0 FAIL** |
| 回归 node ×4 | `t3_settings_harness.js` | **26 PASS / 0 FAIL** |
| | `t4_lang_harness.js` | **28 PASS / 0 FAIL** |
| | `t5_t6_bounds_persist_harness.js` | **16 PASS / 0 FAIL** |
| | `ext026_segid_harness.js` | **13 PASS / 0 FAIL** |

⇒ **合计 11/11 项全过**（reviewer §3「失败就停，不提交，邮件报原文」⇒ **本轮无失败，故继续提交**）。回归脚本：`shared\bgkeep\app128_dl\_regress.py`。

## §5 带旁路的实时 e2e9（**持机器锁**，3 臂）—— **旁路已真正跑起来**

- 🔴 **执行口径**：桥接参数在 `--real --pipeline --port 8765 --delay 20 --target-lang zh` 后加 **`--spk-bypass`**；分离 **GPU.0**；**每臂单独起桥接**；3 臂 `clone_s1`(zh)／`clone_s2`(en)／`clone_cs2`(zh)，**voice=clone**；输出 `shared\bgkeep\e2e9\`。
- 🟢 **reviewer §4 要求「自己写一个 run 脚本或改 v5 的副本，**不要改 `shared\bgkeep\run_bgkeep_v5.ps1` 原件**」** ⇒ 新建 `shared\bgkeep\run_bgkeep_v9_spk.ps1`（与 `run_bgkeep_v5_app_arm.ps1` 的 diff **只有 4 处**：注释、`$root→e2e9`、桥接加 `--spk-bypass`、只跑 3 个 clone 臂）⇒ **v5 原件一字未动**（md5 未变）。
- 🟢 **锁**：`shared\MACHINE_LOCK`（项目规范路径）**原子获取，0 s 拿到**；跑完脚本 `finally` 正常释放（收尾复核**锁已不存在**）⇒ **未泄漏锁**。

### §5.1 reviewer §4 点名的 5 项核对

| 核对项 | clone_s1 | clone_s2 | clone_cs2 | 期望 |
|---|---|---|---|---|
| bridge.log 里旁路加载的 seg IR 路径 | `…\pyannote_seg_3_0\fp16-w5` ✅ | `…\fp16-w5` ✅ | `…\fp16-w5` ✅ | fp16-w5 |
| 「分段推理失败」次数 | **0** | **0** | **0** | 0 ✅ |
| 「IR 输入长度」次数 | **0** | **0** | **0** | 0 ✅ |
| `stats_full.spk_bypass.enabled` | **true** | **true** | **true** | true ✅ |
| `stats_full.speaker.n_speakers` | **2** | **0** ⚠️ | **1** | > 0 |
| `dubs` | 4 | 5 | 21 | — |
| `dub_late_vs_play_s` max / p90 / n_late | 5.9 / 3.5 / 1 | 3.91 / 0.72 / 1 | −0.16 / −3.2 / 0 | — |
| `bg_late_blocks` | **0** | **0** | **0** | 0 ✅ |

- 🟢 **旁路分段 IR 全部命中 `fp16-w5`**（三臂 bridge.log 均有一行：`[spk] 说话人资产（包内）：wespeaker fp16；pyannote_seg_3_0 fp16-w5（窗口 5.000 s，来源 asr_spk_window）`）⇒ **APP-128 的修法在真实链路上生效**（改前会选 `fp16`）。
- 🟢 **`spk_bypass` 其余字段**（三臂）：`available=true`、`load_error=null`、`device_seg=NPU`、`device_embed=GPU.0`、**`spk_queue_drop=0`**、`spk_worker_busy_ms` = 101.5 / 252.2 / 324.2、`n_pending=0`、`shares_device_lock_with_asr=true`。
- 🟢 **`n_label` / `n_no_label`** = 3/1、**0/5**、17/4；`last_label`：s1 = `{"seg_id":"seg_256000","spk":"S1"}`、cs2 = `{"seg_id":"seg_1051520","spk":"S1"}`、s2 = `null`。

### §5.2 🔴 `clone_s2` 的 `n_speakers=0` —— **按 reviewer 要求如实贴日志，未自行改代码**

- 🔴 reviewer §4 原文：「**若 n_speakers 仍为 0，贴 bridge.log 里旁路相关的全部行，不要自行改代码。**」⇒ **本轮未改任何一行产品代码**（§2 的 3 个文件是 reviewer 授权的附件原文替换）。
- 🟢 **旁路相关全部行**（`shared\bgkeep\e2e9\clone_s2\bridge.log` 原文摘录）：

```
[bridge 20:19:09] ★ EXT-029①：说话人旁路已启动（独立线程 + 有界队列 + 异步回填）
[bridge 20:19:09] 旁路：旁路已加载（只读引用 asr_spk；分段@NPU 嵌入@GPU.0）
[bridge 20:19:11] 旁路：分段模型已编译并缓存：pyannote_seg_3_0_w5.xml @ NPU（1.30s，编译次数=1）
[bridge 20:19:11] 旁路：嵌入模型已编译并缓存：openvino_encoder_model.xml @ GPU.0（0.26s）
[bridge 20:19:11] 旁路：旁路模型预热：{'ok': True, 'seg_ready': True, 'enc_ready': True, 'elapsed_sec': 1.585, 'seg_compile_count': 1, 'enc_compile_count': 1, 'seg_reuse': 0, 'enc_reuse': 0}
[bridge 20:19:16] [spk] 说话人资产（包内）：wespeaker fp16；pyannote_seg_3_0 fp16-w5（窗口 5.000 s，来源 asr_spk_window）
[bridge 20:19:16] [spk] 说话人旁路后台线程已启动
[bridge 20:19:16] 克隆说话人已启用（说话人旁路 + 按句绑定音色）
[bridge 20:19:16] [spk] 段 seg_0 标签=- 音色=A（等标签 0.0 s）
[bridge 20:19:21] [spk] 段 seg_56000 标签=- 音色=A（等标签 0.0 s）
[bridge 20:19:25] [spk] 说话人旁路已加载（ASR-029 接口）
[bridge 20:19:27] [spk] 说话人旁路窗口：5.000 s 音频 / 推理 1.175 s
[bridge 20:19:31] [spk] 段 seg_128000 标签=- 音色=A（等标签 0.0 s）
[bridge 20:19:33] [spk] 说话人旁路窗口：5.000 s 音频 / 推理 1.008 s
[bridge 20:19:33] [spk] 说话人旁路窗口：5.000 s 音频 / 推理 0.188 s
[bridge 20:19:42] [spk] 段 seg_256000 标签=- 音色=A（等标签 0.0 s）
[bridge 20:19:43] [spk] 说话人旁路窗口：5.000 s 音频 / 推理 0.305 s
[bridge 20:19:46] [spk] 说话人旁路窗口：5.000 s 音频 / 推理 0.216 s
[bridge 20:19:46] [spk] 说话人旁路窗口：5.000 s 音频 / 推理 0.248 s
[bridge 20:19:47] [spk] 段 seg_384000 标签=- 音色=self_384000.wav（等标签 0.0 s）
```

- 🟢 **旁路本身是健康的**：`fp16-w5` 已加载、模型预热 `ok=True`、**6 次 5 s 窗口推理都跑完**、`n_feed=31`、`n_final_req=5`、`n_pending=0` ⇒ **不是「零分段/IR 不匹配」那类失败**。
- 🟡 **`n_speakers=0` 的口径解读（只报事实，不下结论）**：`n_no_label=5`（= 5 段全部走「明确无标签」分支）；按 `ext/speaker_bypass.py` 第 425–429 行，**「明确无标签」＝ 该段 `on_final` 返回既无 `spk` 也非 `pending`** ⇒ 对应 `ext/spk_engine.py` 的四种 reason 之一：`too_short` / `not_clean_speech` / `overlap` / `embed_shape_out_of_range`。
  - 🔴 **本轮无法从落盘证据里读到具体 reason**：`stats_full` 只回 `spk_bypass` 汇总计数（`n_label`/`n_no_label`），**段级 `spk_table`（含 `spk_reason`）没有进 `bgkeep_e2e.json`**（`tools/bgkeep_e2e.py` 不落 `spk_table`）⇒ **本轮不改工具、不改产品，按 reviewer 要求把日志原样交回，等 reviewer 判定**。
  - 🟡 **供 reviewer 参考的代码侧口径**（只读引用，未改）：`MIN_CLEAN_RATIO` 取自 `asr052_speaker_tracker_api.DEFAULT_MIN_CLEAN_RATIO` = **0.6**（APP-076 的 0.8→0.6 已在 ASR 侧落地）、`OVERLAP_RATIO_MAX` = **0.02**、`MIN_DUR_S` = **2.0**；`clone_s2` 的 5 段时长分别为 3.5 / 4.5 / 8.0 / 8.0 / 6.74 s ⇒ **均 ≥ 2.0 s** ⇒ `too_short` 可排除（**未实测，不作结论**）。
- 🟢 **另两臂的标签真实存在**（`bridge.log` 原文）：`clone_s1` 有 `[spk] new_spk {'spk': 'S1'}` ＋ `[spk] 段 seg_256000 标签=S1 音色=self_256000.wav`；`clone_cs2` 有 `[spk] new_spk {'spk': 'S1'}` ＋ `[spk] 段 seg_1051520 标签=S1`。

## §6 提交 ＋ 推送

- 🟢 **提交**：`3573b2d`（`claude-dev` 分支，`live_dub_ext` 仓库）—— 提交信息**按 reviewer §5 原样**：

  ```
  EXT v0.4.19: speaker bypass picks the 5 s segmentation IR (fp16-w5) — add app/asr_spk to sys.path before the IR lookup; fix the bypass note; real-path unit test
  ```

- 🟢 **只提交了这 3 个文件**（`git diff --cached --name-only` = 3 项；无 token/口令/日志/模型/音色；`bridge_token.txt` 与 `models/` 仍被 `.gitignore` 排除）。
- 🟢 **推送**：`5121d99..3573b2d  claude-dev -> live-dub-ext`（refspec `refs/heads/claude-dev:refs/heads/live-dub-ext` 已在仓库配好；推前 `git fetch` 且**本地与远端无分叉（0/1）**）⇒ 收尾复核 `github/live-dub-ext` = **`3573b2d`**，`git status` **干净**。
- 🔴 **主仓 `confucius4-openvino` 本轮零提交**：APP-128 改的是 `live_dub_ext`（独立仓库），App 主仓只有本 STATUS 文件的改动待提交。

## §7 reviewer §6 要求的另外两项回报

### §7.1 e2e7 三臂对照表（reviewer 要用来定默认分离设备）

| 臂 | `dubs` | `dub_late_vs_play_s` max | p90 | n_late | `bg_late_blocks` |
|---|---|---|---|---|---|
| `off`（保留背景音关） | **123** | **2.43** | **−1.54** | **7** | **0** |
| `on_gpu`（分离 GPU.0） | **123** | **3.41** | **−1.43** | **8** | **0** |
| `on_cpu`（分离 CPU） | **123** | **3.41** | **−1.69** | **8** | **0** |

（源：`shared\bgkeep\e2e7\{off,on_gpu,on_cpu}\bgkeep_e2e.json` 的 `dubs` / `dub_late_vs_play_s` / `bg_late_blocks` 原始字段。）

### §7.2 e2e8 两条 `player_mix.wav` 的 ≤1 MB 有损音频（**已作为邮件附件发出**）

- 🔴 **OGG/Vorbis 不可用**：包内 python 的 libsndfile **VORBIS 编码器栈溢出**（进程退出码 `0xC00000FD`）⇒ **改用 OGG/OPUS（同一容器、仍然有损）**，并同时产出 MP3 备选。
- 🟢 **四个文件全部 ≤1 MB 且回读可解码**（单声道 24 kHz，时长与源一致）：

| 文件 | 字节 | md5 | 源 |
|---|---|---|---|
| `clip_s2_player_mix.ogg` | 143 758（140.4 KB） | `44eab964275ec04415b8d761c08d6762` | `e2e8\clip_s2\player_mix.wav`（30.7 s，峰值 0.9999） |
| `clip_cs2_player_mix.ogg` | 324 763（317.2 KB） | `ecf5620971641b598c19e254e65fd338` | `e2e8\clip_cs2\player_mix.wav`（73.6 s，峰值 0.7280） |
| `clip_s2_player_mix.mp3`（备选） | 239 112（233.5 KB） | `4a028d4f01199ca7de3172ef2e4f4aa0` | 同上 |
| `clip_cs2_player_mix.mp3`（备选） | 559 560（546.4 KB） | `601015e5eb686695c9a74ed2cd494029` | 同上 |

- 🟢 **邮件附件只发 2 个**（reviewer §6「最多 2 个附件」）= 两个 **OGG/OPUS**；A 机上 4 个文件都在 `shared\bgkeep\app128_dl\`。

## §8 纪律登记（本轮做了什么／没做什么）

- 🟢 **开工先备份**：`%TEMP%\live_dub_ext_pre128_bak_20261123_201158\`（3 个文件逐个备份）。
- 🟢 **模块租约**：`session_lease.py acquire app` 拿到 `TOKEN=a44be4c9`（**无 TAKEOVER** ⇒ 新会话，非接续）⇒ 每步 `beat` ⇒ 收尾 `release`；e2e9 的 4 个 PID（`24816`/`32120`/`12944`/`21140`）已 `addpid` 登记。
- 🟢 **未打包／未打 zip／未改客户包任何文件**（APP-128 §6 明确 v2.6 仍等 reviewer 交接 ＋ 用户级记忆「不通知不打包」）。
- 🟢 **未改 `status/app/CORRECTIONS_APP.md`**（reviewer 独占写入文件）—— 收尾复核见 §9。
- 🟢 **未跑 10 分钟整链／未做 MiniMax 抽查与抽听／未调 MiniMax／未连 B 机**（APP-126 §7 的边界未变）。
- 🟢 **未吞他模块改动**：本轮提交只发生在 `live_dub_ext` 仓库；`confucius4-openvino` 主仓**未 commit、未 push**（主仓工作区仍有大量他模块的既有未提交改动，一律未 add）。
- 🔴 **本轮如实登记 2 处事故**：① 附件 base64 人工转写导致 md5 不符（已用落盘工具结果修正，见 §1）；② 首次用 `schtasks` 直接跑 v9 脚本**秒退且无输出**（`>` 重定向不被 `schtasks /TR` 接受 ⇒ 改用 `_run_v9_cleanenv.ps1` 包装器，包装器内做日志重定向 ＋ PATH 变体清理（§223 已知坑）＋ 兜底释放锁）⇒ **第一次那次没有真正开跑，未污染任何产物**。

## §9 收尾复核：`CORRECTIONS_APP.md` **SHA 零改动**

- 🟢 开工记录：SHA256 `fafecf085792cdc0fcecbf85e00be64ff93dc0ea77a1caf8f12a6595a6d97a48`／**429 255 B**／mtime **2026-11-23 16:55:40**／`## APP-` 条数 **125**（max APP-127）。
- 🟢 收尾复核：**四项逐字一致 ⇒ SHA 零改动**（详见 §10 收尾记录）。

## §10 待 reviewer 复核 / 待裁定

1. 🔴 **`clone_s2` 的 `n_speakers=0`**：旁路健康（fp16-w5 命中、模型就绪、6 次窗口推理跑完、`n_pending=0`），但 5 段全部落「明确无标签」分支 ⇒ **具体 reason 未落盘**（`spk_table` 未进 `bgkeep_e2e.json`）⇒ **按 reviewer §4 未自行改代码**，请 reviewer 判定是素材特性（重叠/不干净）还是需要补落 `spk_reason`。
2. 🟡 **默认分离设备**：等 reviewer 用 §7.1 的 e2e7 三臂表裁定（`on_gpu` 与 `on_cpu` 的 `dubs`/`bg_late_blocks` 完全相同、`dub_late_vs_play_s` 的 max/p90/n_late 也几乎一致 ⇒ **本轮数据不足以区分 GPU.0 与 CPU**，需 reviewer 另有判据）。
3. 🔴 **v2.6 打包**：按 APP-128 §6 **仍等 reviewer 交接**，本轮未打包。
