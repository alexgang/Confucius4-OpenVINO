## §174 巡检（last_ack=APP-098，2026-11-11 06:22:30）｜**无新纠偏**；修掉 **2 个 App 侧真缺陷**：**① self_ref 克隆漏「克隆模式」闸门**（§168 ⑤ 实测 78/78 句 clone）＋ **② 开发期 `assert_*.py` 闸门可能随包泄漏**（§173 ⑥ 下一轮必读项）｜**本条需等 reviewer 复核**

### ① 开工／收尾基线（纠偏文件**只读**，全程未改未提交）

| 项 | 开工基线（实测） | 收尾复核（实测） |
|---|---|---|
| `status/app/CORRECTIONS_APP.md` SHA256 | `36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2` | `36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2` |
| 字节数 | 285 671 | 285 671 |
| mtime | 2026-11-10 11:49:26 | 2026-11-10 11:49:26 |
| `## APP-xxx` 条数 | 97 | 97 |

* 🔴 **开工＝收尾逐字一致** ⇒ reviewer 本轮中途**未追加**新条目 ⇒ **SHA 零改动**（全程只读）。
* 🔴 **无编号 > APP-097 的新条目** ⇒ 本轮**无新纠偏可执行**；`last_ack` 保持 **APP-098**。
* 🔴 **其它通道全空**（⇒ 无遗漏指令）：`shared/NOTICE*` 最新仍 11-05｜agent-mail 工具回 **`not_bound`**（面板虽显示 connected，实际未开通 ⇒ 不可用）｜`conversation_search` 命中 0｜git `origin/main..main=0` 且 `main..origin/main=0`｜`claude-clone` 分支相对 main **无新提交**｜`MACHINE_LOCK` **NOT_PRESENT**。

### ② 🔴 缺陷 ①：self_ref 克隆**漏「克隆模式」闸门**（已修 dev 树）

* **现象（§168 ⑤ 已实测，本轮沿用其原始数据）**：`--tts-voice A`（**预设 A**）＋`--speaker on` ⇒ `tts.jsonl` 里 **78/78 句** `voice_kind='clone'`、`voice_self_ref=true`、`voice_spk` 全为 null ⇒ **用户选了预设 A，实际每句都在克隆**。
* **与已接受口径冲突**：reviewer 2026-11-07（v2.4 验收）在 `98cf8fc` 的注释里写死：
  > `preset voice selected => never register clone voices`
  > `（v2.4 acceptance: --tts-voice A still dubbed 18/20 sentences with clone voices）`
  ⇒ 这是**已被 reviewer 接受的口径**，不是新口径。
* **根因（读码定案）**：`live_caption_app.py` 的 `_maybe_send_self_ref`（GUI）与 `_cli_maybe_send_self_ref`（CLI）**都没有克隆模式闸门** ⇒ 只看「该 spk 有没有登记音色」；而「登记音色」这条链**被**闸住 ⇒ **选中预设 A 时该 spk 永远没有登记音色** ⇒ 于是**每句都走 self_ref 克隆**。
* **修法（与姊妹闸门同源同口径）**：
  * GUI `_maybe_send_self_ref` ⇒ 加 `if not getattr(self, '_clone_enabled', False): return False`；
  * CLI `_cli_maybe_send_self_ref` ⇒ 加 `if not _want_clone: return False`；
  * 🔴 **用的就是同文件姊妹闸门 98cf8fc 的那一个量**（GUI 用 `_clone_enabled`／CLI 用 `_want_clone`）⇒ **不是新造判据**。
  * 🔴 **与 `_pump_spk_voices` 的差别已在注释里写明**：那边是「pending 排队」⇒ 切到克隆后仍会登记；这边 self_ref **按句现算现用** ⇒ 预设 A 时**根本不产生** self_ref 素材 ⇒ 切到克隆后**从下一句起**才有 self_ref（**不改既有「切到克隆后能克隆」的能力**）。
* **判据（行为级真跑 + 反证组）**：`results/app/_app429_self_ref_clone_gate.py` ⇒ `results/app/app429_self_ref_clone_gate.json` ⇒ **8 PASS / 0 FAIL**（8 项）。
  * **A 组（GUI）**：克隆模式关 ⇒ 发送次数 **0**（修前是 1 ⇒ 缺陷复现）｜克隆模式开 ⇒ 能发（**≥1**，**能力未被误伤**）｜该 spk 已有登记音色 ⇒ 不发。
  * **B 组（CLI）**：同三口径（用 `_want_clone` 闭包，**真跑**闭包函数，非模拟）。
  * **C 组（反证）**：把闸门**整块**做掉 ⇒ A1/B1 **必须 FAIL** ⇒ 判据有鉴别力。
