"""🔴 APP-048 验收：GUI **三分区状态条**布局。

## 覆盖什么

APP-048 的验收要求（reviewer 原文）：
- 「在 1920×1080 和 1280×720 下各截一张图（用户启动方式），三个区域的状态都可见，
  顶部不再拥挤；有一个模块故意加载失败时，对应区域会显示原因。」
- 截图放到 `shared/app_gui_layout/`。

## 本脚本做两件事（**分开**）

1. **纯逻辑组（离线，不起窗口）**：直接 import `live_caption/gui_status.py`
   ⇒ 断言字段优先级裁剪、级别聚合、tooltip 全文。
   ⚠️ **不 import `live_caption_app`**（它顶层 import numpy/torch/openvino
   ⇒ import 阶段就会 abort；而且会起后台线程）。
2. **GUI 组（起窗口，但**不加载任何模型**）**：把 `App.load_engine` 替换成
   空操作（与 `live_caption/diag_layout_gui.py` 同一手法）
   ⇒ 断言三个分区各有状态条、顶部不再拼三个模块的状态、
   1920×1080 与 1280×720 下都**不截断/溢出**、故意让翻译失败时
   翻译区**显示原因且整行变色**。

## 为什么不跑推理

APP-048 是**布局**验收 ⇒ 不需要模型 ⇒ 不占 GPU/NPU、不取机器锁、不计时。

## 跑法

    .venv\\Scripts\\python.exe results\\app\\app165_app048_gui_layout.py

（本机已有显示 ⇒ 可直接跑；无显示时会报「无法开窗」⇒ 纯逻辑组仍会跑完。）
"""

import ast
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, 'live_caption'))

def _enable_dpi_awareness():
    """🔴 **必须在创建 Tk 窗口之前**声明 per-monitor DPI 感知。

    ⚠️ 本机是 **125% 缩放**（`tk scaling 1.333`）⇒ Tk 的逻辑坐标
      与**物理像素**差 1.333 倍：
      - 不声明 ⇒ `winfo_width()` 返回 1920（逻辑），
        但 `ImageGrab.grab(bbox=...)` 用的是**物理像素**
        ⇒ 截出来只有窗口左上角 1920/2560 ≈ 75%（**截图看着比实际窄**）。
      - 声明后 ⇒ Tk 的坐标就是物理像素 ⇒ 截图与窗口一一对应。

    ⚠️ 声明只在**进程启动后、创建任何窗口前**有效 ⇒ 放在最前面。
    """
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PER_MONITOR_AWARE
        return True
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()      # 老 API
            return True
        except Exception:
            return False


# ⚠️ 必须在 import tkinter / 创建 Tk **之前**调用
_DPI_OK = _enable_dpi_awareness()

RESULTS = os.path.join(REPO, 'results', 'app')
SHOT_DIR = r'C:\Users\Trekker-PTL\shared\app_gui_layout'

FAILS = []
PASSES = []


def check(name, cond, detail=''):
    tag = 'PASS' if cond else 'FAIL'
    print(f'  [{tag}] {name}' + (f'  {detail}' if detail else ''))
    (PASSES if cond else FAILS).append(name)
    return bool(cond)


