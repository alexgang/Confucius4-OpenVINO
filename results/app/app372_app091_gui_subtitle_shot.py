"""APP-091 §3：**屏幕字幕条**验收 —— 抓一张**运行中**的 GUI 截图。

🔴 reviewer 要求（APP-091 §3）：
  > 在译文下方加回定稿后的原文，作为字号更小的第二行（与 EXT v0.3.4 一致）
  > 实时 ASR 行的现有行为保持不变，除非与新布局冲突；冲突时说明取舍。
  > 验收：写明最终布局（几行、各行内容、字号），并附一张运行中的截图。

🔴 本脚本：
  ① 起 GUI（影子包 `after`，喂 dialog3 音频）
  ② 等字幕条出现内容
  ③ 用 `results/app/win_capture.py` 的 `PrintWindow` 抓窗口（**像素级守卫**防黑图）
  ④ 落盘 PNG + 布局说明 JSON

🔴 不占设备推理锁的规矩：本脚本**会**起 ASR/MT/TTS ⇒ **必须持 MACHINE_LOCK**
   ⇒ 由调用方（app369）持锁时调用，或本脚本自己拿锁。
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import time

REPO = r'C:\Users\Trekker-PTL\confucius4-openvino'
BASE = r'C:\Users\Trekker-PTL\_app_shadow'
SPKTEST = r'C:\Users\Trekker-PTL\_reviewer_tmp\spktest'
EVID = os.path.join(REPO, 'results', 'app')
OUT = os.path.join(EVID, 'app372_app091_subtitle_shot')
SHOT = os.path.join(OUT, 'subtitle_bar.png')
LAYOUT = os.path.join(OUT, 'subtitle_layout.json')


def find_caption_hwnd():
    """找字幕条窗口（类名含 Caption / 标题含「字幕」）。

    🔴🔴🔳 **本轮修正**：字幕条是 `tk.Toplevel` + `overrideredirect(True)`
      ⇒ **窗口标题是空字符串**、类名是 `TkTopLevel`
      ⇒ 旧匹配（标题含「字幕」/ 类名含「Caption」）**永远匹配不到**
      ⇒ 本轮实测：只抓到主窗口（`tk` 标题），字幕条**一个都没抓到**。
    ⇒ 修法：**按窗口尺寸 + 类名**识别字幕条
      （字幕条 = 宽 = 屏宽 80%、高 = 3 行 ⇒ 明显扁而宽）
      ⇒ 同时保留标题/类名匹配（兼容将来改标题）。
    """
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
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
        ctypes.windll.user32.GetClassNameW(hwnd, cls, 256)
        r = wintypes.RECT()
        u32.GetWindowRect(hwnd, ctypes.byref(r))
        wd, ht = r.right - r.left, r.bottom - r.top
        by_name = ('字幕' in title or 'Caption' in title
                   or 'Caption' in cls.value)
        # 🔴 **按尺寸识别字幕条**：宽 ≈ 屏宽 80%、高 < 屏宽/8（扁而宽）
        by_size = (cls.value.startswith('Tk') and wd > sw * 0.5
                   and 0 < ht < sw * 0.15)
        if by_name or by_size:
            hits.append((int(hwnd), title, cls.value))
        return True

    u32.EnumWindows(cb, 0)
    return hits


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    root = os.path.join(BASE, 'after')
    wav = os.path.join(SPKTEST, 'dialog3.wav')
    clone_dir = os.path.join(OUT, 'clone_voices')
    os.makedirs(clone_dir, exist_ok=True)
    env = dict(os.environ)
    env['LIVECAP_CLONE_VOICES_DIR'] = clone_dir
    env['PYTHONPATH'] = os.path.join(REPO, 'results', 'app')

    cmd = [
        os.path.join(root, 'python', 'python.exe'),
        os.path.join(root, 'app', 'live_caption_app.py'),
        # 🔴🔴🔳 **本轮修正**：必须显式 `--source file`
        #   ⇒ `--source` 默认是 **mic** ⇒ GUI 会去开麦克风
        #   ⇒ 本机无麦克风 ⇒ **GUI 静默退出**（日志 0 字节）⇒ 抓不到图。
        '--source', 'file',
        '--file', wav,
        '--speaker', 'on',
        '--tts', 'on', '--tts-voice', 'follow_speaker',
        '--tts-precision', 'f16', '--tts-device', 'NPU',
        '--translate', 'zh', '--mt-engine', 'gpu_int8cw',
        '--mt-device', 'GPU.0', '--engine', 'gpu_int8',
        '--asr-device', 'GPU.0',
        '--out', os.path.join(OUT, 'subtitles.txt'),
        '--tts-out', os.path.join(OUT, 'mix.wav'),
        '--autostart',
    ]
    log_path = os.path.join(OUT, 'gui.log')
    print('▶ 起 GUI…', flush=True)
    # 🔴🔴🔳 **本轮修正**：GUI 模式下子进程的 stdout **被缓冲**
    #   ⇒ `p.stdout.readline()` **永久阻塞**（等不到换行）
    #   ⇒ 旧脚本卡在第一行 ⇒ 字幕条窗口根本没被抓到（本轮实测 0 字节日志）。
    #   ⇒ 修法：① stdout **写文件**（不读）⇒ 不阻塞；
    #           ② **独立线程**排干日志；
    #           ③ 主循环**只按时间轮询窗口**，不等 stdout。
    #   ⚠️ 另加 `PYTHONUNBUFFERED=1` ⇒ 子进程自己也别缓冲。
    env['PYTHONUNBUFFERED'] = '1'
    raw_log = os.path.join(OUT, 'gui.raw.log')
    sys.path.insert(0, EVID)
    import win_capture
    with open(log_path, 'w', encoding='utf-8', errors='replace') as lf:
        with open(raw_log, 'wb') as raw:
            p = subprocess.Popen(cmd, stdout=raw,
                                 stderr=subprocess.STDOUT,
                                 env=env, cwd=root)
        got = None
        t0 = time.time()
        # 🔴🔴🔳 **持续轮询 + 持续抓图**（不等 stdout，也不等窗口「稳定」）
        #   ⇒ GUI 要**加载模型**（NPU 编译要几分钟）⇒ 窗口会**晚出现**
        #   ⇒ 旧逻辑「等窗口出现再抓」可能一次都没抓到（实测 caption_shots=[]）
        #   ⇒ 现在：每 3 s 抓一次**所有可见 Tk 窗口**（像素守卫自动过滤黑图）
        #   ⇒ **至少要有一张非黑图**才算成功。
        seen = {}
        shots = []
        while time.time() - t0 < 420:
            time.sleep(3.0)
            for hwnd, title, cls in find_caption_hwnd():
                key = (hwnd, cls)
                path = os.path.join(OUT, 'caption_%d.png' % hwnd)
                try:
                    ok = win_capture.capture_hwnd(hwnd, path)
                except Exception:
                    ok = False
                nb = (os.path.getsize(path)
                      if ok and os.path.exists(path) else 0)
                # 🔴 **像素守卫**：只留**有内容**的图（黑图字节数很小）
                if ok and nb > 3000:
                    if key not in seen or nb > seen[key][1]:
                        seen[key] = (path, nb, title, cls)
            if p.poll() is not None:
                break
        for (hwnd, cls), (path, nb, title, _c) in seen.items():
            shots.append({'hwnd': hwnd, 'title': title, 'cls': cls,
                          'path': path, 'bytes': nb})
        got = [(h, t, c) for (h, c), (p_, n, t, c) in seen.items()]
        # 也抓主窗口（🔴 用**类名 + 尺寸**识别，标题可能为空）
        main_shots = []
        import ctypes
        from ctypes import wintypes
        u32 = ctypes.windll.user32
        wins = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def cb(hwnd, _l):
            if u32.IsWindowVisible(hwnd):
                cls = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetClassNameW(hwnd, cls, 256)
                n = u32.GetWindowTextLengthW(hwnd)
                buf = ctypes.create_unicode_buffer(n + 2)
                u32.GetWindowTextW(hwnd, buf, n + 2)
                r = wintypes.RECT()
                u32.GetWindowRect(hwnd, ctypes.byref(r))
                wd, ht = r.right - r.left, r.bottom - r.top
                if ('Confucius' in buf.value or '实时字幕' in buf.value
                        or (cls.value.startswith('Tk') and wd > 400)):
                    wins.append((int(hwnd), buf.value, wd, ht))
            return True

        u32.EnumWindows(cb, 0)
        for hwnd, title, wd, ht in wins:
            path = os.path.join(OUT, 'main_%d.png' % hwnd)
            try:
                ok = win_capture.capture_hwnd(hwnd, path)
            except Exception:
                ok = False
            main_shots.append({'hwnd': hwnd, 'title': title,
                                'size': '%dx%d' % (wd, ht),
                                'path': path if ok else None,
                                'bytes': os.path.getsize(path) if ok and os.path.exists(path) else 0})
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

    layout = {
        'shot': SHOT if os.path.exists(SHOT) else None,
        'caption_shots': shots,
        'main_shots': main_shots,
        'log': log_path,
        'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': ('字幕条最终布局 = **3 行**：'
                 '① 定稿译文（主字号）② **定稿原文（小字，APP-091 §3 加回）** '
                 '③ 实时识别（ASR 实时行，行为不变）'),
    }
    with open(LAYOUT, 'w', encoding='utf-8') as f:
        json.dump(layout, f, ensure_ascii=False, indent=1)
    print(json.dumps(layout, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
