#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_app425_hist_scan.py — 逐 commit 扫描 live_caption_app.py 的两个缺陷（D1/D2），
用来把「历史影响」从猜测变成事实。

🔴 本脚本先修掉上一版 `_app425_hist_impact.py` 的 **D2 判据缺陷**：
   上一版判据是「`build_asr_options` 里比较到的 kind 集合是否含 'asr06b'」
   ⇒ 但 **rc5 的结构完全不同**：rc5 把 `kind='asr06b'` 直接写在 **ENGINES 表**里
   （没有独立的 `ENGINES_ASR06B` 表）⇒ 上一版判据在 rc5 上返回 'NA'
   ⇒ **假阴性**（把「有缺陷」判成「不适用」）。
   ⇒ 正确判据必须**不依赖具体表名**，而是问：
      「ASR 引擎表里是否存在 kind=='asr06b' 的条目？
        且 build_asr_options 是否能把它和 npu 档**区分开**？」
   ⇒ 若表里有 asr06b 条目，但 build_asr_options 只处理 npu/cuda
      ⇒ asr06b 落入「遍历所有设备」分支 ⇒ 两个档 label 相同 ⇒ 静默错档 = BUG。

输出：results/app/app425_hist_scan.json
"""

import ast
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REL = 'live_caption/live_caption_app.py'


def git(*args):
    return subprocess.run(['git'] + list(args), cwd=REPO, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def diagnose(src):
    """返回 dict：d1/d2 判定。"""
    res = {'d1': 'UNKNOWN', 'd1_detail': '', 'd2': 'UNKNOWN', 'd2_detail': '',
           'n_init_stmts': None, 'asr06b_in_table': None,
           'kinds_handled': None, 'n_asr_entries': None}
    try:
        t = ast.parse(src)
    except SyntaxError as e:
        res['d1_detail'] = res['d2_detail'] = 'SyntaxError: %s' % e
        return res

    # ---- D1: GUI 布局被吞 ----
    app_cls = None
    for n in t.body:
        if isinstance(n, ast.ClassDef) and n.name == 'App':
            app_cls = n
            break
    if app_cls is None:
        res['d1_detail'] = 'no class App'
    else:
        init = None
        for m in app_cls.body:
            if isinstance(m, ast.FunctionDef) and m.name == '__init__':
                init = m
                break
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
                res['d1_detail'] = ('_clone_nearest nested inside App.__init__ '
                                     '(n_init_stmts=%d)' % res['n_init_stmts'])
            elif res['n_init_stmts'] >= 100 and has_layout:
                res['d1'] = 'OK'
                res['d1_detail'] = ('__init__ n_stmts=%d + layout calls + '
                                    '_clone_nearest at class level'
                                    % res['n_init_stmts'])
            elif res['n_init_stmts'] < 60 and not has_layout:
                res['d1'] = 'BROKEN'
                res['d1_detail'] = ('__init__ collapsed to %d stmts, no layout '
                                    'calls' % res['n_init_stmts'])
            else:
                res['d1_detail'] = ('n_init_stmts=%d nested=%s layout=%s'
                                    % (res['n_init_stmts'], res['clone_nested'],
                                       has_layout))

    # ---- D2: asr06b 档位静默错档（**不依赖表名**）----
    # (a) ASR 引擎表里有没有 kind=='asr06b' 的条目？
    asr_entries = {}
    for n in t.body:
        if isinstance(n, ast.Assign):
            tgt = n.targets[0]
            if isinstance(tgt, ast.Name) and tgt.id in ('ENGINES', 'ENGINES_ASR06B'):
                try:
                    val = ast.literal_eval(n.value)
                except Exception:
                    val = None
                if isinstance(val, dict):
                    asr_entries[tgt.id] = val
    has06b = False
    n_asr = 0
    for name, val in asr_entries.items():
        for k, cfg in val.items():
            if isinstance(cfg, dict):
                n_asr += 1
                if cfg.get('kind') == 'asr06b':
                    has06b = True
    res['asr06b_in_table'] = has06b
    res['n_asr_entries'] = n_asr
    res['engine_tables'] = sorted(asr_entries.keys())

    # (b) build_asr_options 实际比较到的 kind 集合
    kinds = set()
    fn = None
    for n in ast.walk(t):
        if isinstance(n, ast.FunctionDef) and n.name == 'build_asr_options':
            fn = n
            break
    if fn is not None:
        for n in ast.walk(fn):
            if (isinstance(n, ast.Compare)
                    and isinstance(n.left, ast.Subscript)
                    and isinstance(n.left.slice, ast.Constant)
                    and n.left.slice.value == 'kind'):
                for c in n.comparators:
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        kinds.add(c.value)
    res['kinds_handled'] = sorted(kinds)

    if not has06b:
        res['d2'] = 'NA'
        res['d2_detail'] = ('no kind=="asr06b" entry in ASR engine table '
                            '(tables=%s, n_entries=%d)'
                            % (res['engine_tables'], n_asr))
    elif 'asr06b' in kinds:
        res['d2'] = 'OK'
        res['d2_detail'] = ('build_asr_options handles kinds=%s (asr06b '
                            'recognized)' % res['kinds_handled'])
    else:
        res['d2'] = 'BUG'
        res['d2_detail'] = ('ASR table HAS kind=="asr06b" but build_asr_options '
                            'handles kinds=%s ⇒ asr06b falls into "iterate all '
                            'devices" ⇒ duplicate labels ⇒ silent wrong engine'
                            % res['kinds_handled'])
    return res


def main():
    log = git('log', '--format=%H|%h|%ad|%s', '--date=format:%Y-%m-%d %H:%M:%S',
              '--', REL)
    commits = []
    for line in log.stdout.splitlines():
        if not line.strip():
            continue
        full, short, date, subj = line.split('|', 3)
        commits.append((full, short, date, subj))
    # 从新到旧
    out = {
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'file': REL,
        'n_commits': len(commits),
        'criterion_d2_note': (
            '🔴 上一版判据依赖表名 `ENGINES_ASR06B` ⇒ 在 rc5 上假阴性 '
            '(rc5 把 kind=asr06b 直接写在 ENGINES 表里) '
            '⇒ 本版改为「表里有没有 kind==asr06b 的条目」+ '
            '「build_asr_options 是否比较到它」⇒ 不依赖表名'),
        'commits': [],
    }

    for full, short, date, subj in commits:
        r = git('show', '%s:%s' % (full, REL))
        if r.returncode != 0:
            out['commits'].append({'sha': short, 'date': date, 'subject': subj,
                                    'error': 'git show failed'})
            continue
        d = diagnose(r.stdout)
        d.update({'sha': short, 'date': date, 'subject': subj})
        out['commits'].append(d)

    # 区间统计：874924a（含）之后、ba76ea5（不含）之前 = 缺陷窗口
    def idx(sha):
        for i, c in enumerate(out['commits']):
            if c.get('sha', '').startswith(sha):
                return i
        return None
    i_broken = idx('874924a')
    i_fixed = idx('ba76ea5')

    window = []
    if i_broken is not None and i_fixed is not None:
        window = out['commits'][i_fixed:i_broken]  # 固定的父..坏的那个（含坏，不含好）

    out['defect_window'] = {
        'introduced_at': '874924a',
        'fixed_at': 'ba76ea5',
        'n_commits_in_window': len(window),
        'commits': [{'sha': c.get('sha'), 'date': c.get('date'),
                     'd1': c.get('d1'), 'd2': c.get('d2'),
                     'subject': (c.get('subject') or '')[:70]} for c in window],
        'd1_broken_commits': [c.get('sha') for c in window if c.get('d1') == 'BROKEN'],
        'd2_bug_commits': [c.get('sha') for c in window if c.get('d2') == 'BUG'],
    }

    # 全历史：D1 BROKEN / D2 BUG 的 commit 列表
    out['all_d1_broken'] = [c.get('sha') for c in out['commits'] if c.get('d1') == 'BROKEN']
    out['all_d2_bug'] = [c.get('sha') for c in out['commits'] if c.get('d2') == 'BUG']

    dst = os.path.join(REPO, 'results', 'app', 'app425_hist_scan.json')
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('WROTE: %s' % dst)
    print(json.dumps(out['defect_window'], ensure_ascii=False, indent=1))
    print('\nall_d1_broken=%s' % out['all_d1_broken'])
    print('all_d2_bug=%s' % out['all_d2_bug'])
    print('\n--- 最近 12 个 commit 的判定 ---')
    for c in out['commits'][:12]:
        print('%s %s D1=%-8s D2=%-6s | %s' % (c.get('sha'), c.get('date'),
                                               c.get('d1'), c.get('d2'),
                                               (c.get('subject') or '')[:58]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
