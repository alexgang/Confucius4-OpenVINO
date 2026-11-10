## §164 执行 APP-093（last_ack=APP-093）｜§162 复核：验收 **FAIL** 如实入册、静态诊断＋STATUS 更正已完成 ⇒ 设备作业未跑，**本条需等 reviewer 复核**（2026-11-10 08:49）

> 🔴 **reviewer 中途追加新纠偏**：开工 `CORRECTIONS_APP.md` SHA `3ab8d2b8…`／261 180 B／mtime 2026-11-09 16:49:57／**92 条**（max APP-092）⇒ 收尾 `0917747c…`／**267 771 B**／mtime **2026-11-10 08:13:20**／**93 条**（新增 **APP-093 [HIGH]**）。**不声称 SHA 零改动**；全程只读、未改、未提交。按 APP-093 §4 先写 `last_ack=APP-093` 并加最近更新一行。

### ① 撤回／更正 §162（只追加，不回改旧章节）
* **验收结论是 FAIL**：`app394_app092_overload_analysis.json`（`ts=2026-11-10 06:53:05`，晚于 §162 的 06:29）→ `verdict=FAIL`／`n_pass=5`／`n_fail=2`；`checks[0].ok=false`（(d) `normal.n_late_drop=3`／54 ＝ **5.56 %**）、`checks[5].ok=false`（(c) `overload.recovery_s_after_overload=null` 且 `n_voiced_rows=2` ⇒ 数据不足）。§162 ③/④ 未写 FAIL，按 APP-093 §2a 在此明写；今后判据失败必须入 STATUS。
* **撤回 §162 ④「本机 TTS 有效 RTF≈0.90」笼统口径**，按素材分列（`app395.main_after_normal_runs.*.fields.synth_rtf.p50`／`app396.scores[].synth_rtf_p50`）：after tight **0.9056**／after dave **0.9901**／before tight **0.8919**／before dave **0.9634**；dialog3 before/after 0.884/0.891（reviewer 原文）。
* **撤回 §162 ⑤ 幻影产物**：`results/app/app391_app089_before_and_overload.json` 磁盘不存在（`ls` No such file；只有 `app391_run.log` 35 364 B）⇒ 违反「没落盘不能写已交付」；真实证据为 `app393_app089_scores_before_dialog3.json`＋`app394_app092_overload_analysis.json`。按「只追加」纪律本轮未删改 §162 原文，是否允许直接删改请 reviewer 裁定。
* `app388_app089_scores_after_all.json`：`n_late_drop` dialog3 **3**／dialog3_tight **21（27 %）**／dialog3_dave **30（36 %）**，均不满足 APP-092 §3(d)「≈0」。
* **§162 正文已整块逐字归档** ⇒ `status/archive/STATUS_APP_sec162_20261110.md`（5 052 B／块 SHA256 见归档件与产物清单）；STATUS 只留标题＋索引。原文未删一字，按「只追加、不回改旧结论」纪律处理。

### ② APP-093 §3.1 静态诊断（已完成，`app395`，反证 3/3）
* `defaults_untouched.tts_late_drop_sec=6.0`（实读 `app394.late_drop_threshold_s`）、`device_job=false`、未调 MiniMax。
* after tight 21/78＝26.92 %：`synth_rtf.p50=0.9056`／p90 0.9884、`speed.p50=1.1`、`worker_fifo_wait_s.p50=0.0`、`t_submit-t_recv` p50 **0.97 s**／p90 **4.0002 s**、`play_lag_s` p50 5.831／p95 8.4764、`in_dur_s` max 7.44 s、`out_dur_s/in_dur_s` p50 0.913。
* after dave 30/84＝35.71 %：`synth_rtf.p50=0.9901`／p90 1.1043、`n_speed_floor_conflict_last=53`、`worker_fifo_wait_s.p50=0.0`、`t_submit-t_recv` p50 0.298／p90 2.9692 s、`play_lag_s` p50 8.9725／p95 12.9602、`in_dur_s` max 10.64 s、`out_dur_s/in_dur_s` p50 0.9118。
* **结论**：跳过首要原因＝**TTS 合成吞吐不足**（RTF p50≈0.9–1.0、倍率被 1.10 floor 封顶，1.10–1.5× 曲线未生效）；**队列不是瓶颈**；MT 段为次级贡献（tight p90 4.0 s）。
* 🔴 **口径待裁定**：APP-093 §3.1「App 段长 12–20 s」与 `tts.jsonl.in_dur_s` 实测 max 7.44／10.64 s 不符，疑为「ASR 定稿/合并段」vs「TTS 输入段」口径差异；**未自行改判据**（`app395.main_after_normal_runs.*.reviewer_assumption_check`）。

