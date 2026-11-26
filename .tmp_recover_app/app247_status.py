#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§247：STATUS 追加（先归档 §228 腾空间，再追加 §247 指针行）。

纪律（§九 / §225）：
- **逐字归档**（原文含原行尾写进 archive 件，write-once）
- 活文档只留 **1 行指针**
- 混合行尾：按被删/新增行的行尾**逐条推算** CRLF 数，写后必须等于推算值
- 其余行**逐字未变**（difflib 证明差异只在预期区间）
- 限额 ≤ 40 000 B；任何判据 FAIL ⇒ 零改动
"""
import difflib
import io
import os

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive',
                    'STATUS_APP_sec228_block_20261126.md')
COMPANION = 'status/app/STATUS_APP_sec247_detail_20261126.md'
LIMIT = 40000

SEC247 = [
    '## §247 打包（用户 22:27 放行）｜🟢 **MiniMVP v1.2 已出 zip**：'
    '`Confucius4_LiveCaption_MiniMVP_v1.2.zip` **5 309 448 161 B / 10 893 条目**'
    '（mtime 22:39:16，压缩率 77.7%≈v1.1.1）｜🟢 **ACCEPTED 已签**（version 1.2 / 34 生产模块 / '
    '聚合指纹 `d51d4d67…` / 闸门⑤ OK）｜🟢 打包前修掉包内 `EXT v0.4.22` 过时文案（4 处 → 0.4.23）'
    '｜🟢 白名单 **19/19**（签 ACCEPTED 之前跑）｜🟢 APP-148 §1a MT3 权重 3 处 hex：候选=源、'
    '与 MT2 全不同（三份字节数相同 1 792 991 738）｜🔴 **§1b 判据自身缺陷**（zip 条目带顶层前缀 '
    'vs 目录无前缀 ⇒ 10 893 全不匹配＝假 FAIL）⇒ 修判据＋反证 **6/6** ⇒ 真跑 '
    '**10 893/10 893、三项 0、CRC 全过**｜🟢 解压自检：10 893 文件 / 44.0 s，包内 python '
    '`--check` **rc=0（42.3 s，Hy-MT3-1.8B、GPU.0+NPU 可用）**，临时目录已删'
    '｜🔴 **留白**：reviewer 从 zip 复核、B 机复验（不挡发版）、APP-144 ① 脱敏、'
    'LOCK-001 取锁改法｜🟢 未连 B 机／未调 MiniMax／未改纠偏文件',
    '> 🔴 **本节正文全文 ⇒ `' + COMPANION + '`**（含 §0 顺序与理由、§1 版本矛盾修法、'
    '§2 白名单、§3 ACCEPTED、§4 六组 hex、§5 zip 参数、§6 判据缺陷＋反证组、'
    '§7 解压自检、§8 留白、§9 纪律）',
]

MERGE_HEAD = ('## §228 执行 **APP-129**（`last_ack=APP-128 → APP-129`，2026-11-24）｜'
              '全文逐字归档 ⇒ `status/archive/STATUS_APP_sec228_block_20261126.md`'
              '（bgkeep 交接 v2.6、EXT 按 commit 取、离线一致性 14/14+18/18+16/16、'
              '两轮整链、降级与样片、签 ACCEPTED、留白、事故登记）')


def eol(s):
    if s.endswith('\r\n'):
        return '\r\n'
    if s.endswith('\n'):
        return '\n'
    return ''


def main():
    raw = open(STATUS, 'rb').read()
    src = raw.decode('utf-8')
    all_lines = src.split('\n')
    body = all_lines[:-1] if all_lines and all_lines[-1] == '' else all_lines
    tail_eol = eol(src) or '\n'
    print('原：%d B / %d 行（CRLF %d，末尾 %r）'
          % (len(raw), len(body), src.count('\r\n'), tail_eol))

    hits = [i for i, l in enumerate(body) if l.startswith('## §228')]
    if len(hits) != 1:
        print('FAIL：§228 标题行命中 %d 次' % len(hits))
        return 2
    i228 = hits[0]
    if not body[i228 + 1].startswith('> 🔴 **本节正文全文'):
        print('FAIL：§228 下一行不是指针行：%r' % body[i228 + 1][:60])
        return 2

    archived = [body[i228], body[i228 + 1]]
    merged = MERGE_HEAD + eol(archived[0])

    out_lines = body[:i228] + [merged] + body[i228 + 2:]
    block = [l + tail_eol for l in SEC247]
    # 🔴 最后一行**已带原来的行尾**（混合行尾里可能只有 '\r'）⇒ 只补 '\n'，
    #    不能补 tail_eol（否则 '\r' + '\r\n' = **双 CRLF**，会让 §247 之前的末行变样）
    out = '\n'.join(out_lines) + '\n' + ''.join(block)

    # 行尾账：删掉的两行里有多少 CRLF，合并行补回几行，追加块几行
    crlf_expect = src.count('\r\n')
    crlf_expect -= sum(1 for l in archived if eol(l) == '\r\n')
    crlf_expect += 1 if eol(merged) == '\r\n' else 0
    crlf_expect += sum(1 for b in block if b.endswith('\r\n') and not b.endswith('\r\r\n'))

    # 比对时**先剥掉追加块**：这样「差异块」只反映对旧正文的改动
    out_wo_block = '\n'.join(out_lines) + '\n'
    sm = difflib.SequenceMatcher(None, body, out_wo_block.split('\n')[:-1],
                                 autojunk=False)
    ops = [op for op in sm.get_opcodes() if op[0] != 'equal']
    print('差异块 %d 个（已剥掉追加块）：%s' % (len(ops), ops))

    inv = [
        ('差异块 = 1', len(ops) == 1),
        ('追加块在文件末尾且逐字等于 SEC247',
         out.endswith(''.join(block))),
        ('差异块恰在 §228（两行→一行）',
         bool(ops) and ops[0][0] == 'replace' and ops[0][1] == i228
         and ops[0][2] == i228 + 2),
        ('CRLF 计数符合推算（%d）' % crlf_expect, out.count('\r\n') == crlf_expect),
        ('行数 = %d' % (len(body) + 1), out.count('\n') == len(body) + 1),
        ('§247 标题唯一', out.count('## §247') == 1),
        ('§228 标题仍在（指针行）', out.count('## §228') == 1),
        ('大小 ≤ %d B' % LIMIT, len(out.encode('utf-8')) <= LIMIT),
        ('§245/§246 仍在', '## §245' in out and '## §246' in out),
        ('last_ack 未动', 'last_ack: APP-151（＋LOCK-001）' in out),
        ('旧正文逐字未变（前 i228 行）', out.split('\n')[:i228] == body[:i228]),
    ]
    for n, ok in inv:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', n))
    bad = [n for n, ok in inv if not ok]
    if bad:
        print('⇒ %d 项不满足，零改动' % len(bad))
        return 1

    os.makedirs(os.path.dirname(ARCH), exist_ok=True)
    if os.path.exists(ARCH):
        print('FAIL：归档件已存在（write-once）%s' % ARCH)
        return 2
    with io.open(ARCH, 'w', encoding='utf-8', newline='') as f:
        f.write('<!-- §228 原文逐字归档（2026-11-26 §247 轮）；活文档只留指针行 -->\n')
        f.write('\n'.join(archived) + '\n')

    tmp = STATUS + '.tmp_app247'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    os.replace(tmp, STATUS)

    back = open(STATUS, 'rb').read()
    arch_back = io.open(ARCH, encoding='utf-8', newline='').read()
    post = [
        ('落盘逐字节等于预期', back == out.encode('utf-8')),
        ('归档件含 §228 原文逐字',
         archived[0] in arch_back and archived[1] in arch_back),
        ('大小 %d B ≤ %d' % (len(back), LIMIT), len(back) <= LIMIT),
        ('归档注释头在位', arch_back.startswith('<!-- §228 原文逐字归档')),
    ]
    for n, ok in post:
        print('  [%s] %s' % ('PASS' if ok else 'FAIL', n))
    print('STATUS：%d -> %d B；%d -> %d 行'
          % (len(raw), len(back), len(body), back.decode('utf-8').count('\n')))
    ok = not [n for n, o in post if not o]
    print('结论：%s' % ('OK' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
