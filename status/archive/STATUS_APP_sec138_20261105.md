# STATUS_APP §138 正文（2026-11-05 15:28）

> 本件为 `status/app/STATUS_APP.md` §138 的**逐字正文**；STATUS 内只留速查表（APP-052 ④ 惯例）。
> 纠偏文件 `status/app/CORRECTIONS_APP.md` 本轮**只读、未修改、未提交**。
> 开工基线 ＝ 收尾复核：**SHA `f6001a0aa99464e5fcaebf400434ec1a6220e2cc3c9b4a4265c645ce02892596`／212 229 B／mtime 2026-11-05T14:33:28.815547／72 条**（APP-001..APP-072）⇒ reviewer 本轮未追加。

---

### §138 ✅ **APP-072（MiniMVP rc3 性能测试 zip）本条已完成** ｜ **APP-071 仍未完成（BLOCKING）** ｜ **本条需等 reviewer 复核**（2026-11-05 15:28）

> 🔴 **本节正文已原样归档** ⇒ `status/archive/STATUS_APP_sec138_20261105.md`（逐字保留，含 README 全文、全部产物元数据）。
> 🔴 开工/收尾 `CORRECTIONS_APP.md`：**SHA `f6001a0aa99464e5fcaebf400434ec1a6220e2cc3c9b4a4265c645ce02892596`／212 229 B／mtime 2026-11-05T14:33:28.815547／72 条**（APP-001..APP-072）⇒ 开工与收尾**逐字相同**（reviewer 本轮未追加；本模块**只读、未改、未提交**该文件）。
> 🔴 本轮 **last_ack：APP-070 → APP-072**（按 APP-072 原文「开始处理时写 last_ack=APP-072」；**APP-071 编号小于 072 但仍为 BLOCKING 未完成** ⇒ 见下方待办）。

#### 0. 本轮读到的两条新纠偏

| 编号 | 优先级 | 状态 |
|---|---|---|
| **APP-071** | BLOCKING（克隆音色串音：男声 3 段听上去是女声） | ⛔ **未完成**（本轮只做了根因分析第一部分，**未改一行产品代码**） |
| **APP-072** | 明确「**优先于** APP-069/070 的剩余项和 APP-071」 | ✅ **本条已完成**（含 GUI 冒烟） |

⇒ **执行顺序**：先做 APP-072（reviewer 明文优先），再做 APP-071。

---

#### 1. APP-072 §1 打包（zip）

| 项 | 值 |
|---|---|
| zip 路径 | `C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip` |
| 字节数 | **5 591 630 138 B**（5.208 GiB） |
| SHA256 | **`dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1`** |
| mtime | 2026-11-05 15:03:54 |
| 文件数 | **10 474**（zip 条目数 = 清单数，`n_mismatch=0`） |
| 顶层目录 | `Confucius4_LiveCaption_MiniMVP_v1.0-rc3`（唯一） |
| 打包命令 | `7z a -tzip -mx=5 -mmt=on -bso0 -bsp0 <zip> -i@_app279_zip_listfile.txt` |
| 优先级 | **BELOW_NORMAL**（不拖慢正在持锁的 TTS 作业） |
| 耗时 / rc | `wall_s=157.49` / `rc=0` |
| 证据 | `results/app/app279_rc3_perftest_zip_evidence.json`（1 259 B／mtime 15:03:58／SHA `25d5a42a63e5deb0…`） |

- ✅ **未覆盖任何已有目录/zip**：脚本在目标 zip 已存在时**直接 FAIL**；本轮**新建**了 zip，未删除/覆盖 `v2.1`／`v2.2`／`rc1`／`rc2` 的任何目录与 zip。
- ✅ **未用 TTS IR 一个都没删**（reviewer 明文「这次不删」⇒ 本轮 rc3 目录内 IR 保持原样）。
- ⚠️ 打包**跑了 7-Zip 后台进程**（PID 24112），已按纪律 `addpid` 登记进租约。

#### 2. APP-072 §2 打包前必过的三道闸门

##### 闸门① 黑名单扫描 —— ✅ 6 PASS / 0 FAIL

扫描对象是**从 zip 解压出来的干净副本**（`C:\minimvp_cleantest\Confucius4_LiveCaption_MiniMVP_v1.0-rc3`），**不是源目录** ⇒ 源目录里有 30 个被 `pkg_exclude` 排除的文件（babelvox 示例音色 8 + scipy 测试音频 22）⇒ 扫源目录会假 FAIL。

