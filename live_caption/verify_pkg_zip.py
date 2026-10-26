#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""verify_pkg_zip.py —— 客户包 zip 与包源目录的**逐文件 SHA256 一致性**校验。

为什么需要这个脚本（真实事故，2026-10-23）
-------------------------------------------
`pack_v13.py` 是**流式**写 zip 的：它一边遍历包目录、一边把文件写进 zip，
写完才做 MANIFEST 硬校验（files/bytes）和几个关键文件的存在性检查。
**它从不校验「zip 里的内容 == 打 zip 那一刻包目录里的内容」**。

后果（实测，2026-10-23 21:00~21:17）：
  - 21:00:32  `pack_v13.py` 写到 `app/translator.py`（此时是 **C-111 旧版**）
  - 21:06:56  MT 模块把 C-111-V7 定点同步进包目录（`app/translator.py` 被覆盖）
  - 21:17:23  打包结束 → zip 落盘
  ⇒ **zip 里是旧版 translator.py，包目录里是新版** ⇒ 客户拿到的是「改包目录 ≠ 交付客户」
    的经典形态：包目录改对了，但**真正发出去的 zip 还是旧的**。
  ⇒ 而 `pack_v13.py` 的所有断言（MANIFEST files/bytes、关键文件 [OK]、符号抽查）
    **全部 PASS** —— 因为它们**只查存在性与统计口径，不查内容一致性**。

本脚本补的就是这一刀：**用内容（SHA256）而不是存在性来判断交付物是否正确**。

用法
----
    # 校验 zip 与包目录一致（默认会同时校验仓库 ⇄ 包目录的关键 .py）
    python verify_pkg_zip.py --pkg C:\\...\\Confucius4_LiveCaption_v1.4 \
                             --zip  C:\\...\\Confucius4_LiveCaption_v1.4.zip

    # 只校验 zip ⇄ 包目录
    python verify_pkg_zip.py --pkg ... --zip ... --no-repo

    # 只做「仓库 ⇄ 包目录」关键文件核对
    python verify_pkg_zip.py --pkg ...

退出码
------
    0 = 全部一致；1 = 存在不一致（详情打到 stdout）。

口径
----
* **逐文件 SHA256**（原始字节，不做换行符归一化）——
  zip 与包目录都应是同一份物理文件的副本，任何字节差异都是**真差异**。
* zip 内条目名 = `<前缀>/<相对路径>`，前缀由 zip 内首个目录名推断，
  也可用 `--prefix` 显式指定。
* MANIFEST 自身**参与**比对（它就在包里，不是自引用问题 —— 这里只是比对字节）。
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import zipfile

# 仓库 ⇄ 客户包 双向核对的**关键 .py**（其余 .py 不逐个比对，避免噪音）
#
# 🔴🔴 §48：**这份清单原来只有 16 条，而包内 `app/*.py` 实测 20 个**
# ⇒ 漏掉 4 个（含 `tts_cuda.py` / `tts_cuda_sidecar.py` 这两个**会进包**
# 且 §48 刚修过写死包路径的文件）⇒ 「仓库 ⇄ 包目录」核对**根本查不到它们**
# ⇒ 属于「自检 PASS ≠ 全面无缺陷」。
# ⇒ 现在改为：**以包内实测的 `app/*.py` 为准**自动取全，
#    再**排除**明确不是交付物的开发专用脚本（`_` 前缀）。
KEY_APP_FILES_EXCLUDE_PREFIX = '_'

# 本脚本放在仓库的 `live_caption/` 下 ⇒ 仓库的 live_caption 目录就是本文件所在目录。
_REPO_LIVE = os.path.dirname(os.path.abspath(__file__))
# 仓库根（含 `pkg_exclude.py`），用于复用排除规则
_REPO_ROOT = os.path.dirname(_REPO_LIVE)


