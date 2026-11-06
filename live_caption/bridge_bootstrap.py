r"""bridge_bootstrap.py — 桥接快捷方式的**版本无关启动器**（APP-077 ② / EXT-042）。

## 为什么需要这一层（用户真实故障）
桌面「实时配音桥接服务 v2.1.lnk」把**生成那一刻**的包目录名写死进
TargetPath/Arguments。App 每次升级删旧目录 ⇒ .lnk 指向不存在的
`pythonw.exe` ⇒ Windows 直接弹「找不到文件」，用户看不到任何原因，
且 pythonw **无控制台** ⇒ 桥接自己 print 的日志全部丢失
（EXT-043 B5 实测 `%LOCALAPPDATA%\LiveDubEXT\bridge.log` 停在 10-30）。

## 本文件做的三件事
1. **运行时解析版本目录**（不写死）：枚举 `~/Confucius4_LiveCaption_v*`
   （含 MiniMVP），按语义版本倒序，挑**第一个**同时具备
   `python/pythonw.exe` 与 `ext/bridge/bridge_launcher.py` 的目录。
   ⇒ 桌面 .lnk 只指向本文件（路径里**不含任何版本号**）。
2. **失败弹提示框**：找不到包 / pythonw / launcher / 子进程非零退出
   ⇒ `ctypes.MessageBoxW`（pythonw 下唯一可见的通道），写清原因。
3. **日志写用户目录**：`%LOCALAPPDATA%\LiveDubEXT\bridge.log`
   （追加 + 时间戳 + 轮转），子进程的 stdout/stderr 一并重定向。

## APP-077 ① 的联动（固定 token 不再进包）
`--token-file` 指向 `%LOCALAPPDATA%\LiveDubEXT\bridge_token.txt`。
包内**不带** `bridge_token.txt`（见 `pkg_exclude.BRIDGE_TOKEN_FILE_RE`），
EXT 的 `TokenStore._load_or_create()` 首次启动会在这条路径**随机生成**。

## 铁律
* 🔴 **不改 EXT 交付的任何源文件** —— 本文件是 App 打包侧**新增**适配层。
* 🔴 **不写死版本目录** —— 源码里不得出现 `Confucius4_LiveCaption_v2.x`。
* 🔴 **不 import 被测模块** —— 只做路径解析 + `subprocess` 转交。
* 🔴 桌面 .lnk **只指向本文件**，不动用户正在测试的旧 .lnk（EXT-042②）。
"""
from __future__ import annotations

import ctypes
import datetime
import glob
import os
import re
import subprocess
import sys
import time

HOME = os.path.expanduser('~')
USER_DIR = os.path.join(os.environ.get('LOCALAPPDATA', HOME), 'LiveDubEXT')
LOG_PATH = os.path.join(USER_DIR, 'bridge.log')
TOKEN_PATH = os.path.join(USER_DIR, 'bridge_token.txt')
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_KEEP = 3

#: 包目录名（**只匹配形状，不含具体版本号**）
PKG_GLOB = 'Confucius4_LiveCaption_v*'
MINIMVP_GLOB = 'Confucius4_LiveCaption_MiniMVP_v*'
VER_RE = re.compile(r'v(\d+)(?:\.(\d+))?(?:\.(\d+))?', re.I)

REQUIRED = (
    os.path.join('python', 'pythonw.exe'),
    os.path.join('ext', 'bridge', 'bridge_launcher.py'),
)

#: 用户目录里的**稳定入口**（路径里不含任何版本号）。
#: 打包/安装期把本文件复制到这里，并生成 `bridge_bootstrap.cmd`。
BOOT_DST = os.path.join(USER_DIR, 'bridge_bootstrap.py')
CMD_DST = os.path.join(USER_DIR, 'bridge_bootstrap.cmd')

#: 🔴 `.lnk` 只指向 **系统 cmd.exe**（Windows 自带、永远存在）+ 这条 cmd。
#:    cmd 里**不写死版本目录**：只用通配符「借一个 pythonw 解释器」，
#:    真正的版本选择交给本文件 `resolve_pkg()`（语义版本排序，已自检）。
#:    ⇒ 即使旧包目录被删，.lnk 也不会变成「Windows 找不到文件」。
CMD_TEMPLATE = r'''@echo off
rem APP-077 (2) / EXT-042: version-free bridge entry. No version dir here.
setlocal
set "UD=%LOCALAPPDATA%\LiveDubEXT"
if not exist "%UD%" mkdir "%UD%"
set "LOG=%UD%\bridge.log"
set "BOOT=%UD%\bridge_bootstrap.py"
if not exist "%BOOT%" (
  >>"%LOG%" echo [%date% %time%] bridge_bootstrap.py missing in user dir
  powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('桥接启动器缺失，请重新安装实时字幕 App。','实时配音桥接服务','OK','Error')" >nul 2>&1
  exit /b 2
)
rem Borrow ANY bundled interpreter just to run the version-free launcher.
set "PYW="
for /d %%D in ("%USERPROFILE%\Confucius4_LiveCaption_v*" "%USERPROFILE%\Confucius4_LiveCaption_MiniMVP_v*") do (
  if not defined PYW if exist "%%~fD\python\pythonw.exe" set "PYW=%%~fD\python\pythonw.exe"
)
if not defined PYW (
  >>"%LOG%" echo [%date% %time%] no bundled pythonw found
  powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('未找到实时字幕 App 自带的 Python，请安装/指定 EXT_APP_ROOT。','实时配音桥接服务','OK','Error')" >nul 2>&1
  exit /b 2
)
>>"%LOG%" echo [%date% %time%] bootstrap via %PYW%
"%PYW%" "%BOOT%" >>"%LOG%" 2>&1
exit /b %ERRORLEVEL%
'''


