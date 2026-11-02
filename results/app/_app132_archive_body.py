#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""把 §132 的**详细正文**归档到 `status/archive/`，正文处只留**索引 + 关键结论**。

🔴 **做法与 APP-052 ④ 一致**（仓库既有惯例）：
   「§109–§124 正文已原样归档到 `status/archive/…`（**逐字保留，内容一字未删**）」
   ⇒ **本节正文同样逐字归档**，正文处留一行指向 ＋ 一张**结论速查表**。

🔴 **不丢信息**：归档文件**逐字保留**；正文里的**速查表**保留全部关键数字
   （判据结果、实测值、待裁定项），细节指向归档。
"""
import os

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive')

SUMMARY = r'''### §132 🔄 **APP-063 ①D4 bug ＋ ②D2 四入口 ＋ ③D1 窗口 ＋ APP-064 锁纪律 ＋ APP-065 A 界面重排 ＋ B 改名** ｜ **本条已完成（代码层 ＋ 设备级）** ｜ **本条需等 reviewer 复核**（2026-11-03 00:05）

> 🔴 **本节正文已原样归档** ⇒ 见 `status/archive/STATUS_APP_sec132_upto_20261103.md`（**逐字保留，内容一字未删**）。

**结论速查（全部数字以归档正文为准）**

| 项 | 结论 |
|---|---|
| **APP-063 ① D4 bug** | ✅ 修好：enforce 命中后**重读 opt** ＋ enforce 内补 set_engine→set_device ⇒ **MT 不再被覆盖回 NPU**（探针 `mt.device=GPU.0`/`engine_key=gpu_int8cw`/落盘 `mt=GPU.0`）；**CLI** 同 NPU 也自动改 GPU.0 ＋ 日志。`app229` **38/0**（含 3 组反证） |
| **APP-063 ② D2 四入口** | ✅ 全补齐：GUI 启动/`_on_tts_toggled` 自动开旁路 ｜ CLI `follow_speaker` 自动开旁路 ｜ 取消勾选 ⇒ 音色切回「预设 A」＋提示 ｜ 会话进行中**真正拉起线程**（`ensure_started`，状态栏「已即时生效，无需重启会话」） |
| **APP-063 ③ D1 窗口** | ⛔ **App 侧已同源（5.0，未写第二份默认值）**，但 **ASR 内核 `asr052_spk_runtime` 仍写死 10 s**（`WIN_N=160000`/`N_FRAMES=589`/`FPS=58.9`）⇒ **跨模块错位**（`app230` 7 PASS/**5 FAIL**）⇒ 已发 `shared/NOTICE_app_to_asr_spk_window_5s_alignment.md` 给 ASR；**v2.3 建议暂缓发布** |
| **APP-064 锁纪律** | ✅ 设备级作业**先拿 `MACHINE_LOCK` 再跑** ＋ **先探安静窗口**（75 s 后取得 45 s 安静；用户 v2.1 GUI CPU 增量实测 0 s/6 s）；`app223 --run` 指向**本轮影子包**（硬链接自 v2.2 ＋ 同步本轮 2 个改动文件）⇒ **测的是本轮代码** |
| **APP-065 A 界面重排** | ✅ **5 组竖排 GroupBox**（①音频输入 ②语音识别 ③翻译 ④语音输出 ⑤高级）＋ 组内统一网格（**标签列右边缘 4 组全 56 px @100 % / 76 px @150 %**、**控件列全 233 px**、行高一致）＋ **4 张截图**（100 %/150 % × 启动后/配音开启后，`results/app/app065a_shots/`）＋ **控件→所在组清单**（`app231_app065a_control_group_map.txt`）⇒ **需 reviewer 复核**（reviewer 明文「截图先交 reviewer，通过后才打包」） |
| **APP-065 B 改名** | ✅ 「说话人识别」→ **「区分说话人（用于克隆）」**，**移入「⑤ 高级」**，带提示；**变量名 `var_speaker` 不变**（`app227`/`app204` 依赖） |
| **设备级实测**（APP-063 ④） | 🔄 已跑完：**7 PASS / 4 FAIL / 4 NONE**（证据 `results/app/app233_device_acceptance_evidence.json`）。✅ 相对 v2.1 实质进步：**定时克隆更新 27 次 → 0**、**「没有可用音色」= 0**（APP-061①「全程无声」已消除）。❌ ⑤-① **clone 占比 0 %**（根因＝**本机无克隆引擎**，⇒ APP-065 C 在本机**无法判定**，≠ 不合格）｜❌ ③-③ ASR RTF 增量 **+0.122 > +0.10** ｜❌ ④-② 声纹无 new_spk 配对（与 10 s 窗口延迟一致）｜🔴 **判据①曾是假 PASS**（正则漏了 `没有可用引擎`）⇒ **已修**（`app223`，自检 5/0） |
| **回归** | `app229` 38/0 ｜`app227` 34/0 ｜`app165` **PASS**（C4 口径按 APP-065 A 更新为 5，**C3/C5/C6 未动** ⇒ APP-048 核心不变量保住）｜`app220/226/228` 39/10/8 全 PASS ｜`app219` 11 PASS/2 FAIL（**仅 G2**：字幕区 **66.88 % < 70 %**）｜`app215` 27 PASS/2 FAIL（**与本轮无关**：HEAD 版同脚本跑出相同 2 条 ⇒ 既有缺陷） |
| **待 reviewer 裁定** | ① D1 跨模块错位（需 ASR 同源；含「seg IR 是否已导成 5 s 形状」）② **70 % 字幕区 vs 5 组竖排**（实测 66.88 % ⇒ 选「接受」还是「允许 ④ 组第二个标签列」）③ app215 的 2 条既有 FAIL 是否顺手修 ④ 判据①「三条故障串」口径 ⑤ `app230` D1-6（客户包须含 `asr_spk_window.py`） |
| **未做 / 未交付** | ⛔ **未打包 v2.3**（reviewer 明文「截图先交 reviewer，通过后才打包」⇒ 本轮停在复核点；且 ③ 未解前也不该打包）｜⛔ 未通知用户／未改桌面快捷方式｜⛔ **v2.1、v2.2 目录与 zip 一个字节都没动**（本轮只建了**影子包** `shared/app065_shadow` 供设备级实测，不是交付物）｜⛔ **未提交任何 `CORRECTIONS_*.md`**（本模块全程只读）｜⛔ APP-065 C 的「每段克隆音色表 ＋ wav ＋ 相似度」需 CUDA 边车环境；APP-063 ③(e) 的 CPU 卸载 A/B 本轮未做 |
'''


def main():
    raw = open(STATUS, 'rb').read()
    txt = raw.decode('utf-8')
    EOL = '\r\n' if '\r\n' in txt else '\n'
    lines = txt.split(EOL)

    i = None
    for k, l in enumerate(lines):
        if l.startswith('### §132'):
            i = k
            break
    if i is None:
        print('[ABORT] 找不到 §132')
        return 2

    # ① 正文**逐字**归档
    os.makedirs(ARCH, exist_ok=True)
    p = os.path.join(ARCH, 'STATUS_APP_sec132_upto_20261103.md')
    body = EOL.join(lines[i:])
    with open(p, 'wb') as f:
        f.write(body.encode('utf-8'))
    print('已归档 §132 正文 ⇒ %s（%d B）' % (p, os.path.getsize(p)))

    # ② 正文处换成「速查表 + 归档指针」
    newlines = lines[:i] + SUMMARY.replace('\n', EOL).split(EOL)
    new = EOL.join(newlines)
    if not new.endswith(EOL):
        new += EOL
    data = new.encode('utf-8')
    print('新文件：%d B / %d 行' % (len(data), new.count('\n')))
    if len(data) > 40000 or new.count('\n') > 300:
        print('[ABORT] 仍超限额')
        return 2
    tmp = STATUS + '.tmp_arch'
    open(tmp, 'wb').write(data)
    assert open(tmp, 'rb').read() == data
    os.replace(tmp, STATUS)
    assert open(STATUS, 'rb').read() == data
    print('OK §132 正文已归档 + 速查表已就位')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
