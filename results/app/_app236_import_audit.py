#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-236 §222④ 审计（修正版）：**已入库脚本 import 的模块 ⇒ 必须入库**。

🔴 初版逻辑漏洞（已修）：
   初版写的是「若模块名**不在**已入库集合里 ⇒ 当第三方，跳过」⇒
   于是「**仓库里根本没有**这个模块」这种情况被当成第三方**放过了**
   ⇒ 恰恰漏掉了 §222④ 要抓的真缺陷（HD4 同族：`package_profiles.py`）。

本版改成三分类，对每个 import 逐个判：
   RESOLVABLE  ⇒ 仓库内能定位（已入库的 .py 或包目录）⇒ 合规
   THIRD_PARTY ⇒ 已知第三方/标准库 ⇒ 合规
   MISSING     ⇒ 仓库内**根本不存在** ⇒ 🔴 缺口（须再判是否「按设计只在客户包里」）

对 MISSING 再判一次「是否按设计只在客户包里」：
   若该模块文件存在于**客户包**内（app/ 或 app/asr_spk/ 等）
   ⇒ 归类 PACKAGE_ONLY（按设计，运行时从包里加载）⇒ 不是仓库缺陷
   ⇒ 但若**已入库的仓库脚本**在**模块级**（非函数内）import 它
     ⇒ 干净 clone 里 import 该仓库脚本就会 ImportError ⇒ 仍是缺口
"""
import ast
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STDLIB = set(getattr(sys, 'stdlib_module_names', set())) | {
    'winreg', 'win32com', 'pythoncom', 'wmi', 'pywintypes'}

THIRD_PARTY = set('''numpy np torch torchvision torchaudio soundfile scipy librosa
openvino transformers tokenizers accelerate safetensors huggingface_hub sentencepiece
PIL cv2 matplotlib pandas yaml pydantic requests flask tqdm numba onnx onnxruntime
psutil pyaudio sounddevice webrtcvad pywinauto uiautomation psutil win32api win32con
paramiko scp ftplib fabric
openai anthropic llama_cpp qwen_tts babelvox demucs einops addict'''.split())


def git_ls(*a):
    return subprocess.run(['git', '-C', REPO] + list(a),
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace').stdout


def main():
    tracked = [f for f in git_ls('ls-files').split('\n') if f.strip()]
    tracked_set = set(tracked)
    repo_py = {os.path.basename(f)[:-3] for f in tracked if f.endswith('.py')}
    repo_pkgs = {os.path.dirname(f).split('/')[-1] for f in tracked if f.endswith('__init__.py')}
    repo_pkgs |= {os.path.basename(f)[:-3] for f in tracked if f.endswith('__init__.py')}

    # 客户包里存在的模块（按设计只在包里 ⇒ PACKAGE_ONLY）
    pkg_dirs = []
    home = os.path.expanduser('~')
    for d in os.listdir(home):
        if d.startswith('Confucius4_LiveCaption_v') and os.path.isdir(os.path.join(home, d)):
            pkg_dirs.append(os.path.join(home, d))
    pkg_modules = set()
    for pd in pkg_dirs:
        for root, dirs, files in os.walk(pd):
            dirs[:] = [x for x in dirs if x not in ('models', 'node_modules', '__pycache__')]
            depth = root[len(pd):].count(os.sep)
            if depth > 3:
                dirs[:] = []
                continue
            for fn in files:
                if fn.endswith('.py'):
                    pkg_modules.add(fn[:-3])
    print("customer pkg dirs scanned =", len(pkg_dirs), "| pkg module basenames =", len(pkg_modules))

    def classify_import(mod):
        top = mod.split('.')[0]
        if top in STDLIB or top == '__future__':
            return 'RESOLVABLE', 'stdlib'
        if top in repo_py or top in repo_pkgs:
            return 'RESOLVABLE', '仓库内已入库'
        if top in THIRD_PARTY:
            return 'THIRD_PARTY', '已知第三方'
        if top in pkg_modules:
            return 'PACKAGE_ONLY', '只在客户包内'
        return 'MISSING', '仓库与客户包都没有'

    findings = []
    scanned = 0
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
        scanned += 1
        # 模块级 import（顶层，不是函数体内）⇒ 干净 clone import 该脚本就会炸
        module_level = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                module_level += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.module and not node.level:
                    module_level.append(node.module)
        for mod in module_level:
            verdict, why = classify_import(mod)
            if verdict in ('MISSING', 'PACKAGE_ONLY'):
                findings.append({'script': f, 'module': mod, 'verdict': verdict,
                                 'why': why, 'level': 'MODULE_LEVEL'})
        # 函数内 import（惰性加载）⇒ 只在运行时才需要 ⇒ 分级为「运行时」
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(node):
                    mods = []
                    if isinstance(sub, ast.Import):
                        mods += [a.name for a in sub.names]
                    elif isinstance(sub, ast.ImportFrom) and sub.module and not sub.level:
                        mods.append(sub.module)
                    for mod in mods:
                        verdict, why = classify_import(mod)
                        if verdict in ('MISSING', 'PACKAGE_ONLY'):
                            findings.append({'script': f, 'module': mod, 'verdict': verdict,
                                             'why': why, 'level': 'FUNCTION_LEVEL'})

    ml = [x for x in findings if x['level'] == 'MODULE_LEVEL']
    fl = [x for x in findings if x['level'] == 'FUNCTION_LEVEL']
    print()
    print("scanned committed App scripts =", scanned)
    print("MODULE_LEVEL gaps (import 该脚本就炸) =", len(ml))
    seen = set()
    for x in ml:
        k = (x['script'], x['module'])
        if k in seen:
            continue
        seen.add(k)
        print("   ", x['script'], "->", x['module'], "|", x['verdict'], "|", x['why'])
    print("FUNCTION_LEVEL gaps (运行时惰性加载，干净 clone 跑不动该功能) =", len(fl))
    seen2 = set()
    for x in fl:
        k = (x['script'], x['module'])
        if k in seen2:
            continue
        seen2.add(k)
        print("   ", x['script'], "->", x['module'], "|", x['verdict'], "|", x['why'])

    outp = {'scripts_scanned': scanned,
            'module_level_gaps': ml, 'function_level_gaps': fl,
            'n_module_level': len(ml), 'n_function_level': len(fl)}
    with open(os.path.join(REPO, 'results/app/app236_import_audit.json'),
              'w', encoding='utf-8', newline='\n') as fh:
        json.dump(outp, fh, ensure_ascii=False, indent=2)
    print()
    print("wrote results/app/app236_import_audit.json")
    return 0


if __name__ == '__main__':
    sys.exit(main())
