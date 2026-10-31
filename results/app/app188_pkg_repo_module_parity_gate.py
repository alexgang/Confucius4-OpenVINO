#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app188_pkg_repo_module_parity_gate.py —— 「客户包 ⇄ 仓库 生产模块集合一致性」闸门。

背景（§118 之后本轮实测，2026-11-01）
----------------------------------------
`app187`（§118 新增）覆盖的是「**STATUS 引用的产物**是否已入库」，
它**不覆盖**下面这一类缺陷：

  **客户包 `app/` 里的模块，与仓库 `live_caption/` 的生产模块集合不一致。**

两种方向都会出事，方向相反：

| 方向 | 现象 | 后果 |
|---|---|---|
| **A 仓库有、包没有** | 仓库 `live_caption/` 有生产模块，但包目录 `app/` 里没有 | 客户机**缺模块** ⇒ 运行时 ImportError ⇒ 🔴🔴🔴 交付事故 |
| **B 包有、仓库没有** | 包目录 `app/` 里有仓库不存在的 `.py` | 下次重打包时**该文件被丢掉** ⇒ 若它是生产模块 ⇒ 客户机突然缺模块 |

🔴🔴🔴 **方向 B 在本轮被实测抓到**（真实案例）：
`Confucius4_LiveCaption_v1.13/app/_probe_tts_cuda.py`（3 072 B，2026-10-25 09:14:06）
—— 仓库里**从未存在**（`find` 与 `git log --diff-filter=A` 双向确认），
却在 v1.13 / v1.5 / v1.4 三个包目录里都有。
⇒ 它**已被 `pkg_exclude.is_app_dev_only()` 排除出 zip**（`_` 前缀规则）
   ⇒ **交付 zip 是干净的**（zip 内 `app/` 只有 28 个 `.py`，不含它）
⇒ 但**包目录**（= 用户实际点桌面快捷方式运行的目录）里仍然躺着这个
   写着开发机绝对路径的探针 ⇒ 「开发机路径泄漏」在**包目录**层面成立。

🔴 **为什么 `app049`（§48「客户包路径写死」闸门）没抓到它**：
`app049` 的扫描根是 `results/app` + `live_caption` —— 都在**仓库里**
⇒ 它**看不见只存在于客户包目录的文件**。
⇒ 这不是 `app049` 的缺陷（它的扫描根设计是对的），
   而是**缺一道「包 ⇄ 仓库」的对账闸门** ⇒ 本脚本补这一维。

判据（两条，都要能识破「已知有缺陷的旧产物」）
------------------------------------------------
* **A1 缺模块（🔴 阻断）**：包目录 `app/` 里的每个**非开发专用** `.py`，
  必须在仓库 `live_caption/` 有同名文件 ⇒ 否则「包里有、仓库没有」。
  ⚠️ 排除**开发专用**（`pkg_exclude.is_app_dev_only()`）——
  那些是**有意**不进 zip 的探针，不算「会丢的生产模块」。
* **A2 孤儿残留（🟡 提醒，不阻断）**：包目录 `app/` 里有**开发专用**文件
  （`_` 前缀等）但仓库没有 ⇒ 它已被排除出 zip ⇒ 交付 zip 不受影响
  ⇒ 只作为「包目录卫生」提醒列出。
* **B1 生产模块漏同步（🔴 阻断）**：仓库 `live_caption/` 里被
  `app049.ACTIVE_RE` 判定为「活跃验收/回归脚本」之外的、且**包目录没有**
  的模块 —— 难以自动判定 ⇒ 本闸门**不做**这一条
  （避免误报 ⇒ 恒 FAIL 的闸门等于没有闸门）。

  ⇒ **实际阻断判据 = A1**；A2 是提醒。

🔴🔴🔴 **「判据 PASS」≠「判据正确」**（§四纪律）
------------------------------------------------
所以本脚本**自带鉴别力自检**（`--selftest`）：
在**临时副本**里注入 3 类已知缺陷 ⇒ 必须**恰好**命中对应条数。

用法
----
    python results/app/app188_pkg_repo_module_parity_gate.py
    python results/app/app188_pkg_repo_module_parity_gate.py --json <out.json>
    python results/app/app188_pkg_repo_module_parity_gate.py --selftest
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

#: 🔴 **`pkg_exclude` 加载失败时的兜底规则**（与
#: `pkg_exclude.APP_DEV_ONLY_FILE_RE` **逐字一致**）
#:   —— 目的：让本闸门在「`pkg_exclude` 不可用」时**仍能区分**
#:   「开发专用探针」与「真生产模块」，而不是把它们一锅端成 orphan
#:   ⇒ 否则闸门会因为「多了一个 `_probe.py`」而恒 FAIL ⇒ 等于没有闸门。
#:   ⚠️ 若 `pkg_exclude.py` 的规则改了，**这里必须同步改** ⇒ 故在自检里
#:      加了 T5：拿**真实** `pkg_exclude` 交叉验证两者一致。
_DEV_ONLY_RE_FALLBACK = re.compile(r'^_[A-Za-z0-9_]+\.(py|ps1|bat|sh)$', re.I)


