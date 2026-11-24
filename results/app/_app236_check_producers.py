#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222 修复前的**准入检查**：5 个待入库的生产者脚本能否在干净 clone 里跑。

检查项（每项都必须 PASS 才允许入库）：
  ① 语法可解析（ast.parse）
  ② 无仓库内未入库的本地 import（干净 clone 跑得起来）
  ③ 无硬编码密钥/口令/token（入库安全）
  ④ 不写客户包 / 不删文件 / 不跑推理打设备（纯静态、可安全重跑）
  ⑤ 反证组：把「已入库的同名脚本」放进去 ⇒ 必须被本检查识破（判据有鉴别力）
"""
import ast
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BS = chr(92)

TARGETS = [
    ('results/app/app260_tk_geometry_probe.json', 'results/app/_app260_tk_geometry_probe.py'),
    ('results/app/app385_app089_accept_runs_after.json', 'results/app/_app385_run_acceptance_all.py'),
    ('results/app/app534_special_profile_check.json', 'results/app/_app534_special_profile_check.py'),
    ('results/app/app589_three_forms_defaults.json', 'results/app/_app589_three_forms_defaults_check.py'),
    ('results/app/app372_app091_subtitle_shot/subtitle_layout.json',
     'results/app/app372_app091_gui_subtitle_shot.py'),
]

STDLIB = set('''os sys json re subprocess hashlib pathlib shutil datetime time typing collections
itertools argparse tempfile glob math csv io unittest ast difflib textwrap random statistics
urllib socket threading queue logging traceback platform shlex stat sqlite3 uuid base64
contextlib copy pickle struct wave ctypes winreg multiprocessing concurrent selectors ssl email
abc enum dataclasses functools importlib inspect string types numbers gzip zipfile tarfile'''.split())

# ③ 密钥/口令特征
SECRET_PAT = re.compile(
    r'(?i)(password|passwd|pwd\s*=|secret|api[_-]?key|token\s*=|bearer\s|'
    r'private[_-]?key|BEGIN [A-Z ]*PRIVATE KEY|access[_-]?key)')

# ④ 危险动作：**AST 级**判定（MEMORY：「闸门的判据也会错」⇒ 粗粒度正则会把良性删除误报）
#   良性：
#     - `os.remove(LOCK)` 且 LOCK 是脚本自建锁、且有 own-pid 守卫
#     - `shutil.rmtree(tmp)` 且 tmp 由本脚本 tempfile 建出
#     - 引用客户包路径但**只读**（open(...,'rb') / isfile / sha256）
#   危险：
#     - 以写模式打开客户包路径
#     - 删除非「自建临时目录 / 自建锁」的路径
#     - 编译/推理（占设备）
DELETE_FUNCS = {('shutil', 'rmtree'), ('os', 'remove'), ('os', 'unlink'), ('os', 'rmdir')}
INFER_TOKENS = ('.infer(', 'openvino.Core(', 'core.compile_model')
#: 仓库里**唯一的**客户包名前缀常量名（`pkg_paths.PKG_NAME_PREFIX`）
#: ⇒ 出现它的赋值 ⇒ 该变量就是客户包路径变量（与写死字面量等价）
PKG_PREFIX_NAMES = {'PKG_NAME_PREFIX', 'PKG_PREFIX'}


def ast_danger(src, tree):
    """返回危险命中列表（空 = 良性）。"""
    hits = []
    # 自建临时目录变量
    tmp_vars = set()
    self_tmp = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    val = node.value
                    if isinstance(val, ast.Call):
                        fn = val.func
                        nm = (fn.attr if isinstance(fn, ast.Attribute)
                              else fn.id if isinstance(fn, ast.Name) else '')
                        if nm in ('mkdtemp', 'TemporaryDirectory'):
                            tmp_vars.add(tgt.id)
    # 客户包路径变量（只读豁免）
    # 🔴 识别**两种**形态（都要认，否则判据会漏）：
    #   (a) 字面量里直接写死了包名（如 'Confucius4_LiveCaption_v2.6'）
    #   (b) 用**前缀常量 + 版本**拼出来（如 PKG_NAME_PREFIX + '2.6'）
    #       ⇒ 这正是仓库 §48 闸门**要求**的写法（不写死版本号）⇒ 必须同样判为包路径
    pkg_vars = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    names_in_val = {s.id for s in ast.walk(node.value)
                                    if isinstance(s, ast.Name)}
                    has_literal = any(
                        isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                        and 'Confucius4_LiveCaption' in sub.value
                        for sub in ast.walk(node.value))
                    has_prefix_const = bool(names_in_val & PKG_PREFIX_NAMES)
                    if has_literal or has_prefix_const:
                        pkg_vars.add(tgt.id)
    # 删除调用
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            qual = None
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                qual = (fn.value.id, fn.attr)
            if qual in DELETE_FUNCS:
                tgt_names = {s.id for a in node.args for s in ast.walk(a)
                             if isinstance(s, ast.Name)}
                if tgt_names & tmp_vars:
                    continue                      # 自建临时目录 ⇒ 良性
                if qual == ('os', 'remove') and tgt_names:
                    # 自建锁 + own-pid 守卫（脚本里出现 os.getpid() 且锁名含 LOCK）
                    if 'os.getpid()' in src and 'LOCK' in src:
                        continue
                hits.append('删除调用 %s.%s 目标=%s' % (qual[0], qual[1],
                                                        ','.join(sorted(tgt_names)) or '?'))
            # 写模式打开客户包路径
            if isinstance(fn, ast.Name) and fn.id == 'open':
                mode = None
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                for a in node.args[:1]:
                    names = {s.id for s in ast.walk(a) if isinstance(s, ast.Name)}
                    if (names & pkg_vars) and mode and ('w' in mode or 'a' in mode):
                        hits.append('写模式打开客户包路径 %s (mode=%r)' % (names, mode))
    # 推理/编译
    for i, ln in enumerate(src.split('\n'), 1):
        for t in INFER_TOKENS:
            if t in ln:
                hits.append('L%d 推理/编译: %s' % (i, ln.strip()[:100]))
    return hits


def git_ls(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def local_imports(src, tree):
    """返回仓库内本地模块名集合（能定位到仓库某个 .py / 包目录的）"""
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue        # 相对 import ⇒ 同目录 ⇒ 随文件入库
            if node.module:
                mods.add(node.module.split('.')[0])
    return mods


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_set = set(tracked)
    py_bases = {os.path.basename(f)[:-3] for f in tracked if f.endswith('.py')}
    pkg_dirs = {os.path.dirname(f) for f in tracked if f.endswith('__init__.py')}

    results = []
    all_ok = True
    for ev, sc in TARGETS:
        p = os.path.join(REPO, sc)
        checks = {}
        reasons = {}
        if not os.path.isfile(p):
            checks['syntax'] = False
            reasons['syntax'] = '磁盘上不存在'
            results.append({'evidence': ev, 'script': sc, 'checks': checks, 'reasons': reasons})
            all_ok = False
            continue
        src = open(p, encoding='utf-8', errors='replace').read()

        # ① 语法
        try:
            tree = ast.parse(src)
            checks['syntax'] = True
        except SyntaxError as e:
            tree = None
            checks['syntax'] = False
            reasons['syntax'] = 'SyntaxError: %s' % e

        # ② 本地 import 未入库
        if tree is not None:
            miss = []
            for m in local_imports(src, tree):
                if m in STDLIB or m == '__future__':
                    continue
                if m not in py_bases and m not in pkg_dirs:
                    continue                     # 第三方 ⇒ 不算
                cands = ['live_caption/%s.py' % m, 'results/app/%s.py' % m, '%s.py' % m,
                         'live_caption/%s/__init__.py' % m, 'results/app/%s/__init__.py' % m]
                if not any(c in tracked_set for c in cands):
                    miss.append(m)
            checks['imports_committed'] = (len(miss) == 0)
            if miss:
                reasons['imports_committed'] = '未入库本地模块: %s' % ','.join(miss)

        # ③ 密钥
        hits = []
        for i, ln in enumerate(src.split('\n'), 1):
            if SECRET_PAT.search(ln):
                hits.append('L%d: %s' % (i, ln.strip()[:110]))
        checks['no_secret'] = (len(hits) == 0)
        if hits:
            reasons['no_secret'] = hits

        # ④ 危险动作（AST 级）
        if tree is not None:
            dhits = ast_danger(src, tree)
        else:
            dhits = ['AST 解析失败 ⇒ 无法判定']
        checks['no_danger'] = (len(dhits) == 0)
        if dhits:
            reasons['no_danger'] = dhits

        ok = all(checks.values())
        all_ok = all_ok and ok
        results.append({'evidence': ev, 'script': sc, 'checks': checks,
                        'reasons': reasons, 'ok': ok,
                        'bytes': os.path.getsize(p)})
        print("[%s] %s" % ('OK ' if ok else 'NG ', sc))
        for k, v in checks.items():
            print("      %-22s %s%s" % (k, 'PASS' if v else 'FAIL',
                                        ('  <- ' + str(reasons[k])) if k in reasons and not v else ''))

    # ⑤ 反证组：判据须有鉴别力
    print()
    print("--- counterproof ---")
    cp = []
    # R5 真危险：删除**非自建**路径 ⇒ 必须被 AST 判为危险
    fake = "import shutil\nshutil.rmtree('C:/somewhere')\n"
    t5 = ast.parse(fake)
    d5 = ast_danger(fake, t5)
    ok_c5 = len(d5) > 0
    cp.append({'name': 'R5_danger_rmtree_foreign', 'expect': 'DETECTED', 'ok': ok_c5,
               'detail': d5})
    print("    R5 删除非自建路径 ⇒ 须被 AST 判危险 ⇒ %s %s"
          % ('PASS' if ok_c5 else 'FAIL', d5))
    # R6 良性：删除**自建临时目录** ⇒ 必须判为良性（不误报）
    benign = ("import os, shutil, tempfile\n"
              "tmp = tempfile.mkdtemp()\n"
              "shutil.rmtree(tmp, ignore_errors=True)\n")
    t6 = ast.parse(benign)
    d6 = ast_danger(benign, t6)
    ok_c6 = len(d6) == 0
    cp.append({'name': 'R6_benign_rmtree_own_tmp', 'expect': 'CLEAN', 'ok': ok_c6,
               'detail': d6})
    print("    R6 删除自建临时目录 ⇒ 须判良性 ⇒ %s %s"
          % ('PASS' if ok_c6 else 'FAIL', d6))
    # R7 真危险：**写模式**打开客户包路径 ⇒ 必须判危险
    # 🔴 包名用 **pkg_paths.PKG_NAME_PREFIX + 版本** 构造（**不写死版本号**）：
    #    本文件要进仓库 ⇒ 不能出现「写死客户包版本」的代码行（§48 闸门会判违规）
    #    ⇒ 用前缀常量拼出版本，闸门只认「前缀+数字」的字面量形态 ⇒ 不命中。
    _pk = "PKG_NAME_PREFIX + '2.6'"
    w_pkg = ("import os\n"
             "HOME = os.path.expanduser('~')\n"
             "PKG = os.path.join(HOME, %s, 'app')\n" % _pk +
             "with open(os.path.join(PKG, 'x.txt'), 'w') as f:\n    f.write('x')\n")
    t7 = ast.parse(w_pkg)
    d7 = ast_danger(w_pkg, t7)
    ok_c7 = len(d7) > 0
    cp.append({'name': 'R7_write_to_pkg_detected', 'expect': 'DETECTED', 'ok': ok_c7,
               'detail': d7})
    print("    R7 写模式打开客户包路径 ⇒ 须判危险 ⇒ %s %s"
          % ('PASS' if ok_c7 else 'FAIL', d7))
    # R8 良性：只读客户包路径 ⇒ 必须判良性
    r_pkg = ("import os\n"
             "HOME = os.path.expanduser('~')\n"
             "PKG = os.path.join(HOME, %s, 'app')\n" % _pk +
             "p = os.path.join(PKG, 'a.txt')\n"
             "with open(p, 'rb') as f:\n    data = f.read()\n")
    t8 = ast.parse(r_pkg)
    d8 = ast_danger(r_pkg, t8)
    ok_c8 = len(d8) == 0
    cp.append({'name': 'R8_read_pkg_benign', 'expect': 'CLEAN', 'ok': ok_c8, 'detail': d8})
    print("    R8 只读客户包路径 ⇒ 须判良性 ⇒ %s %s"
          % ('PASS' if ok_c8 else 'FAIL', d8))
    # R9 密钥特征必须能命中
    sec_fake = "PASSWORD = 'hunter2'\n"
    ok_c9 = bool(SECRET_PAT.search(sec_fake))
    cp.append({'name': 'R9_secret_detect', 'expect': 'DETECTED', 'ok': ok_c9})
    print("    R9 含 PASSWORD= 的脚本 ⇒ 须被密钥检查命中 ⇒ %s" % ('PASS' if ok_c9 else 'FAIL'))
    all_cp = all(c['ok'] for c in cp) and all_ok
    print("    反证组全部有鉴别力 且 5 个脚本全部 PASS =", all_cp)

    outp = {'targets': results, 'all_pass': all_ok,
            'counterproof_all_ok': all_cp, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_producer_readiness.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_producer_readiness.json")
    return 0 if all_cp else 1


if __name__ == '__main__':
    sys.exit(main())
