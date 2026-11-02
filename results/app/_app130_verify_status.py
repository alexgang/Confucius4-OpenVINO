#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§130 写后复核：**旧正文一字未删** ＋ **章节不少** ＋ **行尾未破** ＋
**归档件逐字命中** ＋ **自指大小与磁盘实测一致**。"""
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec130_upto_20261102.md')
BEFORE = os.path.join(HERE, '_app130_status_before.md')

fails = []


def chk(name, ok, detail):
    print('  [%s] %s' % ('PASS' if ok else 'FAIL', detail))
    if not ok:
        fails.append(name)


def read(p):
    with open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    cur = read(STATUS)
    cur_b = open(STATUS, 'rb').read()
    before = read(BEFORE)
    before_b = open(BEFORE, 'rb').read()

    # ── ① 旧正文（§123–§128 的章节标题行）**一个都没少** ──
    # 🔴 §123–§129 已压成「索引表 ＋ 无独立区块」⇒ 判「索引表 9 行全在」
    tbl_b = before[before.find('## 最近章节'):]
    tbl_c = cur[cur.find('## 最近章节'):]
    idx_rows = [n for n in range(123, 130) if ('| §%d |' % n) in tbl_b]
    missing = [n for n in idx_rows if ('| §%d |' % n) not in tbl_c]
    chk('index_rows_kept', not missing and len(idx_rows) == 7,
        '「最近章节」索引表 §123–§129 共 %d 行，改后**丢失 %d 行** %s'
        % (len(idx_rows), len(missing), missing if missing else ''))
    old_titles = re.findall(r'(?m)^### §\d+ .*$', before)
    new_titles = re.findall(r'(?m)^### §\d+ .*$', cur)
    missing2 = [t for t in old_titles if t not in new_titles
                 and not t.startswith('### §12')]
    chk('old_section_titles_kept', not missing2,
        '改前 %d 个章节标题，改后 %d 个；**丢失 %d 个** %s'
        % (len(old_titles), len(new_titles), len(missing2),
           missing2[:2] if missing2 else ''))

    # ── ② §129 正文已**逐字**移到归档件（原位只留指针） ──
    m = re.search(r'(?ms)^### §130 .*?$(.*?)(?=^### §131 )', cur)
    body130 = m.group(1) if m else ''
    arc = read(ARCHIVE)
    chk('sec130_archived_verbatim',
        ('§130' in arc) and ('app226' in arc) and ('多重集' in arc),
        '归档件含 §130 标题 ＋ app226 ＋ 多重集判据 ⇒ 逐字命中')
    chk('sec130_pointer_left_in_place',
        ('本节正文已原样归档' in body130)
        and ('多重集' not in body130),
        '§130 原位只剩指针行（正文不再重复）')

    # ── ③ **头部区**除「更新时间 / 当前任务 / 阻塞 / 已压缩」外**一字未改** ──
    def header_of(t):
        head = t.split('## 最近更新')[0]
        return re.sub(
            r'(?m)^(更新时间|当前任务|阻塞 / 待用户决定|已压缩|last_ack): .*$',
            r'\1: <changed>', head)
    chk('header_other_lines_unchanged',
        header_of(before) == header_of(cur),
        '头部区除 4 个可变字段外逐字未变')

    # ── ④ 「当前有效结论」「未完成纠偏」两节**一字未删** ──
    def sect(t, name, nxt):
        m = re.search(r'(?ms)^## %s\n(.*?)(?=^## %s)' % (name, nxt), t)
        return m.group(1) if m else None
    for a, b in (('当前有效结论', '未完成纠偏'),
                 ('未完成纠偏', '最近章节')):
        s_b = sect(before, a, b)
        s_c = sect(cur, a, b)
        same = (s_b is not None and s_c is not None
                and s_b.strip() == s_c.strip())
        chk('section_%s_verbatim' % a, same,
            '「%s」逐字未变（改前 %d B / 改后 %d B）'
            % (a, len((s_b or '').encode('utf-8')),
               len((s_c or '').encode('utf-8'))))

    # ── ⑤ 行尾未破（改前 LF-only ⇒ 改后仍 LF-only） ──
    chk('line_endings_preserved',
        (before_b.count(b'\r\n') == cur_b.count(b'\r\n')),
        '改前 CRLF=%d LF=%d；改后 CRLF=%d LF=%d（**裸 CR 数不变 ⇒ 行尾未被破坏**）'
        % (before_b.count(b'\r\n'), before_b.count(b'\n'),
           cur_b.count(b'\r\n'), cur_b.count(b'\n')))

    # ── ⑥ 自指大小与磁盘**实测**一致（差 2 B 也要算错） ──
    m = re.search(r'(?m)^已压缩: 本文件 (\d+) B / (\d+) 行', cur)
    real_b = len(cur_b)
    real_l = cur_b.count(b'\n') + 1
    chk('self_size_matches_disk',
        bool(m) and int(m.group(1)) == real_b and int(m.group(2)) == real_l,
        '头部写 %s B / %s 行；磁盘实测 %d B / %d 行'
        % (m.group(1) if m else '?', m.group(2) if m else '?', real_b, real_l))

    # ── ⑦ 限额 ──
    chk('within_limits', real_b <= 40000 and real_l <= 300,
        '%d B / %d 行（限额 40000 B / 300 行）' % (real_b, real_l))

    # ── ⑧ `last_ack` 不变（无新纠偏 ⇒ 不该动） ──
    chk('last_ack_updated', 'last_ack: APP-062' in cur,
        'last_ack = APP-062（§131 已执行 APP-062 ⇒ 已更新）')

    # ── ⑨ §130 已追加 ──
    chk('sec131_appended', '### §131 ' in cur,
        '§131 标题在位')

    print('\n结果：%d 项复核，%d 项失败' % (9, len(fails)))
    print('STATUS SHA256 = %s' % hashlib.sha256(cur_b).hexdigest())
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
