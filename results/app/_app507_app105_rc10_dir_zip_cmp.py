# -*- coding: utf-8 -*-
r"""_app507 — rc10 **包目录 vs zip 逐项逐字节比对**（只读，不改任何东西）。

比 rc9 的 `_app498` 更严：不仅比**清单**，还比**每一个文件的字节**
（SHA-256）⇒ 证明「zip 里就是包里现在这份代码」（APP-055「包里对 ≠ 已交付」的
反向核对）。

判据：
  * zip 条目集合 == 磁盘文件集合（**两边各自独有的必须是 0**）；
  * 每个文件的 SHA-256 相同（**mismatch 必须是 0**）；
  * `zipfile.testzip()` 返回 None（⇒ CRC 全对）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile

ROOT = r'C:\Users\Trekker-PTL\Confucius4_LiveCaption_MiniMVP_v1.0-rc10'
ZIP = r'C:\Users\Trekker-PTL\shared\minimvp\Confucius4_LiveCaption_MiniMVP_v1.0-rc10_perftest.zip'
REPORT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'app507_app105_rc10_dir_zip_cmp.json')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    prefix = os.path.basename(ROOT) + '/'
    ev = {'root': ROOT, 'zip': ZIP}
    disk = {}
    for dp, _dn, fn in os.walk(ROOT):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
            disk[rel] = p
    ev['n_disk_files'] = len(disk)

    mismatch = []
    only_zip = []
    only_disk = []
    with zipfile.ZipFile(ZIP) as z:
        names = set()
        for i in z.infolist():
            if i.is_dir():
                continue
            name = i.filename.replace('\\', '/')
            if name.startswith(prefix):
                name = name[len(prefix):]
            names.add(name)
            if name not in disk:
                only_zip.append(name)
                continue
            # 逐字节：磁盘 SHA vs zip 条目 SHA
            h = hashlib.sha256()
            with z.open(i) as fh:
                for chunk in iter(lambda: fh.read(1 << 22), b''):
                    h.update(chunk)
            if h.hexdigest() != sha256_file(disk[name]):
                mismatch.append(name)
        ev['testzip'] = z.testzip()
    only_disk = sorted(set(disk) - names)
    ev['n_zip_entries'] = len(names)
    ev['only_in_zip'] = only_zip[:20]
    ev['n_only_in_zip'] = len(only_zip)
    ev['only_in_disk'] = only_disk[:20]
    ev['n_only_in_disk'] = len(only_disk)
    ev['n_byte_mismatch'] = len(mismatch)
    ev['byte_mismatch_sample'] = mismatch[:20]
    ev['zip_bytes'] = os.path.getsize(ZIP)
    ev['pass'] = (not only_zip and not only_disk and not mismatch
                  and ev['testzip'] is None)
    with open(REPORT, 'w', encoding='utf-8') as f:
        json.dump(ev, f, ensure_ascii=False, indent=1)
    print('zip 条目 %d ／ 磁盘文件 %d' % (ev['n_zip_entries'],
                                        ev['n_disk_files']))
    print('只在 zip %d ／ 只在磁盘 %d ／ 字节不一致 %d ／ testzip %r'
          % (ev['n_only_in_zip'], ev['n_only_in_disk'],
             ev['n_byte_mismatch'], ev['testzip']))
    print('RESULT: %s' % ('PASS' if ev['pass'] else 'FAIL'))
    return 0 if ev['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
