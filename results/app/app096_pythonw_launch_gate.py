#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-023 回归闸门 —— **「用户真实启动方式」下的冒烟**必须常驻。

🔴 为什么要这个闸门（APP-023 原话）：
    「把『用户真实启动方式（pythonw + 快捷方式）下的冒烟』加进回归闸门，
      避免再出现『测试全绿、用户那边全挂』。」
    —— §54/§61/§62 的 app071/074/075/077 **全是控制台 python**，
    它们永远测不到 `stderr=None` 在**无继承句柄**条件下的行为。

判据：
    G1 桌面快捷方式 → v1.5 包启动器（文件存在）
    G2 app095 里**有**「无继承 stderr 句柄」闸门（AST 级，不看注释）
    G3 app095b 用 `ShellExecuteW`（不是 Popen/控制台）
    G4 最近一次结果 JSON：`no_stderr_handle=True` 且 `all_pass=true`
    G5 **反证**：从控制台直接跑 app095（不带 --force）⇒ **必须 rc=2（拒绝）**
       ⇒ 否则说明闸门是摆设（这就是 §62 那类「闸门自身假通过」）
    G6 闸门判据**不能**只用 `sys.stdout is None`（AST 里必须有 GetStdHandle 调用）
    G7 三级 wav 各自独立落盘（L2/L3 不能互相覆盖）
