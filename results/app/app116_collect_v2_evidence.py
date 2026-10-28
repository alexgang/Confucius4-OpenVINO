# -*- coding: utf-8 -*-
"""app116 — 收集 APP-027 V2（app114）实测产物的**证据清单**。

🔴🔴🔴 **为什么要单独一个脚本**（§81 纪律）：
  「没落盘的东西不能写『已交付』」⇒ STATUS 里列的每个产物都必须有
  **文件数 / mtime / 字节数 / SHA256** ⇒ 手工统计必错 ⇒ 机器生成。

## 采集口径

对 `C:\\Users\\Trekker-PTL\\app027_v2\\` 下的每个产物目录：

- 递归列出**全部文件**（路径 / 字节数 / mtime / SHA256）；
- 汇总**目录级**：文件数 / 总字节 / 最早 mtime / 最晚 mtime；
- 对每个 `v2_<cfg>_report.json`：把**原始字段**原样列出（不加工）；
- 对 `app027_v2_abba_summary.json`：把四臂对照表原样列出。

## 用法

    <pkg>/python/python.exe results/app/app116_collect_v2_evidence.py
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

HOME = r'C:\Users\Trekker-PTL'
OUT_DIR = os.path.join(HOME, 'app027_v2')
EVID = os.path.join(OUT_DIR, 'app116_v2_evidence.json')


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1024 * 1024)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def collect_dir(d: str):
    files = []
    for root, _dirs, names in os.walk(d):
        for n in sorted(names):
            p = os.path.join(root, n)
            try:
                st = os.stat(p)
                files.append(dict(
                    path=os.path.relpath(p, d).replace('\\', '/'),
                    bytes=st.st_size,
                    mtime=time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(st.st_mtime)),
                    sha256=sha256(p),
                ))
            except Exception as e:
                files.append(dict(path=os.path.relpath(p, d), error=repr(e)))
    total = sum(f.get('bytes') or 0 for f in files)
    mts = sorted(f['mtime'] for f in files if 'mtime' in f)
    return dict(
        dir=os.path.basename(d),
        n_files=len(files),
        total_bytes=total,
        mtime_min=(mts[0] if mts else None),
        mtime_max=(mts[-1] if mts else None),
        files=files,
    )


def main():
    if not os.path.isdir(OUT_DIR):
        print('!! 目录不存在：%s' % OUT_DIR)
        return 2
    dirs = []
    for name in sorted(os.listdir(OUT_DIR)):
        p = os.path.join(OUT_DIR, name)
        if os.path.isdir(p):
            dirs.append(p)

    out = dict(ts=time.strftime('%Y-%m-%d %H:%M:%S'),
               out_dir=OUT_DIR, dirs=[])

    for d in dirs:
        c = collect_dir(d)
        # 🔴 报告里的**原始字段**（原样列出，不加工）
        for rp in sorted(os.listdir(d)):
            if rp.endswith('_report.json'):
                try:
                    with open(os.path.join(d, rp), encoding='utf-8') as f:
                        c['report_raw'] = json.load(f)
                except Exception as e:
                    c['report_raw_error'] = repr(e)
        out['dirs'].append(c)

    # 汇总表
    sum_path = os.path.join(OUT_DIR, 'app027_v2_abba_summary.json')
    if os.path.exists(sum_path):
        with open(sum_path, encoding='utf-8') as f:
            out['abba_summary_raw'] = json.load(f)
        out['abba_summary_sha256'] = sha256(sum_path)
        out['abba_summary_bytes'] = os.path.getsize(sum_path)
        out['abba_summary_mtime'] = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(sum_path)))

    with open(EVID, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print('=' * 72)
    print('app116 — APP-027 V2 产物证据清单')
    print('=' * 72)
    for c in out['dirs']:
        print('  %-18s n_files=%-5s total_bytes=%-12s mtime %s ~ %s'
              % (c['dir'], c['n_files'], c['total_bytes'],
                 c['mtime_min'], c['mtime_max']))
    print('  汇总文件：%s' % os.path.basename(EVID))
    print('  sha256=%s  bytes=%s' % (sha256(EVID), os.path.getsize(EVID)))
    print('=' * 72)
    return 0


if __name__ == '__main__':
    sys.exit(main())
