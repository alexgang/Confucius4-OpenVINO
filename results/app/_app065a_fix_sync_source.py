#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-065 A：修 `_sync_source_widgets` 的 `before=` 引用失效。

🔴 **根因**：`lbl_source_note` 已从 `_g_in_dev`（设备控件容器）**移到 ① 组的
   column 3**（避免它的 reqwidth 撑宽 column 2 ⇒ 右侧被裁）
   ⇒ `pack(..., before=self.lbl_source_note)` 指向了**另一个父容器**的控件
   ⇒ TclError: window "..." isn't packed（**每次启动必崩**！）

⇒ 修法：去掉 `before=`（`pack(side='left')` 的**调用顺序**即显示顺序，
   而本函数里各控件的 pack 调用顺序本来就是对的）。
"""
import ast

P = 'live_caption/live_caption_app.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

a = ", before=self.lbl_source_note)"
n = txt.count(a)
assert n >= 4, n
txt = txt.replace(a, ")")
# 说明：留一处注释，指出 `before=` 为何去掉
a2 = ("    def _sync_source_widgets(self):\n"
      "        kind = self._cur_source_key()")
b2 = ("    def _sync_source_widgets(self):\n"
      "        # 🔴🔴🔴 APP-065 A：设备控件**不再用** `before=self.lbl_source_note`\n"
      "        #   ⇒ 说明文字已移到 ① 组的 column 3（`before=` 跨父容器 ⇒ TclError）\n"
      "        #   ⇒ 现在靠 **pack 调用顺序**决定显示顺序（各控件互斥，无歧义）。\n"
      "        kind = self._cur_source_key()")
assert txt.count(a2) == 1, txt.count(a2)
txt = txt.replace(a2, b2)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK 去掉了 %d 处 before=self.lbl_source_note' % n)
