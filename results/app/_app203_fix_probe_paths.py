#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app203_fix_probe_paths.py —— 修掉 `_probe_*` 脚本里**写死的客户包 / 仓库路径**。

🔴 打包闸门 `app049_pkg_path_hardcode_gate.py` 扫 `results/app` + `live_caption`，
   **代码行**里出现 `Confucius4_LiveCaption_v\\d+` ⇒ **命中即 FAIL ⇒ 拒绝打包**（§48）。

🔴 修法（**通用**，不逐条手抄路径）：
  ① 正则匹配「任意盘符 + \\Users\\<用户名>\\...」形式的**字符串字面量**；
  ② 分类替换：
     - 指向**仓库根**        → `REPO`（向上查找，不写死）
     - 指向**仓库的 results/app** → `os.path.join(REPO, 'results', 'app')`
     - 指向**客户包根**      → `pkg_paths.discover_pkg_dir()`
     - 指向**客户包 app/**   → `pkg_paths.pkg_app_dir()`
  ③ 补齐 `sys` / `pkg_paths` import ＋ `_find_repo_root()` 辅助函数；
  ④ 改完**必须 `ast.parse` 复验**（不能只看 grep 命中数）。
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

HELPER = '''

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
'''

#: 任意盘符 + \Users\<用户名>\... 的字符串字面量
RE_ABS = re.compile(
    r"r?(['\"])[A-Za-z]:[\\/]Users[\\/][^'\"\\/]+[\\/]"
    r"(confucius4-openvino(?:[\\/]results[\\/]app)?"
    r"|Confucius4_LiveCaption_v\d+(?:\.\d+)*"
    r"(?:[\\/]app)?)\1")


def classify(target: str) -> str:
    t = target.replace('\\', '/').lower()
    if t.endswith('results/app'):
        return 'RESULTS_APP'
    if 'confucius4-openvino' in t:
        return 'REPO'
    if t.endswith('/app'):
        return 'PKG_APP'
    return 'PKG'


def fix(path: str) -> bool:
    full = os.path.join(REPO, path)
    s = io.open(full, 'r', encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    n = s.replace('\r\n', '\n')

    repl = {
        'REPO': 'REPO',
        'RESULTS_APP': "os.path.join(REPO, 'results', 'app')",
        'PKG': 'pkg_paths.discover_pkg_dir()',
        'PKG_APP': 'pkg_paths.pkg_app_dir()',
    }
    hits = []

    def _sub(m):
        kind = classify(m.group(2))
        hits.append((m.group(0), kind))
        return repl[kind]

    n2 = RE_ABS.sub(_sub, n)
    if not hits:
        print('  [skip] %s：无绝对路径字面量' % path)
        return True

    # ── 补齐辅助设施 ──
    if '_find_repo_root' not in n2:
        # 在首个 import 块之后插入辅助函数
        m = re.search(r'^(?:import|from)[^\n]*\n', n2, re.M)
        if m:
            n2 = n2[:m.end()] + HELPER + n2[m.end():]
    if 'import pkg_paths' not in n2:
        m = re.search(r'^(?:import|from)[^\n]*\n', n2, re.M)
        if m:
            n2 = (n2[:m.end()]
                  + 'import pkg_paths          # noqa: E402  （单一数据源）\n'
                  + n2[m.end():])
    if not re.search(r'^import sys$', n2, re.M):
        n2 = re.sub(r'^import os$', 'import os\nimport sys', n2, count=1,
                    flags=re.M)
        if not re.search(r'^import sys$', n2, re.M):
            n2 = 'import sys\n' + n2
    if not re.search(r'^REPO = ', n2, re.M):
        n2 = ('HERE = os.path.dirname(os.path.abspath(__file__))\n'
              'REPO = _find_repo_root(HERE)\n'
              'sys.path.insert(0, REPO)\n' + n2)
    # 去掉重复的 HERE 定义（若刚插入）
    lines = n2.split('\n')
    seen_here = False
    out = []
    for ln in lines:
        if ln.startswith('HERE = os.path.dirname('):
            if seen_here:
                continue
            seen_here = True
        out.append(ln)
    n2 = '\n'.join(out)

    # ── 写盘前**语法复验**（不能只看 grep 命中数）──
    try:
        ast.parse(n2)
    except SyntaxError as e:
        print('  [FAIL] %s：改后语法错误 ⇒ **不写盘**（%s）' % (path, e))
        return False

    io.open(full, 'w', encoding='utf-8', newline='').write(
        n2.replace('\n', nl) if nl == '\r\n' else n2)
    for old, kind in hits:
        print('  [fixed] %-40s %-12s ⇒ %s'
              % (os.path.basename(path), kind, old[:60]))
    return True


def main():
    targets = [
        'results/app/_probe_app191_base.py',
        'results/app/_probe_fix_lnk.py',
        'results/app/_probe_inject.py',
        'results/app/_probe_notes.py',
        'results/app/_probe_rollback.py',
    ]
    ok = True
    for t in targets:
        if not os.path.isfile(os.path.join(REPO, t)):
            print('  [skip] %s：不存在' % t)
            continue
        ok &= fix(t)
    print('done =', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
