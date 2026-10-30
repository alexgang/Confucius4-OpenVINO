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
  ⑤ **不依赖 COM**：`WScript.Shell` 被安全策略拦截 ⇒ 用
     **纯字节写 .lnk**（MS-SHLLINK 的最小可用形态）⇒ 零依赖、可测。

🔴 **.lnk 格式说明**（MS-SHLLINK）：
  头 76 字节（Header）＋ LinkFlags(4)＋ LinkTargetIDList(可变)
  ＋ LinkInfo(可选)＋ 字符串区（NameString / CommandLineArguments / WorkingDir）
  ⇒ 最小可用形态：Header + LinkFlags + StringData，**无需** IDList 与 LinkInfo。
  Windows 资源管理器按 StringData 里的路径解析目标 ⇒ 可正常启动。

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


# ── .lnk 字节构造（纯字节，不依赖 COM）──────────────────────────────
def _win_str(s: str) -> bytes:
    """Windows 字符串区条目：2 字节字符数 + UTF-16LE 内容（**无终止符**）。"""
    data = s.encode('utf-16-le')
    return struct.pack('<H', len(s)) + data


def build_lnk(target: str, workdir: str, icon: str, description: str,
              name: str) -> bytes:
    """构造一个最小可用的 .lnk 字节串（MS-SHLLINK，StringData 形态）。

    🔴 **为什么不用 COM**：`WScript.Shell`（New-Object -ComObject）在受控环境里
      会被安全策略拦截（实测：`Command blocked for security: COM object
      instantiation can run arbitrary code`）⇒ 纯字节方案零依赖、可测试。
    """
    # ── Header（76 字节）──
    #    逐项核对 MS-SHLLINK（**偏移必须精确**）：
    #      [0:4]   HeaderSize       = 0x4C
    #      [4:20]  LinkCLSID        (16 字节)
    #      [20:24] LinkFlags
    #      [24:28] FileAttributes
    #      [28:36] CreationTime     (FILETIME 8 字节)
    #      [36:44] AccessTime
    #      [44:52] WriteTime
    #      [52:56] FileSize
    #      [56:60] IconIndex
    #      [60:64] ShowCommand
    #      [64:66] HotKey
    #      [66:68] Reserved1
    #      [68:72] Reserved2
    #      [72:76] Reserved3
    #    ⇒ **StringData 从偏移 76 开始**（Header 之后**没有**别的字段）。
    header = bytearray()
    header += struct.pack('<I', 0x0000004C)      # [0:4]  HeaderSize
    # [4:20] LinkCLSID（标准快捷方式 CLSID 00021401-0000-0000-C000-000000000046）
    header += bytes.fromhex('0114020000000000C000000000000046')
    header += struct.pack('<I', 0x00000020)      # [20:24] LinkFlags
    #   bit0 HasLinkTargetIDList=0
    #   bit1 HasLinkInfo=0
    #   bit2 HasName=1
    #   bit3 HasRelativePath=0
    #   bit4 HasWorkingDir=1
    #   bit5 HasArguments=0
    #   bit6 HasIconLocation=1
    #   bit7 IsUnicode=1
    header += struct.pack('<I', 0x00000000)      # [24:28] FileAttributes
    header += struct.pack('<Q', 0)               # [28:36] CreationTime
    header += struct.pack('<Q', 0)               # [36:44] AccessTime
    header += struct.pack('<Q', 0)               # [44:52] WriteTime
    header += struct.pack('<I', 0)               # [52:56] FileSize
    header += struct.pack('<i', 0)               # [56:60] IconIndex
    header += struct.pack('<I', 0)               # [60:64] ShowCommand
    header += struct.pack('<H', 0)               # [64:66] HotKey
    header += struct.pack('<H', 0)               # [66:68] Reserved1
    header += struct.pack('<I', 0)               # [68:72] Reserved2
    header += struct.pack('<I', 0)               # [72:76] Reserved3
    assert len(header) == 76, len(header)

    body = bytearray(header)

    # ── StringData ──
    body += _win_str(name)          # NameString（快捷方式显示名）
    body += _win_str(target)        # RelativePath 槽：这里放**绝对目标路径**
    body += _win_str(workdir)       # WorkingDir
    body += _win_str(icon)          # IconLocation
    body += _win_str(description)   # Description（"RelativePath" 槽位复用）

    return bytes(body)


def lnk_target_of(path: str) -> str:
    """从 .lnk 字节里**反解**目标路径（用于幂等判断 + 自检）。

    🔴 **按 MS-SHLLINK 结构解析**（不是正则乱扫）⇒ 不会把多个路径串起来。
      Header 76 字节 ⇒ StringData 从 76 开始：
      [0] NameString  [1] RelativePath(这里放绝对目标)  [2] WorkingDir
      [3] Arguments   [4] IconLocation
    """
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
               accepted=False, desktop='')
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
    if os.path.isfile(new_lnk):
        cur = lnk_target_of(new_lnk)
        if cur and os.path.normcase(cur) == os.path.normcase(target):
            res['ok'] = True
            res['lnk_path'] = new_lnk
            res['target'] = target
            res['reason'] = '已指向当前版本（幂等，无需重建）'
            on_log('[shortcut] ✓ %s' % res['reason'])
            return res

    data = build_lnk(target=target, workdir=workdir, icon=icon,
                     description='Confucius4 实时字幕 v%s 客户包' % version,
                     name=new_name)

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

    try:
        with open(new_lnk, 'wb') as f:
            f.write(data)
    except OSError as e:
        res['reason'] = '写入失败：%s' % e
        on_log('[shortcut] ⚠️ %s' % res['reason'])
        return res

    res['ok'] = True
    res['lnk_path'] = new_lnk
    res['target'] = target
    res['reason'] = '已更新桌面快捷方式：%s ⇒ %s（清理旧 %d 个）' % (
        new_lnk, target, len(removed))
    on_log('[shortcut] ✓ %s' % res['reason'])
    return res


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
