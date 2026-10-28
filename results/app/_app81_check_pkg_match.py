# -*- coding: utf-8 -*-
"""app81 helper — 仓库 ⇄ 客户包 app/ 归一化 SHA256 比对（只读）。

🔴 §86 修正：**客户包版本号不得写死** —— 本脚本原来写死
`Confucius4_LiveCaption_v1.6\\app` ⇒ 正是 §48「包路径写死」闸门要拦的缺陷类别
⇒ 包一升版就**指向旧包** ⇒ 比对结果失真（与 §48 记录的真实事故同类）。
⇒ 改为走**单一数据源** `pkg_paths.pkg_app_dir()`（自动发现最大版本包）。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pkg_paths  # noqa: E402  §48 单一数据源

REPO = os.path.join(REPO_ROOT, 'live_caption')
PKG = pkg_paths.pkg_app_dir()
FILES = ['live_caption_app.py', 'tts_service.py', 'tts_worker.py',
         'tts_cuda.py', 'tts_engine.py', 'translator.py', 'device_config.py',
         'tts_cuda_sidecar.py', 'offline_reader.py', 'offline_reader_gui.py']


def lf_sha(p):
    b = open(p, 'rb').read()
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()


def main():
    ok = 0
    for f in FILES:
        a = os.path.join(REPO, f)
        b = os.path.join(PKG, f)
        if not (os.path.exists(a) and os.path.exists(b)):
            print('%-24s SKIP (missing)' % f)
            continue
        ha, hb = lf_sha(a), lf_sha(b)
        same = ha == hb
        ok += 1 if same else 0
        print('%-24s %-6s repo=%s pkg=%s' % (f, 'MATCH' if same else 'DIFF',
                                              ha[:16], hb[:16]))
    print('MATCH %d / %d' % (ok, len(FILES)))


if __name__ == '__main__':
    main()
