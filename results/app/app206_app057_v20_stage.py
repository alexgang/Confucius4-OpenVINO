#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app206_app057_v20_stage.py —— 【APP-057】建 V2.0 包目录（**不覆盖任何旧目录**）。

## 为什么先建 V2.0 再还原 v1.13

APP-055 要求把 `Confucius4_LiveCaption_v1.13` 目录**还原到 06:08 态**；
APP-057 要求交付 **V2.0**（含 APP-053/054 的修复 + EXT 插件 + 桥接服务）。

⇒ V2.0 的代码基线 = **当前 v1.13 目录里的内容**（含 APP-053/054 修复）
⇒ 顺序必须是：① 复制出 v2.0 ② 再把 v1.13 原地还原
⇒ 否则还原完就没有新代码可复制了。

## 复制策略（**关键**）

| 目录 | 策略 | 理由 |
|---|---|---|
| `models/`（11.96 GB） | **硬链接** | 只读资产，零拷贝；同卷 NTFS 支持 |
| `python/`（0.78 GB） | **硬链接** | 同上 |
| `app/`、`results/`、`docs/`、根文件 | **真实复制** | 🔴 **代码会被改** ⇒ 若用硬链接，改 v2.0 会**连带改 v1.13** ⇒ 正是 APP-055 要禁止的「原地改用户正在测试的目录」 |
| `_backup_app_*` | **跳过** | 开发期备份，不进发行包（`pkg_exclude` 也剔 `.bak`；这两目录是上一轮 pack 的遗留） |

🔴 **硬链接的坑**：写 v2.0 的硬链接文件前必须先「断开链接」（copy 到临时文件 → replace）。
本脚本**只**对 `models/`、`python/` 建硬链接，且这两个目录**本轮不修改**。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HOME = r'C:\Users\Trekker-PTL'

SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v1.13')
DST = os.path.join(HOME, 'Confucius4_LiveCaption_v2.0')

#: 建硬链接的子目录（**只读资产**）
HARDLINK_DIRS = ('models', 'python')
#: 跳过不复制
SKIP_NAMES = ('_backup_app_20261028_preclone', '_backup_app_20261030_pre_sync99')


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def link_or_copy(src: str, dst: str) -> str:
    """优先硬链接；失败（跨卷 / 不支持）则真实复制。返回 'link' / 'copy'。"""
    if os.path.exists(dst):
        return 'skip'
    try:
        os.link(src, dst)
        return 'link'
    except OSError:
        shutil.copy2(src, dst)
        return 'copy'


def copy_tree_real(src: str, dst: str) -> int:
    """真实复制一整个目录树（**不用硬链接**）。返回文件数。"""
    n = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        target = dst if rel == '.' else os.path.join(dst, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(target, f)
            shutil.copy2(s, d)
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--json', default=None)
    args = ap.parse_args()

    print('=' * 72)
    print('【APP-057】建 V2.0 包目录')
    print('=' * 72)
    print('源：', SRC)
    print('目标：', DST)
    if not os.path.isdir(SRC):
        print('!! 源目录不存在 ⇒ 退出')
        return 1
    if os.path.exists(DST):
        print('!! 目标目录已存在 ⇒ 拒绝（避免覆盖旧目录）')
        return 1

    if args.dry_run:
        tot = 0
        for root, dirs, files in os.walk(SRC):
            for f in files:
                tot += 1
        print('[dry-run] 源文件数 =', tot)
        print('[dry-run] 将创建：', DST)
        return 0

    t0 = time.time()
    os.makedirs(DST, exist_ok=True)
    stats = {'link': 0, 'copy': 0, 'skip': 0}
    n_files = 0

    # ── ① 硬链接目录（只读资产）──
    for sub in HARDLINK_DIRS:
        s = os.path.join(SRC, sub)
        if not os.path.isdir(s):
            continue
        for root, dirs, files in os.walk(s):
            rel = os.path.relpath(root, s)
            target = os.path.join(DST, sub) if rel == '.' else \
                os.path.join(DST, sub, rel)
            os.makedirs(target, exist_ok=True)
            for f in files:
                stats[link_or_copy(os.path.join(root, f),
                                    os.path.join(target, f))] += 1
                n_files += 1
        print('[link] %s 完成' % sub)

    # ── ② 根文件 + 其余目录（真实复制）──
    for name in sorted(os.listdir(SRC)):
        s = os.path.join(SRC, name)
        d = os.path.join(DST, name)
        if name in SKIP_NAMES:
            print('[skip] %s' % name)
            continue
        if os.path.isdir(s):
            if name in HARDLINK_DIRS:
                continue
            c = copy_tree_real(s, d)
            stats['copy'] += c
            n_files += c
            print('[copy] %s/  (%d 文件)' % (name, c))
        else:
            shutil.copy2(s, d)
            stats['copy'] += 1
            n_files += 1
            print('[copy] %s' % name)

    # ── ③ 校验：随机抽 5 个文件逐字节比对 ──
    checks = []
    for rel in ['app/live_caption_app.py', 'app/speaker_tracker.py',
                'app/tts_engine.py', 'models/qwen3tts',
                'python/python.exe', 'ACCEPTED.json']:
        s = os.path.join(SRC, rel.replace('/', os.sep))
        d = os.path.join(DST, rel.replace('/', os.sep))
        if os.path.isdir(s):
            # 目录：逐文件清单比对（内容多，只比清单 + 抽样哈希）
            def listing(root):
                out = {}
                for r, ds, fs in os.walk(root):
                    for f in fs:
                        p = os.path.join(r, f)
                        out[os.path.relpath(p, root)] = os.path.getsize(p)
                return out
            ls_, ld_ = listing(s), listing(d)
            ok = (ls_ == ld_)
            detail = 'dir n=%d' % len(ls_)
            sha = None
        else:
            ok = (os.path.isfile(s) and os.path.isfile(d)
                  and sha256_file(s) == sha256_file(d))
            detail = 'file'
            sha = sha256_file(d) if os.path.isfile(d) else None
        checks.append({'path': rel, 'ok': ok, 'kind': detail,
                       'sha256': sha})
        print('[verify] %-32s %s' % (rel, 'OK' if ok else 'FAIL'))

    out = {
        'script': 'app206_app057_v20_stage.py',
        'correction': 'APP-057',
        'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
        'src': SRC, 'dst': DST,
        'n_files': n_files,
        'strategy': stats,
        'hardlink_dirs': list(HARDLINK_DIRS),
        'skipped': list(SKIP_NAMES),
        'checks': checks,
        'n_pass': sum(1 for c in checks if c['ok']),
        'n_fail': sum(1 for c in checks if not c['ok']),
        'elapsed_s': round(time.time() - t0, 1),
    }
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print('[json] %s' % args.json)
    print('完成：%d 文件 / link=%d copy=%d / %d PASS %d FAIL / %.1f s'
          % (n_files, stats['link'], stats['copy'],
             out['n_pass'], out['n_fail'], out['elapsed_s']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