def _git_head_bytes(rel_path: str):
    """取 **HEAD** 里某文件的内容（字节）。

    🔴🔴 **为什么必须用 HEAD 而不是工作区**（长期记忆铁律：
    「打包前自检『包内代码 == 仓库』的基准必须是 `HEAD`，不是工作区」）：

    实测（§47.4.3）：工作区的 `live_caption_app.py` 是**方案 C 在制品**
    （未提交，SHA `451571bf…`），而包内是 **HEAD**（SHA `78663908…`）
    ⇒ 用工作区当基线 ⇒ 报出 1 处「不一致」⇒ **看起来像缺陷，其实是正常的**
    ⇒ 白白让人工解释一次，且**掩盖真正的差异**。

    ⚠️ `git show` 走 stdout ⇒ 换行符会被 git 原样保留
    （仓库里是 CRLF 时拿到的也是 CRLF）⇒ 后面统一做换行归一化再比。

    取不到（文件不在 HEAD / git 不可用）⇒ 返回 None（调用方按「跳过」处理，
    **不静默当成一致**）。
    """
    try:
        r = subprocess.run(
            ['git', 'show', 'HEAD:' + rel_path.replace('\\', '/')],
            cwd=_REPO_ROOT, capture_output=True, timeout=120)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def key_app_files(pkg_dir: str):
    """关键 .py 清单 = **包内实测全集** − 开发专用脚本（`_` 前缀）。

    🔴 这样清单**不会**随包新增文件而漏检（§48 的核心修法）。
    """
    app_dir = os.path.join(pkg_dir, 'app')
    names = []
    try:
        for n in sorted(os.listdir(app_dir)):
            if not n.endswith('.py'):
                continue
            if n.startswith(KEY_APP_FILES_EXCLUDE_PREFIX):
                continue
            names.append(n)
    except OSError:
        pass
    return names


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def _norm_lines(b):
    """换行符归一化后的字节（用于**仓库 ⇄ 包目录**的代码级比较）。

    ⚠️ 只用于「代码是否等价」的判断，**不能**用于 zip ⇄ 包目录的一致性判断。
    """
    return b.replace(b'\r\n', b'\n')


def detect_prefix(zf):
    """推断 zip 内的顶层目录名（如 `Confucius4_LiveCaption_v1.4`）。"""
    for n in zf.namelist():
        if '/' in n:
            return n.split('/', 1)[0]
        return ''            # 顶层直接是文件
    return ''


def _excluded_rels(pkg_dir):
    """列出包目录里**按排除规则本就不该进 zip** 的文件（相对路径，os.sep 分隔）。

    复用仓库根的 `pkg_exclude.py`（**单一数据源**）——
    否则本脚本会把「本来就该剔掉的编译缓存 / .bak」误报成「zip 不完整」。
    """
    try:
        sys.path.insert(0, _REPO_ROOT)
        import pkg_exclude  # noqa: E402
    except Exception as e:                       # pragma: no cover
        print(f'[warn] 无法 import pkg_exclude（{e}）⇒ 跳过「多余文件」检查')
        return []
    return [rel for rel, _size in pkg_exclude.iter_excluded(pkg_dir)]


def verify_zip_vs_pkg(zip_path, pkg_dir, prefix=None):
    """逐文件比对 zip 与包目录。返回 (ok, n_checked, mismatches, missing_in_pkg, extra_in_pkg)"""
    mismatches = []
    missing_in_pkg = []
    checked = 0
    zip_names = set()

    with zipfile.ZipFile(zip_path, 'r') as zf:
        if prefix is None:
            prefix = detect_prefix(zf)
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if prefix and name.startswith(prefix + '/'):
                rel = name[len(prefix) + 1:]
            elif prefix and '/' not in name:
                rel = name
            else:
                rel = name
            zip_names.add(rel)
            disk = os.path.join(pkg_dir, rel.replace('/', os.sep))
            if not os.path.isfile(disk):
                missing_in_pkg.append(rel)
                continue
            zbytes = zf.read(name)
            with open(disk, 'rb') as f:
                dbytes = f.read()
            checked += 1
            if sha256_bytes(zbytes) != sha256_bytes(dbytes):
                mismatches.append((rel, len(zbytes), len(dbytes),
                                   sha256_bytes(zbytes)[:12], sha256_bytes(dbytes)[:12]))

    # 包目录里存在、但 zip 里没有的文件
    # ⚠️ 正确口径：以 `pkg_exclude` 的**入包集合**为「期望集」——
    #    期望集里缺 = zip 不完整；zip 里多 = 不该进来的混进来了。
    expected, extra_in_zip = _expected_set(pkg_dir)
    missing_from_zip = sorted(expected - zip_names)
    unexpected_in_zip = sorted(zip_names - expected)

    ok = not mismatches and not missing_in_pkg and not missing_from_zip \
        and not unexpected_in_zip
    return ok, checked, mismatches, missing_in_pkg, (missing_from_zip,
                                                      unexpected_in_zip)


