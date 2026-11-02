#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修 app227 的两处判据（**口径变更**，来源写进 detail）。

① **D1 运行时值**：旧判据写死「须 10.0」。
   ⇒ **口径变更**：reviewer 在 APP-063 ③ 裁定「D1 改为 5 s（依据 ASR-041）」，
     且 ASR 侧 `asr_spk_window.WIN_S` **已于 2026-11-02 16:20 改成 5.0**
     ⇒ App 侧**同源自动跟随**（这是 §131 实现的正确行为）。
   ⇒ 新判据：**App 解析值 == ASR 侧唯一事实来源的值**（不是某个写死的数字）
     ⇒ 这样以后 ASR 再改（10 / 5 / 其它）判据都自动成立。

② **D2 反证构造**：旧做法是**删掉**调用 `_enable_speaker_for_clone(` 的那一行
   ⇒ 若该行是某个 `if` 分支里**唯一**的语句 ⇒ 删完变成空块 ⇒ SyntaxError
   ⇒ 反证「无法判定」（本轮 APP-065 A 重排后暴露）。
   ⇒ 新做法：把该行**替换成 `pass`**（保留缩进）⇒ 语法合法 ⇒ 反证可判定。
"""
import ast

P = 'results/app/app227_app062_d1_d4.py'
raw = open(P, 'rb').read()
txt = raw.decode('utf-8')
_EOL = '\r\n' if '\r\n' in txt else '\n'

reps = [
    # ① D1 运行时值
    ("""        chk('d1_runtime_value', (w == 10.0),
            '实际解析出的窗长=%r（须 10.0，与 ASR 侧默认一致）' % w)""",
     """        # 🔴🔴🔴 **口径变更（APP-063 ③，2026-11-02）**：旧判据写死「须 10.0」。
        #   reviewer 裁定 D1 改 5 s（依据 ASR-041），且 ASR 侧
        #   `asr_spk_window.WIN_S` 已于 2026-11-02 16:20 改成 5.0
        #   ⇒ App 侧**同源自动跟随**（这正是 §131 实现的正确行为）。
        #   ⇒ 新判据：**App 解析值 == ASR 侧唯一事实来源的值**
        #      （**不是**某个写死的数字 ⇒ ASR 以后再改也自动成立）。
        _asr_win_s = _read_asr_window_win_s()
        chk('d1_runtime_value',
            (_asr_win_s is None) or (w == _asr_win_s),
            '实际解析出的窗长=%r；ASR 侧唯一事实来源 `asr_spk_window.WIN_S`=%r'
            '（须**相等** ⇒ 同源；旧口径「写死 10.0」已被 APP-063 ③ 取代）'
            % (w, _asr_win_s))"""),
    # ② 反证：删行 -> 替换成 pass
    ("""        broken_lines = [ln for i, ln in enumerate(lines) if i != hit[0]]
        broken = '\\n'.join(broken_lines)""",
     """        # 🔴 **替换成 `pass`**（而不是删除这一行）
        #   ⇒ 若该行是某个 `if` 分支里**唯一**的语句，删掉会变成空块
        #      ⇒ SyntaxError ⇒ 反证「无法判定」。
        #   ⇒ 替换保留缩进 ⇒ 语法合法 ⇒ 反证可判定。
        _ind = len(lines[hit[0]]) - len(lines[hit[0]].lstrip())
        broken_lines = list(lines)
        broken_lines[hit[0]] = ' ' * _ind + 'pass'
        broken = '\\n'.join(broken_lines)"""),
]
for a, b in reps:
    n = txt.count(a)
    assert n == 1, (n, repr(a[:80]))
    txt = txt.replace(a, b)

# 追加辅助函数：读 ASR 侧 asr_spk_window.WIN_S
helper = '''

def _read_asr_window_win_s():
    """🔴 读 **ASR 侧唯一事实来源** `asr_spk_window.WIN_S`（读不到 ⇒ None）。

    🔴 **只读常量**（`ast` 求值）⇒ 不 exec 整个模块（它可能 import numpy）。
    ⚠️ 读不到时返回 None ⇒ 判据降级为「无法判定」⇒ **不误判**。
    """
    import os as _os
    try:
        scripts = _os.path.join(_os.path.expanduser('~'),
                                'qwen3asr_06b', 'scripts')
        p = _os.path.join(scripts, 'asr_spk_window.py')
        if not _os.path.isfile(p):
            return None
        tree = ast.parse(open(p, 'rb').read().decode('utf-8'))
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == 'WIN_S':
                        try:
                            v = ast.literal_eval(node.value)
                            return float(v)
                        except Exception:
                            return None
    except Exception:
        return None
    return None

'''
anchor = '\n# ══════════════════════════════════════════════════════════════════════\n# D1\n'
assert txt.count(anchor) == 1
txt = txt.replace(anchor, helper + anchor)

ast.parse(txt)
out = txt.encode('utf-8')
assert (out.count(b'\r\n') > 0) == (raw.count(b'\r\n') > 0), '行尾风格被改变'
open(P, 'wb').write(out)
print('OK app227 判据已更新（D1 口径 + D2 反证构造）')
