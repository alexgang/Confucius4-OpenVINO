#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""§245：把 §245 指针行追加到 STATUS_APP.md（正文在 companion），并压到 ≤40 000 B / ≤300 行。

🔴 本文件是**混合行尾**（60 CRLF + 47 裸 LF）⇒ 必须**逐行保留原行尾**：
用 `splitlines(keepends=True)`，合并出来的那一行沿用**被合并首行**的行尾，追加块沿用**末行**的行尾；
再用 `difflib` 断言「只有 3 处改动（更新时间／合并指针／尾部追加）」。
"""
import difflib
import io
import os
import re
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
BAK = P + '.bak_app245'
COMPANION = 'status/app/STATUS_APP_sec245_detail_20261126.md'
LIMIT_BYTES = 40000
LIMIT_LINES = 300
NOW = time.strftime('%Y-%m-%d %H:%M')

SEC245_LINES = [
    '## §245 接续上一会话（**TAKEOVER**）｜闭合 §244 断点：**排空判据缺陷** → **三轮全 PASS** → 抽听样片 ＋ 交付面清洗（2026-11-26 20:55）｜🔴 **未打 zip、未签 ACCEPTED**（等用户一句话）｜`last_ack` 仍 **APP-151**',
    '> 🔴 **§0 断点与根因**：上一轮三轮（19:14）`gate_all_pass=false`、`drained_to_zero` 全 False、`arm_done rc=2`；`drain` 均 `elapsed=10.02 s`＋`TimeoutError`，而 `bridge.log` 同刻仍在出段（dubs 123 = n_submitted 123）⇒ 根因＝**排空工具把「一次 stats 超时」当断连** ⇒ 门禁永远过不了。🟢 **修法**：超时后继续排空（记 `drain_timeout_events`）＋**墙钟硬上限兜底**（APP-143 b ② 不破）；行为级 **5/5 PASS（含反证）**，APP-143 b 反证重跑 **4/4 PASS（43.1 s ≤ 50 s）**',
    '> 🟢 **§1 三轮重跑**（新目录 `three_arms_r245/`）：**rc=0 / lock_lost=0 / 排空 True**；dubs **123/123/170**；丢句 **0**；`n_error` **0**；撞 39 s 上限 **0**；NaN/Inf **0**；削波 **0**；最大语速 **1.7**；`synth_rtf` **0.9834/1.0408/1.0547**；排空 **84.3/116.6/177.8 s**；APP-150 §2 门禁 **3/3 PASS**',
    '> 🔴 **§2 滞后实测（必须让用户知道）**：逐句滞后 p50 **29.2/51.2/95.0 s**、p90 **100.6/166.9/274.2 s**、最坏 **160.8/224.8/337.9 s** ⇒ **明显超过** v1.1.1 说明的「1–2 min」⇒ README 中/英**已按实测改写**（`README_zh` 31 264→31 554 B、`README_en` 33 975→34 476 B）',
    '> 🟢 **§3 抽听样片**（clone 臂 `player_mix.wav`）：3 段 × 40 s，Ogg/**Opus** 16 kHz，**117 114/120 347/122 633 B**（≤1 MB）；🔴 顺带两个真缺陷：**旧脚本读 10 min 混音静默崩溃（rc=127）**、**libsndfile VORBIS 大块写爆栈**（48k 20 s／16k 40 s 崩，OPUS 正常）',
    '> 🟢 **§4 交付面**：白名单原 18 条**漏查备份文件** ⇒ 实测包里躺着 **32 个 `*.bak_*`**（含 `translator.py.bak_app151`）⇒ **只移不删**移到包外（32/32 sha256）＋白名单**补第 ⑨ 条**后重跑 **19/19 PASS**',
    '> 🔴 **本节正文全文 ⇒ `' + COMPANION + '`**（§0 断点证据、§1 修法与写前不变量、§2 逐项门禁表＋cp 自检原文、§3～§5、§6 可交付口径、§7 未完成 4 项、§8 纪律、§9 两个坑）',
]


def eol(s):
    if s.endswith('\r\n'):
        return '\r\n'
    if s.endswith('\n'):
        return '\n'
    return ''


def main():
    with io.open(P, encoding='utf-8', newline='') as fh:
        src = fh.read()
    old_bytes = len(src.encode('utf-8'))
    old_nl = src.count('\n')
    lines = src.splitlines(keepends=True)

    # ① 更新时间（只换内容，保留该行行尾）
    idx_t = [i for i, l in enumerate(lines) if l.startswith('更新时间: ')]
    assert len(idx_t) == 1, '更新时间行命中 %d' % len(idx_t)
    i = idx_t[0]
    lines[i] = '更新时间: ' + NOW + eol(lines[i])

    # ② 合并「最近更新」归档指针行（5 → 1，沿用首行行尾）
    hits = [j for j, l in enumerate(lines)
            if l.startswith('> ') and '\U0001F534' in l[:6]
            and (('最近更新」条目' in l) or ('本节 11 行较旧' in l))]
    assert len(hits) == 5, '指针行命中 %d 条（应为 5）' % len(hits)
    merged = ('> 🔴 本节较旧「最近更新」条目与历次指针行原文均已**整块逐字归档** ⇒ '
              '`status/archive/STATUS_APP_recent_updates_20261124d.md`、`…_20261125.md`、'
              '`…_20261125b.md`、`…_20261125c.md`、`…_20261126.md`'
              '（**原文一字未删、未改**；§245 起合并为**本行**）' + eol(lines[hits[0]]))

    new_lines = []
    for j, l in enumerate(lines):
        if j == hits[0]:
            new_lines.append(merged)
        elif j in hits[1:]:
            continue
        else:
            new_lines.append(l)

    # ③ 追加 §245（沿用末行行尾）
    tail_eol = eol(new_lines[-1]) or '\n'
    if not new_lines[-1].endswith('\n'):
        new_lines[-1] = new_lines[-1] + tail_eol
    for l in SEC245_LINES:
        new_lines.append(l + tail_eol)

    out = ''.join(new_lines)
    new_bytes = len(out.encode('utf-8'))
    new_nl = out.count('\n')

    # ③b 行尾账：删掉的行有 CRLF 的要减，合并行与追加块按各自行尾加
    crlf_expect = src.count('\r\n')
    crlf_expect -= sum(1 for j in hits[1:] if eol(lines[j]) == '\r\n')
    crlf_expect += 1 if eol(merged) == '\r\n' else 0
    crlf_expect += sum(1 for _l in SEC245_LINES if tail_eol == '\r\n')

    # ④ 差异只允许 3 处：更新时间 / 指针合并 / 尾部追加
    a = src.splitlines(keepends=True)
    b = out.splitlines(keepends=True)
    ops = [op for op in difflib.SequenceMatcher(None, a, b).get_opcodes()
           if op[0] != 'equal']

    inv = [
        ('差异块数 = 3（实际 %d）' % len(ops), len(ops) == 3),
        ('last_ack 仍 APP-151',
         re.search(r'^last_ack: APP-151\r?$', out, re.M) is not None),
        ('§245 只出现 1 次', out.count('## §245 ') == 1),
        ('companion 指针在位', COMPANION in out),
        ('字节 ≤ %d（实际 %d）' % (LIMIT_BYTES, new_bytes), new_bytes <= LIMIT_BYTES),
        ('行数 ≤ %d（实际 %d）' % (LIMIT_LINES, new_nl), new_nl <= LIMIT_LINES),
        ('§244 指针行仍在', '## §244 执行 **APP-149 / APP-150 / APP-151**' in out),
        ('CRLF 计数符合逐行推算（%d）' % crlf_expect,
         out.count('\r\n') == crlf_expect),
    ]
    for n, ok in inv:
        print('  [%s] %s' % ('OK' if ok else 'FAIL', n))
    if not all(ok for _n, ok in inv):
        print('FAIL（写前不变量）⇒ 零改动')
        return 3

    shutil.copy2(P, BAK)
    tmp = P + '.app245.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    os.replace(tmp, P)

    with io.open(P, encoding='utf-8', newline='') as fh:
        after = fh.read()
    print('\n写后：%d -> %d B（Δ %+d），行数 %d -> %d（Δ %+d）'
          % (old_bytes, len(after.encode('utf-8')),
             len(after.encode('utf-8')) - old_bytes, old_nl,
             after.count('\n'), after.count('\n') - old_nl))
    print('备份：%s' % BAK)
    print('PASS' if after == out else 'FAIL（写后不一致）')
    return 0 if after == out else 4


if __name__ == '__main__':
    sys.exit(main())