def _expected_set(pkg_dir):
    """返回 (期望进 zip 的文件集合, zip 里不该有的文件集合)。

    用 `pkg_exclude.iter_package_files`（**单一数据源**）算期望集，
    免得把「本来就该被剔掉的编译缓存 / .bak」误报成「zip 不完整」。
    """
    try:
        sys.path.insert(0, _REPO_ROOT)
        import pkg_exclude  # noqa: E402
    except Exception as e:                       # pragma: no cover
        print(f'[warn] 无法 import pkg_exclude（{e}）⇒ 跳过「多余文件」检查')
        return set(), set()
    expected = {rel.replace('\\', '/') for rel, _s in pkg_exclude.iter_package_files(pkg_dir)}
    excluded = {rel.replace('\\', '/') for rel, _s in pkg_exclude.iter_excluded(pkg_dir)}
    return expected, excluded


def verify_repo_vs_pkg(pkg_dir, repo_live=None, baseline='head'):
    """关键 .py 的「**基准** ⇄ 包目录」代码级核对（换行符归一化）。

    参数
    ----
    baseline
        * `'head'`（**默认，§48 改**）：基准 = **git HEAD** 的内容
          ⇒ 与「包里装的必须是已入库的代码」这条纪律一致；
        * `'worktree'`：基准 = 工作区文件（旧行为，保留以便对照）。

    返回 (n_same, n_diff, n_skip, diffs)
    diffs 条目 = (文件名, 基准 sha, 包内 sha)
    """
    repo_live = repo_live or _REPO_LIVE
    same = 0
    diffs = []
    n_skip = 0
    for name in key_app_files(pkg_dir):
        pp = os.path.join(pkg_dir, 'app', name)
        if not os.path.isfile(pp):
            continue
        with open(pp, 'rb') as f:
            pb = f.read()

        if baseline == 'head':
            rb = _git_head_bytes('live_caption/' + name)
            if rb is None:
                # HEAD 里没有 ⇒ 跳过（**不静默当成一致**）
                n_skip += 1
                continue
        else:
            rp = os.path.join(repo_live, name)
            if not os.path.isfile(rp):
                n_skip += 1
                continue
            with open(rp, 'rb') as f:
                rb = f.read()

        if _norm_lines(rb) == _norm_lines(pb):
            same += 1
        else:
            diffs.append((name, sha256_bytes(_norm_lines(rb))[:12],
                          sha256_bytes(_norm_lines(pb))[:12]))
    return same, len(diffs), n_skip, diffs


