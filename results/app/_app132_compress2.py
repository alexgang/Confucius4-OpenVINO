#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""再压缩 §132（②③④⑥⑧）约 2 KB —— **只删修饰，事实/数字/路径/判据名全留**。"""
import os

P = 'status/app/STATUS_APP.md'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

REPS = [
    # ② 表格压缩
    ("""| **D4 bug** | `_on_mt_combo_changed` 在 `_enforce_no_npu_conflict` 之后又 `set_engine(opt['engine'])`＋`set_device(opt['device'])` ⇒ **把 MT 覆盖回 NPU**（配置写 GPU.0、实际跑 NPU、还弹框说「已改到 GPU.0」） | ①enforce 命中 ⇒ **重读 `opt`**（`_forced` 分支）②`enforce` 内部补 **set_engine(GPU.0 那一项的 engine) → set_device('GPU.0')**（原只调 set_device ⇒ engine 与设备不一致）③**CLI 侧**补 `--mt-device NPU --tts-device NPU` ⇒ MT 自动改 GPU.0 ＋ 打日志 | `app229` 行为探针：`mt.device='GPU.0'`、`mt.engine_key='gpu_int8cw'`、落盘 `mt='GPU.0'`；反证（删掉重读分支 ⇒ 判据失效）**PASS** |
| **D2(a)** | GUI 启动 `--tts-voice follow_speaker` / `_on_tts_toggled` 开启 TTS ⇒ 自动开旁路（原来只打日志「将使用预设 A」） | 启动路径 + `_on_tts_toggled` 克隆分支 ⇒ 都调 `_enable_speaker_for_clone`（幂等） | `app229` `d2a_toggled_calls_enable` / `d2a_startup_calls_enable` **PASS** |
| **D2(b)** | CLI `--tts-voice follow_speaker` ⇒ `_spk_enabled` 必须为 True（原来只看 `--speaker`） | `_want_clone` **提前**计算 ⇒ `_spk_enabled=True`（**显式 `--speaker off` 也不覆盖** ⇒ 克隆没有 spk 就没法用） | `app229` `d2b_*` 4 条 **PASS** ＋ 反证 **PASS** |
| **D2(c)** | 取消「说话人识别」勾选 ⇒ 音色切回 A 并提示（或禁止取消）；原来 `cb_speaker` **没绑任何事件** | 新增 `_on_speaker_toggled`：取消 ⇒ 音色切「预设 A」＋ 重启 worker ＋ 状态栏/日志提示；勾选 ⇒ 同步 bridge.enabled | `app229` 行为探针：取消后 `var_tts_voice='预设 A'`、`bridge.enabled=False` **PASS** ＋ 反证 **PASS** |
| **D2(d)** | 会话进行中自动开旁路 ⇒ **真正把线程拉起来**（原来状态栏说「开」但实际要重启会话） | `SpeakerBridge.ensure_started()`（新增，**主动** `_ensure_worker()`）＋ `_enable_speaker_for_clone` 判定 `session.running` ⇒ 会话在跑就即时拉起，状态栏「**已即时生效，无需重启会话**」；拉起失败才如实写「需重启会话后生效」 | `app229`：`ensure_started` 被调用 1 次 ＋ 状态栏含「已即时生效」**PASS** |""",
     """| **D4 bug** | `_on_mt_combo_changed` 在 enforce 之后又 `set_engine/set_device(opt)` ⇒ **把 MT 覆盖回 NPU**（配置写 GPU.0、实际跑 NPU、还弹框说「已改到 GPU.0」） | ①enforce 命中 ⇒ **重读 `opt`**（`_forced`）②enforce 内补 **set_engine(GPU.0 那一项) → set_device('GPU.0')**（原只调 set_device ⇒ engine 与设备不一致）③**CLI** 补 `--mt-device NPU --tts-device NPU` ⇒ 改 GPU.0 ＋ 日志 | `app229` 探针：`mt.device='GPU.0'`、`engine_key='gpu_int8cw'`、落盘 `mt='GPU.0'`；反证（删重读分支⇒失效）**PASS** |
| **D2(a)** | GUI 启动 `--tts-voice follow_speaker` / `_on_tts_toggled` ⇒ 自动开旁路（原来只打日志「将使用预设 A」） | 启动路径 + `_on_tts_toggled` 克隆分支 ⇒ 都调 `_enable_speaker_for_clone`（幂等） | `d2a_*` 2 条 **PASS** |
| **D2(b)** | CLI `--tts-voice follow_speaker` ⇒ `_spk_enabled=True`（原来只看 `--speaker`） | `_want_clone` **提前**算 ⇒ 强制 True（**显式 `--speaker off` 也不覆盖**） | `d2b_*` 4 条 **PASS** ＋ 反证 **PASS** |
| **D2(c)** | 取消「说话人识别」勾选 ⇒ 音色切回 A 并提示（或禁止取消）；原来 `cb_speaker` **没绑事件** | 新增 `_on_speaker_toggled`：取消 ⇒ 切「预设 A」＋重启 worker ＋状态栏/日志提示；勾选 ⇒ 同步 bridge.enabled | 探针：取消后 `var_tts_voice='预设 A'`、`bridge.enabled=False` **PASS** ＋ 反证 **PASS** |
| **D2(d)** | 会话进行中 ⇒ **真正拉起线程**（原来状态栏说「开」但要重启会话才生效） | 新增 `SpeakerBridge.ensure_started()`（主动 `_ensure_worker()`）＋ 判定 `session.running` ⇒ 即时拉起，状态栏「**已即时生效，无需重启会话**」；失败才如实写「需重启会话后生效」 | `ensure_started` 调用 1 次 ＋ 状态栏含「已即时生效」**PASS** |"""),
    # ③ 表格压缩
    ("""| 项 | 值 | 结论 |
|---|---|---|
| ASR 唯一事实来源 `asr_spk_window.WIN_S` | **5.0**（2026-11-02 16:20 改） | ✅ |
| App 侧解析 `_WIN_S` / 来源 | **5.0** ／「同源 `asr_spk_window.WIN_S=5.0`」 | ✅ **App 没写第二份默认值**（reviewer 要求） |
| App 喂窗样本数 | **80 000**（5.0 × 16 k） | — |
| ASR 内核 `asr052_spk_runtime.WIN_N` | **160 000**（仍写死 10 s） | 🔴 **错位** |
| ASR 内核 `N_FRAMES` | **589**（写死 10 s 的帧数；5 s 应为 293） | 🔴 **错位** |
| ASR 内核 `FPS` | **58.9**（10 s 帧率；5 s 应为 58.6） | 🔴 **错位** |
| 客户包 `app/asr_spk/` 含 `asr_spk_window.py`？ | **否**（v2.2 只有 `asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | 🔴 客户机仍退回 10 s |""",
     """| 项 | 值 | 结论 |
|---|---|---|
| ASR 唯一事实来源 `asr_spk_window.WIN_S` | **5.0**（2026-11-02 16:20 改） | ✅ |
| App 解析 `_WIN_S` / 来源 | **5.0** ／「同源 `asr_spk_window.WIN_S=5.0`」 | ✅ **没写第二份默认值**（reviewer 要求） |
| App 喂窗样本数 | **80 000**（5.0×16 k） | — |
| 内核 `asr052_spk_runtime.WIN_N` / `N_FRAMES` / `FPS` | **160 000**（仍 10 s）/ **589**（5 s 应 293）/ **58.9**（应 58.6） | 🔴 **三处错位** |
| 客户包 `app/asr_spk/` 含 `asr_spk_window.py`？ | **否**（v2.2 只有 `asr052_speaker_tracker_api.py`/`asr052_spk_runtime.py`/`asr_thread_defaults.py`） | 🔴 客户机仍退回 10 s |"""),
    # ⑧ 压缩
    ("""1. 🔴 **D1 的跨模块错位**（③）⇒ **ASR 侧必须同源**（`asr052_spk_runtime` 读 `asr_spk_window`）；**v2.3 建议暂缓发布**。
2. 🔴 **70 % 字幕区 vs 5 组竖排**（④）⇒ 需 reviewer 在「接受 66.88 %」与「允许 ④ 组第二个标签列」之间选一个。
3. 🔴 **seg IR 是否已导成 5 s 静态形状**（③ 的 NOTICE 问题 2）⇒ 若还是 10 s 形状 ⇒ 切 5 s 会**直接报输入形状不匹配**。
4. 🔴 **app215 的 2 条既有 FAIL**（⑦）⇒ 是否本轮顺手修（属 APP-061①「音色错误提示」范畴）。""",
     """1. 🔴 **D1 跨模块错位**（③）⇒ **ASR 侧必须同源**（`asr052_spk_runtime` 读 `asr_spk_window`）；**v2.3 建议暂缓发布**。
2. 🔴 **70 % 字幕区 vs 5 组竖排**（④）⇒ 请 reviewer 在「接受 66.88 %」与「允许 ④ 组第二个标签列」间选。
3. 🔴 **seg IR 是否已导成 5 s 静态形状**（③ NOTICE 问题 2）⇒ 若仍是 10 s 形状 ⇒ 切 5 s 会**直接报形状不匹配**。
4. 🔴 **app215 的 2 条既有 FAIL**（⑦）⇒ 是否顺手修（属 APP-061①「音色错误提示」）。
5. 🔴 **判据①的假 PASS 已修**（⑪-1）⇒ 请 reviewer 确认「三条故障串」的口径。"""),
    # ⑥ 压缩
    ("""#### ⑥ ✅ **APP-064（锁纪律）** ｜ 本轮设备级作业**先拿 `MACHINE_LOCK` 再跑**（日志 `[lock] 已取得机器锁` ＋ `app PID 29324 started 2026-11-02 20:52:05`），且**先探安静窗口**（`wait_quiet_window_cpu` ⇒ 安静 20 s 后才开始）；APP-063-4 的 `app223 --run` 已指向**本轮影子包**（`shared/app065_shadow`，硬链接自 v2.2 ＋ 同步本轮 2 个改动文件，**自检 PASS**）⇒ **测的是本轮代码**，不是 v2.2 的旧码。""",
     """#### ⑥ ✅ **APP-064（锁纪律）** ｜ 设备级作业**先拿 `MACHINE_LOCK` 再跑** ＋ **先探安静窗口**（`wait_quiet_window_cpu`）；`app223 --run` 指向**本轮影子包**（`shared/app065_shadow`）⇒ **测的是本轮代码**，不是 v2.2 旧码。细节见 ⑩。"""),
]
for a, b in REPS:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:60]))
    txt = txt.replace(a, b)

data = txt.encode('utf-8')
print('压缩后：%d B（原 39112 B）' % len(data))
open(P, 'wb').write(data)
print('OK')
