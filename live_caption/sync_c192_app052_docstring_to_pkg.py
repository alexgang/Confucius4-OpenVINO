#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""sync_c192_app052_docstring_to_pkg.py —— **【APP-052 ③】定点同步**：
把仓库 `live_caption/` 里**三处 docstring 脱敏**（`Trekker-PTL` → `<HOME>`）
同步到客户包 `app/`。

🔴🔴🔴 **纪律（§48 / §120 / 铁律「仓库 ⇄ 客户包 = 两份独立副本」）**：
  - **禁止整目录覆盖** ⇒ 本脚本**只做 3 个文件 6 处精确字符串替换**；
  - 每处替换前**断言「旧串在包内恰好命中 1 次」** ⇒ 命中 0 或 ≥2 ⇒
    **立即抛错退出**（fail-closed，绝不猜）；
  - 🔴 **幂等**：包内**已经是新串** ⇒ 视为「已同步」⇒ **跳过**（不报错），
    这样脚本**重复执行安全**（上一轮已写入 ⇒ 再跑不炸）；
    旧串 ≥2 次 ⇒ 仍然 fail-closed（那是**真的异常**，绝不猜）；
  - **不写死客户包版本号** ⇒ 从 `pkg_paths` 自动发现**最新版本**；
  - 写回后**定点复核**（「本轮那处新串 1 次 ＋ 旧串 0 次」）；
  - **只同步仓库里已经改好的内容** ⇒ 本脚本**不修改仓库**。

🔴 **为什么是「字符串替换」而不是「整文件复制」**：
  客户包与仓库是**两份独立副本**，且客户包的这些文件**已经历过多轮
  定点补丁**（§119/§120 的家目录改写等）⇒ 整文件复制会把包内的
  其它差异**一起覆盖掉** ⇒ 只同步本轮真正改的那几行。

用法：
    python live_caption/sync_c192_app052_docstring_to_pkg.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))


