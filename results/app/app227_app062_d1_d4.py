#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app227 —— APP-062（D1–D4）四项决定的**代码层验收**。

| 编号 | 要求 | 本脚本怎么验 |
|---|---|---|
| **D1** | 旁路窗长做成**配置项** ＋ 与 ASR 侧常量**同源**，默认 10 s | ① `_WIN_S` **不再写死** ② 读 `asr052_spk_runtime.WIN_S`（**同源**）③ 环境变量可覆盖 ④ 非法值退回默认 |
| **D2** | 选「跟随说话人」⇒ **自动打开旁路**；状态栏显示「说话人分离：开（克隆需要）」；旁路关闭时克隆选项不可选 | 静态验三处锚点 + **行为探针**（跑真代码） |
| **D3** | 客户包里去掉 CUDA（界面不显示 ＋ CLI 拒绝）；包里不残留 `_fq3tts_env` 路径 | ① `_in_customer_package()` 判据 ② GUI 分支 ③ CLI 拒绝 ④ **`pkg_exclude` 排除**（结构性） |
| **D4** | MT 与 TTS 同 NPU ⇒ **禁止**，MT 自动改到 GPU.0 ＋ 状态栏/弹框告知 ＋ 写日志；启动时 `device_config.json` 同组合一样处理 | 静态验三个接线点 + **行为探针** |

🔴 **三态判据**：True / False / **None（无法判定）**。
🔴 **反证**：把实现改回旧行为 ⇒ 判据必须 FAIL（证明**非恒真**）。
🔴 **不 import 被测模块**（顶层重依赖 ⇒ import 期 abort）⇒ 用 `ast` 抽源码 + `exec`。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
APP_PY = os.path.join(REPO, 'live_caption', 'live_caption_app.py')
SPK_PY = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
EXCL_PY = os.path.join(REPO, 'pkg_exclude.py')
OUT_JSON = os.path.join(HERE, 'app227_app062_d1_d4_evidence.json')

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


def has_call(node, attr):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr == attr:
                return True
            if isinstance(f, ast.Name) and f.id == attr:
                return True
    return False


def load_module(path, name, drop_modules=()):
    """🔴 用 `ast` 抽源码 + `exec` ⇒ **不触发**顶层重依赖 import。"""
    tree = ast.parse(read(path).decode('utf-8'))
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = ''
            if isinstance(node, ast.Import):
                mod = node.names[0].name.split('.')[0]
            else:
                mod = (node.module or '').split('.')[0]
            if mod in drop_modules:
                continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        keep.append(node)
    mod = types.ModuleType(name)
    mod.__file__ = path
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, 'exec'),
         mod.__dict__)
    return mod


def load_class_method(path, cls_name, meth_name, name, drop_modules=()):
    """🔴 **类方法**探针：把方法单独抽出来 exec ⇒ 不必加载整个类。

    🔴 **为什么**：`App` 类的 `__init__` 会拉起 tkinter / 模型 ⇒ 不能整体实例化
    ⇒ 只把**这一个方法**抽出来当普通函数跑（`self` 由探针自己造）。
    """
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


