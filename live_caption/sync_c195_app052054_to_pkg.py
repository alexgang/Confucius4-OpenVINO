#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c195_app052054_to_pkg.py —— 【APP-052/053/054】客户包定点同步（**骨架升级基底**）。

## 为什么不是「逐块字符串替换」

APP-054 把 `speaker_tracker.py` **整体重写**了（23 853 B → 49 333 B）
⇒ 逐块替换要几百处 ⇒ 不现实。

⇒ 走铁律允许的**第二条路**：**「代码骨架等价校验后升级基底」**。

## 铁律遵守

1. 🔴 **不整目录覆盖** ⇒ 本脚本**只写 3 个文件**（不是 226 个）；
2. 🔴 **前置闸门**：必须先跑 `results/app/app201_pkg_skeleton_gate.py` 且 **PASS**
   ⇒ 否则**拒绝写入**（骨架不等价 ⇒ 升级基底会破坏包内调用方契约）；
3. 🔴 **包外备份**：改前把包内原文件复制到 `<包外>/pkg_backup_app_c195/`
   ⇒ 可回滚；
4. 🔴 **写后逐字节复核**：归一化行尾后与仓库版**逐字节一致**；
5. 🔴 **行尾还原**：写回时**还原包内原行尾**（§119 铁律：同步不得改变包的行尾）；
6. 🔴 **幂等**：已是新串 ⇒ 记 `ALREADY` 并跳过；
7. 🔴 **不写死包版本号** ⇒ `pkg_paths.discover_pkg_dir()` 自动发现。

## 同步的 3 个文件

| 文件 | 内容 |
|---|---|
| `speaker_tracker.py` | APP-054 线程化 / 攒整窗 / 降级 / 默认关；APP-053 `span_for_segment()` |
| `live_caption_app.py` | APP-054 `--speaker off\|on` + GUI「说话人识别」勾选框；APP-053 `span_for_segment` 调用；APP-052 ② GUI 说明文字清理 |
| `speaker_assets.py` | APP-052 ③ docstring 开发机路径 → `<HOME>` 占位 |

## 用法

    python live_caption/sync_c195_app052054_to_pkg.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

FILES = ('speaker_tracker.py', 'live_caption_app.py', 'speaker_assets.py')


def find_repo_root(start: str) -> str:
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
    sys.path.insert(0, repo)
    try:
        import pkg_paths
    finally:
        sys.path.pop(0)
    return pkg_paths.discover_pkg_dir()


def read_norm(path: str):
    with open(path, 'r', encoding='utf-8', newline='') as f:
        raw = f.read()
    nl = '\r\n' if '\r\n' in raw else '\n'
    return raw.replace('\r\n', '\n'), nl


def sha_norm(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    pkg = find_pkg_dir(repo)
    pkg_app = os.path.join(pkg, 'app')
    print('[repo] %s' % repo)
    print('[pkg]  %s' % pkg)

    # ── ① 前置闸门：骨架等价（必须 PASS）──
    gate = os.path.join(repo, 'results', 'app',
                        'app201_pkg_skeleton_evidence.json')
    print('\n--- 前置闸门：骨架等价 ---')
    rc = subprocess_call([sys.executable, os.path.join(
        repo, 'results', 'app', 'app201_pkg_skeleton_gate.py')])
    if rc != 0:
        print('  [FAIL] 骨架等价闸门未通过 ⇒ **拒绝写入**')
        return 1
    if not os.path.isfile(gate):
        print('  [FAIL] 闸门证据缺失 ⇒ 拒绝写入')
        return 1

    # ── ② 备份（包外）──
    backup_dir = os.path.join(os.path.dirname(pkg), 'pkg_backup_app_c195')
    if not os.path.isdir(backup_dir):
        os.makedirs(backup_dir, exist_ok=True)
    for fn in FILES:
        src = os.path.join(pkg_app, fn)
        dst = os.path.join(backup_dir, fn)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
    print('\n[backup] %s' % backup_dir)

    # ── ③ 同步 ──
    ok = True
    plan = []
    for fn in FILES:
        p_repo = os.path.join(repo, 'live_caption', fn)
        p_pkg = os.path.join(pkg_app, fn)
        if not (os.path.isfile(p_repo) and os.path.isfile(p_pkg)):
            print('  !! 缺文件：%s' % fn)
            ok = False
            continue
        t_repo, _ = read_norm(p_repo)
        t_pkg, nl_pkg = read_norm(p_pkg)
        if sha_norm(t_repo) == sha_norm(t_pkg):
            print('  [ALREADY] %-24s 包内已是仓库版' % fn)
            continue
        plan.append((fn, t_repo, t_pkg, nl_pkg))
        print('  [ok] %-24s 仓库 %d B ⇄ 包内 %d B ⇒ 待升级'
              % (fn, len(t_repo.encode('utf-8')),
                 len(t_pkg.encode('utf-8'))))

    if not ok:
        print('\n[FAIL] 前置检查不通过 ⇒ 未做任何修改')
        return 1
    if not plan:
        print('\n[plan] 无需修改（已全部同步）')
        return 0
    if args.dry_run:
        print('\n[dry-run] 未写入（待改 %d 个文件）' % len(plan))
        return 0

    for fn, t_repo, t_pkg, nl_pkg in plan:
        p_pkg = os.path.join(pkg_app, fn)
        out = t_repo
        if nl_pkg == '\r\n':
            out = out.replace('\n', '\r\n')
        with open(p_pkg, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        # 写后复核（归一化后逐字节一致）
        t_after, _ = read_norm(p_pkg)
        t_src, _ = read_norm(os.path.join(repo, 'live_caption', fn))
        if sha_norm(t_after) != sha_norm(t_src):
            print('  [FAIL] %s：写后复核不通过' % fn)
            ok = False
        else:
            print('  [ok] %-24s 已升级 ＋ 归一化 SHA256 %s 一致'
                  % (fn, sha_norm(t_after)[:16]))

    print('\n[done] %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def subprocess_call(cmd):
    import subprocess
    return subprocess.run(cmd).returncode


if __name__ == '__main__':
    sys.exit(main())
