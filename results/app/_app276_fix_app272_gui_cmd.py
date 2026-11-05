#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-069② GUI 臂 harness 修正（§137）：只给 `--autostart` 会卡在启动早期。

实测（本轮）：
* `_app272_rc3_crash_stats.py --phase gui --n 3` 第 0 次：rc=1 / wall=420.96 s /
  `loaded=False` / `gui_00.log` 只有 1 行 transformers 提示 ⇒ **420 s 超时后被 terminate**，
  不是产品崩溃（rc≠3221226505）。
* 单次探针（PYTHONUNBUFFERED=1、90 s）：日志仍只有 1 行、进程未退出
  ⇒ **不是 stdout 块缓冲**，而是 GUI 缺音频源 ⇒ 启动后不进入模型加载流程。
* §135 的 `app259_app066_minimvp_gui_coldstart.py` L261 的真实口径：
  `--source file --file <wav> --autostart --selftest … --selftest-out …`
  ⇒ 本修正给 GUI 臂补 `--source file --file <SPE_0000_0500.wav>`。

🔴 定点替换：唯一命中断言 + ast.parse + 写后逐字节复核；CRLF 保持；旧正文不删。
"""
import ast
import os

P = r'C:/Users/Trekker-PTL/confucius4-openvino/results/app/_app272_rc3_crash_stats.py'

b = open(P, 'rb').read()
old_cmd = b"                cmd = [py, app, '--autostart']"
assert b.count(old_cmd) == 1, ('cmd 锚点', b.count(old_cmd))
old_env = b"                env['PYTHONFAULTHANDLER'] = '1'"
assert b.count(old_env) == 2, ('env 锚点（check+gui 两处）', b.count(old_env))

new_cmd = b'\r\n'.join([
    b"                # SEC137: GUI arm needs an audio source (SEC135 app259 real cmd);",
    b"                # --autostart alone stalls before model loading (420s timeout).",
    b"                wav = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')",
    b"                cmd = [py, app, '--autostart', '--source', 'file', '--file', wav]",
])
b2 = b.replace(old_cmd, new_cmd, 1)
b2 = b2.replace(old_env,
                old_env + b"\r\n                env['PYTHONUNBUFFERED'] = '1'", 2)
assert b2.count(b"env['PYTHONUNBUFFERED'] = '1'") == 2
assert b2.count(b"SPE_0000_0500.wav") == 1
ast.parse(b2.decode('utf-8'))

tmp = P + '.tmp'
with open(tmp, 'wb') as f:
    f.write(b2)
os.replace(tmp, P)
assert open(P, 'rb').read() == b2
print('OK GUI 臂 harness 修正：bytes %d -> %d（CRLF 保持，ast.parse 通过，写后复核一致）'
      % (len(b), len(b2)))