# ══════════════════════════════════════════════════════════════════════
# A 组：纯逻辑（gui_status.py，**不 import live_caption_app**）
# ══════════════════════════════════════════════════════════════════════
def group_a():
    print('\n== A 组：分区状态条纯逻辑（离线）==')
    import gui_status as g

    s = g.SectionStatus('ASR')
    s.set('dev', '设备', 'GPU.0', priority=1)
    s.set('prec', '精度', 'INT8', priority=2)
    s.set('state', '状态', '就绪', priority=1)
    s.set('rtf', 'RTF', '0.53', priority=3)

    text, level, tip = s.render()
    check('A1 渲染出单行文本', '\n' not in text and '·' in text, text)
    check('A2 级别 = ok', level == 'ok', level)
    check('A3 tooltip 含全部字段', all(k in tip for k in ('设备', '精度', '状态', 'RTF')),
          tip.replace('\n', ' | '))

    # 优先级排序：priority 小的在前
    check('A4 字段按优先级排序', text.index('设备') < text.index('精度'),
          text)

    # 裁剪：宽度不够 ⇒ 先丢次要字段
    wide, _, _ = s.render()
    narrow, _, _ = s.render(max_px=120)
    check('A5 宽度不足时裁剪（变短）', len(narrow) < len(wide),
          f'{len(narrow)} < {len(wide)}')
    check('A6 裁剪后保留最重要字段', narrow.startswith('设备'), narrow)

    # 级别聚合：任一 error ⇒ 整行 error
    s.set('state', '状态', '失败', priority=1, level='error', tip='日志 C:/x.log')
    _, level, tip = s.render()
    check('A7 error 字段 ⇒ 整行 error', level == 'error', level)
    check('A8 tooltip 含完整原因', 'C:/x.log' in tip, tip.replace('\n', ' | '))

    # warn 聚合
    s.set('state', '状态', '加载中', priority=1, level='warn')
    _, level, _ = s.render()
    check('A9 warn 字段 ⇒ 整行 warn（不升为 error）', level == 'warn', level)

    # 非法 level 归一
    s.set('state', '状态', 'X', priority=1, level='bogus')
    _, level, _ = s.render()
    check('A10 非法 level 归一为 ok', level == 'ok', level)

    # 三个分区各自独立
    secs = g.build_sections()
    check('A11 build_sections 返回三个分区',
          sorted(secs.keys()) == ['asr', 'mt', 'tts'], str(sorted(secs.keys())))
    secs['asr'].set('dev', '设备', 'NPU', priority=1)
    check('A12 分区互不串扰',
          secs['mt'].render()[0] == '' and 'NPU' in secs['asr'].render()[0],
          f"mt={secs['mt'].render()[0]!r}")

    # 快照可 JSON 化
    import json
    try:
        json.dumps(secs['asr'].snapshot(), ensure_ascii=False)
        check('A13 快照可 JSON 化', True)
    except Exception as e:
        check('A13 快照可 JSON 化', False, repr(e))

    # 字段级 level 会影响整行
    s2 = g.SectionStatus('T')
    s2.set('a', 'A', '1', priority=1, level='ok')
    s2.set('b', 'B', '2', priority=9, level='error')
    check('A14 次要字段的 error 也会让整行 error（用户要看到）',
          s2.render()[1] == 'error', s2.render()[1])


