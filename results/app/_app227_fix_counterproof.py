#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修 app227 的 D2 反证：**破坏所有** `_enable_speaker_for_clone(` 调用点。

🔴 **为什么**：APP-065 A 之后，App 侧有 **3 个**调用点
   （① 启动参数 ② `_on_tts_toggled` ③ `_on_tts_voice_changed`）。
   旧反证只破坏**第一个**命中 ⇒ `_on_tts_voice_changed` 里的调用仍在
   ⇒ 判据仍成立 ⇒ `caught=False`（反证失败）。
⇒ 新做法：把**所有**命中行替换成 `pass` ⇒ 判据必然失效 ⇒ 反证可判定。
"""
import ast

P = 'results/app/app227_app062_d1_d4.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')

a = """        _ind = len(lines[hit[0]]) - len(lines[hit[0]].lstrip())
        broken_lines = list(lines)
        broken_lines[hit[0]] = ' ' * _ind + 'pass'
        broken = '\\n'.join(broken_lines)"""
b = """        # 🔴🔴🔴 **破坏所有命中点**（APP-065 A 之后有 3 个调用点：
        #   ① 启动参数 ② `_on_tts_toggled` ③ `_on_tts_voice_changed`）
        #   ⇒ 只破坏第一个 ⇒ ③ 里的调用仍在 ⇒ 判据仍成立 ⇒ 反证失败。
        broken_lines = list(lines)
        _hits = [i for i, ln in enumerate(lines)
                 if '_enable_speaker_for_clone(' in ln
                 and 'def _enable_speaker_for_clone' not in ln]
        for _i in _hits:
            _ind = len(lines[_i]) - len(lines[_i].lstrip())
            broken_lines[_i] = ' ' * _ind + 'pass'
        broken = '\\n'.join(broken_lines)"""
assert txt.count(a) == 1, txt.count(a)
txt = txt.replace(a, b)

# 命中列表也要改成全部（用于 detail）
a2 = """        hit = [i for i, ln in enumerate(lines)
               if '_enable_speaker_for_clone(' in ln
               and 'def _enable_speaker_for_clone' not in ln]"""
b2 = """        hit = [i for i, ln in enumerate(lines)
               if '_enable_speaker_for_clone(' in ln
               and 'def _enable_speaker_for_clone' not in ln]
        # ⚠️ 可能有**多个**调用点（APP-065 A 之后 3 个）⇒ 反证要全破坏"""
assert txt.count(a2) == 1
txt = txt.replace(a2, b2)

a3 = """        chk('d2_counterproof', caught,
            '把自动开启调用去掉（源码第 %d 行）⇒ 判据应 FAIL（实得 caught=%r）'
            % (hit[0] + 1, caught))"""
b3 = """        chk('d2_counterproof', caught,
            '把**全部** %d 处自动开启调用替换为 pass（源码行 %s）'
            '⇒ 判据应 FAIL（实得 caught=%r）'
            % (len(_hits), [i + 1 for i in _hits], caught))"""
assert txt.count(a3) == 1
txt = txt.replace(a3, b3)

ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0)
open(P, 'wb').write(out)
print('OK app227 D2 反证已改为破坏全部调用点')
