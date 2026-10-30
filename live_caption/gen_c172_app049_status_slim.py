#!/usr/bin/env python
"""🔴 APP-049 第二步：生成**精简版** `status/app/STATUS_APP.md`。

## 结构（APP-049 原文固定要求）

- 头部（≤ 15 行）：last_ack / 当前任务 / 阻塞-待用户决定 / 最近一次更新时间
  ＋ **「已压缩：原文见 archive/…」** 一行。
- 「当前有效结论」表：交付配置 + 关键数字（**每个数字注明来源文件**）；
  **被推翻的旧结论不列**。
- 「未完成纠偏」清单：编号 + 一句话 + 下一步。
- 「最近章节」：**最近 3 节**，每节 **≤ 60 行**。

## 🔴 自指大小一致性（ASR-036 踩过的坑）

文内要写「本文 N B / M 行」⇒ 若用不动点迭代但**占位符替换后才 break**，
写进去的是**替换前**的长度（ASR 实测偏差 34 B）。
⇒ 本脚本每轮都从**带占位符的模板**重新计算长度，直到候选文本长度不再变化。

## 🔴 行尾

新文件用 **LF**（`newline='\\n'`）自写 ⇒ 不受旧文件 CRLF 影响；
旧文件的行尾**原样留在归档里**（bytes 级复制）。

## 跑法

    .venv\\Scripts\\python.exe live_caption\\gen_c172_app049_status_slim.py
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

STAMP = '2026-10-30 18:55'

HEADER = """# STATUS_APP

last_ack: APP-049
更新时间: {STAMP}
当前任务: **§111 ✅ APP-049 压缩完成（STATUS 1 437 968 B / 18 977 行 → 精简版 ≤ 40 KB / ≤ 300 行；原文原样归档）**；本轮同时完成 **APP-046 巡检规则**、**APP-047 FP16 定案**、**APP-048 GUI 三分区状态条**（代码 + 客户包同步 + 64 PASS / 0 FAIL + 三张真图）⇒ **APP-046…049 全部结清**，但 **APP-043 真机验收 / APP-045 ③ / v1.13 打包** 仍未做（按用户 11:30 指令「不通知不打包」⇒ 未发起打包）。
阻塞 / 待用户决定: ① 🔴 **v1.13 未打包**（用户 11:30 指令：未经通知不主动打包；且 v1.12 zip 生成于 11:20，**不含** APP-045/047/048 任何改动）⇒ 等用户通知；② 🔴 **APP-043 真机验收未做**（用户启动方式 `pythonw.exe` 冷启动 / SPE Q&A 双说话人 / GUI 加速播放 / 3 段 1.2–1.3× 配音给用户实听）⇒ 通过后才写 `ACCEPTED.json`、才更新桌面快捷方式；③ 🔴 **桌面快捷方式仍指向 v1.5**（用户当前实测的仍是旧包 ⇒ APP-045 的根因）；④ 🔴 **APP-048 的「和 v1.13 一起交付」尚未满足**（布局与截图已完成，等 v1.13）；⑤ 🔴 **reviewer 的 MiniMax 回转写错误率对比未做**（本模块不得自做）；⑥ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读，reviewer 独占写入）。
已压缩: 原文见 `status/archive/STATUS_APP_upto_20261030.md`（1 437 968 B，只读归档）；纠偏归档见 `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`（全量原文备份 `CORRECTIONS_APP_full_before_compress_20261030.md`）。**本文件 @@SIZE@@ B / @@LINES@@ 行**（原 1 437 968 B / 18 977 行 ⇒ **−@@PCT@@%**）。