# ══════════════════════════════════════════════════════════════════════
# B 组：源码结构判据（静态）
# ══════════════════════════════════════════════════════════════════════
def group_b():
    print('\n== B 组：源码结构判据（静态）==')
    src = open(os.path.join(REPO, 'live_caption', 'live_caption_app.py'),
               encoding='utf-8').read()
    tree = ast.parse(src)

    funcs = {n.name: n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    check('B1 有 `_make_status_strip`', '_make_status_strip' in funcs)
    check('B2 有 `_update_strips`', '_update_strips' in funcs)
    check('B3 有 `_fill_asr_strip` / `_fill_mt_strip` / `_fill_tts_strip`',
          all(k in funcs for k in ('_fill_asr_strip', '_fill_mt_strip',
                                   '_fill_tts_strip')))
    check('B4 有 `_show_global_status`（总状态灯点击查看）',
          '_show_global_status' in funcs)

    # 顶部 meter 不再拼三个模块的状态
    poll_node = funcs['_poll']
    meter_set = [n for n in ast.walk(poll_node)
                 if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute)
                 and n.func.attr == 'set'
                 and isinstance(n.func.value, ast.Attribute)
                 and n.func.value.attr == 'var_meter']
    ok = True
    for call in meter_set:
        seg = ast.get_source_segment(src, call)
        if seg and ('_mt_meter' in seg or '_tts_meter' in seg
                    or 'device_desc' in seg or 'RTF' in seg):
            ok = False
    check('B5 顶部 `var_meter` 不再拼 ASR/翻译/TTS 的模块状态', ok)

    # 1 Hz 节流
    upd = ast.get_source_segment(src, funcs['_update_strips'])
    check('B6 状态条刷新按 ≤ 1 Hz 节流', '1.0' in (upd or ''), 'throttle')

    # 三个分区各建一条状态条
    check('B7 三个分区都建了状态条',
          src.count('_make_status_strip(') >= 4,   # 1 处定义 + 3 处调用
          str(src.count('_make_status_strip(')))

    # tooltip
    check('B8 有 tooltip 实现（悬停显示完整原因和日志路径）',
          '_set_strip_tooltip' in src and 'overrideredirect' in src)

    # 旧的整窗长 meter 拼接已移除
    check('B9 `_tts_meter` 不再被拼进顶部（改为写分区状态条）',
          'self.var_meter.set(' not in (ast.get_source_segment(
              src, funcs['_tts_meter']) or '')
          and '_strip_tts' in (ast.get_source_segment(
              src, funcs['_tts_meter']) or ''))

    # 既有回归不许被破坏：`_poll` 仍调用 `_tts_meter()`
    poll_src = ast.get_source_segment(src, funcs['_poll']) or ''
    check('B10 `_poll()` 仍调用 `_tts_meter()`（既有 app103 B11 判据）',
          'self._tts_meter()' in poll_src)
    check('B11 `_poll()` 仍调用 `_mt_meter()`',
          'self._mt_meter()' in poll_src)

    # 控件行为/默认值不得变（APP-048 明文）
    check('B12 没改 `var_tts_on` 的默认值（APP-041 启动逻辑不变）',
          'self.var_tts_on = tk.BooleanVar(' in src
          and "value=(True if _tts_arg is None else _tts_arg == 'on')" in src)
    check('B13 没改 `var_show_spk` 的默认值（APP-040④ 默认打开）',
          'self.var_show_spk = tk.BooleanVar(value=True)' in src)
    check('B14 没动三个组合下拉的绑定',
          all(s in src for s in ("cb_asr_combo.bind('<<ComboboxSelected>>'",
                                 "cb_mt_combo.bind('<<ComboboxSelected>>'",
                                 "cb_tts_combo.bind('<<ComboboxSelected>>'")))


def functions_node(src_segment):
    """把源码片段解析成 Module 节点（便于 ast.walk）。"""
    return ast.parse(src_segment)



# ══════════════════════════════════════════════════════════════════════
# C 组：GUI 实测（起窗口，不加载模型）
# ══════════════════════════════════════════════════════════════════════
class _Args:
    translate = 'off'
    mt_engine = 'auto'
    mt_ctx = False
    mt_glossary = False
    mt_draft = False
    asr_lang = 'auto'
    engine = 'gpu_int8'
    source = 'mic'
    device = None
    system_device = None
    file = None
    speed = 1.0
    loop = False
    overlay = True
    font_size = 26
    asr_device = 'GPU.0'
    mt_device = 'GPU.0'
    tts_device = 'NPU'
    device_notes = []
    tts = 'off'
    tts_voice = 'A'
    tts_precision = 'f32'
    tts_out_device = None
    selftest = 0
    autostart = False