| 判据 | 结果 | 命中数 |
|---|---|---|
| ① 无会议录音（含 `260902_SPE` **任何**切片） | PASS | 0 |
| ② 无克隆音色（`clone_*.npz`） | PASS | 0 |
| ②b 无 `tts_speakers/` 音色文件落盘 | PASS | 0 |
| ④ 无 babelvox 示例音色（cindy/lou/phil/steve + .npy） | PASS | 0 |
| ⑤ 无开发目录绝对路径 | PASS | 0 |
| ⑥ 无 torch/CUDA 的 dll/pyd/`.cu`/`.cuh` | PASS | 0 |

- 证据：`results/app/app281_rc3_blacklist_scan_evidence.json`（1 130 B／mtime 15:26:50／SHA `da87506200d4f180…`）；脚本 `results/app/_app281_rc3_blacklist_scan.py`。
- 🔴 **反证（证明判据非恒真）**：同一脚本对**源目录**跑 ⇒ **判据④ FAIL**，抓到 **8 个** babelvox 示例音色（`cindy.json/cindy.npy/lou.json/lou.npy/phil.json/phil.npy/steve.json/steve.npy`）⇒ 扫描器**能识破**（证据 `results/app/_app281_counterexample_srcdir.json`）。
- 另做**独立交叉验证**（不依赖扫描器正则）：`find` 全包 ⇒ `*.cu`/`*.cuh`/`*.ptx` **0 个**；`*torch*.dll`/`*torch*.pyd`/`cudnn*.dll`/`cublas*.dll`/`nvrtc*` **0 个**；名为 `torch` 的目录只有 `python/Lib/site-packages/openvino/torch`（**OpenVINO 自带的 torch 适配层**，不是 PyTorch）。
- ⚠️ **诚实说明（不据此声称包内带 CUDA）**：`--check` 输出里 `NVIDIA GPU · CUDA Q8_0 / Q4_K` 显示「模型齐全」，**原因不是包内带 CUDA** ⇒ `_cuda_root()`（`app/live_caption_app.py` L428-441）在包内 `cuda/` 不存在时**回落到开发机家目录** `~/confucius4-r2t2`（该目录在本机存在）⇒ 是**开发机残留**。包内实测 `cuda/` 目录**不存在**、`find -iname "*cuda*"` 只命中 `transformers/kernels/**/cuda` 的**头文件**（`.h`，非 `.cu`/二进制）。**目标机上会正常显示「缺模型」**。

##### 闸门② NOTICE 许可证署名 —— ✅ PASS

- 补丁脚本：`results/app/_app278_rc3_notice_patch.py`（6 557 B／mtime 14:58:49／SHA `4803cbe0c725bc8a…`）⇒ **三块定点替换，每块要求唯一命中**（`hits=1`／`1`／`1`）。
- NOTICE 补丁前 9 643 B / SHA `b4505621ad2d702616b93116d8d42d101edb39dc5adf157f26bd04b61a827887` ⇒ 补丁后 **10 339 B / SHA `e9c9cfc34dba907ca28b35ffbb8437fdbc238cb510265ca2f0ff19b733e0728f`**；`crlf_preserved=true`。
- 首行已改为 `Confucius4 LiveCaption MiniMVP v1.0-rc3 — 第三方组件归属与许可证`。
- 必含项全部为 true：`Qwen3-ASR-0.6B`（Apache-2.0）／`Qwen3-TTS-12Hz-0.6B-Base`／`Hy-MT2-1.8B`（Apache-2.0）／`OpenVINO 2026.4.1`（Intel，Apache-2.0，另含 oneDNN/oneTBB 条款）／`BabelVox`／`babelvox-openvino-int8`。
- 证据：`results/app/app278_rc3_notice_patch_evidence.json`（947 B／mtime 14:58:57／SHA `326e1b1ed8d351d0…`），`verdict=PASS`。
- 🔴 **措辞纪律**：**未**声称随包附带这三个模型的许可证**全文**（包内确实没有对应 LICENSE 文件）⇒ 只做署名与许可证标识。

##### 闸门③ 解压后 `--check` + GUI 冒烟 —— ✅ 10 PASS / 0 FAIL

**解压副本**：`C:\minimvp_cleantest\Confucius4_LiveCaption_MiniMVP_v1.0-rc3`（**10 474 文件 / 7 176 154 805 B**，与打包清单一致）。

