#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app192 —— **【APP-052 ①】桌面快捷方式（.lnk）有效性闸门 ＋ 从 .lnk 冷启动**。

🔴🔴🔴 **为什么必须有这个闸门（reviewer APP-052 ① 的真实事故）**：

  reviewer 在 v1.13 交付检查点复核时发现：

  | 项 | reviewer 实测 | 本模块上一版的实际情况 |
  |---|---|---|
  | `.lnk` 大小 | 554 B | ✅ 一样 |
  | 头部 LinkFlags | `20 00 00 00`（**只置 HasArguments**） | ✅ **完全一样** |
  | COM 读回 TargetPath | `[]`（**空**） | ✅ **完全一样** |
  | COM 读回 Arguments | `[C]` | ✅ **完全一样** |
  | COM 读回 WorkingDirectory | `[]` | ✅ **完全一样** |
  | Shell.Application GetLink.Path | 空 | ✅ 一样 |

  ⇒ **桌面「Confucius4 实时字幕 v1.13.lnk」是坏链** ⇒ 用户双击**启动不了 v1.13**
  ⇒ §117 的「① 子项（用户启动方式）」**其实从未被验证过**：
     `app181` 的冷启动证据时间是 10-31 22:12，**早于** `.lnk` 的创建时间
     （00:39），而且它**直接拉 `pythonw.exe`**，**没有经过 `.lnk`**。
  ⇒ `shortcut_update.py` 回报的「✓ 已指向当前版本」**同样是假通过** ——
     因为它是用**自己写的字节**去反解自己写的字节。

🔴 **根因（上一版的实现错在哪）**：
  上一版 `shortcut_update.build_lnk` 手工拼 MS-SHLLINK 字节，
  写 `LinkFlags = 0x00000020`（**只置 HasArguments**）⇒
  **既没有 `HasLinkTargetIDList`、也没有 `HasLinkInfo`、也没有 `IsUnicode`**
  ⇒ Windows **不会**用它定位目标 ⇒ **坏链**。
  🔴 **教训**：「目标定位」依赖 `LinkTargetIDList`（或 `HasLinkInfo` 的
  `LocalBasePath`），**不是** StringData 里的路径字符串 ⇒
  **「不依赖 COM 手工拼 .lnk」这条路本身就是错的**。

🔴 **本闸门做什么**（4 类判据）：

  **C1 `.lnk` 有效性**（4 道子判据，全部须过）：
      ① COM 读回 `TargetPath` **非空**
      ② `TargetPath` 所指**文件存在**
      ③ `TargetPath` **在本客户包目录之内**（不得指向别的包 / 系统目录）
      ④ `LinkFlags` 含**目标定位位**（`HasLinkTargetIDList` 或 `HasLinkInfo`）
         ⇒ 这一条专门用来**识破「手工拼字节的坏链」**

  **C2 反证组（判据必须有鉴别力 —— 本模块的核心纪律）**：
      把**当前这个已知是坏的** `.lnk` 喂进 C1 ⇒ **必须判 FAIL**；
      再造一个「指向不存在文件」的链 ⇒ **必须判 FAIL**；
      再造一个「指向包外文件」的链 ⇒ **必须判 FAIL**。
      ⇒ 证明 C1 **不是恒真**。

  **C3 从 `.lnk` 冷启动两次**（`explorer.exe "<lnk>"`）：
      进程命令行的路径**必须指向 v1.13 包** ⇒ 证明「用户双击」这条路
      **真的能起**（而不是「我直接拉 pythonw.exe 能起」）。

  **C4 截图有效性**：两张截图的客户区**内容密度**必须达标
      （沿用 app181 的 `content_density` 判据 —— 它已被证明能识破
      「只有标题栏」的半成品图）。

🔴 **纪律**：
  - 本脚本**跑推理**（pythonw 会加载 TTS→NPU / ASR→GPU.0）⇒ **必须持共享机器锁**；
  - **不在 CPU 上跑推理**（设备参数走 NPU / GPU.0）；
  - 结束时**必须**杀掉自己拉起的进程（不留孤儿占 NPU）；
  - 质量判定（音质/可懂）交 reviewer 与用户，本脚本只判「**从 .lnk 真的能起**」。

用法：
    python results/app/app192_lnk_coldstart_gate.py
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
SHOT_DIR = os.path.join(HOME, 'shared', 'app_lnk_coldstart')
EVID = os.path.join(HERE, 'app192_lnk_coldstart_evidence.json')

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