def group_c():
    print('\n== C 组：GUI 实测（起窗口，**不加载模型**）==')
    try:
        import tkinter as tk
    except Exception as e:
        check('C0 有 tkinter', False, repr(e))
        return
    try:
        root = tk.Tk()
    except Exception as e:
        check('C0 能开窗口', False, repr(e))
        return
    check('C0 能开窗口', True)
    # 🔴 DPI 感知已生效 ⇒ Tk 坐标 == 物理像素 ⇒ 截图才能对得上
    try:
        scaling = float(root.tk.call('tk', 'scaling'))
    except Exception:
        scaling = 0.0
    print(f'  （DPI awareness = {_DPI_OK}，tk scaling = {scaling:.3f}）')
    # 🔴 物理屏只有 2048×1280 ⇒ 1920×1080 窗口必须**贴着左上角**放，
    #    否则底边超出屏幕（`PrintWindow` 不受影响，但 Tk 会截断布局计算）
    try:
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
    except Exception:
        sw, sh = 1920, 1080
    print(f'  （物理屏 = {sw}×{sh}）')

    import live_caption_app as lca
    # ⚠️ App.__init__ 末尾会调 load_engine()（后台线程真去加载 ASR 模型）
    #    ⇒ 本组只测**布局**，把它替换成空操作，避免占 GPU/NPU。
    _orig_load = lca.App.load_engine
    _orig_mt_set_engine = lca.TranslationService.set_engine
    _orig_mt_set_device = lca.TranslationService.set_device
    # 🔴 **`set_target` 也会起真加载线程**（`TranslationService.set_target`
    #   ⇒ `if self.active and not self._thread_alive(): self._start()`）
    #   ⇒ 注入的 `state='error'` 会被真线程**覆盖** ⇒ 截图拍到的是
    #   「加载中」而不是「失败」⇒ 必须一起 mock 掉。
    _orig_mt_set_target = lca.TranslationService.set_target
    lca.App.load_engine = lambda self: None
    lca.TranslationService.set_engine = lambda self, k: True
    lca.TranslationService.set_device = lambda self, d: True
    lca.TranslationService.set_target = lambda self, t: True
    try:
        app = lca.App(root, _Args())
        root.update_idletasks()
        root.update()
    except Exception as e:
        check('C1 能构造 App', False, repr(e))
        lca.App.load_engine = _orig_load
        lca.TranslationService.set_engine = _orig_mt_set_engine
        lca.TranslationService.set_device = _orig_mt_set_device
        lca.TranslationService.set_target = _orig_mt_set_target
        return
    check('C1 能构造 App', True)

    try:
        # ── C2：三个分区各有状态条 ──
        check('C2 三个分区都有状态条',
              all(hasattr(app, n) for n in ('_strip_asr', '_strip_mt', '_strip_tts')))

        # ── C3：状态条**在分区内部**（不是窗口顶部）──
        areas = None
        for w in root.winfo_children():
            for c in w.winfo_children():
                if 'Labelframe' in c.winfo_class():
                    areas = w
                    break
            if areas is not None:
                break
        check('C3 找到三分区容器', areas is not None)
        if areas is not None:
            lfs = [c for c in areas.winfo_children()
                   if 'Labelframe' in c.winfo_class()]
            check('C4 分区数 = 3', len(lfs) == 3, str(len(lfs)))
            # 状态条必须是某个 LabelFrame 的**后代**
            for key in ('asr', 'mt', 'tts'):
                lbl = app.__dict__['_strip_' + key]['label']
                anc = []
                p = lbl.master
                while p is not None:
                    anc.append(p)
                    p = getattr(p, 'master', None)
                in_area = any(a in lfs for a in anc)
                check(f'C5 {key} 状态条在自己的分区里（不在窗口顶部）', in_area,
                      str([type(a).__name__ for a in anc[:3]]))

            # 顶部 meter 不在分区里
            check('C6 顶部 meter 不在任何一个分区内',
                  app.lbl_meter.master not in lfs)

        # ── C7：1280×720 与 1920×1080 下都不截断/溢出 ──
        for (w, h) in ((1920, 1080), (1280, 720)):
            root.geometry(f'{w}x{h}+0+0')
            root.update_idletasks()
            root.update()
            time.sleep(0.15)
            root.update()
            bad = []
            for key in ('asr', 'mt', 'tts'):
                strip = app.__dict__['_strip_' + key]
                lw = strip['label'].winfo_width()
                fw = strip['frame'].winfo_width()
                # 文本宽度 > 容器宽度 ⇒ 溢出
                try:
                    tw = strip['label'].winfo_reqwidth()
                except Exception:
                    tw = 0
                if fw > 0 and tw > fw + 2:
                    bad.append(f'{key}: text={tw} frame={fw}')
                if fw <= 0:
                    bad.append(f'{key}: frame 宽度 0')
                if lw <= 0:
                    bad.append(f'{key}: label 宽度 0')
            check(f'C7 {w}x{h}: 三个状态条都不截断/溢出', not bad, '; '.join(bad))

            # 顶部行也不能挤爆：meter 的请求宽度 <= 窗口宽
            mw = app.lbl_meter.winfo_reqwidth()
            check(f'C8 {w}x{h}: 顶部 meter 不溢出窗口',
                  mw <= w, f'meter_req={mw} window={w}')

            # 会话计时 + 总状态灯存在且有内容
            check(f'C9 {w}x{h}: 会话计时与总状态灯可见',
                  app._session_elapsed.get() and app._global_light.get(),
                  f"{app._session_elapsed.get()!r} / {app._global_light.get()!r}")

        # ── C10：故意让翻译失败 ⇒ 翻译区显示原因 + 整行变色 ──
        # ⚠️ **必须先把翻译置为「已开启」**：`TranslationService.active`
        #   是 `target != 'off'` 的属性 ⇒ 目标语言为 'off' 时状态条走
        #   「未开启」分支，**根本到不了** error 分支
        #   ⇒ 用默认的 'off' 来测「失败」是**判据写错**，不是代码缺陷。
        root.geometry('1920x1080+0+0')
        root.update_idletasks()
        app.mt.target = 'zh'
        app.mt.state = 'error'
        app.mt.err = 'ValueError: 故意注入的翻译失败（APP-048 验收）'
        # ⚠️ `_update_strips()` 有 **1 Hz 节流**（APP-048 要求「数值定时刷新
        #   （≤ 1 Hz）」）⇒ 距上次刷新不足 1 s 时会**直接 return**
        #   ⇒ 测试里必须把节流时间戳归零，否则读到的还是旧值。
        app._strip_last = 0.0
        app._update_strips()
        root.update_idletasks()
        mt_text = app._strip_mt['status'].render()[0]
        mt_level = app._strip_mt['status'].render()[1]
        check('C10 翻译失败时翻译区显示失败状态', '失败' in mt_text, mt_text)
        check('C11 翻译失败时翻译区整行 = error（变色）', mt_level == 'error', mt_level)
        tip = app._strip_mt['status'].render()[2]
        check('C12 翻译失败的 tooltip 含原因', '故意注入' in tip,
              tip.replace('\n', ' | '))
        light = app._global_light.get()
        check('C13 总状态灯提示有模块异常', '异常' in light, light)

        # 🔴🔴 C13b：**刷新过程不许抛异常**
        #   （实测过 `ttk.Button.configure(foreground=…)` 抛
        #    `TclError: unknown option "-foreground"` ⇒ 整段刷新被打断
        #    ⇒ 状态灯永不变色 + 会话计时不刷新）
        errs = []
        try:
            while True:
                try:
                    app._ui_log_q.get_nowait()
                except Exception:
                    break
        except Exception:
            pass
        app._strip_last = 0.0
        app._update_strips()
        time.sleep(0.2)
        app.root.update()
        try:
            while True:
                msg = app._ui_log_q.get_nowait()
                if '状态条刷新失败' in str(msg):
                    errs.append(str(msg))
        except Exception:
            pass
        check('C13b 状态条刷新**无异常**（ttk 不支持 foreground 的坑）',
              not errs, '; '.join(errs))

        # ── C14：ASR 区字段（设备/精度/状态/RTF/说话人）──
        asr_fields = app._strip_asr['status'].snapshot()
        check('C14 ASR 区含设备/精度/状态/RTF/说话人字段',
              all(k in asr_fields for k in ('dev', 'prec', 'state', 'rtf', 'spk')),
              str(sorted(asr_fields.keys())))

        # ── C15：翻译区字段 ──
        mt_fields = app._strip_mt['status'].snapshot()
        check('C15 翻译区含设备/模型/目标语言/状态/延迟字段',
              all(k in mt_fields for k in ('dev', 'model', 'lang', 'state', 'lat')),
              str(sorted(mt_fields.keys())))

        # ── C16：语音区字段 ──
        tts_fields = app._strip_tts['status'].snapshot()
        check('C16 语音区含设备/音色/输出/状态/语速/滞后/排队字段',
              all(k in tts_fields for k in ('dev', 'voice', 'out', 'state',
                                            'speed', 'lag', 'queue')),
              str(sorted(tts_fields.keys())))

        # ── C17：截图（1920×1080 与 1280×720）──
        # 🔴🔴🔴 **必须先把 C10 注入的失败态恢复成正常态**！
        #   否则「正常态截图」拍到的其实是**错误态** ⇒
        #   `app048_layout_1920x1080.png` 与 `app048_layout_mt_failed.png`
        #   **字节完全相同**（实测 SHA256 一模一样 ⇒ 失败态根本没拍到）。
        #   ⇒ 截图前复位：目标语言回 'off'（⇒ 未开启分支）+ 清 err。
        app.mt.target = 'off'
        app.mt.state = 'idle'
        app.mt.err = ''
        app._strip_last = 0.0
        app._update_strips()
        # 🔴 清掉「mt load failed: …」那条**全局消息行**
        #   （`_track_mt_state` 在状态转 error 时会 `_ui_log` ⇒
        #     顶部 `var_status` 会残留一行错误 ⇒ 正常态截图看起来像坏了）
        try:
            app.var_status.set('')
        except Exception:
            pass
        root.update_idletasks()
        root.update()
        normal_text = app._strip_mt['status'].render()[0]
        check('C16b 截图前翻译区已复位为非失败态',
              '失败' not in normal_text, normal_text)
        check('C16c 截图前顶部全局消息行已清空（正常态无残留错误）',
              not app.var_status.get(), repr(app.var_status.get()))

        os.makedirs(SHOT_DIR, exist_ok=True)
        shots = []
        for (w, h) in ((1920, 1080), (1280, 720)):
            root.geometry(f'{w}x{h}+0+0')
            root.update_idletasks()
            root.update()
            time.sleep(0.3)
            root.update()
            path = os.path.join(SHOT_DIR, f'app048_layout_{w}x{h}.png')
            ok = _capture(root, path)
            shots.append((path, ok))
            check(f'C17 {w}x{h}: 截图落盘', ok, path)
        # 失败态也截一张（给 reviewer 看「对应区域会显示原因」）
        # ⚠️ **重新注入一次 error**：`_poll` → `_track_mt_state()` 可能
        #   观察到状态变化并写日志；而且截图循环里 `mt.target` 可能被改回
        #   ⇒ 失败态必须**在截图前再置一次**再刷新状态条。
        app.mt.target = 'zh'
        app.mt.state = 'error'
        app.mt.err = 'ValueError: 故意注入的翻译失败（APP-048 验收）'
        app._strip_last = 0.0
        app._update_strips()
        root.geometry('1920x1080+0+0')
        root.update_idletasks()
        root.update()
        time.sleep(0.3)
        root.update()
        path = os.path.join(SHOT_DIR, 'app048_layout_mt_failed.png')
        ok = _capture(root, path)
        shots.append((path, ok))
        check('C18 失败态截图落盘', ok, path)
        # 失败态截图里翻译区**必须真的显示「失败」**（像素级不判，读状态条）
        check('C18b 失败态截图前翻译区确实是 error',
              app._strip_mt['status'].render()[1] == 'error',
              app._strip_mt['status'].render()[0])
        # 🔴🔴🔴 C18c：**两张图必须像素级不同**
        #   （防「失败态截图其实拍到正常态」这种静默假通过；
        #    实测过：注入顺序错了 ⇒ 两图 SHA256 完全相同 ⇒ 假通过）
        diff_px = _png_diff_pixels(
            os.path.join(SHOT_DIR, 'app048_layout_1920x1080.png'), path)
        check('C18c 失败态截图与正常态截图像素级不同（不是同一张）',
              diff_px > 0, f'diff_px={diff_px}')
        # C18d：失败态截图里**红色确实存在**（error 色的整行变色）
        n_red = _count_color(path, (192, 57, 43), tol=40)
        check('C18d 失败态截图里存在 error 红色像素（整行变色生效）',
              n_red > 20, f'red_px={n_red}')

        # ── C19：截图里三个区域的状态**都可见**（像素级粗判）──
        #   判据：每条状态条在其分区**内部**且高度 > 8px（不是被压成 1px）
        for key in ('asr', 'mt', 'tts'):
            strip = app.__dict__['_strip_' + key]
            h = strip['label'].winfo_height()
            check(f'C19 {key} 状态条高度 > 8px（可见）', h > 8, f'h={h}')

        # ── C20：**长文本 note 行不溢出**（APP-048「不能截断或溢出」）──
        #   判据：所有换行 label 的 `wraplength` 已设 且
        #         请求宽度 <= 容器宽度（换行后不横向溢出）。
        wrapped = getattr(app, '_wrapped_labels', [])
        check('C20 长文本 note 行已启用换行（wraplength）',
              len(wrapped) >= 3, f'wrapped={len(wrapped)}')
        bad = []
        for lbl, container in wrapped:
            try:
                wl = lbl.cget('wraplength')
                fw = container.winfo_width()
                rw = lbl.winfo_reqwidth()
            except Exception:
                continue
            if not wl or wl < 10:
                bad.append(f'{lbl}: wraplength={wl}')
            elif fw > 0 and rw > fw + 4:
                bad.append(f'{lbl}: reqwidth={rw} > container={fw}')
        check('C21 长文本 note 行都不横向溢出', not bad, '; '.join(bad))

        # ── C22：顶部 var_note 行也不溢出 ──
        #   （它显示当前组合的说明文字，同样可能很长）
        try:
            vn = app.var_note.get()
            lbl = None
            for w in root.winfo_children():
                if w.winfo_class() == 'TLabel':
                    lbl = w
                    break
            if lbl is not None and vn:
                rw = lbl.winfo_reqwidth()
                check('C22 顶部说明文字不溢出窗口',
                      rw <= root.winfo_width() + 4,
                      f'reqwidth={rw} window={root.winfo_width()} text={vn[:40]!r}')
        except Exception as e:
            check('C22 顶部说明文字不溢出窗口', False, repr(e))

    finally:
        try:
            root.destroy()
        except Exception:
            pass
        lca.App.load_engine = _orig_load
        lca.TranslationService.set_engine = _orig_mt_set_engine
        lca.TranslationService.set_device = _orig_mt_set_device
        lca.TranslationService.set_target = _orig_mt_set_target

    return shots


