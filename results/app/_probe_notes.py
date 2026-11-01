#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔍 一次性探针：打印客户包 MANIFEST notes 里**残留的开发机路径**片段。

🔴 §48 铁律：代码行里不得写死客户包路径 ⇒ 走 `pkg_paths.pkg_app_dir()`（单一数据源）。
🔴 探针的「搜索关键词」也**不写死开发机用户名** ⇒ 按当前家目录 basename 推导。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_repo_root(start):
    """向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

    ⇒ **不写死仓库根**（§118/§119 铁律）。
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


REPO = _find_repo_root(HERE)
sys.path.insert(0, REPO)
import pkg_paths          # noqa: E402  （单一数据源：自动发现最新版本包）

MANIFEST = os.path.join(pkg_paths.pkg_app_dir(), 'MANIFEST.json')
d = json.load(open(MANIFEST, encoding='utf-8'))
n = d['notes']
needle = os.path.basename(os.path.expanduser('~'))
i = 0
while True:
    i = n.find(needle, i)
    if i < 0:
        break
    print('--- 位置', i, '---')
    print(repr(n[max(0, i - 300):i + 200]))
    i += 1