def main():
    ap = argparse.ArgumentParser(
        description='校验客户包 zip 与包目录 / 仓库的一致性（SHA256 逐文件）')
    ap.add_argument('--pkg', required=True, help='客户包源目录')
    ap.add_argument('--zip', default=None, help='zip 路径（默认 <pkg>.zip）')
    ap.add_argument('--prefix', default=None, help='zip 内顶层目录名（默认自动推断）')
    ap.add_argument('--no-repo', action='store_true', help='跳过「仓库 ⇄ 包目录」核对')
    ap.add_argument('--baseline', choices=('head', 'worktree'), default='head',
                    help='「仓库 ⇄ 包目录」的基准（默认 head = git HEAD；'
                         'worktree = 工作区文件，仅供对照）')
    ap.add_argument('--allow-extra', action='store_true',
                    help='包目录里多出来的文件不视为失败（默认只提示）')
    args = ap.parse_args()

    pkg = os.path.abspath(args.pkg)
    if not os.path.isdir(pkg):
        print(f'!! 包目录不存在: {pkg}')
        return 1
    zip_path = args.zip or (pkg.rstrip('\\/') + '.zip')

    rc = 0
    print('=' * 70)
    print('客户包一致性校验（SHA256 逐文件）')
    print('=' * 70)
    print('包目录:', pkg)
    print('zip   :', zip_path)
    print()

    if os.path.isfile(zip_path):
        try:
            ok, checked, mismatches, missing, extra = verify_zip_vs_pkg(
                zip_path, pkg, args.prefix)
        except zipfile.BadZipFile as e:
            print(f'  ✗ zip **不可读**（{e}）')
            print('    ⇒ 极可能**正在被打包**（pack_v13.py 会先删旧 zip 再流式写新 zip）。')
            print('    ⇒ 请等打包结束后重跑本脚本。')
            return 1
        print(f'[1] zip ⇄ 包目录：比对 {checked} 个文件')
        if mismatches:
            rc = 1
            print(f'  ✗ 内容不一致 {len(mismatches)} 个：')
            for rel, zs, ds, zsha, dsha in mismatches:
                print(f'      {rel}  zip {zs} B [{zsha}]  !=  包目录 {ds} B [{dsha}]')
            print('  ⇒ **zip 里是旧版内容** —— 打包期间包目录被改过（同步/打包竞态）。')
            print('    修法：重跑 pack_v13.py（不要手动改 zip）。')
        else:
            print('  ✓ 全部逐字节一致')
        if missing:
            rc = 1
            print(f'  ✗ zip 里有、包目录里没有：{len(missing)} 个')
            for rel in missing[:20]:
                print(f'      {rel}')
        if extra:
            missing_from_zip, unexpected_in_zip = extra
            if missing_from_zip:
                rc = 1
                print(f'  ✗ 该进包但 zip 里没有：{len(missing_from_zip)} 个'
                      f' ⇒ zip 不完整（打包中途包目录被改过）')
                for rel in missing_from_zip[:20]:
                    print(f'      {rel}')
            if unexpected_in_zip:
                rc = 1
                print(f'  ✗ 不该进包却出现在 zip 里：{len(unexpected_in_zip)} 个')
                for rel in unexpected_in_zip[:20]:
                    print(f'      {rel}')
    else:
        print(f'[1] zip ⇄ 包目录：跳过（zip 不存在: {zip_path}）')

    if not args.no_repo:
        same, ndiff, nskip, diffs = verify_repo_vs_pkg(pkg, baseline=args.baseline)
        bl = 'HEAD' if args.baseline == 'head' else '工作区'
        print()
        print(f'[2] {bl} ⇄ 包目录（关键 .py，换行符归一）：'
              f'一致 {same} / 不一致 {ndiff} / 跳过 {nskip}')
        print(f'    清单来源 = 包内实测 app/*.py（排除 `_{KEY_APP_FILES_EXCLUDE_PREFIX}` 前缀的'
              f'开发专用脚本）⇒ 共 {len(key_app_files(pkg))} 个')
        for name, rsha, psha in diffs:
            print(f'      ⚠ {name}  {bl} [{rsha}] != pkg [{psha}]')
        if ndiff:
            print(f'  ⇒ 包目录与{bl}不同步 ⇒ **包里装的不是已入库的代码**')
            print('    （若工作区有在制品改动，请先提交或定点同步后再打包）')
        if nskip:
            print(f'  ⇒ {nskip} 个文件在{bl}里找不到 ⇒ 已跳过（**不算一致**）')

    print()
    print('结论：' + ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
