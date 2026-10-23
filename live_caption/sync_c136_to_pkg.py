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

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
PKG_APP = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_v1.3\app'

REPO_FILE = os.path.join(REPO, 'live_caption', 'tts_engine.py')
PKG_FILE = os.path.join(PKG_APP, 'tts_engine.py')

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
    args = ap.parse_args()

    if not os.path.isfile(PKG_FILE):
        print(f'[FAIL] 客户包文件不存在：{PKG_FILE}')
        return 2

    with open(PKG_FILE, 'r', encoding='utf-8', newline='') as f:
        pkg = f.read()
    with open(REPO_FILE, 'r', encoding='utf-8', newline='') as f:
        repo = f.read()

    if pkg == repo:
        print('[OK] 客户包已是最新（SHA256 一致），no-op')
        print(f'  repo {sha256(REPO_FILE)}')
        print(f'  pkg  {sha256(PKG_FILE)}')
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

    with open(PKG_FILE, 'w', encoding='utf-8', newline='') as f:
        f.write(new_pkg)

    print('[OK] 已写入客户包')
    print(f'  repo {sha256(REPO_FILE)}')
    print(f'  pkg  {sha256(PKG_FILE)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
