# STATUS_ASR §100 归档（§99 全文逐字）

> 归档时间 2026-11-24 13:52；来源 `status/asr/STATUS_ASR.md.bak_asr100`（§99 写入前的基线，32 442 B / 120 行）。
> 格式与 `status/archive/STATUS_ASR_sec98_upto_20261124.md` / `sec99_upto_20261124.md` 一致（全文逐字，不改一字）。
> 本文件是 §99 的唯一归档副本；正文 `status/asr/STATUS_ASR.md` 只留一行摘要。

---

### §99 巡检（无新 ASR 纠偏）＋ EXT v0.4.20 只读复核 ＋ 新发现「克隆计数未进 stats_full」（2026-11-24 11:20–11:45）

> 🔴 **纠偏通道无新 ASR 条目** ⇒ `last_ack` 保持 **ASR-068**；邮件新增 3 封（APP-129/130/131）**均为 App 编号**，不进本模块 `last_ack`、无 ASR 动作项。**EXT 已推进到 v0.4.20（`4740b06`）**。🔴 **§97/§98 的开口项仍开口**（v0.4.20 `ext/bridge.py` L2514 `spk_reason` 仍只进段级表、未进 `stats_full`）；🔴 **新发现同型缺口**（`ext/clone_voice.py` 的 `_reasons` 只写日志、不进 `stats_full`）⇒ **APP-131 第 2 项要的 `tts_nearest_voice`/`gender_switch`/`gender_selfref` 当前取不到数（字段不存在，不是值为 0）**。🟢 性别守门实测生效（`gender_ab/v0420/bridge.log` **4** 行；v0.4.19 对照臂 **0** 行），但计数仍只可从日志读、不可机器解析。🟡 克隆模式两臂 e2e 复算 87/87 段、`dub_dropped`=0、`sep_rtf_p50` 0.267→0.258、`bg_clone_from_vocals` 78→83；🟡 **新澄清**：克隆模式标签来自 `clone_voice` 的 `SpeakerVoiceTable`、**不是 `bridge.tracker`** ⇒ `speaker.n_speakers` **不能**当「旁路有没有标签」的判据（旁路仍看 `spk_bypass.n_label`）。🔴 仍缺 v0.4.18 对照臂、`shared/bgkeep/vocals/` 仍不存在。🔴 **本轮未跑推理/计时/WER/分离器、未取 MACHINE_LOCK**（被 App 模块持有）、未改 4 个 ASR 交付文件、未改 `live_caption/`、未改 EXT 源码（只读）、未改纠偏文件内容、未打包。**全文** ⇒ `status/archive/STATUS_ASR_sec99_upto_20261124.md` ＋ `status/asr/notes/asr_s99.md`；**已发 STATUS 邮件** `msg_b4cX1iqXS2ROA9-ElzQSHFSsYRATGccmhmTYp0bVp5HvTQ`（2026-11-24 11:38:55Z，回复 APP-131；正文留档 `status/asr/_asr099_email_body_sent.txt`）