**`--check` 臂**（`results/app/_app282_rc3_check_arm.py` → `app282_rc3_check_evidence.json` 4 160 B／`app282_rc3_check_output.txt` 2 694 B／SHA `05de9cdedcf9a674…`）：

| 判据 | 结果 | 原始字段 |
|---|---|---|
| ① 退出码 0 | PASS | `rc=0`，`wall_s=11.86` |
| ② 含「环境正常」 | PASS | `matched=true` |
| ③ 探测到 Intel 集显 GPU.0 | PASS | `n_gpu0_hits=3` |
| ④ 探测到 NPU | PASS | `n_npu_hits=8` |
| ⑤ 报出 ASR 可用后端数 | PASS | `n_asr_backends=3` |

原始输出关键行（逐字）：

```
  [ OK ] numpy            2.4.6
  [ OK ] openvino         2026.4.1-22982-e213a147257-releases/2026/4
  [ OK ] openvino_genai   2026.4.1.0-3408-ab01d1771e4
  [ OK ] transformers     4.57.6
  [ OK ] sounddevice      0.5.6
  [ OK ] soundcard
  [ OK ] babelvox(Qwen3-TTS) 1.7.1
  [ OK ] qwen3tts 模型
  [ OK ] GPU.0    Intel(R) Graphics (iGPU)
  [ OK ] GPU.1    NVIDIA GeForce RTX 5050 Laptop GPU (dGPU)
  [ OK ] NPU      Intel(R) AI Boost
  [ OK ] Intel GPU · INT8           模型齐全
  [ OK ] Intel GPU · INT4-CW        GPU.0
  [ OK ] Intel NPU · INT4-CW        NPU
  结论：环境正常。ASR 可用后端 3 个，Intel 集显可用。
```

**GUI 冒烟臂**（`results/app/_app280_rc3_gui_smoke.py` → `app280_rc3_gui_smoke_evidence.json` 10 076 B／mtime 15:23:36／SHA `76a9dacbc382631c…`；截图 `results/app/app280_rc3_gui/gui_rc3.png` 65 925 B／SHA `61a99040b518e46d…`）：

| 判据 | 结果 | 原始字段 |
|---|---|---|
| ① GUI 起得来且模型加载完成（无崩溃） | PASS | `tts_load_s=8.5`，`model_loaded_at_s=27.9`，`wall_s=28.46`，`tts_device=NPU`，`stopped_reason=模型加载完成 ⇒ 停` |
| ② 抓到**完整主窗口**且非黑图 | PASS | `bytes=43745`，`size=[1455,1132]`，`client=[1439,1093]`，`is_main_window=true`，`n_candidates=3` |
| ③ ASR 出字 + MT 翻译 + 字幕渲染都通 | PASS | `rows_with_ink=163`，`max_row_ink=373`，`region=[1095,345]`；`mt_load_s=1.4`，`mt_label=Intel GPU · INT4-CW · GPU.0` |
| ③b **负对照**：字幕区下方空白区 0 墨迹 | PASS | `control_rows_with_ink=0`，`control_max_row_ink=0` |
| ④ 日志里没有 `0xC0000409` 崩溃 | PASS | `crash_marker_found=false` |

- 截图人工核验：窗口标题 `实时字幕 MiniMVP v1.0`；①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级 **五组齐全**；状态栏可见 **「就绪 · 设备 GPU.0 · 精度 INT8 · RTF 0.56 · 出字 303 ms · 段 3」**（ASR）、**「就绪 · 目标 中文 · 延迟 387 ms · 设备 GPU.0 · 精度 0 · 模型 Intel GPU（集显）· INT4-CW」**（MT）、**「就绪 · 设备 NPU · 语音 0.0 s · 语速 1.00× · 排队 12 · 首包 预合成 A · 首句 — · 播放滞后 0.0 s」**（TTS）；字幕区已渲染中英双语字幕（源音频 `SPE_0000_0500.wav`）。
- 🔴 **判据自身缺陷已修并复跑**（首跑 3 PASS / 1 FAIL）：第③项原用 CLI 模式的日志串 `[gpu_int8] 加载 x s`，而**GUI 模式下 ASR 就绪只写状态栏**（`var_status.set`，`app/live_caption_app.py` L3367）⇒ **不落盘会话日志** ⇒ 该串恒为 `None` ⇒ **假 FAIL**（截图人工核验证明 GUI 当时完全正常）。⇒ 改为**独立且更强**的判据：**字幕区深色像素内容**（同时证明 ASR 出字 ＋ MT 翻译 ＋ 渲染三条链路）＋ **负对照**（字幕区下方同宽空白区必须 0 墨迹）⇒ 复跑 **5 PASS / 0 FAIL**。
- 🔴 **判据非恒真的独立验证**：把真截图的字幕区整块涂白后，判据算出 `rows_with_ink=0` / `max_row_ink=0` ⇒ **必 FAIL**（证明不是恒真）。
- 设备纪律：两跑均**先取 `MACHINE_LOCK`**（PID 43172 / 6828）＋ **等安静窗口**（`wait_quiet_window_cpu` 45 s ⇒ `quiet_window.ok=True`），**跑完自动释放锁**；PID 已 `addpid` 登记进租约。