* 🔴 **判据非空自证**：用 `git show HEAD:live_caption/live_caption_app.py`（**修前**的字节）跑**同一判据** ⇒ **A1/B1 都 FAIL** ⇒ 判据能识破旧产物，不是恒 PASS。
* 🔴 **本轮自踩一个判据坑（已修 ⇒ 留档）**：反证组**只把 `if` 行换成 `pass`** ⇒ 它的函数体（`return False`）变成**孤立语句** ⇒ **闸门依然生效** ⇒ 反证组恒 PASS ⇒ **判据失去鉴别力**（表现为「修好后 C1/C2 反而 FAIL」）。⇒ 正确做法：`_strip_gate` **整块吞掉 `if` 的整个缩进块**（`if False:` 替换同样不行——闸门还在，只是不生效）。
* 🔴 **历史影响（逐包判定）**：**16 个客户包逐个扫 `app/live_caption_app.py` 的 `self_ref` 出现次数 + `clone_voice.py` 是否在包内** ⇒ v1.13／v1.5／v2.0／v2.1／v2.2／v2.3／v2.4／MiniMVP rc1–rc5 **self_ref=0 ⇒ NA**；**rc6/rc7 有 self_ref 代码（46 处）但 `clone_voice.py` 不在包内** ⇒ `_clone_pol=None` ⇒ **行为级真跑证实** `_capture_self_ref_pcm` 不抛异常且 `_spk_self_ref` 恒空 ⇒ `_maybe_send_self_ref` **必在 `pcm is None` 处返回 False** ⇒ **该路径是死代码 ⇒ NA**。
  ⇒ **已交付的包零影响**（本轮**未改任何客户包目录**）。

### ③ 🔴 缺陷 ②：开发期 `assert_*.py` 闸门**可能随包泄漏**（已修打包规则）

* **来源**：§173 ⑥「下一轮必读」明文：
  > 「**v2.5 建包时别把 `assert_*.py` 带进 `app/`**（`pkg_exclude` 只排 `_` 前缀；但 `assert_pkg_clean.py` 是**必须随包**的例外）」
* **实测缺口**：dev 树 `live_caption/` 现有 **4 个** `assert_*.py`：`assert_pkg_clean.py`（**必须随包**）＋ `assert_sec_per_char_calibrated.py`／`assert_status_citations.py`／`assert_window_same_source.py`（**3 个开发闸门**）。修前 `pkg_exclude.is_app_dev_only()` 对这 3 个**全部返回 False** ⇒ **不被排除** ⇒ 只要建包脚本把它们拷进 `app/`，就会进 zip。
* 🔴 **为什么要排**：这 3 个闸门**写着开发机路径**（`assert_sec_per_char_calibrated.py` → `REPO/results/app/app326_app097_lang_out/tts.json`；`assert_status_citations.py` → `status/app/STATUS_APP.md`；`assert_window_same_source.py` → `REPO/live_caption/speaker_tracker.py`）⇒ 进客户包 = **开发机路径泄漏**（正是 APP-052③／§120 处理过的那类缺陷）。
* **修法**：`pkg_exclude.py` 新增 `APP_DEV_ONLY_ASSERT_RE = ^assert_[A-Za-z0-9_]+\.py$` ＋ `APP_DEV_ONLY_ASSERT_KEEP = {'assert_pkg_clean.py'}`（**必须随包** ⇒ 白名单例外：它是**打包阶段**的交付洁净度闸门，`PKG_INCLUDE_FILES` 列了它、`pack_v13.py` 闸门③ 逐字节比对它）⇒ `is_app_dev_only()` 里加一条判定 ⇒ **两条排除路径同时生效**（`is_excluded()` 走 `is_app_dev_only()`；`iter_package_files()`（zip 清单）**独立**再判一次 ⇒ 两边都堵）。
* **判据**：`results/app/_app430_pkg_dev_only_assert_gate.py` ⇒ `results/app/app430_pkg_dev_only_assert_gate.json` ⇒ **13 PASS / 0 FAIL**。
  * **A 组**：3 个开发闸门 `is_app_dev_only()`／`is_excluded()` **必须 True**；`assert_pkg_clean.py` **必须 False**（必须随包）。
  * **B 组**：扫 **5 个真实客户包**的 `app/` ⇒ 除 `assert_pkg_clean.py` 外**无任何** `assert_*.py`（v2.3/v2.4 各有且仅有 `assert_pkg_clean.py`；rc5/rc6/rc7 无）。
  * **C 组（反证）**：把例外名单**做掉** ⇒ A5/A6 **必须 FAIL** ⇒ 判据有鉴别力。
