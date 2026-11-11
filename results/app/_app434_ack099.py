# -*- coding: utf-8 -*-
"""APP-099 开工 ack：STATUS_APP.md 头部定点写入。

纪律（MEMORY 一）：
* 只动头部 last_ack / 更新时间 + 在「## 最近更新」下追加一行；
* 旧正文一字不删；章节数不减；行尾不变（无裸 CRLF）；
* 唯一命中断言 + 写后逐行复核。
"""
from __future__ import annotations
import hashlib
import json
import os
import sys

P = r'C:\Users\Trekker-PTL\confucius4-openvino\status\app\STATUS_APP.md'
EV = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\app434_ack099.json'


def main():
    ts = sys.argv[1]                      # 由 PowerShell Get-Date 实测传入
    b0 = open(P, 'rb').read()
    s0 = b0.decode('utf-8')
    lines = s0.split('\n')               # 末尾保留空串（若有）

    assert s0.count('last_ack: APP-098') == 1, 'last_ack 非唯一命中'
    old_ts = '更新时间: 2026-11-11 06:32:29'
    assert s0.count(old_ts) == 1, '更新时间行非唯一命中'
    assert b'\r' not in b0, '源文件出现 CRLF，与基线不符'
    n_head_before = sum(1 for l in lines if l.startswith('## '))

    new_row = ('> 🔴 %s ｜ **开始执行 APP-099**（reviewer 09:20 追加，纠偏文件 **99 条** / '
               'SHA `F01C5C88…` / 307 394 B / mtime 09:28:13）｜第 0 节 **5 项用户决定** ＋ '
               '第 4 节 **8 项任务** ｜**修在 dev 树、暂不打 rc8、不打 v2.5、不通知用户、'
               '做完停等复核**｜🔴 **设备作业排队**：`MACHINE_LOCK` 09:38:49 空文件（无 PID 可解析 '
               '⇒ fail-closed 视为存活）＋ ASR 租约活跃（token `9bda917a`，beat 10:11）'
               '⇒ 第 1/2 项须等锁，不抢｜本条**需等 reviewer 复核**' % ts)

    out = []
    inserted = False
    for l in lines:
        if l == 'last_ack: APP-098':
            out.append('last_ack: APP-099')
        elif l == old_ts:
            out.append('更新时间: ' + ts)
        else:
            out.append(l)
        if l == '## 最近更新':
            out.append(new_row)
            inserted = True
    assert inserted, '未找到「## 最近更新」标题'
    s1 = '\n'.join(out)
    b1 = s1.encode('utf-8')

    # 写前自检：反推回原文件（去掉新增行 + 还原两处头部）必须逐字等于原文
    rebuilt = []
    for l in out:
        if l == new_row:
            continue
        if l == 'last_ack: APP-099':
            l = 'last_ack: APP-098'
        elif l == '更新时间: ' + ts:
            l = old_ts
        rebuilt.append(l)
    assert rebuilt == lines, '写前自检失败：旧正文被改动'
    assert sum(1 for l in out if l.startswith('## ')) == n_head_before, '章节数变化'
    assert b'\r' not in b1, '写后自检失败：出现 CRLF'
    assert len(b1) <= 40000, '写前自检失败：超过 40000 B 限额'

    open(P, 'wb').write(b1)

    # 写后独立复核（重读磁盘）
    b2 = open(P, 'rb').read()
    s2 = b2.decode('utf-8')
    lines2 = s2.split('\n')
    chk = {
        'last_ack_app099': s2.count('last_ack: APP-099') == 1
                           and s2.count('last_ack: APP-098') == 0,
        'timestamp_measured': ('更新时间: ' + ts) in s2,
        'recent_update_row': s2.count(new_row) == 1,
        'old_body_verbatim': [l for l in lines2
                              if l != new_row
                              and l != 'last_ack: APP-099'
                              and l != '更新时间: ' + ts] ==
                             [l for l in lines
                              if l != 'last_ack: APP-098' and l != old_ts],
        'sections_not_reduced': sum(1 for l in lines2 if l.startswith('## ')) == n_head_before,
        'no_crlf': b'\r' not in b2,
        'within_limit': len(b2) <= 40000 and len(lines2) <= 300,
    }
    ev = {
        'task': 'APP-099 开工 ack（STATUS 头部定点写入）',
        'timestamp_source': 'PowerShell Get-Date -Format yyyy-MM-dd HH:mm:ss',
        'timestamp': ts,
        'before': {'bytes': len(b0), 'lines': len(lines),
                   'sha256': hashlib.sha256(b0).hexdigest(),
                   'sections': n_head_before, 'crlf': 0},
        'after': {'bytes': len(b2), 'lines': len(lines2),
                  'sha256': hashlib.sha256(b2).hexdigest(),
                  'sections': sum(1 for l in lines2 if l.startswith('## ')),
                  'crlf': 0},
        'checks': chk,
        'pass': all(chk.values()),
    }
    open(EV, 'w', encoding='utf-8').write(json.dumps(ev, ensure_ascii=False, indent=2))
    print(json.dumps(ev, ensure_ascii=False, indent=2))
    return 0 if ev['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