##### 打包一致性对账（证明除 NOTICE 补丁与新增 README 外未动 rc3 其它内容）

用打包前快照 `C:\Users\Trekker-PTL\shared\_rc3_snapshot_before_pack.json`（10 503 条，相对路径＋size＋mtime）对比打包后的 rc3 目录（10 504 条）：

| 项 | 结果 |
|---|---|
| 新增文件 | **1 个** = `README_perftest.txt`（本轮按 APP-072 §3 新建） |
| 删除文件 | **0 个** |
| 大小变化 | **1 个** = `NOTICE`（9 643 → 10 339 B，即 §2 闸门②的定点补丁） |
| 其余 10 502 个文件 | **逐条未变**（size 与 mtime 均一致） |

⇒ ✅ **rc3 目录除「NOTICE 补丁」＋「新增 README_perftest.txt」外一个字节都没动**。

#### 3. APP-072 §3 包内 `README_perftest.txt`（已落盘，**全文见下方**）

- 位置：`C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc3\README_perftest.txt`
- **9 155 B**／mtime 2026-11-05 15:00:35／SHA256 **`da3cd8ca1dabb1e28fdafb9ba243111f03daf513177782c6f7b545f32daa62b9`**／LF 行尾／**无 U+FFFD**。
- 已进 zip（`has_readme_perftest=true`），解压副本里也有。
- 内容覆盖 reviewer 要求的全部小节：定位／系统要求（CPU·GPU·NPU + **实测驱动版本号** NPU `32.0.201.14005`、集显 `32.0.101.8508`）／内存建议（**明确 APP-070 的「8 GB」是磁盘不是内存**）／磁盘（解压 ~6.7 GB + 首次编译缓存 ~8 GB + **缓存位置 `%LOCALAPPDATA%\Confucius4LiveCaption\`**）／已知问题 5 条／怎么测性能（CLI 命令 + `Get-Counter` 采 CPU 峰值均值的原因「包内无 psutil」）／要带回的结果文件清单／日志关键行说明／**Panther Lake 5 分钟 SPE 基准对照**（数字全部取自已落盘的 `app271`／`app263`／`app264` 证据，**非推算**）。

**README 全文**：

```
========================================================================
  Confucius4 LiveCaption · MiniMVP v1.0-rc3 —— 性能测试版说明
========================================================================

【本包定位】
  这是 **MiniMVP v1.0-rc3 的性能测试构建**，用于在其他机器上测
  ASR / MT / TTS 的实时性能，**不是正式发布版**。
  · 正式验收（APP-066 §4）、桌面快捷方式、其余 bug 修复 → 留到下一版
    （rc4 / v1.0）。
  · 本版**已修**：字幕 dump 落盘错位、配音全零段、说话人旁路缺席、
    内部素材泄漏、TTS 精度文案口径。
  · 本版**未修**（已知问题见下）：克隆音色可能串音、GUI 偶发崩溃、
    首次 NPU 编译 20 分钟、未用 IR 仍在包里、MT 为 INT4。

