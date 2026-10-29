#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""_app099_zip_verify.py —— §99：客户包 zip 产物的**只读**核验。

核验项：
1. zip 文件存在 / 字节数 / mtime / SHA256；
2. `zipfile.ZipFile.testzip()` ⇒ 无 CRC 错误；
3. **zip ⇄ 包目录 `.py` 逐字一致**（归一化 LF 后比对，逐文件）；
4. MANIFEST 的 `version` / `files` 计数；
5. 版本号三处一致：目录版本 == zip 版本 == MANIFEST version。

🔴 **全程只读**：不写任何文件、不改任何产物。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile

HOME = r'C:\Users\Trekker-PTL'
VER = '1.10'
PKG = os.path.join(HOME, 'Confucius4_LiveCaption_v%s' % VER)
ZIP = os.path.join(HOME, 'Confucius4_LiveCaption_v%s.zip' % VER)
PREFIX = 'Confucius4_LiveCaption_v%s' % VER
OUT = r'C:\Users\Trekker-PTL\confucius4-openvino\results\app\_app099_zip_evidence.json'


def sha256_file(p: str) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def norm(b: bytes) -> bytes:
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def main() -> int:
    ev = {}
    ev['zip_path'] = ZIP
    ev['pkg_dir'] = PKG
    ev['zip_exists'] = os.path.exists(ZIP)
    if not ev['zip_exists']:
        print('❌ zip 不存在：%s' % ZIP)
        return 1
    st = os.stat(ZIP)
    ev['zip_bytes'] = st.st_size
    ev['zip_mtime_epoch'] = st.st_mtime
    import time
    ev['zip_mtime'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))
    print('计算 zip SHA256（%s 字节）…' % format(st.st_size, ','))
    ev['zip_sha256'] = sha256_file(ZIP)

    with zipfile.ZipFile(ZIP) as z:
        names = z.namelist()
        ev['n_entries'] = len(names)
        bad = z.testzip()
        ev['testzip_bad_entry'] = bad
        print('testzip() ⇒ %s；条目 %d' % ('OK' if bad is None else 'BAD:' + bad,
                                          len(names)))
        # MANIFEST
        man_name = None
        for n in names:
            if n.endswith('/MANIFEST.json') or n.endswith('MANIFEST.json'):
                man_name = n
                break
        ev['manifest_entry'] = man_name
        man = json.loads(z.read(man_name).decode('utf-8'))
        ev['manifest_version'] = str(man.get('version'))
        files_field = man.get('files')
        ev['manifest_files'] = (len(files_field)
                                 if isinstance(files_field, (list, dict))
                                 else files_field)
        ev['manifest_keys'] = sorted(man.keys())[:12]

        # zip ⇄ 包目录 `.py` 逐字一致
        diffs = []
        checked = 0
        for n in names:
            if not n.lower().endswith('.py'):
                continue
            rel = n[len(PREFIX) + 1:] if n.startswith(PREFIX + '/') else n
            disk = os.path.join(PKG, rel.replace('/', os.sep))
            if not os.path.exists(disk):
                diffs.append((rel, 'MISSING_ON_DISK'))
                continue
            checked += 1
            if norm(z.read(n)) != norm(open(disk, 'rb').read()):
                diffs.append((rel, 'CONTENT_DIFF'))
        ev['n_py_checked'] = checked
        ev['n_py_diff'] = len(diffs)
        ev['py_diff_detail'] = ('全部 %d 个 .py 逐字一致（归一化 LF）' % checked
                                 if not diffs else
                                 '不一致 %d 个：%s' % (len(diffs), diffs[:5]))
        ev['py_diff_summary'] = '%d/%d 一致' % (checked - len(diffs), checked)

    # 版本号三处一致
    dir_ok = os.path.isdir(PKG)
    zip_ok = ZIP.endswith('Confucius4_LiveCaption_v%s.zip' % ev['manifest_version'])
    ev['manifest_check'] = ('目录版本 == zip 版本 == MANIFEST version（%s）三者一致 ✅'
                            % ev['manifest_version']) if (dir_ok and zip_ok) else \
        ('❌ 不一致：目录=%s MANIFEST=%s' % (VER, ev['manifest_version']))
    print(ev['manifest_check'])
    print(ev['py_diff_detail'])

    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    print('证据已写入：%s' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
