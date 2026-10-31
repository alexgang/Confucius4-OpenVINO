#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app178 — APP-043/051②：**用户真实启动方式**（pythonw 冷启动）验收。

🔴 **为什么必须单独验收**（记忆 §七 + APP-043）：
  用户 = 桌面快捷方式 → `Start_LiveCaption.bat` → `pythonw.exe -s app\live_caption_app.py`
  ⇒ **无控制台**（stdout/stderr 全丢）⇒ 用 `--cli` 做的验收**不代表用户路径**。
  🔴 冷启动（无缓存、无预热）还会暴露「首次加载才出现」的缺陷。

🔴 **判据（三态，不靠 stdout）**：
  A. `pythonw.exe` 进程在 N 秒内**存活**（没崩）；
  B. 出现**标题含「Confucius4」的可见顶层窗口**（GUI 真的起来了）；
  C. `PrintWindow` 抓图**有内容**（不是黑图/空白）⇒ 像素级守卫；
  D. 冷启动**两次**（第二次 = 模拟「用户再点一次快捷方式」）都能起来。

🔴 **纪律**：
  - 本脚本**不跑推理**（只验证 GUI 起来）⇒ 不占 GPU/NPU ⇒ 不必取机器锁；
  - 抓图用 Win32 `PrintWindow`（本机 `ImageGrab.grab()` 抓屏全黑）；
  - 结束时**必须**关掉自己拉起的进程（不留孤儿占 NPU）。

## 用法
    python results/app/app178_pythonw_coldstart.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v1.13')
PYTHONW = os.path.join(PKG, 'python', 'pythonw.exe')
APP_PY = os.path.join(PKG, 'app', 'live_caption_app.py')
SHOT_DIR = os.path.join(HOME, 'shared', 'app_pythonw_coldstart')
EVID = os.path.join(HERE, 'app178_pythonw_coldstart_evidence.json')

sys.path.insert(0, HERE)
# 🔴 `capture_hwnd` 内部需要 PIL ⇒ **必须先把包内 site-packages 加进 path**
#   （否则 _save_bmp 里 `from PIL import Image` 失败 ⇒ 静默返回 False）
sys.path.insert(0, os.path.join(HOME, 'Confucius4_LiveCaption_v1.13',
                                'python', 'Lib', 'site-packages'))
from win_capture import capture_hwnd  # noqa: E402

user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

PASS = 0
FAIL = 0
CHECKS = []
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def acquire_lock():
    """🔴🔴 **必须持共享机器锁**：pythonw 启动会**加载模型**
       （TTS→NPU / ASR→GPU.0）⇒ 与其它模块抢硬件
       ⇒ 违反「计时/推理作业前取锁」纪律。
    """
    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    print('[lock] 申请共享机器锁 …')
    ok, payload = ml.acquire(module='app', timeout=7200, poll=20, verbose=True)
    if not ok:
        print('[lock] !! 未能取得机器锁 ⇒ 退出（绝不在无锁下启动 GUI）')
        return None, None
    print('[lock] 已取得：%r' % (payload,))
    return ml, payload


def check(name, cond, detail=''):
    global PASS, FAIL
    ok = bool(cond)
    print('  [%s] %s%s' % ('PASS' if ok else 'FAIL', name,
                           ('  ' + str(detail)) if detail else ''))
    CHECKS.append({'name': name, 'ok': ok, 'detail': str(detail)[:400]})
    if ok:
        PASS += 1
    else:
        FAIL += 1
    return ok


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


def pid_alive(pid):
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    h = k32.OpenProcess(0x1000, False, pid)
    if not h:
        return ctypes.get_last_error() != 87
    try:
        code = wt.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
            return True
        return code.value == 259
    finally:
        k32.CloseHandle(h)