【系统要求】
  · CPU     ：Intel Core Ultra（Panther Lake / Core Ultra 200 系列）
  · GPU     ：Intel 集显（GPU.0），**必须**能跑 OpenVINO GPU 插件
  · NPU     ：Intel NPU（TTS 走 NPU）
  · 驱动版本建议（本包实测机 = Intel Core Ultra 7 356H / Panther Lake）：
        Intel NPU 驱动   >= 32.0.201.14005（实测：32.0.201.14005）
        Intel 集显驱动   >= 32.0.101.8508 （实测：32.0.101.8508）
        OpenVINO         2026.4.1（**随包自带**，不需另装）
    ⚠️ NPU 驱动版本直接决定「首次 NPU 编译」能不能成功、以及快慢。
      驱动过旧 ⇒ NPU 插件加载失败或编译极慢。
  · 内存   ：建议 **>= 16 GB**。
        ⚠️ 说明：APP-070 里写的「8 GB」是**磁盘**占用（首次运行的 NPU
        编译缓存），**不是内存**。本包**尚未实测峰值内存**
        （打包时设备被其它模块占用），所以这里给的是**保守建议**，
        8 GB 机器可能出现内存不足（OV 编译期内存占用较高）。
  · 磁盘   ：解压后 **约 6.7 GB**（10 503 个文件）
            ＋ 首次运行的编译缓存 **约 8 GB**
               （tts_npu_cache ≈ 5 GB、ov_cache ≈ 2 GB、mt_cache ≈ 1 GB）
            ⇒ **合计留 15 GB 以上**。
            缓存写在 **用户目录**（不是包内）：
                %LOCALAPPDATA%\Confucius4LiveCaption\
            （想释放空间：关掉程序后删掉这个目录即可，下次会重新编译。）

【已知问题】（实测记录，请勿当 bug 报给我们，先看这里）
  1. **首次启动 NPU 编译约 20 分钟**
     实测 rc2：TTS 模型加载 **1209.3 s**（全新 LOCALAPPDATA，无缓存）。
     ⚠️ **rc3 的 A+C（后台编译 + 首句先出）方案尚未做设备级验证**，
        所以 rc3 的首次启动可能仍是「等全部编完才出声」。
     第二次启动（缓存已热）：**9.5 s**（省 1199.8 s，≈127×）。
  2. **GUI 启动偶发崩溃 0xC0000409**
     rc2 实测 6 次启动里崩 2 次；**rc3 未做有效复测**。
     ⇒ 建议用 **CLI** 做性能测试（见下），GUI 只做功能确认。
  3. **包内含约 0.6–1 GB 未使用的 TTS IR**
     （NPU 路径不加载那些 IR；本版为避免「删完要重跑 e2e」而保留）
  4. **MT 是 INT4**（对称 · per-channel weight）⇒ 质量比 INT8 略低。
  5. **克隆音色（跟随说话人）可能串音**：用户抽听 v23_clone 发现
     男声 3 段听上去是女声 ⇒ 克隆音色登记逻辑正在修（下一版）。
     ⇒ **本版做性能测试时请用 `--tts-voice A`（预设音色）**，
        不要用 `--tts-voice follow_speaker`。

