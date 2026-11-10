#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_app425_hist_scan3.py — 历史影响定界（v3 · 定案版）

🔴🔴 v1/v2 的 D2 判据都有**自身缺陷**，本版修掉（MEMORY §四「闸门自己的判据也会是错的」）：
   v1: 用 `ast.literal_eval` 读引擎表 ⇒ 真表值是 `dict(...)` 调用 ⇒ 抛异常 ⇒ 表读成空
       ⇒ **假阴性**（rc5/rc6 有缺陷被判成 NA）。
   v1: 判据依赖表名 `ENGINES_ASR06B` ⇒ rc5 把 kind='asr06b' 直接写在 `ENGINES` 里
       ⇒ **假阴性**。
   v2: 修正了上面两条，但收集时**没有只筛 asr06b** ⇒ 把所有 kind 都算成「命中」
       ⇒ **假阳性**（v1.13…rc4 全被判 BUG，而它们根本没有 0.6B 档）。

【v3 的 D2 判据（不依赖表名、不依赖 literal_eval）】
  1. 用 AST 走 ASR 引擎表（`ENGINES` / `ENGINES_ASR06B`），**只**挑 `kind=='asr06b'`
     的条目（兼容 `dict(...)` 调用与 `{...}` 字面量）。
  2. 若表里**没有** asr06b 条目 ⇒ NA（该包根本没有 0.6B 档 ⇒ 与本缺陷无关）。
  3. 若表里有 asr06b 条目 ⇒ **行为级判定**（不只看 AST）：
     把包内 `build_asr_options` 的**真实源码**抽出来，在**桩环境**里执行
     （只 stub 掉 `device_config` / `_asr_ir_ready` / `ASR_PRECISION` / `CUDA_DIR`），
     对一个固定的设备列表跑一遍，**统计输出里 label 是否出现重复**。
     ⇒ 重复 label ⇒ GUI 靠 label 反查会静默取错档 ⇒ **BUG**。
  4. **反证组**：把 rc7 的 `if cfg['kind'] == 'asr06b':` 换成 `if False:`
     ⇒ 行为级判据必须从「无重复」变成「有重复」⇒ 证明判据真的有鉴别力。
     🔴 用替换而不是删行（删行会掏空 if 块 ⇒ SyntaxError ⇒ 假 FAIL）。

【v3 的 D1 判据（GUI 布局被吞）】
  行为特征：`App.__init__` 的语句数塌到 ~24 条 且 **布局调用（pack/grid/migrate）数为 0**；
  同时这些布局调用出现在 `_clone_nearest` 里。
  ⇒ 这就是真机制：`874924a` 把 `App.__init__` 的**后半段（GUI 布局）并进了
     `_clone_nearest`**（它是**兄弟方法**，不是嵌套）⇒ `__init__` 不再建 UI
     ⇒ GUI 只剩 Tk 默认空窗。
  🔴 修正记忆里「误插进 App.__init__ 中间 ⇒ 嵌套」的措辞：**实测是兄弟方法吸收了尾部**。

