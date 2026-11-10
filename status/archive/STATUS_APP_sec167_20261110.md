## §167 续做 APP-093 §3 + APP-097 §2 设备验收（last_ack=APP-097，2026-11-10 15:59）｜**§3.7 截图 PASS（含一个阻断级真缺陷的根因修复）**｜**本条需等 reviewer 复核**

### ① 🔴🔴🔴 本轮最重要的发现：**GUI 布局代码被吞进 `_clone_nearest` ⇒ GUI 一直是空壳**

**现象**（§3.7 反复失败）：
* GUI 起来后 Win32 只枚举到一个 `TkTopLevel 216×239 title='tk'`（Tk **默认**标题/尺寸）⇒ 主窗标题「实时字幕 MiniMVP v1.0」**从未出现**。
* 字幕**永不出现** ⇒ §3.7「截一张有三行字幕的图」在结构上**不可能成功**。
* 探针（`_app331b_gui_probe.py`）5 分钟内始终 `216×239 'tk'`。

**定位过程（三步递进）**：
1. `faulthandler` ⇒ 主线程停在 `tkinter/__init__.py:1505 mainloop` ⇒ 曾误判「GUI 已初始化完毕」。⚠️ **该证据实为误取**（pythonw 的 stdout 为 None ⇒ App 内 `print` 全丢 ⇒ `gui.log` 恒 0 B）。
2. Tk 内部探针（`_app331e_gui_tkprobe.py`，patch `Tk.title`/`Tk.geometry`）⇒ **`Tk.title` 从未被调用**；`root.title()=='tk'`、`wm_geometry=='200x200+234+234'` ⇒ **不是枚举问题，是代码没跑到**。
3. `ast` 精确解析 ⇒ **`App.__init__` 的 ast 范围只有 2205–2292（88 行）**；而 `root.title('实时字幕 MiniMVP v1.0')`（第 2468 行）落在 **`_clone_nearest`（2389–3157）** 体内 ⇒ **`__init__` 被提前截断**。

**根因（git 溯源定案）**：`commit 874924a`（APP-086(2)「clone 策略层接入」）把
`def _clone_nearest(self, seg, spk, sim):` **误插进 `App.__init__` 的中间** ⇒
`__init__` 提前结束 ⇒ **原本属于 `__init__` 的 GUI 布局代码（`root.title` / `root.geometry` /
全部控件构建 / `prewarm_transformers()` / `self.load_engine()`）被吞进 `_clone_nearest` 的方法体**
⇒ **运行时永不执行** ⇒ GUI 永远只有一个空的 `tk` 200×200 窗口。
* 溯源证据：`git log` 逐 commit 跑 ast ⇒ `b1496ba`（`__init__` 2177–2996，**正常**）→ `874924a`（2181–2259，**BROKEN**）⇒ **缺陷由 874924a 引入**。
* 中招范围（实测）：dev 树 `live_caption/live_caption_app.py`、影子包 `after`/`before` **均中招**；`after2`/`after2_pre`/真包 v2.4（`__init__` 2176–2995）**未中招**。
* 被吞代码里用了 `args.tts_voice` ⇒ 在 `_clone_nearest` 里本应是 **NameError**（该方法无 `args` 形参）⇒ 该方法一被调用就会炸。

**修法（`results/app/_app334_fix_gui_init_indent.py`，纯搬移、零内容改写）**：
把 **2407–3157 整块**（原属 `__init__`）搬回 `__init__` 末尾；`_clone_nearest` 只保留它本来的 `try/except`（2397–2406）。
**8 项校验全 PASS**（`results/app/app334_app093_gui_init_indent_fix.json` → `checks`）：
`ast_parse` / `title_owned_by_init` / `init_covers_title_line` / `clone_nearest_small` /
`const_multiset_same`（常量多重集不变）/ `stmt_multiset_same`（语句多重集不变）/ `line_count_same`（行数守恒）/ `eol_preserved`。
* 修后：`App.__init__` = 2205–**3043**；`_clone_nearest` = 3140–**3157**（18 行）。
* dev 树文件：458 919 B（**字节数不变**），SHA256 前 16 = `25b1626cf391417b`。
* 🔴 **本轮未把该修复同步进客户包**（见 ③「未做」）。

