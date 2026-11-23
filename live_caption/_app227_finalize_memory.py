#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_finalize_memory.py —— §227 轮：MEMORY.md 的**收尾指针更新**。

## 架构决定（重要）

**轮次状态**（§226/§227 各做了什么）属 STATUS_APP.md 的职责（已写在 §226／§227 ＋ companion
＋ 当日日志 ＋ automation memory 四处）⇒ **不在 MEMORY.md 里再抄一遍**
（抄一遍＝重复，而重复正是 MEMORY.md 超限的成因）。

**MEMORY.md 只放「换个会话不知道就会做错」的判据** ⇒ 本轮新增的可复用判据
（「压缩 MEMORY.md 时『逐条不删只压从句』怎么才算数」）的**全文**已随
**压缩前全文**一起下沉到 `MEMORY_MODULES.md` **附录·四十九**（那里无字数上限），
MEMORY.md 侧只把**指针**补进 §十二 的 MODULES 范围（三十七/四十三–四十九）。

## 本脚本只做 3 件事
  ① §十二 的 STATUS companion 指针加 `/§227`
  ② §十二 的 MODULES 范围 `四十三–四十七` → `四十三–四十九`
  ③ 等量压掉别处两处赘词 ⇒ 字符数仍 ≤ 9 700

## 不变量
  ① 字符数 ≤ 9 700 ② 行数不变 ③ 章节数不变
  ④ **每行 🔴/🟢/🟡 标记数不减少**（按行号对齐比较）
  ⑤ 全部 `APP-/TTS-/ASR-/MT-/C-/§` 编号存活
  ⑥ `MEMORY_MODULES.md` **一个字节都不动**
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MEM = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY.md')
MODULES = os.path.join(REPO, '.workbuddy', 'memory', 'MEMORY_MODULES.md')
LIMIT = 9700

# ① STATUS companion 指针加 /§227
PTR_OLD = '＋ STATUS §224/§225/§226 companion'
PTR_NEW = '＋ STATUS §224/§225/§226/§227 companion'

# ② MODULES 范围补上「四十九」
RNG_OLD = '四十三–四十七'
RNG_NEW = '四十三–四十九'

# ③ 等量压赘词（判据本身逐字保留）
TRIM = [
    ('⇒用 Write/Edit 或 Python 脚本；', '⇒用 Write/Edit/Python 脚本；'),
    ('（§224 的 11 KB 正文中间丢失⇒要补发）', '（§224 的 11 KB 中间丢失⇒要补发）'),
]


def read(p):
    with io.open(p, 'r', encoding='utf-8', newline='') as f:
        return f.read()


def main():
    orig = read(MEM)
    mod_before = open(MODULES, 'rb').read()
    print('[pre] MEMORY.md %d 字符 / %d 行' % (len(orig), orig.count('\n')))

    new = orig
    for old, rep in ((PTR_OLD, PTR_NEW), (RNG_OLD, RNG_NEW)):
        c = new.count(old)
        if c != 1:
            print('[FAIL] 锚点命中数=%d（应为 1）：%r' % (c, old[:50]))
            return 2
        new = new.replace(old, rep, 1)
    for i, (old, rep) in enumerate(TRIM, 1):
        c = new.count(old)
        if c != 1:
            print('[FAIL] trim #%d 命中数=%d（应为 1）：%r' % (i, c, old[:50]))
            return 2
        new = new.replace(old, rep, 1)

    fails = []

    def chk(name, cond, detail=''):
        print('  %-46s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
        if not cond:
            fails.append(name)

    print('[info] 新 MEMORY.md %d 字符（净 %+d）' % (len(new), len(new) - len(orig)))
    chk('字符数 ≤ 9700', len(new) <= LIMIT, '(%d)' % len(new))
    chk('行数不变', new.count('\n') == orig.count('\n'))
    chk('章节数不变', new.count('\n## ') == orig.count('\n## '))

    def marks(t):
        return [(l.count('🔴'), l.count('🟢'), l.count('🟡'))
                for l in t.split('\n') if l.strip()]
    om, nm = marks(orig), marks(new)
    lost = [(k + 1, o, n) for k, (o, n) in enumerate(zip(om, nm))
            if n[0] < o[0] or n[1] < o[1] or n[2] < o[2]]
    chk('每行判据标记数不减少', not lost, str(lost[:5])[:250])

    pat = r'\b(?:APP|TTS|ASR|MT|C)-\d+\b|§\d+'
    chk('全部编号存活', not (set(re.findall(pat, orig)) - set(re.findall(pat, new))))
    chk('无 CR 引入', '\r' not in new)
    chk('结尾有换行', new.endswith('\n'))

    if fails:
        print('[FAIL] 不变量未过：%s ⇒ 源文件零改动' % fails)
        return 3

    bak = os.path.join(tempfile.gettempdir(), 'MEMORY.md.bak_app227_final')
    shutil.copy2(MEM, bak)
    print('[info] 备份 %s' % bak)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(MEM), prefix='.app227_', suffix='.tmp')
    with io.open(fd, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, MEM)
    print('[ok] 已写盘 ⇒ %d 字符' % len(new))

    assert open(MODULES, 'rb').read() == mod_before, 'MODULES 被改动了！'
    print('[ok] MEMORY_MODULES.md 未被改动（附录·四十九 仍是那份「压缩前全文」快照）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
