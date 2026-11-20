# -*- coding: utf-8 -*-
"""🔴🔴🔳 APP-119 §2：从 `live_caption_app.py` **删除** NPU 互斥强制逻辑。

删掉两个方法（整体删除，保留一行「已删除」的说明，便于以后追溯）：

  * ``_sync_mt_combo_to_gpu0()``   —— 把翻译下拉强行指回 GPU.0
  * ``_enforce_no_npu_conflict()`` —— 「MT 与 TTS 同在 NPU ⇒ 自动把 MT 挪到
    GPU.0 ＋ 写配置 ＋ 弹模态框」

口径（与 §一 纪律一致）：
  * 定点删除（**唯一命中断言**）⇒ 不动文件里其它任何一行；
  * 写盘走 **临时文件 → os.replace**（避免截断写失败 ⇒ 0 B）；
  * 写后 **ast.parse** + 字节复核。
"""
import ast
import os
import shutil
import sys
import tempfile

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'live_caption_app.py')

START = "    def _sync_mt_combo_to_gpu0(self):"
END = "    def _warn_asr_mt_same_gpu(self, origin: str = ''):"

REPLACEMENT = (
    "    # 🔴🔴🔳 **APP-119 §2（2026-11-20）：以下两个方法已整体删除** ——\n"
    "    #   * ``_sync_mt_combo_to_gpu0()``   —— 把翻译下拉强行指回 GPU.0\n"
    "    #   * ``_enforce_no_npu_conflict()`` —— 「MT 与 TTS 同在 NPU ⇒\n"
    "    #     自动把 MT 挪到 GPU.0 ＋ 写配置 ＋ 弹模态框」\n"
    "    #   reviewer 原文：「**删掉**『MT 和 TTS 不能同时放在 NPU ⇒ 自动把\n"
    "    #     MT 挪到 GPU.0』这条强制规则，不再自动改用户的选择。」\n"
    "    #   ⇒ 现在：**用户选什么就用什么**；共用 NPU 只在**语音输出状态条**\n"
    "    #     上留一条**不阻塞**的性能提示（`_npu_conflict_note()`）。\n"
    "    #   ⚠️ **不得**因此把 APP-117 的**全局状态灯**加回来。\n"
    "\n"
)


def main() -> int:
    with open(TARGET, 'rb') as f:
        raw = f.read()
    text = raw.decode('utf-8')
    if text.count(START) != 1:
        print('FAIL: START 标记命中 %d 次（要求恰好 1 次）' % text.count(START))
        return 2
    if text.count(END) != 1:
        print('FAIL: END 标记命中 %d 次（要求恰好 1 次）' % text.count(END))
        return 2
    i = text.index(START)
    j = text.index(END)
    if not (0 < i < j):
        print('FAIL: 区间顺序不对 i=%d j=%d' % (i, j))
        return 2
    old_span = text[i:j]
    if '_enforce_no_npu_conflict' not in old_span:
        print('FAIL: 区间里没有 _enforce_no_npu_conflict ⇒ 锚点不对')
        return 2
    new_text = text[:i] + REPLACEMENT + text[j:]
    # 写前自检：新文本必须能解析
    try:
        ast.parse(new_text)
    except SyntaxError as e:
        print('FAIL: 新文本 ast.parse 失败：%s' % e)
        return 3
    # 反证：新文本里**不得**再出现这两个方法的定义
    for bad in ('def _enforce_no_npu_conflict', 'def _sync_mt_combo_to_gpu0'):
        if bad in new_text:
            print('FAIL: 新文本仍含 %s' % bad)
            return 3
    data = new_text.encode('utf-8')
    # 临时文件 → os.replace
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(TARGET),
                               prefix='_app119_patch_', suffix='.tmp')
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
    # 写后复核
    with open(TARGET, 'rb') as f:
        back = f.read()
    if back != data:
        print('FAIL: 写后字节不一致')
        return 4
    ast.parse(back.decode('utf-8'))
    print('OK: 删除区间 %d 字节 ⇒ 新文件 %d 字节（原 %d 字节）'
          % (len(old_span.encode('utf-8')), len(back), len(raw)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
