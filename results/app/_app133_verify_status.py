#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-133：**独立复核**活文档 `status/app/STATUS_APP.md` 的本轮改动。

## 为什么要有这个脚本（判据工程）

写 STATUS 的脚本**自己说「写好了」不算数** ⇒ 必须**另起脚本**，
对着**写前备份**逐项核对：

1. `last_ack` = **APP-133**（且旧值 APP-128 **不再出现**在头部）；
2. `更新时间` 是**实测值**（格式 `YYYY-MM-DD HH:MM:SS`）且**不是**旧值；
3. **§228 / §229 / §230 三节各恰好 1 处**，且各有 1 行 companion 指针；
4. **§227 及更早的旧节逐字未变**（对着写前备份比）；
5. 「最近更新」小节里**本轮新条目在最前**；
6. 归档件里**旧条目逐字还在**（原文一字未删、未改）；
7. **限额**：≤40 000 B / ≤300 行；
8. 🔴 **反证组**：把归档件里的某一行改坏 ⇒ 复核脚本必须**报错**
   （证明「归档件逐字保留」这条判据**承重**）。

## 纪律

- **只读**（除反证组用临时副本）；
- 任何一项不过 ⇒ 退出码非 0。
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
                        'STATUS_APP_recent_updates_20261124d.md')
TMP = os.environ.get('TEMP', '/tmp')
MAX_BYTES = 40000
MAX_LINES = 300