def find_repo_root(start: str) -> str:
    """🔴 向上查找仓库根（祖先目录含 `live_caption/` ＋ `pkg_paths.py`）。

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


def find_pkg_dir(repo: str) -> str:
    """自动发现**最新版本**客户包目录（**不写死版本号**）。

    🔴 **用 `pkg_paths.discover_pkg_dir()`**（单一数据源）⇒
      客户包在**家目录**下（不在仓库内）⇒ 自己 `os.listdir(repo)` 找不到。
    """
    sys.path.insert(0, repo)
    try:
        import pkg_paths
    finally:
        sys.path.pop(0)
    return pkg_paths.discover_pkg_dir()


#: (文件名, 旧串, 新串) —— **每处的旧串必须在包内恰好命中 1 次**
EDITS = (
    ('speaker_assets.py',
     "WORK   = r'C:\\Users\\Trekker-PTL\\qwen3asr_06b'",
     "WORK   = r'<HOME>\\qwen3asr_06b'"),
    ('speaker_assets.py',
     "REPO   = r'C:\\Users\\Trekker-PTL\\confucius4-openvino'",
     "REPO   = r'<HOME>\\confucius4-openvino'"),
    ('speaker_assets.py',
     "SHARED = r'C:\\Users\\Trekker-PTL\\shared'",
     "SHARED = r'<HOME>\\shared'"),
    ('tts_cuda.py',
     "⇒ 上上级是 `C:\\\\Users\\\\Trekker-PTL`",
     "⇒ 上上级是 `<HOME>`（家目录）"),
    ('tts_cuda.py',
     "开发机命中 `C:\\\\Users\\\\Trekker-PTL` 本身——",
     "开发机命中 `<HOME>` 本身——"),
    ('tts_cuda_sidecar.py',
     "（默认 `C:\\\\Users\\\\Trekker-PTL\\\\_fq3tts_env`）",
     "（默认 `<HOME>\\_fq3tts_env`；🔴【APP-052 ③】原文写的是开发机真实家目录 ⇒ 改为占位，避免随包泄漏开发机用户名）"),
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    repo = find_repo_root(HERE)
    pkg = find_pkg_dir(repo)
    pkg_app = os.path.join(pkg, 'app')
    print('[repo] %s' % repo)
    print('[pkg]  %s' % pkg)

    ok = True
    plan = []
    skipped = 0
    for fname, old, new in EDITS:
        p_repo = os.path.join(repo, 'live_caption', fname)
        p_pkg = os.path.join(pkg_app, fname)
        for p in (p_repo, p_pkg):
            if not os.path.isfile(p):
                print('  !! 缺文件：%s' % p)
                ok = False
        if not ok:
            continue
        with open(p_repo, 'r', encoding='utf-8', newline='') as f:
            src_repo = f.read()
        with open(p_pkg, 'r', encoding='utf-8', newline='') as f:
            src_pkg = f.read()

        # 🔴 断言方向：**仓库侧应已是「新串」（本轮已在仓库改好）**，
        #    **包侧应是「旧串」** ⇒ 两边各恰好 1 次 ⇒ 才允许替换。
        #    ⇒ 若仓库侧不是新串 ⇒ 说明「仓库没改好」⇒ fail-closed。
        n_repo_new = src_repo.count(new)
        n_repo_old = src_repo.count(old)
        n_pkg_old = src_pkg.count(old)
        n_pkg_new = src_pkg.count(new)
        if n_repo_new != 1 or n_repo_old != 0:
            print('  !! 仓库侧状态不对（新串 %d 次 / 旧串 %d 次，须 1/0）：%s :: %s'
                  % (n_repo_new, n_repo_old, fname, old[:60]))
            ok = False
            continue
        # 🔴🔴 **幂等三态**（本轮修正的缺陷）：
        #   ① 包内旧串恰好 1 次 ⇒ 需要替换 ⇒ 入 plan；
        #   ② 包内旧串 0 次 **且** 新串恰好 1 次 ⇒ **已同步**（上一轮已写入）
        #      ⇒ 跳过，**不算失败**（否则脚本不可重复执行）；
        #   ③ 包内旧串 0 次且新串 ≠ 1 次 ⇒ 状态不明 ⇒ fail-closed；
        #   ④ 包内旧串 ≥2 次 ⇒ 异常 ⇒ fail-closed。
        if n_pkg_old == 1:
            plan.append((fname, old, new))
            print('  [ok] %-22s 包内旧串命中 1 次 ⇒ 可替换' % fname)
        elif n_pkg_old == 0 and n_pkg_new == 1:
            skipped += 1
            print('  [skip] %-19s 包内已是新串 ⇒ 已同步，跳过' % fname)
        elif n_pkg_old == 0:
            print('  !! 包内旧串 0 次且新串 %d 次（状态不明，须恰好 1）：%s :: %s'
                  % (n_pkg_new, fname, old[:60]))
            ok = False
        else:
            print('  !! 包内旧串命中 %d 次（须恰好 1）：%s :: %s'
                  % (n_pkg_old, fname, old[:60]))
            ok = False

    if not ok:
        print('\n[FAIL] 前置断言不通过 ⇒ 未做任何修改')
        return 1
    print('\n[plan] 待替换 %d 处 / 已同步跳过 %d 处' % (len(plan), skipped))
    if args.dry_run:
        print('[dry-run] 未写入')
        return 0

    for fname, old, new in plan:
        p_pkg = os.path.join(pkg_app, fname)
        with open(p_pkg, 'r', encoding='utf-8', newline='') as f:
            src = f.read()
        assert src.count(old) == 1
        out = src.replace(old, new)
        with open(p_pkg, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        # 🔴 写后**复核**：本轮这一处**必须已替换**且**旧串已消失**。
        #
        # 🔴🔴🔴 **为什么不是「整文件与仓库逐字节一致」**：
        #   仓库 `live_caption/` 与客户包 `app/` 是**两份独立副本**
        #   （铁律：禁止整目录覆盖同步）⇒ 包内这些文件**本来就带着**
        #   §119/§120 的定点补丁（家目录改写等）⇒ **本来就与仓库不同**。
        #   ⇒ 用「整文件一致」当判据 ⇒ **必然 FAIL** ⇒ 那是**错判据**。
        #   ⇒ 正确判据 = 「**本轮改动的那一处已生效**」＋「旧串已清零」。
        with open(p_pkg, 'r', encoding='utf-8', newline='') as f:
            after = f.read()
        if after.count(new) != 1 or after.count(old) != 0:
            print('  [FAIL] %s：写后复核不通过（新串 %d 次 / 旧串 %d 次）'
                  % (fname, after.count(new), after.count(old)))
            ok = False
        else:
            print('  [ok] %-22s 已替换 ＋ 复核通过（新串 1 次 / 旧串 0 次）'
                  % fname)

    # 🔴 收尾复核：**包内 `app/` 下（除开发专用文件外）不得再出现开发机用户名**。
    print('\n=== 包内 app/ 残留开发机路径复核 ===')
    leaks = []
    for fn in sorted(os.listdir(pkg_app)):
        if not fn.endswith('.py'):
            continue
        try:
            txt = open(os.path.join(pkg_app, fn), 'r', encoding='utf-8',
                       newline='').read()
        except Exception:
            continue
        if 'Trekker-PTL' in txt:
            leaks.append(fn)
    if leaks:
        print('  [WARN] 仍含 "Trekker-PTL"：%s' % ', '.join(leaks))
        print('         （若这些文件被 pkg_exclude 排除出 zip ⇒ 不影响交付）')
    else:
        print('  [ok] 包内 app/ 无任何 "Trekker-PTL" 残留')

    print('\n%s' % ('[PASS] 全部同步完成' if ok else '[FAIL] 有失败项'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
