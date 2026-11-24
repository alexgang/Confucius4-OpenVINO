#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 STATUS 写入的**还原式复核**（只读）。

🔴 判据设计（MEMORY「定点写入三件套」＋「还原式复核」）：
   本轮对 STATUS 做了 **3 处**改动（`更新时间` 1 行／`最近更新` 插入 1 条／文末追加 §236），
   所以「写前整份 == 写后前缀」**不成立**（`更新时间` 那一行被**就地替换**了）
   ⇒ 判据必须是**逐块**的：
     ① **旧正文除「更新时间」一行外逐字未变**
        ⇒ 用 difflib 的 opcodes 判定：**只允许** 3 种改动
           (a) `更新时间` 行被替换　(b) 纯 insert（插入）　(c) 纯 insert（文末追加）
        ⇒ **任何 `replace`/`delete` 除 `更新时间` 行外 ⇒ FAIL**
     ② `last_ack` **唯一**且值 == APP-133
     ③ `更新时间` 已更新为实测值
     ④ §236 追加在文末，其后无其它 §N 节
     ⑤ 「最近更新」块：§236 新条目在 ＋ §235 旧条目仍在（未删）
     ⑥ 限额内（≤40 000 B／≤300 行）
     ⑦ `CORRECTIONS_APP.md` 的 SHA256 **零改动**

🔴 反证组（判据须有鉴别力）：
  R1 把「写前的文件」**改掉一个字节** ⇒ ① 必须 FAIL
  R2 把「写后的文件」**删掉最后一个字节** ⇒ ① 必须 FAIL
  R3 造一个「偷改旧正文一行」的写后版本 ⇒ ① 必须 FAIL