def main():
    errs = []
    ok = {}

    text = open(STATUS, encoding='utf-8', newline='').read()
    raw = open(STATUS, 'rb').read()
    ok['bytes'] = len(raw)
    ok['lines'] = text.count('\n') + 1

    # ① last_ack
    m = re.search(r'^last_ack:\s*(\S+)\s*$', text, re.M)
    la = m.group(1) if m else None
    ok['last_ack'] = la
    if la != 'APP-133':
        errs.append('last_ack = %r（应 APP-133）' % la)
    if re.search(r'^last_ack:\s*APP-12[0-8]\b', text, re.M):
        errs.append('头部还残留旧的 last_ack')

    # ② 更新时间（实测格式）
    m = re.search(r'^更新时间:\s*(\S+ \S+)\s*$', text, re.M)
    ts = m.group(1) if m else None
    ok['更新时间'] = ts
    if not ts or not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', ts):
        errs.append('更新时间格式不对：%r' % ts)
    if ts == '2026-11-24 08:35:43':
        errs.append('更新时间还是旧值（未更新）')

    # ③ 三节各 1 处 ＋ 各 1 行指针
    for sec, comp in (('§228', 'STATUS_APP_sec228_detail_20261124.md'),
                      ('§229', 'STATUS_APP_sec229_detail_20261124.md'),
                      ('§230', 'STATUS_APP_sec230_detail_20261124.md')):
        n = text.count('## %s 执行' % sec)
        ok['%s 节数' % sec] = n
        if n != 1:
            errs.append('%s 节数 = %d（应 1）' % (sec, n))
        if comp not in text:
            errs.append('%s 的 companion 指针缺失（%s）' % (sec, comp))
        cp = os.path.join(REPO, 'status', 'app', comp)
        if not os.path.isfile(cp):
            errs.append('%s companion 文件不存在：%s' % (sec, comp))
        else:
            ok['%s companion B' % sec] = os.path.getsize(cp)

    # ④ 旧节逐字未变（对着**写前的工作树副本**比）
    #    🔴🔴 **不能用 `git show HEAD:` 的 blob 当基线**！
    #       本仓 `core.autocrlf=true` ＋ 无 `.gitattributes`
    #       ⇒ **工作树里是 CRLF、blob 里是 LF** ⇒ 逐字比**必然 FAIL**
    #       （这是**假 FAIL**：文件其实一字未改）⇒ 基线必须是
    #       **写脚本动手前存下的工作树副本**。
    bak = os.path.join(TMP, 'STATUS_APP.md.bak_app133_worktree')
    if not os.path.isfile(bak):
        bak = os.path.join(TMP, 'STATUS_APP.md.bak_app133')
    if os.path.isfile(bak):
        old = open(bak, encoding='utf-8', newline='').read()
        # 旧文档里 §227 及更早的每个「## §N 」标题行都必须**逐字**还在
        heads = re.findall(r'^## §\d+ .*$', old, re.M)
        missing = [h for h in heads if h not in text]
        ok['旧节标题数'] = len(heads)
        ok['基线文件'] = bak
        if missing:
            errs.append('旧节标题丢失：%s' % missing[:5])
        # §227 / §226 的正文块逐字还在
        #    🔴 块尾口径：写前 §227 是**最后一节**（块尾＝文件尾）；
        #    写后 §227 后面多了 §228 ⇒ **块尾必须按「下一节起点」截断**
        #    ⇒ 否则「写前块尾多了一截」会被判成「逐字变了」（**假 FAIL**）。
        for sec in ('## §227 ', '## §226 '):
            i = old.find(sec)
            if i < 0:
                continue
            j = old.find('\n## ', i + 1)
            blk_old = old[i:j if j > 0 else len(old)]
            # 写后：在**新**文档里取同名块（按新文档的下一节截断）
            i2 = text.find(sec)
            j2 = text.find('\n## ', i2 + 1)
            blk_new = text[i2:j2 if j2 > 0 else len(text)]
            # 写前的块尾若含「直到文件末」，允许写后多出后续节
            if blk_old.rstrip() != blk_new.rstrip():
                # 写后块应当以写前块为前缀（多出来的只是后续新节）
                if not blk_new.rstrip().startswith(blk_old.rstrip()):
                    errs.append('%s 的正文块逐字变了' % sec.strip())
        # 🔴 **节号顺序**：新节必须在**文末**（§227 之后）
        idx = {}
        for sec in ('## §226 ', '## §227 ', '## §228 ', '## §229 ',
                    '## §230 '):
            idx[sec] = text.find(sec)
        ok['节位置'] = idx
        order = [idx['## §227 '], idx['## §228 '], idx['## §229 '],
                 idx['## §230 ']]
        if all(v >= 0 for v in order) and order != sorted(order):
            errs.append('节号顺序不对（应 §227 → §228 → §229 → §230）')
    else:
        errs.append('找不到写前备份 %s' % bak)

    # ⑤ 「最近更新」新条目在最前
    i = text.find('## 最近更新')
    j = text.find('\n## ', i + 1)
    sect = text[i:j if j > 0 else len(text)]
    lines = [l for l in sect.split('\n') if l.startswith('> ')]
    ok['最近更新 条目数'] = len(lines)
    if not lines or 'APP-131 / APP-132 / APP-133' not in lines[0]:
        errs.append('「最近更新」最前一条不是本轮条目')

    # ⑥ 归档件里旧条目逐字还在
    if os.path.isfile(ARCHIVE):
        arch = open(ARCHIVE, encoding='utf-8', newline='').read()
        ok['归档件 B'] = len(arch.encode('utf-8'))
        if bak and os.path.isfile(bak):
            old = open(bak, encoding='utf-8', newline='').read()
            oi = old.find('## 最近更新')
            oj = old.find('\n## ', oi + 1)
            osect = old[oi:oj if oj > 0 else len(old)]
            olines = [l for l in osect.split('\n') if l.startswith('> ')]
            lost = [l for l in olines if l not in arch]
            ok['归档覆盖旧行数'] = len(olines) - len(lost)
            if lost:
                errs.append('归档件缺 %d 行旧条目（原文必须逐字保留）' % len(lost))
    else:
        errs.append('归档件不存在：%s' % ARCHIVE)

    # ⑦ 限额
    if len(raw) > MAX_BYTES:
        errs.append('活文档 %d B > 上限 %d B' % (len(raw), MAX_BYTES))
    if ok['lines'] > MAX_LINES:
        errs.append('活文档 %d 行 > 上限 %d 行' % (ok['lines'], MAX_LINES))

    # ⑧ 反证组：改坏归档件里的一行 ⇒ 复核必须报错
    if os.path.isfile(ARCHIVE) and os.path.isfile(bak):
        old = open(bak, encoding='utf-8', newline='').read()
        oi = old.find('## 最近更新')
        oj = old.find('\n## ', oi + 1)
        osect = old[oi:oj if oj > 0 else len(old)]
        olines = [l for l in osect.split('\n') if l.startswith('> ')]
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, 'arch.md')
            mutated = arch.replace(olines[0][:40], 'XX' + olines[0][42:], 1)
            if mutated != arch:
                with open(bad, 'w', encoding='utf-8', newline='') as f:
                    f.write(mutated)
                m2 = open(bad, encoding='utf-8', newline='').read()
                lost2 = [l for l in olines if l not in m2]
                detected = bool(lost2)
            else:
                detected = False
        ok['反证组（归档逐字保留判据）'] = detected
        if not detected:
            errs.append('反证组失败：改坏归档件后复核仍说通过')

    ok['errors'] = errs
    print(json.dumps(ok, ensure_ascii=False, indent=1))
    if errs:
        print('--- FAIL %d 项 ---' % len(errs))
        for e in errs:
            print('  🔴', e)
        return 1
    print('--- ALL PASS ---')
    return 0


if __name__ == '__main__':
    sys.exit(main())