## 最近更新
- 2026-10-30 18:55 **§111 APP-049 压缩完成** ⇒ `STATUS_APP.md` **1 437 968 B / 18 977 行 → 本文件 ≤ 40 KB / ≤ 300 行**（**−99.0%**）；原文件**原样**（bytes 级，SHA256 一致）归档 `status/archive/STATUS_APP_upto_20261030.md`；`CORRECTIONS_APP.md` **零改动**（只生成只读归档副本：索引表 49 条 + 全部 49 条全文）⇒ 独立复核 `app166` **35 PASS / 0 FAIL**。
- 2026-10-30 16:52 **§110 APP-048 GUI 三分区状态条落地** ⇒ 新增 `live_caption/gui_status.py`（纯逻辑，不 import tkinter）+ `live_caption_app.py` +566/−30 行；**客户包 v1.12 定点同步完成**（`live_caption_app.py` 330 336 B / `gui_status.py` 8 320 B，归一化行尾后逐字节一致）⇒ ✅ `app165` **64 PASS / 0 FAIL**；三张截图落 `shared/app_gui_layout/`。
- 2026-10-30 16:00 **§109 APP-047 说话人 IR 精度定案 FP16** ⇒ `asr_spk/` 收敛为 **3 个文件**；`app164` **30 PASS / 0 FAIL**；按 ASR 新清单**重新同步**（不再做字面量替换）。
- 2026-10-30 15:40 **§108 APP-046 巡检规则补充** ⇒ `last_ack` 追平后若仍有未完成项 ⇒ **直接继续做，不空转**；需计时的**等锁不抢**；只在「全部完成」或「卡在需用户决定」时停。


## 当前有效结论

> 🔴 **每个数字都注明来源产物**；**被推翻的旧结论不在此表**（见归档）。

### 交付配置

| 项 | 结论 | 来源 |
|---|---|---|
| 客户包目录 | `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v1.12`（**当前唯一**） | `Confucius4_LiveCaption_v1.12/MANIFEST.json` → `version` |
| 客户包 zip | v1.12（11:20 生成 / 11 233 373 363 B / SHA256 `28cf34de…08a72b6`）⇒ **不含** APP-045/047/048 | `status/archive/STATUS_APP_upto_20261030.md` → §106 / §107.6 |
| 默认翻译模型 | Hy-MT2 INT8-CW，设备 GPU.0（Intel 集显） | `status/app/CORRECTIONS_APP.md` → APP-002（用户决定）；设备实测见 `app048_layout_1920x1080.png` |
| ASR 模型 | Qwen3-ASR 路线，精度 INT8，设备 GPU.0 | `app048_layout_1920x1080.png`（ASR 区实测「Intel GPU（集显）· INT8」） |
| 语音输出设备 | TTS 走 NPU（F16 / INT8 视配置） | `app048_layout_1920x1080.png`（语音区实测「Intel NPU · F16」） |
| 说话人 IR 精度 | **FP16**（ASR 聚类结果与 FP32 **0 段不一致**） | `asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（APP-047） |
| 说话人资产（随包） | **恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`） | `app164_app047_spk_resync_evidence.json` → `pass_=30` |
| 音色策略 | **按句绑定原说话人**（APP-039/040 核心已实施） | `status/archive/STATUS_APP_upto_20261030.md` → §99 / §100 |
| GUI 状态布局 | **三分区状态条**（ASR / 翻译 / 语音输出），顶部只留全局 | `app165_app048_gui_layout_evidence.json` → `verdict=PASS` |
| 桌面快捷方式 | **仍指向 v1.5**（未过真机验收 ⇒ 按 APP-045② 不得改指） | `status/archive/STATUS_APP_upto_20261030.md` → §107.8 ⑤ |

### 关键数字

