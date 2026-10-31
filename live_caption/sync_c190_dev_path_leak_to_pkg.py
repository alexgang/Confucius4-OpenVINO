#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""sync_c190_dev_path_leak_to_pkg.py —— 把 §120 的「开发机路径泄漏」修复合到客户包。

🔴 **只做定点替换**（唯一命中断言），**禁整目录覆盖**。
🔴 **不手抄待插入源码** —— 替换块由 `git show <baseline>:<file>` 与当前工作区文件
   **用 `difflib` 自动派生**（带上下文 ⇒ 唯一命中）。
🔴 **行尾归一化**：读入时统一到 LF 做匹配，写回时**还原目标文件原本的行尾**
   （§119 的教训：CRLF 文件上 `count(anchor)` 恒为 0 ⇒ 定位失效）。
🔴 **幂等**：OLD 不在且 NEW 在 ⇒ 报 `ALREADY`。

🔴🔴🔴 §120 的两个真缺陷（本脚本初版由 §120 会话实测发现并修掉）
----------------------------------------------------------------
① **基线 commit 选错** —— 初版用 `bb7274e`（APP-045 提交）派生替换块，
   但**客户包里的这 5 个文件实际等于 `HEAD`**（包在 `bb7274e` 之后又同步过
   APP-050 等多次改动）⇒ 派生出来的 OLD 块在包内**命中 0 次**
   （实测：`speaker_tracker.py` 7 块里 5 块命中 0、`tts_engine.py` 22 块里
   18 块命中 0，且有 2 块 OLD **命中 14 次 / 2 次** ⇒ 直接套用会报
   `FAIL-mismatch-after` 或**替换错位置**）。
   ⇒ **修法**：基线改为 **HEAD**（= 包内内容的真实来源）⇒ 实测
   5 个文件共 8 块**全部唯一命中（count == 1）**。
   ⚠️ 不变式：**块命中数必须恰好 1** ⇒ 若基线选错 ⇒ 立即 FAIL，
   **不会静默替换错位置**（这正是「唯一命中断言」的价值）。

② **写死仓库根 + 写死包版本 v1.13** ⇒ 脚本搬到别处仍读原仓库
   ⇒ 「在 fresh clone 上同步是假象」（§118 同类根因）；且包升版后
   本脚本指着旧包跑 ⇒ 报出来的差异是「脚本过期」而不是真回归。
   ⇒ **修法**（与 §48 / §119 的 `sync_c136` 一致）：
     * 仓库根**从 `__file__` 向上查找**（祖先目录含 `live_caption/`
       且含 `pkg_paths.py`）；**找不到就抛异常**，绝不「用 cwd 猜」。
     * 包目录用 `pkg_paths.pkg_app_dir()` **自动发现最大版本**，
       保留 `--pkg` 显式覆盖。

用法
----
    python live_caption/sync_c190_dev_path_leak_to_pkg.py
    python live_caption/sync_c190_dev_path_leak_to_pkg.py --check
    python live_caption/sync_c190_dev_path_leak_to_pkg.py --pkg <包目录>
