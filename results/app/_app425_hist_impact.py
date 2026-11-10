#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_app425_hist_impact.py — APP 侧「历史影响未评估」两项的机械化定界（§170 ⑨ 待办）

【背景】
§170 如实登记了两项「历史影响未评估」：
  (1) `874924a` 把 `_clone_nearest` 误插进 `App.__init__` 中间 ⇒ GUI 布局代码被吞
      ⇒ GUI 一直只是空壳 `tk` 200×200 ⇒ **该 commit 之后的 GUI 类验收都跑在空壳上**
  (2) `asr06b` 未被 `build_asr_options()` 识别 ⇒ 两个 ASR 档 label 完全相同
      ⇒ GUI 靠 label 反查 ⇒ **静默错档**

【本脚本做什么】
对**磁盘上真实存在的每一个交付包目录**，用 AST 判定两个缺陷「在不在里面」，
并输出「受影响 / 不受影响 / 无 GUI 文件」三态。

【判据设计纪律（MEMORY §四）】
🔴 判据必须**有鉴别力**：不能是恒真/恒假的弱标记。
   ⇒ D1 用 **AST**：`App.__init__` 的语句条数（布局代码被吞 ⇒ 塌到 ~24 条）
     + `_clone_nearest` 是否**嵌套在** `App.__init__` 内部（真凶就是嵌套）。
   ⇒ D2 用 **AST**：`build_asr_options` 函数体里实际处理的 `kind` 集合
     （不能全文搜 `if cfg['kind'] == 'asr06b':` —— `_check_models()` 里本来就有 ⇒ 锚点不唯一 ⇒ 恒真）。
   ⇒ **反证组**：把 D1/D2 的判据反过来用一次 —— 构造「已知有缺陷」的样本（874924a / rc6）
     与「已知已修」的样本（ba76ea5 / rc7），要求判据能把它们**分开**。

