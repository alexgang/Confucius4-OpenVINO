#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔴🔴🔳 **§219 写后**独立复核（另起脚本，不依赖写入脚本的任何状态）。

复核项（全部针对**磁盘上的成品**，不是内存里的新文本）：

  1. 限额：≤ 40 000 B / ≤ 300 行；
  2. 头部 `last_ack: APP-119` **唯一**、旧的 `APP-118` 已无；
  3. `## §219 执行 **APP-119**` 标题**唯一**；
  4. companion 指针（§219）存在；companion 文件在位且非空；
  5. **§218 / §216 / §217 的原文逐字**仍在各自的归档件里（且归档件里逐字命中）；
  6. **旧正文逐字未变**：把「写前备份」与「现在的活文档」逐行比，
     允许变化的只有本轮动过的那几处（头部两行 / 已压缩行 / 最近更新块 /
     §216 块 / §217 块 / 追加的 §219 块）⇒ 其余**每一行都必须原样出现**；
  7. `status/app/CORRECTIONS_APP.md` **零改动**（SHA256 逐字等于开工时的指纹）。

⇒ 任何一项 FAIL ⇒ 打印 FAIL 并 exit 1。
"""
import hashlib
import os
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
LIVE = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
CORR = os.path.join(REPO, 'status', 'app', 'CORRECTIONS_APP.md')
COMP = os.path.join(REPO, 'status', 'app', 'STATUS_APP_sec219_detail_20261121.md')
A_RU = os.path.join(REPO, 'status', 'archive',
                    'STATUS_APP_recent_updates_20261121.md')
A_216 = os.path.join(REPO, 'status', 'archive',
                     'STATUS_APP_sec216_block_20261121.md')
A_217 = os.path.join(REPO, 'status', 'archive',
                     'STATUS_APP_sec217_header_20261121.md')
BAK = os.path.join(os.environ.get('TEMP', r'C:\Windows\Temp'),
                   'STATUS_APP.bak_app219_2026-11-21_043448.md')

# 开工时（步骤 4）记录的指纹
CORR_SHA_OPEN = ('adf4d7046c9a85c9e583cc74d3d89433e8497c1f419d69b49fe9462'
                 '273f459f5')
CORR_BYTES_OPEN = 399777

res = []


def ck(name, ok, detail=''):
    res.append((name, bool(ok), detail))
    print('  %s %s%s' % ('PASS' if ok else 'FAIL', name,
                         ('  | ' + str(detail)) if detail else ''))


def rd(p):
    with open(p, 'rb') as f:
        return f.read()


def main():
    live_b = rd(LIVE)
    live = live_b.decode('utf-8')
    bak = rd(BAK).decode('utf-8')

    print('── 限额 ──')
    ck('活文档 ≤ 40 000 B', len(live_b) <= 40000, '%d B' % len(live_b))
    ck('活文档 ≤ 300 行', live.count('\n') + 1 <= 300,
       '%d 行' % (live.count('\n') + 1))

    print('── 头部 / 章节 ──')
    ck('last_ack: APP-119 唯一', live.count('last_ack: APP-119') == 1,
       live.count('last_ack: APP-119'))
    ck('旧 last_ack: APP-118 已无', live.count('last_ack: APP-118') == 0)
    ck('§219 标题唯一', live.count('## §219 执行 **APP-119**') == 1)
    ck('更新时间行唯一', live.count('更新时间: 2026-11-21 04:34:48') == 1)
    ck('companion 指针存在', live.count('STATUS_APP_sec219_detail_20261121.md')
       == 2)

    print('── 归档件逐字 ──')
    comp_b = rd(COMP)
    ck('companion 在位且非空', len(comp_b) > 1000, '%d B' % len(comp_b))
    a_ru = rd(A_RU).decode('utf-8')
    a216 = rd(A_216).decode('utf-8')
    a217 = rd(A_217).decode('utf-8')
    ck('归档「最近更新」非空', len(a_ru) > 500, '%d B' % len(a_ru))
    ck('归档 §216 块非空', len(a216) > 500, '%d B' % len(a216))
    ck('归档 §217 块非空', len(a217) > 500, '%d B' % len(a217))
    # 旧原文（写前备份里取）逐字出现在归档件里
    old_ru = [l for l in bak.split('\n')
              if l.startswith('> 🔴 2026-11-20 20:15 ｜ **巡检：6 通道全空')]
    ck('§218 最近更新原文唯一命中', len(old_ru) == 1, len(old_ru))
    if len(old_ru) == 1:
        ck('§218 最近更新原文逐字在归档件里', old_ru[0] in a_ru)
        ck('§218 最近更新原文已不在活文档', old_ru[0] not in live)
    i216 = bak.index('## §216 APP-116')
    i217 = bak.index('## §217 执行')
    i218 = bak.index('## §218 巡检')
    blk216 = bak[i216:i217]
    blk217 = bak[i217:i218]
    ck('§216 整块逐字在归档件里', blk216 in a216)
    ck('§217 标题块逐字在归档件里', blk217 in a217)
    ck('§216 整块已不在活文档', blk216 not in live)
    ck('§217 标题块已不在活文档', blk217 not in live)

    print('── 旧正文逐字未变（与写前备份逐行比）──')
    changed_ok = 0
    bad = []
    # 本轮允许变化的「块」：整块消失 ⇒ 它们的行不再要求出现
    gone_lines = set()
    for blk in (blk216, blk217):
        for ln in blk.split('\n'):
            gone_lines.add(ln)
    for ln in bak.split('\n'):
        if ln in gone_lines:
            continue
        if ln in old_ru:
            continue          # §218 最近更新条目（已被归档指针替换）
        if ln.startswith('last_ack: ') or ln.startswith('更新时间: '):
            continue          # 头部两行
        if ln.startswith('已压缩: '):
            continue          # 已压缩行（追加了 companion 指针）
        if ln == '## 最近更新':
            continue
        if ln.startswith('> 🔴 2026-11-21 04:34:48 ｜ **执行 APP-119**'):
            continue
        if live.count(ln) == 0:
            bad.append(ln[:70])
        else:
            changed_ok += 1
    ck('旧正文逐行仍在活文档里', not bad,
       'checked=%d bad=%d %s' % (changed_ok, len(bad), bad[:3]))

    print('── 纠偏文件零改动 ──')
    corr_b = rd(CORR)
    csha = hashlib.sha256(corr_b).hexdigest()
    ck('CORRECTIONS_APP.md SHA256 与开工一致', csha == CORR_SHA_OPEN, csha)
    ck('CORRECTIONS_APP.md 字节数与开工一致',
       len(corr_b) == CORR_BYTES_OPEN, '%d B' % len(corr_b))

    n_fail = sum(1 for _n, ok, _d in res if not ok)
    print('\n合计 %d 项检查，FAIL %d 项' % (len(res), n_fail))
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
