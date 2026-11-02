#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""修 `app223` 判据①的**假 PASS**（MEMORY：「判据 PASS ≠ 判据正确」）。

🔴 **实测缺陷**（2026-11-02 21:0x 的设备级作业）：
   日志里出现的是 **`🔴 没有可用引擎 ⇒ spk 音色登记失败`**（`tts_worker.py:3805`）
   与 **`⚠️ 没有可用引擎 ⇒ 克隆无法生效（仍用预设 A）`**（`tts_worker.py:3763`）
   ⇒ 而判据①的正则只抓 **`没有可用的音色`**（`tts_worker` 的**另一条**故障串）
   ⇒ **抓不到真实故障** ⇒ 判据①「0 次」是**假 PASS**。

⇒ 修法：`_RE_NO_VOICE` 扩成**三条真实故障串**之一：
   ① `没有可用的音色`（原有：语音没送到边车）
   ② `没有可用引擎`（本轮实测：克隆/spk 音色登记失败 ⇒ 全程 preset）
   ③ `spk 音色登记失败`（本轮实测的精确串）

🔴 **反证**：把 ②③ 也去掉 ⇒ 判据会重新变假 PASS ⇒ 必须保留（源码里写死）。
"""
import ast

P = 'results/app/app223_app061_device_acceptance.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

a = "_RE_NO_VOICE = re.compile(r'没有可用的音色')"
b = ("# 🔴🔴🔴 APP-063 复盘（2026-11-02 21:0x）：**判据①曾是假 PASS** ——\n"
     "#   实测日志里的真实故障串是 **`没有可用引擎`**（`tts_worker.py:3763/3805`）\n"
     "#   与 **`spk 音色登记失败`**，而旧正则只抓 `没有可用的音色`\n"
     "#   （**另一条**故障：语音没送到边车）⇒ **抓不到真实故障**。\n"
     "#   ⇒ 现在三条**都**算「没有可用音色」。\n"
     "_RE_NO_VOICE = re.compile(\n"
     "    r'没有可用的音色|没有可用引擎|spk 音色登记失败')")
assert txt.count(a) == 1, txt.count(a)
txt = txt.replace(a, b)
ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK app223 判据①的正则已补全（3 条真实故障串）')
