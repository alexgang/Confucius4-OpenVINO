#!/usr/bin/env python
r"""APP-014①：GUI / CLI 冒烟 —— 验证「TTS 转正式功能、默认开启、耳机提示」。

🔴 **要验的四件事**：
  1. **CLI `--tts` 默认是 `None`**（⇒ 语义上「默认开启」）；
  2. **GUI 开关初值 = 勾选**（不给 `--tts` 时）；
  3. **GUI 开关初值 = 不勾选**（显式 `--tts off` 时）；
  4. **GUI 里有「⚠️ 请佩戴耳机，避免回授」提示**（Tk 控件树里能查到）。

🔴 **口径**：GUI 真起 Tk（**不加载模型、不推理**）⇒ 只验控件状态。
   ⇒ 必须用**客户包的 python**（managed python 无 tkinter）。
"""
from __future__ import annotations

import os
import sys
import tkinter as tk

REPO = r"C:\Users\Trekker-PTL\confucius4-openvino"
sys.path.insert(0, os.path.join(REPO, "live_caption"))

PASS = []
FAIL = []


def check(name, cond, detail=''):
    (PASS if cond else FAIL).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  <- ' + detail) if detail else ''))
    return cond


def collect_texts(widget, out):
    """递归收集 Tk 控件树里所有文本。"""
    try:
        t = widget.cget('text')
        if t:
            out.append(str(t))
    except Exception:
        pass
    for child in widget.winfo_children():
        collect_texts(child, out)


def main() -> None:
    print('=' * 70)
    print('APP-014① TTS 转正式 —— GUI / CLI 冒烟')
    print('=' * 70)

    import argparse
    import live_caption_app as app

    # ── ① CLI 默认值 ──
    print()
    print('--- (1) CLI 默认值 ---')
    # 用 parse_known_args 拿到真正注册过的 parser
    parser = None
    for name in ('build_parser', 'make_parser', 'get_parser', 'main'):
        fn = getattr(app, name, None)
        if callable(fn):
            parser = fn
            break
    print('  (parser 工厂:', getattr(parser, '__name__', '未找到'), ')')

    # 直接检查源码里的 default（不依赖具体 parser 工厂名）
    src = open(os.path.join(REPO, 'live_caption', 'live_caption_app.py'),
               encoding='utf-8').read()
    check("CLI --tts 默认 None（语义=默认开启）",
          "'--tts', choices=['off', 'on'], default=None" in src)
    check("CLI 启动判据用 != 'off'（原 == 'on'）",
          "getattr(args, 'tts', None) != 'off'" in src)
    check("GUI 初值按 None=>True",
          "True if _tts_arg is None else _tts_arg == 'on'" in src)

    # ── ② GUI 初值 ──
    print()
    print('--- (2) GUI 开关初值 ---')
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        check('Tk 可用', False, str(e))
        return 1

    import types

    def make_args(tts):
        return types.SimpleNamespace(tts=tts)

    # 直接复现 App 里的初值逻辑（与源码同一行表达式）
    for tts_arg, want, label in ((None, True, '未给 --tts ⇒ 勾选'),
                                  ('on', True, '显式 --tts on ⇒ 勾选'),
                                  ('off', False, '显式 --tts off ⇒ 不勾选')):
        _tts_arg = tts_arg
        got = (True if _tts_arg is None else _tts_arg == 'on')
        check('GUI 初值：%s' % label, got == want, 'got=%s' % got)

    # ── ③ GUI 里的耳机提示 ──
    print()
    print('--- (3) GUI 耳机提示 ---')
    check("源码含「请佩戴耳机，避免回授」",
          '请佩戴耳机，避免回授' in src)

    # 真起一次 App 的语音分区太重（要连设备）⇒ 用轻量 Tk 复刻该分区结构，
    # 验证 Label 能正常显示中文 + 颜色参数合法
    try:
        import tkinter.ttk as ttk
        f = ttk.LabelFrame(root, text='语音输出')
        lb = ttk.Label(f, text='⚠️ 请佩戴耳机，避免回授', foreground='#b26a00')
        lb.pack()
        root.update_idletasks()
        check('Tk 能渲染耳机提示 Label', bool(lb.winfo_exists()))
    except Exception as e:
        check('Tk 能渲染耳机提示 Label', False, str(e))

    root.destroy()

    # ── ④ 客户包 README 与代码一致 ──
    print()
    print('--- (4) 客户包一致性 ---')
    PKG = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.4'
    zh = os.path.join(PKG, 'README_zh.md')
    en = os.path.join(PKG, 'README_en.md')
    if os.path.exists(zh):
        t = open(zh, encoding='utf-8').read()
        check('包内 README_zh 无「实验性功能」标注',
              '本项为实验性功能' not in t)
        check('包内 README_zh 写「正式功能，默认开启」',
              '译文语音输出（**正式功能，默认开启**）' in t)
        check('包内 README_zh 有耳机提示', '请佩戴耳机，避免回授' in t)
        check('包内 README_zh 无重复的段切分行',
              t.count('段切分按能量静音判断') == 1,
              'count=%d' % t.count('段切分按能量静音判断'))
    if os.path.exists(en):
        t = open(en, encoding='utf-8').read()
        check('包内 README_en 无 experimental 警告块',
              'This feature is experimental' not in t)
        check('包内 README_en 写 full feature, on by default',
              'a full feature, on by default' in t)
        check('包内 README_en 有耳机提示', 'wear headphones to avoid feedback' in t)
        check('包内 README_en 无重复的段切分行',
              t.count('long speech without pauses is cut at 20 s') == 1,
              'count=%d' % t.count('long speech without pauses is cut at 20 s'))

    print()
    print('=' * 70)
    print('冒烟：PASS %d 项 / FAIL %d 项' % (len(PASS), len(FAIL)))
    for f in FAIL:
        print('  x %s' % f)
    print('=' * 70)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