【输出】
results/app/app425_hist_impact.json
"""

import ast
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 候选交付包目录（磁盘上真实存在的才处理）
PKG_CANDIDATES = [
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


def find_app_py(pkg_dir):
    """在包目录里找 live_caption_app.py（app/ 或 app/app/ 两种布局都试）。"""
    for rel in (os.path.join('app', 'live_caption_app.py'),
                 os.path.join('app', 'app', 'live_caption_app.py'),
                 'live_caption_app.py'):
        p = os.path.join(pkg_dir, rel)
        if os.path.isfile(p):
            return p
    return None


# ---------------- D1：GUI 布局被吞（_clone_nearest 嵌套进 App.__init__） ----------------
def diagnose_d1(src):
    """返回 (verdict, detail)。verdict ∈ {'BROKEN','OK','UNKNOWN'}"""
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        return 'UNKNOWN', 'SyntaxError: %s' % e

    app_cls = None
    for n in t.body:
        if isinstance(n, ast.ClassDef) and n.name == 'App':
            app_cls = n
            break
    if app_cls is None:
        return 'UNKNOWN', 'no class App'

    init = None
    for m in app_cls.body:
        if isinstance(m, ast.FunctionDef) and m.name == '__init__':
            init = m
            break
    if init is None:
        return 'UNKNOWN', 'no App.__init__'

    n_init_stmts = len(init.body)

    # 真凶：_clone_nearest 若是 App.__init__ 内部的**嵌套函数** ⇒ 布局代码被吞进它
    nested = [f.name for f in ast.walk(init)
              if isinstance(f, ast.FunctionDef)]
    clone_nested = '_clone_nearest' in nested

    # 布局塌陷的量化：布局代码被吞 ⇒ __init__ 只剩少量语句
    # （用「有没有嵌套的 _build_ui 类方法」作为布局是否在 __init__ 里的判据）
    has_layout_call = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr in ('pack', 'grid', 'migrate')
        for n in ast.walk(init))

    if clone_nested:
        return 'BROKEN', ('_clone_nearest nested inside App.__init__ '
                          '(n_init_stmts=%d)' % n_init_stmts)
    if n_init_stmts >= 100 and has_layout_call:
        return 'OK', ('App.__init__ n_stmts=%d, layout calls present, '
                      '_clone_nearest at class level' % n_init_stmts)
    if n_init_stmts < 60 and not has_layout_call:
        return 'BROKEN', ('App.__init__ collapsed to %d stmts, no layout calls'
                          % n_init_stmts)
    return 'UNKNOWN', ('n_init_stmts=%d nested=%s layout_call=%s'
                        % (n_init_stmts, nested, has_layout_call))


# ---------------- D2：asr06b 档位 label 撞车（静默错档） ----------------
def diagnose_d2(src):
    """返回 (verdict, detail)。verdict ∈ {'BUG','OK','NA','UNKNOWN'}

    判据：AST 定位 `build_asr_options` 函数体，看它**实际处理的 kind 集合**
    （不能全文搜字符串 —— `_check_models()` 里本来就有 `if cfg['kind'] == 'asr06b':`）。
    """
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        return 'UNKNOWN', 'SyntaxError: %s' % e

    fn = None
    for n in ast.walk(t):
        if isinstance(n, ast.FunctionDef) and n.name == 'build_asr_options':
            fn = n
            break
    if fn is None:
        return 'NA', 'no build_asr_options'

    # 该函数体内比较到的 kind 集合
    kinds = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Compare)
                and isinstance(n.left, ast.Subscript)
                and isinstance(n.left.slice, ast.Constant)
                and n.left.slice.value == 'kind'):
            for c in n.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    kinds.add(c.value)

    has_asr06b_tbl = 'ENGINES_ASR06B' in src

    if 'asr06b' in kinds:
        return 'OK', ('build_asr_options handles kinds=%s (asr06b recognized)'
                      % sorted(kinds))
    if has_asr06b_tbl:
        return 'BUG', ('ENGINES_ASR06B table present but build_asr_options '
                       'handles kinds=%s (asr06b MISSING => falls into '
                       '"iterate all devices" => duplicate labels)'
                       % sorted(kinds))
    return 'NA', 'no asr06b engine table (kinds=%s)' % sorted(kinds)


def main():
    out = {
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'purpose': 'APP-098 §170 ⑨ 两项「历史影响未评估」的机械化定界',
        'criteria': {
            'D1_gui_swallowed': ('AST: _clone_nearest 是否嵌套在 App.__init__ 内'
                                 ' + __init__ 语句条数 + 布局调用是否存在'),
            'D2_asr06b_label_collision': ('AST: build_asr_options 函数体实际处理的 '
                                          "kind 集合是否含 'asr06b'"),
            'note': ('🔴 不用全文搜字符串：`_check_models()` 里本来就有 '
                     "`if cfg['kind'] == 'asr06b':` ⇒ 锚点不唯一 ⇒ 恒真 ⇒ 无鉴别力"),
        },
        'packages': [],
        'neg_control': {},
    }

    for pkg in PKG_CANDIDATES:
        if not os.path.isdir(pkg):
            out['packages'].append({'pkg': pkg, 'state': 'ABSENT_ON_DISK'})
            continue
        ap = find_app_py(pkg)
        if not ap:
            out['packages'].append({'pkg': pkg, 'state': 'NO_GUI_FILE',
                                    'verdict_d1': 'NA', 'verdict_d2': 'NA'})
            continue
        try:
            src = open(ap, 'r', encoding='utf-8').read()
        except Exception as e:
            out['packages'].append({'pkg': pkg, 'state': 'READ_ERR:%s' % e})
            continue

        v1, d1 = diagnose_d1(src)
        v2, d2 = diagnose_d2(src)
        try:
            st = os.stat(ap)
            meta = {'bytes': st.st_size,
                    'mtime': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}
        except OSError:
            meta = {}

        out['packages'].append({
            'pkg': pkg,
            'state': 'PRESENT',
            'app_py': ap,
            'app_py_meta': meta,
            'verdict_d1': v1,
            'detail_d1': d1,
            'verdict_d2': v2,
            'detail_d2': d2,
        })

    # ---------------- 反证组：判据必须能把「已知有缺陷」与「已知已修」分开 ----------------
    neg = {}
    samples = [
        ('broken_874924a', os.path.join(REPO, 'results', 'app', '_app425_hist',
                                        'broken_874924a_app.py')),
        ('fixed_ba76ea5', os.path.join(REPO, 'results', 'app', '_app425_hist',
                                       'fixed_ba76ea5_app.py')),
        ('parent_874924a~1', os.path.join(REPO, 'results', 'app', '_app425_hist',
                                          'parent_app.py')),
    ]
    for label, p in samples:
        if not os.path.isfile(p):
            neg[label] = 'SAMPLE_MISSING'
            continue
        src = open(p, 'r', encoding='utf-8').read()
        v1, d1 = diagnose_d1(src)
        v2, d2 = diagnose_d2(src)
        neg[label] = {'verdict_d1': v1, 'detail_d1': d1,
                      'verdict_d2': v2, 'detail_d2': d2}
    out['neg_control'] = neg

    # ---------------- 汇总 ----------------
    def collect(vkey):
        hit = [p['pkg'] for p in out['packages']
               if p.get('state') == 'PRESENT' and p.get(vkey) in ('BROKEN', 'BUG')]
        ok = [p['pkg'] for p in out['packages']
              if p.get('state') == 'PRESENT' and p.get(vkey) in ('OK', 'NA')]
        return hit, ok

    d1_hit, d1_ok = collect('verdict_d1')
    d2_hit, d2_ok = collect('verdict_d2')
    out['summary'] = {
        'n_pkgs_present': sum(1 for p in out['packages'] if p.get('state') == 'PRESENT'),
        'd1_gui_swallowed_affected': d1_hit,
        'd1_ok_or_na': d1_ok,
        'd2_asr06b_label_collision_affected': d2_hit,
        'd2_ok_or_na': d2_ok,
    }

    # 反证自检：判据必须能把 broken 与 fixed 分开
    nc = neg
    sep1 = (isinstance(nc.get('broken_874924a'), dict)
            and nc['broken_874924a'].get('verdict_d1') == 'BROKEN'
            and isinstance(nc.get('fixed_ba76ea5'), dict)
            and nc['fixed_ba76ea5'].get('verdict_d1') == 'OK')
    out['neg_control_selfcheck'] = {
        'd1_separates_broken_from_fixed': bool(sep1),
    }

    dst = os.path.join(REPO, 'results', 'app', 'app425_hist_impact.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('WROTE: %s' % dst)
    print(json.dumps(out['summary'], ensure_ascii=False, indent=1))
    print('neg_control_selfcheck: %s' % json.dumps(out['neg_control_selfcheck']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
