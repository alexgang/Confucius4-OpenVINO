HERE = os.path.dirname(os.path.abspath(__file__))
REPO = _find_repo_root(HERE)
sys.path.insert(0, REPO)
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""🔍 一次性探针：为什么注入 gui_status.py 的缺陷没被 app191 检出？

**背景**：`app191_discrimination_test.py` 的 D2 明确测过
「改真实模块里的一个字符串常量 ⇒ 必须判 other」⇒ 当时是 PASS 的。
⇒ 但本轮 `_probe_rollback.py` 注入 `gui_status.py` 的 `SEP` 后，⑥ 却 PASS。

**假设**：
  ① `gui_status.py` 不在 app191 的**生产模块**集合里（被 pkg_exclude 排除）
     ⇒ ⇒ app191 **根本不看**它 ⇒ 注入的缺陷**不可见**
  ② 或：该模块在**内容寻址**基线下被判 `identical`（因为基线就是改后的）

先查生产模块集合里有没有 gui_status.py。
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

sys.path.insert(0, os.path.join(REPO, 'results', 'app'))
sys.path.insert(0, REPO)
import app191_acceptance_code_binding_gate as A

pkg_app = pkg_paths.pkg_app_dir()
mods = A.pkg_production_modules(pkg_app)
print('生产模块数 = %d' % len(mods))
print('gui_status.py 在生产模块里？ %s' % ('gui_status.py' in mods))
print()
print('全部生产模块：')
for m in mods:
    print('   %s' % m)

import pkg_exclude
print()
print('pkg_exclude 对 gui_status.py 的判定：')
for fn in ('is_app_dev_only', 'is_excluded'):
    f = getattr(pkg_exclude, fn, None)
    if f is None:
        continue
    for arg in ('app/gui_status.py', 'gui_status.py'):
        try:
            print('   %s(%r) = %r' % (fn, arg, f(arg)))
        except Exception as e:
            print('   %s(%r) 异常 %r' % (fn, arg, e))