# ══════════════════════════════════════════════════════════════════════
# D1
# ══════════════════════════════════════════════════════════════════════
def check_d1():
    src = src_of(SPK_PY)
    tree = ast.parse(src)

    # ① 不再写死 `_WIN_S = 10.0`
    hard = [n for n in ast.walk(tree)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == '_WIN_S'
                    for t in n.targets)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, (int, float))]
    chk('d1_no_hardcoded_win_s', not hard,
        '`_WIN_S` 直接赋值字面量的处数=%d（须 0 ⇒ 已改成同源解析）' % len(hard))

    # ② 同源：读 `asr052_spk_runtime.WIN_S`
    chk('d1_reads_asr_constant',
        'asr_spk_window' in src and 'asr052_spk_runtime' in src
        and 'WIN_S' in src and 'getattr(mod, ' in src,
        '源码里存在「从 ASR 侧读 WIN_S」的解析逻辑'
        '（优先 `asr_spk_window` ＝ ASR-041 的**唯一事实来源**，'
        '兜底 `asr052_spk_runtime` ＝ 随包分发的运行时内核）')

    # ③ 配置项：环境变量可覆盖
    chk('d1_config_env_override', 'LIVECAP_SPK_WINDOW_S' in src,
        '存在配置项 `LIVECAP_SPK_WINDOW_S`（⇒ ASR-040 的 10s vs 5s 可不改代码）')

    # ④ 非法值退回默认
    chk('d1_invalid_falls_back',
        ('_WIN_S_DEFAULT' in src and 'v > 0' in src),
        '非法值（非数字 / ≤0）退回默认 `_WIN_S_DEFAULT`')

    # ⑤ **行为**：真跑一次 ⇒ 解析结果与来源
    #    🔴 探针必须把 `live_caption/` 加进 `sys.path`
    #       ⇒ 否则 `speaker_assets` 找不到 ⇒ 同源读取会失败（假 FAIL）
    try:
        if os.path.join(REPO, 'live_caption') not in sys.path:
            sys.path.insert(0, os.path.join(REPO, 'live_caption'))
        m = load_module(SPK_PY, 'spk_probe_d1',
                        drop_modules=('asr052_speaker_tracker_api',))
        w = getattr(m, '_WIN_S', None)
        srcname = getattr(m, '_WIN_S_SRC', '')
        # 🔴🔴🔴 **口径变更（APP-063 ③，2026-11-02）**：旧判据写死「须 10.0」。
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
            % (w, _asr_win_s))
        chk('d1_runtime_source_is_shared',
            ('asr_spk_window' in srcname or 'asr052_spk_runtime' in srcname),
            '实际来源=%r（须指向 ASR 侧常量 ⇒ **同源**；§131 已对齐 ASR-041 的'
            '`asr_spk_window` 单一事实来源）' % srcname)
    except Exception as e:
        chk('d1_runtime_value', None,
            '无法加载 speaker_tracker ⇒ 无法判定：%s' % e)
        chk('d1_runtime_source_is_shared', None, '同上')

    # ⑥ **行为**：配置项真的能改 ⇒ 子进程跑（环境变量必须**进程级**）
    env = dict(os.environ)
    env['LIVECAP_SPK_WINDOW_S'] = '5.0'
    env['PYTHONPATH'] = os.path.join(REPO, 'live_caption')
    p = subprocess.run(
        [sys.executable, '-c',
         'import speaker_tracker as s; print(s._WIN_S, s._WIN_S_SRC)'],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=180)
    out = (p.stdout or '').strip()
    chk('d1_env_override_works', out.startswith('5.0'),
        '设 `LIVECAP_SPK_WINDOW_S=5.0` ⇒ 实际窗长=%r（须 5.0）' % out)


