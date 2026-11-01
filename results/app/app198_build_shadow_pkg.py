#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app198_build_shadow_pkg.py —— 建「影子客户包」用于 APP-054/053 的 A/B 实测。

## 为什么需要影子包（APP-054 ⑤）

reviewer 明文：「修复验证完之前，不要再在用户正在测试的安装目录里原地改文件。
本次发现包内 app/*.py 在 08:24 和 08:35 被原地修改，而用户恰好在 08:41 开始测试。
以后先在开发目录改好，验收通过后再一次性同步进包。」

⇒ **验证必须发生在「仓库代码 + 包内资产」的组合上**，而不是改包内文件。

## 影子包结构（与真包同构 ⇒ 代码里的相对路径推导全部成立）

```
<shadow>/
  app/         ← 真包 app/*.py 的**硬链接**（零拷贝）
                  + **仓库版**（真副本）的 3 个改动文件：
                    speaker_tracker.py / live_caption_app.py / speaker_assets.py
  models/      ← 真包 models/ 的**硬链接树**（零拷贝，10 GB 不占额外空间）
```

🔴 **硬链接（os.link）而非复制** ⇒ 影子包几乎不占磁盘；
🔴 **只读**：脚本**不改真包**任何字节（只 `os.link` + 在影子目录内写文件）。

## 用法

    python results/app/app198_build_shadow_pkg.py [--shadow <dir>] [--check]

⚠️ 必须在**能 import numpy 的解释器**下跑（本脚本只用 stdlib，无所谓），
   但**跑 A/B 用包内 python**（`Confucius4_LiveCaption_v1.13/python/python.exe`）。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

# 🔴 这三个文件是本轮 APP-053/054 的改动 ⇒ 影子包里必须用**仓库版**
REPO_OVERRIDES = (
    'speaker_tracker.py',
    'live_caption_app.py',
    'speaker_assets.py',
)


def find_repo_root(start: str) -> str:
    """🔴 向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

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


def find_pkg_dir(repo: str) -> str:
    """自动发现**最新版本**客户包目录（**不写死版本号**）。"""
    sys.path.insert(0, repo)
    try:
        import pkg_paths
    finally:
        sys.path.pop(0)
    return pkg_paths.discover_pkg_dir()


def link_tree(src: str, dst: str) -> tuple:
    """用**硬链接**把目录树镜像到 dst（零拷贝）。

    ⇒ 文件夹用 `os.makedirs`（真实目录）⇒ 只有**文件**是硬链接。
    ⇒ 跨卷（不同盘）时 `os.link` 失败 ⇒ 退回 `shutil.copy2`（极少发生）。
    """
    n_link = 0
    n_copy = 0
    n_dir = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        tgt = dst if rel == '.' else os.path.join(dst, rel)
        if not os.path.isdir(tgt):
            os.makedirs(tgt, exist_ok=True)
            n_dir += 1
        for fn in files:
            s = os.path.join(root, fn)
            d = os.path.join(tgt, fn)
            if os.path.exists(d):
                continue
            try:
                os.link(s, d)
                n_link += 1
            except OSError:
                shutil.copy2(s, d)
                n_copy += 1
    return n_link, n_copy, n_dir


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shadow', default=None,
                    help='影子包目录（默认 <HOME>\\shared\\app053054_shadow）')
    ap.add_argument('--check', action='store_true',
                    help='只检查，不构建')
    args = ap.parse_args()

    repo = find_repo_root(os.path.dirname(os.path.abspath(__file__)))
    pkg = find_pkg_dir(repo)
    shadow = args.shadow or os.path.join(
        os.path.expanduser('~'), 'shared', 'app053054_shadow')

    print('repo   =', repo)
    print('pkg    =', pkg)
    print('shadow =', shadow)

    if args.check:
        for rel in ('app/speaker_tracker.py', 'app/live_caption_app.py',
                    'app/speaker_assets.py', 'app/asr_spk',
                    'models/spk', 'models/encoder-int8'):
            p = os.path.join(shadow, rel.replace('/', os.sep))
            print('  %-34s %s' % (rel, 'OK' if os.path.exists(p) else 'MISSING'))
        return 0

    # ── ① app/ ──
    app_src = os.path.join(pkg, 'app')
    app_dst = os.path.join(shadow, 'app')
    if os.path.isdir(app_dst):
        shutil.rmtree(app_dst)
    l, c, d = link_tree(app_src, app_dst)
    print('app/  硬链接 %d 个 / 复制 %d 个 / 目录 %d 个' % (l, c, d))

    # ── ② models/ ──
    mod_src = os.path.join(pkg, 'models')
    mod_dst = os.path.join(shadow, 'models')
    if not os.path.isdir(mod_dst):
        l, c, d = link_tree(mod_src, mod_dst)
        print('models/ 硬链接 %d 个 / 复制 %d 个 / 目录 %d 个' % (l, c, d))
    else:
        print('models/ 已存在（跳过）')

    # ── ③ 覆盖 3 个改动文件为**仓库版**（真副本）──
    for fn in REPO_OVERRIDES:
        src = os.path.join(repo, 'live_caption', fn)
        dst = os.path.join(app_dst, fn)
        if not os.path.isfile(src):
            print('  !! 仓库缺 %s' % fn)
            continue
        if os.path.exists(dst):
            os.remove(dst)          # 先删硬链接（**不影响真包**）
        shutil.copy2(src, dst)
        print('  覆盖为仓库版：%s（%d B）' % (fn, os.path.getsize(dst)))

    # ── ④ 自检 ──
    print('--- 自检 ---')
    ok = True
    for fn in REPO_OVERRIDES:
        src = os.path.join(repo, 'live_caption', fn)
        dst = os.path.join(app_dst, fn)
        same = (os.path.getsize(src) == os.path.getsize(dst))
        print('  %-24s repo=%d shadow=%d %s'
              % (fn, os.path.getsize(src), os.path.getsize(dst),
                 'OK' if same else 'MISMATCH'))
        ok &= same
    for rel in ('app/asr_spk/asr052_speaker_tracker_api.py',
                'models/spk/pyannote_seg_3_0/fp16/pyannote_seg_3_0.xml',
                'models/spk/wespeaker-resnet34-fp16/openvino_encoder_model.xml',
                'models/encoder-int8'):
        p = os.path.join(shadow, rel.replace('/', os.sep))
        e = os.path.exists(p)
        print('  %-56s %s' % (rel, 'OK' if e else 'MISSING'))
        ok &= e
    print('verdict =', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
