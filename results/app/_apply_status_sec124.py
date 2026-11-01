#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 §124 写进 status/app/STATUS_APP.md。

纪律：
* 🔴 **只追加章节**（§124 追加到文末）＋ **只动头部区**（last_ack / 更新时间 / 当前任务 / 阻塞 / 已压缩）
  ＋ 表格里**替换对应行**（旧行内容不删，只是换成新版本口径）。
* 🔴 **旧正文一字未删**（除被显式替换的那几行外，全部原样保留）。
* 🔴 头部「已压缩」里的**自指大小必须与磁盘实测一致** ⇒ 写完迭代到不动点。
* 🔴 **不碰** `status/app/CORRECTIONS_APP.md`。
"""
from __future__ import annotations

import io
import os
import re

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
BODY = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_status_sec124_body.md'

NEW_HEADER_TASK = (
    '当前任务: **§124 ✅ APP-055 / APP-056 / APP-057 / APP-058 已执行完毕**'
    '（`last_ack` APP-054 → **APP-058**）—— ① **APP-055**：v1.13 目录被改的 **6 个文件**已全部还原'
    '（`app207` **6/6**；payload 重算 `files=14212` / `bytes=13689629685` 与 06:08 记录**完全一致**；'
    '旧 zip **不删不改**）⇒ 此后**不用 `--same-version`**，新产物只走「新版本号目录＋新 zip＋新 MANIFEST＋重签 ACCEPTED」'
    '② **APP-056**：自动化指令已插「第 0 步 模块租约」；本轮 **TAKEOVER** 后持 token `8afc6c0f`，'
    '长作业（解压 PID 15792 / 打包 PID 3396）全部后台启动并登记 ⇒ **收尾 release**'
    '③ **APP-057**：交付包 **v2.1**（zip **11 233 135 359 B** / **14 317 文件** / SHA256 `835803a7…aaa4` / 20:38:13）；'
    '闸门 `app191` **18/0** ＋ `app213` **15/0**（含新增的 EXT-029 两条）＋ `app212` **9/0** ＋ `app214` **4/0**'
    '（reviewer 点名的 5 个开发目录 **0** 命中）；**v2.0 目录与 zip 原样保留**'
    '④ **APP-058**：同段复测（3291.6–3591.6 s）覆盖率 **93.75 %**（ref 95.65 % ⇒ Δ 1.90 pp）、不同标签 **4**、'
    '置换一致率 **64.29 %**、APP-054 三项全过 ⇒ **7 PASS / 1 FAIL**；🔴 **换人点召回率 33.33 %（口径A）/ 58.33 %（口径B）⇒ 未达 60 %**（不换口径）'
    '⑤ 本轮抓到并修掉 **4 个判据自身缺陷**（漏扫 docstring / 恒假覆盖判据 / marker 口径混淆 / `pkg_dir` 写死构建机家目录）'
)

NEW_HEADER_BLOCK = (
    '阻塞 / 待用户决定: ① 🔴 **APP-057 ⑤(b) 未做**（桥接 + Edge 加载插件 + player 录 60 s 网页配音 ⇒ **需用户手势**：'
    'Edge 加载已解压扩展 ＋ 点扩展图标 ＋ player「开始捕获」）⇒ 配音录音与逐段译文待用户实听；'
    '② 🔴 **APP-058 判据④ 召回率未达标**（33.33 % / 58.33 %，均 < 60 %；参照标注自身与人工标注就差 1 处 ⇒ 上限 91.7 %）'
    '⇒ **如实记录、未换口径**，根因指向 ASR 侧说话人切换判定；'
    '③ 🔴 **交付版本号是 v2.1 而非用户原话的 V2.0**（v2.0 首包违反 ③，且「旧 zip 不覆盖」）⇒ 请 reviewer 确认 v2.1 即交付版'
    '（改名/重签**不需要**重打包）；'
    '④ 🔴 **v2.1 上尚未重跑 ⑤(a) A/B**（本轮 A/B 跑在 v2.0 上，而 v2.1 的 `app/` 生产模块与 v2.0 **只差** `speaker_assets.py` 的注释）'
    '⇒ 闭环需再跑一次；'
    '⑤ 🔴 **桌面仍残留 `实时配音桥接服务 v2.0.lnk`**（指向被取代的 v2.0 包；快捷方式闸门刻意不删旧链）⇒ 请用户/reviewer 决定是否清理；'
    '⑥ 🔴 **需用户实听 3 段 1.2–1.3× 配音素材**（`C:\\Users\\Trekker-PTL\\shared\\app_accel_listen\\`）＋ reviewer 判定音质 / 不变调 / 可懂；'
    '⑦ 🔴 **APP-054 的 NOTICE 待主会话转达 ASR**（治本项：`run_seg_side` 每次调用重编译模型）；'
    '⑧ 🔴 **§123 待复核项**（GUI 正式行的 `[Sx]` 前缀取不到图 / `app179` B4 空真 / APP-048 运行中截图仍缺）本轮未动；'
    '⑨ 🔴 **本轮未修改** `status/app/CORRECTIONS_APP.md`（只读；开工 SHA256 `89018d17…d920d` / 145 700 B / mtime 15:49:35 / 58 条目 ⇒ 收尾**复核零改动**）；'
    '⑩ 🔴 已写 `shared/NOTICE_app_to_ext_devpath_leak.md`（EXT 侧 `ext/bridge/*.py` 的 docstring 里仍有开发机绝对路径）**待主会话转达 EXT**'
)

NEW_RECENT = (
    '- 2026-11-01 20:45 **§124 APP-055 / APP-056 / APP-057 / APP-058 已执行** ⇒ ① **v1.13 目录还原**（6/6；'
    'payload `files=14212` / `bytes=13689629685` 与 06:08 记录一致；旧 zip 不删不改）② **模块租约**（TAKEOVER 后持 '
    '`8afc6c0f`；长作业后台 + 登记 PID）③ **交付包 v2.1**（zip **11 233 135 359 B** / **14 317 文件** / SHA256 '
    '`835803a7…aaa4` / 20:38:13；`app191` **18/0** ＋ `app213` **15/0** ＋ `app212` **9/0** ＋ `app214` **4/0**；'
    '**v2.0 原样保留**）④ **同段复测**（3291.6–3591.6 s）覆盖率 **93.75 %**（Δ 1.90 pp）、不同标签 **4**、置换 **64.29 %**、'
    'APP-054 三项全过 ⇒ **7 PASS / 1 FAIL**；🔴 召回率 **33.33 %/58.33 % ⇒ 未达 60 %** ⑤ 修掉 **4 个判据自身缺陷**\n'
)

NEW_ROWS = {
    '客户包目录': (
        '| 客户包目录 | `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_v2.1`（**当前最新**；'
        'v2.0 / v1.13 目录仍在，未删除） | `Confucius4_LiveCaption_v2.1/MANIFEST.json` → `version=2.1`'
        '（`DELIVERY_2.1.json` → `manifest_version`） |'),
    '客户包 zip': (
        '| 客户包 zip | **v2.1**（**2026-11-01 20:38:13** / **11 233 135 359 B** / **14 317 文件** / SHA256 '
        '**`835803a7246470faf0725a3f429b0339ccb6dac8ba7e1d1854176775e6cbaaa4`**）⇒ 含 APP-053/054 代码 ＋ '
        '**EXT 插件 + 桥接服务** ＋ `ACCEPTED.json`（`pkg_dir` = `<HOME>\\Confucius4_LiveCaption_v2.1` ＋ '
        '`code_fingerprint` + `binding_gate=app191`）＋ `NOTICE` ＋ `THIRD_PARTY.md` ＋ `README_插件.md` '
        '⇒ **v2.0 首包（17:49 / SHA `8198924f…`）保留不删** | `results/app/DELIVERY_2.1.json` → `sha256` / '
        '`bytes` / `mtime`；打包日志 → 「比对 14 317 个文件 / 全部逐字节一致」＋ `testzip()` OK |'),
    '桌面快捷方式': (
        '| 桌面快捷方式 | **v2.1 两个**（`Confucius4 实时字幕 v2.1.lnk` ＋ `实时配音桥接服务 v2.1.lnk`，'
        '均由 `WScript.Shell.CreateShortcut` 生成 ＋ COM 读回验证 ⇒ 非坏链）；'
        '⚠️ 桌面仍残留 `实时配音桥接服务 v2.0.lnk`（**未删**，待用户/reviewer 决定） | '
        '`results/app/app212_app057_v21_shortcuts_evidence.json` → `checks`（**9 PASS / 0 FAIL**，含 3 条反证） |'),
}

NEW_NUM_ROWS = (
    '| **说话人标签覆盖率（同段口径 · 修复后）** | **93.75 %**（45/48 句带标签，**分子分母同一段** Q&A 切片 '
    '3291.6–3591.6 s）⇒ 与 app193 参照 95.65 % 相差 **1.90 pp**（≤ 5 pp） | '
    '`results/app/app208_app058_spk_retest_evidence.json` → `measured.coverage_pct` / `checks` ② |\n'
    '| **换人点召回率（APP-058 判据④）** | 口径 A **33.33 %**（4/12 命中、误报 3）／口径 B **58.33 %**（7/12、误报 0）'
    '⇒ **均 < 60 % ⇒ 未达标**（参照标注自身与人工标注差 1 处 ⇒ 上限 91.7 %） | `app208…` → `measured.switch_analysis`；'
    '`app210_app058_recall_diagnosis_evidence.json` → `method_A_index` / `method_B_text_aligned` |\n'
    '| **v2.1 内容闸门 / 绑定闸门 / 快捷方式 / 依赖隔离** | `app213` **15/0**（8/8 反证）｜`app191` **18/0**｜'
    '`app212` **9/0**｜`app214` **4/0**（reviewer 点名的 5 个开发目录 **0** 命中；扫 6 729 个文件） | '
    '`results/app/app213_app057_v21_gates_evidence.json` / `app191_v21_binding_evidence.json` / '
    '`app212_app057_v21_shortcuts_evidence.json` / `app214_app057_v21_clean_test_evidence.json` |\n'
)

SEC_INDEX_ROW = (
    '| §124 | **APP-055/056/057/058**：v1.13 还原 ＋ 模块租约 ＋ V2.1 交付包 ＋ 同段覆盖率复测 | '
    '**本轮新增（见下）** |\n'
)


def set_self_size(text):
    """把「已压缩」那一行的自指大小更新成磁盘实测（写完迭代到不动点）。"""
    path, size, lines = STATUS, len(text.encode('utf-8')), text.count('\n') + 1
    new = re.sub(
        r'已压缩: 本文件 \d+ B / \d+ 行',
        '已压缩: 本文件 %d B / %d 行' % (size, lines), text, count=1)
    return new


def main():
    with io.open(STATUS, encoding='utf-8', newline='') as f:
        text = f.read()
    orig_len = len(text)

    # ① 头部区
    text = re.sub(r'^last_ack: APP-054$', 'last_ack: APP-058', text, count=1,
                  flags=re.M)
    text = re.sub(r'^更新时间: .*$', '更新时间: 2026-11-01 20:45', text, count=1,
                  flags=re.M)
    text = re.sub(r'^当前任务: .*$', lambda _m: NEW_HEADER_TASK, text, count=1,
                  flags=re.M)
    text = re.sub(r'^阻塞 / 待用户决定: .*$', lambda _m: NEW_HEADER_BLOCK, text,
                  count=1, flags=re.M)

    # ② 最近更新：插到最前
    m = re.search(r'^## 最近更新\n', text, flags=re.M)
    text = text[:m.end()] + NEW_RECENT + text[m.end():]

    # ③ 表格行替换
    lines = text.split('\n')
    out = []
    for ln in lines:
        hit = False
        for key, newline in NEW_ROWS.items():
            if ln.startswith('| ' + key + ' |'):
                out.append(newline)
                hit = True
                break
        if not hit:
            out.append(ln)
    text = '\n'.join(out)

    # ④ 关键数字：插到表格末尾（「## 最近章节」之前）
    anchor = '\n\n## 最近章节'
    idx = text.rfind(anchor)
    if idx > 0:
        text = text[:idx] + '\n' + NEW_NUM_ROWS.rstrip('\n') + text[idx:]

    # ⑤ 最近章节：插 §124 行（紧跟表头行之后）
    m2 = re.search(r'^\| §123 \|.*$', text, flags=re.M)
    if m2:
        text = text[:m2.end()] + '\n' + SEC_INDEX_ROW.rstrip('\n') + \
            text[m2.end():]

    # ⑥ 追加 §124 正文
    with io.open(BODY, encoding='utf-8') as f:
        body = f.read().rstrip('\n')
    if '### §124 ' not in text:
        text = text.rstrip('\n') + '\n\n' + body + '\n'

    # ⑦ 自指大小 ⇒ 迭代到不动点
    for _ in range(8):
        new = set_self_size(text)
        if new == text:
            break
        text = new
    set_self_size(text)

    tmp = STATUS + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(tmp, STATUS)
    print('STATUS written: %d → %d B / %d 行'
          % (orig_len, len(text.encode('utf-8')), text.count('\n') + 1))


if __name__ == '__main__':
    main()
