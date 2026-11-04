### §133 ✅ **APP-067（①克隆 0 % 根因 / ②APP-065 C 交付物 / ③D4 界面 / ④设备验收 / ⑤D1 5 s 窗口）** ｜ **①③⑤ 本条已完成（设备级）｜ ②④ 的设备级部分未做（等锁）** ｜ **本条需等 reviewer 复核**（2026-11-04 21:10）

> 🔴 **接管上一会话**（TAKEOVER：token `fa098d83`，18:25 起 117 min 无心跳）：它的 3 个提交（`42b62e7`/`e804108`/`e88e3f1`）**已入库但 STATUS 未写** ⇒ 本轮从断点续做；`CORRECTIONS_APP.md` 开工基线 = 收尾实测（SHA `cf71e427…` / 192 381 B / 2026-11-04 09:52:22 / **67 条**）⇒ **本轮零改动**。

| 子项 | 状态 | 证据（原始字段） |
|---|---|---|
| ①(a) worker 加载期丢 `spk_voice` | ✅ 已修（入队 ⇒ 加载完成后补登记） | `app236` → `checks` **9 PASS / 0 FAIL**（9 条反证全被抓住，`n_counterproof_failed_to_detect=0`） |
| ①(b) seg→spk 绑定断点 | ✅ 已定位 = **音色从未登记成功**（不是窗口滞后） | `app235` → `label_vs_submit.A_voice_never_registered=46` / `B_label_after_submit=0` |
| ① **设备级验收** | ✅ **clone 41/42 = 97.62 %**；带 spk 句 **36/42 = 85.71 %**；「没有可用引擎」= **0** | `app243` → `n_pass=9 / n_fail=0 / n_none=0`，**4 条反证全被抓住** |
| ③ D4 界面仍显示 NPU | ✅ 已修（状态栏取真值 `engine_key`） | `app238` → `n_pass=7 / n_fail=0`（含 100 %/150 % 截图） |
| ④ 「有模块待处理」按钮截断 + 高级组截图 | ✅ 已修 | `app238` → G1 像素量按钮宽 95/164/85/164 px（≥ 需求 66/131/58/131） |
| ④ **ABBA / GUI 臂 / ASR RTF +0.122 复测** | ⛔ **未做**（需持 `MACHINE_LOCK`） | 本轮 **ASR 模块持锁**（pid 49688，20:34:25）⇒ 未抢锁、未占设备 |
| ② APP-065 C 交付物（每段音色表 ＋ 男/女各 3 段 wav ＋ 原声参考） | ⛔ **未做**（同上；且需先选一段有男有女的 SPE 片段） | 待办 |
| ⑤ D1 5 s 窗口 | ✅ 包侧落地（`ASR_FILES` 4 项）＋ **设备级实测 log「说话人旁路窗口：5.000 s」45 次** | `app237` → 9 PASS / 0 FAIL；`app243` → 判据⑧ |

🔴 **更正 `app241`**：它的 `ts=2026-11-04 16:58:45` ⇒ 分析的是**修复前**那次运行（影子包 17:08 才建好）⇒ 它的「clone 0 %」**对 17:25 那次运行不成立**；`app243` 是同一判据的**更正版**（切到最新 run）。
🔴 **判据口径坑（新增，写给下一轮）**：`.tts.jsonl` **跨运行累加**（本轮实测 2 段：旧 run 76 句全 preset ＋ 新 run 42 句）⇒ 必须按 `t_submit` 断层切 run（`id` 归零交叉验证一致）⇒ 否则**假 FAIL**（`app243` 的 K1/K4 反证就是防这个）。
🔴 **`app236` 复跑 FAIL ≠ 代码回归**：`real_failure_log_recheck` 依赖 `results/app/app223_device_out/tts_on_clone.log`，而该日志**已被 17:25 的成功运行覆盖**（故障串消失）⇒ 复跑件另存 `app245_regression_rerun_app236_recheck_input_changed.json`；**仓库原证据已 `git checkout` 复原（未覆盖）**。
🔴 **回归复跑口径**：`app215` 必须用**仓库 `.venv`**（WorkBuddy 的 python **无 numpy** ⇒ 27/2 假 FAIL）；换 `.venv` ⇒ **29 PASS / 0 FAIL**（复跑件 `app245_regression_rerun_app215_venv_29_0.json`）。`app227` **34/0**、`app229`/`app237` 复跑**逐字节一致**。

### §134 ✅ **APP-066（MiniMVP 最小客户包）· v1.0 的 6 处硬缺陷已修 ⇒ 新目录 `MiniMVP_v1.0-rc1`（7 个构建闸门全绿）** ｜ **本条已完成（构建层）｜ 设备级验收 (a)(b)(c) 未做（等锁）** ｜ **本条需等 reviewer 复核**（2026-11-04 21:10）

**🔴 v1.0（上一会话建的包）的 6 处硬缺陷**：

