#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_app425_hist_scan2.py — 修正版历史影响扫描（v2）

🔴🔴 v1 的 D2 判据有两处**自身缺陷**，本版修掉：
   (1) 用 `ast.literal_eval` 读 ASR 引擎表 ⇒ **真表里的值是 `dict(...)` 调用**
       （`dict(label=..., kind='asr06b', device='GPU.0')`）⇒ literal_eval 抛异常
       ⇒ 表被读成空 ⇒ 「有没有 kind=='asr06b' 的条目」永远答 False
       ⇒ **假阴性**（把 rc5/rc6 这种真有缺陷的判成 NA）。
   (2) 判据依赖表名 `ENGINES_ASR06B` ⇒ rc5 把 `kind='asr06b'` 直接写在 `ENGINES` 里
       ⇒ rc5 假阴性。

   ⇒ v2 判据：**不依赖表名、不依赖 literal_eval**
      · 用 AST 走 `Assign` 的 value，找所有 `kind=` 关键字参数为 'asr06b' 的条目
        （兼容 `dict(...)` 调用与 `{...}` 字面量两种写法）；
      · 再看 `build_asr_options` 函数体里**比较到的 kind 集合**；
      · 若「表里有 asr06b 条目」但「比较集合里没有 asr06b」
        ⇒ asr06b 落入「遍历所有设备」分支 ⇒ **label 撞车 ⇒ 静默错档** = BUG。

   🔴 判据自证（MEMORY §四）：v2 必须能识破 **rc6（已知有缺陷）**、
      且**不误报 rc7（已知已修）**、且**不误报 rc5 之外的无关包**。
      ⇒ 附**反证组**：把 rc7 的 `build_asr_options` 里 asr06b 分支破坏掉
        （把 `if cfg['kind'] == 'asr06b':` 换成 `if False:`）⇒ 判据必须变成 BUG。

