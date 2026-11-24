#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""app260 — 校准「tk geometry 申请值」与「实际客户区」的**像素差**（纯 CPU，不占设备）。

## 为什么需要
app259 的 150 % 臂：应用算 `int(1080*1.5) x int(820*1.5)` = **1620×1230**
⇒ `root.geometry('1620x1230')` ⇒ 实测客户区 **1618×1229**（差 2/1 px）。
而 100 % 臂：应用算 **1439×1093** ⇒ 实测客户区 **1439×1093**（**逐像素一致**）。
⇒ 差值**不是**「口径写错」⇒ 需要弄清是 Tk 自身取整、还是 WM 裁剪。

## 本脚本测三件事
① 纯 Tk（不设 scaling）申请 `1620x1230` ⇒ 客户区实际多少？
② 设 scaling=1.5 后申请 `1620x1230` ⇒ 客户区实际多少？
③ 设 scaling=1.5 后申请 `1439x1093`（= 100 % 臂的申请值）⇒ 客户区实际多少？
   ⇒ 若③也是 1439×1093 ⇒ 说明 **scaling 不影响 geometry 的像素换算**
   ⇒ 则①的差值只能来自 WM/屏幕可用区裁剪。

## 用法
```
.venv/Scripts/python.exe results/app/_app260_tk_geometry_probe.py
```
"""
from __future__ import annotations

import ctypes
import json
import os
import tkinter as tk

user32 = ctypes.windll.user32
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'app260_tk_geometry_probe.json')


def client_size(hwnd):
    r = ctypes.wintypes.RECT()
    if not user32.GetClientRect(ctypes.c_void_p(hwnd), ctypes.byref(r)):
        return None
    return [r.right - r.left, r.bottom - r.top]


def win_size(hwnd):
    r = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r)):
        return None
    return [r.right - r.left, r.bottom - r.top]


def work_area():
    r = ctypes.wintypes.RECT()
    ok = user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)  # SPI_GETWORKAREA
    return [r.left, r.top, r.right, r.bottom] if ok else None


def probe(label, scale, req_w, req_h):
    root = tk.Tk()
    try:
        if scale is not None:
            root.tk.call('tk', 'scaling', scale)
        root.geometry('%dx%d+0+0' % (req_w, req_h))
        root.update_idletasks()
        root.update()
        hwnd = int(root.frame(), 16) if False else None
        # 取 Tk 顶层窗口的 hwnd（用 winfo_id 的父窗口）
        wid = root.winfo_id()
        top = user32.GetAncestor(wid, 2)  # GA_ROOT
        return {'label': label, 'scaling_set': scale,
                'requested': [req_w, req_h],
                'tk_scaling_actual': float(root.tk.call('tk', 'scaling')),
                'client': client_size(top) if top else None,
                'window_rect': win_size(top) if top else None,
                'winfo_reqwidth': root.winfo_reqwidth(),
                'winfo_reqheight': root.winfo_reqheight(),
                'winfo_width': root.winfo_width(),
                'winfo_height': root.winfo_height()}
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def main():
    out = {'script': '_app260_tk_geometry_probe.py',
           'work_area': work_area(), 'probes': []}
    print('work area =', out['work_area'])
    cases = [
        ('① 默认 scaling（1.333）申请 1620x1230', None, 1620, 1230),
        ('② scaling=1.5 申请 1620x1230', 1.5, 1620, 1230),
        ('③ scaling=1.5 申请 1439x1093', 1.5, 1439, 1093),
        ('④ scaling=1.0 申请 1620x1230', 1.0, 1620, 1230),
    ]
    for label, sc, w, h in cases:
        p = probe(label, sc, w, h)
        out['probes'].append(p)
        print('%-38s req=%s scaling=%s client=%s win=%s winfo=%sx%s'
              % (label, p['requested'], round(p['tk_scaling_actual'], 4),
                 p['client'], p['window_rect'],
                 p['winfo_width'], p['winfo_height']))
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('[evidence] %s' % OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
