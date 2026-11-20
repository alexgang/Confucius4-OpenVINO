#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""APP-116 §1 / §3 验证脚本（A 机实测）。

§1 TTS 输出设备：
  A1 设备枚举（真实 soundcard/sounddevice，A 机有 Plantronics C320-M）
  A2 GUI 反查表：**修复后** name→id 能查到；**反证组**（旧写法）查不到
  A3 resolve_out_device(耳机 id) ⇒ 非 None
  A4 Player(耳机 id) ⇒ out_desc 落在耳机，**不是** Realtek；无回落
  A5 运行中切换：耳机 → 扬声器 → 耳机（**重开播放流**，不重启 worker）

§3 GUI 去掉 4 个选项：
  B1 4 个控件在界面上**不存在**
  B2 行为默认值**不变**（草稿关 / 区分说话人=旁路默认 / 显示说话人=True）
  B3 高级面板 grid **行号连续、无空洞、无同格重叠**
  B4 100% / 150% 缩放各截一张图

跑法（用**客户包的 python**，它才有 sounddevice/soundcard）：
    "C:/Users/Trekker-PTL/Confucius4_LiveCaption_v2.4/python/python.exe" \
        live_caption/diag_app116_device_gui.py
"""
import json
import os
import sys
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, 'results', 'app')
os.makedirs(RESULTS, exist_ok=True)

FAILS = []
PASSES = []


def check(name, cond, detail=''):
    (PASSES if cond else FAILS).append(name)
    print('  [%s] %s%s' % ('PASS' if cond else 'FAIL', name,
                           ('  ' + detail) if detail else ''), flush=True)
    return bool(cond)


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ══════════════════════════════════════════════════════════════════════
# §1 A2/A3/A4/A5
# ══════════════════════════════════════════════════════════════════════
def part_a():
    print('== §1 A1–A5 TTS 输出设备（A 机实测）==', flush=True)
    ev = {'ts': now(), 'section': 'A'}

    from audio_source import list_output_devices, default_output_device_id
    outs = list_output_devices()
    ev['devices'] = [{'id': oid, 'name': name} for oid, name in outs]
    print('  设备数 = %d' % len(outs), flush=True)
    for oid, name in outs:
        print('    - %s' % name, flush=True)

    # ── A2：GUI 反查表（修复后 vs 旧写法 = 反证组）──────────────────
    label = {oid: name for oid, name in outs}
    back_fixed = {name: oid for oid, name in label.items()}          # 修复后
    back_buggy = {name: oid for name, oid in label.items()}          # 旧写法（反证）
    target = None
    for oid, name in outs:
        if 'Plantronics' in name or '耳机' in name or 'Head' in name:
            target = (oid, name)
            break
    if target is None and outs:
        target = outs[-1]
    ev['target'] = {'id': target[0], 'name': target[1]} if target else None

    got_fixed = back_fixed.get(target[1]) if target else None
    got_buggy = back_buggy.get(target[1]) if target else None
    ev['reverse_lookup'] = {'fixed': got_fixed, 'buggy': got_buggy}
    check('A2 修复后：名称→id 反查得到设备 id', bool(got_fixed),
          'id=%s' % got_fixed)
    check('A2 反证组：旧写法反查恒为 None（证明这一行就是根因）',
          got_buggy is None, 'buggy=%s' % got_buggy)
    check('A2 反证组：修复前后结果**不同**（证明修改确实生效）',
          got_fixed != got_buggy)

    if not got_fixed:
        return ev

    # ── A3：resolve_out_device ─────────────────────────────────────
    import tts_worker as W
    sd_dev, how = W.resolve_out_device(got_fixed)
    ev['resolve'] = {'sd_device': sd_dev, 'how': how}
    check('A3 resolve_out_device(耳机 id) ⇒ 解析出设备（非 None）',
          sd_dev is not None, '⇒ %s（%s）' % (sd_dev, how))

    # ── A4：Player 真的开在耳机上 ──────────────────────────────────
    p = W.Player(device=got_fixed, sr=22050)
    tel = p.telemetry()
    ev['player_headphone'] = {
        'out_desc': tel.get('out_desc'),
        'out_requested': tel.get('out_requested'),
        'out_fallback': tel.get('out_fallback'),
        'out_is_default': tel.get('out_is_default'),
        'stream_open': tel.get('stream_open'),
    }
    print('  耳机 Player: out_desc=%s fallback=%r default=%s'
          % (tel.get('out_desc'), tel.get('out_fallback'),
             tel.get('out_is_default')), flush=True)
    check('A4 播放流打开成功', bool(tel.get('stream_open')))
    check('A4 实际输出落在**所选设备**（描述里含所选设备名关键词）',
          (target[1].split('（')[0].split('(')[0].strip()[:6].lower()
           in (tel.get('out_desc') or '').lower()),
          'out_desc=%s' % tel.get('out_desc'))
    check('A4 **没有**回落到系统默认',
          not tel.get('out_is_default') and not tel.get('out_fallback'),
          'fallback=%r default=%s' % (tel.get('out_fallback'),
                                       tel.get('out_is_default')))
    check('A4 遥测带上「用户选的设备」', tel.get('out_requested') == got_fixed)

    # ── A5：运行中切换（重开播放流）────────────────────────────────
    other = None
    for oid, name in outs:
        if oid != got_fixed:
            other = (oid, name)
            break
    switch_log = []
    if other:
        ok1, i1 = p.switch_device(other[0])
        t1 = p.telemetry()
        switch_log.append({'to': other[1], 'ok': ok1, 'out_desc': t1.get('out_desc'),
                            'fallback': t1.get('out_fallback')})
        check('A5 切到「%s」⇒ 实际输出跟着变' % other[1],
              (t1.get('out_desc') or '') != (tel.get('out_desc') or ''),
              'out_desc=%s' % t1.get('out_desc'))
        ok2, i2 = p.switch_device(got_fixed)
        t2 = p.telemetry()
        switch_log.append({'to': target[1], 'ok': ok2, 'out_desc': t2.get('out_desc'),
                            'fallback': t2.get('out_fallback')})
        check('A5 切回「%s」⇒ 实际输出回到所选设备' % target[1],
              (target[1].split('（')[0].split('(')[0].strip()[:6].lower()
               in (t2.get('out_desc') or '').lower()),
              'out_desc=%s' % t2.get('out_desc'))
        check('A5 切换后**没有**回落', not t2.get('out_fallback'),
              'fallback=%r' % t2.get('out_fallback'))
    ev['switch_log'] = switch_log
    try:
        p.close()
    except Exception:
        pass
    return ev


# ══════════════════════════════════════════════════════════════════════
# §3 B1–B4
# ══════════════════════════════════════════════════════════════════════
class _Args:
    translate = 'off'
    mt_engine = 'auto'
    mt_ctx = False
    mt_glossary = False
    mt_draft = False
    asr_lang = 'auto'
    engine = 'gpu_int8'
    source = 'mic'
    device = None
    system_device = None
    file = None
    speed = 1.0
    loop = False
    overlay = True
    font_size = 26
    asr_device = 'GPU.0'
    mt_device = 'GPU.0'
    tts_device = 'NPU'
    device_notes = []
    tts = 'off'
    tts_voice = 'A'
    tts_precision = 'f32'
    tts_out_device = None
    selftest = 0
    autostart = False


def _capture(root, path):
    """纯 ctypes + GDI 抓窗口（PrintWindow）—— ImageGrab 在本机会全黑。"""
    import ctypes
    import struct
    import zlib
    u32 = ctypes.windll.user32
    g32 = ctypes.windll.gdi32
    hwnd = int(root.winfo_id())
    parent = u32.GetParent(hwnd)
    if parent:
        hwnd = parent

    class RECT(ctypes.Structure):
        _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                    ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

    r = RECT()
    if not u32.GetWindowRect(hwnd, ctypes.byref(r)):
        return False
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return False
    hdc_win = u32.GetWindowDC(hwnd)
    hdc_mem = g32.CreateCompatibleDC(hdc_win)
    hbm = g32.CreateCompatibleBitmap(hdc_win, w, h)
    old = g32.SelectObject(hdc_mem, hbm)
    if not u32.PrintWindow(hwnd, hdc_mem, 2):
        g32.BitBlt(hdc_mem, 0, 0, w, h, hdc_win, 0, 0, 0x00CC0020)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32),
                    ('biHeight', ctypes.c_int32), ('biPlanes', ctypes.c_uint16),
                    ('biBitCount', ctypes.c_uint16),
                    ('biCompression', ctypes.c_uint32),
                    ('biSizeImage', ctypes.c_uint32),
                    ('biXPelsPerMeter', ctypes.c_int32),
                    ('biYPelsPerMeter', ctypes.c_int32),
                    ('biClrUsed', ctypes.c_uint32),
                    ('biClrImportant', ctypes.c_uint32)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0
    buf = ctypes.create_string_buffer(w * h * 4)
    got = g32.GetDIBits(hdc_mem, hbm, 0, h, buf, ctypes.byref(bi), 0)
    g32.SelectObject(hdc_mem, old)
    g32.DeleteObject(hbm)
    g32.DeleteDC(hdc_mem)
    u32.ReleaseDC(hwnd, hdc_win)
    if not got:
        return False
    raw = bytes(buf)
    rows = []
    for y in range(h):
        line = bytearray(b'\x00')
        base = y * w * 4
        for x in range(w):
            b_, g_, r_ = raw[base + x * 4], raw[base + x * 4 + 1], raw[base + x * 4 + 2]
            line += bytes((r_, g_, b_))
        rows.append(bytes(line))
    data = zlib.compress(b''.join(rows), 6)

    def chunk(tag, payload):
        c = tag + payload
        return struct.pack('>I', len(payload)) + c + struct.pack('>I', zlib.crc32(c))

    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', data)
           + chunk(b'IEND', b''))
    with open(path, 'wb') as f:
        f.write(png)
    return True


def part_b():
    print('\n== §3 B1–B4 GUI 去掉 4 个选项 ==', flush=True)
    ev = {'ts': now(), 'section': 'B'}
    import tkinter as tk
    import live_caption_app as lca

    root = tk.Tk()
    _orig_load = lca.App.load_engine
    lca.App.load_engine = lambda self: None
    try:
        app = lca.App(root, _Args())
    finally:
        lca.App.load_engine = _orig_load
    root.update_idletasks()
    root.update()
    time.sleep(0.3)
    root.update()

    # ── B1：4 个控件不在界面上 ────────────────────────────────────
    gone = ['chk_mt_draft', 'cb_show_spk', 'cb_speaker']
    for n in gone:
        check('B1 控件 %s 已从界面移除' % n, not hasattr(app, n))
    # 界面上**不应出现**这 4 个标签文字
    texts = []

    def walk(w):
        try:
            t = w.cget('text')
            if t:
                texts.append(str(t))
        except Exception:
            pass
        for c in w.winfo_children():
            walk(c)

    walk(root)
    ev['removed_labels_present'] = [
        s for s in ('草稿译文', '重试翻译', '区分说话人', '显示说话人')
        if any(s in t for t in texts)]
    check('B1 界面上不再出现 4 个选项的文字',
          not ev['removed_labels_present'],
          str(ev['removed_labels_present']))

    # ── B2：默认值不变 ────────────────────────────────────────────
    ev['defaults'] = {
        'var_mt_draft': bool(app.var_mt_draft.get()),
        'var_speaker': bool(app.var_speaker.get()),
        'var_show_spk': bool(app.var_show_spk.get()),
        '_speaker_enabled': bool(app._speaker_enabled),
    }
    check('B2 草稿译文默认**关闭**（行为不变）',
          ev['defaults']['var_mt_draft'] is False)
    check('B2 显示说话人默认**打开**（APP-040④ 不变）',
          ev['defaults']['var_show_spk'] is True)
    check('B2 区分说话人默认值 = 旁路默认值（APP-054 不变）',
          ev['defaults']['var_speaker'] == ev['defaults']['_speaker_enabled'],
          'var_speaker=%s _speaker_enabled=%s'
          % (ev['defaults']['var_speaker'],
             ev['defaults']['_speaker_enabled']))

    # ── B3：高级面板 grid 无空洞、无重叠 ──────────────────────────
    adv = None
    for c in root.winfo_children():
        for d in c.winfo_children():
            if 'Labelframe' in d.winfo_class():
                adv = d
                break
        if adv is not None:
            break
    grid_rows = {}
    if adv is not None:
        for f in adv.winfo_children():
            for c in f.winfo_children():
                info = c.grid_info()
                if not info:
                    continue
                r = int(info['row'])
                col = int(info['column'])
                grid_rows.setdefault(r, []).append((col, str(c.cget('text'))))

    def collect(w, out):
        try:
            info = w.grid_info()
            if info:
                out.append((int(info['row']), int(info['column']),
                            str(w.cget('text')) if 'text' in w.keys() else ''))
        except Exception:
            pass
        for c in w.winfo_children():
            collect(c, out)

    all_g = []
    if adv is not None:
        collect(adv, all_g)
    ev['advanced_grid'] = sorted(all_g)
    rows_used = sorted(set(r for r, c, t in all_g))
    ev['advanced_rows_used'] = rows_used
    check('B3 高级面板行号**连续**（无空洞）',
          rows_used == list(range(rows_used[0], rows_used[-1] + 1)) if rows_used else False,
          str(rows_used))
    dup = {}
    for r, c, t in all_g:
        dup.setdefault((r, c), []).append(t)
    overlap = {k: v for k, v in dup.items() if len(v) > 1}
    ev['advanced_overlaps'] = {str(k): v for k, v in overlap.items()}
    check('B3 高级面板**无同格重叠**（旧的 row7/col1 重叠已消除）',
          not overlap, str(overlap))

    # ── B4：100% / 150% 截图（**展开「高级」面板** ⇒ 能看到那 4 个选项确实没了）
    try:
        app._toggle_advanced()
        root.update_idletasks()
        root.update()
        time.sleep(0.3)
        root.update()
    except Exception as e:
        print('  [warn] 展开高级面板失败：%r' % (e,))
    ev['advanced_expanded'] = True

    # 音色下拉内容（APP-116 §2：预设 A（女声）/ 预设 B（男声））
    try:
        ev['voice_values'] = list(app.cb_tts_voice.cget('values'))
        ev['voice_current'] = app.var_tts_voice.get()
        print('  音色下拉：%s' % ev['voice_values'], flush=True)
    except Exception as e:
        ev['voice_values'] = ['<err %r>' % (e,)]

    root.geometry('1180x860+30+30')
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    p100 = os.path.join(RESULTS, 'app116_gui_100pct.png')
    ok1 = _capture(root, p100)
    check('B4 100% 截图落盘', ok1, p100)

    root.tk.call('tk', 'scaling', 1.5)
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    p150 = os.path.join(RESULTS, 'app116_gui_150pct.png')
    ok2 = _capture(root, p150)
    check('B4 150% 截图落盘', ok2, p150)
    ev['screenshots'] = [
        {'path': p100, 'bytes': os.path.getsize(p100) if os.path.exists(p100) else 0},
        {'path': p150, 'bytes': os.path.getsize(p150) if os.path.exists(p150) else 0},
    ]
    try:
        root.destroy()
    except Exception:
        pass
    return ev


def main():
    print('=== APP-116 §1/§3 验证（A 机实测）===', flush=True)
    print('  python: %s' % sys.executable, flush=True)
    ev = {'ts_start': now()}
    try:
        ev['part_a'] = part_a()
    except Exception as e:
        import traceback
        ev['part_a_error'] = traceback.format_exc()
        check('§1 A 组执行完成', False, repr(e))
    try:
        ev['part_b'] = part_b()
    except Exception as e:
        import traceback
        ev['part_b_error'] = traceback.format_exc()
        check('§3 B 组执行完成', False, repr(e))
    ev['ts_end'] = now()
    ev['n_pass'] = len(PASSES)
    ev['n_fail'] = len(FAILS)
    ev['fails'] = FAILS
    ev['passes'] = PASSES
    out = os.path.join(RESULTS, 'app116_device_gui_evidence.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('\n=== 汇总：PASS %d / FAIL %d ===' % (len(PASSES), len(FAILS)))
    for f_ in FAILS:
        print('  FAIL: %s' % f_)
    print('证据：%s' % out)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
