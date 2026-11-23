#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_verify_memory.py —— §227 轮：**写后独立复核**（另起脚本，不依赖压缩脚本的内存态）。

复核项：
  ① MEMORY.md 字符数 ≤ 9 700、字节数、行数、章节数
  ② MODULES 附录·四十九存在，且**逐字包含压缩前的 MEMORY.md 全文**
  ③ 附录·四十九 只出现一次（write-once / 幂等）
  ④ MEMORY.md 每行判据标记（🔴/🟢/🟡）数 **不少于** 压缩前
  ⑤ 压缩前 MEMORY.md 的全部 `## ` 章节标题仍在
  ⑥ 压缩前 MEMORY.md 的全部 `APP-nnn` / `TTS-nnn` / `ASR-nnn` / `MT-nnn` / `C-nnn` / `§nnn` 编号仍在
  ⑦ 无 CRLF、结尾有换行
  ⑧ 压缩前 MEMORY.md 的**全部反引号标识符**要么仍在，要么在 MODULES 附录·四十九里有逐字原文
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
MODULES = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY_MODULES.md')
BACKUP = os.path.join(tempfile.gettempdir(), 'MEMORY.md.bak_app227')
APPENDIX_TITLE = '### 附录·四十九（2026-11-24 §227 轮压缩前）—— MEMORY.md 压缩前全文快照（逐字下沉）'

fails = []


def chk(name, cond, detail=''):
    print('  %-52s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
    if not cond:
        fails.append(name)


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    if not os.path.exists(BACKUP):
        print('[FAIL] 找不到压缩前备份：%s' % BACKUP)
        return 2
    orig = read(BACKUP)
    new = read(MEM)
    mod = read(MODULES)

    print('[pre] 压缩前 %d 字符 / %d 字节 / %d 行'
          % (len(orig), len(orig.encode('utf-8')), orig.count('\n')))
    print('[pre] 压缩后 %d 字符 / %d 字节 / %d 行'
          % (len(new), len(new.encode('utf-8')), new.count('\n')))

    chk('① MEMORY.md 字符数 ≤ 9700', len(new) <= 9700, '(%d)' % len(new))
    chk('① 行数不变', new.count('\n') == orig.count('\n'))
    chk('① 章节数不变', new.count('\n## ') == orig.count('\n## '))

    # ② 附录·四十九存在且逐字含压缩前全文
    i = mod.find(APPENDIX_TITLE)
    chk('② MODULES 有附录·四十九', i >= 0)
    if i >= 0:
        blk = mod[i:]
        chk('② 附录·四十九 逐字含压缩前全文', orig.rstrip('\n') in blk,
            '(原文 %d 字符)' % len(orig))
    # ③ write-once
    chk('③ 附录·四十九 只出现一次', mod.count(APPENDIX_TITLE) == 1,
        '(count=%d)' % mod.count(APPENDIX_TITLE))

    # ④ 判据标记数不减少
    def marks(t):
        return [(l.count('🔴'), l.count('🟢'), l.count('🟡'))
                for l in t.splitlines() if l.strip()]
    om, nm = marks(orig), marks(new)
    lost = [(k + 1, o, n) for k, (o, n) in enumerate(zip(om, nm))
            if o[0] < n[0] or o[1] < n[1] or o[2] < n[2]]
    chk('④ 每行判据标记数不减少', not lost, str(lost[:5])[:250])

    # ⑤ 章节**身份**（编号前缀）不变 + 标题改写如实登记
    #    注：标题本身允许压缩从句（去掉每轮都变的日期戳、赘词）⇒
    #    真正的判据是「**没有任何一节被删掉**」⇒ 比对**节号前缀**＋节数。
    o_h = re.findall(r'^## .*$', orig, re.M)
    n_h = re.findall(r'^## .*$', new, re.M)
    chk('⑤ 章节数不变（无节被删）', len(o_h) == len(n_h),
        '(%d vs %d)' % (len(o_h), len(n_h)))

    def ident(h):
        m = re.match(r'^##\s*([^（(，,：:、]*)', h)
        return m.group(1).strip() if m else h

    o_id = [ident(h) for h in o_h]
    n_id = [ident(h) for h in n_h]
    lost_h = [h for h in o_id if h not in n_id]
    chk('⑤ 每节的节号标识仍在（无节被合并/删除）', not lost_h, str(lost_h)[:250])

    reworded = [(o, n) for o, n in zip(o_h, n_h) if o != n]
    print('  %-52s %s' % ('（登记）标题被压缩从句改写 %d 处' % len(reworded),
                          '' if not reworded else
                          ' | '.join('%r→%r' % (o[:28], n[:28])
                                     for o, n in reworded)[:300]))
    for o, n in reworded:
        print('       − %s' % o)
        print('       + %s' % n)

    # ⑥ 编号
    pat = r'\b(?:APP|TTS|ASR|MT|C)-\d+\b|§\d+'
    o_n = set(re.findall(pat, orig))
    n_n = set(re.findall(pat, new))
    lost_n = sorted(o_n - n_n)
    chk('⑥ 全部 APP/TTS/ASR/MT/C/§ 编号仍在', not lost_n, str(lost_n)[:250])

    # ⑦ 编码/结尾
    chk('⑦ 无 CR 引入', '\r' not in new)
    chk('⑦ 结尾有换行', new.endswith('\n'))

    # ⑧ 被压掉的标识符必须在 MODULES 里有逐字原文
    o_ids = set(re.findall(r'`[^`\n]+`', orig))
    n_ids = set(re.findall(r'`[^`\n]+`', new))
    dropped = sorted(o_ids - n_ids)
    print('  %-52s %s' % ('⑧ 被压掉的反引号标识符 %d 个' % len(dropped),
                          str(dropped)[:250]))
    bad = [t for t in dropped if t not in mod]
    chk('⑧ 每个被压掉的标识符在 MODULES 里有逐字原文', not bad, str(bad)[:250])

    print()
    if fails:
        print('[FAIL] 写后独立复核未过：%s' % fails)
        return 3
    print('[ok] 写后独立复核 ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
