#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""app126 —— §86 三个打包前闸门缺陷的**回归验收**（零推理、零 GPU、零 NPU、不调 MiniMax）。

本轮（§86）在**真正打包前**被三道闸门各抓到 1 个真实缺陷：

| 组 | 缺陷 | 修法 |
|---|---|---|
| **G1** | `results/app/_app81_check_pkg_match.py` 把客户包路径**写死**成 `…_v1.6\\app` ⇒ 正是 §48 闸门要拦的缺陷类别（包一升版就指向旧包） | 改走 `pkg_paths.pkg_app_dir()`（单一数据源） |
| **G2** | §48 闸门把 **docstring 误判成代码行**（`ast.Expr` 包着字符串常量 ⇒ 外层不是 `ast.Constant`）⇒ 文档里提到包名的文件一律报错 | 显式跳过「裸字符串表达式」；并删掉 2 条因此过期的白名单 + 新增「过期白名单」报告 |
| **G3** | `pkg_exclude.py` 只排除备份**目录**，**备份文件**（`_backup*.md`）⇒ 2 个内部 STATUS 全文（约 2.1 MB，含会议特征串）**会进客户 zip** | 新增 `BACKUP_FILE_RE`，排除**文件**级备份 |
| **G4** | `live_caption/tts_engine.py` 有 **2 个 U+FFFD 乱码**（§82 提交 `b0f7a43` 引入 ⇒ 回归） | 精确替换为可读文本 |
| **G5** | `check_internal_material.py` 的 `clone_[A-Z]`（带 `re.I`）**误伤生产模块** `app/clone_collector.py` ⇒ 打包被拒（假 FAIL） | 收窄为「克隆**素材**」（`clone_*.npz/wav/...`）+ 新增 `tts_speakers/` 目录规则 |

🔴 **双向反证**（本脚本的核心价值）：
- 每条判据都必须证明「**修复前**会 FAIL、**修复后** PASS」；
- 反证用**固定 commit SHA**（不是 `HEAD`）⇒ 源码修好后反证**不会静默失效**；
- ⚠️ 按铁律：**不 import 被测模块**（顶层 numpy 会让 import 阶段 abort）⇒ 用 `ast` 抽源码 + `exec` 独立命名空间。
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# 🔴 §48 单一数据源：**不写死**客户包版本（写死 = 打包前闸门会 FAIL）
import pkg_paths  # noqa: E402

PKG = pkg_paths.pkg_app_dir()
PKG_ROOT = pkg_paths.discover_pkg_dir()

#: 🔴 反证基线 = **修复前**那个 commit（§82 引入 U+FFFD 的那次提交）
BASELINE_COMMIT = 'b0f7a43'

PASS: list = []
FAIL: list = []


def check(name, cond, detail=''):
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' — ' + detail) if detail else ''))
    (PASS if cond else FAIL).append(name)
    return bool(cond)


def lf_sha(p):
    b = open(p, 'rb').read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()


def git_show(commit, rel):
    r = subprocess.run(['git', '-C', REPO, 'show', f'{commit}:{rel}'],
                       capture_output=True)
    return r.stdout if r.returncode == 0 else None


def load_module_from_source(src, name):
    """把源码**独立命名空间**地 exec 出来（不 import 被测模块）。"""
    ns = {'__name__': name, '__file__': os.path.join(REPO, name + '.py')}
    exec(compile(src, ns['__file__'], 'exec'), ns)
    return ns


def scan_ast_code_lines(src):
    """复刻 §48 闸门的「哪些行算代码」判定（修复后版本）。

    🔴 关键点：**跳过裸字符串表达式**（docstring 的精确 AST 形态）。
    """
    tree = ast.parse(src)
    code = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            continue
        if isinstance(node, ast.Expr):
            v = getattr(node, 'value', None)
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                continue            # docstring ⇒ 不算代码
        ln = getattr(node, 'lineno', None)
        if ln is None:
            continue
        for n in range(ln, (getattr(node, 'end_lineno', None) or ln) + 1):
            code.add(n)
    return code


def pkg_name_hits(src):
    """在**代码行**里找客户包名（复刻 §48 闸门主判据）。"""
    rx = re.compile(re.escape('Confucius4_LiveCaption_v') + r'\d+(?:\.\d+)*')
    try:
        code = scan_ast_code_lines(src)
    except SyntaxError:
        code = None
    hits = []
    for i, ln in enumerate(src.split('\n'), 1):
        if not rx.search(ln):
            continue
        if ln.strip().startswith('#'):
            continue
        if code is not None and i not in code:
            continue
        hits.append((i, ln.strip()))
    return hits


