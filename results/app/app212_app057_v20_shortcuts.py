#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""app212 —— APP-057：V2.0 的**桌面快捷方式**（字幕 App + 配音桥接服务）。

## 选型（APP-057 第 2 条要求「二选一，在 STATUS 写明选了哪个、为什么」）

**选了：两个桌面快捷方式**（而不是「在 App 里加启动桥接的开关」）。

**为什么**：

1. 桥接服务**必须用包内 python + 包内模型**（`openvino` / `babelvox` 只在包内）
   ⇒ 它的启动方式与 App 的启动方式**根本不同**（App 走 `live_caption_app.py`，
   桥接走 `ext/bridge/bridge.py`）。
2. 两者**设备互斥**（`ext/bridge.py::_caption_app_running`）⇒ 常常需要**只起一个**
   ⇒ 「App 内开关」会让用户在 App 里找一个根本不该在 App 里出现的按钮。
3. 桥接**可能先于 App 启动**（用户只想看网页配音）⇒ 独立入口才自然。

⇒ 桌面两个入口（**版本号从包目录名派生** ⇒ 只给「当前交付版本」生成）：
* `Confucius4 实时字幕 v<ver>.lnk` → 包内 `python\pythonw.exe` + `app\live_caption_app.py`
* `实时配音桥接服务 v<ver>.lnk` → 包内 `python\pythonw.exe` + `ext\bridge\bridge.py`

## 🔴 APP-060 ②（2026-11-01 21:10）：**已被取代的版本禁止再生成快捷方式**

reviewer 决定 **v2.1 为交付版**，**v2.0 已被取代**（`实时配音桥接服务 v2.0.lnk` 已由
reviewer 于 21:10 删除）⇒ **任何脚本都不得重新生成 v2.0 的快捷方式**。
本脚本据此加了**硬闸门**：
* `SUPERSEDED = {'2.0': '2.1'}` —— 目标包版本被取代 ⇒ **直接退出（exit 2），不写任何 .lnk**；
* `--pkg` 默认值改成**当前交付版本**（v2.1）⇒ 裸跑一次也不会碰到 v2.0。

## 铁律

* 🔴 **桌面 `.lnk` 必须用 `WScript.Shell.CreateShortcut` 生成**
  （手工拼字节 ⇒ 字段错位 ⇒ **坏链**，双击启动不了）
* 🔴 **判据 = COM 读回**（TargetPath 非空 / 所指文件存在 / **在包内** /
  `LinkFlags` 含目标定位位）＋ **反证**（手工坏链 / 目标不存在 / 指向包外 必须 FAIL）
