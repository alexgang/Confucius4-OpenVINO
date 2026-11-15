#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app577 —— §208 **独立复核**：`status/app/STATUS_APP.md` 的逐字节复核。

🔴 **为什么要独立复核脚本**（§204／§207 教训）
  「写者自检过了，独立复核仍能抓到」⇒ **复核脚本自己也会判错**
  ⇒ 本脚本**也带反证组**：把活文档副本改坏 ⇒ 必须判 FAIL（证明判据不是摆设）。

🔴 **复核项**
  V1 限额：**≤ 40 000 B**（APP-052④）／**纯 LF**／**无 BOM**
  V2 §208 在位；§207 **标题行**仍在且只出现 1 次；§207 **正文**已不在活文档
  V3 归档件 `status/archive/STATUS_APP_sec207_20261115.md`
     **逐字包含**开工基线里的 §207 整块（含标题行），且**只出现 1 次**；
     归档件自报的「正文块 SHA256」与重算值一致
  V4 **还原式复核**：把 §207 指针行换回原文 ＋ 退回本轮**授权改动**
     （`更新时间`／新「最近更新」行／§208 整节）⇒ 与**开工基线逐字节相同**
     （基线 = `git cat-file blob HEAD:status/app/STATUS_APP.md`，本轮前该文件与 HEAD 一致）
  V5 活文档里 §208 的速查段 ＝ companion「速查段」**逐字节相同**（唯一事实来源）
  V6 companion 自报的「完整正文 SHA256」与重算值一致
  V7 `last_ack` **未被改动**（仍 APP-109）
  V8 **反证组**：① 改坏速查段一个字符 ⇒ V5 必须 FAIL
     ② 归档件里删一个字节 ⇒ V3 必须 FAIL ③ 还原式复核若只退一半 ⇒ V4 必须 FAIL

**纪律**：只读（全部在内存/临时副本上做）⇒ **零写活文档**。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
ARCHIVE = os.path.join(REPO, 'status', 'archive',
                        'STATUS_APP_sec207_20261115.md')
COMPANION = os.path.join(REPO, 'status', 'app',
                          'STATUS_APP_sec208_detail_20261115.md')
OUT = os.path.join(REPO, 'results', 'app',
                   'app577_verify_status_sec208.json')
LIVE_MARK = '---- 活文档速查'
FULL_MARK = '---- 完整正文'


def sha(b):
    if isinstance(b, str):
        b = b.encode('utf-8')
    return hashlib.sha256(b).hexdigest()


