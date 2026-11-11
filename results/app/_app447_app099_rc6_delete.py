#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""_app447_app099_rc6_delete.py — APP-099 第 0 节第 4 条：删除作废 rc6。

## 用户决定（原文）
> 「**删除作废的 rc6**：`Confucius4_LiveCaption_MiniMVP_v1.0-rc6` 的目录和 zip
>  （只删 rc6，rc5、rc7 都不动）。删除前后各记一次 C 盘剩余空间，写进 STATUS。」

## 🔴 安全纪律
* **只碰两个确切路径**；执行前断言 rc5 / rc7 目录与 zip **不在**删除清单里。
* 用 Win32 ``SHFileOperationW`` + ``FOF_ALLOWUNDO`` ⇒ **进回收站（可逆）**，
  不做 ``shutil.rmtree`` / ``os.remove``，不用通配。
* 不在 Python 里遍历 5.6 GB 目录树（上一轮就是遍历超时被 SIGTERM）⇒
  把整目录一次交给 Shell；只做 ``os.path.isdir/isfile`` 轻量检查。
* 删除前后各取一次 C 盘剩余空间（``GetDiskFreeSpaceExW``）。
* 本脚本**只在设备作业结束后运行**（大 I/O 会污染 ``timing_valid``）。

用法：
    .venv/Scripts/python.exe results/app/_app447_app099_rc6_delete.py --apply
    （不带 --apply ⇒ 只做 dry-run，列出将删除的路径与当前空间，不删任何东西）
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
from ctypes import wintypes

ROOT = r'C:\Users\Trekker-PTL'
RC6_DIR = os.path.join(ROOT, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc6')
RC6_ZIP = os.path.join(ROOT, 'shared', 'minimvp',
                       'Confucius4_LiveCaption_MiniMVP_v1.0-rc6_perftest.zip')
OUT = os.path.join(ROOT, 'confucius4-openvino', 'results', 'app',
                   'app438_app099_rc6_delete.json')

# 绝不能碰的兄弟版本（前置断言）
PROTECTED = [
    os.path.join(ROOT, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5'),
    os.path.join(ROOT, 'Confucius4_LiveCaption_MiniMVP_v1.0-rc7'),
    os.path.join(ROOT, 'shared', 'minimvp',
                 'Confucius4_LiveCaption_MiniMVP_v1.0-rc5_perftest.zip'),
    os.path.join(ROOT, 'shared', 'minimvp',
                 'Confucius4_LiveCaption_MiniMVP_v1.0-rc7_perftest.zip'),
]

FOF_ALLOWUNDO = 0x0040
FOF_NOCONFIRMATION = 0x0010
FOF_SILENT = 0x0004
FOF_NOERRORUI = 0x0400
FOF_NOCONFIRMMKDIR = 0x0200
FO_DELETE = 0x0003


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ('hwnd', wintypes.HWND),
        ('wFunc', wintypes.UINT),
        ('pFrom', wintypes.LPCWSTR),
        ('pTo', wintypes.LPCWSTR),
        ('fFlags', ctypes.c_uint16),
        ('fAnyOperationsAborted', wintypes.BOOL),
        ('hNameMappings', ctypes.c_void_p),
        ('lpszProgressTitle', wintypes.LPCWSTR),
    ]


def free_gb():
    free = ctypes.c_ulonglong(0)
    total = ctypes.c_ulonglong(0)
    totalfree = ctypes.c_ulonglong(0)
    ok = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p('C:\\'),
        ctypes.byref(free), ctypes.byref(total), ctypes.byref(totalfree))
    if not ok:
        raise ctypes.WinError()
    return round(free.value / 1024 ** 3, 3), round(total.value / 1024 ** 3, 3)