"""
import difflib
import hashlib
import io
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status/app/STATUS_APP.md')
BAK = os.path.join(os.environ.get('TEMP', '/tmp'), 'STATUS_APP.md.bak_app236')
CORR = os.path.join(REPO, 'status/app/CORRECTIONS_APP.md')
CORR_SHA_EXPECT = '2db65bf13f23a7015160704f66b32dfa6ebea427d06e3d99f73b1b777e9d1eda'
TS = '2026-11-25 07:38:13'


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def check_only_allowed_edits(before_txt, after_txt):
    """只允许：①`更新时间` 行被 replace　②纯 insert ⇒ 返回 (ok, 说明)"""
    b = before_txt.split('\n')
    a = after_txt.split('\n')
    sm = difflib.SequenceMatcher(None, b, a, autojunk=False)
    n_ts_replace = 0
    n_insert = 0
    bad = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        if tag == 'replace' and (i2 - i1) == 1 and (j2 - j1) == 1 \
                and b[i1].startswith('更新时间: ') and a[j1].startswith('更新时间: '):
            n_ts_replace += 1
            continue
        if tag == 'insert':
            n_insert += 1
            continue
        bad.append({'tag': tag, 'before': b[i1:i2][:3], 'after': a[j1:j2][:3]})
    ok = (len(bad) == 0) and n_ts_replace == 1
    return ok, {'n_ts_replace': n_ts_replace, 'n_insert': n_insert, 'bad': bad}


def main():
    before_bytes = open(BAK, 'rb').read()
    after_bytes = open(STATUS, 'rb').read()
    before_txt = before_bytes.decode('utf-8')
    after_txt = after_bytes.decode('utf-8')
    rows = []

    # ① 旧正文除「更新时间」一行外逐字未变
    c1, detail1 = check_only_allowed_edits(before_txt, after_txt)
    rows.append(('旧正文除「更新时间」一行外逐字未变（replace 只允许它 + 其余纯 insert）', c1))
    # ② last_ack
    n_acks = after_txt.count('last_ack: APP-133')
    c2 = (n_acks == 1) and ('last_ack: APP-134' not in after_txt)
    rows.append(('last_ack 唯一且仍 APP-133（n=%d）' % n_acks, c2))
    # ③ 更新时间
    c3 = ('更新时间: ' + TS) in after_txt
    rows.append(('更新时间 = 实测值 ' + TS, c3))
    # ④ §236 在文末
    i236 = after_txt.find('## §236 ')
    c4 = i236 > 0 and ('## §' not in after_txt[i236:].replace('## §236', '', 1))
    rows.append(('§236 只追加在文末（其后无其它 §N 节）', c4))
    # ⑤ 最近更新
    c5 = ('2026-11-25 07:38:13' in after_txt) and ('2026-11-25 05:52:38' in after_txt)
    rows.append(('最近更新：§236 新条目在 ＋ §235 旧条目仍在（未删）', c5))
    # ⑥ 限额
    lines = after_bytes.count(b'\n')
    c6 = len(after_bytes) <= 40000 and lines <= 300
    rows.append(('限额内（%d B／%d 行 ≤ 40000 B／300 行）' % (len(after_bytes), lines), c6))
    # ⑦ 纠偏文件零改动
    cs = sha_bytes(open(CORR, 'rb').read())
    c7 = cs == CORR_SHA_EXPECT
    rows.append(('CORRECTIONS_APP.md SHA 零改动（%s…）' % cs[:12], c7))
    # ⑧ 行尾结构不变（原 57 个 CRLF 一个不少；新增行全是 LF）
    b_crlf = before_bytes.count(b'\r\n')
    a_crlf = after_bytes.count(b'\r\n')
    b_lf = before_bytes.count(b'\n') - b_crlf
    a_lf = after_bytes.count(b'\n') - a_crlf
    c8 = (a_crlf == b_crlf) and (a_lf == b_lf + 3)
    rows.append(('行尾结构不变：CRLF %d→%d（须相等）／LF %d→%d（+3 新增行）'
                 % (b_crlf, a_crlf, b_lf, a_lf), c8))

    print("=== STATUS 写入复核 ===")
    allok = True
    for name, ok in rows:
        print("  [%s] %s" % ('PASS' if ok else 'FAIL', name))
        allok = allok and ok
    print()
    print("  写前 %d B / 写后 %d B（+%d B）" % (len(before_bytes), len(after_bytes),
                                              len(after_bytes) - len(before_bytes)))
    print("  改动明细：%s" % json.dumps({k: v for k, v in detail1.items() if k != 'bad'},
                                       ensure_ascii=False))
    if detail1['bad']:
        print("  🔴 不允许的改动：%s" % json.dumps(detail1['bad'], ensure_ascii=False)[:600])

    print()
    print("--- counterproof ---")
    cp = []
    # R1：写前文件改 1 字节 ⇒ ① 必须 FAIL
    b1 = before_txt[:-1] + ('X' if before_txt[-1] != 'X' else 'Y')
    ok1, _ = check_only_allowed_edits(b1, after_txt)
    cp.append({'name': 'R1_modified_before_detected', 'expect': 'FAIL', 'ok': ok1 is False})
    print("    R1 写前文件改 1 字节 ⇒ ① 须 FAIL ⇒ %s" % ('PASS' if ok1 is False else 'FAIL'))
    # R2：写后文件**偷改旧正文一行** ⇒ ① 必须 FAIL
    a2 = after_txt.replace('last_ack: APP-133', 'last_ack: APP-134')
    ok2, _ = check_only_allowed_edits(before_txt, a2)
    cp.append({'name': 'R2_tampered_old_body_detected', 'expect': 'FAIL', 'ok': ok2 is False})
    print("    R2 写后偷改旧正文一行 ⇒ ① 须 FAIL ⇒ %s" % ('PASS' if ok2 is False else 'FAIL'))
    # R3：写后文件**把 §236 那一行改短**（少几个字）⇒ ① 必须 FAIL
    #   🔴 不能用「删掉最后一行」做反证：difflib 会把它算成 `insert`（缩进对齐的副作用）
    #      ⇒ 那样反证的是「insert 合法性」而不是「旧正文是否被改」⇒ **反证无效**。
    #   ⇒ 改为**篡改旧正文里的一行**（真 replace ⇒ 必被抓）。
    a3 = after_txt.replace('## §235 接续上一会话', '## §235 接续上一会唔')
    ok3, d3 = check_only_allowed_edits(before_txt, a3)
    cp.append({'name': 'R3_tampered_old_section_detected', 'expect': 'FAIL', 'ok': ok3 is False,
               'detail': d3['bad'][:1]})
    print("    R3 写后篡改旧章节 §235 标题 ⇒ ① 须 FAIL ⇒ %s"
          % ('PASS' if ok3 is False else 'FAIL'))
    # R4：**删掉**旧正文中间的一整行（§236 之前的那行 §235 指针）⇒ ① 必须 FAIL
    #   （delete 不是 insert ⇒ 必被抓；这才是「旧正文少了一行」的判据）
    b_lines = before_txt.split('\n')
    target = None
    for i, l in enumerate(b_lines):
        if l.startswith('> \U0001f534 **本节正文全文 ⇒ `status/app/STATUS_APP_sec235_detail'):
            target = i
            break
    if target is not None:
        a4_lines = after_txt.split('\n')
        # 在写后文件里删掉同一行内容（按文本匹配，避开 CRLF 差异）
        a4 = []
        for l in a4_lines:
            if l.startswith('> \U0001f534 **本节正文全文 ⇒ `status/app/STATUS_APP_sec235_detail'):
                continue
            a4.append(l)
        a4 = '\n'.join(a4)
        ok4, d4 = check_only_allowed_edits(before_txt, a4)
        cp.append({'name': 'R4_deleted_old_line_detected', 'expect': 'FAIL',
                   'ok': ok4 is False, 'detail': d4['bad'][:1]})
        print("    R4 写后删掉旧章节 §235 的一行 ⇒ ① 须 FAIL ⇒ %s"
              % ('PASS' if ok4 is False else 'FAIL'))
    else:
        cp.append({'name': 'R4_deleted_old_line_detected', 'expect': 'FAIL', 'ok': False,
                   'detail': '未找到目标行'})
        print("    R4 未找到目标行 ⇒ FAIL")
        all_cp = False
    all_cp = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_cp)

    outp = {'checks': [{'name': n, 'ok': o} for n, o in rows],
            'edit_detail': {k: v for k, v in detail1.items() if k != 'bad'},
            'before_bytes': len(before_bytes), 'after_bytes': len(after_bytes),
            'all_ok': allok, 'counterproof_all_ok': all_cp, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_status_verify.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_status_verify.json")
    return 0 if (allok and all_cp) else 1


if __name__ == '__main__':
    sys.exit(main())