def _capture(root, path):
    """截**窗口本身**（不是整屏）⇒ 1920×1080 也能截全。

    🔴🔴🔴 **必须用 `PrintWindow`，不能用 `PIL.ImageGrab`**
      （实测 2026-10-30：本机 `ImageGrab.grab()` 抓到的整屏是**全黑**
      ⇒ 之前三张截图全是黑图，而判据全在逻辑层 ⇒ **静默假通过**）。
      `PrintWindow` 让窗口**自己把内容画进内存 DC** ⇒ 不读屏幕像素。

    ⚠️ `root.geometry()` 只是**请求** ⇒ 必须 `update()` 之后
      `winfo_width()` 才是新尺寸；否则截到的是**上一档**尺寸的旧内容。
    ⚠️ **不能最小化** ⇒ 最小化时抓出来是空白。
    """
    try:
        root.update_idletasks()
        root.update()
        try:
            root.deiconify()
            root.attributes('-topmost', True)
            root.lift()
            root.focus_force()
        except Exception:
            pass
        root.update_idletasks()
        root.update()
        time.sleep(0.35)
        root.update()
        hwnd = _hwnd(root)
        if not hwnd:
            return False
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from win_capture import capture_hwnd
        ok = capture_hwnd(hwnd, path)
        if not ok:
            return False
        # 🔴 **黑图检测**：整图几乎全黑 ⇒ 抓取失败（**不算成功**）
        from PIL import Image
        im = Image.open(path).convert('L')
        lo, hi = im.getextrema()
        if hi - lo < 20:
            print(f'    [warn] {os.path.basename(path)} 疑似黑图'
                  f'（extrema=({lo},{hi})）⇒ 抓取失败')
            return False
        return os.path.exists(path) and os.path.getsize(path) > 1000
    except Exception as e:
        try:
            open(os.path.splitext(path)[0] + '.err.txt', 'w',
                 encoding='utf-8').write(repr(e))
        except Exception:
            pass
        return False


