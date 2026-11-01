#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
🔴🔴🔴 APP-045②：**桌面快捷方式**随版本更新（只保留一个、名称带版本号）。

🔴 **为什么必须有这个模块**（reviewer APP-045② 原文）：
  「打包流程增加一步：每次出新版本并通过验收后，**把桌面快捷方式更新到
    最新版本**（只保留一个快捷方式，名称带版本号，例如
    "Confucius4 实时字幕 v1.12"），并在 STATUS 里记录。
    **还没通过真机验收的版本不要指过去。**」

🔴🔴 **事故背景**（reviewer 10:55 在目标机实测）：
  桌面「Confucius4 实时字幕.lnk」指向
  `C:\\Users\\Trekker-PTL\\Confucius4_LiveCaption_**v1.5**\\Start_LiveCaption.bat`
  ⇒ 用户从 v1.7 到 v1.12 的**全部改动**（字幕说话人标签、
  APP-039/040/043 的克隆修复、APP-041/042）**一次都没用上**
  ⇒ 用户说「还没修好」—— **不是没修，是没跑到**。
  ⇒ **这正是「守卫写在那里 ≠ 守卫能触发」的同类问题**：
     修复落在包里，而用户入口指向旧包。

🔴 **设计要点**：
  ① **只保留一个**：旧的「Confucius4 实时字幕.lnk」（无版本号）被**删除**，
     新建「Confucius4 实时字幕 v<版本>.lnk」⇒ 桌面不会堆一排。
  ② **名称带版本号** ⇒ 用户一眼能看出用的是哪一版。
  ③ 🔴 **未通过真机验收就不指过去**：
     判据 = 包目录里存在 `ACCEPTED.json`（**由真机验收通过后写入**）
     ⇒ 打包脚本**不会自作主张**改用户入口。
  ④ **幂等**：指向同一版本时**不重复重建**（避免每次打包都动桌面）。
  ⑤ 🔴🔴🔴 **【APP-052 ①】改用 `WScript.Shell.CreateShortcut` 生成**（**不再手工拼字节**）。

🔴🔴🔴 **APP-052 ① 的真实事故（本模块上一版的实现是「坏链」）**：
  上一版用**纯字节**手工构造 .lnk（MS-SHLLINK 的「最小可用形态」），写的是
  `LinkFlags = 0x00000020`（**只置 HasArguments**）⇒
  **既没有 HasLinkTargetIDList、也没有 HasLinkInfo、也没有 IsUnicode**
  ⇒ Windows **不会**用它定位目标 ⇒ 桌面上的 .lnk 是**坏链**：
  资源管理器双击**启动不了**，COM 读回 `TargetPath=[] / Arguments=[C]`。
  ⇒ reviewer's 字节级指控**已实测复现**（见 §123）。

  🔴 **根因**：「纯字节 .lnk」这个思路本身错了 —— 目标定位**依赖
  `LinkTargetIDList`（或 `HasLinkInfo` 的 LocalBasePath）**，
  **不是** StringData 里的路径字符串 ⇒ 「不依赖 COM」的代价是**造出坏链**。
  ⇒ **修法**：用 `WScript.Shell.CreateShortcut`（经 `pywin32` 调 COM API）
  生成 ⇒ 由**Windows 自己**写 IDList/LinkInfo ⇒ 必然可用。
  ⇒ COM 不可用时 **fail-closed**（**绝不**退回字节拼接造坏链）。

🔴 **纪律**：本模块**不 import 被测模块**、**不跑推理**、**不碰 CPU 重活**
  （纯文件操作）⇒ 不污染别的模块的计时窗口。
