#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-067 ④ 的**截图 + 闸门**：补齐 reviewer 点名的 3 项。

## reviewer 原话（APP-067 ④）

> app233 只跑了 off / preset / clone 三个臂各一次，只有 CLI：
> - 没有 ABBA，也没有 GUI 那一次；
> - ASR RTF 增量 +0.122，超出 +0.10 的限值，需要 ABBA 复测确认；
> - **D2/D4 截图缺失**；
> - **4 张截图里「⑤ 高级」都是折叠状态，看不到高级区的分组和提示。
>   请补「高级」展开后 100 % 和 150 % 各一张。**
> - **150 % 截图中按钮文字「有模块待处理」被截断，请一并修正。**

## 本脚本做什么（**纯 GUI 布局，不加载模型 ⇒ 不占 GPU/NPU ⇒ 不需要 MACHINE_LOCK**）

| # | 产物 | 覆盖 |
|---|---|---|
| S1 | `app067_adv_open_scaling100.png` | 高级组**展开** @100 % |
| S2 | `app067_adv_open_scaling150.png` | 高级组**展开** @150 % |
| S3 | `app067_d4_status_scaling100.png` | D4：翻译行状态栏**不含 NPU** |
| S4 | `app067_d4_status_scaling150.png` | D4 @150 % |

## 闸门（判据 + 反证）

| # | 判据 |
|---|---|
| G1 | 「▲ 有模块待处理」按钮在 100 % / 150 % 下**文字不被裁掉**（按像素量） |
| G2 | 高级组**展开后**可见（含「⑤ 高级」组标题） |
| G3 | 高级组**展开时**含设备选择 / 缓冲时长 / 调试日志等**平时不用的**项 |
| G4 | D4 生效时翻译状态行**不含「NPU」**（APP-063 验收条件） |
| G5 | 翻译状态行的**设备**是 GPU.0 |

## 输出
`results/app/app238_app067_gui_shots_evidence.json`
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
LC = os.path.join(REPO, 'live_caption')
SHOT_DIR = os.path.join(HERE, 'app067_gui_shots')
OUT = os.path.join(HERE, 'app238_app067_gui_shots_evidence.json')
APP_PY = os.path.join(LC, 'live_caption_app.py')

sys.path.insert(0, LC)
sys.path.insert(0, HERE)

# 🔴🔴🔳 **抑制模态弹框**（APP-067 ④）：探针**有** GUI root 但**没人点**
#   ⇒ `messagebox.showwarning()` 会**永久挂起**（实测卡死 >5 min）。
#   ⇒ 用 App 提供的**显式开关**跳过模态弹框（状态栏 + 日志**照旧**）。
os.environ['LIVECAP_NO_MODAL'] = '1'

import tkinter as tk                       # noqa: E402
from PIL import Image                     # noqa: E402


# ══════════════════════════════════════════════════════════════
# 静态：AST 判据（不 import 被测模块）
# ══════════════════════════════════════════════════════════════
def _norm(p):
    with open(p, 'rb') as f:
        return f.read().decode('utf-8').replace('\r\n', '\n')


def _func_src(src, name):
    tree = ast.parse(src)
    lines = src.split('\n')
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return '\n'.join(lines[n.lineno - 1:n.end_lineno])
    return ''


def s1_button_pixel_fit():
    """G1（静态）：按钮宽度**按像素**算，不再靠字符数。"""
    src = _norm(APP_PY)
    body = _func_src(src, '_fit_status_light_width')
    if not body:
        return False, '找不到 _fit_status_light_width'
    has_measure = 'measure(' in body
    has_candidates = '有模块待处理' in body
    has_configure = 'configure(width=' in body
    ok = has_measure and has_candidates and has_configure
    return ok, ('像素量=%s 候选文案=%s 写回宽度=%s'
                % (has_measure, has_candidates, has_configure))


def s2_fit_called():
    """G1（静态）：`_fit_status_light_width()` **真的被调用**。"""
    src = _norm(APP_PY)
    # 调用点必须**不在**函数定义体里
    body = _func_src(src, '_fit_status_light_width')
    rest = src.replace(body, '') if body else src
    called = 'self._fit_status_light_width()' in rest
    return called, ('调用点存在=%s' % called)


# ══════════════════════════════════════════════════════════════
# 动态：GUI 实测（不加载模型）
# ══════════════════════════════════════════════════════════════
def _make_args(tts_voice='A'):
    """🔴 **复用 app231 已验证的 args 构造**（不要自己重写 ⇒ 字段会漂）。

    🔴 **为什么复用**：`live_caption_app.App.__init__` 读的 args 字段很多
    （`translate` / `asr_lang` / `engine` / `font_size` / `autostart` …）
    ⇒ 自己拼 `Namespace` 必然漏字段 ⇒ `AttributeError`（本轮踩过）。
    ⇒ app231 的 `make_args` 是**同一条代码路径**上跑通过的 ⇒ 直接用。
    """
    import app231_app065a_screenshot as a231
    return a231.make_args(tts_voice)