| 指标 | 值 | 来源产物 / 字段 |
|---|---|---|
| GUI 三分区布局验收 | **64 PASS / 0 FAIL** | `results/app/app165_app048_gui_layout_evidence.json` → `n_pass` / `n_fail` |
| 失败态 vs 正常态截图像素差 | **9 492 px**（证明不是同一张图） | `app165_app048_gui_layout_evidence.json` → `diff_pixels_normal_vs_failed` |
| 失败态截图 error 红色像素 | **767 px**（整行变色确实生效） | `app165_app048_gui_layout_evidence.json` → `error_red_pixels_in_failed` |
| 说话人资产同步验收 | **30 PASS / 0 FAIL** | `results/app/app164_app047_spk_resync_evidence.json` → `pass_` / `fail` |
| 克隆纯内存等价性 | **10 PASS / 0 FAIL**；mel `max|Δ|=0.000e+00`；入参逐位相同 | `results/app/app161_app045_clone_inmemory_equivalence.json` → `n_pass` / `n_fail` |
| 克隆 vs 旧落盘路径差 | `max|Δ|=4.101e-05` ⇒ **PCM_16 量化误差，非回归**（内存路径更精确） | `results/app/app161_app045_clone_inmemory_equivalence.json` → 判据②b |
| 内置音色不落用户目录 | **5 PASS / 0 FAIL**；用户目录 8 文件已**移出**（备份可回滚） | `results/app/app162_app045_speakerlib_no_copy.json` → `n_pass` / `n_fail` |
| 桌面快捷方式构造 | **10 PASS / 0 FAIL**；`.lnk` Header **76 字节** | `results/app/app163_app045_shortcut_update.json` → `n_pass` / `n_fail` |
| 客户包 v1.12 规模 | **14 218 文件 / 11 233 373 363 B**；`testzip()` OK；zip ⇄ 包目录逐字节一致 | `status/archive/STATUS_APP_upto_20261030.md` → §106 |
| 包目录代码同步（APP-048） | `live_caption_app.py` **330 336 B** / `gui_status.py` **8 320 B**，归一化行尾后**逐字节一致** | `live_caption/sync_c170_app048_to_pkg.py`（21 个替换块，唯一命中 + `ast.parse` 校验） |

### 已撤回的旧结论（**不作为结论**，仅备查）

- §97 的「APP-039/040 核心已实施」在 §98 补交入库后**才**成立 ⇒ 见 §98。
- §103.4 的「4 产物已入库」当轮**不准确**（只入了脚本，证据由 §104 补交）⇒ 见 §105.4。
- §104.6 的「宿主后台任务有 16 分钟上限」实为**守候器自身退出**，非宿主强杀 ⇒ 见 §105.2。


## 未完成纠偏

| 编号 | 一句话 | 下一步 |
|---|---|---|
| APP-043 | ASR 说话人接口已交付，APP-039/040 克隆资产可取（真机验收全套） | 🔴 **等真机验收**：用户启动方式（桌面快捷方式 → `pythonw.exe` 冷启动）＋ SPE Q&A 双说话人 ＋ GUI 加速播放 ＋ 3 段 1.2–1.3× 配音给用户实听 ⇒ 通过后写包目录 `ACCEPTED.json` |
| APP-045 | 桌面快捷方式仍指向 v1.5 ⇒ 用户实测的全是旧包 | 🔴 **③ 真机验收未做 ⇒ 不得改指**；**② 打包后自动更新快捷方式**已实现（`shortcut_update.py`）⇒ 等 v1.13 就位 |
| APP-048 | GUI 状态信息按 ASR / 翻译 / 语音输出分区 | ✅ **代码 + 客户包同步 + 64 PASS / 0 FAIL + 三张真图已完成**；🔴 **「排在 APP-043 真机验收之后、和 v1.13 一起交付」尚未满足** ⇒ **待 reviewer / 用户定排期** |
| APP-049 | 压缩 STATUS / CORRECTIONS | ✅ 本节已完成（§111）；🔴 需 reviewer 确认归档内容与索引表无误 |


## 最近章节

> 只保留最近 3 节（§109/§110/§111）；更早的章节见 `status/archive/STATUS_APP_upto_20261030.md`。

