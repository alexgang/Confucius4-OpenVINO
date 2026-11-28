#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app251_verify_email.py —— §251：核对**已发邮件**与**入库正文**逐字节等价。

🔴 纪律（§224）：长邮件正文会截断 ⇒ 必须核「首/中/尾三地标」都命中**同一** message_id。
🔴 通道会把 PLAIN 转成 HTML（``&nbsp;`` / ``<br  />``）⇒ 核对前**反向规范化**：
   ① ``<br  />`` → ``\\n``　② ``&nbsp;`` → 空格　③ 去标签　④ HTML 实体反转义
   ⑤ 去首尾空白 ⇒ 再与入库正文比 sha256。

🔴 **输入不手抄**：已发正文由**脚本**从邮箱 API 拉取落盘（`_app251_fetch_sent.py`），
   ⇒ 避免「人工转写 ⇒ 与实发不一致」（§250 的 15 B 差教训）。
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BODY = os.path.join(HERE, 'app251_status_email_body.txt')
SENT_HTML = os.path.join(HERE, 'app251_status_email_sent.html')
OUT = os.path.join(HERE, 'app251_status_email_sent.json')

MSG_ID = 'msg_AMWQx7Mrw37UrvRdNq8yvrO9Sa-JmryY3B6XPNgdJdOh7Q'
SENT_AT = '2026-11-28T11:37:20Z'


def denorm(h):
    t = h
    t = t.replace('<br  />', '\n').replace('<br/>', '\n').replace('<br />', '\n')
    t = t.replace('&nbsp;', ' ')
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t)
    return t


def main():
    disk = io.open(BODY, encoding='utf-8').read()
    h = io.open(SENT_HTML, encoding='utf-8').read()
    t = denorm(h)
    disk_c = disk.rstrip('\r\n')
    t_c = t.rstrip('\r\n')

    sha_disk = hashlib.sha256(disk_c.encode('utf-8')).hexdigest()
    sha_sent = hashlib.sha256(t_c.encode('utf-8')).hexdigest()

    marks = {
        'head': '【0 结论】',
        'mid': '【4 🔴 系统性缺口（比单个乱码更重要）】',
        'tail': '—— App（status/app/STATUS_APP.md §251）',
    }
    mk = {k: (v in t_c) for k, v in marks.items()}

    res = {
        'script': '_app251_verify_email.py',
        'message_id': MSG_ID,
        'sent_at': SENT_AT,
        'bytes_disk': len(disk.encode('utf-8')),
        'bytes_disk_compared': len(disk_c.encode('utf-8')),
        'sha256_disk': sha_disk,
        'bytes_sent_normalized': len(t_c.encode('utf-8')),
        'sha256_sent_normalized': sha_sent,
        'identical_after_denorm': sha_disk == sha_sent,
        'landmarks': mk,
        'all_landmarks_hit': all(mk.values()),
        'truncated': not all(mk.values()),
    }
    with io.open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for k, v in res.items():
        print('  %-26s %s' % (k, v))
    ok = res['identical_after_denorm'] and res['all_landmarks_hit']
    print('总判定：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
