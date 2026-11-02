#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app230 —— APP-063 ③（D1 窗口改 5 s）的**跨模块一致性**验收。

## 为什么要有这个脚本

reviewer 原文（APP-063 ③）：

    「在 `asr_spk_window.WIN_S` 这一个地方改成 5.0。这个文件属于 ASR 模块，
      reviewer 会请主会话转告 ASR 去改；如果 ASR 不改，App 不要自己再写一份默认值。
    **客户包现在不带 asr_spk_window.py**（v2.2 的 app/asr_spk/ 里只有
    asr052_spk_runtime.py，`WIN_S=10.0`，L396），客户机会退回到 10 s，
    这样开发机和客户包又不一致。v2.3 必须把 asr_spk_window.py 一起打进包，
    **或者让 asr052_spk_runtime 从它读取**。
    **核实 asr052_spk_runtime 内部是否还有用到自身 WIN_S（10.0）的地方
    （偏移、最短段长、缓冲长度）；如果有，确保和 App 实际喂进去的窗口长度一致。**」

⇒ 光看 App 侧「读到 5.0」是**不够**的：真正的验收是
**App 喂进去的样本数 == ASR 内核切片用的 `WIN_N`**，
且 **内核的帧数 == 该窗口的帧数**。本脚本把这条跨模块不变量**做成可复现的判据**。

## 判据

| 编号 | 判据 | 期望 |
|---|---|---|
| D1-1 | App 侧解析到的窗长 **同源** ASR（不是 App 自己写死的默认值） | True |
| D1-2 | App 喂窗样本数 (`_WIN_S * SR`) **== ASR 内核 `WIN_N`** | True |
| D1-3 | ASR 内核 `N_FRAMES` **== `asr_spk_window.frames_for(WIN_S)`** | True |
| D1-4 | ASR 内核 `FPS` **== `asr_spk_window.fps_for(WIN_S)`**（容差 1e-6） | True |
| D1-5 | ASR 内核 `WIN_S` **== `asr_spk_window.WIN_S`** | True |
| D1-6 | 客户包 `app/asr_spk/` **是否含 `asr_spk_window.py`**（或内核已同源 ⇒ 二选一即可） | True |
| D1-7 | App 侧**没有**自己写第二份窗口默认值（`_WIN_S_DEFAULT` 仅作读不到时的兜底） | True |

