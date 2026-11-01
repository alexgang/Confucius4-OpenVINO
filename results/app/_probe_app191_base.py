#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔍 一次性探针：打印 app191 对 4 个 other 模块的**基线 blob** 关键片段与 tails。

只读，不改任何被测文件。
"""
import os
import pkg_paths          # noqa: E402  （单一数据源）


def _find_repo_root(start):
    """向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

    ⇒ **不写死仓库根**（§118/§119 铁律：写死 ⇒ fresh clone 里是假象）。
    """
    cur = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(cur, 'live_caption'))
                and os.path.isfile(os.path.join(cur, 'pkg_paths.py'))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError('向上查找仓库根失败：%s' % start)
        cur = parent
import sys
import ast

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)

import app191_acceptance_code_binding_gate as A  # noqa: E402

PKG = pkg_paths.discover_pkg_dir()
pkg_app = os.path.join(PKG, 'app')

mods = ['live_caption_app.py', 'speaker_assets.py', 'tts_cuda.py',
        'tts_cuda_sidecar.py']

for name in mods:
    rel = 'live_caption/' + name
    cur_path = os.path.join(pkg_app, name)
    with open(cur_path, 'rb') as f:
        cur = A.norm_bytes(f.read())

    revs = A.git_commits_touching(rel)
    print('=' * 72)
    print('%s' % name)
    print('  touching commits (前 5): %s' % [r[:8] for r in revs[:5]])
    base_rev = None
    for rev in revs:
        b = A.git_blob(rev, rel)
        if b is not None and A.norm_bytes(b) == cur:
            base_rev = A.git_commit_parent(rev)
            print('  内容寻址命中 rev=%s ⇒ base=%s'
                  % (rev[:8], (base_rev or '')[:8]))
            break
    if not base_rev:
        base_rev = revs[0]
        print('  ⚠️ 内容寻址未命中 ⇒ fallback_latest_commit base=%s'
              % base_rev[:8])

    blob = A.norm_bytes(A.git_blob(base_rev, rel) or b'')
    bsrc = blob.decode('utf-8', 'replace')
    csrc = cur.decode('utf-8', 'replace')

    b_tree = ast.parse(bsrc)
    c_tree = ast.parse(csrc)
    tails = A._collect_tails(b_tree) | A._collect_tails(c_tree)
    print('  tails(%d) = %s' % (len(tails), sorted(tails)[:12]))

    # 基线里含家目录字面量的行
    hits = []
    for i, ln in enumerate(bsrc.splitlines(), 1):
        if 'Trekker-PTL' in ln or '<HOME>' in ln:
            hits.append('B%-4d %s' % (i, ln.strip()[:110]))
    for i, ln in enumerate(csrc.splitlines(), 1):
        if 'Trekker-PTL' in ln or '<HOME>' in ln:
            hits.append('C%-4d %s' % (i, ln.strip()[:110]))
    print('  家目录相关行（共 %d 行，前 14 条）：' % len(hits))
    for h in hits[:14]:
        print('    %s' % h)

    cls, det = A.classify_drift(bsrc, csrc)
    print('  cls = %s' % cls)
    if cls == 'other':
        print('  reason = %s' % det.get('reason'))
        print('  first_diff_at = %s' % det.get('first_diff_at'))
        bad = det.get('bad_derived')
        if bad:
            print('  bad_derived = %s' % bad)