【怎么测性能】
  ⚠️ 本包**不带任何测试音频**（不夹带内部素材）⇒ 请自备一个 wav。

  ── 步骤 1：环境自检（不占设备，几秒）──────────────────────────
      cd <解压目录>
      python\python.exe app\live_caption_app.py --check

  ── 步骤 2：跑 5 分钟音频（CLI）───────────────────────────────
      cd <解压目录>
      python\python.exe app\live_caption_app.py ^
        --cli --file "D:\你的音频.wav" ^
        --engine gpu_int8 --asr-device GPU.0 ^
        --translate zh --mt-device GPU.0 --mt-engine gpu_int4cw ^
        --tts on --tts-voice A --tts-device NPU ^
        --speaker off --max-seconds 300 ^
        --out perf_transcript.txt ^
        --tts-jsonl perf_tts.jsonl ^
        --spk-seg-jsonl perf_spk_seg.jsonl ^
        > perf_run.log 2>&1

      说明：
        --file            你的音频文件（wav）
        --max-seconds 300 跑 5 分钟
        --tts-voice A     用预设音色 A（**不要**用 follow_speaker，见已知问题 5）
        --out             定稿文本（逐句）
        --tts-jsonl       **逐句配音遥测**（RTF / 首包 / 积压 / wav 指标）
        --spk-seg-jsonl   逐段（音频区间 + 说话人）表
        perf_run.log      **全量运行日志**（ASR/MT/TTS 的汇总数字都在里面）

  ── 步骤 3：把 CPU 峰值/均值也采下来（App 本身不采）────────────
      包内没有 psutil，App 不输出 CPU 占用 ⇒ 用 Windows 自带计数器，
      在**另一个** PowerShell 窗口里跑：

        Get-Counter '\Process(python*)\% Processor Time' -SampleInterval 1 `
          -MaxSamples 3600 | Export-Counter perf_cpu.csv

      （跑完后 perf_cpu.csv 里取 python 进程的 max / 平均即可；
        或直接用任务管理器「性能」页目测峰值。）

  ── 步骤 4：把结果带回来 ─────────────────────────────────────
      请把下面这些文件一起带回来（或压缩成一个 zip）：
        perf_run.log          运行日志（含 ASR/MT/TTS 汇总行）
        perf_transcript.txt   定稿文本
        perf_tts.jsonl        逐句配音遥测
        perf_spk_seg.jsonl    逐段说话人表
        perf_cpu.csv          CPU 采样（若做了步骤 3）
        另附：机器型号、CPU/内存、NPU 与集显驱动版本

  ── 步骤 5：怎么读日志里的关键数字 ────────────────────────────
      在 perf_run.log 里搜这几行：
        [gpu_int8] 音频 300.0s  墙钟 300.8s  RTF(计算) 0.833
            出字延迟中位 627 ms  最大积压 1.8s  段 46
              ⇒ ASR：RTF / 出字延迟中位 / 最大积压
        [翻译] ... 延迟中位 687.1 ms  P95 1295.8 ms  TTFT 190.3 ms
              ⇒ MT：延迟中位 / P95 / TTFT
        [TTS] 最终统计（close 后）：提交 76  播完 76  丢弃 0 ...
              ⇒ TTS：积压最大 / 丢弃句数 / 结尾滞后
        [tts_engine] 模型加载完成（1209.3 s）
              ⇒ 首次 NPU 编译耗时（第二次启动只有几秒）
      逐句 RTF 在 perf_tts.jsonl 里（每行一个字段 synth_rtf / t_first_packet）。

【本机（Panther Lake）基准对照】
  机器：Intel Core Ultra 7 356H（Panther Lake，iGPU + NPU 第 5 代）
        内存 32 GB；集显驱动 32.0.101.8508；NPU 驱动 32.0.201.14005
  音频：SPE 前 5 分钟（内部测试音频，**不在本包内**）
  命令：与上面步骤 2 完全相同（--engine gpu_int8 / --tts-device NPU /
        --mt-engine gpu_int4cw / --translate zh）

  实测结果（rc3，设备级 3(a) 验收，76 段全部出声）：
    · 总墙钟            381.86 s（音频 300 s）
    · ASR   RTF(计算)   0.833
             出字延迟中位 627 ms
             最大积压     1.8 s
             段数         46
    · MT    延迟中位    687.1 ms
             P95          1295.8 ms
             TTFT         190.3 ms
             吞吐         25.4 tok/s
    · TTS   合成 RTF 中位 1.0162   P95 1.3799   最大 1.5603
             首包延迟中位 0.5763 s   P95 0.8136 s   最大 1.0705 s
             提交 76 / 播完 76 / 丢弃 0 / 空句 0 / 失败 0
             **最大积压 105.12 s**（TTS 比实时慢 ⇒ 队列会积压；
               这是当前最主要的瓶颈）
             结尾滞后 68.97 s
    · 配音内容判据      PASS（76 段全部非静音、无全零段）
    · 首次 NPU 编译     1209.3 s（rc2 实测；rc3 未复测）
    · 第二次启动         9.5 s（rc2 实测，缓存已热）
    · CPU 峰值/均值     **本机未采集**（打包时设备被其它模块占用）
                        ⇒ 请在目标机按步骤 3 采一份，我们再对比。

  ⚠️ **TTS RTF ≈ 1.0 意味着「勉强跟得上、不富余」**：在更慢的机器上
     积压会更大。测的时候请重点看「最大积压」这个数。

【许可与归属】
  见包内 NOTICE（Qwen3-ASR / Qwen3-TTS / Hy-MT2 / OpenVINO / babelvox /
  djwarf 等的归属与许可证）与 THIRD_PARTY.md。

【本版不含】
  会议录音、克隆音色、同事的声音、EXT 插件与桥接服务、
  CUDA / torch 相关内容、开发者脚本。
========================================================================
```