def _load_pkg_exclude(repo_root):
    """加载 `pkg_exclude.py`（开发专用文件的**权威判定**）。

    🔴 **不 import 被测模块**（§四纪律：验收脚本不 import 被测模块）
    ⇒ 这里 import 的是**规则表**（`pkg_exclude`），不是被验收的 App 模块。
    若加载失败 ⇒ 返回 `None` ⇒ 调用方降级为「只报不判」。
    """
    path = os.path.join(repo_root, 'pkg_exclude.py')
    if not os.path.isfile(path):
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location('_app188_pkg_exclude', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _pkg_app_dir(repo_root):
    """客户包 `app/` 目录（**不写死版本号** ⇒ 自动发现最大版本）。"""
    try:
        sys.path.insert(0, repo_root)
        import pkg_paths
        return pkg_paths.pkg_app_dir()
    except Exception:
        pass
    # 兜底：直接扫包根目录
    root = r'C:\Users\Trekker-PTL'
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
    return best


def _is_dev_only(name, pkg_exclude):
    """判断包目录里的某个 `.py` 是否**开发专用**（不进 zip）。

    优先用 `pkg_exclude.is_app_dev_only()`（权威规则表）；
    不可用时退回**逐字一致**的兜底正则（见 `_DEV_ONLY_RE_FALLBACK` 的说明）。
    """
    if pkg_exclude is not None:
        try:
            return bool(pkg_exclude.is_app_dev_only('app/' + name))
        except Exception:
            pass
    return bool(_DEV_ONLY_RE_FALLBACK.match(name))


def collect(pkg_app, repo_live, pkg_exclude):
    """收集差集。

    返回 dict：
      * ``pkg_modules``     —— 包目录 `app/` 下的 `.py` 文件名
      * ``repo_modules``    —— 仓库 `live_caption/` 下的 `.py` 文件名
      * ``orphan``          —— 包有仓库无，且**非开发专用** ⇒ 🔴 阻断
      * ``dev_only_orphan`` —— 包有仓库无，且**开发专用** ⇒ 🟡 提醒
      * ``pkg_only``        —— 包有仓库有（对齐的，正常）
      * ``repo_only``       —— 仓库有包无（列出，**不判负**：大量一次性脚本）
    """
    pkg_modules = set()
    if pkg_app and os.path.isdir(pkg_app):
        pkg_modules = {f for f in os.listdir(pkg_app) if f.endswith('.py')}

    repo_modules = set()
    if os.path.isdir(repo_live):
        repo_modules = {f for f in os.listdir(repo_live) if f.endswith('.py')}

    orphan = []
    dev_only_orphan = []
    for name in sorted(pkg_modules):
        if name in repo_modules:
            continue
        if _is_dev_only(name, pkg_exclude):
            dev_only_orphan.append(name)
        else:
            orphan.append(name)

    repo_only = sorted(repo_modules - pkg_modules)

    return {
        'pkg_modules': sorted(pkg_modules),
        'repo_modules': sorted(repo_modules),
        'orphan': orphan,
        'dev_only_orphan': dev_only_orphan,
        'repo_only': repo_only,
    }


def _selftest():
    """🔴🔴🔴 **鉴别力实测**（§四纪律：判据必须能识破已知有缺陷的旧产物）。

    在**临时副本**里构造 4 个已知状态 ⇒ 期望各自的判据结论。
    """
    tmp = tempfile.mkdtemp(prefix='app188_selftest_')
    try:
        pkg_app = os.path.join(tmp, 'pkg', 'app')
        repo_live = os.path.join(tmp, 'repo', 'live_caption')
        os.makedirs(pkg_app)
        os.makedirs(repo_live)

        def w(d, n, c='x'):
            with open(os.path.join(d, n), 'w', encoding='utf-8') as f:
                f.write(c)

        # 正常基线：包 3 个、仓库 3 个，全部对齐
        for n in ('a.py', 'b.py', 'c.py'):
            w(pkg_app, n)
            w(repo_live, n)
        # 开发专用孤儿（`_` 前缀）⇒ 只应是提醒，不阻断
        w(pkg_app, '_probe.py')

        r0 = collect(pkg_app, repo_live, None)
        ok = []
        ok.append(('T0 干净基线无孤儿', r0['orphan'] == []))
        ok.append(('T1 开发专用孤儿被单列',
                   r0['dev_only_orphan'] == ['_probe.py'] and r0['orphan'] == []))

        # 注入 1：包有仓库无的**生产**模块 ⇒ 必须被抓成 orphan
        w(pkg_app, 'ghost.py')
        r1 = collect(pkg_app, repo_live, None)
        ok.append(('T2 包有仓库无(生产) ⇒ orphan', r1['orphan'] == ['ghost.py']))

        # 注入 2：包有仓库无的**开发专用**模块 ⇒ 不得进 orphan
        w(pkg_app, '_ghost.py')
        r2 = collect(pkg_app, repo_live, None)
        ok.append(('T3 开发专用孤儿不进 orphan',
                   r2['orphan'] == ['ghost.py']
                   and '_ghost.py' in r2['dev_only_orphan']))

        # 注入 3：包少一个仓库已有的模块 ⇒ 进 repo_only（不判负）
        os.remove(os.path.join(pkg_app, 'c.py'))
        r3 = collect(pkg_app, repo_live, None)
        ok.append(('T4 包少模块 ⇒ repo_only 且不判负',
                   r3['orphan'] == ['ghost.py'] and 'c.py' in r3['repo_only']))

        n_pass = sum(1 for _, v in ok if v)
        n_fail = len(ok) - n_pass

        # T5：兜底正则必须与**真实** `pkg_exclude.APP_DEV_ONLY_FILE_RE` 一致
        #    ⇒ 否则「`pkg_exclude` 加载失败时」的兜底会与权威规则漂移
        #       ⇒ 闸门会在两种加载状态下给出**不同**结论 ⇒ 不可复现。
        pe = _load_pkg_exclude(REPO)
        if pe is None:
            ok.append(('T5 兜底规则与 pkg_exclude 一致', False))
        else:
            pat = getattr(pe, 'APP_DEV_ONLY_FILE_RE', None)
            same = (pat is not None
                    and pat.pattern == _DEV_ONLY_RE_FALLBACK.pattern
                    and bool(pat.flags & re.IGNORECASE) == bool(_DEV_ONLY_RE_FALLBACK.flags & re.IGNORECASE))
            ok.append(('T5 兜底规则与 pkg_exclude 一致', same))
            n_pass = sum(1 for _, v in ok if v)
            n_fail = len(ok) - n_pass

        print('== app188 鉴别力自检 ==')
        for name, v in ok:
            print('  [%s] %s' % ('PASS' if v else 'FAIL', name))
        print('  结论: %s（PASS %d / FAIL %d）' % ('PASS' if n_fail == 0 else 'FAIL',
                                                   n_pass, n_fail))
        return 0 if n_fail == 0 else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description='客户包 ⇄ 仓库 生产模块集合一致性闸门')
    ap.add_argument('--json', default=None, help='证据落盘路径')
    ap.add_argument('--selftest', action='store_true', help='只跑鉴别力自检')
    args = ap.parse_args()

    if args.selftest:
        return _selftest()

    pkg_exclude = _load_pkg_exclude(REPO)
    pkg_app = _pkg_app_dir(REPO)
    repo_live = os.path.join(REPO, 'live_caption')

    res = collect(pkg_app, repo_live, pkg_exclude)

    n_fail = len(res['orphan'])
    res['n_pkg_modules'] = len(res['pkg_modules'])
    res['n_repo_modules'] = len(res['repo_modules'])
    res['n_orphan'] = len(res['orphan'])
    res['n_dev_only_orphan'] = len(res['dev_only_orphan'])
    res['n_repo_only'] = len(res['repo_only'])
    res['n_fail'] = n_fail
    res['n_pass'] = 1 if n_fail == 0 else 0
    res['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    res['pkg_app'] = pkg_app
    res['repo_live'] = repo_live
    res['pkg_exclude_loaded'] = pkg_exclude is not None
    res['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    res['script'] = os.path.basename(__file__)
    res['purpose'] = ('§104 第④层「产物本身没进仓库」的反向形态：'
                       '包目录 app/ 与仓库 live_caption/ 的生产模块集合必须一致 ⇒ '
                       '否则「包里有、仓库没有」的文件会在下次重打包时**被丢掉**')

    print('== 客户包 ⇄ 仓库 生产模块集合一致性闸门 ==')
    print('  包 app/ 目录 : %s' % pkg_app)
    print('  仓库 live_caption : %s' % repo_live)
    print('  pkg_exclude 已加载 : %s' % res['pkg_exclude_loaded'])
    print('  包内 .py 数   : %d' % res['n_pkg_modules'])
    print('  仓库 .py 数   : %d' % res['n_repo_modules'])
    print('  ❌ 包有仓库无（生产模块，会被丢）: %d' % res['n_orphan'])
    for n in res['orphan']:
        print('    ORPHAN  %s' % n)
    print('  (🟡 包有仓库无〔开发专用〕，已被排除出 zip ⇒ 不阻断): %d'
          % res['n_dev_only_orphan'])
    for n in res['dev_only_orphan']:
        print('    DEV-ONLY  %s' % n)
    print('  (仓库有包无：一次性/开发脚本 ⇒ 不判负): %d' % res['n_repo_only'])
    print('  结论: %s（PASS %d / FAIL %d）'
          % (res['verdict'], res['n_pass'], res['n_fail']))

    if args.json:
        outp = args.json if os.path.isabs(args.json) else os.path.join(REPO, args.json)
        d = os.path.dirname(outp)
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(outp, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print('  证据已落盘: %s' % outp)

    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