"""
from __future__ import annotations

import ast
import ctypes
import glob
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# 🔴 §48 闸门：**不写死客户包版本号** ⇒ 用 `pkg_paths` 单一数据源
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
import pkg_paths  # noqa: E402

PKG = pkg_paths.discover_pkg_dir()
SMOKE = os.path.join(HERE, 'app095_pythonw_smoke.py')
LAUNCHER = os.path.join(HERE, 'app095b_launch_via_shellexecute.py')
OUT_JSON = os.path.join(HERE, 'app095_pythonw_smoke.json')
WAV_DIR = os.path.join(HERE, 'app095_wav')

_res = []


def check(name, cond, detail=''):
    _res.append((name, bool(cond)))
    print('  %s %s%s' % ('✅' if cond else '❌', name,
                         ('  —— ' + detail) if detail else ''))
    return bool(cond)


# ── 读快捷方式（复用 app094 的 COM 读法，不引入 PowerShell COM） ──
def read_lnk(path):
    sys.path.insert(0, HERE)
    from app094_fix_desktop_shortcut import read_lnk as _r
    return _r(path)


def main() -> int:
    print('=' * 74)
    print('APP-023 回归闸门：用户真实启动方式（pythonw + 快捷方式）')
    print('=' * 74)

    # G1
    print('\n── G1 桌面快捷方式 ──')
    lnk = os.path.join(os.path.expanduser('~'), 'Desktop',
                       'Confucius4 实时字幕.lnk')
    tgt = ''
    try:
        info = read_lnk(lnk)
        tgt = info.get('TargetPath') or ''
        print('   TargetPath = %s' % tgt)
    except Exception as e:
        print('   读取失败：%r' % (e,))
    check('G1 快捷方式指向 v1.5 包启动器',
          tgt.lower().endswith('start_livecaption.bat')
          and tgt.startswith(PKG) and os.path.isfile(tgt),
          '存在=%s' % os.path.isfile(tgt))

    # G2 / G6（AST 级）
    print('\n── G2/G6 冒烟脚本自带「无句柄」闸门 ──')
    src = io.open(SMOKE, encoding='utf-8').read()
    tree = ast.parse(src)
    has_gsh = any(isinstance(n, ast.Call)
                  and getattr(n.func, 'attr', '') == 'GetStdHandle'
                  for n in ast.walk(tree))
    has_gate = False
    for n in ast.walk(tree):
        if isinstance(n, ast.If):
            seg = ast.dump(n)
            if '_NO_STDERR_HANDLE' in seg and 'force' in seg:
                for x in ast.walk(n):
                    if isinstance(x, ast.Return):
                        has_gate = True
    check('G2 有「无继承句柄」闸门且拒绝时 return 2', has_gate)
    check('G6 判据用到 GetStdHandle（不是只看 sys.stdout is None）', has_gsh)

    # G3
    print('\n── G3 启动器用 ShellExecuteW ──')
    lsrc = io.open(LAUNCHER, encoding='utf-8').read()
    ltree = ast.parse(lsrc)
    uses_shell = any(isinstance(n, ast.Call)
                     and getattr(n.func, 'attr', '') == 'ShellExecuteW'
                     for n in ast.walk(ltree))
    uses_popen = 'Popen' in lsrc
    check('G3 用 ShellExecuteW（explorer 等价）', uses_shell,
          '仍出现 Popen 字样=%s' % uses_popen)

    # G4
    print('\n── G4 最近一次冒烟结果 ──')
    if os.path.isfile(OUT_JSON):
        d = json.load(io.open(OUT_JSON, encoding='utf-8'))
        print('   when=%s  launched_by=%s' % (d.get('when'),
                                              d.get('launched_by')))
        check('G4a 结果是无句柄环境下跑的（no_stderr_handle=True）',
              d.get('no_stderr_handle') is True)
        check('G4b all_pass=true', d.get('all_pass') is True)
        check('G4c 解释器是包内 pythonw',
              'pythonw.exe' in (d.get('launched_by') or '').lower())
        lv = {r.get('level'): r for r in d.get('results', [])}
        for k in ('L1', 'L2', 'L3'):
            r = lv.get(k)
            print('   %s: %s' % (k, '缺' if r is None else
                                 'ready=%s played=%s audible=%s'
                                 % (r.get('ready'), r.get('played'),
                                    r.get('audible'))))
    else:
        for n in ('G4a 结果是无句柄环境下跑的（no_stderr_handle=True）',
                  'G4b all_pass=true', 'G4c 解释器是包内 pythonw'):
            check(n, False, '结果 JSON 不存在')

    # G7
    print('\n── G7 三级 wav 各自落盘 ──')
    w2 = glob.glob(os.path.join(WAV_DIR, 'L2_CUDA', '*.wav'))
    w3 = glob.glob(os.path.join(WAV_DIR, 'L3_NPU', '*.wav'))
    check('G7a L2(CUDA) wav 落盘', len(w2) >= 1,
          '%d 个 %s' % (len(w2), os.path.basename(w2[0]) if w2 else ''))
    check('G7b L3(NPU) wav 落盘', len(w3) >= 1,
          '%d 个 %s' % (len(w3), os.path.basename(w3[0]) if w3 else ''))
    if w2 and w3:
        h2 = open(w2[0], 'rb').read()
        h3 = open(w3[0], 'rb').read()
        check('G7c 两级 wav **不是同一个文件**（没互相覆盖）', h2 != h3)

    # G5 反证：**控制台**跑 app095 必须被拒
    print('\n── G5 反证：控制台 python 跑 app095 必须被拒绝 ──')
    if os.path.isfile(OUT_JSON):
        bak = io.open(OUT_JSON, encoding='utf-8').read()
    else:
        bak = None
    before = sorted(os.listdir(HERE))
    r = subprocess.run([sys.executable, SMOKE, '--levels', 'L1'],
                       capture_output=True, text=True, timeout=180)
    print('   rc=%s' % r.returncode)
    check('G5a 控制台环境被闸门拒绝（rc=2）', r.returncode == 2,
          'rc=%s' % r.returncode)
    if bak is not None:
        now = io.open(OUT_JSON, encoding='utf-8').read()
        check('G5b 被拒绝时**没有**覆盖已有结果 JSON', now == bak)
    check('G5c 被拒绝时没有产出新文件',
          sorted(os.listdir(HERE)) == before)

    ok = sum(1 for _, c in _res if c)
    bad = len(_res) - ok
    print('\n' + '=' * 74)
    print('PASS %d / FAIL %d' % (ok, bad))
    print('=' * 74)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
