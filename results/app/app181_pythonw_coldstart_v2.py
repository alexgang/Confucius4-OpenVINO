#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app181 —— APP-051② **pythonw 冷启动截图重抓**（修 app178 的「假通过」）。

🔴🔴🔴 **为什么必须重抓（app180 抓出的真缺陷）**：
  `app178` 的判据是「整图色彩数 ≥ 8 ⇒ 不是空白」，实测**恒真**：
    - `app178_cold1.png` 整图色彩数 = **66**，但那 66 种颜色
      **全部来自标题栏**（边框 + 标题文字 + 按钮）⇒ **客户区一个像素都没有**；
    - 人眼复核：只见标题栏，无任何控件。
  ⇒ 那张图**不能**作为「pythonw 冷启动 ⇒ GUI 正常渲染」的证据。

🔴 **本脚本的修正（两条）**：
  ① **判据换成「客户区色彩数」**（裁掉顶部 34 px 标题栏后统计）
     ⇒ 空客户区 = 2 种色（边框色 + 底色）；真内容 = 几十上百种色；
     ⇒ 有鉴别力（不是恒真）。
  ② **等待条件改为「客户区真的有内容」**：
     `app178` 只等到「窗口出现（面积 ≥ 400×300）」就抓 ⇒ 那时 Tk **刚建完
     toplevel、控件还没绘制**（模型还在加载）⇒ 抓到空客户区。
     本脚本：窗口出现后**持续重抓**，直到
       **客户区色彩数 ≥ 阈值** 或 **超时**（默认 420 s，覆盖模型冷加载）。
     ⇒ 抓到的是「模型加载完、控件已绘制」的图。

🔴 **反证组（判据必须有鉴别力）**：
  R1：对**已知有缺陷**的 `app178_cold1.png` 跑新判据 ⇒ 必须判「空白」；
  R2：对**已知有内容**的 `app048_layout_1920x1080.png` 跑新判据 ⇒ 必须判「有内容」；
  ⇒ 证明新判据不是「一律判空」也不是「一律判有」。

🔴 **纪律**：
  - 本脚本**跑推理**（pythonw 会加载 TTS→NPU / ASR→GPU.0）⇒ **必须持共享机器锁**；
  - **不在 CPU 上跑推理**（设备参数走 NPU / GPU.0）；
  - 结束时**必须**杀掉自己拉起的进程（不留孤儿占 NPU）；
  - 质量判定（音质/可懂）交 reviewer 与用户，本脚本只判「GUI 真渲染出来 + 截图有效」。

用法：
    python results/app/app181_pythonw_coldstart_v2.py
