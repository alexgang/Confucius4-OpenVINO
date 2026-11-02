#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app130 —— 把 §130 正文**逐字**归档，并把 §131 写进 STATUS_APP.md。

🔴 纪律（APP-052 ④ / MEMORY 十）：
  - 只**追加**章节，不回头改旧章节；
  - 旧正文**一字不删**（移到 `status/archive/`，逐字保留）；
  - 归档件必须**逐字命中**（写后复核）；
  - 压缩后复核 ≤ 40 KB / ≤ 300 行；
  - 压缩用 `.tmp` → `os.replace` **原子替换**；
  - 自指大小（头部「已压缩」行里的字节数）必须与磁盘**实测一致**（不动点迭代）。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE_DIR = os.path.join(REPO, 'status', 'archive')
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_sec130_upto_20261102.md')

MAX_BYTES = 40000
MAX_LINES = 300
UPDATED_AT = '2026-11-02 10:58'


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def split_sections(text):
    ms = list(re.finditer(r'(?m)^(### §\d+ .*)$', text))
    if not ms:
        return text, []
    head = text[:ms[0].start()]
    secs = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        secs.append((m.group(1), text[m.end():end]))
    return head, secs


def main() -> int:
    text = read(STATUS)
    head, secs = split_sections(text)

    # ── 1. 归档 §130 的正文（逐字） ─────────────────────────
    keep_idx = []
    archived = []
    for i, (title, body) in enumerate(secs):
        m = re.match(r'### §(\d+)', title)
        n = int(m.group(1)) if m else 0
        if n == 130:
            archived.append((title, body))
        else:
            keep_idx.append(i)
    if not archived:
        print('!! 没找到 §130 ⇒ 中止（不猜）')
        return 2

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(ARCHIVE, 'w', encoding='utf-8', newline='') as f:
        f.write('# STATUS_APP 归档（§130 正文逐字留存）\n\n'
                '> 本文件由 `results/app/_app130_archive_sec129.py` 之外的 '
                '`results/app/_app130_append_sec131.py` 于 2026-11-02 生成。\n'
                '> **§130 的正文逐字保留，内容一字未删**；'
                '原位留有指针行（见 `status/app/STATUS_APP.md`）。\n\n')
        for title, body in archived:
            f.write(title + '\n')
            f.write(body if body.endswith('\n') else body + '\n')
            f.write('\n')

    arc = read(ARCHIVE)
    for title, body in archived:
        if body.strip() and body.strip() not in arc:
            print('!! 归档件未逐字命中 %s ⇒ 中止' % title[:30])
            return 3
        print('归档逐字命中：%s' % title[:46])

    # ── 2. 重建 STATUS ────────────────────────────────────
    out = head
    for i, (title, body) in enumerate(secs):
        if i in keep_idx:
            out += title + '\n' + body
        else:
            out += title + '\n'
            out += ('\n> **本节正文已原样归档** ⇒ 见 '
                    '`status/archive/STATUS_APP_sec130_upto_20261102.md`'
                    '（逐字保留，内容一字未删）。\n')

    # ── 3. 追加 §131 ────────────────────────────────────────
    sec131 = read(os.path.join(HERE, '_app130_sec131_body.md'))
    out += '\n' + sec131

    # ── 4. 头部：last_ack → APP-062；更新时间用实测值 ────────
    out = re.sub(r'(?m)^last_ack: .*$', 'last_ack: APP-062', out, count=1)
    out = re.sub(r'(?m)^更新时间: .*$',
                 '更新时间: %s' % UPDATED_AT, out, count=1)
    out = re.sub(r'(?m)^当前任务: .*$',
                 '当前任务: **§131 APP-062（D1–D4：用户对 APP-061 的四项决定）'
                 '已执行（代码层全部完成）** —— ① **D1** 旁路窗长改成'
                 '**配置项**（`LIVECAP_SPK_WINDOW_S`）＋**与 ASR 侧常量同源**'
                 '（读 `asr052_spk_runtime.WIN_S`，不再两处各写一个；默认仍 10 s）'
                 '② **D2** 选「跟随说话人」⇒ **自动打开说话人旁路**（勾选框/开关/桥接器'
                 '三处同步）＋ 状态栏「说话人分离：开（克隆需要）」＋ 旁路关着时克隆**不可选**'
                 '③ **D3** **客户包里去掉 TTS=CUDA**（界面不显示 ＋ CLI 明确拒绝 exit 2）'
                 '＋ `pkg_exclude` 排除 `tts_cuda.py`/`tts_cuda_sidecar.py`/`docs/CUDA_TTS.md`'
                 '⇒ **包内 grep `_fq3tts_env` 命中 0 处**（`app228` 8/0）'
                 '④ **D4** **禁止** MT 与 TTS 同 NPU ⇒ **MT 自动改 GPU.0** ＋ 状态栏/弹框告知'
                 '＋ 写进日志 ＋ **启动时 `device_config.json` 同组合同样处理**'
                 '（`app227` 34/0，含反证） ｜ 🔴 **本节更正 §130 的一条结论**：'
                 'reviewer 已于 **09:17:51 追加 APP-062** ⇒ §130「SHA 零改动」作废',
                 out, count=1)
    out = re.sub(r'(?m)^阻塞 / 待用户决定: .*$',
                 '阻塞 / 待用户决定: 🔴 **D1–D4 已由 reviewer 裁定并于 §131 执行**；'
                 '⛔ **D2/D4 的截图验收尚未做**（需起 GUI ⇒ 与设备级作业同批 ⇒ 等设备空闲）；'
                 '⛔ **设备级实测（APP-061 ①③④⑤ + ③(e)）仍未做**'
                 '（本轮 `MACHINE_LOCK` 已被 **TTS 模块**持有 ⇒ 不与它抢设备）；'
                 '🔴 **§128 新增 1 项待 reviewer 裁定**：共享锁 `stale_boot` 分支'
                 '**优先于 PID 存活判断** ⇒ 时钟异常时会**抢走活锁**（未改实现语义）；'
                 '🔴 **§129 新增 1 项待 reviewer 裁定**：锁闸门第 11 组的 AST 反证谓词**恒真**'
                 '⇒ 修它要动**共享锁闸门**（ASR/MT/TTS 共用）⇒ 本轮**只定位、只留证**；'
                 '🔴 **§130 新增 1 项待 reviewer 裁定**：`app224` 的「值没变」判据现在'
                 '**豁免 docstring**（属口径放宽，有自检证明豁免没变成「什么都放过」）；'
                 '🔴 **§131 新增 4 项待 reviewer 确认**：D1 同源依赖包内 ASR 模块'
                 '（读不到 ⇒ 静默退回 10.0）｜D3「客户包」判据用 `app/MANIFEST.json`｜'
                 'D2 自动开旁路在**已开会话**里需**重启会话**才真正生效｜'
                 'D4 弹框在启动路径也会弹（模态）',
                 out, count=1)

    # ── 5. 「最近更新」区块追加本轮条目（**保留条目之间的空行**） ──
    entry = ('- 2026-11-02 10:58 **§131 APP-062（D1–D4）已执行** ⇒ '
             '**D1** 旁路窗长改**配置项**（`LIVECAP_SPK_WINDOW_S`）＋**与 ASR 侧同源**'
             '（读 `asr052_spk_runtime.WIN_S`）｜**D2** 选「跟随说话人」⇒ **自动开旁路**'
             '（三处同步）＋ 状态栏「说话人分离：开（克隆需要）」｜'
             '**D3** **客户包去掉 TTS=CUDA**（界面不显示 ＋ CLI 拒绝 exit 2）'
             '＋ `pkg_exclude` 排除 3 个文件 ⇒ **包内 grep `_fq3tts_env` 命中 0 处**｜'
             '**D4** **禁止** MT+TTS 同 NPU ⇒ MT 自动改 GPU.0 ＋ 告知 ＋ 写日志 '
             '＋ 启动时同样处理 ⇒ `app227` **34/0**、`app228` **8/0**（含反证）'
             '⇒ 回归 `app215` **29/0**、`app220` **39/0**、`app219` **13/0**、'
             '`app224` **5/0**（全部与 §129 一致）'
             '⛔ D2/D4 截图与设备级实测仍未做（TTS 模块持 `MACHINE_LOCK`）'
             '🔴 **更正 §130**：reviewer 于 **09:17:51 追加了 APP-062** '
             '⇒ §130「SHA 零改动」结论作废\n')
    m = re.search(r'(?ms)^## 最近更新\n(.*?)(?=^## )', out)
    if not m:
        print('!! 找不到「最近更新」区块 ⇒ 中止')
        return 7
    out = out[:m.start(1)] + entry + m.group(1) + out[m.end(1):]

    # ── 6. 自指大小修正（不动点迭代） ─────────────────────────
    for _ in range(8):
        b = len(out.encode('utf-8'))
        lines = out.count('\n') + 1
        new_out = re.sub(
            r'(?m)^已压缩: 本文件 \d+ B / \d+ 行',
            '已压缩: 本文件 %d B / %d 行' % (b, lines), out, count=1)
        if new_out == out:
            break
        out = new_out
    b = len(out.encode('utf-8'))
    lines = out.count('\n') + 1
    print('压缩后：%d B / %d 行（限额 %d B / %d 行）' % (b, lines,
                                                       MAX_BYTES, MAX_LINES))
    if b > MAX_BYTES or lines > MAX_LINES:
        print('!! 仍超限 ⇒ 中止（不写盘）')
        return 4

    # ── 7. 原子替换 ─────────────────────────────────────────
    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)

    # ── 8. 写后复核 ─────────────────────────────────────────
    after = read(STATUS)
    assert len(after.encode('utf-8')) == b, '写后字节数不一致'
    assert after.count('\n') + 1 == lines, '写后行数不一致'
    for title, _body in archived:
        if title not in after:
            print('!! 旧章节标题丢失 ⇒ 中止')
            return 5
    if '§131' not in after:
        print('!! §131 未写入 ⇒ 中止')
        return 6
    if 'last_ack: APP-062' not in after:
        print('!! last_ack 未更新 ⇒ 中止')
        return 8
    print('写后复核通过：%d B / %d 行；§130 标题仍在；§131 已追加；last_ack=APP-062'
          % (b, lines))
    print('归档 SHA256 = %s' % hashlib.sha256(
        open(ARCHIVE, 'rb').read()).hexdigest())
    print('STATUS SHA256 = %s' % hashlib.sha256(
        open(STATUS, 'rb').read()).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