### ② APP-093 §3.7 字幕条截图 —— **PASS**（修复后）

| 项 | 值 | 来源产物 / 字段 |
|---|---|---|
| 判定 | **`verdict=PASS`** | `results/app/app331_app093_gui_shot.json` → `verdict` |
| 主窗 | hwnd 1248278 / title「实时字幕 MiniMVP v1.0」/ 1455×1132 px | 同上 → `window` / `png.size` |
| 主窗 png | `results/app/app331_gui_shot/after_fix_tmp/after_fix_tmp_caption.png`（90 095 B） | 同上 → `png.path` / `png.bytes` |
| 主窗三道守卫 | `not_black=true` / `client_height_ge_700=true`（1098 px）/ `content_density_gt_0=true`（0.278057） | 同上 → `guards` |
| **三行字幕条** | hwnd 9047410 / **1638×157** / x=205 y=1034（屏幕下半部） | 同上 → `overlay_window` |
| 字幕条 png | `…/after_fix_tmp_overlay.png`（23 535 B） | 同上 → `overlay_png.path` / `.bytes` |
| 字幕条守卫 | `not_black=true` / `content_density_gt_0=true`（0.129481）/ `wide_bar=true` | 同上 → `overlay_guards` |
| **三行内容（已读图确认）** | ① 青 = 定稿译文「…如寄咖啡。于是，咖啡便成了提醒。没错，你不需要意志力，只需要一个已经存在的触发因素即可。」② 白 = 定稿原文「…es the reminder. Exactly, you don't need willpower, you just need a trigger that already exists.」③ 黄 = 实时识别「That makes sense.」 | 截图人工读图（`overlay_png`） |

* 🔴 **字幕条不能用标题找**：`CaptionOverlay` 是 `tk.Toplevel` + `overrideredirect(True)` ⇒ **Win32 标题继承父窗口标题**（实测与主窗**完全相同**）⇒ 上一版 `find_window('字幕')` 抓到的是**主窗**（hwnd 相同）。⇒ 改用**几何 + 位置**三重判据：宽 ≫ 高（w > 3h）＋ 位于**下半屏**（top ≥ 屏高×0.55）＋ 尺寸下限。
  ⚠️ 中途踩坑：判据原写「贴屏幕底部（bottom ≥ 屏高−40）」⇒ **误杀**（本机屏高 1280，字幕条 bottom=1191，差 89）⇒ 字幕条贴在**工作区**底部而非物理屏底。
* 抓图工具：`results/app/win_capture.py` 的 `capture_hwnd()`（Win32 `PrintWindow` + 三级降级）⇒ **不用** `PIL.ImageGrab`（本机全黑，本项目铁律）。

### ③ APP-093 其余分项 —— 已跑完

* **§3.3 单会话过载臂**（1.0× → 2.0× → 1.0×，同一时间轴）：`results/app/app327b_app093_overload_recompute.json`
  * 修正前 → 修正后：**overload 段 n_rows 1 → 20**、**n_late_drop 0 → 19**；normal 9 → 10（late_drop 1）；recover 49 → 51（late_drop 2）。
  * **恢复用时 = 3.597 s**（阈值 6.0 s，字段 `speed_lag_s`）⇒ **反证组 PASS**（把 `speed_lag_s` 全 +1000 ⇒ 恢复用时变 `None`）。
  * 字幕完整度：`n_subtitle_lines=54` == `n_seg_rows=54` ⇒ `n_sub_n_seg_equal=true`（跳句只丢语音，不影响字幕/转写）。
  * 🔴 **本轮修掉两个分析缺陷**（否则数字会误导）：① `sitecustomize` 的 `__import__` hook **永不触发**（App 以 `__main__` 运行 ⇒ `import live_caption_app` 从不发生）⇒ 改**轮询 `sys.modules['__main__']`**；② `late_drop` 行 `play_wall=None`（22 句）⇒ 只用 `play_wall` 定位会**整体漏掉过载期** ⇒ 改用 `wall_est = t_submit + median(play_wall − t_submit)`（offset std=1.6686 s）。