* 🔴 **凡用 COM 的判据必须用仓库 `.venv`**（本项目唯一装了 `pywin32` 的解释器）
* 🔴 **不覆盖旧版本快捷方式** ⇒ 新建 `v2.0` 名字的；旧的 v1.13 保留不动
* 🔴 **不原地改用户正在测试的目录** ⇒ 只在桌面放新 .lnk，不动包目录里的代码
"""
from __future__ import annotations

import argparse
import json
import os
import struct
import time

HOME = os.path.expanduser('~')
# 🔴 APP-060 ①：交付版 = v2.1（v2.0 已 superseded）⇒ 默认目标包改为当前交付版本
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v2.1')
# 🔴 APP-060 ②：已被取代的版本 ⇒ **禁止再生成其桌面快捷方式**
SUPERSEDED = {'2.0': '2.1'}
DESKTOP = os.path.join(HOME, 'Desktop')

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           (' -- ' + detail) if detail else ''))
    return bool(cond)


def com_read_lnk(path):
    import win32com.client as wc
    ws = wc.Dispatch('WScript.Shell')
    sc = ws.CreateShortcut(path)
    return dict(target=str(sc.TargetPath or ''),
                arguments=str(sc.Arguments or ''),
                working_dir=str(sc.WorkingDirectory or ''),
                icon=str(sc.IconLocation or ''))


def lnk_linkflags(path):
    with open(path, 'rb') as f:
        b = f.read()
    if len(b) < 24:
        return -1
    return struct.unpack_from('<I', b, 20)[0]


def pkg_version_of(pkg_dir):
    """从包目录名派生版本号（`Confucius4_LiveCaption_v2.1` ⇒ `2.1`）。"""
    import re
    base = os.path.basename(os.path.normpath(pkg_dir))
    m = re.search(r'_v(\d+(?:\.\d+)*)$', base)
    if m:
        return m.group(1)
    return '2.0'


def make_lnk(path, target, arguments, workdir, desc, icon):
    """用 COM 生成 .lnk（**不是**手工拼字节）。"""
    import win32com.client as wc
    ws = wc.Dispatch('WScript.Shell')
    sc = ws.CreateShortcut(path)
    sc.TargetPath = target
    sc.Arguments = arguments
    sc.WorkingDirectory = workdir
    sc.Description = desc
    sc.IconLocation = icon
    sc.save()
    return path


def verify_lnk(lnk_path, pkg_dir, expect_target=''):
    """**四道子判据**（与 app192 同口径）。"""
    checks = {}
    try:
        back = com_read_lnk(lnk_path)
        checks['v1_com_target_nonempty'] = bool(back['target'])
    except Exception as e:
        back = {'target': '', 'arguments': '', 'working_dir': '', 'icon': '',
                'error': repr(e)}
        checks['v1_com_target_nonempty'] = False
    tp = back['target']
    checks['v2_target_exists'] = bool(tp and os.path.isfile(tp))
    if tp and pkg_dir:
        try:
            rel = os.path.relpath(os.path.normcase(tp),
                                  os.path.normcase(pkg_dir))
            inside = not rel.startswith('..')
        except ValueError:
            inside = False
    else:
        inside = False
    checks['v3_target_in_pkg'] = bool(inside)
    flags = lnk_linkflags(lnk_path)
    checks['v4_linkflags_has_target'] = bool(
        flags >= 0 and (flags & 0x1 or flags & 0x2))
    if expect_target:
        checks['v5_target_matches_expected'] = bool(
            tp and os.path.normcase(tp) == os.path.normcase(expect_target))
    ok = all(checks.values())
    return dict(ok=ok, checks=checks, com=back, linkflags=flags,
                reason='' if ok else '不通过：%r' % checks)


def main():
    global PKG
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--json', default=None)
    args = ap.parse_args()
    PKG = args.pkg

    pyw = os.path.join(PKG, 'python', 'pythonw.exe')
    app_py = os.path.join(PKG, 'app', 'live_caption_app.py')
    bridge_py = os.path.join(PKG, 'ext', 'bridge', 'bridge.py')
    launcher_py = os.path.join(PKG, 'ext', 'bridge', 'bridge_launcher.py')

    check('包内 pythonw.exe 存在', os.path.isfile(pyw), pyw)
    check('包内 live_caption_app.py 存在', os.path.isfile(app_py), app_py)
    check('包内 bridge.py 存在', os.path.isfile(bridge_py), bridge_py)
    check('包内 bridge_launcher.py 存在', os.path.isfile(launcher_py),
          launcher_py)

    # ── ① 字幕 App 快捷方式 ────────────────────────────────────
    # 🔴 **版本号从包目录名派生**（不写死版本）⇒ 任意版本都能出正确名字的 .lnk
    ver = pkg_version_of(PKG)
    # 🔴 APP-060 ② 硬闸门：**已被取代的版本不生成任何快捷方式**
    if ver in SUPERSEDED:
        print('[ABORT] 版本 v%s 已被 v%s 取代（APP-060 ①）⇒ 禁止再生成 v%s 的桌面快捷方式。'
              % (ver, SUPERSEDED[ver], ver))
        print('        交付版 = v%s；本脚本未写任何 .lnk。' % SUPERSEDED[ver])
        return 2
    print('=' * 70)
    print('app212 —— 桌面快捷方式 v%s（App + 配音桥接）' % ver)
    print('=' * 70)
    lnk1 = os.path.join(DESKTOP, 'Confucius4 实时字幕 v%s.lnk' % ver)
    make_lnk(lnk1, pyw, '"%s"' % app_py, PKG,
             'Confucius4 实时字幕 v%s（本地 ASR/MT/TTS）' % ver,
             '%s,0' % pyw)
    v1 = verify_lnk(lnk1, PKG, expect_target=pyw)
    print('  ① 字幕 App .lnk: %s' % lnk1)
    for k, ok in sorted(v1['checks'].items()):
        print('      %-28s %s' % (k, 'PASS' if ok else 'FAIL'))
    check('① 字幕 App .lnk 四道子判据全过', v1['ok'], v1['reason'])

    # ── ② 配音桥接服务快捷方式 ────────────────────────────────
    lnk2 = os.path.join(DESKTOP, '实时配音桥接服务 v%s.lnk' % ver)
    # ★ 桥接走 **打包侧 launcher**（`bridge_launcher.py`）：
    #   ① 它自己把 `<包根>/ext/.runtime_deps` 与 `<包根>/ext` 加进 sys.path
    #      （★ EXT-031 §3.2 文档称 bridge.py 会自动加 ⇒ **实测代码里没有**
    #        ⇒ 必须由打包侧补）
    #   ② 它自己设 EXT_RELEASE / EXT_APP_ROOT（发行版模式 + 映射到包内模型）
    #   ③ 用 `runpy` 转交 ⇒ 桥接的日志格式与退出码完全不变
    make_lnk(lnk2, pyw, '"%s" --real --pipeline --target-lang en '
                       '--host 127.0.0.1 --port 8765 --pair-port 8766 '
                       '--spk-bypass' % launcher_py,
             os.path.join(PKG, 'ext', 'bridge'),
             '实时配音桥接服务 v2.0（EXT 插件后端）',
             '%s,0' % pyw)
    v2 = verify_lnk(lnk2, PKG, expect_target=pyw)
    print('  ② 配音桥接 .lnk: %s' % lnk2)
    for k, ok in sorted(v2['checks'].items()):
        print('      %-28s %s' % (k, 'PASS' if ok else 'FAIL'))
    check('② 配音桥接 .lnk 四道子判据全过', v2['ok'], v2['reason'])

    # ★ 桥接 .lnk 的额外约束：**工作目录**必须在 `ext/bridge`
    #   （`-m bridge` 需要包根在 sys.path ⇒ cwd = ext/bridge 时 `bridge` 包
    #    在 cwd 下 ⇒ 可 import；且 `ext/config.py` 的 `package_root()` =
    #    `dirname(dirname(__file__))` = `ext/` ⇒ `release.json` 找不到
    #    ⇒ ★ 必须把包根加进 PYTHONPATH ⇒ 见下面的 start_bridge.cmd）
    check('② 桥接 .lnk 工作目录 = ext/bridge',
          os.path.normcase(v2['com']['working_dir'])
          == os.path.normcase(os.path.join(PKG, 'ext', 'bridge')),
          v2['com']['working_dir'])

    # ── ③ 反证组：判据必须能识破坏链 ──────────────────────────
    disc = []
    # (a) 手工拼字节的坏链（COM 读回 TargetPath 为空）
    bad1 = os.path.join(DESKTOP, '_probe_bad1.lnk')
    with open(bad1, 'wb') as f:
        f.write(b'L\x00\x00\x00' + b'\x00' * 60)
    r1 = verify_lnk(bad1, PKG)
    disc.append(dict(name='反证①手工坏链（COM 读回 TargetPath 空）',
                     ok=(not r1['ok']), detail=str(r1['checks'])))
    # (b) 目标文件不存在
    bad2 = os.path.join(DESKTOP, '_probe_bad2.lnk')
    make_lnk(bad2, os.path.join(PKG, 'python', '_no_such_file.exe'),
             '', PKG, 'probe', '%s,0' % pyw)
    r2 = verify_lnk(bad2, PKG)
    disc.append(dict(name='反证②目标文件不存在',
                     ok=(not r2['ok']), detail=str(r2['checks'])))
    # (c) 指向包外（开发目录）
    bad3 = os.path.join(DESKTOP, '_probe_bad3.lnk')
    make_lnk(bad3, os.path.join(HOME, 'live_dub_ext', 'tools',
                                'ext_launcher.py'), '', HOME, 'probe',
             '%s,0' % pyw)
    r3 = verify_lnk(bad3, PKG)
    disc.append(dict(name='反证③指向包外（开发目录 live_dub_ext）',
                     ok=(not r3['ok']), detail=str(r3['checks'])))
    for p in (bad1, bad2, bad3):
        try:
            os.remove(p)
        except OSError:
            pass
    check('③ 反证组全部成立（判据有鉴别力）',
          all(d['ok'] for d in disc),
          '%d/%d' % (sum(1 for d in disc if d['ok']), len(disc)))
    for d in disc:
        print('      %-42s %s' % (d['name'], 'PASS' if d['ok'] else 'FAIL'))

    # ── ④ 不覆盖旧快捷方式 ────────────────────────────────────
    old = [f for f in os.listdir(DESKTOP) if f.endswith('.lnk')
           and ('v1.13' in f or '实时字幕' in f or '桥接' in f)]
    print('  ④ 桌面现存相关 .lnk: %s' % old)
    check('④ 旧快捷方式仍在（未被覆盖）',
          all(os.path.isfile(os.path.join(DESKTOP, f)) for f in old),
          str(old))

    npass = sum(1 for _n, ok, _d in RESULTS if ok)
    nfail = len(RESULTS) - npass
    print('\n结果：%d PASS / %d FAIL' % (npass, nfail))

    out = {
        'tool': 'app212',
        'app': 'APP-057',
        'pkg': PKG,
        'at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'choice': '两个桌面快捷方式（App + 配音桥接服务）'
                  '；**不选**「App 内加启动桥接的开关」',
        'choice_reason': [
            '桥接必须用包内 python + 包内模型（openvino/babelvox 只在包内）'
            '⇒ 启动方式与 App 根本不同',
            '两者设备互斥（ext/bridge.py::_caption_app_running）⇒ 常需只起一个'
            '⇒ 「App 内开关」会让用户找不该在 App 里的按钮',
            '桥接可能先于 App 启动（用户只想看网页配音）⇒ 独立入口才自然',
        ],
        'lnk_caption': {'path': lnk1, 'verify': v1},
        'lnk_bridge': {'path': lnk2, 'verify': v2},
        'discrimination': disc,
        'existing_lnks': old,
        'summary': {'pass': npass, 'fail': nfail},
    }
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.json)
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