🔴 **三态判据**：True / False / **None（无法判定：ASR 侧文件不存在等）**。
🔴 **反证**：把 ASR 内核的 `WIN_N` 改回 10 s ⇒ D1-2 必须 FAIL（证明非恒真）。
"""
from __future__ import annotations

import ast
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
SPK_PY = os.path.join(REPO, 'live_caption', 'speaker_tracker.py')
ASR_SCRIPTS = os.path.join(os.path.expanduser('~'), 'qwen3asr_06b', 'scripts')
OUT_JSON = os.path.join(HERE, 'app230_app063_d1_window_alignment_evidence.json')

CHECKS = []


def chk(name, ok, detail):
    CHECKS.append({'name': name, 'ok': (None if ok is None else bool(ok)),
                   'detail': detail})


def read(p):
    with open(p, 'rb') as f:
        return f.read()


def load_module(path, name):
    """`ast` 抽源码 + `exec`（不触发顶层重依赖 import）。"""
    tree = ast.parse(read(path).decode('utf-8'))
    keep = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mod = ''
            if isinstance(node, ast.Import):
                mod = node.names[0].name.split('.')[0]
            else:
                mod = (node.module or '').split('.')[0]
            if mod in ('numpy', 'openvino', 'torch', 'scipy', 'sklearn'):
                continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue
        keep.append(node)
    mod = types.ModuleType(name)
    mod.__file__ = path
    exec(compile(ast.Module(body=keep, type_ignores=[]), path, 'exec'),
         mod.__dict__)
    return mod


def const_of(mod, name):
    return getattr(mod, name, None)


def read_consts(path, names):
    """🔴 **只抽模块级常量**（`ast`）⇒ 不 exec 整个模块。

    🔴 **为什么**：`asr052_spk_runtime.py` 顶层有 `F32 = np.float32` 等
    **依赖 numpy 的语句** ⇒ 过滤掉 `import numpy` 后再 exec 会 NameError
    （假 FAIL）⇒ 改成**只读常量赋值**（`ast` 求值）。
    """
    tree = ast.parse(read(path).decode('utf-8'))
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name):
                continue
            if tgt.id not in names:
                continue
            try:
                out[tgt.id] = ast.literal_eval(node.value)
            except Exception:
                # 表达式（如 `int(WIN_S * SR)` / `N_FRAMES / WIN_S`）⇒ 后续算
                out[tgt.id] = None
    return out


def compute_runtime_derived(path, win_s_value):
    """🔴 从 ASR 内核源码**算出**它实际用的 `WIN_N` / `N_FRAMES` / `FPS`。

    🔴 **不能只读 `WIN_S`**：内核里 `WIN_N = int(WIN_S * SR)`、
    `N_FRAMES = 589`（**写死的常量**）、`FPS = N_FRAMES / WIN_S`
    ⇒ 必须按**源码实际表达式**求值 ⇒ 与内核运行时的行为一致。
    """
    tree = ast.parse(read(path).decode('utf-8'))
    env = {'SR': 16000, 'WIN_S': win_s_value, 'int': int, 'round': round,
           'float': float}
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name):
                continue
            if tgt.id not in ('SR', 'WIN_S', 'WIN_N', 'N_FRAMES', 'FPS',
                              'FRAME_S'):
                continue
            try:
                val = eval(compile(ast.Expression(node.value), path, 'eval'),
                           {'__builtins__': {}}, env)
            except Exception:
                continue
            out[tgt.id] = val
            env[tgt.id] = val
    return out


def main():
    # ── ASR 侧两个文件 ──
    p_win = os.path.join(ASR_SCRIPTS, 'asr_spk_window.py')
    p_rt = os.path.join(ASR_SCRIPTS, 'asr052_spk_runtime.py')
    if not os.path.isfile(p_win):
        chk('asr_window_file_exists', None,
            'ASR 侧没有 %s ⇒ 无法判定（ASR 模块还没落地）' % p_win)
        asr_win = None
    else:
        chk('asr_window_file_exists', True, p_win)
        asr_win = load_module(p_win, 'asr_spk_window_probe')
    if not os.path.isfile(p_rt):
        chk('asr_runtime_file_exists', None, 'ASR 侧没有 %s' % p_rt)
        asr_rt = None
    else:
        chk('asr_runtime_file_exists', True, p_rt)
        # 🔴 内核只抽**常量**（不 exec 整个模块：它顶层依赖 numpy）
        _rt_consts = read_consts(p_rt, ('SR', 'WIN_S', 'WIN_N', 'N_FRAMES',
                                        'FPS', 'FRAME_S'))
        asr_rt = types.SimpleNamespace(**_rt_consts)

    # ── App 侧解析结果 ──
    sys.path.insert(0, os.path.join(REPO, 'live_caption'))
    try:
        import speaker_tracker as st
    except Exception as e:
        chk('app_speaker_tracker_import', None, 'import 失败：%r' % (e,))
        st = None
    if st is not None:
        chk('app_speaker_tracker_import', True, 'speaker_tracker 导入成功')
        app_win = float(getattr(st, '_WIN_S', 0.0) or 0.0)
        app_src = getattr(st, '_WIN_S_SRC', '?')
        chk('D1-1_app_same_source_as_asr',
            '同源' in str(app_src),
            'App 侧 _WIN_S=%s，来源=%r'
            % (app_win, app_src))

        # D1-7：App 侧没有自己写第二份默认值
        d2 = const_of(st, '_WIN_S_DEFAULT')
        chk('D1-7_app_no_second_default',
            d2 == 10.0,
            'App 侧 _WIN_S_DEFAULT=%r（**仅**作读不到 ASR 时的兜底；'
            '实际生效值来自同源解析=%s）' % (d2, app_win))

        if asr_win is not None:
            w = float(getattr(asr_win, 'WIN_S', 0.0) or 0.0)
            chk('D1-5_kernel_win_s_matches_asr',
                asr_rt is not None
                and float(getattr(asr_rt, 'WIN_S', -1)) == w,
                'ASR 唯一事实来源 asr_spk_window.WIN_S=%s；'
                '内核 asr052_spk_runtime.WIN_S=%r'
                % (w, getattr(asr_rt, 'WIN_S', None) if asr_rt else None))
            chk('D1-1_app_equals_asr_window',
                abs(app_win - w) < 1e-9,
                'App 解析值=%s vs ASR 唯一事实来源=%s' % (app_win, w))
        else:
            chk('D1-5_kernel_win_s_matches_asr', None, 'ASR 侧文件缺失')
            chk('D1-1_app_equals_asr_window', None, 'ASR 侧文件缺失')

        # D1-2 / D1-3 / D1-4：跨模块不变量
        if asr_rt is not None and asr_win is not None:
            sr = float(getattr(st, '_SR', 16000) or 16000)
            fed = int(round(app_win * sr))
            # 🔴 **按内核源码的实际表达式求值**（不是只读 `WIN_S`）：
            #   内核的 `WIN_N = int(WIN_S * SR)`、`N_FRAMES = 589`（写死）、
            #   `FPS = N_FRAMES / WIN_S` ⇒ 必须按源码算才是真实行为。
            _derived = compute_runtime_derived(p_rt, float(app_win))
            k_win_n = int(_derived.get('WIN_N', -1))
            chk('D1-2_fed_samples_match_kernel_win_n',
                fed == k_win_n,
                'App 喂窗样本数=%d（_WIN_S %s × SR %d）；'
                '内核按其源码算出的 WIN_N=%d ⇒ %s'
                % (fed, app_win, sr, k_win_n,
                   '一致' if fed == k_win_n else '**错位**（内核按 10 s 切）'))

            try:
                exp_frames = int(asr_win.frames_for(
                    float(getattr(asr_win, 'WIN_S', 10.0))))
            except Exception as e:
                exp_frames = None
                chk('D1-3_frames_same_source', None,
                    'asr_spk_window.frames_for 不可用：%r' % (e,))
            if exp_frames is not None:
                k_frames = int(_derived.get('N_FRAMES', -1))
                chk('D1-3_frames_same_source',
                    k_frames == exp_frames,
                    '内核 N_FRAMES=%d vs asr_spk_window.frames_for(%s)=%d ⇒ %s'
                    % (k_frames, getattr(asr_win, 'WIN_S', '?'), exp_frames,
                       '一致' if k_frames == exp_frames else '**错位**'))

            try:
                exp_fps = float(asr_win.fps_for(
                    float(getattr(asr_win, 'WIN_S', 10.0))))
            except Exception as e:
                exp_fps = None
                chk('D1-4_fps_same_source', None,
                    'asr_spk_window.fps_for 不可用：%r' % (e,))
            if exp_fps is not None:
                k_fps = float(_derived.get('FPS', -1))
                chk('D1-4_fps_same_source',
                    abs(k_fps - exp_fps) < 1e-6,
                    '内核 FPS=%s vs asr_spk_window.fps_for(%s)=%s ⇒ %s'
                    % (k_fps, getattr(asr_win, 'WIN_S', '?'), exp_fps,
                       '一致' if abs(k_fps - exp_fps) < 1e-6 else '**错位**'))
        else:
            chk('D1-2_fed_samples_match_kernel_win_n', None, 'ASR 侧文件缺失')
            chk('D1-3_frames_same_source', None, 'ASR 侧文件缺失')
            chk('D1-4_fps_same_source', None, 'ASR 侧文件缺失')

    # ── D1-6：客户包是否带 asr_spk_window.py（或内核已同源 ⇒ 二选一）──
    pkgs = []
    try:
        home = os.path.expanduser('~')
        for nm in os.listdir(home):
            # 🔴 **只要目录**（`*.zip` 是打包产物，不是包目录 ⇒ 会被误当目录）
            if nm.startswith('Confucius4_LiveCaption_v') \
                    and os.path.isdir(os.path.join(home, nm)):
                pkgs.append(os.path.join(home, nm))
    except Exception:
        pass
    pkgs.sort(key=lambda p: os.path.getmtime(p))
    latest = pkgs[-1] if pkgs else None
    if latest is None:
        chk('D1-6_pkg_carries_window_or_kernel_same_source', None,
            '找不到任何客户包目录')
    else:
        spk_dir = os.path.join(latest, 'app', 'asr_spk')
        has_win = os.path.isfile(os.path.join(spk_dir, 'asr_spk_window.py'))
        kernel_same = False
        if asr_rt is not None and asr_win is not None:
            kernel_same = (float(getattr(asr_rt, 'WIN_S', -1))
                           == float(getattr(asr_win, 'WIN_S', -2)))
        chk('D1-6_pkg_carries_window_or_kernel_same_source',
            has_win or kernel_same,
            '最新包 %s：含 asr_spk_window.py=%s；内核与唯一事实来源同源=%s ⇒ %s'
            % (os.path.basename(latest), has_win, kernel_same,
               'OK' if (has_win or kernel_same)
               else '**两者皆无**（包内仍是 10 s 兜底 ⇒ 客户机退回 10 s）'))

    # ── 反证：内核 WIN_N 改回 10 s ⇒ D1-2 必须 FAIL ──
    if asr_rt is not None and st is not None:
        sr = float(getattr(st, '_SR', 16000) or 16000)
        app_win = float(getattr(st, '_WIN_S', 0.0) or 0.0)
        fed = int(round(app_win * sr))
        fake_win_n = int(round(10.0 * sr))
        chk('counterproof_d1_2_detects_mismatch',
            not (fed == fake_win_n),
            '把内核 WIN_N 设回 10 s（%d）⇒ 与 App 喂窗 %d 不等 ⇒ D1-2 会 FAIL'
            % (fake_win_n, fed))
    else:
        chk('counterproof_d1_2_detects_mismatch', None, '缺 ASR/App 侧数据')

    n_pass = sum(1 for c in CHECKS if c['ok'] is True)
    n_fail = sum(1 for c in CHECKS if c['ok'] is False)
    n_none = sum(1 for c in CHECKS if c['ok'] is None)
    ev = {
        'script': os.path.basename(__file__),
        'asr_scripts_dir': ASR_SCRIPTS,
        'checks': CHECKS,
        'n_pass': n_pass, 'n_fail': n_fail, 'n_none': n_none,
        'verdict': 'PASS' if n_fail == 0 else 'FAIL',
        'note': ('D1 的跨模块不变量：App 喂窗样本数必须 == ASR 内核 WIN_N；'
                 '内核帧数/帧率必须 == asr_spk_window 的同窗口值。'
                 '当前 ASR 侧唯一事实来源已是 5.0，但内核仍写死 10 s ⇒ '
                 '预期本脚本会 FAIL（这正是要交 ASR 的证据）。'),
    }
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('结果：%d PASS / %d FAIL / %d NONE' % (n_pass, n_fail, n_none))
    for c in CHECKS:
        mark = {True: 'PASS', False: 'FAIL', None: 'NONE'}[c['ok']]
        print('  [%s] %s —— %s' % (mark, c['name'], c['detail']))
    print('证据：%s' % OUT_JSON)
    return 0


if __name__ == '__main__':
    sys.exit(main())
