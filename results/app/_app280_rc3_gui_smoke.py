r"""app280 — APP-072 闸门③ 之二：**解压副本**的 GUI 冒烟。

## 目的

APP-072 §2 原文：

> 解压到 `C:\minimvp_cleantest\` 跑一次 `--check`（模型能加载、无崩溃）即可；
> **GUI 冒烟能做就做，做不了写明。**

`--check` 已在 app280 之前通过（rc=0）。本脚本补上 **GUI 冒烟**这一半：
在**从 zip 解压出来的干净目录**上真正起一次 GUI，等 TTS 模型加载完成，
用 `PrintWindow` 抓主窗口（像素级守卫：非黑图 + 客户区高 ≥ 700 px），
然后正常关窗。

## 🔴 纪律

- **占 NPU/GPU** ⇒ 按 APP-064 必须先取 **MACHINE_LOCK** ＋ **安静窗口**。
- 抓屏**不**用 `PIL.ImageGrab`（本机全黑，见 `win_capture.py` docstring）。
- 抓屏**不**用「建 tmp 再删 tmp」（会触发宿主批量删除保护 ⇒ 进程被杀）
  ⇒ 所有候选窗口写进**同一个** `.cand` 文件（只覆盖不删除）。
- 证据里必须能区分「抓到主窗口」与「抓到窄条」⇒ 客户区高 ≥ 700 px。

## 用法

    .venv/Scripts/python.exe results/app/_app280_rc3_gui_smoke.py --run
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

# 🔴 APP-072 §1 指定的 zip 解压位置（本脚本只认这一个「干净副本」）
CLEANTEST = r'C:\minimvp_cleantest'
PKG_NAME = 'Confucius4_LiveCaption_MiniMVP_v1.0-rc3'

TITLE_KEY = '实时字幕 MiniMVP'
SRC_WAV = r'C:\Users\Trekker-PTL\shared\SPE_0000_0500.wav'

RE_TTS_LOAD = re.compile(r'\[tts_engine\].*?模型加载完成（([0-9.]+)\s*s）')
RE_TTS_MODEL = re.compile(r'\[tts_engine\]\s*加载模型：device=(\S+)')
# 🔴🔴 **ASR 就绪在 GUI 模式下只写状态栏**（`var_status.set`，L3367）
#   ⇒ **不落盘会话日志** ⇒ 上一版判据用 CLI 模式的串 `[gpu_int8] 加载 x s`
#   在 GUI 臂上**恒为 None** ⇒ 假 FAIL（app280 首跑 3 PASS / 1 FAIL 即此因）。
#   ⇒ 改用**独立且更强**的判据：**字幕区有实际内容**（像素判据）
#      ⇒ 同时证明 ASR 出字 ＋ MT 翻译 ＋ 渲染 三条链路都通了。
#      保留 RE_ASR_LOAD2 仅作**补充信息**（不参与判定）。
RE_ASR_LOAD = re.compile(r'\[gpu_int8\]\s+加载\s+([0-9.]+)\s*s')
RE_ASR_LOAD2 = re.compile(r'加载\s+Intel GPU[^）]*?（ov-int8-past）')
RE_MT_LOAD = re.compile(r'翻译模型就绪（([^）]+?)，加载\s+([0-9.]+)\s*s）')

user32 = ctypes.windll.user32


# ══════════════════════════════════════════════════════════════════════
# 抓屏
# ══════════════════════════════════════════════════════════════════════
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _client_size(hwnd):
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
    """全部可见且标题含关键字的窗口（Tk 会建多个同名窗口）。"""
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


def _caption_ink(path):
    """🔴 **字幕区墨迹像素统计**（判据用）。

    只数「深色像素」⇒ 不依赖颜色/字体 ⇒ 跨缩放稳定。
    返回 (有内容的行数, 单行最大墨迹像素数, 区域尺寸)。
    """
    from PIL import Image
    im = Image.open(path).convert('L')
    W, H = im.size
    # 字幕区：主窗口客户区左侧，避开顶部 5 个分组（约 y 190–230）
    box = (25, 215, max(30, W - 335), min(H - 60, 560))
    c = im.crop(box)
    w, h = c.size
    px = c.load()
    rows_ink = 0
    row_max = 0
    for y in range(h):
        n = 0
        for x in range(w):
            if px[x, y] < 200:
                n += 1
        if n >= 3:
            rows_ink += 1
        if n > row_max:
            row_max = n
    # 🔴 **负对照**：同宽度、位于字幕区**下方空白处**的同尺寸区域
    #   ⇒ 空白区必须为 0 墨迹 ⇒ 证明判据不是恒真。
    ctrl_box = (25, min(H - 60, 700), max(30, W - 335), min(H - 60, 1045))
    cc = im.crop(ctrl_box)
    cw, ch = cc.size
    cp = cc.load()
    ctrl_rows = 0
    ctrl_max = 0
    for y in range(ch):
        n = 0
        for x in range(cw):
            if cp[x, y] < 200:
                n += 1
        if n >= 3:
            ctrl_rows += 1
        if n > ctrl_max:
            ctrl_max = n
    return rows_ink, row_max, [w, h], ctrl_rows, ctrl_max


def grab_one(hwnd, path):
    wc = _load('win_capture_mod', os.path.join(HERE, 'win_capture.py'))
    try:
        ok = wc.capture_hwnd(hwnd, path)
    except Exception as e:
        return {'ok': False, 'why': repr(e)}
    info = {'ok': bool(ok),
            'bytes': (os.path.getsize(path) if os.path.isfile(path) else None)}
    if info['bytes'] is not None:
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
        info['why'] = 'capture_hwnd 未产出文件'
    return info


def grab_best(path):
    """按**面积**取最大的非黑窗口（真主窗口）；全部候选写同一 .cand 文件。"""
    cands = find_candidates()
    tried = []
    best = None
    tmp = path + '.cand'
    for c in cands:
        area = (c['rect'][0] * c['rect'][1]) if c.get('rect') else 0
        info = grab_one(c['hwnd'], tmp)
        info.update({'hwnd': c['hwnd'], 'rect': c['rect'],
                     'client': c['client'], 'area': area})
        tried.append(info)
        if info.get('ok') and not info.get('all_black'):
            if best is None or area > best.get('area', 0):
                best = info
    if best is None:
        return {'ok': False,
                'why': '没有抓到有效内容（%d 个候选窗口全失败/全黑）' % len(cands),
                'n_candidates': len(cands), 'tried': tried}
    for c in cands:
        if c['hwnd'] == best['hwnd']:
            grab_one(c['hwnd'], path)
            break
    best = dict(best)
    best['tried'] = [dict(t) for t in tried]
    best['n_candidates'] = len(cands)
    return best


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


def run_gui(pkg, localapp, wav, seconds, tag, timeout_s=1500.0):
    py = os.path.join(pkg, 'python', 'python.exe')
    app = os.path.join(pkg, 'app', 'live_caption_app.py')
    selftest = os.path.join(OUT_DIR, 'selftest_%s' % tag)
    log_path = os.path.join(OUT_DIR, 'gui_%s.log' % tag)
    shot_path = os.path.join(OUT_DIR, 'gui_%s.png' % tag)

    cmd = [py, app,
           '--source', 'file', '--file', wav,
           '--autostart', '--selftest', str(int(seconds)),
           '--selftest-out', selftest,
           '--tts', 'on', '--tts-voice', 'A', '--speaker', 'off',
           '--asr-device', 'GPU.0', '--mt-device', 'GPU.0',
           '--tts-device', 'NPU', '--translate', 'zh',
           '--mt-engine', 'gpu_int4cw']

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
    shot = None
    shot_first = None
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
        cand = grab_best(shot_path)
        if cand.get('ok'):
            n_captures += 1
            cand['at_s'] = round(time.time() - t0, 1)
            if shot_first is None:
                shot_first = dict(cand)
            cl = cand.get('client') or []
            if cl and cl[1] >= 700:
                shot = cand
        slog = newest_session_log(localapp, t0)
        if slog:
            try:
                with open(slog, encoding='utf-8', errors='replace') as f:
                    txt = f.read()
            except OSError:
                txt = ''
            if RE_TTS_LOAD.search(txt):
                model_loaded_at = round(time.time() - t0, 1)
                if shot is not None:
                    stopped_reason = '模型加载完成 ⇒ 停'
                    break
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=25)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
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
    m = RE_TTS_LOAD.search(merged)
    mt = RE_MT_LOAD.search(merged)
    asr = RE_ASR_LOAD.search(merged)
    res = {'tag': tag, 'cmd': cmd, 'pkg': pkg,
           'localappdata': localapp, 'wav': wav,
           'rc': proc.poll(), 'exit_code_early': exit_code,
           'wall_s': round(wall, 2),
           'stopped_reason': stopped_reason,
           'model_loaded_at_s': model_loaded_at,
           'shot': shot, 'shot_first': shot_first,
           'n_captures': n_captures, 'shot_path': shot_path,
           'log_path': log_path, 'session_log': slog,
           'log_bytes': len(text.encode('utf-8', 'replace')),
           'log_tail': text[-2000:],
           'session_log_bytes': len(stext.encode('utf-8', 'replace')),
           'session_log_tail': stext[-2000:],
           'tts_load_s': (float(m.group(1)) if m else None),
           'mt_load_s': (float(mt.group(2)) if mt else None),
           'mt_label': (mt.group(1) if mt else None),
           'asr_load_s': (float(asr.group(1)) if asr else None),
           'asr_load_seen': bool(asr or RE_ASR_LOAD2.search(merged)),
           'tts_device': ((RE_TTS_MODEL.search(merged).group(1))
                          if RE_TTS_MODEL.search(merged) else None),
           'selftest_files': (sorted(os.listdir(selftest))
                              if os.path.isdir(selftest) else []),
           }
    # 🔴 字幕区墨迹（判据③的核心）
    if shot and os.path.isfile(shot_path):
        try:
            rows_ink, row_max, area, ctrl_rows, ctrl_max = _caption_ink(shot_path)
            res['caption_ink'] = {'rows_with_ink': rows_ink,
                                  'max_row_ink': row_max,
                                  'region': area,
                                  'control_rows_with_ink': ctrl_rows,
                                  'control_max_row_ink': ctrl_max}
        except Exception as e:
            res['caption_ink'] = {'error': repr(e)}
    print('[%s] wall=%s s  TTS 加载=%s s  model_loaded_at=%s s  rc=%s  shot=%s'
          % (tag, res['wall_s'], res['tts_load_s'], model_loaded_at,
             res['rc'],
             json.dumps({k: (shot or {}).get(k) for k in
                         ('ok', 'size', 'bytes', 'all_black', 'client')},
                        ensure_ascii=False) if shot else 'None'),
          flush=True)
    return res


OUT_DIR = os.path.join(HERE, 'app280_rc3_gui')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--pkg', default=os.path.join(CLEANTEST, PKG_NAME))
    ap.add_argument('--timeout', type=float, default=1500.0)
    ap.add_argument('--out', default=os.path.join(
        HERE, 'app280_rc3_gui_smoke_evidence.json'))
    args = ap.parse_args()

    out = {'script': '_app280_rc3_gui_smoke.py',
           'correction': 'APP-072 §2 闸门③（GUI 冒烟部分）',
           'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
           'cfg': vars(args), 'checks': [], 'runs': []}

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

    if not os.path.isdir(args.pkg):
        print('!! 解压副本不存在：%s' % args.pkg)
        out['verdict'] = 'NO_CLEANTEST'
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        return 3

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
    out['lock'] = str(payload)

    try:
        ok_q, qinfo = ml.wait_quiet_window_cpu(quiet_seconds=45.0,
                                                timeout=1800.0, verbose=True)
        out['quiet_window'] = {'ok': ok_q, 'info': str(qinfo)}
        if ok_q is False:
            print('[quiet] !! 等不到安静窗口 ⇒ 退出')
            out['verdict'] = 'NOT_QUIET'
            return 3

        # 🔴 用**本机默认 LOCALAPPDATA**（含已编译的 NPU blob）
        #   ⇒ 命中缓存 ⇒ 不必等 20 分钟冷编译；本轮验的是「GUI 能不能起来」。
        localapp = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
        res = run_gui(args.pkg, localapp, SRC_WAV, 500, 'rc3',
                      timeout_s=args.timeout)
        out['runs'].append(res)

        sh = res.get('shot') or {}
        cl = sh.get('client') or []
        is_main = bool(cl) and cl[1] >= 700
        add('① GUI 起得来且模型加载完成（无崩溃）',
            res.get('tts_load_s') is not None,
            {'tts_load_s': res.get('tts_load_s'),
             'model_loaded_at_s': res.get('model_loaded_at_s'),
             'wall_s': res.get('wall_s'), 'rc': res.get('rc'),
             'tts_device': res.get('tts_device'),
             'stopped_reason': res.get('stopped_reason')})
        add('② 抓到**完整主窗口**且非黑图',
            bool(sh.get('ok') and not sh.get('all_black') and is_main),
            {'ok': sh.get('ok'), 'all_black': sh.get('all_black'),
             'bytes': sh.get('bytes'), 'size': sh.get('size'),
             'client': sh.get('client'), 'is_main_window': is_main,
             'n_candidates': sh.get('n_candidates'),
             'note': '客户区高 ≥ 700 px 才是主窗口'})
        # 🔴🔴 **判据③ 改为「字幕区有内容」**（而不是抓 ASR 加载耗时串）
        #   理由见 RE_ASR_LOAD2 处的注释：GUI 模式下 ASR 就绪只写状态栏不落盘
        #   ⇒ 抓 CLI 串 ⇒ 恒 None ⇒ 假 FAIL。
        #   「字幕区有墨迹」是**更强**的判据：同时证明 ASR 出字 ＋ MT 翻译 ＋ 渲染。
        ink = res.get('caption_ink') or {}
        ink_ok = bool(ink.get('rows_with_ink', 0) >= 20
                      and ink.get('max_row_ink', 0) >= 50)
        add('③ ASR 出字 + MT 翻译 + 字幕渲染都通（字幕区有实际内容）',
            ink_ok,
            {'caption_ink': ink,
             'mt_load_s': res.get('mt_load_s'),
             'mt_label': res.get('mt_label'),
             'asr_load_seen': res.get('asr_load_seen'),
             'note': '判据＝字幕区深色像素行数 ≥ 20 且单行墨迹 ≥ 50 px；'
                     'GUI 模式下 ASR 就绪不落盘 ⇒ 不能抓 CLI 的加载耗时串'})
        # 🔴🔴 **负对照**：字幕区**下方空白区**必须 0 墨迹 ⇒ 证明判据非恒真
        add('③b 负对照：字幕区下方空白区 0 墨迹（判据非恒真）',
            ink.get('control_rows_with_ink', -1) == 0
            and ink.get('control_max_row_ink', -1) == 0,
            {'control_rows_with_ink': ink.get('control_rows_with_ink'),
             'control_max_row_ink': ink.get('control_max_row_ink')})
        crash = ('0xC0000409' in (res.get('log_tail') or '')
                 or '0xC0000409' in (res.get('session_log_tail') or ''))
        add('④ 日志里没有 0xC0000409 崩溃', not crash,
            {'crash_marker_found': crash,
             'rc': res.get('rc'),
             'stopped_reason': res.get('stopped_reason')})
    finally:
        try:
            ml.release(payload, verbose=True)
        except Exception as e:
            print('[lock] release 失败：%r' % e)

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
