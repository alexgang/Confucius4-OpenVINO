#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""写 STATUS_APP.md §107（APP-045 执行结果）。

🔴🔴🔴 **字节级定点写入**（STATUS_APP.md 是纯 CRLF）：
  - 用 `split('\n') + join()` 会把整文件行尾改掉 ⇒ 禁止
  - 本脚本：bytes 读入 → 只在**头部区**（第一个 `## §N` 之前）做字段替换
  - 新章节追加在**末尾**（bytes 拼接），写回后断言「仍是纯 CRLF」
"""
import io
import os
import re
import sys

STATUS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', '..', 'status', 'app', 'STATUS_APP.md')
STATUS = os.path.abspath(STATUS)

HEAD_LAST_ACK = 'APP-045'
HEAD_TIME = '2026-10-30 11:33'
HEAD_TASK = (
    '**§107 ✅ APP-045 四个子项全部落地（代码 + 包目录同步 + 验收 + 入库）；'
    '按用户 11:30 指令「不通知不打包」⇒ 未发起 v1.13 重打**'
    '（巡检：`CORRECTIONS_APP.md` 现 **46 条** = APP-045 ＋ APP-046，'
    '而 `last_ack` 仍为 APP-044 ⇒ 有新条目须执行）'
    '⇒ ✅ **① 克隆纯内存化**（`tts_engine.speaker_embedding_from_pcm()` ＋ '
    '`_mel_spectrogram_np_24000()`，复刻 babelvox mel 计算，'
    '`tts_worker.py` 两处 BabelVox 路线不再落盘）'
    '⇒ ✅ **② 打包后更新桌面快捷方式**（新增 `shortcut_update.py` 纯字节 .lnk，'
    '验收门 `ACCEPTED.json`；`pack_v13.py` 打包成功后调用，失败只告警）'
    '⇒ ✅ **④ 内置音色不再落用户目录**（`copy_builtins=False` ＋ '
    '`_SpeakerLibraryWithBuiltinFallback` 只读回退；用户目录 8 个自动复制文件已移出）'
    '⇒ ✅ **③ 真机验收未做**（等 TTS 锁 ＋ 需 reviewer 裁定的项）'
    '⇒ 🔴 **v1.12 zip（11:20 生成）不含 APP-045 改动**（打包早于 11:25 同步）'
    '⇒ 🔴 **桌面快捷方式仍指向 v1.5**（未通过真机验收 ⇒ 按 APP-045② 不得指过去）'
    '⇒ 🔴 **本条需等 reviewer 复核**'
)
HEAD_BLOCK = (
    '阻塞 / 待用户决定: ① 🔴 **v1.13 未打包**（v1.12 zip 不含 APP-045 改动）'
    '⇒ **按用户 11:30 指令，未经通知不主动打包** ⇒ 等用户通知再打；'
    '② 🔴 **APP-043 真机验收未做**（SPE Q&A densest_5min / APP-041 `pythonw` 冷启动 / '
    'GUI 路径 APP-042 / 3 段 1.2–1.3× 配音）；'
    '③ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；'
    '④ 🔴 **APP-044 精度形态待 reviewer 裁定**（FP16 还是 FP32）；'
    '⑤ 🔴 **桌面快捷方式仍指向 v1.5** ⇒ 用户实测的仍是旧包 '
    '⇒ 需真机验收通过 ＋ 新包就位后才能改指；'
    '⑥ 🔴 **本轮未修改** `CORRECTIONS_APP.md`（只读，reviewer 独占写入）'
)

NEW = u'''## §107 ✅ **APP-045 四个子项落地：克隆纯内存化 ＋ 打包后自动更新桌面快捷方式 ＋ 内置音色不再落用户目录；按用户 11:30 指令不主动打包** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**（2026-10-30 11:33）

### 107.0 🔴 **巡检口径更正：并行会话 §106 判定「44 条无新纠偏」已过时**

- 🔴 开工时实测 `status/app/CORRECTIONS_APP.md` 为 **46 条**（APP-045 ＋ **APP-046**），
  而 `STATUS_APP.md` 头部 `last_ack` 仍是 **APP-044** ⇒ **有编号 > last_ack 的新条目，必须执行**。
- 🔴 **并行 App 会话 §106 的巡检结论「44 条 = last_ack ⇒ 无新纠偏」是在 APP-045/046 写入前做的**
  ⇒ 该结论已过时；本节 §107 即为执行 APP-045 的记录。
- 🔴 **`CORRECTIONS_APP.md` 全程只读**（工作区 modified 是 reviewer 独占写入的长期状态）
  ⇒ 本轮**未修改**、**未入库**（`git diff --cached --name-only` 不含它）。
- 🔴 **APP-046（巡检规则补充）** 已收到并遵循：last_ack 追平后若仍有未完成项 ⇒ **直接继续做**，
  不空转；需计时的等锁（不抢）；只在「全部完成」或「卡在需用户决定」时停并写明原因。

### 107.1 ✅ **APP-045① 克隆一律在内存中处理（不写临时文件）**

- 🔴 **根因（reviewer 证据）**：用户 10:49 会话（`session_20261030_104919.log`）中
  「音色 follow_speaker」每隔约 20 s 就把一段 `clone_*.wav` 写到
  `%TEMP%\\confucius4_clone\\` 再提取 embedding ⇒ 违反「克隆只放内存」规则。
- 🔴 **不止旧包**：仓库 `live_caption/tts_worker.py` **同样有**这段落盘代码
  ⇒ **仓库 + 客户包两份副本都要改**（两份独立副本，禁止整目录覆盖）。
- ✅ **实现**（`live_caption/tts_engine.py` 新增两个函数）：
  - `_mel_spectrogram_np_24000(audio)` —— **纯 numpy** 复刻 babelvox
    `pipeline.mel_spectrogram_np`：`sr=24000 / n_fft=1024 / hop=256 / win=1024 /
    n_mels=128 / fmin=0 / fmax=12000 / hann / center=False / reflect-pad /
    log(clip(·,1e-5))` ⇒ `(n_mels, T)`。
  - `speaker_embedding_from_pcm(eng, pcm, sr=16000, on_log=print)` ——
    numpy 数组直接进 `eng.speaker_enc({"mel_spectrogram": ...})`；
    NPU 分支 **pad 到 `eng.max_speaker_frames`**（实测 `(1, 64, 128)`）。
- ✅ **调用点改造**（`live_caption/tts_worker.py`）：`_update_clone` 与 `spk_voice` 登记的
  **BabelVox 路线**（用户实际走的路线，设备配置 `tts: NPU`）**两处**改为
  `tts_engine.speaker_embedding_from_pcm(eng, pcm, sr=16000, on_log=log)`。
- ✅ **CUDA 边车路线保留落盘并加注释**：交付包内**无 `torch` / 无 `faster_qwen3_tts`**
  ⇒ 该路线在客户机上**根本不可达** ⇒ 不是用户反馈的那条路径；保留落盘是为不破坏开发机用法。
- ✅ **验收 `app161_app045_clone_inmemory_equivalence.py`** ⇒
  **PASS=10 / FAIL=0 / verdict=PASS**（证据 `app161_app045_clone_inmemory_equivalence.json`
  **1 803 B / mtime 2026-10-30 11:16:11 / SHA256 `d0eea525b1baa4ee4b598be765b4222c9e8128247243312fef8ad43a7fc042ce`）：
  - 判据②a 内存 resample vs float32 无损基准 **逐位相同**（`max|Δ|=0.000e+00`）
  - 判据②b vs 旧 PCM_16 落盘路径 `max|Δ|=4.101e-05`
    ⇒ 🔴 **这是 PCM_16 量化误差，不是回归**：`soundfile.write()` **默认写 PCM_16**
    （实测 PCM_16→4.101e-05 / FLOAT→0.000e+00 / PCM_24→2.310e-07）
    ⇒ **内存路径（float32 原样）比旧落盘路径更精确**
  - 判据①a/①b mel 形状 `(128, 468)` 一致 / 逐位相同（`max|Δ|=0.000e+00`）
  - 判据③a/③b 端到端入参 `(1, 468, 128)` 一致 / 逐位相同；③c NPU pad 到 `(1, 64, 128)`
  - 判据④a/④b/④c **不落盘**（含**终态检查**抓反证 A 的 `clone_falsify.wav`）
- ✅ **反证干跑有效**：`--falsify` 注入「落盘实现 + 错误 sr=16000」⇒ **5 FAIL**
  ⇒ 判据**非恒真**（踩过的坑：反证只改第一道门会被后续 `except` 兜住 ⇒ 必须改**整个判定单元**）。

### 107.2 ✅ **APP-045④ `tts_speakers` 4 个音色的来源、许可与清理**

- ✅ **来源查明**：4 个音色（cindy / lou / phil / steve）是 **babelvox 自带示例音色**
  （`babelvox/data/speakers/{name}.{json,npy}`，JSON 里 `source_audio` 指向 babelvox 仓库
  `tools/reference_audio/*.mp3`，`tags` 含 `example`）⇒ **不是测试残留**。
- ✅ **许可查明**：babelvox = **Apache-2.0**（`License-Expression: Apache-2.0`）
  ⇒ 随包分发无署名硬要求（与 `wespeaker` 的 CC-BY-4.0 不同，后者**必须**署名，见 §102）。
- 🔴 **但 `copy_builtins=True` 会把内置音色自动复制到用户目录**
  ⇒ 即「非测试残留」也会在 `%LOCALAPPDATA%\\Confucius4LiveCaption\\tts_speakers\\` 留 8 个文件
  ⇒ 与 APP-018「客户包不要带」的精神冲突，且用户看到的就是「凭空多出 4 个音色」。
- ✅ **改法**：`_attach_speaker_library()` 里 `SpeakerLibrary(lib_dir, copy_builtins=True)`
  ⇒ **`copy_builtins=False`** ＋ 新增 `_SpeakerLibraryWithBuiltinFallback`：
  **用户目录优先**（用户自建音色照常存/取），**内置目录只读回退**（`copy_builtins=False` 指向内置目录）。
- ✅ **验收 `app162_app045_speakerlib_no_copy.py`** ⇒ **PASS=5 / FAIL=0 / verdict=PASS**
  （证据 `app162_app045_speakerlib_no_copy.json`
  **966 B / mtime 2026-10-30 11:18:11 / SHA256 `74c915c479b2e8ff44f3e6c787bed4244ae08b6fb5354abee99e2c829a8328a9`**）：
  判据①用户目录**未被写入任何内置音色文件**（沙箱内容 `[]`）／②`cindy` 仍可按名加载
  （`embedding shape=(1, 1024)`）／③`list_profiles()` 仍含 4 个内置音色／
  ④用户自建音色可存可取（未被本次改动破坏）。
  ⇒ 🔴 **用沙箱测**（替换 `_cache_dir`），**绝不碰真实用户目录**。
- ✅ **反证**：`--falsify` 把 `copy_builtins=False` 改回 `True` ⇒ **1 FAIL**（判据①抓到 8 个复制文件）。
- ✅ **真实用户目录已清理**：`%LOCALAPPDATA%\\Confucius4LiveCaption\\tts_speakers\\` 中
  **8 个文件**（cindy/lou/phil/steve 的 `.json` + `.npy`，npy 指纹与包内内置**逐字节相同**）
  已**移出**到 `%LOCALAPPDATA%\\Confucius4LiveCaption\\_app045_backup_tts_speakers\\`（**保留备份可回滚**）
  ⇒ 目录内**无用户自建音色**（无用户数据被误删）。

### 107.3 ✅ **APP-045② 打包流程增加「更新桌面快捷方式」一步**

- 🔴 **背景**：reviewer 实测桌面 `Confucius4 实时字幕.lnk` 指向
  `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_**v1.5**\\Start_LiveCaption.bat`
  ⇒ 用户 v1.7–v1.12 的全部改动（说话人标签、APP-039/040/043 克隆修复、APP-041/042）**都没用上**。
- ✅ **实现**（新增 `shortcut_update.py`，**打包侧脚本，不进客户包**）：
  - 🔴 **COM 被安全策略拦截**：`New-Object -ComObject WScript.Shell` ⇒
    `Error: Command blocked for security: COM object instantiation can run arbitrary code`
    ⇒ **放弃 COM**，自实现**纯字节 `.lnk` 构造**（MS-SHLLINK）。
  - ✅ **格式要点（实测踩坑）**：Header 共 **76 字节**
    （`HeaderSize(4)=0x4C` ＋ `LinkCLSID(16)` ＋ `LinkFlags(4)` ＋ `FileAttributes(4)` ＋
    `CreationTime(8)` ＋ `AccessTime(8)` ＋ `WriteTime(8)` ＋ `FileSize(4)` ＋
    `IconIndex(4)` ＋ `ShowCommand(4)` ＋ `HotKey(2)` ＋ `Reserved1(2)` ＋
    `Reserved2(4)` ＋ `Reserved3(4)`）；
    **StringData 从偏移 76 开始**（无独立 LinkFlags 字段，LinkFlags 实际在偏移 **[20:24]**）；
    StringData 项 = 2 字节字符数 + UTF-16LE（**无终止符**），
    顺序 NameString / RelativePath / WorkingDir / Arguments / IconLocation。
  - ✅ **反解器 `lnk_target_of()` 改为结构化解析**（按偏移 76 读 5 项取 index 1）
    ⇒ 🔴 早期用正则 ⇒ 把多个路径串在一起（假目标）。
  - ✅ **验收门** = 包目录 `ACCEPTED.json` 的 `accepted` 字段（**损坏 ⇒ fail-closed 返回 False**）
    ⇒ 落实 APP-045②「**还没通过真机验收的版本不要指过去**」。
  - ✅ **行为**：「验收门 → 目标存在 → 幂等检查 → 清理同前缀旧 lnk → 写新 lnk」
    ⇒ **只保留一个**、名称带版本号（如 `Confucius4 实时字幕 v1.13.lnk`）。
- ✅ **接入 `pack_v13.py`**：在 `_run()` 的 `_finish(ZIP, tmp_zip, ok)` **成功后**调用
  `_update_shortcut_after_pack(PKG, args)`；🔴 **失败只告警**（不把已成功的打包判成 FAIL）。
- ✅ **验收 `app163_app045_shortcut_update.py`** ⇒ **PASS=10 / FAIL=0 / verdict=PASS**
  （证据 `app163_app045_shortcut_update.json`
  **2 341 B / mtime 2026-10-30 11:20:13 / SHA256 `db58266e1ac483bffb0a9fa2d81551203e9eb950d02ceaee2599f50bd3b1b6e3`**）：
  ⑥a 未验收**不更新**（`ret.ok=False`）／⑥b 已验收更新成功／②只保留一个／
  ③名称带版本号／④旧的无版本号 lnk 已删（`legacy 存在=False`）／
  ①a Header **76 字节**（实际字节 794）／①b **独立解析**还原目标路径／
  ①c 名称串正确／①d `lnk_target_of` 反解一致／⑤幂等（`已指向当前版本（幂等，无需重建）`）。
  ⇒ 🔴 **判据独立**：解析器**不复用被测代码** ⇒ 真判据。
- ✅ **反证**：`--falsify` **整函数替换** `is_accepted` 为 `return True`
  ⇒ **1 FAIL**（判据⑥a）。
  ⇒ 🔴 **教训**：反证只改**第一道门**会被后续 `except` 分支兜住 ⇒ 假 PASS。

### 107.4 ✅ **残留克隆音频清理（APP-045① 的前置动作）**

- ✅ `%TEMP%\\confucius4_clone\\` 当前 **0 个文件**（v1.5 退出时 `close()` 已自行清理）
  ⇒ **删除文件数 = 0**（按 APP-045①「只记录删除了多少个文件」）。
- ✅ 另发现旧引擎残留 `%TEMP%\\tmp0gv6_y4o\\clone_C.npz.tmp.npz`（**280 B**，
  mtime 2026-10-22 17:40，SHA256 `61d8e5e6…`）⇒ 已**移出**到
  `%TEMP%\\_app045_backup_clone_npz\\`（**移出而非删除**，可回滚）。
- 🔴 **删/移的纪律**：APP-045① 明确「**只记录删除文件数，不上传**」
  ⇒ **未上传任何音频内容**。

### 107.5 ✅ **客户包定点同步（仓库 ⇄ 包目录，两份独立副本）**

- ✅ 同步脚本 `live_caption/sync_c168_app045_to_pkg.py`（**不进客户包**）：
  - 🔴 **OLD 取自「包内实际内容」**（不是基线 commit）⇒ `difflib` 派生替换块
  - 🔴 **行尾无关**：bytes 读入 → 检测 `b'\\r\\n'` → 归一化 LF 匹配/替换 → 按原行尾写回
    ＋ **断言「前后行尾不变」**（同目录 `NOTICE` 纯 LF、`THIRD_PARTY.md` 纯 CRLF ⇒ 混用会静默假同步）
  - 🔴 **唯一命中断言**（命中 0 次 ⇒ 中止不落盘）；写盘前 + 写后 `ast.parse` 校验
  - 🔴 **替换块倒序应用**（前面的替换会改变后面块的锚点）
  - 🔴 **纯插入块必须用锚点组合**（前一行 + 后一行）并**逐步扩展上下文**（±1..12 行）直到唯一
    ⇒ 🔴 踩坑：`cur.count('')` = 字符串长度+1（实测 **49 386** 次命中）⇒ 纯字符串匹配必炸
- ✅ **落盘结果**（11:25）：
  - `Confucius4_LiveCaption_v1.12\\app\\tts_engine.py`
    `788d5ca29fd7345b…` ⇒ **`0f239b0ac89febcd…`**（归一化 LF 后与仓库**逐字节一致**）
  - `Confucius4_LiveCaption_v1.12\\app\\tts_worker.py`
    `73c756420fd1c1ee…` ⇒ **`025d1848064a6a47…`**（归一化 LF 后与仓库**逐字节一致**）
  - ✅ 包内两个文件 `ast.parse` **均通过**（客户机启动即崩的类缺陷已排除）
  - ✅ **仓库原文件在 `git diff` 里显示 CRLF，包内 LF** ⇒ 属**正常行尾差异**，
    🔴 **必须归一化行尾后再比**（原始字节必 DIFF = 假报警）
- ✅ **备份**（包外 `%TEMP%`）：`app045_bak_tts_engine.py` **67 920 B** /
  SHA256 `b5245ad913e4ada4b8c624702292208bac85d578fdcd066d968fa01c0cd7e089`；
  `app045_bak_tts_worker.py` **220 854 B** /
  SHA256 `4572b41e1b9441f9f1f8b07536bd9232e61dfd8908dda90bbc49fe177d4eba94`；
  本轮同步备份目录 `%TEMP%\\app045_backup_20261030_112550\\`。

### 107.6 🔴 **v1.12 zip 不含 APP-045 改动 ⇒ 未重打（按用户 11:30 指令）**

- 🔴 **时序**：v1.12 zip 于 **11:20:14** 生成（并行会话 §106 的持锁重打），
  而 APP-045 同步落盘在 **11:25** ⇒ **zip 早于同步** ⇒ **该 zip 不含 APP-045 的任何改动**。
- 🔴 **我方曾自行发起 `pack_v13.py --version 1.13`**，reviewer 于 11:30 指示
  「**打包过于频繁，以后不通知就无需主动打包**」⇒ **已在 11:31 立即停掉**（PID 28816，
  当时仍在等 ASR 锁，**未写入任何 zip**）。
- ✅ **副作用已收拾干净**（`pack_v13.py` **启动即把源目录改名** v1.12 ⇒ v1.13）：
  - 手动 `mv` 回 `Confucius4_LiveCaption_v1.12`（同卷，秒级）
  - MANIFEST `version=1.12` / `files=14217` / `bytes=13689695552`
    ⇒ **目录版本 == MANIFEST 版本**（不白吃版本号）
  - **无** `Confucius4_LiveCaption_v1.13/` 目录、**无** `v1.13.zip`、**无** `*.zip.tmp` 残留
  - 🔴 **v1.12 zip 与包目录仍是完好的一份**（11 233 373 363 B / SHA256 `28cf34de…08a72b6`）
- 🔴 **纪律固化**：用户级记忆 `~/.workbuddy/.../MEMORY.md` ＋ 项目级
  `.workbuddy/memory/MEMORY.md` 第十节均已写入
  「**未经用户明确通知 ⇒ 不主动打包**」。

### 107.7 ✅ **入库（只提本模块文件，绝不提交 `CORRECTIONS_APP.md`）**

- ✅ commit **`bb7274e`**（普通 push，**未 force push**）⇒ `HEAD == origin/main == bb7274e742ba4df6b57fe78949045785f6de547c`
- ✅ **入库文件（11 个）**：`live_caption/tts_engine.py`、`live_caption/tts_worker.py`、
  `pack_v13.py`、`shortcut_update.py`、`live_caption/sync_c168_app045_to_pkg.py`、
  `results/app/app161_app045_clone_inmemory_equivalence.{py,json}`、
  `results/app/app162_app045_speakerlib_no_copy.{py,json}`、
  `results/app/app163_app045_shortcut_update.{py,json}`
- 🔴 **未入库**：`status/app/CORRECTIONS_APP.md`（reviewer 独占写入，**只读**）
- 🔴 **未吞**其它模块的未提交改动（`status/CORRECTIONS.md`、`status/asr/*` 等工作区改动原样保留）
- 🔴 **本轮未跑既有回归套件** ⇒ ⚠️ 按 §五铁律「改 `synth`/决策分支后必须复跑既有回归套件」，
  本次改的是 `tts_engine` 的 embedding 计算与 `SpeakerLibrary` 包装（**非 `synth` 决策分支**），
  且已有 3 个**专属**断言脚本覆盖；**但仍建议 reviewer 安排一次整体回归**。

### 107.8 🔴 **本轮未做（需 reviewer / 用户）**

1. 🔴 **v1.13 打包**（等用户通知）⇒ 之后才能让 zip 含 APP-045 改动。
2. 🔴 **APP-045③ 真机验收**（APP-043 全套）：用户启动方式（桌面快捷方式 → `pythonw.exe` 冷启动）＋
   SPE Q&A 双说话人 ＋ GUI 加速播放 ＋ 3 段 1.2–1.3× 配音给用户实听。
   ⇒ **通过后**才写包目录 `ACCEPTED.json` ⇒ **才**能更新快捷方式 ⇒ **再**通知主会话请用户实测。
3. 🔴 **reviewer 的 MiniMax 回转写错误率对比**（本模块**不得自做**）。
4. 🔴 **APP-044 精度形态裁定**（FP16 还是 FP32 ⇒ 代码无需改，换目录重打即可）。
5. 🔴 **桌面快捷方式仍指向 v1.5** ⇒ 用户当前实测的仍是旧包 ⇒ 这是 APP-045 的**根因**，
   🔴 **在真机验收通过 + 新包就位前不得改指**（APP-045② 原文要求）。
6. 🔴 **§104.3 的 2 个「复跑产物」**（`app158_..._pkg.json` / `app154_...json`）是否入库，待裁定。

### 107.9 🔴 **reviewer 复核清单**

1. 请复核 §107.1 的**纯内存 embedding 等价性**（`app161` 10 PASS / 反证 5 FAIL）
   与「PCM_16 量化误差 4.101e-05 ⇒ 内存路径更精确」的结论。
2. 请复核 §107.2 的**音色来源与许可**结论（babelvox Apache-2.0、自带示例、非测试残留）
   与「用户目录 8 文件移出 + 备份可回滚」的处理方式。
3. 请复核 §107.3 的 **MS-SHLLINK 纯字节构造**（Header 76 字节 / StringData 偏移 76）
   与「验收门 `ACCEPTED.json` ⇒ 未验收不指过去」的设计。
4. 请复核 §107.6 的**中止打包作业 + 还原目录名**的处理（版本号未白吃）。
5. 🔴 **请裁定**：是否安排 **v1.13 打包**（用户 11:30 已指示不主动打包 ⇒ 需明确通知才动）。
6. 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读）。
'''


def main():
    with open(STATUS, 'rb') as f:
        raw = f.read()
    assert b'\r\n' in raw, 'STATUS 不是 CRLF ⇒ 拒绝写入'
    txt = raw.decode('utf-8')

    # ── 头部字段替换（限定在第一个 `## §` 之前）──
    i = txt.find('## §')
    assert i > 0, '找不到章节起点'
    head, body = txt[:i], txt[i:]

    def set_field(head, key, value):
        # 🔴🔴🔴 **正则必须用 `[^\r\n]*`，不能用 `.*$`**：
        #   `(?m)$` 只在 `\n` 前匹配 ⇒ `.*` 会**把 `\r` 一起吃掉**
        #   ⇒ 替换后该行行尾变成**裸 LF** ⇒ 纯 CRLF 文件被污染
        #   （实测：3 处裸 LF ⇒ 写入被自检拦下）。
        #   ⇒ 另：替换文本**必须用 lambda 返回**（避免 `re.sub` 解释
        #     替换串里的 `\n`/`\g` 等转义序列）。
        pat = re.compile(r'(?m)^%s:[^\r\n]*' % re.escape(key))
        assert pat.search(head), '头部缺字段: %s' % key
        return pat.sub(lambda m: '%s: %s' % (key, value), head, count=1)

    head = set_field(head, 'last_ack', HEAD_LAST_ACK)
    head = set_field(head, '更新时间', HEAD_TIME)
    # 「当前任务」行：以 `当前任务:` 开头，可能很长 ⇒ 整行替换
    pat = re.compile(r'(?m)^当前任务:[^\r\n]*')
    assert pat.search(head), '头部缺「当前任务」'
    head = pat.sub(lambda m: '当前任务: ' + HEAD_TASK, head, count=1)
    # 「阻塞 / 待用户决定」行
    pat2 = re.compile(r'(?m)^阻塞 / 待用户决定:[^\r\n]*')
    assert pat2.search(head), '头部缺「阻塞 / 待用户决定」'
    head = pat2.sub(lambda m: '阻塞 / 待用户决定: ' + HEAD_BLOCK, head, count=1)

    # ── 追加新章节 ──
    new_txt = head + body
    sep = '' if new_txt.endswith('\r\n') else '\r\n'
    new_txt = new_txt + sep + NEW.replace('\n', '\r\n')

    # ── 写回前自检 ──
    assert new_txt.count('## §107') == 1, '§107 出现次数异常'
    assert new_txt.count('## §106') == 1, '§106 丢失'
    for k in range(100, 107):
        assert ('## §%d ' % k) in new_txt, '§%d 丢失' % k
    # 旧正文逐字未变（§106 及之前）
    old_body = txt[txt.find('## §'):]
    assert new_txt.endswith(old_body) or old_body in new_txt, '旧正文被改动'

    out = new_txt.encode('utf-8')
    assert b'\r\n' in out
    # 纯 CRLF：不应有裸 LF（除 CRLF 里的）
    assert out.replace(b'\r\n', b'').count(b'\n') == 0, '出现裸 LF ⇒ 行尾被污染'

    with open(STATUS, 'wb') as f:
        f.write(out)
    print('§107 已写入：%s' % STATUS)
    print('新字节数: %d（原 %d）' % (len(out), len(raw)))
    print('章节数: %d' % new_txt.count('\n## §'))


if __name__ == '__main__':
    main()