"""

from __future__ import annotations

import argparse
import ast
import difflib
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _discover_repo_root(start):
    """从 `start` **向上查找**仓库根。

    🔴 **为什么不能简单用「上上级」**：脚本一旦被**搬到别处**（例如复制到
    临时目录单独跑），「上上级」就指向**那个临时目录** ⇒ 找不到
    `live_caption/` ⇒ 报「文件不存在」或**更糟：指向错误对象**。
    ⇒ **向上查找**才能同时满足两种情形：
      ① 脚本在仓库内（`<仓库根>/live_caption/x.py`）⇒ 命中 `<仓库根>`；
      ② 脚本被搬走 ⇒ 沿祖先链找；若仍找不到 ⇒ 退回 `pkg_paths.repo_root()`
         （**不静默**用 cwd 猜 ⇒ 猜错会让验收结论变成假象）。
    """
    d = os.path.abspath(start)
    while True:
        if (os.path.isdir(os.path.join(d, 'live_caption'))
                and os.path.isfile(os.path.join(d, 'pkg_paths.py'))):
            return d
        parent = os.path.dirname(d)
        if parent == d:            # 已到盘根
            break
        d = parent
    for cand in (os.path.abspath(start),
                 os.path.dirname(os.path.abspath(start)),
                 os.path.dirname(os.path.dirname(os.path.abspath(start)))):
        p = os.path.join(cand, 'pkg_paths.py')
        if not os.path.isfile(p):
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                '_sync_c190_pkg_paths', p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            root = mod.repo_root()
            if os.path.isdir(os.path.join(root, 'live_caption')):
                return root
        except Exception:
            continue
    # 实在定位不到 ⇒ 抛异常（**不静默用 cwd** ⇒ 避免验收结论变假象）
    raise FileNotFoundError(
        '[仓库] 从 %s 向上找不到仓库根（需含 live_caption/ 与 pkg_paths.py）'
        % os.path.abspath(start))


#: 仓库根（**向上查找** ⇒ 脚本搬到别处也能定位对）
REPO = _discover_repo_root(_HERE)
if REPO not in sys.path:
    sys.path.insert(0, REPO)

LIVE = os.path.join(REPO, 'live_caption')
BACKUP = os.path.join(REPO, 'results', 'app', 'pkg_backup_app_c190_pkg')

#: 🔴 **基线 commit** = `HEAD`（包内这 5 个文件 == HEAD ⇒ 唯一命中）
#:   ⚠️ **不要**改成更早的 commit（§120 实测：那样 OLD 块命中 0 ⇒ 同步必失败）。
BASELINE_COMMIT = 'HEAD'

TARGETS = ['speaker_assets.py', 'speaker_tracker.py', 'tts_cuda.py',
           'tts_engine.py', 'tts_worker.py']


def _discover_pkg_app(pkg_dir=None):
    """解析客户包的 `app/` 目录（**不写死版本号**）。

    优先：显式 `--pkg` > 环境变量 `LIVECAP_PKG` > **自动发现最大版本**。
    找不到 ⇒ 抛异常（**不静默回退到某个旧版本**）⇒ 否则又会把
    「指错对象」伪装成「验收通过」。
    """
    try:
        import pkg_paths
    except ImportError:
        pkg_paths = None
    if pkg_paths is not None:
        return pkg_paths.pkg_app_dir(pkg_dir)
    root = os.environ.get('LIVECAP_PKG_ROOT', r'C:\Users\Trekker-PTL')
    prefix = 'Confucius4_LiveCaption_v'
    best = None
    best_key = None
    if os.path.isdir(root):
        for name in os.listdir(root):
            if not name.startswith(prefix):
                continue
            app = os.path.join(root, name, 'app')
            if not os.path.isdir(app):
                continue
            try:
                key = tuple(int(x) for x in name[len(prefix):].split('.'))
            except ValueError:
                continue
            if best_key is None or key > best_key:
                best_key = key
                best = app
    if best is None:
        raise FileNotFoundError('[客户包] 未找到 %sX.Y/app' % prefix)
    return best


def norm(b: bytes) -> str:
    return b.decode('utf-8').replace('\r\n', '\n')


def derive_blocks(base_text: str, new_text: str):
    """用 `difflib` 从「基线」与「当前」自动派生替换块（带上下文）。

    返回 ``[(old_block, new_block), ...]``；每个 block 都带**前后各一行**的
    公共上下文 ⇒ 在目标文件里**唯一命中**（§31 的教训：纯新增块不能用
    新块内部的行当锚点）。
    """
    a = base_text.split('\n')
    b = new_text.split('\n')
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    blocks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        ctx = 1
        i_start = max(0, i1 - ctx)
        j_start = max(0, j1 - ctx)
        i_end = min(len(a), i2 + ctx)
        j_end = min(len(b), j2 + ctx)
        old_block = '\n'.join(a[i_start:i_end])
        new_block = '\n'.join(b[j_start:j_end])
        blocks.append((old_block, new_block))
    return blocks


def git_show(commit: str, rel: str):
    p = subprocess.run(['git', '-C', REPO, 'show', '%s:%s' % (commit, rel)],
                       capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode('utf-8', 'replace')


def main():
    ap = argparse.ArgumentParser(
        description='§120 开发机路径泄漏修复 → 客户包定点同步')
    ap.add_argument('--check', action='store_true',
                    help='只校验（不写包）')
    ap.add_argument('--pkg', default=None,
                    help='客户包目录（不含 .zip）⇒ 默认自动发现**最大版本**')
    args = ap.parse_args()

    try:
        pkg_app = _discover_pkg_app(args.pkg)
    except FileNotFoundError as e:
        print('[FAIL] %s' % e)
        return 1

    print('== §120 开发机路径泄漏修复 → 客户包定点同步 ==')
    print('  仓库根   : %s' % REPO)
    print('  包 app/  : %s' % pkg_app)
    print('  基线     : %s' % BASELINE_COMMIT)
    print('  模式     : %s' % ('CHECK（不写）' if args.check else '写入'))

    all_ok = True
    summary = []

    for fname in TARGETS:
        rel = 'live_caption/%s' % fname
        base = git_show(BASELINE_COMMIT, rel)
        if base is None:
            print('FAIL %s: 取不到基线 %s' % (fname, BASELINE_COMMIT))
            all_ok = False
            continue
        with open(os.path.join(LIVE, fname), 'rb') as f:
            cur_bytes = f.read()
        cur = norm(cur_bytes)

        pkg_path = os.path.join(pkg_app, fname)
        if not os.path.isfile(pkg_path):
            print('FAIL %s: 包内不存在' % fname)
            all_ok = False
            continue
        with open(pkg_path, 'rb') as f:
            pkg_bytes = f.read()
        pkg_crlf = pkg_bytes.count(b'\r\n') > 0
        pkg = norm(pkg_bytes)

        blocks = derive_blocks(base, cur)
        if not blocks:
            print('SKIP %s: 基线与当前无差异' % fname)
            continue

        text = pkg
        applied = 0
        for old_b, new_b in blocks:
            n = text.count(old_b)
            if n == 0:
                if new_b in text:
                    continue                      # 幂等：该块已在位
                print('FAIL %s: OLD 命中 0 且 NEW 不在' % fname)
                all_ok = False
                continue
            if n != 1:
                print('FAIL %s: OLD 命中 %d 次（要求恰好 1）' % (fname, n))
                all_ok = False
                continue
            text = text.replace(old_b, new_b)
            applied += 1

        if applied == 0:
            print('ALREADY %s: 全部块已在位（幂等）' % fname)
            summary.append((fname, 'ALREADY', 0))
            continue

        # ---- 语法校验（AST）----
        try:
            ast.parse(text)
        except SyntaxError as e:
            print('FAIL %s: ast.parse 失败 %s' % (fname, e))
            all_ok = False
            continue

        # ---- 合并结果必须与仓库逐字一致（拒绝「部分同步」）----
        if text != cur:
            print('FAIL %s: 合并结果与仓库不一致（拒绝写入）' % fname)
            all_ok = False
            continue

        if args.check:
            print('OK   %s: %d 块将替换（未写入，--check）' % (fname, applied))
            summary.append((fname, 'CHECK', applied))
            continue

        # ---- 包外备份 ----
        os.makedirs(BACKUP, exist_ok=True)
        shutil.copy2(pkg_path, os.path.join(BACKUP, fname))

        # ---- 写回（还原包内原行尾）----
        out = text.replace('\n', '\r\n') if pkg_crlf else text
        with open(pkg_path, 'wb') as f:
            f.write(out.encode('utf-8'))

        # ---- 写后逐字节复核 ----
        with open(pkg_path, 'rb') as f:
            back = norm(f.read())
        if back != cur:
            print('FAIL %s: 写后与仓库不一致' % fname)
            all_ok = False
            continue
        print('OK   %s: %d 块已替换（包内行尾 %s，备份 %s）'
              % (fname, applied, 'CRLF' if pkg_crlf else 'LF',
                 os.path.join(BACKUP, fname)))
        summary.append((fname, 'SYNCED', applied))

    print('-- 汇总 --')
    for fname, st, n in summary:
        print('  %-22s %-8s %d 块' % (fname, st, n))
    print('== %s ==' % ('PASS' if all_ok else 'FAIL'))
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