{RECENT}
"""

SEC_109 = """### §109 ✅ **APP-047 说话人 IR 精度定案 FP16 ⇒ `asr_spk/` 收敛为 3 文件并按新清单重新同步** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- 🔴 **依据（reviewer 转达 ASR）**：`asr067_fp16_vs_fp32_cluster.json` → `n_diff_segments=0`（FP16 与 FP32 聚类结果 **0 段不一致**），嵌入 RTF 增量在固定 T 范围 [100, 2048] 后为 **0.033**（≤ 0.05 门槛）⇒ **FP16 即交付形态**，客户包用 `models/spk` 下的 FP16 IR，**不需要 FP32**。
- 🔴 **「不要再做字面量替换」**（ASR-033 收尾后清单已变）⇒ 本轮**按新清单重新同步** `asr_spk/`，**未**做字面量替换。
- ✅ **结果**：`asr_spk/` 收敛为**恰好 3 个文件**（`asr052_speaker_tracker_api.py` / `asr052_spk_runtime.py` / `asr_thread_defaults.py`）；新增降级原因 `embed_shape_out_of_range`（**不截断**，超界抛 ValueError ⇒ API 层降级）与 `embed_error` 透传。
- ✅ **验收 `app164_app047_spk_resync_test.py`** ⇒ **PASS=30 / FAIL=0 / verdict=PASS**（证据 `app164_app047_spk_resync_evidence.json` **3 937 B / mtime 2026-10-30 15:50:03 / SHA256 `fd5b6f26cd4805d9…`**）。
- 🔴 **未做**：v1.13 何时重打**按用户指示**（11:30 先不要重打）；真机验收（APP-043）可先做。"""

SEC_110 = """### §110 ✅ **APP-048 GUI 三分区状态条：代码 + 客户包定点同步 + 64 PASS / 0 FAIL + 三张真图** ｜ **本条已完成（布局部分）** ｜ **本条需等 reviewer 复核**（交付排期未满足）

- ✅ **新增 `live_caption/gui_status.py`**（**8 320 B / SHA256 `c78813b5bdb6e99e…`**）：**纯逻辑层，不 import tkinter** ⇒ 可离线验收。含 `SectionStatus`（`set` / `ordered` / `level` / `render` / `snapshot`）、`estimate_px`（CJK 按 ASCII **2 倍**估宽）、`measure_text`、`build_sections`。
- ✅ **`live_caption/live_caption_app.py`**（**330 336 B / SHA256 `1fea0446767194fc…`**）：**+566 / −30 行**（5 600 → 6 179 行）。顶部**只保留全局**（会话计时 / 总状态灯 / 采集电平·音频时长·来源·积压）；**ASR / 翻译 / 语音输出三区各一条紧凑状态条**，字段按 APP-048 清单齐备；**错误行变色**、**tooltip** 显示完整原因与日志路径、**≤ 1 Hz 节流刷新**、**只在文本/级别真变化时才 `configure()`**（避免频繁重排）。
- ✅ **客户包 v1.12 定点同步完成**：`sync_c170_app048_to_pkg.py` 派生 **21 个替换块**（包内 5 630 行 → 仓库 6 179 行），每块**唯一命中断言** + **位置复核** + 写盘前 `ast.parse` 校验 ⇒ 写入后归一化行尾与仓库**逐字节一致**（`live_caption_app.py` SHA256 `1fea0446767194fc…` / `gui_status.py` `c78813b5bdb6e99e…`，mtime 2026-10-30 16:46:42）。
- 🔴🔴🔴 **抓出「截图判据恒真」并修掉**：`ImageGrab.grab()` 在本机**抓到的整屏是全黑**（`extrema=(0,126)`、采样点全 `(0,0,0)`）⇒ 之前三张 PNG **全是黑图**，而 60 个判据全在**逻辑层** ⇒ **静默假通过**。
  - ✅ 改用 **Win32 `PrintWindow`**（`results/app/win_capture.py`，**4 007 B**）—— 让窗口**自绘进内存 DC**，不读屏幕像素 ⇒ 不受黑屏 / 遮挡 / 屏幕尺寸限制。
  - ✅ 新增判据 **C18c**（两图**像素级不同**，`diff_px=9 492`）＋ **C18d**（失败态含 error 红像素 `767`）＋ **C16b/C16c**（截图前复位失败态、清空顶部残留错误行）⇒ **判据不再恒真**。
