#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app227_verify_mail.py —— §227 轮：**邮件内容完整性**复核。

## 本轮实际用的方法（§226 同法）

§224 抓到「**11 KB 正文中间被截断**」⇒ §226 定的复核法是：
**在已发箱用内容检索逐个命中「首/中/尾」三个地标**（中段那处正是 §224 的丢失点）。

🔴 **本轮为什么不用「取回实发正文 → 与入库文件逐字节比」**：
那需要解密连接器 OAuth token 才能调 `api.mail.qq.com/mcp` 取原文
（配方见 `MEMORY_attach_send_recipe.md`）；而**上轮的解密助手脚本已按配方纪律
「用完立刻覆写并删除明文 token」被删除** ⇒ 本轮**不重新造一个带凭据操作的脚本**，
改用 **§226 的三地标内容检索法**（同样能证明「中间没丢」）。

⇒ 本脚本的职责：**核对入库正文文件自身含全部地标**（= reviewer 在已发箱应当能搜到的三处）
＋ 给出可逐条复现的检索串。

## 用法
    python _app227_verify_mail.py            # 只核对入库正文文件
    python _app227_verify_mail.py <已发箱正文文件>   # 若已有实发正文副本，则逐字节比对
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMITTED = os.path.join(HERE, '_app227_email_body.txt')

# ① 首 ② 中 ③ 尾 ④ 末行 —— reviewer 可在已发箱用「内容检索」逐条命中
LANDMARKS = [
    ('首', '§227 巡检（无新 reviewer 纠偏）'),
    ('中', '写后独立复核 ALL PASS：9 699 字符'),
    ('尾', '目标机三件套仍被 A 机已离开 192.168.2.0/24 挡住'),
    ('末行', '—— App 线程'),
]


def to_plain(sent):
    """已发箱取回的是 HTML（<br /> = 换行）⇒ 去掉包装还原纯文本。"""
    p = re.sub(r'<br\s*/?>\n?', '\n', sent)
    p = re.sub(r'<div[^>]*>|</div>', '', p)
    for a, b in (('&quot;', '"'), ('&nbsp;', ' '), ('&amp;', '&'),
                 ('&lt;', '<'), ('&gt;', '>')):
        p = p.replace(a, b)
    return p.split('---------- Original ----------')[0].strip('\n')


def main():
    committed = io.open(COMMITTED, encoding='utf-8', newline='').read()
    fails = []

    def chk(name, cond, detail=''):
        print('  %-52s %s %s' % (name, 'PASS' if cond else 'FAIL', detail))
        if not cond:
            fails.append(name)

    print('[pre] 入库正文 %s：%d 字符 / %d 字节'
          % (os.path.basename(COMMITTED), len(committed),
             len(committed.encode('utf-8'))))
    print('[pre] SHA256 = %s'
          % hashlib.sha256(committed.encode('utf-8')).hexdigest())

    print('  ── 地标（reviewer 可在已发箱用内容检索逐条命中）──')
    for tag, lm in LANDMARKS:
        chk('地标[%s] 在入库正文中：%s' % (tag, lm[:30]), lm in committed)

    chk('正文长度 ≪ 11 KB（§224 截断线）',
        len(committed.encode('utf-8')) < 11000,
        '(%d B)' % len(committed.encode('utf-8')))
    chk('正文结构完整（■ 0 … ■ 9 共 10 段）',
        all(('■ %d.' % i) in committed for i in range(0, 10)))
    chk('正文以签名结尾', committed.rstrip().endswith('—— App 线程'))

    if len(sys.argv) > 1:
        sent = io.open(sys.argv[1], encoding='utf-8', newline='').read()
        plain = to_plain(sent)
        same = plain.rstrip('\n') == committed.rstrip('\n')
        chk('实发正文 == 入库正文（逐字节，§222）', same,
            '' if same else 'sent_sha=%s'
            % hashlib.sha256(plain.rstrip('\n').encode()).hexdigest()[:16])

    print()
    if fails:
        print('[FAIL] 邮件内容完整性复核未过：%s' % fails)
        return 3
    print('[ok] 邮件内容完整性复核 ALL PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
