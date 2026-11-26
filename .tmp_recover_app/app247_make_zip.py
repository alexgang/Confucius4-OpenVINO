#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""§247（APP-147 第 5 步）：打 `Confucius4_LiveCaption_MiniMVP_v1.2.zip`。

纪律：
- **只写不删**（本机有安全删除 shim，删文件会失败）⇒ 源目录一字不动；
- 条目结构照抄 v1.1.1：**顶层带目录名**（`Confucius4_LiveCaption_MiniMVP_v1.2/...`），
  **不写目录条目**（只有文件条目）⇒ 与 `_app148_zip_consistency.py` 的比对口径一致；
- 目标 zip 已存在 ⇒ **直接拒绝**（不覆盖旧产物）；
- 每 500 个文件打一行进度，便于后台跑时看是否卡住；
- 完成后自己读回中央目录，核对条目数 == 写入数、字节数。
"""
import os
import sys
import time
import zipfile

SRC = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.2'
TOP = os.path.basename(SRC)                     # 顶层目录名
ZIP = SRC + '.zip'
LEVEL = 6


def main():
    if os.path.exists(ZIP):
        print('拒绝：zip 已存在（不覆盖旧产物）%s' % ZIP)
        return 2
    if not os.path.isdir(SRC):
        print('源目录不存在：%s' % SRC)
        return 2

    files = []
    for dp, dns, fns in os.walk(SRC):
        dns.sort()
        for fn in sorted(fns):
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, SRC).replace('\\', '/')
            files.append((full, rel))
    total_bytes = sum(os.path.getsize(f) for f, _ in files)
    print('源：%s\n  文件 %d 个 / %d B (%.3f GiB)' %
          (SRC, len(files), total_bytes, total_bytes / 1024 ** 3), flush=True)

    t0 = time.time()
    n_done = 0
    n_bytes = 0
    with zipfile.ZipFile(ZIP, 'w', zipfile.ZIP_DEFLATED, compresslevel=LEVEL) as zf:
        for full, rel in files:
            arc = '%s/%s' % (TOP, rel)
            zf.write(full, arc)
            n_done += 1
            n_bytes += os.path.getsize(full)
            if n_done % 500 == 0 or n_done == len(files):
                el = time.time() - t0
                print('  %5d/%d  %5.1f%%  %6.1f s  写入 %6.2f GiB，zip 当前 %.2f GiB'
                      % (n_done, len(files), 100.0 * n_done / len(files), el,
                         n_bytes / 1024 ** 3,
                         os.path.getsize(ZIP) / 1024 ** 3), flush=True)

    el = time.time() - t0
    size = os.path.getsize(ZIP)
    with zipfile.ZipFile(ZIP, 'r') as zf:
        infos = zf.infolist()
    print('\n完成：%.1f s' % el)
    print('  zip 字节数 = %d (%.3f GiB)' % (size, size / 1024 ** 3))
    print('  zip 条目数 = %d（写入 %d）一致=%s' % (len(infos), len(files),
                                                len(infos) == len(files)))
    print('  压缩率 = %.1f%%' % (100.0 * size / total_bytes))
    ok = (len(infos) == len(files) and os.path.getsize(ZIP) > 0)
    print('结果：%s' % ('OK' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