- ✅ **验收 `app165_app048_gui_layout.py`** ⇒ **PASS=64 / FAIL=0 / verdict=PASS**（证据 `app165_app048_gui_layout_evidence.json` **4 476 B / mtime 2026-10-30 16:52:29 / SHA256 `1017e3c842e4994f…`**）。
- ✅ **截图已落 `C:\\Users\\Trekker-PTL\\shared\\app_gui_layout\\`**：`app048_layout_1920x1080.png`（87 830 B / SHA256 `ae871cee4dc8026d…`）、`app048_layout_1280x720.png`（82 441 B / `caad45638f89ede1…`）、`app048_layout_mt_failed.png`（90 237 B / `3ed1cbbdf27da94a…`）⇒ 已人眼复核：三区状态条可见、顶部不拥挤、**失败态翻译区红字显示「失败」且总状态灯「✖ 有模块异常」**。
- 🔴 **未满足项**：APP-048 原文要求「**排在 APP-043 真机验收之后，和 v1.13 一起交付**」⇒ **尚未满足**（APP-043 真机验收未做；v1.13 未打包）⇒ **本条需等 reviewer / 用户**。
- 🔴 **未做**：控件行为与默认值**未改**（`var_tts_on` 默认开 / `var_show_spk` 默认开 / 三个组合下拉绑定未动）⇒ APP-041 启动逻辑保持不变。"""

SEC_111 = """### §111 ✅ **APP-049 压缩：STATUS 1 437 968 B / 18 977 行 → ≤ 40 KB / ≤ 300 行，原文原样归档** ｜ **本条已完成** ｜ **本条需等 reviewer 复核**

- ✅ **① STATUS 拆分**：
  - 原 `status/app/STATUS_APP.md` **原样**（**bytes 级**复制，SHA256 `8fbdd7fe2b6b4547…` **一致**）归档到 **`status/archive/STATUS_APP_upto_20261030.md`**（**1 437 968 B**）⇒ **只读归档，不删内容**。
  - 新建精简版（**本文件**）：头部 ≤ 15 行（含「已压缩：原文见 archive/…」）＋「当前有效结论」表（**每个数字注明来源文件**）＋「未完成纠偏」清单＋「最近章节」（**§109/§110/§111**，每节 ≤ 60 行）。
- ✅ **② CORRECTIONS 压缩（🔴 只读，不改原文件）**：
  - 🔴 **本模块纪律优先**：`status/app/CORRECTIONS_APP.md` 是 **reviewer 独占写入文件** ⇒ **全程零修改、零暂存**（脚本内 `assert` 断言其字节数不变；独立复核判据 B1 以 SHA256 `bb07c52697ecb5aa…` 复核）。
  - 只**生成只读归档副本**：`status/archive/CORRECTIONS_APP_full_before_compress_20261030.md`（**118 903 B**，全量原文备份，SHA256 `bb07c52697ecb5aa…`）＋ `status/archive/CORRECTIONS_APP_closed_upto_20261030.md`（**@@CORRCLOSED@@ B**：**索引表 49 条**（编号/一句话/状态）＋ **全部 49 条全文**（按原文顺序）＋ 最近 5 条指针）。
  - ✅ **编号与标题格式不变**（`## <前缀>-<编号> [级别] 日期 — 标题`）⇒ reviewer 的推送工具仍可往原文件末尾追加。
