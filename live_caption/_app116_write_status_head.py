#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §0：开工先写 last_ack=APP-116 + 一行「最近更新」。

纪律（见项目长期记忆 §一）：
  * 只动头部（last_ack / 更新时间）＋ 只在「最近更新」块**追加**一行；
  * 旧正文**一字不删**；
  * 写盘走「临时文件 → os.replace」（open(p,'w') 先截断 ⇒ 写失败 ⇒ 0 B）；
  * 写前备份 + 写后**独立**复核（还原式：把本轮增量逆向还原后必须 == 原字节）。
"""
import os
import shutil
import sys
import time
import hashlib

STATUS = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
TS = '2026-11-20 10:29:28'          # PowerShell Get-Date 实测值

RECENT = (
    '> \U0001f534 2026-11-20 10:29 ｜ **开始执行 APP-116**'
    '（last_ack=APP-115 → **APP-116**）：'
    '用户反馈 4 条（TTS 输出设备无效／加男声预设／GUI 去掉 4 个选项）＋ 打包默认规则。'
    '§0 打包只出**完整版**下一个版本号（SpecialMVP / MiniMVP **不打**）。'
    '§1 已定位根因：GUI 反查表 `self._out_label_back` 的字典推导式**变量写反**'
    '（`{name: oid for name, oid in ...items()}` ⇒ 实际建出 id→name）'
    '⇒ 名称→id 反查**恒为 None** ⇒ `--out-device` **从未传给 worker**'
    '⇒ worker 落回系统默认设备（本机实测 `session_20261120_091149.log` 09:12:16）。'
    '本条**执行中**。\n'
)

OLD_ACK = 'last_ack: APP-115'
NEW_ACK = 'last_ack: APP-116'
OLD_TIME = '更新时间: 2026-11-20 08:19:22'
NEW_TIME = '更新时间: ' + TS
ANCHOR = '## 最近更新\n'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    orig = open(STATUS, 'rb').read()
    text = orig.decode('utf-8')

    # ── 备份（字节级）──────────────────────────────────────────────────
    bak = os.path.join(os.environ.get('TEMP', '.'),
                       'STATUS_APP.bak_app116_head_%s.md'
                       % time.strftime('%Y%m%d_%H%M%S'))
    shutil.copyfile(STATUS, bak)
    assert open(bak, 'rb').read() == orig, '备份不一致'

    # ── 唯一命中断言 ───────────────────────────────────────────────────
    assert text.count(OLD_ACK) == 1, 'last_ack 锚点不唯一: %d' % text.count(OLD_ACK)
    assert text.count(OLD_TIME) == 1, '更新时间锚点不唯一: %d' % text.count(OLD_TIME)
    assert text.count(ANCHOR) == 1, '「最近更新」锚点不唯一: %d' % text.count(ANCHOR)

    # ── 组装新文本（纯内存）──────────────────────────────────────────
    new = text.replace(OLD_ACK, NEW_ACK, 1)
    new = new.replace(OLD_TIME, NEW_TIME, 1)
    new = new.replace(ANCHOR, ANCHOR + RECENT, 1)

    # ── 写前复核（fail-closed：任一不过 ⇒ 源文件零改动）───────────────
    checks = []

    def chk(name, cond):
        checks.append((name, bool(cond)))

    # ① 还原式复核：把本轮三处增量逆向还原 ⇒ 必须逐字等于原文
    undo = new.replace(RECENT, '', 1).replace(NEW_ACK, OLD_ACK, 1) \
               .replace(NEW_TIME, OLD_TIME, 1)
    chk('还原式复核 undo == original', undo == text)
    # ② 旧正文一字未删（除头部两行 + 新增一行外）
    old_lines = text.split('\n')
    new_lines = new.split('\n')
    chk('行数 = 原 +1', len(new_lines) == len(old_lines) + 1)
    # ③ 头部两行确实变了
    chk('last_ack 已改为 APP-116', NEW_ACK in new and OLD_ACK not in new)
    chk('更新时间已改', NEW_TIME in new and OLD_TIME not in new)
    # ④ 章节数不变
    chk('## § 节数不变',
        new.count('\n## §') == text.count('\n## §'))
    chk('H2 节数不变', new.count('\n## ') == text.count('\n## '))
    # ⑤ 「最近更新」条目数 +1
    chk('最近更新条目 +1',
        new.split(ANCHOR, 1)[1].count('\n> ') == text.split(ANCHOR, 1)[1].count('\n> ') + 1)
    # ⑥ 行尾风格不变（LF-only）
    chk('CRLF 数不变', new.count('\r\n') == text.count('\r\n'))
    # ⑦ 字节数未超 40000 B（APP-052④ 限额）
    chk('字节数 < 40000', len(new.encode('utf-8')) < 40000)
    # ⑧ last_ack 唯一
    chk('last_ack 唯一', new.count('last_ack: ') == 1)

    bad = [n for n, ok in checks if not ok]
    if bad:
        print('FAIL-CLOSED：写前复核未过：', bad)
        print('源文件零改动。')
        return 2

    # ── 落盘：临时文件 → os.replace ────────────────────────────────────
    tmp = STATUS + '.tmp_app116'
    with open(tmp, 'wb') as f:
        f.write(new.encode('utf-8'))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATUS)

    # ── 写后独立复核 ───────────────────────────────────────────────────
    disk = open(STATUS, 'rb').read()
    ok = (disk == new.encode('utf-8')
          and sha(disk) != sha(orig)
          and disk.count(b'\r\n') == orig.count(b'\r\n')
          and disk.decode('utf-8').count('last_ack: ') == 1)
    print('=== APP-116 头部写入 ===')
    for n, o in checks:
        print('  [%s] %s' % ('PASS' if o else 'FAIL', n))
    print('备份      :', bak, os.path.getsize(bak), 'B')
    print('原 SHA256 :', sha(orig))
    print('新 SHA256 :', sha(disk))
    print('原字节/行:', len(orig), '/', orig.count(b'\n'))
    print('新字节/行:', len(disk), '/', disk.count(b'\n'))
    print('写后复核  :', 'PASS' if ok else 'FAIL')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
