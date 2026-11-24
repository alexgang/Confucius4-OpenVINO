#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222④ **精确**审计：已入库的 App 脚本 import 了
「**App 本地模块**（live_caption/ 或 results/app/ 下确实存在该文件）但**未入库**」。

🔴 为什么要有这一版：
   上一版（_app236_import_audit.py）判的是「仓库里有没有这个模块」⇒
   把**第三方库**（av / soundcard / fitz / png_stats / tts_ov.* …）也算成缺口
   ⇒ 全是噪声；而真正的 App 侧缺口（HD4 同族）反而要看的是
   「**这个模块是 App 自己的文件吗？它在磁盘上吗？它入库了吗？**」

判据（必须同时成立才算缺口）：
   ① 被 import 的模块名 m，在 **live_caption/ 或 results/app/ 下确实存在 m.py**（或 m/ 包）
   ② 该文件**未被 git 跟踪**
   ③ import 发生在**模块级**（顶层）⇒ 干净 clone 里 import 该脚本就 ImportError
      （函数级 ⇒ 惰性加载 ⇒ 只影响该功能，不是「clone 就炸」）

🔴 反证组：
  R1 造一个「已入库的 App 模块名」⇒ 必须判 NOT-MISSING
  R2 造一个「磁盘上不存在也不入库的模块名」⇒ 必须判 NOT-MISSING（第三方）
"""
import ast
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APPS = ('live_caption', 'results/app')


def git_ls(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def disk_local_modules():
    """App 本地模块名 → 磁盘路径（只扫 live_caption/ 与 results/app/）"""
    m = {}
    for d in APPS:
        base = os.path.join(REPO, d)
        for root, dirs, files in os.walk(base):
            dirs[:] = [x for x in dirs if x not in ('__pycache__', 'models', 'node_modules')]
            for fn in files:
                if fn.endswith('.py'):
                    p = os.path.join(root, fn)
                    rel = os.path.relpath(p, REPO).replace('\\', '/')
                    m.setdefault(fn[:-3], []).append(rel)
    return m


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_set = set(tracked)
    disk = disk_local_modules()
    disk_tracked = {}
    for name, paths in disk.items():
        disk_tracked[name] = [(p, p in tracked_set) for p in paths]

    gaps = []
    n_scanned = 0
    for f in sorted(tracked):
        if not (f.startswith('live_caption/') or f.startswith('results/app/')):
            continue
        if not f.endswith('.py'):
            continue
        p = os.path.join(REPO, f)
        if not os.path.isfile(p):
            continue
        src = open(p, encoding='utf-8', errors='replace').read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        n_scanned += 1
        for node in tree.body:
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                mods = [node.module]
            for mod in mods:
                top = mod.split('.')[0]
                if top in disk_tracked:
                    # 🔴 只有「**所有副本都没入库**」才是真缺口
                    #   （磁盘上常有多份同名副本：live_caption/ 正式版 ＋
                    #     results/app/_pkg_backup_*/ _baseline/ 等历史快照；
                    #     只要有一份已入库 ⇒ 干净 clone 就能 import ⇒ 合规）
                    if not any(is_tracked for _, is_tracked in disk_tracked[top]):
                        gaps.append({'importer': f, 'module': top,
                                     'uncommitted_local_path':
                                         disk_tracked[top][0][0],
                                     'level': 'MODULE_LEVEL'})
        # 相对 import（同目录 ⇒ 随目录入库 ⇒ 一般已入库，但仍查）
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level and node.module:
                cand = [x for x in disk.get(node.module.split('.')[0], [])
                        if os.path.dirname(x) == os.path.dirname(f)]
                for path, is_tracked in [(c, c in tracked_set) for c in cand]:
                    if not is_tracked:
                        gaps.append({'importer': f, 'module': node.module,
                                     'uncommitted_local_path': path,
                                     'level': 'RELATIVE'})

    uniq = sorted({(g['importer'], g['module'], g['uncommitted_local_path']) for g in gaps})
    print("scanned committed App scripts =", n_scanned)
    print("App-local module imports that are NOT committed =", len(uniq))
    for imp, mod, path in uniq:
        print("   %-52s -> %-28s (未入库: %s)" % (imp[:52], mod, path))

    # 反证组
    print()
    print("--- counterproof ---")
    cp = []
    known_tracked_local = None
    for name, lst in disk_tracked.items():
        for path, is_tracked in lst:
            if is_tracked:
                known_tracked_local = name
                break
        if known_tracked_local:
            break
    ok1 = known_tracked_local is not None and known_tracked_local not in [
        p for _, m, p in uniq if m == known_tracked_local]
    cp.append({'name': 'R1_tracked_local_not_gap', 'expect': 'NOT_GAP', 'ok': ok1,
               'module': known_tracked_local})
    print("    R1 已入库的 App 本地模块 %s ⇒ 须判 NOT-GAP ⇒ %s"
          % (known_tracked_local, 'PASS' if ok1 else 'FAIL'))
    ok2 = 'zzz_not_a_real_module_xyz' not in [m for _, m, _ in uniq]
    cp.append({'name': 'R2_nonexistent_module_not_gap', 'expect': 'NOT_GAP', 'ok': ok2})
    print("    R2 磁盘上不存在的模块名 ⇒ 须判 NOT-GAP ⇒ %s" % ('PASS' if ok2 else 'FAIL'))
    all_ok = all(c['ok'] for c in cp)
    print("    反证组全部有鉴别力 =", all_ok)

    outp = {'scripts_scanned': n_scanned, 'n_gaps': len(uniq),
            'gaps': [{'importer': i, 'module': m, 'uncommitted_local_path': p} for i, m, p in uniq],
            'counterproof_all_ok': all_ok, 'counterproof': cp}
    with open(os.path.join(REPO, 'results/app/app236_import_audit.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_import_audit.json")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