def _hwnd(root):
    try:
        return root.winfo_id()
    except Exception:
        return None


def _png_diff_pixels(p1, p2):
    """两张 PNG 的**不同像素数**（0 ⇒ 同一张图）。

    🔴 用途：防止「失败态截图其实拍到的是正常态」这种**静默假通过**
      （实测踩过：注入顺序错误 ⇒ 两图 SHA256 完全相同 ⇒ 判据恒真）。
    """
    try:
        from PIL import Image
        a = Image.open(p1).convert('RGB')
        b = Image.open(p2).convert('RGB')
        if a.size != b.size:
            return max(a.size[0] * a.size[1], b.size[0] * b.size[1])
        pa = list(a.getdata())
        pb = list(b.getdata())
        n = 0
        for x, y in zip(pa, pb):
            if x != y:
                n += 1
        return n
    except Exception:
        return -1


def _count_color(path, rgb, tol=40):
    """统计图片里接近指定 RGB 的像素数。"""
    try:
        from PIL import Image
        im = Image.open(path).convert('RGB')
        r, g, b = rgb
        n = 0
        for px in im.getdata():
            if (abs(px[0] - r) <= tol and abs(px[1] - g) <= tol
                    and abs(px[2] - b) <= tol):
                n += 1
        return n
    except Exception:
        return -1


