# STATUS_APP §138 逐字正文（2026-11-05 15:28 版）

> 本件为 `status/app/STATUS_APP.md` §138 在 **2026-11-05 18:08 压缩前**的逐字正文。
> 压缩只把 STATUS 内的 §138 换成「标题 + 归档指针 + 速查」；**正文一字未删**（本件即留存）。
> 另见 `status/archive/STATUS_APP_sec138_20261105.md`（原始完整版，含 README 全文）。

---

### §138 ✅ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成** ｜ **APP-071 仍未完成（BLOCKING）** ｜ **本条需等 reviewer 复核**（2026-11-05 15:28）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec138_20261105.md`（**28 336 B**，逐字保留，含 README 全文、全部产物元数据、闸门原始字段）。
> 🔴 开工/收尾 `CORRECTIONS_APP.md`：**SHA `f6001a0a…`／212 229 B／mtime 2026-11-05T14:33:28.815547／72 条**（APP-001..APP-072）⇒ **逐字相同**（reviewer 本轮未追加；本模块**只读、未改、未提交**）。**last_ack：APP-070 → APP-072**（APP-072 原文要求；**APP-071 编号更小但仍未完成** ⇒ 见 ⑨）。

| # | 事项 | 结论 | 证据 |
|---|---|---|---|
| ① | **zip 已出（§1）** | `shared/minimvp/…_v1.0-rc3_perftest.zip`：**5 591 630 138 B**／**10 474 条目**／SHA `dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1`／7-Zip **BELOW_NORMAL** 后台／`wall_s=157.49`／`rc=0`／`n_mismatch=0` | `app279_rc3_perftest_zip_evidence.json`（1 259 B） |
| ② | **闸门① 黑名单** | **6/0**（扫**解压副本**非源目录）：会议录音／克隆 npz／`tts_speakers`／babelvox 示例音色／开发目录绝对路径／torch·CUDA dll·pyd·cu·cuh **各 0**；🔴 **反证**：同脚本扫源目录 ⇒ 判据④ **FAIL**（抓到 8 个 babelvox 示例音色）⇒ 非恒真 | `app281_rc3_blacklist_scan_evidence.json`；反证 `_app281_counterexample_srcdir.json` |
| ③ | **闸门② NOTICE** | **PASS**：9 643 B／SHA `b4505621…` ⇒ **10 339 B**／SHA `e9c9cfc3…`；三块定点替换各 **hits=1**；`crlf_preserved=true`；必含 `Qwen3-ASR-0.6B`／`Qwen3-TTS`／`Hy-MT2-1.8B`／`OpenVINO 2026.4.1`／`BabelVox`／`babelvox-openvino-int8` 全 true；⚠️ **未**声称随包附模型许可证全文 | `app278_rc3_notice_patch_evidence.json`（`verdict=PASS`） |
| ④ | **闸门③ `--check`** | **5/0**：`rc=0`／`wall_s=11.86`／含「环境正常」／`n_gpu0_hits=3`／`n_npu_hits=8`／`n_asr_backends=3`；原始结论行「**环境正常。ASR 可用后端 3 个，Intel 集显可用。**」；⚠️ CUDA Q8_0/Q4_K 显示「模型齐全」是**开发机 `~/confucius4-r2t2` 残留**（`_cuda_root()` L428-441）⇒ **包内无 CUDA**（`cuda/` 不存在、`*.cu/*.cuh/*.ptx` 0 个、`*torch*.dll/*.pyd` 0 个） | `app282_rc3_check_evidence.json` ＋ `app282_rc3_check_output.txt`（2 694 B／SHA `05de9cdedcf9a674…`） |
| ⑤ | **闸门③ GUI 冒烟** | **5/0**：`tts_load_s=8.5`／`model_loaded_at_s=27.9`／`wall_s=28.46`／`tts_device=NPU`；主窗口 `client=[1439,1093]`／`bytes=43745`／`all_black=false`／`is_main_window=true`；**字幕区 `rows_with_ink=163`／`max_row_ink=373`**；**负对照 `control_rows_with_ink=0`**；`crash_marker_found=false`；截图核验：标题「实时字幕 MiniMVP v1.0」＋五组齐全＋ASR「就绪 RTF 0.56」＋MT「就绪 延迟 387 ms」＋字幕已渲染中英双语 | `app280_rc3_gui_smoke_evidence.json`（10 076 B）＋ `app280_rc3_gui/gui_rc3.png`（65 925 B／SHA `61a99040b518e46d…`） |
| ⑥ | 🔴 **判据缺陷已修并复跑** | 首跑 3 PASS／**1 FAIL**：第③项抓 CLI 串 `[gpu_int8] 加载 x s`，而 **GUI 模式下 ASR 就绪只写状态栏**（`var_status.set`，`app/live_caption_app.py` L3367）⇒ **不落盘** ⇒ 恒 `None` ⇒ **假 FAIL**（截图证明 GUI 当时正常）⇒ 改**字幕区像素判据**＋**负对照** ⇒ 复跑 5/0；另**独立反证**：真图字幕区涂白 ⇒ `rows_with_ink=0` ⇒ 必 FAIL | `_counterexample_blank_caption.png` |
| ⑦ | **打包一致性对账** | rc3 目录相对打包前快照（10 503 条）：**新增 1**（`README_perftest.txt`）／**删除 0**／**大小变化 1**（`NOTICE` 9 643→10 339 B）／**其余 10 502 个文件 size+mtime 逐条未变** ⇒ ✅ **除 NOTICE 补丁＋新增 README 外一个字节都没动** | `shared/_rc3_snapshot_before_pack.json` |
| ⑧ | **README_perftest.txt** | **9 155 B**／SHA `da3cd8ca1dabb1e28fdafb9ba243111f03daf513177782c6f7b545f32daa62b9`／LF／无 U+FFFD／**已进 zip**；覆盖 reviewer 全部小节（定位／系统要求＋**实测驱动号** NPU `32.0.201.14005`·集显 `32.0.101.8508`／内存 **≥16 GB** 且**明确 APP-070 的 8 GB 是磁盘不是内存**／磁盘 ~6.7 GB＋缓存 ~8 GB＋`%LOCALAPPDATA%\Confucius4LiveCaption\`／已知问题 5 条／CLI 测法＋`Get-Counter` 采 CPU 的原因「包内无 psutil」／带回清单／日志关键行／**Panther Lake 基准对照**，数字全取自已落盘 `app271`·`app263`·`app264`） | 全文见归档件 §3 |
| ⑨ | ⛔ **APP-071 未完成（BLOCKING）** | 本轮**只完成根因分析第一部分**：S2 首次登记段**确为** `seg_id=1`／`t0=9.6`／`t1=19.2`／`span=9.6 s`／**`spk_conf=0.1292`**／`spk_source=retry`／`switch S1→S2` ⇒ **与 reviewer 怀疑吻合**；🔴 **当前代码完全没有 `spk_conf` 门槛**（`speaker_voice.py` 的 `note_final()`/`ready_to_embed()` 只看 `dur_s` vs `MIN_S=1.5`/`REFINE_S=3.0`）⇒ 低置信度首检会被直接登记；`_pending_spk_voice` 只有「模型未就绪排队」语义，**无「低置信度 pending」**。⇒ **(a)(b)(c)(d) 全未做**：诊断未落盘／余弦矩阵未算／**产品代码一行未改**／`v23_clone_r2/` 未生成 ⇒ **v2.3 不打包** | `shared/app_listen/v23_clone/seg_voice_table_by_seg.csv`；`live_caption/speaker_voice.py`、`live_caption/live_caption_app.py`（只读） |
| ⑩ | **纪律自检** | ✅ 未改 `CORRECTIONS_APP.md`／✅ 未覆盖·未删任何旧目录旧 zip／✅ 不用 `--same-version`／✅ `live_caption/` **一行未改**／✅ 设备作业全持 `MACHINE_LOCK`（PID 43172·6828）＋ session_lease `addpid`／✅ 安静窗口 45 s 通过／✅ **未通过 FTP 或任何外部服务分发**／✅ **未通知用户**（等 reviewer 转告）／⛔ **未打 v2.3** | 逐条明细见归档件 §6 |

🔴 **本轮产物 15 个**（仓库内）＋ 3 个包外产物 ⇒ **全量字节数／mtime／SHA256 见归档件 §5**。
🔴 **本轮 git**：main 分支普通 push（未 force）；只 `git add` App 模块自己的文件；🔴 **绝不提交 `CORRECTIONS_APP.md`**、**不吞** ASR／MT／TTS 其它模块的未提交改动。