输出：results/app/app425_hist_scan3.json
"""

import ast
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REL = 'live_caption/live_caption_app.py'

PKGS = [
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.13',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.5',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.0',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.1',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.2',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.3',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v2.4',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc1',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc2',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc3',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc4',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc5',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc6',
    r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc7',
]

# 桩设备列表：覆盖 iGPU / NPU / 独显（rc7 的 asr06b 档设备写死，只出现在 gpu/npu 两档）
STUB_DEVICES = ['GPU.0', 'NPU', 'GPU.1']


# ============ D1：GUI 布局被吞 ============
def diagnose_d1(t, src):
    res = {'d1': 'UNKNOWN', 'd1_detail': '', 'n_init_stmts': None,
           'layout_in_init': None, 'layout_in_clone': None}
    app_cls = next((n for n in t.body
                    if isinstance(n, ast.ClassDef) and n.name == 'App'), None)
    if app_cls is None:
        res['d1_detail'] = 'no class App'
        return res
    init = next((m for m in app_cls.body
                 if isinstance(m, ast.FunctionDef) and m.name == '__init__'), None)
    if init is None:
        res['d1_detail'] = 'no App.__init__'
        return res

    def layout_count(node):
        return sum(1 for n in ast.walk(node)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr in ('pack', 'grid', 'migrate'))

    res['n_init_stmts'] = len(init.body)
    res['layout_in_init'] = layout_count(init)
    cn = next((m for m in app_cls.body
               if isinstance(m, ast.FunctionDef) and m.name == '_clone_nearest'), None)
    res['layout_in_clone'] = layout_count(cn) if cn else 0
    res['clone_nearest_exists'] = cn is not None

    if res['n_init_stmts'] < 60 and res['layout_in_init'] == 0:
        res['d1'] = 'BROKEN'
        res['d1_detail'] = (
            'App.__init__ collapsed to %d stmts with 0 layout calls; the %d '
            'layout calls live in _clone_nearest (sibling method) => GUI never built'
            % (res['n_init_stmts'], res['layout_in_clone']))
    elif res['layout_in_init'] > 0:
        res['d1'] = 'OK'
        res['d1_detail'] = ('App.__init__ n_stmts=%d with %d layout calls'
                            % (res['n_init_stmts'], res['layout_in_init']))
    else:
        res['d1_detail'] = ('n_init_stmts=%d layout_in_init=%d'
                            % (res['n_init_stmts'], res['layout_in_init']))
    return res


# ============ D2：asr06b 档 label 撞车（行为级） ============
def asr06b_entries(t):
    """只挑 kind=='asr06b' 的引擎表条目。兼容 dict(...) 调用与 {...} 字面量。"""
    hits = []

    def kind_of(v):
        if isinstance(v, ast.Call) and getattr(v.func, 'id', None) == 'dict':
            for kw in v.keywords:
                if kw.arg == 'kind' and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    return kw.value.value
        if isinstance(v, ast.Dict):
            for k, vv in zip(v.keys, v.values):
                if isinstance(k, ast.Constant) and k.value == 'kind' \
                        and isinstance(vv, ast.Constant) \
                        and isinstance(vv.value, str):
                    return vv.value
        return None

    for n in ast.walk(t):
        if not isinstance(n, ast.Assign):
            continue
        tgt = n.targets[0]
        if not (isinstance(tgt, ast.Name)
                and tgt.id in ('ENGINES', 'ENGINES_ASR06B')):
            continue
        val = n.value
        pairs = []
        if isinstance(val, ast.Dict):
            pairs = list(zip(val.keys, val.values))
        elif isinstance(val, ast.Call) and getattr(val.func, 'id', None) == 'dict':
            pairs = [(None, v) for v in val.values]
        for k, v in pairs:
            kd = kind_of(v)
            if kd == 'asr06b':
                kn = k.value if isinstance(k, ast.Constant) and isinstance(k.value, str) else '<expr>'
                hits.append((tgt.id, kn))
    return hits


def run_build_asr_options(src, devices=None, pkg_root=None,
                           force_asr06b_present=None):
    """把包内 build_asr_options 的**真实源码**抽出来，在桩环境里执行。

    ⇒ 这是**行为级**判定（真跑一次，看输出），不是只看 AST。
    ⇒ 不 import 被测模块（避免副作用/缺依赖），只 exec 该函数自身的源码。
    ⇒ 模块级常量（ENGINES / ENGINES_ASR06B / ASR_PRECISION …）**按源码顺序整体执行**，
       这样表之间的相互引用不会 NameError。
    返回 (ok, options_list, error)
    """
    import os as _os
    t = ast.parse(src)
    fn = next((n for n in ast.walk(t)
               if isinstance(n, ast.FunctionDef) and n.name == 'build_asr_options'),
              None)
    if fn is None:
        return False, [], 'no build_asr_options'
    fn_src = ast.get_source_segment(src, fn)
    if not fn_src:
        return False, [], 'cannot extract source segment'

    class _DC:
        @staticmethod
        def is_cuda_device(dev):
            return 'CUDA' in str(dev).upper()

        @staticmethod
        def device_label(dev):
            s = str(dev).upper()
            if s == 'NPU':
                return 'Intel NPU'
            if s == 'GPU.0':
                return 'Intel GPU（集显）'
            return 'NVIDIA 独显'

    g = {'__name__': '__stub__', 'os': _os, 'device_config': _DC,
         'CUDA_DIR': None, '_asr_ir_ready': lambda cfg: True}
    # 🔴 `APP_DIR` 由 `__file__` 推导 ⇒ 把它设成**包内真实路径**，
    #    则 `PKG_ROOT` / `MODELS` / `_MODEL_ALIASES` / `_model_path` 全部是**真实值**
    #    ⇒ 「0.6B 模型是否就位」成为**事实判定**，而不是我瞎猜的桩。
    if pkg_root:
        g['__file__'] = os.path.join(pkg_root, 'app', 'live_caption_app.py')

    # ① 模块级简单赋值（逐条 exec ⇒ 相互引用按顺序可解析；失败者跳过）
    mod_assigns = []
    for n in t.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            mod_assigns.append(n)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            mod_assigns.append(n)
    for n in mod_assigns:
        seg = ast.get_source_segment(src, n)
        if not seg:
            continue
        try:
            exec(compile(seg, '<assign>', 'exec'), g)
        except Exception:
            pass

    # ② 需要用到的 helper 函数（**真实源码**）
    for helper in ('_model_path', 'active_asr_engines', 'active_asr_precision',
                   '_asr06b_models_present'):
        hfn = next((n for n in ast.walk(t)
                    if isinstance(n, ast.FunctionDef) and n.name == helper), None)
        if hfn is not None:
            hsrc = ast.get_source_segment(src, hfn)
            if hsrc:
                try:
                    exec(compile(hsrc, '<helper>', 'exec'), g)
                except Exception:
                    pass
        if helper not in g:
            if helper == 'active_asr_engines':
                g[helper] = lambda: (g.get('ENGINES_ASR06B')
                                     or g.get('ENGINES') or {})
            elif helper == 'active_asr_precision':
                g[helper] = lambda: (g.get('ASR_PRECISION_ASR06B')
                                     or g.get('ASR_PRECISION') or {})
            elif helper == '_asr06b_models_present':
                g[helper] = (lambda: bool(force_asr06b_present))
            else:
                g[helper] = (lambda n: _os.path.join('__no_models__', n))

    # ③ force 覆写（仅用于「假如 0.6B 不就位」的反事实臂）
    if force_asr06b_present is not None:
        g['_asr06b_models_present'] = lambda: bool(force_asr06b_present)

    g['devices'] = list(devices if devices is not None else STUB_DEVICES)

    try:
        exec(compile(fn_src, '<bao>', 'exec'), g)
        opts = g['build_asr_options'](g['devices'])
    except Exception as e:
        return False, [], '%s: %s' % (type(e).__name__, e)
    if opts is None:
        return False, [], 'function returned None'
    return True, list(opts), ''


def diagnose_d2(src, pkg_root=None, force_asr06b_present=None):
    res = {'d2': 'UNKNOWN', 'd2_detail': '', 'asr06b_entries': [],
           'n_opts': None, 'dup_labels': [], 'opt_labels': []}
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        res['d2_detail'] = 'SyntaxError: %s' % e
        return res

    hits = asr06b_entries(t)
    res['asr06b_entries'] = hits
    if not hits:
        res['d2'] = 'NA'
        res['d2_detail'] = 'no kind=="asr06b" entry in ASR engine table'
        return res

    ok, opts, err = run_build_asr_options(src, pkg_root=pkg_root,
                                          force_asr06b_present=force_asr06b_present)
    if not ok:
        res['d2'] = 'UNKNOWN'
        res['d2_detail'] = 'behavioral run failed: %s' % err
        return res

    res['n_opts'] = len(opts)
    labels = [o.get('label') for o in opts]
    res['opt_labels'] = labels
    seen, dup = set(), []
    for lb in labels:
        if lb in seen:
            dup.append(lb)
        seen.add(lb)
    res['dup_labels'] = dup
    if dup:
        res['d2'] = 'BUG'
        res['d2_detail'] = ('build_asr_options produced %d options with '
                            'duplicate label(s) %s => GUI label-reverse-lookup '
                            'picks the wrong ASR engine silently'
                            % (len(opts), sorted(set(dup))))
    else:
        res['d2'] = 'OK'
        res['d2_detail'] = ('build_asr_options produced %d options, all labels '
                            'unique: %s' % (len(opts), labels))
    return res


def diagnose(src, pkg_root=None, force_asr06b_present=None):
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        return {'d1': 'UNKNOWN', 'd2': 'UNKNOWN',
                'd1_detail': 'SyntaxError: %s' % e, 'd2_detail': 'SyntaxError'}
    r = diagnose_d1(t, src)
    r.update(diagnose_d2(src, pkg_root=pkg_root,
                          force_asr06b_present=force_asr06b_present))
    return r


def pkg_app_py(pkg):
    for rel in (os.path.join('app', 'live_caption_app.py'),
                os.path.join('app', 'app', 'live_caption_app.py'),
                'live_caption_app.py'):
        p = os.path.join(pkg, rel)
        if os.path.isfile(p):
            return p
    return None


def git(*a):
    return subprocess.run(['git'] + list(a), cwd=REPO, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def break_asr06b_branch(src):
    """把 `build_asr_options` **内部**的 `if cfg['kind'] == 'asr06b':` 改成 `if False:`

    返回 (新源码 or None, 信息 dict)
    🔴 用 AST 定位调用点 ⇒ 只改 build_asr_options 里那一处（全文该串出现 2 次）
    🔴 用 `if False:` 替换而不是删行 ⇒ if 块不会塌成 SyntaxError
    """
    t = ast.parse(src)
    fn = next((n for n in ast.walk(t)
               if isinstance(n, ast.FunctionDef) and n.name == 'build_asr_options'),
              None)
    if fn is None:
        return None, {'error': 'no build_asr_options'}
    lines = src.splitlines(keepends=True)
    hits = []
    for n in ast.walk(fn):
        if (isinstance(n, ast.If)
                and isinstance(n.test, ast.Compare)
                and isinstance(n.test.left, ast.Subscript)
                and isinstance(n.test.left.slice, ast.Constant)
                and n.test.left.slice.value == 'kind'
                and len(n.test.comparators) == 1
                and isinstance(n.test.comparators[0], ast.Constant)
                and n.test.comparators[0].value == 'asr06b'):
            hits.append(n.test.lineno)
    if len(hits) != 1:
        return None, {'error': 'expected exactly 1 callsite in fn, got %d'
                             % len(hits), 'lines': hits}
    ln = hits[0]
    old = lines[ln - 1]
    indent = old[:len(old) - len(old.lstrip())]
    lines[ln - 1] = indent + 'if False:  # anti-control: asr06b branch disabled\n'
    return ''.join(lines), {'n_callsites_in_fn': len(hits), 'line': ln,
                            'old': old.strip()[:90],
                            'new': lines[ln - 1].strip()[:90]}


def main():
    out = {
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'criterion_note': (
            'v3 定案：D1 = AST（__init__ 语句数塌陷 + 布局调用数 0 ⇒ 布局被并进 '
            '_clone_nearest 兄弟方法）；D2 = **行为级**（把包内 build_asr_options '
            '真实源码抽出来在桩环境里真跑一遍 ⇒ 统计输出 label 是否重复）。'
            '🔴 v1 用 literal_eval 读表 ⇒ 表读成空 ⇒ 假阴性；'
            '🔴 v1 依赖表名 ENGINES_ASR06B ⇒ rc5 假阴性；'
            '🔴 v2 收集时没只筛 asr06b ⇒ 假阳性（v1.13…rc4 全中）。'),
        'stub_devices': STUB_DEVICES,
        'packages': [],
        'commits': [],
        'neg_control': {},
    }

    for pkg in PKGS:
        if not os.path.isdir(pkg):
            out['packages'].append({'pkg': pkg, 'state': 'ABSENT_ON_DISK'})
            continue
        ap = pkg_app_py(pkg)
        if not ap:
            out['packages'].append({'pkg': pkg, 'state': 'NO_GUI_FILE'})
            continue
        src = open(ap, 'r', encoding='utf-8').read()
        d = diagnose(src, pkg_root=pkg)
        st = os.stat(ap)
        d.update({'pkg': pkg, 'state': 'PRESENT', 'app_py': ap,
                  'app_py_bytes': st.st_size,
                  'app_py_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                               time.localtime(st.st_mtime))})
        out['packages'].append(d)

    # ---- 逐 commit ----
    log = git('log', '--format=%H|%h|%ad|%s', '--date=format:%Y-%m-%d %H:%M:%S',
              '--', REL)
    for line in log.stdout.splitlines():
        if not line.strip():
            continue
        full, short, date, subj = line.split('|', 3)
        r = git('show', '%s:%s' % (full, REL))
        if r.returncode != 0:
            out['commits'].append({'sha': short, 'date': date, 'subject': subj,
                                    'error': 'git show failed'})
            continue
        d = diagnose(r.stdout)
        d.update({'sha': short, 'date': date, 'subject': subj})
        out['commits'].append(d)

    out['all_d1_broken'] = [c['sha'] for c in out['commits'] if c.get('d1') == 'BROKEN']
    out['all_d2_bug'] = [c['sha'] for c in out['commits'] if c.get('d2') == 'BUG']

    # ---- 反证组：破坏 rc7 的 asr06b 分支 ⇒ 行为级判据必须变 BUG ----
    # 🔴 用 **AST 定位** build_asr_options 内部的那一处 `if cfg['kind'] == 'asr06b':`
    #    （全文里该串出现 **2 次**：另一次在别的函数里 ⇒ 全文替换会误伤）
    # 🔴 用 **替换 `if False:`** 而不是删行（删行会掏空 if 块 ⇒ SyntaxError ⇒ 假 FAIL）
    rc7 = pkg_app_py(PKGS[-1])
    neg = {}
    if rc7:
        src7 = open(rc7, 'r', encoding='utf-8').read()
        # 🔴 必须传 pkg_root ⇒ 否则 `__file__` 不对 ⇒ MODELS 解析错
        #    ⇒ `_asr06b_models_present()` 误判为 False ⇒ 走 R2T2 引擎表 ⇒ 测不到 asr06b 档
        neg['rc7_intact'] = diagnose(src7, pkg_root=PKGS[-1])
        neg['rc7_anchor_text_count'] = src7.count("if cfg['kind'] == 'asr06b':")
        broken, info = break_asr06b_branch(src7)
        neg['rc7_anticontrol_surgery'] = info
        neg['rc7_anticontrol'] = (diagnose(broken, pkg_root=PKGS[-1])
                                  if broken is not None else {'error': 'surgery failed'})
    out['neg_control'] = neg

    a = neg.get('rc7_intact', {})
    b = neg.get('rc7_anticontrol', {})
    rc6 = next((p for p in out['packages']
                if p.get('pkg', '').endswith('rc6')), {})
    out['neg_control_selfcheck'] = {
        'anchor_text_count_in_rc7': neg.get('rc7_anchor_text_count'),
        'surgery_targeted_single_callsite':
            neg.get('rc7_anticontrol_surgery', {}).get('n_callsites_in_fn') == 1,
        'rc7_intact_d2_OK': a.get('d2') == 'OK',
        'anticontrol_d2_BUG': b.get('d2') == 'BUG',
        'criterion_has_discriminating_power': (a.get('d2') == 'OK'
                                               and b.get('d2') == 'BUG'),
        'rc6_detected_as_BUG': rc6.get('d2') == 'BUG',
    }

    def collect(key, val):
        return [os.path.basename(p['pkg']) for p in out['packages']
                if p.get('state') == 'PRESENT' and p.get(key) == val]

    out['summary'] = {
        'n_pkgs_present': sum(1 for p in out['packages'] if p.get('state') == 'PRESENT'),
        'd1_broken_packages': collect('d1', 'BROKEN'),
        'd2_bug_packages': collect('d2', 'BUG'),
        'd2_ok_packages': collect('d2', 'OK'),
        'd2_na_packages': collect('d2', 'NA'),
    }

    # ---- zip 级复核：MiniMVP rc5/rc6/rc7 的 zip 内 app_py **真跑一遍** ----
    # 🔴 交付口径 = 「zip 内含本轮代码」（看 mtime）⇒ 必须验 zip，不只看目录
    import zipfile
    zips = {
        'rc5': (r'C:\Users\Trekker-PTL\shared\minimvp'
                r'\Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip'),
        'rc6': (r'C:\Users\Trekker-PTL\shared\minimvp'
                r'\Confucius4_LiveCaption_MiniMVP_v1.0-rc6_perftest.zip'),
        'rc7': (r'C:\Users\Trekker-PTL\shared\minimvp'
                r'\Confucius4_LiveCaption_MiniMVP_v1.0-rc7_perftest.zip'),
    }
    out['zip_level'] = {}
    for tag, z in zips.items():
        if not os.path.isfile(z):
            out['zip_level'][tag] = {'zip': z, 'state': 'ABSENT_ON_DISK'}
            continue
        st = os.stat(z)
        rec = {'zip': z, 'state': 'PRESENT', 'zip_bytes': st.st_size,
               'zip_mtime': time.strftime('%Y-%m-%d %H:%M:%S',
                                          time.localtime(st.st_mtime))}
        try:
            with zipfile.ZipFile(z) as zf:
                names = [n for n in zf.namelist()
                         if n.endswith('app/live_caption_app.py')]
                if not names:
                    rec['error'] = 'app_py not found in zip'
                else:
                    nm = names[0]
                    data = zf.read(nm).decode('utf-8')
                    rec['member'] = nm
                    rec['member_bytes'] = len(data.encode('utf-8'))
                    # zip 内代码 vs 目录内代码（逐字节）
                    dirp = os.path.join(PKGS[-1].replace('rc7', tag),
                                        'app', 'live_caption_app.py')
                    if os.path.isfile(dirp):
                        with open(dirp, 'rb') as f:
                            d2b = f.read()
                        rec['zip_eq_dir'] = (d2b == data.encode('utf-8'))
                    dg = diagnose(data, pkg_root=PKGS[-1].replace('rc7', tag))
                    rec['d1'] = dg['d1']
                    rec['d2'] = dg['d2']
                    rec['d2_detail'] = dg['d2_detail'][:220]
                    rec['n_opts'] = dg['n_opts']
                    rec['dup_labels'] = dg['dup_labels']
        except Exception as e:
            rec['error'] = '%s: %s' % (type(e).__name__, e)
        out['zip_level'][tag] = rec

    dst = os.path.join(REPO, 'results', 'app', 'app425_hist_scan3.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('WROTE: %s' % dst)
    print(json.dumps(out['summary'], ensure_ascii=False, indent=1))
    print('\nselfcheck: %s' % json.dumps(out['neg_control_selfcheck'], ensure_ascii=False))
    print('\n--- commit 判定 ---')
    for c in out['commits'][:12]:
        print('%s %s D1=%-8s D2=%-5s | %s' % (c.get('sha'), c.get('date'),
                                               c.get('d1'), c.get('d2'),
                                               (c.get('subject') or '')[:46]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