def launch_and_probe(tag: str, timeout_s: float = 180.0):
    """用 pythonw 启动 GUI ⇒ 等窗口 ⇒ 抓图 ⇒ 杀进程。返回观测 dict。"""
    env = dict(os.environ)
    env['PYTHONPATH'] = ''
    env['PYTHONHOME'] = ''
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONUTF8'] = '1'
    cwd = PKG

    before = {h for h, _t in enum_windows()}
    t0 = time.time()
    proc = subprocess.Popen([PYTHONW, '-s', APP_PY],
                            cwd=cwd, env=env,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    obs = {'tag': tag, 'pid': proc.pid, 'window': None, 'shot': None,
           'shot_bytes': 0, 'shot_extrema': None, 'wait_s': 0.0,
           'rc': None}

    hwnd = None
    title = ''
    best_area = 0
    while time.time() - t0 < timeout_s:
        if proc.poll() is not None:
            obs['rc'] = proc.returncode
            obs['wait_s'] = round(time.time() - t0, 2)
            break
        # 🔴🔴🔴 **必须挑「面积最大」的窗口**（实测）：
        #   Tk 会创建**多个同名 toplevel**（辅助窗 1638x122 / 44x24 /
        #   真正主窗 1096x859）⇒ 只按标题匹配会抓到**辅助窗**
        #   ⇒ 抓出来是黑图 ⇒ 「C 抓图非空」判据假 FAIL。
        for h, t in enum_windows():
            if h in before:
                continue
            if 'Confucius4' not in t and '实时字幕' not in t \
                    and 'LiveCaption' not in t:
                continue
            r = wt.RECT()
            if not user32.GetWindowRect(wt.HWND(h), ctypes.byref(r)):
                continue
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best_area:
                best_area = area
                hwnd, title = h, t
        if hwnd is not None and best_area >= 400 * 300:
            obs['wait_s'] = round(time.time() - t0, 2)
            break
        time.sleep(1.0)

    if hwnd is not None:
        obs['window'] = title
        r = wt.RECT()
        user32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(r))
        obs['window_size'] = [r.right - r.left, r.bottom - r.top]
        # 🔴🔴🔴 **Tk 窗口必须「在前台 + 被重绘过」才画得出客户区**
        #   （app165 的 mock 场景没暴露这点 ⇒ 抓出来全白）
        #   ⇒ ① 置前台 ② 强制 RedrawWindow ③ 等一拍再抓
        try:
            user32.ShowWindow(wt.HWND(hwnd), 9)        # SW_RESTORE
            user32.SetForegroundWindow(wt.HWND(hwnd))
        except Exception:
            pass
        try:
            RDW_INVALIDATE = 0x0001
            RDW_UPDATENOW = 0x0100
            RDW_ALLCHILDREN = 0x0080
            RDW_ERASE = 0x0004
            user32.RedrawWindow(wt.HWND(hwnd), None, None,
                                RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN
                                | RDW_UPDATENOW)
        except Exception:
            pass
        time.sleep(3.0)
        os.makedirs(SHOT_DIR, exist_ok=True)
        shot = os.path.join(SHOT_DIR, 'app178_%s.png' % tag)
        # 🔴🔴 **抓图重试**：GUI 刚起来时客户区可能还没绘制
        #   ⇒ 反复抓，直到「有色彩多样性」或超时
        ok = False
        for attempt in range(6):
            try:
                ok = capture_hwnd(hwnd, shot)
            except Exception as e:
                ok = False
                print('    抓图异常：%r' % e)
            if ok and os.path.isfile(shot):
                try:
                    from PIL import Image
                    im = Image.open(shot).convert('RGB')
                    ncol = len(im.getcolors(maxcolors=4096) or [])
                    if ncol >= 8:
                        break
                    print('    抓图第 %d 次：色彩数=%d（疑似空白）⇒ 重试'
                          % (attempt + 1, ncol))
                except Exception:
                    pass
            time.sleep(3.0)
        obs['shot'] = shot if ok else None
        if ok and os.path.isfile(shot):
            obs['shot_bytes'] = os.path.getsize(shot)
            # 🔴 像素级守卫：不能是纯黑/纯空
            try:
                from PIL import Image
                im = Image.open(shot).convert('RGB')
                obs['shot_extrema'] = list(im.getextrema())
                obs['shot_size'] = list(im.size)
                # 🔴 色彩多样性：全灰/单色 ⇒ 也是「无效抓图」
                obs['shot_n_colors'] = len(im.getcolors(maxcolors=4096) or [])
            except Exception as e:
                obs['shot_extrema'] = 'PIL 不可用：%r' % e

    # ── 收尾：杀掉自己拉起的进程（不留孤儿占 NPU）──
    try:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    except Exception:
        pass
    obs['alive_after_kill'] = pid_alive(proc.pid)
    obs['rc'] = proc.returncode
    return obs


