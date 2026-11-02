#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§131 收尾：把 §131 正文**就地更新**（ASR-041 对齐后的版本），
并同步头部的「阻塞 / 待用户决定」。

🔴 **纪律**：§131 是**本轮自己写的**章节 ⇒ 就地更新它的正文是允许的
（APP-052 ④ 的「旧正文一字不删」针对的是**更早的**章节 ⇒ §123–§130 全部不动）。
⇒ 写后复核：§123–§130 的标题与正文**逐字未变** ＋ §131 已更新 ＋ 限额内。
"""
from __future__ import annotations

import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')

MAX_BYTES = 40000
MAX_LINES = 300


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main() -> int:
    text = read(STATUS)
    before = hashlib.sha256(text.encode('utf-8')).hexdigest()

    # ── 1. 取出 §131 的**旧正文**（用于写后逐字比对：应**被替换**） ──
    m = re.search(r'(?m)^(### §131 [^\n]*)$', text)
    if not m:
        print('!! 找不到 §131 ⇒ 中止')
        return 2
    title131 = m.group(1)

    # ── 2. 取出 §123–§130 的正文（**必须逐字不变**） ──
    protected = {}
    for mm in re.finditer(r'(?m)^(### §(\d+) [^\n]*)$', text):
        n = int(mm.group(2))
        if n <= 130:
            idx = mm.end()
            nxt = re.search(r'(?m)^### ', text[idx:])
            end = idx + (nxt.start() if nxt else len(text) - idx)
            protected[n] = (mm.group(1), text[idx:end])

    # ── 3. 替换 §131 正文 ──
    new_body = read(os.path.join(HERE, '_app130_sec131_body.md'))
    new_body = '\n' + new_body.lstrip('\n')
    # 🔴 **旧正文要被替换掉**（§131 是**本轮自己写的**章节 ⇒ 允许就地更新）
    #   ⇒ 找出 §131 的**正文结束位置**（下一个 `### ` 或文件尾）
    tail_start = m.end()
    nxt = re.search(r'(?m)^### ', text[tail_start:])
    tail_end = tail_start + (nxt.start() if nxt else len(text) - tail_start)
    out = text[:tail_start] + new_body + text[tail_end:]

    # ── 4. 头部「阻塞 / 待用户决定」补 D1 的裁定项 ──
    out = re.sub(
        r'(?m)^(阻塞 / 待用户决定: .*?D1–D4 已由 reviewer 裁定并于 §131 执行.*?)$',
        r'\1 ｜🔴 **D1 是否切 5 s 等 reviewer 裁定**（ASR-041：召回 10/12 持平、'
        r'误报 0、延迟 P50 10.0003→5.0002 s ⇒「建议切 5 s」但 **ASR 自己没切** '
        r'⇒ **App 保持 10 s** ⇒ 切换只改 ASR 常量 ⇒ App 自动跟随）',
        out, count=1)
    # 🔴 **「最近更新」条目**：只保留**一行摘要**（详细在 §131 正文里）
    out = re.sub(
        r'(?m)^- 2026-11-02 10:58 \*\*§131 APP-062（D1–D4）已执行\*\*.*$',
        '- 2026-11-02 10:58 **§131 APP-062（D1–D4）已执行** ⇒ **D1** 旁路窗长改'
        '**配置项**（`LIVECAP_SPK_WINDOW_S`）＋**与 ASR 侧同源**（读 '
        '`asr_spk_window.WIN_S`）｜**D2** 选「跟随说话人」⇒ **自动开旁路**'
        '（三处同步）＋ 状态栏「说话人分离：开（克隆需要）」｜**D3** **客户包去掉 '
        'TTS=CUDA**（界面不显示 ＋ CLI 拒绝 exit 2）＋ `pkg_exclude` 排除 3 个文件 '
        '⇒ **包内 grep `_fq3tts_env` 命中 0 处**｜**D4** **禁止** MT+TTS 同 NPU ⇒ '
        'MT 自动改 GPU.0 ＋ 告知 ＋ 写日志 ＋ 启动时同样处理 ⇒ `app227` **34/0**、'
        '`app228` **8/0** ⇒ 回归 `app215` **29/0**、`app220` **39/0**、'
        '`app219` **13/0**、`app224` **5/0**（均与 §129 一致）'
        '⛔ D2/D4 截图与设备级实测仍未做（TTS 模块持 `MACHINE_LOCK`）'
        '🔴 **更正 §130**：reviewer 于 **09:17:51 追加了 APP-062** '
        '⇒ §130「SHA 零改动」结论作废',
        out, count=1)

    # ── 5. 自指大小修正（不动点迭代） ──
    for _ in range(8):
        b = len(out.encode('utf-8'))
        nl = out.count('\n') + 1
        n2 = re.sub(r'(?m)^已压缩: 本文件 \d+ B / \d+ 行',
                    '已压缩: 本文件 %d B / %d 行' % (b, nl), out, count=1)
        if n2 == out:
            break
        out = n2
    b = len(out.encode('utf-8'))
    nl = out.count('\n') + 1
    print('更新后：%d B / %d 行（限额 %d B / %d 行）'
          % (b, nl, MAX_BYTES, MAX_LINES))
    if b > MAX_BYTES or nl > MAX_LINES:
        print('!! 仍超限 ⇒ 中止（不写盘）')
        return 4

    tmp = STATUS + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)

    # ── 6. 写后复核 ──
    after = read(STATUS)
    assert len(after.encode('utf-8')) == b, '写后字节数不一致'
    assert after.count('\n') + 1 == nl, '写后行数不一致'
    for n, (t, body) in protected.items():
        mm = re.search(r'(?ms)^(### §%d .*)$(.*?)(?=^### |\Z)' % n, after)
        if not mm:
            print('!! §%d 标题丢失 ⇒ 中止' % n)
            return 5
        if mm.group(1) != t:
            print('!! §%d 标题被改 ⇒ 中止' % n)
            return 6
        if mm.group(3) != body:
            print('!! §%d 正文被改 ⇒ 中止（**只允许改 §131**）' % n)
            return 7
    if 'asr_spk_window' not in after:
        print('!! §131 未更新（缺 ASR-041 对齐说明）⇒ 中止')
        return 8
    print('写后复核通过：%d B / %d 行；§123–§130 标题与正文**逐字未变**；'
          '§131 已更新' % (b, nl))
    print('SHA256 %s → %s' % (before, hashlib.sha256(after.encode('utf-8')).hexdigest()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
