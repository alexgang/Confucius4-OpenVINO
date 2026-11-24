#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-232 轮：把 §232 写进 `status/app/STATUS_APP.md`（**只追加，不回改旧章节**）。

## 本脚本做什么（三处改动，全部在**内存新文本**上做，再原子落盘）

1. **头部 `更新时间` 一行** ⇒ 换成 `Get-Date` 实测值（🔴 **只取一次**；写后复核再取一次
   ⇒ 跨秒 ⇒ 还原式复核**必然假 FAIL** ⇒ 本脚本把实测值**存进模块变量**，
   写后复核**复用同一个值**）。
2. **「最近更新」块首插入新条目**（旧条目**下移未删**）。
3. **文末追加 `## §232 …` 标题行 ＋ 1 行指针**（正文全文在 companion）。

## 🔴 纪律

- 🔴 **定点写入三件套**：备份 → 写前内存真不变量 ＋ **还原式复核** → 临时文件 → `os.replace`
  ⇒ 写后**另起脚本**独立复核。
- 🔴 **本文件是「混合行尾」**（头部与 §228–§231 用 LF、更早各节用 CRLF）
  ⇒ 🔴 **不可断言「全文无孤立 LF」** ⇒ 新增行**按所在区域既有行尾**写入。
- 🔴 **`last_ack` 不变**（本轮无新纠偏 ⇒ 值仍 APP-133）⇒ **只改「更新时间」这一行**。
- 🔴 **不碰** `status/app/CORRECTIONS_APP.md`（reviewer 独占、只读）。
"""
from __future__ import annotations

import datetime
import hashlib
import io
import os
import shutil
import sys

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
STATUS = os.path.join(REPO, 'status', 'app', 'STATUS_APP.md')
TMP = os.environ.get('TEMP', r'C:\Users\Trekker-PTL\AppData\Local\Temp')

# 🔴 **Get-Date 只取一次**（写后复核再取一次 ⇒ 跨秒 ⇒ 还原式复核必然假 FAIL）
NOW = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

OLD_TS = '2026-11-24 20:27:19'
NEW_TS = NOW

    # ── §232 的「最近更新」条目（插到「最近更新」块首）──
# 🔴 **行尾按所在区域既有风格写入**（实测：头部「最近更新」块首的旧条目＝**LF**，
#    §228–§231 各节＝**LF**；只有 §13 之前的早期节是 CRLF）⇒ **新增行一律 LF**。
RU_NEW = (
    '> 🔴 ' + NOW + ' ｜ **待命轮：六通道复核 ⇒ 仍无新 App 纠偏**（本地 max APP-133 ＝ '
    'QQ max APP-133 ＝ `last_ack` ⇒ **`last_ack` 仍 APP-133**）｜🟢 **修掉 `MEMORY.md` '
    '超上限导致「注入被截断」**：开工实测 **9 915 字符 > 自声明上限 9 700** ⇒ 会话注入时'
    '尾部判据被截断（§十三 目标机那段只剩一半）⇒ **只压从句、不删判据** ⇒ **9 652 字符**'
    '（余 48）｜🔴 **根因＝该文件跨模块共享**：TTS 模块 21:13 的写入把它顶到 9 915 ⇒ '
    '**已在头部加护栏「谁写完必重跑上限断言」**｜🟢 **独立行为级复核 PASS ＋ 反证组**'
    '（旧版喂同一批检查 ⇒ FAIL 6 条 ⇒ 判据能识破旧状态、非恒 PASS）｜🟢 **未打包·未改客户包·'
    '未跑推理·未取机器锁·未改 `CORRECTIONS_APP.md`**（收尾四项指纹逐字一致）｜⏭ 等 reviewer 复核 §230/§231/§232。\n'
)

# ── §232 标题行 ＋ 指针行（追加在**文末**）──
SEC232 = (
    '## §232 待命轮（**六通道复核 ⇒ 无新 App 纠偏**，`last_ack` 仍 **APP-133**）｜🟢 '
    '**修掉 `MEMORY.md` 超上限导致「注入被截断」**（9 915 → 9 652 字符；根因＝跨模块共享'
    '＋TTS 模块 21:13 写入顶破上限；只压从句不删判据；独立复核 PASS ＋ 反证组）\n'
    '> 🔴 **本节正文全文 ⇒ `status/app/STATUS_APP_sec232_detail_20261124.md`**（含 §1 本轮性质'
    '与「写 §N 的依据」、§2 六通道逐通道证据表、§3 缺陷根因（跨模块共享＋上限断言归属）、'
    '§4 修法与 8 条写前真不变量、§5 新增护栏原文、§6 独立复核（48 条关键事实＋否定式表述'
    '逐条在位＋**反证组**）与证据 json、§7 纪律自查＋`CORRECTIONS_APP.md` 收尾四项指纹、§8 下一轮）\n'
)


def read_bytes(p):
    with open(p, 'rb') as f:
        return f.read()


def main():
    old_b = read_bytes(STATUS)
    old = old_b.decode('utf-8')
    n0 = len(old_b)

    # ① 备份
    bak = os.path.join(TMP, 'STATUS_APP.md.bak_app232')
    shutil.copy2(STATUS, bak)
    assert os.path.getsize(bak) == n0, '备份大小不一致'

    # ② 头部「更新时间」**只改这一行**（`last_ack` 行不动）
    ts_line_old = '更新时间: ' + OLD_TS
    ts_line_new = '更新时间: ' + NEW_TS
    assert old.count(ts_line_old) == 1, '更新时间行命中数 != 1'
    new = old.replace(ts_line_old, ts_line_new, 1)

    # ③ 「最近更新」块首插入（**旧条目下移未删**）
    anchor = '## 最近更新\r\n'
    assert new.count(anchor) == 1, '「最近更新」标题命中数 != 1'
    i = new.index(anchor) + len(anchor)
    new = new[:i] + RU_NEW + new[i:]

    # ④ 文末追加 §232（**该区域既有行尾 = LF**，见实测：§228–§231 各节均为 LF）
    assert new.endswith('\n'), '文末行尾结构与预期不符'
    new = new + SEC232

    # ⑤ 写前真不变量（在**内存新文本**上跑）
    assert new.count('last_ack: APP-133') == 1, 'last_ack 行数变了'
    assert new.count(ts_line_old) == 0, '旧更新时间仍在'
    assert new.count(ts_line_new) == 1, '新更新时间不唯一'
    assert new.count('## §232 ') == 1, '§232 标题不唯一'
    assert new.count('## §231 ') == 1, '§231 标题丢了'
    # 旧正文逐字未变：把新文本的改动**反向还原** ⇒ 必须逐字节等于原文
    restored = new.replace(SEC232, '', 1)
    restored = restored.replace(RU_NEW, '', 1)
    restored = restored.replace(ts_line_new, ts_line_old, 1)
    assert restored == old, '还原式复核失败 ⇒ 零改动'
    assert restored.encode('utf-8') == old_b, '还原式复核（字节）失败 ⇒ 零改动'
    # 行尾风格不变：🔴 **新增行一律 LF**（实测：目标区域既有行尾＝LF）
    #    ⇒ **CRLF 数必须完全不变**；孤立 LF 数 +3（1 条最近更新 ＋ 2 行 §232）
    assert new.count('\r\n') == old.count('\r\n'), 'CRLF 数变了 ⇒ 零改动'
    assert (new.count('\n') - new.count('\r\n')) == \
        (old.count('\n') - old.count('\r\n')) + 3, '孤立 LF 数增量不对 ⇒ 零改动'
    # 限额（APP-052④）
    assert len(new.encode('utf-8')) <= 40000, '超过 40 000 B 限额 ⇒ 零改动'
    assert len(new.split('\n')) <= 300, '超过 300 行限额 ⇒ 零改动'

    # ⑥ 临时文件 → os.replace
    tmp = STATUS + '.tmp_app232'
    with open(tmp, 'wb') as f:
        f.write(new.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    assert os.path.getsize(tmp) > 0, '临时文件 0 B'
    os.replace(tmp, STATUS)

    print('STATUS_APP.md: %d → %d B（+%d）／行数 %d' % (
        n0, len(new.encode('utf-8')), len(new.encode('utf-8')) - n0,
        len(new.split('\n'))))
    print('更新时间: %s → %s' % (OLD_TS, NEW_TS))
    print('SHA256(new)=%s' % hashlib.sha256(new.encode('utf-8')).hexdigest())
    print('备份: %s' % bak)
    return 0


if __name__ == '__main__':
    sys.exit(main())
