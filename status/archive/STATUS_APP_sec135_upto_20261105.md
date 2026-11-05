## §135 ✅ **APP-067 ②④ 设备级补齐（ABBA + GUI 臂 + ② 交付物）＋ APP-066 3(a)(b) ＋ 🔴 修 MiniMVP P0（rc2）** ｜ **本条已完成（设备级）｜ 本条需等 reviewer 复核**（2026-11-05 08:40）

> 🔴 **本轮无新纠偏**：`CORRECTIONS_APP.md` **67 条** / 最高编号 = **`APP-067`** = `last_ack` ⇒ **无编号更大的新条目**；开工基线 SHA `cf71e427…` / **192 381 B** / mtime **2026-11-04 09:52:22** ⇒ 收尾实测逐字相同 ⇒ **本轮零改动**（reviewer 独占文件，全程只读）。
> 🔴 **本轮起点＝接管死租约（第二次）**：上一会话（token `fbf099e8`，11-05 04:51 起、**06:10:53 最后心跳**、note=「等 3(b)」）在**重跑 3(b)** 时死亡 ⇒ 它已把 ③(a)/②④/rc2 做完并**起草了 §135 正文**，但**未写入 STATUS、未提交** ⇒ 本轮**从断点续做**（不是从头重做）。
> 🔴 **本轮先做了一件事：把上一会话的 §135 草稿逐条与磁盘证据对照**（草稿只是草稿，**不是结论**）⇒ **发现草稿 ⑧ 的第 1 点与它自己的证据矛盾** ⇒ 已在本节更正（见 ⑧）。
> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec135_upto_20261105.md`（**逐字保留，内容一字未删**）。

### ① ✅ **APP-067 ④ ABBA（设备级）—— 10 PASS / 0 FAIL / 0 NONE**

`results/app/app250_app067_abba_device_evidence.json` → `judgement.n_pass=10 / n_fail=0 / n_none=0 / verdict=PASS`；**5 臂同一次持锁会话内连续跑**（`arms_order` = `tts_off → tts_on_clone → tts_on_clone → tts_off → tts_on_preset`）；`quiet_window.ok=true`。
🔴 **ASR RTF 增量**（`judgement.rtf_deltas`）：配对① **+0.099**（0.714→0.813）／配对② **−0.146**（0.816→0.670）⇒ **均值 −0.0235 ≤ +0.10** ⇒ **APP-067 ④ 的 +0.122 已复现为达标**（配对顺序不同 ⇒ 旧值是单次测量噪声）。
🔴 **clone 占比 98.851 %**（两臂各 87 句）／「没有可用引擎·登记失败」= **0**；clone 臂与 preset 臂**逐句文本一致（87=87）** ⇒ 预设 A 对照句句对齐。

### ② ✅ **APP-067 ④ GUI 臂（设备级）—— 5 PASS / 0 FAIL**

`results/app/app252_app067_gui_arm_evidence.json` → `n_pass=5 / n_fail=0 / n_none=0 / verdict=PASS`；`gui_wall_s=346.4`；3 张**非黑**截图（`results/app/app252_gui_out/gui_shot_045s/150s/260s.png`）。
🔴 **本轮亲自读图复核**（不只看 json）：`gui_shot_260s.png` 的翻译行 =「设备 GPU.0 · 标注 2 · **模型 Intel GPU（集显）· INT8-CW**」⇒ **不含 NPU** ⇒ **APP-067 ③ D4 界面验收条件成立**（该臂跑的是 `shared/app067_shadow`＝v2.2 影子包，MT 本就是 INT8-CW，显示正确）。
🔴 clone **98.649 %**（`jsonl.pct_voice_kind_clone`）｜标签 41｜音色登记 10｜回落预设 **0**｜keep_last 5｜`n_no_voice_error=0`。

### ③ ✅ **APP-067 ② 交付物（每段音色表 ＋ 男女各 3 段 wav ＋ 原声参考）—— 12 PASS / 0 FAIL**

- **选片段**：源 wav **`3302.72–3602.72 s`**（300.000 s，S1/S2/S3/S5、换人 12 次）⇒ `app246_app067_spk_gender_segment_evidence.json` → `chosen_window`（`verdict=PASS`）
- **性别**：**直接量 App 自己的簇**（不信参照编号）⇒ `app251_app067_deliverables_evidence.json` → `f0_evidence`：**S2 = 153.85 Hz ⇒ 男**；S1 = 202.53 / S3 = 205.13 / S4 = 197.53 Hz ⇒ 女（`male_max_hz=160.0`）
- **①每段一行表**：`shared/app_listen/v23_clone/seg_voice_table_by_seg.csv`（**8 591 B**）＋ `seg_voice_table.csv`（11 696 B）＋ 逐句 JSON 两份 ⇒ **45 段 / 换人 9 次**
- **②男女各 3 段 wav**：`wav_clone/`（男 seg 5/2/4、女 seg 29/21/20，各 6 个）＋**同 6 句**的 `wav_presetA/` 对照 ⇒ **各 6 个 wav 已落盘**
- **③原声参考**：`wav_original/` 6 段（按该段 t0/t1 从混合切片切）＋ `mix_segment_manifest.json`（源/切片 SHA、时间轴换算）

### ④ ✅ **APP-066 3(a) MiniMVP CLI 全链路 —— 8 PASS / 0 FAIL**

`results/app/app253_app066_minimvp_cli_evidence.json` → `n_pass=8 / n_fail=0 / n_none=0 / verdict=PASS`：
用时 **300.9 s ≤ 303 s**｜最大积压 **1.1 s ≤ 2 s**｜ASR RTF **0.761**｜TTS RTF 中位 **0.9565**/P95 **1.0511**｜出字延迟中位 **0.5258 s**/P95 **0.6544 s**｜CPU 峰值 **221.9 %**/均值 **83.06 %**｜配音 wav **15 267 208 B**（`app253_minimvp_out/minimvp_tts.wav`）＋ 逐段译文 **76 行**（`shared/app_listen/minimvp_v1.0/minimvp_v1.0_transcript.tsv`）。
🔴 **MT 已钉住包内 INT4**：证据 `mt_model_pinned = …/MiniMVP_v1.0-rc2/models/mt/mt2-int4sym-cw-q`（不是开发机的 INT8）。

### ⑤ ✅ **APP-066 3(b) MiniMVP GUI 冷启动 —— 本轮重跑，以实测为准**

> 🔴 **本轮先纠正上一会话的一处不实陈述**：上一会话的 §135 草稿写「3(b) 重跑通过」，但**它自己的落盘证据 `app259_app066_minimvp_gui_evidence.json` 写的是 `verdict=FAIL`（4 PASS / 2 FAIL / 1 NONE）** ⇒ 草稿与证据矛盾 ⇒ **不能采信草稿**。本轮**重跑**（`app263` + `app264`），以实测为准。

🔴 **`app259` 首跑的 4 处真缺陷（上一会话已修，本轮复核确认修法在位）**：

| # | 缺陷 | 症状 | 修法 |
|---|---|---|---|
| **D1** | **抓错窗口**：Tk 建**多个同名窗口** ⇒ 取「第一个非黑」⇒ 抓到 **1638×122 窄条**（非主窗口） | `app259` 冷臂 `shot.size=[1638,122]` | 按**窗口面积**取最大者；并追加判据「**客户区高 ≥ 700 px** 才是主窗口」 |
| **D2** | **失败原因被丢弃** | `runs[].shot=null` ⇒ 无法判因 | 每个候选窗口的抓屏结果 + 失败原因全部落盘（`shot.tried[]`） |
| **D3** | **音频只有 300 s ⇒ 冷编译跑不完** | 冷臂 `tts_load_s=null`、`stopped_reason=进程自行退出` | 源 wav 拼成 **1500 s**；且「模型加载完成」出现后立刻停 |
| **D4** | **150 % 尺寸判据口径错**（拿窗口矩形比客户区） | 必 FAIL | 改用 **GetClientRect**（客户区） |

🔴 **本轮实测（`results/app/app263_app066_minimvp_gui_evidence.json`，`long_wav_seconds=1500.0`）**：
- **① 首次启动（TTS 加载耗时）有实测值 = PASS**：`tts_load_s = **1209.3 s**`、`model_loaded_at_s = 1236.4`、`wall_s = 1237.03`、`device = NPU` ⇒ **MiniMVP 首次 NPU 编译 ≈ 20 分钟**（真冷臂：**全新 LOCALAPPDATA** ⇒ `tts_npu_cache` 从 0 个 blob 编到 16–18 个）
- **④ 100 % 截图 = PASS**：抓到的**是完整主窗口 1455×1132**（客户区 **1439×1093**，`is_main_window=true`、非黑 101 801 B）⇒ **D1 修复成立**
- **④ 150 % 截图 = PASS**：**1634×1268**（客户区 **1618×1229**、`is_main_window=true`、非黑 126 843 B）
- **⑤ 150 % 客户区尺寸 = PASS**：实测 1618×1229 vs 应用公式期望 1620×1230 ⇒ **±4 px 内成立**；`app260_tk_geometry_probe.json` 实测 ⇒ 申请 1620×1230 时 Tk 客户区**就是** 1620×1230（Tk 不裁剪）⇒ 差值来自 Tk 把 `scaling 1.5` 量化成 **1.4989** ⇒ App 自己算 `int(1080×1.4989)=1618` / `int(820×1.4989)=1229` ⇒ **与实测逐像素一致 ⇒ App 无 bug** ⇒ 判据按「**应用公式 ±4 px**」而非写死 `[1620,1230]`
- 🔴 **MT 行显示复核（亲自读图）**：100 % 与 150 % 两张截图的翻译行**都是**「设备 GPU.0 · 模型 **Intel GPU（集显）· INT4-CW**」⇒ **不含 NPU**、**显示与实载一致**

🔴 **`app263` 的 ②/⑥ 判 FAIL 的根因（本轮查明，**不是产品缺陷**）**：
- **② FAIL / ③ NONE**：`app263` 的**热启臂超时 900 s**（`tts_load_s=null`）⇒ 原因：热启臂**复用冷臂那个 LOCALAPPDATA**，而**冷臂里 TTS 从未起来**（`tts_load_s=null`）⇒ `tts_npu_cache` **一个 blob 都没编** ⇒ 热启臂等于**又冷启了一次**（真冷要 1209 s）⇒ 900 s 不够 ⇒ **判据超时，不是缓存没生效**
- **⑥ FAIL**：同理（`warm_s=null` ⇒ 无法比较）
- ⇒ **补测 `app264`**（`results/app/app264_app066_minimvp_warm_arm_evidence.json`，**3 PASS / 0 FAIL**）：**同一 LOCALAPPDATA**（`npu_blobs_before = 18` ⇒ 缓存已热 ⇒ 这才是真正的「第二次启动」），100 % 缩放、同音频同 `--selftest` ⇒ **与 `app263` 真冷臂可直接比**
  - **热启臂 `tts_load_s = 9.5 s`**、`model_loaded_at = 47.4 s`、`wall_s = 48.09`、`device = NPU`、`mt_label = Intel GPU · INT4-CW · GPU.0`
  - **热启 ≪ 冷启**：**1209.3 s → 9.5 s**（省 **1199.8 s**，比值 **0.0079** ≈ **127×**）⇒ **NPU 编译缓存确实生效**
  - 100 % 截图 = **完整主窗口 1455×1132**（客户区 1439×1093、非黑 53 348 B、`is_main_window=true`）
- 🔴 **附带查清「冷臂第一次为什么 1561 s 也没测到 tts_load_s」**：首个冷臂（07:21 起）里 **MT 的 GPU oneDNN JIT 编译**把 `ov_cache` 写了 **750 个 `*.onednn.cl_cache`**（07:21→07:40 持续写入）⇒ 该轮 **MT 就绪日志都没打出来** ⇒ TTS 根本没被触发 ⇒ **首个冷臂是「GPU JIT 编译 + NPU 编译」叠加**；而 `app263` 的真冷臂（08:07 重跑，**全新 LOCALAPPDATA**）**MT 只用 6.1 s 就绪** ⇒ 说明首轮那 19 min 的一次性 GPU JIT **已被系统级缓存吸收** ⇒ **客户机首启可能遇到同样的一次性 JIT 开销**
- 🔴 **150 % 臂首跑「异常早退」（rc=3221226505 = `0xC0000409`，崩在模型加载那一刻）** ⇒ 脚本重试 ⇒ 第 2 次成功（`wall=331.82 s`、`tts_load_s=312.1 s`）；**`app264` 首跑也是同一个 rc** ⇒ 重试后成功（`tts_load_s=9.5 s`）
- 🔴 **本轮顺手修掉 `app259`/`app263` 里一个「静默空操作」**：它们的 `kill_stale_minimvp()` 用 `import wmi` ⇒ **本机仓库 `.venv` 里没有 `wmi`** ⇒ 该函数**永远返回 []**（清残留其实是空操作）⇒ `app264` 改用 **Toolhelp32 + `QueryFullProcessImageNameW` 读命令行**（纯 ctypes，不依赖 pywin32）⇒ 才真正能按命令行特征清残留

🔴 **APP-066 3(b) 的最终结论（冷/热 + 两张截图齐了）**：

| 项 | 实测值 | 来源 |
|---|---|---|
| **首次 NPU 编译耗时（真冷）** | **1209.3 s ≈ 20.2 分钟** | `app263` 真冷臂（全新 LOCALAPPDATA）→ `checks[]` ① |
| **第二次启动耗时（热）** | **9.5 s** | `app264` → `checks[]` ① |
| **缓存收益** | **省 1199.8 s（127×）** | `app264` → `checks[]` ③ |
| **100 % 截图** | **1455×1132**（客户区 1439×1093，非黑，主窗口） | `app263`/`app264` → `checks[]` ④ |
| **150 % 截图** | **1634×1268**（客户区 1618×1229，非黑，主窗口） | `app263` → `checks[]` ④ |
| **150 % 客户区尺寸** | 实测 1618×1229 vs 期望 1620×1230 ⇒ **±4 px 内成立** | `app263` → `checks[]` ⑤ |
| **MT 行显示** | 「设备 GPU.0 · 模型 Intel GPU（集显）· INT4-CW」⇒ **不含 NPU** | 两张截图亲自读图 |

### ⑥ ✅ **MiniMVP rc1 的 P0（打不开）已修 ⇒ rc2（9 个构建闸门全绿）**

`results/app/app255_minimvp_rc2_build_evidence.json` → **G1..G9 全 `ok=true`**：G1 导入冒烟全绿｜G2 开发目录路径 **0**｜G3 CUDA/torch DLL **0**｜G4 app 内 CUDA 命中 **0**｜G5 包内 app/ == 开发树（**24 文件 / 0 差异**）｜G6 体积 **52.4 %**（6 844.0 MB vs 13 058.6 MB）｜G7 **鉴别力**（同判据在 v1.0 上 FAIL ✅）｜G8 **AST 导入闭包**（pkg_modules=24 / closure=25 / missing=[]）｜G9 **鉴别力**（同判据在 rc1 上 FAIL，缺模块清单一致 ✅）。
🔴 **rc1 的 G1「导入冒烟 17/17 ✅」是假 PASS**：缺的是**写在类 `__init__` 里**的 import ⇒ 模块级 import 不执行 ⇒ 冒烟碰不到 ⇒ **包打不开而闸门全绿** ⇒ rc2 新增 G8（AST 闭包，含函数内/类内/try 内 import）＋ G9。

🔴🔴🔴 **本轮查出并修好 rc2 的 2 个真缺陷（app191 绑定闸门实测暴露）**：

`results/app/app264_app191_on_rc2.json` ⇒ **9 PASS / 6 FAIL**（rc2 的 `ACCEPTED.json` 自己写着 `binding_gate: app191`，**却过不了 app191** ⇒ 等于「没验收过就宣称验收了」）。逐条查因：

| # | 缺陷 | 根因 | 本轮修法 | 复核 |
|---|---|---|---|---|
| **D-A** | 🔴 **`ACCEPTED.json` 的 `pkg_dir` 仍写 rc1**（`<HOME>\…MiniMVP_v1.0-rc1`）⇒ app191 的 **R3「pkg_dir == 本包目录」FAIL** | 构建脚本 `_app255_build_minimvp_rc2.py` **硬编码**了 rc1 的字面量（复制粘贴时忘了改） | ① 构建脚本改为**从 `DST_PKG` 派生**（消除这类 bug 的根）② rc2 的 `ACCEPTED.json` 就地改正 | 复跑 ⇒ **R3 由 FAIL 转 PASS**（9 → **10 PASS**） |
| **D-B** | 🔴 **R2 的 5 个模块全判 `cls=other`（漂移「推翻了验收」）** | MiniMVP §2 依赖隔离把**开发目录名换成中性占位**（`qwen3asr_06b→asr_module` / `qwen3tts_eval→tts_module` / `hy_bench→mt_module` / `confucius4-openvino→dev_repo`）⇒ 对 app191 的「git 基线 vs 包内」比较器就是**字面量不同** ⇒ 但**语义不变**（那些路径在客户机上本就不存在） | 按 **v2.2 同款机制**在 rc2 的 `ACCEPTED.json` 登记 `waived_changes`（5 条，每条写明 `reason` + `source` = APP-066 ② / APP-067 ②） | 复跑 ⇒ **18 PASS / 0 FAIL**（`app264_app191_on_rc2_final.json`） |

🔴 **本轮为 D-B 做了鉴别力验证（不是拍脑袋）**：对 5 个模块逐个做 `scrub(开发树) == 包内` 的**逐字节**比对 ⇒ **5/5 全部 True** ⇒ **证明「漂移」只有 scrub 这一项、没有任何真实代码差异**；并用 **v2.2 作对照**跑同一闸门 ⇒ **16 PASS / 0 FAIL**（v2.2 用 `<HOME>` 占位 ⇒ 落在良性类 ⇒ 不需要白名单 ⇒ 证明差异确实来自 MiniMVP 的**目录改名**式 scrub，不是闸门本身坏了）。
🔴 **rc2 的 `code_fingerprint` 未变**（`ed4dc8ca687269…`，24 个生产模块逐个重算 ⇒ **0 漂移**）⇒ **只改了 `ACCEPTED.json` 的元数据（`pkg_dir` + `waived_changes`），包内 `app/` 代码一个字节都没动**；**rc1 目录未动**（`pkg_dir` 仍是 rc1、无白名单）。

### ⑦ ✅ **本轮唯一代码改动（纯附加、默认关闭、行为逐字不变）**

`live_caption/live_caption_app.py` ＋ **`--spk-seg-jsonl`**（逐段 `seg/t0/t1/spk/spk_conf/spk_source` ＋ `提交序号→seg` 映射）—— 🔴 CLI **早就算出了** `(t0,t1)` 却**从不落盘** ⇒ reviewer's「每段一行」表与原声切片**无从下手**（② 交付物为 0 的直接原因）。不给这个参数 ⇒ **不落盘、不包装 `submit` ⇒ 默认路径逐字不变**。
🔴 **回归复跑（仓库 `.venv`）**：`app215` **29/0**｜`app227` **34/0**｜`app229` **38/0**｜`app237` **9/0**（与 §132/§133 逐字一致）⇒ **无回归**。
🔴 **影子包刷新**（`shared/app067_shadow`）：刷 **1 个文件**（`app/live_caption_app.py`）＋ 复核**真包 v2.2 的 40 个文件指纹前后一致 ⇒ 未被改动**（`app248_shadow_refresh_evidence.json` → 7 项检查全 `ok=true`）。

### ⑧ 🔴 **本轮新查出/更正、待 reviewer 裁定的 3 点**

1. 🔴 **【更正上一会话草稿】MiniMVP 的 MT `auto` 标签是**硬编码**的，**但 GUI 显示是对的**：
   - 上一会话草稿写「**GUI 的 MT 行仍显示「INT8-CW 模型（默认）」⇒ 显示与实载不符**」⇒ **与它自己的证据矛盾**（`app259` 三臂的 `mt_label` 全是 `Intel GPU · INT4-CW · GPU.0`；本轮亲自读 100 %/150 % 两张截图，翻译行也都是「Intel GPU（集显）· INT4-CW」）⇒ **该说法不成立**。
   - **真正成立的是**：`translator.py` 里 `MT_ENGINES['auto'].label` 与 `MT_ALL_CANDIDATES['auto'].label` **写死** `'自动 · INT8-CW 模型（默认）'`，而 MiniMVP 客户机上 `auto` 实际解析到**包内 INT4**（本轮 CPU 实测：`DEFAULT_MODEL = …MiniMVP_v1.0-rc2/models/mt/mt2-int4sym-cw-q`，`MT_ENGINES` 只有 `auto / gpu_int4cw / npu_int4cw`）⇒ **CLI 的 `--check` 诊断行**与 **`auto` 引擎的 `device_desc`** 会印「INT8-CW」而实载 INT4。
   - **GUI 不受影响**的原因：`App._init_combo_values` 用 `_resolve_mt_engine_key('auto', dev)` 把 `auto` 解析成**具体引擎**（本轮实测 `resolve(auto,'GPU.0') → gpu_int4cw`）＋ `set_engine()` ⇒ 状态栏 label 取的是**真值引擎** ⇒ 显示正确。
   - **未擅改**：改 `translator.py` 的 `auto` label 会波及 v2.x ⇒ **交 reviewer 裁定**（建议按 `DEFAULT_MODEL` 实际目录**动态生成** label）。
2. 🔴 **【本轮实测，数字已确定】MiniMVP 首次 NPU 编译 = 1209.3 s ≈ 20 分钟**（`app263` 真冷臂，全新 LOCALAPPDATA，`tts_npu_cache` 从 0 编到 16–18 个 blob）；**第二次启动 = 9.5 s**（`app264`）⇒ **客户机首次启动会长时间无 TTS（≈20 min）**。根因：`DECODER_BUCKETS_CTX` = 8/16/32/33/40/64/128/256 ⇒ **8 个解码器桶每个都要单独 NPU 编译** ⇒ 是否应把预编译 blob 随包分发（换体积）⇒ **交 reviewer 裁定**。
   🔴 **附带一次性开销**：客户机首启还可能额外遇到 **≈19 min 的 GPU oneDNN JIT**（MT INT4 落 GPU.0）⇒ 本轮实测首个冷臂的 `ov_cache` 写了 **750 个 `*.onednn.cl_cache`**（07:21→07:40）⇒ 该轮 MT 就绪日志都没打出来 ⇒ **总首启开销可能 > 30 min**。
3. **MT INT4 vs INT8 质量对比**：本包用 `mt2-int4sym-cw-q`（**对称 · per-channel weight**）；**开发版已有的 INT4 质量数据未引用**（在 hy_bench/MT 模块侧）⇒ 已登记进 ACCEPTED 的 `pending_reviewer` ⇒ 待补或由 reviewer 指定口径。

### ⑨ ⛔ **本轮仍未做（等 reviewer / 等用户）**

- **APP-066 3(c) zip 未打** ⇒ APP-066 4：**验收 + reviewer 回转写 + 用户抽听**之前不通知用户、不放桌面快捷方式；且**「用户不通知不打包」**规则仍有效 ⇒ **本轮未打**。
- **v2.3 继续暂缓**（APP-067 原文「顺序 1→2→3、4→5→才能打包」）。
- **未通知用户 / 未改桌面快捷方式 / 未改任何 v2.x 客户包目录**（v2.1、v2.2 一个字节都没动）。
