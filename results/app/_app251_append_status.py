#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_append_status.py —— §251：把 STATUS_APP.md 的 §251 段**追加**进去。

🔴 **为什么必须字节层重建（不能用 Edit）**
   `status/app/STATUS_APP.md` 是**混合行尾**（实测 75 CRLF + 43 LF-only）
   ⇒ `Edit` 工具会**规整行尾**（§236 坑⑥ 已踩过）⇒ 会造成**大面积无关 diff**
   ⇒ 本脚本用 `newline=''` 做**纯字节追加**，**一个既有字节都不动**。

🔴 **追加内容**
   ① 尾部追加 `## §251 …` 一节（**指针行**：正文全文在 companion 文件里）
      —— 因为 STATUS_APP.md 本体已 **39 773 B**（限额 40 000 B，§9 触顶处置口径）
      ⇒ 正文放 companion，活文档只留指针行（与 §243/§244/§247/§248/§249/§250 同口径）。
   ② 更新头部 `last_ack`（**不变**，仍 APP-157）与 `更新时间`（**`Get-Date` 实测**）。
      —— 头部两行**只改这两行**，其余**逐字节不变**。

🔴 **写前不变量（内存里跑）+ 写后另起脚本复核**
   不变量：① 除「头部 2 行」与「尾部追加段」外，其余字节**逐字节相等**
            ② `last_ack` 仍含 `APP-157`
            ③ 章节数 +1
            ④ 行数上限（≤300）与字节上限（≤40 000 B）
"""
from __future__ import annotations

import datetime
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
P = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
COMPANION = 'status/app/STATUS_APP_sec251_detail_20261128.md'

#: 🔴 **实测**头部两行的**真实行尾是 LF**（不是 CRLF）⇒ 按**实测**写，不猜
HEADER_OLD = 'last_ack: APP-157（＋LOCK-002）\n更新时间: 2026-11-28 13:24\n'
HEADER_NEW_TMPL = 'last_ack: APP-157（＋LOCK-002）\n更新时间: %s\n'


def main() -> int:
    with io.open(P, 'rb') as f:
        raw = f.read()
    before = raw

    # ── 不变量①：头部两行必须是预期的那两行（**逐字节**）──
    if not raw.startswith(b'# STATUS_APP\r\n\r\n'):
        print('!! 头部结构与预期不符 ⇒ 中止')
        return 2
    if HEADER_OLD.encode('utf-8') not in raw[:400]:
        print('!! 头部 last_ack/更新时间 行与预期不符 ⇒ 中止')
        return 2

    # ── 取 `Get-Date` 等价的实测时间（本机 Python 的 now()）──
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    header_new = (HEADER_NEW_TMPL % now).encode('utf-8')

    # ── 尾部追加段（**逐字**）──
    section = (
        '## §251 六通道复核（**无新 App 纠偏**，`last_ack` 仍 **APP-157**）｜🔴 **接续死会话（TAKEOVER）** ⇒ 闭合 §251 断点｜🔴 **查出并修掉一个真缺陷**：`ext/extension/player.js` 的 **3×U+FFFD** ⇒ **阻断下一次出包**（**已进客户 `LiveCaption_MiniMVP_v1.2.1.zip`**）\r\n'
        '> 🔴 正文全文 ⇒ `status/app/STATUS_APP_sec251_detail_20261128.md`（§0 顺序、§1 六通道证据、§2 独立复核死会话的 3 处修改＋守卫＋2 个反证组、§3 守卫缺口「抽得出清单≠闸门是绿的」＋`--pkg` 实跑抓出真缺陷、§4 U+FFFD 根因（EXT `9bd09dd`）＋复原依据＋独立复核 **10/10**＋EXT `4868a29` 已推、§5 **系统性缺口：MiniMVP 出包线无内部素材闸门 ⇒ 乱码直接进了客户 zip**、§6 未做/待办、§7 纪律、§8 收尾指纹）\r\n'
    ).encode('utf-8')

    # ── 组装新内容 ──
    h_old_b = HEADER_OLD.encode('utf-8')
    h_new_b = header_new
    off = raw.find(h_old_b)
    assert off >= 0, '头部行未找到'
    prefix = raw[:off]                       # '# STATUS_APP\r\n\r\n'
    body_old = raw[off + len(h_old_b):]       # 头部之后的**全部**正文
    new = prefix + h_new_b + body_old + section
    assert new != raw, '头部替换没生效'

    # ── 写前不变量（内存里）──
    # ① 除头部 2 行 + 尾部追加段外，其余逐字节相等
    body_new = new[len(prefix) + len(h_new_b):len(new) - len(section)]
    assert body_old == body_new, '正文被意外改动'
    assert new.endswith(section), '追加段不在尾部'
    # ② last_ack 仍含 APP-157
    assert b'last_ack: APP-157' in new, 'last_ack 被改错'
    # ③ 章节数 +1
    n_old = raw.count(b'\n## \xc2\xa7')
    n_new = new.count(b'\n## \xc2\xa7')
    assert n_new == n_old + 1, '章节数增量异常'
    # ④ 限额
    n_lines = new.count(b'\n')
    assert len(new) <= 40000, '超过 40 000 B 限额：%d' % len(new)
    assert n_lines <= 300, '超过 300 行限额：%d' % n_lines
    print('写前不变量 6/6 PASS：正文逐字节不变 / last_ack 不变 / 章节 +1 / '
          'bytes=%d(≤40000) / lines=%d(≤300)' % (len(new), n_lines))

    # ── 原子落盘（**只追加 + 改头部 2 行**）──
    tmp = P + '.tmp_app251'
    with io.open(tmp, 'wb') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, P)

    print('已写入：%d B → %d B（+%d）' % (len(before), len(new), len(new) - len(before)))
    print('更新时间 → %s' % now)
    return 0


if __name__ == '__main__':
    sys.exit(main())
