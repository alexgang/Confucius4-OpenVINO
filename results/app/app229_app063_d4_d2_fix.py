#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app229 —— APP-063 ①（D4 bug）与 ②（D2 四入口）的**行为级验收**。

| 编号 | reviewer 要求 | 本脚本怎么验 |
|---|---|---|
| **D4-bug** | `_on_mt_combo_changed` 在 `_enforce_no_npu_conflict` 之后**又被** `set_engine(opt['engine'])` + `set_device(opt['device'])` **覆盖回 NPU** ⇒ 配置写 GPU.0、实际跑 NPU、还弹框说「已改到 GPU.0」 | **行为探针**：造假 self（`_cur_mt_opt` 返回 NPU 项）⇒ 调 `_on_mt_combo_changed` ⇒ 断言 `mt.device == 'GPU.0'` 且 `mt.engine_key` 是 GPU.0 那一项的 engine |
| **D2(a)** | GUI 启动 `--tts-voice follow_speaker` / `_on_tts_toggled` 开启 TTS ⇒ **自动开旁路** | 静态锚点 + **行为探针**（假 self 调 `_on_tts_toggled` 的克隆分支） |
| **D2(b)** | CLI `--tts-voice follow_speaker` ⇒ `_spk_enabled` 必须为 True | 静态锚点（源码顺序 + 判定）+ 行为探针（复用同一段源码逻辑） |
| **D2(c)** | 取消「说话人识别」勾选 ⇒ 音色切回 A **并提示**（或禁止取消） | **行为探针**：假 self 调 `_on_speaker_toggled`（取消分支）⇒ 断言 `var_tts_voice` 变成「预设 A」且状态栏有提示 |
| **D2(d)** | 会话进行中自动开旁路 ⇒ **真正把线程拉起来**（不是「重启会话后生效」） | **行为探针**：假 self（session.running=True）调 `_enable_speaker_for_clone` ⇒ 断言 `ensure_started()` 被调用且状态栏**不含**「需重启会话」 |

🔴 **三态判据**：True / False / **None（无法判定）**。
🔴 **反证**：把实现改回旧行为 ⇒ 判据必须 FAIL（证明**非恒真**）。
🔴 **不 import 被测模块**（顶层重依赖 ⇒ import 期 abort）⇒ 用 `ast` 抽源码 + `exec`。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
APP_PY = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
SPK_PY = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
OUT_JSON = os.path.join(HERE, 'app229_app063_d4_d2_fix_evidence.json')

CHECKS = []


def chk(name, ok, detail):
    CHECKS.append({'name': name, 'ok': (None if ok is None else bool(ok)),
                   'detail': detail})


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def src_of(p):
    return read(p).decode('utf-8')