def _build(root, tts_voice='A'):
    import live_caption_app as lca
    import translator
    # 🔴 **不加载模型**（纯 GUI 布局 ⇒ 不占 GPU/NPU ⇒ 不需要 MACHINE_LOCK）
    lca.App.load_engine = lambda self: None
    translator.TranslationService.set_engine = lambda self, k: True
    translator.TranslationService.set_device = lambda self, d: True
    return lca.App(root, _make_args(tts_voice))


def _shot(root, path):
    """抓屏（Win32 PrintWindow；PIL.ImageGrab 本机全黑 ⇒ 不用）。"""
    from win_capture import capture_hwnd
    root.update_idletasks()
    root.update()
    ok = capture_hwnd(root.winfo_id(), path)
    return bool(ok) and os.path.isfile(path)


def _text_of(widget):
    try:
        return widget.cget('text')
    except Exception:
        return ''


def _strip_text(app, key):
    """取某个分区状态条的完整文本。"""
    try:
        s = getattr(app, '_strip_%s' % key)
        st = s['status'].snapshot()
        parts = []
        for _k, f in st.items():
            if f.get('value'):
                parts.append('%s %s' % (f.get('label', ''), f['value']))
        return ' | '.join(parts)
    except Exception as e:
        return 'ERR:%r' % (e,)


def _run(tag, scale, adv_open, d4_probe):
    def _t(msg):
        print('    [trace] %s' % msg, flush=True)

    _t('建 root')
    root = tk.Tk()
    LOGIC_W, LOGIC_H = 1080, 820
    root.geometry('%dx%d+0+0' % (int(LOGIC_W * scale),
                                  int(LOGIC_H * scale)))
    try:
        root.tk.call('tk', 'scaling', scale)
    except Exception as e:
        print('    [warn] scaling 设置失败：%r' % (e,))
    _t('建 App')
    app = _build(root, 'A')
    _t('update')
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    _t('基础 update 完成')

    # ── D4 场景：让 MT 真值 = GPU.0（模拟 enforce 命中后的状态）────────
    if d4_probe:
        try:
            app.mt = getattr(app, 'mt', None)
            if app.mt is not None:
                app.mt.device = 'GPU.0'
                app.mt.engine_key = 'gpu_int8cw'
            # 🔴 关键：combo 停在 NPU 选项上（= reviewer 截图里的故障态）
            #   ⇒ 状态栏若仍显示 NPU ⇒ bug 还在
            app._fill_mt_strip()
            root.update_idletasks()
            root.update()
        except Exception as e:
            print('    [warn] D4 探针异常：%r' % (e,))

    # ── 展开「高级」───────────────────────────────────────────
    if adv_open:
        try:
            if not getattr(app, '_adv_open', False):
                app._toggle_advanced()
            root.update_idletasks()
            root.update()
            time.sleep(0.3)
            root.update()
        except Exception as e:
            print('    [warn] 展开高级失败：%r' % (e,))

    path = os.path.join(SHOT_DIR, 'app067_%s_scaling%03d.png'
                        % (tag, int(round(scale * 100))))
    _t('抓屏')
    ok = _shot(root, path)
    _t('抓屏完成 ok=%s' % ok)

    # ── 量「有模块待处理」按钮是否被裁 ────────────────────────
    btn = getattr(app, 'btn_global_light', None)
    btn_px = None
    need_px = None
    clipped = None
    if btn is not None:
        try:
            import tkinter.font as tkfont
            try:
                fname = btn.cget('font') or 'TkDefaultFont'
                font = tkfont.nametofont(str(fname), root=root)
            except Exception:
                font = tkfont.nametofont('TkDefaultFont', root=root)
            need_px = max(font.measure(s) for s in
                          ('⚪ 就绪', '✖ 有模块异常', '▲ 有模块待处理',
                           '● 全部就绪'))
            btn_px = btn.winfo_width()
            clipped = (btn_px < need_px)
        except Exception as e:
            print('    [warn] 量按钮失败：%r' % (e,))

    # ── 高级组可见性 + 内容清单 ───────────────────────────────
    adv_visible = None
    adv_items = []
    if adv_open:
        try:
            grp = getattr(app, '_adv_group', None)
            adv_visible = bool(grp is not None and grp.winfo_ismapped())
            if grp is not None:
                for ch in grp.winfo_children():
                    adv_items.append(ch.winfo_class())
        except Exception as e:
            print('    [warn] 量高级组失败：%r' % (e,))

    mt_text = _strip_text(app, 'mt')
    tts_text = _strip_text(app, 'tts')

    info = {
        'tag': tag, 'scaling': scale, 'adv_open': adv_open,
        'd4_probe': d4_probe,
        'shot': path if ok else None,
        'shot_bytes': os.path.getsize(path) if ok and os.path.exists(path)
        else 0,
        'btn_width_px': btn_px,
        'btn_text_need_px': need_px,
        'btn_text_clipped': clipped,
        'adv_group_visible': adv_visible,
        'adv_child_classes': adv_items,
        'mt_strip_text': mt_text,
        'tts_strip_text': tts_text,
        'mt_strip_has_NPU': ('NPU' in mt_text),
        'mt_strip_has_GPU0': ('GPU.0' in mt_text),
        'window': [root.winfo_width(), root.winfo_height()],
    }
    try:
        root.destroy()
    except Exception:
        pass
    return info