- ✅ **③ 以后的写作规则已固化**：每个新章节 **≤ 60 行**；长日志 / 逐条明细 / 大表格写 `status/notes/` 或 `results` 目录；**STATUS 超 40 KB 时自己把旧章节移到归档**。
- ✅ **④ 独立复核** `results/app/app166_app049_compress_verify.py` ⇒ **PASS=35 / FAIL=0 / verdict=PASS**（限额 / 自指大小 / 四段结构 / 每行来源文件名 / 归档 107 章节齐全 / CORRECTIONS 49 条编号集合与标题逐字一致 / 幂等闸门仍能取到最大编号 049 / 原 CORRECTIONS 零改动）。
- 🔴 **本条需等 reviewer 复核**：索引表 49 条的状态标注（已完成 / 已关闭 / 进行中）是否与 reviewer 口径一致。"""


def main():
    body = HEADER.replace('{STAMP}', STAMP).replace(
        '{RECENT}', SEC_109 + '\n\n' + SEC_110 + '\n\n' + SEC_111)

    # ── 不动点迭代：自指大小必须与实际一致 ──
    #   🔴 每轮都从「带占位符的模板」重新计算（ASR-036 踩过：
    #     占位符被替换后提前 break ⇒ 写的是替换前的长度，偏差 34 B）
    ORIG = 1437968

    def render(size_txt, line_txt, pct_txt):
        t = body.replace('@@SIZE@@', size_txt)
        t = t.replace('@@LINES@@', line_txt)
        t = t.replace('@@PCT@@', pct_txt)
        # 🔴 归档 CORRECTIONS 的**实测**大小（不能写死 ⇒ 会被下一轮改动带偏）
        corr_closed = os.path.join(REPO, 'status', 'archive',
                                   'CORRECTIONS_APP_closed_upto_20261030.md')
        cb = os.path.getsize(corr_closed) if os.path.exists(corr_closed) else 0
        t = t.replace('@@CORRCLOSED@@', str(cb))
        return t

    text = ''
    for _ in range(30):
        cur = len(text.encode('utf-8'))
        cur_lines = len(text.split('\n')) if text else len(
            body.replace('@@SIZE@@', '0').replace('@@LINES@@', '0')
            .replace('@@PCT@@', '0').split('\n'))
        pct = '%.1f' % (100.0 * (ORIG - cur) / ORIG)
        cand = render(str(cur), str(cur_lines), pct)
        if cand == text:
            break
        text = cand
    # 🔴 收尾：从**带占位符的模板**再渲染一次（保证数字 == 最终真实值）
    size_final = len(text.encode('utf-8'))
    lines_final = len(text.split('\n'))
    pct = '%.1f' % (100.0 * (ORIG - size_final) / ORIG)
    text = render(str(size_final), str(lines_final), pct)

    # 🔴 写盘**前**断言
    assert size_final <= 40960, '超出 40 KB 限额：%d' % size_final
    assert lines_final <= 300, '超出 300 行限额：%d' % lines_final
    assert ('本文件 %d B / %d 行' % (size_final, lines_final)) in text, \
        '自指大小不一致'

    with open(STATUS, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)

    size = os.path.getsize(STATUS)
    nlines = len(open(STATUS, encoding='utf-8').read().split('\n'))
    print('写入 %s' % STATUS)
    print('  bytes = %d  (≤ 40 KB: %s)' % (size, 'OK' if size <= 40960 else 'FAIL'))
    print('  lines = %d  (≤ 300: %s)' % (nlines, 'OK' if nlines <= 300 else 'FAIL'))
    print('  mtime = %s' % time.strftime('%Y-%m-%d %H:%M:%S',
                                        time.localtime(os.path.getmtime(STATUS))))
    # 🔴 写盘**后**独立复核自指一致性
    real = open(STATUS, encoding='utf-8').read()
    assert ('本文件 %d B / %d 行' % (size, nlines)) in real, '写后自指不一致'
    assert size == size_final and nlines == lines_final, '写后尺寸不一致'
    print('✅ 全部限额与自指一致性检查通过（写盘前后双重断言）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
