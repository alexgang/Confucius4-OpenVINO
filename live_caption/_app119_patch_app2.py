# -*- coding: utf-8 -*-
"""🔴🔴🔳 APP-119 §2（续）：两处**文案**改写（注释/文档字符串）。

1. ``_npu_conflict_note`` 的文档字符串 ⇒ 改成 APP-119 §2 的「**只提示、
   不禁止、不改设备**」口径。
2. ``_fill_tts_strip`` 里挂 NPU 提示的那段注释 ⇒ 改成 APP-119 §2 的
   「挂在**相关模块**状态条上、**不得**把 APP-117 全局状态灯加回来」。

写盘走 临时文件 → os.replace；写后 ast.parse + 字节复核。
"""
import ast
import os
import sys
import tempfile

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'live_caption_app.py')

# ---- 1) _npu_conflict_note 的文档字符串 --------------------------------
DOC_NEW = '''        """🔴🔴🔳 **APP-119 §2：NPU 共用的「性能提示」**（MT / ASR 与 TTS 同在 NPU）。

        🔴 **实测依据**（reviewer APP-061③ 的 A/B 表）：
          - 21:21–21:22（ASR GPU.0 + **MT NPU** + TTS NPU）：合成墙钟/音频 = **1.31**
          - 21:25–21:31（ASR+MT GPU.0 + TTS NPU）：**1.05 / 1.00**
          ⇒ MT 与 TTS 同在 NPU ⇒ 合成慢 **25–30 %**（**确定**）。

        🔴🔴🔳 **APP-119 §2 的口径**（reviewer 2026-11-20）：
          「**最多保留一条不阻塞的性能提示**，放在**相关模块**的状态条上。
            **不要把全局状态灯加回来。**」
          ⇒ 本函数**只产出提示文案**：
            ① **不禁止**、**不改设备**、**不弹框**；
            ② 消费方 = **语音输出（TTS）状态条**（`_fill_tts_strip`）
               ⇒ **不是**顶部总状态灯（APP-117 的全局状态灯**不得**回来）；
            ③ 若组合真失败（编译失败 / NPU OOM）⇒ 由各模块**显式报错**
               （`tts.stats()['last_error']` / `mt.err`）＋ 写日志
               ⇒ **绝不静默换设备**。
        """
'''

# ---- 2) _fill_tts_strip 里的注释块 --------------------------------------
STRIP_NEW = """        # 🔴🔴🔳 **APP-119 §2：NPU 共用的性能提示**（**只提示、不禁止**）
        #   reviewer 原文：「最多保留一条不阻塞的性能提示，放在相关模块的
        #   状态条上。**不要把全局状态灯加回来。**」
        #   ⇒ 挂在**语音输出（TTS）状态条**上（合成变慢影响的是 TTS）
        #   ⇒ **不碰**顶部总状态灯（APP-117 的全局状态灯不回来）。
"""


def main() -> int:
    with open(TARGET, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-8')

    # ---- 1) 文档字符串 ----
    anchor = '    def _npu_conflict_note(self):'
    if text.count(anchor) != 1:
        print('FAIL: def _npu_conflict_note 命中 %d 次' % text.count(anchor))
        return 2
    i = text.index(anchor)
    j = text.index('        """', i)          # 文档字符串起始
    k = text.index('        """', j + 12)     # 文档字符串结束
    old_doc = text[j:k + len('        """')]
    if 'D4' not in old_doc:
        print('FAIL: 文档字符串锚点不对')
        return 2
    text = text[:j] + DOC_NEW + text[k + len('        """'):]

    # ---- 2) 注释块 ----
    lines = text.split('\n')
    hit = [n for n, ln in enumerate(lines) if 'D4 未决' in ln]
    if len(hit) != 1:
        print('FAIL: 「D4 未决」命中 %d 次' % len(hit))
        return 2
    n = hit[0]
    # 该注释块：从 n-3 开始的 4 行（都是注释行）
    start = n - 3
    while start > 0 and lines[start - 1].lstrip().startswith('#'):
        start -= 1
    end = n
    while end < len(lines) and lines[end].lstrip().startswith('#'):
        end += 1
    old_block = '\n'.join(lines[start:end])
    if 'NPU' not in old_block:
        print('FAIL: 注释块锚点不对')
        return 2
    new_lines = lines[:start] + STRIP_NEW.rstrip('\n').split('\n') + lines[end:]
    text = '\n'.join(new_lines)

    try:
        ast.parse(text)
    except SyntaxError as e:
        print('FAIL: ast.parse 失败：%s' % e)
        return 3

    data = text.encode('utf-8')
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TARGET),
                               prefix='_app119_patch2_', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, TARGET)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    with open(TARGET, 'rb') as f:
        back = f.read()
    if back != data:
        print('FAIL: 写后字节不一致')
        return 4
    ast.parse(back.decode('utf-8'))
    print('OK: 文档字符串 + 注释块已改写；新文件 %d 字节（原 %d）'
          % (len(back), len(raw)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