输出：results/app/app425_hist_scan2.json
"""

import ast
import json
import os
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


# ---------- 通用：找出模块级 ASR 引擎表里的 kind=='asr06b' 条目 ----------
def find_asr06b_entries(t):
    """返回 (是否找到, 命中条目列表)。兼容 dict(...) 调用与 {...} 字面量。"""
    hits = []
    for n in ast.walk(t):
        if isinstance(n, ast.Assign):
            tgt = n.targets[0]
            if not (isinstance(tgt, ast.Name) and
                    tgt.id in ('ENGINES', 'ENGINES_ASR06B')):
                continue
            val = n.value
            if isinstance(val, ast.Dict):
                keys = val.keys
                vals = val.values
                for k, v in zip(keys, vals):
                    kind = _kind_of(v)
                    if kind:
                        hits.append((tgt.id, _key_name(k), kind))
            elif isinstance(val, ast.Call) and getattr(val.func, 'id', None) == 'dict':
                for kw in val.keywords:
                    if kw.arg == 'kind' and isinstance(kw.value, ast.Constant) \
                            and isinstance(kw.value.value, str):
                        hits.append((tgt.id, '<call>', kw.value.value))
            # 形如 ENGINES = {...}; ENGINES.update(...) 的情形
        # dict(...) 直接赋值给别的名字
        if isinstance(n, ast.Call) and getattr(n.func, 'id', None) == 'dict':
            for kw in n.keywords:
                if kw.arg == 'kind' and isinstance(kw.value, ast.Constant) \
                        and kw.value.value == 'asr06b':
                    hits.append(('<expr>', '<call>', 'asr06b'))
    return hits


def _kind_of(v):
    """从 dict(...) 调用或 dict 字面量里取 kind 的字符串值。"""
    if isinstance(v, ast.Call) and getattr(v.func, 'id', None) == 'dict':
        for kw in v.keywords:
            if kw.arg == 'kind' and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                return kw.value.value
    if isinstance(v, ast.Dict):
        for k, vv in zip(v.keys, v.values):
            if isinstance(k, ast.Constant) and k.value == 'kind' \
                    and isinstance(vv, ast.Constant):
                return vv.value
    return None


def _key_name(k):
    if isinstance(k, ast.Constant) and isinstance(k.value, str):
        return k.value
    return '<expr>'


def kinds_compared_in(fn):
    """build_asr_options 里比较到的 kind 字符串集合。"""
    kinds = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Compare)
                and isinstance(n.left, ast.Subscript)
                and isinstance(n.left.slice, ast.Constant)
                and n.left.slice.value == 'kind'):
            for c in n.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    kinds.add(c.value)
    return kinds


def diagnose(src):
    res = {'d1': 'UNKNOWN', 'd1_detail': '', 'd2': 'UNKNOWN', 'd2_detail': '',
           'n_init_stmts': None, 'asr06b_entries': [], 'kinds_handled': None}
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        res['d1_detail'] = res['d2_detail'] = 'SyntaxError: %s' % e
        return res

    # ---- D1 ----
    app_cls = None
    for n in t.body:
        if isinstance(n, ast.ClassDef) and n.name == 'App':
            app_cls = n
            break
    if app_cls is None:
        res['d1_detail'] = 'no class App'
    else:
        init = next((m for m in app_cls.body
                     if isinstance(m, ast.FunctionDef) and m.name == '__init__'), None)
        if init is None:
            res['d1_detail'] = 'no App.__init__'
        else:
            res['n_init_stmts'] = len(init.body)
            nested = [f.name for f in ast.walk(init)
                      if isinstance(f, ast.FunctionDef)]
            res['clone_nested'] = '_clone_nearest' in nested
            has_layout = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ('pack', 'grid', 'migrate')
                for n in ast.walk(init))
            res['has_layout_call'] = has_layout
            if res['clone_nested']:
                res['d1'] = 'BROKEN'
                res['d1_detail'] = ('_clone_nearest nested in App.__init__ '
                                     '(n_init_stmts=%d)' % res['n_init_stmts'])
            elif res['n_init_stmts'] >= 100 and has_layout:
                res['d1'] = 'OK'
                res['d1_detail'] = ('__init__ n_stmts=%d + layout calls + '
                                    '_clone_nearest class-level'
                                    % res['n_init_stmts'])
            elif res['n_init_stmts'] < 60 and not has_layout:
                res['d1'] = 'BROKEN'
                res['d1_detail'] = ('__init__ collapsed to %d stmts, no layout'
                                    % res['n_init_stmts'])
            else:
                res['d1_detail'] = ('n_init_stmts=%d nested=%s layout=%s'
                                    % (res['n_init_stmts'], res['clone_nested'],
                                       has_layout))

    # ---- D2 ----
    hits = find_asr06b_entries(t)
    res['asr06b_entries'] = hits
    fn = next((n for n in ast.walk(t)
               if isinstance(n, ast.FunctionDef) and n.name == 'build_asr_options'),
              None)
    kinds = sorted(kinds_compared_in(fn)) if fn is not None else []
    res['kinds_handled'] = kinds
    if fn is None:
        res['d2'] = 'NA'
        res['d2_detail'] = 'no build_asr_options'
    elif not hits:
        res['d2'] = 'NA'
        res['d2_detail'] = 'no kind=="asr06b" entry in ASR engine table'
    elif 'asr06b' in kinds:
        res['d2'] = 'OK'
        res['d2_detail'] = ('build_asr_options compares kinds=%s (asr06b '
                            'recognized); entries=%s' % (kinds, hits))
    else:
        res['d2'] = 'BUG'
        res['d2_detail'] = ('ASR table HAS kind=="asr06b" (entries=%s) but '
                            'build_asr_options compares kinds=%s => asr06b falls '
                            'into "iterate all devices" => duplicate labels => '
                            'silent wrong engine' % (hits, kinds))
    return res


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


def main():
    out = {
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'criterion_note': (
            'v2：AST 直读 ASR 引擎表（兼容 dict(...) 调用）取 kind=="asr06b" 条目；'
            '再看 build_asr_options 实际比较到的 kind 集合。'
            '🔴 v1 用 ast.literal_eval 读表 ⇒ 真表值是 dict(...) 调用 ⇒ 抛异常 ⇒ '
            '表读成空 ⇒ 假阴性；且 v1 依赖表名 ENGINES_ASR06B ⇒ rc5 假阴性。'),
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
        d = diagnose(src)
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

    # ---- 反证组：把 rc7 的 asr06b 分支破坏掉 ⇒ 判据必须变 BUG ----
    rc7 = pkg_app_py(PKGS[-1])
    neg = {}
    if rc7:
        src7 = open(rc7, 'r', encoding='utf-8').read()
        neg['rc7_intact'] = diagnose(src7)
        # 反证构造：把 `if cfg['kind'] == 'asr06b':` 换成 `if False:`
        #            （🔴 不能删行 ⇒ 会掏空 if 块 ⇒ SyntaxError ⇒ 假 FAIL）
        broken = src7.replace("if cfg['kind'] == 'asr06b':", "if False:")
        if broken != src7:
            neg['rc7_anticontrol'] = diagnose(broken)
        else:
            neg['rc7_anticontrol'] = {'error': 'anchor not found (single hit expected)'}
    out['neg_control'] = neg

    # 反证自检
    a = neg.get('rc7_intact', {})
    b = neg.get('rc7_anticontrol', {})
    out['neg_control_selfcheck'] = {
        'rc7_intact_is_OK': a.get('d2') == 'OK',
        'anticontrol_is_BUG': b.get('d2') == 'BUG',
        'criterion_has_discriminating_power': (a.get('d2') == 'OK' and b.get('d2') == 'BUG'),
        'rc6_detected_as_BUG': any(p.get('pkg', '').endswith('rc6')
                                   and p.get('d2') == 'BUG'
                                   for p in out['packages']),
    }

    def collect(key, val):
        return [p['pkg'] for p in out['packages']
                if p.get('state') == 'PRESENT' and p.get(key) == val]

    out['summary'] = {
        'n_pkgs_present': sum(1 for p in out['packages'] if p.get('state') == 'PRESENT'),
        'd1_broken_packages': collect('d1', 'BROKEN'),
        'd2_bug_packages': collect('d2', 'BUG'),
        'd2_ok_packages': collect('d2', 'OK'),
        'd2_na_packages': collect('d2', 'NA'),
    }

    dst = os.path.join(REPO, 'results', 'app', 'app425_hist_scan2.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('WROTE: %s' % dst)
    print(json.dumps(out['summary'], ensure_ascii=False, indent=1))
    print('\nselfcheck: %s' % json.dumps(out['neg_control_selfcheck'], ensure_ascii=False))
    print('\n--- commit 判定 ---')
    for c in out['commits'][:10]:
        print('%s %s D1=%-8s D2=%-5s | %s' % (c.get('sha'), c.get('date'),
                                               c.get('d1'), c.get('d2'),
                                               (c.get('subject') or '')[:52]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