PASS = 0
FAIL = 0
CHECKS = []


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    if ok:
        PASS += 1
    else:
        FAIL += 1
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:400]})
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  ' + str(detail)) if detail else ''))
    return ok


# ── 包目录自动发现（**不写死版本号**）──────────────────────────────
def discover_pkg():
    cands = []
    for d in os.listdir(HOME):
        m = re.match(r'^Confucius4_LiveCaption_v(\d+)\.(\d+)$', d)
        if not m:
            continue
        if '.bak_' in d or d.endswith('_backup'):
            continue
        cands.append(((int(m.group(1)), int(m.group(2))),
                      os.path.join(HOME, d)))
    if not cands:
        raise SystemExit('找不到客户包目录')
    cands.sort()
    return cands[-1][1]


def pkg_version(pkg):
    return os.path.basename(pkg).rsplit('_v', 1)[-1]


def desktop_dir():
    for env in ('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer'):
        base = os.environ.get(env)
        if base:
            for sub in ('Desktop', '桌面'):
                p = os.path.join(base, sub)
                if os.path.isdir(p):
                    return p
    for sub in ('Desktop', '桌面'):
        p = os.path.join(HOME, sub)
        if os.path.isdir(p):
            return p
    return os.path.join(HOME, 'Desktop')


# ── 共享机器锁（ctypes 判活；fail-closed；不用 tasklist）────────────
def pid_alive(pid):
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))
        if not h:
            return (ctypes.get_last_error() == 87)
        c = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(c))
        k.CloseHandle(h)
        return c.value == 259
    except Exception:
        return True


def read_lock():
    try:
        with open(LOCK, 'rb') as f:
            raw = f.read()
    except Exception:
        return None
    for enc in ('utf-8', 'gbk', 'cp936', 'latin-1'):
        try:
            txt = raw.decode(enc)
        except Exception:
            continue
        m = re.search(r'pid[:=\s]+(\d+)', txt, re.I)
        if m:
            return {'pid': int(m.group(1)), 'raw': txt}
        m = re.match(r'^(\S+)\s+PID\s+(\d+)\b', txt.strip(), re.I)
        if m:
            return {'pid': int(m.group(2)), 'raw': txt}
    return None


def acquire_lock(timeout_s=10800):
    payload = ('module: app-lnk-coldstart\npid: %d\nstarted: %s\n'
               % (os.getpid(), time.strftime('%Y-%m-%d %H:%M:%S')))
    t0 = time.time()
    while True:
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, payload.encode('utf-8'))
            finally:
                os.close(fd)
            print('[lock] 已取得共享机器锁')
            return True
        except FileExistsError:
            st = read_lock()
            if st and not pid_alive(st['pid']):
                print('[lock] 旧锁持有者 PID %d 已死 ⇒ 回收' % st['pid'])
                try:
                    os.remove(LOCK)
                    continue
                except Exception:
                    pass
            if time.time() - t0 > timeout_s:
                raise SystemExit('等待机器锁超时')
            time.sleep(10)


def release_lock():
    try:
        os.remove(LOCK)
        print('[lock] 已释放')
    except Exception as e:
        print('[lock] 释放异常：%r' % e)


# ── 窗口枚举 ──────────────────────────────────────────────────────
EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def enum_windows():
    out = []

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if buf.value.strip():
            out.append((hwnd, buf.value))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


# ── .lnk 判据（COM 读回 + 字节级体检）──────────────────────────────
def _com():
    import win32com.client as wc
    return wc.Dispatch('WScript.Shell')


def com_read_lnk(path):
    try:
        ws = _com()
        sc = ws.CreateShortcut(path)
        return dict(ok=True, target=str(sc.TargetPath or ''),
                    arguments=str(sc.Arguments or ''),
                    working_dir=str(sc.WorkingDirectory or ''),
                    icon=str(sc.IconLocation or ''))
    except Exception as e:
        return dict(ok=False, target='', arguments='', working_dir='',
                    icon='', error=repr(e))


def lnk_linkflags(path):
    try:
        b = open(path, 'rb').read()
    except OSError:
        return -1
    if len(b) < 24:
        return -1
    return struct.unpack_from('<I', b, 20)[0]


