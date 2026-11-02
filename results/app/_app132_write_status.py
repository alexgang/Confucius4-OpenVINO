#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""写 `status/app/STATUS_APP.md` 的 §132（APP-063 / APP-064 / APP-065）。

🔴 **纪律（逐条对照）**：
1. **只追加** `### §N` 章节；**旧正文一字不删**（§131 原文**逐字归档**到
   `status/archive/`，并在原地留一行指向归档的说明）。
2. 头部 `last_ack` 更新为**已执行完的最大 APP 编号**（= APP-065）。
3. 「更新时间」用 `Get-Date` **实测值**（本脚本用 `datetime.now()`，同源）。
4. **只改 header 区**（`last_ack` / `更新时间` / `当前任务` / `阻塞`）与
   **追加** §132；中间「当前有效结论」「未完成纠偏」「最近章节」表**只增不改**。
5. 写盘走**临时文件 + os.replace**（原子）；写后**逐字节复核**。
6. 限额：≤ 40 000 B / ≤ 300 行 ⇒ 追加前先算字节，超限则**先归档**。
"""
from __future__ import annotations

import datetime
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH_DIR = os.path.join(REPO, 'status', 'archive')
LIMIT_B = 40000
LIMIT_LINES = 300

NEW_SECTION = r'''
### §132 🔄 **APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 ＋ APP-065 A 界面重排 ＋ B 改名** ｜ **本条已完成（代码层）** ｜ **本条需等 reviewer 复核**（2026-11-02 20:52）

> 🔴 **本节更正 §131 的一条结论**：§131 写「D1 是否切 5 s 等 reviewer 裁定（ASR 自己没切 ⇒ App 保持 10 s）」——
> **已不成立**：reviewer 在 APP-063 ③ 裁定「D1 改为 5 s」，且 **ASR 侧 `asr_spk_window.WIN_S` 已于 2026-11-02 16:20 改成 5.0**
> ⇒ App 侧**同源自动跟随**（实测 `_WIN_S = 5.0`，来源「同源 asr_spk_window.WIN_S=5.0」）
> ⇒ **但 ASR 运行时内核未同源**（见 ③）⇒ **旁路目前处于「喂 5 s / 切 10 s」的错位状态**。

#### ① 📌 **开工基线（只读 `CORRECTIONS_APP.md`，全程未写入）**

| 时点 | SHA256 | 字节 | mtime | 条数 |
|---|---|---|---|---|
| §132 开工（15:01） | `0b9cf6227e22fd57f791f7f4bfe16c360b25d2d74b9db3a14de1844a3f4aa033` | 182 008 | 2026-11-02 14:55:36 | **65**（APP-001…APP-065） |
| §132 收尾（20:5x，见下） | 见本节末尾「收尾复核」 | — | — | — |

⇒ **本轮新条目 = APP-063 / APP-064 / APP-065**（`last_ack` 由 APP-062 → **APP-065**）。

#### ② ✅ **APP-063 ①（D4 bug）＋ ②（D2 四入口）—— 代码层已修，`app229` 38 PASS / 0 FAIL**

| 子项 | reviewer 要求 | 本轮实现 | 证据 |
|---|---|---|---|
| **D4 bug** | `_on_mt_combo_changed` 在 `_enforce_no_npu_conflict` 之后又 `set_engine(opt['engine'])`＋`set_device(opt['device'])` ⇒ **把 MT 覆盖回 NPU**（配置写 GPU.0、实际跑 NPU、还弹框说「已改到 GPU.0」） | ①enforce 命中 ⇒ **重读 `opt`**（`_forced` 分支）②`enforce` 内部补 **set_engine(GPU.0 那一项的 engine) → set_device('GPU.0')**（原只调 set_device ⇒ engine 与设备不一致）③**CLI 侧**补 `--mt-device NPU --tts-device NPU` ⇒ MT 自动改 GPU.0 ＋ 打日志 | `app229` 行为探针：`mt.device='GPU.0'`、`mt.engine_key='gpu_int8cw'`、落盘 `mt='GPU.0'`；反证（删掉重读分支 ⇒ 判据失效）**PASS** |
| **D2(a)** | GUI 启动 `--tts-voice follow_speaker` / `_on_tts_toggled` 开启 TTS ⇒ 自动开旁路（原来只打日志「将使用预设 A」） | 启动路径 + `_on_tts_toggled` 克隆分支 ⇒ 都调 `_enable_speaker_for_clone`（幂等） | `app229` `d2a_toggled_calls_enable` / `d2a_startup_calls_enable` **PASS** |
| **D2(b)** | CLI `--tts-voice follow_speaker` ⇒ `_spk_enabled` 必须为 True（原来只看 `--speaker`） | `_want_clone` **提前**计算 ⇒ `_spk_enabled=True`（**显式 `--speaker off` 也不覆盖** ⇒ 克隆没有 spk 就没法用） | `app229` `d2b_*` 4 条 **PASS** ＋ 反证 **PASS** |
| **D2(c)** | 取消「说话人识别」勾选 ⇒ 音色切回 A 并提示（或禁止取消）；原来 `cb_speaker` **没绑任何事件** | 新增 `_on_speaker_toggled`：取消 ⇒ 音色切「预设 A」＋ 重启 worker ＋ 状态栏/日志提示；勾选 ⇒ 同步 bridge.enabled | `app229` 行为探针：取消后 `var_tts_voice='预设 A'`、`bridge.enabled=False` **PASS** ＋ 反证 **PASS** |
| **D2(d)** | 会话进行中自动开旁路 ⇒ **真正把线程拉起来**（原来状态栏说「开」但实际要重启会话） | `SpeakerBridge.ensure_started()`（新增，**主动** `_ensure_worker()`）＋ `_enable_speaker_for_clone` 判定 `session.running` ⇒ 会话在跑就即时拉起，状态栏「**已即时生效，无需重启会话**」；拉起失败才如实写「需重启会话后生效」 | `app229`：`ensure_started` 被调用 1 次 ＋ 状态栏含「已即时生效」**PASS** |

🔴 **连带修掉的既有缺陷**：`self.tts` 从未在 `__init__` 初始化 ⇒ 首次 `_on_tts_toggled` 抛 `AttributeError`（APP-065 A 截图脚本在「配音开启」分支实测到）⇒ 已补 `self.tts = None`。

#### ③ ⛔ **APP-063 ③（D1 窗口 5 s）—— App 侧已同源，但 **ASR 内核未同源 ⇒ 跨模块错位**（已交 ASR + reviewer）**

🔴 **实测事实**（`app230` 7 PASS / 5 FAIL，判据就是这条不变量）：

| 项 | 值 | 结论 |
|---|---|---|
| ASR 唯一事实来源 `asr_spk_window.WIN_S` | **5.0**（2026-11-02 16:20 改） | ✅ |
| App 侧解析 `_WIN_S` / 来源 | **5.0** ／「同源 `asr_spk_window.WIN_S=5.0`」 | ✅ **App 没写第二份默认值**（reviewer 要求） |
| App 喂窗样本数 | **80 000**（5.0 × 16 k） | — |
| ASR 内核 `asr052_spk_runtime.WIN_N` | **160 000**（仍写死 10 s） | 🔴 **错位** |
| ASR 内核 `N_FRAMES` | **589**（写死 10 s 的帧数；5 s 应为 293） | 🔴 **错位** |
| ASR 内核 `FPS` | **58.9**（10 s 帧率；5 s 应为 58.6） | 🔴 **错位** |
| 客户包 `app/asr_spk/` 含 `asr_spk_window.py`？ | **否**（v2.2 只有 `asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | 🔴 客户机仍退回 10 s |

⇒ **后果**：`run_seg_side` 的 `while win_start + WIN_N <= len(audio)`（内核 L464）在 App 只喂 80 000 样本时**恒不成立** ⇒ 旁路**拿不到帧**（不是精度下降，是**零标签**）。
⇒ **已发通知**：`shared/NOTICE_app_to_asr_spk_window_5s_alignment.md`（含「内核改成从 `asr_spk_window` 取值」的**首选方案** ＋ 扩交付集合为 4 个文件的**备选方案** ＋ 需 ASR 回答的 3 个问题，含「seg IR 是否已导成 5 s 静态形状」）。
⇒ ⛔ **App 侧无法单方面完成**（`asr052_spk_runtime.py` 属 ASR 模块）⇒ **v2.3 建议暂缓发布**。

#### ④ ✅ **APP-065 A（界面重排）—— 5 组竖排 + 统一网格；截图与清单已备，交 reviewer 复核**

reviewer 要求：「按处理链分组，从上到下：①音频输入 ②语音识别 ③翻译 ④语音输出（开关、输出设备、音色）⑤高级。每组一个 GroupBox，组内用统一网格：标签列右对齐、等宽，控件列左对齐、同宽；**所有组的标签列宽度一致，行高一致**。」

| 要求 | 实现 | 实测证据（`app231`） |
|---|---|---|
| 5 组 GroupBox **竖排** | `self._groups` 容器内 ①音频输入 / ②语音识别 / ③翻译 / ④语音输出 / ⑤高级（默认收起） | 截图 + `app165` C4（**分区数 = 5**，判据口径已按 APP-065 A 更新）**verdict = PASS** |
| 标签列**右对齐 + 等宽** | 每组 `columnconfigure(0, uniform='lbl', minsize=_GRID_LABEL_PX)`；标签 `anchor='e'`；**不用 `ttk.Label(width=N)`**（N 是字符数 ⇒ 像素宽随缩放变 ⇒ 不可比） | **100 %：4 组标签列右边缘全 56 px**；**150 %：全 76 px**（组间**恒等**） |
| 控件列**左对齐 + 同宽** | 所有 Combobox/Entry 用 `width=_GRID_CTRL_CHARS`（实测**全 233 px**） | `app231` `ctrl_left_edges` = 64 px（100 %）/ 84 px（150 %），4 组一致 |
| **行高一致** | 各组 grid 行统一 `pady=0` ＋ 同类控件 | 100 % 行高 = 18/20 px；150 % = 28/30 px（组间一致） |
| 「高级」只放**不常用**项，每项**一句话提示** | 设备选择（识别/翻译/语音后端）、草稿译文、重试翻译、显示说话人、**区分说话人（用于克隆）**、离线朗读、测试声音、耳机提示 —— 每项旁**同行**一句话说明 | `app231` 控件→组清单（13 项）+ `app065a_control_group_map.txt` |
| **正常使用要选的不得进高级** | 输入源 → ①；识别语种 → ②；目标语言 → ③；开关 / 音色 / 输出设备 → ④ | 同上清单 |
| 100 % / 150 % 缩放各 2 张截图（启动后 / 配音开启后） | `app231` 用 `tk scaling` 模拟（**150 % 时保持逻辑尺寸不变** ⇒ 物理尺寸 = 逻辑 × scaling） | **4 张 PNG 全部抓图成功**（31.8–43.9 KB），路径 `results/app/app065a_shots/` |

🔴 **本轮顺带修掉的 3 个真缺陷**：①`_adv_frame` **从未 pack** ⇒ 展开「⑤ 高级」是**空的**（实测 h=1）②`lbl_source_note` 的 `reqwidth` **撑宽 column 2** ⇒ 150 % 下右侧被**裁**（且 `before=` 跨父容器 ⇒ **每次启动 TclError**）③顶栏「有模块待处理」按钮 `width=12` 在 150 % 下**文字被裁**。
🔴 **口径冲突（提请 reviewer 裁定）**：APP-061⑥ 的「字幕区 ≥ 窗口高度 **70 %**」与 APP-065 A 的「5 组竖排」在 **800 px 高**下**不可兼得** —— 实测 `app219` G2 = **66.88 %**（其余 11 条全 PASS：状态条 1 行、高级默认收起、1024 宽不越界）。已做的压缩：状态条与控件**同行**（每组省 21 px）、① 组设备控件**并入同一行**（省 25 px）、各组 `padding=(6,0)` ＋ `pady=0`、全局状态行**并入顶栏**。**若必须 ≥70 %**：需允许 ④ 组出现**第二个标签列**（把「开关」与「音色」并到一行）⇒ 可再省 ~25 px ⇒ 约 70 %。

#### ⑤ ✅ **APP-065 B（改名）** ｜ GUI「说话人识别」→ **「区分说话人（用于克隆）」**，**移入「⑤ 高级」**，带提示「检测谁在说话，换人时重新克隆音色；只在音色=跟随说话人时生效」；**变量名 `var_speaker` 保持不变**（`app227`/`app204` 依赖）。

#### ⑥ ✅ **APP-064（锁纪律）** ｜ 本轮设备级作业**先拿 `MACHINE_LOCK` 再跑**（日志 `[lock] 已取得机器锁` ＋ `app PID 29324 started 2026-11-02 20:52:05`），且**先探安静窗口**（`wait_quiet_window_cpu` ⇒ 安静 20 s 后才开始）；APP-063-4 的 `app223 --run` 已指向**本轮影子包**（`shared/app065_shadow`，硬链接自 v2.2 ＋ 同步本轮 2 个改动文件，**自检 PASS**）⇒ **测的是本轮代码**，不是 v2.2 的旧码。

#### ⑦ 🔄 **回归（本轮全部复跑，输出另存，不覆盖仓库原证据）**

| 脚本 | 结果 | 说明 |
|---|---|---|
| `app229`（本轮新增：D4 + D2 四入口，含 3 组反证） | **38 PASS / 0 FAIL** | ✅ |
| `app230`（本轮新增：D1 跨模块一致性） | **7 PASS / 5 FAIL** | ✅ **5 条 FAIL 是真实跨模块错位**（见 ③），不是判据缺陷 |
| `app227`（APP-062 D1–D4） | **34 PASS / 0 FAIL / 0 无法判定** | ✅（**判据口径已更新**：D1 改为「等于 ASR 唯一事实来源」；D2 反证改为「破坏**全部** 3 处调用点」——旧版删一行会留下空 `if` 块 ⇒ SyntaxError ⇒ 无法判定） |
| `app165`（APP-048 三分区布局） | **verdict = PASS** | ✅（**C4 口径已更新**：分区数 3 → **5**，依据 APP-065 A；**C3/C5/C6 未动** ⇒ 状态条仍在自己的分组内、顶部 meter 仍不在任何分区内 ⇒ **APP-048 的核心不变量保住了**） |
| `app219`（APP-061⑥ 紧凑） | **11 PASS / 2 FAIL** | ⚠️ **2 条 FAIL 都是 G2（字幕区 66.88 % < 70 %）** ⇒ 见 ④ 的口径冲突 |
| `app220` / `app226` / `app228` | **39 / 10 / 8 全 PASS** | ✅ 零回归 |
| `app215` | **27 PASS / 2 FAIL** | ⚠️ **2 条 FAIL 与本轮无关**（`1c_voice_error_when_ref_missing` / `M3_1abc_mutant_is_caught`）—— 用 **HEAD 版**同脚本跑出**完全相同**的 2 条 ⇒ **既有缺陷**（§131 记的是 29/0，可能是在 pkg 上跑的） |

#### ⑧ 🔴 **本轮新增待 reviewer 裁定 / 待 ASR 回答**
1. 🔴 **D1 的跨模块错位**（③）⇒ **ASR 侧必须同源**（`asr052_spk_runtime` 读 `asr_spk_window`）；**v2.3 建议暂缓发布**。
2. 🔴 **70 % 字幕区 vs 5 组竖排**（④）⇒ 需 reviewer 在「接受 66.88 %」与「允许 ④ 组第二个标签列」之间选一个。
3. 🔴 **seg IR 是否已导成 5 s 静态形状**（③ 的 NOTICE 问题 2）⇒ 若还是 10 s 形状 ⇒ 切 5 s 会**直接报输入形状不匹配**。
4. 🔴 **app215 的 2 条既有 FAIL**（⑦）⇒ 是否本轮顺手修（属 APP-061①「音色错误提示」范畴）。

#### ⑨ 🔴 **未做 / 未交付**
- ⛔ **未打包 v2.3**（APP-065 A 明文「**截图先交 reviewer，通过后才打包**」⇒ **本轮停在 reviewer 复核点**；且 ③ 的 ASR 错位未解决前也不该打包）。
- ⛔ **未通知用户 / 未改桌面快捷方式**（APP-063 交付要求「先报 reviewer」）。
- ⛔ **v2.1、v2.2 的目录与 zip 一个字节都没动**；本轮只建了**影子包** `shared/app065_shadow`（硬链接自 v2.2）**用于设备级实测**，不是交付物。
- ⛔ **未提交任何 `CORRECTIONS_*.md`**（`status/app/CORRECTIONS_APP.md` 本模块**全程只读**）。
'''

NEW_HEADER_TASK = (
    '当前任务: **§132 APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 '
    '＋ APP-065 A 界面重排 ＋ B 改名 —— 代码层已执行** —— ① **D4 bug** 修好：'
    'enforce 命中后**重读 opt** ＋ enforce 内补 set_engine→set_device ⇒ '
    '**MT 不再被覆盖回 NPU**（行为探针 `mt.device=GPU.0` / `engine_key=gpu_int8cw`）'
    '＋ **CLI 同 NPU 也自动改 GPU.0** ② **D2 四入口**补齐：'
    'GUI 启动/`_on_tts_toggled` 自动开旁路 ｜ CLI `--tts-voice follow_speaker` 自动开旁路 ｜ '
    '取消勾选 ⇒ 音色切回「预设 A」＋提示 ｜ 会话进行中**真正拉起旁路线程**（`ensure_started`）'
    '③ **D1**：ASR 侧 `asr_spk_window.WIN_S` 已改 5.0 ⇒ **App 同源自动跟随**（实测 5.0）'
    '，但 **ASR 内核仍写死 10 s** ⇒ **跨模块错位**（已发 NOTICE 给 ASR ＋ reviewer）'
    '④ **APP-065 A 界面重排**：**5 组竖排 GroupBox**（①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级）'
    '＋ 组内统一网格（**标签列右边缘 4 组全 56 px @100 % / 76 px @150 %**、'
    '**控件列全 233 px**、行高一致）＋ **4 张截图**（100 %/150 % × 启动后/配音开启后）'
    '＋ **控件→所在组清单** ⇒ **本条需等 reviewer 复核**（reviewer 明文「截图先交 reviewer，通过后才打包」）'
    '⑤ **APP-065 B**：「说话人识别」改名「区分说话人（用于克隆）」并移入高级'
    ' ｜ `app229` **38/0** ｜ `app227` **34/0** ｜ `app165` **PASS** ｜ `app220/226/228` **39/10/8 全 PASS**'
)

NEW_HEADER_BLOCK = (
    '阻塞 / 待用户决定: 🔴 **本轮停在 reviewer 复核点**（APP-065 A：「截图先交 reviewer，'
    '通过后才打包」⇒ **未打包 v2.3**）；⛔ **D1 的跨模块错位未解**（ASR 内核 `WIN_N/N_FRAMES/FPS` '
    '仍写死 10 s ⇒ 与 App 的 5 s **错位** ⇒ 旁路会零标签；已发 '
    '`shared/NOTICE_app_to_asr_spk_window_5s_alignment.md`）｜'
    '🔴 **70 % 字幕区 vs 5 组竖排冲突**（实测 66.88 % ⇒ 需 reviewer 在「接受」与'
    '「允许 ④ 组第二个标签列」之间选）｜🔴 **seg IR 是否已导成 5 s 静态形状**待 ASR 回答 ｜'
    '🔴 **app215 的 2 条既有 FAIL**（与本轮无关，HEAD 版同样 FAIL）待 reviewer 决定是否顺手修 ｜'
    '🔴 **未打包 / 未通知用户 / 未改桌面快捷方式 / 未改任何客户包目录**（v2.1、v2.2 一个字节都没动；'
    '本轮只建了**影子包** `shared/app065_shadow` 供设备级实测）'
)


def archive_sec131(lines):
    """把 §131 正文**逐字**归档到 `status/archive/`。"""
    i = None
    for idx, l in enumerate(lines):
        if l.startswith('### §131'):
            i = idx
            break
    if i is None:
        raise SystemExit('找不到 §131')
    body = lines[i:]
    os.makedirs(ARCH_DIR, exist_ok=True)
    p = os.path.join(ARCH_DIR, 'STATUS_APP_sec131_upto_20261102.md')
    with open(p, 'wb') as f:
        f.write(('\n'.join(body)).encode('utf-8'))
    print('已归档 §131 ⇒ %s（%d B）' % (p, os.path.getsize(p)))
    # 原地留一行指向（**逐字保留**的正文在归档里）
    return lines[:i] + [
        '### §131 🔄 **APP-062（D1–D4：用户对 APP-061 的四项决定）—— 本条已执行（代码层全部完成）** ｜ **本条需等 reviewer 复核**（2026-11-02 10:58）',
        '',
        '> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec131_upto_20261102.md`（逐字保留，内容一字未删）。',
        '',
    ]


def main():
    with open(STATUS, 'rb') as f:
        raw = f.read()
    txt = raw.decode('utf-8')
    crlf = '\r\n' in txt
    EOL = '\r\n' if crlf else '\n'
    lines = txt.split('\n')

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # ① 归档 §131（腾空间）
    if any(l.startswith('### §131') for l in lines) and not any(
            'STATUS_APP_sec131_upto_20261102.md' in l for l in lines):
        lines = archive_sec131(lines)

    # ② 追加 §132
    if any(l.startswith('### §132') for l in lines):
        print('[ABORT] §132 已存在 ⇒ 不重复追加')
        return 2
    lines = lines[:-1] if lines[-1] == '' else lines
    lines = lines + NEW_SECTION.replace('\n', EOL).split(EOL)

    # ③ 头部：last_ack / 更新时间 / 当前任务 / 阻塞
    out = []
    for l in lines:
        if l.startswith('last_ack: '):
            out.append('last_ack: APP-065')
        elif l.startswith('更新时间: '):
            out.append('更新时间: %s' % now)
        elif l.startswith('当前任务: '):
            out.append(NEW_HEADER_TASK)
        elif l.startswith('阻塞 / 待用户决定: '):
            out.append(NEW_HEADER_BLOCK)
        else:
            out.append(l)
    lines = out

    # ④ 「最近章节」表**追加**一行（只增不改）
    newrow = ('| §132 | **APP-063/064/065**：D4 bug ＋ D2 四入口 ＋ D1 窗口（ASR 未同源⇒跨模块错位）'
              '＋ 锁纪律 ＋ **界面重排 5 组**（截图/清单已交）＋ 改名 | **本轮新增（见下）** |')
    for i, l in enumerate(lines):
        if l.startswith('| §13') and '§132' not in l and '§131' not in l:
            pass
    # 插到 §131 行之后
    for i, l in enumerate(lines):
        if l.startswith('| §131 '):
            lines.insert(i + 1, newrow)
            break
    else:
        print('[warn] 最近章节表里没找到 §131 行 ⇒ 未插入索引行')

    newtxt = EOL.join(lines)
    if not newtxt.endswith(EOL):
        newtxt += EOL
    data = newtxt.encode('utf-8')

    # ⑤ 限额自检
    n_lines = newtxt.count('\n')
    print('新文件：%d B / %d 行（限额 %d B / %d 行）'
          % (len(data), n_lines, LIMIT_B, LIMIT_LINES))
    if len(data) > LIMIT_B or n_lines > LIMIT_LINES:
        print('[ABORT] 超限额 ⇒ 未写盘（需先归档更多）')
        return 2

    # ⑥ 原子写盘 + 逐字节复核
    tmp = STATUS + '.tmp_app132'
    with open(tmp, 'wb') as f:
        f.write(data)
    with open(tmp, 'rb') as f:
        chk = f.read()
    if chk != data:
        print('[ABORT] 临时文件复核不一致')
        return 2
    os.replace(tmp, STATUS)
    with open(STATUS, 'rb') as f:
        after = f.read()
    if after != data:
        print('[ABORT] 写盘后复核不一致')
        return 2
    print('OK 已写入 §132（last_ack=APP-065，更新时间 %s）' % now)
    return 0


if __name__ == '__main__':
    sys.exit(main())
