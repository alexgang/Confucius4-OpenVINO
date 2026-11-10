# -*- coding: utf-8 -*-
"""写后**独立复核**：§169 落盘结果（不看写脚本的自我报告，直接比磁盘）。

口径：
1. `status/app/STATUS_APP.md` 头部 4 行正确（last_ack / 更新时间 / 当前任务 / 阻塞行未变）；
2. §168 正文**整块逐字**在归档件里（**字节级**比对，不是字符级 —— 中文 1 字符 = 3 字节）；
3. 旧章节标题**一个没少**（18/18）；
4. 活文档里 §168 只剩替身（正文已不在活文档）；
5. §169 新章节在文件末尾；
6. 行尾 LF、≤40 KB / ≤300 行；
7. `CORRECTIONS_APP.md` **未被本轮改动**（只读）。
"""
import hashlib
import os
import re
import subprocess
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCH = os.path.join(REPO, 'status', 'archive', 'STATUS_APP_sec168_20261110.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')

OPEN_SHA = '36af1620d7ee867c5d8d7ac7d6e60bd3a63218f09dc0343e787ee8e0246137a2'
OPEN_BYTES = 285671
OPEN_ENTRIES = 97

checks = []


def chk(name, ok, detail):
    checks.append((name, bool(ok), detail))


def main():
    cur = open(STATUS, 'rb').read()
    arc = open(ARCH, 'rb').read()
    head = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:status/app/STATUS_APP.md'],
                          capture_output=True, check=True).stdout

    txt = cur.decode('utf-8')
    lines = txt.split('\n')

    chk('header_last_ack', lines[2] == 'last_ack: APP-097', repr(lines[2]))
    chk('header_timestamp', lines[3].startswith('更新时间: 2026-11-10 '), repr(lines[3]))
    chk('header_task_mentions_169', '§169' in lines[4], lines[4][:60] + '…')
    head_lines = head.decode('utf-8').split('\n')
    chk('header_block_line_unchanged', lines[5] == head_lines[5],
        '阻塞行与 HEAD 逐字一致（未新增门控项）')

    # ② §168 正文整块逐字（字节级）
    i = head.find('\n## §168 '.encode('utf-8')) + 1
    blk = head[i:]
    chk('sec168_archive_verbatim_bytes', blk == arc,
        'HEAD 中 §168 正文块 %d B == 归档件 %d B ⇒ %s' % (len(blk), len(arc), blk == arc))

    # ③ 旧章节标题一个没少
    titles = [l for l in head.decode('utf-8').split('\n') if l.startswith('## ')]
    missing = [x for x in titles if x not in txt]
    chk('old_section_titles_all_preserved', not missing,
        '%d/%d 保留' % (len(titles) - len(missing), len(titles)))

    # ④ §168 正文已不在活文档（只剩替身）
    chk('sec168_body_not_inline', blk.decode('utf-8') not in txt,
        '活文档只保留 §168 标题行 + 归档指针')

    # ⑤ §169 在末尾
    chk('sec169_appended_at_end',
        txt.rstrip('\n').endswith('**未打包 v2.5、未通知用户、未调 MiniMax、未改任何默认值**。'),
        '文件末尾是 §169 ⑥ 段（末句＝未打包/未通知/未调 MiniMax/未改默认值）')

    # ⑥ 限额 + 行尾
    chk('eol_lf_only', b'\r\n' not in cur, '无 CRLF')
    chk('size_limit', len(cur) <= 40000, '%d B ≤ 40000' % len(cur))
    chk('line_limit', len(lines) <= 300, '%d 行 ≤ 300' % len(lines))

    # ⑦ 纠偏文件只读
    cb = open(CORR, 'rb').read()
    csha = hashlib.sha256(cb).hexdigest()
    cent = len(re.findall(r'^## APP-\d+', cb.decode('utf-8'), re.M))
    chk('corrections_file_untouched',
        csha == OPEN_SHA and len(cb) == OPEN_BYTES and cent == OPEN_ENTRIES,
        'SHA %s… / %d B / %d 条（与开工基线一致 ⇒ 本轮未追加）'
        % (csha[:16], len(cb), cent))

    npass = sum(1 for _, ok, _ in checks if ok)
    nfail = len(checks) - npass
    for n, ok, d in checks:
        print(('  PASS ' if ok else '  FAIL '), n, '|', d)
    print('verdict:', 'PASS' if nfail == 0 else 'FAIL', npass, 'PASS /', nfail, 'FAIL')
    print('STATUS bytes=%d lines=%d' % (len(cur), len(lines)))
    return 0 if nfail == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
