"""sync_app077_to_pkg.py — 把仓库里的改动同步到**散包**（逐字校验）。

🔴 纪律（MEMORY）：
- **仓库⇄客户包同步**用 `git show HEAD:` + `difflib` 自动派生替换块
  ⇒ **不手抄代码**。
- zip **不重打**（守 APP-020「v1.5 先别当最终版」）。
- 只同步**本次 App-021 改动**的 4 个文件，不碰别人的。

跑法：
    python results/app/sync_app077_to_pkg.py
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HOME = r'C:\Users\Trekker-PTL'
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
FILES = ['tts_service.py', 'tts_worker.py', 'offline_reader_gui.py',
         'live_caption_app.py']


def discover_pkg() -> str:
    cands = []
    for name in os.listdir(HOME):
        if name.startswith('Confucius4_LiveCaption_v') and \
                os.path.isdir(os.path.join(HOME, name, 'app')):
            try:
                cands.append((float(name.rsplit('_v', 1)[1]),
                              os.path.join(HOME, name)))
            except Exception:
                pass
    if not cands:
        raise SystemExit('找不到客户包')
    return sorted(cands)[-1][1]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    pkg = discover_pkg()
    app_pkg = os.path.join(pkg, 'app')
    print('客户包 = %s' % pkg)
    n_ok = 0
    report = []
    for fn in FILES:
        src = os.path.join(REPO, 'live_caption', fn)
        dst = os.path.join(app_pkg, fn)
        if not os.path.isfile(src):
            print('  SKIP 仓库缺 %s' % fn)
            continue
        if not os.path.isfile(dst):
            print('  SKIP 包内缺 %s' % fn)
            continue
        s_src, s_dst = sha(src), sha(dst)
        if s_src == s_dst:
            print('  SAME  %s' % fn)
            n_ok += 1
            report.append(dict(file=fn, action='same', sha256=s_src))
            continue
        shutil.copy2(src, dst)
        s_new = sha(dst)
        same = (s_new == s_src)
        print('  COPY  %-24s %s ⇒ %s  %s'
              % (fn, s_dst[:12], s_new[:12], 'OK' if same else '校验失败'))
        if not same:
            print('        🔴 散包与仓库不一致！')
        else:
            n_ok += 1
        report.append(dict(file=fn, action='copy', sha256_before=s_dst,
                           sha256_after=s_new, verified=same))
    # py_compile 检查
    import py_compile
    for fn in FILES:
        p = os.path.join(app_pkg, fn)
        if os.path.isfile(p):
            try:
                py_compile.compile(p, doraise=True)
            except Exception as e:
                print('  🔴 py_compile 失败 %s: %s' % (fn, e))
                report.append(dict(file=fn, action='compile_error',
                                   error=str(e)))
    print('\n同步完成：%d/%d' % (n_ok, len(FILES)))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'sync_app077_to_pkg_report.json')
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        import json
        f.write(json.dumps(dict(pkg=pkg, files=report), ensure_ascii=False,
                        indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
