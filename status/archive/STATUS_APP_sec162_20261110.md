# STATUS_APP §162 正文归档（2026-11-10，APP-093 轮次）

> 原文整块逐字移出，仅用于压缩（APP-052④）；块 SHA256 `3098e4dd75a6444fbb7424ba67e38d49bdad838cf162649d9022b9b7827131c6`，共 5052 B。§164 已撤回本节 ③④⑤ 的错误结论；原文未删一字。

## §162 执行 APP-089/090/091/092（last_ack=APP-092）｜移植完成＋NPU 验收已跑 ⇒ **停在等 reviewer 复核**（2026-11-10 06:29:03）

> 🔴 **顺序遵守 APP-089/090/091/092 的「合并一次跑 → 停下等复核」**：本节**只交移植＋验收数字**；**未打 v2.5、未通知用户**。

### ① 移植落地（开发树 `live_caption/`，9 文件）
| 纠偏 | 落地 |
|---|---|
| **APP-089** ① 去掉 ICL | `tts_cuda_sidecar.py` **不再读 `<ref>.txt`** ⇒ 固定 `xvec_only=True`；`clone_voice.py` 不再写 `.txt` |
| **APP-089** ② 会话开始清空 | 会话开始清**克隆目录**＋`_spk_bind`/`_spk_voices`/策略层缓存（`app378` **5 PASS / 0 FAIL**，含反证组） |
| **APP-089** ③ 三项行为 | `self_ref`（本句音频 ≥1.5 s）＋`xv_reference_ticket`（≥3 s 定稿／≥8 s 升级／最长 10 s）＋`split_by_speaker`（**克隆线程**上编译，**不在接收/ASR 线程**） |
| **APP-090** ②a 不等标签 | `n_label_wait` 计数器（默认 `tts_label_wait_sec=0` ⇒ **恒 0**）⇒ jsonl＋stats 均落盘 |
| **APP-090** ②c 中文语速 | 中文目标 **1.10×–1.50×**（`tts_speed_min_zh`/`tts_speed_max_zh`），其他语言仍 1.0–1.30× |
| **APP-091** ③ 字幕条 | **3 行**：① 定稿译文（主字号）② **定稿原文（小字 0.75×）**③ 实时识别（行为不变） |
| **APP-092** ① ASR/MT 永不跳段 | **无** ASR/MT 级 catch-up 代码（`grep` 0 命中） |
| **APP-092** ② TTS 级跳过过期句 | `tts_late_drop_sec`（默认 **6.0 s**，键名可配）⇒ 逐句记「滞后秒数＋阈值」进 jsonl |

### ② 🔴 本轮修掉的一个**真缺陷**（上一会话 02:02 的改法）
* 上一会话把「目标开播墙钟」从 `t0+已消费源秒` 改成 `t0+已消费源秒/实测速率`；**实测速率极不稳定**（隐含速率 p50 **1.49**、范围 **0.28–13.6**，真值恒为 1.0）⇒ **普通跑（speed=1.0）误跳 19 句**（修正前 3 句）⇒ 直接违反 APP-092 §3(d)。
* 改法：`audio_source` 新增 **构造期已知**的 `pace` 属性（`FileSource.speed`／实时源 1.0）⇒ **无估计噪声 ⇒ 确定性**；`speed=0`（全速跑批）⇒ `pace=0` ⇒ 退回旧口径。
* **修后实测**：dialog3 误跳 **19 → 3**（与修正前基线一致）；`--speed 0.35` 臂 **83/83 全跳过 → 0 句**（口径修复的直接证据）。

### ③ NPU 验收数字（after 臂，一次持锁会话连跑）
素材 `C:\Users\Trekker-PTL\_reviewer_tmp\spktest\`；ASR+MT→GPU.0，TTS→NPU；影子包 `_app_shadow/after/`。
| 素材 | TTS 行 | 有配音 | 只有字幕 | TTS 跳过 | 等标签 | 倍率 min/p50 | 首包 P50/P95 |
|---|---|---|---|---|---|---|---|
| dialog3 | 81 | 78 | 3 | 3 | 0 | 1.1 / 1.1 | 0.5339 / 0.682 |
| dialog3_tight | 78 | 57 | 21 | 21 | 0 | 1.1 / 1.1 | 0.5303 / 0.6621 |
| dialog3_dave | 84 | 54 | 30 | 30 | 0 | 1.1 / 1.1 | 0.5454 / 0.6977 |

* **只有字幕＝TTS 跳过**（APP-092 §2：内容仍完整留在字幕/转写）⇒ **ASR/MT 段数一条不少**。
* **等标签 = 0**（APP-090 §2a「必须是 0」）✅；**倍率 min = 1.10**（APP-091 §2「min 必须 ≥1.10」）✅。
* **音色归属**（`app389`，dialog3）：输出 x-vector 与**本句自己原声**比余弦，严格大于另两人 ⇒ 判「音色最接近本人」：**18/51 = 35.3 %**；**对照（源 vs 源）51/51 = 100.0 %** ⇒ 判据非恒真（源永远 100%）。
  ⚠️ **匹配率 35 % 明显低于对照** ⇒ 克隆音色**离本人原声仍有距离**，**须 reviewer 复核是否达标**（未自行改判据）。
* **换人切段**：dialog3 切 **1** 段（`spk_seg.jsonl` 的 `n_split`）；dialog3_tight 切 **0** 段。
* **克隆目录 `.txt` 数 = 0**（APP-089 §4 结构检查）✅。

### ④ ⛔ 未完成 / 需 reviewer 裁定
* **CER 回转写**：wav＋译文已落盘（`mix.wav` / `subtitles.txt`），**由 reviewer 在本机用 MiniMax 回转写**（本轮**未调 MiniMax**）。
* **过载臂方向修正**：reviewer 原文「`--speed` **调高**」⇒ **调高才是过载**（`speed=S` ⇒ 机器须以 S× 实时产出语音；本机 TTS 有效 RTF≈0.90 ⇒ **S>1.22 才积压**）⇒ 上一轮用 `--speed 0.35` 当过载**方向反了**（它之所以 83/83 全跳，是**旧口径**把 0.35× 消费当 1.0×）⇒ 本轮改用 **`--speed 2.0`** ＋ 0.35 轻负载对照。
* **v2.5 打包**：**未打**（按 APP-089 §5/APP-090 §4/APP-092 §4，须复核通过后才打；EXT 版本以 **APP-092 的 @23aae0b（v0.3.5）** 为准）。
* **未通知用户**（reviewer 明文）。

### ⑤ 产物
* `results/app/app385_app089_accept_runs_after.json`（after 四跑清单）／`app388_app089_scores_after_all.json`（打分）／`app389_app089_voice_margin_after_dialog3.json`（音色归属）／`app375_app089_fixes_static_check.json`（静态闸门 **49 PASS / 0 FAIL**）／`app378_app089_session_reset_check.json`（**5 PASS / 0 FAIL**）／`app391_app089_before_and_overload.json`（before 臂＋过载臂）。