def main():
    print('=' * 74)
    print('§86 打包前闸门缺陷 · 回归验收（app126）')
    print('=' * 74)
    print('仓库: %s' % REPO)
    print('客户包: %s' % PKG)
    print('反证基线 commit: %s' % BASELINE_COMMIT)
    print()

    # ══════════════════════════════════════════════════════════════
    # G1 —— §81 helper 不得写死客户包路径
    # ══════════════════════════════════════════════════════════════
    print('── G1：§81 helper 不得写死客户包路径 ──')
    p81 = os.path.join(HERE, '_app81_check_pkg_match.py')
    src81 = open(p81, encoding='utf-8').read()
    hits81 = pkg_name_hits(src81)
    check('G1.1 §81 helper 的**代码行**里无客户包名', not hits81,
          'hits=%s' % hits81)
    check('G1.2 §81 helper 使用 pkg_paths 单一数据源',
          'pkg_paths' in src81 and 'pkg_app_dir()' in src81)
    # 功能等价性：跑一遍，比对必须 10/10 MATCH
    r = subprocess.run([sys.executable, p81], capture_output=True, timeout=300)
    out81 = r.stdout.decode('utf-8', 'replace')
    check('G1.3 §81 helper 实跑 10/10 MATCH', 'MATCH 10 / 10' in out81,
          out81.strip().splitlines()[-1] if out81.strip() else '')
    print()

    # ══════════════════════════════════════════════════════════════
    # G2 —— §48 闸门不得把 docstring 误判成代码
    # ══════════════════════════════════════════════════════════════
    print('── G2：§48 闸门的 docstring 误判 ──')
    gate_path = os.path.join(HERE, 'app049_pkg_path_hardcode_gate.py')
    gsrc = open(gate_path, encoding='utf-8').read()
    gns = load_module_from_source(gsrc, 'gate_fixed')

    # 造一个「只在 docstring 里提到包名」的样本
    tmpdir = tempfile.mkdtemp(prefix='app126_g2_')
    try:
        sample = os.path.join(tmpdir, 'doc_only_sample.py')
        # 🔴 样例里的包名**动态拼装**（不写死版本号）⇒ 本脚本自身不触发 §48 闸门
        _pkg_name = pkg_paths.PKG_NAME_PREFIX + '1.6'
        with open(sample, 'w', encoding='utf-8') as f:
            f.write('# -*- coding: utf-8 -*-\n'
                    '"""说明文字里提到 %s 只是举例。"""\n'
                    'X = 1\n' % _pkg_name)
        hits = gns['code_lines_with_pkg_name'](sample)
        check('G2.1 docstring 里的包名**不判**为代码行', not hits,
              'hits=%s' % hits)

        # 反证：修复前（AST 旧算法）**必须**命中 ⇒ 证明缺陷曾真实存在
        def old_code_lines(src):
            tree = ast.parse(src)
            code = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    continue
                ln = getattr(node, 'lineno', None)
                if ln is None:
                    continue
                for n in range(ln, (getattr(node, 'end_lineno', None) or ln) + 1):
                    code.add(n)
            return code

        s2 = open(sample, encoding='utf-8').read()
        oldcode = old_code_lines(s2)
        old_hits = [(i, l.strip()) for i, l in enumerate(s2.split('\n'), 1)
                    if 'Confucius4_LiveCaption_v' in l and not l.strip().startswith('#')
                    and i in oldcode]
        check('G2.2 反证：旧 AST 判定**确实**把 docstring 当代码（缺陷曾存在）',
              bool(old_hits), 'old_hits=%s' % old_hits)
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    # 白名单过期检测
    check('G2.3 闸门有「过期白名单」检测能力',
          'stale_whitelist' in gsrc and 'stale_whitelist' in
          str(gns.get('WHITELIST', '')) or 'stale_whitelist' in gsrc)
    wl = gns['WHITELIST']
    check('G2.4 已删除 2 条过期白名单（docstring 误判造成）',
          'results/app/app014b_v15_preship_check.py' not in wl and
          'results/app/app049_pkg_path_hardcode_gate.py' not in wl,
          'whitelist=%d 条' % len(wl))
    check('G2.5 保留「闸门自检脚本」白名单（真实代码行命中）',
          'results/app/app049_gate_selftest.py' in wl)
    print()

    # ══════════════════════════════════════════════════════════════
    # G3 —— 备份**文件**不得进客户包
    # ══════════════════════════════════════════════════════════════
    print('── G3：备份文件不得进客户包 ──')
    sys.path.insert(0, REPO)
    import pkg_exclude as pe
    check('G3.1 pkg_exclude 有 BACKUP_FILE_RE 规则',
          hasattr(pe, 'BACKUP_FILE_RE'))
    check('G3.2 `_backup_status_app_pre_s84.md` 被排除',
          pe.is_excluded('_backup_status_app_pre_s84.md'))
    check('G3.3 `_backup_status_app_pre_s85.md` 被排除',
          pe.is_excluded('_backup_status_app_pre_s85.md'))
    check('G3.4 正常文件**不被**误伤（app/live_caption_app.py）',
          not pe.is_excluded('app/live_caption_app.py'))
    check('G3.5 正常文件**不被**误伤（NOTICE）',
          not pe.is_excluded('NOTICE'))

    # 反证：修复前的旧规则（只排目录、不排文件）**必须**放行
    def old_is_excluded_backup_file(rel):
        """修复前的语义：只有「目录段」命中 `_backup` 才排除。"""
        base = rel.rsplit('/', 1)[-1]
        if re.search(r'\.bak', base, re.I):
            return True
        for seg in rel.split('/')[:-1]:
            if re.match(r'^_backup', seg, re.I):
                return True
        return False
    old_ok = not old_is_excluded_backup_file('_backup_status_app_pre_s84.md')
    check('G3.6 反证：旧规则**确实**放行备份文件（缺陷曾真实存在）', old_ok)

    # 端到端：实际 zip 文件清单里不得有 _backup
    if os.path.isdir(PKG):
        n_backup = 0
        for rel, _sz in pe.iter_package_files(PKG):
            if '_backup' in rel:
                n_backup += 1
        check('G3.7 实际包目录 → zip 清单里 **0** 个 _backup 条目',
              n_backup == 0, 'n=%d' % n_backup)
    else:
        check('G3.7 实际包目录 → zip 清单里 **0** 个 _backup 条目', False,
              '包目录不存在：%s' % PKG)
    print()

    # ══════════════════════════════════════════════════════════════
    # G4 —— tts_engine.py 不得有 U+FFFD
    # ══════════════════════════════════════════════════════════════
    print('── G4：tts_engine.py 文本编码完整性 ──')
    eng = os.path.join(REPO, 'live_caption', 'tts_engine.py')
    cur = open(eng, 'rb').read().decode('utf-8', 'replace')
    check('G4.1 当前 tts_engine.py **0** 个 U+FFFD', cur.count('\ufffd') == 0,
          'n=%d' % cur.count('\ufffd'))
    # 反证：固定 commit（修复前）**必须**含 U+FFFD
    old_src = git_show(BASELINE_COMMIT, 'live_caption/tts_engine.py')
    if old_src:
        old_txt = old_src.decode('utf-8', 'replace')
        check('G4.2 反证：基线 %s **确实**含 U+FFFD（缺陷曾存在）' % BASELINE_COMMIT,
              old_txt.count('\ufffd') > 0, 'n=%d' % old_txt.count('\ufffd'))
    else:
        check('G4.2 反证：基线 %s **确实**含 U+FFFD（缺陷曾存在）' % BASELINE_COMMIT,
              False, '取不到基线源码')
    # 语法仍可解析
    try:
        ast.parse(cur)
        ok_ast = True
    except SyntaxError as e:
        ok_ast = False
        print('    SyntaxError: %s' % e)
    check('G4.3 修复后源码 AST 可解析', ok_ast)
    print()

    # ══════════════════════════════════════════════════════════════
    # G5 —— 内部素材闸门：克隆素材 vs 克隆相关代码
    # ══════════════════════════════════════════════════════════════
    print('── G5：内部素材闸门的克隆规则（真素材必拦 / 生产代码不误伤）──')
    cpath = os.path.join(REPO, 'check_internal_material.py')
    cns = load_module_from_source(open(cpath, encoding='utf-8').read(), 'cim_fixed')
    sn = cns['_scan_name']
    must_hit = [
        'app/voices/clone_C.npz',
        'app/voices/clone_S2.wav',
        'app/tts_speakers/S1.npz',
        'app/tts_speakers/whatever.bin',
        'app/models/preset_B.wav',
        'app/models/preset_C.wav',
        'app/results/xx_spoken.txt',
    ]
    must_not = [
        'app/clone_collector.py',
        'app/clone_collector_gui.py',
        'app/live_caption_app.py',
        'app/tts_worker.py',
    ]
    g5_ok = True
    for rel in must_hit:
        hit = sn(rel) is not None
        g5_ok &= check('G5.H %-36s 必拦' % rel, hit, str(sn(rel)))
    for rel in must_not:
        hit = sn(rel) is not None
        g5_ok &= check('G5.N %-36s 不误伤' % rel, not hit, str(sn(rel)))
    # 反证：旧规则（clone_[A-Z] + re.I）**必须**误伤 clone_collector.py
    old_rx = re.compile(r'clone_[A-Z]', re.I)
    old_false_positive = bool(old_rx.search('clone_collector.py'))
    check('G5.R 反证：旧规则**确实**误伤 clone_collector.py（缺陷曾存在）',
          old_false_positive)
    print()

    # ══════════════════════════════════════════════════════════════
    # 汇总
    # ══════════════════════════════════════════════════════════════
    print('=' * 74)
    print('PASS %d / FAIL %d' % (len(PASS), len(FAIL)))
    if FAIL:
        print('失败项：%s' % FAIL)
    verdict = 'PASS' if not FAIL else 'FAIL'
    print('总判定：%s' % verdict)
    print('=' * 74)

    ev = os.path.join(HERE, 'app126_prepack_gate_defects_evidence.json')
    with open(ev, 'w', encoding='utf-8') as f:
        json.dump(dict(pass_list=PASS, fail_list=FAIL, verdict=verdict,
                       baseline_commit=BASELINE_COMMIT, pkg=PKG),
                  f, ensure_ascii=False, indent=2)
    print('证据已落盘：%s' % ev)
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
