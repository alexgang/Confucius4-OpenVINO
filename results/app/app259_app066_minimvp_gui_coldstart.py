#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app259 — **APP-066 3(b)**：MiniMVP 的 **GUI 冷启动** 验收（修 app256 的 3 处真缺陷）。

## 🔴 app256 为什么 FAIL（0 PASS / 3 FAIL）—— 本脚本逐条修
| # | app256 的缺陷 | 证据 | 本脚本的修法 |
|---|---|---|---|
| **D1** | **抓错窗口**：Tk 会建**多个同名窗口**（实测 6 个可见）⇒ app256 取「**第一个非黑**」⇒ 抓到的是 **1638×122 的窄条**（不是主窗口 1455×1132） | `app258_gui_window_diag.json` → `probes[].shots_all` | **按窗口面积取最大者**（真主窗口）＋ 逐个候选都记录 |
| **D2** | **失败原因被丢弃**：`grab()` 失败时返回的 `why`/`tried` **没进证据** ⇒ 只剩 `shot=null` ⇒ **无法判因** | app256 → `runs[].shot = null` | **每个候选窗口的抓屏结果 + 失败原因全部落盘** ⇒ 「无法判定」可见 |
| **D3** | **音频只有 300 s ⇒ 冷编译跑不完**：MiniMVP 首次 NPU 编译要 **~4 min**（实测 23:30→23:34 写 2.4 GB blob）⇒ 300 s 的音频**先结束** ⇒ `模型加载完成` 永远不出现 ⇒ `tts_load_s=None` | `session_20261104_233025.log`（无「模型加载完成」行）＋ `tts_npu_cache` blob mtime | **把源 wav 拼成 900 s**（3×）⇒ 冷臂能跑过编译；**并在「模型加载完成」出现后立刻停** ⇒ 不浪费时间 |
| **D4** | **150 % 尺寸判据口径错**：app256 拿 **窗口矩形**（含标题栏/边框）比 **客户区** 目标 `[1620,1230]` ⇒ 必 FAIL | 100 % 实测 window rect 1455×1132 ⇒ 客户区 1440×1093（= 1080×820 × tk scaling 1.333） | 改用 **GetClientRect**（客户区）⇒ 150 % 客户区应 = `[1620,1230]`（= 1080×820 × 1.5） |

## 🔴 150 % 怎么模拟
`tk scaling` 是**进程级全局**、`tk.Tk()` 会**重置**它 ⇒ 必须**替换 `tkinter.Tk` 类**，
在 `Tk()` 建好**之后**再设 `scaling=1.5` ⇒ App 自己按 `_LOGIC_W × scaling` 算窗口尺寸
（`live_caption_app.py` L2315-2320）⇒ **物理 = 逻辑 × scaling**（逻辑尺寸恒为 1080×820）。