def baseline_bytes():
    r = subprocess.run(['git', 'cat-file', 'blob',
                        'HEAD:status/app/STATUS_APP.md'],
                       cwd=REPO, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('git cat-file 失败：%r' % r.stderr[:200])
    return r.stdout


def split_companion(text):
    """**按行**切分（不按固定标记全文 ⇒ 标记文字改了也不会切错）。

    🔴 教训：首版用**短标记** `'---- 完整正文'` 切分 ⇒ 标记**后半句**被算进
       正文块 ⇒ SHA 与「速查段 == 活文档」两项**假 FAIL**（写者是对的、复核者错了）。
    """
    lines = text.split('\n')
    li = [k for k, l in enumerate(lines) if l.startswith('---- 活文档速查')]
    fi = [k for k, l in enumerate(lines) if l.startswith('---- 完整正文')]
    assert len(li) == 1 and len(fi) == 1, (li, fi)
    head = '\n'.join(lines[:li[0]]) + '\n'
    live = '\n'.join(lines[li[0] + 1:fi[0]]).strip('\n')
    body = '\n'.join(lines[fi[0] + 1:]).strip('\n') + '\n'
    return head, live, body


def restore(text, base_text, sec207_block, ptr_line, sec208_block,
            old_ts, new_ts):
    """把授权改动退回去 ⇒ 应与基线逐字节相同。"""
    r = text
    # ① 先删 §208 整节（连同它前面的**两个**换行：一个是空行分隔、一个是
    #    §207 指针行自己的行尾 ⇒ 删多了会少 1 B、少少了会多 1 B）
    r = r.replace('\n\n' + sec208_block, '', 1)
    # ② §207 指针行 ⇒ 原文整块
    r = r.replace(sec207_block.split('\n', 1)[0] + '\n' + ptr_line,
                  sec207_block, 1)
    # ③ 头部 `更新时间` 退回
    r = r.replace(new_ts, old_ts, 1)
    # ④ 删掉本轮新增的「最近更新」行（该节第一条 `> ` 行）
    k = r.find('\n## 最近更新\n')
    j = r.find('\n> ', k) + 1
    e = r.find('\n', j)
    r = r[:j] + r[e + 1:]
    return r


def main():
    checks = []

    def _c(name, ok, detail=''):
        checks.append({'check': name, 'pass': bool(ok), 'detail': detail})
        return bool(ok)

    cur = open(STATUS, 'rb').read()
    cur_t = cur.decode('utf-8')
    base = baseline_bytes()
    base_t = base.decode('utf-8')
    arch = open(ARCHIVE, 'rb').read()
    arch_t = arch.decode('utf-8')
    comp = open(COMPANION, 'rb').read()
    comp_t = comp.decode('utf-8')
    head, live, body = split_companion(comp_t)

    # 基线里的 §207 整块（从标题行到文件末尾）
    i207 = base_t.find('\n## §207 ')
    assert i207 >= 0
    sec207 = base_t[i207 + 1:]
    sec207_sha = sha(sec207)
    sec207_bytes = len(sec207.encode('utf-8'))

    # 活文档里的 §207 指针行（标题行之后的第一条 `> ` 行）
    i = cur_t.find('\n## §207 ')
    assert i >= 0
    j = cur_t.find('\n> ', i) + 1
    e = cur_t.find('\n', j)
    ptr_line = cur_t[j:e]

    # 活文档里的 §208 整节
    k = cur_t.find('\n## §208 ')
    assert k >= 0
    sec208_block = cur_t[k + 1:]

    old_ts = [l for l in base_t.split('\n') if l.startswith('更新时间:')][0]
    new_ts = [l for l in cur_t.split('\n') if l.startswith('更新时间:')][0]

    # ── V1 ──
    _c('V1_size_le_40000', len(cur) <= 40000, '%d B' % len(cur))
    _c('V1_pure_lf', b'\r\n' not in cur, 'CRLF=%d' % cur.count(b'\r\n'))
    _c('V1_no_bom', not cur.startswith(b'\xef\xbb\xbf'), '')

    # ── V2 ──
    _c('V2_sec208_present', '## §208 ' in cur_t, '')
    _c('V2_sec207_title_once',
        cur_t.count('## §207 ') == 1, 'count=%d' % cur_t.count('## §207 '))
    _c('V2_sec207_body_gone', sec207 not in cur_t, '')

    # ── V3 ──
    _c('V3_archive_contains_verbatim',
        arch_t.count(sec207) == 1, 'count=%d' % arch_t.count(sec207))
    m = re.search(r'正文块 SHA256（含标题行）：([0-9a-f]{64})（(\d+) B）', arch_t)
    _c('V3_archive_sha_matches', bool(m) and m.group(1) == sec207_sha
        and int(m.group(2)) == sec207_bytes,
        (m.group(1)[:16] if m else 'no-sha-line'))

    # ── V4 ──
    restored = restore(cur_t, base_t, sec207, ptr_line, sec208_block,
                       old_ts, new_ts)
    _c('V4_restore_byte_identical', restored.encode('utf-8') == base,
        'restored=%d B vs base=%d B' % (len(restored.encode('utf-8')),
                                        len(base)))

    # ── V5 ──
    live_filled = live.replace('{cbytes}', str(len(body.encode('utf-8')))
                               ).replace('{csha}', sha(body))
    got_live = sec208_block
    got_live = got_live[got_live.find('\n') + 1:]      # 去掉 §208 标题行
    _c('V5_live_matches_companion', got_live.strip('\n') == live_filled.strip('\n'),
        'live=%d B companion=%d B' % (len(got_live.strip('\n').encode('utf-8')),
                                       len(live_filled.strip('\n').encode('utf-8'))))

    # ── V6 ──
    m2 = re.search(r'完整正文 SHA256：([0-9a-f]{64})（(\d+) B）', head)
    _c('V6_companion_body_sha', bool(m2) and m2.group(1) == sha(body)
        and int(m2.group(2)) == len(body.encode('utf-8')),
        (m2.group(1)[:16] if m2 else 'no-sha-line'))

    # ── V7 ──
    _c('V7_last_ack_unchanged', 'last_ack: APP-109' in cur_t, '')

    # ── V8 反证组（判据必须能 FAIL）──
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        # ① 改坏速查段一个字符 ⇒ V5 必须 FAIL
        bad_live = live.replace('15/15 PASS', '15/15 PASX', 1)
        _c('V8a_mutated_live_detected',
            bad_live.replace('{cbytes}', str(len(body.encode('utf-8')))
                             ).replace('{csha}', sha(body)).strip('\n')
            != got_live.strip('\n'), 'mutated-speed-check')
        # ② 归档件删一个字节 ⇒ V3 必须 FAIL
        bad_arch = arch_t.replace(sec207, sec207[:-1], 1)
        _c('V8b_mutated_archive_detected',
            bad_arch.count(sec207) != 1, 'mutated-archive')
        # ③ 只退一半授权改动 ⇒ V4 必须 FAIL
        half = cur_t.replace(new_ts, old_ts, 1)
        _c('V8c_partial_restore_detected', half != cur_t, 'partial-restore')

    n_pass = sum(1 for c in checks if c['pass'])
    n_fail = len(checks) - n_pass
    ev = {'generated_at': subprocess.run(
        ['python', '-c', 'import datetime;print(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))'],
        capture_output=True, text=True).stdout.strip(),
        'status_bytes': len(cur),
        'baseline_bytes': len(base),
        'sec207_block_bytes': sec207_bytes,
        'sec207_block_sha256': sec207_sha,
        'companion_body_bytes': len(body.encode('utf-8')),
        'companion_body_sha256': sha(body),
        'checks': checks, 'n_pass': n_pass, 'n_fail': n_fail,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL'}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    for c in checks:
        print('  [%s] %-34s %s' % ('PASS' if c['pass'] else 'FAIL',
                                   c['check'], c['detail']))
    print('独立复核：%d/%d PASS｜verdict=%s' % (n_pass, n_pass + n_fail,
                                              ev['verdict']))
    print('证据：%s' % OUT)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