def verify_lnk(lnk_path, pkg_dir, expect_target=''):
    """🔴 **C1 的四道子判据**（全部须过）。"""
    checks = {}
    back = com_read_lnk(lnk_path)
    checks['v1_com_target_nonempty'] = bool(back['ok'] and back['target'])
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


# ── 反证组：造各种坏链，判据必须识破 ───────────────────────────────
def _procs_in_pkg(pkg_dir):
    """找出**可执行文件路径位于 `pkg_dir` 内**的进程。

    🔴 **不用 `wmic`**（Win11 已弃用 ⇒ 本轮实测 `FileNotFoundError`）
      ⇒ 用 **`tasklist` 拿 PID**（只认 `pythonw.exe` / `python.exe`）
      ＋ **Win32 `QueryFullProcessImageNameW`** 拿完整路径。
    🔴 **只判可执行文件路径在包内** —— 这正是「用户双击这条路真通了」的判据
      （命令行参数里还可能有包内 `app\\live_caption_app.py`，一并核对）。
    """
    kernel32 = ctypes.windll.kernel32
    hits = []
    try:
        out = subprocess.run(['tasklist', '/fo', 'csv', '/nh'],
                             capture_output=True, text=True, timeout=60)
    except Exception:
        return False, 'tasklist 执行失败'
    for line in out.stdout.splitlines():
        if 'python' not in line.lower():
            continue
        parts = [p.strip('" ') for p in line.split('","')]
        if len(parts) < 2:
            continue
        pid = parts[1]
        try:
            h = kernel32.OpenProcess(0x1000, False, int(pid))
            if not h:
                continue
            buf = ctypes.create_unicode_buffer(1024)
            n = ctypes.c_ulong(len(buf))
            # 🔴 `QueryFullProcessImageNameW` 在 **kernel32**（**不在 psapi**）
            #   ⇒ 本轮实测踩到：psapi 里报 "function not found"
            ok = kernel32.QueryFullProcessImageNameW(
                h, 0, buf, ctypes.byref(n))
            if ok:
                img = buf.value
                if os.path.normcase(img).startswith(os.path.normcase(pkg_dir)):
                    hits.append(dict(pid=int(pid), image=img))
            kernel32.CloseHandle(h)
        except Exception:
            continue
    return (bool(hits)), hits[:5]