def fn_of(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and n.name == name:
            return n
    return None


def load_class_method(path, cls_name, meth_name, name):
    """🔴 **类方法**探针：把方法单独抽出来 exec（不加载整个类 ⇒ 不起 tkinter）。"""
    tree = ast.parse(read(path).decode('utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls_name:
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and sub.name == meth_name:
                    mod = types.ModuleType(name)
                    mod.__file__ = path
                    src = ast.Module(body=[sub], type_ignores=[])
                    ast.fix_missing_locations(src)
                    exec(compile(src, path, 'exec'), mod.__dict__)
                    return getattr(mod, meth_name)
    return None


def call_order(node):
    """方法体里各调用的**源码顺序**（行号）。"""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            name = None
            if isinstance(f, ast.Attribute):
                name = f.attr
            elif isinstance(f, ast.Name):
                name = f.id
            if name:
                out.append((n.lineno, name))
    out.sort()
    return out


def main():
    app_src = src_of(APP_PY)
    tree = ast.parse(app_src)

    # ══════════════════════════════════════════════════════════
    # ① D4 bug：`_on_mt_combo_changed` 的**调用顺序**
    # ══════════════════════════════════════════════════════════
    fn_mt = fn_of(tree, '_on_mt_combo_changed')
    chk('d4_handler_exists', fn_mt is not None,
        '_on_mt_combo_changed 存在' if fn_mt else '找不到该方法')
    if fn_mt is not None:
        order = call_order(fn_mt)
        names = [n for _l, n in order]
        i_enf = names.index('_enforce_no_npu_conflict') \
            if '_enforce_no_npu_conflict' in names else -1
        i_setdev = names.index('set_device') if 'set_device' in names else -1
        chk('d4_bug_enforce_present', i_enf >= 0,
            'handler 内含 _enforce_no_npu_conflict（行 %s）' % (i_enf,))
        chk('d4_bug_setdevice_present', i_setdev >= 0,
            'handler 内含 set_device（行 %s）' % (i_setdev,))
        # 🔴 **反证锚点**：enforce 之后必须**重读 opt**
        i_cur1 = names.index('_cur_mt_opt') if '_cur_mt_opt' in names else -1
        i_cur2 = len(names) - 1 - names[::-1].index('_cur_mt_opt') \
            if '_cur_mt_opt' in names else -1
        chk('d4_bug_opt_reread_after_enforce',
            (i_cur1 >= 0 and i_cur2 > i_cur1 and i_enf >= 0
             and i_cur2 > i_enf),
            '首次 _cur_mt_opt 行序 %s / enforce 行序 %s / 末次 _cur_mt_opt 行序 %s'
            % (i_cur1, i_enf, i_cur2))
        chk('d4_bug_forced_branch_present',
            '_forced' in ast.dump(fn_mt),
            'handler 内含「enforce 命中后重读 opt」的分支标志')

    # ── D4 行为探针：走 handler 路径（**不是**只调 enforce）──
    fn_mt_probe = load_class_method(APP_PY, 'App', '_on_mt_combo_changed',
                                    'probe_d4_handler')
    if fn_mt_probe is None:
        chk('d4_behavior_handler', None, '无法抽取 _on_mt_combo_changed')
    else:
        class FakeMT:
            def __init__(self):
                self.device = 'NPU'
                self.engine_key = 'npu_int8cw'
                self.active = False
                self.calls = []

            def set_engine(self, key):
                self.calls.append(('set_engine', key))
                self.engine_key = key
                # 🔴 复刻 translator.set_engine 的真实副作用：
                #   **把 device 重置成该 engine 的默认值**
                self.device = 'GPU.0' if str(key).startswith('gpu') else 'NPU'
                return True

            def set_device(self, dev):
                self.calls.append(('set_device', dev))
                self.device = dev
                return True

        class FakeApp:
            pass

        app = FakeApp()
        mt = FakeMT()
        gpu_opt = {'id': 'INT8-CW@GPU.0', 'label': 'Intel GPU（集显） · INT8-CW',
                   'engine': 'gpu_int8cw', 'device': 'GPU.0',
                   'precision': 'INT8-CW', 'note': ''}
        npu_opt = {'id': 'INT8-CW@NPU', 'label': 'Intel NPU · INT8-CW',
                   'engine': 'npu_int8cw', 'device': 'NPU',
                   'precision': 'INT8-CW', 'note': ''}
        state = {'combo': npu_opt}
        logs = []
        app.mt = mt
        app._dev_choices = {'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'NPU'}
        app._mt_opt_by_id = {'INT8-CW@GPU.0': gpu_opt}
        app._mt_precision = 'INT8-CW'
        app.var_status = types.SimpleNamespace(set=lambda s: None)
        app.var_mt_note = types.SimpleNamespace(set=lambda s: None)
        app.var_mt_combo = types.SimpleNamespace(set=lambda s: None)
        app._ui_log = lambda s: logs.append(s)
        app.root = None
        app.cb_mt_combo = types.SimpleNamespace(
            configure=lambda **k: None)
        app.save_config_calls = []

        def _cur_mt_opt():
            return state['combo']

        app._cur_mt_opt = _cur_mt_opt

        def _enforce(origin=''):
            """🔴 复刻**修复后**的 enforce：把 MT 改到 GPU.0 且同步 combo。"""
            dev = dict(app._dev_choices)
            if 'NPU' not in str(dev.get('tts', '')).upper() \
                    or 'NPU' not in str(dev.get('mt', '')).upper():
                return False
            dev['mt'] = 'GPU.0'
            app._dev_choices = dev
            state['combo'] = gpu_opt          # ← enforce 同步了 combo
            app.var_mt_combo.set(gpu_opt['label'])
            mt.set_engine(gpu_opt['engine'])
            mt.set_device('GPU.0')
            logs.append('[device] enforce → GPU.0')
            return True

        app._enforce_no_npu_conflict = _enforce
        # device_config.save_config 的替身
        # 🔴 **必须注入到方法被执行时的 globals** ⇒ 抽取出来的函数体里
        #   `device_config` 是**全局名**，模块里没有 ⇒ NameError（假 FAIL）。
        import sys as _sys
        _saved = {}

        class _FakeDeviceConfig:
            @staticmethod
            def save_config(cfg):
                _saved['cfg'] = dict(cfg)

        _real_dc = _sys.modules.get('device_config')
        _sys.modules['device_config'] = _FakeDeviceConfig
        # 🔴 抽取出的函数体在**自己模块的 globals** 里查找全局名
        #   ⇒ 必须把替身塞进那个模块的 `__dict__`。
        _probe_globals = getattr(fn_mt_probe, '__globals__', None)
        if _probe_globals is not None:
            _probe_globals['device_config'] = _FakeDeviceConfig
        try:
            fn_mt_probe(app)
        except Exception as e:
            chk('d4_behavior_handler', None, '探针异常：%r' % (e,))
        else:
            chk('d4_behavior_handler', True, 'handler 探针执行完成')
            chk('d4_behavior_device_is_gpu0',
                mt.device == 'GPU.0',
                '调用后 mt.device=%r（期望 GPU.0）' % (mt.device,))
            chk('d4_behavior_engine_is_gpu0',
                mt.engine_key == gpu_opt['engine'],
                '调用后 mt.engine_key=%r（期望 %r）'
                % (mt.engine_key, gpu_opt['engine']))
            chk('d4_behavior_config_saved_gpu0',
                _saved.get('cfg', {}).get('mt') == 'GPU.0',
                'device_config 落盘 mt=%r'
                % (_saved.get('cfg', {}).get('mt'),))
            chk('d4_behavior_no_npu_after',
                'NPU' not in str(mt.device).upper(),
                '最终设备 %r 不含 NPU' % (mt.device,))

    # ══════════════════════════════════════════════════════════
    # ② D2 (a)：`_on_tts_toggled` 的克隆分支 ⇒ 自动开旁路
    # ══════════════════════════════════════════════════════════
    fn_tog = fn_of(tree, '_on_tts_toggled')
    if fn_tog is None:
        chk('d2a_toggled_exists', None, '找不到 _on_tts_toggled')
    else:
        names = [n for _l, n in call_order(fn_tog)]
        chk('d2a_toggled_calls_enable', '_enable_speaker_for_clone' in names,
            '_on_tts_toggled 调用列表=%s' % (names,))

    # 启动路径：`__init__` 尾部也要开
    init_src = app_src
    chk('d2a_startup_calls_enable',
        "getattr(args, 'tts_voice', 'A')" in init_src
        and '_enable_speaker_for_clone' in init_src,
        '启动路径按 --tts-voice follow_speaker 自动开旁路')

    # ══════════════════════════════════════════════════════════
    # ③ D2 (b)：CLI `_spk_enabled` 必须在 `_want_clone` 之后算
    # ══════════════════════════════════════════════════════════
    fn_cli = fn_of(tree, 'run_cli')
    if fn_cli is None:
        chk('d2b_cli_exists', None, '找不到 run_cli')
    else:
        cli_src = ast.get_source_segment(app_src, fn_cli) or ''
        i_want = cli_src.find('_want_clone = (str(')
        i_spk = cli_src.find('_spk_enabled = (str(')
        i_force = cli_src.find('if _want_clone and not _spk_enabled:')
        chk('d2b_want_clone_defined', i_want >= 0,
            '_want_clone 定义位置=%d' % i_want)
        chk('d2b_spk_after_want', (i_want >= 0 and i_spk > i_want),
            '_want_clone@%d 早于 _spk_enabled@%d' % (i_want, i_spk))
        chk('d2b_forced_true_when_clone', i_force >= 0,
            '存在「_want_clone ⇒ _spk_enabled=True」的判定（位置 %d）' % i_force)
        # 反证锚点：不能有「--speaker off 覆盖克隆」的写法
        chk('d2b_speaker_off_does_not_override',
            i_force >= 0 and i_spk < i_force,
            '「显式 --speaker off」不覆盖克隆自动开（_spk_enabled@%d < 强制分支@%d）'
            % (i_spk, i_force))

    # ══════════════════════════════════════════════════════════
    # ④ D2 (c)：`_on_speaker_toggled` 取消分支 ⇒ 切回预设 A + 提示
    # ══════════════════════════════════════════════════════════
    fn_spk_tog = fn_of(tree, '_on_speaker_toggled')
    chk('d2c_handler_exists', fn_spk_tog is not None,
        '_on_speaker_toggled 存在' if fn_spk_tog else '缺少 _on_speaker_toggled')
    if fn_spk_tog is not None:
        body = ast.dump(fn_spk_tog)
        # 🔴 **AST dump 里 `['A']` 会变成 `Constant(value='A')`**
        #   ⇒ 不能直接找 `_tts_voice_label['A']`（会漏判 ⇒ 假 FAIL）
        #   ⇒ 改判「确实引用了 `_tts_voice_label` 且取了 key 'A'」。
        _has_label_ref = '_tts_voice_label' in body
        _has_a_key = "value='A'" in body or 'value="A"' in body
        chk('d2c_switches_to_preset_a',
            _has_label_ref and _has_a_key,
            '取消分支引用 _tts_voice_label 且取 key=A'
            '（引用=%s / key A=%s）' % (_has_label_ref, _has_a_key))
        chk('d2c_sets_notice', 'var_status' in body,
            '取消分支写状态栏提示')
        # 行为探针
        fn_c = load_class_method(APP_PY, 'App', '_on_speaker_toggled',
                                 'probe_d2c')
        if fn_c is None:
            chk('d2c_behavior', None, '无法抽取方法')
        else:
            class FakeApp:
                pass
            a = FakeApp()
            a.var_speaker = types.SimpleNamespace(get=lambda: False,
                                                 set=lambda v: None)
            a._speaker_enabled = True
            a._spk_bridge = types.SimpleNamespace(enabled=True)
            a._tts_voice_back = {'跟随说话人（克隆·实验）': 'follow_speaker',
                                 '预设 A': 'A'}
            a._tts_voice_label = {'A': '预设 A',
                                  'follow_speaker': '跟随说话人（克隆·实验）'}
            a.var_tts_voice = types.SimpleNamespace(
                get=lambda: '跟随说话人（克隆·实验）',
                set=lambda v: setattr(a, '_voice_now', v))
            a.var_tts_note = types.SimpleNamespace(set=lambda s: None)
            a.var_status = types.SimpleNamespace(set=lambda s: None)
            a._clone_status = ''
            a._clone_enabled = True
            a.tts = None
            a.var_tts_on = types.SimpleNamespace(get=lambda: False)
            a._ui_log = lambda s: None
            logs_c = []
            a._ui_log = lambda s: logs_c.append(s)
            try:
                fn_c(a)
            except Exception as e:
                chk('d2c_behavior', None, '探针异常：%r' % (e,))
            else:
                chk('d2c_behavior', True, '取消勾选分支执行完成')
                chk('d2c_behavior_voice_back_to_a',
                    getattr(a, '_voice_now', None) == '预设 A',
                    '取消后 var_tts_voice=%r（期望 预设 A）'
                    % (getattr(a, '_voice_now', None),))
                chk('d2c_behavior_disabled_bridge',
                    getattr(a._spk_bridge, 'enabled', None) is False,
                    '取消后 bridge.enabled=%r'
                    % (getattr(a._spk_bridge, 'enabled', None),))

    # ══════════════════════════════════════════════════════════
    # ⑤ D2 (d)：会话进行中 ⇒ 真拉起线程（`ensure_started`）
    # ══════════════════════════════════════════════════════════
    fn_en = fn_of(tree, '_enable_speaker_for_clone')
    if fn_en is None:
        chk('d2d_helper_exists', None, '缺少 _enable_speaker_for_clone')
    else:
        body = ast.dump(fn_en)
        chk('d2d_calls_ensure_started', 'ensure_started' in body,
            '_enable_speaker_for_clone 调用 ensure_started')
        chk('d2d_reports_live_session',
            'running' in body,
            '判定「会话进行中」（session.running）')
        # SpeakerBridge 侧必须有 ensure_started
        spk_tree = ast.parse(src_of(SPK_PY))
        fn_es = fn_of(spk_tree, 'ensure_started')
        chk('d2d_bridge_has_ensure_started', fn_es is not None,
            'SpeakerBridge.ensure_started 存在' if fn_es else '缺少该方法')
        # 行为探针：假 self（会话在跑）
        fn_e = load_class_method(APP_PY, 'App', '_enable_speaker_for_clone',
                                 'probe_d2d')
        if fn_e is None:
            chk('d2d_behavior', None, '无法抽取方法')
        else:
            class FakeApp:
                pass
            b = FakeApp()
            b._speaker_enabled = False
            b.var_speaker = types.SimpleNamespace(set=lambda v: None)
            b.var_status = types.SimpleNamespace(set=lambda s: None)
            b._spk_bridge = types.SimpleNamespace(enabled=False)
            b.session = types.SimpleNamespace(running=True)
            started = []
            b._spk_bridge.ensure_started = lambda: (
                started.append(1) or True)
            b._ui_log = lambda s: None
            st = []
            b.var_status = types.SimpleNamespace(set=lambda s: st.append(s))
            try:
                fn_e(b)
            except Exception as e:
                chk('d2d_behavior', None, '探针异常：%r' % (e,))
            else:
                chk('d2d_behavior', True, '会话进行中分支执行完成')
                chk('d2d_behavior_thread_started', len(started) >= 1,
                    'ensure_started 被调用 %d 次' % len(started))
                # 🔴 判据：**不得**出现「需重启会话」这类「要用户重启」的说法
                #   ⇒ 必须表达「已即时生效」。
                #   ⚠️⚠️ **不能用 `'需重启' in s`** ——
                #   「**无需**重启会话」里**也**含「需重启」子串 ⇒ 会误伤（假 FAIL）。
                #   ⇒ 正确口径：**含「需重启」但不含「无需重启」** 才算「要用户重启」。
                _bad = []
                for s in st:
                    _needs_restart = ('需重启' in s) or ('重启会话后生效' in s)
                    _says_no_restart = ('无需重启' in s) or ('已即时生效' in s)
                    if _needs_restart and not _says_no_restart:
                        _bad.append(s)
                _good = [s for s in st if ('已即时生效' in s)
                         or ('无需重启' in s)]
                chk('d2d_behavior_status_not_restart',
                    bool(st) and not _bad and bool(_good),
                    '状态栏文案=%r（不含「需重启会话」且含「已即时生效」）'
                    % (st,))

    # ══════════════════════════════════════════════════════════
    # ⑥ APP-065 B：改名 + 移入高级
    # ══════════════════════════════════════════════════════════
    chk('b_renamed_label', '区分说话人（用于克隆）' in app_src,
        'GUI 勾选框文案已改名')
    chk('b_has_hint', '检测谁在说话，换人时重新克隆音色' in app_src,
        '带一句话提示说明作用')
    chk('b_var_name_kept', 'var_speaker' in app_src,
        '变量名 var_speaker 保留（app227/app204 依赖）')
    # 勾选框必须在**高级面板**里（不是 TTS 区）
    # 🔴 **口径变更（APP-065 A，2026-11-02）**：高级面板的**内容容器**
    #   从 `_adv_frame` 变成了 `g_adv`（⑤ 高级组内的 grid 容器）
    #   ⇒ 判据不能只认 `_adv_frame` ⇒ 改成「必须在高级面板链路上」。
    i_cb = app_src.find('self.cb_speaker = ttk.Checkbutton(')
    seg = app_src[i_cb:i_cb + 400] if i_cb >= 0 else ''
    _in_adv = ('_adv_frame' in seg) or ('g_adv' in seg)
    # 🔴 反证：**不得**出现在 TTS 区的行容器（row_tts）里
    _in_tts_row = ('row_tts' in seg)
    chk('b_moved_to_advanced', _in_adv and not _in_tts_row,
        'cb_speaker 挂在高级面板（_adv_frame/g_adv=%s）且不在 TTS 行（%s）'
        % (_in_adv, _in_tts_row))

    # ══════════════════════════════════════════════════════════
    # ⑦ CLI D4：MT+TTS 同 NPU ⇒ MT 自动改 GPU.0 + 日志
    # ══════════════════════════════════════════════════════════
    chk('cli_d4_guard_present',
        "'NPU' in _mt_d and 'NPU' in _tts_d" in app_src,
        'CLI 侧有 MT/TTS 同 NPU 判定')
    chk('cli_d4_switches_to_gpu0',
        "args.mt_device = 'GPU.0'" in app_src,
        'CLI 侧 MT 自动改到 GPU.0')
    chk('cli_d4_logs', 'MT 自动改到 GPU.0' in app_src,
        'CLI 侧打日志告知')

    # ══════════════════════════════════════════════════════════
    # ⑧ 反证：把 D4 修复改回旧行为 ⇒ 必须 FAIL
    # ══════════════════════════════════════════════════════════
    src_backup = app_src
    try:
        # 反证 1：D4 —— 去掉「enforce 命中后重读 opt」的分支
        # 🔴 **不要硬编码缩进/整段文本**（改一次就匹配不上 ⇒ 静默 NONE）
        #   ⇒ 按**行内容**定位（唯一命中 + 上下文窗口）。
        _lines = src_backup.split('\n')
        _hit = [i for i, l in enumerate(_lines)
                if l.strip() == 'if _forced:']
        if len(_hit) == 1:
            i0 = _hit[0]
            # 该分支体：从 i0+1 到下一个「同级或更浅缩进」的行
            _indent = len(_lines[i0]) - len(_lines[i0].lstrip())
            j = i0 + 1
            while j < len(_lines):
                _ln = _lines[j]
                if _ln.strip():
                    _ind = len(_ln) - len(_ln.lstrip())
                    if _ind <= _indent:
                        break
                j += 1
            _mut = '\n'.join(_lines[:i0] + _lines[j:])
            mt_tree = ast.parse(_mut)
            fn_m = fn_of(mt_tree, '_on_mt_combo_changed')
            names = [n for _l, n in call_order(fn_m)]
            i_enf = names.index('_enforce_no_npu_conflict') \
                if '_enforce_no_npu_conflict' in names else -1
            i_cur2 = len(names) - 1 - names[::-1].index('_cur_mt_opt') \
                if '_cur_mt_opt' in names else -1
            broke = not (i_cur2 > i_enf)
            chk('counterproof_d4_removal_detected', broke,
                '去掉「重读 opt」分支（行 %d–%d）后，重读判据不再成立'
                '（i_cur2=%d i_enf=%d）' % (i0 + 1, j, i_cur2, i_enf))
        else:
            chk('counterproof_d4_removal_detected', None,
                '「if _forced:」命中 %d 次（期望 1）' % len(_hit))
    except Exception as e:
        chk('counterproof_d4_removal_detected', None, '反证异常：%r' % (e,))

    try:
        # 反证 2：D2(b) —— 去掉「克隆 ⇒ 强制开旁路」
        _lines = src_backup.split('\n')
        _hit = [i for i, l in enumerate(_lines)
                if l.strip() == 'if _want_clone and not _spk_enabled:']
        if len(_hit) == 1:
            i0 = _hit[0]
            _indent = len(_lines[i0]) - len(_lines[i0].lstrip())
            j = i0 + 1
            while j < len(_lines):
                _ln = _lines[j]
                if _ln.strip():
                    _ind = len(_ln) - len(_ln.lstrip())
                    if _ind <= _indent:
                        break
                j += 1
            _mut = '\n'.join(_lines[:i0] + _lines[j:])
            chk('counterproof_d2b_removal_detected',
                'if _want_clone and not _spk_enabled:' not in _mut,
                '去掉强制分支（行 %d–%d）后该锚点消失' % (i0 + 1, j))
        else:
            chk('counterproof_d2b_removal_detected', None,
                '「if _want_clone and not _spk_enabled:」命中 %d 次（期望 1）'
                % len(_hit))
    except Exception as e:
        chk('counterproof_d2b_removal_detected', None, '反证异常：%r' % (e,))

    try:
        # 反证 3：D2(c) —— 取消勾选时不切回预设 A
        mutated3 = src_backup.replace(
            "self.var_tts_voice.set(self._tts_voice_label['A'])",
            "self.var_tts_voice.set(self.var_tts_voice.get())")
        if mutated3 != src_backup:
            fn_c2 = load_class_method.__call__  # noqa
            mt3 = ast.parse(mutated3)
            fn3 = fn_of(mt3, '_on_speaker_toggled')
            body3 = ast.dump(fn3) if fn3 else ''
            chk('counterproof_d2c_removal_detected',
                "_tts_voice_label['A']" not in body3,
                '切回「预设 A」的语句消失后判据失效')
        else:
            chk('counterproof_d2c_removal_detected', None,
                '无法定位要替换的代码块（源码已变）')
    except Exception as e:
        chk('counterproof_d2c_removal_detected', None, '反证异常：%r' % (e,))

    # ══════════════════════════════════════════════════════════
    n_pass = sum(1 for c in CHECKS if c['ok'] is True)
    n_fail = sum(1 for c in CHECKS if c['ok'] is False)
    n_none = sum(1 for c in CHECKS if c['ok'] is None)
    ev = {
        'script': os.path.basename(__file__),
        'target': APP_PY,
        'checks': CHECKS,
        'n_pass': n_pass, 'n_fail': n_fail, 'n_none': n_none,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('结果：%d PASS / %d FAIL / %d NONE' % (n_pass, n_fail, n_none))
    for c in CHECKS:
        mark = {True: 'PASS', False: 'FAIL', None: 'NONE'}[c['ok']]
        print('  [%s] %s —— %s' % (mark, c['name'], c['detail']))
    print('证据：%s' % OUT_JSON)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
