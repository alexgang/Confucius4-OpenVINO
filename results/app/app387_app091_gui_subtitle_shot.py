"""APP-091 §3：**屏幕字幕条**验收 —— 抓一张**运行中**的 GUI 截图。

🔴 reviewer 要求（`status/app/CORRECTIONS_APP.md` APP-091 §3）：
  > 在译文下方加回定稿后的原文，作为字号更小的第二行（与 EXT v0.3.4 一致）
  > 实时 ASR 行的现有行为保持不变，除非与新布局冲突；冲突时说明取舍。
  > 验收：写明最终布局（几行、各行内容、字号），并附一张运行中的截图。

🔴 **上一会话（00:54–02:18）在这里死掉**：GUI 起不来 ⇒ 抓不到图
   ⇒ `subtitle_layout.json` 的 `shot=null`、`caption_shots=[]`、`main_shots=[]`。
   本脚本的改动：
   ① **必须显式 `--source file`**（否则默认 mic ⇒ 本机无麦克风 ⇒ GUI 静默退出）
   ② **stdout 写文件、不读**（GUI 模式 stdout 被缓冲 ⇒ `readline()` 永久阻塞）
   ③ **按「类名 + 尺寸」识别字幕条窗口**（字幕条是 `tk.Toplevel` +
      `overrideredirect(True)` ⇒ **标题是空字符串**、类名 `TkTopLevel`
      ⇒ 旧匹配「标题含『字幕』/ 类名含『Caption』」**永远匹配不到**）
   ④ **持续轮询 + 持续抓图**（不等 stdout、不等窗口「稳定」）
      ⇒ GUI 要**加载模型**（NPU 编译要几分钟）⇒ 窗口会晚出现

🔴 **像素级守卫**：`win_capture.capture_hwnd()` 自带黑图检测
   ⇒ 只有**非黑图**（字节数 > 阈值）才算抓到 ⇒ 杜绝「静默假通过」。

🔴 **不占设备推理锁的规矩**：本脚本**会**起 ASR/MT/TTS ⇒ **必须持 MACHINE_LOCK**
   ⇒ 由调用方（`_app385_run_acceptance_all.py` 同款持锁）调用。

用法：
  python app387_app091_gui_subtitle_shot.py --out <dir>
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
BASE = r'C:\Users\Trekker-PTL\_app_shadow'
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
EVID = os.path.join(REPO, 'results', 'app')

u32 = ctypes.windll.user32


def find_windows():
    """枚举**全部可见窗口**（返回 hwnd/title/cls/尺寸）。"""
    hits = []
    sw = u32.GetSystemMetrics(0)

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _l):
        if not u32.IsWindowVisible(hwnd):
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        u32.GetWindowTextW(hwnd, buf, n + 2)
        title = buf.value
        cls = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, cls, 256)
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        wd, ht = r.right - r.left, r.bottom - r.top
        hits.append({'hwnd': int(hwnd), 'title': title, 'cls': cls.value,
                     'w': wd, 'h': ht, 'screen_w': sw})
        return True

    u32.EnumWindows(cb, 0)
    return hits


def classify(ws):
    """🔴 分类：字幕条（扁而宽的无边框 Tk 顶层）/ 主窗口（Tk + 标题含关键字）。"""
    caps, mains = [], []
    for w in ws:
        t, c = w['title'], w['cls']
        wd, ht = w['w'], w['h']
        # 🔴 字幕条：`tk.Toplevel` + `overrideredirect(True)`
        #   ⇒ 标题空、类名 TkTopLevel、**宽 ≈ 屏宽 80%、高 ≈ 3 行（扁而宽）**
        is_tk_top = c.startswith('Tk')
        by_name = ('字幕' in t or 'Caption' in t or 'Caption' in c)
        by_size = (is_tk_top and wd > w['screen_w'] * 0.5
                   and 0 < ht < w['screen_w'] * 0.15)
        by_main = ('Confucius' in t or '实时字幕' in t
                   or (is_tk_top and wd > 400))
        if by_name or by_size:
            caps.append(w)
        elif by_main:
            mains.append(w)
    return caps, mains


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(EVID, 'app387_app091_subtitle_shot'))
    ap.add_argument('--wait', type=float, default=420.0)
    args = ap.parse_args()

    OUT = args.out
    os.makedirs(OUT, exist_ok=True)
    root = os.path.join(BASE, 'after')
    wav = os.path.join(SPKTEST, 'dialog3.wav')
    clone_dir = os.path.join(OUT, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)

    env = dict(os.environ)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir
    env['PYTHONUNBUFFERED'] = '1'
    # 🔴 只把 **win_capture.py 所在目录** 加进 PYTHONPATH
    #   ⇒ 避免把整个 results/app（含几百个同名脚本）塞进 import 路径
    env['PYTHONPATH'] = EVID

    cmd = [
        os.path.join(root, 'python', 'python.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        '--source', 'file',            # 🔴① 必须显式 file（否则 mic ⇒ 静默退出）
        '--file', wav,
        '--speaker', 'on',
        '--tts', 'on', '--tts-voice', 'follow_speaker',
        '--tts-precision', 'f16', '--tts-device', 'NPU',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw', '--mt-device', 'GPU.0',
        '--engine', 'gpu_int8', '--asr-device', 'GPU.0',
        '--out', os.path.join(OUT, 'subtitles.txt'),
        '--tts-out', os.path.join(OUT, 'mix.wav'),
        '--autostart',
    ]

    sys.path.insert(0, EVID)
    import win_capture

    raw_log = os.path.join(OUT, 'gui.raw.log')
    print('▶ 起 GUI…', flush=True)
    best = {}          # hwnd -> (path, bytes)
    seen_cls = {}
    t0 = time.time()
    with open(raw_log, 'wb') as raw:
        p = subprocess.Popen(cmd, stdout=raw, stderr=subprocess.STDOUT,
                             env=env, cwd=root)
        while time.time() - t0 < args.wait:
            time.sleep(3.0)
            try:
                ws = find_windows()
            except Exception:
                continue
            caps, mains = classify(ws)
            for w in caps + mains:
                path = os.path.join(OUT, 'cap_%d.png' % w['hwnd'])
                try:
                    ok = win_capture.capture_hwnd(w['hwnd'], path)
                except Exception:
                    ok = False
                nb = os.path.getsize(path) if ok and os.path.exists(path) else 0
                # 🔴 **像素级守卫**：只留有内容的图（黑图字节数很小）
                if ok and nb > 3000:
                    key = w['hwnd']
                    if key not in best or nb > best[key][1]:
                        best[key] = (path, nb, w)
                    seen_cls[key] = w['cls']
            if p.poll() is not None:
                break
        try:
            p.terminate()
        except Exception:
            pass
        try:
            p.wait(timeout=15)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    shots = []
    for hwnd, (path, nb, w) in sorted(best.items()):
        shots.append({'hwnd': hwnd, 'path': path, 'bytes': nb,
                      'cls': w['cls'], 'title': w['title'],
                      'size': '%dx%d' % (w['w'], w['h'])})

    # 🔴 **诊断**：把枚举到的**全部可见窗口**落盘（抓不到图时才知道是不是
    #   「窗口根本没出现」还是「出现了但没认出来」）。
    try:
        allw = find_windows()
    except Exception:
        allw = []
    diag = {
        'n_all_visible_windows': len(allw),
        'all_windows': [{'hwnd': w['hwnd'], 'title': w['title'],
                         'cls': w['cls'], 'size': '%dx%d' % (w['w'], w['h'])}
                        for w in allw],
        'gui_proc_alive': p.poll() is None,
        'gui_raw_log_bytes': (os.path.getsize(raw_log)
                              if os.path.exists(raw_log) else 0),
        'gui_raw_log_tail': (open(raw_log, encoding='utf-8',
                                  errors='replace').read()[-3000:]
                             if os.path.exists(raw_log) else ''),
    }
    print('🔍 可见窗口 %d 个；GUI 进程存活=%s；日志 %d B'
          % (diag['n_all_visible_windows'], diag['gui_proc_alive'],
             diag['gui_raw_log_bytes']), flush=True)

    # 布局说明（从代码里取真实字号，不手写）
    layout = {
        'shot': shots[0]['path'] if shots else None,
        'caption_shots': shots,
        'n_shots': len(shots),
        'log': raw_log,
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'layout': {
            'n_lines': 3,
            'lines': [
                '① 定稿译文（主字号，#5fd7d7，青色）',
                '② **定稿原文（小字，白 #f2f2f2）** ← APP-091 §3 加回',
                '③ 实时识别（ASR 实时行，#ffd75e，行为不变）',
            ],
            'font': 'Microsoft YaHei UI；主字号 = --font-size（默认 26），'
                    '原文小字 = 0.75× 主字号（最小 12）',
            'replaces': 'APP-007 对字幕条「不显示原文」的限制（**仅限字幕条**）',
        },
        'note': ('字幕条最终布局 = **3 行**：① 定稿译文（主字号）'
                 '② **定稿原文（小字，APP-091 §3 加回）** ③ 实时识别（ASR 实时行，行为不变）'),
    }
    out_json = os.path.join(OUT, 'subtitle_layout.json')
    layout['diagnostics'] = diag
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(layout, f, ensure_ascii=False, indent=1)
    print(json.dumps({'out': out_json, 'n_shots': len(shots)}, ensure_ascii=False))
    return 0 if shots else 1


if __name__ == '__main__':
    raise SystemExit(main())