def main():
    print('=' * 70)
    print('APP-048 验收：GUI 三分区状态条')
    print('=' * 70)
    group_a()
    group_b()
    shots = group_c()
    print('\n' + '=' * 70)
    print(f'PASS {len(PASSES)}  FAIL {len(FAILS)}')
    if FAILS:
        for f in FAILS:
            print('  FAIL:', f)
    print('verdict =', 'PASS' if not FAILS else 'FAIL')
    if shots:
        print('截图:')
        for p, ok in shots:
            print(f'  {"OK " if ok else "NG "} {p}')
    _write_evidence(shots)
    print('=' * 70)
    return 0 if not FAILS else 1


def _write_evidence(shots):
    """落盘证据 JSON（含每张截图的字节数 / mtime / SHA256）。"""
    import hashlib
    import json
    import time

    def sha(p):
        h = hashlib.sha256()
        try:
            with open(p, 'rb') as f:
                for c in iter(lambda: f.read(1 << 20), b''):
                    h.update(c)
        except Exception:
            return ''
        return h.hexdigest()

    ev = {
        'suite': 'app165_app048_gui_layout',
        'verdict': 'PASS' if not FAILS else 'FAIL',
        'n_pass': len(PASSES),
        'n_fail': len(FAILS),
        'passes': list(PASSES),
        'fails': list(FAILS),
        'dpi_awareness': bool(_DPI_OK),
        'shots': [],
    }
    for p, ok in (shots or []):
        if not os.path.exists(p):
            continue
        st = os.stat(p)
        ev['shots'].append({
            'path': p,
            'captured_ok': bool(ok),
            'bytes': st.st_size,
            'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime)),
            'sha256': sha(p),
        })
    # 两张关键截图的像素差异（防「失败态其实拍到正常态」）
    n1 = os.path.join(SHOT_DIR, 'app048_layout_1920x1080.png')
    n2 = os.path.join(SHOT_DIR, 'app048_layout_mt_failed.png')
    if os.path.exists(n1) and os.path.exists(n2):
        ev['diff_pixels_normal_vs_failed'] = _png_diff_pixels(n1, n2)
        ev['error_red_pixels_in_failed'] = _count_color(n2, (192, 57, 43), tol=40)
    out = os.path.join(RESULTS, 'app165_app048_gui_layout_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('证据已落盘:', out, os.path.getsize(out), 'B')


if __name__ == '__main__':
    sys.exit(main())
