#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_bgsep_missing_test.py — **APP-137 §3 的「缺模型降级」离线前置检查**。

## reviewer APP-137 §3 原文
> **缺模型降级**：拿掉 `models\bgsep` 的一份**临时副本**测一次，
> popup 应显示 **unavailable 和原因**。

## 🔴 本脚本做的是**离线前置**（**不占机器、不改任何交付包**）

1. **找降级判据在哪**：EXT 桥接里 `models/bgsep` 缺失时**报什么**、
   `bg_status` 的 `state`/`reason` 字段**长什么样**；
2. **确认真包 v2.6 与 v1.2 候选目录里 `models/bgsep` 的完整文件清单**
   （降级测试要拿掉的**就是这一个目录**）；
3. **列一份「临时副本」的建法**（**必须零拷贝** ⇒ 目录联接）
   ⇒ 降级测试时**只把联接改名**，**真包一个字节都不动**；
4. 🔴 **明确**：**离线无法证明 popup 显示了什么** ⇒ popup 的 UI 文案
   **必须实机跑一次**才算数 ⇒ 本脚本**只报「前置条件齐备」**。

## 用法
```
python live_caption/_app137_bgsep_missing_test.py
```
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
RESULTS = os.path.join(REPO, 'results', 'app')
EVIDENCE = os.path.join(RESULTS, 'app137_bgsep_missing_precheck.json')

CAND = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.2.candidate')
V26 = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')


def list_dir(p):
    out = []
    for dp, dns, fns in os.walk(p):
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, p).replace(os.sep, '/')
            try:
                out.append({'file': rel, 'bytes': os.path.getsize(full)})
            except OSError:
                out.append({'file': rel, 'bytes': None})
    out.sort(key=lambda x: x['file'])
    return out


def find_bgsep_degrade_logic():
    """在**候选目录**的 ext/ 里找 bgsep 缺失的降级判据（**只读**）。"""
    hits = []
    ext = os.path.join(CAND, 'ext', 'bridge')
    if not os.path.isdir(ext):
        return hits
    pats = [r'bgsep', r'unavailable', r'not found', r'bg_status', r'reason']
    for fn in sorted(os.listdir(ext)):
        if not fn.endswith('.py'):
            continue
        p = os.path.join(ext, fn)
        try:
            with io.open(p, encoding='utf-8', errors='replace') as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for i, ln in enumerate(lines, 1):
            if ('bgsep' in ln) and any(re.search(pt, ln) for pt in pats[1:]):
                hits.append({'file': 'ext/bridge/%s' % fn, 'line': i,
                             'text': ln.strip()[:180]})
    return hits


def main():
    checks = []
    ev = {
        'script': '_app137_bgsep_missing_test.py',
        'task': 'APP-137 §3：缺模型降级测试的**离线前置检查**',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    # ① 两个包里的 bgsep 文件清单
    for label, root in (('v2.6', V26), ('candidate_v1.2', CAND)):
        d = os.path.join(root, 'models', 'bgsep')
        if os.path.isdir(d):
            fl = list_dir(d)
            ev.setdefault('bgsep_files', {})[label] = {
                'dir': d, 'n_files': len(fl),
                'bytes': sum(f['bytes'] or 0 for f in fl), 'files': fl}
            checks.append({'name': 'bgsep_present_%s' % label, 'ok': len(fl) > 0,
                           'detail': '%d 文件 / %d B' % (len(fl),
                                                         sum(f['bytes'] or 0 for f in fl))})
        else:
            checks.append({'name': 'bgsep_present_%s' % label, 'ok': False,
                           'detail': '缺 %s' % d})

    # ② 降级判据（EXT 侧）
    hits = find_bgsep_degrade_logic()
    ev['bgsep_degrade_logic'] = hits
    checks.append({'name': 'degrade_logic_found', 'ok': len(hits) > 0,
                   'detail': 'EXT 侧命中 %d 处 bgsep 降级判据' % len(hits)})

    # ③ 临时副本的建法（**必须零拷贝** ⇒ 目录联接）
    tmp_root = os.path.join(HOME, 'shared', 'shadow_pkgs')
    ev['missing_model_test_plan'] = {
        'why_junction': ('降级测试要「拿掉 models\\bgsep」⇒ 用**目录联接**把 '
                         '`models/bgsep` 指到一个**空目录** ⇒ **零拷贝**，'
                         '且**真包一个字节都不动**（联接只在候选目录里）'),
        'steps': [
            '① 在候选目录里把 `models/bgsep` **联接**指向一个空目录'
            '（而不是删真目录）',
            '② 起桥接 ⇒ 观察 `bg_status` 的 `state`/`reason` 与 popup 文案',
            '③ 断言 popup 显示 **unavailable** ＋ **原因**',
            '④ 恢复联接（改回指向真 bgsep）⇒ 候选目录复原',
        ],
        'tmp_root': tmp_root,
    }
    checks.append({'name': 'missing_model_test_plan_ready', 'ok': True,
                   'detail': '用目录联接指向空目录 ⇒ 零拷贝、真包不动'})

    # ④ 🔴 **离线不能证明 popup 文案** ⇒ 如实登记
    ev['limitation'] = ('🔴 **离线无法证明 popup 显示了什么** —— popup 的 UI 文案'
                        '**必须实机跑一次**才算数 ⇒ 本脚本只报「前置条件齐备」，'
                        '**不把「降级可用」当成已验证**。')
    checks.append({'name': 'limitation_declared', 'ok': True,
                   'detail': '已如实登记「popup 文案须实机验证」'})

    ok = all(c['ok'] for c in checks)
    print('=== APP-137 §3 缺模型降级：离线前置检查 ===')
    for c in checks:
        print('  %-40s %s  %s' % (c['name'], 'PASS' if c['ok'] else 'FAIL',
                                  c['detail']))
    print('--- bgsep 降级判据（EXT 侧命中 %d 处，前 8 条）---' % len(hits))
    for h in hits[:8]:
        print('  %s:%s  %s' % (h['file'], h['line'], h['text'][:110]))
    print('🔴 %s' % ev['limitation'])

    os.makedirs(RESULTS, exist_ok=True)
    tmp = EVIDENCE + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, EVIDENCE)
    print('证据：%s' % EVIDENCE)
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