"""
from __future__ import annotations

import argparse
import ast
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = r'C:\Users\Trekker-PTL'
LOCK = os.path.join(HOME, 'shared', 'MACHINE_LOCK')
SHOT_DIR = os.path.join(HOME, 'shared', 'app_pythonw_coldstart_v2')
EVID = os.path.join(HERE, 'app181_pythonw_coldstart_v2_evidence.json')

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


# ── 包目录自动发现（**不写死版本号**；排除 .bak_* / *_backup）────────
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


# ── 共享机器锁（ctypes 判活；fail-closed；不用 tasklist）────────────
def pid_alive(pid):
    try:
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))
        if not h:
            return (ctypes.get_last_error() == 87)  # 87 ⇒ PID 确定不存在
        c = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(c))
        k.CloseHandle(h)
        return c.value == 259
    except Exception:
        return True  # 探测失败 ⇒ 视为存活（fail-closed）


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
    payload = ('module: app-coldstart\npid: %d\nstarted: %s\nhost: LAPTOP-0GDQGD3I\n'
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
        title = buf.value
        if title.strip():
            out.append((hwnd, title))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def client_n_colors(path, title_h=34):
    """客户区（裁掉标题栏）色彩数 —— 空客户区 ≈ 2，真内容 ≫ 10。

    🔴🔴🔴 **纯 stdlib**（不用 PIL）：app181 第一版用 PIL 分析 ⇒
      把**包内 3.12 的 site-packages** 加进**系统 3.13** 的 sys.path
      ⇒ `from PIL import Image` 加载的是 3.12 编译的 C 扩展 `_imaging`
      ⇒ `ImportError: cannot import name '_imaging'` ⇒ 抓图全废
      ⇒ 改用 `png_stats`（纯 zlib+struct）⇒ **任何解释器都能跑**。
    """
    from png_stats import client_color_stats
    return client_color_stats(path, title_h=title_h)


def content_density(path, title_h=34):
    """🔴🔴🔴 **客户区「非背景像素密度」**（去 2 px 边框）—— 真正有鉴别力的判据。

    🔴 **为什么「色彩数 ≥ 8」仍不够**（app181 第二版实测）：
      第一版抓到的图 `client_n_colors` = 54 / 95 ⇒ 判据 PASS，
      **但人眼复核只见标题 + 一行「集显: 编码器 INT8 + 解码器 INT8」**
      ⇒ **三分区控件根本没画出来** ⇒ 又是**静默假通过**！
      ⇒ 真因：Tk **事件循环还没跑**（模型还在加载）⇒ 控件未布局。
      ⇒ 判据换成**密度**（好图 0.32~0.48 / 坏图 0.018~0.021 ⇒ 差 15 倍）
      ⇒ 等待条件也换成「密度达标」。
    """
    from png_stats import content_density as _cd
    return _cd(path, title_h=title_h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pkg', default=None)
    ap.add_argument('--timeout', type=float, default=900.0)
    ap.add_argument('--min-client-colors', type=int, default=8)
    ap.add_argument('--min-density', type=float, default=0.05)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()

    pkg = args.pkg or discover_pkg()
    ver = pkg_version(pkg)
    print('[pkg] %s' % pkg)

    pyw = os.path.join(pkg, 'python', 'pythonw.exe')
    app_py = os.path.join(pkg, 'app', 'live_caption_app.py')
    if not os.path.isfile(pyw):
        raise SystemExit('找不到 pythonw：%s' % pyw)

    # 🔴 `capture_hwnd` 现在**纯 stdlib 落盘**（win_capture 已改）
    #   ⇒ **不需要**把包内 site-packages 加进 path
    #   （加了反而会加载 3.12 编译的 PIL C 扩展 ⇒ 在 3.13 上 ImportError）
    sys.path.insert(0, HERE)
    from win_capture import capture_hwnd  # noqa: E402

    os.makedirs(SHOT_DIR, exist_ok=True)

    acquire_lock()
    obs_list = []
    try:
        for tag in ('cold1', 'cold2'):
            print('\n===== 冷启动 %s =====' % tag)
            env = dict(os.environ)
            env['PYTHONPATH'] = ''
            env['PYTHONHOME'] = ''
            env['PYTHONNOUSERSITE'] = '1'
            env['PYTHONUTF8'] = '1'

            before = {h for h, _t in enum_windows()}
            t0 = time.time()
            proc = subprocess.Popen([pyw, '-s', app_py],
                                    cwd=os.path.join(pkg, 'app'), env=env,
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            obs = {'tag': tag, 'pid': proc.pid, 'window': None, 'shot': None,
                   'client_n_colors': 0, 'wait_s': 0.0, 'rc': None,
                   'attempts': []}

            hwnd = None
            best_area = 0
            title = ''
            # 阶段一：等窗口出现
            while time.time() - t0 < args.timeout:
                if proc.poll() is not None:
                    obs['rc'] = proc.returncode
                    break
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

            if hwnd is not None:
                obs['window'] = title
                r = wt.RECT()
                user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(r))
                obs['window_size'] = [r.right - r.left, r.bottom - r.top]

            if hwnd is None:
                obs['error'] = '未等到主窗口（rc=%r）' % obs.get('rc')
                print('  !! 未等到主窗口')
                obs_list.append(obs)
                try:
                    proc.terminate()
                    proc.wait(timeout=15)
                except Exception:
                    pass
                continue

            # 置前台 + 强制重绘
            try:
                user32.ShowWindow(wt.HWND(hwnd), 9)      # SW_RESTORE
                user32.SetForegroundWindow(wt.HWND(hwnd))
            except Exception:
                pass
            try:
                user32.RedrawWindow(wt.HWND(hwnd), None, None,
                                    0x0001 | 0x0004 | 0x0080 | 0x0100)
            except Exception:
                pass

            # 阶段二：**持续重抓**直到客户区**密度**达标（覆盖模型冷加载）
            #   🔴 判据从「色彩数」换成「密度」：色彩数 ≥8 会被「只画了几行字」
            #      的半成品骗过（app181 第二版实测：54/95 色 ⇒ PASS 但人眼
            #      只看到标题 + 一行设备提示 ⇒ 三分区控件根本没画出来）。
            shot = os.path.join(SHOT_DIR, 'app181_%s.png' % tag)
            ok = False
            best_ncol = 0
            best_dens = 0.0
            while time.time() - t0 < args.timeout:
                try:
                    ok = capture_hwnd(hwnd, shot)
                except Exception as e:
                    ok = False
                    print('    抓图异常：%r' % e)
                if ok and os.path.isfile(shot):
                    try:
                        ncol, size = client_n_colors(shot)
                        dens = content_density(shot)
                    except Exception as e:
                        ncol, size, dens = 0, None, 0.0
                        print('    分析异常：%r' % e)
                    obs['attempts'].append({'t': round(time.time() - t0, 1),
                                            'client_n_colors': ncol,
                                            'content_density': dens})
                    print('    抓图 t=%.1fs  色彩数=%d  密度=%.5f  %s'
                          % (time.time() - t0, ncol, dens,
                             '✅ 达标' if dens >= args.min_density
                             else '（内容不足，继续等）'))
                    if ncol > best_ncol:
                        best_ncol = ncol
                    if dens > best_dens:
                        best_dens = dens
                    if dens >= args.min_density:
                        break
                if proc.poll() is not None:
                    obs['rc'] = proc.returncode
                    break
                time.sleep(5.0)

            obs['wait_s'] = round(time.time() - t0, 1)
            obs['client_n_colors'] = best_ncol
            obs['content_density'] = best_dens
            if ok and os.path.isfile(shot):
                obs['shot'] = shot
                obs['shot_bytes'] = os.path.getsize(shot)
                try:
                    from png_stats import color_stats
                    obs['shot_stats'] = color_stats(shot)
                    obs['shot_size'] = obs['shot_stats']['size']
                    obs['full_n_colors'] = obs['shot_stats']['full_n_colors']
                except Exception as e:
                    obs['shot_stats'] = '解析失败：%r' % e

            # 收尾：杀掉自己拉起的进程（不留孤儿占 NPU）
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except Exception:
                    proc.kill()
            except Exception:
                pass
            obs_list.append(obs)
            print('  观测：rc=%r wait=%.1fs client_n_colors=%d'
                  % (obs.get('rc'), obs.get('wait_s', 0),
                     obs.get('client_n_colors', 0)))

        # ── 判据 ──────────────────────────────────────────────────
        print('\n== 判据 ==')
        for obs in obs_list:
            tag = obs['tag']
            check('%s pythonw 进程成功启动（GUI 未崩）' % tag,
                  obs.get('rc') in (None, 0) and obs.get('window') is not None,
                  'rc=%r window=%r' % (obs.get('rc'), obs.get('window')))
            check('%s 截图客户区**有内容**（不是空客户区）' % tag,
                  obs.get('client_n_colors', 0) >= args.min_client_colors,
                  'client_n_colors=%d（阈值 %d）shot=%r'
                  % (obs.get('client_n_colors', 0), args.min_client_colors,
                     obs.get('shot')))
            # 🔴🔴🔴 **密度判据**（真正能识破「只画了几行文字的半成品」）
            check('%s 截图客户区**内容密度达标**（三分区控件已渲染）' % tag,
                  obs.get('content_density', 0.0) >= args.min_density,
                  'content_density=%.5f（阈值 %.5f）'
                  % (obs.get('content_density', 0.0), args.min_density))
            check('%s 截图文件已落盘' % tag,
                  bool(obs.get('shot')) and obs.get('shot_bytes', 0) > 1000,
                  'bytes=%r path=%r' % (obs.get('shot_bytes'), obs.get('shot')))

        # ── 反证组 ────────────────────────────────────────────────
        print('\n== 反证组（新判据必须有鉴别力）==')
        bad = os.path.join(HOME, 'shared', 'app_pythonw_coldstart',
                           'app178_cold1.png')
        half = os.path.join(SHOT_DIR, 'app181_halfdone.png')
        good = os.path.join(HOME, 'shared', 'app_gui_layout',
                            'app048_layout_1920x1080.png')
        if os.path.isfile(bad):
            n, _ = client_n_colors(bad)
            d = content_density(bad)
            check('R1 反证：已知**空客户区**的旧图 ⇒ 新判据判空',
                  n < args.min_client_colors and d < args.min_density,
                  'client_n_colors=%d（应 < %d）  density=%.5f（应 < %.5f）'
                  % (n, args.min_client_colors, d, args.min_density))
        else:
            check('R1 反证样本存在', False, bad)

        # 🔴🔴🔴 R1b：**半成品图**（app181 第二版抓到的：色彩数 95 ⇒ 旧判据 PASS，
        #   但人眼只见标题 + 一行设备提示 ⇒ 三分区未渲染 ⇒ 密度 0.0195）
        #   ⇒ **必须**被密度判据拦住（而旧色彩数判据放行）⇒ 证明新判据更强。
        if os.path.isfile(half):
            n, _ = client_n_colors(half)
            d = content_density(half)
            check('R1b 反证：**半成品图**（旧色彩数判据会放行）⇒ 密度判据必须拦住',
                  n >= args.min_client_colors and d < args.min_density,
                  'client_n_colors=%d（旧判据放行）  density=%.5f（应 < %.5f）'
                  % (n, d, args.min_density))
        else:
            check('R1b 反证样本存在', False,
                  half + '（需先跑一次 --save-half 留存半成品图）')

        if os.path.isfile(good):
            n, _ = client_n_colors(good)
            d = content_density(good)
            check('R2 反证：已知**有内容**的布局图 ⇒ 新判据放行',
                  n >= args.min_client_colors and d >= args.min_density,
                  'client_n_colors=%d  density=%.5f（应 ≥ %.5f）'
                  % (n, d, args.min_density))
        else:
            check('R2 反证样本存在', False, good)

        verdict = 'PASS' if FAIL == 0 else 'FAIL'
        print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

        ev = {
            'script': os.path.basename(__file__),
            'correction': 'APP-051②（pythonw 冷启动截图重抓）/ APP-043',
            'pkg': pkg, 'version': ver,
            'min_client_colors': args.min_client_colors,
            'timeout_s': args.timeout,
            'observations': obs_list,
            'checks': CHECKS, 'n_pass': PASS, 'n_fail': FAIL,
            'verdict': verdict,
            'note': '① 判据换成「客户区色彩数」（修 app178「整图色彩数≥8」恒真）；'
                    '② 等待条件换成「客户区真有内容」（覆盖模型冷加载）；'
                    '③ 音质/可懂交 reviewer 与用户实听判定',
        }
        out = args.out or EVID
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(ev, f, ensure_ascii=False, indent=2)
        print('[evidence] %s' % out)
        return 0 if FAIL == 0 else 1
    finally:
        release_lock()


if __name__ == '__main__':
    sys.exit(main())