def write_user_launcher() -> dict:
    """打包/安装期调用：把本文件 + 稳定 .cmd 写进用户目录。

    ⚠️ **不写桌面 .lnk**（EXT-042 ② 禁止改用户正在测的 v2.1 .lnk）；
       .lnk 由 v2.3 打包脚本生成，TargetPath 固定为
       `%WINDIR%\\System32\\cmd.exe`，Arguments 为 `/c "<CMD_DST>"`。
    """
    os.makedirs(USER_DIR, exist_ok=True)
    import shutil
    shutil.copy2(os.path.abspath(__file__), BOOT_DST)
    with open(CMD_DST, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(CMD_TEMPLATE)
    return dict(boot=BOOT_DST, cmd=CMD_DST,
                lnk_target=r'%WINDIR%\System32\cmd.exe',
                lnk_args='/c "%s"' % CMD_DST)


def log(msg: str) -> None:
    """写用户目录日志（**不依赖 stdout**：pythonw 下 stdout 可能为 None）。"""
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        if os.path.isfile(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX_BYTES:
            for i in range(LOG_KEEP - 1, 0, -1):
                older = '%s.%d' % (LOG_PATH, i)
                newer = '%s.%d' % (LOG_PATH, i + 1)
                if os.path.isfile(older):
                    if os.path.isfile(newer):
                        os.remove(newer)
                    os.replace(older, newer)
            os.replace(LOG_PATH, LOG_PATH + '.1')
        with open(LOG_PATH, 'a', encoding='utf-8', errors='replace') as f:
            f.write('[%s] %s\n' % (
                datetime.datetime.now().isoformat(timespec='seconds'), msg))
    except Exception:
        pass                       # 日志失败不能反过来让启动器崩掉


def message_box(msg: str, title: str = '实时配音桥接服务') -> None:
    """pythonw 下唯一可见的失败通道（MessageBoxW，MB_ICONERROR=0x10）。"""
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
    except Exception as e:
        log('MessageBoxW 失败：%r' % (e,))


def _ver_key(name: str):
    m = VER_RE.search(name)
    if not m:
        return (-1, -1, -1)
    return tuple(int(x or 0) for x in m.groups()[:3])


def resolve_pkg(search_root: str = HOME):
    """**运行时**枚举最新可用包目录；找不到返回 None（不抛异常）。

    ⚠️ 判据 = 目录名形状 ∧ `pythonw.exe` ∧ `bridge_launcher.py` 三者齐全
       ⇒ 空壳/半成品目录不会被选中（EXT-042③ 的 `_is_complete` 同口径）。
    """
    cands = []
    for pat in (PKG_GLOB, MINIMVP_GLOB):
        cands.extend(glob.glob(os.path.join(search_root, pat)))
    cands = sorted(set(cands), key=lambda p: (_ver_key(os.path.basename(p)),
                                               os.path.basename(p)),
                   reverse=True)
    for d in cands:
        if not os.path.isdir(d):
            continue
        if all(os.path.isfile(os.path.join(d, *r.split('\\'))) for r in REQUIRED):
            return d
    return None


def fail(msg: str) -> int:
    log('启动失败：' + msg)
    message_box(msg)
    return 2


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    log('bootstrap 启动 argv=%r' % (argv,))
    pkg = resolve_pkg()
    if pkg is None:
        return fail('未找到可用的实时字幕 App 目录。\n'
                    '请确认已安装 Confucius4_LiveCaption（含 python\\pythonw.exe '
                    '与 ext\\bridge\\bridge_launcher.py），或设置 EXT_APP_ROOT。')
    pyw = os.path.join(pkg, 'python', 'pythonw.exe')
    launcher = os.path.join(pkg, 'ext', 'bridge', 'bridge_launcher.py')
    if not os.path.isfile(pyw) or not os.path.isfile(launcher):
        return fail('包目录不完整：%s' % pkg)

    os.makedirs(USER_DIR, exist_ok=True)
    # 🔴 APP-077①：token 落用户目录（包内不带固定 token）
    args = [launcher, '--real', '--pipeline', '--target-lang', 'en',
            '--host', '127.0.0.1', '--port', '8765', '--pair-port', '8766',
            '--spk-bypass', '--token-file', TOKEN_PATH]
    # 用户可在 .lnk 里追加参数；已有同名开关不重复
    for a in argv:
        if a not in args:
            args.append(a)
    env = dict(os.environ)
    env.setdefault('PYTHONUTF8', '1')
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env.setdefault('EXT_RELEASE', '1')
    env.setdefault('EXT_APP_ROOT', pkg)
    env.setdefault('EXT_APP_SEARCH_ROOT', pkg)
    env['PYTHONPATH'] = os.pathsep.join(
        [os.path.join(pkg, 'ext', '.runtime_deps'),
         os.path.join(pkg, 'ext'), env.get('PYTHONPATH', '')]).rstrip(os.pathsep)

    log('解析到包目录：%s' % pkg)
    try:
        with open(LOG_PATH, 'a', encoding='utf-8', errors='replace') as lf:
            rc = subprocess.call(
                [pyw] + args, cwd=os.path.join(pkg, 'ext', 'bridge'),
                env=env, stdout=lf, stderr=subprocess.STDOUT)
    except Exception as e:
        return fail('无法启动桥接进程：%r' % (e,))
    log('桥接退出 rc=%d' % rc)
    if rc != 0:
        return fail('桥接服务启动失败（退出码 %d）。\n'
                    '常见原因：8765 端口被占用、实时字幕 App 正在运行'
                    '（设备互斥）、或模型未就绪。详见 %s' % (rc, LOG_PATH))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