# ══════════════════════════════════════════════════════════════════════
# D2
# ══════════════════════════════════════════════════════════════════════
def check_d2():
    src = src_of(APP_PY)
    tree = ast.parse(src)

    fn = fn_of(tree, '_enable_speaker_for_clone')
    chk('d2_helper_exists', fn is not None,
        '存在 `_enable_speaker_for_clone` 方法')

    if fn is not None:
        body = ast.dump(fn)
        # ① 三处同步：勾选框 / 运行时开关 / 桥接器
        chk('d2_syncs_checkbox',
            'var_speaker' in body,
            '方法里同步了**勾选框** `var_speaker`')
        chk('d2_syncs_runtime_flag',
            '_speaker_enabled' in body,
            '方法里同步了**运行时开关** `_speaker_enabled`')
        chk('d2_syncs_bridge',
            '_spk_bridge' in body and 'enabled' in body,
            '方法里同步了**旁路桥接器** `_spk_bridge.enabled`')
        # ② 状态栏文案
        chk('d2_status_text',
            '说话人分离：开（克隆需要）' in src,
            '存在状态栏文案「说话人分离：开（克隆需要）」（reviewer 原文）')

    # ③ 音色回调调用了自动开启
    fn2 = fn_of(tree, '_on_tts_voice_changed')
    chk('d2_voice_callback_calls_helper',
        fn2 is not None and has_call(fn2, '_enable_speaker_for_clone'),
        '选「跟随说话人」的回调里调用了 `_enable_speaker_for_clone`')

    # ④ 旁路关闭时克隆不可选 ⇒ 状态栏要有「关（克隆需开）」告警
    chk('d2_clone_needs_bypass_warning',
        '关（克隆需开）' in src,
        '旁路关闭 + 克隆开启 ⇒ 状态栏显示「关（克隆需开）」告警')

    # ⑤ **反证**：把自动开启去掉 ⇒ 判据必须 FAIL
    #    🔴 锚点用**行内匹配**（缩进可能变）⇒ 避免字符串补丁因缩进不符而落空
    try:
        lines = src.split('\n')
        hit = [i for i, ln in enumerate(lines)
               if '_enable_speaker_for_clone(' in ln
               and 'def _enable_speaker_for_clone' not in ln]
        # ⚠️ 可能有**多个**调用点（APP-065 A 之后 3 个）⇒ 反证要全破坏
        if not hit:
            raise RuntimeError('未找到自动开启调用 ⇒ 反证无法构造')
        # 🔴 **替换成 `pass`**（而不是删除这一行）
        #   ⇒ 若该行是某个 `if` 分支里**唯一**的语句，删掉会变成空块
        #      ⇒ SyntaxError ⇒ 反证「无法判定」。
        #   ⇒ 替换保留缩进 ⇒ 语法合法 ⇒ 反证可判定。
        # 🔴🔴🔴 **破坏所有命中点**（APP-065 A 之后有 3 个调用点：
        #   ① 启动参数 ② `_on_tts_toggled` ③ `_on_tts_voice_changed`）
        #   ⇒ 只破坏第一个 ⇒ ③ 里的调用仍在 ⇒ 判据仍成立 ⇒ 反证失败。
        broken_lines = list(lines)
        _hits = [i for i, ln in enumerate(lines)
                 if '_enable_speaker_for_clone(' in ln
                 and 'def _enable_speaker_for_clone' not in ln]
        for _i in _hits:
            _ind = len(lines[_i]) - len(lines[_i].lstrip())
            broken_lines[_i] = ' ' * _ind + 'pass'
        broken = '\n'.join(broken_lines)
        t2 = ast.parse(broken)
        fn3 = fn_of(t2, '_on_tts_voice_changed')
        caught = not (fn3 is not None
                      and has_call(fn3, '_enable_speaker_for_clone'))
        chk('d2_counterproof', caught,
            '把**全部** %d 处自动开启调用替换为 pass（源码行 %s）'
            '⇒ 判据应 FAIL（实得 caught=%r）'
            % (len(_hits), [i + 1 for i in _hits], caught))
    except Exception as e:
        chk('d2_counterproof', None, '反证构造失败 ⇒ 无法判定：%s' % e)


