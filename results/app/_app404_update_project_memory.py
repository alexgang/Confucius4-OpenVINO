# -*- coding: utf-8 -*-
"""把本轮两条**可复用**教训追加到项目长期记忆 `.workbuddy/memory/MEMORY.md`。

🔴 只**追加**到「四、判据工程」小节末尾（不删改旧条目）。
🔴 注入预算 ≈ 9 800 字符 ⇒ 追加后须 ≤ 9 900 字符。
"""
import os

P = r'C:\Users\Trekker-PTL\confucius4-openvino\.workbuddy\memory\MEMORY.md'

ANCHOR = ('- 🔴🔴 反证构造也会坏：删行致 `if` 块空 ⇒ `SyntaxError` ⇒ 静默「无法判定」'
          '⇒ 改成把那行替换成 `pass`；多调用点须破坏全部。`ast`+`exec` 坑：丢 `Import` '
          '⇒ NameError ⇒ 假 FAIL；丢模块级常量 ⇒ 反证组没识破；反证须改「被测的那个对象」。')

ADD = ('\n- 🔴🔴 **闸门自己的判据也会是错的**（2026-11-10 实例）：给「旁路窗长」写同源闸门时，'
       '判据写成「兜底 == ASR 当前默认值」⇒ 实测 FAIL ⇒ **该判据本身错**（它会诱导把兜底 10.0 改成 '
       'ASR 默认 5.0 ⇒ 破坏与 IR 兜底 `fp16`（160000 样本 = 10 s）的配套 ⇒ 喂 5 s 却选 10 s 的 IR '
       '⇒ shape 不兼容 ⇒ **旁路静默降级、零标签**）⇒ 正确判据是「**兜底窗长 == IR 兜底窗长**」。'
       '⇒ **写闸门前先问「这条判据若被人当真去改生产代码，会不会改坏」**；并让 FAIL 分支自带反证。'
       '\n- 🔴🔴 **STATUS 引用的产物路径必须能在磁盘上定位**（APP-093 ②(d) 机械化）：'
       '归档件里的路径写错（多一个前导下划线）**数字仍全部成立** ⇒ 与 app391 那种「幻影产物」性质不同，'
       '须如实区分。`status/archive/STATUS_APP_sec*` 全部 **write-once** ⇒ 归档件里的旧笔误**不改**，'
       '在新节写明正确路径 + 数字复核；闸门：**活文档=硬闸门，归档件只登记不判 FAIL**。')

s = open(P, encoding='utf-8').read()
assert s.count(ANCHOR) == 1, 'anchor count = %d' % s.count(ANCHOR)
s = s.replace(ANCHOR, ANCHOR + ADD, 1)
assert len(s) <= 9900, '超出注入预算：%d 字符' % len(s)
open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('MEMORY.md chars =', len(s), 'bytes =', os.path.getsize(P))