def recycle(paths):
    """把若干路径整体送进回收站（双 NUL 结尾，一次调用）。"""
    buf = '\0'.join(paths) + '\0\0'
    op = SHFILEOPSTRUCTW()
    op.hwnd = None
    op.wFunc = FO_DELETE
    op.pFrom = buf
    op.pTo = None
    op.fFlags = (FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT |
                 FOF_NOERRORUI | FOF_NOCONFIRMMKDIR)
    op.fAnyOperationsAborted = False
    op.hNameMappings = None
    op.lpszProgressTitle = None
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return {'rc': rc, 'aborted': bool(op.fAnyOperationsAborted)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正删除（默认 dry-run）')
    a = ap.parse_args()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ev = {
        'task': 'APP-099 第 0 节第 4 条：删除作废 rc6（只删 rc6）',
        'created_at': now,
        'mode': 'APPLY' if a.apply else 'DRY_RUN',
        'method': 'Win32 SHFileOperationW + FOF_ALLOWUNDO（回收站，可逆）',
        'targets': [RC6_DIR, RC6_ZIP],
        'protected_must_not_be_touched': PROTECTED,
        'before': {}, 'after': {}, 'delete_result': None,
        'pass': False,
    }
    # 🔴 前置断言：删除清单里绝不能出现 rc5 / rc7
    ev['no_protected_in_targets'] = all(
        not any(os.path.normcase(q).startswith(os.path.normcase(p)) for p in PROTECTED)
        for q in ev['targets'])
    ev['before'] = {
        'free_gb': free_gb()[0], 'total_gb': free_gb()[1],
        'rc6_dir_exists': os.path.isdir(RC6_DIR),
        'rc6_zip_exists': os.path.isfile(RC6_ZIP),
        'rc6_zip_bytes': os.path.getsize(RC6_ZIP) if os.path.isfile(RC6_ZIP) else None,
        'protected': {os.path.basename(p): (os.path.isdir(p) or os.path.isfile(p))
                      for p in PROTECTED},
    }
    print(json.dumps(ev['before'], ensure_ascii=False, indent=1), flush=True)
    if not ev['no_protected_in_targets']:
        ev['error'] = '删除清单含 rc5/rc7 ⇒ 拒绝执行（fail-closed）'
        json.dump(ev, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('🔴 ' + ev['error'], flush=True)
        return 2
    if not a.apply:
        ev['pass'] = True
        ev['note'] = 'dry-run：未删任何文件'
        json.dump(ev, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('[dry-run] 未删除；加 --apply 才执行', flush=True)
        return 0

    targets = [p for p in ev['targets']
               if os.path.isdir(p) or os.path.isfile(p)]
    ev['actually_targeted'] = targets
    if targets:
        ev['delete_result'] = recycle(targets)
        print('[recycle] %s' % ev['delete_result'], flush=True)
    ev['after'] = {
        'free_gb': free_gb()[0], 'total_gb': free_gb()[1],
        'rc6_dir_exists': os.path.isdir(RC6_DIR),
        'rc6_zip_exists': os.path.isfile(RC6_ZIP),
        'protected': {os.path.basename(p): (os.path.isdir(p) or os.path.isfile(p))
                      for p in PROTECTED},
    }
    ev['freed_gb'] = round(ev['after']['free_gb'] - ev['before']['free_gb'], 3)
    # 🔴 判据修正（本轮 app453 复核）：SHFileOperationW 的 rc 是**诊断码**，
    #    不是成功判据；FOF_ALLOWUNDO 送回收站不释放磁盘空间 ⇒ freed_gb
    #    也只是「删除前后各记一次」的记录，不作为成功条件。
    #    成功 = 两个目标不在原位 + 四个保护对象完好；可逆性由 app453 复核
    #    回收站 $I/$R 记录（Win10 路径字段从 offset 28 起）。
    ev['pass'] = bool(
        ev['no_protected_in_targets']
        and not ev['after']['rc6_dir_exists']
        and not ev['after']['rc6_zip_exists']
        and all(ev['after']['protected'].values()))
    ev['shfileop_rc_is_diagnostic_only'] = True
    ev['reversibility_checked_by'] = 'app453_app099_rc6_delete_recheck.json'
    json.dump(ev, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: ev[k] for k in
                      ('pass', 'freed_gb', 'after', 'delete_result')},
                     ensure_ascii=False, indent=1), flush=True)
    return 0 if ev['pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