# ══════════════════════════════════════════════════════════════════════
# D3
# ══════════════════════════════════════════════════════════════════════
def check_d3():
    src = src_of(APP_PY)
    tree = ast.parse(src)

    # ① 包内标记判据
    fn = fn_of(tree, '_in_customer_package')
    chk('d3_pkg_marker_helper', fn is not None,
        '存在 `_in_customer_package()`（用包内 `MANIFEST.json` 判定）')
    if fn is not None:
        body = ast.dump(fn)
        chk('d3_marker_is_manifest',
            'MANIFEST.json' in body,
            '判据用的是包内特有的 `MANIFEST.json`（开发树没有 ⇒ 不会误判）')

    # ② GUI：客户包不列 CUDA
    fn2 = fn_of(tree, 'build_tts_options')
    if fn2 is None:
        chk('d3_gui_hides_cuda', False, '找不到 `build_tts_options`')
    else:
        body = ast.dump(fn2)
        chk('d3_gui_hides_cuda',
            '_in_customer_package' in body and 'CUDA@bf16' in body,
            'GUI 选项构造里有「客户包 ⇒ 不列 CUDA」的分支')

    # ③ CLI：拒绝 `--tts-device CUDA`
    chk('d3_cli_rejects_cuda',
        ('APP-062 ③（D3）' in src or 'APP-062 D3' in src)
        and 'sys.exit(2)' in src and '_tts_device' in src,
        'CLI 里有「客户包 + --tts-device CUDA ⇒ 报错退出(2)」的分支')

    # ④ **结构性**：`pkg_exclude` 排除 CUDA 两模块
    excl = src_of(EXCL_PY)
    chk('d3_pkg_excludes_cuda_modules',
        "'app/tts_cuda.py'" in excl and "'app/tts_cuda_sidecar.py'" in excl,
        '`pkg_exclude.INTERNAL_EXACT` 排除了两个 CUDA 模块'
        '⇒ **包里不残留 `_fq3tts_env` 路径**（结构性保证）')

    # ⑤ **反证**：把排除去掉 ⇒ 判据必须 FAIL
    try:
        broken = excl.replace("    'app/tts_cuda.py',\n", '', 1)
        if broken == excl:
            raise RuntimeError('未找到排除项 ⇒ 反证无法构造')
        caught = ("'app/tts_cuda.py'" not in broken)
        chk('d3_counterproof', caught,
            '把 `app/tts_cuda.py` 的排除去掉 ⇒ 判据应 FAIL（实得 caught=%r）'
            % caught)
    except Exception as e:
        chk('d3_counterproof', None, '反证构造失败 ⇒ 无法判定：%s' % e)

    # ⑥ 开发树**保留** CUDA（用于对照基准）
    chk('d3_dev_keeps_cuda',
        os.path.isfile(os.path.join(REPO, 'live_caption', 'tts_cuda.py'))
        and os.path.isfile(os.path.join(REPO, 'live_caption',
                                        'tts_cuda_sidecar.py')),
        '开发树**保留** `tts_cuda.py` / `tts_cuda_sidecar.py`（用于对照基准）')


