#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP §13：把仓库的 `tts_engine.py` 修复同步到客户包（**定点替换**）。

🔴 **纪律**（仓库 ⇄ 客户包 是两份独立副本）：
- **禁止整目录覆盖同步**；
- 本脚本只做**精确字符串替换 + `assert count == 1`**（唯一命中断言）；
- 替换前后逐字节校验 SHA256，幂等（已同步则 no-op）。

本轮要同步的唯一变更：给引擎挂 `SpeakerLibrary`
（修 `ValueError: speaker_library not set; cannot look up named speaker`）。

用法：
    python live_caption/sync_c136_to_pkg.py            # 执行
    python live_caption/sync_c136_to_pkg.py --check    # 只校验不写
"""
import argparse
import hashlib
import os
import sys

# 🔴🔴🔴 §119 修正（真实缺陷，本脚本被 `app187` 判为 HARDCODED）：
#   原来 **写死仓库根** + **写死包版本 v1.3**
#   ⇒ ① 脚本搬到别处仍读**原仓库** ⇒ 验收结论是假象（§118 同类根因）
#   ⇒ ② 包早升到 v1.13 ⇒ 本脚本指着**旧包**跑 ⇒ 报出来的差异是「脚本过期」
#      而不是真回归（§48 闸门记载的同类事故）
#   ⇒ 修法与 §48 一致：**仓库根从 `__file__` 推导**；**包目录用
#      `pkg_paths.resolve_pkg_dir()` 自动发现**（**不写死版本号**），
#      并保留 `--pkg` 显式覆盖。
# 🔴 纪律：**只做精确字符串替换 + 唯一命中断言**（下方逻辑未变）⇒
#   **禁止整目录覆盖**。

_HERE = os.path.dirname(os.path.abspath(__file__))


def _discover_repo_root(start):
    """从 `start` **向上查找**仓库根（判据 = 祖先目录里有 `live_caption/` 且有 `pkg_paths.py`）。

    🔴 **为什么不能简单用「上上级」**：脚本一旦被**搬到别处**（例如复制到
    临时目录单独跑），「上上级」就指向**那个临时目录** ⇒ 找不到
    `live_caption/tts_engine.py` ⇒ 报错（实测本轮踩到）。
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
    # 兜底：在「脚本所在目录」及其**上两级**找 `pkg_paths.py`
    #   （脚本可能在 `<仓库根>/live_caption/` 下 ⇒ 仓库根在上两级；
    #     也可能被搬到仓库根旁 ⇒ 就在同级）
    #   ⇒ 用 `pkg_paths.repo_root()` 取根（它自己就在仓库根 ⇒ 必然指向真仓库）
    for cand in (os.path.abspath(start),
                 os.path.dirname(os.path.abspath(start)),
                 os.path.dirname(os.path.dirname(os.path.abspath(start)))):
        p = os.path.join(cand, 'pkg_paths.py')
        if not os.path.isfile(p):
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                '_sync_c136_pkg_paths', p)
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
    # 兜底：直接扫包根目录取最大版本
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


#: 仓库侧的源文件（**从 `__file__` 推导** ⇒ 搬走也能定位对）
REPO_FILE = os.path.join(REPO, 'live_caption', 'tts_engine.py')
# 🔴 客户包侧文件**不在模块级解析** ⇒ 必须在 `main()` 里按 `--pkg` /
#   自动发现的结果计算（`pkg_file`）⇒ 避免 import 时就去找包。

# 仓库里新增的那一段（含前置空行）—— 必须与客户包里**完全一致**才能替换。
ANCHOR_OLD = (
    "    on_log('[tts_engine] 模型加载完成')\n"
    "    return eng\n"
)