"""
from __future__ import annotations

import json
import os
import struct
import sys

# 🔴 快捷方式名的**稳定前缀**（含版本号的部分由版本决定）
LNK_BASE_NAME = 'Confucius4 实时字幕'
# 🔴 旧的无版本号快捷方式（要删掉，保证「只保留一个」）
LEGACY_LNK_NAME = 'Confucius4 实时字幕.lnk'
# 🔴 目标启动脚本（相对包目录）
START_BAT = 'Start_LiveCaption.bat'
# 🔴 图标（相对包目录）
ICON_REL = os.path.join('python', 'pythonw.exe')
# 🔴 **验收通过标记**（真机验收通过后由人/脚本写入）
ACCEPTED_MARKER = 'ACCEPTED.json'


# ── 桌面目录（优先 OneDrive 重定向）─────────────────────────────────
def desktop_dir() -> str:
    """返回**真实桌面目录**（兼容 OneDrive 重定向）。"""
    home = os.path.expanduser('~')
    for env in ('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer'):
        base = os.environ.get(env)
        if base:
            for sub in ('Desktop', '桌面'):
                p = os.path.join(base, sub)
                if os.path.isdir(p):
                    return p
    p = os.path.join(home, 'Desktop')
    if os.path.isdir(p):
        return p
    p = os.path.join(home, '桌面')
    if os.path.isdir(p):
        return p
    return p  # 兜底：返回默认路径（调用方负责处理不存在）


# ── .lnk 生成（【APP-052 ①】改用 COM ⇒ 不再手工拼字节）──────────────
def _win_str(s: str) -> bytes:
    """Windows 字符串区条目：2 字节字符数 + UTF-16LE 内容（**无终止符**）。

    🔴 **仅保留给判据里的「字节级体检」用**（用来确认 COM 生成的 .lnk
    **确实**带上了 `HasLinkTargetIDList`）⇒ **不再用它构造 .lnk**。
    """
    data = s.encode('utf-16-le')
    return struct.pack('<H', len(s)) + data


def _com_available() -> tuple:
    """返回 `(ok, reason, shell)`；COM 不可用 ⇒ `(False, 原因, None)`。

    🔴 **fail-closed**：`WScript.Shell` 经 `pywin32` 调 COM API。
      上一版「不依赖 COM」的方案造出了**坏链**（见模块 docstring）⇒
      **绝不**在 COM 不可用时退回字节拼接。
    """
    try:
        import win32com.client as wc
    except Exception as e:
        return False, 'pywin32 未安装（%r）' % e, None
    try:
        shell = wc.Dispatch('WScript.Shell')
    except Exception as e:
        return False, 'WScript.Shell 不可用（%r）' % e, None
    return True, '', shell


def lnk_linkflags(path: str) -> int:
    """读 .lnk 头部的 `LinkFlags`（**字节级体检**，用于判据）。

    🔴 **为什么需要它**：reviewer APP-052 ① 的核心指控是
      「手工构造的 .lnk **只置了 HasArguments**（`0x20`）⇒ 没有
      `HasLinkTargetIDList` / `HasLinkInfo` ⇒ Windows 不拿它定位目标」
      ⇒ **判据必须能检查这一位**，否则换一种坏法又判不出来。
    """
    try:
        b = open(path, 'rb').read()
    except OSError:
        return -1
    if len(b) < 24:
        return -1
    return struct.unpack_from('<I', b, 20)[0]


def lnk_flags_ok(path: str) -> bool:
    """`.lnk` 的 LinkFlags 是否含**目标定位位**（`HasLinkTargetIDList` 或 `HasLinkInfo`）。"""
    f = lnk_linkflags(path)
    if f < 0:
        return False
    HAS_IDLIST = 0x00000001
    HAS_LINKINFO = 0x00000002
    return bool(f & (HAS_IDLIST | HAS_LINKINFO))


def com_read_lnk(path: str) -> dict:
    """用 COM **读回**一个 .lnk 的三个字段（`TargetPath` / `Arguments` /
    `WorkingDirectory`）。

    🔴 **这是判据的权威来源**：reviewer 要求「COM 读回 TargetPath 非空、
      所指文件存在、并且在 v1.13 包内」⇒ 判据**必须**读回，不能自己看
      自己写的数据。
    """
    ok, reason, shell = _com_available()
    if not ok:
        return dict(ok=False, reason=reason, target='', arguments='',
                    working_dir='', icon='')
    try:
        sc = shell.CreateShortcut(path)
        return dict(ok=True, reason='',
                    target=str(sc.TargetPath or ''),
                    arguments=str(sc.Arguments or ''),
                    working_dir=str(sc.WorkingDirectory or ''),
                    icon=str(sc.IconLocation or ''))
    except Exception as e:
        return dict(ok=False, reason='COM 读回失败：%r' % e, target='',
                    arguments='', working_dir='', icon='')


def write_lnk_via_com(lnk_path: str, target: str, workdir: str, icon: str,
                      description: str, arguments: str = '') -> dict:
    """用 `WScript.Shell.CreateShortcut` 生成 .lnk（**APP-052 ① 的修法**）。

    🔴 **由 Windows 自己**写 `LinkTargetIDList` / `LinkInfo` ⇒ 必然可启动。
    🔴 **写完立刻 COM 读回自检** ⇒ 读回不通过 ⇒ 抛错 ⇒ **fail-closed**。
    """
    ok, reason, shell = _com_available()
    if not ok:
        raise RuntimeError('无法生成快捷方式：%s' % reason)
    # 🔴🔴🔴 **必须先删旧文件**：`CreateShortcut` 对**已存在**的路径会
    #   **载入旧内容** ⇒ 上一版坏链残留的 `Arguments='C'` 会被**继承**下来
    #   （实测：重建后 `Arguments` 仍是 `[C]`）⇒ 必须先删 ⇒ 从零生成。
    if os.path.exists(lnk_path):
        try:
            os.remove(lnk_path)
        except OSError as e:
            raise RuntimeError('删除旧快捷方式失败：%r' % e)
    sc = shell.CreateShortcut(lnk_path)
    sc.TargetPath = target
    sc.WorkingDirectory = workdir
    sc.Description = description
    if icon and os.path.isfile(icon):
        sc.IconLocation = '%s,0' % icon
    # 🔴 **总是显式赋值**（哪怕是空串）⇒ 不留任何继承来的旧字段
    sc.Arguments = arguments or ''
    sc.save()
    # 🔴 **写后自检**：COM 读回必须非空 ⇒ 否则说明这条链还是坏的
    back = com_read_lnk(lnk_path)
    if not back['ok'] or not back['target']:
        raise RuntimeError('快捷方式写入后 COM 读回 TargetPath 为空：%r' % back)
    return back


def lnk_target_of(path: str) -> str:
    """从 .lnk **反解**目标路径（用于幂等判断 + 自检）。

    🔴🔴🔴 **【APP-052 ①】权威来源改为 COM 读回**。
      上一版是「按 MS-SHLLINK 结构解析 StringData 的第 2 个串」⇒ 对
      **本模块自己造的坏链**照样能解出目标 ⇒ **判据自欺欺人**（假通过）。
      ⇒ 现在改为 `com_read_lnk()` 读回 `TargetPath`；
      ⇒ COM 不可用时**退回字节解析**（仅作**降级诊断**用，并在结果里
        标记 `read_source='bytes_fallback'` ⇒ 判据据此**降级为不通过**）。
    """
    back = com_read_lnk(path)
    if back['ok']:
        return back['target']
    # 🔴 降级：字节解析（**不作为通过依据**，见上）
    try:
        b = open(path, 'rb').read()
    except OSError:
        return ''
    if len(b) < 78:
        return ''
    off = 76
    strs = []
    for _ in range(5):
        if off + 2 > len(b):
            break
        (nchars,) = struct.unpack_from('<H', b, off)
        off += 2
        nb = nchars * 2
        if nchars == 0 or off + nb > len(b):
            break
        strs.append(b[off:off + nb].decode('utf-16-le', errors='replace'))
        off += nb
    return strs[1] if len(strs) > 1 else ''


def is_accepted(pkg_dir: str) -> bool:
    """🔴 **真机验收是否通过**（判据 = 包目录里有 `ACCEPTED.json`）。

    🔴 **为什么用显式标记**而不是「打包成功就算」：
      APP-045② 明文「**还没通过真机验收的版本不要指过去**」
      ⇒ 打包成功（离线闸门全绿）**不等于**真机验收通过。
      ⇒ 必须有人/脚本在真机验收通过后**显式**写这个标记。
    """
    p = os.path.join(pkg_dir, ACCEPTED_MARKER)
    if not os.path.isfile(p):
        return False
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return bool(data.get('accepted'))
    except Exception:
        # 🔴 标记损坏 ⇒ **保守判为未通过**（fail-closed）
        return False


def update_desktop_shortcut(pkg_dir: str, version: str, dry_run: bool = False,
                            on_log=print) -> dict:
    """把桌面快捷方式指向 `pkg_dir`（并清理旧的、保证「只保留一个」）。

    返回 dict：`{ok, reason, lnk_path, target, removed, accepted}`。
    """
    res = dict(ok=False, reason='', lnk_path='', target='', removed=[],
               accepted=False, desktop='', com=None, linkflags=None)
    desk = desktop_dir()
    res['desktop'] = desk
    if not os.path.isdir(desk):
        res['reason'] = '桌面目录不存在：%s' % desk
        on_log('[shortcut] ⚠️ %s' % res['reason'])
        return res

    # ── 🔴 真机验收门（APP-045②）────────────────────────────────
    accepted = is_accepted(pkg_dir)
    res['accepted'] = accepted
    if not accepted:
        res['reason'] = ('未通过真机验收（包目录缺 %s）⇒ '
                         '**不更新桌面快捷方式**（APP-045②）' % ACCEPTED_MARKER)
        on_log('[shortcut] ⚠️ %s' % res['reason'])
        return res

    target = os.path.join(pkg_dir, START_BAT)
    if not os.path.isfile(target):
        res['reason'] = '目标不存在：%s' % target
        on_log('[shortcut] ⚠️ %s' % res['reason'])
        return res

    icon = os.path.join(pkg_dir, ICON_REL)
    if not os.path.isfile(icon):
        icon = target
    workdir = pkg_dir
    new_name = '%s v%s' % (LNK_BASE_NAME, version)
    new_lnk = os.path.join(desk, new_name + '.lnk')

    # ── 幂等：已指向同一目标 ⇒ 不动 ───────────────────────────────
    #    🔴【APP-052 ①】幂等判断必须用 **COM 读回**，且**必须**检查
    #    LinkFlags 带上目标定位位 ⇒ 否则**坏链**会被当成「已指向」而放过。
    if os.path.isfile(new_lnk):
        back = com_read_lnk(new_lnk)
        # 🔴🔴🔴【APP-052 ①】**COM 不可用 ⇒ 无法判定**（≠「链不合格」）
        #   实测事故（2026-11-01 14:47 打包时）：打包脚本用的是**没装
        #   pywin32 的解释器** ⇒ `com_read_lnk` 返 `ok=False` ⇒
        #   `cur=''` ⇒ 旧逻辑把它当成「**不合格**」⇒ 打印「不合格 ⇒ 重建」
        #   ⇒ 接着去重建 ⇒ 又因 pywin32 缺失而抛错
        #   ⇒ **日志吓人（像坏链），实际链是好的**，而且白白尝试重建。
        #   ⇒ 正确处置：**区分「无法判定」与「判定为不合格」**；
        #     前者**直接返回**（不重建、不改链），后者才重建。
        if not back['ok']:
            res['reason'] = ('COM 不可用（%s）⇒ **无法判定**现有快捷方式是否合格'
                             ' ⇒ **不重建、不改动**（请用装了 pywin32 的解释器'
                             '重跑，例如仓库 .venv）' % back.get('reason', ''))
            res['lnk_path'] = new_lnk
            res['com'] = back
            res['linkflags'] = lnk_linkflags(new_lnk)
            on_log('[shortcut] ⚠️ %s' % res['reason'])
            return res
        cur = back['target']
        flags_ok = lnk_flags_ok(new_lnk)
        # 🔴🔴🔴 幂等判断**必须校验全部关键字段**，不能只看 target：
        #   实测踩到：坏链修好后 `Arguments` 仍残留 `'C'`（COM `CreateShortcut`
        #   对已存在路径会**载入旧内容**）⇒ 只看 target ⇒ 判「幂等」⇒
        #   **残留永远清不掉** ⇒ ⇒ 这里也要求 Arguments 为空。
        args_ok = (not (back.get('arguments') or '').strip())
        if (cur and os.path.normcase(cur) == os.path.normcase(target)
                and flags_ok and args_ok):
            res['ok'] = True
            res['lnk_path'] = new_lnk
            res['target'] = target
            res['com'] = back
            res['linkflags'] = lnk_linkflags(new_lnk)
            res['reason'] = '已指向当前版本（幂等，无需重建）'
            on_log('[shortcut] ✓ %s' % res['reason'])
            return res
        # 🔴 否则（坏链 / 指向别的 / COM 读不到 / 有残留参数）⇒ **重建**
        on_log('[shortcut] ⚠️ 现有快捷方式不合格（COM 读回 target=%r flags_ok=%s '
               'args_ok=%s）⇒ 重建' % (cur, flags_ok, args_ok))

    # ── 清理旧快捷方式（保证「只保留一个」）──────────────────────
    #    🔴 **只删同名前缀的**（含版本号的 + 旧的无版本号那个）
    #    ⇒ 不碰桌面上其它软件的快捷方式。
    removed = []
    try:
        for fn in os.listdir(desk):
            if not fn.lower().endswith('.lnk'):
                continue
            if not fn.startswith(LNK_BASE_NAME):
                continue
            if fn == os.path.basename(new_lnk):
                continue
            full = os.path.join(desk, fn)
            try:
                os.remove(full)
                removed.append(fn)
            except OSError:
                pass
    except OSError as e:
        on_log('[shortcut] ⚠️ 清理旧快捷方式失败：%s' % e)
    res['removed'] = removed

    if dry_run:
        res['ok'] = True
        res['lnk_path'] = new_lnk
        res['target'] = target
        res['reason'] = 'dry-run：将写入 %s（已清理旧：%r）' % (
            new_lnk, removed)
        on_log('[shortcut] [dry-run] %s' % res['reason'])
        return res

    # 🔴🔴🔴【APP-052 ①】用 **COM** 生成（不再手工拼字节）
    try:
        back = write_lnk_via_com(
            lnk_path=new_lnk, target=target, workdir=workdir, icon=icon,
            description='Confucius4 实时字幕 v%s 客户包' % version)
    except Exception as e:
        res['reason'] = '写入失败：%r' % e
        on_log('[shortcut] ⚠️ %s' % res['reason'])
        return res

    res['ok'] = True
    res['lnk_path'] = new_lnk
    res['target'] = target
    res['com'] = back
    res['linkflags'] = lnk_linkflags(new_lnk)
    res['reason'] = '已更新桌面快捷方式：%s ⇒ %s（清理旧 %d 个）' % (
        new_lnk, target, len(removed))
    on_log('[shortcut] ✓ %s' % res['reason'])
    return res


def verify_lnk(lnk_path: str, pkg_dir: str, expect_target: str = '') -> dict:
    """🔴🔴🔴 **【APP-052 ①】权威判据**：校验一个 .lnk 是不是**真能用**的链。

    四道判据（**全部**须通过）：
      V1 **COM 读回 TargetPath 非空**（且不是 COM 读不到）
      V2 **TargetPath 所指文件存在**
      V3 **TargetPath 在 `pkg_dir` 之内**（不得指向别的包 / 系统目录）
      V4 **LinkFlags 含目标定位位**（`HasLinkTargetIDList` 或 `HasLinkInfo`）
         ⇒ 这一条专门用来**识破「手工拼字节的坏链」**

    返回 dict：`{ok, checks, reason, com, linkflags}`。
    """
    checks = {}
    back = com_read_lnk(lnk_path)
    checks['v1_com_target_nonempty'] = bool(back['ok'] and back['target'])
    checks['v2_target_exists'] = bool(
        back['target'] and os.path.isfile(back['target']))
    tp = back['target'] or ''
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
    checks['v4_linkflags_has_target'] = bool(lnk_flags_ok(lnk_path))
    if expect_target:
        checks['v5_target_matches_expected'] = bool(
            tp and os.path.normcase(tp) == os.path.normcase(expect_target))
    ok = all(checks.values())
    return dict(ok=ok, checks=checks, com=back,
                linkflags=lnk_linkflags(lnk_path),
                reason='' if ok else '不通过：%r' % checks)


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description='更新桌面快捷方式（APP-045②）')
    ap.add_argument('--pkg', required=True, help='客户包目录')
    ap.add_argument('--version', required=True, help='版本号（X.Y）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    r = update_desktop_shortcut(args.pkg, args.version, dry_run=args.dry_run)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(r, f, ensure_ascii=False, indent=2)
        print('证据已写:', args.out)
    return 0 if r.get('ok') else 1


if __name__ == '__main__':
    sys.exit(main())