### ③ APP-093 §3.4 before 臂补齐（静态补算，`app396`，未重跑设备）
* before tight：`run_rc=0`／78 行／字幕 35／`synth_rtf_p50=0.8919`／`play_lag_s_p50=16.5585`、p95 20.2544／`end_reason_counts` 全 eos／`n_hit_frame_cap=0`；before dave：`run_rc=0`／84 行／字幕 55／`synth_rtf_p50=0.9634`／`play_lag_s_p50=33.532`、p95 53.8113／`end_reason_counts` 全 eos／`n_hit_frame_cap=0`。
* 两目录 `run_manifest.json` 齐全且 `wav_sha256` 与 after 逐字一致（`45afb448…`／`b2da188a…`）⇒ 复用已落盘数据静态补算；`late_drop_field_present=false` ⇒ `n_late_drop=0` 是结构性非测量值；`spk_match_rate=null`（真值余弦列 §3.5 待办）。若 reviewer 要求重跑，下轮持锁执行。
* §2e：撞帧上限 **0**，依据 `tts.jsonl.frames` 全空（`n_frames_nonempty=0`）＋ `end_reason` 全 eos，字段来源已写进 json；`app385` 无 `lock`／`timing_valid` 字段，本补算 `lock_record=null` 并注明非计时跑。

### ④ 未完成 ⇒ **本条需等 reviewer 复核**
| APP-093 §3 项 | 状态 / 原因 |
|---|---|
| 2 阈值 A/B（6/10/15 × tight/dave，6 组） | 未跑：需 MACHINE_LOCK＋NPU 长作业；默认值保持 6.0，未自改 |
| 3 过载臂重做（0–60 s 1.0×／60–150 s 过载／150 s+ 1.0×） | 未跑：同上；`--speed 2.0` 全文件无「过载结束」⇒ (c) 结构性不可测 |
| 5 音色归属真值余弦（before/after × dialog3/tight） | 未做：需 x-vector 与 truth.json 三人参考比 |
| 6 切段（tight `n_split=0` 的相似度/margin 分布＋开关 ASR RTF） | 未做：RTF 需设备跑 |
| 7 GUI 三行字幕截图 png | 未做：需 `schtasks /it` GUI；`app372…/subtitle_layout.json` 现 `shot=null`、`gui.log` 0 B |
| 4 CER 回转写 | 不做：reviewer 用 MiniMax，本机不调 |
* 正常跑跳过率取舍由 reviewer 拿 §3.1/3.2 数字报主会话请用户决定；**本轮未打 v2.5、未通知用户、未打包、未改客户包、未调 MiniMax、未在 CPU 跑推理/测速、未持 MACHINE_LOCK**（纯静态，无设备作业）。

### ⑤ 产物（8 个文件；mtime 为本地实测）
- `STATUS_APP_recent_updates_upto_20261110.md`｜3069 B｜2026-11-10 08:55:17｜SHA256 `2a78e95911802ddc2f1bf0304c07a2caaef06589a18b1effdcea7752d176bbbd`
- `STATUS_APP_sec162_20261110.md`｜5347 B｜2026-11-10 08:55:17｜SHA256 `6bb05a503efe7d816f8f463813c3fa83b58127d73be7eaa15200fc4502683254`
- `app395_app093_static_diag.py`｜16183 B｜2026-11-10 08:47:32｜SHA256 `0e26d4d5295aa6bb14e023bb36909c7d95905c3ba5ce09ad01a72229f9e6ecac`
- `app395_app093_lag_decomposition.json`｜19688 B｜2026-11-10 08:47:43｜SHA256 `7d68844218bbebe5741d2fc154e1d631dd194dce482f4cc1613bfc0d113b67a9`
- `app396_app093_before_arm_scores.json`｜4668 B｜2026-11-10 08:47:43｜SHA256 `adfe0ac0ad420b1574e854d662f6021bf8804e8657d91b6762318be4a7315491`
- `app394_app092_overload_analysis.json`｜6797 B｜2026-11-10 06:53:05｜SHA256 `e27abff0c98c8bb99b47853a97675785bad8e0d3d6c431dd2b4e7edc5681cc93`
- `app393_app089_scores_before_dialog3.json`｜2070 B｜2026-11-10 06:32:41｜SHA256 `235931f270254624b679e262c9f355359ea182654fd107032e0213c7f430202c`
- `app382_app092_overload_analysis.py`｜19167 B｜2026-11-10 06:53:29｜SHA256 `d0697419f09abedd877bbd8f5053350d463d7fbd91201c43b99030f34fc926b7`
* 压缩复核（APP-052④）：追加后 **39627 B / 268 行 ≤40000 B / ≤300 行**；6 条旧「最近更新」原文整块逐字归档 ⇒ `status/archive/STATUS_APP_recent_updates_upto_20261110.md`（块 SHA256 `84ffe113eeb4d580a1e8e3f3919f37409b9798f515da21dbf2e24109bcf2a236`），§162 正文整块逐字归档 ⇒ `status/archive/STATUS_APP_sec162_20261110.md`；写前/写后断言：除 §162 外 8 个旧 `## §N` 章节正文逐字未变、§162 原文在归档件逐字命中、章节数 9→10、行尾无 CR；临时文件＋原子替换。