> ⚠️ README 里「解压后约 6.7 GB（10 503 个文件）」中的文件数是**打包前源目录**的数（10 503）；**zip 内实际 10 474 个文件**（差 30 = `pkg_exclude` 排除的 babelvox 示例音色 8 + scipy 测试音频 22）。体积口径（~6.7 GB）按源目录 7 176 154 805 B / 6.683 GiB 给出，与 zip 内 10 474 文件的体积差 < 0.1 %。

#### 4. APP-071 —— ⛔ **未完成**（BLOCKING），本轮只做了根因分析第一部分

**reviewer 要求**：(a) 每个已登记音色落盘诊断（参考 PCM wav／起止时间／来源 seg／`spk_conf`／x-vector npy）｜(b) x-vector 余弦矩阵（登记 S1/S2/S3 × 原声各说话人干净段参考向量，**S2 对原声 S2 的余弦必须高于对 S1/S3**）｜(c) 修复登记逻辑（`spk_conf ≥ 阈值` ＋ 连续干净 ≥ 2.5 s、切换边界前后 0.5 s 不取、低 conf 先 pending、有更好片段允许升级一次）｜(d) 重交 `shared\app_listen\v23_clone_r2\`（**不覆盖 `v23_clone`**），男女各 3 段 + 音色表 + 每段输出 F0 中位数；闸门：男声克隆 F0 中位 **< 160 Hz**、女声 **> 170 Hz**，且输出 x-vector 对目标说话人余弦 > 对其他说话人｜(e) 所有设备作业持 MACHINE_LOCK + session_lease；**本条未通过前 v2.3 不打包**。

**本轮已确证的根因线索（只读分析，未改代码）**：

| # | reviewer 的怀疑 | 本轮查证 | 结论 |
|---|---|---|---|
| 1 | **S2 的参考音频取错了**（S2 首次出现在 seg1，9.6–19.2 s，`spk_conf=0.129`，极可能是 S1 女声或边界混音） | `shared/app_listen/v23_clone/seg_voice_table_by_seg.csv` 中 **S2 首次出现确为 `seg_id=1`／`t0=9.6`／`t1=19.2`／`span=9.6 s`／`spk_conf=0.1292`／`spk_source=retry`／`switch S1→S2`** | 🔴 **高度吻合 reviewer 的怀疑**，但**余弦矩阵尚未算** ⇒ 未定案 |
| 2 | **登记/取音色时键错了** | `live_caption/speaker_voice.py`：`note_final()` 只做 `seg → spk` 绑定 ＋ 合并 `clean_ranges`，**完全不检查 `spk_conf`**；`ready_to_embed()` 只按 `dur_s` 与 `MIN_S=1.5`／`REFINE_S=3.0` 判；`voice_for_sentence()` 只有 `row['voice']=='clone'` 才返回该 spk | 🔴 **当前代码没有 `spk_conf` 门槛** ⇒ 低置信度首检会被直接登记 |
| 3 | **补登记时用的是「当前最新音频」而不是该说话人自己的片段** | `live_caption/live_caption_app.py::_spk_pcm_for()` 用 `self._spk_voices.clean_ranges_of(spk)` ＋ `speaker_tracker.pcm_for_ranges(..., keep_t0=...)` ⇒ **取的是该 spk 自己的 clean ranges**（已用 `keep_t0` 修正环形缓冲与全局时间轴错位） | 🟡 该路径**看起来正确**，但 `_pending_spk_voice`（模型未就绪时排队）**没有「低置信度 pending」语义** ⇒ 需 (c) 补 |

⇒ **(a)(b)(c)(d) 全部未做**：(a) 诊断未落盘；(b) 余弦矩阵未算；(c) 代码**一行未改**；(d) `v23_clone_r2/` **未生成**。**⇒ 不能声称 APP-071 有任何进展以外的内容。**

**⛔ v2.3 不打包**（APP-071 (e) 明文）。

#### 5. 本轮产物清单（全量元数据）

**仓库内**（`confucius4-openvino`）：

| 文件 | 字节 | mtime | SHA256 |
|---|---|---|---|
| `results/app/_app278_rc3_notice_patch.py` | 6 557 | 2026-11-05 14:58:49 | `4803cbe0c725bc8a…` |
| `results/app/app278_rc3_notice_patch_evidence.json` | 947 | 2026-11-05 14:58:57 | `326e1b1ed8d351d0…` |
| `results/app/_app279_rc3_perftest_zip.py` | 8 322 | 2026-11-05 15:01:08 | `65a49a003f2aa374…` |
| `results/app/_app279_zip_listfile.txt` | 1 033 588 | 2026-11-05 15:01:17 | `e2ac92dab82e240f…` |
| `results/app/app279_rc3_perftest_zip_evidence.json` | 1 259 | 2026-11-05 15:03:58 | `25d5a42a63e5deb0…` |
| `results/app/_app280_rc3_gui_smoke.py` | 20 683 | 2026-11-05 15:21:58 | `e25bca0cb40e5fea…` |
| `results/app/app280_rc3_gui_smoke_evidence.json` | 10 076 | 2026-11-05 15:23:36 | `76a9dacbc382631c…` |
| `results/app/app280_rc3_gui/gui_rc3.png` | 65 925 | 2026-11-05 15:23:36 | `61a99040b518e46d…` |
| `results/app/app280_rc3_gui/gui_rc3.log` | 160 | 2026-11-05 15:23:12 | `2fc2d6eca60f5268…` |
| `results/app/_app281_rc3_blacklist_scan.py` | 6 943 | 2026-11-05 15:26:32 | `96d2b527fba4e55f…` |
| `results/app/app281_rc3_blacklist_scan_evidence.json` | 1 130 | 2026-11-05 15:26:50 | `da87506200d4f180…` |
| `results/app/_app281_counterexample_srcdir.json` | 1 130 | 2026-11-05 15:26:50 | 反证件（源目录 ⇒ 判据④ FAIL） |
| `results/app/_app282_rc3_check_arm.py` | 4 146 | 2026-11-05 15:27:24 | `f3aaa9e96c8fd5fd…` |
| `results/app/app282_rc3_check_evidence.json` | 4 160 | 2026-11-05 15:27:48 | `02810b680315ff2c…` |
| `results/app/app282_rc3_check_output.txt` | 2 694 | 2026-11-05 15:27:48 | `05de9cdedcf9a674…` |

**包外产物**：

| 文件 | 字节 | mtime | SHA256 |
|---|---|---|---|
| `C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc3_perftest.zip` | 5 591 630 138 | 2026-11-05 15:03:54 | `dda6f229e9d1e70accc4417b328d33b8c929f868a033ad4546e39d7d0f2d45f1` |
| `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc3\README_perftest.txt` | 9 155 | 2026-11-05 15:00:35 | `da3cd8ca1dabb1e28fdafb9ba243111f03daf513177782c6f7b545f32daa62b9` |
| `C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc3\NOTICE` | 10 339 | 2026-11-05 14:58:57 | `e9c9cfc34dba907ca28b35ffbb8437fdbc238cb510265ca2f0ff19b733e0728f` |

#### 6. 纪律自检

- ✅ **未修改 `status/app/CORRECTIONS_APP.md`**（只读；开工/收尾 SHA、字节、mtime、条数逐字相同）。
- ✅ **未覆盖/未删除任何旧版本目录与 zip**（v2.1／v2.2／rc1／rc2 一字未动）；本轮 zip 是**新建**文件。
- ✅ **未使用 `--same-version`**。
- ✅ **未原地改用户正在测试的安装目录**（rc3 目录只加了 README 与 NOTICE 补丁，**都在本轮明示范围内**；`live_caption\` 开发树**一行未改**）。
- ✅ **设备作业全部持 `MACHINE_LOCK` ＋ session_lease**（PID 43172／6828；`addpid` 已登记）。
- ✅ **未通过 FTP 或任何外部服务分发**（zip 只落在 `shared\minimvp\` 本地）。
- ✅ **未通知用户**（等 reviewer 转告）。
- ✅ **未打 v2.3 包**（APP-071 未过）。
- ✅ **git 只提交 App 模块自己的文件**（见下方「本轮 git」）。

#### 7. 本轮 git

- 分支：**main**（仓库只保留 main 分支）；**普通 push，未 force push**。
- 提交内容：`status/app/STATUS_APP.md`（§138）、`status/archive/STATUS_APP_sec138_20261105.md`、`status/app/_sec138_body.md`（章节源）、`results/app/_app278*`／`_app279*`／`_app280*`／`_app281*`／`_app282*`（脚本与证据）。
- 🔴 **绝不提交** `status/app/CORRECTIONS_APP.md`（reviewer 独占）；🔴 **不吞** ASR／MT／TTS 其它模块的未提交改动（逐文件 `git add`，**禁 `-A`**）。
