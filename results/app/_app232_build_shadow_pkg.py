#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""构建**影子包**（§123 做法）用于本轮设备级实测。

🔴 **为什么需要影子包**：
   `app223_app061_device_acceptance.py` 的 `--pkg` 要求**客户包形态**
   （`<pkg>/python/python.exe` + `<pkg>/app/live_caption_app.py`）。
   ⇒ **不能**直接指向开发树 `live_caption/`。
   ⇒ 做法：**硬链接**复制真包（零拷贝）＋ 把**本轮 dev 树**的改动文件覆盖进去
   ⇒ 既是客户包形态，又含本轮代码。

🔴 **纪律**：
   - **不覆盖、不删除任何既有客户包目录/zip**（v2.1 / v2.2 一个字节都不动）。
   - 影子包放在 `shared/` 下（跨模块可见区），**不进 git**。
   - 同步文件**逐个**列出（不做整目录覆盖）⇒ 避免把 dev 树的杂物带进包。

用法：python results/app/_app232_build_shadow_pkg.py [--src v2.2] [--dst shared/app065_shadow]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..'))
HOME = os.path.expanduser('~')
DEV = os.path.join(REPO, 'live_caption')

# 🔴 **本轮改动的 App 侧文件**（逐个列出 ⇒ 不做整目录覆盖）
SYNC_FILES = [
    'live_caption_app.py',      # APP-065 A 界面重排 + APP-063 ① ②
    'speaker_tracker.py',       # APP-063 ② (d)：ensure_started
]


def link_tree(src, dst):
    """**硬链接**复制目录树（零拷贝）；已存在则跳过。"""
    n = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt_root = dst if rel == '.' else os.path.join(dst, rel)
        os.makedirs(tgt_root, exist_ok=True)
        for fn in files:
            s = os.path.join(root, fn)
            t = os.path.join(tgt_root, fn)
            if os.path.exists(t):
                continue
            try:
                os.link(s, t)
            except (OSError, AttributeError):
                shutil.copy2(s, t)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(HOME,
                                                  'Confucius4_LiveCaption_v2.2'))
    ap.add_argument('--dst', default=os.path.join(HOME, 'shared',
                                                  'app065_shadow'))
    args = ap.parse_args()

    src, dst = args.src, args.dst
    if not os.path.isdir(src):
        print('[ABORT] 源包不存在：%s' % src)
        return 2
    if os.path.exists(dst):
        print('[ABORT] 影子包已存在：%s（**不覆盖** ⇒ 请手工处理后重跑）' % dst)
        return 2

    print('源包  : %s' % src)
    print('影子包: %s' % dst)
    os.makedirs(dst, exist_ok=True)
    n = link_tree(src, dst)
    print('硬链接 %d 个文件' % n)

    # ── 同步本轮改动的 App 侧文件 ──
    for fn in SYNC_FILES:
        s = os.path.join(DEV, fn)
        t = os.path.join(dst, 'app', fn)
        if not os.path.isfile(s):
            print('  [skip] dev 侧没有 %s' % fn)
            continue
        if os.path.exists(t):
            try:
                os.remove(t)          # 🔴 只删**影子包里**的硬链接
            except OSError as e:
                print('  [warn] 删除旧硬链接失败：%r' % e)
        shutil.copy2(s, t)
        print('  [sync] app/%s  (%d B)' % (fn, os.path.getsize(t)))

    # ── 自检：影子包的 app/ 必须含本轮代码的**特征串** ──
    probe = os.path.join(dst, 'app', 'live_caption_app.py')
    txt = open(probe, 'rb').read().decode('utf-8')
    marks = {
        'APP-065 A 五组': "text='① 音频输入'",
        'D4 重读 opt': 'if _forced:',
        'D2 取消勾选': 'def _on_speaker_toggled',
        'B 改名': '区分说话人（用于克隆）',
    }
    ok = True
    for k, v in marks.items():
        hit = v in txt
        ok = ok and hit
        print('  [check] %-14s %s' % (k, 'OK' if hit else '**缺失**'))
    print('影子包自检：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