| # | 缺陷 | 证据 | rc1 的修法 |
|---|---|---|---|
| **D1（P0）** | **包无法启动**：`live_caption_app.py:121` 顶层 `import clone_collector`，而 v1.0 把它列进了「不带」清单 | v1.0 实测 `ModuleNotFoundError: No module named 'clone_collector'` | **保留** `clone_collector.py`（纯 Python 10.7 KB，App 顶层 import ＋ `_CLONE_*` 常量来源）⇒ 并把**导入冒烟测试做成构建闸门**（G1） |
| **D2** | app/ 是 **v2.2 的旧代码**（2026-11-02 01:33）⇒ 不含 APP-065 界面分组 / APP-067 ①②③④⑤ 修复 | 包内 `live_caption_app.py` mtime | app/ 改从**开发树 `live_caption/`** 取 **17 个生产模块** |
| **D3** | 10 个文件含**开发目录绝对路径** | `app242` → `scan.dev_path_hits` = 10 | 逐文件定点 scrub（`dev_repo`/`asr_module`/`tts_module`/`mt_module`）⇒ 包内命中 **0** |
| **D4** | **torch/CUDA 内容仍在**：OV 的 PyTorch/JAX/Paddle/TF 转换前端（**1 365** 处 `import torch` 命中）＋ `openvino_pytorch_frontend.dll` ＋ `numba/cuda/` ＋ `docs/CUDA_TTS.md` ＋ EXT 插件截图 | `app242` → `torch_import_hits=1365` / `cuda_dlls=1` / `cuda_code_hits=27` | 全部**移出**（大目录用**改名移出**，避免批量删除守卫）⇒ 包内 CUDA DLL **0**、app 内 CUDA 命中 **0** |
| **D5** | **体积口径错**：`app242` 的体积算的是**源包 v2.2**（13.67 GB / 99.84 %）⇒ 误判「最小包没变小」 | 实测 v1.0 = 7.24 GB | 体积分项一律对**已建成的包**现算 ⇒ rc1 = **6 843.9 MB = v2.2 的 52.41 %** |
| **D6** | 没有**新 MANIFEST / ACCEPTED**（包里是 v2.2 的 MANIFEST，且含 `hy_bench` 路径） | 包内 `MANIFEST.json` | 新生成 MANIFEST（`version=1.0-rc1`）＋ 重签 ACCEPTED（`code_fingerprint=5198846a…` / 17 个生产模块） |

**🔴 rc1 的 7 个构建闸门（`app244` → `gates` 全绿）**：G1 导入冒烟 17/17 ✅（**鉴别力**：同一判据在**已知有缺陷**的 v1.0 上 **FAIL** ✅）｜G2 开发目录路径 **0** ✅｜G3 CUDA/torch DLL **0** ✅｜G4 app 内 CUDA 命中 **0** ✅｜G5 包内 app/ == 开发树（17 文件 / **0 差异**）✅｜G6 体积 **52.41 %** ✅｜G7 鉴别力 ✅。

**包体**：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc1`（**10 507 文件 / 6 843.9 MB**；models 6 114.0 / python 728.7 / app 1.2 / docs 0.0）｜模型：ASR **INT8**（encoder 305.1 MB ＋ decoder-gpu 1 661.3 MB ＋ `embed_tokens_f16.npy` 593.5 MB）＋ MT **INT4** `mt2-int4sym-cw-q` 992.3 MB ＋ TTS **唯一一份 IR** 2 546.7 MB（＋ tokenizer/voices/weights）。设备：**ASR/MT = GPU.0，TTS = NPU**；GUI/CLI 无 CUDA 选项。

🔴 **v1.0 目录保留不动**（APP-066「任何已有版本的目录和 zip 都不覆盖、不删除」）⇒ 它是缺陷证据；剔除掉的内容在 `shared/minimvp_rc1_excluded/`（**改名移出**，非删除 ⇒ 不触发批量删除守卫）。
⛔ **未做（需设备级作业）**：3(a) CLI 跑 SPE 英文 5 分钟片段的完整链路指标 ＋ 配音 wav（`shared/app_listen/minimvp_v1.0/`）；3(b) GUI 冷启动（首次 NPU 编译耗时 / 第二次启动耗时）＋ 100 %/150 % 截图；3(c) **zip 未生成**（① 验收未过 ②「用户不通知不打包」）⇒ 预估 zip ≈ 6–6.5 GB（v2.2 的 11.23 GB）。
🔴 **待 reviewer 裁定（口径）**：APP-066 2 节「不能 import torch」的字面口径 —— 包内 app/ 仍有 **3 处** `import torch`（`backends.py` L64 `extract_audio_features` / L145 `TorchBackend.__init__` / L443 `HybridBackend.__init__`）⇒ **torch 本身未随包**（无 torch 目录、无 CUDA/torch DLL）⇒ 这三条是**开发工作流后端**，MiniMVP 走 OV 路线 ⇒ **运行不可达**；改开发版 `backends.py` 会**波及 v2.x** ⇒ 本轮**未擅自改**。第三方库内另有 1 337 处（`huggingface_hub` 的可选 torch 适配层、`openvino/tools/ovc` 的转换器等）⇒ 同样不可达。
🔴 **MT INT4 vs INT8 质量对比**（APP-066 1）：本包用 `mt2-int4sym-cw-q`（**对称 · per-channel weight**）；**开发版已有的 INT4 质量数据未引用到**（在 hy_bench/MT 模块侧）⇒ 已登记进 ACCEPTED 的 `pending_reviewer` ⇒ 待补或由 reviewer 指定口径。