## 用法
```
.venv/Scripts/python.exe results/app/app259_app066_minimvp_gui_coldstart.py --run
```
"""
from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HOME = os.path.expanduser('~')
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc2')
OUT_DIR = os.path.join(HERE, 'app259_minimvp_gui')
OUT_JSON = os.path.join(HERE, 'app259_app066_minimvp_gui_evidence.json')
TITLE_KEY = '实时字幕'
SRC_WAV = os.path.join(HOME, 'shared', 'SPE_0000_0500.wav')

user32 = ctypes.windll.user32

_RE_TTS_LOAD = re.compile(r'\[tts_engine\].*?模型加载完成（([0-9.]+)\s*s）')
_RE_TTS_MODEL = re.compile(r'\[tts_engine\]\s*加载模型：device=(\S+)')
_RE_ASR_LOAD = re.compile(r'\[gpu_int8\]\s+加载\s+([0-9.]+)\s*s')
_RE_ASR_LOAD2 = re.compile(r'加载\s+Intel GPU[^）]*?（ov-int8-past）')
_RE_MT_LOAD = re.compile(r'翻译模型就绪（([^）]+?)，加载\s+([0-9.]+)\s*s）')
_RE_NPU_COMPILE = re.compile(r'注入 NPU 的编译|编译缓存|CACHE_DIR')


# ══════════════════════════════════════════════════════════════════════
# 🔴 抓屏（修 D1 / D2）
# ══════════════════════════════════════════════════════════════════════
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _client_size(hwnd):
    """客户区尺寸（**不含**标题栏/边框）⇒ 150 % 判据要用它。"""
    r = ctypes.wintypes.RECT()
    if not user32.GetClientRect(ctypes.c_void_p(hwnd), ctypes.byref(r)):
        return None
    return [r.right - r.left, r.bottom - r.top]


def _win_rect(hwnd):
    r = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r)):
        return None
    return [r.right - r.left, r.bottom - r.top]


def find_candidates():
    """**全部**可见且标题含关键字的窗口（🔴 Tk 会建多个同名窗口）。"""
    out = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p,
                                          ctypes.c_void_p)

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        if TITLE_KEY in buf.value:
            out.append({'hwnd': int(hwnd), 'title': buf.value,
                        'rect': _win_rect(hwnd),
                        'client': _client_size(hwnd)})
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def grab_one(hwnd, path):
    """抓单个窗口 ⇒ **失败原因必须带回来**（修 D2）。"""
    wc = _load('win_capture_mod', os.path.join(HERE, 'win_capture.py'))
    try:
        ok = wc.capture_hwnd(hwnd, path)
    except Exception as e:
        return {'ok': False, 'why': repr(e)}
    info = {'ok': bool(ok),
            'bytes': (os.path.getsize(path) if os.path.isfile(path) else None)}
    if ok and os.path.isfile(path):
        try:
            from PIL import Image
            im = Image.open(path).convert('RGB')
            ex = im.getextrema()
            info['extrema'] = [list(e) for e in ex]
            info['all_black'] = all(e[0] == 0 and e[1] == 0 for e in ex)
            info['size'] = list(im.size)
        except Exception as e:
            info['pixel_check_error'] = repr(e)
    else:
        info['why'] = ('capture_hwnd 返回 False（<=1000 B 视为失败）'
                       if info.get('bytes') is not None else 'capture 异常')
    return info


def grab_best(path):
    """🔴 **按窗口面积取最大者**（真主窗口）⇒ 修 D1。

    仍保留**每个候选**的抓屏结果（成功/失败 + 原因）⇒ 修 D2。

    🔴🔴 **绝对不要「建 tmp 再删 tmp」**：每个候选各建一个 `.c<hwnd>` 文件再删
    ⇒ 单轮就产生 **N 次删除** ⇒ 累计到宿主「批量删除保护」阈值（50）
    ⇒ **进程被宿主杀掉**（实测 app259 第二跑：`gui_warm.png.c*` + `MACHINE_LOCK`
    同时被拦 ⇒ 脚本被中止 ⇒ 证据写不出来）。
    ⇒ 改法：**所有候选写进同一个文件**（`path + '.cand'`），**只覆盖不删除**；
    最后 `os.replace` 成正式名（1 次改名，0 次删除）。
    """
    cands = find_candidates()
    tried = []
    best = None
    tmp = path + '.cand'
    for c in cands:
        area = 0
        if c.get('rect'):
            area = c['rect'][0] * c['rect'][1]
        # 🔴 同一路径覆盖写 ⇒ 0 次删除
        info = grab_one(c['hwnd'], tmp)
        info['hwnd'] = c['hwnd']
        info['rect'] = c['rect']
        info['client'] = c['client']
        info['area'] = area
        tried.append(info)
        if info.get('ok') and not info.get('all_black'):
            # 🔴 面积最大的**非黑**窗口才是目标
            if best is None or area > best.get('area', 0):
                if best is not None:
                    # 之前那份已被同名覆盖 ⇒ **不用删**（内容已丢，但要记下尺寸）
                    best['superseded_by_larger'] = True
                info['_area'] = area
                best = info
    if best is None:
        return {'ok': False,
                'why': '没有抓到有效内容（%d 个候选窗口全失败/全黑）' % len(cands),
                'n_candidates': len(cands), 'tried': tried}
    # 🔴 重新抓一次「最佳窗口」写进正式名（上面那次的内容已被后续候选覆盖）
    best_info = None
    for c in cands:
        if c['hwnd'] == best['hwnd']:
            best_info = c
            break
    if best_info is not None:
        grab_one(best_info['hwnd'], path)
    # 🔴 **必须拷贝**：`tried` 里含 `best` 自身 ⇒ 直接挂会形成**循环引用**
    #    ⇒ `json.dump` 抛 `ValueError: Circular reference detected`
    #    ⇒ 证据文件**根本写不出来**（app259 首跑就踩了）。
    best['tried'] = [dict(t) for t in tried]
    best['n_candidates'] = len(cands)
    return best


# ══════════════════════════════════════════════════════════════════════
# 🔴 音频拼接（修 D3）—— 冷编译要 ~4 min ⇒ 音频必须够长
# ══════════════════════════════════════════════════════════════════════
def build_long_wav(src, dst, repeats):
    if not os.path.isfile(src):
        return None
    with wave.open(src, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(w.getnframes())
    with wave.open(dst, 'wb') as w:
        w.setparams(params)
        for _ in range(repeats):
            w.writeframes(frames)
    return dst


# ══════════════════════════════════════════════════════════════════════
# 跑一次 GUI
# ══════════════════════════════════════════════════════════════════════
def newest_session_log(localapp, after_ts):
    d = os.path.join(localapp, 'Confucius4LiveCaption')
    if not os.path.isdir(d):
        return None
    cands = [os.path.join(d, f) for f in os.listdir(d)
             if f.startswith('session_') and f.endswith('.log')]
    cands.sort(key=lambda p: os.path.getmtime(p))
    cands = [p for p in cands if os.path.getmtime(p) >= after_ts - 5]
    return cands[-1] if cands else None


def launcher_150():
    """150 % 启动器（**替换 `tkinter.Tk` 全局类**；scaling 必须在 Tk() 之后设）。"""
    p = os.path.join(HERE, '_app259_gui_150_launcher.py')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(
            "# -*- coding: utf-8 -*-\n"
            "\"\"\"150 % 缩放启动器（由 app259 生成，勿手改）。\"\"\"\n"
            "import sys\n"
            "import tkinter as tk\n"
            "\n"
            "SCALE = 1.5\n"
            "_base = tk.Tk\n"
            "\n"
            "\n"
            "def _scaled(*a, **k):\n"
            "    r = _base(*a, **k)\n"
            "    # 🔴 tk scaling 必须在 Tk() 之后设（tk.Tk() 会重置它）\n"
            "    try:\n"
            "        r.tk.call('tk', 'scaling', SCALE)\n"
            "    except Exception as e:\n"
            "        print('[launcher150] scaling 设置失败：%r' % e)\n"
            "    return r\n"
            "\n"
            "\n"
            "tk.Tk = _scaled\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import live_caption_app\n"
            "sys.argv = [sys.argv[2]] + sys.argv[3:]\n"
            "live_caption_app.main()\n")
    return p


def run_gui(pkg, localapp, wav, seconds, tag, scale=1.0,
            timeout_s=900.0, min_run_s=45.0):
    """跑一次 GUI。

    🔴 **在「模型加载完成」出现后立刻停** ⇒ 冷臂不用干等整段音频。
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    selftest = os.path.join(OUT_DIR, 'selftest_%s' % tag)
    log_path = os.path.join(OUT_DIR, 'gui_%s.log' % tag)
    shot_path = os.path.join(OUT_DIR, 'gui_%s.png' % tag)

    common = ['--source', 'file', '--file', wav,
              '--autostart', '--selftest', str(int(seconds)),
              '--selftest-out', selftest,
              '--tts', 'on', '--tts-voice', 'A', '--speaker', 'off',
              '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
              '--tts-device', 'NPU', '--translate', 'zh',
              # 🔴 APP-066 1：MT 用 INT4 ⇒ 显式指定（不靠 'auto' 的候选顺序）
              '--mt-engine', 'gpu_int4cw']
    if scale == 1.0:
        cmd = [py, app] + common
    else:
        lau = launcher_150()
        cmd = [py, lau, os.path.join(pkg, 'app'), app] + common

    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['LIVECAP_PKG'] = pkg
    env['LOCALAPPDATA'] = localapp
    mt_dir = os.path.join(pkg, 'models', 'mt', 'mt2-int4sym-cw-q')
    if os.path.isdir(mt_dir):
        env['LIVECAP_MT_MODEL'] = mt_dir

    t0 = time.time()
    with open(log_path, 'wb') as lf:
        proc = subprocess.Popen(cmd, env=env, stdout=lf,
                                stderr=subprocess.STDOUT)
    shot = None            # **最后一次**成功抓屏（内容最全）
    shot_first = None      # 第一次成功抓屏（窗口刚出现时）
    n_captures = 0
    model_loaded_at = None
    stopped_reason = 'timeout'
    exit_code = None
    while True:
        if proc.poll() is not None:
            stopped_reason = '进程自行退出'
            exit_code = proc.returncode
            break
        el = time.time() - t0
        if el > timeout_s:
            stopped_reason = '超时 %s s' % timeout_s
            break
        time.sleep(2.0)
        # 🔴🔴 抓屏：**持续抓，保留「客户区最大」的那一次**（= 完整主窗口）
        #   ⚠️ 上一版留「最后一次」⇒ **抓到了 1638×122 的窄条**（顶栏条）：
        #      Tk 同名窗口有 3 个，**窄条在后出现**（模型加载完顶栏才刷新）
        #      ⇒ 「最后一次」≠「主窗口」⇒ 判据被窄条冒充。
        #   ⇒ 改为：**只在抓到「客户区高 ≥ 700 px」的主窗口时**才更新 `shot`。
        cand = grab_best(shot_path)
        if cand.get('ok'):
            n_captures += 1
            cand['at_s'] = round(time.time() - t0, 1)
            if shot_first is None:
                shot_first = dict(cand)
            cl = cand.get('client') or []
            if cl and cl[1] >= 700:
                shot = cand
        # 「模型加载完成」检测 ⇒ 拿到就停
        slog = newest_session_log(localapp, t0)
        if slog:
            try:
                with open(slog, encoding='utf-8', errors='replace') as f:
                    txt = f.read()
            except OSError:
                txt = ''
            if _RE_TTS_LOAD.search(txt):
                model_loaded_at = round(time.time() - t0, 1)
                if shot is not None and model_loaded_at >= min_run_s:
                    stopped_reason = '模型加载完成 ⇒ 停'
                    break
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=20)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    # 🔴 **收尾再抓一次**（只要主窗口）⇒ 一定是「模型已就绪」后的完整界面
    final = grab_best(shot_path)
    if final.get('ok'):
        final['at_s'] = round(time.time() - t0, 1)
        fcl = final.get('client') or []
        if fcl and fcl[1] >= 700:
            shot = final
        elif shot is None:
            shot = final
        n_captures += 1
    wall = time.time() - t0

    with open(log_path, encoding='utf-8', errors='replace') as f:
        text = f.read()
    slog = newest_session_log(localapp, t0)
    stext = ''
    if slog:
        with open(slog, encoding='utf-8', errors='replace') as f:
            stext = f.read()
    merged = text + '\n' + stext
    m = _RE_TTS_LOAD.search(merged)
    mt = _RE_MT_LOAD.search(merged)
    asr = _RE_ASR_LOAD.search(merged)
    res = {'tag': tag, 'scale': scale, 'cmd': cmd,
           'localappdata': localapp, 'wav': wav,
           'rc': proc.poll(), 'exit_code_early': exit_code,
           'wall_s': round(wall, 2),
           'stopped_reason': stopped_reason,
           'model_loaded_at_s': model_loaded_at,
           'shot': shot, 'shot_first': shot_first,
           'n_captures': n_captures,
           'shot_path': shot_path,
           'log_path': log_path, 'session_log': slog,
           'log_bytes': len(text.encode('utf-8', 'replace')),
           'log_tail': text[-1500:],
           'session_log_bytes': len(stext.encode('utf-8', 'replace')),
           'session_log_tail': stext[-1500:],
           'tts_load_s': (float(m.group(1)) if m else None),
           'mt_load_s': (float(mt.group(2)) if mt else None),
           'mt_label': (mt.group(1) if mt else None),
           'asr_load_s': (float(asr.group(1)) if asr else None),
           'asr_load_seen': bool(asr or _RE_ASR_LOAD2.search(merged)),
           'tts_device': ((_RE_TTS_MODEL.search(merged).group(1))
                          if _RE_TTS_MODEL.search(merged) else None),
           'has_npu_compile_hint': bool(_RE_NPU_COMPILE.search(merged)),
           'selftest_files': (sorted(os.listdir(selftest))
                              if os.path.isdir(selftest) else []),
           }
    print('\n[%s] wall=%s s  TTS 加载=%s s  model_loaded_at=%s s  shot=%s'
          % (tag, res['wall_s'], res['tts_load_s'], model_loaded_at,
             (json.dumps({k: shot.get(k) for k in
                          ('ok', 'size', 'bytes', 'all_black', 'hwnd')},
                         ensure_ascii=False) if shot else 'None')),
          flush=True)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--pkg', default=PKG)
    ap.add_argument('--cold-timeout', type=float, default=2400.0)
    ap.add_argument('--warm-timeout', type=float, default=900.0)
    ap.add_argument('--out', default=OUT_JSON)
    args = ap.parse_args()

    out = {'script': 'app259_app066_minimvp_gui_coldstart.py',
           'correction': 'APP-066 3(b)',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args), 'checks': [], 'runs': [],
           'fixes_vs_app256': [
               'D1 抓屏按**窗口面积**取最大者（真主窗口 1455×1132），'
               '不再取「第一个非黑」（那是 1638×122 窄条）',
               'D2 每个候选窗口的抓屏结果 + 失败原因全部落盘（不再只有 shot=null）',
               'D3 音频 300 s → 900 s（冷 NPU 编译 ~4 min 需跑过），'
               '且「模型加载完成」出现后立刻停',
               'D4 150 % 尺寸判据改用**客户区** GetClientRect（= 逻辑 1080×820 × scaling）',
           ]}

    def add(name, verdict, detail, why=''):
        out['checks'].append({'name': name, 'verdict': verdict,
                              'detail': detail, 'why': why})
        print('  [%s] %s%s' % ({True: 'PASS', False: 'FAIL',
                                None: 'NONE'}[verdict], name,
                               ('  ' + json.dumps(detail, ensure_ascii=False))
                               if detail else ''), flush=True)

    if not args.run:
        print('（未加 --run ⇒ 不跑设备作业）')
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)

    sys.path.insert(0, REPO)
    import machine_lock_app as ml
    ok_lock, payload = ml.acquire(module='app', timeout=3600, poll=20,
                                   verbose=True)
    if not ok_lock:
        print('[lock] !! 未取得机器锁 ⇒ 退出')
        out['verdict'] = 'LOCK_BUSY'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3
    print('[lock] 已取得：%r' % (payload,))

    # 🔴 安静窗口（APP-064）：别人在跑 ⇒ 不开跑
    try:
        ok_q, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                timeout=1800.0, verbose=True)
    except Exception as e:
        ok_q, qinfo = None, repr(e)
    out['quiet_window'] = {'ok': ok_q, 'info': str(qinfo)}
    if ok_q is False:
        print('[quiet] !! 等不到安静窗口 ⇒ 退出')
        out['verdict'] = 'NOT_QUIET'
        try:
            ml.release(payload, verbose=True)
        except Exception:
            pass
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3

    la = None
    wav_long = None
    wav_dir = tempfile.mkdtemp(prefix='minimvp_wav_')
    try:
        # 🔴🔴 **音频必须比「首次 NPU 编译」更长**：
        #   App 在 `audio_s >= --selftest` 时**自行退出** ⇒ 音频/selftest 到点
        #   它就关窗 ⇒ 冷编译还没跑完就被打断 ⇒ `tts_load_s=null`。
        #   实测冷编译总耗时 ≈ **1130 s**（950 s 时仍有 3 个组件没编完，
        #   下一臂又花 179.6 s 才收尾）⇒ 音频/selftest 给 **1500 s**。
        wav_long = os.path.join(wav_dir, 'SPE_1500s.wav')
        if not build_long_wav(SRC_WAV, wav_long, 5):
            print('!! 源 wav 不存在：%s' % SRC_WAV)
            out['verdict'] = 'NO_SRC_WAV'
            return 3
        out['long_wav'] = wav_long
        with wave.open(wav_long, 'rb') as w:
            out['long_wav_seconds'] = round(w.getnframes() / w.getframerate(), 1)

        # 🔴🔴 **「进程自行退出」且 < 60 s ⇒ 判为异常退出 ⇒ 重试一次**
        #   （实测 app259 第二跑：冷臂 4 s 就退出 ⇒ 上一轮遗留的
        #     MiniMVP GUI 进程仍占着音频设备 ⇒ 新进程起不来）
        #   ⇒ 重试前先确认没有**别的** MiniMVP GUI 在跑。
        def kill_stale_minimvp():
            """🔴 只杀**本模块自己**遗留的 MiniMVP GUI（按命令行特征过滤）。"""
            killed = []
            try:
                import wmi  # noqa
            except Exception:
                wmi = None
            if wmi is None:
                return killed
            try:
                for p in wmi.WMI().Win32_Process():
                    cl = (p.CommandLine or '')
                    if 'MiniMVP_v1.0-rc2' in cl and 'live_caption_app.py' in cl:
                        try:
                            p.Terminate()
                            killed.append(p.ProcessId)
                        except Exception:
                            pass
            except Exception:
                pass
            return killed

        def run_arm(tag, scale, timeout_s, tries=2, localapp=None):
            """跑一臂。

            🔴 **冷臂每次重试都要用**全新** LOCALAPPDATA**（否则重试是「半热」
            ⇒ 冷/热对比失真）；**热臂与 150 % 臂必须复用冷臂那个目录**
            ⇒ 才能真正命中 NPU 编译缓存。
            """
            last = None
            cur_la = localapp
            for i in range(tries):
                if cur_la is None:
                    cur_la = tempfile.mkdtemp(prefix='minimvp_gui_')
                last = run_gui(args.pkg, cur_la, wav_long, 1500, tag,
                               scale=scale, timeout_s=timeout_s,
                               min_run_s=45.0)
                out['runs'].append(last)
                early = (last.get('stopped_reason') == '进程自行退出'
                         and (last.get('wall_s') or 0) < 60)
                if not early:
                    return last, cur_la
                print('[arm:%s] 异常早退（wall=%s s rc=%s）⇒ 清残留后重试 (%d/%d)'
                      % (tag, last.get('wall_s'), last.get('rc'),
                         i + 1, tries), flush=True)
                k = kill_stale_minimvp()
                if k:
                    print('[arm:%s] 已清残留 MiniMVP GUI：%s' % (tag, k),
                          flush=True)
                time.sleep(3.0)
                if localapp is None:
                    cur_la = None      # 冷臂重试 ⇒ 换新目录（保证「真冷」）
            return last, cur_la

        cold, la = run_arm('cold', 1.0, args.cold_timeout)
        warm, _ = run_arm('warm', 1.0, args.warm_timeout, localapp=la)
        s150, _ = run_arm('scaling150', 1.5, args.warm_timeout, localapp=la)

        # 🔴🔴 **冷臂若没测到 tts_load_s ⇒ 缓存是「半热」的**：
        #   冷臂被音频长度掐断时，它已经编好的 blob **留在共享缓存里**
        #   ⇒ 下一臂（warm）只需补编剩下的 ⇒ 报出来的 179.6 s **不是冷编译耗时**。
        #   ⇒ **冷臂没测到 ⇒ 必须重跑一个「真冷」臂**（全新 LOCALAPPDATA，
        #     且音频/selftest 足够长 ⇒ 2400 s）。
        if cold.get('tts_load_s') is None:
            print('[cold] !! 冷臂未测到 tts_load_s ⇒ 缓存半热 ⇒ 重跑真冷臂',
                  flush=True)
            cold, la = run_arm('cold', 1.0, args.cold_timeout, tries=3,
                               localapp=None)

        add('① 首次启动（TTS 加载耗时）有实测值',
            cold.get('tts_load_s') is not None,
            {'tts_load_s': cold.get('tts_load_s'),
             'model_loaded_at_s': cold.get('model_loaded_at_s'),
             'wall_s': cold.get('wall_s'), 'device': cold.get('tts_device'),
             'stopped_reason': cold.get('stopped_reason')})
        add('② 第二次启动（TTS 加载耗时）有实测值',
            warm.get('tts_load_s') is not None,
            {'tts_load_s': warm.get('tts_load_s'),
             'model_loaded_at_s': warm.get('model_loaded_at_s'),
             'wall_s': warm.get('wall_s')})
        if cold.get('tts_load_s') and warm.get('tts_load_s'):
            add('③ 第二次启动比首次**快**（缓存生效）',
                warm['tts_load_s'] <= cold['tts_load_s'],
                {'cold_s': cold['tts_load_s'], 'warm_s': warm['tts_load_s'],
                 'saved_s': round(cold['tts_load_s'] - warm['tts_load_s'], 2)})
        else:
            add('③ 第二次启动比首次快（缓存生效）', None, {},
                '缺 TTS 加载耗时 ⇒ 无法判定')
        for tag, r in (('100%', cold), ('150%', s150)):
            sh = r.get('shot') or {}
            cl = sh.get('client') or []
            # 🔴🔴 **判据必须要求「抓到的是**完整主窗口**」**，不能只要「非黑」：
            #   Tk 的同名窗口里有一个 **1638×122 的窄条**（顶栏条）⇒ 它也**非黑**
            #   ⇒ 「非黑」判据会让**窄条冒充主窗口**通过（实测冷臂就抓到了窄条）。
            #   ⇒ 追加判据：**客户区高度 ≥ 700 px**（主窗口 100 % 时高 1093；
            #     窄条只有 122 ⇒ 必被拒）。
            is_main = bool(cl) and cl[1] >= 700
            add('④ %s 截图抓到**完整主窗口**且非黑图' % tag,
                (sh.get('ok') and not sh.get('all_black') and is_main),
                {'ok': sh.get('ok'), 'all_black': sh.get('all_black'),
                 'bytes': sh.get('bytes'), 'size': sh.get('size'),
                 'client': sh.get('client'), 'is_main_window': is_main,
                 'n_candidates': sh.get('n_candidates'),
                 'note': '客户区高 ≥ 700 px 才是主窗口（窄条高 122 px）'})
        c150 = (s150.get('shot') or {}).get('client')
        c100 = (cold.get('shot') or {}).get('client')
        # 🔴🔴 **口径校准（实测得来，不是拍脑袋）**：
        #   `tk scaling 1.5` 在本机被 Tk 存成 **1.4989**（量化到像素栅格）
        #   ⇒ App 自己算 `int(1080*1.4989)=1618` / `int(820*1.4989)=1229`
        #   ⇒ 实测客户区 **1618×1229**（与应用公式**逐像素一致** ⇒ App 无 bug）
        #   ⇒ 判据不能写死 [1620,1230] ⇒ 改为「**应用公式 ±4 px**」
        #     （依据：`app260_tk_geometry_probe.json` ⇒ 申请 1620x1230 时
        #       客户区**就是** 1620×1230 ⇒ Tk 不裁剪 ⇒ 差值来自 scaling 量化）
        expect_150 = [1620, 1230]
        near = (c150 is not None
                and abs(c150[0] - expect_150[0]) <= 4
                and abs(c150[1] - expect_150[1]) <= 4)
        add('⑤ 150 % 的**客户区**尺寸 ≈ 逻辑 1080×820 × 1.5（应用公式 ±4 px）',
            near,
            {'client_150': c150, 'expect_150': expect_150,
             'client_100': c100, 'expect_100': [1439, 1093],
             'implied_scaling_150': (round(c150[0] / 1080.0, 4)
                                     if c150 else None),
             'note': 'Tk 把 scaling 1.5 量化成 1.4989 ⇒ 应用公式得 1618×1229；'
                     'app260 实测 Tk 不裁剪申请值 ⇒ 差值来自量化而非 App'})
        add('⑥ 冷启臂确实编译了 NPU（首次 tts_load ≫ 热启）',
            bool(cold.get('tts_load_s') and warm.get('tts_load_s')
                 and cold['tts_load_s'] > warm['tts_load_s']),
            {'cold_s': cold.get('tts_load_s'), 'warm_s': warm.get('tts_load_s')})
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % e)
        # 会话日志先拷出来（临时目录要删）
        try:
            if la:
                sd = os.path.join(la, 'Confucius4LiveCaption')
                if os.path.isdir(sd):
                    for fn in os.listdir(sd):
                        if fn.startswith('session_') and fn.endswith('.log'):
                            shutil.copy2(os.path.join(sd, fn),
                                         os.path.join(OUT_DIR, 'cold_%s' % fn))
        except Exception:
            pass
        # 🔴🔴 **不要 `shutil.rmtree`**：NPU 缓存有 **~20 个大 blob**（4–8 GB）
        #   ⇒ 一次删 20+ 文件 ⇒ 触发宿主「批量删除保护」（阈值 50）
        #   ⇒ **进程被宿主杀掉** ⇒ 证据写不出来（app259 第二跑就踩了）。
        # ⇒ 改：**保留**临时目录（由用户/后续轮次自行清理），
        #   只删**自己建的 wav 目录**（1 个文件，安全）。
        try:
            shutil.rmtree(wav_dir, ignore_errors=True)
        except Exception:
            pass

    n_pass = sum(1 for c in out['checks'] if c['verdict'] is True)
    n_fail = sum(1 for c in out['checks'] if c['verdict'] is False)
    n_none = sum(1 for c in out['checks'] if c['verdict'] is None)
    out['n_pass'], out['n_fail'], out['n_none'] = n_pass, n_fail, n_none
    out['verdict'] = 'PASS' if n_fail == 0 else 'FAIL'
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\n结果：%d PASS / %d FAIL / %d NONE ⇒ %s'
          % (n_pass, n_fail, n_none, out['verdict']))
    print('[evidence] %s' % args.out)
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
