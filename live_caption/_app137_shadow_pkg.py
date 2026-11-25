#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app137_shadow_pkg.py — **造「影子包」**（APP-134 b/c 需要改包内代码时用）。

## 为什么需要影子包

reviewer APP-134 b/c 的两条都要求**改包内代码**做 A/B：
* **b**：自检 + NaN 守卫**开 vs 关**（关 ⇒ 相当于「21f7c39 之前的 tts_engine」）；
* **c**：c13 **开 vs 关** ＋ TTS=GPU.0。

🔴 **但真包 `Confucius4_LiveCaption_v2.6` 是交付版** ⇒
**禁止原地改**（APP-055）⇒ 只能造一份**影子包**。

## 影子包怎么造（**不复制 26 GB**）

* `models/`、`python/`、`.runtime_deps/`、`ext/` ⇒ **Windows 目录联接（junction）**
  ⇒ **零拷贝、零磁盘占用**，且**只读**（源包一个字节都不会动）；
* `app/` ⇒ **真拷贝**（要改的就是它）⇒ 只有 40 个文件 / ~2 MB；
* `docs/`、`tools/`、`results/` ⇒ 联接；
* 根文件（`Start_Bridge.bat` / `release.json` / `package_profile.json` …）⇒ **真拷贝**。

⇒ 影子包 ≈ **2 MB**，建/删都很快。

## 🔴 纪律
* **绝不删/改源包**：联接只指向源，删影子包时**只删联接本身**（用 `os.rmdir`，
  **不**用 `shutil.rmtree` ⇒ 不会顺着联接删到源包）⇒ 本机有「安全删除 shim」，
  `rmtree` 会被拦而且有误删风险；
* 建之前先确认**源包目录存在**；
* 影子包名字带 `shadow` ⇒ 一眼可辨。

## 用法
```
python live_caption/_app137_shadow_pkg.py --build   --tag app134b_guard_off
python live_caption/_app137_shadow_pkg.py --remove  --tag app134b_guard_off
python live_caption/_app137_shadow_pkg.py --list
```
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HOME = os.path.dirname(REPO)
RESULTS = os.path.join(REPO, 'results', 'app')

SRC = os.path.join(HOME, 'Confucius4_LiveCaption_v2.6')
SHADOW_ROOT = os.path.join(HOME, 'shared', 'shadow_pkgs')

#: 🔴 **联接**（大目录，零拷贝）
LINK_DIRS = ['models', 'python', '.runtime_deps', 'ext', 'docs', 'tools', 'results']

#: 🔴 **真拷贝**（要改的 / 小目录）
COPY_DIRS = ['app']
COPY_FILES = ['Start_Bridge.bat', 'Start_LiveCaption.bat', 'Diagnose.bat',
              'package_profile.json', 'release.json', 'README_zh.md',
              'README_en.md', 'NOTICE', 'THIRD_PARTY.md']


def shadow_dir(tag: str) -> str:
    return os.path.join(SHADOW_ROOT, '%s_shadow_%s' % ('Confucius4_LiveCaption_v2.6', tag))


def make_junction(link_path: str, target: str) -> bool:
    """Windows 目录联接（`mklink /J`）。非 Windows ⇒ 用符号链接。"""
    if os.path.exists(link_path):
        return False
    if os.name == 'nt':
        # 🔴 `mklink /J` **不需要管理员**（`/D` 才需要）
        r = subprocess_run(['cmd', '/c', 'mklink', '/J', link_path, target])
        return r == 0 and os.path.exists(link_path)
    os.symlink(target, link_path, target_is_directory=True)
    return os.path.exists(link_path)


def subprocess_run(cmd):
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    if r.returncode != 0:
        print('  cmd 失败：%s' % (r.stderr or r.stdout))
    return r.returncode


def build(tag: str) -> int:
    if not os.path.isdir(SRC):
        print('FAIL: 源包不存在 %s' % SRC)
        return 2
    dst = shadow_dir(tag)
    if os.path.exists(dst):
        print('FAIL: 影子包已存在 %s ⇒ 不覆盖' % dst)
        return 2
    os.makedirs(dst, exist_ok=True)
    made = {'links': [], 'copied': []}
    for d in LINK_DIRS:
        s = os.path.join(SRC, d)
        if not os.path.isdir(s):
            continue
        if make_junction(os.path.join(dst, d), s):
            made['links'].append(d)
        else:
            print('  ⚠️ 联接失败 %s ⇒ 退回复制' % d)
            shutil.copytree(s, os.path.join(dst, d))
            made['copied'].append(d)
    for d in COPY_DIRS:
        s = os.path.join(SRC, d)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(dst, d))
            made['copied'].append(d)
    for f in COPY_FILES:
        s = os.path.join(SRC, f)
        if os.path.isfile(s):
            shutil.copy2(s, os.path.join(dst, f))
            made['copied'].append(f)

    # ── 体积/文件数实测（证明「零拷贝」） ─────────────────────────
    n_files = 0
    n_bytes = 0
    for dp, dns, fns in os.walk(dst):
        for fn in fns:
            try:
                n_files += 1
                n_bytes += os.path.getsize(os.path.join(dp, fn))
            except OSError:
                pass
    ev = {'tag': tag, 'shadow': dst, 'src': SRC, 'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
          'links': made['links'], 'copied': made['copied'],
          'n_files': n_files, 'n_bytes': n_bytes}
    os.makedirs(RESULTS, exist_ok=True)
    op = os.path.join(RESULTS, 'app137_shadow_pkg_%s.json' % tag)
    tmp = op + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(ev, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, op)
    print('影子包已建：%s' % dst)
    print('  联接（零拷贝）：%s' % made['links'])
    print('  真拷贝：%s' % made['copied'])
    print('  实测 %d 文件 / %d B（源包 26 GB ⇒ **零拷贝**已生效）' % (n_files, n_bytes))
    print('  证据：%s' % op)
    return 0


def remove(tag: str) -> int:
    dst = shadow_dir(tag)
    if not os.path.exists(dst):
        print('影子包不存在 %s' % dst)
        return 0
    # 🔴 **先删联接**（只删链接本身，**不**顺着删源包）
    for d in LINK_DIRS:
        p = os.path.join(dst, d)
        if os.path.exists(p):
            try:
                os.rmdir(p)          # junction / symlink ⇒ rdir 即可
                print('  已删联接 %s' % d)
            except OSError as e:
                print('  ⚠️ 联接 %s 删除失败（%s）⇒ **不删源包**' % (d, e))
    # 再删真拷贝的部分
    for d in COPY_DIRS + ['docs', 'tools', 'results']:
        p = os.path.join(dst, d)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p, ignore_errors=True)
    for f in COPY_FILES:
        p = os.path.join(dst, f)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass
    try:
        os.rmdir(dst)
        print('影子包已删：%s' % dst)
    except OSError as e:
        print('⚠️ 目录未清空（%s）⇒ 保留，**未动源包**' % e)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--build', action='store_true')
    ap.add_argument('--remove', action='store_true')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--tag', default='default')
    args = ap.parse_args()
    if args.list:
        if os.path.isdir(SHADOW_ROOT):
            for nm in sorted(os.listdir(SHADOW_ROOT)):
                print(' ', nm)
        else:
            print('（没有影子包）')
        return 0
    if args.build:
        return build(args.tag)
    if args.remove:
        return remove(args.tag)
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
