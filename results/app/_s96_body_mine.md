## §96 🔴🔴🔴 **APP-042 真机实测暴露并修掉「CLI 路径加速链路永不触发」的真机缺陷 ⇒ 客户包 v1.8 已定点同步** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-29 21:58）

> ⚠️ **本节不修改任何旧章节**；旧结论若被本节推翻，在本节内写明「撤回 §x」。
> ⚠️ **本节不写「已交付」** —— 本轮**未重打 zip**（见 96.7）⇒ 客户包 **zip 内仍是旧代码**。

### 96.1 本轮起因：§95 声称「APP-042 代码侧全部完成」，但**真机实测推翻**

§95（2026-10-29 20:49）写「APP-042『自适应加速播放』全链已接通」。本轮按 §95 的遗留项
（⛔ APP-042 的 SPE 5 分钟真机实测未做）补做实测，**实测结果推翻该结论**：

- 🔴 实测落盘证据（`results/app/app042_soak_run2/`，源目录 `C:\Users\Trekker-PTL\app042_soak\`）：
  - `app042_soak.wav.tts.jsonl` **76 行**，逐句统计：
    - `with speed = 76`（字段**在**）
    - `with target_wall = 0` ⇒ **`target_wall` 恒为 `None`**
    - `with play_lag_s = 0` ⇒ **滞后口径永远算不出来**
    - `speed>1.0 句数 = 0`，`speed` 分布 `Counter({1.0: 76})`
  - `app042_speed_distribution.csv` 唯一一行：`speed,n_sent,out_dur_s,ratio` → `1.0,76,339.04,1.0000`
  - `app042_lag_curve.csv` **76 行全部 `lag_s = None`**、`speed = 1.0`
  - `app042_soak_report.json` 字段：`app042.lag_start_s / lag_peak_s / lag_end_s /
    lag_peak_at_t_s / lag_min_s / lag_median_s` **全为 `null`**；
    `clips = []`；`pass_count = 8`、`fail_count = 5`
  - CLI 收尾统计行（`app042_soak_cli.log` 第 553 行，原文）：
    `[TTS] 最终统计（close 后）：提交 76  播完 76  丢弃 0  关闭作废 0  空句 0  失败 0  结尾滞后 62.94s  积压 最大 82.98s`
    ⇒ **结尾滞后 62.94 s、积压峰值 82.98 s** ⇒ **正是 APP-042 要处理的场景，
      却一句都没加速**
- ⇒ 🔴 **撤回 §95 中「APP-042 全链已接通」这一表述**（代码在，但**链路在 CLI 下从未闭合**）。

### 96.2 🔴🔴 缺陷根因（代码定位，精确到行）

APP-042 的「目标开播墙钟」机制**只做在 GUI `App` 类**：

| 位置 | 事实 |
|---|---|
| `live_caption/live_caption_app.py` L2373 | `self._session_wall0 = None`（**仅 GUI 实例属性**） |
| `live_caption/live_caption_app.py` L2886 | `self._session_wall0 = time.time()` —— **只在 `App.start()` 里赋值** |
| `live_caption/live_caption_app.py` L3669 | `self._seg_target_wall[seg] = self._target_play_wall()` —— **只在 `App._on_final()` 里登记** |
| `live_caption/live_caption_app.py` L3491 | GUI 的 `tts.submit(...)` 传了 `target_play_at=self._seg_target_wall.get(ev['seg'])` ✅ |
| `live_caption/live_caption_app.py` L4392 / L4444 / L4480（修前） | **CLI 的三处 `tts.submit(...)` 全都不传 `target_play_at`** ❌ |

⇒ CLI 下 `tts_service.submit()` 的 `target_play_at is None` ⇒ **不下发 `speed` / `target_wall`**
⇒ worker 侧 `tel['target_wall']` 恒 `None` ⇒ `tel['play_lag_s']` 恒 `None`
⇒ **自适应加速链路在 CLI 下永不触发**（⇒ 本轮真机实测用 CLI 回放 ⇒ 必然测不出效果）。

> 🔴 **这条缺陷的教训**：§95 的「代码侧全部完成」是**按 GUI 路径审的**，
> 而**验收脚本走 CLI 路径** ⇒ 「代码写了」≠「链路闭合」。凡跨路径（GUI/CLI）的能力，
> 必须**逐路径核**。

### 96.3 ✅ 修法（CLI 与 GUI 同一口径，跨进程可比）

修改文件：`live_caption/live_caption_app.py`（仓库）+ 客户包 `app/live_caption_app.py`（定点同步）。

1. **会话起点墙钟**：`_cli_wall0 = time.time()`
   - 位置在 `s.start()` **之前**（L4408）⇒ **首句**的目标时刻不是 `None`。
   - 🔴 用**墙钟 `time.time()`** 而非 `perf_counter()`：APP-042 的 lag 跨
     **主进程（目标时刻）** 与 **worker 进程（开播时刻）** ⇒ `perf_counter()`
     各进程基准不同 ⇒ **不可比**（与 GUI 侧同理由）。
2. **目标墙钟计算**：新增闭包 `_cli_target_wall(seg)`（L4345）
   - 口径 = `t0 + session.audio_s`，与 GUI `App._target_play_wall()` **完全一致**
   - ⚠️ ASR 不给段级时间戳 ⇒ 用「已消费源音频时长」近似（GUI 同口径）。
   - ⚠️ 查不到 ⇒ 返回 `None` ⇒ 服务端不下发加速参数 ⇒ **旧行为逐字不变**。
3. **登记时机**：`on_final()` 里**先登记**段号→目标墙钟（**L4380**），**再** submit
   ⇒ 首句也能拿到目标时刻（闸门 C7 验证登记位置早于 submit 位置）。
4. **三处 submit 全传**：L4392（ASR 原文臂）/ L4444（MT 译文主循环）/ L4480（收尾补交）。

### 96.4 ✅ 回归闸门 `app145`（判据不恒真）

新增 `results/app/app145_app042_cli_target_wall.py` +
`results/app/app145_app042_cli_target_wall_evidence.json`。

- **REAL 组 9/9 PASS**：
  `C1_run_cli_found` / `C2_cli_has_submit_calls`（= 3）/ `C3_all_cli_submit_pass_target_play_at`
  （缺 `target_play_at` 的 submit 序号 = `[]`）/ `C4_cli_session_wall0_assigned` /
  `C5_cli_target_wall_fn` / `C6_on_final_registers_target_wall` /
  `C7_register_before_submit`（登记位置 174263 < submit 位置 174759）/
  `C8_gui_still_uses_target_play_at`（GUI 路径未被破坏）/ `C9_service_accepts_target_play_at`。
- **反证组 FAIL**（证明判据不恒真）：在 **AST 层**剥离 CLI 三处 `target_play_at` keyword
  ⇒ `C3` FAIL（`缺 target_play_at 的 submit 序号 = [0, 1, 2]`）⇒ `verdict = true`
  （规则：**REAL 组全 PASS 且 反证组有 FAIL**）。
- 🔴 **判据自身踩坑两处（已修，记录在案）**：
  1. **正则按行删 `target_play_at=` 会破坏语法** —— GUI 那处是**多行续行**
     （`target_play_at=self._seg_target_wall.get(\n    ev['seg']))`）
     ⇒ 按行删留下孤立括号 ⇒ `SyntaxError: unmatched ')'` ⇒ **反证脚本自己崩**
     ⇒ 看起来像「缺陷没复现」⇒ **判据失效**。
     ⇒ 改用 `ast` 找 Call → 删 keyword → `ast.unparse` 回源码 ⇒ **语法永远合法**。
  2. **只按 `attr == 'submit'` 会把 `mt.submit` 也算进来** ⇒ C3 恒 FAIL
     ⇒ **判据 FAIL 先怀疑判据**。⇒ 改为**按接收者名 `tts` 筛选**。

### 96.5 ✅ 客户包定点同步（`sync_c159_to_pkg.py`）

新增 `live_caption/sync_c159_to_pkg.py`（**OLD 取自「包内实际内容」，不是基线 commit**）。

| 项 | 值 |
|---|---|
| 客户包 | `C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.8` |
| 目标文件 | `app/live_caption_app.py` |
| `--check` | `[WOULD-SYNC] blocks=6 applied=6` |
| 实同步 | `[SYNCED] blocks=6 applied=6` |
| 幂等复跑 | `[ALREADY]` ✅ |
| 同步前字节数 / SHA256 | 263 664 B / `c123cdfbf70b2685a208eff323dc865140564a4fb8104e4a0dc385f114f186be` |
| 同步后字节数 / SHA256 | 266 820 B / `a9c957770553591d313ee87bb939138c4ec3bd07757251c4a52efae41c8eb46d` |
| 归一化换行后仓库 SHA256 | `a9c957770553591d313ee87bb939138c4ec3bd07757251c4a52efae41c8eb46d` ⇒ **与包内一致** |
| 包外备份 | `C:\Users\Trekker-PTL\pkg_backup_app_c159\live_caption_app.py.c123cdfbf70b.bak` |

🔴 **仓库 CRLF / 包内 LF ⇒ 原始字节 SHA 必然不同 ⇒ 交付等价性按「归一化换行后」判定**
（同时报 raw + norm 两个 SHA，避免假报警）。

### 96.5b ✅ 离线数学验证闸门 `app146`（纯函数层，不占共享锁）

新增 `results/app/app146_app042_speed_math.py` +
`results/app/app146_app042_speed_math_evidence.json`。
**为什么要离线验**：真机实测要抢共享锁、耗 5 分钟；而「速度公式」与「lag→speed 映射」
是**纯函数** ⇒ 可先用离线单测把数学口径钉死，再等锁做真机确认 ⇒ **两层证据互不替代**。

- **REAL 8/8 PASS**：
  | 项 | 断言 | 实测 |
  |---|---|---|
  | V1 | `lag ≤ 3 s ⇒ speed = 1.0` | `[1.0, 1.0, 1.0, 1.0]` |
  | V2 | `lag = 15 s ⇒ 累积收敛到 1.30` | `1.3` |
  | V3 | `lag > 15 s ⇒ 截断 1.30` | `[1.3, 1.3, 1.3]` |
  | V4 | 滞回：`lag=2.5` 保持 / `lag=1.5` 连两句回 1.0 | `{2.5: 1.2, 1.5#1: 1.1, 1.5#2: 1.0}` |
  | V5 | 线性段 `lag=7 s ⇒ 1.10` | `1.1` |
  | V6 | 相邻句单次变化 ≤ 0.1× | `1.1` |
  | V7 | **WSOLA 保音高**（变调检测） | `f_in 220.18 Hz → f_out 220.18 Hz（ratio = 1.0）`，长度 `24000 → 20000` |
  | V8 | CLI 目标墙钟口径 = `t0 + audio_s` | 源码三项齐备 |
- **反证 3/3 全部被识破**：公式恒 1.0 / 去掉相邻句限幅 / 剥离 CLI 目标墙钟源码
  ⇒ `counterfactual_not_caught = []` ⇒ **判据不恒真**。

🔴 **判据自身踩坑（已修，记录在案）**：
1. **V2/V3/V4 初版 FAIL 是「判据写错」** —— `speed_for_lag` 还受「相邻句变化 ≤ 0.1×」
   步长限制 ⇒ **单次调用**从 `prev=1.0` 最多只能到 **1.1**
   ⇒ 直接断言「单次 = 1.30」必然 FAIL。⇒ 正确口径 = **逐句累积**（每句 `prev` = 上一句结果）。
   ⚠️ **「判据 FAIL 先怀疑判据」**，本轮据此避免了一次「误判产品回归」。
2. **`exec` 抽源码时丢了 `import`** —— 只保留 `FunctionDef/ClassDef/Assign`
   ⇒ `time_stretch.py` 顶层 `import numpy as np` 被丢 ⇒ exec 后 `np` 未定义
   ⇒ `time_stretch()` 内 `np.xxx` ⇒ **NameError** ⇒ 判 V7 **假 FAIL**。
   ⇒ 修法：保留 `Import`/`ImportFrom` 节点。
3. **解释器口径** —— managed 3.13 **无 numpy** ⇒ V7 客观做不了
   ⇒ 改用 **system 3.12**（`numpy 2.5.4`）运行（与 §91 记录的同一条铁律）。

### 96.6 ✅ 验收脚本判据自身缺陷（已修，非产品回归）

`results/app/app143_app042_soak.py` 的 `pick()` 旧实现按 **token 相等**取字段，
但 close 后的最终统计行是**全角冒号紧贴**（`最终统计（close 后）：提交 76`）
⇒ token 为 `后）：提交` ⇒ `pick('提交')` **恒返回 `None`**
⇒ **B4（不变式）/ B6（worker 重启）假 FAIL**。

修法：① 收集**所有**候选统计行（运行时那行含「重启」，close 后那行没有）
⇒ 遍历取值；② 取值改为**正则**（兼容全角/半角冒号 + 可选空格）。

用**本轮 run2 的真实 CLI 日志**离线验证修好的取值逻辑：

```
提交 = 76   播完 = 76   丢弃 = 0   重启 = 0
最大 = 82.98   首包 = 0.43   当前 = 0.0
```

⇒ B4（76 + 0 == 76）✅ PASS、B6（重启 = 0）✅ PASS
⇒ **run2 的 5 项 FAIL 中有 2 项属判据缺陷**，真实产品 FAIL 是 **B9 / B10 / B13** 三项
（`play_lag_s` 恒 None、无 `speed>1.0` 句、无 1.2–1.3× 配音落盘）—— **正是本轮修的缺陷**。

### 96.7 ⛔ 本轮**未**做的事（不写「已交付」）

- ⛔ **zip 未重打** ⇒ **客户包 zip 内仍是修复前的代码**（已**实测核验**，非推断）：
  - `Confucius4_LiveCaption_v1.8.zip` = 11 218 155 024 B / mtime **2026-10-29 17:37:13**
    （**早于**本轮 22:0x 的修复）
  - `zipfile` 读 `Confucius4_LiveCaption_v1.8/app/live_caption_app.py`：
    `_cli_wall0` 存在 = **False**、`_cli_target_wall` 存在 = **False**、
    `target_play_at=_seg_target_wall` 出现 **0** 次
  - ⇒ 严格说「交付」只在**包目录**层面成立，**zip 层面未成立**
    ⇒ 本节**不写「已交付」**（按纪律：没落盘的东西不能写已交付）。
- ⛔ **APP-042 验收仍缺 reviewer / 用户两项**（reviewer 明文要求，本模块**不得自做**）：
  - 🔴 **reviewer 做回转写**，确认加速后错误率不明显上升（**不自己调用 MiniMax**）；
  - 🔴 **用户抽听 3 段 1.2–1.3× 配音**，确认不变调、可懂。
- ⛔ **APP-041 桌面快捷方式 → `pythonw.exe` 冷启动真机验收**仍未做。
- ⛔ **APP-039/040 核心**（音色按句绑定 spk + 说话人音色表）仍未做（卡 ASR 旁路接口）。

### 96.8 git 交付闭环

| commit | 内容 |
|---|---|
| `423c14e` | 仓库 `live_caption_app.py` 修复 + `sync_c159_to_pkg.py` + `app143` 判据修正 + `app145` 闸门与 evidence（5 文件） |
| `76c199d` | `app146` 离线数学闸门与 evidence + run2 缺陷复现证据归档（6 文件） |

- 普通 push：`3e4ea82..423c14e`、`423c14e..76c199d`（**无 force push**）
- `HEAD == origin/main`
- `git show --name-only --format="" HEAD | grep -c CORRECTIONS` = **0**
  ⇒ `CORRECTIONS_APP.md` **未入库**（只读，绝不提交）
- 他模块未提交改动 **485 项全部保留**（未吞）

### 96.9 结论

- ✅ **本条已完成**：APP-042 的 CLI 路径缺陷**已定位、已修、已定点同步到客户包 v1.8**；
  回归闸门 `app145`（REAL 9/9 + 反证识破）与离线数学闸门 `app146`（REAL 8/8 + 反证 3/3）
  双双通过且**判据不恒真**；验收脚本判据缺陷已修并用真实日志离线复验。
- 🔴 **本条需等 reviewer 复核**：
  ① 重打 zip（⇒ 「已交付」成立）；
  ② reviewer 的 MiniMax 回转写错误率对比；
  ③ 用户抽听 3 段 1.2–1.3× 配音（不变调、可懂）；
  ④ APP-041 桌面快捷方式冷启动验收。
  ⑤ 🔴 **修复后的真机实测（run3）仍在等 ASR 释放共享机器锁**
  （`asr PID 41264 started 2026-10-29 21:56:33 task=asr028-ref-diarize`，
  ctypes `exitcode=259` ⇒ **活锁** ⇒ **不抢不删**，fail-closed 排队中）
  ⇒ 修复后的「`target_wall` 有值 / `play_lag_s` 有值 / 有 `speed>1.0` 句 /
  有 1.2–1.3× 配音落盘」**尚未经真机确认** ⇒ 本节**不宣称加速已在真机生效**。
