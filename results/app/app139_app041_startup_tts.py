#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app139 — APP-041 验收：启动时「语音输出」默认开启必须**真的初始化**。

🔴🔴 APP-041（2026-10-29 14:58）用户报 bug：
  「App 启动的时候会默认选中语音输出『开启』选项，但是实际上并没有初始化设备，
    这个时候设备无法正常工作。必须去选中『开启』再选中『开启』之后，
    设备才能正确初始化。」

reviewer 修法要求：
  ① 启动流程里**显式调用和点击「开启」完全相同的那个初始化函数**
     （同一入口，不要另写一套），放在 **ASR → MT 就绪之后**
     （沿用「依次加载、auto=False 防 GPU 编译死锁」的顺序）；
  ② 初始化失败时，开关**自动回到「关闭」**，状态栏写明原因并指向日志；
  ③ 输出设备下拉框、音色/克隆选项在启动时就生效，和手动切换一次的结果一致；
  ④ 再查一下其他默认开启的选项，有无同类「默认值没触发初始化」的问题。
  验收：冷启动后**什么都不点** ⇒ 能出声；状态栏显示 TTS 就绪；
        日志里能看到启动时调用了初始化函数，**而且只调用一次**；
        另测「所选输出设备不存在」⇒ 开关自动回关并提示原因。

🔴 **判据设计铁律**（本项目 §9/§10）：
  ① **绝不 `import` 被测模块**（顶层 numpy 会让 import 阶段 abort）
     ⇒ 用 `ast` 抽源码 + `exec` 在独立命名空间里执行；
  ② **双向反证**：真实缺陷必须能被复现（基线 FAIL），修好后必须 PASS，
     且「注入回退 ⇒ 判据必须 FAIL」⇒ 证明判据不恒真；
  ③ 判据 FAIL 先怀疑判据本身。