ANCHOR_NEW = (
    "    on_log('[tts_engine] 模型加载完成')\n"
    "\n"
    "    # \U0001f534\U0001f534 **必须挂 SpeakerLibrary**，否则按名查内置音色会直接抛\n"
    "    #   `ValueError: speaker_library not set; cannot look up named speaker`\n"
    "    #   （babelvox/pipeline.py:782 —— `speaker_library` 默认是 None）。\n"
    "    # 内置音色 cindy/lou/phil/steve **不是引擎内置常量**，而是随包文件\n"
    "    # `babelvox/data/speakers/{name}.json` + `{name}.npy`（embedding 1×1024）；\n"
    "    # `SpeakerLibrary(dir, copy_builtins=True)` 会把它们复制到库目录。\n"
    "    # ⇒ 只建 `SpeakerLibrary` 而不设 `eng.speaker_library` 是无效的。\n"
    "    _attach_speaker_library(eng, on_log=on_log)\n"
    "    return eng\n"
    "\n"
    "\n"
    "def _attach_speaker_library(eng, on_log=print) -> bool:\n"
    "    \"\"\"给引擎挂上 `SpeakerLibrary`（按名查内置音色的前提）。\n"
    "\n"
    "    库目录放 `%LOCALAPPDATA%\\\\Confucius4LiveCaption\\\\tts_speakers`\n"
    "    （**不写进客户包目录**，同编译缓存的纪律）。\n"
    "    失败只告警不抛 —— 内置音色是可选路径，参考 wav（spkonly）才是主路径。\n"
    "    \"\"\"\n"
    "    try:\n"
    "        from babelvox.speakers import SpeakerLibrary\n"
    "    except Exception as e:\n"
    "        on_log(f'[tts_engine] ⚠️ babelvox.speakers 不可用（{e}）'\n"
    "               f' ⇒ 内置音色（cindy/lou/phil/steve）不可用，只能用参考 wav')\n"
    "        return False\n"
    "    lib_dir = _cache_dir('tts_speakers')\n"
    "    try:\n"
    "        eng.speaker_library = SpeakerLibrary(lib_dir, copy_builtins=True)\n"
    "    except Exception as e:\n"
    "        on_log(f'[tts_engine] ⚠️ SpeakerLibrary 初始化失败（{e}）'\n"
    "               f' ⇒ 内置音色不可用')\n"
    "        return False\n"
    "    try:\n"
    "        names = sorted(p['name'] for p in eng.speaker_library.list_profiles())\n"
    "    except Exception:\n"
    "        names = []\n"
    "    on_log(f'[tts_engine] SpeakerLibrary 就绪：{lib_dir}'\n"
    "           f'（{len(names)} 个音色：{\", \".join(names) if names else \"无\"}）')\n"
    "    return True\n"
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--pkg', default=None,
                    help='客户包目录（不含 .zip）⇒ 默认自动发现**最大版本**')
    args = ap.parse_args()

    # 🔴 §119：包目录**运行时**解析（不写死版本号）
    try:
        pkg_app = _discover_pkg_app(args.pkg)
    except FileNotFoundError as e:
        print(f'[FAIL] {e}')
        return 2
    pkg_file = os.path.join(pkg_app, 'tts_engine.py')
    print(f'[客户包] {pkg_app}')

    if not os.path.isfile(pkg_file):
        print(f'[FAIL] 客户包文件不存在：{pkg_file}')
        return 2

    with open(pkg_file, 'r', encoding='utf-8', newline='') as f:
        pkg = f.read()
    with open(REPO_FILE, 'r', encoding='utf-8', newline='') as f:
        repo = f.read()

    if pkg == repo:
        print('[OK] 客户包已是最新（SHA256 一致），no-op')
        print(f'  repo {sha256(REPO_FILE)}')
        print(f'  pkg  {sha256(pkg_file)}')
        return 0

    n_old = pkg.count(ANCHOR_OLD)
    n_new = pkg.count(ANCHOR_NEW)
    print(f'[info] 客户包锚点计数：old={n_old} new={n_new}')

    if n_new == 1 and n_old == 0:
        print('[OK] 客户包已含新代码块，仅需整体对齐（哈希不同 ⇒ 有其它差异，'
              '不做整文件替换）')
        return 1

    if n_old != 1:
        print(f'[FAIL] 锚点命中 {n_old} 次（要求恰好 1 次）⇒ 拒绝修改')
        return 2

    new_pkg = pkg.replace(ANCHOR_OLD, ANCHOR_NEW)
    assert new_pkg.count(ANCHOR_NEW) == 1, '替换后新块必须恰好 1 处'

    # 替换后必须与仓库版本逐字节一致（说明仓库/包本来就只差这一段）
    if new_pkg != repo:
        print('[FAIL] 替换后仍与仓库不一致 ⇒ 客户包还有其它差异，'
              '本脚本不做整文件覆盖（请另写定点脚本）')
        return 3

    if args.check:
        print('[CHECK] 仅校验：定位到唯一锚点且替换后可与仓库对齐 —— PASS')
        return 0

    # 备份放包外
    bdir = r'C:\Users\Trekker-PTL\pkg_backup_app013'
    os.makedirs(bdir, exist_ok=True)
    bak = os.path.join(bdir, 'tts_engine.py.bak_20261023')
    with open(bak, 'wb') as f:
        f.write(pkg.encode('utf-8'))
    print(f'[backup] {bak}')

    with open(pkg_file, 'w', encoding='utf-8', newline='') as f:
        f.write(new_pkg)

    print('[OK] 已写入客户包')
    print(f'  repo {sha256(REPO_FILE)}')
    print(f'  pkg  {sha256(pkg_file)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
