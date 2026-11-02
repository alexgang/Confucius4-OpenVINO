#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app130 —— 把 §129 正文**逐字**归档，并把 §130 写进 STATUS_APP.md。

🔴 纪律（APP-052 ④ / MEMORY 十）：
  - 只**追加**章节，不回头改旧章节；
  - 旧正文**一字不删**（移到 `status/archive/`，逐字保留）；
  - 归档件必须**逐字命中**（写后复核）；
  - 压缩后复核 ≤ 40 KB / ≤ 300 行；
  - 压缩用 `.tmp` → `os.replace` **原子替换**；
  - 自指大小（头部「已压缩」行里的字节数）必须与磁盘**实测一致**（差 2 B 也要改）⇒ 不动点迭代。
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
ARCHIVE = os.path.join(ARCHIVE_DIR, 'STATUS_APP_sec129_upto_20261102.md')

MAX_BYTES = 40000
MAX_LINES = 300
UPDATED_AT = '2026-11-02 09:56'


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

    # ── 1. 归档 §129 的正文（逐字） ─────────────────────────
    keep_idx = []
    archived = []
    for i, (title, body) in enumerate(secs):
        m = re.match(r'### §(\d+)', title)
        n = int(m.group(1)) if m else 0
        if n == 129:
            archived.append((title, body))
        else:
            keep_idx.append(i)
    if not archived:
        print('!! 没找到 §129 ⇒ 中止（不猜）')
        return 2

    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(ARCHIVE, 'w', encoding='utf-8', newline='') as f:
        f.write('# STATUS_APP 归档（§129 正文逐字留存）\n\n'
                '> 本文件由 `results/app/_app130_archive_sec129.py` 于 '
                '2026-11-02 生成。\n'
                '> **§129 的正文逐字保留，内容一字未删**；'
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

    # ── 2. 重建 STATUS：头部 + 保留的旧节 + §129 指针 ─────────
    out = head
    for i, (title, body) in enumerate(secs):
        if i in keep_idx:
            out += title + '\n' + body
        else:
            out += title + '\n'
            out += ('\n> **本节正文已原样归档** ⇒ 见 '
                    '`status/archive/STATUS_APP_sec129_upto_20261102.md`'
                    '（逐字保留，内容一字未删）。\n')

    # ── 3. 追加 §130（正文由调用方传入，避免在脚本里塞长文本） ──
    sec130 = read(os.path.join(HERE, '_app130_sec130_body.md'))
    out += '\n' + sec130

    # ── 4. 更新头部：last_ack 不变；更新时间用实测值 ───────────
    out = re.sub(r'(?m)^更新时间: .*$',
                 '更新时间: %s' % UPDATED_AT, out, count=1)
    # 「当前任务」行 ⇒ 换成本轮摘要（**只动这一行**，其余头部区不动）
    out = re.sub(r'(?m)^当前任务: .*$',
                 '当前任务: **§130 巡检无新纠偏（61 条 = `last_ack` APP-061）'
                 '⇒ 自查出并修掉 3 个真缺陷：'
                 '① `app224` 的「字符串常量逐字不变」**按下标比** ⇒ 合法增删一个常量就整体错位 '
                 '⇒ 炸出 483 条假「值变了」⇒ 闸门在**正确代码上**报 FAIL（实测 3 PASS / 2 FAIL）'
                 '⇒ 改按**多重集**比 ＋ 拆出 docstring（散文会合法演进）＋ 加 2 组判据自检 '
                 '② CUDA 路线「回落预设」**不换参考音频** ⇒ 边车里仍是上一人的克隆音频 ⇒ **串音** '
                 '⇒ 4 个回落出口收敛到共用出口（`app226` 10/0）'
                 '③ `app215` 的 2 处判据被重构波及（反证锚点 + ①b 作用域）⇒ 语义不变地跟着走**',
                 out, count=1)
    out = re.sub(r'(?m)^阻塞 / 待用户决定: .*$',
                 '阻塞 / 待用户决定: 🔴 **D1–D4 仍由 reviewer/用户决定**'
                 '（旁路窗口时长 / 是否自动开旁路 / 客户包是否保留 CUDA 选项 / NPU 共用是警告还是禁止）；'
                 '🔴 **§128 新增 1 项待 reviewer 裁定**：共享锁 `stale_boot` 分支'
                 '**优先于 PID 存活判断** ⇒ 时钟异常时会**抢走活锁**（本轮只写成显式断言，**未改实现语义**）；'
                 '🔴 **§129 新增 1 项待 reviewer 裁定**：锁闸门第 11 组的 AST 反证谓词**恒真**'
                 '（只认 `os.exists`、抓不到 `os.path.exists`）⇒ 修它要动**共享锁闸门**'
                 '（ASR/MT/TTS 共用）⇒ 本轮**只定位、只留证**；'
                 '🔴 **§130 新增 1 项待 reviewer 裁定**：`app224` 的「值没变」判据现在**豁免 docstring** '
                 '⇒ 属**判据口径的放宽**（行为承载常量仍严格判 ＋ 有自检证明豁免没变成「什么都放过」）；'
                 '⛔ **设备级实测（①③④⑤ + ③(e)）仍未做**：本轮安静窗口不可用的原因**已定位**'
                 '⇒ 是**ASR 持有 `MACHINE_LOCK` 在跑 D1（5 s vs 10 s）**＋ TTS 在跑 `diag_tts044` '
                 '（用户自己的 v2.1 会话实测 CPU 增量 0.000 s/10 s ⇒ **不干扰**）'
                 '⇒ 等 ASR 释放锁且机器安静后跑 `app223 --run`',
                 out, count=1)

    # ── 5. 「最近更新」区块追加本轮条目（**保留条目之间的空行**） ──
    entry = ('- 2026-11-02 09:56 **§130** ⇒ 无新纠偏（61 条 = APP-061）⇒ '
             '**自查 3 个真缺陷并修好**：① `app224` 的「字符串常量逐字不变」**按下标比** ⇒ '
             '合法增删一个常量就整体错位 ⇒ `app223` 炸出 **483 条**假「值变了」'
             '⇒ **闸门在正确代码上永久 FAIL**（实测 **3 PASS / 2 FAIL**）⇒ 改按**多重集**比 '
             '＋ 拆出 docstring（散文会合法演进）＋ 加 ⑦⑧ 两组判据自检 ⇒ 改后 **5 PASS / 0 FAIL** '
             '＋ 真实产物负向测试 **5/5** ② CUDA 路线「回落预设」**不换参考音频** ⇒ '
             '边车里仍是上一人的克隆音频 ⇒ **串音** ⇒ 4 个回落出口**收敛到共用出口** ⇒ `app226` **10/0** '
             '（含反证：改回旧行为必 FAIL）③ `app215` 的 2 处判据被重构波及（反证锚点缩进 ＋ '
             '①b 作用域：`ast.walk(If)` 会遍历 `else` 分支）⇒ **语义不变地**跟着走 '
             '⇒ 回归 `app215` **29/0**、`app220` **39/0**、`app219` **13/0**（与 §129 逐字一致）'
             '＋ ⛔ **设备级实测仍未跑**（本轮定位到干扰源 = **ASR 持锁跑 D1**；'
             '用户 v2.1 会话实测 **0.000 s/10 s** ⇒ 不干扰）\n')
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
    if '§130' not in after:
        print('!! §130 未写入 ⇒ 中止')
        return 6
    print('写后复核通过：%d B / %d 行；§129 标题仍在；§130 已追加'
          % (b, lines))
    print('归档 SHA256 = %s' % hashlib.sha256(
        open(ARCHIVE, 'rb').read()).hexdigest())
    print('STATUS SHA256 = %s' % hashlib.sha256(
        open(STATUS, 'rb').read()).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