"""
from __future__ import annotations

import ast
import io
import json
import os
import re
import subprocess
import sys
import textwrap

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_PY = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app139_app041_startup_tts_evidence.json')

RESULTS = []


def rec(name, ok, detail=''):
    RESULTS.append({'name': name, 'ok': bool(ok), 'detail': str(detail)[:600]})
    print(('PASS ' if ok else 'FAIL ') + name + ('  :: ' + str(detail)[:400] if detail else ''))
    return ok


def load_src(path=None):
    p = path or APP_PY
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()


def find_funcs(src, names):
    """用 ast 抽出指定顶层/类方法的源码段（不 import 被测模块）。"""
    tree = ast.parse(src)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in names:
                out.setdefault(node.name, []).append(node)
    return out


def method_src(src, cls_name, meth_name):
    """抽出 `class X:` 里 `def meth` 的完整源码（缩进还原）。"""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and sub.name == meth_name:
                    lines = src.splitlines()
                    body = lines[sub.lineno - 1:sub.end_lineno]
                    return textwrap.dedent('\n'.join(body))
    return None


def _make_fake_tkinter():
    """造一个**假的 `tkinter` 模块**（塞进 `sys.modules`）。

    🔴🔴🔴 **为什么需要**：
      被测方法内部有 `from tkinter import messagebox`
      ⇒ **函数内的 import 会覆盖 ns_extra 里的桩**
      ⇒ 真 `messagebox.showerror` 弹**模态框** ⇒ **脚本挂死**
        （表现为 SIGTERM / 超时，**很容易误判成产品缺陷**）。
      ⇒ 塞一个假模块 ⇒ 函数内 import 拿到的是桩 ⇒ 不弹框。
    """
    import types as _types
    tk = _types.ModuleType('tkinter')
    mb = _types.ModuleType('tkinter.messagebox')
    mb.showerror = lambda *a, **k: None
    mb.showwarning = lambda *a, **k: None
    mb.showinfo = lambda *a, **k: None
    tk.messagebox = mb
    tk.StringVar = lambda *a, **k: None
    tk.BooleanVar = lambda *a, **k: None
    tk.IntVar = lambda *a, **k: None
    tk.DoubleVar = lambda *a, **k: None
    tk.Tk = object
    tk.Toplevel = object
    tk.Frame = object
    tk.Label = object
    tk.Button = object
    tk.Entry = object
    tk.Text = object
    tk.Canvas = object
    tk.Menu = object
    tk.StringVar = lambda *a, **k: None
    return tk


def exec_methods(src, cls_name, meth_names, ns_extra=None, extra_imports=(),
                 extra_funcs=(), extra_defs=None):
    """把一组方法 exec 到独立命名空间，并**绑到假实例**上。

    🔴🔴 项目铁律（§9）：`exec` 抽出的方法彼此调用时会走 `self.xxx()`
       ⇒ 假实例上必须**先绑好同名方法**，否则 AttributeError。
    🔴 `_on_tts_toggled` 还会调用**模块级函数**
       （`_tts_device_problem` / `_first_usable_tts_device`）
       ⇒ 这些也必须一起 exec 进同一个命名空间；
       它们又依赖 `device_config` / `_is_intel_gpu` / `_cuda_tts_available`
       ⇒ 用 `extra_defs` 注入**桩**（本验收不测设备判据本身）。
    """
    ns = dict(ns_extra or {})
    for imp in extra_imports:
        exec(imp, ns)
    for name, val in (extra_defs or {}).items():
        ns[name] = val
    names = []
    for m in meth_names:
        code = method_src(src, cls_name, m)
        if code is None:
            raise RuntimeError(f'找不到方法 {cls_name}.{m}')
        exec(compile(code, f'<{cls_name}.{m}>', 'exec'), ns)
        names.append(m)
    for fn in extra_funcs:
        code = func_src(src, fn)
        if code is None:
            raise RuntimeError(f'找不到函数 {fn}')
        exec(compile(code, f'<{fn}>', 'exec'), ns)
    return ns, names


# ── 设备判据的桩（本验收不测设备可用性本身，只测「启动时会不会初始化」）──
class _StubDeviceConfig:
    @staticmethod
    def is_cuda_device(dev):
        return str(dev).upper().startswith('CUDA') or str(dev).upper().startswith('GPU.1')

    @staticmethod
    def has_cuda_plugin():
        return False

    @staticmethod
    def available_devices():
        return ['NPU', 'GPU.0']


DEVICE_STUBS = {
    'device_config': _StubDeviceConfig,
    '_is_intel_gpu': lambda dev: str(dev).upper().startswith('GPU.0'),
    '_cuda_tts_available': lambda: False,
}


def func_src(src, fn_name):
    """抽出模块级函数源码。"""
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == fn_name:
            lines = src.splitlines()
            return textwrap.dedent('\n'.join(lines[node.lineno - 1:node.end_lineno]))
    return None


def bind(app, ns, names):
    """把 exec 出来的自由函数绑成假实例的方法。"""
    import types
    for n in names:
        setattr(app, n, types.MethodType(ns[n], app))
    return app


def exec_method(src, cls_name, meth_name, ns_extra=None, extra_imports=()):
    """把某个方法 exec 到独立命名空间（绑成自由函数），返回可调用对象。"""
    ns, names = exec_methods(src, cls_name, [meth_name], ns_extra, extra_imports)
    return ns[meth_name]


# ────────────────────────────────────────────────────────────────────
# 假实例（stub）
# ────────────────────────────────────────────────────────────────────
class FakeVar:
    def __init__(self, value=None):
        self._v = value

    def get(self):
        return self._v

    def set(self, v):
        self._v = v


class FakeMT:
    def __init__(self, state='idle'):
        self.state = state
        self.targets = []

    def set_target(self, t):
        self.targets.append(t)
        return True


def make_app(stub_tts_service=None, mt_state='idle'):
    """造一个最小 App 假实例（够 `_on_tts_toggled` / `_maybe_startup_tts` 跑）。"""
    app = type('FakeApp', (), {})()
    app.var_tts_on = FakeVar(True)
    app.var_tts_note = FakeVar('')
    app.var_status = FakeVar('')
    app.var_tts_voice = FakeVar('预设 A')
    app.var_tts_out = FakeVar('（未找到输出设备）')
    app.tts = None
    app.mt = FakeMT(mt_state)
    app._dev_avail = ['NPU']
    app._dev_choices = {}
    app._tts_precision = 'f32'
    app._tts_voice_back = {'预设 A': 'A', '跟随说话人（克隆·实验）': 'follow_speaker'}
    app._out_label_back = {}
    app._clone_enabled = False
    app._clone_lock = __import__('threading').Lock()
    app._clone_frames = []
    app._clone_voiced_s = 0.0
    app._clone_sent_voiced_s = 0.0
    app._clone_last_update = 0.0
    app._clone_status = ''
    app._asr_ready = False
    app._asr_failed = False
    app._tts_startup_pending = False
    app._tts_startup_done = False
    app.cb_asr_combo = type('C', (), {'configure': staticmethod(lambda *a, **k: None)})()
    app.btn = type('C', (), {'configure': staticmethod(lambda *a, **k: None)})()
    # 🔴 `_on_tts_toggled` 里用 `getattr(self.args, 'tts_device', 'NPU')`
    #   ⇒ 假实例必须带 args。
    app.args = type('A', (), {'tts_device': 'NPU', 'tts_precision': 'f32',
                              'tts_voice': 'A', 'autostart': False})()
    app.logs = []
    app._ui_log = lambda m: app.logs.append(m)
    app.n_toggled = 0
    app._stub = stub_tts_service
    return app


def install_stub_service(ns, stub):
    """把 `tts_service.TTSService` 换成假类（记录实例化次数）。

    🔴🔴 `_on_tts_toggled` 里是**函数内 import**（`from tts_service import TTSService`）
       ⇒ 只往 `ns` 里塞不够，**必须注入 `sys.modules`**，
       否则函数体仍然去 import 真模块 ⇒ 反而会把「import 失败」误当成
       「初始化失败」⇒ **判据假通过**（本脚本首跑就踩到）。
    """
    mod = type('M', (), {})()
    counter = {'n': 0}

    class FakeSvc:
        def __init__(self, **kw):
            counter['n'] += 1
            self.kw = kw
            self.state = 'loading'
            self.device = kw.get('device')
            self.precision = kw.get('precision')
            self.voice = kw.get('voice')

        def close(self):
            pass

    if stub == 'raise':
        class Boom(FakeSvc):
            def __init__(self, **kw):
                raise RuntimeError('stub-boom')

        mod.TTSService = Boom
    else:
        mod.TTSService = FakeSvc
    ns['tts_service'] = mod
    sys.modules['tts_service'] = mod
    return counter


# ────────────────────────────────────────────────────────────────────
# 1) 静态结构判据
# ────────────────────────────────────────────────────────────────────
def test_static_structure():
    src = load_src()
    ok = True

    # ① `_on_tts_toggled` 仍是**唯一**的初始化入口（启动流程不许另写一套）
    calls = re.findall(r'_on_tts_toggled\s*\(', src)
    n_def = len(re.findall(r'def _on_tts_toggled\s*\(', src))
    rec('static: 存在且仅有一个 _on_tts_toggled 定义', n_def == 1,
        f'def 数={n_def}')

    # ② 启动流程里**调用**了它（不是只定义）
    startup_call = re.search(
        r'def _maybe_startup_tts\([^)]*\):(.*?)(?=\n    def |\Z)',
        src, re.S)
    ok2 = bool(startup_call and '_on_tts_toggled()' in startup_call.group(1))
    rec('static: 启动流程调用 _on_tts_toggled()（同一入口）', ok2,
        'found' if ok2 else 'NOT FOUND')
    ok = ok and ok2

    # ③ 启动待办有「只调用一次」的守卫
    ok3 = ('_tts_startup_done' in src
           and re.search(r'_tts_startup_done\s*=\s*True', src) is not None)
    rec('static: 有 _tts_startup_done（只初始化一次）', ok3)
    ok = ok and ok3

    # ④ 初始化失败 ⇒ 开关自动回 False（在 _on_tts_toggled 的 except 分支里）
    m = method_src(src, 'App', '_on_tts_toggled')
    ok4 = bool(m and 'self.var_tts_on.set(False)' in m)
    rec('static: _on_tts_toggled 失败分支把开关置回 False', ok4)
    ok = ok and ok4

    # ⑤ 顺序：ASR 就绪后才登记
    ok5 = ('_arm_startup_tts' in src
           and re.search(r'def _arm_startup_tts\(', src) is not None
           and re.search(r'def _engine_ready\(.*?_arm_startup_tts\(\)',
                         src, re.S) is not None)
    rec('static: _engine_ready 里登记启动待办（ASR 就绪之后）', ok5)
    ok = ok and ok5

    # ⑥ 其它默认开启的开关：不得有「默认值 True 但无启动初始化」
    #    var_overlay(True) 有 command=_toggle_overlay 且启动时显式调过；
    #    var_show_spk(True) 是纯显示开关（无副作用）。
    ok6 = ('self._toggle_overlay()' in src
           and 'command=self._toggle_overlay' in src
           and 'command=self._on_mt_draft_toggled' in src
           and 'self.mt.set_draft(self.var_mt_draft.get())' in src)
    rec('static: 其它默认开启开关（overlay/draft）启动时已生效', ok6)
    ok = ok and ok6

    # ⑦ GUI 的「显示说话人」默认 True 且无 command（纯显示）⇒ 不需要初始化
    ok7 = re.search(r'var_show_spk\s*=\s*tk\.BooleanVar\(value=True\)', src) \
        is not None
    rec('static: var_show_spk 默认 True（纯显示，无副作用）', ok7)
    ok = ok and ok7
    return ok


# ────────────────────────────────────────────────────────────────────
# 2) 行为判据（exec + 假实例）
# ────────────────────────────────────────────────────────────────────
def test_behavior():
    src = load_src()
    ok = True

    # ── B1：ASR 未就绪 ⇒ **不**初始化 ────────────────────────────
    ns = {}
    counter = install_stub_service(ns, None)
    nsm, namesm = exec_methods(
        src, 'App', ['_maybe_startup_tts', '_on_tts_toggled', '_tts_startup_failed'],
        ns_extra={'time': __import__('time')},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app = make_app()
    bind(app, nsm, namesm)
    app._asr_ready = False
    app._tts_startup_pending = True
    app._maybe_startup_tts()
    ok_b1 = (counter['n'] == 0 and app._tts_startup_pending is True)
    rec('B1: ASR 未就绪 ⇒ 不初始化 TTS（等顺序）', ok_b1,
        f'svc_instances={counter["n"]} pending={app._tts_startup_pending}')
    ok = ok and ok_b1

    # ── B2：ASR 就绪但 MT 还在 loading ⇒ **不**初始化 ──────────
    ns2 = {}
    counter2 = install_stub_service(ns2, None)
    ns2m, names2m = exec_methods(
        src, 'App', ['_maybe_startup_tts', '_on_tts_toggled', '_tts_startup_failed'],
        ns_extra={'time': __import__('time')},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app2 = make_app(mt_state='loading')
    bind(app2, ns2m, names2m)
    app2._asr_ready = True
    app2._tts_startup_pending = True
    app2._maybe_startup_tts()
    ok_b2 = (counter2['n'] == 0 and app2._tts_startup_pending is True)
    rec('B2: MT 还在 loading ⇒ 不初始化 TTS（防并行编译）', ok_b2,
        f'svc_instances={counter2["n"]}')
    ok = ok and ok_b2

    # ── B3：ASR 就绪 + MT 就绪 ⇒ **初始化，且只一次** ───────────
    ns3 = {}
    counter3 = install_stub_service(ns3, None)
    ns3m, names3 = exec_methods(
        src, 'App', ['_maybe_startup_tts', '_on_tts_toggled', '_tts_startup_failed'],
        ns_extra={'time': __import__('time')},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app3 = make_app(mt_state='ready')
    bind(app3, ns3m, names3)
    app3._asr_ready = True
    app3._tts_startup_pending = True
    app3._maybe_startup_tts()
    ok_b3a = counter3['n'] == 1
    rec('B3a: ASR+MT 就绪 ⇒ 初始化 TTS 一次', ok_b3a,
        f'svc_instances={counter3["n"]}')
    # 再调 5 次 ⇒ 不得重复初始化
    for _ in range(5):
        app3._maybe_startup_tts()
    ok_b3b = counter3['n'] == 1
    rec('B3b: 重复轮询 5 次 ⇒ 仍只初始化 1 次（不重复起 worker）', ok_b3b,
        f'svc_instances={counter3["n"]}')
    ok = ok and ok_b3a and ok_b3b

    # ── B4：初始化抛异常 ⇒ 开关自动回 False ─────────────────────
    ns4 = {}
    install_stub_service(ns4, 'raise')
    ns4m, names4 = exec_methods(
        src, 'App', ['_maybe_startup_tts', '_on_tts_toggled', '_tts_startup_failed'],
        ns_extra={'time': __import__('time')},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app4 = make_app(mt_state='ready')
    bind(app4, ns4m, names4)
    app4._asr_ready = True
    app4._tts_startup_pending = True
    app4._maybe_startup_tts()
    ok_b4 = (app4.var_tts_on.get() is False
             and app4.var_tts_note.get().startswith('🔴'))
    rec('B4: 初始化失败 ⇒ 开关自动回 False 且写明原因', ok_b4,
        f'on={app4.var_tts_on.get()} note={app4.var_tts_note.get()[:80]}')
    ok = ok and ok_b4

    # ── B5：`_on_tts_toggled` 成功 ⇒ 不动开关（保持开启）──────────
    ns5 = {}
    install_stub_service(ns5, None)
    ns5m, names5 = exec_methods(
        src, 'App', ['_on_tts_toggled'],
        ns_extra={},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app5 = make_app()
    bind(app5, ns5m, names5)
    app5._on_tts_toggled()
    ok_b5 = app5.var_tts_on.get() is True and app5.tts is not None
    rec('B5: _on_tts_toggled 成功 ⇒ 开关保持开启、worker 已建', ok_b5,
        f'tts={type(app5.tts).__name__ if app5.tts else None}')
    ok = ok and ok_b5

    # ── B6：`_on_tts_toggled` 抛异常 ⇒ 开关自动回 False ─────────
    ns6 = {}
    install_stub_service(ns6, 'raise')
    ns6m, names6 = exec_methods(
        src, 'App', ['_on_tts_toggled'],
        ns_extra={},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app6 = make_app()
    bind(app6, ns6m, names6)
    app6._on_tts_toggled()
    ok_b6 = (app6.var_tts_on.get() is False
             and '🔴' in app6.var_tts_note.get())
    rec('B6: _on_tts_toggled 异常 ⇒ 开关自动回 False', ok_b6,
        f'on={app6.var_tts_on.get()} note={app6.var_tts_note.get()[:80]}')
    ok = ok and ok_b6

    # ── B7：用户主动关掉 ⇒ 撤掉启动待办（不会被稍后偷偷打开）────
    ns7 = {}
    install_stub_service(ns7, None)
    ns7m, names7 = exec_methods(
        src, 'App', ['_on_tts_toggled'],
        ns_extra={},
        extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
        extra_defs=DEVICE_STUBS)
    app7 = make_app()
    bind(app7, ns7m, names7)
    app7._tts_startup_pending = True
    app7.var_tts_on.set(False)
    app7._on_tts_toggled()
    ok_b7 = app7._tts_startup_pending is False
    rec('B7: 用户主动关闭 ⇒ 撤掉启动待办', ok_b7,
        f'pending={app7._tts_startup_pending}')
    ok = ok and ok_b7

    # ── B8：`_engine_failed` ⇒ 开关自动回 False ──────────────────
    # 🔴🔴🔴 **脚本自身的坑（本轮实测踩到）**：
    #   `_engine_failed` 内部有 `from tkinter import messagebox`
    #   ⇒ **函数内的 import 会覆盖 ns_extra 里的桩**
    #   ⇒ 真 `messagebox.showerror` 会弹**模态框** ⇒ **脚本挂死**
    #     （表现为 SIGTERM / 超时，且**看起来像产品缺陷**）。
    #   ⇒ 修法：把**假的 tkinter 模块**塞进 `sys.modules`，
    #     这样函数内的 `from tkinter import messagebox` 拿到的是桩。
    _fake_tk = _make_fake_tkinter()
    _old_tk = sys.modules.get('tkinter')
    sys.modules['tkinter'] = _fake_tk
    try:
        ef = exec_method(src, 'App', '_engine_failed',
                         ns_extra={'messagebox': type('M', (), {
                             'showerror': staticmethod(lambda *a, **k: None)})})
        app8 = make_app()
        app8._tts_startup_pending = True
        ef(app8, 'boom')
    finally:
        if _old_tk is not None:
            sys.modules['tkinter'] = _old_tk
        else:
            sys.modules.pop('tkinter', None)
    ok_b8 = (app8.var_tts_on.get() is False
             and app8._tts_startup_pending is False)
    rec('B8: ASR 加载失败 ⇒ 语音输出自动关闭', ok_b8,
        f'on={app8.var_tts_on.get()}')
    ok = ok and ok_b8

    # ── B9：`_engine_ready` ⇒ 登记启动待办 ───────────────────────
    er = exec_method(src, 'App', '_engine_ready',
                     ns_extra={'ENGINES': {'k': {'label': '测试引擎'}}})
    app9 = make_app()
    app9.args = type('A', (), {'autostart': False})()
    app9.engine_key = 'x'
    app9.cb_asr_combo = type('C', (), {'configure': staticmethod(lambda *a, **k: None)})()
    app9.btn = type('C', (), {'configure': staticmethod(lambda *a, **k: None)})()
    app9._cur_mt_target = lambda: 'off'
    app9._arm_startup_tts = lambda: setattr(app9, '_armed', True)
    eng = type('E', (), {'load_s': 1.0})()
    er(app9, 'k', eng, 'NPU')
    ok_b9 = getattr(app9, '_armed', False) is True
    rec('B9: _engine_ready ⇒ 登记启动待办', ok_b9)
    ok = ok and ok_b9

    return ok


# ────────────────────────────────────────────────────────────────────
# 3) 反证：把修复退回去，判据必须 FAIL
# ────────────────────────────────────────────────────────────────────
def test_counterevidence():
    """把 `_maybe_startup_tts` 的初始化调用删掉 ⇒ B3 必须 FAIL。"""
    src = load_src()
    # 整块删除「调用 _on_tts_toggled()」的那一段（带上下文）
    mutated = src.replace(
        "        try:\n"
        "            self._on_tts_toggled()\n"
        "        except Exception as e:\n"
        "            self._ui_log(f'[tts] 启动初始化异常：{type(e).__name__}: {e}')\n"
        "            self._tts_startup_failed(e)\n",
        "        try:\n"
        "            pass\n"
        "        except Exception as e:\n"
        "            pass\n",
        1)
    changed = mutated != src
    rec('反证准备: 注入「启动流程不再调用初始化」', changed,
        'mutated' if changed else 'PATTERN NOT FOUND ⇒ 反证无效')
    if not changed:
        return False
    ns = {}
    counter = install_stub_service(ns, None)
    try:
        nsm, namesm = exec_methods(
            mutated, 'App',
            ['_maybe_startup_tts', '_on_tts_toggled', '_tts_startup_failed'],
            ns_extra={'time': __import__('time')},
            extra_funcs=('_tts_device_problem', '_first_usable_tts_device'),
            extra_defs=DEVICE_STUBS)
    except Exception as e:
        rec('反证: 变异后脚本仍可执行', False, f'{type(e).__name__}: {e}')
        return False
    app = make_app(mt_state='ready')
    bind(app, nsm, namesm)
    app._asr_ready = True
    app._tts_startup_pending = True
    app._maybe_startup_tts()
    failed_as_expected = (counter['n'] == 0)
    rec('反证: 启动流程不调用初始化 ⇒ 判据 FAIL（判据不恒真）',
        failed_as_expected, f'svc_instances={counter["n"]} (期望 0)')
    return failed_as_expected


# ────────────────────────────────────────────────────────────────────
# 4) 基线反证：修前的源码必须 FAIL
# ────────────────────────────────────────────────────────────────────
BASE_COMMIT = 'f724769'


def test_baseline():
    """修前（BASE_COMMIT）的源码 ⇒ 静态判据必须 FAIL。"""
    try:
        r = subprocess.run(
            ['git', '-C', REPO, 'show', f'{BASE_COMMIT}:live_caption/live_caption_app.py'],
            capture_output=True, timeout=120)
    except Exception as e:
        rec('基线: 取出修前源码', False, f'{type(e).__name__}: {e}')
        return False
    if r.returncode != 0:
        rec('基线: 取出修前源码', False, r.stderr.decode('utf-8', 'replace')[:300])
        return False
    old = r.stdout.decode('utf-8')
    rec('基线: 取出修前源码', True, f'{len(old)} 字符')
    has = ('_maybe_startup_tts' in old
           and '_tts_startup_done' in old
           and re.search(r'def _maybe_startup_tts\(', old) is not None)
    rec('基线: 修前**没有**启动初始化机制 ⇒ 判据 FAIL', not has,
        '修前确实缺少该机制' if not has else '修前居然已有（基线选错）')
    return not has


def main():
    print('=' * 70)
    print('app139 — APP-041 验收（启动时语音输出默认开启必须真的初始化）')
    print(f'被测源码: {APP_PY}')
    print(f'解释器:   {sys.executable}  (Python {sys.version.split()[0]})')
    print('=' * 70)

    groups = []
    groups.append(('静态结构', test_static_structure()))
    groups.append(('行为', test_behavior()))
    groups.append(('基线反证', test_baseline()))
    groups.append(('反证（判据不恒真）', test_counterevidence()))

    n_pass = sum(1 for r in RESULTS if r['ok'])
    n_fail = len(RESULTS) - n_pass
    print('-' * 70)
    print(f'REAL: {n_pass}/{len(RESULTS)} PASS, {n_fail} FAIL')
    for nm, gok in groups:
        print(f'  组 [{nm}]: {"PASS" if gok else "FAIL"}')

    evidence = {
        'script': 'app139_app041_startup_tts.py',
        'correction': 'APP-041',
        'target': APP_PY,
        'python': sys.version,
        'interpreter': sys.executable,
        'total': len(RESULTS),
        'n_pass': n_pass,
        'n_fail': n_fail,
        'groups': {nm: bool(g) for nm, g in groups},
        'results': RESULTS,
        'verdict': (n_fail == 0 and all(g for _, g in groups)),
    }
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(evidence, f, ensure_ascii=False, indent=2, allow_nan=False)
    print(f'证据落盘: {OUT} ({os.path.getsize(OUT)} B)')
    print('VERDICT:', 'PASS' if evidence['verdict'] else 'FAIL')
    return 0 if evidence['verdict'] else 1


if __name__ == '__main__':
    sys.exit(main())