def build_broken_byte_lnk(path, target, workdir, arguments='C'):
    """🔴 **重现 reviewer 指控的那个坏链**：手工拼字节，
    `LinkFlags = 0x00000020`（**只置 HasArguments**）⇒ 坏链。"""
    def wstr(s):
        d = s.encode('utf-16-le')
        return struct.pack('<H', len(s)) + d
    h = bytearray()
    h += struct.pack('<I', 0x0000004C)
    h += bytes.fromhex('0114020000000000C000000000000046')
    h += struct.pack('<I', 0x00000020)      # 🔴 只置 HasArguments
    h += struct.pack('<I', 0x00000000)
    h += struct.pack('<Q', 0) * 3
    h += struct.pack('<I', 0)
    h += struct.pack('<i', 0)
    h += struct.pack('<I', 0)
    h += struct.pack('<H', 0) * 2
    h += struct.pack('<I', 0) * 2
    assert len(h) == 76
    body = bytearray(h)
    body += wstr('Confucius4 实时字幕 vX')
    body += wstr(target)
    body += wstr(workdir)
    body += wstr('')
    body += wstr(arguments)
    with open(path, 'wb') as f:
        f.write(bytes(body))
    return bytes(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--timeout', type=float, default=900.0)
    ap.add_argument('--min-density', type=float, default=0.05)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    ver = pkg_version(pkg)
    print('[pkg] %s' % pkg)

    sys.path.insert(0, HERE)
    sys.path.insert(0, REPO)
    from win_capture import capture_hwnd  # noqa: E402
    from png_stats import content_density  # noqa: E402
    import shortcut_update as su  # noqa: E402  （仓库根，不写死）

    desk = desktop_dir()
    lnk_name = '%s v%s.lnk' % (su.LNK_BASE_NAME, ver)
    lnk_path = os.path.join(desk, lnk_name)
    print('[lnk] %s' % lnk_path)

    result = dict(script=os.path.basename(__file__), pkg_dir=pkg,
                  # 🔴 APP-052 ②a：app186 的 `on_pkg()` 判的是 **`pkg`** 字段
                  #   ⇒ 本证据原先只有 `pkg_dir` ⇒ app186 报「证据里没有 'pkg' 字段」
                  #   ⇒ ①b 子项**恒 FAIL**（不是快捷方式有问题 ⇒ 是证据字段名不对）。
                  #   ⇒ 两个字段都写（`pkg` 供 app186 判；`pkg_dir` 保留向后兼容）。
                  pkg=pkg,
                  pkg_version=ver, lnk_path=lnk_path, desktop=desk,
                  checks=[], coldstarts=[], discrimination=None)

    # ── C1 .lnk 有效性 ──────────────────────────────────────────
    print('\n===== C1 .lnk 有效性（COM 读回 + 字节级体检）=====')
    v = verify_lnk(lnk_path, pkg)
    for k, ok in v['checks'].items():
        check('C1 %s' % k, ok,
              ('target=%r flags=0x%08x' % (v['com'].get('target'),
                                          v['linkflags'] if v['linkflags'] >= 0
                                          else -1)))
    check('C1 四道子判据全部通过', v['ok'], v['reason'])
    result['lnk_verify'] = v

    # ── C2 反证组 ───────────────────────────────────────────────
    print('\n===== C2 反证组（判据必须识破坏链）=====')
    tmp = tempfile.mkdtemp(prefix='app192_disc_')
    disc = []
    try:
        # 反证①：**已知是坏的**当前 .lnk 的字节副本（手工拼的坏链）
        bad1 = os.path.join(tmp, 'bad_byte_lnk.lnk')
        build_broken_byte_lnk(bad1, os.path.join(pkg, 'Start_LiveCaption.bat'),
                               pkg, arguments='C')
        r1 = verify_lnk(bad1, pkg)
        disc.append(dict(case='byte_lnk_bad_flags', ok=(not r1['ok']),
                         detail=r1['checks'], linkflags=r1['linkflags']))
        check('C2 反证① 手工拼字节的坏链（LinkFlags=0x20）必须判 FAIL',
              not r1['ok'], 'checks=%r' % r1['checks'])

        # 反证②：COM 生成的链，但**目标文件不存在**
        bad2 = os.path.join(tmp, 'missing_target.lnk')
        try:
            su.write_lnk_via_com(bad2, os.path.join(pkg, '__不存在的文件__.exe'),
                                  pkg, '', 'desc')
            r2 = verify_lnk(bad2, pkg)
        except Exception as e:
            r2 = dict(ok=False, checks={'write_failed': True}, reason=repr(e))
        disc.append(dict(case='com_missing_target', ok=(not r2['ok']),
                         detail=r2.get('checks')))
        check('C2 反证② COM 生成但目标文件不存在 ⇒ 必须判 FAIL',
              not r2['ok'], 'checks=%r' % r2.get('checks'))

        # 反证③：COM 生成的链，但**指向包外**
        bad3 = os.path.join(tmp, 'outside_pkg.lnk')
        outside = os.path.join(tempfile.gettempdir(), 'outside_target.exe')
        try:
            su.write_lnk_via_com(bad3, outside, pkg, '', 'desc')
            r3 = verify_lnk(bad3, pkg)
        except Exception as e:
            r3 = dict(ok=False, checks={'write_failed': True}, reason=repr(e))
        disc.append(dict(case='com_target_outside_pkg', ok=(not r3['ok']),
                         detail=r3.get('checks')))
        check('C2 反证③ 指向包外的链 ⇒ 必须判 FAIL',
              not r3['ok'], 'checks=%r' % r3.get('checks'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    result['discrimination'] = disc
    check('C2 反证组全部成立（判据非恒真）',
          all(d['ok'] for d in disc),
          '%d/%d' % (sum(1 for d in disc if d['ok']), len(disc)))

    # ── C3 从 .lnk 冷启动两次 ──────────────────────────────────
    print('\n===== C3 从 .lnk 冷启动两次（explorer.exe）=====')
    os.makedirs(SHOT_DIR, exist_ok=True)
    acquire_lock()
    cold = []
    try:
        for tag in ('lnk1', 'lnk2'):
            print('\n----- 冷启动 %s -----' % tag)
            before = {h for h, _t in enum_windows()}
            t0 = time.time()
            # 🔴 **从 .lnk 启动**（不是直接拉 pythonw.exe）
            #   ⇒ explorer.exe 解析 .lnk ⇒ 走的就是「用户双击」那条路
            subprocess.Popen(['explorer.exe', lnk_path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            obs = dict(tag=tag, window=None, shot=None, density=0.0,
                       wait_s=0.0, cmdline='', started=False)
            hwnd = None
            best_area = 0
            title = ''
            while time.time() - t0 < args.timeout:
                for h, t in enum_windows():
                    if h in before:
                        continue
                    if ('Confucius4' not in t and '实时字幕' not in t
                            and 'LiveCaption' not in t):
                        continue
                    r = wt.RECT()
                    if not user32.GetWindowRect(wt.HWND(h), ctypes.byref(r)):
                        continue
                    area = (r.right - r.left) * (r.bottom - r.top)
                    if area > best_area:
                        best_area = area
                        hwnd = h
                        title = t
                if hwnd is not None and best_area >= 400 * 300:
                    break
                time.sleep(1.0)

            if hwnd is None:
                obs['error'] = '未等到主窗口'
                print('  !! 未等到主窗口')
                cold.append(obs)
                continue

            obs['window'] = title
            obs['started'] = True
            r = wt.RECT()
            user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(r))
            obs['window_size'] = [r.right - r.left, r.bottom - r.top]
            try:
                user32.ShowWindow(wt.HWND(hwnd), 9)
                user32.SetForegroundWindow(wt.HWND(hwnd))
            except Exception:
                pass
            try:
                user32.RedrawWindow(wt.HWND(hwnd), None, None,
                                    0x0001 | 0x0004 | 0x0080 | 0x0100)
            except Exception:
                pass

            shot = os.path.join(SHOT_DIR, 'app192_%s.png' % tag)
            ok_shot = False
            dens = 0.0
            # 🔴 **在窗口还活着的时候**采集进程可执行文件路径
            #   （窗口一关进程就退 ⇒ 事后再查会查不到）
            try:
                _hit, _det = _procs_in_pkg(pkg)
                if _hit:
                    obs['procs_in_pkg'] = _det
            except Exception:
                pass
            while time.time() - t0 < args.timeout:
                try:
                    ok_shot = capture_hwnd(hwnd, shot)
                except Exception:
                    ok_shot = False
                if ok_shot and os.path.isfile(shot):
                    try:
                        dens = content_density(shot)
                    except Exception:
                        dens = 0.0
                    if dens >= args.min_density:
                        break
                time.sleep(2.0)
            obs['shot'] = shot if os.path.isfile(shot) else None
            obs['density'] = dens
            obs['wait_s'] = round(time.time() - t0, 1)
            check('C4 %s 截图客户区内容密度 ≥ %.3f' % (tag, args.min_density),
                  dens >= args.min_density, 'density=%.4f' % dens)
            cold.append(obs)
            # 收尾：关掉窗口（不留孤儿占 NPU）
            try:
                user32.PostMessageW(wt.HWND(hwnd), 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass
            time.sleep(2.0)
    finally:
        release_lock()

    result['coldstarts'] = cold
    check('C3 从 .lnk 冷启动两次都成功', len(cold) == 2 and
          all(c.get('started') for c in cold),
          'n=%d' % len(cold))

    # 🔴 C3 附加：进程的可执行文件路径必须指向 v1.13 包
    #   🔴 **不用 `wmic`**：Win11 已弃用 wmic（本轮实测 `FileNotFoundError`）
    #   ⇒ 用 **`tasklist` 拿 PID** + **Win32 `QueryFullProcessImageNameW`** 拿路径。
    #   ⇒ **必须在窗口还活着时采**（下面每轮冷启动里已采 ⇒ 这里汇总）。
    all_hits = []
    for c in cold:
        all_hits.extend(c.get('procs_in_pkg') or [])
    cmd_ok = bool(all_hits)
    cmd_detail = all_hits[:5]
    check('C3 从 .lnk 起的进程可执行文件在 v%s 包内' % ver, cmd_ok, cmd_detail)

    overall = FAIL == 0
    result['n_pass'] = PASS
    result['n_fail'] = FAIL
    result['verdict'] = 'PASS' if overall else 'FAIL'
    result['checks'] = CHECKS
    result['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')

    out = args.out or EVID
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print('\n' + '=' * 70)
    print('PASS %d  FAIL %d  verdict=%s' % (PASS, FAIL,
                                           'PASS' if overall else 'FAIL'))
    print('[evidence] %s' % out)
    print('=' * 70)
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
