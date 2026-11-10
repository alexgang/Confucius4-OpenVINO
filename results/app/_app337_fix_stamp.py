# -*- coding: utf-8 -*-
"""定点修正 STATUS_APP.md 中残留的 {stamp} 占位符 + §167 标题缺时间戳。

纪律：
  * 只动两处，各一处唯一命中断言；
  * 旧正文一字不删、不改（除这两处定点替换）；
  * 先写临时文件再 os.replace 原子替换；
  * 改后复核：字节/行数、头部 last_ack 未变、其余行逐字未变。
"""
import io
import os
import sys

P = 'status/app/STATUS_APP.md'
TMP = P + '.tmp_app337'


def replace_once(text, old, new, tag):
    n = text.count(old)
    if n != 1:
        raise SystemExit('[FAIL] %s: 期望唯一命中 1，实际 %d' % (tag, n))
    return text.replace(old, new, 1)


def main():
    with io.open(P, 'r', encoding='utf-8', newline='') as f:
        orig = f.read()

    stamp = '2026-11-10 15:59'
    lines_orig = orig.split('\n')

    # ① 第 11 行：> 🔴 {stamp} ｜  ==> > 🔴 2026-11-10 15:59 ｜
    t = replace_once(orig, '> \U0001F534 {stamp} ｜', '> \U0001F534 ' + stamp + ' ｜', 'stamp_placeholder')

    # ② §167 标题补时间戳（格式对齐其它章节：标题（YYYY-MM-DD HH:MM））
    old_h = ('## §167 续做 APP-093 §3 + APP-097 §2 设备验收（last_ack=APP-097）'
             '｜**§3.7 截图 PASS（含一个阻断级真缺陷的根因修复）**｜**本条需等 reviewer 复核**')
    new_h = ('## §167 续做 APP-093 §3 + APP-097 §2 设备验收（last_ack=APP-097，'
             + stamp + '）｜**§3.7 截图 PASS（含一个阻断级真缺陷的根因修复）**'
             '｜**本条需等 reviewer 复核**')
    t = replace_once(t, old_h, new_h, 'sec167_header_stamp')

    # 改后自检：除两处外逐行未变
    lines_new = t.split('\n')
    if len(lines_orig) != len(lines_new):
        raise SystemExit('[FAIL] 行数变化 %d -> %d' % (len(lines_orig), len(lines_new)))
    diff = [i + 1 for i, (a, b) in enumerate(zip(lines_orig, lines_new)) if a != b]
    if diff != [11, 148]:
        raise SystemExit('[FAIL] 变更行非预期: %r' % diff)

    with io.open(TMP, 'w', encoding='utf-8', newline='') as f:
        f.write(t)
    os.replace(TMP, P)

    with io.open(P, 'r', encoding='utf-8', newline='') as f:
        chk = f.read()
    assert '{stamp}' not in chk, '占位符仍在'
    assert 'last_ack: APP-097' in chk, 'last_ack 被改'
    assert chk.count('\n') == len(lines_new) - 1
    print('[OK] stamp=%s  bytes=%d  lines=%d  changed_lines=%r'
          % (stamp, len(chk.encode('utf-8')), len(lines_new), diff))


if __name__ == '__main__':
    main()