* **§3.4 before 臂**（静态补算，未重跑设备）：`results/app/app396_app093_before_arm_scores.json` —— tight：synth_rtf_p50 0.8919 / play_lag_p50 16.5585 / speed_lag_p50 13.8845 / end_reason={eos:78} / n_hit_frame_cap=0 / subtitles=35；dave：synth_rtf_p50 0.9634 / play_lag_p50 33.532 / speed_lag_p50 28.88 / end_reason={eos:84} / n_hit_frame_cap=0 / subtitles=55。
* **§3.5 音色归属**（4 组 before/after × dialog3/tight，NPU 设备跑，持锁）：`results/app/app329_app093_voice_attrib.json`
  * 命中率 `match_rate_truth_ref`：before_dialog3 **0.4691**（38/81）｜after_dialog3 **0.3418**（27/79）｜before_tight **0.6026**（47/78）｜after_tight **0.3696**（17/46）。
  * 🔴 **判据可分性极低**：三人**真值参考**两两余弦 = dialog3 组 A-B 0.967428 / A-C 0.971264 / B-C 0.957272；tight 组 A-B 0.968116 / A-C 0.971529 / B-C 0.957555 ⇒ 「取最接近正确说话人」在余弦尺度上**几乎不可分** ⇒ **命中率低不等于 App 缺陷** ⇒ **未自行换判据**，等 reviewer 裁定。
  * **反证组 4/4 PASS**（把真值余弦压到最低 ⇒ 命中数必须下降；实测 `neg_n_match` 全部 = 0 < base）。
* **§3.6 切段分析**（静态，未重跑设备）：`results/app/app328_app093_split_analysis.json` —— tight 35 段 `n_split` 全 0、`spk` 全 S1、ASR RTF 0.723；dave 55 段 `n_split` 全 0 但 `spk`={S1:12, S2:42, None:1}、ASR RTF 0.862。
  * 🔴 根因线索：聚类 `delta_new=0.30` **远低于**三人互余弦（0.957–0.972）⇒ 永远不会新建簇 ⇒ 「切段 0 段」。
  * ⚠️ **gap（已写入 `gaps`）**：「切段开/关的 ASR RTF 对照」**本轮未跑**（需两次设备跑）⇒ **不报数**。

### ④ APP-097 §2 逐语种设备验收 —— 已跑完