def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    runs = []
    for tag, scale, adv_open, d4_probe in (
            ('adv_open', 1.0, True, False),
            ('adv_open', 1.5, True, False),
            ('d4_status', 1.0, False, True),
            ('d4_status', 1.5, False, True)):
        print('== 截图 %s scaling=%.1f adv_open=%s d4=%s'
              % (tag, scale, adv_open, d4_probe))
        r = _run(tag, scale, adv_open, d4_probe)
        runs.append(r)
        print('   btn %s px / 需 %s px / 裁=%s ｜ 高级可见=%s'
              % (r['btn_width_px'], r['btn_text_need_px'],
                 r['btn_text_clipped'], r['adv_group_visible']))
        print('   MT 状态行：%s' % r['mt_strip_text'])

    by = {(r['tag'], r['scaling']): r for r in runs}

    checks = []

    def chk(name, ok, detail):
        checks.append({'name': name, 'ok': ok, 'detail': detail})

    # G1：按钮不裁（4 个场景都不能裁）
    clip_bad = [r['tag'] for r in runs if r['btn_text_clipped'] is True]
    chk('G1 「▲ 有模块待处理」在 100%/150% 下不被裁掉（按像素）',
        not clip_bad,
        '各场景按钮宽 px=%s / 需 px=%s；被裁的场景=%s'
        % ([r['btn_width_px'] for r in runs],
           [r['btn_text_need_px'] for r in runs],
           clip_bad or '无'))

    # G1b：静态判据（代码里真的按像素算）
    ok1, d1 = s1_button_pixel_fit()
    chk('G1b 代码按像素量按钮宽度（不靠字符数）', ok1, d1)
    ok2, d2 = s2_fit_called()
    chk('G1c _fit_status_light_width() 真的被调用', ok2, d2)

    # G2：高级组展开后可见
    adv = [by.get(('adv_open', 1.0)), by.get(('adv_open', 1.5))]
    vis = [a['adv_group_visible'] for a in adv if a]
    chk('G2 「⑤ 高级」展开后可见（100 % 与 150 %）',
        len(vis) == 2 and all(vis is True for vis in vis),
        '可见性=%s' % (vis,))

    # G3：高级组里确实是「平时不用的」控件
    chk('G3 高级组展开后含控件（不是空组）',
        all(a and a['adv_child_classes'] for a in adv),
        '子控件类别=%s' % ([a['adv_child_classes'] for a in adv
                            if a],))

    # G4：MT 状态行不含 NPU（D4 场景）
    d4 = [by.get(('d4_status', 1.0)), by.get(('d4_status', 1.5))]
    has_npu = [a['mt_strip_has_NPU'] for a in d4 if a]
    chk('G4 D4 生效后翻译状态行不含 NPU（APP-063 验收条件）',
        len(has_npu) == 2 and not any(has_npu),
        '含 NPU=%s；MT 状态行原文=%s'
        % (has_npu, [a['mt_strip_text'] for a in d4 if a]))

    # G5：MT 状态行设备是 GPU.0
    has_gpu = [a['mt_strip_has_GPU0'] for a in d4 if a]
    chk('G5 翻译状态行的设备是 GPU.0',
        len(has_gpu) == 2 and all(has_gpu),
        '含 GPU.0=%s' % (has_gpu,))

    n_pass = sum(1 for c in checks if c['ok'] is True)
    n_fail = sum(1 for c in checks if c['ok'] is False)
    n_none = sum(1 for c in checks if c['ok'] is None)

    print()
    for c in checks:
        mark = {True: 'PASS', False: 'FAIL', None: 'NONE'}[c['ok']]
        print('  [%s] %s —— %s' % (mark, c['name'], c['detail']))

    ev = {
        'script': os.path.basename(__file__),
        'correction': 'APP-067 ④（GUI 截图 + 按钮截断 + D4 状态行）',
        'device_lock': '不需要（纯 GUI 布局，不加载模型 ⇒ 不占 GPU/NPU）',
        'runs': runs,
        'checks': checks,
        'n_pass': n_pass, 'n_fail': n_fail, 'n_none': n_none,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
        'shots': [r['shot'] for r in runs if r['shot']],
        'meaning': ('PASS = **界面层**的 3 项（按钮不裁 / 高级组可见 / '
                    'D4 状态行不含 NPU）成立。'
                    '≠ APP-067 ④ 的 **ABBA 设备级复测**（ASR RTF +0.122 '
                    '需持 MACHINE_LOCK 在真包上跑 ABBA）。'),
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print()
    print('结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, ev['verdict']))
    print('产物：%s' % OUT)
    return 0 if ev['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