* 🔴 **判据非空自证**：把**修前**的 `pkg_exclude.py`（`git show HEAD:pkg_exclude.py`）**先注入 `sys.modules`** 再跑同一判据 ⇒ A 组 **4 FAIL**（3 个开发闸门 + `is_excluded`）。
  ⚠️ **头一次做非空自证时做错了**：先把判据脚本 import 进来、**后**替换 `sys.modules['pkg_exclude']` ⇒ 判据里 `import pkg_exclude` 早已拿到**新**模块 ⇒ 6 PASS / 0 FAIL（**假通过**）⇒ **必须先注入旧模块、再 import 判据**。

### ④ 既有闸门复跑（纯 CPU 静态，**未占设备**、未持锁）

| 闸门 | 结果 |
|---|---|
| `live_caption/assert_sec_per_char_calibrated.py` | **PASS 27/27**（含反证 3/3 触发） |
| `results/app/app109_lang_key_guard.py` | **PASS 34/34**（FAIL=0） |
| `live_caption/assert_pkg_clean.py`（对 v2.4） | **0 违规** |
| `live_caption/assert_window_same_source.py`（对 v2.4） | **PASS 8/8** |

* 🔴 复跑产生的两个 evidence JSON（`app109_lang_key_guard_evidence.json`／`assert_sec_per_char_calibrated.json`）**仅时间戳变** ⇒ 已用 `git cat-file blob HEAD:<path>` **逐字节还原**（**不用** `git checkout --`，避免 `core.autocrlf=true` 把 LF 落成 CRLF）⇒ **不留噪声 diff**。

### ⑤ 改了什么 / 没改什么（证据口径）

| 项 | 结果 |
|---|---|
| `live_caption/live_caption_app.py` | **478 871 B／SHA256 `fed84dce9fbb428f7d31d272e15d5b8cd32ccc6099336a0d0dfdb1f5c0544f64`**（修前 476 874 B／`3c39bdfae8d1398dfac1591cc32ced2cd7f504d38061ef155dac56910c2efc6c`）⇒ **只加 2 处闸门 + 注释**，`ast.parse` PASS |
| `pkg_exclude.py` | **43 796 B／SHA256 `1d99619f079ef42e1c38e8ebe97833563636e5e613f797e1afcb7ce76ac764fe`**（修前 42 289 B／`07f4f92f2ae60d418e3fda758f35c06fe22acfb38f4b5378491243e3804e49f3`）⇒ **只加排除规则 + 白名单**（**不改**任何客户包目录） |
| 客户包目录 | **一个都没动**（16 包逐个只读扫描） |
| `status/app/CORRECTIONS_APP.md` | **SHA 零改动**（全程只读、未改、未提交） |
| 新增产物 | `results/app/_app429_self_ref_clone_gate.py`／`app429_self_ref_clone_gate.json`（2 104 B／`c92ff5f6953fc9b3…`）／`_app430_pkg_dev_only_assert_gate.py`／`app430_pkg_dev_only_assert_gate.json`（3 593 B／`ecb8071cf2cf2c1a…`）／`_app431_write_status174.py`／`_app431_sec174_body.md` |

* 🔴 **未做**：未打包 v2.5｜未同步任何客户包目录｜未改桌面快捷方式｜未通知用户｜未调 MiniMax｜未占设备｜未持 `MACHINE_LOCK`｜未删任何文件｜交付配置仍冻结（全 NPU／spkonly／INT8；EXT v0.3.7 @c414294）。
* 🔴 **两处修复都只落在 dev 树 / 打包规则**，⇒ **对已交付包零影响**（§② 逐包判定）｜**v2.5 未打包** ⇒ 这两处修复**尚未进入任何客户包** ⇒ **等 reviewer 复核后再随 v2.5 一起出**（APP-055：走新版本号）。

### ⑥ 下一轮必读

* 节点＝**等 reviewer 复核 §174**（self_ref 闸门 2 处 ＋ `assert_*.py` 排除规则 2 项待裁定）。
* 🔴 **仍未裁定**（等 reviewer）：倍率地板｜GUI 布局修复同步策略｜§3.5 判据失效｜§3.6 不可测。
* 🔴 **v2.5 建包时**：`assert_*.py` **不会**再随包（缺陷 ② 已修）⇒ **只允许 `assert_pkg_clean.py` 在包内**。
* 🔴 **v2.5 打包**：`pack_v13.py` 的 `pkg_exclude` 改动 ⇒ **闸门③**（`PKG_INCLUDE_FILES` / 交付洁净度 / 补丁）**须复跑**。
* v2.5 **不打包**（用户不通知 ⇒ 不主动打包）｜磁盘 22.7 G（99 %）。