| 分项 | 结果 | 来源产物 / 字段 |
|---|---|---|
| §2-2 MT（8 语种 × 20 句 = 160） | **0 空译 / 0 错误 / 输出语种 100 %**；`zh_skipped_rate=1.0`（源=中文、目标=非中文 ⇒ 不跳） | `results/app/_app326_app097_lang_out/mt.json`（122 674 B） |
| §2-3 TTS（8 语种 × 预设/克隆，**240 行全落盘**） | **撞帧上限 0**（双口径：`end_reason` 字段 240 行全 `None`；独立判 `frames_out >= max_new_tokens` ⇒ 0）⇒ 判据**未恒真**（反证组：抬 3 行 `frames_out` ⇒ 计数 0 → 3 ⇒ PASS） | `results/app/app326_tts_post.json` |
| §2-4 时长校准 | 8 语种 `sec_per_char_p50` 与 `src_dur_ratio_p50` 全部落盘（例：zh preset rtf_p50 0.8546 / spc_p50 0.217143 / ratio_p50 1.2987；ru preset rtf_p50 0.809 / spc_p50 0.082645 / ratio_p50 1.4125） | 同上 → `by_lang` |
| §2-5 回归（zh before/after） | `n_tts_rows` 81/81、`n_segments` 54/54、`n_subtitle_lines` 54/54 **逐项一致**；`synth_rtf_p50` 0.9963 → 0.9586（Δ −0.0377）；⚠️ **`n_late_drop` 6 → 5 不一致（如实记录，未声称一致）** | `results/app/app333_app097_regress.json` → `zh_compare` |
| §2-5 ja/ko 冒烟 | 各 5 句，rc=0，**0 空译**；ja rtf_p50 0.8906 / ko 0.8778；`EXECUTION_DEVICES` 全部 NPU（speaker_enc / cp_prefill / cp_decode / talker_bucket / decoder_bucket） | 同上 → `smoke` |
| §2-6 模型身份 | **真包 v2.4 vs 影子包 12/12 模型目录树 SHA 全部一致** ⇒ `all_same=true`；`same_physical_dir=true`（realpath 同一 `…\Confucius4_LiveCaption_v2.4\models`）；MANIFEST `files=14319` / `bytes=13692564165` / `version="2.4"` | `results/app/app332_app097_model_identity.json` → `compare` / `manifest` |

* 🔴 §2-5 的前提已实测：两个影子包 `models` **realpath 相同** ⇒ 模型相同 ⇒ 差异只来自代码（`roots.same_models_dir=true`）。
* 🔴 §2-6 反证组 PASS：把内存里 `tokenizer/added_tokens.json` 的 SHA 换成全 0 ⇒ 树 SHA 由 `488d8442…` 变为 `9fa4917a…` ⇒ 判据能触发。

### ⑤ 🔴 未做 / 停下等 reviewer
* 🔴 **GUI 布局缺陷的修复尚未同步进客户包**：修复只落在 **dev 树**（`live_caption/live_caption_app.py`，SHA `25b1626cf391417b…`）＋ 影子包 `_app_shadow/after_fix_tmp`（§3.7 验证用）⇒ **v2.5 未打包、未同步任何客户包目录**（APP-055：同步必须走**打新版本号**）。
  ⇒ **reviewer 需先裁定**：这个缺陷是**必须立刻修**（GUI 完全不可用）还是**随 v2.5 一起出**；本轮**不自行打包**。
* 🔴 **该缺陷的历史影响未评估**：`874924a`（11-09）之后的**所有 GUI 相关验收**都跑在空壳 GUI 上 ⇒ 凡依赖 GUI 的结论都需复查（本轮 §3.7 是第一个真 GUI 验收）。
* 🔴 **CLI 路径不受影响（已实测）**：`run_cli` 段在 dev 修复版与 `after` 影子包**逐字节相同**（段 SHA `420933deb7d2a15a`，6916–7933 行）⇒ **本节 ③/④ 的全部数字（CLI 跑）仍然有效**。
* **§3.5 判据失效** ⇒ 未自行换判据，等 reviewer 裁定；**§3.6 切段开关的 ASR RTF 对照未跑** ⇒ 不报数；**§2-4 只报实测 p50、未改 `_SEC_PER_CHAR` 默认值**。
* 阈值取舍仍由 reviewer 拿 §3.1/§3.2 数字报主会话请用户决定（**默认值仍 6.0**）。
* **未打包 v2.5、未通知用户**（APP-093/APP-097 明文）。
* ⚠️ **§166 与更早的旧结论本轮未改**（§166 已整块归档到 `status/archive/STATUS_APP_sec166_20261110.md`）。
* 🔴 **`CORRECTIONS_APP.md` 全程只读**：开工基线与收尾复核**完全一致** —— SHA256 `36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2` / 285 671 B / mtime 2026-11-10 11:49:26 / **97 条**（APP-001…APP-097）⇒ **reviewer 本轮中途未追加新条目**。