def main():
    print('=' * 74)
    print('app178 —— APP-043/051② 用户真实启动方式（pythonw 冷启动）验收')
    print('  pkg   =', PKG)
    print('  pythonw=', PYTHONW)
    print('=' * 74)

    for p in (PYTHONW, APP_PY):
        if not os.path.isfile(p):
            print('!! 缺少文件：%s' % p)
            return 2

    runs = []
    ml, payload = acquire_lock()
    if ml is None:
        return 3
    try:
        for i, tag in enumerate(('cold1', 'cold2'), 1):
            print('\n-- 第 %d 次冷启动（%s）--' % (i, tag))
            obs = launch_and_probe(tag)
            runs.append(obs)
            print('  观测：%r' % ({k: v for k, v in obs.items()
                                  if k != 'shot_extrema'},))
            print('  像素极值：%r' % (obs.get('shot_extrema'),))
    finally:
        try:
            ml.release(payload)
            print('[lock] 已释放')
        except Exception as e:
            print('[lock] 释放异常：%r' % e)

    print('\n== 判据 ==')
    for obs in runs:
        tag = obs['tag']
        check('A_%s pythonw 进程存活过（没崩）' % tag,
              obs.get('window') is not None or obs.get('rc') == 0,
              'rc=%r window=%r' % (obs.get('rc'), obs.get('window')))
        check('B_%s 出现 GUI 可见窗口' % tag, obs.get('window') is not None,
              'title=%r wait=%.1f s' % (obs.get('window'), obs.get('wait_s', 0)))
        check('C_%s 抓图成功且非空' % tag, obs.get('shot_bytes', 0) > 1000,
              '%d B  path=%r' % (obs.get('shot_bytes', 0), obs.get('shot')))
        ext = obs.get('shot_extrema')
        if isinstance(ext, list) and len(ext) == 3:
            dark = all(hi == 0 for _lo, hi in ext)
            check('D_%s 抓图不是全黑（像素级守卫）' % tag, not dark,
                  'extrema=%r' % (ext,))
        else:
            check('D_%s 抓图不是全黑（像素级守卫）' % tag, False,
                  '无法判定 extrema=%r' % (ext,))
        ncol = obs.get('shot_n_colors')
        check('D2_%s 抓图有色彩多样性（非单色空白）' % tag,
              isinstance(ncol, int) and ncol >= 8,
              'n_colors=%r size=%r' % (ncol, obs.get('shot_size')))
        check('E_%s 进程已被收尾（不留孤儿占 NPU）' % tag,
              not obs.get('alive_after_kill', True),
              'alive_after_kill=%r' % obs.get('alive_after_kill'))

    check('F 两次冷启动都能起来（可重复）',
          all(o.get('window') is not None for o in runs),
          'windows=%r' % ([o.get('window') for o in runs],))

    verdict = 'PASS' if FAIL == 0 else 'FAIL'
    print('\nPASS %d  FAIL %d  verdict=%s' % (PASS, FAIL, verdict))

    ev = {'script': os.path.basename(__file__),
          'correction': 'APP-043 / APP-051②',
          'pkg': PKG, 'pythonw': PYTHONW, 'app_py': APP_PY,
          'shot_dir': SHOT_DIR,
          'runs': runs, 'checks': CHECKS,
          'n_pass': PASS, 'n_fail': FAIL, 'verdict': verdict}
    with open(EVID, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('证据已写：%s' % EVID)
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