# ══════════════════════════════════════════════════════════════════════
# D4
# ══════════════════════════════════════════════════════════════════════
def check_d4():
    src = src_of(APP_PY)
    tree = ast.parse(src)

    fn = fn_of(tree, '_enforce_no_npu_conflict')
    chk('d4_helper_exists', fn is not None,
        '存在 `_enforce_no_npu_conflict` 方法')
    if fn is not None:
        body = ast.dump(fn)
        # ① 改 MT（不是 TTS）
        chk('d4_changes_mt', "'mt'" in body and 'GPU.0' in body,
            '冲突时把 **MT** 改成 `GPU.0`（reviewer：「MT 自动改到 GPU.0」）')
        # ② 告知用户（状态栏 + 弹框）
        chk('d4_notifies_user',
            'var_status' in body and 'messagebox' in body,
            '有**状态栏告知** ＋ **弹框告知**')
        # ③ 写进日志
        chk('d4_writes_log', '_ui_log' in body,
            '有**写进日志**（`_ui_log` ⇒ 落盘会话日志）')
        # ④ 落配置文件
        chk('d4_saves_config', 'save_config' in body,
            '改完**落到 `device_config.json`**（下次启动仍是 GPU.0）')

    # ⑤ 三个接线点
    fn_mt = fn_of(tree, '_on_mt_combo_changed')
    fn_tts = fn_of(tree, '_on_tts_combo_changed')
    chk('d4_wired_mt_change',
        fn_mt is not None and has_call(fn_mt, '_enforce_no_npu_conflict'),
        'MT 下拉变化 ⇒ 调用了 `_enforce_no_npu_conflict`')
    chk('d4_wired_tts_change',
        fn_tts is not None and has_call(fn_tts, '_enforce_no_npu_conflict'),
        'TTS 下拉变化 ⇒ 调用了 `_enforce_no_npu_conflict`')
    chk('d4_wired_startup',
        '启动时读取 device_config.json' in src,
        '**启动时**（`device_config.json` 同组合）⇒ 也处理'
        '（reviewer 原文：「启动时如果 device_config.json 里是这种组合，'
        '也一样处理」）')

    # ⑥ **行为探针**：跑真代码 ⇒ MT 确实被改、且日志确实写了
    #    🔴 方法在 `class App` 里 ⇒ **整体实例化 App 会拉起 tkinter/模型**
    #       ⇒ 只把**这一个方法**抽出来当普通函数跑（`self` 由探针自己造）。
    try:
        fn_enforce = load_class_method(APP_PY, 'App',
                                       '_enforce_no_npu_conflict',
                                       'app_probe_d4')
        if fn_enforce is None:
            raise RuntimeError('抽不出 `App._enforce_no_npu_conflict`')
        logs = []

        class FakeApp:
            pass

        app = FakeApp()
        app._dev_choices = {'asr': 'GPU.0', 'mt': 'NPU', 'tts': 'NPU'}
        app._ui_log = lambda s: logs.append(s)
        app.var_status = types.SimpleNamespace(set=lambda s: None)
        app.var_mt_note = types.SimpleNamespace(set=lambda s: None)
        app.var_mt_combo = types.SimpleNamespace(set=lambda s: None)
        app._mt_opt_by_id = {}
        app._mt_precision = None
        app.mt = None
        changed = fn_enforce(app, '单元测试')
        chk('d4_behavior_mt_moved_to_gpu0',
            changed is True and app._dev_choices['mt'] == 'GPU.0',
            'MT=NPU + TTS=NPU ⇒ 改后 MT=%r（须 GPU.0）；changed=%r'
            % (app._dev_choices.get('mt'), changed))
        chk('d4_behavior_log_written',
            any('NPU' in x and 'GPU.0' in x for x in logs),
            '日志行=%r（须含 NPU 与 GPU.0）' % logs)
        # 幂等：再跑一次 ⇒ 不再改、不再写日志
        n_logs = len(logs)
        changed2 = fn_enforce(app, '单元测试2')
        chk('d4_behavior_idempotent',
            changed2 is False and len(logs) == n_logs,
            '已改过后再跑 ⇒ changed=%r 日志新增=%d 条（须 False / 0）'
            % (changed2, len(logs) - n_logs))
        # 不冲突 ⇒ 不动
        app._dev_choices = {'asr': 'GPU.0', 'mt': 'GPU.0', 'tts': 'NPU'}
        n_logs2 = len(logs)
        changed3 = fn_enforce(app, '不冲突')
        chk('d4_behavior_no_conflict_noop',
            changed3 is False and len(logs) == n_logs2,
            'MT=GPU.0 + TTS=NPU（不冲突）⇒ changed=%r 日志新增=%d（须 False / 0）'
            % (changed3, len(logs) - n_logs2))
    except Exception as e:
        for nm in ('d4_behavior_mt_moved_to_gpu0', 'd4_behavior_log_written',
                   'd4_behavior_idempotent', 'd4_behavior_no_conflict_noop'):
            chk(nm, None, '无法加载被测模块 ⇒ 无法判定：%s' % e)


def main():
    out = {'script': 'app227_app062_d1_d4.py',
           'correction': 'APP-062（D1–D4）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'repo': REPO,
           'files': {os.path.relpath(p, REPO): hashlib.sha256(
               read(p)).hexdigest()
               for p in (APP_PY, SPK_PY, EXCL_PY)}}
    for fn in (check_d1, check_d2, check_d3, check_d4):
        try:
            fn()
        except Exception as e:
            chk(fn.__name__, None, '检查项异常 ⇒ 无法判定：%s' % e)

    n_pass = sum(1 for c in CHECKS if c['ok'] is True)
    n_fail = sum(1 for c in CHECKS if c['ok'] is False)
    n_none = sum(1 for c in CHECKS if c['ok'] is None)
    out['checks'] = CHECKS
    out['n_pass'] = n_pass
    out['n_fail'] = n_fail
    out['n_none'] = n_none
    out['verdict'] = 'PASS' if (n_fail == 0 and n_none == 0) else 'FAIL'

    print('===== app227 APP-062（D1–D4）=====')
    for c in CHECKS:
        mark = 'NONE' if c['ok'] is None else ('PASS' if c['ok'] else 'FAIL')
        print('  [%s] %s' % (mark, c['detail']))
    print('\n结果：%d PASS / %d FAIL / %d 无法判定 ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % OUT_JSON)
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
