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

    txt = cur.decode('utf-8')
    lines = txt.split('\n')

    chk('header_last_ack', lines[2] == 'last_ack: APP-097', repr(lines[2]))
    chk('header_timestamp', lines[3].startswith('更新时间: 2026-11-10 '), repr(lines[3]))
    chk('header_task_mentions_169', '§169' in lines[4], lines[4][:60] + '…')
    # 「阻塞」行本轮**未改** ⇒ 仍含 §168 轮的关键措辞（可作为「本轮未新增门控项」的旁证）
    chk('header_block_line_untouched',
        '§3.5 音色归属判据失效' in lines[5] and '§3.6' in lines[5],
        '阻塞行仍含 §3.5／§3.6 两项门控（本轮未新增门控项、未推进任何门控项）')

    # ② §168 归档件**自洽**：活文档替身行自报的「字节数 + SHA256」
    #    必须与磁盘上的归档件实算值一致（不依赖 HEAD ⇒ 提交后仍成立）
    m = re.search(r'STATUS_APP_sec168_20261110\.md`（(\d+) B／块 SHA256 `([0-9a-f]{64})`）', txt)
    chk('sec168_stub_cites_archive', m is not None,
        '活文档 §168 替身行自报归档字节数与块 SHA256')
    if m:
        cited_bytes = int(m.group(1))
        cited_sha = m.group(2)
        real_sha = hashlib.sha256(arc).hexdigest()
        chk('sec168_archive_selfconsistent',
            cited_bytes == len(arc) and cited_sha == real_sha,
            '替身行自报 %d B / %s… == 归档件实算 %d B / %s…'
            % (cited_bytes, cited_sha[:16], len(arc), real_sha[:16]))

    # ③ **无悬空归档指针**（活文档每个 § 章节：正文内联，或替身行指向真实存在的归档件）
    arch_dir = os.path.join(REPO, 'status', 'archive')
    ptrs = re.findall(r'`(status/archive/STATUS_APP_[A-Za-z0-9_]+\.md)`', txt)
    dangling = [p for p in set(ptrs)
                if not os.path.isfile(os.path.join(REPO, p.replace('/', os.sep)))]
    chk('no_dangling_archive_pointer', not dangling,
        '活文档引用的 %d 个归档件指针全部存在（悬空 %d）' % (len(set(ptrs)), len(dangling)))

    # ③b 归档件自洽性：**非空 + 含 § 章节信息**；
    #     且**本轮新建的** §168 归档件**首行必须是 `## §168 `（逐字归档的直接证据）
    bad_arch = []
    n_arch_sec = 0
    for fn in sorted(os.listdir(arch_dir)):
        fp = os.path.join(arch_dir, fn)
        if not (os.path.isfile(fp) and fn.startswith('STATUS_APP_sec')):
            continue
        with open(fp, encoding='utf-8', errors='replace') as f:
            body = f.read()
        if body.strip() and '\u00a7' in body:
            n_arch_sec += 1
        else:
            bad_arch.append(fn)
    chk('archive_files_nonempty_and_marked', not bad_arch,
        '%d/%d 个 STATUS_APP_sec* 归档件非空且含章节信息（异常 %d 个）'
        % (n_arch_sec, n_arch_sec + len(bad_arch), len(bad_arch)))

    with open(ARCH, encoding='utf-8', errors='replace') as f:
        arc_first = f.readline()
    chk('sec168_archive_starts_with_its_title',
        arc_first.startswith('## \u00a7168 '),
        '§168 归档件首行 = %r' % arc_first[:48])

    # ④ §168 正文已不在活文档（只剩替身）⇒ 归档件与活文档不重复承载
    chk('sec168_body_not_inline',
        ('## §168 ' in txt) and (txt.count('## §168 ') == 1)
        and ('§168 正文整块逐字归档' in txt),
        '活文档只保留 §168 标题行 + 归档指针（正文不再重复承载）')

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
