#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""补回「最近章节」索引表里的 §131 / §132 两行。

🔴 **为什么**：写 §132 时把 §131 正文**整段归档**了（腾字节）⇒ 索引表里
   那一行也被一起删掉 ⇒ 索引与正文的对应关系断了。
   ⇒ 这里把 §131（已归档，标「已归档」）与 §132（正文在本文件里）两行**补回**。
"""
import os

P = 'status/app/STATUS_APP.md'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
EOL = '\r\n' if '\r\n' in txt else '\n'
lines = txt.split(EOL)

row131 = ('| §131 | **APP-062（D1–D4：用户对 APP-061 的四项决定）** —— 代码层全完成'
          '（D1 窗口同源配置项 / D2 自动开旁路 / D3 客户包去 CUDA / D4 禁 MT+TTS 同 NPU）'
          ' ｜ **本条需等 reviewer 复核** | 已归档 |')
row132 = ('| §132 | **APP-063/064/065**：D4 bug ＋ D2 四入口 ＋ D1 窗口（ASR 未同源⇒跨模块错位）'
          '＋ 锁纪律 ＋ **界面重排 5 组**（截图/清单已交）＋ 改名 | **本轮新增（见下）** |')

if any(l.startswith('| §132 |') for l in lines):
    print('[skip] §132 索引行已存在')
    raise SystemExit(0)

# 插到 §129 行之后（§130 的索引行本来就不在表里 —— §130 已被 §131 归档）
for i, l in enumerate(lines):
    if l.startswith('| §129 |'):
        lines.insert(i + 1, row131)
        lines.insert(i + 2, row132)
        break
else:
    print('[ABORT] 找不到 §129 索引行')
    raise SystemExit(2)

new = EOL.join(lines)
data = new.encode('utf-8')
assert len(data) <= 40000, len(data)
tmp = P + '.tmp_idx'
open(tmp, 'wb').write(data)
assert open(tmp, 'rb').read() == data
os.replace(tmp, P)
assert open(P, 'rb').read() == data
print('OK 索引表已补回 §131 / §132 两行（%d B）' % len(data))
